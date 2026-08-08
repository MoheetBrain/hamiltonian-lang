"""Endpoint A -- next-action prediction.

The question is always the same shape: *given the world and what has already been
established, which of these is a correct next result?* It is forced choice, and the
correct option is unique **by construction and by check**, not by intention.

**Why uniqueness needed engineering.** The obvious phrasing -- "what is the next step of
this derivation?" -- has no unique answer whenever two variables are simultaneously
ready, which happens constantly in a dependency DAG. Scoring that would punish a model
for picking a different, equally valid step. So the correct option here is defined by a
property that can be *tested per option*:

- algebraic: the variable is not yet resolved, and every variable its definition
  mentions already is -- so it follows without deriving anything else first;
- logic: the literal is entailed by the facts together with what is established, and is
  not already established.

Every distractor provably fails that test, and `_assert_unique` re-checks all options
with the oracle before the item is emitted. An item where two options pass, or none
does, raises rather than being scored.

**Distractors are near-misses, not noise.** A wrong option that is obviously wrong
measures nothing. The four roles used are: a result that is correct but not yet
reachable (its dependencies are still open), a result for the right variable with the
wrong arithmetic, a restatement of something already established, and a claim about an
irrelevant branch. Each is the kind of error a solver that has lost track of state
actually makes.
"""

from __future__ import annotations

import random
from fractions import Fraction

from ..ir import Atom, BinOp, Cmp, Not, Num, Prop, Var, walk
from ..oracles import entailment, eval_term
from ..worlds import World, generate
from .common import LETTERS, Item, Option

__all__ = ["build_algebraic_item", "build_logic_item", "build_items"]

_N_OPTIONS = 4


class ItemConstructionError(RuntimeError):
    """A world could not yield a well-formed item. Skipped, never patched over."""


# ---------------------------------------------------------------------------
# Algebraic
# ---------------------------------------------------------------------------


def _defs(w: World) -> dict[str, tuple[Prop, set[str]]]:
    out = {}
    for f in w.facts:
        target = f.prop.left.name
        deps = {n.name for n in walk(f.prop.right) if isinstance(n, Var)}
        out[target] = (f.prop.right, deps)
    return out


def _relevant(target: str, defs) -> list[str]:
    """The target's ancestors, in a deterministic topological order."""
    order: list[str] = []
    seen: set[str] = set()

    def visit(v: str) -> None:
        if v in seen:
            return
        seen.add(v)
        for d in sorted(defs[v][1]):
            visit(d)
        order.append(v)

    visit(target)
    return order


def _ready(v: str, resolved: set[str], defs) -> bool:
    return v not in resolved and defs[v][1] <= resolved


def build_algebraic_item(w: World, rng: random.Random) -> Item:
    defs = _defs(w)
    target = w.query.target
    rel = _relevant(target, defs)
    if len(rel) < 4:
        raise ItemConstructionError(f"{w.world_id}: relevant subgraph too small")

    values: dict[str, Fraction] = {}
    for v in rel:
        values[v] = eval_term(defs[v][0], values)

    # Choose a prefix that leaves at least one ready variable and one that is not.
    choices = []
    for k in range(2, len(rel)):
        resolved = set(rel[:k])
        ready = [v for v in rel if _ready(v, resolved, defs)]
        blocked = [v for v in defs if not _ready(v, resolved, defs) and v not in resolved]
        if ready and blocked:
            choices.append((k, ready, blocked))
    if not choices:
        raise ItemConstructionError(f"{w.world_id}: no prefix leaves both a ready and a blocked variable")
    k, ready, blocked = rng.choice(choices)
    resolved = set(rel[:k])

    correct_var = ready[0]
    established = tuple(Cmp("=", Var(v), Num(values[v])) for v in rel[:k])

    opts: list[Option] = [
        Option("", Cmp("=", Var(correct_var), Num(values[correct_var])), role="correct")
    ]

    # (1) correct value, but its dependencies are not resolved yet.
    b = rng.choice(blocked)
    opts.append(Option("", Cmp("=", Var(b), Num(_value_of(b, defs, {}))), role="not_yet_reachable"))

    # (2) right variable, wrong arithmetic -- the operator flipped.
    opts.append(
        Option("", Cmp("=", Var(correct_var), Num(_flipped(correct_var, defs, values))),
               role="wrong_arithmetic")
    )

    # (3) a restatement of something already established.
    old = rng.choice(rel[:k])
    opts.append(Option("", Cmp("=", Var(old), Num(values[old])), role="already_established"))

    rng.shuffle(opts)
    opts = [Option(LETTERS[i], o.prop, o.role) for i, o in enumerate(opts)]
    answer = _assert_unique_algebraic(opts, resolved, defs, w)

    return Item(
        item_id=f"A_{w.world_id}_k{k}",
        endpoint="NEXT_ACTION",
        kind="CHOICE",
        family=w.family,
        level=w.level,
        seed=w.seed,
        world=w,
        question=(
            "Which of the following is a correct next result -- one that follows from "
            "the facts together with the results established so far, without first "
            "deriving any other value?"
        ),
        answer=answer,
        answer_space=tuple(o.key for o in opts),
        options=tuple(opts),
        established=established,
        metrics={"prefix_len": k, "relevant": len(rel), "n_options": len(opts)},
    )


def _value_of(v: str, defs, cache) -> Fraction:
    if v in cache:
        return cache[v]
    env = {d: _value_of(d, defs, cache) for d in defs[v][1]}
    cache[v] = eval_term(defs[v][0], env)
    return cache[v]


