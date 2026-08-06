# Tranche A (restarted run) — MEASUREMENT_INVALID

**Date.** 2026-08-06 · **Queue.** stopped (ran to completion, not killed) ·
**Records.** 32/32 preserved, none altered, none re-run.

## The defect

Three of thirty-two conditions hit the **completion allowance** (`finish_reason=length`,
6144 tokens), and the truncation is **outcome-determining** for two of the four surfaces.

| record | where | completion tokens | consequence |
|---|---|---|---|
| `v2_assumption_boundary_001__A_v0_labelled_linear.json` | attempt zero | 6144 | A's only non-exact condition, and its only constitutional failure |
| `v2_assumption_boundary_001__C_prefix_sexpr.json` | attempt zero | 6144 | one of C's three non-parses, and its only constitutional failure |
| `v2_dimensional_algebra_002__D_constrained_json_graph.json` | repair | 6144 | repair of an already-failed attempt |

## Why this is a harness defect and not a result

**The model was deliberating, not failing to express the object.** Both truncated attempts
show it writing candidate encodings and second-guessing them until the budget ran out. The
tail of the surface-A attempt reads:

```
Final Answer:
module AssumptionBoundary
const eta : Real = 5
var digamma : Real
assume digamma > 4
def rho(mu : PositiveReal) : Real := eta / mu -> NO!

I'll just write it now.

module AssumptionBoundary
const eta : Real = 5
var digamma :        <- cap
```

It had already written a correct encoding and talked itself out of it. The surface-C attempt
does the same thing over the name `varrho`. This is decoding instability interacting with a
cap; it is not a measurement of what the notation can express — the *same model* on the
*same task* produced a clean exact answer in surface B, with no deliberation loop at all.

**The cap is not forced by the runtime.** The slot is 16384 tokens and the prompt is ~3000,
so roughly 13000 tokens were available. `COMPLETION_ALLOWANCE = 6144` was chosen before this
corpus's generation behaviour was known.

**It decides the verdicts.** Surface A is 7/8 exact and fails the gate on the truncation
alone (`constitutional failures = 0` is required, and it has exactly one). Surface C's
truncated condition is one of its three non-parses, so without it C's repaired-parse count
would cross the 6/8 threshold. Reporting "A and C are non-viable" from this run would be a
confidently wrong result about the notations.

**This is the failure mode that already voided one calibration.** The v1 protocol
calibration was closed `PROTOCOL_UNSTABLE` because 56 of 76 generations hit
`finish_reason="length"` at exactly 2048 tokens. The mechanism here is identical, at a
larger cap.

## Integrity of the run, independently of the defect

Everything else audited clean and is preserved:

| check | result |
|---|---|
| task x surface matrix | complete, 8 x 4, 0 missing, 0 duplicate |
| one immutable record per condition | 32/32 |
| all 35 required fields present | 32/32 |
| recorded prompt hashes its own recorded prompt | 32/32 |
| recorded prompt hash == frozen builder's hash | 32/32, **no drift** |
| bundle hashes recomputable | 32/32 |
| transport failures | 0 |
| empty attempt zero | 0 |
| tracked repository files altered during the run | none |

## Preserved but VOID — not a result

Recorded so the evidence is not lost. **No surface may be interpreted from this table**, and
the continuation rule was not applied.

| surface | 1st parse | rep. parse | 1st exact | final exact | CF | tokens | med. latency | trunc |
|---|---|---|---|---|---|---|---|---|
| A_v0_labelled_linear | 7/8 | 7/8 | 7/8 | 7/8 | 1 | 8573 | 27s | 1 |
| B_v1_labelled_linear_simplified | 7/8 | 7/8 | 7/8 | 7/8 | 0 | 16548 | 104s | 0 |
| C_prefix_sexpr | 5/8 | 5/8 | 5/8 | 5/8 | 1 | 22070 | 89s | 1 |
| D_constrained_json_graph | 0/8 | 0/8 | 0/8 | 0/8 | 1 | 57800 | 404s | 1 |

## Not done, deliberately

The completion allowance was **not** raised and nothing was re-run. Per the directive: do not
patch and continue. Any repeat is a new run with its own preregistration, and every record
here stays as invalid-measurement evidence, excluded from every future aggregate.

---

## Run manifest

`RUN_MANIFEST.json` records, per condition: prompt SHA-256, bundle SHA-256, finish reason
(attempt zero and repair), prompt and completion token counts, truncation flag, transport
status, every parse/exact outcome, and the constitutional-failure list. Model
`gemma4:31b`, digest `6316f0629137b426c9d9b853…`.

Stated explicitly, for the record:

- **32/32 conditions completed.**
- **Task × surface matrix complete** — 8 tasks × 4 surfaces, no missing, no duplicate.
- **No transport failures** (0/32).
- **No prompt drift** — every recorded prompt hash equals the frozen builder's hash today.
- **No bundle drift** — every bundle hash recomputes.
- **No repository mutation during measurement** — `git status` showed only the run's own
  new records and generation-cache entries throughout.
- **Three truncations** — two attempt-zero, one repair.
- **No surface-selection or continuation decision is derived from this run.**

These records may be used for **debugging and operational planning only**. They must never
enter the valid Tranche A aggregate.

## Exploratory diagnostic table — NOT A RESULT

| surface | repaired parse | exact semantic | truncations | constitutional failures | completion tokens | median latency |
|---|---|---|---|---|---|---|
| A_v0_labelled_linear | 7/8 | 7/8 | 1 (attempt zero) | 1 | 8,573 | 27s |
| B_v1_labelled_linear_simplified | 7/8 | 7/8 | 0 | 0 | 16,548 | 104s |
| C_prefix_sexpr | 5/8 | 5/8 | 1 (attempt zero) | 1 | 22,070 | 89s |
| D_constrained_json_graph | 0/8 | 0/8 | 1 (repair only) | 1 | 57,800 | 404s |

## SURFACE_D_ELIMINATED_BY_UPPER_BOUND

Surface D is eliminated **without a rerun**, by a bound that no resolution of its truncated
record can escape:

1. D's current repaired-parse count is **0/8** — zero conditions parsed, before or after
   repair.
2. Exactly **one** D record was truncated, and only during its **repair**; its attempt zero
   finished with `stop` at 3,866 tokens and failed on content, not on budget.
3. Grant that record the most favourable possible resolution — a successful repaired parse.
   The maximum attainable count is then **1/8**.
4. The frozen continuation threshold is **6/8**.

1 < 6. **D cannot meet the continuation gate under any resolution of the truncated record.**

This is not a post-hoc aesthetic judgement; it is arithmetic under a threshold frozen before
the run. The dominant failure class is recorded for completeness: D's attempts emit a
*triples* schema (`["alpha","is","Declaration"], ["alpha","declKind","const"], …`) where the
candidate specifies a `statements` array of node objects. Every D attempt failed at import,
none at the compiler, so the failure is schema conformance rather than mathematics.
