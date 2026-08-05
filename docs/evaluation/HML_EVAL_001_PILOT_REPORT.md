# HML-EVAL-001 — Pilot Report

**Specification:** `EVAL_SPEC_v1.1` (supersedes `EVAL_SPEC_v1.0`; both preserved)
**Language commit:** `286a711a35dd`, tag `hml-v0-eval-freeze-3-g286a711`
**Corpus hash:** `10ef721423559dc7` (120 problems, 15 sampled)
**Model:** `gemma4:31b`, digest `6316f0629137`, Q4_K_M, 31.3 B, local Ollama
**Sampling:** temperature 0.7, top-p 1.0, max_tokens 2400, identical in every arm
**Analysed:** generation 0, **105 of 105 cells complete, 0 unrun**

---

## 1. What was run

15 stratified problems (3 per category: probability, binding, quantifier, dimensional,
algebraic) × 7 arms × 1 generation = **105 paired cells, all present**.

| arm | representation |
|-----|----------------|
| A | ordinary English |
| A′ | structured English — the mandated 8-point reasoning schema |
| B | LaTeX |
| C | Stan / Lean |
| D | Hamiltonian, no compiler feedback |
| E | Hamiltonian + compiler feedback |
| F | Hamiltonian graph view |

A second generation (105 further cells, independent because sampling is at temperature
0.7, not 0) also completed and is reported in §7 as a stability check only. It is not
part of the primary analysis.

## 2. Evaluator validation, performed before results were viewed

- **22 synthetic-mutation tests.** Every one of the nine scored facets is shown to both
  pass and fail. A meta-test fails the suite if a facet is added without a mutation test.
- **Binder-renaming invariance, role-swap detection, quantifier-order detection,
  dimension comparison and omitted-structure detection** are each individually pinned.
- **Blinded audit of 20 randomly sampled outputs**, arm labels hidden, seed recorded:
  **20/20 answer agreement, 6/6 semantic agreement, all seven arms represented, no
  disagreements.**

### A defect found *after* results were viewed, handled under protocol

Every arm failed `d24_unknown_constant`, and every arm had in fact answered it correctly.
Cause: answer correctness was computed once at trial time, and the re-scoring path
re-derived only the *encoding* score. The trial-time dimension parser could not read a
parenthesised denominator. That parser was fixed before the freeze; the stored answer
verdicts never received the fix.

Per the directive, the v1.0 result was **preserved verbatim**, the defect recorded as
`EVAL-DEFECT-001`, and the raw outputs transparently rescored under v1.1.

**Effect: 7 of 105 cells changed, all on that one problem, exactly one per arm, all
False → True.** Every paired difference is unchanged. Absolute accuracy in every arm rose
by the same 1/15. The v1.0 headline is preserved at
`evaluation/results/eval001-gen0.analysis.EVAL_SPEC_v1.0.PRESERVED.json`.

## 3. Primary outcome 1 — final-answer correctness

Denominator is 15 in every cell. Intervals are percentile bootstrap.

| arm | correct | accuracy | 95% CI |
|-----|---------|----------|--------|
| A | 14/15 | 93.3% | [80.0, 100.0] |
| A′ | 14/15 | 93.3% | [80.0, 100.0] |
| B | 14/15 | 93.3% | [80.0, 100.0] |
| C | 13/15 | 86.7% | [66.7, 100.0] |
| D | 14/15 | 93.3% | [80.0, 100.0] |
| E | 14/15 | 93.3% | [80.0, 100.0] |
| F | 14/15 | 93.3% | [80.0, 100.0] |

### Paired contrasts, 15 pairs each

