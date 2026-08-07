"""Term-level definedness contracts (D-036).

These exist because of a CRITICAL soundness exploit found by adversarial review of the
trusted-rule kernel. Obligations were keyed on the inference RULE, so `divide_both_sides`
declared `k != 0` and the identical step spelled another way did not:

    assume p1 : a = b
    derive d1 : a * (1.0 / 0.0) = b * (1.0 / 0.0) from p1
                by multiply_both_sides(by := 1.0 / 0.0)

reached **VERIFIED**, its goal reached **PROVED**, with zero obligations and exit 0 --
carrying a literal division by zero in the certified statement. The rule was blameless:
multiplying both sides by anything really is valid. Nobody asked whether the thing being
multiplied by was defined.

Definedness is a property of a term. The tests below therefore attack the *spelling*: the
same undefined operation reached through different rules, different positions, and nesting.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.reasoning.partiality import (
    CONTRACTS,
    Partiality,
    decides_false,
    preconditions_of,
)

P = "module M\nvar a : Real\nvar b : Real\nvar k : Real\n"


def _status(src: str, label: str = "d1") -> str | None:
    r = compile_source(src, "<test>")
    return (r.reasoning.derivation_status or {}).get(label) if r.reasoning else None


# ---------------------------------------------------------------------------
# The exploit, and every spelling of it
# ---------------------------------------------------------------------------


def test_the_original_exploit_is_rejected():
    src = (
        P + "assume p1 : a = b\n"
        "goal   g1 : a * (1.0 / 0.0) = b * (1.0 / 0.0)\n"
        "derive d1 : a * (1.0 / 0.0) = b * (1.0 / 0.0) from p1 "
        "by multiply_both_sides(by := 1.0 / 0.0)\n"
        "proved g1 by d1\n"
    )
    r = compile_source(src, "<test>")
    assert not r.ok()
    assert "HML-R715" in [d.code for d in r.diagnostics.items]
    assert r.reasoning.derivation_status["d1"] == "REJECTED"
    assert r.reasoning.goal_status.get("g1") != "PROVED"


@pytest.mark.parametrize(
    "rule",
    ["multiply_both_sides", "add_both_sides", "subtract_both_sides"],
)
def test_no_rule_can_smuggle_a_division_by_zero(rule):
    """The generalisation. A rule cannot evade a requirement it does not declare,
    because the requirement is found in the term."""
    src = (
        P + "assume p1 : a = b\n"
        f"derive d1 : a = b from p1 by {rule}(by := 1.0 / 0.0)\n"
    )
    r = compile_source(src, "<test>")
    assert r.reasoning.derivation_status.get("d1") == "REJECTED", (
        f"{rule} accepted a division by zero in its argument"
    )


def test_a_division_by_zero_in_the_conclusion_is_rejected():
    src = (
        P + "assume p1 : a = b\n"
        "derive d1 : a + (1.0 / 0.0) = b + (1.0 / 0.0) from p1 "
        "by add_both_sides(by := 1.0 / 0.0)\n"
    )
    assert _status(src) == "REJECTED"


def test_a_nested_division_by_zero_is_found():
    """`preconditions_of` walks the whole term, not just its root."""
    src = (
        P + "assume p1 : a = b\n"
        "derive d1 : a = b from p1 by multiply_both_sides(by := 1.0 + (2.0 * (3.0 / 0.0)))\n"
    )
    assert _status(src) == "REJECTED"


# ---------------------------------------------------------------------------
# Open, discharged, and the refusals
# ---------------------------------------------------------------------------


def test_an_unknown_divisor_leaves_the_obligation_open():
    src = (
        P + "assume p1 : a = b\n"
        "derive d1 : a * (1.0 / k) = b * (1.0 / k) from p1 "
        "by multiply_both_sides(by := 1.0 / k)\n"
    )
    assert _status(src) == "CHECKED", "not refuted, but not certified either"


def test_a_matching_assumption_discharges_a_term_level_obligation():
    src = (
        P + "assume p0 : k != 0.0\nassume p1 : a = b\n"
        "derive d1 : a * (1.0 / k) = b * (1.0 / k) from p1 "
        "by multiply_both_sides(by := 1.0 / k)\n"
    )
    assert _status(src) == "VERIFIED"


def test_non_strict_does_not_discharge_a_definedness_obligation():
    src = (
        P + "assume p0 : k >= 0.0\nassume p1 : a = b\n"
        "derive d1 : a * (1.0 / k) = b * (1.0 / k) from p1 "
        "by multiply_both_sides(by := 1.0 / k)\n"
    )
    assert _status(src) == "CHECKED", "k >= 0 admits k = 0"


def test_a_total_operation_generates_nothing():
    src = P + "assume p1 : a = b\nderive d1 : a * 2.0 = b * 2.0 from p1 by multiply_both_sides(by := 2.0)\n"
    assert _status(src) == "VERIFIED"


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------


def test_every_contracted_operation_has_a_builder():
    """D-036 D4: an operation classified CONTRACTED with no precondition builder would
    silently generate nothing, which is the failure this whole module exists to prevent."""
    for name, c in CONTRACTS.items():
        if c.partiality is Partiality.CONTRACTED:
            assert c.build is not None, f"{name} is CONTRACTED with no builder"
            assert c.reason, f"{name} has no reason string"


def test_division_and_negative_powers_and_tan_are_contracted():
    for op in ("/", "^", "tan"):
        assert CONTRACTS[op].partiality is Partiality.CONTRACTED


def test_log_and_sqrt_are_guarded_by_type_not_by_obligation():
    """They are already rejected statically; adding an obligation would double-report."""
    for op in ("log", "sqrt"):
        assert CONTRACTS[op].partiality is Partiality.GUARDED
        assert CONTRACTS[op].build is None


def test_a_non_negative_literal_exponent_generates_no_obligation():
    """Otherwise every `x ^ 2.0` carries a spurious obligation, which is the fastest way
    to make authors stop reading obligations at all."""
    from hamiltonian_lang.ast.nodes import BinOp, Literal, Ref

    node = BinOp(op="^", left=Ref(name="x"), right=Literal(value=2.0, raw="2.0"))
    assert preconditions_of(node) == []


def test_a_negative_literal_exponent_does_generate_one():
    from hamiltonian_lang.ast.nodes import BinOp, Literal, Ref, UnaryOp

    node = BinOp(
        op="^",
        left=Ref(name="x"),
        right=UnaryOp(op="-", operand=Literal(value=1.0, raw="1.0")),
    )
    assert len(preconditions_of(node)) == 1


# ---------------------------------------------------------------------------
# Refutation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("op", "a", "b", "expected"),
    [("!=", 0.0, 0.0, True), ("!=", 1.0, 0.0, False), (">", -1.0, 0.0, True),
     (">", 1.0, 0.0, False), ("=", 1.0, 2.0, True), ("=", 2.0, 2.0, False)],
)
def test_decides_false_only_on_closed_literals(op, a, b, expected):
    from hamiltonian_lang.ast.nodes import Comparison, Literal

    prop = Comparison(op=op, left=Literal(value=a, raw=str(a)), right=Literal(value=b, raw=str(b)))
    assert decides_false(prop) is expected


def test_an_open_symbolic_obligation_is_never_refuted():
    from hamiltonian_lang.ast.nodes import Comparison, Literal, Ref

    prop = Comparison(op="!=", left=Ref(name="k"), right=Literal(value=0, raw="0"))
    assert decides_false(prop) is False


# ---------------------------------------------------------------------------
# Matrix shape conformance (HML-T435)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("left", "right", "accepted"),
    [
        ("Matrix[Real, 2, 3]", "Matrix[Real, 4, 5]", False),
        ("Matrix[Real, 2, 3]", "Matrix[Real, 2, 5]", False),
        ("Matrix[Real, 2, 3]", "Matrix[Real, 4, 3]", False),
        ("Matrix[Real, 2, 3]", "Matrix[Real, 2, 3]", True),
        ("Matrix[Real, n, m]", "Matrix[Real, n, m]", True),
    ],
)
def test_elementwise_matrix_operations_require_identical_shapes(left, right, accepted):
    """`Matrix[2,3] + Matrix[4,5]` compiled clean while vector `+` and matrix `@` were
    both checked -- a silent shape loss in the one family where shape is the point.
    Found by the full-ontology probe."""
    src = f"module M\nvar A : {left}\nvar B : {right}\nrequire A + B = A + B\n"
    assert compile_source(src, "<test>").ok() is accepted


def test_a_shape_clash_is_reported_as_a_shape_clash():
    r = compile_source(
        "module M\nvar A : Matrix[Real, 2, 3]\nvar B : Matrix[Real, 4, 5]\n"
        "require A + B = A + B\n",
        "<test>",
    )
    assert "HML-T435" in [d.code for d in r.diagnostics.items]
