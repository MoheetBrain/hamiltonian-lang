"""Probability V0 — the conditional product, and the definedness it must not lose.

Two things are being defended.

**Conditioning direction.** ``P(A and B) = P(A)·P(B|A)`` and ``P(A and B) = P(B)·P(A|B)``
are both true, but they are *different* instantiations, and swapping the operands of one
gives a proposition the theorem does not license. Getting this backwards is the single most
common way to misuse the law, so it gets an explicit test rather than being left to the
identity comparison to catch by luck.

**Definedness.** ``P(B|A)`` is undefined at ``P(A) = 0``. The certificate must not validate
without ``P(A) > 0`` established, and it must not quietly totalise the conditional.
"""

from __future__ import annotations

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import EvidenceStatus

HEAD = """module G09
rv X : RandomVariable[Real]
rv Y : RandomVariable[Real]
assume a1 : probability(X > 0.0) = 0.5
assume a2 : probability(Y > 0.0 | X > 0.0) = 0.8
"""
DEFINED = "assume a3 : probability(X > 0.0) > 0.0\n"
CLAIM = (
    "evidence e1 : entails probability((X > 0.0) and (Y > 0.0)) = "
    "probability(X > 0.0) * probability(Y > 0.0 | X > 0.0) "
    "by library_theorem_v1(theorem := conditional_product, {sub})\n"
)
SUB = "A := X > 0.0, B := Y > 0.0"


def _compile(src: str):
    return compile_source(src, "<prob>")


def _status(src: str, label: str = "e1") -> str:
    r = _compile(src)
    if r.reasoning is None:
        return "<not reached>"
    return r.reasoning.evidence_status.get(label, "<absent>")


# --- positive ---------------------------------------------------------------


def test_the_conditional_product_applies_when_the_conditioning_event_is_positive():
    src = HEAD + DEFINED + CLAIM.format(sub=SUB)
    r = _compile(src)
    assert r.ok(), [str(d) for d in r.diagnostics]
    assert r.reasoning.evidence_status["e1"] == EvidenceStatus.VALID


def test_the_numeric_step_is_a_separate_independently_checked_claim():
    """Gold-10 splits the law from the arithmetic, and so does this.

    `conditional_product` gives the identity; `0.5 * 0.8 = 0.4` is closed arithmetic and
    is checked by the exact evaluator that already existed. Neither borrows the other's
    authority.
    """
    src = (
        HEAD
        + DEFINED
        + CLAIM.format(sub=SUB)
        + "evidence e2 : entails 0.5 * 0.8 = 0.4 by closed_eval_v1()\n"
    )
    r = _compile(src)
    assert r.ok(), [str(d) for d in r.diagnostics]
    assert r.reasoning.evidence_status["e1"] == EvidenceStatus.VALID
    assert r.reasoning.evidence_status["e2"] == EvidenceStatus.VALID


# --- definedness ------------------------------------------------------------


def test_without_the_definedness_fact_the_theorem_does_not_apply():
    src = HEAD + CLAIM.format(sub=SUB)
    r = _compile(src)
    assert not r.ok()
    assert r.reasoning.evidence_status["e1"] == EvidenceStatus.REJECTED
    assert any("side condition" in str(d) for d in r.diagnostics)


def test_a_zero_probability_conditioning_event_does_not_verify():
    """P(A) = 0 must not be totalised into a usable conditional."""
    src = (
        HEAD.replace("probability(X > 0.0) = 0.5", "probability(X > 0.0) = 0.0")
        + CLAIM.format(sub=SUB)
    )
    assert _status(src) != EvidenceStatus.VALID


def test_the_side_condition_is_an_ordinary_obligation():
    """Same machinery as a `divide_both_sides` obligation -- not a private check."""
    src = HEAD + CLAIM.format(sub=SUB)
    r = _compile(src)
    reasons = {o.reason for o in r.reasoning.obligations}
    assert "conditioning_event_has_positive_probability" in reasons
    ob = next(
        o
        for o in r.reasoning.obligations
        if o.reason == "conditioning_event_has_positive_probability"
    )
    assert ob.mandatory
    assert ob.generated_by == "e1"


def test_the_side_condition_is_discharged_by_an_assumption_and_says_which():
    src = HEAD + DEFINED + CLAIM.format(sub=SUB)
    r = _compile(src)
    ob = next(
        o
        for o in r.reasoning.obligations
        if o.reason == "conditioning_event_has_positive_probability"
    )
    assert ob.status == "DISCHARGED"
    assert ob.discharged_by == "a3"


# --- conditioning direction -------------------------------------------------


def test_reversing_the_conditioning_is_rejected():
    """A := B and B := A licenses a different proposition than the one claimed."""
    src = HEAD + DEFINED + CLAIM.format(sub="A := Y > 0.0, B := X > 0.0")
    r = _compile(src)
    assert not r.ok()
    assert _status(src) == EvidenceStatus.REJECTED
    assert any("licenses" in str(d) for d in r.diagnostics)


def test_the_mirrored_law_is_a_different_instantiation_and_also_works():
    """P(A and B) = P(B) * P(A | B), given P(B) > 0. Both are true; they are not the same.

    Included so the previous test cannot be satisfied by a checker that simply refuses
    one orientation outright.
    """
    src = (
        HEAD
        + "assume a3 : probability(Y > 0.0) > 0.0\n"
        + "evidence e1 : entails probability((Y > 0.0) and (X > 0.0)) = "
        "probability(Y > 0.0) * probability(X > 0.0 | Y > 0.0) "
        "by library_theorem_v1(theorem := conditional_product, A := Y > 0.0, B := X > 0.0)\n"
    )
    assert _status(src) == EvidenceStatus.VALID


# --- typing -----------------------------------------------------------------


def test_a_non_event_operand_is_rejected():
    src = (
        HEAD
        + DEFINED
        + "var z : Real\n"
        + CLAIM.format(sub="A := z, B := Y > 0.0")
    )
    r = _compile(src)
    assert not r.ok()
    assert any("must be Event" in str(d) for d in r.diagnostics)


def test_a_proposition_over_fixed_quantities_is_not_an_event():
    """HML's own barrier: the probability of a non-random proposition is 0 or 1.

    Asserted here because the theorem's `kind="event"` discipline must agree with the
    type system rather than quietly widening it.
    """
    src = (
        "module P\nvar p : Real\nvar q : Real\n"
        "assume a3 : probability(p > 0.0) > 0.0\n"
        "evidence e1 : entails probability((p > 0.0) and (q > 0.0)) = "
        "probability(p > 0.0) * probability(q > 0.0 | p > 0.0) "
        "by library_theorem_v1(theorem := conditional_product, A := p > 0.0, B := q > 0.0)\n"
    )
    assert _status(src) != EvidenceStatus.VALID
