"""ACQ0 canonical v2: one authority, every artefact derived.

These tests exist because v1 kept mathematics in three independently authored places —
prose, a `SemanticFacts(...)` repr string, and a private reference — which disagreed. A
frontier model followed the prose, produced a mathematically identical function, and was
scored FAIL. 41 of 41 tasks were inadmissible.

The defect class is structural, so the guard is structural: if any artefact could be
authored separately from the canonical object, the divergence can return.
"""

from __future__ import annotations

import datetime

import pytest
from evaluation.corpus_governance.canonical_v2 import (
    CanonicalAcq0TaskV2,
    DerivedFact,
    Objective,
    Provenance,
    SchemaViolation,
    TaskFamily,
)
from evaluation.corpus_governance.v2_corpus import PROOF_CORPUS
from evaluation.corpus_governance.v2_render import (
    SUPPORTED_SURFACES,
    ViewConfusion,
    acq0_view,
    assert_views_distinct,
    h2_view,
    render_prose,
    render_question,
    render_surface,
)

from hamiltonian_lang import compile_source, content_hash

P = Provenance(author="test", created_utc=datetime.datetime.now(datetime.UTC).isoformat())


def _task(source: str, **kw) -> CanonicalAcq0TaskV2:
    return CanonicalAcq0TaskV2(
        task_id=kw.pop("task_id", "t"), family=kw.pop("family", TaskFamily.BINDING_DEPENDENCY),
        source=source, provenance=P, **kw)


# --- schema invariants ---------------------------------------------------------------

def test_a_const_without_an_initialiser_is_rejected():
    """The v1 `eta` defect: a value only the private reference knew."""
    with pytest.raises(SchemaViolation, match="initialiser"):
        _task("module M\nconst e : Real\nvar d : Real\n")


def test_a_definition_without_a_body_cannot_be_expressed():
    """The v1 `varrho` defect. The compiler rejects it, so the schema never sees it."""
    with pytest.raises(SchemaViolation):
        _task("module M\ndef f(x : Real) : Real\n")


def test_a_goal_without_an_objective_is_rejected():
    """v1 posed a question with `objective=None`, so a model added a `prove` the
    reference lacked and the hashes differed."""
    with pytest.raises(SchemaViolation, match="objective is None"):
        _task("module M\nvar d : Real\nprove d = d\n")


def test_an_objective_without_a_goal_is_rejected():
    with pytest.raises(SchemaViolation, match="states no goal"):
        _task("module M\nvar d : Real\n", objective=Objective("prove", "d equals d"))


def test_a_derived_fact_may_not_also_be_a_premise():
    with pytest.raises(SchemaViolation, match="exactly one category"):
        _task("module M\nvar d : Real\nassume d > 4\n",
              derived_facts=(DerivedFact("d > 4", ("d > 4",)),))


def test_a_derived_fact_must_name_its_premises():
    with pytest.raises(SchemaViolation, match="names no premises"):
        DerivedFact("d != 0", ())


def test_the_authoritative_source_must_compile():
    with pytest.raises(SchemaViolation, match="does not compile"):
        _task("module M\nvar : : :\n")


# --- one authority -------------------------------------------------------------------

@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_the_reference_encoding_is_the_authority_itself(task):
    """Not a copy. A copy is what drifted in v1."""
    assert task.reference_hml() == task.source
    assert content_hash(task.reference_hml()) == task.canonical_hash()


@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_the_structured_target_carries_every_value_and_body(task):
    """v1's target omitted const values and function bodies, so the task was
    unreconstructable from model-visible material."""
    st = task.structured_target()
    for d in st["declarations"]:
        if d["kind"] == "const":
            assert d.get("value"), f"{d['name']} is const with no visible value"
    for f in st["definitions"]:
        assert f["body"], f"{f['name']} has no visible body"
        for b in f["binders"]:
            assert b["type"], f"binder {b['name']} is untyped"


@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_the_prose_names_every_declared_entity(task):
    """No hidden entity: v1 named `eta` in the target and never in the prose."""
    prose = render_prose(task)
    for d in task.structured_target()["declarations"]:
        assert d["name"] in prose, f"{d['name']} is absent from the generated prose"
    for f in task.structured_target()["definitions"]:
        assert f["name"] in prose


@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_a_derived_fact_is_never_stated_as_an_independent_restriction(task):
    prose = render_prose(task)
    for fact in task.derived_facts:
        if fact.state_in_prose:
            assert "consequence, not a further restriction" in prose
        else:
            assert f"It is required that {fact.statement}" not in prose


