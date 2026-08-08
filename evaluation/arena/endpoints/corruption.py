"""Endpoint C -- semantic corruption detection. Secondary, and reuses A's worlds.

The task: a proposed derivation is shown, and the solver names the **first** incorrect
line, or `NONE` if every line is right.

**Why "first incorrect line" and not "is this sound?"** A yes/no soundness question is
guessable at 50% and, worse, is passed by a solver that noticed *something* looked odd
without locating it. Naming the line requires actually recomputing the chain, and it is
still a closed answer space, so scoring stays mechanical. `NONE` is a real option and
about half the items are clean, so a solver that always cries corruption scores no better
than one that never does.

**The corruption is semantic, never syntactic.** A corrupted line is well-formed, uses
declared names, and is arithmetically wrong by a plausible slip -- a flipped operator, or
a value belonging to a neighbouring variable. Nothing is malformed, so an arm cannot win
by making bad syntax visually obvious; the error has to be *computed* in every arm. That
is the difference between testing a representation and testing a linter, and it is the
distinction the handoff asked this endpoint to respect.
"""

from __future__ import annotations

import random
from fractions import Fraction

from ..ir import BinOp, Cmp, Num, Prop, Var, walk
from ..oracles import eval_term
from ..worlds import World, generate
from .common import Item

__all__ = ["build_items", "CorruptionError"]


class CorruptionError(RuntimeError):
    """A world could not yield a clean corruption item."""


def _chain(w: World) -> list[tuple[str, Fraction, Prop]]:
    """The target's dependency chain in topological order, with exact values."""
    defs = {}
    for f in w.facts:
        deps = {n.name for n in walk(f.prop.right) if isinstance(n, Var)}
        defs[f.prop.left.name] = (f.prop.right, deps)

    order: list[str] = []
    seen: set[str] = set()

    def visit(v: str) -> None:
        if v in seen:
            return
        seen.add(v)
        for d in sorted(defs[v][1]):
            visit(d)
        order.append(v)

    visit(w.query.target)
    values: dict[str, Fraction] = {}
    out = []
    for v in order:
        values[v] = eval_term(defs[v][0], values)
        out.append((v, values[v], defs[v][0]))
    return out


def build_item(w: World, rng: random.Random) -> Item:
    chain = _chain(w)
    # Roots are bare constants; corrupting one is a reading error, not a reasoning
    # error, so only derived lines are eligible.
    derived = [i for i, (_, _, rhs) in enumerate(chain) if isinstance(rhs, BinOp)]
    if len(chain) < 4 or not derived:
        raise CorruptionError(f"{w.world_id}: chain too short to audit")

    lines = [Cmp("=", Var(v), Num(val)) for v, val, _ in chain]
    corrupt = rng.random() < 0.5

    if not corrupt:
        answer = "NONE"
        idx = -1
    else:
        idx = rng.choice(derived)
        v, val, rhs = chain[idx]
        wrong = _plausible_wrong(rhs, chain[:idx], val)
        if wrong == val:
            raise CorruptionError(f"{w.world_id}: could not construct a distinct wrong value")
        lines[idx] = Cmp("=", Var(v), Num(wrong))
        answer = f"d{idx}"

    _assert_first_error(lines, chain, idx, w)

    space = tuple(f"d{i}" for i in range(len(lines))) + ("NONE",)
    return Item(
        item_id=f"C_{w.world_id}_{'c' if corrupt else 'n'}",
        endpoint="CORRUPTION",
        kind="CLOSED",
        family=w.family,
        level=w.level,
        seed=w.seed,
        world=w,
        question=(
            "The proposed derivation below is offered as a computation of "
            f"{w.query.target}. Each line claims a value that should follow from the "
            "facts and the lines above it.\n\n"
            "Which is the FIRST line whose claimed value is incorrect? "
            "Answer NONE if every line is correct."
        ),
        answer=answer,
        answer_space=space,
        derivation=tuple(lines),
        metrics={"chain_len": len(lines), "corrupted": corrupt, "corrupt_index": idx},
    )


def _plausible_wrong(rhs: Prop, prefix, correct: Fraction) -> Fraction:
    """A flipped top-level operator: the slip a solver actually makes."""
    env = {v: val for v, val, _ in prefix}
    if isinstance(rhs, BinOp) and rhs.op in ("+", "-"):
        flip = "-" if rhs.op == "+" else "+"
        return eval_term(BinOp(flip, rhs.left, rhs.right), env)
    return correct + 1


def _assert_first_error(lines, chain, idx, w) -> None:
    """Re-derive the whole chain and confirm the intended line is the first wrong one.

    Guards the case where a "wrong" value coincides with the correct one, and the case
    where an earlier line is wrong for an unrelated reason.
    """
    first_bad = -1
    for i, ln in enumerate(lines):
        if ln.right.value != chain[i][1]:
            first_bad = i
            break
    if first_bad != idx:
        raise CorruptionError(
            f"{w.world_id}: first incorrect line is {first_bad}, expected {idx}"
        )


def build_items(level: str, seeds) -> list[Item]:
    out = []
    for s in seeds:
        w = generate("ALGEBRAIC_DEPENDENCY_GRAPH", level, s)
        rng = random.Random(f"corruption|{level}|{s}")
        try:
            out.append(build_item(w, rng))
        except CorruptionError:
            continue
    return out
