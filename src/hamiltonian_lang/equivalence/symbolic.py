"""Tier 2 -- trusted algebraic and symbolic equivalence.

Three decision procedures, each narrow enough to be trusted:

1. **Difference is zero.** For two magnitudes, ``simplify(a - b) == 0`` certifies
   equality. Covers commutative reordering, associative regrouping, constant
   simplification, expansion and factorisation in one step.
2. **Relations are proportional.** ``l1 REL r1`` and ``l2 REL r2`` describe the
   same set when ``(l1-r1) = k*(l2-r2)`` for a nonzero constant ``k``. For an
   equality any nonzero ``k`` works; for an inequality the *sign* of ``k`` decides,
   and a negative ``k`` requires the operator to be mirrored. When ``k`` is
   symbolic its sign is taken from the declared types -- and recorded as a tracked
   assumption, never assumed silently.
3. **Propositional validity.** ``Equivalent(A, B)`` is checked with a SAT solver
   over shared atoms. The two directions are *not* symmetric:

   * unsatisfiable negation certifies equivalence, and does so soundly even when
     the atoms are dependent, because propositional validity holds under every
     interpretation of the atoms;
   * a satisfying model refutes equivalence **only** when every atom is a free
     boolean. When an atom stands for a comparison, a model may assign ``x > 0``
     true and ``x > -1`` false, describing a world that does not exist. In that
     case the tier reports ``INCONCLUSIVE``.

Anything outside these three is ``INCONCLUSIVE`` or ``UNSUPPORTED``. Neither is a
failure.
"""

from __future__ import annotations

from typing import Any

from ..ast.nodes import BinOp, Comparison, Expr, Literal, walk
from .display import show
from .status import (
    Assumption,
    Certificate,
    EquivalenceResult,
    EquivalenceStatus,
    NonEquivalenceProof,
    Tier,
)
from .sympy_bridge import SYMPY_AVAILABLE, TranslationContext, is_propositional

if SYMPY_AVAILABLE:  # pragma: no branch - sympy is present on this host
    import sympy
    from sympy.logic.inference import satisfiable

__all__ = [
    "MIRRORED_OPERATORS",
    "compare_expressions",
    "expressions_equal",
]

#: Reversing the sides of an inequality mirrors its operator. Strictness is never
#: changed: ``<`` and ``<=`` are different relations and stay different.
MIRRORED_OPERATORS: dict[str, str] = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}

_REL_OPS = {
    "Equality": "=",
    "Unequality": "!=",
    "StrictLessThan": "<",
    "LessThan": "<=",
    "StrictGreaterThan": ">",
    "GreaterThan": ">=",
}


def _unsupported(detail: str) -> EquivalenceResult:
    return EquivalenceResult(Tier.TIER2_SYMBOLIC, EquivalenceStatus.UNSUPPORTED, detail)


def _inconclusive(detail: str, **evidence: Any) -> EquivalenceResult:
    return EquivalenceResult(
        Tier.TIER2_SYMBOLIC, EquivalenceStatus.INCONCLUSIVE, detail, evidence=evidence
    )


def _relation_parts(rel: Any) -> tuple[str, Any] | None:
    """``(operator, lhs - rhs)`` for a SymPy relational, else None."""
    op = _REL_OPS.get(type(rel).__name__)
    if op is None:
        return None
    return op, rel.lhs - rel.rhs


def _has_symbolic_division(ast_node: object) -> bool:
    """Whether the *source* divides by something that could be zero.

    Checked on the HML tree, not on the SymPy image, because SymPy evaluates
    ``a/a`` to ``1`` at construction: by the time the translated expression exists
    the division has already vanished, and with it the side condition that makes
    the rewrite true. Certifying ``a/a == b/b`` without recording "denominators are
    nonzero" would be an equivalence that is false at zero.
    """
    for node in walk(ast_node):
        if isinstance(node, BinOp) and node.op == "/":
            right = node.right
            if isinstance(right, Literal) and right.value not in (0, 0.0):
                continue
            return True
    return False


def _division_assumptions(*ast_nodes: object) -> tuple[Assumption, ...]:
    if any(_has_symbolic_division(n) for n in ast_nodes if n is not None):
        return (
            Assumption(
                "every symbolic denominator is nonzero",
                "derived",
            ),
        )
    return ()


def expressions_equal(left: Any, right: Any) -> bool:
    """Whether ``simplify(left - right)`` is identically zero."""
    difference = sympy.expand(left - right)
    if difference == 0:
        return True
    simplified = sympy.simplify(difference)
    return bool(simplified == 0 or simplified.is_zero is True)


