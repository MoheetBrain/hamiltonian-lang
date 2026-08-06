# ACQ0 v2 proof-corpus audit

Eight fresh tasks, each **originating** as a `CanonicalAcq0TaskV2` — none is a repaired
v1 record. All ids are new and were never shown to any model.

## Admission results

| task | family | compiles | A/B/C/D round-trip | views distinct | hash | decls | defs |
|---|---|---|---|---|---|---|---|
| `v2_binding_dependency_001` | binding_dependency | ok | 4/4 exact | ok | `de1f550e4960` | 2 | 2 |
| `v2_assumption_boundary_001` | assumption_boundary | ok | 4/4 exact | ok | `ea15c3de3373` | 2 | 1 |
| `v2_implication_equivalence_001` | implication_vs_equivalence | ok | 4/4 exact | ok | `f8088306b9ec` | 2 | 2 |
| `v2_approximation_equality_001` | approximation_vs_equality | ok | 4/4 exact | ok | `5ec8d81b39c5` | 3 | 0 |
| `v2_quantifier_scope_001` | quantifier_scope | ok | 4/4 exact | ok | `6403b51b37d2` | 0 | 1 |
| `v2_probability_law_role_001` | probability_law_role | ok | 4/4 exact | ok | `a5ec3ef23cc5` | 3 | 0 |
| `v2_dimensional_algebra_001` | dimensional_algebra | ok | 4/4 exact | ok | `d4127dfdd621` | 2 | 1 |
| `v2_transformation_side_condition_001` | transformation_side_condition | ok | 4/4 exact | ok | `76e41aa93cf5` | 3 | 0 |

**8/8 admissible.**

Every task satisfies: schema validation · required initialisers present · required bodies
present · all names resolve · exactly one epistemic category per proposition · complete
model-visible rendering · prose consistent with the object · private target equals the
canonical object · reference compiles · reference canonicalises to the expected hash ·
exact round-trip through all four surfaces · no leakage into model-input artefacts.

## Canonical-identity sensitivity

Measured directly, not assumed:

| change | required | observed |
|---|---|---|
| bound variable renamed | equal | equal |
| function binder renamed | equal | equal |
| literal `5` → `7` | differ | differ |
| `Beta(alpha, beta)` roles swapped | differ | differ |
| `forall∃` → `exists∀` | differ | differ |
| `p implies q` → `q implies p` | differ | differ |
| function body `e / m` → `e * m` | differ | differ |

## Old corpus

The 41 v1 tasks stay quarantined as `INVALID_INSTRUMENT_PENDING_AUDIT`,
`schema_version: acq0.v1.lossy`, `eligibility: false`. Their ids, public and private
records, raw GPT and DeepSeek outputs and the admission audit are unchanged. No v1 id is
reused; v2 ids all carry the `v2_` prefix and a test enforces it.

## Unresolved limitations

- **Eight tasks, not 41.** Regeneration of the full corpus is deliberately not attempted.
- **`state_in_prose` is a per-task judgement.** Only one task exercises a derived fact.
- **Prose is machine-plain**, and its readability under a frontier model is unmeasured.
- **No model has seen any v2 task.** Admission proves the instrument is self-consistent;
  it says nothing about whether a model can encode these surfaces.
- **H3 remains interface-only**; the repair view is unimplemented by design.
- The `EpistemicCategory` enum exists and is validated for derived facts, but propositions
  are categorised structurally (assume/require/prove) rather than by an explicit per-
  statement label. Sufficient for these eight; a task needing two categories on one
  statement would require the cross-reference the schema mentions but does not yet carry.

## Did any HML syntax change?

**No.** No grammar, keyword, canonical form or type was added or altered. Surface B
required **no executable change**: its grammar renders `mod` / `dec const … :=` / `fun`
and accepts exactly what it renders, and the earlier ChatGPT output imported with zero
diagnostics. The suspected `def`/`fun` and `=`/`:=` conflict was documentation prose, not
the rule card, and did not reproduce in the executable path.
