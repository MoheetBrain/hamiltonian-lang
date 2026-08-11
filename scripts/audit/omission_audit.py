"""The omission audit: STATE KIND x CHANGE TYPE, built from the model, not from the verifier.

D-057 was a gap of omission — `goals` was absent from the frame loop — and no mutation of
existing code can reveal a record kind that is not in it. So this audit starts at the
dataclasses and enums and asks, for every semantic dimension the *model* has, whether the
enforcement paths know about it.

Two rules make it an audit rather than a restatement:

* the inventory is **introspected** (``dataclasses.fields``, ``enum`` members,
  transition tables), never typed out by hand and compared against itself;
* every cell is decided **empirically** — a payload is built, run through production
  ``import`` and ``verify``, and the verdict recorded. Nothing is inferred from reading.

Payloads are produced by exporting real model objects through the production neutral
adapter, so field names and shapes cannot drift from the schema.

Written 2026-08-11 for the pre-Gemma semantic freeze omission audit.
"""
from __future__ import annotations

import copy
import dataclasses
import enum
import json
from pathlib import Path
from typing import Any

from hamiltonian_lang.semantic_state import (
    model as M,
)
from hamiltonian_lang.semantic_state import (
    neutral,
    verify_replay,
    verify_runtime,
)
from hamiltonian_lang.semantic_state.neutral import NeutralImportError, import_transition

OUT = Path(__file__).resolve().parents[2] / "reports" / "artifacts"


# ---------------------------------------------------------------------------
# 1A / 1C -- the inventory, introspected
# ---------------------------------------------------------------------------

def inventory() -> dict:
    state_fields = {f.name: str(f.type) for f in dataclasses.fields(M.SemanticState)}
    records = {}
    for name, obj in vars(M).items():
        if dataclasses.is_dataclass(obj) and isinstance(obj, type):
            records[name] = {f.name: str(f.type) for f in dataclasses.fields(obj)}
    enums = {
        name: [e.value for e in obj]
        for name, obj in vars(M).items()
        if isinstance(obj, type) and issubclass(obj, enum.Enum) and obj is not M.StrEnum
    }
    tables = {n: {str(k): sorted(str(x) for x in v) for k, v in o.items()}
              for n, o in vars(M).items() if isinstance(o, dict) and n.isupper()}

    # Which state collections carry a *typed* status, and which carry a bare str.
    collection_to_record = {
        "claims": "Claim", "candidates": "Candidate", "branches": "Branch",
        "goals": "Goal", "obligations": "Obligation",
    }
    status_typing = {}
    for coll, rec in collection_to_record.items():
        ty = records[rec].get("status", "<absent>")
        typed = any(e in ty for e in enums)
        status_typing[coll] = {"declared_type": ty, "is_typed_enum": typed}

    lifecycle = {
        coll: {"has_transition_table":
               any(coll[:-1].upper() in t or rec.upper() in t for t in tables)}
        for coll, rec in collection_to_record.items()
    }
    return {"semantic_state_fields": state_fields, "record_dataclasses": records,
            "status_enums": enums, "transition_tables": tables,
            "status_typing": status_typing, "lifecycle_tables": lifecycle,
            "collection_to_record": collection_to_record}


# ---------------------------------------------------------------------------
# Baseline payload, built from real model objects and exported by production code
# ---------------------------------------------------------------------------

def _bystander(kind: str) -> Any:
    """One well-formed record of ``kind`` that the action does not touch."""
    if kind == "claims":
        return M.Claim(id="z_rec", proposition="a bystander fact",
                       status=M.ClaimStatus.GIVEN, scope="global", domain="Integer",
                       dependencies=())
    if kind == "candidates":
        return M.Candidate(id="z_rec", proposition="a bystander candidate",
                           status=M.CandidateStatus.UNVERIFIED, scope="global")
    if kind == "branches":
        return M.Branch(id="z_rec", predicate="case A", status=M.BranchStatus.OPEN,
                        scope="global")
    if kind == "goals":
        return M.Goal(id="z_rec", proposition="a bystander goal", status="OPEN",
                      scope="global")
    if kind == "obligations":
        return M.Obligation(id="z_rec", proposition="a bystander obligation",
                            status=M.ObligationState.OPEN, mandatory=True, origin="audit")
    raise AssertionError(kind)


