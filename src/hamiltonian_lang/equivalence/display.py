"""A small, fully-parenthesised expression printer for evidence strings.

Deliberately independent of :mod:`hamiltonian_lang.backends.hml`. Evidence has one
job -- to let a human check the scorer's reasoning later -- and a printer that
drops parentheses cannot do that job. The motivating defect is concrete: a
renderer in this repository once printed ``(a^b)^c`` as ``a^b^c``, which reads
back as ``a^(b^c)``. This printer never elides a grouping, so a witness string
can be trusted to say which tree was compared.
"""

from __future__ import annotations

from ..ast.nodes import (
    BinOp,
    Call,
    Comparison,
    DistExpr,
    Expr,
    Index,
    Literal,
    LogicalOp,
    Quantifier,
    Ref,
    UnaryOp,
)

__all__ = ["show"]


def show(e: Expr | None) -> str:
    """Render ``e`` with every grouping made explicit."""
    if e is None:
        return "<none>"

    if isinstance(e, Literal):
        return e.raw or repr(e.value)

    if isinstance(e, Ref):
        return e.name

    if isinstance(e, UnaryOp):
        return f"({e.op} {show(e.operand)})"

    if isinstance(e, BinOp):
        return f"({show(e.left)} {e.op} {show(e.right)})"

    if isinstance(e, Comparison):
        return f"({show(e.left)} {e.op} {show(e.right)})"

    if isinstance(e, LogicalOp):
        return f"({show(e.left)} {e.op} {show(e.right)})"

    if isinstance(e, Call):
        return f"{e.callee}({', '.join(show(a) for a in e.args)})"

    if isinstance(e, Index):
        return f"{show(e.base)}[{', '.join(show(i) for i in e.indices)}]"

    if isinstance(e, DistExpr):
        args = ", ".join(f"{a.role} := {show(a.value)}" for a in sorted(e.args, key=lambda x: x.role))
        return f"{e.family}({args})"

    if isinstance(e, Quantifier):
        t = e.var_type.render() if e.var_type is not None else "?"
        return f"({e.kind} {e.var} : {t} . {show(e.body)})"

    return f"<{type(e).__name__}>"
