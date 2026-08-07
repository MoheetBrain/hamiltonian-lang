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

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from ..ast.nodes import Comparison, Expr, Literal, LogicalOp, Ref, SymbolId
from ..types import ScalarType, Type

__all__ = [
    "Fact",
    "Frame",
    "Consistency",
    "RefinementEnv",
    "facts_from_proposition",
]


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


class Consistency(StrEnum):
    """Whether a frame's own assumptions can all hold at once.

    ``INCONSISTENT_LOCAL`` is deliberately *not* an error. Assuming something false and
    deriving a contradiction from it is how proof by contradiction works, and a language
    that globally banned contradictory contexts could not express it. What must be
    contained is *explosion*: an inconsistent frame may not export conclusions to its
    parent, because from a contradiction anything follows.
    """

    CONSISTENT = "CONSISTENT"
    INCONSISTENT_LOCAL = "INCONSISTENT_LOCAL"


#: Relation pairs that are jointly unsatisfiable for the same symbol and the same bound.
#: Deliberately tiny and syntactic -- this detects the obvious contradiction an author
#: writes on purpose, not every contradiction that exists.
_CONTRADICTORY: frozenset[tuple[str, str]] = frozenset(
    {("<", ">"), (">", "<"), ("=", "!="), ("!=", "="), ("<", "="), ("=", "<"),
     (">", "="), ("=", ">")}
)


@dataclass
class Frame:
    """One lexical context. Facts live in exactly one frame and never leak outward."""

    kind: str  # module | quantifier | concept | scope | derivation
    depth: int
    facts: list[Fact] = field(default_factory=list)
    consistency: Consistency = Consistency.CONSISTENT
    #: Which environment/version this frame's facts came from, for imported contexts.
    environment: str | None = None


class RefinementEnv:
    """A lexical stack of frames, plus the conservative decisions they license.

    The stack is the point. A flat set cannot express "assume `x > 0` *for the purposes
    of this argument*", which is what a case split, a bounded lemma and a proof by
    contradiction all need -- and it was the reason maturity criterion 3.3 failed.
    """

    def __init__(self) -> None:
        self._frames: list[Frame] = [Frame(kind="module", depth=0)]

    # -- scope ------------------------------------------------------------
    @property
    def depth(self) -> int:
        return self._frames[-1].depth

    def current(self) -> Frame:
        return self._frames[-1]

    def push(self, kind: str = "scope", *, environment: str | None = None) -> Frame:
        frame = Frame(kind=kind, depth=len(self._frames), environment=environment)
        self._frames.append(frame)
        return frame

    def pop(self) -> Frame:
        """Discard the innermost frame and every fact introduced in it.

        Returns the popped frame so a caller can inspect its consistency -- which is what
        an assumption-discharge rule needs in order to conclude ``not P`` from a
        contradiction derived under ``P``.
        """
        if len(self._frames) == 1:
            raise RuntimeError("cannot pop the module frame")
        return self._frames.pop()

    def frames(self) -> Sequence[Frame]:
        return tuple(self._frames)

    def assume(self, prop: Expr, *, source_label: str | None = None) -> None:
        """Add every atomic fact ``prop`` asserts to the CURRENT frame."""
        frame = self._frames[-1]
        new = facts_from_proposition(
            prop, source_label=source_label, depth=frame.depth
        )
        frame.facts.extend(new)
        if frame.consistency is Consistency.CONSISTENT and self._contradicts(frame):
            frame.consistency = Consistency.INCONSISTENT_LOCAL

    def _contradicts(self, frame: Frame) -> bool:
        """Whether this frame's own facts are jointly unsatisfiable.

        Syntactic and deliberately incomplete: it catches ``x > 0`` with ``x < 0``, and
        ``x = 0`` with ``x != 0``. It does not attempt arithmetic. An undetected
        contradiction is not a soundness hole here -- it simply means the frame is not
        flagged, and the facts still cannot leave the frame.
        """
        by_symbol: dict[SymbolId, list[Fact]] = {}
        for f in frame.facts:
            by_symbol.setdefault(f.symbol, []).append(f)
        for facts in by_symbol.values():
            for i, a in enumerate(facts):
                for b in facts[i + 1 :]:
                    if a.bound_literal is None or b.bound_literal is None:
                        continue
                    if a.bound_literal != b.bound_literal:
                        continue
                    if (a.relation, b.relation) in _CONTRADICTORY:
                        return True
        return False

    def facts_about(self, sid: SymbolId) -> list[Fact]:
        """Every fact about ``sid`` visible from the current frame.

        Searches innermost outward. A sibling frame's facts are unreachable because it is
        not on the stack -- which is the whole reason scoping is a stack and not a set.
        """
        out: list[Fact] = []
        for frame in self._frames:
            out.extend(f for f in frame.facts if f.symbol == sid)
        return out

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

    def refine(self, sid: SymbolId, declared: Type) -> Type:
        """The narrowed type of ``sid`` given the facts in scope, or ``declared``.

        Total in both directions: it is given a type and always returns one, so a caller
        never has to decide what an absent narrowing means. The only sound answer when
        nothing is known is the declared type itself, which is what it returns.

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
