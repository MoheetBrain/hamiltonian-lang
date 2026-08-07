# HML v2 — the obligation model

**Status: normative.** Companion to `REASONING_MODEL.md` (states and the composition rule)
and `SEMANTICS.md` (what is hashed). This file covers the four things an obligation does:
it is **generated**, it **propagates**, it is **discharged** or not, and it **gates**.

Base SHA `3dd4216` (`src/` byte-identical to audited `b1ac7bf`). Measurements were taken
against a pristine `git archive HEAD src` export, because the working tree is being edited
concurrently.

---

## 0. Why this file is the one that decides whether V2 is real

Maturity criterion 3.4 is *"side conditions are generated, not assumed: using a partial
operation (division, inverse, log, square root) produces an inspectable obligation."* HML
fails it today: `1.0 / 0.0` compiles clean and `1/x` emits no obligation. Criterion 3.5 is
the transformation-with-a-preservation-check. Together the ladder calls them "the
distinguishing capability" of a reasoning IR.

A reasoning layer that generates obligations and can never discharge one satisfies 3.4 and
still leaves the project where it started, because every derivation would sit at UNKNOWN
forever. Generation is the easy half. **Discharge is the half that has to be conservative and
still non-empty**, and that is what §4 and §6 are about.

`MINIMAL_SEMANTIC_BASIS.md` §5 makes a further demand this file has to answer: HML's
treatment of partiality is currently "not a design, it is a pair of special cases" — `sqrt`
and `log` restricted by argument type, division, `tan`, `^` and indexing unguarded, with no
stated principle. §2.3 states the principle.

---

## 1. What an obligation is

```
Obligation
  identity   : (generating derivation's ClaimId, template index, instantiation)
  proposition: Expr                      -- NOT a string; see §7
  kind       : ObligationKind            -- SIDE_CONDITION | HYPOTHESIS | CASE_SPLIT
                                         --   | DIRECTION | CONVERSE
  mode       : ObligationMode            -- UNIVERSAL | SATISFIABLE | STRUCTURAL
  mandatory  : bool                      -- derived, never stored: see REASONING_MODEL §4.2
  status     : OPEN | DISCHARGED | FAILED | UNKNOWN
  record     : ObligationRecord | None   -- provenance; excluded from the hash
```

`mode` is reused verbatim from `verification/obligations/records.py::ObligationMode`, whose
docstring states the reason it exists: *"Treating a `require` as `UNIVERSAL` produces
confident false failures on perfectly good programs; treating a `prove` as `SATISFIABLE`
produces confident false successes. Both are worse than reporting nothing."* A rule-generated
side condition is `UNIVERSAL`: `k != 0` must hold for every admissible assignment, not merely
for one.

`mandatory` is **derived, not stored**: it equals the `asserted` flag of the operation that
generated the obligation (`REASONING_MODEL.md` §4.2). Storing it would create a second place
where the answer lives.

---

## 2. Generation

### 2.1 From a rule application

The kernel instantiates every entry of the applied operation's `OperationSpec.obligations`,
plus one per item of `per_item_obligation` where present. The catalogue is already complete
in this respect — verified by execution: 30 operations, 30 specs, no operation missing a
spec. Examples, quoted from `v1/transformation.py`:

| operation | generates | kind |
|---|---|---|
| `divide` / `divide_through` | `{by} != 0` | `SIDE_CONDITION` |
| `cancel` | `{factor} != 0` | `SIDE_CONDITION` |
| `take_log` | `{of} > 0` | `SIDE_CONDITION` |
| `sqrt_both_sides` | both sides `>= 0`; **and** a `CASE_SPLIT` for the sign branch | two |
| `differentiate` | differentiability wrt `{wrt}` on the domain | `SIDE_CONDITION` |
| `apply_theorem` | the hypotheses of `{warrant}` hold, one obligation per hypothesis | `HYPOTHESIS` |
| `equivalent` | `{source} implies {target}` **and** `{target} implies {source}` | two `DIRECTION` |
| `converse` | the converse is neither established nor refuted | `CONVERSE` (advisory) |
| `square_both_sides` | *nothing* — it records a `Weakening` instead | — |

