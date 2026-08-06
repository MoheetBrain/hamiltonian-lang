# ACQ0 v2 human-review packet (round 2 — repaired ordered view)

**PRIVATE — NEVER MODEL VISIBLE.**

Regenerated after the ordered-view repair. The decisive column is **view-only
reconstruction**: the model-visible view alone, rebuilt into a module, compiled, and
compared to the reference. Four tasks failed that path before the repair.

---

## v2_binding_dependency_001

family `binding_dependency` · hash `de1f550e496094c018b16292`

### Authoritative source

```hml
module BindingDependency
const alpha : Real = 3
const beta : Real = 4
def gamma : Real := alpha + beta
def delta : Real := gamma * alpha
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_binding_dependency_001",
  "family": "binding_dependency",
  "module": "BindingDependency",
  "encoding_statements": [
    {
      "position": 1,
      "statement_id": "s1",
      "emit": true,
      "kind": "const",
      "name": "alpha",
      "type": "Real",
      "epistemic_role": "declaration",
      "value": "3"
    },
    {
      "position": 2,
      "statement_id": "s2",
      "emit": true,
      "kind": "const",
      "name": "beta",
      "type": "Real",
      "epistemic_role": "declaration",
      "value": "4"
    },
    {
      "position": 3,
      "statement_id": "s3",
      "emit": true,
      "kind": "def",
      "name": "gamma",
      "binders": [],
      "codomain": "Real",
      "body": "alpha + beta",
      "epistemic_role": "definition"
    },
    {
      "position": 4,
      "statement_id": "s4",
      "emit": true,
      "kind": "def",
      "name": "delta",
      "binders": [],
      "codomain": "Real",
      "body": "gamma * alpha",
      "epistemic_role": "definition"
    }
  ],
  "derived_facts": [],
  "prohibited_assumptions": [],
  "objective": null,
  "emission_rule": "Emit exactly the records in encoding_statements, in position order. Records with emit=false are explanatory metadata and must never appear in the output."
}
```

### Generated prose (encoding order)

The constant alpha has type Real and the value 3.
The constant beta has type Real and the value 4.
The value gamma has type Real and is defined by alpha + beta.
The value delta has type Real and is defined by gamma * alpha.

### Reconstructed from the view alone

```hml
module BindingDependency
const alpha : Real = 3
const beta : Real = 4
def gamma : Real := alpha + beta
def delta : Real := gamma * alpha
```

### Surface B reference

```
mod BindingDependency
dec const alpha : Real := 3
dec const beta : Real := 4
fun gamma : Real := alpha + beta
fun delta : Real := gamma * alpha
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 4 / 4 |
| non-emitted metadata | 0 records, all emit=false |
| ACQ0 question | None |
| H2 target leak | None |
| admission verdict | **PENDING SECOND HUMAN REVIEW** |

---

## v2_assumption_boundary_001

family `assumption_boundary` · hash `a5b95fc0633e42fc3688d2b0`

### Authoritative source

```hml
module AssumptionBoundary
const eta : Real = 5
var digamma : Real
assume digamma > 4
def varrho(mu : PositiveReal) : Real := eta / mu
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_assumption_boundary_001",
  "family": "assumption_boundary",
  "module": "AssumptionBoundary",
  "encoding_statements": [
    {
      "position": 1,
      "statement_id": "s1",
      "emit": true,
      "kind": "const",
      "name": "eta",
      "type": "Real",
      "epistemic_role": "declaration",
      "value": "5"
    },
    {
      "position": 2,
      "statement_id": "s2",
      "emit": true,
      "kind": "var",
      "name": "digamma",
      "type": "Real",
      "epistemic_role": "declaration"
    },
    {
      "position": 3,
      "statement_id": "s3",
      "emit": true,
      "kind": "assume",
      "expression": "digamma > 4",
      "epistemic_role": "supplied_assumption"
    },
    {
      "position": 4,
      "statement_id": "s4",
      "emit": true,
      "kind": "def",
      "name": "varrho",
      "binders": [
        {
          "name": "mu",
          "type": "PositiveReal"
        }
      ],
      "codomain": "Real",
      "body": "eta / mu",
      "epistemic_role": "definition"
    }
  ],
  "derived_facts": [
    {
      "expression": "digamma != 0",
      "derived_from": [
        "digamma > 4"
      ],
      "emit": false
    }
  ],
  "prohibited_assumptions": [],
  "objective": null,
  "emission_rule": "Emit exactly the records in encoding_statements, in position order. Records with emit=false are explanatory metadata and must never appear in the output."
}
```

### Generated prose (encoding order)

The constant eta has type Real and the value 5.
The quantity digamma is declared as var with type Real.
It is assumed that digamma > 4.
The function varrho takes mu of type PositiveReal, returns Real, and is defined by eta / mu.

### Reconstructed from the view alone

```hml
module AssumptionBoundary
const eta : Real = 5
var digamma : Real
assume digamma > 4
def varrho(mu : PositiveReal) : Real := eta / mu
```

### Surface B reference

```
mod AssumptionBoundary
dec const eta : Real := 5
dec var digamma : Real
say assume digamma > 4
fun varrho(mu : PositiveReal) : Real := eta / mu
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 4 / 4 |
| non-emitted metadata | 1 records, all emit=false |
| ACQ0 question | None |
| H2 target leak | None |
| admission verdict | **PENDING SECOND HUMAN REVIEW** |

