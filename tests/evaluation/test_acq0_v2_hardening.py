"""Hardening regressions for canonical v2, from the human-review audit.

Three defects were found in the v2 architecture itself and are pinned here.

1. **Semantic metadata sat outside canonical identity.** `derived_facts` and
   `prohibited_assumptions` reach model-visible prose, yet two tasks differing only in them
   shared a canonical hash. Fixed by distinguishing the identity of the *encoding*
   (`canonical_hash`) from the identity of the *task* (`semantic_identity`).

2. **An unguarded partial definition was admitted.** `def varrho(mu : Real) := eta / mu`
   declares totality over `Real` while being undefined at zero. The obligation engine
   returns VERIFIED for it -- it generates no definedness obligation over a binder's
   declared domain -- so the corpus had to reject it. This project's own proof task carried
   the defect and was narrowed to `PositiveReal`.

3. **`state_in_prose` needed a disposition.** It changes prose and therefore the task, but
   must not change the structured target ACQ0 scores.
"""

from __future__ import annotations

import dataclasses

import pytest
from evaluation.corpus_governance.canonical_v2 import (
    CanonicalAcq0TaskV2,
    DerivedFact,
    Provenance,
    SchemaViolation,
    TaskFamily,
)
from evaluation.corpus_governance.v2_corpus import PROOF_CORPUS
from evaluation.corpus_governance.v2_render import render_prose

P = Provenance(author="test", created_utc="2026-01-01T00:00:00+00:00")
BASE = "module M\nvar d : Real\nassume d > 4\n"


def _task(**kw) -> CanonicalAcq0TaskV2:
    return CanonicalAcq0TaskV2(
        task_id=kw.pop("task_id", "t"),
        family=kw.pop("family", TaskFamily.BINDING_DEPENDENCY),
        source=kw.pop("source", BASE),
        provenance=kw.pop("provenance", P), **kw)


# --- B: the authority definition -------------------------------------------------------

def test_every_field_is_classified():
    """An unclassified field is one nobody decided the identity rules for."""
    classes = CanonicalAcq0TaskV2.FIELD_CLASSIFICATION
    declared = {f.name for f in dataclasses.fields(CanonicalAcq0TaskV2)
                if not f.name.startswith("_")}
    assert declared == set(classes), f"unclassified: {declared ^ set(classes)}"
    assert set(classes.values()) <= {"SEMANTIC", "PRESENTATION_ONLY", "OPERATIONAL_ONLY"}


@pytest.mark.parametrize(
    ("label", "kwargs"),
    [
        ("prohibited_assumptions", {"prohibited_assumptions": ("that d is an integer",)}),
        ("derived_facts", {"derived_facts": (DerivedFact("d != 0", ("d > 4",)),)}),
        ("family", {"family": TaskFamily.QUANTIFIER_SCOPE}),
    ],
)
def test_semantic_metadata_participates_in_task_identity(label: str, kwargs: dict):
    """The audit defect: these changed model-visible prose under one canonical hash."""
    assert _task().semantic_identity() != _task(**kwargs).semantic_identity(), label


@pytest.mark.parametrize(
    ("label", "kwargs"),
    [("task_id", {"task_id": "other"}), ("notes", {"notes": "different"}),
     ("provenance", {"provenance": Provenance(author="z", created_utc="2027-01-01T00:00:00+00:00")})],
)
def test_operational_fields_change_neither_identity(label: str, kwargs: dict):
    a, b = _task(), _task(**kwargs)
    assert a.canonical_hash() == b.canonical_hash(), label
    assert a.semantic_identity() == b.semantic_identity(), label


def test_metadata_must_not_enter_the_encoding_identity():
    """`canonical_hash` scores a model's ENCODING.

    A model is asked to encode mathematics, not to restate a prohibition, so metadata must
    stay out of the hash it is scored against. Keeping the two identities separate is the
    fix -- collapsing them would be a different bug, not a stronger one.
    """
    plain = _task()
    with_meta = _task(prohibited_assumptions=("that d is an integer",))
    assert plain.canonical_hash() == with_meta.canonical_hash()


# --- D: state_in_prose -----------------------------------------------------------------

def test_state_in_prose_changes_prose_but_never_the_structured_target():
    """It must not hide a fact ACQ0 scores. The structured target is what ACQ0 scores."""
    task = next(t for t in PROOF_CORPUS if t.derived_facts)
    flipped = dataclasses.replace(task, derived_facts=tuple(
        dataclasses.replace(f, state_in_prose=not f.state_in_prose)
        for f in task.derived_facts))
    assert task.structured_target() == flipped.structured_target()
    assert render_prose(task) != render_prose(flipped)
    assert task.canonical_hash() == flipped.canonical_hash()
    assert task.semantic_identity() != flipped.semantic_identity()


def test_a_derived_fact_is_never_in_the_source_so_acq0_cannot_score_it():
    """The invariant: no fact ACQ0 scores may be absent from the model-visible target."""
    for task in PROOF_CORPUS:
        for fact in task.derived_facts:
            assert fact.statement not in task.source, (
                f"{task.task_id}: {fact.statement!r} is both a derived fact and part of "
                f"the scored encoding")


# --- E: partiality ---------------------------------------------------------------------

def test_an_unguarded_partial_definition_is_rejected():
    """`eta / mu` with `mu : Real` is undefined at zero.

    The obligation engine returns VERIFIED for this -- it generates no definedness
    obligation over a binder's declared domain -- so admission must reject it.
    """
    with pytest.raises(SchemaViolation, match="admits zero"):
        _task(source="module M\nconst e : Real = 5\ndef f(mu : Real) : Real := e / mu\n")


def test_the_same_definition_with_a_total_domain_is_admitted():
    task = _task(source=(
        "module M\nconst e : Real = 5\ndef f(mu : PositiveReal) : Real := e / mu\n"))
    assert task.canonical_hash()


def test_a_definition_with_no_partial_operation_is_untouched():
    """The guard must not fire on total bodies, or it would reject valid tasks."""
    assert _task(source=(
        "module M\nconst e : Real = 5\ndef f(mu : Real) : Real := e * mu\n")).canonical_hash()


def test_the_corpus_contains_no_unguarded_partial_definition():
    """Every proof task is re-validated at import; this states the property directly."""
    assert len(PROOF_CORPUS) == 8


def test_a_definedness_fact_is_not_silently_promoted_to_a_premise():
    """`mu != 0` must not be quietly added to the source as an assumption."""
    for task in PROOF_CORPUS:
        for fact in task.derived_facts:
            assert f"assume {fact.statement}" not in task.source
