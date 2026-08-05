"""Tier 1 -- what binder-safe normalisation does, and what it refuses to do.

The refusals matter more than the acceptances: every operator this tier declines
to reorder is one that a permissive matcher would silently flatten into a false
positive.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.equivalence import align, skeleton, strict_match


def mod(source: str):
    result = compile_source(source)
    assert result.ok(), result.diagnostics.render()
    return result.module


def matched(a: str, b: str) -> bool:
    return strict_match(mod(a), mod(b)) is not None


# -- accepted normalisations ------------------------------------------------


def test_alpha_renaming_is_invisible():
    assert matched(
        "module A\nparam a : Real\ndef f := a + 1\n",
        "module B\nparam z : Real\ndef g := z + 1\n",
    )


def test_the_module_name_is_a_label():
    assert matched("module A\nparam a : Real\n", "module Totally\nparam a : Real\n")


def test_declaration_order_is_not_semantic():
    assert matched(
        "module M\nparam a : Real\nparam b : Real\ndef f := a - b\n",
        "module M\nparam b : Real\nparam a : Real\ndef f := a - b\n",
    )


@pytest.mark.parametrize(
    "left,right",
    [
        ("a + b", "b + a"),
        ("a * b", "b * a"),
        ("(a + b) + c", "a + (b + c)"),
        ("(a * b) * c", "a * (b * c)"),
        ("a + b + c", "c + b + a"),
    ],
)
def test_associative_and_commutative_regrouping(left, right):
    head = "module M\nparam a : Real\nparam b : Real\nparam c : Real\ndef f := "
    assert matched(head + left + "\n", head + right + "\n")


@pytest.mark.parametrize("op", ["and", "or", "iff"])
def test_symmetric_logical_operators_reorder(op):
    head = "module M\nparam p : Bool\nparam q : Bool\nprove "
    assert matched(f"{head}p {op} q\n", f"{head}q {op} p\n")


@pytest.mark.parametrize("op", ["=", "!="])
def test_symmetric_relations_reorder(op):
    head = "module M\nparam a : Real\nparam b : Real\nrequire "
    assert matched(f"{head}a {op} b\n", f"{head}b {op} a\n")


# -- refusals ---------------------------------------------------------------


def test_exponentiation_is_not_associative():
    head = "module M\nparam a : PositiveReal\nparam b : Real\nparam c : Real\ndef f := "
    assert not matched(head + "(a^b)^c\n", head + "a^(b^c)\n")


def test_implication_is_not_symmetric():
    head = "module M\nparam p : Bool\nparam q : Bool\nprove "
    assert not matched(head + "p => q\n", head + "q => p\n")


@pytest.mark.parametrize("op", ["-", "/"])
def test_non_commutative_arithmetic_is_not_reordered(op):
    head = "module M\nparam a : PositiveReal\nparam b : PositiveReal\ndef f := "
    assert not matched(f"{head}a {op} b\n", f"{head}b {op} a\n")


@pytest.mark.parametrize("op", ["<", "<=", ">", ">="])
def test_ordering_relations_are_not_reordered(op):
    head = "module M\nparam a : Real\nparam b : Real\nrequire "
    assert not matched(f"{head}a {op} b\n", f"{head}b {op} a\n")


def test_quantifier_alternation_is_not_reordered():
    assert not matched(
        "module M\nprove forall x : Real . exists y : Real . y > x\n",
        "module M\nprove exists y : Real . forall x : Real . y > x\n",
    )


def test_two_universals_do_commute():
    assert matched(
        "module M\nprove forall x : Real . forall y : Real . x + y = y + x\n",
        "module M\nprove forall y : Real . forall x : Real . x + y = y + x\n",
    )


def test_a_shared_vocabulary_locks_module_level_names():
    """A candidate reusing the reference's names is using them as identities.

    Without the lock, ``prove p => q`` and ``prove q => p`` are alpha-variants of
    one another -- swap the two anonymous booleans -- and Tier 1 would certify the
    pair the directive names as adversarial.
    """
    head = "module M\nparam p : Bool\nparam q : Bool\nprove "
    assert not matched(head + "p => q\n", head + "q => p\n")
    # Different vocabulary: free renaming is restored.
    assert matched(
        head + "p => q\n",
        "module M\nparam r : Bool\nparam s : Bool\nprove r => s\n",
    )


# -- skeletons and alignment ------------------------------------------------


def test_skeletons_are_renaming_invariant_but_operator_sensitive():
    a = mod("module M\nparam a : Real\nparam b : Real\ndef f := a - b\n")
    b = mod("module M\nparam x : Real\nparam y : Real\ndef g := x - y\n")
    c = mod("module M\nparam a : Real\nparam b : Real\ndef f := a / b\n")
    assert skeleton(a.statements[3]) == skeleton(b.statements[3])
    assert skeleton(a.statements[3]) != skeleton(c.statements[3])


def test_alignment_pairs_by_name_before_guessing():
    left = mod("module M\nparam alpha : Real\nparam beta : Real\ndef f := alpha - beta\n")
    right = mod("module M\nparam beta : Real\nparam alpha : Real\ndef f := alpha - beta\n")
    alignment = align(left, right)
    assert alignment.complete
    assert all(p.confidence in ("name", "exact_key") for p in alignment.pairings)


def test_a_residual_inside_a_matched_expression_is_marked_a_fragment():
    left = mod("module M\nrv y : Real\nlaw y ~ Normal(location := 0, scale := 1)\n")
    right = mod("module M\nrv y : Real\nlaw y ~ Normal(location := 1, scale := 1)\n")
    alignment = align(left, right)
    assert alignment.residuals
    assert all(r.fragment for r in alignment.residuals)
    assert all(not r.may_refute for r in alignment.residuals)
