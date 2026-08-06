# Decisions

Format per §23 of the master directive. Reversal cost is stated because when uncertain we
prefer reversible choices.

---

## D-001 — Implementation language

**Question.** What should v0 be written in?
**Options.** Python · Rust · OCaml · TypeScript.
**Evidence.** The consumers of this work are ML evaluation harnesses and the Stan/SymPy
ecosystems, all Python-native. No performance requirement exists at v0 scale.
**Chosen.** Python ≥3.11, standard library only for the core.
**Rejected.** Rust (no requirement justifies the cost); OCaml (ecosystem mismatch).
**Confidence.** High. **Reversal cost.** Medium — the IR is data, the algorithms are small.

---

## D-002 — Canonical alphabet is ASCII; Unicode is display only

**Question.** Should Unicode mathematical notation be canonical, accepted, or rejected?
**Options.** (a) Unicode canonical · (b) ASCII canonical, Unicode accepted and folded ·
(c) ASCII only, Unicode rejected.
**Evidence.** U+03BC (μ) and U+00B5 (µ) are visually identical and both plausible model
outputs; NFC/NFKC normalisation is not idempotent across all mathematical characters;
byte-level hashing and diffing require a stable encoding.
**Chosen.** (b). Unicode identifiers fold to ASCII with warning `HML-L102`; Unicode
operators normalise with `HML-L103`; anything else is `HML-L101`.
**Trade-off.** Slightly more lexer complexity in exchange for eliminating an entire class
of identity bug rather than mitigating it.
**Confidence.** High. **Reversal cost.** Low.
**Required experiment.** Tokeniser fragmentation study — assigned to the alphabet agent.

---

## D-003 — Distribution arguments are role-labelled, and labels are mandatory

**Question.** Should `Normal(mu, sigma)` be permitted?
**Chosen.** No. Positional distribution arguments are a parse error (`HML-P234`).
**Evidence.** The scale-vs-variance ambiguity is a documented source of error across
statistical libraries (R and NumPy take sd; some texts and MATLAB take variance).
**Trade-off.** Costs tokens. That cost is measured under H5, not assumed away.
**Prior art (added after Wave 1).** PyMC already uses named parameters
(`mu=`, `sigma=`, `tau=`) and SciPy uses `loc`/`scale`. **The mechanism is not novel.**
What differs is that labels are *mandatory* rather than conventional, and that alternative
parameterisations are prohibited rather than offered. This is a policy hardening, not an
invention, and must be described as such.
**Confidence.** High on the mechanism, low on the value — H5 may show the token cost
exceeds the benefit.
**Reversal cost.** Medium — relaxing to optional labels is easy; the canonical form and
every backend already key on roles.

---

## D-004 — The scalar order is a poset, not a chain

**Question.** How do `Probability`, `PositiveReal` and `Natural` relate?
**Chosen.** `Probability` and `PositiveReal` are **incomparable**. 0 is a probability and
is not a positive real; 2.0 is a positive real and is not a probability. They meet at
`NonNegativeReal`.
**Consequence.** `PositiveNatural` was added as the meet of `Natural` and `PositiveReal`,
so that the literal `1` can inhabit both a count role and a scale role.
**Confidence.** High — this is mathematics, not preference.
**Reversal cost.** High. Linearising the order would silently admit unsound programs.

---

## D-005 — Hybrid binding: readable names, structural identity

**Question.** De Bruijn indices, locally nameless, unique IDs, or plain names?
**Chosen.** Surface syntax uses names. The resolver assigns
`SymbolId(name, ordinal, depth)`. Canonicalisation projects to `sym:#depth.ordinal`,
discarding spelling.
**Effect.** Alpha-renaming invariance without forcing De Bruijn indices on the author.
Property-tested in `tests/roundtrip/test_roundtrip.py`.
**Confidence.** High. **Reversal cost.** Medium.

---

## D-006 — Shadowing is an error, not a warning

**Question.** May an inner binder reuse an outer name?
**Chosen.** No — `HML-N302`.
**Rationale.** The directive requires the language to *prevent* silent scope changes. A
warning prevents nothing.
**Known cost.** This is stricter than most languages and will annoy authors who reuse `i`
or `x` across quantifiers. If benchmark H1 shows the strictness produces no measurable
binding-accuracy gain, relax it to a warning.
**Confidence.** Medium. **Reversal cost.** Low.

---

## D-007 — Blocks close with `end`, not by indentation

**Question.** Should `concept` bodies be indentation-delimited?
**Chosen.** Explicit `end`.
**Rationale.** Whitespace-significant semantics degrade under copy/paste and under model
generation, and the failure is silent. An unclosed `end` is a loud, locally-reported error
(`HML-P210`).
**Confidence.** High. **Reversal cost.** Low.

