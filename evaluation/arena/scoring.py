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
    "extract_bare",
    "normalise",
    "score_response",
    "Scored",
    "pair_score",
]

#: Bumped from 1.0.0 when `allow_bare` was added. The old version string stayed put across
#: a behaviour-changing edit, so `ACQ_gemma3-4b.json` (attempt #1) no longer re-scores to
#: its committed numbers from this tree -- 12/18 reproduce. That file is frozen historical
#: evidence, marked INVALID_INSTRUMENT, and is NOT rescored; the version bump is what makes
#: the discrepancy legible instead of mysterious. Every MICRO file still reproduces 12/12.
SCORER_VERSION = "arena-scorer-1.1.0"

#: `\s` matches newlines, so `FINAL:\s*` used to span a line break: `FINAL:\n\nforall\nexists`
#: extracted `forall` -- the *first* following line -- contradicting this module's own
#: last-wins rule. Restricted to horizontal whitespace so the marker and its answer must
#: share a line. Verified against every frozen record: 0 of 96 extractions change, so no
#: historical score moves and model selection is untouched.
_FINAL = re.compile(r"^[ \t]*FINAL:[ \t]*(\S.*?)[ \t]*$", re.MULTILINE)


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


def extract_bare(response: str, answer_space: tuple[str, ...]) -> str | None:
    """An unambiguous bare answer: the whole reply, or its last line, IS a declared answer.

    Used **only** by the acquisition gate. A literal-recall question asks for one word, and
    this model frequently replies with that word and nothing else -- no `FINAL:` line. The
    first acquisition run discarded six such replies, three of which were correct, which
    made the instrument measure its own prompt shape instead of whether an arm can be read.

    Deliberately the least permissive rule that fixes that: the candidate text must equal a
    member of the declared space **exactly** after decoration stripping. Prose that merely
    *contains* the word does not match, so "the answer is TRUE" is still wrong. Applied
    identically to SE, AST and HML.
    """
    text = (response or "").strip()
    if not text:
        return None
    lines = [ln for ln in text.splitlines() if ln.strip()]

    # A reply that NAMES more than one declared answer has not chosen; it has enumerated.
    # Resolving that by line position would hand credit to a refusal -- and because
    # `normalise` strips a leading `*`, the markdown a model uses to list options
    # ("* forall\n* exists") is exactly the shape that leaked. With `FINAL:` the model
    # declares which answer is final; with a bare reply there is no declaration, so
    # ambiguity must be rejected rather than guessed at.
    named = {got for ln in lines if (got := normalise(ln, answer_space))}
    if len(named) > 1:
        return None

    for candidate in (text, lines[-1] if lines else ""):
        got = normalise(candidate, answer_space)
        if got:
            return got
    return None


def score_response(
    item_id: str,
    response: str,
    expected: str,
    answer_space: tuple[str, ...],
    *,
    finish_reason: str = "stop",
    allow_bare: bool = False,
) -> Scored:
    """Score one response. `allow_bare` is the acquisition-only relaxation.

    The reasoning pilot keeps `allow_bare=False` and therefore keeps the original rule --
    only a declared `FINAL:` line counts. Relaxing the pilot scorer would change what a
    scored reasoning answer means, which is a treatment change, not an instrument repair.
    """
    if finish_reason != "stop":
        return Scored(item_id, False, False, "", f"not scored: finish_reason={finish_reason}")

    raw = extract_final(response)
    if raw is None:
        if allow_bare:
            bare = extract_bare(response, answer_space)
            if bare:
                return Scored(item_id, True, bare == expected, bare, "bare answer accepted")
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
