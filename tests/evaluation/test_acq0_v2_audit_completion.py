"""Audit sections C, F, H, I: coverage, reversibility, bundle seal, firewall.

Each section found a real defect in v2 when first executed:

* **F** rejected `v2_dimensional_algebra_001`, whose `def pressure := force / area` had no
  declared codomain. An annotated and an unannotated definition hash *differently*, so the
  model-visible `codomain: None` left an encoder unable to know which spelling was meant --
  the v1 ambiguity class, in this project's own replacement corpus.
* **0** found `state_in_prose` inside `semantic_identity`, making the field classification
  self-contradictory.
"""

from __future__ import annotations

import dataclasses

import pytest
from evaluation.corpus_governance.canonical_v2 import (
    CanonicalAcq0TaskV2,
    Provenance,
    SchemaViolation,
    TaskFamily,
)
from evaluation.corpus_governance.v2_bundle import (
    ALLOWED_PARTS,
    BundleLeak,
    build_bundle,
)
from evaluation.corpus_governance.v2_corpus import PROOF_CORPUS
from evaluation.corpus_governance.v2_facts import (
    ReversibilityFailure,
    check_prose_coverage,
    reconstruct_semantic_payload,
    required_public_facts,
    semantic_payload,
)
from evaluation.corpus_governance.v2_firewall import (
    CrossModeAccess,
    Mode,
    acq0_semantic_diff,
    in_mode,
)
from evaluation.corpus_governance.v2_view import encoding_view

P = Provenance(author="test", created_utc="2026-01-01T00:00:00+00:00")


# --- 0: state_in_prose is PRESENTATION_ONLY and behaves like it -------------------------

def test_state_in_prose_does_not_alter_task_identity():
    """It changes prose only. A PRESENTATION_ONLY field altering identity was the
    inconsistency this section existed to resolve."""
    task = next(t for t in PROOF_CORPUS if t.derived_facts)
    flipped = dataclasses.replace(task, derived_facts=tuple(
        dataclasses.replace(f, state_in_prose=not f.state_in_prose)
        for f in task.derived_facts))
    assert task.semantic_identity() == flipped.semantic_identity()
    assert task.canonical_hash() == flipped.canonical_hash()
    assert encoding_view(task) == encoding_view(flipped)


def test_the_derived_fact_itself_is_semantic():
    """Changing what follows from what must change identity, even though the flag does not."""
    from evaluation.corpus_governance.canonical_v2 import DerivedFact
    task = next(t for t in PROOF_CORPUS if t.derived_facts)
    altered = dataclasses.replace(
        task, derived_facts=(DerivedFact("digamma != 1", ("digamma > 4",)),))
    assert task.semantic_identity() != altered.semantic_identity()


# --- C: prose exact coverage -----------------------------------------------------------

@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_prose_coverage_is_exact(task):
    coverage = check_prose_coverage(task)
    assert coverage.exact, coverage.render()


@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_every_required_fact_class_is_covered(task):
    """Initialisers and binder order are separate facts: prose can drop either while
    keeping the name, which is what v1 did."""
    ids = {f.fact_id for f in required_public_facts(task)}
    for r in encoding_view(task)["encoding_statements"]:
        sid = r["statement_id"]
        assert f"{sid}.kind" in ids and f"{sid}.position" in ids
        if "value" in r:
            assert f"{sid}.value" in ids
        if r["kind"] == "def":
            assert f"{sid}.body" in ids
            for j in range(len(r["binders"])):
                assert f"{sid}.binder{j}" in ids
        if r["kind"].startswith("check_"):
            # The class the bucketed fact layer had no branch for at all.
            assert f"{sid}.subject" in ids and f"{sid}.expected" in ids
    assert "module" in ids, "the module name is part of the content hash"
    assert "objective" in ids, "absence of a goal is itself a fact"


def test_an_unmapped_clause_fails_coverage():
    """A clause carrying no fact id is an invented fact. The check must catch it."""
    from evaluation.corpus_governance.v2_facts import Clause, ProseCoverage
    bad = ProseCoverage("t", frozenset({"a"}), frozenset({"a"}), ("c.invented",))
    assert not bad.exact
    assert "unmapped" in bad.render()
    assert Clause("c", "text", (), "ACQ0_TRANSLATION").fact_ids == ()


