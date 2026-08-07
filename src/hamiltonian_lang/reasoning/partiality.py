"""Term-level definedness: one contract registry for every partial operation (D-036).

Why this is term-level and not rule-level
-----------------------------------------
The first version of this idea attached a side condition to an inference *rule*:
``divide_both_sides`` declared ``k != 0``. That is keyed on the wrong thing, and the
consequence was a critical soundness hole — spelling the division differently walked
straight past it:

    assume p1 : a = b
    derive d1 : a * (1.0 / 0.0) = b * (1.0 / 0.0) from p1
                by multiply_both_sides(by := 1.0 / 0.0)

``multiply_both_sides`` declares no side condition, so this reached **VERIFIED** and its
goal reached **PROVED**, with zero obligations and zero diagnostics, carrying a literal
division by zero in the certified statement. The rule was blameless: multiplying both
sides by anything really is valid. What was wrong is that *nobody asked whether the thing
being multiplied by was defined*.

Definedness is a property of a **term**, not of the rule that happens to mention it. So
this module walks expressions and generates a precondition for every partial operation it
finds, wherever that operation appears — inside a conclusion, a rule argument, a
requirement, a declaration's initialiser. A rule cannot evade it by not knowing about it.

The four classes (D-036)
------------------------
``TOTAL``
    Defined everywhere on its domain type. No obligation.
``GUARDED``
    The argument *type* restricts the domain, so out-of-domain is a static type error and
    the type rule is the guard. ``log`` (PositiveReal), ``sqrt`` (NonNegativeReal).
``CONTRACTED``
    Defined on a subset expressible as a proposition. **Always** generates a mandatory
    precondition, which Γ may discharge and which otherwise stays OPEN.
``PARTIAL_UNDECIDABLE``
    Mathematically partial, precondition not expressible in HML's proposition language.
    Recorded explicitly rather than silently treated as total.

What this deliberately does not do
----------------------------------
It does not totalise. Lean defines ``(1:Nat)/0 = 0`` and moves on, which is defensible for
a proof assistant carrying a full logic; HML's product is *surfacing* the condition to a
model that must repair, and totalising hides exactly the signal the repair loop consumes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum

from ..ast.nodes import BinOp, Call, Comparison, Expr, Index, Literal, UnaryOp

__all__ = [
    "Partiality",
    "OperationContract",
    "Precondition",
    "CONTRACTS",
    "preconditions_of",
    "decides_false",
]


class Partiality(StrEnum):
    TOTAL = "TOTAL"
    GUARDED = "GUARDED"
    CONTRACTED = "CONTRACTED"
    PARTIAL_UNDECIDABLE = "PARTIAL_UNDECIDABLE"


@dataclass(frozen=True)
class Precondition:
    """One instantiated definedness requirement found in a term."""

    proposition: Expr
    reason: str
    #: The sub-expression that generated it, for the diagnostic's span.
    site: Expr
    mandatory: bool = True


@dataclass(frozen=True)
class OperationContract:
    """What an operation requires in order to denote anything."""

    name: str
    partiality: Partiality
    reason: str = ""
    #: Builds the precondition(s) from the operation's own node. Only CONTRACTED
    #: operations have one.
    build: Callable[[Expr], list[Expr]] | None = None
    note: str = ""


# ---------------------------------------------------------------------------
# Precondition builders
# ---------------------------------------------------------------------------


def _ne_zero(e: Expr) -> Expr:
    """``e != 0``, with the span of the offending term so diagnostics point at it."""
    return Comparison(
        op="!=",
        left=e,
        right=Literal(value=0, raw="0", span=e.span),
        span=e.span,
    )


def _divisor_nonzero(node: Expr) -> list[Expr]:
    assert isinstance(node, BinOp)
    return [_ne_zero(node.right)]


def _base_nonzero_for_negative_power(node: Expr) -> list[Expr]:
    """``x ^ n`` needs ``x != 0`` only when ``n`` may be negative.

    A literal non-negative exponent is total and generates nothing -- otherwise every
    ``x ^ 2.0`` in the corpus would carry a spurious obligation, which is the fastest way
    to make authors stop reading obligations at all.
    """
    assert isinstance(node, BinOp)
    exponent = node.right
    if isinstance(exponent, Literal) and not isinstance(exponent.value, bool):
        if exponent.value >= 0:
            return []
        return [_ne_zero(node.left)]
    if isinstance(exponent, UnaryOp) and exponent.op == "-":
        return [_ne_zero(node.left)]
    # An unknown exponent may be negative, so the base must be non-zero.
    return [_ne_zero(node.left)]


def _tan_pole(node: Expr) -> list[Expr]:
    """``tan(x)`` needs ``cos(x) != 0``.

    Expressed in HML's own language rather than as an opaque predicate, so Γ can in
    principle discharge it and a backend can lower it.
    """
    assert isinstance(node, Call)
    arg = node.args[0] if node.args else node
    return [_ne_zero(Call(callee="cos", args=[arg], span=arg.span))]


#: The registry. D-036 D4: an operation absent from here is a build error, asserted by
#: `tests/reasoning/test_partiality.py::test_every_partial_operation_is_classified`.
CONTRACTS: dict[str, OperationContract] = {
    # -- total ---------------------------------------------------------------
    "+": OperationContract("+", Partiality.TOTAL),
    "-": OperationContract("-", Partiality.TOTAL),
    "*": OperationContract("*", Partiality.TOTAL),
    "@": OperationContract("@", Partiality.TOTAL),
    "exp": OperationContract("exp", Partiality.TOTAL),
    "sin": OperationContract("sin", Partiality.TOTAL),
    "cos": OperationContract("cos", Partiality.TOTAL),
    "abs": OperationContract("abs", Partiality.TOTAL),
    # -- guarded by the argument type ---------------------------------------
    "log": OperationContract(
        "log", Partiality.GUARDED, note="argument type PositiveReal is the guard"
    ),
    "sqrt": OperationContract(
        "sqrt", Partiality.GUARDED, note="argument type NonNegativeReal is the guard"
    ),
    # -- contracted ----------------------------------------------------------
    "/": OperationContract(
        "/", Partiality.CONTRACTED, reason="divide_domain", build=_divisor_nonzero
    ),
    "^": OperationContract(
        "^",
        Partiality.CONTRACTED,
        reason="power_domain",
        build=_base_nonzero_for_negative_power,
    ),
    "tan": OperationContract(
        "tan", Partiality.CONTRACTED, reason="tangent_pole", build=_tan_pole
    ),
}


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------


def _subexpressions(e: Expr | None) -> Iterator[Expr]:
    """Every sub-expression, including ``e`` itself.

    Descends into quantifier and comprehension bodies deliberately: a division by zero
    under a binder is still a division by zero. The binder introduces no risk here
    because this pass only *reads*.
    """
    if e is None:
        return
    yield e
    from ..ast.nodes import walk

    for node in walk(e):
        if isinstance(node, Expr) and node is not e:
            yield node


def preconditions_of(e: Expr | None) -> list[Precondition]:
    """Every definedness requirement the term ``e`` carries.

    Called on conclusions, rule arguments, propositions and initialisers alike -- which
    is the point. An inference rule cannot evade a precondition by not declaring it,
    because the requirement is found in the term rather than in the rule.
    """
    out: list[Precondition] = []
    seen: set[int] = set()
    for node in _subexpressions(e):
        if id(node) in seen:
            continue
        seen.add(id(node))

        key: str | None = None
        if isinstance(node, BinOp):
            key = node.op
        elif isinstance(node, Call):
            key = node.callee
        elif isinstance(node, Index):
            key = "index"

        if key is None:
            continue
        contract = CONTRACTS.get(key)
        if contract is None or contract.partiality is not Partiality.CONTRACTED:
            continue
        if contract.build is None:
            continue
        for prop in contract.build(node):
            out.append(
                Precondition(proposition=prop, reason=contract.reason, site=node)
            )
    return out


def decides_false(prop: Expr) -> bool:
    """Whether ``prop`` is decidably FALSE by inspection alone.

    Only the closed-literal case, which is the one that matters: ``0 != 0`` arising from
    a literal ``1.0 / 0.0``. A refuted obligation is REJECTED rather than merely OPEN --
    refutation is information, and reporting it as ignorance would be a strictly worse
    answer (D-038 V5).
    """
    if not isinstance(prop, Comparison):
        return False
    left, right = prop.left, prop.right
    if not (isinstance(left, Literal) and isinstance(right, Literal)):
        return False
    if isinstance(left.value, bool) or isinstance(right.value, bool):
        return False
    a, b = float(left.value), float(right.value)
    return {
        "!=": a == b,
        "=": a != b,
        ">": a <= b,
        ">=": a < b,
        "<": a >= b,
        "<=": a > b,
    }.get(prop.op, False)