def base_transition(kind: str | None) -> dict:
    """A minimal VALID derivation, optionally carrying one untouched bystander record."""
    p0 = M.Claim(id="p0", proposition="n > 0", status=M.ClaimStatus.GIVEN, scope="global",
                 domain="Natural", dependencies=())
    c1 = M.Claim(id="c1", proposition="q", status=M.ClaimStatus.DERIVED, scope="global",
                 domain="Proposition", dependencies=("p0",))
    before_kw: dict[str, Any] = {"claims": {"p0": p0}, "active_scopes": ("global",)}
    after_kw: dict[str, Any] = {"claims": {"p0": p0, "c1": c1}, "active_scopes": ("global",)}
    if kind:
        rec = _bystander(kind)
        if kind == "claims":
            before_kw["claims"] = {"p0": p0, "z_rec": rec}
            after_kw["claims"] = {"p0": p0, "c1": c1, "z_rec": rec}
        else:
            before_kw[kind] = {"z_rec": rec}
            after_kw[kind] = {"z_rec": rec}
    action = M.Action(id="a0", operation="DERIVE", summary="q", output_id="c1",
                      dependencies=("p0",),
                      typing={"input_domains": {"p0": "Integer"},
                              "output_domain": "Proposition"})
    t = M.Transition(case_id="AUDIT", action=action,
                     state_before=M.SemanticState(**before_kw),
                     state_after=M.SemanticState(**after_kw),
                     evidence={}, schema_version="semantic-firewall-case-0.1.0",
                     source={"origin": "synthetic", "rationale": "omission audit"})
    return neutral.export_transition(t)


def run(payload: dict, runtime: bool = False) -> list:
    try:
        t = import_transition(payload)
    except NeutralImportError as exc:
        return ["REFUSED_AT_IMPORT", type(exc).__name__, str(exc)[:100]]
    except Exception as exc:  # noqa: BLE001 - an uncontrolled crash is a result
        return ["IMPORT_CRASH", type(exc).__name__, str(exc)[:100]]
    try:
        r = verify_runtime(t) if runtime else verify_replay(t)
    except Exception as exc:  # noqa: BLE001
        return ["VERIFY_CRASH", type(exc).__name__, str(exc)[:100]]
    return [str(r.verdict), r.error_class, (r.findings[0].detail[:100] if r.findings else "")]


# ---------------------------------------------------------------------------
# 2 -- the cross-product
# ---------------------------------------------------------------------------

#: A semantic field per record kind whose change is truth-relevant and is NOT the status.
CONTENT_FIELD = {"claims": "proposition", "candidates": "proposition",
                 "branches": "predicate", "goals": "proposition",
                 "obligations": "proposition"}

#: A status value genuinely different from the bystander's, per kind.
OTHER_STATUS = {"claims": "VERIFIED", "candidates": "VERIFIED", "branches": "CLOSED",
                "goals": "DISCHARGED", "obligations": "DISCHARGED"}


