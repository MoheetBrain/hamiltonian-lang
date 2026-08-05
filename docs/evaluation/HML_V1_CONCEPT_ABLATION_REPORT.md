# HML-V1 Concept-Kernel Ablation — Report

Status: **PREREGISTERED SKELETON. NO DATA EXISTS.** Every results cell reads `NOT YET RUN`
and no number in this document is a measurement of model behaviour. The design-time
figures in §3 and §4 are computed from the corpus with no model in the loop and are
reproducible with:

```bash
.venv/bin/python -m evaluation.v1.score_v1 --design
```

This document is written before any run so that the hypotheses, the metric definitions,
the denominators and the decision rule cannot be adjusted after a result is seen. That is
the same discipline `EVAL_SPEC_v1.0` imposed on the V0 pilot, and it is the reason the
pilot's negative result was reportable.

| | |
|---|---|
| **Corpus** | `evaluation/v1/corpus.py`, `hml-v1-ablation-0.1.0`, 60 problems |
| **Scorer** | `evaluation/v1/score_v1.py` |
| **Adversarial suite** | `tests/v1/test_adversarial_v1.py` |
| **Baseline** | `docs/evaluation/HML_EVAL_001_PILOT_REPORT.md`, `EVAL_SPEC_v1.1`, tag `hml-v0-baseline` |
| **Governing plan** | `docs/design/V1_EXPERIMENT_PLAN.md` |
| **Gate** | `docs/evaluation/V1_GATE_DECISION.md` — passed on criteria 4 and 5 only |

---

## 1. What this experiment may and may not claim

The gate that licensed V1 passed on **two** criteria: compiler feedback improves encoding
reliability, and the pilot exposed a specific weakness worth testing. It did **not** pass
on any reasoning improvement — criterion 1 was tested and refuted, with **zero discordant
pairs** across three separate controls.

Carried forward as a hard constraint on what this report may say:

- V1 may claim to make errors **catchable**. It may **not** claim to make reasoning
  better.
- No result here supersedes the pilot. The pilot measured V0 against English, structured
  English, LaTeX and Stan/Lean and found no answer-accuracy difference. Nothing in this
  ablation re-opens that question, and nothing in it may be quoted as having done so.
- **Hard gate inherited from `V1_EXPERIMENT_PLAN.md` §1: no V0-vs-V1 comparison may be
  reported until the V1 parse rate reaches ≥ 90%.** A language the model cannot write is
  not being tested. The scorer prints this warning beside every parse rate it computes.

## 2. Arms — a nested ablation, not a set of conditions

Each arm is the previous arm plus exactly one layer. That is what makes the differences
attributable.

| arm | contents |
|-----|----------|
| `SE` | structured English — the mandated 8-point schema, reused verbatim from the pilot |
| `V0` | Hamiltonian V0, the preserved baseline |
| `V1_nomint` | V0 + V1's typed vocabulary (L2–L5 surface), **minting prohibited** |
| `V1_mint` | `V1_nomint` + the admitted-concept registry + the minting protocol |
| `V1_full` | `V1_mint` + transformation edges, epistemic status and discourse state |

The contrast ladder, and what each rung isolates:

| contrast | isolates |
|----------|----------|
| `V0 − SE` | the typed representation against scaffolding (settled null at V0; retained as a sanity check, not as an open question) |
| `V1_nomint − V0` | V1's added vocabulary alone — the pure cost of surface area |
| **`V1_mint − V1_nomint`** | **concept minting. The decisive contrast.** |
| `V1_full − V1_mint` | transformation and epistemic tracking |

`A`, `B` and `C` (plain English, LaTeX, Stan/Lean) are not re-run, per plan §2.

## 3. Corpus — design facts, computed, no model involved

60 problems, 12 in each of five blocks.

| block | n | what it tests | V1 layer it is diagnostic for |
|-------|---|---------------|-------------------------------|
| `concept_recognition` | 12 | naming the concept a structure instantiates exactly, or NONE | concept registry |
| `family_derivation` | 12 | which Estimation-family member a property attaches to | concept families |
| `recurring_structure` | 12 | how many distinct structures four near-identical displays carry | concept minting / compression |
| `transformation_chain` | 12 | the index of the first step whose stated justification fails | L2 transformation |
| `epistemic_calibration` | 12 | the correct reading of a statistical situation | L4 epistemic (11), L5 discourse (1) |

