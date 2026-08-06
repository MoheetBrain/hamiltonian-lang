"""ACQ0 context budget: the properties that stop a silently truncated experiment.

The tests are grouped by the failure each one prevents.

**No test in this file makes a model call.** Every counter used here is offline or a
deterministic stub, and one test asserts that the live counter without a Lead
authorisation raises rather than dialling out.

The failure this file exists to prevent
---------------------------------------
An oversized prompt does not error. ``llama-server`` evicts the front of the context, the
run completes, and the demonstrations the model was meant to learn from are the part that
went missing. The affected candidate scores worse for a reason that appears nowhere in
the record. Every assertion here is downstream of that one fact.
"""

from __future__ import annotations

import inspect

import pytest
from evaluation.acq0.budget.curriculum import (
    CURRICULUM_SIZE,
    DEFAULT_LAMBDA,
    CostModel,
    HeldOutLeakage,
    NoFeasibleCurriculum,
    demonstration_pool,
    provisional_cost_model,
    select_curriculum,
)
from evaluation.acq0.budget.probe import (
    TRUNCATION_MARGIN,
    OfflineTokenCounter,
    OllamaPromptEvalCounter,
    StubTokenCounter,
    probe_prompt,
)
from evaluation.acq0.budget.report import (
    BudgetReport,
    probe_curriculum,
    walk_ladder,
    worst_case_task,
)
from evaluation.acq0.budget.slots import (
    COMPLETION_ALLOWANCE,
    DEFAULT_SAFETY_RESERVE,
    MIN_COMPLETION_ALLOWANCE,
    MIN_SAFETY_RESERVE,
    SLOT_LADDER,
    TOTAL_CONTEXT,
    AsymmetricSlotAllocation,
    ComparisonPlan,
    EstimateOfferedAsMeasurement,
    Fit,
    InsufficientAllowance,
    InsufficientReserve,
    SlotPolicy,
    UnequalCurriculum,
    assert_symmetric,
    eligibility,
    next_policy,
    policy_for_slots,
)
from evaluation.acq0.protocols.runner import LiveCallAuthorisation, UnauthorisedModelCall
from evaluation.syntax_gate.candidates import CANDIDATE_IDS, resolve_adapters
from evaluation.syntax_gate.partition import TRACK_A_DEMO_IDS, TRACK_A_HELD_OUT_IDS
from evaluation.syntax_gate.prompts import CONDITIONS
from evaluation.syntax_gate.tasks import build_corpus

from hamiltonian_lang.improvement.episodes import Measurement


def _tokens(n: int) -> Measurement:
    """A count carrying a token-counter instrument, as a real probe would return."""
    return Measurement.measured(n, instrument="provider_usage", citation="test fixture")


@pytest.fixture(scope="module")
def corpus() -> dict:
    return {t.id: t for t in build_corpus()}


@pytest.fixture(scope="module")
def five(corpus) -> list:
    return [corpus[i] for i in select_curriculum().task_ids]


# ---------------------------------------------------------------------------
# The eligibility inequality
# ---------------------------------------------------------------------------


def test_the_constants_are_the_ones_the_directive_specifies():
    assert COMPLETION_ALLOWANCE == 2048
    assert MIN_SAFETY_RESERVE >= 256
    assert DEFAULT_SAFETY_RESERVE >= MIN_SAFETY_RESERVE
    assert TOTAL_CONTEXT == 32768
    assert policy_for_slots(4).per_slot_context == 8192


def test_the_ceiling_is_the_slot_minus_the_allowance_and_the_reserve():
    assert policy_for_slots(4).prompt_ceiling() == 8192 - 2048 - 256


@pytest.mark.parametrize("slots,expected", [(4, 8192), (2, 16384), (1, 32768)])
def test_each_rung_divides_the_context_evenly(slots, expected):
    assert policy_for_slots(slots).per_slot_context == expected


def test_a_prompt_exactly_on_the_ceiling_fits_and_one_token_more_does_not():
    policy = policy_for_slots(4)
    ceiling = policy.prompt_ceiling()
    assert eligibility(_tokens(ceiling), policy).fit is Fit.FITS
    assert eligibility(_tokens(ceiling + 1), policy).fit is Fit.OVERFLOWS


def test_headroom_is_the_distance_to_the_ceiling():
    policy = policy_for_slots(4)
    verdict = eligibility(_tokens(5000), policy)
    assert verdict.headroom == policy.prompt_ceiling() - 5000


