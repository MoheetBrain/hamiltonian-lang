"""The neutral-transition adapter (SF-R03): corpus record in, typed state out.

Losslessness is a *test*, not an intention
------------------------------------------
The requirement is a versioned lossless importer. "Lossless" is easy to claim and easy to
get wrong quietly — the usual failure is to model the fields you thought of and silently
drop the rest, which then surfaces much later as a fixture that cannot be expressed.

So the property is checked directly: :func:`export_transition` is the inverse of
:func:`import_transition`, and ``tests/semantic_state/test_neutral_adapter.py`` asserts
``export(import(x)) == x`` for **every** acceptance fixture. If a field is added upstream
and this adapter does not model it, that test fails rather than the field disappearing.

Fail closed on version
----------------------
An unrecognised ``schema_version`` is refused. It is tempting to accept anything that
parses, but a corpus whose schema has moved on is a corpus this code does not understand,
and importing it optimistically would produce a typed state that looks authoritative and
is wrong in unknown ways.

No syntax was added for any of this
-----------------------------------
The builder brief is explicit: do not add syntax merely to support import. Nothing here
touches the lexer, the parser or ``ast/nodes.py``. The canonical object is the typed state;
HML text is a rendering of it, and the renderer is deliberately later work.
"""

from __future__ import annotations

from typing import Any

from .model import (
    Action,
    Branch,
    BranchStatus,
    Candidate,
    CandidateStatus,
    Claim,
    ClaimStatus,
    EvidenceRecord,
    Goal,
    Obligation,
    ObligationState,
    SemanticState,
    Transition,
)

__all__ = [
    "SUPPORTED_SCHEMA_VERSIONS",
    "NeutralImportError",
    "import_transition",
    "export_transition",
    "import_state",
    "export_state",
]

#: Versions this adapter understands. Adding one is a deliberate act, because it is a
#: statement that the semantics of every field have been re-read.
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"semantic-firewall-case-0.1.0"})

#: Payload keys of an evidence record that this adapter models explicitly. Everything else
#: is preserved verbatim in ``EvidenceRecord.payload`` -- which is what makes a new
#: evidence kind survive the round trip without this module knowing about it.
_EVIDENCE_STRUCTURAL = frozenset({"id", "kind", "status", "trusted", "supports_rule", "premise_ids"})


class NeutralImportError(Exception):
    """The record could not be imported. Always a refusal, never a partial import."""


def _require(payload: Any, what: str) -> dict:
    if not isinstance(payload, dict):
        raise NeutralImportError(f"{what} must be an object, got {type(payload).__name__}")
    return payload


def _enum(value: Any, cls, what: str):
    try:
        return cls(value)
    except ValueError as exc:
        raise NeutralImportError(
            f"{what} {value!r} is not one of {', '.join(sorted(m.value for m in cls))}"
        ) from exc