# --- F: reversibility ------------------------------------------------------------------

@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_the_structured_target_reconstructs_the_semantic_payload(task):
    """Weak by construction — both sides derive from the view, so this detects a missing
    KEY and never a missing statement. `view_reconstructs_exactly` is the real gate."""
    assert reconstruct_semantic_payload(encoding_view(task)) == semantic_payload(task)


@pytest.mark.parametrize(
    "field",
    ["module", "family", "encoding_statements", "objective", "derived_facts",
     "prohibited_assumptions"],
)
def test_removing_any_semantic_field_breaks_reconstruction(field: str):
    target = dict(encoding_view(PROOF_CORPUS[1]))
    target.pop(field)
    with pytest.raises(ReversibilityFailure):
        reconstruct_semantic_payload(target)


def test_a_const_without_a_visible_value_breaks_reconstruction():
    """The v1 `eta` defect, caught at the reconstruction boundary that can see it.

    `reconstruct_semantic_payload` cannot: it copies keys. `reconstruct_source` refuses,
    because it must produce a compilable module and an initialiser cannot be invented.
    """
    from evaluation.corpus_governance.v2_view import ViewIncomplete, reconstruct_source

    target = dict(encoding_view(PROOF_CORPUS[1]))
    target["encoding_statements"] = [
        {k: v for k, v in r.items() if k != "value"}
        for r in target["encoding_statements"]]
    with pytest.raises(ViewIncomplete, match="invent"):
        reconstruct_source(target)


def test_a_definition_without_a_codomain_is_rejected_at_construction():
    """An annotated and an unannotated definition hash differently, so `codomain: None`
    is unreconstructable. Found by section F in this project's own dimensional task."""
    with pytest.raises(SchemaViolation, match="codomain"):
        CanonicalAcq0TaskV2(
            task_id="t", family=TaskFamily.DIMENSIONAL_ALGEBRA, provenance=P,
            source="module M\nvar a : Real\nvar b : Real\ndef q := a + b\n")


# --- H: bundle seal --------------------------------------------------------------------

def test_a_safe_bundle_carries_only_allowed_parts():
    bundle = build_bundle(PROOF_CORPUS[1], "B_v1_labelled_linear_simplified",
                          PROOF_CORPUS[2:5])
    assert set(bundle.parts) <= set(ALLOWED_PARTS)
    assert bundle.bundle_hash and len(bundle.bundle_hash) == 64


def test_the_bundle_carries_no_expected_hash_or_reference():
    task = PROOF_CORPUS[1]
    bundle = build_bundle(task, "B_v1_labelled_linear_simplified")
    blob = str(bundle.parts)
    assert task.canonical_hash() not in blob
    assert task.semantic_identity() not in blob
    assert task.source.strip() not in blob


def test_a_bundle_carrying_the_reference_is_refused():
    """The guard must fire, not merely be documented."""
    import evaluation.corpus_governance.v2_bundle as mod

    task = PROOF_CORPUS[1]
    original = mod.render_surface
    mod.render_surface = lambda t, s: task.source  # force the reference into a demo
    try:
        with pytest.raises(BundleLeak):
            build_bundle(task, "B_v1_labelled_linear_simplified", (task,))
    finally:
        mod.render_surface = original


# --- I: firewall -----------------------------------------------------------------------

def test_acq0_may_take_a_semantic_diff():
    task = PROOF_CORPUS[0]
    assert acq0_semantic_diff(task, task.source)["equal"] is True


@pytest.mark.parametrize("mode", [Mode.H2, Mode.H3])
def test_a_reasoning_mode_cannot_take_an_acq0_semantic_diff(mode: Mode):
    """H2 scored against one intended encoding would penalise any other valid derivation;
    H3 fed by it would be transcription, not repair."""
    task = PROOF_CORPUS[0]
    with in_mode(mode), pytest.raises(CrossModeAccess, match="independent answer oracle"):
        acq0_semantic_diff(task, task.source)


def test_the_mode_gate_restores_itself():
    from evaluation.corpus_governance.v2_firewall import current_mode

    assert current_mode() is Mode.ACQ0
    with in_mode(Mode.H2):
        assert current_mode() is Mode.H2
    assert current_mode() is Mode.ACQ0
