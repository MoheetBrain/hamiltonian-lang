# Project Status

Snapshot date: 2026-08-04. Maintained per the commit continuity protocol.

## Project Objective

Hamiltonian Lang is a **cross-domain, typed mathematical intermediate representation and
verifier-guided reasoning protocol whose syntax, semantic organisation and concept system
are treated as experimentally optimisable variables**, tested under matched conditions
against natural language, conventional notation and existing formal systems.

Specified as eight components in `GOAL.md`: Σ surface · 𝒢 front end · 𝒮 semantic core ·
ℛ reasoning state · ℰ epistemics · 𝒞 concept registry · ℬ backends · **𝒪 empirical language
optimisation — the novelty candidate**.

**The broad novelty claim is withdrawn.** Minilang/AoA (arXiv 2607.16372, 17 July 2026,
retrieved and verified) already demonstrated an LLM-oriented proof language, a JSON AST
interface, demonstration-based teaching, prover feedback and reduced token cost. Hamiltonian
may not claim novelty from any of those. What remains is the **conjunction** of eight
properties in `GOAL.md` §1, of which item 8 — optimising the representation itself under
matched controls — is the defensible candidate.

The project succeeds only if a reproducible advantage is demonstrated on at least one
important mathematical task. **A pilot measurement has now been taken and found no
advantage — see `docs/evaluation/HML_EVAL_001_PILOT_REPORT.md`. The decision is REDESIGN
AND RETEST.** The pilot was saturated at 93% accuracy across all seven arms and had almost
no power, so it is not evidence that no advantage exists.

## Current Stage

**THE REPRESENTATION ARENA EXISTS AND IS GREEN — `arena-1.0.0`, zero model calls.**
`evaluation/arena/` renders one neutral semantic world in three provably
information-matched notations — structured English (SE), a generic semantic AST (the
required control), and real HML — and scores answers with deterministic oracles. Parity is
**proved per world** by round trip, `canonical_world(decode_X(render_X(w))) ==
canonical_world(w)`: measured **1800 round trips over 600 worlds, 0 failures**. The
pre-flight gate passes all eight checks (306 items, 69 minimal-contrast pairs) and 100 arena
tests pass. Design record: `docs/evaluation/ARENA_DESIGN.md`.

The handoff's plan to bolt a rendering layer onto `difficulty_lab/families.py` was **not
executable**: that generator builds its English inline and discards the structure, so
nothing survives to render a second way. The arena rebuilds the worlds structure-first;
`difficulty-lab-1.0.0` is untouched and byte-identical.

**No HML-vs-SE reasoning result exists yet.** The arena is instrumentation, not evidence.

**The first SE-only developmental screen is INVALID and no model has been selected.**
`gemma4:12b` (11.9B, Q4_K_M, digest `4eb23ef187e2c546…`) was pulled as the first of at most
three candidates — the 31B is excluded because it is known to saturate. The screen ran 24
structured-English calls and failed twice: a misplaced module-entry guard crashed the runner
after every call had completed, discarding all records (~36 min of compute, log preserved at
`evaluation/arena/results/DEV_gemma4-12b_ATTEMPT1_LOST.console.txt`); and **12 of 24 responses were
truncated** at `max_tokens=4096`, because `gemma4:12b` is a thinking model whose finished
responses averaged 2395 completion tokens. Ten of twelve pairs were dropped whole, so the
model cannot be placed in the 30–70% target band. Both faults were mine, not the model's.

The runner is repaired — records are now written incrementally, and
`tests/arena/test_runner_preflight.py` drives CLI → calls → JSONL → summary → reload with a
fake client before any model is touched.

**A DEVELOPMENTAL ORGANISM IS FROZEN: `gemma3:4b` at 3/6 pairs.** The SE-only micro-screen
was run down a fixed ladder, one frozen 6-pair / 12-call set (offset 6, L3, temp 0,
`max_tokens` 8192) reused unchanged for every candidate:

| model | params | pair BOTH-CORRECT | single-item | trunc | mean ctok | mean lat | verdict |
|---|---|---|---|---|---|---|---|
| `gemma4:e4b` | 8.0B | 6/6 | 12/12 | 0 | 1004 | 15.4 s | too strong |
| `gemma4:e2b` | 5.1B | 6/6 | 12/12 | 0 | 996 | 7.6 s | too strong |
| **`gemma3:4b`** | **4.3B** | **3/6 = 0.50** | **7/12 = 0.583** | **0** | **180** | **3.8 s** | **SELECTED** |
| `llama3.2:3b` | 3.2B | 0/6 = 0.00 | 4/12 = 0.333 | 0 | 108 | 0.8 s | too weak + 2 responses with no `FINAL:` line → rejected |

Every screen was clean — no truncations, no invalid responses, nothing dropped. `gemma3:4b`
is perfect on algebra, half on quantifier order and zero on implication direction, with
**12/12 correctly formatted responses**: it follows instructions and reasons imperfectly,
which is the organism the protocol wants. The ladder **brackets** the choice — 6/6 above, 0/6 below, `gemma3:4b` alone in band — so it
was not a knife-edge call between neighbours. Frozen in
`evaluation/arena/results/FREEZE_gemma3-4b.json` — model + digest `a2af6cc3eb7fa8be…`,
runtime, prompt hashes, endpoint, scoring, and generator/scorer versions.

**Caveat recorded, not buried:** `gemma3:4b` is a *different family* from the gemma4
candidates. Acceptable because the pilot compares SE/AST/HML **within** this one frozen
model, so family never enters the contrast — but its results cannot be pooled with or
compared against the gemma4 screens. Note also that Endpoint B at L3 remains saturated for
every gemma4 candidate tried; headroom exists for this organism specifically, not for the
endpoint in general. And N=6 pairs makes 0.50 a selection signal, not an estimate.

**MODEL CONFIRMED AND FINAL-FROZEN: `gemma3:4b` — 5/6 out-of-sample, 8/12 pooled.**
Stated precisely because the two halves play different roles: offset 6 scored **3/6 and is
the set that *selected* the model**; offset 8 scored **5/6 and is the only genuinely
out-of-sample half**. The headline 8/12 (0.667) pools selection with confirmation.
Six additional fresh pairs (offset 8) gave 5/6, added to the earlier 3/6. Inside the 4–8
target band, so `FREEZE_FINAL_gemma3-4b.json` supersedes the provisional freeze. Three
caveats are recorded in it: 8/12 is on the **upper edge** and outside the preferred 5–7; the
halves disagree sharply (3/6 then 5/6), so the estimate is unstable; and **`OPERAND_ORDER`
is 4/4 — saturated**, so one third of frozen pilot pairs are expected to be
non-discriminating. The composition was deliberately not changed, because altering task
semantics after selection would invalidate the selection.

**SEMANTIC AUDIT PASSED — 62 checks, read-only, no production change.**
`tests/arena/test_semantic_audit.py` keeps the seven judgment classes separate rather than
collapsing them into one `VALID` flag, and verifies exactly the properties the pilot depends
on: entities, types, free/bound variables, binder order and scope, assumptions, implication
direction, goal/query, and that the oracle answer is *literally shared* across arms. A
negative control confirms a binder swap is observable in every arm. `EXECUTES` and
`IS_PROVEN` are recorded not-applicable **with an assertion**, not skipped. Constitution:
`docs/semantics/HML_SEMANTIC_CONSTITUTION_V1.md`.

**ACQUISITION GATE FAILED TWICE. THE PILOT HAS NOT BEEN RUN.**

*Attempt 1 — `INVALID_INSTRUMENT`, permanently.* Six of eighteen responses had no `FINAL:`
line and three held the correct answer, so AST's 0/6 was an artefact. Not carried forward.

*Attempt 2 — repaired scoring, fresh seeds 400101–400106.* `extract_bare` now accepts a
reply that **is** a declared answer (whole reply or last line, exact match), applied
identically to all arms; **the reasoning-pilot scorer is untouched** and still requires a
`FINAL:` line, guarded by a test. Five bare answers were recovered. Result:

