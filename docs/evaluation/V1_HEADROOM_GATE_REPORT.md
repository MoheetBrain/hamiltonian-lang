# V1 benchmark — headroom gate report

**Run:** `decisive_01` · **Protocol:** developmental v1.3 · **Model:** `gemma4:31b`,
digest `6316f0629137b426…` · **Runtime:** `1 x 32768`, temperature 0.0
**Verdict: `HML_BENCHMARK_FAILED_NO_SIGNAL`**

---

## 1. Result

| | |
|---|---:|
| valid paired tasks | 23 (of 24; `v1b_11` excluded pre-run) |
| **SE final correct** | **23 / 23 (100%)** |
| SE first-call correct | **23 / 23** |
| second call changed the answer | 2 |
| ideal headroom band | 8–15 |
| usable headroom band | 6–17 |
| **band** | **INSUFFICIENT** |
| HML-V1 calls made | **0** |
| wall clock | 2.27 h · 46 calls · 132,571 completion tokens |

Integrity: 23/23 records complete, **0 truncations, 0 transport errors**, all 46 calls
scored `ok`, every reply carrying exactly one answer marker, one model digest throughout.

**No HML-V1 call was made.** The gate is evaluated on the complete SE matrix before any
treatment call, so an insufficient-headroom finding costs no treatment compute and cannot be
reached after treatment results are visible.

## 2. What this does and does not say

**It says nothing about HML.** No HML scientific call exists. This is a measurement of the
*corpus*, and it says the corpus cannot discriminate between representations for this model
at this budget.

**It says the 24-task benchmark is retired for H2**, on the same grounds as eval001 before
it. That is now two purpose-built corpora in a row lost to saturation:

| corpus | design intent | measured | outcome |
|---|---|---|---|
| eval001 (95 tasks × 3 seeds) | discriminating | mean accuracy **0.961** | `HEADROOM_INSUFFICIENT` |
| v1 benchmark (23 tasks) | predicted accuracy **0.556** | **1.000** | `HEADROOM_INSUFFICIENT` |

## 3. Why the difficulty predictions failed

Every difficulty figure in `evaluation/v1_benchmark/difficulty.py` carries status
`PREDICTED_NOT_MEASURED`, and the predictions were not merely optimistic — they carried no
signal at all. The three tasks tied as hardest (`v1b_06` Simpson reversal, `v1b_07` law of
total variance, `v1b_22` correlated testimony, each predicted 0.45) were **all correct**, as
was the Frullani sign trap (`v1b_18`) and every other convention trap the corpus was built
around.

The corpus was constructed to defeat a model by baiting known error modes. It was calibrated
against an intuition about which traps are hard, and that intuition did not survive contact
with the model.

## 4. The finding that matters most: headroom is a function of the budget

This is the transferable lesson, and it was measured rather than argued.

On the *same tasks*, with the *same model*, at temperature 0:

| per-call completion allowance | outcome |
|---|---|
| 1024 (v1 frozen) | inherited from ACQ0; never validated against this corpus |
| **4096 (v1.2)** | **probe truncated; `v1b_06` returned ZERO characters of content** |
| **8192 (v1.3)** | **23/23 correct** |

`gemma4:31b` bills its reasoning trace to `completion_tokens` while returning it in a
separate field. The trace alone costs ~3,000–4,000 tokens. Below roughly 5,000 the answer
field is empty or truncated — scored as a failure of the representation. Above it, the model
solves everything.

**So this corpus has no usable headroom at any allowance we can currently identify.** Below
the threshold it floors for a measurement artefact; above it, it ceilings. The band between
is narrow and is a property of the token budget rather than of the mathematics.

**Consequence for corpus design: a corpus must be calibrated at the budget it will be run
at.** Headroom measured at one allowance does not transfer to another, and a difficulty
estimate that ignores the completion budget is not an estimate of difficulty.

## 5. An uncomfortable corollary about this protocol

The v1.2 → v1.3 budget raise was necessary — at 4096 the model produced no answer at all,
which is measurement-invalid by construction. That same raise is what moved the corpus from
floor to ceiling.

Both facts are true and neither was chosen with a result in view: the amendment was written
and committed before any scientific call, and the probe that forced the second raise was
non-scientific by construction. But it should be recorded plainly that **the budget decision
and the saturation outcome are causally linked**, and a reader is entitled to weigh that.

## 6. Where the value of this run actually landed

The measurement returned no signal. The pre-run work returned a great deal, and it is worth
separating because none of it would have been visible from a result table:

- **Four scorer/prompt defects**, each demonstrated and independently reproduced:
  the *first* `<ANSWER>` span was scored rather than the last (penalising the second call
  exactly when it worked); the first number-like substring was mined out of the answer
  (`16/7 → 16.0`, `ln(5/2) → 5.0`) on 9 of 24 tasks, a **differential** error falling on
  whichever arm writes exact forms; a reply with no answer marker was scored against its
  whole text, producing spurious passes; and the two arms carried unequal prior working into
  their second call, handicapping the treatment.
- **One task excluded** (`v1b_11`) whose correct answer its own scorer could not accept.
- **Two defects in the harness**: unbounded compiler diagnostics (a 122× blowup that would
  have truncated the repair prompt hardest exactly where the model wrote the worst HML), and
  no crash safety at all.
- **All 24 answer keys independently re-derived**, 24/24 confirmed.

Had the corpus not saturated, the measurement would have run on a scorer that
mis-scored exact-form answers differentially by arm. That defect alone could have produced a
confident, wrong verdict.

## 7. Exact reproduction

```bash
caffeinate -dimsu .venv/bin/python -m evaluation.v1_benchmark.run_experiment \
    --run-id decisive_01 --workers 1
```

Artefacts: `evaluation/results/v1_benchmark/decisive_01/` — `MANIFEST.json` (immutable,
with the scientific-input drift hash), `records/*.json` (23 write-once records, both raw
calls preserved), `HEADROOM_GATE.json`, `DECISION.json`, `PROGRESS.json`, `HEARTBEAT.json`,
`generation_cache/`.

## 8. Next

The gate is a corpus verdict, not an HML verdict. A usable H2 measurement needs a corpus
built to a different rule:

1. **Calibrate at the run budget.** Measure SE accuracy at 8192 *first*, and admit only
   tasks the control gets wrong at that allowance.
2. **Select empirically, not by predicted trap.** Two corpora have now been designed around
   intuitions about difficulty and both saturated. Difficulty must be measured before a task
   is admitted.
3. **Target the 8–15 band directly.** Admit tasks until the control lands inside it, rather
   than designing for a predicted mean and hoping.
4. Consider whether a corpus this model cannot saturate exists at all within the mathematics
   the benchmark targets — and if not, whether a larger model or a harder domain is required
   before H2 can be tested.
