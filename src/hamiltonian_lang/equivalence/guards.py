"""Invariant guards -- the properties an equivalence claim may never trade away.

Every transformation this engine accepts must preserve binder scope, assumptions,
domains, dimensions, epistemic status, direction of implication and quantifier
order. The guards run *before* the tiers and can only ever refute; none of them
can certify anything. A guard that does not fire contributes nothing.

Each guard is a sound argument, not a heuristic:

* **Declared types incomparable.** The type system is the contract. When two
  matched declarations carry types with no subtyping path in either direction --
  ``Probability`` against ``PValue``, ``RandomVariable[T]`` against ``T``,
  ``Quantity[Mass]`` against ``Quantity[Length]`` -- they denote different things
  by construction (``types.py``, D-004..D-007 and D-022).
* **Epistemic role.** ``obs`` is data, ``param`` is unknown, ``rv`` is a random
  variable; ``assume`` is granted, ``require`` is an obligation, ``prove`` is a
  claim. Swapping any of these changes what is being asserted.
* **Objective direction.** Minimising and maximising a non-constant objective are
  different problems.
* **Conditioning set.** A conditional law and a marginal law are different objects.
* **Quantifier alternation.** ``exists y . forall x . P`` entails
  ``forall x . exists y . P`` and not the converse, so the two are different
  claims. This guard only fires when a *witness* shows the body genuinely depends
  on both binders, which rules out the vacuous case where a binder does not matter.

A guard refuses to fire on a pairing it does not trust. If two statements were
matched only because nothing better was available, refuting on that basis would
invent a false negative -- and a false negative biases H1/H2 downward, which is
the very defect this package exists to remove.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence

from ..ast.nodes import (
    AssumeStmt,
    Expr,
    ProveStmt,
    Quantifier,
    RequireStmt,
    SymbolId,
)
from ..types import (
    UNIT_INTERVAL_KINDS,
    DistributionType,
    QuantityType,
    RandomVariableType,
    ScalarType,
    Type,
    dimension_of,
    is_subtype,
)
from .display import show
from .matching import Alignment, Env, Residual, match_node
from .search import varies_with
from .status import (
    EquivalenceResult,
    EquivalenceStatus,
    NonEquivalenceProof,
    Tier,
)
from .sympy_bridge import SYMPY_AVAILABLE, TranslationContext

__all__ = ["run_guards", "quantifier_prefix"]

#: Declaration kinds whose difference is a difference in epistemic status.
_EPISTEMIC_KIND_PAIRS: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"obs", "param"}),
        frozenset({"obs", "var"}),
    }
)


def _refute(method: str, detail: str, left: str, right: str) -> EquivalenceResult:
    return EquivalenceResult(
        Tier.GUARD,
        EquivalenceStatus.VERIFIED_NONEQUIVALENT,
        detail,
        proof=NonEquivalenceProof(method, detail, left=left, right=right),
    )


def _type_guard(left: Type | None, right: Type | None, where: str) -> EquivalenceResult | None:
    if left is None or right is None:
        return None
    if is_subtype(left, right) or is_subtype(right, left):
        return None

    lname = left.render()
    rname = right.render()

    if (
        isinstance(left, ScalarType)
        and isinstance(right, ScalarType)
        and left.name in UNIT_INTERVAL_KINDS
        and right.name in UNIT_INTERVAL_KINDS
    ):
        return _refute(
            "guard.epistemic_kind_differs",
            f"{where}: {lname} and {rname} are the same subset of [0, 1] and different "
            f"epistemic objects. P(data at least this extreme | H0) is not P(H0 | data); "
            f"the type system admits no coercion between them in either direction",
            lname,
            rname,
        )

    if isinstance(left, (RandomVariableType, DistributionType)) != isinstance(
        right, (RandomVariableType, DistributionType)
    ):
        return _refute(
            "guard.random_variable_vs_value",
            f"{where}: {lname} and {rname} differ in whether the object is a law or a "
            f"value of the support. A Distribution[T] is not a T and a "
            f"RandomVariable[T] is neither",
            lname,
            rname,
        )

    dl, dr = dimension_of(left), dimension_of(right)
    if (
        isinstance(left, QuantityType)
        and isinstance(right, QuantityType)
        and dl is not None
        and dr is not None
        and dl.is_concrete()
        and dr.is_concrete()
        and dl != dr
    ):
        return _refute(
            "guard.dimension_differs",
            f"{where}: the dimensions {dl.render()} and {dr.render()} are different "
            f"exponent vectors, so the two quantities are not the same magnitude",
            lname,
            rname,
        )

    return _refute(
        "guard.declared_types_incomparable",
        f"{where}: {lname} and {rname} have no subtyping path in either direction, so "
        f"they do not denote the same set of values",
        lname,
        rname,
    )


def quantifier_prefix(
    e: Expr | None,
) -> tuple[list[tuple[str, SymbolId | None, Type | None]], Expr | None]:
    """Split a quantified expression into its binder prefix and its body."""
    prefix: list[tuple[str, SymbolId | None, Type | None]] = []
    node = e
    while isinstance(node, Quantifier):
        prefix.append((node.kind, node.symbol_id, node.var_type))
        node = node.body
    return prefix, node


def _binder_bijection(
    left_prefix: Sequence[tuple[str, SymbolId | None, Type | None]],
    right_prefix: Sequence[tuple[str, SymbolId | None, Type | None]],
    left_body: Expr | None,
    right_body: Expr | None,
    env: Env,
) -> tuple[int, ...] | None:
    """A type-preserving binder correspondence that makes the bodies identical."""
    n = len(left_prefix)
    if n == 0 or n > 5 or len(right_prefix) != n:
        return None
    for perm in itertools.permutations(range(n)):
        ok = True
        e1: Env | None = env
        for i, j in enumerate(perm):
            _, ls, lt = left_prefix[i]
            _, rs, rt = right_prefix[j]
            if (lt.render() if lt else None) != (rt.render() if rt else None):
                ok = False
                break
            if ls is None or rs is None or e1 is None:
                ok = False
                break
            e1 = e1.bind(ls, rs)
            if e1 is None:
                ok = False
                break
        if not ok or e1 is None:
            continue
        if any(True for _ in itertools.islice(match_node(left_body, right_body, e1), 1)):
            return perm
    return None


def _quantifier_guard(
    residual: Residual, alignment: Alignment, ctx: TranslationContext
) -> EquivalenceResult | None:
    left, right = residual.left, residual.right
    if not isinstance(left, Quantifier) or not isinstance(right, Quantifier):
        return None

    lp, lbody = quantifier_prefix(left)
    rp, rbody = quantifier_prefix(right)
    if len(lp) != len(rp) or lbody is None or rbody is None:
        return None

    perm = _binder_bijection(lp, rp, lbody, rbody, alignment.env)
    if perm is None:
        return None

    # ``perm[i] = j`` means left binder i is right binder j. To compare the two
    # nesting orders, read the *left* binders in the order the right module binds
    # them, which is the inverse permutation.
    inverse = [0] * len(perm)
    for i, j in enumerate(perm):
        inverse[j] = i
    left_kinds = [k for k, _, _ in lp]
    right_kinds = [left_kinds[i] for i in inverse]
    if left_kinds == right_kinds:
        return None

    # The same body under a different binder order. Only a genuine dependence on
    # every binder rules out the vacuous case where the order cannot matter.
    if not SYMPY_AVAILABLE:  # pragma: no cover
        return None
    binder_types: dict[SymbolId, Type | None] = {
        sid: t for _, sid, t in lp if sid is not None
    }
    translation = ctx.translate(lbody, "left", binder_types=binder_types)
    if translation.expr is None:
        return None
    symbols = ctx.symbol_table()
    symbol_types = ctx.symbol_types()
    witnesses: dict[str, dict[str, str]] = {}
    for _, sid, _t in lp:
        if sid is None:
            return None
        name = ctx.name_for(sid, "left")
        symbol = symbols.get(name)
        if symbol is None:
            return None
        witness = varies_with(translation.expr, symbol, symbols, symbol_types)
        if witness is None:
            return None
        witnesses[sid.name] = witness

    detail = (
        f"the binder prefix is {' '.join(left_kinds)} on one side and "
        f"{' '.join(right_kinds)} on the other, over the same body, and the body was "
        f"witnessed to depend on every binder. Swapping a forall past an exists changes "
        f"which claim is being made: exists-then-forall entails forall-then-exists and "
        f"not the converse"
    )
    return EquivalenceResult(
        Tier.GUARD,
        EquivalenceStatus.VERIFIED_NONEQUIVALENT,
        detail,
        proof=NonEquivalenceProof(
            "guard.quantifier_alternation_differs",
            detail,
            left=show(left),
            right=show(right),
        ),
        evidence={"dependence_witnesses": witnesses},
    )


def run_guards(alignment: Alignment, ctx: TranslationContext) -> list[EquivalenceResult]:
    """Every guard that fired, in the order they were checked. Usually empty.

    Residuals from an untrusted (guessed) statement pairing are skipped entirely:
    refuting on a guess would invent a false negative.
    """
    fired: list[EquivalenceResult] = []

    for residual in alignment.residuals:
        if not residual.trustworthy:
            continue
        kind = residual.kind

        if kind == "declared_type":
            left_type = residual.left if isinstance(residual.left, Type) else None
            right_type = residual.right if isinstance(residual.right, Type) else None
            verdict = _type_guard(left_type, right_type, residual.path)
            if verdict is not None:
                fired.append(verdict)

        elif kind == "declaration_kind":
            pair = frozenset({str(residual.left), str(residual.right)})
            if "rv" in pair and len(pair) == 2:
                fired.append(
                    _refute(
                        "guard.random_variable_vs_value",
                        f"{residual.path}: one side declares a random variable and the "
                        f"other a deterministic quantity. A RandomVariable[T] is a "
                        f"measurable function, not a value of T",
                        str(residual.left),
                        str(residual.right),
                    )
                )
            elif pair in _EPISTEMIC_KIND_PAIRS:
                fired.append(
                    _refute(
                        "guard.epistemic_role_differs",
                        f"{residual.path}: `obs` is observed data and `{sorted(pair)[1]}` "
                        f"is not. The epistemic status of a quantity is part of what the "
                        f"model says",
                        str(residual.left),
                        str(residual.right),
                    )
                )

        elif kind == "statement_kind":
            names = {str(residual.left), str(residual.right)}
            if names <= {
                AssumeStmt.__name__,
                RequireStmt.__name__,
                ProveStmt.__name__,
            } and len(names) == 2:
                fired.append(
                    _refute(
                        "guard.epistemic_role_differs",
                        f"{residual.path}: a granted assumption, an imposed constraint "
                        f"and a claim to be proved are three different assertions about "
                        f"the same proposition",
                        str(residual.left),
                        str(residual.right),
                    )
                )

        elif kind == "objective_direction":
            fired.append(
                _refute(
                    "guard.objective_direction_differs",
                    f"{residual.path}: minimising and maximising the same objective are "
                    f"different problems",
                    str(residual.left),
                    str(residual.right),
                )
            )

        elif kind == "conditioning_arity":
            fired.append(
                _refute(
                    "guard.conditioning_set_differs",
                    f"{residual.path}: the laws condition on {residual.left} and "
                    f"{residual.right} variables. A conditional law and a marginal law "
                    f"are different objects",
                    str(residual.left),
                    str(residual.right),
                )
            )

        elif kind == "expression":
            verdict = _quantifier_guard(residual, alignment, ctx)
            if verdict is not None:
                fired.append(verdict)

    return fired
