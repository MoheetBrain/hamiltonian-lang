# Pre-Evaluation Audit — HML-EVAL-001

Every claim below was produced by running a command during this audit. Nothing is carried
over from a previous status summary. Where a previous summary was wrong, the correction is
marked **CORRECTION**.

Audit date: 2026-08-04.

---

## 1. Repository state

| item | value |
|------|-------|
| branch | `main` |
| HEAD | `2ea31b4a144f02bf9b271d3aa0f2c72304f28e6c` |
| parent | `0d7cf103c780749038f6b3cfc823d68707771cb9` |
| root | `965a7c7155938b319f69db2f73b5cefb6e4e4149` (the original bare README) |
| working tree | clean (0 modified files at audit start) |
| remote | `origin` → `https://github.com/MoheetBrain/hamiltonian-lang.git` |

**Nothing has been pushed.** Verified with `git log --branches --not --remotes`, which
lists both project commits as local-only. The remote is configured but contains only the
initial commit.

## 2. Conformance

`./scripts/conformance.sh` → **CONFORMANCE: PASS**, all 8 stages:
ruff · mypy · examples check · pytest · IR schema validation · no-superiority-claim check ·
private-docs check · no-placeholder check.

`.venv/bin/python -m pytest` → **609 passed, 0 failed** at audit start.
After the fix in §7, **615 passed**.

## 3. Implemented constructs

Verified by importing the modules, not by reading documentation.

| category | count | members |
|----------|-------|---------|
| declaration kinds | 6 | `var param const obs index rv` |
| inference queries | 5 | `posterior expectation variance mle map` |
| concept members | 6 | `parameter transform invariant property example counterexample` |
| scalar types | 9 | `Bool Integer Natural NonNegativeReal PositiveNatural PositiveReal Probability Rational Real` |
| base dimensions | 7 | Mass Length Time Temperature Current Amount Luminosity |
| distribution families | 16 | Bernoulli Beta Binomial Categorical Cauchy Dirichlet Exponential Gamma HalfNormal InverseGamma LogNormal Normal NormalVector Poisson StudentT Uniform |
| backends registered | 9 | english graph hml json latex lean stan sympy triples |
| graph edge kinds | 15 | closed vocabulary, asserted at insertion |
| diagnostic codes | 82 | L:3 P:26 N:7 T:26 D:5 S:7 (+ B reserved, unused) |

Type constructors: `Vector Matrix Tensor Set Function Predicate RandomVariable
Distribution Quantity Proposition`.

## 4. Unsupported constructs

From `docs/design/V0_DESIGN_FREEZE.md` §8, each re-verified against the code:

- proof **search** of any kind — Lean output is statement skeletons with `sorry`
- measure-theoretic foundations beyond family names and parameter roles
- continuous-time processes, SDEs
- dependent types over runtime values — shape extents are checked **nominally**, so
  `Vector[Real, N+1]` is inexpressible and `Vector[Real, N]` vs `Vector[Real, M]` differ
  by name only
- unit *conversion* — dimensions are checked; metres and feet are indistinguishable
- user-defined distribution families with custom densities
- import / multi-module linking
- provenance and derivation history (D-011)
- role labels on ordinary function `Call`s — the discipline covers `DistExpr` only (Q-05)

## 5. Rendering versus round-tripping — **the central audit finding**

The directive asks these be distinguished. They are not the same thing, and the gap is
larger than the phrase "9 backends" suggests.

Method: compile `examples/statistics/bayesian_coin.hml`, render to each backend, feed the
emitted text back to `compile_source`, and compare content hashes.

| backend | declares itself faithful | losses reported | re-parses as HML | hash preserved |
|---------|-------------------------|-----------------|------------------|----------------|
| `hml` | yes | 0 | **yes** | **yes** |
| `json` | yes | 0 | no | no |
| `graph` | yes | 0 | no | no |
| `triples` | yes | 0 | no | no |
| `english` | yes | 0 | no | no |
| `latex` | no | 5 | no | no |
| `stan` | no | 7 | no | no |
| `sympy` | no | 6 | no | no |
| `lean` | no | 7 | no | no |

**Exactly one round trip exists: HML → HML.** It is the one that cannot lose anything.
Every other backend is one-way rendering. No semantics-preserving translation to or from
any external system has been demonstrated.

**CORRECTION to earlier summaries.** Describing the project as having "nine backends"
invites the reading that nine translations are available. Nine *renderings* are available.
The count of demonstrated semantics-preserving translations is **one**, and its source and
target are the same language.