---

## v2_implication_equivalence_001

family `implication_vs_equivalence` · hash `f8088306b9ec0979e9613880`

### Authoritative source

```hml
module ImplicationDirection
var p : Bool
var q : Bool
def forward : Proposition := p implies q
def backward : Proposition := q implies p
assume p implies q
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_implication_equivalence_001",
  "family": "implication_vs_equivalence",
  "module": "ImplicationDirection",
  "encoding_statements": [
    {
      "position": 1,
      "statement_id": "s1",
      "emit": true,
      "kind": "var",
      "name": "p",
      "type": "Bool",
      "epistemic_role": "declaration"
    },
    {
      "position": 2,
      "statement_id": "s2",
      "emit": true,
      "kind": "var",
      "name": "q",
      "type": "Bool",
      "epistemic_role": "declaration"
    },
    {
      "position": 3,
      "statement_id": "s3",
      "emit": true,
      "kind": "def",
      "name": "forward",
      "binders": [],
      "codomain": "Proposition",
      "body": "p => q",
      "epistemic_role": "definition"
    },
    {
      "position": 4,
      "statement_id": "s4",
      "emit": true,
      "kind": "def",
      "name": "backward",
      "binders": [],
      "codomain": "Proposition",
      "body": "q => p",
      "epistemic_role": "definition"
    },
    {
      "position": 5,
      "statement_id": "s5",
      "emit": true,
      "kind": "assume",
      "expression": "p => q",
      "epistemic_role": "supplied_assumption"
    }
  ],
  "derived_facts": [],
  "prohibited_assumptions": [
    {
      "statement": "that the converse holds",
      "emit": false
    }
  ],
  "objective": null,
  "emission_rule": "Emit exactly the records in encoding_statements, in position order. Records with emit=false are explanatory metadata and must never appear in the output."
}
```

### Generated prose (encoding order)

The quantity p is declared as var with type Bool.
The quantity q is declared as var with type Bool.
The value forward has type Proposition and is defined by p => q.
The value backward has type Proposition and is defined by q => p.
It is assumed that p => q.
Do not assume that the converse holds. This is guidance and must not be encoded.

### Reconstructed from the view alone

```hml
module ImplicationDirection
var p : Bool
var q : Bool
def forward : Proposition := p => q
def backward : Proposition := q => p
assume p => q
```

### Surface B reference

