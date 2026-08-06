# M1.5 independent falsification report

**Role.** Agent 4, independent falsifier for `HML-RESUME-RECOVER-FREEZE-ACQ0-006`.
**Tree.** `integration/m1.5-paper-derived-closeout` @ `57459a1`, measured 2026-08-06.
**Method.** Offline only. No model call of any kind was made, by this agent or by anything
it ran.
**Mandate.** Break the claims. Do not repair them. Every finding below carries a runnable
reproduction; every attack that failed is recorded as such.

**Gate: `M1_5_FALSIFICATION_FOUND_DEFECTS`** — five reproduced defects, two of them
soundness breaks in endpoints that gate published numbers.

---

## Summary

| id | subsystem | severity | one line |
|----|-----------|----------|----------|
| **F-1** | `equivalence/matching.py` | **high** | Renaming one *unused* declaration disables the Tier-1 name lock, and the scorer certifies role swaps it refutes when the vocabularies coincide. False-positive equivalences. |
| **F-2** | `verification/obligations/checkers.py` | **critical** | A partial operation hidden behind a `def` is invisible to `partiality_risk`, so `prove q = 1` with `def q := x / x` and `x : Real` reaches **`VERIFIED`**. It is false at zero. |
| **F-3** | `evaluation/acq0/budget/slots.py` | **high** | `completion_allowance` is unvalidated while its sibling `safety_reserve` is floored. A 9000-token prompt reports `FITS` in an 8192-token slot. |
| **F-4** | `repair/plan.py` | **high** | The leak check is an exact substring test. Permuting the statements of the corrected program hides a complete, transcribable copy of the answer from it. |
| **F-5** | `equivalence/status.py` | **medium** | `register_certifying_method` rebinds `status.CERTIFYING_METHODS`; the package-level re-export goes stale. One authoritative set, two names, and they disagree. |

Resisted: metric integrity (target 3), training eligibility (target 4, three routes),
hypothesis isolation (target 5), the D-024 `ContextVar` fix under contention, and all nine
of the explicitly required `VERIFIED` probes. Details in "Attacks that failed".

Tests: `tests/adversarial/test_m1_5_falsification.py` — 39 passed, 13 xfailed, 0 failed.
Each defect is pinned by an `xfail` naming its finding id, and each is accompanied by a
**hard passing control** that establishes the contradiction rather than merely asserting a
preference.

---

## F-1 — the Tier-1 name lock is defeated by renaming one unrelated declaration

**Claim attacked.** 49/49 decided, precision 1.000, **0 false-positive equivalences**.
Reproduced as stated: `.venv/bin/python -m evaluation.m3.equivalence.run` gives
`precision 1.000`, `false-positive equivalences 0`.

**The mechanism.** `matching.strict_match`:

```python
vocabulary = declared_names(reference)
locked = bool(vocabulary) and vocabulary == declared_names(candidate)
```

The lock that stops Tier 1 permuting module-level names is switched on only when the two
modules declare **exactly** the same set of names. Change one declaration's spelling — any
declaration, including one that is never referenced — and the lock switches off for the
whole module. Tier 1 is then free to swap the two names that actually carry the claim.

**Reproduction.**

```python
from hamiltonian_lang.equivalence import EquivalenceScorer, Endpoint
S = EquivalenceScorer()

REF  = "module M\n\nparam p : Bool\nparam q : Bool\nparam spare : Bool\n\nprove p implies q\n"
SAME = "module M\n\nparam p : Bool\nparam q : Bool\nparam spare : Bool\n\nprove q implies p\n"
DIFF = "module M\n\nparam p : Bool\nparam q : Bool\nparam filler : Bool\n\nprove q implies p\n"

S.compare(REF, SAME, endpoint=Endpoint.ENCODING_EQUIVALENCE).status
# EquivalenceStatus.VERIFIED_NONEQUIVALENT   (Tier 2, propositional countermodel)
S.compare(REF, DIFF, endpoint=Endpoint.ENCODING_EQUIVALENCE).status
# EquivalenceStatus.VERIFIED_EQUIVALENT      (Tier 1, symbol_map {'p':'q','q':'p','spare':'filler'})
```

