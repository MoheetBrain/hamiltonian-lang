# V1 Freeze Manifest — what is actually safe to freeze

HML-PHASE-FG-001 Phase F1. Branch `hml-v1-concept-kernel`.
Author role: Adversarial Verification Agent. Probe date: 2026-08-05.

Machine-readable twin: `tests/freeze/frozen_subset.py`.
Mechanical enforcement: `tests/freeze/test_quarantine.py`.

This document decides what enters the frozen syntax gate. It is adversarial by charter:
a feature that *looks* supported and is not enforced is the failure this phase exists to
prevent. Every command below was executed on this machine and its real output is pasted.
Nothing is classified from reading the source.

---

## 0. The evidential bar

`SUPPORTED_ENFORCED` requires **all three**, shown, not asserted:

1. a valid example that checks clean;
2. an invalid example **rejected with a named `HML-*` diagnostic code**;
3. a **deterministic semantic oracle** — the canonical form / content hash, which must
   round-trip and must discriminate the meanings the feature exists to keep apart.

Failing (2) caps a feature at `SUPPORTED_PARTIAL`. Failing (3) excludes it from the
frozen subset outright, per the Phase F1 charter.

Vocabulary, closed: `SUPPORTED_ENFORCED` · `SUPPORTED_PARTIAL` · `EXPERIMENTAL` ·
`KNOWN_FAILED` · `DEFERRED` · `UNSUPPORTED`.

### What "the syntax gate" means here

The gate is what `hml check` accepts, defined by three closed sets in
`tests/freeze/frozen_subset.py`: `FROZEN_KEYWORDS` (47 tokens), `FROZEN_STATEMENT_KINDS`
(12 `Statement` subclasses) and `FROZEN_TYPE_NAMES` (11 scalars + 11 constructors). It is
an **allowlist**, not a denylist: a denylist fails open on a construct nobody listed.

---

## 1. The classification table

| feature | verdict | reachable from the gate? | oracle |
|---|---|---|---|
| declarations and types | `SUPPORTED_ENFORCED` | yes | canonical hash |
| probability roles | `SUPPORTED_ENFORCED` | yes | canonical hash |
| PValue | `SUPPORTED_ENFORCED` | yes, as a scalar type (D-022) | canonical hash |
| binders and quantifiers | `SUPPORTED_ENFORCED` | yes | canonical hash, alpha-invariant and order-sensitive |
| dimensions | `SUPPORTED_ENFORCED` | yes | canonical hash |
| transformations | `EXPERIMENTAL` | no | none |
| epistemic statuses | `EXPERIMENTAL` | no | none |
| discourse obligations | `EXPERIMENTAL` | no | none |
| concept references | `SUPPORTED_ENFORCED` | yes | canonical hash |
| concept minting and admission | `KNOWN_FAILED` | no | none |
| semantic morphology | `EXPERIMENTAL` | no | none |
| Lean | `UNSUPPORTED` | render only | none — no emitted file has ever elaborated |
| Stan | `SUPPORTED_PARTIAL` | render only | canonical hash, on a narrow subset |
| SymPy | `SUPPORTED_PARTIAL` | render only | execution only, which is a syntax check |

**Frozen subset = the six `SUPPORTED_ENFORCED` rows.** Everything else is quarantined
and is mechanically held outside the gate by `tests/freeze/test_quarantine.py`.

> **Amendment, 2026-08-05 (Subagent A, HML-CONSTITUTIONAL-CORE-001).** The `PValue` row
> moved from `KNOWN_FAILED` to `SUPPORTED_ENFORCED`. §4 below is rewritten with the new
> evidence. What moved is **two scalar types**, not the L4 layer: no
> `hamiltonian_lang.v1` module became reachable, no keyword was added, no statement kind
> was added, and no epistemic status, justification or claim object entered the gate.
> The residual hole §4 records is pinned by
> `test_pin_a_mis_declared_p_value_is_still_admitted`.

### How the quarantine is enforced

`tests/freeze/frozen_subset.py` holds the allowlist **and** a copy of this table as
`MANIFEST_CLASSIFICATION`. `tests/freeze/test_quarantine.py` parses the table above out of
this file and asserts the two agree, so the document and the code cannot drift. It then
asserts three independent barriers:

1. **Closed sets.** `lexer.KEYWORDS` must equal `FROZEN_KEYWORDS`; the `Statement`
   subclasses must equal `FROZEN_STATEMENT_KINDS`; `types.SCALARS` must equal
   `FROZEN_SCALARS`. Adding `goal` to the lexer, or a scalar to the lattice, fails here —
   before any behavioural test would notice. **This barrier has fired once, as designed:**
   D-022 added `PValue` and `PosteriorProbability` to `types.SCALARS`, the assertion
   failed, and the promotion could not land until this document and `frozen_subset.py`
   were amended together with new evidence (§4).
2. **The import barrier.** Every `.py` under `src/hamiltonian_lang/` outside `v1/` is
   parsed with `ast` and must contain no import of `hamiltonian_lang.v1`. A runtime check
   compiles, canonicalises and hashes the concept example in a fresh interpreter and
   asserts that `sys.modules` contains no `hamiltonian_lang.v1.*`.
3. **Behavioural probes.** All 17 quarantined surface forms and all 10 quarantined type
   names are compiled and must be rejected with a code.

Plus **known-failure pins** (§4, §11) that assert an open hole is *still* open. If one is
fixed, the suite fails and this manifest must be re-evidenced in the same change. A freeze
manifest that keeps saying `KNOWN_FAILED` after the failure is fixed is as wrong as one
that says `SUPPORTED_ENFORCED` before it is.

The §4 pin has now done exactly that. It asserted that the p-value-as-posterior
conflation type-checked; D-022 closed it, the pin failed, and the row moved with new
evidence. What stands in its place is narrower and still a pin: a *mis-declared* p-value
is admitted, and no type system detects that.

