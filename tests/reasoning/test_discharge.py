"""Obligation generation and assumption discharge.

The three cases the directive singles out are the first three tests, because they are
the ones where a permissive answer would be unsound:

    assume x > 0   DISCHARGES  x > 0
    assume x >= 0  does NOT discharge  x > 0
    x != 0 is NOT inferred from x >= 0
"""

from __future__ import annotations

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import DerivationStatus, DeriveStmt
from hamiltonian_lang.reasoning import ObligationStatus

PRELUDE = "module M\nvar x : Real\nvar y : Real\nvar k : Real\n"


def _compile(body: str):
    return compile_source(PRELUDE + body, "<test>")


def _status(result, label: str) -> str:
    for st in result.module.statements:
        if isinstance(st, DeriveStmt) and st.label == label:
            return st.status
    raise AssertionError(f"no derivation {label!r}")


_DIVIDE = (
    "assume a1 : y = 2.0 * x\n"
    "derive d1 : y / k = 2.0 * x / k from a1 by divide_both_sides(by := k)\n"
)


# ---------------------------------------------------------------------------
# The three named cases
# ---------------------------------------------------------------------------


def test_a_matching_assumption_discharges_the_obligation():
    r = _compile("assume a0 : k != 0.0\n" + _DIVIDE)
    assert r.ok(), r.diagnostics.render()
    assert _status(r, "d1") == DerivationStatus.VERIFIED
    assert all(o.status == ObligationStatus.DISCHARGED for o in r.reasoning.obligations)
    assert r.reasoning.obligations[0].discharged_by == "a0"


def test_non_strict_does_not_discharge_strict():
    """`k >= 0` must NOT establish `k != 0`. Zero satisfies the former, not the latter."""
    r = _compile("assume a0 : k >= 0.0\n" + _DIVIDE)
    assert _status(r, "d1") == DerivationStatus.CHECKED, "must not reach VERIFIED"
    assert r.reasoning.open_obligations()


def test_strict_positivity_does_discharge_disequality():
    """`k > 0` DOES establish `k != 0`. Sound, and the environment must not be so timid
    that it refuses valid entailments -- that would make the layer useless instead of
    merely conservative."""
    r = _compile("assume a0 : k > 0.0\n" + _DIVIDE)
    assert r.ok(), r.diagnostics.render()
    assert _status(r, "d1") == DerivationStatus.VERIFIED


def test_an_unrelated_assumption_does_not_discharge():
    r = _compile("var m : Real\nassume a0 : m != 0.0\n" + _DIVIDE)
    assert _status(r, "d1") == DerivationStatus.CHECKED
    assert r.reasoning.open_obligations()


def test_no_assumption_leaves_the_obligation_open():
    r = _compile(_DIVIDE)
    assert _status(r, "d1") == DerivationStatus.CHECKED
    open_obs = r.reasoning.open_obligations()
    assert len(open_obs) == 1
    assert open_obs[0].reason == "divide_domain"
    assert open_obs[0].mandatory


def test_integer_and_float_zero_agree():
    """`divide_both_sides` builds its obligation with an integer 0; the author writes
    0.0. Regression for the bug the first end-to-end run exposed, where every division
    obligation stayed OPEN no matter what was assumed."""
    r = _compile("assume a0 : k != 0.0\n" + _DIVIDE)
    assert _status(r, "d1") == DerivationStatus.VERIFIED


# ---------------------------------------------------------------------------
# Obligations block VERIFIED, and therefore block `proved`
# ---------------------------------------------------------------------------


def test_an_open_obligation_blocks_proved():
    r = _compile(
        _DIVIDE
        + "goal g1 : y / k = 2.0 * x / k\n"
        + "proved g1 by d1\n"
    )
    assert not r.ok()
    assert "HML-R710" in [d.code for d in r.diagnostics.items]


def test_multiply_inequality_generates_a_positivity_obligation():
    """Multiplying an inequality by an unsigned quantity is a classic false step."""
    r = _compile(
        "assume a1 : x < y\n"
        "derive d1 : x * k < y * k from a1 by multiply_inequality(by := k)\n"
    )
    assert _status(r, "d1") == DerivationStatus.CHECKED, "k is not known positive"
    assert r.reasoning.open_obligations()[0].reason == "order_preserving_multiplier"

    r2 = _compile(
        "assume a0 : k > 0.0\n"
        "assume a1 : x < y\n"
        "derive d1 : x * k < y * k from a1 by multiply_inequality(by := k)\n"
    )
    assert _status(r2, "d1") == DerivationStatus.VERIFIED


# ---------------------------------------------------------------------------
# What must never enter the environment
# ---------------------------------------------------------------------------


def test_a_disjunction_asserts_neither_disjunct():
    r = _compile("assume a0 : k != 0.0 or x > 0.0\n" + _DIVIDE)
    assert _status(r, "d1") == DerivationStatus.CHECKED, (
        "`P or Q` must not license a step that needs P"
    )


def test_require_is_not_a_fact():
    """`require` states an obligation. Letting it discharge one would be circular:
    the module would be assuming what it is asking to be checked."""
    r = _compile("require k != 0.0\n" + _DIVIDE)
    assert _status(r, "d1") == DerivationStatus.CHECKED


def test_prove_is_not_a_fact():
    r = _compile("prove k != 0.0\n" + _DIVIDE)
    assert _status(r, "d1") == DerivationStatus.CHECKED


def test_a_conjunction_contributes_both_sides():
    r = _compile("assume a0 : k != 0.0 and x > 0.0\n" + _DIVIDE)
    assert _status(r, "d1") == DerivationStatus.VERIFIED
