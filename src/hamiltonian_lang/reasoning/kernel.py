"""The trusted inference kernel.

This module is the *whole* of what Hamiltonian Lang is willing to certify. It is
deliberately small and deliberately dull: every rule here is checked by constructing
the conclusion the rule mandates and comparing it, under canonical identity, with the
conclusion the author wrote. There is no search, no rewriting, no normalisation beyond
the canonical form the language already commits to, and no procedure that can succeed
by accident.

Why this shape and not a tactic language
----------------------------------------
A tactic language decides *what to do next*. That is the model's job (directive §3):
the model may explore freely, and HML records only the state it is willing to commit
to. What HML must supply is the other half — a mechanical answer to "does this step
actually follow?" — and for that, local checking is sufficient and unrestricted
rewriting is actively harmful. An unchecked rewriter is precisely what makes SymPy and
Wolfram untrustworthy as reasoning substrates: it produces authoritative-looking output
with nothing behind it.

The soundness argument
----------------------
For every rule R with premises P1..Pn and arguments A, :func:`apply` returns the unique
conclusion C that R licenses, built structurally from the premises. The checker then
demands ``content_hash(C) == content_hash(claimed)``. So a derivation is CHECKED only
when the author's conclusion **is** the kernel's conclusion, up to alpha-equivalence
and the canonical form. No rule returns a conclusion it did not construct, and no rule
consults the claimed conclusion while constructing it — that separation is what makes
the comparison meaningful rather than circular, and it is asserted by
``tests/reasoning/test_kernel_does_not_see_claim.py``.

Obligations are *not* discharged here. A rule declares what must additionally hold
(``divide_both_sides`` requires a non-zero divisor); establishing it is the refinement
environment's job, and an obligation nobody discharged stays OPEN. A derivation with an
OPEN mandatory obligation is CHECKED, never VERIFIED.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from ..ast.nodes import BinOp, Comparison, Expr, LogicalOp, Ref, UnaryOp

__all__ = [
    "ObligationSpec",
    "RuleSpec",
    "RULES",
    "RuleApplication",
    "apply",
    "rule_names",
]


# ---------------------------------------------------------------------------
# What a rule declares
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObligationSpec:
    """A side condition a rule generates but does not itself establish.

    ``mandatory`` decides whether an OPEN instance blocks VERIFIED. A mandatory
    obligation is one whose failure makes the inference *unsound* (dividing by zero).
    An advisory one records something the reader should know but which does not
    invalidate the step.
    """

    #: Builds the obligation proposition from the bound rule arguments.
    build: Callable[[Mapping[str, Expr]], Expr]
    #: Stable identifier for the reason, used in diagnostics and provenance.
    reason: str
    mandatory: bool = True


@dataclass(frozen=True)
class RuleSpec:
    """One trusted inference rule."""

    name: str
    #: Exact number of premises the rule consumes.
    arity: int
    #: Required role-labelled arguments, in canonical order.
    params: tuple[str, ...] = ()
    #: Applies the rule. Receives premise propositions and bound arguments; returns the
    #: conclusion it licenses, or None when the premises do not have the shape the rule
    #: requires. MUST NOT look at the author's claimed conclusion.
    apply: Callable[[Sequence[Expr], Mapping[str, Expr]], Expr | None] = field(
        default=lambda premises, args: None
    )
    obligations: tuple[ObligationSpec, ...] = ()
    #: One line, shown in diagnostics when the shape does not match.
    shape: str = ""
    doc: str = ""


@dataclass
class RuleApplication:
    """The kernel's verdict on one attempted application."""

    ok: bool
    conclusion: Expr | None = None
    #: Obligation propositions this application generates, paired with their reason and
    #: mandatory flag.
    obligations: list[tuple[Expr, str, bool]] = field(default_factory=list)
    reason: str | None = None


# ---------------------------------------------------------------------------
# Small structural helpers
# ---------------------------------------------------------------------------


def _eq(e: Expr) -> tuple[Expr, Expr] | None:
    """Destructure ``a = b``. Returns None for anything else, including ``a != b``."""
    if isinstance(e, Comparison) and e.op == "=":
        return e.left, e.right
    return None


def _ineq(e: Expr) -> tuple[str, Expr, Expr] | None:
    if isinstance(e, Comparison) and e.op in ("<", "<=", ">", ">="):
        return e.op, e.left, e.right
    return None


def _binop(op: str, left: Expr, right: Expr) -> Expr:
    return BinOp(op=op, left=left, right=right, span=left.span)


def _cmp(op: str, left: Expr, right: Expr, span_from: Expr) -> Expr:
    return Comparison(op=op, left=left, right=right, span=span_from.span)


