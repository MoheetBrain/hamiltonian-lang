# Mathematical-equivalence scoring

**Status:** implemented, measured, and gated by tests.
**Package:** `src/hamiltonian_lang/equivalence/`
**Benchmark:** `evaluation/m3/equivalence/`
**Tests:** `tests/equivalence/` — 239 tests
**Protocol version:** `hml-equivalence-1.0.0`

---

## 1. The defect this replaces

`CanonicalComparatorVerifier` compares two encodings by their canonical content
hash. That comparison is sound in **one** direction only:

| observation | what it actually licenses |
|---|---|
| hashes equal | the two are the same semantic object — sound |
| hashes differ | the two are *different objects* — **not** "the candidate is wrong" |

The second row was being read as wrongness. A mismatch landed in
`SUPPORTED_AND_FAILED` and classified `DISPROVED`.

Per CONF-003 in `docs/evaluation/CONSTITUTIONAL_INTEGRATION_DECISIONS.md`, that
reading is:

- **correct for ACQ0.** ACQ0 asks whether the model reproduced *the same canonical
  object*. Exact hash match **is** the definition of semantic preservation there,
  and a rephrasing that yields a different object genuinely failed the task.
- **wrong for H1/H2.** H1 and H2 ask whether the representation improved the
  *answer*. A mathematically equivalent encoding that hashes differently is not a
  wrong answer, and scoring it `DISPROVED` would systematically bias both
  hypotheses downward — against the project's own thesis.

This package is the "separate equivalence comparator" that CONF-003 names as a
prerequisite for M3. **It does not modify, wrap, or replace ACQ0's scoring in
`evaluation/syntax_gate/`**; that code is untouched, and
`tests/equivalence/test_isolation_and_adjudication.py` enforces the separation
mechanically by inspecting the import graph.

---

## 2. Two rules that shape every decision

### 2.1 No false-positive equivalences

A false positive silently declares a wrong answer right and corrupts every H1/H2
number computed from it. A false negative only costs coverage. **The errors are
not symmetric and are not traded off.** When in doubt the answer is
`INCONCLUSIVE`.

### 2.2 Unsupported and inconclusive are never failures

Converting "I could not tell" into "wrong" is the same defect being fixed, pointed
the other way. `status.NEGATIVE_STATUSES` contains exactly two members —
`VERIFIED_NONEQUIVALENT` and `COUNTEREXAMPLE_FOUND` — and an aggregate may read
only those as wrongness. `INCONCLUSIVE`, `UNSUPPORTED` and `SEMANTIC_LOSS` are
excluded by construction and are queued for adjudication rather than dropped.

---

## 3. The layers

```
TIER 0  exact canonical identity            certifies
GUARDS  invariant refutations               refutes only
TIER 1  alpha / binder-safe normalisation   certifies
TIER 2  trusted algebraic + symbolic        certifies and refutes
TIER 3  executable counterexample search    refutes only, NEVER certifies
TIER 4  endpoint answer verification        answers the endpoint question only
TIER 5  unresolved -> human adjudication    decides nothing
```

The scorer runs them cheapest-first and stops at the first decisive result.

### TIER 0 — exact canonical identity

`backends/canonical.py::content_hash`. Equal hashes issue a certificate. Unequal
hashes issue `INCONCLUSIVE` with the hashes as evidence, and the boolean is
surfaced separately as `ComparisonReport.exact_preservation` so ACQ0's endpoint
stays readable without being conflated with the equivalence verdict.

### GUARDS — the invariants an equivalence claim may never trade away

Guards run before the tiers, can only refute, and each is a sound argument rather
than a heuristic.

| guard | argument |
|---|---|
| `declared_types_incomparable` | no subtyping path in either direction, so the two do not denote the same set of values |
| `epistemic_kind_differs` | `Probability` / `PValue` / `PosteriorProbability` are the same subset of [0,1] and different epistemic objects (D-022); the type system admits no coercion either way |
| `dimension_differs` | different rational exponent vectors are different magnitudes |
| `random_variable_vs_value` | a `Distribution[T]` is not a `T`; a `RandomVariable[T]` is neither |
| `epistemic_role_differs` | `obs` is data and `param` is not; `assume` grants, `require` obliges, `prove` claims |
| `objective_direction_differs` | minimising and maximising are different problems |
| `conditioning_set_differs` | a conditional law and a marginal law are different objects |
| `quantifier_alternation_differs` | `exists y . forall x . P` entails `forall x . exists y . P` and not the converse |

