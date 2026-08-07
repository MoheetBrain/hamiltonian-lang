"""`assume` must narrow types, not just discharge kernel obligations.

The V2 directive §7 names this exact program as the pathological case:

    var x : Real
    assume x > 0.0
    require log(x) = log(x)          # HML-T427 before this was wired

The refinement environment existed after D-025 but was consumed only by
`reasoning/check.py`; the type checker never saw it. So `assume` discharged a
`divide_domain` obligation and still did not make `log(x)` legal -- half a fix, and
reported as a whole one. Found by the capability-audit rerun, which is why these tests
exist. See D-028.

The negative cases matter more than the positive one. Narrowing may only ever move DOWN
the refinement lattice, and only when an assumption strictly justifies it.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source


def _ok(src: str) -> bool:
    return compile_source(src, "<test>").ok()


# ---------------------------------------------------------------------------
# The directive's example
# ---------------------------------------------------------------------------


def test_assume_positive_licenses_log():
    assert _ok("module M\nvar x : Real\nassume x > 0.0\nrequire log(x) = log(x)\n")


def test_assume_non_negative_licenses_sqrt():
    assert _ok("module M\nvar x : Real\nassume x >= 0.0\nrequire sqrt(x) = sqrt(x)\n")


# ---------------------------------------------------------------------------
# What must STILL be refused
# ---------------------------------------------------------------------------


def test_non_strict_does_not_license_log():
    """`x >= 0` admits x = 0, and log(0) is undefined. The single most important
    negative case here: the whole value of the refinement environment is that it
    refuses this."""
    assert not _ok("module M\nvar x : Real\nassume x >= 0.0\nrequire log(x) = log(x)\n")


def test_no_assumption_does_not_license_log():
    assert not _ok("module M\nvar x : Real\nrequire log(x) = log(x)\n")


def test_an_assumption_about_another_symbol_licenses_nothing():
    assert not _ok(
        "module M\nvar x : Real\nvar y : Real\n"
        "assume y > 0.0\nrequire log(x) = log(x)\n"
    )


def test_a_disjunction_licenses_nothing():
    assert not _ok(
        "module M\nvar x : Real\n"
        "assume x > 0.0 or x < 0.0\nrequire log(x) = log(x)\n"
    )


def test_a_negative_assumption_does_not_license_log():
    assert not _ok("module M\nvar x : Real\nassume x < 0.0\nrequire log(x) = log(x)\n")


def test_require_is_not_an_assumption():
    """`require` states an obligation. If it narrowed types, a module could license a
    partial operation by asking for the very thing that makes it legal."""
    assert not _ok("module M\nvar x : Real\nrequire x > 0.0\nrequire log(x) = log(x)\n")


def test_prove_is_not_an_assumption():
    assert not _ok("module M\nvar x : Real\nprove x > 0.0\nrequire log(x) = log(x)\n")


# ---------------------------------------------------------------------------
# Narrowing must not widen, and must not disturb v1 behaviour
# ---------------------------------------------------------------------------


def test_narrowing_never_widens_a_declared_type():
    """An assumption cannot make a Probability into an unbounded PositiveReal."""
    assert not _ok(
        "module M\nparam p : Probability\nassume p > 0.0\nparam q : PositiveReal = p\n"
    )


def test_an_assumption_does_not_defeat_the_dimensional_check():
    assert not _ok(
        "module M\n"
        "param a : Quantity[Length]\nparam b : Quantity[Time]\n"
        "assume a > 0.0\nrequire a + b > 0.0\n"
    )


def test_a_stronger_bound_licenses_a_weaker_requirement():
    """`x > 5` entails `x > 0`, so log is legal. Sound, and the environment should not
    be so timid that it refuses valid entailments."""
    assert _ok("module M\nvar x : Real\nassume x > 5.0\nrequire log(x) = log(x)\n")


@pytest.mark.parametrize(
    "example",
    [
        "examples/statistics/bayesian_coin.hml",
        "examples/algebra/constrained_optimisation.hml",
    ],
)
def test_shipped_examples_still_compile(example):
    """Narrowing is additive; it must not change any existing module's verdict."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    src = (root / example).read_text()
    assert compile_source(src, example).ok()
