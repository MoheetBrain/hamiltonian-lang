# Hamiltonian V1 — Discourse, Transformation and Epistemics

Status: **DESIGN**. Nothing here is implemented. `src/` remains frozen at
`hml-v0-baseline` and must not change while this document is drafted.

V0 asked whether a compact typed representation changes what a model computes. The pilot
answered: it did not — six of seven paired contrasts had zero discordant pairs
(`docs/evaluation/HML_EVAL_001_PILOT_REPORT.md`). V0 is preserved as the baseline against
which V1 must be measured.

V1 asks a different question. V0 represents *mathematical content*. It has no way to say
what is being **derived from what**, what **follows logically** as opposed to what merely
**rewrites algebraically**, what is **known versus assumed versus merely not refuted**, or
what remains **to be shown**. Those four things are most of what a mathematician's prose is
actually doing. V1 adds them as executable state.

---

## 0. The rule that governs every addition below

> A construct enters the kernel **only if it changes what the checker reports.**

If a phrase alters no obligation, no type, no dependency and no open-goal set, it is
presentation and belongs in a renderer. "For completeness", "recall that", "it is worth
noting" are presentation. "We now show", "it remains to establish", "the converse fails"
are state.

This rule exists because V0's pilot demonstrated that added surface area is not
self-justifying. `CLAUDE.md` rule 7 already said so; the pilot supplied the evidence.

**Every layer below therefore carries its own kill criterion.** A layer that fails its
criterion is deleted, not defended.

---

## 1. The five layers

```
L5  DISCOURSE STATE        goal · pending_obligation · case · otherwise · discharge
     ▲                     what remains to be shown
L4  EPISTEMIC STATUS       proved · assumed · evidence · credence · almost_sure
     ▲                     how strongly, and on what grounds
L3  INFERENTIAL RELATIONS  entails · equivalent · counterexample · converse
     ▲                     what follows from what, logically
L2  TRANSFORMATION EDGES   step · yields · side conditions
     ▲                     what rewrites to what, algebraically
L1  MATHEMATICAL CONTENT   ── V0, unchanged ──
                           objects, types, laws, constraints, dimensions
```

L1 is V0 and is reused verbatim. L2–L5 are new. The layers are **separately droppable**:
each can be removed without breaking the ones below it.

---

## 2. The distinction V1 exists to draw

**Algebraic yielding is not logical implication.** V0 cannot express the difference; most
mathematical prose depends on it.

```
Given  e1 :  y = 2x + 1
       e2 :  x = 3

step   s1 := substitute(source := e2, into := e1)
yields e3 :  y = 2*3 + 1
```

`s1` rewrites `e1` into `e3`. It does **not** assert `e2 => e3`. The two live in different
layers and have different types, so no consumer can conflate them:

| | L2 transformation | L3 inference |
|---|---|---|
| written | `derive e3 from [e1, e2] via s1` | `entails p3 from [p1, p2] via modus_ponens` |
| relates | expressions | propositions |
| type | `Derivation` | `Entailment` |
| truth-preserving? | **only if its side conditions hold** | by the named rule |
| coercion between them | **none** | **none** |

### Side conditions are the point

Every transformation operation declares the obligations it generates. This is where L2
earns its place: an algebra step that silently divides by zero is exactly the error class
V0 cannot catch.

| operation | typed arguments | generated obligations |
|-----------|-----------------|----------------------|
| `substitute` | `source`, `into` | none |
| `divide` | `expr`, `by` | `by != 0` |
| `sqrt_both_sides` | `expr` | both sides `>= 0`; **sign branch is not unique** |
| `square_both_sides` | `expr` | **not reversible** — records a weakening |
| `differentiate` | `expr`, `wrt` | `expr` differentiable on its domain |
| `integrate` | `expr`, `wrt`, `over` | integrability on `over` |
| `limit` | `expr`, `variable`, `approaches` | limit exists |
| `cancel` | `expr`, `factor` | `factor != 0` |
| `apply` | `fn`, `to` | `to` in `domain(fn)` |
| `rearrange` | `expr`, `for` | `for` isolable |

`square_both_sides` recording a *weakening* rather than an equivalence is the small case
that shows the layer is doing real work: `x = -2` and `x^2 = 4` are not interchangeable, and
V0 has no way to say so.

---

## 3. Layer 4 — epistemic status, and the statistical negative

This layer exists mainly to make one error unrepresentable.

> **"Fail to reject H₀" must never compile to "H₀ is proved" or "there is no effect."**

V0's method for prohibiting a conflation is to give the two things incompatible types with
no coercion path between them (that is how `Distribution[T]`, `RandomVariable[T]` and `T`
are kept apart). V1 applies the same method.

