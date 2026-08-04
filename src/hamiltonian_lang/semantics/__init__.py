"""Name resolution and scope checking.

Assigns a :class:`SymbolId` to every binder and every reference. After a clean run,
no consumer downstream ever needs to match names by spelling — which is what makes
alpha-renaming invariance (a v0 success criterion) achievable.

Policy decisions:

* **Module scope is order-independent.** A declarative mathematical model should not
  depend on statement order for name visibility, so binders are collected in a first
  pass. Order still matters for *definition* cycles, which are detected separately.
* **Shadowing is an error, not a warning** (D-006). The directive requires the
  language to prevent silent scope changes; a warning does not prevent anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
    Span,
    Statement,
    SymbolId,
    UnaryOp,
)
from ..diagnostics import DiagnosticBag
from ..types import Type

__all__ = ["Symbol", "SymbolTable", "Resolver", "resolve"]


@dataclass
class Symbol:
    id: SymbolId
    name: str
    kind: str  # var param const obs index rv def concept quantified concept_param
    declared_type: Type | None = None
    span: Span = field(default_factory=Span)
    stochastic: bool = False
    law_family: str | None = None
    references: list[Span] = field(default_factory=list)


class Scope:
    def __init__(self, depth: int, parent: Scope | None = None, label: str = "") -> None:
        self.depth = depth
        self.parent = parent
        self.label = label
        self.by_name: dict[str, Symbol] = {}
        self._next_ordinal = 0

    def declare(self, name: str, kind: str, declared_type, span) -> Symbol:
        sym = Symbol(
            id=SymbolId(name, self._next_ordinal, self.depth),
            name=name,
            kind=kind,
            declared_type=declared_type,
            span=span,
        )
        self._next_ordinal += 1
        self.by_name[name] = sym
        return sym

    def lookup_local(self, name: str) -> Symbol | None:
        return self.by_name.get(name)

    def lookup(self, name: str) -> Symbol | None:
        s: Scope | None = self
        while s is not None:
            hit = s.by_name.get(name)
            if hit is not None:
                return hit
            s = s.parent
        return None


class SymbolTable:
    def __init__(self, root: Scope) -> None:
        self.root = root
        self.all: dict[SymbolId, Symbol] = {}

    def register(self, sym: Symbol) -> None:
        self.all[sym.id] = sym

    def get(self, sid: SymbolId) -> Symbol | None:
        return self.all.get(sid)

    def module_symbols(self) -> list[Symbol]:
        return list(self.root.by_name.values())


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class Resolver:
    def __init__(self, module: Module, diags: DiagnosticBag) -> None:
        self.module = module
        self.diags = diags
        self.root = Scope(0, None, "module")
        self.table = SymbolTable(self.root)
        self.scope = self.root
        self.concepts: dict[str, ConceptDecl] = {}

    # -- scope plumbing ---------------------------------------------------
    def push(self, label: str) -> Scope:
        self.scope = Scope(self.scope.depth + 1, self.scope, label)
        return self.scope

    def pop(self) -> None:
        assert self.scope.parent is not None
        self.scope = self.scope.parent

    def declare(self, name: str, kind: str, declared_type, span) -> Symbol:
        existing_local = self.scope.lookup_local(name)
        if existing_local is not None:
            self.diags.error(
                "HML-N303",
                f"{name!r} is already declared in this scope",
                span,
                notes=[f"previous declaration at line {existing_local.span.line}"],
                correction="use a distinct name, or remove the duplicate declaration",
            )
            return existing_local
        outer = self.scope.parent.lookup(name) if self.scope.parent is not None else None
        if outer is not None:
            self.diags.error(
                "HML-N302",
                f"{name!r} shadows an outer binding and would silently change scope",
                span,
                notes=[
                    f"outer {outer.kind} {name!r} is bound at line {outer.span.line}",
                    "shadowing is rejected by design decision D-006",
                ],
                correction=f"rename the inner binding, e.g. {name}_inner",
            )
        sym = self.scope.declare(name, kind, declared_type, span)
        self.table.register(sym)
        return sym

    def reference(self, ref: Ref) -> Symbol | None:
        sym = self.scope.lookup(ref.name)
        if sym is None:
            self.diags.error(
                "HML-N301",
                f"{ref.name!r} is not bound",
                ref.span,
                found=ref.name,
                correction=self._suggest(ref.name),
            )
            return None
        ref.symbol_id = sym.id
        sym.references.append(ref.span)
        return sym

    def _suggest(self, name: str) -> str:
        candidates: list[str] = []
        s: Scope | None = self.scope
        while s is not None:
            candidates.extend(s.by_name)
            s = s.parent
        near = sorted(
            (c for c in candidates if _levenshtein(name.lower(), c.lower()) <= 2),
            key=lambda c: _levenshtein(name.lower(), c.lower()),
        )
        if near:
            return f"did you mean {near[0]!r}?"
        return f"declare it first, e.g. 'param {name} : Real'"

    def _check_family_collision(self, name: str, span) -> None:
        """A symbol may not take the name of a distribution family.

        The parser routes any labelled-argument call to the distribution registry
        without consulting the symbol table, so `param Normal : Real` alongside
        `law X ~ Normal(...)` would leave two meanings for one spelling, resolved
        silently. (Red-team finding 1.2.)
        """
        from ..type_system.distributions import DISTRIBUTIONS

        if name in DISTRIBUTIONS:
            self.diags.error(
                "HML-N307",
                f"{name!r} is a distribution family and cannot also name a value",
                span,
                found=name,
                correction=f"rename the symbol, e.g. {name.lower()}",
                notes=[
                    "distribution families and values share one namespace so that a "
                    "spelling has exactly one meaning"
                ],
            )

    # -- driver -----------------------------------------------------------
    def run(self) -> SymbolTable:
        # Pass 1: collect module-level binders so that order does not affect visibility.
        for st in self.module.statements:
            if isinstance(st, Declaration):
                self._check_family_collision(st.name, st.span)
                st.symbol_id = self.declare(st.name, st.kind, st.declared_type, st.span).id
            elif isinstance(st, DefineStmt):
                st.symbol_id = self.declare(st.name, "def", st.declared_type, st.span).id
            elif isinstance(st, ConceptDecl):
                if st.name in self.concepts:
                    self.diags.error(
                        "HML-N304", f"concept {st.name!r} is declared twice", st.span
                    )
                self.concepts[st.name] = st
                st.symbol_id = self.declare(st.name, "concept", None, st.span).id

        # Pass 2: resolve every reference.
        for st in self.module.statements:
            self.visit_statement(st)

        # Pass 3: cycle detection. Module scope is order-independent (D-008), which is
        # exactly what makes cycles possible; they must therefore be detected explicitly.
        self._check_definition_cycles()
        self._check_concept_cycles()
        return self.table


    # -- cycle detection --------------------------------------------------
    def _refs_in(self, e: Expr) -> list[str]:
        found: list[str] = []

        def rec(n: Expr | None) -> None:
            if n is None:
                return
            if isinstance(n, Ref):
                found.append(n.name)
                return
            if isinstance(n, (BinOp, Comparison, LogicalOp)):
                rec(n.left)
                rec(n.right)
                return
            if isinstance(n, UnaryOp):
                rec(n.operand)
                return
            if isinstance(n, Call):
                found.append(n.callee)
                for call_arg in n.args:
                    rec(call_arg)
                return
            if isinstance(n, Index):
                rec(n.base)
                for i in n.indices:
                    rec(i)
                return
            if isinstance(n, DistExpr):
                for dist_arg in n.args:
                    rec(dist_arg.value)
                return
            if isinstance(n, Quantifier):
                rec(n.body)
                return

        rec(e)
        return found

    @staticmethod
    def _find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
        """Return one cycle as a path, or None. Iterative DFS with colouring."""
        WHITE, GREY, BLACK = 0, 1, 2
        colour = dict.fromkeys(graph, WHITE)
        parent: dict[str, str | None] = {}

        for root in graph:
            if colour[root] != WHITE:
                continue
            stack: list[tuple[str, bool]] = [(root, False)]
            parent[root] = None
            while stack:
                node, processed = stack.pop()
                if processed:
                    colour[node] = BLACK
                    continue
                if colour[node] != WHITE:
                    continue
                colour[node] = GREY
                stack.append((node, True))
                for nxt in graph.get(node, []):
                    if nxt not in colour:
                        continue
                    if colour[nxt] == GREY:
                        path = [nxt]
                        cur: str | None = node
                        while cur is not None and cur != nxt:
                            path.append(cur)
                            cur = parent.get(cur)
                        path.append(nxt)
                        return list(reversed(path))
                    if colour[nxt] == WHITE:
                        parent[nxt] = node
                        stack.append((nxt, False))
        return None

    def _check_definition_cycles(self) -> None:
        """A definition may not depend on itself, directly or transitively.

        Governing principle 3 requires every inference to have traceable dependencies;
        a cyclic dependency graph has none. Detected here rather than assumed.
        """
        bodies: dict[str, DefineStmt] = {}
        graph: dict[str, list[str]] = {}
        for st in self.module.statements:
            if isinstance(st, DefineStmt):
                bodies[st.name] = st
                graph[st.name] = []
        for name, st in bodies.items():
            local = {p for p, _ in st.params}
            graph[name] = [r for r in self._refs_in(st.body) if r in bodies and r not in local]

        cycle = self._find_cycle(graph)
        if cycle is not None:
            head = bodies[cycle[0]]
            self.diags.error(
                "HML-S606",
                "circular definition: " + " -> ".join(cycle),
                head.span,
                correction="break the cycle, or introduce the quantity as a 'param'",
                notes=[
                    "a definition must be reducible to non-circular terms; every "
                    "inference needs traceable dependencies (governing principle 3)"
                ],
            )

    def _check_concept_cycles(self) -> None:
        """`extends` must be a partial order. A cycle of any length is rejected."""
        graph = {
            name: [b for b in decl.extends if b in self.concepts]
            for name, decl in self.concepts.items()
        }
        cycle = self._find_cycle(graph)
        if cycle is not None and len(cycle) > 2:
            head = self.concepts[cycle[0]]
            self.diags.error(
                "HML-S602",
                "circular concept hierarchy: " + " extends ".join(cycle),
                head.span,
                correction="remove one 'extends' edge",
                notes=[
                    "a concept defined in terms of itself has no formal definition "
                    "(governing principle 4)"
                ],
            )

    def visit_statement(self, st: Statement) -> None:
        if isinstance(st, (ModuleDecl,)):
            return
        if isinstance(st, Declaration):
            if st.value is not None:
                self.visit_expr(st.value)
            return
        if isinstance(st, DefineStmt):
            if st.params:
                self.push(f"def {st.name}")
                for pname, ptype in st.params:
                    self.declare(pname, "def_param", ptype, st.span)
                self.visit_expr(st.body)
                self.pop()
            else:
                self.visit_expr(st.body)
            return
        if isinstance(st, LawStmt):
            target = self.scope.lookup(st.target)
            if target is None:
                self.diags.error(
                    "HML-N301",
                    f"{st.target!r} is not bound",
                    st.span,
                    correction=self._suggest(st.target),
                    notes=["a law can only be given to a previously declared symbol"],
                )
            else:
                st.target_symbol = target.id
                if target.stochastic:
                    self.diags.error(
                        "HML-S601",
                        f"{st.target!r} already has a probability law "
                        f"({target.law_family})",
                        st.span,
                        correction="remove the duplicate law, or introduce a distinct symbol",
                        notes=["a symbol has at most one probability law in v0"],
                    )
                target.stochastic = True
                target.law_family = st.distribution.family if st.distribution else None
            for g in st.given:
                self.reference(g)
            if st.distribution is not None:
                self.visit_expr(st.distribution)
            return
        if isinstance(st, (AssumeStmt, RequireStmt, ProveStmt)):
            self.visit_expr(st.proposition)
            return
        if isinstance(st, ObjectiveStmt):
            self.visit_expr(st.expression)
            return
        if isinstance(st, (SolveStmt, InferStmt)):
            for r in st.targets:
                self.reference(r)
            return
        if isinstance(st, CheckStmt):
            if st.subject is not None:
                self.visit_expr(st.subject)
            return
        if isinstance(st, ConceptDecl):
            self.visit_concept(st)
            return

    def visit_concept(self, st: ConceptDecl) -> None:
        for base in st.extends:
            if base not in self.concepts:
                self.diags.error(
                    "HML-N305",
                    f"concept {st.name!r} extends unknown concept {base!r}",
                    st.span,
                    correction=self._suggest(base),
                )
        if st.name in st.extends:
            self.diags.error(
                "HML-S602", f"concept {st.name!r} extends itself", st.span
            )
        self.push(f"concept {st.name}")
        # Parameters and transforms are both visible to every member body, so an
        # invariant may refer to a transform declared after it.
        for m in st.members:
            if m.kind == "parameter":
                self.declare(m.name, "concept_param", m.declared_type, m.span)
            elif m.kind == "transform":
                self.declare(m.name, "concept_transform", m.declared_type, m.span)
        for m in st.members:
            if m.body is None:
                continue
            if m.params:
                self.push(f"{st.name}.{m.name}")
                for pname, ptype in m.params:
                    self.declare(pname, "transform_param", ptype, m.span)
                self.visit_expr(m.body)
                self.pop()
            else:
                self.visit_expr(m.body)
        self.pop()

        if not st.members_of("invariant") and not st.members_of("example"):
            self.diags.error(
                "HML-S603",
                f"concept {st.name!r} declares no invariant and no example",
                st.span,
                correction="add at least one 'invariant' or 'example' member",
                notes=[
                    "a minted concept must have testable consequences; plausibility is "
                    "not a definition (CLAUDE.md rule 4)"
                ],
            )

    def visit_expr(self, e: Expr) -> None:
        if isinstance(e, Literal):
            return
        if isinstance(e, Ref):
            self.reference(e)
            return
        if isinstance(e, (BinOp, Comparison, LogicalOp)):
            self.visit_expr(e.left)
            self.visit_expr(e.right)
            return
        if isinstance(e, UnaryOp):
            self.visit_expr(e.operand)
            return
        if isinstance(e, Call):
            if self.scope.lookup(e.callee) is None and e.callee not in _BUILTIN_FUNCTIONS:
                self.diags.error(
                    "HML-N306",
                    f"{e.callee!r} is not a known function",
                    e.span,
                    correction=self._suggest(e.callee),
                )
            for a in e.args:
                self.visit_expr(a)
            return
        if isinstance(e, Index):
            self.visit_expr(e.base)
            for i in e.indices:
                self.visit_expr(i)
            return
        if isinstance(e, DistExpr):
            for arg in e.args:
                self.visit_expr(arg.value)
            return
        if isinstance(e, Quantifier):
            self.push(f"{e.kind} {e.var}")
            sym = self.declare(e.var, "quantified", e.var_type, e.span)
            e.symbol_id = sym.id
            self.visit_expr(e.body)
            self.pop()
            return


_BUILTIN_FUNCTIONS = {
    "exp", "log", "sqrt", "abs", "sin", "cos", "tan",
    "sum", "prod", "mean", "variance", "expectation", "transpose",
}


def resolve(module: Module, diags: DiagnosticBag) -> SymbolTable:
    return Resolver(module, diags).run()