---

## D-008 — Module scope is order-independent

**Question.** Must a symbol be declared before use?
**Chosen.** No. Module-level binders are collected in a first pass.
**Rationale.** A declarative mathematical model should not depend on statement order for
visibility. Order still matters for declaration *ordinals*, and therefore for the
canonical hash of programs whose declarations have different types.
**Confidence.** Medium. **Reversal cost.** Low.

---

## D-009 — Literals are checked by value, not by nominal type

**Question.** Should `const p : Probability = 1` type-check?
**Chosen.** Yes. When an expression is a numeric literal, its exact value is checked
against the target refinement predicate rather than its nominal type.
**Rationale.** The nominal type of `1` is `PositiveNatural`, which is not a subtype of
`Probability`, yet the value 1 plainly is a probability. Refusing it would be a false
negative caused by an artefact of nominal typing.
**Confidence.** High. **Reversal cost.** Low.

---

## D-010 — Names are excluded from the content hash

**Question.** Should the canonical JSON carry declaration names?
**Chosen.** Human-facing canonical JSON keeps names; `content_hash` serialises without
them.
**Rationale.** v0 success criterion 6 requires renaming invariance. Keeping names in the
hashed form violated it, which the property test caught.
**Confidence.** High. **Reversal cost.** Low.

---

## D-011 — Provenance is deferred out of v0 *(added after Wave 1 prior-art review)*

**Question.** `GOAL.md` §5 states that Layer 2 records provenance. It does not.
**Finding.** `ast/nodes.py` carries `Span` and `type_` only. There is no derivation
record and no dependency-provenance edge.
**Chosen.** Record the gap honestly rather than claim the capability. Provenance is listed
under "explicitly unsupported in v0" in the freeze document. The semantic graph's
`depends_on` / `conditioned_on` edges provide dependency tracking but **not** derivation
history.
**Confidence.** High. **Reversal cost.** Low — additive.

---

## D-012 — The claimed contribution is demoted from the representation to the experiment *(added after Wave 1)*

**Question.** Is the three-layer typed-semantic-core architecture a novel contribution?
**Evidence.** Prior-art review found no structurally new construct in Layer 2. Rocq's own
documentation describes surface-to-kernel translation as *the de Bruijn criterion*, a
named principle. Lean 4's `Syntax`→`Expr` elaborator is the same architecture. OpenMath
Content Dictionaries already mandate formal-property and example fields. Content MathML
has carried `domainofapplication` and `condition` since 1998. MMT/OAF has already exported
Isabelle, the AFP and the Coq library as theory graphs.
**Chosen.** The architecture is **apparatus, not contribution**. The only defensible
residual novelty is the *experiment*: a matched multi-arm comparison with deterministic
scoring in which the representation is the independent variable. Documentation must say
this.
**Confidence.** High on the prior art; the novelty of the experiment is marked UNVERIFIED
(a negative result from targeted search is weak evidence).
**Reversal cost.** None — this is a claim correction, and correcting it costs nothing but
the story.
**Consequence.** `GOAL.md` §5 calls Layer 2 "the actual contribution". That line is now
contradicted by evidence in this repository and should be revised by the project owner.

---

## D-013 — `!` and `?` remain reserved and unused *(added after Wave 1)*

**Finding.** `!` is the annotation operator in SMT-LIB 2 (§3.6). Assigning it a
proof-obligation meaning would collide with a target format.
**Chosen.** Both stay reserved and unassigned in v0. Revisit only with a concrete
requirement and a note on the SMT-LIB collision.
**Confidence.** High. **Reversal cost.** None — nothing depends on them yet.

---

## D-014 — The frozen alphabet and grammar survive measurement *(added after Wave 1)*

**Question.** Was ASCII-canonical, labelled-linear, `end`-delimited (D-002, D-003, D-007)
the right choice, or did it just feel right?

**Evidence — measured, 8 real tokenisers** (tiktoken cl100k/o200k/p50k/r50k, HF
gpt2/Llama-2/gpt-neox-20b/starcoder2; Llama-3 was gated and is excluded from every
aggregate rather than estimated):

- **Weighted scores.** A (labelled-linear) 115/125 · C (S-expression) 101 · E (triples) 93
  · B (symbolic ASCII) 90 · D (indentation) 68.
- **Terseness does not pay.** Candidate B is 36.5% shorter in characters and saves only
  3.1% of tokens on average — and that average hides a 4–4 split, with B *losing* on p50k,
  r50k, gpt2 and gpt-neox-20b. B's digraphs `:<` / `:>` cost 2 tokens where A's whole words
  ` prior` / ` likelihood` cost 1. Fragmentation: B 0.401 tokens/char vs A 0.279.