### The epistemic type hierarchy — deliberately **not** a chain

```
Justification
├── Proof            established; discharges a goal
├── Assumption       taken as given; never discharges a goal
├── Evidence         data-derived support; NEVER becomes a Proof
└── Credence         a degree of belief ABOUT a model, not a probability WITHIN one
```

There is **no coercion** `Evidence -> Proof`, `Credence -> Probability`, or
`Assumption -> Proof`. `prove` requires a `Proof`. Therefore:

```
test   t1 := hypothesis_test(null := H0, alternative := H1, alpha := 0.05)
result r1 := fail_to_reject(test := t1, p_value := 0.18)
claim  c1 := insufficient_evidence_against(H0, under := t1)

prove c1                      # TYPE ERROR: c1 : Evidence, prove requires Proof
assert no_effect from c1      # TYPE ERROR: absence of evidence is not evidence of absence
```

### PValue is its own type

`p_value : PValue`, a refinement of `Probability` with **no** coercion to a posterior. So
`posterior(H0 | data) := p_value` does not type-check. This kills the single most common
misreading in applied statistics at the type level rather than in a comment.

### Epistemic constructors

| construct | type | meaning |
|-----------|------|---------|
| `proved(P, via := <proof>)` | `Proof` | established |
| `by_definition(P)` | `Proof` | true by a definition in scope |
| `assumed(P)` | `Assumption` | granted; carries forward as a dependency |
| `almost_sure(P)` | `Proposition` | holds with measure 1 |
| `with_high_probability(P, regime := n -> infinity)` | `Proposition` | asymptotic qualifier, regime mandatory |
| `likely(P, probability := q)` | `Credence` | degree of belief; `q : Probability` |
| `possible(P)` | `Credence` | not excluded |
| `consistent_with(P, data := D)` | `Evidence` | compatible; **not** support for P alone |
| `insufficient_evidence_against(H, under := test)` | `Evidence` | the correct reading of a non-rejection |
| `model_conditional(P, model := M)` | `Proposition` | true relative to M; M becomes a dependency |

`with_high_probability` requires an explicit `regime` because "with high probability" with
no asymptotic regime named is not a mathematical statement.

---

## 4. Layer 5 — discourse state

Executable, not decorative. `goal` opens an obligation; `discharge` closes it; the checker
reports every goal still open at end of module. That is the test of whether an item belongs
here at all.

| construct | effect on checker state |
|-----------|------------------------|
| `goal g1 := <proposition>` | opens an obligation named `g1` |
| `discharge g1 by <Proof>` | closes it; **requires `Proof`, not `Evidence`** |
| `pending_obligation` | derived, never written by hand: the open set |
| `case c1 := <condition>` | opens a branch; propositions inside are conditional on `c1` |
| `otherwise` | the complement branch; **exhaustiveness is checked** |
| `end_case` | closes the branch |

Case exhaustiveness is a real check: `case x > 0` … `otherwise` covers the reals, but
`case x > 0` … `case x < 0` without `otherwise` leaves `x = 0` uncovered and must be
reported.

### Mapping from the human register

Your table, made precise. The left column is a **renderer output**, never a source
keyword.

| human register | canonical construct | layer |
|----------------|--------------------|-------|
| such that / provided that | `require` (V0) or `case` | L1 / L5 |
| under the assumption that | `assumed(P)` | L4 |
| for all / there exists | `forall` / `exists` (V0) | L1 |
| if and only if | `equivalent(P, Q)` | L3 |
| it follows that | `entails q from [p] via <rule>` | L3 |
| is given by / denote by | `define` / `bind` (V0) | L1 |
| with respect to θ | `differentiate(expr, wrt := theta)` | L2 |
| in the limit as | `limit(expr, variable := x, approaches := a)` | L2 |
| special case / otherwise | `case` / `otherwise` | L5 |
| the converse need not hold | `counterexample_to(implies(Q, P), witness := w)` | L3 |
| we now show | `goal` | L5 |
| it remains to establish | `pending_obligation` (derived) | L5 |
| for completeness | **renderer only — not in the kernel** | — |

---

## 5. Concept families are declared, never generated

Your warning is correct and becomes a hard design constraint: **`vary → variance` is not a
safe rule.** Nor is `estimate → estimator`. Productive morphology over mathematical
vocabulary manufactures plausible nonsense.

A family is therefore a **declared set of independently typed members with explicit
relations**. There is no suffix rule, no derivation engine, and no way to mint a member by
pattern.

