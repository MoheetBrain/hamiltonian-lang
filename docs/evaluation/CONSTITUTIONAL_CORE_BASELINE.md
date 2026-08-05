# Constitutional Core — Phase 0 baseline

HML-CONSTITUTIONAL-CORE-001 Phase 0. Every claim below was produced by running code on
2026-08-05, not by reading documentation. Where a probe contradicted a document, the probe
wins and the contradiction is named.

## Exact baseline

| | |
|---|---|
| commit | `967e95d` — *feat: enforceable Phase F4 freeze; 50-demo curriculum fits the slot* |
| branch | `hml-v1-concept-kernel` |
| tests | **3454 passed, 4 skipped, 1 xfailed** (10.44s at `-n 18`) |
| conformance | **PASS**, all 8 stages, no override |
| tree | dirty — uncommitted work from three Phase F agents, all of it passing |

The suite grew from 1531 at the last commit to 3454. The additional ~1900 tests come from
the F1/F2/F3 agents' uncommitted work. **Conformance passes on that partial work**, which
is why it is preserved rather than reverted.

---

## THE HYPOTHESIS REGISTER — read this first in a year's time

The project tests **three hypotheses that can come apart**. Conflating them is the single
most likely way to end up unable to say what went right or wrong.

| id | hypothesis | isolated by | status today |
|----|-----------|-------------|--------------|
| **H1** | representation as **input** improves the answer | vary the input, fix the output format | **UNTESTED** |
| **H2** | representation as **reasoning workspace** improves the answer | English input, Hamiltonian derivation *required* | **UNTESTED** |
| **H3** | **verifier-guided repair** improves the verified answer | same input and derivation, feedback added | **UNTESTED** |

**A win on H3 alone is a win for verifier-guided reasoning and must never be reported as a
win for the representation.** H3 can succeed while H1 and H2 fail; that outcome would mean
the compiler is valuable and the language is not, which is a real and publishable result —
but only if the three were kept apart from the beginning.

### What is already known, and what it does and does not mean

The HML-EVAL-001 pilot conflated all three. Its result was:

> Zero-shot Hamiltonian did not improve answer accuracy on this small, low-discrimination
> pilot. The experiment was underpowered and had a severe ceiling effect.

**Status of the thesis: UNPROVEN, NOT REFUTED.** 14 of 15 problems were solved by nearly
every arm; the minimum detectable effect was ~33 percentage points. That pilot is evidence
about *nothing in particular* with respect to H1/H2/H3, because no arm isolated any of them.

### Mechanical protections now required

Because prose reminders decay, the separation is enforced in the schema:

- `Episode.hypothesis_id` is a typed `H1 | H2 | H3 | NONE` value, never free text.
- Episodes with different `hypothesis_id` may not be aggregated into one statistic.
- `EvidencePackage.hypothesis` is typed, and the controller must refuse to advance a stage
  on evidence drawn from a hypothesis other than the one its gate names.
- Repair episodes are **H3 machinery** and are distinguishable by construction, not by
  convention.

**A diagnostic that leaks the final answer silently converts an H3 result into an
unmeasurable one.** That is why the diagnostic contract forbids the complete target
program, the final answer, and unrestricted replacement patches.

---

## F2/F3 ownership — resolved, and there was no conflict

I flagged a possible duplication earlier: both `evaluation/syntax_gate/` (F2) and
`evaluation/syntax_acquisition/` (F3) exist, and F2 shipped a `candidates.py`. **That
concern was wrong**, and the correction matters because deleting either side would have
destroyed working code.

F2's `candidates.py` is a **binding layer, not a second renderer**. It defines the
`SyntaxAdapter` protocol, the decidable feature vocabulary that makes Track A membership a
fact rather than a judgement call, and `SyntaxAcquisitionAdapter`, which converts F3's
`SyntaxCandidate` (`render(Module) -> str`, `parse(str) -> Module`) into the text-in,
verdict-out interface the harness needs. The split is exactly the one the directive
prefers.

**Measured, live:**

```
adapter_availability()  -> all four: available: SyntaxAcquisitionAdapter
resolve_adapters()      -> all four: SyntaxAcquisitionAdapter
```

**All four surfaces round-trip to hash-identical canonical objects:**

