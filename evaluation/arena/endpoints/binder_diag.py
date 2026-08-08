"""Binder-only diagnostic — control characterisation, **not** a fourth acquisition attempt.

The final acquisition gate returned AST 4/6 against HML 5/6 and SE 5/6, and the AST arm's
only miss was `BINDER_ORDER`. That is one item. Redesigning a control on the strength of a
single wrong answer would be indefensible; so would running a pilot whose headline contrast
is quantifier order while a known question mark hangs over the control's ability to read
binders. This instrument settles which of those it is, cheaply.

**It is deliberately not an acquisition run.** It has its own seed band, it does not gate
anything, and its outcome decides whether the AST *renderer* needs work — not whether HML
may proceed. Reading it as "acquisition attempt #4" would be exactly the repair-until-it-
passes pattern the protocol forbids.

**Design.** Eight items, two from each of the four binder combinations:

    forall → exists     exists → forall     forall → forall     exists → exists

The generator's own claim shapes cover only three of these (`exists → exists` never occurs),
so the claims are constructed directly rather than sampled. That is legitimate here because
this measures *reading*, not reasoning: the question is only ever "which binder is written
outermost", the answer is a property of the surface text, and no arithmetic, entailment or
truth evaluation is involved in answering it.

Balance matters more than realism. With two of each combination the answer key is exactly
4 `forall` and 4 `exists`, so a model that always says `forall` scores 4/8 — chance — rather
than being flattered by a skewed key.
"""

from __future__ import annotations

from dataclasses import replace

from ..ir import BVar, Quant, Rel
from ..oracles import eval_prop
from ..worlds import Query, generate
from .common import Item

__all__ = ["BINDER_COMBINATIONS", "build_items"]

#: (outer, inner). Two items are built from each, giving a 4/4 answer key.
BINDER_COMBINATIONS = (
    ("forall", "exists"),
    ("exists", "forall"),
    ("forall", "forall"),
    ("exists", "exists"),
)


def _claim(outer: str, inner: str) -> Quant:
    return Quant(
        outer, "x", "D",
        Quant(inner, "y", "D", Rel("R", (BVar("x"), BVar("y")))),
    )


def _item(seed: int, outer: str, inner: str, level: str) -> Item:
    """A quantifier world whose claim is replaced by the requested binder pair.

    The relation and domain come from the generator untouched, so the state block is an
    ordinary arena state; only the claim is constructed. The world's stored answer is
    recomputed for coherence, but nothing in this endpoint scores it -- the item's answer
    is the outermost binder.
    """
    w = generate("FINITE_QUANTIFIER_WORLD", level, seed)
    claim = _claim(outer, inner)
    truth = eval_prop(claim, table=w.relation.table(), domain=w.domain)
    w = replace(
        w,
        query=Query(
            kind="TRUTH",
            answer="TRUE" if truth else "FALSE",
            answer_space=("TRUE", "FALSE"),
            claim=claim,
        ),
        metrics=dict(w.metrics, binder_outer=outer, binder_inner=inner),
    )
    return Item(
        item_id=f"BD_{outer}_{inner}_{seed}",
        endpoint="BINDER_DIAGNOSTIC",
        kind="CLOSED",
        family=w.family,
        level=w.level,
        seed=seed,
        world=w,
        question=(
            "In the QUERY above, which quantifier is written OUTERMOST -- that is, which "
            "one binds first? Read it off the text; no reasoning is required.\n"
            "Answer `forall` for a universal quantifier (\"for every\") or `exists` for an "
            "existential one (\"there exists\")."
        ),
        answer=outer,
        answer_space=("forall", "exists"),
        show_query=True,
        metrics={"binder_outer": outer, "binder_inner": inner},
    )


def build_items(seed_base: int = 600_001, level: str = "L3", per_combination: int = 2):
    """Eight items by default: `per_combination` from each of the four binder pairs."""
    out = []
    seed = seed_base
    for outer, inner in BINDER_COMBINATIONS:
        for _ in range(per_combination):
            out.append(_item(seed, outer, inner, level))
            seed += 1
    return out
