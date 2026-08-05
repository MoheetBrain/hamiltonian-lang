"""Phase 12 — the staged controller. One stage is executable; the rest are gates.

The seven stages describe an intended order of work. Six of them are not built. This
module makes that fact operational rather than aspirational: ``EXECUTABLE_STAGES``
contains stage 0 alone, ``execute`` refuses to run anything else, and every proposed
transition is refused with ``STAGE_NOT_IMPLEMENTED`` — *and still reports which metrics
are missing*, because a refusal that does not say what is missing teaches nothing.

Thresholds here are proposed, not calibrated
--------------------------------------------
Every number in ``GATES`` carries ``calibration = "proposed_not_calibrated"``. None was
derived from a measurement, because the measurements do not exist. They are written down
so that the shape of the argument is fixed in advance — a gate invented after seeing the
data is not a gate — and a test asserts that none of them claims to be calibrated.

Gates name a hypothesis, and evidence must match it
---------------------------------------------------
Each gate declares the hypothesis its metrics bear on. Evidence gathered under a
different hypothesis is refused with ``HYPOTHESIS_MISMATCH`` even when every number
clears its threshold. This is the controller's share of the separability requirement: a
repair-loop result (H3) can be excellent and still say nothing about whether the
representation helps as input (H1), so it cannot open an H1 gate.

Deliberately absent
-------------------
``NOT_IMPLEMENTED_MECHANISMS`` names the things this subsystem does **not** do. Nothing
here performs supervised fine-tuning, preference optimisation, low-rank adaptation,
weight promotion, best-of-N search, conjecture/solve/falsify role play, or automatic
mutation of the surface syntax. The list is exported so a reader can check the claim
against the code rather than believe it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any, TypeVar

from .state import Hypothesis, Measurement, Unavailable

__all__ = [
    "Stage",
    "EXECUTABLE_STAGES",
    "NOT_IMPLEMENTED_MECHANISMS",
    "CALIBRATION_PROPOSED",
    "MetricRequirement",
    "StageGate",
    "GATES",
    "MetricEvidence",
    "TransitionBlocker",
    "TransitionVerdict",
    "StageNotExecutable",
    "PrematureTransitionError",
    "StagedController",
]

T = TypeVar("T")


class Stage(IntEnum):
    """The intended order of work. Ordering is meaningful; only stage 0 runs."""

    STAGE_0_COMPILER_TRUST = 0
    STAGE_1_SYNTAX_ACQUISITION = 1
    STAGE_2_ON_POLICY_REPAIR = 2
    STAGE_3_HARD_NEGATIVE_PREFERENCE = 3
    STAGE_4_SEARCH_DISTILLATION = 4
    STAGE_5_SELF_PLAY = 5
    STAGE_6_LANGUAGE_EVOLUTION = 6


#: The only stage with an implementation behind it. Everything else is interface.
EXECUTABLE_STAGES: frozenset[Stage] = frozenset({Stage.STAGE_0_COMPILER_TRUST})

#: Named absences. Each of these is a thing a reader might reasonably assume is here.
NOT_IMPLEMENTED_MECHANISMS: tuple[str, ...] = (
    "supervised fine-tuning",
    "preference optimisation (DPO-style)",
    "group-relative policy optimisation (GRPO-style)",
    "low-rank adaptation of model weights",
    "promotion of model weights",
    "best-of-N search",
    "conjecturer / solver / falsifier role play",
    "automatic mutation of the surface syntax",
)

#: Every threshold in this module carries this. No number here was measured.
CALIBRATION_PROPOSED = "proposed_not_calibrated"


@dataclass(frozen=True)
class MetricRequirement:
    """One named quantity, one threshold, and the honest status of that threshold."""

    metric: str
    minimum: float
    description: str
    calibration: str = CALIBRATION_PROPOSED

    def satisfied_by(self, value: Measurement) -> bool:
        if isinstance(value, Unavailable):
            return False
        return value >= self.minimum

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "minimum": self.minimum,
            "description": self.description,
            "calibration": self.calibration,
        }


@dataclass(frozen=True)
class StageGate:
    """What must be true, and about which hypothesis, to move from one stage to the next."""

    source: Stage
    target: Stage
    hypothesis: Hypothesis
    requirements: tuple[MetricRequirement, ...]
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, Hypothesis):
            raise TypeError("StageGate.hypothesis must be a Hypothesis member")
        if self.target != self.source + 1:
            raise ValueError("a gate joins consecutive stages")

    def metric_names(self) -> tuple[str, ...]:
        return tuple(r.metric for r in self.requirements)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.name,
            "target": self.target.name,
            "hypothesis": self.hypothesis.value,
            "hypothesis_claim": self.hypothesis.claim,
            "rationale": self.rationale,
            "requirements": [r.to_dict() for r in self.requirements],
        }


def _gate(
    source: Stage, target: Stage, hypothesis: Hypothesis, rationale: str, *reqs: MetricRequirement
) -> StageGate:
    return StageGate(source, target, hypothesis, reqs, rationale)


GATES: Mapping[tuple[Stage, Stage], StageGate] = {
    (g.source, g.target): g
    for g in (
        _gate(
            Stage.STAGE_0_COMPILER_TRUST,
            Stage.STAGE_1_SYNTAX_ACQUISITION,
            Hypothesis.H1_REPRESENTATION_AS_INPUT,
            "Nothing may be learned from the compiler until the compiler's verdicts are "
            "trustworthy and every task has an oracle that can conclude.",
            MetricRequirement(
                "constitutional_suite_pass_rate",
                1.0,
                "the constitutional test suite passes in full",
            ),
            MetricRequirement(
                "diagnostic_precision",
                0.90,
                "a diagnostic names the actual defect rather than a downstream symptom",
            ),
            MetricRequirement(
                "required_verifier_coverage",
                1.0,
                "every task in the corpus has a required verifier that can return a verdict",
            ),
            MetricRequirement(
                "deterministic_oracle_coverage",
                1.0,
                "every task is scored by a deterministic oracle, never by model judgement",
            ),
        ),
        _gate(
            Stage.STAGE_1_SYNTAX_ACQUISITION,
            Stage.STAGE_2_ON_POLICY_REPAIR,
            Hypothesis.H1_REPRESENTATION_AS_INPUT,
            "On-policy repair is only meaningful once the surface can be produced at all; "
            "otherwise the repair loop is measuring syntax acquisition wearing another name.",
            MetricRequirement(
                "first_attempt_parse_rate", 0.80, "outputs that parse without any repair"
            ),
            MetricRequirement(
                "repaired_parse_rate", 0.95, "outputs that parse after at most one repair"
            ),
            MetricRequirement(
                "semantic_fidelity",
                0.90,
                "parsed outputs whose canonical form matches the reference",
            ),
        ),
        _gate(
            Stage.STAGE_2_ON_POLICY_REPAIR,
            Stage.STAGE_3_HARD_NEGATIVE_PREFERENCE,
            Hypothesis.H3_VERIFIER_GUIDED_REPAIR,
            "Preference data over near-misses is worth collecting only when the repair "
            "loop itself works and the diagnostics that drive it are precise.",
            MetricRequirement("repair_success_rate", 0.60, "single repairs that verify"),
            MetricRequirement("repaired_parse_rate", 0.95, "outputs that parse after one repair"),
            MetricRequirement("semantic_fidelity", 0.90, "canonical-form match against reference"),
            MetricRequirement("diagnostic_precision", 0.90, "diagnostics that name the defect"),
        ),
        _gate(
            Stage.STAGE_3_HARD_NEGATIVE_PREFERENCE,
            Stage.STAGE_4_SEARCH_DISTILLATION,
            Hypothesis.H2_REPRESENTATION_AS_WORKSPACE,
            "Distilling search presupposes that near-misses are minimal and attributable; "
            "without that, the distilled signal is an average over unlike things.",
            MetricRequirement(
                "hard_negative_attribution_rate",
                0.90,
                "hard negatives carrying exactly one attributed near-miss",
            ),
            MetricRequirement(
                "preference_pair_minimality_rate",
                0.95,
                "preference pairs differing in one attributable respect",
            ),
        ),
        _gate(
            Stage.STAGE_4_SEARCH_DISTILLATION,
            Stage.STAGE_5_SELF_PLAY,
            Hypothesis.H2_REPRESENTATION_AS_WORKSPACE,
            "Self-play amplifies whatever the previous stage produced, including its "
            "errors, so retention must be demonstrated before amplification.",
            MetricRequirement(
                "search_distillation_retention",
                0.90,
                "distilled behaviour retained on the held-out retention suite",
            ),
            MetricRequirement("semantic_fidelity", 0.90, "canonical-form match against reference"),
        ),
        _gate(
            Stage.STAGE_5_SELF_PLAY,
            Stage.STAGE_6_LANGUAGE_EVOLUTION,
            Hypothesis.H1_REPRESENTATION_AS_INPUT,
            "The language changes last. A surface change invalidates every earlier "
            "measurement, so it is only admissible once the earlier measurements exist.",
            MetricRequirement(
                "self_play_falsifier_yield",
                0.10,
                "self-play rounds that produce a reproducible falsification",
            ),
            MetricRequirement(
                "constitutional_suite_pass_rate", 1.0, "the constitutional suite still passes"
            ),
        ),
    )
}


@dataclass(frozen=True)
class MetricEvidence:
    """Measured values offered in support of a transition, with their provenance."""

    hypothesis: Hypothesis
    values: Mapping[str, Measurement]
    provenance: str
    state_fingerprint: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, Hypothesis):
            raise TypeError(
                "MetricEvidence.hypothesis must be a Hypothesis member. Untyped evidence "
                "cannot be kept from opening the wrong gate."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis": self.hypothesis.value,
            "provenance": self.provenance,
            "state_fingerprint": self.state_fingerprint,
            "values": {
                k: (v.to_dict() if isinstance(v, Unavailable) else v)
                for k, v in sorted(self.values.items())
            },
            "notes": list(self.notes),
        }


class TransitionBlocker(StrEnum):
    STAGE_NOT_IMPLEMENTED = "stage_not_implemented"
    NOT_THE_NEXT_STAGE = "not_the_next_stage"
    UNKNOWN_TRANSITION = "unknown_transition"
    HYPOTHESIS_MISMATCH = "hypothesis_mismatch"
    METRIC_MISSING = "metric_missing"
    METRIC_UNAVAILABLE = "metric_unavailable"
    METRIC_BELOW_THRESHOLD = "metric_below_threshold"
    PROVENANCE_MISSING = "provenance_missing"


@dataclass(frozen=True)
class TransitionVerdict:
    allowed: bool
    source: Stage
    target: Stage
    blockers: tuple[tuple[TransitionBlocker, str], ...]
    missing_metrics: tuple[str, ...]
    unavailable_metrics: tuple[str, ...]
    below_threshold: tuple[tuple[str, float, float], ...]
    gate: StageGate | None

    def codes(self) -> tuple[TransitionBlocker, ...]:
        return tuple(code for code, _ in self.blockers)

    def render(self) -> str:
        head = (
            f"{self.source.name} -> {self.target.name}: "
            f"{'ALLOWED' if self.allowed else 'REFUSED'}"
        )
        lines = [head]
        for code, detail in self.blockers:
            lines.append(f"  {code.value}: {detail}")
        if self.missing_metrics:
            lines.append(f"  missing metrics: {', '.join(self.missing_metrics)}")
        if self.unavailable_metrics:
            lines.append(f"  metrics with no value: {', '.join(self.unavailable_metrics)}")
        for name, value, minimum in self.below_threshold:
            lines.append(f"  {name}: {value} < required {minimum}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "source": self.source.name,
            "target": self.target.name,
            "blockers": [{"code": c.value, "detail": d} for c, d in self.blockers],
            "missing_metrics": list(self.missing_metrics),
            "unavailable_metrics": list(self.unavailable_metrics),
            "below_threshold": [
                {"metric": n, "value": v, "minimum": m} for n, v, m in self.below_threshold
            ],
            "gate": self.gate.to_dict() if self.gate else None,
        }


class StageNotExecutable(RuntimeError):
    """Raised when work is attempted in a stage that has no implementation."""


class PrematureTransitionError(RuntimeError):
    """Raised by ``advance`` when the gate refuses. Carries the full verdict."""

    def __init__(self, verdict: TransitionVerdict) -> None:
        super().__init__(verdict.render())
        self.verdict = verdict


class StagedController:
    """Holds the current stage, runs only what is implemented, and refuses the rest."""

    def __init__(self, stage: Stage = Stage.STAGE_0_COMPILER_TRUST) -> None:
        self._stage = stage

    @property
    def stage(self) -> Stage:
        return self._stage

    @staticmethod
    def is_executable(stage: Stage) -> bool:
        return stage in EXECUTABLE_STAGES

    def execute(self, stage: Stage, action: Callable[[], T]) -> T:
        """Run ``action`` if ``stage`` is implemented; otherwise refuse and say why."""
        if not self.is_executable(stage):
            raise StageNotExecutable(
                f"{stage.name} has no implementation. Implemented: "
                f"{', '.join(s.name for s in sorted(EXECUTABLE_STAGES))}. "
                f"Not implemented anywhere in this subsystem: "
                f"{'; '.join(NOT_IMPLEMENTED_MECHANISMS)}."
            )
        if stage is not self._stage:
            raise StageNotExecutable(
                f"controller is at {self._stage.name}; refusing to run {stage.name}"
            )
        return action()

    def evaluate_transition(
        self, target: Stage, evidence: MetricEvidence, source: Stage | None = None
    ) -> TransitionVerdict:
        """Judge a proposed transition. Always reports every reason, not the first."""
        src = source if source is not None else self._stage
        blockers: list[tuple[TransitionBlocker, str]] = []
        missing: list[str] = []
        unavailable: list[str] = []
        below: list[tuple[str, float, float]] = []

        gate = GATES.get((src, target))
        if target != src + 1:
            blockers.append(
                (
                    TransitionBlocker.NOT_THE_NEXT_STAGE,
                    f"{target.name} does not follow {src.name}; stages are not skipped",
                )
            )
        if gate is None:
            blockers.append(
                (
                    TransitionBlocker.UNKNOWN_TRANSITION,
                    f"no gate is defined for {src.name} -> {target.name}",
                )
            )
        else:
            if evidence.hypothesis is not gate.hypothesis:
                blockers.append(
                    (
                        TransitionBlocker.HYPOTHESIS_MISMATCH,
                        f"this gate is about {gate.hypothesis.name} and the evidence is "
                        f"about {evidence.hypothesis.name}. {evidence.hypothesis.excluded_claim}",
                    )
                )
            for req in gate.requirements:
                if req.metric not in evidence.values:
                    missing.append(req.metric)
                    blockers.append(
                        (
                            TransitionBlocker.METRIC_MISSING,
                            f"{req.metric} was never measured ({req.description})",
                        )
                    )
                    continue
                value = evidence.values[req.metric]
                if isinstance(value, Unavailable):
                    unavailable.append(req.metric)
                    blockers.append(
                        (
                            TransitionBlocker.METRIC_UNAVAILABLE,
                            f"{req.metric} has no value: {value.reason}",
                        )
                    )
                    continue
                if not req.satisfied_by(value):
                    below.append((req.metric, float(value), req.minimum))
                    blockers.append(
                        (
                            TransitionBlocker.METRIC_BELOW_THRESHOLD,
                            f"{req.metric} = {value} is below the required {req.minimum}",
                        )
                    )
        if not evidence.provenance.strip():
            blockers.append(
                (
                    TransitionBlocker.PROVENANCE_MISSING,
                    "evidence carries no provenance, so it cannot be reproduced",
                )
            )
        if not self.is_executable(target):
            blockers.append(
                (
                    TransitionBlocker.STAGE_NOT_IMPLEMENTED,
                    f"{target.name} is an interface and a gate, not an implementation; "
                    "the metrics above are listed so the remaining work is visible",
                )
            )

        return TransitionVerdict(
            allowed=not blockers,
            source=src,
            target=target,
            blockers=tuple(blockers),
            missing_metrics=tuple(missing),
            unavailable_metrics=tuple(unavailable),
            below_threshold=tuple(below),
            gate=gate,
        )

    def advance(self, target: Stage, evidence: MetricEvidence) -> Stage:
        """Move to ``target`` if the gate allows it. Raises with the verdict if not."""
        verdict = self.evaluate_transition(target, evidence)
        if not verdict.allowed:
            raise PrematureTransitionError(verdict)
        self._stage = target
        return self._stage

    def gate_for(self, source: Stage, target: Stage) -> StageGate | None:
        return GATES.get((source, target))

    def roadmap(self) -> dict[str, Any]:
        """Every gate, its hypothesis and its metrics — the plan, stated in one place."""
        return {
            "executable_stages": [s.name for s in sorted(EXECUTABLE_STAGES)],
            "not_implemented": list(NOT_IMPLEMENTED_MECHANISMS),
            "threshold_calibration": CALIBRATION_PROPOSED,
            "gates": [g.to_dict() for g in GATES.values()],
        }
