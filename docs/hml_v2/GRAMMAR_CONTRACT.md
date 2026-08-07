# HML v2 — frozen surface-syntax contract

**This file is the integration contract.** It is fixed by the lead integrator before any
implementation begins, so that five parallel workstreams cannot invent conflicting syntax.
Any agent that believes a form here is wrong must say so and stop, not improvise.

Base SHA `3dd4216`. `src/` is byte-identical to the audited SHA `b1ac7bf`, so every audit
finding applies to this base unchanged.

---

## 0. Design rules that constrain every choice below

1. **Keyword-led, one statement per line.** This is HML v1's existing shape and it is the
   single biggest reason a model can write it. Do not introduce blocks, indentation
   significance, or multi-line statements.
2. **Reuse existing punctuation.** `:` type/proposition annotation, `:=` definition,
   `~` distributed-as, `|` given. Do not add new sigils where an existing one fits.
3. **Every new construct must compose as an expression of its result type**, subject only to
   type and domain rules. Composition is the measured target (0.615 → ≥ 0.85); it is not
   achieved by adding forms, it is achieved by not special-casing them.
4. **Nothing is `VERIFIED` unless a checker established it.** The word is reserved.
5. **Semantic identity must not absorb evidence metadata.** Provenance is part of the
   reasoning graph; it must not change the content hash of the mathematics.

## 1. New statement forms — exactly five

```
goal        <name> : <proposition>
derive      <name> from <ref> [, <ref>]* by <rule> [( <role> := <expr> [, ...] )] yields <proposition>
obligation  <name> : <proposition>                    # normally generated; declarable for tests
discharge   <name> by <ref>
proved      <name> by <ref>
```

Rationale for each, against the audit:

* `goal` separates *what we are trying to establish* from `require` (a constraint that must
  hold) and from `prove` (v1's word, which established nothing).
* `derive` is the missing centre. It carries premises, rule identity, parameters and output,
  which is exactly the tuple the audit found 0/19 representable.
* `obligation` makes side conditions first-class objects rather than compiler-internal state.
* `discharge` is the only way an obligation leaves `OPEN`, and it must name its evidence.
* `proved` is the only way a goal becomes `PROVED`, and it must name a *verified* derivation.

**`prove` (v1) is retained and RECLASSIFIED.** It parses exactly as before and now produces a
`goal` with status `ASSERTED_UNCHECKED`. It never yields `PROVED`. v1 files keep parsing;
their canonical identity is versioned (§5).

## 2. New expression forms

```
E[ <expr> ]                    expectation
E[ <expr> | <expr> ]           conditional expectation
P( <prop> )                    probability of an event
P( <prop> | <prop> )           conditional probability
joint( <ref>, <ref> [, ...] )
independent( <ref>, <ref> [, ...] )
independent( <ref>, <ref> given <ref> )      conditional independence

<expr> in <expr>               set membership
{ <name> : <Type> | <prop> }   set comprehension

limit( <expr>, <name> -> <expr> )
derivative( <expr>, <name> )
integral( <expr>, <name>, <expr>, <expr> )
continuous( <expr>, <expr> )                 f, domain

implies( <prop>, <prop> )      # distinct from =>, which stays an operator
associated( <ref>, <ref> )
correlated( <ref>, <ref> )
causes( <ref>, <ref> )
```

`E[...]` and `P(...)` are chosen over `expectation(...)`/`probability(...)` as the *primary*
surface because they are the notation the mathematics actually uses, which matters for model
writability. `expectation(x)` remains available as a plain call once the keyword is freed
(§4), and both canonicalise identically.

**Binding forms.** `limit`, `derivative`, `integral` and `{ ... | ... }` all BIND a name.
They must go through the existing quantifier binder machinery so that alpha-equivalence and
scope work without new code paths. This is a hard requirement, not an optimisation: HML's
alpha-equivalence is a measured strength and must not be bypassed.

## 3. Verification and obligation state machines

Finite, closed, and no probabilistic states.

```
DerivationStatus : PROPOSED -> CHECKED -> VERIFIED
                            \-> REJECTED
ObligationStatus : OPEN -> DISCHARGED
                        \-> FAILED
                        \-> UNKNOWN
GoalStatus       : OPEN -> PROVED | REFUTED | ASSERTED_UNCHECKED
```

Transition rules, enforced by the checker:

* `PROPOSED` — the source stated it. Nothing checked.
* `CHECKED` — the rule applied: input shape matched, output shape follows.
* `VERIFIED` — `CHECKED` **and** every mandatory obligation is `DISCHARGED`.
* A goal reaches `PROVED` only via `proved g by d` where `d` is `VERIFIED`.
* `UNKNOWN` is the honest default when the discharge procedure cannot decide. **Never guess.**

## 4. Keyword changes

| keyword | v1 state | v2 action |
|---|---|---|
| `expectation` | reserved; shadows a working `_aggregate_type` rule | **REMOVE from KEYWORDS** — unshadows the builtin |
| `variance` | reserved; shadows a working `_aggregate_type` rule | **REMOVE from KEYWORDS** — unshadows the builtin |
| `unique` | reserved; no parser production | **IMPLEMENT** as `unique <name> : <T> . <prop>` (∃!) |
| `fn` | reserved; no parser production | **IMPLEMENT** as the user-function form (§15A) |
| `map` | reserved; no parser production | **REMOVE** — no design requires it; zombie syntax |
| new | — | `goal derive obligation discharge proved by yields from rule relation import in given` |

Every removal is a migration note in `MIGRATION_V1_TO_V2.md`.

## 5. Versioning

`canonical_json` gains `"spec_version": 2`. v1 modules — those using no v2 construct —
**must canonicalise byte-identically to their v1 form under spec_version 1**, so historical
ACQ0/H2 evidence stays reconstructible. This is a test, not an intention:
`test_v1_canonical_identity_is_unchanged` compiles every committed v1 example under both
versions and compares content hashes.

## 6. What is explicitly NOT built

Named here so no agent drifts into it: no tactic language, no proof search, no unrestricted
rewriting, no dependent type theory, no theorem library, no package manager, no
user-definable *trusted* inference rules, and no model calls of any kind.
