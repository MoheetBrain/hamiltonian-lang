# HML v2 — audit rerun

**Status: measurement.** Every number here was produced by compiling real HML source
through `hamiltonian_lang.compile_source`. No model was called. Nothing in
`/Users/moheet/hml_audit_worktree` was modified.

| | |
|---|---|
| instrument | `audit/language_comparison` @ `b1ac7bf` (read-only) |
| BEFORE tree | `/Users/moheet/hml_audit_worktree/src` @ `b1ac7bf` — the audited SHA |
| BEFORE tree (2) | `/Users/moheet/hamiltonian_lang/src` @ `3dd4216` — v1 HEAD, the V2 branch point |
| AFTER tree | `/Users/moheet/hml_v2_worktree/src` @ `f0e3340` — D-025 + D-026 + D-027 |
| interpreter | `/Users/moheet/hml_v2_worktree/.venv/bin/python` (3.14.6) for **every** run |
| workspace | `/Users/moheet/hml_v2_worktree/audit_rerun/` |

One interpreter drives all runs; the compiler under test is selected only by
`HML_PROBE_SRC`, so a Python difference cannot be mistaken for a language difference. Each
run records the resolved `hamiltonian_lang.__file__` to
`runs/<label>/language_comparison/logs/ATTRIBUTION.txt` before measuring, and the three
supplementary suites embed it in their JSON output. All five runs were executed twice and
produced identical figures.

---

## 0. The one thing to read first

Three of the nine metrics have a **reading problem**, and pretending otherwise would make
this report useless. Stated plainly:

1. **The headline coverage gain depends on rewriting probes.** Nine of the eleven
   previously-zero capabilities needed their probe respelled, plus one more to repair a
   regression: ten critical-atom probes in total, out of 64. V2 changed the surface
   spelling of most of what it closed (`expectation(X)` not `E[X]`, `{x : T | P}` not
   `{x : T . P}`, typed binders in `limit`/`derivative`/`integral`).
   Under the **unmodified** probes V2 scores **82.8% / 8 zeros**. Under **idiom-corrected**
   probes it scores **96.9% / 0 zeros**. Both are reported. The corrections were run
   against v1 as a control and bought v1 **nothing** (79.7% → 79.7%, 11 zeros → 11 zeros),
   which is the only reason the corrected figure is defensible at all.
2. **The published BEFORE compositional closure of 0.615 does not reproduce.** The audit's
   own committed artefact at `b1ac7bf` records **9 of 13 = 0.692**. Details in §4.
3. **Two BEFORE figures were never probe-derived.** The 0/19 transformation matrix and the
   8/13 · 5/13 epistemic matrix are hand-authored literals in
   `tools/build_hml_matrices.py`. They were re-derived here by execution; the transformation
   figure reproduced exactly, the enforcement figure did not (§6, §7).

---

## 1. Reproduction

```bash
# 1. copy the instrument (read-only source) into the rerun workspace
mkdir -p /Users/moheet/hml_v2_worktree/audit_rerun/runs
for L in A_before_b1ac7bf B_v1head_3dd4216 C_after_f0e3340 D_after_idiom E_v1head_idiom; do
  mkdir -p /Users/moheet/hml_v2_worktree/audit_rerun/runs/$L/language_comparison
  cp -R /Users/moheet/hml_audit_worktree/audit/language_comparison/{ontology,tools,methodology} \
        /Users/moheet/hml_v2_worktree/audit_rerun/runs/$L/language_comparison/
done

# 2. apply the two harness patches (§9.1) and the seventeen idiom corrections (§9.2)
/Users/moheet/hml_v2_worktree/.venv/bin/python \
  /Users/moheet/hml_v2_worktree/audit_rerun/apply_idiom_corrections.py

# 3. the five runs
audit_rerun/run_suite.sh A_before_b1ac7bf /Users/moheet/hml_audit_worktree/src
audit_rerun/run_suite.sh B_v1head_3dd4216 /Users/moheet/hamiltonian_lang/src
audit_rerun/run_suite.sh C_after_f0e3340  /Users/moheet/hml_v2_worktree/src
audit_rerun/run_suite.sh D_after_idiom    /Users/moheet/hml_v2_worktree/src
audit_rerun/run_suite.sh E_v1head_idiom   /Users/moheet/hamiltonian_lang/src

# 4. the three supplementary suites, per tree
PY=/Users/moheet/hml_v2_worktree/.venv/bin/python
cd /Users/moheet/hml_v2_worktree/audit_rerun
for s in A_before_b1ac7bf:/Users/moheet/hml_audit_worktree/src \
         B_v1head_3dd4216:/Users/moheet/hamiltonian_lang/src \
         C_after_f0e3340:/Users/moheet/hml_v2_worktree/src; do
  L=${s%%:*}; S=${s#*:}
  HML_RUN_LABEL=$L HML_PROBE_SRC=$S $PY probe_transformations.py
  HML_RUN_LABEL=$L HML_PROBE_SRC=$S $PY probe_epistemic_enforcement.py
  HML_RUN_LABEL=$L HML_PROBE_SRC=$S $PY probe_v2_backends_and_level3.py
done
```

### 1.1 The ontology is unmodified

`shasum -a 256` over the originals and over all five copies:

| file | sha256 | copies |
|---|---|---|
| `ontology/MATHEMATICAL_REASONING_ONTOLOGY_V1.json` | `a10645a414296363b2a8206b4b5ad5331c2486f0531f40519f13bbb3837cf7c4` | identical in all 5 |
| `ontology/COMPOSITION_TESTS.json` | `334bc3f26fbf01bbf25b9373f8be2e71c0bf700ad4becd7e5388e5b11decff4f` | identical in all 5 |
| `ontology/ONTOLOGY_DEPENDENCIES.json` | `dcf23d9c0bc81fad1a350e45bc6720479623b1a367d6e562ae49a79b98647f47` | — |

Per-domain shards (unchanged, copied verbatim):
`A` `db2dd02b…` · `B` `33316b7f…` · `C` `8934bed9…` · `D` `f6a7eff5…` · `E` `73ae6800…` ·
`F` `add82355…` · `G` `71696f4c…` · `H` `e524b121…` · `I` `fd317013…` · `J` `aea6fec5…` ·
`K` `df4822f7…` · `L` `f016c4e8…` · `M` `3378a9e0…`

**486 atoms · 64 CRITICAL. Denominators unchanged throughout: 64 critical atoms, 13
composition specimens, 19 transformation forms, 13 epistemic states, 19 definedness
probes, 54 backend lowerings.**

### 1.2 Which tool files are byte-identical to the original