**A contract weakness this exposes.** `json`, `graph`, `triples` and `english` report
`faithful=True` because `BackendResult.faithful` only checks whether `unsupported` is
non-empty. `english` is a one-way prose rendering that cannot be read back; calling it
"faithful" is misleading even though its `limitations` field says so in prose. The flag
means "declared no per-construct loss", not "round-trips". §9 of the directive is the fix:
round-trip status must be *measured*, not self-reported.

## 6. Benchmark results that are compiler assertions, not AI evaluations

**Every currently recorded benchmark number is a deterministic compiler property. Not one
is a model-performance observation.** `evaluation/results/baseline.json` states this in its
own header, and the audit confirms it.

| recorded metric | what it actually measures | AI involved |
|-----------------|---------------------------|-------------|
| `valid_parse_success_rate` 21/21 | hand-authored files parse | no |
| `negative_rejection_rate` 3/3 | hand-authored invalid files are rejected | no |
| `assertions_passed` 93/93 | compiler output matches hand-authored ground truth | no |
| `diagnostic_quality.line_accuracy` 1.0 | compiler points at the injected line, 50 trials | no |
| `tokens.by_arm` | character/token counts of hand-authored text | no |
| type/role/scope/semantic-equivalence rates | compiler agreement with hand-authored truth | no |
| `experiments/alphabet/**` | tokeniser fragmentation of hand-authored corpora | no |

Corpus size at audit: **24 problems**, 5 arms, 125 files. The directive requires ≥120
problems and 7 arms.

**Consequence.** The project has measured that its compiler behaves as its authors
intended. It has measured nothing about whether a model reasons better through it. That is
the entire content of HML-EVAL-001.

## 7. Defect found during this audit — D-019, lexer non-termination

The round-trip probe in §5 **hung**. Cause: `str.isalpha()` is true for every Unicode
letter, so `ℝ` (U+211D, emitted by the Lean backend in `variable (theta : ℝ)`) was
dispatched into the identifier routine, which accepts only ASCII and folded Greek. It
consumed **zero** characters, emitted an empty token, and returned; the caller
re-dispatched on the same character indefinitely.

Minimal reproducer: a file containing only `ℝ`.

This is recorded as **D-019** with two redundant fixes, 8 regression cases covering CJK and
mathematical italic pi, and a test that feeds real Lean output back through the parser.

**Why it is worth this much space in an audit.** The evaluation harness feeds model output
to the parser. Models emit `ℝ`, `∈`, `∀` and Greek routinely. The first such generation
would have hung the run — no timeout, no diagnostic, no error. The experiment would have
failed silently rather than loudly. It was found only because the audit tested a claim
(round-tripping) instead of trusting it.

Verified no prior result changed: all example content hashes and the golden snapshot are
unchanged, full suite green.

## 8. Model availability for the experiment

| item | value |
|------|-------|
| endpoint | `http://localhost:11434/v1` (Ollama, OpenAI-compatible) |
| model | `gemma4:31b` |
| digest | `6316f0629137b426…` |
| parameters | 31.3 B |
| quantisation | Q4_K_M |
| size on disk | 19.9 GB |

Verified generating. **It is a reasoning model**: responses carry a separate `reasoning`
field alongside `content`, and completion-token counts include the reasoning trace.

Measured throughput on a representative encoding prompt, run twice:
**638 completion tokens, 25.7 s and 25.9 s.** Identical output at `temperature=0`.

### The binding constraint, stated up front

The directive specifies 120 problems × 7 arms × 3 generations = **2 520 calls**. At the
measured 26 s that is **≈18.2 hours** of continuous generation on this machine.

That is not a reason to fabricate or to quietly shrink the design. The apparatus will be
built for the full specification; the *run* will be a preregistered subset sized to what
actually completes, and the report will state exactly which cells were executed and which
were not. An unrun cell will be reported as unrun.

### Two confounds this model introduces, recorded before any result exists

1. **Reasoning-model confound.** The model performs structured decomposition internally
   regardless of arm. Arm A′ (structured English) manipulates a variable the model may
   already supply for itself, which biases the A vs A′ contrast *towards the null* and
   therefore biases the A′ vs Hamiltonian contrast in Hamiltonian's favour. Any Hamiltonian
   advantage over A′ measured here is an **upper bound**, not an estimate.
2. **Token accounting.** Reasoning tokens are billed to `completion_tokens` but do not
   appear in `content`. Compute matching must use total completion tokens, and any
   "token efficiency" claim must say which channel it counts.

## 9. Pre-registered position before any data is collected

- Nothing in this repository is evidence for the project thesis.
- The one demonstrated round trip is HML → HML.
- The measured token cost of D-003 (≈5.9%) is a property of hand-authored text, not of
  model output.
- The strongest argument against the thesis — that the inference happens when the file is
  *written*, not read — is unaddressed by anything measured so far, and Arm A′ is the test
  of it.
