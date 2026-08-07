# Research integration — decisions

**Date:** 2026-08-07 · **Verified against:** `34079d0` · **Status:** gate for all subsequent code.

## Scope and a limitation of this document

Two independent architecture research reports are described as having converged on a set
of principles. **I do not have the text of either report.** What I have is the enumerated
list of their recommendations. This document therefore classifies *those enumerated
recommendations* against measured repository state, and cannot speak to any reasoning,
caveat or supporting evidence the reports contain that did not survive into the list.

Where a recommendation is ambiguous, I state the reading I adopted. A reader with the
reports should check those readings first.

## State verified before classifying anything

Every figure below was re-measured, not inherited from the directive.

| claim in the directive | measured at `34079d0` | verdict |
|---|---|---|
| HEAD `0715bfc` | **`34079d0`** | **stale** — step 1 landed after |
| 6240 tests passing | **6252 passed, 0 failed** | stale (+12 freeze tests) |
| compositional closure 0.692 | 0.692 on the 13-specimen subset; **20/48 on the full specimen set** | see note |
| 486 atoms, 64 critical | **486 / 64** | confirmed |
| extensibility 0/9 | **0/6 probed forms accepted** (`import`, user type, relation, distribution, `fn … -> T`, signature) | confirmed |
| transformations 7/19 | per `AUDIT_RERUN.md`, not re-derived here | carried forward, labelled |

**The closure figure needs care.** 0.692 is 9/13 over the subset the original audit
probed. The full `COMPOSITION_TESTS.json` has 48 specimens and had **no runner until
now**; the first execution closes **20/48**. These are not the same measurement and must
never be compared as if they were. Stage 7 supersedes both with a purpose-built battery.

---

## Classification

### 1. Explicit proof/evidence DAG — **PARTIALLY_IMPLEMENTED → ACCEPT**

*Evidence.* `reasoning/check.py` splits `propositions` (established) from `unestablished`
and propagates obligations along premise edges (the V2 D-027 record). But acyclicity rests
**entirely on the textual-order rule** — a derivation may cite only earlier claims. There
is no graph object and **no cycle validator**: `grep -rn "def .*cycle" reasoning/` returns
nothing.

*Why that is not enough.* Textual order is a sound acyclicity argument only for
single-module, single-pass construction. It fails the moment claims arrive from an import,
a batch graph build, or any construction order that is not source order — which is exactly
the directive's E9. The existing defence is real but narrow, and its narrowness is not
documented anywhere.

**Accept**, as specified in §3. Build the explicit graph with a real validator, and keep
the ordering rule as a cheap first line rather than the only one.

### 2. Established-claim semantics — **ALREADY_IMPLEMENTED (naming defect only)**

*Evidence.* Measured: a CHECKED derivation *is* usable as a premise, and a step resting on
it inherits the open obligation and itself stays CHECKED —

```
derive d1 : y / k = 2.0 * x / k  ... by divide_both_sides(by := k)   -> CHECKED
derive d2 : 2.0 * x / k = y / k  from d1 by symmetry                  -> CHECKED
open obligations: 1
```

This is precisely the "provisional use with transitive obligations" the directive
mandates. The behaviour is correct.

**The defect is nomenclature.** The dict is called `propositions` and the code comment
calls its contents "established", which contradicts the directive's instruction not to
call a CHECKED claim established. **Accept the renaming only** — `established` vs
`provisional` — with no behavioural change. Recorded so nobody "fixes" working semantics
to match a label.

### 3. Status monotonicity — **ACCEPT_WITH_MODIFICATION**

The frozen D-034 E4 already says the opposite of naive monotonicity: evidence is **not**
monotone across runs, and nothing may treat a cached VERIFIED as durable. That is
deliberate and stays.

What is accepted is *within-run* monotonicity: a status may not be upgraded by anything
except the kernel, and no status transition may manufacture evidence (E5/E6). Adopted with
that scoping made explicit, because unqualified "monotonicity" would license exactly the
stale-VERIFIED caching D-034 forbids.

### 4. Scoped Γ — **ACCEPT** (frozen as D-035, not built)

*Evidence.* `RefinementEnv.push`/`pop` exist and **nothing calls them**; the type checker
collects module-level assumptions flat. Verified: `assume x > 0` licenses `log(x)`
module-wide, and there is no construct that scopes it.

Accept in full, including the directive's contradiction requirement — local inconsistency
must be usable for proof by contradiction and must not let a theorem escape the frame.
This is the part the freeze did **not** specify and is the substantive addition from the
research.

### 5. Uniform precondition contracts — **ACCEPT** (frozen as D-036, not built)

*Evidence.* Measured: `1.0/0.0`, `tan(x)` and `x^-1` compile with zero relevant
obligations; `log`/`sqrt` are type-guarded. Two policies, no principle.

Accepted with one modification the directive itself supplies and which I endorse:
expectation's precondition is the **tractable predicate `integrable(X)`**, not a
measure-theoretic proof obligation. Forcing the latter would make the feature unusable and
push authors to omit expectation entirely — a worse outcome than a checkable placeholder
that libraries may strengthen.

### 6. Generic application/binding expression core — **DEFER, pending measurement**

