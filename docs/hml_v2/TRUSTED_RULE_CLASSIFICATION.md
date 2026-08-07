# Trusted-rule classification

**Directive:** §8 · **Pinned SHA:** `ae9a2a0` · **Date:** 2026-08-07
**Subject:** `src/hamiltonian_lang/reasoning/kernel.py`, the 16 CORE rules of D-039.

Everything numeric below was **measured**, not asserted. The measurement scripts live in
the session scratchpad (`probe_kernel.py`, `probe_e2e.py`, `probe_deriv.py`,
`tcb_count.py`, `rule_trace_plugin.py`) and are reproducible against the pinned tree.

> **Pinning note.** The lead was concurrently editing `type_system/`, `semantics/`,
> `parser/`, `lexer/`, `ast/nodes.py`, `backends/canonical.py`, `backends/hml.py` and
> `reasoning/refinement.py` for scoped Γ. `git diff ae9a2a0 -- src` confirms that
> **`reasoning/kernel.py` and `reasoning/check.py` are byte-identical to `ae9a2a0`**, so
> the kernel analysis is not affected. All end-to-end probes were nevertheless run
> against a `git archive ae9a2a0` snapshot on `PYTHONPATH`, not the live tree, so no
> in-flight edit can have coloured a result. The one full-suite run (used only for
> usage counts) was made against the live tree and reported
> **one pre-existing failure unrelated to this work** —
> `tests/freeze/test_quarantine.py::test_the_keyword_set_is_exactly_the_frozen_set`,
> failing on the lead's newly added `scope` keyword.

---

## 0. Headline

| finding | severity |
|---|---|
| **The `k != 0` guard on `divide_both_sides` is bypassable.** `multiply_both_sides(by := 1.0 / 0.0)` reaches **VERIFIED**, and its goal reaches **PROVED**, with **zero diagnostics** and a literal division by zero in the certified statement. | **critical** |
| **4 of 16 rules are never successfully applied anywhere in the test suite** (`modus_tollens`, `and_elim_left`, `and_elim_right`, `weaken_inequality`). 9 of 16 have no dedicated test at all. | high |
| The D-039 **X3 conformance test covers 8 of 16 rules**; its own assertion is `checked >= 8`, so it passes at exactly its floor and 8 CORE rules are admitted with no X3 evidence. | high |
| `expr_identity` collapses **all unresolved `Ref`s to one canonical form**. Currently unreachable through `compile_source` (the resolver errors first), but it is a live hazard for any future direct kernel caller. | medium (latent) |
| A **decidably false** mandatory obligation (`0.0 != 0`, `-1.0 > 0`) is reported OPEN, not REFUTED. D-038 says `REFUTED` means REJECTED, not OPEN. | medium |
| **No individual rule is logically unsound.** All 16 are valid schemas. The defects above are all *system-level*: obligations attached to rule names rather than to the terms a conclusion introduces. | — |

**Recommendation on the kernel itself: do not change the rule set.** Change the
obligation model. Details in §4 and §5.

---

## 1. Per-rule classification table

Column definitions:

- **TCB lines** — `apply` function (physical, incl. docstring) + `RuleSpec` dict entry +
  any obligation builder used only by this rule. `_both_sides` (12 lines) is charged once
  to `add_both_sides`; `_and_elim` (8 lines) once to `and_elim_left`; the three siblings
  therefore show spec-only cost. Shared helpers are amortised separately (§3).
- **Tests** — `ded` = distinct tests in which `kernel.apply` returned `ok=True` for this
  rule, excluding the two generic loops that iterate `RULES`; `gen` = the generic loops.
  Measured by wrapping `kernel.apply` from a pytest plugin over the whole suite.
- **Locally checkable** — can the rule's conclusion be constructed and compared using only
  the premises, the arguments and the canonical form, with no search?