`spare` and `filler` are declared and never referenced. They cannot change what either
module asserts. The engine nonetheless issues **opposite decisive verdicts** for the same
mathematical content.

**Why this is a false positive and not a policy disagreement.** The benchmark corpus
itself labels these pairs `NONEQUIVALENT`, with rationales:

| corpus case | pair | label |
|---|---|---|
| `nearmiss.converse` | `prove p => q` vs `prove q => p` | NONEQUIVALENT — "a conditional is not its converse" |
| `nearmiss.subtraction_order` | `def f := a - b` vs `def f := b - a` | NONEQUIVALENT — "subtraction is not commutative" |
| `nearmiss.division_order` | `def f := x / y` vs `def f := y / x` | NONEQUIVALENT — "division is not commutative" |
| `adversarial.implication_direction` | same as `nearmiss.converse` | NONEQUIVALENT |

Each of these becomes `VERIFIED_EQUIVALENT` when one unrelated declaration is renamed.
Confirmed for implication, subtraction, division and comparison direction:

```
E  p=>q vs q=>p,   lock defeated -> VERIFIED_EQUIVALENT  (Tier 1)
F  a-b vs b-a,     lock defeated -> VERIFIED_EQUIVALENT  (Tier 1)
F2 a-b vs b-a,     lock on       -> COUNTEREXAMPLE_FOUND (Tier 3)
G  a/b vs b/a,     lock defeated -> VERIFIED_EQUIVALENT  (Tier 1)
H  a>b vs b>a,     lock defeated -> VERIFIED_EQUIVALENT  (Tier 1)
```

**Blast radius.** The 49-pair corpus contains no case where the candidate renames a
declaration, so the measured precision of 1.000 says nothing about this class. Under H1/H2
scoring the candidate is *model output*: choosing a different variable name is the single
most likely difference between a model's encoding and the reference. The precision claim is
therefore load-bearing exactly where it is untested.

**Root disagreement.** Tier 1 treats module-level declared names as freely renameable
binders. Tier 2 treats them as rigid atoms — its refutation detail reads "a propositional
countermodel exists over **independent boolean atoms**". Both tiers are internally
consistent; they cannot both be right about the same module, and the lock's
vocabulary-equality test is what decides which one runs.

**Not fixed here.** A fix should make module-level name rigidity unconditional, or make it
follow from a property of the *pairing* rather than from set equality of the whole
vocabulary. Either way it is a change to `matching.py`, which this agent does not own.

**Pinned by.** `test_f1_spare_rename_must_not_flip_the_verdict[converse|subtraction|comparison]`
(xfail) and the hard control `test_f1_control_the_same_pair_is_refuted_when_vocabularies_coincide`.

---

## F-2 — an unsound claim reaches `VERIFIED` by hiding a division behind a `def`

**Claim attacked.** `VERIFIED` was made reachable under D-025 without being weakened. The
brief names the exact probe: `x/x = 1` with `x : Real` must **not** be `VERIFIED`, because
it is false at zero.

**Direct form: correct.**

```python
verify_source("module M\n\nparam x : Real\n\nprove x / x = 1\n").verdict
# GlobalVerdict.UNSUPPORTED
#   detail: "a divisor ranges over (-inf, +inf), which is not provably non-zero"
```

**Laundered form: unsound.**

```python
from hamiltonian_lang.verification.obligations import verify_source
SRC = "module M\n\nparam x : Real\n\ndef q := x / x\n\nprove q = 1\n"
verify_source(SRC).verdict
# GlobalVerdict.VERIFIED     substantive=True
#   OBL-...  DISCHARGED  symbolic_identity  ::  q = 1
#   detail: "sympy.simplify(left - right) is identically zero"
```

