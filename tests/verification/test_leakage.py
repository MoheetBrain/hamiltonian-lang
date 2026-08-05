"""The four conditions, and the guard that must run before them.

Two failure modes are being defended against, and they pull in opposite directions:

* a diagnostic that **contains the answer** makes H3 measure copying. The guard rejects
  those, and the tests use a deliberately leaky diagnostic to prove the guard fires.
* a control that is **trivially recognisable as noise** makes condition D too easy to
  beat, which would make a useless diagnostic look useful. Hence the default D is a real
  diagnostic from a different task, not a word scramble.

Every arm here is a scripted function. Nothing in this file makes a model call.
"""

from __future__ import annotations

import pathlib

import pytest
from evaluation.m3.verification.leakage import (
    LEAK_THRESHOLD,
    Condition,
    Payload,
    assert_no_answer_leak,
    build_payload,
    find_answer_leak,
    mismatched_diagnostic,
    run_conditions,
    scrambled_diagnostic,
)

REPO = pathlib.Path(__file__).resolve().parents[2]

TARGET = "module Budget\n\nvar spend : NonNegativeReal\n\nrequire spend <= 100\nrequire spend >= 50\n"
BROKEN = "module Budget\n\nvar spend : NonNegativeReal\n\nrequire spend <= 100\nrequire spend >= 150\n"

SAFE = (
    "The constraint set has no model: an upper bound and a lower bound on the same "
    "variable intersect to the empty set. Reconsider which bound the problem states."
)
LEAKY_PROGRAM = (
    "The constraint set has no model. Replace the program with:\n" + TARGET
)
LEAKY_LINE = "The constraint set has no model. It should read: require spend >= 50"


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------


def test_a_diagnostic_that_embeds_the_target_program_is_rejected() -> None:
    findings = find_answer_leak(LEAKY_PROGRAM, TARGET, BROKEN)
    assert findings
    assert any(f.kind == "target_program_embedded" for f in findings)


def test_a_diagnostic_that_embeds_any_complete_program_is_rejected() -> None:
    other = "module Other\n\nvar y : Real\n\nrequire y >= 0\n"
    findings = find_answer_leak(f"Try this instead:\n{other}", TARGET, BROKEN)
    assert any(f.kind == "complete_program_embedded" for f in findings)


def test_a_diagnostic_that_quotes_the_corrected_line_is_rejected() -> None:
    """The 'here is the fixed line' leak, which neither program check catches."""
    findings = find_answer_leak(LEAKY_LINE, TARGET, BROKEN)
    assert any(f.kind == "copied_run" for f in findings)


def test_a_diagnostic_that_only_describes_the_defect_is_accepted() -> None:
    assert find_answer_leak(SAFE, TARGET, BROKEN) == ()
    assert_no_answer_leak(SAFE, TARGET, BROKEN)


def test_quoting_the_broken_trace_back_is_not_a_leak() -> None:
    """Repeating what the model already wrote tells it nothing it did not have."""
    echo = "The failing constraint is: require spend >= 150 — it conflicts with the cap."
    assert find_answer_leak(echo, TARGET, BROKEN) == ()


def test_assert_no_answer_leak_raises_with_an_explanation() -> None:
    with pytest.raises(ValueError, match="tautology"):
        assert_no_answer_leak(LEAKY_PROGRAM, TARGET, BROKEN)


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------


def test_each_condition_shows_exactly_what_it_should() -> None:
    diagnostics = {"t": SAFE, "u": "a different report about a different task"}
    a = build_payload("t", Condition.A_TRACE_ONLY, BROKEN, SAFE, diagnostics)
    b = build_payload("t", Condition.B_DIAGNOSTIC_ONLY, BROKEN, SAFE, diagnostics)
    c = build_payload("t", Condition.C_TRACE_PLUS_DIAGNOSTIC, BROKEN, SAFE, diagnostics)
    d = build_payload("t", Condition.D_TRACE_PLUS_SHUFFLED, BROKEN, SAFE, diagnostics)

    assert a.broken_trace and not a.diagnostic
    assert b.diagnostic and not b.broken_trace
    assert c.broken_trace and c.diagnostic == SAFE
    assert d.broken_trace and d.diagnostic and d.diagnostic != SAFE


