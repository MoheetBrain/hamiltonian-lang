# ACQ0 v2 private review packet — 12 development tasks + 2 sealed spares

**PRIVATE — NEVER MODEL VISIBLE.**

Regenerated after INDEPENDENT_SEMANTIC_REVIEW. The decisive column is **view-only
reconstruction**: the model-visible view alone, rebuilt, compiled, and compared to the
reference. Findings and repairs are summarised in
`ACQ0_V2_INDEPENDENT_SEMANTIC_REVIEW.md`; the feature matrix is in
`ACQ0_V2_TAXONOMY.md`.

---

## v2_binding_dependency_001

family `binding_dependency` · hash `de1f550e496094c018b16292` · objective `none`

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
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `BindingDependency`; every statement below belongs to it, in the order given.
The constant `alpha` has type `Real` and the value `3`.
The constant `beta` has type `Real` and the value `4`.
The definition `gamma` takes no arguments, has codomain `Real` and body `alpha + beta`.
The definition `delta` takes no arguments, has codomain `Real` and body `gamma * alpha`.
No goal is stated; do not add one. Encode the statements above and nothing else.

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
| partiality | v2_binding_dependency_001: ACCEPT — 5 statement(s) walked, 0 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

## v2_assumption_boundary_001

family `assumption_boundary` · hash `a5b95fc0633e42fc3688d2b0` · objective `none`

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
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `AssumptionBoundary`; every statement below belongs to it, in the order given.
The constant `eta` has type `Real` and the value `5`.
The quantity `digamma` is declared as var with type `Real`.
It is assumed that `digamma > 4`.
The definition `varrho` takes `mu` of type `PositiveReal`, has codomain `Real` and body `eta / mu`.
No goal is stated; do not add one. Encode the statements above and nothing else.

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
| partiality | v2_assumption_boundary_001: ACCEPT — 5 statement(s) walked, 1 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

## v2_implication_equivalence_001

family `implication_vs_equivalence` · hash `f8088306b9ec0979e9613880` · objective `none`

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
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `ImplicationDirection`; every statement below belongs to it, in the order given.
The quantity `p` is declared as var with type `Bool`.
The quantity `q` is declared as var with type `Bool`.
The definition `forward` takes no arguments, has codomain `Proposition` and body `p => q`.
The definition `backward` takes no arguments, has codomain `Proposition` and body `q => p`.
It is assumed that `p => q`.
Do not assume that the converse holds. This is guidance and must not be encoded.
No goal is stated; do not add one. Encode the statements above and nothing else.

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
| partiality | v2_implication_equivalence_001: ACCEPT — 6 statement(s) walked, 0 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

## v2_approximation_equality_002

family `approximation_vs_equality` · hash `f4b4a7e47c30ecb1125fce73` · objective `none`

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
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `ApproximationBoundary`; every statement below belongs to it, in the order given.
The constant `target` has type `Real` and the value `2`.
The quantity `estimate` is declared as var with type `Real`.
The constant `tolerance` has type `PositiveReal` and the value `0.01`.
It is required that `estimate - target < tolerance`.
It is required that `target - estimate < tolerance`.
No goal is stated; do not add one. Encode the statements above and nothing else.

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
| partiality | v2_approximation_equality_002: ACCEPT — 6 statement(s) walked, 0 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

## v2_quantifier_scope_001

family `quantifier_scope` · hash `6403b51b37d2929c4e633d6a` · objective `none`

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
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `QuantifierScope`; every statement below belongs to it, in the order given.
The definition `every_x_has_a_y` takes no arguments, has codomain `Proposition` and body `forall x : Real . exists y : Real . y > x`.
It is assumed that `every_x_has_a_y`.
Do not assume that the quantifiers may be exchanged. This is guidance and must not be encoded.
No goal is stated; do not add one. Encode the statements above and nothing else.

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
| partiality | v2_quantifier_scope_001: ACCEPT — 3 statement(s) walked, 0 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

## v2_probability_law_role_001

