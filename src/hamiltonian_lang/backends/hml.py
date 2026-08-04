"""Render a Module back to canonical HML-L1 source.

This is the round-trip backend: ``parse(render(parse(s))) == parse(s)`` up to
canonical form. It is also the pretty-printer, and it always emits ASCII.
"""

from __future__ import annotations

from ..ast.nodes import (
    AssumeStmt,
    BinOp,
    Call,
    CheckStmt,
    Comparison,
    ConceptDecl,
    Declaration,
    DefineStmt,
    DistExpr,
    Expr,
    Index,
    InferStmt,
    LawStmt,
    Literal,
    LogicalOp,
    Module,
    ModuleDecl,
    ObjectiveStmt,
    ProveStmt,
    Quantifier,
    Ref,
    RequireStmt,
    SolveStmt,
    Statement,
    UnaryOp,
)

__all__ = ["render_module", "render_statement", "render_expr"]

_PRECEDENCE = {
    "iff": 1, "implies": 1,
    "or": 2, "and": 3,
    "=": 4, "!=": 4, "<": 4, "<=": 4, ">": 4, ">=": 4,
    "+": 5, "-": 5,
    "*": 6, "/": 6, "@": 6,
    "^": 8,
}


def _prec(e: Expr) -> int:
    if isinstance(e, (BinOp, Comparison, LogicalOp)):
        return _PRECEDENCE.get(e.op, 0)
    if isinstance(e, UnaryOp):
        return 7
    if isinstance(e, Quantifier):
        return 0
    return 10


def _wrap(child: Expr, parent_prec: int, *, right: bool = False) -> str:
    s = render_expr(child)
    cp = _prec(child)
    if cp < parent_prec or (right and cp == parent_prec and cp in (5, 6)):
        return f"({s})"
    return s


def render_expr(e: Expr) -> str:
    if isinstance(e, Literal):
        if isinstance(e.value, bool):
            return "true" if e.value else "false"
        return e.raw or str(e.value)

    if isinstance(e, Ref):
        return e.name

    if isinstance(e, UnaryOp):
        if e.op == "not":
            return f"not {_wrap(e.operand, 7)}"
        return f"-{_wrap(e.operand, 7)}"

    if isinstance(e, (BinOp, Comparison, LogicalOp)):
        op = e.op
        p = _PRECEDENCE.get(op, 0)
        symbol = {"implies": "=>", "iff": "<=>"}.get(op, op)
        left = _wrap(e.left, p)
        right = _wrap(e.right, p, right=True)
        if op in ("and", "or"):
            return f"{left} {op} {right}"
        return f"{left} {symbol} {right}"

    if isinstance(e, Call):
        return f"{e.callee}({', '.join(render_expr(a) for a in e.args)})"

    if isinstance(e, Index):
        return f"{render_expr(e.base)}[{', '.join(render_expr(i) for i in e.indices)}]"

    if isinstance(e, DistExpr):
        if not e.args:
            return e.family
        args = ", ".join(f"{a.role} := {render_expr(a.value)}" for a in e.args)
        return f"{e.family}({args})"

    if isinstance(e, Quantifier):
        kw = "exists unique" if e.kind == "exists_unique" else e.kind
        t = e.var_type.render() if e.var_type is not None else "?"
        return f"{kw} {e.var} : {t} . {render_expr(e.body)}"

    return f"<{type(e).__name__}>"


def render_statement(st: Statement) -> str:
    if isinstance(st, ModuleDecl):
        return f"module {st.name}"

    if isinstance(st, Declaration):
        t = st.declared_type.render() if st.declared_type is not None else "?"
        base = f"{st.kind} {st.name} : {t}"
        if st.value is not None:
            base += f" = {render_expr(st.value)}"
        return base

    if isinstance(st, DefineStmt):
        params = f"({', '.join(p for p, _ in st.params)})" if st.params else ""
        ann = f" : {st.declared_type.render()}" if st.declared_type is not None else ""
        return f"def {st.name}{params}{ann} := {render_expr(st.body)}"

    if isinstance(st, LawStmt):
        given = f" | {' '.join(g.name for g in st.given)}" if st.given else ""
        dist = render_expr(st.distribution) if st.distribution is not None else "?"
        return f"{st.role} {st.target}{given} ~ {dist}"

    if isinstance(st, AssumeStmt):
        return f"assume {render_expr(st.proposition)}"
    if isinstance(st, RequireStmt):
        return f"require {render_expr(st.proposition)}"
    if isinstance(st, ProveStmt):
        return f"prove {render_expr(st.proposition)}"

    if isinstance(st, ObjectiveStmt):
        return f"{st.direction} {render_expr(st.expression)}"

    if isinstance(st, SolveStmt):
        return f"solve {' '.join(t.name for t in st.targets)}"

    if isinstance(st, InferStmt):
        return f"infer {st.query} {' '.join(t.name for t in st.targets)}"

    if isinstance(st, CheckStmt):
        subject = "?" if st.subject is None else render_expr(st.subject)
        if st.check_kind == "dimension":
            base = f"check dimension {subject}"
            if st.expected:
                base += f" = {st.expected}"
            return base
        return f"check {subject}"

    if isinstance(st, ConceptDecl):
        lines = [f"concept {st.name}"]
        if st.extends:
            lines[0] += " extends " + ", ".join(st.extends)
        for m in st.members:
            params = (
                "("
                + ", ".join(
                    n if t is None else f"{n} : {t.render()}" for n, t in m.params
                )
                + ")"
                if m.params
                else ""
            )
            ann = f" : {m.declared_type.render()}" if m.declared_type is not None else ""
            body = f" := {render_expr(m.body)}" if m.body is not None else ""
            lines.append(f"    {m.kind} {m.name}{params}{ann}{body}")
        lines.append("end")
        return "\n".join(lines)

    return f"# <unrenderable {type(st).__name__}>"


def render_module(module: Module) -> str:
    lines: list[str] = []
    has_module_decl = any(isinstance(s, ModuleDecl) for s in module.statements)
    if not has_module_decl:
        lines.append(f"module {module.name}")
        lines.append("")
    prev: Statement | None = None
    for st in module.statements:
        if prev is not None and (
            isinstance(st, ConceptDecl)
            or isinstance(prev, (ModuleDecl, ConceptDecl))
            or type(st) is not type(prev)
        ):
            lines.append("")
        lines.append(render_statement(st))
        prev = st
    return "\n".join(lines).strip() + "\n"
