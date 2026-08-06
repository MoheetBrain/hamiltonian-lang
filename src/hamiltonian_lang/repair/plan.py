"""The repair plan — what a Teacher may say, and the boundary it may not cross.

INTERVENOR's finding, and the constraint it forces
--------------------------------------------------
Self-repair fails when one model stays trapped in its original interpretation
("Degeneration-of-Thought"): asked to fix its own output, it re-derives the same wrong
thing with more confidence. The fix is **role separation** — a Teacher receives the broken
program, the diagnostic and the failed checks, and returns *the cause and a repair plan*,
explicitly **not the corrected program**; a separate Learner applies the plan.

That "explicitly not" is the whole load-bearing constraint of the H3 programme. A plan
that contains the corrected program converts the measurement into a tautology: the Learner
copies, the verifier passes, and the number reported as "verifier-guided repair improved
the answer" measures transcription. Worse, nothing in the resulting record distinguishes
that run from a real one — the transcript looks identical.

So the boundary is enforced in code, not in a prompt. :class:`RepairPlan` refuses to be
constructed empty, :func:`plan_leak_reasons` states every way a plan crosses the line, and
:func:`assert_plan_non_leaking` raises rather than returns a warning. The Teacher calls it
on every plan it emits.

What a plan may contain
-----------------------
Six fields, and no seventh:

``failing_invariant``            the rule that was broken
``cause``                        why the construct breaks it
``source_span``                  where
``expected_semantic_category``   the *kind* of thing that belongs there
``repair_steps``                 what class of edit to make
``preservation_constraints``     what must not change while making it

``expected_semantic_category`` is a category, not a value: "a positive real scale
parameter", never "0.5". The distinction is the difference between telling a student that
the argument must be positive and telling them the answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..context_broker import ContextStatus, ErrorClass
from ..improvement.diagnostics import SourceSpan

__all__ = [
    "PLAN_VERSION",
    "MAX_STEPS",
    "MAX_STEP_LINES",
    "STATEMENT_KEYWORDS",
    "RepairPlan",
    "NoPlan",
    "PlanLeak",
    "statement_lines",
    "is_program_like",
    "plan_leak_reasons",
    "assert_plan_non_leaking",
]

PLAN_VERSION = "hml-repair-plan-1.0.0"

#: A plan longer than this stops being a plan and becomes a transcript of the answer.
MAX_STEPS = 6

#: A single step spanning more lines than this is a patch, not an instruction.
MAX_STEP_LINES = 2


class PlanLeak(Exception):
    """A repair plan carried information the Learner must derive for itself."""


@dataclass(frozen=True)
class NoPlan:
    """The Teacher declined to produce a plan, and why.

    A first-class result rather than ``None``. "The invariant is unknown and retrieval
    found nothing" is a real, reportable outcome of a repair turn; collapsing it into a
    missing value would let a null be counted as a failure of the Learner.
    """

    reason: str
    error_class: ErrorClass | None = None
    context_status: ContextStatus = ContextStatus.NO_RELEVANT_CONTEXT

    def to_dict(self) -> dict[str, Any]:
        return {
            "no_plan": True,
            "reason": self.reason,
            "error_class": None if self.error_class is None else str(self.error_class),
            "context_status": str(self.context_status),
        }


@dataclass(frozen=True)
class RepairPlan:
    """The Teacher's whole output. Cause and plan; never the corrected program."""

    failing_invariant: str
    cause: str
    source_span: SourceSpan
    expected_semantic_category: str
    repair_steps: tuple[str, ...]
    preservation_constraints: tuple[str, ...]
    error_class: ErrorClass
    context_status: ContextStatus
    #: ``provenance`` strings from every retrieved context item used to build this plan.
    #: Empty means the plan rests on the diagnostic alone, which is a weaker plan and is
    #: recorded as such rather than dressed up.
    context_provenance: tuple[str, ...] = ()
    diagnostic_code: str = ""
    #: Where ``failing_invariant`` came from: the compiler's invariant table, a retrieved
    #: context item, or the class-level rule. Metadata, not one of the six plan fields —
    #: but the field that makes "never hallucinate a rule" auditable after the fact.
    invariant_source: str = ""
    plan_version: str = PLAN_VERSION

    def __post_init__(self) -> None:
        for name in (
            "failing_invariant", "cause", "expected_semantic_category",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(
                    f"RepairPlan.{name} is empty. A plan missing this field is not a "
                    "weaker plan, it is an unusable one; emit NoPlan instead."
                )
        if not self.repair_steps:
            raise ValueError(
                "RepairPlan.repair_steps is empty; a plan with no steps tells the Learner "
                "nothing. Emit NoPlan if no step can be stated."
            )
        if len(self.repair_steps) > MAX_STEPS:
            raise ValueError(
                f"RepairPlan has {len(self.repair_steps)} steps (limit {MAX_STEPS}). "
                "A step-by-step transcript long enough to be followed mechanically is a "
                "corrected program written in prose."
            )
        if not self.preservation_constraints:
            raise ValueError(
                "RepairPlan.preservation_constraints is empty. A repair with no stated "
                "invariant to preserve licenses the Learner to delete the failing "
                "construct, which passes the checker and destroys the meaning."
            )
        if not isinstance(self.error_class, ErrorClass):
            raise TypeError("RepairPlan.error_class must be an ErrorClass member")
        if not isinstance(self.context_status, ContextStatus):
            raise TypeError("RepairPlan.context_status must be a ContextStatus member")

    # -- rendering ---------------------------------------------------------------

    def text_fields(self) -> list[str]:
        """Every free-text field. What :func:`plan_leak_reasons` inspects."""
        return [
            self.failing_invariant,
            self.cause,
            self.expected_semantic_category,
            *self.repair_steps,
            *self.preservation_constraints,
        ]

    def render(self) -> str:
        """The plan as the Learner receives it."""
        span = self.source_span
        where = (
            f"{span.file}:{span.line}:{span.col + 1}" if span.located else "not attributed"
        )
        lines = [
            f"failing invariant: {self.failing_invariant}",
            f"cause: {self.cause}",
            f"source span: {where}",
            f"expected semantic category: {self.expected_semantic_category}",
            "repair plan:",
        ]
        lines += [f"  {n}. {s}" for n, s in enumerate(self.repair_steps, start=1)]
        lines.append("preservation constraints:")
        lines += [f"  - {c}" for c in self.preservation_constraints]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "failing_invariant": self.failing_invariant,
            "cause": self.cause,
            "source_span": self.source_span.to_dict(),
            "expected_semantic_category": self.expected_semantic_category,
            "repair_steps": list(self.repair_steps),
            "preservation_constraints": list(self.preservation_constraints),
            "error_class": str(self.error_class),
            "context_status": str(self.context_status),
            "context_provenance": list(self.context_provenance),
            "diagnostic_code": self.diagnostic_code,
            "invariant_source": self.invariant_source,
            "plan_version": self.plan_version,
        }


