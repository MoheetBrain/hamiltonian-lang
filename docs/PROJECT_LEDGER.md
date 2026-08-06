# Project Ledger

Append-only. Never rewrite or delete an entry except to correct a demonstrable factual
error, and document the correction in the entry itself.

---

## 2026-08-04 — Session 1: repository initialisation and v0 vertical slice

**Branch.** `main`
**Stage.** v0 — first working foundation.

**Objective.** Take the repository from a bare README to a functioning compiler for an
AI-native mathematical language, with a frozen semantic contract, executable examples,
tests, and research artefacts sufficient to make the project's central hypothesis
testable.

**Files and systems changed.**

- Repository scaffolded: `pyproject.toml`, `.gitignore`, `LICENSE`, `CLAUDE.md`,
  `README.md`, `ARCHITECTURE.md`, `SPEC.md`, `ROADMAP.md`, `DECISIONS.md`,
  `CHANGELOG.md`, `SECURITY.md`
- `GOAL.md` written (thesis, three layers, four principles, falsification conditions)
- Semantic kernel: `src/hamiltonian_lang/types.py`, `ast/nodes.py`
- Compiler: `lexer/`, `parser/`, `semantics/`, `type_system/`, `diagnostics/`, `graph/`,
  `cli/`
- Backends: `base.py`, `hml.py`, `canonical.py`, `latex.py`, `english.py` (Lead Architect);
  `stan.py`, `sympy.py`, `lean.py` (Backend Engineer agent)
- Specs: `spec/semantic_objects.yaml`, `type_rules.yaml`, `concept_schema.yaml`,
  `ir.schema.json`
- Examples: seven reference problems plus a quantifier-scope companion file
- Tests: `tests/{parser,semantics,type_system,roundtrip,golden}` (Lead Architect);
  `tests/{backends,adversarial}` (agents)
- Governance: ten agent definitions in `.claude/agents/`, five skills in
  `.claude/skills/`, `.claude/settings.json` hooks, `.githooks/pre-commit`,
  `scripts/conformance.sh`, `scripts/install-git-hooks.sh`, CI workflow

**What was completed.** A full pipeline runs end to end: HML-L1 source parses, resolves,
type-checks, and renders to six views plus a stable content hash. All eight example files
check cleanly. 229 tests pass.

**Decisions made and why.** D-001 to D-013, recorded in `DECISIONS.md`. The four with the
largest consequences:

- **D-003** — distribution arguments are role-labelled and labels are mandatory. Rationale:
  the scale-vs-variance ambiguity is a real, documented source of error. Cost: tokens,
  which H5 will measure rather than assume away.
- **D-004** — the scalar order is a poset, not a chain, because 0 is a probability and is
  not a positive real. `PositiveNatural` was added as the meet of `Natural` and
  `PositiveReal` so the literal `1` can serve as both a count and a scale.
- **D-010** — names are excluded from the content hash. This was forced by a failing
  property test, not chosen up front.
- **D-012** — the claimed contribution was demoted from the representation to the
  experiment, in response to Wave 1 prior-art evidence.

**Agent orchestration.** The master directive specified ten agents; the operator capped
this at four. Roles were merged: prior-art with novelty audit; alphabet with grammar;
backends; benchmarks with adversarial review. The semantics, IR and parser/compiler roles
were executed directly by the Lead Architect because the kernel had to exist before any
other agent could build against it. File ownership was disjoint by construction.
`morphology-architect` was **deferred and not run** — this is a real gap and a
prerequisite for benchmark hypothesis H6.

**Tests and verification actually executed.**

| command | actual result |
|---------|---------------|
| `.venv/bin/pip install -e ".[dev]"` | success |
| `.venv/bin/hml check examples/*/*.hml` | 8/8 clean |
| `.venv/bin/python -m pytest -q` | 229 passed |
| `.venv/bin/ruff check` (Lead-Architect files) | All checks passed |
| `.venv/bin/mypy src/hamiltonian_lang` | 1 error in `backends/sympy.py` |
| `./scripts/conformance.sh` | passes except the mypy stage |
| `hml hash` on the two quantifier scopings | hashes differ, as required |

**Failures and unresolved uncertainty.**

- Four real defects were found by running the code and fixed: unary minus preserved a
  positivity refinement (so `const a : Natural = -3` type-checked); `check dimension x = D`
  parsed the assertion as an equation; concept transforms were invisible to invariant
  bodies; declaration names were included in the content hash, breaking alpha-renaming
  invariance. Each is now covered by a test.
- Two defects were reported by the prior-art agent and fixed: `types.py::join` would raise
  `ValueError` on incompatible quantity bases; provenance is claimed in `GOAL.md` and not
  implemented.
- One `mypy` error remains, in an agent-owned file.
- The `linear_regression` example initially failed with "cannot infer a posterior: no
  probability law". The compiler was correct and the example was wrong; the example was
  fixed by adding priors. Recorded because it is the clearest instance of the design
  catching an authoring error.
- **No comparative measurement has been run.** The project's thesis remains untested.

**Effect on the overall project.** The project moves from a prose description to a
falsifiable artefact. The apparatus needed to run the central experiment now exists; the
experiment does not.

**Agent findings integrated after the first draft of this entry.**

- *Prior art.* No structurally novel construct was found in Layer 2. `GOAL.md` was
  corrected in place: Layer 2 is now called "the apparatus", the provenance claim was
  withdrawn, and two falsification conditions were added (out-of-distribution confound;
  Tam et al. EMNLP 2024 on reasoning degradation under format restriction). D-011, D-012.
- *Alphabet and grammar.* The freeze survives measurement across 8 real tokenisers
  (Llama-3 was gated and is excluded rather than estimated). Candidate A scores 115/125.
  Terseness does not pay: candidate B is 36.5% shorter and saves only 3.1% of tokens, and
  loses outright on 4 of 8 tokenisers. 13 of 17 Unicode confusable pairs survive both NFC
  and NFKC. D-014. Two defects in my own freeze document were found and fixed: `rv` was
  missing from the statement list, and the claim that the sd-vs-variance ambiguity "cannot
  be expressed" was **false as written** — the grammar admits it and the type system
  rejects it.
- *Backends.* Stan, SymPy and Lean statement-skeleton backends added, 292 tests. Stan's
  role→position mapping is pinned per family. No example is faithful under any of the
  three, and each backend says so rather than implying fidelity.
- *Red team.* Eight programs that passed `hml check` and should not have. All eight now
  rejected — D-016. The reviewer's use of `xfail(strict=True)` is why every fix was
  noticed immediately: fixing a defect turned its test into a visible failure.

**Corrections to my own work, recorded because they matter.** `semantics/__init__.py`
asserted in a docstring that definition cycles "are detected separately". No such detection
existed. That is worse than a missing feature. It now exists (`HML-S606`). Separately, my
first fix for finding 1.8 rejected any expression carrying `UnknownType`, which made
`require sum(w) = 1.0` a type error — ordinary mathematics the language ought to express.
Replaced with real signatures for the aggregate builtins.

**Verification after integration.**

| command | actual result |
|---------|---------------|
| `.venv/bin/python -m pytest` | **594 passed** (backends 292, golden 84, adversarial 71, roundtrip 50, type_system 39, parser 37, semantics 21) |
| `.venv/bin/ruff check src tests` | All checks passed |
| `.venv/bin/mypy src/hamiltonian_lang` | Success: no issues found in 22 source files |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS**, all 8 stages |
| `.venv/bin/python evaluation/run_baseline.py` | ran; deterministic compiler-side metrics only |

The baseline's generated header previously named three defects that had since been fixed;
the claims were withdrawn and the file regenerated. A stale honest-limitations note is
still a false statement.

**Next intended step.** Build the scaffolding-ablation arm — English plus the same
structural prompting — because it is the arm most likely to falsify the thesis, and
therefore the one that should be built before any arm that could confirm it.

---

## 2026-08-04 — Session 1, second pass: red-team integration

**Branch.** `main`
**Stage.** v0 — integration of the final Wave 2 agent.

**Objective.** Act on the benchmark and adversarial review agent's report: withdraw
claims it showed were unsupported, and fix the methodological defect that let a false
success criterion pass a green test suite.

**What the agent delivered.** 24 problems across six
categories, 120 arm files, a 620-line preregistered protocol with **seven** arms rather
than five (A' = prose plus a matched structural checklist, E' = comments stripped), and a
deterministic scoring harness reporting 93/93 assertions passed and diagnostic line
accuracy 1.0 over 50 single-line injections. The protocol states plainly that **one
confound is not resolvable**: "structured formal notation helps" cannot be separated from
"*this* notation helps".

Two of my own claims were withdrawn as unsupported:

- `distributions.py` called targeted misparameterisation diagnostics "the clearest single
  demonstration of the project thesis" — a claim about evidence, in a file containing
  none.
- The freeze document's "+4 tokens per law statement, ≈5.9% … measured rather than
  assumed" named no tokeniser and no corpus. The number is real; the citation was missing
  and is now present, together with the fact that `tiktoken` is absent from the project
  venv so `evaluation/score.py`'s own token figures are approximate and not interchangeable
  with it.

**The methodological finding of the session (D-018).** The alpha-renaming success
criterion was **false while a passing property-based test asserted it**. The test was real
and green; its generator simply never produced `def` parameters — the one binder form that
failed. The property is now parameterised over every binder form, with a companion test
asserting each template actually compiles, because a template that silently fails to
compile makes the property vacuously true one level up.

Strengthening that generator immediately produced a further case, which turned out to be a
*design question* rather than a defect: concept parameter names are the concept's
interface, like distribution roles, so renaming one *should* change the hash. The
implementation was already right and the test was wrong. Recorded as D-017 with an explicit
table of which names are binders and which are roles.

**Verification after the second pass.**

| command | actual result |
|---------|---------------|
| `.venv/bin/python -m pytest` | **609 passed** (backends 292, golden 84, adversarial 71, roundtrip 65, type_system 39, parser 37, semantics 21) |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS**, all 8 stages |

**Adopted, not rebutted.** The reviewer's strongest failure argument is now in
`ROADMAP.md`: the inference the thesis wants to eliminate happens when the file is
*written*, not read. A correct-looking encoding of a misunderstanding compiles clean,
hashes correctly, and is wrong. If arm A' closes the gap, the right artefact is a prompt,
not a compiler. That is precisely why A' is built first.

**Files changed.** `DECISIONS.md` (D-017, D-018), `ROADMAP.md`,
`docs/design/V0_DESIGN_FREEZE.md`, `docs/PROJECT_STATUS.md`,
`src/hamiltonian_lang/type_system/distributions.py`,
`tests/roundtrip/test_roundtrip.py`, `evaluation/run_baseline.py` and its regenerated
output.

**Effect on the overall project.** The compiler, the benchmark corpus and the
preregistered protocol are now mutually consistent. Two false statements were removed
from the repository. The apparatus is sound; the experiment is still not run.

**Next intended step.** Demonstrate a lossless round trip through a real Layer-3
backend (HML → Stan → HML, HML → Lean → HML) preserving the content hash, or
characterise exactly where it fails. It needs no model call and tests the
one-object-many-views claim directly.

---

## 2026-08-04 — HML-EVAL-001 §1–2: pre-evaluation audit and version freeze

**Branch.** `main`
**Stage.** HML-EVAL-001, empirical evaluation phase.

**Objective.** Verify repository state directly from commands rather than from prior
summaries, before building any evaluation apparatus on top of it. Freeze v0.

**Files and systems changed.** `docs/evaluation/PRE_EVALUATION_AUDIT.md` (new),
`src/hamiltonian_lang/lexer/__init__.py`, `tests/parser/test_parser.py`, `DECISIONS.md`
(D-019), tag `hml-v0-eval-freeze`.

**What was completed.** A verified inventory: 6 declaration kinds, 5 inference queries,
9 scalar types, 7 base dimensions, 16 distribution families, 9 registered backends, 15
graph edge kinds, 82 diagnostic codes. Commit hashes recorded. Push status confirmed:
both project commits are local-only, verified with `git log --branches --not --remotes`.

