"""Binder-safe structural matching: Tier 1, and the correspondence the rest needs.

Two jobs, in the same walk of the trees.

**Strict matching (Tier 1).** Find a bijection between the two modules' bound
symbols that makes the trees identical up to

* alpha-renaming (a binder's spelling is not part of its identity);
* declaration and statement *order* (a module is a collection of statements, not
  a script -- recorded as a tracked assumption, not assumed silently);
* commutative reordering and associative regrouping of ``+``, ``*``, ``and``,
  ``or``, ``iff``, and of the symmetric relations ``=`` and ``!=``;
* the conditioning set of a law, which the canonical form already sorts.

Nothing else is normalised here. ``^`` is **not** associative and is **not**
flattened: ``(a^b)^c`` and ``a^(b^c)`` are different trees and stay different.
``implies`` is **not** symmetric: ``p => q`` and ``q => p`` stay different. ``-``,
``/`` and ``@`` are not reordered.

**Relaxed alignment.** When the strict match fails, pair the statements anyway and
record every point where the trees diverge as a :class:`Residual`. Everything
above a residual matched exactly, so the residual is a self-contained question
that the symbolic tier or the counterexample searcher can be handed. Each pairing
carries the *confidence* with which it was made, because a guard that refutes on
the strength of a bad pairing would manufacture a false negative.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field

from ..ast.nodes import (
    Arg,
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
    SymbolId,
    UnaryOp,
)
from ..types import Type
from .display import show

__all__ = [
    "AC_BINOPS",
    "AC_LOGICAL",
    "SYMMETRIC_COMPARISONS",
    "Env",
    "Residual",
    "Pairing",
    "Alignment",
    "skeleton",
    "strict_match",
    "align",
]

#: ``+`` and ``*`` over the exact reals this language denotes. Floating-point
#: non-associativity is a property of a *machine representation*; HML literals are
#: exact rationals (the SymPy backend emits ``Rational``), so regrouping is sound.
AC_BINOPS: frozenset[str] = frozenset({"+", "*"})
AC_LOGICAL: frozenset[str] = frozenset({"and", "or", "iff"})
SYMMETRIC_COMPARISONS: frozenset[str] = frozenset({"=", "!="})

#: Above this many operands the permutation search is abandoned and operands are
#: matched positionally. Refusing to search is a coverage loss, never a verdict.
_PERMUTATION_LIMIT = 7


# ---------------------------------------------------------------------------
# The bijection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Env:
    """An injective, total-so-far map between the two modules' bound symbols.

    ``names_locked`` forbids permuting *module-level* names. It is switched on when
    the two modules declare exactly the same vocabulary, because a candidate that
    reuses the reference's own names is using them as identities: reading
    ``prove p => q`` and ``prove q => p`` as one object because ``p`` and ``q`` can
    be swapped would erase the direction of the implication. Locally bound names --
    quantifier and parameter binders, at depth > 0 -- stay freely renameable, which
    is what alpha-equivalence actually means.
    """

    fwd: Mapping[SymbolId, SymbolId] = field(default_factory=dict)
    bwd: Mapping[SymbolId, SymbolId] = field(default_factory=dict)
    names_locked: bool = False

    def bind(self, a: SymbolId, b: SymbolId) -> Env | None:
        """Extend with ``a <-> b``, or return None when that breaks injectivity."""
        if self.names_locked and a.depth == 0 and b.depth == 0 and a.name != b.name:
            return None
        seen_a = self.fwd.get(a)
        seen_b = self.bwd.get(b)
        if seen_a is not None or seen_b is not None:
            return self if (seen_a == b and seen_b == a) else None
        return Env({**self.fwd, a: b}, {**self.bwd, b: a}, self.names_locked)

    def pairs(self) -> tuple[tuple[SymbolId, SymbolId], ...]:
        return tuple(sorted(self.fwd.items()))

    def names(self) -> dict[str, str]:
        return {a.name: b.name for a, b in self.fwd.items()}


# ---------------------------------------------------------------------------
# Sigma-invariant skeletons
# ---------------------------------------------------------------------------


def _literal_key(v: object) -> str:
    if isinstance(v, bool):
        return f"bool:{v}"
    if isinstance(v, (int, float)):
        return f"num:{float(v)!r}"
    return f"lit:{v!r}"


def _type_key(t: Type | None) -> str:
    return "?" if t is None else t.render()


def skeleton(node: object) -> str:
    """A key that is invariant under renaming and under AC reordering.

    Two nodes with different skeletons can never match, so this prunes the search
    and gives the relaxed pass a reliable way to pair statements.
    """
    if node is None:
        return "-"

    if isinstance(node, Literal):
        return _literal_key(node.value)
    if isinstance(node, Ref):
        return "ref"
    if isinstance(node, UnaryOp):
        return f"u[{node.op}]({skeleton(node.operand)})"
    if isinstance(node, BinOp):
        if node.op in AC_BINOPS:
            parts = sorted(skeleton(x) for x in _flatten_binop(node))
            return f"ac[{node.op}]({','.join(parts)})"
        return f"b[{node.op}]({skeleton(node.left)},{skeleton(node.right)})"
    if isinstance(node, Comparison):
        if node.op in SYMMETRIC_COMPARISONS:
            parts = sorted([skeleton(node.left), skeleton(node.right)])
            return f"cs[{node.op}]({','.join(parts)})"
        return f"c[{node.op}]({skeleton(node.left)},{skeleton(node.right)})"
    if isinstance(node, LogicalOp):
        if node.op in AC_LOGICAL:
            parts = sorted(skeleton(x) for x in _flatten_logical(node))
            return f"al[{node.op}]({','.join(parts)})"
        return f"l[{node.op}]({skeleton(node.left)},{skeleton(node.right)})"
    if isinstance(node, Call):
        return f"call[{node.callee}]({','.join(skeleton(a) for a in node.args)})"
    if isinstance(node, Index):
        return f"idx({skeleton(node.base)};{','.join(skeleton(i) for i in node.indices)})"
    if isinstance(node, DistExpr):
        args = ",".join(
            f"{a.role}={skeleton(a.value)}" for a in sorted(node.args, key=lambda x: x.role)
        )
        return f"dist[{node.family}]({args})"
    if isinstance(node, Quantifier):
        return f"q[{node.kind}:{_type_key(node.var_type)}]({skeleton(node.body)})"

    if isinstance(node, ModuleDecl):
        return "module"
    if isinstance(node, Declaration):
        return f"decl[{node.kind}:{_type_key(node.declared_type)}]({skeleton(node.value)})"
    if isinstance(node, DefineStmt):
        ps = ",".join(_type_key(t) for _, t in node.params)
        return f"def[{_type_key(node.declared_type)};{ps}]({skeleton(node.body)})"
    if isinstance(node, LawStmt):
        return f"law[{node.role};given={len(node.given)}]({skeleton(node.distribution)})"
    if isinstance(node, AssumeStmt):
        return f"assume({skeleton(node.proposition)})"
    if isinstance(node, RequireStmt):
        return f"require({skeleton(node.proposition)})"
    if isinstance(node, ProveStmt):
        return f"prove({skeleton(node.proposition)})"
    if isinstance(node, ObjectiveStmt):
        return f"objective[{node.direction}]({skeleton(node.expression)})"
    if isinstance(node, SolveStmt):
        return f"solve[{len(node.targets)}]"
    if isinstance(node, InferStmt):
        return f"infer[{node.query};{len(node.targets)}]"
    if isinstance(node, CheckStmt):
        return f"check[{node.check_kind};{node.expected}]({skeleton(node.subject)})"
    if isinstance(node, ConceptDecl):
        ms = ",".join(
            f"{m.kind}:{m.name}:{_type_key(m.declared_type)}:{skeleton(m.body)}"
            for m in sorted(node.members, key=lambda m: (m.kind, m.name))
        )
        return f"concept[{node.name};{','.join(sorted(node.extends))}]({ms})"

    return f"<{type(node).__name__}>"


def _flatten_binop(node: BinOp) -> list[Expr]:
    out: list[Expr] = []
    stack: list[Expr] = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, BinOp) and cur.op == node.op and node.op in AC_BINOPS:
            stack.extend([cur.right, cur.left])
        else:
            out.append(cur)
    return out


def _flatten_logical(node: LogicalOp) -> list[Expr]:
    out: list[Expr] = []
    stack: list[Expr] = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, LogicalOp) and cur.op == node.op and node.op in AC_LOGICAL:
            stack.extend([cur.right, cur.left])
        else:
            out.append(cur)
    return out


# ---------------------------------------------------------------------------
# Strict matching  (Tier 1)
# ---------------------------------------------------------------------------


def _match_ref(a: Ref, b: Ref, env: Env) -> Iterator[Env]:
    if a.symbol_id is not None and b.symbol_id is not None:
        nxt = env.bind(a.symbol_id, b.symbol_id)
        if nxt is not None:
            yield nxt
        return
    # Unresolved on one side: fall back to spelling. This only happens on input
    # that did not resolve, which the scorer refuses to score anyway.
    if a.name == b.name:
        yield env


def _match_sequence(
    xs: Sequence[object], ys: Sequence[object], env: Env
) -> Iterator[Env]:
    if len(xs) != len(ys):
        return
    if not xs:
        yield env
        return
    for e1 in match_node(xs[0], ys[0], env):
        yield from _match_sequence(xs[1:], ys[1:], e1)


def _match_multiset(xs: Sequence[object], ys: Sequence[object], env: Env) -> Iterator[Env]:
    """Match two operand lists in any order, pruning by skeleton."""
    if len(xs) != len(ys):
        return
    if len(xs) > _PERMUTATION_LIMIT:
        yield from _match_sequence(xs, ys, env)
        return
    if sorted(skeleton(x) for x in xs) != sorted(skeleton(y) for y in ys):
        return
    for perm in itertools.permutations(range(len(ys))):
        if any(skeleton(xs[i]) != skeleton(ys[perm[i]]) for i in range(len(xs))):
            continue
        yield from _match_sequence(xs, [ys[i] for i in perm], env)


def match_node(a: object, b: object, env: Env) -> Iterator[Env]:
    """Yield every environment extension under which ``a`` and ``b`` are identical."""
    if a is None or b is None:
        if a is None and b is None:
            yield env
        return
    if type(a) is not type(b):
        return

    if isinstance(a, Literal) and isinstance(b, Literal):
        if _literal_key(a.value) == _literal_key(b.value):
            yield env
        return

    if isinstance(a, Ref) and isinstance(b, Ref):
        yield from _match_ref(a, b, env)
        return

    if isinstance(a, UnaryOp) and isinstance(b, UnaryOp):
        if a.op == b.op:
            yield from match_node(a.operand, b.operand, env)
        return

    if isinstance(a, BinOp) and isinstance(b, BinOp):
        if a.op != b.op:
            return
        if a.op in AC_BINOPS:
            yield from _match_multiset(_flatten_binop(a), _flatten_binop(b), env)
        else:
            yield from _match_sequence([a.left, a.right], [b.left, b.right], env)
        return

    if isinstance(a, Comparison) and isinstance(b, Comparison):
        if a.op != b.op:
            return
        if a.op in SYMMETRIC_COMPARISONS:
            yield from _match_multiset([a.left, a.right], [b.left, b.right], env)
        else:
            yield from _match_sequence([a.left, a.right], [b.left, b.right], env)
        return

    if isinstance(a, LogicalOp) and isinstance(b, LogicalOp):
        if a.op != b.op:
            return
        if a.op in AC_LOGICAL:
            yield from _match_multiset(_flatten_logical(a), _flatten_logical(b), env)
        else:
            # `implies` is directional. Antecedent to antecedent, always.
            yield from _match_sequence([a.left, a.right], [b.left, b.right], env)
        return

    if isinstance(a, Call) and isinstance(b, Call):
        if a.callee == b.callee:
            yield from _match_sequence(a.args, b.args, env)
        return

    if isinstance(a, Index) and isinstance(b, Index):
        for e1 in match_node(a.base, b.base, env):
            yield from _match_sequence(a.indices, b.indices, e1)
        return

    if isinstance(a, DistExpr) and isinstance(b, DistExpr):
        if a.family != b.family:
            return
        ra = {x.role: x.value for x in a.args}
        rb = {x.role: x.value for x in b.args}
        if set(ra) != set(rb):
            return
        roles = sorted(ra)
        yield from _match_sequence([ra[r] for r in roles], [rb[r] for r in roles], env)
        return

    if isinstance(a, Quantifier) and isinstance(b, Quantifier):
        if a.kind != b.kind or _type_key(a.var_type) != _type_key(b.var_type):
            return
        e1 = env
        if a.symbol_id is not None and b.symbol_id is not None:
            bound = env.bind(a.symbol_id, b.symbol_id)
            if bound is None:
                return
            e1 = bound
        yield from match_node(a.body, b.body, e1)
        return

    if isinstance(a, Arg) and isinstance(b, Arg):
        if a.role == b.role:
            yield from match_node(a.value, b.value, env)
        return

    yield from _match_statement(a, b, env)


def _match_statement(a: object, b: object, env: Env) -> Iterator[Env]:
    if isinstance(a, Declaration) and isinstance(b, Declaration):
        if a.kind != b.kind or _type_key(a.declared_type) != _type_key(b.declared_type):
            return
        e1 = env
        if a.symbol_id is not None and b.symbol_id is not None:
            bound = env.bind(a.symbol_id, b.symbol_id)
            if bound is None:
                return
            e1 = bound
        yield from match_node(a.value, b.value, e1)
        return

    if isinstance(a, DefineStmt) and isinstance(b, DefineStmt):
        if _type_key(a.declared_type) != _type_key(b.declared_type):
            return
        if [_type_key(t) for _, t in a.params] != [_type_key(t) for _, t in b.params]:
            return
        e1 = env
        if a.symbol_id is not None and b.symbol_id is not None:
            bound = env.bind(a.symbol_id, b.symbol_id)
            if bound is None:
                return
            e1 = bound
        yield from match_node(a.body, b.body, e1)
        return

    if isinstance(a, LawStmt) and isinstance(b, LawStmt):
        if a.role != b.role or len(a.given) != len(b.given):
            return
        for e1 in match_node(
            Ref(name=a.target, symbol_id=a.target_symbol),
            Ref(name=b.target, symbol_id=b.target_symbol),
            env,
        ):
            for e2 in _match_multiset(list(a.given), list(b.given), e1):
                yield from match_node(a.distribution, b.distribution, e2)
        return

    if isinstance(a, (AssumeStmt, RequireStmt, ProveStmt)) and isinstance(
        b, (AssumeStmt, RequireStmt, ProveStmt)
    ):
        yield from match_node(a.proposition, b.proposition, env)
        return

    if isinstance(a, ObjectiveStmt) and isinstance(b, ObjectiveStmt):
        if a.direction == b.direction:
            yield from match_node(a.expression, b.expression, env)
        return

    if isinstance(a, SolveStmt) and isinstance(b, SolveStmt):
        yield from _match_multiset(list(a.targets), list(b.targets), env)
        return

    if isinstance(a, InferStmt) and isinstance(b, InferStmt):
        if a.query == b.query:
            yield from _match_multiset(list(a.targets), list(b.targets), env)
        return

    if isinstance(a, CheckStmt) and isinstance(b, CheckStmt):
        if a.check_kind == b.check_kind and a.expected == b.expected:
            yield from match_node(a.subject, b.subject, env)
        return

    if isinstance(a, ConceptDecl) and isinstance(b, ConceptDecl):
        # A concept's name is a minted term, not a binder: it is part of the
        # object's identity, so it is compared by spelling.
        if a.name != b.name or sorted(a.extends) != sorted(b.extends):
            return
        if skeleton(a) != skeleton(b):
            return
        yield env
        return

    if isinstance(a, ModuleDecl) and isinstance(b, ModuleDecl):
        yield env
        return


def _content_statements(module: Module) -> list[Statement]:
    """Every statement except the module header.

    The module name is a label. Two modules that differ only in what they are
    called denote the same object, so the header is excluded here and the
    exclusion is reported as a tracked assumption by the scorer.
    """
    return [s for s in module.statements if not isinstance(s, ModuleDecl)]


def declared_names(module: Module) -> tuple[str, ...]:
    """The module-level vocabulary, sorted."""
    return tuple(
        sorted(
            s.name
            for s in module.statements
            if isinstance(s, (Declaration, DefineStmt, ConceptDecl)) and s.name
        )
    )


def strict_match(reference: Module, candidate: Module) -> Env | None:
    """Return a bijection making the modules identical, or None.

    Statements are matched as an unordered collection, pruned by skeleton, with
    backtracking. Returning None means *no such bijection was found*, which is a
    structural fact and not a claim about mathematics.

    When both modules declare the same vocabulary the bijection is required to
    preserve module-level names (see :class:`Env`). Refusing an equivalence that a
    free renaming would have found costs coverage; admitting one that swaps two
    named roles would be a false positive, and those are not traded for coverage.
    """
    left = _content_statements(reference)
    right = _content_statements(candidate)
    if len(left) != len(right):
        return None
    if sorted(skeleton(s) for s in left) != sorted(skeleton(s) for s in right):
        return None

    vocabulary = declared_names(reference)
    locked = bool(vocabulary) and vocabulary == declared_names(candidate)
    order = sorted(range(len(left)), key=lambda i: -len(skeleton(left[i])))

    def rec(idx: int, used: frozenset[int], env: Env) -> Env | None:
        if idx == len(order):
            return env
        i = order[idx]
        key = skeleton(left[i])
        for j, stmt in enumerate(right):
            if j in used or skeleton(stmt) != key:
                continue
            for e1 in match_node(left[i], stmt, env):
                got = rec(idx + 1, used | {j}, e1)
                if got is not None:
                    return got
        return None

    return rec(0, frozenset(), Env(names_locked=locked))


# ---------------------------------------------------------------------------
# Relaxed alignment
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Residual:
    """A point where the two trees diverge, with everything above it identical.

    ``binders`` lists the binder pairs in scope at the divergence, so a downstream
    tier can build free symbols for them consistently on both sides.
    """

    kind: str  # "expression" | "declared_type" | "declaration_kind" | "unpaired"
    path: str
    left: object
    right: object
    binders: tuple[tuple[SymbolId, SymbolId, Type | None], ...] = ()
    #: Inherited from the :class:`Pairing` that produced it. A guard must not
    #: refute on a residual whose pairing was a guess.
    confidence: str = "positional"
    #: True when this residual is a *part* of a larger expression that matched
    #: around it. Certifying a fragment is sound -- equal parts in identical
    #: contexts give equal wholes. **Refuting** from a fragment is not: ``b - b``
    #: and ``c - c`` differ in every part and are both zero. Only whole
    #: statement-level expressions may produce a negative verdict.
    fragment: bool = False

    @property
    def trustworthy(self) -> bool:
        return self.confidence in ("name", "exact_key", "unique_kind")

    @property
    def may_refute(self) -> bool:
        return self.trustworthy and not self.fragment

    def describe(self) -> str:
        left = show(self.left) if isinstance(self.left, Expr) else str(self.left)
        right = show(self.right) if isinstance(self.right, Expr) else str(self.right)
        return f"{self.path}: {left}  vs  {right}"


@dataclass(frozen=True)
class Pairing:
    """One matched statement pair and how confidently it was matched."""

    left: Statement
    right: Statement
    confidence: str  # "name" | "exact_key" | "unique_kind" | "positional"

    @property
    def trustworthy(self) -> bool:
        """Whether a *refuting* guard may rely on this pairing.

        A positional pairing between two same-kind statements is a guess. A guard
        that refuted on a guess would invent a false negative, which biases H1/H2
        downward -- the exact defect this package exists to remove.
        """
        return self.confidence in ("name", "exact_key", "unique_kind")


@dataclass(frozen=True)
class Alignment:
    """The relaxed correspondence between two modules."""

    env: Env
    pairings: tuple[Pairing, ...] = ()
    residuals: tuple[Residual, ...] = ()
    unpaired_left: tuple[Statement, ...] = ()
    unpaired_right: tuple[Statement, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.unpaired_left and not self.unpaired_right

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol_map": self.env.names(),
            "pairings": [
                {"confidence": p.confidence, "skeleton": skeleton(p.left)}
                for p in self.pairings
            ],
            "residuals": [r.describe() for r in self.residuals],
            "unpaired_left": [skeleton(s) for s in self.unpaired_left],
            "unpaired_right": [skeleton(s) for s in self.unpaired_right],
        }


def _stmt_name(s: Statement) -> str | None:
    return getattr(s, "name", None) if isinstance(s, (Declaration, DefineStmt, ConceptDecl)) else None


def _stmt_symbol(s: Statement) -> SymbolId | None:
    return getattr(s, "symbol_id", None)


def _group_key(s: Statement) -> str:
    if isinstance(s, Declaration):
        return f"Declaration:{s.kind}"
    if isinstance(s, ObjectiveStmt):
        return "ObjectiveStmt"
    if isinstance(s, LawStmt):
        return f"LawStmt:{s.role}"
    if isinstance(s, InferStmt):
        return f"InferStmt:{s.query}"
    if isinstance(s, (AssumeStmt, RequireStmt, ProveStmt)):
        # One group, so `assume P` and `prove P` can be *paired* and the difference
        # surfaced as a residual the epistemic guard reads. Leaving them in separate
        # groups would make them unpairable, and an unpaired statement is silently
        # undecided -- exactly the case that needs to be caught.
        return "Proposition"
    return type(s).__name__


def _pair_statements(
    left: Sequence[Statement], right: Sequence[Statement]
) -> tuple[list[Pairing], list[Statement], list[Statement]]:
    """Pair statements most-confident-first: by name, then exact key, then kind."""
    pending_l = list(left)
    pending_r = list(right)
    out: list[Pairing] = []

    def take(pred, confidence: str) -> None:
        for a in list(pending_l):
            match = next((b for b in pending_r if pred(a, b)), None)
            if match is not None:
                out.append(Pairing(a, match, confidence))
                pending_l.remove(a)
                pending_r.remove(match)

    take(
        lambda a, b: type(a) is type(b)
        and _stmt_name(a) is not None
        and _stmt_name(a) == _stmt_name(b),
        "name",
    )
    take(lambda a, b: skeleton(a) == skeleton(b), "exact_key")

    # Unique within its kind on both sides: the pairing is forced, not guessed.
    for a in list(pending_l):
        key = _group_key(a)
        same_l = [x for x in pending_l if _group_key(x) == key]
        same_r = [x for x in pending_r if _group_key(x) == key]
        if len(same_l) == 1 and len(same_r) == 1:
            out.append(Pairing(a, same_r[0], "unique_kind"))
            pending_l.remove(a)
            pending_r.remove(same_r[0])

    for a in list(pending_l):
        key = _group_key(a)
        match = next((b for b in pending_r if _group_key(b) == key), None)
        if match is not None:
            out.append(Pairing(a, match, "positional"))
            pending_l.remove(a)
            pending_r.remove(match)

    return out, pending_l, pending_r


def _collect_residuals(
    a: object,
    b: object,
    env: Env,
    path: str,
    binders: tuple[tuple[SymbolId, SymbolId, Type | None], ...],
    out: list[Residual],
    confidence: str,
    fragment: bool = False,
) -> Env:
    """Record where two trees diverge, descending only where descent is safe.

    Descent happens in exactly two places, both chosen because a *positive* result
    on the part gives a positive result on the whole:

    * through a matching quantifier prefix -- equivalent bodies give equivalent
      quantified formulas;
    * through the role arguments of a distribution of the same family -- equal
      arguments give the same law.

    It deliberately does **not** descend through arithmetic or propositional
    structure. Splitting ``b - b`` against ``c - c`` into ``b`` against ``c``
    would let a counterexample on the part refute a whole that is identically
    zero on both sides. Anything not descended into becomes one residual covering
    the entire statement-level expression, which is also the form the symbolic
    tier handles best.
    """
    if a is None and b is None:
        return env
    if a is None or b is None or type(a) is not type(b):
        out.append(Residual("expression", path, a, b, binders, confidence, fragment))
        return env

    # Fast path: this subtree matches exactly.
    for e1 in match_node(a, b, env):
        return e1

    if isinstance(a, Quantifier) and isinstance(b, Quantifier):
        if a.kind == b.kind and _type_key(a.var_type) == _type_key(b.var_type):
            e1 = env
            more = binders
            if a.symbol_id is not None and b.symbol_id is not None:
                bound = env.bind(a.symbol_id, b.symbol_id)
                if bound is None:
                    out.append(
                        Residual("expression", path, a, b, binders, confidence, fragment)
                    )
                    return env
                e1 = bound
                more = binders + ((a.symbol_id, b.symbol_id, a.var_type),)
            return _collect_residuals(
                a.body, b.body, e1, f"{path}.body", more, out, confidence, True
            )
        out.append(Residual("expression", path, a, b, binders, confidence, fragment))
        return env

    if isinstance(a, DistExpr) and isinstance(b, DistExpr) and a.family == b.family:
        ra = {x.role: x.value for x in a.args}
        rb = {x.role: x.value for x in b.args}
        if set(ra) == set(rb):
            e1 = env
            for role in sorted(ra):
                e1 = _collect_residuals(
                    ra[role], rb[role], e1, f"{path}.{role}", binders, out, confidence, True
                )
            return e1

    out.append(Residual("expression", path, a, b, binders, confidence, fragment))
    return env


def align(reference: Module, candidate: Module) -> Alignment:
    """Pair the two modules and record every divergence.

    Never raises and never concludes anything: it produces the correspondence that
    the guards and the symbolic tiers reason over.
    """
    left = _content_statements(reference)
    right = _content_statements(candidate)
    pairings, un_l, un_r = _pair_statements(left, right)

    env = Env()
    residuals: list[Residual] = []

    # Bind declared symbols first so expression residuals are interpreted under a
    # complete symbol map rather than a partial one.
    for p in pairings:
        sa, sb = _stmt_symbol(p.left), _stmt_symbol(p.right)
        if sa is not None and sb is not None:
            bound = env.bind(sa, sb)
            if bound is not None:
                env = bound

    for p in pairings:
        a, b, conf = p.left, p.right, p.confidence
        tag = f"{_group_key(a)}[{_stmt_name(a) or ''}]"
        if isinstance(a, Declaration) and isinstance(b, Declaration):
            if a.kind != b.kind:
                residuals.append(
                    Residual("declaration_kind", tag, a.kind, b.kind, confidence=conf)
                )
            if _type_key(a.declared_type) != _type_key(b.declared_type):
                residuals.append(
                    Residual(
                        "declared_type", tag, a.declared_type, b.declared_type, confidence=conf
                    )
                )
            env = _collect_residuals(
                a.value, b.value, env, f"{tag}.value", (), residuals, conf
            )
        elif isinstance(a, DefineStmt) and isinstance(b, DefineStmt):
            if _type_key(a.declared_type) != _type_key(b.declared_type):
                residuals.append(
                    Residual(
                        "declared_type", tag, a.declared_type, b.declared_type, confidence=conf
                    )
                )
            env = _collect_residuals(a.body, b.body, env, f"{tag}.body", (), residuals, conf)
        elif isinstance(a, (AssumeStmt, RequireStmt, ProveStmt)) and isinstance(
            b, (AssumeStmt, RequireStmt, ProveStmt)
        ):
            if type(a) is not type(b):
                residuals.append(
                    Residual(
                        "statement_kind",
                        tag,
                        type(a).__name__,
                        type(b).__name__,
                        confidence=conf,
                    )
                )
            else:
                env = _collect_residuals(
                    a.proposition, b.proposition, env, f"{tag}.proposition", (), residuals, conf
                )
        elif isinstance(a, ObjectiveStmt) and isinstance(b, ObjectiveStmt):
            if a.direction != b.direction:
                residuals.append(
                    Residual(
                        "objective_direction", tag, a.direction, b.direction, confidence=conf
                    )
                )
            env = _collect_residuals(
                a.expression, b.expression, env, f"{tag}.expression", (), residuals, conf
            )
        elif isinstance(a, LawStmt) and isinstance(b, LawStmt):
            if a.role != b.role:
                residuals.append(Residual("law_role", tag, a.role, b.role, confidence=conf))
            if len(a.given) != len(b.given):
                residuals.append(
                    Residual(
                        "conditioning_arity", tag, len(a.given), len(b.given), confidence=conf
                    )
                )
            env = _collect_residuals(
                a.distribution, b.distribution, env, f"{tag}.distribution", (), residuals, conf
            )
        elif not any(True for _ in itertools.islice(match_node(a, b, env), 1)):
            residuals.append(Residual("expression", tag, a, b, confidence=conf))
        else:
            for e1 in match_node(a, b, env):
                env = e1
                break

    return Alignment(env, tuple(pairings), tuple(residuals), tuple(un_l), tuple(un_r))
