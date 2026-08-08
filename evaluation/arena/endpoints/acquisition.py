"""Acquisition sanity check -- can the model *read* each notation at all?

This is not a reasoning endpoint and is not evidence about representations. It exists to
stop one specific misreading: if HML scores badly on the pilot, the cause could be that HML
is a worse reasoning representation, or simply that the model cannot parse it. Those are
different findings with different consequences, and no amount of pilot data separates them
afterwards.

So every item here is **literal state recovery, requiring no inference**. The answer is
present in the rendered state as a fact about the notation, not as a conclusion from it:

1. `SORT` -- the declared sort of a named symbol;
2. `FACT_CONTENT` -- which option is the content of a labelled assumption;
3. `RELATION_LOOKUP` -- whether a given tuple is in the stated relation;
4. `GOAL_TARGET` -- what the question is actually asking about;
5. `BINDER_ORDER` -- which quantifier is outermost in the claim;
6. `FACT_COUNT` -- how many facts are stated.

A model that answers these cannot be said to be unable to read the notation. A model that
fails them has not been shown to reason badly in it -- only that the syntax is unfamiliar,
which is a different programme (ACQ0) and explicitly not this one.

Throwaway seeds from the `ACQUISITION` band. These items are diagnostic and are never
scored as evidence.
"""

from __future__ import annotations

import random

from ..ir import Quant
from ..worlds import World, generate
from .common import LETTERS, Item, Option

__all__ = ["build_items", "ACQUISITION_KINDS"]

ACQUISITION_KINDS = (
    "SORT", "FACT_CONTENT", "FACT_COUNT",
    "RELATION_LOOKUP", "BINDER_ORDER", "GOAL_TARGET",
)


def _item(w: World, kind: str, question: str, answer: str, space, **kw) -> Item:
    return Item(
        item_id=f"Q_{kind}_{w.world_id}",
        endpoint="ACQUISITION",
        kind=kw.pop("item_kind", "CLOSED"),
        family=w.family,
        level=w.level,
        seed=w.seed,
        world=w,
        question=question,
        answer=answer,
        answer_space=tuple(space),
        metrics={"acquisition_kind": kind},
        **kw,
    )


def _sort_item(w: World, rng: random.Random) -> Item:
    d = rng.choice([d for d in w.decls if d.sort in ("Real", "Proposition")])
    return _item(
        w, "SORT",
        f"What sort is declared for {d.name}? This is stated directly in the state above; "
        "no reasoning is required.",
        d.sort, ("Real", "Proposition"),
    )


def _fact_content_item(w: World, rng: random.Random) -> Item:
    """Forced choice among rendered propositions -- one is the labelled fact."""
    idx = rng.randrange(len(w.facts))
    target = w.facts[idx]
    others = [f for j, f in enumerate(w.facts) if j != idx]
    rng.shuffle(others)
    opts = [Option("", target.prop, role="correct")]
    opts += [Option("", f.prop, role="other_fact") for f in others[:3]]
    if len(opts) < 4:
        raise ValueError("not enough facts for a four-way choice")
    rng.shuffle(opts)
    opts = [Option(LETTERS[i], o.prop, o.role) for i, o in enumerate(opts)]
    answer = next(o.key for o in opts if o.role == "correct")
    return _item(
        w, "FACT_CONTENT",
        f"Which of the options below is exactly what fact {target.label} states? "
        "Copy it out; no reasoning is required.",
        answer, tuple(o.key for o in opts),
        item_kind="CHOICE", options=tuple(opts),
    )


def _fact_count_item(w: World, rng: random.Random) -> Item:
    n = len(w.facts)
    space = sorted({str(max(1, n + d)) for d in (-2, -1, 0, 1, 2)} | {str(n)})
    return _item(
        w, "FACT_COUNT",
        "How many separate facts are stated in the state above? Count them; no reasoning "
        "is required.",
        str(n), space,
    )


def _relation_lookup_item(w: World, rng: random.Random) -> Item:
    table = w.relation.table()
    key = rng.choice(sorted(table))
    return _item(
        w, "RELATION_LOOKUP",
        f"According to the state above, does {w.relation.name}({key[0]}, {key[1]}) hold? "
        "This is a direct lookup; no reasoning is required.",
        "TRUE" if table[key] else "FALSE", ("TRUE", "FALSE"),
    )


def _binder_order_item(w: World, rng: random.Random) -> Item:
    claim = w.query.claim
    if not isinstance(claim, Quant):
        raise ValueError("claim is not quantified")
    return _item(
        w, "BINDER_ORDER",
        "In the claim in the question above, which quantifier is written OUTERMOST -- that "
        "is, which one binds first? Read it off the text; no reasoning is required.",
        claim.kind, ("forall", "exists"),
    )


def _goal_target_item(w: World, rng: random.Random) -> Item:
    names = [d.name for d in w.decls if d.sort in ("Real", "Proposition")]
    if w.query.target not in names:
        raise ValueError("no named target")
    space = [w.query.target] + [n for n in names if n != w.query.target][:3]
    space.sort()
    return _item(
        w, "GOAL_TARGET",
        "Which symbol is the question above asking about? Read it off the question; no "
        "reasoning is required.",
        w.query.target, space,
    )


def build_items(seeds, level: str = "L3") -> list[Item]:
    """Six items: three from a propositional world, three from a relational one.

    Six is what the directive asks for and is deliberately small -- this is a gate, not a
    study. The split covers both shapes of state the pilot will use.
    """
    out: list[Item] = []
    seeds = list(seeds)
    for i, builder in enumerate((_sort_item, _fact_content_item, _fact_count_item)):
        w = generate("FINITE_LOGIC_WORLD", level, seeds[i])
        out.append(builder(w, random.Random(f"acq|{builder.__name__}|{seeds[i]}")))
    for i, builder in enumerate(
        (_relation_lookup_item, _binder_order_item), start=3
    ):
        w = generate("FINITE_QUANTIFIER_WORLD", level, seeds[i])
        out.append(builder(w, random.Random(f"acq|{builder.__name__}|{seeds[i]}")))
    w = generate("FINITE_LOGIC_WORLD", level, seeds[5])
    out.append(_goal_target_item(w, random.Random(f"acq|goal|{seeds[5]}")))
    return out
