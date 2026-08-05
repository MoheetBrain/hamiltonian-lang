"""M3 equivalence benchmark: paired encodings, hand-checked truth, measured scores.

``pairs`` holds the corpus. ``run`` scores it and reports precision and coverage
separately, because they are different quantities and the approval criterion only
binds one of them: **no false-positive equivalences**, at whatever coverage that
costs.
"""

from __future__ import annotations

from .pairs import CATEGORIES, EQUIVALENT, NONEQUIVALENT, PAIRS, PairCase, by_category
from .run import BenchmarkResult, CaseResult, run_benchmark

__all__ = [
    "PAIRS",
    "PairCase",
    "CATEGORIES",
    "EQUIVALENT",
    "NONEQUIVALENT",
    "by_category",
    "CaseResult",
    "BenchmarkResult",
    "run_benchmark",
]
