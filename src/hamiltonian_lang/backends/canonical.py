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
    ClaimId,
    Comparison,
    ConceptDecl,
    ConceptMember,
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
    Statement,
    SymbolId,
    UnaryOp,
    uses_v2,
)
from ..types import Type

__all__ = [
    "CANONICAL_VERSION",
    "CANONICAL_VERSION_V2",
    "to_canonical",
    "canonical_json",
    "content_hash",
    "expr_identity",
]

CANONICAL_VERSION = "hml-canonical-0.1.0"

#: Emitted **only** for modules that actually use a V2 reasoning construct.
#:
#: This is the mechanism that satisfies directive §28. A v1 module's canonical document
#: is byte-for-byte what it was before V2 existed -- same schema tag, same keys, same
#: hash -- so every ACQ0/H2 record stays reconstructible under its original language
#: version. The version is a property of the *document*, not of the compiler that
#: produced it. A blanket bump would have invalidated the existing scientific evidence
#: for no semantic reason, which is the failure §28 exists to prevent.
CANONICAL_VERSION_V2 = "hml-canonical-0.2.0"


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


def _claim(cid: ClaimId | None) -> Any:
    """Serialise a claim label by ordinal, never by spelling.

    Exactly the treatment ``_sym`` gives value symbols, and for the same reason:
    renaming ``d1`` to ``step_one`` throughout must not change what the module means.
    Alpha-equivalence has to hold for the reasoning graph too, or the canonical hash
    would report two identical proofs as different.
    """
    if cid is None:
        return None
    if _INCLUDE_NAMES.get():
        return {"id": cid.canonical(), "name": cid.name}
    return cid.canonical()


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

    # -- V2 mathematical expression coverage (D-026) ------------------------
    #
    # Every one of these MUST be here. The fallthrough at the bottom of this function
    # emits `{"kind": "<ClassName>"}` and nothing else, so a missing branch would give
    # every instance of a form the SAME canonical identity -- `integral(f, x, 0, 1)`
    # and `integral(g, y, 2, 3)` would hash equal and the reasoning kernel would treat
    # one as a proof of the other. That is a silent identity collapse, not a rendering
    # gap, which is why `tests/semantics/test_v2_expressions.py` asserts by construction
    # that no `Expr` subclass reaches the fallthrough.

    if isinstance(e, MomentExpr):
        # `given` is SORTED. Conditioning on Y and Z generates one sigma-algebra
        # however the two are ordered, exactly as `Law.given` is sorted for the same
        # reason. `body` is not, because there is only one.
        return {
            "kind": "Moment",
            "moment": e.kind,
            "body": _expr(e.body),
            "given": _sorted_exprs(e.given),
            "type": _type(e.type_),
        }

    if isinstance(e, ProbabilityExpr):
        return {
            "kind": "Probability",
            "event": _expr(e.event),
            "given": _sorted_exprs(e.given),
            "type": _type(e.type_),
        }

    if isinstance(e, JointExpr):
        # ORDERED, unlike independence below. The type is `Product[T1, T2]` and a
        # product is ordered: the first component of a pair is not the second.
        return {
            "kind": "Joint",
            "components": [_expr(p) for p in e.parts],
            "type": _type(e.type_),
        }

    if isinstance(e, IndependenceExpr):
        # SORTED in both lists: independence is symmetric in its operands and in its
        # conditioning set, so `independent(X, Y)` and `independent(Y, X)` are one
        # claim and must be one identity.
        return {
            "kind": "Independence",
            "operands": _sorted_exprs(e.parts),
            "given": _sorted_exprs(e.given),
            "type": _type(e.type_),
        }

    if isinstance(e, MembershipExpr):
        return {
            "kind": "Membership",
            "element": _expr(e.element),
            "collection": _expr(e.collection),
            "type": _type(e.type_),
        }

    if isinstance(e, SetComprehension):
        return {
            "kind": "SetComprehension",
            "binder": _sym(e.symbol_id),
            "binder_type": _type(e.var_type),
            "predicate": _expr(e.predicate),
            "type": _type(e.type_),
        }

    if isinstance(e, LimitExpr):
        return {
            "kind": "Limit",
            "binder": _sym(e.symbol_id),
            "binder_type": _type(e.var_type),
            "body": _expr(e.body),
            "point": _expr(e.point),
            "type": _type(e.type_),
        }

    if isinstance(e, DerivativeExpr):
        return {
            "kind": "Derivative",
            "binder": _sym(e.symbol_id),
            "binder_type": _type(e.var_type),
            "body": _expr(e.body),
            "type": _type(e.type_),
        }

    if isinstance(e, IntegralExpr):
        return {
            "kind": "Integral",
            "binder": _sym(e.symbol_id),
            "binder_type": _type(e.var_type),
            "body": _expr(e.body),
            "lower": _expr(e.lower),
            "upper": _expr(e.upper),
            "type": _type(e.type_),
        }

    if isinstance(e, ContinuityExpr):
        return {
            "kind": "Continuity",
            "function": _expr(e.function),
            "domain": _expr(e.domain),
            "type": _type(e.type_),
        }

    if isinstance(e, RelationExpr):
        # The `relation` key is what keeps `correlated(X, Y)` and `causes(X, Y)` apart,
        # and the conditional sort is what keeps `causes(X, Y)` apart from
        # `causes(Y, X)` while identifying `correlated(X, Y)` with `correlated(Y, X)`.
        # Both properties are asserted directly in the test suite.
        operands = [_expr(e.left), _expr(e.right)]
        return {
            "kind": "Relation",
            "relation": e.relation,
            "operands": _sorted_docs(operands) if e.symmetric else operands,
            "type": _type(e.type_),
        }

    return {"kind": type(e).__name__}