**Decisions made and why.** D-019 — the lexer did not terminate on non-ASCII letters.
`str.isalpha()` is true for every Unicode letter, so `ℝ` was dispatched into the identifier
routine, which consumed zero characters; the caller then re-dispatched on the same
character forever. Fixed twice over: ASCII test first in the dispatch, and a zero-progress
guard inside the routine, because a lexer routine must never consume zero input whatever
the dispatch above it believes.

**Tests and verification actually executed.**

| command | actual result |
|---------|---------------|
| `./scripts/conformance.sh` | CONFORMANCE: PASS, all 8 stages |
| `.venv/bin/python -m pytest` | 615 passed (609 before; 6 new regression tests) |
| `.venv/bin/python -m pytest tests/golden` | 84 passed, no content hash moved |
| round-trip probe over 9 backends | 1 re-parses and preserves the hash; 8 do not |
| `curl localhost:11434/v1/chat/completions` | gemma4:31b generating, 638 completion tokens in 25.7s |

**Failures and unresolved uncertainty.**

- The audit **contradicted a convenient reading of my own earlier summaries**. "Nine
  backends" invites the reading that nine translations exist. Nine *renderings* exist. The
  count of demonstrated semantics-preserving round trips is **one**, HML → HML, which is
  the trip that cannot lose anything. Corrected in the audit and in `PROJECT_STATUS.md`.
- `BackendResult.faithful` is a weaker claim than its name suggests: it means "declared no
  per-construct loss", not "round-trips". Four backends report `faithful=True` while being
  one-way.
- D-019 was found only because the audit *tested* the round-trip claim instead of trusting
  it. Had it not been found, the first model output containing `ℝ` or `∀` would have hung
  the run with no timeout and no diagnostic — destroying the experiment silently rather
  than failing it loudly.
- The available model is a **reasoning model**. It decomposes problems internally
  regardless of arm, which biases the A vs A′ contrast towards the null and therefore
  biases any Hamiltonian-over-A′ result in the thesis's favour. Recorded before any data
  exists.
- Measured throughput 26 s/call makes the full 120 × 7 × 3 design ≈18.2 hours. The
  apparatus will be built to specification; the run will be a preregistered subset, and
  unrun cells will be reported as unrun rather than quietly dropped.

**Effect on the overall project.** The project's factual base is now verified rather than
asserted, and one defect that would have invalidated the experiment has been removed.

**Next intended step.** Build the canonical semantic source dataset, so that all seven arms
are rendered from one object rather than authored independently — which is what prevents
one arm from silently carrying more information than another.

---

## 2026-08-04 — HML-EVAL-001 §3–6, §9: evaluation apparatus

**Branch.** `main` · **Stage.** HML-EVAL-001, empirical evaluation phase.

**Objective.** Build the apparatus for the seven-arm comparison, and implement the
supported-subset round trips that test the one-object-many-views claim.

**Files and systems changed.** `evaluation/corpus/{cso,generators,renderers}.py`,
`evaluation/{model_client,semantic_equiv,harness,build_corpus}.py`,
`src/hamiltonian_lang/importers/`, `tests/roundtrip/test_importers.py`,
`benchmarks/eval001/` (120 problems, 840 arm files), `DECISIONS.md` (D-020).

**What was completed.** A canonical semantic object per problem, rendered into all seven
arms — so no arm is authored independently and none can silently carry more information
than another. 120 problems: probability 25, binding 25, quantifier 25, dimensional 25,
algebraic 20. All 120 reference encodings compile. Leakage controls assert demonstrations
are disjoint from the benchmark by both id and prose; all 840 arm files carry the problem
statement and question verbatim, verified programmatically.

**Decisions made and why.** D-020 — the five inference queries do not share a
precondition. D-016's finding 1.7 had required every query's target to carry a law, which
rejected `infer mle p` where `p` appears in a likelihood. An MLE is defined by the
likelihood of the data *given* the parameter; the parameter carries no law. Found while
building a corpus problem whose prose states no prior: encoding a prior to satisfy the
compiler would have made the Hamiltonian arm say more than the problem does, which is the
information asymmetry §4 forbids.

**Tests and verification actually executed.**

| command | actual result |
|---------|---------------|
| `.venv/bin/python -m pytest` | 645 passed |
| `.venv/bin/python -m evaluation.build_corpus` | 120 problems, 840 arm files, 0 reference failures |
| `./scripts/conformance.sh` | CONFORMANCE: PASS, all 8 stages |
| arm fairness audit | 840/840 files carry problem+question verbatim |
| measured prompt asymmetry | A 1096 chars, A' 2311, D 4397, E 4540, F 5141 |

**Failures and unresolved uncertainty.**

- **The round trips found more than they confirmed.** Stan cannot express strict
  positivity, so most distribution families cannot round-trip at all; Stan loses observed
  values and destroys interleaved declaration order; and the Lean route silently loses
  probability laws while producing a reconstruction that compiles cleanly. That last one
  is the strongest argument for round-tripping as a validation method: a one-way test
  cannot detect it.
- **A validity bug in my own comparator, caught before it produced numbers.** The first
  semantic-equivalence check compared entity *names*, which would have penalised
  legitimate renaming and systematically understated Hamiltonian encoding accuracy. Module
  names are binders, not roles (D-017). Rewritten to be name-independent and validated
  three ways: reference encoding scores 1.0, a renamed encoding is unaffected, a role swap
  is caught.
- **The run cannot cover the full design.** 120 x 7 x 3 = 2520 calls at ~57 s is ~40
  hours. A stratified 15-problem pilot (315 calls, ~5 h) is running; job ordering
  completes generation 0 across all arms first, so truncation costs generations rather
  than arm coverage. Unrun cells will be reported as unrun.

**Effect on the overall project.** The experiment can now be run and scored without any
model judging any output.

**Next intended step.** Complete the pilot, then produce
`docs/evaluation/HML_EVAL_001_REPORT.md` with paired intervals, effect sizes and the
go/redesign/stop decision.

---

## 2026-08-04 — HML-EVAL-001 §8, §10: comparator validity and analysis

**Branch.** `main` · **Stage.** HML-EVAL-001, pilot in flight.

**Objective.** Make the semantic-equivalence comparator trustworthy before it produces any
reported number, and build the paired analysis.

**Files changed.** `evaluation/semantic_equiv.py`, `evaluation/corpus/{cso,generators}.py`,
`evaluation/analyse.py` (new), `tests/evaluation/test_corpus.py` (new).

**What was completed.** Paired bootstrap intervals, exact McNemar, Cohen's h, coverage
accounting that reports unrun cells as unrun, and per-domain breakdowns — standard library
only. 300 new corpus self-consistency tests.

**Failures and unresolved uncertainty — the substance of this entry.**

Inspecting low encoding scores before trusting them found **four comparator bugs, all
biasing against the project's own thesis**:

1. `score()` returned 0.0 when nothing was checkable. The 25 dimensional problems declare
   no entities, so every Hamiltonian encoding of them scored zero regardless of quality.
2. A parameterised definition's `declared_type` is its *return* type; comparing it against
   `Function[Real -> Real]` marked correct encodings wrong.
3. The quantifier chain did not follow `def p := forall …` + `prove p`, a legitimate
   encoding, and missed its structure entirely.
4. `parse_dimension` could not handle a parenthesised denominator or a half-integer
   exponent, so those ground truths silently failed to parse and their facet was dropped.

Then a **corpus self-consistency failure**: 60 of 120 reference encodings scored below 1.0
against their own ground truth. The facts said `param` where the encoding said `const`;
quantifier binders were listed as module declarations they were never in; the dimensional
references were generic boilerplate that never carried the case's own dimension. Every one
would have depressed the Hamiltonian arms' measured encoding accuracy for reasons having
nothing to do with the model. All fixed; a test now asserts every reference encoding
compiles and scores exactly 1.0, so the drift cannot recur silently.

Effect on data already collected: arm D's mean encoding score moved from 0.56 to 0.70.
Analysis now **re-scores from stored raw output** rather than trusting the score written
during the run, so a comparator fix never requires re-running the model.

One v0 limitation surfaced and was recorded rather than encoded incorrectly: HML type
syntax cannot express a half-integer exponent — `Quantity[Mass^1/2 * Length]` parses `^1`
and then reads `/ 2` as dimension division. That corpus case was removed.

**Tests and verification actually executed.**

| command | actual result |
|---------|---------------|
| `.venv/bin/python -m pytest` | 945 passed |
| `./scripts/conformance.sh` | CONFORMANCE: PASS, all 8 stages |
| `.venv/bin/python -m evaluation.build_corpus` | 120 problems, 840 arm files, 0 failures |
| `.venv/bin/python -m evaluation.analyse --run eval001-pilot` | 34/315 calls, 4 fully covered cells |

**Effect on the overall project.** The instrument is now checked against itself. Had these
bugs survived, the experiment would most likely have produced a **false negative** and the
thesis would have been rejected for an artefact of my own measurement code.

**Next intended step.** Let the pilot accumulate, then write
`docs/evaluation/HML_EVAL_001_REPORT.md` with the go/redesign/stop decision.

---

## 2026-08-04 — EVAL_SPEC_v1.0: freeze and evaluator validation

**Branch.** `main` · **Stage.** HML-EVAL-001 pilot, generation 0 complete.

**Objective.** Freeze the evaluation specification and validate the evaluator *before*
looking at any arm-level comparative result.

**Files changed.** `evaluation/freeze.py` (new), `evaluation/blind_audit.py` (new),
`tests/evaluation/test_evaluator_validation.py` (new), `evaluation/analyse.py`
(generation filter and secondary outcomes).

**What was completed.** Generation 0 of the pilot finished before the time budget
expired: **105/105 cells, 15 problems x 7 arms, every cell present.** Generation 1 also
completed (105 further trials) at temperature 0.7, so those are independent samples rather
than temperature-zero duplicates. `EVAL_SPEC_v1.0` records language commit and tag, corpus
hash, per-arm prompt-template hashes, scorer hash, model digest and sampling, and a
per-cell raw-output manifest.

**Evaluator validation.** 22 synthetic-mutation tests demonstrate that all nine scored
facets can both pass and fail, with a meta-test that fails if a facet is added without a
mutation test. Binder-renaming invariance, role-swap detection, quantifier-order
detection, dimension comparison and omitted-structure detection are each pinned.

**Blinded audit.** 20 randomly sampled generation-0 outputs, arm labels hidden, seed
recorded. Result: **20/20 answer agreement, 6/6 semantic agreement, all seven arms
represented, no disagreements.**

**Failures and unresolved uncertainty.**

- The audit found the blind-audit tool itself was reading **stale scores** written during
  the run rather than re-scoring with the current comparator. Case02 showed 0.0 where the
  current comparator gives 1.0. Fixed before any verdict was recorded; auditing a scorer
  version that no longer exists would have audited nothing.
- Two comparator limitations were found and **documented rather than fixed**, both biasing
  against the Hamiltonian arms: (1) an encoding that folds a constraint into a refinement
  type (`param x : NonNegativeReal`) is scored as a type and kind mismatch against a
  ground truth using `var` + `require`, though the two are arguably equivalent; (2) an
  encoding that fails to parse zeroes every structural facet, so the semantic score
  conflates syntax failure with mistranslation. The report presents encoding score both
  over all encodings and over parsing encodings only.
- **6 of 105 generation-0 cells produced zero characters of output**, spread roughly one
  per arm (D had none). Cause is generation-budget exhaustion in the model's reasoning
  channel, not a representation effect. Recorded as a data-quality fact with its
  per-arm distribution rather than dropped.

**Tests and verification actually executed.**

| command | actual result |
|---------|---------------|
| `.venv/bin/python -m pytest` | 967 passed |
| `./scripts/conformance.sh` | CONFORMANCE: PASS, all 8 stages |
| `.venv/bin/python -m evaluation.freeze --version 1.0` | spec written, 105 raw outputs manifested |
| `.venv/bin/python -m evaluation.blind_audit unblind` | 20/20 answer, 6/6 semantic, no disagreements |

**Effect on the overall project.** The scorer is frozen and validated. Any change from
here requires a new EVAL_SPEC version with the v1.0 result preserved.

**Next intended step.** Primary analysis on generation 0 and
`docs/evaluation/HML_EVAL_001_PILOT_REPORT.md` with a single decision.

---

