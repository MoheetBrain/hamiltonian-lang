# ACQ0 v2 human-review packet

**PRIVATE — NEVER MODEL VISIBLE.** Contains authoritative sources, expected hashes and
reference renderings. Its presence in a model bundle is a leak.

Eight tasks. Generated deterministically from the canonical objects.

---

## v2_binding_dependency_001

**Family** `binding_dependency` · **canonical_hash** `de1f550e496094c018b1629274fee036fc303f26c76bcb70c476f53e5b3fee5d`
**semantic_identity** `9c9cc5daf14dd12478321618c9373f1374b837d75c245e1df9008e8e61f608bd`

### Authoritative HML-L1 source

```hml
module BindingDependency
const alpha : Real = 3
const beta : Real = 4
def gamma : Real := alpha + beta
def delta : Real := gamma * alpha
```

### Semantic metadata

- objective: `None`
- derived facts: none
- prohibited assumptions: none

### Model-visible structured target

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_binding_dependency_001",
  "family": "binding_dependency",
  "module": "BindingDependency",
  "declarations": [
    {
      "name": "alpha",
      "kind": "const",
      "type": "Real",
      "value": "3"
    },
    {
      "name": "beta",
      "kind": "const",
      "type": "Real",
      "value": "4"
    }
  ],
  "definitions": [
    {
      "name": "gamma",
      "binders": [],
      "codomain": "Real",
      "body": "alpha + beta"
    },
    {
      "name": "delta",
      "binders": [],
      "codomain": "Real",
      "body": "gamma * alpha"
    }
  ],
  "probability_laws": [],
  "assumptions": [],
  "domain_constraints": [],
  "derived_facts": [],
  "objective": null,
  "prohibited_assumptions": []
}
```

### Generated ACQ0 prose (clause → facts)

- `c.decl0`  → `decl0.name, decl0.kind, decl0.type, decl0.value`  
  The constant alpha has type Real and the value 3.
- `c.decl1`  → `decl1.name, decl1.kind, decl1.type, decl1.value`  
  The constant beta has type Real and the value 4.
- `c.def0`  → `def0.name, def0.codomain, def0.body`  
  The value gamma has type Real and is defined by alpha + beta.
- `c.def1`  → `def1.name, def1.codomain, def1.body`  
  The value delta has type Real and is defined by gamma * alpha.
- `c.objective`  → `objective`  
  No goal is stated; encode the object only.

### Surface B reference

```
mod BindingDependency
dec const alpha : Real := 3
dec const beta : Real := 4
fun gamma : Real := alpha + beta
fun delta : Real := gamma * alpha
```

### Results

| check | result |
|---|---|
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 exact |
| prose exact coverage | EXACT (15 facts) |
| structured-target reversibility | exact |
| partial operations | none |
| ACQ0 view has no question | True |
| H2 view carries no target | True |
| safe-bundle eligible | yes |
| **admission verdict** | **ADMISSIBLE** |

---

## v2_assumption_boundary_001

**Family** `assumption_boundary` · **canonical_hash** `a5b95fc0633e42fc3688d2b0b1b33f66e4abb0eabbdc8cce1c68fce3c63812e2`
**semantic_identity** `561abb036c293a2ea142e6c5f41ef0214d743a24e10a483accce8a279a32ec9f`

### Authoritative HML-L1 source

```hml
module AssumptionBoundary
const eta : Real = 5
var digamma : Real
assume digamma > 4
def varrho(mu : PositiveReal) : Real := eta / mu
```

### Semantic metadata

- objective: `None`
- derived facts: [('digamma != 0', ('digamma > 4',), False)]
- prohibited assumptions: none

### Model-visible structured target

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_assumption_boundary_001",
  "family": "assumption_boundary",
  "module": "AssumptionBoundary",
  "declarations": [
    {
      "name": "eta",
      "kind": "const",
      "type": "Real",
      "value": "5"
    },
    {
      "name": "digamma",
      "kind": "var",
      "type": "Real"
    }
  ],
  "definitions": [
    {
      "name": "varrho",
      "binders": [
        {
          "name": "mu",
          "type": "PositiveReal"
        }
      ],
      "codomain": "Real",
      "body": "eta / mu"
    }
  ],
  "probability_laws": [],
  "assumptions": [
    "digamma > 4"
  ],
  "domain_constraints": [],
  "derived_facts": [
    {
      "statement": "digamma != 0",
      "derived_from": [
        "digamma > 4"
      ]
    }
  ],
  "objective": null,
  "prohibited_assumptions": []
}
```

