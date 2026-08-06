"""The A/B/C/D leakage study, run offline against scripted fixtures.

The harness is built and tested here; no live run is performed. A plan is *useful* when
C > A and C > D. A plan *leaks* when B alone — the plan with the broken output removed —
reconstructs the target at an unacceptable rate.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.context_broker import ContextStatus, ErrorClass
from hamiltonian_lang.improvement.diagnostics import SourceSpan, adapt
from hamiltonian_lang.repair import (
    DEFAULT_LEAK_THRESHOLD,
    DeterministicRepairTeacher,
    EvidenceGap,
    LeakageCase,
    LeakageCondition,
    LeakageReport,
    LeakageVerdict,
    LiveProbeRefused,
    ReconstructionProbe,
    RepairPlan,
    ScriptedLeakageProbe,
    ShuffleDegenerate,
    ShuffleMode,
    plan_leak_reasons,
    run_leakage_study,
    shuffle_plan,
    statement_lines,
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


def test_a_two_step_plan_is_still_permuted_rather_than_losing_its_d_trial() -> None:
    """A short plan draws the identity by chance, not for any reason about the plan.

    A two-step plan has exactly one non-identity permutation, so each seeded draw is a coin
    flip. Excluding its D trial would cost the study power for a reason that has nothing to
    do with the plan, so reversal is the deterministic last resort.
    """
    for seed in ("a", "b", "c", "d", "e", "f", "g", "h"):
        plan = plan_for("type", steps=("First step.", "Second step."))
        shuffled = shuffle_plan(plan, seed=seed)
        assert shuffled.repair_steps == ("Second step.", "First step.")


def test_a_palindromic_step_list_still_cannot_be_permuted_and_says_so() -> None:
    """Reversal is a fallback, not a guarantee. The guard stays reachable.

    A palindromic step list reads the same reversed, so reversal is the identity for it
    too. Seed ``s0`` is one under which both seeded draws also reproduce the tuple, which
    is what carries execution to the final guard.
    """
    plan = plan_for("type", steps=("A step.", "Another step.", "A step."))
    with pytest.raises(ShuffleDegenerate, match="including reversal"):
        shuffle_plan(plan, seed="s0")


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
    """A must stay *below* ceiling here, or the finding is an artefact of the fixture.

    If A solved every case, C could not exceed it whatever the plan contained, and the
    study would be reporting the arithmetic rather than the plan. Four of six leaves
    headroom the plan demonstrably failed to use.
    """
    four = {"arity", "role", "type", "callee"}
    probe = ScriptedLeakageProbe(script=probe_script(a=four, c=four))
    report = run_leakage_study(cases(), probe)
    assert report.rate(LeakageCondition.A_BROKEN_ONLY) < 1.0
    assert report.verdict is LeakageVerdict.PLAN_NOT_USEFUL
    assert report.evidence_gap is EvidenceGap.NONE
    assert "does not exceed A" in report.reasoning


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
    assert payload["evidence_gap"] == str(report.evidence_gap)


# --- controls on the study itself -----------------------------------------------------
#
# A four-condition table can be arithmetically well formed and measure nothing. That is
# the failure least likely to be noticed, because the harness runs, every rate is
# populated, and the verdict reads like a finding. These are the checks that the table had
# the power to distinguish anything before a verdict about the plan is issued.


def test_a_probe_that_reconstructs_nothing_yields_no_verdict_about_the_plan() -> None:
    """Floor. C > A and C > D are false as arithmetic, not as evidence."""
    report = run_leakage_study(cases(), ScriptedLeakageProbe(script={}))
    assert all(r.rate == 0.0 for r in report.rates)
    assert report.verdict is LeakageVerdict.INSUFFICIENT_EVIDENCE
    assert report.evidence_gap is EvidenceGap.PROBE_AT_FLOOR


def test_the_floor_report_does_not_claim_the_plan_lost_to_a_shuffled_one() -> None:
    """The specific false statement this control exists to prevent.

    With every rate at zero the old comparison chain reported PLAN_NOT_USEFUL and
    attributed the (non-existent) gain over A to "being prompted again with plan-shaped
    text" — an explanation of an effect that was never observed.
    """
    report = run_leakage_study(cases(), ScriptedLeakageProbe(script={}))
    assert "performs no better than a shuffled one" not in report.reasoning
    assert "attributable to" not in report.reasoning
    assert "nothing was measured" in report.reasoning


def test_a_baseline_at_ceiling_yields_no_verdict_about_the_plan() -> None:
    """Ceiling. C > A is unsatisfiable by construction, so the test is undecidable."""
    everything = set(TARGETS)
    probe = ScriptedLeakageProbe(script=probe_script(a=everything, c=everything))
    report = run_leakage_study(cases(), probe)
    assert report.rate(LeakageCondition.A_BROKEN_ONLY) == 1.0
    assert report.verdict is LeakageVerdict.INSUFFICIENT_EVIDENCE
    assert report.evidence_gap is EvidenceGap.BASELINE_AT_CEILING
    assert "undecidable on this case set rather than failed by this plan" in report.reasoning


def test_a_leak_is_still_detected_in_a_study_with_no_other_power() -> None:
    """The leak check outranks the power checks, because a leak is a positive finding.

    B reconstructed the target. That is evidence, and it does not stop being evidence
    because the other three conditions happened to sit at floor.
    """
    probe = ScriptedLeakageProbe(script=probe_script(b=set(TARGETS)))
    report = run_leakage_study(cases(), probe)
    assert report.rate(LeakageCondition.A_BROKEN_ONLY) == 0.0
    assert report.rate(LeakageCondition.C_BROKEN_PLUS_PLAN) == 0.0
    assert report.verdict is LeakageVerdict.PLAN_LEAKS
    assert report.evidence_gap is EvidenceGap.NONE


def test_each_reason_for_having_no_verdict_is_separately_identified() -> None:
    """Four causes, four fixes. A reader must not have to parse prose to tell them apart."""
    gaps = {
        run_leakage_study([], ScriptedLeakageProbe(script={})).evidence_gap,
        run_leakage_study(cases()[:2], ScriptedLeakageProbe(script={})).evidence_gap,
        run_leakage_study(cases(), ScriptedLeakageProbe(script={})).evidence_gap,
        run_leakage_study(
            cases(), ScriptedLeakageProbe(script=probe_script(a=set(TARGETS)))
        ).evidence_gap,
    }
    assert gaps == {
        EvidenceGap.NO_CASES,
        EvidenceGap.TOO_FEW_TRIALS,
        EvidenceGap.PROBE_AT_FLOOR,
        EvidenceGap.BASELINE_AT_CEILING,
    }
    assert {g.name for g in EvidenceGap} == {"NONE"} | {g.name for g in gaps}


def test_a_verdict_and_a_reason_there_is_no_verdict_cannot_both_be_recorded() -> None:
    common = {
        "rates": (), "trials": (), "leak_threshold": 0.1, "min_trials": 4,
        "reasoning": "x", "shuffle_mode": ShuffleMode.STEP_PERMUTATION, "seed": "s",
    }
    with pytest.raises(ValueError, match="cannot both be true"):
        LeakageReport(
            verdict=LeakageVerdict.PLAN_LEAKS,
            evidence_gap=EvidenceGap.PROBE_AT_FLOOR,
            **common,
        )
    with pytest.raises(ValueError, match="without an EvidenceGap"):
        LeakageReport(
            verdict=LeakageVerdict.INSUFFICIENT_EVIDENCE,
            evidence_gap=EvidenceGap.NONE,
            **common,
        )


def test_both_failed_comparisons_are_reported_when_both_failed() -> None:
    """C beat neither A nor D. Naming only one of the two hides half the result."""
    four = {"arity", "role", "type", "callee"}
    probe = ScriptedLeakageProbe(script=probe_script(a=four, c=four, d=four))
    report = run_leakage_study(cases(), probe)
    assert report.verdict is LeakageVerdict.PLAN_NOT_USEFUL
    assert "does not exceed A" in report.reasoning
    assert "does not exceed D" in report.reasoning
    # The causal attribution is only sound when there *was* a gain over A.
    assert "attributable to" not in report.reasoning


# --- condition D actually delivers a different plan -----------------------------------


def test_condition_d_delivers_a_plan_that_differs_from_condition_c() -> None:
    """The instrument check for D.

    If D silently received the correct plan, C > D would be unsatisfiable and every study
    would report PLAN_NOT_USEFUL for a reason that had nothing to do with any plan. The
    ShuffleDegenerate guard is meant to prevent that; this asserts it at the point where
    the plan is actually handed over.
    """
    delivered: dict[tuple[str, LeakageCondition], tuple[str, ...]] = {}

    class Recorder:
        name = "recorder"
        live = False

        def attempt(self, *, case, condition, broken_output, plan):
            if plan is not None:
                delivered[(case.case_id, condition)] = plan.repair_steps
            return ""

    run_leakage_study(cases(), Recorder())
    for case in cases():
        c = delivered[(case.case_id, LeakageCondition.C_BROKEN_PLUS_PLAN)]
        d = delivered[(case.case_id, LeakageCondition.D_BROKEN_PLUS_SHUFFLED_PLAN)]
        assert d != c, f"{case.case_id}: D received the same step order as C"
        assert sorted(d) == sorted(c), f"{case.case_id}: D changed the content, not order"


def test_cross_task_shuffling_gives_each_case_a_different_cases_plan() -> None:
    """The stronger control, exercised through the study rather than only on shuffle_plan.

    Every D trial carries a plan that is well formed and irrelevant, which holds "a plan
    was present" fixed while destroying its relevance.
    """
    delivered: dict[tuple[str, LeakageCondition], str] = {}

    class Recorder:
        name = "recorder"
        live = False

        def attempt(self, *, case, condition, broken_output, plan):
            if plan is not None:
                delivered[(case.case_id, condition)] = plan.failing_invariant
            return ""

    run_leakage_study(cases(), Recorder(), shuffle_mode=ShuffleMode.CROSS_TASK)
    ordered = [c.case_id for c in cases()]
    for n, case_id in enumerate(ordered):
        donor = ordered[(n + 1) % len(ordered)]
        got = delivered[(case_id, LeakageCondition.D_BROKEN_PLUS_SHUFFLED_PLAN)]
        assert got == f"the {donor} invariant was violated"
        assert got != delivered[(case_id, LeakageCondition.C_BROKEN_PLUS_PLAN)]


def test_a_single_case_cross_task_study_has_no_donor_and_says_so() -> None:
    """Not a silent fallback to the identity, which would make D a duplicate of C."""
    single = [
        LeakageCase(
            case_id="only",
            broken_output=BROKEN["arity"],
            plan=plan_for("arity"),
            target=TARGETS["arity"],
        )
    ]
    report = run_leakage_study(
        single, ScriptedLeakageProbe(script={}), shuffle_mode=ShuffleMode.CROSS_TASK
    )
    d = next(
        t for t in report.trials
        if t.condition is LeakageCondition.D_BROKEN_PLUS_SHUFFLED_PLAN
    )
    assert d.usable is False
    assert "donor plan" in d.excluded_reason
    assert report.verdict is LeakageVerdict.INSUFFICIENT_EVIDENCE


# --- a probe that reads its material, so a leak is measured rather than stipulated -----
#
# Every test above scripts the probe's answers, which means the fixture asserts the
# conclusion the study then reports. That is fine for testing the verdict arithmetic and
# worthless as evidence that the harness can detect anything. ReconstructionProbe reads
# the plan it is handed, so B rises above floor only when the plan really carries the
# answer.

LEAKING_STEPS = (
    "Read the arity rule shown above.",
    "Replace the call with the following:",
    "def g : Real := f(1.0, 2.0)",
)


def test_the_statement_detector_separates_a_program_line_from_prose() -> None:
    assert statement_lines("def g : Real := f(1.0, 2.0)") == ["def g : Real := f(1.0, 2.0)"]
    assert statement_lines("param x : Real") == ["param x : Real"]
    assert statement_lines("Read the arity rule shown above.") == []
    assert statement_lines("Do not delete the failing construct.") == []


def test_a_reconstruction_probe_detects_a_genuinely_leaking_plan() -> None:
    """The positive control: a real leak, found by reading, not by fixture."""
    leaking = [
        LeakageCase(
            case_id=name,
            broken_output=BROKEN[name],
            plan=plan_for(name, steps=LEAKING_STEPS),
            target=TARGETS["arity"],
        )
        for name in sorted(TARGETS)
    ]
    report = run_leakage_study(leaking, ReconstructionProbe())
    assert report.rate(LeakageCondition.B_PLAN_ONLY) == 1.0
    assert report.verdict is LeakageVerdict.PLAN_LEAKS


def test_the_same_probe_clears_a_plan_that_does_not_carry_the_answer() -> None:
    """The negative control. Without it the probe above could be a rubber stamp."""
    report = run_leakage_study(cases(), ReconstructionProbe())
    assert report.rate(LeakageCondition.B_PLAN_ONLY) == 0.0
    assert report.verdict is not LeakageVerdict.PLAN_LEAKS


def test_reconstructing_from_the_broken_output_alone_is_never_correct() -> None:
    """Why condition A is a true floor under this probe, by construction not by fixture."""
    probe = ReconstructionProbe()
    report = run_leakage_study(cases(), probe)
    a_trials = [
        t for t in report.trials if t.condition is LeakageCondition.A_BROKEN_ONLY
    ]
    assert all(t.answer for t in a_trials), "the probe should echo the broken statement"
    assert all(not t.correct for t in a_trials), "echoing the broken program is never right"


def test_permuting_the_steps_does_not_destroy_a_leak() -> None:
    """Why the leak check must run first, and what STEP_PERMUTATION is a control *for*.

    Reordering preserves content, so a leaked statement survives into D. STEP_PERMUTATION
    controls for the plan's *coherence*, never for what it contains — a distinction that
    matters when reading a D rate next to a B rate.
    """
    leaking = plan_for("arity", steps=LEAKING_STEPS)
    shuffled = shuffle_plan(leaking, seed="s")
    assert shuffled.repair_steps != leaking.repair_steps
    assert statement_lines("\n".join(shuffled.repair_steps)) == [
        "def g : Real := f(1.0, 2.0)"
    ]


# --- the real Teacher's own plans, through the real harness ----------------------------
#
# Everything above runs on constructed plans. These two run the plans
# DeterministicRepairTeacher actually emits for the five deterministic mappings, compiled
# from real broken programs by the real compiler, through the same four conditions.

#: broken source -> the one statement that has to change. The target of reconstruction.
REAL_CASES: dict[str, tuple[str, str]] = {
    "HML-T471": (
        "module M\ndef f(a : Real, b : Real) : Real := a + b\ndef g : Real := f(1.0)\n",
        "def g : Real := f(1.0, 2.0)",
    ),
    "HML-T472": (
        "module M\ndef f(a : Real, b : PositiveReal) : Real := a + b\n"
        "def c : Real := f(1.0, -2.0)\n",
        "def c : Real := f(1.0, 2.0)",
    ),
    "HML-T415": (
        "module M\nparam s : PositiveReal\nvar X : Real\n"
        "law X ~ Normal(location := 0.0, variance := s)\n",
        "law X ~ Normal(location := 0.0, scale := s)",
    ),
    "HML-T440": ("module M\nparam x : Frobnicator\n", "param x : Real"),
    "HML-N306": (
        "module M\nparam a : Real\ndef c : Real := wibble(a)\n",
        "def c : Real := exp(a)",
    ),
}


def real_cases() -> list[LeakageCase]:
    """One LeakageCase per deterministic mapping, carrying the Teacher's actual plan."""
    teacher = DeterministicRepairTeacher()
    out: list[LeakageCase] = []
    for code, (broken, target) in sorted(REAL_CASES.items()):
        errors = compile_source(broken).diagnostics.errors
        diagnostic = next(d for d in errors if d.code == code)
        _, plan = teacher.diagnose(broken_output=broken, diagnostic=adapt(diagnostic))
        assert isinstance(plan, RepairPlan), f"{code}: {plan}"
        out.append(
            LeakageCase(case_id=code, broken_output=broken, plan=plan, target=target)
        )
    return out


