# Benchmark governance

Governance version: `hml-corpus-governance-1.0.0`
Corpus: M3-Lite `hml-m3-lite-001-0.1.0`, 40 items
Status: **prepared, not run.** No model call has been made. `ACQ0 = UNTESTED · H1 = UNTESTED · H2 = UNTESTED · H3 = UNTESTED`.

This document states the rules a candidate must survive to enter a Hamiltonian Lang
benchmark corpus, and — more importantly — the rules this project refuses to relax. Code
is in `evaluation/corpus_governance/` and `evaluation/m3/lite/`; every claim below is
enforced by a test in `tests/evaluation/test_corpus_governance.py`.

## The premise: compiler acceptance is not admission

The research basis is FormalMATH. Its funnel dropped from roughly **92% compiler-valid**
candidates to roughly **32% retained** after semantic checking. Two thirds of everything a
type checker was willing to accept did not mean what the specification said.

A corpus built on a type checker alone is a syntax test wearing a benchmark's clothes.
Hamiltonian Lang has a stricter type system than most, which makes the temptation worse,
not better: the stricter gate 1 is, the more plausible it is to stop there.

`FunnelReport.compiler_only_illusion()` therefore reports what the retention rate *would*
have been on gate 1 alone, printed beside the true retention. **A run that reports the same
number at both ends has not validated a corpus.** It has demonstrated that gates 2 to 5 are
inert, and that is the first thing to check about any corpus this package blesses.

## The five gates

Ordered, total, short-circuiting. A later gate never runs on an item an earlier gate
rejected — asking whether a non-compiling object back-translates faithfully is asking about
the meaning of something that has no meaning, and recording an answer would put a
fabricated verdict in the audit trail.

| # | gate (`GATE_ORDER`) | what it decides | module |
|---|---|---|---|
| 1 | `compiler` | lex, parse, resolve, type-check | `gates.py` |
| 2 | `deterministic_semantics` | the encoding matches the recorded ground truth | `semantic_checks.py` |
| 3 | `back_translation` | the formal object renders back to the same proposition | `back_translation.py` |
| 4 | `negation_attack` | the negation is not provable | `negation.py` |
| 5 | `human_review` | a person decides, where the machinery declined to | `human_gate.py` |

In the wording of the protocol: **1. parser/compiler validation → 2. deterministic semantic
checks → 3. back-translation consistency → 4. counterexample or negation attack → 5. human
review when unresolved or promotion-critical.**

An item **missing** from a gate's results is `ESCALATED`, never skipped and never passed.
An unrun gate that defaults to a pass is the failure this whole package exists to prevent.

## Three commitments enforced by types, not by convention

A comment saying "note: this is asymmetric" is deleted by the first person in a hurry. A
missing constructor is not.

### 1. A failed refutation is not validation

`negation.py` has exactly two outcome constructors:

```
NegationOutcome = Refutation | NoInformation
```

There is no `Confirmation`, no `Validated`, no `Supported`, no `Survived`, and no boolean
whose `False` branch could be read as "passed". `NoInformation.evidential_weight` is the
literal `0`, annotated `Literal[0]`, on a frozen dataclass — it cannot be assigned another
value at runtime or written to in a way a static checker accepts.

Consequently "the negation attack validated this item" is not merely discouraged here; it
is **unrepresentable**. A test parses the module's own source and asserts the class set.

This matters most because on this host the tools are weak: Mathlib and `stanc` are absent,
and the Lean backend closes every obligation with `sorry` **by design**, so `lean_verify`
rejects its own backend's output. **No Lean path can certify anything here.** Failure to
refute is therefore the overwhelmingly common outcome, and reading it as support would wave
through essentially the entire corpus.

Three disprovers are available, and the prover is a parameter rather than a hard dependency
so that what is actually available on a host is visible in the record:

- `no_prover_available` — the honest default. Records `NEGATION_UNATTEMPTED` per item.
- `sympy_disprover` — settles closed-form arithmetic and dimensional-exponent claims.
  Anything with a free symbol, a distribution, a quantifier or a limit is declined.
- `obligation_disprover` — delegates to `hamiltonian_lang.verification.obligations`, the
  project's own nine-class discharge engine, rather than growing a second and inevitably
  divergent set of checks inside the governance package.

The obligation disprover refutes only on `VERIFIED` **and** `substantive`, and the
conjunction is load-bearing. `verify_source` returns `VERIFIED` on a module carrying no
obligations at all — correctly, since there was nothing to fail. Read on the verdict alone,
gate 4 would refute every candidate whose negation is not statable in the supported subset.
That is gate 4's spelling of "compiler acceptance is admission", and it is the more
dangerous spelling: it *deletes* items rather than admitting them. A `DISPROVED` verdict
means the negation is false, which closes off one negation and says nothing about the
candidate.

