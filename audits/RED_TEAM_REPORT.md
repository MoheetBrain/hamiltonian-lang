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

## 1. Semantic holes

Constructs that parse and type-check and mean something wrong, ambiguous, or nothing at
all. Each is reproduced as an `.hml` snippet that **survives `hml check`** and should not.
Each has a corresponding `xfail(strict=True)` in `tests/adversarial/`.

### 1.1 (CLOSED during this session) Refinement types and negative literals

Recorded because it shows the shape of the risk, not because it is open. At 19:5x,
`param s : PositiveReal = -1.0` compiled clean: unary minus returned its operand's type
unchanged, so `-1.0` inhabited `PositiveReal`, and `sqrt(-4.0)` and `log(-1.0)` type-checked
for the same reason. The flagship worked example in `GOAL.md` §2 — six commitments, of
which #6 is "σ > 0 is a **required constraint**, silently assumed" — failed on the
simplest possible instance of its own headline case. Re-measured at 20:12:47: all three are
now rejected (`HML-T402`, `HML-T413`, `HML-T427`). Regression guards are in
`tests/adversarial/test_rejections.py`.

The lesson is not "a bug existed". It is that the *type system was never the thing doing
the work* for positivity — the positivity obligation is generated and left undischarged
either way (`hml obligations` still reports `s > 0 : NOT DISCHARGED`), and the only reason
the bad program was caught in the end was a literal-typing rule. A checker whose refinement
guarantee rests on literal special-casing will keep producing this class of hole.

### 1.2 (OPEN) A value may take a distribution family's name, silently

```hml
module M
param Normal : Real
var X : RandomVariable[Real]
law X ~ Normal(location := 0.0, scale := 1.0)
```

Compiles clean. `Normal` is simultaneously a real-valued module parameter and the
distribution family used on the next line. The parser routes any call with labelled
arguments straight to the distribution registry without consulting the symbol table, so
family names and value names occupy disjoint namespaces with no diagnostic and no note.

Why it is a design hole and not a nit: governing principle 2 is "every relation has
defined semantics". Here a relation (`~`) resolves its right-hand operand by a rule that is
never stated anywhere in the freeze document, and a reader of the source cannot tell from
the text which `Normal` is meant. Compare Stan, which rejects a variable named after a
built-in distribution, and Lean, where a shadowing definition would at least be resolvable
by the elaborator's stated rules.

### 1.3 (OPEN) Concept cycles of length ≥ 2

```hml
module M
concept A extends B
    parameter p : Real
    invariant i := p > 0.0
end
concept B extends A
    parameter q : Real
    invariant j := q > 0.0
end
```

Compiles clean. `Resolver.visit_concept` tests `if st.name in st.extends`, which catches
`A extends A` (`HML-S602`) and nothing longer. A circular concept lattice is not a
definition, and governing principle 4 — "every new concept has a formal definition" — is
enforced only against the length-1 cycle. The fix is a standard SCC check over the
`extends` edges; its absence is not a subtle problem.

### 1.4 (OPEN) Definition cycles, contradicting a docstring

```hml
module M
param a : Real
def f := g + a
def g := f + a
```

Compiles clean. Both `f` and `g` receive inferred types from a derivation with no base
case. `src/hamiltonian_lang/semantics/__init__.py` line 11 states, verbatim:

> `  pass. Order still matters for *definition* cycles, which are detected separately.`

No such detection exists anywhere in the package. Governing principle 3 is "every inference
has traceable dependencies"; here the dependency graph has a cycle and nothing objects.
This is worse than 1.3 because the documentation asserts the check exists, so a reader
building on it is actively misled.

### 1.5 (OPEN) Distribution parameters are checked in isolation, never against each other

```hml
module M
var X : RandomVariable[Real]
law X ~ Uniform(lower := 5.0, upper := 1.0)
```

Compiles clean, generates no obligation, and denotes a law over the empty set. Likewise:

```hml
module M
obs trials : Natural = 5
obs successes : Natural = 9
likelihood successes ~ Binomial(trials := trials, prob := 0.5)
```

Compiles clean, with 9 successes in 5 trials.

