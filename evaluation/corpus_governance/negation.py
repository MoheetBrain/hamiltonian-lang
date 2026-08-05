"""Gate 4 — the negation attack, and why it can only ever subtract.

The rule
--------
Construct the negation of the candidate claim and try to prove it.

* If the negation is **proved**, the candidate is refuted. Remove it from the corpus.
* If the negation is **not** proved, **nothing has been learned about the candidate.**

The second half is the one that gets lost. It is the classic converse error: a search
that fails to find a counterexample has found nothing, and treating that as confirmation
turns "our tools are weak" into "the item is correct". On this machine the tools *are*
weak — there is no Mathlib, no ``stanc``, and the Lean backend discharges every
obligation with ``sorry`` — so failure to refute is the overwhelmingly common outcome and
would, if read as support, wave through essentially the entire corpus.

How the asymmetry is encoded in the types rather than in a comment
------------------------------------------------------------------
:func:`attack` returns :data:`NegationOutcome`, which is exactly two constructors::

    NegationOutcome = Refutation | NoInformation

There is no ``Confirmation``. There is no ``supports_candidate`` flag that a caller could
set. There is no boolean whose ``False`` branch could be read as "passed". The only
member :class:`NoInformation` exposes about the candidate is
:attr:`NoInformation.evidential_weight`, which is the literal integer ``0`` and is
annotated ``Literal[0]`` so that a static checker rejects any attempt to write another
value into it.

Consequently a caller *cannot* express "the negation attack validated this item" in this
type system. It is not discouraged; it is unrepresentable.

What the prover actually is
---------------------------
:func:`attack` takes a ``disprove`` callable so that the available deterministic
machinery is a parameter, not a hard dependency. The default,
:func:`no_prover_available`, refuses every attempt and records why — which is the honest
default on a machine with no proof assistant. :func:`sympy_disprover` is supplied for the
closed-form arithmetic and dimensional cases SymPy can actually settle, and it is
deliberately conservative: anything it is not certain about becomes
``NEGATION_NOT_PROVED``, never a refutation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

__all__ = [
    "NegationVerdict",
    "NegationAttempt",
    "Refutation",
    "NoInformation",
    "NegationOutcome",
    "attack",
    "no_prover_available",
    "sympy_disprover",
    "Disprover",
]


class NegationVerdict(StrEnum):
    """What the disproof attempt actually established.

    Note the spelling of the two negative members. ``NEGATION_NOT_PROVED`` says what
    happened to the negation; it deliberately does **not** say anything about the
    candidate. An earlier draft called it ``SURVIVED``, which reads as a property of the
    candidate and is exactly the misreading this module exists to prevent.
    """

    #: The negation was established. The candidate is refuted.
    NEGATION_PROVED = "negation_proved"
    #: The negation was attempted and not established. Says nothing about the candidate.
    NEGATION_NOT_PROVED = "negation_not_proved"
    #: No attempt was made — no procedure applies, or none is available on this machine.
    NEGATION_UNATTEMPTED = "negation_unattempted"


@dataclass(frozen=True)
class NegationAttempt:
    """One disproof attempt: what was tried, on what, and what came back."""

    item_id: str
    #: The negated claim, as it was handed to the prover.
    negated_claim: str
    verdict: NegationVerdict
    #: Which procedure ran. "none" when nothing applied.
    procedure: str
    #: Free text. Mandatory in every direction, including success.
    detail: str


@dataclass(frozen=True)
class Refutation:
    """The negation was proved. The candidate is out.

    This is the *only* constructor in this module that carries a decision about the
    candidate, and the decision it carries is always removal.
    """

    item_id: str
    attempt: NegationAttempt
    #: Reason, for the corpus record. A refuted item is retained in the exclusion log,
    #: never deleted, so the funnel's own drop rate stays auditable.
    reason: str

    @property
    def candidate_rejected(self) -> Literal[True]:
        return True


@dataclass(frozen=True)
class NoInformation:
    """The negation was not proved, or was not attempted.

    **This is not a pass.** The candidate's status is exactly what it was before the
    attack ran. :attr:`evidential_weight` is the literal ``0`` and is typed so that no
    other value can be written; there is no field on this class that a caller could use
    to record support for the candidate, because recording that would be a false
    statement about what happened.
    """

    item_id: str
    attempt: NegationAttempt

    @property
    def evidential_weight(self) -> Literal[0]:
        """Zero. Always. A failed refutation is not evidence for anything."""
        return 0

    @property
    def candidate_rejected(self) -> Literal[False]:
        return False


#: Exactly two constructors. The absence of a third is the encoding of the asymmetry.
NegationOutcome = Refutation | NoInformation

#: ``(item_id, negated_claim) -> (verdict, procedure, detail)``.
Disprover = Callable[[str, str], tuple[NegationVerdict, str, str]]


def no_prover_available(item_id: str, negated_claim: str) -> tuple[NegationVerdict, str, str]:
    """The honest default on this machine.

    Mathlib is absent, ``stanc`` is absent, and the Lean backend emits ``sorry`` for every
    obligation — so ``lean_verify`` rejects its own backend's output and no Lean path can
    certify anything here. Returning ``NEGATION_UNATTEMPTED`` records that fact per item
    instead of letting a silent no-op look like a completed check.
    """
    del item_id, negated_claim
    return (
        NegationVerdict.NEGATION_UNATTEMPTED,
        "none",
        "no deterministic disproof procedure applies on this host: Mathlib and stanc are "
        "absent and the Lean backend discharges every obligation with sorry",
    )


def sympy_disprover(item_id: str, negated_claim: str) -> tuple[NegationVerdict, str, str]:
    """Settle a *closed-form* negated claim with SymPy, or decline.

    ``negated_claim`` must be a relation over rational literals and named constants that
    SymPy can decide outright — the arithmetic and dimensional-exponent cases. Anything
    involving a free symbol, a distribution, a quantifier or a limit is declined with
    ``NEGATION_NOT_PROVED``, because a procedure that cannot decide a class of claim must
    say so rather than default to either answer.

    Declining is the common case and is not a failure of this function.
    """
    del item_id
    try:
        import sympy
    except ImportError:  # pragma: no cover - SymPy is a declared dependency here
        return (
            NegationVerdict.NEGATION_UNATTEMPTED,
            "sympy",
            "SymPy is not importable in this environment",
        )

    try:
        expr = sympy.sympify(negated_claim, evaluate=True)
    except (sympy.SympifyError, SyntaxError, TypeError) as exc:
        return (
            NegationVerdict.NEGATION_NOT_PROVED,
            "sympy",
            f"the negated claim is not a closed-form SymPy relation ({exc.__class__.__name__})",
        )

    if getattr(expr, "free_symbols", set()):
        return (
            NegationVerdict.NEGATION_NOT_PROVED,
            "sympy",
            "the negated claim contains free symbols; SymPy decides closed forms only, "
            "and a partially-evaluated relation is not a decision",
        )

    truth = expr if isinstance(expr, bool) else getattr(expr, "is_Boolean", False) and bool(expr)
    if truth is True:
        return (
            NegationVerdict.NEGATION_PROVED,
            "sympy",
            f"SymPy evaluates the negation {negated_claim!r} to True, so the candidate is false",
        )
    if truth is False:
        return (
            NegationVerdict.NEGATION_NOT_PROVED,
            "sympy",
            f"SymPy evaluates the negation {negated_claim!r} to False. The candidate is "
            f"not thereby established; only this one negation is closed off",
        )
    return (
        NegationVerdict.NEGATION_NOT_PROVED,
        "sympy",
        "SymPy returned a non-boolean; the attempt is undecided",
    )


def attack(
    item_id: str,
    negated_claim: str,
    *,
    disprove: Disprover = no_prover_available,
) -> NegationOutcome:
    """Run the negation attack and return the one outcome the result actually supports.

    A ``NEGATION_PROVED`` verdict yields a :class:`Refutation`. Everything else — not
    proved, not attempted, prover unavailable, prover confused — yields
    :class:`NoInformation`, and they are not distinguished at the outcome level *on
    purpose*: they are the same amount of evidence about the candidate, namely none.
    The distinction survives inside :attr:`NoInformation.attempt` for the audit trail.
    """
    verdict, procedure, detail = disprove(item_id, negated_claim)
    attempt = NegationAttempt(
        item_id=item_id,
        negated_claim=negated_claim,
        verdict=verdict,
        procedure=procedure,
        detail=detail,
    )
    if verdict is NegationVerdict.NEGATION_PROVED:
        return Refutation(
            item_id=item_id,
            attempt=attempt,
            reason=f"negation proved by {procedure}: {detail}",
        )
    return NoInformation(item_id=item_id, attempt=attempt)
