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
