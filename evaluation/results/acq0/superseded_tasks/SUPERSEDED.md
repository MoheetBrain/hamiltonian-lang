# Superseded ACQ0 v2 tasks — invalid development evidence

Preserved verbatim. Neither id is reused; both are excluded from every aggregate.

## `v2_approximation_equality_001` → `v2_approximation_equality_002`

```hml
module ApproximationBoundary
const target : Real = 2
var estimate : Real
const tolerance : PositiveReal = 0.01
require estimate - target < tolerance
```

**Why superseded.** The single inequality is a **one-sided** bound: it is satisfied by an
estimate arbitrarily far *below* target. The task encoded uniquely and passed every
executable check, so no machine test could have found this — it was caught by reading the
mathematics in plain English against the family name it claimed.

The replacement adds `require target - estimate < tolerance`, giving a genuine two-sided
bound. HML has no absolute-value form, so two explicit inequalities are the supported
spelling. Fresh id because the mathematics changed.

## `v2_dimensional_algebra_001` → `v2_dimensional_algebra_002`

```hml
module DimensionalAlgebra
var force : Quantity[Mass * Length / Time^2]
var area : Quantity[Length^2]
def pressure : Quantity[Mass / (Length * Time^2)] := force / area
check dimension pressure = Mass / (Length * Time^2)
```

**Why superseded — two independent defects.**

1. **The `check dimension` statement was invisible to the model.** `structured_target()`
   had no `CheckStmt` branch, so the statement existed in the reference and in no
   model-visible artefact. The AST held 5 statements; the view carried 3. Every encoder
   failed this task deterministically, whatever the model.
2. **Unguarded division.** `area` is a module-level `var` admitting zero. The partiality
   guard inspects only *binders*, so it never fired — the same defect displaced by one
   construct. It is also unguardable as written: `require area != 0` does not compile
   (`HML-D502`), because a `Quantity[Length^2]` cannot be compared to a dimensionless `0`.

The replacement uses `impulse := force * duration`. Multiplication is total, so no
definedness question arises, and the dimension check now appears in the ordered view.
Fresh id because the mathematics changed.

## What this pair demonstrates

Defect 1 above was a *view* defect and is now caught by the reconstruction gate. The
one-sided bound and the unguarded `var` division were **not** — the first is a semantics
question no hash comparison can pose, and the second sits outside the guard's reach.
Human review remains load-bearing.

---

## Round 2 — withdrawn during INDEPENDENT_SEMANTIC_REVIEW, before any model call

Both were authored on 2026-08-06 to fill taxonomy cells 9 and 10, and both were rejected by
the independent partiality/well-posedness reviewer in the same session. Neither was ever
shown to a model. Both are recorded here because the reasons generalise.

### `v2_quantifier_scope_002` — the premise is false

```hml
module QuantifierProof
def some_bound_beats_all : Proposition := exists b : Real . forall x : Real . x < b
def each_x_has_a_bound : Proposition := forall x : Real . exists b : Real . x < b
assume some_bound_beats_all
prove each_x_has_a_bound
```

`exists b : Real . forall x : Real . x < b` asserts a real number greater than every real
number. Instantiate the inner binder at `x := b` and it says `b < b`. The premise is
unsatisfiable, so the hypothesis set is inconsistent and **everything is entailed —
including the converse the task explicitly prohibited.** The one discrimination the task
existed to make was therefore vacuous.

Independently: the goal `forall x . exists b . x < b` is a theorem of the reals (take
`b = x + 1`), so it holds with no premise at all and the `assume` is inert. A `prove` that
cannot separate a model which used the premise from one which ignored it measures nothing.

Nothing in the construction gate catches this. `assume 1 > 2` compiles and scans ACCEPT.
There is no satisfiability, entailment or truth check anywhere in the corpus admission
path, and adding one is out of scope for a corpus gate.

Superseded by `v2_quantifier_scope_003`, which quantifies over `Probability` — a **bounded**
domain — so the premise is satisfiable, the goal is not a theorem, and the entailment holds
only because the domain is non-empty.

### `v2_dimensional_algebra_003` — the identifier and the body disagree

```hml
module KineticEnergyCheck
var mass : Quantity[Mass]
var speed : Quantity[Length / Time]
def kinetic_energy : Quantity[Mass * Length^2 / Time^2] := mass * speed ^ 2
check dimension kinetic_energy = Mass * Length^2 / Time^2
```

The dimensional arithmetic is correct and the operation is total. The defect is that
kinetic energy is **½mv²**, and `0.5 * mass * speed ^ 2` compiles *and* passes the same
dimension check while hashing differently. Every other occurrence of that identifier in
this repository — the AST docstring, `examples/physics/kinetic_energy.hml`, all five
candidate-syntax examples, the language guide, the syntax-acquisition generator — writes
the coefficient. The prior ACQ0 track_a items on this shape are this task **with the `0.5`
deleted**, and they were run against this model.

A model that knows physics, or that had seen that material, emits the coefficient and is
scored FAIL on a hash difference. Failures would correlate with prior exposure and with
physical competence, in the direction that inflates the apparent difficulty of dimensional
encoding — and that is precisely the v1 defect this corpus exists to retire.

The contamination gate does not catch it: measured shingle overlap 0.04 against a 0.60
threshold. Structural reproduction with one term deleted is not textual near-duplication.

Superseded by `v2_dimensional_algebra_004`, the second moment of a point mass `m * r^2`,
which has no coefficient, so the identifier and the body agree.
