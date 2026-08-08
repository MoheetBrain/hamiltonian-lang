"""The shared item format and prompt builder.

**Every arm gets a byte-identical prompt except for the rendered blocks.** The
instructions, the section headers, the option letters, the answer rule and the closing
`FINAL:` line are one template. If the arms differed in how they *asked*, a difference in
score would be a difference in prompt engineering, and the experiment would be measuring
whichever arm happened to get the better wording.

**Answers are letters, or one word from a closed set.** Never free-form. This matters
more than it looks: if the model had to *write* an answer in each arm's notation, HML
would be scored partly on how hard HML is to emit, which is a different question from
whether HML is a better representation to reason *from*. Forced choice separates the two.
An unparseable answer is wrong, never silently retried.

Options are rendered in the arm's own representation, so an option list never leaks a
second notation into an arm.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ir import Prop
from ..worlds import World

__all__ = ["Option", "Item", "LETTERS", "build_prompt", "ANSWER_RULE"]

LETTERS = "ABCDEFGH"

ANSWER_RULE = (
    "Reason concisely. Do not restate the problem.\n"
    "End with exactly one line of the form:\n"
    "FINAL: <answer>"
)


@dataclass(frozen=True)
class Option:
    key: str
    prop: Prop
    #: Why this option is wrong, or "" for the correct one. Recorded for analysis, never
    #: shown to the model.
    role: str = ""


@dataclass(frozen=True)
class Item:
    item_id: str
    endpoint: str
    kind: str  # "CHOICE" | "CLOSED"
    family: str
    level: str
    seed: int
    world: World
    question: str
    answer: str
    answer_space: tuple[str, ...]
    options: tuple[Option, ...] = ()
    #: Facts established before the question is asked, for next-action items.
    established: tuple[Prop, ...] = ()
    #: A proposed chain of results to be audited, for corruption items. Rendered in the
    #: arm's own notation and addressed by shared labels, so the *question* is identical
    #: across arms while the notation under audit is not.
    derivation: tuple[Prop, ...] = ()
    #: Pairs this item with its twin, for paired minimal contrasts.
    pair_id: str = ""
    metrics: dict = field(default_factory=dict)


def build_prompt(item: Item, renderer, *, instructions: str) -> str:
    """Assemble the prompt for one arm. The only arm-dependent parts are rendered blocks."""
    out = [instructions, "", "STATE", "", renderer.state(item.world)]

    if item.established:
        out += ["", "ESTABLISHED SO FAR", ""]
        out += [f"  e{i}. {renderer.prop(p)}" for i, p in enumerate(item.established)]

    if item.derivation:
        out += ["", "PROPOSED DERIVATION", ""]
        out += [f"  d{i}. {renderer.prop(p)}" for i, p in enumerate(item.derivation)]

    # An empty question means "ask the world's own query". Contrast items must do this,
    # because the claim under test has to be rendered in the arm's own notation -- a
    # question fixed at construction time would put one arm's syntax into all three.
    question = item.question or renderer.question(item.world)
    out += ["", "QUESTION", "", question]

    if item.kind == "CHOICE":
        out += ["", "OPTIONS", ""]
        out += [f"  {o.key}. {renderer.prop(o.prop)}" for o in item.options]
        space = ", ".join(o.key for o in item.options)
    else:
        space = ", ".join(item.answer_space)

    out += ["", f"Answer with exactly one of: {space}.", "", ANSWER_RULE]
    return "\n".join(out)
