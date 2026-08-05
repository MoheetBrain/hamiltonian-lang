"""Canonical JSON serialization and content hashing.

The canonical form is the *identity* of a Hamiltonian object. Two programs that differ
only by variable spelling, blank lines, or comments must produce byte-identical
canonical JSON and therefore the same hash. This is v0 success criterion 6 and is
property-tested in ``tests/roundtrip/``.

Achieved by:
  * emitting ``SymbolId.canonical()`` (``sym:#depth.ordinal``) rather than names;
  * sorting object keys;
  * dropping every source span;
  * tagging the schema version so a future change is detectable rather than silent.
"""

from __future__ import annotations

import hashlib
import json
from contextvars import ContextVar
from typing import Any

from ..ast.nodes import (
    AssumeStmt,
    BinOp,
    Call,
    CheckStmt,
    Comparison,
    ConceptDecl,
    ConceptMember,
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

__all__ = ["CANONICAL_VERSION", "to_canonical", "canonical_json", "content_hash"]

CANONICAL_VERSION = "hml-canonical-0.1.0"


#: When False, declaration names are omitted entirely so that a consistent renaming
#: produces byte-identical output. ``content_hash`` always serialises with names off:
#: identity is structural, and the spelling of a bound variable is not part of it
#: (v0 success criterion 6). Human-facing JSON keeps names for readability.
#: A ``ContextVar``, not a module global. The save/restore below is reentrancy-safe but
#: was **not thread-safe**: ``content_hash`` forces this False while serialising, so a
#: concurrent ``canonical_json(..., include_names=True)`` on another thread silently
#: returned the *nameless* form -- no exception, no diagnostic, just the wrong document.
#: Reproduced by the M1 reproducibility audit with 8 hasher threads and a 600-statement
#: module: 1 corrupted named canonical form. See D-024.
#:
#: A ContextVar has independent per-thread values and still restores correctly on the
#: token, so single-threaded behaviour is byte-identical to the global it replaces.
_INCLUDE_NAMES: ContextVar[bool] = ContextVar("hml_canonical_include_names", default=True)


def _sym(sid: SymbolId | None, *, keep_name: bool = False) -> Any:
    if sid is None:
        return None
    if keep_name and _INCLUDE_NAMES.get():
        return {"id": sid.canonical(), "name": sid.name}
    return sid.canonical()


def _params(params: list) -> Any:
    """Serialise a binder list.

    Parameter *names* are binders exactly like quantifier variables, so they must not
    appear in the hashed form or alpha-renaming a definition's parameter would change
    its identity. Positional order carries the meaning. (Red-team finding 1.9.)
    """
    if _INCLUDE_NAMES.get():
        return [{"name": n, "type": _type(t)} for n, t in params]
    return [{"type": _type(t)} for _, t in params]


def _type(t: Type | None) -> Any:
    return None if t is None else t.render()


def _expr(e: Expr | None) -> Any:
    if e is None:
        return None

    if isinstance(e, Literal):
        return {"kind": "Literal", "value": e.value, "type": _type(e.type_)}

    if isinstance(e, Ref):
        return {"kind": "Ref", "symbol": _sym(e.symbol_id), "type": _type(e.type_)}

    if isinstance(e, UnaryOp):
        return {
            "kind": "UnaryOp", "op": e.op, "operand": _expr(e.operand),
            "type": _type(e.type_),
        }

    if isinstance(e, BinOp):
        return {
            "kind": "BinOp", "op": e.op, "left": _expr(e.left),
            "right": _expr(e.right), "type": _type(e.type_),
        }

    if isinstance(e, Comparison):
        return {
            "kind": "Comparison", "op": e.op, "left": _expr(e.left),
            "right": _expr(e.right), "type": _type(e.type_),
        }

    if isinstance(e, LogicalOp):
        return {
            "kind": "LogicalOp", "op": e.op, "left": _expr(e.left),
            "right": _expr(e.right), "type": _type(e.type_),
        }

    if isinstance(e, Call):
        return {
            "kind": "Call", "callee": e.callee,
            "arguments": [_expr(a) for a in e.args], "type": _type(e.type_),
        }

    if isinstance(e, Index):
        return {
            "kind": "Index", "base": _expr(e.base),
            "indices": [_expr(i) for i in e.indices], "type": _type(e.type_),
        }

    if isinstance(e, DistExpr):
        # Roles are sorted so that argument *order* is not part of identity; the role
        # label carries the meaning, which is the point of D-003.
        return {
            "kind": "DistributionLaw",
            "family": e.family,
            "arguments": {a.role: _expr(a.value) for a in sorted(e.args, key=lambda x: x.role)},
            "type": _type(e.type_),
        }

    if isinstance(e, Quantifier):
        return {
            "kind": "Quantifier",
            "quantifier": e.kind,
            "binder": _sym(e.symbol_id),
            "binder_type": _type(e.var_type),
            "body": _expr(e.body),
            "type": _type(e.type_),
        }

    return {"kind": type(e).__name__}


def _member(m: ConceptMember) -> dict:
    return {
        "kind": m.kind,
        "name": m.name,
        "type": _type(m.declared_type),
        "parameters": _params(m.params),
        "body": _expr(m.body),
    }


def _statement(st: Statement) -> dict:
    if isinstance(st, ModuleDecl):
        return {"kind": "ModuleDecl", "name": st.name}

    if isinstance(st, Declaration):
        return {
            "kind": "Declaration",
            "declaration_kind": st.kind,
            "symbol": _sym(st.symbol_id, keep_name=True),
            "type": _type(st.declared_type),
            "value": _expr(st.value),
        }

    if isinstance(st, DefineStmt):
        return {
            "kind": "Definition",
            "symbol": _sym(st.symbol_id, keep_name=True),
            "type": _type(st.declared_type),
            "parameters": _params(st.params),
            "body": _expr(st.body),
        }

    if isinstance(st, LawStmt):
        return {
            "kind": "Law",
            "role": st.role,
            "target": _sym(st.target_symbol),
            "given": sorted(_sym(g.symbol_id) or "" for g in st.given),
            "distribution": _expr(st.distribution),
        }

    if isinstance(st, AssumeStmt):
        return {"kind": "Assumption", "proposition": _expr(st.proposition)}
    if isinstance(st, RequireStmt):
        return {"kind": "Constraint", "proposition": _expr(st.proposition)}
    if isinstance(st, ProveStmt):
        return {"kind": "Theorem", "proposition": _expr(st.proposition)}

    if isinstance(st, ObjectiveStmt):
        return {
            "kind": "Objective", "direction": st.direction,
            "expression": _expr(st.expression),
        }

    if isinstance(st, SolveStmt):
        return {"kind": "Solve", "targets": [_sym(t.symbol_id) for t in st.targets]}

    if isinstance(st, InferStmt):
        return {
            "kind": "Inference", "query": st.query,
            "targets": [_sym(t.symbol_id) for t in st.targets],
        }

    if isinstance(st, CheckStmt):
        return {
            "kind": "Check", "check_kind": st.check_kind,
            "subject": _expr(st.subject), "expected": st.expected,
        }

    if isinstance(st, ConceptDecl):
        return {
            "kind": "Concept",
            "name": st.name,
            "extends": sorted(st.extends),
            "members": [_member(m) for m in st.members],
        }

    return {"kind": type(st).__name__}


def to_canonical(
    module: Module, *, obligations: list | None = None, include_names: bool = True
) -> dict:
    token = _INCLUDE_NAMES.set(include_names)
    try:
        return _to_canonical(module, obligations)
    finally:
        _INCLUDE_NAMES.reset(token)


def _to_canonical(module: Module, obligations: list | None) -> dict:
    doc: dict[str, Any] = {
        "canonical_version": CANONICAL_VERSION,
        "module": module.name,
        "statements": [_statement(s) for s in module.statements
                       if not isinstance(s, ModuleDecl)],
    }
    if obligations is not None:
        doc["proof_obligations"] = [o.to_dict() for o in obligations]
    return doc


def canonical_json(
    module: Module, *, obligations: list | None = None, include_names: bool = True
) -> str:
    return json.dumps(
        to_canonical(module, obligations=obligations, include_names=include_names),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def content_hash(module: Module) -> str:
    """SHA-256 of the *nameless* canonical form.

    Names are excluded so that alpha-renaming is invisible to identity. Proof
    obligations are excluded too, because they carry source line numbers.
    """
    blob = canonical_json(module, include_names=False)
    return hashlib.sha256(blob.encode("ascii")).hexdigest()
