"""Corpus assembly: the item set, and the same item rendered for each arm.

One item, three prompts. The item -- world, question, options, answer -- is built once
and is arm-independent; the arm only decides how it is written down. That ordering is
what makes the comparison paired: every arm is asked exactly the same question about
exactly the same world, so a difference in score cannot be a difference in what was
asked.

Seeds come from `ARENA_SEED_BASE` (200_000), disjoint from the calibration band
(900_000+). Calibration instances tuned the protocol and are permanently excluded from
anything scored.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .endpoints import contrast, corruption, next_action
from .endpoints.common import Item, build_prompt
from .parity import ARM_RENDERERS
from .worlds import ARENA_SEED_BASE, ARENA_VERSION

__all__ = ["INSTRUCTIONS", "Corpus", "build_corpus", "prompts_for"]

#: One instruction block for every arm and every endpoint. Arms differ in notation, not
#: in what they are told to do.
INSTRUCTIONS = (
    "You are given a formal description of a state, and a question about it.\n"
    "Everything needed to answer is stated. Nothing is implied by convention."
)


@dataclass
class Corpus:
    version: str
    items: list[Item] = field(default_factory=list)
    #: Minimal-contrast pairs, referenced by the items they contain.
    pairs: list[tuple[Item, Item]] = field(default_factory=list)

    def by_endpoint(self, endpoint: str) -> list[Item]:
        return [i for i in self.items if i.endpoint == endpoint]


def build_corpus(
    *,
    levels=("L2", "L3", "L4"),
    n_seeds: int = 20,
    endpoints=("NEXT_ACTION", "CONTRAST", "CORRUPTION"),
) -> Corpus:
    seeds = range(ARENA_SEED_BASE + 1, ARENA_SEED_BASE + 1 + n_seeds)
    c = Corpus(version=ARENA_VERSION)

    if "NEXT_ACTION" in endpoints:
        for fam in ("ALGEBRAIC_DEPENDENCY_GRAPH", "FINITE_LOGIC_WORLD"):
            for lv in levels:
                c.items += next_action.build_items(fam, lv, seeds)

    if "CONTRAST" in endpoints:
        for kind in contrast.CONTRASTS:
            for lv in levels:
                for a, b in contrast.build_pairs(kind, lv, seeds):
                    c.pairs.append((a, b))
                    c.items += [a, b]

    if "CORRUPTION" in endpoints:
        for lv in levels:
            c.items += corruption.build_items(lv, seeds)

    return c


def prompts_for(items: list[Item], arm: str) -> list[str]:
    r = ARM_RENDERERS[arm]
    return [build_prompt(i, r, instructions=INSTRUCTIONS) for i in items]