```
$ .venv/bin/python -m pytest tests/freeze/test_quarantine.py
52 passed in 0.19s      # 2026-08-05, before the §4 amendment
51 passed in 0.18s      # 2026-08-05, after it (two quarantined type names promoted,
                        #   one pin split into an assertion plus a narrower pin,
                        #   one lattice-shape assertion added)
```

### The single structural fact behind most of this table

```
$ grep -rn "from ..v1\|from .v1\|import v1\|hamiltonian_lang.v1" \
    src/hamiltonian_lang --include="*.py" | grep -v "^src/hamiltonian_lang/v1/"
(no output)
```

**No module on the `hml check` path imports `hamiltonian_lang.v1`.** The six V1 layers —
registry, minting, morphology, transformation, epistemic, discourse — are a standalone
Python API. They are not reachable from any HML source program, and no HML source
program can invoke, consult or be judged by them. Every V1 row below is quarantined for
this reason before any of its own merits are considered.

---

## 2. declarations and types — `SUPPORTED_ENFORCED`

Covers `module`, `var|param|const|obs|index|rv`, `def`, and every name in
`FROZEN_TYPE_NAMES`.

**(1) valid**

```
$ .venv/bin/hml check examples/statistics/bayesian_coin.hml
ok: BayesianCoin (7 statements, 3 symbols, 1 proof obligation(s))
```

**(2) rejected, with codes**

```
$ printf 'module M\nparam sigma : Positiv\n'          | .venv/bin/hml check -
error HML-T440: unknown type 'Positiv'
  help: did you mean 'PositiveReal'?

$ printf 'module M\nparam theta\n'                     | .venv/bin/hml check -
error HML-T401: 'theta' has no type

$ printf 'module M\nconst a : Natural = -3\n'          | .venv/bin/hml check -
error HML-T402: the declared type of 'a' requires Natural

$ printf 'module M\ndef f := undefined_name + 1\n'     | .venv/bin/hml check -
error HML-N301: 'undefined_name' is not bound
```

**(3) oracle**

```
$ .venv/bin/hml hash examples/statistics/bayesian_coin.hml
f79c553cca1adaa1...
$ .venv/bin/hml render examples/statistics/bayesian_coin.hml -t hml --no-report > /tmp/rt.hml
$ .venv/bin/hml hash /tmp/rt.hml
f79c553cca1adaa1...    # ROUND-TRIP STABLE
```

Measured over every canonical `.hml` example (the 8 outside `candidate_syntaxes/`):
**8/8 round-trip stable.**

### Two defects found inside this row — FIXED 2026-08-05

Both were in `src/hamiltonian_lang/type_system/__init__.py`. They did **not** move the
verdict — the enforced core held — but they narrowed what the row could be said to
enforce. Both were reproduced independently by the Lead
(`docs/evaluation/PHASE1_LEAD_AUDIT.md` §2a, defects A and B) and are now closed. The
reproductions below are kept as the *historical* record; the current behaviour is stated
after each.

**2a. User-defined function calls are not checked at all.** Neither arity nor argument
type.

```
$ printf 'module M\nparam x : Real\ndef f(a : Real, b : Real) : Real := a + b\ndef g : Real := f(x)\ndef h : Real := f(x, x, x, x)\n' | .venv/bin/hml check -
ok: M (5 statements, 6 symbols, 0 proof obligation(s))

$ printf 'module M\nparam p : Proposition\ndef f(a : Real) : Real := a + 1\ndef g : Real := f(p)\n' | .venv/bin/hml check -
ok: M (4 statements, 4 symbols, 0 proof obligation(s))
```

`_call_type` (line 1059) checks only the seven `_BUILTIN_SIGNATURES` entries; a symbol
resolved to a user `def` returns `sym.declared_type.codomain` with the arguments
unexamined. The module docstring at line 234 says checking is used for "function
arguments". It is not. Contrast the builtin path, which works:

```
$ printf 'module M\nparam x : Real\ndef g : Real := log(x)\n' | .venv/bin/hml check -
error HML-T427: the argument of log has the wrong type
```

*Now.* Every user-supplied callable carries a `CallableSignature` — ordered parameter
names, ordered parameter types, declared return type, defining `SymbolId` — collected
before checking begins, because module scope is order-independent and a call may
textually precede its definition. Arity is exact and every argument is checked
contextually:

```
$ printf 'module M\ndef f(x : Real, y : PositiveReal) : Real := x + y\ndef a : Real := f(1.0)\n' | .venv/bin/hml check -
error HML-T471: f takes 2 argument(s), 1 given
  expected: f(x : Real, y : PositiveReal) : Real
  help: supply 1 more argument(s); the parameters are (x : Real, y : PositiveReal)

$ printf 'module M\ndef f(x : Real, y : PositiveReal) : Real := x + y\ndef c : Real := f(1.0, -2.0)\n' | .venv/bin/hml check -
error HML-T472: the parameter 'y' (argument 2) of f requires PositiveReal
  help: supply a value in PositiveReal; -2.0 is not one
```

`HML-T470` covers the third case the old path silently accepted: applying a definition
that binds a value rather than a function.

**2b. Two checking sites disagree about the same literal.** `Declaration` routes through
`TypeChecker.check`, which applies the D-009 literal refinement; `DefineStmt` uses a bare
`is_subtype`. The same value and the same declared type therefore get opposite answers:

```
$ printf 'module M\nconst p : Probability = 0.5\n' | .venv/bin/hml check -
ok: M (2 statements, 1 symbols, 1 proof obligation(s))

$ printf 'module M\ndef p : Probability := 0.5\n'  | .venv/bin/hml check -
error HML-T403: the body of 'p' does not inhabit its declared type
  found:    PositiveReal
  expected: Probability
```