| # | rule | semantic purpose | locally checkable | derivable from other rules | generates obligations | capture / scope risk | TCB lines | tests (ded/gen) | external verifier better | classification |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `symmetry` | `a = b ⊢ b = a` | **yes** | **no** — worked failure R2 | no | none | **13** | 13 / 1 | no | **CORE_TRUSTED** |
| 2 | `transitivity` | `a = b, b = c ⊢ a = c` | **yes** | **yes** — worked reduction R1a via `substitute` (premises reversed), fails when `a` contains `b` | no | none | **16** | 2 / 1 | no | **DERIVED_RULE** *(retain — §4)* |
| 3 | `add_both_sides` | `a = b ⊢ a+k = b+k` | **yes** | **no** — worked failures R3 (no lambda) and R4 (substitution is total, not selective) | no | none | **20** | 4 / 1 | no | **CORE_TRUSTED** |
| 4 | `subtract_both_sides` | `a = b ⊢ a−k = b−k` | **yes** | **yes** — worked reduction R5a via `add_both_sides(by := -k)`; conclusion must then be written `a + -k` (R5b shows `a - k` is canonically distinct) | no | none | **8** | 0 / 1 | no | **DERIVED_RULE** *(retain — §4)* |
| 5 | `multiply_both_sides` | `a = b ⊢ a*k = b*k` | **yes** | **no** | **no — and this is the defect** (§5.1) | none | **8** | 0 / 1 | **yes, for definedness of `k`** | **CORE_TRUSTED** *(needs the §5.1 fix)* |
| 6 | `divide_both_sides` | `a = b ⊢ a/k = b/k`, `k ≠ 0` | **yes** | **yes, but only via the §5.1 defect** — `multiply_both_sides(by := 1.0/k)` | **yes**, `k != 0`, mandatory | none | **18** | 15 / 1 | **yes, for discharging `k != 0`** | **DERIVED_RULE** *(retain — the reduction is a bug, not a saving)* |
| 7 | `substitute` | `a = b, P ⊢ P[a := b]` | **yes** | **no** | no | **highest — and correctly refused.** Does not descend into `Quantifier`; also silently does not descend into the 11 other `Expr` kinds (`IntegralExpr`, `SetComprehension`, `LimitExpr`, `DerivativeExpr`, `ContinuityExpr`, `MomentExpr`, `ProbabilityExpr`, `JointExpr`, `IndependenceExpr`, `MembershipExpr`, `RelationExpr`, `DistExpr`). Under-substitution is sound (§5.4). | **21** | 0 / 1 | no | **CORE_TRUSTED** |
| 8 | `congruence` | `a = b ⊢ f(a) = f(b)` | **yes** | **no** | no *(domain caught downstream — §5.2)* | none | **25** | 1 / 0 | no | **CORE_TRUSTED** |
| 9 | `modus_ponens` | `P, P⇒Q ⊢ Q` | **yes** | **no** | no | none — probe A4/P11 | **15** | 1 / 0 | no | **CORE_TRUSTED** |
| 10 | `modus_tollens` | `¬Q, P⇒Q ⊢ ¬P` | **yes** | **only by assuming the contrapositive** (R8a) — a trust downgrade, not a derivation | no | none | **17** | **0 / 0** | no | **CORE_TRUSTED** |
| 11 | `and_intro` | `P, Q ⊢ P ∧ Q` | **yes** | **no** | no | none — probe A3 | **11** | 0 / 2 | no | **CORE_TRUSTED** |
| 12 | `and_elim_left` | `P ∧ Q ⊢ P` | **yes** | **only by assuming the projection axiom** (R7a) — a trust downgrade | no | none | **15** | **0 / 0** | no | **CORE_TRUSTED** |
| 13 | `and_elim_right` | `P ∧ Q ⊢ Q` | **yes** | as above | no | none | **7** | **0 / 0** | no | **CORE_TRUSTED** |
| 14 | `weaken_inequality` | `a < b ⊢ a ≤ b` | **yes** | **only by assuming the implication** (R9a) — a trust downgrade | no | none | **22** | **0 / 0** | no | **CORE_TRUSTED** |
| 15 | `add_inequality` | `a ⋈ b ⊢ a+k ⋈ b+k` | **yes** | **no** (same lambda blocker as #3) | no | none | **16** | 0 / 1 | no | **CORE_TRUSTED** |
| 16 | `multiply_inequality` | `a ⋈ b ⊢ a*k ⋈ b*k`, `k > 0` | **yes** | **no** — and **not** bypassable the way #6 is (§5.1) | **yes**, `k > 0`, mandatory | none | **38** | 1 / 1 | **yes, for discharging `k > 0`** | **CORE_TRUSTED** — the model the others should follow |

### Classification histogram

| classification | n | rules |
|---|---|---|
| **CORE_TRUSTED** | **13** | symmetry, add_both_sides, multiply_both_sides, substitute, congruence, modus_ponens, modus_tollens, and_intro, and_elim_left, and_elim_right, weaken_inequality, add_inequality, multiply_inequality |
| **DERIVED_RULE** | **3** | transitivity, subtract_both_sides, divide_both_sides |
| LIBRARY_SCHEMA | 0 | — |
| EXTERNAL_CHECK | 0 | — (no *rule* belongs here; three *obligations* do — §5.3) |
| DEPRECATE | 0 | — |

**All three DERIVED_RULE rows are recommended for retention.** The classification records
a mathematical fact; the recommendation column in §4 records the engineering decision, and
they deliberately differ. Directive filter B forbids reducing below 10 rules to hit a
number, and none of these three reductions buys enough to be worth its cost.

---

## 2. Usage measurement (how it was obtained, and what it found)

`kernel.apply` was wrapped by a pytest plugin loaded with `-p` from the scratchpad — no
file under `src/` or `tests/` was touched — and the full suite was run once. The plugin
records, per rule: total calls, calls returning `ok=True`, and the set of distinct test
node-ids in which an `ok=True` call occurred.

```
rule                      calls    ok  distinct tests   dedicated (non-generic)
symmetry                     20    17      14                    13
divide_both_sides            18    17      16                    15
add_both_sides                7     6       5                     4
transitivity                  6     3       3                     2
modus_ponens                  4     1       1                     1
multiply_inequality           4     3       2                     1
congruence                    3     1       1                     1
substitute                    2     1       1                     0
subtract_both_sides           2     1       1                     0
multiply_both_sides           2     1       1                     0
add_inequality                2     1       1                     0
and_intro                     2     2       2                     0
modus_tollens                 2     0       0                     0
and_elim_left                 2     0       0                     0
and_elim_right                2     0       0                     0
weaken_inequality             2     0       0                     0
```

Two facts fall out.

**(a) Four rules are never successfully applied anywhere in the suite.** `modus_tollens`,
`and_elim_left`, `and_elim_right` and `weaken_inequality` have `ok = 0`. Their only two
calls each come from the two generic loops
(`test_kernel.py::test_no_rule_strengthens_a_non_strict_premise_into_a_strict_conclusion`
and `test_architecture_freeze.py::test_x3_every_core_rule_rejects_a_step_differing_only_in_its_conclusion`),
both of which feed premises these rules correctly refuse, so both `continue` past them.
**Nothing in the repository has ever observed these four rules produce a conclusion.**

I verified by hand that all four do in fact work end to end (probes P8, P8b, P8c, P8d —
all reach `VERIFIED` with zero diagnostics), so this is a test-coverage finding, not a
correctness finding. It is still the sharpest kind of finding available here: a CORE rule
admitted to the trusted base with no executed evidence is exactly what D-039 X3 exists to
prevent.

**(b) Nine rules have zero dedicated tests.** Adding `substitute`, `subtract_both_sides`,
`multiply_both_sides`, `add_inequality` and `and_intro` to the four above: nine of sixteen
CORE rules are exercised only incidentally by loops that iterate `RULES` generically.

### The X3 conformance test passes at exactly its own floor

`test_x3_every_core_rule_rejects_a_step_differing_only_in_its_conclusion` feeds every rule
`arity` copies of `a = b` and a `1.0` for every declared parameter, then asserts
`checked >= 8`. Measured, it covers **8 of 16**:

```
covered : symmetry, transitivity, add_both_sides, subtract_both_sides,
          multiply_both_sides, divide_both_sides, substitute, and_intro
SKIPPED : congruence, modus_ponens, modus_tollens, and_elim_left,
          and_elim_right, weaken_inequality, add_inequality, multiply_inequality
```

`congruence` is skipped because `fn := Literal(1.0)` is not a `Ref`; the logical and
inequality rules are skipped because `a = b` is the wrong premise shape. Taking the union
with the `<=` strictness loop (which covers `and_intro`, `add_inequality`,
`multiply_inequality`), **six rules are covered by neither**: `and_elim_left`,
`and_elim_right`, `congruence`, `modus_ponens`, `modus_tollens`, `weaken_inequality`.

The assertion `checked >= 8` therefore reads as a guard but is satisfied by the current
state exactly, and would keep passing if a ninth rule silently stopped being checkable.

---

## 3. Measured TCB

All counts are **physical lines** of `ae9a2a0`, produced by an AST walk (`tcb_count.py`),
not by eye.

### 3.1 `kernel.py` decomposition — 553 lines total

| component | lines | note |
|---|---:|---|
| rule-specific (16 `apply` fns + 16 `RuleSpec` entries + 2 obligation builders) | **270** | the number the reduction question is about |
| — of which: `apply` functions (physical) | 121 | |
| — of which: `RULES` dict entries | 135 | |
| — of which: `_ne_zero` + `_gt_zero` | 14 | |
| shared structural helpers | **80** (61 non-comment) | `_eq` 5 · `_ineq` 4 · `_binop` 2 · `_cmp` 2 · `_structurally_equal` 13 · **`_substitute` 54** |
| scaffolding | **88** | `ObligationSpec` 14 · `RuleSpec` 18 · `RuleApplication` 9 · `apply` dispatcher 37 · `rule_names` 2 · `__all__` 8 |
| module docstring, imports, section banners, blanks | 115 | the soundness argument is written here; it is not dead weight |

### 3.2 The TCB is larger than `kernel.py`

`_structurally_equal` delegates to `backends.canonical.expr_identity` — deliberately, so
that the kernel's notion of "the same expression" is the language's own. That decision is
right, and it means the canonical serializer is inside the trusted base:

| module | trusted surface | lines |
|---|---|---:|
| `reasoning/kernel.py` | all of it | 553 |
| `backends/canonical.py` | `expr_identity` 39 + `_expr` 185 + `_normalise_for_identity` 27 + `_type` 2 | **253** |
| `reasoning/check.py` | the driver that compares kernel conclusion to author claim, manages the two premise pools, propagates obligations | 617 |
| **total TCB** | | **≈ 1 423** |

**The rules are 19% of `kernel.py` and 6% of the whole trusted base.** This is the single
most important number in this document: *deleting rules is not where TCB reduction lives.*
`_expr` alone (185 lines) is larger than every rule body combined (121 lines).

### 3.3 What each candidate reduction actually saves

| scenario | rules left | rule-specific lines | saved | verdict |
|---|---:|---:|---:|---|
| **as shipped** | 16 | 270 | — | |
| drop `subtract_both_sides` (R5a) | 15 | 262 | **8** | not worth it — §4 |
| merge `and_elim_left`/`and_elim_right` into one `side`-parameterised rule | 15 | 263 | **7** | not worth it — changes the surface a model writes |
| drop `transitivity` (R1a) | 15 | 254 | **16** | not worth it — §4 |
| drop `divide_both_sides` (R6a) | 15 | 252 | **18** | **actively harmful** — removes the only divide-by-zero guard in the language |
| drop the 4 never-successfully-exercised rules | 12 | 209 | **61** | rejected — §4; they are the cheapest rules and their "reductions" are `assume` statements |
| aggressive 16 → 10 (drop `subtract_both_sides`, `transitivity`, `and_elim_right`, `modus_tollens`, `weaken_inequality`, `add_inequality`) | 10 | 184 | **86** | rejected — 86 lines is 6% of the TCB, bought by making six common steps unwritable or unchecked |

Even the most aggressive legal reduction removes **86 of ~1 423 TCB lines — 6.0%** — while
deleting a third of what a model can say. Against the stated objective
("minimise TCB at fixed trusted semantic power"), this fails on both terms: the power
falls and the TCB barely moves.

---

## 4. Derivability analysis — worked reductions and worked failures

Each reduction below was written as real HML and compiled. `WORKS` means the compiler
reached `VERIFIED` with no diagnostics.

### R1 — `transitivity` ⇐ `substitute` · **WORKS**

`substitute` is `a = b, P ⊢ P[a := b]` with the equation as premise 0. Feeding the
*second* equation as premise 0 and the *first* as `P`:

```hml
assume p1 : a = b
assume p2 : b = c
derive d1 : a = c from p2, p1 by substitute      -- VERIFIED
```

`_substitute(a = b, old := b, new := c)` rewrites the `b` on the right-hand side, giving
`a = c`. The reduction is real.

**Its failure mode is safe.** When the left-hand side also contains the middle term,
`_substitute` rewrites *every* occurrence:

```hml
assume p1 : b + 1.0 = b
assume p2 : b = c
derive d1 : b + 1.0 = c from p2, p1 by substitute   -- REJECTED, HML-R706
```
The kernel yields `c + 1.0 = c`, not `b + 1.0 = c`, and the conclusion comparison catches
it. Native `transitivity` handles this case correctly, because it matches the middle term
positionally rather than rewriting.

**Recommendation: retain.** Saves 16 lines. Costs: a counter-intuitive reversed premise
order that a model must learn; a silent behavioural difference in the sub-term case; and
`transitivity`'s premise-order semantics are pinned by
`test_architecture_freeze.py::test_e5_premise_order_is_part_of_semantic_identity`.
16 lines is not worth making the most common equality idiom in mathematics awkward to write.

### R2 — `symmetry` ⇐ `substitute` · **FAILS**

```hml
assume p1 : a = b
assume p2 : a = a
derive d1 : b = a from p1, p2 by substitute      -- REJECTED, HML-R706
derive d1 : b = a from p1, p1 by substitute      -- REJECTED, HML-R706
```

`_substitute` is **total**: it replaces every canonically-identical occurrence. From
`a = a` it yields `b = b`, never `b = a`. Reducing `symmetry` would require *selective*
(positional or occurrence-indexed) substitution, which this kernel deliberately does not
have. `symmetry` is primitive at 13 lines and is the most-used rule in the repository
(13 dedicated tests).

### R3 — `add_both_sides` ⇐ `congruence` with `f = (· + k)` · **FAILS — the language blocks it**

This is the reduction the brief asked to check specifically, and the concrete finding is
the one anticipated: **HML has no lambda, so `(· + k)` is not expressible.**

```hml
derive d1 : a + k = b + k from p1 by congruence(fn := (u) => u + k)
```
does not even parse as an abstraction. `=>` is HML's **implication** operator (a
prohibited conflation the language guards elsewhere), so `(u) => u + k` parses as the
proposition `u ⇒ u + k` and the resolver reports `HML-N301: 'u' is not bound` — twice.
Passing an expression directly is refused by the kernel:

```hml
derive d1 : a + k = b + k from p1 by congruence(fn := a + k)   -- REJECTED, HML-R705
```
because `_apply_congruence` requires `isinstance(fn, Ref)`.

This is corroborated independently by **D-041**, which records that *abstraction* is one
of exactly two things HML genuinely cannot express and which it accepted as a targeted
future addition. Until abstraction lands, **`congruence` cannot subsume any of
`add_both_sides`, `subtract_both_sides`, `multiply_both_sides`, `divide_both_sides` or
`add_inequality`.** The five algebraic rules are primitive *for this language*, and the
blocker is a language-level fact, not a kernel-design choice.

### R4 — `add_both_sides` ⇐ `substitute` + an assumed reflexivity · **FAILS**

Same root cause as R2 — substitution is total:

```hml
assume p1 : a = b
assume p2 : a + k = a + k
derive d1 : a + k = b + k from p1, p2 by substitute   -- REJECTED, HML-R706
derive d1 : b + k = b + k from p1, p2 by substitute   -- VERIFIED  (what it really yields)
```

There is a second, independent blocker: **the kernel has no `reflexivity` rule**
(`derive ... by reflexivity` → `HML-R704: 'reflexivity' is not a rule in the trusted
kernel`). So `a + k = a + k` can only enter as an `assume` — which is *granted*, not
proved. Any reduction that needs it converts a checked step into an unchecked assumption.

