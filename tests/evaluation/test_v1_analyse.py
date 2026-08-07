"""The decision rules and the statistics, tested against hand-computed values.

The decision rules are the part of this study most likely to be wrong in a way nobody
notices, because they are only exercised once, on data that does not exist yet. So they are
exercised here instead, on constructed tables whose verdict is obvious by inspection.
"""

from __future__ import annotations

from typing import Any

import pytest
from evaluation.v1_benchmark.analyse import (
    PairedTable,
    bootstrap_ci,
    build_paired_table,
    decide,
    domain_table,
    mcnemar_exact,
)

# ---------------------------------------------------------------------------
# McNemar
# ---------------------------------------------------------------------------


def test_mcnemar_no_discordant_pairs_is_p_one() -> None:
    assert mcnemar_exact(0, 0)["p_value"] == 1.0


@pytest.mark.parametrize(
    ("b", "c", "expected"),
    [
        (5, 0, 0.0625),  # 2 * 0.5^5
        (0, 5, 0.0625),  # symmetric
        (6, 0, 0.03125),  # 2 * 0.5^6
        (1, 1, 1.0),  # 2 * (2 choose 0 + 2 choose 1) * 0.25 -> capped at 1
        (10, 0, 0.001953),
    ],
)
def test_mcnemar_matches_hand_computed_binomial(b: int, c: int, expected: float) -> None:
    assert mcnemar_exact(b, c)["p_value"] == pytest.approx(expected, abs=1e-6)


def test_mcnemar_is_symmetric_in_its_arguments() -> None:
    """The test must not know which arm is the treatment."""
    for b, c in [(3, 7), (2, 9), (0, 4)]:
        assert mcnemar_exact(b, c)["p_value"] == mcnemar_exact(c, b)["p_value"]


# ---------------------------------------------------------------------------
# The paired table
# ---------------------------------------------------------------------------


def _rec(tid: str, arm: str, *, correct: bool, first: bool = False, **kw: Any) -> dict:
    base = {
        "task_id": tid,
        "arm": arm,
        "domain": kw.get("domain", "algebra"),
        "answer_correct": correct,
        "first_attempt_correct": first,
        "second_call_changed_answer": kw.get("changed", False),
        "normalised_answer": "x",
        "prompt_tokens": kw.get("pt", 100),
        "completion_tokens": kw.get("ct", 100),
        "latency_s": kw.get("lat", 1.0),
        "verified_completion": kw.get("verified"),
        "calls": [{"content": ""}, {"content": kw.get("final_content", "<ANSWER>1</ANSWER>")}],
    }
    if arm == "HML-V1":
        base["hml"] = {
            "initial_verdict": {
                "structural_errors": kw.get("si", 0),
                "semantic_errors": kw.get("mi", 0),
            },
            "structural_errors": kw.get("sf", 0),
            "semantic_errors": kw.get("mf", 0),
            "repaired_module_emitted": kw.get("emitted", True),
        }
    return base


def test_paired_table_classifies_all_four_cells() -> None:
    recs = [
        _rec("t1", "SE", correct=True),
        _rec("t1", "HML-V1", correct=True),
        _rec("t2", "SE", correct=True),
        _rec("t2", "HML-V1", correct=False),
        _rec("t3", "SE", correct=False),
        _rec("t3", "HML-V1", correct=True),
        _rec("t4", "SE", correct=False),
        _rec("t4", "HML-V1", correct=False),
    ]
    t = build_paired_table(recs, ["t1", "t2", "t3", "t4"])
    assert (t.both_correct, t.se_only, t.hml_only, t.both_wrong) == (1, 1, 1, 1)
    assert t.n == 4
    assert t.se_correct == 2
    assert t.hml_correct == 2
    assert t.difference == 0


def test_unpaired_task_is_dropped_not_counted_as_wrong() -> None:
    """A task present in one arm only must not silently score as a loss for the other."""
    recs = [_rec("t1", "SE", correct=True), _rec("t2", "HML-V1", correct=True)]
    t = build_paired_table(recs, ["t1", "t2"])
    assert t.n == 0


# ---------------------------------------------------------------------------
# Domain catastrophe
# ---------------------------------------------------------------------------


