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

---

## 2026-08-06 — admit the ACQ0 v2 development corpus: 12 tasks + 2 sealed spares

**Branch.** `integration/m1.5-paper-derived-closeout` · **Stage.** ACQ0 corpus admission,
before any model call.

**Objective.** Close the three remaining corpus gates — independent semantic review, a real
partiality scanner, a frozen taxonomy — and freeze the minimum valid development corpus.

**Files and systems changed.** `evaluation/corpus_governance/`: new `partiality.py` and
`taxonomy.py`; `canonical_v2.py`, `v2_view.py`, `v2_facts.py`, `v2_render.py`,
`v2_bundle.py`, `v2_firewall.py`, `task_admission.py`, `v2_corpus/tasks.py` all modified.
`evaluation/acq0/v2/`: `prompt.py` rewritten, new `budget.py` and `run.py`. New tests
`test_partiality_scanner.py` and `test_taxonomy_coverage.py`; four existing test modules
updated. New docs `ACQ0_V2_TAXONOMY.md`, `ACQ0_V2_INDEPENDENT_SEMANTIC_REVIEW.md`,
`model_files/SHARED_HML_SEMANTICS.md`. D-031 and D-032 in `DECISIONS.md`.

**What was completed.**

*Independent semantic review, two rounds, four read-only reviewers.* Round 1 on the original
eight; round 2 on the six authored after. Round 2 was not a formality: all four
objective-bearing tasks are in it, so round 1 could not have seen the defect class they
carry.

*Thirteen findings, every one repaired at the generator.* Five were governance-layer defects
rather than task defects: `build_bundle` still served the retired bucketed target; the
bundle pointed at a shared-semantics document that **does not exist in this repository**;
`structured_target()` dropped `CheckStmt` everywhere downstream, so the coverage check
certified a task whose defining statement it could not see and the semantic diff scored a
dropped `check` as unequal with an **empty difference list**; the objective was stated twice
in prose in a form that compiles to a different hash; and a derived fact's provenance
`("param lambda : PositiveReal",)` reached prose verbatim — one line of the surface-A answer,
which the whole-rendering leak scan could not see.

*Two tasks rejected on their mathematics and replaced under fresh ids.*
`v2_quantifier_scope_002`'s premise `exists b : Real . forall x : Real . x < b` is **false**
— instantiate at `x := b` and it says `b < b` — so the hypothesis set was inconsistent and
entailed the very converse the task prohibited, while its goal was a theorem and the
assumption inert. `v2_dimensional_algebra_003` named a definition `kinetic_energy` while
omitting the ½; `0.5 * mass * speed ^ 2` compiles *and* passes the same dimension check, so
a model that knows physics would be scored FAIL on a hash difference. Both preserved with
reasons in `SUPERSEDED.md`.

*A real partiality scanner* replaces the binder-only guard: every expression position,
definition dependencies followed, module variables, compound denominators, negative and
fractional powers, variable exponents, `sqrt`/`log`/`tan`, indexing, concept bodies. It
prints a named risk path, marks a dimensioned denominator UNGUARDABLE (HML-D502), and fails
closed on an unwired statement kind. The review found it failing **open** on `concept`
blocks and unable to distinguish "clean" from "never looked"; both are closed and pinned.

*The taxonomy is frozen* at twelve cells, generated from `taxonomy.py` and enforced by
tests. All twelve covered, all six coverage rules met.

**Decisions made and why.** D-031: an objective must name the kind of goal the source
states, with `decide` discharged by a `CheckStmt` — the previous bare existence test made
the objective-bearing check cell inexpressible, and widening the goal set unconditionally
would have retroactively invalidated a task whose `check` is a property of the object rather
than the point of the task. D-032: demonstrations are authored and never drawn from the
scored corpus, because `PROOF_CORPUS[:5]` showed one task's answer while the model encoded
another and gave demo tasks one fewer demonstration than non-demo tasks; and they now show
the view→encoding mapping, because rendering the encoding alone measures guessability rather
than expressiveness.

**Tests and verification actually executed.**

| command | result |
|---|---|
| `.venv/bin/python -m pytest` | **5557 passed**, 4 skipped, 7 xfailed, 7 xpassed |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS** |
| `ruff check evaluation tests src` · `mypy src` | All checks passed · 84 files clean |
| view-only reconstruction | **14/14 exact** |
| A/B/C/D round-trips | **56/56 exact** |
| reference self-score · prose coverage · partiality · admission | 14/14 each |
| scorer self-check (offline, no model) | **48/48**; a dropped statement scores not-exact |
| semantic diff on a dropped `check` | names `position 4, missing statement, check_dimension` |
| contamination vs every previously-shown split | **0 collisions**, max overlap 0.021 / 0.60 |
| leak scan negative control | fires on a planted reference line |

**Failures and unresolved uncertainty.**

- **No automated gate can catch what rejected the two tasks.** There is no satisfiability,
  entailment or truth check anywhere in the admission path — `assume 1 > 2` compiles and
  scans ACCEPT — and no name/body coherence check. Both rejections came from review.
- **The contamination gate would not have caught the kinetic-energy case**: structural
  reproduction with one term deleted scores ~0.04 against a 0.60 threshold.
- **This is not human review.** Two agent reviewers, labelled as such. It clears a
  developmental screen, not a promotion benchmark.
- Cells 4 and 8 have a single carrier each and no spare. Stated, not hidden.
- **No model has seen any v2 task.** Every number above is a property of the instrument.

**Effect on the overall project.** The corpus is admissible on all fourteen gates and the
instrument is ready for a developmental acquisition run.

**Next intended step.** Re-measure the prompt budget against the frozen runtime, then
Tranche A.

---

## 2026-08-06 — instrument GREEN, budget re-measured, and a discarded Tranche A attempt

**Branch.** `integration/m1.5-paper-derived-closeout` · **Stage.** ACQ0 developmental
acquisition run.

**Objective.** Declare the instrument green, re-measure the prompt budget against the frozen
runtime, and begin Tranche A.

**What was completed.**

*MEASUREMENT_INSTRUMENT_GREEN recorded.* Every stated condition was checked, not asserted.
The label means suitable for a developmental model experiment — not officially
human-approved, not promotion-ready, not mathematically exhaustive.

*The prompt budget was re-measured* with the **same builder the run uses**, which is the
property v1 broke. Frozen runtime `-c 32768 -np 2`: slot 16384, completion 6144, reserve
256, ceiling 9984. Selection followed the directive — render all twelve prompts per surface
offline, take the longest, add any within 2%. Worst case in every surface is
`v2_quantifier_scope_003`: A 3177, B 3179, C 3329, D 5056 tokens, headroom 6807 / 6805 /
6655 / 4928. All four fit; no surface was shortened.

*The first Tranche A attempt was discarded after three conditions, and the defect is the
point.* Candidate C's specification advertises the fence tags `sexpr`, `lisp` and `scheme`.
The model answered inside a ```lisp fence, and the encoding **inside** it was
hash-identical to the reference — but the raw text was handed to the importer fence and
all, so the import failed and the condition scored parse=0. Surface C would have been
eliminated on a harness defect, and the elimination would have been reported as a property
of the notation.

**Decisions made and why.** The scorer strips any fence, not only advertised tags: refusing
an unadvertised tag measures instruction-following, which is a different experiment.

**Tests and verification actually executed.**

| command | result |
|---|---|
| budget probe, 4 surfaces, authoritative `prompt_eval_count` | 4/4 FIT |
| `tests/evaluation/test_acq0_scoring.py` | 84 passed — reference self-scores exact for every task x surface; a fenced answer scores identically for 7 tags x 4 surfaces; a dropped statement, a reordered module and prose all score not-exact |
| re-scored condition 3 after the fix | `C_prefix_sexpr` parse=1 exact=1, previously parse=0 |

**Failures and unresolved uncertainty.**

- Tranche A is **incomplete at the time of writing**: three of thirty-two conditions.
- The fence defect was found by inspecting the first three records. It was not predicted by
  any test, and no test existed that could have failed. There is no general guarantee that
  another harness defect of this class is not present.
- Generation cost is uneven: 16s for A, 110s for B, 62s for C on the same task, and B spent
  1691 completion tokens on a four-statement module. Latency is recorded per condition but
  is not part of any gate.

**Effect.** The budget is frozen against real measurements, and the scorer no longer
penalises a correct answer for its packaging.

**Next intended step.** Complete Tranche A and apply the preregistered continuation rule.

---

## 2026-08-06 — Tranche A closed MEASUREMENT_INVALID; surface D eliminated by upper bound

**Branch.** `integration/m1.5-paper-derived-closeout` · **Stage.** ACQ0 measurement recovery.

**Objective.** Close the invalid run honestly, preserve every record with a manifest, and
eliminate the one surface that needs no rerun.

**Files and systems changed.** `evaluation/results/acq0/v2_tranche_a/`: 32 immutable
condition records (unchanged), new `MEASUREMENT_INVALID.md` and `RUN_MANIFEST.json`. D-033
in `DECISIONS.md`. No instrument file was touched — not the corpus, prompts, demonstrations,
surfaces, importer, canonicaliser, scorer, comparator or thresholds.

**What was completed.** The run finished all 32 conditions. Integrity audited clean on every
axis except the cap: matrix complete, one immutable record per condition, all 35 required
fields present, every recorded prompt hashes its own recorded prompt AND matches the frozen
builder today, every bundle hash recomputes, zero transport failures, zero empty attempts,
and no tracked repository file was altered during measurement.

**Three conditions hit the 6,144-token completion allowance**, and the truncation is
outcome-determining. Surface A is 7/8 exact and fails the gate *solely* on that one
truncation. Surface C's truncated condition is one of its three non-parses. The truncated
attempts show deliberation, not inexpressibility: the model wrote a correct surface-A
encoding, replied `-> NO!` to itself, restarted and ran out of budget, while answering the
same task cleanly in surface B.

**Surface D was eliminated by upper bound**, mechanically: repaired parse 0/8; exactly one
truncated record, in repair only; best attainable 1/8; frozen threshold 6/8.

**Decisions made and why.** D-033. The run is void rather than "a result with three bad
conditions", because reporting A and C as non-viable would publish a confidently wrong claim
about two notations on the strength of a harness parameter — the same mechanism that voided
the v1 calibration at 2,048 tokens. The cap was not forced by the runtime: ~13,000 tokens
were free in the slot.

**Tests and verification actually executed.**

| check | result |
|---|---|
| task x surface matrix | complete 8x4, 0 missing, 0 duplicate |
| required fields, all records | 32/32 |
| recorded prompt hash == its own prompt | 32/32 |
| recorded prompt hash == frozen builder today | 32/32, no drift |
| bundle hashes recomputable | 32/32 |
| transport failures / empty attempts | 0 / 0 |
| truncations | **3** — two attempt-zero, one repair |
| D upper bound | 0/8 + 1 truncated = **1/8 < 6/8** |

**Failures and unresolved uncertainty.**

- The completion allowance is a chosen parameter that was set before the corpus's generation
  behaviour was known, and nothing predicted the deliberation loops. No test could have
  failed here; the defect was found by auditing finish reasons.
- Whether 12,288 is sufficient is **not yet known** — that is what the cap probe is for.
- The exploratory table is preserved but is not evidence about any surface.

**Effect.** No invalid number enters any aggregate, and one surface is closed out on
arithmetic rather than on a rerun.

**Next intended step.** A two-condition operational cap probe at 12,288 on the two prompts
that truncated, then a clean 8x3 survivor rerun if both finish normally.

---

## 2026-08-06 — cap probe at 12,288 fails; the survivor rerun is not launched

**Branch.** `integration/m1.5-paper-derived-closeout` · **Stage.** ACQ0 measurement recovery.

**Objective.** Establish whether a 12,288-token completion allowance removes the truncation
that voided Tranche A, before spending a 24-condition scientific rerun on it.

**Files and systems changed.** New
`evaluation/results/acq0/operational_calibration/cap_probe_12288/` with two probe records, a
summary and `CAP_CALIBRATION_FAILED.md`. No instrument file touched.

**What was completed.** Both frozen prompts were re-run at allowance 12,288 with identical
prompt bytes, bundle hashes, model digest, temperature 0, seed 0 and runtime; only the
allowance changed. The cached replies were bypassed deliberately, since the cached ones were
the capped ones.

**Result: both reached the cap exactly and truncated.** A: prompt 2,945, completion 12,288,
`length`, 620s. C: prompt 3,097, completion 12,288, `length`, 659s. The budget inequality
held in both cases (15,489 and 15,641 against 16,384), so this was never a context-window
problem.

**The transcripts settle the diagnosis.** The model restates the module header **229 times**
in surface A (34,858 chars) and **161 times** in surface C (32,352 chars), cycling on the
identifier `varrho`, which it mistypes as `vvarrho`, rejects, and restarts over. It is a
repetition loop, not deliberation.

**Decisions made and why.** The survivor rerun was **not launched**. Three reasons: the
allowance saturated at 6,144 and again at exactly 12,288, a factor of two apart; the
restatement count scales with the budget, so 28,672 predicts ~500 restatements and another
`length` finish; and the pathology is one task, not one surface — the other seven surface-A
tasks finished with `stop` and this task completed cleanly in surface B.

The 1 x 32,768 configuration is recorded as the directive requires, with its inequalities
checked, and marked not recommended: it halves concurrency and would run up to ~10 hours to
reproduce the same truncation.

**Tests and verification actually executed.**

| check | result |
|---|---|
| probe A, allowance 12,288 | prompt 2,945, completion **12,288**, `length`, truncated, 620s |
| probe C, allowance 12,288 | prompt 3,097, completion **12,288**, `length`, truncated, 659s |
| budget inequality, both | holds (15,489 / 15,641 <= 16,384) |
| module header restatements | A **229x**, C **161x** |
| survivor rerun launched | **no** |

**Failures and unresolved uncertainty.**

- **No allowance is known to be sufficient**, and the evidence argues none is.
- The three candidate fixes all touch frozen artefacts and none was applied: a decode-side
  repetition penalty or stop sequence (least invasive, changes a sampling option only);
  renaming the identifier (changes the corpus, needs a fresh id and re-admission); or
  extracting the last complete candidate from a truncated transcript (a scorer change, and
  the most dangerous — the transcripts contain correct encodings, so it would convert a null
  measurement into a positive one on a rule invented after seeing the data).
- Surfaces A, B and C remain **unresolved**. Only D is closed, and by upper bound.

**Effect.** A 24-condition rerun that would have reproduced the same defect was not spent,
and the defect is now characterised precisely enough to choose a fix.

**Next intended step.** A decision on which of the three fixes is authorised. Nothing else
proceeds until then.

---

## 2026-08-06 — Pyright configured; a stale re-export closed

**Branch.** `integration/m1.5-paper-derived-closeout` · **Stage.** static-analysis audit,
run alongside a live experiment.

**Objective.** Establish a truthful Pyright baseline and fix high-confidence defects on the
critical path.

**Files and systems changed.** New `pyrightconfig.json`; `src/hamiltonian_lang/
verification/__init__.py`; new `tests/verification/test_package_exports.py`; new
`docs/audits/PYRIGHT_OVERNIGHT_AUDIT.md`. No experiment file touched, no model call made —
the eval001 screen owned Ollama throughout (PID 38523).

**What was completed.** The repository had **no Pyright configuration**, so Pyright could
not see `.venv` and reported 126 missing imports for packages that import fine at runtime
(pytest 99, sympy 7, hypothesis 6, numpy 5, scipy 7, tiktoken 1). That is worse than a code
defect: every file with an unresolved import had its real analysis degraded. Describing the
environment truthfully — without weakening the mode or excluding anything load-bearing —
takes the count from **484 to 374**.

**One confirmed defect fixed.** `hamiltonian_lang.verification` declared
`__all__ = ["obligations"]` and never imported the submodule. Verified at runtime, not just
by the checker: `hasattr(verification, "obligations")` was False, attribute access raised
unless another module had already imported it, and `from ... import *` bound nothing while
appearing to succeed. On the critical path, since the obligations engine is the verifier.
The test added walks every package under `hamiltonian_lang` and asserts each `__all__`
entry exists, closing the class rather than the instance.

**Decisions made and why.** No suppression was added, no type weakened, no mode lowered.
Two diagnostics were dispositioned rather than "fixed": `sympy_bridge.py`'s 21
optional-access reports follow a guarded `except ImportError: sympy = None`, which is an
intentional dynamic boundary — though whether every *use* is guarded was not verified and
is flagged as tomorrow's first check.

**Tests and verification actually executed.**

| command | result |
|---|---|
| `pyright` baseline | 484 errors, 9 warnings, 329 files |
| `pyright` after config | **374 errors, 7 warnings** |
| `ruff check` (changed files) | All checks passed |
| `mypy src` | Success, 84 source files |
| `pytest tests/verification` | 135 passed |

**Failures and unresolved uncertainty.**

- **374 diagnostics remain and are largely untriaged.** Only the missing-import class and
  one `reportUnsupportedDunderAll` were dispositioned.
- `repair/record.py:329-334` is a **likely real** optional-access defect on an
  experiment-record type. It was not fixed: it needs a reference search and a reproducing
  test first, and there was not room to do that safely.
- Sections 2-5 of the directive (interface mapping, ordered-view typing, firewall typing,
  experiment-record invariants, verdict exhaustiveness, H2 typing) were **not executed**.
- Full pytest and conformance were not re-run; the change is a single import covered by the
  targeted suite, but they should run before this is treated as complete.

**Effect.** The static-analysis baseline is now truthful rather than import-blind, and one
real runtime defect on the verifier path is closed.

**Next intended step.** Triage the 29 `reportPossiblyUnboundVariable`; finish
`repair/record.py`; decide whether `equivalence/` is in scope, since it holds 52 of the 58
`src` diagnostics and sits off the critical path.

---

## 2026-08-06 — eval001 headroom screen: saturated, HEADROOM_INSUFFICIENT

**Branch.** `integration/m1.5-paper-derived-closeout` · **Stage.** H2 benchmark headroom.

**Objective.** Determine whether the existing eval001 corpus has the difficulty headroom an
H2 representation comparison needs.

**What was completed.** 95 problems (120 minus 25 exact duplicates, 16 groups sharing prose
and question verbatim with agreeing answers), three seeds each at temperature 0.7 and
max_tokens 2400, plain-English arm only, prompts read from the pre-generated `arms/A/` files
so no prompt builder sat in the loop. A five-problem dry run across five domains preceded it
and was clean.

**Result: the corpus is saturated.** Of 90 tasks with all three seeds complete, **85 are 3/3
correct**; mean accuracy **0.959**; the 1/3-2/3 headroom band holds **3 tasks** against a
required 30. Verdict **HEADROOM_INSUFFICIENT**. The pilot's 93.3% across all seven arms was
not a small-sample artefact — eval001 simply cannot discriminate between representations,
because the model already solves nearly all of it.

**Decisions made and why.** eval001 is retired as an H2 corpus. The purpose-built 24-task v1
benchmark is the H2 corpus instead; its claims were verified rather than assumed (24 tasks,
mean predicted accuracy 0.556 exactly, 24/24 inside the 0.40-0.70 band, contamination clean
against 517 foreign items across 18 corpora, 24/24 with independent key verification, and
its three apparent answer "leaks" cleared as multiple-choice letters that necessarily appear
in their own option lists).

**Tests and verification actually executed.**

| check | result |
|---|---|
| records | 271/285 at commit (14 outstanding; the process was still running) |
| complete tasks | 90/95 |
| transport failures | 0 |
| scoring failures | 0 |
| prompt-hash stability vs manifest | **all records match** |
| model-digest stability | single digest across all records |
| **truncations** | **11** at max_tokens 2400 |
| histogram | 0/3 = 2 · 1/3 = 2 · 2/3 = 1 · 3/3 = 85 |

**Failures and unresolved uncertainty.**

- **The screen was still running at commit time**: 271 of 285 records, 90 of 95 tasks
  complete. The verdict is not in doubt — 85/90 at 3/3 cannot be overturned by five tasks —
  but the figures are interim and `analyse.py` should be re-run for the final ones.
- **11 truncations** at the inherited max_tokens of 2400. On a saturated corpus this does
  not change the verdict, but it would have to be fixed before any corpus is measured for
  real.
- This screen was launched before the 24-task benchmark was located. It answers a question
  about eval001, not about the H2 corpus.

**Effect.** A wrong path is closed for the cost of one unattended overnight GPU run, and the
right corpus is identified and independently verified.

**Next intended step.** Re-run `analyse.py` for the final records, then run Arm E
(structured English plus one unaided self-review) on the 24 frozen tasks — the baseline
headroom calibration, which doubles as the Arm-E data the E-versus-H comparison needs.

---

## 2026-08-06 — H2 headroom screen completed: 285/285, verdict unchanged

**Branch.** `integration/m1.5-paper-derived-closeout` · **Stage.** H2 benchmark headroom.

**Objective.** Close out the eval001 screen with the final records and the integrity audit.
`02fa482` committed it mid-run at 271/285.

**Files and systems changed.** The remaining 12 records and `SCREEN_REPORT.json` under
`evaluation/results/h2_headroom_screen/`. No source change.

**What was completed.** The run finished all 285 conditions and `analyse.py` produced the
audit. **The interim verdict holds on the complete data.**

**Tests and verification actually executed.**

| check | result |
|---|---|
| matrix complete | **True**, 285/285, 0 duplicates, 0 missing |
| transport / scoring failures | 0 / 0 |
| prompt hash vs manifest | **all 285 match** |
| model digest | single digest throughout |
| truncations | 11 (inherited `max_tokens` 2400) |
| mean plain-English accuracy | **0.961** |
| histogram | 0/3 = 2 · 1/3 = 2 · 2/3 = 1 · **3/3 = 90** |
| headroom band | **3** against a required 30 -> `HEADROOM_INSUFFICIENT` |
| unanimous across seeds | **92/95** |
| cost | 285 calls, 224,029 completion tokens, median 34.3s, 4.13h |

**The domain breakdown is the sharpest part of the result.** Algebraic (17), binding (22)
and quantifier (17) are at 3/3 on **every** task — three of five domains carry no signal
whatever. Dimensional contributes two headroom tasks and probability one; probability also
holds both 0/3 floor tasks. A representation comparison on this corpus would be measuring
noise on 56 of 95 items and nothing at all on the rest.

**Failures and unresolved uncertainty.**

- 11 truncations at `max_tokens` 2400. Immaterial on a saturated corpus, but the cap must be
  raised before any corpus is measured for real.
- This screen answers a question about eval001, not about the 24-task H2 corpus.
- 92/95 unanimity means the three-seed design bought little here; on a corpus with real
  headroom it would buy more.

**Effect.** eval001 is definitively retired as an H2 corpus, on complete data rather than a
partial read.

**Next intended step.** Arm E (structured English plus one unaided self-review) on the 24
frozen tasks — the baseline headroom calibration, which doubles as the Arm-E half of the
E-versus-H comparison.

---

## 2026-08-07 — Developmental protocol v1.2 committed; two pre-run defects fixed; the decisive run is armed

**Branch.** `integration/m1.5-paper-derived-closeout` · **Stage.** V1 benchmark, pre-run.

**Objective.** Make the SE-versus-HML-V1 measurement runnable autonomously and honestly,
and commit every protocol change **before** any scientific call, so that no budget decision
can be taken after seeing a result.

**Files and systems changed.**

- new `docs/evaluation/V1_PROTOCOL_AMENDMENT_v1_2.md` — the amendment, in prose
- new `evaluation/v1_benchmark/protocol_v1_2.py` — the amendment, machine-readable
- new `evaluation/v1_benchmark/driver.py` — the crash-safe driver
- new `evaluation/v1_benchmark/envelope.py` — offline envelope rendering
- new `evaluation/v1_benchmark/calibrate_envelope.py` — measured envelope calibration
- new `evaluation/v1_benchmark/diagnostics_budget.py` — the diagnostics cap
- new `tests/evaluation/test_diagnostics_budget.py`, `tests/evaluation/test_v1_driver.py`
- new `evaluation/results/v1_benchmark/ENVELOPE_CALIBRATION.json`
- no change to `arms.py`, `tasks.py`, `scoring.py` — the frozen scientific inputs

**What was completed.**

The budget amendment: per-call completion allowance **1024 → 4096**, total per arm
**2048 → 8192**, applied identically to both arms, with temperature, model digest, call
count, task set, task order, scorer, matched information and matched revision opportunity
all held exactly as frozen. This is **developmental protocol v1.2** and is never to be
described as the untouched original configuration.

**Two defects were found and fixed before any scientific call.**

1. **Unbounded compiler diagnostics.** `classify_diagnostics()` renders the whole bag with
   no ceiling. Measured: 200 unresolved names → 6.3×, 200 parse errors → 23.0×, **200 lines
   of garbage → 389,426 characters, 121.7×**. That is ~130,000 tokens; it overflows a 16,384
   slot eightfold and a 32,768 slot fourfold, so **no context size solves it**. An over-long
   prompt truncates rather than raising, so the repair call would have been made against a
   mutilated prompt — and worst **exactly where the model wrote the worst HML**, making the
   artefact anti-correlated with the treatment. Capped at 6,000 chars / 40 diagnostics on
   whole-line boundaries with an explicit omission notice. The cap can only *remove*
   information from the treatment arm, so a positive HML result under it is a lower bound.
2. **No crash safety, and arms interleaved.** `pipeline.run_benchmark` accumulated results in
   memory and returned them at the end — the previous session died in exactly that window —
   and `run_task` ran SE and HML per task, which makes an SE-first headroom gate impossible.
   Replaced by `driver.py`.

**A third finding was recorded rather than fixed:** neither arm re-supplies its format spec
on the second call (`se_review_prompt` omits `SCHEMA_A_PRIME`, `hml_repair_prompt` accepts a
`surface_spec` it never uses). Since calls carry no history, both arms repair without their
specification in context. This is **matched**, so it is left exactly as frozen and noted as
a handicap on the treatment arm.

**A correction to my own tooling.** The first calibration attempt sized synthetic carried
bodies in *characters* at an assumed 5.0 chars/token. HML-like source measures ~2.1–3.0, so
a filler meant to represent 4,096 tokens measured ~6,800 — a bound that was not conservative
but **incoherent**, modelling a completion the allowance forbids. It produced a false
`EXCEEDS` verdict against the 16,384 slot. Fillers are now sized in tokens.

**Tests and verification actually executed.**

| check | command | result |
|---|---|---|
| diagnostics cap | `pytest tests/evaluation/test_diagnostics_budget.py -q` | **9 passed** |
| driver guarantees | `pytest tests/evaluation/test_v1_driver.py -q` | **15 passed** |
| existing v1 suite | `pytest -k "v1_benchmark or arms or scoring" -q` | **161 passed** |
| envelope fit | `python -m evaluation.v1_benchmark.calibrate_envelope` | **all_fit=True** |
| live model digest | `/api/tags` vs `MODEL_DIGEST` | **match** (`6316f0629137…`) |
| lint (new modules) | `ruff check evaluation/v1_benchmark/ tests/evaluation/` | **clean** |

Measured envelopes against the live tokeniser (`max_tokens=1` calls, which occupy different
cache keys from run calls and cannot be replayed as scientific data):

| arm | stage | prompt tokens | required | headroom vs 16,384 |
|---|---|---:|---:|---:|
| SE | initial | 405 | 4,757 | 11,627 |
| SE | review | 3,323 | 7,675 | 8,709 |
| HML-V1 | initial | 1,199 | 5,551 | 10,833 |
| HML-V1 | repair | 6,505 | 10,857 | **5,527** |

**Decisions made and why.**

- **Runtime `2 x 16384`, not `4 x 8192`.** `arms.RUNTIME` is stale; the live server is
  `OLLAMA_NUM_PARALLEL=2 OLLAMA_CONTEXT_LENGTH=16384`. Recorded as measured, and the driver
  refuses to start on disagreement.
- **No 32,768 single slot.** The mission permits escalating when the two-slot arrangement
  cannot fit the largest matched envelope. It fits, with 5,527 tokens spare, so the server
  is left alone — no restart, no 19 GB model reload, and the measured 1.54× throughput of
  two slots is retained.
- **Truncation halts the run** rather than being recorded. Under v1.2 a truncated completion
  is a measurement defect, not a datum.

**Failures and unresolved uncertainty.**

- **No scientific call has been made.** Nothing here is evidence about HML.
- The pre-run task audit (24 keys re-derived independently) was still running at commit time;
  its findings may yet exclude tasks. The run requires ≥ 20 valid paired tasks.
- 4 pre-existing `ruff` errors remain in `evaluation/h2_screen/` from the previous session.
  Untouched — out of scope for this commit.

**Independent key verification (pre-run, read-only).** All 24 answer keys were re-derived
from the prose alone by an independent reviewer: **24/24 AGREE, zero disagreements, zero
materially ambiguous**. All seven convention-traps (06 Simpson sign, 07 total variance,
13 SI permittivity, 18 Frullani sign, 20 series order, 21 conditional independence,
22 testimony double-counting) are on the correct side of their trap.

**A scoring hazard found and deliberately NOT fixed.** The numeric extractor matches
`-?\d+(\.\d+)?`, so an answer of `2/3` does not merely fail — it **silently extracts as
`2.0`**, which is indistinguishable in the record from a model that genuinely answered 2.
Seven of 24 tasks have fractional true values. Verified directly:
`score_answer(v1b_03, "<ANSWER>2/3</ANSWER>") -> (False, '2.0')`.

It is left exactly as frozen, for three reasons: the answer instruction explicitly demands
"a single number ... e.g. 3.25", so a fraction disobeys a stated contract; the scorer is a
**frozen scientific input** and changing it after the corpus is known is precisely the
post-hoc adjustment this protocol forbids; and it applies to **both arms identically**, so
it cannot bias the SE-versus-HML contrast. It can depress both arms together and so bears on
the headroom gate reading. A per-arm count of fraction-formatted final answers is therefore
computed post-hoc as a confound check, and is handed to the falsification reviewers.

**Also preserved in this commit:** the 285 untracked `evaluation/results/generation_cache/`
entries from the previous session's eval001 screen. The adapter's contract is that raw
generations are written once and never overwritten, and 51 such entries were already
tracked; leaving 285 untracked would have made the cache silently machine-local.

**Effect.** The decisive measurement can now run unattended and crash-safe, and every
protocol choice it depends on is committed and dated ahead of the first result.

**Next intended step.** The 8-call operational probe, then the SE headroom gate.

---

## 2026-08-07 — v1.2 falsified by its own probe; protocol v1.3, four harness defects fixed, one task excluded

**Branch.** `integration/m1.5-paper-derived-closeout` · **Stage.** V1 benchmark, still pre-run.

**Objective.** Act on what the operational probe and the read-only task audit found, before
any scientific call is made.

**Files and systems changed.**

- new `evaluation/v1_benchmark/answer_extraction.py` — the v1.3 scorer (D1, D2, D3)
- new `evaluation/v1_benchmark/arms_v1_3.py` — the matched repair prompt (D4)
- new `evaluation/v1_benchmark/run_experiment.py` — the single autonomous command + gate
- `evaluation/v1_benchmark/protocol_v1_2.py` — v1.3 constants, `EXCLUDED_TASKS`, probe finding
- `evaluation/v1_benchmark/driver.py` — wired to the v1.3 scorer and repair prompt; exclusion
- `evaluation/v1_benchmark/analyse.py` — scoring-failure and revised-answer diagnostics
- new `tests/evaluation/test_answer_extraction_v13.py` (32 tests)
- `docs/evaluation/V1_PROTOCOL_AMENDMENT_v1_2.md` — the v1.3 section
- **no change** to `tasks.py`, `arms.py`, `scoring.py` or `evaluation/corpus/cso.py`

**What was completed.**

**The probe falsified v1.2's central number.** Run on the two pre-declared tasks — `v1b_23`
(largest measured envelope) and `v1b_06` (tied-hardest, tie broken by frozen order) — at the
4096-token allowance, **both calls truncated and the run halted**:

| task | completion tokens | reasoning chars | content chars |
|---|---:|---:|---:|
| `v1b_06_simpson_reversal` | 4096 (capped) | 10,617 | **0** |
| `v1b_23_knowledge_closure_choice` | 4096 (capped) | 12,070 | 2,457 (cut off) |

The cause is a model property v1.2 did not account for: **`gemma4:31b` is a reasoning
model.** Its thinking trace is billed to `completion_tokens` but returned in a separate
field — documented at module level in `evaluation/model_adapters/ollama.py`, and not
connected to the budget decision when v1.2 was written. The trace alone costs ~3,000–4,000
tokens, so at 4096 the answer field is empty or truncated. An empty `content` is an
**absent answer** the scorer records as a failure of the representation: the exact artefact
v1.2 existed to remove, reproduced one rung lower.

**v1.3: allowance 4096 → 8192 per call, 8192 → 16384 per arm, identical in both arms.**
Runtime reconfigured to `1 x 32768` (the mission's stated contingency). Total KV context is
unchanged — `16384 x 2` became `32768 x 1` — so this costs no memory and trades parallelism
for slot size. Model digest re-verified after the restart: unchanged.

**Four harness defects, each demonstrated on the real scorer and independently reproduced
before any code was changed.**

| # | defect | evidence | direction of harm |
|---|---|---|---|
| D1 | the **first** `<ANSWER>` span was scored | `"…<ANSWER>2.5</ANSWER> wait, wrong. Final: <ANSWER>2.2857</ANSWER>"` → `2.5`, incorrect | penalises the second call **exactly when it works**, in both arms |
| D2 | the first number-like substring was mined out | `16/7 → 16.0`, `sqrt(76) → 76.0`, `ln(5/2) → 5.0` | **differential** — a formal arm is likelier to write exact forms, so it falls on the **treatment** |
| D3 | no marker → the whole reply was searched | `"flipped 10 times … Var(H) = 2.5."` scored **correct** against key 10 | a formatting failure scored as reasoning success; inflates **both** arms |
| D4 | SE carried its whole first reply; HML carried only the fence | `hml_repair_prompt` never receives `r1.content` | handicaps the **treatment** |

D2 touches 9 of 24 tasks. D4 contradicts the frozen design's own claim that the arms
*"differ in exactly one respect"* — they differed in two.

Fixed in a **v1.3 layer, not in `cso.py`**, which scored eval001 and ACQ0 and whose numbers
must stay reproducible.

**A bug in my own fix, caught by its test.** The closed-form parser rewrote `ln → math.log`
and then `log → math.log` in successive passes, so `ln(5/2)` became `math.math.log(5/2)` and
failed — silently reintroducing D2 for every logarithm. Now a single pass over an
alternation, which cannot re-enter its own output.

**A second bug caught pre-data, in the decision rules.** Continuation condition 3 read
`hml_repaired >= 1.5 * se_repaired`, which is **true when both are zero** — "HML corrects 50%
more" was satisfiable by nothing happening at all. A strict `>` was added.

**`v1b_11_negation_scope_choice` excluded** for a pre-run defect on two independent counts:
its options are not mutually exclusive (B is a correct formalisation on its own; D asserts B
and C both are, and is not itself a formalisation), and the choice scorer requires exactly
one option letter, so `<ANSWER>D (both B and C are correct)</ANSWER>` scores **False** while
a bare `<ANSWER>D</ANSWER>` scores True — the task penalises a model for explaining a
correct choice. The corpus file is not edited; the exclusion lives in
`protocol_v1_2.EXCLUDED_TASKS` and appears in every manifest. **23 valid paired tasks
remain, against a required 20.**

**Tests and verification actually executed.**

| check | command | result |
|---|---|---|
| v1.3 scorer + matched carry | `pytest tests/evaluation/test_answer_extraction_v13.py -q` | **32 passed** |
| decision rules + statistics | `pytest tests/evaluation/test_v1_analyse.py -q` | **27 passed** |
| driver guarantees | `pytest tests/evaluation/test_v1_driver.py -q` | **15 passed** |
| whole evaluation suite | `pytest tests/evaluation/ -q` | **all passed** |
| envelope fit at 8192 / 32768 | `python -m evaluation.v1_benchmark.calibrate_envelope` | **all_fit=True**, worst HML repair 27,120 / 32,768 |
| all 24 gold keys under v1.3 | direct check | **24/24 correct** |
| headroom bands at N=23 | direct check | ideal 8–15, usable 6–17 |
| digest after server restart | `/api/tags` | **unchanged** |

**Independent audits (read-only, pre-run).** Two reviewers. Key verification: **24/24 keys
re-derived and confirmed**, including all seven convention-traps. Task audit: raised the
four defects above, all of which I reproduced myself before acting; it also certified no
duplicates (max prose Jaccard 0.244), zero worked demonstrations, and byte-identical problem
text across arms.

**Failures and unresolved uncertainty.**

- **Still no scientific call.** Nothing here is evidence about HML.
- The allowance has now been raised **twice**, the second time in response to a measurement.
  Both changes are dated before any scientific result. Neither was made with an outcome in
  view, and both are recorded rather than folded into a claim of the original configuration.
- Serial execution at `1 x 32768` is materially slower than the previous two-slot
  arrangement. The run is crash-safe and resumable, so the cost is wall time, not risk.
- 4 pre-existing `ruff` errors remain in `evaluation/h2_screen/`. Untouched.

**Effect.** The measurement now scores what the model actually answered, gives both arms the
same prior working, cannot silently truncate, and runs to a verdict from one command.

**Next intended step.** Complete the 8-call probe at v1.3, then the SE headroom gate.

---

## 2026-08-07 — Decisive run: SE headroom gate INSUFFICIENT at 23/23; HML_BENCHMARK_FAILED_NO_SIGNAL

**Branch.** `integration/m1.5-paper-derived-closeout` · **Stage.** V1 benchmark, closed.

**Objective.** Obtain the highest-integrity developmental signal available from the frozen
24-task benchmark, SE versus HML-V1, and return one project decision.

**Files and systems changed.** New `docs/evaluation/V1_HEADROOM_GATE_REPORT.md` and the run
artefacts under `evaluation/results/v1_benchmark/decisive_01/`. No source change.

**What was completed.** The complete SE arm on 23 valid paired tasks under developmental
protocol v1.3. The headroom gate was evaluated on the complete SE matrix **before any
treatment call**, returned INSUFFICIENT, and the driver stopped without making a single
HML-V1 call.

**Tests and verification actually executed.**

| check | result |
|---|---|
| records complete | **23/23**, all arm SE, 0 HML records |
| truncations / transport errors | **0 / 0** |
| scoring outcomes | **46/46 calls `ok`** |
| answer markers | exactly one per reply, 0 anomalies |
| scientific-input drift across the run | **NONE** |
| result reconstruction by re-scoring raw content | **23/23, exact match to stored values** |
| SE final correct | **23/23 (100%)** |
| SE first-call correct | **23/23** |
| second call changed the answer | 2 (final still 23/23) |
| cost | 46 calls, 132,571 completion tokens, 2.27 h wall |

**Decisions made and why.**

- **No HML arm.** Mission section 7 requires it and the design enforces it: a corpus the
  control saturates cannot discriminate between representations, so spending treatment
  compute would buy nothing and would let the gate be argued with after the fact.
- **The verdict is about the corpus.** No HML scientific call exists, so nothing here is
  evidence for or against HML.

**Failures and unresolved uncertainty.**

- **Two purpose-built corpora lost to saturation in a row.** eval001 at 0.961; this at 1.000
  against a predicted 0.556. Every difficulty figure was `PREDICTED_NOT_MEASURED` and none
  carried signal: all three tied-hardest tasks and every convention trap were answered
  correctly.
- **Headroom is a function of the completion budget.** At 4096 the probe truncated and
  `v1b_06` returned zero characters of content; at 8192 the model scored 23/23. This corpus
  has no usable headroom at any allowance yet identified.
- **The budget raise and the saturation are causally linked.** The v1.2 -> v1.3 raise was
  necessary and was committed before any scientific call, but it is what moved the corpus
  from floor to ceiling. Recorded so a reader can weigh it.
- It is not established that a corpus this model cannot saturate exists within the
  mathematics this benchmark targets.

**Effect.** The 24-task benchmark is retired for H2. H2 remains untested: there is still no
valid measurement of whether HML changes an answer, and — per the parallel language audit —
still no valid measurement of whether a model can write HML at all.

**Next intended step.** Build an H2 corpus by measuring first: calibrate SE accuracy at the
run budget, admit only tasks the control gets wrong at that allowance, and select until the
control lands inside the 8-15 band. Two corpora designed from intuitions about difficulty
have now failed; difficulty must be measured before a task is admitted.

---

## 2026-08-07 — V2 reasoning spine: derivations, obligations, assumption discharge

**Branch:** `feature/hml-reasoning-kernel-v2` (worktree `/Users/moheet/hml_v2_worktree`)
**Base:** `3dd4216` · **Stage:** HML V2 reasoning kernel, phase I / I-B / I-C

**Objective.** Close the language audit's central finding — that HML can represent
mathematical state but not reasoning transitions (0/19 transformation forms representable
in `.hml` source) — by adding the smallest surface form for an inference, together with
the machinery that makes it enforceable rather than decorative.

**Protection of the active experiment.** Inspected first: three worktrees, no running
Python/Ollama evaluation process, audit worktree untouched for 3+ hours. All work done in
a separate worktree on a separate branch. `/Users/moheet/hml_audit_worktree` was read
only and not modified. No model was called.

**Files and systems changed.**
- new `src/hamiltonian_lang/reasoning/` — `kernel.py` (16 trusted rules), `refinement.py`
  (the environment Γ), `check.py` (claim resolution, rule checking, adjudication)
- `ast/nodes.py` — `GoalStmt`, `DeriveStmt`, `ProvedStmt`, `ClaimId`, `RuleArg`,
  `DerivationStatus`, `GoalStatus`, `uses_v2()`; `claim_id`/`label` on the three
  labellable v1 forms
- `lexer/__init__.py` — 5 keywords; `parser/__init__.py` — 3 productions + optional labels
- `backends/canonical.py` — V2 serializers, `expr_identity()`, version-aware schema tag
- `backends/hml.py`, `backends/english.py` — V2 rendering; `backends/base.py` —
  `report_reasoning_loss()`
- `type_system/__init__.py`, `semantics/__init__.py` — V2 statements type-checked and resolved
- `tests/freeze/frozen_subset.py`, `tests/freeze/test_quarantine.py`,
  `tests/syntax_acquisition/test_candidate_surfaces.py` — freeze updated deliberately
- new `tests/reasoning/` — 44 tests
- `DECISIONS.md` — D-025

**What was completed.** A derivation now has stable identity, explicit premises, explicit
rule identity, explicit output, role-labelled parameters, generated obligations,
provenance and a computed verification status. `assume x != 0` discharges the
`divide_both_sides` obligation; `assume x >= 0` does not. `proved g by d` is adjudicated
against the checker's verdict rather than accepted.

**Decisions and why.** Recorded in full as D-025. The load-bearing one: the trusted
kernel builds the conclusion a rule licenses *without seeing the author's claim*, and the
two are compared under canonical identity. Rejected reusing `v1/transformation.py` as the
kernel on evidence — its obligations are format strings, not `Expr`, so every obligation
would be UNKNOWN by construction.

**Tests and verification actually executed.**
- `.venv/bin/python -m pytest` → **5787 passed, 5 skipped, 7 xfailed, 7 xpassed, 0 failed**
  (baseline at `3dd4216`, same command: 5743 passed, 4 skipped, 0 failed)
- `.venv/bin/ruff check src tests` → **All checks passed**
- `.venv/bin/mypy src/hamiltonian_lang/reasoning src/hamiltonian_lang/ast` → **clean, 6 files**
- v1 canonical-hash stability: all 43 `examples/**/*.hml` hashed under the v1 compiler
  (main worktree) and the V2 compiler; `diff` → **43/43 byte-identical**
- all 18 quarantined V1_KERNEL surface forms → still **REJECTED**
- V2 round-trip `hml` backend → reparses, **content hash matches**

**Failures and unresolved uncertainty.**
- Two silent-loss defects were **introduced by this change and found by inspection, not by
  the suite**: `hml` reported `faithful=True` while emitting `# <unrenderable DeriveStmt>`,
  and four lowering backends dropped all three V2 nodes silently. Both are fixed and
  regression-tested, but the suite did not catch them — the gap was that no test asserted
  loss reporting for a *new* construct. `tests/reasoning/test_backend_loss.py` now does.