The federation inherits it:

```python
from hamiltonian_lang.improvement.verification import (
    Candidate, CandidateLanguage, CanonicalObject, classify, default_federation)
classify(default_federation().run(
    CanonicalObject(object_id="p", source=SRC),
    Candidate(text=SRC, language=CandidateLanguage.HML)))
# 'VERIFIED'
```

**Mechanism.** Two functions in `checkers.py` disagree about which expression is under
consideration.

* `_to_sympy` (line ~840) resolves a `Ref` by looking it up in `env.definitions` and
  **inlining the definition body**:
  ```python
  definition = env.definitions.get(expr.name)
  if definition is not None:
      return _to_sympy(definition.body, env, symbols, sympy)
  ```
* `partiality_risk` (line 1038) walks `BinOp`, `Call`, `UnaryOp`, `Comparison` and
  `LogicalOp`. It has **no `Ref` case**, so it falls through to `return None` for a bare
  name.

`SymbolicIdentityChecker.judge` calls `partiality_risk(expr, task.env)` on the *surface*
proposition `q = 1`. That tree contains a `Ref` and a `Literal`, no division, and
`env.domain("q")` is `None`. The guard reports no risk. `_to_sympy` then decides
`simplify(x/x - 1) == 0` and the obligation is `DISCHARGED`. The counterexample sampler
never runs: `_run_pipeline` returns at the first checker that says `DISCHARGED` or `FAILED`,
and `SymbolicIdentityChecker` precedes `NumericalCounterexampleChecker` in
`DEFAULT_CHECKERS`.

The `partiality_risk` docstring names precisely this unsoundness — *"`sympy.simplify(x/x - 1)`
is `0`, so without this check the engine discharged `prove x / x = 1` for a free real `x` —
a claim that is **false at zero**"* — and the guard it describes is bypassed by one line of
indirection.

**Generalises to every partial operation the guard covers.**

| module | verdict | why it is wrong |
|---|---|---|
| `def q := x / x` · `prove q = 1` | `VERIFIED` | undefined at `x = 0` |
| `def q := x ^ (-1)` · `prove q * x = 1` | `VERIFIED` | undefined at `x = 0` |
| `def q := x ^ 0` · `prove q = 1` | `VERIFIED` | `0^0` is indeterminate |

**Does not generalise where the divisor stays syntactically visible** — the guard is not
broken, only blind:

| module | verdict |
|---|---|
| `def d := x` · `prove d / d = 1` | `UNSUPPORTED` (correct) |
| `def z := x - x` · `prove z / z = 1` | `UNSUPPORTED` (correct) |
| `prove -(x / x) = -1` | `UNSUPPORTED` (correct — `UnaryOp` recursion works) |

**Severity.** This is the flagship endpoint. `substantive=True` on the laundered form means
the H3 task filter would accept it as a real measurement. A `def` is idiomatic HML and
appears throughout `examples/`; a model asked to encode a ratio will very often name it.

**Not fixed here.** The fix is a `Ref` case in `partiality_risk` that follows
`env.definitions` with a depth bound, mirroring what `dimension_of_expr` already does at
line 1289. That is an edit to `src/hamiltonian_lang/verification/obligations/`, which this
agent does not own.

**Pinned by.** `test_f2_a_partial_operation_behind_a_def_must_not_reach_verified[...]`,
`test_f2_the_federation_inherits_the_unsound_verified` (xfail) and the hard control
`test_f2_control_the_same_claim_is_unsupported_when_written_inline`.

---

## F-3 — `completion_allowance` is unvalidated, so a prompt larger than the slot "fits"

**Claim attacked.** Zero hidden truncation permitted;
`prompt + completion_allowance(2048) + safety_reserve(>=256) <= per-slot context`.

**Asymmetry.** `SlotPolicy.prompt_ceiling` floors `safety_reserve`:

```python
if safety_reserve < MIN_SAFETY_RESERVE:
    raise InsufficientReserve(...)
return self.per_slot_context - completion_allowance - safety_reserve
```

