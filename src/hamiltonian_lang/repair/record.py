"""Repair records, the chain driver, and the hypothesis discipline they carry.

The distinction this module exists to protect
---------------------------------------------
Compiler-assisted **syntax** repair during ACQ0 is ``ACQ0_REPAIR``. It is **not H3**.
Fixing a malformed encoding and fixing a wrong argument are different acts with different
success conditions, and conflating them would let "the model learned to write the syntax
with compiler help" be read, a year later, as "verifier feedback improved mathematical
reasoning". H3 requires a *mathematical reasoning endpoint*.

The register (``docs/evaluation/HYPOTHESIS_REGISTER.md``) states this as a rule. Here it
is a type: :class:`RepairEndpoint` is recorded on every record, and
:class:`RepairRecord` refuses the combinations that would blur the two —

* ``H3`` with a syntactic endpoint (a syntax fix relabelled as reasoning repair)
* ``ACQ0`` with a mathematical endpoint (a reasoning result relabelled as acquisition)
* ``H1`` or ``H2`` with any repair turn at all (neither hypothesis involves a repair loop)

Every record carries exactly one ``state.Hypothesis``, one :class:`RepairBudget` and one
:class:`FeedbackArm`, and :func:`summarise` refuses to aggregate across the first two.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from ..context_broker import (
    ContextStatus,
    DiagnosticContextBroker,
    ErrorClass,
    RetrievedContext,
)
from ..improvement.diagnostics import StructuredDiagnostic, adapt
from ..improvement.state import (
    REPAIR_MECHANISM,
    Hypothesis,
    require_single_hypothesis,
)
from .arms import FeedbackArm, build_payload
from .budget import (
    RepairBudget,
    RepairBudgetExceeded,
    assert_official,
    require_single_budget,
)
from .learner import RepairLearner
from .plan import NoPlan, RepairPlan
from .teacher import DeterministicRepairTeacher, RepairTeacher

__all__ = [
    "RepairEndpoint",
    "HypothesisEndpointError",
    "LiveComponentRefused",
    "CheckOutcome",
    "Checker",
    "default_checker",
    "RepairTurnRecord",
    "RepairRecord",
    "run_repair_chain",
    "summarise",
]


class RepairEndpoint(StrEnum):
    """What the repair is being scored on. The axis that separates ACQ0 from H3."""

    #: Did the encoding parse, resolve and type-check? A syntax-acquisition endpoint.
    SYNTACTIC_ENCODING = "syntactic_encoding"
    #: Was the mathematical answer correct under a verifier? A reasoning endpoint.
    MATHEMATICAL_ANSWER = "mathematical_answer"


class HypothesisEndpointError(ValueError):
    """A hypothesis was paired with an endpoint that cannot bear on it."""


class LiveComponentRefused(RuntimeError):
    """A live Teacher or Learner was supplied to a chain that did not authorise one."""


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckOutcome:
    """The verdict on one candidate. ``ok`` means every stage accepted it."""

    ok: bool
    diagnostics: tuple[StructuredDiagnostic, ...] = ()

    @property
    def first_error(self) -> StructuredDiagnostic | None:
        return self.diagnostics[0] if self.diagnostics else None


@runtime_checkable
class Checker(Protocol):
    def __call__(self, text: str) -> CheckOutcome: ...


def default_checker(text: str) -> CheckOutcome:
    """Compile with the real compiler and adapt its errors. Offline; no model involved."""
    from .. import compile_source

    result = compile_source(text)
    errors = tuple(adapt(d) for d in result.diagnostics.errors)
    return CheckOutcome(ok=result.ok(), diagnostics=errors)


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepairTurnRecord:
    """One repair turn. Turn 1 is the first repair; the initial attempt is turn 0."""

    index: int
    arm: FeedbackArm
    diagnostic_code: str
    error_class: ErrorClass | None
    context_status: ContextStatus
    plan: RepairPlan | None
    no_plan_reason: str
    output: str
    resolved: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "arm": str(self.arm),
            "diagnostic_code": self.diagnostic_code,
            "error_class": None if self.error_class is None else str(self.error_class),
            "context_status": str(self.context_status),
            "plan": None if self.plan is None else self.plan.to_dict(),
            "no_plan_reason": self.no_plan_reason,
            "output": self.output,
            "resolved": self.resolved,
        }


@dataclass(frozen=True)
class RepairRecord:
    """Everything one task's repair produced, under exactly one hypothesis and budget."""

    task_id: str
    hypothesis: Hypothesis
    endpoint: RepairEndpoint
    budget: RepairBudget
    arm: FeedbackArm
    initial_output: str
    initial_resolved: bool
    initial_diagnostic_code: str = ""
    turns: tuple[RepairTurnRecord, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, Hypothesis):
            raise TypeError(
                "RepairRecord.hypothesis must be a Hypothesis member, not "
                f"{type(self.hypothesis).__name__}. Free text cannot be separated later."
            )
        if not isinstance(self.endpoint, RepairEndpoint):
            raise TypeError("RepairRecord.endpoint must be a RepairEndpoint member")
        if not isinstance(self.budget, RepairBudget):
            raise TypeError("RepairRecord.budget must be a RepairBudget member")
        if not isinstance(self.arm, FeedbackArm):
            raise TypeError("RepairRecord.arm must be a FeedbackArm member")

        h, e = self.hypothesis, self.endpoint
        if h is Hypothesis.H3 and e is not RepairEndpoint.MATHEMATICAL_ANSWER:
            raise HypothesisEndpointError(
                "H3 requires a mathematical reasoning endpoint. A repair scored on "
                f"{e.value} is ACQ0_REPAIR — compiler-assisted syntax repair — and "
                "recording it as H3 would let 'the model learned to write the syntax' be "
                "read later as 'verifier feedback improved mathematical reasoning'. See "
                "docs/evaluation/HYPOTHESIS_REGISTER.md rule 2."
            )
        if h is Hypothesis.ACQ0 and e is not RepairEndpoint.SYNTACTIC_ENCODING:
            raise HypothesisEndpointError(
                "ACQ0 asks whether the model can express a frozen object in the candidate "
                f"surface. A repair scored on {e.value} is not that question; if the "
                "endpoint is a mathematical answer the hypothesis is H3."
            )
        if h in (Hypothesis.H1, Hypothesis.H2) and self.turns:
            raise HypothesisEndpointError(
                f"{h.name} does not involve a repair loop: it compares representations at "
                "a single attempt. A repair turn recorded under it would make the "
                "comparison a comparison of repair, not of representation."
            )
        if len(self.turns) > self.budget.limit:
            raise RepairBudgetExceeded(
                f"{self.task_id!r}: {len(self.turns)} repair turns recorded but the "
                f"budget {self.budget.value} permits {self.budget.limit}"
            )
        assert_official(
            self.budget, hypothesis=self.hypothesis, context=f"record {self.task_id!r}"
        )

    # -- derived -----------------------------------------------------------------

    @property
    def mechanism(self) -> str:
        """The name under which this repair is recorded. ``ACQ0_REPAIR`` is not H3."""
        try:
            return REPAIR_MECHANISM[self.hypothesis]
        except KeyError:
            return f"NO_REPAIR_MECHANISM({self.hypothesis.name})"

    @property
    def repaired(self) -> bool:
        """Resolved after at least one repair. Distinct from :attr:`initial_resolved`."""
        return bool(self.turns) and self.turns[-1].resolved

    @property
    def resolved(self) -> bool:
        return self.initial_resolved or self.repaired

    @property
    def repair_turns_used(self) -> int:
        return len(self.turns)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "hypothesis": self.hypothesis.value,
            "hypothesis_name": self.hypothesis.name,
            "hypothesis_claim": self.hypothesis.claim,
            "hypothesis_excluded_claim": self.hypothesis.excluded_claim,
            "mechanism": self.mechanism,
            "endpoint": str(self.endpoint),
            "budget": self.budget.value,
            "budget_limit": self.budget.limit,
            "arm": str(self.arm),
            "initial_output": self.initial_output,
            "initial_resolved": self.initial_resolved,
            "initial_diagnostic_code": self.initial_diagnostic_code,
            "repair_turns_used": self.repair_turns_used,
            "first_attempt_resolved": self.initial_resolved,
            "repaired": self.repaired,
            "resolved": self.resolved,
            "turns": [t.to_dict() for t in self.turns],
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# The chain
# ---------------------------------------------------------------------------