### Generated ACQ0 prose (clause → facts)

- `c.decl0`  → `decl0.name, decl0.kind, decl0.type, decl0.value`  
  The constant eta has type Real and the value 5.
- `c.decl1`  → `decl1.name, decl1.kind, decl1.type`  
  The quantity digamma is declared as var with type Real.
- `c.def0`  → `def0.name, def0.codomain, def0.body, def0.binder0`  
  The function varrho takes mu of type PositiveReal, returns Real, and is defined by eta / mu.
- `c.assume0`  → `assume0`  
  It is assumed that digamma > 4.
- `c.objective`  → `objective`  
  No goal is stated; encode the object only.

### Surface B reference

```
mod AssumptionBoundary
dec const eta : Real := 5
dec var digamma : Real
say assume digamma > 4
fun varrho(mu : PositiveReal) : Real := eta / mu
```

### Results

| check | result |
|---|---|
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 exact |
| prose exact coverage | EXACT (13 facts) |
| structured-target reversibility | exact |
| partial operations | division present, binder domains checked |
| ACQ0 view has no question | True |
| H2 view carries no target | True |
| safe-bundle eligible | yes |
| **admission verdict** | **ADMISSIBLE** |

---

## v2_implication_equivalence_001

**Family** `implication_vs_equivalence` · **canonical_hash** `f8088306b9ec0979e96138805940968e86737bad621b0edabb5729275396f31a`
**semantic_identity** `32ccbab81f1d2acc67626a57785954428d28ad82723db67fad17b8b49c77afb7`

### Authoritative HML-L1 source

```hml
module ImplicationDirection
var p : Bool
var q : Bool
def forward : Proposition := p implies q
def backward : Proposition := q implies p
assume p implies q
```

### Semantic metadata

- objective: `None`
- derived facts: none
- prohibited assumptions: ['that the converse holds']

### Model-visible structured target

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_implication_equivalence_001",
  "family": "implication_vs_equivalence",
  "module": "ImplicationDirection",
  "declarations": [
    {
      "name": "p",
      "kind": "var",
      "type": "Bool"
    },
    {
      "name": "q",
      "kind": "var",
      "type": "Bool"
    }
  ],
  "definitions": [
    {
      "name": "forward",
      "binders": [],
      "codomain": "Proposition",
      "body": "p => q"
    },
    {
      "name": "backward",
      "binders": [],
      "codomain": "Proposition",
      "body": "q => p"
    }
  ],
  "probability_laws": [],
  "assumptions": [
    "p => q"
  ],
  "domain_constraints": [],
  "derived_facts": [],
  "objective": null,
  "prohibited_assumptions": [
    "that the converse holds"
  ]
}
```

### Generated ACQ0 prose (clause → facts)

- `c.decl0`  → `decl0.name, decl0.kind, decl0.type`  
  The quantity p is declared as var with type Bool.
- `c.decl1`  → `decl1.name, decl1.kind, decl1.type`  
  The quantity q is declared as var with type Bool.
- `c.def0`  → `def0.name, def0.codomain, def0.body`  
  The value forward has type Proposition and is defined by p => q.
- `c.def1`  → `def1.name, def1.codomain, def1.body`  
  The value backward has type Proposition and is defined by q => p.
- `c.assume0`  → `assume0`  
  It is assumed that p => q.
- `c.prohibit0`  → `prohibit0`  
  Do not assume that the converse holds.
- `c.objective`  → `objective`  
  No goal is stated; encode the object only.

### Surface B reference

```
mod ImplicationDirection
dec var p : Bool
dec var q : Bool
fun forward : Proposition := p => q
fun backward : Proposition := q => p
say assume p => q
```

### Results

| check | result |
|---|---|
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 exact |
| prose exact coverage | EXACT (15 facts) |
| structured-target reversibility | exact |
| partial operations | none |
| ACQ0 view has no question | True |
| H2 view carries no target | True |
| safe-bundle eligible | yes |
| **admission verdict** | **ADMISSIBLE** |

---

## v2_approximation_equality_001

**Family** `approximation_vs_equality` · **canonical_hash** `5ec8d81b39c57a81c38ef44c2d2362db30bb5fd5b5e10a59442c3e9be082d9ba`
**semantic_identity** `3aeee6a55a6a620cf31de4eadf0b57a797be6e0f5a1635a0f5af93f06a281d7c`

### Authoritative HML-L1 source

```hml
module ApproximationBoundary
const target : Real = 2
var estimate : Real
const tolerance : PositiveReal = 0.01
require estimate - target < tolerance
```

### Semantic metadata

- objective: `None`
- derived facts: none
- prohibited assumptions: none

### Model-visible structured target

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_approximation_equality_001",
  "family": "approximation_vs_equality",
  "module": "ApproximationBoundary",
  "declarations": [
    {
      "name": "target",
      "kind": "const",
      "type": "Real",
      "value": "2"
    },
    {
      "name": "estimate",
      "kind": "var",
      "type": "Real"
    },
    {
      "name": "tolerance",
      "kind": "const",
      "type": "PositiveReal",
      "value": "0.01"
    }
  ],
  "definitions": [],
  "probability_laws": [],
  "assumptions": [],
  "domain_constraints": [
    "estimate - target < tolerance"
  ],
  "derived_facts": [],
  "objective": null,
  "prohibited_assumptions": []
}
```