| contrast | difference | 95% CI | discordant pairs | McNemar exact p | Cohen's h |
|----------|-----------|--------|------------------|-----------------|-----------|
| A′ − A | +0.000 | [0.000, 0.000] | 0 / 0 | 1.000 | 0.00 |
| D − A | +0.000 | [0.000, 0.000] | 0 / 0 | 1.000 | 0.00 |
| **D − A′** | **+0.000** | **[0.000, 0.000]** | **0 / 0** | **1.000** | **0.00** |
| D − B | +0.000 | [0.000, 0.000] | 0 / 0 | 1.000 | 0.00 |
| D − C | +0.067 | [0.000, 0.200] | 1 / 0 | 1.000 | 0.23 |
| E − D | +0.000 | [0.000, 0.000] | 0 / 0 | 1.000 | 0.00 |
| F − D | +0.000 | [0.000, 0.000] | 0 / 0 | 1.000 | 0.00 |

Six of the seven contrasts have **zero discordant pairs**: the arms did not merely score
the same, they succeeded and failed on exactly the same problems. The single discordant
pair is arm C failing one algebraic problem the others answered.

### By domain (accuracy per arm, n = 3 per cell)

| domain | A | A′ | B | C | D | E | F |
|--------|---|----|---|---|---|---|---|
| algebraic | 1.00 | 1.00 | 1.00 | 0.67 | 1.00 | 1.00 | 1.00 |
| binding | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| dimensional | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| probability | 0.67 | 0.67 | 0.67 | 0.67 | 0.67 | 0.67 | 0.67 |
| quantifier | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

The one universally-failed problem is `p19_beta_binomial_posterior`, where **6 of 7 arms
produced zero characters of output**: the model's reasoning channel consumed the entire
2400-token budget before emitting any content. This is a generation-budget failure, not a
representation effect, and it is the sole source of the 1/15 shortfall in every arm.

## 4. Primary outcome 2 — semantic preservation

Only arms D and E produce a Hamiltonian encoding that can be compared against ground
truth. Arm C emits Stan/Lean, which this compiler does not parse; arm F emits triples,
which the graph importer covers only for a declaration-and-law subset. Those are recorded
as **not measured**, not as zero.

| arm | encoding score (all) | encoding score (parsing encodings only) | parse success |
|-----|---------------------|------------------------------------------|---------------|
| D | 0.648 | 0.738 (n = 11) | **11/15 = 73.3%** |
| E | 0.701 | 0.734 (n = 12) | **12/15 = 80.0%**¹ |

¹ `parse_success_rate` over cells reporting one: 0.857.

**Hamiltonian encodings do not preserve the original mathematical meaning.** Even
restricted to encodings that compile, roughly a quarter of the ground-truth structure is
lost. Between a quarter and a fifth of encodings do not compile at all.

Two comparator limitations, both biasing *against* the Hamiltonian arms, are documented
and were not silently corrected:

1. An encoding that folds a constraint into a refinement type (`param x : NonNegativeReal`)
   is scored as a type and declaration-kind mismatch against a ground truth using
   `var x : Real` + `require x >= 0`, though the two are arguably equivalent.
2. An encoding that fails to parse zeroes every structural facet, so the all-encodings
   column conflates syntax failure with mistranslation. That is why the parsing-only
   column is reported beside it.

`prohibited_assumptions` is carried in the ground truth and **is not scored**. Detecting
an unstated assumption in free prose is not deterministically decidable and no facet
claims to do it. Missing-assumption detection is therefore **not measured** in this pilot.

## 5. Secondary outcomes

| arm | prompt tok | completion tok | latency s | empty output | marker compliance | repairs | binding err | type err | scope err |
|-----|-----------|----------------|-----------|--------------|-------------------|---------|-------------|----------|-----------|
| A | 262 | 1145 | 87.5 | 1/15 | 0.93 | – | – | – | – |
| A′ | 565 | 1699 | 136.7 | 1/15 | 0.93 | – | – | – | – |
| B | 314 | 1117 | 85.0 | 1/15 | 0.93 | – | – | – | – |
| C | 349 | 1309 | 98.1 | 1/15 | 0.87 | – | – | – | – |
| D | 1205 | 973 | 78.1 | 0/15 | 1.00 | 0 | 0.00 | 0.07 | 0.13 |
| E | 1666 | 1341 | 100.0 | 1/15 | 0.93 | 4 (2 trials) | 0.00 | 0.07 | 0.13 |
| F | 1437 | 1135 | 86.4 | 1/15 | 0.93 | – | – | – | – |