| arm | score | BINDER_ORDER | FACT_CONTENT | RELATION_LOOKUP | SORT | FACT_COUNT | GOAL_TARGET |
|---|---|---|---|---|---|---|---|
| SE | 4/6 | correct | correct | correct | correct | WRONG | WRONG |
| AST | **3/6** | **WRONG** | correct | correct | correct | WRONG | WRONG |
| HML | **4/6** | correct | correct | correct | correct | WRONG | WRONG |

**Required ≥5/6 for AST and HML. Both fail.** Diagnosis, stated in both directions:

- **`GOAL_TARGET` is a broken item of mine** — it asks about "the question above", but the
  acquisition question *replaces* the world's query, so no such question is in the prompt.
  Unanswerable by construction; all arms answered `P3` with nothing to read.
- **`FACT_COUNT` is failed identically by all three arms** (byte-identical `10` against a
  true 11) — a counting failure of the model, shared by the control, carrying no
  representation signal.
- **RETRACTED (2026-08-08, pre-run audit): `BINDER_ORDER` was ALSO unanswerable.** This
  document previously read: *"On the four items testing distinctions the pilot depends on,
  HML scored 4/4 and AST 3/4. AST's miss is `BINDER_ORDER` … opposite to the direction a
  'structure helps' hypothesis predicts."* **That inference is unsound and is withdrawn.**
  `build_prompt` uses `item.question or renderer.question(world)`, so a non-empty item
  question *shadows* the world query — and every acquisition item sets one. The claim lives
  only in `renderer.question`, so the only occurrence of `forall`/`exists` in any of the
  three prompts was the answer line itself. All three arms were guessing a coin flip with
  nothing to read; SE and HML were lucky, AST was not. HML's "4/4 on pilot-relevant
  distinctions" was really 3/3 plus a coin flip.

It would be easy to argue the gate "really" passed for HML. That argument is deliberately
**not** made: the pre-registered bar is 5/6, HML scored 4/6, and one instrument repair has
already been authorised. Repairing until the gate clears is what makes a result
unfalsifiable.

**Pilot composition was decided and documented before any pilot call** —
`docs/evaluation/PILOT_COMPOSITION_DECISION.md`: 6 `QUANTIFIER_ORDER` + 6
`IMPLICATION_DIRECTION` + 0 `OPERAND_ORDER`, calibrated from the SE-only control (4/4
ceiling vs 2/4, 2/4).

**Zero pilot calls have been made.** The PILOT seed band is untouched; ACQUISITION seeds are
burned.

**CI IS GREEN ON THIS BRANCH.** The reproducible environment repair proven on
`integration/m1.5-paper-derived-closeout` @ `8e1c4df` was never propagated here, so this
branch stayed red for an environment reason while the fix sat on a divergent branch. Ported
now: SymPy declared as an `equivalence` extra (`>=1.14,<2`) that `[dev]` installs, the
scoring-worker test made portable, and workflow concurrency bounded. No mathematical
semantics changed and no test weakened.

**HML V2 REASONING KERNEL — PHASE I LANDED (branch `feature/hml-reasoning-kernel-v2`).**
The language now has a surface form for a reasoning *transition*, which the language
audit found it entirely lacked (0/19 transformation forms representable in `.hml`).
Three statement forms — `goal`, `derive`, `proved` — plus a 16-rule trusted kernel,
generated proof obligations, and a scoped refinement environment that makes `assume`
load-bearing. `DeriveStmt.status` is computed by the checker and has no surface syntax,
so a model can assert a derivation but cannot assert that it is correct. See `D-025` and
`docs/hml_v2/`.

Strictly additive: all 43 `examples/**/*.hml` hash byte-identically under the V2 and v1
compilers, so ACQ0/H2 records stay reconstructible under their original language version.

**Phase II is now done too (D-026):** all eleven critical coverage zeros are closed and
enforced — expectation/conditional/joint/independence, set membership and comprehension,
limit/derivative/integral/continuity, and correlation-vs-causation. Four ship as examples.

**Adversarial review found a critical defect in the phase-I spine and it is fixed
(D-027):** a `goal` was admissible as a derivation premise, so `goal g1 : 1.0 = 2.0`
could prove itself with zero diagnostics. Premises must now be ESTABLISHED, and
obligations propagate along derivation chains.

**The capability audit has been rerun (`docs/hml_v2/AUDIT_RERUN.md`).** Critical zeros
11 → 0 and critical faithful 79.7% → 96.9% under corrected probes (8 zeros / 82.8% under
unmodified probes; both readings published). Transformation representability 0/19 → 7/19
and verifiability 0/19 → 7/19. Backend silent loss held at 0. **Maturity is still
LEVEL 1 — DOMAIN DSL**: compositional closure measured 0.692 against a Level 2 threshold
of 0.70, and coverage is `NOT_ASSESSED` with 408/486 atoms unprobed. Criterion 3.5 —
transformations that check their own preservation, which the ladder names as the
distinguishing Level 3 capability — moved FAIL → PASS.

**READ `docs/handoff/HML_HANDOFF_2026-08-08_SIGNAL_PIVOT.md` FIRST.** It is the
authoritative, verified entry point for a fresh context and supersedes any stale figure
elsewhere in this file.

**STRATEGIC PIVOT.** The plan is no longer "finish HML → harder maths → paired benchmark".
It is a neutral semantic world factory rendered three ways (structured English / generic
AST / HML) feeding representation microbenchmarks — next-action prediction, paired minimal
contrasts, corruption detection. **A generic AST is a required control**: without it, any
HML benefit could be a benefit of structure in general.

**SYNTHETIC CALIBRATION ALSO SATURATED — `SYNTHETIC_STATE_COMPLEXITY_SATURATED`.** A
neutral machine-generated difficulty lab (four families, deterministic oracles, validated
offline with independent cross-checks) returned **9 valid / 9 correct / 0 truncations**
across L3, L5 and L7 — L7 being depth-16 dependency chains with 6 distractors and
10-variable logic worlds with 26 constraints. Two independent instruments have now failed
to find headroom for this model. See `docs/evaluation/SYNTHETIC_CALIBRATION_REPORT.md`.
Total local Gemma calls across all protocols: **22. HML calls: 0.**

**THE EARLIER SE CALIBRATION ALSO FOUND NO USABLE HEADROOM.** 13/13 calls used;
**10 valid observations, 10 correct**. The two apparent failures were `finish=length`
truncations at 8192 tokens, one of them mid-way through a correct argument — recorded
MEASUREMENT_INVALID rather than counted as difficulty. This is the third corpus in the
project's history to saturate (93%, 100%, 10/10). The one difficulty axis discovered
(length) is unusable for this hypothesis, because HML is more verbose than prose and would
truncate sooner. See `docs/evaluation/SE_CALIBRATION_REPORT.md`.
**No HML model call has been made. Total Gemma calls: 13, all structured English.**

**Superseded note — SE difficulty calibration was under way (signal-first directive).** Structured-English
only, no HML. CAL-1 3/3 and CAL-2 5/5 against tasks built around the exact semantic traps
HML targets; CAL-3 pending. 9 of the 13-call budget used. No truncation (877-2392 tokens of
8192). This is the third corpus in the project's history to saturate.

**A binder protocol now exists (D-046),** added to fix `free_names`, which dispatched by
whitelist and silently reported NO free variables inside an integral, derivative or
comprehension. Measured: `ObligationTask.closed()` returned **True** for a proposition
with a free variable. Masked end-to-end by an unrelated subset guard, so no wrong verdict
was delivered — but wrong in the dangerous direction. `binder_of` / `expr_children` /
`BINDER_KINDS` are structural, so an unknown node kind is descended into rather than
skipped. Used by `free_names` only; the other ~78 binder dispatch sites are unaudited.

**The binder/shadowing defect is fixed (D-045).** D-006 was being applied to mathematical
binders, so `derivative(f, x)` was rejected whenever `x` was declared. Composition moved
0.438 -> 0.458 — one specimen, against a prediction of high leverage that was wrong.