- **A wins the two criteria the thesis actually cares about:** silent-meaning-change rate
  9.88% (best of five) and error-localisation precision 96.5%. C's disqualifier is
  measured, not asserted: only 51.5% of its detected errors land on the right line,
  because a dropped parenthesis surfaces at end-of-file.
- **Unicode display-only is now evidenced, not assumed.** `⇒` costs 3 tokens in 5 of 8
  tokenisers against 1 for ASCII `=>`; `∏` costs 4 under Llama-2. Of 17 confusable pairs,
  NFC resolves 2, NFKC resolves 4, and **13 survive both**. gpt-neox-20b assigns identical
  token ids to Ω/Ω and Å/Å — a Unicode-canonical form would not be injective under that
  tokeniser.

**A prediction of mine that was wrong.** I expected indentation-based candidate D to fail
on whitespace damage. All 560 dedent trials were *detected*. D fails worse for a different
reason: **100% of closing-bracket deletions silently changed meaning, 0% detected**,
because every bracket in D sits inside a quoted expression string that the YAML layer
cannot see into. The conclusion (avoid D) stands; my reasoning for it did not.

**Chosen.** Keep D-002, D-003 and D-007 as frozen. The freeze is retained on evidence
rather than on intuition.
**Confidence.** High for the ranking. **Reversal cost.** Low — the candidates and the
harness are retained in `experiments/alphabet/` and `examples/candidate_syntaxes/`.
**Consequence.** Freeze §2's claim that the sd-vs-variance ambiguity "cannot be expressed"
was **false as written** and has been narrowed: the grammar permits
`Normal(location := mu, variance := s)`; the *type system* rejects it. Both mechanisms are
needed and the document now says which does what.

---

## D-015 — Concept transform parameters may be typed *(added after Wave 1)*

**Question.** `transform standardise(u) := (u - location) / scale` binds `u` with no type.
Governing principle 1 says every object has a type. Which gives way?

**How it surfaced.** The grammar agent, reconstructing HML-L1 from the freeze document,
wrote `transform standardise(x : Real) := ...`. The implementation rejected it with
`HML-P201`. The agent's reading was the better one: the freeze was under-specified and the
implementation was inconsistent with its own stated principle.

**Chosen.** `ConceptMember.params` changes from `list[str]` to
`list[tuple[str, Type | None]]`, matching `DefineStmt.params`. The annotation is optional,
because the type is usually inferable from use; the *slot* is mandatory, because the
principle says so.

**Contract impact.** This is a change to the frozen IR (`ast/nodes.py`) and to the
canonical form. It was caught by `tests/golden` as a changed content hash for
`examples/concepts/location_scale_family.hml` — which is what that tripwire exists for.
Re-blessed deliberately, with this record as the justification.

**Also touched.** `parser`, `semantics` (transform parameters now carry their declared type
into the symbol table), `backends/canonical.py`, `backends/hml.py`, `backends/english.py`.
`ConceptMember.param_names()` added for consumers that only want the names.

**Confidence.** High. **Reversal cost.** Low, but non-zero — it is an IR change, so any
stored canonical JSON for concepts predating it is stale.

---

## D-016 — Eight red-team defects resolved *(added after Wave 2)*

The adversarial reviewer measured eight programs that passed `hml check` and should not
have. All eight are now rejected. The reviewer holds veto over *claims*; the Lead
Architect resolves *implementation* — this is that resolution.

| # | defect | resolution | code |
|---|--------|-----------|------|
| 1.2 | `param Normal : Real` coexisted silently with `law X ~ Normal(...)`; family and value namespaces were disjoint | one namespace: a symbol may not take a family's name | `HML-N307` |
| 1.3 | only length-1 concept cycles were caught (`A extends A`, but not `A extends B extends A`) | general cycle detection over the `extends` graph | `HML-S602` |
| 1.4 | definition cycles were **documented as detected** in a module docstring and were not | dependency graph + iterative DFS cycle detection | `HML-S606` |
| 1.5 | `Uniform(lower := 5, upper := 1)` — a law over the empty set — compiled clean | `cross_constraints` on `DistributionSpec`: decided when both sides are literals, obligated otherwise | `HML-T417` |
| 1.6 | `prior` on an `obs` compiled clean; the role keyword was never checked against the target's declaration kind | role/declaration-kind compatibility check | `HML-S607` |
| 1.7 | only `posterior` was guarded; `infer mle` with no likelihood compiled clean | all five query kinds require a law, each with its own reason | `HML-S604` |
| 1.8 | `UnknownType` survived a successful check, so `require sum(w) = 1.0` type-checked while nothing had been typed | real signatures for the aggregate builtins, plus a final pass rejecting any surviving Unknown | `HML-T450` |
| 1.9 | definition and transform **parameter names** were serialised into the hashed canonical form, so renaming a parameter changed a definition's identity | parameter binders are positional in the nameless form, like every other binder | — |

