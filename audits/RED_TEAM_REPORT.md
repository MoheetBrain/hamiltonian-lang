# Red Team Report — Hamiltonian Lang v0

Role: Benchmark Scientist and Adversarial Reviewer.
Scope: the *design* and the *claims*, not the typos.
Authority: veto over claims, not over implementation. Nothing in `src/` was edited.

## Provenance of every measurement in this document

All behavioural claims below were executed, not inferred. Anything I did not measure is
labelled ESTIMATE; there are two such labels in this document and no others.

**The tree was being edited by another author throughout this review, and every open
defect I found was fixed within minutes of being written down.** Three distinct source
trees were measured:

| Tree | Fingerprint (`sha256` over sorted `src/**/*.py`) | Time |
|------|--------------------------------------------------|------|
| T1 | (not captured — probe predates fingerprinting) | ~19:55 |
| T2 | `6640d1a22a31fcb5aad75ca25d01a7a8d8ce116003e3922309a005ea44ec15dc` | 20:12:47 |
| T3 | `4776ebfdcdb51ff3cacb28b3ba56321917a8a61938be1eab06a79836457fdb77` | 20:22:27 |

Findings are reported **as a timeline**, not as a snapshot, because the timeline is itself
the most useful thing in this report. §1 is now organised as *closed* and *open* against
T3. The closed findings are not deleted: deleting them would hide that the defect *class*
is live, and a reviewer needs to know which guarantees were absent until someone went
looking. Section 5.11 draws the methodological conclusion.

Every finding below has an executable guard in `tests/adversarial/`. Re-run that suite
before citing any row of this document.

---

## 1. Semantic holes — as a timeline

Constructs that parse and type-check and mean something wrong, ambiguous, or nothing at
all. Every one below was reproduced as an `.hml` snippet that survived `hml check` at the
time stated. Every one has a guard in `tests/adversarial/`.

### 1A. Closed during this review

Thirteen holes were open when found and closed before this document was finished. They are
kept, with their reproductions, because a reader needs to know which guarantees were
absent until someone went looking — and because the reproductions are now regression
tests rather than bug reports.

| # | Hole | Reproduction | Open at | Closed at | Now |
|---|------|--------------|---------|-----------|-----|
| 1.1 | Unary minus preserved refinement types, so a negative literal inhabited `PositiveReal` | `param s : PositiveReal = -1.0` | T1 | T2 | `HML-T402` |
| 1.2 | `sqrt` / `log` domain restrictions unenforceable for literals, same root cause | `def d := sqrt(-4.0)` | T1 | T2 | `HML-T427` |
| 1.3 | No probability literal could be written: `0.5` typed `PositiveReal`, incomparable with `Probability` | `param p : Probability = 0.5` | T1 | T2 | accepted (correct) |
| 1.4 | Module-level declarations not alpha-normalised | `var alpha : Real` vs `var omega : Real` hashed differently | T1 | T2 | invariant |
| 1.5 | Definition **parameters** not alpha-normalised — the binder form the existing property test did not generate | `def f(u : Real) := u + 1.0` vs `def f(w : Real) := ...` | T1, T2 | T3 | invariant |
| 1.6 | A value could take a distribution family's name, silently | `param Normal : Real` beside `law X ~ Normal(...)` | T1, T2 | T3 | `HML-N307` |
| 1.7 | Concept cycles of length ≥ 2 undetected (only `A extends A` was checked) | `concept A extends B` / `concept B extends A` | T1, T2 | T3 | `HML-S602` |
| 1.8 | Definition cycles undetected, **contradicting a docstring that claimed the check existed** | `def f := g + a` / `def g := f + a` | T1, T2 | T3 | `HML-S606` |
| 1.9 | Cross-role constraints never checked, so a law could denote the empty set | `Uniform(lower := 5.0, upper := 1.0)` | T1, T2 | T3 | `HML-T417` |
| 1.10 | `prior` / `likelihood` / `law` decorative — role never checked against the target's declaration kind | `obs y : Real = 3.0` then `prior y ~ Normal(...)` | T1, T2 | T3 | `HML-S607` |
| 1.11 | Only `infer posterior` was well-posedness-checked; the other four queries were not | `param t : Real` then `infer mle t` | T1, T2 | T3 | `HML-S604` |
| 1.12 | Concept members barely checked: a transform could ignore its own argument, and arity was unchecked at the call site | `transform t(u) := p` | T1, T2 | T3 | `HML-P214` |
| 1.13 | `UnknownType` survived a clean check, contradicting the invariant in `ast/nodes.py:16` | `require sum(w) = 1.0` | T1, T2 | T3 | typed; 0 surviving `UnknownType` nodes measured |

