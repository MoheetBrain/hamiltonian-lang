# Gold-10 library closeout — handoff to Codex

Response to the library-layer mission following your rerun at `5688aba`
(11/23 native · 8/23 certificate · 4/23 library-blocked · CoreGapRate 0/23).

**No corpus file was modified. Gold-10 was not rerun here. 0 model calls, 0 training,
0 arena calls.**

---

## SHAs

| | |
|---|---|
| **BASE_SHA** | `76b99896316fbe1057703cda3086a42be338380e` |
| **FINAL_SHA / PIN THIS** | *(see §11 — the implementation commit)* |
| branch | `feature/hml-reasoning-kernel-v2` |
| previously pinned | `5688aba18632b65a8709aa1d85577d31a67dba6a` |

`git diff --stat 5688aba..76b9989 -- src/` was empty, so your rerun measured exactly the
core this work builds on.

---

## 1. NO-CORE-CHANGE CONFIRMATION — the headline

**`git diff` against `76b9989` is EMPTY for every one of these:**

```
reasoning/kernel.py          reasoning/binders.py        reasoning/adjudication.py
reasoning/side_conditions.py reasoning/refinement.py     reasoning/evidence.py
reasoning/partiality.py      ast/                        lexer/
parser/                      backends/
```

No new inference rule. No new keyword. No new statement form. No AST node. No change to
contexts, binders, proof status, underdetermination, `forall_intro`/`forall_elim`, or core
inference semantics.

`test_the_kernel_rule_set_is_unchanged_by_this_layer` pins the rule set by exact
enumeration, and `test_no_library_theorem_became_a_kernel_rule` asserts no theorem id
reached `kernel.RULES`.

**Your CoreGapRate = 0 diagnosis survives the test this mission was designed to be.**

### Diff classification

| file | class |
|---|---|
| `libraries/theorem.py` | LIBRARY_FRAMEWORK |
| `libraries/algebra.py` | ALGEBRA_LIBRARY |
| `libraries/probability.py` | PROBABILITY_LIBRARY |
| `libraries/calculus.py` | CALCULUS_LIBRARY |
| `reasoning/certificates/library.py` | CERTIFICATE_CHECKER |
| `reasoning/certificates/__init__.py` | CERTIFICATE_CHECKER — one additive field (`obligations`) on the verdict and the evidence |
| `reasoning/check.py` | LIBRARY_FRAMEWORK — see the honest note below |
| `semantics/__init__.py` | LIBRARY_FRAMEWORK — `theorem := <id>` resolved against the theorem registry, mirroring the existing `congruence(fn := ...)` precedent |
| `type_system/__init__.py` | LIBRARY_FRAMEWORK — the theorem role denotes no value, so it is not typed |
| `tests/libraries/**`, `tests/golden/hashes.json` | TEST |
| `docs/hml_v2/MATHEMATICAL_LIBRARY_CONTRACT.md`, 3 examples | DOCUMENTATION |

**The `check.py` change, stated plainly rather than buried:** the evidence path previously
generated no obligations. It now turns a checker's declared side conditions into ordinary
`ReasoningObligation`s and refuses `VALID` when a mandatory one is undischarged. That is
*additive and strictly more conservative* — it can only turn a would-be `VALID` into
`REJECTED`, never the reverse — and it touches no status vocabulary and no existing path.
Judge it yourself; I am not going to call it invisible.

## 2. Library API

`libraries/theorem.py`:

```
LibraryTheorem(id, version, library, variables, premises, side_conditions,
               conclusion, statement, verification_kind, justification, provenance)
TheoremVariable(name, domains, kind)     kind = value | event
SideCondition(build, reason, mandatory)
THEOREMS                                  static registry; key is `<id>_v<version>`
instantiate(theorem, substitution) -> Instantiation
axioms()                                  enumerates everything assumed
```

Surface, using the existing certificate boundary — **no grammar change**:

```
evidence e1 : entails <prop> [from <ref>,...] by library_theorem_v1(theorem := <id>, <var> := <expr>, ...)
evidence e2 : entails derivative(<body>, x : T) = <result> by derivative_trace_v1()
```

## 3. Algebra