Two observations that cut against expectation:

- **Arm D is the cheapest arm to run and the fastest**, at 973 completion tokens and
  78.1 s, below plain English (1145, 87.5 s). The representation is expensive in *prompt*
  tokens — 4.6× arm A — and cheaper in generated tokens.
- **Arm A′ is the most expensive arm by a wide margin** (1699 completion tokens, 136.7 s)
  and bought exactly zero accuracy over arm A.

### Verifier acceptance

No proof obligation was discharged in any arm. v0 discharges only dimensional checks; no
theorem prover was invoked. Verifier acceptance is **not measured**.

## 6. Compiler feedback (E vs D)

This is the only contrast in the pilot with a difference whose interval excludes zero.

| measure | D | E | paired difference | 95% CI |
|---------|---|---|-------------------|--------|
| answer accuracy | 93.3% | 93.3% | +0.000 | [0.000, 0.000] |
| encoding score | 0.636 | 0.701 | **+0.065** | **[0.006, 0.136]**, n = 14 |
| parse success | 73.3% | 85.7% | +12.4 pp | not tested |
| completion tokens | 973 | 1341 | +38% | – |
| latency | 78.1 s | 100.0 s | +28% | – |

**Compiler feedback measurably improves the encoding and does not improve the answer.**
It bought +0.065 encoding fidelity and a higher parse rate for 38% more generated tokens
and 28% more latency. Four repair calls fired across two trials.

## 7. Stability check — generation 1 (not part of the primary analysis)

An independent second generation completed. It is reported because a result that moves
under resampling is not a result.

| arm | gen 0 | gen 1 |
|-----|-------|-------|
| A | 93.3% | 93.3% |
| A′ | 93.3% | **66.7%** |
| B | 93.3% | 93.3% |
| C | 86.7% | 80.0% |
| D | 93.3% | 93.3% |
| E | 93.3% | 93.3% |
| F | 93.3% | 86.7% |
| D parse rate | 73.3% | **50.0%** |
| E parse rate | 85.7% | **93.3%** |

Two findings survive resampling and one does not:

- **Hamiltonian's parse rate is unstable and low**: 73.3% then 50.0%. Between a quarter
  and a half of encodings do not compile.
- **Compiler feedback consistently raises it**: 85.7% then 93.3%, in both generations.
- **Structured English is the least stable arm**, falling to 66.7%. Whatever A′ does, it
  does not make the model more reliable.

## 8. Required interpretation

**1. Did Hamiltonian preserve the original mathematical meaning?**
No. Encoding fidelity was 0.648 (0.738 among encodings that compile), and 27–50% of
encodings did not compile at all. Meaning was routinely lost.

**2. Did it improve final-answer accuracy?**
No. The paired difference against ordinary English, structured English and LaTeX was
**exactly zero, with zero discordant pairs** — the arms succeeded and failed on the same
problems. Against Stan/Lean it was +0.067 on a single discordant pair, McNemar p = 1.0.

**3. Did it outperform structured English, or merely provide scaffolding?**
Neither. D − A′ = 0.000 with zero discordant pairs. Structured English also failed to beat
plain English (A′ − A = 0.000), while costing 48% more generated tokens and 56% more
latency, and proving the least stable arm on replication. On this evidence the scaffolding
hypothesis and the representation hypothesis are *both* unsupported.

**4. Did compiler feedback provide the gain?**
There was no answer-accuracy gain for it to provide. Feedback did produce the pilot's one
interval excluding zero: +0.065 encoding fidelity, and a parse-rate improvement that
replicated across both generations. That is a gain in the *encoding*, not in the
*mathematics*.

