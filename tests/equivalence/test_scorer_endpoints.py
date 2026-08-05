"""End-to-end: the endpoints ask different questions and get different answers.

This is CONF-003 made executable. The same pair -- an equivalent encoding with a
different shape -- must be *not preserved* under ACQ0 and *equivalent* under the
H1/H2 encoding endpoint. If those two ever agree, the bug this package was written
to fix has come back.
"""

from __future__ import annotations

from hamiltonian_lang.equivalence import (
    AdjudicationQueue,
    AnswerSpec,
    Endpoint,
    EquivalenceScorer,
    EquivalenceStatus,
)

REFERENCE = "module M\nparam a : Real\ndef f := (a + 1) * (a + 1)\n"
EQUIVALENT_RESHAPE = "module M\nparam a : Real\ndef f := a^2 + 2 * a + 1\n"


def test_the_two_endpoints_disagree_and_that_is_the_point():
    scorer = EquivalenceScorer()
    acq0 = scorer.compare(
        REFERENCE, EQUIVALENT_RESHAPE, endpoint=Endpoint.ACQ0_EXACT_PRESERVATION
    )
    h1h2 = scorer.compare(
        REFERENCE, EQUIVALENT_RESHAPE, endpoint=Endpoint.ENCODING_EQUIVALENCE
    )
    assert acq0.exact_preservation is False
    assert acq0.status is EquivalenceStatus.INCONCLUSIVE
    assert not acq0.is_negative, "a hash mismatch is not a claim of mathematical error"
    assert h1h2.status is EquivalenceStatus.VERIFIED_EQUIVALENT


def test_acq0_consults_no_tier_below_the_hash():
    report = EquivalenceScorer().compare(
        REFERENCE, EQUIVALENT_RESHAPE, endpoint=Endpoint.ACQ0_EXACT_PRESERVATION
    )
    tiers = {str(o.tier) for o in report.outcomes}
    assert tiers == {"TIER0_CANONICAL_IDENTITY"}


def test_an_exact_match_satisfies_every_endpoint():
    for endpoint in Endpoint:
        report = EquivalenceScorer().compare(REFERENCE, REFERENCE, endpoint=endpoint)
        assert report.exact_preservation is True
        if endpoint is not Endpoint.FINAL_ANSWER:
            assert report.status is EquivalenceStatus.VERIFIED_EQUIVALENT


def test_a_non_compiling_candidate_is_recorded_not_scored_wrong():
    report = EquivalenceScorer().compare(REFERENCE, "module M\nparam a : Nonsense\n")
    assert report.candidate_compiles is False
    assert report.status is EquivalenceStatus.UNSUPPORTED
    assert not report.is_negative
    assert report.diagnostics


def test_a_non_compiling_reference_says_nothing_about_the_candidate():
    report = EquivalenceScorer().compare("module M\nparam a : Nonsense\n", REFERENCE)
    assert report.reference_compiles is False
    assert report.status is EquivalenceStatus.UNSUPPORTED
    assert not report.is_negative


def test_the_answer_endpoint_scores_the_answer_even_without_a_working_encoding():
    report = EquivalenceScorer().compare(
        REFERENCE,
        "module M\nparam a : Nonsense\n",
        endpoint=Endpoint.FINAL_ANSWER,
        answer_spec=AnswerSpec("4"),
        candidate_answer="4",
    )
    assert report.candidate_compiles is False
    assert report.answer is not None
    assert report.answer.status is EquivalenceStatus.VERIFIED_CORRECT_ANSWER


def test_a_right_answer_never_becomes_an_equivalence_claim():
    report = EquivalenceScorer().compare(
        REFERENCE,
        "module M\nparam a : Real\ndef f := a^3\n",
        endpoint=Endpoint.FINAL_ANSWER,
        answer_spec=AnswerSpec("4"),
        candidate_answer="4",
    )
    assert report.status is EquivalenceStatus.VERIFIED_CORRECT_ANSWER
    assert report.status is not EquivalenceStatus.VERIFIED_EQUIVALENT


def test_undecided_pairs_are_queued_rather_than_dropped():
    queue = AdjudicationQueue()
    scorer = EquivalenceScorer(queue=queue)
    # Under a matching quantifier prefix the bodies are a *fragment*, which may be
    # certified but never refuted. Neither happens here, so the pair is unresolved.
    report = scorer.compare(
        "module M\nprove forall x : Real . exists y : Real . y > x\n",
        "module M\nprove forall x : Real . exists y : Real . y >= x + 1\n",
        item_id="quantified-pair",
    )
    assert report.status is EquivalenceStatus.INCONCLUSIVE
    assert not report.is_negative
    assert len(queue) == 1
    assert queue.items[0].item_id == "quantified-pair"
    assert queue.items[0].reason


def test_a_body_under_a_matching_quantifier_prefix_can_still_be_certified():
    report = EquivalenceScorer().compare(
        "module M\nprove forall x : Real . x * x >= 0\n",
        "module M\nprove forall x : Real . x^2 >= 0\n",
    )
    assert report.status is EquivalenceStatus.VERIFIED_EQUIVALENT


def test_the_report_serialises_without_losing_the_verdict():
    report = EquivalenceScorer().compare(REFERENCE, EQUIVALENT_RESHAPE)
    payload = report.to_dict()
    assert payload["status"] == "VERIFIED_EQUIVALENT"
    assert payload["decided_by"] == "TIER2_SYMBOLIC"
    assert payload["exact_preservation"] is False
    assert payload["protocol_version"].startswith("hml-equivalence-")


def test_tier_order_is_cheapest_first():
    report = EquivalenceScorer().compare(REFERENCE, EQUIVALENT_RESHAPE)
    order = [str(o.tier) for o in report.outcomes]
    assert order[0] == "TIER0_CANONICAL_IDENTITY"
    assert order[1] == "TIER1_ALPHA_NORMALISATION"