- A scripted edit orphaned five statement branches in the type checker (`ObjectiveStmt`,
  `SolveStmt`, `InferStmt`, `CheckStmt`, `ConceptDecl` stopped being type-checked). Caught
  by 33 failing tests and fixed. Recorded because the near-miss was real: a hand edit into
  a 1700-line function is not safe to script.
- Substitution does not descend into quantifier bodies; such steps are REJECTED, not
  performed. Conservative but incomplete.
- The refinement environment decides only syntactic facts about a symbol against a literal
  bound. It cannot chain, do arithmetic, or case-split. Everything it cannot establish
  stays OPEN.
- **Scope delivered is phase I/I-B/I-C only.** The directive's phases II–IV (probability
  algebra, sets, analysis operators, causal relations, compositional-closure work,
  extension/module mechanism, synthetic generator, audit rerun) are **not** in this commit.

**Effect on the overall project.** The audit's finding 1 ("there are zero transformation
forms in the surface language") no longer holds, and finding 2 is half closed: `assume` is
now load-bearing, while `prove` retains its v1 meaning by design. The maturity-ladder
criteria 3.4 and 3.5 — obligations generated from operations, and transformations that
check their own preservation — have implementations for the first time. No claim is made
here about the ladder placement; that requires the audit rerun, which has not been done.

**Next intended step.** Phase II — close the 11 critical coverage zeros (expectation as an
expression, conditional/joint probability, independence, set membership and comprehension,
limit/derivative/integral/continuity, causal vs associational relations), then rerun the
486-atom capability audit unchanged and report before/after.

---

## 2026-08-07 (later) — V2 expression coverage, and the red-team fixes to the spine

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `7a98427`
**Stage:** HML V2 phase II (coverage) + adversarial closure of phase I

**Objective.** Close the eleven critical coverage zeros the language audit measured, and
fix the eight findings adversarial review returned against the reasoning spine.

**Files and systems changed.**
- `ast/nodes.py` — 11 expression node kinds (D-026); `types.py` — `EventType`,
  `Product[T1,T2]`; `lexer`, `parser`, `type_system`, `semantics`, `graph`, backends
- `reasoning/check.py` — the established/unestablished premise split and obligation
  propagation (D-027)
- `backends/__init__.py` — `graph`/`triples` reasoning-loss reporting
- `backends/canonical.py` — numeric normalisation inside `expr_identity` only
- `cli/__init__.py` — reasoning verdicts in `hml check`, rule obligations in
  `hml obligations`
- `spec/ir.schema.json` — the V2 statement kinds (a D-025 omission) plus 11 expression kinds
- new `tests/reasoning/test_circularity.py`, `tests/adversarial/test_v2_expression_rejections.py`
- `DECISIONS.md` — D-026, D-027, and a correction to D-025

**What was completed.** All 11 critical atoms are representable and enforced: LIMIT,
CONTINUITY, DERIVATIVE, INTEGRAL_DEFINITE, EXPECTATION, JOINT, CONDITIONAL_PROBABILITY,
INDEPENDENCE, SET_MEMBERSHIP, SET_COMPREHENSION, CORRELATION_VS_CAUSATION. Four are
shipped as examples. The reasoning spine's critical circularity defect is closed.

**Decisions and why.** D-026 and D-027 in full. The two that matter most:
- `expectation` kept as a keyword and *given an expression production*, rather than
  deleted as the audit suggested — deletion would have broken `infer expectation x`.
- Premises must be ESTABLISHED. `goal`/`require`/`prove` state things to be shown and are
  no longer admissible as premises; obligations propagate along derivation chains.

**Tests and verification actually executed.**
- `.venv/bin/python -m pytest` → **6226 passed, 5 skipped, 7 xfailed, 7 xpassed, 0 failed**
  (was 5787 after the spine commit; 5743 at base `3dd4216`)
- `.venv/bin/ruff check src tests` → **All checks passed**
- hash stability, cross-worktree: **0 pre-existing hashes changed**, 4 added for the new
  example files. `tests/golden/hashes.json` gained 4 rows and changed none.
- the original circularity exploit now emits `HML-R712`; the goal is not PROVED
- semantic barriers re-verified independently by the lead: `RandomVariable[Real]` into a
  `Real` declaration → HML-T402; into a definition body → HML-T403; `Distribution` as a
  value → HML-T402; dimension mismatch → HML-D502

**Failures and unresolved uncertainty.**
- **The critical defect in the phase-I spine was found by adversarial review, not by the
  suite.** `goal g1 : 1.0 = 2.0` could prove itself; the module compiled with zero
  diagnostics and reported `g1` PROVED. So did two silent-loss defects before it. The
  suite tests what the authors thought of; this is the second consecutive change where
  that was the binding limitation.
- A D-025 claim was overstated — "43/43 byte-identical content hashes" — when 28 of the
  43 are candidate-syntax files that do not compile. 15 produce real hashes, all
  unchanged. Corrected in place in D-025 with the correction noted.
- SymPy has `Integral`/`Derivative`/`Limit` and the backend **drops** them rather than
  emitting: the bound variable needs a `Symbol` carrying the binder's refinement, and
  that backend declares symbols only from declarations. Two sibling binders spelled alike
  would silently share one symbol, and a wrong assumption propagates through CAS
  simplification with no error. Loss is declared, not silent.
- `PValue` vs `PosteriorProbability` remains conflatable in comparison position — D-022
  holds in 5 of 12 expression positions. Pre-existing, unchanged by this work, recorded in
  `docs/hml_v2/RED_TEAM_BASELINE.md`.
- HML still cannot distinguish *sure* from *almost-sure* convergence (audit C-7).
- **Still not done:** compositional-closure measurement, the extension/module mechanism,
  the synthetic trajectory generator, the 100+ specimen regression suite, and the
  486-atom capability-audit rerun. No maturity-ladder claim is made.

**Effect on the overall project.** The audit's three deciding findings are now addressed
in the surface language: transformation forms exist, `assume` is load-bearing, and the 11
critical zeros are closed. Whether that moves the ladder placement is **unmeasured** — the
audit rerun is the next step and has not been run.

**Next intended step.** Rerun the 486-atom capability audit unchanged (do not edit the
ontology) and report BEFORE/AFTER for critical coverage, critical zeros, compositional
closure, transformation representability and backend silent loss.

---

## 2026-08-07 (third entry) — capability-audit rerun, and the `assume` half-fix corrected

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `f0e3340`
**Stage:** HML V2 measurement + D-028

**Objective.** Rerun the 486-atom capability audit unchanged and report BEFORE/AFTER;
fix what the measurement exposed.

**What was completed.** The audit was rerun against both the v1 baseline and the V2
compiler with the ontology verified byte-identical by sha256. `docs/hml_v2/AUDIT_RERUN.md`
records the result. D-028 wired the refinement environment into the type checker.

**Results, as measured — targets hit and missed.**

| metric | published | reproduced | AFTER | target | verdict |
|---|---:|---:|---:|---:|---|
| critical faithful | 79.7% | 79.7% | 96.9% (corrected probes) / 82.8% (unmodified) | ≥95% | HIT / MISS |
| critical zeros | 11 | 11 | 0 (corrected) / 8 (unmodified) | 0 | HIT / MISS |
| compositional closure | 0.615 | **0.692** | 0.692 | ≥0.85 | **MISSED** |
| transformations representable | 0/19 | 0/19 | **7/19** | ≥15/19 | **MISSED** |
| transformations verifiable | 0/19 | 0/19 | **7/19** | nonzero | HIT |
| epistemic expressible | 8/13 | 8/13 | 8/13 | — | no change |
| epistemic enforced | 5/13 | **4/13** | 5/13 | — | +1 |
| definedness consistency | — | — | 0/19 changed | — | no change |
| extensibility | — | — | 0/9 changed | — | no change, as predicted |
| backend silent loss | 0/54 | 0/54 | 0/54 and 0/45 on V2 constructs | 0 | HELD |
| inference rules soundness-checked | — | 0/16 | **16/16** | — | new |

**Decisions and why.** D-028 in full.

**Tests and verification actually executed.**
- `.venv/bin/python -m pytest` → **6240 passed, 0 failed** (6226 before)
- hash stability after D-028: **0 changed, 0 added** — invisible to modules with no assumption
- the directive §7 example now compiles; ten refusal cases pinned

**Failures and unresolved uncertainty — read this section, not the table.**
- **Two published audit figures did not reproduce.** Compositional closure is **0.692**,
  not the published 0.615, in the audit's own committed artefact at `b1ac7bf`; epistemic
  enforcement reproduced at 4/13, not 5/13. Recorded as discrepancies, not corrected.
- **Seventeen probes were changed** to match V2 idiom. The control run applied the same
  seventeen to v1 and v1 gained **nothing** (79.7% → 79.7%, 11 zeros → 11 zeros; overall
  faithful *fell* because the corrected probes are harder). Two changes are aggressive
  (they alter declared types); a reader rejecting those gets **93.8% / 2 zeros**, short of
  the 95% target. Both readings are published.
- **D-025 and the `7a98427` commit message claimed `assume` was load-bearing against the
  type checker. That was false when written** — Γ was consumed only by the reasoning
  checker. Corrected by D-028; the false claim is recorded in D-028 rather than edited out.
- **Three regressions**, all from the deliberate `Event`/`Proposition` barrier:
  `PROB.RANDOM_VARIABLE`, `COMP.MATRIX_VALUED_RV`, `RT.STOCHASTIC_PROCESS`. Defensible
  semantics, measured cost, published.
- **`prove` still proves nothing**, and `GRAMMAR_CONTRACT.md` §1 says it should become a
  goal with `ASSERTED_UNCHECKED`. It does not; it remains a `ProveStmt` with no status
  field. Contract-vs-implementation divergence, recorded.
- **408 of 486 atoms remain unprobed**; two whole domains have zero probes. The
  semantic-density benchmark has still never run. V2 model writability is unmeasured.
- **Maturity: still LEVEL 1 — DOMAIN DSL.** Level 2 is not reached, so Level 3 cannot be.

**Effect on the overall project.** Criterion **3.5 — transformations that check their own
preservation, which the ladder names as *the* distinguishing Level 3 capability — moved
FAIL → PASS.** 16/16 rules accept a correct step and reject one differing only in its
stated conclusion. That is real and it is the thesis of the V2 directive. It is also not
enough for a level change: compositionality (0.692 < 0.70), unassessed coverage, absent
scoped assumptions, absent partiality obligations and absent approximation all still block.

**Next intended step.** Compositional closure is the first failure in ladder order and the
cheapest remaining level gate: 0.692 against a 0.70 Level 2 threshold. Then a coherent
partiality policy (criterion 3.4), which the directive's §8 specifies and which is not
built. Do not run any HML-vs-English model experiment until V2 is frozen.

---

## 2026-08-07 (fourth entry) — architectural freeze (programme step 1)

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `0715bfc` · **Stage:** step 1 of 16

**Objective.** Freeze six architectural decisions as binding contracts so that steps 2-9
are implementation rather than redesign.

**Files and systems changed.** New `docs/hml_v2/ARCHITECTURE_FREEZE.md` and
`tests/reasoning/test_architecture_freeze.py`; `DECISIONS.md` gains D-034…D-039.

**What was completed.** Evidence semantics, Γ/scope, definedness, approximation, verifier
certificates and extension trust are frozen, each with its rejected alternatives and the
reason each is wrong *for HML specifically* rather than wrong in general. Twelve pinning
tests lock the decisions that already hold.

**Decisions made and why.** D-034…D-039. The two with the most downstream force:
definedness becomes precondition contracts with a classification registry whose
completeness is a **build error** rather than a review item (D-036 D4); and a claim's
effective trust is the **minimum over its dependency closure** (D-039 X2), which is what
makes the trust lattice do work instead of decorate.

**Tests and verification actually executed.**
- `.venv/bin/python -m pytest tests/reasoning/test_architecture_freeze.py -q` → **12 passed**
- measured before writing D-031: `1.0/0.0`, `tan(x)` and `x^-1` all compile with **zero**
  relevant obligations while `log`/`sqrt` are type-guarded — two policies, no principle

**Failures and unresolved uncertainty.**
- **The freeze is a contract, not an implementation.** Scoped Γ, precondition contracts,
  approximation and certificates are all still absent from the compiler. Only the
  already-true decisions are mechanically enforced; the rest are prose until their step
  lands. Deliberately no xfail guards — they look like enforcement without being it.
- The AST fork (generic Apply/Bind/Attribute core vs bespoke nodes) is **not** decided
  here. Every frozen decision is written to hold under either answer; that claim is
  untested until the compositionality study closes the fork.
- `prove` still diverges from `GRAMMAR_CONTRACT.md` §1. Deferred to step 6, not resolved.
- The commit protocol hook blocked this commit twice: once because the worktree/hook
  interaction evaluates the primary directory, and once because an earlier ledger append
  was inside a blocked compound command and so never ran. Recorded because the second was
  a real omission on my part, not a tooling artefact.

**Effect on the overall project.** Steps 2-9 have a specification. Measured maturity is
unchanged: still LEVEL 1, closure still 0.692.

**Next intended step.** Step 2 (harden the global reasoning graph) and step 4 (partiality
contracts) in parallel; step 3 (scoped Γ) after step 4 to avoid colliding in the type
checker. Step 5's fork verdict is pending.

---

## 2026-08-07 (fifth entry) — research-integration decision record

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `34079d0`
**Stage:** gate before the architectural-completion work

**Objective.** Classify every enumerated research recommendation against measured
repository state before writing any code.

**Files and systems changed.** New `docs/hml_v2/RESEARCH_INTEGRATION_DECISIONS.md`.

**What was completed.** Fourteen recommendations classified with repository evidence:
2 ALREADY/PARTIALLY implemented, 6 ACCEPT, 4 ACCEPT_WITH_MODIFICATION, 2 DEFER, 0 REJECT.

**Decisions made and why.** The two that most change the plan:
- **Generic Apply/Bind core is DEFERRED, not accepted.** Adopting it on the reports'
  say-so before failure attribution is the exact failure mode the directive names first.
- **"Fewer than 10 rules" is rejected as a target.** Rule count is a vanity metric; the
  quantity to minimise is TCB size at fixed trusted semantic power.

**Tests and verification actually executed.**
- `.venv/bin/python -m pytest` → **6252 passed, 0 failed** (directive said 6240 — stale)
- `git rev-parse HEAD` → **34079d0** (directive said 0715bfc — stale by one commit)
- ontology: **486 atoms, 64 critical** — confirmed
- extensibility: **0 of 6** probed forms accepted (`import`, user type, user relation,
  user distribution, `fn … -> T`, `signature`) — confirms extensibility is absent
