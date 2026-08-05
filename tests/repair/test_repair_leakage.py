"""The A/B/C/D leakage study, run offline against scripted fixtures.

The harness is built and tested here; no live run is performed. A plan is *useful* when
C > A and C > D. A plan *leaks* when B alone — the plan with the broken output removed —
reconstructs the target at an unacceptable rate.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.context_broker import ContextStatus, ErrorClass
from hamiltonian_lang.improvement.diagnostics import SourceSpan
from hamiltonian_lang.repair import (
    DEFAULT_LEAK_THRESHOLD,
    LeakageCase,
    LeakageCondition,
    LeakageReport,
    LeakageVerdict,
    LiveProbeRefused,
    RepairPlan,
    ScriptedLeakageProbe,
    ShuffleDegenerate,
    ShuffleMode,
    run_leakage_study,
    shuffle_plan,
)

# --- fixtures ---------------------------------------------------------------------

TARGETS = {
    "arity": "def g : Real := f(1.0, 2.0)",
    "role": "law X ~ Normal(location := 0.0, scale := s)",
    "type": "param x : Real",
    "callee": "def c : Real := exp(a)",
    "refine": "def c : Real := f(1.0, 2.0)",
    "dimension": "def e : Quantity[Mass] := m",
}

BROKEN = {
    "arity": "def g : Real := f(1.0)",
    "role": "law X ~ Normal(location := 0.0, variance := s)",
    "type": "param x : Frobnicator",
    "callee": "def c : Real := wibble(a)",
    "refine": "def c : Real := f(1.0, -2.0)",
    "dimension": "def e : Quantity[Length] := m",
}

CLASSES = {
    "arity": ErrorClass.ARITY,
    "role": ErrorClass.ROLE,
    "type": ErrorClass.TYPE,
    "callee": ErrorClass.RESOLUTION,
    "refine": ErrorClass.REFINEMENT,
    "dimension": ErrorClass.DIMENSION,
}


def plan_for(name: str, *, steps: tuple[str, ...] | None = None) -> RepairPlan:
    return RepairPlan(
        failing_invariant=f"the {name} invariant was violated",
        cause=f"the construct at the span breaks the {name} rule",
        source_span=SourceSpan(line=3, col=4, file="<input>"),
        expected_semantic_category=f"a construct satisfying the {name} rule",
        repair_steps=steps
        or (
            f"Read the {name} rule shown above.",
            "Identify which part of the failing construct violates it.",
            "Edit that part only.",
        ),
        preservation_constraints=("Do not delete the failing construct.",),
        error_class=CLASSES[name],
        context_status=ContextStatus.CONTEXT_FOUND,
        diagnostic_code=f"HML-{name.upper()[:1]}000",
    )


def cases() -> list[LeakageCase]:
    return [
        LeakageCase(
            case_id=name, broken_output=BROKEN[name], plan=plan_for(name),
            target=TARGETS[name],
        )
        for name in sorted(TARGETS)
    ]


def probe_script(
    *,
    a: set[str] = frozenset(),
    b: set[str] = frozenset(),
    c: set[str] = frozenset(),
    d: set[str] = frozenset(),
) -> dict:
    """Which cases each condition reconstructs. Everything else answers nothing."""
    script: dict = {}
    for names, condition in (
        (a, LeakageCondition.A_BROKEN_ONLY),
        (b, LeakageCondition.B_PLAN_ONLY),
        (c, LeakageCondition.C_BROKEN_PLUS_PLAN),
        (d, LeakageCondition.D_BROKEN_PLUS_SHUFFLED_PLAN),
    ):
        for name in names:
            script[(name, condition)] = TARGETS[name]
    return script


# --- the four conditions are constructed correctly ---------------------------------


def test_all_four_conditions_are_run_for_every_case() -> None:
    probe = ScriptedLeakageProbe(script={})
    report = run_leakage_study(cases(), probe)
    assert len(report.trials) == 4 * len(cases())
    assert {t.condition for t in report.trials} == set(LeakageCondition)


def test_condition_b_receives_no_broken_output() -> None:
    seen: list[tuple[LeakageCondition, bool]] = []

    class Recorder:
        name = "recorder"
        live = False

        def attempt(self, *, case, condition, broken_output, plan):
            seen.append((condition, broken_output is None))
            return ""

    run_leakage_study(cases(), Recorder())
    by_condition = dict(seen)
    assert by_condition[LeakageCondition.B_PLAN_ONLY] is True
    assert by_condition[LeakageCondition.A_BROKEN_ONLY] is False
    assert by_condition[LeakageCondition.C_BROKEN_PLUS_PLAN] is False


def test_condition_a_receives_no_plan() -> None:
    plans: dict[LeakageCondition, bool] = {}

    class Recorder:
        name = "recorder"
        live = False

        def attempt(self, *, case, condition, broken_output, plan):
            plans[condition] = plan is not None
            return ""

    run_leakage_study(cases(), Recorder())
    assert plans[LeakageCondition.A_BROKEN_ONLY] is False
    assert plans[LeakageCondition.B_PLAN_ONLY] is True


# --- shuffling ---------------------------------------------------------------------


def test_step_permutation_changes_the_order_but_not_the_content() -> None:
    plan = plan_for("arity")
    shuffled = shuffle_plan(plan, seed="s")
    assert shuffled.repair_steps != plan.repair_steps
    assert sorted(shuffled.repair_steps) == sorted(plan.repair_steps)
    assert shuffled.failing_invariant == plan.failing_invariant


def test_shuffling_is_deterministic_from_the_seed() -> None:
    plan = plan_for("arity")
    assert shuffle_plan(plan, seed="x") == shuffle_plan(plan, seed="x")


def test_a_single_step_plan_cannot_be_permuted_and_says_so() -> None:
    """A D trial identical to its C trial would silently inflate D."""
    plan = plan_for("arity", steps=("Only one step.",))
    with pytest.raises(ShuffleDegenerate, match="no permutation"):
        shuffle_plan(plan, seed="s")


def test_a_degenerate_d_trial_is_excluded_with_a_reason_not_silently_dropped() -> None:
    single = [
        LeakageCase(
            case_id="only",
            broken_output=BROKEN["arity"],
            plan=plan_for("arity", steps=("Only one step.",)),
            target=TARGETS["arity"],
        )
    ]
    report = run_leakage_study(single, ScriptedLeakageProbe(script={}))
    d_trials = [
        t for t in report.trials
        if t.condition is LeakageCondition.D_BROKEN_PLUS_SHUFFLED_PLAN
    ]
    assert len(d_trials) == 1
    assert d_trials[0].usable is False
    assert "no permutation" in d_trials[0].excluded_reason
    d_rate = next(
        r for r in report.rates
        if r.condition is LeakageCondition.D_BROKEN_PLUS_SHUFFLED_PLAN
    )
    assert d_rate.excluded == 1
    assert d_rate.n == 0


def test_cross_task_shuffling_substitutes_another_cases_plan() -> None:
    a, b = plan_for("arity"), plan_for("role")
    swapped = shuffle_plan(a, seed="s", mode=ShuffleMode.CROSS_TASK, donor=b)
    assert swapped is b


def test_cross_task_shuffling_needs_a_donor() -> None:
    with pytest.raises(ShuffleDegenerate, match="donor plan"):
        shuffle_plan(plan_for("arity"), seed="s", mode=ShuffleMode.CROSS_TASK)


# --- verdicts ------------------------------------------------------------------------


def test_a_useful_non_leaking_plan() -> None:
    """C beats both A and D; B alone reconstructs nothing."""
    all_names = set(TARGETS)
    probe = ScriptedLeakageProbe(script=probe_script(a={"arity"}, c=all_names, d={"role"}))
    report = run_leakage_study(cases(), probe)
    assert report.verdict is LeakageVerdict.PLAN_USEFUL_AND_NON_LEAKING
    assert report.rate(LeakageCondition.C_BROKEN_PLUS_PLAN) == 1.0
    assert report.rate(LeakageCondition.B_PLAN_ONLY) == 0.0
    assert "exceeds both A" in report.reasoning


def test_a_leaking_plan_is_reported_as_leaking_even_when_it_is_also_useful() -> None:
    """The leak check outranks the usefulness check: usefulness is the thing in doubt."""
    all_names = set(TARGETS)
    probe = ScriptedLeakageProbe(script=probe_script(c=all_names, b=all_names))
    report = run_leakage_study(cases(), probe)
    assert report.verdict is LeakageVerdict.PLAN_LEAKS
    assert report.rate(LeakageCondition.B_PLAN_ONLY) > DEFAULT_LEAK_THRESHOLD
    assert "uninterpretable" in report.reasoning


def test_a_plan_that_does_not_beat_a_shuffled_plan_is_not_useful() -> None:
    """The control most self-repair evaluations omit."""
    all_names = set(TARGETS)
    probe = ScriptedLeakageProbe(script=probe_script(c=all_names, d=all_names))
    report = run_leakage_study(cases(), probe)
    assert report.verdict is LeakageVerdict.PLAN_NOT_USEFUL
    assert "shuffled" in report.reasoning


def test_a_plan_that_does_not_beat_the_broken_output_alone_is_not_useful() -> None:
    all_names = set(TARGETS)
    probe = ScriptedLeakageProbe(script=probe_script(a=all_names, c=all_names))
    report = run_leakage_study(cases(), probe)
    assert report.verdict is LeakageVerdict.PLAN_NOT_USEFUL


def test_too_few_trials_yields_no_verdict() -> None:
    few = cases()[:2]
    report = run_leakage_study(few, ScriptedLeakageProbe(script={}), min_trials=4)
    assert report.verdict is LeakageVerdict.INSUFFICIENT_EVIDENCE
    assert "No verdict is issued" in report.reasoning


def test_no_cases_yields_no_verdict() -> None:
    report = run_leakage_study([], ScriptedLeakageProbe(script={}))
    assert report.verdict is LeakageVerdict.INSUFFICIENT_EVIDENCE


def test_the_threshold_and_seed_are_recorded_on_the_report() -> None:
    """A report produced under one threshold must not be readable as another's."""
    report = run_leakage_study(
        cases(), ScriptedLeakageProbe(script={}), leak_threshold=0.33, seed="abc"
    )
    assert report.leak_threshold == 0.33
    assert report.seed == "abc"
    assert report.to_dict()["leak_threshold"] == 0.33
    assert "leak threshold 0.33" in report.render()


