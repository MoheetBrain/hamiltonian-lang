# Compositional Closure Framework

Status: normative. Defines what is measured by
`../ontology/COMPOSITION_TESTS.json` and how the results are interpreted.

---

## 1. The claim being tested

Feature lists are additive; mathematics is not. A system can support quantifiers,
support units, support random variables and support matrices — and still be
unable to state

> for every i, the measured height H_i is a random variable with mean μ metres
> and standard deviation σ metres, σ > 0

because that sentence requires all four capabilities to hold **simultaneously**,
in one expression, with each one's guarantees intact.

**Compositional closure** is the property that a system's capabilities do not
degrade when combined. It is the operational form of the Frege/Montague
compositionality principle: the meaning of the compound must be a function of the
meanings of the parts and their mode of combination, with nothing silently
dropped in the composing.

The hypothesis this framework exists to test — and the one that most often turns
out true — is:

> **A system's standalone capability profile systematically overstates its real
> capability, and the gap appears at composition boundaries, especially where two
> different domains meet.**

Every specimen in the suite is designed to sit on such a boundary.

---

## 2. Why standalone probing is insufficient

Three concrete mechanisms cause capabilities to fail only in combination:

1. **Type-system stratification.** Each capability is implemented at a different
   layer, and the layers do not compose. Units may attach to scalars but not to
   matrix entries; refinement types may apply to values but not to distribution
   parameters; shapes may be checked for matrices but not for matrices *inside* a
   distribution.
2. **Binder interference.** Two constructs that each bind a variable — a
   quantifier and an integral, an index and an expectation, a lambda and a
   summation — interact through scope and capture. Composition exposes capture
   bugs that a single binder never triggers.
3. **Canonicalisation collapse.** A normaliser written for one construct may, when
   applied to a compound, reorder or merge subterms in a way that is valid for the
   construct it was written for and invalid for the one it was applied to. This is
   the mechanism behind commutativity bugs in matrix expressions and quantifier
   reordering.

None of these is visible in a per-feature checklist. All three are visible in a
two-atom specimen.

---

## 3. Specimen design rules

Each specimen satisfies:

- **R1 — Two or more atoms, from two or more domains where possible.** Same-domain
  specimens are included only where the interaction is itself the hard part (e.g.
  nested quantifier order).
- **R2 — Mathematically ordinary.** Every specimen is a statement a working
  mathematician, statistician, physicist or engineer would actually write. The
  suite tests real composition, not contrived pathology. Where a specimen *is*
  adversarial, it is marked `adversarial: true` and its purpose is stated.
- **R3 — Stated in prose and in standard notation.** Both are given, so a system's
  encoding can be checked against the mathematics rather than against another
  system's encoding.
- **R4 — A stated reason it is hard.** `why_hard` names the specific interaction,
  not a generality.
- **R5 — Predicted failure surfaces.** `expected_failure_modes` names which layer
  is expected to break, drawn from the fixed vocabulary in §4. This is a
  falsifiable prediction made before probing: if a system fails somewhere else,
  that is itself a finding about the framework.
- **R6 — No system-specific content.** Specimens contain no construct, keyword or
  idiom from any candidate system.

---

## 4. Failure-surface vocabulary

`expected_failure_modes` draws from exactly these seven values:

| Value | The layer that breaks |
|---|---|
| `GRAMMAR` | The compound cannot be written: no surface form exists, or the parse is ambiguous. |
| `TYPE_SYSTEM` | It parses, but the type discipline cannot express or check the compound type (shape inside a distribution, unit on a tensor component, refinement on a parameter). |
| `SEMANTIC_MODEL` | It typechecks, but the internal model has no place to put one of the facts — the fact has nowhere to live even though the syntax accepted it. |
| `CANONICALIZATION` | The compound is representable but the normal form loses or corrupts a distinction. |
| `COMPILER` | The checker/translator crashes, times out, or produces an internal error on the compound. |
| `BACKEND` | The compound is representable internally but no target can receive it, and the translation drops the interaction. |
| `UNSUPPORTED` | One or more participating atoms is absent, so the specimen cannot be attempted. |

Multiple values may be listed; they are predictions of where breakage is
plausible, ordered most-likely first.

---

## 5. Scoring a specimen

For each (system, specimen) pair, record one outcome from the table in
`METRIC_DEFINITIONS.md` §4 (`COMPOSES`, `COMPOSES_DEGRADED`,
`COMPOSES_SILENT_LOSS`, `REJECTED_SPURIOUS`, `REJECTED_CORRECT`, `UNSUPPORTED`)
plus:

```json
{
  "specimen_id": "CT-014",
  "system": "...",
  "outcome": "COMPOSES_DEGRADED",
  "encoding": "<verbatim>",
  "per_atom_codes": {"LOGIC.FORALL": "P", "SCI.QUANTITY": "L"},
  "standalone_codes": {"LOGIC.FORALL": "P", "SCI.QUANTITY": "P"},
  "degradation": [
    {"atom": "SCI.QUANTITY",
     "standalone": "P", "in_composition": "L",
     "fact_lost": "the unit of the standard deviation",
     "declared_by_system": true}
  ],
  "observed_failure_surface": "TYPE_SYSTEM",
  "predicted_failure_surfaces": ["TYPE_SYSTEM", "SEMANTIC_MODEL"],
  "composition_cost": 2.4
}
```