family `probability_law_role` · hash `a5ec3ef23cc5f4cd527b9bb4` · objective `none`

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
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `ProbabilityRole`; every statement below belongs to it, in the order given.
The quantity `theta` is declared as param with type `Probability`.
The prior of `theta` is `Beta(alpha := 2, beta := 5)`.
The observed quantity `successes` has type `Natural` and the value `7`.
The observed quantity `trials` has type `Natural` and the value `10`.
The likelihood of `successes` given `theta` is `Binomial(trials := trials, prob := theta)`.
No goal is stated; do not add one. Encode the statements above and nothing else.

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
| partiality | v2_probability_law_role_001: ACCEPT — 6 statement(s) walked, 0 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

## v2_dimensional_algebra_002

family `dimensional_algebra` · hash `6c16f97bd05dd86473465409` · objective `none`

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
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `DimensionalAlgebra`; every statement below belongs to it, in the order given.
The quantity `force` is declared as var with type `Quantity[Length * Mass / Time^2]`.
The quantity `duration` is declared as var with type `Quantity[Time]`.
The definition `impulse` takes no arguments, has codomain `Quantity[Length * Mass / Time]` and body `force * duration`.
It is checked that the dimension of `impulse` is `Length * Mass / Time`.
No goal is stated; do not add one. Encode the statements above and nothing else.

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
| partiality | v2_dimensional_algebra_002: ACCEPT — 5 statement(s) walked, 0 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

## v2_transformation_side_condition_001

family `transformation_side_condition` · hash `76e41aa93cf5048656d52841` · objective `none`

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
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `TransformationSideCondition`; every statement below belongs to it, in the order given.
The quantity `lhs` is declared as var with type `Real`.
The quantity `rhs` is declared as var with type `Real`.
The quantity `scale` is declared as var with type `Real`.
It is required that `scale != 0`.
It is assumed that `lhs * scale = rhs * scale`.
No goal is stated; do not add one. Encode the statements above and nothing else.

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
| partiality | v2_transformation_side_condition_001: ACCEPT — 6 statement(s) walked, 0 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

## v2_quantifier_scope_003

family `quantifier_scope` · hash `f08671f35a5ce74f324fcf28` · objective `prove`

### Authoritative source

```hml
module BoundedQuantifierProof
var threshold : Real
def all_below : Proposition := forall x : Probability . x < threshold
def some_below : Proposition := exists x : Probability . x < threshold
assume all_below
prove some_below
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_quantifier_scope_003",
  "family": "quantifier_scope",
  "module": "BoundedQuantifierProof",
  "encoding_statements": [
    {
      "position": 1,
      "statement_id": "s1",
      "emit": true,
      "kind": "var",
      "name": "threshold",
      "type": "Real",
      "epistemic_role": "declaration"
    },
    {
      "position": 2,
      "statement_id": "s2",
      "emit": true,
      "kind": "def",
      "name": "all_below",
      "binders": [],
      "codomain": "Proposition",
      "body": "forall x : Probability . x < threshold",
      "epistemic_role": "definition"
    },
    {
      "position": 3,
      "statement_id": "s3",
      "emit": true,
      "kind": "def",
      "name": "some_below",
      "binders": [],
      "codomain": "Proposition",
      "body": "exists x : Probability . x < threshold",
      "epistemic_role": "definition"
    },
    {
      "position": 4,
      "statement_id": "s4",
      "emit": true,
      "kind": "assume",
      "expression": "all_below",
      "epistemic_role": "supplied_assumption"
    },
    {
      "position": 5,
      "statement_id": "s5",
      "emit": true,
      "kind": "prove",
      "expression": "some_below",
      "epistemic_role": "proof_obligation"
    }
  ],
  "derived_facts": [
    {
      "expression": "all_below => some_below",
      "derived_from": [
        "the non-emptiness of Probability"
      ],
      "emit": false
    }
  ],
  "prohibited_assumptions": [
    {
      "statement": "that the converse holds; exists does not give forall",
      "emit": false
    }
  ],
  "objective": {
    "kind": "prove",
    "statement": "some_below",
    "emit": false
  },
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `BoundedQuantifierProof`; every statement below belongs to it, in the order given.
The quantity `threshold` is declared as var with type `Real`.
The definition `all_below` takes no arguments, has codomain `Proposition` and body `forall x : Probability . x < threshold`.
The definition `some_below` takes no arguments, has codomain `Proposition` and body `exists x : Probability . x < threshold`.
It is assumed that `all_below`.
The goal is to prove that `some_below`.
It follows from the non-emptiness of Probability that `all_below => some_below`; this is a consequence, not a further restriction, and must not be encoded.
Do not assume that the converse holds; exists does not give forall. This is guidance and must not be encoded.
The point of this task is the `prove` statement already listed above (some_below). It is described here, not restated: do not emit a second statement for it.

### Reconstructed from the view alone

```hml
module BoundedQuantifierProof
var threshold : Real
def all_below : Proposition := forall x : Probability . x < threshold
def some_below : Proposition := exists x : Probability . x < threshold
assume all_below
prove some_below
```

### Surface B reference

```
mod BoundedQuantifierProof
dec var threshold : Real
fun all_below : Proposition := all x : Probability . x < threshold
fun some_below : Proposition := some x : Probability . x < threshold
say assume all_below
say prove some_below
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 5 / 5 |
| partiality | v2_quantifier_scope_003: ACCEPT — 6 statement(s) walked, 0 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