Two of these deserve to be remembered after the code is fixed.

**1.8 is the one that should worry a reviewer most.** `src/hamiltonian_lang/semantics/__init__.py`
line 11 asserted, verbatim:

> Order still matters for *definition* cycles, which are detected separately.

No such detection existed. A documented guarantee that is absent is worse than an absent
guarantee, because a reader building on it will not test for it.

**1.5 is the one with the methodological lesson.** The freeze document, §5, said:

> canonical hash. Property-tested in `tests/roundtrip/`.

The property test was real and passing. It generated `param` and `def`-name binders and
never generated a `def` **parameter** — the one binder form that violated the criterion. A
green property-based suite was not evidence, because the generator did not reach the
defect. Any future claim of the form "property-tested" must state the generator's
coverage, not merely its existence.

### 1B. Open at T3 (`4776ebfd…`, measured 2026-08-04T20:22:27)

**1.14 The content hash is edit-fragile, and is advertised as a dataset key.**
Measured: inserting an unrelated declaration anywhere above a referenced symbol changes the
hash of the whole module. `SymbolId.ordinal` is positional, so `sym:#0.2` means "the third
thing declared" and any edit above it renumbers everything below.

This is a correct consequence of the design, not a bug. It is listed because freeze §7
advertises the hash as "Suitable for equality testing, deduplication, and **dataset keys**"
and `README.md:65` describes it as "invariant under renaming, sensitive to structure". Both
true; neither warns about *insertion position*, which is what actually breaks a
content-addressed corpus in practice. The protocol works around it by freezing the corpus by
hash before a run (§9.5, §12 row 10).

**1.15 `exists unique` generates one opaque obligation, not two.**
Measured: `require exists unique x : Real . x > 0.0` compiles and yields a single
`constraint` obligation carrying the whole proposition. Unique existence is precisely the
claim that decomposes into an existence obligation and a uniqueness obligation, and the
obligation machinery already exists to carry both. Zero examples and zero benchmark items
use the construct (measured: 0 occurrences across `examples/` and `spec/`).

**1.16 A `counterexample` need not differ from the invariant it purports to refute.**
```hml
concept C
    parameter p : Real
    invariant i := p > 0.0
    counterexample bad := p > 0.0
end
```
Compiles clean at T3. `HML-S603` enforces that a concept has *at least one* invariant or
example — a presence check, not a content check. `GOAL.md` §4 demands "testable
consequences" and says "Plausibility is not admissible evidence"; a counterexample that
asserts exactly its own invariant satisfies the letter of the rule and tests nothing.

**1.17 Distributions may be given data outside their own support.**
```hml
obs trials : Natural = 5
obs successes : Natural = 9
likelihood successes ~ Binomial(trials := trials, prob := 0.5)
```
Compiles clean: nine successes in five trials. `Uniform`'s reversed bounds are now caught
(1.9 above), so the cross-role machinery exists; it has simply not been extended to the
support relation between a law's parameters and an observed value bound to it.

**1.18 Two constructs that are accepted and arguably should not be.** `def d := 1.0 / 0.0`
compiles clean, and a module containing nothing but `module M` compiles clean and is
reported as valid. Neither is dangerous on its own. The empty module matters for the
benchmark specifically: it is the cheapest way to game `parse_success`, which is why
`evaluation/score.py::_a_compiles` additionally requires at least one statement beyond the
module header.

## 2. Where existing tools genuinely beat this design

Not hedged. These are cases where I would tell a working scientist to use the other tool.