### R5 — `subtract_both_sides` ⇐ `add_both_sides(by := -k)` · **WORKS, with a writability cost**

```hml
derive d1 : a + -k = b + -k from p1 by add_both_sides(by := -k)   -- VERIFIED
derive d1 : a -  k = b -  k from p1 by add_both_sides(by := -k)   -- REJECTED, HML-R706
```

The reduction is genuine but the author must then write `a + -k`. `a - k` is a distinct
canonical tree (`BinOp("-")` vs `BinOp("+", …, UnaryOp("-"))`) and the canonical form does
**not** fold one into the other — correctly so; folding it would be exactly the kind of
unchecked normalisation this kernel exists to avoid.

**Recommendation: retain.** The saving is **8 lines**, the smallest of any candidate. The
cost is that every subtraction step in the language becomes `a + -k`, against a directive
that optimises for LLM writability. This is the clearest case in the document of a rule
that is technically derivable and obviously worth keeping.

### R6 — `divide_both_sides` ⇐ `multiply_both_sides(by := 1.0/k)` · **WORKS — and that is the bug**

```hml
assume p1 : a = b
derive d1 : a * (1.0 / k) = b * (1.0 / k) from p1 by multiply_both_sides(by := 1.0 / k)
--> VERIFIED, zero diagnostics, zero obligations

derive d1 : a / k = b / k from p1 by divide_both_sides(by := k)
--> CHECKED, HML-R707, open mandatory obligation `k != 0`
```

Two spellings of the same mathematical step; one is guarded and one is not. See §5.1 — this
is not an argument for deleting `divide_both_sides`, it is an argument that the guard is in
the wrong place.

### R7 / R8 / R9 — the "reductions" that are actually trust downgrades

All three of the following compile and reach `VERIFIED`:

```hml
-- R7: and_elim_left
assume p2 : (x > 0.0 and y > 0.0) implies x > 0.0
derive d1 : x > 0.0 from p1, p2 by modus_ponens          -- VERIFIED

-- R8: modus_tollens
assume p2 : not (y > 0.0) implies not (x > 0.0)
derive d1 : not (x > 0.0) from p1, p2 by modus_ponens    -- VERIFIED

-- R9: weaken_inequality
assume p2 : x < y implies x <= y
derive d1 : x <= y from p1, p2 by modus_ponens           -- VERIFIED
```

**These are not derivations.** Each replaces a rule the kernel *checks* with an `assume`
the kernel *grants*. The projection axiom, the contrapositive and the weakening
implication are all true, but nothing in the system knows that — an author who wrote
`assume p2 : x <= y implies x < y` would get the same `VERIFIED`, and the false step would
be certified.