### Generated ACQ0 prose (clause → facts)

- `c.decl0`  → `decl0.name, decl0.kind, decl0.type, decl0.value`  
  The constant target has type Real and the value 2.
- `c.decl1`  → `decl1.name, decl1.kind, decl1.type`  
  The quantity estimate is declared as var with type Real.
- `c.decl2`  → `decl2.name, decl2.kind, decl2.type, decl2.value`  
  The constant tolerance has type PositiveReal and the value 0.01.
- `c.require0`  → `require0`  
  It is required that estimate - target < tolerance.
- `c.objective`  → `objective`  
  No goal is stated; encode the object only.

### Surface B reference

```
mod ApproximationBoundary
dec const target : Real := 2
dec var estimate : Real
dec const tolerance : PositiveReal := 0.01
say require estimate - target < tolerance
```

### Results

| check | result |
|---|---|
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 exact |
| prose exact coverage | EXACT (13 facts) |
| structured-target reversibility | exact |
| partial operations | none |
| ACQ0 view has no question | True |
| H2 view carries no target | True |
| safe-bundle eligible | yes |
| **admission verdict** | **ADMISSIBLE** |

---

## v2_quantifier_scope_001

**Family** `quantifier_scope` · **canonical_hash** `6403b51b37d2929c4e633d6a9e3d24db7a1940b7162d97fa6cd8fbb21da9e97e`
**semantic_identity** `5463d694105f9918bf7aaa1df6de277474eb77a94f4c3cde6888d2a2200c0228`

### Authoritative HML-L1 source

```hml
module QuantifierScope
def every_x_has_a_y : Proposition := forall x : Real . exists y : Real . y > x
assume every_x_has_a_y
```

### Semantic metadata

- objective: `None`
- derived facts: none
- prohibited assumptions: ['that the quantifiers may be exchanged']

