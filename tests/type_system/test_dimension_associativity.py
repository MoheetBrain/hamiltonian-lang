"""Dimension division associates left and honours parentheses.

Raised as a suspected defect during the V1 sprint: the claim was that `/` associates right
and that parentheses are ignored, so `Mass / Length / Time^2` and `Mass / (Length * Time^2)`
would both collapse to `Mass * Time^2 / Length`. Direct measurement refuted it — the claim
does not reproduce, and no parser change was made.

These tests exist so the question is settled by an executable check rather than re-argued.
The first two identities agreeing is *correct*, not a collapse: `a/b/c` and `a/(b*c)` are
the same dimension. The load-bearing case is the third, where a parenthesised divisor
inverts the sign of the inner exponent and must produce a genuinely different dimension.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source


def _dim(expr: str) -> str:
    result = compile_source(f"module M\nvar x : Quantity[{expr}]\n")
    assert result.ok(), f"{expr!r} did not compile: {result.diagnostics}"
    rendered = result.module.statements[-1].declared_type
    assert rendered is not None
    return rendered.render()


@pytest.mark.parametrize(
    ("written", "canonical"),
    [
        ("Mass / Length / Time", "Mass * Length^-1 * Time^-1"),
        ("Mass / (Length * Time)", "Mass * Length^-1 * Time^-1"),
        ("Mass / (Length / Time)", "Mass * Length^-1 * Time"),
    ],
)
def test_division_matches_its_explicit_exponent_form(written: str, canonical: str):
    """`a/b/c` and `a/(b*c)` are `a*b^-1*c^-1`; `a/(b/c)` is `a*b^-1*c`."""
    assert _dim(written) == _dim(canonical)


def test_a_parenthesised_divisor_is_not_the_same_dimension():
    """The discriminating case. If parentheses were ignored these would be equal."""
    assert _dim("Mass / (Length * Time)") != _dim("Mass / (Length / Time)")


def test_division_is_left_associative_not_right():
    """Right association would make `a/b/c` equal `a/(b/c)` = `a*b^-1*c`."""
    assert _dim("Mass / Length / Time") != _dim("Mass / (Length / Time)")


def test_check_dimension_rejects_a_mismatched_dimension():
    """The statement path, not just the type path -- both were doubted."""
    ok = compile_source(
        "module M\nvar x : Quantity[Mass / (Length * Time^2)]\n"
        "check dimension x = Mass / Length / Time^2\n"
    )
    assert ok.ok(), ok.diagnostics

    bad = compile_source(
        "module M\nvar x : Quantity[Mass / (Length * Time^2)]\n"
        "check dimension x = Mass * Time^2 / Length\n"
    )
    assert not bad.ok()
    assert any("HML-D504" in d.code for d in bad.diagnostics.errors)
