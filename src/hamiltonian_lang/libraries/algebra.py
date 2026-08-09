"""Algebra V0 — the identity Gold-10 needs, plus exactly what normalisation required.

Scope discipline
----------------
Five identities. Not four, not fifty. ``add_zero`` is what G07's body needs; the other four
are what the calculus replay actually produced and could not otherwise close (see
:mod:`hamiltonian_lang.libraries.calculus` and the report in
``docs/agent_handoffs/CLAUDE_GOLD10_LIBRARY_CLOSEOUT.md``). Every one is generic, typed and
independently useful; none mentions a Gold-10 variable, a Gold-10 type, or a Gold-10 shape.

What was deliberately **not** built: an e-graph, equality saturation, a ring normaliser, a
`simp` tactic, or any use of `sympy.simplify` as an oracle. Gold-10 needs one algebraic
identity and a four-step normalisation; a search subsystem would add proof-extraction and
termination questions that nothing here requires. Recorded as a deferred backend option.

Typing
------
The variable of each identity ranges over the numeric scalars for which the identity is
legitimately defined by *current* HML type semantics: ``Natural``, ``Integer``,
``Rational``, ``Real`` and the refinement scalars that are subtypes of ``Real``. It is not
generalised to arbitrary user structures — HML has no algebraic-structure contract
(monoid, ring) to hang that on, and inventing one to look general would be worse than
being narrow.

``Probability`` is deliberately **absent** from the admissible domains: it is bounded above
by 1, so ``p + 0 = p`` is fine but the type is not closed under the arithmetic these
identities sit inside, and admitting it would invite ``p + q`` to look well-typed.

Honesty about status
--------------------
These are ``LIBRARY_AXIOM``. HML has no induction principle and no ring-structure
machinery, so ``x + 0 = x`` is **asserted** here, not derived. Each carries its
justification, and ``libraries.axioms()`` prints the complete list of what is assumed.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..ast.nodes import BinOp, Comparison, Expr, Literal, UnaryOp
from .theorem import (
    LibraryTheorem,
    TheoremVariable,
    VerificationKind,
    _register,
)

__all__ = ["NUMERIC_DOMAINS", "REWRITES", "rewrite_step"]

#: Scalars for which these identities hold under current HML semantics. `Probability` is
#: excluded on purpose -- see the module docstring.
NUMERIC_DOMAINS: tuple[str, ...] = (
    "Natural",
    "PositiveNatural",
    "Integer",
    "Rational",
    "Real",
    "NonNegativeReal",
    "PositiveReal",
)


def _zero(like: Expr) -> Literal:
    return Literal(value=0.0, raw="0.0", span=like.span)


def _one(like: Expr) -> Literal:
    return Literal(value=1.0, raw="1.0", span=like.span)


def _is_literal(e: Expr, value: float) -> bool:
    return isinstance(e, Literal) and not isinstance(e.value, bool) and e.value == value


def _eq(left: Expr, right: Expr) -> Comparison:
    return Comparison(op="=", left=left, right=right, span=left.span)


def _var(name: str) -> TheoremVariable:
    return TheoremVariable(name=name, domains=NUMERIC_DOMAINS)


def _axiom(
    ident: str,
    statement: str,
    conclusion,
    justification: str,
    variables: tuple[TheoremVariable, ...] = (),
) -> LibraryTheorem:
    return _register(
        LibraryTheorem(
            id=ident,
            version=1,
            library="algebra",
            variables=variables or (_var("x"),),
            conclusion=conclusion,
            statement=statement,
            verification_kind=VerificationKind.LIBRARY_AXIOM,
            justification=justification,
            provenance="elementary arithmetic; standard ring/Peano axioms",
        )
    )


# ---------------------------------------------------------------------------
# The identities
# ---------------------------------------------------------------------------

ADD_ZERO = _axiom(
    "add_zero",
    "forall x : T . x + 0 = x",
    lambda s: _eq(BinOp(op="+", left=s["x"], right=_zero(s["x"]), span=s["x"].span), s["x"]),
    justification=(
        "0 is the additive identity. For Natural this is a Peano axiom; for the ordered "
        "fields it is a field axiom. HML has no induction principle and no ring-structure "
        "contract, so it is asserted here rather than derived, and it is asserted only "
        "over the scalars whose arithmetic HML already models."
    ),
)

ZERO_MUL = _axiom(
    "zero_mul",
    "forall x : T . 0 * x = 0",
    lambda s: _eq(
        BinOp(op="*", left=_zero(s["x"]), right=s["x"], span=s["x"].span),
        _zero(s["x"]),
    ),
    justification=(
        "0 annihilates under multiplication. A ring axiom consequence; asserted for the "
        "same reason as add_zero."
    ),
)

ONE_MUL = _axiom(
    "one_mul",
    "forall x : T . 1 * x = x",
    lambda s: _eq(BinOp(op="*", left=_one(s["x"]), right=s["x"], span=s["x"].span), s["x"]),
    justification="1 is the multiplicative identity. A ring/field axiom.",
)

MUL_ONE = _axiom(
    "mul_one",
    "forall x : T . x * 1 = x",
    lambda s: _eq(BinOp(op="*", left=s["x"], right=_one(s["x"]), span=s["x"].span), s["x"]),
    justification=(
        "1 is the multiplicative identity on the right. Stated separately from one_mul "
        "because HML does not assume commutativity for every admissible type, and a "
        "theorem that quietly relied on it would be unsound the moment a matrix type "
        "entered the domain list."
    ),
)

ZERO_SUB = _axiom(
    "zero_sub",
    "forall x : T . 0 - x = -x",
    lambda s: _eq(
        BinOp(op="-", left=_zero(s["x"]), right=s["x"], span=s["x"].span),
        UnaryOp(op="-", operand=s["x"], span=s["x"].span),
    ),
    justification=(
        "Subtraction from zero is negation, by the definition of the additive inverse. "
        "Note that instantiating at Natural produces a negation that is not a Natural; "
        "that is caught by the ordinary type checker on the resulting term, not papered "
        "over here."
    ),
)


# ---------------------------------------------------------------------------
# Oriented rewriting, for the calculus replay
# ---------------------------------------------------------------------------
#
# `calculus` produces terms like `(0 * x - 1 * 1) / x ^ 2` and must reach `-1 / x ^ 2` to
# match what an author would write. Doing that with a search procedure would be the wrong
# trade at this size, so instead each identity above is given ONE orientation -- always
# left-to-right, always strictly reducing the term -- and applied deterministically to a
# fixed point.
#
# Termination is structural, not hopeful: every rewrite below replaces a term with one of
# strictly smaller node count, so no sequence of them can cycle. `zero_sub` is the only
# one that does not shrink the count (`0 - x` and `-x` are both two nodes plus x), so it
# is applied only when the operand is already irreducible, and it cannot re-enable any
# other rule because no left-hand side above matches a `UnaryOp`.
#
# Each step records WHICH theorem justified it, so a normalisation is auditable rather
# than a black box: `normalise` returns the identity ids it used.

#: (predicate, rewrite, theorem id). Order matters only for reporting; the rules do not
#: overlap on any term.
REWRITES = (
    (
        lambda e: isinstance(e, BinOp) and e.op == "+" and _is_literal(e.right, 0.0),
        lambda e: e.left,
        "add_zero",
    ),
    (
        lambda e: isinstance(e, BinOp) and e.op == "*" and _is_literal(e.left, 0.0),
        lambda e: _zero(e),
        "zero_mul",
    ),
    (
        lambda e: isinstance(e, BinOp) and e.op == "*" and _is_literal(e.right, 0.0),
        lambda e: _zero(e),
        "zero_mul",
    ),
    (
        lambda e: isinstance(e, BinOp) and e.op == "*" and _is_literal(e.left, 1.0),
        lambda e: e.right,
        "one_mul",
    ),
    (
        lambda e: isinstance(e, BinOp) and e.op == "*" and _is_literal(e.right, 1.0),
        lambda e: e.left,
        "mul_one",
    ),
    (
        lambda e: isinstance(e, BinOp) and e.op == "-" and _is_literal(e.left, 0.0),
        lambda e: UnaryOp(op="-", operand=e.right, span=e.span),
        "zero_sub",
    ),
)


def rewrite_step(e: Expr) -> tuple[Expr, str | None]:
    """One outermost rewrite, or the term unchanged.

    Returns the rewritten term and the id of the theorem that justified it, so the caller
    can record exactly which identities a normalisation depended on.
    """
    for matches, apply, theorem_id in REWRITES:
        if matches(e):
            return apply(e), theorem_id
    return e, None


def substitution_for(theorem_id: str, term: Expr) -> Mapping[str, Expr] | None:
    """The substitution under which ``theorem_id`` licenses rewriting ``term``.

    Used by the calculus checker to record a normalisation as a sequence of *instantiated
    theorems* rather than as an opaque simplification. Returns None when the theorem does
    not apply to the term, which is a refusal and not an error.
    """
    if not isinstance(term, BinOp):
        return None
    table = {
        "add_zero": (term.op == "+" and _is_literal(term.right, 0.0), term.left),
        "zero_mul": (
            term.op == "*" and (_is_literal(term.left, 0.0) or _is_literal(term.right, 0.0)),
            term.right if _is_literal(term.left, 0.0) else term.left,
        ),
        "one_mul": (term.op == "*" and _is_literal(term.left, 1.0), term.right),
        "mul_one": (term.op == "*" and _is_literal(term.right, 1.0), term.left),
        "zero_sub": (term.op == "-" and _is_literal(term.left, 0.0), term.right),
    }
    entry = table.get(theorem_id)
    if entry is None or not entry[0]:
        return None
    return {"x": entry[1]}