| file | A / B / C | D / E |
|---|---|---|
| `probe_critical_atoms.py` | **identical** `d9a9e15a…` | modified `1f4b8da4…` (§9.2) |
| `probe_composition.py` | **identical** `101fee4c…` | modified `25430dc3…` (§9.2) |
| `probe_definedness.py` | **identical** `dab4e863…` | identical |
| `probe_epistemic_extensibility.py` | **identical** `33ef0a14…` | identical |
| `build_coverage.py` | **identical** `6a85cb29…` | identical |
| `hml_probe.py` | harness patch `5f32f9c8…` (was `28cd4753…`) | same patch |
| `probe_backends.py` | harness patch `062b9411…` (was `0b2211c4…`) | same patch |

### 1.3 The audit tree was not written to

Re-hashed after every run: `ontology/MATHEMATICAL_REASONING_ONTOLOGY_V1.json` and
`ontology/COMPOSITION_TESTS.json` still carry the sha256 values of §1.1, and
`tools/hml_probe.py` `28cd4753…`, `tools/probe_critical_atoms.py` `d9a9e15a…`,
`tools/probe_composition.py` `101fee4c…`, `tools/probe_backends.py` `0b2211c4…` are
unchanged. Every file under `/Users/moheet/hml_audit_worktree` has an mtime of 06:00–06:54
on the rerun date, predating this session; no `git` command was run there beyond
`rev-parse` and `status`. The pre-existing `AM` entries in that worktree's index are the
audit's own uncommitted state and were not created here.

---

## 2. BEFORE / AFTER / DELTA

`AFTER-u` = V2 measured with the **unmodified** probes. `AFTER-c` = V2 measured with the
**idiom-corrected** probes. `v1-c` = the v1 baseline measured with the *same* corrected
probes — the control that says how much of the gain the rewrite bought by itself.

| metric | published BEFORE | reproduced BEFORE | AFTER-u | AFTER-c | v1-c control | target | verdict |
|---|---:|---:|---:|---:|---:|---:|:---|
| CRITICAL faithful (64/64 probed) | 79.7% | **79.7%** ✓ | 82.8% | **96.9%** | 79.7% | ≥ 95% | **HIT on AFTER-c, MISSED on AFTER-u** |
| CRITICAL zeros | 11 | **11** ✓ | 8 | **0** | 11 | 0 | **HIT on AFTER-c, MISSED on AFTER-u** |
| faithful of all probed atoms (78) | 76.9% | **76.9%** ✓ | 78.2% | 93.6% | 75.6% | — | +16.7 pp (AFTER-c) |
| compositional closure (13 specimens) | 0.615 | **0.692** ✗ | 0.615 | 0.692 | 0.615 | ≥ 0.85 | **MISSED** |
| transformation REPRESENTABLE (19) † | 0/19 | **0/19** ✓ | **7/19** | n/a | 0/19 | ≥ 15/19 | **MISSED** |
| transformation VERIFIABLE (19) † | 0/19 | **0/19** ✓ | **7/19** | n/a | 0/19 | — | +7 |
| transformation EXECUTABLE (19) † | 0/19 | **0/19** ✓ | **0/19** | n/a | 0/19 | — | no change |
| transformation PROVENANCE (19) † | 0/19 | **0/19** ✓ | **7/19** | n/a | 0/19 | — | +7 |
| epistemic states expressible (13) † | 8/13 | **8/13** ✓ | **8/13** | n/a | 8/13 | — | **no change** |
| epistemic states enforced (13) † | 5/13 | **4/13** ✗ | **5/13** | n/a | 4/13 | — | +1 |
| definedness probes changed (19) | — | — | **0/19** | 0/19 | — | — | **no change** |
| extensibility probes changed (9) | — | — | **0/9** | 0/9 | — | — | **no change**, as expected |
| backend silent loss (54 lowerings) | 0 | **0** ✓ | **0** | 0 | 0 | 0 | **held** |
| backend silent loss, V2 constructs (45) | n/a | n/a | **0/45** | n/a | n/a | 0 | **held** (new suite) |
| inference rules that accept-correct **and** reject-broken (16) | n/a | **0/16** | **16/16** | n/a | 0/16 | — | new capability |

† These rows come from purpose-written suites (`probe_transformations.py`,
`probe_epistemic_enforcement.py`) that have no unmodified/corrected split — the same file
runs against every tree — so the AFTER-c and v1-c columns do not apply. The v1-c column
shows the v1 result from that same file.

Supporting: `.venv/bin/python -m pytest -q` in the V2 worktree —
**6226 passed, 5 skipped, 7 xfailed, 7 xpassed, 0 failed** (exit 0, 40.94 s).

---

## 3. Critical coverage, per atom

`P` faithful primitive · `L` representable only by weakening the declared type ·
`0` not representable. `**` marks an atom whose verdict moved between BEFORE and AFTER-c.

