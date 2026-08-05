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