def test_the_real_teachers_plans_do_not_leak_and_usefulness_stays_unmeasured() -> None:
    """The honest offline result, stated as two separate facts.

    B sits at zero: nothing in the plans the Teacher actually emits lets a reader
    reconstruct the corrected statement without the program. That is a measurement.

    Every other rate also sits at zero, because a deterministic probe cannot repair. So
    the *usefulness* half is not "failed" — it is unmeasurable without a probe that can
    reason, which is a live component. The report says PROBE_AT_FLOOR rather than
    PLAN_NOT_USEFUL, and that distinction is the whole point of the control.
    """
    report = run_leakage_study(real_cases(), ReconstructionProbe())
    assert report.rate(LeakageCondition.B_PLAN_ONLY) == 0.0
    assert report.verdict is LeakageVerdict.INSUFFICIENT_EVIDENCE
    assert report.evidence_gap is EvidenceGap.PROBE_AT_FLOOR


def test_the_same_real_plans_are_flagged_once_the_answer_is_planted_in_them() -> None:
    """The paired positive control.

    Without it, the clean result above is equally consistent with a probe that never fires
    on anything. Same plans, same probe, same harness — one statement added.
    """
    planted = [
        replace(case.plan, repair_steps=case.plan.repair_steps[:-1] + (case.target,))
        for case in real_cases()
    ]
    leaking = [
        LeakageCase(
            case_id=case.case_id,
            broken_output=case.broken_output,
            plan=plan,
            target=case.target,
        )
        for case, plan in zip(real_cases(), planted, strict=True)
    ]
    report = run_leakage_study(leaking, ReconstructionProbe())
    assert report.rate(LeakageCondition.B_PLAN_ONLY) == 1.0
    assert report.verdict is LeakageVerdict.PLAN_LEAKS


def test_the_planted_statement_is_what_the_boundary_check_already_forbids() -> None:
    """The harness and the construction-time guard agree about the same plans.

    Two independent mechanisms — a reconstruction study and plan_leak_reasons — must not
    disagree about whether a plan carries the answer.
    """
    for case in real_cases():
        broken, target = REAL_CASES[case.case_id]
        assert plan_leak_reasons(case.plan, target_program=target) == []
        planted = replace(
            case.plan, repair_steps=case.plan.repair_steps[:-1] + (target,)
        )
        assert plan_leak_reasons(planted, target_program=target) != []