**Stan, for anything with a constrained parameter space.** `simplex[3] shares;` captures
"three non-negative reals summing to one" in one declaration, with the constraint enforced
by the sampler's transform, not merely asserted. The Hamiltonian encoding
(`benchmarks/representations/hamiltonian/a03_three_way_share_split.hml`) needs three
`Probability` declarations plus a `require`, produces five undischarged obligations, and
enforces nothing. Stan also has `ordered`, `positive_ordered`, `unit_vector`,
`cholesky_factor_corr` — a vocabulary of constrained types built from real modelling
experience. The v0 type lattice has nine scalars and no constrained aggregate types at all.

**Lean, for anything where the answer is a proof.** The Lean backend emits statement
skeletons closed with `sorry`, which is the honest thing to do given freeze §8 rules out
proof search. But it means that for the entire quantifier-scope category — the category
where this design's structural advantage should be clearest — Hamiltonian Lang produces a
*statement* and Lean produces a *verified theorem*. In
`benchmarks/representations/stan_or_lean/q02_exists_forall.lean` the arm-D encoding proves
the statement false. The arm-E encoding records that someone claimed it. For H2 as
preregistered this is fine, because H2 scores representation fidelity. For a user who wants
to know whether the statement is true, arm D wins outright.

**SciPy, for distribution morphology.** H6 claims that concept families let a model derive
siblings from one member. `scipy.stats` already implements exactly this morphology:
essentially every continuous family takes `loc=` and `scale=`, and the ones that cannot
(`poisson(mu=)`) say so. A model that has seen SciPy has already seen this generalisation,
in a vastly larger corpus. The v0 registry has 15 families; SciPy has over 100. H6's null
hypothesis is set against arm C for this reason and it is a hard null.

**pint (Python), for dimensions with units.** Hamiltonian Lang checks dimensions and
explicitly does not reconcile units (freeze §8). `pint` does both: it will reject
joule + newton *and* convert feet to metres. For `d02_invalid_dimensional_addition` the two
tools give the same verdict; for any real engineering calculation, unit reconciliation is
the part that actually causes accidents, and this design does not address it.

**LaTeX, for communicating with humans, and that matters more than it sounds.** The project
correctly refuses to optimise for the blackboard. But every model under test was pretrained
overwhelmingly on LaTeX mathematics. Arm B is not merely "the notation humans use"; it is
the notation the *model* has the most experience with. That is a genuine advantage of arm B
in the actual experiment, not a concession to aesthetics.

**Plain English, for stating a problem that has not been formalised yet.** Every arm-E file
in `benchmarks/representations/hamiltonian/` is an *answer*. Producing it required deciding
that `jitter` is a scale and not a variance. Prose can carry an unresolved question; this
language cannot represent one, because `?` is reserved and unused in v0. A representation
in which under-determined problems are inexpressible has a narrower domain than the prose it
means to replace, and §3 of `GOAL.md` ("What Must Be Representable") does not list "an
incompletely specified problem" among the things that must be representable. It should.

---

## 3. Unsupported claims

Verbatim quotations, with file and line, of sentences in the repository that assert more
than the evidence supports. **Re-verified against T3**; where the code changed under a
quotation during this review, that is recorded rather than quietly dropped.

### 3.1 Still unsupported at T3

**`src/hamiltonian_lang/type_system/distributions.py:9`**

> targeted error for these is the clearest single demonstration of the project thesis:

The thesis is that an AI system *reasons more accurately* through this representation.
A targeted error message demonstrates that **the compiler** distinguishes `scale` from
`variance`. Whether that changes any model's accuracy is H3/H4 and is unmeasured. This is a
claim about a demonstration of a thesis, asserted in a file that contains no measurement,
in a repository whose README correctly states that "Nothing in this repository should be
read as evidence for it". The docstring should say what it does: that the confusion is
rejected with a diagnostic naming it.

---

**`docs/design/V0_DESIGN_FREEZE.md:72`**

> Cost, now measured rather than assumed: **+4 tokens per law statement, ≈5.9% of a

