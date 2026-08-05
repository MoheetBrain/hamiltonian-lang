"""Frozen prompts: matched information content, verbatim shared content, five conditions.

"Matched" is asserted here rather than promised. What cannot be matched — character
length of an S-expression spec against a JSON spec of the same content — is measured and
reported instead of being padded into false equality.
"""

from __future__ import annotations

import pytest
from evaluation.syntax_gate.candidates import (
    CANDIDATE_IDS,
    SE_CONTROL,
    SHARED_CORE_FEATURES,
    V0LinearAdapter,
)
from evaluation.syntax_gate.prompts import (
    CONDITIONS,
    G4_CONDITIONS,
    SECTION_COVERAGE,
    SECTION_ORDER,
    SPEC_SECTIONS,
    RendererUnavailable,
    build_prompt,
    render_demonstration,
    render_spec,
    spec_size_report,
    verify_shared_content_identical,
)
from evaluation.syntax_gate.tasks import build_track_a

TASKS = build_track_a()
SAMPLE = [TASKS[0], TASKS[30], TASKS[60], TASKS[90], TASKS[120], TASKS[150], TASKS[180],
          TASKS[210]]


def test_five_conditions_and_the_control_is_one_of_them():
    assert len(CONDITIONS) == 5
    assert set(CONDITIONS) == set(CANDIDATE_IDS) | {SE_CONTROL}


def test_g4_must_carry_the_structured_english_control():
    """Without it the Gate 2 token threshold has no denominator and cannot be evaluated,
    while the run would still look complete."""
    assert SE_CONTROL in G4_CONDITIONS


def test_every_condition_documents_the_same_sections_in_the_same_order():
    for condition in CONDITIONS:
        assert [s.key for s in SPEC_SECTIONS[condition]] == list(SECTION_ORDER)


def test_every_section_covers_the_same_features_in_every_condition():
    for key in SECTION_ORDER:
        covered = {
            condition: next(s for s in SPEC_SECTIONS[condition] if s.key == key).covers
            for condition in CONDITIONS
        }
        assert len(set(covered.values())) == 1, (key, covered)


def test_the_sections_cover_exactly_the_shared_core():
    union = frozenset().union(*SECTION_COVERAGE.values())
    assert union == SHARED_CORE_FEATURES
    assert len(union) == 34


def test_no_section_is_empty_in_any_condition():
    for condition in CONDITIONS:
        for s in SPEC_SECTIONS[condition]:
            assert len(s.body.strip()) > 60, (condition, s.key)


@pytest.mark.parametrize("task", SAMPLE, ids=[t.id for t in SAMPLE])
def test_shared_content_is_carried_verbatim_in_every_condition(task):
    verify_shared_content_identical(task)


@pytest.mark.parametrize("task", SAMPLE, ids=[t.id for t in SAMPLE])
def test_the_answer_instruction_is_identical_in_every_condition(task):
    instruction = task.cso.answer.render_instruction()
    for condition in CONDITIONS:
        assert instruction in build_prompt(task, condition).user


def test_every_condition_receives_the_same_number_of_demonstrations():
    demos = TASKS[:2]
    adapters = {c: V0LinearAdapter() for c in CANDIDATE_IDS}
    sizes = {
        c: build_prompt(TASKS[100], c, demos, adapters).curriculum_size
        for c in CONDITIONS
    }
    assert set(sizes.values()) == {2}


def test_demonstrations_render_in_each_condition_own_notation():
    """A demonstration rendered in the wrong surface would teach the model the wrong
    syntax and the resulting parse rate would be blamed on the candidate."""
    from evaluation.syntax_gate.candidates import CANDIDATES, resolve_adapters

    adapters = resolve_adapters()
    demo = TASKS[0]
    rendered = {}
    for condition in CANDIDATE_IDS:
        if adapters[condition] is None:
            continue
        text = render_demonstration(demo, condition, adapters)
        assert text.startswith(f"```{CANDIDATES[condition].fence_tags[0]}\n")
        assert f"<ANSWER>{demo.cso.answer.value}</ANSWER>" in text
        rendered[condition] = text
    assert rendered, "candidate A always has a front end"
    # Different surfaces must actually differ, or one is being substituted for another.
    assert len(set(rendered.values())) == len(rendered)
    se = render_demonstration(demo, SE_CONTROL, adapters)
    assert "```" not in se
    assert f"<ANSWER>{demo.cso.answer.value}</ANSWER>" in se


