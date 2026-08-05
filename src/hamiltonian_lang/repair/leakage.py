"""The leakage study — is the plan useful, and does it give the answer away?

The question this answers
-------------------------
A repair plan sits between two failure modes. Too weak and it changes nothing, so
``CHAIN_OF_REPAIR`` measures nothing. Too strong and it *contains* the answer, so
``CHAIN_OF_REPAIR`` measures transcription and the H3 number is uninterpretable. Both
failures produce a working pipeline and a plausible-looking table.

Four conditions separate them::

    A  broken output only
    B  plan only (no broken output)
    C  broken output + the correct plan
    D  broken output + a shuffled plan

*Useful* means ``C > A`` **and** ``C > D``. The second half is what most self-repair
evaluations omit: if C beats A but not D, the gain came from being prompted again with
some structured text, not from the content of the plan.

*Leaking* means **B alone** reconstructs the target at an unacceptable rate. A plan that
cannot be read without the broken program is doing its job; a plan from which the answer
can be recovered with the program removed has become the answer.

The leak check takes precedence over the usefulness check. A leaking plan that is also
useful is not a good plan — its usefulness is exactly the thing in doubt.

Offline by construction
-----------------------
:class:`LeakageProbe` is a Protocol and the shipped implementation is scripted.
:func:`run_leakage_study` refuses a probe that declares ``live`` unless ``allow_live`` is
set, so building and testing this harness cannot start making model calls by accident.
The Lead authorises live runs separately.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from .plan import RepairPlan

__all__ = [
    "LEAKAGE_VERSION",
    "DEFAULT_LEAK_THRESHOLD",
    "DEFAULT_MIN_TRIALS",
    "LeakageCondition",
    "ShuffleMode",
    "ShuffleDegenerate",
    "LiveProbeRefused",
    "LeakageCase",
    "LeakageProbe",
    "ScriptedLeakageProbe",
    "LeakageTrial",
    "ConditionRate",
    "LeakageVerdict",
    "LeakageReport",
    "shuffle_plan",
    "run_leakage_study",
]

LEAKAGE_VERSION = "hml-leakage-study-1.0.0"

#: Provisional until preregistered. Recorded on every report, so a report produced under
#: one threshold cannot be read as though it were produced under another.
DEFAULT_LEAK_THRESHOLD = 0.10

#: Below this many usable trials per condition, no verdict is issued.
DEFAULT_MIN_TRIALS = 4


class LeakageCondition(StrEnum):
    """The four conditions. Named A–D so a report cannot be misread."""

    A_BROKEN_ONLY = "A_broken_only"
    B_PLAN_ONLY = "B_plan_only"
    C_BROKEN_PLUS_PLAN = "C_broken_plus_plan"
    D_BROKEN_PLUS_SHUFFLED_PLAN = "D_broken_plus_shuffled_plan"


class ShuffleMode(StrEnum):
    """How condition D destroys the plan's coherence while keeping its surface form."""

    #: Reorder this plan's own steps. Requires at least two distinct steps.
    STEP_PERMUTATION = "step_permutation"
    #: Substitute another task's plan wholesale. The control for "any plan-shaped text".
    CROSS_TASK = "cross_task"


class ShuffleDegenerate(ValueError):
    """No shuffle of this plan differs from the plan. The D trial cannot be constructed."""


class LiveProbeRefused(RuntimeError):
    """A probe that contacts a model was supplied to a study that did not authorise one."""


@dataclass(frozen=True)
class LeakageCase:
    """One task the study runs in all four conditions."""

    case_id: str
    broken_output: str
    plan: RepairPlan
    #: What counts as reconstructing the answer. Compared by exact normalised match.
    target: str

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("LeakageCase.case_id must be non-empty")
        if not self.target.strip():
            raise ValueError(
                "LeakageCase.target must be non-empty; without a target there is nothing "
                "a leak could reconstruct and the B condition is unscoreable"
            )


# ---------------------------------------------------------------------------
# Shuffling
# ---------------------------------------------------------------------------