**Not reproducible as stated.** No tokenizer is named, no corpus is named, and no artefact
computes it. `tiktoken` is **not installed in this repository's `.venv`** — re-verified at
T3: `ModuleNotFoundError: No module named 'tiktoken'` — so any token count produced here
today is tokenizer-dependent and approximate. My own harness labels every token number
`APPROXIMATE` for exactly this reason (`evaluation/score.py::TOKENIZER_IS_APPROXIMATE`). A
figure quoted to two significant figures in a *frozen design document*, introduced by the
words "measured rather than assumed", should name its tokenizer and its corpus or give a
range. This is the clearest remaining instance of a number carrying more authority than its
provenance supports.

---

**`README.md:65`**

> | `hml hash FILE` | content hash — invariant under renaming, sensitive to structure |

**Now true as far as it goes, and still incomplete in the way that matters.** Renaming
invariance holds at T3 for every binder form I could generate, including the definition
parameters that failed at T2. But the sentence is silent about *insertion-position*
sensitivity (§1.14): adding an unrelated declaration above a referenced symbol changes the
hash of the whole module. That, not renaming, is what breaks a content-addressed corpus in
practice, and it is the property a reader of this table would most likely assume.

### 3.2 Withdrawn — the code changed under the quotation during this review

Recorded so the record is honest in both directions.

**`src/hamiltonian_lang/semantics/__init__.py:11`** — text unchanged at T3:

> Order still matters for *definition* cycles, which are detected separately.

At T1 and T2 this was **false**: no cycle detection existed anywhere in the package. At T3
it is **true** (`HML-S606`, §1.8). The claim outran the implementation by roughly half an
hour. The finding stands as a process observation, not as a live defect.

**`src/hamiltonian_lang/ast/nodes.py`** — at T2 this file asserted, as a post-condition of
a successful check, that "every node has a non-None `type_` (no `UnknownType` survives)".
That was false at T2 (§1.13). At T3 the line no longer appears in the file and the property
holds when measured (0 surviving `UnknownType` nodes on the probe that previously broke it).
The quotation is withdrawn.

**`src/hamiltonian_lang/type_system/__init__.py:11`** — text unchanged at T3:

> directive are unrepresentable rather than merely discouraged.

At T1 and T2 "unrepresentable" was too strong: a symbol could be named after a distribution
family and coexist with it (§1.6), which is a conflation of a name for a value with a name
for a law. At T3 that is rejected (`HML-N307`) and the three structural conflations are
genuinely blocked — I verified `HML-T410`, `HML-T428` and `HML-T430`. The word is now
defensible. Noting for the record that the freeze document models the right behaviour here
already: §2 lines 68–70 explicitly withdraw an earlier "cannot be expressed" claim as having
"overstated the grammar's role".

**`docs/design/V0_DESIGN_FREEZE.md:122`** — text unchanged at T3:

> canonical hash. Property-tested in `tests/roundtrip/`.

At T2 this was *misleading rather than false*: the test existed and passed, but its
generator never produced the binder form that violated the criterion (§1.5). At T3 the
underlying defect is fixed. The sentence should still gain a clause naming what the
generator covers, because the failure mode it enabled — a green property suite that reaches
none of the defects — costs nothing to guard against and is invisible when it happens.

### 3.3 Claims that are correctly scoped

So this section is not one-sided. `README.md`:

> **No comparative evaluation has been run.** […] Nothing in this repository should be read
> as evidence for it.

Exactly right, and prominent. `GOAL.md` §8 and §13 are likewise unusually disciplined about
falsification, and freeze §8's list of what is *explicitly unsupported* ("Stated so that no
reader infers capability from silence") is the single best piece of claim hygiene in the
repository. The pattern in every finding above is the same: **claim discipline is strong at
the document level and weak in docstrings**, which are where claims escape review.

## 4. Overengineering — complexity in v0 with no demonstrated requirement

**`Tensor[T, ...]`.** Declared in the type vocabulary and the parser. Zero uses across
`examples/`, zero across the 24 benchmark problems, no operation defined on it beyond
element extraction (`_binop_type` handles `Vector` and `Matrix` shapes; a `Tensor` falls
through to the scalar path). It is vocabulary, not capability.

