"""Chain-of-Repair — role-separated, context-conditioned repair, and its leakage controls.

Two research results shape this package.

**INTERVENOR.** Self-repair fails when one model stays trapped in the interpretation that
produced the error. The fix is role separation: a *Teacher* receives the broken output,
the diagnostic and the failed checks and returns the cause and a plan — explicitly not the
corrected program — and a *Learner* applies the plan.

**COCOGEN.** A diagnostic says what is wrong but not which project-specific rule,
signature or type should replace it. The fix is error-conditioned retrieval over a
structural project graph; compiler feedback alone did not deliver the full gain. That
retrieval lives in :mod:`hamiltonian_lang.context_broker`.

The constraint that makes the measurement mean anything is that the plan must not contain
the answer. It is enforced in :mod:`.plan` and tested, not left to a prompt.

Nothing in this package contacts a model or a network. Live components are refused unless
a caller passes ``allow_live=True``.
"""

from __future__ import annotations

from .arms import (
    ARM_DESCRIPTION,
    ArmContamination,
    FeedbackArm,
    FeedbackPayload,
    build_payload,
)
from .budget import (
    MAX_REPAIRS,
    NonOfficialBudgetError,
    RepairBudget,
    RepairBudgetExceeded,
    RepairBudgetPoolingError,
    assert_official,
    max_repairs,
    require_single_budget,
)
from .leakage import (
    DEFAULT_LEAK_THRESHOLD,
    DEFAULT_MIN_TRIALS,
    LEAKAGE_VERSION,
    ConditionRate,
    EvidenceGap,
    LeakageCase,
    LeakageCondition,
    LeakageProbe,
    LeakageReport,
    LeakageTrial,
    LeakageVerdict,
    LiveProbeRefused,
    ReconstructionProbe,
    ScriptedLeakageProbe,
    ShuffleDegenerate,
    ShuffleMode,
    run_leakage_study,
    shuffle_plan,
)
from .learner import (
    LearnerScriptError,
    RepairLearner,
    ScriptedRepairLearner,
    ScriptKey,
)
from .plan import (
    MAX_STEP_LINES,
    MAX_STEPS,
    PLAN_VERSION,
    STATEMENT_KEYWORDS,
    NoPlan,
    PlanLeak,
    RepairPlan,
    assert_plan_non_leaking,
    is_program_like,
    plan_leak_reasons,
    statement_lines,
)
from .record import (
    ArmSummary,
    Checker,
    CheckOutcome,
    HypothesisEndpointError,
    LiveComponentRefused,
    RepairEndpoint,
    RepairRecord,
    RepairSummary,
    RepairTurnRecord,
    default_checker,
    run_repair_chain,
    summarise,
)
from .teacher import (
    CLASS_INVARIANT,
    CLASS_REPAIR_STEPS,
    CLASS_SEMANTIC_CATEGORY,
    TEACHER_VERSION,
    UNIVERSAL_PRESERVATION,
    DeterministicRepairTeacher,
    RepairTeacher,
    TeachResult,
    numerals_in,
)

__all__ = [
    "ARM_DESCRIPTION",
    "ArmContamination",
    "ArmSummary",
    "CLASS_INVARIANT",
    "CLASS_REPAIR_STEPS",
    "CLASS_SEMANTIC_CATEGORY",
    "CheckOutcome",
    "Checker",
    "ConditionRate",
    "DEFAULT_LEAK_THRESHOLD",
    "DEFAULT_MIN_TRIALS",
    "DeterministicRepairTeacher",
    "EvidenceGap",
    "FeedbackArm",
    "FeedbackPayload",
    "HypothesisEndpointError",
    "LEAKAGE_VERSION",
    "LeakageCase",
    "LeakageCondition",
    "LeakageProbe",
    "LeakageReport",
    "LeakageTrial",
    "LeakageVerdict",
    "LearnerScriptError",
    "LiveComponentRefused",
    "LiveProbeRefused",
    "MAX_REPAIRS",
    "MAX_STEPS",
    "MAX_STEP_LINES",
    "NoPlan",
    "NonOfficialBudgetError",
    "PLAN_VERSION",
    "PlanLeak",
    "ReconstructionProbe",
    "RepairBudget",
    "RepairBudgetExceeded",
    "RepairBudgetPoolingError",
    "RepairEndpoint",
    "RepairLearner",
    "RepairPlan",
    "RepairRecord",
    "RepairSummary",
    "RepairTeacher",
    "RepairTurnRecord",
    "ScriptKey",
    "ScriptedLeakageProbe",
    "ScriptedRepairLearner",
    "STATEMENT_KEYWORDS",
    "ShuffleDegenerate",
    "ShuffleMode",
    "TEACHER_VERSION",
    "TeachResult",
    "UNIVERSAL_PRESERVATION",
    "assert_official",
    "assert_plan_non_leaking",
    "build_payload",
    "default_checker",
    "is_program_like",
    "max_repairs",
    "numerals_in",
    "plan_leak_reasons",
    "require_single_budget",
    "run_leakage_study",
    "run_repair_chain",
    "shuffle_plan",
    "statement_lines",
    "summarise",
]
