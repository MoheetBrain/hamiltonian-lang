# V1 Backend Support Matrix — Lean, Stan, SymPy/Python

Author role: Lean/Stan Interoperability Agent
Phase: HML-V1-CONCEPT-001 Phase 8
Machine-readable twin: `src/hamiltonian_lang/v1/backend_support.py`
Tests: `tests/v1/test_backend_support.py`
Probe date: 2026-08-05

This document states, per backend and per layer, what survives translation, what is lost,
and **whether a real toolchain ever saw it**. The V0 backends (`backends/{lean,stan,sympy}.py`)
are frozen and were not modified.

> **No general HML↔Stan or HML↔Lean round-trip equivalence is claimed here.** It does not
> exist. Sections 4 and 6 give the measured reasons.

---

## 0. Toolchain reality on this machine

Everything below was probed, not assumed.

| Toolchain | Present | Version | How it was probed |
|---|---|---|---|
| `lean` | **yes** | 4.32.2 (arm64-apple-darwin24.6.0, `f3b06c705e6c`) | `~/.elan/bin/lean --version` |
| `lake` | yes | 5.0.0-src+f3b06c7 | `~/.elan/bin/lake --version` |
| **Mathlib** | **NO** | — | `import Mathlib` → `unknown module prefix 'Mathlib'` |
| `stanc` / CmdStan | **NO** | — | not on `PATH`; no `~/.cmdstan`; no `cmdstanpy`/`pystan` in the venv |
| `sympy` | yes | 1.14.0 | `.venv/bin/python -c "import sympy; print(sympy.__version__)"` |

Lean was **not** installed when Phase 8 began; `elan` downloaded toolchain `v4.32.2` on
first invocation. So Deliverable 3 applies: a Lean kernel was genuinely run, and section 3
records exactly what it accepted.

**The Mathlib gap is the most consequential fact in this document.** Core Lean 4 has `ℕ`,
`ℤ` and `Prop`. It does **not** have `ℝ`, `abs` on `ℝ`, or any measure theory. Every HML
scalar except `Bool`, `Natural`, `PositiveNatural` and `Integer` maps to `ℝ`, and the V0
Lean backend emits `import Mathlib` at the top of every file. Consequently **no ℝ-typed
HML module can be checked on this machine at all** (section 4).

---

## 1. Three ways "the compiler accepted it" is a lie

Each was reproduced here, and each is the reason for a specific rule in
`backend_support.py`.

### 1.1 `sorry` compiles, and certifies a false theorem

```
$ cat SorryIsNotProof.lean
set_option autoImplicit false
theorem definitely_false : (1 : Nat) = 2 := by sorry

$ ~/.elan/bin/lean SorryIsNotProof.lean
SorryIsNotProof.lean:2:8: warning: declaration uses `sorry`
EXIT=0
```

Exit status 0 for a demonstrably false theorem. The discriminator is `#print axioms`:

```
'A.status_proved'    does not depend on any axioms
'A.status_disproved' depends on axioms: [propext, Quot.sound]
'A.skeleton_only'    depends on axioms: [sorryAx]        <-- the marker
```

Hence `ToolchainEvidence.sorry_free`, which is **mandatory** for Lean: a Lean run that
exited 0 without answering the `sorry` question is rejected at construction.

This matters directly, because **the V0 Lean backend closes every obligation with
`sorry` by design** (design freeze §8, no proof search). So even if Mathlib were
installed, *no theorem emitted by the V0 Lean backend would ever count as verified.*

### 1.2 Lean silently invents types that do not exist

```
$ echo '#check (Real)' > RealProbe.lean && ~/.elan/bin/lean RealProbe.lean
RealProbe.lean:1:8: error(lean.unknownIdentifier): Unknown identifier `Real`
EXIT=1

$ cat AutoImplicit.lean
theorem t : ∀ x : Real, x = x := by intro x; rfl
#print t

$ ~/.elan/bin/lean AutoImplicit.lean
theorem t.{u_1} : ∀ {Real : Sort u_1} (x : Real), x = x := fun {Real} x => Eq.refl x
EXIT=0
```

