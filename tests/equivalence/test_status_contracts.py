"""The asymmetry must live in the types, not in a comment.

These tests are the executable form of the rule "failing to find a counterexample
is not a proof of equivalence". If any of them is deleted, the block it enforces is
gone and the next author will not notice.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.equivalence import (
    ANSWER_METHODS,
    CERTIFYING_METHODS,
    NEGATIVE_STATUSES,
    REFUTING_METHODS,
    SEARCH_ONLY_METHODS,
    Assumption,
    Certificate,
    Counterexample,
    EquivalenceResult,
    EquivalenceStatus,
    NonEquivalenceProof,
    NoRefutation,
    SemanticLossNote,
    Tier,
    register_certifying_method,
)


def test_the_counterexample_searcher_is_not_a_certifying_method():
    assert "tier3.numeric_counterexample" not in CERTIFYING_METHODS
    assert "tier3.numeric_counterexample" in SEARCH_ONLY_METHODS
    assert "tier3.numeric_counterexample" in REFUTING_METHODS


def test_a_certificate_refuses_to_be_issued_by_a_search():
    with pytest.raises(ValueError, match="not an approved certifying method"):
        Certificate("tier3.numeric_counterexample", "found nothing, so they must agree")


def test_a_search_method_cannot_be_promoted_into_the_certifying_set():
    with pytest.raises(ValueError, match="not a proof of equivalence"):
        register_certifying_method("tier3.numeric_counterexample")
    assert "tier3.numeric_counterexample" not in CERTIFYING_METHODS


def test_no_refutation_is_a_different_class_and_never_certifies():
    empty = NoRefutation("tier3.numeric_counterexample", 400)
    assert empty.certifies_equivalence is False
    assert not isinstance(empty, Certificate)
    assert empty.to_dict()["certifies_equivalence"] is False


def test_a_search_that_found_nothing_cannot_support_a_negative_verdict_either():
    with pytest.raises(ValueError, match="cannot support a negative verdict"):
        EquivalenceResult(
            Tier.TIER3_COUNTEREXAMPLE_SEARCH,
            EquivalenceStatus.VERIFIED_NONEQUIVALENT,
            "nothing found, so they differ",
            proof=NonEquivalenceProof("tier3.numeric_counterexample", "nothing found"),
            no_refutation=NoRefutation("tier3.numeric_counterexample", 10),
        )


def test_verified_equivalent_requires_a_certificate():
    with pytest.raises(ValueError, match="requires a certificate"):
        EquivalenceResult(
            Tier.TIER2_SYMBOLIC, EquivalenceStatus.VERIFIED_EQUIVALENT, "trust me"
        )


def test_an_answer_certificate_cannot_support_an_equivalence_claim():
    answer = Certificate("tier4.final_answer_match", "expected 2, produced 2")
    assert answer.certifies_equivalence is False
    with pytest.raises(ValueError, match="answers the endpoint question"):
        EquivalenceResult(
            Tier.TIER4_ENDPOINT_ANSWER,
            EquivalenceStatus.VERIFIED_EQUIVALENT,
            "right answer",
            certificate=answer,
        )


def test_verified_nonequivalent_requires_a_proof_not_a_failed_check():
    with pytest.raises(ValueError, match="requires a proof"):
        EquivalenceResult(
            Tier.TIER2_SYMBOLIC,
            EquivalenceStatus.VERIFIED_NONEQUIVALENT,
            "simplify did not return zero",
        )


def test_counterexample_status_requires_the_witness():
    with pytest.raises(ValueError, match="requires the witness"):
        EquivalenceResult(
            Tier.TIER3_COUNTEREXAMPLE_SEARCH,
            EquivalenceStatus.COUNTEREXAMPLE_FOUND,
            "they disagree somewhere",
        )


def test_semantic_loss_must_name_what_was_lost():
    with pytest.raises(ValueError, match="must name what was lost"):
        EquivalenceResult(
            Tier.TIER2_SYMBOLIC, EquivalenceStatus.SEMANTIC_LOSS, "something went missing"
        )
    ok = EquivalenceResult(
        Tier.TIER2_SYMBOLIC,
        EquivalenceStatus.SEMANTIC_LOSS,
        "quantifier dropped",
        semantic_loss=(SemanticLossNote("forall", "no SymPy binder"),),
    )
    assert ok.status is EquivalenceStatus.SEMANTIC_LOSS


@pytest.mark.parametrize(
    "status",
    [
        EquivalenceStatus.INCONCLUSIVE,
        EquivalenceStatus.UNSUPPORTED,
        EquivalenceStatus.SEMANTIC_LOSS,
    ],
)
def test_undecided_statuses_are_never_failures(status):
    """The defect being fixed, pointed the other way, must stay impossible."""
    assert status not in NEGATIVE_STATUSES
    result = EquivalenceResult(Tier.TIER2_SYMBOLIC, status, "could not tell", **(
        {"semantic_loss": (SemanticLossNote("x", "y"),)}
        if status is EquivalenceStatus.SEMANTIC_LOSS
        else {}
    ))
    assert result.is_negative is False


def test_negative_statuses_are_exactly_the_two_with_evidence():
    assert NEGATIVE_STATUSES == {
        EquivalenceStatus.VERIFIED_NONEQUIVALENT,
        EquivalenceStatus.COUNTEREXAMPLE_FOUND,
    }


def test_inconclusive_and_unsupported_are_not_decisive_and_semantic_loss_is_not_either():
    for status in (
        EquivalenceStatus.INCONCLUSIVE,
        EquivalenceStatus.UNSUPPORTED,
    ):
        assert not EquivalenceResult(Tier.TIER2_SYMBOLIC, status, "x").decisive


def test_an_assumption_must_say_what_is_assumed():
    with pytest.raises(ValueError, match="must state what is assumed"):
        Assumption("   ")
    assert Assumption("a > 0", "declared type").to_dict()["statement"] == "a > 0"


def test_a_counterexample_must_describe_what_it_witnesses():
    with pytest.raises(ValueError, match="must describe"):
        Counterexample("tier3.numeric_counterexample", "")


def test_a_refuting_method_must_be_registered():
    with pytest.raises(ValueError, match="not an approved refuting method"):
        NonEquivalenceProof("guard.invented_out_of_thin_air", "because I said so")


def test_answer_methods_and_certifying_methods_are_disjoint():
    assert not (ANSWER_METHODS & CERTIFYING_METHODS)