def _seeded_permutation(n: int, seed: str) -> list[int]:
    """A deterministic permutation of ``range(n)``, derived from ``seed``.

    Deterministic rather than random so that a study is reproducible from its seed alone;
    the digest is used as a sort key, which is a stable way to permute without carrying a
    PRNG's version-to-version behaviour into the record.
    """
    keyed = sorted(
        range(n),
        key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).hexdigest(),
    )
    return keyed


def shuffle_plan(
    plan: RepairPlan,
    *,
    seed: str,
    mode: ShuffleMode = ShuffleMode.STEP_PERMUTATION,
    donor: RepairPlan | None = None,
) -> RepairPlan:
    """Produce the condition-D plan.

    ``STEP_PERMUTATION`` reorders the steps: the same instructions, in an order that does
    not describe a repair. ``CROSS_TASK`` substitutes ``donor`` wholesale, which is the
    stronger control — it holds "a plan was present" fixed while destroying its relevance.

    Raises :class:`ShuffleDegenerate` when the result would equal the input, because a D
    trial identical to its C trial silently inflates D and hides a plan that does nothing.
    """
    if mode is ShuffleMode.CROSS_TASK:
        if donor is None:
            raise ShuffleDegenerate(
                "CROSS_TASK shuffling needs a donor plan from a different case"
            )
        if donor.repair_steps == plan.repair_steps:
            raise ShuffleDegenerate(
                "the donor plan has the same steps as the plan it would replace"
            )
        return donor

    steps = plan.repair_steps
    if len(set(steps)) < 2:
        raise ShuffleDegenerate(
            f"plan for {plan.diagnostic_code or 'case'} has {len(set(steps))} distinct "
            "step(s); no permutation of it differs from it. Use CROSS_TASK instead."
        )
    order = _seeded_permutation(len(steps), seed)
    shuffled = tuple(steps[i] for i in order)
    if shuffled == steps:
        # One retry with a derived seed. Still equal means the permutation space is
        # exhausted for this length, which is reported rather than papered over.
        order = _seeded_permutation(len(steps), seed + "!")
        shuffled = tuple(steps[i] for i in order)
    if shuffled == steps:
        raise ShuffleDegenerate(
            "the seeded permutation is the identity for this plan; the D condition would "
            "duplicate C"
        )
    from dataclasses import replace

    return replace(plan, repair_steps=shuffled)


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------


@runtime_checkable
class LeakageProbe(Protocol):
    """Whatever attempts the reconstruction. Scripted here; a model later, if authorised."""

    name: str
    live: bool

    def attempt(
        self,
        *,
        case: LeakageCase,
        condition: LeakageCondition,
        broken_output: str | None,
        plan: RepairPlan | None,
    ) -> str: ...


@dataclass
class ScriptedLeakageProbe:
    """A deterministic probe. Answers come from a fixture keyed by (case, condition).

    A missing entry is an explicit empty answer, not an error: a fixture that omits a
    condition is asserting "the probe produced nothing there", which is a legitimate
    scripted outcome and the common one for condition A.
    """

    script: Mapping[tuple[str, LeakageCondition], str]
    name: str = "scripted"
    live: bool = False
    calls: list[tuple[str, LeakageCondition]] = field(default_factory=list)

    def attempt(
        self,
        *,
        case: LeakageCase,
        condition: LeakageCondition,
        broken_output: str | None,
        plan: RepairPlan | None,
    ) -> str:
        self.calls.append((case.case_id, condition))
        return self.script.get((case.case_id, condition), "")


# ---------------------------------------------------------------------------
# Trials and the report
# ---------------------------------------------------------------------------


def _normalise(text: str) -> str:
    return " ".join(text.split())


@dataclass(frozen=True)
class LeakageTrial:
    """One (case, condition) attempt and whether it reconstructed the target."""

    case_id: str
    condition: LeakageCondition
    answer: str
    correct: bool
    #: Set when the condition could not be constructed for this case (a degenerate D).
    excluded_reason: str = ""

    @property
    def usable(self) -> bool:
        return not self.excluded_reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "condition": str(self.condition),
            "answer": self.answer,
            "correct": self.correct,
            "excluded_reason": self.excluded_reason,
            "usable": self.usable,
        }


