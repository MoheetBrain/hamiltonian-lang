"""Phase F2/G2-G4 apparatus for the four-syntax acquisition tournament.

Additive over the V0 apparatus in ``evaluation/`` and the V1 apparatus in
``evaluation/v1/``. Nothing here rewrites ``evaluation/corpus/cso.py``,
``evaluation/semantic_equiv.py`` or ``evaluation/analyse.py``; the
``CanonicalSemanticObject``, the deterministic answer checker, the semantic
comparator, the bootstrap, exact McNemar and Cohen's h are all imported from there.

Three separations govern every design choice in this package.

**Track A decides the gate; Track B never can.** ``partition`` splits the corpus into
Track A (semantic objects representable *and* scoreable in all four candidate syntaxes)
and Track B (V1 capability: epistemic calibration, discourse obligations, semantic
morphology, concept structures, richer transformation relations). Track B is engineering
validation. ``stats.gate_verdict`` consumes only ``TRACK_A_GATE_IDS`` and
``tests/evaluation/test_syntax_gate_partition.py`` proves by differential test that
adding arbitrary Track B trials leaves every gate numerator and denominator bit-identical.

**Nothing here calls a model.** Phase ordering is strict: the offline equivalence gate
(F3) must pass and the Lead must freeze (F4) before any generation is legitimate.
``harness.run_tournament`` refuses a live adapter until the freeze manifest exists, and
the tests drive it with ``StubAdapter`` only.

**A facet that has never been observed failing is not known to work.** The HML-EVAL-001
pilot shipped a scorer that returned 0.0 when nothing was checkable and silently zeroed
25 problems. ``mutations`` therefore carries a synthetic passing case *and* a synthetic
failing case for every scorer facet, and the scorer reports ``NotMeasured`` — never 0.0 —
when a facet has no denominator.
"""

from __future__ import annotations

__all__ = ["SYNTAX_GATE_VERSION", "TRACK_A", "TRACK_B", "TRACKS"]

#: Bump when the partition content, the prompt text or the scorer contract changes.
#: Every manifest and every analysis records it, so a result cannot be silently compared
#: against a different corpus or a different scorer.
SYNTAX_GATE_VERSION = "hml-phase-fg-001-syntax-gate-0.1.0"

#: Shared core. The only track that may influence the Gate 2 verdict.
TRACK_A = "A_shared_core"
#: V1 capability. Engineering validation only; structurally excluded from the gate.
TRACK_B = "B_v1_capability"

TRACKS = (TRACK_A, TRACK_B)
