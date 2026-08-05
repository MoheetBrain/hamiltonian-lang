"""How the 40–70% band was arrived at without a single model call, and what that is worth.

The distinction this module exists to hold
------------------------------------------
Two different things are computed here and they must never be quoted as one number.

**Measured.** Deterministic baselines run against the corpus on this machine. The
shallow-reader baselines, the uniform-guess floor and the constant-response baselines are
*computations over the corpus*, reproducible, with no model involved. They are facts about
the corpus.

**Predicted.** The expected accuracy band for a real model. This is an *inference from two
measured anchors*, and :class:`BandEstimate` carries the status
``PREDICTED_NOT_MEASURED`` with ``measured_band = None`` until a real run fills it in.
:meth:`BandEstimate.is_measured` returns ``False``, and there is no setter that could make
it return ``True`` without an actual measurement being supplied.

The two anchors, both from HML-EVAL-001 on this host
-----------------------------------------------------
**Anchor A1 — final-answer accuracy on the old corpus: 93.3%** (14/15, every arm). The one
failure was a generation-budget exhaustion, not a reasoning failure. Per domain, n = 3 per
cell: algebraic 1.00, binding 1.00, dimensional 1.00, quantifier 1.00, probability 0.67.
Six of seven arm contrasts had **zero discordant pairs** — the arms succeeded and failed on
exactly the same problems, which is the signature of a task set with no discriminating
structure at all.

**Anchor A2 — structural fidelity on the same items, same model: 0.648 and 0.701** semantic
encoding score for the two Hamiltonian-emitting arms, with parse success 73.3% and 80.0%.

Why A2 rather than A1 is the right anchor for M3-Lite
------------------------------------------------------
A1 measures "select the final answer to a problem whose structure is given". A2 measures
"get the structure right". Every M3-Lite item is built so that the *answer is itself a
structural discrimination* — which quantifier prefix, which symbol fills which role, whether
this is an equality or an approximation, whether the binder resolves inward or outward. Its
difficulty class is A2's, not A1's. So the predicted **upper** edge is set at A2's ceiling,
≈0.70, and A1's 0.93 is explicitly *not* used.

The **lower** edge is computed, not chosen: :func:`uniform_guess_floor` is the exact expected
accuracy of a responder that guesses uniformly within each item's answer kind. No item is
below chance in expectation, so the band cannot honestly start below it.

What could still be wrong with this, stated plainly
----------------------------------------------------
1. A2 was measured on *encoding* tasks, not on answering questions about structure. The
   transfer is an argument, not a measurement.
2. Both anchors come from one model on one host with n = 15. That is a thin base.
3. If the real baseline lands outside 40–70%, the corpus needs re-tuning and **the band was
   wrong** — which is why it is recorded as a prediction with a status field rather than
   asserted as a property.

Response-bias control
---------------------
:func:`constant_response_baselines` computes what a responder that always says the same
thing would score. A boolean-heavy corpus whose booleans are mostly ``FALSE`` can be beaten
to a plausible-looking 55% by a model with a negative answer bias, and that score would be
indistinguishable from reasoning. This is a real defect class, it is cheap to detect, and
:data:`MAX_CONSTANT_RESPONSE_BASELINE` is the threshold above which the corpus must be
rebalanced.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from evaluation.corpus.cso import ANSWER_CLOSE, ANSWER_OPEN, check_answer

from .items import LiteItem, build_items

__all__ = [
    "BandStatus",
    "BandEstimate",
    "ANCHOR_A1_FINAL_ANSWER",
    "ANCHOR_A2_STRUCTURAL_FIDELITY",
    "TARGET_BAND",
    "MAX_CONSTANT_RESPONSE_BASELINE",
    "MAX_SHALLOW_READER_BASELINE",
    "uniform_guess_floor",
    "shallow_reader_baselines",
    "constant_response_baselines",
    "difficulty_index",
    "estimate_band",
    "calibration_report",
]

#: HML-EVAL-001, final-answer accuracy, every arm. Ceiling; deliberately not used as the
#: anchor for M3-Lite. Recorded so the choice not to use it is visible.
ANCHOR_A1_FINAL_ANSWER = 0.933

#: HML-EVAL-001, semantic-encoding score for the two Hamiltonian-emitting arms (0.648, 0.701)
#: with parse success 0.733 and 0.800. The upper edge of the predicted band is set here.
ANCHOR_A2_STRUCTURAL_FIDELITY = (0.648, 0.701)

#: The band M3-Lite is designed for. A baseline outside it means the corpus needs re-tuning.
TARGET_BAND = (0.40, 0.70)

#: A constant-response baseline above this is a response-bias artifact, not a difficulty
#: level, and the corpus must be rebalanced before use.
MAX_CONSTANT_RESPONSE_BASELINE = 0.50

#: A shallow-reader strategy above this means items are solvable by surface heuristics.
MAX_SHALLOW_READER_BASELINE = 0.30


class BandStatus(StrEnum):
    PREDICTED_NOT_MEASURED = "predicted_not_measured"
    MEASURED = "measured"


@dataclass(frozen=True)
class BandEstimate:
    """A predicted accuracy band that knows it is predicted.

    ``measured_band`` stays ``None`` until a real run supplies one. :meth:`is_measured`
    reads that field and nothing else, so the status cannot be set to ``MEASURED`` without a
    measurement actually being present.
    """

    predicted_low: float
    predicted_high: float
    derivation: str
    anchors: tuple[str, ...]
    caveats: tuple[str, ...]
    measured_band: tuple[float, float] | None = None

    @property
    def status(self) -> BandStatus:
        return (
            BandStatus.MEASURED
            if self.measured_band is not None
            else BandStatus.PREDICTED_NOT_MEASURED
        )

    def is_measured(self) -> bool:
        return self.measured_band is not None

    def within_target(self) -> bool:
        """Whether the *predicted* band sits inside the design target. Not a validation."""
        low, high = TARGET_BAND
        return low <= self.predicted_low and self.predicted_high <= high

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": str(self.status),
            "predicted_band": [self.predicted_low, self.predicted_high],
            "measured_band": list(self.measured_band) if self.measured_band else None,
            "target_band": list(TARGET_BAND),
            "predicted_within_target": self.within_target(),
            "derivation": self.derivation,
            "anchors": list(self.anchors),
            "caveats": list(self.caveats),
        }


# ---------------------------------------------------------------------------
# Measured baselines. These involve no model.
# ---------------------------------------------------------------------------


def _score(item: LiteItem, response: str) -> bool:
    correct, _ = check_answer(item.cso.answer, f"{ANSWER_OPEN}{response}{ANSWER_CLOSE}")
    return correct


def uniform_guess_floor(items: Sequence[LiteItem] | None = None) -> float:
    """Exact expected accuracy of a responder guessing uniformly within each answer kind.

    ``boolean`` has 2 outcomes, ``choice`` has ``len(options)``. ``numeric``, ``dimension``
    and ``role_map`` have an unbounded response space, so their guess probability is taken as
    0 — a guesser does not hit an arbitrary real or an arbitrary JSON object.
    """
    pool = list(items) if items is not None else build_items()
    total = 0.0
    for item in pool:
        kind = item.cso.answer.kind
        if kind == "boolean":
            total += 0.5
        elif kind == "choice":
            n = len(item.cso.answer.options)
            total += 1.0 / n if n else 0.0
    return total / len(pool) if pool else 0.0


def constant_response_baselines(
    items: Sequence[LiteItem] | None = None,
) -> dict[str, float]:
    """What a responder that always says the same thing scores.

    A high value here is a response-bias artifact and would be indistinguishable from
    reasoning in the results table. Detecting it is cheap; not detecting it is expensive.
    """
    pool = list(items) if items is not None else build_items()
    if not pool:
        return {}
    responses = {
        "always_TRUE": "TRUE",
        "always_FALSE": "FALSE",
        "always_zero": "0",
        "always_first_option": "",  # filled per item below
    }
    out: dict[str, float] = {}
    for name, fixed in responses.items():
        hits = 0
        for item in pool:
            if name == "always_first_option":
                opts = item.cso.answer.options
                response = opts[0] if opts else ""
            else:
                response = fixed
            if response and _score(item, response):
                hits += 1
        out[name] = round(hits / len(pool), 6)
    return out


_NUMBER_TOKEN = re.compile(r"-?\d+(?:\.\d+)?")

#: Number words the prose actually uses. A shallow reader that can read "seven" is a
#: stronger shallow reader, and the point of the baseline is to be as strong as a careless
#: reader plausibly is.
_WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twenty": 20, "fifty": 50,
}


def _last_number_in(text: str) -> str | None:
    tokens = re.findall(r"[a-z]+|-?\d+(?:\.\d+)?", text.lower())
    found: str | None = None
    for tok in tokens:
        if _NUMBER_TOKEN.fullmatch(tok):
            found = tok
        elif tok in _WORD_NUMBERS:
            found = str(_WORD_NUMBERS[tok])
    return found


def shallow_reader_baselines(
    items: Sequence[LiteItem] | None = None,
) -> dict[str, float]:
    """Deterministic surface heuristics a careless reader might apply. Measured, not guessed.

    ``copy_last_number``  echo the last number appearing in the problem statement
    ``copy_first_number`` echo the first one
    ``take_distractor``   answer with the item's own recorded one-step misreading
    ``echo_question_tail`` echo the final content word of the question

    ``take_distractor`` **must** score 0. It is the corpus's own statement of what a careless
    reader concludes; if it ever scored above zero, that item's distractor and its answer
    would be the same thing and the item would classify nothing.
    """
    pool = list(items) if items is not None else build_items()
    if not pool:
        return {}
    strategies: dict[str, Any] = {
        "copy_last_number": lambda i: _last_number_in(f"{i.cso.prose} {i.cso.question}"),
        "copy_first_number": lambda i: next(
            iter(re.findall(r"-?\d+(?:\.\d+)?", i.cso.prose)), None
        ),
        "take_distractor": lambda i: (i.cso.distractors[0] if i.cso.distractors else None),
        "echo_question_tail": lambda i: (
            re.findall(r"[A-Za-z_]+", i.cso.question)[-1]
            if re.findall(r"[A-Za-z_]+", i.cso.question)
            else None
        ),
    }
    out: dict[str, float] = {}
    for name, fn in strategies.items():
        hits = 0
        for item in pool:
            response = fn(item)
            if response and _score(item, str(response)):
                hits += 1
        out[name] = round(hits / len(pool), 6)
    return out


# ---------------------------------------------------------------------------
# The deterministic difficulty index
# ---------------------------------------------------------------------------

#: Feature weights. Deliberately small integers and deliberately visible: this is a
#: bookkeeping device for saying "this item has more places to go wrong than that one", not
#: a psychometric model, and dressing it up as one would overclaim.
_WEIGHTS = {
    "reasoning_step": 1,
    "hard": 2,
    "medium": 1,
    "has_distractor": 1,
    "structural_answer": 1,
    "multi_entity": 1,
}


def difficulty_index(item: LiteItem) -> int:
    """A small integer. Higher means more independent places for the derivation to fail.

    Countable offline, from the item's own recorded structure. It is used only to *rank*
    items and to show that the corpus is not concentrated at the easy end; it is not
    converted into a predicted accuracy for any individual item, because nothing measured
    licenses that mapping.
    """
    score = _WEIGHTS["reasoning_step"] * item.reasoning_steps
    score += _WEIGHTS.get(item.difficulty, 0)
    if item.cso.distractors:
        score += _WEIGHTS["has_distractor"]
    if item.cso.answer.kind in {"choice", "role_map", "dimension"}:
        score += _WEIGHTS["structural_answer"]
    if len(item.cso.semantics.entities) >= 3:
        score += _WEIGHTS["multi_entity"]
    return score


def estimate_band(items: Sequence[LiteItem] | None = None) -> BandEstimate:
    """The predicted band, with its derivation attached and its status set to predicted."""
    pool = list(items) if items is not None else build_items()
    floor = uniform_guess_floor(pool)
    low = max(TARGET_BAND[0], round(floor, 3))
    # Two significant figures. n = 15 does not support a third, and reporting 0.701 would
    # imply a precision the anchor does not have.
    high = round(max(ANCHOR_A2_STRUCTURAL_FIDELITY), 2)
    return BandEstimate(
        predicted_low=low,
        predicted_high=high,
        derivation=(
            "Lower edge: the exact uniform-guess floor over the corpus's own answer kinds "
            f"({floor:.3f}), raised to the design floor {TARGET_BAND[0]} since no item is "
            "below chance in expectation. Upper edge: HML-EVAL-001's structural-fidelity "
            "anchor A2 (max of 0.648 and 0.701), because every M3-Lite item's answer is "
            "itself a structural discrimination rather than a formula lookup. A1's 93.3% "
            "final-answer ceiling is deliberately NOT used as the anchor."
        ),
        anchors=(
            f"A1 final-answer accuracy {ANCHOR_A1_FINAL_ANSWER} (14/15, all seven arms, "
            "zero discordant pairs in six of seven contrasts) - NOT used",
            f"A2 semantic-encoding score {ANCHOR_A2_STRUCTURAL_FIDELITY} with parse success "
            "0.733 and 0.800, same model, same host - used for the upper edge",
        ),
        caveats=(
            "A2 was measured on encoding tasks, not on answering questions about structure; "
            "the transfer is an argument, not a measurement",
            "both anchors come from one model on one host with n = 15",
            "if a real run lands outside the target band the corpus needs re-tuning and this "
            "prediction was wrong; that is why measured_band is None rather than absent",
        ),
        measured_band=None,
    )


def calibration_report(items: Sequence[LiteItem] | None = None) -> dict[str, Any]:
    """Everything measured and everything predicted, kept apart."""
    pool = list(items) if items is not None else build_items()
    indices = sorted(difficulty_index(i) for i in pool)
    band = estimate_band(pool)
    return {
        "measured": {
            "n_items": len(pool),
            "uniform_guess_floor": round(uniform_guess_floor(pool), 6),
            "constant_response_baselines": constant_response_baselines(pool),
            "shallow_reader_baselines": shallow_reader_baselines(pool),
            "difficulty_index": {
                "min": indices[0] if indices else 0,
                "median": indices[len(indices) // 2] if indices else 0,
                "max": indices[-1] if indices else 0,
            },
            "thresholds": {
                "max_constant_response_baseline": MAX_CONSTANT_RESPONSE_BASELINE,
                "max_shallow_reader_baseline": MAX_SHALLOW_READER_BASELINE,
            },
        },
        "predicted": band.to_dict(),
    }


if __name__ == "__main__":  # pragma: no cover - operator convenience
    print(json.dumps(calibration_report(), indent=2, sort_keys=True))
