# V1 Experiment Plan — V0 versus V1

Status: **PLAN**. Preregistered before V1 is implemented, so that the design cannot be
tuned to a result already seen.

Baseline: tag `hml-v0-baseline`, `EVAL_SPEC_v1.1`, 221 stored trials.

---

## 1. What the V0 pilot obliges this plan to fix

The pilot did not fail because the representation lost. It failed because the experiment
could not have detected a win:

| pilot defect | consequence | required fix |
|--------------|-------------|--------------|
| 14/15 problems correct in **every** arm | ceiling effect; minimum detectable effect ≈ 33 pp | corpus targeting **50–60%** baseline accuracy |
| n = 15 paired | McNemar needs ~5 discordant pairs for p < 0.05 | **n ≥ 60** paired problems |
| 27–50% of encodings did not compile | an encoding that does not compile demonstrates nothing | parse rate **≥ 90%** before any comparison is run |
| answer accuracy was the primary outcome | it measured what the model computes, not what the checker catches | primary outcome changes — see §3 |

**No V0-vs-V1 comparison may begin until the parse-rate gate is met.** A language the
model cannot write is not being tested.

## 2. Arms

| arm | representation |
|-----|----------------|
| V0-D | Hamiltonian V0, no feedback — *the preserved baseline* |
| V0-E | Hamiltonian V0 + compiler feedback |
| V1-D | Hamiltonian V1, no feedback |
| V1-E | Hamiltonian V1 + compiler feedback |
| A′ | structured English — retained as the scaffolding control |

A, B, C (plain English, LaTeX, Stan/Lean) are **not** re-run. The pilot already
established they are indistinguishable from V0-D on answer accuracy, and re-running them
would spend compute re-measuring a settled null.

A′ is retained because it was the *least stable* arm in the pilot (66.7% on replication)
and that instability is itself worth confirming.

## 3. Primary outcome — error detection, not answer accuracy

The pilot showed the representation does not change what the model computes. The
remaining defensible claim is that it changes **what can be caught**. So:

> **Primary outcome: does the checker reject encodings that misrepresent the problem, and
> accept those that do not?**

Reported as precision and recall over a labelled set of encodings:

- **Recall** — of encodings that genuinely misrepresent the problem, what fraction does
  the checker reject?
- **Precision** — of encodings the checker rejects, what fraction genuinely misrepresent
  it? (A checker that rejects everything has perfect recall and is useless.)

This is deterministic and needs no accuracy gain to be meaningful.

### Secondary outcomes

Answer correctness · encoding fidelity · parse success · repair count · tokens · latency.
All retained from `EVAL_SPEC_v1.1` so the two experiments remain comparable.

## 4. The V1-specific test set

Each new layer gets injected errors of its own kind. These are the cases V0 provably
cannot catch, so they are where V1 either earns its place or does not.

| layer | injected error | V0 behaviour | V1 must |
|-------|---------------|--------------|---------|
| L2 | divide by a quantity that may be zero | accepts | reject or obligate |
| L2 | square both sides, then treat as reversible | accepts | record a weakening |
| L2 | differentiate a function not differentiable on its domain | accepts | obligate |
| L3 | assert the converse of an established implication | accepts | leave pending or demand a counterexample |
| L3 | conclude via an invalid rule chain | accepts | reject |
| L4 | `prove(fail_to_reject(H0))` | accepts | **reject — type error** |
| L4 | use a p-value as a posterior probability | accepts | **reject — type error** |
| L4 | drop an `almost_sure` qualifier | accepts | reject |
| L4 | `with_high_probability` with no regime | accepts | reject |
| L5 | leave a goal open and conclude anyway | accepts | report the open goal |
| L5 | non-exhaustive case split | accepts | report the gap |
| families | call an estimate unbiased | accepts | **reject — type error** |

Each row needs **≥ 20 instances**, half genuine errors and half correct near-misses, so
precision is measurable and a reject-everything checker scores badly.

## 5. Preregistered hypotheses

| id | claim | null | falsified if |
|----|-------|------|--------------|
| **V1-H1** | V1 rejects the §4 error classes that V0 accepts | V1 detection rate ≤ V0 | recall < 30% on any layer's errors |
| **V1-H2** | V1's rejections are specific, not indiscriminate | precision ≤ 0.5 | precision < 0.7 on correct near-misses |
| **V1-H3** | V1's added surface does not degrade encoding fidelity | V1 fidelity < V0 fidelity | V1 fidelity is materially below V0's 0.648 |
| **V1-H4** | the model can write V1 as reliably as V0 | V1 parse rate < V0 | V1 parse rate below V0's, or below 90% absolute |
| **V1-H5** | compiler feedback helps V1 at least as much as V0 | no difference | V1-E − V1-D fidelity gain is not positive |

**V1-H4 is the one most likely to fail**, and it is the one to watch. V1 adds four layers
of surface area to a language the model already wrote unparseably 27–50% of the time.
Every added construct is another thing to get wrong.

## 6. Layer-by-layer stopping rule

Layers are evaluated **independently and dropped independently**. A layer that fails its
criterion (`spec/v1/semantic_objects.yaml::kill_criteria`) is deleted from V1, not
defended, and the remaining layers are re-measured without it.

The expected ordering by likelihood of survival, stated in advance so that a surprise is
visible as a surprise:

1. **L4 epistemic** — most likely to survive. Its claims are type-level and checkable
   without a model.
2. **L5 discourse** — likely; open-goal reporting is cheap and clearly diagnostic.
3. **L2 transformation** — uncertain; depends entirely on whether side conditions catch
   real errors rather than firing constantly.
4. **L3 inference** — least likely. Verifying inference chains without a prover is close
   to re-implementing one, which §22 of the founding directive forbids.

## 7. Compute

| item | value |
|------|-------|
| arms | 5 |
| problems | ≥ 60 |
| generations | 3 |
| calls | ≥ 900 |
| measured throughput | ~57–100 s/call on the pilot machine |
| estimated wall clock | **14–25 hours** |

The pilot's 15-problem run took ~5 h. This is 3–5× that and must be planned as a
multi-session, resumable run — the harness already checkpoints per trial.

## 8. What would make this worth doing, and what would not

**Worth continuing if:** L4 alone reaches ≥ 70% recall at ≥ 0.7 precision on the
statistical-negative and estimator/estimate classes. That is a genuinely useful checker
for machine-generated statistics, independent of any reasoning claim.

**Stop if:** V1's parse rate is below V0's, or no layer clears its kill criterion. In that
case the conclusion is that the representational programme does not pay, and the honest
output is the negative result plus a validated evaluation harness — which is more than
most projects of this kind produce.

**Explicitly not a success condition:** V1 producing more mathematician-sounding English.
The renderer is output. It is not evidence of anything.