`Real` does not exist, yet the file compiles. Lean's default `autoImplicit` bound `Real`
as an **implicit variable of arbitrary sort**, so the accepted theorem is a vacuous claim
about an arbitrary type — not about the reals. With the option off, Lean is honest:

```
error: Unknown identifier `Real`
Note: It is not possible to treat `Real` as an implicitly bound variable here because
the `autoImplicit` option is set to `false`.
```

**Every Lean probe behind this matrix sets `autoImplicit false` and
`relaxedAutoImplicit false`**, and `tests/v1/test_backend_support.py` does the same.

### 1.3 Executing generated Python proves only that it runs

`linear_regression.hml` renders to a SymPy module that executes cleanly while reporting
**eight** dropped or weakened constructs. Execution is a syntax check, not a semantics
check, and is recorded that way in every SymPy evidence record's `does_not_establish`.

---

## 2. How to read the matrix

`status` describes what survives **translation**. `toolchain` separately describes whether
a compiler was actually run. The two are orthogonal on purpose: a construct can translate
faithfully into a target nothing here can check, and a construct can compile while meaning
something other than it did.

| Status | Meaning |
|---|---|
| **supported** | survives with no declared loss |
| **partial** | translates, but something is dropped, weakened or approximated — losses enumerated |
| **unsupported** | no faithful encoding exists; a reason is mandatory |

Toolchain column: **yes** = a real compiler accepted it (for Lean: exit 0 *and* no
`sorryAx`); **no** = nothing was run, or the run failed; the note says which.

Across the 69 cells: 3 supported, 29 partial, 37 unsupported; **20 toolchain-verified, 49
not**. No Stan cell is verified, because `stanc` is absent.

---

## 3. Deliverable 3 — Lean kernel acceptance actually obtained

Lean **is** installed, so this section records real runs rather than an excuse. All files
were hand-written over `ℕ` with `autoImplicit false`. All are `sorry`-free.

### 3.1 The two quantifier scopings — proved and refuted

```
$ cat QuantifierScoping.lean
set_option autoImplicit false
set_option relaxedAutoImplicit false
namespace Scope
theorem forall_exists : ∀ a : Nat, ∃ b : Nat, b > a := fun a => ⟨a + 1, Nat.lt_succ_self a⟩
theorem exists_forall_is_false : ¬ (∃ b : Nat, ∀ a : Nat, b > a) := by
  rintro ⟨b, hb⟩; exact absurd (hb b) (Nat.lt_irrefl b)
end Scope
#print axioms Scope.forall_exists
#print axioms Scope.exists_forall_is_false

$ ~/.elan/bin/lean QuantifierScoping.lean
'Scope.forall_exists' does not depend on any axioms
'Scope.exists_forall_is_false' does not depend on any axioms
EXIT=0
```

This is the strongest positive result in Phase 8. The two scopings HML deliberately keeps
distinct (`examples/logic/quantifier_scope.hml` and `..._reversed.hml`) are, over `ℕ`, one
**provable** and the other **refutable** — Lean's kernel agrees with HML that they are
different propositions, and neither proof touches an axiom.

It does **not** establish the `ℝ` case, which is what the HML examples actually say.

### 3.2 Epistemic statuses

`EpistemicProbe.lean` — exit 0, no diagnostics — encodes exactly five statuses: `proved`
(theorem + real proof term), `definitionally_true` (`rfl`), `disproved` (proof of a
negation), `conjectured` (Prop-valued `def`, deliberately unproved) and
`model_conditional` (hypothesis carried in the type). `AxiomAudit.lean` adds a
`sorry`-closed **false** theorem as a control; see §1.1 for its output.

### 3.3 V1 layer shapes

`V1Layers.lean` — exit 0, no `sorry` — encodes a concept-shaped definition with a proved
invariant, an Entailment via modus ponens, a ConverseClaim stated but not asserted, a
Counterexample as a proof of a negation, a discourse Goal discharged by a proof term, and
an open Goal left undischarged.

```
'HmlV1Probe.double_even' depends on axioms: [propext]
'HmlV1Probe.entailment_mp' does not depend on any axioms
'HmlV1Probe.counterexample_not_all_even' depends on axioms: [propext]
'HmlV1Probe.discharge_goal_comm' does not depend on any axioms
```

### 3.4 Derivation chains, and the obligation contrast