def test_an_unmeasured_prompt_is_undetermined_and_undetermined_is_not_a_pass():
    verdict = eligibility(Measurement.absent("no probe was run"), policy_for_slots(4))
    assert verdict.fit is Fit.UNDETERMINED
    # The property that matters: `fits` must be False, so a caller that only reads the
    # boolean cannot proceed on an unmeasured prompt.
    assert verdict.fits is False


def test_a_character_estimate_cannot_decide_eligibility():
    """The central rule. An estimate is refused by instrument, not by convention."""
    estimate = Measurement.measured(
        4000, instrument="time.perf_counter", citation="not a token counter"
    )
    with pytest.raises(EstimateOfferedAsMeasurement):
        eligibility(estimate, policy_for_slots(4))


def test_a_reserve_below_the_floor_is_refused():
    with pytest.raises(InsufficientReserve):
        policy_for_slots(4).prompt_ceiling(safety_reserve=0)
    with pytest.raises(InsufficientReserve):
        policy_for_slots(4).prompt_ceiling(safety_reserve=MIN_SAFETY_RESERVE - 1)


@pytest.mark.parametrize("allowance", [0, -2000, MIN_COMPLETION_ALLOWANCE - 1])
def test_the_allowance_cannot_be_shrunk_to_buy_a_fitting_verdict(allowance):
    """Finding F-3, from `tests/adversarial/test_m1_5_falsification.py`.

    The reserve was floored and the allowance was not, so a caller could shrink or negate
    the allowance, raise the ceiling and obtain FITS for a prompt that provably overflows
    the slot. Same silent-eviction failure as an unguarded reserve, reached from the
    opposite side. Rejected rather than answered: an invalid configuration has no
    eligibility verdict.
    """
    with pytest.raises(InsufficientAllowance):
        eligibility(_tokens(7900), policy_for_slots(4), completion_allowance=allowance)


def test_a_negative_allowance_cannot_lift_the_ceiling_above_the_slot():
    policy = policy_for_slots(4)
    with pytest.raises(InsufficientAllowance):
        policy.prompt_ceiling(completion_allowance=-2000)


def test_the_ceiling_never_exceeds_the_slot_at_any_permitted_setting():
    for policy in SLOT_LADDER:
        for allowance in (MIN_COMPLETION_ALLOWANCE, COMPLETION_ALLOWANCE, 4096):
            ceiling = policy.prompt_ceiling(
                completion_allowance=allowance, safety_reserve=MIN_SAFETY_RESERVE
            )
            assert ceiling <= policy.per_slot_context


def test_a_negative_ceiling_is_reported_rather_than_clamped():
    """A slot too small for the allowance cannot run any prompt, which is not the same
    fact as a prompt being too big."""
    tiny = SlotPolicy(parallel_slots=16, speedup=1.0)
    assert tiny.per_slot_context == 2048
    assert tiny.prompt_ceiling() < 0


def test_hidden_reasoning_tokens_are_inside_the_completion_allowance():
    """The allowance is for everything emitted, so a reasoning channel is already
    budgeted; there is no second allowance to forget."""
    policy = policy_for_slots(4)
    assert (
        policy.prompt_ceiling() + COMPLETION_ALLOWANCE + DEFAULT_SAFETY_RESERVE
        == policy.per_slot_context
    )


# ---------------------------------------------------------------------------
# The probe, and the truncation trap
# ---------------------------------------------------------------------------


def test_the_default_counter_is_offline_and_measures_nothing():
    counter = OfflineTokenCounter()
    assert counter.AUTHORITATIVE is False
    m = counter.count("sys", "user", num_ctx=8192)
    assert not m.is_measured


def test_the_live_counter_without_an_authorisation_raises_rather_than_dialling_out():
    with pytest.raises(UnauthorisedModelCall):
        OllamaPromptEvalCounter("gemma4:31b")


def test_the_live_counter_accepts_a_valid_authorisation_without_calling_anything():
    auth = LiveCallAuthorisation(
        authorised_by="Lead",
        call_budget=5,
        scope="ACQ0 context budget probe",
        conformance_state="green",
    )
    counter = OllamaPromptEvalCounter("gemma4:31b", auth)
    assert counter.AUTHORITATIVE is True
    assert counter.calls == []  # constructing it makes no call


def test_an_authorisation_against_a_red_tree_cannot_authorise_a_probe():
    from evaluation.acq0.protocols.runner import ConformanceNotGreen

    with pytest.raises(ConformanceNotGreen):
        LiveCallAuthorisation(
            authorised_by="Lead", call_budget=5, scope="probe", conformance_state="red"
        )


