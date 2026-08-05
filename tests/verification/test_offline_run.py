"""The offline evidence run: it succeeds, it is deterministic, and it can fail.

Reproducibility is the whole point of the evidence file. Two runs on the same commit
must produce identical JSON — no clocks, no randomness, no network — otherwise "the
evidence" is a snapshot of a mood rather than a derivation.
"""

from __future__ import annotations

import json

from evaluation.m3.verification.run_offline import build_report, main


def test_the_offline_run_exits_clean() -> None:
    assert main([]) == 0


def test_the_report_is_byte_identical_across_runs() -> None:
    first = json.dumps(build_report(), sort_keys=True)
    second = json.dumps(build_report(), sort_keys=True)
    assert first == second


def test_the_report_states_that_it_made_no_model_call() -> None:
    report = build_report()
    assert report["offline"] is True
    assert report["model_calls"] == 0


def test_every_fixture_matches_its_declared_verdict() -> None:
    report = build_report()
    assert report["fixture_conformance"]["mismatches"] == 0
    assert report["fixture_conformance"]["fixtures"]


def test_the_corpus_section_reports_a_reachable_and_incomplete_coverage() -> None:
    """Both halves matter: reachable means the endpoint exists, incomplete means it bites."""
    coverage = build_report()["corpus_coverage"]
    assert coverage["total"] >= 15
    assert coverage["verified"] >= 10
    assert coverage["verified"] < coverage["total"]
    assert coverage["verified_substantively"] >= 6


def test_the_h3_subset_is_a_proper_subset() -> None:
    subset = build_report()["h3_task_subset"]
    assert 0 < subset["admitted"] < subset["total"]
    assert subset["exclusion_counts"]


def test_the_leakage_section_shows_the_guard_firing_on_a_leak_and_not_on_a_safe_one() -> None:
    probe = build_report()["leakage_control"]["guard_probe"]
    assert probe["leaky_diagnostic_rejected"] is True
    assert probe["safe_diagnostic_rejected"] is False


def test_the_scripted_conditions_are_admissible() -> None:
    conditions = build_report()["leakage_control"]["conditions"]
    assert conditions["rates"]["C"] > conditions["rates"]["A"]
    assert conditions["rates"]["C"] > conditions["rates"]["D"]
    assert conditions["admissible"] is True


def test_the_report_names_the_supported_classes_it_claims() -> None:
    report = build_report()
    assert len(report["supported_classes"]) == 9
    assert "out_of_subset" not in report["supported_classes"]


def test_the_process_section_carries_the_endpoint_alongside_the_metrics() -> None:
    from evaluation.m3.verification.process_metrics import assert_reported_with_endpoint

    section = build_report()["process_metrics"]
    assert_reported_with_endpoint(section["before_repair"])
    assert_reported_with_endpoint(section["after_repair"])
    assert section["repair_effect"]["verified_after"] is True
    assert section["repair_effect"]["regression"] is False
