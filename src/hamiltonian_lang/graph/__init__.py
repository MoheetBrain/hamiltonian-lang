"""Semantic graph view.

The same object rendered as nodes and typed edges. This is a *view*, not a separate
representation: it is derived from the AST, never authored independently, and never a
user interface (master directive section 22).

Edge vocabulary is closed and defined in :data:`EDGE_KINDS` so that a consumer can rely
on it. Triples are emitted as ``(subject, predicate, object)`` for retrieval and
dependency tracking, which is benchmark hypothesis H7.
"""

from __future__ import annotations

from collections.abc import Iterable
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
    LogicalOp,
    Module,
    ObjectiveStmt,
    ProveStmt,
    Quantifier,
    Ref,
    RequireStmt,
    SolveStmt,
    Statement,
    UnaryOp,
)
from ..semantics import SymbolTable

__all__ = ["Node", "Edge", "SemanticGraph", "build_graph", "EDGE_KINDS"]

EDGE_KINDS = frozenset({
    "has_type",            # symbol -> type
    "declared_as",         # symbol -> declaration kind
    "has_law",             # symbol -> distribution node
    "family",              # distribution -> family name
    "role",                # distribution -> argument, labelled by role
    "conditioned_on",      # symbol -> symbol
    "depends_on",          # symbol -> symbol (definition body reference)
    "constrains",          # constraint -> symbol
    "objective_of",        # objective -> symbol
    "queries",             # inference -> symbol
    "binds",               # quantifier -> symbol
    "scope_of",            # quantifier -> inner quantifier
    "member_of",           # concept member -> concept
    "extends",             # concept -> concept
    "obligation_on",       # obligation -> symbol
})


@dataclass
class Node:
    id: str
    kind: str
    label: str
    attrs: dict = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    kind: str
    target: str
    label: str = ""

    def as_triple(self) -> tuple[str, str, str]:
        pred = f"{self.kind}:{self.label}" if self.label else self.kind
        return (self.source, pred, self.target)


class SemanticGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._counters: dict[str, int] = {}

    def fresh(self, kind: str) -> str:
        n = self._counters.get(kind, 0)
        self._counters[kind] = n + 1
        return f"{kind}:{n}"

    def add_node(self, id: str, kind: str, label: str, **attrs) -> str:
        if id not in self.nodes:
            self.nodes[id] = Node(id, kind, label, attrs)
        return id

    def add_edge(self, source: str, kind: str, target: str, label: str = "") -> None:
        assert kind in EDGE_KINDS, f"undeclared edge kind {kind!r}"
        self.edges.append(Edge(source, kind, target, label))

    def triples(self) -> list[tuple[str, str, str]]:
        return [e.as_triple() for e in self.edges]

    def to_dict(self) -> dict:
        return {
            "nodes": [
                {"id": n.id, "kind": n.kind, "label": n.label, **n.attrs}
                for n in self.nodes.values()
            ],
            "edges": [
                {"source": e.source, "kind": e.kind, "target": e.target, "label": e.label}
                for e in self.edges
            ],
        }

    def render_triples(self) -> str:
        return "\n".join(f"{s} -> {p} {o}" for s, p, o in self.triples())

    def dependencies_of(self, symbol_label: str) -> set[str]:
        """Transitive closure of depends_on / conditioned_on / role edges."""
        by_label = {n.label: n.id for n in self.nodes.values() if n.kind == "symbol"}
        start = by_label.get(symbol_label)
        if start is None:
            return set()
        adjacency: dict[str, list[str]] = {}
        for e in self.edges:
            if e.kind in ("depends_on", "conditioned_on", "has_law", "role"):
                adjacency.setdefault(e.source, []).append(e.target)
        seen: set[str] = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            for nxt in adjacency.get(cur, []):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return {self.nodes[i].label for i in seen if i in self.nodes and self.nodes[i].kind == "symbol"}


