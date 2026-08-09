"""Side conditions: the parts of a rule that the kernel structurally cannot check.

The kernel is context-free on purpose. It builds a conclusion from premises and arguments,
never consults the author's claim, and that separation is what makes comparing the two
meaningful rather than circular. But two of the quantifier rules' requirements are not
local to their premises:

* the **eigenvariable condition** asks whether anything *anywhere in scope* constrains the
  variable being generalised;
* **domain conformance** asks what type a term has, which lives in the type environment.

Neither question can be answered from a premise list, so the kernel names the condition and
``check.py`` — which holds the module, the symbol table and the evidence graph — answers it
from the static table below.

Fail-closed by construction
---------------------------
:func:`evaluate` rejects an unknown condition name. A rule can therefore never be admitted
by a side condition nobody implemented; the failure direction is "unproved", not
"unguarded". That matters more than it looks: the alternative arrangement, where an
unrecognised name is skipped, produces a rule that *appears* to carry a guard and does not.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from ..ast.nodes import Expr, Quantifier, Ref
from ..types import Type, is_subtype
from .binders import occurs_free

__all__ = ["SideConditionContext", "SIDE_CONDITIONS", "evaluate"]


@dataclass(frozen=True)
class SideConditionContext:
    """What a side condition may consult."""

    rule: str
    label: str
    premises: Sequence[Expr]
    args: Mapping[str, Expr]
    #: (label, proposition) for **every assumption in scope**, including inside `scope`
    #: frames. See the note in :func:`_eigenvariable` on why the whole set is used.
    assumptions: Sequence[tuple[str, Expr]] = ()
    declared_types: Mapping[str, Type] = field(default_factory=dict)


def _eigenvariable(ctx: SideConditionContext) -> tuple[bool, str]:
    """``a`` must be arbitrary: no assumption in scope may constrain it.

    The textbook condition is "``a`` does not occur free in any *undischarged assumption
    the body proof depends on*". Implemented literally, "depends on" would mean the
    transitive premise closure — and that would leave a hole, because HML discharges
    obligations against Γ through :meth:`RefinementEnv.entails`, not only through cited
    premise edges. A derivation can therefore rest on an assumption it never names, and a
    premise-closure check would not see it.

    So the implemented condition is deliberately stronger and simpler: **no assumption in
    scope at all may mention ``a`` freely.** This rejects some sound generalisations — one
    where an unrelated, uncited assumption happens to mention the variable — and that is
    the safe direction. Every assumption it trips on genuinely constrains ``a``, and
    generalising over a constrained variable is exactly the unsoundness the condition
    exists to stop:

        var a : Natural
        assume a1 : a = 0
        derive  d1 : a + 0 = a  ...
        derive  d2 : forall x : Natural . x + 0 = x from d1 by forall_intro(var := a)

    ``d2`` must be REJECTED. ``d1`` was about the particular value 0, not about an
    arbitrary natural.
    """
    var = ctx.args.get("var")
    if not isinstance(var, Ref) or var.symbol_id is None:
        return False, "forall_intro needs 'var' to name a resolved variable"
    if var.symbol_id.depth != 0:
        return False, (
            f"{var.name!r} is already bound; only a module-level variable can be "
            f"generalised"
        )
    offenders = [
        label
        for label, prop in ctx.assumptions
        if prop is not None and occurs_free(prop, var.symbol_id)
    ]
    if offenders:
        return False, (
            f"{var.name!r} is not arbitrary: it occurs free in assumption"
            f"{'s' if len(offenders) > 1 else ''} "
            f"{', '.join(repr(o) for o in offenders)}. A proof about a constrained "
            f"variable does not generalise"
        )
    return True, ""


def _instantiation_domain(ctx: SideConditionContext) -> tuple[bool, str]:
    """``t`` must inhabit the binder's declared domain.

    Fails closed when either type is unknown. Instantiating ``forall n : Natural . phi(n)``
    at a term whose type nobody established is not "probably fine": the whole value of the
    binder's domain is that it constrains what may be substituted.
    """
    quant = ctx.premises[0] if ctx.premises else None
    if not isinstance(quant, Quantifier) or quant.kind != "forall":
        return False, "forall_elim needs a universally quantified premise"
    term = ctx.args.get("at")
    if term is None:
        return False, "forall_elim needs the instantiation term 'at'"
    domain = quant.var_type
    if domain is None:
        return False, (
            f"the binder {quant.var!r} has no declared domain, so no term can be shown "
            f"to inhabit it"
        )
    actual = term.type_
    if actual is None:
        return False, (
            "the instantiation term has no resolved type, so it cannot be shown to "
            "inhabit the binder's domain"
        )
    if not is_subtype(actual, domain):
        return False, (
            f"the instantiation term has type {actual.render()}, which does not inhabit "
            f"the binder's domain {domain.render()}"
        )
    return True, ""


#: Static table. Adding an entry is a deliberate change; there is no registration path
#: from source.
SIDE_CONDITIONS: dict[str, Callable[[SideConditionContext], tuple[bool, str]]] = {
    "eigenvariable": _eigenvariable,
    "instantiation_domain": _instantiation_domain,
}


def evaluate(names: Sequence[str], ctx: SideConditionContext) -> tuple[bool, str]:
    """Check every named condition. Unknown names REJECT; any exception REJECTS."""
    for name in names:
        fn = SIDE_CONDITIONS.get(name)
        if fn is None:
            return False, (
                f"rule {ctx.rule!r} declares side condition {name!r}, which is not "
                f"implemented; the step cannot be admitted"
            )
        try:
            ok, reason = fn(ctx)
        except Exception as exc:  # noqa: BLE001 -- a guard that crashes is a guard that fails
            return False, f"side condition {name!r} failed: {type(exc).__name__}: {exc}"
        if not ok:
            return False, reason
    return True, ""