Each role's type is checked independently against `DistributionSpec.roles`. There is no
mechanism — not even an obligation, which is the cheap option and would fit the existing
design perfectly — for a *cross-role* constraint such as `lower <= upper`. This is the
sharpest hole in the report, because role labelling is the load-bearing design decision
(D-003) and the freeze document calls it "the single largest semantic-explicitness win in
the design". Role labelling buys correct *identification* of parameters and buys nothing
about their *joint admissibility*. Stan's `<lower=,upper=>` bounds do not solve this either,
but Stan at least fails at run time on an empty support, whereas here nothing ever fails.

### 1.6 (OPEN) `prior`, `likelihood` and `law` are decorative

```hml
module M
obs y : Real = 3.0
prior y ~ Normal(location := 0.0, scale := 1.0)
```

Compiles clean: a *prior* on *observed data*. `LawStmt.role` is recorded on the statement
and threaded into the graph as an edge label, but it is never checked against the
declaration kind of its target. The three keywords exist to draw a distinction the checker
does not draw. Either they should be enforced (a `prior` targets a non-`obs` symbol; a
`likelihood` targets one that is observed or conditioned) or they should be removed as
surface sugar — but a keyword that looks like a semantic commitment and is not one is
exactly the implicit-structure problem the project exists to attack, reintroduced by the
project.

### 1.7 (OPEN) Only one of five inference queries is well-posedness-checked

```hml
module M
param t : Real
infer mle t
```

