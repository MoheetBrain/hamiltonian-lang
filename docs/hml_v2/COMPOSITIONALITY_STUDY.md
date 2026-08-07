# HML v2 — compositionality failure study

**Status: measurement plus one architectural recommendation.** Every number below was
produced by compiling real HML through `hamiltonian_lang.compile_source` on the V2 tree.
No model was called. Nothing under `/Users/moheet/hml_audit_worktree` or
`/Users/moheet/hamiltonian_lang` was modified, and nothing under `src/` or `tests/` was
modified. The only new code is one file, `audit_rerun/probe_composition_48.py`.

| | |
|---|---|
| tree under test | `/Users/moheet/hml_v2_worktree/src` @ `34079d0` (D-025 · D-026 · D-027 · D-028) |
| src provenance | `git diff 0715bfc..34079d0 -- src/` is **empty** — `34079d0` (the D-034…D-039 freeze) and `e435c77` (the research-integration record) are docs and tests only — so every measurement here holds unchanged at the `0715bfc` base the brief named |
| concurrency note | a parallel workstream began editing `src/hamiltonian_lang/reasoning/check.py` and adding `reasoning/evidence.py` while this study was finishing. The suite was re-run against that working tree and **every figure below is identical**; the study is nevertheless anchored to committed `src/` @ `34079d0`, and should be re-run if the reasoning spine changes further |
| interpreter | `/Users/moheet/hml_v2_worktree/.venv/bin/python` (3.14.6) |
| specimens | `audit/language_comparison/ontology/COMPOSITION_TESTS.json` — 48, read-only |
| governing method | `audit/language_comparison/methodology/COMPOSITIONAL_CLOSURE_FRAMEWORK.md` |
| runner | `audit_rerun/probe_composition_48.py` (new) |
| raw results | `audit_rerun/results/COMPOSITION_48.json` |
| regression baseline | `.venv/bin/python -m pytest` → **6252 passed, 5 skipped, 7 xfailed, 7 xpassed in 43.99s** |

Reproduce with:

```bash
cd /Users/moheet/hml_v2_worktree && .venv/bin/python audit_rerun/probe_composition_48.py
```

Run twice; the figures are identical.

---

## 0. Headline

```
48 specimens executed, first time ever.

  compositional closure      20/48 = 0.417      (strict, 48 denominator)
                             20/38 = 0.526      (framework, 10 UNSUPPORTED excluded)
  silent composition loss    3     (CT-018, CT-022, CT-038)   -- must be 0 for Level 3

  failure class   GRAMMAR 14 · TYPE 8 · COMPILER 3 · CONSTRAINT 2 · SCOPE 1
  repair needed   LOCAL 12 · ONE_NODE 9 · GENERAL 7

FORK VERDICT: the AST is NOT the primary blocker. 21 of the 28 failures are closed
without touching `ast/nodes.py`, and the remaining 7 need two specific ADDITIONS
(abstraction, and a binder over statements) rather than a generic Apply/Bind/Attribute
core. Confidence ~0.75. Do not do the rewrite. Do adopt a generic binder PROTOCOL.
```

The legacy 13-probe measure was re-run at this SHA on the **unmodified** audit probes and
is **9/13 = 0.692**. `docs/hml_v2/AUDIT_RERUN.md` §4 records 8/13 = 0.615 for that same
reading at `f0e3340`, so D-028 moved the unmodified-probe figure 0.615 → 0.692 by fixing
`COMP.LOCAL_ASSUMPTION_IN_SCOPE`; `COMP.MATRIX_VALUED_RV` still fails, on the
Event/Proposition rule. The four residual failures are `QUANT_X_PROB`, `PROB_X_UNITS`,
`MATRIX_VALUED_RV`, `OBJECTIVE_OVER_PROBABILISTIC`.

**0.692 and 0.417 are not the same measurement and must never be compared as if they
were.** All thirteen legacy probes are two-atom pairs; none checks whether an accepted
encoding actually carried the specimen's facts; none has a negative control; and several
are three lines long. The 48 include triple and quadruple compositions, 16 specimens the
suite itself marks `adversarial`, 12 that predict a canonicalisation failure and 6 that
predict a backend failure; all of them are scored against 105 probes and 29 fact checks.

---

## 1. What the runner does, and why "it compiled" is not the result

`COMPOSITION_TESTS.json` states every specimen in prose and in standard notation and
supplies no encoding, deliberately (framework R6). That is why it had no runner: running
it requires somebody to *write* 48 HML encodings. This study is those encodings plus a
scoring harness.

Encoding policy, applied uniformly and visible in the runner:

* the most faithful form the language admits, not the form most likely to pass;
* where several encodings exist, the one preserving the most facts is primary and the
  rejected alternatives are kept as controls so their diagnostics are on the record;
* HML's own documented idioms are used (`param` + `prior` for a quantity that has a law
  and is used as a parameter, per `examples/statistics/bayesian_coin.hml`).

Each specimen carries three kinds of evidence:

1. **A primary encoding and an expectation** — what HML must do for the specimen to be
   scored as composing. `accept` for 47 of them; `reject` only for CT-038, whose encoded
   statement is mathematically false. Three *controls* are `reject` for the same reason
   (CT-014's out-of-range index, CT-022's cyclic model, CT-035's contradictory measure).
2. **Controls** — a second source whose verdict shows the primary's success is not
   vacuous. `log(sigma)` compiling proves nothing until `log(r)` for unconstrained `r` is
   refused. 57 controls, 55 of them gating; the two non-gating ones are marked
   `gate=False` and only illustrate a consequence. 105 probes are run in all.
3. **Fact checks** — mechanical assertions that the load-bearing fact survived into the
   *checked tree*: a rendered type, a canonical-hash inequality, a print/reparse hash
   equality, a declared backend loss. This is what separates `COMPOSES` from
   `COMPOSES_SILENT_LOSS`, and it is why CT-018 fails while compiling clean.

**The gate**: a specimen closes iff the primary matched, every fact held, and every gating
control matched. The adjudicated outcome label is recorded beside each specimen and the
runner cross-checks it against the gate; it reports
`gate/adjudication disagreements: none`, so no verdict in this document is editorial.

The runner also re-reads the read-only specimen file every run and cross-checks all 48 ids
and titles against its own copies (`specimen cross-check : 48/48 ids and titles agree`), so
this study cannot silently drift from the suite it claims to run.

### 1.1 Two rates, both reported

Per framework §6 the closure numerator is `|COMPOSES| + |REJECTED_CORRECT|` over
`attempted − UNSUPPORTED`. Both readings are given because the exclusion count is high:

| reading | value | what it means |
|---|---|---|
| strict | **20/48 = 0.417** | every specimen counts; missing an atom is a failure |
| framework | **20/38 = 0.526** | the 10 specimens whose atoms HML lacks entirely are excluded |

Framework §7 warns that "a high closure rate over few attempted specimens is not a strong
result". 10 exclusions out of 48 is 21%, so the framework figure is the weaker of the two
and the strict figure is the one to plan against. Neither reaches the Level 2 threshold
of 0.70, and neither is close to the programme target of 0.85.

There are **zero** `REJECTED_CORRECT` outcomes. In every case where HML refused something,
the mathematics being refused was valid. That is a finding in itself: the suite contains
no specimen HML refuses *because the specimen is wrong*.

---

## 2. The 48-specimen result table

`closes` is the mechanical gate. `class` is the adjudicated cause of failure, one per
specimen. `repair` is what it would take to close it (defined in §4).

| id | title | closes | outcome | class | repair | first diagnostic, or why it failed the gate |
|---|---|:---:|---|---|---|---|
| CT-001 | quantifier over a family of random variables | n | UNSUPPORTED | GRAMMAR | GENERAL | HML-P204: unexpected '~' after require |
| CT-002 | quantifier over matrices with a shape hypothesis | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-003 | quantifier over a dimensionful domain | n | REJECTED_SPURIOUS | TYPE | LOCAL | HML-T427: the argument of sqrt has the wrong type |
| CT-004 | distribution parameters carrying units | n | REJECTED_SPURIOUS | TYPE | LOCAL | HML-T413: the 'location' role of Normal requires Real |
| CT-005 | minimising an expectation | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-006 | matrix with a symbolic structural constraint | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-007 | a function whose value is a distribution | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-008 | indexed family of RVs with index-dependent parameters | n | UNSUPPORTED | GRAMMAR | GENERAL | HML-P204: unexpected '~' after require |
| CT-009 | gradient of an expectation whose measure depends on the parameter | n | REJECTED_SPURIOUS | SCOPE | GENERAL | HML-N302: 'theta' shadows an outer binding and would silently change scope |
| CT-010 | definite integral carrying units | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-011 | local assumption inside a function body | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-012 | constraint scoped to a subset of an index set | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-013 | objective over derived state | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-014 | tensor appearing inside a proposition | n | COMPOSES_DEGRADED | COMPILER | LOCAL | compiles clean; control failed: a literal index outside the declared extent |
| CT-015 | quantifier alternation order: uniform versus pointwise | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-016 | approximate value inside a proof obligation | n | UNSUPPORTED | GRAMMAR | ONE_NODE | HML-P204: unexpected '~' after assume |
| CT-017 | matrix-valued random variable with a structural constraint | n | UNSUPPORTED | TYPE | LOCAL | HML-T412: unknown distribution family 'InverseWishart' |
| CT-018 | conditional expectation given a sigma-algebra | n | COMPOSES_SILENT_LOSS | TYPE | LOCAL | compiles clean; fact check failed: E[X \| G] must be a G-measurable RANDOM VARIABLE, not a value |
| CT-019 | piecewise function with a domain partition | n | UNSUPPORTED | GRAMMAR | ONE_NODE | HML-P204: unexpected 'x' after definition |
| CT-020 | statement quantifying over functions | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-021 | probability of a quantified event | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-022 | hierarchical model with an acyclic dependency structure | n | COMPOSES_SILENT_LOSS | COMPILER | LOCAL | compiles clean; control failed: a CYCLIC variant must be rejected |
| CT-023 | conditioning versus intervening | n | UNSUPPORTED | GRAMMAR | ONE_NODE | HML-N306: 'do' is not a known function |
| CT-024 | chance constraint | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-025 | robust minimax with alternating quantifiers | n | UNSUPPORTED | GRAMMAR | GENERAL | HML-P231: expected an expression, found 'maximise' |
| CT-026 | unit-carrying derivative in a differential equation | n | COMPOSES_DEGRADED | GRAMMAR | LOCAL | compiles clean; control failed: the initial condition x(0) = 3 m |
| CT-027 | non-commutative matrix product under a transformation | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-028 | density with reciprocal units | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-029 | sum over an index of a unitful family | n | COMPOSES_DEGRADED | GRAMMAR | ONE_NODE | compiles clean; control failed: an indexed summation with an explicit binder |
| CT-030 | log-likelihood as a product over independent observations | n | UNSUPPORTED | GRAMMAR | ONE_NODE | HML-P201: expected ')' to close the arguments of 'prod' |
| CT-031 | argmax over a constrained parameter space | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-032 | confidence interval as a statement about a random interval | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-033 | expectation of a matrix-valued function of a random vector | n | REJECTED_SPURIOUS | TYPE | LOCAL | HML-T427: transpose requires a matrix |
| CT-034 | transformation of a random variable with a Jacobian factor | n | REJECTED_SPURIOUS | GRAMMAR | GENERAL | HML-T470: 'J' is not callable |
| CT-035 | almost-everywhere qualifier surviving a transformation | n | COMPOSES_DEGRADED | CONSTRAINT | ONE_NODE | compiles clean; control failed: the declared 'measure' is an arbitrary set function |
| CT-036 | Taylor expansion with an explicit remainder | n | REJECTED_SPURIOUS | GRAMMAR | GENERAL | HML-T470: 'fp' is not callable |
| CT-037 | series rearrangement blocked by conditional convergence | n | UNSUPPORTED | GRAMMAR | ONE_NODE | HML-P201: expected ')' to close the arguments of 'sum' |
| CT-038 | simplification that narrows the domain | n | COMPOSES_SILENT_LOSS | CONSTRAINT | LOCAL | compiles clean, but the encoded statement is FALSE and had to be refused |
| CT-039 | mixed-unit state vector | n | UNSUPPORTED | TYPE | LOCAL | HML-T435: '@' requires matrix or vector operands |
| CT-040 | dimensionless argument requirement inside a model | n | REJECTED_SPURIOUS | TYPE | LOCAL | HML-T427: the argument of log has the wrong type |
| CT-041 | assumption discharged by a refinement carried through a call | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-042 | epistemic status preserved through a derivation | n | COMPOSES_DEGRADED | GRAMMAR | ONE_NODE | compiles clean; control failed: an APPROXIMATE step cannot be marked at all |
| CT-043 | translation to a backend that lacks a constraint | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-044 | round trip through the printer with a qualifier | n | COMPOSES_DEGRADED | GRAMMAR | ONE_NODE | compiles clean; control failed: an approximation marker to round-trip |
| CT-045 | capture-avoiding substitution under two binders | n | REJECTED_SPURIOUS | COMPILER | LOCAL | HML-R706: the stated conclusion is not what 'substitute' yields |
| CT-046 | optimisation over a distribution | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-047 | sup versus max in an optimisation conclusion | **Y** | COMPOSES | — | — | compiles clean; every control and fact check held |
| CT-048 | triple composition: quantifier, units and a random variable | n | REJECTED_SPURIOUS | TYPE | GENERAL | HML-D502: cannot compare quantities with different dimensions |

Full encodings, controls, fact checks and complete diagnostics for every row are in
`audit_rerun/results/COMPOSITION_48.json`.

### 2.1 What composes, stated plainly

Twenty specimens close, and several of them are things a mathematical IR routinely gets
wrong:

* **Quantifier order is structural** (CT-015). Uniform and pointwise continuity, four
  binders deep, have different content hashes, and consistent alpha-renaming leaves the
  hash unchanged. Nothing sorts or hoists binders anywhere.
* **The Event / Proposition barrier does real work** (CT-021, CT-024, CT-032). The
  textbook misreading of a confidence interval — `probability(l <= theta and theta <= u)`
  over fixed endpoints — is a *type error* (`HML-T482`), not a footnote. The silent
  replacement of a chance constraint by a scenario constraint is refused by the same rule.
* **The unit calculus composes with the analysis binders** (CT-010, CT-026, CT-028). A
  derivative divides by the binder's dimension and an integral multiplies by it, and the
  checker enforces it: claiming `∫P(t)dt` is still in watts produces `HML-D502`.
* **Backend loss is declared structurally** (CT-043). Stan reports
  `[dropped] require ... Stan cannot state a hard constraint on parameters` and
  `[weakened] sigma ... PositiveReal is open at 0 but Stan's <lower=0> is a closed bound`,
  as machine-readable `Unsupported` records with a severity, and `faithful` is `False`.
* **D-028 works** (CT-011, CT-041). A refinement crosses an application boundary,
  discharges the precondition, leaves no residue, and does not over-discharge. This
  specimen's ancestor `COMP.LOCAL_ASSUMPTION_IN_SCOPE` is recorded as a failure in
  `AUDIT_RERUN.md` §4 and now passes.
* **Set comprehension did the work of two missing primitives** (CT-031, CT-047). There is
  no `argmax` and no `inf`, but the set of maximisers and the set of lower bounds are both
  directly definable, and the comprehension encoding has the property the specimens
  actually test: it does not assert uniqueness, and it does not assert attainment.

That last point matters for the fork: a *general* form (comprehension) closed two
specimens that a bespoke `argmax` node and a bespoke `infimum` node would have closed. It
is the only place in the suite where generality paid off, and it is worth exactly two
specimens.

---

## 3. Failure classification, with the diagnostics

Twenty-eight specimens fail. Exactly one class each, chosen by the *actual* cause rather
than by where the diagnostic happens to fire.

| class | n | specimens |
|---|---:|---|
| GRAMMAR | 14 | CT-001, 008, 016, 019, 023, 025, 026, 029, 030, 034, 036, 037, 042, 044 |
| TYPE | 8 | CT-003, 004, 017, 018, 033, 039, 040, 048 |
| COMPILER | 3 | CT-014, 022, 045 |
| CONSTRAINT | 2 | CT-035, 038 |
| SCOPE | 1 | CT-009 |
| CANONICAL | 0 | — |
| BACKEND | 0 | — |
| SPECIMEN | 0 | — |

**No specimen was classed SPECIMEN.** All 48 are mathematically sound statements a working
practitioner would write, and none tests something HML deliberately refuses. The class was
available and was not used; that is stated so its absence is not read as an oversight.

**No specimen was classed CANONICAL, against 12 predicted.** `expected_failure_modes`
names `CANONICALIZATION` for CT-009, 013, 015, 016, 025, 027, 030, 035, 036, 037, 038 and
044; not one of them failed there. Every canonicalisation trap the suite sets —
quantifier alternation (CT-015), matrix non-commutativity (CT-027), guard hoisting
(CT-012), tensor index order (CT-014), divergence argument order (CT-046), round-tripping
three binder kinds (CT-044) — was survived. The canonical form is the strongest part of
this compiler and it is not implicated in a single failure.

**No specimen was classed BACKEND, against 6 predicted** (CT-006, 009, 017, 024, 034,
043). The one specimen that tests translation loss directly (CT-043) passes on three
backends at once.

### 3.1 `prediction_accuracy` — the framework predicted the wrong layer

Framework §6 asks for `prediction_accuracy`, which scores the *framework*, not HML.
Computed over the 28 failures with this mapping — `GRAMMAR→GRAMMAR`,
`TYPE→TYPE_SYSTEM`, `SCOPE→SEMANTIC_MODEL`, `CONSTRAINT→SEMANTIC_MODEL`,
`COMPILER→COMPILER`, `BACKEND→BACKEND`, plus `UNSUPPORTED` accepted as a hit for any
specimen scored `UNSUPPORTED`:

```
prediction_accuracy (scores the FRAMEWORK, not HML): 13/28 = 0.464
```

The mapping and the full miss list are in the runner (`SURFACE_MAP`,
`prediction_accuracy()`) and in the emitted JSON, so the figure is reproduced by the same
command as everything else rather than computed by hand.

The miss pattern is not noise. **Thirteen of the fifteen misses are specimens the
framework predicted would fail at `SEMANTIC_MODEL`, `TYPE_SYSTEM` or `CANONICALIZATION`
and which HML instead failed at `GRAMMAR`** — CT-001, 008, 016, 019, 025, 026, 029, 030,
034, 036, 037, 042, 044. HML fails *earlier* than the framework expected: at the point of
writing the sentence, not at the point of checking it.

That is a substantive finding and it cuts in HML's favour, because a construct that has no
surface form is cheaper and safer to add than a semantic model that quietly stores the
wrong thing. It is also the single strongest piece of evidence for §7: the framework's
authors predicted a *representation* problem across the board and measured a *vocabulary*
problem. Under framework §6 a low `prediction_accuracy` is grounds for revising the
specimens' `expected_failure_modes`; the more useful reading here is that the prediction
was calibrated on systems whose grammar is permissive and whose checking is weak, which is
the opposite of HML's shape.

### 3.2 The three silent losses — the ones that matter most

Framework §6: `silent_composition_loss_count` **must be 0** for Level 3. It is 3.

**CT-018 — `E[X | 𝒢]` is typed as a value.** Compiles clean; the fact check fails.

```hml
module CT018
rv X : RandomVariable[Real]
var G : Set[Set[Real]]
def c := expectation(X | G)
```

`c` renders as `Real`. So does `expectation(X)` with no conditioning at all. But
`E[X | 𝒢]` is the almost-surely unique 𝒢-measurable **random variable** whose integral
agrees with X's on every set in 𝒢. The moment rule in
`src/hamiltonian_lang/ast/nodes.py::MomentExpr` states it deliberately: "Conditioning on
something non-random — a parameter — yields a value again". That is right for a parameter
and wrong for a σ-algebra, and nothing distinguishes the two because there is no
σ-algebra type. `expectation(X | Y)` for a random `Y` does correctly give
`RandomVariable[Real]`, so the rule is half right; the half that is wrong produces a clean
compile with a wrong type, which every downstream consumer reads.

**CT-022 — no acyclicity check exists.** The hierarchical model compiles, and so does this:

```hml
module CT022b
param a : Real
param b : Real
prior a ~ Normal(location := b, scale := 1.0)
prior b ~ Normal(location := a, scale := 1.0)
```

`ok=True`, no diagnostics. The specimen names rejecting a cyclic variant as its
requirement. The dependency edges are already in `LawStmt.given` and in the `DistExpr`
role arguments — this is a missing pass, not a missing representation.

**CT-038 — division raises no definedness obligation.**

```hml
module CT038
var x : Real
require ((x * x - 1.0) / (x - 1.0)) = (x + 1.0)
```

`ok=True`. The statement is false at `x = 1`. The only obligation recorded is the generic
`constraint:(x * x - 1.0) / (x - 1.0) = x + 1.0` for the whole `require`. `log` and `sqrt`
get partial-definedness enforcement free from their domain types (`PositiveReal`,
`NonNegativeReal`); `/` gets none. HML never *performs* the unsound simplification — it
does no rewriting at all — but it will accept the unsound conclusion if a model writes it,
which for a reasoning IR is the same exposure.

### 3.3 The load-bearing walls, with their diagnostics

**Wall 1 — a `law` cannot sit under a binder.** CT-001, CT-008, CT-048; 3 specimens.

```hml
require forall i : Natural . X[i] ~ Normal(location := mu, scale := sigma)
```
```
error HML-P204: unexpected '~' after require
```

The family itself is fine: `var X : Vector[RandomVariable[Real], N]` indexes, `X[i]`
yields `RandomVariable[Real]`, `probability(exists i : Natural . X[i] > t) <= alpha`
compiles clean and the quantified body is correctly classified as an `Event`. What is
missing is that `law`/`prior`/`likelihood` are **statements** and `forall` is an
**expression**, and statements do not nest under expression binders. `law X[i] ~ ...` is
refused at the parser too: the target must be a bare identifier (`HML-P208`). Indexed
families of random variables — the basis of every hierarchical model and every stochastic
process — are therefore unwritable in HML.

**Wall 2 — a binding expression is a value, never a function.** CT-034, CT-036, and half
of CT-026; 3 specimens.

```hml
def J := derivative(ginv(u), u : Real)
def fY(y : Real) : NonNegativeReal := fX(ginv(y)) * abs(J(y))
```
```
error HML-T470: 'J' is not callable
  note: 'J' binds a value, not a function (defined at line 4)
  note: a definition with no parameter list is a value; applying it is a category error
```

`derivative(body, x : T)` binds `x` and immediately discharges the binder into a value of
the body's type. There is no abstraction form anywhere in the language — no lambda, and no
way to read a binding expression as a function — so **there is no derivative-at-a-point in
HML**. Change of variables with a Jacobian, `f'(a)` in a Taylor expansion, and an initial
condition on an ODE are all blocked by this one fact.

**Wall 3 — you cannot differentiate with respect to a symbol that exists.** CT-009.

```hml
param theta : Real
def obj := derivative(expectation(f(Z)), theta : Real)
```
```
error HML-N302: 'theta' shadows an outer binding and would silently change scope
  note: shadowing is rejected by design decision D-006
```

The only accepted spelling binds a fresh name — `derivative(expectation(f(Z)), th : Real)`
— which compiles clean and states the derivative of a constant, because `th` occurs
nowhere in the body. Nothing warns. `∇_θ E_{Z ~ q_θ}[f(Z)]`, the object at the centre of
variational inference and policy gradients, is either a scope error or silently vacuous.
This is the sharpest measured case of the binder *design* being the obstacle: the type
rules are not involved at all.

**Wall 4 — `RandomVariable` does not compose with `Quantity`.** CT-004, CT-048.

```hml
param mu : Quantity[Length]
param sigma : Quantity[Length]
rv H : RandomVariable[Quantity[Length]]
law H ~ Normal(location := mu, scale := sigma)
```
```
error HML-T413: the 'location' role of Normal requires Real          found: Quantity[Length]
error HML-T413: the 'scale' role of Normal requires PositiveReal     found: Quantity[Length]
error HML-T411: the support of Normal does not inhabit the declared type of 'H'
```

`DistributionSpec` fixes every family's support and role types to unrefined scalars, with
no dimension variable. A measured height in metres — the framework's own worked example
in §1 of the closure document — cannot be given a law. `AUDIT_RERUN.md` §4 already flagged
this as `COMP.PROB_X_UNITS`; D-026 and D-028 did not address it and it is unchanged.

**Wall 5 — the refinement environment refines symbols, not expressions.** CT-019, CT-035,
CT-038, CT-040.

```hml
require forall u : Real . u > 0.0 => f(u) = log(u)      -- HML-T427
assume d / d0 > 0.0
def eta := log(d / d0)                                   -- HML-T427
```

D-028's `RefinementEnv` is keyed on `SymbolId`. A module-level `assume r > 0.0` on a bare
reference narrows `r` and discharges `log`'s obligation (CT-011, CT-041 — both pass). An
implication's antecedent introduces no hypothesis, and a compound expression cannot be
refined at all. CT-040 is the crispest consequence: the specimen states that `log(d/d0)`
**is** well formed and `log(d)` is not. HML refuses both, because `Quantity/Quantity`
cancels to the unrefined scalar `Real` and `log` demands `PositiveReal`.

**Wall 6 — the surface has no summation binder, no conditional, no approximation marker,
no intervention operator, no a.e. qualifier, no unit-carrying literal.** CT-016, CT-019,
CT-023, CT-029, CT-030, CT-035, CT-037, CT-042, CT-044; 9 specimens, all of them a single
missing keyword-headed form. These are exactly the shape of thing D-026 added eleven of in
one commit.

---

## 4. The repair taxonomy — counted, not asserted

Each of the 28 failures carries a `repair` label in the runner, so the fork argument below
is arithmetic over data rather than an opinion.

| repair | n | definition |
|---|---:|---|
| `LOCAL` | 12 | one builtin signature, one type rule, one registry entry, or one checker pass. **No change to `ast/nodes.py`.** |
| `ONE_NODE` | 9 | one more bespoke expression or statement form closes it, exactly the way D-026 closed eleven at once. |
| `GENERAL` | 7 | needs a capability the current AST cannot express at all. |

**`LOCAL` — 12 specimens, no AST change:**

| id | the repair |
|---|---|
| CT-003 | a `Quantity` overload for `sqrt` halving the dimension exponents (`Dimension` already stores `Fraction` exponents), plus a unit-carrying literal |
| CT-004 | make `DistributionSpec` dimension-parametric: one dimension variable on the support and the location/scale roles |
| CT-014 | range-check literal indices against the declared extents — the extents are already in the type |
| CT-017 | one matrix-supported family in the registry, with a support constraint |
| CT-018 | a σ-algebra type in `types.py` and one clause in the moment rule |
| CT-022 | one acyclicity pass over the law graph |
| CT-026 | a unit-carrying literal |
| CT-033 | one vector case in the `transpose` signature |
| CT-038 | raise a definedness obligation for `/` |
| CT-039 | per-component element types in the aggregate type constructors |
| CT-040 | preserve the positivity refinement when a `Quantity` ratio cancels |
| CT-045 | capture-avoiding substitution in the kernel — D-006's no-shadowing rule already guarantees the precondition, so this is an algorithm to write, not a representation to invent |

**`ONE_NODE` — 9 specimens, ~5 new forms:** an approximation marker (closes CT-016,
CT-042, CT-044 together), a conditional expression (CT-019), an intervention operator
(CT-023), an indexed summation/product binder (CT-029, CT-030), an a.e. qualifier plus a
`Measure` type (CT-035), a series form with a convergence predicate (CT-037).

**`GENERAL` — 7 specimens, and they reduce to exactly two missing things:**

* **abstraction** — the ability to read a binding expression as a function and apply it:
  CT-034, CT-036, CT-009 (and the second half of CT-026);
* **a binder over statements** — `for each i : T`, or making `law` an expression:
  CT-001, CT-008, CT-048, CT-025 (`minimise`/`maximise` are statements and cannot nest).

That is the whole of what the 48 specimens demand beyond the current design. **Neither is
Apply/Bind/Attribute.** Both are *additions* to the existing AST.

### 4.1 Six of the 28 are already targeted by the D-034…D-039 freeze

`34079d0` landed while this study was running and froze six architectural decisions
(`docs/hml_v2/ARCHITECTURE_FREEZE.md`). It explicitly defers the AST fork to this study —
"Whether the AST needs a generic Apply/Bind/Attribute core … is step 5's fork and is being
measured, not assumed" — and every decision in it is written to hold under either answer.
Read against this measurement, the freeze already commits to closing six specimens, and
**not one of them needs the generic core**:

| specimen | frozen decision | repair label here |
|---|---|---|
| CT-038 division raises no obligation | **D-036** — division is `CONTRACTED`, "always generates its obligation" | `LOCAL` |
| CT-014 literal index unchecked | **D-036** — indexing is `CONTRACTED` (`0 <= i < n`) | `LOCAL` |
| CT-016 / CT-042 / CT-044 no approximation marker | **D-037** — `approx(a, b, bound := eps)`, distinct canonical identity, no coercion | `ONE_NODE` |
| CT-019 branch guard is not a hypothesis | **D-035** — Γ becomes a stack of frames; a guard introduces a frame fact | `ONE_NODE` (the conditional form) + `LOCAL` (the Γ frame) |

That is 20 + 6 = **26/48 = 0.542** from the freeze alone, if it is implemented as
specified. D-036's diagnosis — "two policies and no principle distinguishing them" — is
independently confirmed here by CT-038's clean compile of a false statement.

Two of my failures are adjacent to the freeze but **not** covered by it, and should be
picked up: **CT-040** (a `Quantity` ratio that cancels to `Real` loses its positivity
refinement, so the specimen's well-formed `log(d/d0)` is refused) is a lattice question
D-035 does not reach, and **CT-018** (`E[X | 𝒢]` typed as a value) needs a σ-algebra type
that no frozen decision mentions.

One correction to a figure in the adjacent step's write-up:
`docs/hml_v2/RESEARCH_INTEGRATION_DECISIONS.md` §6 records "13 expression node classes".
Counted by reflection over `hamiltonian_lang.ast.nodes` at this SHA, `Expr` has **21**
concrete subclasses and `Statement` has **15**; the `symbol_id` count of 12 in that
section is correct. The higher node count strengthens rather than weakens that section's
`DEFER`: it is a larger surface to rewrite, not a smaller one.

---

## 5. The duplication measurement

The fork's strongest argument is that five bespoke binder classes mean the binding logic is
written five times in every consumer. That is measurable, so it was measured, over
`src/hamiltonian_lang/` excluding `v1/` and `ast/nodes.py`, by parsing every module and
counting `isinstance(_, <NodeClass>)` dispatch sites.

```
expression node kinds (Expr subclasses)          21
statement node kinds (Statement subclasses)      15
binder kinds (BINDING_EXPRESSIONS)                5

total expression-kind dispatch sites            413
  of which on the five binder kinds              79
    Quantifier 29 · LimitExpr 13 · DerivativeExpr 13 · IntegralExpr 12 · SetComprehension 12

lines occupied by `if isinstance(e, <binder>):` branches   298
files naming at least one binder kind                       17
  handling ALL FIVE                                         10
  handling ONLY Quantifier                                   7
```

The ten that handle all five: `semantics/__init__.py` (56 lines), `backends/canonical.py`
(44), `backends/english.py` (35), `backends/lean.py` (31), `type_system/__init__.py` (27),
`backends/latex.py` (21), `graph/__init__.py` (21), `backends/hml.py` (20),
`backends/sympy.py` (10), `backends/stan.py` (9).

So: **adding one binder costs ten edit sites in practice and seventeen in principle** —
ten is what D-026 actually paid, and §5.1 is the bill for the other seven. The resolver's
own comment says as much: the new branches do "exactly what the Quantifier branch above
does, deliberately by the same code shape". The comment is honest, and the cost is real.

Reproduce the counts with:

```bash
cd /Users/moheet/hml_v2_worktree && .venv/bin/python - <<'PY'
import ast, pathlib, collections
BIND = {"Quantifier","SetComprehension","LimitExpr","DerivativeExpr","IntegralExpr"}
per, sites, lines = collections.defaultdict(set), collections.Counter(), collections.Counter()
for f in pathlib.Path("src/hamiltonian_lang").rglob("*.py"):
    if f.name == "nodes.py" or "/v1/" in str(f): continue
    t = ast.parse(f.read_text()); k = str(f)
    for n in ast.walk(t):
        if isinstance(n, ast.Call) and getattr(n.func,"id","")=="isinstance" and len(n.args)==2:
            a = n.args[1]
            for x in (a.elts if isinstance(a, ast.Tuple) else [a]):
                if isinstance(x, ast.Name) and x.id in BIND: per[k].add(x.id); sites[x.id]+=1
        if isinstance(n, ast.If):
            c = n.test
            if (isinstance(c, ast.Call) and getattr(c.func,"id","")=="isinstance"
                    and isinstance(c.args[1], ast.Name) and c.args[1].id in BIND):
                lines[k] += n.end_lineno - n.lineno + 1
print(dict(sites), sum(sites.values()), sum(lines.values()), len(per),
      sum(1 for v in per.values() if len(v)==5), sum(1 for v in per.values() if v=={"Quantifier"}))
PY
```

### 5.1 The consequence is already visible, and it is a defect

Seven files handle `Quantifier` and **not** the four binders D-026 added:
`equivalence/display.py`, `equivalence/guards.py`, `equivalence/matching.py`,
`equivalence/sympy_bridge.py`, `reasoning/kernel.py`,
`verification/obligations/checkers.py`, `verification/obligations/evaluate.py`.

All seven dispatch by whitelist with a silent fall-through, so the omission is invisible.
It is not harmless. `verification/obligations/evaluate.py::free_names` removes a
quantifier's binder from the free set and has no branch for the other four:

```python
if isinstance(e, Quantifier):
    walk(e.body, scope | {e.var}, depth + 1)
    return
```

Measured directly:

```
free_names( integral(y, x : Real, 0.0, 1.0) > 0.0 )  ->  []       # y IS free
free_names( forall x : Real . y > x )                ->  ['y']    # correct
free_names( S = {x : Real | x > y} )                 ->  ['S']    # y IS free
free_names( y > 0.0 )                                ->  ['y']    # correct
```

`free_names` **under-reports free variables** under an `IntegralExpr` or a
`SetComprehension`. Today this causes no unsound discharge, because `evaluate` raises
`Undecidable` on those node kinds for an unrelated reason and the obligation engine
reports `UNSUPPORTED` for both cases (verified). The defect is therefore latent, not
active — but it is a real defect, it was introduced by D-026 in the commit before last,
and it is precisely the class of bug a generic binder representation removes by
construction. It is out of scope for this study to fix (`src/` is read-only here) and it
should be filed.

**This is the honest case for the fork, and it is a good one.** It is also, as §7 argues,
not a case for replacing the IR.

---

## 6. What a generic core would cost

### 6.1 Token and grammar cost

The generic core is an *internal* question; the keyword-led surface can survive as sugar
that elaborates into it. If it does, the token cost is exactly zero and the LLM-writability
argument is neutral. If the surface genericises too, it is not neutral. Measured with the
project's own lexer over six representative statements:

| form | current tokens | current chars | generic-surface tokens | generic-surface chars |
|---|---:|---:|---:|---:|
| `expectation(X \| Y)` | 9 | 27 | 15 | 48 |
| `integral(f(t), t : Real, 0.0, 1.0)` | 18 | 43 | 29 | 78 |
| `{x : Real \| x > 0.0}` | 12 | 29 | 20 | 54 |
| `forall x : Real . x > 0.0` | 9 | 33 | 18 | 54 |
| `law y \| x ~ Normal(location := mu, scale := sigma)` | 15 | 50 | 27 | 90 |
| `derive d1 : y = 2.0 * x from a1 by multiply_both_sides(by := 2.0)` | 17 | 65 | 26 | 92 |
| **total** | **80** | **247** | **135** | **416** |

**×1.69 tokens, ×1.68 characters.** The directive that produced V2 optimises explicitly for
LLM writability and against compiler complexity; a generic surface trades the first away to
buy the second. Keeping the sugar avoids that trade but does not avoid the costs below.

### 6.2 Canonical identity

`backends/canonical.py` carries `CANONICAL_VERSION = "hml-canonical-0.1.0"` and
`CANONICAL_VERSION_V2 = "hml-canonical-0.2.0"`, switched by `uses_v2(module)`. That whole
mechanism exists for one reason (directive §28): a v1 module must serialise
byte-identically to the way it did before V2 existed, so historical ACQ0/H2 evidence stays
reconstructible.

A generic core changes every node's `"kind"` string and every node's field layout. **Every
content hash changes — v1 and v2 alike.** The `uses_v2` switch cannot protect v1 identity
because v1's own nodes would be re-encoded. Preserving the evidence would require a
v1-shaped canonical projection maintained *alongside* the core one, with a proof that they
agree — that is, keeping the thing the rewrite was supposed to delete. `pytest` currently
reports 6252 passing tests, including
`tests/adversarial/test_alpha_equivalence.py` (9 hash-identity properties) and the eight
canonical fixtures under `examples/ir/`; all of them would need regenerating, which means
none of them would be a regression test across the change.

### 6.3 Alpha-equivalence

This one improves. One `Bind` node means one alpha rule, and `SymbolId.canonical()`'s
locally-nameless `#depth.ordinal` scheme is already binder-agnostic. Alpha-equivalence is
the *only* item on this list where the generic core is strictly better.

### 6.4 The RV / Distribution / value barriers

These are the product (CLAUDE.md rule 9: "rejection is the product"). They live in
`types.py` and in 53 `HML-T*` rules, and they are dispatched **on node class**:
`_moment_type` refuses a non-`RandomVariable` subject with `HML-T481`, `dist_type` fixes
the result to `Distribution[T]`, `MembershipExpr` exists as its own node specifically so
that no backend can emit membership as an infix relational operator.

Under a generic `Apply`, each of those becomes a signature lookup keyed on a head symbol.
That is a workable design — but it is a rewrite of every rule that produces the measured
strength, executed with no regression baseline (§6.2), and the audit's own finding is that
this compiler's value is concentrated in exactly those rules.

### 6.5 Role labels — D-003

This is the sharpest concrete risk. Today `Call` (positional) and `DistExpr`
(role-labelled) are **different node classes**, and the parser chooses between them by
whether `:=` appears. The consequence is that positional distribution arguments are refused
*at the parser*, with a bespoke correction:

```
error HML-P234: positional arguments are not permitted for distribution 'Normal'
  --> <input>:3:16
   3 | law X ~ Normal(0.0, 1.0)
                      ^^^
  note: role labels are mandatory by design decision D-003: they make 'scale' vs
        'variance' explicit rather than positional
  help: label each argument by its role, e.g. Normal(location := mu, scale := sigma)
```

A single generic `Apply` with optionally-labelled arguments cannot make that distinction at
parse time: `Normal(0.0, 1.0)` becomes a well-formed positional `Apply` and the refusal
moves downstream into the checker, several passes away from the token the user got wrong.
The brief's own warning — "a generic `Apply` that erases role labels would destroy D-003"
— is right, and the proposed `Attribute` third node does not fully answer it: keeping
labels *representable* is not the same as keeping them *mandatory at the parser*, and it is
the mandatory-at-the-parser part that D-003 bought.

The same applies to `RuleArg` (D-025), `ConceptMember` and `ContinuityExpr`'s mandatory
`on :=` role.

### 6.6 Dimensional safety

Dimension rules are attached to node classes: `BinOp` multiplies and divides dimensions,
`DerivativeExpr` divides by the binder's dimension, `IntegralExpr` multiplies by it,
comparisons demand dimensional equality (`HML-D502`). Under a generic `Bind` these become a
per-head table. That is arguably *cleaner* than the current arrangement — but it is another
re-derivation of working, measured rules with no regression baseline.

### 6.7 Diagnostics

159 distinct diagnostic codes; 360 emission sites; 136 of 184 structured emission sites
carry a `correction`, `notes`, `expected` or `found` field. The diagnostics are keyed to
surface constructs (`"a set comprehension requires '|' between the binder and its
predicate"`). Elaborating a sugared surface into a generic core means diagnostics are
produced against the core and must be re-projected onto the surface the author wrote.
**Nothing in the current codebase does that**, and the repair-loop benchmark (H4) depends
on one diagnostic per genuine mistake.

---

## 7. The fork — recommendation

> **The AST is not the primary blocker. Do not replace it with a generic
> Apply / Bind / Attribute core. Make two targeted additions, do the local repairs, and
> adopt a generic binder *protocol* to fix the duplication without touching identity.**
>
> **Confidence: ~0.75.**

The argument, entirely from the measurement:

**1. Twenty-one of twenty-eight failures do not involve `ast/nodes.py` at all.** Twelve are
`LOCAL` — a builtin signature, a registry entry, a type rule, a checker pass. Nine are
`ONE_NODE` — one more keyword-headed form each, which is precisely the operation D-026
performed eleven times in a single commit and which this measurement shows is well
tolerated: the suite predicted a canonicalisation failure for 12 specimens and **none
occurred**, and CT-044 verifies print/reparse hash stability and alpha-invariance across
three different binder kinds at once. A generic core does nothing for any of these 21.
Six of them are already frozen as D-035, D-036 and D-037 (§4.1) — the programme has
*already* committed to the non-rewrite route for a fifth of the failure set, on
independent grounds.

**2. The seven that do need something new need two named things, not a new IR.**
Abstraction — CT-009, CT-034, CT-036 — and a binder over statements — CT-001, CT-008,
CT-025, CT-048. Both are additive. `Lambda(var, var_type, symbol_id, body)` is one more entry in
`BINDING_EXPRESSIONS`; `ForEachStmt(var, var_type, symbol_id, body: list[Statement])` is one
more `Statement`. Neither changes a single existing node's canonical encoding, so v1 hashes
survive by construction and the `uses_v2` machinery keeps working exactly as designed.

**3. The failure classes point away from representation.** Zero `CANONICAL`, zero
`BACKEND`, zero `SPECIMEN`. The classes that dominate are `GRAMMAR` (14 — missing surface
forms) and `TYPE` (8 — rules that are too narrow: `sqrt` has no `Quantity` case,
`transpose` has no vector case, `DistributionSpec` has no dimension variable, the
refinement lattice loses positivity across a cancellation). Not one of these eight is a
*shape* problem. They are all *content* problems in `types.py` and
`type_system/__init__.py`, which a generic core leaves entirely untouched. §3.1 is the
independent check on this: the specimens' own authors predicted `SEMANTIC_MODEL` or
`TYPE_SYSTEM` or `CANONICALIZATION` for thirteen failures that turned out to be plain
`GRAMMAR`. The suite was written expecting a representation problem and measured a
vocabulary problem.

**4. The generic core's own numbers do not clear the bar.** Applied alone, it closes the 7
`GENERAL` specimens and nothing else: **27/48 = 0.563**, below the Level 2 threshold of
0.70. Local repair alone reaches **32/48 = 0.667**. Local repair plus the one-node
additions reaches **41/48 = 0.854**, which is *above* the programme target of 0.85. The
rewrite is neither necessary nor sufficient for the target; the repairs are both.

**5. The duplication is real and the cheap fix gets most of it.** §5 measures 79 dispatch
sites and 298 lines across 17 files, and §5.1 shows a live defect caused by it. But the
defect's cause is not "five node classes" — it is "seventeen hand-rolled traversals". A
generic **protocol** on the existing nodes gets the benefit without the cost:

```python
# ast/nodes.py — ~40 lines, no field changes, no canonical change
def binder_of(node) -> tuple[SymbolId | None, Type | None] | None: ...
def scoped_children(node) -> tuple[list[Expr], list[Expr]]:  # (outside binder, inside)
```

Every one of the 17 consumers then asks the AST what binds what, instead of asserting it.
`free_names` becomes correct for all five binders and for every binder ever added. Zero
hashes change, zero of the 6252 tests need regenerating, D-003 is untouched, and the
diagnostics stay where they are. That is the generic core's principal measured benefit at
roughly 1% of its cost and none of its identity risk.

### 7.1 The strongest argument against this recommendation

Stated as strongly as I can make it, because it is not weak:

> Every `LOCAL` and `ONE_NODE` repair is cheap in isolation and expensive in aggregate.
> CLAUDE.md rule 4 requires all eight parts for each new construct — surface syntax, AST
> form, semantic rule, type rule, valid and invalid examples, backend behaviour, round-trip
> test — and §5 measures ten edit sites per binder. The plan above adds a λ, a `for each`,
> a summation binder, a conditional, an approximation marker, an intervention operator, an
> a.e. qualifier and a series form: eight new forms, three of them binders, on top of
> twelve type-system repairs.
>
> And the evidence that this project cannot sustain that is *already in this document*.
> D-026 added four binders in the commit before last. Seven of the seventeen binder-aware
> files still do not know about them, silently, and one of the seven — `free_names` — is
> measurably wrong as a result. If four binders in one commit produced seven stale
> traversals and one latent unsoundness, eight more forms will produce more. The generic
> core's entire value proposition is that the synchronisation question stops existing, and
> the honest reading of §5.1 is that the synchronisation question has already been lost
> once. Under that reading the correct move is to pay the restructuring now, at 21 node
> kinds, rather than at 30, and to accept the identity break while the historical evidence
> base is still small.

I do not find this decisive, for one reason: it argues for **removing the hand-rolled
traversals**, and it silently assumes that requires **removing the node classes**. It does
not. The binder protocol in point 5 removes the traversals and keeps the classes. If that
protocol is adopted and a subsequent commit *still* produces stale traversals, the argument
becomes decisive and the rewrite should be reconsidered — that is a concrete falsification
condition and it is cheap to test.

What would change my mind, stated in advance:

* a binder protocol lands and a later binder addition still leaves consumers stale;
* the `LOCAL` repairs turn out to interact — e.g. making `DistributionSpec`
  dimension-parametric requires reworking the node shapes rather than the spec table;
* abstraction turns out not to be expressible as one more `BINDING_EXPRESSIONS` entry
  because application against a bound variable needs a different `Call` shape;
* the programme raises the target above 0.90, at which point the 7 `GENERAL` specimens
  stop being optional and the two additions become load-bearing enough that their
  interaction with the existing 21 kinds needs re-examining.

### 7.2 Reachable-closure estimates

**These are estimates, not measurements.** They assume each labelled repair lands
completely and that no repair breaks another. The ceilings are printed by the runner.

| scenario | ceiling | realistic band |
|---|---:|---|
| today | **20/48 = 0.417** | measured |
| + all 12 `LOCAL` repairs | 32/48 = 0.667 | 0.60 – 0.67 |
| + all 9 `ONE_NODE` additions — **generic repair ceiling** | **41/48 = 0.854** | **0.75 – 0.85** |
| + a general nesting capability — **generic-core ceiling** | 48/48 = 1.000 | 0.85 – 0.95 |
| generic core **alone**, no local repair | 27/48 = 0.563 | 0.50 – 0.56 |

The bands discount the ceilings because `LOCAL` repairs are individually reliable
(a single well-scoped rule each, ~10–12 of 12 landing) while `ONE_NODE` additions each
carry the eight-part cost and ten edit sites (~6–9 of 9 landing).

Read against the programme target of 0.85:

* **generic repair alone reaches the target, at the top of its band.** It is the cheapest
  route and it is sufficient — but only if nearly everything lands.
* **the generic core alone does not reach the Level 2 threshold of 0.70**, let alone the
  target.
* the combination clears the target comfortably, which is why the two targeted additions
  in §7 are recommended *alongside* the repairs rather than instead of them.

One caveat on comparability: the 0.85 target was set against the 13-probe measure, whose
current value is 0.692. The 48-specimen suite is a harder and much larger instrument, and
0.85 on it is a materially stronger claim than 0.85 on the 13. If the programme wants the
target expressed on the 48, that should be an explicit decision.

### 7.3 Ordering, if the recommendation is taken

Ordered by closure gained per unit of risk, from the table above:

1. **The three silent losses first** (CT-018, CT-022, CT-038). All three are `LOCAL`, all
   three currently produce a clean compile with a wrong or unguarded result, and
   `silent_composition_loss_count` must be 0 for Level 3 regardless of the closure rate.
   CT-038 is already frozen as D-036; CT-018 and CT-022 are not covered by any frozen
   decision and need one each.
2. **The binder protocol** (§7 point 5). No closure gain, no hash change, fixes a live
   defect, and it is the prerequisite that makes every later binder addition cheap.
3. **The remaining 9 `LOCAL` repairs.** 0.417 → ~0.65, no AST change.
4. **The approximation marker** — one form, three specimens (CT-016, CT-042, CT-044).
5. **Abstraction** (`Lambda`) — one binder, three specimens (CT-034, CT-036, CT-009), and
   it is the single addition that unblocks the whole of analysis.
6. **The remaining one-node forms and the statement binder.**

---

## 8. Limitations of this study

Stated so they are not discovered as gotchas.

1. **The encodings are mine.** Framework §9.3 names encoding quality as the principal
   confound. Every encoding is stored verbatim in `audit_rerun/results/COMPOSITION_48.json`
   and a better one replaces it and re-scores the specimen. At least four specimens changed
   verdict during this study once a better encoding was found — CT-021 via
   `Vector[RandomVariable[T], N]`, CT-031 and CT-047 via set comprehension, CT-046 once the
   decision variable was named with `solve` — which is direct evidence that the confound is
   live and that my first encoding is not always the best one. **Every specimen scored
   `UNSUPPORTED` or `REJECTED_SPURIOUS` should be re-attacked by someone trying to make it
   pass before the fork decision is executed.**
2. **Fact checks cover what is inspectable.** A specimen with no fact check is scored on
   its primary and controls alone, so `COMPOSES` there means "compiled and the controls
   held", not "provably faithful". 23 of the 48 carry at least one fact check, 29 in all.
3. **The repair labels are judgement.** The failure *classes* are read off diagnostics and
   code; the `LOCAL`/`ONE_NODE`/`GENERAL` labels are my estimate of implementation cost,
   and they drive §7.2 entirely. They are recorded per specimen with a one-line
   justification so each can be disputed individually.
4. **48 specimens cannot cover the composition space** (framework §9.1). A failure mode not
   represented here was not detected.
5. **`prediction_accuracy` (§3.1) depends on a hand-written mapping.** My eight failure
   classes and the framework's seven surfaces are not the same vocabulary; the mapping is
   stated in §3.1 and a different reasonable mapping would move the figure. `SCOPE` and
   `CONSTRAINT` both map to `SEMANTIC_MODEL`, which is the loosest of the seven and
   therefore the most generous to the framework.
6. **No backend beyond CT-043 was exercised.** Translation loss was tested on one specimen
   across three targets; a full backend-composition sweep is `probe_v2_backends_and_level3.py`'s
   job, not this study's.