@dataclass(frozen=True)
class ConditionRate:
    condition: LeakageCondition
    n: int
    correct: int
    excluded: int

    @property
    def rate(self) -> float:
        return self.correct / self.n if self.n else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition": str(self.condition),
            "n_usable": self.n,
            "correct": self.correct,
            "excluded": self.excluded,
            "rate": self.rate,
        }


class LeakageVerdict(StrEnum):
    """The four things a study can conclude. ``PLAN_LEAKS`` outranks everything."""

    PLAN_USEFUL_AND_NON_LEAKING = "PLAN_USEFUL_AND_NON_LEAKING"
    PLAN_NOT_USEFUL = "PLAN_NOT_USEFUL"
    PLAN_LEAKS = "PLAN_LEAKS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class LeakageReport:
    """Rates, verdict, and every parameter the verdict depends on."""

    verdict: LeakageVerdict
    rates: tuple[ConditionRate, ...]
    trials: tuple[LeakageTrial, ...]
    leak_threshold: float
    min_trials: int
    reasoning: str
    shuffle_mode: ShuffleMode
    seed: str
    leakage_version: str = LEAKAGE_VERSION

    def rate(self, condition: LeakageCondition) -> float:
        for r in self.rates:
            if r.condition is condition:
                return r.rate
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": str(self.verdict),
            "rates": [r.to_dict() for r in self.rates],
            "trials": [t.to_dict() for t in self.trials],
            "leak_threshold": self.leak_threshold,
            "min_trials": self.min_trials,
            "reasoning": self.reasoning,
            "shuffle_mode": str(self.shuffle_mode),
            "seed": self.seed,
            "leakage_version": self.leakage_version,
        }

    def render(self) -> str:
        lines = [f"leakage study [{self.verdict}]", self.reasoning, "rates:"]
        lines += [
            f"  {r.condition}: {r.correct}/{r.n} = {r.rate:.3f}"
            + (f" ({r.excluded} excluded)" if r.excluded else "")
            for r in self.rates
        ]
        lines.append(
            f"leak threshold {self.leak_threshold}; minimum usable trials {self.min_trials}"
        )
        return "\n".join(lines)


def run_leakage_study(
    cases: Sequence[LeakageCase],
    probe: LeakageProbe,
    *,
    seed: str = "hml-leakage",
    shuffle_mode: ShuffleMode = ShuffleMode.STEP_PERMUTATION,
    leak_threshold: float = DEFAULT_LEAK_THRESHOLD,
    min_trials: int = DEFAULT_MIN_TRIALS,
    allow_live: bool = False,
) -> LeakageReport:
    """Run every case in all four conditions and return the verdict.

    Under ``CROSS_TASK`` shuffling each case receives the next case's plan, cyclically, so
    every D trial carries a plan that is well formed and irrelevant. A single-case study
    cannot use that mode and its D trials are excluded with a stated reason rather than
    quietly falling back to the identity.
    """
    if getattr(probe, "live", False) and not allow_live:
        raise LiveProbeRefused(
            f"probe {getattr(probe, 'name', '?')!r} is live but the study was not started "
            "with allow_live=True. The offline harness is built and tested first; live "
            "runs are authorised separately."
        )
    if not cases:
        return LeakageReport(
            verdict=LeakageVerdict.INSUFFICIENT_EVIDENCE,
            rates=(),
            trials=(),
            leak_threshold=leak_threshold,
            min_trials=min_trials,
            reasoning="no cases were supplied",
            shuffle_mode=shuffle_mode,
            seed=seed,
        )

    trials: list[LeakageTrial] = []
    for n, case in enumerate(cases):
        target = _normalise(case.target)

        def score(condition: LeakageCondition, broken: str | None, plan: RepairPlan | None,
                  _case: LeakageCase = case, _target: str = target) -> None:
            answer = probe.attempt(
                case=_case, condition=condition, broken_output=broken, plan=plan
            )
            trials.append(
                LeakageTrial(
                    case_id=_case.case_id,
                    condition=condition,
                    answer=answer,
                    correct=_normalise(answer) == _target and bool(answer.strip()),
                )
            )

        score(LeakageCondition.A_BROKEN_ONLY, case.broken_output, None)
        score(LeakageCondition.B_PLAN_ONLY, None, case.plan)
        score(LeakageCondition.C_BROKEN_PLUS_PLAN, case.broken_output, case.plan)

        donor = cases[(n + 1) % len(cases)].plan if len(cases) > 1 else None
        try:
            shuffled = shuffle_plan(
                case.plan, seed=f"{seed}:{case.case_id}", mode=shuffle_mode, donor=donor
            )
        except ShuffleDegenerate as exc:
            trials.append(
                LeakageTrial(
                    case_id=case.case_id,
                    condition=LeakageCondition.D_BROKEN_PLUS_SHUFFLED_PLAN,
                    answer="",
                    correct=False,
                    excluded_reason=str(exc),
                )
            )
        else:
            score(
                LeakageCondition.D_BROKEN_PLUS_SHUFFLED_PLAN, case.broken_output, shuffled
            )

    rates = tuple(
        ConditionRate(
            condition=c,
            n=sum(1 for t in trials if t.condition is c and t.usable),
            correct=sum(1 for t in trials if t.condition is c and t.usable and t.correct),
            excluded=sum(1 for t in trials if t.condition is c and not t.usable),
        )
        for c in LeakageCondition
    )
    verdict, reasoning = _verdict(rates, leak_threshold=leak_threshold, min_trials=min_trials)
    return LeakageReport(
        verdict=verdict,
        rates=rates,
        trials=tuple(trials),
        leak_threshold=leak_threshold,
        min_trials=min_trials,
        reasoning=reasoning,
        shuffle_mode=shuffle_mode,
        seed=seed,
    )


