"""Calculus V0 — a replayable differentiation checker, not a table of answers.

The trust model, which is the whole point
------------------------------------------
A derivative may be *proposed* by anything: an author, a model, SymPy, a CAS. **The
proposal is never evidence.** What this module does is differentiate the expression itself,
from primitive rules, and compare. So the trusted computation is HML's, and the proposal is
reduced to a claim that either survives that comparison or does not.

That is why this is not ``derivative(1/x) = -1/x^2`` in a lookup table. A table would make
G10 pass and teach the architecture nothing; a replay makes *any* expression in the
supported fragment checkable and makes a wrong proposal impossible to launder.

Primitive rules
---------------
``constant`` · ``variable`` · ``sum`` (and difference) · ``product`` · ``quotient`` ·
``integer_power``. Each is the textbook rule, applied structurally.

``chain`` is **not** implemented. It would need `Call` handling plus definition unfolding to
be useful, which is neither cheap nor clean at this size, and Gold-10 does not reach it.
Anything outside the fragment fails closed — it is not silently differentiated as a
constant, which is the dangerous default.

Domain conditions go through the existing machinery
---------------------------------------------------
The quotient rule requires its denominator to be non-zero. That condition is emitted as an
ordinary obligation carried on the verdict, turned into a ``ReasoningObligation`` by
``check.py``, and discharged against Γ by ``RefinementEnv.entails`` — the same path a
``divide_both_sides`` obligation takes. There is no second domain-condition system, and an
undischarged one means the certificate does not validate.

Note the condition is on the **original denominator**, ``x != 0``, not on the ``x ^ 2`` that
appears in the result. They are equivalent here but the first is the one the rule actually
requires, and stating the derived form would be recording a consequence in place of a
premise.

Normalisation
-------------
Replaying the quotient rule on ``1 / x`` yields ``(0 * x - 1 * 1) / x ^ 2``, which is
correct and unreadable. Reaching ``-1 / x ^ 2`` is done with the **oriented algebra
identities** in :mod:`hamiltonian_lang.libraries.algebra` — each step justified by a named,
registered theorem, applied deterministically to a fixed point, terminating because every
rewrite strictly shrinks the term. No search, no e-graph, and emphatically no
``sympy.simplify(...) == ...``, which would put an untrusted oracle back in the middle of
the trusted path.

:func:`normalise` returns the identities it used, so a normalisation is an auditable list of
theorem applications rather than a black box.
"""

from __future__ import annotations

from dataclasses import replace

from ..ast.nodes import (
    BinOp,
    Comparison,
    DerivativeExpr,
    Expr,
    Literal,
    Ref,
    SymbolId,
    UnaryOp,
)
from . import algebra

__all__ = [
    "DifferentiationError",
    "PRIMITIVE_RULES",
    "differentiate",
    "normalise",
    "check_derivative_claim",
]

#: Named for diagnostics and for the handoff. Each is applied structurally by
#: :func:`differentiate`; none is a kernel inference rule.
PRIMITIVE_RULES = (
    "derivative_constant",
    "derivative_variable",
    "derivative_sum",
    "derivative_product",
    "derivative_quotient",
    "derivative_integer_power",
)


class DifferentiationError(Exception):
    """The expression is outside the supported fragment. Always a refusal, never a guess."""


def _zero(like: Expr) -> Literal:
    return Literal(value=0.0, raw="0.0", span=like.span)


def _one(like: Expr) -> Literal:
    return Literal(value=1.0, raw="1.0", span=like.span)


def _num(value: float, like: Expr) -> Literal:
    return Literal(value=value, raw=repr(value), span=like.span)


def _mentions(e: Expr, sid: SymbolId) -> bool:
    from ..ast.nodes import walk

    return any(
        isinstance(n, Ref) and n.symbol_id is not None and n.symbol_id == sid
        for n in walk(e)
    )


