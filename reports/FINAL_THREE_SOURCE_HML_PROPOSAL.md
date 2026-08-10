# Final three-source architecture proposal

**Status: PROPOSAL. No production semantics were changed to produce it.** Baseline HML
`a21fdb7`. Corpus `d5b5ffa`. Nothing here may enter the build before explicit approval.

Sources: **LeanDojo Benchmark 4** (execution) · **PRM800K phase 1** (action quality) ·
**AMPS-Khan** (pedagogy). MiniLang is prior evidence and was not re-audited.

---

## 0. Provenance and real N

| source | artefact | verified | real N analysed |
|---|---|---|---|
| LeanDojo | Benchmark 4 v10, DOI `10.5281/zenodo.12740403`, mathlib4 `29dcec07`, Lean `v4.10.0-rc1`, CC BY 2.0 | archive SHA256 `19b9a319…a98a4` **matches Zenodo's published checksum** | **259,580 proof steps**, 122,517 theorems, 3,606 files. No sampling. |
| PRM800K | repo `7ecc7947`, `phase1_train.jsonl` sha256 `e9da6a73…e34d` | re-derived counts match the prior audit independently | **6,456 decision points**, 43,853 candidates; 260 blind-adjudicated |
| AMPS-Khan | `/Users/moheet/Desktop/0000.parquet`, sha256 `b48c40af…5df41` | **community mirror.** Traced one hop to HF `XinyaoHu/AMPS_khan`; **not** verified against Hendrycks' official tarball | 103,059 rows → **~11,000 distinct skeletons** |

**Three N corrections that change how every number reads.**

1. **AMPS inflates ~9.3×.** Khan exercises are template-generated; blanking math and numerals
   collapses 103,059 rows to ~11,000 distinct solution skeletons (I reproduced this: 11,054).
   Every AMPS frequency quoted in rows overstates the evidence roughly tenfold.
2. **PRM decision points are a conditioned sample.** Labelers sampled once, accepted if Great,
   and expanded k *only after failure*. Measured: P(first candidate = `+1`) is **0.999 at k=1**
   and **0.049 at k=7**. So the multi-candidate corpus is exactly the states where the
   generator already failed. Unconditional rates cannot be read off it.
3. **Half of LeanDojo's theorems carry no transition evidence.** 60,973 of 122,517 (49.8%) have
   zero traced tactics — term-mode proofs and proofs the tracer could not decompose.

---

## 1. Triangulation matrix

`3` = supported by three · `2` = two · `1` = single source · `✗` = not observed ·
`—` = source structurally cannot measure it.

| mechanism | AMPS | PRM | LEAN | verdict |
|---|:--:|:--:|:--:|---|
| INTERPRETATION | — | — | — | no source measures it |
| PLANNING (declared, executed) | weak | — | ✗ | **1**, 24 skeletons / 4 topics |
| ACTION GENERATION (k alternatives) | ✗ | **strong** | — | **1** |
| ACTION SELECTION (quality ≠ validity) | weak | **strong** | — | **2 (weak second)** |
| EXECUTION (small effect core) | — | — | **strong** | **1**, but 259,580 steps |
| WARRANT separable from step | **strong** | — | **strong** | **2** ✓ |
| DEPENDENCY / premise citation | — | — | **strong** | **1** |
| GOAL structure (tree, not set) | ✗ | ✗ | **strong** | **1** |
| SCOPE containment | weak | — | **strong** | **2** |
| CANDIDATE (object) lifecycle | weak (11 skel.) | — | ✗ | **1, weak** |
| OBLIGATION | weak | — | **strong** | **2** |
| VERIFICATION owned by checker | — | — | **strong** | **1** |
| BACKEND / decision procedure | — | — | **strong** | **1** |
| FAILURE / abandonment | **✗ (0/103,059)** | ✗ | ✗ | **NOT OBSERVED BY ANY SOURCE** |
| REPAIR / backtracking | **✗ (0)** | ✗ | ✗ | **NOT OBSERVED BY ANY SOURCE** |

