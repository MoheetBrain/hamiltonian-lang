"""The context-relative entailment judgment.

Why a judgment and not a status
--------------------------------
``GoalStatus`` is a word attached to a goal. That is enough for ``PROVED``, where the
supporting derivation is named right there in the ``proved`` statement and the checker can
re-examine it. It is *not* enough for underdetermination, because "the premises settle
neither P nor not-P" is a claim about a **theory**, and a theory is not identified by the
goal it is being asked about.

Two consequences drive the design.

**Non-entailment does not survive adding premises.** If Γ ⊭ P and you then assert one more
fact, Γ' ⊨ P may well hold — entailment is monotone, so a certificate issued against a
subset says nothing about the superset. A status word cannot express which Γ it was about.
A judgment can, by binding the context's identity.

**Ignorance and underdetermination must never share a representation.** A four-valued
verdict makes the distinction structural rather than a matter of remembering to check a
flag: ``UNKNOWN`` and ``UNDERDETERMINED`` are different values, and the only route to the
latter runs through a validated certificate carrying two models.

So :class:`Adjudication` is the semantic source of truth, and ``GoalStatus`` is its
*projection* (:meth:`Adjudication.goal_status`) — present so existing consumers keep
working, never a thing that can be set on its own.

Specification: ``docs/hml_v2/GOLD10_CORE_SEMANTICS_SPEC.md`` §3.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..ast.nodes import GoalStatus

__all__ = ["EntailmentVerdict", "Adjudication"]


class EntailmentVerdict(StrEnum):
    """``adjudicate(Γ, P)``. Four values, and the gap between the last two is the point.

    ``ENTAILED``          Γ ⊨ P.
    ``REFUTED``           Γ ⊨ ¬P.
    ``UNDERDETERMINED``   checked models M⁺ ⊨ Γ ∪ {P} and M⁻ ⊨ Γ ∪ {¬P} both exist.
    ``UNKNOWN``           the supported checkers cannot establish any of the above.

    **Nothing converts ``UNKNOWN`` into ``UNDERDETERMINED``.** Not a failed search, not a
    timeout, not an unsupported fragment, not a partial model, not an external solver
    shrugging, not the absence of evidence. Certified underdetermination is a positive
    result and carries two models; ignorance carries nothing. This is the single most
    important invariant in this subsystem.

    ``REFUTED`` is part of the vocabulary and has no adjudicating statement form yet —
    exactly as ``GoalStatus.REFUTED`` did before this work. It is named here so the
    judgment is total over the four semantic outcomes rather than shaped by which
    statements happen to exist.
    """

    ENTAILED = "ENTAILED"
    REFUTED = "REFUTED"
    UNDERDETERMINED = "UNDERDETERMINED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Adjudication:
    """One verdict, bound to the exact mathematics it was reached about.

    Frozen, because an adjudication that could be edited after the fact would be a label
    rather than a finding.
    """

    goal: str
    verdict: EntailmentVerdict
    #: ``expr_identity`` of the goal's proposition.
    target_hash: str
    #: Identity of Γ at the moment of adjudication. See ``certificates.context_hash``.
    context_hash: str
    #: ``expr_identity`` of each premise the supporting evidence declared, in order.
    premise_hashes: tuple[str, ...] = ()
    #: Claim label of the derivation or evidence that supports this verdict.
    support: str | None = None
    #: Registry key of the checker, when the support was a certificate.
    checker: str | None = None
    #: Why, when the verdict is UNKNOWN. Present so "we could not tell" always has a
    #: reason attached, which is what stops it being read as a finding.
    reason: str = ""

    def goal_status(self) -> str:
        """Project onto the legacy ``GoalStatus`` vocabulary.

        A projection loses information — ``UNKNOWN`` and "never adjudicated" both land on
        ``OPEN`` — which is precisely why the judgment, not the status, is the source of
        truth.
        """
        return {
            EntailmentVerdict.ENTAILED: GoalStatus.PROVED,
            EntailmentVerdict.REFUTED: GoalStatus.REFUTED,
            EntailmentVerdict.UNDERDETERMINED: GoalStatus.UNDERDETERMINED,
            EntailmentVerdict.UNKNOWN: GoalStatus.OPEN,
        }[self.verdict]

    def to_dict(self) -> dict:
        """Presentation only. Never enters a content hash."""
        return {
            "goal": self.goal,
            "verdict": str(self.verdict),
            "target_hash": self.target_hash,
            "context_hash": self.context_hash,
            "premise_hashes": list(self.premise_hashes),
            "support": self.support,
            "checker": self.checker,
            "reason": self.reason,
        }