### 3.1 The pilot defect this corpus exists to fix

The V0 pilot's §9 named the limitation that dominated everything else: 14 of 15 problems
correct in **every** arm, and a minimum detectable effect around 33 percentage points.
Its conclusion was explicitly not "no difference exists" but "no difference large enough
to move a saturated 15-problem set was observed".

`V1_EXPERIMENT_PLAN.md` §1 therefore requires a corpus targeting **50–60% baseline
accuracy** at **n ≥ 60**. This corpus carries n = 60 and is built item by item around a
specific near-miss.

> **The 50–60% target is a design intent. It is `NOT YET RUN` as a measurement, and it
> must not be reported as achieved until a calibration run measures it.** Every item's
> `calibration_status` field reads `NOT YET RUN`. If the first run comes back at 85% the
> corpus has failed at its one job and must be hardened before any contrast is read.

### 3.2 Chance floors — the number the pilot never reported

Most items here are multiple choice, so an accuracy must be read against a guessing floor
rather than against zero. Both floors are reported because they differ, and the larger of
the two is the one that matters.

| block | uniform guessing | always answer the modal truth |
|-------|-----------------|------------------------------|
| `concept_recognition` | 0.313 | 0.083 |
| `family_derivation` | 0.167 | **0.333** |
| `recurring_structure` | 0.250 | 0.250 |
| `transformation_chain` | 0.250 | 0.250 |
| `epistemic_calibration` | 0.246 | 0.083 |
| whole corpus | 0.245 | — (blocks use different answer spaces; do not pool) |

An arm scoring 0.35 on `family_derivation` has not demonstrated anything: always
answering `ESTIMATOR` scores 0.333.

### 3.3 Power — and a limitation that must not be buried

Computed by `minimum_detectable_discordance`, using the same exact McNemar test as
`evaluation/analyse.py`.

| unit | n pairs | discordant pairs needed at α = .05 | minimum detectable difference |
|------|---------|-----------------------------------|------------------------------|
| whole corpus | 60 | 6 | **10.0 pp** |
| any single block | 12 | 6 | **50.0 pp** |

The whole-corpus figure is a real improvement on the pilot's ≈ 33 pp. **The per-block
figure is worse than the pilot's**, and this is the most important design limitation in
this document:

> **Every per-block contrast in this experiment is underpowered.** A 50-percentage-point
> effect within one block of 12 is not a realistic target. Block-level results are
> therefore **descriptive only** and no hypothesis below is decided on one block's paired
> contrast. Where a hypothesis is inherently per-block — V1-H6 and V1-H7 are — it is
> decided on an absolute threshold against the chance floor, not on a paired significance
> test, and that is stated in the hypothesis table rather than discovered afterwards.

If a block-level paired test is wanted later, the corpus must grow to roughly 40 items in
that block. That is a corpus change and requires its own preregistration.

### 3.4 Expressibility — how much of this corpus V0 cannot state

| V0 can express the structure | problems |
|------------------------------|----------|
| yes | 1 |
| partially | 21 |
| **no** | **38** |

This is a property of V0, not a result, and it has one large consequence that must
travel with every fidelity number in this report:

> **The pilot's encoding-fidelity metric is NOT DEFINED on this corpus.** That metric
> compares an encoding against `SemanticFacts` — entities, types, roles, laws. 59 of 60
> problems here carry no such facts, because a concept, a derivation chain and an
> epistemic status have no `SemanticFacts` slot. The pilot's 0.648 must never be placed
> beside anything in §6. A separate, V1-specific `structural_preservation` measure is
> defined in §5.2 with its own denominator.

It also means the `V0` arm is, on 38 of 60 problems, answering from the prose while being
asked to produce an encoding that cannot represent the question. That is a real
disadvantage to the control and it is recorded in §9 as such, in the direction it biases.

### 3.5 The transfer set

Seven `concept_recognition` items have a correct answer that is **deliberately absent**
from the 15-concept registry the minting arms receive: `SCALE_FAMILY`, `QUASICONVEX`,
`SEMINORM`, `PSEUDOMETRIC`, `PREORDER`, `MONOID`, `ALGEBRA_OF_SETS`. Each is the strictly
weaker relative of a concept that **is** in the registry.

