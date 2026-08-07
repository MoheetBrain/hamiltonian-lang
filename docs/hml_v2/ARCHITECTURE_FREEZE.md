# HML V2 — architectural freeze

**Status:** BINDING. **Date:** 2026-08-07. **Base:** `0715bfc`.
**Decision records:** D-034 … D-039.

This document freezes six architectural questions that steps 2–9 of the current
programme implement. After this freeze, those steps are *implementation*. Reopening any
decision here requires a new decision record that names the evidence that changed.

The freeze exists because V2 shipped three defects of the same shape: a mechanism was
half-built, and the half that was missing was the half that made it load-bearing.
`assume` discharged kernel obligations but did not narrow types (D-028). Γ had `push`
and `pop` that nothing called. `goal` was kept out of the refinement environment and let
into the premise pool (D-027). Each was a coherent idea implemented on one of two
channels. Freezing the contract first is the countermeasure.

Every decision below states what is **rejected** as well as what is chosen, because the
rejected option is what a later reader will otherwise re-propose.

---

## D-034 — Evidence semantics

**The split.** Two layers that never mix:

| | SEMANTIC IDENTITY | EVIDENCE |
|---|---|---|
| answers | what does this module *state*? | what did some checker *find*? |
| hashed by `content_hash` | **yes** | **never** |
| includes | structure, locally-nameless symbol identity, types, role labels, rule identity, premise identity **and order**, conclusion | verdicts, checker id and version, witnesses, timings, spans, durations |

**Rules.**

- **E1.** `content_hash(module)` is invariant under verification. Running the checker
  twice, running a *different* checker, or running one that crashes, must not change it.
- **E2.** An evidence record references its module by `content_hash`. Evidence is
  therefore attributable and cannot migrate to a different module unnoticed.
- **E3.** A status is evidence, not source. There is no surface syntax for `VERIFIED`,
  and there never will be. *(Already true; this freezes it.)*
- **E4.** Evidence is **not** monotone across runs. A later run may downgrade a claim.
  Nothing may treat a cached `VERIFIED` as durable.
- **E5.** Premise **order** is semantic identity, not presentation. `transitivity` on
  `(a=b, b=c)` is a different inference from the same rule on `(b=c, a=b)`.

**Why.** Hashing `sympy-1.14.0` into identity would rewrite every historical hash on a
dependency bump, and a verification regression would then be indistinguishable from a
different mathematical object. The consequence, stated plainly so nobody has to infer
it: **a content hash certifies what was claimed, never that it holds.**

**Rejected.** Embedding status in the canonical form so that a module "carries its own
proof". It would make identity depend on the prover, break E1, and let a module assert
its own verification.

---

## D-035 — Γ and scope

**Model.** Γ is a **stack of frames**, not a flat set.

| frame | opened by | depth |
|---|---|---|
| MODULE | the module itself | 0 |
| QUANTIFIER | a quantifier body | +1 |
| CONCEPT | a concept body | +1 |
| SCOPE | an explicit `scope … end` block *(new surface, step 3)* | +1 |

**Rules.**

- **G1.** No fact escapes its frame. `pop()` discards every fact at that depth.
- **G2.** An obligation is discharged only by facts visible **at the obligation's own
  frame**. An assumption made inside a scope cannot discharge an obligation outside it.
- **G3.** Γ contains facts from `assume` only. `require` and `prove` state things to be
  *shown*; admitting them would let a module license an operation by asking for the very
  thing that makes it legal. *(Already true; frozen.)*
- **G4.** Narrowing moves **down** the refinement lattice only (`Real → PositiveReal`),
  never up. An assumption can never widen a declared type.
- **G5.** Within a frame, facts are **order-independent**, matching the resolver's
  treatment of binders (D-008). Frames nest lexically. One policy, not two.

**Why a stack and not a flat set.** The flat model cannot express "assume `x > 0` for
the purposes of *this* argument", which is what a case split, a proof by contradiction
and a bounded lemma all need. It is also the reason maturity criterion 3.3 fails and
`COMP.LOCAL_ASSUMPTION_IN_SCOPE` fails.