**A CRITICAL soundness exploit was found and closed (D-044).** Obligations were keyed on
the inference rule, so `multiply_both_sides(by := 1.0 / 0.0)` reached VERIFIED and its goal
reached PROVED with zero diagnostics. Definedness is now a property of TERMS: one contract
registry, and a pass over every expression a derivation touches. Refuted obligations REJECT
rather than sit OPEN. Also closed: `Matrix[2,3] + Matrix[4,5]` compiled clean (HML-T435).

**The full 486-atom ontology is now classified with executed states:** PASS 162, PARTIAL 71,
LOSSY 207, ABSENT 21, BACKEND_ONLY 1, NOT_MEASURED 24. Of the 64 CRITICAL: PASS 47,
PARTIAL 15, LOSSY 2, **ABSENT 0**. Whole-ontology PASS+PARTIAL is 233/486 = 47.9%.

**Scoped Γ is implemented (D-043):** `scope … end` opens a real assumption frame; facts
do not survive it, precede it, cross to siblings, or escape nesting. Local contradiction
is warned and contained rather than banned, so proof by contradiction stays expressible.
Composition moved **0.417 → 0.438** — one specimen; the gate is 0.85 and the remaining
failures are 14 GRAMMAR / 8 TYPE.

**The AST fork is decided on measurement: no rewrite (D-041).** The 48 composition
specimens were encoded and executed for the first time — STRICT closure **20/48 = 0.417**
(the legacy 13-probe subset reads 0.692 at the same SHA; they are different instruments).
Failure attribution over 28 failures: GRAMMAR 14 · TYPE 8 · COMPILER 3 · CONSTRAINT 2 ·
SCOPE 1 · CANONICAL 0 · BACKEND 0. A generic Apply/Bind/Attribute core would reach
**0.563 — below the Level 2 threshold** — while targeted repairs reach **0.854**. The
rewrite is neither necessary nor sufficient. Circular probability laws are now rejected
(HML-S607, D-042).

**An explicit evidence graph now backs the reasoning layer** (`reasoning/evidence.py`,
D-040). Acyclicity previously rested on a single textual-order rule that was sound only
for single-module source-order construction and never saw `proved` edges; there is now a
validator walking all four edge kinds, a three-way ESTABLISHED / PROVISIONAL /
NOT_EVIDENCE split, and named checks for E1/E2/E3/E4/E7/E8.

**Research-integration decisions are recorded** in
`docs/hml_v2/RESEARCH_INTEGRATION_DECISIONS.md`: 14 recommendations classified against
measured state, with the generic Apply/Bind AST core explicitly DEFERRED pending failure
attribution rather than accepted on recommendation. Measured corrections to inherited
figures: tests are 6252 (not 6240); the full 48-specimen composition set closes **20/48**,
which is not the same measurement as the 0.692 reported over a 13-specimen subset.

**A 16-step programme is now underway; step 1 (architectural freeze) is done.**
`docs/hml_v2/ARCHITECTURE_FREEZE.md` freezes six decisions as binding contracts —
evidence semantics, Γ/scope, definedness, approximation, verifier certificates and
extension trust (D-034…D-039) — each with its rejected alternatives recorded. Twelve
tests pin the decisions that already hold. **The freeze is a contract, not an
implementation**: scoped Γ, precondition contracts, approximation and certificates are
all still absent from the compiler. Steps 2–4 implement them next; step 5's AST fork
(generic Apply/Bind/Attribute core vs bespoke nodes) is being measured, not assumed.

**Phases III-IV are NOT done** — compositional-closure measurement, the extension/module
mechanism, the synthetic trajectory generator, the 100+ specimen suite and the
capability-audit rerun all remain. **No maturity-ladder claim is made until the audit is
rerun**, and no BEFORE/AFTER coverage percentages exist yet.

**THE 24-TASK V1 BENCHMARK IS RETIRED FOR H2 — `HML_BENCHMARK_FAILED_NO_SIGNAL`.**
The SE control scored **23/23 (100%)** against a usable headroom band of 6-17, so the gate
returned INSUFFICIENT and **no HML-V1 call was made**. See
`docs/evaluation/V1_HEADROOM_GATE_REPORT.md`.

**This is a verdict about the corpus, not about HML.** No HML scientific call exists.

Run `decisive_01`, developmental protocol v1.3: 23 valid paired tasks, 46 calls, 2.27 h,
132,571 completion tokens. Integrity complete -- 0 truncations, 0 transport errors, all 46
calls scored `ok`, exactly one answer marker per reply, one model digest, **zero drift in the
scientific-input hash across the whole run**, and all 23 results reconstruct exactly by
re-scoring the raw content.

**Two purpose-built corpora have now been lost to saturation in a row** -- eval001 at mean
accuracy 0.961, and this one at 1.000 against a predicted 0.556. All three tied-hardest tasks
and every convention trap were answered correctly. The difficulty estimates, all marked
`PREDICTED_NOT_MEASURED`, carried no signal.

**The transferable finding is that headroom is a function of the completion budget.** On the
same tasks with the same model at temperature 0: at 4096 tokens the probe truncated and
`v1b_06` returned **zero characters of content**; at 8192 the model scored 23/23. The
reasoning trace alone costs ~3,000-4,000 tokens. Below ~5,000 the corpus floors on a
measurement artefact; above it, it ceilings. A corpus must be calibrated **at the budget it
will be run at**, and a difficulty estimate that ignores the completion budget is not an
estimate of difficulty.

Recorded plainly: the v1.2 -> v1.3 budget raise was necessary (4096 produced no answer at
all) and is also what moved this corpus from floor to ceiling. Both changes were committed
before any scientific call, but the budget decision and the saturation outcome are causally
linked.

**Where the value landed.** The measurement returned no signal; the pre-run work returned
four demonstrated scorer/prompt defects, two harness defects, one excluded task, and 24/24
independently re-derived answer keys. Had the corpus not saturated, the run would have
proceeded on a scorer that mis-scored exact-form answers **differentially by arm** -- which
could have produced a confident, wrong verdict.


**DEVELOPMENTAL PROTOCOL v1.3 — v1.2 WAS FALSIFIED BY ITS OWN PROBE, AND FOUR HARNESS
DEFECTS WERE FOUND AND FIXED. NO SCIENTIFIC CALL HAS BEEN MADE.**

The operational probe ran the two pre-declared tasks at v1.2's 4096-token allowance and
**both truncated**. The cause is a model property v1.2 did not account for: `gemma4:31b` is
a reasoning model whose thinking trace is billed to `completion_tokens` but returned in a
separate field. On `v1b_06` the trace consumed the entire allowance and returned **zero
characters of content** — an absent answer, which is exactly the artefact the amendment
exists to prevent, reproduced one rung lower.

- **Allowance raised to 8192 per call / 16384 per arm**, identically in both arms.
- **Runtime reconfigured to `1 x 32768`** — the mission's stated contingency. Total KV
  context is unchanged (`16384 x 2` → `32768 x 1`), so it costs no memory; it trades
  parallelism for slot size. Digest re-verified after restart.
- **Four harness defects, demonstrated and repaired** (all independently reproduced before
  any change): **D1** the *first* `<ANSWER>` span was scored rather than the last, which
  penalised the second call exactly when it worked; **D2** the first number-like substring
  was mined out of the answer, so `16/7 → 16.0` and `ln(5/2) → 5.0` — a **differential**
  error, since a formal arm is likelier to write exact forms, so it fell on the treatment;
  **D3** a reply with no marker was scored against its whole text, so
  `"flipped 10 times … Var(H) = 2.5"` scored **correct** against key 10; **D4** SE carried
  its whole first reply into call two while HML carried only the extracted fence, which
  handicapped the treatment and contradicted the design's own claim that the arms "differ
  in exactly one respect".
- **`v1b_11_negation_scope_choice` excluded** for a pre-run defect: its options are not
  mutually exclusive and the choice scorer cannot accept an explained answer. **23 valid
  paired tasks remain against a required 20.**

Previously: **DEVELOPMENTAL PROTOCOL v1.2 COMMITTED; THE DECISIVE SE-vs-HML-V1 RUN IS ARMED BUT NOT YET
RUN.** The 24-task benchmark has an amended runtime budget, a crash-safe driver, and two
pre-run defects fixed. No scientific call has been made at the time of this commit.

