"""Controlled-English rendering.

Not natural prose. A *controlled* language: fixed clause order, one clause per
semantic relation, explicit role marking, no anaphora, no hedging. Every sentence is
generated from exactly one AST node, so the mapping back to structure is
unambiguous — which is the property ordinary mathematical English lacks.

Design borrowings (documented in docs/design/SEMANTIC_MORPHOLOGY.md):
* Attempto-style fixed clause order and explicit determiners;
* explicit role marking in the manner of case-marking languages ("in the role of");
* no pronouns, so binding never has to be recovered from discourse.
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

__all__ = ["EnglishBackend", "to_english"]

_TYPE_PHRASE = {
    "Real": "a real number",
    "Rational": "a rational number",
    "Integer": "an integer",
    "Natural": "a natural number",
    "PositiveReal": "a strictly positive real number",
    "NonNegativeReal": "a non-negative real number",
    "Probability": "a real number in the closed interval from 0 to 1",
    "Bool": "a truth value",
    "Proposition": "a proposition",
}

_DECL_PHRASE = {
    "var": "a variable",
    "param": "a parameter",
    "const": "a constant",
    "obs": "an observed quantity",
    "index": "an index",
    "rv": "a random variable",
}

_REL_PHRASE = {
    "=": "is equal to",
    "!=": "is not equal to",
    "<": "is strictly less than",
    "<=": "is less than or equal to",
    ">": "is strictly greater than",
    ">=": "is greater than or equal to",
}

_OP_PHRASE = {"+": "plus", "-": "minus", "*": "times", "/": "divided by",
              "@": "matrix-multiplied by", "^": "raised to the power"}


def _type_phrase(rendered: str) -> str:
    if rendered in _TYPE_PHRASE:
        return _TYPE_PHRASE[rendered]
    if rendered.startswith("Vector["):
        inner = rendered[len("Vector["):-1]
        elem, _, length = inner.partition(", ")
        return f"a vector of length {length} whose elements are {_type_phrase(elem)}"
    if rendered.startswith("Matrix["):
        inner = rendered[len("Matrix["):-1]
        parts = [p.strip() for p in inner.split(",")]
        if len(parts) == 3:
            return (
                f"a matrix with {parts[1]} rows and {parts[2]} columns whose entries "
                f"are {_type_phrase(parts[0])}"
            )
        return "a matrix"
    if rendered.startswith("Quantity["):
        return f"a physical quantity with dimension {rendered[len('Quantity['):-1]}"
    if rendered.startswith("RandomVariable["):
        return (
            "a random variable whose outcomes are "
            f"{_type_phrase(rendered[len('RandomVariable['):-1])}"
        )
    if rendered.startswith("Distribution["):
        return (
            "a probability distribution supported on values that are "
            f"{_type_phrase(rendered[len('Distribution['):-1])}"
        )
    if rendered.startswith("Function["):
        return f"a function, {rendered}"
    if rendered.startswith("Set["):
        return f"a set of elements that are {_type_phrase(rendered[len('Set['):-1])}"
    return f"of type {rendered}"


class EnglishBackend(Backend):
    target = "controlled-english"
    limitations = (
        "Controlled English is generated from the semantic graph and is one-way: it "
        "is not parsed back. It is a reading aid, not a source format.",
    )

    def emit(self) -> str:
        lines = [f"Module {self.module.name}.", ""]
        for st in self.module.statements:
            s = self.statement(st)
            if s:
                lines.append(s)
        return "\n".join(lines).rstrip() + "\n"

    def statement(self, st: Statement) -> str:
        if isinstance(st, ModuleDecl):
            return ""

        if isinstance(st, Declaration):
            t = st.declared_type.render() if st.declared_type else "of unknown type"
            phrase = _DECL_PHRASE.get(st.kind, "a symbol")
            base = f"Let {st.name} be {phrase} that is {_type_phrase(t)}."
            if st.value is not None:
                verb = "is observed to equal" if st.kind == "obs" else "equals"
                base += f" {st.name} {verb} {self.expr(st.value)}."
            return base

        if isinstance(st, DefineStmt):
            if st.params:
                params = " and ".join(p for p, _ in st.params)
                return f"Define {st.name} of {params} to be {self.expr(st.body)}."
            return f"Define {st.name} to be {self.expr(st.body)}."

        if isinstance(st, LawStmt):
            role = {
                "prior": "The prior probability law of",
                "likelihood": "The likelihood of",
                "law": "The probability law of",
            }[st.role]
            cond = ""
            if st.given:
                cond = " given " + " and ".join(g.name for g in st.given)
            d = st.distribution
            sentence = f"{role} {st.target}{cond} is {self._family(d)}."
            if d is not None and d.args:
                clauses = [
                    f"{self.expr(a.value)} in the role of {a.role.replace('_', ' ')}"
                    for a in d.args
                ]
                sentence += " It takes " + ", and ".join(clauses) + "."
            return sentence

        if isinstance(st, AssumeStmt):
            return f"Assume that {self.expr(st.proposition)}."
        if isinstance(st, RequireStmt):
            return f"It is required that {self.expr(st.proposition)}."
        if isinstance(st, ProveStmt):
            return (
                f"It is claimed, and not yet proved, that "
                f"{self.expr(st.proposition)}."
            )

        if isinstance(st, ObjectiveStmt):
            word = "minimise" if st.direction == "minimise" else "maximise"
            return f"The objective is to {word} {self.expr(st.expression)}."

        if isinstance(st, SolveStmt):
            return "Solve for " + " and ".join(t.name for t in st.targets) + "."

        if isinstance(st, InferStmt):
            names = " and ".join(t.name for t in st.targets)
            phrase = {
                "posterior": f"Infer the posterior probability law of {names}",
                "expectation": f"Infer the expectation of {names}",
                "variance": f"Infer the variance of {names}",
                "mle": f"Infer the maximum-likelihood estimate of {names}",
                "map": f"Infer the maximum-a-posteriori estimate of {names}",
            }[st.query]
            return phrase + "."

        if isinstance(st, CheckStmt):
            if st.check_kind == "dimension" and st.subject is not None:
                dim = st.subject.type_.render() if st.subject.type_ else "unknown"
                return (
                    f"Check that the physical dimension of {self.expr(st.subject)} "
                    f"is {dim}."
                )
            return f"Check that {self.expr(st.subject)}." if st.subject else ""

        if isinstance(st, ConceptDecl):
            lines = [f"Define the concept {st.name}."]
            if st.extends:
                lines.append(
                    f"{st.name} extends " + " and ".join(st.extends) + "."
                )
            for m in st.members:
                if m.kind == "parameter":
                    t = m.declared_type.render() if m.declared_type else "unknown"
                    lines.append(
                        f"{st.name} has a parameter {m.name} that is {_type_phrase(t)}."
                    )
                elif m.kind == "transform":
                    args = " and ".join(m.param_names())
                    lines.append(
                        f"{st.name} defines a transform {m.name} of {args}, "
                        f"equal to {self.expr(m.body)}."
                        if m.body is not None
                        else f"{st.name} declares a transform {m.name}."
                    )
                elif m.kind == "invariant":
                    lines.append(
                        f"{st.name} has the invariant {m.name}: "
                        f"{self.expr(m.body)}."
                        if m.body is not None
                        else f"{st.name} declares an invariant {m.name}."
                    )
                elif m.kind == "counterexample":
                    lines.append(
                        f"{m.name} is a counterexample to {st.name}"
                        + (f", because {self.expr(m.body)}." if m.body else ".")
                    )
                else:
                    lines.append(
                        f"{st.name} has {m.kind} {m.name}"
                        + (f", equal to {self.expr(m.body)}." if m.body else ".")
                    )
            return " ".join(lines)

        return ""

    def _family(self, d: DistExpr | None) -> str:
        if d is None:
            return "unspecified"
        vowel = d.family[0] in "AEIOU"
        return f"{'an' if vowel else 'a'} {d.family} distribution"

    def expr(self, e: Expr) -> str:
        if isinstance(e, Literal):
            if isinstance(e.value, bool):
                return "true" if e.value else "false"
            return e.raw or str(e.value)

        if isinstance(e, Ref):
            return e.name

        if isinstance(e, UnaryOp):
            if e.op == "not":
                return f"it is not the case that {self.expr(e.operand)}"
            return f"the negation of {self.expr(e.operand)}"

        if isinstance(e, BinOp):
            phrase = _OP_PHRASE.get(e.op, e.op)
            if e.op == "^":
                return f"{self.expr(e.left)} raised to the power {self.expr(e.right)}"
            return f"{self.expr(e.left)} {phrase} {self.expr(e.right)}"

        if isinstance(e, Comparison):
            return (
                f"{self.expr(e.left)} {_REL_PHRASE.get(e.op, e.op)} "
                f"{self.expr(e.right)}"
            )

        if isinstance(e, LogicalOp):
            if e.op == "implies":
                return f"if {self.expr(e.left)} then {self.expr(e.right)}"
            if e.op == "iff":
                return (
                    f"{self.expr(e.left)} if and only if {self.expr(e.right)}"
                )
            return f"{self.expr(e.left)} {e.op} {self.expr(e.right)}"

        if isinstance(e, Call):
            args = " and ".join(self.expr(a) for a in e.args)
            return f"{e.callee} of {args}"

        if isinstance(e, Index):
            idx = " and ".join(self.expr(i) for i in e.indices)
            return f"the entry of {self.expr(e.base)} at index {idx}"

        if isinstance(e, DistExpr):
            base = self._family(e)
            if not e.args:
                return base
            roles = ", and ".join(
                f"{self.expr(a.value)} in the role of {a.role.replace('_', ' ')}"
                for a in e.args
            )
            return f"{base} taking {roles}"

        if isinstance(e, Quantifier):
            t = e.var_type.render() if e.var_type else "unknown"
            head = {
                "forall": f"for every {e.var} that is {_type_phrase(t)}",
                "exists": f"there exists at least one {e.var} that is {_type_phrase(t)}",
                "exists_unique": (
                    f"there exists exactly one {e.var} that is {_type_phrase(t)}"
                ),
            }[e.kind]
            return f"{head}, {self.expr(e.body)}"

        return "an unrepresented expression"


def to_english(module, symbols=None):
    return EnglishBackend(module, symbols).run()
