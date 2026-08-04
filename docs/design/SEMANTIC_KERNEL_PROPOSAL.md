# Semantic Kernel Proposal

Owner: Lead Architect (the `semantics-architect` role was folded in under the four-agent
limit, because the kernel had to exist before any other agent could build against it).

Implemented in `src/hamiltonian_lang/types.py`, `semantics/`, `type_system/`.
Machine-readable form: `spec/semantic_objects.yaml`, `spec/type_rules.yaml`.

## 1. What a kernel has to be

A semantic kernel is the set of distinctions the language commits to. It is not the
syntax, and it is not the type checker; it is what the type checker is checking *about*.
The test of a kernel is that it can be expressed in more than one surface syntax. HML-L1,
and the five candidate syntaxes in `examples/candidate_syntaxes/`, all target this kernel.

## 2. Object categories

Nine, no more:

`Symbol` · `Law` · `Distribution` · `Constraint` · `Assumption` · `Theorem` · `Objective` ·
`Inference` · `Concept` (+ `Check`, which is a compiler-discharged assertion rather than a
mathematical object).

`Symbol` carries a **declaration kind** — `var param const obs index rv` — which is
epistemic status, not decoration. `obs` records that a value was *observed*; `param`
records that it is *unknown*; `const` that it is *known*. These are three different
mathematical situations that ordinary notation renders identically, as a letter.

## 3. The minimum semantics for v0

Deliberately small. The kernel commits to exactly these distinctions:

1. **Every object has a type.** No inference from context, no untyped binder. `param a`
   without a type is `HML-T401`; `forall x . P` without a domain is `HML-P236`.
2. **Types form a partial order with refinements.** Not a chain. See §4.
3. **A value, a random variable, and a probability law are three things.** No subtyping
   path connects them. This is the kernel's single most load-bearing commitment.
4. **Binding is structural.** A symbol's identity is `(depth, ordinal)`, not its spelling.
5. **Dimension is part of type.** Checked exactly, over rational exponents.
6. **Assertion is separated from proof.** Every `require`, `assume`, `prove` and invariant
   produces a `ProofObligation` that is explicitly *not discharged*.

Everything else — measure theory, dependent shapes, unit conversion, proof search — is out
of v0 and listed in `V0_DESIGN_FREEZE.md` §8, so that no capability is inferred from
silence.

## 4. Equality, equivalence, and the poset

Three relations that ordinary notation runs together, kept apart here:

| relation | written | meaning |
|----------|---------|---------|
| definition | `:=` | binds a name to an expression |
| mathematical equality | `=` | a proposition, generating an obligation |
| distribution | `~` | relates a symbol to a probability law |
| structural identity | (not written) | equal canonical hashes |

`=` is a proposition, not an assignment; `:=` is a binding, not a claim. Writing `def f = 1`
is `HML-P207` with the distinction spelled out in the diagnostic.

**The scalar order is a poset.** `Probability` (the closed unit interval) and
`PositiveReal` (the open positive ray) are incomparable: 0 is in the first and not the
second, 2.0 is in the second and not the first. They meet at `NonNegativeReal`.
`PositiveNatural` was introduced as the meet of `Natural` and `PositiveReal` so that the
literal `1` can serve both as a count and as a scale.

A kernel that linearises this order admits unsound programs — specifically, it would let a
probability be used wherever a scale is required. That is why D-004 is marked high
reversal cost.

## 5. Binding and scope

- Module scope is collected in a first pass, so visibility is order-independent (D-008).
- Each quantifier and each parameterised definition opens a scope at `depth + 1`.
- **Shadowing is an error** (`HML-N302`, D-006), because the directive requires the
  language to *prevent* silent scope changes and a warning prevents nothing. This is
  stricter than most languages and is flagged as a candidate for relaxation if H1 shows no
  measurable benefit.
- A quantified variable is not visible outside its body; verified by test.

## 6. Constraints, assumptions and proof obligations

The kernel distinguishes:

| kind | source | epistemic status |
|------|--------|------------------|
| `constraint` | `require` | must hold; not proved |
| `assumption` | `assume` | taken as given; explicitly not proved |
| `theorem` | `prove` | claimed; a statement, never a proof |
| `parameter_positivity` | a refined scalar declaration | standing side condition |
| `dimension` | `check dimension` | **discharged** by the type system |

Only the last is ever marked discharged. `hml obligations FILE` shows the rest as
`NOT DISCHARGED`, which is the honest state of a system with no prover in it.

## 7. Concept minting

A new term must have a formal identity, not a plausible sound. The admission rule
(`HML-S603`) is deliberately minimal: **a concept declaring neither an invariant nor an
example is rejected.** Cheap to satisfy honestly, impossible to satisfy vacuously.

Full field list in `spec/concept_schema.yaml`.

## 8. What this kernel does not settle

Recorded rather than glossed:

- Whether declaration ordinals should be positional (they currently are; see
  `IR_PROPOSAL.md` §7).
- Whether the role discipline should extend from distributions to all function calls
  (Q-05).
- Whether `Quantity` should carry a *unit* as well as a dimension. v0 checks dimensions
  and does not reconcile units, so metres and feet are indistinguishable to it.
- Whether `RandomVariable[T]` should be required for any symbol given a law. Currently a
  plain `param theta : Probability` may receive a prior, which matches Bayesian practice
  but means the type does not record stochasticity — the *symbol table* does, via
  `Symbol.stochastic`. This is a defensible split and an arguable one.

## 9. Prior art

This kernel is not novel and should not be described as such. Typed semantic cores
separated from surface syntax are standard: Rocq names the discipline *the de Bruijn
criterion*; Lean 4's elaborator lowers `Syntax` to `Expr`; OpenMath and MMT have
formalised cross-system semantic interchange for two decades. The full analysis, including
the specific claims this project must not make, is in `docs/research/PRIOR_ART.md`.

What v0 contributes is a kernel small enough to be an experimental control — not a new
foundation.
