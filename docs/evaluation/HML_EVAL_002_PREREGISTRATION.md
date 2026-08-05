# HML-EVAL-002 — Preregistration

Written **before** any HML-EVAL-002 data is collected. Registered against branch
`hml-v1-concept-kernel`; V0 preserved at `hml-v0-baseline`.

## 0. Status of the thesis, stated precisely

The central thesis is:

> An AI model taught to represent and execute mathematical reasoning through Hamiltonian
> Lang becomes more accurate, systematic and verifiable than the same model operating
> through English, structured English, LaTeX or existing formal representations.

Its current status is **UNPROVEN, NOT REFUTED.**

The only defensible conclusion from HML-EVAL-001 is:

> **Zero-shot Hamiltonian did not improve answer accuracy on this small,
> low-discrimination pilot. The experiment was underpowered and had a severe ceiling
> effect.**

14 of 15 problems were solved by nearly every arm; the minimum detectable effect was
roughly 33 percentage points. A design with that little power cannot refute anything.

**A correction is recorded** in `V1_GATE_DECISION.md`: an earlier version of that document
called criterion 1 "refuted", contradicting this project's own pilot report §9. The report
was right. The pivot that error encouraged — treating the checker as the product — is
withdrawn. **The checker is a component of a verifier-guided reasoning system (H3), not the
objective.**

## 1. Three hypotheses, tested independently

The pilot conflated these. HML-EVAL-002 separates them, because they can come apart: a
representation might be a poor *input* format and a good *reasoning* format, or useless
without a verifier and valuable with one.

| id | hypothesis | isolated by |
|----|-----------|-------------|
| **H1** | **Input representation.** Receiving the problem in Hamiltonian improves the final answer. | conditions 1–4: representation varies, output format fixed |
| **H2** | **Reasoning representation.** Requiring explicit Hamiltonian transformation and inference steps improves the final answer. | conditions 5–6 vs 1 and 4: derivation required or not, input held fixed |
| **H3** | **Verifier-guided reasoning.** Compiler feedback plus repair improves the final *verified* answer. | condition 7 vs 6: same input and derivation requirement, feedback added |

### The eight conditions

| # | input | reasoning | output |
|---|-------|-----------|--------|
| 1 | English | free | answer |
| 2 | structured English | free | answer |
| 3 | LaTeX | free | answer |
| 4 | Hamiltonian | free | answer |
| 5 | English | Hamiltonian derivation required | answer |
| 6 | Hamiltonian | Hamiltonian derivation required | answer |
| 7 | Hamiltonian | Hamiltonian derivation + compiler feedback + repair | answer |
| 8 | direct Lean / Stan / SymPy where appropriate | native | answer |

Condition 5 is the one the pilot lacked and the one that most cleanly isolates H2: the
model reads ordinary English and must *reason* in Hamiltonian. If H2 holds and H1 does not,
condition 5 beats condition 1 while condition 4 does not.

Mathematical information is identical across conditions by construction (all rendered from
one canonical semantic object). Compute budgets are matched and recorded per call.

## 2. Phase gates — no phase may be skipped

### Syntax gate (Phase 2), blocking

No reasoning experiment may run until **at least one** Hamiltonian surface form achieves,
on held-out tasks:

- **≥ 95% parse success after at most one repair**
- **≥ 90% semantic preservation**
- **no catastrophic domain-specific failure** (no domain below 70% parse)
- **acceptable token cost** (≤ 2× the structured-English arm on completion tokens)

Four surface renderings of the *identical* semantic core are compared: V0 labelled-linear ·
simplified V1 labelled-linear · prefix/S-expression · constrained JSON-or-graph. Same model,
tasks, demonstrations, token budget. The winner is selected **empirically, on measured
parse and preservation rates** — not because it reads well.

Measured per form: first-attempt parse rate · semantic preservation · repair success ·
tokens · latency · modal failure type.

This gate exists because V0 achieved only 50–73% parse. A language the model cannot write
is not being tested, and every null result before this gate is passed is uninterpretable.

### Benchmark gate (Phase 3), blocking

≥ 200 held-out problems (target 300), with **baseline accuracy between 40% and 70%**.
Adaptive pre-screening removes: problems solved by nearly every arm; problems failed by
every arm for want of knowledge rather than reasoning; ambiguous or mis-scored problems.
Problems and answers are frozen and hashed before any comparative run.