# ---------------------------------------------------------------------------
# The non-leaking contract
# ---------------------------------------------------------------------------

#: Statement keywords — the tokens a Hamiltonian Lang statement may open with. More than
#: one in a single step means the step is a program. Public because the leakage harness's
#: reconstruction probe needs the *same* notion of "this line is a statement, not prose";
#: two definitions of that would drift and the drift would be invisible.
STATEMENT_KEYWORDS = (
    "module", "param", "const", "var", "obs", "result", "def", "law", "prior",
    "likelihood", "assume", "require", "prove", "minimise", "maximise", "minimize",
    "maximize", "solve", "infer", "check", "concept",
)

#: An assignment whose right-hand side is a concrete value rather than an elision.
_BOUND_VALUE = re.compile(r":=\s*(?!\.\.\.)(?P<rhs>[^\n]+)")

_NUMERAL = re.compile(r"(?<![A-Za-z0-9_.])-?\d+(?:\.\d+)?(?![A-Za-z0-9_])")

_WS = re.compile(r"\s+")

#: Below this many significant tokens a fragment is too short for containment to mean
#: anything: every plan mentioning ``x`` would otherwise count as a leak. It is a floor on
#: *fragments only* — see :func:`is_program_like`.
_MIN_PROGRAM_TOKENS = 4

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9.]+")

#: A line is a *statement* when its first token opens one. Prose imperatives ("Read the
#: rule above.", "Do not delete the failing construct.") never do, which separates an
#: instruction from a program without parsing either.
_LEADING_KEYWORD = re.compile(
    rf"^\s*(?:{'|'.join(sorted(STATEMENT_KEYWORDS, key=len, reverse=True))})\s+\S"
)


def _normalise(text: str) -> str:
    return _WS.sub(" ", text).strip()