`Derivation.lean` — exit 0, no `sorry` — a `calc` chain plus a cancellation step
(`Nat.eq_of_mul_eq_mul_left`) whose `0 < a` side condition is supplied explicitly. Both
theorems depend on no axioms. Omitting the side condition does not make it disappear: it
becomes a `sorry`, and the theorem becomes unproved.

**Lean demands the side conditions the transformation layer cares about. SymPy discards
them (§6.2). The two targets fail in opposite directions, and only one direction is safe.**

### 3.5 What none of this establishes

- **No V1 Lean emitter exists.** Every probe was written by hand. These results show the
  encoding *shapes* are realisable in Lean 4; they do not show HML produces them.
- **Nothing `ℝ`-typed was checked**, and `ℝ` is what HML actually uses.
- **The V0 Lean backend's own output does not compile here** — §4.1.

---

## 4. The V0 Lean backend's output, submitted to Lean

```
$ hml views examples/logic/quantifier_scope.hml --target lean > QuantScope.lean
$ ~/.elan/bin/lean QuantScope.lean
QuantScope.lean:14:0: error: unknown module prefix 'Mathlib'
EXIT=1
```

Two repair attempts, both rejected:

| Attempt | Result |
|---|---|
| strip `import Mathlib`, default `autoImplicit` | `error: failed to synthesize instance of type class LT ℝ` (×2) |
| strip `import Mathlib`, `autoImplicit false` | `error: Unknown identifier ℝ` (×4) |

The middle row is the instructive one: with `autoImplicit` at its default, Lean bound `ℝ`
as an implicit variable of arbitrary sort and got as far as failing to find an `LT`
instance for it — i.e. **it was elaborating a fabricated type**.

**This does not mean the emitted Lean is wrong.** The statements may well be faithful;
they simply cannot be checked here. Absence of verification is not evidence of a defect
and is not recorded as one.

---

## 5. V1 layers

### 5.1 Concept registry

| Backend | Status | Toolchain | Principal losses |
|---|---|---|---|
| Lean | partial | yes (shapes, over ℕ) | concept flattened to `Concept_*` prefixes, not an object; `extends` dropped; `example`/`counterexample` members dropped; lifecycle, provenance, aliases and `compresses` have no encoding; `claimStatus` lost — a `sorry`-closed theorem is textually identical to a proved one |
| Stan | **unsupported** | no (`stanc` absent) | no user-defined types, no namespaces, no propositions. Invariants, equivalences, counterexamples and obligations have no Stan form; the one partial route (`functions` block) is explicitly outside the V0 importer's subset. Any `PositiveReal` parameter also blocks round-tripping |
| SymPy | partial | yes (executes) | members name-mangled to `Concept__member`; quantified invariants dropped (no binder); **no justification object** — `sp.Eq(x+y, y+x)` auto-evaluates to bare `True`, so a proved invariant and a conjectured one are indistinguishable |

### 5.2 Concept-minting protocol

**Unsupported in all three.** The protocol is a *process* whose output is an admission
report about the registry, not a mathematical object in the concept's domain. No target
has a surface for it, and manufacturing one (an `axiom` asserting admission) would state
something the protocol never claimed. The obligations the protocol *generates* are a
different thing, covered by §5.1 and §5.5.

### 5.3 Semantic morphology (concept families)

**Unsupported in all three**, for three different reasons.

- **Lean** — an identifier is an atom carrying no structure a checker can read. The
  tempting encoding (`Estimation.estimator` as a namespace) imposes a tree on a relation
  that need not be one, and Lean treats the components as opaque path segments anyway, so
  it gains nothing over a naming convention. Note the spec forbids *generating* morphology
  ("DECLARED, never GENERATED"), so there is no derivation rule to translate in any case.
- **Stan** — identifiers are flat ASCII with no namespace mechanism at all.
- **SymPy** — a `Symbol` name is an opaque string; assumptions constrain values, not
  vocabulary. Critically, the estimator/estimate/procedure distinction this layer exists
  to enforce would have to be carried by **types**, and all three become bare `Symbol`.

The family's *content* does survive into Lean and SymPy — members are ordinary typed
declarations, invariants are ordinary claims. It is the morphological relation between the
**names** that has no encoding.