*Now.* `DefineStmt` routes through `check`, so both forms accept. `HML-T403` is retained
as the code, and its headline wording is preserved, so nothing downstream that keys on
either has to change.

```
$ printf 'module M\ndef p : Probability := 0.5\n' | .venv/bin/hml check -
ok: M (2 statements, 1 symbols, 0 proof obligation(s))
```

### Bidirectional-checking sites, enumerated

Charter item. Re-measured 2026-08-05 after the fixes above. **Five** of twelve positions
route through `check`; the count was two. The table is asserted mechanically by
`tests/type_system/test_contextual_positions.py`, so it cannot drift from the code.

| site | routes through `check`? | code |
|---|---|---|
| `Declaration.value` against its declared type | **yes** | `HML-T402` |
| `DefineStmt.body` against its declared type | **yes** (was bare `is_subtype`) | `HML-T403` |
| **user-`def` / transform `Call` arguments** | **yes** (was no check of any kind) | `HML-T472` |
| distribution role against its role signature | **yes** | `HML-T413` |
| concept member body against its declared type | **yes** (was synthesised and discarded) | `HML-T473` |
| builtin `Call` arguments | no — inline `is_subtype` loop | `HML-T427` |
| `Assume`/`Require`/`Prove` proposition | no — kind test | `HML-T404` |
| `ObjectiveStmt.expression` | no — `dimension_of` test | `HML-T405` |
| `CheckStmt.subject` | no — kind test | `HML-T404` / `HML-D503` |
| concept `transform` body (declares no type) | no expectation exists | — |
| `Index` base and indices | no — kind test | `HML-T423` |
| `BinOp` / `Comparison` operands | no — synthesis then relation test | `HML-D502` etc. |

**The checker is still not fully bidirectional and must not be described as such.** The
seven remaining positions impose a *predicate* — is it a proposition, does it have a
dimension, is it indexable — rather than a single expected type, so there is no
expectation for checking mode to carry. Converting them needs a disjunctive expectation
the checker does not have. That is future work, not a present capability.

---

## 3. probability roles — `SUPPORTED_ENFORCED`

The load-bearing D-003 decision. This is the strongest row in the manifest.

**(1) valid** — `examples/statistics/bayesian_coin.hml`, above.

**(2) rejected, five distinct codes**

```
$ printf 'module M\nparam mu : Real\nparam s : PositiveReal\nrv y : RandomVariable[Real]\nlaw y ~ Normal(location := mu, variance := s)\n' | .venv/bin/hml check -
error HML-T415: Normal has no role 'variance'
error HML-T414: Normal is missing required role(s): scale

$ printf 'module M\nparam mu : Real\nparam sigma : PositiveReal\nrv y : RandomVariable[Real]\nlaw y ~ Normal(mu, sigma)\n' | .venv/bin/hml check -
error HML-P234: positional arguments are not permitted for distribution 'Normal'

$ printf 'module M\nparam mu : Real\nparam sigma : PositiveReal\nrv y : RandomVariable[Real]\nlaw y ~ Normal(location := mu, spread := sigma)\n' | .venv/bin/hml check -
error HML-T416: Normal has no role 'spread'

$ printf 'module M\nrv u : RandomVariable[Real]\nlaw u ~ Uniform(lower := 5, upper := 1)\n' | .venv/bin/hml check -
error HML-T417: Uniform requires lower < upper

$ printf 'module M\nparam theta : Probability\ndef bad : Probability := Beta(alpha := 1, beta := 1)\n' | .venv/bin/hml check -
error HML-T403: the body of 'bad' does not inhabit its declared type
```

The last one is the `Distribution[T]` / `T` separation holding: a distribution expression
cannot inhabit its own support type.

**(3) oracle** — role order does not affect the canonical form; role *identity* does.
Covered by `tests/roundtrip/test_importers.py::test_stan_roundtrip_preserves_role_to_position_to_role`.

---

## 4. PValue — `SUPPORTED_ENFORCED`

**Reclassified 2026-08-05 from `KNOWN_FAILED`.** The prior verdict was correct when it
was written: `PValue` existed only in `src/hamiltonian_lang/v1/epistemic.py`, a Python
API, so `param q : PValue` was `HML-T440: unknown type` and no HML program could state
the distinction. D-022 adds `PValue` and `PosteriorProbability` to the scalar lattice as
**pairwise incomparable** refinements of `NonNegativeReal` — the same shape as
`Probability` vs `PositiveReal`, and with no subtyping path in either direction between
any pair.

**(1) valid**

```
$ printf 'module M\nconst pv : PValue := 0.05\n' | .venv/bin/hml check -
ok: M (2 statements, 1 symbols, 1 proof obligation(s))
```

**(2) rejected, with codes** — executed 2026-08-05, output pasted verbatim

```
$ printf 'module M\nconst pv : PValue := 0.05\ndef posterior_h0 : Probability := pv\n' | .venv/bin/hml check -
error HML-T403: the body of 'posterior_h0' does not inhabit its declared type
  found:    PValue
  expected: Probability
  note: a p-value is a property of a test procedure, not a probability within the model
  help: there is no conversion from PValue to Probability; supply a quantity that
        already is a Probability, or correct the declared type of the target

$ printf 'module M\nconst p : Probability = 0.5\ndef observed_pvalue : PValue := p\n' | .venv/bin/hml check -
error HML-T403: the body of 'observed_pvalue' does not inhabit its declared type
  found:    Probability
  expected: PValue

$ printf 'module M\nconst pv : PValue := 0.05\ndef post : PosteriorProbability := pv\n' | .venv/bin/hml check -
error HML-T403: the body of 'post' does not inhabit its declared type
  note: a p-value is P(data at least this extreme | H0); a posterior is P(H0 | data).
        Reading a p-value as a posterior is the prosecutor's fallacy

$ printf 'module M\nconst pv : PValue := 1.5\n' | .venv/bin/hml check -
error HML-T402: the declared type of 'pv' requires PValue
  help: supply a value in PValue; 1.5 is not one
```