## v2_dimensional_algebra_004

family `dimensional_algebra` · hash `a3474923149cdeec9ec18509` · objective `decide`

### Authoritative source

```hml
module SecondMomentCheck
var mass : Quantity[Mass]
var radius : Quantity[Length]
def second_moment : Quantity[Mass * Length^2] := mass * radius ^ 2
check dimension second_moment = Mass * Length^2
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_dimensional_algebra_004",
  "family": "dimensional_algebra",
  "module": "SecondMomentCheck",
  "encoding_statements": [
    {
      "position": 1,
      "statement_id": "s1",
      "emit": true,
      "kind": "var",
      "name": "mass",
      "type": "Quantity[Mass]",
      "epistemic_role": "declaration"
    },
    {
      "position": 2,
      "statement_id": "s2",
      "emit": true,
      "kind": "var",
      "name": "radius",
      "type": "Quantity[Length]",
      "epistemic_role": "declaration"
    },
    {
      "position": 3,
      "statement_id": "s3",
      "emit": true,
      "kind": "def",
      "name": "second_moment",
      "binders": [],
      "codomain": "Quantity[Length^2 * Mass]",
      "body": "mass * radius ^ 2",
      "epistemic_role": "definition"
    },
    {
      "position": 4,
      "statement_id": "s4",
      "emit": true,
      "kind": "check_dimension",
      "subject": "second_moment",
      "expression": "Length^2 * Mass",
      "epistemic_role": "checked_property"
    }
  ],
  "derived_facts": [],
  "prohibited_assumptions": [],
  "objective": {
    "kind": "decide",
    "statement": "that second_moment has dimension Mass * Length^2",
    "emit": false
  },
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `SecondMomentCheck`; every statement below belongs to it, in the order given.
The quantity `mass` is declared as var with type `Quantity[Mass]`.
The quantity `radius` is declared as var with type `Quantity[Length]`.
The definition `second_moment` takes no arguments, has codomain `Quantity[Length^2 * Mass]` and body `mass * radius ^ 2`.
It is checked that the dimension of `second_moment` is `Length^2 * Mass`.
The point of this task is the `decide` statement already listed above (that second_moment has dimension Mass * Length^2). It is described here, not restated: do not emit a second statement for it.

### Reconstructed from the view alone

```hml
module SecondMomentCheck
var mass : Quantity[Mass]
var radius : Quantity[Length]
def second_moment : Quantity[Length^2 * Mass] := mass * radius ^ 2
check dimension second_moment = Length^2 * Mass
```

### Surface B reference

```
mod SecondMomentCheck
dec var mass : Quantity[Mass]
dec var radius : Quantity[Length]
fun second_moment : Quantity[Length^2 * Mass] := mass * radius ^ 2
say dim second_moment = Length^2 * Mass
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 4 / 4 |
| partiality | v2_dimensional_algebra_004: ACCEPT — 5 statement(s) walked, 0 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

