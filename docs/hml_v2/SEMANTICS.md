# HML v2 — reasoning constructs against the existing semantic barriers

**Status: normative.** Companion to `REASONING_MODEL.md`. This file answers one question
for each of HML's existing semantic commitments: *what does a reasoning transition have to
respect here, and what would break if it did not?*

It then answers the question the lead singled out: **what belongs in the canonical hash of a
derivation, and what must not.**

Base SHA `3dd4216` (`src/` byte-identical to audited `b1ac7bf`). Measurements were taken
against a pristine `git archive HEAD src` export.

---

## 0. The governing constraint

V0's type system is the project's strongest measured property. The audit puts it ahead of
the comparison panel on four axes and records that "the RV / distribution / value barrier is
enforced in the type system", against SymPy where "`RandomSymbol > Expr` — an RV *is* an
expression".

A reasoning layer is the most dangerous thing you can add to a system like that, because
**every inference rule is a potential coercion**. `substitute` can put a `Distribution`
where a value was; `apply_theorem` can put a `PValue` where a `PosteriorProbability` was;
`universal_instantiation` can capture a bound variable. Each of those is a barrier breach
performed by a rule rather than by a type annotation, and the type checker never sees it
unless the kernel asks.

> **The rule that governs this whole document: a derivation step is type-checked as if the
> conclusion had been written by hand.** A rule may not conclude anything the source could
> not have stated. There is no "derived" path that bypasses `type_system/__init__.py`.

That single rule closes most of what follows. The rest of this file is the cases where it is
not sufficient.

---

## 1. RandomVariable vs Distribution vs value

The barrier: `RandomVariableType`, `DistributionType` and the underlying `T` are three
distinct constructors with no subtyping path between them (`types.py:396-413`,
`is_subtype` lines 492-496 relate each constructor only to itself).

### 1.1 What a rule may not do

| forbidden | why |
|---|---|
| a rule that concludes `X = e` where `X : RandomVariable[T]` and `e : T` | that is the identification the type system exists to prevent |
| a rule that treats a `DistExpr` as a value of its support | `Distribution[T]` is a law, not a sample |
| `substitute` binding a name of one of the three to an expression of another | substitution is the general form of the two above |

`substitute` is the case that needs the most care, because it is the rule with the widest
reach and the loosest spec: `Operation.SUBSTITUTE` has no `required_arguments` and no
obligations at all (`v1/transformation.py:400-406`). Its whole safety comes from the
governing constraint: the substituted result is re-typed, and a substitution that produces
an ill-typed conclusion is `REJECTED` with the ordinary type diagnostic, located at the
derivation.

### 1.2 What a rule must record

`Operation.TAKE_EXPECTATION` already carries the correct weakening: *"an identity between
random variables is strictly stronger than an identity between their expectations:
`E[X] = E[Y]` does not recover `X = Y`"*. This is a `Weakening`, not an obligation, and the
distinction is right — it is not something you can discharge, it is information the step
destroyed.

V2 requirement: **a weakening is carried on the derivation and propagates to every
downstream derivation that uses it as a premise.** A conclusion reached through a weakening
step is not reversible, and the English and LaTeX renderings must say so. `ChainReport`
already accumulates weakenings; V2 must make them transitive, which it currently is not.

### 1.3 Known hole, inherited

The audit's C-7 records that `law y ~ Normal(...)` on a plain `var y : Real` compiles clean,
and `y` is then usable as an ordinary `Real`. That is a v0 defect and V2 does not fix it,
but V2 makes it *reachable by inference*: a derivation over `y` would inherit the confusion.
This model does not claim to close C-7. It is recorded here so that a reader does not
mistake the barrier for airtight.

---

## 2. Probability vs PValue vs PosteriorProbability

The barrier: the three are pairwise incomparable scalars meeting at `NonNegativeReal`
(`types.py:92-106`), with no coercion admitted in either direction
(`epistemic.py::PROHIBITED_PROBABILITY_COERCIONS`).

