# HML v2 — mathematical expression coverage

**Status: normative.** Companion to `SEMANTICS.md` and `REASONING_MODEL.md`. Decision
record: `DECISIONS.md` D-026.

This file answers one question for each of the eleven expression forms V2 adds: *what
does it denote, what type does it have, and what does it refuse?* The refusals are the
substance. A construct that accepts everything has not been added to this language; it
has been added to a different one.

Base: `7a98427` (the V2 reasoning spine).

---

## 0. What was broken

The language audit probed 64 critical mathematical atoms. 79.7% were faithfully
representable; **11 were at zero**:

| cluster | atoms |
|---|---|
| analysis | LIMIT · CONTINUITY · DERIVATIVE · INTEGRAL_DEFINITE |
| probability | EXPECTATION · JOINT · CONDITIONAL_PROBABILITY · INDEPENDENCE |
| sets | SET_MEMBERSHIP · SET_COMPREHENSION |
| epistemics | CORRELATION_VS_CAUSATION |

Two of the eleven were not missing but *unreachable*. `expectation` and `variance` were
reserved keywords with no expression production, so a complete and correct type rule sat
in the checker where no source could reach it:

```
require expectation(X) > 0.0
error HML-P231: expected an expression, found 'expectation'
```

`Set[T]` was inert in the same way: a type constructor with no membership relation and no
constructor, so no program could say anything about a set.

---

## 1. The surface, in full

```
expectation(X)                    expectation(X | Y, Z)        variance(X)
probability(A)                    probability(A | B)
joint(X, Y)
independent(X, Y)                 independent(X, Y | Z)
x in A                            { x : T | P }
limit(f, x : T -> a)              derivative(f, x : T)
integral(f, x : T, a, b)          continuous(f, on := D)
associated(X, Y)                  correlated(X, Y)             causes(X, Y)
```

Two type constructors join them: `Event` (nullary) and `Product[T1, T2, ...]`.

Three properties of the surface are deliberate and are worth stating because a reader
will otherwise assume the opposite.

**Every binder carries an explicit type.** `derivative(f, x : Real)`, never
`derivative(f, x)`. Governing principle 1 has already forced this twice — `HML-P236` on
quantifiers, `HML-P214` on transform parameters (D-015). An inferred binder type would be
inferred from the point or the bounds, which is exactly the implicit coupling those two
decisions refused.

**The primary spelling is `expectation(...)`, not `E[...]`.** `E[X]` collides with
indexing: `parse_postfix` already reads `IDENT [ ... ]` as an `Index`, so `E` would have
to be reserved in the value namespace. It cannot be. This is a language called
*Hamiltonian* Lang, `E` is energy, and
`benchmarks/representations/hamiltonian/p01_normal_scale_role.hml` already declares
`var E : RandomVariable[Real]`. A form whose reading depends on whether the author also
wanted a variable called `E` is the ambiguity `CLAUDE.md` rule 1 forbids.

**Conditioning is always `|`.** The same bar `law y | x ~ ...` uses. A reader who knows
one knows all of `expectation(X | Y)`, `probability(A | B)` and `independent(X, Y | Z)`.

---

## 2. The five kinds of thing, and why they must stay five

The audit's strongest measured finding is that HML's type system keeps
`RandomVariable[T]`, `Distribution[T]` and `T` apart where the comparison panel does not.
Adding probability *operators* is the most dangerous thing that can be done to that
result, because every operator is a potential coercion. The table is the contract:

| written | type | is it… |
|---|---|---|
| `X` | `RandomVariable[Real]` | a measurable function |
| `Normal(location := m, scale := s)` | `Distribution[Real]` | a law |
| `expectation(X)` | `Real` | a **value** |
| `expectation(X \| Y)` | `RandomVariable[Real]` | a **random variable** |
| `expectation(X \| theta)` | `Real` | a value — `theta` is not random |
| `joint(X, Y)` | `Distribution[Product[Real, Real]]` | a **law** |
| `X > 0.0` | `Event` | a measurable set of outcomes |
| `probability(X > 0.0)` | `Probability` | a **number** in [0, 1] |
| `independent(X, Y)` | `Proposition` | a claim about the laws |

### 2.1 E[X] is a value; E[X | Y] is a random variable

E[X] is a number. E[X | Y] is a function of Y, and a function of a random variable is a
random variable. Collapsing them lets

```
param m : Real = expectation(X | Y)
```

bind a random quantity to a fixed name. The checker rejects it (`HML-T403`).

