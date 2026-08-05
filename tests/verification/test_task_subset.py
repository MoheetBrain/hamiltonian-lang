"""The H3 task filter: what it admits, what it refuses, and what it publishes.

A filter that only admits the tasks the verifier happens to handle, and says nothing
about the rest, makes H3 unfalsifiable. So the tests check three things: the criteria
bite, the exclusions are reported with reasons, and the two arms cannot silently receive
different problems.
"""

from __future__ import annotations

import pytest
from evaluation.m3.verification.task_subset import (
    EXCLUDED_DOMAINS,
    SUBSET_POLICY_VERSION,
    Task,
    admit,
    assert_parity,
    build_subset,
    load_fixture_tasks,
    paired_roster,
)


def _task(task_id: str, solution: str) -> Task:
    return Task(task_id, f"encode {task_id}", solution)


def test_a_mechanically_checkable_task_is_admitted() -> None:
    decision = admit(
        _task("ok", "module M\nvar x : Real\nrequire x >= 0\nprove x^2 >= 0\n")
    )
    assert decision.admitted
    assert decision.verdict == "VERIFIED"
    assert decision.reasons, "an admission must state why, not only that"


def test_a_task_whose_key_does_not_compile_is_excluded() -> None:
    decision = admit(_task("broken", "module M\nrequire x > nope\n"))
    assert not decision.admitted
    assert any("does not compile" in r for r in decision.reasons)


def test_a_task_with_an_out_of_subset_obligation_is_excluded() -> None:
    decision = admit(
        _task("quant", "module M\nprove exists y : Real . forall x : Real . y > x\n")
    )
    assert not decision.admitted
    assert any("outside the implemented subset" in r for r in decision.reasons)
    assert decision.unsupported_statements


def test_a_task_passed_only_by_definitional_discharge_is_excluded() -> None:
    """`param s : PositiveReal` verifies, but checking it establishes nothing."""
    decision = admit(_task("free", "module M\nparam s : PositiveReal\n"))
    assert not decision.admitted
    assert any("definitional" in r for r in decision.reasons)


def test_the_substantive_requirement_can_be_relaxed_but_is_on_by_default() -> None:
    task = _task("free", "module M\nparam s : PositiveReal\n")
    assert not admit(task).admitted
    assert admit(task, require_substantive=False).admitted


def test_a_refuted_key_is_not_a_key() -> None:
    decision = admit(_task("wrong", "module M\nrequire 2 + 3 = 6\n"))
    assert not decision.admitted
    assert any("refuted" in r for r in decision.reasons)


def test_the_report_publishes_every_exclusion_and_its_reason() -> None:
    report = build_subset(load_fixture_tasks())
    assert report.policy_version == SUBSET_POLICY_VERSION
    assert report.admitted and report.excluded
    assert len(report.admitted) + len(report.excluded) == len(report.decisions)
    counts = report.exclusion_counts()
    assert counts and sum(counts.values()) >= len(report.excluded)
    for decision in report.excluded:
        assert decision.reasons, decision.task_id


def test_the_report_names_the_excluded_domains_before_any_task_is_seen() -> None:
    payload = build_subset([]).to_dict()
    domains = payload["excluded_domains"]
    assert len(domains) == len(EXCLUDED_DOMAINS) >= 6
    for entry in domains:
        assert entry["domain"] and entry["why"] and entry["what_would_admit_it"]


def test_arm_parity_is_enforced_on_ids_and_on_text() -> None:
    tasks = [_task("a", "module A\nrequire 1 = 1\n"), _task("b", "module B\nrequire 2 = 2\n")]
    report = build_subset(tasks, require_substantive=False)
    roster, digests = paired_roster(tasks, report)
    assert len(roster) == 2

    assert_parity(digests, dict(digests))

    with pytest.raises(ValueError, match="same task ids"):
        assert_parity(digests, {"a": digests["a"]})

    drifted = dict(digests)
    drifted["b"] = "0" * 64
    with pytest.raises(ValueError, match="different problem text"):
        assert_parity(digests, drifted)


def test_the_roster_contains_only_admitted_tasks() -> None:
    tasks = load_fixture_tasks()
    report = build_subset(tasks)
    roster, digests = paired_roster(tasks, report)
    admitted_ids = {d.task_id for d in report.admitted}
    assert {t.task_id for t in roster} == admitted_ids
    assert set(digests) == admitted_ids


def test_the_admitted_set_is_not_empty_and_not_everything() -> None:
    """A filter that admits nothing is unusable; one that admits everything is not a filter."""
    report = build_subset(load_fixture_tasks())
    assert 0 < len(report.admitted) < len(report.decisions)
    assert 0.0 < report.coverage() < 1.0