### 2. Judge disagreement stays disagreement

`JudgePanel` retains every individual decision and exposes **no majority vote**. Three
judges, two `ALIGNED` and one `MISALIGNED`, returns `INCONCLUSIVE` and raises a human-review
request. A majority vote would return `ALIGNED` and destroy the only signal that says *this
item is ambiguous*.

The panel has no `majority` and no `modal_alignment` attribute, and a panel constructed with
zero decisions raises rather than reporting `INCONCLUSIVE` — an unrun gate is not an
inconclusive one.

Lexical overlap is a **screen, not a verdict**: a reversed quantifier prefix reuses every
word of the original, so `deterministic_overlap` scores it above 0.9 while the two
renderings state different propositions. This is asserted, so that nobody later promotes
the screen to a decision procedure.

### 3. The pipeline stops rather than resolves

`ReviewQueue` has no `auto_resolve`, no `resolve_by_majority`, no `resolve_all` and no
`expire`. A corpus that silently self-approves its own hard cases is unfalsifiable: every
item it retains is an item its own machinery was comfortable with.

Five triggers demand a human, and all five stop promotion until a named reviewer with a
written rationale clears them:

- `promotion_set_ambiguity`
- `new_equivalence_transformation`
- `new_verifier_class`
- `inconclusive_semantic_pair`
- `benchmark_correction`

## Gate 2 in detail: what "not applicable" is not

Four statuses, and the distinctions are load-bearing:

| status | blocks admission? | meaning |
|---|---|---|
| `PASS` | no | the check ran and the encoding matched |
| `FAIL` | yes | the check ran and the encoding did not match |
| `NOT_APPLICABLE` | no | the precondition is structurally absent (a logic item declares no distribution law) |
| `INCONCLUSIVE` | **yes** | the check applies and could not be decided; goes to gate 5 |

Collapsing the last two loses in both directions. Treating "no laws here" as inconclusive
blocks every logic item forever; treating "could not decide" as inapplicable waves through
exactly the items the gate was built for. The HML-EVAL-001 pilot shipped a scorer that
returned 0.0 when nothing was checkable and silently zeroed 25 problems — the same confusion
with a third spelling.

Because `NOT_APPLICABLE` is neutral, an item could in principle be admitted with almost
nothing checked. `MIN_APPLICABLE_CHECKS = 4` closes that: **"passed because nothing was
checked" is not a pass.**

Faithfulness is checked in both directions. `no_undeclared_entities` matters as much as
`entities_declared`: an encoding that declares everything asked for *plus* three extra
parameters is a different model that happens to contain the right one.

## Partitions

Four pools, dealt deterministically in `evaluation/m3/lite/partitions.py`. Ten items each;
every one of the seven domains is present in every partition, and that is checked rather
than assumed.

| partition | visible | role |
|---|---|---|
| `development` | **yes** | the only pool anything may be tuned, demonstrated or debugged against. Scores here are diagnostics, never results. |
| `adversarial` | no | attacks on the pipeline. An attack set the pipeline has been fitted to stops being an attack set. |
| `promotion` | no | gates promotion decisions. Every item is `promotion_critical`, so gate 5 stops and asks. |
| `transfer` | no | the generalisation pool. Read once, at the end. |

The deal is a **round-robin**, not a judgement: domain by domain in declared order, items
sorted by id, one cursor carried across domain boundaries. Nobody chooses what is held out,
because hand-picking is how the easy items end up in the pool that gets reported. The same
40 items always produce the same four partitions, so the manifest can be regenerated and
compared rather than trusted.

### Disjointness is checked by content hash, never by name

**An ACQ0 demonstration must never come from a held-out partition.** An item shown to a
model as a worked example and later scored is measuring recall.

The check compares SHA-256 digests over `(specification, question, answer, reference)`. **An
id is not among those fields.** Renaming a reused item changes its id and nothing else, so a
name-based check passes exactly the case it exists to catch. Three redundant passes run:
exact digest, digest after case folding and punctuation stripping, and a 5-token shingle
Jaccard at 0.60 for paraphrase. The third is a *flag*, not a rejection — whether two items
are "the same problem" is a judgement, and this machinery does not make judgements.

A contamination check against an empty set of foreign corpora **raises**. A clean report
produced by comparing against nothing is worse than no check.

Provenance is validated before the deal: unique ids, every generator under the
`hml-m3-lite-001::` seed namespace, one corpus version, and an assignment that is total and
disjoint.

## M3-Lite: shape and calibration

