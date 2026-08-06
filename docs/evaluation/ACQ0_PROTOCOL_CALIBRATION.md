# ACQ0 protocol calibration

Phase record for the 16-condition protocol calibration.
Tree: `commit 21687cf` / `tag hml-m2-context-budget`, branch
`integration/m1.5-paper-derived-closeout`.

This is a **developmental calibration**, not a powered test. Nothing here licenses a
claim of statistical significance, and no ACQ0 Round 1 result is produced by it.

---

## 1. The ACQ0 oracle exemption

`assert_no_oracle` remains **mandatory and unchanged** for H1/H2/H3. It is what stops H3
becoming a tautology: a reasoning hypothesis whose prompt carries the answer is not a
weakened test of reasoning, it is not a test of reasoning.

The exemption is scoped to ACQ0 only and is implemented in
`evaluation/acq0/protocols/oracle.py`:

| Element | Behaviour |
| --- | --- |
| `Hypothesis` | `ACQ0`, `H1`, `H2`, `H3`. |
| `OracleExemption` | Frozen dataclass. `__post_init__` **refuses every hypothesis but `ACQ0`**, so no value of this type exists that an H1/H2/H3 builder could pass. Requires `granted_by`, `authority`, `rationale`. |
| `ACQ0_ENCODING_DISCLOSURE` | `{GOLD_ANSWER, SEMANTIC_FACTS}` — the target proposition plus declared entities, declaration kinds, mathematical roles, law families, conditioning, constraints, quantifier order, dependency structure, domains and dimensions. |
| `NEVER_DISCLOSED` | `{REFERENCE_ENCODING, DISTRACTORS}`. Disclosing the reference HML would make ACQ0 a transcription task and every remaining facet would measure copying. Disclosing distractors teaches the failure modes the corpus exists to detect. |
| `assert_no_oracle(..., hypothesis=, exemption=)` | Both parameters default to the strict behaviour. With an exemption, findings on permitted fields are **returned** (so the disclosure stays in the record); findings on any other field still raise. |

### Why it is unreachable from H1/H2/H3

`evaluation/acq0/prompts/stages.py` — which builds every H1/H2/H3 prompt — is **not
modified**. The disclosure is applied by wrapping its output in
`evaluation/acq0/protocols/encoding.py::acq0_encoding_prompt`, the exemption's only call
site. Three independent instruments enforce this, in
`tests/evaluation/test_acq0_oracle_exemption.py`:

1. the type refuses to be constructed for `H1`/`H2`/`H3`;
2. the guard refuses an exemption presented under a reasoning hypothesis;
3. a source-text assertion that `stages.py` contains no `exemption` / `OracleExemption` /
   `Hypothesis` token, and that `ACQ0_ENCODING_EXEMPTION` appears in exactly two files.

### Consequence — recorded, not buried

> ACQ0 prompts supply the target, so ACQ0's `answer_correct` facet is uninformative by
> construction and must never be cited as evidence about the representation. ACQ0 measures
> format adherence, parse, resolution, type and **exact semantic preservation** only.

This string is `oracle.ACQ0_ANSWER_FACET_VOID` and is written into every condition record
this phase produces.

### Scan scope

The exempted scan covers the **appended disclosure block only**. `base.user` was already
validated by `formalise_prompt` with the correct instrument (substring scan over the
task-composed portion plus content-hash disjointness on the demonstrations). Measured at
`21687cf`, scanning the fully assembled `A_v0_labelled_linear / binding_chain_001` prompt
reports `reference_encoding leaked via 'module BindingChain'` — a *demonstration's* module
name, not this task's answer. That is the documented false-alarm mode, and re-introducing
it here would have been a regression.

---

## 2. Quarantine

`encoding.py::quarantine_report` / `assert_mathematics_fixed_independently` refuse any task
whose expected mathematics is not pinned in the corpus before execution: no `reference_hml`,
no declared entities, no structural facts at all, or no `content_hash`.

Which structure fixes the mathematics is domain-dependent, and the predicate says so. A
binding-chain task's ground truth is its dependency graph and declaration kinds and it has
no laws or quantifiers; requiring laws would have quarantined a task whose mathematics is
perfectly well fixed.

