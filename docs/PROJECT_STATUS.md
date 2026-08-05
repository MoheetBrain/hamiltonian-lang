# Project Status

Snapshot date: 2026-08-04. Maintained per the commit continuity protocol.

## Project Objective

Determine whether an AI-native mathematical representation — compact, typed, semantically
explicit, compositional — measurably improves machine mathematical reasoning,
verification and generalisation relative to ordinary mathematical English, LaTeX,
conventional code, and direct use of existing formal languages.

The project succeeds only if a reproducible advantage is demonstrated on at least one
important mathematical task. **A pilot measurement has now been taken and found no
advantage — see `docs/evaluation/HML_EVAL_001_PILOT_REPORT.md`. The decision is REDESIGN
AND RETEST.** The pilot was saturated at 93% accuracy across all seven arms and had almost
no power, so it is not evidence that no advantage exists.

## Current Stage

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

`hml-v1-concept-kernel`. V0 preserved on `main` at tag `hml-v0-baseline`. No remote
pushes. Repository is private.

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
| `DECISIONS.md` | D-001..D-021 with reversal costs |
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

Commands executed and their real results:

| command | result |
|---------|--------|
| `.venv/bin/python -m pytest -q` | **967 passed, 0 failed, 0 xfailed** |
| `evaluation.analyse --generation 0` | 105/105 cells; all arms 93.3% except C 86.7% |
| `.venv/bin/hml check examples/*/*.hml` | **8/8 check cleanly** |
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

None blocking implementation. Q-03 (OpenMath licensing) blocks a reuse decision, not the
build.

## Exact Next Actions

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