def _verdict(
    rates: Sequence[ConditionRate], *, leak_threshold: float, min_trials: int
) -> tuple[LeakageVerdict, str]:
    by = {r.condition: r for r in rates}
    a = by[LeakageCondition.A_BROKEN_ONLY]
    b = by[LeakageCondition.B_PLAN_ONLY]
    c = by[LeakageCondition.C_BROKEN_PLUS_PLAN]
    d = by[LeakageCondition.D_BROKEN_PLUS_SHUFFLED_PLAN]

    thin = [r for r in (a, b, c, d) if r.n < min_trials]
    if thin:
        names = ", ".join(f"{r.condition} (n={r.n})" for r in thin)
        return (
            LeakageVerdict.INSUFFICIENT_EVIDENCE,
            f"fewer than {min_trials} usable trials in: {names}. No verdict is issued; a "
            "verdict from too few trials is a claim, not a measurement.",
        )

    if b.rate > leak_threshold:
        return (
            LeakageVerdict.PLAN_LEAKS,
            f"condition B (plan only, no broken output) reconstructed the target at "
            f"{b.rate:.3f}, above the {leak_threshold} threshold. The plan carries the "
            "answer, so any CHAIN_OF_REPAIR gain measured with it is uninterpretable.",
        )

    if c.rate > a.rate and c.rate > d.rate:
        return (
            LeakageVerdict.PLAN_USEFUL_AND_NON_LEAKING,
            f"C ({c.rate:.3f}) exceeds both A ({a.rate:.3f}) and D ({d.rate:.3f}), and B "
            f"({b.rate:.3f}) stays at or below the {leak_threshold} threshold: the plan's "
            "content helps, and its content alone does not reconstruct the target.",
        )

    if c.rate <= d.rate:
        return (
            LeakageVerdict.PLAN_NOT_USEFUL,
            f"C ({c.rate:.3f}) does not exceed D ({d.rate:.3f}). A correct plan performs "
            "no better than a shuffled one, so the gain over A is attributable to being "
            "prompted again with plan-shaped text, not to the plan's content.",
        )
    return (
        LeakageVerdict.PLAN_NOT_USEFUL,
        f"C ({c.rate:.3f}) does not exceed A ({a.rate:.3f}). Supplying the plan did not "
        "beat supplying the broken output alone.",
    )
