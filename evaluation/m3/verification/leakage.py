"""Diagnostic leakage controls: the four conditions, and the guard that precedes them.

The problem this solves
-----------------------
"Repair succeeds more often with compiler feedback" has two very different causes, and
one number cannot tell them apart:

* the diagnostic **helped the model reason** — it named the wrong step, and the model
  fixed it; or
* the diagnostic **contained the answer** — the model copied it out.

The second makes H3 a tautology: feedback improves the verified rate because feedback
*is* the verified program. So the comparison is run under four conditions::

    A  broken trace only                       -- the floor
    B  diagnostic only, no trace               -- the leak probe
    C  broken trace + the correct diagnostic   -- the treatment
    D  broken trace + a mismatched diagnostic  -- the well-formed-but-wrong control

The diagnostic is **useful** when ``repair(C) > repair(A)`` *and* ``repair(C) >
repair(D)``: better than nothing, and better than any well-formed text in the same slot.
It **leaks** when condition **B alone** reconstructs the target above
:data:`LEAK_THRESHOLD` — because a diagnostic that lets you rebuild the program without
ever seeing the broken one is carrying the program.

Condition D is a *mismatched* diagnostic by default — a real diagnostic from a different
task — rather than a word-scramble, because a scramble is trivially recognisable as
noise and would make D an easy control to beat. ``scramble`` remains available for the
weaker variant, and which one was used is recorded in the report.

The guard runs first
--------------------
:func:`assert_no_answer_leak` is not part of the measurement; it is a precondition on
the diagnostics themselves. A diagnostic that embeds a compilable program equal to the
target, or that quotes a long contiguous run of the target absent from the broken trace,
is rejected before any condition is run. Measuring leakage after allowing the answer
through would only tell you how well the model can copy.

Offline
-------
Nothing here makes a model call. An arm is any callable ``(Condition, Payload) -> str``;
the fixtures supply scripted responses so the harness is testable with no server, and a
live run is the Lead's decision, not this module's.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from hamiltonian_lang import compile_source
from hamiltonian_lang.verification.obligations import GlobalVerdict, verify_source

__all__ = [
    "LEAKAGE_PROTOCOL_VERSION",
    "LEAK_THRESHOLD",
    "Condition",
    "LeakFinding",
    "Payload",
    "ConditionResult",
    "LeakageReport",
    "assert_no_answer_leak",
    "find_answer_leak",
    "build_payload",
    "mismatched_diagnostic",
    "scrambled_diagnostic",
    "run_conditions",
]

LEAKAGE_PROTOCOL_VERSION = "hml-h3-leakage-1.0.0"

#: Condition B is allowed to succeed occasionally — a trivially short target can be
#: guessed. Above this share, the diagnostic is carrying the answer and the H3 number
#: computed from it means nothing.
LEAK_THRESHOLD = 0.20

#: A run of this many consecutive tokens copied from the target, absent from the broken
#: trace, is treated as the answer appearing in the diagnostic.
#:
#: Four is short enough to catch a single corrected statement — ``require spend >= 50``
#: is exactly four HML tokens — and safe from false positives because a run that already
#: appears in the broken trace is exempt. The model has already seen its own program;
#: repeating part of it back tells it nothing.
MAX_COPIED_RUN = 4


class Condition(StrEnum):
    A_TRACE_ONLY = "A"
    B_DIAGNOSTIC_ONLY = "B"
    C_TRACE_PLUS_DIAGNOSTIC = "C"
    D_TRACE_PLUS_SHUFFLED = "D"


@dataclass(frozen=True)
class LeakFinding:
    """One reason a diagnostic must not be used as it stands."""

    kind: str
    detail: str
    excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "detail": self.detail, "excerpt": self.excerpt}


@dataclass(frozen=True)
class Payload:
    """Exactly what one arm is shown under one condition."""

    task_id: str
    condition: Condition
    broken_trace: str
    diagnostic: str

    def render(self) -> str:
        parts: list[str] = []
        if self.broken_trace:
            parts.append(f"# candidate program\n{self.broken_trace}")
        if self.diagnostic:
            parts.append(f"# verifier report\n{self.diagnostic}")
        return "\n\n".join(parts)

    def digest(self) -> str:
        return hashlib.sha256(self.render().encode()).hexdigest()[:16]


@dataclass(frozen=True)
class ConditionResult:
    condition: Condition
    attempted: int
    repaired: int
    per_task: Mapping[str, bool] = field(default_factory=dict)

    @property
    def rate(self) -> float:
        return self.repaired / self.attempted if self.attempted else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition": str(self.condition),
            "attempted": self.attempted,
            "repaired": self.repaired,
            "rate": round(self.rate, 6),
            "per_task": dict(self.per_task),
        }


@dataclass(frozen=True)
class LeakageReport:
    """The four rates and the two judgements that follow from them."""

    protocol_version: str
    results: Mapping[Condition, ConditionResult]
    shuffle_mode: str
    guard_findings: Mapping[str, tuple[LeakFinding, ...]] = field(default_factory=dict)

    def rate(self, condition: Condition) -> float:
        result = self.results.get(condition)
        return result.rate if result else 0.0

    @property
    def useful(self) -> bool:
        """The diagnostic beats both the floor and a well-formed wrong diagnostic."""
        return (
            self.rate(Condition.C_TRACE_PLUS_DIAGNOSTIC) > self.rate(Condition.A_TRACE_ONLY)
            and self.rate(Condition.C_TRACE_PLUS_DIAGNOSTIC)
            > self.rate(Condition.D_TRACE_PLUS_SHUFFLED)
        )

    @property
    def leaks(self) -> bool:
        """Condition B alone reconstructs the target too often."""
        return self.rate(Condition.B_DIAGNOSTIC_ONLY) > LEAK_THRESHOLD

    @property
    def admissible(self) -> bool:
        """H3 may be computed from this diagnostic channel only when both hold."""
        return self.useful and not self.leaks and not self.guard_findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "shuffle_mode": self.shuffle_mode,
            "leak_threshold": LEAK_THRESHOLD,
            "rates": {str(c): round(self.rate(c), 6) for c in Condition},
            "results": [self.results[c].to_dict() for c in Condition if c in self.results],
            "useful": self.useful,
            "leaks": self.leaks,
            "admissible": self.admissible,
            "guard_findings": {
                k: [f.to_dict() for f in v] for k, v in self.guard_findings.items()
            },
        }

    def render(self) -> str:
        lines = [f"diagnostic leakage control ({self.protocol_version})"]
        for condition in Condition:
            result = self.results.get(condition)
            if result:
                lines.append(
                    f"  {condition}  repair {result.repaired}/{result.attempted} "
                    f"= {result.rate:.1%}"
                )
        lines.append(f"  useful      : {self.useful}   (C > A and C > D)")
        lines.append(f"  leaks       : {self.leaks}   (B > {LEAK_THRESHOLD:.0%})")
        lines.append(f"  admissible  : {self.admissible}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------

#: HML's multi-character operators are lexed whole, so ``>=`` counts as one token and a
#: copied statement is measured the way a reader would count it.
_TOKEN = re.compile(
    r"<=>|:=|->|=>|<=|>=|!=|::|\*\*"
    r"|[A-Za-z_][A-Za-z0-9_]*"
    r"|[0-9]+(?:\.[0-9]+)?"
    r"|[^\sA-Za-z0-9_]"
)


def _tokens(text: str) -> list[str]:
    stripped = "\n".join(
        line.split("#", 1)[0] for line in text.splitlines()
    )
    return _TOKEN.findall(stripped)


def _candidate_programs(diagnostic: str) -> list[str]:
    """Every block of the diagnostic that might be a program.

    Both the whole text and each ``module``-headed run are tried, because a diagnostic
    that embeds a replacement program usually does so inline rather than fenced.
    """
    out = [diagnostic]
    lines = diagnostic.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip().startswith("module ")]
    for start in starts:
        out.append("\n".join(lines[start:]))
    return out


def find_answer_leak(
    diagnostic: str, target_source: str, broken_trace: str = ""
) -> tuple[LeakFinding, ...]:
    """Reasons this diagnostic would hand the model the answer.

    Three independent checks, because each catches a different way of leaking:

    1. **the diagnostic contains a program equal to the target** — compiled and compared
       by alpha-invariant content hash, so a renamed copy is still caught;
    2. **the diagnostic contains a compilable program at all** — a full replacement
       program is out of bounds even when it is not the reference one, since the whole
       point is that the model must produce the program;
    3. **the diagnostic quotes a long contiguous run of the target** that is absent from
       the broken trace — the "here is the corrected line" leak, which neither of the
       first two catches.
    """
    findings: list[LeakFinding] = []
    reference = compile_source(target_source)
    reference_hash = reference.hash() if reference.ok() else None

    for candidate in _candidate_programs(diagnostic):
        if "module " not in candidate:
            continue
        compiled = compile_source(candidate)
        if not compiled.ok():
            continue
        if reference_hash is not None and compiled.hash() == reference_hash:
            findings.append(
                LeakFinding(
                    "target_program_embedded",
                    "the diagnostic contains a program whose canonical content hash "
                    "equals the target's; the answer is in the feedback",
                    candidate.strip()[:200],
                )
            )
        else:
            findings.append(
                LeakFinding(
                    "complete_program_embedded",
                    "the diagnostic contains a complete compilable program; a diagnostic "
                    "may describe a defect, never supply the replacement",
                    candidate.strip()[:200],
                )
            )
        break

    target_tokens = _tokens(target_source)
    diagnostic_tokens = _tokens(diagnostic)
    trace_runs = _runs(_tokens(broken_trace), MAX_COPIED_RUN)
    for run in _runs(target_tokens, MAX_COPIED_RUN):
        if run in trace_runs:
            continue  # already visible in what the model was shown
        if _contains_run(diagnostic_tokens, run):
            findings.append(
                LeakFinding(
                    "copied_run",
                    f"the diagnostic quotes {MAX_COPIED_RUN} consecutive tokens of the "
                    f"target that do not appear in the broken trace",
                    " ".join(run),
                )
            )
            break
    return tuple(findings)


def _runs(tokens: Sequence[str], length: int) -> set[tuple[str, ...]]:
    return {
        tuple(tokens[i : i + length]) for i in range(max(0, len(tokens) - length + 1))
    }


def _contains_run(tokens: Sequence[str], run: tuple[str, ...]) -> bool:
    n = len(run)
    return any(tuple(tokens[i : i + n]) == run for i in range(max(0, len(tokens) - n + 1)))


def assert_no_answer_leak(
    diagnostic: str, target_source: str, broken_trace: str = ""
) -> None:
    """Raise unless the diagnostic is safe to use as feedback."""
    findings = find_answer_leak(diagnostic, target_source, broken_trace)
    if findings:
        detail = "; ".join(f"{f.kind}: {f.detail}" for f in findings)
        raise ValueError(
            f"this diagnostic must not be used as H3 feedback — {detail}. A diagnostic "
            f"that carries the answer converts H3 from a measurement into a tautology"
        )


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------


def mismatched_diagnostic(task_id: str, diagnostics: Mapping[str, str]) -> str:
    """A real diagnostic belonging to a **different** task.

    Deterministic: the offset is derived from the task id, so condition D is
    reproducible without a random seed. A well-formed but wrong diagnostic is the right
    control — it holds the *shape* of the feedback constant and varies only whether it
    is about this problem.
    """
    keys = sorted(k for k in diagnostics if k != task_id)
    if not keys:
        return ""
    offset = int(hashlib.sha256(task_id.encode()).hexdigest(), 16) % len(keys)
    return diagnostics[keys[offset]]


def scrambled_diagnostic(task_id: str, diagnostic: str) -> str:
    """The weaker control: the same tokens, deterministically reordered."""
    tokens = diagnostic.split()
    if len(tokens) < 2:
        return diagnostic
    seed = int(hashlib.sha256(task_id.encode()).hexdigest(), 16)
    order = sorted(range(len(tokens)), key=lambda i: (seed >> (i % 64)) & 0xFF)
    return " ".join(tokens[i] for i in order)


def build_payload(
    task_id: str,
    condition: Condition,
    broken_trace: str,
    diagnostic: str,
    diagnostics: Mapping[str, str],
    *,
    shuffle_mode: str = "mismatched",
) -> Payload:
    """Assemble what one arm sees. The only thing that varies across A-D is this."""
    if condition is Condition.A_TRACE_ONLY:
        return Payload(task_id, condition, broken_trace, "")
    if condition is Condition.B_DIAGNOSTIC_ONLY:
        return Payload(task_id, condition, "", diagnostic)
    if condition is Condition.C_TRACE_PLUS_DIAGNOSTIC:
        return Payload(task_id, condition, broken_trace, diagnostic)
    shuffled = (
        mismatched_diagnostic(task_id, diagnostics)
        if shuffle_mode == "mismatched"
        else scrambled_diagnostic(task_id, diagnostic)
    )
    return Payload(task_id, condition, broken_trace, shuffled)


#: An arm: given what it was shown, return a candidate HML program. Offline runs pass a
#: lookup into scripted fixtures; a live run would pass a model client, and that is the
#: Lead's decision to authorise.
Responder = Callable[[Payload], str]


def run_conditions(
    cases: Sequence[tuple[str, str, str, str]],
    responder: Responder,
    *,
    shuffle_mode: str = "mismatched",
    enforce_guard: bool = True,
) -> LeakageReport:
    """Run A, B, C and D over ``(task_id, broken_trace, diagnostic, target)`` cases.

    ``repaired`` means the response reaches the global ``VERIFIED`` verdict — the same
    endpoint H3 reports, not a looser proxy. When ``enforce_guard`` is set, a case whose
    diagnostic would leak the answer is recorded in ``guard_findings`` and **excluded**
    from every condition, so a leaking diagnostic cannot contribute to the very number
    that is supposed to detect it.
    """
    diagnostics = {task_id: diagnostic for task_id, _t, diagnostic, _g in cases}
    guard_findings: dict[str, tuple[LeakFinding, ...]] = {}
    admissible: list[tuple[str, str, str, str]] = []
    for task_id, trace, diagnostic, target in cases:
        findings = find_answer_leak(diagnostic, target, trace) if enforce_guard else ()
        if findings:
            guard_findings[task_id] = findings
            continue
        admissible.append((task_id, trace, diagnostic, target))

    results: dict[Condition, ConditionResult] = {}
    for condition in Condition:
        per_task: dict[str, bool] = {}
        for task_id, trace, diagnostic, _target in admissible:
            payload = build_payload(
                task_id, condition, trace, diagnostic, diagnostics, shuffle_mode=shuffle_mode
            )
            response = responder(payload)
            per_task[task_id] = (
                bool(response.strip())
                and verify_source(response, f"{task_id}:{condition}").verdict
                is GlobalVerdict.VERIFIED
            )
        results[condition] = ConditionResult(
            condition=condition,
            attempted=len(admissible),
            repaired=sum(1 for v in per_task.values() if v),
            per_task=per_task,
        )
    return LeakageReport(
        protocol_version=LEAKAGE_PROTOCOL_VERSION,
        results=results,
        shuffle_mode=shuffle_mode,
        guard_findings=guard_findings,
    )
