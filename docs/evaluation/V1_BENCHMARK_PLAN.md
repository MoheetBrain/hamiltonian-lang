# HML-V1 matched benchmark — plan

**Status: machinery complete, NOT RUN. No model call has been made.** Every accuracy figure
in this document is `PREDICTED_NOT_MEASURED`. The live run awaits (a) a syntax winner from
the ACQ0 gate and (b) the Lead's authorisation once Ollama contention is cleared.

## 1. The question

Does Hamiltonian Lang **help**, as distinct from whether the model can write it?

ACQ0 asks the second question. This asks the first, and the two must not be run together
or reported together. This benchmark bears on **H2** and **H3** only. It bears on neither
ACQ0 nor H1.

| hypothesis | claim | what a win here means |
|---|---|---|
| H2 | reasoning *in* the representation improves the answer | evidence for the representation |
| H3 | verifier-guided repair improves the answer | evidence for the **loop**, not the notation |

Every result row carries exactly one `hamiltonian_lang.improvement.state.Hypothesis`, and
the attribution rule below decides which.

## 2. The design

```
Arm SE       problem -> structured-English reasoning -> self-review      -> final answer
Arm HML-V1   problem -> unrestricted reasoning -> HML formalisation
                     -> compile and verify -> one repair (with diagnostics) -> final answer
```

**Why SE gets a second call.** The Lead's sketch gives HML-V1 a repair and gives SE nothing
corresponding. Run that way, an HML win has a mundane alternative explanation — *it had two
attempts and the control had one* — that no later statistics can remove. SE therefore gets
an unaided self-review at the same token allowance, carrying no signal from outside the
model.

The arms then differ in exactly one respect, and that difference is the treatment: HML-V1's
second call carries compiler diagnostics. SE's does not.

## 3. Matching

| dimension | matched | detail |
|---|---|---|
| task | yes | one Canonical Semantic Object; prose and question byte-identical in both arms |
| model | yes | `gemma4:31b`, digest `6316f0629137…` |
| temperature | yes | 0.0, every call |
| runtime | yes | `4 x 8192`, one server configuration for the whole run |
| **total generation budget** | yes | **2048 completion tokens per task per arm, across all calls** (2 × 1024). Inherited from `ACQ0_CONTEXT_BUDGET.md`, which fixes the same figure for one-stage and two-stage protocols alike |
| number of attempts | yes | 2 generations per task in both arms |
| answer contract | yes | identical `render_instruction()` and `<ANSWER>` markers |
| worked demonstrations | yes | zero in both arms; zero-shot on both sides |
| **external information** | **NO** | **this is the treatment.** HML-V1's repair call carries compiler diagnostics; SE's carries only its own prior working. A win attributable to it is H3 |
| **prompt length** | **NO** | HML carries a ~3,000-character language spec; SE carries a ~600-character schema. Padding SE would add content nobody would otherwise send. `prompt_tokens` is recorded per call so the gap is visible in the data |
| **familiarity of the notation** | **NO, and not matchable** | structured English is in pretraining; HML was invented weeks ago. This biases **against** HML, so it cannot manufacture a positive result — but it means a null result cannot separate "the representation does not help" from "the model cannot yet write it". That is ACQ0's question |

## 4. The corpus — 24 hard tasks

Authored to a target base-accuracy band of **0.40–0.70**.

**The constraint exists because of a specific failure.** HML-EVAL-001 scored 93% in all
seven arms, had a minimum detectable effect near 33 points, and produced **zero** discordant
pairs in six of seven contrasts. A paired design reads nothing but discordant pairs, so a
corpus everything gets right measures nothing at any sample size.

Each task therefore carries an **engineered attractor**: a named wrong answer reachable by a
standard, plausible, invalid shortcut, recorded in the task's `distractors`.

