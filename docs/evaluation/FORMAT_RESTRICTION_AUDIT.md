# Format-restriction audit — ACQ0 generation protocol

**Milestone** HML-PAPER-DERIVED-INTEGRATION-005, Agent 1
**Branch** `hml-v1-concept-kernel` · **built at commit** `9afafa8`
**Status** protocols, prompts, harness and tests built and passing. **No model call has
been made.** No protocol has been selected.

---

## 1. The research basis and why it threatens ACQ0

Tam et al., *Let Me Speak Freely? A Study on the Impact of Format Restrictions on
Performance of Large Language Models* (EMNLP 2024, Industry Track). Four findings are
load-bearing here:

1. Constraining a model to a structured output format can degrade **reasoning itself**,
   not merely the parseability of the result.
2. Stricter constraints generally degraded more.
3. Constrained decoding was often worse than prompt-based restriction.
4. A two-stage natural-language-then-format pipeline came closest to unrestricted
   performance.

And one observation that this whole package is organised around: a condition with a
**0.148% parse-error rate** coexisted with a **>38-point** reasoning gap.

### The threat, stated precisely

ACQ0 asks which of four candidate surfaces a model can express a frozen semantic object
in. It runs under exactly one generation protocol: problem in, target syntax out. If that
protocol is itself damaging the model's reasoning, then the tournament does not rank
syntaxes by how well they carry meaning. It ranks them by **how well they survive a
flawed protocol** — and the two orderings need not agree.

Worse, the failure is invisible from inside the tournament. Every candidate is damaged
under the same measurement, so no candidate looks anomalous, and the winner arrives with
a clean parse rate and a plausible margin. Nothing downstream of ACQ0 would reveal it.

That is why protocol selection has to happen before the tournament is trusted, and why it
has to be a measurement rather than a judgement.

---

## 2. The three protocols

| protocol | stages | calls | rationale |
|---|---|---:|---|
| `DIRECT_FORMAL` | formalise | 1 | **the protocol the tournament runs today.** The reference arm — if it is not measured, no other arm's result means anything about ACQ0. |
| `DRAFT_THEN_FORMAL` | draft → formalise | 2 | the paper's NL-to-Format arm. If format restriction is damaging reasoning here, this is where it becomes visible. |
| `PLAN_THEN_FORMAL` | plan → formalise | 2 | a **bounded** first stage. Separates "the model needed to think first" from "the model needed to emit more text first", which an unbounded draft cannot. |

`evaluation/acq0/protocols/core.py`

### `DIRECT_FORMAL` is byte-identical to the tournament's own prompt

Not a paraphrase of it. `formalise_prompt` builds on
`evaluation.syntax_gate.prompts.build_prompt`, and a test asserts the resulting
`system` and `user` strings are equal to what `build_prompt` returns. Two consequences:
the reference arm is the protocol actually in use, and the candidate specifications
cannot drift out of sync with the ones the gate will run.

### Stage two keeps the problem statement

A conversion-only second stage ("turn this into JSON") would drop any content the draft
failed to mention. A preservation loss caused by that dropout would be indistinguishable
from a loss caused by format restriction. Keeping the problem costs prompt tokens — which
are recorded and visible in the ledger — and buys an interpretable contrast.

### The upstream block is labelled non-authoritative

The draft is the model's own text and can be wrong. Presenting it as established fact
would convert a stage-one error into a stage-two constraint, making the two-stage arm
look worse than it is. The block header says what it is and what it is not.

---

## 3. No hidden oracle information

If the draft stage were told the answer, `DRAFT_THEN_FORMAL` would win for the wrong
reason, and every conclusion about format restriction drawn from it would be false.

`evaluation/acq0/protocols/oracle.py` splits the guarantee into two questions, each asked
with an instrument that can actually answer it.

**Question one — did this harness compose any of the answer key into the prompt?**
A substring scan over the *task-composed* portion of the prompt, for the reference
encoding (line by line), the gold answer, the structured `SemanticFacts`, and the
distractors. A fragment already present in the permitted content (prose, question,
answer-format instruction) is not a leak, because the one-stage arm carries it too.

**Question two — is any demonstration actually this task?**
`assert_demonstrations_disjoint`, on the **content hash**. Ids can differ while content
does not, and the id check alone would pass for a duplicated task.