def test_a_truncated_reading_is_an_overflow_and_never_undetermined():
    """The trap: the server reports a comfortable count for a prompt it already cut."""

    class TruncatingCounter:
        AUTHORITATIVE = True
        name = "truncating"

        def count(self, system, user, *, num_ctx):
            return Measurement.absent(
                f"prompt_eval_count={num_ctx - 1} is within {TRUNCATION_MARGIN} tokens "
                f"of the {num_ctx}-token slot; the prompt was truncated"
            )

    probe = probe_prompt(
        "sys",
        "user",
        condition="D_constrained_json_graph",
        task_id="t",
        policy=policy_for_slots(4),
        counter=TruncatingCounter(),
    )
    assert probe.eligibility.fit is Fit.OVERFLOWS
    assert probe.fits is False
    assert any("truncation" in n for n in probe.notes)


def test_a_stub_counter_can_produce_a_plan_but_never_an_authoritative_one(five):
    report = walk_ladder(five, StubTokenCounter(fixed=1000))
    assert report.plan is not None
    assert report.authoritative is False
    assert report.official is False


def test_an_offline_walk_produces_no_plan_at_any_rung(five):
    report = walk_ladder(five, OfflineTokenCounter(), stop_at_first_fit=False)
    assert report.plan is None
    assert report.official is False
    for rung in report.ladder:
        assert rung.every_condition_fits is False
        assert set(rung.undetermined) == set(CONDITIONS)


def test_the_probe_records_characters_but_does_not_decide_on_them():
    probe = probe_prompt(
        "s" * 100,
        "u" * 900,
        condition="A_v0_labelled_linear",
        task_id="t",
        policy=policy_for_slots(4),
        counter=StubTokenCounter(fixed=5000),
    )
    assert probe.characters == 1001
    # The verdict comes from the count, not the characters.
    assert probe.prompt_eval_count.value == 5000
    assert probe.eligibility.headroom == policy_for_slots(4).prompt_ceiling() - 5000


# ---------------------------------------------------------------------------
# The ladder, and the symmetry that makes candidate D's cost a finding
# ---------------------------------------------------------------------------


def test_the_ladder_is_tried_highest_throughput_first():
    assert [p.parallel_slots for p in SLOT_LADDER] == [4, 2, 1]
    assert [p.per_slot_context for p in SLOT_LADDER] == [8192, 16384, 32768]
    # Descending throughput is the price of descending the ladder.
    assert [p.speedup for p in SLOT_LADDER] == sorted(
        (p.speedup for p in SLOT_LADDER), reverse=True
    )


def test_the_ladder_ends_rather_than_wrapping():
    assert next_policy(policy_for_slots(4)).parallel_slots == 2
    assert next_policy(policy_for_slots(2)).parallel_slots == 1
    assert next_policy(policy_for_slots(1)) is None


def test_the_walk_selects_the_highest_rung_on_which_every_condition_fits(five):
    """Every condition, not most of them. One overflowing candidate blocks the rung."""
    ceiling_4 = policy_for_slots(4).prompt_ceiling()

    class PerConditionCounter:
        AUTHORITATIVE = True
        name = "per-condition"

        def count(self, system, user, *, num_ctx):
            # D overflows the 4-slot rung; everything else fits comfortably.
            big = "CONSTRAINED JSON GRAPH" in user or '"triples"' in user
            return _tokens(ceiling_4 + 500 if big else 1000)

    report = walk_ladder(five, PerConditionCounter(), stop_at_first_fit=False)
    assert report.ladder[0].every_condition_fits is False
    assert "D_constrained_json_graph" in report.ladder[0].overflowing
    assert report.plan is not None
    assert report.plan.policy.parallel_slots == 2


def test_a_comparison_plan_cannot_hold_two_policies():
    """The asymmetry is not expressible: there is nowhere to put a per-candidate slot."""
    plan = ComparisonPlan(
        policy=policy_for_slots(4), curriculum=("a", "b"), candidates=CANDIDATE_IDS
    )
    fields = {f for f in plan.__dataclass_fields__}
    assert "policy" in fields
    assert not any(
        f for f in fields if "per_candidate" in f or "policies" in f
    ), "a per-candidate policy field would make the rigged comparison expressible"


def test_candidate_d_is_never_run_under_a_larger_slot_than_the_others(five):
    report = walk_ladder(five, StubTokenCounter(fixed=1000))
    for rung in report.ladder:
        policies = {p.eligibility.policy.label for p in rung.probes}
        assert len(policies) == 1, f"one rung ran conditions under {policies}"


def test_differing_slot_policies_across_candidates_are_refused():
    with pytest.raises(AsymmetricSlotAllocation):
        assert_symmetric(
            {"A": policy_for_slots(4), "D": policy_for_slots(2)},
            {"A": ["x"], "D": ["x"]},
        )


