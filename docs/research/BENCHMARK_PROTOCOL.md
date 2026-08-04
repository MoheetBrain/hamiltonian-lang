# Benchmark Protocol — Hamiltonian Lang v0

Status: **PREREGISTERED**. Written before any model-in-the-loop measurement was taken.
Author role: Benchmark Scientist / Adversarial Reviewer.
Companion document: `audits/RED_TEAM_REPORT.md` (attacks on this protocol and on the design).

---

## 0. What this document is, and what it is not

This document fixes, in advance, the hypotheses, metrics, arms, effect sizes, sample sizes and
**falsification conditions** for the central experiment described in `GOAL.md` §8.

It is not a results document. **No comparative measurement has been run.** The only numbers
that exist at the time of writing are compiler-side baselines in `evaluation/results/baseline.json`,
which measure the *tooling* and are explicitly not evidence for or against the thesis.

Three rules bind everything below.

1. **A hypothesis with no stated falsification condition is not preregistered.** Every H below
   states one. If a future revision removes one, the hypothesis reverts to unpreregistered and
   any result on it is exploratory.
2. **Deterministic scoring is mandatory wherever a deterministic checker is possible.** Where it
   is not possible, the metric is marked `NON-DETERMINISTIC` and reported separately; it may not
   be aggregated into a headline number.
3. **Arms are fixed before data collection.** Adding an arm after seeing results converts the
   study to exploratory and must be labelled as such in the results document.

### Terminology

- **Arm** — a representation in which a problem is presented to the model under test.
- **Problem** — one item in `benchmarks/datasets/`, with prose, ground truth and a check.
- **Deterministic check** — a scoring procedure implemented in `evaluation/score.py` that
  involves no model call and returns the same verdict on every run.
- **Compiler baseline** — a measurement of the Hamiltonian toolchain alone, with no model in the
  loop. Never evidence for the thesis.

---

## 1. Arms

The five arms of `GOAL.md` §8, plus the two ablation arms that the threats-to-validity section
requires. Arms A–E are the primary comparison; A′ and E′ are the confound controls and are
**as important as the primary comparison**.

| Arm | Directory | Representation | Prompt scaffolding |
|-----|-----------|----------------|--------------------|
| A | `benchmarks/representations/english/` | Ordinary mathematical prose | none beyond the task instruction |
| A′ | *derived from A at run time* | Ordinary mathematical prose | **matched structural checklist** (see §9.1) |
| B | `benchmarks/representations/latex/` | LaTeX | none |
| C | `benchmarks/representations/python/` | Conventional code (NumPy/SciPy idiom) | none |
| D | `benchmarks/representations/stan_or_lean/` | An existing formal language (Stan for probability/algebra, Lean 4 for logic/quantifiers) | none |
| E | `benchmarks/representations/hamiltonian/` | Hamiltonian Lang (HML-L1) | none |
| E′ | *derived from E at run time* | Hamiltonian Lang | **scaffolding stripped**: source with all comments removed and no mention of the type discipline in the prompt |

A′ is the arm that can kill the project. See §9.1.

---

## 2. H1 — Variable binding

**Claim.** A model reading a problem in arm E resolves every symbol reference to the correct
binding occurrence more reliably than in arms A–D.

**Null hypothesis H1₀.** Binding accuracy in arm E is less than or equal to the maximum binding
accuracy across arms A–D, on matched problems.

**Metric — `binding_accuracy`. DETERMINISTIC.**
For each problem the ground truth in `benchmarks/expected/<id>.json` lists, for every symbol
occurrence the prose mentions, the declaration it must resolve to. The model is asked to emit
its resolution as a flat mapping `occurrence -> declaration_id`. Score is
`correct_resolutions / total_resolutions`, micro-averaged over problems. For arm E the mapping
is additionally cross-checked against `SymbolTable` output from `hamiltonian_lang.compile_source`;
a disagreement between the model's stated mapping and the compiler's is scored as *incorrect*,
not silently corrected.

**Comparison arms.** E vs A, B, C, D, and critically E vs A′.

**Minimum effect size worth caring about.** +10 percentage points absolute over the best of
A–D, at the problem level. Below 10 points the result is within the range that prompt phrasing
alone is known to move and is not worth acting on.