An arm that is better only on the five non-transfer recognition items has learnt to look
things up in its prompt. Transfer and non-transfer accuracy are therefore reported
separately and **never pooled**, and the headline for the registry layer is the
interaction, not either accuracy alone.

## 4. Adversarial cases — 11 matched pairs

`tests/v1/test_adversarial_v1.py`. Every case is a pair: one thing that must be rejected
and one near-miss that must be accepted. A rejection test with no acceptance twin cannot
distinguish a checker from a refusal, and V1-H2 is a preregistered claim about precision.

| id | must be rejected | matched near-miss that must be accepted | V0 today |
|----|------------------|----------------------------------------|----------|
| adv01 | a duplicate concept minted under a new name | a genuine specialisation (extra parameter) | accepts |
| adv02 | a concept claiming a property it does not have | the same claim recorded as `conjectured` | accepts |
| adv03 | a concept that compresses nothing (a pure synonym) | a concept abbreviating a structure that recurs ≥ 2 times | accepts |
| adv04 | `ArbitraryConcept.density` | `Normal.density` | not expressible |
| adv05 | `yields` used where `implies` is required | the same step at the layer it belongs to | not expressible |
| adv06 | a goal discharged by `Evidence` | the same goal discharged by `Proof` | not expressible |
| adv07 | `prove(fail_to_reject(H0))` | `insufficient_evidence_against(H0, under := t1)` | not expressible |
| adv08 | a p-value used as a posterior probability | the p-value typed as a `PValue` | **accepts** |
| adv09 | `with_high_probability` with no regime | the same claim with `regime := n -> infinity` | not expressible |
| adv10 | "the estimate is unbiased" | "the estimator is unbiased" | **accepts** |
| adv11 | a non-exhaustive case split | a split closed by `otherwise` | not expressible |

### 4.1 The V0 baseline, executed rather than asserted

`V1_EXPERIMENT_PLAN.md` §4 asserts "V0 behaviour: accepts" for each of these classes.
`test_recorded_v0_status_matches_the_real_compiler` runs the V0 compiler on every case
that can be written in V0 at all and checks the assertion.

**Measured, live:** of the 5 cases expressible in V0, V0 rejects **0**. Baseline recall
on the expressible cases is therefore **0.0**, and where a matched V0 pair exists V0
accepts both halves indistinguishably.

The remaining 6 cases are recorded `not_expressible`. **`not_expressible` is not a V0
success and is never counted as one** — V0 has no `entails`, `discharge`, `case` or
`fail_to_reject`, so "V0 rejects this source" would be a missing keyword masquerading as
a caught error. `test_cases_v0_cannot_express_are_recorded_as_such_not_as_v0_successes`
enforces the distinction.

### 4.2 V1 implementation coverage, at the time of writing

**Measured, live:** 10 of 11 cases bind to a V1 module that exists and pass.

**One case is OPEN:** `adv08`, the p-value-as-posterior conflation. There is no `PValue`
type anywhere in `src/hamiltonian_lang/v1/`, V0 types both sides as `Probability`, and
the conflation therefore type-checks today. `V1_KERNEL.md` §7 item 3 and
`spec/v1/semantic_objects.yaml::no_coercion_between` both name this prohibition and
neither is implemented. The test is `xfail` against `hamiltonian_lang.v1.types:PValue`
and will turn green unchanged when that module lands.

This matters more than one row suggests. `spec/v1/semantic_objects.yaml::kill_criteria`
sets L4's criterion as **"any prohibited conflation type-checks"**. One of the nine
prohibited conflations currently does.

## 5. Metrics — definition and denominator

Every metric below is computed by `evaluation/v1/score_v1.py`. **No model judges any
output at any point.** Anything not measured is returned as a `NotMeasured` object
carrying its reason, its denominator and the field that would supply it; it is never
returned as zero and never omitted.

### 5.1 Primary