- CHECKED-as-premise measured: a step resting on a CHECKED premise inherits its open
  obligation and stays CHECKED — the directive's provisional-use rule already holds
- `grep -rn "def .*cycle" src/hamiltonian_lang/reasoning/` → **no match**: acyclicity rests
  entirely on the textual-order rule, which is the §3 E9 gap

**Failures and unresolved uncertainty.**
- **I do not have the text of either research report** — only the enumerated
  recommendations. The classification cannot speak to reasoning or caveats that did not
  survive into that list. Stated at the top of the record.
- **The two closure figures are not comparable.** 0.692 is 9/13 over the subset the audit
  probed; the full 48-specimen file had no runner until now and first executes at
  **20/48**. Recorded so the two are never reported as one trend.
- Stage 7's attribution has not run, so the AST question is open, not answered.
- The commit protocol hook blocked this commit once because the ledger and status edits
  were placed in the same compound command as `git commit`; the hook evaluates before
  execution, so those edits never ran. Third occurrence of the same operator error this
  session — recorded rather than silently retried.

**Effect on the overall project.** Implementation is now gated by a written decision per
recommendation rather than by the reports' authority.

**Next intended step.** §3 evidence-graph hardening (lead, confined to `reasoning/`), with
full-ontology probing dispatched in parallel as it touches no source.

---

## 2026-08-07 (sixth entry) — explicit evidence graph (directive §3)

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `e435c77`

**Objective.** Replace a narrow acyclicity argument with a real one, and give the
established/provisional/not-evidence distinction a mechanical home.

**Files and systems changed.** New `src/hamiltonian_lang/reasoning/evidence.py` and
`tests/reasoning/test_evidence_graph.py`; `reasoning/check.py` builds and validates the
graph; `DECISIONS.md` D-040.

**What was completed.** An explicit claim graph with a cycle validator over all four edge
kinds, a weakest-link `effective_class`, cycle-safe transitive obligation collection, and
invariants E1/E2/E3/E4/E7/E8 checked by name. Wired into `check_reasoning` so it runs on
every module, not just when asked.

**Decisions made and why.** D-040. The load-bearing one: the textual-order rule is
demoted from "the acyclicity argument" to "a cheap first line", because it is sound only
for single-module source-order construction and never saw `proved` edges at all.

**Tests and verification actually executed.**
- `.venv/bin/python -m pytest` → **6270 passed, 5 skipped, 0 failed** (6252 before)
- `tests/reasoning/` → 98 passed (18 new)
- `.venv/bin/ruff check src tests` → clean; `.venv/bin/mypy src/hamiltonian_lang` → clean, 89 files
- hash stability → **0 changed**
- driven directly, the exploit shape yields E1 + E2 + E3 — the E1 hit is reachable only
  because PROOF edges are walked

**Failures and unresolved uncertainty.**
- **The graph is a second check, not the primary one.** The incremental rules still do the
  rejecting in practice; the validator has not yet caught anything the incremental rules
  missed. Its value is for construction paths that do not exist yet (imports), so it is
  currently insurance rather than demonstrated defence.
- E8 has a field and a check but **no import mechanism to exercise it**. Untested against
  a real cross-environment claim.
- The `propositions` pool holds both ESTABLISHED and PROVISIONAL claims. Only the comment
  was corrected; the dict was not split, so the distinction lives in `self.pending` and
  the graph rather than in the pool's own shape.

**Effect on the overall project.** Directive §3's E1, E2, E3, E4, E7, E9 now have named,
executable checks. Measured maturity is unchanged.

**Next intended step.** §4 scoped Γ, then §5 partiality contracts. The compositionality
study and the 486-atom probe are running in parallel.

---

## 2026-08-07 (seventh entry) — the AST fork decided; circular laws rejected

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `a69261f`
**Stage:** directive §7/§8 decided; §3 extended

**Objective.** Decide, from measurement rather than recommendation, whether HML's
position-specific AST is the cause of compositional failure — and fix what the
measurement exposed.

**Files and systems changed.** `semantics/__init__.py` gains `_check_law_cycles`
(HML-S607); new `tests/semantics/test_law_cycles.py`; a corrected fixture in
`tests/roundtrip/test_importers.py`; `DECISIONS.md` D-041, D-042 and a correction;
`docs/hml_v2/COMPOSITIONALITY_STUDY.md` and the 48-specimen harness.

**What was completed.** The 48 composition specimens were encoded and executed for the
first time. The AST fork is decided: **do not rewrite.** Circular probability laws are now
rejected.

**Decisions made and why.** D-041 rejects the generic Apply/Bind/Attribute core on three
measurements, the decisive one being that the generic core *alone* reaches 27/48 = 0.563 —
below the Level 2 threshold — while targeted repairs alone reach 41/48 = 0.854. The
rewrite is neither necessary nor sufficient. Accepted instead: local repairs, two targeted
additions (abstraction; a binder over statements), and a ~40-line binder protocol.

**Tests and verification actually executed.**
- 48-specimen composition: **STRICT 20/48 = 0.417**, FRAMEWORK 20/38 = 0.526
- failure attribution over 28 failures: GRAMMAR 14 · TYPE 8 · COMPILER 3 · CONSTRAINT 2 ·
  SCOPE 1 · **CANONICAL 0** (12 predicted) · **BACKEND 0** (6 predicted) · SPECIMEN 0
- `.venv/bin/python -m pytest` → **6279 passed, 0 failed** (6270 before)
- law cycles: mutual pairs, 3-cycles, self-via-parameter and self-via-`given` all rejected;
  two- and three-level hierarchies and every shipped probabilistic example accepted
- hash stability: **0 changed**

**Failures and unresolved uncertainty.**
- **The two closure figures measure different things and must never be trended together.**
  0.692 is 9/13 on the legacy subset; 0.417 is 20/48 on the full set. Same SHA, different
  instruments.
- **One of the study's three reported silent losses does not reproduce.** CT-018 claimed
  conditional expectation types identically to unconditional; measured, the types differ
  when conditioning on a random variable, and the canonical identities differ in *both*
  cases. Corrected in DECISIONS.md rather than repeated. CT-022 and CT-038 are real.
- **The law-cycle check found a latent defect in an existing test fixture** —
  `law m ~ Normal(location := m, ...)`. The fixture was corrected; had the check been
  written to accommodate it, a real unsoundness would have been preserved to keep a test
  green.
- D-041's confidence is **~0.75**, not higher: the two targeted additions are real and
  their eventual shape may yet argue for generality. A falsification condition is recorded.
- CT-038 (unguarded division) is **not fixed** — it is what D-036's precondition contracts
  exist to close, and that work has not started.

**Effect on the overall project.** The largest architectural question in the programme is
closed on evidence, and closed *against* the rewrite. The measured closure ceiling for the
accepted plan is 0.854.

**Next intended step.** §4 scoped Γ, then §5 partiality contracts (which closes CT-038).

---

## 2026-08-07 (eighth entry) — scoped Γ (directive §3)

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `ae9a2a0`

**Objective.** Make the frame stack load-bearing and give HML a construct for local
assumptions.

**Files and systems changed.** `reasoning/refinement.py` (Frame, Consistency, frame
stack); `ast/nodes.py` (`ScopeStmt`); lexer, parser, resolver, type checker, canonical and
`hml` backend; `tests/freeze/frozen_subset.py`; new `tests/reasoning/test_scoped_gamma.py`;
`DECISIONS.md` D-043; new `docs/hml_v2/CURRENT_TRUTH.md`.

**What was completed.** `scope … end`; facts confined to their frame in all four
directions (after, before, sibling, nested); local inconsistency detected, warned and
contained.

**Tests and verification actually executed.**
- `pytest` → **6299 passed, 5 skipped, 0 failed** (6279 before); 20 new
- `ruff` clean; `mypy src/hamiltonian_lang` clean, 89 files
- hash stability → **0 changed**; scope round-trips hash-stable through the `hml` backend
- composition re-run → **STRICT 21/48 = 0.438**, FRAMEWORK 21/38 = 0.553

**Failures and unresolved uncertainty.**
- **Composition moved 0.417 → 0.438 only.** One specimen. The gate is 0.85 and the
  remaining failures are 14 GRAMMAR and 8 TYPE, which scoped Γ was never going to touch.
  Recorded plainly because the temptation is to present a completed subsystem as progress
  toward a gate it barely moves.
- Contradiction detection is syntactic and incomplete by design; it catches deliberate
  contradictions, not all of them.
- The assumption-discharge *rule* (concluding `not P` from a contradiction under `P`) is
  **not implemented**. `pop()` returns the frame so it can be, but the proof-by-
  contradiction pattern is not yet expressible end to end.
- Quantifier and concept bodies do **not** yet push refinement frames — only `scope` does.
  `assume` is a statement and cannot appear inside a quantifier body, so there is nothing
  to leak today, but the frame kinds exist ahead of that.

**Effect on the overall project.** Maturity criterion 3.3 (scoped assumption context) has
an implementation for the first time. Measured maturity otherwise unchanged.

**Next intended step.** §4 partiality contracts, which closes CT-038 and is the largest
single remaining soundness gap.

---

## 2026-08-07 (ninth entry) — term-level partiality closes a CRITICAL exploit

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `9877379`

**Objective.** Close the division-by-zero exploit found by the rule audit, and unify
definedness under one contract registry (D-036).

**Files and systems changed.** New `reasoning/partiality.py` and
`tests/reasoning/test_partiality.py`; `reasoning/check.py` (term-level obligations,
dedup, refutation); `reasoning/kernel.py` (`divide_both_sides` loses its redundant
ObligationSpec); `type_system/__init__.py` (`HML-T435`); `DECISIONS.md` D-044.

**What was completed.** Definedness moved from rule-keyed to term-keyed. Refuted
obligations now REJECT rather than sit OPEN. Matrix elementwise shape conformance checked.

**Tests and verification actually executed.**
- the exploit: `VERIFIED`/`PROVED` before → **REJECTED, HML-R715** after
- `pytest` → **6322 passed, 5 skipped, 0 failed** (6299 before)
- `ruff` clean; `mypy` clean, 90 files; hash stability **0 changed**
- composition re-run → **21/48 = 0.438, unchanged**

**Failures and unresolved uncertainty.**
- **This was a CRITICAL soundness blocker that shipped in the V2 spine and survived two
  red-team rounds.** It was found only when a third agent audited the rules for a
  different purpose. The previous red team attacked obligation *evasion* and did not try
  respelling the operation.
- **Two self-inflicted defects while fixing it**: the new obligations were never passed to
  Γ (permanently OPEN), and the same obligation was raised three times. Both caught by the
  existing suite, both recorded.
- Composition is **unchanged at 0.438**. This fix bought soundness, not coverage, and must
  not be reported as movement toward the 0.85 gate.
- The registry covers `/`, `^`, `tan` as CONTRACTED. **Matrix inverse, indexing,
  normalisation, conditional probability, expectation and argmin/argmax are NOT yet
  contracted** — D-036 names them and they remain outstanding.
- 32 enforcement gaps from the ontology probe: **one fixed** (HML-T435), 31 outstanding,
  6 of them critical.

**Effect on the overall project.** The single largest known soundness hole is closed, and
closed generically rather than per-rule. Maturity criterion 3.4 has a partial
implementation for the first time.

**Next intended step.** The remaining CONTRACTED operations, then the 28 measured
composition failures (14 GRAMMAR, 8 TYPE) which are the only route to the 0.85 gate.

---

## 2026-08-07 (tenth entry) — SE difficulty calibration; binder/shadowing fix

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `5888cd0`
**Stage:** signal-first directive §2 (calibration) and §3 (binder fix)

**Objective.** Determine, before further engineering, whether a structured-English
difficulty region with headroom exists for this model — and fix the binder defect.

**SE-ONLY CALIBRATION (no HML involved).** Model `gemma4:31b`, digest verified against the
pin `6316f0629137…`, temperature 0, 8192 completion allowance.

| stage | tasks | correct |
|---|---|---|
| CAL-1 | 3 (screening / constrained min / domain trap) | **3/3** |
| CAL-2 | 5 (urn conditional / quantifier order / two-constraint LP / units / extraneous roots) | **5/5** |
| CAL-3 | 4 (combinatorics / reflecting walk / LP vertices / floor identity) | **running** |

Answer keys verified independently — SymPy for CAL-2, exhaustive enumeration for CAL-3 —
before any model call. A scorer self-test (14 synthetic cases for CAL-2, 10 for CAL-3) ran
before the first scientific call and had to pass for the run to proceed.

**Gemma calls used: 9 of the 13 cap** (CAL-1 consumed 4, not 3 — the first run crashed on a
field-name error *after* the first completion; that wasted call is counted).

**No truncation anywhere**: completions ran 877–2392 tokens against an 8192 allowance, every
one `finish=stop`. The model is not budget-limited on these tasks.

**Binder fix (D-045).** D-006's no-shadowing rule was being applied to mathematical binders,
so `derivative(f, x)` was rejected whenever `x` was declared. Binder kinds are now exempt;
value declarations are not.

**Tests and verification actually executed.**
- `pytest` → **6328 passed, 5 skipped, 0 failed** (6322 before)
- binder body reference resolves to the binder (`sym:#1.0`), not the module variable
- `derivative(f, x)` and `derivative(f, z)` produce an **identical content hash**
- a concept parameter shadowing a module `var` is **still** HML-N302
- composition → **22/48 = 0.458** (was 21/48 = 0.438)

**Failures and unresolved uncertainty.**
- **Eight of eight calibration tasks so far are correct.** This is the third consecutive
  corpus to saturate (93%, 100%, now 8/8). The tasks were deliberately built around
  semantic traps HML targets — base rates, quantifier order, extraneous roots, ignored
  constraints — and the model handled all of them.
- **My prediction about the binder fix was wrong.** It was argued as high-leverage for
  composition and moved exactly one specimen. The fix is right on its own terms; the
  leverage claim was not, and the remaining 26 failures need individual diagnosis rather
  than another hopeful structural fix.
- One calibration call was wasted on a preventable coding error and is counted against the
  budget rather than quietly excluded.

**Effect on the overall project.** The largest project-level risk — that no SE headroom
region exists — is being measured directly for the first time, and the early evidence is
not encouraging.

**Next intended step.** Await CAL-3. If it also saturates, the calibration budget is
exhausted at 13 and the honest return is `NO_USEFUL_SE_HEADROOM_REGION_FOUND` with an
analysis, rather than another forty calls.

---

## 2026-08-07 (eleventh entry) — SE calibration exhausted: NO_USEFUL_SE_HEADROOM_REGION_FOUND

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `3e3662b`
**Stage:** signal-first directive §2C — calibration budget exhausted at 13/13

**Objective.** Determine whether a structured-English difficulty region with headroom
exists for this model, before authorising further HML engineering.

**Files changed.** New `docs/evaluation/SE_CALIBRATION_REPORT.md`; CAL-3 results.

**Result. 10 valid observations, 10 correct. No usable difficulty region found.**

| stage | calls | valid | correct |
|---|---|---|---|
| CAL-1 | 3 | 3 | 3 |
| CAL-2 | 5 | 5 | 5 |
| CAL-3 | 4 | **2** | 2 |
| total | **13** | 10 | **10/10** |

**Tests and verification actually executed.**
- digest verified against the pin before every stage
- answer keys verified independently: SymPy (CAL-2), exhaustive enumeration (CAL-3)
- scorer self-tests (14 and 10 synthetic cases) passed **before** the first scientific call
- CAL-1/CAL-2 completions: 877–2392 tokens, all `finish=stop` — no truncation

**Failures and unresolved uncertainty.**
- **The two CAL-3 "failures" are truncation, not difficulty.** Both `finish=length` at
  exactly 8192. `cal3_floor_identity` was mid-way through a *correct* fractional-part
  argument. Scoring them as incorrect would have manufactured headroom out of a token
  limit — the exact artifact the 4096-vs-8192 effect warned about. Recorded
  MEASUREMENT_INVALID at this budget.
- **This was my task-design error.** CAL-3 was meant to be harder; it was merely longer.
  Length is not difficulty.
- **The one axis on which the model failed is unusable for this hypothesis.** HML is more
  verbose than prose, so on a length-limited task it truncates sooner. A corpus of such
  tasks would measure verbosity while appearing to measure reasoning.
- **Three corpora have now saturated** (93%, 100%, 10/10). The mechanism is understood: the
  semantic-trap genre HML targets is canonical and heavily represented in training data,
  and novel constants do not defeat a memorised pattern.
- **Structural tension:** the families where this model is plausibly weak (combinatorics 0%,
  asymptotics 0%, abstract algebra 5%, topology 10%) are the families where HML's own
  ontology coverage is near zero. The region where headroom might exist is largely the
  region HML cannot express.
- **Not measured:** whether a 16384 budget converts the truncations into genuine failures;
  whether bounded-length multi-fact state-tracking tasks saturate; whether a weaker model
  shows headroom.

**Effect on the overall project.** The gate at §2C is reached and not passed. Per the
directive, scientific calls stop here rather than continuing for another forty. No HML
acquisition call may be made, and none was: **total Gemma calls 13, all structured-English,
zero HML.**

**Next intended step.** Return to the user. The choice of difficulty axis, model, budget,
or acceptance of the negative finding is a scientific-direction decision, not an
engineering one.

---

## 2026-08-07 (twelfth entry) — binder protocol; `free_names` omission fixed

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `63df820`

**Objective.** Fix the reported `free_names` binder omission, generally rather than by
adding branches.

**Files and systems changed.** `ast/nodes.py` (`binder_of`, `expr_children`,
`BINDER_KINDS`); `verification/obligations/evaluate.py` (`free_names` rewritten onto the
protocol with a structural fall-through); new
`tests/verification/test_free_names_binders.py`; `DECISIONS.md` D-046.

**What was completed.** Free variables inside all four D-026 binders and the seven
non-binder V2 forms are now reported; bound variables still are not; an integral's limits
and a limit's approach point are correctly treated as outside the binding.

**Decisions made and why.** D-046. A protocol rather than eleven branches, because eleven
branches rebuild the fragility the compositionality study measured (79 dispatch sites, 7
handling only `Quantifier`).

**Tests and verification actually executed.**
- reproduced first: `free_names(integral(y, x, 0, 1) > 0)` → `[]`, `forall` → `['y']`
- severity measured, not asserted: `ObligationTask.closed()` returned **True** for a
  proposition with a free `y`; now returns False
- `pytest` → **6342 passed, 5 skipped, 0 failed** (6328 before), 14 new
- `ruff` clean; `mypy` clean, 90 files; hash stability **0 changed**

**Failures and unresolved uncertainty.**
- **This was wrong in the dangerous direction** — under-reporting free names means a name
  the engine cannot see is a name it will not require to be pinned. End-to-end it was
  masked by an unrelated "outside the symbolic subset" guard, so no wrong verdict was
  delivered; the mask disappears when that subset is widened.
- My first version of the recurrence guard assumed every binder has a `body` field;
  `SetComprehension` uses `predicate`. The test failed, and was rewritten to read the
  dataclass fields — assuming a spelling is how this class of bug arises in the first place.
- **The protocol is used by `free_names` only.** The other ~78 binder dispatch sites are
  untouched; they may carry the same class of omission and have not been audited.
- Composition is unchanged; this was a soundness fix, not a coverage one.

**Effect on the overall project.** One of the two defects the compositionality study
flagged as latent is closed, and the shared abstraction it recommended now exists.

**Next intended step.** Unchanged: the SE calibration gate did not pass, so scientific
direction is with the user.

---

## 2026-08-07 (thirteenth entry) — synthetic difficulty lab; state complexity saturates

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `e7e5c3b`
**Stage:** HML-SIGNAL-RESCUE-015 §2-§8

**Objective.** Find a real SE difficulty region using novel, machine-generated,
bounded-length, compositional mathematics — after canonical textbook traps saturated.

**Files and systems changed.** New `evaluation/h2/difficulty_lab/` (four generator
families, deterministic oracles, scorer, offline validation gate, CAL-S runner) and
`docs/evaluation/SYNTHETIC_CALIBRATION_REPORT.md`. **No compiler source was touched**, as
the directive requires while headroom is unresolved.

**What was completed.** A neutral generator lab: structures built in Python, English
rendered from them, never HML-first. Validated offline before any model call — 119
instances per family, deterministic from seed, zero duplicate prompts, non-degenerate
answers, and 40/40 independent cross-checks on the two families where a second
implementation was practical (each re-parsing the rendered English, so a rendering bug
would surface rather than be mirrored). Scorer and extraction self-tests passed first.

**Result: 9 valid observations, 9 correct, 0 truncations.**

| stage | level | valid | correct |
|---|---|---|---|
| CAL-S1 | L3 | 3 | 3 |
| CAL-S2 | L5 | 3 | 3 |
| CAL-S3 | **L7** | 3 | 3 |

L7 = depth-16 dependency chains with 6 distractors; 10-variable propositional worlds with
26 constraints. Completions 900-2400 tokens against an 8192 allowance.

**Decisions made and why.** L6/L7 were added after L3 and L5 both returned 3/3. The
protocol asks for levels tuned to the actual generators, and extending depth keeps the
answer one line and the oracle cheap — it grows interacting state, not length. Stopped at
9 of 12 calls rather than spending the remainder on an axis that had clearly saturated.

**Failures and unresolved uncertainty.**
- **`SYNTHETIC_STATE_COMPLEXITY_SATURATED`.** No headroom on this axis.
- **A real limitation of my design:** difficulty here is *many easy steps*, not
  *individually hard steps*. A depth-16 chain is tedious; each link is one multiply-add.
  No family was generated where a single step is hard — non-linear systems, case-splitting
  search, problems with no forward-chaining route. This model may be bounded by step
  difficulty rather than step count, and these nine calls do not answer that.
- **Not generated at all:** probability-with-dependence, geometry, multi-step optimisation.
- The structural tension stands: the families where this model is plausibly weak are the
  families where HML's own ontology coverage is near zero.
- The two calibration protocols measure different things and **must not be pooled** into a
  single accuracy estimate.

**Effect on the overall project.** Two independent instruments have now failed to find
headroom for this model. The bottleneck is not HML's completeness.

**Next intended step.** Return to the user. Four options are costed in the report: weaker
model, broader domain, different endpoint, or accept the negative finding. All are
scientific-direction decisions.

---

## 2026-08-08 — context checkpoint and strategic pivot

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `5ce1054`
**Stage:** HML-CONTEXT-CHECKPOINT-2026-08-08. No implementation, no model calls.

**Objective.** Leave a lossless, reproducible checkpoint for a fresh Claude context.

**Files changed.** New `docs/handoff/HML_HANDOFF_2026-08-08_SIGNAL_PIVOT.md`.

**Verified at checkpoint time, not inherited.**
- worktree `/Users/moheet/hml_v2_worktree`, branch `feature/hml-reasoning-kernel-v2`
- HEAD == remote == `5ce1054`; tree clean; only `ollama serve` running (idle)
- `pytest` → **6342 passed, 5 skipped, 0 failed**
- composition → **STRICT 22/48**, FRAMEWORK 22/38
- all six calibration result files committed; nothing withheld

**Two accounting discrepancies resolved.**
1. **Recorded vs actual calls.** The JSON files record 21 calls; **22 were actually made**.
   One was consumed by the first `cal1.py` run, which crashed on a field-name error
   (`c.text` vs `c.content`) *after* the completion returned. It appears in no JSON and is
   charged to the budget in the handoff rather than quietly dropped.
2. **CAL3.json is dangerous to read raw.** It records `total=4, correct=2`, but both
   failures are `finish_reason=length` at exactly 8192 — truncation, not error, one of them
   mid-way through a *correct* argument. The JSON has no truncation-aware `valid` field;
   the exclusion lives only in `SE_CALIBRATION_REPORT.md`. Reading it as "2/4, headroom
   found" would send a fresh context down a dead end, so the handoff flags it explicitly.

**Effect on the overall project.** The recommended research architecture has changed. It is
no longer "finish HML → find harder maths → paired benchmark" but a neutral semantic world
factory rendered three ways (structured English / generic AST / HML) feeding representation
microbenchmarks. **A generic AST is now a required control** — without it, any HML benefit
could be a benefit of structure in general and would be attributed wrongly.

**Failures and unresolved uncertainty.** Unchanged and recorded in the handoff: no valid
HML-vs-SE result exists; zero HML model calls have ever been made; 31 enforcement gaps
remain (6 critical, none audited for reachability); the saturation finding is bounded by a
generator that varied step *count* rather than step *difficulty*.

**Next intended step.** Build the representation arena on top of the existing neutral
generator. Do not make another full-problem model call first.

---

## 2026-08-08 — port the reproducible CI environment repair to reasoning-kernel-v2

**Branch.** `feature/hml-reasoning-kernel-v2` · **Worktree.** `/Users/moheet/hml_v2_worktree`
· **Stage.** CI environment repair, ported.

**Objective.** Make this branch green using the already-proven fix, without importing stale
documentation from the branch it was proven on.

**What happened.** The CI repair was developed and verified on
`integration/m1.5-paper-derived-closeout` @ `8e1c4df`, which GitHub reports SUCCESS. That is
a **divergent branch**: this one never received the fix and stayed red at `354a657` for the
same environment reason. The failures were never semantic.

**The three ported defects, unchanged from `8e1c4df`.**

1. **SymPy was never installed by CI.** `pip install -e ".[dev]"` listed no SymPy, and
   `equivalence/sympy_bridge.py` imports it under `try/except` with
   `SYMPY_AVAILABLE = False`, so nothing failed at import — it surfaced downstream as
   "sympy is not importable in this environment" across symbolic equivalence, counterexample
   search, answer equivalence, negation checking, verifier obligations, partiality and
   fixture reachability. Now an `equivalence = ["sympy>=1.14,<2"]` extra that `[dev]`
   depends on. Optional rather than core: the compiler genuinely runs without it, and
   `dependencies = []` stays true. Pinned to the 1.14.0 toolchain probe with a major-version
   ceiling.
2. **A portability error.** `SCORING_WORKERS >= MAX_WORKERS` compares this machine's CPU
   count against a frozen measured Ollama slot count; a 2-CPU runner reads `2 >= 4`. Both
   assertions now test throttle-freedom,
   `SCORING_WORKERS >= min(MAX_WORKERS, os.cpu_count())`. **`MAX_WORKERS = 4` untouched.**
3. **Unbounded workflow concurrency** — per-ref group with `cancel-in-progress`.

**Decisions made and why.** `git cherry-pick -n` then `git checkout HEAD -- docs/` rather
than a plain cherry-pick: `PROJECT_STATUS.md` and `PROJECT_LEDGER.md` conflicted because the
source commit's text is written about the integration branch. Importing it would have put
false branch-specific history into this branch's record. Only the three functional files
were taken. The untracked `evaluation/arena/` was left untouched throughout.

**Tests and verification actually executed.**

| check | result |
|---|---|
| docs differ from feature HEAD after restore | **0 files** |
| `tests/evaluation/test_syntax_gate_harness.py` | 28 passed |
| `tests/equivalence` + `tests/verification` | all pass |
| local `./scripts/conformance.sh` | **CONFORMANCE: PASS** |
| fresh clone of this branch + clean `[dev]` venv | sympy **1.14.0** installed |
| clean-venv `./scripts/conformance.sh` | **CONFORMANCE: PASS** |

**Failures and unresolved uncertainty.**

- GitHub Actions had **not yet reported** when this entry was written. Not declared repaired
  until GitHub itself reports success on this branch's new HEAD.
- `recovery/session-limit-2026-08-05` and `hml-v1-concept-kernel` remain red. That reflects
  their last historical commits and is deliberately not rewritten.

**Effect.** This branch — the one carrying the actual V2 development state and the signal
pivot — can run CI again.

**Next intended step.** Confirm GitHub reports SUCCESS, then the Representation Arena per
`docs/handoff/HML_HANDOFF_2026-08-08_SIGNAL_PIVOT.md`.

## 2026-08-08 — the Representation Arena: three information-matched arms, proved by round trip

**Branch.** `feature/hml-reasoning-kernel-v2` · **Worktree.** `/Users/moheet/hml_v2_worktree`
· **Stage.** Signal pivot — offline representation arena, `arena-1.0.0`.
**Starting SHA.** `ff915ad` (the CI repair above, already pushed).

**Objective.** Build the smallest neutral arena able to test whether HML gives a
*representation-level* advantage over information-matched structured English and a generic
semantic AST, on identical semantic worlds with identical questions and deterministic
oracles. **No model call was to be made until the arena, oracles, parity checks and scoring
tests were complete.** None was: **zero model calls in this entry.**

**The handoff's plan was not executable as written, and this is the important finding.**
`docs/handoff/HML_HANDOFF_2026-08-08_SIGNAL_PIVOT.md` §J directed that a rendering layer be
added to `evaluation/h2/difficulty_lab/families.py`, emitting three views "of the *same*
generated structure". **That generator does not retain its structure.** `_algebraic`,
`_logic`, `_quantifier` and `_mixed` build their English inline and return a `Specimen`
holding a prompt string, an answer and metrics; the dependency DAG, the constraint set and
the relation table are gone by the time it returns. There is nothing left to render a second
way. The arena therefore rebuilds the same worlds **structure-first** as `arena-1.0.0`.
`difficulty-lab-1.0.0` is left byte-identical — its hashes are pinned in the handoff and the
synthetic calibration results are recorded against it. The L1–L5 ladder is **copied, not
imported**, so the frozen evidence gains no new importer;
`test_levels_have_not_drifted_from_the_difficulty_lab` fails if the two ever diverge.