Under D-039's lattice this is a strict trust downgrade: an assumption is a granted premise,
so eliminating these rules moves genuine mathematics out of CORE and into "the author said
so". `and_elim_left` costs 15 lines, `and_elim_right` 7, `modus_tollens` 17,
`weaken_inequality` 22. **Sixty-one lines is a very cheap price for four steps that are
checked rather than assumed**, and this is precisely the case directive filter B was
written to protect.

### Summary of derivability

| rule | derivable? | by what | verdict |
|---|---|---|---|
| `transitivity` | **yes** | `substitute` with reversed premises | retain (16 lines) |
| `subtract_both_sides` | **yes** | `add_both_sides(by := -k)` | retain (8 lines) |
| `divide_both_sides` | **yes, via a defect** | `multiply_both_sides(by := 1/k)` | retain; fix the defect (§5.1) |
| `symmetry` | no | — | primitive |
| `add_both_sides`, `multiply_both_sides`, `add_inequality`, `multiply_inequality` | no | lambda blocker (R3), total-substitution blocker (R4) | primitive |
| `substitute`, `congruence`, `modus_ponens`, `and_intro` | no | — | primitive |
| `modus_tollens`, `and_elim_left`, `and_elim_right`, `weaken_inequality` | only via `assume` | — | primitive *in effect*; the alternative is a trust downgrade |

---

## 5. Unsoundness and incomplete checking

> This is the section the exercise exists for. **No individual rule is logically unsound.**
> Every one of the 16 is a valid schema over an ordered field, given that the terms it
> introduces are defined. The defects are in what the surrounding system does *not* check.

### 5.1 CRITICAL — the divide-by-zero guard is bypassable by spelling `/` as `* (1/·)`

**Reproduced at `ae9a2a0`, compiled from source, zero diagnostics:**

```hml
module M
var a : Real
var b : Real
assume p1 : a = b
goal   g1 : a * (1.0 / 0.0) = b * (1.0 / 0.0)
derive d1 : a * (1.0 / 0.0) = b * (1.0 / 0.0) from p1 by multiply_both_sides(by := 1.0 / 0.0)
proved g1 by d1
```

```
ok = True
diagnostics = []
GoalStmt   g1  PROVED
DeriveStmt d1  VERIFIED
```

A **literal division by zero** appears in a statement the system reports as `VERIFIED` and
a goal it reports as `PROVED`, with nothing said. This is the failure mode `CLAUDE.md`
names as the worst in the codebase — authoritative-looking output for something that
denotes nothing — and it is reachable in six lines of HML.

**Root cause.** `ObligationSpec` is attached to the *rule name*. `divide_both_sides`
declares `k != 0`; `multiply_both_sides` declares nothing. But the obligation is a
property of the **`/` operator that appears in the conclusion**, not of the rule that
happened to put it there. Once a conclusion can contain `/` without going through
`divide_both_sides`, the guard is decorative.

**It is worse than the kernel.** The bare expression is unguarded everywhere:

```hml
prove  a = 1.0 / 0.0     -- ok=True, no diagnostics
assume p1 : a = 1.0 / 0.0 -- ok=True, no diagnostics
```

So `divide_both_sides`'s `k != 0` is currently the **only** place in the entire language
where a division domain is checked at all.

**This directly contradicts D-036**, which freezes: *"Division, `tan`, negative powers,
indexing, matrix inverse, conditional probability and normalisation become CONTRACTED and
always generate a precondition."* `grep -rn "CONTRACTED\|definedness"` over
`src/hamiltonian_lang/` returns nothing; the registry D-036 mandates does not exist yet.
The freeze is a contract that the implementation has not yet met, and the kernel's
name-keyed obligation is a stand-in that a two-token rewrite walks around.

**Fix (recommended, and it is not a kernel change):** implement the D-036 definedness
registry as a **term-level pass over `DeriveStmt.conclusion`** that emits a mandatory
precondition for every CONTRACTED operation the conclusion contains, regardless of which
rule produced it. `divide_both_sides`'s own `ObligationSpec` then becomes redundant and
can be deleted — which is the *one* genuine TCB reduction this analysis found, and it is
available only after the fix, never before.

**Scope check — is `multiply_inequality` bypassable the same way?** No, measured. Its
`k > 0` obligation is not reachable around, because no other kernel rule introduces
multiplication into an inequality:

```hml
derive d1 : a * (0.0 - 1.0) < b * (0.0 - 1.0) from p1 by multiply_inequality(by := 0.0 - 1.0)
--> CHECKED, HML-R707 (obligation `0.0 - 1.0 > 0` open)
```
`divide_both_sides` is bypassable specifically because `multiply_both_sides` sits beside
it and can construct the reciprocal.

### 5.2 `congruence` introduces an application with no definedness obligation — but the type checker catches it

`_apply_congruence` builds `Call(callee=fn.name, args=[a])` with **zero obligations**, for
any `fn` that is a `Ref`. At kernel level it will happily manufacture:

```
congruence(fn := log)  -->  log(a) = log(b)          -- no obligation
congruence(fn := sqrt) -->  sqrt(a) = sqrt(b)        -- no obligation
congruence(fn := x)    -->  x(a) = x(b)              -- x is a Real variable
congruence(fn := zzz)  -->  zzz(a) = zzz(b)          -- zzz does not exist
```

End to end, **all four are caught before the kernel runs**, because the type checker and
resolver visit `DeriveStmt.conclusion` first and the derivation never leaves `PROPOSED`:

| probe | result |
|---|---|
| `congruence(fn := log)` on an unconstrained `Real` | `HML-T427`, status `PROPOSED` |
| `congruence(fn := sqrt)` on an unconstrained `Real` | `HML-T427`, status `PROPOSED` |
| `congruence(fn := k)` where `k : Real` | `HML-T470`, status `PROPOSED` |
| `congruence(fn := zzz)` undeclared | `HML-N306`, status `PROPOSED` |