## v2_probability_law_role_002

family `probability_law_role` · hash `da94a9779157e4433dc465e2` · objective `none`

### Authoritative source

```hml
module RateLaw
param lambda : PositiveReal
prior lambda ~ Gamma(shape := 2, rate := 3)
obs count : Natural = 4
likelihood count | lambda ~ Poisson(rate := lambda)
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_probability_law_role_002",
  "family": "probability_law_role",
  "module": "RateLaw",
  "encoding_statements": [
    {
      "position": 1,
      "statement_id": "s1",
      "emit": true,
      "kind": "param",
      "name": "lambda",
      "type": "PositiveReal",
      "epistemic_role": "declaration"
    },
    {
      "position": 2,
      "statement_id": "s2",
      "emit": true,
      "kind": "prior",
      "target": "lambda",
      "given": [],
      "distribution": "Gamma(shape := 2, rate := 3)",
      "epistemic_role": "probability_law"
    },
    {
      "position": 3,
      "statement_id": "s3",
      "emit": true,
      "kind": "obs",
      "name": "count",
      "type": "Natural",
      "epistemic_role": "declaration",
      "value": "4"
    },
    {
      "position": 4,
      "statement_id": "s4",
      "emit": true,
      "kind": "likelihood",
      "target": "count",
      "given": [
        "lambda"
      ],
      "distribution": "Poisson(rate := lambda)",
      "epistemic_role": "probability_law"
    }
  ],
  "derived_facts": [
    {
      "expression": "lambda > 0",
      "derived_from": [
        "the declared type of lambda"
      ],
      "emit": false
    }
  ],
  "prohibited_assumptions": [
    {
      "statement": "that a Gamma rate and a Poisson rate are the same role; the first parameterises the prior, the second is the observed process intensity",
      "emit": false
    }
  ],
  "objective": null,
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `RateLaw`; every statement below belongs to it, in the order given.
The quantity `lambda` is declared as param with type `PositiveReal`.
The prior of `lambda` is `Gamma(shape := 2, rate := 3)`.
The observed quantity `count` has type `Natural` and the value `4`.
The likelihood of `count` given `lambda` is `Poisson(rate := lambda)`.
It follows from the declared type of lambda that `lambda > 0`; this is a consequence, not a further restriction, and must not be encoded.
Do not assume that a Gamma rate and a Poisson rate are the same role; the first parameterises the prior, the second is the observed process intensity. This is guidance and must not be encoded.
No goal is stated; do not add one. Encode the statements above and nothing else.

### Reconstructed from the view alone

```hml
module RateLaw
param lambda : PositiveReal
prior lambda ~ Gamma(shape := 2, rate := 3)
obs count : Natural = 4
likelihood count | lambda ~ Poisson(rate := lambda)
```

### Surface B reference

```
mod RateLaw
dec param lambda : PositiveReal
dist prior lambda ~ Gamma(shape := 2, rate := 3)
dec obs count : Natural := 4
dist likelihood count | lambda ~ Poisson(rate := lambda)
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 4 / 4 |
| partiality | v2_probability_law_role_002: ACCEPT — 5 statement(s) walked, 0 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

## v2_assumption_boundary_002

family `assumption_boundary` · hash `458d73d235399b728aeae401` · objective `none`

### Authoritative source