`completion_allowance` gets no floor, no sign check, and no upper bound on the resulting
ceiling. It is a plain keyword argument on both `prompt_ceiling` and `eligibility`.

**Reproduction.** 4 x 8192, correct ceiling 5888.

```python
from evaluation.acq0.budget.slots import eligibility, policy_for_slots
from hamiltonian_lang.improvement.episodes import Measurement
m = lambda n: Measurement.measured(n, instrument="provider_usage", citation="fixture")
p = policy_for_slots(4)                      # per_slot_context == 8192

eligibility(m(7900), p, completion_allowance=0).fit
# Fit.FITS   ceiling=7936 headroom=36
#   real requirement: 7900 + 2048 + 256 = 10204  >  8192

eligibility(m(9000), p, completion_allowance=-2000)
# Fit.FITS   ceiling=9936
#   detail: '9000 + -2000 + 256 = 7256 <= 8192'
```

The second case is the sharp one: a 9000-token prompt is declared to fit an 8192-token
slot, and `Eligibility.detail` — the field a reader would trust — records the false
arithmetic verbatim, in an artefact that serialises through `to_dict()`.

**Why it matters here specifically.** The module's own docstring says the overflow failure
mode is silent (`llama-server` evicts the front of the context; the run continues and looks
plausible) and that `COMPLETION_ALLOWANCE` is "Fixed across protocols by design ... so
neither arm wins by having been allowed to emit more". Making it a free per-call keyword is
exactly the asymmetry `ComparisonPlan` and `assert_symmetric` exist to forbid for slot size
and curriculum, left open on the third axis.

**Secondary, same file, lower severity.** `SlotPolicy.total_context` is a free constructor
parameter with no relation to the measured `TOTAL_CONTEXT = 32768`.
`SlotPolicy(parallel_slots=4, speedup=2.08, total_context=131072)` yields four 32768-token
slots on a server configured `-c 32768`, and a 30000-token prompt then reports `FITS`. Not
pinned by a test: declaring a differently-configured server is arguably a legitimate use.

**Cosmetic, noted not pinned.** `count = int(prompt_eval_count.value or 0)` truncates a
float toward zero, so a hypothetical `5888.9` becomes `5888` and reports `FITS` with
headroom 0. Real `prompt_eval_count` values are integers, so this is latent.

**Held.** `Measurement` refuses a fabricated count outright (`FabricatedMeasurement` for an
unknown instrument, a missing citation on an unprobeable instrument, or a negative value),
`eligibility` raises `EstimateOfferedAsMeasurement` for a non-token instrument, and an
absent measurement yields `Fit.UNDETERMINED` with `fits is False`. The provenance discipline
around the input number is sound; only the arithmetic around it is open.

**Pinned by.** `test_f3_no_prompt_may_be_eligible_when_the_real_inequality_fails[...]`,
`test_f3_the_ceiling_may_never_exceed_the_slot` (xfail) and the hard controls
`test_the_stated_inequality_holds_at_the_documented_defaults`,
`test_the_safety_reserve_floor_is_enforced`,
`test_an_unmeasured_prompt_is_undetermined_and_not_a_pass`.

---

## F-4 — permuting the corrected program hides it from the leak check

**Claim attacked.** A repair plan must never contain the complete corrected program or the
final answer.

**Mechanism.** `plan_leak_reasons` detects the corrected program with

```python
needle = _normalise(target_program)
if is_program_like(needle) and needle in haystack:
```

— a whitespace-normalised **exact substring** test against the concatenated plan fields.
`matching.py` records, as an explicit Tier-1 assumption, that *"a module is an unordered
collection of statements, not a script"*. Permuting the statements therefore yields the same
module and a different string, and the check does not fire.

**Reproduction.**