def differentiate(
    body: Expr, sid: SymbolId, *, _used: set[str] | None = None
) -> tuple[Expr, tuple[Comparison, ...], set[str]]:
    """``d(body)/dx`` for the binder ``sid``.

    Returns the derivative, the domain conditions the rules require, and the names of the
    primitive rules used. Raises :class:`DifferentiationError` outside the fragment.
    """
    used: set[str] = _used if _used is not None else set()
    conditions: list[Comparison] = []

    def rec(e: Expr) -> Expr:
        inner, conds, _ = differentiate(e, sid, _used=used)
        conditions.extend(conds)
        return inner

    # d(c)/dx = 0 for any literal, and for any Ref that is not the binder. A reference to
    # another variable is constant *with respect to x*, which is the correct reading.
    if isinstance(body, Literal):
        used.add("derivative_constant")
        return _zero(body), (), used
    if isinstance(body, Ref):
        if body.symbol_id is not None and body.symbol_id == sid:
            used.add("derivative_variable")
            return _one(body), (), used
        used.add("derivative_constant")
        return _zero(body), (), used

    if isinstance(body, UnaryOp) and body.op == "-":
        used.add("derivative_sum")
        return UnaryOp(op="-", operand=rec(body.operand), span=body.span), tuple(conditions), used

    if isinstance(body, BinOp):
        if body.op in ("+", "-"):
            used.add("derivative_sum")
            return (
                BinOp(op=body.op, left=rec(body.left), right=rec(body.right), span=body.span),
                tuple(conditions),
                used,
            )
        if body.op == "*":
            # d(uv) = u'v + uv'
            used.add("derivative_product")
            u, v = body.left, body.right
            du, dv = rec(u), rec(v)
            return (
                BinOp(
                    op="+",
                    left=BinOp(op="*", left=du, right=v, span=body.span),
                    right=BinOp(op="*", left=u, right=dv, span=body.span),
                    span=body.span,
                ),
                tuple(conditions),
                used,
            )
        if body.op == "/":
            # d(u/v) = (u'v - uv') / v^2, requiring v != 0.
            used.add("derivative_quotient")
            u, v = body.left, body.right
            du, dv = rec(u), rec(v)
            conditions.append(
                Comparison(op="!=", left=v, right=_zero(v), span=v.span)
            )
            numerator = BinOp(
                op="-",
                left=BinOp(op="*", left=du, right=v, span=body.span),
                right=BinOp(op="*", left=u, right=dv, span=body.span),
                span=body.span,
            )
            return (
                BinOp(
                    op="/",
                    left=numerator,
                    right=BinOp(op="^", left=v, right=_num(2.0, v), span=body.span),
                    span=body.span,
                ),
                tuple(conditions),
                used,
            )
        if body.op == "^":
            # d(u^n) = n * u^(n-1) * u', for a LITERAL n only. A symbolic exponent needs
            # logarithmic differentiation and is outside the fragment; refusing is correct.
            if not isinstance(body.right, Literal) or isinstance(body.right.value, bool):
                raise DifferentiationError(
                    "a symbolic exponent is outside the supported fragment"
                )
            if _mentions(body.right, sid):
                raise DifferentiationError(
                    "an exponent depending on the differentiation variable is outside "
                    "the supported fragment"
                )
            used.add("derivative_integer_power")
            n = float(body.right.value)
            base, dbase = body.left, rec(body.left)
            power = BinOp(
                op="^", left=base, right=_num(n - 1.0, body.right), span=body.span
            )
            return (
                BinOp(
                    op="*",
                    left=BinOp(op="*", left=_num(n, body.right), right=power, span=body.span),
                    right=dbase,
                    span=body.span,
                ),
                tuple(conditions),
                used,
            )
        raise DifferentiationError(
            f"operator {body.op!r} is outside the supported differentiation fragment"
        )

    raise DifferentiationError(
        f"{type(body).__name__} is outside the supported differentiation fragment"
    )


# ---------------------------------------------------------------------------
# Normalisation by oriented algebra identities
# ---------------------------------------------------------------------------


def normalise(e: Expr, *, _budget: int = 200) -> tuple[Expr, tuple[str, ...]]:
    """Rewrite to a fixed point using the registered algebra identities.

    Bottom-up, deterministic, and terminating: every rewrite in
    ``algebra.REWRITES`` strictly reduces the term, and the explicit budget is a
    belt-and-braces guard so a future identity that failed to shrink cannot hang the
    compiler. Returns the normalised term and the identities that fired.
    """
    used: list[str] = []

    def go(node: Expr, budget: int) -> Expr:
        if budget <= 0:
            return node
        # Children first, so an outer rule sees already-reduced operands.
        if isinstance(node, BinOp):
            node = replace(node, left=go(node.left, budget - 1), right=go(node.right, budget - 1))
        elif isinstance(node, UnaryOp):
            node = replace(node, operand=go(node.operand, budget - 1))
        rewritten, theorem_id = algebra.rewrite_step(node)
        if theorem_id is None:
            return node
        used.append(theorem_id)
        return go(rewritten, budget - 1)

    out = go(e, _budget)
    # Stable, de-duplicated, so the report is "which identities were needed" rather than
    # an execution trace whose length depends on traversal order.
    seen: list[str] = []
    for t in used:
        if t not in seen:
            seen.append(t)
    return out, tuple(seen)


