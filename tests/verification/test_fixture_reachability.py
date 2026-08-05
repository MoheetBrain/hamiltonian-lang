"""The approval criteria, driven by the fixture manifest.

Four claims, each of which would be worthless without the other three:

* a positive fixture reaches ``VERIFIED`` — the endpoint is *reachable*;
* an invalid fixture does not — the endpoint can *fail*;
* an unsupported fixture stays outside the subset — the gap is *visible*;
* the corpus figure is measured rather than asserted — the coverage claim is *checked*.

The manifest is the source of truth. A fixture whose verdict drifts is a regression in
the engine, and relabelling the manifest to make this file pass would be the exact
failure it exists to catch.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from hamiltonian_lang.verification.obligations import (
    SUPPORTED_CLASSES,
    GlobalVerdict,
    ObligationClass,
    ObligationStatus,
    verify_source,
)

REPO = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = REPO / "evaluation" / "m3" / "verification" / "fixtures"
MANIFEST = json.loads((FIXTURES / "MANIFEST.json").read_text())
ENTRIES = MANIFEST["fixtures"]


@pytest.mark.parametrize("entry", ENTRIES, ids=[e["file"] for e in ENTRIES])
def test_each_fixture_reaches_the_verdict_its_manifest_declares(entry: dict) -> None:
    source = (FIXTURES / entry["file"]).read_text()
    outcome = verify_source(source, entry["file"])
    assert str(outcome.verdict) == entry["expected_verdict"], (
        f"{entry['file']}: expected {entry['expected_verdict']}, got {outcome.verdict}\n"
        + outcome.render()
    )
    assert outcome.substantive == entry["expected_substantive"], entry["file"]


@pytest.mark.parametrize(
    "entry",
    [e for e in ENTRIES if e["file"].startswith("positive_")],
    ids=[e["file"] for e in ENTRIES if e["file"].startswith("positive_")],
)
def test_positive_fixtures_make_verified_reachable(entry: dict) -> None:
    outcome = verify_source((FIXTURES / entry["file"]).read_text(), entry["file"])
    assert outcome.verdict is GlobalVerdict.VERIFIED
    assert outcome.substantive, "a positive fixture must not pass on definitional discharges"
    assert outcome.records, "a fixture with no obligation verifies vacuously"
    assert all(r.discharged for r in outcome.records)
    exercised = {str(r.obligation_class) for r in outcome.records}
    assert set(entry["exercises"]) <= exercised, entry["file"]


@pytest.mark.parametrize(
    "entry",
    [e for e in ENTRIES if e["file"].startswith("invalid_")],
    ids=[e["file"] for e in ENTRIES if e["file"].startswith("invalid_")],
)
def test_invalid_fixtures_fail(entry: dict) -> None:
    outcome = verify_source((FIXTURES / entry["file"]).read_text(), entry["file"])
    assert not outcome.verified
    assert outcome.verdict in (GlobalVerdict.DISPROVED, GlobalVerdict.INVALID)
    if outcome.verdict is GlobalVerdict.DISPROVED:
        failure = outcome.first_failure()
        assert failure is not None and failure.witness is not None


@pytest.mark.parametrize(
    "entry",
    [e for e in ENTRIES if e["file"].startswith("unsupported_")],
    ids=[e["file"] for e in ENTRIES if e["file"].startswith("unsupported_")],
)
def test_unsupported_fixtures_stay_outside_the_subset(entry: dict) -> None:
    outcome = verify_source((FIXTURES / entry["file"]).read_text(), entry["file"])
    assert outcome.verdict is GlobalVerdict.UNSUPPORTED
    unsupported = [r for r in outcome.records if r.status is ObligationStatus.UNSUPPORTED]
    assert unsupported
    for record in unsupported:
        assert record.detail.strip(), "an unexplained skip is indistinguishable from nothing"
        assert record.status is not ObligationStatus.DISCHARGED


def test_the_fixture_set_covers_every_supported_class() -> None:
    exercised: set[str] = set()
    for entry in ENTRIES:
        outcome = verify_source((FIXTURES / entry["file"]).read_text(), entry["file"])
        exercised |= {str(r.obligation_class) for r in outcome.records}
    missing = {str(c) for c in SUPPORTED_CLASSES} - exercised
    assert not missing, f"no fixture exercises: {sorted(missing)}"


def _corpus() -> list[pathlib.Path]:
    return [
        p
        for p in sorted((REPO / "examples").rglob("*.hml"))
        if not any((parent / ".illustrative").exists() for parent in p.parents)
    ]


def test_verified_is_reachable_on_the_shipped_example_corpus() -> None:
    """The measured figure, asserted as a floor rather than quoted from a report."""
    outcomes = [verify_source(p.read_text(), str(p)) for p in _corpus()]
    verified = [o for o in outcomes if o.verdict is GlobalVerdict.VERIFIED]
    assert len(outcomes) >= 15
    assert len(verified) >= 10, (
        f"only {len(verified)}/{len(outcomes)} examples verify; "
        f"the reported coverage would be stale"
    )
    assert sum(1 for o in verified if o.substantive) >= 6


def test_no_example_is_verified_through_an_out_of_subset_obligation() -> None:
    for path in _corpus():
        outcome = verify_source(path.read_text(), str(path))
        if outcome.verdict is not GlobalVerdict.VERIFIED:
            continue
        for record in outcome.records:
            assert record.obligation_class is not ObligationClass.OUT_OF_SUBSET, path
            assert record.status is ObligationStatus.DISCHARGED, path