**Both calibration tasks pass with zero findings.**

---

## 3. Blocker found and closed: calibration tasks inside their own curriculum

The Lead froze a 5-demonstration curriculum. The pre-existing
`calibration.calibration_tasks()` rule — first demonstration-stage task per domain, in id
order — returned `binding_chain_000` and `distribution_law_000`, **both of which are in the
frozen curriculum**.

Running that combination would have pasted each task's own reference encoding into its own
prompt as a worked example: the trial would have measured copying, and
`assert_demonstrations_disjoint` would have refused to build the prompt at all.

Closed by adding `exclude_ids` (defaulting to `FROZEN_CURRICULUM_IDS`) to
`calibration_tasks`. Selected tasks are now `binding_chain_001` (structural) and
`distribution_law_001` (distributional). Determinism and the domain contrast are preserved.

---

## 4. Call ledger — derived before execution

Derived by `ledger.derive_call_ledger()` from `core.PROTOCOL_STAGES`, never counted by hand.

| Quantity | Value |
| --- | --- |
| conditions (cells) | 16 |
| direct-generation invocations | 8 |
| draft-generation invocations | 8 |
| formalisation invocations | 16 |
| max eligible repair invocations | 16 |
| **hard maximum total** | **40** |

`8 draft + 16 formalisation (of which 8 are the DIRECT_FORMAL arm's only call) + 16 repair
= 40`. `direct_generation` is a **subset** of `formalisation`, not an addend.

### Token matching (frozen)

| Protocol | Split | Total generated |
| --- | --- | --- |
| `DIRECT_FORMAL` | formal 2048 | 2048 |
| `DRAFT_THEN_FORMAL` | draft 768 + formal 1280 | 2048 |
| repair (separate) | max 1024 | not inside the matched total |

### Authorisation

`ledger.phase_authorisation()` constructs a **phase-specific** `LiveCallAuthorisation` with
`call_budget` equal to the derived hard maximum. The budget cannot be typed in at the call
site.

- scope: `ACQ0 protocol calibration: 4 candidates x 2 non-evaluation tasks x
  {DIRECT_FORMAL, DRAFT_THEN_FORMAL}, curriculum 5, plus at most one repair per cell`
- `conformance_state` must be the literal `"green"`
- citation: `commit 21687cf / tag hml-m2-context-budget`

**Recorded governance defect.** The budget probe was authorised at 400 calls against a
15-call plan — a 26x margin authorises whatever happens rather than a specific study. The
budget-probe authorisation is **not reused**. The correction is mechanical rather than
advisory: `phase_authorisation` derives the number and 40 is not a round number.

---

## 5. Transport

`execute.OllamaBackend` posts to `/api/chat` with `temperature 0` and `num_ctx` held
**constant** at the frozen 8192 rung on every call. `budget/probe.py` varies `num_ctx` per
call, which forces a 24 GB model reload and caused five 120 s timeouts; `timeout_s` here is
600.

Two rules the executor does not break:

- **a transport retry never erases the original failed call** — every attempt is appended
  to `transport_attempts`;
- **an empty visible answer is never retried** — it is a model failure and precisely the
  outcome the paper predicts.

Each condition record is written to
`evaluation/results/acq0/protocol_calibration/<protocol>__<condition>__<task>.json` before
the next condition starts.

---

## 6. Terminal status

Exactly one **earliest** status per attempt, from
`execute._earliest_terminal`, ordered:

`INCONCLUSIVE` (transport) → `UNSUPPORTED` → `FORMAT_FAILED` → `PARSE_FAILED` →
`RESOLUTION_FAILED` → `TYPE_FAILED` → `SEMANTIC_LOSS` → `OBLIGATION_FAILED` → `VERIFIED`.

`CompileResult.ok()` is never read. Per-stage statuses come from
`improvement/episodes.py::classify_stages` via each candidate's `SyntaxAdapter.parse`.
`HML-T426` (wrong arity), `HML-T415` (wrong role), `HML-T403` (declared-type mismatch) and
the epistemic-kind mismatch all parse and resolve cleanly; unknown identifiers fail at
resolution.

