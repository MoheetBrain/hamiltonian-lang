"""Binder abstraction and instantiation, in the language's own locally-nameless form.

Why this module exists
----------------------
Universal introduction turns ``P(n)`` — a proposition about a module-level variable — into
``forall n : T . P(n)``. That is not a wrapper. HML's canonical identity is *locally
nameless*: :meth:`SymbolId.canonical` is ``sym:#<depth>.<ordinal>``, so a name's identity
is its binding position, not its spelling. The resolver numbers a binder at nesting depth
``d`` as ``depth=d``, and module-level declarations as ``depth=0``. Empirically, and
asserted by ``tests/reasoning/test_binders.py``::

    var n : Natural
    assume a1 : n + 0 = n                    -- refs are sym:#0.0
    goal   g1 : forall n : Natural . n + 0 = n
                                             -- binder and refs are sym:#1.0

So the premise's ``n`` and the conclusion's ``n`` are **different symbols**, and wrapping
the premise in a ``Quantifier`` would produce a term that is not canonically identical to
the one the resolver builds from the same text. The step would be rejected for a reason
that has nothing to do with its validity.

:func:`abstract` performs the real operation: it re-depths the whole subtree so that the
result is exactly what the resolver would have produced. Every binder and every reference
to a binder moves down one level; the eigenvariable becomes the new outermost binder;
references to *other* module-level names stay where they are. :func:`instantiate` is its
inverse and shares the same traversal.

The safety property
-------------------
Neither function invents a notion of identity. They rearrange symbols so that the
*existing* :func:`~hamiltonian_lang.backends.canonical.expr_identity` can decide the
comparison — which is the only notion of sameness this codebase has, and the only one the
kernel is allowed to use. ``test_forall_intro_matches_the_resolvers_own_parse`` pins that:
it compiles the quantified statement from source and asserts the constructed term is
canonically identical to it. If the resolver's numbering ever changes, that test fails
rather than the kernel silently accepting or rejecting the wrong things.

Rebuilding is generic
---------------------
:func:`_map_children` walks dataclass fields rather than matching on node kinds. This is
the lesson ``evaluate.free_names`` records in its own comment: a whitelist of expression
kinds fell silently out of date the moment D-026 added eleven forms, and under-reporting
free names is wrong in the dangerous direction. A structural rebuild handles the twelfth
expression kind the day it is written.
"""

from __future__ import annotations

from dataclasses import fields, replace
from typing import Any

from ..ast.nodes import Expr, Quantifier, Ref, SymbolId, walk

__all__ = [
    "CaptureError",
    "abstract",
    "instantiate",
    "free_symbols",
    "occurs_free",
]


class CaptureError(Exception):
    """A rearrangement was refused because it would capture or escape a binder.

    Raised, never swallowed into a silent no-op: a kernel rule that quietly declined to
    substitute would build a conclusion that merely *looks* wrong to the author, and the
    resulting diagnostic would blame the wrong thing.
    """


# ---------------------------------------------------------------------------
# Generic structural rebuild
# ---------------------------------------------------------------------------


def _map_children(node: Expr, fn) -> Expr:
    """Rebuild ``node`` with ``fn`` applied to every Expr-valued field.

    Lists of Exprs are mapped elementwise. Non-Expr fields (operators, names, types,
    spans) are carried through untouched by :func:`dataclasses.replace`.
    """
    updates: dict[str, Any] = {}
    for f in fields(node):
        value = getattr(node, f.name, None)
        if isinstance(value, Expr):
            updates[f.name] = fn(value)
        elif isinstance(value, list) and value and all(isinstance(v, Expr) for v in value):
            updates[f.name] = [fn(v) for v in value]
    return replace(node, **updates) if updates else node


def _shifted(sid: SymbolId | None, delta: int) -> SymbolId | None:
    """Move a bound symbol ``delta`` levels. Module-level symbols never move.

    ``depth == 0`` means "declared at module level", which is not a binding position
    inside this expression, so it is invariant under adding or removing an enclosing
    binder.
    """
    if sid is None or sid.depth == 0:
        return sid
    return SymbolId(name=sid.name, ordinal=sid.ordinal, depth=sid.depth + delta)