Two of these deserve comment.

**1.4 was a documentation lie.** `semantics/__init__.py` line 11 asserted that definition
cycles "are detected separately". No such detection existed anywhere. That is worse than a
missing feature, because a reader had no reason to doubt it.

**1.8's first fix was wrong and was replaced.** My initial response was to reject any
expression carrying `UnknownType`. That made `require sum(w) = 1.0` a *type error* — but
that expression is ordinary mathematics the language ought to express. The correct fix was
to give `sum`, `prod`, `mean`, `variance`, `expectation` and `transpose` real signatures.
The refinement behaviour is deliberate: `mean` of a `Vector[Probability]` is a
`Probability`, while `sum` of one is a `NonNegativeReal`, because a sum of probabilities
may exceed 1.

**Consequence for D-015.** Transform parameter annotations were optional there, on the
reasoning that the type was "usually inferable". Finding 1.8 showed it was never inferred —
it simply became `Unknown`. The annotation is now **mandatory** (`HML-P214`) and governing
principle 1 holds without exception.

**Method note.** The reviewer marked each case `xfail(strict=True)`, so fixing a defect
turned its test into a visible failure rather than a silent pass. That design is why all
eight fixes were noticed immediately. The markers have been removed and the provenance
kept in comments.

**Confidence.** High — each fix has an executable test. **Reversal cost.** Low.

---

## D-017 — Interface names are roles; only local binders are alpha-renameable

**Question.** Is `concept C { parameter location; ... }` the same object as
`concept C { parameter a; ... }`?

**Chosen.** No. A concept's parameter names are its **interface**, exactly as a
distribution's role names are (D-003). `LocationScaleFamily` parameterised by `location`
and `scale` is not the same concept parameterised by `a` and `b` — the names carry the
meaning. Renaming one changes the content hash, and should.

Local binders are the opposite and are normalised away:

| name | status | renaming changes the hash? |
|------|--------|---------------------------|
| module-level declarations | binder | no |
| quantifier variables | binder | no |
| definition parameters | binder | no |
| transform parameters | binder | no |
| **concept parameter members** | **role** | **yes** |
| **concept member names** (invariant, example, …) | **role** | **yes** |
| distribution roles | role | yes |

**How it surfaced.** Not from reasoning — from a test failing. Strengthening the
alpha-equivalence generator to cover every binder form (see below) produced a case that
looked like a ninth defect. Checking it against the D-003 principle showed the
implementation was already right and the *test* was wrong.

**Confidence.** High. **Reversal cost.** Low.

---

## D-018 — A green property test is only evidence about the inputs it reaches

Not a design decision; a method correction, recorded because it caused the
longest-lived defect in the session.

`tests/roundtrip` asserted v0 success criterion 6 — renaming invariance — with a
hypothesis property test. The test was real and passing. The criterion was **false**:
definition parameters were serialised by spelling, so `def f(u : Real) := u + 1.0` and
`def f(w : Real) := w + 1.0` hashed differently.

The test passed because its generator produced only module-level `param` declarations. It
never generated the one binder form that was broken. Nobody was lying and nothing was
skipped; the suite was green and the property did not hold.

**Correction.** The property is now parameterised over an explicit list of *every* binder
form, with a companion test asserting each template actually compiles — because a template
that silently fails to compile makes the property vacuously true, which is the same
failure one level up.

**Standing rule.** When a test asserts a universal property, enumerate the constructors it
must reach and assert that it reached them. Coverage of the generator is part of the
claim, not an implementation detail.

---

## D-019 — Lexer non-termination on non-ASCII letters *(implementation bug, fixed under freeze)*

**Severity.** The compiler hung forever — not an incorrect answer, an unbounded one.

**Reproducer.** `hml check` on a file containing `ℝ`, or any Unicode letter absent from
`UNICODE_FOLD`. Minimal case: a file containing only `ℝ`.

**Cause.** `str.isalpha()` is true for every Unicode letter, so the dispatch
`if ch.isalpha() or ch == "_"` routed U+211D into `_identifier()`. That routine accepts
only ASCII alphanumerics and folded Greek, so it consumed **zero** characters, emitted an
empty token, and returned. The caller then re-dispatched on the same character. Forever.

