# HML process verification — the reachable `VERIFIED` endpoint

**Status:** implemented, measured, offline.
**Owner module:** `src/hamiltonian_lang/verification/obligations/`
**Evaluation apparatus:** `evaluation/m3/verification/`
**Tests:** `tests/verification/`
**Engine version:** `hml-obligation-engine-1.0.0` · **record schema:** `hml-obligation-record-1.0.0`

---

## 1. The problem this closes

`docs/evaluation/CONSTITUTIONAL_INTEGRATION_DECISIONS.md` records CONF-004:

> a well-formed candidate that exactly matches the reference classifies `INCONCLUSIVE`,
> because the type checker collects an undischarged `constraint` obligation and nothing
> discharges it.

Combined with CONF-005 — the Lean backend closes every obligation with `sorry` **by
design**, `sorry` is in `FORBIDDEN_TACTICS`, and Mathlib is absent — `VERIFIED` was
unreachable overall. H3's primary endpoint is *kernel-verified completion rate*, so H3
could not be run as specified.

The resolution recorded in CONF-004 was, correctly, *"accept as correct and record the
consequence loudly"*, and it named the trap: **auto-discharging constraints to obtain
`VERIFIED` would make the verdict meaningless.** This document describes an endpoint
that is reachable *and* still able to fail. Nothing here relaxes what `VERIFIED` means;
it adds a bounded set of things the system can actually decide, and refuses everything
else out loud.

**Nothing here widens Lean.** The engine never invokes Lean, never reads emitted Lean,
and never consults a proof-assistant artefact. `tests/verification/test_no_sorry_path.py`
enforces that by inspection and reproduces CONF-005 as a live assertion.

---

## 2. What `VERIFIED` now means

A module is globally `VERIFIED` when **all four** hold. The conjunction is written once,
in `engine._verdict`, so no caller can assemble a weaker version:

1. every required stage — lex, parse, resolve, type-check — reported no error;
2. every obligation, the compiler's and the engine's derived ones, is `DISCHARGED`;
3. no *semantic-preserving* view reported loss, **and** the HML surface round-trips to
   the same alpha-invariant canonical content hash;
4. no obligation remains `UNSUPPORTED`.

Condition 4 does the work. Drop it and every gap in the supported subset becomes a
silent pass; the endpoint stops being able to fail, and an endpoint that everything
reaches is worse than an unreachable one, because it looks authoritative. That is the
failure mode `CLAUDE.md` names as the worst in this codebase.

### Verdict lattice

| verdict | when |
|---|---|
| `INVALID` | a compiler stage errored; no obligation was even collected |
| `SEMANTIC_LOSS` | a semantic-preserving view lost something, or the round trip changed the content hash |
| `DISPROVED` | at least one obligation was refuted **with a witness** |
| `UNSUPPORTED` | some obligation lies outside the implemented subset |
| `INCONCLUSIVE` | some obligation was attempted and not decided |
| `VERIFIED` | all four conditions above |

`UNSUPPORTED` outranks `INCONCLUSIVE` in the report. The first names a capability this
system does not have; the second names an attempt that came back empty. Reporting the
second while the first is present would understate the gap.

### Semantic loss, split honestly

| targets | treatment |
|---|---|
| `hml`, `json`, `graph`, `triples` | **gating.** These views claim to *be* the semantic object. Loss here blocks `VERIFIED`. |
| `latex`, `english`, `lean`, `stan`, `sympy` | **recorded, not gating.** These are lowerings to foreign targets that are known not to express everything HML expresses. Blocking on them would make `VERIFIED` unreachable again for a reason unrelated to the obligation. |

Both sets are probed on every run and both appear in the report.

---

## 3. The nine supported obligation classes

Membership of `records.SUPPORTED_CLASSES` **is** the verification claim of this package.
A record outside it can never carry `DISCHARGED` — the dataclass refuses to construct
one.

| class | decided by | sound direction |
|---|---|---|
| `literal_refinement_bound` | interval entailment over declared refinement types, and over pinned literal values | positive (entailment); refutation is delegated |
| `closed_arithmetic_equality` | exact rational evaluation | both |
| `closed_inequality` | exact rational evaluation | both |
| `dimension_compatibility` | dimension re-derived from declared types, compared structurally against the asserted dimension re-parsed from source | both |
| `declared_signature_conformance` | arity and parameter-type re-check at every call site | both |
| `finite_set_membership` | exhaustion over a genuinely finite domain (`Bool`, bounded integers) | both — exhaustion really is exhaustive |
| `logical_consistency` | closed propositional evaluation; per-variable interval feasibility; joint model search | positive by witness, negative by empty intersection |
| `symbolic_identity` | SymPy 1.14.0, restricted operators, assumptions carried from declared types | positive only |
| `numerical_counterexample` | a fixed deterministic grid | **negative only — it can never discharge** |

