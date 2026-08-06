"""The ACQ0 context budget: authoritative token measurement and the slot decision.

Read :mod:`.slots` first. It holds the one inequality the rest of the package serves::

    prompt_eval_count + completion_allowance + safety_reserve <= per_slot_context

Everything else is machinery for obtaining the left-hand side honestly (:mod:`.probe`),
choosing what goes into it (:mod:`.curriculum`), and deciding which rung of the slot
ladder the whole comparison runs on (:mod:`.report`).

The rule that shapes the package
--------------------------------
A character-derived estimate may **select** a prompt to measure. It may never **decide**
whether that prompt fits. :func:`.slots.eligibility` enforces this at the type level by
taking a :class:`~hamiltonian_lang.improvement.episodes.Measurement` and rejecting any
instrument that is not a real token counter, so the rule cannot be forgotten by a caller
who only has an integer to hand.

This supersedes the 5,893-token figure in ``docs/evaluation/EXECUTION_ENVIRONMENT.md``
for ACQ0 purposes: that number was measured on ``benchmarks/representations/`` material,
not on the frozen syntax-gate curricula, and the frozen curricula are several times
larger. See ``docs/evaluation/ACQ0_CONTEXT_BUDGET.md``.
"""

from __future__ import annotations

from .curriculum import (
    CURRICULUM_SIZE,
    DEFAULT_LAMBDA,
    CostModel,
    CurriculumSelection,
    HeldOutLeakage,
    NoFeasibleCurriculum,
    SelectionStep,
    cost_model_from_probes,
    demonstration_pool,
    provisional_cost_model,
    select_curriculum,
)
from .probe import (
    TRUNCATION_MARGIN,
    OfflineTokenCounter,
    OllamaPromptEvalCounter,
    PromptProbe,
    StubTokenCounter,
    TokenCounter,
    probe_prompt,
)
from .report import (
    THIN_MARGIN_CHARACTERS,
    BudgetReport,
    LadderResult,
    candidate_conditions,
    probe_curriculum,
    walk_ladder,
    worst_case_task,
)
from .slots import (
    COMPLETION_ALLOWANCE,
    DEFAULT_SAFETY_RESERVE,
    MIN_COMPLETION_ALLOWANCE,
    MIN_SAFETY_RESERVE,
    SLOT_LADDER,
    TOTAL_CONTEXT,
    AsymmetricSlotAllocation,
    ComparisonPlan,
    Eligibility,
    EstimateOfferedAsMeasurement,
    Fit,
    InsufficientAllowance,
    InsufficientReserve,
    SlotPolicy,
    UnequalCurriculum,
    assert_symmetric,
    eligibility,
    next_policy,
    policy_for_slots,
)

__all__ = [
    "TOTAL_CONTEXT",
    "COMPLETION_ALLOWANCE",
    "MIN_COMPLETION_ALLOWANCE",
    "MIN_SAFETY_RESERVE",
    "DEFAULT_SAFETY_RESERVE",
    "SLOT_LADDER",
    "SlotPolicy",
    "Fit",
    "Eligibility",
    "eligibility",
    "ComparisonPlan",
    "assert_symmetric",
    "AsymmetricSlotAllocation",
    "UnequalCurriculum",
    "EstimateOfferedAsMeasurement",
    "InsufficientReserve",
    "InsufficientAllowance",
    "policy_for_slots",
    "next_policy",
    "TokenCounter",
    "OfflineTokenCounter",
    "StubTokenCounter",
    "OllamaPromptEvalCounter",
    "PromptProbe",
    "probe_prompt",
    "TRUNCATION_MARGIN",
    "CURRICULUM_SIZE",
    "DEFAULT_LAMBDA",
    "CostModel",
    "CurriculumSelection",
    "SelectionStep",
    "HeldOutLeakage",
    "NoFeasibleCurriculum",
    "select_curriculum",
    "provisional_cost_model",
    "cost_model_from_probes",
    "demonstration_pool",
    "worst_case_task",
    "probe_curriculum",
    "walk_ladder",
    "BudgetReport",
    "LadderResult",
    "THIN_MARGIN_CHARACTERS",
    "candidate_conditions",
]