class _Builder:
    def __init__(self, module: Module, symbols: SymbolTable) -> None:
        self.module = module
        self.symbols = symbols
        self.g = SemanticGraph()

    def symbol_node(self, sid) -> str | None:
        if sid is None:
            return None
        sym = self.symbols.get(sid)
        if sym is None:
            return None
        nid = sid.canonical()
        self.g.add_node(
            nid,
            "symbol",
            sym.name,
            declaration=sym.kind,
            type=sym.declared_type.render() if sym.declared_type else None,
            stochastic=sym.stochastic,
        )
        return nid

    def build(self) -> SemanticGraph:
        for sym in self.symbols.all.values():
            nid = sym.id.canonical()
            self.g.add_node(
                nid, "symbol", sym.name,
                declaration=sym.kind,
                type=sym.declared_type.render() if sym.declared_type else None,
                stochastic=sym.stochastic,
            )
            if sym.declared_type is not None:
                tid = self.g.add_node(
                    f"type:{sym.declared_type.render()}", "type", sym.declared_type.render()
                )
                self.g.add_edge(nid, "has_type", tid)
            kid = self.g.add_node(f"declkind:{sym.kind}", "declaration_kind", sym.kind)
            self.g.add_edge(nid, "declared_as", kid)

        for st in self.module.statements:
            self.statement(st)
        return self.g

    def statement(self, st: Statement) -> None:
        if isinstance(st, Declaration):
            if st.value is not None:
                src = self.symbol_node(st.symbol_id)
                for dep in self.refs_in(st.value):
                    if src and dep:
                        self.g.add_edge(src, "depends_on", dep)
            return

        if isinstance(st, DefineStmt):
            src = self.symbol_node(st.symbol_id)
            for dep in self.refs_in(st.body):
                if src and dep:
                    self.g.add_edge(src, "depends_on", dep)
            return

        if isinstance(st, LawStmt):
            target = self.symbol_node(st.target_symbol)
            if target is None or st.distribution is None:
                return
            dist_id = self.distribution(st.distribution)
            self.g.add_edge(target, "has_law", dist_id, st.role)
            for gref in st.given:
                gid = self.symbol_node(gref.symbol_id)
                if gid:
                    self.g.add_edge(target, "conditioned_on", gid)
            return

        if isinstance(st, (RequireStmt, AssumeStmt, ProveStmt)):
            kind = {
                RequireStmt: "constraint",
                AssumeStmt: "assumption",
                ProveStmt: "theorem",
            }[type(st)]
            nid = self.g.fresh(kind)
            from ..backends.hml import render_expr

            self.g.add_node(nid, kind, render_expr(st.proposition), line=st.span.line)
            for dep in self.refs_in(st.proposition):
                if dep:
                    self.g.add_edge(nid, "constrains", dep)
            self.quantifier_chain(st.proposition, nid)
            return

        if isinstance(st, ObjectiveStmt):
            from ..backends.hml import render_expr

            nid = self.g.fresh("objective")
            self.g.add_node(nid, "objective", render_expr(st.expression),
                            direction=st.direction)
            for dep in self.refs_in(st.expression):
                if dep:
                    self.g.add_edge(nid, "objective_of", dep)
            return

        if isinstance(st, InferStmt):
            nid = self.g.fresh("inference")
            self.g.add_node(nid, "inference", st.query)
            for t in st.targets:
                tid = self.symbol_node(t.symbol_id)
                if tid:
                    self.g.add_edge(nid, "queries", tid, st.query)
            return

        if isinstance(st, SolveStmt):
            nid = self.g.fresh("solve")
            self.g.add_node(nid, "solve", "solve")
            for t in st.targets:
                tid = self.symbol_node(t.symbol_id)
                if tid:
                    self.g.add_edge(nid, "queries", tid, "solve")
            return

        if isinstance(st, CheckStmt):
            from ..backends.hml import render_expr

            nid = self.g.fresh("check")
            label = render_expr(st.subject) if st.subject is not None else st.check_kind
            self.g.add_node(nid, "check", label, check_kind=st.check_kind,
                            expected=st.expected)
            if st.subject is not None:
                for dep in self.refs_in(st.subject):
                    if dep:
                        self.g.add_edge(nid, "constrains", dep)
            return

        if isinstance(st, ConceptDecl):
            cid = self.g.add_node(f"concept:{st.name}", "concept", st.name)
            for base in st.extends:
                bid = self.g.add_node(f"concept:{base}", "concept", base)
                self.g.add_edge(cid, "extends", bid)
            from ..backends.hml import render_expr

            for m in st.members:
                mid = self.g.fresh("member")
                self.g.add_node(
                    mid, f"concept_{m.kind}", m.name,
                    body=render_expr(m.body) if m.body is not None else None,
                    type=m.declared_type.render() if m.declared_type else None,
                )
                self.g.add_edge(mid, "member_of", cid, m.kind)
            return

    def distribution(self, d: DistExpr) -> str:
        nid = self.g.fresh("law")
        self.g.add_node(nid, "distribution", d.family)
        fid = self.g.add_node(f"family:{d.family}", "family", d.family)
        self.g.add_edge(nid, "family", fid)
        from ..backends.hml import render_expr

        for a in d.args:
            if isinstance(a.value, Ref) and a.value.symbol_id is not None:
                tid = self.symbol_node(a.value.symbol_id)
            else:
                tid = self.g.fresh("expr")
                self.g.add_node(tid, "expression", render_expr(a.value))
                for dep in self.refs_in(a.value):
                    if dep:
                        self.g.add_edge(tid, "depends_on", dep)
            if tid:
                self.g.add_edge(nid, "role", tid, a.role)
        return nid

    def quantifier_chain(self, e: Expr, parent: str) -> None:
        """Record quantifier nesting explicitly so scope order is queryable (H2)."""
        if isinstance(e, Quantifier):
            qid = self.g.fresh("quantifier")
            self.g.add_node(qid, "quantifier", e.kind,
                            variable=e.var,
                            variable_type=e.var_type.render() if e.var_type else None)
            self.g.add_edge(parent, "scope_of", qid, e.kind)
            bid = self.symbol_node(e.symbol_id)
            if bid:
                self.g.add_edge(qid, "binds", bid)
            self.quantifier_chain(e.body, qid)
            return
        for child in _children(e):
            self.quantifier_chain(child, parent)

    def refs_in(self, e: Expr) -> list[str | None]:
        out: list[str | None] = []
        if isinstance(e, Ref):
            out.append(self.symbol_node(e.symbol_id))
        for child in _children(e):
            out.extend(self.refs_in(child))
        return out


def _children(e: Expr) -> Iterable[Expr]:
    if isinstance(e, (BinOp, Comparison, LogicalOp)):
        return (e.left, e.right)
    if isinstance(e, UnaryOp):
        return (e.operand,)
    if isinstance(e, Call):
        return tuple(e.args)
    if isinstance(e, Index):
        return (e.base, *e.indices)
    if isinstance(e, DistExpr):
        return tuple(a.value for a in e.args)
    if isinstance(e, Quantifier):
        return (e.body,)
    return ()


def build_graph(module: Module, symbols: SymbolTable) -> SemanticGraph:
    return _Builder(module, symbols).build()