Compiles clean. `infer posterior` on a symbol with no law is correctly rejected with
`HML-S604` and a good diagnostic ("a posterior requires a prior; without one this query is
not well posed"). The same argument applies verbatim to `mle`, `map`, `expectation` and
`variance`, and none of them is checked. The guard was written for one case and not
generalised.

### 1.8 (OPEN) `UnknownType` survives a clean check, contradicting a stated invariant

```hml
module M
index K : Natural
var w : Vector[Probability, K]
require sum(w) = 1.0
```

Compiles clean. `sum` is whitelisted in `semantics._BUILTIN_FUNCTIONS` (so resolution
passes) but absent from `type_system._BUILTIN_SIGNATURES` (so `_call_type` returns
`UnknownType`). `is_subtype` returns `True` whenever either side is `UnknownType`, so the
comparison succeeds and the checker has in fact typed nothing.

`src/hamiltonian_lang/ast/nodes.py` line 16 states the invariant, verbatim:

> `* every node has a non-None `` type_ `` (no ``UnknownType`` survives);`

It does not hold. The permissiveness of `UnknownType` is defensible *during* inference; the
absence of a final sweep that reports any `UnknownType` still standing at the end is not —
and the type checker's own docstring says such a sweep exists ("the checker separately
reports any Unknown that survives to the end of checking", `types.py`). It does not.

### 1.9 (OPEN) Definition parameters are not alpha-normalised

```hml
def f(u : Real) : Real := u + 1.0
def f(w : Real) : Real := w + 1.0
```

Different content hashes. `backends/canonical.py` serialises a `Definition`'s parameters as
`[{"name": n, "type": ...}]` — the raw spelling — while every other binder is projected to
`sym:#<depth>.<ordinal>`. The freeze document, §5 line 122, states:

> `canonical hash. Property-tested in ``tests/roundtrip/``.`

The property test exists (`tests/roundtrip/test_roundtrip.py::test_alpha_renaming_invariance_property`)
and is genuine, but it generates only `param` and `def`-name binders. It does not generate
the one binder form that fails. This is the most instructive finding in the report: **a
green property-based test suite was not evidence, because the generator did not reach the
defect.** Any future claim of the form "property-tested" must state the generator's
coverage, not just its existence.

### 1.10 (OPEN, by design, but a trap) Ordinals are positional, so the content hash is edit-fragile

Measured: inserting an unrelated declaration anywhere above a referenced symbol changes the
hash of the whole module; so does appending one. `SymbolId.ordinal` is assigned in
declaration order, so `sym:#0.2` means "the third thing declared", and any edit above it
renumbers everything below.

This is a correct consequence of the design, not a bug. It is listed because the freeze
document §7 advertises the hash as "Suitable for equality testing, deduplication, and
**dataset keys**", and `README.md` line 65 describes it as "invariant under renaming,
sensitive to structure". Both are true; neither warns that the hash is also sensitive to
*insertion position*, which is what actually breaks a dataset key in practice. A
content-addressed corpus built on this will churn on every unrelated edit.

### 1.11 (OPEN) Concept members are barely checked

All three of these compile clean:

```hml
concept C
    parameter p : Real
    transform t(u) := p          # ignores its own argument
    invariant i := t(p, p) = p   # called with the wrong arity
    counterexample bad := p > 0.0  # identical to the invariant it is meant to refute
end
```

`HML-S605` warns about a transform with *no* parameters, but a transform that declares a
parameter and ignores it is silent, arity is not checked at the call site, and a
`counterexample` is never required to differ from — let alone contradict — the invariants.
`GOAL.md` §4's corollary demands "testable consequences" and says "Plausibility is not
admissible evidence". `HML-S603` enforces that a concept has *at least one* invariant or
example, which is a presence check, not a content check. A concept can satisfy the letter of
the rule with an invariant and a counterexample that assert the same proposition.

---

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
than the evidence supports. All line numbers as of the fingerprinted tree.

**3.1** `src/hamiltonian_lang/semantics/__init__.py:11`

> Order still matters for *definition* cycles, which are detected separately.

**False.** No cycle detection exists. Measured: §1.4 above.

---

**3.2** `src/hamiltonian_lang/ast/nodes.py:16`

> every node has a non-None ``type_`` (no ``UnknownType`` survives);

**False** as a post-condition of a successful check. Measured: §1.8 above.

---

**3.3** `docs/design/V0_DESIGN_FREEZE.md:122`

> canonical hash. Property-tested in `tests/roundtrip/`.

**Misleading, not false.** The test exists and is real, but its generator does not cover
definition parameters, which is the binder form that violates the criterion. Measured:
§1.9. The remedy is a sentence stating what the generator covers.

---

**3.4** `src/hamiltonian_lang/type_system/distributions.py:9`

> targeted error for these is the clearest single demonstration of the project thesis:

**Unsupported.** The thesis is that an AI system reasons more accurately through this
representation. A targeted error message demonstrates that *the compiler* distinguishes
`scale` from `variance`. Whether that changes a model's accuracy is H3/H4 and is unmeasured.
This is a claim about a demonstration of a thesis, made in a file that contains no
measurement. The freeze document is scrupulous about this ("No superiority claim is made
anywhere in this repository"); this docstring is not.

---

**3.5** `src/hamiltonian_lang/type_system/__init__.py:11`

> directive are unrepresentable rather than merely discouraged.

**Overreach in the general case, though narrower than it reads.** The three prohibited
conflations of `RandomVariable[T]` / `Distribution[T]` / `T` are indeed structurally
blocked, and I verified `HML-T410`, `HML-T428` and `HML-T430`. But "unrepresentable" is
falsified by §1.2: a symbol can be named after a distribution family and coexist with it,
which is a conflation of a *name* for a value with a *name* for a law. The freeze document
itself models the right behaviour here — §2 lines 68–70 explicitly withdraw an earlier
"cannot be expressed" claim as having "overstated the grammar's role". That withdrawal
should be propagated to this docstring.

---

**3.6** `README.md:65`

> | `hml hash FILE` | content hash — invariant under renaming, sensitive to structure |

**Incomplete in a way that misleads.** True for the binders tested; false for definition
parameters (§1.9); and silent about insertion-position sensitivity (§1.10), which is what
will actually bite a user who treats the hash as a stable key.

---

**3.7** `docs/design/V0_DESIGN_FREEZE.md:72`

> Cost, now measured rather than assumed: **+4 tokens per law statement, ≈5.9% of a

**Cannot be verified as stated, and probably should not be stated.** No tokenizer is named.
`tiktoken` is **not installed in this repository's `.venv`** (measured:
`ModuleNotFoundError: No module named 'tiktoken'`), so any token count produced in this
repository today is tokenizer-dependent and approximate — my own harness labels its numbers
`APPROXIMATE` for exactly this reason. A figure quoted to two significant figures, in a
frozen design document, with no tokenizer named and no artefact to reproduce it, is not
"measured rather than assumed" in any useful sense. Name the tokenizer and the corpus, or
give a range.

---

**3.8** A claim that is *correctly* scoped, recorded so this section is not one-sided

`README.md`:

> **No comparative evaluation has been run.** […] Nothing in this repository should be read
> as evidence for it.

This is exactly right and it is prominent. `GOAL.md` §8 and §13 are likewise unusually
disciplined about falsification. The claim hygiene at the document level is good; the drift
is in docstrings, which are where claims go to escape review.

---

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
