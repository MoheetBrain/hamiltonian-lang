"""Secondary process metrics, including the guard that keeps them secondary.

The failure these tests protect against is subtle: process metrics look like progress
even when the endpoint is flat, so they are the easiest number to quote instead of the
one H3 is about. ``assert_reported_with_endpoint`` makes that mechanical, and it is
tested in both directions.
"""

from __future__ import annotations

import pytest
from evaluation.m3.verification.process_metrics import (
    Step,
    assert_reported_with_endpoint,
    compare_repair,
    measure_trace,
)

BASE = "module Budget\n\nvar spend : NonNegativeReal\n"
CAP = BASE + "\nrequire spend <= 100\n"
BROKEN = CAP + "require spend >= 150\n"
FIXED = CAP + "require spend >= 50\n"


def _steps(sources: list[str]) -> list[Step]:
    return [Step(i, f"step {i}", src) for i, src in enumerate(sources)]


def test_the_verified_prefix_stops_at_the_first_failing_step() -> None:
    metrics = measure_trace(_steps([BASE, CAP, BROKEN]))
    assert metrics.verified_prefix_length == 2
    assert metrics.first_failing_step == 2
    assert not metrics.final_verified


def test_a_wholly_verified_trace_has_no_failing_step() -> None:
    metrics = measure_trace(_steps([BASE, CAP, FIXED]))
    assert metrics.verified_prefix_length == 3
    assert metrics.first_failing_step is None
    assert metrics.final_verified


def test_the_locally_discharged_fraction_is_between_zero_and_one() -> None:
    metrics = measure_trace(_steps([BASE, CAP, BROKEN]))
    assert 0.0 < metrics.locally_discharged_fraction < 1.0


def test_an_empty_trace_is_not_a_success() -> None:
    metrics = measure_trace([])
    assert metrics.verified_prefix_length == 0
    assert metrics.first_failing_step is None
    assert not metrics.final_verified
    assert metrics.final_verdict == "NO_TRACE"


def test_a_successful_repair_moves_the_failing_step_and_introduces_nothing() -> None:
    before = measure_trace(_steps([BASE, CAP, BROKEN]))
    after = measure_trace(_steps([BASE, CAP, FIXED]))
    effect = compare_repair(before, after)
    assert effect.moved_failing_step
    assert effect.failing_step_before == 2 and effect.failing_step_after is None
    assert effect.resolved
    assert not effect.introduced
    assert not effect.regression
    assert effect.verified_after and not effect.verified_before


def test_a_repair_that_breaks_something_else_is_reported_as_a_regression() -> None:
    """A repair that fixes the reported defect and creates a new one is not a success."""
    before = measure_trace(_steps([BASE, CAP, BROKEN]))
    worse = measure_trace(_steps([BASE, CAP + "require spend >= 50\n", BASE + "\nrequire 1 = 2\n"]))
    effect = compare_repair(before, worse)
    assert effect.regression
    assert effect.failing_step_after is not None


def test_the_metrics_record_always_carries_the_binary_endpoint() -> None:
    payload = measure_trace(_steps([BASE, CAP, BROKEN])).to_dict()
    assert "primary_endpoint" in payload
    assert payload["primary_endpoint"]["verified"] is False
    assert "secondary_process_metrics" in payload
    assert_reported_with_endpoint(payload)


def test_quoting_process_metrics_without_the_endpoint_is_refused() -> None:
    with pytest.raises(ValueError, match="without the primary endpoint"):
        assert_reported_with_endpoint(
            {"secondary_process_metrics": {"verified_prefix_length": 2}}
        )


def test_a_summary_with_no_process_metrics_is_left_alone() -> None:
    assert_reported_with_endpoint({"primary_endpoint": {"verified": True}})
    assert_reported_with_endpoint({})


def test_each_step_records_which_obligations_blocked_it() -> None:
    metrics = measure_trace(_steps([BASE, CAP, BROKEN]))
    failing = metrics.failing_obligation_ids()
    assert failing
    assert all(oid.startswith("OBL-") for oid in failing)
