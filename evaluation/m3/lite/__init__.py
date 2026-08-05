"""M3-Lite — 40 fresh, domain-stratified, deliberately-not-saturated tasks.

Why this corpus exists
----------------------
HML-EVAL-001 measured nothing. All seven arms scored 93.3% on 15 problems, six of the seven
contrasts had **zero discordant pairs** — the arms did not merely score the same, they
succeeded and failed on exactly the same problems — and the minimum detectable effect was
about 33 percentage points. A design that can only see a 33-point effect cannot report the
absence of a 5-point one, which is the effect size H1 and H2 are specified at.

M3-Lite is built to the opposite constraint: a baseline in the **40–70%** band, where a
paired design has room to move in either direction.

What is new here relative to every earlier corpus
-------------------------------------------------
* **Seven domains, not five.** Linear algebra, calculus and epistemic reasoning are added;
  FormalMATH found sharp domain bias (algebra behaves nothing like number theory), so an
  overall average across domains is a number that conceals its own composition. Hence the
  per-domain **floors** in :mod:`.roster` — a corpus that meets its overall target while a
  domain sits at zero has failed, and the floor is what makes that failure visible.
* **Eight structural-error categories, five items each.** Balanced by construction, so a
  structural-error rate is comparable across categories rather than dominated by whichever
  category happened to be over-represented.
* **A distractor per item that a one-step reader actually reaches.** Recorded, and checked
  to be distinct from the answer, so near-miss failures can be classified instead of merely
  counted.
* **No contamination.** Generated under the seed namespace ``hml-m3-lite-001::``, and
  ``tests/evaluation/test_corpus_governance.py`` asserts empty intersection with every ACQ0
  split **by content hash**, not by name.

What this corpus does **not** claim
-----------------------------------
The 40–70% band is a **prediction, not a measurement**. No model call has been made. See
:mod:`.calibration`, which states the two anchor points it was derived from, computes a
deterministic shallow-reader baseline that *is* measured, and refuses to mark the band
``MEASURED`` until a real run fills it in.
"""

from __future__ import annotations

__all__ = ["M3_LITE_VERSION", "SEED_NAMESPACE", "DOMAINS", "ERROR_CATEGORIES"]

#: Bump on any change to item content, domain assignment or floors. Every manifest records
#: it, so two results can never be compared silently across different corpora.
M3_LITE_VERSION = "hml-m3-lite-001-0.1.0"

#: No earlier study used this namespace. Reusing a namespace is how "fresh tasks" quietly
#: become the tasks the model was already shown.
SEED_NAMESPACE = "hml-m3-lite-001::"

#: The seven strata. Order is fixed and reported; it is not an ordering of importance.
DOMAINS: tuple[str, ...] = (
    "algebra",
    "probability_statistics",
    "logic_and_scope",
    "dimensions_physics",
    "linear_algebra",
    "calculus",
    "epistemic_reasoning",
)

#: The eight structural-error categories, five items each. Five of the eight are the
#: project's own prohibited conflations, which is deliberate: a benchmark for this language
#: should be hardest exactly where its type system claims to be strictest.
ERROR_CATEGORIES: tuple[str, ...] = (
    "binding_scope",
    "quantifier_order",
    "role_assignment",
    "dimensional_consistency",
    "distribution_vs_value",
    "equality_vs_implication",
    "assumption_boundary",
    "approximation_vs_equality",
)
