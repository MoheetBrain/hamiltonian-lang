# Shared HML semantics

The semantic core every surface must express. **Surface-independent** — how these are
*written* differs per surface file; what they *mean* does not.

Feature vocabulary exported verbatim from
`evaluation/syntax_gate/prompts.py::SHARED_CORE_FEATURES` (34 features). A task is
shared-core only when its features are a subset of the intersection all four candidates
support, which is what makes "representable in all four" a decidable predicate rather than
a judgement call.

## Feature vocabulary

- `assume`
- `check_dimension`
- `concept_block`
- `decl_const`
- `decl_index`
- `decl_obs`
- `decl_param`
- `decl_rv`
- `decl_var`
- `def_parametric`
- `def_simple`
- `infer`
- `law_conditioning`
- `law_labelled_roles`
- `law_likelihood`
- `law_prior`
- `objective`
- `op_arithmetic`
- `op_comparison`
- `op_equivalence`
- `op_implication`
- `op_logical`
- `prove`
- `quantifier_negation`
- `quantifier_nested`
- `require`
- `solve`
- `type_function`
- `type_proposition`
- `type_quantity`
- `type_random_variable`
- `type_refined`
- `type_scalar`
- `type_set`

## Core distinctions the semantics enforce

These are enforced by the type system, not by convention. No coercion path exists between
either side of any line:

```
a Distribution[T]   is not a value of T
a RandomVariable[T] is not a Distribution[T] and is not a T
=  (equality)       is not ~ (distributed as) and is not approximation
=> (implication)    is not correlation and is not causation
Probability         is not PositiveReal   (incomparable; they meet at NonNegativeReal)
PValue              is not Probability and is not PosteriorProbability
Evidence            is not Proof
fail_to_reject(H0)  is not proof of H0
```

## Declarations

The keyword records epistemic status, not style:

```
var   <name> : <Type>            a free mathematical variable
param <name> : <Type>            an unknown to be inferred or fixed
const <name> : <Type> = <expr>   a fixed known value
obs   <name> : <Type> = <expr>   an observed datum
index <name> : Natural           a counting or dimension index
rv    <name> : RandomVariable[T] an explicitly declared random variable
```

## Types

```
Bool Natural Integer Rational Real NonNegativeReal PositiveReal Probability
PValue PosteriorProbability Proposition
Vector[T, n]  Matrix[T, m, n]  Quantity[<dimension>]  Distribution[T]  RandomVariable[T]
```

## Dimensions

Rational-exponent vectors over seven SI base dimensions. Division is **left-associative**
and parentheses are honoured:

```
a / b / c    ==  a * b^-1 * c^-1
a / (b * c)  ==  a * b^-1 * c^-1
a / (b / c)  ==  a * b^-1 * c      <- genuinely different
```

## Unsupported constructs

Anything outside the above fails loudly with a diagnostic code rather than being silently
accepted. An unknown type is `HML-T440`; an unknown callee is `HML-N306`. Do not invent
constructs to fill a gap — a rejected encoding is a measurable outcome, a fabricated one is
not.

## Source repository paths

- `evaluation/syntax_gate/prompts.py` — `SHARED_CORE_FEATURES`, rule cards
- `src/hamiltonian_lang/types.py` — type lattice and dimensions
- `src/hamiltonian_lang/ast/nodes.py` — semantic contract
- `src/hamiltonian_lang/backends/canonical.py` — canonical form and content hash