```
mod ImplicationDirection
dec var p : Bool
dec var q : Bool
fun forward : Proposition := p => q
fun backward : Proposition := q => p
say assume p => q
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 5 / 5 |
| non-emitted metadata | 1 records, all emit=false |
| ACQ0 question | None |
| H2 target leak | None |
| admission verdict | **PENDING SECOND HUMAN REVIEW** |

---

## v2_approximation_equality_002

family `approximation_vs_equality` · hash `f4b4a7e47c30ecb1125fce73`

### Authoritative source

```hml
module ApproximationBoundary
const target : Real = 2
var estimate : Real
const tolerance : PositiveReal = 0.01
require estimate - target < tolerance
require target - estimate < tolerance
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_approximation_equality_002",
  "family": "approximation_vs_equality",
  "module": "ApproximationBoundary",
  "encoding_statements": [
    {
      "position": 1,
      "statement_id": "s1",
      "emit": true,
      "kind": "const",
      "name": "target",
      "type": "Real",
      "epistemic_role": "declaration",
      "value": "2"
    },
    {
      "position": 2,
      "statement_id": "s2",
      "emit": true,
      "kind": "var",
      "name": "estimate",
      "type": "Real",
      "epistemic_role": "declaration"
    },
    {
      "position": 3,
      "statement_id": "s3",
      "emit": true,
      "kind": "const",
      "name": "tolerance",
      "type": "PositiveReal",
      "epistemic_role": "declaration",
      "value": "0.01"
    },
    {
      "position": 4,
      "statement_id": "s4",
      "emit": true,
      "kind": "require",
      "expression": "estimate - target < tolerance",
      "epistemic_role": "domain_constraint"
    },
    {
      "position": 5,
      "statement_id": "s5",
      "emit": true,
      "kind": "require",
      "expression": "target - estimate < tolerance",
      "epistemic_role": "domain_constraint"
    }
  ],
  "derived_facts": [],
  "prohibited_assumptions": [],
  "objective": null,
  "emission_rule": "Emit exactly the records in encoding_statements, in position order. Records with emit=false are explanatory metadata and must never appear in the output."
}
```

### Generated prose (encoding order)

The constant target has type Real and the value 2.
The quantity estimate is declared as var with type Real.
The constant tolerance has type PositiveReal and the value 0.01.
It is required that estimate - target < tolerance.
It is required that target - estimate < tolerance.

### Reconstructed from the view alone

```hml
module ApproximationBoundary
const target : Real = 2
var estimate : Real
const tolerance : PositiveReal = 0.01
require estimate - target < tolerance
require target - estimate < tolerance
```

### Surface B reference

```
mod ApproximationBoundary
dec const target : Real := 2
dec var estimate : Real
dec const tolerance : PositiveReal := 0.01
say require estimate - target < tolerance
say require target - estimate < tolerance
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 5 / 5 |
| non-emitted metadata | 0 records, all emit=false |
| ACQ0 question | None |
| H2 target leak | None |
| admission verdict | **PENDING SECOND HUMAN REVIEW** |

---

## v2_quantifier_scope_001

family `quantifier_scope` · hash `6403b51b37d2929c4e633d6a`

### Authoritative source

```hml
module QuantifierScope
def every_x_has_a_y : Proposition := forall x : Real . exists y : Real . y > x
assume every_x_has_a_y
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_quantifier_scope_001",
  "family": "quantifier_scope",
  "module": "QuantifierScope",
  "encoding_statements": [
    {
      "position": 1,
      "statement_id": "s1",
      "emit": true,
      "kind": "def",
      "name": "every_x_has_a_y",
      "binders": [],
      "codomain": "Proposition",
      "body": "forall x : Real . exists y : Real . y > x",
      "epistemic_role": "definition"
    },
    {
      "position": 2,
      "statement_id": "s2",
      "emit": true,
      "kind": "assume",
      "expression": "every_x_has_a_y",
      "epistemic_role": "supplied_assumption"
    }
  ],
  "derived_facts": [],
  "prohibited_assumptions": [
    {
      "statement": "that the quantifiers may be exchanged",
      "emit": false
    }
  ],
  "objective": null,
  "emission_rule": "Emit exactly the records in encoding_statements, in position order. Records with emit=false are explanatory metadata and must never appear in the output."
}
```

### Generated prose (encoding order)

The value every_x_has_a_y has type Proposition and is defined by forall x : Real . exists y : Real . y > x.
It is assumed that every_x_has_a_y.
Do not assume that the quantifiers may be exchanged. This is guidance and must not be encoded.

### Reconstructed from the view alone

```hml
module QuantifierScope
def every_x_has_a_y : Proposition := forall x : Real . exists y : Real . y > x
assume every_x_has_a_y
```

### Surface B reference