Conditioning on something **non-random** gives a value again, because a deterministic
function of a constant is a constant. That is not a special case bolted on to make an
example work — it is the reason `expectation(X | theta) = A(theta) @ x` is a well-formed
equation rather than a category error.

The rule is stated once, in `TypeChecker._moment_type`:

> the result is `RandomVariable[T]` iff some element of the conditioning set has type
> `RandomVariable[_]`; otherwise it is `T`.

### 2.2 An expectation leaves the support

E[N] for a count is **not** a count. Returning the codomain unchanged — the obvious
implementation, and the one the dead `_aggregate_type` branch had — would make
`expectation(N) : Natural` compile for a Poisson count, which is false. The result lies
in the closed convex hull of the support (`_EXPECTATION_HULL`):

```
Bool            -> Probability          E[1_A] = P(A)
Natural         -> NonNegativeReal
PositiveNatural -> PositiveReal
Integer         -> Real
Probability     -> Probability          closed and convex
PValue          -> PValue               stays its own epistemic kind (D-022)
```

The last line matters as much as the first: no operator added here performs a
unit-interval coercion. Averaging p-values does not produce a posterior.

### 2.3 `probability(...)` is a `Probability`, and only that

Never `PValue`, never `PosteriorProbability`. The three are pairwise incomparable
(D-022) and a probability computed *inside the model* is the first of them; a tail
probability under a null and a posterior over hypotheses are outputs of procedures this
language does not run.

### 2.4 A joint law is a law

`joint(X, Y) : Distribution[Product[Real, Real]]`. It is not a random variable and not a
value, so every existing barrier applies to it with no new code: `joint(X, Y) > 0.0` is
refused by the same rule that refuses comparing any distribution with a number, and
`joint(X, Y) + 1.0` by the same rule that refuses arithmetic on a law.

`Product` is ordered, so `joint(X, Y)` and `joint(Y, X)` are different objects. This is
the one place where V2 does *not* sort a symmetric-looking operand list, and §4 says why.

---

## 3. `Event` — the barrier this change adds

`Event` and `Proposition` are **incomparable**. There is deliberately no subtyping path
in either direction.

A proposition is true or false. An event is neither until an outcome is drawn; it has a
*probability*, not a truth value. A comparison or logical formula with a
`RandomVariable` operand is therefore typed `Event`, and `require` / `assume` / `prove` /
`goal` / `derive` / `check` refuse it:

```
require X > 0.0
error HML-T480: require requires a proposition, not an event
  correction: require probability(X > 0.0) = 1.0
```

Without the separation, `require X > 0.0` looks exactly like `require x > 0.0` over a
value and claims something completely different — that a random inequality holds on
*every* draw. That is the silent-conflation failure mode, in the one place where the two
readings are typographically identical.

**Closure properties**, so the type is not trivially escapable: the complement of an
event is an event, an event combined with anything is an event, quantifying over an event
gives an event, and a random variable's membership in a fixed set is an event.

**This is a barrier addition, not a change of verdict.** Before D-026 an event could not
be *formed*: `X > 0.0` failed at `HML-T429`, "these operands are not comparable". Nothing
that used to compile stops compiling. One case is worth naming: `require X = Y` between
two random variables did compile, through `join`'s identity path, and now does not. Sure
equality and almost-sure equality are different claims and the language previously
admitted the stronger-looking one without saying which it meant.

### 3.1 What this does not give you

HML v2 has **no way to say "almost surely" as distinct from "surely"**.
`require probability(A) = 1.0` is the only spelling and it means the former. Recorded as
a limitation rather than papered over.

Also unchanged: the audit's C-7 hole. `law y ~ Normal(...)` on a plain `var y : Real`
still compiles, so a Bayesian `param theta : Probability` with a prior is not
`RandomVariable`-typed and its comparisons are propositions, not events. To get events,
declare `rv theta : RandomVariable[Probability]`. This is inherited (see `SEMANTICS.md`
§1.3) and D-026 does not claim to close it.

---

## 4. Measurable lifting

`expectation(f(X))` requires `f(X)` to be well-typed. So:

> **Lifting.** If `f : T -> U` and `X : RandomVariable[T]` then
> `f(X) : RandomVariable[U]`. The same holds for the arithmetic operators.

This is standard measure theory — a measurable function of a random variable is a random
variable — and it is what makes the new operators *compose* rather than requiring every
argument to be a bare symbol.

**It is not a subtyping path and must never become one.** `_underlying` strips one
wrapper and every caller re-wraps. It is applied only at operator and application sites.
`check(..., lift_random=True)` is opt-in and only `_check_user_call` passes it;
declaration initialisers, distribution roles and definition bodies do not. Therefore:

```
param p : Real = X               HML-T402      still refused
def t : Real := 2.0 * X          HML-T403      still refused
def t : Real := log(W)           HML-T403      still refused
```

The randomness is *tracked through* the operation, never erased by it.

Lifting is also strictly more precise than the accident it replaces.
`RandomVariable[Probability] + RandomVariable[Probability]` previously reached `join`,
which returned `RandomVariable[Probability]` — for a sum that may exceed 1. It now yields
`RandomVariable[NonNegativeReal]`.

---

## 5. Symmetry, declared

Canonical identity is where a symmetry claim becomes checkable, so each form declares
one and the test suite asserts it.

| form | operands | why |
|---|---|---|
| `correlated`, `associated` | **sorted** | the relations are symmetric |
| `causes` | **ordered** | direction *is* the claim |
| `independent(X, Y \| Z)` | both lists **sorted** | symmetric in operands and conditioning set |
| `expectation(X \| Y, Z)` | `given` **sorted** | conditioning on Y and Z generates one sigma-algebra — the treatment `Law.given` already receives |
| `joint(X, Y)` | **ordered** | the type is `Product[T1, T2]`; the first component of a pair is not the second |

Measured, and pinned as tests:

```
correlated(X, Y)  ==  correlated(Y, X)     same hash
causes(X, Y)      !=  causes(Y, X)         different hash
correlated(X, Y)  !=  causes(X, Y)         different hash
joint(X, Y)       !=  joint(Y, X)          different hash
```

HML performs no causal inference and these constructs claim none. Their entire purpose is
that the three relations cannot be written as if they were one thing, and that a causal
claim carries a direction the canonical form preserves.

`implies(P, Q)` is **not** added. `=>` and the `implies` keyword already denote it and
already produce one canonical form; a third spelling of one object would be two
implementations waiting to disagree.

---

## 6. Analysis: representation is not execution

`hml check` differentiates nothing and integrates nothing. What it checks is that each
expression names a well-scoped object with an exact type, an exact dimension and an exact
binder.

The dimensional rules are the checkable content, and they are exact inverses:

| form | dimension |
|---|---|
| `derivative(f, x : T)` | `dim(f) / dim(T)` — a length by a time is a velocity |
| `integral(f, x : T, a, b)` | `dim(f) * dim(T)` — a velocity over a time is a length |
| `limit(f, x : T -> a)` | the **closure** of `dim(f)`'s scalar refinement |

The base scalar of a derivative is `Real`: a derivative may be negative however positive
the body is.

**A limit lands in the closure.** Every value of `1.0 / x` for positive `x` is positive
and the limit need not be, so `PositiveReal` widens to `NonNegativeReal` and
`Natural` to `NonNegativeReal` — a limit of integers need not be an integer. Giving the
limit the body's own type would let a construction that provably escapes an open set keep
the refinement saying it cannot. The closed unit-interval kinds are their own closure.

**Scope is real.** The point of a limit and the bounds of an integral are evaluated in
the *enclosing* scope:

```
def t := limit(1.0 / x, x : PositiveReal -> x)
error HML-N301: 'x' is not bound
```

Otherwise the point would quietly bind to the variable being taken to it, which denotes
nothing.

All four new binders — `{...|...}`, `limit`, `derivative`, `integral` — go through the
**same resolver machinery as quantifiers**, so alpha-equivalence holds for them by
construction rather than by a parallel implementation that can drift:

```
integral(x ^ 2.0, x : Real, 0.0, 1.0)  ==  integral(u ^ 2.0, u : Real, 0.0, 1.0)
```

`ast.nodes.BINDING_EXPRESSIONS` is the table a reader consults; a test asserts it is
complete.

---

## 7. Sets: generative machinery, not a library

Two constructs, chosen so that the test of correctness is whether they **compose** with
what already exists rather than how many set operations are provided.

```
require forall x : Real . x in unit_interval => x in positives
require a in {x : Real | x > 1.0}
require continuous(f, on := {x : Real | x > 1.0})
```

None of those is a special case. Membership is an ordinary relation at comparison
precedence; a comprehension is an ordinary primary; continuity takes a function and a
set and neither had to be taught about the other.

Deliberate refusals:

* `{x : Real | X > x}` is rejected (`HML-T488`). The predicate is an event, so the set it
  would define is itself random, and v2 has no random-set type. It will not pretend the
  membership is fixed.
* `x in A` is a dedicated node, **not** a `Comparison` with `op="in"`. Membership relates
  a `T` to a `Set[T]`, not two comparable magnitudes; reusing `Comparison` would let
  every backend emit it as an infix relational operator without noticing.