def _doc_key(doc: Any) -> str:
    """A total, deterministic order on serialised sub-documents.

    Sorting by the canonical JSON of each element rather than by source position is what
    makes a symmetric operator's identity independent of the order it was written in.
    """
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sorted_docs(docs: list) -> list:
    return sorted(docs, key=_doc_key)


def _sorted_exprs(items: list) -> list:
    return _sorted_docs([_expr(x) for x in items])


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
        doc: dict[str, Any] = {"kind": "Assumption", "proposition": _expr(st.proposition)}
        # The key is absent, not null, when there is no label: an unlabelled v1
        # assumption must serialise to exactly the document it always did.
        if st.label is not None:
            doc["label"] = _claim(st.claim_id) if st.claim_id is not None else st.label
        return doc

    if isinstance(st, GoalStmt):
        # `status` is deliberately ABSENT from the canonical form. It is evidence about
        # the module, not part of the mathematics the module states -- see the
        # SEMANTIC IDENTITY / EVIDENCE METADATA split in docs/hml_v2/SEMANTICS.md.
        # Two modules stating the same goal are the same module whether or not one of
        # them happens to have been proved in this run.
        return {
            "kind": "Goal",
            "label": _claim(st.claim_id),
            "proposition": _expr(st.proposition),
        }

    if isinstance(st, DeriveStmt):
        # Premise ORDER is part of identity: `transitivity` on (a=b, b=c) is a different
        # inference from the same rule on (b=c, a=b), and modus ponens distinguishes the
        # antecedent from the implication. Sorting them -- as `law.given` does, where
        # order genuinely is meaningless -- would silently identify distinct derivations.
        return {
            "kind": "Derivation",
            "label": _claim(st.claim_id),
            "rule": st.rule,
            "premises": [_claim(p) for p in st.premise_ids],
            "arguments": {
                a.role: _expr(a.value) for a in sorted(st.rule_args, key=lambda x: x.role)
            },
            "conclusion": _expr(st.conclusion),
        }

    if isinstance(st, ScopeStmt):
        # `consistency` is a VERDICT and is deliberately absent: evidence never enters
        # semantic identity (D-034 E1). Two modules stating the same scoped argument are
        # the same module whether or not one of them happens to be contradictory.
        return {
            "kind": "Scope",
            "body": [_statement(inner) for inner in st.body],
        }

    if isinstance(st, ProvedStmt):
        return {
            "kind": "ProofClaim",
            "goal": _claim(st.goal_id),
            "derivation": _claim(st.derivation_id),
        }

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
        "canonical_version": CANONICAL_VERSION_V2 if uses_v2(module) else CANONICAL_VERSION,
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


