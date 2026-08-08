"""The scorer, the budget instrument, and the pre-flight gate."""

from __future__ import annotations

import pytest
from evaluation.arena.budget import budget_table, measure
from evaluation.arena.scoring import (
    Scored,
    extract_final,
    normalise,
    pair_score,
    score_response,
)

SPACE4 = ("A", "B", "C", "D")
TFU = ("TRUE", "FALSE", "UNDETERMINED")
NUM = ("an exact integer or fraction",)


def test_extract_final_takes_the_last_declared_line():
    assert extract_final("FINAL: A\nno wait\nFINAL: C") == "C"
    assert extract_final("no answer here") is None


@pytest.mark.parametrize(
    "raw,expected",
    [("B", "B"), ("b", "B"), ("**B**", "B"), ("**B**.", "B"), (" B .", "B"), ("`B`", "B")],
)
def test_normalise_strips_decoration_but_not_meaning(raw, expected):
    assert normalise(raw, SPACE4) == expected


@pytest.mark.parametrize("raw", ["Z", "B is correct", "the answer is B", ""])
def test_normalise_refuses_anything_that_is_not_the_answer(raw):
    assert normalise(raw, SPACE4) == ""


def test_truncated_responses_are_not_scored():
    """The CAL3 lesson: a `finish_reason=length` response is absence of data, not a failure.

    Reading two truncations as two wrong answers is what would have made the older
    calibration look as though the model had headroom it did not have.
    """
    s = score_response("i", "FINAL: B", "B", SPACE4, finish_reason="length")
    assert not s.valid and not s.correct and "length" in s.reason


def test_a_missing_or_malformed_answer_is_wrong_not_retried():
    for resp in ("I think it is B", "FINAL: Z", ""):
        s = score_response("i", resp, "B", SPACE4)
        assert s.valid and not s.correct


def test_numeric_answers_compare_by_value_not_by_text():
    assert score_response("i", "FINAL: 4/2", "2", NUM).correct
    assert score_response("i", "FINAL: -5", "-5", NUM).correct
    assert not score_response("i", "FINAL: 5", "-5", NUM).correct


def test_closed_word_answers():
    assert score_response("i", "FINAL: UNDETERMINED", "UNDETERMINED", TFU).correct
    assert not score_response("i", "FINAL: TRUE", "UNDETERMINED", TFU).correct


def test_pair_score_requires_both_members():
    pairs_ok = _fake_pairs([("p1", True, True), ("p2", True, False)])
    scored = {
        "p1a": Scored("p1a", True, True, "T"), "p1b": Scored("p1b", True, True, "F"),
        "p2a": Scored("p2a", True, True, "T"), "p2b": Scored("p2b", True, False, "T"),
    }
    r = pair_score(scored, pairs_ok)
    assert r["pairs_scored"] == 2 and r["both_correct"] == 1


def test_pair_with_a_truncation_is_dropped_whole():
    """Scoring the surviving half would turn a sensitivity measure into an accuracy one."""
    pairs = _fake_pairs([("p1", True, True)])
    scored = {"p1a": Scored("p1a", True, True, "T"), "p1b": Scored("p1b", False, False, "")}
    r = pair_score(scored, pairs)
    assert r["pairs_scored"] == 0 and r["pairs_dropped"] == 1
    assert r["both_correct_rate"] is None


def _fake_pairs(spec):
    from evaluation.arena.endpoints.common import Item
    from evaluation.arena.worlds import generate

    w = generate("FINITE_LOGIC_WORLD", "L2", 200_001)

    def mk(pid: str, suffix: str) -> Item:
        return Item(
            item_id=f"{pid}{suffix}", endpoint="CONTRAST", kind="CLOSED",
            family=w.family, level=w.level, seed=w.seed, world=w,
            question="", answer="TRUE", answer_space=("TRUE", "FALSE"), pair_id=pid,
        )

    return [(mk(pid, "a"), mk(pid, "b")) for pid, _, _ in spec]


def test_budget_reports_a_lopsided_corpus():
    t = budget_table({"SHORT": ["a b c"], "LONG": ["a b c " * 50]})
    assert t["shortest_arm"] == "SHORT" and t["longest_arm"] == "LONG"
    assert t["tokens_mean_ratio_max_over_min"] > 10


def test_measure_counts_something_for_every_arm():
    b = measure("SE", ["hello world", "second prompt"])
    assert b.n == 2 and b.tokens_mean > 0 and b.chars_mean > 0


@pytest.mark.slow
def test_pre_flight_gate_passes():
    """The gate that must be green before any model call is made."""
    from evaluation.arena.validate import run_gate

    out = run_gate(levels=("L3",), n_seeds=6)
    failed = {k: v for k, v in out["checks"].items() if not v["ok"]}
    assert out["all_ok"], f"gate failed: {failed}"
