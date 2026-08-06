"""The single configuration object for the V1 solve pipeline.

One file, read once, recorded verbatim into every result record. Nothing in the pipeline
reads an environment variable or a global: if a run behaved a certain way, the reason is
in :meth:`SolveConfig.to_dict` and therefore in the JSON.

The surface is a configuration value
------------------------------------
Round 1 of the syntax gate has not been run, so the winning candidate is not known. The
pipeline therefore never names a surface in code: it names
:data:`DEFAULT_SURFACE` here and resolves it through
``evaluation.syntax_gate.candidates.resolve_adapters``. Switching to B, C or D is a
one-line edit to the config *file*, not to any module.

``DEFAULT_SURFACE`` is spelled out rather than imported so that this package does not
take a hard import dependency on the evaluation tree just to hold a default.
``tests/v1/test_solve_pipeline.py`` asserts it equals ``candidates.A_V0_LINEAR``, so the
two cannot drift silently.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...repair.arms import FeedbackArm
from ...repair.budget import RepairBudget

__all__ = [
    "CONFIG_SCHEMA_VERSION",
    "DEFAULT_SURFACE",
    "ConfigError",
    "SolveConfig",
]

CONFIG_SCHEMA_VERSION = "hml-v1-solve-config-1.0.0"

#: Must equal ``evaluation.syntax_gate.candidates.A_V0_LINEAR``; a test enforces it.
DEFAULT_SURFACE = "A_v0_labelled_linear"


class ConfigError(ValueError):
    """The configuration file is unusable. Never repaired by defaulting."""


@dataclass(frozen=True)
class SolveConfig:
    """Everything that varies between runs of ``hamiltonian_lang.v1.solve``."""

    #: Candidate id resolved through ``resolve_adapters``. Config value, never a literal
    #: in the pipeline code.
    surface: str = DEFAULT_SURFACE
    #: ``scripted`` is the only backend this milestone ships. A live backend is refused
    #: unless ``allow_live_model`` is set *and* an adapter is registered, so an offline
    #: suite cannot drift online and a stray call cannot perturb another run.
    model: str = "scripted"
    allow_live_model: bool = False
    #: Official ACQ0/H3 preregister exactly one repair. The pipeline enforces it.
    repair_budget: RepairBudget = RepairBudget.OFFICIAL_ONE
    #: What the repair turn is allowed to show. The treatment arm is the default.
    feedback_arm: FeedbackArm = FeedbackArm.CHAIN_OF_REPAIR
    #: ``SympyExecutionVerifier`` spawns a subprocess; off by default.
    include_execution_verifiers: bool = False
    #: Display-only cap for the terminal summary. The JSON record is **never** truncated,
    #: and any display truncation is reported with the exact number of omitted characters.
    summary_max_chars: int = 1200
    #: Where result records are written. ``None`` means stdout only.
    output_dir: str | None = None
    source_path: str = "<defaults>"
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.surface).strip():
            raise ConfigError("surface is empty; there is no default surface in code")
        if self.model != "scripted" and not self.allow_live_model:
            raise ConfigError(
                f"model {self.model!r} is not the scripted backend and allow_live_model "
                "is false. A live model call is refused rather than made: this milestone "
                "shares a host with other measured runs."
            )
        if self.summary_max_chars < 0:
            raise ConfigError("summary_max_chars must be >= 0")

    # -- loading -----------------------------------------------------------------

    @staticmethod
    def load(path: str | Path | None) -> SolveConfig:
        """Read a JSON config. ``None`` yields the documented defaults, recorded as such."""
        if path is None:
            return SolveConfig()
        p = Path(path)
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigError(f"config file {p} does not exist") from exc
        except json.JSONDecodeError as exc:
            raise ConfigError(f"config file {p} is not valid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigError(f"config file {p} must contain a JSON object")
        return SolveConfig.from_dict(raw, source_path=str(p))

    @staticmethod
    def from_dict(raw: dict[str, Any], *, source_path: str = "<dict>") -> SolveConfig:
        known = {
            "surface", "model", "allow_live_model", "repair_budget", "feedback_arm",
            "include_execution_verifiers", "summary_max_chars", "output_dir",
        }
        extra = {k: v for k, v in raw.items() if k not in known}
        try:
            budget = RepairBudget(raw.get("repair_budget", RepairBudget.OFFICIAL_ONE.value))
        except ValueError as exc:
            raise ConfigError(f"{source_path}: unknown repair_budget: {exc}") from exc
        try:
            arm = FeedbackArm(raw.get("feedback_arm", FeedbackArm.CHAIN_OF_REPAIR.value))
        except ValueError as exc:
            raise ConfigError(f"{source_path}: unknown feedback_arm: {exc}") from exc
        return SolveConfig(
            surface=str(raw.get("surface", DEFAULT_SURFACE)),
            model=str(raw.get("model", "scripted")),
            allow_live_model=bool(raw.get("allow_live_model", False)),
            repair_budget=budget,
            feedback_arm=arm,
            include_execution_verifiers=bool(raw.get("include_execution_verifiers", False)),
            summary_max_chars=int(raw.get("summary_max_chars", 1200)),
            output_dir=raw.get("output_dir"),
            source_path=source_path,
            extra=extra,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "source_path": self.source_path,
            "surface": self.surface,
            "model": self.model,
            "allow_live_model": self.allow_live_model,
            "repair_budget": str(self.repair_budget),
            "repair_limit": self.repair_budget.limit,
            "feedback_arm": str(self.feedback_arm),
            "include_execution_verifiers": self.include_execution_verifiers,
            "summary_max_chars": self.summary_max_chars,
            "output_dir": self.output_dir,
            "extra": dict(self.extra),
        }