| id | domain | steps | attractor | predicted | band | answer kind |
|---|---|---|---|---|---|---|
| `v1b_01_radical_extraneous` | algebra | 4 | HIGH | 0.59 | 0.47–0.71 | numeric |
| `v1b_02_vieta_reciprocal_squares` | algebra | 5 | MEDIUM | 0.60 | 0.48–0.72 | numeric |
| `v1b_03_mobius_iteration_period` | algebra | 4 | HIGH | 0.59 | 0.47–0.71 | numeric |
| `v1b_04_conditional_min_given_max` | probability/statistics | 5 | HIGH | 0.52 | 0.40–0.64 | numeric |
| `v1b_05_sd_of_linear_combination` | probability/statistics | 4 | HIGH | 0.59 | 0.47–0.71 | numeric |
| `v1b_06_simpson_reversal` | probability/statistics | 6 | HIGH | 0.45 | 0.33–0.57 | numeric |
| `v1b_07_law_of_total_variance` | probability/statistics | 6 | HIGH | 0.45 | 0.33–0.57 | numeric |
| `v1b_08_quantifier_order_repair` | logic/quantifier scope | 5 | HIGH | 0.52 | 0.40–0.64 | numeric |
| `v1b_09_negation_prenex_prefix` | logic/quantifier scope | 4 | MEDIUM | 0.67 | 0.55–0.79 | exact_string |
| `v1b_10_vacuous_truth_count` | logic/quantifier scope | 4 | HIGH | 0.59 | 0.47–0.71 | numeric |
| `v1b_11_negation_scope_choice` | logic/quantifier scope | 4 | MEDIUM | 0.67 | 0.55–0.79 | choice |
| `v1b_12_kinematic_viscosity_dimension` | dimensions/physics | 4 | MEDIUM | 0.67 | 0.55–0.79 | dimension |
| `v1b_13_permittivity_from_dimensionless` | dimensions/physics | 7 | MEDIUM | 0.46 | 0.34–0.58 | dimension |
| `v1b_14_pendulum_consistency_count` | dimensions/physics | 5 | MEDIUM | 0.60 | 0.48–0.72 | numeric |
| `v1b_15_sylvester_rank_range` | linear algebra | 5 | HIGH | 0.52 | 0.40–0.64 | numeric |
| `v1b_16_defective_matrix_trace` | linear algebra | 5 | HIGH | 0.52 | 0.40–0.64 | numeric |
| `v1b_17_determinant_scalar_similarity` | linear algebra | 5 | HIGH | 0.52 | 0.40–0.64 | numeric |
| `v1b_18_frullani_integral` | calculus | 5 | MEDIUM | 0.60 | 0.48–0.72 | numeric |
| `v1b_19_implicit_second_derivative` | calculus | 7 | MEDIUM | 0.46 | 0.34–0.58 | numeric |
| `v1b_20_series_order_limit` | calculus | 5 | MEDIUM | 0.60 | 0.48–0.72 | numeric |
| `v1b_21_two_detector_posterior` | epistemic reasoning | 5 | HIGH | 0.52 | 0.40–0.64 | numeric |
| `v1b_22_correlated_testimony` | epistemic reasoning | 6 | HIGH | 0.45 | 0.33–0.57 | numeric |
| `v1b_23_knowledge_closure_choice` | epistemic reasoning | 4 | MEDIUM | 0.67 | 0.55–0.79 | choice |
| `v1b_24_licensed_conclusion_choice` | epistemic reasoning | 5 | HIGH | 0.52 | 0.40–0.64 | choice |

Mean predicted base accuracy **0.556**. Every task inside the 0.40–0.70 band; enforced by
`test_no_task_is_a_ceiling_task`.

### 4.1 How difficulty was estimated, and why it is not a measurement

`evaluation/v1_benchmark/difficulty.py`:

```
predicted = CEILING_ANCHOR - STEP_PENALTY * (dependent_steps - ANCHOR_STEPS) - attractor_penalty
            then floored at chance_floor + 0.05
```

* `CEILING_ANCHOR = 0.93` — the **one measured quantity** in the rubric: the accuracy
  HML-EVAL-001 actually recorded, across all seven arms, on items of roughly two dependent
  steps with no engineered attractor. Anchoring to a measured ceiling is what makes the
  subtractions mean "how much harder than a pilot item is this".
