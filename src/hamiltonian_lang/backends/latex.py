"""LaTeX rendering.

A *presentation* view. It is deliberately lossy in a specific way that the backend
declares: LaTeX has no way to carry a symbol's declared type, a role label, or a proof
obligation, so those become prose annotations or are dropped with a report. That
asymmetry is itself evidence for the project thesis and is worth surfacing rather than
hiding.
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
from .base import Backend

__all__ = ["LatexBackend", "to_latex"]

_GREEK = {
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota",
    "kappa", "lambda", "mu", "nu", "xi", "pi", "rho", "sigma", "tau", "upsilon",
    "phi", "chi", "psi", "omega",
}

_FAMILY = {
    "Normal": r"\mathcal{N}",
    "NormalVector": r"\mathcal{N}",
    "Beta": r"\mathrm{Beta}",
    "Binomial": r"\mathrm{Binomial}",
    "Bernoulli": r"\mathrm{Bernoulli}",
    "Poisson": r"\mathrm{Poisson}",
    "Exponential": r"\mathrm{Exponential}",
    "Gamma": r"\mathrm{Gamma}",
    "Uniform": r"\mathrm{Uniform}",
    "Cauchy": r"\mathrm{Cauchy}",
    "StudentT": r"\mathrm{Student}\text{-}t",
    "Dirichlet": r"\mathrm{Dirichlet}",
    "Categorical": r"\mathrm{Categorical}",
    "LogNormal": r"\mathrm{LogNormal}",
    "HalfNormal": r"\mathrm{HalfNormal}",
    "InverseGamma": r"\mathrm{InvGamma}",
}

_REL = {"<=": r"\leq", ">=": r"\geq", "!=": r"\neq", "=": "=", "<": "<", ">": ">"}


def _name(n: str) -> str:
    base, _, sub = n.partition("_")
    head = f"\\{base}" if base in _GREEK else (
        base if len(base) == 1 else rf"\mathrm{{{base}}}"
    )
    return f"{head}_{{{sub}}}" if sub else head


class LatexBackend(Backend):
    target = "latex"
    limitations = (
        "LaTeX carries presentation, not semantics: declared types, parameter role "
        "labels, scope identity and proof obligations have no LaTeX encoding.",
        "Rendering is one-way. LaTeX produced here cannot be parsed back into an "
        "equivalent Hamiltonian object.",
    )

    def emit(self) -> str:
        lines = [rf"% module {self.module.name}", r"\begin{align}"]
        body: list[str] = []
        for st in self.module.statements:
            rendered = self.statement(st)
            if rendered:
                body.append(rendered)
        lines.append(" \\\\\n".join(body))
        lines.append(r"\end{align}")
        return "\n".join(lines)

    def statement(self, st: Statement) -> str:
        if isinstance(st, ModuleDecl):
            return ""

        if isinstance(st, Declaration):
            t = st.declared_type
            self.weaken(
                f"{st.kind} {st.name}",
                f"declared type {t.render() if t else '?'} rendered as set membership; "
                f"the declaration role ({st.kind}) has no LaTeX encoding",
                st.span.line,
            )
            setname = _set_of(t.render() if t else "?")
            base = rf"{_name(st.name)} &\in {setname}"
            if st.value is not None:
                base += rf",\quad {_name(st.name)} = {self.expr(st.value)}"
            return base

        if isinstance(st, DefineStmt):
            params = ", ".join(_name(p) for p, _ in st.params)
            head = f"{_name(st.name)}({params})" if params else _name(st.name)
            return rf"{head} &:= {self.expr(st.body)}"

        if isinstance(st, LawStmt):
            target = _name(st.target)
            if st.given:
                target += r" \mid " + ", ".join(_name(g.name) for g in st.given)
            dist = self.expr(st.distribution) if st.distribution else "?"
            return rf"{target} &\sim {dist}"

        if isinstance(st, RequireStmt):
            return rf"&{self.expr(st.proposition)}"
        if isinstance(st, AssumeStmt):
            return rf"&\text{{assume }} {self.expr(st.proposition)}"
        if isinstance(st, ProveStmt):
            return rf"&\text{{claim: }} {self.expr(st.proposition)}"

        if isinstance(st, ObjectiveStmt):
            op = r"\min" if st.direction == "minimise" else r"\max"
            return rf"&{op}\; {self.expr(st.expression)}"

        if isinstance(st, SolveStmt):
            return (
                r"&\text{solve for } "
                + ", ".join(_name(t.name) for t in st.targets)
            )

        if isinstance(st, InferStmt):
            names = ", ".join(_name(t.name) for t in st.targets)
            if st.query == "posterior":
                return rf"&p({names} \mid \text{{data}})"
            return rf"&\mathrm{{{st.query}}}[{names}]"

        if isinstance(st, CheckStmt):
            if st.check_kind == "dimension" and st.subject is not None:
                dim = st.subject.type_.render() if st.subject.type_ else "?"
                return rf"&[{self.expr(st.subject)}] = \mathrm{{{_escape(dim)}}}"
            return rf"&{self.expr(st.subject)}" if st.subject else ""

        if isinstance(st, ConceptDecl):
            self.drop(
                f"concept {st.name}",
                "concept families have no LaTeX encoding; the invariants, transforms "
                "and counterexamples are not representable",
                st.span.line,
            )
            return ""

        return ""

    def expr(self, e: Expr) -> str:
        if isinstance(e, Literal):
            if isinstance(e.value, bool):
                return r"\top" if e.value else r"\bot"
            return e.raw or str(e.value)

        if isinstance(e, Ref):
            return _name(e.name)

        if isinstance(e, UnaryOp):
            if e.op == "not":
                return rf"\lnot {self.expr(e.operand)}"
            return rf"-{self.expr(e.operand)}"

        if isinstance(e, BinOp):
            if e.op == "/":
                return rf"\frac{{{self.expr(e.left)}}}{{{self.expr(e.right)}}}"
            if e.op == "^":
                return rf"{self.expr(e.left)}^{{{self.expr(e.right)}}}"
            if e.op == "*":
                return rf"{self.expr(e.left)} \cdot {self.expr(e.right)}"
            if e.op == "@":
                return rf"{self.expr(e.left)} {self.expr(e.right)}"
            return f"{self.expr(e.left)} {e.op} {self.expr(e.right)}"

        if isinstance(e, Comparison):
            return f"{self.expr(e.left)} {_REL.get(e.op, e.op)} {self.expr(e.right)}"

        if isinstance(e, LogicalOp):
            sym = {"and": r"\land", "or": r"\lor", "implies": r"\Rightarrow",
                   "iff": r"\Leftrightarrow"}[e.op]
            return f"{self.expr(e.left)} {sym} {self.expr(e.right)}"

        if isinstance(e, Call):
            args = ", ".join(self.expr(a) for a in e.args)
            if e.callee in ("exp", "log", "sin", "cos", "tan"):
                return rf"\{e.callee}\left({args}\right)"
            if e.callee == "sqrt":
                return rf"\sqrt{{{args}}}"
            return rf"\mathrm{{{e.callee}}}\left({args}\right)"

        if isinstance(e, Index):
            idx = ", ".join(self.expr(i) for i in e.indices)
            return f"{self.expr(e.base)}_{{{idx}}}"

        if isinstance(e, DistExpr):
            head = _FAMILY.get(e.family, rf"\mathrm{{{_escape(e.family)}}}")
            if not e.args:
                return head
            # LaTeX convention is positional. The role labels are the semantic content
            # and they are lost here; declare it once per law.
            self.weaken(
                f"{e.family} argument roles",
                "role labels ("
                + ", ".join(a.role for a in e.args)
                + ") become positional in LaTeX; the reader must recover them from "
                "convention",
                e.span.line,
            )
            args = ", ".join(self.expr(a.value) for a in e.args)
            return rf"{head}\left({args}\right)"

        if isinstance(e, Quantifier):
            q = {"forall": r"\forall", "exists": r"\exists",
                 "exists_unique": r"\exists!"}[e.kind]
            t = _set_of(e.var_type.render()) if e.var_type else "?"
            return rf"{q} {_name(e.var)} \in {t} \,.\, {self.expr(e.body)}"

        return r"\text{?}"


_SETS = {
    "Real": r"\mathbb{R}",
    "Rational": r"\mathbb{Q}",
    "Integer": r"\mathbb{Z}",
    "Natural": r"\mathbb{N}",
    "PositiveReal": r"\mathbb{R}_{>0}",
    "NonNegativeReal": r"\mathbb{R}_{\geq 0}",
    "Probability": r"[0, 1]",
    "Bool": r"\{\top, \bot\}",
}


def _set_of(rendered: str) -> str:
    if rendered in _SETS:
        return _SETS[rendered]
    if rendered.startswith("Vector["):
        return r"\mathbb{R}^{n}"
    if rendered.startswith("Matrix["):
        return r"\mathbb{R}^{m \times n}"
    if rendered.startswith("Quantity["):
        return r"\mathbb{R}"
    return rf"\mathrm{{{_escape(rendered)}}}"


def _escape(s: str) -> str:
    return s.replace("_", r"\_").replace("^", r"\^{}").replace("[", "(").replace("]", ")")


def to_latex(module, symbols=None):
    return LatexBackend(module, symbols).run()
