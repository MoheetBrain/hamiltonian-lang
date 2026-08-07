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
    ContinuityExpr,
    Declaration,
    DefineStmt,
    DerivativeExpr,
    DeriveStmt,
    DistExpr,
    Expr,
    GoalStmt,
    IndependenceExpr,
    Index,
    InferStmt,
    IntegralExpr,
    JointExpr,
    LawStmt,
    LimitExpr,
    Literal,
    LogicalOp,
    MembershipExpr,
    ModuleDecl,
    MomentExpr,
    ObjectiveStmt,
    ProbabilityExpr,
    ProvedStmt,
    ProveStmt,
    Quantifier,
    Ref,
    RelationExpr,
    RequireStmt,
    SetComprehension,
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
    # The three unit-interval kinds share a range and differ in what they are ABOUT, so
    # each gloss has to state the referent. Glossing all three as "a number between 0
    # and 1" would erase in prose exactly the distinction the type carries.
    "PValue": (
        "a p-value: the probability, computed under the null hypothesis, of data at "
        "least as extreme as those observed"
    ),
    "PosteriorProbability": (
        "a posterior probability: the probability of a hypothesis given the data and a "
        "stated prior"
    ),
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
            tag = f" Call this {st.label}." if st.label else ""
            return f"Assume that {self.expr(st.proposition)}.{tag}"
        if isinstance(st, RequireStmt):
            tag = f" Call this {st.label}." if st.label else ""
            return f"It is required that {self.expr(st.proposition)}.{tag}"
        if isinstance(st, ProveStmt):
            tag = f" Call this {st.label}." if st.label else ""
            return (
                f"It is claimed, and not yet proved, that "
                f"{self.expr(st.proposition)}.{tag}"
            )

        # -- V2 reasoning spine ------------------------------------------
        #
        # These are rendered rather than dropped. Omitting them left English claiming
        # `faithful=True` on a module whose entire argument it had discarded -- a
        # reading aid that silently loses the reasoning is worse than no reading aid,
        # and `backends/base.py` names that the worst failure mode in the codebase.
        #
        # The wording never asserts that a step holds. A derivation is described as
        # what was *claimed*, because the English backend does not know the verdict:
        # it renders the module, not the check.
        if isinstance(st, GoalStmt):
            return f"The goal {st.label} is to establish that {self.expr(st.proposition)}."

        if isinstance(st, DeriveStmt):
            premises = (
                " from " + " and ".join(st.premises) if st.premises else " from no premise"
            )
            args = (
                " with "
                + ", ".join(f"{a.role} = {self.expr(a.value)}" for a in st.rule_args)
                if st.rule_args
                else ""
            )
            rule = st.rule.replace("_", " ")
            return (
                f"Step {st.label}: applying {rule}{args}{premises} is claimed to give "
                f"{self.expr(st.conclusion)}."
            )

        if isinstance(st, ProvedStmt):
            return (
                f"The goal {st.goal} is claimed to follow from step {st.derivation}; "
                f"whether it does is decided by the checker, not by this claim."
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

        # -- V2 mathematical expression coverage (D-026) --------------------
        #
        # Controlled English can carry all eleven forms, and carrying them is the whole
        # point of this backend: it is the view a reader checks the encoding against.
        # Each clause names the construct explicitly rather than borrowing notation, so
        # "the expectation of X given Y" cannot be misread as "the expectation of X".

        if isinstance(e, MomentExpr):
            word = "expectation" if e.kind == "expectation" else "variance"
            return f"the {word} of {self.expr(e.body)}{self._given_clause(e.given)}"

        if isinstance(e, ProbabilityExpr):
            return (
                f"the probability that {self.expr(e.event)}"
                f"{self._given_clause(e.given)}"
            )

        if isinstance(e, JointExpr):
            parts = ", and ".join(self.expr(p) for p in e.parts)
            return f"the joint probability law of {parts}"

        if isinstance(e, IndependenceExpr):
            parts = ", and ".join(self.expr(p) for p in e.parts)
            return f"{parts} are independent{self._given_clause(e.given)}"

        if isinstance(e, MembershipExpr):
            return (
                f"{self.expr(e.element)} is a member of {self.expr(e.collection)}"
            )

        if isinstance(e, SetComprehension):
            t = e.var_type.render() if e.var_type else "unknown"
            return (
                f"the set of every {e.var} that is {_type_phrase(t)} such that "
                f"{self.expr(e.predicate)}"
            )

        if isinstance(e, LimitExpr):
            t = e.var_type.render() if e.var_type else "unknown"
            return (
                f"the limit of {self.expr(e.body)} as {e.var}, which is "
                f"{_type_phrase(t)}, approaches {self.expr(e.point)}"
            )

        if isinstance(e, DerivativeExpr):
            t = e.var_type.render() if e.var_type else "unknown"
            return (
                f"the derivative of {self.expr(e.body)} with respect to {e.var}, "
                f"which is {_type_phrase(t)}"
            )

        if isinstance(e, IntegralExpr):
            t = e.var_type.render() if e.var_type else "unknown"
            return (
                f"the definite integral of {self.expr(e.body)} with respect to "
                f"{e.var}, which is {_type_phrase(t)}, from {self.expr(e.lower)} to "
                f"{self.expr(e.upper)}"
            )

        if isinstance(e, ContinuityExpr):
            return (
                f"{self.expr(e.function)} is continuous on {self.expr(e.domain)}"
            )

        if isinstance(e, RelationExpr):
            # Deliberately three different sentences. Rendering all three as "is
            # related to" would erase in the view the very distinction the type system
            # was extended to make (D-026), and this view is what a reader audits.
            phrase = {
                "associated": (
                    f"{self.expr(e.left)} is statistically associated with "
                    f"{self.expr(e.right)}"
                ),
                "correlated": (
                    f"{self.expr(e.left)} is correlated with {self.expr(e.right)}"
                ),
                "causes": f"{self.expr(e.left)} causes {self.expr(e.right)}",
            }[e.relation]
            return phrase

        # A node with no clause above would otherwise be rendered as bland prose and
        # counted faithful -- the exact failure `backends/base.py` names as the worst
        # in this codebase. Declare it instead.
        self.drop(
            f"expression {type(e).__name__}",
            "no controlled-English clause is defined for this construct, so the "
            "sentence would omit it silently",
            e.span.line,
        )
        return "an unrepresented expression"

    def _given_clause(self, given: list[Expr]) -> str:
        if not given:
            return ""
        return " given " + ", and ".join(self.expr(g) for g in given)


def to_english(module, symbols=None):
    return EnglishBackend(module, symbols).run()