Two safeguards keep the guards from inventing false negatives:

1. **A guard never fires on a guessed pairing.** Statements are paired by name,
   then by exact skeleton, then by uniqueness within a kind, and only then
   positionally. A residual inherits its pairing's confidence, and only the first
   three are trusted.
2. **The quantifier guard requires a dependence witness.** Before refuting on
   alternation it must exhibit, by sampling, two assignments differing only in one
   binder that give the body different truth values — for *each* binder. That is a
   proof of dependence, and it rules out the vacuous case
   (`forall x . exists y . x = x`) where the order cannot matter.

### TIER 1 — alpha-equivalence and binder-safe normalisation

Finds a bijection between the two modules' bound symbols making the trees
identical, with backtracking and skeleton-based pruning. Normalises:

- alpha-renaming of bound names;
- statement and declaration order (a module is a collection, not a script);
- the module's own name;
- associative/commutative regrouping of `+`, `*`, `and`, `or`, `iff` and the
  symmetric relations `=`, `!=`;
- the conditioning set of a law, which the canonical form already sorts.

Each of these is attached to the certificate as a tracked `Assumption`.

**Explicit refusals.** `^` is not associative and is never flattened. `implies`
is directional and is matched antecedent-to-antecedent. `-`, `/`, `@` and the
ordering relations are never reordered. Quantifier alternation is never permuted.

**The name lock.** When both modules declare the same module-level vocabulary, the
bijection must preserve those names. A candidate reusing the reference's own names
is using them as identities; without the lock, `prove p => q` and `prove q => p`
over two anonymous booleans are alpha-variants of one another, and the adversarial
pair the directive names would be certified equivalent. Locally bound names —
quantifier and parameter binders, at depth > 0 — stay freely renameable, which is
what alpha-equivalence actually means.

### TIER 2 — trusted algebraic and symbolic equivalence

Three decision procedures over SymPy 1.14.0, in one shared translation context so
that matched symbols on the two sides become the *same* SymPy symbol.

1. **Difference is zero.** `expand` then `simplify` of `a - b`. Covers commutative
   reordering, associative regrouping, constant folding, expansion and
   factorisation.
2. **Relations are proportional.** `l1 REL r1` and `l2 REL r2` describe the same
   set when `(l1-r1) = k*(l2-r2)` for a nonzero `k`. For an equality any nonzero
   `k` works; for an inequality the *sign* of `k` decides, and a negative `k`
   requires the operator to be mirrored. Strictness is never traded: `<` and `<=`
   stay different. When `k` is symbolic its sign is taken from the declared types
   and **recorded as a tracked assumption** — `a*x < 6` and `x < 6/a` are
   equivalent only when `a > 0`.
3. **Propositional validity.** `Equivalent(A, B)` through a SAT solver over shared
   atoms. The two directions are deliberately asymmetric:
   - an unsatisfiable negation **certifies**, soundly even when atoms are
     dependent, because propositional validity holds under every interpretation
     of the atoms;
   - a satisfying model **refutes only when every atom is a free boolean**. When
     an atom stands for a comparison, a model may set `x > 0` true and `x > -1`
     false — a world that does not exist — so the tier returns `INCONCLUSIVE`.

**Refusals.** Quantifiers, distribution laws, index expressions and `@` have no
faithful SymPy image and are refused with a `SemanticLossNote`, never
approximated. `sympy.Q` is a predicate namespace, not a binder; routing a
quantifier through it would erase nesting order.

**Division caveat.** SymPy evaluates `a/a` to `1` at construction, so the check for
a symbolic denominator runs on the **HML tree**, not on the translated expression.
Certifying `a/a == b/b` without recording "denominators are nonzero" would be an
equivalence that is false at zero.

### TIER 3 — executable counterexample search

Deterministic (`SEED = 20260805`); a scoring engine whose verdict depends on a
seed is not a measurement instrument. Sampling respects declared types — a
`Probability` never sees 1.7, a `PositiveReal` never sees 0 — and samples that
violate an `assume` statement are discarded rather than counted. `require` is
deliberately **not** used as a domain filter: it is an obligation, and letting a
candidate's own constraint hide its counterexample would be circular.

Values are drawn from a per-type grid augmented with **hints harvested from the
expressions themselves** — the constants that appear, plus solutions of any
equality, each filtered through `types.literal_inhabits`. Without hints, `2*x = 6`
and `x = 6` agree on every point of any reasonable default grid.