### Soundness rules the code enforces

- **Exact or nothing.** Arithmetic is `Fraction`-exact. The moment a transcendental or a
  fractional power enters, the value is marked inexact, and an inexact value may never
  settle an equality. `sqrt(2)^2 == 2` is false in binary and true in mathematics; a
  verifier that cannot tell those apart is worse than no verifier.
- **Intervals over-approximate.** `interval_of(e)` returns a set guaranteed to *contain*
  every value `e` can take. Only two conclusions are drawn from it: containment in the
  target set (a discharge) and empty intersection with it (an unsatisfiability proof).
  `I ∩ S ≠ ∅` means nothing and is never used.
- **A failure needs a witness.** `FAILED` without a witness is refused by the schema. "The
  checker did not accept this" and "this is false" are different facts.
- **Sampling never proves.** The grid can refute a universal claim and can exhibit a model
  for a satisfiability claim. It can never establish a universal claim, and
  `NumericalCounterexampleChecker` structurally cannot return `DISCHARGED`.
- **Unfolding is definitional.** `const` values and non-parameterised `def` bodies are
  substituted by their own declared right-hand sides. Recursion is capped and cycles are
  detected.
- **A generic simplification is not a proof.** `checkers.partiality_risk` refuses a
  symbolic discharge unless every partial operation is *total* over the declared domains
  — see §3.1.

### 3.1 The partiality guard, and why it exists

This was a measured unsoundness, not a hypothetical one. `sympy.simplify(x/x - 1)` is
`0`, so before the guard the engine discharged `prove x / x = 1` for a free real `x` — a
claim that is **false at zero**. SymPy simplifies *generically*: it cancels on the
assumption that it is not standing on the measure-zero set where the operation is
undefined. That is correct behaviour for a CAS and the wrong basis for a proof.

A symbolic result is therefore believed only when:

| operation | requirement |
|---|---|
| `a / b` | `b` provably non-zero over its declared domain |
| `a ^ n`, `n` ≤ 0 | `a` provably non-zero |
| `a ^ n`, `n` fractional | `a` provably non-negative |
| `a ^ n`, `n` symbolic | refused |
| `log(a)` | `a` provably positive |
| `sqrt(a)` | `a` provably non-negative |
| `tan(a)` | refused — its poles are not an interval condition |

Failing the guard yields `UNSUPPORTED` with the operation and the domain that could not
be excluded, which is different from saying the claim is false. Declaring the divisor
`PositiveReal` makes the same identity total, and it then discharges.
`tests/verification/test_partiality.py` asserts both directions.

The `sqrt` and `log` rows are defence in depth: the builtin signatures
(`sqrt : NonNegativeReal -> NonNegativeReal`, `log : PositiveReal -> Real`) already make
a real-valued argument an `HML-T427` error before the engine sees it.

---

## 4. Obligation *mode* — the correction that matters most

The type checker labels `require`, a concept `invariant`, and a distribution's cross-role
constraint all as `kind == "constraint"`. **They do not mean the same thing**, and the
first implementation of this engine got it wrong: it read every obligation universally,
so `require x >= 0` for a free real `x` was "refuted" with the witness `x = -1` — a
confident, authoritative-looking failure on a perfectly good program.

The Lean backend already documents the correct reading, in its own source:

> an HML `require` is a constraint the model must satisfy, i.e. an obligation over free
> variables. Lean has no such statement form, so it is emitted as a theorem over those
> free variables. Read literally the theorem may be false (`require x >= 0` for a free
> real x is) …

So the engine recovers provenance from the module AST by span, and assigns a mode:

| provenance | mode | what discharging means |
|---|---|---|
| `require` | `SATISFIABLE` | exhibit a model |
| `assume` | `SATISFIABLE` | the hypothesis is consistent |
| `prove` | `UNIVERSAL` | prove it for every admissible value |
| concept `invariant` | `UNIVERSAL` | holds for every instance |
| distribution cross-role constraint | `UNIVERSAL` | holds for the declared parameters |
| refinement (`parameter_positivity`) | `UNIVERSAL` | entailed by the declared type |
| `check dimension` | `STRUCTURAL` | recomputation agrees |

An obligation whose producing statement cannot be identified defaults to `UNIVERSAL` —
the strict reading. Guessing `SATISFIABLE` would be the permissive guess, and the
permissive guess is the one that manufactures false passes.