* `STEP_PENALTY = 0.07` per **dependent** step beyond the anchor — one whose input is a
  previous step's output, so errors propagate. Independent sub-calculations are not counted.
* attractor penalty — LOW 0.05, MEDIUM 0.12, HIGH 0.20, grading how natural the invalid
  shortcut is. This is the term a ceiling item lacks entirely.
* chance floor applied last: a five-way choice cannot score below 0.20 however hard it is.

Reported band is ± 0.12, wide on purpose.

**Why this is not a measurement.** No model call produced any number above. The rubric is a
design instrument for avoiding a second saturated corpus. It is stamped
`PREDICTED_NOT_MEASURED` in every serialisation, report line and test assertion. A measured
accuracy outside a predicted band **falsifies the rubric, not the corpus** — the tasks stay,
the rubric is corrected.

### 4.2 Answer keys

Every key was verified independently before authoring: exhaustive enumeration where the
space is finite, exact rational arithmetic (`fractions.Fraction`) where a closed form
exists, and numerical cross-check against a second method where neither applies — the
implicit second derivative was confirmed by a central finite difference on the implicitly
solved curve, agreeing to 8 decimal places.

Numeric tolerance is `5e-3` for non-terminating decimals and `1e-9` for exact integers.
`check_answer` treats tolerance as `max(absolute, relative)`, so `5e-3` accepts a
three-decimal rounding of `16/7` while still rejecting every named attractor.
`test_the_named_attractor_is_never_scored_as_correct` enforces the second half.

### 4.3 Contamination

Checked **by content hash, never by identifier**, reusing
`evaluation/corpus_governance/contamination.py` unmodified — imported, not forked. Three
redundant checks: exact digest, digest after case folding and punctuation stripping, and a
5-token shingle Jaccard for paraphrase.

Result: **24 tasks vs 517 foreign items across 18 corpora — 0 hard collisions, 0
near-duplicate flags.**

Registered corpora, each built from its own source of truth rather than a copied id list:

* every ACQ0 syntax-gate stage pool, discovered from the partition itself — demonstration,
  G2 screening, G3 curriculum, G4 confirmatory, G4 replication — plus Track B and the
  recorded Track A exclusions;
* the **five frozen demonstrations**, separately named so the report can assert that line on
  its own and a rename cannot slip past;
* the **ACQ0 calibration tasks** (`binding_chain_001`, `distribution_law_001`);
* every **M3-Lite partition** — development, adversarial, promotion, transfer;
* the HML-EVAL-001 corpus (120 objects) and its demonstrations;
* the V1 concept-ablation corpus and demonstrations — not on the Lead's list, checked anyway,
  being 60 authored problems in adjacent domains in the same tree.

**On ACQ0 Round 1.** No separate Round-1 corpus exists in the tree yet; Round 1 draws from
the held-out stage pools, all of which are registered. Checking every stage pool covers
Round 1 now and will keep covering it after Round 1 is named.

## 5. The oracle guard

`assert_no_oracle` runs on **every** prompt in **both** arms, hypothesis fixed to H2, no
exemption. ACQ0's scoped exemption is refused by two independent locks: the upstream guard
(which raises for any non-ACQ0 hypothesis) and `arms._refuse_exemption`, so neither is
load-bearing alone. Both are tested separately.

**Two documented exclusions from the scan**, both resting on the upstream module's own
argument that content carried by everything cannot discriminate:

1. **Task-independent constants** — the SE schema and the HML specification, byte-identical
   in all 24 prompts. They must be excluded because the language spec legitimately contains
   `forall x : Real . ...` as a quantifier example, and a task with a variable `x` of type
   `Real` produces the semantic-fact rendering `x : Real`. That is a false positive of a
   deliberately blunt heuristic. `test_excluded_segments_are_task_independent` asserts the
   premise that licenses the exclusion.
