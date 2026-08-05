# Phase 1 — Lead audit of the actual implementation

HML-VALUE-OF-INFORMATION-001 Phase 1 requires the Lead to audit the implementation directly
rather than trust any summary of it, including this project's own documents. Every claim
below was produced by running code on 2026-08-05 at commit `967e95d`. Where a finding
contradicts an existing document, the finding wins and the contradiction is named.

This is the Lead's independent verification. It cross-checks, and does not replace, the
Adversarial agent's `V1_FREEZE_MANIFEST.md`.

---

## 1. Where `synthesise` is used

Defined at `src/hamiltonian_lang/type_system/__init__.py:236`.

**Called at exactly one site in `src/`** — line 254, *inside* `check` itself:

```python
actual = self.synthesise(e)
```

`synthesise` is not an independently used entry point. It is the synthesis half of a
two-function pair whose only consumer is `check`. Line 238 shows it delegates to
`expr_type`, so `synthesise` is a thin named alias over the pre-existing synthesis path
rather than a separate algorithm.

## 2. Where contextual `check` is used

**Exactly two call sites**, against **19** `self.expr_type(...)` synthesis-only sites.

| site | statement | diagnostic |
|---|---|---|
| line 384 | `Declaration` carrying a value | `HML-T402` |
| line 635 | distribution argument role | `HML-T413` |

**Statement positions that carry an expression but are NOT checked bidirectionally:**

| line | position | path used |
|---|---|---|
| 396 | `DefineStmt` body | `expr_type` then `is_subtype` → `HML-T403` |
| 416 | `AssumeStmt` / `RequireStmt` / `ProveStmt` proposition | `expr_type` |
| 436 | `ObjectiveStmt` expression | `expr_type` |
| 754 | `CheckStmt` subject | `expr_type` |
| 801 | `ConceptDecl` transform body | `expr_type` |
| 809 | `ConceptDecl` member body | `expr_type` |

Two of roughly nine expression-bearing statement positions route through checking mode.
The `DefineStmt` case is the most consequential: a wrong `def` body produces a
synthesised-versus-declared subtype complaint rather than a role-named, repair-actionable
message, and the repair loop in Phase 6 depends on exactly that quality of diagnostic.

**Classification: `SUPPORTED_PARTIAL`** — as the directive mandates, now with the specific
sites enumerated.

### 2a. Three defects confirmed at the two-site boundary

Raised by the Phase F1 agent and **independently reproduced here** before being recorded.
All three live in `type_system/__init__.py`, which is Lead-owned; none is fixed in this
milestone.

**Defect A — a user `def` call checks neither arity nor argument type.**

```
def f(a : Real, b : Real) : Real := a + b
def g : Real := f(1.0)                 -> ok
def g : Real := f(1.0, 2.0, 3.0, 4.0)  -> ok
```

Only the seven `_BUILTIN_SIGNATURES` are checked. A call with the wrong number of arguments
compiles clean.

*Consequence for Phase 6.* The content hash still separates these — a wrong-arity call
canonicalises differently — so **semantic preservation remains correctly scored**. What is
lost is the diagnostic: the repair loop gets no message to act on, so an arity error is
unrepairable by construction and will appear as a first-attempt parse *success* followed by
a semantic failure. Report the two facets separately, which the scorer already does.

**Defect B — the two checking sites disagree about the same literal.**

```
const p : Probability = 0.5   -> ok
def   p : Probability := 0.5  -> error HML-T403
```

`Declaration` routes through `TypeChecker.check`, which applies literal refinement (D-009).
`DefineStmt` uses bare `is_subtype` and rejects. Identical mathematics, opposite verdicts,
decided entirely by which keyword was used. For a syntax tournament this is worse than a
plain bug: a candidate surface that happens to prefer `def` is penalised for a reason that
has nothing to do with the surface.

**Defect C — the module docstring overstates coverage.** Line 234 describes a bidirectional
checker; §2 above shows two of roughly a dozen positions participate.

## 3. Binder representation

```python
class SymbolId:
    name: str
    ordinal: int      # assigned by the resolver in declaration order within a scope
    depth: int = 0    # binder nesting depth, 0 at module level
```

`canonical()` emits `sym:#{depth}.{ordinal}` — **the name is excluded**. `display()` keeps
it.

The AST is **not** locally nameless: nodes retain `name`. It is the *canonical form* that
is locally nameless, via `(depth, ordinal)`. This is the D-005 hybrid. The docstring's
phrase "locally-nameless canonical form" is accurate but easy to misread as a claim about
the AST representation; no de Bruijn index appears in the AST.