- **Amendment (`docs/evaluation/V1_PROTOCOL_AMENDMENT_v1_2.md`).** Per-call completion
  allowance 1024 → **4096**; total per arm 2048 → **8192**; applied identically to both
  arms. Everything else — temperature 0.0, model digest, two calls, task set and order,
  scorer, matched information, matched revision — held exactly as frozen. 1024 was unsafe
  because eval001 truncated 11 of 285 completions at a **2400** cap, and a truncated
  completion is an *absent* answer scored as a failure of the representation. HML must emit
  a module *in addition to* its reasoning, so it is the more verbose arm by construction and
  the artefact would have been **anti-correlated with the treatment**.
- **The recorded runtime was wrong.** `arms.RUNTIME` says `4 x 8192`; the live server runs
  `OLLAMA_NUM_PARALLEL=2 OLLAMA_CONTEXT_LENGTH=16384` — a **`2 x 16384`** arrangement. The
  measured value is now recorded and the driver refuses to start if the server disagrees.
- **Context fit is measured, not estimated.** Ollama 0.32.5 has no tokenizer endpoint, so
  envelopes were measured with `max_tokens=1` calls (which cannot collide with scientific
  cache keys). Worst case is HML repair at **10,857 of 16,384**, leaving 5,527 tokens spare.
  **The two-slot arrangement fits; the 32,768 single slot is not required.**
- **Defect fixed — unbounded compiler diagnostics.** `classify_diagnostics()` renders without
  bound: 200 lines of garbage HML produce **389,426 characters (~130,000 tokens), a 122×
  blowup** that overflows *any* slot. It would have truncated the repair prompt hardest
  exactly where the model wrote the worst HML — again anti-correlated with the treatment.
  Capped at 6,000 chars / 40 diagnostics with an explicit omission notice. The cap can only
  *remove* help from the treatment arm, so a positive HML result under it is a lower bound.
- **Defect fixed — no crash safety.** `pipeline.run_benchmark` held all results in memory and
  interleaved the arms, making the SE-first headroom gate impossible. Replaced by
  `evaluation/v1_benchmark/driver.py`: write-once records, immediate save, resume-missing-only,
  immutable manifest, source-level drift hashing over tasks/prompts/scorer/compiler/extraction,
  halt on truncation and on transport error.

Previously: **eval001 IS SATURATED AND UNUSABLE FOR H2 — HEADROOM_INSUFFICIENT (complete, 285/285).**
The plain-English headroom screen (95 deduplicated problems x 3 seeds, temperature 0.7)
returns **mean accuracy 0.961**: **90 of 95 tasks are 3/3 correct** and only **3** fall in
the 1/3-2/3 headroom band against a required 30. **Three of five domains — algebraic,
binding and quantifier — are at 3/3 on every single task**, so they carry no signal at all;
the three headroom tasks are two dimensional and one probability. 92/95 tasks are unanimous
across all three seeds, which makes this corpus saturation rather than sampling noise.
Integrity: matrix complete, 0 duplicates, 0 transport failures, 0 scoring failures, every
prompt hash matching the manifest, one model digest, 11 truncations at the inherited
max_tokens of 2400. The pilot's 93.3% was not an
artefact of its 15-problem sample — the whole corpus is saturated.

This closes a wrong path cheaply and confirms the right one: the purpose-built **24-task v1
benchmark** (`evaluation/v1_benchmark/tasks.py`) is the H2 corpus. Its claims were verified
independently — 24 tasks, mean predicted accuracy **0.556** exactly, all 24 inside the
0.40-0.70 band (range 0.45-0.67), contamination clean against 517 items across 18 corpora,
24/24 carrying independent key verification, and its 3 apparent answer leaks cleared as
multiple-choice letters that necessarily appear in their own options.

Previously: **PYRIGHT CONFIGURED; ONE STALE RE-EXPORT CLOSED.** The repository had no Pyright
configuration at all, so 126 of 484 baseline diagnostics were unresolved imports of
installed packages — and every file carrying one was analysed against a partly-blind view.
Configuring the environment truthfully (no mode weakened, nothing excluded that matters)
drops the count to 374. One confirmed runtime defect is fixed: `hamiltonian_lang.
verification.__all__` named `obligations` without importing it, so attribute access raised
and `import *` bound nothing; a test now walks every package and asserts each `__all__`
entry exists. The remaining 374 are largely untriaged — see
`docs/audits/PYRIGHT_OVERNIGHT_AUDIT.md`.

Previously: **CAP_CALIBRATION_FAILED — THE SURVIVOR RERUN IS BLOCKED, AND A BIGGER CAP IS NOT THE
FIX.** Both cap probes at 12,288 reached the cap exactly and truncated, on the same task
that truncated at 6,144. The transcripts show why: the model restates the module header
**229 times** in surface A and **161 times** in surface C, cycling on the identifier
`varrho` which it repeatedly mistypes as `vvarrho` and restarts over. Two allowances a
factor of two apart, both fully consumed, with the repetition count scaling with the
budget — that is non-termination, not an undersized budget. The proposed 1 x 32,768
configuration is recorded as required but is **not recommended**: it predicts ~500
restatements, still truncates, and costs ~10 hours at halved concurrency. It is one task,
not one surface: the other seven surface-A tasks finished with `stop`, and this task
completed cleanly in surface B.

Previously: **TRANCHE A VOID ON TRUNCATION; SURFACE D ELIMINATED BY UPPER BOUND.** The 32-condition
run completed and is `MEASUREMENT_INVALID` (D-033). Everything except the cap audited clean:
matrix complete 8x4, no duplicates, no missing, 0 transport failures, no prompt drift, no
bundle drift, no repository mutation during measurement. Three conditions hit the 6,144-token
completion allowance, and the truncation decides the verdict for two of four surfaces, so no
surface-selection or continuation decision is derived from it. All 32 records are preserved
with a hash manifest, admissible for debugging only.

**Surface D is eliminated without a rerun**: repaired parse 0/8, one truncated record and
only in repair, so the best attainable count is 1/8 against a frozen 6/8 threshold. Its
failure class is schema conformance — every attempt emitted a *triples* encoding where the
candidate specifies a `statements` array, and all failed at import, none at the compiler.

Previously: **MEASUREMENT_INSTRUMENT_GREEN; TRANCHE A RUNNING.** All green conditions hold: 12/12
development tasks and 2/2 spares admitted, view-only reconstruction 14/14, round-trips
56/56, leakage clean with a firing negative control, mutation controls firing, full tests
and conformance passing. Green means **suitable for a developmental model experiment** — it
does not mean officially human-approved, promotion-ready, or mathematically exhaustive.

The prompt budget is re-measured against the frozen runtime (`-c 32768 -np 2`, slot 16384,
completion 6144, reserve 256, ceiling 9984) with the **same builder the run uses**: worst
case A 3177 / B 3179 / C 3329 / D 5056 tokens, all four fitting with 4928–6807 headroom.

