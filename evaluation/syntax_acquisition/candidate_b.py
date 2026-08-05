"""Candidate B -- simplified V1 labelled-linear.

Same semantics as candidate A, same operators, same role discipline, **17 reserved words
instead of 47**. The reduction comes from one idea applied uniformly: where HML-L1 spends
a distinct keyword on each member of a closed family, B spends one keyword on the family
and writes the member as an ordinary word in a position where nothing else can appear.

    HML-L1                                B
    var|param|const|obs|index|rv x : T    dec <kind> x : T
    def f(..) : T := e                    fun f(..) : T := e
    law|prior|likelihood y | x ~ D        dist <role> y | x ~ D
    assume|require|prove|check p          say <mode> p
    check dimension e [= d]               say dim e [= d]
    minimise|maximise e                   opt <min|max> e
    solve r... / infer <q> r...           ask <query> r...
    concept C extends B1, B2 .. end       kind C < B1, B2 .. end
    forall / exists / exists unique       all / some / one

What is deliberately **not** simplified, because each would be a semantic regression:

* ``:=`` still binds and ``=`` still means equality. Collapsing them onto one token is
  the shortest available saving and it is exactly the conflation ``CLAUDE.md`` forbids.
* Distribution arguments keep mandatory role labels (D-003).
* Quantified variables keep mandatory type annotations.
* Conditioning keeps its own token ``|``.
* HML-L1 accepts two spellings for several things (``=``/``:=`` initialisers,
  ``minimise``/``minimize``, ``def``/``fn``, ``:``/``::``). B has exactly one spelling
  for everything, so its renderer is deterministic by construction rather than by
  convention.
"""

from __future__ import annotations

from hamiltonian_lang.ast.nodes import (
    AssumeStmt,
    CheckStmt,
    ConceptDecl,
    ConceptMember,
    Declaration,
    DefineStmt,
    InferStmt,
    LawStmt,
    Module,
    ModuleDecl,
    ObjectiveStmt,
    ProveStmt,
    Ref,
    RequireStmt,
    SolveStmt,
    Span,
    Statement,
)

from ._infix import (
    Reader,
    Vocab,
    render_expr,
    render_expr_at,
    render_type,
    tokenise,
)
from .core import (
    DECL_KINDS,
    INFER_QUERIES,
    LAW_ROLES,
    MEMBER_KINDS,
    SyntaxCandidate,
    validate_supported,
)

__all__ = ["CandidateB", "render_module_b", "B_VOCAB", "B_RESERVED_WORDS"]

SURFACE = "B"

B_VOCAB = Vocab(
    forall="all",
    exists="some",
    exists_unique="one",
    true="true",
    false="false",
    conj="and",
    disj="or",
    neg="not",
)

#: The complete reserved-word set. Every other word in the language -- `param`, `prior`,
#: `posterior`, `invariant`, `min` -- is an ordinary identifier that only carries meaning
#: in a position where no identifier can occur.
B_RESERVED_WORDS = frozenset(
    {
        "mod", "dec", "fun", "dist", "say", "opt", "ask", "kind", "end",
        "all", "some", "one", "and", "or", "not", "true", "false",
    }
)

_SAY_MODES = ("assume", "require", "prove", "check", "dim")
_OPT_DIRECTIONS = {"min": "minimise", "max": "maximise"}
_OPT_WORDS = {v: k for k, v in _OPT_DIRECTIONS.items()}
_ADDITIVE_PREC = 5


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _expr(e) -> str:
    return render_expr(e, B_VOCAB)


def _member(m: ConceptMember) -> str:
    params = ""
    if m.params:
        params = "(" + ", ".join(f"{n} : {render_type(t)}" for n, t in m.params) + ")"
    annotation = f" : {render_type(m.declared_type)}" if m.declared_type is not None else ""
    body = f" := {_expr(m.body)}" if m.body is not None else ""
    return f"    {m.kind} {m.name}{params}{annotation}{body}"


