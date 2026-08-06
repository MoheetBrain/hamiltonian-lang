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

**eval001 IS SATURATED AND UNUSABLE FOR H2 — HEADROOM_INSUFFICIENT (complete, 285/285).**
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

`integration/m1.5-paper-derived-closeout`. V0 preserved on `main` at tag
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

**Current run — the repaired model-visible view, 2026-08-06.** Every number below was
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

0. Re-measure the prompt budget against the frozen runtime (`-c 32768 -np 2`), then run
   Tranche A: 8 development tasks x 4 surfaces, `DIRECT_FORMAL`, one safe repair maximum.

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
