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
