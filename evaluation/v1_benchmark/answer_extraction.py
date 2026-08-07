"""Answer extraction and scoring for developmental protocol v1.3.

Three demonstrated defects in :func:`evaluation.corpus.cso.check_answer` corrupt this
benchmark's primary endpoint. They are fixed **here**, in a v1.3 layer, rather than in
``cso.py`` — that module scored eval001 and the ACQ0 corpora, whose results are frozen
evidence, and editing it would silently change what those historical numbers mean.

Every defect below was demonstrated on the real scorer before any scientific call.

Defect 1 — the FIRST answer marker wins
----------------------------------------
``normalise_answer`` uses a non-greedy ``re.search``, so it takes the **first**
``<ANSWER>…</ANSWER>`` span::

    "Working... <ANSWER>2.5</ANSWER> wait, that is wrong.
     Final: <ANSWER>2.2857</ANSWER>"        ->  scored "2.5", INCORRECT

This defeats the entire two-call design. Both arms' second-call prompts say *"Correct
anything you find wrong, then give your final answer"*, so a model that shows its abandoned
answer before its corrected one is scored on the abandoned one — the second call is
penalised precisely when it works. It also contradicts the system prompt, which mandates
that the reply **end** with the answer and have "nothing after the closing marker".

v1.3 takes the **last** complete span, which is what "your final answer" means.

Defect 2 — the first number-like substring wins
------------------------------------------------
The numeric branch searches for ``-?\\d+(\\.\\d+)?`` anywhere in the extracted text, so an
exact closed form is silently converted into a different number rather than rejected::

    16/7      -> 16.0        sqrt(76) -> 76.0        ln(5/2) -> 5.0
    2/3       ->  2.0        -1/15    -> -1.0        1/3     -> 1.0

Nine of the twenty-four tasks have an exact closed form of this shape. This is the most
dangerous defect of the three, because the error is **differential**: an arm reasoning in a
formal representation is *more* likely to answer ``16/7`` than ``2.2857``, so the
mis-scoring falls preferentially on the treatment. It does not add noise to the paired
contrast, it biases it.

v1.3 parses the whole extracted string as a mathematical value — decimals, fractions,
surds, logs — and **rejects** anything it cannot parse rather than silently grabbing a
digit out of it.

Defect 3 — a reply with no marker is scored against its entire text
-------------------------------------------------------------------
When no marker is present, ``normalise_answer`` falls through to the whole reply, so any
digit anywhere in the prose can score as the answer. Demonstrated **spurious passes**::

    v1b_07 (key 10): "The coin is flipped 10 times ... Var(H) = 2.5."  -> CORRECT
    v1b_14 (key 1):  "Proposal (1) is fine ... Two are consistent."    -> CORRECT

A formatting failure is scored as a reasoning success. This inflates both arms toward
saturation, which is exactly the direction that would make a real headroom band look
insufficient.

v1.3 requires the marker. Absent it, the trial is incorrect and is recorded as
``no_answer_marker`` so the rate is visible rather than buried.

Why these fixes cannot flatter either arm
------------------------------------------
All three are applied identically to SE and HML-V1 by the same function, before any
scientific call, and none consults the arm, the task, or the key. Defects 1 and 2 currently
penalise correct answers; fixing them can only *raise* measured accuracy, and raises it more
for whichever arm was writing exact forms — which is the arm the defect was penalising.
Defect 3 currently rewards non-answers; fixing it can only *lower* measured accuracy. The
net direction is not predictable in advance and was not chosen with any result in view.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from evaluation.corpus.cso import (
    ANSWER_CLOSE,
    ANSWER_OPEN,
    AnswerSpec,
    parse_dimension,
)

__all__ = [
    "ExtractedAnswer",
    "extract_final_answer",
    "parse_numeric",
    "score_answer_v13",
]

#: Characters a numeric answer may contain once wrappers are stripped. Anything else means
#: the model wrote prose where a number was demanded, and that is a failure to answer, not
#: an invitation to go digging for a digit.
_NUMERIC_CHARSET = re.compile(
    r"^[0-9\s+\-*/^().,eE]*(?:sqrt|ln|log|pi|exp)?[0-9\s+\-*/^().,eE]*$"
)
_ALLOWED_TOKENS = re.compile(r"^(?:[0-9.,\s+\-*/^()eE]|sqrt|ln|log|pi|exp)+$")


@dataclass(frozen=True)
class ExtractedAnswer:
    text: str
    found_marker: bool
    marker_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "found_marker": self.found_marker,
            "marker_count": self.marker_count,
        }


def extract_final_answer(raw: str) -> ExtractedAnswer:
    """The LAST complete answer span, with wrappers stripped.

    A model that revises its answer inside one reply must be scored on the revision. An
    unterminated final marker is honoured as a last resort so that a reply which begins its
    answer and is cut off is not treated as having answered something earlier.
    """
    if not raw:
        return ExtractedAnswer("", False, 0)

    pattern = re.escape(ANSWER_OPEN) + r"(.*?)" + re.escape(ANSWER_CLOSE)
    spans = re.findall(pattern, raw, re.S | re.I)
    if spans:
        text = spans[-1]
        count = len(spans)
    else:
        m = re.search(re.escape(ANSWER_OPEN) + r"(.*)", raw, re.S | re.I)
        if not m:
            return ExtractedAnswer("", False, 0)
        text = m.group(1)
        count = 1

    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text).strip()
    text = text.strip("`").strip()
    text = re.sub(r"^\$+|\$+$", "", text).strip()
    text = re.sub(r"^\\\(|\\\)$", "", text).strip()
    return ExtractedAnswer(text, True, count)


def parse_numeric(text: str) -> float | None:
    """Parse a complete numeric answer, or return ``None``.

    Accepts decimals, scientific notation, fractions, and the small set of closed forms
    this corpus's keys actually take (``sqrt``, ``ln``, ``log``, ``pi``, ``exp``). Refuses
    anything outside that vocabulary instead of extracting a digit from it — the refusal is
    the point, since silent extraction is what defect 2 was.
    """
    if text is None:
        return None
    s = text.strip().replace(",", "").replace("\\", "")
    s = re.sub(r"\s*(?:approx(?:imately)?|about|~|≈)\s*", "", s, flags=re.I)
    s = s.strip()
    if not s:
        return None

    # Fast path: a plain number, the overwhelmingly common case.
    try:
        return float(s)
    except ValueError:
        pass

    # A bare fraction, including negatives: the single most common exact form here.
    m = re.fullmatch(r"(-?\d+)\s*/\s*(-?\d+)", s)
    if m:
        num, den = int(m.group(1)), int(m.group(2))
        if den == 0:
            return None
        return float(Fraction(num, den))

    if not _ALLOWED_TOKENS.fullmatch(s):
        return None

    # Closed forms. Evaluated on a whitelisted namespace with no builtins, so a model
    # cannot cause anything to execute by writing something clever in an answer field.
    #
    # The substitution is a SINGLE pass. Doing it as successive re.sub calls is wrong and
    # was wrong here: rewriting `ln` -> `math.log` creates the token `log`, which the next
    # rule then rewrites again, yielding `math.math.log(...)` and a silent parse failure on
    # every logarithm. One pass over an alternation cannot re-enter its own output.
    _FUNCS = {
        "ln": "math.log",
        "log": "math.log",
        "sqrt": "math.sqrt",
        "exp": "math.exp",
        "pi": "math.pi",
    }
    expr = re.sub(
        r"\b(ln|log|sqrt|exp|pi)\b",
        lambda m: _FUNCS[m.group(1)],
        s.replace("^", "**"),
    )
    if not re.fullmatch(
        r"[0-9.\s+\-*/()eE]*(?:math\.(?:log|sqrt|exp|pi)[0-9.\s+\-*/()eE]*)*", expr
    ):
        return None
    try:
        value = eval(expr, {"__builtins__": {}, "math": math}, {})  # noqa: S307
    except Exception:  # noqa: BLE001 — an unparseable answer is a wrong answer
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def score_answer_v13(spec: AnswerSpec, raw: str) -> tuple[bool, str, dict[str, Any]]:
    """Deterministic scoring under v1.3. Returns (correct, normalised, diagnostics)."""
    ex = extract_final_answer(raw)
    diag: dict[str, Any] = {
        "found_marker": ex.found_marker,
        "marker_count": ex.marker_count,
        "extracted": ex.text,
        "reason": "",
    }
    if not ex.found_marker:
        diag["reason"] = "no_answer_marker"
        return False, "", diag
    if not ex.text:
        diag["reason"] = "empty_answer_marker"
        return False, "", diag

    text = ex.text

    if spec.kind == "numeric":
        got = parse_numeric(text)
        if got is None:
            diag["reason"] = "unparseable_numeric"
            return False, text, diag
        want = float(spec.value)
        tol = max(spec.tolerance, abs(want) * spec.tolerance)
        ok = abs(got - want) <= tol
        diag["reason"] = "ok" if ok else "numeric_mismatch"
        diag["parsed_value"] = got
        return ok, str(got), diag

    if spec.kind == "boolean":
        t = re.sub(r"[^A-Z]", "", text.upper())[:5]
        if t.startswith("TRUE"):
            ok = bool(spec.value) is True
            diag["reason"] = "ok" if ok else "boolean_mismatch"
            return ok, "TRUE", diag
        if t.startswith("FALSE"):
            ok = bool(spec.value) is False
            diag["reason"] = "ok" if ok else "boolean_mismatch"
            return ok, "FALSE", diag
        diag["reason"] = "unparseable_boolean"
        return False, text, diag

    if spec.kind == "choice":
        t = text.strip().upper()
        hits = [o for o in spec.options if re.search(rf"\b{re.escape(o.upper())}\b", t)]
        if len(hits) != 1:
            diag["reason"] = "ambiguous_choice" if hits else "no_choice_found"
            return False, text, diag
        ok = hits[0] == str(spec.value)
        diag["reason"] = "ok" if ok else "choice_mismatch"
        return ok, hits[0], diag

    if spec.kind == "dimension":
        got_d = parse_dimension(text)
        want_d = parse_dimension(str(spec.value))
        if got_d is None or want_d is None:
            diag["reason"] = "unparseable_dimension"
            return False, text, diag
        ok = got_d == want_d
        diag["reason"] = "ok" if ok else "dimension_mismatch"
        return ok, str(sorted(got_d.items())), diag

    if spec.kind == "exact_string":
        # Matches the frozen scorer's fallthrough exactly: collapse whitespace, drop a
        # trailing full stop, compare case-insensitively.
        got_s = re.sub(r"\s+", " ", text).strip().rstrip(".")
        want_s = re.sub(r"\s+", " ", str(spec.value)).strip().rstrip(".")
        ok = got_s.lower() == want_s.lower()
        diag["reason"] = "ok" if ok else "string_mismatch"
        return ok, got_s, diag

    diag["reason"] = f"unsupported_kind:{spec.kind}"
    return False, text, diag
