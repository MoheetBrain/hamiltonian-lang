"""Regression tests for the four v1.3 harness fixes.

Each test names the defect it pins and, where the defect was demonstrated on the frozen
scorer, asserts the old behaviour is really gone rather than merely asserting the new one.
"""

from __future__ import annotations

import pytest
from evaluation.corpus.cso import check_answer
from evaluation.v1_benchmark.answer_extraction import (
    extract_final_answer,
    parse_numeric,
    score_answer_v13,
)
from evaluation.v1_benchmark.tasks import build_tasks

TASKS = {t.id: t for t in build_tasks()}


# ---------------------------------------------------------------------------
# D1 — the LAST answer marker is the final answer
# ---------------------------------------------------------------------------


def test_last_marker_wins_not_first() -> None:
    raw = "Try <ANSWER>2.5</ANSWER> no, wrong.\nFinal: <ANSWER>2.2857</ANSWER>"
    assert extract_final_answer(raw).text == "2.2857"


def test_the_frozen_scorer_really_did_take_the_first_marker() -> None:
    """Pins the defect itself. If cso.py is ever fixed, this test should be revisited."""
    t = TASKS["v1b_04_conditional_min_given_max"]
    raw = "Try <ANSWER>2.5</ANSWER> no, wrong.\nFinal: <ANSWER>2.2857</ANSWER>"
    assert check_answer(t.cso.answer, raw) == (False, "2.5")
    assert score_answer_v13(t.cso.answer, raw)[0] is True


def test_marker_count_is_recorded() -> None:
    raw = "<ANSWER>1</ANSWER> and <ANSWER>2</ANSWER> and <ANSWER>3</ANSWER>"
    ex = extract_final_answer(raw)
    assert ex.marker_count == 3
    assert ex.text == "3"


# ---------------------------------------------------------------------------
# D2 — exact closed forms parse, they do not silently become another number
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("16/7", 16 / 7),
        ("2/3", 2 / 3),
        ("-1/15", -1 / 15),
        ("9/13", 9 / 13),
        ("14/23", 14 / 23),
        ("sqrt(76)", 76**0.5),
        ("ln(5/2)", 0.9162907318741551),
        ("1/3", 1 / 3),
        ("2.2857", 2.2857),
        ("1e-3", 0.001),
        (".6667", 0.6667),
        ("-24", -24.0),
    ],
)
def test_exact_forms_parse_to_their_value(text: str, expected: float) -> None:
    got = parse_numeric(text)
    assert got is not None
    assert got == pytest.approx(expected, rel=1e-9)


@pytest.mark.parametrize("text", ["not a number", "2/0", "the answer is 5 or 6", ""])
def test_unparseable_answers_are_refused_not_mined_for_digits(text: str) -> None:
    assert parse_numeric(text) is None


def test_the_frozen_scorer_really_did_mine_digits_out_of_exact_forms() -> None:
    """Pins the differential defect: 16/7 became 16.0, not a rejection."""
    t = TASKS["v1b_04_conditional_min_given_max"]
    assert check_answer(t.cso.answer, "<ANSWER>16/7</ANSWER>") == (False, "16.0")
    assert score_answer_v13(t.cso.answer, "<ANSWER>16/7</ANSWER>")[0] is True


def test_logarithm_substitution_does_not_re_enter_itself() -> None:
    """Regression: `ln` -> `math.log` then `log` -> `math.log` gave `math.math.log`."""
    assert parse_numeric("ln(5/2)") == pytest.approx(0.9162907318741551)
    assert parse_numeric("log(10)") == pytest.approx(2.302585092994046)


def test_parser_executes_nothing_outside_the_whitelist() -> None:
    for hostile in [
        "__import__('os').system('true')",
        "open('/etc/passwd')",
        "1 if True else 2",
        "[].__class__",
    ]:
        assert parse_numeric(hostile) is None


# ---------------------------------------------------------------------------
# D3 — a missing marker is a failure, not a licence to search the whole reply
# ---------------------------------------------------------------------------


