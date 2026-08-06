"""The frozen taxonomy must stay covered, and the whole corpus must stay admissible.

Losing a cell is silent: the suite still passes, the corpus still compiles, and the
experiment simply stops measuring a feature. These tests make it loud.
"""

from __future__ import annotations

import pytest
from evaluation.corpus_governance.taxonomy import (
    CELLS,
    COVERAGE_RULES,
    TASK_CELLS,
    coverage_report,
)
from evaluation.corpus_governance.v2_corpus import PROOF_CORPUS, SEALED_SPARES

REPORT = coverage_report(PROOF_CORPUS)


def test_the_corpus_is_twelve_plus_two():
    assert len(PROOF_CORPUS) == 12
    assert len(SEALED_SPARES) == 2


def test_every_cell_has_a_carrier():
    assert REPORT["uncovered"] == [], (
        f"cells with no carrier: {REPORT['uncovered']} — the screen would silently stop "
        f"measuring them")


@pytest.mark.parametrize(("label", "need"), COVERAGE_RULES)
def test_each_coverage_rule_is_met(label: str, need: int):
    actual = REPORT["counts"][label]
    assert actual >= need, f"{label}: {actual} < {need}"


def test_both_state_in_prose_values_occur():
    """A flag exercised in one direction only is an untested branch of the prose layer."""
    assert REPORT["both_state_in_prose_values"]


def test_every_task_is_placed_in_the_taxonomy():
    """An unplaced task is one nobody decided the purpose of."""
    assert REPORT["unknown_tasks"] == []
    for task in (*PROOF_CORPUS, *SEALED_SPARES):
        assert TASK_CELLS[task.task_id], f"{task.task_id} carries no cell"


def test_the_fragile_cells_are_exactly_the_ones_documented():
    """Cells 9 and 10 are backed by a spare; 4 and 8 are single-carrier by admission.

    Pinned so that a corpus change which makes a *different* cell fragile fails here
    rather than passing quietly.
    """
    assert sorted(REPORT["single_carrier"]) == [4, 8, 9, 10]


def test_cell_numbers_are_one_to_twelve_without_gaps():
    assert [c.number for c in CELLS] == list(range(1, 13))


def test_every_referenced_cell_exists():
    known = {c.number for c in CELLS}
    for task_id, cells in TASK_CELLS.items():
        assert set(cells) <= known, f"{task_id} references an unknown cell"


# --- the whole corpus, including spares, stays admissible -----------------------------

@pytest.mark.parametrize("task", [*PROOF_CORPUS, *SEALED_SPARES],
                         ids=lambda t: t.task_id)
def test_every_task_reconstructs_from_its_view_alone(task):
    from evaluation.corpus_governance.v2_view import view_reconstructs_exactly

    ok, detail = view_reconstructs_exactly(task)
    assert ok, detail


@pytest.mark.parametrize("task", [*PROOF_CORPUS, *SEALED_SPARES],
                         ids=lambda t: t.task_id)
def test_every_task_passes_the_partiality_scanner(task):
    from evaluation.corpus_governance.partiality import scan_module

    report = scan_module(task.module, task.task_id)
    assert report.admissible, report.render()


@pytest.mark.parametrize("task", [*PROOF_CORPUS, *SEALED_SPARES],
                         ids=lambda t: t.task_id)
def test_every_task_round_trips_through_all_four_surfaces(task):
    from evaluation.corpus_governance.v2_render import SUPPORTED_SURFACES, render_surface
    from evaluation.syntax_gate.candidates import resolve_adapters

    from hamiltonian_lang import content_hash

    adapters = resolve_adapters()
    for surface in SUPPORTED_SURFACES:
        outcome = adapters[surface].parse(render_surface(task, surface))
        assert outcome.ok, f"{surface} rejected its own rendering"
        assert content_hash(outcome.hml_l1) == task.canonical_hash(), surface


@pytest.mark.parametrize("task", [*PROOF_CORPUS, *SEALED_SPARES],
                         ids=lambda t: t.task_id)
def test_every_task_has_exact_prose_coverage(task):
    from evaluation.corpus_governance.v2_facts import check_prose_coverage

    coverage = check_prose_coverage(task)
    assert coverage.exact, coverage.render()


def test_a_spare_is_never_also_a_development_task():
    """A spare that is already scored cannot replace anything without contaminating it."""
    assert not ({t.task_id for t in PROOF_CORPUS}
                & {t.task_id for t in SEALED_SPARES})


# --- regressions from the second independent semantic review --------------------------
#
# All three findings were generator defects on the four objective-bearing tasks, which are
# ALL among the six authored after the first review -- the earlier eight have
# `objective=None`, so the first review could not have seen them.

@pytest.mark.parametrize(
    "task", [t for t in [*PROOF_CORPUS, *SEALED_SPARES] if t.objective is not None],
    ids=lambda t: t.task_id)
def test_the_objective_does_not_read_as_a_second_statement(task):
    """The prose said "The goal is to prove X." beside "The goal is to prove that `X`."

    One word apart, separated by other sentences, and the duplicate reading COMPILED to a
    different hash. The objective sentence must now describe the listed statement and
    forbid a second.
    """
    from evaluation.corpus_governance.v2_render import render_prose

    prose = render_prose(task)
    assert "already listed above" in prose
    assert "do not emit a second statement" in prose
    assert prose.count("The goal is to") <= 1