### Model-visible structured target

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_quantifier_scope_001",
  "family": "quantifier_scope",
  "module": "QuantifierScope",
  "declarations": [],
  "definitions": [
    {
      "name": "every_x_has_a_y",
      "binders": [],
      "codomain": "Proposition",
      "body": "forall x : Real . exists y : Real . y > x"
    }
  ],
  "probability_laws": [],
  "assumptions": [
    "every_x_has_a_y"
  ],
  "domain_constraints": [],
  "derived_facts": [],
  "objective": null,
  "prohibited_assumptions": [
    "that the quantifiers may be exchanged"
  ]
}
```

### Generated ACQ0 prose (clause → facts)

- `c.def0`  → `def0.name, def0.codomain, def0.body`  
  The value every_x_has_a_y has type Proposition and is defined by forall x : Real . exists y : Real . y > x.
- `c.assume0`  → `assume0`  
  It is assumed that every_x_has_a_y.
- `c.prohibit0`  → `prohibit0`  
  Do not assume that the quantifiers may be exchanged.
- `c.objective`  → `objective`  
  No goal is stated; encode the object only.

### Surface B reference

```
mod QuantifierScope
fun every_x_has_a_y : Proposition := all x : Real . some y : Real . y > x
say assume every_x_has_a_y
```

### Results

| check | result |
|---|---|
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 exact |
| prose exact coverage | EXACT (6 facts) |
| structured-target reversibility | exact |
| partial operations | none |
| ACQ0 view has no question | True |
| H2 view carries no target | True |
| safe-bundle eligible | yes |
| **admission verdict** | **ADMISSIBLE** |

---

## v2_probability_law_role_001

**Family** `probability_law_role` · **canonical_hash** `a5ec3ef23cc5f4cd527b9bb445191773689e25d3a291eb975b3061e538b13762`
**semantic_identity** `b4dba5cb2622dc5231e693cce42cb829c3eca3818194bae6e879c8d6bef92e11`

### Authoritative HML-L1 source

```hml
module ProbabilityRole
param theta : Probability
prior theta ~ Beta(alpha := 2, beta := 5)
obs successes : Natural = 7
obs trials : Natural = 10
likelihood successes | theta ~ Binomial(trials := trials, prob := theta)
```

### Semantic metadata

- objective: `None`
- derived facts: none
- prohibited assumptions: none

### Model-visible structured target

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_probability_law_role_001",
  "family": "probability_law_role",
  "module": "ProbabilityRole",
  "declarations": [
    {
      "name": "theta",
      "kind": "param",
      "type": "Probability"
    },
    {
      "name": "successes",
      "kind": "obs",
      "type": "Natural",
      "value": "7"
    },
    {
      "name": "trials",
      "kind": "obs",
      "type": "Natural",
      "value": "10"
    }
  ],
  "definitions": [],
  "probability_laws": [
    {
      "role": "prior",
      "target": "theta",
      "given": [],
      "distribution": "Beta(alpha := 2, beta := 5)"
    },
    {
      "role": "likelihood",
      "target": "successes",
      "given": [
        "theta"
      ],
      "distribution": "Binomial(trials := trials, prob := theta)"
    }
  ],
  "assumptions": [],
  "domain_constraints": [],
  "derived_facts": [],
  "objective": null,
  "prohibited_assumptions": []
}
```

### Generated ACQ0 prose (clause → facts)

- `c.decl0`  → `decl0.name, decl0.kind, decl0.type`  
  The quantity theta is declared as param with type Probability.
- `c.decl1`  → `decl1.name, decl1.kind, decl1.type, decl1.value`  
  The observed quantity successes has type Natural and the value 7.
- `c.decl2`  → `decl2.name, decl2.kind, decl2.type, decl2.value`  
  The observed quantity trials has type Natural and the value 10.
- `c.law0`  → `law0.role, law0.family, law0.target`  
  The prior of theta is Beta(alpha := 2, beta := 5).
- `c.law1`  → `law1.role, law1.family, law1.target, law1.given`  
  The likelihood of successes given theta is Binomial(trials := trials, prob := theta).
- `c.objective`  → `objective`  
  No goal is stated; encode the object only.

### Surface B reference

```
mod ProbabilityRole
dec param theta : Probability
dist prior theta ~ Beta(alpha := 2, beta := 5)
dec obs successes : Natural := 7
dec obs trials : Natural := 10
dist likelihood successes | theta ~ Binomial(trials := trials, prob := theta)
```

### Results

| check | result |
|---|---|
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 exact |
| prose exact coverage | EXACT (19 facts) |
| structured-target reversibility | exact |
| partial operations | none |
| ACQ0 view has no question | True |
| H2 view carries no target | True |
| safe-bundle eligible | yes |
| **admission verdict** | **ADMISSIBLE** |

---

## v2_dimensional_algebra_001

**Family** `dimensional_algebra` · **canonical_hash** `08277ef8e6b9cb4357d2bc02bcfec0a638944463f90c21feadea957d679e967e`
**semantic_identity** `99c0f7c71770f15449fcbb985df6b191a80f5d9e2ff04194ea9f3755c721bf30`

### Authoritative HML-L1 source

```hml
module DimensionalAlgebra
var force : Quantity[Mass * Length / Time^2]
var area : Quantity[Length^2]
def pressure : Quantity[Mass / (Length * Time^2)] := force / area
check dimension pressure = Mass / (Length * Time^2)
```

### Semantic metadata

- objective: `None`
- derived facts: none
- prohibited assumptions: none

