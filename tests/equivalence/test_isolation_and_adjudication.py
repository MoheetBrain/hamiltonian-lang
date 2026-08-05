"""Two things that must stay true: ACQ0 is untouched, and nothing is silently dropped.

CONF-003 rules that exact hash comparison is *correct for ACQ0*. This package
therefore adds a second scorer rather than changing the first one, and the import
graph is the mechanical check that it did.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from hamiltonian_lang.equivalence import (
    AdjudicationItem,
    AdjudicationQueue,
    EquivalenceStatus,
)

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "hamiltonian_lang" / "equivalence"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("path", sorted(PACKAGE.glob("*.py")), ids=lambda p: p.name)
def test_the_equivalence_package_never_reaches_into_acq0_or_the_old_verifier(path):
    """A new scorer that edits the old one is not a new scorer."""
    forbidden = ("evaluation", "syntax_gate", "improvement")
    for name in _imports(path):
        assert not any(name.startswith(f) or f".{f}" in name for f in forbidden), (
            f"{path.name} imports {name}; the equivalence engine must stand alone so "
            f"ACQ0's exact-preservation scoring keeps working unchanged"
        )


def test_the_package_exposes_one_entry_point_and_the_statuses():
    from hamiltonian_lang import equivalence

    for name in (
        "EquivalenceScorer",
        "Endpoint",
        "EquivalenceStatus",
        "AnswerSpec",
        "NEGATIVE_STATUSES",
    ):
        assert name in equivalence.__all__


# -- the adjudication queue --------------------------------------------------


def test_the_queue_keeps_order_and_serialises():
    queue = AdjudicationQueue()
    queue.add(
        AdjudicationItem("a", EquivalenceStatus.INCONCLUSIVE, "no tier decided it")
    )
    queue.add(
        AdjudicationItem("b", EquivalenceStatus.SEMANTIC_LOSS, "quantifier dropped")
    )
    assert len(queue) == 2
    assert [i.item_id for i in queue] == ["a", "b"]
    assert len(queue.by_status(EquivalenceStatus.INCONCLUSIVE)) == 1
    payload = queue.to_dict()
    assert payload["count"] == 2
    assert payload["items"][0]["item_id"] == "a"


def test_the_queue_writes_json(tmp_path):
    queue = AdjudicationQueue.from_items(
        [AdjudicationItem("x", EquivalenceStatus.INCONCLUSIVE, "undecided")]
    )
    target = queue.write_json(tmp_path / "nested" / "queue.json")
    assert target.exists()
    assert '"item_id": "x"' in target.read_text()