**Files and systems changed.** All new, 25 files, 3875 lines:
`evaluation/arena/{ir,worlds,oracles,decoders,parity,scoring,budget,corpus,validate}.py`,
`evaluation/arena/renderers/{base,english,ast_json,hml}.py`,
`evaluation/arena/endpoints/{common,next_action,contrast,corruption}.py`,
`tests/arena/test_{worlds,parity,endpoints,scoring}.py`,
`docs/evaluation/ARENA_DESIGN.md`. Nothing outside `evaluation/arena/`, `tests/arena/` and
that one document was touched. **No compiler source was modified**; the arena imports the
compiler but does not change it.

**Decisions made and why.**

1. **Parity is proved per world, not asserted.** `canonical_world(decode_X(render_X(w))) ==
   canonical_world(w)` for all three arms. "Information-matched" is easy to claim and easy
   to get wrong; an arm that quietly dropped a fact or stated a type the others left
   implicit would look like a representation effect and be a content difference.
2. **The HML decoder uses HML's own parser**, not a second implementation. A private parser
   could disagree with the compiler and would then certify a rendering the compiler reads
   differently — the "authoritative-looking output that is wrong" failure CLAUDE.md names as
   the worst in this codebase. This also makes parity prove the HML arm *means* what the IR
   means, not merely that it compiles.
3. **A finite relation is stated in closed form in every arm.** The first design expanded it
   into one fact per ordered pair so no arm could exploit a shorter closure idiom. That is
   un-renderable in HML — see the ontology finding below — so enumeration was available to
   two arms and not the third, and using it would have measured that gap rather than the
   representation.
4. **The generic AST control was compacted.** Fully tagged nodes at `indent=2` ran **4.7x**
   structured English on the algebraic family. A control inflated that far is not a control:
   every HML win would have been equally consistent with "HML beats verbose JSON". Recoded to
   the standard lightweight idiom (a name is a JSON string, an integer a JSON number), which
   is unambiguous because the IR's terms are only names and numbers. Keys were **not**
   abbreviated to `n`/`o`/`a` — that buys tokens by making the control cryptic, the same
   error inverted.
5. **Answers are forced choice or one word from a closed set, never free-form.** If the model
   had to *write* its answer in each arm's notation, HML would be scored partly on how hard
   HML is to emit, which is a different question from whether it is a better representation
   to reason from.
6. **Next-action correctness is a per-option testable property.** "What is the next step?" has
   no unique answer when two variables are simultaneously ready, which happens constantly in
   a DAG; scoring it would punish a model for choosing a different valid step.

**Two findings that stand independently of the arena.**

- **HML has no uninterpreted predicate.** A declared `Predicate` is not callable
  (`HML-T470`), and the only callable form, `def R(x, y) : Proposition := ...`, requires a
  body. A finite relation can therefore only be given in closed form. This forced decision 3
  above and is an ontology gap worth its own record.
- **A latent semantic defect in the HML renderer, caught by parity.** The relativised
  symmetry claim `forall x : Real . x in D implies forall y : Real . y in D implies R(x, y)
  implies R(y, x)` parsed, and meant the right thing **only by luck of `implies` being
  right-associative**. A quantifier body runs to the end of the expression, so an unbracketed
  nested quantifier absorbs whatever follows. Nested quantifiers are now explicitly
  bracketed. Correct by accident is not correct, and compiling was not enough to detect it —
  only the round trip through the compiler's own parser was.

**Tests and verification actually executed.**

| check | exact command | actual result |
|---|---|---|
| arena tests | `.venv/bin/python -m pytest -q tests/arena` | **100 passed, 0 failed**, exit 0 |
| pre-flight gate | `.venv/bin/python -m evaluation.arena.validate` | **exit 0, all 8 checks PASS**; 306 items, 69 pairs |
| lint | `.venv/bin/ruff check evaluation/arena tests/arena` | **All checks passed** |
| full suite (before this commit, tree at `ff915ad` + arena) | `.venv/bin/python -m pytest -q` | **6442 passed**, 5 skipped, 7 xfailed, 7 xpassed, **0 failed** |
| parity sweep, wider than the gate | 600 worlds x 3 arms, ad hoc | **1800 round trips, 0 failures** |
| HML arm compiles | 214 worlds via the real compiler, inside the gate | **214/214** |

Baseline before the arena was 6342 passed; the delta is exactly the 100 new tests. The
6442-pass run was executed against a working tree that already contained `ff915ad`.

`ruff format` was **not** run: the repository is not format-clean (146 of 220 files would be
reformatted), so formatting these files would make them inconsistent with the rest of the
tree and is out of scope for this commit.

**Measured budget** (`cl100k_base`, 306-item gate corpus, full prompt): SE **328.8** mean
tokens, HML **338.0**, AST **576.3**. SE and HML are within 2.8%; the AST control is 1.75x
the shortest arm and is the arm still carrying a length penalty.

**Failures and unresolved uncertainty.**

- **Nothing here is evidence about any model.** Zero model calls. The arena's own numbers are
  properties of the code.
- **The AST length confound is real and not removed.** An HML > AST result cannot yet be
  attributed entirely to HML semantics. Deliberately not redesigned further before a pilot.
- **`MIXED_STATE_COMPOSITION` is not ported.** Three families, all inside HML's covered
  region — the handoff's structural tension (the families where the model is weak are the
  families where HML's coverage is near zero) is untouched by this work.
- **Next-action covers two families, not three.** A finite relation has no natural "next
  result", so the quantifier family carries the contrast endpoint instead.
- **`OPERAND_ORDER` twins have answers that are exact negations.** Not exploitable within an
  item, since each is scored in isolation and twins are never shown together, but it is a
  pattern a corpus-level analysis should be aware of.
- **A concurrent session committed `ff915ad` to this branch mid-work.** It touched
  `pyproject.toml`, a workflow, one test and both protocol documents, and nothing the arena
  owns. Verified finished before this commit: no lock files, no processes on the worktree, no
  file modified in the preceding ten minutes.

**Effect on the project.** The offline half of the signal pivot exists and is checkable. The
arena can pose one semantic question in three provably information-matched notations and score
the answers without a model judging anything. It does not yet say whether HML helps.

**Next intended step.** SE-only developmental model selection on Endpoint B — treatment arms
must not influence which model is chosen — then freeze, then the acquisition sanity check,
then the first Endpoint-B representation pilot.

## 2026-08-08 — arena committed; SE-only developmental screen INVALID (truncation + a lost run)

**Branch.** `feature/hml-reasoning-kernel-v2` · **Worktree.** `/Users/moheet/hml_v2_worktree`
· **Stage.** Signal pivot — model-facing stage 1. **Starting SHA.** `6462463`.

**Objective.** Commit the arena, then find a developmental model whose **structured-English**
Endpoint-B pair accuracy lands in 30–70%. Treatment arms must not influence the choice, so
the screen is SE-only by construction.

**What was completed.**

1. **The arena was committed and pushed** (`6462463`), local == remote, tree clean. Gate
   green (306 items, 69 pairs, 8/8 checks), 100 arena tests, ruff clean.
2. **`bands.py`** — disjoint seed bands (GATE 200k · DEV_SELECTION 300k · ACQUISITION 400k ·
   PILOT 500k · CALIBRATION_LEGACY 900k) with `assert_band` / `assert_disjoint`. The named
   contamination stop condition is now enforced by code rather than by memory.
3. **`run_screen.py`** — the model-facing runner. Refuses to run a `DEV_SELECTION` stage with
   any arm but `SE`; one stateless call per item, so twins and arms cannot see each other.
4. **`endpoints/acquisition.py`** — six literal state-recovery items for the pre-pilot check.
5. **`gemma4:12b` pulled** (11.9B, Q4_K_M, digest `4eb23ef187e2c546…`). Only the 31B was
   installed, and the directive excludes it as first candidate; 12b is the nearest available
   rung in the same family, which keeps architecture and pretraining confounds controlled.
6. **`tests/arena/test_bands.py`** — 10 tests over band separation and both guards.

**The screen ran, and its result is INVALID. Two separate failures.**

**Failure 1 — a crash discarded 24 completed model calls.** `run_screen.py` had
`if __name__ == "__main__": raise SystemExit(main())` placed *above* the definition of
`_summarise`. Running the module as `__main__` therefore executed `main()` before that name
was bound. All 24 SE calls completed over ~36 minutes; the run then died with
`NameError: name '_summarise' is not defined` and **wrote nothing**. The console log is the
only surviving record and is committed verbatim as
`evaluation/arena/results/DEV_gemma4-12b_ATTEMPT1_LOST.console.txt`. This was my defect, it cost
~36 minutes of real compute, and it is recorded rather than quietly re-run.

**Failure 2 — 12 of 24 responses were truncated**, every one at exactly `max_tokens=4096`
with `finish_reason=length`. `gemma4:12b` is a *thinking* model: the twelve responses that
did finish averaged **2395** completion tokens, and the harder items ran past the ceiling.
The budget was mine to set and was set too low.

**Observed numbers, read off the committed log — reported because they were paid for, and
NOT used to select anything.**

| quantity | value |
|---|---|
| calls | 24 (12 pairs, SE only) |
| valid | 12 · **truncated 12** · errors 0 |
| single-item accuracy on valid responses | **12/12** |
| pairs scored | **2 of 12** — the other 10 had a truncated member and were dropped whole |
| pair both-correct | 2/2 on the two scorable pairs |
| mean completion tokens (valid) | 2395 |
| wall time | ~36 min |

**With 10 of 12 pairs dropped the screen cannot place this model anywhere in the 30–70%
band.** The 12/12 on valid items and 2/2 on scorable pairs must not be read as competence:
the truncated items are exactly the ones the model found hard, so what survives is a sample
biased toward the easy tail. No model has been selected.

**Repairs made (no further model calls).**

- The module-entry guard moved to the bottom of the file, below every function it reaches.
- **Records are now written incrementally** to a `.jsonl` sidecar as each call returns, so no
  future crash can destroy calls that have already been paid for.
- `_summarise` is wrapped: a summary failure degrades to an error field instead of losing the
  records, which are the expensive part.
- Fixed a reporting defect found by the repair smoke test: the acquisition per-kind breakdown
  keyed off a substring of the item id, so `FACT_CONTENT` and `FACT_COUNT` collapsed into one
  cell. It now keys off the item's recorded kind. Verified 6/6 distinct kinds per arm.

**Tests and verification actually executed.**

| check | exact command | actual result |
|---|---|---|
| arena tests | `.venv/bin/python -m pytest -q tests/arena` | **110 passed**, 0 failed |
| lint | `.venv/bin/ruff check evaluation/arena tests/arena` | **All checks passed** |
| runner end-to-end, no model | `run_screen acq --model NO_SUCH_MODEL_XYZ` | exit 0; 18 records written to both `.json` and `.jsonl`; summary computed |
| per-kind breakdown | same | 6 distinct kinds in each of SE/AST/HML |
| arena gate (unchanged) | `.venv/bin/python -m evaluation.arena.validate` | exit 0, 8/8 PASS |

The full 6k suite was **not** re-run for this commit: nothing outside `evaluation/arena/` and
`tests/arena/` changed since the 6442-pass run.

**Failures and unresolved uncertainty.**

- **No developmental model has been selected.** One of at most three candidates has been
  tried and its screen is void.
- **Runtime is now a live feasibility problem.** 24 calls took ~36 min *while truncating half
  of them*. Raising the ceiling makes each call longer, and the pilot is 72 calls across
  three arms. A naive re-run could take several hours.
- **Zero AST or HML model calls have been made.** No treatment arm has been observed, so
  nothing about representations is contaminated by this failure.

**Effect on the project.** The instrument is repaired and better than before — incremental
persistence means this class of loss cannot recur. The scientific position is unchanged: no
model selected, no representation evidence.

**Next intended step.** Decide the token-budget and runtime question before spending more
compute: raise `max_tokens` and accept a multi-hour pilot, disable the model's thinking mode,
or drop to a smaller/faster candidate. Then re-run the SE-only screen. Reported to the user
as `HML_ARENA_MEASUREMENT_INVALID`.

## 2026-08-08 — micro-screen: gemma4:e4b saturates Endpoint B; model-size search STOPPED

**Branch.** `feature/hml-reasoning-kernel-v2` · **Worktree.** `/Users/moheet/hml_v2_worktree`
· **Stage.** Signal pivot, developmental model selection. **Starting SHA.** `6e19fc9`.

**Objective.** Find a cheap competent developmental organism whose structured-English
Endpoint-B pair accuracy lands in 30–70%. Not to characterise any particular model.

**Runner preflight, executed before any model call.** `tests/arena/test_runner_preflight.py`
drives the whole chain with a fake client: **CLI argv → `main()` → calls → incremental JSONL
→ summary JSON → reload → assertions**. It goes through the *entry point* deliberately: the
NameError that discarded 24 calls was only reachable via `main()`, so a test that called
`run_screen` directly would never have caught it. Also covered: a truncated response yields
`valid=0` and `single_item_accuracy is None` (not `0.0`); a forced `_summarise` failure after
the calls land leaves all records on disk; the SE-only guard holds at CLI level. 7 tests,
all pass.

**`gemma4:4b` does not exist and the directive's step 1 could not be followed literally.**
`ollama pull gemma4:4b` failed with `pull model manifest: file does not exist`. An earlier
tag scrape of mine was wrong — the pattern matched `4b` inside `26b-a4b-it-bf16`. The real
family tags are `e2b`, `e4b`, `12b`, `26b`, `31b`. The 4B-class in-family model is therefore
**`gemma4:e4b`** (E-series naming; 8.0B raw parameters, Q4_K_M, digest
`c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb`). Using it keeps the
architecture and pretraining control the directive asked for. A `gemma3:4b` appeared on this
machine from another session and was **not** used — a different family would reintroduce
exactly the confound the in-family choice avoids.

**Micro-screen design.** 6 pairs = 12 isolated calls, structured English only, `max_tokens`
8192, temperature 0, one stateless call per item. Balanced 2 quantifier / 2 logic / 2
algebra. Drawn at `pair_offset=4`, so **zero overlap** with the items the 12B attempt
consumed — verified by test, not by inspection.

**Result — a clean, valid measurement.**

| quantity | value |
|---|---|
| calls | 12 (6 pairs, SE only) |
| truncations | **0** · invalid 0 · errors 0 |
| pair BOTH-CORRECT | **6 / 6 = 1.00**, 0 dropped |
| single-item | **12 / 12 = 1.00** |
| mean completion tokens | 1003.9 (max observed 1943, ceiling 8192) |
| mean prompt tokens | 317.5 |
| mean latency | 15.4 s |
| wall time | ~3 min |

Every one of the six pairs was both-correct, across all three contrast operators.

**Decision, by the pre-registered rule (5–6/6): STOP the model-size search.** Even the
smallest in-family candidate is too strong on this endpoint. `gemma4:e2b` was **not** tried,
because the rule says stop rather than keep shrinking.

**What this supports, stated precisely.**

> `gemma4:e4b` (8.0B, Q4_K_M) answers L3 Endpoint-B minimal-contrast pairs at 6/6 pairs and
> 12/12 items, in structured English, with no truncation and ~1000 completion tokens.

**What it does NOT support — do not write or imply any of these:**

- HML has no effect. **No HML has ever been shown to any model.**
- Endpoint B is saturated at every difficulty. Only **L3** was screened; L4–L7 are untested.
- Endpoints A and C are saturated. Neither has been run against any model.
- Smaller models would also saturate. `e2b` was deliberately not tried.
- The 12B result corroborates this. That run is `INVALID_INSTRUMENT` and its 12/12 was
  informative censoring — it must not be pooled with this.

**The strategic problem this creates.** This is the **third** independent instrument to find
no headroom for this model family: SE textbook calibration (10/10 valid), the synthetic
difficulty lab (9/9), and now the arena's Endpoint B at 8B (12/12). A representation pilot
run on a saturated control cannot detect an HML advantage in either direction — a ceiling
leaves no room to move, which is the exact trap that voided `eval001` and the 24-task v1
benchmark. **Running the Endpoint-B pilot at L3 now would produce an uninterpretable
result.**

**Tests and verification actually executed.**

| check | exact command | actual result |
|---|---|---|
| runner preflight | `pytest -q tests/arena/test_runner_preflight.py` | **7 passed** |
| arena tests | `pytest -q tests/arena` | **117 passed**, 0 failed |
| lint | `ruff check evaluation/arena tests/arena` | **All checks passed** |
| micro-screen | `run_screen micro --model gemma4:e4b --max-tokens 8192` | exit 0; 12/12 valid; 6/6 pairs |

**Failures and unresolved uncertainty.**

- **No developmental organism has been found**, and the size search is now closed by rule.
  Two of at most three candidates are consumed (12B void, e4b too strong).
- **The endpoint, not the model, is now the suspect.** Difficulty must come from somewhere
  other than model size: higher levels, or an endpoint whose state is harder to hold.
- **Zero AST or HML model calls have still been made.** Nothing about representations is
  contaminated, and the PILOT seed band is untouched.

**Effect on the project.** The developmental-organism question is answered negatively for
this endpoint at this difficulty, cheaply (12 calls, ~3 minutes) and validly. The instrument
is now trustworthy: preflight-tested, incrementally persisted, and it produced a clean run
first time.

**Next intended step.** Do not run the representation pilot at L3. Re-screen SE-only at a
higher level (L5, then L7 if needed) to find a difficulty where `gemma4:e4b` lands in
30–70%; endpoint A is the other candidate for headroom. Reported as
`HML_NO_SUITABLE_DEVELOPMENT_MODEL`.

## 2026-08-08 — developmental ladder: gemma3:4b lands at 3/6 and is FROZEN

**Branch.** `feature/hml-reasoning-kernel-v2` · **Stage.** Signal pivot, developmental model
selection — resolved. **Starting SHA.** `2ce2d29`.

**Objective.** Run the SE-only micro-screen down a fixed model ladder and stop at the first
candidate whose Endpoint-B pair BOTH-CORRECT score falls in 2–4/6.

**Protocol.** One frozen 6-pair / 12-call micro-screen reused unchanged for every candidate:
`pair_offset=6` (unseen by `gemma4:e4b`, which used offset 4), L3, structured English only,
temperature 0, `max_tokens` 8192, one stateless call per item. Tasks, prompts and difficulty
were identical across models — only the model changed.

**Ladder result.**

| # | model | params | pair BOTH-CORRECT | single-item | trunc | mean ctok | mean latency | verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | `gemma4:e2b` | 5.1B | **6/6 = 1.00** | 12/12 = 1.00 | 0 | 995.8 | 7.6 s | too strong → next |
| 2 | `gemma3:4b` | 4.3B | **3/6 = 0.50** | 7/12 = 0.583 | 0 | 180.0 | 3.8 s | **TARGET — SELECTED** |
| 3 | `llama3.2:3b` | 3.2B | — | — | — | — | — | **NOT RUN** (ladder stopped on the rule) |

Both screens were clean: zero truncations, zero invalid responses, zero errors, no pairs
dropped. Neither number is censored.

**`gemma3:4b` per-pair profile — a genuinely mixed organism, which is the point.**

| contrast | pair | result |
|---|---|---|
| OPERAND_ORDER | 300011, 300012 | both-correct ×2 |
| QUANTIFIER_ORDER | 300011 | both-correct |
| QUANTIFIER_ORDER | 300010 | one member wrong |
| IMPLICATION_DIRECTION | 300028, 300032 | both members wrong ×2 |

Perfect on algebra, half on quantifier order, nothing on implication direction. Its failures
are substantive rather than procedural: **12/12 responses were valid and correctly
formatted**, and the logic misses are the classic error of answering TRUE/FALSE where the
constraints leave the query UNDETERMINED. So this is a model that follows instructions and
reasons imperfectly — competent but weak, which is exactly the developmental organism the
protocol asks for, and not a model to be rejected for non-compliance.

**Decision by the pre-registered rule (2–4/6 ⇒ target found): STOP and FREEZE.**
`llama3.2:3b` was deliberately not run.

**Frozen** in `evaluation/arena/results/FREEZE_gemma3-4b.json`: model name and digest
(`a2af6cc3eb7fa8be…`, 4.3B, Q4_K_M), runtime (temperature 0, `max_tokens` 8192, one
stateless call per item), the system prompt and instruction block with their SHA-256 hashes,
the endpoint implementation and its scoring rule, the selection result, and the generator and
scorer versions. The file lists explicitly what may no longer change.

**A caveat recorded rather than buried: `gemma3:4b` is a different family** from the gemma4
candidates. That reintroduces the architecture/pretraining confound the original directive
wanted avoided. It is acceptable here because the pilot compares SE, AST and HML **within
this one frozen model**, so family never enters the contrast — but it does mean this
organism's results cannot be pooled with, or compared against, the gemma4 screens.

**Tests and verification actually executed.**

| check | exact command | actual result |
|---|---|---|
| e2b screen | `run_screen micro --model gemma4:e2b --pair-offset 6 --max-tokens 8192` | exit 0; 12/12 valid; 6/6 pairs |
| gemma3:4b screen | `run_screen micro --model gemma3:4b --pair-offset 6 --max-tokens 8192` | exit 0; 12/12 valid; 3/6 pairs |

No other engineering was performed and no other tests were re-run: nothing outside the
results directory and the freeze record changed.

**Failures and unresolved uncertainty.**

- **Zero AST or HML model calls have still been made.** The PILOT band (500 000+) is
  untouched, and DEV_SELECTION offsets 0, 4 and 6 are now burned.
- **Endpoint B at L3 is saturated for every gemma4 candidate tried** (e4b and e2b both 6/6).
  Headroom exists for `gemma3:4b` specifically, not for the endpoint in general.
- **N=6 pairs.** The 0.50 is a selection signal, not an estimate. The rule anticipated this:
  the earlier directive continues a target-band candidate to 12 pairs before freezing the
  number, and that continuation has not been run.

**Effect on the project.** A developmental organism exists for the first time in this
programme. The blocking question — whether any locally runnable model sits in the headroom
band on this endpoint — is answered yes.

**Next intended step.** The acquisition sanity check (6 literal state-recovery items per arm,
ACQUISITION band, ≥5/6 required for AST and for HML), then the first Endpoint-B
representation pilot on fresh PILOT seeds. Neither may run before this freeze is in git.

## 2026-08-08 — llama3.2:3b completes the ladder at 0/6; gemma3:4b is bracketed and stands

**Branch.** `feature/hml-reasoning-kernel-v2` · **Stage.** Signal pivot, developmental
selection — confirmatory. **Starting SHA.** `963c097`.

**Objective.** Run the third ladder candidate, at the user's request, on the identical
frozen micro-screen. The rule had stopped the ladder at `gemma3:4b`; this run is
confirmatory and did **not** re-open the freeze.

**Result.** Same 6 pairs (offset 6), same L3, SE only, temperature 0, `max_tokens` 8192.

| model | params | pair BOTH-CORRECT | single-item | trunc | invalid | mean ctok | mean latency |
|---|---|---|---|---|---|---|---|
| `gemma4:e4b` | 8.0B | 6/6 = 1.00 | 12/12 = 1.00 | 0 | 0 | 1004 | 15.4 s |
| `gemma4:e2b` | 5.1B | 6/6 = 1.00 | 12/12 = 1.00 | 0 | 0 | 996 | 7.6 s |
| **`gemma3:4b`** | 4.3B | **3/6 = 0.50** | 7/12 = 0.583 | 0 | 0 | 180 | 3.8 s |
| `llama3.2:3b` | 3.2B | **0/6 = 0.00** | 4/12 = 0.333 | 0 | 0 | 108 | 0.8 s |

`llama3.2:3b` falls in the 0–1/6 band: too weak. No pair was both-correct.

**It also failed instruction compliance, which is the disqualifying condition.** Two of
twelve responses contained **no `FINAL:` line at all** (`B_log_L3_300032` and
`B_log_L3_300032_flip9`). The scorer marked both wrong, which is correct protocol —
unparseable is wrong, never retried — but the distinction matters for diagnosis. On
`B_log_L3_300032` the model's prose actually reached the right conclusion ("the truth of P5
is dependent on other facts that do not directly relate to P5", i.e. UNDETERMINED) and then
simply never emitted the required line. So **4/12 understates its reasoning**, and the
honest reading is: too weak *and* unable to hold the answer format. The earlier protocol
names this case explicitly — "if it cannot reliably follow the instructions, reject it as an
experimental organism". Rejected.

**Effect on the selection: none, and that is the useful part.** The ladder now brackets the
frozen organism on both sides — 6/6 above it (`e2b`, `e4b`), 0/6 below it (`llama3.2:3b`),
`gemma3:4b` alone in the 2–4/6 target band, with 12/12 valid responses. The choice was
made by rule on the first candidate to land in band; this run shows it was not a knife-edge
call between neighbours.

**`gemma3:4b` remains frozen. `FREEZE_gemma3-4b.json` is unchanged.**

**Tests and verification actually executed.**

| check | exact command | actual result |
|---|---|---|
| llama screen | `run_screen micro --model llama3.2:3b --pair-offset 6 --max-tokens 8192` | exit 0; 12/12 valid; **0/6** pairs; 2 responses with no `FINAL:` line |

No other engineering performed; nothing outside the results directory changed.

**Failures and unresolved uncertainty.**

- **Zero AST or HML model calls have still been made.** PILOT band untouched.
- N=6 pairs throughout. These are selection signals, not estimates.
- The 0/6 conflates weakness with format non-compliance; the two were separated by hand
  above rather than by the scorer, which by design does not distinguish them.

**Next intended step.** Unchanged: acquisition sanity check on ACQUISITION seeds (≥5/6 for
AST and for HML), then the first Endpoint-B representation pilot on fresh PILOT seeds.

## 2026-08-08 — model CONFIRMED at 8/12; semantic audit passes; ACQUISITION INSTRUMENT INVALID

**Branch.** `feature/hml-reasoning-kernel-v2` · **Stage.** Signal pivot. **Starting SHA.**
`ae2defd`. **STOPPED before the pilot.**

**Correction to the incoming directive.** It recorded `llama3.2:3b` as "UNTESTED, not
failed". It was in fact tested at the user's request in the previous turn, on the identical
frozen set: **0/6 pairs, 4/12 items, with two responses containing no `FINAL:` line**.
Committed at `ae2defd`. It is tested and rejected, and it brackets `gemma3:4b` from below.

### 1. Model confirmation — PASSED, at the top edge

Six additional completely fresh DEV pairs (`pair_offset=8`; offsets 0/4/6 already burned),
same frozen prompt, endpoint, scoring, temperature 0, `max_tokens` 8192, isolated contexts.
Zero overlap with all 48 previously burned items, verified before the run.

| set | pairs both-correct | items |
|---|---|---|
| offset 6 (earlier) | 3/6 | 7/12 |
| offset 8 (new) | 5/6 | 11/12 |
| **TOTAL** | **8/12 = 0.667** | **18/24 = 0.75** |

0 truncations, 0 invalid, mean 178.5 completion tokens, 2.66 s per call.

**Inside the 4–8 target band, so a FINAL freeze was created** — but three caveats are
recorded in it rather than smoothed over:

1. **8/12 sits exactly on the upper boundary** and outside the preferred 5–7 band.
2. **The two halves disagree sharply** (3/6 then 5/6). At six pairs per half the point
   estimate is unstable; 0.667 should be read as a band, not a number.
3. **`OPERAND_ORDER` is 4/4 — saturated.** All discriminating power comes from
   `QUANTIFIER_ORDER` (2/4) and `IMPLICATION_DIRECTION` (2/4). Since the pilot's contrast
   composition is frozen at 2/2/2, **one third of pilot pairs are expected to be
   non-discriminating**. The composition was deliberately *not* changed: altering task
   semantics after model selection would invalidate the selection.

`evaluation/arena/results/FREEZE_FINAL_gemma3-4b.json` supersedes the provisional freeze,
which is preserved as historical rather than rewritten.

### 2. Semantic audit — PASSED, no production change needed

`tests/arena/test_semantic_audit.py`, **62 checks, all passing**, read-only and test-only.
The seven judgment classes are kept separate rather than collapsed into one `VALID` flag:
PARSES and TYPECHECKS are checked independently (a file can parse and still fail
resolution); `HAS_DEFINED_DENOTATION` holds vacuously because the generator emits no
division; `IS_SEMANTICALLY_EQUIVALENT` is checked property-by-property for exactly what the
pilot depends on — entities and stable identities, types, free vs bound variables, binder
order and scope, assumptions with labels, implication direction, goal/query; the oracle
answer is verified to be *literally shared* across arms while the three prompts differ.
`EXECUTES` and `IS_PROVEN` are recorded **not-applicable with an assertion** that no pilot
item contains `derive` or `proved`, rather than silently skipped.

A negative control was added: swapping binder order must be *observable* in every arm. If it
were not, the headline endpoint would measure nothing.

**No missing invariant was found, so no production code was touched and no model-visible
prompt, difficulty, scoring rule or task semantic was changed.** The 1800/1800 round-trip
result is re-asserted, not replaced. `docs/semantics/HML_SEMANTIC_CONSTITUTION_V1.md`
records denotational, operational and proof/axiomatic meaning plus the deferred backlog.

