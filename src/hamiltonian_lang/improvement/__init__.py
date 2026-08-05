"""The improvement subsystem: versioned state, memory, skills, staging, evidence.

This package is **offline and non-training**. Nothing in it calls a model provider,
holds weights, or promotes anything automatically. It records what happened, decides
what is admissible, and refuses what is not yet earned.

Module map (owner in brackets is the build-time split, not a runtime boundary):

* ``state``      — Phase 5: the versioned ``SystemState``, the typed ``Hypothesis``, and
  the one-component-at-a-time transition rule.
* ``memory``     — Phase 10: four append-only stores and the routing that fills them.
* ``skills``     — Phase 11: the versioned skill taxonomy and per-skill aggregation.
* ``controller`` — Phase 12: the staged controller. Only stage 0 is executable.
* ``evidence``   — Phase 13: the evidence package and the promotion dry-run.
* ``runner``     — Phase 14: the offline one-repair arena.

``episodes``, ``events``, ``ledger``, ``diagnostics`` and ``verification`` are built
separately; the modules here talk to them through narrow ``Protocol`` declarations so
that neither half has to exist for the other to be tested.

Nothing is re-exported at package level on purpose. The submodules carry meaning that a
flat namespace would blur — ``improvement.state.Hypothesis`` says where the hypothesis
lives, ``improvement.Hypothesis`` does not.
"""

from __future__ import annotations

__all__: list[str] = []
