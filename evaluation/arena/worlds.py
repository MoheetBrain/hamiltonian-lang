"""Structure-first neutral world factory for the representation arena.

Three families, each deterministic in its seed, each returning a `World` that **retains
its own structure**. This is the difference from `difficulty_lab.families`, which
renders English inline and discards the DAG -- see `ir.py` for why that made "just add a
rendering layer" impossible there.

**Neutrality.** Worlds are generated in Python from a difficulty target, never written
in HML and translated. A benchmark authored in HML and rendered into English would be
native to HML by construction and could not fairly test it. Nothing in this module
imports the compiler.

**Self-checking.** Every world is solved twice: once incidentally, as the generator
accumulates values while building, and once from the finished fact set by
`oracles.py`. `generate()` asserts the two agree before returning. A generator that
emitted a fact inconsistent with its own arithmetic fails here rather than becoming a
confidently wrong answer key.

**Seed bands.** Arena worlds draw from `ARENA_SEED_BASE = 200_000`. The synthetic
calibration used `900_000+`. The bands are disjoint on purpose: calibration instances
are permanently excluded from any scored arena run, so nothing that tuned the protocol
can also be measured by it.

The level ladder mirrors `difficulty-lab-1.0.0`'s L1-L5 so that arena difficulty is
comparable to the levels already calibrated. It is copied rather than imported: the
difficulty lab is frozen evidence and gains nothing from a new importer.
`tests/arena/test_worlds.py` asserts the shared entries have not drifted apart.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from fractions import Fraction

from .ir import (
    Atom,
    BinOp,
    BVar,
    Cmp,
    Conn,
    Not,
    Num,
    Prop,
    Quant,
    Rel,
    Var,
    canonical,
)
from .oracles import entailment, eval_prop, solve_values

__all__ = [
    "ARENA_VERSION",
    "ARENA_SEED_BASE",
    "LEVELS",
    "FAMILIES",
    "FAMILY_CODES",
    "Decl",
    "Fact",
    "Query",
    "Relation",
    "World",
    "generate",
    "canonical_world",
]

ARENA_VERSION = "arena-1.0.0"
ARENA_SEED_BASE = 200_000

#: Mirrors difficulty-lab-1.0.0's L1-L5 exactly. Difficulty is MORE INTERACTING STATE,
#: never a longer requested answer: every arena answer is one line from a closed set.
LEVELS: dict[str, dict] = {
    "L1": {"facts": 5, "depth": 3, "distractors": 1, "vars": 4, "alternations": 1},
    "L2": {"facts": 7, "depth": 4, "distractors": 1, "vars": 5, "alternations": 1},
    "L3": {"facts": 9, "depth": 5, "distractors": 2, "vars": 6, "alternations": 2},
    "L4": {"facts": 12, "depth": 7, "distractors": 3, "vars": 7, "alternations": 2},
    "L5": {"facts": 15, "depth": 9, "distractors": 4, "vars": 8, "alternations": 3},
}


@dataclass(frozen=True)
class Decl:
    """A declared name and its sort. Every arm states sorts; none may infer them."""

    name: str
    sort: str  # "Real" | "Proposition" | "Relation"
    arity: int = 0


@dataclass(frozen=True)
class Fact:
    """A labelled asserted proposition.

    Labels are addressing, not information: all three arms use the same labels, so a
    premise can be referred to identically in an English option, an AST option and an
    HML option. Without shared labels the arms could not pose the same question.
    """

    label: str
    prop: Prop


@dataclass(frozen=True)
class Relation:
    """A finite relation given by its full extension.

    Carried as a record rather than as a list of per-tuple facts because HML cannot
    render per-tuple facts about an uninterpreted predicate -- see the note in `ir.py`.
    Each renderer states this table once, in its own idiom.
    """

    name: str
    arity: int
    domain: tuple[int, ...]
    true_tuples: tuple[tuple[int, ...], ...]

    def table(self) -> dict[tuple[int, ...], bool]:
        from itertools import product as _product

        true = set(self.true_tuples)
        return {k: (k in true) for k in _product(self.domain, repeat=self.arity)}


@dataclass(frozen=True)
class Query:
    kind: str  # "VALUE" | "ENTAILMENT" | "TRUTH"
    answer: str
    answer_space: tuple[str, ...]
    #: The queried variable/atom name, for VALUE and ENTAILMENT.
    target: str = ""
    #: The queried claim, for TRUTH.
    claim: Prop | None = None


@dataclass(frozen=True)
class World:
    world_id: str
    family: str
    version: str
    seed: int
    level: str
    decls: tuple[Decl, ...]
    facts: tuple[Fact, ...]
    query: Query
    domain: tuple[int, ...] = ()
    relation: Relation | None = None
    metrics: dict = field(default_factory=dict)

    def fact(self, label: str) -> Fact:
        for f in self.facts:
            if f.label == label:
                return f
        raise KeyError(f"no fact labelled {label!r} in {self.world_id}")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["facts"] = [{"label": f.label, "prop": canonical(f.prop)} for f in self.facts]
        d["query"] = {
            "kind": self.query.kind,
            "answer": self.query.answer,
            "answer_space": list(self.query.answer_space),
            "target": self.query.target,
            "claim": canonical(self.query.claim) if self.query.claim else None,
        }
        return d


def canonical_world(w: World) -> str:
    """Order-insensitive identity of a world's *content*.

    Facts are sorted, because the order they are presented in is a rendering choice and
    two renderings that differ only in fact order still carry the same information.
    Labels are kept inside the sorted key so a relabelling is still a difference.
    """
    decls = " ".join(sorted(f"(decl {d.name} {d.sort} {d.arity})" for d in w.decls))
    facts = " ".join(sorted(f"(fact {f.label} {canonical(f.prop)})" for f in w.facts))
    q = w.query
    claim = canonical(q.claim) if q.claim is not None else "-"
    dom = " ".join(str(e) for e in w.domain)
    if w.relation is None:
        rel = "-"
    else:
        pairs = " ".join(
            "(" + ",".join(str(x) for x in t) + ")" for t in sorted(w.relation.true_tuples)
        )
        rel = f"({w.relation.name} {w.relation.arity} {pairs})"
    return (
        f"(world {w.family} (domain {dom}) (rel {rel}) (decls {decls}) (facts {facts}) "
        f"(query {q.kind} {q.target} {claim}))"
    )


def _frac(v: Fraction) -> str:
    return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"


# ---------------------------------------------------------------------------
# A. ALGEBRAIC_DEPENDENCY_GRAPH
# ---------------------------------------------------------------------------


def _algebraic(rng: random.Random, level: str, wid: str, seed: int) -> World:
    """A DAG of exact rational definitions with distractor branches.

    Every internal variable is an integer combination of two earlier ones, so the
    arithmetic stays small and the work is holding the chain. Division never appears, so
    no term can be undefined and no world depends on a definedness side condition.
    """
    p = LEVELS[level]
    depth, n_dis = p["depth"], p["distractors"]
    names = [f"v{i}" for i in range(depth + n_dis + 2)]
    rng.shuffle(names)

    value: dict[str, Fraction] = {}
    props: list[Prop] = []

    for r in names[:2]:
        value[r] = Fraction(rng.randint(2, 9))
        props.append(Cmp("=", Var(r), Num(value[r])))

    chain = names[2 : 2 + depth]
    pool = names[:2]
    for nm in chain:
        a, b = rng.sample(pool, 2)
        ca, cb = rng.randint(2, 5), rng.randint(1, 4)
        op = rng.choice(["+", "-"])
        value[nm] = ca * value[a] + cb * value[b] if op == "+" else ca * value[a] - cb * value[b]
        props.append(
            Cmp(
                "=",
                Var(nm),
                BinOp(
                    op,
                    BinOp("*", Num(Fraction(ca)), Var(a)),
                    BinOp("*", Num(Fraction(cb)), Var(b)),
                ),
            )
        )
        pool.append(nm)

    target = chain[-1]

    for nm in names[2 + depth : 2 + depth + n_dis]:
        a, b = rng.sample(pool, 2)
        ca, cb = rng.randint(2, 5), rng.randint(1, 4)
        value[nm] = ca * value[a] + cb * value[b]
        props.append(
            Cmp(
                "=",
                Var(nm),
                BinOp(
                    "+",
                    BinOp("*", Num(Fraction(ca)), Var(a)),
                    BinOp("*", Num(Fraction(cb)), Var(b)),
                ),
            )
        )

    rng.shuffle(props)
    facts = tuple(Fact(f"f{i}", pr) for i, pr in enumerate(props))
    used = sorted({n.name for pr in props for n in _vars_of(pr)})

    # Independent re-solve from the finished fact set.
    solved = solve_values([f.prop for f in facts])
    if solved.get(target) != value[target]:
        raise AssertionError(
            f"{wid}: generator says {target}={value[target]}, oracle says {solved.get(target)}"
        )

    return World(
        world_id=wid,
        family="ALGEBRAIC_DEPENDENCY_GRAPH",
        version=ARENA_VERSION,
        seed=seed,
        level=level,
        decls=tuple(Decl(n, "Real") for n in used),
        facts=facts,
        query=Query(
            kind="VALUE",
            answer=_frac(value[target]),
            answer_space=("an exact integer or fraction",),
            target=target,
        ),
        metrics={
            "n_facts": len(facts),
            "n_relevant_facts": depth + 2,
            "n_distractors": n_dis,
            "dependency_depth": depth,
        },
    )


def _vars_of(p: Prop):
    from .ir import walk

    return [n for n in walk(p) if isinstance(n, Var)]


# ---------------------------------------------------------------------------
# B. FINITE_LOGIC_WORLD
# ---------------------------------------------------------------------------

#: Four distinct connective shapes. The difficulty lab had six English templates, two of
#: which ("if ... then", "does not hold unless") denote the same implication. Surface
#: variation belongs in the renderer, not the structure -- keeping it here would mean
#: the AST and HML arms had to invent a distinction that carries no information.
_LOGIC_SHAPES = ("implies", "nand", "or", "iff")


def _logic_prop(shape: str, a: str, b: str) -> Prop:
    if shape == "implies":
        return Conn("implies", Atom(a), Atom(b))
    if shape == "nand":
        return Not(Conn("and", Atom(a), Atom(b)))
    if shape == "or":
        return Conn("or", Atom(a), Atom(b))
    return Conn("iff", Atom(a), Atom(b))


def _logic(rng: random.Random, level: str, wid: str, seed: int) -> World:
    """A satisfiable propositional world whose query may be UNDETERMINED."""
    p = LEVELS[level]
    n = p["vars"]
    names = [f"P{i + 1}" for i in range(n)]

    for _ in range(400):
        constraints = [
            _logic_prop(rng.choice(_LOGIC_SHAPES), *rng.sample(names, 2))
            for _ in range(p["facts"])
        ]
        anchors = rng.sample(names, min(2, n))
        anchor_props = [
            Atom(nm) if rng.choice([True, False]) else Not(Atom(nm)) for nm in anchors
        ]
        all_props = anchor_props + constraints
        try:
            query = rng.choice(names)
            answer = entailment(names, all_props, query)
        except Exception:
            continue
        # Prefer worlds that are not trivially all-TRUE: UNDETERMINED and FALSE are
        # where the reasoning actually happens.
        if answer == "TRUE" and rng.random() < 0.6:
            continue
        break
    else:  # pragma: no cover - the retry loop essentially always succeeds
        raise RuntimeError(f"{wid}: could not generate a satisfiable logic world")

    rng.shuffle(all_props)
    facts = tuple(Fact(f"f{i}", pr) for i, pr in enumerate(all_props))

    return World(
        world_id=wid,
        family="FINITE_LOGIC_WORLD",
        version=ARENA_VERSION,
        seed=seed,
        level=level,
        decls=tuple(Decl(nm, "Proposition") for nm in names),
        facts=facts,
        query=Query(
            kind="ENTAILMENT",
            answer=answer,
            answer_space=("TRUE", "FALSE", "UNDETERMINED"),
            target=query,
        ),
        metrics={
            "n_facts": len(facts),
            "n_variables": n,
            "n_constraints": len(constraints),
        },
    )


# ---------------------------------------------------------------------------
# C. FINITE_QUANTIFIER_WORLD
# ---------------------------------------------------------------------------

#: Claim shapes. The first two are the canonical quantifier-order minimal contrast:
#: they differ only in the nesting of the two binders and disagree on most tables.
_CLAIM_SHAPES = ("forall_exists", "exists_forall", "symmetry", "exists_row_empty")


def _claim(shape: str, dom: str) -> Prop:
    R = lambda *a: Rel("R", tuple(a))  # noqa: E731
    if shape == "forall_exists":
        return Quant("forall", "x", dom, Quant("exists", "y", dom, R(BVar("x"), BVar("y"))))
    if shape == "exists_forall":
        return Quant("exists", "y", dom, Quant("forall", "x", dom, R(BVar("x"), BVar("y"))))
    if shape == "symmetry":
        return Quant(
            "forall", "x", dom,
            Quant("forall", "y", dom,
                  Conn("implies", R(BVar("x"), BVar("y")), R(BVar("y"), BVar("x")))),
        )
    return Quant("exists", "x", dom, Quant("forall", "y", dom, Not(R(BVar("x"), BVar("y")))))


def _quantifier(rng: random.Random, level: str, wid: str, seed: int) -> World:
    """An explicit finite relation and a quantified claim over it.

    The relation is enumerated in full -- one fact per ordered pair, positive or
    negated. English could state it as "and for no others"; expanding it instead means
    every arm carries literally the same facts, so the comparison is about form and not
    about which notation has the shorter idiom for closure.
    """
    p = LEVELS[level]
    d = min(3 + p["alternations"], 5)
    elems = tuple(range(1, d + 1))
    dom = "D"

    for _ in range(400):
        table = {(a, b): rng.random() < 0.45 for a in elems for b in elems}
        shape = rng.choice(_CLAIM_SHAPES)
        claim = _claim(shape, dom)
        truth = eval_prop(claim, table=table, domain=elems)
        # Avoid a run of same-signed answers; both truth values must occur in a corpus.
        if rng.random() < 0.5 and not truth:
            continue
        break

    relation = Relation(
        name="R",
        arity=2,
        domain=elems,
        true_tuples=tuple(sorted(k for k, v in table.items() if v)),
    )

    # Independent re-read: rebuild the table from the stored extension and re-evaluate.
    reread = relation.table()
    if reread != table:
        raise AssertionError(f"{wid}: relation table did not survive extension storage")
    if eval_prop(claim, table=reread, domain=elems) is not truth:
        raise AssertionError(f"{wid}: claim truth changed under re-read")

    return World(
        world_id=wid,
        family="FINITE_QUANTIFIER_WORLD",
        version=ARENA_VERSION,
        seed=seed,
        level=level,
        decls=(Decl("R", "Relation", arity=2),),
        facts=(),
        domain=elems,
        relation=relation,
        query=Query(
            kind="TRUTH",
            answer="TRUE" if truth else "FALSE",
            answer_space=("TRUE", "FALSE"),
            claim=claim,
        ),
        metrics={
            "n_facts": 1,
            "domain_size": d,
            "n_true_pairs": len(relation.true_tuples),
            "n_tuples": d * d,
            "claim_shape": shape,
            "quantifier_alternations": 2,
        },
    )


FAMILIES: dict[str, object] = {
    "ALGEBRAIC_DEPENDENCY_GRAPH": _algebraic,
    "FINITE_LOGIC_WORLD": _logic,
    "FINITE_QUANTIFIER_WORLD": _quantifier,
}

#: Explicit short codes rather than ``family[:4]``. Both finite families begin "fini",
#: so a truncation scheme silently gives two different worlds the same id, and a
#: results file keyed by id would then overwrite one family with the other.
FAMILY_CODES: dict[str, str] = {
    "ALGEBRAIC_DEPENDENCY_GRAPH": "alg",
    "FINITE_LOGIC_WORLD": "log",
    "FINITE_QUANTIFIER_WORLD": "qnt",
}


def generate(family: str, level: str, seed: int) -> World:
    """Deterministic in ``seed``: the same seed always yields the same world."""
    if family not in FAMILIES:
        raise KeyError(f"unknown family {family!r}")
    if level not in LEVELS:
        raise KeyError(f"unknown level {level!r}")
    rng = random.Random(f"{ARENA_VERSION}|{family}|{level}|{seed}")
    wid = f"{FAMILY_CODES[family]}_{level}_{seed}"
    return FAMILIES[family](rng, level, wid, seed)  # type: ignore[operator]