def _compare_relations(
    left: Any,
    right: Any,
    left_ast: Expr,
    right_ast: Expr,
) -> EquivalenceResult | None:
    left_src, right_src = show(left_ast), show(right_ast)
    a = _relation_parts(left)
    b = _relation_parts(right)
    if a is None or b is None:
        return None
    op_a, form_a = a
    op_b, form_b = b

    if form_b == 0:
        return _inconclusive(
            "the candidate relation is degenerate (both sides identical), so no "
            "scaling factor exists"
        )
    ratio = sympy.simplify(sympy.cancel(form_a / form_b))
    if ratio.has(sympy.zoo) or ratio.has(sympy.nan) or ratio.has(sympy.oo):
        return _inconclusive("the ratio of the two relations is not a finite quantity")
    if ratio == 0:
        return _inconclusive("the reference relation is degenerate")

    assumptions = _division_assumptions(left_ast, right_ast)
    constant = not ratio.free_symbols

    same_op = op_a == op_b
    mirrored = MIRRORED_OPERATORS.get(op_a) == op_b

    if op_a in ("=", "!=") and op_b == op_a:
        if constant:
            return EquivalenceResult(
                Tier.TIER2_SYMBOLIC,
                EquivalenceStatus.VERIFIED_EQUIVALENT,
                f"the two {op_a} relations differ by the nonzero constant factor {ratio}",
                certificate=Certificate(
                    "tier2.sympy_relation_proportional",
                    f"({left_src}) and ({right_src}) have the same solution set: "
                    f"their normalised forms differ by the factor {ratio}",
                    assumptions=assumptions,
                    witness={"factor": str(ratio)},
                ),
                assumptions=assumptions,
            )
        sign = _known_sign(ratio)
        if sign is not None:
            note = Assumption(f"{ratio} != 0", "declared type")
            return EquivalenceResult(
                Tier.TIER2_SYMBOLIC,
                EquivalenceStatus.VERIFIED_EQUIVALENT,
                f"the two {op_a} relations differ by the factor {ratio}, known nonzero "
                f"from the declared types",
                certificate=Certificate(
                    "tier2.sympy_relation_proportional",
                    f"({left_src}) and ({right_src}) have the same solution set",
                    assumptions=assumptions + (note,),
                    witness={"factor": str(ratio)},
                ),
                assumptions=assumptions + (note,),
            )
        return _inconclusive(
            f"the scaling factor {ratio} is not known to be nonzero from the declared "
            f"types, so the two relations cannot be shown to have the same solution set"
        )

    if not same_op and not mirrored:
        return _inconclusive(
            f"the relations use {op_a} and {op_b}; these differ in strictness or in "
            f"kind, which scaling cannot reconcile"
        )

    sign = _known_sign(ratio)
    if sign is None:
        return _inconclusive(
            f"the scaling factor {ratio} has no known sign, and the direction of an "
            f"inequality depends on it"
        )
    if same_op and sign > 0:
        note = Assumption(f"{ratio} > 0, so the direction of {op_a} is preserved", "declared type")
        return _equivalent_relation(left_src, right_src, ratio, assumptions + (note,))
    if mirrored and sign < 0:
        note = Assumption(
            f"{ratio} < 0, so multiplying through reverses {op_b} into {op_a}",
            "declared type",
        )
        return _equivalent_relation(left_src, right_src, ratio, assumptions + (note,))
    return _inconclusive(
        f"the factor {ratio} has sign {sign} but the operators are {op_a} and {op_b}; "
        f"under that sign the directions do not agree"
    )


def _equivalent_relation(
    left_src: str, right_src: str, ratio: Any, assumptions: tuple[Assumption, ...]
) -> EquivalenceResult:
    return EquivalenceResult(
        Tier.TIER2_SYMBOLIC,
        EquivalenceStatus.VERIFIED_EQUIVALENT,
        f"equivalent inequalities under the tracked sign assumption on {ratio}",
        certificate=Certificate(
            "tier2.sympy_relation_proportional",
            f"({left_src}) and ({right_src}) describe the same set",
            assumptions=assumptions,
            witness={"factor": str(ratio)},
        ),
        assumptions=assumptions,
    )


def _known_sign(ratio: Any) -> int | None:
    if not ratio.free_symbols:
        try:
            value = float(ratio)
        except (TypeError, ValueError):
            return None
        if value > 0:
            return 1
        if value < 0:
            return -1
        return None
    if ratio.is_positive:
        return 1
    if ratio.is_negative:
        return -1
    return None