def test_no_objective_means_no_question_anywhere():
    task = PROOF_CORPUS[0]
    assert task.objective is None
    assert render_question(task) is None
    assert acq0_view(task)["question"] is None
    assert h2_view(task)["question"] is None


def test_an_explicit_goal_renders_exactly_once():
    task = _task("module M\nvar d : Real\nprove d = d\n",
                 objective=Objective("prove", "d equals itself"))
    question = render_question(task)
    assert question and question.count("Prove") == 1


# --- surfaces ------------------------------------------------------------------------

@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
@pytest.mark.parametrize("surface", SUPPORTED_SURFACES)
def test_every_surface_round_trips_to_the_same_canonical_object(task, surface):
    from evaluation.syntax_gate.candidates import resolve_adapters

    adapter = resolve_adapters()[surface]
    assert adapter is not None, f"{surface} unavailable: NOT MEASURED, never assumed clean"
    outcome = adapter.parse(render_surface(task, surface))
    assert outcome.ok, f"{surface} rejected its own rendering: {outcome.diagnostics}"
    assert content_hash(outcome.hml_l1) == task.canonical_hash()


# --- canonical identity sensitivity ---------------------------------------------------

@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("module M\ndef p : Proposition := forall x : Real . x = x\n",
         "module M\ndef p : Proposition := forall z : Real . z = z\n"),
        ("module M\nconst e : Real = 5\ndef f(mu : Real) : Real := e / mu\n",
         "module M\nconst e : Real = 5\ndef f(nu : Real) : Real := e / nu\n"),
    ],
)
def test_alpha_renaming_preserves_identity(a: str, b: str):
    assert content_hash(a) == content_hash(b)


@pytest.mark.parametrize(
    ("a", "b", "what"),
    [
        ("module M\nconst e : Real = 5\n", "module M\nconst e : Real = 7\n", "literal"),
        ("module M\nparam t : Probability\nprior t ~ Beta(alpha := 2, beta := 5)\n",
         "module M\nparam t : Probability\nprior t ~ Beta(alpha := 5, beta := 2)\n", "role"),
        ("module M\ndef p : Proposition := forall x : Real . exists y : Real . y > x\n",
         "module M\ndef p : Proposition := exists y : Real . forall x : Real . y > x\n",
         "quantifier order"),
        ("module M\nvar p : Bool\nvar q : Bool\ndef i : Proposition := p implies q\n",
         "module M\nvar p : Bool\nvar q : Bool\ndef i : Proposition := q implies p\n",
         "implication direction"),
        ("module M\nconst e : Real = 5\ndef f(m : Real) : Real := e / m\n",
         "module M\nconst e : Real = 5\ndef f(m : Real) : Real := e * m\n", "body"),
    ],
)
def test_changing_the_mathematics_changes_the_identity(a: str, b: str, what: str):
    assert content_hash(a) != content_hash(b), f"{what} change did not alter the hash"


# --- view separation ------------------------------------------------------------------

@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_acq0_and_h2_views_cannot_be_confused(task):
    assert_views_distinct(acq0_view(task), h2_view(task))


@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_the_h2_view_leaks_neither_target_nor_encoding(task):
    view = h2_view(task)
    assert view["structured_target"] is None
    assert view["reference_encoding"] is None
    assert task.source not in str(view)
    assert task.canonical_hash() not in str(view)


def test_an_h2_view_carrying_a_target_is_refused():
    """The guard must fire, not merely be documented."""
    task = PROOF_CORPUS[0]
    poisoned = dict(h2_view(task), structured_target=task.structured_target())
    with pytest.raises(ViewConfusion, match="answer-key exposure"):
        assert_views_distinct(acq0_view(task), poisoned)


def test_an_acq0_view_carrying_a_question_is_refused():
    task = PROOF_CORPUS[0]
    poisoned = dict(acq0_view(task), question="Is d = 4 admissible?")
    with pytest.raises(ViewConfusion, match="invent a goal"):
        assert_views_distinct(poisoned, h2_view(task))


# --- reference self-score --------------------------------------------------------------

@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_the_reference_self_scores_pass(task):
    """A task whose own reference does not score PASS cannot score anything else."""
    result = compile_source(task.source, f"<{task.task_id}>")
    assert result.ok(), [d.code for d in result.diagnostics.errors]


def test_the_proof_corpus_has_one_task_per_family():
    families = [t.family for t in PROOF_CORPUS]
    assert len(PROOF_CORPUS) == 8
    assert len(set(families)) == 8


def test_v2_ids_do_not_collide_with_the_quarantined_v1_corpus():
    """v1 ids stay quarantined with their evidence; v2 must not reuse one."""
    for task in PROOF_CORPUS:
        assert task.task_id.startswith("v2_")