def _budget_report():
    from evaluation.syntax_gate.candidates import resolve_adapters
    from evaluation.syntax_gate.partition import CURRICULUM_SIZES, demonstration_curriculum
    from evaluation.syntax_gate.prompts import prompt_budget_report

    by_id = {t.id: t for t in TASKS}
    demos = {n: [by_id[i] for i in demonstration_curriculum(n)] for n in CURRICULUM_SIZES}
    return prompt_budget_report(TASKS[100], demos, resolve_adapters())


def test_the_curriculum_ladder_does_not_fit_the_measured_per_slot_budget():
    """A measured constraint, recorded so it cannot be discovered mid-tournament.

    ``OLLAMA_NUM_PARALLEL=4`` divides 32768 tokens into four 8192-token slots
    (EXECUTION_ENVIRONMENT.md Finding 3), so the longest prompt must be measured against
    8192 and not 32768. On this corpus only the 0- and 5-demonstration curricula fit
    every condition. Candidate D is the binding constraint: the constrained JSON graph
    is roughly 3.4x the size of the linear surfaces for identical content.

    This asserts the *current* state. If a change made a larger curriculum fit, this
    test fails and the constraint is re-examined deliberately rather than assumed away.
    """
    rep = _budget_report()
    assert rep["per_slot_token_budget"] == 8192
    assert rep["largest_curriculum_that_fits_every_condition"] == 5
    per_size = rep["per_size"]
    assert per_size[0]["fits_every_condition"] is True
    assert per_size[5]["fits_every_condition"] is True
    assert per_size[10]["conditions_over_budget"] == ["D_constrained_json_graph"]
    assert per_size[25]["conditions_over_budget"] == ["D_constrained_json_graph"]
    # At 50 demonstrations nothing fits, in any condition.
    assert len(per_size[50]["conditions_over_budget"]) == len(CONDITIONS)


def test_the_json_graph_surface_is_the_binding_size_constraint():
    """Recorded because it biases the tournament and cannot be removed by prompt
    construction: identical content costs candidate D several times what it costs the
    linear surfaces, which raises its token cost and shrinks its usable curriculum."""
    rep = _budget_report()
    rows = {(r["curriculum_size"], r["condition"]): r for r in rep["rows"]
            if not r.get("NOT MEASURED")}
    d = rows[(10, "D_constrained_json_graph")]["characters"]
    a = rows[(10, CANDIDATE_IDS[0])]["characters"]
    assert d > 2.5 * a, (d, a)


def test_a_missing_front_end_refuses_to_render_a_demonstration():
    """Silently substituting another surface would teach the model the wrong syntax and
    the resulting parse rate would be blamed on the candidate."""
    with pytest.raises(RendererUnavailable):
        render_demonstration(TASKS[0], CANDIDATE_IDS[2], {})


def test_zero_shot_prompts_build_for_every_condition_without_any_front_end():
    for condition in CONDITIONS:
        p = build_prompt(TASKS[0], condition, [], {})
        assert p.curriculum_size == 0
        assert len(p.user) > 500


def test_the_control_is_the_only_condition_without_a_formal_encoding():
    for condition in CONDITIONS:
        p = build_prompt(TASKS[0], condition)
        assert p.formal_encoding == (condition != SE_CONTROL)


def test_the_system_prompt_is_identical_across_conditions():
    systems = {build_prompt(TASKS[0], c).system for c in CONDITIONS}
    assert len(systems) == 1


def test_residual_spec_asymmetry_is_measured_not_hidden():
    report = spec_size_report()
    for condition in CONDITIONS:
        assert report[condition]["features_documented"] == len(SHARED_CORE_FEATURES)
        assert report[condition]["sections"] == len(SECTION_ORDER)
    sizes = [report[c]["spec_characters"] for c in CONDITIONS]
    # They genuinely differ; the point is that the difference is reported.
    assert max(sizes) > min(sizes)
    assert all(s > 1000 for s in sizes)


def test_each_specification_names_its_own_fence_tag():
    from evaluation.syntax_gate.candidates import CANDIDATES

    for condition in CANDIDATE_IDS:
        method = build_prompt(TASKS[0], condition).user
        assert CANDIDATES[condition].fence_tags[0] in method


def test_the_specifications_state_the_prohibited_conflations():
    """Every condition must warn about the same conflations, or one condition is being
    given a hint the others lack."""
    for condition in CONDITIONS:
        spec = render_spec(condition).lower()
        assert "standard deviation" in spec
        assert "not a subtype of positivereal" in spec or "not the same kind" in spec
        assert "correlation" in spec
        assert "reciprocal of its mean" in spec or "1 / mean" in spec