def render_statement_b(st: Statement) -> str:
    if isinstance(st, ModuleDecl):
        return f"mod {st.name}"

    if isinstance(st, Declaration):
        line = f"dec {st.kind} {st.name} : {render_type(st.declared_type)}"
        if st.value is not None:
            line += f" := {_expr(st.value)}"
        return line

    if isinstance(st, DefineStmt):
        params = ""
        if st.params:
            params = "(" + ", ".join(
                n if t is None else f"{n} : {render_type(t)}" for n, t in st.params
            ) + ")"
        annotation = f" : {render_type(st.declared_type)}" if st.declared_type is not None else ""
        return f"fun {st.name}{params}{annotation} := {_expr(st.body)}"

    if isinstance(st, LawStmt):
        given = f" | {', '.join(g.name for g in st.given)}" if st.given else ""
        return f"dist {st.role} {st.target}{given} ~ {_expr(st.distribution)}"

    if isinstance(st, AssumeStmt):
        return f"say assume {_expr(st.proposition)}"
    if isinstance(st, RequireStmt):
        return f"say require {_expr(st.proposition)}"
    if isinstance(st, ProveStmt):
        return f"say prove {_expr(st.proposition)}"

    if isinstance(st, ObjectiveStmt):
        return f"opt {_OPT_WORDS[st.direction]} {_expr(st.expression)}"

    if isinstance(st, SolveStmt):
        return f"ask solve {', '.join(t.name for t in st.targets)}"

    if isinstance(st, InferStmt):
        return f"ask {st.query} {', '.join(t.name for t in st.targets)}"

    if isinstance(st, CheckStmt):
        if st.check_kind == "dimension":
            line = f"say dim {render_expr_at(st.subject, _ADDITIVE_PREC, B_VOCAB)}"
            if st.expected is not None:
                line += f" = {st.expected}"
            return line
        return f"say check {_expr(st.subject)}"

    if isinstance(st, ConceptDecl):
        head = f"kind {st.name}"
        if st.extends:
            head += " < " + ", ".join(st.extends)
        return "\n".join([head, *(_member(m) for m in st.members), "end"])

    raise AssertionError(f"validate_supported let through {type(st).__name__}")


def render_module_b(module: Module) -> str:
    validate_supported(module, SURFACE)
    lines: list[str] = []
    if not any(isinstance(s, ModuleDecl) for s in module.statements):
        lines.append(f"mod {module.name}")
    lines.extend(render_statement_b(st) for st in module.statements)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