The last row is the design working. Squaring is not a step with a side condition; it is a
step that destroys information, and `Weakening` is a different object from `Obligation`
precisely because you cannot discharge it.

### 2.2 From partial operations in ordinary expressions

Rule application is not the only generator, and if it were, criterion 3.4 would still fail:
`1.0 / 0.0` appears in an ordinary expression, not in a `derive`.

**Rule.** The type checker generates a `SIDE_CONDITION` obligation at every occurrence of a
partial operation, whether or not it appears inside a derivation. There is machinery for this
already — `checkers.py::partiality_risk` exists and is consulted — but nothing emits an
obligation from an ordinary expression today.

### 2.3 The definedness policy, stated for the first time

`MINIMAL_SEMANTIC_BASIS.md` §5 records that HML has no policy, and that any of the five
observed treatments applied consistently would be defensible. This is the sixth, stated
consistently:

> **HML restricts by argument type where the restriction is expressible in the scalar
> lattice, and generates an obligation where it is not. It never totalises and never
> propagates a NaN.**

Applied:

| operation | mechanism | note |
|---|---|---|
| `log` | argument type `PositiveReal` | already implemented |
| `sqrt` | argument type `NonNegativeReal` | already implemented |
| `/`, `%` | **obligation** `divisor != 0` | not expressible as a type: the divisor is an expression, not a declaration |
| `^` with non-integer exponent | **obligation** `base >= 0` | |
| `tan` | **obligation** `cos(arg) != 0` | |
| indexing | **obligation** `index in bounds` | `STRUCTURAL` where the extent is known |
| matrix inverse | **obligation** `det != 0` | if and when an inverse is added |

The two mechanisms are not arbitrary: a type restriction applies at a *declaration*, an
obligation applies at a *use site*. `log(x)` restricts what `x` may be; `a / b` cannot,
because `b` is an arbitrary expression whose value the declaration does not fix.