**`exists_unique`.** Parsed (`exists unique x : T . P`), canonicalised, and rendered
correctly (measured: the English backend emits "there exists exactly one x that is a real
number"). But **no obligation is generated for the uniqueness half** — measured, the single
obligation produced is the whole proposition, undifferentiated — and zero examples and zero
benchmark items use it (measured: 0 occurrences across `examples/` and `spec/`). Unique
existence is precisely the claim that decomposes into an existence obligation and a
uniqueness obligation; emitting one opaque obligation for both is the weakest possible
handling of the construct that most needed the obligation machinery.

**Five candidate grammars in `spec/grammars/` and five encodings of seven problems in
`examples/candidate_syntaxes/`.** Measured: of the 35 candidate-syntax files, only
`a_labelled_linear` compiles at all (5 of 7 — `3_linear_regression.hml` and
`7_concept_definition.hml` fail), and `b_symbolic_ascii`, `c_sexpr`, `d_indent_block` and
`e_graph_triple` are 0 of 7. They are design sketches preserved as if they were arms.
`GOAL.md` §7 frames the language as an optimisation over candidate representations, which
justifies *having* explored them; keeping four dead encodings in `examples/` — the directory
whose README contract is "all of which must check" — invites exactly the misreading that
five surface syntaxes are supported.

**Nine scalar types with an eight-edge poset.** The poset is correct and the reasoning in
`types.py` is good. But `PositiveNatural` exists solely so that the literal `1` can inhabit
both `Natural` and `PositiveReal`, which is a workaround for literals being typed by value
rather than by context. Bidirectional checking (push the expected type down into the
literal) would remove the need for the node. The lattice is carrying weight that belongs in
the inference algorithm.

**`?` and `!` reserved and unused** (freeze §1). Reserving punctuation is cheap and I would
not normally flag it — except that `?` is reserved as a "query marker" while §2 above shows
the language's inability to represent an *under-specified* problem is a real limitation. The
reservation is a placeholder for the feature that would most widen the language's domain.

**What is NOT overengineered, for balance.** Role-labelled distribution arguments, the
dimension vector over `Fraction`, the locally-nameless canonical projection, and the
diagnostic structure (code, expected, found, correction, notes) are all carrying their
weight. The diagnostics in particular are the best thing in the codebase: measured, 50 of 50
single-line injected errors were reported at the correct line
(`evaluation/results/baseline.json`, `diagnostic_quality.line_accuracy = 1.0`).

---

## 5. Metric gaming — how to fake a positive result with this protocol

Written as an attack plan, because a countermeasure you cannot state an attack against is
decoration. Each item names what in `docs/research/BENCHMARK_PROTOCOL.md` stops it, and
where nothing does, it says so.

**5.1 Author the dataset after reading `src/`.** I did this. All 24 problems were authored by
an agent that had read the type system, the distribution registry and the statement
inventory. Every one of the 21 valid Hamiltonian encodings compiled on the first attempt —
`0 files needed fixing`. That number looks like a usability finding and **it is not one**. It
measures the author's familiarity with the compiler, not the language's learnability. A
naive author would have hit `Probability = 0.5` (which was a type error four hours before
this was written), `NormalVector(location := <scalar>)` (rejected — the role demands a
vector), and the absence of any way to write `sum`. *Countermeasure:* protocol §13 item 6
requires the dataset to be re-authored or audited by someone who has not read `src/`. Until
that happens the 21/21 figure should be quoted only with this paragraph attached.

**5.2 Let arm E's files carry the analysis and call it representation.**
`examples/statistics/normal_distribution.hml` opens with a twelve-line comment enumerating
the six semantic commitments. A model handed that file has been handed the answer.
*Countermeasure:* arm E′ (comments stripped) in protocol §9.1. **Weakness:** E′ is defined
but not run, because no model-in-the-loop arm exists yet.

**5.3 Skip the A′ ablation, or run it and bury it.** This is the single most effective
attack and the hardest to detect from outside, because A′ is the arm most likely to erase
the result. *Countermeasure:* protocol §9.1 fixes the checklist text in advance, forbids
tuning it after seeing results, and states the decision rule — if the CI for (E − A′)
includes 0, the hypothesis is **falsified** and that must be the headline. **Weakness:**
nothing but the author's discipline enforces it. This is the section a reviewer should check
first.

**5.4 Score arm E deterministically and arms A/B by model judgement.** Arm E has a compiler;
arms A and B do not. It is trivially tempting to score "did the prose arm get it right" with
an LLM judge that has already seen the Hamiltonian ground truth. *Countermeasure:* protocol
§9.4 partitions metrics into deterministic and non-deterministic and forbids aggregating the
second into a headline. `evaluation/score.py` contains no model calls at all, which is
mechanically checkable.

**5.5 Report `error_visibility` without `false_alarm_rate`.** A checker that rejects
everything scores 1.0. *Countermeasure:* protocol §4 makes the headline `visibility −
false_alarm` and sets a hard ceiling of 0.05 false alarms on the valid set.

**5.6 Choose the tokenizer that flatters arm E, or quote the wrong tokens.** Note the trap
already sitting in `evaluation/results/baseline.json`: the Hamiltonian arm totals 879
approximate tokens against English's 1242, which reads like a 29 % saving and **is an
artefact of corpus layout** — the English files contain the problem statement and the
Hamiltonian files contain only the finished encoding. The harness prints a `CAVEAT` beside
the number for this reason. *Countermeasure:* protocol §6 fixes `cl100k_base` in advance and
defines H5 as tokens-to-*verified-correct*, not tokens-to-represent, with the denominator
including failed trials.

**5.7 Tune k until arm E converges.** *Countermeasure:* k fixed at {0,1,3} for all arms, and
the whole curve published — §5 additionally falsifies H4 if the k=3 gain is entirely
explained by the k=0 gain, so a flat repair curve cannot be dressed up as a repair-loop win.

**5.8 Drop the problems arm E fails.** *Countermeasure:* the corpus is fixed by content hash
before the run and `score.py` reports `problems_scored`; the results document must state it
equals the dataset size. `UnknownAssertion` is raised rather than skipped for the same
reason — a silently skipped assertion inflates the pass rate.

**5.9 Publish the baseline as if it were a result.** `evaluation/results/baseline.json`
reports 93/93 assertions passed and 1.0 on every per-metric rate. Those numbers are *the
compiler agreeing with a ground truth authored to describe what the compiler does*. They
say nothing about any model. *Countermeasure:* the file's `header` field says so in its
first two keys, and `run_baseline.py` prints "NOT EVIDENCE FOR THE THESIS" as its banner.
This is the number most likely to be quoted out of context, so it was made hard to quote
without the disclaimer.

**5.10 The attack with no countermeasure.** Arm E's advantage could come from "structured
formal notation helps", not from "*these* structural choices help". Arms B, C and D use
notations with enormous pretraining representation; arm E uses one invented weeks ago.
Nothing in this protocol separates those hypotheses, and I could not design an arm that
does. Protocol §9.1 states this plainly rather than hiding it. Any positive result must
carry it.

**5.11 The methodological conclusion of this review, which is not about metrics.**
Thirteen semantic holes were open when this review began and all thirteen were closed
before it ended, most within minutes of being written down. That is a fast and serious
response and it should be said plainly. It is also the finding with the longest half-life,
for three reasons.

*First:* every one of the thirteen was reachable by a few lines of adversarial input, and
none was found by the existing suite, which was green throughout — 594 tests passing at T3.
A test suite that is written alongside an implementation tests what the implementer
imagined. §1.5 is the sharpest case: a *property-based* test, the technique specifically
meant to escape that limitation, was passing while the property was false, because its
generator did not produce the failing binder form.

*Second:* claims outran the implementation in at least three places (§3.2), and in the worst
case (§1.8) a docstring asserted a check that did not exist. That is a systematic hazard for
this project in particular, because its entire pitch is that structure is *stated* rather
than inferred. A repository whose stated structure is not enforced is making the same
mistake it accuses prose of making.

*Third, and this is the part that bears on the benchmark:* a red-team pass concurrent with
active development produces a corpus and a protocol calibrated against a moving instrument.
Every number in `evaluation/results/baseline.json` was produced against T3 and is
reproducible only against T3. Protocol §12 therefore pins a fingerprint, and
`tests/adversarial/` used `xfail(strict=True)` throughout so that a fix would announce
itself as a failure rather than decay into a stale comment. Both mechanisms worked: the
xfails converted to passes and were removed once the defects were fixed. **Any future run
must re-fingerprint before it reports.**

---

## 6. The strongest argument that this project will fail

Not hedged, as instructed. This is the case I would make if I were reviewing a paper.

**The project has mistaken a property of the artefact for a property of the reasoner.**

The thesis is that eliminating re-inference improves reasoning. The engineering that
follows from it makes structure explicit *in a file*. But the inference the thesis wants to
eliminate does not happen when a file is read — it happens when the file is **written**.
Somebody, or something, had to decide that `jitter` is a scale rather than a variance
before `scale := jitter` could be typed. Every one of the six commitments in `GOAL.md` §2 is
resolved by the author of the `.hml` file, not by the language. The language records the
decision; it does not make it, and it cannot check it, because the prose the decision came
from is not in the file.

So in the actual experiment the model is asked to translate prose into Hamiltonian Lang and
is then scored on the translation. The hard step — reading "standard deviation" and knowing
it is not a variance — is upstream of every guarantee the compiler offers. If the model gets
that step wrong, it emits `Normal(location := drift, scale := jitter)` with `jitter` bound
to a variance, and the file compiles clean, hashes correctly, renders beautifully into three
views, and is wrong. **The compiler cannot catch a correct-looking encoding of a
misunderstanding, and misunderstandings are the failure mode the project was built to fix.**
§1.5 is the concrete demonstration: `Uniform(lower := 5.0, upper := 1.0)` is a perfectly
well-labelled encoding of an impossible object.

The second blade. Where the language *does* catch things — undischarged obligations,
dimensional mismatches, scope order — the value is real but it is not new. Stan has had
constrained types for fifteen years. Lean has had dependent types and a kernel for longer.
`pint` has had dimensions since 2012. The genuinely novel commitments are mandatory role
labels and one canonical form addressing many backends. Mandatory role labels are a good
idea whose benefit is bounded by how often role confusion is the binding constraint on a
frontier model's accuracy — and that is an empirical quantity nobody has measured, which
may well be small, and which is being *assumed* by the decision to build a language around
it. The one-canonical-form claim is the more interesting one, and it is the one v0 has done
least to test: the Lean backend emits `sorry`, the Stan backend cannot express dimensions,
and no round trip through any backend has been shown to preserve meaning. `GOAL.md` §8
failure condition 4 is "translation loss: round-tripping through the semantic core changes
the meaning" — and the only round trip currently tested is HML → HML, which is the one that
cannot lose anything.

The third blade, and the one that actually decides it. Suppose the experiment runs and arm E
wins. Failure condition 3 asks whether a prose arm with the same structural prompting closes
the gap. My honest prior — and I am labelling this **ESTIMATE**, because no measurement
exists — is that arm A′ closes most of it. The checklist in protocol §9.1 asks a model to
state each variable's type, domain, constraints, distribution roles, bindings and quantifier
order. That is the *entire semantic content* of a Hamiltonian program, delivered as a
prompt, in prose, at a fraction of the engineering cost. If a checklist buys 90 % of the
benefit, the correct conclusion is that the finding is about eliciting structured reasoning,
not about representing it — and the correct artefact is a prompt, not a compiler. The
project's own falsification criteria say this, clearly, in advance. That is to its enormous
credit. It is also, in my judgement, the most likely thing to happen.

**What would change my mind.** Three results, in order of how much they would move me:

1. Arm E beats arm A′ on H2 (quantifier scope) by more than 15 points. Scope is the one
   place where a *structural* representation should beat a *checklist*, because order is
   carried by the tree rather than by a sentence the model has to keep consistent.
2. A demonstrated round trip HML → Lean → HML, or HML → Stan → HML, that preserves the
   content hash on a non-trivial corpus. That would substantiate the one-object-many-views
   claim, which is the actual novel contribution, and it is testable today without any model.
3. H4 showing that the *repair loop* contributes independently of the k=0 gap — i.e. that
   compiler feedback teaches the model something a checklist cannot. That would be a
   genuinely new result about tool-augmented reasoning, and it is the outcome that would
   justify having built a compiler rather than written a prompt.

None of the three requires a model to run item 2. I would do that one first.