**The most important row is the last two.** No source exhibits backtracking, abandonment or
repair. AMPS: zero hits for `backtrack`, zero for seven abandonment phrasings, zero announced
case splits, across all 103,059 rows (I verified this myself). PRM records a strictly linear
chosen path and nothing about unchosen branches. LeanDojo contains only *successful* proofs.
Their silence is **cannot measure**, never support — but the practical consequence is the same:
**no search, backtracking or failure-history machinery is justified by this evidence.**

---

## 2. The four findings that drive everything

### F-1 · The execution core is genuinely small — 42×, measured

**254 distinct Lean tactic heads (185,011 distinct raw tactic strings, 90.5% hapax) reduce to
6 state-effect classes covering 99.86% of 259,580 steps.** Residual: 13 steps.

`DISCHARGE 41.2% · TRANSFORM_TARGET 32.9% · EXTEND_CONTEXT 10.5% · SPLIT 7.1% ·
TRANSFORM_CONTEXT 5.4% · TRANSFORM_BOTH 2.7%`

Entropy 4.693 → 2.050 bits. I recomputed the head side independently: 254 heads, H = 4.693
bits, exactly. **This is the strongest single piece of evidence in the whole audit, and it is
independent of HML** — Lean's designers were not building HML.

**Bound, stated because it matters:** the compression is measured over *pretty-printed states*.
Lean's metavariable context, universe levels, instance cache, goal ordering and elided terms
never reach this dataset. **42× is an upper bound on compressibility, not the size of Lean's
real state algebra.**

### F-2 · An operation label does not predict its state effect

`MI(head ; effect) / H(head) = 0.240`. **Only 24% of the information in a tactic name is about
what it does to the state.** The other 76% is warrant, backend selection and search policy.

The clean demonstration, which I reproduced exactly: `rw` — the commonest tactic, 48,991
occurrences — **transforms the target in only 50.3%** of them. It **closes the goal in 34.5%**
(Lean tries `rfl` afterwards), rewrites a *hypothesis* in 11.7%, and splits in ~3%.

The intuitive decomposition "`rw` = TRANSFORM target" is wrong slightly more than half the time.

### F-3 · Validity is separate from action quality, and must not gate it

PRM, blind-adjudicated (260 candidates, ratings and ground truth hidden until after):

- **72% of `-1`s are mathematically wrong** — so validity is the dominant axis for rejection.
- **But 25.8% of mathematically invalid candidates were rated `0` or `+1`.**
- Pruning every invalid candidate **destroys the only acceptable option in 5.0%** of decision points.
- Measured head-to-head: soft scalar picks a `+1` **0.725**; validity-first lexicographic **0.700**. **Lexicographic is worse.**

Minimal factorization that survives: **VALIDITY + PROGRESS**. `GOAL_RELEVANCE` and
`INFORMATION_GAIN` collapsed — neither ever separated a pair that PROGRESS did not.
`CLARITY`, `VERIFIABILITY`, `COST`, `EXPECTED_SEARCH_VALUE` were **not testable** here.

**27–38% of matched pairs are unexplained by both axes together**, and label noise is a floor
of 2.5–4.5% (byte-identical candidates, same prefix, same labeler, different rating — I verified
4.5%). One labeler emits `0` at .147 where another emits .358. **A scalar critic fit to this
label is partly fitting labeler identity.**

### F-4 · 81% of apparent planning language is narration

AMPS, exhaustive 121-clause frame, strict deletion test: **only 19% carries information the
adjacent mathematics does not already state.** Section headers (`Putting the pieces together`),
restatements (`In conclusion…`, 13.4% of rows) and encouragement are rendering, not reasoning.

The one genuinely novel move found is **not planning**: an *expandable justification pointer*
(`[Why is this identity true?]`, `[What if I don't see this factorization?]` — 597 distinct,
7.66% of rows). A step and its warrant as separable objects, warrant normally suppressed.
**HML already has this**: `Action.warrant` + `EvidenceRecord` + the renderer.

---

## 3. Proposals

Ordered by evidence strength. **None is implemented.**

---

### P-01 · Demote `Action.operation` to provenance; make the effect channels primary