**One harness defect was found by the first Tranche A attempt and the attempt was
discarded.** Candidate C's own specification advertises the fence tags `sexpr`, `lisp` and
`scheme`; the model answered inside a ```lisp fence with a **hash-identical** encoding, the
raw text went to the importer fence and all, and the import failed. Surface C would have
been eliminated on a harness bug reported as a property of the notation. The scorer now
strips any fence, with a regression matrix over every surface and seven tags.

Previously: **ACQ0 v2 DEVELOPMENT CORPUS ADMITTED — 12 TASKS + 2 SEALED SPARES.** The taxonomy is
frozen at twelve feature cells (`docs/evaluation/ACQ0_V2_TAXONOMY.md`), all twelve covered,
every coverage rule met. Two independent read-only reviewers examined the corpus in two
rounds and returned **0 WRONG and 0 REJECT**; all eight of their findings were repaired at
the **generator**, never at an individual answer, and each has a regression test.

The binder-only partiality guard is replaced by an **AST scanner** that walks every
expression position and follows definition dependencies — module variables, compound
denominators, negative and fractional powers, variable exponents, `sqrt`/`log`/`tan`,
indexing, and partiality one or two `def`s deep — reporting a named risk path and failing
closed. It marks a dimensioned denominator **UNGUARDABLE**, because `require area != 0`
does not compile (HML-D502).

Three defects the reviewers found were in the governance layer rather than in any task:
`build_bundle` still served the retired bucketed target; `structured_target()` dropped
`CheckStmt` everywhere downstream, so the semantic diff scored a dropped `check` as unequal
with an **empty difference list**; and the objective was stated twice in prose in a form
that compiles to a different hash. `structured_target()` now raises — the fact layer, the
prose generator and the semantic diff all read one traversal.

Previously: **ACQ0 v2 MODEL-VISIBLE VIEW REPAIRED.** A line-by-line
English-versus-formal review of all eight tasks found that the artefact handed to a model
was insufficient to produce the reference. `structured_target()` partitioned each module
into unordered kind-buckets while `content_hash` is order-sensitive, so three tasks were
unencodable; a fourth dropped its `check dimension` statement entirely because the function
had no `CheckStmt` branch. Two further tasks were mathematically defective — a one-sided
bound in the approximation family, and an unguardable division by a module-level `var` in
the dimensional family.

The repair is generator-level, not answer-level (D-030). The model now receives one ordered
`encoding_statements` list with explicit `emit` flags, prose follows encoding order, and
**admission requires that the view alone reconstruct the reference**: view → rebuild →
compile → `content_hash` equality. That gate is the first check in this project that crosses
the boundary where the loss occurred — the three previous checks each validated an artefact
against itself. It is now **8/8 exact**, with the two defective tasks replaced under fresh
ids and preserved. **No task is marked human-approved; that decision is not automatable.**

Previously: **ACQ0 v2 AUDIT COMPLETE; MODEL TESTING PAUSED.** All hardening sections executed. Five defects were found in v2 itself and fixed: metadata outside identity, unguarded partiality, a self-contradictory `state_in_prose` classification, an ambiguous omitted codomain, and a leak check that could not fail. Prose coverage 8/8 exact, reversibility 8/8, round-trips 32/32, firewall enforced.

Previously: **ACQ0 v2 HARDENED.** The hardening audit found two defects in v2 itself: semantic metadata sat outside canonical identity, and an unguarded partial definition was admitted. Both fixed; `canonical_hash` (encoding identity) is now distinguished from `semantic_identity` (task identity). Audit sections C, F, H, I, J remain incomplete.

Previously: **ACQ0 INSTRUMENT REBUILT (v2).** The v1 41-task corpus is quarantined `INVALID_INSTRUMENT` (0/41 admissible): mathematics was authored in three independent places and disagreed, so a frontier model that followed the prose was scored FAIL. `CanonicalAcq0TaskV2` makes one object the authority and derives every artefact from it; 8 proof tasks are admissible with exact round-trips through all four surfaces. Both protocol calibrations (v1 completion-cap, v2 invalid corpus) are void; no protocol has been validly selected.

Previously: **M2 CONTEXT BUDGET MEASURED.** Selected shared runtime `4x8192`, curriculum size 5, measured `prompt_eval_count`: A 1880 / B 1887 / C 2074 / D 4907 / SE 1829 against a 5888 ceiling. Worst case D, 981 tokens headroom (16.7%), full 2048 allowance and 256 reserve intact, zero truncation. The tokeniser beats 2.48 ch/tok everywhere, so candidate D is NOT eliminated on budget.

Previously: **M1.5 INTEGRATION.** All four resumed agents returned. Two blocking soundness defects found by an independent falsifier are closed (D-026 unsound VERIFIED behind a `def`; D-027 false-positive equivalence under a spare rename). Suite **4927 passed**, `CONFORMANCE: PASS`.

Previously: **RECOVERY.** Three subagents terminated on an API session limit mid-write. The dirty tree (152 files) is preserved verbatim on `recovery/session-limit-2026-08-05`; see `docs/evaluation/SESSION_LIMIT_RECOVERY_MANIFEST.md`. State at capture: **4721 passed**, `CONFORMANCE: PASS`. Four subsystems returned gate verdicts; three (Chain-of-Repair, format protocol, benchmark governance) are **INTERRUPTED and unaudited** — each stopped while writing its own tests, so their controls are the parts most likely missing.

**HML-CONSTITUTIONAL-CORE-001 — installing recursive improvement as a constitutional
subsystem.** Phase 0 baseline is recorded in
`docs/evaluation/CONSTITUTIONAL_CORE_BASELINE.md`. The compiler is the semantic truth
kernel; the new subsystem is an improvement control plane. Governing law: *models and
agents may propose changes; only external verification and controlled evidence may change
the official system.* After the constitutional baseline is frozen, every experimental
transition must change exactly one major state component (`|ΔS|₀ = 1`).

**Four identifiers are now maintained separately: ACQ0 (prerequisite), H1, H2, H3.** ACQ0 asks only whether the model can *write* the language; it is not evidence for any hypothesis, and its repair mechanism is `ACQ0_REPAIR`, not H3. See `docs/evaluation/HYPOTHESIS_REGISTER.md` and `evaluation/manifests/hypotheses.json`.

**H1, H2 and H3 are held apart mechanically, not by convention.** `Episode.hypothesis_id`
and `EvidencePackage.hypothesis` are typed values; episodes from different hypotheses may
not be aggregated; the controller may not advance a stage on evidence from a hypothesis its
gate does not name. **A win on H3 alone is a win for verifier-guided reasoning and must
never be reported as a win for the representation.** All three remain **UNTESTED**.

**F2/F3 ownership: resolved, no conflict existed.** `evaluation/syntax_gate/candidates.py`
is a binding layer over `evaluation/syntax_acquisition/`, not a second renderer. All four
candidate surfaces round-trip to **hash-identical** canonical objects on four examples, so
no candidate receives additional mathematical information.

Previously: **HML-PHASE-FG-001 — freezing the supported V1 subset and preparing the Gemma syntax
tournament.** Phases F1 (freeze-eligibility audit), F2 (fair benchmark partition) and F3
(offline equivalence gate) are in progress. No model call is legitimate until the offline
gate passes and the Lead tags `hml-v1-eval-freeze`.

Host tuning is measured and recorded in `docs/evaluation/EXECUTION_ENVIRONMENT.md`: stock
Ollama serialises every request at one slot (~23 tok/s regardless of client concurrency);
four batching slots with exactly four client workers give **2.08x**, and eight workers
*degrade* to 1.43x. The 18 CPU cores do not accelerate a GPU-resident 31B model — they
accelerate the offline round-trip matrix and the test suite (13.3s to 6.5s). The largest
curriculum (50 demonstrations, 5,893 prompt tokens) fits the 8192-token slot, so that
configuration is safe for the whole tournament.

The F4 freeze is **enforceable, not declarative**: `evaluation/syntax_gate_freeze.py
--verify` recomputes every hash and exits non-zero on drift, hashes frozen trees wholesale
so an added file also counts, and pins the model by digest rather than by its reassignable
tag. **The tournament has not been run. Nothing about syntax acquisition is yet known.**

**HML-EVAL-002 preregistered; V1 implementation in progress.**

**Status of the central thesis: UNPROVEN, NOT REFUTED.** The precise conclusion from the
pilot is: *zero-shot Hamiltonian did not improve answer accuracy on this small,
low-discrimination pilot; the experiment was underpowered and had a severe ceiling effect.*
A correction is recorded in `V1_GATE_DECISION.md` — an earlier version of that document
said "refuted", contradicting this project's own pilot report §9. The report was right.

The checker is a **component of a verifier-guided reasoning system (H3)**, not the
objective. The earlier drift toward treating it as the product is withdrawn.

Previously: **V0 closed and preserved; V1 in design.** V0 is tagged `hml-v0-baseline` — the language,
the frozen spec, and 221 stored model trials. `src/` does not change under that tag.
**Hamiltonian V1: Discourse, Transformation and Epistemics** is specified in
`docs/design/V1_KERNEL.md` with a preregistered comparison plan in
`docs/design/V1_EXPERIMENT_PLAN.md`. Nothing of V1 is implemented.

Previously: **HML-EVAL-001 — empirical evaluation phase.** v0 is frozen at tag `hml-v0-eval-freeze`.
No new language features, domains, or abstractions are being added. The sole objective is
to test whether a model reasons better through Hamiltonian Lang than through English,
structured English, LaTeX, or an existing formal representation.

## Current Branch

Active development: `feature/hml-reasoning-kernel-v2` (worktree
`/Users/moheet/hml_v2_worktree`, based on `3dd4216`, now carrying the CI repair `ff915ad`
and the Representation Arena). The scientific integration branch
`integration/m1.5-paper-derived-closeout` is unchanged and was not merged into.
The language-audit worktree `/Users/moheet/hml_audit_worktree` is read-only evidence.
V0 preserved on `main` at tag
`hml-v0-baseline`; the interrupted state is preserved on
`recovery/session-limit-2026-08-05`. Repository is private.

## Current System Architecture

Three layers, one identity:

1. **Surface** — HML-L1: ASCII-canonical, line-oriented, role-labelled, `end`-delimited.
2. **Semantic core** — typed AST + symbol table + proof obligations. The only source of
   truth. `src/hamiltonian_lang/ast/nodes.py` is the frozen contract.
3. **Backends** — projections: HML, canonical JSON, semantic graph, triples, LaTeX,
   controlled English, Stan, SymPy, Lean statement skeletons. Every one reports its own
   translation loss; **no example is faithful under Stan, SymPy or Lean**, and each says so.

Pipeline: source → lexer → parser → name resolution → type checking → canonical form →
views. Source spans are preserved through every stage.

## Capabilities Implemented

- Scalar refinement **poset** (`Probability` and `PositiveReal` incomparable, meeting at
  `NonNegativeReal`; `PositiveNatural` as their meet with `Natural`)
- Structurally distinct `T`, `RandomVariable[T]`, `Distribution[T]` with no subtyping path
- Rational-exponent dimensional algebra over seven SI base dimensions, exact and decidable
- Shape checking for `Vector`, `Matrix`, `Tensor`, including matrix-vector inner extents
- Lexer with ASCII canonicalisation and Unicode folding (μ U+03BC and µ U+00B5 both fold
  to `mu`, warned)
- Recursive-descent parser, LL(1) at statement level, non-cascading error recovery
- Name resolution with stable `SymbolId(name, ordinal, depth)`; shadowing rejected;
  order-independent module scope
- Distribution registry with **mandatory role labels** and targeted diagnostics for known
  misparameterisations (scale-vs-variance, rate-vs-mean, `n`/`p`, `a`/`b`)
- Proof-obligation collection — constraints, assumptions, theorems, concept invariants,
  and standing positivity requirements
- Canonical JSON + SHA-256 content hash: invariant under renaming, sensitive to quantifier
  order and role assignment
- Semantic graph with a closed edge vocabulary; triple output; transitive dependency query
- `hml` CLI: `check render canonical hash graph obligations views`
- **Representation Arena (`arena-1.0.0`)** — a structure-first neutral world factory over
  three families, three renderers (SE / generic AST / HML), a decoder per arm proving
  information parity by round trip, three endpoints (next-action, paired minimal contrast,
  corruption), a truncation-aware scorer, a token-budget instrument and an eight-check
  pre-flight gate. Every HML rendering compiles under the real compiler.

## Work Completed to Date

Repository initialised from `MoheetBrain/hamiltonian-lang` (which contained only a
README). Full directory structure, governance documents, ten agent definitions, five
project skills, deterministic conformance script, git hooks and CI created. Semantic
kernel, compiler and core backends implemented by the Lead Architect. Four subagents run
against isolated file ownership.

## Important Files and Artifacts

| file | role |
|------|------|
| `GOAL.md` | project thesis |
| `docs/design/V0_DESIGN_FREEZE.md` | the frozen v0 contract |
| `SPEC.md` | normative language reference |
| `DECISIONS.md` | D-001..D-032 with reversal costs |
| `docs/evaluation/ACQ0_V2_TAXONOMY.md` | **the frozen 12-cell taxonomy and feature matrix** |
| `docs/evaluation/ACQ0_V2_INDEPENDENT_SEMANTIC_REVIEW.md` | both review rounds, compact |
| `evaluation/corpus_governance/partiality.py` | **the AST partiality scanner** |
| `evaluation/acq0/v2/prompt.py` | the one frozen prompt builder |
| `evaluation/acq0/v2/run.py` | the Tranche A driver and preregistered gates |
| `evaluation/corpus_governance/canonical_v2.py` | **the single ACQ0 authority** |
| `evaluation/corpus_governance/v2_view.py` | **the ordered view and the admission gate** |
| `evaluation/corpus_governance/v2_render.py` | every model-visible artefact, all derived |
| `evaluation/corpus_governance/v2_corpus/tasks.py` | the eight proof tasks |
| `docs/evaluation/ACQ0_V2_HUMAN_REVIEW_PACKET_R2.md` | **private review packet — never model-visible** |
| `evaluation/results/acq0/superseded_tasks/SUPERSEDED.md` | withdrawn tasks, with reasons |
| `benchmarks/eval001/` | 120-problem corpus, 7 arms, 840 prompt files |
| `evaluation/harness.py` | model-evaluation harness |
| `evaluation/analyse.py` | paired intervals, McNemar, effect sizes |
| `docs/evaluation/HML_EVAL_001_PILOT_REPORT.md` | **the pilot result and decision** |
| `docs/design/V1_KERNEL.md` | **V1 five-layer design** |
| `docs/design/V1_EXPERIMENT_PLAN.md` | preregistered V0-vs-V1 plan |
| `spec/v1/semantic_objects.yaml` | V1 objects, machine-readable |
| `evaluation/results/EVAL_SPEC_v1.1.json` | frozen spec + defect record |
| `docs/evaluation/PRE_EVALUATION_AUDIT.md` | verified state before the experiment |
| `audits/RED_TEAM_REPORT.md` | adversarial review |
| `src/hamiltonian_lang/ast/nodes.py` | **frozen IR contract** |
| `src/hamiltonian_lang/types.py` | the type lattice |
| `src/hamiltonian_lang/type_system/distributions.py` | distribution roles |
| `spec/ir.schema.json` | canonical form JSON Schema |
| `scripts/conformance.sh` | deterministic gate |
| `docs/research/PRIOR_ART.md` | prior-art and novelty analysis |

## Data Sources and Provenance

No external data. The seven reference examples are authored from the master directive.
Prior-art licence claims were verified from canonical sources during Wave 1 and are
recorded in `docs/research/PRIOR_ART_MATRIX.csv` with an explicit UNVERIFIED register.

## Decisions and Rationale

D-001..D-021 in `DECISIONS.md`. Load-bearing ones:

- **D-003** mandatory role-labelled distribution arguments. Prior art shows the
  *mechanism* is not novel (PyMC, SciPy already use named parameters); the delta is that
  labels are mandatory rather than conventional.
- **D-004** the scalar order is a poset, not a chain. Linearising it would admit unsound
  programs.
- **D-005** hybrid binding: readable names, structural identity.
- **D-012** the claimed contribution is demoted from the representation to the experiment.
- **D-014** the frozen alphabet and grammar survive measurement across 8 real tokenisers.
- **D-016** eight adversarial defects found and fixed; all eight are now rejected with a
  named diagnostic code.
- **D-017** interface names (concept parameters, distribution roles) are meaning; only
  local binders are alpha-renameable.
- **D-018** a green property test is only evidence about the inputs its generator
  actually reaches.
- **D-019** the lexer did not terminate on non-ASCII letters; it would have hung the
  evaluation harness silently rather than failing it.
- **D-020** the five inference queries do not share a precondition; requiring a law for
  `mle` rejected the most common frequentist model in statistics.

## Verification and Test Results

**Current run — 2026-08-08, the Representation Arena commit.** Executed, not estimated:

| check | exact command | result |
|---|---|---|
| full suite | `.venv/bin/python -m pytest -q` | **6442 passed**, 5 skipped, 7 xfailed, 7 xpassed, **0 failed** |
| arena tests | `.venv/bin/python -m pytest -q tests/arena` | **100 passed**, exit 0 |
| arena pre-flight gate | `.venv/bin/python -m evaluation.arena.validate` | **exit 0, all 8 checks PASS** — 306 items, 69 pairs |
| arena lint | `.venv/bin/ruff check evaluation/arena tests/arena` | **All checks passed** |
| representation parity | 600 worlds x 3 arms | **1800 round trips, 0 failures** |
| HML arm compiles | 214 worlds, real compiler, inside the gate | **214/214** |

Baseline immediately before the arena was 6342 passed; the delta is exactly the 100 new
tests. Arena prompt budget (`cl100k_base`, 306 items): SE **328.8** mean tokens, HML
**338.0**, AST **576.3** — SE and HML within 2.8%, the AST control 1.75x the shortest arm.

`ruff format` was **not** run and is not claimed: the repository is not format-clean (146 of
220 files would be reformatted), so reformatting only the new files would make them
inconsistent with the tree.

**Earlier run — the repaired model-visible view, 2026-08-06.** Every number below was
executed, not estimated:

| check | result |
|---|---|
| `pytest` (full suite) | **5300 passed**, 4 skipped, 7 xfailed, 7 xpassed |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS** |
| `ruff check src tests evaluation/` | **All checks passed** |
| `mypy src` | **Success: no issues found in 84 source files** |
| view-only reconstruction (**the admission gate**) | **8/8 exact** |
| every emitted statement present exactly once | **8/8** |
| A/B/C/D surface round-trips | **32/32 exact** |
| reference self-score | **8/8** |
| `audit_task` admission | **8/8 admissible, 0 defects** |
| ACQ0 / H2 view separation | 8/8, `assert_views_distinct` raised nothing |
| model-safe bundle leak scan | 8/8 clean |
| `tests/evaluation/test_acq0_view_reconstruction.py` | 50 passed, incl. 9 negative controls |

The negative controls matter more than the pass counts: the gate is asserted to **fail** on
a removed statement, a swapped order, a swapped `assume`/`require` role, a dropped dimension
check, an emitted derived fact, an invented goal, and a missing initialiser, body or
codomain. Each is a defect that actually occurred or a near neighbour of one.

Commands executed and their real results (historical, cumulative):

| command | result |
|---------|--------|
| `.venv/bin/python -m pytest -n 18` | **3974 passed, 4 skipped, 1 xfailed** (was 1531) |
| `./scripts/conformance.sh` | **PASS without override** (all four V1 agents integrated) |
| `evaluation.analyse --generation 0` | 105/105 cells; all arms 93.3% except C 86.7% |
| `.venv/bin/hml check examples/*/*.hml` | **8/8 check cleanly** |
| `pytest tests/golden/test_examples_compile.py` | **23 passed** — recursive example gate |
| Ollama concurrency probe, stock `-np 1` | 23 tok/s at 1, 2, 4 and 6 workers — fully serialised |
| Ollama concurrency probe, `-np 4` | 22.8 / 35.1 / **47.4** / 32.7 tok/s at 1 / 2 / **4** / 8 workers |
| curriculum probe, `prompt_eval_count` | 0/5/10/25/50 demos = 66/643/1286/2967/**5893** tokens; all fit the 8192 slot |
| `pytest tests/freeze/test_syntax_gate_freeze.py` | **22 passed, 1 skipped** |
| `python -m evaluation.syntax_gate_freeze --verify` | correctly reports nothing frozen yet, exit 1 |
| four-surface hash round-trip | **MATCH on all 4 candidates x 4 examples** |
| `pytest tests/freeze` | 75 passed (52 quarantine + 23 freeze tooling) |
| `.venv/bin/ruff check src tests` | **All checks passed** |
| `.venv/bin/mypy src/hamiltonian_lang` | **Success: no issues found in 22 source files** |
| `experiments/alphabet/tokenisation_benchmark.py` | ran; 8 tokenisers real, Llama-3 gated and excluded |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS** (all 8 stages) |

Test breakdown: backends 292 · golden 84 · adversarial 71 · roundtrip 65 · type_system 39 ·
parser 37 · semantics 21.

Property-based tests (hypothesis) cover alpha-renaming invariance and inconsistent-rename
detection, parameterised over **every** binder form with a companion test asserting each
template actually compiles. This followed D-018: the earlier generator was green while the
property it asserted was false, because it never produced `def` parameters.

## Known Failures and Limitations

**Representation Arena — what it does not establish.**

- **Zero model calls. Nothing in the arena is evidence about any model's behaviour.**
- **HML has no uninterpreted predicate.** A declared `Predicate` is not callable
  (`HML-T470`); the only callable form requires a body. A finite relation can therefore only
  be stated in closed form, which forced all three arms to state it once in their own idiom
  rather than by enumeration. An ontology gap independent of the arena.
- **The AST control carries a length penalty** — 576 mean tokens against SE 329 and HML 338.
  An HML > AST result therefore cannot yet be attributed entirely to HML semantics.
- **The HML renderer had a latent semantic defect caught only by parity.** A relativised
  nested quantifier parsed and meant the right thing solely because `implies` is
  right-associative; nested quantifiers are now bracketed. Compiling was not sufficient to
  detect it.
- **`MIXED_STATE_COMPOSITION` is not ported**, and next-action covers two families rather
  than three. All three ported families sit inside HML's covered ontology region, so the
  handoff's structural tension — the families where the tested model is weak are the
  families where HML's coverage is near zero — is untouched.
- **`OPERAND_ORDER` contrast twins have answers that are exact negations** of each other.
  Not exploitable within an independently scored item, but a corpus-level analysis should
  know it.

- **The ACQ0 instrument has now failed its own audit twice.** v1 was 0/41 admissible
  because the mathematics was authored in three places and disagreed. v2 was built to
  remove that failure mode and still shipped a model-visible view from which three of eight
  tasks could not be encoded, plus a fourth whose `check dimension` statement appeared in no
  model-visible artefact. The lesson is specific and unresolved in general: **three separate
  "verifications" all validated an artefact against itself.** Only a check that crosses the
  boundary where information is lost can detect that class of defect.
- **No model has seen any v2 task.** Every property recorded for v2 is a property of the
  instrument, not an observation about model behaviour.
- **The partiality guard is narrow and fails closed.** The compiler generates no definedness
  obligation over a binder's declared domain, so admission rejects division by a **bare
  binder** only. Compound denominators, `sqrt`, `log`, negative or fractional powers,
  indexing, and partiality reachable through a chain of definitions are **not** detected.
  `v2_dimensional_algebra_001` divided by a module-level `var`, which sits outside that
  reach entirely; it was replaced rather than guarded, because `require area != 0` does not
  compile (HML-D502 — a `Quantity[Length^2]` is not comparable to a dimensionless `0`).
- **HML has no absolute-value form**, so a two-sided bound must be written as two explicit
  inequalities. `v2_approximation_equality_001` stated one and was therefore satisfiable by
  an estimate arbitrarily far below the target.
- **The pilot found no representation advantage *on a saturated benchmark*.** Every paired
  contrast was exactly zero with zero discordant pairs — but 14 of 15 problems were solved
  by nearly every arm, so the design could not have detected an effect of realistic size.
  This is not evidence of absence. Encoding fidelity was 0.648 and 27–50% of encodings did
  not compile.
- **Two blocking gates precede any HML-EVAL-002 reasoning result:** parse success ≥95%
  after at most one repair with ≥90% semantic preservation, and a benchmark of ≥200
  problems at 40–70% baseline accuracy.
- **Phase 5 is partly blocked:** only `gemma4:31b` is installed; the 7–14B non-reasoning
  arm needs a model download.
- **Phase 6 is blocked:** no training stack exists (torch, transformers, peft, datasets,
  trl, accelerate all absent). Recorded as blocked, not dropped.
- **The pilot was underpowered.** 14 of 15 problems were answered correctly by every arm;
  the design could only detect an effect of roughly 33 percentage points. The zero
  differences are not evidence that no difference exists.
- **The one positive signal:** compiler feedback raised encoding fidelity by +0.065
  (CI [0.006, 0.136]) and parse rate by 12–43 points across both generations, at +38%
  generated tokens. It did not change answer accuracy at all.
- **Round trips now measured, not assumed** (HML-EVAL-001 §9). Four routes implemented
  with explicitly declared narrow subsets: canonical IR (5/5 in-subset fixtures preserve
  the content hash), graph triples (2/2), Stan (2/2), Lean statement subset (2/2). What
  the measurement revealed matters more than the pass counts:
  - **Stan cannot express strict positivity.** `real<lower=0>` admits 0; `PositiveReal`
    does not. Every family with a `PositiveReal` role — Normal, Beta, Gamma, Exponential,
    Poisson, Cauchy and most others — therefore cannot round-trip at all. Only Uniform,
    Binomial and Bernoulli can.
  - **Stan loses observed values** (data comes from a data file, not the program text)
    and **destroys interleaved declaration order** (block structure), which changes the
    content hash because ordinals are positional.
  - **The Lean route silently loses probability laws**, and the reconstruction compiles
    perfectly happily. Only the content-hash comparison detects it. A one-way test cannot
    detect this class of loss at all.
- **`BackendResult.faithful` means "declared no per-construct loss", not "round-trips".**
  `english`, `json`, `graph` and `triples` report `faithful=True` while being one-way.
- **Every recorded benchmark number is a deterministic compiler property.** None is a
  model-performance observation.
- **No structural novelty was found in Layer 2.** Wave 1 prior-art review identified prior
  implementations of every representational claim. See D-012.
- **Provenance is not implemented** (D-011). The IR carries spans and types only.
  `GOAL.md` §5 originally claimed otherwise and has been corrected in place.
- Proof obligations are collected and, apart from dimensional checks, **not discharged**.
  This is by design; v0 proves nothing.
- Role-label discipline applies to `DistExpr` only, not to ordinary `Call`s (Q-05).
- The freeze document previously claimed the sd-vs-variance ambiguity "cannot be
  expressed". That was false as written: the *grammar* admits
  `Normal(location := mu, variance := s)` and the *type system* rejects it. Corrected
  (D-014).
- Statement order affects declaration ordinals, so reordering differently-typed
  declarations changes the content hash. Whether this is right is unresolved.

## Risks and Technical Debt

- **Out-of-distribution confound** — arms A–D are saturated in model pretraining; arm E has
  effectively zero tokens. This may dominate every comparison. Now recorded as falsification
  condition 6 in `GOAL.md`.
- **Published evidence points the other way** — Tam et al. (EMNLP 2024) report reasoning
  degradation under format restriction. Now recorded as falsification condition 7.
- **Scaffolding confound** — if English plus structural prompting closes the gap, the win
  is prompting, not representation.
- **D-006 (shadowing as an error) may be too strict** for practical authoring.
- **OpenMath IPR status is unresolved** (Q-03), blocking the highest-value reuse option.
- **The strongest argument against the project**, adopted rather than rebutted: the
  inference the thesis wants to eliminate happens when the file is *written*, not read.
  Someone had to decide `jitter` is a scale before `scale := jitter` could be typed. A
  correct-looking encoding of a misunderstanding compiles clean and is wrong. Reviewer's
  ESTIMATE: arm A' (prose + matched checklist) closes most of the gap.
- **One confound is not resolvable**: "structured formal notation helps" cannot be
  separated from "*this* notation helps", because Lean and Stan are far better represented
  in pretraining than a language invented weeks ago.

## Current Blockers

- **No official human review has happened.** `INDEPENDENT_SEMANTIC_REVIEW` is two
  read-only agent reviews, and is labelled as such. It clears the developmental screen; it
  does not clear a promotion benchmark.
- Q-03 (OpenMath licensing) blocks a reuse decision, not the build.

## Exact Next Actions

**The signal pivot supersedes the ordering below.** Broad compiler completion is
deliberately not resumed. The live sequence is:

0. **Acquisition sanity check, then the Endpoint-B pilot.** The organism is frozen. Run 6 literal state-recovery items per arm on ACQUISITION seeds; require >=5/6 for AST and for HML before any pilot. Then 12 fresh PILOT pairs, SE/AST/HML.
1. ~~Find difficulty other than model size.~~ Superseded for this organism, but still open for the endpoint: Endpoint B at L3
   is saturated at 8B, so the pilot cannot run there. Re-screen SE-only at **L5**, then L7
   if needed, looking for a level where `gemma4:e4b` lands in 30–70% pair both-correct.
   Endpoint A (next-action) is the other candidate for headroom and has never been run
   against any model. Both are cheap: a 6-pair micro-screen is 12 calls and ~3 minutes.
1. ~~SE-only developmental model **size** search.~~ **CLOSED by rule.** Two candidates
   consumed: `gemma4:12b` (screen void — instrument failure, not a verdict on the model)
   and `gemma4:e4b` (6/6 pairs, too strong). `gemma4:e2b` deliberately not tried. The
   constraint that a model be chosen on structured English alone still holds for any future
   screen.
2. **Freeze** model, digest, runtime, instructions, endpoint implementation, generator and
   scorer versions. Generate a fresh held-out seed set.
3. **Acquisition sanity check** — 6 literal state-recovery items per structured arm,
   requiring no reasoning, on throwaway seeds. Require ≥5/6 for AST and for HML, so that
   unfamiliar syntax is not mistaken for a bad reasoning representation.
4. **First Endpoint-B representation pilot** — 12 fresh contrast pairs, SE/AST/HML, fresh
   context per item, deterministic order. No significance claims at N=12.
5. **Endpoint A only if B is non-degenerate.**

The AST length confound (576 vs 329/338 tokens) is recorded and deliberately not yet fixed:
an HML > AST result cannot be attributed entirely to HML semantics until a more compact
neutral control exists. No representation may be truncated to force equal length.

The pre-pivot backlog, retained for the record and **not** currently active:

0. **HML V2 phase II — close the 11 critical coverage zeros.** Expectation as an
   expression, conditional and joint probability, independence, set membership and
   comprehension, limit/derivative/integral/continuity, causal vs associational
   relations. Then rerun the 486-atom capability audit **unchanged** (do not edit the
   ontology) and report BEFORE/AFTER for critical coverage, critical zeros,
   compositional closure, transformation representability and backend silent loss.
   Do not run any HML-vs-English model experiment until V2 is frozen: V1 and V2
   conclusions must not be mixed.

1. **The decisive run, in this order and no other.** (a) 8-call operational probe on the
   largest-envelope and hardest predicted tasks; (b) **SE arm on all valid tasks as the
   headroom gate** — 8–16 of 24 correct is ideal, 6–18 usable, 0–5 or 19–24 insufficient;
   (c) HML-V1 only if the gate passes; (d) paired McNemar + bootstrap; (e) two read-only
   falsification reviewers; (f) `DECISION.json`. The prompt budget re-measurement against
   the frozen runtime is **done** — it is `2 x 16384`, recorded in
   `evaluation/results/v1_benchmark/ENVELOPE_CALIBRATION.json`.

1. Decide the D-003 cost/benefit question now that the token cost is measured at ~5.9%
   (D-014): is the explicitness worth it? This is H5 and is still open.
2. Build the scaffolding-ablation arm **first**, since it is the arm most likely to
   falsify the thesis.
3. Decide Q-05 (role labels on ordinary calls).
4. Run the morphology analysis — deferred in session 1 and a prerequisite for H6.
5. Work through the remaining findings in `audits/RED_TEAM_REPORT.md` that were not
   resolved in session 1.
7. **V1, in order:** redesign the corpus to a 50–60% baseline (n ≥ 60); raise the
   Hamiltonian parse rate to ≥ 90% — **a hard gate, since a language the model cannot
   write is not being tested**; then implement L4 epistemic first, because it has the
   clearest correctness claim and the strictest kill criterion.
6. **Cheapest high-value step, no model needed:** demonstrate HML → Stan → HML and
   HML → Lean → HML preserving the content hash, or characterise exactly where it fails.
   The only round trip verified today is HML → HML, which is the one that cannot lose
   anything.