### Why the second question needs the second instrument — measured

A substring scan over a prompt carrying the 50-demonstration curriculum flags
**281 of 320** confirmatory-gate prompts. Every one is a false alarm. The corpus reuses a
module name per domain and draws symbols from a shared pool:

| flagged fragment | actually appears in |
|---|---|
| `module ApproximationStatus` | 6 demonstration tasks |
| `varrho : Real` | 7 demonstration tasks, across 3 domains |

A demonstration of a *different* task legitimately contains strings that also occur in the
task-under-test's answer key. A guard with an 88% false-alarm rate is switched off within
a week, and the real check goes with it. After the split, **0 of 320** gate prompts are
refused and the genuine self-demonstration leak is still caught.

### Information parity

The union of what a protocol's stages may carry is asserted equal across all three arms.
The only permitted difference is `UPSTREAM_MODEL_OUTPUT`, and it is admissible for one
specific reason: it is the model's own text, produced under a stage-one prompt already
asserted to be oracle-free. A model that solved the problem correctly writes the gold
answer into its own draft; flagging that would accuse the harness of revealing an answer
the model derived, and would make the two-stage protocol unrunnable on every task it gets
right.

### The unrestricted stage names no target syntax

The draft prompt is asserted **identical across all four candidates**. If it differed, the
two-stage arm would be four different first stages and its result would not be a fact
about the protocol. It carries no fence, no grammar reference and no candidate name.

---

## 4. Token cost is recorded per stage

A two-stage protocol that reports only its formalisation tokens looks as cheap as the
one-stage protocol and is not.

`TokenLedger` keeps the unrestricted stage's cost and the formalisation stage's cost in
separate slots. There is **no settable total** — a test asserts no field name contains
`total`. Totals are derived, and they distinguish two reasons a component can be missing:

* `unrestricted_stage_ran=False` — the stage **did not exist**, so it contributes a
  structural zero and `DIRECT_FORMAL` has a real, complete total;
* `unrestricted_stage_ran=True` with an absent count — the stage ran and its cost is
  unknown, so the total is **absent**.

Collapsing the two would either make `DIRECT_FORMAL`'s cost unavailable — blocking the
comparison the ledger exists for — or make an unmeasured draft look free.

Counts are `Measurement`, not `int`. `Measurement.measured` requires an instrument from
`KNOWN_INSTRUMENTS` that is available on this machine; `provider_usage` is unprobeable
from inside the process, so it additionally requires the artefact to be cited. Offline,
the honest value is an absence with a reason, never a zero.

---

## 5. Field order is an inductive bias

Tam et al. observed JSON-mode outputs placing the answer field **before** the reasoning
field. A model that must emit `"answer"` first has to answer first: the schema removed
chain-of-thought by ordering alone, with no instruction to that effect, no visible
symptom, and valid JSON every time.

The required order (`evaluation/acq0/prompts/field_order.py`):

```
assumptions -> declarations -> constraints -> derivation/state -> result
```

`validate_field_order` enforces it as a **partial** order — no result field may precede a
prerequisite; a prompt need not list every field.

### The candidate D probe

Candidate D's surface is a JSON object, so it is the candidate that can order the answer
before the reasoning in exactly the way the paper observed.

| | |
|---|---|
| arms | `SEMANTIC_FIRST` vs `ANSWER_FIRST` |
| pool | demonstration-stage tasks only, never G2/G3/G4/replication |
| hypothesis | answer-first reduces exact semantic preservation **without** reducing parse success — the paper's pattern, on this corpus |
| decision rule | answer-first is excluded from the official gate unless the probe records `degrades_semantic_preservation: False` with a cited artefact |
| scope | candidate D, this model, this corpus. No claim about A/B/C and none about JSON in general |

**The probe has not been run.** `assert_gate_field_order` therefore refuses `ANSWER_FIRST`
in the official gate, and refuses it for partial evidence: an unrun probe, a positive or
unmeasured degradation result, or an uncited claim. The asymmetry is deliberate —
semantic-first needs no evidence because it is the arrangement with no published mechanism
for harm.

The answer-first arm is nevertheless buildable, because a refusal is only meaningful if
the refused thing exists to be compared against.