**Sample size.** 8 binding-category problems is *not enough* for a hypothesis test; it is enough
for a pilot. Preregistered target for a confirmatory run: **120 binding items** (the 8 seeds
expanded by the mutation procedure in §10), 5 independent samples per item per arm, giving
n = 600 per arm. At p₀ = 0.70 and a 10-point effect, a two-proportion test at α = 0.05 with
80 % power needs roughly 330 per arm; 600 leaves headroom for clustering by seed problem.
Analysis must use a cluster-robust (by seed problem) test, not a naive binomial, because the
120 items are not independent.

**Falsification.** H1 is falsified if, on the confirmatory run, the cluster-robust 95 % CI for
(E − best of A..D) has an upper bound below +10 points. H1 is *also* treated as falsified for
the purposes of the thesis if the CI for (E − A′) includes 0 — see §9.1.

---

## 3. H2 — Quantifier scope

**Claim.** Arm E preserves quantifier nesting order under paraphrase, translation and
round-trip more reliably than arms A–D.

**Null hypothesis H2₀.** Scope accuracy in arm E is less than or equal to the maximum across
arms A–D.

**Metric — `scope_accuracy`. DETERMINISTIC.**
Each quantifier problem ships as a *pair*: a forward form and a reversed form that differ only
in prefix order. The model is asked to produce, in the arm's own notation, a representation of
the stated English sentence. Scoring:
- For arm E: compile the emitted `.hml` and compare `hamiltonian_lang.content_hash` against the
  reference form's hash. Correct iff it matches the intended member of the pair **and** differs
  from the other member. Both conditions are required; matching neither and matching both are
  distinct failure modes and are logged separately.
- For arms A, B, C, D: the model emits an explicit quantifier prefix as a list
  (e.g. `["forall:x", "exists:y"]`). Correct iff the list equals ground truth. This is a string
  comparison, not a judgement.

Note the asymmetry: arm E is scored on a *compiled artefact*, arms A–D on a *declared prefix*.
This favours A–D, because declaring a prefix is easier than producing a compiling program. The
asymmetry is deliberate and must be reported; it makes any E advantage conservative.

**Comparison arms.** All. Plus E vs E′ to check the advantage is not carried by the explanatory
comments in the seed files.

**Minimum effect size.** +15 points absolute. Scope errors are the failure mode with the
largest documented base rate, so a smaller improvement is not distinguishable from sampling noise
at feasible n.

**Sample size.** 60 quantifier pairs (120 items), 5 samples per item per arm.

**Falsification.** H2 is falsified if the upper bound of the 95 % CI for (E − best of A..D) is
below +15 points; **or** if any arm-E emission that hash-matches the *reversed* reference is
scored correct by the harness (that would be a harness bug and invalidates the run); **or** if
the forward and reversed reference forms are ever found to share a content hash. The last
condition is checked by `tests/adversarial/` on every run and is currently **satisfied**
(measured: the two `examples/logic/quantifier_scope*.hml` forms hash differently).

---

## 4. H3 — Types and dimensions

**Claim.** Arm E surfaces type and dimensional errors that arms A–D leave silent.

**Null hypothesis H3₀.** The rate at which a dimensionally or type-invalid construction is
*detected and reported* is no higher in arm E than in arms A–D.

**Metric — `error_visibility`. DETERMINISTIC for E, D; NON-DETERMINISTIC for A, B.**
Each problem in the dimensional and probability categories has a *corrupted* twin whose ground
truth is "this is invalid, for reason R". Score is the rate at which the invalidity is reported.
- Arm E: `compile_source` returns a diagnostic. Deterministic. The diagnostic **code** must
  match the ground-truth code, not merely be nonempty.
- Arm D (Stan): `stanc --warn-pedantic` exit status / diagnostic. Deterministic.
- Arm D (Lean): `lake env lean` exit status. Deterministic.
- Arm C (Python): running the reference snippet under a units library (`pint`) where the problem
  is dimensional; otherwise **NON-DETERMINISTIC** and reported separately.
- Arms A, B: there is no checker. The model must *state* that the construction is invalid and
  give the reason. Matching "the reason" requires judgement → **NON-DETERMINISTIC**. Reported as
  a separate table, never folded into the headline number.

This is the hypothesis where scoring circularity is hardest to avoid, and the honest answer is
that arms A and B cannot be scored deterministically on it. See §9.4.

