"""Which problems H3 may be run on, and — just as importantly — which it may not.

The rule
--------
A task is admitted only when **all** of the following hold of its *expected solution*:

1. it compiles;
2. every obligation it raises falls inside an implemented class — no obligation is
   ``UNSUPPORTED`` and none lands in ``out_of_subset``;
3. it reaches the global ``VERIFIED`` verdict, so the endpoint is actually attainable;
4. at least one of its discharges is **not** definitional, so the task cannot be passed
   for free;
5. both arms receive the identical problem text.

Why the exclusions are published rather than applied quietly
------------------------------------------------------------
A filter that silently keeps only the tasks the verifier happens to handle makes H3
unfalsifiable: whatever the model does, the retained subset is the one where the
machinery works, and the result generalises to nothing. So :class:`SubsetReport` carries
the admitted **and** the excluded tasks, the reason for each exclusion, and the counts
per reason — and :data:`EXCLUDED_DOMAINS` names the whole domains that are out of scope
before any task is looked at.

Arm parity
----------
:func:`paired_roster` refuses to build a roster unless the no-feedback and feedback arms
are handed the same task ids and the same problem text. An H3 comparison across
different problem sets is not a comparison.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from hamiltonian_lang.verification.obligations import (
    GlobalVerdict,
    ObligationClass,
    ObligationStatus,
    VerificationOutcome,
    verify_source,
)

__all__ = [
    "SUBSET_POLICY_VERSION",
    "EXCLUDED_DOMAINS",
    "Task",
    "TaskDecision",
    "SubsetReport",
    "admit",
    "build_subset",
    "paired_roster",
    "load_fixture_tasks",
]

SUBSET_POLICY_VERSION = "hml-h3-task-subset-1.0.0"

#: Whole areas of mathematics the implemented subset cannot check, listed before any
#: task is examined so that "H3 was run on what happened to work" is not a possible
#: reading of the result. Each entry is (domain, why it is out, what would let it in).
EXCLUDED_DOMAINS: tuple[tuple[str, str, str], ...] = (
    (
        "quantification over infinite domains",
        "a universal claim over the reals cannot be established by exhaustion or by a "
        "finite grid, and no decision procedure for real arithmetic is implemented",
        "a real-closed-field decision procedure, or a proof assistant with a working "
        "library — neither is available on this machine",
    ),
    (
        "probability and distributions",
        "no checker can express a claim about a Distribution or a RandomVariable; the "
        "type system keeps them apart from values and nothing here bridges that",
        "a measure-theoretic backend with a checkable semantics",
    ),
    (
        "integration, limits and differentiation",
        "v0 has no surface syntax for them, so no obligation of this kind can even be "
        "stated",
        "the corresponding language constructs, with their own eight-part definition",
    ),
    (
        "linear algebra over indexed terms",
        "the evaluator refuses indexing and the matrix product; a claim about w[i] is "
        "outside the subset",
        "an indexed-term evaluator with bounds obligations of its own",
    ),
    (
        "dimensioned numeric comparison",
        "the numeric value of a Quantity[Length] is unit-relative, so comparing it "
        "against a bare literal is not a well-posed question",
        "a unit system in the surface language, not only a dimension system",
    ),
    (
        "concept transforms and abstract properties",
        "an invariant that calls a transform quantifies over every instance of the "
        "concept, and no instance is available to check",
        "instance-level concept checking, which v0 does not have",
    ),
)


@dataclass(frozen=True)
class Task:
    """One H3 problem. ``expected_solution`` is the reference HML."""

    task_id: str
    prompt: str
    expected_solution: str
    domain: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def digest(self) -> str:
        return hashlib.sha256(
            f"{self.task_id}\x00{self.prompt}\x00{self.expected_solution}".encode()
        ).hexdigest()


@dataclass(frozen=True)
class TaskDecision:
    """Admitted or not, and why. The 'why' is mandatory in both directions."""

    task_id: str
    admitted: bool
    reasons: tuple[str, ...]
    verdict: str
    substantive: bool
    classes: tuple[str, ...]
    unsupported_statements: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "admitted": self.admitted,
            "reasons": list(self.reasons),
            "verdict": self.verdict,
            "substantive": self.substantive,
            "classes": list(self.classes),
            "unsupported_statements": list(self.unsupported_statements),
        }


@dataclass(frozen=True)
class SubsetReport:
    """The admitted set, the excluded set, and the arithmetic connecting them."""

    policy_version: str
    decisions: tuple[TaskDecision, ...]

    @property
    def admitted(self) -> tuple[TaskDecision, ...]:
        return tuple(d for d in self.decisions if d.admitted)

    @property
    def excluded(self) -> tuple[TaskDecision, ...]:
        return tuple(d for d in self.decisions if not d.admitted)

    def exclusion_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for decision in self.excluded:
            for reason in decision.reasons:
                out[reason] = out.get(reason, 0) + 1
        return out

    def coverage(self) -> float:
        if not self.decisions:
            return 0.0
        return len(self.admitted) / len(self.decisions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "total": len(self.decisions),
            "admitted": len(self.admitted),
            "excluded": len(self.excluded),
            "coverage": round(self.coverage(), 6),
            "exclusion_counts": self.exclusion_counts(),
            "excluded_domains": [
                {"domain": d, "why": w, "what_would_admit_it": a}
                for d, w, a in EXCLUDED_DOMAINS
            ],
            "decisions": [d.to_dict() for d in self.decisions],
        }

    def render(self) -> str:
        lines = [
            f"H3 supported task subset ({self.policy_version})",
            f"  admitted {len(self.admitted)} / {len(self.decisions)} "
            f"({self.coverage():.1%})",
        ]
        for reason, count in sorted(self.exclusion_counts().items(), key=lambda kv: -kv[1]):
            lines.append(f"  excluded {count:3d}  {reason}")
        return "\n".join(lines)


def admit(task: Task, *, require_substantive: bool = True) -> TaskDecision:
    """Decide one task against the five criteria."""
    outcome: VerificationOutcome = verify_source(task.expected_solution, task.task_id)
    reasons: list[str] = []

    if outcome.verdict is GlobalVerdict.INVALID:
        reasons.append("the expected solution does not compile")
    unsupported = tuple(
        r.statement
        for r in outcome.records
        if r.status is ObligationStatus.UNSUPPORTED
        or r.obligation_class is ObligationClass.OUT_OF_SUBSET
    )
    if unsupported:
        reasons.append(
            f"{len(unsupported)} obligation(s) of the expected solution are outside the "
            f"implemented subset"
        )
    inconclusive = sum(
        1 for r in outcome.records if r.status is ObligationStatus.INCONCLUSIVE
    )
    if inconclusive:
        reasons.append(
            f"{inconclusive} obligation(s) of the expected solution were attempted and "
            f"not decided"
        )
    if outcome.verdict is GlobalVerdict.DISPROVED:
        reasons.append("the expected solution is refuted by the engine, so it is not a key")
    if outcome.semantic_loss:
        reasons.append("a semantic-preserving view of the expected solution reported loss")
    if outcome.verdict is not GlobalVerdict.VERIFIED and not reasons:
        reasons.append(f"the expected solution reaches {outcome.verdict}, not VERIFIED")
    if require_substantive and not outcome.substantive:
        reasons.append(
            "every discharge in the expected solution is definitional, so the task would "
            "be passed without checking anything"
        )

    admitted = not reasons
    if admitted:
        reasons.append(
            "the expected solution is VERIFIED, substantively, entirely inside the "
            "implemented subset"
        )
    return TaskDecision(
        task_id=task.task_id,
        admitted=admitted,
        reasons=tuple(reasons),
        verdict=str(outcome.verdict),
        substantive=outcome.substantive,
        classes=tuple(sorted({str(r.obligation_class) for r in outcome.records})),
        unsupported_statements=unsupported,
    )


def build_subset(
    tasks: Sequence[Task], *, require_substantive: bool = True
) -> SubsetReport:
    """Decide a whole task set, preserving the excluded tasks and their reasons."""
    return SubsetReport(
        policy_version=SUBSET_POLICY_VERSION,
        decisions=tuple(admit(t, require_substantive=require_substantive) for t in tasks),
    )


def paired_roster(
    tasks: Sequence[Task], report: SubsetReport
) -> tuple[tuple[Task, ...], dict[str, str]]:
    """The admitted tasks plus a digest per task, for asserting arm parity.

    The digest covers the prompt and the expected solution. Two arms that report the
    same digests received the same problems; two that do not are not comparable, and
    :func:`assert_parity` refuses them.
    """
    admitted_ids = {d.task_id for d in report.admitted}
    roster = tuple(t for t in tasks if t.task_id in admitted_ids)
    return roster, {t.task_id: t.digest() for t in roster}


def assert_parity(
    no_feedback: Mapping[str, str], feedback: Mapping[str, str]
) -> None:
    """Raise unless both arms were handed exactly the same problems.

    H3 holds the input representation, the reasoning representation, the model and the
    task set fixed and varies only the feedback. A mismatch here means the comparison
    measures something else, so it is an error rather than a warning.
    """
    if set(no_feedback) != set(feedback):
        missing = sorted(set(no_feedback) ^ set(feedback))
        raise ValueError(
            f"the two arms did not receive the same task ids; differing: {missing}"
        )
    drifted = sorted(k for k in no_feedback if no_feedback[k] != feedback[k])
    if drifted:
        raise ValueError(
            f"the two arms received different problem text for: {drifted}. H3 varies "
            f"feedback only; a differing problem makes the arms incomparable"
        )


def load_fixture_tasks(directory: pathlib.Path | None = None) -> list[Task]:
    """Build a task list from the fixture manifest.

    Every fixture becomes a candidate task, including the ones that must be excluded —
    a filter is only worth having if it is exercised on things it should reject.
    """
    from . import FIXTURES

    root = directory or FIXTURES
    manifest = json.loads((root / "MANIFEST.json").read_text())
    tasks: list[Task] = []
    for entry in manifest["fixtures"]:
        path = root / entry["file"]
        tasks.append(
            Task(
                task_id=entry["file"].removesuffix(".hml"),
                prompt=f"Encode the model described in {entry['file']}.",
                expected_solution=path.read_text(),
                domain=entry["file"].split("_", 1)[0],
                metadata={
                    "expected_verdict": entry["expected_verdict"],
                    "exercises": entry.get("exercises", []),
                },
            )
        )
    return tasks
