"""Synthetic mutations: every scorer facet proved able to pass **and** to fail.

The HML-EVAL-001 pilot shipped a scorer whose semantic-preservation facet returned 0.0
when nothing was checkable. Nothing caught it because nothing had ever exercised the
branch. The rule taken from that: *a facet that has never been observed failing is not
known to work.*

Each entry below is a fully specified trial with the outcome the scorer must produce.
``tests/evaluation/test_syntax_gate_scorer.py`` runs every one and asserts the exact
value, and separately asserts that the facets covered here are exactly ``scorer.FACETS``
— so adding a facet without a failing mutation breaks the build.

Everything here is offline. No mutation calls a model.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable

from evaluation.v1.score_v1 import NotMeasured

from .candidates import (
    A_V0_LINEAR,
    C_SEXPR,
    SE_CONTROL,
    SyntaxAdapter,
    V0LinearAdapter,
)
from .scorer import FACETS, ScoredTrial, TrialInput, score_trial
from .tasks import GateTask, build_track_a

__all__ = ["Mutation", "MUTATIONS", "run_mutation", "covered_facets"]


def _task(domain: str | None = None) -> GateTask:
    corpus = build_track_a()
    if domain is None:
        return corpus[0]
    return next(t for t in corpus if t.domain == domain)


#: A task whose answer key populates comparable facets (entities/types/kinds).
_T_FACETED = _task()
#: A task whose answer key populates only ``quantifier_order`` -- still comparable.
_T_QUANT = _task("quantifier_scope")

_GOOD = _T_FACETED.cso.reference_hml
_BROKEN_SYNTAX = "module BindingChain\nconst a : Real = ((\n"
_BROKEN_TYPE = "module BindingChain\nconst a : Probability = 2\n"
_UNRESOLVED = "module BindingChain\ndef y : Real := zzz + 1\n"
#: Parses cleanly, mistranslates: every `const` becomes a `var`, which is a different
#: epistemic status, and the numeric literals are dropped.
_MISTRANSLATED = (
    "module BindingChain\n\n"
    "var koppa : Real\nvar kappa : Real\n"
    "def gamma : Real := koppa + kappa\n"
    "def xi : Real := gamma * 5\n"
    "def varrho : Real := xi - koppa + 8\nsolve varrho\n"
)


def _reply(encoding: str, answer: str = "40.0", tag: str = "hml") -> str:
    return f"Working.\n\n```{tag}\n{encoding}```\n\n<ANSWER>{answer}</ANSWER>"


def _trial(**kw: Any) -> TrialInput:
    base = TrialInput(
        trial_id="mut", run_id="mutation-suite", task_id=_T_FACETED.id,
        condition=A_V0_LINEAR, curriculum_size=0,
        content=_reply(_GOOD), completion_tokens=120, prompt_tokens=800,
        latency_s=3.2, finish_reason="stop",
    )
    return replace(base, **kw)


@dataclass(frozen=True)
class Mutation:
    facet: str
    name: str
    #: "pass" = the facet reports its healthy value; "fail" = its unhealthy value.
    kind: str
    trial: TrialInput
    task: GateTask
    adapter: SyntaxAdapter | None
    #: What the scorer must produce. Called with the ScoredTrial; returns (ok, detail).
    expect: Callable[[ScoredTrial], tuple[bool, str]]
    why: str


def _eq(field: str, want: Any) -> Callable[[ScoredTrial], tuple[bool, str]]:
    def check(s: ScoredTrial) -> tuple[bool, str]:
        got = getattr(s, field)
        return got == want, f"{field}={got!r} want {want!r}"

    return check


def _is_not_measured(field: str) -> Callable[[ScoredTrial], tuple[bool, str]]:
    def check(s: ScoredTrial) -> tuple[bool, str]:
        got = getattr(s, field)
        return isinstance(got, NotMeasured), f"{field}={got!r} want NotMeasured"

    return check


def _approx(field: str, want: float, tol: float = 1e-9):
    def check(s: ScoredTrial) -> tuple[bool, str]:
        got = getattr(s, field)
        if isinstance(got, NotMeasured):
            return False, f"{field} is NotMeasured, want {want}"
        return abs(float(got) - want) <= tol, f"{field}={got!r} want {want}"

    return check


def _lt(field: str, bound: float):
    def check(s: ScoredTrial) -> tuple[bool, str]:
        got = getattr(s, field)
        if isinstance(got, NotMeasured):
            return False, f"{field} is NotMeasured, want < {bound}"
        return float(got) < bound, f"{field}={got!r} want < {bound}"

    return check


_A = V0LinearAdapter()

MUTATIONS: tuple[Mutation, ...] = (
    # -- first_attempt_parse -------------------------------------------------
    Mutation(
        "first_attempt_parse", "clean encoding parses", "pass",
        _trial(), _T_FACETED, _A, _eq("first_attempt_parse", True),
        "the reference encoding is a correct encoding by definition",
    ),
    Mutation(
        "first_attempt_parse", "unbalanced parentheses fail", "fail",
        _trial(content=_reply(_BROKEN_SYNTAX)), _T_FACETED, _A,
        _eq("first_attempt_parse", False),
        "HML-P231; if this passed, the parse rate would be a constant",
    ),
    # -- repaired_parse ------------------------------------------------------
    Mutation(
        "repaired_parse", "one repair fixes a syntax error", "pass",
        _trial(content=_reply(_BROKEN_SYNTAX), repair_attempted=True,
               repair_content=_reply(_GOOD), repair_completion_tokens=90,
               repair_latency_s=2.1),
        _T_FACETED, _A, _eq("repaired_parse", True),
        "repaired parse must be able to exceed first-attempt parse",
    ),
    Mutation(
        "repaired_parse", "a repair that is still broken does not count", "fail",
        _trial(content=_reply(_BROKEN_SYNTAX), repair_attempted=True,
               repair_content=_reply(_BROKEN_TYPE), repair_completion_tokens=90,
               repair_latency_s=2.1),
        _T_FACETED, _A, _eq("repaired_parse", False),
        "a repair loop that always reports success is not a repair loop",
    ),
    # -- semantic_preservation ----------------------------------------------
    Mutation(
        "semantic_preservation", "reference encoding preserves everything", "pass",
        _trial(), _T_FACETED, _A, _approx("semantic_preservation", 1.0),
        "the corpus self-consistency test asserts this is 1.0",
    ),
    Mutation(
        "semantic_preservation", "parses but mistranslates the epistemic status", "fail",
        _trial(content=_reply(_MISTRANSLATED)), _T_FACETED, _A,
        _lt("semantic_preservation", 1.0),
        "const rewritten as var is a different claim about what is known",
    ),
    Mutation(
        "semantic_preservation", "no facets in the answer key is NOT MEASURED", "fail",
        _trial(task_id="synthetic_no_facets"), _T_FACETED, _A,
        _is_not_measured("semantic_preservation"),
        "**the exact pilot defect**: nothing checkable must be NotMeasured, not 0.0",
    ),
    Mutation(
        "semantic_preservation", "facets present but no encoding is a measured 0.0",
        "fail",
        _trial(content="No encoding here at all.\n\n<ANSWER>40.0</ANSWER>"),
        _T_FACETED, _A, _approx("semantic_preservation", 0.0),
        "the mirror image: a real failure must not hide behind NotMeasured",
    ),
    # -- empty_or_truncated --------------------------------------------------
    Mutation(
        "empty_or_truncated", "a complete reply is neither", "pass",
        _trial(), _T_FACETED, _A, _eq("empty_or_truncated", False),
        "",
    ),
    Mutation(
        "empty_or_truncated", "an empty visible answer is a model failure", "fail",
        _trial(content="", reasoning="a long reasoning trace", completion_tokens=2400,
               finish_reason="length"),
        _T_FACETED, _A, _eq("failure_category", "empty_visible_answer"),
        "never silently retried; the reasoning channel eating the budget is a property "
        "of the model under this representation",
    ),
    Mutation(
        "empty_or_truncated", "a truncated but non-empty reply is flagged", "fail",
        _trial(content=_reply(_GOOD), finish_reason="length"), _T_FACETED, _A,
        _eq("empty_or_truncated", True),
        "truncation is a distinct outcome from emptiness",
    ),
    # -- visible_output_length ----------------------------------------------
    Mutation(
        "visible_output_length", "counts the visible channel only", "pass",
        _trial(content="abcdef", reasoning="x" * 5000), _T_FACETED, _A,
        _eq("visible_output_length", 6),
        "the reasoning trace is not visible output and must not inflate this",
    ),
    Mutation(
        "visible_output_length", "an empty reply measures zero", "fail",
        _trial(content=""), _T_FACETED, _A, _eq("visible_output_length", 0),
        "",
    ),
    # -- completion_tokens_reasoning_inclusive -------------------------------
    Mutation(
        "completion_tokens_reasoning_inclusive",
        "2 characters of content billing 43 completion tokens reports 43", "pass",
        _trial(content="ok", reasoning="r" * 4000, completion_tokens=43),
        _T_FACETED, _A, _eq("completion_tokens_reasoning_inclusive", 43),
        "Ollama bills the reasoning channel to completion_tokens "
        "(docs/evaluation/LOCAL_MODEL_MANIFEST.md); a scorer that counted visible "
        "characters would report ~1 and understate the cost by 40x",
    ),
    Mutation(
        "completion_tokens_reasoning_inclusive", "a repair adds to the cost", "fail",
        _trial(completion_tokens=120, repair_attempted=True,
               repair_content=_reply(_GOOD), repair_completion_tokens=90),
        _T_FACETED, _A, _eq("completion_tokens_reasoning_inclusive", 210),
        "charging only the first attempt would make the repair arm look free",
    ),
    # -- latency_s -----------------------------------------------------------
    Mutation(
        "latency_s", "a single call reports its own latency", "pass",
        _trial(latency_s=3.2), _T_FACETED, _A, _approx("latency_s", 3.2, 1e-6),
        "",
    ),
    Mutation(
        "latency_s", "a repair adds to the latency", "fail",
        _trial(latency_s=3.2, repair_attempted=True, repair_content=_reply(_GOOD),
               repair_latency_s=2.1),
        _T_FACETED, _A, _approx("latency_s", 5.3, 1e-6),
        "the repair loop's wall cost belongs to the arm that used it",
    ),
    # -- failure_category ----------------------------------------------------
    Mutation(
        "failure_category", "a clean, preserved encoding is ok", "pass",
        _trial(), _T_FACETED, _A, _eq("failure_category", "ok"), "",
    ),
    Mutation(
        "failure_category", "unbalanced parentheses classify as syntax", "fail",
        _trial(content=_reply(_BROKEN_SYNTAX)), _T_FACETED, _A,
        _eq("failure_category", "syntax_failure"), "HML-P231",
    ),
    Mutation(
        "failure_category", "a refinement violation classifies as type", "fail",
        _trial(content=_reply(_BROKEN_TYPE)), _T_FACETED, _A,
        _eq("failure_category", "type_failure"), "HML-T402",
    ),
    Mutation(
        "failure_category", "an unresolved name classifies as semantic", "fail",
        _trial(content=_reply(_UNRESOLVED)), _T_FACETED, _A,
        _eq("failure_category", "semantic_failure"), "HML-N301",
    ),
    Mutation(
        "failure_category", "prose with no fenced block", "fail",
        _trial(content="The answer is forty.\n\n<ANSWER>40.0</ANSWER>"),
        _T_FACETED, _A, _eq("failure_category", "no_encoding_block"),
        "a formatting failure is not a mathematical failure and is counted apart",
    ),
    Mutation(
        "failure_category", "parses cleanly but mistranslates", "fail",
        _trial(content=_reply(_MISTRANSLATED)), _T_FACETED, _A,
        _eq("failure_category", "semantic_mistranslation"),
        "parser acceptance is not evidence of preservation",
    ),
    Mutation(
        "failure_category", "no front end is NOT a model failure", "fail",
        _trial(condition=C_SEXPR, content=_reply("(module X)", tag="sexpr")),
        _T_FACETED, None, _eq("failure_category", "front_end_unavailable"),
        "scoring an unbuilt parser as 0% parse would invent a measurement",
    ),
    Mutation(
        "failure_category", "a transport failure is NOT a model failure", "fail",
        _trial(content="", error="URLError: connection refused"), _T_FACETED, _A,
        _eq("failure_category", "transport_failure"),
        "may be retried; every attempt is preserved by the harness",
    ),
    Mutation(
        "failure_category", "the control arm emits no encoding by design", "fail",
        _trial(condition=SE_CONTROL,
               content="Objects and types: ...\n\n<ANSWER>40.0</ANSWER>"),
        _T_FACETED, None, _eq("failure_category", "control_arm_no_encoding"),
        "giving the control a parse rate of 0 would make it look catastrophic at the "
        "one thing it is not doing",
    ),
)


def covered_facets() -> set[str]:
    return {m.facet for m in MUTATIONS}


def run_mutation(m: Mutation) -> tuple[bool, str]:
    """Score one mutation and check it. Used by the tests and by ``build --self-check``."""
    task = m.task
    if m.trial.task_id == "synthetic_no_facets":
        # A task whose answer key populates no comparable facet. Built by replacing the
        # facet set, so the prose and the encoding are otherwise identical -- the only
        # difference is the thing under test.
        task = GateTask(
            cso=m.task.cso, track=m.task.track, features=m.task.features,
            scored_facets=frozenset(), reference_syntax=m.task.reference_syntax,
        )
    trial = replace(m.trial, task_id=task.id)
    scored = score_trial(trial, task, m.adapter)
    ok, detail = m.expect(scored)
    return ok, f"[{m.facet}/{m.kind}] {m.name}: {detail}"


assert covered_facets() == set(FACETS), (
    "every scorer facet needs at least one mutation; missing: "
    f"{sorted(set(FACETS) - covered_facets())}"
)