*Evidence.* 13 expression node classes, 12 `symbol_id` sites in `ast/nodes.py`; five
distinct binder implementations (`Quantifier`, `SetComprehension`, `LimitExpr`,
`DerivativeExpr`, `IntegralExpr`).

**Explicitly not accepted on the reports' say-so**, per filter A. A study is measuring
whether position-specific AST design actually causes the composition failures. Adopting a
generic core is a rewrite of the semantic contract; doing it because two reports recommend
it, before attribution, is the failure mode this directive names first.

Decision deferred to Stage 7's attribution. Stage 8 executes only if Stage 7 demonstrates
SPECIALISED_AST as a major cause.

### 7. Minimal transformation kernel — **ACCEPT_WITH_MODIFICATION**

Accept the *classification* exercise (Stage 9). **Reject the target of "fewer than 10"**
per filter B: rule count is a vanity metric, and the quantity to minimise is TCB size at
fixed trusted semantic power. A rule that is locally checkable in twenty lines costs
almost nothing and removing it buys nothing.

### 8. Declarative extensibility / content dictionaries — **ACCEPT_WITH_MODIFICATION**

*Evidence.* Measured 0/6: `import`, user type, user relation, user distribution,
`fn f(x) -> T`, and `signature` are all rejected. Extensibility is genuinely absent.

Accept the mechanism. **Reject importing OpenMath wholesale and reject any coverage
target expressed as a percentage of OpenMath** (filters F, G) — OpenMath is a useful
*shape* for declarative signatures and a useful independent coverage guide, and is not a
specification HML must satisfy. Trust rules from the frozen D-039 are unconditional: a
signature may never add a trusted inference rule or mark a claim VERIFIED.

### 9. Small trusted computing base — **ACCEPT**

Not currently documented anywhere. Accepted, with the directive's own caution adopted: the
parser is **not** automatically trusted if the canonical IR can be independently validated
after parsing. That distinction materially shrinks the TCB and is worth the validator.

### 10. Certificate-based external verification — **ACCEPT** (frozen as D-038, not built)

Accepted including the hard rule (filter J, directive §11 B/C): a raw CAS or solver success
flag **never** produces VERIFIED. Architecture and trust boundary are mandatory now; actual
Lean/Z3 integrations are not.

### 11. Explicit approximation semantics — **ACCEPT** (frozen as D-037, not built)

Accepted at the directive's scope: exact equality and bounded approximation only. IEEE
identity, asymptotic equivalence, measurement uncertainty and confidence intervals stay
**out of core** — they are library concerns over the semantic core. Filter K is already
satisfied and must remain so: `~` denotes distribution and nothing else; approximation gets
its own role-labelled form.

### 12. OpenMath / MSC ontology comparison — **ACCEPT_WITH_MODIFICATION**

Accept as an **independent coverage guide only**, exactly as §13 frames it. The 486-atom
ontology is not replaced, and no existing atom is altered to improve a score. Order is
mandatory: probe all 486 first, *then* look for absent families. Any atom added afterwards
is recorded in a separate `ADDED_AFTER_EXTERNAL_COVERAGE_REVIEW` set so no score is ever
improved by moving the denominator.

### 13. Formal-verification priorities — **DEFER**

Per filter M and §17: do not verify moving architecture. Ranking and a costed plan only,
after freeze and exhaustion. No Lean/Coq project starts in this directive.

### 14. Compiler fuzzing / exhaustion — **PARTIALLY_IMPLEMENTED → ACCEPT**

*Evidence.* `tests/fuzz/test_frontend_robustness.py` exists and passes (52 tests). It is
frontend robustness only — no semantic mutation, no metamorphic testing, no differential
checking, no bounded exhaustive enumeration.

Accept the full campaign, with the directive's stopping rule: floors are floors, and
stopping is decided by bug-discovery rate, branch/grammar/rule/obligation/ontology
coverage and mutation score — not by a round count.

---

## Summary

| # | recommendation | verdict |
|---|---|---|
| 1 | evidence DAG | PARTIAL → ACCEPT |
| 2 | established-claim semantics | ALREADY_IMPLEMENTED (rename only) |
| 3 | status monotonicity | ACCEPT_WITH_MODIFICATION (within-run only) |
| 4 | scoped Γ | ACCEPT |
| 5 | precondition contracts | ACCEPT (`integrable(X)` as tractable predicate) |
| 6 | generic Apply/Bind core | **DEFER** pending attribution |
| 7 | minimal kernel | ACCEPT_WITH_MODIFICATION (no count target) |
| 8 | declarative extensibility | ACCEPT_WITH_MODIFICATION (no OpenMath wholesale) |
| 9 | small TCB | ACCEPT |
| 10 | certificates | ACCEPT |
| 11 | approximation | ACCEPT (core = exact + bounded only) |
| 12 | OpenMath/MSC comparison | ACCEPT_WITH_MODIFICATION (guide only, after full probing) |
| 13 | formal verification | DEFER |
| 14 | fuzzing/exhaustion | PARTIAL → ACCEPT |

**Nothing is REJECTED outright.** Four filters (A, B, F/G, M) are honoured by scoping a
recommendation rather than refusing it, which is recorded here so that a later reader does
not mistake a modification for an acceptance.