Checkers are gated on mode. `NumericalCounterexampleChecker` refuses satisfiability
obligations (a counterexample refutes "for all", not "there exists");
`SatisfiabilityChecker` refuses universal ones. `tests/verification/test_modes.py` is the
regression test for the original defect and asserts both directions.

---

## 5. The vacuity problem, and how it is handled

`param sigma : PositiveReal` generates the obligation `sigma > 0`, which the declared
type entails by construction. Discharging it is **sound** and **definitional**: the
entailment is real, but it was generated by the very rule that satisfies it, so it can
never fail.

This is not hidden. Every such record carries `evidence["definitional"] = true`, and
`VerificationOutcome.substantive` is True only when at least one discharge is *not*
definitional. A module whose only discharges are definitional is still `VERIFIED` — the
conjunction in `_verdict` is about soundness, not interest — but:

- the H3 task filter **refuses** such a task, because passing it measures nothing;
- the offline evidence run reports `verified` and `verified_substantively` separately.

`examples/statistics/normal_distribution.hml` is exactly this case: `VERIFIED`, not
substantive.

---

## 6. What is refused, by name

`task_subset.EXCLUDED_DOMAINS` lists these before any task is examined, each with what
would admit it:

1. **quantification over infinite domains** — no decision procedure for real arithmetic
   is implemented, and no proof assistant is usable on this machine;
2. **probability and distributions** — no checker can express a claim about a
   `Distribution` or a `RandomVariable`;
3. **integration, limits, differentiation** — v0 has no surface syntax for them;
4. **linear algebra over indexed terms** — the evaluator refuses indexing and `@`;
5. **dimensioned numeric comparison** — the numeric value of a `Quantity[Length]` is
   unit-relative, so comparing it against a bare literal is not well posed;
6. **concept transforms and abstract properties** — an invariant calling a transform
   quantifies over every instance, and no instance is available.

Publishing these is not a formality. A filter that silently keeps only the tasks the
verifier happens to handle makes H3 unfalsifiable: whatever the model does, the retained
subset is the one where the machinery works, and the result generalises to nothing.

---

## 7. The H3 apparatus

### 7.1 Supported task subset — `evaluation/m3/verification/task_subset.py`

A task is admitted only when its expected solution: compiles · raises no obligation
outside an implemented class · reaches `VERIFIED` · is `substantive` · and is handed
identically to both arms. `assert_parity` raises unless the no-feedback and feedback arms
received the same task ids **and** the same problem text — H3 varies feedback only, and a
differing problem makes the arms incomparable.

`SubsetReport` carries the admitted set, the excluded set, the reason for every exclusion,
and the counts per reason.

### 7.2 Secondary process metrics — `evaluation/m3/verification/process_metrics.py`

For traces that are not globally verified:

- **verified-prefix length** — how many leading prefixes reach `VERIFIED`;
- **first failing step** — the index of the first prefix that does not;
- **fraction of locally discharged obligations** — across every step;
- **repair effect** — whether the failing step moved, which obligations were resolved,
  and **which failed after the repair that did not fail before**. A repair that fixes the
  reported defect and breaks something else is a `regression`, reported separately,
  because a net-positive average hides it.

These are secondary and the code enforces it: every metrics record carries the binary
verdict, and `assert_reported_with_endpoint` refuses a summary that quotes the process
numbers without it. Quoting a softer number instead of the endpoint is the shape a moved
goalpost takes.

### 7.3 Diagnostic leakage control — `evaluation/m3/verification/leakage.py`

```
A  broken trace only                       the floor
B  diagnostic only, no trace               the leak probe
C  broken trace + the correct diagnostic   the treatment
D  broken trace + a mismatched diagnostic  the well-formed-but-wrong control
```

- **useful** iff `repair(C) > repair(A)` **and** `repair(C) > repair(D)`;
- **leaks** iff `repair(B) > 0.20`;
- **admissible** iff useful, not leaking, and no guard finding.

Condition D uses a *real diagnostic from a different task* by default rather than a word
scramble: a scramble is trivially recognisable as noise, which would make D too easy to
beat and a useless diagnostic look useful. The `scramble` variant remains available and
the mode used is recorded in the report.

**The guard runs first.** `find_answer_leak` rejects a diagnostic that (a) embeds a
program whose canonical content hash equals the target's, (b) embeds any complete
compilable program at all, or (c) quotes four or more consecutive tokens of the target
that are absent from the broken trace — the "here is the corrected line" leak. A case
with a guard finding is **excluded from every condition**, not merely flagged, so a
leaking diagnostic cannot contribute to the number that is supposed to detect it.

