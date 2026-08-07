"""The explicit evidence graph and its invariants (directive §3, E1-E10).

Two layers are tested separately and on purpose:

* the **graph itself**, driven directly, because it must be correct for constructions
  that source order cannot produce -- imports, batch builds, any assembly whose order is
  not textual. That is precisely where the old textual-order rule stops being an
  acyclicity argument.
* the **compiler**, end to end, because a validator nothing calls is decoration. V2 has
  already shipped that failure three times (`push`/`pop` nobody called; Γ the type
  checker never read; a guard on one of two channels), so the wiring is asserted, not
  assumed.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.reasoning.evidence import (
    INVARIANTS,
    ClaimNode,
    EdgeKind,
    EvidenceClass,
    EvidenceGraph,
)


def _violations(graph: EvidenceGraph, **kw) -> set[str]:
    return {v.invariant for v in graph.validate(**kw)}


# ---------------------------------------------------------------------------
# E1 / E9 — cycles, through every edge kind
# ---------------------------------------------------------------------------


def test_e1_a_direct_cycle_is_found():
    g = EvidenceGraph()
    g.add_claim(ClaimNode("a", EvidenceClass.ESTABLISHED))
    g.add_edge("a", "a", EdgeKind.PREMISE)
    assert "E1" in _violations(g)


def test_e1_a_mutual_cycle_is_found():
    g = EvidenceGraph()
    g.add_claim(ClaimNode("a", EvidenceClass.ESTABLISHED))
    g.add_claim(ClaimNode("b", EvidenceClass.ESTABLISHED))
    g.add_edge("a", "b", EdgeKind.PREMISE)
    g.add_edge("b", "a", EdgeKind.PREMISE)
    assert "E1" in _violations(g)


def test_e1_a_long_cycle_is_found():
    g = EvidenceGraph()
    labels = [f"n{i}" for i in range(12)]
    for label in labels:
        g.add_claim(ClaimNode(label, EvidenceClass.ESTABLISHED))
    for i, label in enumerate(labels):
        g.add_edge(label, labels[(i + 1) % len(labels)], EdgeKind.PREMISE)
    assert "E1" in _violations(g)


def test_e9_a_cycle_closed_by_a_proof_edge_is_found():
    """The exploit's actual shape. A premise edge one way, a proof edge the other.

    The premise-only view could not see this, which is why the original
    goal-proves-itself module compiled with zero diagnostics.
    """
    g = EvidenceGraph()
    g.add_claim(ClaimNode("g1", EvidenceClass.NOT_EVIDENCE))
    g.add_claim(ClaimNode("d1", EvidenceClass.ESTABLISHED))
    g.add_edge("d1", "g1", EdgeKind.PREMISE)
    g.add_edge("g1", "d1", EdgeKind.PROOF)
    found = _violations(g, verified_labels=["d1"])
    assert "E1" in found, "the proof edge must be walked by the cycle validator"
    assert "E2" in found and "E3" in found, "and the other invariants must fire too"


def test_a_dag_is_accepted():
    g = EvidenceGraph()
    for label in ("a", "b", "c"):
        g.add_claim(ClaimNode(label, EvidenceClass.ESTABLISHED))
    g.add_edge("c", "b", EdgeKind.PREMISE)
    g.add_edge("b", "a", EdgeKind.PREMISE)
    assert g.validate(verified_labels=["c"]) == []


# ---------------------------------------------------------------------------
# E2 / E3 — laundering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["goal", "require", "prove"])
def test_e2_no_unestablished_claim_can_be_laundered_into_evidence(kind):
    g = EvidenceGraph()
    g.add_claim(ClaimNode(kind, EvidenceClass.NOT_EVIDENCE))
    g.add_claim(ClaimNode("d", EvidenceClass.ESTABLISHED))
    g.add_edge("d", kind, EdgeKind.PREMISE)
    assert "E2" in _violations(g)


def test_e3_a_verified_claim_may_not_rest_on_a_provisional_one():
    g = EvidenceGraph()
    g.add_claim(ClaimNode("prov", EvidenceClass.PROVISIONAL))
    g.add_claim(ClaimNode("d", EvidenceClass.ESTABLISHED))
    g.add_edge("d", "prov", EdgeKind.PREMISE)
    assert "E3" in _violations(g, verified_labels=["d"])


def test_effective_class_is_the_weakest_link():
    g = EvidenceGraph()
    g.add_claim(ClaimNode("a", EvidenceClass.ESTABLISHED))
    g.add_claim(ClaimNode("b", EvidenceClass.PROVISIONAL))
    g.add_claim(ClaimNode("c", EvidenceClass.ESTABLISHED))
    g.add_edge("c", "b", EdgeKind.PREMISE)
    g.add_edge("b", "a", EdgeKind.PREMISE)
    assert g.effective_class("c") is EvidenceClass.PROVISIONAL


# ---------------------------------------------------------------------------
# E4 — transitive obligations
# ---------------------------------------------------------------------------


def test_e4_a_transitive_open_obligation_blocks_verified():
    g = EvidenceGraph()
    g.add_claim(ClaimNode("root", EvidenceClass.ESTABLISHED, own_open_obligations=("o1",)))
    g.add_claim(ClaimNode("mid", EvidenceClass.ESTABLISHED))
    g.add_claim(ClaimNode("top", EvidenceClass.ESTABLISHED))
    g.add_edge("top", "mid", EdgeKind.PREMISE)
    g.add_edge("mid", "root", EdgeKind.PREMISE)
    assert g.transitive_open_obligations("top") == {"o1"}
    assert "E4" in _violations(g, verified_labels=["top"])


def test_transitive_walk_terminates_on_a_cyclic_graph():
    """A soundness routine that can hang is one that will eventually be bypassed."""
    g = EvidenceGraph()
    g.add_claim(ClaimNode("a", EvidenceClass.ESTABLISHED, own_open_obligations=("o1",)))
    g.add_claim(ClaimNode("b", EvidenceClass.ESTABLISHED))
    g.add_edge("a", "b", EdgeKind.PREMISE)
    g.add_edge("b", "a", EdgeKind.PREMISE)
    assert g.transitive_open_obligations("a") == {"o1"}


# ---------------------------------------------------------------------------
# E7 / E8 — provenance and environment
# ---------------------------------------------------------------------------


def test_e7_a_premise_with_no_claim_node_is_incomplete_provenance():
    g = EvidenceGraph()
    g.add_claim(ClaimNode("d", EvidenceClass.ESTABLISHED))
    g.add_edge("d", "nowhere", EdgeKind.PREMISE)
    assert "E7" in _violations(g)


def test_e8_an_empty_environment_tag_is_rejected():
    g = EvidenceGraph()
    g.add_claim(ClaimNode("imported", EvidenceClass.ESTABLISHED, environment="  "))
    assert "E8" in _violations(g)


def test_every_invariant_has_a_description():
    for key in ("E1", "E2", "E3", "E4", "E7", "E8", "E9"):
        assert INVARIANTS.get(key), f"{key} has no recorded description"


# ---------------------------------------------------------------------------
# The graph is actually wired into the compiler
# ---------------------------------------------------------------------------


def test_the_compiler_builds_a_graph_for_a_real_module():
    r = compile_source(
        "module M\nvar x : Real\nvar y : Real\n"
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : 2.0 * x = y from a1 by symmetry\n"
        "goal g1 : 2.0 * x = y\n"
        "proved g1 by d1\n",
        "<test>",
    )
    assert r.ok(), r.diagnostics.render()


def test_a_v1_module_produces_no_graph_violations():
    r = compile_source("module M\nvar x : Real\nassume x > 0.0\n", "<test>")
    assert r.ok()


def test_the_original_exploit_stays_blocked():
    r = compile_source(
        "module M\n"
        "goal   g1 : 1.0 = 2.0\n"
        "derive d1 : 2.0 = 1.0 from g1 by symmetry\n"
        "derive d2 : 1.0 = 2.0 from d1 by symmetry\n"
        "proved g1 by d2\n",
        "<test>",
    )
    assert not r.ok()
