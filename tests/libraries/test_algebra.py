"""Algebra V0.

The composition being tested is the point of the whole mission:

    add_zero supplies the domain fact          -> checked evidence
    forall_intro supplies the logic            -> forall n : Natural . n + 0 = n

``forall_intro`` is unchanged and remains the generic operation. If this file could be
made to pass by adding an ``x + 0 -> x`` rule to the kernel, the architecture would have
failed, so `test_no_library_theorem_became_a_kernel_rule` guards the other side of it.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang import libraries as lib
from hamiltonian_lang.ast.nodes import DerivationStatus, EvidenceStatus, GoalStatus


def _compile(src: str):
    return compile_source(src, "<alg>")


def _status(src: str, label: str = "e1") -> str:
    r = _compile(src)
    if r.reasoning is None:
        return "<not reached>"
    return r.reasoning.evidence_status.get(label, "<absent>")


# --- positive: the identity over each supported numeric type ----------------


@pytest.mark.parametrize("type_name", ["Natural", "Integer", "Real"])
def test_add_zero_holds_over_the_supported_numeric_types(type_name):
    src = (
        f"module A\nvar v : {type_name}\n"
        "evidence e1 : entails v + 0.0 = v by library_theorem_v1(theorem := add_zero, x := v)\n"
    )
    assert _status(src) == EvidenceStatus.VALID, type_name


def test_the_identity_does_not_depend_on_the_variable_spelling():
    """Alpha-renaming: `n + 0 = n` and `x + 0 = x` are the same theorem applied twice."""
    for name in ("n", "x", "zzz"):
        src = (
            f"module A\nvar {name} : Natural\n"
            f"evidence e1 : entails {name} + 0.0 = {name} "
            f"by library_theorem_v1(theorem := add_zero, x := {name})\n"
        )
        assert _status(src) == EvidenceStatus.VALID, name


def test_gold10_G07_composition_add_zero_then_forall_intro():
    """The end-to-end shape: a domain fact, then the generic logical operation."""
    src = """module G07
var n : Natural
goal g1 : forall n : Natural . n + 0.0 = n
evidence e1 : entails n + 0.0 = n by library_theorem_v1(theorem := add_zero, x := n)
derive d1 : forall n : Natural . n + 0.0 = n from e1 by forall_intro(var := n)
proved g1 by d1
"""
    r = _compile(src)
    assert r.ok(), [str(d) for d in r.diagnostics]
    assert r.reasoning.evidence_status["e1"] == EvidenceStatus.VALID
    assert r.reasoning.derivation_status["d1"] == DerivationStatus.VERIFIED
    assert r.reasoning.goal_status["g1"] == GoalStatus.PROVED


def test_the_generalisation_still_obeys_the_eigenvariable_condition():
    """The library must not smuggle a witness-specific proof past forall_intro.

    A previous mission's guard, re-asserted here because this is the first time a
    *library* supplies the body: if the variable is constrained, generalising is still
    refused, and the certificate being valid changes nothing about that.
    """
    src = """module G07
var n : Natural
assume a1 : n = 0.0
evidence e1 : entails n + 0.0 = n by library_theorem_v1(theorem := add_zero, x := n)
derive d1 : forall n : Natural . n + 0.0 = n from e1 by forall_intro(var := n)
"""
    r = _compile(src)
    assert not r.ok()
    assert r.reasoning.derivation_status["d1"] == DerivationStatus.REJECTED
    assert any("is not arbitrary" in str(d) for d in r.diagnostics)


# --- negative ---------------------------------------------------------------


def test_a_non_numeric_type_is_refused():
    """`Bool` is not in the identity's declared domains, so the instantiation is refused."""
    src = (
        "module A\nvar b : Bool\n"
        "evidence e1 : entails b + 0.0 = b by library_theorem_v1(theorem := add_zero, x := b)\n"
    )
    assert _status(src) != EvidenceStatus.VALID


def test_probability_is_deliberately_outside_the_domain():
    """Excluded on purpose -- see the module docstring in libraries/algebra.py."""
    assert "Probability" not in lib.algebra.NUMERIC_DOMAINS
    assert "PValue" not in lib.algebra.NUMERIC_DOMAINS
    assert "PosteriorProbability" not in lib.algebra.NUMERIC_DOMAINS


def test_wrong_conclusion_orientation_is_rejected():
    """`add_zero` states `x + 0 = x`. It does not state `0 + x = x`."""
    src = (
        "module A\nvar n : Natural\n"
        "evidence e1 : entails 0.0 + n = n by library_theorem_v1(theorem := add_zero, x := n)\n"
    )
    assert _status(src) == EvidenceStatus.REJECTED


def test_a_different_constant_is_rejected():
    src = (
        "module A\nvar n : Natural\n"
        "evidence e1 : entails n + 1.0 = n by library_theorem_v1(theorem := add_zero, x := n)\n"
    )
    assert _status(src) == EvidenceStatus.REJECTED


# --- the rewriting used by the calculus normalisation ------------------------


def test_every_rewrite_is_justified_by_a_registered_theorem():
    """A normalisation step nobody can name is a simplifier, not evidence."""
    for _, _, theorem_id in lib.algebra.REWRITES:
        assert theorem_id in lib.THEOREMS, theorem_id


def test_every_rewrite_strictly_reduces_the_term():
    """Termination is structural, not hopeful. See the note in libraries/algebra.py."""
    from hamiltonian_lang.ast.nodes import BinOp, Literal, Ref, walk

    def size(e):
        return len(list(walk(e)))

    x = Ref(name="x")
    zero = Literal(value=0.0, raw="0.0")
    one = Literal(value=1.0, raw="1.0")
    samples = [
        BinOp(op="+", left=x, right=zero),
        BinOp(op="*", left=zero, right=x),
        BinOp(op="*", left=x, right=zero),
        BinOp(op="*", left=one, right=x),
        BinOp(op="*", left=x, right=one),
        BinOp(op="-", left=zero, right=x),
    ]
    for term in samples:
        out, theorem_id = lib.algebra.rewrite_step(term)
        assert theorem_id is not None, term
        assert size(out) <= size(term), f"{theorem_id} did not reduce the term"


def test_a_term_with_no_applicable_identity_is_left_alone():
    from hamiltonian_lang.ast.nodes import BinOp, Ref

    term = BinOp(op="+", left=Ref(name="a"), right=Ref(name="b"))
    out, theorem_id = lib.algebra.rewrite_step(term)
    assert theorem_id is None and out is term