**How it surfaced.** Not from a test. The pre-evaluation audit fed each backend's output
back through the parser to separate *rendering* from *round-tripping*; the Lean backend
emits `variable (theta : ℝ)`, and the audit command hung.

**Why it mattered more than it looks.** The evaluation harness feeds model output to the
parser. Models emit `ℝ`, `∈`, `∀` and Greek constantly. The first such generation would
have hung the run with no timeout and no diagnostic — silently destroying the experiment
rather than failing it.

**Fix.** Two changes, deliberately redundant:

1. the ASCII test now precedes the alphabetic test in the dispatch;
2. `_identifier()` asserts progress: if it consumed nothing it emits `HML-L101` and
   advances one character. A lexer routine must never consume zero input, whatever the
   dispatch above it believes.

**Regression tests.** `tests/parser/test_parser.py::test_lexer_terminates_on_unfolded_non_ascii_letters`
(8 cases including CJK and mathematical italic pi) and
`::test_lean_backend_output_does_not_hang_the_parser`.

**Effect on prior benchmark items.** None. No existing benchmark item, example or test
contains an unfolded non-ASCII letter, so no previously recorded result changes. Verified:
all example hashes and the golden snapshot are unchanged and the full suite passes.
**No benchmark-version increment is required.**

**Freeze status.** Permitted under `hml-v0-eval-freeze` as a demonstrated implementation
bug. No syntax or semantics changed: input that previously hung now produces the
diagnostic it always should have.

**Confidence.** High. **Reversal cost.** None.

---

## Open questions

---

## D-020 — Inference queries do not share a precondition *(implementation bug, fixed under freeze)*

**Question.** D-016 finding 1.7 made every `infer` query require its target to carry a
probability law. Was that right?

**No — it was an over-correction, and it rejected the most common frequentist model in
statistics.** `infer mle p`, where `p` appears in `likelihood germinated | p ~ Binomial(…)`,
was rejected with `HML-S604`. A maximum-likelihood estimate is defined by the likelihood of
the *data given* the parameter; the parameter itself carries no law. Demanding one confuses
the MLE with the posterior.

**How it surfaced.** Not from review. Building the HML-EVAL-001 corpus, a generated
problem stated "the germination probability is not known and is to be estimated from this
data" — no prior. The faithful encoding is an MLE, and the compiler refused it. Encoding a
prior instead would have made the Hamiltonian arm say more than the problem does, which is
exactly the information asymmetry §4 forbids.

**Corrected rule.** The five queries have three different preconditions:

| query | precondition |
|-------|--------------|
| `posterior`, `map` | the target has a **prior** |
| `expectation`, `variance` | the target has **a law** |
| `mle` | the target has a law **or appears in the conditioning set of some likelihood** |

**Regression tests.** Four, in `tests/type_system/test_types.py`: the MLE case now
accepted; MLE with no likelihood anywhere still rejected; MLE where the likelihood does not
mention the target still rejected; and `posterior` still requiring a prior even when a
likelihood exists — which is the test that pins the three preconditions apart.

**Effect on prior benchmark items.** None recorded before this change relied on the
rejection: the adversarial case `param t : Real; infer mle t` has no likelihood at all and
is still rejected. Verified: full suite green, no golden hash moved.
**No benchmark-version increment is required.**

**Freeze status.** Permitted under `hml-v0-eval-freeze` as a demonstrated implementation
bug. It widens what is accepted, so no previously valid program becomes invalid.

**Confidence.** High. **Reversal cost.** Low.

---

## Open questions

---

## D-021 — V0 is preserved as a baseline; V1 is a separate, additive, separately-tested language

**Question.** The pilot returned REDESIGN AND RETEST. Does that mean editing V0?

**No.** Editing V0 would invalidate the 221 stored model trials, which are the only
model-in-the-loop measurement this project has. V0 is tagged `hml-v0-baseline` and
`src/` is closed under it. V1 is a **new, additive** language specified in
`docs/design/V1_KERNEL.md`, and it must be *measured against* V0 rather than assumed to
improve on it.

**What V1 adds.** Four layers above V0's mathematical content: transformation edges (what
rewrites to what, with side conditions), inferential relations (what follows logically —
a *different* relation from rewriting), epistemic status (how strongly, on what grounds),
and discourse state (what remains to be shown).

**The governing admission rule.** A construct enters the kernel only if it changes what
the checker reports. "We now show" becomes `goal` because it opens an obligation. "For
completeness" stays in the renderer because it changes nothing. This rule exists because
the pilot demonstrated that surface area is not self-justifying.