| | |
|---|---|
| **mechanism** | operation labelling |
| **evidence** | LEAN (F-2): MI/H = 0.240; `rw` modal effect only 50.3% across 5 classes |
| **exact examples** | `rw` → 50.3% target / 34.5% discharge / 11.7% context. `induction` → 74% DISCHARGE; its port `induction'` → 83% SPLIT. Same mathematics, opposite signature, from surface syntax alone. |
| **current HML** | `Action.operation: str` (`model.py:271`) — free string, no enum, no validation. The wider corpus already contains `NUMBER_THEORY`, `NOTATION`, `COMBINATORIAL_REASONING` (subject tags), `modus_ponens` (a warrant), `differentiate_reciprocal` (a backend call) all in the same field. |
| **gap** | one field conflates state effect, warrant, backend and subject area |
| **proposed** | Contract change only: `operation` is **provenance**; the five `*_effect` dicts are the semantic primary. Optionally constrain `operation` to a small closed set matching the six measured classes. No new field. |
| **layer** | STATE (contract) |
| **confidence** | **High** — largest measurement in the audit |
| **evidence_against** | Lean's tactic vocabulary is not HML's; HML's corpus uses only 3 operations across 630 records, so the conflation is currently latent, not active |
| **alternative reading** | `operation` is already *de facto* provenance since `verify.py` keys on it only for `VERIFY_CANDIDATE`/`JOIN_BRANCHES`; this may be documentation, not architecture |
| **size** | S (doc + one test) · **risk** L · **back-compat** full |
| **acceptance test** | A fixture whose `operation` is a subject tag verifies identically to one whose operation is `DERIVE`, with the same effects — proving `operation` carries no semantics |
| **Gemma implication** | If HML text is generated by a model, an unconstrained `operation` string is an unbounded vocabulary to learn. Closing it shrinks the target. |
| **recommendation** | **TEST_FIRST** |

---

### P-02 · An in-place claim-transformation effect

| | |
|---|---|
| **mechanism** | rewriting an existing premise rather than deriving a new one |
| **evidence** | LEAN: `TRANSFORM_CONTEXT` 5.41% + `TRANSFORM_BOTH` 2.71% = **8.12% of 259,580 steps**. `replace` is 98% TRANSFORM_CONTEXT; `rw … at h` 11.7% of all `rw`. |
| **current HML** | **This is currently a `DEPENDENCY_VIOLATION` with no legal encoding.** `Claim` is `frozen=True`; `_check_frame` (D-049, shipped this session) rejects any altered prior record unless a declared effect licenses it, and `_licensed_change` licenses only scope effects for claims. |
| **gap** | the frame condition — correct and necessary — is missing a licensed case that is **one step in twelve** in real formal mathematics |
| **proposed** | A `claim_effect` channel `{kind: "TRANSFORM", claim_id, warrant, evidence_id}`, licensed by `_licensed_change`, with its own invariant checking that the new proposition follows from the old under the cited warrant. Mirrors `candidate_effect`/`branch_effect` exactly; no new object. |
| **layer** | STATE + VERIFIER |
| **confidence** | **High** — a direct, quantified contradiction with a rule shipped this session |
| **evidence_for** | LEAN 8.12%, n=21,097 steps |
| **evidence_against** | Single source. HML's corpus has no such transition, so nothing external would test it. Lean's hypothesis rewriting may be an artefact of tactic-mode ergonomics rather than mathematical necessity — a derived new claim is always *expressible*, just less concise. |
| **alternative reading** | Model it as `EXTEND` + retire-old, i.e. never mutate. This is semantically cleaner and costs a claim per rewrite. **This alternative may well be correct** and should be considered before implementing mutation. |
| **size** | M · **risk** M — touches the frame condition, the one rule that made everything else enforceable · **back-compat** additive |
| **acceptance test** | A transition rewriting `h : a = b` to `h : b = a` under `symmetry` verifies VALID; the same without a warrant is INVALID; and the frame condition still rejects an *undeclared* mutation |
| **Gemma implication** | none directly |
| **recommendation** | **TEST_FIRST** — build the fixture and decide mutate-vs-retire *before* writing code |