**Secondary metric — `false_alarm_rate`. DETERMINISTIC.** Rate at which an arm reports an error
on a *valid* problem. A representation that rejects everything scores 1.0 on error visibility;
this metric is what stops that. Both numbers must be reported together, and the headline figure
is `visibility − false_alarm`.

**Minimum effect size.** +20 points on `visibility − false_alarm` over the best deterministic
comparator (D). Large, because arm E has a purpose-built checker and arm A has none: anything
smaller would be an unimpressive return on building a compiler.

**Sample size.** 40 valid / 40 corrupted pairs.

**Falsification.** H3 is falsified if `visibility − false_alarm` for E does not exceed D's by
20 points; or if the false-alarm rate for E exceeds 0.05 on the valid set (a checker that
rejects correct mathematics is worse than no checker). **A currently-known threat:** the
compiler accepts `param s : PositiveReal = -1.0` (measured, see red-team report §1.1), which is
a false *negative*; the corrupted set deliberately includes this case, and H3 will be scored
with it included.

---

## 5. H4 — Verified success with compiler feedback

**Claim.** Given up to *k* rounds of compiler diagnostics, a model converges to a program that
type-checks and whose semantics match ground truth, at a higher rate in arm E than the
comparable repair loop in arm D.

**Null hypothesis H4₀.** The converged-correct rate in arm E is no higher than in arm D at equal
*k* and equal token budget.

**Metric — `verified_success_at_k`. DETERMINISTIC.**
`k ∈ {0, 1, 3}`. A trial succeeds iff, after at most *k* repair rounds, the emitted artefact
(a) compiles clean and (b) satisfies the problem's structural assertions in
`deterministic_check`. Both conditions are machine-checked by `evaluation/score.py`.

Arms A, B, C have no repair loop and are scored only at k = 0 on the structural assertions
extracted from a declared answer. They are not part of the H4 comparison, which is
**E vs D only**. Comparing a language with a compiler against prose is not a fair test of the
repair-loop claim, and pretending otherwise would be the easiest way to fake a positive result.

**Secondary metric — `diagnostic_precision`. DETERMINISTIC.** For each injected single-line
error, does the first reported diagnostic point at the correct source line? Measured as exact
line match. Implemented in `evaluation/score.py::diagnostic_line_accuracy`.

**Minimum effect size.** +10 points on `verified_success_at_3` over arm D, at matched total
tokens.

**Sample size.** 100 problems × 5 samples per arm.

**Falsification.** H4 is falsified if E does not exceed D by 10 points at matched tokens; or if
the gain at k = 3 is entirely explained by the gain at k = 0 (i.e. the repair loop contributes
nothing — the claim is specifically about *feedback*, so a flat repair curve falsifies it even
if the headline number is favourable). Report the k = 0 / 1 / 3 curve, not just the endpoint.

---

## 6. H5 — Token efficiency

**Claim.** The stated-structure cost of arm E is repaid: the tokens required to reach a correct,
verified answer are no worse than arms A–D, even though the representation itself is longer.

Note that this is deliberately weaker than "arm E uses fewer tokens". The design freeze §2
concedes that mandatory role labels cost tokens. The defensible claim is about *tokens to
correctness*, not tokens to represent.

**Null hypothesis H5₀.** Tokens-to-verified-correct in arm E is greater than or equal to the
minimum across arms A–D.

**Metric — `tokens_to_correct`. DETERMINISTIC given a fixed tokenizer.**
`total_tokens_consumed_over_all_rounds / number_of_correct_trials`, per arm.
Tokenizer: `tiktoken` `cl100k_base`. **`tiktoken` is not installed in this repository's `.venv`
at the time of writing** (measured: `ModuleNotFoundError`), so the harness falls back to a
documented approximation and labels every number `APPROXIMATE`. The fallback is defined in
`evaluation/score.py::count_tokens` and is a whitespace-and-punctuation split calibrated to
nothing; it is adequate for *relative* comparison of arms within one run and inadequate for any
absolute claim. A confirmatory run must install `tiktoken`.

**Secondary metric — `representation_tokens`. DETERMINISTIC.** Raw token count of the problem
statement in each arm. This will almost certainly favour A and B; report it anyway.

**Minimum effect size.** For the primary claim, a null result is acceptable: parity on
`tokens_to_correct` combined with a win on H1–H4 is a coherent positive outcome. What is *not*
acceptable is arm E costing more than 2× the cheapest arm per correct answer.