```python
TARGET = ("module M\n"
          "param sigma : PositiveReal\n"
          "var X : RandomVariable[Real]\n"
          "require sigma > 0.0")
lines    = TARGET.splitlines()
permuted = [lines[0], lines[2], lines[1], lines[3]]      # same statements, swapped order

plan_leak_reasons(plan(lines),    target_program=TARGET)
# ['the plan contains the complete corrected program; ...']      <- caught
plan_leak_reasons(plan(permuted), target_program=TARGET)
# []                                                             <- clean
assert_plan_non_leaking(plan(permuted), target_program=TARGET)   # returns the plan
```

The plan the Learner then receives:

```
repair plan:
  1. module M
  2. var X : RandomVariable[Real]
  3. param sigma : PositiveReal
  4. require sigma > 0.0
```

Every statement of the answer, verbatim, one per step, inside the six-step limit, with no
`:=` binding for `_BOUND_VALUE` to catch and no step exceeding `MAX_STEP_LINES`. The
per-step "multiple statement keywords" rule does not fire because each step holds exactly
one statement. `CHAIN_OF_REPAIR` run against such a plan measures transcription, which is
the precise failure the module exists to prevent.

**Second gap in the same function.** `forbid_novel_numerals` scans for digit sequences
(`_NUMERAL`). An answer written in words carries none:

```python
plan_leak_reasons(plan(("the corrected scale is three point one four",)),
                  final_answer="3.14", forbid_novel_numerals=True, known_numerals=())
# []
```

**Not fixed here.** A containment test over the *multiset of statement lines*
(`statement_lines` already exists and is exported for exactly this kind of sharing) would
close the permutation route; the spelled-out-numeral route needs a different instrument.
Both are edits to `src/hamiltonian_lang/repair/`, which this agent does not own.

**Held.** The verbatim-order case, the over-long step, the multi-keyword step and the
bound-value step all fire correctly, and a legitimate category-level plan
(`"widen the declared type until it excludes non-positive values"`) is clean.

**Pinned by.** `test_f4_a_permuted_corrected_program_is_still_the_answer`,
`test_f4_a_spelled_out_numeral_evades_the_novel_numeral_check` (xfail) and the hard controls
`test_a_plan_carrying_the_corrected_program_verbatim_is_refused`,
`test_a_plan_stating_a_category_rather_than_a_value_is_clean`.

---

## F-5 — the certifying-method set has two names that diverge

**Claim attacked.** Target 8 asked for the *next* shared-state hazard after D-024 made
`backends/canonical.py::_INCLUDE_NAMES` a `ContextVar`.

**Mechanism.** `equivalence/status.py`:

```python
CERTIFYING_METHODS: frozenset[str] = frozenset(_CERTIFYING)

def register_certifying_method(method: str) -> None:
    global CERTIFYING_METHODS
    ...
    _CERTIFYING.add(method)
    CERTIFYING_METHODS = frozenset(_CERTIFYING)     # rebinds the module attribute
```

`equivalence/__init__.py` does `from .status import CERTIFYING_METHODS`, which copies the
*value* into the package namespace. Rebinding the module attribute cannot reach it.

**Reproduction.**

```python
import hamiltonian_lang.equivalence as pkg
from hamiltonian_lang.equivalence import status

status.register_certifying_method("tier9.new_sound_method")
"tier9.new_sound_method" in status.CERTIFYING_METHODS   # True
"tier9.new_sound_method" in pkg.CERTIFYING_METHODS      # False
pkg.CERTIFYING_METHODS == status.CERTIFYING_METHODS     # False
```

Every `from hamiltonian_lang.equivalence import CERTIFYING_METHODS` binding anywhere in the
process is stale from the first registration onward.

**Why it matters.** The set names the methods permitted to establish `VERIFIED_EQUIVALENT`.
Two disagreeing copies of a soundness-relevant allowlist is the shape of hazard D-024 was
about — one authority, several readers, silent divergence — moved from a module global to a
module attribute. `_CERTIFYING` is additionally a plain mutable `set` shared process-wide,
with no lock across the `add`/rebind pair.

