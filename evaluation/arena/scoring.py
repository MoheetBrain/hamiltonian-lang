"""Scoring. Reads only the declared `FINAL:` line; anything unparseable is wrong.

Deliberately inherited from `difficulty-lab-scorer-1.0.0`, whose discipline is the
reason the synthetic calibration is trustworthy:

- only the **last** `FINAL:` line counts, so a model that reconsiders is scored on its
  final answer rather than on whichever guess appears first;
- an answer that is missing, malformed, or outside the declared answer space is
  **wrong**, never a retry and never partial credit;
- a **truncated** response is not scored at all. `CAL3.json` in the older protocol
  recorded two `finish_reason=length` responses as failures, and reading that file
  without the truncation caveat would say the model had headroom where it did not. The
  `valid` flag here exists so that mistake cannot be repeated: `score_response` refuses
  to grade a response that did not finish.

Pair scoring for endpoint B is `both_correct`: a pair counts only when *both* members
are right. On a two-way question that is what separates perceiving a distinction from
guessing a constant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

__all__ = [
    "SCORER_VERSION",
    "extract_final",
    "normalise",
    "score_response",
    "Scored",
    "pair_score",
]

SCORER_VERSION = "arena-scorer-1.0.0"

_FINAL = re.compile(r"^\s*FINAL:\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Scored:
    item_id: str
    #: False when the response was truncated or produced no readable answer line.
    valid: bool
    correct: bool
    extracted: str
    reason: str = ""


def extract_final(text: str) -> str | None:
    """The last `FINAL:` line's payload, or None."""
    hits = _FINAL.findall(text or "")
    return hits[-1].strip() if hits else None


def normalise(raw: str, answer_space: tuple[str, ...]) -> str:
    """Map a raw answer onto the declared space, or return '' if it does not land there.

    Tolerates the formatting a model adds around a correct answer -- surrounding
    asterisks, a trailing period, `**A**`, `A.` -- because those are presentation, not a
    different answer. It does **not** tolerate a different answer: no prefix matching, no
    nearest-neighbour, no "contains".
    """
    # Strip decoration from both ends until it stops changing. A single pass is not
    # enough: `**B**.` leaves a trailing `.` that blocks the asterisk strip, so `B**`
    # survives and a correct answer is scored wrong.
    s = raw or ""
    while True:
        t = s.strip().strip("*_`").rstrip(".").strip()
        if t == s:
            break
        s = t
    if not s:
        return ""
    for a in answer_space:
        if s.upper() == a.upper():
            return a
    # A numeric answer space is declared by description rather than by enumeration.
    if len(answer_space) == 1 and "exact" in answer_space[0]:
        t = s.replace(" ", "")
        if re.fullmatch(r"[+-]?\d+(/\d+)?", t):
            return t
    return ""


def _numeric_equal(a: str, b: str) -> bool:
    try:
        return Fraction(a) == Fraction(b)
    except (ValueError, ZeroDivisionError):
        return False


def score_response(
    item_id: str,
    response: str,
    expected: str,
    answer_space: tuple[str, ...],
    *,
    finish_reason: str = "stop",
) -> Scored:
    if finish_reason != "stop":
        return Scored(item_id, False, False, "", f"not scored: finish_reason={finish_reason}")

    raw = extract_final(response)
    if raw is None:
        return Scored(item_id, True, False, "", "no FINAL: line")

    got = normalise(raw, answer_space)
    if not got:
        return Scored(item_id, True, False, raw, "answer outside the declared space")

    if len(answer_space) == 1 and "exact" in answer_space[0]:
        return Scored(item_id, True, _numeric_equal(got, expected), got)
    return Scored(item_id, True, got == expected, got)


def pair_score(scored_by_id: dict[str, Scored], pairs) -> dict:
    """Both-correct rate over minimal-contrast pairs.

    A pair is counted only when both members produced a *valid* response; a pair with a
    truncation in it is dropped whole, because scoring one half would silently turn a
    sensitivity measure into a single-item accuracy measure.
    """
    both = n = dropped = 0
    for a, b in pairs:
        sa, sb = scored_by_id.get(a.item_id), scored_by_id.get(b.item_id)
        if sa is None or sb is None or not sa.valid or not sb.valid:
            dropped += 1
            continue
        n += 1
        both += int(sa.correct and sb.correct)
    return {
        "pairs_scored": n,
        "pairs_dropped": dropped,
        "both_correct": both,
        "both_correct_rate": (both / n) if n else None,
    }
