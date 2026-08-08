# The Representation Arena — design and pre-flight state

`arena-1.0.0` · scorer `arena-scorer-1.0.0` · built 2026-08-08 · **zero model calls made**

The arena tests one question: does HML provide a **representation-level** advantage over
(1) information-matched structured English and (2) a generic semantic JSON/AST — on the
*same* semantic worlds, with the *same* questions, scored by the *same* deterministic
oracles.

---

## 1. Why the difficulty lab could not simply be given a renderer

The signal-pivot handoff (§J) said to add a rendering layer to
`evaluation/h2/difficulty_lab/families.py`, emitting three views "of the *same* generated
structure".

**That generator does not keep the structure.** `_algebraic`, `_logic`, `_quantifier` and
`_mixed` build their English inline and return a `Specimen` holding `prompt` (a string),
`answer` and `metrics`. By the time a specimen exists, the dependency DAG, the constraint
set and the relation table have been discarded. There is nothing left to render a second
or third way.

The arena therefore rebuilds the same worlds **structure-first**, in
`evaluation/arena/worlds.py`. `difficulty-lab-1.0.0` is left byte-identical — its file
hashes are pinned in the handoff and the synthetic calibration results are recorded
against that version. The level ladder L1–L5 is copied, not imported, and
`tests/arena/test_worlds.py::test_levels_have_not_drifted_from_the_difficulty_lab` fails
if the two ever diverge.

---

## 2. Architecture

```
worlds.py        structure-first factory  ──►  World  (decls, facts, relation, query)
   │                                              │
   │  oracles.py re-solves every world from the finished fact set and
   │  `generate()` asserts it agrees with the generator's own arithmetic
   │                                              │
   └──────────────► renderers/ ──────────────────┤
                      english.py   (arm SE)      │  three pure functions of one structure
                      ast_json.py  (arm AST)     │
                      hml.py       (arm HML)     │
                                                 ▼
                    decoders.py ◄── parity.py: canonical(decode(render(w))) == canonical(w)
                                                 │
                    endpoints/  next_action · contrast · corruption
                                                 │
                    scoring.py · budget.py · validate.py (the gate)
```

---

## 3. The three arms

| arm | what it is | notes |
|---|---|---|
| **SE** | structured English | the strong baseline — every previous model call in this project was structured English, and it saturated two benchmarks |
| **AST** | generic Apply/Bind/Name/Lit JSON | **the required control** |
| **HML** | real HML surface syntax | every rendering compiles under the actual compiler |

**The AST control is the single most important methodological addition.** Without it, any
benefit measured for HML is equally consistent with a benefit of *structure in general*,
and the project would attribute it to HML specifically.

The AST vocabulary is deliberately the generic core that **D-041 rejected** for HML's own
internals. That is not a reopening of D-041: that decision was about HML's internal
representation judged on compositional coverage. Here the same core is what a neutral
control should be — what a competent engineer would write knowing nothing about this
project.

---

## 4. Parity is proved, not asserted

For every world and every arm:

```
canonical_world( decode_X( render_X(w) ) ) == canonical_world(w)
```

**Measured: 1800 round trips over 600 worlds (3 families × 5 levels × 40 seeds), 0
failures.**

Consequences worth stating:

- **The English decoder doubles as an ambiguity proof.** Structured English is only a
  fair baseline if it has exactly one reading. The bracketing forms `both … and …`,
  `either … or …`, `if …, then …` are *prefix*-marked, which is what makes recursive
  descent deterministic — the marker announces the structure before the operands arrive.
  A phrasing that could not be parsed deterministically would fail the round trip.
- **The HML decoder uses HML's own parser**, not a second implementation. So parity also
  proves the HML arm *means* what the IR means, rather than merely compiling. This caught
  a real defect: the relativised symmetry claim parsed correctly only by luck of
  `implies` being right-associative. Nested quantifiers are now explicitly bracketed.
- **The parity check is shown to be able to fail** —
  `test_parity_detects_a_dropped_fact` swaps in a renderer that omits one fact and
  asserts the check catches it. A parity check that cannot fail is not evidence.

---

## 5. Two costs HML pays, measured rather than hidden

1. **Relativised quantification.** HML has no `forall x in D` binder, so a finite-domain
   quantifier becomes `forall x : Real . x in D implies …`. Sound, standard, and longer.
2. **No uninterpreted predicate.** A declared `Predicate` is not callable (`HML-T470`);
   the only callable form, `def R(x, y) : Proposition := …`, requires a body. **HML cannot
   state an uninterpreted relation.**

Cost 2 forced a design change. The original plan expanded a finite relation into one fact
per ordered pair, so no arm could benefit from a shorter idiom for closure. That is
un-renderable in HML, so enumeration was available to two arms and not the third — using
it would have measured that gap rather than the representation. The relation is now stated
**once per arm in that arm's own idiom** (a list of pairs; a table node; a disjunction of
equalities), and the decoders prove the three determine the same relation.

*This is an ontology gap worth recording independently of the arena.*

---

## 6. Endpoints

### A · Next-action prediction — forced choice, unique key

"Given the world and what has already been established, which of these is a correct next
result?"

The obvious phrasing ("what is the next step?") has **no unique answer** when two
variables are simultaneously ready, which happens constantly in a DAG. So correctness is a
property tested *per option*:

- algebraic — the variable is unresolved and every variable its definition mentions is
  resolved, so it follows without deriving anything else first;
