# SE difficulty calibration — result and analysis

**Date:** 2026-08-07 · **SHA:** `3e3662b` · **Arm:** structured English only, no HML
**Model:** `gemma4:31b`, digest `6316f0629137…` verified against the pin before every stage
**Runtime:** temperature 0, 8192 completion allowance, one call per task, no review call
**Budget:** 13 of 13 calls used — **exhausted**

## Result

**10 valid observations, 10 correct.**

| stage | calls | valid | correct | tasks |
|---|---|---|---|---|
| CAL-1 | 3 | 3 | **3** | screening · constrained min · domain trap |
| CAL-2 | 5 | 5 | **5** | urn conditional · quantifier order · 2-constraint LP · units · extraneous roots |
| CAL-3 | 4 | **2** | 2 | reflecting walk · LP vertices *(2 truncated, see below)* |

**No usable difficulty region was found.** `NO_USEFUL_SE_HEADROOM_REGION_FOUND`.

## The two CAL-3 "failures" are not difficulty findings

Both returned `finish_reason = length` at exactly 8192 tokens. They were not wrong; they
were unfinished. `cal3_floor_identity` was part-way through a correct fractional-part
argument —

> `g(n) = (13/385)n − ({n/7} + {n/11} − {n/5})`, and the bracket is bounded between −1 and 2…

— when the budget ran out. Scoring these as incorrect would have manufactured headroom out
of a token limit, which is precisely the artifact the directive warned about after the
4096-vs-8192 effect in the previous benchmark.

They are recorded as **MEASUREMENT_INVALID at this budget**, not as failures.

**This was a task-design error on my part.** CAL-3 was meant to be *harder*; what I
actually built was *longer* — exhaustive counting problems that invite in-context
enumeration. Length is not difficulty.

## Why this matters more than it first appears

**The one axis on which this model failed is an axis on which the experiment would be
invalid anyway.** HML is a more verbose representation than prose. On a task whose failure
mode is running out of tokens, HML would truncate *sooner*. Building a corpus out of
length-limited tasks would bias the comparison against HML and produce a meaningless
result — a measurement of verbosity wearing the costume of a measurement of reasoning.

So the finding is not merely "no headroom found". It is: **the only difficulty axis
discovered is unusable for this hypothesis.**

## Why saturation keeps happening — three corpora, one pattern

| corpus | control | result |
|---|---|---|
| benchmark 1 | SE | ~93% |
| benchmark 2 | SE | 23/23 = 100% |
| this calibration | SE | 10/10 |

1. **The model is stronger than the task designs assume.** Three independently designed
   corpora saturated. That is now a property of the measurement approach, not bad luck.

2. **The semantic-trap genre is memorised.** Bayes screening, extraneous roots, an
   infeasible unconstrained optimum, quantifier order — these are canonical textbook
   patterns present in training data in enormous quantity. Novel *constants* do not defeat
   a memorised *pattern*. Every trap in CAL-1 and CAL-2 was of this genre, chosen precisely
   because they are the error classes HML targets, and every one was handled.

3. **The hypothesis needs errors that this model does not make.** "HML helps by catching
   semantic errors" presupposes semantic errors. On expressible mathematics, at a
   non-truncating budget, this model does not make them at a detectable rate.

## The structural tension that constrains every way forward

The families where this model is *plausibly* weak are the families where **HML has almost
no coverage**, measured in the same repository:

| family | HML ontology coverage |
|---|---|
| combinatorics | 0% |
| asymptotics | 0% |
| abstract algebra | 5% |
| sequences / series | 10% |
| topology | 10% |
| discrete optimisation | 10% |
| numerical analysis | 13% |

So the region where headroom might exist is largely the region HML cannot express. Any
plan that says "just use harder mathematics" runs into this immediately, and it should be
confronted before more compiler work is authorised rather than discovered afterwards.

## What was *not* measured

- **Whether a longer budget changes the picture.** 16384 tokens might convert both
  truncations into correct answers, or into genuine failures. Untested; it would cost
  calls, and the budget is exhausted.
- **Whether a weaker or smaller model shows headroom.** That changes the scientific
  question rather than answering it.
- **Whether multi-fact state-tracking tasks (bounded length, many interacting
  constraints) saturate.** This is the one untried design in the "hard, not long"
  direction, and it is the most promising remaining option.
- **Anything about HML itself.** No HML was involved at any point in this calibration.

## Recommendation

Do not spend another forty calls on the current task-generation approach; three corpora
have now saturated and the mechanism is understood. The decision of which way to go —
different difficulty axis, different model, larger budget, or accepting the negative
finding — is a scientific-direction decision and belongs to the user.

**Calibration responses are recorded in `evaluation/calibration/results/` and must never be
reused as paired-pilot observations.**