```
family Estimation of theta : ParameterSpace
    member procedure  : EstimationProcedure
    member estimator  : Function[Sample -> ParameterSpace]
    member estimate   : ParameterSpace
    member sampling_law : Distribution[ParameterSpace]
    member standard_error : PositiveReal

    relation estimate = apply(estimator, to := sample)
    relation sampling_law = law_of(estimator, under := sampling_model)

    invariant estimator_is_a_function_not_a_value
    invariant estimate_depends_on_sample
    counterexample plugin_estimator_is_biased
end
```

Four things V0 and ordinary prose both blur, now four distinct types:

- **procedure** — the algorithm, independent of any sample
- **estimator** — a function from samples to parameter space
- **estimate** — the value obtained from one sample
- **sampling law** — the distribution of the estimator under repeated sampling

Saying "the estimate is unbiased" is then a type error: unbiasedness is a property of the
**estimator**, not of a number.

---

## 6. Build order — meaning outward

Every construct is specified in exactly this order, and no step may be skipped:

1. **semantic object** — what it is, and its type
2. **typed arguments** — the roles it takes, each with a type
3. **generated obligations** — what the checker must now track
4. **compact ASCII surface** — the source form
5. **controlled-English rendering** — professor register, output only

Worked example, `fail_to_reject`:

| step | content |
|------|---------|
| 1. object | a test outcome |
| 2. type | `Evidence` |
| 3. arguments | `test : HypothesisTest`, `p_value : PValue` |
| 4. obligations | `p_value > alpha(test)` must hold, else the outcome contradicts the test |
| 5. ASCII | `result r1 := fail_to_reject(test := t1, p_value := 0.18)` |
| 6. English | "The test t1 did not reject the null hypothesis at the 5% level (p = 0.18). This is not evidence that the null is true." |

The English rendering carries the caveat because the **type** carries it. That is the
difference between a language and a style guide.

---

## 7. Prohibited conflations added in V1

Enforced by types, as in V0. No subtyping path may be added between any pair.

1. `Evidence` is not `Proof` — failing to reject is not proving
2. `Credence` is not `Probability` — belief about a model is not a measure within it
3. `PValue` is not a posterior probability
4. `Derivation` (L2) is not `Entailment` (L3) — rewriting is not implying
5. `estimator` is not `estimate` is not `procedure`
6. `goal` (L5) is not `theorem` (L1) — intent is not a claim
7. `assumed(P)` never discharges a goal
8. `almost_sure(P)` is not `P` — a measure-1 qualifier is not removable
9. `with_high_probability` without a `regime` is not well formed

---

## 8. Falsifiability — each layer's kill criterion

The pilot's lesson is that a layer must earn its place with evidence. Each is dropped if
it fails its criterion.

| layer | must demonstrably do | kill criterion |
|-------|---------------------|----------------|
| **L2 transformation** | catch algebra errors V0 misses — division by a possibly-zero quantity, non-reversible squaring, out-of-domain application | fewer than 30% of injected invalid-step errors detected |
| **L3 inference** | distinguish valid from invalid inference chains, and detect an asserted converse that does not hold | does not separate valid from invalid chains at better than chance |
| **L4 epistemic** | reject `prove(fail_to_reject(...))` and every conflation in §7 | any conflation in §7 type-checks |
| **L5 discourse** | report open goals and non-exhaustive cases | adds no diagnostic V0 does not already produce |
| **families** | prevent estimator/estimate confusion | the confusion still type-checks |

L4's criterion is the strictest deliberately: it is the layer with the clearest
correctness claim, so it should be the easiest to falsify.

---

## 9. What V1 must **not** do

- It must not touch `src/hamiltonian_lang/` while V0 is the measured baseline.
- It must not add vocabulary that fails §0 — a construct that changes no checker state is
  a renderer feature.
- It must not derive concept members by morphological rule (§5).
- It must not be described as an improvement over V0 before
  `docs/design/V1_EXPERIMENT_PLAN.md` returns a result. On the current evidence V0 shows
  **no representation advantage**, and V1 inherits that starting position.

## 10. The honest prior on V1

V1 adds substantially more surface area than V0, and V0's surface area bought nothing
measurable. Two considerations cut the other way, and they are why the design is worth
building:

1. V1's claims are **correctness** claims, not reasoning-speed claims. "This program
   cannot express `prove(fail_to_reject(H0))`" is checkable without any model in the loop,
   and it is true or false independently of whether a model reasons better.
2. The pilot's one replicated positive signal was that **compiler feedback improved
   encoding fidelity**. L2–L5 add far more for a checker to have an opinion about, which is
   the mechanism that signal ran through.

Neither consideration is evidence. Both are reasons to run the experiment rather than to
assume its outcome.