---

### P-03 · Goals are a tree, not a set

| | |
|---|---|
| **mechanism** | subgoal lineage and sibling structure |
| **evidence** | LEAN: `case` tags compose (`h_real` → `h_real.h_bot`) on **59.59%** of steps; only **67.27%** of consecutive traced pairs satisfy `state_after[i] == state_before[i+1]`, and only 68.32% of proofs are fully linear |
| **current HML** | `SemanticState.goals: dict[str, Goal]`; `Goal` has `id/proposition/status/scope` — no parent, no children, no order. `active_scopes` is a flat ordered tuple. |
| **gap** | ~32% of real proofs are a flattened tree traversal that a chain-shaped `Transition` cannot express |
| **proposed** | `Goal.parent_id: str \| None` and an explicit sibling order. **Not** a search tree — a *derivation* tree. |
| **layer** | STATE |
| **confidence** | **Medium-high** for the finding; **medium** for the remedy |
| **evidence_against** | Single source, and Lean's tree is partly a tracer artefact: LeanDojo traces against the *focused* goal, so only 0.61% of steps ever show >1 goal. The tree may be Lean's bookkeeping rather than mathematics. |
| **alternative reading** | This is the same defect as the **sibling-scope bug already found in `_check_scope`** (a premise in `branch:a` may conclude into `branch:b`, while the mirror is a SCOPE_LEAK — verdicts differ by list position alone). Fixing scope to a tree may subsume this entirely, at a fraction of the cost. |
| **size** | L · **risk** M-H · **back-compat** additive if `parent_id` defaults `None` |
| **acceptance test** | The sibling-scope reproduction returns the *same* verdict in both directions |
| **recommendation** | **TEST_FIRST** — fix sibling scope first and re-measure whether a goal tree is still needed |

---

### P-04 · If a planner ever arrives, `ActionCandidate` must be disjoint from `Candidate`

| | |
|---|---|
| **mechanism** | naming discipline, not a feature |
| **evidence** | PRM: a decision-point alternative is a proposed **action**; **27% of rejected actions are mathematically true**. HML's `Candidate` is *a proposed mathematical object plus the constraints it must satisfy*, whose rejection is a refutation. |
| **gap** | reusing the word would give one term two lifecycles and let a `REJECTED` action be read as a refuted object |
| **proposed** | Record now, in `DECISIONS.md` and the prohibited-conflations list, that action candidates and object candidates are disjoint with **no subtyping path** — before any planner exists to get it wrong. |
| **layer** | STATE (naming) · **size** XS · **risk** L · **back-compat** full |
| **confidence** | **High** — costs nothing, prevents a class of error this project already prohibits elsewhere |
| **recommendation** | **IMPLEMENT** (documentation only, no code) |

---

### P-05 · A policy score beside `verify()`, vector-valued, never a gate

| | |
|---|---|
| **mechanism** | ranking alternative actions |
| **evidence** | PRM (F-3): lexicographic validity-first measured **worse** (0.700) than soft scalar (0.725); pruning invalids destroys the only good option in 5.0% of points; validity and progress have opposite discriminative power on the two boundaries (.457/.213 vs .203/.363) |
| **current HML** | `verify()` returns `VALID/INVALID/UNRESOLVED` and nothing ordinal. No score, no comparison operator over `TransitionResult`. |
| **proposed** | If built: emit `(validity, progress)` as a **vector**, keep the combination soft and revisable, and let a validity verdict *order* candidates rather than delete them. |
| **layer** | POLICY |
| **confidence** | **Medium** — the shape is well evidenced; whether to build it at all is not |
| **evidence_against** | Single source. The target is partly not a function of the state (2.5–4.5% irreproducible labels; 2× inter-labeler variation). 27–38% of matched pairs are unexplained by both axes. **The critic may be fitting annotator identity.** |
| **size** | L · **risk** H · **back-compat** additive |
| **acceptance test** | On held-out PRM decision points, the critic beats the 0.308 random baseline *and* beats a validity-only ranker — measured, not assumed |
| **Gemma implication** | This is the only proposal that directly changes the matched experiment: it would add a scoring arm |
| **recommendation** | **DEFER** — do not build before the Gemma experiment. Nothing in HML today needs it, and it would add an untested component to an experiment meant to test representation. |