def test_missing_marker_scores_incorrect() -> None:
    t = TASKS["v1b_07_law_of_total_variance"]
    raw = "The coin is flipped 10 times, so H is binomial. Var(H) = 2.5."
    ok, _, diag = score_answer_v13(t.cso.answer, raw)
    assert ok is False
    assert diag["reason"] == "no_answer_marker"


def test_the_frozen_scorer_really_did_produce_spurious_passes() -> None:
    """Pins the defect: a formatting failure scored as a reasoning success."""
    t = TASKS["v1b_07_law_of_total_variance"]
    raw = "The coin is flipped 10 times, so H is binomial. Var(H) = 2.5."
    assert check_answer(t.cso.answer, raw)[0] is True  # the defect
    assert score_answer_v13(t.cso.answer, raw)[0] is False  # fixed


# ---------------------------------------------------------------------------
# The scorer must still reject wrong answers, and accept every gold key
# ---------------------------------------------------------------------------


def test_every_gold_key_scores_correct_under_v13() -> None:
    failures = [
        t.id
        for t in build_tasks()
        if not score_answer_v13(t.cso.answer, f"<ANSWER>{t.cso.answer.value}</ANSWER>")[0]
    ]
    assert failures == []


@pytest.mark.parametrize(
    ("tid", "wrong"),
    [
        ("v1b_04_conditional_min_given_max", "3.9"),
        ("v1b_18_frullani_integral", "ln(2/5)"),  # the classic sign error
        ("v1b_20_series_order_limit", "1/6"),  # the drop-the-cos-expansion error
        ("v1b_23_knowledge_closure_choice", "A"),
    ],
)
def test_wrong_answers_are_still_wrong(tid: str, wrong: str) -> None:
    t = TASKS[tid]
    assert score_answer_v13(t.cso.answer, f"<ANSWER>{wrong}</ANSWER>")[0] is False


def test_scoring_never_consults_the_arm_or_the_task_id() -> None:
    """The fix must be arm-blind: the same text scores the same way regardless of caller."""
    t = TASKS["v1b_04_conditional_min_given_max"]
    a = score_answer_v13(t.cso.answer, "<ANSWER>16/7</ANSWER>")
    b = score_answer_v13(t.cso.answer, "<ANSWER>16/7</ANSWER>")
    assert a == b


# ---------------------------------------------------------------------------
# D4 — both arms carry the same prior working into their second call
# ---------------------------------------------------------------------------


def test_hml_repair_carries_the_full_prior_reply_like_se_does() -> None:
    from evaluation.v1_benchmark.arms import se_review_prompt
    from evaluation.v1_benchmark.arms_v1_3 import hml_repair_prompt_v13

    t = TASKS["v1b_04_conditional_min_given_max"]
    reply = (
        "Step 1: enumerate the pairs.\nStep 2: the minima are 1,1,2,2,3,3,4.\n"
        "<ANSWER>2.2857</ANSWER>"
    )
    module = "let s : Real = 16.0"

    se = se_review_prompt(t.cso, reply)
    hml = hml_repair_prompt_v13(t.cso, reply, module, "(no diagnostics)")

    for fragment in ["Step 1: enumerate the pairs.", "Step 2: the minima are"]:
        assert fragment in se.user
        assert fragment in hml.user, "the HML arm must carry its working like SE does"
    assert module in hml.user
    # The answer span is stripped from both, so neither arm is anchored on its own answer.
    assert "2.2857" not in se.user
    assert "2.2857" not in hml.user


def test_the_frozen_repair_prompt_really_did_drop_the_working() -> None:
    """Pins the asymmetry that handicapped the treatment arm."""
    from evaluation.v1_benchmark.arms import hml_repair_prompt

    t = TASKS["v1b_04_conditional_min_given_max"]
    module = "let s : Real = 16.0"
    old = hml_repair_prompt(t.cso, module, "(no diagnostics)")
    # The module survives; the reasoning that produced it does not reach the second call.
    assert module in old.user
    assert "Step 1: enumerate the pairs." not in old.user