## 2026-08-04 — HML-EVAL-001 pilot complete: result and decision

**Branch.** `main` · **Stage.** HML-EVAL-001 pilot closed.

**Objective.** Complete one fully paired generation, freeze the spec, validate the
evaluator blind, analyse, and record one decision.

**What was completed.** Generation 0: **105/105 cells, 15 problems × 7 arms, zero unrun.**
`EVAL_SPEC_v1.0` frozen on a clean tree before any comparative result was viewed; 22
mutation tests and a 20-case blinded audit (20/20 answer, 6/6 semantic, no disagreements).
`docs/evaluation/HML_EVAL_001_PILOT_REPORT.md` written.

**Result.** Answer accuracy: A, A′, B, D, E, F all 14/15 = 93.3%; C 13/15 = 86.7%. Six of
seven paired contrasts had **zero discordant pairs** — the arms succeeded and failed on the
same problems. Encoding fidelity: D 0.648, E 0.701; parse rate D 73.3%, E 85.7%. The single
interval excluding zero was E−D encoding fidelity, +0.065 [0.006, 0.136].

**Decisions made and why.** **REDESIGN AND RETEST.** Not "no advantage", because a set
saturated at 93% with n=15 could only detect an effect of ~33 points and therefore had
almost no power; and not "continue", because there is no answer-accuracy effect to amplify
and 27–50% of Hamiltonian encodings do not compile — an explicit redesign trigger.

**Failures and unresolved uncertainty.**

- **A scorer defect was found after comparative results were viewed.** All seven arms were
  marked wrong on `d24_unknown_constant` and all seven had answered it correctly: answer
  correctness was computed once at trial time and the re-scoring path re-derived only the
  encoding score, so a dimension-parser fix never reached the stored verdicts. Handled
  under the directive's protocol — v1.0 preserved verbatim, defect recorded as
  EVAL-DEFECT-001, raw outputs transparently rescored under v1.1. Effect: 7 cells, one per
  arm, all False→True; every paired difference unchanged.
- The blind-audit tool itself was initially reading stale run-time scores; fixed before any
  verdict was recorded.
- 6 of 105 cells produced empty output from reasoning-budget exhaustion, concentrated on
  one problem, which is the sole source of the 1/15 shortfall in every arm.
- Structured English (A′) was the **least stable** arm on replication, falling to 66.7% in
  generation 1, while costing 48% more generated tokens than plain English for zero gain.
- Two comparator limitations documented, not corrected, both biasing against the
  Hamiltonian arms; `prohibited_assumptions` is carried but not scored, so
  missing-assumption detection is **not measured**.

**Tests and verification actually executed.**

| command | actual result |
|---------|---------------|
| `.venv/bin/python -m pytest` | 967 passed |
| `./scripts/conformance.sh` | CONFORMANCE: PASS, all 8 stages |
| `evaluation.analyse --generation 0` | 105/105 cells, 0 unrun |
| `evaluation.blind_audit unblind` | 20/20 answer, 6/6 semantic, no disagreements |

**Effect on the overall project.** The thesis now has its first real measurement against
it. Nothing observed supports a representation advantage; the design was too weak to rule
one out.

**Next intended step.** Redesign the corpus so it discriminates — harder problems, lower
baseline accuracy, more of them — and reduce the Hamiltonian syntax-failure rate before
retesting.

---

## 2026-08-04 — V0 preserved as baseline; V1 designed

**Branch.** `main` · **Stage.** V0 closed; V1 in design, unimplemented.

**Objective.** Preserve the completed V0 experiment as the comparison baseline, then
specify Hamiltonian V1: Discourse, Transformation and Epistemics.

**Files changed.** Tag `hml-v0-baseline`; `docs/design/V1_KERNEL.md`,
`docs/design/V1_EXPERIMENT_PLAN.md`, `spec/v1/semantic_objects.yaml` (all new);
`DECISIONS.md` (D-021), `ROADMAP.md`, `docs/PROJECT_STATUS.md`.

**What was completed.** V0 is tagged with its pilot result and 221 stored trials; `src/`
is closed under it, so no V1 work can invalidate the only model-in-the-loop measurement
this project has. V1 is specified as four layers above V0's mathematical content:
transformation edges (what rewrites to what, with side conditions), inferential relations
(what follows logically — a different relation), epistemic status (how strongly, on what
grounds) and discourse state (what remains to be shown).

**Decisions made and why.** D-021. The governing rule is that **a construct enters the
kernel only if it changes what the checker reports** — "we now show" becomes `goal`
because it opens an obligation; "for completeness" stays in the renderer because it
changes nothing. That rule exists because the pilot demonstrated surface area is not
self-justifying.

The load-bearing addition is the epistemic layer: `fail_to_reject` returns `Evidence`,
`prove` requires `Proof`, and there is **no coercion between them**, so
`prove(fail_to_reject(H0))` is a type error. This applies V0's own method — prohibit a
conflation by making the two things incompatible types — to the most consequential
misreading in applied statistics. `PValue` is likewise a distinct type with no coercion to
a posterior.

Concept families are **declared, never generated**: `vary -> variance` is not a safe rule
and neither is `estimate -> estimator`, so there is no suffix rule and no derivation
engine. `estimator`, `estimate` and `estimation procedure` are three independently
declared types, which makes "the estimate is unbiased" a type error.

**Verification actually executed.**

| command | actual result |
|---------|---------------|
| `git tag -a hml-v0-baseline` | created; `git describe` returns it |
| `.venv/bin/python -m pytest` | 967 passed |
| `./scripts/conformance.sh` | CONFORMANCE: PASS, all 8 stages |

**Failures and unresolved uncertainty.**

- **V1 is design only. Nothing is implemented and nothing is claimed.**
- The honest prior is poor: V1 adds substantially more surface than V0, and V0's surface
  bought nothing measurable. **V1-H4 — that the model can write V1 as reliably as V0 — is
  the hypothesis most likely to fail**, since the model already wrote V0 unparseably
  27–50% of the time. A hard gate now blocks any V0-vs-V1 comparison until parse rate
  reaches 90%.
- L3 inference is predicted **least** likely to survive: checking inference chains without
  a prover approaches re-implementing one, which the founding directive forbids. Recorded
  in advance so that a surprise is visible as a surprise.
- The primary outcome changes from answer accuracy to **error detection** (precision and
  recall on injected errors), because the pilot settled that representation does not
  change what the model computes.

**Effect on the overall project.** The measured V0 result is safe from further editing,
and V1 is specified in a form that can be falsified layer by layer rather than defended
as a whole.

**Next intended step.** Redesign the corpus to a 50–60% baseline accuracy at n >= 60, then
attack the parse-rate gate. No V1 layer is testable until the model can write the language.

---

## 2026-08-04 — HML-V1-CONCEPT-001: gate, branch, semantic contract

**Branch.** `hml-v1-concept-kernel` (created from `main` at `hml-v0-baseline`).
**Stage.** V1 Phase 0–1 complete; Phases 2–10 delegated to four agents.

**Objective.** Evaluate the V1 gate against pilot evidence, branch, and build the semantic
contract agents must work against.

**Files changed.** `docs/evaluation/V1_GATE_DECISION.md`,
`docs/design/V1_CONCEPT_KERNEL.md`, `spec/concept_registry.schema.json`,
`src/hamiltonian_lang/v1/{__init__,epistemic}.py` — all new.

**Gate verdict.** PASSED on criteria 4 and 5 only. Criterion 1 (answer accuracy) is
**refuted**, not merely unproven: D−A, D−A′ and D−B were all +0.000 with **zero discordant
pairs**. Criterion 2 has no comparison arm and criterion 3 was never measured (no prover
was invoked). The pass rests on compiler feedback raising parse rate 73.3%→85.7% and
50.0%→93.3% with encoding fidelity +0.065 CI [0.006, 0.136], and on the 27–50%
parse-failure weakness being directly testable.

**Decisions made and why.** The gate constrains what V1 may claim: errors catchable, not
reasoning improved. The primary outcome is therefore error detection (precision and recall
on injected errors), not answer accuracy — the pilot settled that representation does not
change what the model computes.

The Lead Architect owns and has frozen two artefacts before any agent ran:
`spec/concept_registry.schema.json` and `src/hamiltonian_lang/v1/epistemic.py`. The latter
implements the prohibition the whole layer exists for: `fail_to_reject` yields `Evidence`,
`prove` demands `Proof`, and `coercion_allowed` refuses the pair with an explicit reason.
Verified by execution, not assertion.

**Verification actually executed.**

| command | actual result |
|---------|---------------|
| `git checkout -b hml-v1-concept-kernel` | branch created |
| epistemic contract executed directly | `fail_to_reject` → Evidence; discharges_goals False; coercion to Proof refused with reason |
| context enforcement | `with_high_probability` with no regime, `model_conditional` with no model, `fail_to_reject` with no alpha — all rejected |
| `jsonschema.Draft202012Validator.check_schema` | registry schema valid |
| `.venv/bin/python -m pytest` | 967 passed (V0 suite, unchanged) |
| `./scripts/conformance.sh` | CONFORMANCE: PASS, all 8 stages |

**Failures and unresolved uncertainty.**

- **The principal risk is stated, not buried:** V1 is *larger* than a language the model
  already wrote unparseably 27–50% of the time. A hard gate blocks any V0-vs-V1
  comparison until V1 parse rate reaches 90%.
- Predicted layer survival is recorded in advance — epistemic most likely, inference least
  — so a surprise is visible as a surprise rather than rationalised afterwards.
- Four agents are running; none has reported. No V1 implementation claim is made in this
  entry beyond the two contract artefacts, which were executed and verified here.

**Effect on the overall project.** The contract that the whole milestone depends on exists
and enforces its central prohibition before any dependent code was written.

**Next intended step.** Integrate the four agents' output, run conformance, and produce
`docs/evaluation/HML_V1_CONCEPT_ABLATION_REPORT.md`.

---

## 2026-08-04 — HML-EVAL-002 preregistration; correction of a refutation overclaim

**Branch.** `hml-v1-concept-kernel` · **Stage.** HML-EVAL-002 preregistered.

**Objective.** Give the original reasoning thesis its first adequately powered and
technically fair test, and correct an overclaim in previously committed files.

**The correction, which is the substance of this entry.** `V1_GATE_DECISION.md`,
`V1_CONCEPT_KERNEL.md` and `v1/__init__.py` stated that criterion 1 "was tested and
**refuted**". That was wrong, and it **contradicted this project's own pilot report**,
which states in §9 that the zero differences "are not evidence that no difference exists."
The report was right and the later documents were wrong. All three are corrected, and
`V1_GATE_DECISION.md` carries a visible CORRECTION section rather than a silent edit.

The canonical conclusion is now recorded verbatim in every affected file:

> Zero-shot Hamiltonian did not improve answer accuracy on this small, low-discrimination
> pilot. The experiment was underpowered and had a severe ceiling effect.

The status of the thesis is **UNPROVEN, NOT REFUTED**. The drift this error encouraged —
treating the checker as the product rather than as the mechanism tested by H3 — is
withdrawn.

**What was completed.** `docs/evaluation/HML_EVAL_002_PREREGISTRATION.md`: three
independently tested hypotheses (H1 input representation, H2 reasoning representation,
H3 verifier-guided reasoning), eight matched conditions, two blocking gates, fixed success
thresholds, and an eight-part failure condition specifying when a negative conclusion
becomes legitimate. §8 guards the opposite error: thresholds fixed in advance, benchmark
frozen and hashed, syntax chosen on measured parse rate, and H1/H2/H3 reported separately
so a win on H3 alone is never reported as a win for the representation.

**Verification actually executed.**

| command | actual result |
|---------|---------------|
| `grep -rn refut docs/ src/` | three overclaims located and corrected |
| `curl localhost:11434/api/tags` | only `gemma4:31b` installed |
| import probe for torch/peft/transformers/datasets/trl/accelerate | **all ABSENT** |
| `.venv/bin/python -m pytest` | 967 passed |

**Failures, blockers and unresolved uncertainty.**

- **Phase 5 partly blocked:** the 7–14B non-reasoning arm requires a model download that
  has not been performed. That arm tests the most plausible version of the thesis — that
  Hamiltonian helps most where the model does not already decompose internally — so its
  absence is material, not cosmetic.
