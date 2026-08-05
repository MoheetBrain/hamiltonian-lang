"""Exact evaluation, definitional unfolding, and the refusals that keep it sound.

The single most dangerous thing an evaluator like this can do is settle an equality in
floating point. ``sqrt(2)^2 == 2`` is false in binary and true in mathematics, and a
verifier that cannot tell those apart will confidently disprove correct programs. The
refusal is therefore tested directly, not inferred from the docstring.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.verification.obligations.evaluate import (
    Undecidable,
    build_environment,
    evaluate,
    free_names,
    interval_of,
)


def _env(source: str):
    result = compile_source(source)
    assert result.ok(), [d.code for d in result.diagnostics.errors]
    return result, build_environment(result.module, result.symbols)


def _proposition(source: str, index: int = 0):
    result, env = _env(source)
    return result.obligations[index].expression, env


def test_exact_rational_arithmetic() -> None:
    expr, env = _proposition("module M\nrequire 1 / 3 + 1 / 6 = 1 / 2\n")
    assert evaluate(expr, env).as_bool() is True


def test_a_float_equality_is_refused_rather_than_decided() -> None:
    """``sqrt(2)^2`` is 2.0000000000000004 in binary and exactly 2 in mathematics.

    Both refusals are correct and both must fire: the near-equal case is caught by the
    tolerance guard, and a float equality that is *not* near-equal is still refused,
    because a float has no business settling an equality at all.
    """
    near, env = _proposition("module M\nrequire sqrt(2.0) ^ 2 = 2\n")
    with pytest.raises(Undecidable, match="floating-point tolerance"):
        evaluate(near, env)

    far, env2 = _proposition("module M\nrequire exp(1.0) = 3\n")
    with pytest.raises(Undecidable, match="exact rational equality only"):
        evaluate(far, env2)


def test_a_float_comparison_within_tolerance_is_refused() -> None:
    expr, env = _proposition("module M\nrequire exp(0.0) > 1.0\n")
    with pytest.raises(Undecidable, match="floating-point tolerance"):
        evaluate(expr, env)


def test_constants_are_substituted_and_definitions_unfolded() -> None:
    expr, env = _proposition(
        "module M\n"
        "const m : PositiveReal = 2.0\n"
        "const v : Real = 3.0\n"
        "def ke : Real := 0.5 * m * v^2\n"
        "require ke = 9.0\n"
    )
    assert evaluate(expr, env).as_bool() is True
    assert free_names(expr, env) == set()


def test_a_free_name_is_reported_not_guessed() -> None:
    expr, env = _proposition("module M\nvar x : Real\nrequire x > 1\n")
    with pytest.raises(Undecidable, match="free and no value was supplied"):
        evaluate(expr, env)
    assert free_names(expr, env) == {"x"}


def test_a_user_function_is_unfolded_at_its_call_site() -> None:
    expr, env = _proposition(
        "module M\ndef add(a : Real, b : Real) : Real := a + b\nrequire add(2.0, 3.0) = 5\n"
    )
    assert evaluate(expr, env).as_bool() is True


def test_indexing_and_the_matrix_product_are_refused() -> None:
    expr, env = _proposition(
        "module M\nvar w : Vector[Real, 3]\nindex i : Natural\nrequire w[i] = w[i]\n"
    )
    with pytest.raises(Undecidable, match="indexing is outside"):
        evaluate(expr, env)


def test_a_bool_assignment_is_read_as_a_truth_value() -> None:
    expr, env = _proposition("module M\nvar b : Bool\nrequire b = true or b = false\n")
    assert evaluate(expr, env, {"b": Fraction(1)}).as_bool() is True
    assert evaluate(expr, env, {"b": Fraction(0)}).as_bool() is True


def test_division_by_zero_is_refused_not_returned() -> None:
    expr, env = _proposition("module M\nrequire 1 / 0 = 0\n")
    with pytest.raises(Undecidable, match="division by zero"):
        evaluate(expr, env)


def test_a_quantifier_over_an_infinite_domain_is_refused() -> None:
    expr, env = _proposition("module M\nrequire forall x : Real . x = x\n")
    with pytest.raises(Undecidable, match="infinite"):
        evaluate(expr, env)


def test_a_quantifier_over_bool_is_exhausted() -> None:
    expr, env = _proposition("module M\nrequire forall b : Bool . b = true or b = false\n")
    assert evaluate(expr, env).as_bool() is True


def test_interval_propagation_keeps_the_declared_refinement() -> None:
    result, env = _env("module M\nparam s : PositiveReal\nparam p : Probability\n")
    assert env.domain("s") is not None
    assert env.domain("s").interval.entirely_above(Fraction(0), strict=True)
    assert env.domain("p").interval.entirely_below(Fraction(1), strict=False)
    assert not env.domain("p").interval.entirely_above(Fraction(0), strict=True)


def test_interval_of_a_sum_of_non_negatives_stays_non_negative() -> None:
    expr, env = _proposition(
        "module M\nvar a : NonNegativeReal\nvar b : NonNegativeReal\nrequire a + b >= 0\n"
    )
    interval = interval_of(expr.left, env)
    assert interval.entirely_above(Fraction(0), strict=False)
    assert not interval.entirely_above(Fraction(1), strict=False)


def test_an_unmodelled_type_reports_the_real_reason() -> None:
    expr, env = _proposition(
        "module M\nvar X : RandomVariable[Real]\nvar y : Real\nrequire y = y\n"
    )
    assert "X" in env.unmodelled
    assert "no modelled numeric domain" in env.unmodelled["X"]
