"""Three semantically identical phrasings of one instruction, and where they may be used.

Why this probe exists
---------------------
If the winning candidate's measured parse rate moves substantially when the *wording* of
the instruction changes while its *content* does not, then ACQ0 measured a prompt, not a
syntax. That is a different failure from the one the paper describes and it is cheaper to
detect: it needs no new tasks, only the same tasks under three wordings.

What "semantically identical" is made to mean
---------------------------------------------
Not "similar". Each phrasing must discharge every obligation in
:data:`INSTRUCTION_OBLIGATIONS`, and :func:`assert_phrasings_match_in_content` checks each
one mechanically. A phrasing that dropped the fence tag, or that added an instruction the
others lack, fails the check rather than quietly becoming a fourth condition.

Where they may be used
----------------------
Development subset only. :func:`assert_development_subset_only` refuses any task id in
``TRACK_A_HELD_OUT_IDS`` — the G2 screening, G3 curriculum, G4 confirmatory and G4
replication stages. The confirmatory set decides the gate, so a task shown to the model
during a wording probe is spent, and spending it silently would inflate the gate's result
by exactly the amount nobody could later measure.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from evaluation.corpus.cso import ANSWER_CLOSE, ANSWER_OPEN

__all__ = [
    "PHRASING_IDS",
    "PHRASINGS",
    "INSTRUCTION_OBLIGATIONS",
    "PhrasingContentMismatch",
    "HeldOutTaskTouched",
    "render_phrasing",
    "assert_phrasings_match_in_content",
    "assert_development_subset_only",
    "sensitivity_design",
]


class PhrasingContentMismatch(AssertionError):
    """Two phrasings do not carry the same instruction content."""


class HeldOutTaskTouched(AssertionError):
    """A developmental probe reached a task reserved for scoring."""


#: The identifiers. ``P1`` is the phrasing the syntax tournament already uses, so the
#: probe has a reference point rather than three equally novel wordings.
PHRASING_IDS: tuple[str, ...] = ("P1_imperative", "P2_descriptive", "P3_procedural")


@dataclass(frozen=True)
class Obligation:
    """One thing every phrasing must say. Checked, not asserted in a comment."""

    key: str
    why: str
    #: Substrings, any one of which discharges the obligation. Case-insensitive.
    any_of: tuple[str, ...]


#: What every phrasing must convey. A phrasing missing any of these is not a rewording of
#: the instruction; it is a different instruction.
INSTRUCTION_OBLIGATIONS: tuple[Obligation, ...] = (
    Obligation(
        "encode_the_problem",
        "without it the model may answer the question and never produce an encoding, "
        "which would make the trial unscoreable rather than failed",
        ("encode", "write the problem", "express the problem", "render the problem"),
    ),
    Obligation(
        "use_the_reference",
        "the grammar is supplied in the prompt; a phrasing that does not point at it "
        "measures recall of the syntax instead of use of it",
        ("reference above", "notation above", "specification above", "grammar above"),
    ),
    Obligation(
        "fenced_block",
        "the scorer extracts a fenced block; a phrasing that omits the requirement "
        "changes format adherence, which is one of the eight measured quantities",
        ("fenced block", "fenced code block", "```"),
    ),
    Obligation(
        "answer_markers",
        "the answer is checked between the markers; omitting them turns a correct "
        "answer into an unparsed one",
        (ANSWER_OPEN.lower(), "answer marker"),
    ),
    Obligation(
        "encoding_before_answer",
        "the field-order rule: the encoding is the semantic prerequisite and the answer "
        "is the result field",
        ("then answer", "then give", "after the encoding", "before the answer"),
    ),
)


#: The three wordings. Each carries a ``{tag}`` slot for the candidate's fence tag so a
#: phrasing cannot hard-code one candidate's notation and thereby favour it.
PHRASINGS: Mapping[str, str] = {
    "P1_imperative": (
        "Encode the problem using the reference above. Put the encoding in a fenced "
        "block marked ```{tag}. Then answer the question, wrapping the final answer in "
        f"{ANSWER_OPEN} and {ANSWER_CLOSE} answer markers."
    ),
    "P2_descriptive": (
        "A complete reply has two parts. The first is the problem encoded in the "
        "notation above, inside a fenced block marked ```{tag}. The second, after the "
        f"encoding, is the answer to the question between the {ANSWER_OPEN} and "
        f"{ANSWER_CLOSE} answer markers."
    ),
    "P3_procedural": (
        "Proceed in two steps. Step one: express the problem in the specification above "
        "and place it in a fenced block marked ```{tag}. Step two: then give the answer "
        f"to the question, wrapped in {ANSWER_OPEN} and {ANSWER_CLOSE} answer markers."
    ),
}


def render_phrasing(phrasing_id: str, fence_tag: str) -> str:
    """One phrasing, bound to a candidate's fence tag."""
    if phrasing_id not in PHRASINGS:
        raise ValueError(
            f"unknown phrasing {phrasing_id!r}; known: {list(PHRASING_IDS)}"
        )
    return PHRASINGS[phrasing_id].format(tag=fence_tag)


