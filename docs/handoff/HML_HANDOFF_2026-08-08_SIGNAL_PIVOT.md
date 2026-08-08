# HML handoff — 2026-08-08 · signal pivot

Written at the end of a context window for a **fresh Claude context**. Everything below was
verified at write time, not carried over from earlier reports.

---

## A. Repository

| | |
|---|---|
| worktree | `/Users/moheet/hml_v2_worktree` ← **all work happens here** |
| branch | `feature/hml-reasoning-kernel-v2` |
| starting SHA (session) | `3dd4216` |
| final local SHA | see the checkpoint commit at the end of this file |
| remote | `origin/feature/hml-reasoning-kernel-v2`, in sync |
| tree | clean |
| tests | **6342 passed**, 5 skipped, 7 xfailed, 7 xpassed, **0 failed** |
| venv | `/Users/moheet/hml_v2_worktree/.venv` (needs `sympy`, `tiktoken`, `jsonschema`, `hypothesis` beyond `.[dev]`) |

**Worktree discrepancy — read this first.** The shell's default directory is
`/Users/moheet/hamiltonian_lang`, which is a **different worktree** sitting on
`integration/m1.5-paper-derived-closeout` @ `3dd4216`. It has not been touched and must not
be. `cd /Users/moheet/hml_v2_worktree` before anything.

The commit-protocol hook evaluates the *default* directory, so `git commit` from a `cd`
subshell is blocked. Use `git -C /Users/moheet/hml_v2_worktree commit …`, and **never put
the ledger/status edits in the same compound command as the commit** — the hook blocks the
whole command and the edits silently never run. That mistake was made three times.

Third worktree: `/Users/moheet/hml_audit_worktree` @ `b1ac7bf` — **read-only scientific
evidence**, never modify.

---

## B. Scientific state

| hypothesis | status |
|---|---|
| H1 (representation exists / compiles) | partially — compiler works, coverage incomplete |
| ACQ0 (can a model write HML?) | **NEVER VALIDLY MEASURED.** Only tranche was n=8, closed `MEASUREMENT_INVALID` |
| H2 (HML vs structured English) | **NOT RUN.** Blocked on headroom, not on HML |
| H3 (compiler feedback) | not started; deliberately deferred |

> **There is no valid HML-vs-SE reasoning result. Zero HML scientific model calls have ever
> been made.** Every model call in this project's history has been structured-English.

---

## C. Compiler state

Working and tested:

- **Evidence DAG** (`reasoning/evidence.py`, D-040) — explicit graph, cycle validator over
  all four edge kinds, ESTABLISHED / PROVISIONAL / NOT_EVIDENCE, invariants E1–E4, E7, E8.
- **Scoped Γ** (D-043) — `scope … end`; facts do not survive, precede, cross to siblings,
  or escape nesting. Local contradiction warned and contained, not banned.
- **Partiality** (D-044) — definedness is a property of **terms**, not rules. Closed a
  CRITICAL exploit where `multiply_both_sides(by := 1.0 / 0.0)` reached VERIFIED/PROVED.
- **Binder fix** (D-045) — D-006's shadowing rule no longer applies to binders, so
  `derivative(f, x)` works when `x` is declared.
- **Binder protocol** (D-046) — `binder_of` / `expr_children` / `BINDER_KINDS`; fixed
  `free_names` silently reporting no free variables inside integrals/derivatives/
  comprehensions.
- **Circular laws rejected** (D-042, `HML-S607`).

| metric | value |
|---|---|
| **FULL_LANGUAGE_COMPOSITION** | **22 / 48 strict = 0.458** (framework 22/38 = 0.579) |
| ontology | 486/486 classified; 64 critical → PASS 47, PARTIAL 15, LOSSY 2, ABSENT 0 |
| backend silent loss | 0 |
| v1 hash stability | preserved throughout |
| maturity | **LEVEL 1 — DOMAIN DSL** (unchanged) |

**Known critical blockers:** none currently open. One CRITICAL was found and fixed (D-044).
The full-ontology probe found **32 enforcement gaps, 7 critical**; **1 fixed** (`HML-T435`,
matrix shape conformance), **31 outstanding, 6 critical** — none audited for reachability.