### 2.1 The numeric coincidence is the hazard

All three occupy `[0, 1]`, and `verification/obligations/domains.py:198-203` gives all three
**the same interval**, with a comment that says so and states the mitigation: "this table is
consulted by name, never by subtyping".

That mitigation holds today because the discharge engine keys domains by *name*, and each
name carries exactly one declared type. Measured:

```
param p : Probability          prove p >= 0.0   → DISCHARGED  ([0,1] satisfies >= 0)
param q : PValue               prove q <= 1.0   → DISCHARGED  ([0,1] satisfies <= 1)
```

Both discharged from their own declared type. No cross-kind step occurred, because there was
nothing that could take one.

### 2.2 What V2 adds, and the rule it needs

Substitution is the first construct that can replace one name by another. Under interval
reasoning alone, substituting a `PValue` for a `PosteriorProbability` is invisible: the
intervals are identical, so every obligation that held before still holds after.

> **Rule.** Before any interval or numeric reasoning, a substitution is checked against
> `probability_coercion_allowed(source_kind, target_kind)`. A non-identity pair is
> `REJECTED` (`HML-R910`) carrying the prohibition's own recorded reason — for the
> `PValue → PosteriorProbability` case, "Reading a p-value as a posterior is the
> prosecutor's fallacy".

This is not a new policy. It is the existing policy applied at the one new place where it can
be evaded. *Test:* `test_substitution_cannot_cross_probability_kinds` — a derivation
substituting a `PValue`-typed name where a `PosteriorProbability` is expected is REJECTED,
and the diagnostic text contains the recorded reason rather than a generic type message.

---

## 3. Dimensions

The barrier: dimensions are rational-exponent vectors over seven SI bases, so dimensional
algebra is exact and decidable (`types.py:150-318`); a dimension carrying an unresolved
variable "is not dimensionless — it is unknown, which is a different thing and must not be
silently treated as scalar".

### 3.1 Rules must be dimensionally closed

Every catalogue rule is dimension-preserving or dimension-computing, and the kernel checks
which. `differentiate wrt t` divides the dimension by `Time`; `integrate wrt t over I`
multiplies by it. A rule that cannot state what it does to a dimension may not be applied to
a dimensioned quantity: `UNKNOWN`, not a guess.

### 3.2 Numeric discharge over dimensioned quantities stays refused

`domains.py::domain_of_type` returns `None` for a dimensioned `Quantity`, with the reason
stated in place: "its numeric value is unit-relative, so comparing it against a bare literal
is not a well-posed numeric question and pretending otherwise would be exactly the
silent-coercion failure this codebase forbids."

V2 changes nothing here. An obligation such as `{by} != 0` where `by : Quantity[Length]` is
**UNKNOWN**, not discharged by interval reasoning, and consequently blocks VERIFIED. This is
restrictive and it is correct. The dimensional *structure* is still checkable — that a
divisor is dimensionally well-formed is a `STRUCTURAL` obligation and
`DimensionCompatibilityChecker` already decides it — but the *value* question is not.

---

## 4. Semantic identity versus execution and evidence metadata

This is the split the lead asked for. It is the most consequential decision in the file, so
the criterion is stated first and then applied.

> **The criterion.** A field belongs in the canonical form iff **two objects differing only
> in that field are different mathematics.** Everything else is metadata about the *checking
> process*, and lives in the `VerificationOutcome` / `ObligationRecord` layer.

### 4.1 The split

**SEMANTIC IDENTITY — in the canonical form, in the content hash**

