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

#: Associativity as the *parser* implements it, not as it is usually assumed.
#: ``parse_implication`` and ``parse_power`` recurse on the right, so ``=>``, ``<=>``
#: and ``^`` are right-associative; ``parse_comparison`` rejects chaining (HML-P230), so
#: comparisons are non-associative.
#:
#: This table is load-bearing. Parenthesising only the right operand of ``+ - * /`` --
#: which is what this module did until the F3 round-trip gate exercised the other cases --
#: prints ``(a ^ b) ^ c`` as ``a ^ b ^ c``, which reads back as ``a ^ (b ^ c)``: a
#: silently different object with a different canonical hash. The same held for
#: ``(p => q) => r``.
_ASSOCIATIVITY = {
    "iff": "right", "implies": "right",
    "or": "left", "and": "left",
    "=": "none", "!=": "none", "<": "none", "<=": "none", ">": "none", ">=": "none",
    "+": "left", "-": "left",
    "*": "left", "/": "left", "@": "left",
    "^": "right",
}

_UNARY_PREC = 7
#: Postfix indexing binds to a *primary*, so an indexed base that is anything else needs
#: parentheses: ``(a + b)[i]``, never ``a + b[i]``.
_PRIMARY_PREC = 10
#: ``parse_check`` reads a dimension subject at the additive level, because the ``=``
#: that may follow introduces a dimension rather than an equation.
_ADDITIVE_PREC = 5


def _prec(e: Expr) -> int:
    if isinstance(e, (BinOp, Comparison, LogicalOp)):
        return _PRECEDENCE.get(e.op, 0)
    if isinstance(e, UnaryOp):
        return _UNARY_PREC
    if isinstance(e, Quantifier):
        return 0
    return _PRIMARY_PREC


def _wrap(child: Expr, parent_prec: int, assoc: str = "left", side: str = "left") -> str:
    """Parenthesise ``child`` exactly when omitting the brackets would re-read wrongly.

    A child that binds looser than its parent always needs brackets. At *equal*
    precedence it needs them on whichever side the operator does not associate towards,
    and on both sides when the operator does not associate at all.
    """
    s = render_expr(child)
    cp = _prec(child)
    if cp < parent_prec or (cp == parent_prec and assoc != side):
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
        operand = _wrap(e.operand, _UNARY_PREC, "right", "right")
        if e.op == "not":
            return f"not {operand}"
        return f"-{operand}"

    if isinstance(e, (BinOp, Comparison, LogicalOp)):
        op = e.op
        p = _PRECEDENCE.get(op, 0)
        assoc = _ASSOCIATIVITY.get(op, "left")
        symbol = {"implies": "=>", "iff": "<=>"}.get(op, op)
        left = _wrap(e.left, p, assoc, "left")
        right = _wrap(e.right, p, assoc, "right")
        if op in ("and", "or"):
            return f"{left} {op} {right}"
        return f"{left} {symbol} {right}"

    if isinstance(e, Call):
        return f"{e.callee}({', '.join(render_expr(a) for a in e.args)})"

    if isinstance(e, Index):
        base = _wrap(e.base, _PRIMARY_PREC)
        return f"{base}[{', '.join(render_expr(i) for i in e.indices)}]"

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
        # The formal's declared type is part of the definition, not decoration. Dropping
        # it renders `def f(x) : Real := x * 2`, which re-parses with an untyped formal
        # and then fails to type-check (HML-T431) -- a view that silently loses meaning,
        # which is the failure mode this project treats as the worst one. The ConceptDecl
        # branch below already renders member formals this way.
        params = (
            "("
            + ", ".join(n if t is None else f"{n} : {t.render()}" for n, t in st.params)
            + ")"
            if st.params
            else ""
        )
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
        if st.check_kind == "dimension":
            subject = (
                "?" if st.subject is None else _wrap(st.subject, _ADDITIVE_PREC)
            )
            base = f"check dimension {subject}"
            if st.expected:
                base += f" = {st.expected}"
            return base
        subject = "?" if st.subject is None else render_expr(st.subject)
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
