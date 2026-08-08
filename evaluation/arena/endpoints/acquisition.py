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
    """The declared sort of a named symbol.

    The gloss is arm-neutral and identical in all three prompts. It exists because the
    *answer space* is written in AST/HML vocabulary (`Real`, `Proposition`) while SE
    renders "are propositions" / "are exact rational numbers". Without it, two arms are
    handed their native token and SE has to translate -- which is a notation advantage
    smuggled in through the answer line rather than the state.
    """
    d = rng.choice([d for d in w.decls if d.sort in ("Real", "Proposition")])
    return _item(
        w, "SORT",
        f"What sort is declared for {d.name}? This is stated directly in the state above; "
        "no reasoning is required.\n"
        "Answer `Real` if it is declared as a real/rational number, or `Proposition` if it "
        "is declared as a proposition.",
        d.sort, ("Real", "Proposition"),
    )


def _fact_content_item(w: World, rng: random.Random) -> Item:
    """Forced choice among rendered propositions -- one is the labelled fact."""
    idx = rng.randrange(len(w.facts))
    target = w.facts[idx]
    # Distractors must differ from the answer in *rendered text*, not merely in fact
    # index. A logic world can state the same proposition under two labels, and then two
    # options read identically and the oracle names only one of them -- 11 of 600 items.
    from ..ir import canonical

    seen = {canonical(target.prop)}
    others = []
    for f in (x for j, x in enumerate(w.facts) if j != idx):
        c = canonical(f.prop)
        if c not in seen:
            seen.add(c)
            others.append(f)
    rng.shuffle(others)
    opts = [Option("", target.prop, role="correct")]
    opts += [Option("", f.prop, role="other_fact") for f in others[:3]]
    if len(opts) < 4:
        raise ValueError("not enough distinct facts for a four-way choice")
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
    """Which binder is outermost in the world's claim.

    `show_query=True` is load-bearing: the claim lives only in `renderer.question(world)`,
    and without the QUERY block this item was a coin flip in all three arms -- the only
    occurrence of `forall`/`exists` in the whole prompt was the answer line. The gloss is
    arm-neutral, for the same reason as in `_sort_item`: SE writes "for every" and "there
    exists", not `forall` and `exists`.
    """
    claim = w.query.claim
    if not isinstance(claim, Quant):
        raise ValueError("claim is not quantified")
    return _item(
        w, "BINDER_ORDER",
        "In the QUERY above, which quantifier is written OUTERMOST -- that is, which one "
        "binds first? Read it off the text; no reasoning is required.\n"
        "Answer `forall` for a universal quantifier (\"for every\") or `exists` for an "
        "existential one (\"there exists\").",
        claim.kind, ("forall", "exists"),
        show_query=True,
    )


def _goal_target_item(w: World, rng: random.Random) -> Item:
    """Which symbol the world's query is about.

    Two defects were repaired here together, and fixing either alone would have been
    worse than fixing neither:

    1. `show_query=True` -- the target lives only in `renderer.question(world)`, so
       without the QUERY block there was nothing in the prompt to read it off.
    2. Distractors are **sampled**, not taken in declaration order. The old
       `[n for n in names if n != target][:3]` always yielded `{P1, P2, P3} + target`,
       so whenever the target was `P5` or `P6` the answer space had a visible gap and
       the answer could be read off the answer line with the state ignored entirely --
       true for 76 of 200 seeds, and true for the next planned seed set. Repairing the
       query block without this would have let the item pass for the wrong reason.
    """
    names = [d.name for d in w.decls if d.sort in ("Real", "Proposition")]
    if w.query.target not in names:
        raise ValueError("no named target")
    others = [n for n in names if n != w.query.target]
    if len(others) < 3:
        raise ValueError("not enough distractors for a non-leaking answer space")
    space = sorted([w.query.target, *rng.sample(others, 3)])
    return _item(
        w, "GOAL_TARGET",
        "Which symbol is the QUERY above asking about? Read it off the QUERY; no "
        "reasoning is required.",
        w.query.target, space,
        show_query=True,
    )


def build_items(seeds, level: str = "L3") -> list[Item]:
    """Six items: three from a propositional world, three from a relational one.

    Six is what the directive asks for and is deliberately small -- this is a gate, not a
    study. The split covers both shapes of state the pilot will use.
    """
    out: list[Item] = []
    seeds = list(seeds)

    # SORT alternates its source family by seed parity. Drawn only from
    # FINITE_LOGIC_WORLD, every declaration is a `Proposition`, the distractor `Real`
    # never appears anywhere in the prompt, and the answer is `Proposition` for every
    # seed tested -- an item no model can fail without reading, which cannot contribute
    # evidence to a 5/6 bar. ALGEBRAIC_DEPENDENCY_GRAPH declares `Real`, so the answer
    # now varies with the state.
    sort_family = random.Random(f"acq|sort_family|{seeds[0]}").choice(
        ["ALGEBRAIC_DEPENDENCY_GRAPH", "FINITE_LOGIC_WORLD"]
    )
    out.append(
        _sort_item(
            generate(sort_family, level, seeds[0]),
            random.Random(f"acq|_sort_item|{seeds[0]}"),
        )
    )
    for i, builder in enumerate((_fact_content_item, _fact_count_item), start=1):
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
