"""Endpoint B -- paired minimal-contrast semantic sensitivity.

Each pair is two worlds that differ by **one** declared semantic edit and that have
**different answers**. Both conditions are enforced, not intended:

- *minimality* -- everything except the edit site is compared for identity, so a pair
  whose members also differ somewhere else is rejected at construction;
- *sensitivity* -- if the edit does not flip the answer, the pair tests nothing and is
  discarded.

**Scoring is both-correct, and that is the whole point.** On a two-way question a model
that always answers TRUE scores 50% per item and looks partly competent. On pairs it
scores 0, because exactly one member of every pair is TRUE. Pair scoring therefore
measures whether the distinction was *perceived*, which is precisely the claim HML makes
for itself -- that it puts semantic differences where they cannot be skimmed past. It is
also the endpoint where the generic-AST control matters most: an AST marks the same
distinctions structurally, so a gap between HML and AST here is about HML's ontology
rather than about structure.

The three contrast operators are chosen because each is a distinction the project's own
prohibited-conflations list treats as load-bearing:

1. `QUANTIFIER_ORDER` -- swapping two binders. The example in `examples/logic/` exists
   for exactly this reason: the two orders are not equivalent and their hashes differ.
2. `IMPLICATION_DIRECTION` -- `A implies B` against `B implies A`. Implication is not
   symmetric and is not correlation.
3. `OPERAND_ORDER` -- `a - b` against `b - a`. Subtraction is not commutative.
"""

from __future__ import annotations

import random

from ..ir import BinOp, Cmp, Conn, Prop, Quant, canonical
from ..oracles import entailment, eval_prop, solve_values
from ..worlds import Fact, Query, World, generate
from .common import Item

__all__ = ["build_pairs", "CONTRASTS", "ContrastError"]

CONTRASTS = ("QUANTIFIER_ORDER", "IMPLICATION_DIRECTION", "OPERAND_ORDER")


class ContrastError(RuntimeError):
    """A candidate pair failed minimality or sensitivity. Discarded, never repaired."""


def _assert_minimal(a: World, b: World, site: str) -> None:
    """Everything but the declared edit site must be identical."""
    if a.family != b.family or a.domain != b.domain or a.decls != b.decls:
        raise ContrastError("pair differs outside the edit site: declarations or domain")
    if site == "claim":
        if a.facts != b.facts or a.relation != b.relation:
            raise ContrastError("pair differs outside the edit site: facts")
        if canonical(a.query.claim) == canonical(b.query.claim):
            raise ContrastError("claims are identical -- not a contrast")
    else:
        if a.relation != b.relation:
            raise ContrastError("pair differs outside the edit site: relation")
        diff = [
            i for i, (x, y) in enumerate(zip(a.facts, b.facts, strict=True))
            if canonical(x.prop) != canonical(y.prop) or x.label != y.label
        ]
        if len(diff) != 1:
            raise ContrastError(f"{len(diff)} facts differ, expected exactly 1")
    if a.query.answer == b.query.answer:
        raise ContrastError("the edit does not change the answer -- nothing to be sensitive to")


def _swap_binders(claim: Prop) -> Prop:
    """`Q1 x . Q2 y . body`  ->  `Q2 y . Q1 x . body`, body untouched."""
    if not (isinstance(claim, Quant) and isinstance(claim.body, Quant)):
        raise ContrastError("claim is not a two-binder quantification")
    outer, inner = claim, claim.body
    return Quant(inner.kind, inner.var, inner.domain,
                 Quant(outer.kind, outer.var, outer.domain, inner.body))


def _quantifier_pair(seed: int, level: str) -> tuple[World, World]:
    w = generate("FINITE_QUANTIFIER_WORLD", level, seed)
    swapped = _swap_binders(w.query.claim)
    truth = eval_prop(swapped, table=w.relation.table(), domain=w.domain)
    twin = World(
        world_id=w.world_id + "_swap",
        family=w.family, version=w.version, seed=w.seed, level=w.level,
        decls=w.decls, facts=w.facts, domain=w.domain, relation=w.relation,
        query=Query("TRUTH", "TRUE" if truth else "FALSE", ("TRUE", "FALSE"), claim=swapped),
        metrics=dict(w.metrics, contrast="QUANTIFIER_ORDER"),
    )
    _assert_minimal(w, twin, "claim")
    return w, twin