The refusal is symmetric — neither direction is a widening — and it survives arithmetic
laundering, because the join of two incomparable unit-interval kinds is
`NonNegativeReal`, which is not a subtype of any of them:

```
$ printf 'module M\nconst pv : PValue := 0.05\ndef q : Probability := pv * 1.0\n' | .venv/bin/hml check -
error HML-T403: the body of 'q' does not inhabit its declared type
  found:    NonNegativeReal
  expected: Probability
```

**(3) oracle** — the canonical form carries the declared type, so the content hash
separates the three kinds of the same numeric value:

```
const pv : PValue               := 0.05   0fb9317ccbb37354…
const pv : Probability           = 0.05   73b255c24bc705ca…
const pv : PosteriorProbability := 0.05   2d15ea3cfe910910…
```

### What this row does NOT claim

**A mis-declared p-value is still admitted, and no type system can change that.**

```
$ printf 'module M\nparam p_value : Probability\ndef posterior_h0 : Probability := p_value\n' | .venv/bin/hml check -
ok: M (3 statements, 2 symbols, 2 proof obligation(s))
```

Both sides genuinely are `Probability`; the author chose the wrong type, which is a
modelling error and not a type error. The language's contribution is that the right type
now exists to be chosen and that choosing it is enforced. Inferring epistemic kind from a
symbol's *spelling* would be a name heuristic, and this project does not decide semantics
by spelling. Pinned by
`test_quarantine.py::test_pin_a_mis_declared_p_value_is_still_admitted`.

**No coercion in either direction is not the same as no laundering path at all.** A
`PValue` widens to `NonNegativeReal` and to `Real`, exactly as `Probability` does, and
nothing brings it back down — the descent is what is blocked. A program that deliberately
widens to `Real` and re-declares has discarded the kind in the source, visibly.

**The L4 *layer* is still `EXPERIMENTAL` (§8).** What moved into the gate is two scalar
types. `EpistemicStatus`, `Justification`, `EpistemicClaim` and the coercion table remain
Python-only and unreachable; `param e : Evidence` is still `HML-T440`.

---

## 5. binders and quantifiers — `SUPPORTED_ENFORCED`

**(1) valid**

```
$ .venv/bin/hml check examples/logic/quantifier_scope.hml
ok: QuantifierScope (3 statements, 4 symbols, 2 proof obligation(s))
```

**(2) rejected**

```
$ printf 'module M\nrequire forall x : Real . forall x : Real . x > 0\n' | .venv/bin/hml check -
error HML-N302: 'x' shadows an outer binding and would silently change scope

$ printf 'module M\nrequire forall x : Real . x > 0\nrequire x > 1\n' | .venv/bin/hml check -
error HML-N301: 'x' is not bound

$ printf 'module M\nparam m : Real\nrequire forall x : Real . m\n' | .venv/bin/hml check -
error HML-T422: the body of 'forall x' must be a proposition
```

**(3) oracle — the strongest in the manifest.** It is both alpha-invariant and
order-sensitive, which is exactly the pair of properties D-005 promises.

```
forall x . exists y . y > x                       ad46a359cbf154d3…
forall aardvark . exists zebra . zebra > aardvark ad46a359cbf154d3…   same
exists y . forall x . y > x                       43db883eeb3a79c2…   different
```

An alpha-renaming leaves the hash byte-identical; swapping the binder order changes it.

---

## 6. dimensions — `SUPPORTED_ENFORCED`

**(1) valid**

```
$ .venv/bin/hml check examples/physics/kinetic_energy.hml
ok: KineticEnergy (5 statements, 3 symbols, 1 proof obligation(s))
```

**(2) rejected**

```
$ printf 'module M\nparam m : Quantity[Mass]\nparam l : Quantity[Length]\ndef bad := m + l\n' | .venv/bin/hml check -
error HML-D502: cannot add quantities with different dimensions

$ printf 'module M\nparam m : Quantity[Mass]\nparam l : Quantity[Length]\nrequire m > l\n' | .venv/bin/hml check -
error HML-D502: cannot compare quantities with different dimensions

$ printf 'module M\nparam m : Quantity[Mass]\nparam v : Quantity[Length / Time]\ndef ke := 0.5 * m * v^2\ncheck dimension ke = Mass * Length^3 / Time^2\n' | .venv/bin/hml check -
error HML-D504: the computed dimension does not match the asserted dimension
```

**(3) oracle** — `kinetic_energy.hml` round-trips to a byte-identical hash
(`25efff792d32ccf0…`). Exponents are `Fraction`, so the check is exact, not floating.

**Scope limit, restated from the design freeze §8:** dimensions are checked; **units are
not reconciled**. `check dimension` proves nothing about a unit system.

---

## 7. transformations (L2) — `EXPERIMENTAL`

Fails (1), (2) and (3) *as a language feature*, and passes a weaker version of (2) as a
Python API.

**Not reachable from the gate.** Every surface form `docs/design/V1_KERNEL.md` §2
proposes is rejected by the parser:

```
$ printf 'module M\nstep s1 := divide(expr := e1, by := a)\n'      | .venv/bin/hml check -
error HML-P205: 'step' does not begin a statement
$ printf 'module M\nderive e3 from [e1, e2] via s1\n'              | .venv/bin/hml check -
error HML-P205: 'derive' does not begin a statement
```

**What does work, in Python.** The obligation table is real and the edge-kind barrier is
real:

```
>>> s = step("s1", source="e1", operation=Operation.DIVIDE, target="e2", arguments={"by": "a"})
>>> [o.render() for o in s.obligations()]
['[side_condition] s1 (divide): a != 0']
>>> s.require_kind(EdgeKind.LOGICAL_IMPLICATION)
EdgeKindError: step s1 is a algebraic_transformation edge but a logical_implication edge
  is required: yields is not implies …
```

