"""The three feedback arms, and the exclusions that make comparing them meaningful.

If ``NO_FEEDBACK`` quietly receives the diagnostic, the contrast is between two arms that
both saw the error, the measured difference collapses toward zero, and nothing in the
output shows why. These tests assert the exclusions from the payload's side.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.context_broker import ContextQuery, DiagnosticContextBroker
from hamiltonian_lang.improvement.diagnostics import adapt
from hamiltonian_lang.repair import (
    ARM_DESCRIPTION,
    ArmContamination,
    DeterministicRepairTeacher,
    FeedbackArm,
    FeedbackPayload,
    NoPlan,
    RepairPlan,
    build_payload,
)

BROKEN = "module M\ndef f(a : Real, b : Real) : Real := a + b\ndef g : Real := f(1.0)\n"


@pytest.fixture(scope="module")
def parts():
    diagnostic = adapt(compile_source(BROKEN).diagnostics.errors[0])
    broker = DiagnosticContextBroker()
    context = broker.retrieve(ContextQuery(diagnostic=diagnostic, source=BROKEN))
    plan = DeterministicRepairTeacher(broker=broker).teach(
        broken_output=BROKEN, diagnostic=diagnostic, context=context
    )
    assert isinstance(plan, RepairPlan)
    return diagnostic, context, plan


def test_there_are_exactly_three_arms() -> None:
    assert {a.name for a in FeedbackArm} == {
        "NO_FEEDBACK",
        "RAW_DIAGNOSTIC",
        "CHAIN_OF_REPAIR",
    }
    assert set(ARM_DESCRIPTION) == set(FeedbackArm)


def test_no_feedback_carries_only_the_broken_output(parts) -> None:
    diagnostic, context, plan = parts
    payload = build_payload(
        FeedbackArm.NO_FEEDBACK,
        broken_output=BROKEN,
        diagnostic=diagnostic,
        context=context,
        plan=plan,
    )
    assert payload.diagnostic_text == ""
    assert payload.context_text == ""
    assert payload.plan_text == ""
    rendered = payload.render()
    assert diagnostic.code not in rendered
    assert "arity" not in rendered.lower()
    assert BROKEN.strip() in rendered


def test_raw_diagnostic_carries_the_diagnostic_and_nothing_else(parts) -> None:
    diagnostic, context, plan = parts
    payload = build_payload(
        FeedbackArm.RAW_DIAGNOSTIC,
        broken_output=BROKEN,
        diagnostic=diagnostic,
        context=context,
        plan=plan,
    )
    assert diagnostic.code in payload.render()
    assert payload.context_text == ""
    assert payload.plan_text == ""
    for step in plan.repair_steps:
        assert step not in payload.render()


def test_chain_of_repair_carries_diagnostic_context_and_plan(parts) -> None:
    diagnostic, context, plan = parts
    payload = build_payload(
        FeedbackArm.CHAIN_OF_REPAIR,
        broken_output=BROKEN,
        diagnostic=diagnostic,
        context=context,
        plan=plan,
    )
    rendered = payload.render()
    assert diagnostic.code in rendered
    assert "source:" in rendered  # provenance travels with the context
    assert plan.failing_invariant in rendered
    assert plan.repair_steps[0] in rendered


def test_a_no_plan_result_is_stated_rather_than_hidden(parts) -> None:
    diagnostic, context, _ = parts
    payload = build_payload(
        FeedbackArm.CHAIN_OF_REPAIR,
        broken_output=BROKEN,
        diagnostic=diagnostic,
        context=context,
        plan=NoPlan(reason="no invariant is recorded for this code"),
    )
    assert "no repair plan was produced" in payload.plan_text
    assert "no invariant is recorded" in payload.plan_text


def test_a_contaminated_no_feedback_payload_is_refused() -> None:
    """Constructed by hand to simulate the bug this check exists to catch."""
    contaminated = FeedbackPayload(
        arm=FeedbackArm.NO_FEEDBACK,
        broken_output=BROKEN,
        diagnostic_text="error HML-T471",
    )
    from hamiltonian_lang.repair.arms import _assert_arm_exclusions

    with pytest.raises(ArmContamination, match="defined by their absence"):
        _assert_arm_exclusions(contaminated, diagnostic=None, plan=None)


def test_a_contaminated_raw_diagnostic_payload_is_refused(parts) -> None:
    _, _, plan = parts
    contaminated = FeedbackPayload(
        arm=FeedbackArm.RAW_DIAGNOSTIC,
        broken_output=BROKEN,
        diagnostic_text="error HML-T471",
        plan_text=plan.render(),
    )
    from hamiltonian_lang.repair.arms import _assert_arm_exclusions

    with pytest.raises(ArmContamination, match="isolate the diagnostic"):
        _assert_arm_exclusions(contaminated, diagnostic=None, plan=plan)


def test_contamination_raises_rather_than_trimming(parts) -> None:
    """Silently removing leaked material would hide the bug that put it there."""
    diagnostic, context, plan = parts
    ok = build_payload(
        FeedbackArm.NO_FEEDBACK, broken_output=BROKEN, diagnostic=diagnostic
    )
    assert ok.arm is FeedbackArm.NO_FEEDBACK

    # A broken output that already quotes its own diagnostic code is a real hazard: a
    # model that echoed the compiler output into its answer would smuggle feedback into
    # the no-feedback arm.
    with pytest.raises(ArmContamination, match="would then measure feedback"):
        build_payload(
            FeedbackArm.NO_FEEDBACK,
            broken_output=f"{BROKEN}\n# earlier run said HML-T471",
            diagnostic=diagnostic,
        )


def test_a_non_arm_value_is_a_type_error() -> None:
    with pytest.raises(TypeError, match="FeedbackArm"):
        build_payload("CHAIN_OF_REPAIR", broken_output=BROKEN)  # type: ignore[arg-type]
