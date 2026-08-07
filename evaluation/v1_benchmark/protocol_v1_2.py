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

PROTOCOL = "developmental-v1.3"

#: The amendment. Applied identically to SE and HML-V1.
#:
#: **v1.3 raises this from the 4096 that v1.2 specified.** The operational probe
#: demonstrated that 4096 cannot produce an answer at all on this model: `gemma4:31b` is a
#: reasoning model whose thinking trace is billed to `completion_tokens` but returned in a
#: separate field, and on `v1b_06` the trace consumed the entire 4096-token allowance and
#: returned **zero characters of content**. See `PROBE_FINDING` below.
PER_CALL_COMPLETION_ALLOWANCE = 8192
CALLS_PER_ARM = 2
TOTAL_COMPLETION_ALLOWANCE_PER_ARM = 16384

#: What this supersedes, named so every change is legible in the results.
SUPERSEDED_PER_CALL_BUDGET = 1024
SUPERSEDED_TOTAL_BUDGET = 2048
SUPERSEDED_RUNTIME = "4 x 8192"
V1_2_PER_CALL_BUDGET = 4096
V1_2_TOTAL_BUDGET = 8192
V1_2_RUNTIME = "2 x 16384"

#: Reconfigured after the probe, to the single 32,768-token slot the mission specifies as
#: the contingency when the two-slot arrangement cannot fit the largest matched envelope.
#: Total KV context is unchanged (`CONTEXT_LENGTH x NUM_PARALLEL` was 16384 x 2 and is now
#: 32768 x 1), so this costs no additional memory; it trades parallelism for slot size.
NUM_PARALLEL = 1
PER_SLOT_CONTEXT = 32768
RUNTIME_MEASURED = f"{NUM_PARALLEL} x {PER_SLOT_CONTEXT}"

#: What the probe measured, kept as data because it is the reason v1.3 exists.
PROBE_FINDING = {
    "at_allowance": 4096,
    "tasks": ["v1b_06_simpson_reversal", "v1b_23_knowledge_closure_choice"],
    "both_truncated": True,
    "v1b_06": {"completion_tokens": 4096, "reasoning_chars": 10617, "content_chars": 0},
    "v1b_23": {"completion_tokens": 4096, "reasoning_chars": 12070, "content_chars": 2457},
    "conclusion": (
        "The reasoning trace alone costs ~10,600-12,100 characters (~3,000-4,000 tokens). "
        "At 4096 the trace consumes the budget and the answer is empty or cut off. An empty "
        "content field is an ABSENT answer that the scorer records as a failure of the "
        "representation under test -- precisely the artefact the amendment exists to remove."
    ),
}


#: Tasks excluded before the run, each for a documented defect in the task itself and never
#: because of an observed model outcome. Exclusion is recorded here rather than by deleting
#: the task, so the corpus stays intact and the exclusion is auditable.
EXCLUDED_TASKS = {
    "v1b_11_negation_scope_choice": (
        "Pre-run defect on two independent counts. (1) The option set is not mutually "
        "exclusive: option B is a correct formalisation on its own, option C is too, and "
        "option D asserts that both are. The stem calls all five 'candidate formalisations' "
        "and asks for 'the correct option' with no 'most complete' instruction, so B is "
        "defensible and the intended answer D is not itself a formalisation. (2) The choice "
        "scorer requires exactly one option letter to appear in the answer span, and this "
        "task's correct answer intrinsically names B and C -- verified: "
        "'<ANSWER>D (both B and C are correct)</ANSWER>' scores False while a bare "
        "'<ANSWER>D</ANSWER>' scores True. The task therefore penalises a model for "
        "explaining a correct choice."
    ),
}

#: The four scorer/prompt defects v1.3 repairs, each demonstrated before any scientific
#: call. Recorded as data so a reviewer can check the claim rather than trust the prose.
HARNESS_FIXES = [
    {
        "id": "D1_last_answer_marker",
        "was": "the FIRST <ANSWER> span was scored",
        "now": "the LAST complete span is scored",
        "why": (
            "Both arms' second call says 'correct anything you find wrong, then give your "
            "final answer'. Scoring the first span penalises the second call exactly when it "
            "works, and contradicts the system prompt's 'nothing after the closing marker'."
        ),
    },
    {
        "id": "D2_exact_closed_forms",
        "was": "the first number-like substring was taken: 16/7 -> 16.0, ln(5/2) -> 5.0",
        "now": "the whole answer is parsed (decimals, fractions, sqrt/ln/log/exp/pi) or rejected",
        "why": (
            "9 of 24 keys have an exact closed form. The error is DIFFERENTIAL: an arm "
            "reasoning in a formal representation is more likely to answer 16/7 than 2.2857, "
            "so the mis-scoring falls preferentially on the treatment and biases the paired "
            "contrast rather than merely adding noise."
        ),
    },
    {
        "id": "D3_missing_marker_scored_against_whole_reply",
        "was": "no marker -> the entire reply was searched, producing spurious passes",
        "now": "no marker -> incorrect, recorded as no_answer_marker",
        "why": (
            "Demonstrated: 'The coin is flipped 10 times ... Var(H) = 2.5.' scored CORRECT "
            "against key 10. A formatting failure was scored as a reasoning success, "
            "inflating both arms toward saturation."
        ),
    },
    {
        "id": "D4_unmatched_second_call_carry",
        "was": "SE carried its whole first reply; HML carried only the extracted fence",
        "now": "both arms carry their whole first reply; HML additionally gets diagnostics",
        "why": (
            "The frozen design states the arms differ in exactly one respect. They differed "
            "in two. The asymmetry handicaps the TREATMENT, so a kill verdict resting on it "
            "would not be trustworthy."
        ),
    },
]


def amendment() -> dict[str, Any]:
    """The amendment as data, for embedding in every manifest and report."""
    return {
        "protocol": PROTOCOL,
        "supersedes": "v1 frozen budget inherited from ACQ0; and v1.2's 4096 allowance",
        "amended": {
            "per_call_completion_allowance": {
                "from": SUPERSEDED_PER_CALL_BUDGET,
                "via_v1_2": V1_2_PER_CALL_BUDGET,
                "to": PER_CALL_COMPLETION_ALLOWANCE,
            },
            "total_completion_allowance_per_arm": {
                "from": SUPERSEDED_TOTAL_BUDGET,
                "via_v1_2": V1_2_TOTAL_BUDGET,
                "to": TOTAL_COMPLETION_ALLOWANCE_PER_ARM,
            },
            "runtime": {
                "recorded_in_arms_py": SUPERSEDED_RUNTIME,
                "measured_at_v1_2": V1_2_RUNTIME,
                "reconfigured_for_v1_3": RUNTIME_MEASURED,
            },
        },
        "probe_finding_forcing_v1_3": PROBE_FINDING,
        "harness_fixes": HARNESS_FIXES,
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