**Sample size.** Falls out of the H4 run; no separate collection.

**Falsification.** H5 is falsified if `tokens_to_correct` for arm E exceeds 2× the minimum across
A–D. This is `GOAL.md` §8 failure condition 5 made numeric.

---

## 7. H6 — Morphological generalisation

**Claim.** `GOAL.md` §6: knowing one member of a concept family lets a model derive its siblings.
Concretely: a model shown `Normal(location := ·, scale := ·)` and told the role vocabulary
should correctly emit `Cauchy(location := ·, scale := ·)` and correctly *refuse* to emit
`Poisson(location := ·, scale := ·)`, without having seen either.

**Null hypothesis H6₀.** The rate of correct role assignment on held-out families is no higher
in arm E than the rate of correct parameter assignment in arm C (Python/SciPy), where families
also share a `loc`/`scale` convention.

Arm C is the right comparator here and it is a **hard** one: SciPy already implements exactly
this morphology (`scipy.stats.<family>(loc=, scale=)`). If Hamiltonian Lang cannot beat SciPy's
existing convention on family generalisation, the morphology claim adds nothing.

**Metric — `family_generalisation`. DETERMINISTIC.**
Held-out set: families removed from the prompt's exposure set but present in
`hamiltonian_lang.type_system.distributions.DISTRIBUTIONS`. Score = fraction of held-out
families for which the model emits a law that compiles clean and whose role set exactly equals
the registry's `spec.roles`. Refusal cases (families for which a proposed role is *wrong*, e.g.
`scale` on `Poisson`) score correct iff the model declines and names the correct role.

**Minimum effect size.** +15 points over arm C.

**Sample size.** The v0 registry holds **15 families** (measured). That is too few. A
confirmatory run must extend the registry, which is a `src/` change and outside this document's
authority. Until then H6 is **pilot only** and no confirmatory claim on it may be made.
This limitation is stated here rather than discovered later.

