"""Recursive-descent parser for HML-L1.

The grammar is line-oriented and LL(1) at the statement level: the leading keyword
determines the statement kind with zero lookahead. Expression parsing uses standard
precedence climbing.

Error strategy: a parse error records a diagnostic and skips to the next NEWLINE, so a
single bad line does not cascade. This matters for the repair-loop benchmark (H4),
where the model gets one diagnostic per genuine mistake rather than a cascade.
"""

from __future__ import annotations

from fractions import Fraction

from ..ast.nodes import (
    Arg,
    AssumeStmt,
    BinOp,
    CheckStmt,
    Comparison,
    ConceptDecl,
    ConceptMember,
    Declaration,
    DeclKind,
    DefineStmt,
    DeriveStmt,
    DistExpr,
    Expr,
    GoalStmt,
    Index,
    InferStmt,
    LawStmt,
    Literal,
    LogicalOp,
    Module,
    ModuleDecl,
    ObjectiveStmt,
    ProvedStmt,
    ProveStmt,
    Quantifier,
    Ref,
    RequireStmt,
    RuleArg,
    SolveStmt,
    Span,
    Statement,
    UnaryOp,
)
from ..diagnostics import DiagnosticBag
from ..lexer import Token, TokenKind, tokenize
from ..types import (
    BASE_DIMENSIONS,
    ConceptType,
    Dimension,
    DistributionType,
    FunctionType,
    MatrixType,
    PredicateType,
    PropositionType,
    QuantityType,
    RandomVariableType,
    SetType,
    TensorType,
    Type,
    VectorType,
    is_dimension_variable,
    parse_scalar_name,
)

__all__ = ["Parser", "parse", "ParseAbort"]

_DECL_KEYWORDS = {
    "var": DeclKind.VAR,
    "param": DeclKind.PARAM,
    "const": DeclKind.CONST,
    "obs": DeclKind.OBS,
    "index": DeclKind.INDEX,
    "rv": DeclKind.RANDOM,
}

_INFER_QUERIES = {"posterior", "expectation", "variance", "mle", "map"}

_COMPARISONS = {"=", "!=", "<", "<=", ">", ">="}

_CONCEPT_MEMBER_KEYWORDS = {
    "parameter", "transform", "invariant", "property", "example", "counterexample",
}


class ParseAbort(Exception):
    """Internal control flow: abandon the current line."""


#: Maximum nesting depth for expressions. Recursive descent recurses once per level, so
#: without a bound a degenerate generation -- `((((( ... ` repeated a few hundred times --
#: raises RecursionError and crashes the process. A generated encoding that is truncated
#: mid-expression can reach this, so the parser must reject it with a diagnostic rather
#: than die.
#:
#: The bound is MEASURED, not guessed. Each nesting level costs ~12.2 Python stack frames
#: (parse_expr -> implication -> disjunction -> ... -> primary -> parse_expr), and the
#: default recursion limit of 1000 breaks at depth 82. 50 leaves roughly a 40% margin for
#: the frames already on the stack when parsing begins, and for statement-level nesting
#: above the expression. Re-measure this if the expression grammar gains levels.
MAX_EXPR_DEPTH = 50


