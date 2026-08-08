"""The neutral semantic IR every arena rendering is produced from.

This module is the whole reason the arena can claim to be a *representation*
experiment rather than a content experiment. A world is built once, as a structure,
and each of the three renderings -- structured English, generic AST, HML -- is a pure
function of that structure. No renderer sees the query's answer, no renderer receives a
fact the others do not, and no renderer is written first with the others translated
from it.

**Why this exists at all.** `evaluation/h2/difficulty_lab/families.py` generates its
English inline and discards the structure it came from: by the time a `Specimen` is
returned, the dependency DAG and the constraint set are gone. That generator therefore
cannot be given "a rendering layer" as the handoff assumed -- there is nothing left to
render. The arena rebuilds the same worlds structure-first. `difficulty-lab-1.0.0` is
left byte-identical, because the synthetic calibration results are recorded against
that version and its file hashes are pinned.

**A finite relation is stated in closed form in every arm.** The first design here
expanded "R holds for exactly these pairs and for no others" into one explicit fact per
ordered pair, so that no arm could benefit from having a shorter idiom for closure. That
turned out to be un-renderable in HML: a declared `Predicate` is not callable
(`HML-T470`), and the only callable form, `def R(x, y) : Proposition := ...`, requires a
body -- **HML has no uninterpreted predicate**. Enumeration is therefore available to
two arms and not the third, and using it would have measured that gap rather than the
representation.

So the table is stated *once* in each arm, in that arm's own idiom: a list of pairs in
English, a table node in the AST, a disjunction of equalities in HML. All three
determine the same relation, and the decoders prove it. HML's form is markedly the
longest, which is a real property of the language and shows up in the token budget
rather than being hidden.

**Canonical form.** `canonical()` emits a fully parenthesised S-expression. It is the
identity used by the parity checker: a rendering is information-matched iff decoding it
reproduces a structure with the same canonical form. Rational literals are normalised
through `Fraction`, so `4/2` and `2` are the same term and cannot smuggle in a
difference that is really about formatting.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

__all__ = [
    "Term", "Num", "Var", "BinOp",
    "Prop", "Atom", "Rel", "Not", "Conn", "Cmp", "Quant",
    "Arg", "Elem", "BVar",
    "canonical", "term_vars", "prop_atoms", "prop_size", "walk",
    "TERM_OPS", "CMP_OPS", "CONN_OPS", "QUANT_KINDS",
]

#: Arithmetic operators. Deliberately small: the difficulty is holding the chain, not
#: the arithmetic, so division never appears and no term can be undefined.
TERM_OPS = ("+", "-", "*")
CMP_OPS = ("=", "<", "<=", ">", ">=")
CONN_OPS = ("and", "or", "implies", "iff")
QUANT_KINDS = ("forall", "exists")


# ---------------------------------------------------------------------------
# Terms
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Num:
    """An exact rational literal. Never a float -- the oracles must stay exact."""

    value: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.value, Fraction):
            raise TypeError("Num.value must be a Fraction, so the oracle stays exact")


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class BinOp:
    op: str
    left: Term
    right: Term

    def __post_init__(self) -> None:
        if self.op not in TERM_OPS:
            raise ValueError(f"unknown term operator {self.op!r}")


Term = Num | Var | BinOp


# ---------------------------------------------------------------------------
# Quantifier arguments
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Elem:
    """A concrete element of a finite domain."""

    value: int


@dataclass(frozen=True)
class BVar:
    """A variable bound by an enclosing quantifier."""

    name: str


Arg = Elem | BVar


# ---------------------------------------------------------------------------
# Propositions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Atom:
    """A propositional variable, e.g. ``P3``."""

    name: str


@dataclass(frozen=True)
class Rel:
    name: str
    args: tuple[Arg, ...]


@dataclass(frozen=True)
class Not:
    inner: Prop


@dataclass(frozen=True)
class Conn:
    op: str
    left: Prop
    right: Prop

    def __post_init__(self) -> None:
        if self.op not in CONN_OPS:
            raise ValueError(f"unknown connective {self.op!r}")


@dataclass(frozen=True)
class Cmp:
    op: str
    left: Term
    right: Term

    def __post_init__(self) -> None:
        if self.op not in CMP_OPS:
            raise ValueError(f"unknown comparison {self.op!r}")


@dataclass(frozen=True)
class Quant:
    """``forall x in D . body`` / ``exists x in D . body``.

    The binder carries its domain explicitly. Quantifier *order* is the single most
    important minimal contrast the arena tests, so nesting is represented by nesting --
    never flattened into a list of binders, which would make the two orders differ only
    by a list permutation and invite a renderer to normalise the distinction away.
    """

    kind: str
    var: str
    domain: str
    body: Prop

    def __post_init__(self) -> None:
        if self.kind not in QUANT_KINDS:
            raise ValueError(f"unknown quantifier {self.kind!r}")


Prop = Atom | Rel | Not | Conn | Cmp | Quant


# ---------------------------------------------------------------------------
# Canonical form
# ---------------------------------------------------------------------------


def _num(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def canonical(node: Term | Prop | Arg) -> str:
    """A fully parenthesised S-expression -- the arena's notion of identity.

    Structural, not semantic: ``(+ a b)`` and ``(+ b a)`` are different canonical forms.
    That is intended. Two renderings are information-matched when they decode to the
    *same structure*, and a decoder that silently reordered a sum would be hiding a real
    difference between the arms.
    """
    match node:
        case Num(value):
            return f"(num {_num(value)})"
        case Var(name):
            return f"(var {name})"
        case BinOp(op, left, right):
            return f"({op} {canonical(left)} {canonical(right)})"
        case Elem(value):
            return f"(elem {value})"
        case BVar(name):
            return f"(bvar {name})"
        case Atom(name):
            return f"(atom {name})"
        case Rel(name, args):
            return f"(rel {name} {' '.join(canonical(a) for a in args)})"
        case Not(inner):
            return f"(not {canonical(inner)})"
        case Conn(op, left, right):
            return f"({op} {canonical(left)} {canonical(right)})"
        case Cmp(op, left, right):
            return f"(cmp {op} {canonical(left)} {canonical(right)})"
        case Quant(kind, var, domain, body):
            return f"({kind} {var} {domain} {canonical(body)})"
        case _:  # pragma: no cover - exhaustive over the IR
            raise TypeError(f"not an IR node: {node!r}")


def walk(node: Term | Prop):
    """Yield every node in the tree, parents before children."""
    yield node
    match node:
        case BinOp(_, left, right) | Conn(_, left, right) | Cmp(_, left, right):
            yield from walk(left)
            yield from walk(right)
        case Not(inner):
            yield from walk(inner)
        case Quant(_, _, _, body):
            yield from walk(body)
        case _:
            return


def term_vars(node: Term) -> set[str]:
    return {n.name for n in walk(node) if isinstance(n, Var)}


def prop_atoms(node: Prop) -> set[str]:
    return {n.name for n in walk(node) if isinstance(n, Atom)}


def prop_size(node: Term | Prop) -> int:
    """Node count. Used to certify that a minimal contrast really is minimal."""
    return sum(1 for _ in walk(node))