**Falsification.** H6 is falsified if held-out role accuracy does not exceed arm C by 15 points;
or if the model's arm-E advantage disappears when the role vocabulary is *not* supplied in the
prompt (which would show the advantage came from the prompt's glossary, not the language).

---

## 8. H7 — Graph retrieval

**Claim.** The semantic graph view supports dependency queries that prose and LaTeX cannot
answer reliably: "what does `y` depend on, transitively?", "which constraints touch `sigma`?",
"which symbols are stochastic?".

**Null hypothesis H7₀.** Retrieval accuracy from arm E's graph is no higher than from arms A/B
read directly.

**Metric — `retrieval_f1`. DETERMINISTIC.**
Ground truth is the transitive dependency set authored in `benchmarks/expected/<id>.json`. The
model answers a set-valued query; score is micro-F1 over the returned symbol set. For arm E the
graph is available via `CompileResult.graph().dependencies_of(name)`; the model may query it.
For arms A/B the model must read the prose.

**A serious caveat, stated in advance.** If arm E's answer is obtained by *calling*
`dependencies_of`, then H7 measures the graph implementation, not the representation, and the
model is a lookup wrapper. Two conditions must both be reported:
- **H7-tool**: model may call `dependencies_of`. Expected to be near 1.0; scientifically
  uninteresting; report it as a tooling sanity check.
- **H7-read**: model may only read the triple listing as text, no tool call. This is the
  hypothesis. Only H7-read counts.

**Minimum effect size.** +20 points micro-F1 on H7-read over the best of A/B.

**Sample size.** 60 queries over 20 models.

**Falsification.** H7 is falsified if H7-read does not beat A/B by 20 points; or if H7-tool and
H7-read differ by more than 40 points, which would indicate the graph text is not actually
readable and the win is entirely tooling.

---

## 9. Threats to validity

### 9.1 The scaffolding confound — the one that can kill the project

`GOAL.md` §8 failure condition 3 names this. It is the most likely way this project produces a
result that looks positive and means nothing.

**The threat.** Arm E's files do not merely use a different notation. They *state* things arms
A–D leave implicit: that `sigma` is positive, that `X` is a random variable, that `scale` is a
standard deviation. A model reading arm E is handed a completed structural analysis. If you hand
the same completed analysis to a prose arm as a prompt checklist, the advantage may vanish
entirely — and the finding would be "structured prompting helps", which is already known and
requires no language.

**The ablation arm A′.** Arm A′ presents the *same prose as arm A*, prefixed with a fixed,
problem-independent checklist:

```
Before answering, write out:
1. every variable, and its type (real / natural / probability / random variable / distribution)
2. the domain and any dimension or unit of each variable
3. every constraint that must hold, including implicit positivity or range constraints
4. for any probability statement, the distribution family and which role each parameter fills
   (location vs scale vs variance vs rate)
5. the binding of every symbol you use to the place it was introduced
6. for any quantified statement, the exact order of the quantifier prefix
Then answer.
```

This checklist is **problem-independent** — it is the same text for every item. That is what
makes it an ablation of *representation* rather than an ablation of *content*: A′ receives the
same generic structural pressure that arm E's syntax applies, but zero problem-specific
information. It must be frozen before the run and must not be tuned after seeing results.

**The decision rule, fixed in advance.**
- If E > A–D **and** E > A′ by at least the H1/H2 effect sizes → the representation contributes
  something beyond structural prompting. Thesis survives this threat.
- If E > A–D **but** E ≈ A′ (CI for E − A′ includes 0) → **the thesis is falsified for that
  hypothesis** under `GOAL.md` §8 condition 3, regardless of how large E − A looks. This must be
  reported as the headline, not as a footnote.
- If A′ > E → report it as a negative result and say plainly that structured prompting beats the
  language.

**What A′ cannot isolate, stated plainly.** A′ controls for *generic* structural prompting. It
does not control for the possibility that arm E's advantage comes from the seed files' explanatory
comments (e.g. `examples/statistics/normal_distribution.hml` contains a six-line comment
enumerating the six commitments). Arm E′ — comments stripped — controls for that. But there is
one confound that **no arm in this design isolates**: a model that has been trained on structured
formal languages generally may do better on arm E because arm E *looks like* Lean/Stan, not
because Hamiltonian Lang's specific choices are good. Distinguishing "structured formal notation
helps" from "*this* structured formal notation helps" requires arm D to be a strong, fair
implementation, and even then the comparison is confounded by Lean and Stan being far more
represented in pretraining data than a language invented last month. **This confound is not
resolvable within this protocol.** Any positive result must be reported with this limitation
attached. Failing to state it would be the most dishonest thing this document could do.

### 9.2 Compute and token matching

Arm E's representations are longer (measured: see `evaluation/results/baseline.json`
`representation_tokens`). Three equalisation rules, all fixed in advance:

1. **Equal output budget.** Every arm gets the same `max_tokens` for its response. No arm gets a
   larger generation allowance because "it needs more room".
2. **Equal round budget.** k is identical across arms in any comparison. Arms without a compiler
   still get k rounds, with the feedback being their own re-read of the problem (a no-op
   feedback loop), so that the number of forward passes is equal.
3. **Input-token headroom is *not* equalised, and results are reported both ways.** Padding arm A
   to arm E's input length with filler would be a worse distortion than the imbalance. Instead:
   report every headline metric twice — raw, and normalised as `correct_answers_per_1k_tokens`.
   If arm E wins raw but loses normalised, the honest summary is "E is more accurate and more
   expensive", and that must be the sentence used.
4. Same model, same decoding parameters, same temperature, same random seeds paired across arms.
   Trials are paired by (problem, sample index) so that a paired test is available.

### 9.3 Benchmark leakage

The problems must not be recognisable from pretraining. Procedure:

1. **No canonical textbook problems by name.** No "Monty Hall", no "birthday problem", no
   `eight_schools` (the Stan example everyone has memorised). Every dataset item is checked
   against this list by hand before inclusion.
2. **Numeric randomisation at build time.** Every numeric constant is drawn from a seeded RNG at
   dataset-build time and recorded in the item. Regenerating with a new seed produces a
   structurally identical but textually novel item. The seed is recorded in each JSON.
3. **Surface paraphrase.** Each item's `natural_language` is authored fresh rather than quoted.
   Items that could be a verbatim quotation from a textbook are rejected.
4. **Leakage probe, run before the confirmatory run.** Present the model with the first sentence
   of each item and ask it to complete the rest. If completion overlaps the true continuation
   above a fixed threshold (ROUGE-L ≥ 0.6), the item is flagged as possibly memorised and dropped.
   This probe is itself model-based and therefore `NON-DETERMINISTIC`; it is used only to *drop*
   items, never to score them, so its errors cost statistical power rather than validity.