**Rejected.** Making assumptions procedural (visible only after the line on which they
appear). It reads naturally but contradicts D-008, under which module scope is
order-independent, and would mean the same program means different things depending on
statement order — the property HML exists to eliminate.

---

## D-036 — Definedness: precondition contracts

**The problem being fixed.** Measured at `0715bfc`, HML has two policies and no
principle distinguishing them:

| expression | accepted | obligation generated |
|---|---|---|
| `log(x)` on `x : Real` | **no** | — (rejected by argument type) |
| `sqrt(x)` on `x : Real` | **no** | — (rejected by argument type) |
| `1.0 / x` | yes | **none** |
| `1.0 / 0.0` | yes | **none** |
| `tan(x)` | yes | **none** |
| `x ^ (0-1)` | yes | **none** |

The audit called this "not a design, a pair of special cases". It is right.

**Decision: every operation carries a partiality classification, and the classification
is data.**

| class | meaning | obligation |
|---|---|---|
| **TOTAL** | defined on all of its domain type | none |
| **GUARDED** | the argument *type* restricts the domain; out-of-domain is a static type error | none — the type rule is the guard |
| **CONTRACTED** | defined on a subset expressible as a proposition | **always generates a mandatory precondition** |
| **PARTIAL_UNDECIDABLE** | mathematically partial, precondition not expressible in HML's proposition language | records the limitation explicitly; never silently total |

**Assignment** (step 4 implements; this freezes the target):

- TOTAL — `+ - *`, `exp`, `sin`, `cos`, `abs`
- GUARDED — `log` (`PositiveReal`), `sqrt` (`NonNegativeReal`)
- CONTRACTED — division (`divisor != 0`), `tan` (`cos(x) != 0`), negative/fractional
  powers (`base != 0`), indexing (`0 <= i < n`), matrix inverse (`invertible(A)`),
  conditional probability (`P(B) > 0`), expectation (integrability), normalisation
  (`total != 0`)
- PARTIAL_UNDECIDABLE — limit existence in general

**Rules.**

- **D1.** Every operation is classified. The classification lives in one registry.
- **D2.** A CONTRACTED operation **always** generates its obligation. Γ may discharge
  it. Undischarged ⇒ OPEN ⇒ the enclosing claim cannot be VERIFIED.
- **D3.** Only Γ discharge clears an obligation. Writing `require x != 0` does not.
- **D4.** An operation with no classification is a **build error**, enforced
  mechanically over the registry — not by review.
- **D5.** An obligation Γ can **refute** (`0 != 0`) is `FAILED`, not `OPEN`. Refutation
  is information and must not be reported as ignorance.

**Rejected, with the reason each is wrong *here* rather than wrong in general.**

- **Totalisation** (Lean: `(1:Nat)/0 = 0` by `rfl`). Defensible for a proof assistant
  with a full logic behind it. Rejected for HML because HML's product is *surfacing* the
  condition to a model that must repair; totalising hides exactly the signal the repair
  loop consumes.
- **Underspecified total functions** (SMT-LIB). Same objection.
- **Error propagation** (`NaN`, OpenMath `OME`). Rejected on mechanism: HML performs no
  value-level evaluation, so there is nothing to propagate.

---

## D-037 — Approximation

**Decision.** Approximation is a **distinct relation**, never equality.

Surface: `approx(a, b, bound := eps)` — role-labelled, consistent with D-003.

- **A1.** `approx` and `=` have different canonical identity. No coercion path exists in
  either direction, in the same way `Distribution[T]` and `T` have none.
- **A2.** Approximation does **not** chain silently. Two approximations compose only
  through explicit bound arithmetic; a derivation that chains them without summing
  bounds stays OPEN. *(An unchecked transitive `≈` is how error analysis is lost.)*