**The load-bearing addition** is the epistemic layer, and specifically that
`fail_to_reject` returns `Evidence` while `prove` requires `Proof`, with **no coercion
between them**. `prove(fail_to_reject(H0))` becomes a type error. This applies V0's own
method — prohibit a conflation by giving the two things incompatible types — to the most
consequential misreading in applied statistics.

**A constraint adopted from the directive and made hard.** Concept families are
**declared, never generated**. `vary -> variance` is not a safe grammatical rule and
neither is `estimate -> estimator`. Productive morphology over mathematical vocabulary
manufactures plausible nonsense, so there is no suffix rule and no derivation engine;
`estimator`, `estimate` and `estimation procedure` are three independently declared types.

**Falsifiability.** Every layer carries its own kill criterion and is dropped
independently if it fails. Predicted survival order is recorded in advance
(`V1_EXPERIMENT_PLAN.md` §6) so a surprise is visible as one: L4 most likely, L3 least —
verifying inference chains without a prover approaches re-implementing one, which the
founding directive forbids.

**Honest prior.** V1 adds substantially more surface than V0, and V0's surface bought
nothing measurable. The reason to build it anyway is that V1's claims are *correctness*
claims checkable without a model in the loop, not reasoning-speed claims. **V1-H4 — that
the model can write V1 as reliably as V0 — is the hypothesis most likely to fail**, since
the model already wrote V0 unparseably 27–50% of the time.

**Confidence.** Medium on the design; low on the outcome, deliberately.
**Reversal cost.** None yet — nothing is implemented.

---

## D-022 — The unit interval carries three incomparable epistemic kinds

**Status.** Accepted 2026-08-05. **This is a semantic-contract change to `types.py`** and
is recorded here because `CLAUDE.md` requires it.

**Decision.** `PValue` and `PosteriorProbability` join `Probability` in the scalar
lattice. All three have `NonNegativeReal` as their **only** parent, so they are pairwise
incomparable and meet at `NonNegativeReal`. There is no subtyping path between any pair
in either direction. All three admit exactly the literals in `[0, 1]`.

**Why the language needed this and not only the library.**
`spec/v1/semantic_objects.yaml::kill_criteria.L4` recorded the p-value-as-posterior
conflation as "Now closed". It was closed in `src/hamiltonian_lang/v1/epistemic.py`, a
Python API, and open in Hamiltonian Lang: `param q : PValue` was `HML-T440: unknown type`,
so no HML program could state the distinction and `hml check` could not enforce it. A
kill criterion about the language met by a library is not met. The claim is corrected in
the spec rather than deleted.

**Why incomparable rather than a refinement of `Probability`.** Making
`PosteriorProbability <: Probability` reads plausible — a posterior *is* a probability —
and would immediately admit `def q : Probability := posterior`, which discards the prior
the posterior was computed against. `epistemic.py::probability_coercion_allowed` already
refuses every non-identity pair, including that one. The lattice now says the same thing.
This is the `Probability` / `PositiveReal` shape (design freeze §4) applied again: the
scalar order is a poset, and linearising it is the error.

**What this does not do.** A p-value *declared* as `Probability` and read as a posterior
still type-checks, because both sides genuinely are `Probability`. That is a modelling
error, not a type error. Inferring the epistemic kind from a symbol's spelling was
considered and rejected: this project does not decide semantics by spelling, and
`p_value`, `pval`, `p` and `sig` would all have to be guessed at. The residual is pinned
by `tests/freeze/test_quarantine.py::test_pin_a_mis_declared_p_value_is_still_admitted`
so it cannot be forgotten and reported as closed.

**Backends.** No target can express the distinction. Each now says so rather than erasing
it silently: SymPy, Stan and Lean `weaken()` with a named reason; LaTeX keeps
`\mathrm{PValue}` rather than collapsing to `[0, 1]`; English glosses the referent, not
the range. A backend that mapped `PValue` to the same text as `Probability` with no report
would be the failure mode `backends/base.py` exists to prevent.

**Cost of the addition** (`CLAUDE.md` rule 7 puts the burden on the addition): two scalar
names, two predicate entries, six conflation messages, five backend entries. No keyword,
no statement kind, no AST field, no grammar change. The L4 *layer* — `EpistemicStatus`,
`Justification`, `EpistemicClaim` — is untouched and remains `EXPERIMENTAL` and
unreachable from HML source.

**Confidence.** High that the lattice shape is right; it is the existing poset argument.
Medium on `PosteriorProbability`, which is required by the stated invariant
`PValue != PosteriorProbability` but has no probe of its own in the directive.
**Reversal cost.** Low-moderate. Removing the two scalars is a deletion from one table;
any program that used them stops compiling, and the freeze manifest and `frozen_subset.py`
must move back together.

---

## D-023 — A callable has a signature, and a definition body is checked, not compared