`TransformationEdge.kind` is a derived property with no setter, so a caller cannot label
a rewrite an implication. That is a genuine, working prohibition.

**Why it is still `EXPERIMENTAL`.** The red-team's §5 circularity reproduces exactly:

```
>>> step("s2", source="e1", operation=Operation.SIMPLIFY, target="e2",
...      arguments={"identity": "unstated"}).obligations()
['[side_condition] s2 (simplify): the identity unstated holds on the domain of e1']
```

The same mathematics, labelled `simplify` instead of `divide`, generates no `!= 0`
obligation. The checker looks up the row it was told to read. L2 catches **unstated side
conditions on correctly labelled steps** and cannot catch a mislabelled step.

**No oracle.** `TransformationEdge` has `render()` and no canonical form; nothing in
`backends/canonical.py` serialises it; there is no content hash. Excluded from the frozen
subset on criterion (3) alone.

---

## 8. epistemic statuses (L4) — `EXPERIMENTAL`

L4 is the best-built layer in V1 and I could not break its core. It is still not a
language feature.

**Not reachable from the gate.** No status is a keyword, and no `Justification` is a type:

```
$ printf 'module M\nparam e : Evidence\n' | .venv/bin/hml check -
error HML-T440: unknown type 'Evidence'
$ printf 'module M\nparam x : Proof\n'    | .venv/bin/hml check -
error HML-T440: unknown type 'Proof'
```

**What works, in Python.**

```
>>> coercion_allowed(Justification.EVIDENCE, Justification.PROOF)
(False, 'absence of evidence against a hypothesis is not evidence for it; …')
>>> EpistemicClaim(EpistemicStatus.FAIL_TO_REJECT, "H0", {})
ContextError: fail_to_reject requires null, alpha, p_value; without it the claim is not a
  mathematical statement
```

Refusal is the default (`coercion_allowed` returns `False` for every pair it does not
recognise), and `REQUIRED_CONTEXT` fires in `__post_init__`.

**Two reasons it stays `EXPERIMENTAL`.**

- **Coherence is opt-in, and silently so.** A `fail_to_reject` reported at `p = 0.01`
  under `alpha = 0.05` constructs without complaint; the contradiction surfaces only if
  the caller separately invokes `check_test_coherence`:
  ```
  >>> c = EpistemicClaim(FAIL_TO_REJECT, "H0", {"null":"H0","alpha":"0.05","p_value":"0.01"})
  >>> c.status
  fail_to_reject                       # constructed
  >>> check_test_coherence("t", c).code
  'HML-E704'                           # only now
  ```
  The context rule is constructor-time, the obligation rule is pass-time, and the
  asymmetry is invisible at the call site.
- **No oracle.** `EpistemicClaim` has no canonical form and no hash.

`render_english` is the most demo-able thing V1 does and is not evidence of anything;
`V1_EXPERIMENT_PLAN.md` §8 already says so, and it bears repeating at every showing.

---

## 9. discourse obligations (L5) — `EXPERIMENTAL`

**Not reachable from the gate.** All six surfaces of `V1_KERNEL.md` §4 are rejected:

```
$ printf 'module M\ngoal g1 := 1 > 0\n'      | .venv/bin/hml check -
error HML-P205: 'goal' does not begin a statement
$ printf 'module M\ndischarge g1 by p1\n'    | .venv/bin/hml check -
error HML-P205: 'discharge' does not begin a statement
$ printf 'module M\ncase c1 := 1 > 0\n'      | .venv/bin/hml check -
error HML-P205: 'case' does not begin a statement
$ printf 'module M\notherwise\n'             | .venv/bin/hml check -
error HML-P205: 'otherwise' does not begin a statement
$ printf 'module M\nend_case\n'              | .venv/bin/hml check -
error HML-P205: 'end_case' does not begin a statement
$ printf 'module M\npending_obligation\n'    | .venv/bin/hml check -
error HML-P205: 'pending_obligation' does not begin a statement
```

**The one genuinely decidable fragment works:**

```
>>> check_exhaustive(["x > 0", "x < 0"])
decided=True  exhaustive=False  reason='the branches leave x = 0 uncovered'
>>> check_exhaustive(["x > 0", "otherwise"])
decided=False exhaustive=False
```

That is a real decision procedure over one variable against numeric thresholds, and its
docstring bounds itself honestly. `otherwise` is undecidable *as a bare condition* by
design — it is modelled one level up as `Case(complement=True)` — which is correct
layering and a usability trap for anyone who reaches for the obviously named function.

**The kill criterion cannot fail.** `L5: adds no diagnostic V0 does not already produce`.
V0 produces no discourse diagnostics at all, so the criterion is satisfied by the layer
existing. Red-team §2.2 recommended replacing it with a reported/false-report rate;
that recommendation is **still open** in `spec/v1/semantic_objects.yaml`.

No oracle. `EXPERIMENTAL`.

---

## 10. concept references — `SUPPORTED_ENFORCED`

**This is the safe concept surface, stated precisely.** A `concept … end` block is a
**module-local typed declaration that generates proof obligations**. It is admissible in
the frozen gate because **no trust decision depends on automatic admission**: the block
makes no novelty claim, consults no registry, and asserts nothing about identity outside
the module in which it appears.

Concretely, the safe surface is exactly:

- `concept <Name> [extends <Name>(, <Name>)*] … end` as a statement;
- the six member kinds `parameter` `transform` `invariant` `property` `example`
  `counterexample`;
- `<Name>` used in type position within the same module, yielding `ConceptType`;
- each `invariant` becoming a `ProofObligation` that the checker reports and does not
  discharge.

Everything else about concepts — minting, admission, duplicate detection, lifecycle,
aliases, dependency admission, `compresses` evidence — is §11 and is quarantined.

**(1) valid**

