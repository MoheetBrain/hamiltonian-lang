# Endpoint-B pilot composition — decision record

**Decided and written before any pilot call was made. Zero Endpoint-B AST or HML model
calls existed at the time of this decision.** That fact is what makes this calibration
rather than treatment-informed selection, and it is the whole reason the record is dated
ahead of the run.

## The decision

The first Endpoint-B representation pilot uses **12 fresh PILOT pairs**:

| contrast operator | pairs | why |
|---|---|---|
| `QUANTIFIER_ORDER` | **6** | control arm scored 2/4 — discriminating |
| `IMPLICATION_DIRECTION` | **6** | control arm scored 2/4 — discriminating |
| `OPERAND_ORDER` | **0** | control arm scored **4/4 — at ceiling** |

## Evidence, from the control arm only

Developmental selection ran `gemma3:4b` on 12 DEV pairs in **structured English only**. No
AST and no HML was ever shown. Per-operator pair BOTH-CORRECT:

```
OPERAND_ORDER          4/4   ceiling
QUANTIFIER_ORDER       2/4
IMPLICATION_DIRECTION  2/4
```

## Why dropping a saturated operator is not p-hacking

The distinction that matters is *what the composition was chosen from*:

- **Legitimate here:** the SE control tells us how hard each operator is *for this model*,
  independently of any representation. An operator the control answers perfectly cannot
  move under a representation manipulation — a pair that is already both-correct in the
  baseline has no room to improve, and its failure mode under a treatment would be noise
  rather than signal. Spending a third of a 12-pair pilot on such pairs buys nothing.
- **Would have been illegitimate:** choosing the composition after seeing how AST or HML
  performed. That selects the benchmark *for* the treatment and cannot be undone by
  analysis. It did not happen, and cannot have: the treatment arms have never been run on
  this endpoint.

This mirrors ordinary practice in psychophysics and item-response calibration — you
calibrate item difficulty on a control condition before assigning the manipulation.

## What this costs, stated plainly

- **Narrower construct coverage.** The pilot now measures sensitivity to two semantic
  distinctions, not three. A result generalises to quantifier order and implication
  direction, and says nothing about operand order.
- **`OPERAND_ORDER` remains untested under AST and HML.** If a representation effect exists
  specifically for arithmetic operand order, this pilot cannot see it. Recorded as a known
  blind spot rather than treated as settled.
- **The control's own numbers are noisy.** 4/4, 2/4 and 2/4 come from four pairs each. The
  ceiling reading for `OPERAND_ORDER` is the most robust of the three — a clean sweep — but
  the 2/4 figures are not precise estimates of anything.

## What is frozen alongside this

Unchanged from `FREEZE_FINAL_gemma3-4b.json`: model `gemma3:4b`
(`a2af6cc3eb7fa8be…`), temperature 0, `max_tokens` 8192, one stateless call per item,
system prompt and instruction hashes, level L3, the scoring rule (pair BOTH-CORRECT;
truncation unscored and drops the pair whole), and the generator and scorer versions.

**The pilot scorer is not relaxed.** The acquisition instrument's bare-answer repair applies
to the acquisition gate only; a scored reasoning answer still requires a declared `FINAL:`
line. `tests/arena/test_scoring.py::test_pilot_scorer_is_unchanged_by_the_repair` guards it.

Pairs are drawn from the `PILOT` band (500 000+), disjoint by construction from every
DEV_SELECTION and ACQUISITION seed used anywhere in this programme.
