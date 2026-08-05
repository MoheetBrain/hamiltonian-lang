"""The paired benchmark, run as a gate.

The binding criterion is precision, not coverage: **no false-positive
equivalences**. A false positive declares a wrong answer right and corrupts every
H1/H2 number computed downstream; a false negative only costs coverage, and is
recorded rather than tolerated silently.
"""

from __future__ import annotations

import pytest
from evaluation.m3.equivalence import CATEGORIES, EQUIVALENT, NONEQUIVALENT, PAIRS
from evaluation.m3.equivalence.run import run_benchmark

from hamiltonian_lang import compile_source


@pytest.fixture(scope="module")
def result():
    return run_benchmark()


@pytest.mark.parametrize("case", PAIRS, ids=lambda c: c.case_id)
def test_every_benchmark_source_compiles(case):
    for label, source in (("reference", case.reference), ("candidate", case.candidate)):
        compiled = compile_source(source)
        assert compiled.ok(), f"{case.case_id} {label}:\n{compiled.diagnostics.render()}"


def test_no_false_positive_equivalence(result):
    """The approval criterion. Zero, not "few"."""
    assert result.false_positives == (), [c.case.case_id for c in result.false_positives]
    assert result.equivalence_precision == 1.0


def test_no_false_negative_either(result):
    """Not a hard gate elsewhere, but a regression here would bias H1/H2 downward."""
    assert result.false_negatives == (), [c.case.case_id for c in result.false_negatives]


def test_precision_over_the_decided_pairs_is_perfect(result):
    assert result.precision == 1.0
    assert result.nonequivalence_precision == 1.0


def test_measured_coverage_is_recorded_and_does_not_regress(result):
    # Measured on this machine at 49/49. Pinned below the measurement so a genuine
    # improvement does not fail the gate, and a real regression does.
    assert result.coverage >= 0.90, result.render()


def test_every_category_is_populated(result):
    for name in CATEGORIES:
        assert result.per_category[name]["n"] > 0, f"category {name} has no pairs"


def test_the_corpus_contains_both_truths(result):
    truths = {c.truth for c in PAIRS}
    assert truths == {EQUIVALENT, NONEQUIVALENT}


@pytest.mark.parametrize(
    "case_id",
    [
        "adversarial.implication_direction",
        "adversarial.quantifier_order",
        "adversarial.pvalue_posterior",
        "adversarial.power_association",
        "adversarial.division_for_multiplication",
    ],
)
def test_the_five_named_adversarial_pairs_come_out_non_equivalent(result, case_id):
    row = next(c for c in result.cases if c.case.case_id == case_id)
    assert row.verdict == NONEQUIVALENT, f"{case_id}: {row.status} -- {row.detail}"


def test_the_result_serialises_with_the_numbers_a_reader_needs(result):
    payload = result.to_dict()
    for key in (
        "coverage",
        "precision",
        "equivalence_precision",
        "nonequivalence_precision",
        "false_positive_equivalences",
        "false_negatives",
        "undecided",
    ):
        assert key in payload


def test_scoring_the_corpus_is_deterministic():
    first, second = run_benchmark(), run_benchmark()
    assert [c.status for c in first.cases] == [c.status for c in second.cases]