### 5.4 Transformation edges (L2: Step, Derivation)

| Backend | Status | Toolchain | Principal losses |
|---|---|---|---|
| Lean | partial | yes (`calc` + cancellation, over ℕ) | `calc`/`rw` are a genuine home for a Derivation chain and Lean **demands** side conditions rather than discarding them — the safe failure direction. But `simplify` cannot record *which* identity was used (`simp`/`ring` close goals without a citable identity in the source); `square_both_sides` is a weakening with nothing marking it one-way; `differentiate`/`integrate`/`limit` are ℝ-typed, hence uncheckable here |
| Stan | **unsupported** | no | not an algebra system: no symbolic rewriting, no equation objects, no way to state `by != 0` except in a comment |
| SymPy | partial | yes (probed directly) | performs the operations, discharges **none** of the obligations — see §6.2 |

Both targets lose the L2/L3 distinction: a Derivation is not an Entailment and there is no
coercion, but Lean's `calc` works over equalities and implications with the same syntax.
The distinction must be preserved upstream.

### 5.5 Inference edges (L3: Entailment, Equivalence, Counterexample)

| Backend | Status | Toolchain | Principal losses |
|---|---|---|---|
| Lean | partial | yes (modus ponens, converse, counterexample, over ℕ) | `claimStatus` does not survive into the file — the proved/conjectured separation exists only in `#print axioms` output, which is not part of the artefact. A ConverseClaim states cleanly as a Prop-valued `def` but looks nothing like the theorem beside it, so its relation to the Entailment is conventional rather than structural |
| Stan | **unsupported** | no | no propositions, no implication connective |
| SymPy | partial | yes | `sp.Implies(P, Q)` exists and correctly does not license `Implies(Q, P)` — but there is **no quantifier** (probed: no `ForAll`, no `Exists`), so quantified edges are dropped; no proof object and no inference-rule record; `sp.Eq` auto-evaluates to a bool, collapsing an equivalence edge into a truth value with no status |

### 5.6 Epistemic status — the hardest rows

Summarised here; the per-status table is §7.

| Backend | Status | Toolchain | Verdict |
|---|---|---|---|
| Lean | partial | yes (5 of 16 statuses) | 5 expressible and kernel-accepted, 5 library-gated, 6 category mismatches |
| Stan | **unsupported** | no | no propositions, so nothing for a status to qualify. The one superficially plausible mapping — a p-value to `real<lower=0, upper=1>` — is exactly the PValue-to-posterior conflation the layer forbids, and Stan's types could not tell the two apart |
| SymPy | **unsupported** | no | no justification object of any kind. Probed: `sp.Eq(x+y, y+x)` is bare `True`, and `sp.Eq` has no `status` attribute — so `proved`, `conjectured`, `estimated` and `fail_to_reject` all arrive at the same representation. **A target that represents every status identically represents none of them**, so the honest verdict is unsupported, not partial |

### 5.7 Discourse state (L5: Goal, Discharge, Case)

| Backend | Status | Toolchain | Principal losses |
|---|---|---|---|
| Lean | partial | yes (goal stated + discharged, over ℕ) | a Goal is not a Theorem, and Lean has one keyword for both, so the intent/claim distinction is not carried. **The open-goal set — the layer's actual product — has no representation**: an undischarged goal is just a `def` nobody proved, and Lean will not report it. `sorry` would make it visible, but `sorry` also makes false theorems compile (§1.1), so it cannot serve as the marker. Case/Otherwise/EndCase map inside a proof, not onto module structure. Discharge-by-Assumption is correctly blocked (hypotheses stay in the type); discharge-by-Evidence has nothing to bite on, since Lean has no Evidence category |
| Stan | **unsupported** | no | a fixed block sequence, not a discourse — and it already destroys interleaved declaration order (§6.1). No propositions for a Goal to range over |
| SymPy | **unsupported** | no | a module namespace has no open obligation. The `claims` list is a container, not a state: nothing distinguishes a discharged goal from an open one, and nothing reports the open set |

**Direct corroborating evidence:** V0 already measured that Lean's single `variable`
mechanism loses the `var`/`param`/`const`/`obs`/`index` distinction. Discourse state is a
strictly *finer* distinction than that one.