def _compare_propositions(
    left_ast: Expr,
    right_ast: Expr,
    ctx: TranslationContext,
    binder_types_left: dict,
    binder_types_right: dict,
) -> EquivalenceResult:
    lt = ctx.translate_proposition(left_ast, "left", binder_types=binder_types_left)
    rt = ctx.translate_proposition(right_ast, "right", binder_types=binder_types_right)
    if lt.expr is None or rt.expr is None:
        losses = lt.losses + rt.losses
        return EquivalenceResult(
            Tier.TIER2_SYMBOLIC,
            EquivalenceStatus.SEMANTIC_LOSS,
            "the propositions could not be translated without loss",
            semantic_loss=losses,
        )
    negation = sympy.Not(sympy.Equivalent(lt.expr, rt.expr))
    model = satisfiable(negation)
    if model is False:
        return EquivalenceResult(
            Tier.TIER2_SYMBOLIC,
            EquivalenceStatus.VERIFIED_EQUIVALENT,
            "the biconditional is a propositional tautology, so the two hold under "
            "every interpretation of their atoms",
            certificate=Certificate(
                "tier2.propositional_tautology",
                f"Equivalent({show(left_ast)}, {show(right_ast)}) is valid; validity "
                f"over free atoms holds for any reading of those atoms",
                witness={"atoms": ctx.atoms()},
            ),
        )
    if ctx.atoms_independent:
        assignment = {str(k): str(v) for k, v in model.items()}
        return EquivalenceResult(
            Tier.TIER2_SYMBOLIC,
            EquivalenceStatus.VERIFIED_NONEQUIVALENT,
            "a propositional countermodel exists over independent boolean atoms, so "
            "the two propositions genuinely differ",
            proof=NonEquivalenceProof(
                "tier2.propositional_countermodel",
                f"under {assignment} the two propositions take different truth values",
                left=show(left_ast),
                right=show(right_ast),
            ),
            evidence={"model": assignment, "atoms": ctx.atoms()},
        )
    return _inconclusive(
        "a propositional countermodel exists, but at least one atom stands for a "
        "comparison rather than a free boolean, so the model may describe a world "
        "that does not exist; no conclusion is drawn",
        atoms=ctx.atoms(),
    )


def compare_expressions(
    left: Expr | None,
    right: Expr | None,
    ctx: TranslationContext,
    *,
    binder_types_left: dict | None = None,
    binder_types_right: dict | None = None,
) -> EquivalenceResult:
    """Decide a single residual symbolically, or report why it could not be decided."""
    if not SYMPY_AVAILABLE:  # pragma: no cover
        return _unsupported("sympy is not importable in this environment")
    if left is None or right is None:
        return _unsupported("one side has no expression to compare")

    bl = dict(binder_types_left or {})
    br = dict(binder_types_right or {})

    if is_propositional(left) and is_propositional(right):
        if isinstance(left, Comparison) and isinstance(right, Comparison):
            lt = ctx.translate(left, "left", binder_types=bl)
            rt = ctx.translate(right, "right", binder_types=br)
            if lt.expr is not None and rt.expr is not None:
                verdict = _compare_relations(lt.expr, rt.expr, left, right)
                if verdict is not None and verdict.status is not EquivalenceStatus.INCONCLUSIVE:
                    return verdict
                if verdict is not None:
                    relational = verdict
                    propositional = _compare_propositions(left, right, ctx, bl, br)
                    return (
                        propositional
                        if propositional.status is not EquivalenceStatus.INCONCLUSIVE
                        else relational
                    )
        return _compare_propositions(left, right, ctx, bl, br)

    if is_propositional(left) != is_propositional(right):
        return _inconclusive(
            "one side is a proposition and the other is a magnitude; the comparison "
            "is not well posed and no verdict is issued"
        )

    lt = ctx.translate(left, "left", binder_types=bl)
    rt = ctx.translate(right, "right", binder_types=br)
    if lt.expr is None or rt.expr is None:
        return EquivalenceResult(
            Tier.TIER2_SYMBOLIC,
            EquivalenceStatus.SEMANTIC_LOSS,
            "the expressions could not be translated into SymPy without loss",
            semantic_loss=lt.losses + rt.losses,
        )

    try:
        equal = expressions_equal(lt.expr, rt.expr)
    except (TypeError, ValueError, AttributeError, NotImplementedError) as exc:
        return _inconclusive(f"SymPy could not decide the difference: {exc}")

    if equal:
        assumptions = _division_assumptions(left, right) + lt.assumptions + rt.assumptions
        return EquivalenceResult(
            Tier.TIER2_SYMBOLIC,
            EquivalenceStatus.VERIFIED_EQUIVALENT,
            "the difference of the two expressions simplifies to zero",
            certificate=Certificate(
                "tier2.sympy_difference_is_zero",
                f"simplify(({show(left)}) - ({show(right)})) == 0",
                assumptions=assumptions,
                witness={"left": str(lt.expr), "right": str(rt.expr)},
            ),
            assumptions=assumptions,
        )
    return _inconclusive(
        "the difference did not simplify to zero. That is not a proof of "
        "difference: SymPy's simplifier is incomplete",
        left=str(lt.expr),
        right=str(rt.expr),
    )