def run_repair_chain(
    *,
    task_id: str,
    hypothesis: Hypothesis,
    endpoint: RepairEndpoint,
    budget: RepairBudget,
    arm: FeedbackArm,
    initial_output: str,
    learner: RepairLearner,
    teacher: RepairTeacher | None = None,
    broker: DiagnosticContextBroker | None = None,
    checker: Callable[[str], CheckOutcome] = default_checker,
    verified_prefix: str = "",
    allow_live: bool = False,
    notes: Sequence[str] = (),
) -> RepairRecord:
    """Drive one task through its repair budget under one arm, and record what happened.

    The loop stops on the first turn that resolves, or when the budget is spent. Every
    turn is recorded whether or not it helped: a repair that made things worse is
    evidence, and a record that keeps only the successful turns reports a rate that no
    longer means anything.

    ``allow_live`` must be set before a Teacher or Learner that contacts a model may run.
    The default refuses, so an offline suite cannot start making network calls because a
    component was swapped somewhere upstream.
    """
    if not allow_live:
        for role, component in (("teacher", teacher), ("learner", learner)):
            if component is not None and getattr(component, "live", False):
                raise LiveComponentRefused(
                    f"{role} {getattr(component, 'name', '?')!r} is live but the chain "
                    "was not started with allow_live=True"
                )

    if arm is FeedbackArm.CHAIN_OF_REPAIR and teacher is None:
        teacher = DeterministicRepairTeacher(
            broker=broker if broker is not None else DiagnosticContextBroker()
        )

    forbid_novel_numerals = endpoint is RepairEndpoint.MATHEMATICAL_ANSWER

    outcome = checker(initial_output)
    first = outcome.first_error
    # Captured before the loop. Re-checking the initial output afterwards would call the
    # checker twice and, with a stateful checker, could disagree with itself.
    initial_resolved = outcome.ok
    record_turns: list[RepairTurnRecord] = []
    current = initial_output

    limit = budget.limit
    while not outcome.ok and len(record_turns) < limit:
        diagnostic = outcome.first_error
        if diagnostic is None:  # pragma: no cover - ok() is false only with an error
            break

        context: RetrievedContext | None = None
        plan: RepairPlan | None = None
        no_plan_reason = ""
        context_status = ContextStatus.NO_RELEVANT_CONTEXT
        error_class: ErrorClass | None = None

        if arm is FeedbackArm.CHAIN_OF_REPAIR and teacher is not None:
            active_broker = getattr(teacher, "broker", None) or broker
            if active_broker is None:
                active_broker = DiagnosticContextBroker()
            from ..context_broker import ContextQuery

            context = active_broker.retrieve(
                ContextQuery(diagnostic=diagnostic, source=current)
            )
            context_status = context.status
            error_class = context.error_class
            taught = teacher.teach(
                broken_output=current,
                diagnostic=diagnostic,
                context=context,
                verified_prefix=verified_prefix,
                forbid_novel_numerals=forbid_novel_numerals,
            )
            if isinstance(taught, RepairPlan):
                plan = taught
            elif isinstance(taught, NoPlan):
                no_plan_reason = taught.reason
        else:
            from .. import context_broker as _cb

            error_class = _cb.classify(diagnostic.code).error_class

        payload = build_payload(
            arm,
            broken_output=current,
            diagnostic=diagnostic,
            context=context,
            plan=plan if plan is not None else (NoPlan(no_plan_reason) if no_plan_reason
                                               else None),
        )
        index = len(record_turns) + 1
        current = learner.apply(task_id=task_id, turn=index, payload=payload)
        outcome = checker(current)
        record_turns.append(
            RepairTurnRecord(
                index=index,
                arm=arm,
                diagnostic_code=diagnostic.code,
                error_class=error_class,
                context_status=context_status,
                plan=plan,
                no_plan_reason=no_plan_reason,
                output=current,
                resolved=outcome.ok,
            )
        )

    return RepairRecord(
        task_id=task_id,
        hypothesis=hypothesis,
        endpoint=endpoint,
        budget=budget,
        arm=arm,
        initial_output=initial_output,
        initial_resolved=initial_resolved,
        initial_diagnostic_code=first.code if first is not None else "",
        turns=tuple(record_turns),
        notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArmSummary:
    """Per-arm rates. First-attempt and repaired are reported separately, never merged."""

    arm: FeedbackArm
    n: int
    first_attempt_resolved: int
    repaired: int

    @property
    def first_attempt_rate(self) -> float:
        return self.first_attempt_resolved / self.n if self.n else 0.0

    @property
    def resolved_rate(self) -> float:
        return (self.first_attempt_resolved + self.repaired) / self.n if self.n else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": str(self.arm),
            "n": self.n,
            "first_attempt_resolved": self.first_attempt_resolved,
            "repaired_after_feedback": self.repaired,
            "first_attempt_rate": self.first_attempt_rate,
            "resolved_rate": self.resolved_rate,
        }