**Defect found and closed during the dry run.** `SyntaxAdapter.parse` classifies without an
expected object, so `semantic_status` returns `NOT_RUN` even on a clean parse. The first
implementation fell through to `INCONCLUSIVE`, which would have reported every well-formed
encoding as unmeasured and no arm would ever have recorded a semantic result. The
canonical-hash comparison against `scorer._reference_canonical_hash(task.cso.reference_hml)`
is now done explicitly.

---

## 7. Decision rule

Developmental, not a powered test. Prefer `DIRECT_FORMAL` for causal simplicity **unless**
`DRAFT_THEN_FORMAL`:

1. produces at least **two more** paired semantic successes than it harms;
2. introduces no constitutional failure;
3. does not exceed 2x total generated tokens;
4. creates no new systematic semantic-loss mode.

No statistical significance is claimed from 16 calls.

---

## 8. Results — v1 run (RETAINED, REJECTED as a syntax measurement)

38 of 40 authorised calls spent; 0 transport retries; 17 truncated generations; **27 of 38
calls returned an empty visible answer** with `finish_reason="length"` and `eval_count` at
the cap. Raw records: `evaluation/results/acq0/protocol_calibration/`.

| Condition | Task | DIRECT_FORMAL | DRAFT_THEN_FORMAL |
| --- | --- | --- | --- |
| A_v0_labelled_linear | binding_chain_001 | **VERIFIED** | SEMANTIC_LOSS |
| A_v0_labelled_linear | distribution_law_001 | FORMAT_FAILED | FORMAT_FAILED |
| B_v1_labelled_linear_simplified | binding_chain_001 | PARSE_FAILED | PARSE_FAILED |
| B_v1_labelled_linear_simplified | distribution_law_001 | FORMAT_FAILED | FORMAT_FAILED |
| C_prefix_sexpr | binding_chain_001 | SEMANTIC_LOSS | SEMANTIC_LOSS |
| C_prefix_sexpr | distribution_law_001 | FORMAT_FAILED | FORMAT_FAILED |
| D_constrained_json_graph | binding_chain_001 | **VERIFIED** | FORMAT_FAILED |
| D_constrained_json_graph | distribution_law_001 | FORMAT_FAILED | FORMAT_FAILED |

Paired: `DRAFT_THEN_FORMAL` helps 0, harms 2, ties 6. Exact semantic preservation
2/8 vs 0/8. No repair rescued any cell (14 repairs, 0 recoveries). Generated tokens
excluding repair: DIRECT 11,590 / DRAFT 13,958 (1.20x). Latency: 1,506 s / 1,883 s.

**Gate: `DIRECT_FORMAL_SELECTED`** — decision rule (1) requires `DRAFT_THEN_FORMAL` to
produce at least two more paired semantic successes than it harms; it produced two fewer.

### The dominant failure is not a protocol difference

The model spends its whole completion allowance on reasoning tokens (gemma4 routes these to
`message.thinking`) and emits no visible answer. Every `distribution_law_001` cell failed
this way in both arms. Six of the eight pairs are therefore ties produced by a shared
budget failure, and the selection rests on the two informative pairs — both favouring
`DIRECT_FORMAL`.

One of those two is itself confounded: at `D_constrained_json_graph / binding_chain_001`
`DIRECT_FORMAL` verified using 2,005 of its 2,048 tokens, so the draft arm's 1,280-token
formal allowance could not have fitted the same output. That harm is attributable to the
token split, not to the protocol. The clean harm is
`A_v0_labelled_linear / binding_chain_001`: DIRECT verified at 427 tokens, DRAFT produced a
semantically different object at 426 tokens with no truncation on either side.

Every draft stage hit its 768-token cap (`truncated: true`, 8/8), so the two-stage arm's
first stage never completed. The arm as executed is "truncated draft, then formalise".


---

## 9. v2 run — re-run at 16,384-token slot, 6,144-token allowance

Runtime verified before starting: `llama-server ... -c 32768 -np 2` (pid 9464), Ollama
reports `context_length 16384`, digest `6316f0629137b426…`. `num_ctx=16384` constant on
every call; not changed mid-run.