| # | critical atom | dom | BEFORE `b1ac7bf` | AFTER-u `f0e3340` | AFTER-c `f0e3340` | v1-c control |
|---:|---|---|:---:|:---:|:---:|:---:|
| 1 | `LOGIC.APPLICATION` | A | P | P | P | P |
| 2 | `LOGIC.CONJUNCTION` | A | P | P | P | P |
| 3 | `LOGIC.DEFINITIONAL_EQUALITY` | A | P | P | P | P |
| 4 | `LOGIC.DISJUNCTION` | A | P | P | P | P |
| 5 | `LOGIC.EQUALITY` | A | P | P | P | P |
| 6 | `LOGIC.EXISTS` | A | P | P | P | P |
| 7 | `LOGIC.FORALL` | A | P | P | P | P |
| 8 | `LOGIC.FREE_VS_BOUND` | A | P | P | P | P |
| 9 | `LOGIC.FUNCTION_AS_OBJECT` | A | P | P | P | P |
| 10 | `LOGIC.IMPLICATION` | A | P | P | P | P |
| 11 | `LOGIC.INDEXED_FAMILY` | A | P | P | P | P |
| 12 | `LOGIC.NEGATION` | A | P | P | P | P |
| 13 | `LOGIC.NESTED_QUANTIFIER_ORDER` | A | P | P | P | P |
| 14 | `LOGIC.PREDICATE` | A | **L** | **L** | **L** | L |
| 15 | `LOGIC.PROPOSITION` | A | P | P | P | P |
| 16 | `LOGIC.SET_COMPREHENSION` | A | **0** | **0** | **P** ** | **0** |
| 17 | `LOGIC.SET_MEMBERSHIP` | A | **0** | **P** | **P** ** | **0** |
| 18 | `LOGIC.SUBSTITUTION` | A | P | P | P | P |
| 19 | `LOGIC.THEOREM_STATEMENT` | A | P | P | P | P |
| 20 | `LOGIC.TYPE_JUDGEMENT` | A | P | P | P | P |
| 21 | `LOGIC.VARIABLE_BINDING` | A | P | P | P | P |
| 22 | `NUM.INTEGER` | B | P | P | P | P |
| 23 | `NUM.NATURAL` | B | P | P | P | P |
| 24 | `NUM.ORDER_RELATION` | B | P | P | P | P |
| 25 | `NUM.REAL` | B | P | P | P | P |
| 26 | `NUM.VECTOR_OF_SCALARS` | B | P | P | P | P |
| 27 | `ALG.EQUATION` | C | P | P | P | P |
| 28 | `ALG.INEQUALITY` | C | P | P | P | P |
| 29 | `ALG.MATRIX` | C | P | P | P | P |
| 30 | `ALG.MATRIX_ARITHMETIC` | C | P | P | P | P |
| 31 | `ALG.MATRIX_SHAPE_TYPING` | C | P | P | P | P |
| 32 | `ALG.SYMBOLIC_VARIABLE` | C | P | P | P | P |
| 33 | `ANA.CONTINUITY` | D | **0** | **0** | **P** ** | **0** |
| 34 | `ANA.DERIVATIVE` | D | **0** | **0** | **P** ** | **0** |
| 35 | `ANA.DOMAIN_CODOMAIN` | D | P | P | P | P |
| 36 | `ANA.FUNCTION_REAL` | D | P | P | P | P |
| 37 | `ANA.INTEGRAL_DEFINITE` | D | **0** | **0** | **P** ** | **0** |
| 38 | `ANA.LIMIT` | D | **0** | **0** | **P** ** | **0** |
| 39 | `PROB.CONDITIONAL_DISTRIBUTION` | E | P | P | P | P |
| 40 | `PROB.CONDITIONAL_PROBABILITY` | E | **0** | **0** | **P** ** | **0** |
| 41 | `PROB.DISTRIBUTED_AS` | E | P | P | P | P |
| 42 | `PROB.DISTRIBUTION_OBJECT` | E | P | P | P | P |
| 43 | `PROB.EXPECTATION` | E | **0** | **0** | **P** ** | **0** |
| 44 | `PROB.FUNCTION_RETURNING_DISTRIBUTION` | E | P | P | P | P |
| 45 | `PROB.INDEPENDENCE` | E | **0** | **P** | **P** ** | **0** |
| 46 | `PROB.INDEXED_FAMILY_RV` | E | P | P | P | P |
| 47 | `PROB.JOINT` | E | **0** | **L** | **P** ** | **0** |
| 48 | `PROB.PROBABILITY_MEASURE` | E | P | P | P | P |
| 49 | `PROB.RANDOM_VARIABLE` | E | P | P † | P | P |
| 50 | `STAT.ESTIMATOR` | F | P | P | P | P |
| 51 | `STAT.LIKELIHOOD_FUNCTION` | F | P | P | P | P |
| 52 | `STAT.POPULATION_VS_SAMPLE` | F | P | P | P | P |
| 53 | `DISC.SUMMATION` | G | **L** | **L** | **L** | L |
| 54 | `OPT.DECISION_VARIABLE` | I | P | P | P | P |
| 55 | `OPT.EQUALITY_CONSTRAINT` | I | P | P | P | P |
| 56 | `OPT.FEASIBLE_SET` | I | P | P | P | P |
| 57 | `OPT.INEQUALITY_CONSTRAINT` | I | P | P | P | P |
| 58 | `OPT.OBJECTIVE` | I | P | P | P | P |
| 59 | `EPIS.ASSERTION_VS_DEFINITION` | L | P | P | P | P |
| 60 | `EPIS.ASSUMPTION` | L | P | P | P | P |
| 61 | `EPIS.CONSISTENCY_CHECK` | L | P | P | P | P |
| 62 | `EPIS.CORRELATION_VS_CAUSATION` | L | **0** | **0** | **P** ** | **0** |
| 63 | `XFORM.CANONICALIZATION` | M | P | P | P | P |
| 64 | `XFORM.TYPE_INFERENCE` | M | P | P | P | P |

### 3.1 † A masked regression, reported because the matrix hides it

Row 49 reads `P` in every column, and that is **wrong for AFTER-u**. The critical-atom
probe for `PROB.RANDOM_VARIABLE` is `rv X : RandomVariable[Real]` + `require X = X`. Under
V2 that is `HML-T480` — `require` refuses an `Event` — so the probe's verdict is **FAIL**,
a straight regression from BEFORE's PASS. The coverage matrix does not show it because
`build_coverage.load_probe_evidence` resolves `PROB.RANDOM_VARIABLE` from the *composition*
suite's `BASE.RANDOM_VARIABLE` probe (sorted glob order puts `HML_COMPOSITION_PROBES.json`
first), which still compiles clean. This is a property of the instrument, not of V2, and it
existed before this rerun.

Two further regressions under AFTER-u, both traceable to the same `Event` barrier and both
**deliberate** per `EXPRESSION_COVERAGE.md` §3:

| probe | BEFORE | AFTER-u | code |
|---|---|---|---|
| `COMP.MATRIX_VALUED_RV` (`require S = S`) | ok | **not ok** | `HML-T480` |
| `RT.STOCHASTIC_PROCESS` (`require W = W`) | ok | **not ok** | `HML-T480` |
| `PROB.STOCHASTIC_PROCESS` atom code | P | **L** | `HML-T480` |

The barrier is defensible — sure equality of two random variables is not a proposition —
but it is a **breaking change that costs measured coverage under the audit's own probes**,
and the audit instrument scores it as loss. Both readings are in the table.

### 3.2 What is still not `P` under the most favourable reading

Two CRITICAL atoms remain `L` in every column, i.e. V2 did not touch them:

* `LOGIC.PREDICATE` — `var P : Predicate[Real]` + `require forall x : Real . P(x)` →
  `HML-T470`. The documented workaround is `Function[Real -> Bool]`.
* `DISC.SUMMATION` — `sum(i, 1, 10, i)` → `HML-T426` (`sum` takes 1 argument, 4 given).
  There is no indexed summation binder.

Non-critical atoms still short: `LOGIC.EXISTS_UNIQUE` `0` (HIGH, `HML-L101`),
`ANA.PIECEWISE` `0` (HIGH, `HML-P204`), `NUM.COMPLEX` `L` (HIGH, `HML-T440`).

### 3.3 Per-domain faithful coverage, probed atoms only

| domain | atoms | probed | BEFORE faithful | AFTER-c faithful |
|---|---:|---:|---:|---:|
| A_FOUNDATIONS_LOGIC | 56 | 23 | 82.6% | 91.3% |
| B_NUMBER_SYSTEMS | 30 | 7 | 85.7% | 85.7% |
| C_ALGEBRA | 46 | 9 | 100% | 100% |
| D_ANALYSIS | 48 | 7 | 28.6% | **85.7%** |
| E_PROBABILITY | 50 | 14 | 57.1% | **100%** |
| F_STATISTICS | 44 | 3 | 100% | 100% |
| G_DISCRETE | 31 | 1 | 0% | 0% |
| H_GEOMETRY_TOPOLOGY | 30 | **0** | `NOT_MEASURED` | `NOT_MEASURED` |
| I_OPTIMIZATION | 32 | 5 | 100% | 100% |
| J_SCIENTIFIC_UNITS | 25 | 3 | 100% | 100% |
| K_NUMERICAL | 31 | **0** | `NOT_MEASURED` | `NOT_MEASURED` |
| L_REASONING_EPISTEMICS | 25 | 4 | 75% | 100% |
| M_TRANSFORMATIONS_INFERENCE | 38 | 2 | 100% | 100% |