- logic — the literal is entailed by facts + established, and is not already established.

`_assert_unique_*` re-checks every option with the oracle before the item is emitted; an
item where two options pass, or none, raises rather than being scored.

Distractor roles: `not_yet_reachable`, `wrong_arithmetic` (a flipped operator — the slip a
real solver makes), `already_established`, `opposite_polarity`, `undetermined`.

### B · Paired minimal-contrast sensitivity — the headline endpoint

Pairs differ by **one** declared edit and have **different answers**; both conditions are
enforced at construction. Scored **both-correct**: a model that always answers TRUE scores
0, because exactly one member of every pair is TRUE. That is what makes this a measure of
whether a distinction was *perceived* rather than guessed.

| contrast | edit | why it matters here |
|---|---|---|
| `QUANTIFIER_ORDER` | swap two binders | `examples/logic/` exists for exactly this: the orders are not equivalent |
| `IMPLICATION_DIRECTION` | `A implies B` ↔ `B implies A` | implication is not correlation |
| `OPERAND_ORDER` | `a - b` ↔ `b - a` | subtraction is not commutative |

### C · Corruption detection — secondary, reuses A's worlds

"Which is the FIRST incorrect line, or NONE?" Naming the line — rather than a yes/no
soundness verdict — forces the chain to be recomputed and is not guessable at 50%. About
half the corpora are clean, so always crying corruption scores no better than never doing
so. **Corruptions are semantic, never syntactic**: every line is well-formed and uses
declared names, so no arm can win by making bad syntax visually obvious.

---

## 7. Scoring

Inherited from `difficulty-lab-scorer-1.0.0`: only the **last** `FINAL:` line counts;
missing, malformed or out-of-space answers are **wrong**, never retried; a **truncated**
response is **not scored at all**.

That last rule exists because of a concrete near-miss in this project's own record.
`evaluation/calibration/results/CAL3.json` reports `total=4, correct=2`; both "failures"
are `finish_reason=length` at exactly 8192 tokens. Reading that file without the
truncation caveat says the model had headroom it did not have. The `valid` flag makes that
mistake unrepeatable here, and `pair_score` drops a pair whole when either member is
invalid — scoring the surviving half would silently turn a sensitivity measure into an
accuracy measure.

---

## 8. Budget — the length confound stays visible

Parity makes the arms carry the same information. It cannot make them the same length, and
forcing that would mean distorting a notation into something nobody writes.

Measured over the 306-item gate corpus (`cl100k_base`, prompt = instructions + state +
question + options):

| arm | mean tokens | max | mean chars |
|---|---|---|---|
| SE | 328.8 | 507 | 898.8 |
| HML | 338.0 | 532 | 931.9 |
| AST | 576.3 | 991 | 1671.7 |

SE and HML are within **2.8%**. The AST control is 1.75× the shortest arm.

The first AST encoding was **4.7×** SE — fully tagged nodes at `indent=2`. A control
inflated that far is not a control: every HML win would have been equally consistent with
"HML beats verbose JSON". The encoding was compacted to the standard lightweight idiom (a
name is a JSON string, an integer is a JSON number) *without* abbreviating keys to
`n`/`o`/`a`, which would have bought tokens by making the control cryptic — the same error
in the other direction. **Any result where the arms differ in accuracy *and* in length has
two candidate explanations, and the AST arm is the one still carrying a length penalty.**

---

## 9. Pre-flight gate — `python -m evaluation.arena.validate`

**All eight checks PASS.** 306 items · 69 pairs · exit 0.

| check | result |
|---|---|
| determinism (rebuild → byte-identical prompts) | PASS |
| parity (214 worlds × 3 arms = 642 round trips) | PASS |
| HML compiles (214 worlds, real compiler) | PASS |
| no duplicate prompts within an arm | PASS |
| answer distribution non-degenerate | PASS — modal share 0.298 / 0.239 / 0.407 |
| contrast pairs answer-balanced | PASS — 0 of 69 pairs agree |
| seeds disjoint from the calibration band | PASS — base 200 000 vs 900 000+ |
| scorer behaviour, incl. truncation refusal | PASS — 12 cases |

Items: NEXT_ACTION 114 · CONTRAST 138 · CORRUPTION 54.

---

## 10. What this design does **not** establish

- **No model has been called.** Nothing here is evidence about any model's behaviour.
- **It does not test HML's ontology at large.** Three families, all within HML's covered
  region. The structural tension from the handoff stands: the families where the tested
  model is plausibly weak are the families where HML's coverage is near zero.
- **The AST arm remains the longest.** Parity is on information, not on tokens.
- **`MIXED_STATE_COMPOSITION` is not ported.** The three ported families were enough for
  both headline endpoints; composition is the obvious next family.
- **Next-action covers two families, not three.** A finite relation has no natural
  "next result", so the quantifier family carries endpoint B instead.
- **`OPERAND_ORDER` twins have answers that are exact negations** of each other. A model
  could in principle exploit the pattern across a corpus; it cannot within a single item,
  since each item is scored independently and the twin is never shown alongside.

---

## 11. Exact next action

Run the first small-model screen. Suggested shape, to be confirmed before spending calls:
one endpoint (B, the highest-signal), one level, all three arms, paired items adjacent in
the seed order so that arm is the only thing varying. Record the budget table alongside
the accuracy in the same results file, per §8.