def test_catastrophic_domain_requires_zero_against_at_least_two() -> None:
    rows = [
        {"domain": "calculus", "se_correct": True, "hml_correct": False},
        {"domain": "calculus", "se_correct": True, "hml_correct": False},
        {"domain": "algebra", "se_correct": True, "hml_correct": True},
        {"domain": "algebra", "se_correct": False, "hml_correct": True},
    ]
    d = {x["domain"]: x for x in domain_table(rows)}
    assert d["calculus"]["hml_catastrophic"] is True
    assert d["algebra"]["hml_catastrophic"] is False


def test_a_single_task_domain_cannot_be_catastrophic() -> None:
    rows = [{"domain": "solo", "se_correct": True, "hml_correct": False}]
    assert domain_table(rows)[0]["hml_catastrophic"] is False


# ---------------------------------------------------------------------------
# The decision rules
# ---------------------------------------------------------------------------


def _sec(**kw: Any) -> dict[str, Any]:
    return {
        "verified_completion": {"verified": kw.get("verified", 0)},
        "hml_structured_errors": {"combined_reduction": kw.get("reduction", 0.0)},
        "cost": {"token_ratio_hml_over_se": kw.get("cost", 1.0)},
        "hml_final_state": {"rate": kw.get("invalid", 0.0)},
        "second_call": {
            "se": {
                "repaired_to_correct": kw.get("se_rep", 0),
                "broken_by_second_call": kw.get("se_broke", 0),
            },
            "hml": {
                "repaired_to_correct": kw.get("hml_rep", 0),
                "broken_by_second_call": kw.get("hml_broke", 0),
            },
        },
    }


def test_condition_1_three_more_correct_continues() -> None:
    t = PairedTable(both_correct=10, se_only=0, hml_only=3, both_wrong=11)
    d = decide(t, _sec(), [])
    assert d["verdict"] == "HML_CONTINUE_SIGNAL"
    assert d["continuation_conditions"]["c1_three_more_correct_no_catastrophe"]["met"]


def test_condition_1_is_blocked_by_a_catastrophic_domain() -> None:
    t = PairedTable(both_correct=10, se_only=0, hml_only=3, both_wrong=11)
    domains = [
        {"domain": "calculus", "hml_catastrophic": True, "se_catastrophic": False},
    ]
    d = decide(t, _sec(), domains)
    assert not d["continuation_conditions"]["c1_three_more_correct_no_catastrophe"]["met"]
    assert d["verdict"] == "HML_KILL_SIGNAL"
    assert d["kill_conditions"]["k4_catastrophic_domain_failure"]["met"]


def test_exactly_two_more_correct_does_not_meet_condition_1() -> None:
    t = PairedTable(both_correct=10, se_only=0, hml_only=2, both_wrong=12)
    d = decide(t, _sec(), [])
    assert not d["continuation_conditions"]["c1_three_more_correct_no_catastrophe"]["met"]


def test_condition_2_verified_and_error_reduction_continues() -> None:
    t = PairedTable(both_correct=10, se_only=1, hml_only=1, both_wrong=12)
    d = decide(t, _sec(verified=6, reduction=0.5), [])
    assert d["continuation_conditions"][
        "c2_four_more_verified_lose_at_most_one_reduce_errors_30pct"
    ]["met"]
    assert d["verdict"] == "HML_CONTINUE_SIGNAL"


def test_condition_2_fails_when_two_answers_are_lost() -> None:
    t = PairedTable(both_correct=10, se_only=2, hml_only=1, both_wrong=11)
    d = decide(t, _sec(verified=6, reduction=0.5), [])
    assert not d["continuation_conditions"][
        "c2_four_more_verified_lose_at_most_one_reduce_errors_30pct"
    ]["met"]


def test_condition_2_fails_below_thirty_percent_error_reduction() -> None:
    t = PairedTable(both_correct=10, se_only=1, hml_only=1, both_wrong=12)
    d = decide(t, _sec(verified=6, reduction=0.29), [])
    assert not d["continuation_conditions"][
        "c2_four_more_verified_lose_at_most_one_reduce_errors_30pct"
    ]["met"]


def test_condition_3_repair_advantage_continues() -> None:
    t = PairedTable(both_correct=10, se_only=1, hml_only=1, both_wrong=12)
    d = decide(t, _sec(se_rep=4, hml_rep=6, se_broke=1, hml_broke=1, cost=1.8), [])
    assert d["continuation_conditions"][
        "c3_fifty_pct_more_repairs_no_new_errors_cost_within_2x"
    ]["met"]