Domains: long variable-binding chains · nested quantifiers and scope · Bayesian and
frequentist reasoning · transformation chains · dimensions and units · assumptions and
boundary conditions · equivalence vs implication · approximation vs exact equality ·
epistemic calibration · concept-family transfer · novel but formally defined concepts.

## 3. Models (Phase 5)

| role | model | status on this machine |
|------|-------|------------------------|
| reasoning model | `gemma4:31b` Q4_K_M | **available** |
| non-reasoning instruct, 7–14B | to be selected | **NOT INSTALLED — requires a model download** |

The 7–14B non-reasoning arm tests the most plausible version of the thesis: that
Hamiltonian supplies most value to a model that does *not* already decompose internally.
The 31B reasoning model compresses every scaffolding contrast, which biased the pilot's
A-to-A′ comparison towards the null.

Multiple stochastic generations with recorded seeds and sampling settings.

## 4. Matched adaptation (Phase 6)

Parallel corpora rendered from the same canonical objects in five representations. Identical
base checkpoint, split, content, example count, training tokens where practicable, optimiser
budget, LoRA rank, steps and inference budget.

> **A Hamiltonian-tuned model is never compared with an untuned baseline.** That would
> measure additional mathematical training, not representation.

**Infrastructure status: NOT PRESENT.** `torch`, `transformers`, `peft`, `datasets`, `trl`
and `accelerate` are all absent. On Apple silicon the realistic path is `mlx-lm` LoRA. This
phase is **blocked on an install decision** and is recorded as blocked rather than quietly
dropped.

## 5. Verifier-guided repair (Phase 7)

```
generate derivation -> parse and type-check -> classify diagnostic
                    -> repair ONE step -> verify -> continue or terminate
```

Recorded: first-attempt correctness · corrected correctness · repairs used · errors caught ·
errors missed · final verified success · compute overhead.

The checker must produce **actionable** feedback capable of changing the reasoning
trajectory — not merely reject a final output. A diagnostic that says only "type error" and
does not change what the model does next fails this phase regardless of its accuracy.

## 6. Success criteria

Continue developing the reasoning language if **at least one replicates across models or
seeds**:

- ≥ **5 percentage-point** paired improvement in final-answer accuracy
- ≥ **10 percentage-point** improvement in verified-solution rate
- ≥ **30% reduction** in binding, scope, type or invalid-inference errors
- a statistically *and practically* meaningful improvement in transfer to unseen concept
  families

Reported with confidence intervals, paired differences, domain-level effects and compute
costs. "Replicates" means the same direction and a comparable magnitude in an independent
seed or a second model — not merely a second look at the same data.

## 7. Failure condition — when a negative conclusion becomes legitimate

A conclusion that the representation does not improve reasoning may be drawn **only when
every one of these holds**:

1. Hamiltonian parse success ≥ 95%
2. semantic preservation ≥ 90%
3. benchmark baseline accuracy in 40–70%
4. ≥ 200 paired problems evaluated
5. matched information and compute
6. **both** few-shot and matched adaptation tested
7. verifier-guided repair tested
8. no practically meaningful advantage appears

**Until all eight are satisfied, the correct status is: the original reasoning thesis
remains unproven, not refuted.** Any report violating this is wrong and must be corrected,
as `V1_GATE_DECISION.md` was.

## 8. Guard against the opposite error

Moving goalposts is as much a failure as declaring premature defeat. Therefore, fixed now:

- the success thresholds in §6 are **fixed** and may not be lowered after seeing results;
- the benchmark is **frozen and hashed** before any comparative run;
- the winning syntax is chosen on **measured parse and preservation**, before the reasoning
  experiment;
- any scorer change after comparative results are seen requires a **new evaluator version
  with the prior analysis preserved**, exactly as `EVAL_SPEC_v1.1` preserved v1.0;
- H1, H2 and H3 are reported **separately**. A win on H3 alone is a win for
  verifier-guided reasoning, and must not be reported as a win for the representation.

## 9. Deliverables

`HML_SYNTAX_ACQUISITION_REPORT.md` · this preregistration · the frozen hard benchmark ·
matched adaptation datasets · the verifier-guided repair loop · `HML_EVAL_002_REPORT.md`.

Committed locally. Never pushed.
