"""Rational dimension exponents and constrained dimension variables.

Two measured gaps from `docs/evaluation/COMPILER_CORE_AUDIT.md` §5: `Dimension` has always
stored `Fraction` exponents, but the *parser* split on `/` before reading the exponent, so
`Quantity[Length^1/2]` was a parse error. A benchmark case had to be deleted because of it.
Dimension variables did not exist at all.

The variable syntax is deliberately constrained to a single capital letter. If any
unrecognised identifier could be a variable, `Quantity[Lenght]` would silently become one
instead of erroring — reintroducing the unknown-name hole that `HML-T440` closes for
ordinary types. That property is tested here, not assumed.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.types import BASE_DIMENSIONS, Dimension, is_dimension_variable


def _dim(src: str):
    r = compile_source(src)
    assert r.ok(), r.diagnostics.render()
    st = next(s for s in r.module.statements if getattr(s, "declared_type", None))
    return st.declared_type.dimension


@pytest.mark.parametrize(
    "src,expect",
    [
        ("param q : Quantity[Length^1/2]", {"Length": Fraction(1, 2)}),
        ("param q : Quantity[Mass^1/2 * Length]", {"Mass": Fraction(1, 2), "Length": Fraction(1)}),
        ("param q : Quantity[Time^-1/2]", {"Time": Fraction(-1, 2)}),
        ("param q : Quantity[Length^3/2]", {"Length": Fraction(3, 2)}),
        ("param q : Quantity[Length^2]", {"Length": Fraction(2)}),
    ],
)
def test_rational_exponents_parse(src, expect):
    assert _dim(src).as_dict() == expect


@pytest.mark.parametrize(
    "src,expect",
    [
        ("param v : Quantity[Length / Time]", {"Length": Fraction(1), "Time": Fraction(-1)}),
        ("param a : Quantity[Length^2 / Time^2]", {"Length": Fraction(2), "Time": Fraction(-2)}),
        ("param p : Quantity[Mass / (Length * Time^2)]",
         {"Mass": Fraction(1), "Length": Fraction(-1), "Time": Fraction(-2)}),
    ],
)
def test_division_is_still_division(src, expect):
    """`/` before a NUMBER is a fractional exponent; before an identifier it is division."""
    assert _dim(src).as_dict() == expect


def test_sqrt_of_an_area_is_a_length():
    assert _dim("param q : Quantity[Length^2]").power(Fraction(1, 2)) == Dimension.of(Length=1)


# -- dimension variables -------------------------------------------------


def test_a_single_capital_is_a_dimension_variable():
    d = _dim("param x : Quantity[D]")
    assert not d.is_concrete()
    assert d.free_variables() == {"D"}


def test_a_variable_is_not_dimensionless():
    """An unknown dimension must never be silently treated as scalar."""
    assert not _dim("param x : Quantity[D]").is_dimensionless()


def test_variables_compose_with_base_dimensions():
    d = _dim("param x : Quantity[D * Mass]")
    assert d.as_dict() == {"Mass": Fraction(1)}
    assert d.variables_dict() == {"D": Fraction(1)}


def test_variable_powers():
    assert _dim("param x : Quantity[D^2]").variables_dict() == {"D": Fraction(2)}


@pytest.mark.parametrize("typo", ["Lenght", "Mas", "Tim", "Frobnicator", "Length2"])
def test_a_multi_letter_unknown_is_an_error_not_a_variable(typo):
    """The load-bearing constraint: a typo must not become a variable."""
    r = compile_source(f"param x : Quantity[{typo}]")
    assert not r.ok(), f"{typo} was silently accepted as a dimension variable"
    assert "HML-D501" in [d.code for d in r.diagnostics.errors]


@pytest.mark.parametrize("name", list(BASE_DIMENSIONS))
def test_base_dimensions_are_never_variables(name):
    assert not is_dimension_variable(name)


def test_unification_solves_a_single_variable():
    solved = Dimension.variable("D").unify(Dimension.of(Mass=1, Length=2))
    assert solved is not None
    assert solved["D"] == Dimension.of(Mass=1, Length=2)


def test_unification_refuses_two_concrete_mismatches():
    assert Dimension.of(Mass=1).unify(Dimension.of(Length=1)) is None


def test_zero_denominator_is_rejected():
    r = compile_source("param x : Quantity[Length^1/0]")
    assert not r.ok()
    assert "HML-P227" in [d.code for d in r.diagnostics.errors]


def test_dimensional_arithmetic_still_rejects_incompatible_addition():
    r = compile_source(
        "param m : Quantity[Mass]\nparam l : Quantity[Length]\ndef bad := m + l"
    )
    assert not r.ok()
    assert "HML-D502" in [d.code for d in r.diagnostics.errors]