Changes from v1, and nothing else: completion allowance 2048 → **6144**; split
`DIRECT_FORMAL` formal 6144 / `DRAFT_THEN_FORMAL` draft 2048 + formal 4096; repair 1024 →
2048; **`reasoning`/`thinking` now persisted** (`reasoning`, `reasoning_characters` —
297,374 characters captured across the run); fresh tasks `binding_chain_002` and
`distribution_law_002` (`calibration.EXPOSED_TASK_IDS` now records the v1 exposures and
`CALIBRATION_EXCLUSIONS` unions them with the frozen curriculum); new phase-specific
authorisation; output to `protocol_calibration_v2/`. v1 records are untouched.

### Cap count — the stopping rule fires

| Arm | Stage | Allowance | n | hit `length` |
| --- | --- | --- | --- | --- |
| DIRECT_FORMAL | formalise | 6144 | 8 | **0** |
| DIRECT_FORMAL | repair | 2048 | 8 | 6 |
| DRAFT_THEN_FORMAL | draft | 2048 | 8 | **8** |
| DRAFT_THEN_FORMAL | formalise | 4096 | 8 | 4 |
| DRAFT_THEN_FORMAL | repair | 2048 | 8 | 7 |

**12 of 24 generation events (50%)** hit the cap, against the ~15% invalidity threshold.
Including repair: 25 of 40 (62%). 25 empty visible answers. 0 transport retries.

### Results

| Condition | Task | DIRECT_FORMAL | DRAFT_THEN_FORMAL |
| --- | --- | --- | --- |
| A_v0_labelled_linear | binding_chain_002 | SEMANTIC_LOSS | SEMANTIC_LOSS |
| A_v0_labelled_linear | distribution_law_002 | SEMANTIC_LOSS | FORMAT_FAILED |
| B_v1_labelled_linear_simplified | binding_chain_002 | PARSE_FAILED | PARSE_FAILED |
| B_v1_labelled_linear_simplified | distribution_law_002 | PARSE_FAILED | PARSE_FAILED |
| C_prefix_sexpr | binding_chain_002 | PARSE_FAILED | PARSE_FAILED |
| C_prefix_sexpr | distribution_law_002 | PARSE_FAILED | FORMAT_FAILED |
| D_constrained_json_graph | binding_chain_002 | PARSE_FAILED | FORMAT_FAILED |
| D_constrained_json_graph | distribution_law_002 | PARSE_FAILED | FORMAT_FAILED |

Paired: helps 0, harms 0, **ties 8**. Zero VERIFIED in either arm. No repair recovered any
cell (16 repairs, 0 recoveries). Generated tokens excluding repair: DIRECT 24,507 / DRAFT
39,273 (1.60x). Latency 2,957 s / 4,258 s. 40 of 40 authorised calls spent.

### Gate: `PROTOCOL_UNSTABLE`

Two independent reasons, either sufficient:

1. the pre-agreed invalidity criterion fired — 50% of generation events capped;
2. every pair tied, so the design produced no discriminating evidence at all.

### The allowance fix worked, but only for the one-stage arm

`DIRECT_FORMAL` at 6144 capped **0 of 8** times (`eval_count` 659–5,727, all
`finish_reason="stop"`, all with visible output). That arm is now a clean measurement of
the representation — and on the fresh tasks it produced 6 PARSE_FAILED and 2 SEMANTIC_LOSS,
0 VERIFIED.

The failure is now specific to the **split**: the same 6,144-token budget spent as
2048 + 4096 caps 12 of 16 times. All 8 drafts capped at 2048; 4 of 8 second-stage
formalisations capped at 4096. A two-stage arm whose first stage never finishes is not the
protocol it is labelled as, and the 2,048-token repair allowance is also too small
(13 of 16 capped).

### What this does and does not license

- It does **not** license selecting `DIRECT_FORMAL`. Nothing discriminated the arms.
- It does not license a claim that the candidate surfaces are bad. The `_002` tasks are a
  different pair from v1's `_001` pair, where `DIRECT_FORMAL` verified 2 of 8; a
  task-difficulty difference and a protocol difference are not separated here.
- The `reasoning` field is now on disk for every call, so the next diagnosis has evidence.
  Total generated thinking: 297,374 characters against 24 generation calls.
