# ACQ0 context budget

The authoritative budget for the ACQ0 format-restriction study. It supersedes, for ACQ0
purposes, the curriculum figures in `EXECUTION_ENVIRONMENT.md` — see
[The superseded figure](#the-superseded-figure).

**Status: machinery complete, probe not yet run.** No model call has been made. Every
token figure below that is labelled an *estimate* is an estimate, and no eligibility
decision has been taken. `evaluation/acq0/budget/` is built and unit-tested against
stubs; it awaits the Lead's authorisation of the probe after the M1.5 freeze.

## The rule

A prompt is eligible for a slot when, and only when:

```
prompt_eval_count + completion_allowance + safety_reserve <= per_slot_context
```

| term | value | why |
|---|---|---|
| `completion_allowance` | **2048** | everything the model emits, visible **and** hidden reasoning |
| `safety_reserve` | **256** (floor, and the value used) | the overflow failure mode is silent |
| `per_slot_context` | **8192** at `-np 4` | `-c 32768` divided by the slot count |
| **ceiling at `4 x 8192`** | **5888** | `8192 - 2048 - 256` |

The same maximum total completion allowance applies to `DIRECT_FORMAL` and
`DRAFT_THEN_FORMAL`, so neither protocol wins by having been permitted to emit more.
For the two-stage arm the 2048 is the budget for draft plus formalisation combined.

Both terms are floored. `safety_reserve` may not go below 256, and `completion_allowance`
may not go below 256 either — shrinking or negating the allowance raises the ceiling and
buys a `FITS` verdict for a prompt that provably overflows, which is the same silent
eviction reached from the opposite side. An out-of-range value is **refused**, not
answered: an invalid configuration has no eligibility verdict. (Finding F-3, raised by
`tests/adversarial/test_m1_5_falsification.py` and closed in `slots.py`.)

### Three verdicts, and the third is not a soft pass

`FITS` · `OVERFLOWS` · `UNDETERMINED`.

`UNDETERMINED` is what an unmeasured prompt gets. It is **not** eligibility, it does not
become eligibility when nothing better is available, and no rung may be selected on it.
`Eligibility.fits` returns `False` for it, so a caller reading only the boolean cannot
proceed on an unmeasured prompt.

### Why an estimate may not decide

`evaluation/syntax_gate/prompts.py` offers `estimate_tokens()` with a conservative
divisor of 3.0. That is a reasonable design aid and it is **not admissible here**.
`slots.eligibility()` takes a `Measurement` and rejects any instrument that is not a real
token counter, so the rule is enforced by the type rather than by discipline.

The reason is arithmetic, not principle. See the sensitivity table below: the answer for
candidate D flips between two different server configurations somewhere around 2.48
characters per token, which is squarely inside the plausible range for punctuation-dense
JSON. The estimate cannot tell us which side of the line D falls on.

## The truncation trap

An oversized prompt does not raise. `llama-server` evicts the front of the context, the
run completes, and the demonstrations the model was supposed to learn from are the part
that silently went missing. The affected candidate then scores worse for a reason that
appears nowhere in the record — indistinguishable from that candidate simply being worse.

The probe is itself served in a slot, so it inherits the same trap:

- it pins `num_ctx` to the slot under test, so it measures the prompt under the
  configuration the tournament will actually run;
- a reported count within `TRUNCATION_MARGIN` (8) tokens of `num_ctx` is treated as
  evidence of eviction, not as a measurement. The true size is unknown and strictly
  greater, which is `OVERFLOWS` — never `FITS`, and never merely `UNDETERMINED`.

A probe that cannot separate those cases is worse than no probe, because it returns a
comfortable number in exactly the situation that should have stopped the run.

## Measured: the frozen curricula are far larger than the legacy material

Character counts of the fully assembled prompt (system + user), worst case over all 184
held-out Track A tasks, with the five-demonstration curriculum selected below.

| condition | characters | est. @3.0 | est. @2.5 |
|---|---:|---:|---:|
| `A_v0_labelled_linear` | 6,396 | 2,132 | 2,558 |
| `B_v1_labelled_linear_simplified` | 6,415 | 2,138 | 2,566 |
| `C_prefix_sexpr` | 6,722 | 2,240 | 2,688 |
| **`D_constrained_json_graph`** | **14,588** | **4,862** | **5,835** |
| `SE_structured_english` | 7,361 | 2,453 | 2,944 |

**These are estimates and decide nothing.** They are recorded because the *ratio* between
characters and the eventual measured count is itself a finding, and because they show
where the risk is concentrated.

### The 50-demonstration curriculum is not merely tight, it is impossible

Estimated at the conservative 3.0 divisor, worst case over held-out tasks:

| demos | A | B | C | **D** | SE |
|---:|---:|---:|---:|---:|---:|
| 0 | 1,351 | 1,342 | 1,396 | 1,751 | 1,599 |
| 5 (round-robin) | 2,273 | 2,279 | 2,387 | 5,392 | 2,552 |
| 10 | 3,090 | 3,110 | 3,244 | **8,494** | 3,415 |
| 25 | 5,633 | 5,704 | 5,972 | **18,660** | 6,090 |
| 50 | **9,857** | **10,003** | **10,474** | **35,321** | **10,490** |

At 50 demonstrations *every* condition exceeds the 5,888 ceiling, and candidate D exceeds
the entire 32,768-token context. At 10, D alone exceeds the 8,192 slot outright.

Per-demonstration growth on the frozen material is roughly **170 tokens for A** and
**671 for D**, against the 117 tokens/demonstration recorded for the legacy corpus.

### Sensitivity: where candidate D's verdict actually turns

Run through the real ladder machinery with a stub counter at varying ratios:

| chars/token | D estimate | headroom vs 5,888 | selected rung |
|---:|---:|---:|---|
| 4.0 | 3,647 | +2,241 | `4 x 8192` |
| 3.0 | 4,862 | +1,026 | `4 x 8192` |
| 2.5 | 5,835 | +53 | `4 x 8192` |
| 2.0 | 7,294 | −1,406 | **`2 x 16384`** |

**D fits `4 x 8192` if and only if the real tokeniser achieves better than ~2.48
characters per token on its JSON-graph prompt.** Nothing available offline settles that.
This single number is why the probe exists.

## Slot policy and the ladder

Tried in order, and the **whole comparison** moves together:

| rung | per-slot | ceiling | measured speedup |
|---|---:|---:|---:|
| `4 x 8192` | 8,192 | 5,888 | 2.08x |
| `2 x 16384` | 16,384 | 14,080 | 1.54x |
| `1 x 32768` | 32,768 | 30,464 | 1.00x |

Two things are forbidden, and both are refused mechanically rather than discouraged:

1. **Candidate D is never run under a larger slot than A/B/C in the same comparison.**
   `ComparisonPlan` holds one policy and one curriculum for every candidate; there is
   nowhere to put a per-candidate value. `assert_symmetric()` catches the asymmetry if
   results assembled elsewhere are read back in.
2. **D's demonstrations are never reduced alone.** D's extra token cost is a *measured
   property of the JSON-graph representation*, not a harness parameter to be normalised
   away. Trimming it would make the expensive representation look affordable by teaching
   it less, and the resulting score gap would be misread as a property of the syntax.

If no rung fits every candidate, the permitted responses are to shorten the curriculum
**for every candidate together**, or to record that the comparison cannot be run at this
curriculum size. Truncation is never among them.

## The five-example curriculum

Constrained greedy maximisation of

```
F(S) = sum_u max_{s in S} coverage(u, s) - lambda * TokenCost(S)     subject to |S| = 5
```

- **Universe** — the 34 shared core features, the ones every candidate can express.
- **Coverage** — set coverage, so a second demonstration of an already-covered feature
  earns nothing. A plain sum over features used would select five near-duplicates.
- **`TokenCost(S)`** — the **worst case across candidates**, because the binding
  constraint is that all five fit *every* candidate. Costing each candidate separately
  would let the curriculum be cheap on average while overflowing D.
- **`lambda = 1e-4`** — with `|S|` fixed at five, the cost term cannot trade quantity for
  quality; it can only choose between equally-covering sets. At this value the most
  expensive plausible demonstration (~700 tokens) costs ~0.07 coverage units: enough to
  break a tie towards the cheaper set, never enough to discard a demonstration covering
  one extra feature.
- **Determinism** — every step sorts by `(-gain, penalty, task_id)`, so ties resolve by
  id and never by set iteration order. A `digest` over inputs and result makes "the same
  inputs always give the same five" checkable rather than asserted.
- **No dynamic retrieval** — `select_curriculum()` takes **no target task**. Per-task
  curricula are structurally unrepresentable, not merely discouraged.

### Provisional selection (character costs — not yet official)

| rank | task | marginal coverage | cumulative |
|---:|---|---:|---:|
| 1 | `equivalence_vs_implication_000` | 10 | 10 |
| 2 | `distribution_law_004` | 8 | 18 |
| 3 | `assumption_boundary_005` | 5 | 23 |
| 4 | `distribution_law_002` | 2 | 25 |
| 5 | `dimensional_algebra_003` | 2 | 27 |

**27 of 34 shared core features (79.4%).** Uncovered: `concept_block`, `decl_index`,
`objective`, `op_logical`, `quantifier_negation`, `solve`, `type_set`.

This selection is marked `authoritative=False` and carries a `PROVISIONAL` note, because
`TokenCost` came from character estimates. It **must be re-run against measured
`prompt_eval_count`** before it is recorded as the ACQ0 curriculum. The five ids may
change when real costs replace estimates; that is the point of re-running it.

Every selected id is asserted to be in the demonstration pool and absent from the
held-out set. A held-out task reaching the curriculum would turn every downstream number
into a measurement of memorisation, so it raises rather than warns.

## Running the probe (after authorisation)

```python
from evaluation.acq0.budget import (
    OllamaPromptEvalCounter, select_curriculum, walk_ladder,
)
from evaluation.acq0.protocols.runner import LiveCallAuthorisation

auth = LiveCallAuthorisation(
    authorised_by="<Lead>", call_budget=<n>,
    scope="ACQ0 context budget probe", conformance_state="green",
)
counter = OllamaPromptEvalCounter("gemma4:31b", auth)
report = walk_ladder(curriculum_tasks, counter, stop_at_first_fit=False)
assert report.official  # plan found AND every count authoritative
```

The counter cannot be constructed without an authorisation, and the authorisation cannot
be constructed against a red tree. `num_predict=0` makes each probe cheap — it evaluates
the prompt and generates nothing — but not unbudgeted.

`report.official` is `True` only when a rung fits **and** every count came from an
authoritative counter. A stub can produce a plan; it can never produce an official one.

## The superseded figure

`EXECUTION_ENVIRONMENT.md` records **5,893 prompt tokens at 50 demonstrations, "fits —
~2,300 tokens left for completion"**.

That measurement is real and is preserved. It is **not authoritative for ACQ0**, because
it was measured on the 24 paired English/HML demonstrations in
`benchmarks/representations/` — legacy V0 material — and **not on the frozen syntax-gate
curricula this experiment actually uses**. The frozen curricula are several times larger:
50 demonstrations of candidate A estimate at ~9,857 tokens and candidate D at ~35,321,
against the 5,893 recorded there.

That document anticipated this exactly: *"if the frozen curricula are materially longer,
re-measure before Phase G2."* They are. This document is that re-measurement, and the
condition it named has triggered.

## Limitations

- **No token count in this document is a measurement.** Every figure is a character-based
  estimate. The probe has not been authorised or run.
- The probe target in each condition is the longest prompt **by characters**. Characters
  may *select* what to measure — being wrong costs a slightly suboptimal probe target —
  but never *decide* a verdict. Where the runner-up is within 200 characters the probe
  records a note and both should be measured.
- Marginal per-demonstration costs are treated as additive when building a cost model
  from single-demonstration probes. Prompt assembly is concatenation, so this holds up to
  tokeniser boundary effects of a few tokens; the safety reserve absorbs that.
- The `TRUNCATION_MARGIN` of 8 tokens is a heuristic. The server does not announce
  truncation, so proximity to the limit is the only signal available, and a prompt
  genuinely landing in the last few tokens of a slot is refused along with a truncated
  one. Refusing a fitting prompt is the safe direction of that error.