These are percentages over 78 probed atoms out of 486. **They are not whole-ontology
coverage and must not be quoted as such.** Two domains have zero probed atoms, which is why
ladder criteria 2.1 and 3.1 are `NOT_ASSESSED` rather than PASS or FAIL (§8).

---

## 4. Compositional closure — the published BEFORE does not reproduce

Measure: fraction of the 13 `group="composition"` probes that compile clean. Denominator
unchanged.

| run | tree | closure | failing specimens |
|---|---|---:|---|
| A — BEFORE, unmodified probes | `b1ac7bf` | **0.692** (9/13) | QUANT_X_PROB · PROB_X_UNITS · OBJECTIVE_OVER_PROBABILISTIC · LOCAL_ASSUMPTION_IN_SCOPE |
| B — v1 HEAD, unmodified | `3dd4216` | **0.692** (9/13) | same four |
| C — AFTER, unmodified | `f0e3340` | **0.615** (8/13) | the four, **plus** MATRIX_VALUED_RV |
| D — AFTER, corrected | `f0e3340` | **0.692** (9/13) | the four |
| E — v1 HEAD, corrected | `3dd4216` | **0.615** (8/13) | the four, plus MATRIX_VALUED_RV |

**The published 0.615 is contradicted by the audit's own committed evidence.**
`matrices/HML_COMPOSITION_PROBES.json` at `b1ac7bf` records
`hml_source_sha = b1ac7bf0625c…` and 9 of 13 composition probes with `ok: true`. The
`0.615` appearing in `README.md`, `report/FULL_AUDIT.md` §9, `report/EXECUTIVE_VERDICT.md`
and `hml/HML_MATURITY_PLACEMENT.md` row 2.10 is 8/13. The most likely cause is visible in
the FULL_AUDIT prose, which names five failures — "quantifier×RV, probability×units,
assumption×domain-restriction, objective×probabilistic quantity, **conditional
expectation**" — but conditional expectation is `RT.CONDITIONAL_EXPECTATION`, a member of
the *red-team* group, not of the 13-specimen composition group. A red-team failure was
counted into a composition denominator.

This is reported as a finding, not corrected silently. It does not change the Level 2
verdict: 0.692 is still below the 0.70 threshold.

**Net effect of V2 on closure: 0.692 → 0.692 (unchanged) on the corrected reading, and
0.692 → 0.615 (a regression) on the unmodified reading.** Against a target of ≥ 0.85 this
is the largest miss in the rerun. The four residual failures and why they persist:

| specimen | code | diagnosis |
|---|---|---|
| `COMP.QUANT_X_PROB` | `HML-T480` | `require forall t : Probability . X > 0.0` — the body is an `Event`, and `require` refuses events. Not a bug; the composition is genuinely unsayable in this shape. |
| `COMP.PROB_X_UNITS` | `HML-T411` | `rv H : RandomVariable[Quantity[Length]]` with `law H ~ Normal(...)` — Normal's support is `Real`. **`RandomVariable` still does not compose with `Quantity`.** D-026 did not address this. |
| `COMP.OBJECTIVE_OVER_PROBABILISTIC` | `HML-T411` | **A defect in the probe, not in either language.** `rv X : RandomVariable[Real]` with `law X ~ Bernoulli(prob := t)` — Bernoulli's support is `Bool`. Present identically in BEFORE and AFTER, so it cancels in the delta. Left uncorrected because correcting it would raise the closure figure, which is the direction that flatters the subject. |
| `COMP.LOCAL_ASSUMPTION_IN_SCOPE` | `HML-T427` | `assume x > 0.0` then `log(x)` — **still fails.** See §5. |

A disputed adjudication, recorded under the ladder's own anti-gaming rule: under
`COMPOSITIONAL_CLOSURE_FRAMEWORK.md` §6 the numerator is `|COMPOSES| + |REJECTED_CORRECT|`,
and `COMP.MATRIX_VALUED_RV`'s `HML-T480` is arguably `REJECTED_CORRECT`. Under that reading
AFTER-u is also 0.692. Neither reading reaches 0.70, so the level is the same under both.

---

## 5. `assume` — closed inside the kernel, still open at the type level

`DECISIONS.md` D-025 describes "a scoped refinement environment making `assume`
load-bearing", and `reasoning/refinement.py` states the goal as
`Γ = { x : Real, x > 0 } ⊢ x : PositiveReal ⊢ log(x) defined`. **Measured, that holds for
kernel-generated obligations and not for the type checker.**

```
module M
var x : Real
assume a0 : x > 0.0
def y := log(x)
-> error HML-T427: the argument of log has the wrong type   (found Real, expected PositiveReal)
```

Identical result for the unlabelled `assume x > 0.0`, for `require log(x) = log(x)`, and
for `sqrt` under `assume x >= 0.0`. `grep -rn RefinementEnv src/` finds it consumed in
`reasoning/check.py` only; `type_system/__init__.py` never sees it.

What *does* work, measured:

```
assume a0 : k != 0.0
assume a1 : y = 2.0 * x
derive d1 : y / k = 2.0 * x / k from a1 by divide_both_sides(by := k)   -> VERIFIED
```
and without `a0` the same derivation stops at `CHECKED` with one open obligation.

So the audit's **C-1** finding is **half closed**: an assumption discharges a side condition
raised by an inference rule, and does not discharge a domain restriction raised by the type
system. That is why `COMP.LOCAL_ASSUMPTION_IN_SCOPE` still fails and why ladder criterion
3.4 still fails.

---

## 6. Transformations

The BEFORE figure was a hand-authored literal. `audit_rerun/probe_transformations.py`
re-derives it by compiling one candidate program per transformation name, against the same
19-name taxonomy.

* REPRESENTABLE — a statement expresses "from A, by rule R, infer B" and it compiles clean.
* EXECUTABLE — the system computes the output rather than the author stating it.
* VERIFIABLE — **both** measured: the correct step reaches `DerivationStatus.VERIFIED`
  **and** a variant differing only in the stated conclusion is rejected.
* PROVENANCE — the artefact records premises, rule name and status.

