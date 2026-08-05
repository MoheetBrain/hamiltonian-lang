"""Tier 4 -- answer verification, and the line between a right answer and equivalence."""

from __future__ import annotations

import pytest

from hamiltonian_lang.equivalence import AnswerSpec, EquivalenceStatus, verify_answer


def test_an_exact_match_is_a_correct_answer_and_not_an_equivalence():
    result = verify_answer(AnswerSpec("2.5"), "2.5")
    assert result.status is EquivalenceStatus.VERIFIED_CORRECT_ANSWER
    assert result.certificate is not None
    assert result.certificate.certifies_equivalence is False


@pytest.mark.parametrize("actual", ["0.5", "1/2", "2^-1", " 0.500 "])
def test_different_spellings_of_the_same_number_agree(actual):
    assert (
        verify_answer(AnswerSpec("0.5", kind="exact"), actual).status
        is EquivalenceStatus.VERIFIED_CORRECT_ANSWER
    )


def test_a_wrong_answer_is_reported_with_the_expected_value():
    result = verify_answer(AnswerSpec("2.5"), "3.0")
    assert result.status is EquivalenceStatus.COUNTEREXAMPLE_FOUND
    assert result.counterexample is not None
    assert result.counterexample.left_value.startswith("5/2")


def test_tolerance_is_relative_and_respected():
    assert (
        verify_answer(AnswerSpec("1000", tolerance=1e-3), "1000.5").status
        is EquivalenceStatus.VERIFIED_CORRECT_ANSWER
    )
    assert (
        verify_answer(AnswerSpec("1000", tolerance=1e-9), "1000.5").status
        is EquivalenceStatus.COUNTEREXAMPLE_FOUND
    )


def test_a_missing_answer_is_not_a_wrong_answer():
    for value in (None, "", "   "):
        result = verify_answer(AnswerSpec("2.5"), value)
        assert result.status is EquivalenceStatus.INCONCLUSIVE
        assert not result.is_negative


def test_an_unparseable_answer_is_inconclusive_not_wrong():
    result = verify_answer(AnswerSpec("2.5"), "about two and a half")
    assert result.status is EquivalenceStatus.INCONCLUSIVE
    assert not result.is_negative


def test_an_unparseable_expectation_is_unsupported():
    result = verify_answer(AnswerSpec("whatever the model says"), "2.5")
    assert result.status is EquivalenceStatus.UNSUPPORTED


def test_mismatched_units_decline_rather_than_guess():
    result = verify_answer(AnswerSpec("100", unit="metres"), "100 seconds")
    assert result.status is EquivalenceStatus.INCONCLUSIVE
    assert "unit algebra" in result.detail


def test_matching_units_are_compared():
    assert (
        verify_answer(AnswerSpec("100", unit="metres"), "100 metres").status
        is EquivalenceStatus.VERIFIED_CORRECT_ANSWER
    )


def test_a_solution_set_is_compared_as_a_multiset():
    spec = AnswerSpec("{1, 2, 3}", kind="set")
    assert verify_answer(spec, "3, 1, 2").status is EquivalenceStatus.VERIFIED_CORRECT_ANSWER
    assert verify_answer(spec, "1, 2").status is EquivalenceStatus.COUNTEREXAMPLE_FOUND
    assert verify_answer(spec, "1, 2, 3, 4").status is EquivalenceStatus.COUNTEREXAMPLE_FOUND


def test_an_unknown_answer_kind_is_rejected_at_construction():
    with pytest.raises(ValueError, match="unknown answer kind"):
        AnswerSpec("1", kind="vibes")
