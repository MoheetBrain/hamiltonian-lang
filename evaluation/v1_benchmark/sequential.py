"""Sequential analysis on discordant pairs. Standard library only, exact arithmetic.

The model
---------
A paired design learns nothing from a task both arms get right or both get wrong. Only the
**discordant** pairs carry information:

    w = solved by HML-V1 and not by SE
    l = solved by SE and not by HML-V1

With a uniform prior on the probability that a discordant pair falls to HML-V1,

    theta | D  ~  Beta(1 + w, 1 + l)

and the reported quantity is ``P(theta > 0.5 | D)``.

Why the arithmetic is exact
---------------------------
For integer parameters the Beta tail is a finite binomial sum:

    P(theta > 0.5) = sum_{j=0..w} C(w+l+1, j) / 2^(w+l+1)

computed here in :class:`fractions.Fraction`, so the reported probability is exact and
carries no floating-point error, no special-function library and no dependency the project
does not already have. This is the project's established standard-library constraint, and
here it costs nothing: the closed form is simpler than the numerical alternative.

The decision rule, pre-registered
---------------------------------
After 24 tasks:

* ``P >= 0.90`` **and** absolute uplift ``>= 10`` percentage points
  -> :data:`Verdict.STRONG_DEVELOPMENTAL_SIGNAL`
* ``P <= 0.20`` -> :data:`Verdict.NO_CURRENT_BENEFIT_SIGNAL`
* otherwise -> :data:`Verdict.EXTEND_TO_40`

After 40 the same thresholds apply and the third branch becomes
:data:`Verdict.INCONCLUSIVE`, because there is no third tranche: a rule that could extend
indefinitely is a rule that stops when it likes the answer.

Both conditions are required for a positive verdict, and the second is doing real work.
``P >= 0.90`` is reachable on three discordant pairs and no losses, which is not a result
anybody should act on. The uplift floor forces the effect to be visible in the raw task
counts as well as in the posterior.

Fragility
---------
:attr:`Decision.flips_to_change` reports the smallest number of task outcomes that would
have to flip to change the verdict. It is computed by exhaustive search over single-task
perturbations, not estimated. A verdict that one task would overturn is reported with that
number attached, every time, because "STRONG DEVELOPMENTAL SIGNAL" and "three discordant
pairs" belong in the same sentence.

Nothing here is proof
---------------------
:data:`DEVELOPMENTAL_STANDING` is the wording that must accompany every verdict. It is a
data member rather than a comment so that a report cannot render a verdict without it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from math import comb
from typing import Any

__all__ = [
    "Verdict",
    "PairCounts",
    "Decision",
    "PROBABILITY_THRESHOLD",
    "NULL_THRESHOLD",
    "UPLIFT_THRESHOLD_POINTS",
    "DEVELOPMENTAL_STANDING",
    "posterior_probability",
    "decide",
]

#: P(theta > 0.5 | D) at or above which a positive verdict is permitted.
PROBABILITY_THRESHOLD = Fraction(90, 100)

#: P(theta > 0.5 | D) at or below which the study reports no current benefit.
NULL_THRESHOLD = Fraction(20, 100)

#: Absolute answer-accuracy uplift, in percentage points, additionally required.
UPLIFT_THRESHOLD_POINTS = 10.0

#: Attached to every verdict this module produces. Never omitted, never paraphrased.
DEVELOPMENTAL_STANDING = (
    "DEVELOPMENTAL RESULT, NOT PROOF. This is a 24-task (or, after extension, 40-task) "
    "paired comparison on a single model at a single temperature, analysed on its "
    "discordant pairs alone. It is evidence about a direction of development. It is not a "
    "demonstration that the representation helps, it does not generalise beyond this model "
    "and this corpus, and no verdict it produces may be reported as a benchmark result or "
    "as superiority over any other language or notation."
)


class Verdict(StrEnum):
    STRONG_DEVELOPMENTAL_SIGNAL = "STRONG_DEVELOPMENTAL_SIGNAL"
    NO_CURRENT_BENEFIT_SIGNAL = "NO_CURRENT_BENEFIT_SIGNAL"
    EXTEND_TO_40 = "EXTEND_TO_40"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class PairCounts:
    """The four cells of the paired table. Only ``w`` and ``l`` enter the posterior."""

    #: solved by HML-V1, not by SE. The spec calls this ``w``.
    w: int
    #: solved by SE, not by HML-V1. The spec calls this ``l``; the identifier is spelled
    #: out because a lone ``l`` is not distinguishable from ``1`` in most fonts, and the
    #: reported JSON key keeps the ``l_se_only`` spelling so the notation still matches.
    losses: int
    #: solved by both
    both: int
    #: solved by neither
    neither: int

    def __post_init__(self) -> None:
        for name in ("w", "losses", "both", "neither"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")

    @property
    def n(self) -> int:
        return self.w + self.losses + self.both + self.neither

    @property
    def discordant(self) -> int:
        return self.w + self.losses

    @property
    def se_correct(self) -> int:
        return self.losses + self.both

    @property
    def hml_correct(self) -> int:
        return self.w + self.both

    @property
    def uplift_points(self) -> float:
        """Absolute answer-accuracy difference in percentage points, HML minus SE.

        Equal to ``100 * (w - l) / n``: the concordant cells cancel exactly.
        """
        if self.n == 0:
            return 0.0
        return round(100.0 * (self.hml_correct - self.se_correct) / self.n, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "w_hml_only": self.w,
            "l_se_only": self.losses,
            "both": self.both,
            "neither": self.neither,
            "n": self.n,
            "discordant": self.discordant,
            "se_accuracy": round(self.se_correct / self.n, 4) if self.n else None,
            "hml_accuracy": round(self.hml_correct / self.n, 4) if self.n else None,
            "uplift_points": self.uplift_points,
        }


def posterior_probability(w: int, losses: int) -> Fraction:
    """``P(theta > 0.5 | D)`` for ``theta | D ~ Beta(1 + w, 1 + l)``. Exact.

    With no discordant pairs at all this returns exactly ``1/2`` — the prior, unmoved —
    which is the correct and necessary behaviour: a design that produced no discordant
    pairs has learned nothing, and that is exactly what sank HML-EVAL-001.
    """
    if w < 0 or losses < 0:
        raise ValueError("discordant counts cannot be negative")
    n = w + losses + 1
    total = sum(comb(n, j) for j in range(w + 1))
    return Fraction(total, 2**n)


@dataclass(frozen=True)
class Decision:
    counts: PairCounts
    probability: Fraction
    verdict: Verdict
    tranche: int
    flips_to_change: int | None
    standing: str = DEVELOPMENTAL_STANDING

    @property
    def probability_float(self) -> float:
        return round(float(self.probability), 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": str(self.verdict),
            "tranche": self.tranche,
            "posterior_p_theta_gt_half": self.probability_float,
            "posterior_exact": f"{self.probability.numerator}/{self.probability.denominator}",
            "thresholds": {
                "probability": float(PROBABILITY_THRESHOLD),
                "null": float(NULL_THRESHOLD),
                "uplift_points": UPLIFT_THRESHOLD_POINTS,
            },
            "counts": self.counts.to_dict(),
            "flips_to_change_verdict": self.flips_to_change,
            "standing": self.standing,
        }


def _verdict_for(counts: PairCounts, tranche: int) -> Verdict:
    p = posterior_probability(counts.w, counts.losses)
    if p >= PROBABILITY_THRESHOLD and counts.uplift_points >= UPLIFT_THRESHOLD_POINTS:
        return Verdict.STRONG_DEVELOPMENTAL_SIGNAL
    if p <= NULL_THRESHOLD:
        return Verdict.NO_CURRENT_BENEFIT_SIGNAL
    return Verdict.EXTEND_TO_40 if tranche < 40 else Verdict.INCONCLUSIVE


def _neighbours(c: PairCounts) -> list[PairCounts]:
    """Every table reachable by moving one task between adjacent cells.

    A single task's outcome can change in these ways: an HML-only win becomes concordant
    or becomes an SE-only win, and symmetrically. Enumerated rather than reasoned about.
    """
    out: list[PairCounts] = []
    moves = [
        ("w", "both"), ("w", "neither"), ("w", "losses"),
        ("losses", "both"), ("losses", "neither"), ("losses", "w"),
        ("both", "w"), ("both", "losses"),
        ("neither", "w"), ("neither", "losses"),
    ]
    cells = {"w": c.w, "losses": c.losses, "both": c.both, "neither": c.neither}
    for src, dst in moves:
        if cells[src] <= 0:
            continue
        nxt = dict(cells)
        nxt[src] -= 1
        nxt[dst] += 1
        out.append(PairCounts(**nxt))  # type: ignore[arg-type]
    return out


def _flips_to_change(counts: PairCounts, tranche: int, verdict: Verdict) -> int | None:
    """Smallest number of single-task flips that changes the verdict, searched to depth 3.

    Returns ``None`` when no perturbation of three tasks or fewer changes it. Breadth-first
    over the reachable tables, so the answer is exact within that depth rather than a bound.
    """
    frontier = [counts]
    seen = {(counts.w, counts.losses, counts.both, counts.neither)}
    for depth in (1, 2, 3):
        nxt: list[PairCounts] = []
        for c in frontier:
            for cand in _neighbours(c):
                key = (cand.w, cand.losses, cand.both, cand.neither)
                if key in seen:
                    continue
                seen.add(key)
                if _verdict_for(cand, tranche) is not verdict:
                    return depth
                nxt.append(cand)
        frontier = nxt
    return None


def decide(counts: PairCounts, *, tranche: int | None = None) -> Decision:
    """Apply the pre-registered rule. Pure arithmetic; no data are re-read, nothing is fit.

    ``tranche`` defaults to the observed ``n``. It selects which branch the third case
    takes — extend at 24, close as inconclusive at 40 — and is recorded in the result so
    that a verdict cannot be quoted without the sample size it was taken at.
    """
    t = counts.n if tranche is None else tranche
    verdict = _verdict_for(counts, t)
    return Decision(
        counts=counts,
        probability=posterior_probability(counts.w, counts.losses),
        verdict=verdict,
        tranche=t,
        flips_to_change=_flips_to_change(counts, t, verdict),
    )
