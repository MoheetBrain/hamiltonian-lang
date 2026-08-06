"""Predicted difficulty — a design rubric, not a measurement.

Why this module exists
----------------------
HML-EVAL-001 was saturated. Fourteen of fifteen problems were answered correctly in
**every** arm, the minimum detectable effect was roughly 33 percentage points, and six of
seven paired contrasts contained zero discordant pairs. The pilot therefore measured
nothing about the representation: a ceiling task cannot discriminate between two arms
because both arms hit the ceiling.

The lesson is that difficulty has to be *engineered into the corpus at authoring time*,
before any model is run, and has to be checkable by a test rather than hoped for. This
module is that check.

What is estimated, and what is not
----------------------------------
:class:`DifficultyEstimate` carries a predicted base accuracy band. It is
:data:`PREDICTED_NOT_MEASURED` and the status field says so in every serialisation, every
report line and every test assertion. **No model call produced any number in this file.**
The rubric is a design instrument for avoiding a second saturated corpus; it is not
evidence, it cannot be cited as a result, and a measured accuracy that falls outside the
predicted band falsifies the rubric rather than the corpus.

The arithmetic, and where each constant comes from
--------------------------------------------------
``predicted = CEILING_ANCHOR - STEP_PENALTY * (dependent_steps - ANCHOR_STEPS) - attractor``

* :data:`CEILING_ANCHOR` = 0.93. This is the **one internal measurement** the rubric is
  anchored to: the accuracy HML-EVAL-001 actually recorded, across all seven arms, on
  items of roughly two dependent steps with no engineered attractor. Anchoring to a
  measured ceiling rather than to a guessed mid-point is what makes the subtractions
  meaningful — every term below says "how much harder than a pilot item is this".
* :data:`STEP_PENALTY` = 0.07 per dependent step beyond the anchor. A *dependent* step is
  one whose input is a previous step's output, so an error propagates rather than
  cancelling. Independent sub-calculations are not counted: three unrelated one-line
  computations are not a three-step problem.
* Attractor penalty — the load-bearing term. Every task in this corpus has a **named
  wrong answer** reachable by a standard, plausible, invalid shortcut, recorded in the
  task's ``distractors``. :data:`ATTRACTOR_PENALTY` grades how natural that shortcut is.
  This is the term that a ceiling item lacks entirely, and it is why an item here is not
  merely a longer pilot item.

The chance floor is applied last and is not cosmetic. A five-option multiple choice cannot
score below 0.20 however hard it is, so a rubric that predicted 0.05 for one would be
predicting something arithmetically impossible.

The band is +/- :data:`BAND_HALF_WIDTH` = 0.12, which is wide on purpose: a point estimate
from an unmeasured rubric would imply a precision that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

__all__ = [
    "Attractor",
    "DifficultyEstimate",
    "PREDICTED_NOT_MEASURED",
    "CEILING_ANCHOR",
    "ANCHOR_STEPS",
    "STEP_PENALTY",
    "ATTRACTOR_PENALTY",
    "BAND_HALF_WIDTH",
    "TARGET_BAND",
    "estimate",
]

#: Stamped on every difficulty figure this project emits. Never removed, never abbreviated.
PREDICTED_NOT_MEASURED = "PREDICTED_NOT_MEASURED"

#: The measured HML-EVAL-001 accuracy. The only measured quantity in this module.
CEILING_ANCHOR = 0.93

#: Dependent-step count of a typical pilot item, the anchor's implied difficulty.
ANCHOR_STEPS = 2

#: Cost of one further dependent step.
STEP_PENALTY = 0.07

#: The target base-accuracy band this corpus is authored to hit. Outside it, a paired
#: comparison either cannot discriminate (too high) or is dominated by noise (too low).
TARGET_BAND = (0.40, 0.70)

#: Half-width of the reported band. Deliberately wide; see the module docstring.
BAND_HALF_WIDTH = 0.12


class Attractor(StrEnum):
    """How natural the invalid shortcut is that produces the task's named wrong answer.

    ``HIGH`` is not "the task is hard". It means the *wrong* route is the one a competent
    reasoner reaches first — discarding a root that survives the check, averaging within
    strata, reading a nested quantifier in the convenient order. That is what suppresses
    accuracy without making a task unfair, and it is what a pilot item did not have.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


#: Accuracy cost per attractor grade.
ATTRACTOR_PENALTY: dict[Attractor, float] = {
    Attractor.LOW: 0.05,
    Attractor.MEDIUM: 0.12,
    Attractor.HIGH: 0.20,
}


@dataclass(frozen=True)
class DifficultyEstimate:
    """A predicted band with its whole derivation attached.

    The derivation travels with the number so that a reader can reject the estimate on its
    reasoning rather than having to take the figure on trust.
    """

    dependent_steps: int
    attractor: Attractor
    chance_floor: float
    predicted_accuracy: float
    band_low: float
    band_high: float
    rationale: str
    status: str = PREDICTED_NOT_MEASURED

    @property
    def in_target_band(self) -> bool:
        low, high = TARGET_BAND
        return low <= self.predicted_accuracy <= high

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "dependent_steps": self.dependent_steps,
            "attractor": str(self.attractor),
            "chance_floor": self.chance_floor,
            "predicted_accuracy": self.predicted_accuracy,
            "band": [self.band_low, self.band_high],
            "in_target_band": self.in_target_band,
            "rationale": self.rationale,
            "anchor": {
                "ceiling_anchor": CEILING_ANCHOR,
                "anchor_source": "HML-EVAL-001 measured accuracy across all seven arms",
                "anchor_steps": ANCHOR_STEPS,
            },
        }


def estimate(
    *,
    dependent_steps: int,
    attractor: Attractor,
    chance_floor: float,
    rationale: str,
) -> DifficultyEstimate:
    """Apply the rubric. Pure arithmetic over authored judgements; no model is called.

    ``chance_floor`` is the accuracy an answer-shaped guess achieves: ``1/k`` for a
    ``k``-way choice, ``0.5`` for a boolean, and ~0 for a free numeric answer. It is
    applied as a floor **after** the penalties, because no amount of engineered difficulty
    can push a five-way choice below one in five.
    """
    if dependent_steps < 1:
        raise ValueError("a task with no dependent step is not a reasoning task")
    if not 0.0 <= chance_floor < 1.0:
        raise ValueError(f"chance_floor {chance_floor} is not a probability below 1")

    raw = (
        CEILING_ANCHOR
        - STEP_PENALTY * (dependent_steps - ANCHOR_STEPS)
        - ATTRACTOR_PENALTY[attractor]
    )
    # A guessable answer cannot fall to the raw figure. The +0.05 is the margin by which a
    # reasoning model is assumed to beat blind guessing even when it reasons wrongly.
    predicted = round(max(raw, chance_floor + 0.05), 4)
    return DifficultyEstimate(
        dependent_steps=dependent_steps,
        attractor=attractor,
        chance_floor=chance_floor,
        predicted_accuracy=predicted,
        band_low=round(max(0.0, predicted - BAND_HALF_WIDTH), 4),
        band_high=round(min(1.0, predicted + BAND_HALF_WIDTH), 4),
        rationale=rationale.strip(),
    )