**Rejected alternative — totalisation (Lean's `(1:Nat)/0 = 0` by `rfl`).** It is the most
rigorous system in the panel and it does this, so it is defensible in general. It is rejected
*here* because HML's stated purpose is to catch the class of error where a step divides by
something that might vanish, and totalisation makes that error *disappear* rather than be
caught. A language whose thesis is verifier-guided reasoning should not define its way out of
the one check its thesis names. Recorded as `DESIGN_LOCK.md` D-V2-010.

**Cost, stated honestly.** This will make previously-clean modules report UNKNOWN
obligations, and will therefore reduce the VERIFIED rate on any existing corpus. That is the
intended direction — an endpoint that cannot fail is not an endpoint — but it must be
measured before and after, not discovered afterwards.

### 2.4 Authored obligations

`obligation n : P` (`GRAMMAR_CONTRACT.md` §1) restates a generated obligation so it can be
referenced by name in a `discharge`. It **does not create** one. An authored obligation with
no matching generated obligation is `HML-R909`. Allowing source to invent obligations would
let a module manufacture an easy one, discharge it, and gain nothing but a green light.

---

## 3. Propagation

Three rules.

**P1 — obligations attach to the derivation that generated them and do not migrate.** The
diagnostic points at the step that owes the condition, not at the conclusion. This is already
the design in `ChainReport.obligations_of(edge)`: "Chains fail at a *location*, not
globally."

**P2 — a derivation inherits the open obligations of its premises, transitively.** If `d2`
uses `d1` as a premise and `d1` has an open `k != 0`, then `d2` is not VERIFIED. This is
condition V3 of `REASONING_MODEL.md` §2.1 restated from the obligation side, and it is what
makes the DAG (§5 there) load-bearing rather than decorative.

**P3 — discharge by assumption records a dependency, and the dependency propagates.** An
obligation closed by an `assume` does not vanish; it becomes an entry in the derivation's
dependency set, which propagates to every downstream derivation and to the goal. See
`REASONING_MODEL.md` §6 and §8.3. `TransformationEdge.assumptions` and
`ChainReport.dependencies` already carry this shape; V2 makes it transitive, which it
currently is not.

**Obligations are accumulated even for a defective step.** Copied from
`transformation.py:1138-1141`, which states the reason: "a divisor that might be zero does
not stop mattering because the step also failed some other check."

---

## 4. Discharge — the exact conservative rules

Five admissible rules. **Anything not covered by one of them is `UNKNOWN`, and `UNKNOWN`
blocks VERIFIED.** There is no sixth "probably fine" rule and no default-allow branch.

### D1 — Entailment from a declared refinement type

The obligation is a comparison `e op c` with `c` a closed rational, and the interval
over-approximation of `e` derived from declared types is **entirely** on the satisfying side.
Implemented today: `LiteralRefinementBoundChecker._entailment`, using
`Interval.entirely_above` / `entirely_below`.

Soundness is stated in `domains.py`'s own contract, and only two consequences may be drawn
from an over-approximation: `I ⊆ S` licenses DISCHARGED; `I ∩ S = ∅` licenses nothing,
because "a refutation must exhibit a witness, and an empty intersection with an
over-approximation does not hand you one".

### D2 — Entailment from an assumption **(new; this is the C-1 fix)**

The obligation is a comparison, and the module's active assumption set narrows the
interval enough to entail it.

**This does not work today**, and the reason is one location:
`verification/obligations/evaluate.py::build_environment` (lines 169-229) reads
`Declaration`, `DefineStmt` and `ConceptDecl`, and **never reads `AssumeStmt`**. The measured
consequence is worse than "does not discharge" — see §8.

**The rule, stated so that it is implementable and sound:**

1. Collect every `AssumeStmt` in the module. An assumption is *admissible for narrowing* iff
   it is a `Comparison` whose left side is a `Ref` with a modelled domain and whose right
   side evaluates to a closed `Fraction`. Everything else is carried as an assumption but
   contributes **no** narrowing.
2. For each admissible assumption, intersect the referenced name's domain interval with the
   assumption's interval, using `Interval.intersect` — which is exact, not
   over-approximate, and already handles open/closed boundary agreement
   (`domains.py:109-133`).
3. Discharge exactly as D1, against the narrowed interval.
4. Record every assumption used in the derivation's dependency set (P3).

Four constraints that make it sound, each of which has a reason:

* **Conjunction only.** `assume x > 0 or y > 0` narrows nothing. A disjunction does not
  constrain either variable, and treating it as though it did is the classic unsound
  shortcut.
* **One free name per assumption.** `assume x < y` narrows nothing under this rule. It is
  still recorded, and a future relational domain could use it; interval arithmetic cannot.
* **Contradictory assumptions produce an empty interval, and an empty interval discharges
  nothing.** `Interval.entirely_above` returns `False` on an empty interval, with the comment
  "a vacuous domain proves nothing; say so rather than pass" — measured: `False`. Without
  this, `assume x > 1` plus `assume x < 0` would let every obligation about `x` be discharged
  ex falso, and the audit's C-6 (contradictory assumptions accepted silently) would become
  *actively harmful* instead of merely permissive. A separate `LOGICAL_CONSISTENCY` obligation
  on the assumption set — which `LogicalConsistencyChecker` already computes for `require` —
  should be raised in the same pass.
* **Assumptions are module-scoped in v2.0.** Ladder criterion 3.3 wants *scoped* assumptions.
  V2 does not deliver scoping and this document does not pretend it does; the dependency set
  gives the *enumerability* half of 3.3 and not the *non-leakage* half. Recorded as a known
  limitation, not as a pass.

### D3 — Closed evaluation

The obligation has no free names and evaluates exactly over the rationals. Implemented:
`ClosedArithmeticEqualityChecker`, `ClosedInequalityChecker`. This is the rule that produced
the correct `FAILED` on `prove 1.0 = 2.0` (§8), so it is known to work.

### D4 — Syntactic entailment from an available hypothesis

The obligation's proposition is **canonically identical** to an available claim: an
assumption, a declaration-derived fact, or the conclusion of a VERIFIED derivation. Compared
by canonical form with `include_names=False`, so alpha-renaming does not defeat it.

This is deliberately narrower than "logically implied by". It matches only identity, not
consequence. Widening it is a solver, and a solver is not in scope
(`GRAMMAR_CONTRACT.md` §6).

### D5 — Structural recomputation

`mode == STRUCTURAL`: dimensional agreement, call arity, parameter types. Decided by
recomputing rather than by reasoning about values. Implemented:
`DimensionCompatibilityChecker`, `DeclaredSignatureChecker`.

### Not admissible, named so that no one adds them quietly

* **Sampling as proof.** `NumericalCounterexampleChecker` may only ever produce `FAILED`.
  Its own note is the rule: "a fixed grid — never a proof". Finding no counterexample on a
  grid is not a discharge.
* **Discharge by evidence.** A statistical result may not discharge a mandatory obligation.
  `DISCHARGES_GOALS[EVIDENCE]` is `False` and `PROHIBITED_COERCIONS` records the reason:
  "absence of evidence against a hypothesis is not evidence for it".
* **Discharge by another undischarged obligation.** Dependencies between obligation records
  exist (`ObligationRecord.dependencies`), and the rule stated there applies: "a discharge
  that rests on another obligation is only as good as that one". A cycle among obligation
  dependencies is `HML-R901`, the same code as a derivation cycle.
* **Discharge by backend success.** Emitting Lean or Stan that compiles is source
  generation. `improvement/verification.py` already says this in three places; it is
  restated because a reasoning layer is exactly where someone will be tempted.

---

## 5. Status mapping between the surface and the record layer

Two four-valued vocabularies exist and they are not the same set. Both are correct at their
own layer; the mapping is total and gate-preserving.

| surface (`GRAMMAR_CONTRACT.md` §3) | record (`records.py`) | blocks VERIFIED |
|---|---|---|
| `OPEN` | *(new; no record yet)* | **yes** |
| `DISCHARGED` | `DISCHARGED` | no |
| `FAILED` | `FAILED` | **yes** |
| `UNKNOWN` | `UNSUPPORTED` | **yes** |
| `UNKNOWN` | `INCONCLUSIVE` | **yes** |

`UNKNOWN` is a **presentation** of the last two; the record always retains which one it was.
`records.py` argues that collapsing `UNSUPPORTED` and `INCONCLUSIVE` "would hide which of
the two is growing" — the first means *this system has no theory for that*, the second means
*this system tried and came back empty* — and that argument is correct and is preserved. What
is collapsed is only the word shown to a reader, and no gating power is lost because all
four non-`DISCHARGED` values block.

*Test:* `test_unknown_retains_its_record_class` — for every obligation presented as
`UNKNOWN`, the record's status is one of `UNSUPPORTED` / `INCONCLUSIVE` and the report can
say which. Recorded as `DESIGN_LOCK.md` D-V2-008.

---

## 6. The three required cases, with the arithmetic

These are the three the lead named. All three are decided by `Interval.entirely_above` /
`entirely_below`, which already exist and already behave correctly. The table below is
**measured output**, not a design intention:

```
hypothesis interval        |= > 0     |= >= 0    |= != 0    |= > 1
------------------------------------------------------------------
x > 0    -> (0, +inf)      True       True       True       False
x >= 0   -> [0, +inf)      False      True       False      False
x < 0    -> (-inf, 0)      False      False      True       False
x >= 1   -> [1, +inf)      True       True       True       False
Real     -> (-inf,+inf)    False      False      False      False
```

### Case 1 — `assume x > 0` **DISCHARGES** an `x > 0` obligation

`x > 0` gives `(0, +inf)`: `lo = 0`, `lo_closed = False`.
`entirely_above(0, strict=True)` returns `lo == c and (not strict or not lo_closed)` →
`0 == 0 and (False or True)` → **True**. Discharged, with `x > 0` entering the dependency
set. This is the case the audit's C-1 says is unwritable today.

### Case 2 — `assume x >= 0` must **NOT** discharge `x > 0`

`x >= 0` gives `[0, +inf)`: `lo = 0`, `lo_closed = True`.
`entirely_above(0, strict=True)` → `0 == 0 and (False or False)` → **False**.
Status: `UNKNOWN`, not `FAILED` — no witness was produced, and the interval machinery is not
permitted to refute (D1's soundness contract). `UNKNOWN` blocks VERIFIED.

The single boundary point `x = 0` is the entire difference, and it is exactly the point at
which `log` is undefined and division fails. An implementation that used `>=` where `>` was
meant would pass every non-boundary test.

### Case 3 — `x != 0` must **NOT** be inferred from `x >= 0`

`!= 0` is discharged only when the whole interval lies strictly on one side:
`entirely_above(0, strict=True) or entirely_below(0, strict=True)`.
For `[0, +inf)` that is `False or False` → **False**. `UNKNOWN`.

Note the asymmetry that makes this a real check rather than a coincidence: `x > 0` **does**
discharge `x != 0` (measured `True`), and `x < 0` does too. Only the non-strict bound fails,
which is correct — `x >= 0` genuinely admits `x = 0`.

### Required test fixtures

`tests/reasoning/test_discharge_conservatism.py`, as a table, with both directions present:

| hypothesis | obligation | required status |
|---|---|---|
| `x > 0` | `x > 0` | DISCHARGED |
| `x > 0` | `x != 0` | DISCHARGED |
| `x > 0` | `x >= 0` | DISCHARGED |
| `x >= 0` | `x > 0` | **UNKNOWN** |
| `x >= 0` | `x != 0` | **UNKNOWN** |
| `x >= 0` | `x >= 0` | DISCHARGED |
| `x < 0` | `x != 0` | DISCHARGED |
| `x > 0` | `x > 1` | **UNKNOWN** |
| `x > 1` and `x < 0` | anything | **UNKNOWN** (empty interval discharges nothing) |
| no assumption, `x : Real` | `x > 0` | **UNKNOWN** — and specifically **not FAILED** |

The last row is the regression test for §8. It must assert `UNKNOWN`, not merely
"not DISCHARGED", because the current behaviour is `FAILED`.

---

## 7. Blocker: the catalogue's obligations are strings

`OperationSpec.obligations` is `tuple[tuple[str, ObligationKind], ...]` and
`TransformationEdge.obligations()` produces `Obligation.condition: str` via
`template.format_map(ctx)` — a Python format string such as `"{by} != 0"`, rendered against
node *names*.

Every discharge rule in §4 consumes an `Expr`. `checkers.py` pattern-matches on
`Comparison`, `Quantifier`, `Call`, `Ref`; `evaluate.py` walks an expression tree. **Nothing
in the discharge engine can accept a string.**

Consequence, stated without hedging: **if V2 reuses the obligation templates verbatim, every
generated obligation is `UNKNOWN` by construction.** The reasoning layer would generate
obligations it can never discharge, which is the state the audit already records, relocated
to a new file. Criterion 3.4 would pass; 3.5 would still fail; and the VERIFIED rate would
be structurally zero for any derivation whose rule generates an obligation — which is most
of them.

**Recommendation.** Keep the table and the taxonomy. Change the obligation payload from a
format string to an `Expr` **builder**: a callable taking the edge's typed arguments and its
premise/conclusion expressions, returning an `Expr`. `divide_through`'s becomes

```
lambda ctx: Comparison(op="!=", left=ctx.arg("by"), right=Literal(value=0.0))
```

The string template is retained beside it, for rendering. Two rejected alternatives and the
reasoning are in `DESIGN_LOCK.md` D-V2-002.

Not every template can become an `Expr`, and that is fine and honest: *"the identity
`{warrant}` holds on the domain of `{source}`"* and *"`{source}` is differentiable with
respect to `{wrt}`"* are not propositions in HML's expression language. Those stay textual
and are permanently `UNKNOWN` — which is the correct answer, is what `UNSUPPORTED` in
`records.py` means, and blocks VERIFIED honestly. The point is that the arithmetic ones —
`!= 0`, `> 0`, `>= 0`, the ones that make up the majority of side conditions and all three
of the lead's required cases — **must** be expressions.

---

## 8. Blocker: today an assumption lets the verifier *refute*

Measured on the pristine base:

```
module A                                     module B
var x : Real                                 var x : PositiveReal
assume x > 0.0                               prove x > 0.0
prove x > 0.0
                                             → VERIFIED
→ DISPROVED
  [DISCHARGED] logical_consistency/satisfiable   x > 0.0
  [FAILED]     numerical_counterexample/universal  x > 0.0
      witness: this assignment satisfies every declared type
               constraint and makes the obligation false
```

Module A states an assumption and then a goal that follows from it in one step. The verifier
returns **DISPROVED with a witness**. Module B, which is the same mathematics with the
positivity moved into the declaration, returns VERIFIED.

The cause is `build_environment` never reading `AssumeStmt` (§4, D2). The counterexample
search then draws `x = -1` from `Real`'s *unnarrowed* domain, which the assumption should
have excluded.

This is a confident false negative. `records.py` and `engine.py` both name this class of
error as the one they exist to prevent, and `ObligationMode`'s docstring names it exactly:
"treating a `prove` as `SATISFIABLE` produces confident false successes" — this is the
mirror image, a confident false *failure*.

It is the highest-value single fix in the build, it is a precondition for D2, and it is
localised to one function.

---

## 9. Reporting

`hml obligations` today prints the type checker's undischarged obligations and nothing else.
There is **no CLI path that runs the discharge engine at all** — verified by reading
`cli/__init__.py:48-150`: the subcommands are `check`, `render`, `canonical`, `hash`,
`graph`, `obligations`, `views`, and none calls `verify_source`. The engine is reachable only
from `v1/pipeline/run.py` and `improvement/verification.py`.

This matters for the audit's headline. `prove 1.0 = 2.0` "compiles clean" via `hml check` —
true, and reproduced. But the discharge engine, when actually invoked, gets it right:

```
$ python -c "from hamiltonian_lang.verification.obligations import verify_source; ..."
DISPROVED | at least one obligation was refuted with a witness
[FAILED] OBL-000-c417785a (closed_arithmetic_equality/universal) 1.0 = 2.0
    witness: the two sides are 1 and 2
```

So the correct statement of the gap is narrower and more useful than "HML cannot refute
`1 = 2`": **the capability exists and is not wired to the surface.** V2 should add
`hml verify <file>` and report obligation status per derivation. That is a small change with
a large effect on whether the reasoning layer is visible to a user or a model.

---

## 10. What was and was not run

| check | result |
|---|---|
| interval truth table of §6 | **run**, output quoted verbatim |
| empty interval discharges nothing | **run**, `False` |
| `intersect((0,∞), [0,∞))` = `(0,∞)` | **run** |
| `assume x > 0` + `prove x > 0` → DISPROVED | **run**, §8 |
| `var x : PositiveReal` + `prove x > 0` → VERIFIED | **run**, §8 |
| `prove 1.0 = 2.0` → DISPROVED under `verify_source` | **run**, §9 |
| `build_environment` never reads `AssumeStmt` | **read**, `evaluate.py:169-229` |
| no CLI subcommand invokes the discharge engine | **read**, `cli/__init__.py:48-150` |
| catalogue obligations are strings | **read**, `transformation.py:332-360, 764-787` |
| **any V2 obligation behaviour** | **NOT IMPLEMENTED, NOT TESTED.** Every rule in §2–§6 is a specification. |
| **full test suite** | **NOT RUN** — the worktree is under concurrent edit. |