5. **A limitation that cannot be fixed.** Arms B, C and D use notations that are massively
   represented in pretraining; arm E uses a notation invented for this project and represented
   nowhere. This cuts *against* arm E on fluency and *for* arm E on memorisation. There is no
   way to balance it. State it in the results.

### 9.4 Scoring circularity

**Rule: no metric that can be computed deterministically may be scored by a model.**

Deterministic (implemented in `evaluation/score.py`, no model calls):

| Metric | How |
|--------|-----|
| `parse_success` | `compile_source(...).ok()` |
| `binding_accuracy` | symbol-table resolution vs authored ground truth |
| `scope_accuracy` | `content_hash` equality against reference pair members |
| `dimension_correct` | `type_system` dimension vs authored ground truth |
| `semantic_equivalence` | `content_hash` equality |
| `obligation_count` | length of `CompileResult.obligations` |
| `diagnostic_line_accuracy` | reported line vs injected-error line |
| `token_count` | tokenizer (APPROXIMATE without `tiktoken`) |
| `structural_assertions` | the assertion language in §11 |

Non-deterministic, reported separately and never aggregated into a headline:

| Metric | Why it resists determinism |
|--------|---------------------------|
| "did arm A notice the error and say why" | free-text reason matching |
| final numeric answer on open-ended word problems | requires interpretation of the model's prose |
| leakage probe (§9.3.4) | model-based by construction |

**Circularity specific to `content_hash`.** `semantic_equivalence` via `content_hash` is *not*
semantic equivalence. It is equality of a canonical syntax tree modulo bound-variable spelling
and distribution-argument order. Measured facts (see `evaluation/results/baseline.json`):

- `a > 0` and `0 < a` hash **differently**
- `a + b > 0` and `b + a > 0` hash **differently**
- `require P` then `require Q` and `require Q` then `require P` hash **differently**
- module-level declaration renaming changes the hash (see §12, known defect)

So the metric has false negatives by construction. The protocol therefore uses `content_hash`
only for **hash-differs** assertions (proving two things are *not* the same, which the hash does
soundly) and for **exact-form** assertions against a fixed reference. It is never used to claim
two different-looking programs mean the same thing. Any future use of it as a positive
equivalence oracle must first fix the defects in §12.

### 9.5 Gameability

For each metric: the cheapest cheat, and the countermeasure. This table is the reason the
protocol is worth writing.

| Metric | Cheapest way to fake a win | Countermeasure |
|--------|---------------------------|----------------|
| `parse_success` | Emit a trivially valid program (`module M`) that answers nothing | Structural assertions must also pass; an empty module fails every assertion. `score.py` requires ≥1 non-`ModuleDecl` statement. |
| `binding_accuracy` | Author dataset items where the prose already names the binding unambiguously | Distractor requirement: every binding item must carry a `distractors` field naming what a careless reader gets wrong, and an item with no plausible distractor is rejected at authoring time. |
| `scope_accuracy` | Only include quantifier problems whose natural reading is the correct one | Every quantifier item ships as a forward/reversed pair and both are scored; a model biased to one order gets 50 %. |
| `error_visibility` | Report an error on everything | Paired `false_alarm_rate` on the valid set; headline is the difference. |
| `verified_success_at_k` | Increase k until arm E converges, leave arm D at low k | k is fixed at {0,1,3} for all arms before the run and the whole curve is published. |
| `tokens_to_correct` | Report tokens for the winning trials only | Denominator is *all* tokens consumed including failed trials. Defined that way in `score.py`. |
| `token_count` | Choose the tokenizer that flatters arm E | Tokenizer fixed to `cl100k_base` in advance; any fallback is labelled APPROXIMATE and cannot support an absolute claim. |
| `family_generalisation` | Pick held-out families that are morphologically identical to shown ones | Held-out set must include at least one family whose roles *break* the shown pattern (`Poisson` has `rate`, not `location`/`scale`), and refusal cases are scored. |
| `retrieval_f1` | Let the model call `dependencies_of` | H7-read is the scored condition; H7-tool is reported as tooling only. |
| Everything | Run many configurations, publish the best | Arms, k, tokenizer, effect sizes and n are fixed in this document before collection. Any deviation is reported as exploratory in the results document. The dataset seed is recorded per item. |
| Everything | Drop problems arm E fails | The dataset is fixed by content hash before the run; `score.py` reports `problems_scored` and the results document must state it equals the dataset size. |