```
$ .venv/bin/hml check examples/concepts/location_scale_family.hml
ok: ConceptLibrary (2 statements, 5 symbols, 2 proof obligation(s))
```

**(2) rejected — six distinct codes**

```
$ printf 'module M\nconcept Vague\n    parameter location : Real\nend\n' | .venv/bin/hml check -
error HML-S603: concept 'Vague' declares no invariant and no example

$ printf 'module M\nconcept Child extends Nonexistent\n    parameter a : Real\n    invariant p := a > 0\nend\n' | .venv/bin/hml check -
error HML-N305: concept 'Child' extends unknown concept 'Nonexistent'

$ printf 'module M\nconcept A extends B\n    parameter a : Real\n    invariant p := a > 0\nend\nconcept B extends A\n    parameter b : Real\n    invariant q := b > 0\nend\n' | .venv/bin/hml check -
error HML-S602: circular concept hierarchy: A extends B extends A

$ printf 'module M\nparam x : Frobnicator\n' | .venv/bin/hml check -
error HML-T440: unknown type 'Frobnicator'
```

plus `HML-N304` (concept declared twice) and `HML-N303` (name already in scope).
`HML-S603` is the important one: "sounds plausible" is not an admissible definition.

**(3) oracle** — `location_scale_family.hml` round-trips to a byte-identical hash
(`4498edfa93ba212c…`); `ConceptDecl` and `ConceptMember` are both serialised by
`backends/canonical.py`.

**Enforced mechanically that this surface stays inert:**
`test_quarantine.py::test_compiling_a_concept_never_loads_the_minting_or_registry_modules`
compiles, canonicalises and hashes the concept example in a fresh interpreter and asserts
that no `hamiltonian_lang.v1.*` module was imported.

---

## 11. concept minting and admission — `KNOWN_FAILED`

Mandated ruling. Evidenced by re-execution, not by citation.

`spec/v1/semantic_objects.yaml::kill_criteria.minting` says the protocol has failed if a
seeded registry accepts a semantically equivalent concept via a vacuous constraint, an
undeclared parameter, or a trivially rearranged definition. **All three still succeed**,
verbatim from `audits/V1_RED_TEAM.md` §3:

Reproduction, executable from this repository — the same four candidates are built and
minted by
`tests/freeze/test_quarantine.py::test_pin_the_minting_duplicate_admission_exploits_still_reproduce`:

```
$ .venv/bin/python -m pytest tests/freeze/test_quarantine.py -k minting
3 passed, 49 deselected in 0.13s
```

The raw session, run 2026-08-05:

```
baseline Alpha                   -> verdict=admitted   admitted=True blocking=()
3.1 vacuous constraint           -> verdict=admitted   admitted=True blocking=()
3.2 undeclared parameters        -> verdict=admitted   admitted=True blocking=()
3.3 algebraic rewrite            -> verdict=admitted   admitted=True blocking=()

ADMITTED IN REGISTRY: ['Alpha', 'AlphaClone', 'AlphaNoParams', 'AlphaRewritten']
COUNT: 4
```

Four names for one concept, admitted with two fabricated file paths
(`does/not/exist_1.hml`, `does/not/exist_2.hml`) and `lambda: True` as the inhabitation
witness. The evidence check is still unverified against the filesystem:

```
>>> CompressionEvidence("s", ("does/not/exist_1.hml","does/not/exist_2.hml"), "(a-b)+(a-b)", "C").demonstrated
True
```

**Control — the protocol is circumventable, not inert.** A byte-identical clone under a
new name *is* caught:

```
>>> mint(candidate(concept("AlphaExactClone")), registry).verdict
duplicate            # blocking codes ('DUPLICATE_OF_EXISTING',), duplicate_of 'Alpha'
```

Both the exploit and this control are pinned in `test_quarantine.py`, so closing any of
the four attacks fails the suite and forces this row to be re-evidenced.

**What the registry itself does enforce** (its own kill criterion, and it passes):

```
dependency cycle           -> DependencyCycleError: dependency cycle: A -> B -> A
alias collision            -> AliasCollisionError: handle 'shared' already resolves to 'C1'
duplicate canonical id     -> DuplicateConceptError: canonical_id 'D' is already registered
proposed -> admitted       -> LifecycleError: not a legal transition
unadmitted dependency      -> UnadmittedDependencyError: H cites 'G', whose status is proposed
```

So the *data structure* holds and the *admission decision* does not. That is the precise
shape of the failure, and it is why §10's concept surface can be frozen while this one
cannot: §10 never asks the protocol anything.

**No registry artefact is committed** — `find . -name "*registry*.json"` returns only
`spec/concept_registry.schema.json`, the schema. Nothing in the repository currently
depends on an admission verdict.

---

## 12. semantic morphology — `EXPERIMENTAL`

**Not reachable from the gate.**

```
$ printf 'module M\nfamily Estimation of theta : ParameterSpace\n' | .venv/bin/hml check -
error HML-P205: 'family' does not begin a statement
$ printf 'module M\nmember estimator : Real\n'                     | .venv/bin/hml check -
error HML-P205: 'member' does not begin a statement
```