@pytest.mark.parametrize("task", [*PROOF_CORPUS, *SEALED_SPARES], ids=lambda t: t.task_id)
def test_the_objective_carries_an_explicit_emit_flag(task):
    """It was the one model-visible field with no disposition at all."""
    from evaluation.corpus_governance.v2_view import encoding_view

    view = encoding_view(task)
    if view["objective"] is not None:
        assert view["objective"]["emit"] is False
    assert "the objective" in view["emission_rule"]


@pytest.mark.parametrize("task", [*PROOF_CORPUS, *SEALED_SPARES], ids=lambda t: t.task_id)
def test_prose_states_every_clause_the_coverage_check_scores(task):
    """`render_prose` filtered the objective clause; coverage counted it anyway.

    The gate walked `prose_clauses` while the model read `render_prose`, so two tasks were
    certified EXACT for a fact their prose did not state.
    """
    from evaluation.corpus_governance.v2_facts import prose_clauses
    from evaluation.corpus_governance.v2_render import render_prose

    prose = render_prose(task)
    for clause in prose_clauses(task):
        assert clause.text in prose, f"{clause.clause_id} is scored but never shown"


@pytest.mark.parametrize("task", [*PROOF_CORPUS, *SEALED_SPARES], ids=lambda t: t.task_id)
def test_no_derived_fact_provenance_is_a_line_of_the_answer(task):
    """`("param lambda : PositiveReal",)` reached prose verbatim — one surface-A line."""
    lines = {line.strip() for line in task.source.splitlines() if line.strip()}
    for fact in task.derived_facts:
        for origin in fact.derived_from:
            assert origin.strip() not in lines, (
                f"{task.task_id}: provenance {origin!r} is a verbatim answer line")


def test_the_provenance_guard_fires_at_construction():
    from evaluation.corpus_governance.canonical_v2 import (
        CanonicalAcq0TaskV2,
        DerivedFact,
        Provenance,
        SchemaViolation,
        TaskFamily,
    )

    with pytest.raises(SchemaViolation, match="verbatim line of the answer"):
        CanonicalAcq0TaskV2(
            task_id="t", family=TaskFamily.BINDING_DEPENDENCY,
            provenance=Provenance(author="t", created_utc="2026-01-01T00:00:00+00:00"),
            source="module M\nvar d : PositiveReal\n",
            derived_facts=(DerivedFact("d != 0", ("var d : PositiveReal",)),))


@pytest.mark.parametrize(
    "task", [t for t in [*PROOF_CORPUS, *SEALED_SPARES] if t.objective is not None],
    ids=lambda t: t.task_id)
def test_the_rendered_question_has_no_doubled_conjunction(task):
    """"Decide whether" + a statement beginning "whether" gave "Decide whether whether"."""
    from evaluation.corpus_governance.v2_render import render_question

    question = render_question(task)
    assert question
    assert "whether whether" not in question
    assert "whether that" not in question


@pytest.mark.parametrize("task", [*PROOF_CORPUS, *SEALED_SPARES], ids=lambda t: t.task_id)
def test_no_single_reference_line_leaks_into_the_bundle(task):
    """Whole-rendering containment cannot see one leaked statement."""
    from evaluation.corpus_governance.v2_bundle import build_bundle

    for surface in ("A_v0_labelled_linear", "B_v1_labelled_linear_simplified",
                    "C_prefix_sexpr", "D_constrained_json_graph"):
        build_bundle(task, surface)  # raises BundleLeak on any leak


def test_the_per_line_leak_scan_fires_on_a_planted_line():
    """A leak check that cannot fail reports safety. This proves this one can."""
    import evaluation.corpus_governance.v2_bundle as mod
    from evaluation.corpus_governance.v2_render import render_surface

    task = PROOF_CORPUS[0]
    planted = render_surface(task, "A_v0_labelled_linear").splitlines()[1]
    original = mod.render_prose
    mod.render_prose = lambda t: f"{original(t)}\nfor example {planted}"
    try:
        with pytest.raises(mod.BundleLeak, match="a line of the task's own"):
            mod.build_bundle(task, "B_v1_labelled_linear_simplified")
    finally:
        mod.render_prose = original


def test_the_v2_corpus_is_contamination_checked_against_every_shown_split():
    """The v2 corpus had never been run through the contamination gate at all.

    `acq0_splits()` enumerates only the v1 pools, and nothing checked `PROOF_CORPUS`
    against them. Recorded honestly: this catches textual near-duplication, and would NOT
    have caught the case that mattered — a previously-shown item reproduced structurally
    with one term deleted scores ~0.04 against a 0.60 threshold. The independent semantic
    review caught that one; this is the cheaper net underneath it.
    """
    from evaluation.corpus_governance.contamination import (
        ContentFields,
        acq0_splits,
        check_contamination,
        fingerprint,
    )
    from evaluation.corpus_governance.v2_render import render_prose

    def extract(task):
        return task.task_id, ContentFields(
            specification=render_prose(task), question="", answer="",
            reference=task.source)

    candidate = fingerprint("acq0::v2_development",
                            (*PROOF_CORPUS, *SEALED_SPARES), extract)
    report = check_contamination(candidate, acq0_splits())
    assert not report.collisions, [c.to_dict() for c in report.collisions]