def _discharged(text: str, ob: Obligation) -> bool:
    low = text.lower()
    return any(needle.lower() in low for needle in ob.any_of)


def assert_phrasings_match_in_content(fence_tag: str = "hml") -> None:
    """Every phrasing discharges every obligation. Raises naming what is missing."""
    failures: list[str] = []
    for pid in PHRASING_IDS:
        text = render_phrasing(pid, fence_tag)
        for ob in INSTRUCTION_OBLIGATIONS:
            if not _discharged(text, ob):
                failures.append(f"{pid} does not discharge {ob.key!r}: {ob.why}")
    if failures:
        raise PhrasingContentMismatch(
            "phrasings differ in content, not only in wording, so a difference between "
            "them would not be a sensitivity result:\n  " + "\n  ".join(failures)
        )


def assert_development_subset_only(task_ids: Iterable[str]) -> None:
    """Refuse any task reserved for scoring.

    Imported lazily: this module is otherwise free of the partition, and the partition
    builds the whole corpus on import.
    """
    from evaluation.syntax_gate.partition import TRACK_A_HELD_OUT_IDS

    touched = sorted(set(task_ids) & set(TRACK_A_HELD_OUT_IDS))
    if touched:
        raise HeldOutTaskTouched(
            f"{len(touched)} held-out task(s) reached a developmental probe: "
            f"{touched[:5]}. A task shown to the model during a wording probe can no "
            "longer score the gate, and spending it silently inflates the gate's result "
            "by an amount nobody can measure afterwards."
        )


def sensitivity_design(fence_tag: str = "hml") -> dict[str, Any]:
    """The probe specification, for the audit record.

    Not executed here. ``winning_candidate`` is deliberately unresolved: the probe runs
    on the *eventual* winner's fence tag, which is not known until the gate has run.
    """
    return {
        "phrasings": {pid: render_phrasing(pid, fence_tag) for pid in PHRASING_IDS},
        "obligations": [
            {"key": ob.key, "why": ob.why} for ob in INSTRUCTION_OBLIGATIONS
        ],
        "task_pool": "demonstration-stage tasks only",
        "held_out_pools_refused": [
            "G2_screening",
            "G3_curriculum",
            "G4_confirmatory",
            "G4_replication",
        ],
        "applies_to": (
            "the eventual winning syntax only; running it across all four candidates "
            "before a winner exists would spend development tasks on a question that "
            "three of the four candidates will never need answered"
        ),
        "interpretation": (
            "a substantial move in the measured quantities across P1/P2/P3 means ACQ0 "
            "measured a prompt rather than a syntax, and the gate's result does not "
            "transfer to any other wording"
        ),
    }