40 items. The predecessor, HML-EVAL-001, measured nothing: all seven arms scored 93.3% on 15
problems, six of seven contrasts had **zero discordant pairs**, and the minimum detectable
effect was about 33 percentage points. A design that can only see a 33-point effect cannot
report the absence of a 5-point one.

**Domain floors, evaluated per domain, never as an average.** An overall 55% is compatible
with six domains at 65% and one at 5%, and those are different corpora with different
conclusions.

| domain | floor | authored |
|---|---|---|
| algebra | 6 | 6 |
| probability_statistics | 6 | 6 |
| logic_and_scope | 6 | 6 |
| dimensions_physics | 6 | 6 |
| linear_algebra | 6 | 6 |
| calculus | 5 | 5 |
| epistemic_reasoning | 5 | 5 |

Eight structural-error categories, **five items each**, so a per-category error rate has the
same denominator everywhere. Five of the eight are the project's own prohibited conflations:
a benchmark for this language should be hardest exactly where its type system claims to be
strictest.

An H3 roster drops to 29 items across five domains, because the implemented verifier subset
cannot state an obligation about an indexed term or a limit. **The drop is published on the
roster with its reason.** A filter that silently keeps only the tasks the verifier happens to
handle makes H3 unfalsifiable: whatever the model does, the retained subset is the one where
the machinery works.

### Measured, and predicted

These are kept in separate keys of `calibration_report()` and must never be merged.

**Measured** (deterministic, no model involved):

| quantity | value | threshold |
|---|---|---|
| uniform-guess floor | 0.306 | — |
| `always_TRUE` | 0.275 | ≤ 0.50 |
| `always_FALSE` | 0.300 | ≤ 0.50 |
| `always_first_option` | 0.325 | ≤ 0.50 |
| `take_distractor` | 0.000 | ≤ 0.30 |
| `copy_last_number` | 0.025 | ≤ 0.30 |
| difficulty index | min 5, median 6, max 8 | ≥ 4 |

The constant-response test earned its place during authoring: it caught `always_FALSE` at
0.55 and forced the boolean polarity to be rebalanced. A corpus beatable by answer bias
reports response bias as reasoning.

**Predicted** — status `PREDICTED_NOT_MEASURED`, `measured_band = None`:

The target band is **0.40–0.70**. The lower edge is the uniform-guess floor raised to the
design floor; the upper edge is HML-EVAL-001's structural-fidelity anchor A2 (0.648, 0.701).
A1's 93.3% final-answer ceiling is named and **deliberately not used**.

Caveats travel with the prediction: A2 was measured on encoding tasks rather than on
answering questions about structure, so the transfer is an argument and not a measurement;
both anchors come from one model on one host with n = 15; and if a real run lands outside the
band, the corpus needs re-tuning and this prediction was wrong. That is why `measured_band`
is `None` rather than absent — there is no `mark_measured` method, and the field cannot be
written to.

## Guidance variants

Three, prepared and not run: `no_supplied_solution` (the default scout),
`model_generated_local_plan`, and `human_written_complete_solution`. The default scout
**refuses** the third — FormalMATH found that a supplied full solution sometimes *reduced*
success — and using it at all requires a written justification. It will not silently render
as the no-solution arm.

## What this apparatus cannot do

`evaluation/corpus_governance/` and `evaluation/m3/lite/` import no network library, no
model client, and no proof assistant. There is no `subprocess`, no `os`, no `importlib`, and
none of `exec`, `eval`, `compile`, `open` or `__import__` anywhere in either package — so a
string containing a tool name cannot become a call. This is asserted by parsing each module,
with negative controls proving the scanner distinguishes a planted `subprocess.Popen` from a
docstring that merely explains why Lean is unavailable.

Every gate here is pure Python over the frozen AST, SymPy, or an explicitly recorded human
decision.

## Known limitations

- **Nothing has been run against a model.** The 40–70% band is a prediction. Whether the
  corpus is calibrated is unknown until it is measured.
- **Gate 3 has no judges.** `JudgePanel` is exercised with hand-supplied decisions in tests.
  A real back-translation panel requires either humans or model calls, and neither has
  happened.
- **Gate 4 decides only closed-form claims.** SymPy settles the arithmetic answer-key audit;
  everything else is recorded as `NoInformation`, which is worth exactly zero.
- **The funnel's drop rate has not been observed on foreign candidates.** Every M3-Lite item
  passes every gate by construction, since the items were authored against the gates. The
  92%-vs-32% gap is reproduced in tests with a deliberately corrupted ground truth, not
  measured on an independent candidate pool.
- **`MIN_DOMAIN_PRESENCE = 1`** is all a ten-item partition can honestly promise. It is not
  a stratification guarantee at the strength of the roster floors.
