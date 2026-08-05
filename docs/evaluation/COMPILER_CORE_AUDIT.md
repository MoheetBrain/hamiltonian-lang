# Compiler Core Audit — HML-COMPILER-CORE-003 Phase 0

**Measurement before modification.** Every classification below is backed by a command that
was run against the current tree, not by reading the source and forming an impression.
Where a proposal turned out to be already satisfied, that is recorded as a reason **not** to
rewrite.

Batteries: 22 hand-built malformed inputs · 400 random-byte fuzz · 400 token-soup fuzz ·
8 precedence probes · 4 semantic-hole probes · 5 dimensional probes · 4 canonical-identity
probes.

---

## Summary — what the measurements license

| verdict | count | items |
|---------|-------|-------|
| **already implemented** — do not touch | 7 | precedence, associativity, canonical identity (all 4 rules), fuzz robustness, malformed recovery, symbol IDs, alpha-normalisation |
| **measured defect — fix now** | 5 | recursion crash, unknown-type hole, truncated-type hole, rational dimension exponents, dimension variables |
| **useful now** | 1 | bidirectional checking (absent; confirmed by source inspection) |
| **deferred with a written gate** | 3 | Pratt parser, red-green tree, e-graph |
| **out of scope this milestone** | 4 | probability monads, dependent typing, Julia/LLVM, incremental IDE |

---

## 1. Front end

### 1.1 Lexer — **already implemented**, one prior defect fixed

800 fuzz inputs (400 random-byte, 400 token-soup): **0 hangs, 0 crashes.** The
non-termination defect D-019 (`ℝ` consuming zero characters and looping forever) is fixed
and regression-tested.

### 1.2 Parser strategy — recursive descent, LL(1) at statement level. **No change needed.**

22 malformed inputs, of which **21 produced diagnostics or a clean parse and 1 crashed**.
Recovery synchronises at line boundaries; a bad line does not cascade.

### 1.3 Precedence and associativity — **ALREADY CORRECT. Measured.**

| probe | result | correct? |
|-------|--------|----------|
| `1 + 2 * 3` | `1 + 2 * 3` (mult binds tighter) | yes |
| `2 ^ 3 ^ 2` | right-associative | yes |
| `-2 ^ 2` | unary minus below power | yes |
| `10 - 3 - 2` | left-associative | yes |
| `12 / 3 / 2` | left-associative | yes |

> **Pratt-parser decision: DO NOT ADOPT.** The directive permits a Pratt/precedence-climbing
> expression parser *only if tests demonstrate failures involving precedence, associativity,
> prefix/postfix operators, implicit multiplication, function application or chained
> transformations*. **No precedence or associativity failure was found.** Replacing a
> measurably correct subsystem would be churn. Recorded as **D-022**.

### 1.4 Implicit multiplication — **absent by design, and it is a syntax-acquisition question, not a correctness bug**

`2 x`, `2 (x + 1)` and `x y` are all rejected with `HML-P204`.

This is defensible — `x y` is genuinely ambiguous between multiplication and application —
but models emit `2x` habitually. Classified **useful now for the acquisition gate only**,
and to be decided by the syntax study rather than by preference. It is a candidate *surface*
difference between the four syntaxes, not a semantic change.

### 1.5 Incomplete input — **MEASURED DEFECT**

```
def f := ((((( … 400 deep … 1
    -> RecursionError: maximum recursion depth exceeded
```

Recursive descent recurses per nesting level. **A crash on adversarial input violates the
Phase 1 requirement that the parser never crash on arbitrary model output.** A truncated or
degenerate generation can reach this. Fix: an explicit nesting-depth bound producing a
diagnostic, not a Python exception.

### 1.6 CST / spans / trivia — **partially implemented, sufficient**

No CST; typed AST only. Every node and token carries a `Span` with line, column and end
position. Sufficient for diagnostics and for the exact supported round trip (HML → HML
preserves the content hash).

> **Red-green tree: DEFERRED.** No incremental IDE, collaborative editor or large-document
> reparsing requirement exists. Written up in `docs/design/DEFERRED_INCREMENTAL_SYNTAX.md`.

---

## 2. Binding — **already implemented**

`SymbolId(name, ordinal, depth)`; canonicalisation projects to `sym:#depth.ordinal`
(D-005, D-010). Shadowing is an error (D-006). Supported binders: `forall`, `exists`,
function parameters, concept parameters, indices, local definitions.

Alpha-equivalence is property-tested across **every** binder form, with a companion test
asserting each template actually compiles — added after D-018, where a green property suite
was found to be asserting a false criterion because its generator never produced `def`
parameters.

> **Locally nameless representation: DO NOT ADOPT.** The directive permits it "only if it
> reduces actual complexity or fixes a demonstrated binding defect". **No binding defect was
> found.** The hybrid scheme already gives renaming invariance with readable diagnostics.

---

## 3. Type checking — **synthesis only. Bidirectional checking is genuinely absent.**

Confirmed by source inspection: `expr_type()` exists; there is no
`check(context, expr, expected)`.

Consequence, and it is the **most consequential finding in this audit**:

