"""Score the paired benchmark and report precision and coverage separately.

The two numbers answer different questions and must never be merged into one:

* **Precision** -- of the verdicts the scorer issued, how many were right? A
  false-positive equivalence is the failure that matters: it declares a wrong
  answer right and corrupts every H1/H2 number computed from it. The approval
  criterion is zero of them.
* **Coverage** -- of the pairs, how many got a verdict at all? Everything else is
  ``INCONCLUSIVE``, ``UNSUPPORTED`` or ``SEMANTIC_LOSS``, all of which are
  reported as undecided and **never** counted as failures.

Run it directly::

    .venv/bin/python -m evaluation.m3.equivalence.run
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hamiltonian_lang.equivalence import (
    AdjudicationQueue,
    Endpoint,
    EquivalenceScorer,
    EquivalenceStatus,
)

from .pairs import CATEGORIES, EQUIVALENT, NONEQUIVALENT, PAIRS, PairCase

__all__ = ["CaseResult", "BenchmarkResult", "run_benchmark", "main"]

_POSITIVE = {EquivalenceStatus.VERIFIED_EQUIVALENT}
_NEGATIVE = {
    EquivalenceStatus.VERIFIED_NONEQUIVALENT,
    EquivalenceStatus.COUNTEREXAMPLE_FOUND,
}


@dataclass(frozen=True)
class CaseResult:
    """What the scorer said about one pair, and whether that was right."""

    case: PairCase
    status: EquivalenceStatus
    decided_by: str | None
    detail: str

    @property
    def verdict(self) -> str:
        if self.status in _POSITIVE:
            return EQUIVALENT
        if self.status in _NEGATIVE:
            return NONEQUIVALENT
        return "UNDECIDED"

    @property
    def decided(self) -> bool:
        return self.verdict != "UNDECIDED"

    @property
    def correct(self) -> bool:
        return self.decided and self.verdict == self.case.truth

    @property
    def false_positive_equivalence(self) -> bool:
        """The failure the approval criterion forbids outright."""
        return self.verdict == EQUIVALENT and self.case.truth == NONEQUIVALENT

    @property
    def false_negative(self) -> bool:
        """Called non-equivalent when the two really are the same object."""
        return self.verdict == NONEQUIVALENT and self.case.truth == EQUIVALENT

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case.case_id,
            "category": self.case.category,
            "truth": self.case.truth,
            "verdict": self.verdict,
            "status": str(self.status),
            "decided_by": self.decided_by,
            "correct": self.correct,
            "false_positive_equivalence": self.false_positive_equivalence,
            "false_negative": self.false_negative,
            "detail": self.detail[:240],
            "rationale": self.case.rationale,
        }


@dataclass(frozen=True)
class BenchmarkResult:
    """Aggregates over the whole corpus, plus the per-case rows."""

    cases: tuple[CaseResult, ...]
    queue_size: int = 0
    per_category: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def decided(self) -> int:
        return sum(1 for c in self.cases if c.decided)

    @property
    def coverage(self) -> float:
        return self.decided / self.total if self.total else 0.0

    @property
    def precision(self) -> float:
        """Correct verdicts over issued verdicts. Undecided pairs are excluded."""
        return (
            sum(1 for c in self.cases if c.correct) / self.decided if self.decided else 0.0
        )

    @property
    def equivalence_precision(self) -> float:
        called = [c for c in self.cases if c.verdict == EQUIVALENT]
        if not called:
            return 1.0
        return sum(1 for c in called if c.correct) / len(called)

    @property
    def nonequivalence_precision(self) -> float:
        called = [c for c in self.cases if c.verdict == NONEQUIVALENT]
        if not called:
            return 1.0
        return sum(1 for c in called if c.correct) / len(called)

    @property
    def false_positives(self) -> tuple[CaseResult, ...]:
        return tuple(c for c in self.cases if c.false_positive_equivalence)

    @property
    def false_negatives(self) -> tuple[CaseResult, ...]:
        return tuple(c for c in self.cases if c.false_negative)

    @property
    def undecided(self) -> tuple[CaseResult, ...]:
        return tuple(c for c in self.cases if not c.decided)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "decided": self.decided,
            "coverage": round(self.coverage, 4),
            "precision": round(self.precision, 4),
            "equivalence_precision": round(self.equivalence_precision, 4),
            "nonequivalence_precision": round(self.nonequivalence_precision, 4),
            "false_positive_equivalences": [c.case.case_id for c in self.false_positives],
            "false_negatives": [c.case.case_id for c in self.false_negatives],
            "undecided": [c.case.case_id for c in self.undecided],
            "adjudication_queue": self.queue_size,
            "per_category": self.per_category,
            "cases": [c.to_dict() for c in self.cases],
        }

    def render(self) -> str:
        lines = [
            f"pairs                     {self.total}",
            f"decided                   {self.decided}",
            f"coverage                  {self.coverage:.3f}",
            f"precision (decided)       {self.precision:.3f}",
            f"equivalence precision     {self.equivalence_precision:.3f}",
            f"non-equivalence precision {self.nonequivalence_precision:.3f}",
            f"false-positive equivalences {len(self.false_positives)}"
            f"  {[c.case.case_id for c in self.false_positives]}",
            f"false negatives           {len(self.false_negatives)}"
            f"  {[c.case.case_id for c in self.false_negatives]}",
            f"undecided (queued)        {len(self.undecided)}"
            f"  {[c.case.case_id for c in self.undecided]}",
            "",
            "by category:",
        ]
        for name, row in self.per_category.items():
            lines.append(
                f"  {name:24s} n={row['n']:3d}  decided={row['decided']:3d}  "
                f"correct={row['correct']:3d}  false_positive={row['false_positive']}"
            )
        return "\n".join(lines)


def run_benchmark(
    cases: Sequence[PairCase] = PAIRS, *, endpoint: Endpoint = Endpoint.ENCODING_EQUIVALENCE
) -> BenchmarkResult:
    """Score every pair. Makes no model calls and touches no network."""
    queue = AdjudicationQueue()
    scorer = EquivalenceScorer(queue=queue)
    rows: list[CaseResult] = []
    for case in cases:
        report = scorer.compare(
            case.reference, case.candidate, endpoint=endpoint, item_id=case.case_id
        )
        rows.append(
            CaseResult(
                case=case,
                status=report.status,
                decided_by=str(report.decided_by) if report.decided_by else None,
                detail=report.detail,
            )
        )

    per_category: dict[str, dict[str, Any]] = {}
    for name in CATEGORIES:
        subset = [r for r in rows if r.case.category == name]
        per_category[name] = {
            "n": len(subset),
            "decided": sum(1 for r in subset if r.decided),
            "correct": sum(1 for r in subset if r.correct),
            "false_positive": sum(1 for r in subset if r.false_positive_equivalence),
            "false_negative": sum(1 for r in subset if r.false_negative),
        }
    return BenchmarkResult(tuple(rows), len(queue), per_category)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    result = run_benchmark()
    print(result.render())
    if "--json" in args:
        target = Path("evaluation/m3/equivalence/results/benchmark.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n")
        print(f"\nwrote {target}")
    return 1 if result.false_positives else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