def _flipped(v: str, defs, values) -> Fraction:
    """The value the definition would take with its top-level operator flipped.

    A concrete, plausible slip rather than a random number: a solver that misreads a
    minus as a plus lands exactly here.
    """
    rhs = defs[v][0]
    if isinstance(rhs, BinOp) and rhs.op in ("+", "-"):
        flip = "-" if rhs.op == "+" else "+"
        wrong = eval_term(BinOp(flip, rhs.left, rhs.right), values)
        if wrong != values[v]:
            return wrong
    return values[v] + 1


def _assert_unique_algebraic(opts, resolved, defs, w) -> str:
    """Re-check every option with the oracle. Exactly one must pass."""
    cache: dict[str, Fraction] = {}
    passing = []
    for o in opts:
        v = o.prop.left.name
        claimed = o.prop.right.value
        if _ready(v, resolved, defs) and claimed == _value_of(v, defs, cache):
            passing.append(o.key)
    if len(passing) != 1:
        raise ItemConstructionError(
            f"{w.world_id}: {len(passing)} options satisfy the oracle, expected exactly 1"
        )
    return passing[0]


# ---------------------------------------------------------------------------
# Logic
# ---------------------------------------------------------------------------


def build_logic_item(w: World, rng: random.Random) -> Item:
    """Which literal is entailed next, given the facts plus what is established."""
    atoms = [d.name for d in w.decls]
    facts = [f.prop for f in w.facts]

    # Establish a couple of literals that the world already forces, so the prefix is
    # true rather than hypothetical.
    forced = [(a, entailment(atoms, facts, a)) for a in atoms]
    settled = [(a, v) for a, v in forced if v in ("TRUE", "FALSE")]
    if len(settled) < 2:
        raise ItemConstructionError(f"{w.world_id}: fewer than two settled atoms")
    rng.shuffle(settled)
    est = settled[: max(1, len(settled) // 2)]
    rest = settled[len(est) :]
    if not rest:
        raise ItemConstructionError(f"{w.world_id}: nothing left to ask about")

    established = tuple(
        Atom(a) if v == "TRUE" else Not(Atom(a)) for a, v in est
    )
    est_names = {a for a, _ in est}

    correct_atom, correct_val = rest[0]
    correct = Atom(correct_atom) if correct_val == "TRUE" else Not(Atom(correct_atom))

    opts = [Option("", correct, role="correct")]
    # Distractor: the same atom with the opposite polarity -- refuted, not merely open.
    opts.append(
        Option("", Not(Atom(correct_atom)) if correct_val == "TRUE" else Atom(correct_atom),
               role="opposite_polarity")
    )
    # Distractors: atoms the facts leave undetermined, in both polarities.
    open_atoms = [a for a, v in forced if v == "UNDETERMINED"]
    rng.shuffle(open_atoms)
    for a in open_atoms:
        if len(opts) >= _N_OPTIONS:
            break
        opts.append(Option("", Atom(a) if rng.random() < 0.5 else Not(Atom(a)),
                           role="undetermined"))
    # Fall back to restating something already established.
    while len(opts) < _N_OPTIONS and est_names:
        a, v = est[len(opts) % len(est)]
        opts.append(Option("", Atom(a) if v == "TRUE" else Not(Atom(a)),
                           role="already_established"))
    if len(opts) < _N_OPTIONS:
        raise ItemConstructionError(f"{w.world_id}: too few distractors")

    rng.shuffle(opts)
    opts = [Option(LETTERS[i], o.prop, o.role) for i, o in enumerate(opts)]
    answer = _assert_unique_logic(opts, atoms, facts, est_names, w)

    return Item(
        item_id=f"A_{w.world_id}_e{len(est)}",
        endpoint="NEXT_ACTION",
        kind="CHOICE",
        family=w.family,
        level=w.level,
        seed=w.seed,
        world=w,
        question=(
            "Which of the following is necessarily true given the facts, and is not "
            "already among the results established so far?"
        ),
        answer=answer,
        answer_space=tuple(o.key for o in opts),
        options=tuple(opts),
        established=established,
        metrics={"n_established": len(est), "n_options": len(opts)},
    )


def _assert_unique_logic(opts, atoms, facts, est_names, w) -> str:
    passing = []
    for o in opts:
        p = o.prop
        name = p.inner.name if isinstance(p, Not) else p.name
        want = "FALSE" if isinstance(p, Not) else "TRUE"
        if name in est_names:
            continue
        if entailment(atoms, facts, name) == want:
            passing.append(o.key)
    if len(passing) != 1:
        raise ItemConstructionError(
            f"{w.world_id}: {len(passing)} options satisfy the oracle, expected exactly 1"
        )
    return passing[0]


# ---------------------------------------------------------------------------


_BUILDERS = {
    "ALGEBRAIC_DEPENDENCY_GRAPH": build_algebraic_item,
    "FINITE_LOGIC_WORLD": build_logic_item,
}


def build_items(family: str, level: str, seeds) -> list[Item]:
    """Best-effort over a seed range; worlds that cannot yield a clean item are skipped."""
    out = []
    for s in seeds:
        w = generate(family, level, s)
        rng = random.Random(f"next_action|{family}|{level}|{s}")
        try:
            out.append(_BUILDERS[family](w, rng))
        except ItemConstructionError:
            continue
    return out