def _ne_zero(args: Mapping[str, Expr]) -> Expr:
    from ..ast.nodes import Literal

    k = args["by"]
    return Comparison(
        op="!=", left=k, right=Literal(value=0, raw="0", span=k.span), span=k.span
    )


def _gt_zero(args: Mapping[str, Expr]) -> Expr:
    from ..ast.nodes import Literal

    k = args["by"]
    return Comparison(
        op=">", left=k, right=Literal(value=0, raw="0", span=k.span), span=k.span
    )


def _structurally_equal(a: Expr | None, b: Expr | None) -> bool:
    """Canonical-identity comparison of two sub-expressions.

    Uses the language's own canonical form so that this notion of "the same
    expression" is *the* notion the rest of the compiler uses -- not a second,
    subtly different one. A private equality here would be a soundness hole the
    moment it diverged from ``content_hash``.
    """
    if a is None or b is None:
        return a is b
    from ..backends.canonical import expr_identity

    return expr_identity(a) == expr_identity(b)


def _substitute(target: Expr, old: Expr, new: Expr) -> Expr:
    """Replace every occurrence of ``old`` in ``target`` with ``new``.

    Structural, not semantic: it rewrites sub-trees that are canonically identical to
    ``old``. It does not descend into quantifier bodies, because substituting under a
    binder can capture -- and the conservative refusal (leaving the term alone, so the
    conclusion will not match and the step is REJECTED) is the safe failure direction.
    """
    from ..ast.nodes import Call, Index, Quantifier

    if _structurally_equal(target, old):
        return new
    if isinstance(target, BinOp):
        return BinOp(
            op=target.op,
            left=_substitute(target.left, old, new),
            right=_substitute(target.right, old, new),
            span=target.span,
        )
    if isinstance(target, Comparison):
        return Comparison(
            op=target.op,
            left=_substitute(target.left, old, new),
            right=_substitute(target.right, old, new),
            span=target.span,
        )
    if isinstance(target, LogicalOp):
        return LogicalOp(
            op=target.op,
            left=_substitute(target.left, old, new),
            right=_substitute(target.right, old, new),
            span=target.span,
        )
    if isinstance(target, UnaryOp):
        return UnaryOp(
            op=target.op, operand=_substitute(target.operand, old, new), span=target.span
        )
    if isinstance(target, Call):
        return Call(
            callee=target.callee,
            args=[_substitute(a, old, new) for a in target.args],
            span=target.span,
        )
    if isinstance(target, Index):
        return Index(
            base=_substitute(target.base, old, new),
            indices=[_substitute(i, old, new) for i in target.indices],
            span=target.span,
        )
    if isinstance(target, Quantifier):
        # Deliberately not descending: see the docstring. Capture-avoiding substitution
        # under a binder is a real algorithm and this kernel does not implement it.
        return target
    return target


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------


def _both_sides(op: str):
    """``a = b`` |- ``a OP k = b OP k``."""

    def go(premises: Sequence[Expr], args: Mapping[str, Expr]) -> Expr | None:
        parts = _eq(premises[0])
        if parts is None:
            return None
        a, b = parts
        k = args["by"]
        return _cmp("=", _binop(op, a, k), _binop(op, b, k), premises[0])

    return go


def _apply_symmetry(premises: Sequence[Expr], args: Mapping[str, Expr]) -> Expr | None:
    parts = _eq(premises[0])
    if parts is None:
        return None
    a, b = parts
    return _cmp("=", b, a, premises[0])


def _apply_transitivity(premises: Sequence[Expr], args: Mapping[str, Expr]) -> Expr | None:
    first, second = _eq(premises[0]), _eq(premises[1])
    if first is None or second is None:
        return None
    a, b = first
    c, d = second
    if not _structurally_equal(b, c):
        return None
    return _cmp("=", a, d, premises[0])


def _apply_substitute(premises: Sequence[Expr], args: Mapping[str, Expr]) -> Expr | None:
    """``a = b`` and ``P`` |- ``P[a := b]``.

    Premise 0 is the equation, premise 1 the proposition being rewritten.
    """
    eq = _eq(premises[0])
    if eq is None:
        return None
    a, b = eq
    return _substitute(premises[1], a, b)


def _apply_congruence(premises: Sequence[Expr], args: Mapping[str, Expr]) -> Expr | None:
    """``a = b`` |- ``f(a) = f(b)``, for a named unary function."""
    from ..ast.nodes import Call

    eq = _eq(premises[0])
    if eq is None:
        return None
    a, b = eq
    fn = args["fn"]
    if not isinstance(fn, Ref):
        return None
    return _cmp(
        "=",
        Call(callee=fn.name, args=[a], span=a.span),
        Call(callee=fn.name, args=[b], span=b.span),
        premises[0],
    )


