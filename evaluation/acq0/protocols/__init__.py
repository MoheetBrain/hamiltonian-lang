"""Generation protocols, oracle guard, metrics, runner, selector and calibration design.

Read :mod:`.core` first: it defines the three protocols and the per-stage token ledger
that everything else is written against. :mod:`.metrics` defines the eight quantities and
is the module to read before adding any measurement, because the design rule there —
eight fields, no aggregate — is the one most easily undone by a well-meaning helper.
"""

from __future__ import annotations

from .calibration import (
    CALIBRATION_CALL_COUNT,
    CALIBRATION_CELL_COUNT,
    CALIBRATION_PROTOCOLS,
    CalibrationCell,
    calibration_cells,
    calibration_design,
    calibration_tasks,
)
from .core import (
    PROTOCOL_STAGES,
    UNRESTRICTED_STAGES,
    GenerationProtocol,
    ProtocolTranscript,
    StageAccountingError,
    StageCall,
    StageKind,
    TokenLedger,
)
from .metrics import (
    EIGHT_METRICS,
    ArmSummary,
    ConflatedVerdict,
    ProtocolMetrics,
    aggregate,
    format_adherence,
    metrics_for_reply,
    metrics_from_stage_outcome,
)
from .oracle import (
    ORACLE_FIELDS,
    PERMITTED_TASK_INFORMATION,
    InformationAsymmetry,
    OracleLeak,
    TaskInformation,
    assert_information_parity,
    assert_no_oracle,
    protocol_information,
    scan_for_oracle,
)
from .runner import (
    AuthorisedSession,
    LiveCallAuthorisation,
    OfflineBackend,
    ScriptedBackend,
    UnauthorisedModelCall,
    run_protocol,
)
from .selection import (
    LEXICOGRAPHIC_KEYS,
    MATERIALITY,
    Selection,
    SelectionStatus,
    select_protocol,
)

__all__ = [
    "PROTOCOL_STAGES",
    "UNRESTRICTED_STAGES",
    "GenerationProtocol",
    "ProtocolTranscript",
    "StageAccountingError",
    "StageCall",
    "StageKind",
    "TokenLedger",
    "ORACLE_FIELDS",
    "PERMITTED_TASK_INFORMATION",
    "InformationAsymmetry",
    "OracleLeak",
    "TaskInformation",
    "assert_information_parity",
    "assert_no_oracle",
    "protocol_information",
    "scan_for_oracle",
    "EIGHT_METRICS",
    "ArmSummary",
    "ConflatedVerdict",
    "ProtocolMetrics",
    "aggregate",
    "format_adherence",
    "metrics_for_reply",
    "metrics_from_stage_outcome",
    "AuthorisedSession",
    "LiveCallAuthorisation",
    "OfflineBackend",
    "ScriptedBackend",
    "UnauthorisedModelCall",
    "run_protocol",
    "LEXICOGRAPHIC_KEYS",
    "MATERIALITY",
    "Selection",
    "SelectionStatus",
    "select_protocol",
    "CALIBRATION_CALL_COUNT",
    "CALIBRATION_CELL_COUNT",
    "CALIBRATION_PROTOCOLS",
    "CalibrationCell",
    "calibration_cells",
    "calibration_design",
    "calibration_tasks",
]
