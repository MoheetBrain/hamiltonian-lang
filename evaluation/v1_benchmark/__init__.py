"""HML-V1 matched benchmark — the project's first evidence about whether HML *helps*.

    Arm SE       problem -> structured-English reasoning -> self-review -> answer
    Arm HML-V1   problem -> unrestricted reasoning -> HML formalisation
                         -> compile and verify -> one repair -> answer

Twenty-four hard tasks across seven domains, one frozen model, temperature 0, and a
matched total generation budget. Analysed sequentially on discordant pairs alone.

This package bears on **H2 and H3**. It is not ACQ0 and not H1. ACQ0 asks whether the model
can write the syntax; this asks whether writing it changes the answer. A win driven by the
repair loop is H3 — verifier-guided reasoning — and
:mod:`~evaluation.v1_benchmark.scoring` attributes it per task so that it cannot be
reported as a win for the representation.

**No model call happens by importing anything here.** :func:`~pipeline.run_benchmark`
refuses to run without an injected client and an explicit authorisation, and the tests
drive the whole pipeline through scripted fixtures.

Status: machinery complete, **not yet run**. Every difficulty figure is
``PREDICTED_NOT_MEASURED``.

    python -m evaluation.v1_benchmark --design    # design facts; no model, no data
    python -m evaluation.v1_benchmark --run ...   # requires the Lead's authorisation
"""

from __future__ import annotations

from evaluation.v1_benchmark.arms import (
    MATCHING,
    MODEL,
    MODEL_DIGEST,
    TOTAL_COMPLETION_BUDGET,
    Arm,
)
from evaluation.v1_benchmark.difficulty import PREDICTED_NOT_MEASURED, DifficultyEstimate
from evaluation.v1_benchmark.sequential import (
    DEVELOPMENTAL_STANDING,
    Decision,
    PairCounts,
    Verdict,
    decide,
    posterior_probability,
)
from evaluation.v1_benchmark.tasks import (
    EXTENSION_COUNT,
    TASK_COUNT,
    V1_BENCHMARK_VERSION,
    BenchTask,
    build_tasks,
)

__all__ = [
    "Arm",
    "BenchTask",
    "Decision",
    "DifficultyEstimate",
    "DEVELOPMENTAL_STANDING",
    "EXTENSION_COUNT",
    "MATCHING",
    "MODEL",
    "MODEL_DIGEST",
    "PREDICTED_NOT_MEASURED",
    "PairCounts",
    "TASK_COUNT",
    "TOTAL_COMPLETION_BUDGET",
    "V1_BENCHMARK_VERSION",
    "Verdict",
    "build_tasks",
    "decide",
    "posterior_probability",
]
