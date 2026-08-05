"""An adapter that speaks the existing verifier-federation protocol.

:mod:`hamiltonian_lang.improvement.verification` is **not modified by this package**.
This adapter implements its ``Verifier`` protocol from the outside, so the Lead can
register it — or not — without any change here being a change there.

One thing the Lead must decide, stated plainly rather than worked around
--------------------------------------------------------------------------
``improvement.verification.classify`` returns ``INCONCLUSIVE`` whenever *any* result
carries ``obligations_remaining``, and ``TypeCheckVerifier`` unconditionally reports
every obligation the checker collected as remaining. So adding this verifier to
``default_federation()`` does **not**, on its own, make the federation reach
``VERIFIED``: the type checker's own report would still block it, correctly, because
the type checker really has not discharged those obligations.

Making the federation reach ``VERIFIED`` requires one deliberate change inside
``improvement/verification.py`` — either ``TypeCheckVerifier`` consults this engine and
reports only the *undischarged* obligations as remaining, or ``classify`` treats an
obligation as remaining only when no verifier discharged it. Both are edits to a file
this agent does not own, so neither is made here.

Until that decision is taken, the reachable ``VERIFIED`` endpoint is
:func:`hamiltonian_lang.verification.obligations.verify_source`, which applies the same
conjunction end to end and is what the H3 harness measures.
"""

from __future__ import annotations

from typing import Any

from ...improvement.verification import (
    Candidate,
    CandidateLanguage,
    CanonicalObject,
    Counterexample,
    SemanticLoss,
    SupportDecision,
    VerificationResult,
    VerifierStatus,
)
from .engine import ENGINE_VERSION, GlobalVerdict, verify_source
from .records import ObligationStatus

__all__ = ["ObligationDischargeVerifier"]


class ObligationDischargeVerifier:
    """Reports the obligation engine's verdict in the federation's vocabulary."""

    name = "obligation_discharge"
    version = ENGINE_VERSION

    def supports(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> SupportDecision:
        if candidate.language is not CandidateLanguage.HML:
            return SupportDecision(
                False,
                f"the obligation engine reads HML; this candidate is {candidate.language}",
                missing_capability=(f"{candidate.language}-frontend",),
            )
        if not candidate.text.strip():
            return SupportDecision(False, "the candidate is empty; there is nothing to check")
        return SupportDecision(True)

    def verify(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> VerificationResult:
        decision = self.supports(canonical_object, candidate)
        if not decision.supported:
            return VerificationResult(
                verifier_name=self.name,
                verifier_version=self.version,
                status=VerifierStatus.UNSUPPORTED,
                detail=decision.reason,
                evidence={"missing_capability": list(decision.missing_capability)},
            )

        outcome = verify_source(candidate.text)
        # Each obligation is reported under BOTH names: this engine's stable id and the
        # compiler's own `kind:description` descriptor, which is what `TypeCheckVerifier`
        # emits. Without the second, the two verifiers name the same obligation
        # differently -- `OBL-000-7fe9b36c` against `theorem:2.0 + 2.0 = 4.0` -- and the
        # federation's discharged-set difference can never match, so a fully discharged
        # module still classifies INCONCLUSIVE. `source_kind` exists precisely to keep the
        # compiler's kind verbatim; this is what it is for. (D-025.)
        def _names(record: Any) -> tuple[str, ...]:
            names = [record.obligation_id]
            if record.source_kind:
                names.append(f"{record.source_kind}:{record.statement}")
            return tuple(names)

        # `checked` carries only *discharged* obligations. Listing an obligation as both
        # checked and remaining is self-contradictory, and `classify` builds its
        # discharged-set from this field: including an UNSUPPORTED record here made an
        # undecidable `forall` classify as VERIFIED, which is precisely the "weaken
        # VERIFIED until everything reaches it" failure the endpoint exists to avoid.
        checked = tuple(n for r in outcome.records if r.discharged for n in _names(r))
        remaining = tuple(
            n for r in outcome.records if not r.discharged for n in _names(r)
        )
        evidence: dict[str, Any] = {
            "counts": outcome.counts(),
            "by_class": outcome.by_class(),
            "substantive": outcome.substantive,
            "engine_version": outcome.engine_version,
            "evidence_digest": outcome.evidence_digest(),
        }

        if outcome.verdict is GlobalVerdict.INVALID:
            return VerificationResult(
                verifier_name=self.name,
                verifier_version=self.version,
                status=VerifierStatus.INVALID,
                obligations_remaining=remaining,
                detail=outcome.detail,
                evidence={**evidence, "codes": list(outcome.diagnostics)},
            )
        if outcome.verdict is GlobalVerdict.SEMANTIC_LOSS:
            return VerificationResult(
                verifier_name=self.name,
                verifier_version=self.version,
                status=VerifierStatus.SEMANTIC_LOSS,
                obligations_remaining=remaining,
                semantic_loss=tuple(
                    SemanticLoss(loss.construct, loss.reason, loss.severity)
                    for loss in outcome.semantic_loss
                ),
                detail=outcome.detail,
                evidence=evidence,
            )
        if outcome.verdict is GlobalVerdict.DISPROVED:
            failure = outcome.first_failure()
            assert failure is not None and failure.witness is not None
            return VerificationResult(
                verifier_name=self.name,
                verifier_version=self.version,
                status=VerifierStatus.SUPPORTED_AND_FAILED,
                obligations_checked=checked,
                obligations_remaining=remaining,
                counterexample=Counterexample(
                    description=failure.witness.description,
                    witness=failure.witness.evaluated
                    or "; ".join(f"{k} = {v}" for k, v in failure.witness.bindings.items()),
                    produced_by=f"{self.name}/{failure.checker}",
                ),
                detail=f"{failure.obligation_id}: {failure.detail}",
                evidence=evidence,
            )
        if outcome.verdict is GlobalVerdict.VERIFIED:
            return VerificationResult(
                verifier_name=self.name,
                verifier_version=self.version,
                status=VerifierStatus.SUPPORTED_AND_VERIFIED,
                obligations_checked=checked,
                detail=outcome.detail,
                evidence=evidence,
            )
        unsupported = sum(
            1 for r in outcome.records if r.status is ObligationStatus.UNSUPPORTED
        )
        return VerificationResult(
            verifier_name=self.name,
            verifier_version=self.version,
            status=VerifierStatus.INCONCLUSIVE,
            obligations_checked=checked,
            obligations_remaining=remaining,
            detail=f"{outcome.detail} ({unsupported} outside the supported subset)",
            evidence=evidence,
        )