def statement_lines(text: str) -> list[str]:
    """Every line of ``text`` that opens with a statement keyword, in order.

    The shared definition of "this is a program line, not prose". Both the leak detector
    here and the leakage harness's reconstruction probe use it; two definitions would
    drift, and a drift between them would show up as the two mechanisms disagreeing about
    whether a plan carries the answer — silently, in opposite directions.
    """
    return [_normalise(line) for line in text.splitlines() if _LEADING_KEYWORD.match(line)]


def is_program_like(text: str) -> bool:
    """Whether ``text`` is substantial enough that containing it verbatim means something.

    Either it is long enough to be a fragment worth matching, **or** it opens with a
    statement keyword — a complete statement is a complete statement however short.
    ``param x : Real`` carries three significant tokens and is nonetheless the whole
    answer to an unknown-type diagnostic; a pure token-count floor lets exactly that
    class of short corrected statement through unflagged.
    """
    normalised = _normalise(text)
    if not normalised:
        return False
    return (
        len(_TOKEN.findall(normalised)) >= _MIN_PROGRAM_TOKENS
        or _LEADING_KEYWORD.match(normalised) is not None
    )


def plan_leak_reasons(
    plan: RepairPlan,
    *,
    target_program: str | None = None,
    final_answer: str | None = None,
    known_numerals: tuple[str, ...] = (),
    forbid_novel_numerals: bool = False,
) -> list[str]:
    """Every way ``plan`` crosses the Teacher/Learner boundary. Empty means clean.

    ``forbid_novel_numerals`` is the H3-specific check. When the endpoint is a
    *mathematical answer*, any numeral in the plan that did not come from the broken
    output, the diagnostic or the retrieved context is a candidate answer, and the
    Learner has no way to distinguish "the Teacher told me" from "I derived it".
    ``known_numerals`` is the whitelist of numerals that were already visible.
    """
    reasons: list[str] = []
    fields = plan.text_fields()
    haystack = _normalise(" \n ".join(fields))

    if target_program:
        needle = _normalise(target_program)
        if is_program_like(needle) and needle in haystack:
            reasons.append(
                "the plan contains the complete corrected program; a Learner given the "
                "answer measures transcription, not verifier-guided repair"
            )

    if final_answer:
        answer = _normalise(final_answer)
        if answer and answer in haystack:
            reasons.append(
                "the plan contains the final mathematical answer; any H3 result computed "
                "from this episode would be uninterpretable"
            )

    for n, step in enumerate(plan.repair_steps, start=1):
        lines = [ln for ln in step.splitlines() if ln.strip()]
        if len(lines) > MAX_STEP_LINES:
            reasons.append(
                f"repair step {n} spans {len(lines)} lines (limit {MAX_STEP_LINES}); a "
                "step that long is a replacement patch rather than an instruction"
            )
        found = {
            kw for kw in STATEMENT_KEYWORDS
            if re.search(rf"(?<![A-Za-z0-9_]){kw}\s", step)
        }
        if len(found) > 1:
            reasons.append(
                f"repair step {n} contains multiple statement keywords {sorted(found)}; "
                "it is a program fragment, not an instruction"
            )
        for m in _BOUND_VALUE.finditer(step):
            rhs = m.group("rhs").strip()
            if _NUMERAL.search(rhs):
                reasons.append(
                    f"repair step {n} binds a concrete value ({rhs!r}); a plan states the "
                    "category a value must belong to, never the value"
                )
                break

    if forbid_novel_numerals:
        allowed = set(known_numerals)
        novel = sorted(
            {m.group(0) for f in fields for m in _NUMERAL.finditer(f)} - allowed
        )
        if novel:
            reasons.append(
                f"the plan introduces numerals not present in the broken output, the "
                f"diagnostic or the retrieved context: {novel}. At a mathematical "
                "endpoint a novel numeral is indistinguishable from the answer."
            )
    return reasons


def assert_plan_non_leaking(
    plan: RepairPlan,
    *,
    target_program: str | None = None,
    final_answer: str | None = None,
    known_numerals: tuple[str, ...] = (),
    forbid_novel_numerals: bool = False,
) -> RepairPlan:
    """Raise :class:`PlanLeak` if the boundary is crossed; return the plan otherwise."""
    reasons = plan_leak_reasons(
        plan,
        target_program=target_program,
        final_answer=final_answer,
        known_numerals=known_numerals,
        forbid_novel_numerals=forbid_novel_numerals,
    )
    if reasons:
        raise PlanLeak(f"{plan.diagnostic_code or 'plan'}: " + "; ".join(reasons))
    return plan