* `continuous(f, on := D)` requires the role label, for the reason D-003 requires it on
  distributions: a bare second argument does not say whether it is the domain or a point.

---

## 8. Backends: render, or declare

`BackendResult.faithful` must never be `True` for a backend that dropped something. Three
**pre-existing** silent holes were closed here, because the new nodes would have fallen
into all three:

* `backends/latex.py` returned `\text{?}` for an unknown node while reporting faithful;
* `backends/english.py` returned "an unrepresented expression" likewise;
* `backends/graph.py::_children` returned `()`, so `require probability(X > 0.0)` would
  have appeared in the semantic graph with **no dependency edge on X at all** — a
  different shape of silence and a worse one, because the graph is what downstream tools
  query.

| target | treatment |
|---|---|
| `hml` | all eleven; round-trip hash-stable and idempotent |
| `english` | all eleven; three *different* sentences for the three causal relations |
| `latex` | nine exact; `joint` and the three analysis binders **weakened**, each declared |
| `lean` | membership and comprehension exact — Mathlib's `Set` *is* HML's `Set[T]`; nine **dropped** with specific reasons |
| `stan` | all eleven **dropped** with specific reasons |
| `sympy` | all eleven **dropped**; see the limitation below |

Two of those reasons are worth reading, because "the target cannot" would have been the
easy and false answer:

* **LaTeX weakens the analysis binders.** `\lim_{x \to 0}` is written identically whether
  `x` ranges over the reals or the positives, and those are different limits. Standard
  notation carries the binder's *name* and not its *domain*.
* **SymPy genuinely has `Integral`, `Derivative` and `Limit`.** They are dropped because
  the bound variable would need a `Symbol` carrying the assumptions of the HML binder
  type, and that backend declares symbols only from *declarations*. Two sibling binders
  spelled alike with different refinements — legal, because HML forbids shadowing but not
  reuse across disjoint scopes — would silently share one symbol, and a wrong assumption
  in a symbolic algebra system propagates into simplification results with no error.
  **This is a real gap.** Closing it needs a scoped symbol name per binder; it is
  recorded rather than half-done.

---

## 9. Canonical identity

Every new node has a branch in `backends/canonical.py::_expr`. This is not a rendering
nicety. The fallthrough emits `{"kind": "<ClassName>"}` and nothing else, so a missing
branch gives **every instance of a form the same identity** — and `expr_identity` is what
the reasoning kernel compares, so one integral would be accepted as a proof of another.

`tests/semantics/test_v2_expressions.py` therefore instantiates one of every `Expr`
subclass from real source and asserts, for each:

1. the canonical document has more than a `kind` key;
2. `render_expr` does not emit `<ClassName>`;
3. `graph._children` returns exactly the sub-expressions the node holds.

A twelfth expression form cannot be added without that test failing first.

---

## 10. Diagnostics introduced

| code | refuses |
|---|---|
| `HML-P261` | a relation given fewer operands than it relates |
| `HML-P262` | a binder with no explicit type |
| `HML-P263` | a causal relation with one operand |
| `HML-P264` | a comprehension with no predicate |
| `HML-P265` | a limit with no `->` |
| `HML-P266` | a continuity claim with a positional or misnamed domain |
| `HML-P267` | `Product` with fewer than two components |
| `HML-T480` | asserting an **event** as a proposition |
| `HML-T481` | the expectation of a quantity that is not random |
| `HML-T482` | `probability` of something that is not an event |
| `HML-T483` | conditioning a fixed aggregate's variance |
| `HML-T484` | a moment of a non-numeric or vector-valued random variable |
| `HML-T485` | `joint` / `independent` over a non-random operand |
| `HML-T486` | `in` with a non-set on the right |
| `HML-T487` | an element that cannot inhabit the set's element type |
| `HML-T488` | a comprehension predicate that is not a proposition |
| `HML-T489` | a limit point or integral bound outside the binder's type |
| `HML-T490` | a limit of something with no magnitude |
| `HML-T491` | an analysis form with an undetermined dimension |
| `HML-T492` | continuity of a non-function or of several arguments at once |
| `HML-T493` | a continuity domain that is not a set |
| `HML-T494` | a continuity domain outside the function's domain |
| `HML-T495` | a causal relation between constants |

Existing codes reused rather than duplicated: `HML-T428` (a law is not a value),
`HML-T430` (no arithmetic on a law), `HML-T403`/`HML-T402` (declared-type mismatch),
`HML-N301`/`HML-N302` (scope and shadowing), `HML-P202` (a keyword is not a name),
`HML-P230` (no chained relations).