`per_atom_codes` versus `standalone_codes` is the load-bearing comparison. The
**compositional closure gap** for a system is

```
gap(S) = { (specimen, atom) : code_in_composition(S, atom, specimen)
                              is strictly worse than standalone_code(S, atom) }
```

and `|gap(S)|`, together with the list itself, is the framework's primary output.
A system with a large gap has a capability profile that its documentation
overstates — which is a finding about the documentation as much as the system.

---

## 6. Derived measures

```
compositional_closure_rate(S)
    = |COMPOSES| + |REJECTED_CORRECT|
      ─────────────────────────────────────────────
      |attempted specimens| − |UNSUPPORTED|

silent_composition_loss_count(S)   = |COMPOSES_SILENT_LOSS|        # must be 0 for level 3
critical_composition_failures(S)   = specimens with COMPOSES_SILENT_LOSS
                                     involving a CRITICAL atom     # any > 0 caps maturity
degradation_depth(S)               = mean over gap(S) of the code-distance
                                     P>S>C>B>L>0 between standalone and composed
prediction_accuracy                = |observed surface ∈ predicted| / |attempted|
```

`prediction_accuracy` scores the *framework*, not the system. A low value means
the specimens' `expected_failure_modes` were wrong and should be revised — a
required piece of self-criticism, since a framework that never checks its own
predictions cannot be shown to be measuring what it claims.

---

## 7. Interpreting results honestly

- **`REJECTED_CORRECT` is a pass.** A system that refuses `1 m + 1 s` inside a
  quantified statement is behaving correctly; it must not be scored as a failure
  because a rejection was observed. Every rejection must be adjudicated as correct
  or spurious against the mathematics, never against convenience.
- **`UNSUPPORTED` is excluded, and counted.** A system missing an atom entirely is
  not additionally penalised in the composition rate — that gap is already
  reported in coverage — but the count of excluded specimens is reported, because
  a high exclusion count means the composition rate is computed over a small and
  possibly easy subset.
- **A high closure rate over few attempted specimens is not a strong result.**
  Always report `attempted / total`.
- **Degradation that is declared is not the same as degradation that is silent.**
  `COMPOSES_DEGRADED` with a loss record is an honest limitation;
  `COMPOSES_SILENT_LOSS` is a defect. They are never summed.
- **The gap list is the deliverable.** The rate is a summary; the enumerated
  (specimen, atom, fact lost) triples are what a maintainer can act on and what a
  reader can verify.

---

## 8. Suite composition

The suite in `../ontology/COMPOSITION_TESTS.json` contains 48 specimens, and
covers every interaction the task specification requires, at minimum:

| Required interaction | Specimen(s) |
|---|---|
| quantifier + probability | CT-001, CT-021 |
| quantifier + matrix | CT-002 |
| quantifier + units | CT-003 |
| probability + dimensions | CT-004, CT-028 |
| probability + optimization | CT-005, CT-024 |
| matrix + symbolic constraint | CT-006 |
| function returning a distribution | CT-007 |
| indexed / families of random variables | CT-008 |
| derivative of a probabilistic objective | CT-009 |
| integral carrying units | CT-010 |
| local assumption inside a function body | CT-011 |
| scoped constraint | CT-012 |
| objective over derived state | CT-013 |
| tensor inside a proposition | CT-014 |
| nested quantifier ORDER (∀∃ vs ∃∀) | CT-015 |
| approximate value inside a proof obligation | CT-016 |
| matrix-valued random variable | CT-017 |
| conditional distribution given a sigma-algebra | CT-018 |
| piecewise domain | CT-019 |
| statement quantifying over functions | CT-020 |

The remaining 28 specimens extend coverage to triple compositions, causal and
epistemic composition, unit-aware calculus, canonicalisation traps, and the
number-system and discrete-mathematics boundaries.

---

## 9. Known limitations of this framework

Stated so they are not discovered as gotchas:

1. **Finite suite.** 48 specimens cannot cover the composition space. A failure
   mode not represented here will not be detected. Mitigation: any newly found
   mode is added as a specimen and every system is re-run.
2. **Author bias in `why_hard`.** The specimens were designed by predicting where
   systems break. Those predictions could be wrong in a correlated way.
   Mitigation: `prediction_accuracy` is measured and reported.
3. **Encoding quality is a confound.** A poor encoding by the person probing can
   look like a system limitation. Mitigation: every encoding is stored verbatim
   and is open to a counter-encoding; a system's maintainers' better encoding, if
   supplied, replaces ours and the result is re-scored.
4. **Fact-loss detection depends on the system's introspection.** If a system
   offers no way to inspect what it stored, distinguishing `COMPOSES` from
   `COMPOSES_SILENT_LOSS` becomes a judgement about its printer. Systems with no
   introspection surface are recorded as `?` on that axis rather than assumed
   faithful.