def cross_product() -> list[dict]:
    rows = []
    kinds = ["claims", "candidates", "branches", "goals", "obligations"]
    for kind in kinds:
        base = base_transition(kind)
        baseline = run(copy.deepcopy(base))

        cases: dict[str, dict] = {}

        # ADD -- a record materialises in state_after that was not in state_before
        p = copy.deepcopy(base)
        newrec = copy.deepcopy(p["state_before"][kind]["z_rec"])
        newrec["id"] = "z_new"
        p["state_after"][kind]["z_new"] = newrec
        cases["ADD"] = p

        # DELETE -- the record is gone from state_after
        p = copy.deepcopy(base)
        del p["state_after"][kind]["z_rec"]
        cases["DELETE"] = p

        # MODIFY -- a truth-relevant non-status field changes, undeclared
        p = copy.deepcopy(base)
        p["state_after"][kind]["z_rec"][CONTENT_FIELD[kind]] = "SOMETHING ELSE ENTIRELY"
        cases["MODIFY"] = p

        # STATUS CHANGE -- undeclared
        p = copy.deepcopy(base)
        p["state_after"][kind]["z_rec"]["status"] = OTHER_STATUS[kind]
        cases["STATUS_CHANGE"] = p

        # SCOPE CHANGE -- undeclared (only where the record carries a scope)
        if "scope" in base["state_before"][kind]["z_rec"]:
            p = copy.deepcopy(base)
            p["state_after"][kind]["z_rec"]["scope"] = "a_different_scope"
            cases["SCOPE_CHANGE"] = p

        # ID CHANGE -- payload id diverges from the key it is filed under
        p = copy.deepcopy(base)
        p["state_after"][kind]["z_rec"]["id"] = "a_different_id"
        cases["ID_CHANGE_payload_id"] = p

        # KEY CHANGE -- the record is refiled under a different key
        p = copy.deepcopy(base)
        rec = p["state_after"][kind].pop("z_rec")
        p["state_after"][kind]["z_moved"] = rec
        cases["KEY_CHANGE"] = p

        for change, payload in cases.items():
            rows.append({
                "state_kind": kind, "change_type": change,
                "baseline_replay": baseline,
                "replay": run(copy.deepcopy(payload)),
                "runtime": run(copy.deepcopy(payload), runtime=True),
            })
    return rows


# ---------------------------------------------------------------------------
# 1C -- every enum value, on every status-bearing record
# ---------------------------------------------------------------------------

def status_value_sweep() -> list[dict]:
    """No enum value may bypass enforcement because the verifier forgot to enumerate it.

    A bystander record is walked through every value its status enum admits, plus values
    from *other* enums and a value belonging to no enum at all.
    """
    rows = []
    all_values = sorted({v for E in (M.ClaimStatus, M.CandidateStatus, M.BranchStatus,
                                     M.ObligationState) for v in (e.value for e in E)})
    all_values += ["NOT_A_STATUS_AT_ALL", "", "open", "DISCHARGED "]
    for kind in ["claims", "candidates", "branches", "goals", "obligations"]:
        base = base_transition(kind)
        current = base["state_before"][kind]["z_rec"]["status"]
        for value in all_values:
            p = copy.deepcopy(base)
            # change it in BOTH states, so this tests admissibility, not the frame
            p["state_before"][kind]["z_rec"]["status"] = value
            p["state_after"][kind]["z_rec"]["status"] = value
            rows.append({"state_kind": kind, "from_status": current, "set_status": value,
                         "replay": run(copy.deepcopy(p)),
                         "runtime": run(copy.deepcopy(p), runtime=True)})
    return rows


# ---------------------------------------------------------------------------
# 1C -- lifecycle: settled -> reopened, per record kind
# ---------------------------------------------------------------------------

def lifecycle_sweep() -> list[dict]:
    """Candidate lifecycle is enforced by a transition table. Is anything else?

    A settled record walked backwards to an open state is the shape SF-R06 refuses for
    candidates; the same shape is tried on every other kind.
    """
    settled_to_open = {
        "claims": [("VERIFIED", "ASSUMED"), ("REFUTED", "VERIFIED")],
        "candidates": [("VERIFIED", "UNVERIFIED"), ("REJECTED", "PROPOSED")],
        "branches": [("JOINED", "OPEN"), ("ABANDONED", "OPEN"), ("CLOSED", "OPEN")],
        "goals": [("DISCHARGED", "OPEN")],
        "obligations": [("DISCHARGED", "OPEN"), ("FAILED", "OPEN")],
    }
    rows = []
    for kind, pairs in settled_to_open.items():
        base = base_transition(kind)
        for settled, reopened in pairs:
            p = copy.deepcopy(base)
            p["state_before"][kind]["z_rec"]["status"] = settled
            p["state_after"][kind]["z_rec"]["status"] = reopened
            rows.append({"state_kind": kind, "from": settled, "to": reopened,
                         "undeclared_replay": run(copy.deepcopy(p)),
                         "undeclared_runtime": run(copy.deepcopy(p), runtime=True)})
    return rows