| field | why it is mathematics |
|---|---|
| statement kind (`Goal`, `Derivation`, `Discharge`, …) | a goal and a derivation are different objects |
| the goal's proposition, canonicalised as an `Expr` | changing it changes what is claimed |
| the derivation's rule name | `divide_through` and `multiply_both_sides` are different inferences |
| the derivation's premises, as **canonical claim ids** (`claim:#<ordinal>`) | which facts were used is part of the argument |
| the rule's role-labelled arguments, **sorted by role**, values canonicalised as `Expr` | dividing by `k` and dividing by `2` are different steps |
| the derivation's stated conclusion, canonicalised as an `Expr` | it is the content of the claim |
| the **generated obligation set**, as canonical propositions with their `ObligationKind` | what the step owes is determined by the step; two arguments owing different things are different arguments |
| the recorded `Weakening`, if any | what the step irreversibly lost is a property of the mathematics |
| the discharge's *target obligation* and *evidence claim id* | which fact was used to close which condition is part of the argument's structure |

**EXECUTION / EVIDENCE METADATA — excluded from the canonical form and the hash**

| field | why it is not mathematics |
|---|---|
| `DerivationStatus`, `GoalStatus`, `ObligationStatus` | a verdict about the object, not the object |
| checker name, checker version, engine version | *who* decided, not *what* was claimed |
| the discharge witness / evaluated values / bindings | evidence for a verdict |
| `rejection_reason`, `detail`, `checkers_attempted` | diagnostic text |
| spans, file names, line numbers | already excluded for every v0 statement |
| the human-readable claim **label spelling** | a binder; excluded for the same reason `SymbolId` names are |
| timestamps, run ids, machine identity | not mathematics under any reading |

### 4.2 Why the split falls exactly there — two arguments

**(a) Reproducibility of historical evidence.** `content_hash` is the identity used across
this repository's evidence chain — `engine.py` records it on every `VerificationOutcome`,
and `_roundtrip_loss` compares it to detect surface loss. If checker version were part of
the hash, upgrading SymPy (the `SymbolicIdentityChecker` is versioned `sympy-1.14.0`) would
rewrite the identity of every derivation that used it, and every ACQ0/H2 record would cease
to be reconstructible. The mathematics did not change; the tool did.

**(b) Falsifiability.** If status were in the hash, "is this the same derivation?" and "did
it check?" become one question, and a regression — the same object, a different verdict —
becomes undetectable, because the two runs would produce different hashes and look like
different objects. Keeping them separate is what makes it possible to say *this exact
derivation used to be VERIFIED and now is not*, which is the only useful form of a
verification regression report.

The codebase has already made this decision, for the same reason, at the module level:
`VerificationOutcome` carries `content_hash` **and** `evidence_digest` as two separate
fields, one for the object and one for the run. V2 is the same design one level down.

### 4.3 The consequence that must be stated in words

A content hash **certifies what was claimed; it never certifies that the claim holds.**

Two modules with the same content hash contain the same derivation. One may be VERIFIED and
the other REJECTED — for example, because a checker was upgraded, or because one run had a
timeout. Any tool, report or dashboard that treats "hash matches a known-good hash" as
"verified" is reading the artefact wrongly. This is worth a note in the CLI output and a
sentence in `MIGRATION_V1_TO_V2.md`.

The corresponding property is a test:
`test_status_not_restorable_from_canonical` (`REASONING_MODEL.md` §2.2(d)) — reparse a
serialised VERIFIED module and assert every derivation is back at `PROPOSED`. If it is not,
status has leaked into the surface and the split has failed.

### 4.4 Why obligations *are* in the hash, though records are not

An obligation has two aspects and they separate cleanly. Its **statement** — the proposition
`k != 0`, tagged `SIDE_CONDITION`, generated by `divide_through` — is determined by the
mathematics and belongs in the hash: an argument that owes `k != 0` is a different argument
from one that owes nothing. Its **record** — status, checker, witness, evidence — is a
verdict and does not.