**Intentionally unfinished:** extensibility (0/6 probed forms — nothing can be added
without compiler edits), certificates, approximation, indexed/range binders, the remaining
CONTRACTED operations (matrix inverse, indexing, normalisation, conditional probability,
expectation, argmin/argmax), 9 of 13 requested V2 docs, model guide, synthetic trajectory
generator, compiler exhaustion.

**D-041 must not be reopened without new falsifying evidence:** the generic
Apply/Bind/Attribute AST core is **rejected on measurement** — it reaches 0.563 alone,
*below* the Level 2 threshold, while targeted repairs reach 0.854.

---

## D. Experiment history — all structured English

| # | corpus | result |
|---|---|---|
| 1 | first reasoning benchmark | SE control ≈ **93%** → saturated, no signal |
| 2 | 24-task v1 benchmark | SE control **23/23 = 100%** → `HML_BENCHMARK_FAILED_NO_SIGNAL` |
| 3 | textbook-trap calibration | **10 valid / 10 correct**, 2 truncations excluded |
| 4 | synthetic state-complexity | **9 valid / 9 correct**, 0 truncations |

### Exact model-call accounting

| protocol | calls in JSON | actual calls | note |
|---|---|---|---|
| textbook calibration (CAL1–3) | 12 | **13** | one call consumed by a crashed run (`c.text` vs `c.content`) before the fix; not in any JSON |
| synthetic calibration (CAL-S1–S3) | 9 | **9** | |
| **total** | **21** | **22** | |
| **HML scientific calls** | — | **0** | |

### ⚠ Raw-data caveat a fresh context MUST NOT misread

`evaluation/calibration/results/CAL3.json` records `total=4, correct=2`. **Those two
failures are `finish_reason=length` at exactly 8192 tokens — truncation, not error.**
`cal3_floor_identity` was mid-way through a *correct* fractional-part argument when it ran
out. The JSON has **no truncation-aware `valid` field**; the exclusion lives only in
`docs/evaluation/SE_CALIBRATION_REPORT.md`.

Reading CAL3.json as "2/4 correct, headroom found" would be wrong and would send the
project down a dead end. The correct reading is **2 valid observations, 2 correct**.

(The newer `run_cal.py` records `valid` explicitly and never scores a truncated response.)

---

## E. Synthetic difficulty lab

`evaluation/h2/difficulty_lab/` — **all committed**, nothing withheld.

| file | sha256 (first 16) |
|---|---|
| `families.py` | `7c837f0af0e17bff` |
| `scorer.py` | `01ce7033a92dea13` |

- **Generators (4):** `ALGEBRAIC_DEPENDENCY_GRAPH`, `FINITE_LOGIC_WORLD`,
  `FINITE_QUANTIFIER_WORLD`, `MIXED_STATE_COMPOSITION`. Version
  `difficulty-lab-1.0.0`.
- **Neutrality:** structures generated in Python, English rendered *from* them. Never
  HML-first — a benchmark written in HML and translated would be native to HML by
  construction.
- **Levels:** L1–L7. L7 = 26 facts, depth 16, 6 distractors, 10 propositional variables.
- **Oracles:** exact `Fraction` arithmetic; exhaustive enumeration. No LLM judged anything.
- **Independent cross-checks:** 40/40 on algebraic and quantifier families, each
  **re-parsing the rendered English** through a second implementation, so a rendering bug
  surfaces rather than being mirrored.
- **Validation gate** (`validate.py`, ran before any model call): 119 instances/family,
  deterministic from seed, 0 duplicate prompts, non-degenerate answers.
- **Scorer** (`difficulty-lab-scorer-1.0.0`): reads only the declared `FINAL:` line;
  unparseable is wrong; 15 scorer + 5 extraction self-tests pass.
- **Seeds:** calibration uses `CALIBRATION_SEED_BASE = 900_000 + n`. Pilot tasks must draw
  from a disjoint band. **Calibration instances are permanently excluded from any pilot.**
- **Raw results:** `CAL_S1.json`, `CAL_S2_L5.json`, `CAL_S3_L7.json`, `VALIDATION.json`.
- **Runtime:** `gemma4:31b`, digest `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7`,
  temperature 0, 8192 completion allowance. Digest verified before every stage.

---

## F. Current conclusion — state this precisely

**SUPPORTED:**

> The current Gemma 31B saturates the tested state-complexity families. Across L3, L5 and
> L7, over four generator families, it answered 9/9 correctly with no truncation, using
> 900–2400 tokens of an 8192 allowance.