```
mod QuantifierScope
fun every_x_has_a_y : Proposition := all x : Real . some y : Real . y > x
say assume every_x_has_a_y
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 2 / 2 |
| non-emitted metadata | 1 records, all emit=false |
| ACQ0 question | None |
| H2 target leak | None |
| admission verdict | **PENDING SECOND HUMAN REVIEW** |

---

## v2_probability_law_role_001

family `probability_law_role` · hash `a5ec3ef23cc5f4cd527b9bb4`

### Authoritative source

```hml
module ProbabilityRole
param theta : Probability
prior theta ~ Beta(alpha := 2, beta := 5)
obs successes : Natural = 7
obs trials : Natural = 10
likelihood successes | theta ~ Binomial(trials := trials, prob := theta)
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_probability_law_role_001",
  "family": "probability_law_role",
  "module": "ProbabilityRole",
  "encoding_statements": [
    {
      "position": 1,
      "statement_id": "s1",
      "emit": true,
      "kind": "param",
      "name": "theta",
      "type": "Probability",
      "epistemic_role": "declaration"
    },
    {
      "position": 2,
      "statement_id": "s2",
      "emit": true,
      "kind": "prior",
      "target": "theta",
      "given": [],
      "distribution": "Beta(alpha := 2, beta := 5)",
      "epistemic_role": "probability_law"
    },
    {
      "position": 3,
      "statement_id": "s3",
      "emit": true,
      "kind": "obs",
      "name": "successes",
      "type": "Natural",
      "epistemic_role": "declaration",
      "value": "7"
    },
    {
      "position": 4,
      "statement_id": "s4",
      "emit": true,
      "kind": "obs",
      "name": "trials",
      "type": "Natural",
      "epistemic_role": "declaration",
      "value": "10"
    },
    {
      "position": 5,
      "statement_id": "s5",
      "emit": true,
      "kind": "likelihood",
      "target": "successes",
      "given": [
        "theta"
      ],
      "distribution": "Binomial(trials := trials, prob := theta)",
      "epistemic_role": "probability_law"
    }
  ],
  "derived_facts": [],
  "prohibited_assumptions": [],
  "objective": null,
  "emission_rule": "Emit exactly the records in encoding_statements, in position order. Records with emit=false are explanatory metadata and must never appear in the output."
}
```

### Generated prose (encoding order)

The quantity theta is declared as param with type Probability.
The prior of theta is Beta(alpha := 2, beta := 5).
The observed quantity successes has type Natural and the value 7.
The observed quantity trials has type Natural and the value 10.
The likelihood of successes given theta is Binomial(trials := trials, prob := theta).

### Reconstructed from the view alone

```hml
module ProbabilityRole
param theta : Probability
prior theta ~ Beta(alpha := 2, beta := 5)
obs successes : Natural = 7
obs trials : Natural = 10
likelihood successes | theta ~ Binomial(trials := trials, prob := theta)
```

### Surface B reference

```
mod ProbabilityRole
dec param theta : Probability
dist prior theta ~ Beta(alpha := 2, beta := 5)
dec obs successes : Natural := 7
dec obs trials : Natural := 10
dist likelihood successes | theta ~ Binomial(trials := trials, prob := theta)
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 5 / 5 |
| non-emitted metadata | 0 records, all emit=false |
| ACQ0 question | None |
| H2 target leak | None |
| admission verdict | **PENDING SECOND HUMAN REVIEW** |

---

## v2_dimensional_algebra_002

family `dimensional_algebra` · hash `6c16f97bd05dd86473465409`

### Authoritative source

```hml
module DimensionalAlgebra
var force : Quantity[Mass * Length / Time^2]
var duration : Quantity[Time]
def impulse : Quantity[Mass * Length / Time] := force * duration
check dimension impulse = Mass * Length / Time
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_dimensional_algebra_002",
  "family": "dimensional_algebra",
  "module": "DimensionalAlgebra",
  "encoding_statements": [
    {
      "position": 1,
      "statement_id": "s1",
      "emit": true,
      "kind": "var",
      "name": "force",
      "type": "Quantity[Length * Mass / Time^2]",
      "epistemic_role": "declaration"
    },
    {
      "position": 2,
      "statement_id": "s2",
      "emit": true,
      "kind": "var",
      "name": "duration",
      "type": "Quantity[Time]",
      "epistemic_role": "declaration"
    },
    {
      "position": 3,
      "statement_id": "s3",
      "emit": true,
      "kind": "def",
      "name": "impulse",
      "binders": [],
      "codomain": "Quantity[Length * Mass / Time]",
      "body": "force * duration",
      "epistemic_role": "definition"
    },
    {
      "position": 4,
      "statement_id": "s4",
      "emit": true,
      "kind": "check_dimension",
      "subject": "impulse",
      "expression": "Length * Mass / Time",
      "epistemic_role": "checked_property"
    }
  ],
  "derived_facts": [],
  "prohibited_assumptions": [],
  "objective": null,
  "emission_rule": "Emit exactly the records in encoding_statements, in position order. Records with emit=false are explanatory metadata and must never appear in the output."
}
```