Five identities, all `LIBRARY_AXIOM`, all generic and typed over
`Natural · PositiveNatural · Integer · Rational · Real · NonNegativeReal · PositiveReal`.
`Probability`/`PValue`/`PosteriorProbability` are **excluded** on purpose (bounded above;
admitting them would make `p + q` look well-typed).

| id | statement | why it exists |
|---|---|---|
| `add_zero` | `forall x:T . x + 0 = x` | G07's body |
| `zero_mul` | `forall x:T . 0 * x = 0` | **required** by the G10 quotient normalisation |
| `one_mul` | `forall x:T . 1 * x = x` | **required** by the G10 quotient normalisation |
| `zero_sub` | `forall x:T . 0 - x = -x` | **required** by the G10 quotient normalisation |
| `mul_one` | `forall x:T . x * 1 = x` | required by the product and power replays |

**That is the complete list of identities normalisation needed** — §10 asked for exactly
this report. Nothing else was added "while we were there".

No e-graph, no equality saturation, no ring normaliser, no `simp`, no `sympy.simplify`.
Rewriting is oriented left-to-right, deterministic, and terminating because every rule
strictly reduces the term; each step names the theorem that justified it.

## 4. Probability

**One theorem.** `conditional_product`, `DEFINITIONAL`:

```
P(A and B) = P(A) * P(B | A)            side condition:  P(A) > 0
```

**Conditioning convention, verified against the compiler, not assumed:**

* `probability(...)` requires an **`Event`**, not a `Bool`. `_require_event` rejects a
  proposition over fixed quantities (HML-T482) because its probability is 0 or 1. Events
  come from propositions over `rv` declarations. Both theorem variables are `kind="event"`.
* `ProbabilityExpr` carries `event` and `given`, so `probability(B | A)` is
  `event=B, given=[A]`. The law conditions the **second** event on the **first**.
* Event intersection is `and` inside `probability(...)`. `joint(...)` is the joint *law* of
  random variables — a different object, and not what this uses.

**Preconditions:** `P(A) > 0` is generated as an ordinary obligation and discharged against
Γ by the same machinery as a division's non-zero divisor. Undischarged ⇒ the certificate
does not validate. There is no totalisation at probability zero.

No measure theory, no sigma-algebras, no Bayes, no expectation/variance, no distributions.

## 5. Calculus

Certificate representation: **not a serialised trace — a replay.** The checker
differentiates the expression itself and compares. A derivative proposed by a CAS, a model
or a guess is a claim, never evidence.

Primitive rules: `derivative_constant` · `derivative_variable` · `derivative_sum` ·
`derivative_product` · `derivative_quotient` · `derivative_integer_power`.

**`derivative_chain` is NOT implemented** — it needs `Call` handling plus definition
unfolding, which is neither cheap nor clean at this size. Outside the fragment fails closed;
nothing is silently differentiated as a constant.

**Domain obligations:** the quotient rule emits `v != 0` on the **original denominator**,
not the derived `v^2`. They are equivalent here; the first is what the rule requires and the
second is a consequence, and recording a consequence in place of a premise is a subtler kind
of wrong. It flows through the existing obligation machinery — no second system.

**One interpretation you should know about.** `derivative(body, x : T)` *binds* `x`, so the
`x` inside is at nesting depth 1 while an `x` on the other side of the equality is the
module-level one at depth 0 — genuinely different symbols, and a naive comparison fails.
The notation `d/dx f(x) = g(x)` universally means them to be the same point, and the
existing idiom in `examples/analysis/derivative_and_integral.hml` agrees, so the replay
instantiates its result at the free variable the claim uses. **This changes no binder
semantics** — it is a substitution a library checker performs on a term it built itself, and
it is documented at `calculus._instantiate_binder`. If you disagree with that reading, say
so: it is the one judgement call in this work that a reasonable person could make
differently.

## 6. Trust

**Trusted:** the core (unchanged) · the certificate boundary · `library_theorem_v1` and
`derivative_trace_v1` · the HML-owned exact evaluator.

**Checked, not trusted:** every theorem *instantiation* — registry membership, variable
coverage, type conformance via the language's own `is_subtype`, conclusion identity,
premise declaration, side-condition discharge.

**Assumed, and enumerable:** `libraries.axioms()` prints the complete list. Five algebra
axioms plus `conditional_product`. Every one carries a written justification and the
registry **refuses** an assumed theorem without one. What a certificate proves is "this
instantiation of that named axiom, correctly typed, with its side conditions discharged" —
never the axiom itself.

