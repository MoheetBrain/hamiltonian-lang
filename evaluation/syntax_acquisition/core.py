"""Shared interface, frozen supported subset, and the information-parity normaliser.

Every candidate surface is a *projection* of one canonical Hamiltonian object. Three
properties are enforced here rather than left to each candidate's good behaviour,
because a fairness property that each candidate polices for itself is not a property:

1. **One subset.** :func:`validate_supported` is called by every renderer before it
   emits a byte. A construct outside the frozen subset raises
   :class:`UnsupportedConstruct` in all four candidates identically. No candidate can
   quietly support something the others drop, and none can silently drop something.

2. **One pipeline.** Every candidate's ``parse`` returns an *unresolved* ``Module``.
   Name resolution and type checking are then run by :func:`recover` from the shared
   compiler. A candidate cannot pre-resolve a reference or pre-annotate a type, because
   it never gets to run either stage.

3. **One information content.** :func:`declared_content` normalises an unresolved
   ``Module`` to exactly what an author writes down -- names, declared types, literals,
   operators, roles, structure -- discarding everything the checker derives. All four
   candidates must produce a byte-identical ``declared_content`` for the same object.
   That is the mechanical statement of "no candidate receives additional mathematical
   information".
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from hamiltonian_lang.ast.nodes import (
    Arg,
    AssumeStmt,
    BinOp,
    Call,
    CheckStmt,
    Comparison,
    ConceptDecl,
    ConceptMember,
    Declaration,
    DeclKind,
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
from hamiltonian_lang.backends.canonical import content_hash
from hamiltonian_lang.diagnostics import DiagnosticBag
from hamiltonian_lang.lexer import KEYWORDS
from hamiltonian_lang.semantics import resolve
from hamiltonian_lang.type_system import check
from hamiltonian_lang.types import (
    ConceptType,
    Dimension,
    DistributionType,
    FunctionType,
    MatrixType,
    PredicateType,
    PropositionType,
    QuantityType,
    RandomVariableType,
    ScalarType,
    SetType,
    TensorType,
    Type,
    VectorType,
)

__all__ = [
    "FROZEN_SUBSET_VERSION",
    "UnsupportedConstruct",
    "SurfaceParseError",
    "SyntaxCandidate",
    "RoundTripOutcome",
    "validate_supported",
    "declared_content",
    "recover",
    "round_trip",
    "CANDIDATES",
    "candidate",
    "DECL_KINDS",
    "LAW_ROLES",
    "INFER_QUERIES",
    "MEMBER_KINDS",
    "BINARY_OPS",
    "COMPARISON_OPS",
    "LOGICAL_OPS",
    "UNARY_OPS",
    "QUANTIFIER_KINDS",
]

#: Bumped whenever the frozen supported subset changes. A round-trip figure quoted
#: against one version is not comparable with a figure quoted against another.
FROZEN_SUBSET_VERSION = "hml-fg001-subset-1.0.0"

#: Words that candidate B reserves and HML-L1 does not. A name free in one surface and
#: reserved in another would make the supported subset surface-dependent, and a subset
#: that differs per candidate is not a subset. The union is excluded everywhere.
#: Candidates C and D reserve nothing at identifier positions: C's special words occur
#: only as list heads and D's only as JSON keys.
SURFACE_B_RESERVED = frozenset(
    {"mod", "dec", "fun", "dist", "say", "opt", "ask", "kind", "all", "some", "one"}
)

RESERVED_IN_ANY_SURFACE = frozenset(KEYWORDS) | SURFACE_B_RESERVED

DECL_KINDS = (
    DeclKind.VAR,
    DeclKind.PARAM,
    DeclKind.CONST,
    DeclKind.OBS,
    DeclKind.INDEX,
    DeclKind.RANDOM,
)
LAW_ROLES = ("law", "prior", "likelihood")
INFER_QUERIES = ("posterior", "expectation", "variance", "mle", "map")
OBJECTIVE_DIRECTIONS = ("minimise", "maximise")
CHECK_KINDS = ("proposition", "dimension")
MEMBER_KINDS = (
    "parameter",
    "transform",
    "invariant",
    "property",
    "example",
    "counterexample",
)
BINARY_OPS = ("+", "-", "*", "/", "^", "@")
COMPARISON_OPS = ("=", "!=", "<", "<=", ">", ">=")
LOGICAL_OPS = ("and", "or", "implies", "iff")
UNARY_OPS = ("-", "not")
QUANTIFIER_KINDS = ("forall", "exists", "exists_unique")


class UnsupportedConstruct(Exception):
    """A construct outside the frozen subset reached a renderer.

    Raised, never worked around. A renderer that silently omitted the construct would
    produce authoritative-looking output that is wrong, which ``CLAUDE.md`` names as the
    worst failure mode in this codebase.
    """

    def __init__(self, surface: str, what: str, detail: str = "") -> None:
        self.surface = surface
        self.what = what
        self.detail = detail
        super().__init__(f"[{surface}] cannot express {what}" + (f": {detail}" if detail else ""))


class SurfaceParseError(Exception):
    """A candidate's parser rejected its input.

    Carries the diagnostics when the candidate delegates to the HML-L1 compiler front
    end, and a plain message when the candidate has its own reader.
    """

    def __init__(self, surface: str, message: str, diagnostics: DiagnosticBag | None = None) -> None:
        self.surface = surface
        self.diagnostics = diagnostics
        super().__init__(f"[{surface}] {message}")


# ---------------------------------------------------------------------------
# The frozen supported subset
# ---------------------------------------------------------------------------


def _bad(surface: str, what: str, detail: str = "") -> UnsupportedConstruct:
    return UnsupportedConstruct(surface, what, detail)


def _validate_identifier(surface: str, name: str, role: str) -> None:
    if not name:
        raise _bad(surface, f"an empty {role}")
    if not (name[0].isalpha() or name[0] == "_") or not name.isascii():
        raise _bad(surface, f"the {role} {name!r}", "identifiers are ASCII [A-Za-z_][A-Za-z0-9_]*")
    if not all(c.isalnum() or c == "_" for c in name) or not name.isascii():
        raise _bad(surface, f"the {role} {name!r}", "identifiers are ASCII [A-Za-z_][A-Za-z0-9_]*")
    if name in RESERVED_IN_ANY_SURFACE:
        raise _bad(
            surface, f"the {role} {name!r}", "the name is reserved in at least one surface"
        )


def _validate_type(surface: str, t: Type | None, *, allow_none: bool, where: str) -> None:
    if t is None:
        if allow_none:
            return
        raise _bad(surface, f"an unannotated {where}", "every binder needs an explicit type")
    if isinstance(t, ScalarType | PropositionType):
        return
    if isinstance(t, QuantityType):
        if t.base != ScalarType("Real"):
            raise _bad(surface, f"Quantity with base {t.base.render()}", "no surface syntax exists")
        _validate_dimension(surface, t.dimension)
        return
    if isinstance(t, VectorType):
        _validate_type(surface, t.element, allow_none=False, where=where)
        _validate_extent(surface, t.length)
        return
    if isinstance(t, MatrixType):
        _validate_type(surface, t.element, allow_none=False, where=where)
        if t.rows is None and t.cols is not None:
            # An unknown extent is written by omission, and omission is positional, so
            # a known column extent cannot follow an unknown row extent.
            raise _bad(
                surface,
                "a Matrix with an unknown row extent and a known column extent",
                "an unknown extent can only be written by omitting it, which is positional",
            )
        _validate_extent(surface, t.rows)
        _validate_extent(surface, t.cols)
        return
    if isinstance(t, TensorType):
        _validate_type(surface, t.element, allow_none=False, where=where)
        if not t.shape:
            raise _bad(surface, "a Tensor with an empty shape")
        if any(d is None for d in t.shape):
            raise _bad(
                surface,
                "a Tensor with an unknown extent",
                "'?' is not a lexable token in HML-L1, so an unknown extent has no spelling here",
            )
        for d in t.shape:
            _validate_extent(surface, d)
        return
    if isinstance(t, SetType):
        _validate_type(surface, t.element, allow_none=False, where=where)
        return
    if isinstance(t, FunctionType):
        if not t.domain:
            raise _bad(surface, "Function with an empty domain", "no surface syntax exists")
        for d in t.domain:
            _validate_type(surface, d, allow_none=False, where=where)
        _validate_type(surface, t.codomain, allow_none=False, where=where)
        return
    if isinstance(t, PredicateType):
        if not t.domain:
            raise _bad(surface, "Predicate with an empty domain", "no surface syntax exists")
        for d in t.domain:
            _validate_type(surface, d, allow_none=False, where=where)
        return
    if isinstance(t, RandomVariableType):
        _validate_type(surface, t.codomain, allow_none=False, where=where)
        return
    if isinstance(t, DistributionType):
        _validate_type(surface, t.support, allow_none=False, where=where)
        return
    if isinstance(t, ConceptType):
        _validate_identifier(surface, t.name, "concept type name")
        return
    raise _bad(surface, f"the type {type(t).__name__}")


def _validate_extent(surface: str, e: str | int | None) -> None:
    if e is None or isinstance(e, int):
        return
    _validate_identifier(surface, e, "shape extent")


def _validate_dimension(surface: str, d: Dimension) -> None:
    for _, exp in tuple(d.exponents) + tuple(d.variables):
        if not isinstance(exp, Fraction):
            raise _bad(surface, "a non-rational dimension exponent")


def _validate_expr(surface: str, e: Expr | None, *, where: str) -> None:
    if e is None:
        raise _bad(surface, f"a missing expression in {where}")
    if isinstance(e, Literal):
        v = e.value
        if isinstance(v, bool):
            return
        if isinstance(v, int | float):
            if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
                raise _bad(surface, "a non-finite literal", repr(v))
            if v < 0:
                # No surface has a negative numeric token: `-3` lexes as unary minus
                # applied to `3`, which is a different tree. Rejected rather than
                # emitted as something that reads back differently.
                raise _bad(
                    surface,
                    "a negative numeric literal",
                    "negation is a UnaryOp in every surface, not part of the token",
                )
            return
        raise _bad(surface, f"a literal of Python type {type(v).__name__}")
    if isinstance(e, Ref):
        _validate_identifier(surface, e.name, "reference")
        return
    if isinstance(e, UnaryOp):
        if e.op not in UNARY_OPS:
            raise _bad(surface, f"the unary operator {e.op!r}")
        _validate_expr(surface, e.operand, where=where)
        return
    if isinstance(e, BinOp):
        if e.op not in BINARY_OPS:
            raise _bad(surface, f"the binary operator {e.op!r}")
        _validate_expr(surface, e.left, where=where)
        _validate_expr(surface, e.right, where=where)
        return
    if isinstance(e, Comparison):
        if e.op not in COMPARISON_OPS:
            raise _bad(surface, f"the comparison operator {e.op!r}")
        _validate_expr(surface, e.left, where=where)
        _validate_expr(surface, e.right, where=where)
        return
    if isinstance(e, LogicalOp):
        if e.op not in LOGICAL_OPS:
            raise _bad(surface, f"the logical operator {e.op!r}")
        _validate_expr(surface, e.left, where=where)
        _validate_expr(surface, e.right, where=where)
        return
    if isinstance(e, Call):
        _validate_identifier(surface, e.callee, "callee")
        for a in e.args:
            if isinstance(a, Arg):
                raise _bad(
                    surface,
                    "a role-labelled ordinary function call",
                    "role labels apply to DistExpr only in v0 (Q-05)",
                )
            _validate_expr(surface, a, where=where)
        return
    if isinstance(e, Index):
        _validate_expr(surface, e.base, where=where)
        if not e.indices:
            raise _bad(surface, "an index with no subscripts")
        for i in e.indices:
            _validate_expr(surface, i, where=where)
        return
    if isinstance(e, DistExpr):
        if not e.args:
            # In law position `theta ~ Beta` is a DistExpr with no arguments; in
            # expression position the same text lexes as a plain reference. The two are
            # different trees, so a bare family is only expressible as a law right-hand
            # side. Rejected here; permitted by `_validate_dist_head`.
            raise _bad(
                surface,
                "a distribution with no arguments outside law position",
                "the same text reads back as a Ref",
            )
        _validate_dist_head(surface, e, where=where)
        return
    if isinstance(e, Quantifier):
        if e.kind not in QUANTIFIER_KINDS:
            raise _bad(surface, f"the quantifier {e.kind!r}")
        _validate_identifier(surface, e.var, "quantified variable")
        _validate_type(surface, e.var_type, allow_none=False, where="quantified variable")
        _validate_expr(surface, e.body, where=where)
        return
    raise _bad(surface, f"the expression node {type(e).__name__}")


def _validate_dist_head(surface: str, e: DistExpr, *, where: str) -> None:
    _validate_identifier(surface, e.family, "distribution family")
    seen: set[str] = set()
    for a in e.args:
        if a.role in seen:
            raise _bad(surface, f"a repeated role {a.role!r} on {e.family}")
        seen.add(a.role)
        _validate_identifier(surface, a.role, "parameter role")
        _validate_expr(surface, a.value, where=where)


def _validate_member(surface: str, m: ConceptMember) -> None:
    if m.kind not in MEMBER_KINDS:
        raise _bad(surface, f"the concept member kind {m.kind!r}")
    _validate_identifier(surface, m.name, "concept member name")
    for pname, ptype in m.params:
        _validate_identifier(surface, pname, "transform parameter")
        # HML-P214: a transform parameter must carry an explicit type. A surface that
        # emitted a bare name here would produce source the HML-L1 parser rejects.
        _validate_type(surface, ptype, allow_none=False, where="transform parameter")
    _validate_type(surface, m.declared_type, allow_none=True, where="concept member")
    if m.body is not None:
        _validate_expr(surface, m.body, where=f"concept {m.kind}")


def _validate_statement(surface: str, st: Statement) -> None:
    if isinstance(st, ModuleDecl):
        _validate_identifier(surface, st.name, "module name")
        return
    if isinstance(st, Declaration):
        if st.kind not in DECL_KINDS:
            raise _bad(surface, f"the declaration kind {st.kind!r}")
        _validate_identifier(surface, st.name, "declared name")
        _validate_type(surface, st.declared_type, allow_none=False, where="declaration")
        if st.value is not None:
            _validate_expr(surface, st.value, where="declaration initialiser")
        return
    if isinstance(st, DefineStmt):
        _validate_identifier(surface, st.name, "definition name")
        for pname, ptype in st.params:
            _validate_identifier(surface, pname, "definition parameter")
            _validate_type(surface, ptype, allow_none=True, where="definition parameter")
        _validate_type(surface, st.declared_type, allow_none=True, where="definition")
        _validate_expr(surface, st.body, where="definition body")
        return
    if isinstance(st, LawStmt):
        if st.role not in LAW_ROLES:
            raise _bad(surface, f"the law role {st.role!r}")
        _validate_identifier(surface, st.target, "law target")
        for g in st.given:
            _validate_identifier(surface, g.name, "conditioning reference")
        if st.distribution is None:
            raise _bad(surface, "a law with no distribution")
        _validate_dist_head(surface, st.distribution, where="law")
        return
    if isinstance(st, AssumeStmt):
        _validate_expr(surface, st.proposition, where="assume")
        return
    if isinstance(st, RequireStmt):
        if st.label is not None:
            raise _bad(surface, "a labelled 'require'", "HML-L1 has no surface syntax for the label")
        _validate_expr(surface, st.proposition, where="require")
        return
    if isinstance(st, ProveStmt):
        if st.label is not None:
            raise _bad(surface, "a labelled 'prove'", "HML-L1 has no surface syntax for the label")
        _validate_expr(surface, st.proposition, where="prove")
        return
    if isinstance(st, ObjectiveStmt):
        if st.direction not in OBJECTIVE_DIRECTIONS:
            raise _bad(surface, f"the objective direction {st.direction!r}")
        _validate_expr(surface, st.expression, where="objective")
        return
    if isinstance(st, SolveStmt):
        if not st.targets:
            raise _bad(surface, "'solve' with no targets")
        for t in st.targets:
            _validate_identifier(surface, t.name, "solve target")
        return
    if isinstance(st, InferStmt):
        if st.query not in INFER_QUERIES:
            raise _bad(surface, f"the inference query {st.query!r}")
        if not st.targets:
            raise _bad(surface, "'infer' with no targets")
        for t in st.targets:
            _validate_identifier(surface, t.name, "infer target")
        return
    if isinstance(st, CheckStmt):
        if st.check_kind not in CHECK_KINDS:
            # `check_kind == "type"` exists in ast/nodes.py but the HML-L1 grammar has no
            # production for it, so no surface can express it. Reported, not dropped.
            raise _bad(
                surface,
                f"the check kind {st.check_kind!r}",
                "the HML-L1 grammar has no production for it",
            )
        if st.subject is None:
            raise _bad(surface, "a 'check' with no subject")
        _validate_expr(surface, st.subject, where="check")
        if st.check_kind == "dimension" and st.expected is not None and not st.expected:
            raise _bad(surface, "a 'check dimension' with an empty expected dimension")
        return
    if isinstance(st, ConceptDecl):
        _validate_identifier(surface, st.name, "concept name")
        for base in st.extends:
            _validate_identifier(surface, base, "extended concept name")
        for m in st.members:
            _validate_member(surface, m)
        return
    raise _bad(surface, f"the statement node {type(st).__name__}")


def validate_supported(module: Module, surface: str = "shared") -> None:
    """Raise :class:`UnsupportedConstruct` for anything outside the frozen subset.

    Called by all four renderers with the same rules, so the subset is a property of the
    phase and not of any individual candidate.
    """
    _validate_identifier(surface, module.name, "module name")
    for st in module.statements:
        _validate_statement(surface, st)


# ---------------------------------------------------------------------------
# Information parity
# ---------------------------------------------------------------------------


def _dc_type(t: Type | None) -> Any:
    #: ``Type.render()`` is the canonical spelling and is surface-independent, so two
    #: surfaces that wrote the same type in different notation normalise to one string.
    return None if t is None else t.render()


def _dc_expr(e: Expr | None) -> Any:
    if e is None:
        return None
    if isinstance(e, Literal):
        # The Python type is kept: the canonical form distinguishes the integer 1 from
        # the real 1.0, so a surface that lost the distinction would change identity.
        kind = "bool" if isinstance(e.value, bool) else type(e.value).__name__
        return {"n": "literal", "value": e.value, "value_type": kind}
    if isinstance(e, Ref):
        return {"n": "ref", "name": e.name}
    if isinstance(e, UnaryOp):
        return {"n": "unary", "op": e.op, "operand": _dc_expr(e.operand)}
    if isinstance(e, BinOp):
        return {"n": "binary", "op": e.op, "left": _dc_expr(e.left), "right": _dc_expr(e.right)}
    if isinstance(e, Comparison):
        return {"n": "compare", "op": e.op, "left": _dc_expr(e.left), "right": _dc_expr(e.right)}
    if isinstance(e, LogicalOp):
        return {"n": "logical", "op": e.op, "left": _dc_expr(e.left), "right": _dc_expr(e.right)}
    if isinstance(e, Call):
        return {"n": "call", "callee": e.callee, "args": [_dc_expr(a) for a in e.args]}
    if isinstance(e, Index):
        return {"n": "index", "base": _dc_expr(e.base), "indices": [_dc_expr(i) for i in e.indices]}
    if isinstance(e, DistExpr):
        # Written order is preserved rather than sorted: the canonical form sorts roles,
        # so if one surface reordered arguments the round trip would still pass. Keeping
        # the written order here makes such a reordering visible to the parity test.
        return {
            "n": "dist",
            "family": e.family,
            "args": [{"role": a.role, "value": _dc_expr(a.value)} for a in e.args],
        }
    if isinstance(e, Quantifier):
        return {
            "n": "quantifier",
            "kind": e.kind,
            "var": e.var,
            "var_type": _dc_type(e.var_type),
            "body": _dc_expr(e.body),
        }
    raise UnsupportedConstruct("parity", f"the expression node {type(e).__name__}")


def _dc_params(params: list[tuple[str, Type | None]]) -> Any:
    return [{"name": n, "type": _dc_type(t)} for n, t in params]


def _dc_statement(st: Statement) -> Any:
    if isinstance(st, ModuleDecl):
        return {"n": "module", "name": st.name}
    if isinstance(st, Declaration):
        return {
            "n": "declaration",
            "kind": st.kind,
            "name": st.name,
            "type": _dc_type(st.declared_type),
            "value": _dc_expr(st.value) if st.value is not None else None,
        }
    if isinstance(st, DefineStmt):
        return {
            "n": "definition",
            "name": st.name,
            "params": _dc_params(st.params),
            "type": _dc_type(st.declared_type),
            "body": _dc_expr(st.body),
        }
    if isinstance(st, LawStmt):
        return {
            "n": "law",
            "role": st.role,
            "target": st.target,
            "given": [g.name for g in st.given],
            "distribution": _dc_expr(st.distribution),
        }
    if isinstance(st, AssumeStmt):
        return {"n": "assume", "proposition": _dc_expr(st.proposition)}
    if isinstance(st, RequireStmt):
        return {"n": "require", "proposition": _dc_expr(st.proposition)}
    if isinstance(st, ProveStmt):
        return {"n": "prove", "proposition": _dc_expr(st.proposition)}
    if isinstance(st, ObjectiveStmt):
        return {"n": "objective", "direction": st.direction, "expression": _dc_expr(st.expression)}
    if isinstance(st, SolveStmt):
        return {"n": "solve", "targets": [t.name for t in st.targets]}
    if isinstance(st, InferStmt):
        return {"n": "infer", "query": st.query, "targets": [t.name for t in st.targets]}
    if isinstance(st, CheckStmt):
        return {
            "n": "check",
            "check_kind": st.check_kind,
            "subject": _dc_expr(st.subject),
            "expected": st.expected,
        }
    if isinstance(st, ConceptDecl):
        return {
            "n": "concept",
            "name": st.name,
            "extends": list(st.extends),
            "members": [
                {
                    "kind": m.kind,
                    "name": m.name,
                    "params": _dc_params(m.params),
                    "type": _dc_type(m.declared_type),
                    "body": _dc_expr(m.body) if m.body is not None else None,
                }
                for m in st.members
            ],
        }
    raise UnsupportedConstruct("parity", f"the statement node {type(st).__name__}")


def declared_content(module: Module) -> str:
    """What an author writes down, normalised and surface-independent.

    Keeps names, declared types, literal values *and their numeric kind*, operators,
    distribution families and roles, and every structural nesting relation. Discards
    spans, ``SymbolId``s, inferred ``type_`` annotations, and notation.

    Two surfaces agree on ``declared_content`` exactly when they carry the same
    mathematical content for a reader to work from. That is the operational definition
    of the fairness constraint for this phase.
    """
    doc = {
        "parity_version": FROZEN_SUBSET_VERSION,
        "module": module.name,
        "statements": [_dc_statement(s) for s in module.statements if not isinstance(s, ModuleDecl)],
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def derived_facts_present(module: Module) -> dict[str, int]:
    """Count the checker-derived annotations carried by ``module``.

    A candidate's ``parse`` must return a module with all of these at zero: everything
    counted here is something the shared resolver and checker are supposed to compute.
    A surface that supplied any of it would be handing the reader an answer the other
    three surfaces have to derive.
    """
    counts = {"symbol_ids": 0, "inferred_types": 0}
    stack: list[Any] = [module]
    seen: set[int] = set()
    while stack:
        n = stack.pop()
        if id(n) in seen:
            continue
        seen.add(id(n))
        if isinstance(n, Ref | Declaration | DefineStmt | Quantifier | ConceptDecl):
            if getattr(n, "symbol_id", None) is not None:
                counts["symbol_ids"] += 1
        if isinstance(n, LawStmt) and n.target_symbol is not None:
            counts["symbol_ids"] += 1
        if hasattr(n, "type_") and getattr(n, "type_", None) is not None:
            counts["inferred_types"] += 1
        if isinstance(n, Module | Statement | Expr | Arg | ConceptMember):
            for value in vars(n).values():
                if isinstance(value, Module | Statement | Expr | Arg | ConceptMember):
                    stack.append(value)
                elif isinstance(value, list):
                    stack.extend(
                        v for v in value if isinstance(v, Module | Statement | Expr | Arg | ConceptMember)
                    )
    return counts


# ---------------------------------------------------------------------------
# The candidate interface
# ---------------------------------------------------------------------------


class SyntaxCandidate(ABC):
    """One surface: a deterministic renderer and a parser back to the same object."""

    #: Single-letter identity used in reports and filenames.
    id: str = "?"
    #: Human-readable name.
    name: str = ""
    #: Short description of the surface family.
    family: str = ""

    @abstractmethod
    def render(self, module: Module) -> str:
        """Serialise ``module`` to this surface. Byte-identical on repeated calls."""

    @abstractmethod
    def parse(self, text: str) -> Module:
        """Read this surface back to an **unresolved** ``Module``.

        Must raise :class:`SurfaceParseError` on malformed input and must never return
        a partially-populated module: a surface that silently accepts damage is worse
        than one that rejects valid input.
        """

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<candidate {self.id}: {self.name}>"


@dataclass
class RoundTripOutcome:
    candidate_id: str
    object_id: str
    ok: bool
    stage: str  # render | parse | resolve | check | hash | parity
    original_hash: str
    recovered_hash: str | None
    detail: str
    rendered: str
    render_bytes: int


def recover(cand: SyntaxCandidate, module: Module) -> tuple[str, Module, DiagnosticBag]:
    """Render ``module`` in ``cand``'s surface, read it back, resolve and type-check it.

    Resolution and checking come from the shared compiler, identically for all four
    candidates, so no surface can shortcut either stage.
    """
    text = cand.render(module)
    parsed = cand.parse(text)
    bag = DiagnosticBag(text, f"<candidate-{cand.id}>")
    symbols = resolve(parsed, bag)
    if bag.ok():
        check(parsed, symbols, bag)
    return text, parsed, bag


def round_trip(cand: SyntaxCandidate, module: Module, object_id: str = "") -> RoundTripOutcome:
    """One cell of the round-trip matrix. Never raises; reports the failing stage."""
    original = content_hash(module)
    try:
        text = cand.render(module)
    except UnsupportedConstruct as exc:
        return RoundTripOutcome(cand.id, object_id, False, "render", original, None, str(exc), "", 0)
    except Exception as exc:  # noqa: BLE001 - a renderer crash is a reportable result
        return RoundTripOutcome(
            cand.id, object_id, False, "render", original, None,
            f"{type(exc).__name__}: {exc}", "", 0,
        )

    if text != cand.render(module):
        return RoundTripOutcome(
            cand.id, object_id, False, "render", original, None,
            "rendering is not deterministic", text, len(text),
        )

    try:
        parsed = cand.parse(text)
    except SurfaceParseError as exc:
        return RoundTripOutcome(
            cand.id, object_id, False, "parse", original, None, str(exc), text, len(text)
        )
    except Exception as exc:  # noqa: BLE001
        return RoundTripOutcome(
            cand.id, object_id, False, "parse", original, None,
            f"{type(exc).__name__}: {exc}", text, len(text),
        )

    leaked = derived_facts_present(parsed)
    if any(leaked.values()):
        return RoundTripOutcome(
            cand.id, object_id, False, "parity", original, None,
            f"parse returned checker-derived facts: {leaked}", text, len(text),
        )

    bag = DiagnosticBag(text, f"<candidate-{cand.id}>")
    symbols = resolve(parsed, bag)
    if not bag.ok():
        return RoundTripOutcome(
            cand.id, object_id, False, "resolve", original, None,
            "; ".join(f"{d.code} {d.message}" for d in bag.errors), text, len(text),
        )
    check(parsed, symbols, bag)
    if not bag.ok():
        return RoundTripOutcome(
            cand.id, object_id, False, "check", original, None,
            "; ".join(f"{d.code} {d.message}" for d in bag.errors), text, len(text),
        )

    recovered = content_hash(parsed)
    if recovered != original:
        return RoundTripOutcome(
            cand.id, object_id, False, "hash", original, recovered,
            "canonical hash changed across the round trip", text, len(text),
        )
    return RoundTripOutcome(cand.id, object_id, True, "ok", original, recovered, "", text, len(text))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def _build_registry() -> dict[str, SyntaxCandidate]:
    from .candidate_a import CandidateA
    from .candidate_b import CandidateB
    from .candidate_c import CandidateC
    from .candidate_d import CandidateD

    return {c.id: c for c in (CandidateA(), CandidateB(), CandidateC(), CandidateD())}


class _Registry(dict):
    """Lazy registry so that ``core`` stays importable from each candidate module."""

    def _ensure(self) -> None:
        if not dict.__len__(self):
            dict.update(self, _build_registry())

    def __getitem__(self, key: str) -> SyntaxCandidate:
        self._ensure()
        return dict.__getitem__(self, key)

    def __iter__(self):
        self._ensure()
        return dict.__iter__(self)

    def __len__(self) -> int:
        self._ensure()
        return dict.__len__(self)

    def items(self):
        self._ensure()
        return dict.items(self)

    def values(self):
        self._ensure()
        return dict.values(self)

    def keys(self):
        self._ensure()
        return dict.keys(self)


CANDIDATES: dict[str, SyntaxCandidate] = _Registry()


def candidate(cid: str) -> SyntaxCandidate:
    return CANDIDATES[cid]