- **Phase 6 blocked:** no training stack is installed. On Apple silicon the realistic path
  is `mlx-lm` LoRA. Recorded as blocked pending an install decision rather than dropped.
- Condition 5 (English input, Hamiltonian derivation required) is the condition the pilot
  lacked and the one that most cleanly isolates H2. Its absence is why H1 and H2 were
  conflated in HML-EVAL-001.
- Four V1 agents are still running; `registry.py`, `minting.py`, `epistemic_checks.py`,
  `transformation.py` and `evaluation/v1/corpus.py` exist but are unintegrated and
  unverified by me. No claim is made about them here.

**Effect on the overall project.** The thesis is restored to its correct status and the
experiment that could actually settle it is specified with its gates and its failure
condition fixed in advance.

**Conformance note for this commit.** The full pre-commit gate FAILED on ruff and mypy
errors inside `src/hamiltonian_lang/v1/minting.py`, an agent-owned file still being
written. That is the gate working as designed. This commit therefore stages **only
Lead-Architect-owned files** — the correction and the preregistration — and leaves the
four agents' in-flight modules uncommitted. Stages verified for the staged set: pytest 967
passed, examples check passed, IR schema validation passed, no-superiority-claim check
passed, private-docs check passed, placeholder check passed. The ruff and mypy failures
belong to unstaged agent work and will be resolved at integration.

**Next intended step.** Integrate the V1 agents, then build and run Phase 2 — the syntax
acquisition comparison. Nothing about reasoning can be measured until a surface form
reaches 95% parse.

---

## 2026-08-04 — HML-COMPILER-CORE-003 Phase 0-1; four V1 agents integrated

**Branch.** `hml-v1-concept-kernel` · **Stage.** Compiler hardening; V1 integrated.

**Objective.** Measure before modifying, fix only what measurement justifies, and
integrate the four V1 agents to a clean conformance pass.

**Phase 0 audit — `docs/evaluation/COMPILER_CORE_AUDIT.md`.** 22 malformed inputs, 800
fuzz inputs, 8 precedence probes, 4 semantic-hole probes, 5 dimensional probes, 4 identity
probes. The audit's main effect was to *prevent* four rewrites: expression precedence and
associativity are measurably correct (5/5 probes), all four canonical-identity rules are
correct, binder identity is correct, and the lexer survived 800 fuzz inputs with no hang or
crash. **The directive's own conditions for a Pratt parser, a locally nameless
representation, a red-green tree and an e-graph are each unmet by measurement**, and each
is recorded as a deferred decision with a trigger rather than as an omission.

**Two measured defects fixed by the Lead Architect.**

1. **`RecursionError` on deep nesting.** 400 nested parens crashed the process — a Phase 1
   violation, and reachable by a truncated generation. The first fix did not work: a bound
   of 120 was never reached because each nesting level costs ~12.2 Python stack frames and
   the default limit of 1000 breaks at **depth 82**, measured by bisection. `MAX_EXPR_DEPTH`
   is now 50, derived from that measurement, with a `RecursionError` backstop at the parse
   boundary and a test asserting the bound stays below the measured ceiling.