This resolves a live inconsistency at the base. `to_canonical` accepts an `obligations`
parameter and emits a `proof_obligations` key, but `content_hash` deliberately excludes it,
with the docstring reason "Proof obligations are excluded too, because they carry source
line numbers" (`backends/canonical.py:280-287`). The exclusion is right; the *reason* given
is the wrong one — line numbers are metadata that should simply not be in the obligation's
canonical projection. V2's rule is precise: **the canonical projection of an obligation is
`(canonical proposition, ObligationKind, generating rule, generating derivation's claim
id)`, and it is hashed.** Nothing about a verdict, a span or a checker enters it.

### 4.5 Backward compatibility, measured

The lead's locked rule is that a module using no V2 construct must produce byte-identical
canonical JSON and the same `content_hash`. **This is achievable, and it was tested.**

`_statement` dispatches by `isinstance` and returns per-statement dictionaries; `_to_canonical`
adds no module-wide derived value. A module containing no V2 statement therefore serialises
through exactly the same branches as before. Measured on the pristine base, defining a new
`Statement` subclass and recompiling:

```
A. V1-only module unchanged by class addition : True   (hash 8b3acca3691c334c…)
```

**It is achievable but it is not free, and one item of the locked plan currently violates
it.** `GRAMMAR_CONTRACT.md` §5 says `canonical_json` *gains* `"spec_version": 2`. Adding any
top-level key unconditionally changes every hash. Measured, using an unconditional field
addition as the demonstration:

```
baseline hash : cc1c1a002958408c9f601d7ab51199a56055e10b83afc5d43e6ff28769fb20a1
after   hash  : a4c37069e480d5fea44da4e7930608409b8acf3b149c7e5b39ffa593924f9cd1
BYTE-IDENTICAL: False
```

Three conditions are therefore necessary and, together, sufficient:

1. **`CANONICAL_VERSION` must not be bumped.** It is emitted on every document
   (`canonical.py:259`). Bumping it changes every hash in the repository's history. This
   creates a real tension with the field's stated purpose — "tagging the schema version so a
   future change is detectable rather than silent" — which is discussed as
   `DESIGN_LOCK.md` D-V2-006.
2. **Any V2 key is emitted only when the module actually uses a V2 construct.** A predicate
   over the statement list — `uses_v2(module)` — gates it. The implementation workstream has
   already written this predicate; this document makes it normative and requires that its
   definition include *every* V2-introduced field, not only the new statement kinds. In
   particular, if a `label` is added to `AssumeStmt`, a module whose assumptions are all
   unlabelled must serialise as it did before, which means the key is omitted rather than
   emitted as `null`.
3. **`spec/ir.schema.json` must be extended in the same change.** It is not optional:
   verified here,

   ```
   fallthrough doc REJECTED by schema: 'DeriveStmt' is not one of
     ['Declaration','Definition','Law','Assumption','Constraint','Theorem',
      'Objective','Solve','Inference','Check','Concept']
   spec_version doc REJECTED by schema:
     Additional properties are not allowed ('spec_version' was unexpected)
   ```

   Both rejections come from the schema's `statement.kind` enum and its top-level
   `additionalProperties: false`. Extending an enum and adding an optional property are
   additive changes that keep every existing document valid.

The gate is a test, not an intention. `GRAMMAR_CONTRACT.md` §5 already names it
(`test_v1_canonical_identity_is_unchanged`). It should compare **recorded hashes committed
as fixtures**, not hashes recomputed by the same build — otherwise a change that alters
every hash consistently would pass.

---

## 5. Quantifier scope and alpha-equivalence

Two properties the audit scores `PASS` (2.4) and `PASS (partial)` (2.8). V2 is the first
thing that can break either.

### 5.1 Scope order is structural and must stay so

`forall x . exists y . P` and `exists y . forall x . P` are different trees and different
canonical hashes (`nodes.py:203-217`; the audit re-measured it). Any rule that reorders or
introduces a binder — `universal_instantiation`, `existential_generalisation`, and the new
binding expression forms in `GRAMMAR_CONTRACT.md` §2 — must go through the existing
`Quantifier` machinery. The grammar contract already requires this for the expression forms
and calls it "a hard requirement, not an optimisation". The same requirement applies to
rules.

