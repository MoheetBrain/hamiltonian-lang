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
    ContinuityExpr,
    Declaration,
    DefineStmt,
    DerivativeExpr,
    DeriveStmt,
    DistExpr,
    EvidenceStmt,
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
    Module,
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
    ScopeStmt,
    SetComprehension,
    SolveStmt,
    Span,
    Statement,
    SymbolId,
    UnaryOp,
    UndeterminedStmt,
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


#: Declaration kinds that are MATHEMATICAL BINDERS rather than value declarations.
#:
#: D-006 rejects shadowing so that a nested value declaration cannot silently change what
#: a name means. That reasoning is right for values and **wrong for binders**, and
#: applying it to binders removed most of calculus from the language:
#:
#:     var x : Real
#:     require derivative(f, x : Real) = 0.0     -> HML-N302
#:     require integral(f, x : Real, 0.0, 1.0)   -> HML-N302
#:     require forall x : Real . x = x           -> HML-N302
#:
#: You could not differentiate with respect to a variable you had declared, write an ODE
#: in one time variable, or take a gradient with respect to your own decision variable.
#: Binding occurrences in a body is not an accident a binder might commit -- it is what a
#: binder *is*, and `integral(f(x), x, 0, 1)` where `x` is also a global is ordinary
#: mathematical notation, not an ambiguity.
#:
#: Shadowing here is safe for a reason the machinery already provides: `SymbolId` carries
#: `(depth, ordinal)` and canonicalises to `sym:#depth.ordinal`, so the binder and the
#: outer value have distinct identities regardless of spelling, alpha-equivalence holds,
#: and resolution is lexical so capture cannot occur. The rule was protecting an invariant
#: that was never at risk. (D-045.)
_BINDER_KINDS: frozenset[str] = frozenset({"quantified"})


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
        if outer is not None and kind not in _BINDER_KINDS:
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
        self._check_law_cycles()
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
            # V2 expression forms (D-026). Omitting any of these would make a definition
            # cycle running through, say, an integrand invisible to HML-S606 -- the
            # checker would report nothing and the definition would be unfoldable.
            if isinstance(n, MomentExpr):
                rec(n.body)
                for g in n.given:
                    rec(g)
                return
            if isinstance(n, ProbabilityExpr):
                rec(n.event)
                for g in n.given:
                    rec(g)
                return
            if isinstance(n, JointExpr):
                for p in n.parts:
                    rec(p)
                return
            if isinstance(n, IndependenceExpr):
                for p in n.parts:
                    rec(p)
                for g in n.given:
                    rec(g)
                return
            if isinstance(n, MembershipExpr):
                rec(n.element)
                rec(n.collection)
                return
            if isinstance(n, ContinuityExpr):
                rec(n.function)
                rec(n.domain)
                return
            if isinstance(n, RelationExpr):
                rec(n.left)
                rec(n.right)
                return
            if isinstance(n, SetComprehension):
                rec(n.predicate)
                return
            if isinstance(n, LimitExpr):
                rec(n.body)
                rec(n.point)
                return
            if isinstance(n, DerivativeExpr):
                rec(n.body)
                return
            if isinstance(n, IntegralExpr):
                rec(n.body)
                rec(n.lower)
                rec(n.upper)
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

    def _check_law_cycles(self) -> None:
        """A probability law may not depend on itself, directly or transitively.

        ``prior a ~ Normal(location := b, ...)`` says *a*'s law is specified in terms of
        *b*. If *b*'s law is in turn specified in terms of *a*, the pair specifies no
        distribution at all -- there is no joint density to factor, and the "model" is
        not a model. Measured before this check existed: such a module compiled clean
        with zero diagnostics, which is authoritative-looking output for something that
        denotes nothing. Found by the compositional-failure study (CT-022).

        Note the direction. The edge runs from the law's *target* to every symbol its
        distribution mentions, because that is the direction of dependency: to know a's
        law you must first know b. `given` symbols are conditioning variables and are
        edges for the same reason.

        Self-reference through a `given` (``law x | x ~ ...``) is caught by the same
        walk, since a one-node cycle is still a cycle.
        """
        laws: dict[str, LawStmt] = {}
        for st in self.module.statements:
            if isinstance(st, LawStmt) and st.target:
                laws.setdefault(st.target, st)

        graph: dict[str, list[str]] = {name: [] for name in laws}
        for name, st in laws.items():
            deps: list[str] = []
            if st.distribution is not None:
                for arg in st.distribution.args:
                    deps.extend(self._refs_in(arg.value))
            deps.extend(g.name for g in st.given)
            graph[name] = [d for d in deps if d in laws]

        cycle = self._find_cycle(graph)
        if cycle is not None:
            head = laws[cycle[0]]
            self.diags.error(
                "HML-S607",
                "circular probability law: " + " -> ".join(cycle),
                head.span,
                correction=(
                    "break the cycle -- give one of these symbols a law that does not "
                    "depend on the others, or declare it as a 'param'"
                ),
                notes=[
                    "a set of mutually dependent laws specifies no joint distribution: "
                    "there is no density to factor and nothing to infer from",
                    "detected because module scope is order-independent (D-008), which "
                    "is exactly what makes such a cycle expressible",
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
        if isinstance(st, (AssumeStmt, RequireStmt, ProveStmt, GoalStmt)):
            self.visit_expr(st.proposition)
            return
        if isinstance(st, DeriveStmt):
            # Only the *expressions* are resolved here. Premise labels live in the
            # claim namespace, which is disjoint from the value namespace and is
            # resolved by reasoning.resolve_claims -- so `derive d2 : ... from d1`
            # cannot accidentally bind `d1` to a variable, and `d1 + 1` cannot
            # accidentally bind a derivation.
            self.visit_expr(st.conclusion)
            for a in st.rule_args:
                # A rule argument in the `fn` role names a FUNCTION, not a value, so it
                # is resolved against the function namespace rather than the value one.
                # Without this, `congruence(fn := exp)` fails with "'exp' is not bound"
                # -- correct for a value position and wrong here, since `exp` is a
                # builtin and has no binding occurrence to point at.
                if a.role == "fn" and isinstance(a.value, Ref):
                    if (
                        a.value.name not in _BUILTIN_FUNCTIONS
                        and self.scope.lookup(a.value.name) is None
                    ):
                        self.diags.error(
                            "HML-N306",
                            f"{a.value.name!r} is not a known function",
                            a.value.span,
                            correction=self._suggest(a.value.name),
                        )
                    continue
                self.visit_expr(a.value)
            return
        if isinstance(st, ScopeStmt):
            # A scope frames ASSUMPTIONS, not value bindings. Declarations keep module
            # scope so that a name declared outside stays visible inside and a name is
            # never silently rebound -- shadowing is already an error (D-006), and this
            # construct must not become a back door to it.
            for inner in st.body:
                self.visit_statement(inner)
            return

        if isinstance(st, EvidenceStmt):
            # Same split as `derive`: expressions resolve in the value namespace, premise
            # labels belong to the disjoint claim namespace. The checker *name* is not
            # resolved here either -- it indexes the static trusted registry, which is not
            # a namespace any module can add to.
            self.visit_expr(st.proposition)
            for a in st.checker_args:
                # The `theorem` role names an entry in the static THEOREM registry, not a
                # value -- exactly as `congruence(fn := exp)` names a function rather than
                # a value. Resolving it against the value namespace would report
                # "'add_zero' is not bound", which is correct for a value position and
                # wrong here, since a theorem has no binding occurrence in the module.
                if a.role == "theorem" and isinstance(a.value, Ref):
                    from ..libraries import THEOREMS, theorem_ids

                    if a.value.name not in THEOREMS:
                        self.diags.error(
                            "HML-N307",
                            f"{a.value.name!r} is not a registered theorem",
                            a.value.span,
                            found=a.value.name,
                            correction=f"available theorems: {', '.join(theorem_ids())}",
                            notes=[
                                "theorems come from a static library registry; a module "
                                "may name one but cannot define one",
                            ],
                        )
                    continue
                self.visit_expr(a.value)
            return

        if isinstance(st, (ProvedStmt, UndeterminedStmt)):
            # Both name claims only, and claims are resolved by the reasoning pass.
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

        # -- V2 expression forms (D-026) ----------------------------------
        #
        # Two groups. The non-binding forms only recurse. The binding forms push a
        # scope, declare the binder and record its SymbolId -- exactly what the
        # Quantifier branch above does, deliberately by the same code shape, because
        # alpha-equivalence for the new binders has to come from the same machinery
        # rather than from a parallel implementation that can drift.
        if isinstance(e, MomentExpr):
            self.visit_expr(e.body)
            for g in e.given:
                self.visit_expr(g)
            return
        if isinstance(e, ProbabilityExpr):
            self.visit_expr(e.event)
            for g in e.given:
                self.visit_expr(g)
            return
        if isinstance(e, JointExpr):
            for p in e.parts:
                self.visit_expr(p)
            return
        if isinstance(e, IndependenceExpr):
            for p in e.parts:
                self.visit_expr(p)
            for g in e.given:
                self.visit_expr(g)
            return
        if isinstance(e, MembershipExpr):
            self.visit_expr(e.element)
            self.visit_expr(e.collection)
            return
        if isinstance(e, ContinuityExpr):
            self.visit_expr(e.function)
            self.visit_expr(e.domain)
            return
        if isinstance(e, RelationExpr):
            self.visit_expr(e.left)
            self.visit_expr(e.right)
            return

        if isinstance(e, SetComprehension):
            self.push(f"set {e.var}")
            e.symbol_id = self.declare(e.var, "quantified", e.var_type, e.span).id
            self.visit_expr(e.predicate)
            self.pop()
            return
        if isinstance(e, LimitExpr):
            # The point is resolved in the ENCLOSING scope, before the binder exists.
            # Otherwise `limit(1.0 / x, x : Real -> x)` would quietly bind the point to
            # the variable being taken to it, which denotes nothing.
            self.visit_expr(e.point)
            self.push(f"limit {e.var}")
            e.symbol_id = self.declare(e.var, "quantified", e.var_type, e.span).id
            self.visit_expr(e.body)
            self.pop()
            return
        if isinstance(e, DerivativeExpr):
            self.push(f"derivative {e.var}")
            e.symbol_id = self.declare(e.var, "quantified", e.var_type, e.span).id
            self.visit_expr(e.body)
            self.pop()
            return
        if isinstance(e, IntegralExpr):
            # Same rule as the limit point: the bounds are outside the binder.
            self.visit_expr(e.lower)
            self.visit_expr(e.upper)
            self.push(f"integral {e.var}")
            e.symbol_id = self.declare(e.var, "quantified", e.var_type, e.span).id
            self.visit_expr(e.body)
            self.pop()
            return


_BUILTIN_FUNCTIONS = {
    "exp", "log", "sqrt", "abs", "sin", "cos", "tan",
    "sum", "prod", "mean", "transpose",
}


def resolve(module: Module, diags: DiagnosticBag) -> SymbolTable:
    return Resolver(module, diags).run()