Consequence, and it is the property the content hash relies on: alpha-renaming changes
`name` but never `(depth, ordinal)`.

## 4. Dimension semantics

```python
class Dimension:
    exponents: tuple[tuple[str, Fraction], ...] = ()
    variables: tuple[tuple[str, Fraction], ...] = ()
```

- **Rational exponents** via `Fraction` — half-integer powers are representable.
- **Dimension variables** are single capital letters, excluding base dimension names.
- Zero exponents are elided, so structural equality *is* dimensional equality.
- A dimension containing any variable is **not concrete**: it may be unified, cannot be
  compared for equality against a concrete dimension, and is never silently treated as
  dimensionless.

**Known limitation, unchanged:** `unify()` handles the single-variable case only.

## 5. Concept minting — trust status

**`KNOWN_FAILED`, confirmed by direct experiment, not by reading `audits/V1_RED_TEAM.md`.**

A registry was seeded with one admitted concept and disguised copies were offered, each
supplied with a valid example and compression evidence so that duplication would be the
only possible blocker:

| disguise | folded definition | equality match | verdict |
|---|---|---|---|
| identical | `sqrt(variance(estimator) / n)` | yes | `duplicate` |
| **space after `(`, none around `/`** | `sqrt( variance(estimator)/n )` | **no** | **`admitted`** — zero blocking findings |
| newline + indent | collapses to the original | yes | `duplicate` |

**The name is not the vector — the definition text is.** Offering four differently *named*
copies with a byte-identical definition produced `duplicate` four times out of four.
Offering four names with the definition merely *respelled* produced **two admissions**:

| candidate | definition | verdict |
|---|---|---|
| `re_a` | `sqrt( variance(estimator)/n )` | **admitted** |
| `re_b` | `sqrt(variance(estimator)/ n)` | rejected |
| `re_c` | `sqrt(variance( estimator ) / n)` | **admitted** |
| `re_d` | `sqrt(variance(estimator)  /n)` | rejected |

This corrects a plausible misreading: the registry's rename handling works. What fails is
definition comparison. **The remedy is to parse and canonicalise definitions before
comparing them, not to harden the rename check** — a fix aimed at names would leave the
hole exactly where it is.

**Root cause.** Definition matching is textual:

```python
def _fold(text: str) -> str:
    return normalise_whitespace(text).casefold()
```

`normalise_whitespace` collapses *runs* of whitespace, so a newline-and-indent variant
folds back onto the original and is caught. It does not normalise whitespace **adjacent to
punctuation**, so `sqrt( variance(estimator)/n )` and `sqrt(variance(estimator) / n)` fold
to different strings and the candidate is admitted as a novel concept. The disguise is one
keystroke deep. Detection is lexical where it would need to be structural — parsing both
definitions and comparing canonical forms.

**A second, separate defect.** `AdmissionReport.duplicate_of` is populated only on an
equality match. A candidate can carry `verdict == Lifecycle.DUPLICATE` with
`duplicate_of is None`, because `COMPRESSES_NOTHING` also implies `Lifecycle.DUPLICATE`
(`minting.py:1313`, `:1341`). A consumer reading `duplicate_of` to find *what* was
duplicated gets `None` and may conclude nothing was. Verdict and provenance disagree.

**Correction to this project's own records.** `GOAL.md` §3 and
`spec/v1/semantic_objects.yaml` describe the failure as "a registry seeded with one concept
accepted three further copies of it". The specific disguises recorded there — pure rename,
vacuous constraint, alias — are **now caught**. The kill criterion is still failed, but by
a different and narrower route. The status is unchanged; the reason has changed.

### 5a. The p-value conflation is closed in Python and open in the language

`spec/v1/semantic_objects.yaml` `kill_criteria.L4` states the conflation is "Now closed".
**That is wrong as written**, and it was reproduced here:

```
param p_value : Probability
def posterior_h0 : Probability := p_value   -> ok
param q : PValue                            -> error HML-T440: unknown type 'PValue'
```

`PValue` and `PosteriorProbability` are distinct types in `v1/epistemic.py` — a Python API.
They are **not HML types**, so no HML program can express the distinction and the checker
cannot enforce it. The kill criterion is met by the library and unmet by the language.

This is the same structural fact the F1 agent found across the board: nothing on the
`hml check` path imports `hamiltonian_lang.v1`. Every V1 layer is a standalone Python API,
unreachable from HML source. **Classification of PValue: `KNOWN_FAILED`.**

## 6. Lean

`lean` 4.32.2 is on PATH (`arm64-apple-darwin24.6.0`).