### 5.2 Capture-avoidance stops being untested

The audit's note on 2.8 is precise: *"Capture-avoidance is untested because HML has no
substitution statement."* `Operation.SUBSTITUTE` is a substitution statement. The moment it
lands, criterion 2.8's currently-partial PASS becomes fully load-bearing, and the classic
capture bug becomes reachable:

```
premise    : forall y : Real . x < y
substitute : x := y                       -- naive substitution captures y
wrong      : forall y : Real . y < y
correct    : forall y' : Real . x[x:=y] < y'      (rename the binder first)
```

**Rule.** Substitution is capture-avoiding: a binder whose name occurs free in the
substituted term is alpha-renamed before the substitution. A kernel that does not do this is
unsound, and the unsoundness is silent — the result type-checks.

*Tests, required before `substitute` is admitted to the trusted set:*
`test_substitution_avoids_capture` over a fixture table (the case above, plus nested
binders, plus a binder shadowed in the substituted term), and
`test_substitution_preserves_content_hash_under_alpha_renaming`.

Note that HML's resolver rejects shadowing outright (`HML-N302`, D-006), which removes one
whole class of capture at the *source* level. It does not remove it at the *derived* level,
because a derived binder never passes through the resolver's shadowing check unless the
kernel re-runs resolution on the conclusion. Per §0, it must.

### 5.3 Claim labels are binders

`d1`, `g1`, `a1` are names in a namespace disjoint from values. They must be canonicalised
positionally — `claim:#<ordinal>` — exactly as `SymbolId.canonical()` produces
`sym:#<depth>.<ordinal>`, so that renaming `d1` to `step_one` leaves the content hash
unchanged. The implementation workstream has already written this; it is endorsed and made
normative here.

Two consequences worth stating because they are easy to get wrong:

* the ordinal must be assigned by a **deterministic** traversal (declaration order in the
  statement list), or alpha-invariance fails non-deterministically;
* claim labels must **not** be resolvable as values. `d1 + 1` is a scope error
  (`HML-R902`), not a type error. Sharing the namespace would let a derivation be smuggled
  into an expression, and then provenance would be inside the mathematics, defeating §4.

---

## 6. Summary of new rules imposed by this document

| # | rule | enforced by |
|---|---|---|
| S1 | a derived conclusion is type-checked as if hand-written | re-run `type_system.check` on the conclusion |
| S2 | a rule may not conclude across the RV / Distribution / value barrier | S1, plus explicit `substitute` check |
| S3 | weakenings propagate transitively to downstream derivations | kernel; currently non-transitive in `ChainReport` |
| S4 | substitution across probability kinds is REJECTED with the recorded reason | `probability_coercion_allowed` |
| S5 | a rule that cannot state its dimensional effect may not apply to a dimensioned quantity | rule catalogue metadata |
| S6 | numeric discharge over dimensioned quantities stays refused → UNKNOWN | `domain_of_type` returning `None` |
| S7 | status, checker, witness, span, label spelling are excluded from the hash | canonical serialiser + `test_status_not_restorable_from_canonical` |
| S8 | obligation *statements* are hashed; obligation *records* are not | canonical projection of an obligation |
| S9 | `CANONICAL_VERSION` is not bumped; V2 keys are gated on `uses_v2` | `test_v1_canonical_identity_is_unchanged` against committed fixtures |
| S10 | substitution is capture-avoiding | fixture table, required before `substitute` is trusted |
| S11 | claim labels are binders, canonicalised positionally, not resolvable as values | claim resolver |

**Implementation status of every rule in this table: NOT IMPLEMENTED, NOT TESTED.** The
measurements quoted in this document are of the *existing* base, not of V2.