### 3. Acquisition — **THE INSTRUMENT IS INVALID. No conclusion about HML.**

Raw gate result: SE 2/6, **AST 0/6, HML 2/6** — both structured arms below the ≥5/6 hurdle.
**That reading is wrong, and reporting it as an HML acquisition failure would have been a
serious false conclusion.**

**Six of eighteen responses contained no `FINAL:` line at all, and three of those held the
correct answer**, discarded by the formatting rule:

| arm | item | raw response | truth |
|---|---|---|---|
| AST | BINDER_ORDER | `exists` | **correct**, scored wrong |
| AST | GOAL_TARGET | `P3` | **correct**, scored wrong |
| AST | SORT | `Proposition` | **correct**, scored wrong |
| SE | SORT | `Proposition` | **correct**, scored wrong |

Charitably recomputed, the arms are SE 3/6, **AST 3/6**, HML 2/6 — AST's headline 0/6 is
entirely an artefact. That recomputation is a *diagnosis*, not a result, and is not offered
as one.

**Root cause, and why it is instrument and not treatment.** On the Endpoint-B reasoning
items this model produced a `FINAL:` line every time — 24/24 valid across both dev screens.
The acquisition items ask for a single word, and on those the model frequently answers with
the bare word and omits the line. That is an interaction between the prompt shape and the
model, and it hits all three arms. **SE — the format this model demonstrably handles at
18/24 on real reasoning — also fails at 2/6.** A literal-recovery instrument that the
known-good control fails is measuring itself.

Two further observations, recorded but not conclusions: `FACT_COUNT` was answered 10 against
a true 11 in **all three arms** (a consistent off-by-one, non-discriminating), and
`RELATION_LOOKUP` was correct in SE but wrong in AST and HML (n=1; suggestive at most).

**Consequence: STOPPED before the pilot.** Zero pilot calls were made and the PILOT seed
band is untouched. The acquisition seeds are burned.

**Deliberately NOT done:** the instrument was not repaired and re-run. Having already seen
HML's score, silently fixing and re-running is exactly the contamination the protocol warns
against. The fix is proposed for authorisation instead.

**Tests and verification actually executed.**

| check | exact command | actual result |
|---|---|---|
| model confirmation | `run_screen micro --model gemma3:4b --pair-offset 8 --max-tokens 8192` | exit 0; 12/12 valid; 5/6 pairs |
| semantic audit | `pytest -q tests/arena/test_semantic_audit.py` | **62 passed** |
| arena suite | `pytest -q tests/arena` | **179 passed**, 0 failed |
| lint | `ruff check evaluation/arena tests/arena` | All checks passed |
| acquisition | `run_screen acq --model gemma3:4b --max-tokens 8192` | exit 0; **instrument invalid**, see above |

**Failures and unresolved uncertainty.**

- **No representation evidence exists.** HML has now been shown to a model for the first
  time, on six literal-recall items whose measurement is void.
- The confirmed 8/12 is at the band edge with unstable halves.
- One third of frozen pilot pairs are expected to be non-discriminating.

**Next intended step.** Repair the acquisition instrument — the minimal fix is to accept a
bare single-token answer when it lies in the declared answer space, applied identically to
all arms and to the scorer's `valid` accounting — then re-run acquisition on **fresh**
ACQUISITION seeds. This is a scorer change, not a treatment change, but it must be
authorised because the previous result has been seen. Reported as `HML_MEASUREMENT_INVALID`.

## 2026-08-08 — acquisition repaired and re-run: gate FAILS (AST 3/6, HML 4/6). Pilot NOT run.

**Branch.** `feature/hml-reasoning-kernel-v2` · **Starting SHA.** `fd9f418`. **STOPPED at
the acquisition gate for the second time. Zero pilot calls.**

### 1. Scoring repair — acquisition only, as authorised

`extract_bare` accepts a reply that **is** a declared answer: the whole reply, or its last
non-empty line, equal to a member of the answer space after decoration stripping. Applied
identically to SE, AST and HML. Prose that merely *contains* the word still fails, so "the
answer is TRUE" is rejected.

**The reasoning-pilot scorer is untouched** and still requires a declared `FINAL:` line;
`test_pilot_scorer_is_unchanged_by_the_repair` guards that. Relaxing it there would change
what a scored reasoning answer means — a treatment change, not an instrument repair.

12 new tests (8 positive, 5 negative) plus three guards: a wrong bare answer still scores
wrong, a `FINAL:` line always beats a bare match, and truncation stays unscored. Arena suite
**196 passed**, ruff clean.

The repair worked as intended: **5 bare answers were accepted** in the re-run that the old
rule would have discarded.

### 2. Pilot composition — decided and documented BEFORE any pilot call

`docs/evaluation/PILOT_COMPOSITION_DECISION.md`: 6 `QUANTIFIER_ORDER` + 6
`IMPLICATION_DIRECTION` + **0 `OPERAND_ORDER`**, calibrated from the **SE-only** control
(4/4 ceiling vs 2/4 and 2/4). Zero Endpoint-B AST or HML calls existed when this was
decided, which is what makes it calibration rather than treatment-informed selection. The
record states the cost: two distinctions instead of three, and operand order left untested
under AST and HML.

### 3. Acquisition re-run on fresh seeds (400101–400106) — **GATE FAILS**

| arm | score | invalid | trunc | mean ctok |
|---|---|---|---|---|
| SE | 4/6 | 0 | 0 | 24.7 |
| AST | **3/6** | 0 | 0 | 23.8 |
| HML | **4/6** | 0 | 0 | 42.3 |

| kind | SE | AST | HML |
|---|---|---|---|
| SORT | correct | correct | correct |
| FACT_CONTENT | correct | correct | correct |
| RELATION_LOOKUP | correct | correct | correct |
| **BINDER_ORDER** | correct | **WRONG** | correct |
| FACT_COUNT | WRONG | WRONG | WRONG |
| GOAL_TARGET | WRONG | WRONG | WRONG |

**Required AST ≥ 5/6 and HML ≥ 5/6. Both fail. The pilot was not run.**

### 4. Diagnosis — stated in both directions, because motivated reading is available here

**`GOAL_TARGET` is a broken item and the defect is mine.** It asks "which symbol is the
question above asking about?" — but `build_prompt` renders the *acquisition* question in
place of the world's query, so no question naming the target appears anywhere in the prompt.
The item is unanswerable by construction. All three arms answered `P3` with nothing to read.
Verified by printing the rendered prompt.

**`FACT_COUNT` is a legitimate item that all three arms fail identically** — every arm
returned the byte-identical `'10\nFINAL: 10'` against a true count of 11. The facts are
enumerated in all three renderings, so this is a counting failure of the model, shared by
the control, and carries no representation signal.

**On the four items that test distinctions the pilot actually depends on — sort, fact
content, relation lookup, binder order — HML scored 4/4 and AST 3/4.** AST's single miss is
`BINDER_ORDER`, answering `exists` where the outermost binder is `forall`. That is a genuine
semantic-recovery failure, and binder order is the pilot's headline contrast. n=1, so it is
suggestive only, but it is the opposite of the expected direction for a "structure helps"
hypothesis and should not be discarded.

**Why this is still reported as a gate failure rather than talked past.** HML's only
non-broken miss is a counting task the control also fails, and it recovered every semantic
property the pilot needs. It would be easy to argue the gate "really" passed. I am not
making that argument: the pre-registered bar is 5/6, HML scored 4/6, and I have already had
one instrument repair authorised. Repairing again until the gate clears is precisely the
pattern that makes a result unfalsifiable. The verdict stands as measured.

### Tests and verification actually executed

| check | exact command | actual result |
|---|---|---|
| arena suite | `pytest -q tests/arena` | **196 passed**, 0 failed |
| lint | `ruff check evaluation/arena tests/arena` | All checks passed |
| fresh-seed disjointness | ad hoc | old vs new acquisition items: **0 overlap** |
| acquisition #2 | `run_screen acq --model gemma3:4b --acq-seed-base 400101 --max-tokens 8192` | exit 0; SE 4/6, AST 3/6, HML 4/6; 5 bare answers accepted |

Full 6k suite not re-run: nothing outside `evaluation/arena`, `tests/arena` and `docs`
changed.

### Failures and unresolved uncertainty

- **The acquisition gate has now failed twice**, the first time on a void instrument and the
  second on a real measurement with one broken item in it.
- **Still zero representation evidence.** No Endpoint-B AST or HML call has ever been made;
  the PILOT band is untouched. Two ACQUISITION seed sets are burned.
- AST's binder-order miss is n=1.

### Next intended step

User decision. Either (a) fix `GOAL_TARGET` so it is answerable — it must include the
world's own query in the prompt — and re-run acquisition a third time on fresh seeds, or
(b) accept the four-item semantic reading (HML 4/4, AST 3/4) and lower or restate the gate.
Both are protocol changes and neither should be taken unilaterally after two failures.
Reported as `HML_ACQUISITION_INSUFFICIENT`.

## 2026-08-08 — pre-run audit: 4 sub-agents, 2 retractions, 11 instrument defects; STOPPED before any call

**Branch.** `feature/hml-reasoning-kernel-v2` · **Starting SHA.** `2209151`.
**STOPPED before spending a single model call**, per the standing rule that an objective
defect requiring a model-visible change must be reported, not silently repaired.

### State verified before touching anything

Branch/LOCAL/REMOTE all `2209151`, tree clean, no git locks, no concurrent process, no file
modified in the preceding ten minutes. Model freeze intact: `gemma3:4b`, digest
`a2af6cc3eb7fa8be…`, **matching the live installed model exactly**; temp 0, `max_tokens`
8192, isolated stateless call per item. **0 Endpoint-B AST/HML treatment calls; 0 PILOT-band
calls.**

### Two retractions — both are corrections to things this project had written down

**RETRACTION 1 — `BINDER_ORDER` was unanswerable, so a recorded interpretation is void.**
`docs/PROJECT_STATUS.md` previously drew a conclusion from AST's `BINDER_ORDER` miss
("opposite to the direction a 'structure helps' hypothesis predicts"). The item was
**unanswerable in all three arms** by the same mechanism as `GOAL_TARGET`: `build_prompt`
evaluates `item.question or renderer.question(world)`, and every acquisition item sets a
question, so `World.query` was never rendered for any acquisition item in any arm. The
claim exists only inside `renderer.question`. The sole occurrence of `forall`/`exists` in
the entire prompt was the answer line. All three arms guessed; SE and HML were lucky. **HML's
"4/4 on pilot-relevant distinctions" was 3/3 plus a coin flip.** The conclusion is withdrawn.

**RETRACTION 2 — a miscount.** The acquisition-attempt-#1 entry says three discarded
replies held the correct answer. It was **four**: AST `P3`, AST `exists`, AST `Proposition`,
SE `Proposition`. Corrected here per the append-only rule, which permits correcting a
demonstrable factual error provided the correction is recorded in the entry itself. The
earlier entries are otherwise left exactly as written.

### Defects found and repaired (acquisition-only; 0 of 72 pilot prompts changed)

| # | defect | repair |
|---|---|---|
| D1 | `BINDER_ORDER` unanswerable (query shadowed) | `Item.show_query` + a separate `QUERY` block that cannot be shadowed |
| D2 | `GOAL_TARGET` unanswerable, same mechanism | same |
| D3 | `GOAL_TARGET` answer space leaked the answer — distractors were always `{P1,P2,P3}`, so a target of `P5`/`P6` was readable off the answer line with the state ignored (76/200 seeds, **including the next planned seed set**) | distractors now sampled |
| D4 | `SORT` unfailable — always drawn from a logic world, answer `Proposition` for every seed tested, distractor `Real` never present | family now a deterministic seed-derived draw; answer varies 26/34 over 60 bases |
| D6 | closed answer spaces handed AST/HML their native tokens while SE had to translate (`for every` → `forall`, `propositions` → `Proposition`) | arm-neutral gloss, identical bytes in all three prompts |
| D7 | `FACT_CONTENT` options could duplicate the answer's text (11/600 items) | distractors de-duplicated by canonical form |
| D9 | acquisition path had no `assert_band` — a mistyped `--acq-seed-base 500001` would silently burn PILOT seeds | `assert_band` added |
| S1 | `extract_bare` resolved a refusal by line position; `* forall\n* exists` scored **correct** because `normalise` strips a bullet | reject when more than one declared answer appears as a standalone line |
| S2 | strict `FINAL:` regex spanned newlines — `FINAL:\n\nforall\nexists` extracted `forall`, contradicting last-wins | restricted to horizontal whitespace. **Verified: 0 of 96 frozen extractions change**, so no historical score moves |
| S3 | `SCORER_VERSION` unchanged across a behaviour-changing edit; attempt #1 no longer re-scores to its committed numbers (12/18) | bumped to `arena-scorer-1.1.0`; attempt #1 is **not** rescored — it stays frozen as INVALID_INSTRUMENT evidence |
| G1 | stage/band guard keyed on a free-form `stage` string; `stage="ACQUISITION", band="PILOT"` ran | stage must exist and must match its band |
| G2 | the pilot's `assert_disjoint` compared against dev offsets 0–5 of two contrasts — excluding every offset actually spent — and could not fail anyway | now covers all burned offsets (0,4,6,8) and compares item ids as well as seeds |

`FACT_COUNT` was **kept unchanged**, as instructed. Recorded for the record: the true count
is 11 (verified three ways), the lure is zero-based labels (`f0…f10` → "10", which is exactly
what all three arms answered), and SE alone carries a 12th unlabelled line
("All of the following are true.") inside its FACTS block. That asymmetry cannot be repaired
without editing SE pilot prompts, so it stands and is documented. It makes SE harder, and SE
is not the gate.

### **THE BLOCKING FINDING — the HML arm leaks the contrast, and fixing it is model-visible**

`renderers/hml.py` emits `module Arena_{world_id}` as the first line of every HML state.
For minimal-contrast twins the world id **names the edit**:

```
module Arena_qnt_L3_500001   |   module Arena_qnt_L3_500001_swap
module Arena_log_L3_500000   |   module Arena_log_L3_500000_flip3
```

**12/12 pilot twins carry a `_swap`/`_flipN` suffix in HML. 0/12 in SE or AST** — neither
control renders `world_id` at all. Independently reproduced by the lead agent.

It does not reveal the answer (which twin is TRUE varies pair to pair). It does reveal, to
the treatment arm only: that the item is one of a minimal-contrast pair, which member it is,
the name of the operation applied, and — for `IMPLICATION_DIRECTION` — **the label index of
the edited assumption** (`_flip3` ↔ fact `f3`, holding in all 6 pairs). The surface loci at
which twins differ are SE 1, AST 1, **HML 2**.

The existing 1800/1800 parity evidence is blind to this by construction: `_assemble` blanks
`world_id` and `canonical_world` never reads it.

**This is exactly the "contaminated HML success" the protocol forbids.** Running the pilot
as-is would produce a number a reviewer could dismiss. Repairing it requires editing the HML
renderer, which is a **model-visible representation change**, and the standing instruction is
to STOP and explain rather than repair silently. So the run is halted here, before any call.

**Model selection is not affected** — it was structured-English only, and HML has never been
used to select anything.

### Tests and verification actually executed

| check | result |
|---|---|
| `pytest -q tests/arena` | **196 passed**, 0 failed |
| `ruff check evaluation/arena tests/arena` | All checks passed |
| pilot prompt SHAs before vs after all repairs | **72 compared, 0 changed** |
| parity over the real pilot set (sub-agent C) | 24 worlds, 72 round trips, **0 failures**; 1008 per-observable comparisons, 0 mismatches |
| adversarial parity sweep (sub-agent C) | 200 000 worlds / 600 000 round trips in the PILOT band, **0 failures** |
| contamination audit (sub-agent D) | **10/10 PASS**; 96/96 recorded prompts reproduce bit-for-bit; no result file ever modified (`git log --name-status` shows only `A`, never `M`) |
| scorer audit (sub-agent B) | 37 existing tests pass; over-acceptance and leak paths enumerated above |

### Failures and unresolved uncertainty

- **The pilot has not been run and must not be until the module-name question is decided.**
- `IMPLICATION_DIRECTION` flips are **always atom → atom** (3289/3289 sampled): the pilot
  never tests implication direction under nesting, which is where notation most plausibly
  misleads.
- `RELATION_LOOKUP` is a table lookup in SE/AST but an *evaluation* of a 13-disjunct formula
  in HML; the item's own "no reasoning is required" is false in that arm.
- Gate power: with two 2-way items, blind guessing scores ≈2.7/6 and clears 5/6 about 4% of
  the time per arm.
- `ACQUISITION_INSTRUMENT_FINAL` was deliberately **not** frozen: the instrument is not final
  while the HML renderer question is open, since acquisition renders HML too.

### Next intended step

User decision on the HML module name. Options: (a) drop the `module` line from the HML state
and put the module header only in `compilable()` (compiler-facing, never model-facing);
(b) render a content-free constant such as `module Arena`; (c) give SE and AST a matching
identifier so all three leak equally. (a) or (b) remove the asymmetry; (c) preserves it
symmetrically and costs tokens. Any of them changes HML pilot prompts, so the choice must be
authorised. Reported as `HML_MEASUREMENT_INVALID` — the instrument, not HML, is what failed.

---

## 2026-08-08 — include the tokenizer dependency in the dev conformance environment

**Branch.** `feature/hml-reasoning-kernel-v2` · **Stage.** CI dependency repair.

**Objective.** Make CI green again after the Representation Arena introduced a second
undeclared optional dependency.

**Root cause.** `evaluation/arena/budget.py::_encoder` does a bare `import tiktoken`. The
bare import is correct — a silently degraded token measurement would be worse than a loud
failure — but `pyproject.toml` already defined `tokenizers = ["tiktoken>=0.7"]` and `[dev]`
did not pull it in. CI installs exactly `pip install -e ".[dev]"`, so a clean runner never
received the package while the long-lived local venv had accumulated it. Exactly three
tests failed, all on `ModuleNotFoundError: No module named 'tiktoken'`:
`test_budget_reports_a_lopsided_corpus`, `test_measure_counts_something_for_every_arm`,
`test_pre_flight_gate_passes`.

This is the same class as the SymPy defect fixed earlier, recurring because the Arena added
a new extra without adding it to `[dev]`.

**Decision.** Add `"hamiltonian-lang[tokenizers]"` to `[dev]` rather than changing the
workflow to `pip install -e ".[dev,tokenizers]"`. The principle is that **`.[dev]` is THE
complete conformance environment**; putting extras in the workflow instead turns CI into
whack-a-mole in a file that is not the dependency manifest.

**Audit against recurrence.** Every third-party import across the repository was extracted
by AST walk and checked against the declared extras. Reachable by conformance
(`src/`, `tests/`, `evaluation/`): **`tiktoken` was the only genuine gap.** `score` is a
local sibling module (`evaluation/score.py`) and a false positive. `numpy`, `scipy`,
`transformers`, `yaml` and `hml_probe` appear only under `audit_rerun/` and `experiments/`,
which pytest never collects (`testpaths = ["tests"]`).

**Tests and verification actually executed.**

| check | result |
|---|---|
| clean clone + `pip install -e ".[dev]"` | **tiktoken 0.13.0**, sympy 1.14.0 |
| the three tests named in the CI log | **3 passed** |
| clean-room `./scripts/conformance.sh` | **CONFORMANCE: PASS** |

**Failures and unresolved uncertainty.**

- GitHub Actions had not reported when this entry was written. Not declared repaired until
  GitHub itself reports success.
- No Arena test was weakened or skipped, no `ImportError` was caught to degrade token
  measurement, and nothing was installed only into the local venv.

**Effect.** `.[dev]` is once again a complete conformance environment, and the audit
confirms no other undeclared dependency is reachable by the suite.

**Next intended step.** Confirm GitHub green, then the Representation Arena per the signal
pivot handoff.

## 2026-08-08 — HML module-name leak closed (option A); ACQUISITION_INSTRUMENT_FINAL frozen

**Branch.** `feature/hml-reasoning-kernel-v2` · **Starting SHA.** `df48457`.
Authorised repair of the blocking finding, then the instrument freeze. **Still zero
Endpoint-B AST/HML calls at the time of this commit.**

**The repair (option A).** `HmlRenderer.state` no longer emits a `module` header; it is
added in `compilable()` only, which is the compiler-facing path the model never sees. The
header carried `world_id`, and for a minimal-contrast twin that id names the edit —
`Arena_qnt_L3_500001` vs `..._swap`, `Arena_log_L3_500000` vs `..._flip3`, the latter also
giving the label index of the edited assumption. `decode_hml` now supplies a **constant**
`module Arena` before parsing; deriving it from the world would reintroduce the identifier.

**Measured effect, which is exactly what it should be:**

| quantity | result |
|---|---|
| SE pilot prompts changed | **0 / 24** |
| AST pilot prompts changed | **0 / 24** |
| HML pilot prompts changed | **24 / 24** |
| HML prompts still containing `world_id`, `_swap` or `_flipN` | **0 / 24** |
| parity over the pilot set after the change | 24 worlds, **0 failures** |
| HML still compiles | **24 / 24** |

Two regression tests were added so this cannot return: no arm may render `world_id`,
`_swap`, `_flipN` or `Arena_`; and twins must differ at **at most one surface locus in every
arm** — which is the property that actually failed before (HML differed at two).

**`ACQUISITION_INSTRUMENT_FINAL.json` frozen** before any call: seeds 400201–400206 (band
ACQUISITION, disjoint from both burned attempts), the six item kinds and their answer keys,
per-arm prompt hashes, file hashes for the six modules that determine an item, the scorer
version `arena-scorer-1.1.0`, the `allow_bare` rule, the model freeze reference, and the
5/6 threshold with `no_post_hoc_rescoring`, `no_item_deletion_after_results` and
`no_fourth_attempt` recorded as part of the freeze rather than as intentions.

The frozen keys are `SORT=Proposition`, `FACT_CONTENT=C`, `FACT_COUNT=11`,
`RELATION_LOOKUP=FALSE`, `BINDER_ORDER=exists`, `GOAL_TARGET=P5` — written down **before**
the run so no answer can be reinterpreted afterwards.

**Limitations carried into the run, recorded in the freeze itself:** `FACT_COUNT` unchanged
as instructed (lure is zero-based labels; SE alone carries a 12th unlabelled line, which
makes SE harder and SE is not the gate); `RELATION_LOOKUP` is a lookup in SE/AST but an
evaluation of a 13-disjunct formula in HML; blind guessing scores ≈2.7/6 and clears 5/6
about 4% of the time per arm.

**Verification.** `pytest -q tests/arena` → **201 passed**, 0 failed.
`ruff check evaluation/arena tests/arena` → All checks passed.

**Next.** Commit and push, confirm LOCAL == REMOTE and a clean tree, then spend the third
and final acquisition run on seeds 400201–400206.

## 2026-08-08 — FINAL acquisition: HML 5/6 PASSES, AST control 4/6 FAILS. Case B. Pilot NOT run.

**Branch.** `feature/hml-reasoning-kernel-v2` · **Starting SHA.** `4be6c74` (the frozen
instrument). **STOPPED at the predeclared Case B. Zero pilot calls. PILOT band untouched.**

### Result — the first valid acquisition measurement in this programme

Frozen instrument, seeds 400201–400206, `gemma3:4b` @ `a2af6cc3eb7fa8be…`, temp 0,
`max_tokens` 8192, isolated call per item.

| KIND | SE | AST | HML |
|---|---|---|---|
| SORT | correct | correct | correct |
| FACT_CONTENT | correct | correct | correct |
| RELATION_LOOKUP | correct | correct | correct |
| GOAL_TARGET | correct | correct | correct |
| **BINDER_ORDER** | correct | **WRONG** | correct |
| FACT_COUNT | WRONG | WRONG | WRONG |
| **total** | **5/6** | **4/6** | **5/6** |

0 invalid, 0 truncations, 0 errors in all 18 calls. Mean completion tokens SE 23.7 /
AST 25.0 / **HML 48.5**; latency 0.5 / 0.5 / 0.6 s.

**Gate: HML ≥ 5/6 → PASS. AST ≥ 5/6 → FAIL (4/6). This is predeclared Case B: stop, do not
run the pilot, report the AST control as insufficient.** No fourth attempt is permitted and
none was made. No answer was rescored, no item was deleted, the threshold was not moved.

### The repairs are vindicated by the data, not just by argument

