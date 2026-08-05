"""Tier 2 -- the three decision procedures, and the boundaries of each.

The propositional half is the delicate one. Validity over free atoms is sound for
*any* reading of those atoms, so the positive direction always holds. A satisfying
model is only a refutation when the atoms are genuinely independent, which is why
``x > 0`` against ``x > -1`` must come out inconclusive rather than refuted.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import DefineStmt, ProveStmt, RequireStmt
from hamiltonian_lang.equivalence import (
    EquivalenceStatus,
    TranslationContext,
    align,
    collect_declared_types,
    compare_expressions,
)


def _module(source: str):
    result = compile_source(source)
    assert result.ok(), result.diagnostics.render()
    return result.module


def _expr(source: str):
    module = _module(source)
    for st in module.statements:
        if isinstance(st, DefineStmt):
            return module, st.body
        if isinstance(st, (RequireStmt, ProveStmt)):
            return module, st.proposition
    raise AssertionError("no expression in source")


def compare(left_src: str, right_src: str):
    left_module, left = _expr(left_src)
    right_module, right = _expr(right_src)
    alignment = align(left_module, right_module)
    ctx = TranslationContext(
        left_types=collect_declared_types(left_module),
        right_types=collect_declared_types(right_module),
        pairing=dict(alignment.env.bwd),
    )
    return compare_expressions(left, right, ctx)


HEAD = "module M\nparam a : Real\nparam b : Real\nparam x : Real\n"
POS = "module M\nparam a : PositiveReal\nparam x : Real\n"
BOOL = "module M\nparam p : Bool\nparam q : Bool\n"


# -- difference-is-zero -----------------------------------------------------


@pytest.mark.parametrize(
    "left,right",
    [
        ("(a + 1) * (a + 1)", "a^2 + 2 * a + 1"),
        ("a^2 - 1", "(a - 1) * (a + 1)"),
        ("2 * 3 * x", "6 * x"),
        ("a - a", "b - b"),
        ("0.5 * a", "a / 2"),
    ],
)
def test_algebraic_identities_are_certified(left, right):
    result = compare(f"{HEAD}def f := {left}\n", f"{HEAD}def f := {right}\n")
    assert result.status is EquivalenceStatus.VERIFIED_EQUIVALENT
    assert result.certificate is not None
    assert result.certificate.certifies_equivalence


@pytest.mark.parametrize(
    "left,right",
    [
        ("a^2", "2 * a"),
        ("a - b", "b - a"),
        ("a * b", "a / b"),
    ],
)
def test_non_identities_are_not_certified(left, right):
    result = compare(f"{HEAD}def f := {left}\n", f"{HEAD}def f := {right}\n")
    assert result.status is not EquivalenceStatus.VERIFIED_EQUIVALENT


def test_exponent_association_is_not_certified():
    head = "module M\nparam a : PositiveReal\nparam b : Real\nparam c : Real\n"
    result = compare(f"{head}def f := (a^b)^c\n", f"{head}def f := a^(b^c)\n")
    assert result.status is not EquivalenceStatus.VERIFIED_EQUIVALENT


def test_a_symbolic_denominator_is_recorded_as_an_assumption():
    result = compare(f"{HEAD}def f := a / a\n", f"{HEAD}def f := b / b\n")
    if result.status is EquivalenceStatus.VERIFIED_EQUIVALENT:
        statements = [x.statement for x in result.assumptions]
        assert any("denominator" in s for s in statements), (
            "certifying x/x == 1 without recording the nonzero-denominator condition "
            "would be an equivalence that is false at zero"
        )


# -- relation proportionality -----------------------------------------------


@pytest.mark.parametrize(
    "left,right",
    [
        ("x + 1 < 3", "x < 2"),
        ("2 * x < 4", "x < 2"),
        ("-x < -2", "x > 2"),
        ("2 * x = 6", "x = 3"),
        ("3 * x >= 9", "x >= 3"),
    ],
)
def test_equivalent_relations_are_certified(left, right):
    result = compare(f"{HEAD}require {left}\n", f"{HEAD}require {right}\n")
    assert result.status is EquivalenceStatus.VERIFIED_EQUIVALENT


def test_strictness_is_never_traded_away():
    result = compare(f"{HEAD}require x < 2\n", f"{HEAD}require x <= 2\n")
    assert result.status is not EquivalenceStatus.VERIFIED_EQUIVALENT


def test_a_sign_assumption_is_used_and_recorded():
    result = compare(f"{POS}require a * x < 6\n", f"{POS}require x < 6 / a\n")
    assert result.status is EquivalenceStatus.VERIFIED_EQUIVALENT
    statements = " ".join(x.statement for x in result.assumptions)
    assert ">" in statements, "the positivity of a is load-bearing and must be recorded"


def test_an_unknown_sign_blocks_the_inequality_rewrite():
    result = compare(f"{HEAD}require a * x < 6\n", f"{HEAD}require x < 6 / a\n")
    assert result.status is EquivalenceStatus.INCONCLUSIVE
    assert "sign" in result.detail


# -- propositional ----------------------------------------------------------


@pytest.mark.parametrize(
    "left,right",
    [
        ("p => q", "(not q) => (not p)"),
        ("not (p and q)", "(not p) or (not q)"),
        ("not (not p)", "p"),
        ("p and q", "q and p"),
        ("p iff q", "q iff p"),
    ],
)
def test_propositional_tautologies_are_certified(left, right):
    result = compare(f"{BOOL}prove {left}\n", f"{BOOL}prove {right}\n")
    assert result.status is EquivalenceStatus.VERIFIED_EQUIVALENT
    assert result.certificate is not None
    assert result.certificate.method == "tier2.propositional_tautology"


@pytest.mark.parametrize("left,right", [("p => q", "q => p"), ("p and q", "p or q")])
def test_a_countermodel_over_free_atoms_refutes(left, right):
    result = compare(f"{BOOL}prove {left}\n", f"{BOOL}prove {right}\n")
    assert result.status is EquivalenceStatus.VERIFIED_NONEQUIVALENT
    assert result.proof is not None
    assert result.proof.method == "tier2.propositional_countermodel"


def test_a_countermodel_over_dependent_atoms_refutes_nothing():
    """``x > 0`` and ``x > -1`` are not independent, so a model may not exist."""
    left = "module M\nparam x : Real\nparam p : Bool\nprove (x > 0) => p\n"
    right = "module M\nparam x : Real\nparam p : Bool\nprove (x > -1) => p\n"
    result = compare(left, right)
    assert result.status is EquivalenceStatus.INCONCLUSIVE
    assert "does not exist" in result.detail or "comparison" in result.detail


# -- refusals ---------------------------------------------------------------


def test_a_quantifier_is_refused_rather_than_approximated():
    left = "module M\nprove forall x : Real . x = x\n"
    right = "module M\nprove forall x : Real . x + 0 = x\n"
    result = compare(left, right)
    assert result.status in (
        EquivalenceStatus.SEMANTIC_LOSS,
        EquivalenceStatus.INCONCLUSIVE,
    )
    assert result.status is not EquivalenceStatus.VERIFIED_NONEQUIVALENT


def test_comparing_a_proposition_with_a_magnitude_is_not_well_posed():
    left = "module M\nparam x : Real\nparam p : Bool\nprove p\n"
    right = "module M\nparam x : Real\nparam p : Bool\ndef f := x\n"
    result = compare(left, right)
    assert result.status is EquivalenceStatus.INCONCLUSIVE