| example | base hash | A | B | C | D |
|---|---|---|---|---|---|
| `bayesian_coin` | `f79c553cca1adaa1` | MATCH | MATCH | MATCH | MATCH |
| `linear_regression` | `583109a8db26c6c8` | MATCH | MATCH | MATCH | MATCH |
| `kinetic_energy` | `25efff792d32ccf0` | MATCH | MATCH | MATCH | MATCH |
| `quantifier_scope` | `8250373bb23c814a` | MATCH | MATCH | MATCH | MATCH |

This is the fairness property the tournament depends on: **no candidate receives additional
mathematical information.**

**One early token-cost signal**, from rendering `bayesian_coin`:

| candidate | surface |
|---|---|
| A — v0 labelled linear | 237 chars |
| B — v1 labelled linear simplified | 256 chars |
| C — prefix / S-expression | 289 chars |
| D — constrained JSON / graph | **1907 chars** |

D is roughly **8x** the others in characters. Gate 2 caps reasoning-inclusive completion
cost at 2x structured English, so D starts at a substantial disadvantage that fidelity
would have to repay. This is a character count on one example, **not** a token measurement
and not a verdict.

---

## State of every load-bearing claim

### Confirmed implementation

| claim | evidence |
|---|---|
| conformance passes with >1500 tests | 3454 passed; `CONFORMANCE: PASS`, 8/8 stages |
| SymPy has a supported executable subset | 15/15 non-illustrative examples emit and **execute** |
| freeze tooling exists | `evaluation/syntax_gate_freeze.py`, `--write`/`--verify`, 22 tests |
| Ollama execution manifest exists | `docs/evaluation/EXECUTION_ENVIRONMENT.md`, measured |
| four syntaxes carry identical information | hash MATCH across four examples, table above |
| `lean_verify` is sound | verifies a core-only theorem; rejects `sorry`; rejects statement mismatch |

### Known failure

| claim | evidence |
|---|---|
| user-`def` calls enforce neither arity nor argument type | `f(1.0)` and `f(1.0,2.0,3.0,4.0)` on a 2-parameter `def` both compile clean |
| typed `def` bodies use contextual checking inconsistently | `const p : Probability = 0.5` ok; `def p : Probability := 0.5` -> `HML-T403` |
| concept novelty detection is defeated by respelling | 2 of 4 respellings **admitted**; byte-identical copies caught 4/4 |
| `PValue` exists in Python but not in HML | `param q : PValue` -> `HML-T440`; `def posterior_h0 : Probability := p_value` -> ok |

### Documented but absent

| document claim | reality |
|---|---|
| `semantic_objects.yaml` `kill_criteria.L4`: p-value conflation "Now closed" | closed in `v1/epistemic.py` (Python), **open in the language** |
| `type_system/__init__.py:234` docstring: bidirectional checker | 2 of ~12 expression positions route through `check` |
| `CLAUDE.md` rule 10: `tests/golden` compiles every `.hml` | was false until 2026-08-05; now enforced recursively |
| `GOAL.md` §3: minting admitted three copies via rename/vacuous-constraint/alias | those three are now **caught**; the hole moved to definition respelling |

### Unsupported

| capability | reason |
|---|---|
| general Lean verification | Mathlib absent; **and** the backend closes every obligation with `sorry` by design, so `lean_verify` rejects its own output before Lean runs |
| Stan compilation | `stanc` absent; no Stan artefact has ever been compiled by anyone |
| V1 layers from HML source | nothing on the `hml check` path imports `hamiltonian_lang.v1`; every V1 surface form is `HML-P205`, every V1 type name `HML-T440` |

### Partial

| capability | boundary |
|---|---|
| bidirectional checking | `Declaration.value` (`HML-T402`) and distribution role (`HML-T413`) only |
| dimensions | concrete dimensions enforced; `unify()` is single-variable only |
| Stan round-trip | a real content-hash oracle over a narrow subset; only Uniform/Binomial/Bernoulli survive |

---

## Scope note

Phase 1 repairs (1A function signatures, 1B contextual definition checking, 1C
source-language `PValue`) are **corrections to the intended contract**, not experimental
mutations. They happen before the constitutional baseline is frozen, and the `|ΔS|₀ = 1`
one-component rule applies only *after* that freeze.