def _instantiate_binder(e: Expr, binder: SymbolId, target: Ref) -> Expr:
    """Replace references to the derivative's bound variable with ``target``.

    Why this is needed, and why it is an interpretation rather than a semantic change.

    ``derivative(body, x : T)`` **binds** ``x``: inside the body ``x`` is the binder's
    symbol at nesting depth 1, while an ``x`` on the other side of the equality is the
    *module-level* variable at depth 0. They are genuinely different symbols, and comparing
    them naively fails --

        derivative(x * x, x : Real) = 1.0 * x + x * 1.0
                   ^^^^^ sym:#1.0                ^ sym:#0.0

    -- which is HML's binder machinery working correctly, not a defect.

    The notation ``d/dx f(x) = g(x)`` is universally read with those two ``x``s denoting
    the same point, and the existing idiom in ``examples/analysis/derivative_and_integral.hml``
    uses the same convention. So the replay instantiates its result at the free variable
    the claim actually uses, which is the standard reading and is exactly what
    ``forall_elim`` does for a universal. **No binder semantics are altered** -- this is a
    substitution performed by a library checker on a term it constructed itself.

    Limitation, stated rather than hidden: the supported fragment contains no nested
    binders, so a plain substitution suffices and no depth shifting is required. A nested
    binder would need ``reasoning.binders`` and is outside V0.
    """
    if isinstance(e, Ref):
        return target if e.symbol_id is not None and e.symbol_id == binder else e
    if isinstance(e, BinOp):
        return replace(
            e,
            left=_instantiate_binder(e.left, binder, target),
            right=_instantiate_binder(e.right, binder, target),
        )
    if isinstance(e, UnaryOp):
        return replace(e, operand=_instantiate_binder(e.operand, binder, target))
    return e


def _free_occurrence(e: Expr, name: str) -> Ref | None:
    """A module-level reference to ``name`` inside ``e``, if the claim uses one."""
    from ..ast.nodes import walk

    for node in walk(e):
        if (
            isinstance(node, Ref)
            and node.name == name
            and node.symbol_id is not None
            and node.symbol_id.depth == 0
        ):
            return node
    return None


def _untyped(e: Expr) -> Expr:
    """``e`` with every inferred type cleared, recursively. ``symbol_id`` is preserved.

    Used only to compare two arithmetic terms for structural sameness. See the note at the
    comparison site for why this is a normalisation rather than a rival identity.
    """
    out = e
    if isinstance(e, BinOp):
        out = replace(e, left=_untyped(e.left), right=_untyped(e.right))
    elif isinstance(e, UnaryOp):
        out = replace(e, operand=_untyped(e.operand))
    return replace(out, type_=None)


# ---------------------------------------------------------------------------
# The claim checker
# ---------------------------------------------------------------------------


def check_derivative_claim(claim: Expr) -> tuple[Expr, tuple[Comparison, ...], dict[str, str]]:
    """Validate ``derivative(body, x : T) = <result>`` by replaying the differentiation.

    Returns the claim (so the boundary can confirm it is what was established), the domain
    conditions to be discharged, and detail for provenance. Raises
    :class:`DifferentiationError` on anything it will not certify.
    """
    if not (isinstance(claim, Comparison) and claim.op == "="):
        raise DifferentiationError(
            "a derivative certificate must be an equality "
            "`derivative(<body>, x : T) = <result>`"
        )
    left, right = claim.left, claim.right
    if not isinstance(left, DerivativeExpr):
        # Accept it written the other way round; refuse when neither side is a derivative.
        if isinstance(right, DerivativeExpr):
            left, right = right, left
        else:
            raise DifferentiationError(
                "neither side of the equality is a `derivative(...)` expression"
            )
    if left.symbol_id is None:
        raise DifferentiationError("the derivative's binder is unresolved")

    computed, conditions, rules = differentiate(left.body, left.symbol_id)

    # Read the equation the way the notation means it: the bound `x` of the derivative and
    # a free `x` on the other side denote the same point. See `_instantiate_binder`.
    target = _free_occurrence(right, left.var)
    if target is not None:
        computed = _instantiate_binder(computed, left.symbol_id, target)
        conditions = tuple(
            replace(
                c,
                left=_instantiate_binder(c.left, left.symbol_id, target),
                right=_instantiate_binder(c.right, left.symbol_id, target),
            )
            for c in conditions
        )

    computed_n, used_computed = normalise(computed)
    claimed_n, used_claimed = normalise(right)

    from ..backends.canonical import expr_identity
    from ..backends.hml import render_expr

    # Compare on STRUCTURE, with inferred types stripped from both sides.
    #
    # The replay constructs fresh nodes, which carry no inferred type; the author's claim
    # came through the type checker and does. `expr_identity` includes `type_`, so an
    # otherwise identical pair would differ on a field neither side is making a claim
    # about here. Stripping is applied to *both* sides by the same function, and the
    # comparison is still the language's own `expr_identity` -- this is a normalisation
    # before it, not a second notion of sameness.
    #
    # Nothing is lost by it: the claim had to type-check to reach this point at all, and
    # `symbol_id` -- which is what actually distinguishes one variable from another -- is
    # deliberately preserved.
    if expr_identity(_untyped(computed_n)) != expr_identity(_untyped(claimed_n)):
        raise DifferentiationError(
            f"replaying the differentiation gives {render_expr(computed_n)}, "
            f"not {render_expr(claimed_n)}"
        )

    identities = tuple(sorted(set(used_computed) | set(used_claimed)))
    return (
        claim,
        conditions,
        {
            "rules": ", ".join(sorted(rules)),
            "identities": ", ".join(identities) or "none",
            "replayed": render_expr(computed_n),
        },
    )