def test_condition_3_does_not_fire_when_neither_arm_repaired_anything() -> None:
    """Regression: `0 >= 1.5 * 0` is true, so the condition once fired on an empty result.

    "HML corrects at least 50% more initially wrong solutions than SE" must not be
    satisfiable by nothing happening. Caught by this test before any data existed.
    """
    t = PairedTable(both_correct=10, se_only=1, hml_only=1, both_wrong=12)
    d = decide(t, _sec(se_rep=0, hml_rep=0), [])
    assert not d["continuation_conditions"][
        "c3_fifty_pct_more_repairs_no_new_errors_cost_within_2x"
    ]["met"]
    assert d["verdict"] == "HML_KILL_SIGNAL"


def test_condition_3_fires_when_se_repairs_nothing_and_hml_repairs_something() -> None:
    """The unbounded-ratio case must still count as met."""
    t = PairedTable(both_correct=10, se_only=1, hml_only=1, both_wrong=12)
    d = decide(t, _sec(se_rep=0, hml_rep=2), [])
    assert d["continuation_conditions"][
        "c3_fifty_pct_more_repairs_no_new_errors_cost_within_2x"
    ]["met"]


def test_condition_3_fails_when_cost_exceeds_twice_se() -> None:
    t = PairedTable(both_correct=10, se_only=1, hml_only=1, both_wrong=12)
    d = decide(t, _sec(se_rep=4, hml_rep=8, cost=2.1), [])
    assert not d["continuation_conditions"][
        "c3_fifty_pct_more_repairs_no_new_errors_cost_within_2x"
    ]["met"]


def test_null_result_kills() -> None:
    t = PairedTable(both_correct=10, se_only=2, hml_only=2, both_wrong=10)
    d = decide(t, _sec(verified=1), [])
    assert d["verdict"] == "HML_KILL_SIGNAL"
    assert d["kill_conditions"]["k1_no_more_accurate_and_under_3_verified"]["met"]


def test_invalid_final_state_over_ten_percent_is_a_kill_flag() -> None:
    t = PairedTable(both_correct=10, se_only=1, hml_only=1, both_wrong=12)
    d = decide(t, _sec(invalid=0.15), [])
    assert d["kill_conditions"]["k3_invalid_final_state_over_10pct"]["met"]


def test_verdict_is_always_one_of_the_two_computable_values() -> None:
    """No branch may return 'inconclusive' after a valid paired measurement."""
    for hml_only in range(0, 8):
        for se_only in range(0, 8):
            t = PairedTable(both_correct=5, se_only=se_only, hml_only=hml_only, both_wrong=5)
            v = decide(t, _sec(), [])["verdict"]
            assert v in {"HML_CONTINUE_SIGNAL", "HML_KILL_SIGNAL"}


def test_a_strong_continue_is_not_overridden_by_a_kill_flag() -> None:
    """Continuation is disjunctive by design; the rules make CONTINUE dominant."""
    t = PairedTable(both_correct=10, se_only=0, hml_only=5, both_wrong=9)
    d = decide(t, _sec(cost=3.0), [])
    assert d["verdict"] == "HML_CONTINUE_SIGNAL"


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def test_bootstrap_is_deterministic_under_a_fixed_seed() -> None:
    rows = [
        {"se_correct": True, "hml_correct": True},
        {"se_correct": False, "hml_correct": True},
        {"se_correct": True, "hml_correct": False},
        {"se_correct": False, "hml_correct": False},
    ]
    a = bootstrap_ci(rows, iterations=500, seed=7)
    b = bootstrap_ci(rows, iterations=500, seed=7)
    assert a == b


def test_bootstrap_point_estimate_matches_the_observed_difference() -> None:
    rows = [
        {"se_correct": False, "hml_correct": True},
        {"se_correct": False, "hml_correct": True},
        {"se_correct": True, "hml_correct": True},
        {"se_correct": True, "hml_correct": True},
    ]
    out = bootstrap_ci(rows, iterations=200, seed=1)
    assert out["point_estimate_accuracy_difference"] == pytest.approx(0.5)
