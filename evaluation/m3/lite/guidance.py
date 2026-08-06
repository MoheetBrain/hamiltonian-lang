"""The three guidance variants — prepared, never run.

The variants
------------
``NO_SUPPLIED_SOLUTION``            the problem statement only.
``MODEL_GENERATED_LOCAL_PLAN``      the model drafts its own short plan first, then solves.
``HUMAN_WRITTEN_COMPLETE_SOLUTION`` a full worked solution is supplied alongside the problem.

Why the third is not the default
--------------------------------
FormalMATH found that supplying human-written **full solutions** sometimes *reduced* success
even on problems where ordinary chain-of-thought helped. The plausible mechanism is that a
complete solution invites transcription rather than derivation: the model reproduces the
supplied text's surface and stops reasoning, so the arm measures copying fidelity while
looking like it measures reasoning.

That makes the third variant a *treatment under test*, not a helpful default. Running an
H2 or H3 scout with it as the baseline would confound the hypothesis with a known-harmful
manipulation, and a null result would be uninterpretable.

So :data:`DEFAULT_SCOUT_GUIDANCE` is ``NO_SUPPLIED_SOLUTION``, and
:func:`assert_scout_guidance` **raises** if an H2 or H3 scout is configured with the
human-written variant without an explicit, written justification. The justification is a
required argument rather than a flag, because "someone had to type a reason" is the only
form of a warning that survives contact with a deadline.

Nothing here calls a model
--------------------------
:func:`render_prompt` builds prompt text and returns a string. There is no client, no
adapter, no transport, and ``tests/evaluation/test_corpus_governance.py`` asserts that this
package imports none. The Lead authorises live runs; this module prepares them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from evaluation.corpus.cso import ANSWER_CLOSE, ANSWER_OPEN

from hamiltonian_lang.improvement.state import Hypothesis

from .items import LiteItem

__all__ = [
    "Guidance",
    "DEFAULT_SCOUT_GUIDANCE",
    "GuidanceConfig",
    "assert_scout_guidance",
    "render_prompt",
    "GuidanceViolation",
]


class Guidance(StrEnum):
    NO_SUPPLIED_SOLUTION = "no_supplied_solution"
    MODEL_GENERATED_LOCAL_PLAN = "model_generated_local_plan"
    HUMAN_WRITTEN_COMPLETE_SOLUTION = "human_written_complete_solution"


#: The default for every H2 and H3 scout. See the module docstring.
DEFAULT_SCOUT_GUIDANCE = Guidance.NO_SUPPLIED_SOLUTION

#: Variants whose use as a scout default requires a written justification.
_REQUIRES_JUSTIFICATION = frozenset({Guidance.HUMAN_WRITTEN_COMPLETE_SOLUTION})


class GuidanceViolation(ValueError):
    """Raised when a scout is configured with a variant known to confound it."""


@dataclass(frozen=True)
class GuidanceConfig:
    """A guidance choice plus, where required, the reason it was made."""

    guidance: Guidance = DEFAULT_SCOUT_GUIDANCE
    #: Mandatory for the human-written variant. Empty otherwise.
    justification: str = ""

    def __post_init__(self) -> None:
        if self.guidance in _REQUIRES_JUSTIFICATION and not self.justification.strip():
            raise GuidanceViolation(
                f"{self.guidance} requires a written justification. FormalMATH found that "
                f"supplying a human-written complete solution sometimes reduced success "
                f"even where ordinary chain-of-thought helped, so it is a treatment under "
                f"test rather than a neutral default"
            )

    def to_dict(self) -> dict[str, Any]:
        return {"guidance": str(self.guidance), "justification": self.justification}


def assert_scout_guidance(hypothesis: Hypothesis, config: GuidanceConfig) -> None:
    """Refuse a default H2/H3 scout configured with a human-written complete solution.

    H1 is exempt: it varies the *input representation* and a supplied solution would be part
    of the manipulation under study there, not a confound with it.
    """
    if hypothesis not in {Hypothesis.H2, Hypothesis.H3}:
        return
    if config.guidance is not Guidance.HUMAN_WRITTEN_COMPLETE_SOLUTION:
        return
    raise GuidanceViolation(
        f"the default {hypothesis} scout must not supply a human-written complete solution. "
        f"{hypothesis.claim} A supplied solution invites transcription instead of "
        f"derivation, so a null result would be uninterpretable. Run it as an explicit "
        f"additional arm with its own pre-registration, not as the scout baseline "
        f"(justification on file: {config.justification!r})"
    )


_PREAMBLE = (
    "Solve the following problem. Reason carefully; the problem is built so that the most "
    "immediate reading is wrong."
)

_ANSWER_RULE = (
    f"Give your final answer wrapped in {ANSWER_OPEN} and {ANSWER_CLOSE}, as "
)

_PLAN_RULE = (
    "First write a plan of at most three lines naming the steps you will take. Do not solve "
    "the problem in the plan. Then carry the plan out."
)


def render_prompt(
    item: LiteItem,
    config: GuidanceConfig = GuidanceConfig(),
    *,
    supplied_solution: str = "",
) -> str:
    """Build the prompt text for one item under one guidance variant.

    Returns a string. It does not send it anywhere.
    """
    parts = [_PREAMBLE, "", item.cso.prose, "", item.cso.question, ""]
    if config.guidance is Guidance.MODEL_GENERATED_LOCAL_PLAN:
        parts += [_PLAN_RULE, ""]
    elif config.guidance is Guidance.HUMAN_WRITTEN_COMPLETE_SOLUTION:
        if not supplied_solution.strip():
            raise GuidanceViolation(
                f"{item.id}: the human-written variant was selected but no solution text was "
                f"supplied. Rendering it as if it were the no-solution arm would silently "
                f"merge two conditions"
            )
        parts += ["A complete worked solution to a related problem follows.", "",
                  supplied_solution.strip(), ""]
    parts.append(_ANSWER_RULE + item.cso.answer.render_instruction())
    return "\n".join(parts)
