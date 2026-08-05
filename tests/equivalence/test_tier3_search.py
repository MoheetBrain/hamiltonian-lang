"""Tier 3 -- what a search may conclude, and what it may never conclude.

A witness disproves. Its absence proves nothing. These tests pin both halves,
including the one that is easy to get wrong: the searcher must not manufacture a
counterexample out of a point the declared types exclude, or out of a value where
the expression is undefined.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.equivalence import (
    Counterexample,
    NoRefutation,
    search_disagreement,
    varies_with,
)
from hamiltonian_lang.equivalence.search import (
    SEED,
    domain_for,
    evaluate,
    harvest_hints,
    sample_assignments,
)
from hamiltonian_lang.types import Dimension, QuantityType, ScalarType

# sympy is an optional dependency: guarded so a clean clone skips rather than errors.
sympy = pytest.importorskip("sympy", reason="Tier 3 evaluates SymPy expressions")


def sym(name: str, **kw):
    return sympy.Symbol(name, **kw)


def test_a_disagreement_is_reported_as_a_counterexample():
    a, b, c = sym("a", positive=True), sym("b", real=True), sym("c", real=True)
    left = sympy.Pow(sympy.Pow(a, b), c)
    right = sympy.Pow(a, sympy.Pow(b, c))
    outcome = search_disagreement(
        left,
        right,
        {"a": a, "b": b, "c": c},
        {"a": ScalarType("PositiveReal"), "b": ScalarType("Real"), "c": ScalarType("Real")},
    )
    assert isinstance(outcome, Counterexample)
    assert outcome.method == "tier3.numeric_counterexample"
    assert outcome.assignment


def test_no_disagreement_returns_a_different_class_entirely():
    x = sym("x", real=True)
    outcome = search_disagreement(
        x + x, 2 * x, {"x": x}, {"x": ScalarType("Real")}
    )
    assert isinstance(outcome, NoRefutation)
    assert not isinstance(outcome, Counterexample)
    assert outcome.certifies_equivalence is False
    assert "not evidence of equivalence" in outcome.detail


def test_samples_stay_inside_the_declared_domain():
    values = domain_for(ScalarType("Probability"))
    assert values and all(0 <= float(v) <= 1 for v in values)
    assert all(float(v) > 0 for v in domain_for(ScalarType("PositiveReal")))
    assert all(float(v) >= 0 for v in domain_for(ScalarType("Natural")))
    assert all(float(v) == int(v) for v in domain_for(ScalarType("Integer")))


def test_a_dimensioned_quantity_samples_over_its_base_scalar():
    t = QuantityType(Dimension.of(Mass=1), ScalarType("PositiveReal"))
    assert all(float(v) > 0 for v in domain_for(t))


def test_assumptions_exclude_samples_rather_than_being_ignored():
    x = sym("x", real=True)
    # |x| and x agree only where x >= 0; the assumption makes them agree everywhere.
    outcome = search_disagreement(
        sympy.Abs(x),
        x,
        {"x": x},
        {"x": ScalarType("Real")},
        constraints=[sympy.Ge(x, 0)],
    )
    assert isinstance(outcome, NoRefutation)
    unconstrained = search_disagreement(
        sympy.Abs(x), x, {"x": x}, {"x": ScalarType("Real")}
    )
    assert isinstance(unconstrained, Counterexample)


def test_an_undefined_point_is_skipped_not_counted_as_disagreement():
    x = sym("x", real=True)
    assert evaluate(1 / x, {x: sympy.Integer(0)}) is None
    assert evaluate(sympy.sqrt(x), {x: sympy.Integer(-4)}) is None
    assert evaluate(x + 1, {x: sympy.Integer(2)}) == 3


def test_sampling_is_deterministic():
    x, y = sym("x", real=True), sym("y", real=True)
    types = {"x": ScalarType("Real"), "y": ScalarType("Real")}
    first = sample_assignments(types, {"x": x, "y": y}, budget=20)
    second = sample_assignments(types, {"x": x, "y": y}, budget=20)
    assert [sorted(map(str, a.items())) for a in first] == [
        sorted(map(str, a.items())) for a in second
    ]
    assert SEED == 20260805


def test_hints_are_harvested_from_the_expressions_and_filtered_by_type():
    x = sym("x", real=True)
    hints = harvest_hints(
        [sympy.Eq(2 * x, 6), sympy.Eq(x, 6)], {"x": x}, {"x": ScalarType("Real")}
    )
    assert 3 in [float(v) for v in hints["x"]]
    # A probability may not be handed a hint of 6.
    p = sym("p", nonnegative=True)
    bounded = harvest_hints(
        [sympy.Eq(p, 6)], {"p": p}, {"p": ScalarType("Probability")}
    )
    assert all(0 <= float(v) <= 1 for v in bounded.get("p", []))


def test_equation_pairs_are_separated_by_the_harvested_solutions():
    x = sym("x", real=True)
    outcome = search_disagreement(
        sympy.Eq(2 * x, 6), sympy.Eq(x, 6), {"x": x}, {"x": ScalarType("Real")}
    )
    assert isinstance(outcome, Counterexample)


# -- dependence witnesses ---------------------------------------------------


def test_a_dependence_witness_is_found_when_the_body_really_depends():
    x, y = sym("x", real=True), sym("y", real=True)
    body = sympy.Gt(y, x)
    types = {"x": ScalarType("Real"), "y": ScalarType("Real")}
    assert varies_with(body, x, {"x": x, "y": y}, types) is not None
    assert varies_with(body, y, {"x": x, "y": y}, types) is not None


def test_no_dependence_witness_when_the_binder_does_not_matter():
    x, y = sym("x", real=True), sym("y", real=True)
    body = sympy.Gt(x, x - 1)  # always true, independent of both
    types = {"x": ScalarType("Real"), "y": ScalarType("Real")}
    assert varies_with(body, y, {"x": x, "y": y}, types) is None
