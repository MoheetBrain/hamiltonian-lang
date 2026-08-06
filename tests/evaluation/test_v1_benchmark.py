"""Tests for the HML-V1 matched benchmark.

The load-bearing tests, and what each would catch:

* ``test_no_task_is_a_ceiling_task`` — the failure that made HML-EVAL-001 worthless. A task
  predicted above 0.70 cannot discriminate between the arms.
* ``test_tasks_are_disjoint_from_every_foreign_corpus_by_content_hash`` — an item the model
  has already seen measures memory. Checked on content, so a renamed reuse still fails.
* ``test_the_acq0_exemption_is_unreachable_from_this_benchmark`` — ACQ0's exemption supplies
  the target for *translation* tasks. Reaching it from a reasoning arm would not weaken the
  test, it would delete it.
* ``test_prompt_construction_is_independent_of_the_answer_key`` — the structural proof
  behind the leak scan's two documented exclusions. Every prompt is rebuilt against a
  mutated key and compared byte for byte.
* ``test_a_repair_driven_win_is_h3_not_h2`` — the misreport this whole design exists to
  prevent.
* ``test_verified_completion_is_never_a_false_in_the_se_arm`` — reporting SE's verified
  completion as ``False`` would manufacture a 100-point uplift out of a definition.
* ``test_no_test_in_this_module_can_reach_a_model`` — another study held the Ollama server
  while this was written. A stray call destroys its latency measurements irreversibly.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest
from evaluation.corpus.cso import ANSWER_CLOSE, ANSWER_OPEN, check_answer
from evaluation.v1_benchmark import contamination
from evaluation.v1_benchmark.arms import (
    CALLS_PER_ARM,
    MATCHING,
    PER_CALL_BUDGET,
    TASK_INDEPENDENT_SEGMENTS,
    TOTAL_COMPLETION_BUDGET,
    Arm,
    ExemptionRefused,
    extract_hml,
    hml_initial_prompt,
    hml_repair_prompt,
    se_initial_prompt,
    se_review_prompt,
    strip_answer_block,
)
from evaluation.v1_benchmark.difficulty import (
    PREDICTED_NOT_MEASURED,
    TARGET_BAND,
    Attractor,
    estimate,
)
from evaluation.v1_benchmark.pipeline import (
    FROZEN_L1_SURFACE,
    ModelAccessRefused,
    RunAuthorisation,
    ScriptedClient,
    SurfaceNotDeclared,
    run_benchmark,
    run_task,
)
from evaluation.v1_benchmark.report import (
    MissingStanding,
    design_report,
    render_text,
    run_report,
)
from evaluation.v1_benchmark.scoring import (
    TrialResult,
    aggregate,
    classify_diagnostics,
    pair_counts,
)
from evaluation.v1_benchmark.sequential import (
    DEVELOPMENTAL_STANDING,
    NULL_THRESHOLD,
    PROBABILITY_THRESHOLD,
    UPLIFT_THRESHOLD_POINTS,
    PairCounts,
    Verdict,
    decide,
    posterior_probability,
)
from evaluation.v1_benchmark.tasks import (
    DOMAINS,
    TASK_COUNT,
    build_tasks,
    by_domain,
)

from hamiltonian_lang.improvement.state import Hypothesis

TASKS = build_tasks()
AUTH = RunAuthorisation(
    authorised_by="test-suite",
    scope="scripted fixtures only",
    ollama_contention_cleared=True,
)


def _reply(answer: str, module: str | None = None) -> str:
    body = "working...\n"
    if module is not None:
        body += f"```hml\n{module}\n```\n"
    return f"{body}{ANSWER_OPEN}{answer}{ANSWER_CLOSE}"


def _scripted(task, se_first, se_final, hml_first, hml_final, module="var q : Real"):
    return ScriptedClient(
        replies=[
            _reply(se_first),
            _reply(se_final),
            _reply(hml_first, module),
            _reply(hml_final, module),
        ]
    )


# ===========================================================================
# The corpus
# ===========================================================================


def test_there_are_exactly_24_tasks_covering_all_seven_domains():
    assert len(TASKS) == TASK_COUNT == 24
    grouped = by_domain(TASKS)
    assert set(grouped) == set(DOMAINS)
    for domain, items in grouped.items():
        assert items, f"{domain} has no task; a named domain with no item is not covered"


def test_task_ids_are_unique():
    ids = [t.id for t in TASKS]
    assert len(set(ids)) == len(ids)


def test_no_task_is_a_ceiling_task():
    """The HML-EVAL-001 failure, made mechanical.

    A corpus everything gets right produces no discordant pairs, and a paired design reads
    nothing but discordant pairs. This is the test that would have stopped the pilot.
    """
    low, high = TARGET_BAND
    for t in TASKS:
        d = t.difficulty
        assert d.in_target_band, (
            f"{t.id} predicted at {d.predicted_accuracy}, outside the "
            f"{low}-{high} band. Above it the task cannot discriminate between the arms."
        )


def test_every_difficulty_figure_is_marked_predicted_not_measured():
    for t in TASKS:
        assert t.difficulty.status == PREDICTED_NOT_MEASURED
        assert t.difficulty.to_dict()["status"] == PREDICTED_NOT_MEASURED


def test_every_task_names_an_attractor_and_records_how_its_key_was_verified():
    for t in TASKS:
        assert t.cso.distractors, f"{t.id} has no named wrong answer; difficulty is then hoped for"
        assert len(t.attractor_description) > 40, t.id
        assert len(t.key_verification) > 30, t.id
        assert t.cso.answer.justification.strip(), f"{t.id} has an unjustified answer key"


def test_the_answer_key_accepts_itself():
    """A key its own checker rejects would score every arm wrong and measure nothing."""
    for t in TASKS:
        spec = t.cso.answer
        ok, _ = check_answer(spec, f"{ANSWER_OPEN}{spec.value}{ANSWER_CLOSE}")
        assert ok, f"{t.id}: check_answer rejects its own key {spec.value!r}"


def test_the_named_attractor_is_never_scored_as_correct():
    """The distractor must be far enough from the key that the tolerance cannot admit it."""
    for t in TASKS:
        if t.cso.answer.kind != "numeric":
            continue
        text = t.cso.distractors[0]
        # the distractor line begins with the wrong value
        candidate = text.split("--")[0].strip()
        ok, _ = check_answer(t.cso.answer, f"{ANSWER_OPEN}{candidate}{ANSWER_CLOSE}")
        assert not ok, f"{t.id}: the named attractor {candidate!r} scores as correct"


def test_no_constant_response_beats_a_quarter_of_the_corpus():
    """Answer bias, the defect ``test_constant_response_baselines`` caught in M3-Lite.

    A corpus whose keys cluster on one value can be beaten without reasoning. The bound is
    deliberately tight: at 24 tasks, 6 free correct answers would swamp the effect the
    study is trying to detect.
    """
    candidates = ["0", "1", "2", "-1", "0.5", "A", "B", "C", "D", "E", "TRUE", "FALSE"]
    for c in candidates:
        hits = sum(
            1 for t in TASKS if check_answer(t.cso.answer, f"{ANSWER_OPEN}{c}{ANSWER_CLOSE}")[0]
        )
        assert hits / len(TASKS) < 0.25, f"the constant answer {c!r} scores {hits}/{len(TASKS)}"


def test_the_difficulty_rubric_rejects_an_impossible_chance_floor():
    with pytest.raises(ValueError):
        estimate(dependent_steps=4, attractor=Attractor.HIGH, chance_floor=1.5, rationale="x")
    with pytest.raises(ValueError):
        estimate(dependent_steps=0, attractor=Attractor.HIGH, chance_floor=0.0, rationale="x")


def test_a_guessable_answer_cannot_be_predicted_below_its_chance_floor():
    e = estimate(dependent_steps=9, attractor=Attractor.HIGH, chance_floor=0.2, rationale="x")
    assert e.predicted_accuracy >= 0.2


# ===========================================================================
# Contamination
# ===========================================================================


def test_tasks_are_disjoint_from_every_foreign_corpus_by_content_hash():
    report = contamination.assert_clean(TASKS)
    assert report.clean()
    assert not report.hard_collisions


def test_the_registered_corpora_include_every_one_the_lead_named():
    names = {f.name for f in contamination.foreign_corpora()}
    assert "acq0::frozen_demonstrations_5" in names
    assert "acq0::calibration_tasks" in names
    # ACQ0 Round 1 draws from the held-out stage pools; all are registered.
    for stage in ("G2_screening", "G3_curriculum", "G4_confirmatory", "G4_replication"):
        assert f"acq0::{stage}" in names, stage
    assert any(n.startswith("m3_lite::") for n in names)


def test_disjointness_is_checked_on_content_and_not_on_identifiers():
    """A benchmark task renamed to a foreign id must still be reported clean.

    The converse is the real property, but this direction proves ids are not consulted:
    changing only the id changes nothing about the verdict.
    """
    renamed = list(TASKS)
    renamed[0] = replace(
        TASKS[0], cso=replace(TASKS[0].cso, id="binding_chain_000")
    )
    assert contamination.check(renamed).clean()


def test_a_copied_foreign_item_is_caught():
    """Insert a genuine foreign item under a fresh id; the content check must fail."""
    from evaluation.syntax_gate.tasks import build_track_a

    foreign = build_track_a()[0].cso
    poisoned = list(TASKS)
    poisoned[0] = replace(
        TASKS[0],
        cso=replace(
            TASKS[0].cso,
            id="v1b_99_poisoned",
            prose=foreign.prose,
            question=foreign.question,
            answer=foreign.answer,
            reference_hml=foreign.reference_hml,
        ),
    )
    with pytest.raises(contamination.ContaminationFailure):
        contamination.assert_clean(poisoned)


# ===========================================================================
# The oracle guard
# ===========================================================================


def test_assert_no_oracle_runs_in_both_arms_for_every_task():
    """Every builder calls the guard. A builder that stopped calling it would raise here
    only if it also leaked, so the direct check is that all four succeed on all 24 tasks."""
    for t in TASKS:
        se_initial_prompt(t.cso)
        se_review_prompt(t.cso, "some working")
        hml_initial_prompt(t.cso, surface_spec=FROZEN_L1_SURFACE)
        hml_repair_prompt(t.cso, "var q : Real", "error HML-N301", surface_spec=FROZEN_L1_SURFACE)


def test_the_acq0_exemption_is_unreachable_from_this_benchmark():
    """Two independent locks, tested independently.

    The ACQ0 exemption supplies the canonical target for a *translation* task. A reasoning
    arm handed the target is not a weakened test of reasoning; it is not a test of
    reasoning.
    """
    from evaluation.acq0.protocols.oracle import ACQ0_ENCODING_EXEMPTION

    cso = TASKS[0].cso
    for builder, args in (
        (se_initial_prompt, (cso,)),
        (se_review_prompt, (cso, "working")),
        (hml_initial_prompt, (cso,)),
        (hml_repair_prompt, (cso, "var q : Real", "diags")),
    ):
        with pytest.raises(ExemptionRefused):
            builder(*args, exemption=ACQ0_ENCODING_EXEMPTION)


def test_the_upstream_guard_also_refuses_the_exemption_for_a_reasoning_hypothesis():
    """The second lock, exercised directly, so neither lock alone is load-bearing."""
    from evaluation.acq0.protocols.oracle import (
        ACQ0_ENCODING_EXEMPTION,
        ExemptionMisuse,
        assert_no_oracle,
    )
    from evaluation.acq0.protocols.oracle import (
        Hypothesis as OracleHypothesis,
    )

    with pytest.raises(ExemptionMisuse):
        assert_no_oracle(
            "some prompt",
            TASKS[0].cso,
            hypothesis=OracleHypothesis.H2,
            exemption=ACQ0_ENCODING_EXEMPTION,
        )


def test_prompt_construction_is_independent_of_the_answer_key():
    """The structural proof behind the leak scan's documented exclusions.

    The upstream guard skips gold answers shorter than two characters, so four tasks here
    are not protected by substring scanning. They are protected by this instead: rebuild
    every prompt against a mutated key and compare bytes. A builder that touched
    ``answer.value`` would differ.
    """
    for t in TASKS:
        original = t.cso
        mutated = replace(
            original,
            answer=replace(original.answer, value="ZZ-MUTATED-KEY-ZZ", justification=""),
        )
        for build in (
            lambda c: se_initial_prompt(c).user,
            lambda c: se_review_prompt(c, "working").user,
            lambda c: hml_initial_prompt(c, surface_spec=FROZEN_L1_SURFACE).user,
            lambda c: hml_repair_prompt(c, "var q : Real", "diags", surface_spec=FROZEN_L1_SURFACE).user,
        ):
            try:
                mutated_prompt = build(mutated)
            except Exception:  # a mutated kind/value may not render; that is not a leak
                continue
            assert build(original) == mutated_prompt, (
                f"{t.id}: the prompt changed when only the answer key changed, so the "
                "builder reads the key"
            )


def test_excluded_segments_are_task_independent():
    """What licenses excluding the schema and the language spec from the leak scan.

    They are excluded because they are identical in every prompt and so cannot encode
    anything about one task. This asserts that premise rather than trusting it.
    """
    for segment in TASK_INDEPENDENT_SEGMENTS:
        assert segment.strip()
    for t in TASKS:
        assert TASK_INDEPENDENT_SEGMENTS[0] in se_initial_prompt(t.cso).user
        assert TASK_INDEPENDENT_SEGMENTS[1] in hml_initial_prompt(
            t.cso, surface_spec=FROZEN_L1_SURFACE
        ).user


def test_the_answer_block_is_stripped_from_carried_forward_working():
    """Removes both the leak-scan false positive and the anchoring confound."""
    text = f"reasoning here\n{ANSWER_OPEN}42{ANSWER_CLOSE}"
    assert "42" not in strip_answer_block(text)
    assert "reasoning here" in strip_answer_block(text)
    # an unterminated marker must not carry the tail through
    assert "42" not in strip_answer_block(f"work\n{ANSWER_OPEN}42")
    cso = TASKS[0].cso
    assert "42" not in se_review_prompt(cso, text).user


# ===========================================================================
# Matching
# ===========================================================================


def test_the_total_generation_budget_is_identical_in_both_arms():
    """The likeliest single reason for this result to be dismissed."""
    for t in TASKS[:3]:
        se = [se_initial_prompt(t.cso), se_review_prompt(t.cso, "w")]
        hml = [
            hml_initial_prompt(t.cso, surface_spec=FROZEN_L1_SURFACE),
            hml_repair_prompt(t.cso, "var q : Real", "d", surface_spec=FROZEN_L1_SURFACE),
        ]
        assert len(se) == len(hml) == CALLS_PER_ARM
        assert sum(p.completion_budget for p in se) == TOTAL_COMPLETION_BUDGET
        assert sum(p.completion_budget for p in hml) == TOTAL_COMPLETION_BUDGET
        assert all(p.completion_budget == PER_CALL_BUDGET for p in se + hml)


def test_the_problem_text_is_byte_identical_in_both_arms():
    for t in TASKS:
        se = se_initial_prompt(t.cso).user
        hml = hml_initial_prompt(t.cso, surface_spec=FROZEN_L1_SURFACE).user
        assert t.cso.prose in se and t.cso.prose in hml
        assert t.cso.question in se and t.cso.question in hml


def test_every_unmatched_dimension_is_recorded_with_a_reason():
    unmatched = [m for m in MATCHING if not m.matched]
    assert unmatched, "a matching table with no asymmetries is not credible"
    for m in unmatched:
        assert "NOT MATCHED" in m.detail
        assert len(m.detail) > 80, f"{m.dimension} is unmatched without an explanation"


# ===========================================================================
# Sequential analysis
# ===========================================================================


@pytest.mark.parametrize(
    "w,losses,expected",
    [
        (0, 0, Fraction(1, 2)),
        (1, 0, Fraction(3, 4)),
        (0, 1, Fraction(1, 4)),
        (2, 0, Fraction(7, 8)),
        (0, 2, Fraction(1, 8)),
        (1, 1, Fraction(1, 2)),
        (3, 0, Fraction(15, 16)),
    ],
)
def test_the_posterior_matches_the_closed_form_beta_tail(w, losses, expected):
    assert posterior_probability(w, losses) == expected


def test_no_discordant_pairs_leaves_the_prior_unmoved():
    """The HML-EVAL-001 outcome. A design that produced no discordant pairs learned nothing,
    and the arithmetic must say exactly that rather than rounding to a verdict."""
    d = decide(PairCounts(w=0, losses=0, both=24, neither=0))
    assert d.probability == Fraction(1, 2)
    assert d.verdict is Verdict.EXTEND_TO_40


def test_a_strong_signal_needs_both_the_probability_and_the_uplift():
    """Three discordant wins clear the probability threshold on their own. The uplift floor
    is what stops that being reported as a result."""
    thin = PairCounts(w=3, losses=0, both=0, neither=97)  # P >= 0.90 but uplift only 3 points
    d = decide(thin, tranche=100)
    assert posterior_probability(3, 0) >= PROBABILITY_THRESHOLD
    assert thin.uplift_points < UPLIFT_THRESHOLD_POINTS
    assert d.verdict is not Verdict.STRONG_DEVELOPMENTAL_SIGNAL


def test_the_three_decision_branches():
    strong = decide(PairCounts(w=6, losses=0, both=12, neither=6), tranche=24)
    assert strong.verdict is Verdict.STRONG_DEVELOPMENTAL_SIGNAL

    null = decide(PairCounts(w=0, losses=5, both=13, neither=6), tranche=24)
    assert null.probability <= NULL_THRESHOLD
    assert null.verdict is Verdict.NO_CURRENT_BENEFIT_SIGNAL

    middling = decide(PairCounts(w=2, losses=2, both=14, neither=6), tranche=24)
    assert middling.verdict is Verdict.EXTEND_TO_40


def test_the_study_closes_rather_than_extending_forever():
    d = decide(PairCounts(w=3, losses=3, both=24, neither=10), tranche=40)
    assert d.verdict is Verdict.INCONCLUSIVE


def test_a_fragile_verdict_reports_how_fragile_it_is():
    d = decide(PairCounts(w=3, losses=0, both=12, neither=9), tranche=24)
    assert d.verdict is Verdict.STRONG_DEVELOPMENTAL_SIGNAL
    assert d.flips_to_change == 1, (
        "a verdict one task would overturn must say so; 'STRONG DEVELOPMENTAL SIGNAL' and "
        "'three discordant pairs' belong in the same sentence"
    )


def test_every_decision_carries_the_developmental_standing():
    d = decide(PairCounts(w=8, losses=1, both=12, neither=3))
    assert d.standing == DEVELOPMENTAL_STANDING
    assert "NOT PROOF" in d.to_dict()["standing"]


def test_uplift_is_computed_from_the_discordant_cells_alone():
    """The concordant cells cancel exactly, so uplift depends only on w and l.

    The reported figure is rounded to four decimal places, so the comparison is made at
    that precision rather than at floating-point equality.
    """
    c = PairCounts(w=6, losses=2, both=10, neither=6)
    assert c.uplift_points == pytest.approx(100.0 * (6 - 2) / 24, abs=1e-4)
    # same discordant counts, concordant cells redistributed: identical uplift
    assert PairCounts(w=6, losses=2, both=16, neither=0).uplift_points == c.uplift_points


# ===========================================================================
# Scoring, and the H2/H3 separation
# ===========================================================================


def _row(arm, *, correct, first_correct=None, changed=False, hyp=None):
    first = correct if first_correct is None else first_correct
    is_se = arm is Arm.SE
    return TrialResult(
        task_id=f"t{id((arm, correct, changed, first))%9973}",
        domain="algebra",
        arm=arm,
        hypothesis=hyp or (Hypothesis.H2 if is_se or not changed else Hypothesis.H3),
        answer_correct=correct,
        first_attempt_correct=first,
        second_call_changed_answer=changed,
        verified_completion=(
            __import__("evaluation.v1_benchmark.scoring", fromlist=["x"]).SE_VERIFIED_COMPLETION_NOT_APPLICABLE
            if is_se
            else True
        ),
        structural_errors=(
            __import__("evaluation.v1_benchmark.scoring", fromlist=["x"]).SE_VERIFIED_COMPLETION_NOT_APPLICABLE
            if is_se
            else 0
        ),
        semantic_errors=(
            __import__("evaluation.v1_benchmark.scoring", fromlist=["x"]).SE_VERIFIED_COMPLETION_NOT_APPLICABLE
            if is_se
            else 0
        ),
        prompt_tokens=10,
        completion_tokens=20,
        latency_s=0.1,
    )


def test_a_repair_driven_win_is_h3_not_h2():
    """The misreport this design exists to prevent.

    HML wins the task, but only after the compiler told it something. That is evidence for
    verifier-guided repair, not for the representation, and the H2-restricted table must
    exclude it.
    """
    task = TASKS[0]
    gold = str(task.cso.answer.value)
    client = _scripted(task, se_first="999", se_final="999", hml_first="999", hml_final=gold)
    rows = run_task(task, client, surface=FROZEN_L1_SURFACE)
    hml = next(r for r in rows if r.arm is Arm.HML_V1)

    assert hml.answer_correct and not hml.first_attempt_correct
    assert hml.second_call_changed_answer
    assert hml.hypothesis is Hypothesis.H3
    assert hml.repair_attributable

    assert pair_counts(rows).w == 1, "the win counts in the overall table"
    assert pair_counts(rows, h2_only=True).n == 0, (
        "and must be excluded from the table that speaks to the representation"
    )


def test_a_win_the_repair_did_not_touch_is_h2():
    task = TASKS[0]
    gold = str(task.cso.answer.value)
    client = _scripted(task, se_first="999", se_final="999", hml_first=gold, hml_final=gold)
    rows = run_task(task, client, surface=FROZEN_L1_SURFACE)
    hml = next(r for r in rows if r.arm is Arm.HML_V1)
    assert hml.hypothesis is Hypothesis.H2
    assert not hml.second_call_changed_answer
    assert pair_counts(rows, h2_only=True).w == 1


def test_an_se_trial_can_never_be_h3():
    with pytest.raises(ValueError):
        _row(Arm.SE, correct=True, hyp=Hypothesis.H3)


def test_no_row_may_be_excluded():
    """EXCLUDED is engineering work and is never routed into a scientific aggregate."""
    with pytest.raises(ValueError):
        _row(Arm.HML_V1, correct=True, hyp=Hypothesis.EXCLUDED)


def test_every_row_carries_exactly_one_hypothesis_and_names_what_it_excludes():
    task = TASKS[0]
    rows = run_task(
        task,
        _scripted(task, "1", "1", "2", "2"),
        surface=FROZEN_L1_SURFACE,
    )
    for r in rows:
        d = r.to_dict()
        assert d["hypothesis"] in {"H2", "H3"}
        assert d["hypothesis_claim"]
        assert d["hypothesis_excluded_claim"]


def test_verified_completion_is_never_a_false_in_the_se_arm():
    """Reporting SE as False would create a 100-point uplift out of a definition."""
    from evaluation.v1.score_v1 import NotMeasured

    task = TASKS[0]
    rows = run_task(task, _scripted(task, "1", "1", "1", "1"), surface=FROZEN_L1_SURFACE)
    se = next(r for r in rows if r.arm is Arm.SE)
    assert isinstance(se.verified_completion, NotMeasured)
    assert se.verified_completion is not False
    assert "not applicable" in se.verified_completion.reason
    assert se.to_dict()["verified_completion"]["NOT MEASURED"] is True


def test_verified_completion_uplift_is_reported_separately_from_answer_accuracy():
    task = TASKS[0]
    rows = run_task(task, _scripted(task, "1", "1", "1", "1"), surface=FROZEN_L1_SURFACE)
    d = aggregate(rows).to_dict()
    assert "answer_accuracy" in d and "verified_completion" in d
    assert d["verified_completion"]["denominator"] == 1
    assert "no uplift ratio against SE" in d["verified_completion"]["note"]


def test_a_missing_module_is_a_structural_failure_and_not_a_clean_compile():
    """Compiling the empty string parses cleanly. Scoring that as a verified completion
    would reward a model that emitted no formalisation at all."""
    v = classify_diagnostics("")
    assert not v.emitted and not v.ok
    assert v.structural_errors == 1 and v.semantic_errors == 0


def test_structural_and_semantic_errors_are_counted_apart():
    structural = classify_diagnostics("var x : Rea!!l ((")
    assert structural.structural_errors > 0 and structural.semantic_errors == 0
    semantic = classify_diagnostics("var q : Real\nrequire undefined_name > 0")
    assert semantic.semantic_errors > 0 and semantic.structural_errors == 0


def test_extraction_of_an_unfenced_module_yields_nothing():
    assert extract_hml("here is my module: var q : Real") == ""
    assert extract_hml("```hml\nvar q : Real\n```") == "var q : Real"


# ===========================================================================
# The pipeline refuses to reach a model
# ===========================================================================


def test_no_test_in_this_module_can_reach_a_model():
    """Another study held the Ollama server while this was written. A concurrent call
    destroys its latency measurements and the damage cannot be undone."""
    with pytest.raises(ModelAccessRefused):
        run_benchmark(TASKS, client=None, surface=FROZEN_L1_SURFACE, authorisation=AUTH)


def test_a_run_requires_an_attributed_authorisation():
    with pytest.raises(ModelAccessRefused):
        run_benchmark(
            TASKS, client=ScriptedClient(replies=[]), surface=FROZEN_L1_SURFACE, authorisation=None
        )
    with pytest.raises(ModelAccessRefused):
        RunAuthorisation(authorised_by="", scope="s", ollama_contention_cleared=True)


def test_a_run_requires_ollama_contention_to_be_cleared():
    with pytest.raises(ModelAccessRefused):
        RunAuthorisation(authorised_by="lead", scope="s", ollama_contention_cleared=False)


def test_the_surface_under_test_must_be_named():
    """Defaulting would install HML-L1 as the syntax winner by omission."""
    with pytest.raises(SurfaceNotDeclared):
        run_benchmark(
            TASKS, client=ScriptedClient(replies=[]), surface=None, authorisation=AUTH
        )


def test_an_exhausted_fixture_raises_rather_than_scoring_a_model_failure():
    task = TASKS[0]
    with pytest.raises(AssertionError):
        run_task(task, ScriptedClient(replies=[_reply("1")]), surface=FROZEN_L1_SURFACE)


def test_the_whole_benchmark_runs_on_scripted_fixtures():
    replies: list[str] = []
    for i, t in enumerate(TASKS):
        gold = str(t.cso.answer.value)
        se = gold if i % 2 == 0 else "999"
        replies += [_reply(se), _reply(se), _reply(gold, "var q : Real"), _reply(gold, "var q : Real")]
    result = run_benchmark(
        TASKS,
        client=ScriptedClient(replies=replies),
        surface=FROZEN_L1_SURFACE,
        authorisation=AUTH,
    )
    assert len(result["_rows"]) == 2 * len(TASKS)
    assert result["manifest"]["total_completion_budget_per_task_per_arm"] == TOTAL_COMPLETION_BUDGET
    assert result["manifest"]["authorisation"]["authorised_by"] == "test-suite"


# ===========================================================================
# Reporting
# ===========================================================================


def test_the_design_report_runs_with_no_data_and_declares_itself_unmeasured():
    r = design_report()
    assert r["measured"] is False
    assert r["tasks"]["n"] == 24
    assert r["contamination"]["clean"] is True
    assert r["bears_on"]["hypotheses"] == ["H2", "H3"]
    assert "not ACQ0" in r["bears_on"]["not_acq0"]
    render_text(r)


def test_a_report_cannot_be_rendered_without_its_standing():
    r = design_report()
    r.pop("standing")
    with pytest.raises(MissingStanding):
        render_text(r)


def test_the_rendered_run_report_separates_the_two_claims_and_names_h3():
    replies: list[str] = []
    for t in TASKS:
        gold = str(t.cso.answer.value)
        replies += [_reply("999"), _reply("999"), _reply("999", "var q : Real"), _reply(gold, "var q : Real")]
    result = run_benchmark(
        TASKS,
        client=ScriptedClient(replies=replies),
        surface=FROZEN_L1_SURFACE,
        authorisation=AUTH,
    )
    text = render_text(run_report(result["_rows"]))
    assert "ANSWER ACCURACY" in text
    assert "VERIFIED COMPLETION" in text
    assert "not evidence about the representation" in text
    assert "NOT PROOF" in text
    # every win here came from the repair, so the H2-restricted table must be empty
    assert "n=0" in text