**The asymmetry is in the types.** The searcher returns
`Counterexample | NoRefutation`. `NoRefutation` is a different class with
`certifies_equivalence` hard-coded to `False`, its method id lives in
`SEARCH_ONLY_METHODS`, `Certificate.__post_init__` rejects it, and
`register_certifying_method` raises rather than admit it. `EquivalenceResult`
additionally refuses to attach a `NoRefutation` to a negative verdict, so "found
nothing" cannot support a verdict in *either* direction.

### TIER 4 — endpoint answer verification

`numeric` (relative tolerance), `exact` (symbolic), `set` (multiset). A match
yields `VERIFIED_CORRECT_ANSWER` and **never** `VERIFIED_EQUIVALENT`: two
encodings can reach the same number by different routes. An unparseable or missing
answer is `INCONCLUSIVE`, never wrong. Differing units are `INCONCLUSIVE` — this
tier has no unit algebra and declines rather than guesses.

### TIER 5 — adjudication

Everything undecided is queued as a serialisable `AdjudicationItem` carrying the
residuals that defeated the automation. An engine whose unresolved cases vanish is
an engine whose coverage cannot be measured.

---

## 4. Certification is compositional; refutation is not

The aligner descends into two places only — a matching quantifier prefix, and the
role arguments of a same-family distribution — and marks what it finds there as a
**fragment**.

- Certifying a fragment is sound: equal parts in identical contexts give equal
  wholes, and equivalent bodies give equivalent quantified formulas.
- **Refuting** from a fragment is not sound. `b - b` and `c - c` differ in every
  part and are both identically zero. `Residual.may_refute` is false for
  fragments, Tier 3 skips them, and a Tier 2 negative on a fragment is downgraded
  to undecided.

Everything else becomes one residual covering the whole statement-level
expression, which is also the form the symbolic tier handles best.

---

## 5. Endpoints

| endpoint | question | tiers consulted |
|---|---|---|
| `ACQ0_EXACT_PRESERVATION` | did the same canonical object come back? | Tier 0 only |
| `ENCODING_EQUIVALENCE` | do the two denote the same object? | 0, guards, 1, 2, 3 |
| `FINAL_ANSWER` | is the answer right? | as above, plus Tier 4 decides |

The ACQ0 mode exists so the difference is explicit and testable, not so ACQ0
starts using this engine. On the same equivalent-but-reshaped pair the two
endpoints must disagree — ACQ0 reports `exact_preservation = False` with status
`INCONCLUSIVE` (not a claim of mathematical error), while the encoding endpoint
certifies `VERIFIED_EQUIVALENT`. If those ever agree, the original defect is back.

---

## 6. Measured results

`evaluation/m3/equivalence/pairs.py` — 49 hand-labelled pairs across eight
categories. Reproduce with:

```bash
.venv/bin/python -m evaluation.m3.equivalence.run
```

| metric | measured |
|---|---|
| pairs | 49 |
| decided | 49 |
| **coverage** | **1.000** |
| **precision over decided pairs** | **1.000** |
| **equivalence precision** | **1.000** |
| **non-equivalence precision** | **1.000** |
| **false-positive equivalences** | **0** |
| false negatives | 0 |
| queued for adjudication | 0 |

By category — all `false_positive = 0`:

| category | n | decided | correct |
|---|---|---|---|
| identical | 4 | 4 | 4 |
| structurally_equivalent | 18 | 18 | 18 |
| near_miss | 7 | 7 | 7 |
| assumption_sensitive | 4 | 4 | 4 |
| scope_sensitive | 2 | 2 | 2 |
| dimension_sensitive | 3 | 3 | 3 |
| epistemic | 6 | 6 | 6 |
| adversarial | 5 | 5 | 5 |

Which tier decided each pair:

| tier | pairs |
|---|---|
| Tier 2 symbolic | 18 |
| guards | 12 |
| Tier 3 counterexample search | 9 |
| Tier 1 alpha normalisation | 7 |
| Tier 0 canonical identity | 3 |

The five adversarial pairs the directive names all come out non-equivalent:

| pair | decided by |
|---|---|
| `p => q` vs `q => p` | Tier 2 propositional countermodel |
| `forall x exists y` vs `exists y forall x` | guard, with dependence witnesses for both binders |
| p-value vs posterior probability | guard, epistemic kind |
| `(a^b)^c` vs `a^(b^c)` | Tier 3 counterexample |
| `x/y` vs `x*y` | Tier 3 counterexample |