---

### P-06 · "No acceptable action exists" as a first-class outcome

| | |
|---|---|
| **evidence** | PRM: **41.9%** of decision points contain **no** `+1` (I verified). In **40.0%** a *human wrote the step* because all seven model candidates were rejected. |
| **gap** | `generate k → score → pick best` has no defined behaviour when everything is bad, and that is not a corner case |
| **layer** | PLANNER · **confidence** High for the fact, N/A for the remedy |
| **recommendation** | **DEFER** — records a hard constraint on any future planner. Nothing to build until one exists. |

---

### P-07 · REJECT — search, backtracking, failed-action history, frontier, budget, representation history

| | |
|---|---|
| **evidence** | **Zero support in all three sources.** AMPS: 0 backtracking, 0 abandonment, 0 announced case splits in 103,059 rows (verified). PRM: strictly linear chosen path, nothing about unchosen branches. LEAN: successful proofs only. |
| **gap** | none demonstrated |
| **recommendation** | **REJECT.** Do not add `SemanticState` history fields. If these are wanted later they need a source that actually contains failure — none of these three does. |

---

### P-08 · REJECT — a plan or strategy object

| | |
|---|---|
| **evidence** | AMPS: declared multi-step plans occur in **24 skeletons across 4 topics**, and are **always executed exactly as declared** — never revised. Strategy is chosen once at step 0 and never changes. |
| **gap** | a write-once decoration |
| **alternative** | The genuinely interesting AMPS finding — **guarded method dispatch** ("*since* the terms share no common monomial factor *and* the leading coefficient is not 1, factor by grouping", 442 skeletons / 55 topics) — is already expressible as `Action.preconditions` + `Action.warrant`. |
| **recommendation** | **REJECT** the object; **DEFER** a typed warrant kind for method guards |

---

### P-09 · CONFIRMED, no change — the open warrant vocabulary

Lean cites **66,603 distinct premises** across 259,580 steps, plus decision procedures
(`omega`, `ring`, `positivity`) that discharge 100% of their goals while citing **zero**
premises. A closed-world warrant registry would be wrong at this scale.

This **independently corroborates** the decision recorded in `SEMANTIC_STATE_CONTRACT.md`
that there is deliberately no warrant-rule registry. **No change.**

---

### P-10 · Use these sources as fixtures, not as semantics

Free, test-only, no semantic change:

- **AMPS extraneous-root skeletons (11 distinct)** are real `PROPOSED → REJECTED` candidate
  cases with a constraint check — exactly the SF-R06 path the contract records as exercised by
  **no** fixture.
- **Lean SPLIT transitions** (18,315 steps, `by_cases` 91%, `constructor` 88%) are external
  branch-structure cases.
- **PRM matched contrasts** (2,916 points with both a `-1` and a `+1`) are a ready-made
  action-ranking benchmark if P-05 is ever built.

**recommendation: IMPLEMENT** — highest value per unit of risk in this document.

---

## 4. Recommended order

1. **P-04** (naming, documentation only) — free, prevents a conflation.
2. **P-10** (fixtures) — closes a gap the contract already admits.
3. **P-01** (contract: `operation` is provenance) — small, high-confidence.
4. **Fix sibling scope**, then re-measure **P-03**. Do not build a goal tree first.
5. **P-02** — but decide mutate-vs-retire on a fixture before writing code.
6. **D-050 trust boundary** — unrelated to this audit and still the top blocker.
7. **P-05 / P-06** — only after the Gemma experiment, if at all.
8. **P-07 / P-08** — rejected.

---

## 5. The eighteen questions

