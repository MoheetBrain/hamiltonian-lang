# V1 Gate Decision — HML-V1-CONCEPT-001 Phase 0

Evaluated against `docs/evaluation/HML_EVAL_001_PILOT_REPORT.md`, `EVAL_SPEC_v1.1`, and
tag `hml-v0-baseline`. Generation 0 = **105/105 paired cells, 0 unrun**.

## Phase 0 checklist

| requirement | status |
|-------------|--------|
| 1. verify frozen commit, corpus, prompt, evaluator, raw-output hashes | done — `EVAL_SPEC_v1.0.json`, superseded by `v1.1` with the defect record |
| 2. generation 0 as the primary 105-cell paired experiment | done |
| 3. generation 1 at temperature 0.7 as independent replication | done — §7 of the report |
| 4. `HML_EVAL_001_PILOT_REPORT.md` | done |
| 5. accuracy, semantic preservation, parser, verifier, tokens, latency, CIs, paired diffs | done; **verifier acceptance reported as NOT MEASURED** — no prover was ever invoked |
| 6. compare against English, structured English, LaTeX, direct formal, graph | done |
| 7. state whether compiler feedback produced a gain | done — yes, on encoding only |
| scorer not modified after inspecting comparative results | honoured — a defect found afterwards created `EVAL_SPEC_v1.1` with v1.0 preserved verbatim |

## The gate

Proceed to V1 only if at least one criterion is supported.

| # | criterion | verdict | evidence |
|---|-----------|---------|----------|
| 1 | improves final-answer accuracy | **NOT SUPPORTED IN THIS PILOT** | D−A, D−A′, D−B all **+0.000 with zero discordant pairs**; D−C +0.067 on a single pair, McNemar p = 1.0. **This is not a refutation** — see the correction below |
| 2 | improves semantic preservation | **NOT SUPPORTED** | no non-Hamiltonian arm produces a comparable encoding, so no comparison exists. Absolute fidelity 0.648 improves on nothing |
| 3 | materially reduces binding / scope / type / verification failures | **NOT SUPPORTED** | the checker does reject these, but that is a *compiler property* verified without a model. No arm-vs-arm reduction was measured, and verifier acceptance was not measured at all |
| 4 | compiler feedback gives a meaningful reliability gain | **SUPPORTED** | parse rate 73.3% → 85.7% (gen 0) and 50.0% → 93.3% (gen 1); encoding fidelity **+0.065, CI [0.006, 0.136]** — the pilot's only interval excluding zero, and it replicated across both generations |
| 5 | results expose a specific representational weakness V1 can directly test | **SUPPORTED** | (a) **27–50% of encodings do not compile** — the model cannot reliably write the language; (b) representation does not change what the model computes, which redirects the testable claim from *reasoning* to *error detection* |

### Verdict — GATE PASSED, on criteria 4 and 5 only

**What this licenses, and what it does not.**

The gate is passed on *reliability of encoding under compiler feedback* and on *an
identified weakness worth testing*. It is **not** passed on any reasoning improvement.
V1 therefore inherits a constrained mandate:

- V1 may claim to make errors **catchable**. It may **not yet** claim to make reasoning
  better, because that has not been adequately tested — see the correction immediately
  below.
- V1's primary outcome is **error detection** (precision and recall on injected errors),
  not answer accuracy.
- Criterion 5 cuts both ways. The weakness it identifies is that a language written
  unparseably 27–50% of the time is now being *made larger*. **Parse rate is the gating
  risk, not a footnote.**

**Hard gate carried into V1:** no V0-vs-V1 comparison may be reported until V1 parse rate
reaches ≥ 90%. A language the model cannot write is not being tested.

**Prediction recorded in advance,** so a surprise is visible as one: of the six V1 layers,
the epistemic-status layer is most likely to justify itself (its claims are type-level and
checkable with no model in the loop), and the inference layer least likely (checking
inference chains without a prover approaches re-implementing one, which the founding
directive forbids).


---

## CORRECTION — issued after this document was first committed

An earlier version of this file stated that criterion 1 "was tested and **refuted**". That
was an overclaim, and it **contradicted this project's own pilot report**, which states in
§9 that the zero differences "are **not** evidence that no difference exists." The report
was right and this document was wrong.

The precise and only defensible conclusion from HML-EVAL-001 is:

> **Zero-shot Hamiltonian did not improve answer accuracy on this small,
> low-discrimination pilot. The experiment was underpowered and had a severe ceiling
> effect.**

A design in which 14 of 15 problems were solved by nearly every arm, and whose minimum
detectable effect was roughly 33 percentage points, cannot refute anything. The correct
status of the central reasoning thesis is **unproven, not refuted**, and it remains so
until every failure condition in `docs/evaluation/HML_EVAL_002_PREREGISTRATION.md` is satisfied.

The pivot this error encouraged — treating the checker as the product rather than as one
component of a verifier-guided reasoning system — is withdrawn. The checker is the
mechanism tested by H3, not the objective.