def _normalise_for_identity(doc: Any) -> Any:
    """Drop ``type`` annotations and normalise numeric literal spellings.

    Two adjustments, both confined to :func:`expr_identity` and invisible to
    :func:`content_hash`, so no historical module hash moves.

    *Types* are dropped for the reason given in :func:`expr_identity`.

    *Numbers* are normalised because ``1`` and ``1.0`` are the same number, and the two
    halves of the reasoning layer disagreed about that: ``reasoning/refinement.py``
    deliberately treats ``0`` and ``0.0`` as one value (it has a named regression test
    for it, because a rule generates ``k != 0`` with an integer zero while the author
    writes ``0.0``), while this function distinguished them. The visible symptom was a
    *correct* derivation rejected -- ``derive d : y + 1 = 2.0 * x + 1 ... by
    add_both_sides(by := 1.0)`` -- which is the safe direction to be wrong in but is
    still wrong, and an author has no way to tell that the mismatch is a literal
    spelling. Booleans are left alone: ``True`` must not collapse into ``1``.
    """
    if isinstance(doc, dict):
        return {k: _normalise_for_identity(v) for k, v in doc.items() if k != "type"}
    if isinstance(doc, list):
        return [_normalise_for_identity(v) for v in doc]
    if isinstance(doc, bool):
        return doc
    if isinstance(doc, int):
        return float(doc)
    return doc


def expr_identity(e: Expr, *, with_types: bool = False) -> str:
    """The canonical identity of a single expression, independent of its module.

    The reasoning kernel uses this to decide whether the conclusion an author claimed
    *is* the conclusion a rule licenses. It deliberately reuses ``_expr`` -- the very
    serializer that defines module identity -- rather than introducing a second notion
    of "the same expression". Two notions would agree until the day they did not, and
    on that day the kernel would certify a step the rest of the compiler considers a
    different statement.

    Names are excluded, so alpha-equivalent conclusions are identical here, matching
    :func:`content_hash`.

    **Why types are excluded by default.** The kernel builds its conclusion by
    assembling sub-trees taken from the premises under fresh ``BinOp``/``Comparison``
    wrappers. Those wrappers have never been through the type checker, so they carry
    ``type_ = None`` while the author's conclusion -- which has -- carries real types.
    Comparing with types would then report every correct derivation as a mismatch,
    which is what the first end-to-end run of the spine actually did.

    Dropping types loses no discriminating power *here*, and that is a claim worth
    being precise about: a node's type is a function of its structure and the resolved
    types of the symbols beneath it, and ``symbol`` (a ``SymbolId``, not a spelling) is
    still compared. Two expressions with identical type-free canonical forms therefore
    have identical types. What excluding types would lose is the ability to catch an
    *ill-typed* conclusion -- so that is caught separately and earlier, by the type
    checker visiting ``DeriveStmt.conclusion`` before this ever runs.

    ``with_types=True`` keeps the annotations, for callers comparing two expressions
    that have both been type-checked.
    """
    token = _INCLUDE_NAMES.set(False)
    try:
        doc = _expr(e)
    finally:
        _INCLUDE_NAMES.reset(token)
    if not with_types:
        doc = _normalise_for_identity(doc)
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def content_hash(module: Module) -> str:
    """SHA-256 of the *nameless* canonical form.

    Names are excluded so that alpha-renaming is invisible to identity. Proof
    obligations are excluded too, because they carry source line numbers.
    """
    blob = canonical_json(module, include_names=False)
    return hashlib.sha256(blob.encode("ascii")).hexdigest()