| # | metric | definition | denominator |
|---|--------|-----------|-------------|
| 1 | **mathematical-answer accuracy** | `check_answer` on the marked answer, re-derived from `raw_output` at analysis time | trials per arm (60 per generation) |
| 8 | **epistemic-calibration accuracy** | answer accuracy restricted to the epistemic block | 12 items per arm |
| 8b | **accuracy on insufficient-evidence items** | accuracy on the 5 items whose correct answer is that the evidence supports no conclusion | 5 items per arm |
| 8c | **prohibited-status rate** | encodings using a status the item prohibits (`prove` over an `Evidence` claim, etc.), by regex over the encoding | trials in the block that produced an encoding |

Metric 8b is the headline for L4. Its items are `ep01_fail_to_reject`,
`ep04_underpowered_null`, `ep05_interval_contains_zero`, `ep10_multiplicity`,
`ep11_absence_of_evidence` — the ones where "H0 is true", "there is no effect" and "H0 is
proved" are all wrong and "insufficient evidence against H0" is right.

### 5.2 Secondary

| # | metric | definition | denominator |
|---|--------|-----------|-------------|
| 2 | **semantic preservation (V1)** | `structural_preservation`: fraction of the problem's checkable V1 facets the encoding records | encodings with ≥ 1 checkable facet |
| 2b | **semantic preservation (V0-style)** | the pilot's encoding score | **NOT DEFINED** — 1 of 60 problems carries `SemanticFacts` (§3.4) |
| 3 | **valid concept admission** | minted concepts classified `valid_admission` | all concepts minted |
| 4 | **duplicate-concept rejection** | adversarial duplicate cases the checker rejects | 3 minting cases (adv01–03) |
| 5 | **false-novelty rate** | minted concepts that are unlicensed, synonymous, or carry no testable consequence | all concepts minted |
| 6 | **valid family-member derivation** | accuracy on the family block | 12 items per arm |
| 7 | **transformation correctness** | exact match on the first-invalid-step index | 12 items per arm |
| 7b | **specificity on valid chains** | correct `0` on the 3 wholly-valid chains | 3 items per arm |
| 7c | **obligation recorded** | encoding records the faulty step's side condition | faulted chains producing an encoding |
| 9 | **verifier acceptance** | obligations a prover discharged / obligations generated | **NOT MEASURED** (§5.4) |
| 10 | **transfer** | accuracy on transfer vs non-transfer recognition items, and their interaction | 7 transfer / 5 non-transfer |
| 11 | **token cost** | mean prompt and completion tokens | trials per arm |
| 12 | **latency cost** | mean wall-clock seconds | trials per arm |

Metric 7b is the guard against a "always report a fault" strategy. Three of twelve chains
are wholly valid; answering `0` is the only way to score them, and an arm that never
answers `0` is capped at 9/12.

### 5.3 A bound, stated rather than glossed

`classify_minted_concept` matches concept **names**, not formal definitions. Two concepts
with different names and identical definitions are counted as valid by it. That is
precisely the case the minting protocol exists to catch, and catching it needs the
registry's structural matcher.

> **The reported false-novelty rate is a LOWER BOUND.** Definition-level duplication is
> reported as `NOT MEASURED` with the required interface named.

### 5.4 Verifier acceptance stays NOT MEASURED

The V0 pilot reported verifier acceptance as not measured because no theorem prover was
ever invoked. Nothing in V1 changes that. It remains `NOT MEASURED` until a real prover
accepts or rejects a real obligation.

**Parser acceptance is not verifier acceptance.** Reporting one in place of the other
would be the single most misleading number this apparatus could produce, and
`verifier_acceptance()` refuses to do it.

## 6. Preregistered hypotheses

Inherits V1-H1 to V1-H5 from `V1_EXPERIMENT_PLAN.md` §5 unchanged, and adds four specific
to the concept kernel. Each states in advance what falsifies it.