### Generated prose (encoding order)

The quantity force is declared as var with type Quantity[Length * Mass / Time^2].
The quantity duration is declared as var with type Quantity[Time].
The value impulse has type Quantity[Length * Mass / Time] and is defined by force * duration.
It is checked that the dimension of impulse is Length * Mass / Time.

### Reconstructed from the view alone

```hml
module DimensionalAlgebra
var force : Quantity[Length * Mass / Time^2]
var duration : Quantity[Time]
def impulse : Quantity[Length * Mass / Time] := force * duration
check dimension impulse = Length * Mass / Time
```

### Surface B reference

```
mod DimensionalAlgebra
dec var force : Quantity[Length * Mass / Time^2]
dec var duration : Quantity[Time]
fun impulse : Quantity[Length * Mass / Time] := force * duration
say dim impulse = Length * Mass / Time
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 4 / 4 |
| non-emitted metadata | 0 records, all emit=false |
| ACQ0 question | None |
| H2 target leak | None |
| admission verdict | **PENDING SECOND HUMAN REVIEW** |

---

## v2_transformation_side_condition_001

family `transformation_side_condition` · hash `76e41aa93cf5048656d52841`

### Authoritative source

```hml
module TransformationSideCondition
var lhs : Real
var rhs : Real
var scale : Real
require scale != 0
assume lhs * scale = rhs * scale
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_transformation_side_condition_001",
  "family": "transformation_side_condition",
  "module": "TransformationSideCondition",
  "encoding_statements": [
    {
      "position": 1,
      "statement_id": "s1",
      "emit": true,
      "kind": "var",
      "name": "lhs",
      "type": "Real",
      "epistemic_role": "declaration"
    },
    {
      "position": 2,
      "statement_id": "s2",
      "emit": true,
      "kind": "var",
      "name": "rhs",
      "type": "Real",
      "epistemic_role": "declaration"
    },
    {
      "position": 3,
      "statement_id": "s3",
      "emit": true,
      "kind": "var",
      "name": "scale",
      "type": "Real",
      "epistemic_role": "declaration"
    },
    {
      "position": 4,
      "statement_id": "s4",
      "emit": true,
      "kind": "require",
      "expression": "scale != 0",
      "epistemic_role": "domain_constraint"
    },
    {
      "position": 5,
      "statement_id": "s5",
      "emit": true,
      "kind": "assume",
      "expression": "lhs * scale = rhs * scale",
      "epistemic_role": "supplied_assumption"
    }
  ],
  "derived_facts": [],
  "prohibited_assumptions": [],
  "objective": null,
  "emission_rule": "Emit exactly the records in encoding_statements, in position order. Records with emit=false are explanatory metadata and must never appear in the output."
}
```

### Generated prose (encoding order)

The quantity lhs is declared as var with type Real.
The quantity rhs is declared as var with type Real.
The quantity scale is declared as var with type Real.
It is required that scale != 0.
It is assumed that lhs * scale = rhs * scale.

### Reconstructed from the view alone

```hml
module TransformationSideCondition
var lhs : Real
var rhs : Real
var scale : Real
require scale != 0
assume lhs * scale = rhs * scale
```

### Surface B reference

```
mod TransformationSideCondition
dec var lhs : Real
dec var rhs : Real
dec var scale : Real
say require scale != 0
say assume lhs * scale = rhs * scale
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 5 / 5 |
| non-emitted metadata | 0 records, all emit=false |
| ACQ0 question | None |
| H2 target leak | None |
| admission verdict | **PENDING SECOND HUMAN REVIEW** |

---

**View-only reconstruction: 8/8 exact.**

No task is marked human-approved. That decision is not automatable.
