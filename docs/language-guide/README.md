# HML-L1 language guide

A practical introduction. `SPEC.md` is normative; this is the readable version.

## The shape of a program

A program is a sequence of statements, one per line. Every line begins with a keyword that
determines what kind of statement it is, so nothing has to be inferred from context.

```
module BayesianCoin

param theta : Probability
prior theta ~ Beta(alpha := 1, beta := 1)

obs trials : Natural = 10
obs successes : Natural = 7

likelihood successes | theta ~ Binomial(trials := trials, prob := theta)

infer posterior theta
```

## Declaration kinds carry epistemic status

`var`, `param`, `const`, `obs`, `index` and `rv` are not stylistic variants. They record
*what kind of thing* a symbol is:

| keyword | meaning |
|---------|---------|
| `var` | a free mathematical variable |
| `param` | an unknown to be inferred or fixed |
| `const` | a fixed known value |
| `obs` | an observed datum |
| `index` | a dimension or counting index |
| `rv` | an explicitly declared random variable |

In LaTeX all six render as a letter. That difference is the point.

## Types say what a value can be

```
param sigma : PositiveReal      # cannot be zero or negative
param theta : Probability       # lies in [0, 1]
obs   n     : Natural           # a count
param beta  : Vector[Real, P]
param m     : Quantity[Mass]
param v     : Quantity[Length / Time]
```

`Probability` is **not** a `PositiveReal`. Zero is a probability and is not a positive
real; 2.0 is a positive real and is not a probability. The compiler knows this.

## Distributions are given by role, never by position

```
theta ~ Beta(alpha := 1, beta := 1)
x     ~ Normal(location := mu, scale := sigma)
```

`Normal(mu, sigma)` does not parse. Neither does `Normal(location := mu, variance := s)` —
that one produces:

```
error HML-T415: Normal has no role 'variance'
  expected: scale : PositiveReal
  found:    variance
  note: Normal is parameterised by its scale (standard deviation) in Hamiltonian Lang.
        Passing a variance here is the single most common cross-library error.
  help: scale := ...
```

## Quantifier scope is structural

```
require forall x : Real . exists y : Real . y > x
require exists y : Real . forall x : Real . y > x
```

These are different programs with different content hashes. The first is true over the
reals; the second is false. No consumer of the semantic graph can confuse them, because
the nesting is recorded as `scope_of` edges rather than left to reading order.

Every quantified variable needs an explicit domain. `forall x . P` does not parse.

## Dimensions are checked exactly

```
param m : Quantity[Mass]
param v : Quantity[Length / Time]

def kinetic_energy := 0.5 * m * v^2

check dimension kinetic_energy = Mass * Length^2 / Time^2
```

Dimensions are rational-exponent vectors, so `sqrt` of an area really is a length. Adding
a mass to a length is `HML-D502`, with both dimensions printed.

## Concepts must have consequences

```
concept LocationScaleFamily
    parameter location : Real
    parameter scale : PositiveReal
    transform standardise(u) := (u - location) / scale
    invariant scale_is_positive := scale > 0
    example standard_normal := location = 0 and scale = 1
end
```

A concept declaring neither an invariant nor an example is rejected. A name with no
testable consequence is not a definition.

## What the compiler will not let you do

| you write | you get |
|-----------|---------|
| `Normal(mu, sigma)` | `HML-P234` — label the roles |
| `0 < x < 1` | `HML-P230` — write `0 < x and x < 1` |
| `forall x . P` | `HML-P236` — state the domain |
| `param x : Real` used as a `scale` | `HML-T413` — a scale must be positive |
| a `Distribution` in arithmetic | `HML-T430` — a law is not a value |
| the same name bound twice in nested scopes | `HML-N302` — shadowing |
| `infer posterior theta` with no prior | `HML-S604` — not well posed |
| a concept with no invariant or example | `HML-S603` |

The rejections are the product. A permissive checker would have no value here.

## Seeing every view at once

```bash
.venv/bin/hml views examples/statistics/bayesian_coin.hml
```

prints the HML source, the controlled English, the LaTeX, the semantic-graph triples, and
the content hash — all projections of one object.

## What it does not do

It proves nothing. `hml obligations FILE` lists what the program *claims* and shows every
obligation as `NOT DISCHARGED`, except dimensional checks, which the type system decides.
