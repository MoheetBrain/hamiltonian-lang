# HML_OBF — withdrawn as causal evidence

**Status:** `INVALID_AS_CAUSAL_EVIDENCE` / `WITHDRAWN_PENDING_CLEAN_RERUN`
**Date:** 2026-08-10 · **Applies to:** the `HML_OBF` arm of the causal-diagnosis scout,
frozen `2026-08-08` at `b87736a`, results in `CAUSAL_SCOUT.json` / `.jsonl`

**Nothing was deleted or re-run.** The experiment, its code, its raw records and its manifest
values are unchanged. `CAUSAL_DIAGNOSIS_MANIFEST.json` gained one additive `WITHDRAWN` key
pointing here; every original field is byte-identical. This document withdraws an
*interpretation*, not a measurement.

## The defect

`evaluation/arena/endpoints/causal_diag.py:48-58` defines the obfuscation map. It contains
five ordinary English words:

```
implies -> zeta5    iff -> zeta6    and -> zeta7    or -> zeta8    not -> zeta9
```

`causal_diag.py:121-125` — `render_question` — applies that map to the **question text**, not
only to the HML material:

```python
def render_question(w, condition: str) -> str:
    if condition == "SE":
        return _SE.question(w)
    q = _HML.question(w)
    return _obfuscate(q) if condition == "HML_OBF" else q
```

Re-derived from the frozen deterministic builder at `8bcd9a5`:

| condition | question as the model received it |
|---|---|
| `HML_BASIC` | `Is P6 necessarily true, necessarily false, or is it not determined by these assumptions?` |
| `HML_OBF` | `Is P6 necessarily true, necessarily false, zeta8 is it zeta9 determined by these assumptions?` |

**The clause naming the third answer option was destroyed.** `or` and `not` are the two words
that make "or is it **not** determined" readable as a third option, and both were substituted
with no key.

## Why this invalidates the inference

`HML_OBF` scored 2/6 — the lowest arm — and **answered `UNDETERMINED` on 6/6 items**. Those two
facts were read as a familiarity effect: unfamiliar surface syntax degrades reasoning.

The one arm that answered `UNDETERMINED` on every item is the one arm whose `UNDETERMINED`
option was the only one still legible as a sentence. Stored responses show the model treating
the substituted tokens as propositions rather than operators. Degraded reasoning and a
destroyed question predict the same observation, and this design cannot separate them.

Two further defects, recorded because they bear on how the condition should be rebuilt:

1. **The manifest contradicts its own code.** `CAUSAL_DIAGNOSIS_MANIFEST.json` describes
   `HML_OBF` as *"structure, labels, operators and nesting preserved"*. `implies`, `iff`,
   `and`, `or` and `not` are operators and all five are substituted. As implemented the
   condition does not measure a familiarity tax — it removes the logical vocabulary and
   supplies no key.
2. **No test covers `causal_diag`.** Endpoint A and B2 both carry prompt-construction audits.
   This endpoint has none, which is why a substitution reaching the question text was never
   caught.

One mitigation, for completeness: the `Answer with exactly one of: TRUE, FALSE, UNDETERMINED.`
instruction is built outside `render_question` and was **not** obfuscated. So the answer space
was still named — but the question's own third clause was not.

## What is withdrawn

* `HML_OBF` is **removed as positive evidence for H2 / the familiarity hypothesis.**
* `HML_OBF` is **removed as the justification for the LoRA adaptation experiment.**

## What is *not* concluded

**Familiarity is not refuted.** It remains **unresolved**, because the one experiment offered
in its support is confounded. Withdrawing evidence for a hypothesis is not evidence against it,
and nothing here licenses the opposite claim.

The scout's other arms are unaffected: `SE` 5/6, `HML_BASIC` 4/6, `HML_EPI` 3/6, `HML_VERIFY`
3/6 stand as recorded. The scout's CASE D verdict is unchanged, since `HML_OBF` scored below
`HML_BASIC` under either reading.

## Blast radius

`HML_OBF` was the **only** positive signature for H2. Every other experiment — B1 implication
direction, Endpoint A and its replication, B2 quantifier scope, the binder diagnostic, the
acquisition gate — cites it nowhere, so nothing else moves.

## Conditions for a clean rerun

1. Obfuscate the HML material **only**. `render_question` must not apply the map.
2. Do not map ordinary English words, or supply an explicit key for the ones mapped.
3. Add a prompt-construction audit for this endpoint, as Endpoint A and B2 have.
4. Reconcile the manifest's description with what the code does before freezing.

Until all four hold, `HML_OBF` carries no weight in any argument about representation
familiarity.