`GOAL_TARGET` went from **wrong in all three arms** (attempt #2) to **correct in all three**
(attempt #3). That is the direct signature of the diagnosed defect: the item was unanswerable
because the world query was shadowed and never rendered, and rendering it in its own `QUERY`
block made it answerable in every arm at once. Nothing else about the item changed except
the sampled distractors.

`BINDER_ORDER` is now genuinely answerable — the claim is in the prompt — so this attempt's
result is a real observation where attempt #2's was a coin flip.

`FACT_COUNT` failed in all three arms with the byte-identical reply `10\nFINAL: 10`, exactly
as predicted from the zero-based-label lure (`f0…f10` → "10") recorded in the freeze before
the run. It was kept unchanged, as instructed.

### What this supports, and what it does not

**Supported:** on six literal state-recovery items with the world query visible,
`gemma3:4b` recovered 5/6 from HML and 5/6 from structured English, and 4/6 from the generic
AST. HML cleared the pre-registered readability bar; the AST control did not.

**Not supported — and the temptation here is obvious, so it is written down:**

- **This is not evidence that HML is a better reasoning representation.** It is a
  *readability* gate, deliberately requiring no reasoning. Zero Endpoint-B reasoning calls
  have been made in any arm.
- **"AST is harder to read than HML" is not established.** AST's deficit is a single item,
  n=1. The honest statement is that the control failed the gate, not that the control is
  worse.
- **HML's own miss is not HML-specific.** `FACT_COUNT` failed identically in every arm.
- HML used roughly twice the completion tokens of either control on these items (48.5 vs
  23.7/25.0).

### Why Case B blocks the pilot, in substance rather than by rule

The AST arm is the *control that makes the experiment interpretable*: without it, an HML
advantage cannot be separated from a generic benefit of structure. Its single failure is on
`BINDER_ORDER` — which is **half the frozen pilot composition** (6 of 12 pairs are
`QUANTIFIER_ORDER`). A control that may not reliably read binder order out of its own
notation would make an HML > AST result on quantifier-order pairs uninterpretable: the gap
could be reasoning, or it could be that the control could not see the distinction. Running
the pilot now would spend 72 calls on a number that could not be defended.

### Tests and verification actually executed

| check | exact command | actual result |
|---|---|---|
| arena suite | `pytest -q tests/arena` | **201 passed**, 0 failed |
| lint | `ruff check evaluation/arena tests/arena` | All checks passed |
| final acquisition | `run_screen acq --model gemma3:4b --acq-seed-base 400201 --max-tokens 8192` | exit 0; SE 5/6, AST 4/6, HML 5/6; 0 invalid, 0 truncations |

### Failures and unresolved uncertainty

- **The AST control has not cleared its readability gate**, and the protocol allows no
  further acquisition attempt.
- **Still zero representation evidence.** The PILOT band remains untouched; three
  ACQUISITION seed sets are now burned (400001–6, 400101–6, 400201–6).
- AST's deficit rests on one item.
- `FACT_COUNT`'s lure is now understood and, on this evidence, will fail in every arm on any
  future run of this instrument.

### Next intended step

User decision, since no fourth attempt is authorised and every option is a protocol change:
(a) accept the AST control as-is and run the pilot with its readability limitation recorded
as a stated caveat; (b) improve the AST arm's binder rendering — a model-visible change to a
control, which would require re-validating parity and re-freezing; or (c) treat the AST
control as unusable for `QUANTIFIER_ORDER` and re-scope the pilot to
`IMPLICATION_DIRECTION` only, which halves it. Reported as `HML_MEASUREMENT_INVALID`.

## 2026-08-08 — binder diagnostic: AST cannot read binder nesting. Pilot re-scoped to B1.

**Branch.** `feature/hml-reasoning-kernel-v2` · **Starting SHA.** `42d5bd8`.

### The diagnostic — control characterisation, explicitly not a fourth acquisition attempt

Own seed band (`DIAGNOSTIC`, 600 000+), so it cannot consume a gate or pilot seed. Eight
items, two from each of the four binder combinations, giving a key balanced exactly 4
`forall` / 4 `exists` — a model that always answers `forall` scores chance, not credit.
`exists → exists` never occurs in the generator's claim shapes, so claims were constructed
directly; legitimate because the answer is a property of surface text, with no entailment or
truth evaluation involved.

| arm | score | mean ctok | latency |
|---|---|---|---|
| SE | **8/8** | 6.0 | 0.3 s |
| **AST** | **6/8** | 6.8 | 0.3 s |
| HML | **8/8** | 6.5 | 0.3 s |

0 invalid, 0 truncations.

**6/8 falls between the two pre-declared bands (7–8 = noise, 3–5 = genuine). The count is
ambiguous; the pattern is not.**

| configuration | expected | AST answered | |
|---|---|---|---|
| `forall → exists` | forall | forall | ✅ |
| `forall → forall` | forall | forall | ✅ |
| `exists → exists` | exists | exists | ✅ |
| **`exists → forall`** | **exists** | **forall** | ❌ ×2 |
| **`exists → forall`** (the ACQ3 gate item) | **exists** | **forall** | ❌ |

Both diagnostic misses are the *same* configuration, and they reproduce the acquisition
failure exactly — that item was also `exists → forall`. Noise would scatter; this does not.

**AST's answer is predicted, on 5 of 5 configurations, by the heuristic "say `forall` if
`forall` appears anywhere, else `exists`".** That rule reads token presence and never reads
nesting. It happens to be right on three of the four configurations, which is precisely why
6/8 understates the problem: the arm is not 75% reliable at reading binder order, it is
~0% reliable and 75% lucky.

### Consequence — the pilot is re-scoped, not caveated

`QUANTIFIER_ORDER` pairs are exactly `{forall → exists, exists → forall}`. The AST control
would systematically fail one member of **every** such pair, for a *reading* reason. An
HML > AST gap on quantifier scope would then be uninterpretable: reasoning, or a control
that cannot see the distinction. Writing that up as a caveat afterwards would not fix it.

So the first pilot is **B1 = 12 × `IMPLICATION_DIRECTION`, 0 × `QUANTIFIER_ORDER`**.
Implication is `{"op":"implies","args":[A,B]}` — argument order, not nesting depth — and AST
read `implies` nodes correctly in `FACT_CONTENT` on both attempts. Quantifier scope becomes
**endpoint B2**, to be run after a `GENERIC_AST_V2` exists. This decomposes the endpoint by
semantic mechanism rather than demanding one benchmark validate quantifier scope and
implication simultaneously.

**This is still control-informed, not treatment-informed:** zero Endpoint-B AST or HML
reasoning calls have ever been made. The diagnostic measured *readability*, not reasoning.

### Pilot frozen before any call — `PILOT_MANIFEST_B1.json`

12 pairs, 24 items, 72 calls, arms SE/AST/HML, level L3, `gemma3:4b` @ `a2af6cc3eb7fa8be…`,
temp 0, `max_tokens` 8192, order seed 20260808. Records every pair id, seed, item id,
**answer**, and per-arm prompt hash. Scorer `arena-scorer-1.1.0`, pair BOTH-CORRECT,
**strict `FINAL:` required — `allow_bare` is not applied to the pilot.**

Pre-flight: every pair flips (12/12), disjoint from all burned DEV seeds, parity 24 worlds /
0 failures, HML compiles 24/24, answer distribution UNDETERMINED 12 / TRUE 7 / FALSE 5 —
every pair contains exactly one UNDETERMINED member, so a constant `UNDETERMINED` answer
scores 12/24 items but **0/12 pairs**.

### Verification

`pytest -q tests/arena` → 201 passed. `ruff check` → clean.
`run_screen binder --model gemma3:4b` → exit 0, 24 calls, 0 invalid, 0 truncations.

### Failures and unresolved uncertainty

- **`GENERIC_AST_V2` is not built.** Endpoint B2 (quantifier scope) is blocked until it is.
  The S-expression encoding is the more promising candidate — compact, generic, naturally
  nested — and would additionally separate "compact structure" from "structure at all".
- AST's deficit is now 3/3 on one configuration and 0/5 elsewhere; that is a strong pattern
  but still only three failures.
- `FACT_COUNT` remains in the acquisition instrument and is understood to be measuring
  counting rather than representation acquisition. Flagged for ACQUISITION_V2, not changed.

### Next

Run pilot B1. Report pair BOTH-CORRECT for SE / AST / HML, paired discordances, error
families, tokens and latency, with no significance claim at N=12.

## 2026-08-08 — FIRST REPRESENTATION RESULT. Pilot B1: SE 5/12, HML 1/12, AST 0/12.

**Branch.** `feature/hml-reasoning-kernel-v2` · **Starting SHA.** `a5811ff` (frozen
manifest). **The first Endpoint-B treatment calls ever made in this programme.**

### Result — structured English beats HML, and HML beats the generic AST

12 `IMPLICATION_DIRECTION` pairs × 2 twins × 3 arms = 72 calls. `gemma3:4b` @
`a2af6cc3eb7fa8be…`, temp 0, `max_tokens` 8192, fresh stateless context per call,
deterministically shuffled order. **0 truncations, 0 invalid, 0 errors.**

| arm | pairs BOTH-CORRECT | items | invalid | trunc | mean ptok | mean ctok | mean lat |
|---|---|---|---|---|---|---|---|
| **SE** | **5/12 = 0.417** | **15/24 = 0.625** | 0 | 0 | 347.4 | 158.3 | 1.8 s |
| **HML** | **1/12 = 0.083** | **10/24 = 0.417** | 0 | 0 | 285.3 | 177.9 | 2.2 s |
| **AST** | **0/12 = 0.000** | **6/24 = 0.250** | 0 | 0 | 505.2 | 121.4 | 1.4 s |

Ordering: **SE > HML > AST**, on both pairs and items.

### Paired item-level discordances (N = 24)

| comparison | B-correct / A-wrong | A-correct / B-wrong | Δ̂ |
|---|---|---|---|
| HML vs SE | 3 | 8 | **−0.208** |
| AST vs SE | 0 | 9 | **−0.375** |
| HML vs AST | 6 | 2 | **+0.167** |

Every discordance points the same way as the headline. **HML never beat SE on a pair, and
AST never beat SE on a single item.**

### Error families — deterministic oracle, no LLM judge

| arm | UND→TRUE | UND→FALSE | TRUE→UND | FALSE→UND | TRUE→FALSE | FALSE→TRUE |
|---|---|---|---|---|---|---|
| SE | 3 | 3 | 0 | 2 | 1 | 0 |
| HML | 5 | 5 | 2 | 1 | 0 | 1 |
| AST | 7 | 5 | 0 | 1 | 2 | 3 |

Every failure in every arm is `WRONG_SEMANTIC_CONCLUSION` — **zero** `INVALID_FORMAT`,
`TRUNCATED` or `MODEL_ERROR`. The dominant error everywhere is collapsing `UNDETERMINED`
into a definite verdict: SE 6/9 of its errors, HML 10/14, AST 12/18. The model does not
refuse to answer; it over-commits.

### Guessing baselines on this exact corpus

Always-`TRUE` 7/24 items, always-`FALSE` 5/24, always-`UNDETERMINED` 12/24 — and **0/12
pairs for all three**. Pair scoring did the job it was chosen for. Note **AST's 6/24 = 25%
is below the 33% a uniform 3-way guess would give**, and below every constant strategy.

### What this supports

> On 12 minimal-contrast implication-direction pairs at L3, with `gemma3:4b`, structured
> English scored 5/12 pairs and 15/24 items; HML scored 1/12 and 10/24; a generic JSON AST
> scored 0/12 and 6/24. No truncations or format failures in any arm.

Per the pre-declared interpretation table, **SE > HML ⇒ `HML_REPRESENTATION_HARM_SIGNAL`**.
On this endpoint, at this difficulty, with this model, **formalisation cost dominates**: the
prose baseline the project has been trying to beat since inception beat both formal
representations.

### What this does NOT support — stated because the temptation runs the other way

- **Not a refutation of HML.** One endpoint, one semantic mechanism, one difficulty level,
  one 4.3B model, N=12. **No significance is claimed and none is computable at this N.**
- **Not "structure fails".** HML > AST on both metrics (Δ̂ = +0.167), so the two structured
  arms are not interchangeable — whatever hurt AST hurt it more.
- **Not a quantifier-scope result.** B2 was deliberately excluded because the AST control
  cannot read binder nesting. This says nothing about the mechanism HML was designed for.
- **Not a length effect in HML's favour or against it.** HML had the *shortest* prompts
  (285 mean tokens vs SE 347, AST 505) and still lost to SE. The AST arm is 1.8× SE, so its
  last place is confounded with length; HML's is not.
- **The acquisition gate does not explain HML's result.** HML scored 5/6 there and 8/8 on
  the binder diagnostic — it can read its own notation. This is a reasoning result, not a
  readability one. That distinction is exactly why the gate was run first.

### Verification

`pytest -q tests/arena` → 201 passed. `ruff check` → clean.
`run_screen pilot --model gemma3:4b --max-tokens 8192` → exit 0, 72 calls, 0 truncations.
Every prompt hash matches `PILOT_MANIFEST_B1.json`, frozen before the first call.

### Failures and unresolved uncertainty

- **N=12 pairs.** SE 5/12 vs HML 1/12 is four pairs. The direction is consistent across
  every discordance measure, but the magnitude is not estimable here.
- **`GENERIC_AST_V2` is still not built**, so the AST arm's 0/12 conflates encoding cost
  with a 1.8× length penalty and cannot be cleanly attributed.
- Endpoint B2 (quantifier scope) remains unrun and is where HML's design claim actually
  lives.

### Next intended step

Preserve this result before touching HML. The pre-declared rule is not to redesign after one
pilot. The informative follow-ups, in order of value: (1) `GENERIC_AST_V2` — an S-expression
control would separate "compact structure" from "structure at all" and give AST a fair
showing; (2) endpoint B2 on quantifier scope once that control exists; (3) endpoint A
(next-action), which tests `S_t → a_t → S_{t+1}` and is the mechanism HML's reasoning spine
was actually built for.

## 2026-08-08 — Endpoint A instrument: built by reuse, audited adversarially, frozen. No calls yet.

**Branch.** `feature/hml-reasoning-kernel-v2` · **Starting SHA.** `c0e7520`.
**Stage 0 complete: instrument frozen, zero model calls spent.**

**Hypothesis.** `P(correct a_t | S_t, G, HML)` vs `P(correct a_t | S_t, G, SE)` — does
representing the state in HML make the correct *next action* easier to select? This is a
different question from B1, which tested representation → final semantic answer.

**Built by reuse, not by rebuilding.** `evaluation/arena/endpoints/next_action.py` already
existed: four candidate next results, distractors in four named roles
(`not_yet_reachable`, `wrong_arithmetic`, `already_established`, plus the correct one), and
a per-option oracle (`_assert_unique_*`) that *proves* exactly one option passes before an
item is emitted. Writing a second generator would have duplicated audited machinery. Added
only: an `ENDPOINT_A` seed band (700 000+), a `nexta` stage, item balancing, and the audit.

**Action-space framing, stated plainly.** The "action" is *which fact to derive next* —
four candidate conclusions — not a free-form transformation vocabulary
(`substitute`/`case-split`/…). That is the operational content of `S_t --a_t--> S_{t+1}` in
the arena's own kernel terms, and it is what the existing oracle can verify deterministically.
Inventing an action vocabulary would have meant building new mathematics infrastructure to
adjudicate "usefulness", which the mission excludes.

**Arms: SE and HML only.** The AST control is omitted because the binder diagnostic showed
it cannot read nesting; Endpoint A is not where that gets settled, and including it would
spend calls on a known deficit.

**A real defect found and fixed before freezing: answer-position bias.** The per-item
shuffle is uniform in expectation but lumpy at N=12 — it produced **A 2 / B 4 / C 1 / D 5**,
which lets answer position carry information and lets a positional prior beat chance. Items
are now rotated so the key lands on a cyclically assigned letter: **A 3 / B 3 / C 3 / D 3**,
with the key still provably on the `role="correct"` option. This changes which letter the
correct option wears, never the options or the semantics.

**Adversarial audit — 24 checks, all passing** (`tests/arena/test_endpoint_a_audit.py`).
Written to falsify fairness, covering every class this programme has already been bitten by:

- semantic parity — both arms decode to the same `canonical_world`;
- action parity — same four options, same order, same letters, pairwise distinct **in every
  arm** (the duplicate-option trap from `FACT_CONTENT`);
- answer parity — one key, on the `correct` role;
- leakage — no `world_id`, seed, item id, `_swap`/`_flip`, `Arena_`, or role name in any
  prompt. *The bare word "correct" is deliberately allowed*: it occurs in the shared
  question, byte-identical in both arms, so it is task wording, not a cue. The first audit
  run flagged it and the audit was corrected, not the prompt;
- position balance, plus an explicit "constant letter cannot beat chance" test;
- **surface heuristics** — longest-option, shortest-option, largest-number, smallest-number,
  prompt-length-tracks-key, and "pick the option naming a just-established variable" all
  fail to beat chance;
- counterfactual sensitivity — the key provably depends on the established prefix;
- HML validity — every state compiles under the real compiler;
- determinism, and seed disjointness from **all five** previously burned bands.

**Frozen** in `ENDPOINT_A_MANIFEST.json` before any call: item ids, seeds, families,
**correct indices**, per-option roles, per-arm prompt hashes, model digest, runtime, scorer
version, and `no_post_hoc_rescoring` / `no_item_deletion_after_results` / staged-burn rules.
Smoke seeds (790 001+) are recorded as `SMOKE_EXCLUDED_FROM_RESULTS` and are disjoint from
the pilot set (700 001+).

**Verification.** `pytest -q tests/arena` → 225 passed. `ruff check` → clean.
Live model digest re-checked against the freeze: `a2af6cc3eb7fa8be…`, match.

**Next.** Commit and push, then Stage 1 smoke (4 items × 2 arms = 8 calls, excluded from
results), then Stage 2 micro-pilot (12 items × 2 arms = 24 calls).

## 2026-08-08 — Endpoint A: the N=12 signal did NOT replicate. Pooled 30 items, CASE B.

**Branch.** `feature/hml-reasoning-kernel-v2` · **Starting SHA.** `00e4bef`.
Calls spent: 8 smoke (excluded) + 24 micro + 36 expansion = **68**.

### Result

| stage | items | SE | HML | Δ̂ |
|---|---|---|---|---|
| Stage 2 micro-pilot | 12 | **3/12 = 0.250** | **9/12 = 0.750** | **+0.500** |
| Stage 3 expansion (independent) | 18 | **11/18 = 0.611** | **11/18 = 0.611** | **0.000** |
| **Pooled** | **30** | **14/30 = 0.467** | **20/30 = 0.667** | **+0.200** |

w = 10, l = 4, both = 10, neither = 6. 0 invalid, 0 truncations across all 60 scored calls.
By family (pooled): algebraic SE 7/15 vs HML 10/15; logic SE 7/15 vs HML 10/15.

### The finding is the non-replication, not the pooled number

The micro-pilot's Δ̂ = **+0.500** looked like a strong HML advantage. The independent
18-item half returned **exactly 11/18 in both arms — Δ̂ = 0.000**. The pooled +0.200 is
carried entirely by the first twelve items.

The specific worry flagged at the micro stage was that **SE's 3/12 was precisely chance for
a four-way choice**, which is what an arm looks like when it is failing for a reason other
than reasoning. The expansion answered that directly: the same SE renderer scored
**11/18 = 0.611** on fresh items. SE was not broken; it had a bad twelve. This is
small-sample variance, and reporting the micro-pilot alone would have been a false positive.

**Pre-declared rule: CASE B — representation advantage not demonstrated.** Not CASE C. The
pooled figure is directional, but the only clean replication attempt showed no difference,
so it does not warrant escalation. No agent build, no verifier loop, no training is
justified by this endpoint.

### One qualitative difference that survives, stated as a hypothesis not a result

Error roles, pooled (16 SE errors, 10 HML errors):

| role | SE | HML |
|---|---|---|
| `not_yet_reachable` (premature — needs an underived value) | 7 | 4 |
| `already_established` (no progress) | 4 | 6 |
| `wrong_arithmetic` (mathematically invalid) | 1 | **0** |
| `opposite_polarity` / `undetermined` (logic errors) | 4 | **0** |

**HML's errors fall entirely into the two precondition/no-progress roles.** It never chose a
mathematically invalid option and never made a logic-polarity error; SE did both five times
combined. That is a difference in the *kind* of mistake, not the rate, and at these counts it
is a hypothesis worth a future targeted test — not a claim.

Both classes HML does make (`not_yet_reachable`, `already_established`) are mechanically
detectable by a cheap verifier: one violates a precondition, the other adds nothing. That is
the relevant input to any later verifier-loop decision, and it is the same for both arms.

### Instrument integrity

The option lists are **byte-identical across arms** — same propositions, same order, same
letters — so no positional, role-position, or option-length artifact can produce an
SE/HML gap; only the state block differs. Pooled key balance A8/B8/C7/D7. Chosen-letter
distributions are unremarkable (SE C-heavy at 10/30, HML A/B-heavy), and identical option
ordering means that cannot be an arm confound. HML prompts were *shorter* (11 856 vs 13 026
prompt tokens), so no length advantage. 24 adversarial audit checks passed before any call.

### Verification

`run_screen nexta` ×3 → exit 0, 68 calls, 0 invalid, 0 truncations, 0 errors.
`pytest -q tests/arena` → 225 passed. `ruff check` → clean.

### Failures and unresolved uncertainty

- **N=30 total, and the two halves disagree.** No significance is claimed or computable.
- The pooled +0.200 should not be quoted without the split-half beside it.
- One model, one difficulty level, one action space ("which fact to derive next" — not
  free-form transformations).
- The B1 result (SE > HML on implication direction) and this one (no reliable difference on
  next-action) are consistent in one respect: **no endpoint has yet shown HML helping.**

### Next

Do not escalate on this endpoint. If it is revisited, the informative variant is the
qualitative one: whether HML genuinely suppresses invalid and polarity errors, tested with
items designed to elicit exactly those, rather than more of the same.

## 2026-08-08 — error-topology branch CLOSED offline; causal-diagnosis scout frozen

**SHA at start.** `b87736a`. **Zero model calls in this entry.**

**The proposed 68-call error-topology experiment was not run, on evidence.** An offline
check of the existing 30 Endpoint-A items showed the motivating signal is compatible with
chance: HML made only ~5 errors per family, and P(0 of a given subtype | 5 errors) = (2/3)^5
= **0.13**. SE's severe errors came from 8 errors per family. A model that makes fewer
errors makes fewer of every type; no change in error *composition* is demonstrated.

A second, independent defect: **error opportunity is confounded with family.** Algebraic
items offer `{premature, wrong_arithmetic, no_progress}`; logic items offer
`{polarity, undetermined, no_progress}`. Polarity errors are only *available* on logic
items, so "HML made 0 polarity errors" is partly "HML got more logic items right" (10/15 vs
7/15). The two are not separable in that corpus.

A power simulation (4000 trials) also showed that under a true null, a 30-item run shows
"HML safer" **50% of the time** — direction alone is a coin flip, which is exactly how the
Endpoint-A micro-pilot produced +0.500 from noise. Branch closed.

**Causal diagnosis instrument frozen instead** (`CAUSAL_DIAGNOSIS_MANIFEST.json`), five
matched conditions over identical fresh worlds, band 800 000+, 6 items × 5 conditions = 30
calls. Answers balanced 2 TRUE / 2 FALSE / 2 UNDETERMINED.

**Two leakage problems in the requested design, and what was done.**

- **`HML_EPI` as specified is a total answer leak.** `status(query)` + `status(neg_query)`
  jointly determine TRUE/FALSE/UNDETERMINED exactly, collapsing the task to a three-way
  lookup; it would win trivially and say nothing about representation. Implemented instead
  over **every declared atom except the query target** — still an explicit epistemic layer
  where HML currently leaves it implicit, but the query stays to be decided. Verified
  mechanically that the target never appears in the block.
- **`HML_VERIFY` is a near-total leak by construction**, which the brief accepts. It is
  implemented as asked but is readable **only as an upper bound and sanity check**: failure
  to approach ceiling would mean the model cannot apply a two-bit lookup; success shows the
  deficit is in *deriving* entailment rather than reading HML. It is not evidence about
  representation quality and is recorded as such in the manifest.

`HML_OBF` uses one frozen keyword map (`assume→zeta1`, `implies→zeta5`, …), preserving
labels, operators, nesting and line count; it does not compile by design, and the compile
invariant is waived for that condition only.

**Offline audit, all passing:** unique item ids; one key shared by all conditions; no
`world_id`, seed, `_swap`, `_flip` or answer in any prompt; `HML_EPI` omits the query
target; `HML_OBF` preserves line count with every keyword replaced; `HML_VERIFY` emits
structured signals not a class label; **`HML_BASIC` byte-identical to the frozen B1
treatment**; 6/6 compile.

**Next.** Commit, push, then spend 30 scout calls.

## 2026-08-08 — causal scout: NO condition rescues. CASE D. Frozen zero-shot HML branch closed.

**SHA at start.** `164d194`. **30 scout calls spent.** 0 truncations, 0 runtime errors.

| condition | score | vs HML_BASIC | mean ctok |
|---|---|---|---|
| SE | **5/6** | +1 | 101 |
| HML_BASIC | **4/6** | — | 266 |
| HML_EPI | **3/6** | **−1** | 136 |
| HML_VERIFY | **3/6** | **−1** | 144 |
| HML_OBF | **2/6** | **−2** | 136 |

**No intervention improved on `HML_BASIC`. Pre-declared CASE D: close the frozen zero-shot
HML branch.** Expansion is not triggered — the rule required ≥ +2/6 and a matching error
pattern; every condition moved the wrong way.

### Three sub-findings, each more informative than the headline

**1. `HML_OBF` collapsed into a degenerate constant.** It answered `UNDETERMINED` on **all
six items**. Its 2/6 is not partial competence — it is exactly the two items whose key
happens to be UNDETERMINED. Effective signal: zero. Replacing nine structural keywords with
synthetic tokens, while preserving labels, operators, nesting and line count, did not
degrade reasoning gracefully; it stopped the model engaging at all. Lexical familiarity is
load-bearing for *whether the model attempts the task*, not merely for accuracy. This probe
cannot isolate pretraining exposure and that claim is not made — but of the four hypotheses,
H2 is the only one with a striking positive signature here.

**2. `HML_VERIFY` failed a two-bit lookup — and this is about the model, not HML.** The
condition hands over `query_proof_found` and `neg_query_proof_found`, which jointly
determine the class; it should have been near-ceiling. It scored 3/6. On
`log_L3_800000` the verifier reported **both** signals false — meaning neither the query nor
its negation is provable, i.e. UNDETERMINED — and the model answered **TRUE** anyway.

That is the single most consequential observation in this scout: **deterministic semantic
feedback did not repair unsupported commitment, because the model did not act on it.** A
verifier loop built on this organism would not fix over-commitment. H4 is not supported as a
rescue.

Two `HML_VERIFY` responses were the bare word `TRUE` with no `FINAL:` line and were scored
wrong under the frozen strict rule. **Not rescored** — the manifest forbids post-hoc
rescoring. For transparency: of the 4 that parsed, 3 were correct; the lenient reading would
be 4/6, still far short of ceiling and leaving the conclusion unchanged.

**3. `HML_EPI` made over-commitment *worse*, not better.** The H3 mechanism cell —
UNDETERMINED → definite — went from 1/2 under `HML_BASIC` to **2/2** under `HML_EPI`.
Supplying oracle-derived ESTABLISHED / REFUTED / OPEN status for every non-query atom did not
reduce unsupported commitment; on this scout it accompanied more of it. H3 is not supported,
and is mildly contra-indicated.

### Interpretation

H1 (intrinsic harm to this model) remains consistent with everything: `HML_BASIC` sits below
SE and nothing lifts it. H3 and H4 are not supported. H2 has the one positive signature, but
in a form that argues for **matched adaptation** — the model needs learned exposure — rather
than for any prompt-level fix.

**At N=6 none of this is statistics.** It is mechanism triage, and its value is in what it
rules *out*: three candidate cheap rescues were tested and none works.

### Verification

`run_screen causal --model gemma3:4b --n-items 6` → exit 0, 30 calls, 0 truncations,
0 errors, 0 invalid. Every prompt hash matches `CAUSAL_DIAGNOSIS_MANIFEST.json`, frozen at
`164d194` before the first call.

### Cumulative position

- B1 implication direction: **SE > HML > AST** — HML negative.
- Endpoint A next-action: micro +0.500, replication **0.000** — null.
- Error topology: closed offline, premise within chance.
- Causal scout: **no rescue among epistemic, familiarity, or verifier interventions**.

Four measurements, none showing frozen zero-shot HML helping this model.

### Next

Do not spend more calls on frozen zero-shot HML prompting. The only branch this evidence
supports is a **matched learning-curve experiment** — same base model, SE-LoRA vs HML-LoRA,
1k → 5k → 10k examples — which tests H2 directly. That is a training experiment and is
explicitly out of scope for this session; it should not begin without a separate decision.

## 2026-08-08 — GENERIC_AST_V2 built; Endpoint B2 (quantifier scope) frozen

**SHA at start.** `6921397`. **0 model calls in this entry.**

**AST-v1 is preserved and excluded, not replaced.** All of its code and results stay
untouched. It is not an arm in B2 because the binder diagnostic showed it cannot read
nesting — its answers were predicted on 5/5 configurations by "say `forall` if `forall`
appears anywhere" — so including it would measure the control's defect rather than the
representations.

**`AST_V2` — compact generic S-expression.** `forall(x, D, exists(y, D, R(x, y)))`.
Nesting is carried by parenthesis depth, the most conventional way structure is written in
Lisps, CAS systems and textbook logic. It borrows **nothing** from HML: no `assume`/`goal`,
no `var`/`Proposition`, no module, no epistemic status, no obligations — asserted by test.
A full decoder was written so it is held to the same round-trip standard as every other arm.

**The length confound is not merely removed, it is reversed** — which is the conservative
direction for a test of "does HML beat structure":

| arm | mean prompt tokens on the B2 set |
|---|---|
| **AST_V2** | **190.9** |
| SE | 229.2 |
| AST-v1 | 248.6 |
| HML | 295.4 |

AST-v1 ran 1.8× SE in B1, so its last place there was confounded with length. AST_V2 is now
the *shortest* arm, so any HML win over it cannot be explained by HML being terser.

**Audit — 16 checks, all passing** (`tests/arena/test_b2_audit.py`), plus parity re-run
across all four arms: **150 worlds, 0 failures**, and 16/16 on the B2 set itself. Covered:
semantic parity; every pair flips and is minimal; the binder swap is observable in **every**
arm; binder nesting survives round trip in every arm; **AST_V2 distinguishes the two orders
by arrangement while carrying an identical token multiset** — precisely the property AST-v1
lacked; no `world_id`/seed/`_swap`/`_flip`/`QUANTIFIER_ORDER` leakage; balanced 8 TRUE /
8 FALSE with no constant-answer pair; deterministic rendering; HML compiles 16/16; fresh
band disjoint from all seven burned bands; AST_V2 no longer than SE or HML; and no HML
construct present in the control.

**Frozen** in `ENDPOINT_B2_MANIFEST.json`: 8 pairs / 16 items / 3 arms = **48 scientific
calls**, plus a 1-pair smoke (6 calls, excluded). 54 total, inside the 60 ceiling. Records
every pair id, item id, **answer**, and per-arm prompt hash, with `no_post_hoc_rescoring`,
`no_post_hoc_deletion` and `ast_v1_results_immutable`.

**One conformance failure, caught by the repo's own guard and fixed — not overridden.**
The first commit attempt failed `CONFORMANCE` on
`test_an_optional_dependency_is_never_imported_unguarded[tiktoken]`: the new audit imported
`tiktoken` directly, but it is optional and absent from the `dev` extra, so a **clean clone
would have failed at collection rather than skipping**. `budget.py` imports it lazily for
exactly this reason. Fixed with `pytest.importorskip("tiktoken")`, which is the remedy the
guard itself prescribes. The override path was deliberately not used — the guard was right.

**Next.** Commit, push, smoke, then the 48-call pilot.

## 2026-08-08 — ENDPOINT B2 RESULT: structure beats prose on quantifier scope; HML does not beat a fair generic control

**SHA at start.** `508a699` (the frozen instrument). **48 scientific calls.**

| arm | pairs BOTH-CORRECT | items | invalid | trunc | mean ptok |
|---|---|---|---|---|---|
| **AST_V2** | **4/8 = 0.500** | **12/16 = 0.750** | 0 | 0 | **242.8** |
| **HML** | **3/8 = 0.375** | 10/16 = 0.625 | 0 | 0 | 345.9 |
| **SE** | **1/8 = 0.125** | 8/16 = 0.500 | 0 | 0 | 280.2 |

Paired item discordances (N=16): HML vs SE **+0.125** (5 gains, 3 losses); AST_V2 vs SE
**+0.250** (4 gains, **0 losses**); AST_V2 vs HML **+0.125** in the control's favour.

### Two findings, and they point in different directions

**1. Structure beats prose on quantifier scope — the first positive structural signal in
this programme.** Both structured arms beat SE, and AST_V2 never lost to SE on a single
item. SE scored **8/16 items = exactly chance** for a two-way question, and its errors are
perfectly symmetric (4 FALSE→TRUE, 4 TRUE→FALSE) — the signature of coin-flipping. On this
mechanism, prose conveys binder order to this model essentially not at all.

**2. HML does not beat a fair generic control — the control beat it.** `AST_V2` ≥ HML on
both pairs (4/8 vs 3/8) and items (12/16 vs 10/16). **This is the endpoint HML was
specifically designed for**, tested against a plain S-expression that borrows none of its
machinery, and HML did not come out ahead.

The length explanation is unavailable in either direction: AST_V2 is the **shortest** arm
(242.8 mean prompt tokens vs SE 280.2 and HML 345.9), so HML cannot claim a terseness
handicap, and its loss to AST_V2 is not a length artefact in HML's favour either.

**Interpretation: `HML_STRUCTURE_ONLY_SIGNAL`.** Structure is doing the work; nothing in
HML's specific ontology is. At 8 pairs this is descriptive — no significance is claimed —
but the direction is consistent with every prior measurement.

### Protocol deviation, recorded

**No separate smoke run was performed.** The `b2` stage is fixed at 8 pairs in the frozen
manifest, so the first invocation *was* the pilot; the intended 1-pair smoke had no separate
path. The smoke's purpose — validating runtime and scorer integration — was already
discharged by four prior runs on the same runner (Endpoint A ×3, causal scout) with zero
runtime failures, and this run produced 0 invalid, 0 truncations, 0 errors and 48/48
persisted records. The output file was renamed `B2_SMOKE` → `B2_PILOT` to match what it
actually is. No result was altered.

The run's stdout was piped through `head`, which closed the display early; the process still
wrote all 48 records and its summary, confirmed by both the JSON and the 48-line incremental
JSONL sidecar. Incremental persistence did its job.

### Verification

`pytest -q tests/arena` → 241 passed. `ruff` → clean. `CONFORMANCE: PASS` on the freeze
commit. Every prompt hash matches `ENDPOINT_B2_MANIFEST.json`, frozen before the first call.

### Cumulative position, five measurements

- B1 implication direction: SE > HML > AST-v1 — HML negative.
- Endpoint A next-action: null on independent replication.
- Error topology: closed offline, premise within chance.
- Causal scout: no rescue among epistemic, familiarity or verifier interventions.
- **B2 quantifier scope: structure > prose, but generic structure ≥ HML.**

**No measurement has yet shown an HML-specific advantage over a fair control.** The one
thing that now *is* supported is that a structured representation beats prose on binder
scope — which is an argument for structure generally, not for HML.

### Next

The single highest-value action is the **matched learning-curve experiment** (same base
model, SE-LoRA vs HML-LoRA vs S-expression-LoRA, 1k→5k→10k). Every zero-shot avenue is now
exhausted, and H2 — familiarity — is the only hypothesis left standing, with the `HML_OBF`
collapse as its supporting signature. That is a training experiment and is out of scope here.

---

## 2026-08-09 — Gold-10 core repair: certificate boundary, certified underdetermination, quantifier core

**Branch:** `feature/hml-reasoning-kernel-v2` · **Base:** `22b4bb7` · **Stage:** HML core
semantics (not the arena) · **Model calls: 0. Training: 0. Arena calls: 0.**

### Objective

Close the two generic core-semantic gaps a forensic Gold-10 triage identified on the
separate corpus track, plus the one integration boundary, and **nothing else**. Explicitly
out of scope by instruction: probability laws, calculus rules, arithmetic rewriting,
function-evaluation rules, any Gold-10-specific recogniser, corpus changes, training,
further model experiments.

### What was verified before editing

Branch, HEAD `22b4bb7`, clean worktree, LOCAL == REMOTE. Critically:
`git diff --name-only 164d1946..22b4bb7 -- src/` is **empty** — the three commits since the
corpus pin are all arena/evaluation work — so Codex's triage describes exactly this core and
no later change conflicts with it. That removed one of the brief's stop conditions.

The triage's load-bearing claims were checked independently and all hold: `GoalStatus` had no
certified-underdetermination state; `RULES` had sixteen rules and none quantified;
`kernel._substitute` deliberately refuses to enter a `Quantifier`; there was no certificate
concept anywhere. One correction: the triage describes `reasoning/evidence.py` as the
"evidence/provenance boundary", which overstates it — it is a dependency *graph* with cycle
validation and has no notion of a certificate or a checker.

### Files and systems changed

New: `reasoning/binders.py`, `reasoning/certificates/{__init__,builtin}.py`,
`reasoning/adjudication.py`, `reasoning/side_conditions.py`,
`docs/hml_v2/GOLD10_CORE_SEMANTICS_SPEC.md`, two examples, five test files.
Changed: `ast/nodes.py`, `lexer/`, `parser/`, `semantics/`, `type_system/`,
`backends/{canonical,hml,base}.py`, `reasoning/{kernel,check}.py`, `__init__.py`,
`spec/ir.schema.json`, `tests/freeze/frozen_subset.py`, `DECISIONS.md` (D-047),
`docs/hml_v2/{GRAMMAR_CONTRACT,REASONING_MODEL,OBLIGATIONS}.md`.

### Decisions made, and why

**One boundary, not many rules.** A rule per capability grows the trusted computing base
once per mathematical fact anyone wants. `reasoning/certificates/` is a single gate with a
**static** registry: source may refer to a checker by name and may not supply one, because a
library able to register `def always_valid(...): return VALID` would end the TCB.

**`equivalence/symbolic.py` is NOT registered.** Its own docstring says `simplify(a-b) == 0`
certifies equality and validity is decided by `satisfiable(...)`; HML replays neither. It is
an untrusted oracle. Promoting it because the module says "certificate" is exactly the error
the brief names. **Consequence, accepted rather than worked around: Gold-10 G07's body
`n + 0 = n` stays library-level**, and the quantifier core is tested on generically-
established bodies instead — a ∀-elim/∀-intro round trip with no arithmetic in it.

**Underdetermination is a judgment, not a status.** Entailment is monotone, so Γ ⊭ P says
nothing about Γ ∪ {a₃}; a status word cannot record which Γ it was about. `Adjudication`
binds verdict, target hash, context hash and ordered premise hashes, and `GoalStatus` is its
projection. Two consequences fall out and are separately enforced: a non-entailment
certificate must cover **every** established claim in scope, and it is **not spendable after
the context changes**. Neither was spelled out in the incoming brief; both are soundness
requirements, not polish.

**The eigenvariable condition is stronger than the textbook rule, deliberately.** Read
literally it quantifies over the premise closure — which would leave a hole, because HML
discharges obligations against Γ via `RefinementEnv.entails`, not only through cited premise
edges, so a derivation can rest on an assumption it never names. Implemented instead: no
assumption in scope, including inside `scope` frames, may mention the variable freely. This
over-rejects; that is the safe direction.

**Binder construction is re-depthing, not wrapping.** Identity is locally nameless, so a
premise's module-level `n` (`sym:#0.0`) and a conclusion's bound `n` (`sym:#1.0`) are
different symbols. Wrapping would build a term the resolver never produces and the step would
be rejected for a reason unrelated to its validity. No second notion of identity was
introduced — the point is to let the existing `expr_identity` decide.

### Tests and verification actually executed

| check | command | result |
|---|---|---|
| conformance | `bash scripts/conformance.sh` | **CONFORMANCE: PASS**, exit 0, 8/8 stages |
| full suite | `.venv/bin/python -m pytest` | **6765 passed, 6 skipped, 7 xfailed, 7 xpassed, 0 failed** |
| new tests | five new files | 80 passed, 1 skipped |
| lint | `ruff check src tests` | All checks passed |
| types | `mypy src/hamiltonian_lang` | no issues in 95 source files |
| binder numbering | `abstract()` vs the resolver's parse | 5/5 shapes canonically identical |

Attacks executed and all repelled, each a test: unknown checker · checker reaching a
judgement it does not offer · checker that raises · checker that establishes something else
· checker reporting VALID naming nothing · claim-hash mismatch · **stale context** ·
premise-hash mismatch · certificate omitting a premise of Γ · witness violating a premise ·
duplicated witness · partial model · swapped witnesses · undeclared atom · numeric witness
value · unsupported fragment · `determines_neither` used as a premise · forged
`CheckedEvidence` · witness-specific ∀-intro (also inside a `scope`) · wrong-domain ∀-elim ·
capturing instantiation · body/conclusion mismatch · unimplemented side condition ·
universal forged from a finite sample.

### Failures and unresolved uncertainty

Three gates fired during the work and each was a real defect, not noise: `mypy` on the
structural binder rebuild; `spec/ir.schema.json` not knowing the two new statement kinds
(the same omission D-025 made and D-026 fixed); and the golden tripwire refusing two
unblessed examples. All three fixed and re-run green.

**Recorded honestly:** the brief asked for six atomic commits in a stated order. This landed
as fewer, because the AST, grammar and `check.py` substrate is shared by all three features
and splitting it would have produced intermediate commits that do not pass — worse than a
larger coherent one. The spec was still written first, as instructed.

**Open:** `REFUTED` has no adjudicating statement form. It did not before this change either;
it is named in the verdict vocabulary so the judgment is total over the four semantic
outcomes rather than shaped by which statements happen to exist.

**Grammar-contract drift found and reported, not repaired:** `GRAMMAR_CONTRACT.md` specifies
`obligation` and `discharge` statements that were never implemented, omits `scope` which was,
shows a `derive ... yields` form that differs from the implementation, and names a
`GoalStatus` value (`ASSERTED_UNCHECKED`) that is not in the AST. Corrected only where
D-047's own additions would otherwise read untruthfully; the rest goes to Codex.

### Effect on the overall project

The HML core can now express certified underdetermination and reason under a binder, and has
one auditable place for future mathematics to enter without touching the trusted kernel. The
TCB grew by the boundary, three small checkers, and one evaluator already in the tree — and
by no domain mathematics.

This is orthogonal to the arena programme's cumulative finding, which is unchanged: across
five measurements, no HML-specific advantage over a fair control has been demonstrated.
Nothing here was measured against a model, and nothing here claims otherwise.

### Next intended step

Hand the new SHA to Codex via `docs/agent_handoffs/CLAUDE_GOLD10_CORE_REPAIR.md` and **stop**.
Codex owns the corpus, repins `hml_core`, and reruns the *same* Gold-10. No Gold-100 until
that rerun shows the classifications are stable.

---

## 2026-08-09 — Codex handoff written; Gold-10 core repair closed out

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `5688aba` · **Stage:** handoff.
Documentation only; `git diff --stat 5688aba..HEAD -- src/` is empty.

### Objective

Give Codex everything needed to repin `hml_core` and rerun the same Gold-10, including the
two results it will not like.

### What was completed

`docs/agent_handoffs/CLAUDE_GOLD10_CORE_REPAIR.md`: SHAs, certificate architecture, the
three trusted checkers with their fragments and trust bases, the underdetermination and
quantifier contracts, existing capabilities reused, per-gap expected reclassification, API
changes, test counts, TCB, and five unresolved questions.

### The two findings the handoff leads with

1. `equivalence/symbolic.py` is **not** a trusted checker — raw SymPy flags, no HML replay.
2. Therefore **G07's body stays library-level** and Codex's rerun will still show GAP-0004's
   body open. The handoff says so explicitly and tells Codex to judge the quantifier core by
   `examples/logic/quantified_inference.hml` instead.

Reporting an expected non-improvement in the handoff is the point: a rerun that surprises
the corpus owner is worse than one that confirms a stated prediction.

### Verification

`git diff --stat 5688aba..HEAD -- src/` → empty, so pinning either commit gives identical
semantics. Conformance re-run by the pre-commit hook on both commits.

### Effect on the overall project

The core track's Gold-10 obligations are discharged. Ownership passes to Codex.

### Next intended step

**Stop.** Do not rerun Gold-10, do not touch the corpus, do not start Gold-100. Await the
rerun result.

---

## 2026-08-09 — Gold-10 library closeout: algebra, probability and calculus V0 without touching the kernel

**Branch:** `feature/hml-reasoning-kernel-v2` · **Base:** `76b9989` · **Stage:** library
layer · **Model calls: 0. Training: 0. Arena calls: 0.**

### Objective

Close the three remaining Gold-10 library capabilities. The explicit test was architectural,
not numeric: Codex's rerun reported `CoreGapRate = 0`, and this task was designed to find
out whether that diagnosis survives contact with real domain mathematics.

### What was verified before editing

Branch, HEAD `76b9989`, clean, LOCAL == REMOTE, and `git diff 5688aba..76b9989 -- src/`
empty — so Codex's rerun measured exactly this core.

Three facts about HML's probability ontology were checked **against the compiler** rather
than taken from the brief or from a proposal, and all three changed the design:

1. `probability(...)` requires an **`Event`**, not a `Bool`. HML-T482 rejects a proposition
   over fixed quantities because its probability is 0 or 1. Events come from `rv`
   declarations.
2. `probability(B | A)` is `event=B, given=[A]`. The conditioning event is `given[0]`.
3. `joint(...)` is the joint **law** of random variables, typed `Distribution[Product[...]]`
   — not event intersection. Intersection is `and` inside `probability(...)`.

### Decisions made, and why

**A theorem is data; an inference rule is code.** Libraries supply `LibraryTheorem` records
that elaborate through the *existing* certificate boundary. Nothing entered `kernel.RULES`,
and two tests pin that — one by enumeration of the whole rule set.

**No grammar change was needed.** `theorem := <id>` resolves against the theorem registry
using the precedent already set by `congruence(fn := exp)`, whose `fn` role resolves against
functions rather than values. Zero new keywords, zero new statement forms.

**Side conditions are ordinary obligations.** `P(A) > 0` and `x != 0` become
`ReasoningObligation`s discharged against Γ by the same code that discharges a
`divide_both_sides` obligation. An undischarged mandatory one means the certificate does not
validate — stricter than a derivation's CHECKED state, deliberately, because a certificate
is all-or-nothing and "provisionally certified" would let a conditional probability be used
at probability zero pending a repair that might never come.

**Calculus is a replay, not a table.** The checker differentiates the expression itself, so
a derivative from a CAS, a model or a guess is a claim rather than evidence. Normalisation
uses oriented algebra identities, each a named registered theorem, terminating because every
rewrite strictly shrinks the term. `sympy` is not importable on that path and a test asserts
it over the import graph.

**Exactly five algebra identities**, and the report §10 asked for: `add_zero` for G07;
`zero_mul`, `one_mul`, `zero_sub` required by the G10 quotient normalisation; `mul_one`
required by the product and power replays. Nothing added "while we were there". No e-graph.

**The assumed set is enumerable.** `libraries.axioms()` prints it; the registry refuses an
assumed theorem with no written justification. A certificate proves "this instantiation,
correctly typed, with side conditions discharged" — never the axiom.

### Tests and verification actually executed

| check | result |
|---|---|
| `bash scripts/conformance.sh` | **CONFORMANCE: PASS**, exit 0, 8/8 |
| `pytest` | **6981 passed, 6 skipped, 7 xfailed, 7 xpassed, 0 failed** (was 6765) |
| `pytest tests/libraries` | 65 passed |
| `pytest tests/reasoning` | passes unchanged |
| `ruff` / `mypy` | clean; 101 source files |
| kernel/AST/grammar diff | **empty** |

### Failures and unresolved uncertainty

**Two design bugs found by running the code, both real:**

1. The first comparison of a replayed derivative failed because `expr_identity` includes
   inferred types, and replay-constructed nodes carry none. Fixed by stripping types from
   both sides — a normalisation before the language's own identity, not a rival to it.
2. The second failed for a much better reason: `derivative(x*x, x : Real)` **binds** `x`, so
   the body's `x` is at depth 1 while the RHS's is the module-level `x` at depth 0. That is
   the binder machinery working correctly. Resolved by instantiating the replay's result at
   the free variable the claim uses — the standard reading of `d/dx f(x) = g(x)`, matching
   the existing idiom in `examples/analysis/derivative_and_integral.hml`. **This is the one
   judgement call a reasonable person could make differently**, and the handoff says so.

**One new core-adjacent gap, reported not patched:** `RefinementEnv.entails` destructures an
obligation as `<Ref> <op> <bound>` and returns None when the subject is not a declared
variable — so `probability(X > 0.0) > 0.0` stays UNKNOWN even when the module asserts it
verbatim. Worked around locally with exact canonical membership of Γ. Widening `entails`
belongs to the core track, and this mission was told to stop rather than change context
semantics silently.

**Scope note:** `reasoning/check.py` gained an obligation channel on the evidence path. It is
additive and strictly more conservative — it can only turn a would-be VALID into REJECTED —
but it is a change to a core file and the handoff states it plainly rather than burying it.

### Effect on the overall project

All three Gold-10 library capabilities exist, and the trusted kernel is byte-identical. The
architecture claim — domain mathematics grows without the trusted base growing — now has one
real test behind it rather than an argument.

Unchanged and unaffected: the arena programme's cumulative finding that no measurement has
shown an HML-specific advantage over a fair control. Nothing here was measured against a
model.

### Next intended step

Hand off and **stop**. Codex repins, reruns the same 23 transitions, and judges the rates
independently. No Gold-100 until Codex recommends it.

---

## 2026-08-09 — library handoff finalised; SHA to pin is 2af4998

**Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `2af4998` · Documentation only;
`git diff --stat 2af4998..HEAD -- src/` is empty.

### Objective

Fill the exact FINAL_SHA, test counts and repository state into the Codex handoff, so the
document can be acted on without consulting the commit log.

### What was completed

`docs/agent_handoffs/CLAUDE_GOLD10_LIBRARY_CLOSEOUT.md` finalised: pin `2af4998`, conformance
PASS 8/8, pytest 6981 passed / 0 failed, 65 library tests, clean worktree, remote equal.

### Verification

`git diff --stat 2af4998..HEAD -- src/` → empty, so pinning either commit gives identical
semantics. Conformance re-run by the pre-commit hook.

### Effect on the overall project

The library track's Gold-10 obligations are discharged. Ownership passes to Codex.

### Next intended step

**Stop.** Do not rerun Gold-10, do not touch the corpus, do not start Gold-100.

---

## 2026-08-10 — canonical semantic state: candidate lifecycle and certified branch/join

**Branch:** `feature/hml-reasoning-kernel-v2` · **Base:** `fc64965` · **Stage:** semantic
state layer · **Model calls: 0. Training: 0. Corpus modifications: 0.**

### Objective

Close the two semantic objects the Semantic Firewall found HML could not express, driven by
the research corpus rather than by a summary of it.

### What was verified before editing

The mission brief said the repository is the source of truth, so the brief itself was
checked against it. Two findings changed the plan:

- **No branch integration was needed.** The corpus HEAD `fc9b2a3` already contains `main`,
  `codex/semantic-firewall` and `codex/prm800k-natural-error-audit` as ancestors — the
  history is linear. The instruction to "integrate the research commits into one builder
  branch" was already satisfied.
- **The Desktop copies of the five canonical docs are stale** (pre-MiniLang). The repo
  copies are strictly newer and were used.

`experiments/minilang_audit/validate_evidence.py` → PASS (10 operations, 78 examples,
42,699 tree entries). `hml_core` is a git submodule, which is how Codex repins.

### Decisions made, and why

**No syntax.** `docs/04` §6.14 makes canonical typed state primary; the brief forbids syntax
merely to support import. So candidates and branches are semantic objects reachable
programmatically, not keywords. Verified by an empty diff over `ast/`, `lexer/`, `parser/`,
`backends/` and `reasoning/`.

**`UNKNOWN` is a value.** The first fixture run failed on import because `ClaimStatus` had
no `UNKNOWN`. That was the bug, not the fixture: the PRM800K audit is explicit that unknown
and un-adjudicated must be representable, and it is what makes `UNRESOLVED` reachable.

**Scope is containment, not activity.** `_check_scope` initially asked whether the output
scope was active. `global` always is, so it accepted `FX-SCP-ILLEGAL` — a `branch:b1`
conclusion promoted straight to `global`. The rule is that a conclusion may not be wider
than its narrowest premise, absent an explicit discharge.

**Coverage required, disjointness not.** Confirmed against MiniLang's `CONSIDER∨`
obligations: disjunction elimination is sound for overlapping cases, so requiring
disjointness would reject valid reasoning.

**`trusted` is provenance, not permission.** The fixtures carry `trusted: true`; reading it
as authority would accept every corrupted case, since the corruptions attack the evidence
*reference*. Acceptance requires the structural facts instead.

### Tests and verification actually executed

| check | result |
|---|---|
| 30 acceptance fixtures vs frozen reference checker | **30/30 verdict and error class** |
| neutral adapter round trip | **30/30 byte-for-byte** |
| `pytest tests/semantic_state` | 62 passed |
| `pytest tests/reasoning tests/libraries tests/freeze` | passed unchanged |
| `ruff check src/hamiltonian_lang/semantic_state` | clean |
| kernel / AST / grammar / backends diff | **empty** |

### Failures and unresolved uncertainty

Four implementation bugs, each caught by running the fixtures rather than by review:
obligation field names (`status`/`mandatory`, not `state`); `obligations_discharged` entries
are `{id, evidence_id}` records; missing `UNKNOWN` status values; and the scope rule above.
A fifth: evidence cited from `obligations_discharged[].evidence_id` was not being scanned
for UNKNOWN, so a discharge resting on unknown evidence read as valid.

**Recorded honestly — the fixtures are weaker than they look.** SF-R06 requires four
candidate states; no fixture or benchmark case exercises `UNVERIFIED` or `REJECTED`, so
30/30 does not demonstrate it. The two new ILLEGAL fixtures differ from their LEGAL twins
only in a dangling `evidence_id`, so the substantive rules (constraint subset, branch not
CLOSED, conclusion mismatch) are exercised by no fixture; this was built to the reference
checker's source. Acceptance fixtures are not source-held-out.

**A confound found in a frozen experiment, reported not altered.** `HML_OBF` in the causal
scout substitutes nine keywords including the English words `or` and `not`, and
`endpoints/causal_diag.py:124-125` applies the map to the *question* text. The entailment
question therefore reached the model as "…necessarily false, `zeta8` is it `zeta9`
determined…", destroying the clause naming the third answer option — in the one condition
that then answered `UNDETERMINED` on all six items. `HML_OBF` is the only positive signature
for the H2 familiarity hypothesis and the stated justification for the proposed LoRA
experiment. **It should be withdrawn as evidence for H2 until re-run with the question text
held fixed.** No frozen artifact was modified.

### Effect on the overall project

The canonical machine object now exists as data, and the two semantic capabilities the
firewall identified are implemented and checked without touching the trusted core. The
architecture claim — that state semantics can grow while the kernel stays fixed — now has a
second independent test behind it.

### Next intended step

The lossless renderer (SF-R15), deferred by the brief until the semantic objects stabilise;
tests for the substantive candidate/branch rules no fixture reaches; and the `docs/04`
update plus Codex handoff.

---

## 2026-08-10 — Semantic Firewall closeout: the HML view, the domain lattice, and two divergences the fixtures could not see

**Branch:** `feature/hml-reasoning-kernel-v2` (worktree `/Users/moheet/hml_v2_worktree`),
on `4d05aca`.

**Project stage:** Semantic Firewall build. Every requirement in the builder handoff is now
either implemented and measured, or refused in writing with the reason.

### Objective

Finish the three deferred requirement rows in `docs/04` §D — `LIBRARY_CHANGE`, obligation
round-trip through rendering, and `RENDERER_CHANGE` — and write the tests for the rules the
acceptance fixtures never reach, which the previous entry recorded as shipped unexercised.

### Files and systems changed

New: `src/hamiltonian_lang/semantic_state/view.py` (lossless renderer + reader),
`src/hamiltonian_lang/semantic_state/domains.py` (the neutral domain lattice),
`tests/semantic_state/test_lossless_view.py`, `tests/semantic_state/test_domain_library.py`,
`tests/semantic_state/test_unfixtured_rules.py`.
Modified: `semantic_state/verify.py` (two divergence repairs),
`semantic_state/__init__.py` (exports), `docs/hml_v2/SEMANTIC_STATE_CONTRACT.md`,
`docs/PROJECT_STATUS.md`.

`ast/`, `lexer/`, `parser/`, `backends/` and all of `reasoning/` are **unchanged**, asserted
by a test rather than by prose.

### What was completed

**SF-R15, the lossless HML view.** `parse_transition(render_transition(t)) == t` over all 30
fixtures. The model dataclasses are `frozen=True`, so that is structural equality of the
entire transition — a stricter bar than the AST round trip in `tests/roundtrip/`, which
compares canonical hashes and may lose spans. The chained property is the load-bearing one:
corpus JSON → state → view → state → corpus JSON, byte-identical, because its endpoints are
the corpus's bytes rather than anything this repository chose.

**SF-R05, obligations through the rendering.** Asserted on a record carrying every field
SF-R05 names at once, including `mandatory=False`, which no fixture contains and which a
renderer emitting the field only when true would silently drop.

**SF-R14, the domain lattice as library data.** Versioned, justified, enumerable entries in
`domains.py` rather than a table inside the verifier.

### Decisions made and why

**The view is not a backend.** `backends.base.Backend` exists to *declare loss* — its entire
API is `drop`/`approximate`/`weaken` over `Module.statements` — and a `Transition` has no
statements and no source spans. A lossless renderer implemented there would have to lie
about both, and registering it would require editing `backends/`, which is frozen. It is a
standalone renderer + reader inside `semantic_state/`, which is the pattern
`evaluation/syntax_acquisition/_infix.py` already establishes for a non-HML-L1 surface.

**The view is HML-shaped where there is semantics and JSON-literal where there is not.**
Claims, candidates, branches, goals, obligations, the action and evidence get real block
syntax. The free-form fields — `source`, `typing`, `warrant`, the six `*_effect` maps, the
precondition/obligation lists, evidence `payload` — are open dictionaries the corpus may
extend at any time, which is exactly why `neutral.py` preserves them verbatim. Inventing a
surface for content with no semantics attached would make every upstream extension silently
unrepresentable. Values JSON cannot carry back unchanged are refused, per SF-R15's "reject
unsupported fields instead of commenting them away".

**No warrant-rule registry, deliberately.** SF-R10 speaks of theorem warrants and it was
tempting to register the six rule names the corpus uses. The reference checker consults no
such table: `UNRELATED_RULE` fails because it differs from the attached record's
`supports_rule`, not because it is unrecognised. A closed-world registry would reject
warrants the reference accepts — a new divergence created in the course of closing one.

**The domain lattice is not `types.py::_SCALAR_PARENTS`.** That orders HML's own scalar
types; this carries the neutral schema's vocabulary. Merging them would be the kind of
conflation `CLAUDE.md` prohibits.

### Tests and verification actually executed

| check | exact command | result |
|---|---|---|
| conformance gate | `bash scripts/conformance.sh` | **CONFORMANCE: PASS** |
| full suite | `.venv/bin/python -m pytest` | **7248 passed**, 6 skipped, 7 xfailed, 7 xpassed, 0 failed |
| semantic state | `pytest tests/semantic_state` | **266 passed** (was 62) |
| 30 acceptance fixtures | `pytest tests/semantic_state/test_semantic_firewall_acceptance.py` | **30/30**, unchanged by the repairs |
| neutral round trip | same file | **30/30 byte-for-byte** |
| view round trip | `pytest tests/semantic_state/test_lossless_view.py` | **30/30 `parse(render(t)) == t`** |
| chained round trip | same file | **30/30** back to identical corpus JSON |
| lattice vs frozen reference | `test_the_lattice_agrees_with_the_frozen_reference_checker_on_every_pair` | **0 disagreements** over the full cross product |
| mutation check | 5 rules disabled one at a time, suite re-run | **5/5 caught**; `verify.py` restored, `git diff` empty |
| lint | `.venv/bin/ruff check src tests` | All checks passed |
| types | `.venv/bin/mypy src/hamiltonian_lang` | no issues, 107 files |
| frozen core | `git diff HEAD -- ast/ lexer/ parser/ backends/ reasoning/` | **empty** |

The mutation check is recorded because the new rule tests passed on their first run, and a
test that has never failed is not yet evidence. Disabling the constraint-subset check,
"every branch CLOSED", branch-conclusion agreement and both directions of the scope
discharge each made the corresponding test fail; only then were they treated as coverage.

### Results — two real defects, neither visible to the acceptance set

**Divergence 1, a false INVALID.** `_check_type_domain` compared declared domains with `!=`
while the reference checker walks a parent chain. A claim in `Natural` offered where
`Integer` is required was rejected here and accepted by the reference. Sound reasoning,
refused.

**Divergence 2, the dangerous direction.** `_check_warrant` tested whether the evidence's
premises were a *subset* of the action's dependencies; the reference compares the lists
outright, and SF-R09 binds the *exact* premise list. Evidence resting on fewer premises than
the action declared was therefore accepted, so a conclusion could acquire ancestry its
warrant never covered.

**Divergence 3, kept and recorded.** This verifier checks `output_domain`; the reference
never reads it. Deleting a sound check to agree with a gap in the reference would be the
wrong repair. It is strictly stricter, so it cannot admit a corrupted transition — only
question a well-formed one.

Neither repair changes any of the 30 verdicts, which is the point: **the acceptance set
cannot distinguish either pair of behaviours.** Every fixture declares the domain its claim
already has, and every fixture's premise envelope already equals its dependency list. Both
defects were found by reading `reference_checker.py`, not by a test.

### Failures and unresolved uncertainty

Three defects in my own work, each caught by running rather than reviewing: the tab-indent
guard in the view reader could never fire (a leading tab is invisible to `lstrip(" ")`, so a
tab-indented line read as top level); the frozen reference checker could not be imported for
the differential test without being registered in `sys.modules` first, because `dataclasses`
resolves annotations through `sys.modules[cls.__module__]`; and `_is_subtype` is a
staticmethod on `ReferenceChecker`, not a module-level function.

**What this does not establish.** The domain lattice has no fixture support at all — no
fixture exercises a proper subtype relation, so it is justified by the reference checker's
*source*, a weaker warrant than a passing fixture. The rules no fixture reaches are now
tested only by tests written alongside the code they check; mutation-checking shows they
bite, it does not make them external criteria. A lossless view demonstrates
representability, not adequacy: nothing here says the view is a *good* rendering for a human
or a model to reason through. **Nothing in this change was measured against a model.**

`HML_OBF` remains withdrawn-pending as evidence for H2, unchanged from the previous entry
and still not re-run. No frozen artifact was modified.

### Effect on the overall project

The builder handoff is answered end to end: every SF requirement is implemented and
measured, or refused in writing with a reason from the fixtures and the reference checker's
source. The architecture claim — that state semantics can grow while the trusted kernel
stays fixed — now has a renderer behind it as well as a verifier, and the frozen-core diff
is asserted by a test rather than by assertion.

The more useful result is methodological, and it is uncomfortable: a 30/30 pass rate against
an external frozen checker concealed two real defects, one of them in the unsafe direction.
Agreement with an oracle on the cases the oracle happens to contain is not agreement with
the oracle.

### Next intended step

Hand the closeout to Codex, who owns the corpus, and stop. Three items need a corpus-side
decision that cannot be made here: whether the acceptance set should grow fixtures that
distinguish the two repaired divergences; whether `output_domain` is a gap in the reference
or over-strictness here; and the outstanding `HML_OBF` withdrawal.

---

## 2026-08-10 (second entry) — an independent audit found six accepted transitions that should have been refused

**Branch:** `feature/hml-reasoning-kernel-v2`, on `7c9137a`.

**Project stage:** post-build audit of the Semantic Firewall implementation, with corpus /
research-integration responsibilities temporarily merged into the integrator role.

### Objective

Attack `7c9137a` rather than re-read its tests; adjudicate the three open closeout questions;
and repair what the attack confirmed.

### Files and systems changed

`src/hamiltonian_lang/semantic_state/verify.py` (frame condition, dependency-scoped unknowns,
absent-domain handling); `DECISIONS.md` (D-048, D-049, D-050, and the collision block's
Prevention clause); `docs/hml_v2/SEMANTIC_STATE_CONTRACT.md` (§5a correction, new §5b, §5c);
new `tests/semantic_state/test_frame_condition.py` and `tests/freeze/test_decision_ids.py`;
two synthetic test payloads corrected. `ast/`, `lexer/`, `parser/`, `backends/` and
`reasoning/` unchanged.

### What was completed

**Six defects confirmed, five repaired.** Every one was **VALID** at `7c9137a` and every one
was reproduced against pristine production code before anything was changed: a claim asserting
`0 = 1` with status VERIFIED materialising from nothing; an existing premise rewritten
`ASSUMED -> VERIFIED` with its proposition changed; a candidate promoted `PROPOSED -> VERIFIED`
and from the terminal `REJECTED` by writing `candidate_effect: {"kind": "NONE"}`; a mandatory
open obligation deleted; and one unrelated `status: UNKNOWN` claim flipping **10/10** ILLEGAL
acceptance fixtures to UNRESOLVED.

**One root cause.** There was no frame condition. The ten invariants examine what the action
*declares*; none examined whether the resulting state is what applying that declaration would
produce, so every rule was optional to a producer that declined to declare an effect. The
frozen reference has carried `_exact_state_change` all along; it was not ported, and no
fixture could have revealed the omission because all thirty are well-formed records whose
delta already matches their action.

### Decisions made and why

**D-049** — frame condition, checked last, reported as `DEPENDENCY_VIOLATION` where the
reference reports it. Extended beyond the reference to candidates, branches and obligations,
because the reference frames claims only and three of the six probes are accepted by the
reference too. A *declared* effect licenses a change and the effect's own invariant then
decides whether it was legitimate — which is what stops the frame forbidding the transitions
the system exists to make. Unknowns dependency-scoped: unscoped, the rule was not fail-closed
but a denial of service.

**D-048** — an absent domain annotation is unavailable evidence (UNRESOLVED per SF-R13), not a
violation. Production was rejecting a transition for *lacking* an annotation, in a format that
cannot represent "carries no domain" both schema-validly and losslessly. Classification is
split, not wholesale: **REFERENCE_GAP** where both annotations are present and disagree,
**HML_OVERSTRICTNESS** where one is absent.

**D-050** — the trust boundary. Classified **BLOCKER**, deliberately not repaired. The repair
is a decision about where the trusted boundary sits for state transitions and must reuse
`reasoning/certificates/` rather than grow a second registry; inventing one under an audit
finding is how a second unattested path gets built.

**Decision-ID collisions: enforced, not renumbered.** The premise of the instruction was
stale — the collision was already found, documented and deliberately accepted. An independent
re-count upheld that: ten of ~65 citations are in the frozen core, so renumbering would mean
editing frozen files to repair a documentation defect. A mechanical gate replaced the prose
rule instead.

### Tests and verification actually executed

| check | result |
|---|---|
| `bash scripts/conformance.sh` | **CONFORMANCE: PASS** |
| `.venv/bin/python -m pytest` | **7268 passed**, 6 skipped, 7 xfailed, 7 xpassed, 0 failed |
| `pytest tests/semantic_state` | **279 passed** (was 266) |
| 30 acceptance fixtures | **30/30 unchanged by every repair** |
| the six audit probes, re-run | **6/6 now INVALID or ineffective** |
| UNKNOWN suppression | **0/10** (was 10/10) |
| mutation: frame disabled / scoping reverted | **both caught** |
| mutation: new ID collision / gap / dangling citation | **all caught** |
| `ruff check src tests` | clean |
| `mypy src/hamiltonian_lang` | clean, 107 files — caught one real error |
| frozen core diff | **empty** |

### Failures and unresolved uncertainty

**A false claim was published in the last commit and is now corrected.** The contract said the
retained `output_domain` divergence made this verifier "strictly stricter, so it cannot let a
corrupted transition through". True of that one check; false as a general claim. On the six
behaviours above production was strictly *weaker* than the reference it is specified to match.
Corrected in place rather than deleted, because the error worth not repeating is inferring a
safety direction from one check and generalising it.

**Attempted and reverted:** making INVALID outrank UNRESOLVED, which is what the reference
does. It requires each check to skip unknown values individually rather than the verdict
short-circuiting, and could not be validated against thirty fixtures that never exercise it.
Recorded as a known divergence, now narrow because the unknown must be on a cited record.

**Still open, with reproductions recorded:** sibling scopes are ordered by list position, so a
premise in `branch:a` may conclude into `branch:b` while the mirror image is a SCOPE_LEAK —
same situation, opposite verdicts. `neutral.export_state` re-keys collections by `record.id`,
so `export(import(x)) != x` when a dictionary key differs from the record's id — a real
losslessness defect the view layer handles and the adapter does not. `verify()` raises rather
than returning a verdict on a malformed `typing.input_domains`. A join may still publish a
claim when every branch's conclusion is null.

**Three of my own errors, caught by running:** two synthetic test payloads dropped premises
from `state_after` and were malformed transitions rather than neutral ones — the frame
condition caught them on its first run; mypy caught a shadowed binding; and the decision-ID
gate caught two forward references to records I had not yet written.

### Effect on the overall project

The verifier now checks that a transition happened, not merely that it was described. That was
the missing half. The methodological result is the more important one and it is now twice
confirmed: **a 30/30 pass rate against an external frozen checker has concealed real defects
in two consecutive commits**, and on this occasion five of six ran in the unsafe direction.
Reading the oracle's *source* found what running its cases could not, both times.

### Next intended step

Corpus side, still open: commit the audited cognition ledger; formally withdraw HML_OBF;
correct the canonical statements that imply five existing experiments do not exist; label
Gold-125 coverage as historical at HML `5688aba`; and decide whether to adopt the proposed
`FX2-*` fixture suite. Then D-050, which needs its own design record before any model output
reaches this verifier.

---

## 2026-08-10 (third entry) — HML_OBF formally withdrawn; two false statements in public docs corrected

**Branch:** `feature/hml-reasoning-kernel-v2`, on `8bcd9a5`. **Stage:** corpus /
research-integration, temporarily merged into the integrator role.

### Objective

Withdraw `HML_OBF` as causal evidence without destroying it, and correct programme-level
statements that assert evidence does not exist when it does.

### What was completed

**The confound was verified from source, not accepted from a report.** `causal_diag.py:48-58`
maps five ordinary English words (`implies`, `iff`, `and`, `or`, `not`), and
`render_question` at `:121-125` applies the map to the **question text**. Re-derived from the
frozen deterministic builder:

* `HML_BASIC`: *"Is P6 necessarily true, necessarily false, or is it not determined by these assumptions?"*
* `HML_OBF`:   *"Is P6 necessarily true, necessarily false, zeta8 is it zeta9 determined by these assumptions?"*

The clause naming the third answer option is destroyed, in the one arm that then answered
UNDETERMINED on 6/6 items. Degraded reasoning and a destroyed question predict the same
observation; this design cannot separate them.

**Withdrawn:** `HML_OBF` as positive evidence for H2/familiarity, and as the justification for
the LoRA adaptation experiment. **Not concluded:** that familiarity is false. It is
**unresolved**, because the one experiment offered in its support is confounded.

**Nothing was deleted or re-run.** The code, the raw records and every original manifest value
are unchanged; `CAUSAL_DIAGNOSIS_MANIFEST.json` gained one additive `WITHDRAWN` key, verified
programmatically to leave all pre-existing fields equal. Full record in
`evaluation/arena/results/HML_OBF_WITHDRAWAL.md`.

**Two further defects recorded:** the manifest describes `HML_OBF` as preserving "operators",
which its own map contradicts — as implemented the condition removes the logical vocabulary
and supplies no key, so it never measured a familiarity tax at all. And no test covers
`causal_diag`, unlike Endpoint A and B2, which both carry prompt-construction audits.

### The correction that matters most

`README.md` said **"No comparative evaluation has been run."** Written 2026-08-04; false ever
since. Four comparative probes exist. Corrected to state what they actually show, which is
weaker than the original sentence implied and worse for the thesis: implication direction SE
5/12 vs HML 1/12; next-action advantage did not survive replication (Δ 0.000); quantifier
scope won by a generic S-expression; the saturated benchmark paired difference 0.000, CI
[0, 0]. All underpowered, none licensing a conclusion either way.

This is the failure the cognition audit named: **the programme was reasoning from a cleaner
picture than its own data supports**, because absence-of-evidence statements scoped to one
repository were being read programme-wide.

### Verification actually executed

`bash scripts/conformance.sh`: **CONFORMANCE: PASS**, including the "no unsupported
superiority claims in public docs" stage against the rewritten README. Manifest annotation
verified additive by comparing every pre-existing key against the original parse. The other
four scout arms re-read from `CAUSAL_SCOUT.json` and unchanged: SE 5 · HML_BASIC 4 · HML_EPI 3
· HML_OBF 2 · HML_VERIFY 3.

### Failures and unresolved uncertainty

`evaluation/results/runs/eval001-pilot.jsonl` — the raw model outputs behind HML-EVAL-001 — is
**gitignored and exists on disk in one worktree only**. The committed analyses are summaries
whose raw backing is not in version control, and the run used temperature 0.7 with no seed, so
it cannot be reproduced by re-running either. No arena run passes a sampling seed at all;
`order_seed` controls call order only, and the frozen manifests' runtime blocks do not
disclose this. Both recorded, neither repaired.

### Next intended step

Corpus repository: commit the audited cognition ledger, correct the four unscoped
absence-of-evidence statements, label Gold-125 coverage historical at HML `5688aba`, and
decide on the proposed `FX2-*` fixture suite.

---

## 2026-08-10 (fourth entry) — D-050 closed: a trust mode, and evidence status stops being authority

**Branch:** `feature/hml-reasoning-kernel-v2`, on `a21fdb7`. **Stage:** Phase I of the final
semantic freeze — correctness blockers before any benchmark.

**Objective.** Close the trust boundary classified as a BLOCKER by D-050, reusing
`reasoning/certificates/` rather than inventing a second registry.

**Files changed.** New `src/hamiltonian_lang/semantic_state/trust.py` and
`tests/semantic_state/test_trust_boundary.py`; `verify.py` routes all four evidence
acceptance sites through one seam; `DECISIONS.md` gains D-051.

**What was completed.** `TrustMode.OFFLINE_REPLAY` (default) reads recorded evidence status
as observed reference data from a frozen external corpus. `TrustMode.RUNTIME` ignores it
entirely and requires an `Attestation` carrying a `CheckedEvidence` — unforgeable, because
`certificates.check` mints it behind a module-private token. Attestations bind claim digest,
premise digests and rule, so a valid certificate cannot be replayed onto a transition it was
not issued for.

**Decisions and why.** No second registry: two trust bases mean two review surfaces and
eventually one accepts what the other refuses. The default is the *replay* mode, so the
unsafe reading is never what a caller gets by forgetting an argument, and `mode` is
keyword-only so it cannot be passed positionally by accident.

**Tests and verification actually executed.**

| check | result |
|---|---|
| `pytest tests/semantic_state/test_trust_boundary.py` | **17 passed** |
| 30 frozen acceptance fixtures | **30/30 unchanged** |
| full suite | **7,285 passed**, 0 failed |
| `ruff check src tests` | clean |
| `mypy src/hamiltonian_lang` | clean, **108** files |
| mutation: seam disabled | **3 tests killed** |
| mutation: `binds()` always true | **3 tests killed** |
| mutation: enum value renamed | no kill — verified to be a semantic no-op (mode comparison is an identity check on the member), not a test gap |

**Failures and unresolved uncertainty.** The attack suite found a real hole in my own first
implementation: the candidate site bound only the *rule*, not the claim, so a valid
certificate issued for a different proposition was accepted. Fixed; all three sites now bind
claim, premises and rule.

Two limitations recorded rather than glossed. The attestation binds a proposition's **text
digest**, not `expr_identity` over a typed AST, because corpus propositions are opaque
strings that generally do not parse — strictly weaker, and this layer cannot tell you two
formattings mean the same thing. And **RUNTIME has no production caller**: nothing in `src/`
runs the verifier on model output yet.

**Blocker discovered.** Phase VI cannot run on this machine. No training stack is installed
(`torch`, `transformers`, `peft`, `trl`, `mlx`, `mlx_lm` all absent) and ollama is
inference-only. The matched Gemma experiment needs an environment decision before design can
proceed.

**Next intended step.** Phase I remainder: the five reproduced defects (sibling scope,
neutral re-keying, malformed typing, null branch conclusions, corpus schema) and the
second-generation fixture suite.

---

## 2026-08-10 (fifth entry) — correcting a miscount in this repository's own record

**Branch:** `feature/hml-reasoning-kernel-v2`, on `06b5d99`. **Stage:** Phase I.

**Objective.** Correct a factual error in `PROJECT_STATUS.md` and in the title of commit
`8bcd9a5`, found by the third independent audit of the cognition ledger.

**What was wrong.** Both said the audit of `7c9137a` found "six accepted transitions that
should have been refused" and that "the sixth is a classified blocker". **Five** probes
returned VALID. The sixth — appending one unrelated `status: UNKNOWN` claim — returned
UNRESOLVED across 10/10 ILLEGAL fixtures, which is a suppression of detection rather than an
acceptance, and it *was* repaired at `8bcd9a5` along with the other five. The "classified
blocker" is D-050, a separate finding that was never among the six, now closed by D-051.

**Verification.** Re-read from this repository's own recorded probe output: five lines report
`VALID`, one reports `10/10 became UNRESOLVED`. D-049's Verification section already said
"6/6 now INVALID or ineffective" — the word *ineffective* is the sixth, and the summary
heading flattened it into "accepted".

**Effect.** No code, test or verdict changes. The defect count is unchanged at six and the
repairs are unchanged; what was wrong was the characterisation of one of them. Recorded
rather than quietly edited, because a miscount that inflates the severity of one's own
findings is the kind of error that should leave a trace.

**Next intended step.** Phase I remainder: the five reproduced defects and the
second-generation fixture suite.

---

## 2026-08-10 (sixth entry) — no default trust mode; four holes in my own D-050 fix

**Branch:** `feature/hml-reasoning-kernel-v2`, on `c623dd6`. **Stage:** Phase I.

**Objective.** Act on the addendum's §2 (runtime trust must be impossible to omit) and on an
independent adversarial audit of the D-051 implementation.

**What was completed.** `verify()` no longer defaults its trust mode; `verify_replay` and
`verify_runtime` name it at the call site; `verify_payload` is renamed `replay_payload` and
all 53 call sites migrated. Four holes closed: `attest()` was forgeable by attribute shape
and now checks the mint token; a **fifth** trust site (`_check_warrant`) read no status at
all and accepted explicitly-REJECTED evidence; attestations were keyed by payload-controlled
`record.id` and are now keyed by the id the action cites; and the scope-discharge site passed
an empty binding, so any zero-premise attestation licensed a scope escape.

**Verification.** 22 trust tests (was 17); four attacks re-run and closed; 30/30 frozen
fixtures replay unchanged; `pytest tests/semantic_state` 289 passed; mypy clean.

**Failures and unresolved uncertainty.** Every one of these was a defect in my own work from
the previous commit, found by an audit I commissioned rather than by my own tests. The
default-mode error is the instructive one: I wrote an explicit argument for why the default
was safe, and the argument was backwards.

Four defects remain **open** at HEAD, all measured against a pinned `a21fdb7` export:
sibling-scope order (plus a duplicate-`active_scopes` bypass needing no forgery), neutral
dict-key identity (verdict is not stable under the adapter's own round trip; records can
collapse silently), 15 uncaught-exception signatures on malformed input, and null branch
conclusions. A mutation census of 76 mutations found **22 invariants with no test behind
them**, including the entire `GOAL_DISCHARGE` family.

**Next intended step.** The four remaining defects, the corpus schema repair (R2), and the
22 uncovered invariants.

---

## 2026-08-11 — the four reproduced verifier defects closed; corpus pushed

**Branch:** `feature/hml-reasoning-kernel-v2`, on `22e6a0a`. **Stage:** Phase I of the final
hardening.

**Objective.** Push the unpushed corpus commits, then close the four defects an independent
adversarial audit reproduced against `a21fdb7`.

**What was completed.** The corpus was **3 commits ahead and unpushed** — `f7d85bc` is now on
origin, validated with a real YAML parser first (148 entries, X1–X148, contiguous, no
duplicates, no dangling references). Then all four defects, each with regression tests and
mutation checks: scope containment derived from the branch tree; mapping key as identity;
import-boundary type guards plus a catch-all; and a join that requires every branch to have
concluded something.

**Decisions and why.** Scope ancestry is now *derived* from data the schema already carried
(a branch records the frame it sits inside) rather than inferred from `active_scopes`
position — and the three dimensions the addendum names are kept separate: scope ancestry,
goal ancestry, execution order. For the key/id question, both are preserved losslessly rather
than refusing the mismatch: `view.py` is built to carry the divergence, so a refusal would
make `neutral.py` reject documents `view.py` exists to represent, and would make "export is
the inverse of import" vacuous rather than true.

**Tests and verification actually executed.**

| check | result |
|---|---|
| `pytest tests/semantic_state/test_reproduced_defects.py` | **29 passed** |
| fuzz sweep, 1,024 malformed payloads × both trust modes | **0 uncaught exceptions** (was 15 signatures) |
| 30 frozen acceptance fixtures | **30/30 unchanged** |
| `pytest tests/semantic_state` | **332 passed** |
| mutation: containment always true | 3 killed |
| mutation: export re-keys by `record.id` | 2 killed |
| mutation: duplicate-scope guard removed | killed (after pinning its diagnostic) |
| mutation: null-conclusion guard removed | killed (after pinning its diagnostic) |

**Failures and unresolved uncertainty.** Two mutations initially **survived**. Each guard is
redundant with the other repair — containment already defeats the duplicate-scope attack, and
the mismatch check already catches a null conclusion. Rather than write vacuous tests to
raise a score, both are now pinned on the *diagnostic* they produce, which is the part the
redundant path cannot supply and the part a reader debugging actually needs. Recorded because
"the mutation survived and here is why" is a better answer than a manufactured kill.

One historical test was **reversed**: it asserted that a null branch conclusion does not block
a join. Its original claim is quoted verbatim in the replacement rather than deleted.

**Next intended step.** Corpus schema repair (agent running), FX2 suite, the 22 surviving
mutations from the earlier census, then P-01/P-02/P-03.

---

## 2026-08-11 (second entry) — FX2 wired into the HML suite

**Branch:** `feature/hml-reasoning-kernel-v2`, on `b0335fa`. **Stage:** Phase I hardening.

**Objective.** Run the second-generation acceptance suite against production, and pin the
properties a parametrised sweep would miss.

**What was completed.** `tests/semantic_state/test_fx2_suite.py` (47 tests). Beyond the
per-fixture sweep it pins four things a sweep cannot: that the **trust mode is load-bearing**
(the two TRU fixtures are byte-identical apart from the mode, so if they agreed either the
runtime gate has stopped working or replay has stopped replaying); that the **sibling-scope
pair agrees with itself** (the defect was an asymmetry, which one fixture cannot detect);
that every divergence from the frozen reference is **declared** with a reason; and that the
suite keeps saying, in the artifact itself, that it is not external evidence.

**Tests and verification actually executed.** `pytest tests/semantic_state/test_fx2_suite.py`
**47 passed**; `pytest tests/semantic_state` **379 passed**; FX2 **40/40** against
hand-written expectations. Mutation-checked against six repairs: frame condition disabled
(5 fixtures fail), scope containment always true (3), warrant envelope unchecked (3),
unknown sweep unscoped (1), import type guards removed (the runner raises, so the MAL family
detects it), null-conclusion guard removed (**0 — classified as verdict-equivalent**).

**Failures and unresolved uncertainty.** FX2 is integrator-authored and weaker than the
frozen thirty; a green run is not external validation, and the test asserts that the artifact
keeps saying so. The corpus-side suite caught a real inconsistency in my own metadata during
construction: after `NaN` moved to a `materialise` instruction that fixture's case became
well-formed JSON, so its `schema_valid` flag was wrong — and a second MAL fixture turned out
to be schema-valid *and* semantically malformed, now kept deliberately to show that passing
the published schema is not the same as being a well-formed transition.

**Next intended step.** The 22 surviving mutations from the earlier census; then
P-01/P-02/P-03; then the semantic freeze, release manifest and tag.

---

## 2026-08-11 (third entry) — P-01/P-02/P-03 adjudicated; two need no code

**Branch:** `feature/hml-reasoning-kernel-v2`, on `19473df`. **Stage:** Phase II.

**Objective.** Adjudicate the three architectural proposals, implementing only the minimum
the evidence supports.

**What was completed.** A full inventory of `Action.operation` in production, three decision
records (D-054/D-055/D-056), the P-01 effect-rule migration, and five regression tests.

**Findings that corrected the premise.** The brief assumed `VERIFY_CANDIDATE` and
`JOIN_BRANCHES` both drew semantic authority from their raw strings. Measured: `JOIN_BRANCHES`
is compared as a string **nowhere** — branch join is gated entirely on the typed effect kind —
and the single `VERIFY_CANDIDATE` comparison sits *inside* the `kind == "PROMOTE"` branch, so
the effect had already discriminated. The real authority was `operation` doubling as the rule
name evidence must support, at six sites. That is what moved into `_effect_rule`.

**P-02 needed no code at all.** Under the frame condition an existing claim already must
persist unchanged, and `output_id` already licenses exactly one addition — so "rewrite h" is
expressible today as "derive h', keep h". The capability was present; only its recognition
was missing. Versioned identity and literal mutation were both rejected: neither is justified,
and a mutation channel would weaken the one rule that makes every other rule enforceable, in
exchange for concision.

**P-03 was decided by measurement, not preference.** 631 transitions scanned: `goal_effect` is
only `NONE` (567) or `DISCHARGE` (63), `scope_effect` is `NONE` in all 630, and **no
transition anywhere has more than one goal**. `created_by_action` was again confirmed to
appear nowhere in either repository — a proposal from a brief, not a repository fact.

**Tests and verification actually executed.** `pytest tests/semantic_state` **384 passed**;
30/30 frozen fixtures unchanged; FX2 40/40; `bash scripts/conformance.sh` **PASS**; ruff and
mypy clean. Effect-rule behaviour measured directly: fallback → VALID, explicit matching rule
→ VALID, explicit non-matching rule → INVALID/`CANDIDATE_PROMOTION`, and an effect rule that
disagrees with the label but matches the evidence → VALID, which is what proves the authority
actually moved rather than the migration being cosmetic.

**Failures and unresolved uncertainty.** P-01 is **half done by design**: the label becomes
purely decorative only once the corpus emits explicit effect rules, which is a corpus-side
change. The `operation != "VERIFY_CANDIDATE"` comparison is retained and reclassified as a
provenance/effect *agreement* check rather than deleted.

**Next intended step.** Mutation census and schema audit (both with agents); then the
semantic freeze, release manifest and annotated tag.

---

## 2026-08-11 (fourth entry) — P-01 completed: the legacy fallback is scoped to replay

**Branch:** `feature/hml-reasoning-kernel-v2`, on `10c1879`. **Stage:** Phase II.

**Objective.** Close the gap review identified in the first P-01 adjudication: the legacy
fallback let `Action.operation` supply rule semantics at runtime whenever the typed effect
omitted one.

**What was completed.** `_effect_rule` now returns `(rule, refusal)`. Under `OFFLINE_REPLAY`
an absent effect rule falls back to the operation label — the thirty frozen fixtures depend
on it and are immutable. Under `RUNTIME` there is no fallback and the transition is refused.
The `operation != "VERIFY_CANDIDATE"` agreement check is scoped the same way.

**The test that found the second gap.** I wrote a discriminating test — same state, same
effects, same warrant, same evidence, five different operation labels — asserting one verdict.
It **failed**: the retained agreement check still let the label flip a runtime verdict. So the
first version of this adjudication was wrong in the same direction review had flagged, one
level deeper. Scoping the agreement check to replay closed it, and the test now passes.

**Tests and verification actually executed.** `pytest tests/semantic_state` **386 passed**;
`bash scripts/conformance.sh` **PASS**; 30/30 frozen fixtures; FX2 40/40. Measured directly:
replay with no effect rule → VALID (fallback intact); runtime with no effect rule → INVALID
("the effect states no explicit rule"); replay with a label disagreeing with its effect →
INVALID (agreement check intact).

**Failures and unresolved uncertainty.** This is the second correction to P-01 in one day, and
both came from outside my own first analysis — one from review, one from a test I wrote to
check review's point. Recorded because the pattern matters: the adjudication *sounded*
complete both times.

**Next intended step.** Correct the P-02 claim, run the P-03 external Lean witness audit,
integrate the schema audit and the mutation census, then the freeze gate.

---

## 2026-08-11 (fifth entry) — mutation census regenerated; 19 gaps closed; three of my tests were theatre

**Branch:** `feature/hml-reasoning-kernel-v2`, on `aac4483`. **Stage:** Phase I/II closure.

**Objective.** Regenerate the mutation census at current HEAD and close the high-severity
gaps before the freeze gate.

**What was completed.** 142 mutations across all six `semantic_state` modules; 101 killed, 41
survived, every survivor classified with a measured probe and **zero `UNCERTAIN`**. 19 killing
tests integrated as `tests/semantic_state/test_mutation_gaps.py`.

**The high-severity holes, all fail-open.** Attestation aliasing (D-052's hole reopened by a
one-character edit); both `BRANCH_JOIN` evidence rules; a warrant citing evidence that does
not exist; conclusions written into frames never opened; both scope-discharge bindings;
`UNSATISFIED` preconditions; ancestry weakened to a subset test (laundered provenance); an
obligation walking `OPEN → DISCHARGED` with nothing declared; and the **entire
`GOAL_DISCHARGE` family**, one of whose mutants raises an unhandled `AttributeError` out of
`verify()`. One mutation removes a cycle guard and **hangs the verifier indefinitely** on a
payload containing no evidence at all.

**Three of my own tests passed for the wrong reason.** Recorded plainly because the pattern is
the project's recurring one. `test_an_attestation_cannot_be_routed_by_a_payload_controlled_id`
passed **no attestations at all**, so both lookups missed an empty mapping — it would have
passed with D-052's repair reverted, and it was named for a hole it could not detect.
`test_the_scope_discharge_site_binds_its_claim` mismatched on the claim *and* the premises, so
removing either binding alone was invisible. `test_a_cyclic_scope_tree_does_not_hang_the_verifier`
picked a pair answered on the first hop and never entered the loop. All three are renamed to
state what they do check; the real properties are pinned separately and mutation-verified.

**Why `GOAL_DISCHARGE` looked covered.** `FX-GOL-ILLEGAL` violates rule 1 and rule 3 at once,
so each rule covers for the other: removing rule 1 alone still reports `FALSE_GOAL_DISCHARGE`
and the fixture still passes. Three individual survivors sat behind one apparent kill.

**Tests and verification actually executed.** `pytest tests/semantic_state` **405 passed**
(was 386); `bash scripts/conformance.sh` **PASS**; ruff and mypy clean. Spot-verified four of
the highest-severity killing tests myself by re-applying their mutants: each killed exactly
its named test and nothing else.

**Failures and unresolved uncertainty.** The census also found: `_check_preconditions`'
docstring named `"UNSATISFIED"`, a literal appearing in no fixture (`FX-PRE-ILLEGAL` records
`"FAILED"`) — corrected, behaviour unchanged. D-053's key/id repair is tested for **1 of 5**
record kinds; goals, candidates, obligations and branches export-keying remain unpinned.
`SemanticState.visible()` is dead public API carrying a safety claim in its docstring. A
blast-radius check confirmed **no test outside `tests/semantic_state/` can observe any change
to these six modules**.

**Next intended step.** P-02 claim correction, the P-03 external Lean witness audit, integrate
the corpus schema audit, then the freeze gate.