@dataclass(frozen=True)
class RepairSummary:
    """One hypothesis, one budget, three arms."""

    hypothesis: Hypothesis
    budget: RepairBudget
    endpoint: RepairEndpoint
    arms: tuple[ArmSummary, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis": self.hypothesis.value,
            "hypothesis_name": self.hypothesis.name,
            "hypothesis_excluded_claim": self.hypothesis.excluded_claim,
            "mechanism": REPAIR_MECHANISM.get(self.hypothesis, "none"),
            "budget": self.budget.value,
            "budget_limit": self.budget.limit,
            "endpoint": str(self.endpoint),
            "arms": [a.to_dict() for a in self.arms],
        }


def summarise(records: Sequence[RepairRecord], *, context: str) -> RepairSummary:
    """Aggregate, after refusing to mix hypotheses, budgets or endpoints.

    Arms are pooled — comparing them is the point. Hypotheses and budgets are not: a
    one-repair arm and a three-repair arm do not measure the same quantity, and a mixed
    mean is a number that looks exactly like a clean one.
    """
    # Endpoint first: it is the *quantity* being measured, and mixing quantities is a
    # narrower, more mechanical fault than mixing claims. Both refuse; reporting the
    # narrower one first makes the fix obvious.
    endpoints = {r.endpoint for r in records}
    if len(endpoints) > 1:
        raise HypothesisEndpointError(
            f"{context}: records span {len(endpoints)} endpoints "
            f"({', '.join(sorted(str(e) for e in endpoints))}). A syntactic-encoding rate "
            "and a mathematical-answer rate are different quantities."
        )
    hypothesis = require_single_hypothesis(records, context=context)
    budget = require_single_budget(records, context=context)

    by_arm: dict[FeedbackArm, list[RepairRecord]] = {}
    for r in records:
        by_arm.setdefault(r.arm, []).append(r)
    arms = tuple(
        ArmSummary(
            arm=arm,
            n=len(rs),
            first_attempt_resolved=sum(1 for r in rs if r.initial_resolved),
            repaired=sum(1 for r in rs if r.repaired),
        )
        for arm, rs in sorted(by_arm.items(), key=lambda kv: str(kv[0]))
    )
    return RepairSummary(
        hypothesis=hypothesis,
        budget=budget,
        endpoint=endpoints.pop(),
        arms=arms,
    )