**Held, in the same module.** The block that actually matters is executable and works:
`register_certifying_method` raises `ValueError` for every member of `SEARCH_ONLY_METHODS`,
so the counterexample searcher cannot be promoted to a certifier.

**Pinned by.** `test_f5_the_certifying_method_set_has_one_value_not_two` (xfail) and the
hard control `test_a_search_method_can_never_be_promoted_to_certifying`.

---

## Attacks that failed

Recorded because "I could not break X by A, B and C" is the informative form.

### Target 2 — obligation discharge / `VERIFIED`

All nine explicitly required probes hold. Measured verdicts:

| probe | engine | federation `classify` |
|---|---|---|
| `prove x / x = 1`, `x : Real` | `UNSUPPORTED` | `INCONCLUSIVE` |
| `prove x / x = 1`, `x : PositiveReal` | `VERIFIED` | `VERIFIED` |
| `prove 2 + 2 = 5` | `DISPROVED` (with witness) | `DISPROVED` |
| `prove 2 + 2 = 4` | `VERIFIED` | `VERIFIED` |
| `prove forall x : Real . x * x >= 0` | `UNSUPPORTED` | `INCONCLUSIVE` |

Attacks that did not work:

* **Name collision between the two obligation-naming schemes.** Two records with the same
  `kind:statement` descriptor but different decidability do not cancel: the engine also
  emits a per-record `OBL-NNN-<digest>` id, so the undischarged record survives the
  `remaining - discharged` set difference and `classify` still returns `INCONCLUSIVE`.
* **Injecting a discharged obligation name through `attachments["epistemic"]`.**
  `EpistemicVerifier` emits `claim:<key>` from caller-supplied keys, but every
  obligation-engine descriptor is `<source_kind>:<statement>` with `source_kind` drawn from
  the type checker's own kinds, and no kind is spelled `claim`. No collision is reachable.
* **`obligations_checked` carrying an `UNSUPPORTED` record.** Confirmed already fixed:
  `federation.py` builds `checked` from `if r.discharged` only, so an undecidable `forall`
  cannot be listed as checked.
* **Empty module.** `module M` + `param a : Real` is `VERIFIED` with zero obligations and
  `substantive=False`. This is documented behaviour (`VerificationOutcome.substantive`
  exists to let the H3 filter refuse it), not a defect.

### Target 3 — metric integrity

All four constructions parse and fail at the type stage; none produces an `HML-P` code.

| construction | code |
|---|---|
| wrong arity — `def f(a,b)`, called `f(1.0)` | `HML-T471` |
| wrong argument type — `Bool` into a `Real` parameter | `HML-T472` |
| wrong distribution role — `Normal(shape :=, rate :=)` | `HML-T416`, `HML-T414` |
| declared-type mismatch — `param p : Probability = 2.0` | `HML-T402` |
| unknown identifier | `HML-N301` (resolution, not parse) |
| genuine syntax error — `require ((((` | `HML-P231` (the control: parse can still fail) |

`CompileResult.ok()` is not readable as parse success and is not being read that way:
`evaluation/syntax_gate/candidates.py` carries a separate `parsed` property over
`stages.parse_status`, with the distinction stated in its own docstring, and
`scorer.py::_parse_facet` refuses to infer a parse verdict from an outcome that reports no
stages.

### Target 4 — training eligibility

Three routes attempted, all closed:

1. **Caller-supplied decision.** `build_record(..., decision=RoutingDecision(store=POSITIVE,
   training_eligible=True))` on facts that quarantine raises `RoutingDisagreement`; the
   decision is re-derived and compared, never trusted.
2. **Direct record construction.** `MemoryRecord(store=QUARANTINE, training_eligible=True)`
   raises `QuarantineEligibilityError`.
3. **Laundering through a trainable store.** `MemoryRecord(store=POSITIVE,
   training_eligible=True, hypothesis=EXCLUDED)` raises `QuarantineEligibilityError`; and a
   record whose `store` disagrees with its own `decision.store` raises `ValueError`.