class _BReader(Reader):
    def read_module(self) -> Module:
        module = Module(name="Main", source_file=f"<candidate-{SURFACE}>", span=Span())
        self.skip_newlines()
        while self.cur.kind != "eof":
            module.statements.append(self._statement(module))
            self.skip_newlines()
        return module

    def _word(self, allowed: tuple[str, ...] | frozenset[str], ctx: str) -> str:
        if self.cur.kind != "ident" or self.cur.value not in allowed:
            self.fail(f"expected one of {', '.join(sorted(allowed))} {ctx}")
        return self.next().value

    def _statement(self, module: Module) -> Statement:
        tok = self.cur
        if tok.kind != "ident":
            self.fail("expected a statement keyword")
        head = tok.value

        if head == "mod":
            self.next()
            name = self.expect_ident("after 'mod'")
            self.end_line("module declaration")
            module.name = name.value
            return ModuleDecl(name=name.value, span=Span())

        if head == "dec":
            self.next()
            kind = self._word(DECL_KINDS, "after 'dec'")
            name = self.expect_ident("after a declaration kind")
            if not self.accept_op(":"):
                self.fail("a declaration requires ': <Type>'")
            declared = self.read_type()
            value = self.read_expr() if self.accept_op(":=") else None
            self.end_line("declaration")
            return Declaration(
                kind=kind, name=name.value, declared_type=declared, value=value, span=Span()
            )

        if head == "fun":
            self.next()
            name = self.expect_ident("after 'fun'")
            params: list[tuple[str, object]] = []
            if self.accept_op("("):
                if not self.cur.is_op(")"):
                    while True:
                        pname = self.expect_ident("in a parameter list")
                        ptype = self.read_type() if self.accept_op(":") else None
                        params.append((pname.value, ptype))
                        if not self.accept_op(","):
                            break
                self.expect_op(")", "to close the parameter list")
            declared = self.read_type() if self.accept_op(":") else None
            if not self.accept_op(":="):
                self.fail("a definition requires ':='")
            body = self.read_expr()
            self.end_line("definition")
            return DefineStmt(
                name=name.value,
                declared_type=declared,
                body=body,
                params=params,  # type: ignore[arg-type]
                span=Span(),
            )

        if head == "dist":
            self.next()
            role = self._word(LAW_ROLES, "after 'dist'")
            target = self.expect_ident("after a law role")
            given: list[Ref] = self.read_name_list() if self.accept_op("|") else []
            if not self.accept_op("~"):
                self.fail("a law requires '~' between the variable and its distribution")
            dist = self.read_dist()
            self.end_line("law")
            return LawStmt(
                target=target.value, given=given, distribution=dist, role=role, span=Span()
            )

        if head == "say":
            self.next()
            mode = self._word(_SAY_MODES, "after 'say'")
            if mode == "dim":
                subject = self.read_additive()
                expected = self.read_dimension().render() if self.accept_op("=") else None
                self.end_line("dimension check")
                return CheckStmt(
                    check_kind="dimension", subject=subject, expected=expected, span=Span()
                )
            proposition = self.read_expr()
            self.end_line(f"say {mode}")
            if mode == "assume":
                return AssumeStmt(proposition=proposition, span=Span())
            if mode == "require":
                return RequireStmt(proposition=proposition, span=Span())
            if mode == "prove":
                return ProveStmt(proposition=proposition, span=Span())
            return CheckStmt(check_kind="proposition", subject=proposition, span=Span())

        if head == "opt":
            self.next()
            direction = _OPT_DIRECTIONS[self._word(tuple(_OPT_DIRECTIONS), "after 'opt'")]
            expression = self.read_expr()
            self.end_line("objective")
            return ObjectiveStmt(direction=direction, expression=expression, span=Span())

        if head == "ask":
            self.next()
            query = self._word(("solve", *INFER_QUERIES), "after 'ask'")
            targets = self.read_name_list()
            self.end_line("query")
            if query == "solve":
                return SolveStmt(targets=targets, span=Span())
            return InferStmt(query=query, targets=targets, span=Span())

        if head == "kind":
            return self._concept()

        self.fail(f"{head!r} does not begin a statement")
        raise AssertionError("unreachable")

    def _concept(self) -> ConceptDecl:
        self.next()
        name = self.expect_ident("after 'kind'")
        extends: list[str] = []
        if self.accept_op("<"):
            while True:
                extends.append(self.expect_ident("in an extends clause").value)
                if not self.accept_op(","):
                    break
        self.end_line("concept header")
        members: list[ConceptMember] = []
        while True:
            self.skip_newlines()
            if self.cur.kind == "eof":
                self.fail(f"concept {name.value!r} is not closed with 'end'")
            if self.cur.is_word("end"):
                self.next()
                self.end_line("concept")
                break
            members.append(self._member())
        return ConceptDecl(name=name.value, extends=extends, members=members, span=Span())

    def _member(self) -> ConceptMember:
        kind = self._word(MEMBER_KINDS, "at the start of a concept member")
        mname = self.expect_ident(f"after '{kind}'")
        params: list[tuple[str, object]] = []
        if self.accept_op("("):
            if not self.cur.is_op(")"):
                while True:
                    pname = self.expect_ident("in a transform parameter list")
                    if not self.accept_op(":"):
                        self.fail(f"transform parameter {pname.value!r} needs an explicit type")
                    params.append((pname.value, self.read_type()))
                    if not self.accept_op(","):
                        break
            self.expect_op(")", "to close the parameter list")
        declared = self.read_type() if self.accept_op(":") else None
        body = self.read_expr() if self.accept_op(":=") else None
        self.end_line(f"concept {kind}")
        return ConceptMember(
            kind=kind,
            name=mname.value,
            declared_type=declared,
            body=body,
            params=params,  # type: ignore[arg-type]
            span=Span(),
        )


class CandidateB(SyntaxCandidate):
    id = "B"
    name = "simplified V1 labelled-linear"
    family = "line-oriented infix, one keyword per statement family, contextual discriminators"

    def render(self, module: Module) -> str:
        return render_module_b(module)

    def parse(self, text: str) -> Module:
        toks = tokenise(text, SURFACE)
        return _BReader(toks, SURFACE, B_VOCAB).read_module()
