"""The verifier's dimension re-reader must honour parentheses.

`parse_dimension_text` is a deliberately independent re-implementation of the dimension
grammar, so a dimensional claim is checked against a *second* reading of the source rather
than against the type checker's own answer echoed back. That independence is worth having
— but the second reader was incomplete: its tokeniser deleted `(` and `)` outright.

The consequence was worse than a spelling inconvenience. The compiler *renders* its own
canonical form with parentheses, so the re-reader received `Mass / (Length * Time^2)` and
re-read it as `Mass / Length * Time^2`. Every dimension needing two divisions — pressure,
density, acceleration over area — was reported DISPROVED no matter how the author wrote it.
A single trailing division was unaffected, which is why `examples/physics/kinetic_energy.hml`
never caught it.

See D-028.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.verification.obligations import verify_source
from hamiltonian_lang.verification.obligations.checkers import parse_dimension_text

PRESSURE_MODULE = (
    "module P\n"
    "param f : Quantity[Mass * Length / Time^2]\n"
    "param a : Quantity[Length^2]\n"
    "def q := f / a\n"
    "check dimension q = {expr}\n"
)


@pytest.mark.parametrize(
    "expr",
    [
        "Mass / Length / Time^2",       # unparenthesised, left-associative
        "Mass / (Length * Time^2)",     # the compiler's own canonical rendering
        "Mass / Length^1 / Time^2",     # explicit unit exponent
    ],
)
def test_a_two_division_dimension_can_be_asserted(expr: str):
    """All three spellings denote pressure and must verify. Before D-028, none did."""
    outcome = verify_source(PRESSURE_MODULE.format(expr=expr), "<test>")
    assert str(outcome.verdict) == "VERIFIED", (
        f"{expr!r} did not verify; records: "
        f"{[(r.evidence.get('computed'), r.evidence.get('asserted')) for r in outcome.records]}"
    )


@pytest.mark.parametrize(
    ("written", "equivalent"),
    [
        ("Mass / Length / Time^2", "Mass / (Length * Time^2)"),
        ("Mass / (Length * Time^2)", "Mass * Length^-1 * Time^-2"),
        ("Mass / (Length / Time)", "Mass * Length^-1 * Time"),
    ],
)
def test_the_re_reader_agrees_with_the_explicit_exponent_form(written: str, equivalent: str):
    left, right = parse_dimension_text(written), parse_dimension_text(equivalent)
    assert left is not None and right is not None
    assert left == right, f"{written!r} -> {left.render()}, {equivalent!r} -> {right.render()}"


def test_a_parenthesised_divisor_is_a_different_dimension():
    """The discriminating case. If parentheses were dropped these would collapse."""
    grouped = parse_dimension_text("Mass / (Length * Time)")
    nested = parse_dimension_text("Mass / (Length / Time)")
    assert grouped is not None and nested is not None
    assert grouped != nested


def test_a_group_exponent_binds_to_the_whole_group():
    assert parse_dimension_text("(Length * Mass)^2") == parse_dimension_text(
        "Length^2 * Mass^2"
    )


@pytest.mark.parametrize(
    ("text", "expected_render"),
    [
        ("Length^1/2", "Length^1/2"),   # rational exponent, NOT a division
        ("Mass^2 / Time", "Mass^2 / Time"),  # division, NOT a rational exponent
    ],
)
def test_a_slash_after_an_exponent_is_a_fraction_only_when_both_sides_are_numeric(
    text: str, expected_render: str
):
    """Tokenising `(` and `)` separated `1` `/` `2`, which had been one identifier token.

    Rational exponents are a supported dimension feature, so the fix had to keep them
    working. `n / m` is an exponent only when both sides are numeric; the language parser
    draws the same distinction and the re-reader must agree or it rejects valid programs.
    """
    parsed = parse_dimension_text(text)
    assert parsed is not None, f"{text!r} failed to parse"
    assert parsed.render() == expected_render


def test_a_genuinely_wrong_dimension_is_still_rejected():
    """The fix must not make the check permissive."""
    outcome = verify_source(
        PRESSURE_MODULE.format(expr="Mass * Time^2 / Length"), "<test>"
    )
    assert str(outcome.verdict) != "VERIFIED"