1. **Does Lean independently support the small-execution-core thesis?** **Yes.** 254 heads → 6 classes, 99.86% coverage, 42×. Upper bound, since pretty-printing erases structure.
2. **Which operations survive?** `CASE_SPLIT` (7.1%), goal discharge (41.2%), and rewriting — but rewriting must split into target/context/both. `DERIVE` survives and is nearly contentless. `VERIFY_CANDIDATE`/`JOIN_BRANCHES` are **untested**, not refuted.
3. **Which labels should be warrants/effects/backends?** `APPLY_THEOREM`, `modus_ponens`, `modus_tollens` → warrants. `differentiate_reciprocal`, `multiply_inequality`, `evaluate_probability_product` → backend calls. `NUMBER_THEORY`, `NOTATION`, `COMBINATORIAL_REASONING` → provenance tags, not operations at all.
4. **What does AMPS reveal that MATH missed?** Two things: the *guard* on method selection (the precondition a terse solution omits), and the expandable justification pointer. Both are warrant-layer, not planner-layer.
5. **Which AMPS moves are prose?** **81%.** Section headers, `In conclusion` restatements, encouragement, analogies.
6. **What distinguishes `-1`/`0`/`+1`?** `-1` vs `0` is mostly **validity** (gap .457); `0` vs `+1` is mostly **progress** (gap .363). 27–38% is unexplained by both.
7. **Is validity separate from action quality?** **Yes, decisively.** 25.8% of invalid candidates were rated acceptable or Great.
8. **Fixed-k or dynamic-k?** **Dynamic, and reactive** — expand after a failure, not predicted from difficulty. That is literally how the data was collected.
9. **Should multiple branches stay alive?** The data **licenses** it (67% of decision points have ≥2 acceptable successors) and gives **zero evidence of its value**. No source records what happened down an unchosen branch.
10. **What state does a planner need that `SemanticState` lacks?** A goal tree with sibling order; a set of proposed actions; a "no acceptable action" outcome. Lean additionally maintains a metavariable context, universe levels, an instance context, local definitions with bodies, and unnameable hypotheses (27.9%) — none of which HML can represent, and the first of which **LeanDojo itself cannot measure**.
11. **What failed history should survive?** **None, on this evidence.**
12. **Do we need a policy critic?** Not for anything HML does today. A critic is *learnable* (0.76 precision / 0.79 recall on rejecting bad actions from state alone, no oracle) but its target is partly annotator identity.
13. **Scalar or multidimensional?** **Vector `(validity, progress)`.** Measured: lexicographic is worse than scalar; one weight mis-orders one boundary.
14. **What stays outside trusted state?** Decision procedures, premise retrieval at scale (mean 64,733 accessible premises), clarity/cost, and every subject-area tag.
15. **Which proposals have ≥2 independent sources?** **Only the separable warrant** (AMPS justification pointers + Lean decision procedures) — and it is already implemented. Everything else is single-source. That is the most sobering line in this document.
16. **Which earlier ideas now look unnecessary?** Search trees, backtracking pointers, failed-candidate history, plan objects, strategy stacks, representation history. Also `EXPECTED_SEARCH_VALUE`, `CLARITY`, `COST` as distinct axes — no source can measure them.
17. **Smallest complete architecture?** **Very close to what already exists.** Six execution effects (HML has five channels), an open warrant vocabulary (has), verifier-owned status (has), scope containment (has), obligations (has). The genuine gaps are: in-place claim transformation (8.12% of Lean steps), goal-tree/sibling structure, and `operation` doing four jobs.
18. **What should be implemented after approval?** In order: P-04, P-10, P-01, then the sibling-scope fix, then re-measure P-03. Nothing else without a further decision.

---

## 6. What this audit does not establish

- **Nothing was measured against a model.** No claim about HML's reasoning quality follows.
- **Fifteen of sixteen mechanisms are single-source.** Convergence was the goal and was largely *not* achieved — the three sources answer different questions and mostly do not overlap.
- **AMPS rests on an unverified community mirror** whose reshaping flattened per-hint segmentation, so "steps" there are partly an artefact.
- **The 42× compression is an upper bound** on a pretty-printed projection, not Lean's state algebra.
- **The PRM critic numbers are one adjudicator, 260 candidates, with acknowledged upward bias** from stratification.
- **Absence of failure evidence is not evidence of absence.** All three sources record success. A source containing genuine failed reasoning would be needed to justify any repair machinery, and none of these three is one.
