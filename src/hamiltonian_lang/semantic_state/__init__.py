"""Canonical typed semantic state, its neutral adapter, and the transition verifier.

The canonical machine object is the typed state in :mod:`.model`. HML text, a generic typed
AST and Structured English are all *renderings* of it — ``docs/04`` §6.14 — so nothing in
this package touches the lexer, the parser or ``ast/nodes.py``. No surface syntax was added
to support any of it.

    neutral record  --import-->  SemanticState + Action  --verify-->  VALID | INVALID | UNRESOLVED

Specification: ``docs/hml_v2/SEMANTIC_STATE_CONTRACT.md``.
"""

from __future__ import annotations

from .model import (
    Action,
    Branch,
    BranchStatus,
    Candidate,
    CandidateStatus,
    Claim,
    ClaimStatus,
    ErrorClass,
    EvidenceRecord,
    Goal,
    Obligation,
    ObligationState,
    SemanticState,
    Transition,
    Verdict,
)
from .neutral import (
    SUPPORTED_SCHEMA_VERSIONS,
    NeutralImportError,
    export_state,
    export_transition,
    import_state,
    import_transition,
)
from .verify import INVARIANTS, Finding, TransitionResult, verify, verify_payload

__all__ = [
    "Action",
    "Branch",
    "BranchStatus",
    "Candidate",
    "CandidateStatus",
    "Claim",
    "ClaimStatus",
    "ErrorClass",
    "EvidenceRecord",
    "Goal",
    "Obligation",
    "ObligationState",
    "SemanticState",
    "Transition",
    "Verdict",
    "SUPPORTED_SCHEMA_VERSIONS",
    "NeutralImportError",
    "export_state",
    "export_transition",
    "import_state",
    "import_transition",
    "INVARIANTS",
    "Finding",
    "TransitionResult",
    "verify",
    "verify_payload",
]
