"""The minimal V1 pipeline: a mathematical problem to a verified answer, once.

Entry point::

    .venv/bin/python -m hamiltonian_lang.v1.solve --problem <file>

The pipeline is a driver over machinery that already exists elsewhere in this repository.
See :mod:`hamiltonian_lang.v1.pipeline.run` for what is borrowed from where, and
:mod:`hamiltonian_lang.v1.pipeline.problem` for the reasoning-mode oracle firewall.
"""

from __future__ import annotations

from .answer import extract_answer, grade
from .config import CONFIG_SCHEMA_VERSION, DEFAULT_SURFACE, ConfigError, SolveConfig
from .problem import (
    PROBLEM_SCHEMA_VERSION,
    AnswerKey,
    Disclosable,
    OracleGuardUnavailable,
    Problem,
    ProblemError,
    Withheld,
    assert_prompt_carries_no_oracle,
    injected_repair_text,
    load_problem,
    problem_from_dict,
    reasoning_prompt,
    repair_prompt,
)
from .record import (
    RECORD_SCHEMA_VERSION,
    AnswerRecord,
    AttemptRecord,
    SolveRecord,
    StepRecord,
    StepStatus,
    clip,
    render_summary,
)
from .run import PipelineError, build_model, solve_problem

__all__ = [
    "CONFIG_SCHEMA_VERSION",
    "PROBLEM_SCHEMA_VERSION",
    "RECORD_SCHEMA_VERSION",
    "DEFAULT_SURFACE",
    "AnswerKey",
    "AnswerRecord",
    "AttemptRecord",
    "ConfigError",
    "Disclosable",
    "OracleGuardUnavailable",
    "PipelineError",
    "Problem",
    "ProblemError",
    "SolveConfig",
    "SolveRecord",
    "StepRecord",
    "StepStatus",
    "Withheld",
    "assert_prompt_carries_no_oracle",
    "build_model",
    "clip",
    "extract_answer",
    "grade",
    "injected_repair_text",
    "load_problem",
    "problem_from_dict",
    "reasoning_prompt",
    "render_summary",
    "repair_prompt",
    "solve_problem",
]