---

## 6. V0 constructs, carried over

These restate results already measured in `tests/roundtrip/test_importers.py` and
`docs/evaluation/HML_EVAL_001_PILOT_REPORT.md` §4. They are carried, not rediscovered.

| Construct | Lean | Stan | SymPy |
|---|---|---|---|
| declaration kind | partial — kind lost; `variable` is one mechanism | partial — `obs`/`param` survive as blocks; `const`/`index`/`rv` do not; grouping reorders | partial — every kind becomes a `Symbol` |
| refinement scalars | partial — carrier + hypothesis, not a subtype; a hypothesis is not part of the type | partial — **`PositiveReal` impossible**; see §6.1 | partial — `positive=True` works; `Probability`'s upper bound cannot be an assumption |
| `Quantity` / dimensions | **unsupported** — no units library | **unsupported** — Stan is dimensionless | **unsupported** — HML dimensions carry no unit |
| probability laws | **unsupported** — see §6.3 | partial — `~` survives, role lost, most families blocked | **unsupported** — dropped rather than emit ⅓ of a law |
| conditioning set | **unsupported** — no law to condition | **unsupported** — `~` carries none | **unsupported** |
| `infer` | **unsupported** | **unsupported** | **unsupported** — no inference engine |
| quantifiers | **supported** — nesting preserved; **verified over ℕ** (§3.1) | **unsupported** — none exist | **unsupported** — no `ForAll`/`Exists` (probed) |
| `require`/`prove`/`assume` | partial — `prove` faithful; **`require` weakened**: a constraint stated as a theorem may be literally false | **unsupported** — emitted as comments | partial — unquantified only; no proof, no status |
| objectives | **unsupported** — `IsMinOn` needs a set HML does not supply | **unsupported** | partial — expression recorded, nothing optimised |
| `solve` | **unsupported** — which existential is undetermined | **unsupported** — Stan samples, it does not solve | partial — targets recorded, nothing solved |
| `check dimension` | **unsupported** | **unsupported** | **unsupported** |
| `concept` | partial — flattened; `extends`, examples, counterexamples dropped | **unsupported** | partial — name-mangled |
| vectors / matrices | partial — `Fin n → T` **manufactures** bounds obligations the source never had | partial — shapes survive, element refinements do not | partial — `MatrixSymbol(n, 1)` is a column-matrix approximation; no element assumptions |
| `define` | partial — closest correspondence in the table (`def`) | partial — one-way: the importer rejects `transformed parameters` and `functions` | partial — **measured defect**, see §6.4 |
| observed values | partial — value survives as `def k : ℕ := 7`; "observed" does not | **unsupported** — see §6.1 | partial — value becomes an indistinguishable constraint |
| declaration order | **supported** | **unsupported** — see §6.1 | **supported** |

### 6.1 Stan cannot express strict positivity — the largest single limitation

Stan's `real<lower=0>` is a **closed** lower bound: it admits 0. HML's `PositiveReal`
excludes 0. Stan therefore cannot express strict positivity at all.

The V0 importer widens to `NonNegativeReal` on the way back, and the reconstructed program
is then **correctly rejected** with `HML-T413` — a scale must be strictly positive.

Because every scale parameter in every family is strictly positive, **most of the
distribution registry is outside the Stan round-trippable subset**: Normal, Beta, Gamma,
Exponential, Poisson, Cauchy and the rest each carry at least one `PositiveReal` role.
Only **Uniform, Binomial and Bernoulli** survive.

Two further measured Stan losses:

- **Observed values are lost.** Stan reads data from a data file, not from the program
  text. The backend honestly records `n = 20` in a comment header, but a comment is not
  code, the importer cannot recover it, and the round trip fails on a changed content hash.
- **Interleaved declaration order is destroyed.** Stan groups declarations into `data` and
  `parameters` blocks; HML declaration ordinals are positional, so an interleaved module
  comes back reordered and its content hash changes. The meaning is arguably unaltered;
  the identity is not. Neither fact is normalised away.

### 6.2 SymPy performs transformation steps and discharges none of their obligations

