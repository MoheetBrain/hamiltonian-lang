"""The adapter must speak the federation's vocabulary without loosening it.

``improvement/verification.py`` is not modified by the obligation package; the adapter
implements its ``Verifier`` protocol from outside. Two things are asserted here:

1. every verdict maps to the *pessimistic* federation status — in particular, a
   ``SUPPORTED_AND_VERIFIED`` is emitted only when nothing remains open, which the
   federation's own ``__post_init__`` also enforces;
2. the documented consequence is real: registering this verifier does **not**, by
   itself, let ``classify`` return ``VERIFIED``, because ``TypeCheckVerifier`` still
   reports every collected obligation as remaining. That is a decision for the owner of
   that file, and the test pins the current behaviour so the decision is taken
   deliberately rather than drifted into.
"""

from __future__ import annotations

from hamiltonian_lang.improvement.verification import (
    Candidate,
    CandidateLanguage,
    CanonicalObject,
    VerifierStatus,
    classify,
    default_federation,
)
from hamiltonian_lang.verification.obligations import ObligationDischargeVerifier

VERIFIABLE = "module M\nvar x : Real\nrequire x >= 0\nprove (x + 1)^2 = x^2 + 2 * x + 1\n"
REFUTED = "module M\nrequire 2 + 3 = 6\n"
OUT_OF_SUBSET = "module M\nprove exists y : Real . forall x : Real . y > x\n"


def _run(source: str, language: CandidateLanguage = CandidateLanguage.HML):
    verifier = ObligationDischargeVerifier()
    return verifier.verify(CanonicalObject("t"), Candidate(source, language))


def test_a_verified_module_maps_to_supported_and_verified() -> None:
    result = _run(VERIFIABLE)
    assert result.status is VerifierStatus.SUPPORTED_AND_VERIFIED
    assert result.obligations_remaining == ()
    assert result.verified


def test_a_refuted_module_maps_to_failed_with_a_counterexample() -> None:
    result = _run(REFUTED)
    assert result.status is VerifierStatus.SUPPORTED_AND_FAILED
    assert result.counterexample is not None
    assert result.counterexample.witness


def test_an_out_of_subset_module_is_inconclusive_not_unsupported_silence() -> None:
    result = _run(OUT_OF_SUBSET)
    assert result.status is VerifierStatus.INCONCLUSIVE
    assert result.obligations_remaining
    assert "outside the supported subset" in result.detail


def test_a_non_hml_candidate_is_unsupported_with_a_reason() -> None:
    result = _run("theorem t : True := trivial", CandidateLanguage.LEAN)
    assert result.status is VerifierStatus.UNSUPPORTED
    assert result.detail.strip()


def test_the_adapter_never_claims_verified_with_an_open_obligation() -> None:
    for source in (VERIFIABLE, REFUTED, OUT_OF_SUBSET, "module M\n"):
        result = _run(source)
        if result.status is VerifierStatus.SUPPORTED_AND_VERIFIED:
            assert result.obligations_remaining == ()
            assert result.counterexample is None


def test_the_evidence_is_reproducible() -> None:
    a, b = _run(VERIFIABLE), _run(VERIFIABLE)
    assert a.evidence["evidence_digest"] == b.evidence["evidence_digest"]
    assert a.evidence_hash == b.evidence_hash


def test_the_federation_verifies_once_the_adapter_discharges_the_obligations() -> None:
    """MIGRATED by D-025. This pinned the opposite, and that is why the change is here.

    It asserted that registering this adapter could not by itself make the federation
    reach ``VERIFIED``, because ``TypeCheckVerifier`` reports every collected obligation
    as remaining and ``classify`` blocked on any remaining obligation. That was honest
    for the type checker in isolation, and holding it as a *test* rather than a sentence
    is what forced the Lead to decide deliberately instead of drifting.

    The decision taken: composition belongs in ``classify``. An obligation is remaining
    only when no verifier discharged it, and a verifier that reported ``INCONCLUSIVE``
    *because* obligations were open is resolved once those exact obligations are
    discharged elsewhere. ``TypeCheckVerifier`` was left honest and unchanged.

    Two details were needed to make it sound, both found by measurement:
    the adapter must report obligations under the compiler's own
    ``kind:statement`` descriptor as well as its internal id, or the two naming schemes
    never intersect; and ``obligations_checked`` must carry only *discharged* records,
    because an UNSUPPORTED record listed as checked made an undecidable ``forall``
    classify as ``VERIFIED``.
    """
    federation = default_federation()
    results = [
        v.verify(CanonicalObject("t", source=VERIFIABLE), Candidate(VERIFIABLE))
        for v in federation.verifiers
    ]
    assert any(
        r.verifier_name == "obligation_discharge"
        and r.status is VerifierStatus.SUPPORTED_AND_VERIFIED
        for r in results
    )
    type_check = next(r for r in results if r.verifier_name == "type_checker")
    assert type_check.obligations_remaining, "the premise of this test has changed"
    assert classify(results) == "VERIFIED"