2. **Model-produced text** — carried-forward working, and compiler diagnostics that quote
   the model's own source. The guard asks "did *we* disclose the key?"; a model that states
   the right answer in its own working has been told nothing. Scanning it would fail the run
   precisely when the model succeeded.

Neither is a hole a prompt builder could exploit, because **no function in `arms.py` accepts
`answer.value` at all**. `test_prompt_construction_is_independent_of_the_answer_key` proves
it by rebuilding every prompt against a mutated key and comparing bytes. This also covers
the upstream guard's known gap — it skips gold answers under two characters, which four
tasks here have.

Additionally, the `<ANSWER>` block is stripped from carried-forward working. This removes an
**anchoring confound**: a model shown its own previous answer restates it, which would
suppress the revision rate in both arms and blunt exactly the repair effect under study.

## 6. Measurement

Per task per arm: final-answer correctness · verified completion · structural errors ·
semantic errors · prompt tokens · completion tokens · latency.

**Verified completion is reported separately from answer accuracy, with its own
denominator.** It is defined only in the HML arm — the SE arm emits no artefact a verifier
can check — so SE's field carries `NotMeasured` with that reason, never `False`. Reporting
SE as `False` would manufacture a 100-point uplift out of a definition rather than a
measurement, and **no uplift ratio against SE is computed or computable**.

Error taxonomy, following `evaluation/semantic_equiv.py`:

* **structural** — `HML-L*` (lex), `HML-P*` (parse), or no module emitted at all;
* **semantic** — `HML-N*`/`HML-S*` (resolution, scope), `HML-T*`/`HML-D*` (type, dimension).

A corpus of structural errors indicts the grammar; a corpus of semantic errors indicts the
model's grasp of the mathematics.

## 7. Hypothesis attribution

Fixed before any run, and **not outcome-dependent**:

> an HML-V1 trial is **H3** if and only if the repair call **changed the final answer**;
> otherwise it is **H2**. An SE trial is always H2 — the SE arm has no verifier.

The rule keys on whether the repair *moved* the answer, not on whether it ended up correct.
Two tables are therefore reported:

* the **overall** paired table (all 24 tasks);
* the **H2-restricted** table, over tasks the repair did not move — the contrast that speaks
  to the representation. Its `n` is smaller and its rates are **not** interchangeable with
  the overall rates.

`test_a_repair_driven_win_is_h3_not_h2` enforces the separation.

## 8. Sequential analysis

Discordant pairs only. `w` = solved by HML-V1 not SE; `l` = solved by SE not HML-V1.

```
theta | D ~ Beta(1 + w, 1 + l)        report P(theta > 0.5 | D)
```

Standard library only, and **exact**: for integer parameters the tail is a finite binomial
sum, computed in `fractions.Fraction`:

```
P(theta > 0.5) = sum_{j=0..w} C(w+l+1, j) / 2^(w+l+1)
```

Cross-checked against direct Beta integration to 6 decimal places.

**Decision rule after 24:**

| condition | verdict |
|---|---|
| `P >= 0.90` **and** absolute uplift `>= 10` points | STRONG DEVELOPMENTAL SIGNAL |
| `P <= 0.20` | NO CURRENT BENEFIT SIGNAL |
| otherwise | extend to 40 |

After 40 the same thresholds apply and the third branch closes as INCONCLUSIVE. There is no
third tranche: a rule that can extend indefinitely is a rule that stops when it likes the
answer.

**Both conditions are required, and the second does real work.** `P >= 0.90` is reachable on
three discordant wins and no losses. The uplift floor forces the effect to be visible in raw
task counts as well as in the posterior.

**Fragility.** Every decision reports `flips_to_change` — the smallest number of task
outcomes that would change the verdict, found by breadth-first search over perturbed tables
to depth 3, not estimated. A verdict one task would overturn says so, every time.

## 9. Standing — this is never proof

Every report carries, and `render_text` refuses to render a verdict without:

> **DEVELOPMENTAL RESULT, NOT PROOF.** This is a 24-task (or, after extension, 40-task)
> paired comparison on a single model at a single temperature, analysed on its discordant
> pairs alone. It is evidence about a direction of development. It is not a demonstration
> that the representation helps, it does not generalise beyond this model and this corpus,
> and no verdict it produces may be reported as a benchmark result or as superiority over
> any other language or notation.

The wording is a data member, not a comment, so a report cannot be produced without it.

## 10. Running it

Design facts — safe at any time, no model, no data:

```bash
.venv/bin/python -m evaluation.v1_benchmark --design
.venv/bin/python -m evaluation.v1_benchmark --design --json \
    --out evaluation/results/v1_benchmark/design_report.json
```

The live run, **once the Lead authorises it**:

```bash
.venv/bin/python -m evaluation.v1_benchmark --run \
    --authorised-by "<Lead>" \
    --scope "HML-V1 matched benchmark, 24 tasks, tranche 1" \
    --contention-cleared \
    --surface frozen_l1
```

`--contention-cleared` is the operator asserting that no other study holds the Ollama
server. The pipeline refuses without it: a concurrent call destroys another study's latency
measurements and cannot be undone. There is no implicit path to a model anywhere in the
package — `run_benchmark` raises without an injected client, and the tests drive the whole
pipeline through scripted fixtures.

## 11. Limitations

1. **Nothing has been measured.** Every accuracy figure is predicted. The difficulty band
   could be wrong in either direction, and if it is, the study either saturates again or
   bottoms out.
2. **The surface is not yet selected.** The syntax gate has not named a winner. `--surface`
   currently offers only `frozen_l1`, and running on it makes HML-L1 the surface under test
   by explicit choice, recorded in the manifest. It is not a default.
3. **Prompt length is unmatched** (§3). Recorded per call rather than argued about.
4. **Notation familiarity is unmatched and unmatchable** (§3). Biases against HML, so it
   cannot manufacture a positive result; but a null result is ambiguous between "does not
   help" and "cannot yet be written", and only ACQ0 can separate those.
5. **The positive verdict can fire on few discordant pairs.** The rule is the Lead's and is
   implemented as specified; `flips_to_change` and the discordant count are reported
   alongside every verdict so the thinness is never invisible.
6. **One model, one temperature, one seed.** No claim generalises past `gemma4:31b` at
   temperature 0.
7. **The H2/H3 attribution rule is a proxy.** "The repair changed the answer" is observable
   and pre-specifiable; "the repair *caused* the change" is not directly observable. A model
   that would have revised anyway is counted as H3, which is the conservative direction —
   it moves wins **out** of the representation's column, not into it.
8. **`reference_hml` is empty on every task**, correctly, since a reasoning benchmark has no
   authored encoding. This weakens the contamination exact-digest check by one field; the
   specification and question carry the discriminating content and the shingle pass runs
   regardless.
9. **Semantic-encoding accuracy is not measured.** With no reference encoding there is
   nothing to compare a formalisation against, so the study measures whether the module
   *compiles*, not whether it means the right thing. A well-typed module that models the
   wrong problem scores as a verified completion.

## 12. Files

| path | role |
|---|---|
| `evaluation/v1_benchmark/tasks.py` | the 24 tasks, as Canonical Semantic Objects |
| `evaluation/v1_benchmark/difficulty.py` | the predicted-difficulty rubric |
| `evaluation/v1_benchmark/arms.py` | prompts, budget, oracle guard, matching table |
| `evaluation/v1_benchmark/pipeline.py` | execution; refuses model access by default |
| `evaluation/v1_benchmark/scoring.py` | deterministic scoring, H2/H3 attribution |
| `evaluation/v1_benchmark/sequential.py` | exact Beta posterior, decision rule, fragility |
| `evaluation/v1_benchmark/contamination.py` | disjointness wiring |
| `evaluation/v1_benchmark/report.py` | design and run reports |
| `evaluation/v1_benchmark/__main__.py` | the command line |
| `tests/evaluation/test_v1_benchmark.py` | 56 tests |
| `evaluation/results/v1_benchmark/design_report.json` | the design artefact |