### Model-visible structured target

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_dimensional_algebra_001",
  "family": "dimensional_algebra",
  "module": "DimensionalAlgebra",
  "declarations": [
    {
      "name": "force",
      "kind": "var",
      "type": "Quantity[Length * Mass / Time^2]"
    },
    {
      "name": "area",
      "kind": "var",
      "type": "Quantity[Length^2]"
    }
  ],
  "definitions": [
    {
      "name": "pressure",
      "binders": [],
      "codomain": "Quantity[Mass / (Length * Time^2)]",
      "body": "force / area"
    }
  ],
  "probability_laws": [],
  "assumptions": [],
  "domain_constraints": [],
  "derived_facts": [],
  "objective": null,
  "prohibited_assumptions": []
}
```

### Generated ACQ0 prose (clause → facts)

- `c.decl0`  → `decl0.name, decl0.kind, decl0.type`  
  The quantity force is declared as var with type Quantity[Length * Mass / Time^2].
- `c.decl1`  → `decl1.name, decl1.kind, decl1.type`  
  The quantity area is declared as var with type Quantity[Length^2].
- `c.def0`  → `def0.name, def0.codomain, def0.body`  
  The value pressure has type Quantity[Mass / (Length * Time^2)] and is defined by force / area.
- `c.objective`  → `objective`  
  No goal is stated; encode the object only.

### Surface B reference

```
mod DimensionalAlgebra
dec var force : Quantity[Length * Mass / Time^2]
dec var area : Quantity[Length^2]
fun pressure : Quantity[Mass / (Length * Time^2)] := force / area
say dim pressure = Mass / (Length * Time^2)
```

### Results

| check | result |
|---|---|
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 exact |
| prose exact coverage | EXACT (10 facts) |
| structured-target reversibility | exact |
| partial operations | division present, binder domains checked |
| ACQ0 view has no question | True |
| H2 view carries no target | True |
| safe-bundle eligible | yes |
| **admission verdict** | **ADMISSIBLE** |

---

## v2_transformation_side_condition_001

**Family** `transformation_side_condition` · **canonical_hash** `76e41aa93cf5048656d52841d35a9f95e308c91440bf8ad4b4a3fa72c18443cf`
**semantic_identity** `daa47b7306c99ed73a29797fe45b1226edf147b2329ac0a44bfd044526b62463`

### Authoritative HML-L1 source

```hml
module TransformationSideCondition
var lhs : Real
var rhs : Real
var scale : Real
require scale != 0
assume lhs * scale = rhs * scale
```

### Semantic metadata

- objective: `None`
- derived facts: none
- prohibited assumptions: none

### Model-visible structured target

```json
{
  "schema_version": "acq0.v2.lossless",
  "task_id": "v2_transformation_side_condition_001",
  "family": "transformation_side_condition",
  "module": "TransformationSideCondition",
  "declarations": [
    {
      "name": "lhs",
      "kind": "var",
      "type": "Real"
    },
    {
      "name": "rhs",
      "kind": "var",
      "type": "Real"
    },
    {
      "name": "scale",
      "kind": "var",
      "type": "Real"
    }
  ],
  "definitions": [],
  "probability_laws": [],
  "assumptions": [
    "lhs * scale = rhs * scale"
  ],
  "domain_constraints": [
    "scale != 0"
  ],
  "derived_facts": [],
  "objective": null,
  "prohibited_assumptions": []
}
```

### Generated ACQ0 prose (clause → facts)

- `c.decl0`  → `decl0.name, decl0.kind, decl0.type`  
  The quantity lhs is declared as var with type Real.
- `c.decl1`  → `decl1.name, decl1.kind, decl1.type`  
  The quantity rhs is declared as var with type Real.
- `c.decl2`  → `decl2.name, decl2.kind, decl2.type`  
  The quantity scale is declared as var with type Real.
- `c.assume0`  → `assume0`  
  It is assumed that lhs * scale = rhs * scale.
- `c.require0`  → `require0`  
  It is required that scale != 0.
- `c.objective`  → `objective`  
  No goal is stated; encode the object only.

### Surface B reference

```
mod TransformationSideCondition
dec var lhs : Real
dec var rhs : Real
dec var scale : Real
say require scale != 0
say assume lhs * scale = rhs * scale
```

### Results

| check | result |
|---|---|
| reference self-score | PASS |
| A/B/C/D round-trip | 4/4 exact |
| prose exact coverage | EXACT (12 facts) |
| structured-target reversibility | exact |
| partial operations | none |
| ACQ0 view has no question | True |
| H2 view carries no target | True |
| safe-bundle eligible | yes |
| **admission verdict** | **ADMISSIBLE** |