def _tuple(value: Any) -> tuple:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    raise NeutralImportError(f"expected a list, got {type(value).__name__}")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def import_state(payload: dict) -> SemanticState:
    payload = _require(payload, "state")
    claims = {}
    for cid, raw in (payload.get("claims") or {}).items():
        raw = _require(raw, f"claim {cid!r}")
        claims[cid] = Claim(
            id=raw.get("id", cid),
            proposition=raw.get("proposition", ""),
            status=_enum(raw.get("status", "GIVEN"), ClaimStatus, f"claim {cid!r} status"),
            scope=raw.get("scope", "global"),
            domain=raw.get("domain"),
            dependencies=_tuple(raw.get("dependencies")),
        )
    candidates = {}
    for kid, raw in (payload.get("candidates") or {}).items():
        raw = _require(raw, f"candidate {kid!r}")
        candidates[kid] = Candidate(
            id=raw.get("id", kid),
            proposition=raw.get("proposition", ""),
            status=_enum(
                raw.get("status", "PROPOSED"), CandidateStatus, f"candidate {kid!r} status"
            ),
            scope=raw.get("scope", "global"),
            constraint_ids=_tuple(raw.get("constraint_ids")),
            origin=raw.get("origin"),
            dependencies=_tuple(raw.get("dependencies")),
            evidence_id=raw.get("evidence_id"),
            verification_result=raw.get("verification_result"),
        )
    branches = {}
    for bid, raw in (payload.get("branches") or {}).items():
        raw = _require(raw, f"branch {bid!r}")
        branches[bid] = Branch(
            id=raw.get("id", bid),
            predicate=raw.get("predicate", ""),
            status=_enum(raw.get("status", "OPEN"), BranchStatus, f"branch {bid!r} status"),
            scope=raw.get("scope", "global"),
            conclusion=raw.get("conclusion"),
            partition_id=raw.get("partition_id"),
        )
    goals = {}
    for gid, raw in (payload.get("goals") or {}).items():
        raw = _require(raw, f"goal {gid!r}")
        goals[gid] = Goal(
            id=raw.get("id", gid),
            proposition=raw.get("proposition", ""),
            status=raw.get("status", "OPEN"),
            scope=raw.get("scope", "global"),
        )
    obligations = {}
    for oid, raw in (payload.get("obligations") or {}).items():
        raw = _require(raw, f"obligation {oid!r}")
        obligations[oid] = Obligation(
            id=raw.get("id", oid),
            proposition=raw.get("proposition", ""),
            status=_enum(
                raw.get("status", "OPEN"), ObligationState, f"obligation {oid!r} status"
            ),
            mandatory=bool(raw.get("mandatory", True)),
            origin=raw.get("origin"),
            dependencies=_tuple(raw.get("dependencies")),
            discharge_evidence_id=raw.get("discharge_evidence_id"),
        )
    return SemanticState(
        claims=claims,
        candidates=candidates,
        branches=branches,
        goals=goals,
        obligations=obligations,
        active_scopes=_tuple(payload.get("active_scopes")) or ("global",),
    )


def _drop_none(d: dict) -> dict:
    """Omit keys the source did not carry, so the round trip is exact.

    An importer that helpfully materialises ``"origin": null`` for every record produces a
    document that no longer equals the one it read, which would make the losslessness test
    either fail or -- worse -- be weakened until it passed.
    """
    return {k: v for k, v in d.items() if v is not None}


def export_state(state: SemanticState) -> dict:
    return {
        "active_scopes": list(state.active_scopes),
        "branches": {
            b.id: _drop_none(
                {
                    "conclusion": b.conclusion,
                    "id": b.id,
                    "partition_id": b.partition_id,
                    "predicate": b.predicate,
                    "scope": b.scope if b.scope != "global" else None,
                    "status": str(b.status),
                }
            )
            for b in state.branches.values()
        },
        "candidates": {
            c.id: _drop_none(
                {
                    "constraint_ids": list(c.constraint_ids),
                    "dependencies": list(c.dependencies) or None,
                    "evidence_id": c.evidence_id,
                    "id": c.id,
                    "origin": c.origin,
                    "proposition": c.proposition,
                    "scope": c.scope,
                    "status": str(c.status),
                    "verification_result": c.verification_result,
                }
            )
            for c in state.candidates.values()
        },
        "claims": {
            c.id: _drop_none(
                {
                    "dependencies": list(c.dependencies),
                    "domain": c.domain,
                    "id": c.id,
                    "proposition": c.proposition,
                    "scope": c.scope,
                    "status": str(c.status),
                }
            )
            for c in state.claims.values()
        },
        "goals": {
            g.id: _drop_none(
                {
                    "id": g.id,
                    "proposition": g.proposition,
                    "scope": g.scope,
                    "status": g.status,
                }
            )
            for g in state.goals.values()
        },
        "obligations": {
            o.id: _drop_none(
                {
                    "dependencies": list(o.dependencies),
                    "discharge_evidence_id": o.discharge_evidence_id,
                    "id": o.id,
                    "mandatory": o.mandatory,
                    "origin": o.origin,
                    "proposition": o.proposition,
                    "status": str(o.status),
                }
            )
            for o in state.obligations.values()
        },
    }


# ---------------------------------------------------------------------------
# Action, evidence, transition
# ---------------------------------------------------------------------------