**Status.** Accepted 2026-08-05. Behavioural change to the checker; no contract file
altered.

**Decision, two parts.**

1. Every user-supplied callable — a parameterised `def`, and a concept `transform` —
   carries a `CallableSignature`: ordered parameter names, ordered parameter types,
   declared return type, and the defining `SymbolId`. A call is checked for callee
   existence, callability, **exact** arity, every argument contextually, and the declared
   return type. New codes: `HML-T470` (not callable), `HML-T471` (arity), `HML-T472`
   (argument).
2. `DefineStmt` routes through `TypeChecker.check` instead of a bare `is_subtype`, so
   `const p : Probability = 0.5` and `def p : Probability := 0.5` agree. `HML-T403` and
   its headline wording are retained.

**Why signatures are collected before checking begins.** Module scope is order-independent
(D-008), so a call may textually precede its definition. Resolving the signature lazily at
the call site would make enforcement depend on statement order — the bug D-008 exists to
prevent, reintroduced one level down.

**Why a codomain was not enough.** The old path returned `sym.declared_type.codomain` and
never looked at the arguments. A codomain answers "what does this produce"; enforcement
needs "what does this consume", which only the ordered parameters give.

**The diagnostic constraint, and why it is a measurement constraint.** These messages are
H3 machinery. H3 is verifier-guided repair; H1 and H2 are about the representation. A
diagnostic that contains the corrected program turns an H3 measurement into a
transcription test while telling us nothing new about H1 or H2 — and the three hypotheses
must stay separable, or a win on the verifier gets reported as a win for the language.
Every hint here is therefore a repair *class*: a parameter name, a type, a count, a
direction of edit. Never a value, never a corrected line. Asserted by
`tests/type_system/test_call_signatures.py::test_no_signature_diagnostic_leaks_a_repair`.

**One diagnostic-quality defect this change introduced and then fixed.** Routing
`DefineStmt` through `check` made the generic hint fire on a prohibited conflation,
emitting `declare 'pv : Probability'` — instructing a repair loop to commit the
prosecutor's fallacy on the compiler's own advice. `_repair_hint` now handles the
conflation case first and refuses the re-declaration shortcut.

**Confidence.** High. **Reversal cost.** Low for part 1 (delete the call-site branch);
part 2 is a two-line revert but would restore a measured inconsistency and should not be
reverted without one.

---

## Open questions

| id | question | blocked on |
|----|----------|------------|
| Q-01 | Does the mandatory-role token cost exceed its accuracy benefit? | H5 measurement |
| Q-02 | Is the shadowing prohibition (D-006) too strict in practice? | H1 measurement |
| Q-03 | Is OpenMath reusable? No licence statement was found on openmath.org. | legal review |
| Q-04 | Does arm E's out-of-distribution status confound every comparison? | benchmark design |
| Q-05 | Should `Call` arguments be role-labelled too, or only `DistExpr`? | usage evidence |
| Q-06 | Can the model write V1 at >=90% parse rate? If not, no V1 layer is testable. | V1-H4 |
| Q-07 | Does L3 inference checking reduce to re-implementing a prover (forbidden)? | L3 prototype |
| Q-08 | What corpus difficulty yields 50-60% baseline accuracy on gemma4:31b? | corpus redesign |

## D-024 — canonical include-names is a ContextVar, not a module global

**Date.** 2026-08-05 · **Status.** Accepted · **Touches the contract.**
`backends/canonical.py` is a semantic-contract file, so this record is mandatory
(`CLAUDE.md` rule 2).

**Problem.** `to_canonical` selected whether declaration names appear via a module global
with save/restore. That is reentrancy-safe and **not thread-safe**. `content_hash` always
forces names *off*; while one thread hashed, a concurrent
`canonical_json(..., include_names=True)` on another thread silently received the
**nameless** document. No exception, no diagnostic — an authoritative-looking wrong
answer, which `CLAUDE.md` names as the worst failure mode in this codebase.

Found by the M1 reproducibility audit: 8 hasher threads, a 600-statement module and
`sys.setswitchinterval(1e-6)` produced **1 corrupted named canonical form**.

**Decision.** Replace the global with
`ContextVar("hml_canonical_include_names", default=True)`. Each thread gets an independent
value; `set`/`reset(token)` preserves the reentrancy the global already had.

**Why now, given the milestone freezes rather than extends.** ACQ0 scores semantic
preservation by comparing canonical forms. The hazard was latent — the only existing
thread pool (`evaluation/syntax_gate/scorer.py::score_many`) reaches `compile_source` and
`render_module` but never canonicalisation — so nothing shipped was wrong. But the first
threaded scorer that canonicalises would have hit it, and the corruption is **silent**.
Fixing it before the tournament is far cheaper than discovering it in the results.