A diagnostic must never contain a complete replacement program or the final answer. That
would convert H3 from a measurement into a tautology.

### 7.4 Offline evidence — `evaluation/m3/verification/run_offline.py`

```bash
.venv/bin/python -m evaluation.m3.verification.run_offline --out evidence.json
```

Deterministic: no clocks, no randomness, no network, **no model calls**. Two runs on the
same commit produce byte-identical JSON.
`tests/verification/test_no_sorry_path.py::test_the_engine_makes_no_model_call` asserts by
inspection that neither the engine nor this apparatus imports a client, a socket, or an
HTTP library.

---

## 8. Measured state (this commit, this machine)

| measurement | value |
|---|---|
| non-illustrative examples under `examples/` that compile | 15 |
| of those, `VERIFIED` | **10 (66.7 %)** |
| of those, `VERIFIED` **and** substantive | **6 (40.0 %)** |
| not verified | 5, all `UNSUPPORTED` — quantifier-scope and concept-transform cases |
| fixtures | 18; every one matches its declared verdict |
| H3-admitted fixtures | 8 of 18 |
| obligation classes exercised across fixtures | 9 of 9 |

The 5 unverified examples are the honest answer, not a gap to be closed by widening the
subset: `examples/logic/quantifier_scope.hml` asserts a true statement over the reals and
a false one, and neither is decidable by anything implemented here.

---

## 9. Integration — one decision left to the Lead

`src/hamiltonian_lang/verification/obligations/federation.py` implements the
`Verifier` protocol of `src/hamiltonian_lang/improvement/verification.py` **from the
outside**. That file is not modified by this package.

Registering the adapter in `default_federation()` does **not**, on its own, let
`classify` return `VERIFIED`. `classify` returns `INCONCLUSIVE` whenever any result
carries `obligations_remaining`, and `TypeCheckVerifier` unconditionally reports every
collected obligation as remaining — correctly, in isolation: the type checker really has
not discharged them.

Making the federation reach `VERIFIED` requires one deliberate edit inside
`improvement/verification.py`, and there are two clean options:

1. `TypeCheckVerifier` consults this engine and reports only the *undischarged*
   obligations as remaining; or
2. `classify` treats an obligation as remaining only when **no** verifier discharged it.

Both change a file this package does not own, so neither is made here.
`tests/verification/test_federation_adapter.py` pins the current behaviour so the choice
is taken deliberately rather than drifted into. Until it is taken, the reachable endpoint
is `hamiltonian_lang.verification.obligations.verify_source`, which applies the same
four-part conjunction end to end and is what the H3 harness measures.

---

## 10. Known limitations

1. **Definitional discharges cannot fail.** A `parameter_positivity` obligation is
   generated by the declared type and re-derived from it. Sound, labelled, and excluded
   from the H3 task set — but it is not evidence of anything.
2. **`DeclaredSignatureChecker` reads `Expr.type_`** for argument types, which is the
   type checker's own answer. Independence is therefore partial, and every such record
   carries `evidence["reads_synthesised_argument_type"] = true`. Arity and the
   subtyping decision are re-derived.
3. **The sample grid is finite.** Constraints whose models lie far from both the generic
   grid and the constraint's own constants will report "no model found", which is
   `UNSUPPORTED`, not a failure. Widening the grid changes power, never soundness.
4. **SymPy is the trusted component.** `simplify(l - r) == 0` is taken as a proof of
   identity, subject to the partiality guard of §3.1. SymPy 1.14.0 is pinned in the
   checker version string so a change is visible in the evidence. The guard covers
   partiality; it does not cover a hypothetical simplification bug in SymPy itself.
5. **Multiplication of unbounded intervals falls back to `UNBOUNDED`.** Sound, and it
   costs power: `sigma^2 > 0` for `sigma : PositiveReal` is not discharged by intervals
   (SymPy discharges it instead).
6. **Concept parameters are modelled by name.** A concept `parameter` with a declared
   refinement type contributes a domain when the name is unused at module level. A
   deliberate collision could shadow it; the resolver's scope depth is not consulted.
7. **The leakage harness has been exercised only against scripted responders.** It tests
   the *harness*, not any model. A live run is the Lead's decision to authorise.

---

## 11. Reproducing

```bash
.venv/bin/python -m pytest tests/verification -q
.venv/bin/python -m evaluation.m3.verification.run_offline
.venv/bin/ruff check src/hamiltonian_lang/verification tests/verification evaluation/m3/verification
.venv/bin/mypy src/hamiltonian_lang
```