```hml
module MixedOrderTransformation
var input : Real
require input > 0
var gain : PositiveReal
def amplified : Real := input * gain
assume amplified > input
require amplified < 100
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_assumption_boundary_002",
  "family": "assumption_boundary",
  "module": "MixedOrderTransformation",
  "encoding_statements": [
    {
      "position": 1,
      "statement_id": "s1",
      "emit": true,
      "kind": "var",
      "name": "input",
      "type": "Real",
      "epistemic_role": "declaration"
    },
    {
      "position": 2,
      "statement_id": "s2",
      "emit": true,
      "kind": "require",
      "expression": "input > 0",
      "epistemic_role": "domain_constraint"
    },
    {
      "position": 3,
      "statement_id": "s3",
      "emit": true,
      "kind": "var",
      "name": "gain",
      "type": "PositiveReal",
      "epistemic_role": "declaration"
    },
    {
      "position": 4,
      "statement_id": "s4",
      "emit": true,
      "kind": "def",
      "name": "amplified",
      "binders": [],
      "codomain": "Real",
      "body": "input * gain",
      "epistemic_role": "definition"
    },
    {
      "position": 5,
      "statement_id": "s5",
      "emit": true,
      "kind": "assume",
      "expression": "amplified > input",
      "epistemic_role": "supplied_assumption"
    },
    {
      "position": 6,
      "statement_id": "s6",
      "emit": true,
      "kind": "require",
      "expression": "amplified < 100",
      "epistemic_role": "domain_constraint"
    }
  ],
  "derived_facts": [
    {
      "expression": "input != 0",
      "derived_from": [
        "input > 0"
      ],
      "emit": false
    }
  ],
  "prohibited_assumptions": [],
  "objective": null,
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `MixedOrderTransformation`; every statement below belongs to it, in the order given.
The quantity `input` is declared as var with type `Real`.
It is required that `input > 0`.
The quantity `gain` is declared as var with type `PositiveReal`.
The definition `amplified` takes no arguments, has codomain `Real` and body `input * gain`.
It is assumed that `amplified > input`.
It is required that `amplified < 100`.
No goal is stated; do not add one. Encode the statements above and nothing else.

### Reconstructed from the view alone

```hml
module MixedOrderTransformation
var input : Real
require input > 0
var gain : PositiveReal
def amplified : Real := input * gain
assume amplified > input
require amplified < 100
```

### Surface B reference

```
mod MixedOrderTransformation
dec var input : Real
say require input > 0
dec var gain : PositiveReal
fun amplified : Real := input * gain
say assume amplified > input
say require amplified < 100
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 6 / 6 |
| partiality | v2_assumption_boundary_002: ACCEPT — 7 statement(s) walked, 0 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

## v2_dimensional_algebra_spare_001 *(sealed spare — never scored)*

family `dimensional_algebra` · hash `b0e3129057646f610caacf68` · objective `decide`

### Authoritative source

```hml
module WorkCheck
var force : Quantity[Mass * Length / Time^2]
var distance : Quantity[Length]
def work : Quantity[Mass * Length^2 / Time^2] := force * distance
check dimension work = Mass * Length^2 / Time^2
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_dimensional_algebra_spare_001",
  "family": "dimensional_algebra",
  "module": "WorkCheck",
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
      "name": "distance",
      "type": "Quantity[Length]",
      "epistemic_role": "declaration"
    },
    {
      "position": 3,
      "statement_id": "s3",
      "emit": true,
      "kind": "def",
      "name": "work",
      "binders": [],
      "codomain": "Quantity[Length^2 * Mass / Time^2]",
      "body": "force * distance",
      "epistemic_role": "definition"
    },
    {
      "position": 4,
      "statement_id": "s4",
      "emit": true,
      "kind": "check_dimension",
      "subject": "work",
      "expression": "Length^2 * Mass / Time^2",
      "epistemic_role": "checked_property"
    }
  ],
  "derived_facts": [],
  "prohibited_assumptions": [],
  "objective": {
    "kind": "decide",
    "statement": "that work has dimension Mass * Length^2 / Time^2",
    "emit": false
  },
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `WorkCheck`; every statement below belongs to it, in the order given.
The quantity `force` is declared as var with type `Quantity[Length * Mass / Time^2]`.
The quantity `distance` is declared as var with type `Quantity[Length]`.
The definition `work` takes no arguments, has codomain `Quantity[Length^2 * Mass / Time^2]` and body `force * distance`.
It is checked that the dimension of `work` is `Length^2 * Mass / Time^2`.
The point of this task is the `decide` statement already listed above (that work has dimension Mass * Length^2 / Time^2). It is described here, not restated: do not emit a second statement for it.

### Reconstructed from the view alone

```hml
module WorkCheck
var force : Quantity[Length * Mass / Time^2]
var distance : Quantity[Length]
def work : Quantity[Length^2 * Mass / Time^2] := force * distance
check dimension work = Length^2 * Mass / Time^2
```

### Surface B reference

```
mod WorkCheck
dec var force : Quantity[Length * Mass / Time^2]
dec var distance : Quantity[Length]
fun work : Quantity[Length^2 * Mass / Time^2] := force * distance
say dim work = Length^2 * Mass / Time^2
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 4 / 4 |
| partiality | v2_dimensional_algebra_spare_001: ACCEPT — 5 statement(s) walked, 0 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