def _rewrite(node: Expr, delta: int, swap: dict[str, SymbolId], into: dict[str, Expr]) -> Expr:
    """One traversal serving both directions.

    ``delta``  shift applied to every *bound* symbol.
    ``swap``   canonical-symbol -> replacement symbol, applied to matching ``Ref``s.
    ``into``   canonical-symbol -> replacement *term*, applied to matching ``Ref``s.
    """
    if isinstance(node, Ref) and node.symbol_id is not None:
        key = node.symbol_id.canonical()
        if key in into:
            return into[key]
        if key in swap:
            return replace(node, name=swap[key].name, symbol_id=swap[key])
        return replace(node, symbol_id=_shifted(node.symbol_id, delta))

    out = _map_children(node, lambda c: _rewrite(c, delta, swap, into))
    sid = getattr(out, "symbol_id", None)
    if isinstance(sid, SymbolId):
        # `symbol_id` is not on `Expr` -- it belongs to the five binder kinds and to
        # `Ref`. Reaching it structurally rather than branching on those six types is
        # deliberate (see the module docstring): a seventh binder is then handled the day
        # it is written. The isinstance guard above is what makes this safe, and mypy
        # cannot see that a field it does not know about exists on this instance.
        out = replace(out, symbol_id=_shifted(sid, delta))  # type: ignore[call-arg]
    return out


# ---------------------------------------------------------------------------
# Abstraction: P(n)  ->  forall n : T . P(n)
# ---------------------------------------------------------------------------


def abstract(body: Expr, eigen: SymbolId, *, kind: str, var_type) -> Quantifier:
    """Bind ``eigen`` as the new outermost quantifier over ``body``.

    ``eigen`` must be a module-level symbol (``depth == 0``). Generalising over something
    that is already bound is meaningless — the name is not free to be quantified — and is
    refused rather than silently producing a shadowing binder.
    """
    if eigen.depth != 0:
        raise CaptureError(
            f"{eigen.name!r} is already bound at depth {eigen.depth}; only a "
            f"module-level name can be generalised"
        )
    new_binder = SymbolId(name=eigen.name, ordinal=0, depth=1)
    # One pass: every bound symbol descends a level, and the eigenvariable's references
    # become references to the binder now sitting above them. There is no collision
    # between the two, because everything shifted lands at depth >= 2.
    inner = _rewrite(body, +1, {eigen.canonical(): new_binder}, {})
    return Quantifier(
        kind=kind,
        var=eigen.name,
        var_type=var_type,
        symbol_id=new_binder,
        body=inner,
        span=body.span,
    )


# ---------------------------------------------------------------------------
# Instantiation: forall x : T . P(x)  ->  P(t)
# ---------------------------------------------------------------------------


def instantiate(quant: Quantifier, term: Expr) -> Expr:
    """Strip ``quant``'s binder and replace its variable with ``term``.

    Refuses when ``term`` mentions any bound name. Such a term is only meaningful
    relative to a binder that does not enclose the substitution site, so inserting it
    would capture — the classic unsoundness this whole module exists to avoid. The
    conservative refusal is safe; a wrong substitution is not.
    """
    if quant.symbol_id is None:
        raise CaptureError("the quantifier has no resolved binder symbol")
    for node in walk(term):
        sid = getattr(node, "symbol_id", None)
        if isinstance(sid, SymbolId) and sid.depth > 0:
            raise CaptureError(
                f"the instantiation term mentions {sid.name!r}, which is bound at "
                f"depth {sid.depth}; substituting it here would capture"
            )
    return _rewrite(quant.body, -1, {}, {quant.symbol_id.canonical(): term})


# ---------------------------------------------------------------------------
# Occurrence
# ---------------------------------------------------------------------------


def free_symbols(expr: Expr) -> set[str]:
    """Canonical ids of every module-level symbol referenced by ``expr``.

    Module-level means ``depth == 0``: not bound anywhere inside the expression, and so
    free in it. Used for the eigenvariable side condition, where the question is exactly
    "does this assumption constrain the variable we are about to generalise?".
    """
    out: set[str] = set()
    for node in walk(expr):
        if isinstance(node, Ref) and node.symbol_id is not None and node.symbol_id.depth == 0:
            out.add(node.symbol_id.canonical())
    return out


def occurs_free(expr: Expr, sid: SymbolId) -> bool:
    return sid.canonical() in free_symbols(expr)