2. **The unknown-type hole, the audit's most consequential finding.** `param x :
   Frobnicator` and `param sigma : Positiv` — a truncation of `PositiveReal` — were both
   **accepted in silence**, because an unknown capitalised name parses as a concept
   reference. That is exactly the failure mode of generated code and it corrupts encoding
   fidelity with no diagnostic to trigger a repair. Now `HML-T440`, with a nearest-name
   correction (`Positiv` → `did you mean 'PositiveReal'?`), because one-repair success is a
   gate metric and a diagnostic that cannot be acted on does not help a repair loop.

**A gap in my own contract, found by the adversarial agent.** `spec/v1/semantic_objects.yaml`
named `PValue` as a distinct type with no coercion to a posterior. **I never implemented
it.** Both sides were typed `Probability`, so p-value-as-posterior type-checked — meaning
**L4 was failing its own kill criterion**. Now closed: `PValue` and `PosteriorProbability`
are distinct frozen types, deliberately not subclasses of anything (subclassing would
create the coercion path the types exist to forbid), identity is the only permitted
coercion, and a posterior without its prior is rejected.

**Three of six V1 layers had no kill criterion** — registry, minting and morphology, the
three the milestone is named after. Added, including the minting criterion recording its
own current **FAILURE**: the adversarial agent seeded a registry with one concept and got
three further copies admitted via a vacuous constraint, an undeclared parameter, and a
trivially rearranged definition.

**Tests and verification actually executed.**

| command | actual result |
|---------|---------------|
| `.venv/bin/python -m pytest` | **1469 passed, 4 skipped, 1 xfailed** |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS — without override** |
| `.venv/bin/ruff check src tests` | All checks passed |
| `.venv/bin/mypy src/hamiltonian_lang` | no issues, 32 source files |
| front-end fuzz battery, re-run | 0 hangs, 0 crashes, deep nesting now `HML-P240` |
| `hml check examples/*/*.hml` | 8/8 pass; golden hashes unmoved |

**Failures and unresolved uncertainty.**

- The **minting protocol is gameable and currently fails its criterion**. Not fixed in this
  entry; recorded with a runnable reproduction in `audits/V1_RED_TEAM.md` §3.
- **V0 cannot express 38 of the 60 ablation problems**, so the pilot's encoding-fidelity
  metric is undefined on that corpus and the V0 control is disadvantaged by construction.
- Per-block ablation contrasts need a **50 pp** effect at 12 items — worse than the pilot.
  Whole-corpus MDE is 10.0 pp. Block results are marked descriptive-only.
- Lean's `sorry` **compiles and exits 0**, so exit status alone would certify a false
  theorem; `#print axioms` is the real discriminator. Since V0's Lean backend closes every
  obligation with `sorry`, no V0-emitted theorem could ever count as verified.
- A **V0 SymPy defect** remains open: generated modules raise `NameError` on import when a
  quantified `Proposition` is dropped but a reference survives.

**Effect on the overall project.** The compiler is hardened where measurement justified it
and left alone where it did not, and conformance passes cleanly with all V1 work integrated.

**Next intended step.** Freeze the compiler, freeze four syntax candidates, and run the
syntax-acquisition gate on `gemma4:31b`.

---

## 2026-08-04 — HML-COMPILER-CORE-003: defect remediation complete

**Branch.** `hml-v1-concept-kernel` · **Stage.** Compiler hardening finished; conformance
clean without override.

**Objective.** Finish the measured defect-remediation sequence before any further
architecture, and adopt nothing whose stated condition is unmet.

**Seven measured defects fixed, each with a regression test.** Full table in
`docs/evaluation/COMPILER_CORE_REMEDIATION.md`.

1. Parser crash on 400 nested parens. `MAX_EXPR_DEPTH = 50`, derived from a measurement
   (~12.2 frames per level, ceiling at depth 82), plus a `RecursionError` backstop.
2. Unknown and truncated type names accepted in silence — `HML-T440` with a nearest-name
   correction in every position a type can appear.
3. Synthesis-only checking — explicit `synthesise` / `check` with `CheckedExpr`, so a
   failure names the role that imposed the expectation.
4. Rational dimension exponents (`Quantity[Length^1/2]`) and constrained dimension
   variables (`Quantity[D]`).
5. Generated SymPy raising `NameError` — a dropped definition left a live reference.
6. Lean `sorry` compiling and exiting 0 — `lean_verify.verify()` with forbidden-tactic
   pre-check, `autoImplicit false`, compilation, statement comparison and `#print axioms`.
7. `PValue` specified and never implemented, so L4 failed its own kill criterion.

**Decisions made and why.** Six proposals were **declined**, each because its own stated
adoption condition is unmet by measurement: Pratt parsing (precedence correct on 5/5
probes), locally nameless binders (no binding defect), red-green trees, e-graphs,
cryptographic canonicalisation and probability monads.

**Two lessons worth recording beyond the fixes themselves.**

The dimension-variable syntax is constrained to a **single capital letter**, and that
constraint is load-bearing rather than cosmetic: if any unrecognised identifier could be a
variable, `Quantity[Lenght]` would silently become one, reintroducing the very hole
`HML-T440` closes. Five typo cases pin it.

The SymPy defect survived every existing test because those tests check emitted *text*.
Rendering succeeded; only executing the file revealed it. The new tests execute every
generated module.

**Tests and verification actually executed.**

| command | actual result |
|---------|---------------|
| `./scripts/conformance.sh` | **CONFORMANCE: PASS**, all 8 stages, no override |
| `.venv/bin/python -m pytest` | **1531 passed**, 4 skipped, 1 xfailed |
| front-end fuzz battery | 800 inputs, 0 hangs, 0 crashes |
| generated SymPy execution | every example module runs, 0 failures |
| `lean_verify` against Lean 4.32.2 | false theorem rejected; true theorem verified, `axioms: []` |
| `hml check examples/*/*.hml` | 8/8; golden hashes unmoved |

**Failures and unresolved uncertainty.**

- **Mathlib is absent**, so almost nothing HML emits is expressible in Lean: every scalar
  but `Bool`/`Natural`/`Integer` maps to `ℝ`. V0's Lean backend closes every obligation
  with `sorry`, so **no V0-emitted theorem can ever be verified** regardless of this work.
- Only two sites are routed through `check`; function arguments, proof claims and concept
  members still synthesise-and-compare.
- Dimension unification solves the single-variable case only.
- The **minting protocol remains gameable** and fails its own criterion.
- The benchmark case deleted for the half-integer-exponent gap has **not** been restored.

**Effect on the overall project.** The compiler is hardened exactly where measurement
justified it, and conformance passes cleanly with all V1 work integrated.

**Next intended step.** Freeze the supported V1 compiler and run the four-syntax Gemma
acquisition tournament. The report must state whether at least one syntax clears 95%
repaired parse success and 90% semantic preservation.

---

## 2026-08-04 — GOAL.md respecified; broad novelty claim withdrawn

**Branch.** `hml-v1-concept-kernel` · **Stage.** Objective sharpened before the syntax gate.

**Objective.** Replace a slogan-level goal with a hyperspecific, falsifiable specification,
and withdraw a novelty claim that prior art has occupied.

**The withdrawal, verified rather than assumed.** `WebFetch` on arXiv 2607.16372 confirmed
*AoA: Theorem Proving Agent over Abstract Syntax Tree of Redesigned Language* (Xu, Ong Jun
Leang, Wang, Li, Li, Ong, Watt; 17 July 2026). The abstract describes **Minilang** as "a
recent proof language that reaches SOTA on LLM-based proving but is too new for LLMs'
training corpora", and states "the model supplies proofs as JSON representations of
Minilang's AST — native to tool-calling LLMs".

Hamiltonian therefore **may not** claim novelty from: designing a formal language for LLMs ·
exposing an AST as JSON · demonstration-based teaching · compiler/prover feedback · reduced
token cost. All five are now explicitly listed as unavailable in `GOAL.md` §0.

One claim in the source material — that Minilang and its tree-edit interface cannot be
cleanly ablated — is **not in the retrieved abstract** and is marked **UNVERIFIED** and not
relied upon.

**What was completed.** `GOAL.md` rewritten as an eight-component specification
(Σ 𝒢 𝒮 ℛ ℰ 𝒞 ℬ 𝒪) with the optimisation objective stated formally, a per-component status
line, the remaining gap expressed as an eight-part conjunction, a prior-art table naming
what each near neighbour does *not* occupy, the H1/H2/H3 separation, the defensible
one-sentence claim, and eight failure modes.

**Decisions made and why.** The defensible claim is narrowed to the **conjunction**, with
𝒪 — empirical optimisation of the representation under matched-model, matched-information,
matched-compute controls — as the novelty candidate. "One semantic representation feeding
multiple systems" is explicitly recorded as **not novel**: OpenMath and MMT have done it for
two decades.

Per-component status is stated honestly, including that 𝒞 (concept registry) is **not
trustworthy** — red-teaming admitted three disguised duplicates — and that 𝒪 and
H1/H2/H3 are **untested**.

**Verification actually executed.**

| command | actual result |
|---------|---------------|
| `WebFetch arxiv.org/abs/2607.16372` | title, authors, date and both load-bearing quotes confirmed |
| `pytest tests/golden` | 84 passed — the no-superiority-claim gate accepts the new text |
| `./scripts/conformance.sh` | CONFORMANCE: PASS, all 8 stages |

**Failures and unresolved uncertainty.**

- The eight-part conjunction was not found in any published system, but that is a
  **search-based negative**, not proof of absence, and `GOAL.md` says so.
- X, Y and Z in the target result are **unmeasured**, and the document states it.
- The immediate bottleneck is unchanged and now stated as §8 of the goal: can `gemma4:31b`
  acquire one surface at ≥95% repaired parse and ≥90% fidelity? V0 managed 50–73%. Until a
  surface clears it, **every null result is uninterpretable.**

**Effect on the overall project.** The objective is now specific enough to be wrong in a
particular way, which is the property it previously lacked.

**Next intended step.** Freeze the V1 compiler and run the four-syntax Gemma acquisition
tournament.


---

## 2026-08-05 — host tuning measured; the example-compile gate was not enforcing its own rule

**Branch.** `hml-v1-concept-kernel`

**Project stage.** HML-PHASE-FG-001, preparation before the Phase F freeze.

**Objective.** Tune execution for this host (18 cores, 52 GB, `gemma4:31b` on Ollama) before
spending ~360 model calls on the tournament, and establish a clean conformance baseline.

**Files and systems changed.**

- `docs/evaluation/EXECUTION_ENVIRONMENT.md` — new; measured tuning, part of the F4 manifest
- `scripts/conformance.sh` — `pytest -n 18`; recursive, marker-aware example walk
- `tests/golden/test_examples_compile.py` — new; enforces CLAUDE.md rule 10
- `examples/candidate_syntaxes/README.md` + six `.illustrative` markers — new
- `examples/candidate_syntaxes/a_labelled_linear/{3_linear_regression,7_concept_definition}.hml` — fixed

**What was completed.**

Two findings, both measured.

*Ollama serialises by default.* `llama-server` ran with `-np 1`. Client concurrency bought
exactly nothing: wall time was linear in request count (12 requests x 2.8s = 33.2s) and
throughput was pinned at ~23 tok/s from 1 to 6 workers. With `OLLAMA_NUM_PARALLEL=4` the
same probe gave 22.8 / 35.1 / 47.4 / 32.7 tok/s at 1 / 2 / 4 / 8 workers — **2.08x at four
workers, degrading to 1.43x at eight**. Client concurrency must equal the slot count. The
harness will pin `max_workers=4`.

*The example gate was checking 8 of 43 files.* Conformance globbed `examples/*/*.hml`, one
level deep, so all 35 files under `examples/candidate_syntaxes/` were unchecked. Widening
to a recursive walk exposed that two files in `a_labelled_linear` — the **implemented**
syntax — no longer compiled: `3_linear_regression.hml` used `infer posterior` with no
prior (an error since D-016) and `7_concept_definition.hml` used unnamed invariants. In
both cases the compiler was right and the example was stale.

CLAUDE.md rule 10 claims `tests/golden` compiles every `.hml` under `examples/`. It did
not; `test_golden.py` referenced two files by name and globbed nothing. That is now true
rather than merely asserted.

**Decisions made and why.**

- The 28 non-L1 files are design sketches in surfaces the compiler does not accept, so they
  are marked `.illustrative` per directory rather than deleted — `c_sexpr` and
  `e_graph_triple` are the direct ancestors of candidates C and D in this milestone.
- The marker is a **directory file, not a filename convention**, because the sketches use
  different comment characters (`;`, `#`) and no single header syntax covers them.
- A test asserts each marker states a reason of >=30 characters and that the marker never
  covers `a_labelled_linear`. A bare `touch .illustrative` must not be able to silence a
  real failure.
- Reconfiguring Ollama is reversible: relaunching Ollama.app restores stock behaviour.
  `launchctl setenv` and shell exports both failed because Ollama.app respawns a server
  that does not inherit them; the app must be quit and `ollama serve` started manually.

**Tests and verification actually executed.**

| command | result |
|---------|--------|
| Ollama concurrency probe, `-np 1` | 23 tok/s flat across 1/2/4/6 workers |
| Ollama concurrency probe, `-np 4` | 2.08x at 4 workers; 1.43x at 8 |
| `ps aux \| grep llama-server` | confirmed `-c 32768 -np 4` after restart |
| `pytest -q` serial vs `-n 18` | 13.26s vs 6.53s |
| `pytest tests/golden/test_examples_compile.py -q` | 23 passed |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS**, all 8 stages |

**Failures and unresolved uncertainty.**

- `-np 4` splits the 32768-token context into four 8192-token slots. The
  50-demonstration curriculum must be measured against **8192**, not 32768. If it does not
  fit, the correct response is to drop to `-np 2` (16384 per slot, 1.54x), not to truncate
  a curriculum — a truncated curriculum is a different experimental condition. **Not yet
  measured**, because the curricula do not exist yet.
- The 2.08x figure comes from 160-token completions. Tournament completions are longer and
  prompts carry demonstrations; the ratio may differ and will be re-measured in G2.
- Whether the two stale examples indicate wider drift in unchecked corners is **unknown**;
  only `examples/` was audited.

**Effect on the overall project.** The tournament's dominant cost is now roughly halved,
and the project's own rule 10 is enforced rather than merely stated.

**Next intended step.** Integrate the three agents' Phase F output, then freeze and tag
`hml-v1-eval-freeze`.

---

## 2026-08-05 — Phase F4 freeze tooling; 50-demo curriculum measured against the slot

**Branch.** `hml-v1-concept-kernel`

**Project stage.** HML-PHASE-FG-001, Lead-owned Phase F4 preparation while three agents run
F1/F2/F3.

**Objective.** Make the Phase F4 freeze enforceable rather than declarative, and resolve the
context-budget risk recorded in the previous entry.

**Files and systems changed.**

- `evaluation/syntax_gate_freeze.py` — new; writes and **verifies** the F4 manifest
- `tests/freeze/test_syntax_gate_freeze.py` — new; 22 tests
- `docs/evaluation/EXECUTION_ENVIRONMENT.md` — curriculum token measurements added

**What was completed.**

*The context risk is resolved.* Measured with Ollama's `prompt_eval_count`, building
curricula from the 24 paired demonstrations in `benchmarks/representations/`: 0/5/10/25/50
demonstrations cost 66 / 643 / 1,286 / 2,967 / **5,893** prompt tokens. The largest
curriculum fits the 8192-token slot with ~2,300 tokens of completion headroom, so
`OLLAMA_NUM_PARALLEL=4` is safe for the whole tournament and the 2.08x speedup stands.
Growth is ~117 prompt tokens per demonstration.

*The freeze can now be checked.* `evaluation/freeze.py` only ever wrote a manifest. The new
module adds `--verify`, which recomputes every hash and exits non-zero on drift. It hashes
`FROZEN_TREES` wholesale, so an **added** file is drift too — a fifth renderer appearing in
a frozen tree changes the experiment as surely as an edited one. `--write` refuses to
overwrite an existing version.

**Decisions made and why.**

- The model is pinned by **digest** (`6316f0629137b426`, Q4_K_M, 31.3B), not by the tag
  `gemma4:31b`, because a tag can be reassigned to different weights.
- Policies (empty output, transport retry, repair, truncation, raw-output immutability) are
  data in the module and asserted by tests, not prose in a document. Truncation is a
  distinct failure category: folding it into parse failure would understate a syntax's
  token cost.
- A test asserts `client_max_workers == ollama_num_parallel`, so the measured 4-worker
  optimum cannot drift apart from the server configuration.

**Tests and verification actually executed.**

| command | result |
|---------|--------|
| curriculum probe via `prompt_eval_count` | 66 / 643 / 1,286 / 2,967 / 5,893 tokens; all fit 8192 |
| `pytest tests/freeze/test_syntax_gate_freeze.py -q` | **22 passed, 1 skipped** |
| `python -m evaluation.syntax_gate_freeze --verify` | correctly reports nothing frozen yet, exit 1 |
| `mypy src/hamiltonian_lang` | Success, 33 source files |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS**, all 8 stages |

**Failures and unresolved uncertainty.**

- A defect was found and fixed in the new module during testing: `Path.relative_to(REPO)`
  raised for any output path outside the repo, so every reporting call crashed under test.
  A reporting helper that can crash is worse than a long path; `_show()` now falls back to
  the absolute path.
- The skipped test is `V1_FREEZE_MANIFEST.md`, which the Phase F1 agent has not yet
  produced. The freeze deliberately treats it as `<MISSING>` rather than skipping it.
- The 5,893-token figure uses **existing V0 demonstration material**. If the frozen
  curricula are materially longer, this must be re-measured before Phase G2.
- The tournament has **not** been run and no model call beyond the tuning probes has been
  made. Nothing about syntax acquisition is known yet.

**Effect on the overall project.** "After the tag, no silent modifications are allowed" is
now a command that fails rather than a sentence in a document.

**Next intended step.** Integrate the three agents' F1/F2/F3 output, then tag
`hml-v1-eval-freeze` and begin Phase G2 screening.

---

## 2026-08-05 — Phase F agent integration; constitutional Phase 0 baseline

**Branch.** `hml-v1-concept-kernel`

**Project stage.** HML-CONSTITUTIONAL-CORE-001 Phase 0, integrating the three Phase F
agents.

**Objective.** Establish the real baseline before building the improvement control plane,
and resolve the suspected F2/F3 duplication centrally.

**Files and systems changed.**

- `docs/evaluation/CONSTITUTIONAL_CORE_BASELINE.md` — new; Phase 0 deliverable
- `docs/evaluation/PHASE1_LEAD_AUDIT.md` — new; the Lead's independent implementation audit
- `docs/evaluation/V1_FREEZE_MANIFEST.md`, `tests/freeze/{frozen_subset,test_quarantine}.py` — F1 agent
- `evaluation/syntax_acquisition/` (8 modules), `docs/design/syntax/` — F3 agent
- `evaluation/syntax_gate/` (9 modules), `tests/evaluation/test_syntax_gate_*.py` — F2 agent
- `src/hamiltonian_lang/backends/hml.py`, `tests/roundtrip/test_roundtrip.py` — F3 agent
- `tests/syntax_gate/test_information_equality.py` — new, Lead
- `tests/freeze/test_syntax_gate_freeze.py` — stale unconditional skip made conditional

**What was completed.**

*Baseline.* Commit `967e95d`; **3459 passed, 4 skipped, 1 xfailed**; conformance PASS on
all 8 stages without override. The suite grew from 1531 because the agents' uncommitted
work added ~1900 tests, all passing.

*F2/F3 — the suspected conflict did not exist.* I had flagged possible duplication because
both packages shipped candidate modules. That was wrong.
`evaluation/syntax_gate/candidates.py` is a binding layer: it defines the `SyntaxAdapter`
protocol, a decidable feature vocabulary that makes Track A membership a fact rather than a
judgement, and `SyntaxAcquisitionAdapter`, which converts F3's `SyntaxCandidate`
(`render(Module) -> str`, `parse(str) -> Module`) into the text-in/verdict-out form the
harness needs. Deleting either side would have destroyed working code.

*The fairness property is measured, not assumed.* All four candidate surfaces round-trip to
**hash-identical** canonical objects across `bayesian_coin`, `linear_regression`,
`kinetic_energy` and `quantifier_scope`. A new test pins this and fails loudly rather than
passing vacuously when an adapter is missing.

*A real round-trip defect was found and fixed by the F3 agent* in
`backends/hml.py`: the renderer parenthesised only the right operand, so `(a ^ b) ^ c`
printed as `a ^ b ^ c`, which reads back as `a ^ (b ^ c)` — a different object with a
different content hash. The same held for `(p => q) => r`. An associativity table now
drives bracketing.

**Decisions made and why.**

- Agent work is **preserved, not reverted**, because conformance passes on it and it
  contains a genuine compiler fix.
- The hypothesis register is written into the Phase 0 baseline as a first-class section,
  and H1/H2/H3 separation is enforced in the episode and evidence schemas rather than by
  prose. The user's requirement is to be able to look back in a year and know what went
  right versus wrong; a comment cannot carry that.
- Character counts per surface (A 237, B 256, C 289, **D 1907**) are recorded as an early
  cost signal and explicitly **not** as a token measurement or a verdict.

**Tests and verification actually executed.**

| command | result |
|---------|--------|
| `pytest -n 18` | **3459 passed, 4 skipped, 1 xfailed** |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS**, 8/8 stages |
| four-surface hash round-trip, 4 examples | **MATCH in all 16 cells** |
| `pytest tests/freeze` | 75 passed |
| `pytest tests/syntax_gate/test_information_equality.py` | 5 passed |
| minting disguise probes | byte-identical caught 4/4; **2 of 4 respellings admitted** |
| `hml check` probes for arity / `def` literal / PValue | all three defects reproduced |

**Failures and unresolved uncertainty.**

- **Three repair-loop blockers remain open** and are Subagent A's Phase 1 work: user-`def`
  calls check neither arity nor argument type; `const` and `def` disagree on the same
  literal; `PValue` is not an HML type.
- Concept minting is defeated by **definition respelling**, not by renaming. This corrects
  `GOAL.md` §3 and `semantic_objects.yaml`, which name rename/vacuous-constraint/alias —
  all three of those are now caught. The remedy is to canonicalise parsed definitions, not
  to harden the name check.
- The Lean backend closes every obligation with `sorry` **by design**, so `lean_verify`
  rejects its own backend's output before Lean runs. Lean is a sound gate with nothing able
  to pass through it, and must not be described as an available verification path.
- Two Phase F agents (F2, F3) terminated early on a session limit. Their work is complete
  enough to pass conformance but neither delivered its final report, so **their own
  accounts of what remains are unavailable**.
- **H1, H2 and H3 are all UNTESTED.** No model call has been made beyond tuning probes.

**Effect on the overall project.** The baseline is real rather than assumed, the suspected
duplication is disproven, and the tournament's central fairness property is now a passing
test instead of a design intention.

**Next intended step.** Subagents A, B and C deliver the Phase 1 repairs and the
improvement control plane; the Lead integrates and decides freeze eligibility.

---

## 2026-08-05 — M1 constitutional core: repair blockers closed, control plane landed

**Branch.** `hml-v1-concept-kernel`

**Project stage.** HML-MARKOV-TRANSITION-002, M1 integration.

**Objective.** Close the three repair-loop blockers, land the improvement control plane,
and establish the four-identifier hypothesis register before any model call.

**Files and systems changed.**

- `src/hamiltonian_lang/improvement/` — new package, 11 modules (Subagents B and C)
- `src/hamiltonian_lang/type_system/`, `types.py` — Phase 1 repairs (Subagent A)
- `tests/{improvement,constitutional,freeze,evaluation,roundtrip}/` — new suites
- `docs/evaluation/HYPOTHESIS_REGISTER.md`, `evaluation/manifests/hypotheses.json` — new
- `docs/evaluation/CONSTITUTIONAL_INTEGRATION_DECISIONS.md` — new, six conflict records
- `docs/evaluation/CONSTITUTIONAL_CORE_BASELINE.md` — Phase 0 deliverable
- `DECISIONS.md`, `spec/skills/`, `spec/v1/` — updated

**What was completed.**

*The three repair blockers are closed and independently verified by the Lead:*

| probe | result |
|---|---|
| `f(1.0)` on a 2-parameter `def` | `HML-T471: f takes 2 argument(s), 1 given` |
| `f(1.0, 2.0, 3.0)` | `HML-T471: ... 3 given` |
| `f(1.0, -2.0)` | `HML-T472: parameter 'y' (argument 2) requires PositiveReal` |
| `nosuch(1.0)` | `HML-N306: 'nosuch' is not a known function` |
| `const p : Probability = 0.5` vs `def p : Probability := 0.5` | **both ok** |
| `const pv : PValue = 0.05` | ok |
| `def posterior_h0 : Probability := pv` | `HML-T403` |
| `def observed_pvalue : PValue := p` | `HML-T403` |

*Ledger tamper detection reproduced by the Lead*, not accepted on report: forging a
payload **and** recomputing that line's own hash is still caught by the chain.

*The hypothesis register now carries four identifiers.* ACQ0 was separated from H1/H2/H3
because syntax acquisition is a **prerequisite**, and its compiler-assisted repair
(`ACQ0_REPAIR`) is not H3. Conflating them would let "the model learned to write the
syntax with compiler help" be misread as "verifier feedback improved reasoning".

**Decisions made and why.** Six conflicts recorded in
`CONSTITUTIONAL_INTEGRATION_DECISIONS.md`. The two that constrain future work:

- **CONF-003.** The canonical comparator treats hash inequality as wrongness. That is
  *correct for ACQ0*, where exact match is the definition of semantic preservation, and
  *forbidden for H1/H2*, where an equivalent-but-differently-shaped encoding is not a wrong
  answer. No H1/H2 number may be computed from it. A separate equivalence comparator is a
  prerequisite for M3.
- **CONF-004.** No module containing `require` can reach `VERIFIED`, because the checker
  collects an undischarged constraint obligation. Accepted as correct — auto-discharging to
  obtain `VERIFIED` would make the verdict meaningless. Consequence: with Lean also
  unusable, **`VERIFIED` is effectively unreachable**, so H3's stated primary endpoint
  (kernel-verified completion rate) is currently unmeasurable and must be resolved before
  M3.

**Tests and verification actually executed.**

| command | result |
|---------|--------|
| `pytest -n 18` | **3862 passed, 4 skipped, 1 xfailed** |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS**, 8/8 stages, no override |
| 10 `hml check` probes for 1A/1B/1C | all as specified, table above |
| ledger forge-and-rehash probe | detected |
| `gh repo view` | **PUBLIC** — see blockers |

**Failures and unresolved uncertainty.**

- **`REMOTE_SAFETY_BLOCKED`.** The remote `MoheetBrain/hamiltonian-lang` is **PUBLIC**. The
  directive requires it be private before any push. `gh repo edit --visibility private`
  was **denied at the permission layer**, so nothing was pushed. The remote holds only
  `965a7c7 Initial commit`; 15+ local commits of research are unpushed, so nothing has
  leaked. Zero stars and zero forks, so making it private costs nothing.
- Subagents A and C had not returned final reports when this commit was prepared;
  conformance passed and no file had changed for several minutes. Their own accounts of
  remaining limitations are therefore not yet in this entry.
- Conformance flipped FAIL then PASS during preparation as agents wrote; the failing run
  was transient and the passing run is the one recorded.
- **ACQ0 = BLOCKED. H1 = H2 = H3 = UNTESTED.** No model call has been made beyond tuning
  probes.

**Effect on the overall project.** The repair loop can now produce actionable diagnostics
for arity and argument-type errors, which were previously unrepairable by construction and
would have depressed any future H3 measurement for reasons unrelated to the hypothesis.

**Next intended step.** Unblock remote privacy, then M1 freeze manifests and tag.

---

## 2026-08-05 — M1 completed: all three subagents integrated; remote privatised and pushed

**Branch.** `hml-v1-concept-kernel`

**Project stage.** HML-MARKOV-TRANSITION-002, M1 completion.

**Objective.** Integrate the final subagent outputs, repair the Lead-owned defect Subagent
A found, and clear `REMOTE_SAFETY_BLOCKED`.

**Files and systems changed.**

- `evaluation/syntax_gate/harness.py` — `SCORING_WORKERS` now reads `HML_SCORING_WORKERS`
- `tests/evaluation/test_syntax_gate_harness.py` — regression test for the collision
- `tests/improvement/test_{evidence_package,hypothesis_separation,repair_arena,stage_controller}.py`,
  `improvement/{memory,runner}.py` — Subagent C's final work
- `.claude/settings.json` — the user removed `Bash(git push:*)` from the deny list

**What was completed.**

*A Lead-owned defect, found by Subagent A.* `scripts/conformance.sh` documents `HML_JOBS=1`
as the serial escape hatch for diagnosing ordering-dependent failures that `-n 18` hides.
`evaluation/syntax_gate/harness.py` read the **same** variable for `SCORING_WORKERS`, so
`HML_JOBS=1` set scoring concurrency to 1 and failed
`test_scoring_uses_the_cores_that_model_calls_cannot` on `1 >= 4`. **The documented
debugging tool broke the build for a reason unrelated to the bug being chased.** Two
concerns had collided on one name. Scoring now reads `HML_SCORING_WORKERS`, and a
regression test runs a subprocess with `HML_JOBS=1` to prove the knob no longer leaks.

*A defect I introduced while fixing it.* The first version of that regression test used
`importlib.reload`, which rebinds the module's exception classes — a reloaded
`PhaseGateError` is no longer the one sibling tests catch, so
`test_a_live_backend_is_refused_before_the_phase_f4_freeze` began failing. Replaced with a
subprocess, which cannot mutate this interpreter. A second slip left a stray `"""` and
broke collection; also fixed. Both are recorded because the ledger is for what happened,
not for what it would be tidier to have happened.

*Remote safety cleared.* The repository was **PUBLIC**. `gh repo edit --visibility private`
is denied by `.claude/settings.json`, so the user performed it; verified
`"isPrivate": true`. The user then removed `Bash(git push:*)` from the deny list while
**keeping** `gh repo edit` denied — push is permitted, visibility changes stay human-gated.

**Decisions made and why.**

- The env-var split is `HML_SCORING_WORKERS`, not a widened assertion. Relaxing
  `SCORING_WORKERS >= MAX_WORKERS` would have hidden a real constraint (measured: four
  client workers give 2.08x, eight degrade to 1.43x) to accommodate an unrelated knob.
- `.claude/settings.json` is committed rather than left dirty. It records the project's
  outward-action policy, and a policy that only exists in an untracked working file is not
  a policy.

**Tests and verification actually executed.**

| command | result |
|---------|--------|
| `pytest -n 18` (x3, checking flakiness) | **3974 passed, 4 skipped, 1 xfailed**, stable |
| `pytest tests/improvement` serial | all passed; not ordering-dependent |
| `HML_JOBS=1 pytest tests/evaluation/test_syntax_gate_harness.py` | 28 passed — knob restored |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS**, 8/8, no override |
| `gh repo view` | `"isPrivate": true, "visibility": "PRIVATE"` |

**Failures and unresolved uncertainty.**

- Subagent A added `PosteriorProbability` to the scalar lattice. Its brief said not to add
  it merely because a quarantine test names it; A's justification is that the stated
  invariant `PValue != PosteriorProbability` requires it. A rated its own confidence
  **medium**. Accepted, and flagged here so it is reviewable rather than assumed.
- **The mis-declaration residual is open and no type system can close it.**
  `param p_value : Probability` followed by `def posterior_h0 : Probability := p_value`
  compiles, because both sides genuinely *are* `Probability`. A correctly rejected
  inferring epistemic kind from spelling. Pinned by a test so it cannot be reported closed.
- **Seven of twelve expression positions still do not check contextually** (up from ten of
  twelve). The checker is **not** fully bidirectional and is not claimed to be.
- `HML-T428`'s `expectation(<law>)` branch is unreachable from source: `expectation` is a
  reserved keyword, so `expectation(d)` is `HML-P231` before the checker runs.
- **ACQ0 = BLOCKED, H1 = H2 = H3 = UNTESTED.** No model call beyond tuning probes.

**Effect on the overall project.** M1 is complete and pushable. The repair loop now emits
actionable arity and argument-type diagnostics that leak no values, which is a precondition
for any honest future H3 measurement.

**Next intended step.** Push, tag `hml-m1-constitutional-core`, then M2 calibration.

---

## 2026-08-05 — session-limit recovery: interrupted state preserved verbatim

**Branch.** `recovery/session-limit-2026-08-05` (from `hml-v1-concept-kernel` @ `9afafa8`)

**Project stage.** HML-RESUME-RECOVER-FREEZE-ACQ0-006, step 2.

**Objective.** Preserve every interrupted change before any integration edit. The dirty
tree is evidence.

**What was completed.**

Three subagents — Chain-of-Repair, format protocol, benchmark governance — terminated on an
API session limit (resets 23:20 Europe/London). Their partial work was on disk. A secret and
artefact scan over all 152 changed/untracked files found **nothing** to exclude: no
credentials, model blobs, virtualenvs, caches, or files over 1 MB. The tree was **green** at
capture: 4721 passed, `CONFORMANCE: PASS`, 8/8, no override.

`evaluation/manifests/session_limit_recovery.json` classifies every file by subsystem,
attributed agent and completion status: **94 COMPLETE, 47 INTERRUPTED, 5 MIXED, 6 REVIEW**.

**Decisions made and why.**

- **No replacement agents were spawned.** All three failed on the same shared session
  limit; new ones would fail identically and consume effort for nothing.
- The recovery commit is explicitly **not** a scientific freeze, and the document says so.
  Preserving and validating are different acts and must not share a commit.
- The three interrupted agents each stopped **while writing tests**, not implementation.
  Their implementation is present and the suite is green, but their leakage, verification
  and governance controls are the most likely omissions — the category whose absence is
  least visible. Nothing from those subsystems is treated as validated.

**Tests and verification actually executed.**

| command | result |
|---------|--------|
| secret/artefact scan over 152 files | clean on all four checks |
| `pytest -n 18` | **4721 passed, 4 skipped, 1 xfailed** |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS**, 8/8, no override |
| `gh repo view` | `"isPrivate": true` |

**Failures and unresolved uncertainty.**

- Chain-of-Repair, format protocol and benchmark governance are **INTERRUPTED, unaudited
  and unintegrated**. Their gate verdicts do not exist.
- **ACQ0 = UNTESTED. H1 = H2 = H3 = UNTESTED.** No model call beyond host-tuning probes:
  no context-budget probe, no 16-call calibration, no 48-call screen.
- The directive's later steps (M1.5 freeze, budget probe, calibration, Round 1) all require
  model calls or further agent work and are **not** reached in this entry.

**Effect on the overall project.** Roughly 152 files of multi-agent work — including two
completed M3 blockers — are now recoverable from a commit rather than only from a working
tree.

**Next intended step.** Audit on `integration/m1.5-paper-derived-closeout`; finish or
quarantine the three interrupted subsystems; then freeze M1.5.

---

## 2026-08-06 — M1.5: four agents integrated; two soundness defects closed

**Branch.** `integration/m1.5-paper-derived-closeout`

**Project stage.** HML-RESUME-RECOVER-FREEZE-ACQ0-006, integration.

**Objective.** Finish the three interrupted subsystems, falsify the four that reported
ready, and close whatever the falsifier finds.

**What was completed.**

All four resumed agents returned: `ACQ0_PROTOCOL_READY_FOR_PROBE`,
`HML_CHAIN_OF_REPAIR_READY`, `M3_LITE_CORPUS_READY`,
`M1_5_FALSIFICATION_FOUND_DEFECTS`.

*The falsifier earned its place.* Five reproduced defects, two of them soundness breaks in
endpoints that gate published numbers. Both are now closed by the Lead:

- **D-026 (F-2).** `partiality_risk` had no `Ref` case while `_to_sympy` inlines
  definitions, so the guard inspected a different expression from the one SymPy decided.
  `def q := x / x ; prove q = 1` with `x : Real` reached **VERIFIED** — false at zero — and
  `classify` inherited it. Reproduced by the Lead before fixing.
- **D-027 (F-1).** The Tier-1 name lock required *exact* vocabulary equality, so renaming
  one unused declaration disabled it and Tier 1 certified `p=>q` as equivalent to `q=>p`.
  A false-positive equivalence is the one error class the scorer trades coverage to avoid.

*Three further findings*, fixed by their owners or recorded: F-3 silent budget overflow
(`completion_allowance` unvalidated, now floored); F-4 repair-plan leak via statement
permutation; F-5 a soundness allowlist re-exported by value, giving two disagreeing copies.

*The interrupted agents' own controls were the missing part*, as predicted. Chain-of-Repair
found its leakage harness reported a **floor effect as a finding** — `PLAN_NOT_USEFUL` with
reasoning explaining a gain that never occurred — and a pre-existing test built on a
**ceiling fixture**, demonstrating "C fails to beat A" using a case where C cannot. Every
fixture was a stipulation: the scripted probe ignored its inputs entirely.

*The governance fixture was worse than "does not compile".* It declared `centre : Real`,
making the role swap visible to the type checker, so gate 1 rejected it and gate 2 never
ran — **the test asserted the opposite of its own thesis.** Quarantine lifted only after 15
targeted mutations were each shown to fail the guarding test.

*The stale token figure was not merely stale — the 50-demo curriculum is impossible.*
Estimated on frozen material: A 9,857, D **35,321** tokens against a 5,888 ceiling. D
exceeds the entire 32,768 context; at 10 demos D alone (8,494) exceeds the 8,192 slot. At 5
demos D fits `4x8192` only if the real tokeniser beats 2.48 chars/token — genuinely
undecidable offline, which is exactly why the probe must run.

**Tests and verification actually executed.**

| command | result |
|---------|--------|
| `pytest -n 18` | **4927 passed, 4 skipped, 7 xfailed, 7 xpassed** |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS**, 8/8, no override |
| `ruff check src tests` · `mypy src/hamiltonian_lang` | clean · Success, 76 files |
| D-026 probes | `def q := x/x` with `x : Real` UNSUPPORTED; with `PositiveReal` VERIFIED |
| D-027 probes | `a>b`/`b>a`, `a-b>0`/`b-a>0`, `a/b=2`/`b/a=2` all COUNTEREXAMPLE_FOUND under both spare variants; `a=a`/`b=b` still EQUIVALENT |
| equivalence benchmark | 49/49 decided, precision 1.000, **0 false positives** |

**Failures and unresolved uncertainty.**

- **A Lead verification was incomplete and the falsifier caught it.** "VERIFIED is
  reachable and refusable" was established on the *direct* form only; the indirect form
  behind a `def` was never tested and was unsound. Recorded in D-026.
- The 49-pair equivalence corpus contains **no spare-rename case**, so precision 1.000 was
  untested exactly where model output will hit it. D-027 is pinned by the falsifier's
  adversarial tests, not by the corpus.
- Repair-plan **usefulness** (`C > A`, `C > D`) is unmeasurable offline; every measured
  B rate is exactly 0.0 or 1.0, so the 0.10 leak threshold has never discriminated.
- **No token count anywhere is a measurement.** Every figure is a character estimate; the
  probe is built, stub-tested, and unrun. The five-example curriculum is PROVISIONAL.
- **ACQ0 = UNTESTED. H1 = H2 = H3 = UNTESTED.** No experimental model call has been made.

**Effect on the overall project.** Two endpoints that would have gated published numbers
were unsound and are now sound. The context budget is known to be the binding constraint,
and known not yet to be measured.

**Next intended step.** Freeze and tag M1.5, then run the authoritative context-budget
probe.

---

## 2026-08-06 — M2 context budget measured; shared runtime frozen

**Branch.** `integration/m1.5-paper-derived-closeout`

**Objective.** Replace character estimates with authoritative `prompt_eval_count` and
select one shared runtime.

**What was completed.** The ladder probe ran to completion (1234 s) and Agent 1 audited it
rather than rerunning it. All five conditions fit `4 x 8192` at curriculum size 5:

| condition | prompt_eval_count | ch/tok | headroom |
|---|---:|---:|---:|
| A_v0_labelled_linear | 1880 | 3.63 | 4008 |
| B_v1_labelled_linear_simplified | 1887 | 3.62 | 4001 |
| C_prefix_sexpr | 2074 | 3.45 | 3814 |
| D_constrained_json_graph | **4907** | 3.30 | **981** |
| SE_structured_english | 1829 | 4.18 | 4059 |

**Decisions.** Shared runtime `4 x 8192`; curriculum size 5 (measured). n=6 projects to
5469 and fits, but is **unmeasured** and may not be used without measurement.

**Corrections to earlier records.** The character projection of ~35,321 tokens for
candidate D at 50 demonstrations was pessimistic by about a third; at the frozen size of
five D measures 4907 and fits. **Candidate D is not eliminated on budget.** An earlier Lead
report repeated the projection as though it settled the question; it did not.

**Verification.** `pytest -n 18` all passed; `./scripts/conformance.sh` **PASS**;
`ruff check src tests` clean; `mypy` Success, 76 files. Model digest verified unchanged.

**Failures and unresolved uncertainty.**

- Five transport timeouts, caused by `probe.py` sending `num_ctx` per call, which forces a
  full 24 GB model reload on every rung change. Recorded `UNDETERMINED`, never as small
  prompts. Closed for SE by one re-measurement at `timeout_s=600`; **no scientific prompt
  was altered.**
- **Governance defect (Lead):** the probe was authorised with `call_budget=400` against a
  15-call plan. The counts are physical and sound; the authorisation record is not, and
  `ladder_report.json` carries the wrong figure.
- `candidate_conditions()` returns 4 conditions while the probe actually measures 5. The
  probe logged 4 and measured 5, which is why SE's timeout went unanticipated.
- **SE's count is a proxy.** Passing `pool=` changes worst-case selection, so SE was
  measured on 7645 chars rather than its true worst 7655. ~2 tokens against 4059 headroom;
  verdict unaffected, but the two selections must be reconciled before the tournament.
- Agent 1 lost one otherwise-good measurement to a serialiser bug of its own and recorded
  it as a harness fault rather than a transport retry.
- Harness transport retries issued: **0** — the counter records `ABSENT` rather than
  retrying.

**Effect.** The tournament can be run fairly at `4 x 8192`. This is not ACQ0 evidence.

**Next.** Resolve the ACQ0 oracle-scoping question, then run the 16-condition calibration.

---

## 2026-08-06 — ACQ0 instrument rebuilt: canonical v2, one authority

**Branch.** `integration/m1.5-paper-derived-closeout`

**Objective.** Replace an evaluation corpus that could not measure what it claimed to.

**What was completed.**

*The v1 corpus is inadmissible, 41 of 41.* Mathematics lived in three independently
authored places — prose, a `SemanticFacts(...)` **repr string**, and a private reference —
with nothing forcing agreement. In `assumption_boundary_000` the prose said "varrho of an
argument equals 5 divided by that argument" while the reference wrote `eta / mu` with
`eta = 5`. Same function, different canonical hash. A frontier model followed the prose and
was scored FAIL; it also added a `prove` statement invited by a question posed while
`objective=None`. **That was a scoring-instrument failure, not a model failure**, and the
earlier FAIL verdict is withdrawn.

Defect counts across the 41: question-without-objective 41 · entity-absent-from-prose 38 ·
function-body-missing 10 · assumption-not-declared 6 · derived-fact-as-premise 4 ·
public-insufficient 3 · const-without-initialiser 2.

*`CanonicalAcq0TaskV2`* makes the compiled source the sole authored mathematics and derives
the structured target, prose, four surface renderings, reference and expected hash from it.
No second mathematical AST was created — the compiler's AST is the AST. Seven invariants
are enforced at construction, each rejecting a defect the audit actually found.

*Eight proof tasks*, one per family, fresh unexposed ids, **8/8 admissible**, exact
round-trips through A/B/C/D, ACQ0 and H2 views provably distinct.

**Decisions made and why.**

- The authority is the compiled source, not a parallel description of it. Editing prose
  would not have fixed a defect whose cause is that three artefacts could be authored
  separately at all.
- v1 ids stay quarantined with their evidence; v2 ids carry a `v2_` prefix and a test
  enforces it. No exposed id is reused.
- Surface B was **not** changed. Its grammar renders `mod` / `dec const … :=` / `fun` and
  accepts exactly what it renders; the ChatGPT output imported with zero diagnostics. The
  suspected `def`/`fun` conflict was documentation prose and did not reproduce.
- No HML syntax, keyword, canonical form or type changed anywhere.

**Tests and verification actually executed.**

| command | result |
|---|---|
| `pytest -n 18` | **5191 passed**, 4 skipped, 7 xfailed, 7 xpassed |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS**, 8/8, no override |
| 8 tasks x 4 surfaces round-trip | **32/32 exact** |
| identity sensitivity (7 properties) | all correct |
| `pytest tests/evaluation/test_acq0_canonical_v2.py` | 108 passed |

**Failures and unresolved uncertainty.**

- **Both protocol calibrations are void.** v1 hit the 2048-token completion cap on 56 of 76
  generations; v2 ran on `binding_chain_002` and `distribution_law_002`, both
  `INVALID_INSTRUMENT`. Different causes, same outcome: **no protocol has been validly
  selected.** All 32 raw records are preserved.
- The 41-task regeneration is **not** attempted.
- Epistemic categories are structural (assume/require/prove), not per-statement labels.
- Prose is machine-plain; its readability to a model is unmeasured.
- **No model has seen any v2 task.** Admission proves the instrument is self-consistent, not
  that a model can encode it.

**Effect.** ACQ0 has an instrument that can measure a model rather than its own corpus.

**Next.** Human-review hardening audit of the v2 architecture.

---

## 2026-08-06 — ACQ0 v2 hardening audit: two defects in v2 itself

**Branch.** `integration/m1.5-paper-derived-closeout` (checkpoint `986f4ee`)

**Objective.** Audit the v2 architecture against its own claims and fix what fails.

**What was completed.** Two real defects were found **in v2 itself** and fixed.

*1. Semantic metadata sat outside canonical identity.* `derived_facts` and
`prohibited_assumptions` reach model-visible prose, yet two tasks differing only in them
shared a canonical hash — semantic metadata affecting a renderer while excluded from
identity. Fixed by separating two identities that had been conflated:

- `canonical_hash` — the **encoding's** identity, from the compiled AST alone. Metadata is
  excluded *on purpose*: a model encodes mathematics, not prohibitions, and this is what it
  is scored against.
- `semantic_identity` — the **task's** identity, AST plus every SEMANTIC metadata field.

Every field is now classified `SEMANTIC` / `PRESENTATION_ONLY` / `OPERATIONAL_ONLY`, and a
test fails if a field is added without a classification. The documented authority wording
was corrected from *"the reference encoding is the authority"* to *"the normalised compiler
AST plus validated semantic metadata"*.

*2. An unguarded partial definition was admitted.* `def varrho(mu : Real) := eta / mu`
declares totality over `Real` while being undefined at zero. The obligation engine returns
`VERIFIED` for it **and for the guarded spelling alike** — it generates no definedness
obligation over a binder's declared domain at all. This project's own proof task carried
the defect. The binder is now `PositiveReal`; the corpus does not assume non-zeroness on
the model's behalf.

*3. `state_in_prose` disposition.* Changes prose and task identity; provably does **not**
change the structured target ACQ0 scores, so it cannot hide a scored fact.

**Tests and verification actually executed.**

| command | result |
|---|---|
| `pytest -n 18` | **5206 passed**, 4 skipped, 7 xfailed, 7 xpassed |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS**, 8/8, no override |
| 8 tasks x 4 surfaces after the corpus fix | **32/32 exact** |
| `e / mu` with `mu:Real` / `mu:PositiveReal` / `e * mu` | REJECTED / ADMITTED / ADMITTED |

**Failures and unresolved uncertainty.**

- **The compiler generates no definedness obligation over a binder's declared domain.** The
  guard added here is corpus-side admission, not a compiler fix, and covers division by a
  **bare binder only** — not division by an arbitrary expression, `sqrt`, `log` or indexing.
- **Audit sections C, F, H, I and J are not complete**: prose clause-to-fact exact
  coverage, structured-target reversibility, the safe-bundle leakage seal, the ACQ0/H2/H3
  firewall test, and the human-review packet.
- The protocol calibration agent returned `PROTOCOL_UNSTABLE`: 50% of generation events hit
  the cap, all 8 pairs tied, zero VERIFIED. It confirmed the allowance diagnosis —
  `DIRECT_FORMAL` at 6144 capped 0/8 — but the same 6144 split as 2048+4096 capped 12/16,
  and it ran on two `INVALID_INSTRUMENT` tasks. No protocol is selected.

**Effect.** The v2 authority claim is now true as stated rather than approximately true.

**Next.** Complete the remaining audit sections, or accept the current hardening for review.

---

## 2026-08-06 — ACQ0 v2 audit sections 0, C, F, H, I, J completed

**Branch.** `integration/m1.5-paper-derived-closeout` (from `b454f4e`)

**Objective.** Complete the remaining hardening-audit sections.

**What was completed.** Three further defects were found **in v2 itself**.

*Section 0 — the classification was self-contradictory.* `state_in_prose` sat inside
`semantic_identity`, so a PRESENTATION_ONLY field altered task identity. The derived fact
and its provenance are SEMANTIC; whether an already-visible fact is *redundantly repeated
in prose* is presentation. The flag is now excluded from identity; the fact is still in it.

*Section F — an ambiguous codomain, in this project's own corpus.*
`v2_dimensional_algebra_001` used `def pressure := force / area` with no declared codomain.
An annotated and an unannotated definition **hash differently**, so the model-visible
`codomain: None` left an encoder unable to know which spelling was meant — the v1 ambiguity
class, recurring in its replacement. The task now declares its codomain, and the schema
rejects any definition without one.

*Section H — the leak check could not fail.* It compared raw text against a JSON-escaped
blob, so `\n` never matched `\\n` and every containment check silently passed. Found by its
own negative control. The scan is now whitespace-normalised. The bundle hash is unchanged,
so the fix tightened the check without altering the artefact.

*Sections C, I, J* delivered: a fact-provenance layer giving exact prose coverage (set
equality, not substring presence); a mode gate refusing an ACQ0 semantic diff outside
`Mode.ACQ0`; and a private human-review packet.

**Tests and verification actually executed.**

| command | result |
|---|---|
| `pytest -n 18` | **5250 passed**, 4 skipped, 7 xfailed, 7 xpassed |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS**, 8/8, no override |
| prose exact coverage | **8/8 EXACT** (6–19 facts per task) |
| structured-target reversibility | **8/8 exact** after the codomain fix |
| A/B/C/D round-trips | **32/32 exact** |
| firewall | ACQ0 permitted; H2 and H3 refused |
| safe bundle | 7 parts, hash `204ad665821a3c69…`, leakage NONE |

**Failures and unresolved uncertainty.**

- **The compiler generates no definedness obligation over a binder's declared domain.** The
  guard is corpus-side and detects division by a **bare binder** only — not compound
  denominators, `sqrt`, `log`, negative or fractional powers, indexing, or partiality
  reachable through a chain of definitions. Documented as fail-closed.
- One hardening test was migrated rather than deleted: it asserted the pre-section-0
  behaviour, and its docstring records why the expectation reversed.
- **No model has seen any v2 task.** Every property here is about the instrument.

**Effect.** The v2 instrument's claims are now executable checks rather than assertions,
and three of its own defects were found by them.

**Next.** Human inspection of the review packet, then a decision on manual frontier testing.

---

## 2026-08-06 — repair the generator and the model-visible view, not the answers

**Branch.** `integration/m1.5-paper-derived-closeout` · **Stage.** ACQ0 v2 instrument
repair, before any model call.

**Objective.** A line-by-line English-versus-formal review of all eight v2 tasks was
requested with a standing rule: *any uncertainty means UNSURE — do not admit.* Four tasks
came back unsure or worse. The instruction that followed was explicit — repair the
generator and the model-visible view, not the individual answers.

**What was actually wrong.** The artefact handed to a model was insufficient to produce the
reference it would be scored against.

`structured_target()` partitioned each module into unordered kind-buckets — declarations,
assumptions, requirements — while `content_hash` is **order-sensitive**. Nothing in the view
said that `v2_transformation_side_condition_001` puts `require` before `assume`, so that
task was unencodable; two others were unencodable for the same reason, and the remaining
five passed only because their source order happened to coincide with the bucket order. A
fourth defect was worse in kind: `structured_target()` had no `CheckStmt` branch, so
`check dimension pressure = …` existed in the reference and in **no** model-visible artefact
at all.

**Why the existing checks could not have found it.** `check_prose_coverage`,
`reconstruct_semantic_payload` and the 32/32 surface round-trip each validated an artefact
**against itself** — the first two derive from `structured_target()` and re-read its own
keys; the third renders from `task.source` and never traverses the view. The loss lived
exactly on the boundary between the view and the source, and none of them crossed it. This
is the second time this instrument has failed on self-validation; the first cost the entire
41-task v1 corpus.

**Files and systems changed.**

- `evaluation/corpus_governance/v2_view.py` (new) — `encoding_view` (one positional list;
  `position`, `statement_id`, `kind`, structured content, `epistemic_role`, explicit
  `emit`; a `CheckStmt` branch; `UnsupportedStatement` for anything unrepresented),
  `reconstruct_source` (reads the view and nothing else), `view_reconstructs_exactly`.
- `evaluation/corpus_governance/v2_render.py` — `render_prose` rewritten to walk encoding
  order by position; the kind-bucket version deleted, not deprecated; `acq0_view` now serves
  the ordered view.
- `evaluation/corpus_governance/v2_corpus/tasks.py` — two tasks replaced under **fresh ids**
  because their mathematics changed.
- `tests/evaluation/test_acq0_view_reconstruction.py` (new, 50 tests).
- `DECISIONS.md` — D-029 (DIRECT_FORMAL as the primary protocol), D-030 (the ordered view
  and the reconstruction gate).
- `evaluation/results/acq0/superseded_tasks/SUPERSEDED.md`,
  `docs/evaluation/ACQ0_V2_HUMAN_REVIEW_PACKET_R2.md`.

**Decisions made and why.**

*The gate is reconstruction from the view alone* (D-030). A function permitted to read the
view and nothing else must rebuild a module that compiles to the reference hash. If a task
cannot survive that, a model cannot encode it, and no amount of model capability changes the
outcome. Missing fields raise rather than default — defaulting is how an encoder gets blamed
for information it never had.

*Two tasks were replaced, not patched.* `v2_approximation_equality_001` stated a **one-sided**
bound, satisfied by an estimate arbitrarily far below the target; it encoded uniquely but did
not express the contrast its family claims. HML has no absolute-value form, so the
replacement states both inequalities explicitly. `v2_dimensional_algebra_001` divided by
`area`, a module-level `var` admitting zero — outside the binder-only partiality guard and
**unguardable**, because `require area != 0` does not compile (HML-D502: a
`Quantity[Length^2]` is not comparable to a dimensionless `0`). The replacement uses
multiplication, which is total. Fresh ids in both cases: the mathematics changed, so the
identity must.

**Tests and verification actually executed.**

| command | result |
|---|---|
| `.venv/bin/python -m pytest` | **5300 passed**, 4 skipped, 7 xfailed, 7 xpassed |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS** |
| `.venv/bin/ruff check src tests evaluation/` | **All checks passed** |
| `.venv/bin/mypy src` | **Success: no issues found in 84 source files** |
| view-only reconstruction | **8/8 exact** |
| every emitted statement exactly once | **8/8** |
| A/B/C/D round-trips | **32/32 exact** |
| reference self-score | **8/8** |
| `audit_task` admission | **8/8, zero defects** |
| view separation, bundle leak scan | 8/8 clean, no exception raised |

**Failures and unresolved uncertainty.**

- **No task is marked human-approved.** The gates prove a task *can* be encoded from what
  the model is given. They cannot prove the English says what the formal version says. That
  is exactly the judgement the review was asked for, and it is not automatable.
- The partiality guard remains **binder-only**. Compound denominators, `sqrt`, `log`,
  negative or fractional powers, indexing, and partiality through a chain of definitions are
  not detected. The dimensional task was replaced rather than guarded for this reason.
- The 12-task development taxonomy was **not located**, so no continuation tasks were
  authored. Per the standing instruction this is reported, not worked around.
- The prose-order test asserts a token correspondence per emitted statement, not full
  semantic agreement between prose and encoding. It would not catch a faithful-looking
  clause that means something else.

**Effect on the overall project.** The instrument now has one check that crosses the
boundary where information is actually lost, and nine negative controls proving that check
can fail. Two mathematically defective tasks are out of the corpus and preserved with
reasons. Model testing remains blocked on human review — correctly.

**Next.** Human review of `ACQ0_V2_HUMAN_REVIEW_PACKET_R2.md`. If it passes, locate or
freeze the development taxonomy before authoring four continuation tasks and two sealed
spares.
