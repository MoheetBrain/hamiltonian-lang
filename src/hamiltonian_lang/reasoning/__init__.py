"""The V2 reasoning layer: derivations, obligations, refinement, adjudication.

Three modules, in dependency order:

* :mod:`.kernel` -- the trusted inference rules. Small, local, and the only thing in
  the language that can certify a step.
* :mod:`.refinement` -- the environment Γ that turns assumptions into discharged
  obligations, conservatively.
* :mod:`.check` -- the compiler pass that resolves claims, applies the kernel, and
  adjudicates ``proved``.
"""

from __future__ import annotations

from .check import (
    ObligationStatus,
    ReasoningObligation,
    ReasoningResult,
    check_reasoning,
)
from .kernel import RULES, RuleApplication, RuleSpec, apply, rule_names
from .refinement import Fact, RefinementEnv

__all__ = [
    "ObligationStatus",
    "ReasoningObligation",
    "ReasoningResult",
    "check_reasoning",
    "RULES",
    "RuleApplication",
    "RuleSpec",
    "apply",
    "rule_names",
    "Fact",
    "RefinementEnv",
]
