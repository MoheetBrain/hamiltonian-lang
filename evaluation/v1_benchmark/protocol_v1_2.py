"""Developmental protocol v1.2 — the amended runtime budget, and nothing else.

This module is the single machine-readable statement of what v1.2 changes relative to the
frozen v1 benchmark design. It is imported by the driver, the calibrator and the report, so
no consumer can disagree with another about what the protocol was.

**v1.2 is not the original configuration and must never be described as one.** The frozen
design in :mod:`evaluation.v1_benchmark.arms` inherits a 2048-token total completion budget
from ACQ0, giving 1024 per call. That figure was chosen so that ACQ0 and this benchmark
could share one server configuration — a scheduling constraint, not a scientific one.

Why 1024 is operationally unsafe here
-------------------------------------
The eval001 headroom screen (``evaluation/results/h2_headroom_screen/SCREEN_REPORT.json``)
recorded **11 truncations at a 2400-token cap**, and its own closing commit named the
consequence: *"the cap must be raised before any corpus is measured for real."* A
truncated completion is not a wrong answer, it is an absent one, and it is scored as a
failure of the representation under test. At 1024 tokens — less than half the cap that
already truncated — that artefact would fall on whichever arm is more verbose. The HML arm
must emit a fenced module *in addition to* its reasoning, so it is the more verbose arm by
construction, and the truncation artefact would therefore be **anti-correlated with the
treatment**. Running at 1024 would measure verbosity and report it as representation.

What is amended, and what is held fixed
---------------------------------------
Amended, identically in both arms:

* ``PER_CALL_COMPLETION_ALLOWANCE`` 1024 -> 4096
* ``TOTAL_COMPLETION_ALLOWANCE_PER_ARM`` 2048 -> 8192

Held exactly as frozen:

* temperature 0.0
* the same model and the same pinned digest
* the same two calls per task per arm
* the same 24 tasks in the same frozen order
* the same deterministic scorer
* matched mathematical information between the arms
* matched revision opportunity between the arms

The amendment is therefore a *ceiling* change applied symmetrically. It cannot advantage
either arm, because neither arm's prompt, task, or information changes; it removes a
truncation artefact that would have fallen asymmetrically.

The runtime is recorded as measured, not as inherited
-----------------------------------------------------
:data:`evaluation.v1_benchmark.arms.RUNTIME` records ``"4 x 8192"``. That string was
written when the shared ACQ0 runtime was selected. **The live server does not match it.**
Read from the running process at amendment time::

    OLLAMA_NUM_PARALLEL=2  OLLAMA_CONTEXT_LENGTH=16384  OLLAMA_KEEP_ALIVE=4h

which is a two-slot ``2 x 16384`` arrangement. This module records the measured value and
the driver refuses to start if the live server disagrees with it, so the discrepancy
cannot be inherited silently into the results.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "PROTOCOL",
    "PER_CALL_COMPLETION_ALLOWANCE",
    "TOTAL_COMPLETION_ALLOWANCE_PER_ARM",
    "CALLS_PER_ARM",
    "PER_SLOT_CONTEXT",
    "NUM_PARALLEL",
    "RUNTIME_MEASURED",
    "SUPERSEDED_PER_CALL_BUDGET",
    "SUPERSEDED_TOTAL_BUDGET",
    "SUPERSEDED_RUNTIME",
    "amendment",
]

PROTOCOL = "developmental-v1.2"

#: The amendment. Applied identically to SE and HML-V1.
PER_CALL_COMPLETION_ALLOWANCE = 4096
CALLS_PER_ARM = 2
TOTAL_COMPLETION_ALLOWANCE_PER_ARM = 8192

#: What v1.2 supersedes, named so the change is legible in the results.
SUPERSEDED_PER_CALL_BUDGET = 1024
SUPERSEDED_TOTAL_BUDGET = 2048
SUPERSEDED_RUNTIME = "4 x 8192"

#: Read from the live `ollama serve` process, not inherited from the ACQ0 selection.
NUM_PARALLEL = 2
PER_SLOT_CONTEXT = 16384
RUNTIME_MEASURED = f"{NUM_PARALLEL} x {PER_SLOT_CONTEXT}"


def amendment() -> dict[str, Any]:
    """The amendment as data, for embedding in every manifest and report."""
    return {
        "protocol": PROTOCOL,
        "supersedes": "v1 frozen budget inherited from ACQ0",
        "amended": {
            "per_call_completion_allowance": {
                "from": SUPERSEDED_PER_CALL_BUDGET,
                "to": PER_CALL_COMPLETION_ALLOWANCE,
            },
            "total_completion_allowance_per_arm": {
                "from": SUPERSEDED_TOTAL_BUDGET,
                "to": TOTAL_COMPLETION_ALLOWANCE_PER_ARM,
            },
            "runtime": {"recorded": SUPERSEDED_RUNTIME, "measured": RUNTIME_MEASURED},
        },
        "applied_identically_to_both_arms": True,
        "held_fixed": [
            "temperature 0.0",
            "same model and pinned digest",
            "same two calls per task per arm",
            "same tasks in the same frozen order",
            "same deterministic scorer",
            "matched mathematical information",
            "matched revision opportunity",
        ],
        "rationale": (
            "The eval001 screen truncated 11 of 285 completions at a 2400-token cap and its "
            "closing commit required the cap be raised before any corpus was measured for "
            "real. At 1024 the artefact would fall preferentially on the HML arm, which must "
            "emit a module in addition to its reasoning and is therefore the more verbose arm "
            "by construction. That would anti-correlate a measurement artefact with the "
            "treatment."
        ),
        "this_is_not_the_original_configuration": True,
    }