def _import_action(payload: dict) -> Action:
    payload = _require(payload, "action")
    return Action(
        id=payload.get("id", "a0"),
        operation=payload.get("operation", ""),
        summary=payload.get("summary", ""),
        output_id=payload.get("output_id"),
        dependencies=_tuple(payload.get("dependencies")),
        preconditions=tuple(payload.get("preconditions") or ()),
        obligations_created=tuple(payload.get("obligations_created") or ()),
        obligations_discharged=_tuple(payload.get("obligations_discharged")),
        typing=dict(payload.get("typing") or {}),
        warrant=dict(payload.get("warrant") or {}),
        goal_effect=dict(payload.get("goal_effect") or {}),
        scope_effect=dict(payload.get("scope_effect") or {}),
        branch_effect=dict(payload.get("branch_effect") or {}),
        candidate_effect=dict(payload.get("candidate_effect") or {}),
        epistemic_effect=dict(payload.get("epistemic_effect") or {}),
    )


def _export_action(action: Action) -> dict:
    out = {
        "branch_effect": action.branch_effect,
        "candidate_effect": action.candidate_effect,
        "dependencies": list(action.dependencies),
        "epistemic_effect": action.epistemic_effect,
        "goal_effect": action.goal_effect,
        "id": action.id,
        "obligations_created": list(action.obligations_created),
        "obligations_discharged": list(action.obligations_discharged),
        "operation": action.operation,
        "preconditions": list(action.preconditions),
        "scope_effect": action.scope_effect,
        "summary": action.summary,
        "typing": action.typing,
        "warrant": action.warrant,
    }
    if action.output_id is not None:
        out["output_id"] = action.output_id
    return out


def _import_evidence(payload: dict) -> EvidenceRecord:
    payload = _require(payload, "evidence record")
    return EvidenceRecord(
        id=payload.get("id", ""),
        kind=payload.get("kind", ""),
        status=payload.get("status", "UNKNOWN"),
        trusted=bool(payload.get("trusted", False)),
        supports_rule=payload.get("supports_rule"),
        premise_ids=_tuple(payload.get("premise_ids")),
        payload={k: v for k, v in payload.items() if k not in _EVIDENCE_STRUCTURAL},
    )


def _export_evidence(record: EvidenceRecord) -> dict:
    out = {
        "id": record.id,
        "kind": record.kind,
        "premise_ids": list(record.premise_ids),
        "status": record.status,
        "supports_rule": record.supports_rule,
        "trusted": record.trusted,
    }
    out.update(record.payload)
    return out


def import_transition(payload: dict) -> Transition:
    """Import one neutral transition record. Refuses rather than importing partially."""
    payload = _require(payload, "transition")
    version = payload.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise NeutralImportError(
            f"schema version {version!r} is not supported "
            f"(this adapter reads {', '.join(sorted(SUPPORTED_SCHEMA_VERSIONS))})"
        )
    if "action" not in payload:
        raise NeutralImportError("a transition record must carry an action")
    return Transition(
        case_id=payload.get("case_id", ""),
        action=_import_action(payload["action"]),
        state_before=import_state(payload.get("state_before") or {}),
        state_after=import_state(payload.get("state_after") or {}),
        evidence={
            eid: _import_evidence(raw) for eid, raw in (payload.get("evidence") or {}).items()
        },
        schema_version=version,
        source=dict(payload.get("source") or {}),
    )


def export_transition(transition: Transition, *, extras: dict | None = None) -> dict:
    """The inverse of :func:`import_transition`.

    ``extras`` carries record-level keys this adapter does not model semantically —
    ``pair_id``, ``split``, ``semantic_focus`` and the like. They are provenance, so they
    are round-tripped rather than interpreted, and the caller supplies them explicitly
    instead of this module pretending it understood them.
    """
    out = {
        "action": _export_action(transition.action),
        "case_id": transition.case_id,
        "evidence": {
            eid: _export_evidence(rec) for eid, rec in transition.evidence.items()
        },
        "schema_version": transition.schema_version,
        "source": transition.source,
        "state_after": export_state(transition.state_after),
        "state_before": export_state(transition.state_before),
    }
    if extras:
        out.update(extras)
    return out