| id | claim | falsified if | decided on |
|----|-------|-------------|-----------|
| **V1-H1** | V1 rejects the error classes V0 accepts | recall < 30% on any layer's errors | adversarial suite |
| **V1-H2** | V1's rejections are specific, not indiscriminate | precision < 0.7 on the matched near-misses | adversarial suite |
| **V1-H3** | V1's added surface does not degrade encoding fidelity | V1 structural preservation materially below `V1_nomint`'s | metric 2, paired |
| **V1-H4** | the model can write V1 as reliably as V0 | V1 parse rate below V0's, or below 90% absolute | metric 2, parse rate |
| **V1-H5** | compiler feedback helps V1 at least as much as V0 | the fidelity gain is not positive | **not testable in this design** — no feedback arm; see §10 |
| **V1-H6** | the admitted-concept registry raises concept recognition | `V1_mint` recognition accuracy is not above the 0.313 uniform floor by a margin exceeding its bootstrap CI | absolute threshold, per §3.3 |
| **V1-H7** | the family layer prevents the estimator/estimate confusion | `V1_mint` family accuracy does not exceed the 0.333 modal floor | absolute threshold, per §3.3 |
| **V1-H8** | any registry advantage is a concept advantage, not a lookup | the transfer difference is ≈ 0 while the non-transfer difference is positive | interaction, metric 10 |
| **V1-H9** | minting arms do not manufacture concepts | false-novelty rate > 0.3 among minted concepts | metric 5 |

**V1-H4 is the one most likely to fail and the one to watch.** V1 adds four layers to a
language the model already wrote unparseably 27–50% of the time, and the `V1_mint` prompt
is 3.1× the `V0` prompt in characters. Every added construct is another thing to get
wrong.

**V1-H8 is the one this design exists to make answerable.** It is also the one most likely
to embarrass the registry: a registry that lists the answer is an answer key, and the
transfer set is the only thing standing between a real result and that artefact.

### 6.1 Recorded in advance so a surprise is visible as one

Repeating the gate decision's prediction and adding this ablation's own:

1. **L4 epistemic** is most likely to justify itself — its claims are type-level and
   checkable with no model in the loop. Ten of eleven adversarial cases already pass.
2. **The registry is most likely to produce a spurious positive**, via the lookup
   artefact V1-H8 is designed to detect.
3. **`V1_full` is most likely to be the most expensive arm and no more accurate**, by
   analogy with the pilot's arm A′ — the most expensive arm, buying exactly zero accuracy,
   and the least stable on replication.

## 7. Results

**`NOT YET RUN`.** No model has been run against this corpus. No cell below has a value,
and none may be filled by estimate, analogy or expectation.

### 7.1 Coverage

| | |
|---|---|
| planned calls | `NOT YET RUN` (60 problems × 5 arms × generations) |
| completed calls | `NOT YET RUN` |
| unrun cells | `NOT YET RUN` |
| fully covered problem-generation cells | `NOT YET RUN` |

### 7.2 Answer accuracy per arm

| arm | trials | accuracy | 95% CI |
|-----|--------|----------|--------|
| `SE` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V0` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_nomint` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_mint` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_full` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |

### 7.3 Ladder contrasts

Discordant-pair counts are reported beside every difference. The pilot's decisive finding
was six contrasts with **zero** discordant pairs — invisible in an accuracy column and
unmissable in this one.

| contrast | difference | 95% CI | discordant | McNemar p | Cohen's h |
|----------|-----------|--------|-----------|-----------|-----------|
| `V0 − SE` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_nomint − V0` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_mint − V1_nomint` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_full − V1_mint` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |

### 7.4 Per block

Descriptive only — see §3.3. Read every cell against its chance floor.

| block | floor | `SE` | `V0` | `V1_nomint` | `V1_mint` | `V1_full` |
|-------|-------|------|------|-------------|-----------|-----------|
| `concept_recognition` | 0.313 | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `family_derivation` | 0.333 | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `recurring_structure` | 0.250 | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `transformation_chain` | 0.250 | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `epistemic_calibration` | 0.246 | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |

### 7.5 Concept admission

| | value |
|---|---|
| concepts minted | `NOT YET RUN` |
| valid concept admission rate | `NOT YET RUN` |
| false-novelty rate (lower bound, §5.3) | `NOT YET RUN` |
| duplicate-concept rejection rate | `NOT YET RUN` |
| definition-level duplication | `NOT MEASURED` — needs the registry structural matcher |

If no arm mints anything, that is itself the finding: **an arm given a minting protocol
that never mints has not exercised the layer**, and the layer's contribution to any
accuracy difference is zero by construction.

### 7.6 Transfer

| arm | transfer (n=7) | non-transfer (n=5) | interaction |
|-----|---------------|-------------------|-------------|
| `V1_nomint` | `NOT YET RUN` | `NOT YET RUN` | — |
| `V1_mint` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_full` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |

### 7.7 Epistemic calibration — the highest-value block

| arm | block accuracy | accuracy on insufficient-evidence items (n=5) | prohibited status in encoding |
|-----|---------------|----------------------------------------------|------------------------------|
| `SE` | `NOT YET RUN` | `NOT YET RUN` | n/a — no encoding |
| `V0` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_nomint` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_mint` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_full` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |

### 7.8 Transformation chains

| arm | exact index | recall on faulted (n=9) | specificity on valid (n=3) | obligation recorded |
|-----|------------|------------------------|---------------------------|--------------------|
| all | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |

### 7.9 Parse rate and the gate

| arm | parse rate | gate (≥ 90%) |
|-----|-----------|--------------|
| `V0` | `NOT YET RUN` | — |
| `V1_nomint` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_mint` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_full` | `NOT YET RUN` | `NOT YET RUN` |

**If any V1 arm's parse rate is below 90%, §7.3 must not be read at all.**

### 7.10 Cost

| arm | prompt chars (design-time, measured) | prompt tok | completion tok | latency s |
|-----|--------------------------------------|-----------|----------------|-----------|
| `SE` | 1,446 | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V0` | 3,862 | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_nomint` | 6,554 | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_mint` | 12,146 | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |
| `V1_full` | 12,338 | `NOT YET RUN` | `NOT YET RUN` | `NOT YET RUN` |

The prompt-character column is a measured property of the renderers, not of any model.
It is here because it is the confound in §9 item 1, and stating it in advance is the only
way to stop it being discovered as a surprise later.

## 8. Decision rule, fixed in advance

Applied in this order. The order matters: a later step is not consulted if an earlier one
disposes of the question.

1. **Parse gate.** If any V1 arm's parse rate < 90%, the verdict is
   `V1 ADDS STRUCTURE WITHOUT MEASURABLE BENEFIT` on the ground that the comparison could
   not be run, and no contrast in §7.3 is reported as a result.
2. **Corpus validity.** If baseline (`SE`) accuracy exceeds 80% or falls below 25%, the
   corpus has failed its calibration and **no verdict is issued at all** — the run is a
   calibration run, reported as such, and the corpus is revised before the experiment.
3. **Harm.** If any V1 arm's accuracy is below `V0`'s with a paired CI excluding zero, or
   any V1 arm's false-novelty rate exceeds 0.3, the verdict is
   `V1 HARMS PERFORMANCE OR RELIABILITY`.
4. **Benefit.** The verdict is `V1 CONCEPT KERNEL IMPROVES THE REPRESENTATION` only if
   **both** hold:
   - the adversarial suite gives recall ≥ 0.7 at precision ≥ 0.7 across the 11 matched
     pairs, with **every one of the nine §7 prohibited conflations failing to type-check**
     (`spec/v1/semantic_objects.yaml::kill_criteria` for L4); **and**
   - `V1_mint − V1_nomint` on answer accuracy has a paired CI excluding zero **and** the
     V1-H8 interaction shows the advantage is not confined to non-transfer items.
5. **Otherwise** the verdict is `V1 ADDS STRUCTURE WITHOUT MEASURABLE BENEFIT`.

A layer that fails its own kill criterion in `spec/v1/semantic_objects.yaml` is deleted
from V1 and the remaining layers are re-measured without it, per plan §6. Layers are
dropped independently and are not defended.

**Note on step 4 as of today:** the first clause is already not satisfied. `adv08`, the
p-value-to-posterior conflation, type-checks (§4.2). On the current implementation the
benefit verdict is unavailable regardless of what any model does.

## 9. Confounds that cannot be removed by prompt construction

Each is recorded with the direction in which it biases the comparison, per the pilot's
practice of recording rather than silently correcting.

1. **Prompt length rises monotonically with the treatment.** 1,446 → 3,862 → 6,554 →
   12,146 → 12,338 characters. This is the worst possible confound structure: the thing
   that varies with the treatment is also the thing that plausibly hurts. *Direction:
   against the V1 arms.*
