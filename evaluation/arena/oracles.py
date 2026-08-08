"""Deterministic oracles over the neutral IR. No LLM judges anything, anywhere.

Each oracle reads only the *structure* -- the declarations and the fact set -- and never
the bookkeeping the generator accumulated while building the world. That is deliberate
and is the arena's version of the difficulty lab's independent cross-check: the
generator computes an answer as it goes, the oracle recomputes it from the finished fact
set, and `worlds.generate` asserts the two agree. A generator bug that fabricated a fact
inconsistent with its own running value therefore fails at construction time rather than
becoming a silently wrong key in a scored run.

The oracles are also what make the endpoints scoreable at all: every answer here is a
single line drawn from a small closed set, so no answer is graded by similarity.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import product

from .ir import (
    Atom,
    BinOp,
    BVar,
    Cmp,
    Conn,
    Elem,
    Not,
    Num,
    Prop,
    Quant,
    Rel,
    Term,
    Var,
    canonical,
)

__all__ = [
    "UNDETERMINED",
    "eval_term",
    "eval_prop",
    "solve_values",
    "entailment",
    "relation_table",
    "substitute_bvar",
    "OracleError",
]

UNDETERMINED = "UNDETERMINED"


class OracleError(RuntimeError):
    """Raised when a world is malformed. Never caught -- a broken world must not score."""


# ---------------------------------------------------------------------------
# Terms
# ---------------------------------------------------------------------------


def eval_term(t: Term, env: dict[str, Fraction]) -> Fraction:
    match t:
        case Num(value):
            return value
        case Var(name):
            if name not in env:
                raise OracleError(f"unbound variable {name!r}")
            return env[name]
        case BinOp(op, left, right):
            a, b = eval_term(left, env), eval_term(right, env)
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            return a * b
        case _:  # pragma: no cover
            raise OracleError(f"not a term: {t!r}")


def solve_values(facts: list[Prop]) -> dict[str, Fraction]:
    """Resolve a DAG of ``x = <term>`` definitions by repeated relaxation.

    Order-independent by construction: the facts are presented shuffled, and this walks
    the list until nothing new resolves. A definition whose dependencies never resolve
    is left out rather than guessed at, and asking for its value raises.
    """
    pending = []
    for f in facts:
        if not (isinstance(f, Cmp) and f.op == "=" and isinstance(f.left, Var)):
            raise OracleError(f"not a definition: {canonical(f)}")
        pending.append((f.left.name, f.right))

    env: dict[str, Fraction] = {}
    progress = True
    while progress:
        progress = False
        for name, rhs in list(pending):
            if name in env:
                continue
            try:
                env[name] = eval_term(rhs, env)
            except OracleError:
                continue
            progress = True
    return env


# ---------------------------------------------------------------------------
# Propositions
# ---------------------------------------------------------------------------


def substitute_bvar(p: Prop, var: str, value: int) -> Prop:
    """Replace a bound variable with a concrete domain element."""
    match p:
        case Rel(name, args):
            return Rel(
                name,
                tuple(Elem(value) if isinstance(a, BVar) and a.name == var else a for a in args),
            )
        case Not(inner):
            return Not(substitute_bvar(inner, var, value))
        case Conn(op, left, right):
            return Conn(op, substitute_bvar(left, var, value), substitute_bvar(right, var, value))
        case Quant(kind, v, dom, body):
            # Shadowing: an inner binder of the same name captures, so stop here.
            if v == var:
                return p
            return Quant(kind, v, dom, substitute_bvar(body, var, value))
        case _:
            return p


def eval_prop(
    p: Prop,
    assign: dict[str, bool] | None = None,
    table: dict[tuple[int, ...], bool] | None = None,
    domain: tuple[int, ...] = (),
    env: dict[str, Fraction] | None = None,
) -> bool:
    """Evaluate a proposition to a definite truth value.

    Total on well-formed worlds: an atom with no assignment, a relation tuple absent
    from the table, or a comparison over an unresolved variable is an error rather than
    a default. Defaulting here would turn a malformed world into a plausible-looking
    scored answer.
    """
    assign = assign or {}
    table = table or {}
    env = env or {}
    match p:
        case Atom(name):
            if name not in assign:
                raise OracleError(f"unassigned atom {name!r}")
            return assign[name]
        case Rel(_, args):
            key = []
            for a in args:
                if not isinstance(a, Elem):
                    raise OracleError(f"free variable in evaluated relation: {canonical(p)}")
                key.append(a.value)
            k = tuple(key)
            if k not in table:
                raise OracleError(f"relation tuple {k} not in table")
            return table[k]
        case Not(inner):
            return not eval_prop(inner, assign, table, domain, env)
        case Conn(op, left, right):
            a = eval_prop(left, assign, table, domain, env)
            b = eval_prop(right, assign, table, domain, env)
            if op == "and":
                return a and b
            if op == "or":
                return a or b
            if op == "implies":
                return (not a) or b
            return a == b
        case Cmp(op, left, right):
            a, b = eval_term(left, env), eval_term(right, env)
            return {
                "=": a == b, "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b,
            }[op]
        case Quant(kind, var, _, body):
            if not domain:
                raise OracleError("quantifier evaluated with an empty domain")
            results = (
                eval_prop(substitute_bvar(body, var, e), assign, table, domain, env)
                for e in domain
            )
            return all(results) if kind == "forall" else any(results)
        case _:  # pragma: no cover
            raise OracleError(f"not a proposition: {p!r}")


def relation_table(facts: list[Prop]) -> tuple[dict[tuple[int, ...], bool], str]:
    """Read an explicit, fully enumerated relation out of the fact list.

    The world carries one fact per tuple -- positive or negated -- because closed-world
    phrasing ("and for no others") is expanded before rendering. If a tuple appeared
    twice with conflicting signs the world would be contradictory, so that raises.
    """
    table: dict[tuple[int, ...], bool] = {}
    name = ""
    for f in facts:
        sign, inner = (False, f.inner) if isinstance(f, Not) else (True, f)
        if not isinstance(inner, Rel):
            raise OracleError(f"not a relation fact: {canonical(f)}")
        name = name or inner.name
        key = tuple(a.value for a in inner.args if isinstance(a, Elem))
        if len(key) != len(inner.args):
            raise OracleError(f"free variable in a stated fact: {canonical(f)}")
        if key in table and table[key] != sign:
            raise OracleError(f"contradictory facts for {name}{key}")
        table[key] = sign
    return table, name


def entailment(atoms: list[str], facts: list[Prop], target: str) -> str:
    """TRUE / FALSE / UNDETERMINED, by exhaustive enumeration over all assignments.

    The three-way answer is the point of this family. A solver that assumes every query
    is decided will confidently answer TRUE or FALSE where the constraints leave it
    open, and that is a reasoning error rather than an arithmetic one.
    """
    models = []
    for combo in product([False, True], repeat=len(atoms)):
        assign = dict(zip(atoms, combo, strict=True))
        if all(eval_prop(f, assign=assign) for f in facts):
            models.append(assign)
    if not models:
        raise OracleError("unsatisfiable world -- entailment is vacuous")
    vals = {m[target] for m in models}
    if vals == {True}:
        return "TRUE"
    if vals == {False}:
        return "FALSE"
    return UNDETERMINED
