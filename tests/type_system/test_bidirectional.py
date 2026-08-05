"""Explicit synthesise / check paths — HML-COMPILER-CORE-003 item 3.

The checker was synthesis-only (`docs/evaluation/COMPILER_CORE_AUDIT.md` §3): every site
computed a type bottom-up and compared it. That loses the *expectation*, so a failure
could say what a thing was but not what it was being asked to be, nor which role wanted
it. For generated code the expectation is the useful half of the message, because it is
what a repair loop acts on — and one-repair success is a gate metric.

    synthesise(expr)              -> Type         intrinsic, bottom-up
    check(expr, expected, role)   -> CheckedExpr  type-directed, top-down
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.type_system import CheckedExpr


def _first(src: str, code: str):
    r = compile_source(src)
    return next((d for d in r.diagnostics.errors if d.code == code), None)


def test_checked_expr_carries_both_types_and_the_role():
    fields = set(CheckedExpr.__dataclass_fields__)
    assert {"expr", "actual", "expected", "role", "ok"} <= fields


# -- checking mode names the role that imposed the expectation -----------


def test_a_distribution_role_failure_names_the_role():
    d = _first(
        "param m : Real\nparam s : Real\nvar X : RandomVariable[Real]\n"
        "law X ~ Normal(location := m, scale := s)",
        "HML-T413",
    )
    assert d is not None
    assert "'scale' role of Normal" in d.message
    assert d.expected == "PositiveReal" and d.found == "Real"
    assert d.correction == "declare 's : PositiveReal'"


def test_a_declaration_failure_names_the_declared_type():
    d = _first("const a : Natural = -3", "HML-T402")
    assert d is not None
    assert "declared type of 'a'" in d.message
    assert d.expected == "Natural" and d.found == "Integer"
    assert "-3 is not one" in (d.correction or "")


def test_every_checking_failure_carries_expected_found_span_and_correction():
    """The five things the directive requires of a checking failure."""
    for src, code in [
        ("param m : Real\nparam s : Real\nvar X : RandomVariable[Real]\n"
         "law X ~ Normal(location := m, scale := s)", "HML-T413"),
        ("const a : Natural = -3", "HML-T402"),
    ]:
        d = _first(src, code)
        assert d is not None
        assert d.expected, "no expected type"
        assert d.found, "no actual type"
        assert d.line > 0, "no source range"
        assert d.correction, "no correction"
        assert d.message != d.correction, "the correction merely restates the message"


# -- synthesis mode is unchanged where the type is intrinsic -------------


@pytest.mark.parametrize(
    "src",
    [
        "param a : Real\nparam b : Real\ndef f := a + b",
        "param m : Quantity[Mass]\nparam v : Quantity[Length / Time]\ndef e := 0.5 * m * v^2",
        "index N : Natural\nobs x : Matrix[Real, N, N]\nparam b : Vector[Real, N]\ndef y := x @ b",
    ],
)
def test_synthesis_still_types_intrinsic_expressions(src):
    assert compile_source(src).ok()


def test_a_literal_is_checked_by_value_not_by_nominal_type():
    """D-009 survives the refactor: `0.5` inhabits Probability though its nominal type
    (PositiveReal) is not a subtype of it."""
    assert compile_source("const p : Probability = 0.5").ok()
    assert compile_source("const q : Probability = 1").ok()
    assert not compile_source("const r : Probability = 1.5").ok()


def test_the_correction_is_specific_to_what_went_wrong():
    ref = _first(
        "param m : Real\nparam s : Real\nvar X : RandomVariable[Real]\n"
        "law X ~ Normal(location := m, scale := s)", "HML-T413")
    lit = _first("const a : Natural = -3", "HML-T402")
    assert ref.correction != lit.correction, "one generic hint for two different failures"
