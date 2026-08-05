"""Secondary process metrics over a reasoning trace.

H3's primary endpoint is binary: kernel-verified completion. These metrics describe
*how* a trajectory reached its verdict, and they exist because a null primary result is
much easier to interpret when you can see whether feedback moved the failure earlier,
later, or not at all.

They are secondary, and the code says so rather than the docstring alone
------------------------------------------------------------------------
:class:`TraceMetrics` carries ``final_verdict`` and ``final_verified``. Every reporting
path therefore has the binary result in hand at the moment it has the process numbers,
and :func:`assert_reported_with_endpoint` refuses a summary that omits it. A process
metric quoted without the endpoint is the shape a moved goalpost takes.

The four measurements
---------------------
``verified_prefix_length``
    How many leading steps verify. A trace is walked as a growing prefix; the answer is
    the number of prefixes that reach ``VERIFIED`` before the first one that does not.
``first_failing_step``
    The index of that first non-verifying prefix, or ``None`` when every prefix
    verifies. This is the step feedback would have to move.
``locally_discharged_fraction``
    Across every obligation raised at every step, the share that was discharged. It
    separates "one thing is wrong" from "nothing is checkable".
``repair effect``
    :func:`compare_repair` reports whether the failing step moved, which obligations
    were resolved, and — the one that matters most — which obligations **failed after
    the repair that did not fail before**. A repair that fixes the reported problem and
    breaks something else is not a success, and an aggregate success rate hides that.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from hamiltonian_lang.verification.obligations import (
    GlobalVerdict,
    ObligationStatus,
    VerificationOutcome,
    verify_source,
)

__all__ = [
    "PROCESS_METRICS_VERSION",
    "Step",
    "StepOutcome",
    "TraceMetrics",
    "RepairEffect",
    "measure_trace",
    "compare_repair",
    "assert_reported_with_endpoint",
]

PROCESS_METRICS_VERSION = "hml-h3-process-metrics-1.0.0"


@dataclass(frozen=True)
class Step:
    """One step of a derivation, as the **cumulative** program after that step.

    Cumulative rather than incremental because a fragment in isolation rarely compiles:
    the point of a prefix is that it is a whole program a verifier can judge.
    """

    index: int
    label: str
    source: str


@dataclass(frozen=True)
class StepOutcome:
    step: Step
    verdict: str
    verified: bool
    discharged: int
    total: int
    failing_obligations: tuple[str, ...]
    unsupported_obligations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.step.index,
            "label": self.step.label,
            "verdict": self.verdict,
            "verified": self.verified,
            "discharged": self.discharged,
            "total": self.total,
            "failing_obligations": list(self.failing_obligations),
            "unsupported_obligations": list(self.unsupported_obligations),
        }


@dataclass(frozen=True)
class TraceMetrics:
    """The four process numbers, carried together with the binary endpoint."""

    verified_prefix_length: int
    first_failing_step: int | None
    locally_discharged_fraction: float
    final_verdict: str
    final_verified: bool
    steps: tuple[StepOutcome, ...]
    version: str = PROCESS_METRICS_VERSION

    def failing_obligation_ids(self) -> tuple[str, ...]:
        if self.first_failing_step is None:
            return ()
        for outcome in self.steps:
            if outcome.step.index == self.first_failing_step:
                return outcome.failing_obligations + outcome.unsupported_obligations
        return ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "primary_endpoint": {
                "verdict": self.final_verdict,
                "verified": self.final_verified,
            },
            "secondary_process_metrics": {
                "verified_prefix_length": self.verified_prefix_length,
                "first_failing_step": self.first_failing_step,
                "locally_discharged_fraction": round(self.locally_discharged_fraction, 6),
            },
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass(frozen=True)
class RepairEffect:
    """What one repair actually did, stated in both directions."""

    failing_step_before: int | None
    failing_step_after: int | None
    moved_failing_step: bool
    resolved: tuple[str, ...]
    introduced: tuple[str, ...]
    verified_before: bool
    verified_after: bool
    #: True when the repair broke something that previously held. Reported separately
    #: from success because a net-positive average can hide a regression.
    regression: bool = field(default=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "failing_step_before": self.failing_step_before,
            "failing_step_after": self.failing_step_after,
            "moved_failing_step": self.moved_failing_step,
            "resolved_obligations": list(self.resolved),
            "introduced_obligations": list(self.introduced),
            "verified_before": self.verified_before,
            "verified_after": self.verified_after,
            "regression": self.regression,
        }


def measure_trace(steps: Sequence[Step]) -> TraceMetrics:
    """Verify every prefix and derive the four numbers.

    An empty trace is not a verified trace: it returns a prefix length of zero and no
    failing step, with ``final_verified`` False, so a missing trace cannot be counted as
    a success.
    """
    outcomes: list[StepOutcome] = []
    discharged_total = 0
    obligation_total = 0
    for step in steps:
        outcome: VerificationOutcome = verify_source(step.source, f"step-{step.index}")
        discharged = sum(1 for r in outcome.records if r.discharged)
        discharged_total += discharged
        obligation_total += len(outcome.records)
        outcomes.append(
            StepOutcome(
                step=step,
                verdict=str(outcome.verdict),
                verified=outcome.verdict is GlobalVerdict.VERIFIED,
                discharged=discharged,
                total=len(outcome.records),
                failing_obligations=tuple(
                    r.obligation_id
                    for r in outcome.records
                    if r.status is ObligationStatus.FAILED
                ),
                unsupported_obligations=tuple(
                    r.obligation_id
                    for r in outcome.records
                    if r.status is ObligationStatus.UNSUPPORTED
                ),
            )
        )

    prefix = 0
    first_failing: int | None = None
    for outcome in outcomes:
        if outcome.verified:
            prefix += 1
        else:
            first_failing = outcome.step.index
            break

    fraction = discharged_total / obligation_total if obligation_total else 0.0
    final = outcomes[-1] if outcomes else None
    return TraceMetrics(
        verified_prefix_length=prefix,
        first_failing_step=first_failing,
        locally_discharged_fraction=fraction,
        final_verdict=final.verdict if final else "NO_TRACE",
        final_verified=bool(final and final.verified),
        steps=tuple(outcomes),
    )


def compare_repair(before: TraceMetrics, after: TraceMetrics) -> RepairEffect:
    """What changed between the pre-repair and post-repair traces."""
    before_ids = set(before.failing_obligation_ids())
    after_ids = set(after.failing_obligation_ids())
    introduced = tuple(sorted(after_ids - before_ids))
    return RepairEffect(
        failing_step_before=before.first_failing_step,
        failing_step_after=after.first_failing_step,
        moved_failing_step=before.first_failing_step != after.first_failing_step,
        resolved=tuple(sorted(before_ids - after_ids)),
        introduced=introduced,
        verified_before=before.final_verified,
        verified_after=after.final_verified,
        regression=bool(introduced)
        or (before.final_verified and not after.final_verified)
        or (
            before.first_failing_step is not None
            and after.first_failing_step is not None
            and after.first_failing_step < before.first_failing_step
        ),
    )


def assert_reported_with_endpoint(summary: dict[str, Any]) -> None:
    """Refuse a summary that quotes process metrics without the binary endpoint.

    The directive is explicit that these metrics *do not replace* the endpoint. The
    cheapest way for that to be violated is a report that quotes verified-prefix length
    because it looks better than the verified rate, so the check is mechanical.
    """
    if "secondary_process_metrics" not in summary:
        return
    endpoint = summary.get("primary_endpoint")
    if not isinstance(endpoint, dict) or "verified" not in endpoint:
        raise ValueError(
            "process metrics were reported without the primary endpoint. These are "
            "secondary measurements; quoting them alone substitutes a softer number "
            "for the one H3 is about"
        )