**Assessment: not a defect, but it is load-bearing in a way that is not written down.**
`congruence`'s soundness for partial functions rests entirely on the fact that the author
must *write* the conclusion and the type checker sees it. That is a legitimate defence and
it works — but it is undocumented, untested (`congruence` has exactly one dedicated test),
and it is the same architecture that failed in §5.1. It should be pinned by a test.

I also checked the obvious way this could be a real hole — whether the canonical form
drops the callee name, which would make `congruence(fn := exp)` certify a conclusion about
`log`. It does not: `expr_identity(exp(y)) != expr_identity(log(y))`; `callee` is retained
in the serialisation. Verified.

### 5.3 A decidably false mandatory obligation is reported OPEN, not REFUTED — contra D-038

```hml
derive d1 : a / 0.0 = b / 0.0 from p1 by divide_both_sides(by := 0.0)
--> CHECKED, obligation `0.0 != 0` reported OPEN (HML-R707)

derive d1 : x * -1.0 < y * -1.0 from p1 by multiply_inequality(by := -1.0)
--> CHECKED, obligation `-1.0 > 0` reported OPEN (HML-R707)
```

Both obligations are **closed propositions that are decidably false**. D-038 freezes:
*"`REFUTED` means REJECTED, not OPEN"*. Reporting them OPEN says "nobody established this
yet" when the truth is "this is false and the step is wrong".

**Severity is contained**: a mandatory OPEN obligation already blocks `VERIFIED` and blocks
`proved`, so nothing false is certified. But the diagnostic misdirects — it invites the
author to go and discharge an obligation that can never be discharged, and under D-038's
own contract the step should be REJECTED outright.

**This is the strongest EXTERNAL_CHECK case in the document.** `verification/obligations/`
already contains an interval evaluator (`evaluate.py`, with an explicit
`Undecidable("division by zero in a closed expression")` path) and a domain solver
(`domains.py`). Routing closed obligation propositions through it, and mapping a decided
`False` to `REFUTED → REJECTED`, is a small change that uses machinery already present. No
rule needs to move to `EXTERNAL_CHECK`; the *obligation discharge path* does.

### 5.4 `substitute` does not descend into eleven binder-carrying expression kinds

`_substitute` handles `BinOp`, `Comparison`, `LogicalOp`, `UnaryOp`, `Call`, `Index` and
`Quantifier` (the last by *deliberate refusal*), and returns the node unchanged for
everything else. Since D-026 that "everything else" includes eleven expression kinds, of
which five are binders: `IntegralExpr`, `SetComprehension`, `LimitExpr`, `DerivativeExpr`,
`ContinuityExpr` — plus `MomentExpr`, `ProbabilityExpr`, `JointExpr`, `IndependenceExpr`,
`MembershipExpr`, `RelationExpr` and `DistExpr`.

**This is sound.** Partial substitution of equals is always valid (`P ⊢ P` is the limiting
case), so failing to rewrite can only produce a conclusion the author did not write, which
the `HML-R706` comparison then rejects. The failure direction is the safe one, exactly as
for `Quantifier`.

**But it is incomplete and undocumented.** The `Quantifier` refusal carries a comment
explaining itself; the other eleven are silent fall-through. A model attempting a
legitimate rewrite inside a probability or an integrand gets `HML-R706` — *"the stated
conclusion is not what `substitute` yields"* — with no hint that the rule structurally
cannot do it. That is a bad repair signal for the loop the directive optimises for.

This is the same drift D-041 recorded as *the strongest argument against* its own decision
("7 of 17 consumers are already stale"). `_substitute` is consumer number eighteen, and it
is stale in the safe direction. The binder protocol D-041 accepted (`binder_of` /
`scoped_children`) should cover it.

### 5.5 Capture and scope — tested, and clean

I drove every rule with a binder in a premise. **No rule captures, and no bound name
escapes its binder**:

| probe | result |
|---|---|
| A1 `substitute x := 1` into `forall x . x > 0` | returns the quantifier **unchanged** — the documented refusal, correct |
| A2 same inside `(forall x . x > 0) and x > 5` | rewrites only the free `x` outside the binder — correct |
| A3 `and_intro(forall x . x > 0, x > 5)` | `(forall x . x > 0) and x > 5` — no capture; conjunction binds nothing |
| A4 `modus_ponens` yielding a quantifier | returns `imp.right` intact |
| A5 `add_both_sides(by := x)` onto `(forall x . x > 0) = y` | `(forall x . x > 0) + x = y + x` — the `x` is outside the binder and the renderer parenthesises correctly |
| A6 `substitute` into an `IntegralExpr` body | body unchanged (§5.4) |
| P11 `modus_ponens` with a quantified antecedent, end to end | `VERIFIED`, correct |

The structural reason is worth recording, because it explains why the risk is genuinely low
rather than accidentally low: **no rule in this kernel introduces a binder.** Every
conclusion is built from premise sub-trees under fresh `BinOp` / `Comparison` /
`LogicalOp` / `UnaryOp` / `Call` wrappers, none of which bind. Capture requires a binder to
be introduced or descended into; `substitute` is the only rule that descends, and it
refuses.

**One caveat I could not settle:** whether a fact established inside a quantifier or
`scope` frame can be cited as a premise outside it. That is Γ-frame discipline (D-035),
it is `check.py`'s responsibility rather than the kernel's, and the lead is actively
implementing it in `refinement.py` / `semantics/` right now. Flagged, not measured — see §7.

### 5.6 `expr_identity` collapses all unresolved `Ref`s (latent, currently unreachable)