The `(a^b)^c` case is not hypothetical: a renderer in this repository printed
`(a^b)^c` as `a^b^c`, which reads back as `a^(b^c)`. `equivalence/display.py`
therefore never elides a grouping, so an evidence string can be trusted to say
which tree was compared.

**Coverage is a property of this corpus, not of the world.** Coverage on real
H1/H2 model output will be lower, because that corpus contains constructs no tier
here can decide. The gate in `tests/equivalence/test_benchmark.py` pins coverage
at `>= 0.90` so a genuine improvement does not fail it and a real regression does;
precision is pinned at exactly 1.0.

---

## 7. Known limitations

1. **Quantified bodies that differ are undecidable here.** Under a matching prefix
   the bodies are a fragment, so they can be certified but never refuted; if Tier
   2 cannot discharge them the pair is `INCONCLUSIVE`. There is no first-order
   decision procedure in this engine.
2. **Quantifier alternation is treated as part of a proposition's identity.** Two
   differently-ordered statements that happen to have the same truth value in the
   intended model — for instance `forall x . exists y . (x = 0 or y = 0)` against
   its swap over the reals, both true — are reported non-equivalent. This is a
   deliberate false negative: it follows the project's own commitment to
   preserving quantifier order, and it errs in the direction that costs coverage
   rather than the direction that corrupts a number.
3. **The name lock costs coverage.** A candidate that reuses the reference's
   vocabulary but permutes two roles is refused at Tier 1 rather than certified.
   It then falls through to Tier 2 and Tier 3, so a genuinely equivalent
   permutation may end `INCONCLUSIVE`.
4. **`const` versus `param` is not refuted.** Both are deterministic and
   non-random; the difference is real but was judged too close to notation to
   refute on. It surfaces as a residual and usually ends undecided.
5. **Distribution families are never compared for equivalence.** `Beta(1,1)` and
   `Uniform(0,1)` are the same law; this engine does not know that and does not
   guess. A family difference is `INCONCLUSIVE`, not a refutation.
6. **No unit algebra.** Tier 4 declines rather than converts when the two answers
   carry different unit strings. Dimensional differences *inside* an encoding are
   caught by the dimension guard, which uses the compiler's exact exponent
   vectors.
7. **No Lean path certifies anything.** The Lean backend closes every obligation
   with `sorry` by design and `lean_verify` rejects it textually; Mathlib is
   absent. Nothing in this package consults Lean, and none of it should be
   described as toolchain-verified. `stanc` is likewise absent.
8. **SymPy's simplifier is incomplete.** A difference that does not simplify to
   zero is reported as `INCONCLUSIVE`, with that incompleteness stated in the
   detail string — it is never reported as evidence of difference.
9. **Expressions above 400 nodes are refused** rather than handed to `simplify`,
   which trades coverage for a bounded run time.
10. **Statement pairing is a heuristic below the top three confidence levels.** A
    positional pairing can misalign two same-kind statements. Guards never fire on
    such a pairing, so the failure mode is undecidedness, not a wrong verdict.

---

## 8. Contract for callers

```python
from hamiltonian_lang.equivalence import (
    EquivalenceScorer, Endpoint, EquivalenceStatus, NEGATIVE_STATUSES,
)

report = EquivalenceScorer().compare(
    reference_hml, candidate_hml, endpoint=Endpoint.ENCODING_EQUIVALENCE
)

# The ONLY correct way to read a negative:
wrong = report.status in NEGATIVE_STATUSES
```

Rules a caller must not break:

- Never treat `INCONCLUSIVE`, `UNSUPPORTED` or `SEMANTIC_LOSS` as wrong. Report
  them as undecided and quote `AdjudicationQueue` for the count.
- Never read `VERIFIED_CORRECT_ANSWER` as an equivalence claim.
- Never compute an H1 or H2 number from `CanonicalComparatorVerifier` alone; that
  is the CONF-003 prohibition and this package exists to satisfy it.
- Report precision and coverage separately. Merging them hides the only number the
  approval criterion binds.

---

## 9. Verification actually run

| command | result |
|---|---|
| `.venv/bin/ruff check src/hamiltonian_lang/equivalence evaluation/m3 tests/equivalence` | All checks passed |
| `.venv/bin/mypy src/hamiltonian_lang` | Success: no issues found in 64 source files |
| `.venv/bin/python -m pytest tests/equivalence` | 239 passed |
| `.venv/bin/python -m evaluation.m3.equivalence.run` | coverage 1.000, precision 1.000, 0 false positives |