---

## 6. The eight metrics, kept apart

`format adherence` · `parse success` · `resolution success` · `type success` ·
`exact semantic preservation` · `repair success` · `token cost` · `latency`

Eight fields. No `score()`, no weighted combination, no boolean standing for "it worked".
A test asserts `ProtocolMetrics` exposes no aggregate.

`None` means **not measured**, never `False`. A stage the pipeline never reached has no
verdict, and recording one as a failure attaches a defect to a stage that was never given
an input.

### `CompileResult.ok()` is not the parse verdict — measured on this compiler

Every metric is derived from `improvement/episodes.py::classify_stages`, which runs each
stage in its own right. Measured, and asserted by
`test_the_conflation_defect_is_refuted_on_real_sources`:

| source | terminal | parse | resolution | type |
|---|---|---|---|---|
| `const a : Real = ((` | `PARSE_FAILED` | **False** | — | — |
| `def y : Real := zzz + 1` | `PARSE_PASSED_RESOLUTION_FAILED` | **True** | False | — |
| `const a : Probability = 2` | `RESOLVED_TYPE_FAILED` | **True** | True | False |
| `law x ~ Normal(mean := 0.0, variance := 1.0)` (HML-T415) | `RESOLVED_TYPE_FAILED` | **True** | True | False |
| `const a : Real = 2` | `SEMANTICALLY_PRESERVED` | True | True | True |

Only the first is a parse failure. Under a single `ok()` boolean, four of these five are
indistinguishable, and the first-attempt parse rate would be understated while the
compiler's type checking is blamed on the candidate surface.

`assert_no_conflated_verdict` refuses any third-party object exposing `ok` and no
per-stage record. `ProtocolMetrics.__post_init__` refuses a record in which a stage
carries a verdict after an earlier stage failed to run.

### Format adherence and parse success are independent

The paper's headline pairing, reproduced as a type-level property and asserted in both
directions:

* a reply with a correct ` ```hml ` fence containing unparseable text →
  `format_adherence=True`, `parse_success=False`;
* a reply with no fence at all containing valid HML-L1 →
  `format_adherence=False`, `parse_success=True`.

An **untagged** fence is not counted as adherence. The scorer's extractor tolerates one as
a fallback; measuring the tolerance would credit the model with compliance it did not
produce.

### Repair success reads the parse status, not the compile status

A repair that fixes a syntax error and leaves a type error **did** repair the parse.
Counting it as a failure would understate the repaired parse rate and blame the surface
for the type checker. No repair attempted is `None`, which is not a failed repair.

---

## 7. Prompt sensitivity

Three phrasings (`evaluation/acq0/prompts/sensitivity.py`), differing in wording and not
in content. "Semantically identical" is checked, not asserted: each phrasing must
discharge every obligation in `INSTRUCTION_OBLIGATIONS` — encode the problem, point at
the supplied reference, require a fenced block, require the answer markers, and put the
encoding before the answer. A phrasing that dropped one is a different instruction, and
the checker says which obligation is missing.

`P1_imperative` is the wording the tournament already uses, so a result can name the
incumbent rather than "the first one". Substitution operates on the assembled prompt's
block structure and **raises** if that structure is gone: a phrasing probe that silently
failed to change the phrasing would report three identical arms as evidence of
insensitivity.

**Development subset only.** `assert_development_subset_only` refuses any task id in
`TRACK_A_HELD_OUT_IDS` — G2 screening, G3 curriculum, G4 confirmatory and G4 replication.
A task shown to the model during a wording probe is spent, and spending it silently
inflates the gate's result by exactly the amount nobody could measure afterwards. The
probe applies to the eventual winning syntax only.

---

## 8. Calibration design — specified, not executed

`4 syntaxes x 2 non-evaluation tasks x 2 protocols`
(`evaluation/acq0/protocols/calibration.py`)

### 16 cells is 24 calls

| protocol | cells | calls |
|---|---:|---:|
| `DIRECT_FORMAL` | 8 | 8 |
| `DRAFT_THEN_FORMAL` | 8 | **16** |
| **total** | **16** | **24** |

`DRAFT_THEN_FORMAL` runs two stages per cell. **An authorisation written against the cell
count is short by exactly the draft stage** — the same omission the token ledger exists to
prevent, transplanted into the budget.

### Tasks

`binding_chain_000` and `distribution_law_000`, both **demonstration-stage**: the only
pool that never scores anything. Chosen deterministically (first in id order within each
domain) and from different domains — one structural, one distributional — so a protocol
that helps only one kind of content cannot look like a protocol that helps.
`assert_calibration_tasks_are_not_evaluation` asserts this against
`TRACK_A_HELD_OUT_IDS` rather than trusting the selection.

### Curriculum size 0, and why

Two grounds, the first of which the guard caught in practice:

1. The calibration tasks come from the demonstration pool, so a non-zero curriculum places
   a task **in its own demonstration set** — its reference encoding pasted into its own
   prompt as a worked example. Measured: attempting exactly this raises `OracleLeak`.
2. Prompt budget. Stage two of `DRAFT_THEN_FORMAL` carries specification + problem +
   draft. Measured with a 3,000-character draft stand-in, conservative 3 chars/token:

| condition | direct | stage 2 | vs 8192 slot |
|---|---:|---:|---|
| A labelled-linear | 1,298 | 2,325 | fits |
| B simplified linear | 1,289 | 2,316 | fits |
| C prefix S-expression | 1,343 | 2,370 | fits |
| D constrained JSON | 1,698 | 2,725 | fits |

Worst case 2,725 estimated tokens against an 8,192 slot: 5,467 tokens of headroom.

### Selection rule

Lexicographic (`evaluation/acq0/protocols/selection.py`). In order:

1. **constitutional validity** — a design violation disqualifies before any number is read
2. **semantic preservation** — exact recovery of the canonical object
3. **repaired parse rate**
4. **domain stability** — the *worst* per-domain rate, not the mean
5. **token cost** — including the draft
6. **latency**

**Never by parse rate alone.** Parse rate is not a primary criterion at all. The paper
observed a 0.148% parse-error rate alongside a >38-point reasoning gap: a protocol can
produce text that parses essentially always and means the wrong thing essentially always.
Selecting on parse rate would prefer exactly that protocol.

**Never by a weighted score.** Under any positive weight on cost, a protocol producing
cheaper, subtly wrong encodings can outrank one producing correct expensive ones, and the
trade is invisible in the headline number. Lexicographic ordering makes the trade
inexpressible. `assert_no_weighted_scorer` asserts the module never acquires a combiner,
and a test constructs the adversarial case directly: an arm at 25% preservation and 100
tokens loses to an arm at 100% preservation and 100,000 tokens.

### Materiality thresholds — pre-registered

Fixed before any model call was made, which is what makes them thresholds rather than
post-hoc choices.

| key | threshold |
|---|---|
| semantic preservation | 0.25 |
| repaired parse rate | 0.25 |
| domain stability | 0.25 |
| token cost | 20% relative |
| latency | 20% relative |

8 trials per arm, so one trial is 0.125 and 0.25 is two trials' worth. Coarse, and
honestly so: 8 trials cannot resolve less, and pretending otherwise would turn sampling
noise into a protocol decision.

### The three refusals

`select_protocol` returns `UNSTABLE` rather than a winner when nothing was measured, and
when a key needed for the comparison is absent for an arm still in contention — an absent
key is *unavailable*, not tied. It returns `AMBIGUOUS` when every key ties, and the
escalation is to run `PLAN_THEN_FORMAL` (8 more cells, 16 more calls), **not** to break
the tie on cost. Breaking a tie on cost is a weighted score with all the weight on one key.

### Authorisation

`LiveCallAuthorisation` names the authoriser, the budget and the scope, and records the
conformance state. Anything but `"green"` raises `ConformanceNotGreen`: a result produced
on a red tree cannot be attributed to the code that was reviewed. `AuthorisedSession`
counts calls down and raises when the budget is spent. A live backend with no
authorisation raises `UnauthorisedModelCall` — there is no keyword that bypasses it, and
the default backend is offline.

An empty completion is **never** retried. An empty visible answer under a format
restriction is precisely the outcome the paper predicts and this study is trying to
observe; retrying until text appears would delete the measurement. Transport failures are
retried and every attempt is preserved.

---

## 9. Findings

### F1 — 16 cells is 24 calls

`DRAFT_THEN_FORMAL` is a two-stage protocol. The authorisation must be written on 24, or
the draft stage of the final eight cells is unfunded. Escalation to `PLAN_THEN_FORMAL`
adds 16 more.

### F2 — a substring leak scan is unsound on this corpus

281 of 320 confirmatory-gate prompts flagged at the 50-demonstration curriculum, all false
alarms, caused by module and symbol names shared across tasks by design. Demonstration
disjointness must be asserted on the **content hash**, which is the instrument
`partition.py` already uses. After the fix: 0 of 320 refused, self-demonstration still
caught.

### F3 — the frozen curricula do not fit the per-slot budget above size 5

`docs/PROJECT_STATUS.md` records "50 demonstrations, 5,893 prompt tokens, fits the
8192-token slot". That figure was measured on the 24 paired demonstrations in
`benchmarks/representations/`, **not** on the frozen `syntax_gate` curricula.
`docs/evaluation/EXECUTION_ENVIRONMENT.md` carries the caveat: *"if the frozen curricula
are materially longer, re-measure before Phase G2."*

They are. Measured with the repo's own `prompt_budget_report`, against a held-out G4
confirmatory task, conservative 3 chars/token:

| size | A chars | D chars | D est. tokens | verdict |
|---:|---:|---:|---:|---|
| 0 | 3,905 | 5,105 | 1,701 | fits |
| 5 | 6,673 | 16,029 | 5,343 | fits |
| 10 | 9,122 | 25,336 | 8,445 | D over the 8,192 slot |
| 25 | 16,752 | 55,832 | 18,610 | D over |
| 50 | 29,423 | 105,816 | 35,272 | **every condition over; D exceeds even the 32,768 total context** |

The repo's own tooling agrees: `largest_curriculum_that_fits_every_condition` returns
**5**, not 50. Candidate D drives it — its surface is roughly 3.6x candidate A's character
count for the same semantic content.

This is outside this agent's ownership and is not fixed here. It bears directly on
protocol calibration: curriculum 0 is the only size at which stage two of
`DRAFT_THEN_FORMAL` has comfortable headroom, and the gate's own runnable curriculum
appears to be 5 rather than 50. The chars-per-token figures are estimates using the repo's
conservative divisor; the authoritative number is `prompt_eval_count` per call, which
requires an authorised model call.

### F4 — no protocol has been selected, and none could have been

No model call was made. `select_protocol` on zero measured trials returns `UNSTABLE` with
the reason recorded: a choice made now would be a preference wearing the label of a
result.

---

## 10. Limitations

* **Nothing has been measured about the protocols themselves.** Everything above is
  design, guard and harness. The paper's effect has not been reproduced, refuted or
  bounded on this model or this corpus.
* **8 trials per arm** detects a large protocol effect and cannot detect a small one.
* **Calibrated at curriculum 0.** Transfer to the gate's curriculum is an assumption.
  Demonstrations may themselves mitigate format restriction, in which case the difference
  measured at calibration is an *upper bound* on the difference at the gate's curriculum.
* **One model, one quantisation, one host** — `gemma4:31b` Q4_K_M, Ollama 0.32.5,
  temperature 0. No claim transfers to another model.
* **The two calibration tasks are demonstration-pool tasks** and will subsequently appear
  in gate curricula. That does not contaminate the gate's *scoring* set, but those two
  tasks are no longer usable as held-out items.
* **The field-order probe has not been run**, so the paper's answer-first effect is
  neither confirmed nor excluded on candidate D. Semantic-first stands by default, not by
  evidence.
* **The prompt-sensitivity probe has not been run**, and cannot be until a winning syntax
  exists.
* **`assert_no_oracle` is a string scan.** It catches a fragment of the answer key
  reaching a prompt. It cannot catch a *semantic* leak — a paraphrase of the reference
  encoding that shares no distinctive substring with it. Prompts are built from frozen
  templates, so the exposure is bounded, but the guard is not a proof.

---

## 11. Gate

`ACQ0_PROTOCOL_UNSTABLE`

Not because a measurement was unstable — because **no measurement was taken**. Selection
awaits the Lead-authorised calls, and the authorisation must be written on **24**, not 16.