def test_trimming_one_candidates_demonstrations_is_refused():
    with pytest.raises(UnequalCurriculum):
        assert_symmetric(
            {"A": policy_for_slots(4), "D": policy_for_slots(4)},
            {"A": ["x", "y"], "D": ["x"]},
        )


def test_a_same_sized_but_different_curriculum_is_still_refused():
    """Demonstrations differ in difficulty, so equal length is not equal treatment."""
    with pytest.raises(UnequalCurriculum):
        assert_symmetric(
            {"A": policy_for_slots(4), "D": policy_for_slots(4)},
            {"A": ["x", "y"], "D": ["x", "z"]},
        )


def test_every_condition_is_probed_under_the_same_curriculum(five):
    probes = probe_curriculum(five, policy_for_slots(4), StubTokenCounter(fixed=100))
    curricula = {p.curriculum for p in probes}
    assert len(curricula) == 1
    assert curricula.pop() == tuple(t.id for t in five)


def test_no_rung_fitting_yields_no_plan_and_says_what_is_permitted(five):
    report = walk_ladder(five, StubTokenCounter(fixed=999_999), stop_at_first_fit=False)
    assert report.plan is None
    assert any("EVERY CANDIDATE TOGETHER" in n for n in report.notes)


# ---------------------------------------------------------------------------
# The five-example curriculum
# ---------------------------------------------------------------------------


def test_the_curriculum_is_exactly_five():
    assert CURRICULUM_SIZE == 5
    assert len(select_curriculum().task_ids) == 5


def test_the_same_inputs_always_give_the_same_five():
    a, b = select_curriculum(), select_curriculum()
    assert a.task_ids == b.task_ids
    assert a.digest == b.digest


def test_the_selection_is_independent_of_pool_ordering():
    """Determinism must not depend on the order the pool happened to arrive in."""
    pool = demonstration_pool()
    forward = select_curriculum(pool=pool)
    reverse = select_curriculum(pool=list(reversed(pool)))
    assert forward.task_ids == reverse.task_ids
    assert forward.digest == reverse.digest


def test_the_digest_changes_when_the_objective_changes():
    a = select_curriculum()
    b = select_curriculum(lambda_=DEFAULT_LAMBDA * 1000)
    assert a.digest != b.digest


def test_no_selected_demonstration_is_a_held_out_task():
    for task_id in select_curriculum().task_ids:
        assert task_id in TRACK_A_DEMO_IDS
        assert task_id not in TRACK_A_HELD_OUT_IDS


def test_a_held_out_task_in_the_pool_is_caught_rather_than_silently_shown(corpus):
    poisoned = list(demonstration_pool())[:4] + [
        corpus[sorted(TRACK_A_HELD_OUT_IDS)[0]]
    ]
    with pytest.raises(HeldOutLeakage):
        select_curriculum(pool=poisoned)


def test_greedy_coverage_is_monotone_with_non_increasing_marginal_gains():
    """The signature of a correct greedy pass over a submodular objective."""
    selection = select_curriculum()
    cumulative = [s.cumulative_coverage for s in selection.steps]
    assert cumulative == sorted(cumulative)
    gains = [s.marginal_coverage for s in selection.steps]
    assert gains == sorted(gains, reverse=True)
    # Cumulative coverage is exactly the running sum of the marginal gains.
    running = 0
    for step in selection.steps:
        running += step.marginal_coverage
        assert step.cumulative_coverage == running
    assert len(selection.covered) == cumulative[-1]


def test_greedy_beats_both_naive_orderings(corpus):
    """Otherwise the objective is decoration and the round-robin default would do."""
    from evaluation.syntax_gate.candidates import SHARED_CORE_FEATURES
    from evaluation.syntax_gate.partition import demonstration_curriculum

    selection = select_curriculum()

    def covered(ids):
        return set().union(*(corpus[i].features & SHARED_CORE_FEATURES for i in ids))

    by_id = covered(sorted(t.id for t in demonstration_pool())[:5])
    round_robin = covered(demonstration_curriculum(5))
    assert len(selection.covered) > len(round_robin) > len(by_id)


def test_the_selector_cannot_see_the_target_task():
    """No dynamic retrieval in primary ACQ0 — enforced by the signature, not a comment."""
    params = set(inspect.signature(select_curriculum).parameters)
    for forbidden in ("task", "target", "target_task", "query", "retrieve"):
        assert forbidden not in params


def test_a_pool_smaller_than_the_curriculum_is_refused():
    with pytest.raises(NoFeasibleCurriculum):
        select_curriculum(pool=demonstration_pool()[:3])