`route(RoutingFacts(hypothesis=EXCLUDED, ...))` returns
`store=QUARANTINE, training_eligible=False` with `QuarantineReason.EXCLUDED_HYPOTHESIS`.

### Target 5 — hypothesis isolation

`require_single_hypothesis` refused every pooling attempt: `ACQ0 + H3`, `H1 + H2`,
`EXCLUDED + H1` (including with `allow_excluded=True`, which widens *which* single
hypothesis is acceptable and never the count), the bare string `"H1"`, and the empty
sequence. `Hypothesis.H3` and `Hypothesis.H3_VERIFIER_GUIDED_REPAIR` are the same member, so
they correctly do not count as two. `REPAIR_MECHANISM[ACQ0] == "ACQ0_REPAIR"` is distinct
from `REPAIR_MECHANISM[H3] == "H3_VERIFIER_GUIDED_REPAIR"` and contains no `H3` substring.
`EXCLUDED` is the only non-scientific member.

*Latent hazard, no reachable exploit found.* `Hypothesis` is a `StrEnum`, so
`hash(Hypothesis.H1) == hash("H1")` and `{Hypothesis.H1: 1, "H1": 2}` collapses to a single
key. Any aggregation keyed by a dict or set would silently merge a typed hypothesis with an
untyped string. `require_single_hypothesis` rejects untyped items at the boundary and no
call site was found that bypasses it, so this is recorded as a limitation rather than a
finding.

### Target 8 — concurrency, D-024 itself

The `ContextVar` fix holds under real contention. 600 `canonical_json(..., include_names=True)`
calls interleaved with 600 `content_hash` calls across 16 threads on a 300-declaration
module produced **0** corrupted named forms; 400 concurrent `result.hash()` calls produced
exactly 1 distinct hash. Both are pinned as hard tests so the regression cannot come back.

Other shared state surveyed without a reproduced defect: `v1/registry.py::_SCHEMA_CACHE`
(a process-global mutable dict cache keyed by `Path` — a shared singleton, but no
correctness divergence demonstrated); `v1/lean_verify.py` uses
`tempfile.TemporaryDirectory()` rather than a fixed path; no `importlib.reload` and no
parallel writes to a fixed file were found on any measured path.

---

## Limitations of this pass

* **Not exhaustive on the equivalence corpus.** F-1 was found by attacking the lock
  directly. Whether other Tier-1 certifications are reachable by different vocabulary
  manipulations (a `def` with parameters, a concept member, a name that is both declared
  and a `Call` callee) was not swept systematically.
* **F-2's blast radius is not quantified.** Every module under `examples/` was not
  re-verified for laundered partial operations; only the mechanism and three instances are
  demonstrated.
* **`evaluation/acq0/budget/` and `src/hamiltonian_lang/repair/` were in flight** during
  this pass. F-3 and F-4 are measured against the tree as it stood, and the budget tests
  skip cleanly if the module is absent.
* **`evaluation/corpus_governance/` was not attacked.** It is another agent's exclusive
  path, it was being edited throughout this pass, and it was not among the eight targets
  this agent was given. Nothing here says anything about it either way.
* **No live-model behaviour was tested.** Every claim here is about deterministic code. The
  leakage study's *empirical* half (does condition B reconstruct the target?) requires model
  calls and is out of scope by mandate.
* **All five defects are pinned with `xfail(strict=False)`.** A fix will turn them green
  silently rather than failing loudly. The trade is deliberate — three agents were writing
  to these paths concurrently and a strict xfail would convert someone else's fix into a
  gate failure — but it means this document, not the marker, is the durable record.

---

## Reproduce

```bash
.venv/bin/python -m pytest tests/adversarial/test_m1_5_falsification.py -q -rxs
.venv/bin/python -m evaluation.m3.equivalence.run
```

Nothing above requires a network connection, a model, or a running server.