class Parser:
    def __init__(self, tokens: list[Token], diags: DiagnosticBag, file: str = "<input>") -> None:
        self.toks = tokens
        self.k = 0
        self.diags = diags
        self.file = file
        self._depth = 0

    # -- token helpers ----------------------------------------------------
    @property
    def cur(self) -> Token:
        return self.toks[min(self.k, len(self.toks) - 1)]

    def peek(self, n: int = 1) -> Token:
        return self.toks[min(self.k + n, len(self.toks) - 1)]

    def next(self) -> Token:
        t = self.cur
        if self.k < len(self.toks) - 1:
            self.k += 1
        return t

    def at_end(self) -> bool:
        return self.cur.kind is TokenKind.EOF

    def accept_op(self, *ops: str) -> Token | None:
        if self.cur.is_op(*ops):
            return self.next()
        return None

    def accept_kw(self, *names: str) -> Token | None:
        if self.cur.is_kw(*names):
            return self.next()
        return None

    def expect_op(self, op: str, ctx: str) -> Token:
        if self.cur.is_op(op):
            return self.next()
        self._err("HML-P201", f"expected {op!r} {ctx}", found=self._describe(self.cur))
        raise ParseAbort

    def expect_ident(self, ctx: str) -> Token:
        if self.cur.kind is TokenKind.IDENT:
            return self.next()
        # A keyword where a name is expected is a common and confusing mistake.
        if self.cur.kind is TokenKind.KEYWORD:
            self._err(
                "HML-P202",
                f"{self.cur.value!r} is a reserved keyword and cannot be used as a name {ctx}",
                found=self._describe(self.cur),
                correction=f"rename the symbol, e.g. {self.cur.value}_",
            )
            raise ParseAbort
        self._err("HML-P203", f"expected an identifier {ctx}", found=self._describe(self.cur))
        raise ParseAbort

    def _describe(self, t: Token) -> str:
        if t.kind is TokenKind.EOF:
            return "end of input"
        if t.kind is TokenKind.NEWLINE:
            return "end of line"
        return repr(t.value)

    def _err(self, code: str, msg: str, span: Span | None = None, **kw) -> None:
        self.diags.error(code, msg, span or self.cur.span, **kw)

    def skip_line(self) -> None:
        while self.cur.kind not in (TokenKind.NEWLINE, TokenKind.EOF):
            self.next()
        if self.cur.kind is TokenKind.NEWLINE:
            self.next()

    def end_line(self, ctx: str) -> None:
        if self.cur.kind is TokenKind.NEWLINE:
            self.next()
            return
        if self.cur.kind is TokenKind.EOF:
            return
        self._err(
            "HML-P204",
            f"unexpected {self._describe(self.cur)} after {ctx}",
            correction="HML-L1 permits one statement per line",
        )
        self.skip_line()

    # -- entry point ------------------------------------------------------
    def parse_module(self) -> Module:
        mod = Module(name="Main", source_file=self.file, span=Span(1, 0, 1, 0, self.file))
        while self.cur.kind is TokenKind.NEWLINE:
            self.next()
        while not self.at_end():
            try:
                stmt = self.parse_statement()
            except ParseAbort:
                self.skip_line()
                continue
            if stmt is not None:
                if isinstance(stmt, ModuleDecl):
                    mod.name = stmt.name
                mod.statements.append(stmt)
            while self.cur.kind is TokenKind.NEWLINE:
                self.next()
        return mod

    # -- statements -------------------------------------------------------
    def parse_statement(self) -> Statement | None:
        t = self.cur
        if t.kind is TokenKind.NEWLINE:
            self.next()
            return None

        if t.is_kw("module"):
            self.next()
            name = self.expect_ident("after 'module'")
            self.end_line("module declaration")
            return ModuleDecl(name=name.value, span=Span.merge(t.span, name.span))

        if t.kind is TokenKind.KEYWORD and t.value in _DECL_KEYWORDS:
            return self.parse_declaration()

        if t.is_kw("def", "fn"):
            return self.parse_define()

        if t.is_kw("law", "prior", "likelihood"):
            return self.parse_law()

        if t.is_kw("assume"):
            self.next()
            label = self._optional_claim_label()
            e = self.parse_expr()
            self.end_line("assume")
            return AssumeStmt(proposition=e, label=label, span=Span.merge(t.span, e.span))

        if t.is_kw("require"):
            self.next()
            label = self._optional_claim_label()
            e = self.parse_expr()
            self.end_line("require")
            return RequireStmt(proposition=e, label=label, span=Span.merge(t.span, e.span))

        if t.is_kw("prove"):
            self.next()
            label = self._optional_claim_label()
            e = self.parse_expr()
            self.end_line("prove")
            return ProveStmt(proposition=e, label=label, span=Span.merge(t.span, e.span))

        if t.is_kw("goal"):
            return self.parse_goal()

        if t.is_kw("derive"):
            return self.parse_derive()

        if t.is_kw("proved"):
            return self.parse_proved()

        if t.is_kw("minimise", "minimize", "maximise", "maximize"):
            self.next()
            direction = "minimise" if t.value.startswith("mini") else "maximise"
            e = self.parse_expr()
            self.end_line("objective")
            return ObjectiveStmt(direction=direction, expression=e, span=Span.merge(t.span, e.span))

        if t.is_kw("solve"):
            self.next()
            refs = self.parse_ref_list()
            self.end_line("solve")
            end = refs[-1].span if refs else t.span
            return SolveStmt(targets=refs, span=Span.merge(t.span, end))

        if t.is_kw("infer"):
            return self.parse_infer()

        if t.is_kw("check"):
            return self.parse_check()

        if t.is_kw("concept"):
            return self.parse_concept()

        self._err(
            "HML-P205",
            f"{self._describe(t)} does not begin a statement",
            correction=(
                "statements begin with one of: module var param const obs index rv def "
                "law prior likelihood assume require prove minimise maximise solve "
                "infer check concept goal derive proved"
            ),
        )
        raise ParseAbort

    # -- V2 reasoning spine -----------------------------------------------
    #
    # Three statement forms, all single-line, all LL(2). The block form the directive
    # sketched (`derive d1:` / newline / `from ...`) was rejected: HML-L1 is
    # line-oriented everywhere except `concept ... end`, and a second block convention
    # would cost a grammar rule, an indentation policy and a recovery strategy to buy
    # nothing a model needs. One line per inference is also the cheaper thing to emit.

    def _optional_claim_label(self) -> str | None:
        """Accept a leading ``name :`` claim label.

        LL(2) and unambiguous: no proposition can begin with IDENT followed by ':',
        because ':' is not an expression operator. The unlabelled v1 forms therefore
        keep parsing exactly as before.
        """
        if self.cur.kind is TokenKind.IDENT and self.peek().is_op(":"):
            name = self.next().value
            self.next()  # ':'
            return name
        return None

    def _require_claim_label(self, ctx: str) -> str:
        name = self.expect_ident(f"to label the {ctx}")
        if not self.accept_op(":"):
            self._err(
                "HML-P250",
                f"expected ':' after the {ctx} label {name.value!r}",
                correction=f"{ctx} {name.value} : <proposition>",
            )
            raise ParseAbort
        return name.value

    def parse_goal(self) -> GoalStmt:
        t = self.next()
        label = self._require_claim_label("goal")
        prop = self.parse_expr()
        self.end_line("goal")
        return GoalStmt(
            label=label, proposition=prop, span=Span.merge(t.span, prop.span)
        )

    def parse_derive(self) -> DeriveStmt:
        """``derive <id> : <conclusion> [from <id>, ...] by <rule>[(<role> := e, ...)]``

        The conclusion comes before ``from``/``by`` and is parsed by the ordinary
        expression parser, which stops cleanly at the first non-operator token. Since
        ``from`` and ``by`` are keywords, they can never be absorbed into the
        conclusion by mistake.
        """
        t = self.next()
        label = self._require_claim_label("derivation")
        conclusion = self.parse_expr()

        premises: list[str] = []
        if self.accept_kw("from"):
            while True:
                premises.append(self.expect_ident("as a premise of the derivation").value)
                if not self.accept_op(","):
                    break

        if not self.accept_kw("by"):
            self._err(
                "HML-P251",
                "a derivation must name the rule it applies",
                correction=(
                    "derive d1 : <conclusion> from <premise> by <rule>(<role> := ...)"
                ),
                notes=[
                    "an inference without a named rule is an assertion, not a "
                    "derivation; HML has no syntax for 'this follows somehow'"
                ],
            )
            raise ParseAbort

        rule_tok = self.expect_ident("to name the inference rule")
        rule_args: list[RuleArg] = []
        if self.accept_op("("):
            if not self.cur.is_op(")"):
                while True:
                    if not (
                        self.cur.kind in (TokenKind.IDENT, TokenKind.KEYWORD)
                        and self.peek().is_op(":=")
                    ):
                        bad = self.cur
                        self._err(
                            "HML-P252",
                            f"positional arguments are not permitted for rule "
                            f"{rule_tok.value!r}",
                            bad.span,
                            correction=(
                                f"label each argument by its role, e.g. "
                                f"{rule_tok.value}(by := k)"
                            ),
                            notes=[
                                "role labels are mandatory for the same reason they are "
                                "mandatory on distributions (D-003): "
                                "'multiply_both_sides(2.0)' does not say what 2.0 is"
                            ],
                        )
                        raise ParseAbort
                    role_tok = self.next()
                    self.next()  # ':='
                    value = self.parse_expr()
                    rule_args.append(
                        RuleArg(role=role_tok.value, value=value, span=role_tok.span)
                    )
                    if not self.accept_op(","):
                        break
            self.expect_op(")", f"to close the arguments of {rule_tok.value!r}")

        seen: set[str] = set()
        for a in rule_args:
            if a.role in seen:
                self.diags.error(
                    "HML-P253",
                    f"role {a.role!r} is given more than once to {rule_tok.value!r}",
                    a.span,
                )
            seen.add(a.role)

        self.end_line("derivation")
        return DeriveStmt(
            label=label,
            conclusion=conclusion,
            premises=premises,
            rule=rule_tok.value,
            rule_args=rule_args,
            span=Span.merge(t.span, rule_tok.span),
        )

    def parse_proved(self) -> ProvedStmt:
        """``proved <goal> by <derivation>``"""
        t = self.next()
        goal = self.expect_ident("to name the goal being claimed proved")
        if not self.accept_kw("by"):
            self._err(
                "HML-P254",
                "a proof claim must name the derivation it rests on",
                correction="proved g1 by d1",
                notes=[
                    "'proved g1' alone would be an unsupported assertion; the whole "
                    "point of the form is that the checker can adjudicate it"
                ],
            )
            raise ParseAbort
        derivation = self.expect_ident("to name the supporting derivation")
        self.end_line("proof claim")
        return ProvedStmt(
            goal=goal.value,
            derivation=derivation.value,
            span=Span.merge(t.span, derivation.span),
        )

    def parse_declaration(self) -> Declaration:
        t = self.next()
        kind = _DECL_KEYWORDS[t.value]
        name = self.expect_ident(f"after '{t.value}'")
        declared: Type | None = None
        if self.accept_op(":"):
            declared = self.parse_type()
        elif self.cur.is_op("::"):
            self.next()
            self.diags.warn(
                "HML-P206",
                "'::' is accepted as a synonym for ':' in v0 but ':' is canonical",
                self.toks[self.k - 1].span,
            )
            declared = self.parse_type()
        value: Expr | None = None
        if self.accept_op("="):
            value = self.parse_expr()
        elif self.cur.is_op(":="):
            self.next()
            value = self.parse_expr()
        end = value.span if value is not None else name.span
        self.end_line(f"{t.value} declaration")
        return Declaration(
            kind=kind,
            name=name.value,
            declared_type=declared,
            value=value,
            span=Span.merge(t.span, end),
        )

    def parse_define(self) -> DefineStmt:
        t = self.next()
        name = self.expect_ident(f"after '{t.value}'")
        params: list[tuple[str, Type | None]] = []
        if self.accept_op("("):
            if not self.cur.is_op(")"):
                while True:
                    pname = self.expect_ident("in parameter list")
                    ptype: Type | None = None
                    if self.accept_op(":"):
                        ptype = self.parse_type()
                    params.append((pname.value, ptype))
                    if not self.accept_op(","):
                        break
            self.expect_op(")", "to close the parameter list")
        declared: Type | None = None
        if self.accept_op(":"):
            declared = self.parse_type()
        if not self.accept_op(":="):
            self._err(
                "HML-P207",
                "a definition requires ':='",
                correction=f"def {name.value} := <expression>",
                notes=["':=' binds a definition; '=' is mathematical equality"],
            )
            raise ParseAbort
        body = self.parse_expr()
        self.end_line("definition")
        return DefineStmt(
            name=name.value,
            declared_type=declared,
            body=body,
            params=params,
            span=Span.merge(t.span, body.span),
        )

    def parse_law(self) -> LawStmt:
        t = self.next()
        target = self.expect_ident(f"after '{t.value}'")
        given: list[Ref] = []
        if self.accept_op("|"):
            given = self.parse_ref_list()
        if not self.accept_op("~"):
            self._err(
                "HML-P208",
                "a law requires '~' between the variable and its distribution",
                correction=f"{t.value} {target.value} ~ Normal(location := mu, scale := sigma)",
                notes=["'~' relates a RandomVariable[T] to a Distribution[T]"],
            )
            raise ParseAbort
        dist = self.parse_dist_expr()
        self.end_line("law")
        return LawStmt(
            target=target.value,
            given=given,
            distribution=dist,
            role=t.value,
            span=Span.merge(t.span, dist.span),
        )

    def parse_infer(self) -> InferStmt:
        t = self.next()
        query = "posterior"
        if self.cur.kind is TokenKind.KEYWORD and self.cur.value in _INFER_QUERIES:
            query = self.next().value
        else:
            self._err(
                "HML-P209",
                "'infer' requires a query kind",
                correction="infer posterior theta",
                notes=[f"available queries: {', '.join(sorted(_INFER_QUERIES))}"],
            )
            raise ParseAbort
        refs = self.parse_ref_list()
        self.end_line("infer")
        end = refs[-1].span if refs else t.span
        return InferStmt(query=query, targets=refs, span=Span.merge(t.span, end))

    def parse_check(self) -> CheckStmt:
        t = self.next()
        if self.accept_kw("dimension"):
            # Parse below the comparison level: the '=' that may follow introduces the
            # asserted *dimension*, not a mathematical equation.
            subject = self.parse_additive()
            expected: str | None = None
            if self.accept_op("="):
                expected = self.parse_dimension().render()
            self.end_line("check")
            return CheckStmt(
                check_kind="dimension",
                subject=subject,
                expected=expected,
                span=Span.merge(t.span, subject.span),
            )
        subject = self.parse_expr()
        self.end_line("check")
        return CheckStmt(
            check_kind="proposition", subject=subject, span=Span.merge(t.span, subject.span)
        )

    def parse_concept(self) -> ConceptDecl:
        t = self.next()
        name = self.expect_ident("after 'concept'")
        extends: list[str] = []
        if self.accept_kw("extends"):
            while True:
                extends.append(self.expect_ident("in an extends clause").value)
                if not self.accept_op(","):
                    break
        self.end_line("concept header")
        members: list[ConceptMember] = []
        while True:
            while self.cur.kind is TokenKind.NEWLINE:
                self.next()
            if self.at_end():
                self._err(
                    "HML-P210",
                    f"concept {name.value!r} is not closed",
                    t.span,
                    correction="add 'end' on its own line",
                )
                break
            if self.accept_kw("end"):
                self.end_line("concept")
                break
            try:
                members.append(self.parse_concept_member())
            except ParseAbort:
                self.skip_line()
        return ConceptDecl(
            name=name.value, extends=extends, members=members, span=Span.merge(t.span, name.span)
        )

    def parse_concept_member(self) -> ConceptMember:
        t = self.cur
        if not (t.kind is TokenKind.KEYWORD and t.value in _CONCEPT_MEMBER_KEYWORDS):
            self._err(
                "HML-P211",
                f"{self._describe(t)} is not a concept member",
                correction=(
                    "concept members begin with: "
                    + " ".join(sorted(_CONCEPT_MEMBER_KEYWORDS))
                ),
            )
            raise ParseAbort
        self.next()
        mname = self.expect_ident(f"after '{t.value}'")
        # Transform parameters may carry an explicit type. Governing principle 1 says
        # every object has a type, so an untyped binder here was an inconsistency; the
        # annotation is optional only because the type is often inferable from use.
        params: list[tuple[str, Type | None]] = []
        if self.accept_op("("):
            if not self.cur.is_op(")"):
                while True:
                    pname = self.expect_ident("in a transform parameter list")
                    if not self.accept_op(":"):
                        # An unannotated binder was previously allowed and simply became
                        # Unknown, which governing principle 1 forbids. Requiring the
                        # annotation is the resolution; see D-015.
                        self._err(
                            "HML-P214",
                            f"transform parameter {pname.value!r} needs an explicit type",
                            pname.span,
                            correction=f"{mname.value}({pname.value} : Real)",
                            notes=["every object has a type (governing principle 1)"],
                        )
                        raise ParseAbort
                    ptype: Type = self.parse_type()
                    params.append((pname.value, ptype))
                    if not self.accept_op(","):
                        break
            self.expect_op(")", "to close the parameter list")
        declared: Type | None = None
        if self.accept_op(":"):
            declared = self.parse_type()
        body: Expr | None = None
        if self.accept_op(":="):
            body = self.parse_expr()
        elif t.value in ("invariant", "example", "counterexample", "property"):
            # `invariant scale > 0` is a natural thing to write and a natural mistake:
            # the name has been consumed as the start of the expression. Say so, rather
            # than reporting a stray operator several tokens later.
            if self.cur.kind is not TokenKind.NEWLINE and self.cur.kind is not TokenKind.EOF:
                self._err(
                    "HML-P213",
                    f"a concept {t.value} must be named, then bound with ':='",
                    Span.merge(t.span, self.cur.span),
                    found=f"{t.value} {mname.value} ...",
                    correction=f"{t.value} <name> := {mname.value} ...",
                    notes=[
                        "names make each obligation referenceable in 'hml obligations' "
                        "and in diagnostics"
                    ],
                )
                raise ParseAbort
        self.end_line(f"concept {t.value}")
        return ConceptMember(
            kind=t.value,
            name=mname.value,
            declared_type=declared,
            body=body,
            params=params,
            span=Span.merge(t.span, mname.span),
        )

    def parse_ref_list(self) -> list[Ref]:
        """Refs separated by commas or plain whitespace: ``y | x beta sigma``."""
        refs: list[Ref] = []
        while self.cur.kind is TokenKind.IDENT:
            tok = self.next()
            refs.append(Ref(name=tok.value, span=tok.span))
            self.accept_op(",")
        if not refs:
            self._err("HML-P212", "expected at least one symbol", found=self._describe(self.cur))
            raise ParseAbort
        return refs

    # -- types ------------------------------------------------------------
    def parse_type(self) -> Type:
        tok = self.cur
        if tok.kind is not TokenKind.IDENT:
            self._err(
                "HML-P220",
                "expected a type",
                found=self._describe(tok),
                correction="e.g. Real, PositiveReal, Probability, Vector[Real, N]",
            )
            raise ParseAbort
        self.next()
        head = tok.value

        args_present = self.cur.is_op("[")
        if not args_present:
            scalar = parse_scalar_name(head)
            if scalar is not None:
                return scalar
            if head == "Proposition":
                return PropositionType()
            if head == "Dimensionless":
                return QuantityType()
            if head in ("Quantity", "Vector", "Matrix", "Tensor", "Set", "Function",
                        "Predicate", "RandomVariable", "Distribution"):
                self._err(
                    "HML-P221",
                    f"type constructor {head!r} requires arguments",
                    tok.span,
                    correction=f"{head}[...]",
                )
                raise ParseAbort
            # An unknown capitalised name is a concept reference; the checker verifies it.
            return ConceptType(head)

        self.next()  # consume '['
        if head == "Quantity":
            dim = self.parse_dimension()
            self.expect_op("]", "to close Quantity[...]")
            return QuantityType(dim)

        if head == "Function":
            domain: list[Type] = [self.parse_type()]
            while self.accept_op(","):
                domain.append(self.parse_type())
            if not self.accept_op("->"):
                self._err(
                    "HML-P222",
                    "Function requires '->' between domain and codomain",
                    correction="Function[Real -> Real]",
                )
                raise ParseAbort
            codomain = self.parse_type()
            self.expect_op("]", "to close Function[...]")
            return FunctionType(tuple(domain), codomain)

        first = self.parse_type()

        if head == "Set":
            self.expect_op("]", "to close Set[...]")
            return SetType(first)
        if head == "RandomVariable":
            self.expect_op("]", "to close RandomVariable[...]")
            return RandomVariableType(first)
        if head == "Distribution":
            self.expect_op("]", "to close Distribution[...]")
            return DistributionType(first)
        if head == "Predicate":
            dom = [first]
            while self.accept_op(","):
                dom.append(self.parse_type())
            self.expect_op("]", "to close Predicate[...]")
            return PredicateType(tuple(dom))

        extents: list[str | int | None] = []
        while self.accept_op(","):
            extents.append(self.parse_extent())
        self.expect_op("]", f"to close {head}[...]")

        if head == "Vector":
            return VectorType(first, extents[0] if extents else None)
        if head == "Matrix":
            rows = extents[0] if len(extents) > 0 else None
            cols = extents[1] if len(extents) > 1 else None
            return MatrixType(first, rows, cols)
        if head == "Tensor":
            return TensorType(first, tuple(extents))

        self._err("HML-P223", f"unknown parameterised type {head!r}", tok.span)
        raise ParseAbort

    def parse_extent(self) -> str | int | None:
        if self.cur.kind is TokenKind.NUMBER:
            return int(float(self.next().value))
        if self.cur.kind is TokenKind.IDENT:
            return self.next().value
        if self.cur.is_op("?"):
            self.next()
            return None
        self._err(
            "HML-P224",
            "expected a dimension extent",
            found=self._describe(self.cur),
            correction="a positive integer, a symbolic name such as N, or '?'",
        )
        raise ParseAbort

    def parse_dimension(self) -> Dimension:
        dim = self._dim_term()
        while True:
            if self.accept_op("*"):
                dim = dim * self._dim_term()
            elif self.accept_op("/"):
                dim = dim / self._dim_term()
            else:
                return dim

    def _dim_term(self) -> Dimension:
        if self.accept_op("("):
            inner = self.parse_dimension()
            self.expect_op(")", "to close a dimension group")
            return self._dim_power(inner)
        if self.cur.kind is TokenKind.NUMBER and self.cur.value in ("1", "1.0"):
            self.next()
            return Dimension()
        tok = self.cur
        if tok.kind is not TokenKind.IDENT:
            self._err(
                "HML-P225",
                "expected a base dimension",
                found=self._describe(tok),
                correction=f"one of: {', '.join(BASE_DIMENSIONS)}, or Dimensionless",
            )
            raise ParseAbort
        self.next()
        if tok.value == "Dimensionless":
            return self._dim_power(Dimension())
        if tok.value not in BASE_DIMENSIONS:
            # A single capital letter is a dimension VARIABLE. Anything longer is a typo
            # and must stay an error -- otherwise `Quantity[Lenght]` would silently become
            # a variable, reintroducing the unknown-name hole HML-T440 closes elsewhere.
            if is_dimension_variable(tok.value):
                return self._dim_power(Dimension.variable(tok.value))
            self._err(
                "HML-D501",
                f"{tok.value!r} is not a base dimension",
                tok.span,
                expected=", ".join(BASE_DIMENSIONS),
                found=tok.value,
                correction=(
                    "use a base dimension, or a single capital letter for an unknown "
                    "dimension variable"
                ),
            )
            raise ParseAbort
        return self._dim_power(Dimension.of(**{tok.value: 1}))

    def _dim_power(self, base: Dimension) -> Dimension:
        """Parse an optional `^ exponent`, where the exponent may be a rational.

        The disambiguation that makes `Mass^1/2 * Length` work: after reading the
        numerator, a `/` followed by a NUMBER is a fractional exponent, whereas a `/`
        followed by an identifier is dimension division. Splitting on `/` first -- which
        is what the previous implementation did -- tore `1/2` apart and made every
        half-integer exponent a parse error, even though `Dimension` has always stored
        `Fraction` exponents. One benchmark case had to be deleted because of it.
        """
        if self.accept_op("^"):
            neg = bool(self.accept_op("-"))
            if self.cur.kind is not TokenKind.NUMBER:
                self._err(
                    "HML-P226",
                    "dimension exponents must be rational literals",
                    found=self._describe(self.cur),
                    correction="e.g. Length^2, Length^-1, Length^1/2",
                )
                raise ParseAbort
            raw = self.next().value
            exp = (
                Fraction(raw)
                if "." not in raw and "e" not in raw.lower()
                else Fraction(str(float(raw)))
            )
            if self.cur.is_op("/") and self.peek().kind is TokenKind.NUMBER:
                self.next()
                denom_raw = self.next().value
                try:
                    denom = Fraction(denom_raw)
                except ValueError:
                    self._err("HML-P226", "a fractional exponent needs an integer denominator")
                    raise ParseAbort from None
                if denom == 0:
                    self._err(
                        "HML-P227",
                        "a dimension exponent may not have a zero denominator",
                        correction="e.g. Length^1/2",
                    )
                    raise ParseAbort
                exp = exp / denom
            return base.power(-exp if neg else exp)
        return base

    # -- expressions ------------------------------------------------------
    def parse_expr(self) -> Expr:
        """Entry point for expression parsing, with a hard nesting bound.

        The bound is enforced here rather than at each recursive site so that every path
        into an expression is covered by one check.
        """
        self._depth += 1
        try:
            if self._depth > MAX_EXPR_DEPTH:
                self._err(
                    "HML-P240",
                    f"expression nested more than {MAX_EXPR_DEPTH} levels deep",
                    correction="simplify the expression, or check for unbalanced '('",
                    notes=[
                        "a deeply nested or truncated expression is rejected rather than "
                        "risking a crash"
                    ],
                )
                raise ParseAbort
            return self.parse_implication()
        finally:
            self._depth -= 1

    def parse_implication(self) -> Expr:
        left = self.parse_disjunction()
        if self.cur.is_op("=>", "<=>") or self.cur.is_kw("implies", "iff"):
            tok = self.next()
            op = {"=>": "implies", "<=>": "iff"}.get(tok.value, tok.value)
            right = self.parse_implication()  # right associative
            return LogicalOp(op=op, left=left, right=right, span=Span.merge(left.span, right.span))
        return left

    def parse_disjunction(self) -> Expr:
        left = self.parse_conjunction()
        while self.cur.is_kw("or"):
            self.next()
            right = self.parse_conjunction()
            left = LogicalOp(op="or", left=left, right=right, span=Span.merge(left.span, right.span))
        return left

    def parse_conjunction(self) -> Expr:
        left = self.parse_negation()
        while self.cur.is_kw("and"):
            self.next()
            right = self.parse_negation()
            left = LogicalOp(op="and", left=left, right=right, span=Span.merge(left.span, right.span))
        return left

    def parse_negation(self) -> Expr:
        if self.cur.is_kw("not"):
            tok = self.next()
            operand = self.parse_negation()
            return UnaryOp(op="not", operand=operand, span=Span.merge(tok.span, operand.span))
        return self.parse_comparison()

    def parse_comparison(self) -> Expr:
        left = self.parse_additive()
        if self.cur.kind is TokenKind.OP and self.cur.value in _COMPARISONS:
            tok = self.next()
            right = self.parse_additive()
            node = Comparison(op=tok.value, left=left, right=right,
                              span=Span.merge(left.span, right.span))
            # Chained comparisons are a classic silent-meaning bug (a < b < c).
            if self.cur.kind is TokenKind.OP and self.cur.value in _COMPARISONS:
                self._err(
                    "HML-P230",
                    "chained comparisons are not permitted",
                    correction="write 'a < b and b < c'",
                    notes=["chaining hides which comparison is intended and is rejected"],
                )
                raise ParseAbort
            return node
        return left

    def parse_additive(self) -> Expr:
        left = self.parse_multiplicative()
        while self.cur.is_op("+", "-"):
            tok = self.next()
            right = self.parse_multiplicative()
            left = BinOp(op=tok.value, left=left, right=right,
                         span=Span.merge(left.span, right.span))
        return left

    def parse_multiplicative(self) -> Expr:
        left = self.parse_unary()
        while self.cur.is_op("*", "/", "@"):
            tok = self.next()
            right = self.parse_unary()
            left = BinOp(op=tok.value, left=left, right=right,
                         span=Span.merge(left.span, right.span))
        return left

    def parse_unary(self) -> Expr:
        if self.cur.is_op("-"):
            tok = self.next()
            operand = self.parse_unary()
            return UnaryOp(op="-", operand=operand, span=Span.merge(tok.span, operand.span))
        return self.parse_power()

    def parse_power(self) -> Expr:
        base = self.parse_postfix()
        if self.cur.is_op("^", "**"):
            self.next()
            exponent = self.parse_unary()  # right associative
            return BinOp(op="^", left=base, right=exponent,
                         span=Span.merge(base.span, exponent.span))
        return base

    def parse_postfix(self) -> Expr:
        node = self.parse_primary()
        while self.cur.is_op("["):
            self.next()
            indices: list[Expr] = [self.parse_expr()]
            while self.accept_op(","):
                indices.append(self.parse_expr())
            close = self.expect_op("]", "to close an index")
            node = Index(base=node, indices=indices, span=Span.merge(node.span, close.span))
        return node

    def parse_primary(self) -> Expr:
        tok = self.cur

        if tok.kind is TokenKind.NUMBER:
            self.next()
            raw = tok.value
            value: float | int = int(raw) if raw.isdigit() else float(raw)
            return Literal(value=value, raw=raw, span=tok.span)

        if tok.is_kw("true", "false"):
            self.next()
            return Literal(value=(tok.value == "true"), raw=tok.value, span=tok.span)

        if tok.is_kw("forall", "exists"):
            return self.parse_quantifier()

        if tok.kind is TokenKind.IDENT:
            self.next()
            if self.cur.is_op("("):
                return self.parse_call(tok)
            return Ref(name=tok.value, span=tok.span)

        if tok.is_op("("):
            self.next()
            inner = self.parse_expr()
            close = self.expect_op(")", "to close a parenthesised expression")
            inner.span = Span.merge(tok.span, close.span)
            return inner

        self._err(
            "HML-P231",
            f"expected an expression, found {self._describe(tok)}",
        )
        raise ParseAbort

    def parse_call(self, name_tok: Token):
        """A call in expression position. Labelled args make it a DistExpr."""
        self.expect_op("(", "to open an argument list")
        labelled: list[Arg] = []
        positional: list[Expr] = []
        if not self.cur.is_op(")"):
            while True:
                if (
                    self.cur.kind in (TokenKind.IDENT, TokenKind.KEYWORD)
                    and self.peek().is_op(":=")
                ):
                    role_tok = self.next()
                    self.next()  # ':='
                    value = self.parse_expr()
                    labelled.append(Arg(role=role_tok.value, value=value, span=role_tok.span))
                else:
                    positional.append(self.parse_expr())
                if not self.accept_op(","):
                    break
        close = self.expect_op(")", f"to close the arguments of {name_tok.value!r}")
        span = Span.merge(name_tok.span, close.span)

        if labelled and positional:
            self._err(
                "HML-P232",
                f"{name_tok.value!r} mixes role-labelled and positional arguments",
                span,
                correction="label every argument, e.g. Normal(location := mu, scale := sigma)",
            )
            raise ParseAbort
        if labelled:
            return DistExpr(family=name_tok.value, args=labelled, span=span)
        from ..ast.nodes import Call

        return Call(callee=name_tok.value, args=positional, span=span)

    def parse_dist_expr(self) -> DistExpr:
        tok = self.cur
        if tok.kind is not TokenKind.IDENT:
            self._err(
                "HML-P233",
                "expected a distribution family",
                found=self._describe(tok),
                correction="e.g. Normal(location := mu, scale := sigma)",
            )
            raise ParseAbort
        self.next()
        if not self.cur.is_op("("):
            return DistExpr(family=tok.value, args=[], span=tok.span)
        self.next()
        args: list[Arg] = []
        if not self.cur.is_op(")"):
            while True:
                if not (
                    self.cur.kind in (TokenKind.IDENT, TokenKind.KEYWORD)
                    and self.peek().is_op(":=")
                ):
                    bad = self.cur
                    self._err(
                        "HML-P234",
                        f"positional arguments are not permitted for distribution "
                        f"{tok.value!r}",
                        bad.span,
                        correction=(
                            f"label each argument by its role, e.g. "
                            f"{tok.value}(location := mu, scale := sigma)"
                        ),
                        notes=[
                            "role labels are mandatory by design decision D-003: they "
                            "make 'scale' vs 'variance' explicit rather than positional"
                        ],
                    )
                    raise ParseAbort
                role_tok = self.next()
                self.next()  # ':='
                value = self.parse_expr()
                args.append(Arg(role=role_tok.value, value=value, span=role_tok.span))
                if not self.accept_op(","):
                    break
        close = self.expect_op(")", f"to close the arguments of {tok.value!r}")
        seen: set[str] = set()
        for a in args:
            if a.role in seen:
                self.diags.error(
                    "HML-P235",
                    f"role {a.role!r} is given more than once to {tok.value!r}",
                    a.span,
                )
            seen.add(a.role)
        return DistExpr(family=tok.value, args=args, span=Span.merge(tok.span, close.span))

    def parse_quantifier(self) -> Quantifier:
        tok = self.next()
        kind = tok.value
        if kind == "exists" and self.cur.is_kw("unique"):
            self.next()
            kind = "exists_unique"
        var = self.expect_ident(f"after '{tok.value}'")
        if not self.accept_op(":"):
            self._err(
                "HML-P236",
                "a quantified variable requires an explicit type",
                correction=f"{tok.value} {var.value} : Real . <proposition>",
                notes=["untyped quantification is rejected: the domain must be explicit"],
            )
            raise ParseAbort
        var_type = self.parse_type()
        if not self.accept_op("."):
            self._err(
                "HML-P237",
                "expected '.' between the quantifier binding and its body",
                correction=f"{tok.value} {var.value} : {var_type.render()} . <proposition>",
            )
            raise ParseAbort
        body = self.parse_expr()
        return Quantifier(
            kind=kind,
            var=var.value,
            var_type=var_type,
            body=body,
            span=Span.merge(tok.span, body.span),
        )


def parse(source: str, file: str = "<input>", diags: DiagnosticBag | None = None):
    """Parse HML-L1 source into a ``Module``. Returns ``(module, diagnostics)``.

    Guarantees, which the evaluation harness depends on: finite runtime, no uncaught
    exception, and at least one diagnostic or a valid parse for **any** input. Arbitrary
    model output reaches this function, so a crash here would take down a run rather than
    scoring a bad generation.
    """
    bag = diags if diags is not None else DiagnosticBag(source, file)
    try:
        tokens, bag = tokenize(source, bag, file)
        module = Parser(tokens, bag, file).parse_module()
    except RecursionError:
        # Backstop only. MAX_EXPR_DEPTH should catch nesting first; if this fires, the
        # bound is wrong for some path and needs re-measuring.
        bag.error(
            "HML-P241",
            "input is nested too deeply for the parser to process",
            Span(1, 0, 1, 0, file),
            correction="simplify the expression, or check for unbalanced delimiters",
            notes=["recursion backstop reached; MAX_EXPR_DEPTH did not cover this path"],
        )
        module = Module(name="Main", source_file=file, span=Span(1, 0, 1, 0, file))
    return module, bag
