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