def _implication_pair(seed: int, level: str, rng: random.Random) -> tuple[World, World]:
    w = generate("FINITE_LOGIC_WORLD", level, seed)
    atoms = [d.name for d in w.decls]
    sites = [i for i, f in enumerate(w.facts)
             if isinstance(f.prop, Conn) and f.prop.op == "implies"]
    rng.shuffle(sites)
    for i in sites:
        p = w.facts[i].prop
        flipped = Conn("implies", p.right, p.left)
        facts = tuple(
            Fact(f.label, flipped) if j == i else f for j, f in enumerate(w.facts)
        )
        try:
            ans = entailment(atoms, [f.prop for f in facts], w.query.target)
        except Exception:
            continue
        twin = World(
            world_id=w.world_id + f"_flip{i}",
            family=w.family, version=w.version, seed=w.seed, level=w.level,
            decls=w.decls, facts=facts, domain=w.domain, relation=None,
            query=Query("ENTAILMENT", ans, ("TRUE", "FALSE", "UNDETERMINED"),
                        target=w.query.target),
            metrics=dict(w.metrics, contrast="IMPLICATION_DIRECTION"),
        )
        try:
            _assert_minimal(w, twin, "fact")
        except ContrastError:
            continue
        return w, twin
    raise ContrastError(f"{w.world_id}: no implication flip changes the answer")


def _operand_pair(seed: int, level: str) -> tuple[World, World]:
    w = generate("ALGEBRAIC_DEPENDENCY_GRAPH", level, seed)
    target = w.query.target
    idx = next(i for i, f in enumerate(w.facts) if f.prop.left.name == target)
    rhs = w.facts[idx].prop.right
    if not (isinstance(rhs, BinOp) and rhs.op == "-"):
        raise ContrastError("target definition is not a subtraction")
    swapped = BinOp("-", rhs.right, rhs.left)
    facts = tuple(
        Fact(f.label, Cmp("=", f.prop.left, swapped)) if j == idx else f
        for j, f in enumerate(w.facts)
    )
    values = solve_values([f.prop for f in facts])
    v = values[target]
    twin = World(
        world_id=w.world_id + "_swapops",
        family=w.family, version=w.version, seed=w.seed, level=w.level,
        decls=w.decls, facts=facts, domain=(), relation=None,
        query=Query("VALUE",
                    str(v.numerator) if v.denominator == 1 else str(v),
                    ("an exact integer or fraction",), target=target),
        metrics=dict(w.metrics, contrast="OPERAND_ORDER"),
    )
    _assert_minimal(w, twin, "fact")
    return w, twin


def _item(w: World, pair_id: str, contrast: str) -> Item:
    return Item(
        item_id=f"B_{w.world_id}",
        endpoint="CONTRAST",
        kind="CLOSED",
        family=w.family,
        level=w.level,
        seed=w.seed,
        world=w,
        question="",  # filled per arm at prompt time
        answer=w.query.answer,
        answer_space=w.query.answer_space,
        pair_id=pair_id,
        metrics={"contrast": contrast},
    )


def build_pairs(contrast: str, level: str, seeds) -> list[tuple[Item, Item]]:
    """Best-effort: candidates that are not minimal or not sensitive are discarded."""
    out: list[tuple[Item, Item]] = []
    for s in seeds:
        rng = random.Random(f"contrast|{contrast}|{level}|{s}")
        try:
            if contrast == "QUANTIFIER_ORDER":
                a, b = _quantifier_pair(s, level)
            elif contrast == "IMPLICATION_DIRECTION":
                a, b = _implication_pair(s, level, rng)
            elif contrast == "OPERAND_ORDER":
                a, b = _operand_pair(s, level)
            else:
                raise KeyError(f"unknown contrast {contrast!r}")
        except (ContrastError, StopIteration):
            continue
        pid = f"P_{contrast}_{level}_{s}"
        out.append((_item(a, pid, contrast), _item(b, pid, contrast)))
    return out
