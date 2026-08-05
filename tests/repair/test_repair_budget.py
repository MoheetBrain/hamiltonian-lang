"""Repair budgets and hypothesis discipline: one repair officially, and never pooled.

Two rules are enforced here, both because their violation is silent:

* a one-repair arm and a three-repair arm do not measure the same quantity, and a mixed
  mean looks exactly like a clean one;
* compiler-assisted **syntax** repair during ACQ0 is ``ACQ0_REPAIR``, not H3. H3 requires
  a mathematical reasoning endpoint. See ``docs/evaluation/HYPOTHESIS_REGISTER.md``.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.improvement.state import (
    REPAIR_MECHANISM,
    Hypothesis,
    HypothesisMixingError,
)
from hamiltonian_lang.repair import (
    MAX_REPAIRS,
    FeedbackArm,
    HypothesisEndpointError,
    NonOfficialBudgetError,
    RepairBudget,
    RepairBudgetExceeded,
    RepairBudgetPoolingError,
    RepairEndpoint,
    RepairRecord,
    RepairTurnRecord,
    ScriptedRepairLearner,
    assert_official,
    max_repairs,
    require_single_budget,
    run_repair_chain,
    summarise,
)

BROKEN = "module M\ndef f(a : Real, b : Real) : Real := a + b\ndef g : Real := f(1.0)\n"
STILL_BROKEN = "module M\ndef f(a : Real, b : Real) : Real := a + b\ndef g : Real := f(1.0, 2.0, 3.0)\n"
FIXED = "module M\ndef f(a : Real, b : Real) : Real := a + b\ndef g : Real := f(1.0, 2.0)\n"


def record(
    *,
    task_id: str = "t",
    hypothesis: Hypothesis = Hypothesis.ACQ0,
    endpoint: RepairEndpoint = RepairEndpoint.SYNTACTIC_ENCODING,
    budget: RepairBudget = RepairBudget.OFFICIAL_ONE,
    arm: FeedbackArm = FeedbackArm.CHAIN_OF_REPAIR,
    turns: int = 0,
    resolved: bool = False,
) -> RepairRecord:
    return RepairRecord(
        task_id=task_id,
        hypothesis=hypothesis,
        endpoint=endpoint,
        budget=budget,
        arm=arm,
        initial_output=BROKEN,
        initial_resolved=resolved and turns == 0,
        turns=tuple(
            RepairTurnRecord(
                index=n + 1,
                arm=arm,
                diagnostic_code="HML-T471",
                error_class=None,
                context_status=__import__(
                    "hamiltonian_lang.context_broker", fromlist=["ContextStatus"]
                ).ContextStatus.CONTEXT_FOUND,
                plan=None,
                no_plan_reason="",
                output=FIXED if (resolved and n == turns - 1) else BROKEN,
                resolved=resolved and n == turns - 1,
            )
            for n in range(turns)
        ),
    )


# --- the budgets themselves --------------------------------------------------------


def test_there_are_exactly_two_budgets_with_the_specified_limits() -> None:
    assert {b.name for b in RepairBudget} == {"OFFICIAL_ONE", "DEVELOPMENTAL_THREE"}
    assert MAX_REPAIRS[RepairBudget.OFFICIAL_ONE] == 1
    assert MAX_REPAIRS[RepairBudget.DEVELOPMENTAL_THREE] == 3
    assert set(MAX_REPAIRS) == set(RepairBudget)
    assert max_repairs(RepairBudget.OFFICIAL_ONE) == 1


def test_only_the_one_repair_budget_is_official() -> None:
    assert RepairBudget.OFFICIAL_ONE.official is True
    assert RepairBudget.DEVELOPMENTAL_THREE.official is False


# --- the refusal to pool ------------------------------------------------------------


def test_two_budgets_never_enter_one_statistic() -> None:
    """The test the specification asks for by name."""
    records = [
        record(task_id="a", budget=RepairBudget.OFFICIAL_ONE),
        record(
            task_id="b",
            budget=RepairBudget.DEVELOPMENTAL_THREE,
            hypothesis=Hypothesis.EXCLUDED,
        ),
    ]
    with pytest.raises(RepairBudgetPoolingError, match="span 2 repair budgets"):
        require_single_budget(records, context="test")
    with pytest.raises((RepairBudgetPoolingError, HypothesisMixingError)):
        summarise(records, context="test")


def test_an_untyped_budget_cannot_be_aggregated() -> None:
    with pytest.raises(RepairBudgetPoolingError, match="no typed RepairBudget"):
        require_single_budget([object()], context="test")


def test_an_empty_aggregate_has_no_budget() -> None:
    with pytest.raises(RepairBudgetPoolingError, match="no observations"):
        require_single_budget([], context="test")


def test_a_single_budget_aggregates_normally() -> None:
    records = [record(task_id="a"), record(task_id="b")]
    assert require_single_budget(records, context="test") is RepairBudget.OFFICIAL_ONE


def test_arms_are_pooled_because_comparing_them_is_the_point() -> None:
    records = [
        record(task_id="a", arm=FeedbackArm.NO_FEEDBACK, turns=1),
        record(task_id="b", arm=FeedbackArm.RAW_DIAGNOSTIC, turns=1, resolved=True),
        record(task_id="c", arm=FeedbackArm.CHAIN_OF_REPAIR, turns=1, resolved=True),
    ]
    summary = summarise(records, context="test")
    assert {a.arm for a in summary.arms} == set(FeedbackArm)
    assert summary.budget is RepairBudget.OFFICIAL_ONE
    assert summary.hypothesis is Hypothesis.ACQ0


def test_two_endpoints_never_enter_one_statistic() -> None:
    """An ACQ0 syntactic-encoding rate and an H3 answer rate are different quantities."""
    records = [
        record(task_id="a", hypothesis=Hypothesis.ACQ0),
        record(
            task_id="b",
            hypothesis=Hypothesis.H3,
            endpoint=RepairEndpoint.MATHEMATICAL_ANSWER,
        ),
    ]
    with pytest.raises(HypothesisEndpointError, match="different quantities"):
        summarise(records, context="test")


def test_two_hypotheses_at_one_endpoint_never_enter_one_statistic() -> None:
    """ACQ0 evidence and an EXCLUDED engineering run share the syntactic endpoint and are
    still not the same thing."""
    records = [
        record(task_id="a", hypothesis=Hypothesis.ACQ0),
        record(task_id="b", hypothesis=Hypothesis.EXCLUDED),
    ]
    with pytest.raises(HypothesisMixingError, match="span 2 hypotheses"):
        summarise(records, context="test")


# --- official runs may not use the developmental budget ------------------------------


def test_a_developmental_budget_is_refused_under_a_preregistered_hypothesis() -> None:
    for hypothesis in (Hypothesis.ACQ0, Hypothesis.H3):
        with pytest.raises(NonOfficialBudgetError, match="maximum of one repair"):
            assert_official(
                RepairBudget.DEVELOPMENTAL_THREE, hypothesis=hypothesis, context="test"
            )


def test_a_developmental_budget_is_allowed_for_excluded_engineering_work() -> None:
    assert_official(
        RepairBudget.DEVELOPMENTAL_THREE, hypothesis=Hypothesis.EXCLUDED, context="test"
    )


def test_a_record_cannot_carry_a_developmental_budget_under_acq0() -> None:
    with pytest.raises(NonOfficialBudgetError):
        record(budget=RepairBudget.DEVELOPMENTAL_THREE)


# --- the ACQ0 / H3 boundary ----------------------------------------------------------


def test_h3_requires_a_mathematical_endpoint() -> None:
    with pytest.raises(HypothesisEndpointError, match="mathematical reasoning endpoint"):
        record(hypothesis=Hypothesis.H3, endpoint=RepairEndpoint.SYNTACTIC_ENCODING)


def test_acq0_requires_a_syntactic_endpoint() -> None:
    with pytest.raises(HypothesisEndpointError, match="the hypothesis is H3"):
        record(hypothesis=Hypothesis.ACQ0, endpoint=RepairEndpoint.MATHEMATICAL_ANSWER)


def test_h1_and_h2_may_not_carry_a_repair_turn_at_all() -> None:
    for hypothesis in (Hypothesis.H1, Hypothesis.H2):
        with pytest.raises(HypothesisEndpointError, match="does not involve a repair loop"):
            record(
                hypothesis=hypothesis,
                endpoint=RepairEndpoint.MATHEMATICAL_ANSWER,
                turns=1,
            )


def test_the_mechanism_names_acq0_repair_separately_from_h3() -> None:
    acq0 = record(hypothesis=Hypothesis.ACQ0)
    assert acq0.mechanism == "ACQ0_REPAIR"
    assert REPAIR_MECHANISM[Hypothesis.H3] == "H3_VERIFIER_GUIDED_REPAIR"
    assert acq0.mechanism != REPAIR_MECHANISM[Hypothesis.H3]


def test_every_record_carries_exactly_one_typed_hypothesis() -> None:
    with pytest.raises(TypeError, match="Hypothesis member"):
        record(hypothesis="ACQ0")  # type: ignore[arg-type]


def test_the_serialised_record_states_what_it_does_not_support() -> None:
    payload = record(hypothesis=Hypothesis.ACQ0).to_dict()
    assert payload["hypothesis"] == "ACQ0"
    assert payload["mechanism"] == "ACQ0_REPAIR"
    assert "does NOT support any claim about H1, H2 or H3" in payload[
        "hypothesis_excluded_claim"
    ]


# --- the limit is enforced, not advisory ---------------------------------------------


def test_a_record_with_more_turns_than_the_budget_is_refused() -> None:
    with pytest.raises(RepairBudgetExceeded, match="permits 1"):
        record(turns=2)


def test_the_chain_stops_at_the_official_limit() -> None:
    learner = ScriptedRepairLearner(
        script={("t", FeedbackArm.CHAIN_OF_REPAIR, n): STILL_BROKEN for n in (1, 2, 3)}
    )
    result = run_repair_chain(
        task_id="t",
        hypothesis=Hypothesis.ACQ0,
        endpoint=RepairEndpoint.SYNTACTIC_ENCODING,
        budget=RepairBudget.OFFICIAL_ONE,
        arm=FeedbackArm.CHAIN_OF_REPAIR,
        initial_output=BROKEN,
        learner=learner,
    )
    assert result.repair_turns_used == 1
    assert learner.call_count() == 1


def test_the_developmental_chain_may_take_three_turns_but_only_as_excluded() -> None:
    learner = ScriptedRepairLearner(
        script={("t", FeedbackArm.CHAIN_OF_REPAIR, n): STILL_BROKEN for n in (1, 2, 3)}
    )
    result = run_repair_chain(
        task_id="t",
        hypothesis=Hypothesis.EXCLUDED,
        endpoint=RepairEndpoint.SYNTACTIC_ENCODING,
        budget=RepairBudget.DEVELOPMENTAL_THREE,
        arm=FeedbackArm.CHAIN_OF_REPAIR,
        initial_output=BROKEN,
        learner=learner,
    )
    assert result.repair_turns_used == 3
    assert result.budget is RepairBudget.DEVELOPMENTAL_THREE
    assert result.hypothesis is Hypothesis.EXCLUDED