```
sp.cancel((x*y)/x)                -> y      # x != 0 neither recorded nor checked
sp.simplify((x-x)/x)              -> 0      # same
sp.simplify(sin(x)**2+cos(x)**2)  -> 1      # which identity? not recorded
```

This is **precisely the error the transformation layer exists to catch, committed silently
by the target**. Contrast §3.4: Lean demands the same side condition. The obligation must
therefore be discharged on the HML side — the target will neither do it nor complain.

### 6.3 The Lean route drops probability laws, and only the hash notices

The most dangerous loss in the table. A law would need a measurable space on the family's
support, a `MeasureTheory.Measure`, a density and a proof it integrates to one — none of
which is determined by a family name plus role labels, so the V0 backend drops it and says
so.

What makes it dangerous is measured: **the importer cannot know a law was ever there, the
reconstruction compiles perfectly happily, and only the content-hash comparison reveals
that meaning went missing.** A one-way test cannot detect this class of loss at all. This
is the strongest argument in the codebase for round-tripping as a validation method.

### 6.4 A V0 SymPy defect found by executing the output

Reported, **not fixed** — V0 is frozen at `hml-v0-baseline` and is outside this phase's
write scope.

```
module Min
def p : Proposition := forall x : Real . x = x
prove p
```

renders to a module containing `claims.append(p)` while `definitions` is empty, so it
raises `NameError: name 'p' is not defined` on import. The quantified body is dropped
correctly — SymPy has no binder — but the later reference to the name that definition
would have bound is still emitted. Also reproduced on
`examples/candidate_syntaxes/a_labelled_linear/6_quantifier_scope.hml`.

All 8 canonical examples under `examples/{algebra,concepts,logic,physics,statistics}` are
unaffected, because none of them names a quantified proposition and then proves it by
name. Found only by **executing** the output, not by reading it.

---

## 7. Which epistemic statuses can Lean express?

The central question of this phase. Sixteen statuses; **five have a Lean encoding that was
kernel-accepted here, eleven do not.** No encoding is invented for any of the eleven.

Two *different* reasons for "no encoding" are kept apart, because collapsing them would
itself be a modelling error:

- **library-gated** — Mathlib supplies the vocabulary; Mathlib is absent here. Installing
  it would move the row.
- **category mismatch** — the status is not a proposition about mathematical objects at
  all. **No library fixes this**, and recording it as library-gated would falsely imply a
  fix exists.

### 7.1 Expressible, and compiled here (5)

| Status | Encoding | Note |
|---|---|---|
| `proved` | `theorem <n> : <P> := <proof term>` | the one exact correspondence — Lean's `theorem` *is* a proof claim. Caveat that must travel with it: a `sorry`-closed theorem is textually identical |
| `definitionally_true` | `def` + `theorem … := rfl` | `rfl` is definitional equality, exactly what the status asserts. Closest fit in the table |
| `disproved` | `theorem <n> : ¬ <P> := <proof>` | a refutation is a proof of a negation, which is why `Justification.REFUTATION` discharges goals in HML too |
| `conjectured` | `def <n> : Prop := <P>` | statable, **not assertable** — correct, since `Justification.NONE` discharges nothing. Weakness is presentational: a reader must notice no theorem proves it |
| `model_conditional` | `theorem <n> (h_model : <M>) : <P>` | the model becomes a hypothesis in the type, so it propagates as a dependency exactly as `REQUIRED_CONTEXT` demands |

### 7.2 Library-gated — Mathlib has it, this machine does not (5)

| Status | What Mathlib would give | Why not here |
|---|---|---|
| `almost_sure` | `∀ᵐ x ∂μ, P x` | probed: `MeasureTheory.Measure` is an unknown identifier in core Lean |
| `converges_in_probability` | `MeasureTheory.TendstoInMeasure` | no measures, no filters over them |
| `asymptotically_equivalent` | `Asymptotics.IsEquivalent` along a filter; the mandatory `regime` picks the filter | needs Mathlib for both the filter library and `ℝ` |
| `approximately_equal` | `|a - b| ≤ ε`, with the mandatory `tolerance` | core Lean has no `ℝ` and no `abs` on it |
| `with_high_probability` | a bound `μ_n {ω \| P_n ω} ≥ 1 - δ(n)` with `δ(n) → 0` | **doubly blocked** — see below |

