# Synthetic difficulty calibration — SYNTHETIC_STATE_COMPLEXITY_SATURATED

**Date:** 2026-08-07 · **Protocol:** CAL-S · **Arm:** structured English only, no HML
**Model:** `gemma4:31b`, digest `6316f0629137…` verified before every stage
**Runtime:** temperature 0, 8192 completion allowance, one call per task
**Budget:** 9 of 12 used — **3 deliberately unspent**

## Result

**9 valid observations, 9 correct, 0 truncations.**

| stage | level | families | valid | correct |
|---|---|---|---|---|
| CAL-S1 | L3 | algebraic · logic · quantifier | 3 | **3** |
| CAL-S2 | L5 | algebraic · mixed · logic | 3 | **3** |
| CAL-S3 | **L7** | algebraic · mixed · logic | 3 | **3** |

L7 is depth-16 dependency chains with 6 distractors, and 10-variable propositional worlds
with 26 constraints. Completions ran 900–2400 tokens against an 8192 allowance — nowhere
near the limit, so this is not a budget effect.

**`SYNTHETIC_STATE_COMPLEXITY_SATURATED`.**

## This is a different instrument from the previous calibration

The previous protocol measured canonical textbook traps and returned 10/10 valid. This one
measures machine-generated interacting state and returns 9/9. **The two must not be pooled
into one accuracy estimate** — they are different instruments. What they share is the
qualitative conclusion: neither found headroom.

## The generator lab is sound, and that matters for interpreting the result

Validation ran offline before any model call:

| family | n | deterministic | duplicate prompts | independent cross-check |
|---|---|---|---|---|
| ALGEBRAIC_DEPENDENCY_GRAPH | 119 | yes | 0 | **40/40** |
| FINITE_LOGIC_WORLD | 119 | yes | 0 | n/a |
| FINITE_QUANTIFIER_WORLD | 119 | yes | 0 | **40/40** |
| MIXED_STATE_COMPOSITION | 119 | yes | 0 | n/a |

The cross-checks re-parse the **rendered English** and re-derive the answer through a
second implementation, so a rendering bug would surface rather than be mirrored. Scorer and
extraction self-tests (15 + 5 cases) passed before the first call. Answers are
non-degenerate. No LLM judged anything.

So the saturation is a fact about the model, not an artifact of broken tasks.

## A limitation of my design, stated plainly

Difficulty here is **many easy steps**, not **individually hard steps**. A depth-16 chain
is tedious; each link is one multiply-add. A 26-constraint propositional world is large;
each constraint is a two-variable implication.

What was never generated is a family where a *single* step is hard — non-linear systems,
case-splitting search, problems with no forward-chaining route. It is possible that
interacting state is simply the wrong axis and this model is bounded by step *difficulty*
rather than step *count*. That is the strongest remaining criticism of this negative
result, and it is not answered by these nine calls.

## Options, with what each costs and gives up

**A. Weaker development model.** Immediately creates headroom. Only `gemma4:31b` is
installed, so this needs a download. It changes the question from "does HML help this
model" to "does HML help a weak model" — which is arguably the *right* developmental
question, since a notation that only helps models that already succeed helps nobody.

**B. Broaden the domain.** Note what was *not* generated: no probability-with-dependence
family, no geometry, no multi-step optimisation. But the structural tension recorded
earlier stands — the ontology probe found the families where this model is plausibly weak
(combinatorics 0%, asymptotics 0%, abstract algebra 5%, topology 10%) are the families
where **HML's own coverage is near zero**. Broadening the domain risks moving into
mathematics HML cannot express.

**C. Change the endpoint.** If accuracy has no headroom, accuracy is the wrong dependent
variable. HML's measurable claims might instead be about *auditability* (can a checker find
the error when one occurs), *token cost*, or *repair* under H3 — but H3 also needs errors
to repair.

**D. Accept the finding.** For this model, on mathematics HML can express, at a
non-truncating budget, there is no measurable accuracy headroom. That is a legitimate
scientific result and it is cheap to report.

## Accounting

| | |
|---|---|
| previous calibration | 13 calls · 10 valid · 10 correct · 2 truncations |
| synthetic calibration | **9 calls · 9 valid · 9 correct · 0 truncations** |
| total local Gemma calls, all protocols | **22** |
| **HML model calls** | **0** |

No HML acquisition call has been made or permitted. Composition remains 22/48 = 0.458 and
no compiler work was done under this directive, as instructed.