One gap this table cannot close: nothing in this protocol prevents an author from writing
dataset items that happen to suit Hamiltonian Lang's statement inventory. Every item here was
authored by an agent that had already read `src/`. The mitigation is the `distractors` field and
the requirement that items be expressible in all five arms — an item that cannot be written in
Stan or Lean at all is suspect — but the mitigation is partial. An independent author who has
not read `src/` should re-author the dataset before any confirmatory claim.

---

## 10. Item generation and mutation

Seeds live in `benchmarks/datasets/` (23 items at the time of writing). Confirmatory runs expand
each seed by mutation, all mutations structure-preserving and mechanically applied:

| Mutation | Effect |
|----------|--------|
| `rename` | consistently rename every symbol via a fixed permutation of an identifier pool |
| `renumber` | redraw every numeric constant from the seeded RNG within its declared range |
| `reorder` | permute independent declarations (does **not** preserve `content_hash` — see §12) |
| `retype` | swap a scalar type for a sibling in the refinement poset where the prose supports it |
| `negate` | for paired items, produce the invalid twin with a recorded ground-truth diagnostic code |

Mutations are applied to the *dataset item*, and all five arm encodings are regenerated from it,
so no arm gets a hand-tuned version. The mutation seed is recorded in the results.

---

## 11. The assertion language

`deterministic_check.assertions` is a list of objects, each with an `assert` key. `score.py`
implements exactly these and rejects unknown assertion types loudly rather than skipping them.

| `assert` | Fields | Meaning |
|----------|--------|---------|
| `compiles` | — | `compile_source(...).ok()` is true |
| `rejects_with` | `code` | compilation fails and `code` appears among the error codes |
| `symbol_type` | `symbol`, `type` | the named symbol's rendered declared type equals `type` |
| `symbol_kind` | `symbol`, `kind` | declaration kind (`var`/`param`/`obs`/…) |
| `stochastic` | `symbol`, `value` | the symbol does / does not carry a probability law |
| `law_family` | `symbol`, `family` | the symbol's law family |
| `law_role` | `symbol`, `role`, `argument` | the named role of the symbol's law is the named symbol or literal |
| `conditioned_on` | `symbol`, `given` | the conditioning set, as a sorted list |
| `quantifier_prefix` | `prefix` | the ordered quantifier prefix, as `["forall:x", "exists:y"]` |
| `dimension_of` | `symbol`, `dimension` | rendered dimension of a definition or declaration |
| `obligation_count` | `count` | number of proof obligations |
| `depends_on` | `symbol`, `set` | transitive dependency set from the semantic graph |
| `hash_equals` | `problem` | content hash equals that of another problem's hamiltonian arm |
| `hash_differs` | `problem` | content hash differs from another problem's |

Every assertion is computable without a model. An item whose ground truth cannot be expressed in
this language does not belong in the deterministic set.

---

## 12. Known defects in the measurement instrument

Preregistering a protocol on top of a broken instrument is how false positives happen. These
are **measured**, not suspected, and each constrains what the protocol may claim. Full detail
and the full timeline are in `audits/RED_TEAM_REPORT.md`.

`src/` was under active development while this protocol was written, and **thirteen defects
found during the review were fixed before it was finished**. Measurements are therefore pinned
to a fingerprinted tree:

```
SRC_TREE_SHA256 = 4776ebfdcdb51ff3cacb28b3ba56321917a8a61938be1eab06a79836457fdb77
measured at     = 2026-08-04T20:22:27
```

**Re-fingerprint and re-run `tests/adversarial/` before citing any row.** Every finding has an
executable guard there.

### Open at the fingerprinted tree