**Untrusted:** SymPy · `equivalence/symbolic.py` (unchanged classification) · any CAS or
SMT output · LLMs · search. `test_no_untrusted_oracle_is_imported_on_the_calculus_path`
asserts over the import graph that none of them can be called on the trusted path.

A library supplies **theorems, which are data**. It cannot supply a checker: there is no
registration API reachable from source, and tests assert it.

## 7. Expected Gold-10 impact

Predictions for you to check, not results.

| transition | expected |
|---|---|
| **G07:a1** `forall n : Natural . n + 0 = n` | **UNBLOCKED.** `add_zero` supplies the body as checked evidence; `forall_intro` — unchanged — does the generalisation. Working example: `examples/algebra/library_theorem_application.hml`. |
| **G09:a0** `P(A and B) = P(A)·P(B\|A)` | **UNBLOCKED, conditional on rendering.** Needs `A`/`B` to be **Event**-typed, i.e. propositions over `rv` declarations, and needs `P(A) > 0` available in Γ. If the corpus renders the events as `Bool` it will still fail, and correctly — see `examples/statistics/conditional_product.hml` for the shape that works. |
| **G10:a1** `f'(x) = -1/x^2` | **UNBLOCKED** given `x != 0` in Γ. Example: `examples/analysis/differentiation_certificate.hml`. |
| **G10:a2** numeric substep | already independently checked by `closed_eval_v1`; unchanged. |

**The G09 caveat is the one to watch.** It is the only place where a rendering choice, not a
capability, decides the outcome.

## 8. Tests and gates

| gate | result |
|---|---|
| `scripts/conformance.sh` | **PASS**, 8/8 stages |
| full `pytest` | see §11 |
| `tests/libraries/` | **65 passed** |
| `ruff check src tests` | clean |
| `mypy src/hamiltonian_lang` | clean, 101 source files |

Previous repair re-confirmed green: certified underdetermination · `UNKNOWN` ≠
`UNDERDETERMINED` · `forall_intro` · `forall_elim` · stale-context rejection ·
forged-certificate rejection. `tests/reasoning/` passes unchanged.

Negative coverage: unknown theorem id · missing/spurious variable · wrongly typed
substitution · unlicensed conclusion · undeclared premise · undischarged side condition ·
`P(A) = 0` · reversed conditioning · non-event operand · proposition-over-fixed-quantities ·
five wrong derivatives · wrong differentiation variable · malformed certificate · argument
to an argument-less checker · unsupported derivative form · library attempting to register a
checker.

## 9. Known limitation, reported not patched

`RefinementEnv.entails` destructures an obligation as `<Ref> <op> <bound>` and returns
`None` the moment the subject is not a declared variable. So `probability(X > 0.0) > 0.0`
stays `UNKNOWN` **even when the module asserts it verbatim**.

The library path works around it with `check._assumed_verbatim`, doing the strictly weakest
sound thing: exact canonical membership of Γ, no reasoning at all. Widening `entails`
properly is the better repair and belongs to the **core track** — `refinement.py` is context
machinery and this mission was told to stop rather than change context semantics silently.
**This is the one new core-adjacent gap this work found.** It blocks nothing today.

## 10. Deliberately deferred

E-graphs / equality saturation (recorded as a possible future *backend* for HML and generic
AST alike, not an architecture change) · `simp` · ring normaliser · measure-theoretic
probability · Bayes · expectation/variance · distributions · integration · MVT/FTC ·
transcendental derivatives · chain rule · interval-domain calculus · locally-nameless
refactor · Lean dependency · CAS-guided search · Gold-100 · training.

The libraries stay **inside `hamiltonian-lang`** for now. Three capabilities do not justify a
third repository; the theorem API is the seam to split along if Gold-100 shows the domains
growing independently.

## 11. Repository state

Filled in at commit time — see the commit body and `docs/PROJECT_STATUS.md` for the exact
FINAL_SHA, pytest count, remote SHA and clean-worktree confirmation.

**Next step is yours.** Repin, rerun the same frozen 23 transitions, and judge
`23/23 HANDLED · CoreGapRate 0 · AdapterGapRate 0 · LibraryBlockedRate 0 · RegressionRate 0`
independently. Only you may recommend Gold-100.