**What works, in Python** — and the `families` kill criterion (*"the estimator/estimate
confusion still type-checks"*) is **not** met here:

```
>>> may_substitute(EstimationRole.ESTIMATOR, EstimationRole.ESTIMATE)
(False, 'a estimator (a function from samples to the parameter space) cannot stand where
  a estimate (the value obtained from one particular sample) is required; there is no
  coercion between estimation roles')
>>> attribute_property("unbiased", to=EstimationRole.ESTIMATE)
RoleTypeError: 'unbiased' is not a property of the estimate …
>>> attribute_property("frobnicated", to=EstimationRole.ESTIMATOR)
UnknownPropertyError: 'frobnicated' is not a declared property of the estimation family
```

`STRING_DERIVATION_IS_PROHIBITED` is a real module constant, not a comment, and
`PROPERTY_CARRIERS` is a declared table with no suffix rule behind it. The spec's
"DECLARED, never GENERATED" is honoured.

**Why `EXPERIMENTAL` and not higher.** No surface, no oracle, and `PROPERTY_CARRIERS` is
a hand-written table of 19 properties that is correct for what it lists and raises
`UnknownPropertyError` on the twentieth. It is a closed set that grows by decision
record; it should be documented as one rather than as a rule.

---

## 13. Lean — `UNSUPPORTED`

Mandated ruling, and the evidence is stronger than "Mathlib is missing".

**Toolchain, probed here:**

```
$ lean --version
Lean (version 4.32.2, arm64-apple-darwin24.6.0, commit f3b06c705e6c85f5314019d5d3baab0fec5b580c, Release)

$ printf 'import Mathlib\ntheorem t : True := trivial\n' > /tmp/MathlibProbe.lean && lean /tmp/MathlibProbe.lean
error: unknown module prefix 'Mathlib'
No directory 'Mathlib' or file 'Mathlib.olean' in the search path entries:
/Users/moheet/.elan/toolchains/leanprover--lean4---v4.32.2/lib/lean
```

`lean` **is** on PATH. **Mathlib is not installed.**

**Every emitted file depends on Mathlib.** 8 of 8 canonical examples emit
`import Mathlib` (`backends/lean.py:243`). Nothing the backend produces elaborates:

```
$ .venv/bin/hml render examples/logic/quantifier_scope.hml -t lean --no-report > /tmp/QS.lean
$ lean /tmp/QS.lean ; echo $?
error: unknown module prefix 'Mathlib'
1

$ grep -v '^import Mathlib' /tmp/QS.lean > /tmp/QSnm.lean && lean /tmp/QSnm.lean ; echo $?
error(lean.synthInstanceFailed): failed to synthesize instance of type class  LT ℝ   (x2)
1
```

**Not even the `Natural`-only case survives**, which is the sharpest result in this
section — `ℕ` is Mathlib notation, so there is no Mathlib-free subset at all:

```
$ printf 'module NatOnly\nconst n : Natural = 7\nprove n > 3\n' > /tmp/nat.hml
$ .venv/bin/hml render /tmp/nat.hml -t lean --no-report | grep -v '^import Mathlib' > /tmp/Nat.lean
$ lean /tmp/Nat.lean ; echo $?
error(lean.synthInstanceFailed): failed to synthesize instance of type class  OfNat ℕ 7
1
```

**And even with Mathlib installed, no emitted theorem could ever be verified**, because
the design freeze §8 forbids proof search and every obligation is closed with `sorry`.
`v1/lean_verify.py` rejects the backend's own output before Lean is invoked:

```
>>> verify(open('/tmp/QS.lean').read()).verdict
rejected_forbidden_tactic
  detail: source contains 'sorry'; a goal closed by 'sorry' is not proved, and Lean exits 0 on it
```

**`lean_verify.py` itself is sound and was exercised** — it is the one part of this row
that works:

```
>>> verify("theorem t_true : (1 : Nat) = 1 := rfl\n",
...        expected_statement="theorem t_true : (1 : Nat) = 1").verdict
verified                       # axioms {'t_true': []}
>>> verify("theorem definitely_false : (1 : Nat) = 2 := by sorry\n").verdict
rejected_forbidden_tactic
>>> verify("theorem t_true : (1 : Nat) = 1 := rfl\n",
...        expected_statement="theorem t_true : (1 : Nat) = 2").verdict
rejected_statement_mismatch
```

So: `lean_verify` is a working gate that currently has nothing to pass through it.

**Verdict `UNSUPPORTED`, with this precise reading:** the Lean *rendering* is
statement-only and structurally tested — `tests/backends/test_lean.py` is 120 parametrised
cases over 30 test functions, all passing — and its translation losses are fully declared.
Those tests check the emitted **text**, never its elaboration. **No emitted artefact has
ever been accepted by a Lean kernel**, on this machine or any other recorded in this
repository, and by design none can be. Nothing downstream may treat Lean output as
verification.

```
$ .venv/bin/python -m pytest tests/backends/test_lean.py
120 passed in 0.15s
```

---

## 14. Stan — `SUPPORTED_PARTIAL`

**Toolchain:** `stanc` is not on PATH; there is no CmdStan install and no
`cmdstanpy`/`pystan` in the venv. **No Stan artefact this project has ever produced has
been compiled.**

**Why `SUPPORTED_PARTIAL` and not `UNSUPPORTED`:** unlike Lean, Stan has a working
deterministic oracle over a declared narrow subset. `importers.SUPPORTED_SUBSETS["stan"]`
declares what it accepts and rejects, and the round trip is checked by content hash:

```
$ .venv/bin/python -m pytest tests/roundtrip/test_importers.py -q -k stan
11 passed, 15 deselected in 0.07s
```

The losses are measured, not assumed:

- **`PositiveReal` is inexpressible.** Stan's `real<lower=0>` is closed and admits 0. The
  importer widens to `NonNegativeReal` and the reconstruction is then *correctly rejected*
  with `HML-T413`. Because every scale role in every family is strictly positive, only
  **Uniform, Binomial and Bernoulli** are inside the round-trippable subset.
- **Observed values are lost** — Stan reads data from a file, so `obs n = 20` survives
  only as a comment and the hash changes.
- **Interleaved declaration order is destroyed** by Stan's block grouping; the hash
  changes even though the meaning arguably does not. Not normalised away.
- Role labels become positional; the prior/likelihood/law distinction and the
  conditioning set are both lost.

**No diagnostic code on the backend side.** `backends/base.py` records loss as
`Unsupported(construct, reason, line, severity)` with free text and no code, and no
backend rejects anything. Criterion (2) is therefore met only indirectly — through the
importer's `UnsupportedConstruct` and the `HML-T413` on reconstruction — which is why
this row is capped at `SUPPORTED_PARTIAL`.

---

## 15. SymPy — `SUPPORTED_PARTIAL`

**Toolchain:** `sympy 1.14.0` in the venv. This is the only backend whose output is
actually executed.

```
$ for f in examples/**/*.hml; do hml render $f -t sympy --no-report > out.py && python out.py; done
sympy: rendered=8 executed_ok=8
```

8/8 canonical examples render and execute, exit 0. `tests/backends/test_sympy_execution.py`
pins three regressions where a dropped quantified definition left a dangling reference and
the module raised `NameError` on import — a defect found only by running the output, never
by reading it.

**Why capped at `SUPPORTED_PARTIAL`:**

- **Execution is a syntax check, not a semantics check.** `linear_regression.hml` executes
  cleanly while reporting eight dropped or weakened constructs.
- **SymPy performs transformation steps and discharges none of their obligations** —
  `sp.cancel((x*y)/x) -> y` with `x != 0` neither recorded nor checked. This is precisely
  the error class L2 exists to catch, committed silently by the target.
- **No justification object of any kind.** `sp.Eq(x+y, y+x)` evaluates to bare `True`, so
  a proved invariant and a conjectured one arrive at the same representation.
- No rejection path and no diagnostic code, as with every backend.

---

## 16. What this manifest does not claim

1. **`backend_support.py` (1,949 lines) was not audited.** Its claims are cross-checked
   against my own probes where they overlap (Mathlib absent, `stanc` absent, SymPy
   executes) and every overlap agreed. The rest is unverified by me.
2. **`discourse.py` (936 lines) was probed at one function**, `check_exhaustive`. The
   `DiscourseState` machinery, `classify_phrase` and `DiscourseReport` are unexercised
   here.
3. **`registry.py`'s schema-validation path and `by_alias` machinery were not attacked.**
   I exercised the five invariants its kill criterion names; the rest is untested by me.
4. **`transformation.py`'s `TransformationChain` (lines 957–1162) was not exercised.**
   I probed `step`, `obligations`, `kind` and `require_kind` only.
5. **No model was run.** This phase is entirely offline, by charter.
6. **No claim that any frozen feature is correct**, only that it is *enforced*: a stated
   invalid program is rejected with a named code and the canonical form discriminates the
   meanings the feature exists to separate.

---

## 17. Open items for the Lead Architect

Reported, not fixed — all are in Lead-owned files.

| # | item | file | severity | status |
|---|---|---|---|---|
| 1 | `kill_criteria.L4` says the p-value conflation is "Now closed"; it was closed in the Python API and open in the language (§4) | `spec/v1/semantic_objects.yaml` | **claim was wrong as written** | **fixed** 2026-08-05 — criterion now names the layer and records the language-level status |
| 2 | User-`def` calls check neither arity nor argument type (§2a) | `type_system/__init__.py` | permissive checker; `CLAUDE.md` rule 9 | **fixed** 2026-08-05 — `CallableSignature`, `HML-T470/471/472` |
| 3 | `const p : Probability = 0.5` accepted, `def p : Probability := 0.5` rejected (§2b) | `type_system/__init__.py` | inconsistent enforcement | **fixed** 2026-08-05 — `DefineStmt` routes through `check` |
| 4 | Module docstring claims `check` is used for "function arguments … definition bodies … proof claims"; 2 of 12 sites route through it (§2) | `type_system/__init__.py` | docstring overstates | **fixed** 2026-08-05 — docstring carries the measured table; 5 of 12 now check |
| 5 | L5's kill criterion is still satisfiable by the layer existing (red-team §2.2, unactioned) | `spec/v1/semantic_objects.yaml` | unfalsifiable criterion | **open** — Lead-owned |
| 6 | `test_frozen_file_list_is_not_stale` unconditionally skips this manifest's path; the skip is now stale | `tests/freeze/test_syntax_gate_freeze.py:119` | stale skip (coverage exists via `test_quarantine.py`) | **open** — Lead-owned |

---

## 18. Verification

Run after every change in this phase, on the branch as it stands:

```
$ ./scripts/conformance.sh
=== ruff lint ===                                            PASS
=== mypy ===                                                 PASS
=== examples check ===                                       PASS
=== pytest (-n 18) ===                                       PASS
=== canonical form validates against spec/ir.schema.json ===  PASS
=== no unsupported superiority claims in public docs ===      PASS
=== docs/private is not referenced from public docs ===       PASS
=== no unresolved placeholders in production source ===       PASS
============================
CONFORMANCE: PASS
```

Full suite: **1628 passed, 5 skipped, 1 xfailed** (8.26s at `-n 18`), of which 52 are the
new quarantine tests. Serial re-run (`HML_JOBS=1`) of `tests/freeze` agrees, so nothing
here is ordering-dependent.

**Re-verified 2026-08-05 after the §2 and §4 amendments** (Subagent A,
HML-CONSTITUTIONAL-CORE-001): `./scripts/conformance.sh` ends `CONFORMANCE: PASS`, full
suite **3809 passed, 4 skipped, 1 xfailed** at `-n 18`. That total includes concurrent
work by other agents on this branch and is not attributable to this amendment alone; the
amendment itself added 185 tests across `tests/constitutional/`,
`tests/type_system/test_call_signatures.py`,
`tests/type_system/test_contextual_positions.py` and `tests/type_system/test_pvalue.py`.
`tests/freeze` and `tests/constitutional` were re-run serially (`HML_JOBS=1`) and agree,
so neither is ordering-dependent.

`stanc` is absent, so no Stan stage exists to run. `lean` is present and was invoked
directly (§13); it is not part of `conformance.sh` and remains so — a conformance gate
that depends on an absent Mathlib would be a gate nobody can pass.
