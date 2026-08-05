"""SymPy simplifies *generically*. This file is why that is not a proof.

A measured unsoundness, found while red-teaming the engine: ``sympy.simplify(x/x - 1)``
is ``0``, so the symbolic checker discharged ``prove x / x = 1`` for a free real ``x``.
That claim is **false at zero**. A CAS is entitled to cancel on the assumption that it is
not standing on the measure-zero set where the operation is undefined; a verifier is not.

``partiality_risk`` closes it by requiring every partial operation to be *total* over the
declared domains before a symbolic result may be believed. The tests below assert both
halves — the hole stays shut, and the guard does not cost the identities that are
genuinely total.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.verification.obligations import GlobalVerdict, verify_source
from hamiltonian_lang.verification.obligations.checkers import partiality_risk
from hamiltonian_lang.verification.obligations.evaluate import build_environment

# Claims a CAS "simplifies to true" that are false or undefined somewhere in the domain.
UNSOUND_IF_UNGUARDED = [
    ("self division over the reals", "module M\nvar x : Real\nprove x / x = 1\n"),
    ("cancellation by a possibly-zero factor",
     "module M\nvar x : Real\nvar y : Real\nprove x * y / y = x\n"),
    ("zeroth power of a possibly-zero base", "module M\nvar x : Real\nprove x^0 = 1\n"),
    ("negative power of a possibly-zero base",
     "module M\nvar x : Real\nprove x^-1 * x = 1\n"),
    ("tangent, whose poles are not an interval condition",
     "module M\nvar x : Real\nprove tan(x) = tan(x)\n"),
]

# The same shapes, made total by a declared refinement type.
TOTAL_AND_STILL_DISCHARGED = [
    ("self division on PositiveReal",
     "module M\nparam x : PositiveReal\nprove x / x = 1\n"),
    ("cancellation by a positive factor",
     "module M\nvar x : Real\nparam y : PositiveReal\nprove x * y / y = x\n"),
    ("sqrt of a positive parameter",
     "module M\nparam t : PositiveReal\nprove sqrt(t) * sqrt(t) = t\n"),
    ("log of exp, which is positive everywhere",
     "module M\nvar t : Real\nprove log(exp(t)) = t\n"),
    ("a polynomial identity, total by construction",
     "module M\nvar x : Real\nprove (x + 1)^2 = x^2 + 2 * x + 1\n"),
]


@pytest.mark.parametrize(
    ("label", "source"), UNSOUND_IF_UNGUARDED, ids=[c[0] for c in UNSOUND_IF_UNGUARDED]
)
def test_a_partial_operation_is_never_discharged_symbolically(
    label: str, source: str
) -> None:
    outcome = verify_source(source)
    assert outcome.verdict is not GlobalVerdict.VERIFIED, label
    symbolic = [r for r in outcome.records if r.checker == "symbolic_identity"]
    assert symbolic, label
    for record in symbolic:
        assert not record.discharged, label
        assert "partiality_risk" in record.evidence, label


@pytest.mark.parametrize(
    ("label", "source"),
    TOTAL_AND_STILL_DISCHARGED,
    ids=[c[0] for c in TOTAL_AND_STILL_DISCHARGED],
)
def test_a_total_identity_still_discharges(label: str, source: str) -> None:
    outcome = verify_source(source)
    assert outcome.verdict is GlobalVerdict.VERIFIED, f"{label}\n{outcome.render()}"
    assert any(r.checker == "symbolic_identity" and r.discharged for r in outcome.records)


def _risk(source: str) -> str | None:
    result = compile_source(source)
    assert result.ok(), [d.code for d in result.diagnostics.errors]
    env = build_environment(result.module, result.symbols)
    expr = result.obligations[0].expression
    assert expr is not None
    return partiality_risk(expr, env)


def test_the_guard_names_the_operation_and_the_domain_it_could_not_exclude() -> None:
    risk = _risk("module M\nvar x : Real\nprove x / x = 1\n")
    assert risk is not None
    assert "divisor" in risk
    assert "not provably non-zero" in risk


def test_the_guard_is_silent_when_every_operation_is_total() -> None:
    assert _risk("module M\nvar x : Real\nprove (x + 1)^2 = x^2 + 2 * x + 1\n") is None


def test_a_symbolic_exponent_is_refused() -> None:
    risk = _risk("module M\nvar x : PositiveReal\nvar n : Real\nprove x^n = x^n\n")
    assert risk is not None and "symbolic exponent" in risk


def test_the_type_checker_already_closes_the_sqrt_and_log_domains() -> None:
    """Defence in depth: the guard's `sqrt`/`log` branches sit behind HML-T427.

    ``sqrt : NonNegativeReal -> NonNegativeReal`` and ``log : PositiveReal -> Real`` are
    declared builtin signatures, so a real-valued argument never reaches the engine.
    Recording that here means the guard's redundancy is a fact rather than an assumption.
    """
    for source in (
        "module M\nvar x : Real\nprove sqrt(x) * sqrt(x) = x\n",
        "module M\nparam x : NonNegativeReal\nprove log(x) = log(x)\n",
    ):
        result = compile_source(source)
        assert not result.ok()
        assert "HML-T427" in [d.code for d in result.diagnostics.errors]
        assert verify_source(source).verdict is GlobalVerdict.INVALID


def test_the_guard_refuses_sqrt_and_log_on_an_unmodelled_argument() -> None:
    """Exercised directly, because the type system stops these before the engine sees them."""
    from hamiltonian_lang.ast.nodes import Call, Ref
    from hamiltonian_lang.verification.obligations.evaluate import Environment

    env = Environment()
    unknown = Ref(name="opaque")
    assert "sqrt" in (partiality_risk(Call(callee="sqrt", args=[unknown]), env) or "")
    assert "log" in (partiality_risk(Call(callee="log", args=[unknown]), env) or "")