| probe | result |
|-------|--------|
| `param x : Frobnicator` | **ACCEPTS** |
| `param sigma : Positiv` (truncated `PositiveReal`) | **ACCEPTS** |
| `param v : Vector[Frobnicator, N]` | **ACCEPTS** |

An unknown capitalised name is silently treated as a *concept reference*. So a **truncated
or hallucinated type name passes the checker without a diagnostic** — precisely the failure
mode of AI-generated code, and it directly corrupts **semantic preservation**, which is a
gate metric.

Classified **useful now**. This single hole plausibly accounts for a material share of the
V0 pilot's 0.648 encoding fidelity, because a wrong type that is silently accepted scores as
a type mismatch against ground truth with no diagnostic to trigger repair.

---

## 4. Probabilistic roles — **already implemented**; effect labels **not present**

Role-labelled arguments are mandatory, with targeted diagnostics for known
misparameterisations (`HML-T415`, verified: `Normal(loc := m, sd := s)` is rejected). The
three prohibited conflations are enforced structurally.

`det` / `rnd` / `qry` effect labels do not exist. Classified **useful now**, narrowly: the
five rejections named in Phase 4 are the whole scope. **Probability monads: out of scope**,
gate written to `docs/design/DEFERRED_PROBABILITY_MONADS.md`.

---

## 5. Dimensions — **mostly implemented, two measured parser gaps**

| probe | result | verdict |
|-------|--------|---------|
| add incompatible dimensions | rejected `HML-D502` | correct |
| transcendental of a dimensional quantity | rejected `HML-T427` | correct |
| `Length / Length` cancels to scalar | accepted | correct |
| **`Quantity[Length^1/2]`** | **rejected `HML-P225`** | **DEFECT** |
| **`Quantity[D]` (dimension variable)** | **rejected `HML-D501`** | **DEFECT** |

`Dimension` stores `Fraction` exponents and `power()` accepts a `Fraction` — the **type
system supports rational exponents and the parser does not**. Splitting on `/` tears `^1/2`
into a numerator and a spurious division. This already forced a benchmark case
(`Mass^1/2 * Length`) to be deleted from the corpus.

Dimension variables are needed for Phase 5's "unification with unknown dimension variables".

---

## 6. Canonical identity — **ALREADY CORRECT on all four documented rules. Measured.**

| rule | expected | measured |
|------|----------|----------|
| local binder renaming | same hash | **same** |
| quantifier order | different | **different** |
| public role swap | different | **different** |
| AC reorder of `+` with no AC declared | different | **different** |

SHA-256 over alpha-normalised canonical JSON; sorted keys, ASCII, no spans. No XOR
combiner anywhere. The hash is documented as an identifier, not a proof of equivalence.

> **E-graph: DO NOT BUILD.** Adoption gate written to
> `docs/design/EGRAPH_ADOPTION_GATE.md`. None of its five conditions is currently met — in
> particular no syntax has passed the acquisition gate and no positive reasoning signal
> exists.

---

## 7. Backends — claims already matched to tooling, one measured defect

Established by measurement and carried forward, not re-litigated:

- **Lean 4.32.2 is installed; Mathlib is not.** `sorry` compiles and **exits 0** — exit
  status alone would certify a false theorem, so `#print axioms` is the real discriminator.
  Since the V0 Lean backend closes every obligation with `sorry` by design, **no V0-emitted
  theorem could ever count as verified.** Lean also auto-binds missing types unless
  `autoImplicit false` is set, which would otherwise "prove" something vacuous.
- **stanc / CmdStan absent.** Stan claims are structural only. Stan cannot express strict
  positivity, loses observed values, and destroys interleaved declaration order.
- **SymPy 1.14.0 present. MEASURED DEFECT:** generated SymPy raises `NameError` on import
  for a module containing a quantified `Proposition` — the definition is dropped but a
  reference to it survives. Found by *executing* the output rather than rendering it.

---

## 8. Agent allocation justified by measurement

| agent | scope, each item traceable to a measured defect above |
|-------|------------------------------------------------------|
| **A — Front-End Reliability** | §1.5 recursion crash; depth-bounded diagnostics; extend the fuzz battery into the permanent suite; implicit-multiplication decision **as a surface variant only**. **No Pratt rewrite** (§1.3), **no red-green tree** (§1.6) |
| **B — Binding and Type Semantics** | §3 unknown/truncated type hole (highest value); bidirectional `check`; §5 rational exponents and dimension variables; §4 minimal `det`/`rnd`/`qry`. **No locally nameless rewrite** (§2) |
| **C — Verification and Backend Contracts** | §7 SymPy `NameError`; `#print axioms` gating so nothing is called verified without kernel acceptance; support-matrix accuracy; adversarial review |

**Three agents, matching the concurrency limit.** Every task above is justified by a
measurement in this document. Nothing is being rewritten because it looked wrong.

## 9. What this audit refuses to do

Four proposals are **already satisfied** and rebuilding them would be churn with regression
risk: expression precedence, canonical identity, binder identity, and lexer robustness. The
directive's own conditions for Pratt parsing, a locally nameless representation, a red-green
tree and an e-graph are each **unmet by measurement**, and each is recorded as a deferred
decision with an explicit trigger rather than as an omission.