**5. Did graph representation add value?**
No. F − D = 0.000 in generation 0, and F was slightly worse in generation 1 (86.7% vs
93.3%). The graph view also carries the largest prompt of any arm.

**6. Were gains large enough to justify a language-learning or fine-tuning experiment?**
No. There is no answer-accuracy gain to amplify. Fine-tuning on the basis of a zero effect
would be training toward an outcome the pilot did not observe.

**7. Which results are evidence, which are compiler properties, and which are
speculation?**

| status | items |
|--------|-------|
| **Evidence** (model-in-the-loop, 105 completed cells) | All arm accuracies and paired contrasts; encoding fidelity for D and E; parse rates; token, latency and repair costs; the E-vs-D encoding difference; the generation-1 stability check |
| **Compiler property, not evidence** | That the language rejects positional distribution arguments, role confusions, quantifier-order collapse and dimensional errors. These are properties of the checker and were true before any model ran |
| **Speculation** | That any of this would change with a larger corpus, a harder corpus, a stronger model, a fine-tuned model, or a corpus not saturated at 93% |

## 9. The limitation that dominates everything above

**The task set is saturated.** Fourteen of fifteen problems were answered correctly by
essentially every arm. With 15 paired observations and a ceiling at 93%, the design can
only detect an effect if it moves several problems — McNemar at n = 15 needs roughly five
concordant-direction discordant pairs to reach p < 0.05, an effect of about 33 percentage
points. **The pilot had almost no power to detect any realistic difference.**

This means the zero differences reported above are **not evidence that no difference
exists**. They are evidence that no difference large enough to move a saturated 15-problem
set was observed.

Further limitations, each recorded rather than corrected:

- 6 of 105 cells produced empty output through reasoning-budget exhaustion, concentrated
  on one problem.
- The model is a reasoning model. It decomposes internally in every arm, which compresses
  the A-to-A′ contrast and therefore inflates any A′-to-Hamiltonian difference **in the
  thesis's favour**. No such difference appeared regardless.
- Arms D/E/F carry a ~4× longer prompt containing a specification for a language invented
  weeks ago; arm C names languages saturated in pretraining. This out-of-distribution
  confound cannot be removed by prompt construction.
- One generation, one model, one quantisation, one machine.

## 10. Decision

The evidence does not support continuing to language adaptation: there is no
answer-accuracy effect to amplify, and encoding fidelity is well below faithful. But the
evidence equally does not support concluding that no representation advantage exists — a
saturated 15-problem set with a 93% ceiling cannot detect one.

Two things must change before the question is answerable: the corpus must discriminate
(harder problems, lower baseline accuracy, more of them), and Hamiltonian's own syntax
failure rate of 27–50% must be reduced, since an encoding that does not compile cannot
demonstrate anything about reasoning. Syntax failure is currently the dominant
Hamiltonian-specific failure mode, which is an explicit redesign trigger in the governing
directive.

### REDESIGN AND RETEST

---

## Reproduction

```bash
.venv/bin/python -m evaluation.analyse --run eval001-pilot --generation 0
```

```bash
.venv/bin/python -m evaluation.blind_audit unblind
```

```bash
.venv/bin/python -m pytest tests/evaluation -q
```

Artefacts: `evaluation/results/EVAL_SPEC_v1.1.json`,
`evaluation/results/eval001-gen0.EVAL_SPEC_v1.1.analysis.json`,
`evaluation/results/EVAL_SPEC_v1.0.PRESERVED.json`,
`evaluation/results/eval001-gen0.analysis.EVAL_SPEC_v1.0.PRESERVED.json`,
`evaluation/results/audit/audit_result.json`.

Raw per-trial records are not committed (machine-specific and large); their per-cell
SHA-256 hashes are in the manifest of each `EVAL_SPEC` file.