| transformation | BEFORE (all four) | AFTER repr | AFTER verif | AFTER exec | AFTER prov | evidence |
|---|:---:|:---:|:---:|:---:|:---:|---|
| substitution | NO | **YES** | **YES** | NO | **YES** | `substitute`, VERIFIED; broken conclusion → `HML-R706` |
| rewrite | NO | **YES** | **YES** | NO | **YES** | `congruence(fn := exp)` |
| simplify | NO | NO | NO | NO | NO | no normalisation rule |
| rearrange | NO | **YES** | **YES** | NO | **YES** | `subtract_both_sides(by := k)` |
| cancel | NO | **YES** | **YES** | NO | **YES** | `divide_both_sides(by := k)` + `k != 0` obligation |
| factor | NO | NO | NO | NO | NO | no rule |
| expand | NO | NO | NO | NO | NO | no rule |
| differentiate | NO | NO | NO | NO | NO | `derivative(...)` is an expression; no rule differentiates a relation |
| integrate | NO | NO | NO | NO | NO | as above |
| change of variables | NO | NO | NO | NO | NO | no rule |
| case split | NO | NO | NO | NO | NO | `or` cannot be eliminated |
| contradiction | NO | **YES** | **YES** | NO | **YES** | `modus_tollens` only; **no reductio / `False`-elimination** |
| induction | NO | NO | NO | NO | NO | no rule, no inductive types |
| implication application | NO | **YES** | **YES** | NO | **YES** | `modus_ponens` |
| equality substitution | NO | **YES** | **YES** | NO | **YES** | `symmetry` + `transitivity` |
| probability conditioning | PARTIAL (hand) | NO | NO | NO | NO | `probability(A \| B)` is an expression; no conditioning **step** |
| Bayesian update | PARTIAL (hand) | NO | NO | NO | NO | `infer posterior` requests, does not represent |
| optimisation update | PARTIAL (hand) | NO | NO | NO | NO | objective statement, not a step |
| approximation | NO | NO | NO | NO | NO | no approximation relation |
| **totals** | **0/19** | **7/19** | **7/19** | **0/19** | **7/19** | |

Executed against `b1ac7bf` and `3dd4216`, the identical file scores **0/19 on every
column** — every `derive` fails at the parser with `HML-P204`/`HML-P205`. The published
BEFORE reproduces.

**Target ≥ 15/19 representable: MISSED at 7/19.** The gap is structural: the 19-name
taxonomy is dominated by symbolic-algebra and analysis rewriting (simplify, factor, expand,
differentiate, integrate, change of variables) and by proof structure (case split,
induction), and V2's closed 16-rule catalogue contains none of those by design
(`GRAMMAR_CONTRACT.md` §6 excludes unrestricted rewriting and proof search).

A caveat that does **not** change the number: the taxonomy also under-counts V2. Six of the
sixteen kernel rules — `and_intro`, `and_elim_left`, `and_elim_right`, `weaken_inequality`,
`add_inequality`, `multiply_inequality` — have no slot in the 19 names, so their capability
is invisible in this metric. Measured separately, **16 of 16 rules accept a correct step
and reject a variant differing only in the stated conclusion**:

```
symmetry transitivity add_both_sides subtract_both_sides multiply_both_sides
divide_both_sides substitute congruence modus_ponens modus_tollens and_intro
and_elim_left and_elim_right weaken_inequality add_inequality multiply_inequality
                                                          16/16 sound_check
```

`weaken_inequality` is the sharpest of these: `x > 0 ⊢ x >= 0` VERIFIES, and
`x >= 0 ⊢ x > 0` is rejected.

---

## 7. Epistemic expressivity and enforcement

Also hand-authored BEFORE; re-derived by `audit_rerun/probe_epistemic_enforcement.py`.
Each state gets an expressibility specimen and a **falsifier** — a program that must be
rejected if the state carries semantic weight.

| state | expressible BEFORE | expressible AFTER | enforced BEFORE (measured) | enforced AFTER | falsifier result |
|---|:---:|:---:|:---:|:---:|---|
| DECLARED | YES | YES | YES | YES | `const n : Natural = x` → `HML-T402` |
| DEFINED | YES | YES | YES | YES | duplicate `const c` → `HML-N303` |
| ASSUMED | YES | YES | **NO** | **YES (kernel only)** | assumption discharges a `divide_domain` obligation; **does not refine a type** (§5) |
| REQUIRED | YES | YES | NO | NO | `require 1.0 = 2.0` compiles clean in both |
| OBSERVED | YES | YES | INCONCLUSIVE | INCONCLUSIVE | accepting `obs + param` is arguably correct |
| PARAMETER | YES | YES | YES | YES | `infer posterior` with no law → `HML-S604` |
| GOAL | YES | YES | NO | NO | `prove 1.0 = 2.0` **still compiles clean in V2** |
| OBJECTIVE | YES | YES | YES | YES | objective over an unresolved name → `HML-N301` |
| CONJECTURED | NO | NO | n/a | n/a | `HML-P205` |
| REFUTED | NO | NO | n/a | n/a | `HML-P205` |
| APPROXIMATE | NO | NO | n/a | n/a | `HML-P204` |
| UNCERTAIN | NO | NO | n/a | n/a | `9.81 +- 0.02` compiles, but as `9.81 + (-0.02)` — scored NO |
| PROHIBITED_ASSUMPTION | NO | NO | n/a | n/a | `HML-P205` |
| **totals** | **8/13** | **8/13** | **4/13** | **5/13** | |

**Expressivity did not move: 8/13 → 8/13.** V2 added no new epistemic *state*; it added
mechanism inside states that already existed.

**Enforcement discrepancy with the published figure.** The published BEFORE is 5/13; my
measured BEFORE is 4/13. The published table counts `REQUIRED` as enforced on the strength
of the note *"obligation recorded, discharged by nothing"*. Executed, `require 1.0 = 2.0`
compiles clean with zero diagnostics in both trees, so by the falsifier standard used here
it is not enforcement. I report 4/13 and name the disagreement rather than adopting the
published number.

### 7.1 The v2-only `goal` / `derive` / `proved` path

Outside the fixed 13-state denominator, reported separately so it cannot inflate it:

| check | required | V2 result |
|---|---|---|
| a goal proved by a derivation the kernel REJECTED | reject | **reject** `HML-R706`, `HML-R710` |
| a goal proved by a derivation with an OPEN obligation | reject | **reject** `HML-R707`, `HML-R710` |
| a goal proved by a VERIFIED derivation | accept | **accept**, `GoalStatus.PROVED` |
| a goal used as its own premise (D-027's hole) | reject | **reject** `HML-R712`, `HML-R710` |
| `prove 1.0 = 2.0` | reject | **ACCEPTED — the audit's C-6 finding survives for `prove`** |

Four of five behave as required. The fifth is the audit's headline
*"`prove` proves nothing"*, and it is **still true of `prove`**. Measured: in V2
`prove 1.0 = 2.0` compiles clean, remains a `ProveStmt` (it does **not** become a
`GoalStmt`), the node carries **no `status` field at all**, and it emits one
`ProofObligation(kind='theorem')` that nothing discharges. `GRAMMAR_CONTRACT.md` §1 says
`prove` "now produces a `goal` with status `ASSERTED_UNCHECKED`"; that is the
pre-implementation contract and the shipped parser does not do it. **Recorded as a
divergence between the frozen contract and the implementation**, and as the reason the
audit's C-6 finding survives. The new `goal`/`derive`/`proved` path is sound; the old word
is still available and still means nothing.

---

## 8. Definedness, extensibility, backends

**Definedness: 0 of 19 probes changed.** Byte-identical verdicts and codes across BEFORE
and AFTER. `1.0 / 0.0`, `1.0 / x`, `tan(x)`, `0.0 ^ -1.0` and `v[10]` on `Vector[Real, 3]`
all compile clean with **zero obligations**. `sqrt`/`log` restrict by argument type, as
before. The audit's finding — *"the defect is the absence of a policy"* — is unchanged.

**Extensibility: 0 of 9 probes changed**, exactly as expected.

| probe | BEFORE | AFTER |
|---|---|---|
| `EXT.NEW_FUNCTION` (`def`) | ok | ok |
| `EXT.NEW_CONCEPT` (`concept`) | ok | ok |
| `EXT.NEW_TYPE` | `HML-P205` | `HML-P205` |
| `EXT.NEW_DISTRIBUTION` | `HML-P205` | `HML-P205` |
| `EXT.NEW_OPERATOR` | `HML-P205` | `HML-P205` |
| `EXT.NEW_DIMENSION` | `HML-P205`, `HML-D501` | same |
| `EXT.NEW_INFERENCE_RULE` | `HML-P205` | `HML-P205` |
| `EXT.IMPORT_MODULE` | `HML-P205` | `HML-P205` |

There is still no `import`, no user type, no user distribution, no user dimension and no
user inference rule. The rule catalogue being closed is a stated design decision
(`GRAMMAR_CONTRACT.md` §6), not an oversight; the absence of `import` is not.

**Backends: 0 silent losses, held.** 54 lowerings across 9 registered backends
(`english graph hml json latex lean stan sympy triples`), identical BEFORE and AFTER: 0
silent losses, 7 rows `faithful=True` disclosed only by a blanket note, 0 crashes.

The original specimens contain no V2 construct, so that result says nothing about the new
forms. A supplementary suite lowers five V2-carrying modules through all 9 backends using
the *same* silent-loss definition: **0 silent losses in 45 lowerings.**

Coverage of the suite, stated so it is not overclaimed: the five specimens exercise ten of
the eleven new expression forms (`expectation` `probability` `joint` `independent` `in`
`{…|…}` `limit` `derivative` `integral` `continuous` `correlated` `associated` `causes`;
**`variance` and the conditional variants of `expectation`/`probability`/`independent` are
not in these specimens**) and four of the five new statement forms (`assume`-labelled,
`derive`, `goal`, `proved`; **`obligation` and `discharge` are not**).

Measured per target: `latex` weakens and declares (2–5 records per specimen); `lean` 3–14,
`stan` 4–11 and `sympy` 3–8 drop and declare; `english` discloses by blanket note; `hml`
and `json` report `faithful=True` with zero unsupported records on all five; `graph` and
`triples` report the three reasoning statements as unsupported (`faithful=False`,
3 records) rather than emitting them silently.

---

## 9. PROBE CHANGES

Two harness changes affecting *which* compiler is measured, and seventeen probe-text
changes affecting *what* is written. Both are listed in full. The C-run (`AFTER-u`) uses
**zero** probe-text changes.

### 9.1 Harness — `hml_probe.py` and `probe_backends.py`

Applied to all five copies. Does not touch any probe source string.

```diff
 AUDIT_ROOT = Path(__file__).resolve().parents[3]
-sys.path.insert(0, str(AUDIT_ROOT / "src"))
+import os
+_SRC = os.environ.get("HML_PROBE_SRC") or str(AUDIT_ROOT / "src")
+sys.path.insert(0, _SRC)
```

Justification: the rerun must execute the same probe text against three source trees. The
original line pins the tree to the directory layout. Default behaviour is unchanged.

`probe_backends.py` additionally redirects its output from
`AUDIT_ROOT / "audit/language_comparison/matrices/…"` to
`Path(__file__).parents[1] / "matrices" / …`, so each run writes into its own copy instead
of into the read-only audit tree.

### 9.2 Probe text — seventeen changes, D and E runs only

Applied by `audit_rerun/apply_idiom_corrections.py`, which asserts each fragment occurs
exactly once and fails loudly otherwise. **The identical seventeen changes were applied to
the v1 baseline (run E) as the control.** Ten are in the critical-atom suite; seven are in
the composition suite, of which only one (`COMP.MATRIX_VALUED_RV`) touches the closure
denominator.

| # | probe | old | new | justification |
|---:|---|---|---|---|
| 1 | `LOGIC.SET_COMPREHENSION` | `def T := { x : Real . x > 0.0 }` | `def T := { x : Real \| x > 0.0 }` | separator is `\|` (`EXPRESSION_COVERAGE.md` §1). The `.` spelling parsed in **neither** tree; it was the audit's guess. |
| 2 | `ANA.LIMIT` | `def l := limit(f, 0.0)` | `def l := limit(f(x), x : Real -> 0.0)` | V2 binds an explicitly typed variable and takes an expression body. |
| 3 | `ANA.CONTINUITY` | `require continuous(f)` | `var D : Set[Real]` + `require continuous(f, on := D)` | continuity requires the domain with a role label. |
| 4 | `ANA.DERIVATIVE` | `def d := derivative(f, x)` | `def d := derivative(f(x), x : Real)` | typed binder. The original referenced an **undeclared `x`** and was ill-formed under v1 too (`HML-N301`). |
| 5 | `ANA.INTEGRAL_DEFINITE` | `def a := integral(f, x, 0.0, 1.0)` | `def a := integral(f(x), x : Real, 0.0, 1.0)` | same; same undeclared-`x` defect. |
| 6 | `PROB.EXPECTATION` | `require E[X] = 0.0` | `require expectation(X) = 0.0` | D-026 chose `expectation(...)` over `E[...]`; `E` must stay usable as a value name. |
| 7 | `PROB.JOINT` | `require joint(X, Y) = joint(X, Y)` | `def j := joint(X, Y)` | `joint` yields a `Distribution`; comparing two laws with `=` is refused by the pre-existing `HML-T428` barrier the project's own contract requires. `= itself` was an inert filler. |
| 8 | `PROB.CONDITIONAL_PROBABILITY` | `var A : Proposition` `var B : Proposition` `require Pr(A \| B) = 0.5` | `var A : Event` `var B : Event` `require probability(A \| B) = 0.5` | **two changes**, and the more aggressive of the two is the declared **type**. V2 makes `Event` and `Proposition` incomparable by design, so `probability()` of a `Proposition` is `HML-T482`. |
| 9 | `EPIS.CORRELATION_VS_CAUSATION` | `var x : Real` `var y : Real` `require x causes y` | `rv X : RandomVariable[Real]` `rv Y : …` `require causes(X, Y)` | **two changes**: infix → prefix, and the operands become random variables. V2 refuses a causal relation between constants (`HML-T495`). |
| 10 | `PROB.RANDOM_VARIABLE` | `require X = X` | `require probability(X = X) = 1.0` | **regression repair.** V2 types `X = X` as an `Event`; `require` refuses events. Unmodified result also reported (§3.1). |
| 11 | `COMP.MATRIX_VALUED_RV` | `require S = S` | `require probability(S = S) = 1.0` | same barrier. **This is the one correction that moves compositional closure** (0.615 → 0.692) and therefore the most consequential change in this file. |
| 12 | `RT.STOCHASTIC_PROCESS` | `require W = W` | `require probability(W = W) = 1.0` | same barrier. Red-team group; outside every headline denominator. |
| 13 | `RT.CONDITIONAL_EXPECTATION` | `require E[X \| t] = t` | `require expectation(X \| t) = t` | spelling. Red-team group. |
| 14 | `RT.INTEGRAL` | `def a := integral(f, 0.0, 1.0)` | `def a := integral(f(x), x : Real, 0.0, 1.0)` | typed binder. Red-team group. |
| 15 | `RT.DERIVATIVE` | `def d := derivative(f)` | `def d := derivative(f(x), x : Real)` | typed binder. Red-team group. |
| 16 | `RT.LIMIT` | `def l := limit(f, 0.0)` | `def l := limit(f(x), x : Real -> 0.0)` | typed binder. Red-team group. |
| 17 | `RT.SIGMA_ALGEBRA_CONDITIONING` | `require E[X \| Y] = Y` | `def m := expectation(X \| Y)` | spelling; and `E[X\|Y]` is a `RandomVariable` in V2, so `= Y` forms an `Event`. Red-team group. |

**What the control shows.** Running all seventeen against v1 `3dd4216` gives **79.7%
critical faithful and the same 11 critical zeros** — identical to v1 with the original
probes — and drops overall faithful-of-probed from 76.9% to 75.6%, because the corrected
probes are strictly *harder* for v1. **Not one atom is gained by the rewrite alone.** All
eleven closed zeros are therefore attributable to V2 and to nothing else; nine of them
additionally required the probe to be respelled, and two (`LOGIC.SET_MEMBERSHIP`,
`PROB.INDEPENDENCE`) closed with the audit's original probe text untouched.

**Where the corrections are weakest.** Changes 8 and 9 alter declared types, not just
spelling. A reader who rejects them should read `PROB.CONDITIONAL_PROBABILITY` and
`EPIS.CORRELATION_VS_CAUSATION` as unresolved, giving **60/64 = 93.8% and 2 critical
zeros** instead of 96.9% and 0 — still short of the 95% target on that reading. That
alternative is stated here rather than buried.

### 9.3 Two probe-authoring errors I made and corrected

Recorded because the audit's own honesty log records the same class of error.

* `probe_transformations.py` first passed `substitute` and `modus_tollens` their premises
  in the wrong order and scored both `REJECTED`. Corrected against each rule's own `shape`
  string (`a = b, P ⊢ P[a := b]`; `not Q, P implies Q ⊢ not P`). Both then VERIFY.
  Transformation representability went 5/19 → 7/19 as a result.
* `probe_epistemic_enforcement.py` first treated `add_inequality` as "add two
  inequalities". It is arity 1 with a `by` parameter. Corrected; rule soundness went
  15/16 → 16/16.

Both were errors in probes I wrote for this rerun, not in the audit's instrument.

---

## 10. UNRESOLVED / NOT MEASURED

The original audit was candid about its blind spots. They are almost all still blind.

| item | status |
|---|---|
| **408 of 486 ontology atoms** | `NOT_MEASURED`. Unchanged: 78 probed before, 78 probed after. Every percentage here is over probed atoms only. |
| **H_GEOMETRY_TOPOLOGY (30 atoms), K_NUMERICAL (31 atoms)** | `NOT_MEASURED`. Zero probes touch either domain in either run. This alone blocks ladder criteria 2.1 and 3.1. |
| **Semantic-density benchmark** | `NOT_MEASURED`. 60 specimens / 516 facts remain authored and unrun; no frozen tokenizer. Absent, not estimated. |
| **Model writability of V2** | `NOT_MEASURED`. The V2 constructs have never been put in front of a model. The only ACQ0 tranche is n=8, one model, closed `MEASUREMENT_INVALID`. No model was called for this rerun by instruction. |
| **Human writability** | `NOT_MEASURED`. No study exists. |
| **`COMPOSITION_TESTS.json` (48 specimens)** | `NOT_MEASURED`. The closure figure comes from the 13 executable composition probes, never from the 48-specimen suite, which has no runner. This was true of the original audit too. |
| **Julia / R / Wolfram / MATLAB comparison genomes** | `NOT_MEASURED`. Not installed; unchanged. |
| **Ladder 2.8 capture-avoiding substitution** | `PARTIAL`. `substitute` is documented to REJECT rather than perform a step needing capture avoidance, which is sound but is not a capture-avoidance implementation. Not separately probed here. |
| **Whether a backend that reports nothing on a V2 construct really rendered it** | `NOT_MEASURED` for `graph`, `json`, `triples`, `english`. The suite records the disclosure channel, exactly as the original probe does; deciding faithfulness mechanically would need a decompiler. |
| **`prove` / `require` obligations** | measured as generated (`result.obligations` is non-empty) and `NOT_MEASURED` as discharged — nothing discharges them. |
| **Internal inconsistency in the source audit** | `report/FULL_AUDIT.md` says 78 atoms probed; `hml/HML_MATURITY_PLACEMENT.md` row 2.1 says 71. My runs give 78. Recorded, not resolved. |

---

## 11. Maturity ladder verdict

Assessed against `/Users/moheet/hml_audit_worktree/audit/language_comparison/methodology/MATURITY_LADDER.md`.
Rule: `level = max{ n : every criterion of levels 0..n is PASS }`. `NOT_ASSESSED` blocks
exactly as `FAIL` does.

### Level 2 gate (Level 3 requires it via 3.1)

| # | criterion | BEFORE | AFTER | evidence |
|---|---|---|---|---|
| 2.1 | weighted coverage ≥ 0.60 overall, ≥ 0.40 per domain, all 13 domains | NOT_ASSESSED | **NOT_ASSESSED** | 408/486 unprobed; 2 domains have zero probes |
| 2.2 | no CRITICAL atom at `0` | FAIL (11) | **PASS** on AFTER-c (0) · **FAIL** on AFTER-u (8) | §3 |
| 2.3 | versioned schema | PASS | PASS | `spec/ir.schema.json`; suite green |
| 2.4 | canonical form semantics-preserving | PASS | **PASS** | re-measured: `∀∃ ≠ ∃∀`, `A@B ≠ B@A`, `causes(X,Y) ≠ causes(Y,X)`, `correlated` symmetric, `causes ≠ correlated` |
| 2.5 | round-trip | PASS | PASS | 6226 tests green incl. golden hashes |
| 2.6 | cross-domain type checking | PASS | **PASS** | re-measured: a `Matrix[Real,2,3] @ Matrix[Real,2,3]` shape error inside a module carrying `likelihood X \| t ~ Bernoulli(prob := t)` → `HML-T434` |
| 2.7 | machine-readable translation loss, no silent omission | PASS | **PASS** | 0/54 original + 0/45 on V2 constructs |
| 2.8 | alpha-equivalence | PASS (partial) | **PASS (partial)** | re-measured on all four new binders: renaming the bound variable in `integral`, `derivative`, `limit` and `{…\|…}` leaves the content hash **identical**, while changing the binder's *type* changes it. Still partial: capture-avoidance is untested because `substitute` REJECTS rather than performs such a step. |
| 2.9 | localised diagnostics | PASS | **PASS** | re-measured over 20 rejections (10 of them V2-only codes): **20/20** first errors carry code + line + column; threshold is 90% |
| 2.10 | compositionality ≥ 0.70 | FAIL | **FAIL — 0.692** | §4 |

### Level 3 — Mathematical Reasoning IR, criterion by criterion

| # | criterion | BEFORE | AFTER | evidence |
|---|---|---|---|---|
| 3.1 | all L2 hold, coverage ≥ 0.80 overall and ≥ 0.60 per domain | FAIL | **BLOCKED** | 2.10 FAILs; 2.1 NOT_ASSESSED; per-domain coverage unmeasurable for H and K |
| 3.2 | every CRITICAL **and HIGH** atom is `P`/`S`/`C`, no `B` or `L` | FAIL | **FAIL** | CRITICAL `L`: `LOGIC.PREDICATE`, `DISC.SUMMATION`. HIGH: `NUM.COMPLEX` `L`, `LOGIC.EXISTS_UNIQUE` `0`, `ANA.PIECEWISE` `0` |
| 3.3 | assumptions first-class **and scoped**; active set enumerable | FAIL | **FAIL** | no local assumption context exists (`scope … end` → `HML-P205`); `assume` is module-global; a module-level assumption does not refine a type (§5). The assumption *set* IS enumerable from the AST. |
| 3.4 | side conditions generated from partial operations | FAIL | **FAIL** | `1.0/x`, `1.0/0.0`, `tan(x)`, `0.0^-1.0` all compile clean, **0 obligations**. Obligations exist only for rules inside `derive`. |
| 3.5 | a semantics-preserving transformation **with a preservation check that fails on a broken variant** | FAIL | **PASS** | **16/16** rules: correct step → `VERIFIED`; variant differing only in the stated conclusion → `HML-R706`/`REJECTED` |
| 3.6 | epistemic status preserved through transformation (assumed / derived / **approximate** / observed / unknown) | FAIL | **FAIL** | assumed→derived is preserved and `require` is refused as a premise (`HML-R703`); but `approximate` does not exist as a status, so it cannot survive anything |
| 3.7 | approximation distinct from equality, carrying an error term | FAIL | **FAIL** | `~=` → `HML-P204`. `9.81 +- 0.02` compiles as `9.81 + (-0.02)` |
| 3.8 | representation queryable | PASS | **PASS** | executed: "which statements assume?" → `[a1]`; "which derivations and status?" → `[{d1, symmetry, VERIFIED}]`; "which goals and status?" → `[{g, PROVED}]`; `result.canonical/graph/hash/symbols` all available |
| 3.9 | compositionality ≥ 0.85, zero silent composition loss | FAIL | **FAIL — 0.692** | §4 |

### Verdict

**HML v2 is LEVEL 1 — DOMAIN DSL. Level 2 is not reached, and therefore neither is
Level 3.**

**Blocking criteria, named:**

* **2.10 / 3.9 — compositionality 0.692 < 0.70 (< 0.85).** The first failure in ladder
  order, and it fails under every reading of the probe set.
* **2.1 / 3.1 — coverage NOT_ASSESSED.** 408 of 486 atoms unprobed; two whole domains
  untouched. Cannot pass on the evidence that exists.
* **3.2** — two CRITICAL atoms at `L`, three HIGH atoms at `L`/`0`.
* **3.3** — no scoped assumption context.
* **3.4** — no obligation from any partial operation outside the derivation kernel.
* **3.6** — no approximate status to preserve.
* **3.7** — no approximation relation.
* On the **unmodified** probe reading, **2.2** also fails (8 critical zeros), and the
  ladder's criticality gate independently caps at Level 1.

**What did change.** Of the nine Level-3 criteria, **3.5 moved from FAIL to PASS** — the
one the ladder itself names as *the* distinguishing capability of Level 3, jointly with
3.4. That is a real result and it is the first time any HML criterion above the engineering
band has passed: 16 of 16 inference rules accept a correct step and reject a step that
differs only in its stated conclusion, and a goal cannot reach `PROVED` through a rejected
derivation, an open obligation, or itself. 3.8 held.

**What did not.** 3.4 — the other half of the pair — is unchanged. The audit's sentence
*"the gap to Level 3 is architectural"* is still accurate for obligations, scoping,
approximation and composition. V2 built a sound reasoning **kernel** and eleven **expression
forms**; it did not connect the refinement environment to the type checker, did not give
partial operations obligations, did not add a scoped assumption context, did not add an
approximation relation, and did not move composition.

The honest one-line summary: **V2 closed the coverage gap and opened the reasoning door;
it did not close the composition gap or the definedness gap, and the label is still
Level 1.**

---

## 12. Artefacts

```
audit_rerun/
  run_suite.sh                       the five-run driver
  apply_idiom_corrections.py         the seventeen changes of §9.2, self-verifying
  probe_transformations.py           §6
  probe_epistemic_enforcement.py     §7
  probe_v2_backends_and_level3.py    §8, §11
  runs/<label>/language_comparison/
      ontology/                      byte-identical copies, sha256 in §1.1
      tools/                         probe sources, sha256 in §1.2
      matrices/                      per-run probe output + coverage matrix
      logs/                          stdout of every probe, incl. attribution lines
  results/                           TRANSFORMATIONS_*.json EPISTEMIC_*.json V2SUPP_*.json
```