`with_high_probability` deserves its own note. Even *with* Mathlib installed there is no
determinate target, because **which** proposition it is depends entirely on the asymptotic
regime, and V1 carries the regime as an unstructured `bound_or_regime` context string
rather than a typed object. The spec is right that a regime is mandatory; until it is
typed, no encoding can be generated, and none is offered here.

None of these five was compiled, and none is marked as though it were.

### 7.3 Category mismatch — no library fixes these (6)

| Status | Why there is no Lean proposition for it |
|---|---|
| **`fail_to_reject`** | The sharpest row, and the one where **absence is a requirement, not a gap.** It records the output of a decision procedure applied to a sample; it asserts nothing about the world — that is the entire point of the layer, which renders it as "This is not evidence that H0 is true". Any Lean encoding must be a `theorem`, and a `theorem` is a Proof claim; `PROHIBITED_COERCIONS` forbids Evidence→Proof precisely so that failing to reject H0 cannot become proving H0. **Emitting a theorem here would perform in the backend the exact conflation the layer was built to prevent.** |
| `reject` | Symmetric. Rejecting at a significance level is not a disproof — `PROHIBITED_COERCIONS` blocks Evidence→Refutation for exactly this reason — so `theorem : ¬ H0` is the *wrong* statement, not a rough one |
| `estimated` | Attaches to a **value obtained from one sample**. Lean can formalise an estimator as a function and prove things about it, but there is no proposition whose truth is "this number was estimated from that data"; formalising the sample as a term would make the claim be about the formalisation. The concept-family spec makes the same point from the other side: "the estimate is unbiased" is a type error, because unbiasedness is a property of the estimator, not of a number |
| `consistent_with` | Compatibility, and the layer says outright that compatibility is not support. Consistency in Lean's sense is *metatheoretic* — no contradiction is derivable — which a theory cannot state about itself, and which is a different claim from the statistical one anyway |
| `possible` | `Justification.CREDENCE`: a degree of belief **about** a model, not a proposition **within** one. Lean's `Prop` universe has no modal operator, and `∃ …` would be a different, much stronger claim |
| `unsupported` | Asserts the **absence of grounds** for P — a statement about the epistemic record, not about P. `¬P` is a different and much stronger claim (that is `disproved`), and silence in a Lean file asserts nothing |

**No encoding is proposed for any row in §7.3.** `tests/v1/test_backend_support.py`
asserts this mechanically: a `LeanEncoding` marked inexpressible that carries an encoding
string is rejected at construction.

---

## 8. What this document does not claim

1. **No general HML↔Stan or HML↔Lean round-trip equivalence.** Sections 6.1 and 6.3 give
   the measured reasons it does not exist.
2. **No V0 backend output has been verified by any toolchain.** The Lean output does not
   compile here (§4); the Stan output has never been seen by `stanc`; the SymPy output
   executes, which is a syntax check only (§1.3), and does not always even do that (§6.4).
3. **The Lean results in §3 are hand-written encodings, not generated ones.** No V1 Lean
   emitter exists. They establish that the *shapes* are realisable, not that HML produces
   them.
4. **Nothing `ℝ`-typed has been checked by Lean**, and `ℝ` is what HML actually uses.
5. **No claim that any HML module is mathematically correct.** Every V0 Lean obligation is
   closed with `sorry` by design, and a `sorry`-closed theorem proves nothing (§1.1).
6. **49 of 69 cells are unverified**, and a test guards against that majority quietly
   shrinking for reasons other than real toolchain runs.

## 9. What would move the matrix

| Action | Effect |
|---|---|
| Install Mathlib | Unblocks every `ℝ`-typed Lean row and moves 4 epistemic statuses from library-gated to expressible. **Would not** move any §7.3 row |
| Install `stanc` | Allows the Stan rows to be verified for the first time. Does **not** fix `PositiveReal` — that is a language-level limit, not a tooling one |
| Type the asymptotic regime | Makes `with_high_probability` determinate enough to encode, given Mathlib |
| Build a V1 Lean emitter | Would let §3's hand-written shapes be replaced by generated output — the only way these rows become claims about HML rather than about Lean |
| Fix §6.4 | Requires a change to frozen V0; out of scope here |
