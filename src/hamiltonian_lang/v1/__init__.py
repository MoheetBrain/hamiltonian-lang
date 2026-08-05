"""Hamiltonian V1 — Concept Kernel.

HML-V1-CONCEPT-001. Additive over V0, which is frozen at tag ``hml-v0-baseline`` and must
not change. Six narrowly scoped layers:

1. typed concept registry
2. concept-minting protocol
3. semantic morphology
4. transformation and inference edges
5. epistemic-status types
6. discourse-state types

The gate that licensed this work (`docs/evaluation/V1_GATE_DECISION.md`) passed on two
criteria only: compiler feedback improves encoding reliability, and the pilot exposed a
specific weakness worth testing. It did **not** pass on any reasoning improvement.

**V1 may therefore claim to make errors catchable. It may not YET claim to make reasoning
better** — that claim is unproven, not refuted. The V0 pilot was underpowered with a severe
ceiling effect (14 of 15 problems solved by nearly every arm), so it could not have
detected an effect of any realistic size. HML-EVAL-002 is the first adequately powered
test.
"""

from __future__ import annotations

__all__ = ["V1_VERSION"]

V1_VERSION = "hml-v1-concept-kernel-0.1.0-DESIGN"