| # | Defect | Measured evidence | Consequence for this protocol |
|---|--------|-------------------|-------------------------------|
| 1 | `SymbolId.ordinal` is positional, so inserting a declaration above a referenced symbol changes the whole module's hash | measured | the corpus must be frozen by hash before a run; the hash is **not** a stable key across edits. `reorder` mutations may not be combined with `hash_equals`. |
| 2 | Statement reordering changes `content_hash` when the reordered statements are referenced; reordering bare same-typed declarations does not | measured both ways | as above |
| 3 | A law may be given data outside its own support: `trials = 5`, `successes = 9` under `Binomial` compiles clean | measured | H3's corrupted set includes this case and it counts **against** arm E |
| 4 | `exists unique` yields one opaque obligation rather than an existence obligation and a uniqueness obligation | measured | no H4 item may use `exists unique`; `obligation_count` assertions would encode the conflation as ground truth |
| 5 | A `counterexample` need not differ from the invariant it purports to refute | measured | `HML-S603` is a presence check, not a content check; H6 concept items must not treat it as evidence of testable consequences |
| 6 | `def d := 1.0 / 0.0` compiles clean; a module with no statements compiles clean | measured | the empty module is the cheapest way to game `parse_success`; `score.py::_a_compiles` therefore additionally requires ≥1 non-header statement |

### Closed during the writing of this protocol — recorded, not deleted

Deleting these would hide that the defect *class* is live. Each now has a regression guard in
`tests/adversarial/`. Full table with reproductions in `audits/RED_TEAM_REPORT.md` §1A.

Unary minus preserving refinement types (`param s : PositiveReal = -1.0`) · `sqrt(-4.0)` and
`log(-1.0)` type-checking · no writable probability literal (`Probability = 0.5` rejected) ·
module-level declarations not alpha-normalised · **definition parameters** not alpha-normalised ·
a value able to take a distribution family's name · concept cycles of length ≥ 2 · definition
cycles · cross-role constraints never checked (`Uniform(lower := 5.0, upper := 1.0)`) ·
`prior` on `obs` · `infer mle` with no likelihood · concept transforms ignoring their arguments ·
`UnknownType` surviving a clean check.

Two of these bear on how this protocol must be read.

**The alpha-renaming criterion was false while a passing property test asserted it.** The test
in `tests/roundtrip/` was real and green; its generator simply never produced a `def` parameter,
the one binder form that failed. §9.4's restriction — `hash_equals` only against a fixed
reference form, `hash_differs` used freely because it is sound — was written for this reason and
should be kept even now that the defect is closed.

**Three docstrings asserted checks that did not exist.** The consequence for a preregistration
is direct: no hypothesis here may rest on a guarantee that is documented but not executed. Every
assertion in §11 is computed from a compiled module at scoring time, never read from a claim.

### What the backends do and do not settle

`GOAL.md` §13 item 3 requires "at least two backends (Layer 3) — one verification, one
probabilistic or numerical". Lean, Stan and SymPy lowerings exist at the fingerprinted tree, so
the *count* is met. The *claim* is not, and H4 is still not runnable end-to-end:

- the Lean backend closes every obligation with `sorry` (correctly — freeze §8 rules out proof
  search), so it produces statements, not verifications;
- the Stan backend cannot express `Quantity[...]`, so the whole dimensional category has no
  arm-D counterpart through the toolchain.

Most importantly, `GOAL.md` §8 failure condition 4 is translation loss under round-tripping, and
**no backend round trip has been tested**. The only round trip verified is HML → HML (measured:
29/29 files hash-preserving), which is the one that cannot lose anything. Until HML → Lean → HML
or HML → Stan → HML is demonstrated, the one-object-many-views claim — the project's genuinely
novel contribution — remains untested, and it is testable **today, with no model in the loop**.

---

## 13. What must be true before any comparative claim is published

A checklist, so that "the experiment ran" is not confused with "the experiment was valid".

1. `tiktoken` installed; no `APPROXIMATE` label on any token number.
2. Arm A′ run and reported alongside arm E, with the §9.1 decision rule applied as written.
3. Arm E′ run, to separate the language from its explanatory comments.
4. Defects 1, 2, 3, 5, 6 in §12 fixed, or each explicitly carried as a caveat naming the
   hypotheses it weakens.
5. A real Layer-3 backend for arm D comparison, or an explicit statement that H4 is untestable.
6. Dataset re-authored, or at least audited, by someone who has not read `src/`.
7. Cluster-robust analysis, paired by problem, not naive binomial tests.
8. Both raw and token-normalised versions of every headline number.
9. The negative results reported in the same document, at the same prominence, as the positive
   ones — `GOAL.md` §8: "These outcomes will be reported, not buried."

Until items 1–9 hold, the correct description of this project's status is: **the thesis is
untested.**
