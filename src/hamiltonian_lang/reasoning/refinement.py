"""The refinement environment Γ: what the assumptions in scope actually buy you.

The audit's second critical finding was that HML's epistemic layer and its type layer
were disconnected -- ``assume x > 0.0`` did not make ``log(x)`` legal, so the one
construct that reads like reasoning was decorative. This module connects them.

    Γ = { x : Real, x > 0 }   ⊢   x : PositiveReal   ⊢   log(x) defined

What this is not
----------------
It is not a theorem prover, and the refusal to become one is the design. Every fact
here is a *syntactic* fact about a bound symbol, drawn directly from an assumption the
author wrote. There is no arithmetic reasoning, no transitive closure over unknowns, no
case analysis. When Γ cannot establish an obligation, the answer is UNKNOWN and the
obligation stays OPEN -- never DISCHARGED. Guessing in the permissive direction is the
one failure mode that would make the whole reasoning layer worthless, because it would
let a false step reach VERIFIED.

The three cases the directive names, and why they come out as they do:

* ``assume x > 0``  discharges ``x > 0``  -- the fact is literally present.
* ``assume x >= 0`` does NOT discharge ``x > 0`` -- ``>=`` does not entail ``>``;
  :data:`_ENTAILS` has no edge in that direction and none may be added.
* ``x != 0`` is NOT inferred from ``x >= 0`` -- 0 satisfies ``x >= 0``. It *is*
  inferred from ``x > 0``, which is sound.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ast.nodes import Comparison, Expr, Literal, LogicalOp, Ref, SymbolId
from ..types import ScalarType, Type

__all__ = ["Fact", "RefinementEnv", "facts_from_proposition"]


#: Which relation entails which, for the SAME symbol and the SAME bound.
#:
#: Read ``(a, b) in _ENTAILS`` as "a fact written with relation `a` establishes an
#: obligation written with relation `b`". This table is the entire entailment theory
#: and is deliberately tiny; every edge is one that holds for all reals.
#:
#: The absent edges matter more than the present ones:
#:   (">=", ">")  absent -- x >= 0 does not give x > 0
#:   (">=", "!=") absent -- x >= 0 does not give x != 0
#:   ("!=", ">")  absent -- x != 0 does not give x > 0
_ENTAILS: frozenset[tuple[str, str]] = frozenset(
    {
        (">", ">"),
        (">", ">="),   # x > c  entails  x >= c
        (">", "!="),   # x > c  entails  x != c
        (">=", ">="),
        ("<", "<"),
        ("<", "<="),
        ("<", "!="),
        ("<=", "<="),
        ("=", "="),
        ("=", ">="),   # x = c  entails  x >= c
        ("=", "<="),
        ("!=", "!="),
    }
)

#: Relations that, when asserted against literal 0, refine a symbol's scalar type.
_ZERO_REFINEMENTS: dict[str, str] = {
    ">": "PositiveReal",
    ">=": "NonNegativeReal",
}


@dataclass(frozen=True)
class Fact:
    """One atomic, syntactic fact about a bound symbol: ``symbol REL bound``.

    ``bound`` is kept as a literal value when it is one, because the only comparisons
    this environment can decide are those against a known constant. A fact whose bound
    is another symbol is recorded but decides nothing beyond a syntactically identical
    obligation.
    """

    symbol: SymbolId
    relation: str
    bound_literal: float | int | None
    #: Canonical identity of the bound expression, for symbol-vs-symbol facts.
    bound_identity: str
    #: The claim label that introduced this fact, for provenance on discharge.
    source_label: str | None = None
    #: Scope depth at which the fact was introduced; facts do not leak outward.
    depth: int = 0


def _literal_of(e: Expr) -> float | int | None:
    if isinstance(e, Literal) and not isinstance(e.value, bool):
        return e.value
    return None


def _flip(op: str) -> str:
    return {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "=": "=", "!=": "!="}[op]


def facts_from_proposition(
    prop: Expr, *, source_label: str | None = None, depth: int = 0
) -> list[Fact]:
    """Extract every atomic fact a proposition asserts.

    Conjunctions contribute both sides -- ``assume x > 0 and y < 1`` gives two facts.
    Disjunctions contribute **nothing**: ``x > 0 or y > 0`` asserts neither disjunct,
    and treating it as if it did is exactly the unsound shortcut this module exists to
    refuse. Negations likewise contribute nothing except the one case ``not (a = b)``,
    which is precisely ``a != b``.
    """
    from ..backends.canonical import expr_identity

    out: list[Fact] = []

    def rec(e: Expr) -> None:
        if isinstance(e, LogicalOp) and e.op == "and":
            rec(e.left)
            rec(e.right)
            return
        if isinstance(e, Comparison):
            left, right, op = e.left, e.right, e.op
            # Normalise to `symbol REL bound`.
            if not isinstance(left, Ref):
                if isinstance(right, Ref):
                    left, right, op = right, left, _flip(op)
                else:
                    return
            if not isinstance(left, Ref) or left.symbol_id is None:
                return
            out.append(
                Fact(
                    symbol=left.symbol_id,
                    relation=op,
                    bound_literal=_literal_of(right),
                    bound_identity=expr_identity(right),
                    source_label=source_label,
                    depth=depth,
                )
            )
            return
        # `or`, `implies`, `iff`, `not`, quantifiers: no atomic fact is asserted.
        return

    rec(prop)
    return out


class RefinementEnv:
    """A scoped set of facts, plus the conservative decisions they license."""

    def __init__(self) -> None:
        self._facts: list[Fact] = []
        self._depth = 0

    # -- scope ------------------------------------------------------------
    def push(self) -> None:
        self._depth += 1

    def pop(self) -> None:
        """Discard every fact introduced at the current depth.

        Scoped assumptions must not leak: a fact asserted inside a quantifier body or a
        concept is not available to the module around it. `tests/reasoning/` asserts
        that an obligation outside the scope of its discharging assumption stays OPEN.
        """
        self._facts = [f for f in self._facts if f.depth < self._depth]
        self._depth -= 1

    def assume(self, prop: Expr, *, source_label: str | None = None) -> None:
        self._facts.extend(
            facts_from_proposition(prop, source_label=source_label, depth=self._depth)
        )

    def facts_about(self, sid: SymbolId) -> list[Fact]:
        return [f for f in self._facts if f.symbol == sid]

    # -- decisions --------------------------------------------------------
    def entails(self, obligation: Expr) -> Fact | None:
        """Return the fact that establishes ``obligation``, or None.

        None means UNKNOWN, not False. The caller must leave the obligation OPEN.
        """
        from ..backends.canonical import expr_identity

        if not isinstance(obligation, Comparison):
            return None
        left, right, op = obligation.left, obligation.right, obligation.op
        if not isinstance(left, Ref):
            if isinstance(right, Ref):
                left, right, op = right, left, _flip(op)
            else:
                return None
        if not isinstance(left, Ref) or left.symbol_id is None:
            return None

        want_literal = _literal_of(right)
        want_identity = expr_identity(right)

        for f in self.facts_about(left.symbol_id):
            if (f.relation, op) not in _ENTAILS:
                continue
            # Same bound. Two ways to be the same: canonically identical expressions
            # (covers symbol-vs-symbol bounds), or numerically equal literals.
            #
            # The numeric case is not pedantry. A rule generates its obligation
            # programmatically -- `divide_both_sides` builds `k != 0` with an integer
            # zero -- while the author writes `assume k != 0.0` with a float. Those are
            # the same mathematical fact and different JSON, so comparing only the
            # canonical form left every division obligation OPEN no matter what the
            # author assumed. Caught by the first end-to-end run; regression-tested in
            # tests/reasoning/test_discharge.py::test_integer_and_float_zero_agree.
            if f.bound_identity == want_identity:
                return f
            if (
                want_literal is not None
                and f.bound_literal is not None
                and f.bound_literal == want_literal
                and f.relation == op
            ):
                return f
            # Numeric bounds admit one extra sound step: a fact with a *stronger*
            # bound establishes a weaker one in the same direction.
            #   x > 5  establishes  x > 0   and   x != 0
            #   x < -1 establishes  x < 0
            if want_literal is None or f.bound_literal is None:
                continue
            if op in (">", ">=") and f.relation in (">", ">=", "="):
                if f.bound_literal >= want_literal:
                    if op == ">" and f.relation == ">=" and f.bound_literal == want_literal:
                        continue  # x >= 0 does NOT give x > 0
                    return f
            elif op in ("<", "<=") and f.relation in ("<", "<=", "="):
                if f.bound_literal <= want_literal:
                    if op == "<" and f.relation == "<=" and f.bound_literal == want_literal:
                        continue
                    return f
            elif op == "!=":
                # x != c holds if a fact pins the symbol strictly to one side of c.
                if f.relation == ">" and f.bound_literal >= want_literal:
                    return f
                if f.relation == "<" and f.bound_literal <= want_literal:
                    return f
                if f.relation == ">=" and f.bound_literal > want_literal:
                    return f
                if f.relation == "<=" and f.bound_literal < want_literal:
                    return f
        return None

    def refine(self, sid: SymbolId, declared: Type | None) -> Type | None:
        """The narrowed type of ``sid`` given the facts in scope, or ``declared``.

        This is what makes ``assume x > 0.0`` license ``log(x)``. Only the scalar
        refinements are narrowed, and only against a literal zero -- the two cases the
        type lattice actually distinguishes. Anything else is left exactly as declared.
        """
        if not isinstance(declared, ScalarType):
            return declared
        if declared.name not in ("Real", "Rational", "Integer"):
            return declared

        best: str | None = None
        for f in self.facts_about(sid):
            if f.bound_literal is None:
                continue
            refined: str | None = None
            if f.bound_literal == 0:
                refined = _ZERO_REFINEMENTS.get(f.relation)
            elif f.bound_literal > 0 and f.relation in (">", ">=", "="):
                # x > 5 implies x > 0, so PositiveReal is sound.
                refined = "PositiveReal"
            elif f.bound_literal == 0 and f.relation == "=":
                refined = "NonNegativeReal"
            if refined is None:
                continue
            # PositiveReal is strictly stronger than NonNegativeReal; keep the best.
            if best is None or (best == "NonNegativeReal" and refined == "PositiveReal"):
                best = refined
        if best is None:
            return declared
        return ScalarType(best)
