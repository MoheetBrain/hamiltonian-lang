"""Probability V0 — the conditional-product law, and nothing else.

One theorem::

    P(A and B) = P(A) * P(B | A)          requires  P(A) > 0

HML's actual conventions, checked before writing this rather than assumed
---------------------------------------------------------------------------
Three facts about the existing ontology drive the whole design, and each was verified
against the compiler rather than taken from a textbook or a proposal:

1. **`probability(...)` requires an `Event`, not a `Bool`.** `_require_event` rejects a
   proposition over fixed quantities with HML-T482 and says why: "a proposition over fixed
   quantities is true or false, so its probability is 0 or 1 and asking for it states
   nothing". Events arise from propositions over random variables — `X > 0.0` where
   `rv X : RandomVariable[Real]`. The theorem's variables are therefore declared
   ``kind="event"`` and a value substitution is refused.

2. **Conditioning direction is `event` given `given`.** `ProbabilityExpr` carries
   ``event`` and ``given: list[Expr]``, so ``probability(B | A)`` is
   ``event=B, given=[A]``. The conditioning event is ``given[0]``. Writing the law with
   the operands the other way round produces a different proposition and is rejected —
   there is a test for exactly that, because a reversed conditional is the single most
   common way to get this law wrong.

3. **`joint(...)` is NOT event intersection.** It is the joint *law* of random variables,
   typed ``Distribution[Product[...]]``. Using it for `A ∩ B` would be a category error the
   type system would catch, but it is worth stating: the intersection of two events is the
   conjunction ``A and B`` inside `probability(...)`, and that is what this theorem builds.

Definedness is not optional
---------------------------
``P(B | A)`` is undefined when ``P(A) = 0``. The side condition ``P(A) > 0`` is generated
as an **ordinary ``ReasoningObligation``** and discharged against Γ by the existing
machinery — not by a private probability-specific check, and not by quietly totalising the
conditional at zero. If nothing in Γ establishes it, the certificate does not validate.

What was deliberately not built
-------------------------------
No measure theory, no sigma-algebras, no measurability side conditions, no Bayes, no
expectation or variance library, no distributions. HML's probability ontology does not
currently require them, and adding them to make Gold-10 greener would be building a
different language. This is elementary probability over the events HML already types.
"""

from __future__ import annotations

from ..ast.nodes import BinOp, Comparison, Expr, Literal, LogicalOp, ProbabilityExpr
from .theorem import (
    LibraryTheorem,
    SideCondition,
    TheoremVariable,
    VerificationKind,
    _register,
)

__all__ = ["CONDITIONAL_PRODUCT"]


def _p(event: Expr, given: Expr | None = None) -> ProbabilityExpr:
    return ProbabilityExpr(
        event=event, given=[given] if given is not None else [], span=event.span
    )


def _conclusion(s) -> Comparison:
    """``P(A and B) = P(A) * P(B | A)``.

    Note the shape of each side. The left is the probability of a *conjunction of events*
    -- HML's spelling of intersection. The right conditions B on A, in that direction.
    """
    a, b = s["A"], s["B"]
    joint_event = LogicalOp(op="and", left=a, right=b, span=a.span)
    return Comparison(
        op="=",
        left=_p(joint_event),
        right=BinOp(op="*", left=_p(a), right=_p(b, a), span=a.span),
        span=a.span,
    )


def _positive_conditioning_event(s) -> Comparison:
    """``P(A) > 0`` -- the definedness condition for conditioning on A."""
    a = s["A"]
    return Comparison(
        op=">", left=_p(a), right=Literal(value=0.0, raw="0.0", span=a.span), span=a.span
    )


CONDITIONAL_PRODUCT = _register(
    LibraryTheorem(
        id="conditional_product",
        version=1,
        library="probability",
        variables=(
            TheoremVariable(name="A", kind="event"),
            TheoremVariable(name="B", kind="event"),
        ),
        conclusion=_conclusion,
        statement="P(A and B) = P(A) * P(B | A)   [requires P(A) > 0]",
        verification_kind=VerificationKind.DEFINITIONAL,
        justification=(
            "This is the definition of conditional probability rearranged: "
            "P(B | A) is *defined* as P(A and B) / P(A) for P(A) > 0, so the product form "
            "adds no content beyond that definition and the definedness condition it "
            "already carries. It is labelled DEFINITIONAL rather than LIBRARY_AXIOM for "
            "that reason -- accepting it commits to nothing HML's probability ontology "
            "had not already committed to. It is still an assumption in the sense that "
            "HML does not derive it, and it appears in libraries.axioms()."
        ),
        side_conditions=(
            SideCondition(
                build=_positive_conditioning_event,
                reason="conditioning_event_has_positive_probability",
                mandatory=True,
            ),
        ),
        provenance="elementary probability; the definition of conditional probability",
    )
)
