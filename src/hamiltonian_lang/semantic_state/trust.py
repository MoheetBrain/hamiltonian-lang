"""Who may create VALID evidence (D-050).

The hole this closes
--------------------
:class:`~.model.EvidenceRecord` arrives from a JSON payload, and its ``status`` field is a
string the payload's author chose. Every acceptance path in :mod:`.verify` turned on
``record.status == "VALID"``. Nothing in ``src/`` has ever *produced* that string — it is
only ever compared. So a producer that authors a transition also authors the verdict on it,
and a model asked to reason in this format could write::

    {"id": "e1", "status": "VALID", "supports_rule": "VERIFY_CANDIDATE", ...}

and be believed. Feeding model output through such a verifier measures whether the model
bothered to attack, not whether the reasoning is sound.

``EvidenceRecord.trusted`` is **not** the problem and never was: it is provenance, nothing
reads it as authority, and an audit confirmed that. ``status`` is the live field.

Two modes, because the corpus and a model are not the same kind of author
------------------------------------------------------------------------
The frozen Semantic Firewall corpus records an *observed* evidence status produced by an
external process this repository does not run. Replaying it is a legitimate activity and
its recorded statuses are reference data, not assertions by the thing under test. Refusing
them would make the acceptance fixtures unreplayable and would not make anything safer.

So the mode is explicit and the *unsafe* one is not the default you get by accident:

``OFFLINE_REPLAY``
    Recorded ``status`` is reference data. What the verifier checks is structural
    consistency between an action and the evidence it cites. Correct for the frozen corpus,
    and correct for nothing else.

``RUNTIME``
    The record's ``status`` is **ignored entirely**. Acceptance requires an
    :class:`Attestation` carrying a :class:`~..reasoning.certificates.CheckedEvidence`,
    which :func:`~..reasoning.certificates.check` mints and which nothing else can
    construct — its ``_token`` is a module-private object, so a payload cannot contain one,
    HML source cannot produce one, and library data cannot forge one.

Why this reuses ``reasoning/certificates`` rather than adding a registry
-----------------------------------------------------------------------
A second trusted registry is the failure mode, not the fix: two registries mean two trust
bases, two review surfaces, and eventually one of them accepts something the other would
refuse. ``reasoning.certificates`` already binds claim, context, premises, checker identity
and checker version into an envelope, keeps ``CHECKERS`` static and unreachable from source
or library data, and fails closed when a checker raises. This module supplies the *seam*
into that machinery and adds no trust of its own.

What the binding is, and honestly what it is not
------------------------------------------------
``certificates.check`` binds a claim by ``expr_identity`` over a typed AST. A
:class:`~.model.Claim` here carries ``proposition: str`` — an opaque corpus string that is
not HML source and generally does not parse. So an attestation binds the proposition's
**text digest**, not its expression identity. That is strictly weaker: two propositions
that differ only in formatting hash differently, and this module cannot tell you that they
mean the same thing. It is recorded rather than glossed, because the alternative — parsing
arbitrary corpus text into an AST and silently accepting whatever came out — would be a
much worse kind of wrong.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..reasoning.certificates import CheckedEvidence

__all__ = [
    "TrustMode",
    "Attestation",
    "AttestationError",
    "proposition_digest",
    "attest",
]


class TrustMode(StrEnum):
    """Who authored the transition, and therefore what its evidence status is worth."""

    #: A frozen external corpus. Recorded evidence status is observed reference data.
    OFFLINE_REPLAY = "OFFLINE_REPLAY"
    #: A model, a user, or anything else that may benefit from the verdict. Recorded
    #: status carries no authority whatsoever.
    RUNTIME = "RUNTIME"


class AttestationError(Exception):
    """An attestation was requested and could not be produced. Always a refusal."""


def proposition_digest(text: str) -> str:
    """Stable digest of a proposition's exact text.

    Deliberately not a normalisation: whitespace and formatting are significant here,
    because this module has no parser for corpus propositions and inventing an equivalence
    it cannot justify would let an attestation drift off the claim it was issued for.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Attestation:
    """A checker's verdict, bound to the exact thing it was issued about.

    The ``evidence`` field is the load-bearing one and it cannot be forged: only
    :func:`..reasoning.certificates.check` mints a ``CheckedEvidence``. Everything else here
    exists so the verifier can confirm this attestation is about *this* claim, *these*
    premises and *this* rule, rather than a valid certificate for something else replayed
    into a transition where it does not belong.
    """

    evidence_id: str
    #: Minted by ``certificates.check`` and unforgeable. Typed loosely to keep this module
    #: importable without dragging the reasoning layer in at import time.
    evidence: object
    #: Digest of the proposition this attestation is about.
    claim_digest: str
    #: Digests of the premises it was checked against, in the order they were declared.
    premise_digests: tuple[str, ...]
    #: The rule the action claims. Must match what the action's warrant declares.
    rule: str | None
    checker: str
    checker_version: str

    def binds(
        self, *, claim: str | None, premises: tuple[str, ...], rule: str | None
    ) -> tuple[bool, str]:
        """Whether this attestation is about the thing being checked.

        Returns ``(ok, reason)``. A certificate that is perfectly valid for a *different*
        claim is exactly the replay attack this guards, so a mismatch is a refusal rather
        than a warning.
        """
        if claim is not None and self.claim_digest != proposition_digest(claim):
            return False, (
                f"attestation {self.evidence_id!r} was issued for a different proposition "
                f"than the one it is being applied to"
            )
        expected = tuple(proposition_digest(p) for p in premises)
        if self.premise_digests != expected:
            return False, (
                f"attestation {self.evidence_id!r} was checked against different premises "
                f"than the action declares"
            )
        if rule is not None and self.rule != rule:
            return False, (
                f"attestation {self.evidence_id!r} certifies {self.rule!r}, not {rule!r}"
            )
        return True, ""


def attest(
    evidence_id: str,
    checked: CheckedEvidence,
    *,
    claim: str,
    premises: tuple[str, ...],
    rule: str | None = None,
) -> Attestation:
    """Wrap a minted :class:`CheckedEvidence` as an :class:`Attestation`.

    Refuses anything that is not genuinely minted, by consulting the **mint token**.

    The first version of this function duck-typed on the presence of ``envelope`` and
    ``checker``, reasoning that "a subclass could be declared anywhere". That inverted the
    risk and was forgeable: ``SimpleNamespace(envelope=..., checker=...)`` passed, and the
    resulting attestation was indistinguishable downstream from a real one. ``isinstance``
    would in fact have caught exactly that. The genuinely unforgeable fact is the private
    sentinel ``certificates._MINT``, which only ``certificates.check`` ever attaches, so
    that is what is checked here — attribute shape is not identity.
    """
    from ..reasoning import certificates as _certs

    if not isinstance(checked, _certs.CheckedEvidence) or (
        getattr(checked, "_token", None) is not _certs._MINT
    ):
        raise AttestationError(
            "attest() requires a CheckedEvidence minted by "
            "reasoning.certificates.check(); an object of the right shape is not one"
        )
    envelope = checked.envelope
    checker = checked.checker
    return Attestation(
        evidence_id=evidence_id,
        evidence=checked,
        claim_digest=proposition_digest(claim),
        premise_digests=tuple(proposition_digest(p) for p in premises),
        rule=rule,
        checker=str(checker),
        checker_version=str(getattr(envelope, "certificate_version", "")),
    )