**NOT SUPPORTED — do not write or imply any of these:**

- HML has no effect.
- All difficulty axes are saturated.
- Smaller models would also saturate.
- Hard-single-step tasks would saturate.
- Next-action or error-detection representations show no effect.

**The strongest known limitation of the negative result:** the generator increased the
**number of easy steps**, not the **intrinsic difficulty of individual steps**. A depth-16
chain is tedious; each link is one multiply-add. No family was generated where a single
step is hard — non-linear systems, case-splitting search, problems with no forward-chaining
route. Also never generated: probability-with-dependence, geometry, multi-step optimisation.

**Structural tension to carry forward:** the families where this model is plausibly weak
(combinatorics 0%, asymptotics 0%, abstract algebra 5%, topology 10%) are the families where
**HML's own ontology coverage is near zero**. "Just use harder mathematics" collides with
this immediately.

---

## G. Strategic pivot

The recommended architecture is **no longer**:

> finish HML → find harder full maths → paired full-answer benchmark

It is now:

```
NEUTRAL SEMANTIC WORLD FACTORY
  → equivalent renderings:  Structured English | generic AST | HML
  → representation microbenchmarks:
       1. paired minimal contrasts
       2. next-action prediction
       3. semantic corruption / error detection
  → representation bottleneck swap, if signal exists
  → tiny train-from-scratch representation ablation, if justified
  → full H2 only after these
```

**A generic AST is now a REQUIRED control.** Without it, any benefit observed for HML could
be a benefit of *structure in general* rather than of HML specifically, and the project
would attribute it wrongly. This is the single most important methodological addition.

The existing `difficulty_lab` generators are the right substrate: they already produce
neutral semantic worlds with deterministic oracles, and only the *rendering* layer needs to
be added.

---

## H. Next experimental questions

1. Does HML improve **next-action prediction** relative to information-matched SE and
   generic AST?
2. Does HML improve **semantic sensitivity** on paired minimal contrasts?
3. Does HML improve **held-out corruption detection**, rather than merely exposing
   superficial syntax?
4. Is a correct HML state **more useful to a fresh solver** than an equivalent English or
   AST state?
5. Does HML improve **sample efficiency** in a tiny train-from-scratch model?

---

## I. Do NOT do yet

Broad compiler completion · grinding the 48 specimens purely for score · extensibility ·
certificate ecosystem · massive compiler exhaustion · a 100×64-generation confirmatory
benchmark · fine-tuning · agent gateway · MCTS · recursive language evolution.

---

## J. Exact next action

**Design and build the REPRESENTATION ARENA on top of the existing neutral semantic-world
generator** (`evaluation/h2/difficulty_lab/families.py`). Add a rendering layer emitting
three information-matched views of the *same* generated structure — structured English,
generic AST, HML — then implement the microbenchmarks in G.

**Do not make another Gemma 31B full-problem call first.**

---

## Key documents

| path | contents |
|---|---|
| `docs/hml_v2/CURRENT_TRUTH.md` | measured snapshot |
| `docs/evaluation/SE_CALIBRATION_REPORT.md` | protocol 3 + truncation analysis |
| `docs/evaluation/SYNTHETIC_CALIBRATION_REPORT.md` | protocol 4 + saturation analysis |
| `docs/hml_v2/COMPOSITIONALITY_STUDY.md` | 48-specimen study, AST fork evidence |
| `docs/hml_v2/ONTOLOGY_FULL_PROBE.md` | all 486 atoms |
| `docs/hml_v2/TRUSTED_RULE_CLASSIFICATION.md` | 16 rules, TCB ≈1423 lines |
| `docs/hml_v2/ARCHITECTURE_FREEZE.md` | D-034…D-039 |
| `docs/hml_v2/RED_TEAM_BASELINE.md`, `RED_TEAM_V2.md` | exploit registers |
| `DECISIONS.md` | D-040…D-046 are this session's; **note the ID-collision notice at the top** |

**`DECISIONS.md` has a known defect:** D-026, D-027 and D-028 each identify **two**
different decisions. A prominent notice at the top of the file gives the disambiguation
table. They were not renumbered because ~65 reference sites are ambiguous; renumbering had
a worse expected outcome than the collision.