2. **The registry names the correct answer on 4 of the 12 recognition items** (`cr04`,
   `cr05`, `cr10`, `cr12`). On a fifth non-transfer item, `cr02`, the correct answer is
   `NONE`, which the registry cannot supply. *Direction: in favour of the minting arms.*
   Mitigated, not removed, by the 7-item transfer set and by reporting the interaction
   rather than the pooled accuracy.
3. **V0 cannot express 38 of 60 problems.** The `V0` arm is asked for an encoding that
   cannot represent the question. *Direction: against the V0 control, and therefore in
   favour of every V1 arm.* This is the confound most likely to manufacture a false
   positive for V1, and §10 gives the only honest way to bound it.
4. **`V1_full` is asked to record steps, entailments, statuses and goals.** More output
   for the same answer. *Direction: raises `V1_full` cost.* Cost is reported, never netted
   off against accuracy.
5. **Out-of-distribution language.** Every Hamiltonian arm carries a specification for a
   language invented weeks ago; `SE` carries none. *Direction: against every Hamiltonian
   arm.* Unchanged from the pilot and unfixable by prompt construction.
6. **The model decomposes internally in every arm**, compressing the `SE`-to-`V0`
   contrast and inflating any `V0`-to-V1 difference. *Direction: in favour of the V1
   arms.*
7. **Item authorship.** Structural identity in the `recurring_structure` block is fixed by
   the generator's draw, so the ground truth is exact by construction — but the *fairness*
   of an item rests on the four variants of a motif being genuinely non-equivalent
   relations, which is an authoring judgement made once and not independently reviewed.
   *Direction: unknown.* A blinded review of the 12 motifs, on the model of the pilot's
   blinded audit, would bound it.

## 10. Known gaps in this design

Stated here rather than discovered later.

- **V1-H5 is not testable in this design.** There is no compiler-feedback arm. The
  pilot's one replicated positive signal was that compiler feedback improves encoding
  fidelity, and this ablation cannot confirm or refute it for V1. Testing it needs a sixth
  arm (`V1_full` + feedback) and roughly 20% more compute.
- **Per-block contrasts are underpowered at 50 pp** (§3.3).
- **Encoding fidelity is not comparable to the pilot's** (§3.4).
- **Confound 3 has no control.** The clean fix is a `V0-prose` arm — V0's prompt with the
  encoding requirement removed on problems V0 cannot express — which separates "V0 is a
  bad representation here" from "V0 cannot represent this at all". It is not in this
  design and should be added before any V1-beats-V0 claim is made.
- **The harness is not written.** `evaluation/harness.py` renders the seven V0 arms and
  does not know about `ARMS_V1`. `render_v1_arm` returns the existing `ArmPrompt` type so
  the integration is small, but it does not exist and nothing here has been executed
  end-to-end against a model.
- **One prohibited conflation is unimplemented** (`adv08`, §4.2).
- **`otherwise` is not decidable by `check_exhaustive` alone.** The complement branch is
  modelled at `DiscourseState`/`CaseSplit` level, and a caller reaching for
  `check_exhaustive` by itself will fail to recognise the one construct that makes a split
  exhaustive by construction. Pinned by
  `test_otherwise_is_not_decidable_as_a_bare_condition` so it cannot regress silently.

## 11. Reproduction

```bash
# design-time facts — no data required, no model involved
.venv/bin/python -m evaluation.v1.score_v1 --design

# the adversarial suite, including the live V0 baseline
.venv/bin/python -m pytest tests/v1/test_adversarial_v1.py -q -rxX

# once a run exists
.venv/bin/python -m evaluation.v1.score_v1 --run <run_id>
```

---

## Verdict

**`V1 ADDS STRUCTURE WITHOUT MEASURABLE BENEFIT` — PENDING.**

This is the placeholder, not a finding. It is written as the default because it is the
verdict the decision rule in §8 returns when no data exists, and because writing a
different placeholder would bias the reading of the first result that arrives. It becomes
a finding only when §7 carries measurements, and it may then be replaced by
`V1 CONCEPT KERNEL IMPROVES THE REPRESENTATION` or by
`V1 HARMS PERFORMANCE OR RELIABILITY` strictly according to §8.

**No model has been run. Nothing in §7 has a value. This verdict is PENDING.**