def test_a_provisional_cost_model_yields_a_provisional_selection():
    selection = select_curriculum(cost_model=provisional_cost_model())
    assert selection.authoritative is False
    assert not selection.token_cost.is_measured
    assert any("PROVISIONAL" in n for n in selection.notes)


def test_a_provisional_cost_cannot_masquerade_as_a_measurement():
    """The estimate stays visible in the reason and stays out of the value."""
    model = provisional_cost_model()
    m = model.as_measurement(1234, "curriculum token cost")
    assert not m.is_measured
    assert "1234" in m.reason
    assert m.value is None


def test_a_measured_cost_model_yields_an_authoritative_selection():
    pool = demonstration_pool()
    cost = {(t.id, c): 100 for t in pool for c in CANDIDATE_IDS}
    model = CostModel(cost=cost, authoritative=True, source="test fixture")
    selection = select_curriculum(cost_model=model)
    assert selection.authoritative is True
    assert selection.token_cost.is_measured
    assert selection.token_cost.value == 500


def test_the_worst_case_cost_is_over_every_candidate_not_a_subset():
    """A worst case missing one candidate would understate the one most likely to
    overflow, which is the whole reason the worst case is used."""
    model = CostModel(
        cost={("d", "A_v0_labelled_linear"): 10}, authoritative=True, source="partial"
    )
    assert model.worst_case("d") is None

    full = CostModel(
        cost={("d", c): (900 if c == "D_constrained_json_graph" else 10) for c in CANDIDATE_IDS},
        authoritative=True,
        source="full",
    )
    assert full.worst_case("d") == 900


def test_lambda_can_break_a_tie_but_not_override_a_coverage_gain():
    """With |S| fixed, the cost term must only ever choose between equal-coverage sets."""
    pool = demonstration_pool()
    cheap = select_curriculum(
        cost_model=CostModel(
            cost={(t.id, c): 1 for t in pool for c in CANDIDATE_IDS},
            authoritative=True,
            source="uniform-cheap",
        )
    )
    expensive = select_curriculum(
        cost_model=CostModel(
            cost={(t.id, c): 5000 for t in pool for c in CANDIDATE_IDS},
            authoritative=True,
            source="uniform-expensive",
        )
    )
    # Uniform costs cannot change which set covers most, at the default lambda.
    assert cheap.task_ids == expensive.task_ids
    assert len(cheap.covered) == len(expensive.covered)


# ---------------------------------------------------------------------------
# Choosing what to probe (characters may select; they may not decide)
# ---------------------------------------------------------------------------


def test_the_probe_target_is_the_longest_prompt_in_the_condition(five):
    task, chars, runner_up = worst_case_task(
        "A_v0_labelled_linear", five, resolve_adapters()
    )
    assert chars >= runner_up
    assert task.id in TRACK_A_HELD_OUT_IDS


def test_the_probe_target_choice_is_deterministic(five):
    ad = resolve_adapters()
    a = worst_case_task("D_constrained_json_graph", five, ad)
    b = worst_case_task("D_constrained_json_graph", five, ad)
    assert a[0].id == b[0].id


# ---------------------------------------------------------------------------
# The stale figure is corrected rather than deleted
# ---------------------------------------------------------------------------


def test_the_execution_environment_doc_marks_its_own_figure_as_superseded():
    """5,893 tokens was measured on legacy material and is not authoritative here.

    Asserted mechanically because a stale number that still reads as current is how a
    later reader concludes the 50-demonstration curriculum fits.
    """
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    text = (repo / "docs" / "evaluation" / "EXECUTION_ENVIRONMENT.md").read_text()
    assert "5,893" in text, "the original figure must be preserved, not deleted"
    assert "SUPERSEDED" in text
    assert "ACQ0_CONTEXT_BUDGET.md" in text
    assert "benchmarks/representations/" in text


def test_the_context_budget_doc_states_the_eligibility_rule():
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    text = (repo / "docs" / "evaluation" / "ACQ0_CONTEXT_BUDGET.md").read_text()
    assert "prompt_eval_count" in text
    assert "2048" in text and "256" in text and "8192" in text
    assert "UNDETERMINED" in text


def test_the_report_dict_is_serialisable_and_names_the_rule(five):
    import json

    report = walk_ladder(five, StubTokenCounter(fixed=1000))
    payload = json.dumps(report.to_dict())
    assert "prompt_eval_count" in payload
    assert "UNDETERMINED is never a pass" in payload


def test_a_budget_report_without_a_plan_is_not_official():
    report = BudgetReport(ladder=(), plan=None, curriculum=(), authoritative=True)
    assert report.official is False