- **A3.** Every backend reports approximation as a loss unless it can carry the bound.
- **A4.** An approximation carries a bound, or is explicitly `UNBOUNDED` — which is
  recorded, never omitted. "Approximately equal, amount unspecified" is a legitimate
  thing to state and an illegitimate thing to leave implicit.

**Why this is not optional.** Maturity criteria 3.6 and 3.7 both fail today for want of
any approximation status or relation, and a reasoning IR that cannot distinguish "equals"
from "equals to within ε" cannot represent numerical mathematics at all.

---

## D-038 — Verifier evidence and certificates

**Decision.** One evidence path, for internal and external checkers alike.

```
Certificate {
    module_hash      # binds to exactly this module (D-034 E2)
    claim_id         # what was checked
    obligation_id    # or None for a whole-derivation check
    checker_id       # "hml-kernel" | "z3" | "lean" | "sympy" | ...
    checker_version  # exact, e.g. "sympy-1.14.0"
    verdict          # DISCHARGED | REFUTED | UNSUPPORTED | INCONCLUSIVE | TIMEOUT
    witness          # counterexample or proof term, optional
    produced_at
}
```

- **V1.** No external verdict changes an HML status without a Certificate.
- **V2.** `UNSUPPORTED` ("no theory for this") and `INCONCLUSIVE` ("tried, could not
  decide") are **distinct** and never collapse into "not proved". *(`records.py` already
  refuses to collapse them; frozen.)*
- **V3.** The trusted kernel emits certificates too, with `checker_id = "hml-kernel"`.
  One path, not two — so no verdict can arrive by a route that has no evidence record.
- **V4.** A certificate is evidence, so it never enters `content_hash` (E1).
- **V5.** `REFUTED` makes the claim **REJECTED**, not OPEN.
- **V6.** A `TIMEOUT` is never an approximation of `DISCHARGED`.

---

## D-039 — Extension trust

**Decision.** A three-level lattice with a strict one-way rule.

| level | what | may reach `VERIFIED`? |
|---|---|---|
| **CORE** | the trusted kernel — 16 rules today | **yes** |
| **LIBRARY** | definitions, relations and types the compiler can *check* by reduction to CORE | **yes**, and only because the check reduces to CORE |
| **USER** | anything whose justification the compiler cannot check: a user-asserted inference rule, an opaque imported lemma, a backend-asserted fact | **never** — best status is `ASSUMED` |

- **X1.** Trust never flows upward. A USER rule does not become CORE by being used
  often, by being imported, or by any annotation in source. There is deliberately no
  `trusted` keyword.
- **X2.** **A claim's effective trust is the MINIMUM over its dependency closure.** This
  is the rule that makes the lattice do work rather than decorate: one USER premise taints
  everything downstream, exactly as one undischarged obligation does (D-027).
- **X3.** Adding to CORE requires a decision record, a soundness argument, and a
  rejection test — the new rule must be shown to reject a step differing *only* in its
  stated conclusion.
- **X4.** `import` never grants trust. An imported claim arrives at its recorded level,
  capped at LIBRARY.

**Why.** The V2 directive's §15G asks for the boundary to be designed now and the
capability deferred. This is that boundary. The failure it prevents is the one that
makes a reasoning system worthless: a user-defined rule that is automatically believed,
so that "VERIFIED" comes to mean "somebody wrote a rule that said so".

---

## What this freeze does *not* decide

Recorded so no reader infers coverage from silence.

- **Whether the AST needs a generic Apply/Bind/Attribute core.** That is step 5's fork
  and is being measured, not assumed. Every decision above is written to hold under
  either answer.
- **The compositional-closure target.** 0.692 measured; 0.85 targeted; no route to it is
  frozen here because the route depends on step 5.
- **Module and import syntax.** D-039 fixes what `import` may *mean* for trust; it does
  not fix its spelling.
- **Whether `prove` is migrated to a goal.** `GRAMMAR_CONTRACT.md` §1 says it becomes a
  goal with `ASSERTED_UNCHECKED`; the implementation leaves it a `ProveStmt` with no
  status. The divergence is real and is deferred to step 6, not resolved here.