# ---------------------------------------------------------------------------
# 1A -- UNKNOWN relevance, per record kind
# ---------------------------------------------------------------------------

def unknown_sweep() -> list[dict]:
    """UNKNOWN is fail-closed *where the action consults the record*.

    Tested twice per kind: as a bystander the action never cites (must NOT become
    UNRESOLVED, or one junk record disables the verifier -- D-049), and as a record the
    action does cite (must become UNRESOLVED).
    """
    rows = []
    for kind in ["claims", "candidates", "branches", "goals", "obligations"]:
        base = base_transition(kind)
        p = copy.deepcopy(base)
        p["state_before"][kind]["z_rec"]["status"] = "UNKNOWN"
        p["state_after"][kind]["z_rec"]["status"] = "UNKNOWN"
        rows.append({"state_kind": kind, "role": "bystander_uncited",
                     "replay": run(copy.deepcopy(p))})

        cited = copy.deepcopy(p)
        if kind == "claims":
            cited["action"]["dependencies"] = ["p0", "z_rec"]
        elif kind == "candidates":
            cited["action"]["candidate_effect"] = {"candidate_id": "z_rec", "kind": "OPEN"}
        elif kind == "branches":
            cited["action"]["branch_effect"] = {"branch_ids": ["z_rec"], "kind": "JOIN"}
        elif kind == "goals":
            cited["action"]["goal_effect"] = {"goal_id": "z_rec", "kind": "DISCHARGE"}
        elif kind == "obligations":
            cited["action"]["obligations_discharged"] = ["z_rec"]
        rows.append({"state_kind": kind, "role": "cited_by_action",
                     "replay": run(copy.deepcopy(cited))})
    return rows


def main() -> None:
    report = {
        "artifact_id": "semantic_omission_audit",
        "generated": "2026-08-11",
        "method": "Inventory introspected from dataclasses/enums/transition tables. Every "
                  "cell decided empirically by running production import+verify on a "
                  "payload exported through the production neutral adapter.",
        "inventory": inventory(),
        "cross_product": cross_product(),
        "status_value_sweep": status_value_sweep(),
        "lifecycle_sweep": lifecycle_sweep(),
        "unknown_sweep": unknown_sweep(),
    }
    (OUT / "OMISSION_AUDIT_RAW.json").write_text(json.dumps(report, indent=1))
    print("wrote", OUT / "OMISSION_AUDIT_RAW.json")

    # -- console summary ---------------------------------------------------
    print("\n=== STATUS TYPING ===")
    for k, v in report["inventory"]["status_typing"].items():
        print(f"  {k:<12} typed_enum={str(v['is_typed_enum']):<5}  {v['declared_type']}")
    print("\n=== CROSS PRODUCT (replay verdict / runtime verdict) ===")
    for r in report["cross_product"]:
        print(f"  {r['state_kind']:<12} {r['change_type']:<22} {r['replay'][0]:<11} "
              f"{r['runtime'][0]:<11} {r['replay'][1] or ''}")
    print("\n=== LIFECYCLE: settled -> reopened, undeclared ===")
    for r in report["lifecycle_sweep"]:
        print(f"  {r['state_kind']:<12} {r['from']:<10} -> {r['to']:<10} "
              f"{r['undeclared_replay'][0]:<11} {r['undeclared_replay'][1] or ''}")
    print("\n=== UNKNOWN relevance ===")
    for r in report["unknown_sweep"]:
        print(f"  {r['state_kind']:<12} {r['role']:<18} {r['replay'][0]}")


if __name__ == "__main__":
    main()