def _apply_modus_ponens(premises: Sequence[Expr], args: Mapping[str, Expr]) -> Expr | None:
    """``P`` and ``P implies Q`` |- ``Q``."""
    p, imp = premises[0], premises[1]
    if not (isinstance(imp, LogicalOp) and imp.op == "implies"):
        return None
    if not _structurally_equal(imp.left, p):
        return None
    return imp.right


def _apply_modus_tollens(premises: Sequence[Expr], args: Mapping[str, Expr]) -> Expr | None:
    """``not Q`` and ``P implies Q`` |- ``not P``."""
    nq, imp = premises[0], premises[1]
    if not (isinstance(imp, LogicalOp) and imp.op == "implies"):
        return None
    if not (isinstance(nq, UnaryOp) and nq.op == "not"):
        return None
    if not _structurally_equal(nq.operand, imp.right):
        return None
    return UnaryOp(op="not", operand=imp.left, span=imp.span)


def _apply_and_intro(premises: Sequence[Expr], args: Mapping[str, Expr]) -> Expr | None:
    return LogicalOp(
        op="and", left=premises[0], right=premises[1], span=premises[0].span
    )


def _and_elim(side: str):
    def go(premises: Sequence[Expr], args: Mapping[str, Expr]) -> Expr | None:
        c = premises[0]
        if not (isinstance(c, LogicalOp) and c.op == "and"):
            return None
        return c.left if side == "left" else c.right

    return go


def _apply_weaken_inequality(
    premises: Sequence[Expr], args: Mapping[str, Expr]
) -> Expr | None:
    """``a < b`` |- ``a <= b``. Strictly weaker, and one-directional."""
    parts = _ineq(premises[0])
    if parts is None:
        return None
    op, a, b = parts
    weaker = {"<": "<=", ">": ">="}.get(op)
    if weaker is None:
        return None
    return _cmp(weaker, a, b, premises[0])


def _apply_add_inequality(premises: Sequence[Expr], args: Mapping[str, Expr]) -> Expr | None:
    """``a OP b`` |- ``a + k OP b + k``. Addition preserves every order relation."""
    parts = _ineq(premises[0])
    if parts is None:
        return None
    op, a, b = parts
    k = args["by"]
    return _cmp(op, _binop("+", a, k), _binop("+", b, k), premises[0])


def _apply_multiply_inequality(
    premises: Sequence[Expr], args: Mapping[str, Expr]
) -> Expr | None:
    """``a OP b`` |- ``a * k OP b * k``, **with a mandatory ``k > 0`` obligation**.

    The direction of the relation is preserved only for a positive multiplier. Rather
    than silently assume it, the rule keeps the relation and emits ``k > 0`` as a
    mandatory obligation: if nothing discharges it the step never reaches VERIFIED.
    Multiplying an inequality by an unsigned quantity is one of the most common false
    algebra steps, and this is where it is caught.
    """
    parts = _ineq(premises[0])
    if parts is None:
        return None
    op, a, b = parts
    k = args["by"]
    return _cmp(op, _binop("*", a, k), _binop("*", b, k), premises[0])


