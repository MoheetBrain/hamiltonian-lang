"""The admission gate: reconstruct from the model-visible view alone.

Three earlier checks all validated an artefact against itself and so could not see the
defect that mattered:

* `check_prose_coverage` and `reconstruct_semantic_payload` both derive from
  `structured_target()` and re-read its own keys;
* the 32/32 surface round-trip renders from `task.source` and never touches the view.

The loss lived exactly between `structured_target()` and the source, which none of them
crossed. Three of eight tasks were unencodable because statement order is part of
`content_hash` and the view carried unordered kind-buckets; a fourth dropped a
`check dimension` statement entirely.

The gate here is the one that would have caught all four before any model call, and every
negative test below is a defect that actually occurred or a near neighbour of one.
"""

from __future__ import annotations

import copy

import pytest
from evaluation.corpus_governance.v2_corpus import PROOF_CORPUS
from evaluation.corpus_governance.v2_render import acq0_view, render_prose
from evaluation.corpus_governance.v2_view import (
    ViewIncomplete,
    encoding_view,
    reconstruct_source,
    view_reconstructs_exactly,
)

from hamiltonian_lang import compile_source, content_hash

# --- the gate -------------------------------------------------------------------------

@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_the_view_alone_reconstructs_the_reference_exactly(task):
    ok, detail = view_reconstructs_exactly(task)
    assert ok, detail


@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_every_emitted_source_statement_appears_exactly_once(task):
    """No drop, no duplicate. The dimension check was a silent drop."""
    from hamiltonian_lang.ast.nodes import ModuleDecl

    expected = [s for s in task.module.statements if not isinstance(s, ModuleDecl)]
    records = encoding_view(task)["encoding_statements"]
    assert len(records) == len(expected), (
        f"view carries {len(records)} statements for {len(expected)} in the source")
    positions = sorted(r["position"] for r in records)
    assert positions == list(range(1, len(expected) + 1))


@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_prose_order_equals_encoding_order(task):
    """Prose walked kind-buckets, so its order diverged from the answer's order."""
    prose_lines = render_prose(task).splitlines()
    emitted = [r for r in encoding_view(task)["encoding_statements"] if r["emit"]]
    assert len(prose_lines) >= len(emitted)
    for i, record in enumerate(emitted):
        line = prose_lines[i]
        subject = record.get("name") or record.get("target") or record.get("expression") \
            or record.get("subject") or ""
        token = str(subject).split()[0] if subject else ""
        if token:
            assert token in line, (
                f"prose line {i} does not correspond to statement {record['position']}: "
                f"{line!r}")


# --- negative tests: the gate must FAIL on a broken view ------------------------------

def _view_of(index: int = 7) -> dict:
    return copy.deepcopy(encoding_view(PROOF_CORPUS[index]))


def _rebuild_hash(view: dict) -> str:
    return content_hash(reconstruct_source(view))


def test_a_removed_statement_changes_the_reconstruction():
    task = PROOF_CORPUS[7]
    view = _view_of(7)
    view["encoding_statements"] = view["encoding_statements"][:-1]
    for i, r in enumerate(view["encoding_statements"], 1):
        r["position"] = i
    assert _rebuild_hash(view) != task.canonical_hash()


def test_changed_statement_order_changes_the_reconstruction():
    """The defect itself: `require` before `assume` is a different module."""
    task = PROOF_CORPUS[7]
    view = _view_of(7)
    a, b = view["encoding_statements"][-2], view["encoding_statements"][-1]
    a["position"], b["position"] = b["position"], a["position"]
    assert _rebuild_hash(view) != task.canonical_hash()


def test_a_missing_initialiser_is_refused_not_defaulted():
    view = _view_of(0)
    for r in view["encoding_statements"]:
        r.pop("value", None)
    with pytest.raises(ViewIncomplete, match="cannot invent"):
        reconstruct_source(view)


def test_a_missing_definition_body_is_refused():
    view = _view_of(0)
    for r in view["encoding_statements"]:
        if r["kind"] == "def":
            r["body"] = ""
    with pytest.raises(ViewIncomplete, match="body"):
        reconstruct_source(view)


def test_a_missing_codomain_is_refused():
    """Annotated and unannotated definitions canonicalise differently."""
    view = _view_of(0)
    for r in view["encoding_statements"]:
        if r["kind"] == "def":
            r["codomain"] = None
    with pytest.raises(ViewIncomplete, match="codomain"):
        reconstruct_source(view)


def test_a_missing_dimension_check_changes_the_reconstruction():
    task = next(t for t in PROOF_CORPUS if "dimensional" in t.task_id)
    view = copy.deepcopy(encoding_view(task))
    kept = [r for r in view["encoding_statements"] if not r["kind"].startswith("check_")]
    assert len(kept) < len(view["encoding_statements"]), "the task has no check statement"
    for i, r in enumerate(kept, 1):
        r["position"] = i
    view["encoding_statements"] = kept
    assert _rebuild_hash(view) != task.canonical_hash()


def test_swapping_assume_and_require_roles_changes_the_reconstruction():
    task = PROOF_CORPUS[7]
    view = _view_of(7)
    for r in view["encoding_statements"]:
        if r["kind"] == "assume":
            r["kind"] = "require"
        elif r["kind"] == "require":
            r["kind"] = "assume"
    assert _rebuild_hash(view) != task.canonical_hash()


def test_emitting_a_derived_fact_changes_the_reconstruction():
    """`emit=false` metadata must not become a statement."""
    task = next(t for t in PROOF_CORPUS if t.derived_facts)
    view = copy.deepcopy(encoding_view(task))
    n = len(view["encoding_statements"])
    view["encoding_statements"].append({
        "position": n + 1, "statement_id": f"s{n + 1}", "emit": True,
        "kind": "require", "expression": view["derived_facts"][0]["expression"]})
    assert _rebuild_hash(view) != task.canonical_hash()


def test_an_invented_goal_changes_the_reconstruction():
    task = PROOF_CORPUS[0]
    view = _view_of(0)
    n = len(view["encoding_statements"])
    view["encoding_statements"].append({
        "position": n + 1, "statement_id": f"s{n + 1}", "emit": True,
        "kind": "prove", "expression": "delta > 0"})
    assert _rebuild_hash(view) != task.canonical_hash()


# --- emission policy ------------------------------------------------------------------

@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_non_emitted_metadata_carries_an_explicit_emit_flag(task):
    view = encoding_view(task)
    for record in view["derived_facts"] + view["prohibited_assumptions"]:
        assert record["emit"] is False
    assert "emit=false" in view["emission_rule"]


@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_the_model_facing_view_is_the_ordered_one(task):
    """Kind-buckets are never handed to a model again."""
    target = acq0_view(task)["structured_target"]
    assert "encoding_statements" in target
    assert "declarations" not in target


def test_reconstruction_reads_nothing_but_the_view():
    """A view detached from its task still reconstructs -- proof of no back-channel."""
    task = PROOF_CORPUS[5]
    view = copy.deepcopy(encoding_view(task))
    rebuilt = reconstruct_source(view)
    assert compile_source(rebuilt).ok()
    assert content_hash(rebuilt) == task.canonical_hash()