**Evidence the change is behaviour-preserving.** Content hashes byte-identical across the
change on `bayesian_coin` (`f79c553cca1adaa1…`), `quantifier_scope` (`8250373bb23c814a…`)
and `kinetic_energy` (`25efff792d32ccf0…`); `tests/roundtrip` and `tests/golden` pass
unchanged. The hazard probe reports 0 corrupted forms after the fix.

**On the regression test, honestly.** The stress test is a **weak** guard: the race window
is narrow enough that a deliberately reverted implementation survived 16 threads over a
2000-statement module in this session, and the original audit hit it only once. A test that
only sometimes detects the regression it exists for is decoration. The load-bearing guard
is therefore `test_the_include_names_flag_is_per_thread_by_construction`, which asserts the
flag *is* a `ContextVar` and that a second thread does not observe this thread's setting.
Verified against a simulated revert: it fires on both checks, every run. The stress tests
are retained as secondary evidence and labelled as such.

**Reversal.** Restore the module global and delete the two structural assertions. Reversal
reintroduces silent cross-thread corruption and must not be done to make a threaded scorer
simpler.

## D-026 — the partiality guard must follow definitions

**Date.** 2026-08-06 · **Status.** Accepted · **Closes falsifier finding F-2.**

**Problem.** `checkers.partiality_risk` had no `Ref` case, while `checkers._to_sympy`
inlines `env.definitions`. The guard therefore inspected a *different expression* from the
one SymPy decided, and one line of idiomatic HML defeated it:

```
prove x / x = 1          , x : Real   ->  UNSUPPORTED   (guard sees the `/`)
def q := x / x ; prove q = 1          ->  VERIFIED      (guard sees only `q`)
```

The second claim is **false at zero**, and `improvement.verification.classify` inherited
the unsound verdict, so the H3 primary endpoint could be reached by a false claim.
Generalises to `x ^ (-1)` and `x ^ 0`.

**Decision.** Add a `Ref` case that follows `env.definitions`, mirroring what `_to_sympy`
and `dimension_of_expr` already do. Guard and decision procedure now read the same
expression.

**Evidence.** `def q := x/x; prove q = 1` with `x : Real` -> `UNSUPPORTED`; with
`x : PositiveReal` -> `VERIFIED`. So this is a fix, not a blanket refusal: the guard still
lifts when the domain excludes zero. Regression controls hold — `2+2=4` VERIFIED,
`2+2=5` DISPROVED.

**Provenance, stated plainly.** The Lead had earlier verified "VERIFIED is reachable and
refusable" using only the *direct* form and reported it as such. That verification was
incomplete; the indirect form was not tested. The independent falsifier found it.

---

## D-027 — the Tier-1 name lock is the shared vocabulary, not exact equality

**Date.** 2026-08-06 · **Status.** Accepted · **Closes falsifier finding F-1.**

**Problem.** `matching.strict_match` enabled the module-level name lock only when the two
vocabularies were *exactly* equal. Renaming a single **unused** declaration disabled it,
and Tier 1 then certified a role swap:

```
p=>q vs q=>p, spare/spare   ->  VERIFIED_NONEQUIVALENT
p=>q vs q=>p, spare/filler  ->  VERIFIED_EQUIVALENT   {p:q, q:p, spare:filler}
```

That is a **false-positive equivalence** — the one error class the scorer's whole design
trades coverage to avoid, because it silently declares a wrong answer right and would
corrupt every H1/H2 number. The 49-pair corpus contains no renaming case, so the reported
precision of 1.000 was untested exactly where real model output will hit it.

**Decision.** `Env.names_locked: bool` becomes `Env.locked_names: frozenset[str]`, holding
the **intersection** of the two declared vocabularies. A name declared in both modules is
being used as an identity and may not be permuted; a name genuinely absent from one side
stays free, which preserves the coverage the original condition was protecting.

**Evidence.** `a > b` vs `b > a`, `a - b > 0` vs `b - a > 0`, and `a / b = 2` vs
`b / a = 2` all report `COUNTEREXAMPLE_FOUND` under **both** the same-spare and
renamed-spare variants. Legitimate alpha-renaming (`a = a` vs `b = b`) still reports
`VERIFIED_EQUIVALENT`. The 49-pair benchmark is unchanged: 49/49 decided, precision 1.000,
zero false positives.

**Limitation retained.** The benchmark still contains no spare-rename case. These fixes are
pinned by the falsifier's own adversarial tests rather than by the corpus, and the corpus
should gain such pairs before any H1/H2 number is computed.
