"""V1 concept-kernel ablation apparatus — HML-V1-CONCEPT-001 Phase 10.

Additive over the V0 evaluation apparatus in ``evaluation/``. Nothing here rewrites
``evaluation/corpus/cso.py``, ``evaluation/harness.py`` or ``evaluation/analyse.py``;
the ``CanonicalSemanticObject``, the deterministic answer checker, the bootstrap and
the paired-difference machinery are all imported from there.

Two constraints inherited from the V0 pilot govern every design choice in this package:

1. **The V0 corpus was saturated.** 14/15 problems correct in every arm, minimum
   detectable effect ~33 percentage points, six of seven paired contrasts with zero
   discordant pairs. This corpus is built to discriminate, not to be answered.
2. **No model may judge any output.** Every metric in ``score_v1`` is computed from a
   string or a compiler verdict. Where a quantity cannot be computed deterministically
   it is reported as ``NOT MEASURED``, never estimated.
"""

from __future__ import annotations

__all__ = ["V1_EVAL_VERSION"]

#: Bump when the corpus content or the arm surface changes. Analyses record it so a
#: result cannot be silently compared against a different corpus.
V1_EVAL_VERSION = "hml-v1-ablation-0.1.0"