```python
expr_identity(Ref(name="p")) == '{"kind":"Ref","symbol":null}'
expr_identity(Ref(name="q")) == '{"kind":"Ref","symbol":null}'   # identical
```

`expr_identity` compares `symbol` (a `SymbolId`) and deliberately excludes the *spelling*,
which is what gives alpha-equivalence. When `symbol_id is None` — an unresolved node —
every `Ref` in the language becomes one expression. Driving the kernel directly with
unresolved nodes produces nonsense that it reports as `ok`:

```
modus_tollens( not p , p implies q )   -->  OK, "not p"      # should be a shape refusal
substitute( y := x , integral(...) = z ) -->  "... = x"        # rewrote z, which is not y
```

**Not reachable through `compile_source`.** The resolver errors first and the derivation
never reaches the kernel:

```hml
derive d1 : undeclared_zzz = 2.0 * x from a1 by symmetry
--> HML-N301, status PROPOSED   (the control with a declared-but-wrong name gives HML-R706 / REJECTED)
```

So this is a **latent hazard, not a live defect**. It matters because `expr_identity`'s own
docstring argues its safety from *"`symbol` (a `SymbolId`, not a spelling) is still
compared"* — an argument that silently assumes resolution has happened. Any future caller
of `kernel.apply` on an unresolved or synthetic tree (an importer, a batch graph builder, a
repair loop constructing candidate steps, a fuzzer) inherits a comparison that says
everything is equal to everything. Given D-038/D-040 anticipate exactly such callers, the
precondition should be enforced rather than assumed — an assertion in `apply` that every
`Ref` reachable from a premise or argument carries a `symbol_id` would cost about three
lines.

### 5.7 Minor: shape and argument discipline

| finding | severity | detail |
|---|---|---|
| `and_intro` performs no shape check at all | low | `and_intro(3.0, 5.0)` yields `3.0 and 5.0`; `and_intro(x, y)` yields `x and y`. Sound in context (the premise pool holds propositions), and the type checker rejects the result downstream, but it is the only rule with no premise validation whatsoever. |
| undeclared rule arguments are silently ignored | low | `symmetry(by := 1.0)` → `VERIFIED`; `add_both_sides(by := 1.0, bogus := 9.0)` → `VERIFIED`. `apply` checks that required params are *present*, never that supplied params are *expected*. A model that misremembers a role name gets silence instead of a correction — against the directive's repair-loop goal. Two lines to fix. |
| `divide_both_sides(by := 0.0)` builds the term before the obligation is judged | low | consequence of §5.3, not separate. |

**What held under attack** (recorded so no reader infers weakness from the length of the
list above): every wrong-shaped premise was refused with a precise reason —
`symmetry` on `!=`, `weaken_inequality` on `<=` and on `!=`, `add_inequality` on `!=`,
`and_elim_*` on `or` and on `implies`, `modus_ponens` on `or` and with premises swapped,
`congruence` with a `Literal` or a `Call` as `fn`, wrong premise counts, missing required
arguments. `modus_tollens` correctly refused affirming-the-consequent shapes once the
§5.6 resolution precondition was met. `expr_identity` distinguishes `forall` from
`exists`, and `exp(y)` from `log(y)`. No rule strengthens `<=` into `<`. Degenerate
arguments (`by := 0.0`, `by := -1.0`, `a = a`, matching sides) all behaved as documented.

---

## 6. Recommendation per rule

| rule | recommendation | justification |
|---|---|---|
| `symmetry` | **KEEP unchanged** | primitive (R2 worked failure); 13 lines; most-used rule in the repository |
| `transitivity` | **KEEP despite derivability** | R1a reduces it to `substitute`, saving 16 lines, at the cost of reversed premise order and a silent behavioural difference when the LHS contains the middle term (R1c). Materially used: 2 dedicated tests plus the flagship `test_symmetry_transitivity_and_congruence_verify`. |
| `add_both_sides` | **KEEP unchanged** | primitive; the `congruence` reduction is blocked by the absence of lambda (R3) and the `substitute` reduction by total substitution (R4). 4 dedicated tests. |
| `subtract_both_sides` | **KEEP despite derivability** | R5a is a real reduction worth **8 lines** — the smallest saving on the table — and it forces every subtraction step to be written `a + -k`. The clearest keep-despite-derivable case in this document. **Add a dedicated test** (currently 0). |
| `multiply_both_sides` | **KEEP; must gain the §5.1 term-level definedness check** | it is the bypass vector. Sound as a rule; unsound as shipped in combination with the missing D-036 registry. **Add a dedicated test** (currently 0). |
| `divide_both_sides` | **KEEP; move its obligation to the term level (§5.1)** | after the fix its `ObligationSpec` becomes redundant and can be deleted — **the only genuine TCB reduction this analysis found (18 lines)**, and available only *after* the fix, never before. Deleting the rule now would remove the language's only division guard. |
| `substitute` | **KEEP unchanged; document the eleven non-descended kinds (§5.4)** | the highest-leverage rule; 21 lines; it is what makes R1a possible at all. **0 dedicated tests — the most serious coverage gap on the table**, given it is also the rule with the only real capture risk. |
| `congruence` | **KEEP; pin the §5.2 defence with a test** | primitive; the reduction blocker (no lambda) is a language fact recorded in D-041. Its safety for partial functions depends on a downstream type check that nothing asserts. |
| `modus_ponens` | **KEEP unchanged** | primitive; the only route from an implication to its consequent. |
| `modus_tollens` | **KEEP; add a test** | **0 successful applications in the entire suite.** The R8a alternative is an `assume`d contrapositive — a trust downgrade. 17 lines. |
| `and_intro` | **KEEP; consider a premise shape check** | 11 lines, the second cheapest rule, not derivable. 0 dedicated tests. |
| `and_elim_left` | **KEEP; add a test** | **0 successful applications.** R7a's alternative assumes the projection axiom. 15 lines. |
| `and_elim_right` | **KEEP as a separate rule; add a test** | **0 successful applications.** Merging with `and_elim_left` behind a `side` parameter saves **7 lines** and makes the surface a model writes less obvious. Not worth it. |
| `weaken_inequality` | **KEEP; add a test** | **0 successful applications.** 22 lines. Its doc records the property that makes it valuable — *there is no rule that strengthens `<=` to `<`* — and that asymmetry is asserted by an executed test. Deleting the weakening direction while keeping the guard against the strengthening direction would be incoherent. |
| `add_inequality` | **KEEP unchanged** | primitive (lambda blocker). 0 dedicated tests. |
| `multiply_inequality` | **KEEP unchanged — it is the reference design** | the only rule whose obligation is not bypassable (measured). It demonstrates the pattern the definedness work in §5.1 should generalise: keep the relation, emit the side condition, refuse to reach VERIFIED without it. |

