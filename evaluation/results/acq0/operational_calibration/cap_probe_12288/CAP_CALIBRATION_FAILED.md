# Cap probe at 12,288 — CAP_CALIBRATION_FAILED

**Date.** 2026-08-06 · Operational calibration only. Nothing here was semantically scored,
and none of it is acquisition evidence.

## Result

Both probes reached the cap exactly and reported truncation.

| condition | prompt tok | completion tok | finish | truncated | budget inequality | latency |
|---|---|---|---|---|---|---|
| `v2_assumption_boundary_001 × A_v0_labelled_linear` | 2,945 | **12,288** | `length` | yes | 2945 + 12288 + 256 = 15,489 ≤ 16,384 ✓ | 620s |
| `v2_assumption_boundary_001 × C_prefix_sexpr` | 3,097 | **12,288** | `length` | yes | 3097 + 12288 + 256 = 15,641 ≤ 16,384 ✓ | 659s |

Identical prompt bytes, bundle hashes, model digest, temperature 0, seed 0, runtime and
`num_ctx` handling as the frozen configuration. Only the completion allowance changed.
The budget inequality held in both cases, so this was never a context-window problem.

## What the transcripts actually show

**The model does not deliberate — it loops.**

| surface | transcript | module header restated |
|---|---|---|
| A_v0_labelled_linear | 34,858 chars | **229 times** |
| C_prefix_sexpr | 32,352 chars | **161 times** |

It cycles on one identifier, writing the module, mistyping the name, rejecting it, and
starting over. The surface-A tail:

```
# NO! "varrho".

module AssumptionBoundary
const eta : Real = 5
var digamma : Real
assume digamma > 4
def rho(mu : PositiveReal) : Real := eta / mu
# I'll just write it.

module AssumptionBoundary
...
def rho(mu : PositiveReal) : Real := eta /        <- cap
```

Surface C does the same over `varrho` / `vvarrho`.

## Why a larger cap will not fix this

1. **It saturated at 6,144 and again at exactly 12,288.** Two allowances, a factor of two
   apart, both fully consumed. That is the signature of non-termination, not of an
   undersized budget.
2. **The repetition count scales with the budget.** Roughly twice the allowance produced
   roughly twice the restatements. A 28,672-token allowance predicts ~500 restatements and
   another `length` finish.
3. **It is one task, not one surface.** The other seven tasks in surface A completed
   normally with `stop`, and this same task completed cleanly in surface B. The trigger is
   the identifier `varrho` in `v2_assumption_boundary_001`, which the model repeatedly
   mistypes as `vvarrho` and then restarts over.

## Proposal, as required: one common 1 × 32,768 configuration

Recorded because the directive asks for it. **It is not recommended on this evidence.**

```
OLLAMA total context   32,768
parallel slots         1            (was 2)
slot context           32,768
safety reserve            256
completion allowance   28,672       (= 7 x 4096)
```

Inequality, worst prompt per surface:

```
A:  2,945 + 28,672 + 256 = 31,873  <= 32,768   ok
C:  3,097 + 28,672 + 256 = 32,025  <= 32,768   ok
B:  3,179 + 28,672 + 256 = 32,107  <= 32,768   ok
```

Costs: concurrency halves (one slot, so no batching gain), and at the observed
~20 tokens/s a single capped condition takes ~24 minutes. A 24-condition rerun would run
**up to ~10 hours** and, on the evidence above, would still truncate this task in A and C.

## What would actually address it — all require approval

None of these was applied. Each touches something frozen, and the directive forbids
patching and continuing.

1. **A decode-side stop condition** — a repetition penalty or a stop sequence. Least
   invasive: it changes a runtime sampling option, not the corpus, prompts or scorer. It
   would end the loop at its first restatement instead of the 229th.
2. **Rename the identifier** in `v2_assumption_boundary_001`. The mathematics is unchanged
   but the task identity is not, so this needs a fresh id and re-admission.
3. **Extract the last complete candidate encoding** from a truncated transcript. This is a
   scorer change, and it is the most dangerous of the three: the transcripts contain
   *correct* encodings, so it would convert a null measurement into a positive one on a
   rule invented after seeing the data.

Option 1 is the only one that does not change what is being measured.

## Status

The scientific survivor rerun was **not launched**. Its runner exists, refuses to start if
its directory already holds records, and aborts the whole rerun on the first truncation
rather than patching. Both probe records are preserved here with their hashes.