RULES: dict[str, RuleSpec] = {
    "symmetry": RuleSpec(
        name="symmetry",
        arity=1,
        apply=_apply_symmetry,
        shape="a = b  |-  b = a",
        doc="Equality is symmetric.",
    ),
    "transitivity": RuleSpec(
        name="transitivity",
        arity=2,
        apply=_apply_transitivity,
        shape="a = b, b = c  |-  a = c",
        doc="Equality is transitive. The shared middle term must match exactly.",
    ),
    "add_both_sides": RuleSpec(
        name="add_both_sides",
        arity=1,
        params=("by",),
        apply=_both_sides("+"),
        shape="a = b  |-  a + k = b + k",
        doc="Adding the same term to both sides preserves equality unconditionally.",
    ),
    "subtract_both_sides": RuleSpec(
        name="subtract_both_sides",
        arity=1,
        params=("by",),
        apply=_both_sides("-"),
        shape="a = b  |-  a - k = b - k",
        doc="Subtracting the same term from both sides preserves equality.",
    ),
    "multiply_both_sides": RuleSpec(
        name="multiply_both_sides",
        arity=1,
        params=("by",),
        apply=_both_sides("*"),
        shape="a = b  |-  a * k = b * k",
        doc="Multiplying both sides preserves equality for any k, including zero.",
    ),
    "divide_both_sides": RuleSpec(
        name="divide_both_sides",
        arity=1,
        params=("by",),
        apply=_both_sides("/"),
        obligations=(
            ObligationSpec(build=_ne_zero, reason="divide_domain", mandatory=True),
        ),
        shape="a = b  |-  a / k = b / k   [requires k != 0]",
        doc="Dividing both sides is sound only for a non-zero divisor.",
    ),
    "substitute": RuleSpec(
        name="substitute",
        arity=2,
        apply=_apply_substitute,
        shape="a = b, P  |-  P[a := b]",
        doc=(
            "Substitution of equals. Does not descend into quantifier bodies, so a "
            "step that would require capture-avoiding substitution is REJECTED rather "
            "than performed unsoundly."
        ),
    ),
    "congruence": RuleSpec(
        name="congruence",
        arity=1,
        params=("fn",),
        apply=_apply_congruence,
        shape="a = b  |-  f(a) = f(b)",
        doc="Functions respect equality. f must be a named unary function.",
    ),
    "modus_ponens": RuleSpec(
        name="modus_ponens",
        arity=2,
        apply=_apply_modus_ponens,
        shape="P, P implies Q  |-  Q",
        doc="The antecedent must match the implication's left side exactly.",
    ),
    "modus_tollens": RuleSpec(
        name="modus_tollens",
        arity=2,
        apply=_apply_modus_tollens,
        shape="not Q, P implies Q  |-  not P",
        doc="Denying the consequent.",
    ),
    "and_intro": RuleSpec(
        name="and_intro",
        arity=2,
        apply=_apply_and_intro,
        shape="P, Q  |-  P and Q",
        doc="Conjunction introduction.",
    ),
    "and_elim_left": RuleSpec(
        name="and_elim_left",
        arity=1,
        apply=_and_elim("left"),
        shape="P and Q  |-  P",
        doc="Conjunction elimination, left.",
    ),
    "and_elim_right": RuleSpec(
        name="and_elim_right",
        arity=1,
        apply=_and_elim("right"),
        shape="P and Q  |-  Q",
        doc="Conjunction elimination, right.",
    ),
    "weaken_inequality": RuleSpec(
        name="weaken_inequality",
        arity=1,
        apply=_apply_weaken_inequality,
        shape="a < b  |-  a <= b",
        doc=(
            "Strict to non-strict. One-directional by construction: there is no rule "
            "in this kernel that strengthens <= to <, because none is sound."
        ),
    ),
    "add_inequality": RuleSpec(
        name="add_inequality",
        arity=1,
        params=("by",),
        apply=_apply_add_inequality,
        shape="a < b  |-  a + k < b + k",
        doc="Translation preserves order for any k.",
    ),
    "multiply_inequality": RuleSpec(
        name="multiply_inequality",
        arity=1,
        params=("by",),
        apply=_apply_multiply_inequality,
        obligations=(
            ObligationSpec(build=_gt_zero, reason="order_preserving_multiplier", mandatory=True),
        ),
        shape="a < b  |-  a * k < b * k   [requires k > 0]",
        doc=(
            "Scaling preserves the direction of an inequality only for a positive "
            "multiplier; the obligation is mandatory."
        ),
    ),
}


def rule_names() -> tuple[str, ...]:
    return tuple(sorted(RULES))


def apply(
    rule: str, premises: Sequence[Expr], args: Mapping[str, Expr]
) -> RuleApplication:
    """Apply ``rule`` and return the conclusion it licenses, or a refusal.

    The caller compares the returned conclusion against the author's claim. This
    function never sees that claim.
    """
    spec = RULES.get(rule)
    if spec is None:
        return RuleApplication(ok=False, reason=f"unknown rule {rule!r}")
    if len(premises) != spec.arity:
        return RuleApplication(
            ok=False,
            reason=(
                f"{rule} takes {spec.arity} premise(s), {len(premises)} given "
                f"({spec.shape})"
            ),
        )
    missing = [p for p in spec.params if p not in args]
    if missing:
        return RuleApplication(
            ok=False,
            reason=f"{rule} requires argument(s) {', '.join(missing)} ({spec.shape})",
        )

    conclusion = spec.apply(premises, args)
    if conclusion is None:
        return RuleApplication(
            ok=False,
            reason=f"the premises do not have the shape {rule} requires: {spec.shape}",
        )

    obligations = [
        (spec_o.build(args), spec_o.reason, spec_o.mandatory) for spec_o in spec.obligations
    ]
    return RuleApplication(ok=True, conclusion=conclusion, obligations=obligations)