### Should the kernel change at all?

**No — the rule set should not change.** Concretely:

1. **The rules are 6% of the TCB.** 270 of ~1 423 trusted lines. `_expr` in
   `backends/canonical.py` (185 lines) is larger than all 16 `apply` bodies combined
   (121 lines). Reduction effort spent on rules is effort spent on the wrong 6%.
2. **The most aggressive legal reduction (16 → 10) saves 86 lines: 6.0% of the TCB**, while
   removing six writable steps. Against "minimise TCB at fixed trusted semantic power",
   the power falls and the TCB barely moves. Filter B forbids it and filter B is right.
3. **Of the six reductions that compile, only two are genuine.** R1a (`transitivity`) and
   R5a (`subtract_both_sides`) are real and are worth 16 and 8 lines. R6a
   (`divide_both_sides`) works only because of the §5.1 defect. R7a, R8a and R9a
   (`and_elim_left`, `modus_tollens`, `weaken_inequality`) all replace a checked rule with
   an `assume` — trust downgrades under D-039's lattice, not reductions.
4. **The one real reduction available (deleting `divide_both_sides`'s `ObligationSpec`)
   only becomes available after fixing §5.1**, and the fix is a term-level definedness
   pass — outside the kernel entirely.

**What should change** is the obligation model, in this order:

1. **§5.1 (critical)** — implement the D-036 definedness registry as a term-level pass over
   `DeriveStmt.conclusion` (and over `assume` / `prove` / `goal` propositions), so that a
   CONTRACTED operation generates its precondition regardless of which rule introduced it.
   Add a regression test built from the six-line exploit above.
2. **§5.3** — route closed obligation propositions through
   `verification/obligations/evaluate.py` and map a decided `False` to
   `REFUTED → REJECTED`, per D-038.
3. **Test coverage** — one dedicated positive-and-rejection test per rule for the nine that
   have none, and raise `test_x3_…`'s floor from `>= 8` to `== len(RULES)` by giving it
   shape-appropriate premises per rule instead of `a = b` for all.
4. **§5.6** — assert the resolution precondition inside `kernel.apply` (~3 lines).
5. **§5.4 / §5.2 / §5.7** — documentation and small hardening.

Items 1–3 add lines to the trusted base. That is the correct direction: the objective is
minimum TCB **at fixed trusted semantic power**, and right now the semantic power the
system claims (a checked divide-by-zero guard) exceeds the power it has.

---

## 7. What I did NOT verify

Stated explicitly so no reader infers coverage from silence.

1. **Γ-frame discipline for premises (D-035).** I did not test whether a fact established
   inside a `forall` body, a `concept`, or the new `scope` frame can be cited as a premise
   outside that frame. That is `check.py` / `refinement.py` territory and the lead is
   editing it concurrently; any result I produced would have been measured against a
   half-landed implementation. **This is the highest-value untested area adjacent to my
   scope**, because §5.5's clean result covers only *syntactic* capture inside the kernel,
   not *scope escape* through the premise pool.
2. **Soundness of the rules relative to a formal semantics.** I checked each schema against
   the standard ordered-field / propositional reading and against HML's own documented
   contracts. There is no mechanised semantics to check against, and I did not build one.
3. **Whether `expr_identity` has collisions on resolved trees.** D-027 records that none was
   found; I re-tested only the specific cases relevant here (`forall`/`exists`,
   `exp`/`log` callees, `1`/`1.0`, unresolved `Ref`s). I did not fuzz it.
4. **The `1`/`1.0` normalisation's interaction with `Integer` vs `Real` typing.**
   `expr_identity(1) == expr_identity(1.0)` is `True` by D-027's deliberate choice (booleans
   correctly excluded). I confirmed `transitivity` will bridge an `Integer` and a `Real`
   middle term and `modus_ponens` will match `P(1)` against `P(1.0)`. Whether that can
   produce an ill-typed certified conclusion depends on the type checker's treatment of the
   author's written conclusion, which I did not exhaustively probe.
5. **Backend faithfulness for derivations.** Not in scope; covered by
   `tests/reasoning/test_backend_loss.py`.
6. **Performance / termination.** `_substitute` is recursive over expression trees with no
   depth bound. I did not test a deeply nested expression for `RecursionError`. D-040 took
   care to make `find_cycle` iterative for exactly this reason; `_substitute` did not get
   the same treatment. Unmeasured, flagged.
7. **Whether the `examples/` corpus uses any rule.** `grep` over `examples/` found no
   `derive` statements at all, so the usage figures in §2 come entirely from the test
   suite. No shipped example exercises the reasoning spine.
8. **The full suite's green status.** One pre-existing, unrelated failure was present in the
   live tree (`tests/freeze/test_quarantine.py`, the lead's new `scope` keyword). I did not
   investigate or fix it; it does not touch `reasoning/`.