def test_the_shuffled_condition_is_deterministic() -> None:
    diagnostics = {"t": SAFE, "u": "other", "v": "another"}
    first = build_payload("t", Condition.D_TRACE_PLUS_SHUFFLED, BROKEN, SAFE, diagnostics)
    second = build_payload("t", Condition.D_TRACE_PLUS_SHUFFLED, BROKEN, SAFE, diagnostics)
    assert first.diagnostic == second.diagnostic
    assert mismatched_diagnostic("t", diagnostics) == mismatched_diagnostic("t", diagnostics)


def test_the_mismatched_control_never_returns_the_task_s_own_diagnostic() -> None:
    diagnostics = {"t": SAFE, "u": "other", "v": "another"}
    assert mismatched_diagnostic("t", diagnostics) != SAFE


def test_the_scramble_variant_keeps_the_tokens_and_changes_the_order() -> None:
    scrambled = scrambled_diagnostic("t", SAFE)
    assert sorted(scrambled.split()) == sorted(SAFE.split())
    assert scrambled != SAFE


# ---------------------------------------------------------------------------
# The four conditions end to end
# ---------------------------------------------------------------------------


def _cases() -> list[tuple[str, str, str, str]]:
    fixtures = REPO / "evaluation" / "m3" / "verification" / "fixtures"
    other_target = (fixtures / "positive_refinement_bound.hml").read_text()
    other_broken = other_target.replace("require scale > 0", "require scale < 0")
    return [
        ("budget", BROKEN, SAFE, TARGET),
        (
            "refinement",
            other_broken,
            "A constraint is excluded by its declared type: the declared domain cannot "
            "reach the bound the constraint demands.",
            other_target,
        ),
    ]


def _responder(targets: dict[str, str], *, c_succeeds: bool, b_succeeds: bool = False):
    def respond(payload: Payload) -> str:
        if payload.condition is Condition.C_TRACE_PLUS_DIAGNOSTIC and c_succeeds:
            return targets[payload.task_id]
        if payload.condition is Condition.B_DIAGNOSTIC_ONLY and b_succeeds:
            return targets[payload.task_id]
        return payload.broken_trace

    return respond


def test_a_useful_non_leaking_diagnostic_is_admissible() -> None:
    cases = _cases()
    targets = {t: g for t, _b, _d, g in cases}
    report = run_conditions(cases, _responder(targets, c_succeeds=True))
    assert report.rate(Condition.C_TRACE_PLUS_DIAGNOSTIC) == 1.0
    assert report.rate(Condition.A_TRACE_ONLY) == 0.0
    assert report.rate(Condition.D_TRACE_PLUS_SHUFFLED) == 0.0
    assert report.rate(Condition.B_DIAGNOSTIC_ONLY) == 0.0
    assert report.useful and not report.leaks and report.admissible


def test_a_diagnostic_that_does_not_beat_the_floor_is_not_useful() -> None:
    cases = _cases()
    targets = {t: g for t, _b, _d, g in cases}
    report = run_conditions(cases, _responder(targets, c_succeeds=False))
    assert not report.useful
    assert not report.admissible


def test_condition_b_reconstructing_the_target_is_reported_as_a_leak() -> None:
    """The whole reason B exists: if the diagnostic alone rebuilds the answer, it leaked."""
    cases = _cases()
    targets = {t: g for t, _b, _d, g in cases}
    report = run_conditions(
        cases, _responder(targets, c_succeeds=True, b_succeeds=True)
    )
    assert report.rate(Condition.B_DIAGNOSTIC_ONLY) > LEAK_THRESHOLD
    assert report.leaks
    assert not report.admissible


def test_a_leaking_case_is_excluded_from_every_condition_not_merely_flagged() -> None:
    cases = [("budget", BROKEN, LEAKY_PROGRAM, TARGET), *_cases()[1:]]
    targets = {t: g for t, _b, _d, g in cases}
    report = run_conditions(cases, _responder(targets, c_succeeds=True))
    assert "budget" in report.guard_findings
    for result in report.results.values():
        assert "budget" not in result.per_task
        assert result.attempted == len(cases) - 1
    assert not report.admissible, "a guard finding alone must block admissibility"


def test_the_report_serialises_every_rate_and_both_judgements() -> None:
    cases = _cases()
    targets = {t: g for t, _b, _d, g in cases}
    payload = run_conditions(cases, _responder(targets, c_succeeds=True)).to_dict()
    assert set(payload["rates"]) == {"A", "B", "C", "D"}
    assert payload["leak_threshold"] == LEAK_THRESHOLD
    assert "useful" in payload and "leaks" in payload and "admissible" in payload
    assert payload["shuffle_mode"] == "mismatched"