def test_the_four_verdicts_are_the_whole_enum() -> None:
    assert {v.name for v in LeakageVerdict} == {
        "PLAN_USEFUL_AND_NON_LEAKING",
        "PLAN_NOT_USEFUL",
        "PLAN_LEAKS",
        "INSUFFICIENT_EVIDENCE",
    }


# --- the harness cannot go live by accident -------------------------------------------


def test_a_live_probe_is_refused_unless_explicitly_allowed() -> None:
    live = ScriptedLeakageProbe(script={}, live=True)
    with pytest.raises(LiveProbeRefused, match="allow_live"):
        run_leakage_study(cases(), live)


def test_the_shipped_probe_is_offline() -> None:
    assert ScriptedLeakageProbe(script={}).live is False


def test_a_case_without_a_target_is_unscoreable_and_refused() -> None:
    with pytest.raises(ValueError, match="unscoreable"):
        LeakageCase(case_id="x", broken_output="y", plan=plan_for("arity"), target="  ")


def test_the_report_round_trips_to_a_dict() -> None:
    report = run_leakage_study(cases(), ScriptedLeakageProbe(script={}))
    payload = report.to_dict()
    assert isinstance(report, LeakageReport)
    assert payload["verdict"] == str(report.verdict)
    assert len(payload["trials"]) == len(report.trials)
    assert len(payload["rates"]) == 4
