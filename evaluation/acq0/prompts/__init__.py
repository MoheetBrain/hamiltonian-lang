"""Stage prompts, field-order controls and the prompt-sensitivity phrasings.

:mod:`.field_order` is the module with the sharpest teeth: it encodes the paper's
observation that a schema placing the answer field before the reasoning field induces
direct answering, with valid output and degraded content, and it refuses answer-first in
the official gate until a probe says otherwise.
"""

from __future__ import annotations

from .field_order import (
    ANSWER_FIRST_ORDER,
    CANDIDATE_D_FIELD_ORDER_PROBE,
    CANONICAL_FIELD_ORDER,
    SEMANTIC_PREREQUISITES,
    AnswerFirstNotLicensed,
    FieldOrderArm,
    FieldOrderViolation,
    FieldRole,
    assert_gate_field_order,
    official_gate_field_order,
    validate_field_order,
)
from .sensitivity import (
    INSTRUCTION_OBLIGATIONS,
    PHRASING_IDS,
    PHRASINGS,
    HeldOutTaskTouched,
    PhrasingContentMismatch,
    assert_development_subset_only,
    assert_phrasings_match_in_content,
    render_phrasing,
    sensitivity_design,
)
from .stages import (
    DEFAULT_PHRASING,
    UPSTREAM_HEADER,
    PromptStructureChanged,
    StagePrompt,
    build_stage_prompt,
    draft_prompt,
    formalise_prompt,
    plan_prompt,
)

__all__ = [
    "ANSWER_FIRST_ORDER",
    "CANDIDATE_D_FIELD_ORDER_PROBE",
    "CANONICAL_FIELD_ORDER",
    "SEMANTIC_PREREQUISITES",
    "AnswerFirstNotLicensed",
    "FieldOrderArm",
    "FieldOrderViolation",
    "FieldRole",
    "assert_gate_field_order",
    "official_gate_field_order",
    "validate_field_order",
    "INSTRUCTION_OBLIGATIONS",
    "PHRASING_IDS",
    "PHRASINGS",
    "HeldOutTaskTouched",
    "PhrasingContentMismatch",
    "assert_development_subset_only",
    "assert_phrasings_match_in_content",
    "render_phrasing",
    "sensitivity_design",
    "DEFAULT_PHRASING",
    "UPSTREAM_HEADER",
    "PromptStructureChanged",
    "StagePrompt",
    "build_stage_prompt",
    "draft_prompt",
    "formalise_prompt",
    "plan_prompt",
]