| probe | verdict |
|---|---|
| `theorem t_true : 1 + 1 = 2 := by rfl` | `verified`, axioms `[]` |
| `theorem t_false : (1:Nat) = 2 := by sorry` | `rejected_forbidden_tactic` |
| `theorem t_real : forall x : Real, x = x := ...` | `rejected_compile_error` |

`~/.elan/toolchains` contains only `leanprover--lean4---v4.32.2`; **no Mathlib directory
exists on the filesystem.** `Real` therefore does not resolve, and with
`autoImplicit false` in the preamble it cannot be silently auto-bound either — the third
probe fails to compile, which is the correct behaviour and confirms trap 2 is closed.

**Classification: Mathlib-dependent lowering is `UNSUPPORTED`.** Only theorems expressible
in core Lean 4 can reach `verified`, which excludes essentially every statement about
real numbers, probability or measure — that is most of what HML emits.

**Two further facts, reproduced here after the F1 agent raised them.**

*The backend closes every obligation with `sorry`, by design.* Its own generated header
says so: "Every obligation is closed with `sorry`: this backend performs no proof search
(design freeze §8)." Since `sorry` is in `FORBIDDEN_TACTICS`, `lean_verify.verify()`
rejects the backend's output **textually, before Lean is invoked**. The verifier is sound
and has nothing to verify — a working gate with nothing able to pass through it. Any future
report must not describe Lean as an available verification path for HML output.

*The Mathlib dependency is partly self-inflicted.* Core Lean handles naturals perfectly
well —

```
theorem t : (7:Nat) = 7 := by rfl     -> compiles
theorem t : (7:ℕ) = 7 := by rfl       -> error: Unknown identifier `ℕ`
```

— but the backend emits the Mathlib notation `ℕ`. So a `Natural`-only module fails for a
*notational* reason, not a mathematical one. A Mathlib-free subset over `Nat`, `Bool` and
core propositional structure looks reachable by changing emission alone. That is a genuine
opportunity, and it is **out of scope here**: it is a backend change, and this milestone
freezes rather than extends. Recorded so the option is not lost.

## 7. Stan

`stanc` is **not on PATH**. Stan emission is therefore **unverified**: the backend produces
text that has never been compiled. Independently of tooling, the previously measured
expressive limits stand — Stan cannot state strict positivity, so most distribution
families cannot round-trip, and observed values and declaration order are lost.

**Classification: `SUPPORTED_PARTIAL`, compilation unverified.**

## 8. SymPy

SymPy 1.14.0 is installed. Every non-illustrative example was rendered with
`hml render -t sympy --no-report` and executed as a Python module:

```
EXECUTES 15/15
```

Emitted modules run without error. The directive's condition — supported only when emitted
modules execute successfully — **is met**.

Caveat: execution is not correctness. These runs prove the emitted module imports, builds
its symbols and evaluates; they do not prove the SymPy expression means what the HML meant.
The known drop-propagation behaviour (a `Ref` to a dropped name yields `None` rather than
an unbound name) is a containment measure, not a fidelity guarantee.

---

## Summary against the Phase 2 vocabulary

| feature | classification | basis |
|---|---|---|
| declarations and types | `SUPPORTED_ENFORCED` | checked bidirectionally, `HML-T402` |
| probability roles | `SUPPORTED_ENFORCED` | checked bidirectionally, `HML-T413` |
| binders and quantifiers | `SUPPORTED_ENFORCED` | canonical form excludes names; hash is alpha-invariant |
| dimensions | `SUPPORTED_ENFORCED` for concrete; `SUPPORTED_PARTIAL` for variables | unification is single-variable only |
| bidirectional checking overall | `SUPPORTED_PARTIAL` | 2 of ~9 expression positions |
| concept automatic admission | **`KNOWN_FAILED`** | whitespace disguise admitted, reproduced above |
| SymPy | `SUPPORTED_ENFORCED` (execution) | 15/15 execute |
| Stan | `SUPPORTED_PARTIAL`, unverified | no `stanc` |
| Lean, core | `SUPPORTED_PARTIAL` | verifies, rejects `sorry` |
| Lean, Mathlib-dependent | **`UNSUPPORTED`** | Mathlib absent; `Real` does not resolve |

**Consequence for the syntax gate.** Only `SUPPORTED_ENFORCED` features may enter it, so
the shared-core corpus must avoid concept minting entirely, avoid dimension variables, and
must not depend on Lean or Stan for its oracle. The deterministic oracle for the gate is
the content hash, and SymPy execution where a numeric check is wanted.