## v2_implication_equivalence_spare_001 *(sealed spare — never scored)*

family `implication_vs_equivalence` · hash `51de0262b6fd6daab735c6ae` · objective `prove`

### Authoritative source

```hml
module BiconditionalCare
var p : Bool
var q : Bool
assume p => q
assume q => p
def equivalent : Proposition := p <=> q
prove equivalent
```

### Ordered model-visible view

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_implication_equivalence_spare_001",
  "family": "implication_vs_equivalence",
  "module": "BiconditionalCare",
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
      "kind": "assume",
      "expression": "p => q",
      "epistemic_role": "supplied_assumption"
    },
    {
      "position": 4,
      "statement_id": "s4",
      "emit": true,
      "kind": "assume",
      "expression": "q => p",
      "epistemic_role": "supplied_assumption"
    },
    {
      "position": 5,
      "statement_id": "s5",
      "emit": true,
      "kind": "def",
      "name": "equivalent",
      "binders": [],
      "codomain": "Proposition",
      "body": "p <=> q",
      "epistemic_role": "definition"
    },
    {
      "position": 6,
      "statement_id": "s6",
      "emit": true,
      "kind": "prove",
      "expression": "equivalent",
      "epistemic_role": "proof_obligation"
    }
  ],
  "derived_facts": [],
  "prohibited_assumptions": [
    {
      "statement": "that either implication alone establishes the biconditional",
      "emit": false
    }
  ],
  "objective": {
    "kind": "prove",
    "statement": "equivalent",
    "emit": false
  },
  "emission_rule": "Emit the module header named by `module` first, then exactly the records in encoding_statements, in position order \u2014 no more and no fewer. Anything carrying emit=false \u2014 derived facts, prohibited assumptions, and the objective \u2014 is explanatory metadata describing statements already listed, and must never appear in the output as a statement of its own."
}
```

### Generated prose (encoding order)

The module is named `BiconditionalCare`; every statement below belongs to it, in the order given.
The quantity `p` is declared as var with type `Bool`.
The quantity `q` is declared as var with type `Bool`.
It is assumed that `p => q`.
It is assumed that `q => p`.
The definition `equivalent` takes no arguments, has codomain `Proposition` and body `p <=> q`.
The goal is to prove that `equivalent`.
Do not assume that either implication alone establishes the biconditional. This is guidance and must not be encoded.
The point of this task is the `prove` statement already listed above (equivalent). It is described here, not restated: do not emit a second statement for it.

### Reconstructed from the view alone

```hml
module BiconditionalCare
var p : Bool
var q : Bool
assume p => q
assume q => p
def equivalent : Proposition := p <=> q
prove equivalent
```

### Surface B reference

```
mod BiconditionalCare
dec var p : Bool
dec var q : Bool
say assume p => q
say assume q => p
fun equivalent : Proposition := p <=> q
say prove equivalent
```

| check | result |
|---|---|
| **view-only reconstruction** | **EXACT** |
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 |
| statements in view / AST | 6 / 6 |
| partiality | v2_implication_equivalence_spare_001: ACCEPT — 7 statement(s) walked, 0 partial-operation site(s) inspected, all established |
| ACQ0 question (must be null) | None |
| H2 target leak (must be null) | None |
| independent semantic review | **PASSED (agent review, not human)** |

---

**View-only reconstruction: 14/14 exact.**

No task is marked human-approved. That decision is not automatable.
