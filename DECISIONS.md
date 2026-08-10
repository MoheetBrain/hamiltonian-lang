# Decisions

Format per §23 of the master directive. Reversal cost is stated because when uncertain we
prefer reversible choices.

---

> ## ⚠ DECISION-ID COLLISION — read before citing D-026, D-027 or D-028
>
> **Three decision numbers were reused in error on 2026-08-07.** The V2 reasoning work
> appended records numbered D-026, D-027 and D-028 while records with those numbers
> already existed. Each of those three IDs therefore identifies **two** decisions:
>
> | ID | earlier record (2026-08-06) | later record (2026-08-07, V2) |
> |---|---|---|
> | D-026 | the partiality guard must follow definitions | the eleven critical coverage zeros |
> | D-027 | the Tier-1 name lock is shared vocabulary | premises must be ESTABLISHED |
> | D-028 | the verifier's dimension re-reader must honour parentheses | wire the refinement environment into the type checker |
>
> **Disambiguation rule:** the V2 records are dated 2026-08-07 and appear *after* D-033 in
> file order. Cite them as "D-026 (V2)" and so on.
>
> **Why they were not renumbered.** The three collided records were already committed and
> pushed, and roughly 65 sites across `src/`, `tests/`, `spec/` and `docs/` reference one
> number or the other. Several references are genuinely ambiguous without reading their
> surrounding context — `type_system/__init__.py` cites the V2 record, while
> `tests/verification/test_dimension_text_parentheses.py` cites the earlier one. A bulk
> renumber would have had a worse expected outcome than the collision it fixed. The
> decision is to record the collision precisely rather than to risk corrupting the
> references.
>
> **Prevention.** The architectural freeze that follows was renumbered to D-034…D-039
> *before* it was committed, after this collision was discovered. Any future record must
> take a number strictly greater than every number already present in this file.
>
> **Enforced since 2026-08-10, not merely stated.** `tests/freeze/test_decision_ids.py`
> pins the collision set to exactly these three and fails on a fourth. It also fails on a
> gap in the numbering, on a citation naming a record that does not exist, and on this
> table drifting from the headings it describes. The rule above was a sentence, and a
> sentence does not fail a build — which is how three numbers came to be reused.
>
> **Re-examined 2026-08-10; the decision not to renumber is upheld.** An independent
> re-count found ten of the ~65 citations inside the frozen core (`ast/`, `lexer/`,
> `parser/`, `backends/`). Renumbering would mean editing frozen files to repair a
> documentation defect, and every such edit is a chance to point a citation at the wrong
> record — the precise failure the original decision avoided. Referential integrity is
> otherwise intact: D-001…D-047 with no gaps, and no dangling citation anywhere in the
> repository.

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

## D-028 — the verifier's dimension re-reader must honour parentheses

**Date.** 2026-08-06 · **Status.** Accepted · **Bug fix, not a grammar change.**

**Scope, stated first because it determines the procedure.** This changes
`verification/obligations/checkers.py::parse_dimension_text`, a checker-side helper. It does
**not** touch `ast/nodes.py`, `types.py`, `backends/canonical.py`, the grammar or the
canonical form, so the `V0_DESIGN_FREEZE` design-change procedure does not apply. Content
hashes are unaffected. It is recorded here because it changes verification behaviour.

**Problem.** `parse_dimension_text` is a deliberately independent re-implementation of the
dimension grammar, so a dimensional claim is compared against a *second* reading of the
source rather than the type checker's answer echoed back. That independence is sound, but
the second reader was incomplete: `_dim_tokens` did
`text.replace("(", " ").replace(")", " ")`, deleting grouping outright.

Because the compiler **renders its own canonical form with parentheses**, the re-reader
received `Mass / (Length * Time^2)` and re-read it as `Mass / Length * Time^2`. Every
dimension requiring two divisions — pressure, density, force per area — was reported
DISPROVED regardless of how the author spelled it. A single trailing division was
unaffected, which is why `examples/physics/kinetic_energy.hml` never caught it.

**One defect, not two.** The bug report also alleged right-associative division. That does
not reproduce: `a / b / c` parsed correctly as `(a / b) / c` both before and after. All
three reported spellings failed for the single reason above, which is exactly what made the
symptom look like an associativity error.

**Decision.** Tokenise `(` and `)` and give the re-reader a recursive `group` rule with
left-associative `*` and `/`, plus a group exponent so `(a * b)^2` binds to the whole group.

**A regression the fix introduced and closed.** Removing `/` from the identifier character
class broke rational exponents: `Length^1/2` had tokenised as one identifier and became
three tokens. `_exponent()` now reads `n / m` as a fraction **only when both sides are
numeric**, so `Length^1/2` is a half power while `Mass^2 / Time` stays a division — the same
distinction the language parser draws. Without this, valid programs would have been
rejected.

**Evidence.**

| assertion | before | after |
|---|---|---|
| `check dimension q = Mass / Length / Time^2` | DISPROVED | **VERIFIED** |
| `check dimension q = Mass / (Length * Time^2)` | DISPROVED | **VERIFIED** |
| `check dimension q = Mass / Length^1 / Time^2` | DISPROVED | **VERIFIED** |
| `Mass / (Length / Time)` vs `Mass / (Length * Time)` | identical | **distinct** |
| `Length^1/2` | `Length^1/2` | `Length^1/2` |
| `check dimension q = Mass * Time^2 / Length` | rejected | **still rejected** (`HML-D504`) |

A genuinely wrong assertion is still caught, by the type checker, before the obligation
engine runs — so it surfaces as `INVALID` rather than `DISPROVED`. The fix removes a false
negative without making the check permissive.

`tests/verification/test_dimension_text_parentheses.py` pins all of the above, including a
negative control.

**Reversal.** Restore the two `replace` calls and delete the `group`/`_exponent` rules.
Reversal reintroduces the inability to assert any two-division dimension.

## D-029 — ACQ0's primary protocol is DIRECT_FORMAL

**Date.** 2026-08-06 · **Status.** Accepted · **Experimental redesign, recorded before any
model call.**

**Decision.** The ACQ0 acquisition screen uses `DIRECT_FORMAL` only.
`DRAFT_THEN_FORMAL` is deferred to H2, and permitted as a rescue arm only after direct
acquisition has been *measured* to fail systematically.

**Reason.** ACQ0 receives the complete canonical mathematical target and tests faithful
*encoding*, not reasoning. A free-draft stage changes the intervention, doubles the call
count, and obscures the acquisition measurement — the model would be reasoning about a
problem whose answer it was already given.

**Why the prior calibration cannot decide this.** Both runs are closed as
`PROTOCOL_UNSTABLE` for different reasons, and neither is evidence about the protocols:

- **v1** was invalidated by output capping: 56 of 76 generation events hit
  `finish_reason="length"` at exactly 2048 tokens, returning empty visible answers. Six of
  eight pairs were ties produced by that shared budget failure.
- **v2** ran on `binding_chain_002` and `distribution_law_002`, both since audited
  `INVALID_INSTRUMENT`. All 8 pairs tied, zero VERIFIED.

One fact from v2 survives and motivates the split: at a 6144 allowance `DIRECT_FORMAL`
capped **0 of 8** with visible output throughout, while the *same* 6144 split as
2048 draft + 4096 formal capped 12 of 16. The two-stage arm's first stage never finished
in either run (768 in v1, 2048 in v2, both 8/8 capped), so it was never "draft then
formalise" — it was "truncated draft, then formalise". Re-running that comparison before
ACQ0 would spend calls re-measuring a known truncation artefact.

**Not deleted.** The `DRAFT_THEN_FORMAL` implementation and all 32 historical raw records
are retained. They are preserved as invalid-measurement evidence and excluded from every
new aggregate.

**Reversal.** Re-enable the two-stage arm with a draft allowance large enough to reach
`finish_reason="stop"`, and treat it as a new experiment with its own preregistration.

## D-030 — the model-visible view is an ordered statement list

**Date.** 2026-08-06 · **Status.** Accepted · **Supersedes the bucketed
`structured_target()` as the model-facing artefact.**

**Decision.** What a model receives is `encoding_view(task)`: a single positional list of
`encoding_statements`, each carrying `position`, `statement_id`, `kind`, structured content,
`epistemic_role` and an explicit `emit` flag. A task is admissible only if
`reconstruct_source(encoding_view(task))` — a function permitted to read the view and
nothing else — compiles to a module whose `content_hash` equals the reference.

**Reason.** `content_hash` is order-sensitive; the previous view partitioned a module into
unordered kind-buckets. Three of the eight v2 tasks were therefore unencodable: nothing in
the view said that `v2_transformation_side_condition_001` puts `require` before `assume`.
The other five passed only because their source order happened to match the bucket order. A
fourth defect was worse — `structured_target()` had no `CheckStmt` branch, so
`check dimension …` existed in the reference and in no model-visible artefact at all.

**Why three existing checks all missed it.** `check_prose_coverage`,
`reconstruct_semantic_payload` and the 32/32 surface round-trip each validated an artefact
**against itself**: the first two derive from `structured_target()` and re-read its own
keys; the third renders from `task.source` and never traverses the view. The loss lived
exactly on the boundary between the view and the source, which none of them crossed. A
check that cannot fail is not a check.

**Consequences.**

- Prose is generated in encoding order, one clause per emitted statement, rather than by
  kind-bucket — the reader now sees the order the answer requires.
- An unrepresented statement kind raises `UnsupportedStatement` instead of vanishing.
- A missing initialiser, body or codomain raises `ViewIncomplete` rather than being
  defaulted; defaulting is how an encoder gets blamed for information it never had.
- `emit=false` records (derived facts, prohibited assumptions) carry the flag explicitly and
  the emission rule is stated inside the view.
- Two tasks whose mathematics could not survive the gate were replaced under **fresh ids**
  and preserved in `evaluation/results/acq0/superseded_tasks/SUPERSEDED.md`.

**Reversal.** Serve `structured_target()` to models again and delete
`view_reconstructs_exactly` from admission. Reversal restores an instrument that scores
models against information they were never given.

## D-031 — an objective must name the kind of goal the source states

**Date.** 2026-08-06 · **Status.** Accepted

**Decision.** `objective.kind` selects the statement class that discharges it:
`prove`→`ProveStmt`, `solve`→`SolveStmt`, `infer`→`InferStmt`, **`decide`→`CheckStmt`**.
A task whose objective names a kind the source does not state is rejected at construction.
A `check` with **no** objective stays legal.

**Reason.** The previous rule was a bare existence test — "an objective implies some goal
statement" — over `(ProveStmt, SolveStmt, InferStmt)`. Under it, `objective=Objective(
"decide", …)` could not be discharged at all, so the taxonomy's objective-bearing *check*
cell had no expressible task. Widening the goal set to include `CheckStmt` unconditionally
would have been worse: it would retroactively invalidate `v2_dimensional_algebra_002`,
whose `check dimension` is a property **of** the object rather than the point of the task.

The distinction is the content: a `check` states something true of the object; an
objective declares that establishing it is what the task is *for*.

**Reversal.** Restore the existence test and delete the `decide`→`CheckStmt` mapping.
Reversal removes taxonomy cell 10 and leaves the `decide` objective kind unusable.

## D-032 — demonstrations are authored, never drawn from the scored corpus

**Date.** 2026-08-06 · **Status.** Accepted

**Decision.** The four ACQ0 demonstrations live in `evaluation/acq0/v2/prompt.py`, are
authored HML modules, are never scored, and duplicate no scored task's mathematics. Each is
shown as an **ordered view paired with its encoding**, not as an encoding alone.

**Reason.** Two separate defects in the predecessor, which used `PROOF_CORPUS[:5]`.

*Contamination and asymmetry.* A demonstration task's answer was visible while a model
encoded a different task, and a demo task received one fewer demonstration than a non-demo
task, because a task never demonstrates itself. Per-task difficulty was therefore not
comparable, and five of twelve tasks were scored after their answers had been shown.

*The demonstrations taught the wrong thing.* Rendering only the encoding exhibits the
notation and leaves the model to infer how a view becomes one. That measures inference, not
translation, and it penalises whichever surface is hardest to *guess* rather than hardest to
*express* — which would have been read as a property of the surface.

**Reversal.** Point `DEMONSTRATIONS` back at `PROOF_CORPUS[:k]` and drop the `GIVEN:` block.
Reversal reintroduces answer exposure across tasks and measures guessability.

## D-033 — Tranche A is void on truncation; surface D is eliminated by upper bound

**Date.** 2026-08-06 · **Status.** Accepted

**Decision.** The completed 32-condition Tranche A run is `MEASUREMENT_INVALID`. Surface D
is eliminated **without a rerun**, by a bound no resolution of its truncated record escapes.

**Why the run is void.** Three conditions hit the 6,144-token completion allowance, and the
truncation is outcome-determining for two of four surfaces. Surface A is 7/8 exact and fails
the gate *solely* on its one truncation, since `constitutional failures = 0` is required.
Surface C's truncated condition is one of its three non-parses, so without it C's
repaired-parse count would cross the 6/8 threshold. The truncated attempts show the model
**deliberating** — it wrote a correct surface-A encoding, replied to itself `-> NO!`, started
again and ran out of budget — while the same model answered the same task cleanly in surface
B. That is decoding instability meeting a cap, not a measurement of what a notation can
express. It is the mechanism that already voided the v1 calibration (56/76 capped at 2,048).

**The cap was not forced by the runtime**: slot 16,384, prompt ~3,000, so ~13,000 tokens
were free. 6,144 was chosen before this corpus's generation behaviour was known.

**Why D needs no rerun.** Its repaired-parse count is 0/8; exactly one D record truncated,
and only in *repair* (its attempt zero finished `stop` at 3,866 tokens and failed on
content). Granting that record the most favourable possible resolution gives at most 1/8
against a frozen threshold of 6/8. Arithmetic, not taste. The failure class is schema
conformance: every D attempt emitted a *triples* encoding where the candidate specifies a
`statements` array, and all failed at import rather than at the compiler.

**Not deleted.** All 32 records are preserved with a manifest of prompt and bundle hashes.
They are admissible for debugging and operational planning and **must never** enter the
valid Tranche A aggregate.

**Reversal.** Treat the truncated conditions as legitimate failures and report A and C as
non-viable. Reversal publishes a confidently wrong claim about two notations on the strength
of a harness parameter.

---

## D-025 — the V2 reasoning spine: `goal`, `derive`, `proved`

**Date:** 2026-08-07 · **Branch:** `feature/hml-reasoning-kernel-v2` · **Base:** `3dd4216`

**Context.** The language audit (`audit/language_comparison/report/EXECUTIVE_VERDICT.md`,
audited SHA `b1ac7bf`) found that HML represents mathematical *state* but has no surface
form for a reasoning *transition*: 0 of 19 transformation forms were representable in
`.hml` source. Verified independently before acting — `prove 1.0 = 2.0` compiles clean
(exit 0), and `assume x > 0.0` does not discharge `log`'s `PositiveReal` domain
(`HML-T427`).

**Decision.** Add three statement forms and five keywords:

```
goal   g1 : <proposition>
derive d1 : <conclusion> [from c1, c2] by <rule>[(<role> := <expr>, ...)]
proved g1 by d1
```
plus an optional `<label> :` on `assume` / `require` / `prove`.

**What makes this more than vocabulary.** `DeriveStmt.status` is computed by the checker
and **has no surface syntax**. A model can assert a derivation; it cannot assert that the
derivation is correct. `PROPOSED → CHECKED → VERIFIED` is reachable only through
`reasoning/check.py::_finalise_status`, which requires that the trusted kernel reproduced
the conclusion *and* that every mandatory obligation is DISCHARGED.

**The soundness argument.** `reasoning/kernel.py::apply` constructs the conclusion a rule
licenses without ever seeing the author's claimed conclusion; the checker then demands
`expr_identity(kernel_conclusion) == expr_identity(claimed)`. A step is certified only
when the author's conclusion *is* the kernel's conclusion, up to alpha-equivalence.

**Alternatives rejected.**

- *A tactic language.* Cloning Lean onto a system where `prove 1 = 2` compiled clean
  would produce authoritative-looking output with nothing behind it. The audit scored a
  general rewriting engine with a **negative** safety delta.
- *Reusing `v1/transformation.py` as the kernel.* Considered and rejected on evidence.
  Its 30 operation specs are a sound *taxonomy*, but their obligations are Python format
  strings (`"{by} != 0"`) and its edges relate names, not `Expr`. Every checker in
  `verification/obligations/` consumes `Expr`, so reusing the templates verbatim would
  make every generated obligation UNKNOWN by construction and no derivation could ever
  reach CHECKED. The module says so itself: *"Nothing here claims to check a side
  condition."* The taxonomy informed the rule set; the code is not on the path.
- *A block syntax* (`derive d1:` / newline / `from ...`). HML-L1 is line-oriented
  everywhere except `concept ... end`; a second block convention costs an indentation
  policy and a recovery strategy to buy nothing a model needs.

**Backward compatibility.** Strictly additive. `backends/canonical.py` emits the v0.2
schema tag **only** for modules where `ast.nodes.uses_v2()` is true. Measured: all 43
`.hml` files under `examples/` produce byte-identical output under the V2 compiler and
the v1 compiler (cross-worktree `diff`, 43/43 identical). ACQ0/H2 records therefore
remain reconstructible under their original language version.

> **Correction (2026-08-07, same day).** The sentence above originally read "byte-identical
> **content hashes** ... 43/43". That overstated the evidence. 28 of the 43 files are the
> alternative candidate-syntax grammars under `examples/candidate_syntaxes/`, which do not
> compile as HML-L1 and therefore produce an identical *error*, not an identical hash.
> **15 files produce an actual content hash, and all 15 are unchanged.** The backward
> compatibility conclusion holds; the number supporting it was loosely worded. Found by
> adversarial review.

`prove` keeps its v1 meaning exactly — it states an obligation and proves nothing.
V2 does not reinterpret historical files; it adds `goal`/`derive`/`proved`, where the
claim *is* adjudicated. `tests/reasoning/test_kernel.py::test_prove_still_does_not_prove`
pins the distinction.

**Freeze manifest.** `tests/freeze/frozen_subset.py` was updated deliberately, not
suppressed: 5 keywords and 3 statement kinds admitted. The V1_KERNEL surface forms
(`goal g1 := ...`, `derive e3 from [...] via s1`) remain **rejected** — verified for all
18 quarantined forms — because V2 uses different syntax and reaches its own kernel in
`reasoning/`, not the quarantined `v1/` layer. The import barrier is untouched.

**Verification.** `pytest`: 5787 passed, 0 failed (baseline 3dd4216: 5743 passed).
`ruff check src tests`: clean. `mypy src/hamiltonian_lang/reasoning src/hamiltonian_lang/ast`:
clean.

**Two defects this change introduced and closed.** Both were silent backend losses, the
failure mode `backends/base.py` calls the worst in the codebase:
1. `backends/hml.py` emitted `# <unrenderable DeriveStmt>` while reporting
   `faithful=True`. Fixed by rendering the forms; the round-trip is now hash-stable.
2. `latex`/`lean`/`sympy`/`stan` dropped all three V2 nodes and reported nothing about
   them. Fixed by `Backend.report_reasoning_loss()` on the base class — placed there so
   the next construct is remembered once rather than five times.
`tests/reasoning/test_backend_loss.py` locks both.

**Known limitation.** `RuleSpec.apply` does not descend into quantifier bodies during
substitution, so a step requiring capture-avoiding substitution is REJECTED rather than
performed. The conservative direction is deliberate; lifting it needs a real
capture-avoiding implementation, not a loosened comparison.

---

## D-027 — closing the V2 red-team findings: premises must be ESTABLISHED

**Date:** 2026-08-07 · **Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `7a98427`

**Context.** Adversarial review of the just-landed V2 spine ran 30 attacks: 22 blocked,
8 succeeded. One was critical and is the substance of this record.

### The critical defect: unestablished claims were admissible as premises

```
goal   g1 : 1.0 = 2.0
derive d1 : 2.0 = 1.0 from g1 by symmetry
derive d2 : 1.0 = 2.0 from d1 by symmetry
proved g1 by d2
```
compiled with **zero errors and zero warnings**, reporting `d1` and `d2` VERIFIED and
`g1` PROVED. Reproduced before fixing.

**The trusted kernel was blameless.** Both steps really are valid applications of
symmetry, and every kernel-level and obligation-level attack was blocked. The hole was
one layer up: `check.py::run` correctly kept `goal`/`require`/`prove` out of the
refinement environment Γ — with a comment naming the exact hazard — and then wrote them
into `self.propositions`, which is the pool `_check_derivation` draws premises from.
**The guard was applied to one channel and not the other**, which is worse than guarding
neither, because it reads as though the hazard was handled.

This also defeated D-025's stated acyclicity argument. That argument was "a derivation
may only cite claims established *earlier* in the module, so a cycle needs a backward
edge and there are none." It is now stated correctly: **textual order is an acyclicity
argument only if every claim in the namespace is _established_ when it is cited.** A
`goal` is textually earlier than the derivations that consume it, and the `proved` edge
that closes the loop was never in the premise graph at all.

**Fix.** Two pools, not one. `propositions` holds only ESTABLISHED claims — assumptions
(granted by definition) and successfully-checked derivations. `unestablished` holds
`goal`/`require`/`prove`, cited only to produce `HML-R712` explaining why they are
refused. Plus **obligation propagation**: a derivation inherits the undischarged
mandatory obligations of its premises (`HML-R713`), so a chain resting on an open
`k != 0` cannot be certified at any depth.

### The other three findings

- **`graph` and `triples` dropped all three V2 nodes reporting `faithful=True`**
  (6 silent losses). `Backend.report_reasoning_loss` covers everything subclassing
  `Backend`; these two are plain closures over `build_graph` and were missed. Fixed with
  `_reasoning_loss()` in `backends/__init__.py`. These are the *machine-readable*
  semantic views, so an undeclared loss here is worse than in a prose rendering: a
  consumer reading the graph would conclude the reasoning does not exist.
- **No CLI surface reported any reasoning verdict**, and `hml obligations` inverted the
  truth — on a module whose obligation was correctly discharged it printed the
  *assumptions* as `NOT DISCHARGED` and omitted the real obligation. This is what made
  the critical defect invisible: `hml check` printed `ok:` and stopped. Both fixed.
  A verifier that computes a verdict and never surfaces it is half a verifier.
- **`expr_identity` treated `1` and `1.0` as different** while `refinement.py`
  deliberately treats `0`/`0.0` as one number (with a named regression test). The two
  halves disagreed about what a number is; the symptom was *correct* derivations
  rejected. Numeric literals are now normalised inside `expr_identity` only — booleans
  excluded, and `content_hash` untouched, verified by re-running the cross-worktree hash
  comparison.

**What held, and is worth protecting.** The kernel resisted every attack. `_ENTAILS`
correctly refuses `x>=0 ⊢ x!=0`, `k=0 ⊢ k>0`, disjunctions, and facts under binders.
`proved` is genuinely adjudicated. Substitution refuses to descend into binders as
documented. No `expr_identity` collision was found. Alpha-equivalence holds for both
claim labels and variables. **No surface syntax asserts a status — that D-025 claim
survived.** 5/5 adversarial inputs ran clean with no crash, hang or missing diagnostic.

**Verification.** `tests/reasoning/`: 54 passed (was 44). The original exploit now emits
`HML-R712` and the goal is not PROVED. v1 hash stability re-verified after the
`expr_identity` change: unchanged.

**Lesson recorded.** Both this defect and the two silent-loss defects in D-025 were found
by adversarial review, not by the test suite. The suite tests what the authors thought of.

---

## D-026 — the eleven critical coverage zeros: mathematical expression forms

**Date:** 2026-08-07 · **Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `7a98427`

**Context.** The language audit probed 64 critical mathematical atoms and found 79.7%
faithfully representable with **11 at zero**, clustered in four areas: analysis (LIMIT,
CONTINUITY, DERIVATIVE, INTEGRAL_DEFINITE), probability (EXPECTATION, JOINT,
CONDITIONAL_PROBABILITY, INDEPENDENCE), sets (SET_MEMBERSHIP, SET_COMPREHENSION) and
epistemics (CORRELATION_VS_CAUSATION). Every one was verified before acting; the
`expectation` finding was reproduced exactly as reported:

```
$ hml check /tmp/t.hml          # require expectation(X) > 0.0
error HML-P231: expected an expression, found 'expectation'
```

**Decision.** Add eleven expression forms, two type constructors and eleven keywords.

```
expectation(X)            expectation(X | Y, Z)         variance(X)
probability(A)            probability(A | B)
joint(X, Y)               independent(X, Y)             independent(X, Y | Z)
x in A                    {x : T | P}
limit(f, x : T -> a)      derivative(f, x : T)          integral(f, x : T, a, b)
continuous(f, on := D)
associated(X, Y)          correlated(X, Y)              causes(X, Y)
```

New types: `Event` (nullary, incomparable with `Proposition`) and `Product[T1, T2]`
(what gives `joint` an honest type). New keywords: `probability joint independent in
limit derivative integral continuous associated correlated causes`. New operators:
`{` `}`.

### The `expectation` defect, and why the audit's fix was not taken

`expectation` and `variance` were **already** keywords, and the checker already carried
correct type rules for both in `_aggregate_type`. The keyword had no expression
production, so the rules were unreachable: the audit's diagnosis was exact.

Its suggested repair — delete the lexer entry — would have broken `infer expectation x`,
which is the *other* production that needs the word. The repair taken is smaller and
loses nothing: **keep the keyword, give it an expression production.** Both
`infer expectation theta` and `require expectation(X) > 0.0` now compile, and
`tests/semantics/test_v2_expressions.py` pins each so neither can be traded for the
other. The dead `_aggregate_type` branches were removed rather than left as a second
implementation of a rule that now lives in `_moment_type`.

### The barrier this change is really about: E[X] versus E[X | Y]

```
expectation(X)          : Real                  a VALUE
expectation(X | theta)  : Real                  theta is not random
expectation(X | Y)      : RandomVariable[Real]  Y is random
joint(X, Y)             : Distribution[Product[Real, Real]]   a LAW
probability(X > 0.0)    : Probability           never PValue, never PosteriorProbability
```

E[X] is a number; E[X | Y] is a function of Y, and a function of a random variable is a
random variable. Collapsing them would let `param m : Real = expectation(X | Y)` bind a
random quantity to a fixed name. Conditioning on a **non-random** parameter yields a
value again, because a deterministic function of a constant is a constant — which is
what makes `expectation(X | theta) = A(theta) @ x` a well-formed equation.

Two further type rules are load-bearing and were not obvious:

* **Expectation leaves the support for its convex hull.** E[N] for a count is not a
  count. Returning the codomain unchanged would make `expectation(N) : Natural` compile,
  which is false. `Bool` maps to `Probability`, because E[1_A] = P(A).
* **A limit lands in the CLOSURE of the body's type.** Every value of `1.0 / x` for
  positive x is positive and the limit need not be, so `PositiveReal` widens to
  `NonNegativeReal`. The three unit-interval kinds are closed intervals and each stays
  its own kind: no operator here performs a D-022 coercion.

### `Event` — a new barrier, not a weakened one

A comparison with a `RandomVariable` operand is typed `Event`, and `Event` is
**incomparable** with `Proposition`. `require X > 0.0` is therefore rejected
(`HML-T480`) with the correction `require probability(X > 0.0) = 1.0`.

A proposition is true or false; an event is neither until a draw. `require X > 0.0`
looks exactly like `require x > 0.0` over a value and claims something completely
different — that a random inequality holds on *every* draw. Admitting it silently is the
conflation this codebase treats as the worst failure mode.

**Blast radius, measured: zero.** Before this change an event could not be *formed*:
`X > 0.0` failed with `HML-T429` "these operands are not comparable". Nothing that used
to compile stops compiling. The exception worth naming is `require X = Y` between two
random variables, which did compile via `join`'s identity path and now does not. That is
the correct direction: sure equality and almost-sure equality are different claims, and
the language previously admitted the stronger-looking one without saying which it meant.
No file under `examples/` and no test asserted it.

### Measurable lifting — the mechanism that must never become a subtyping path

`expectation(f(X))` requires `f(X)` to be well-typed, so a **lifting** rule was added:
if `f : T -> U` and `X : RandomVariable[T]` then `f(X) : RandomVariable[U]`, and the
same for arithmetic operators.

`_underlying` strips one `RandomVariable` wrapper and **every caller re-wraps**. It is
applied only at operator and application sites; `check(..., lift_random=True)` is opt-in
and only `_check_user_call` passes it. Declaration initialisers, distribution roles and
definition bodies deliberately do not, so `param p : Real = X` and
`def t : Real := 2.0 * X` remain the errors they have always been. Four tests pin that.

The rule is also strictly **more precise** than the accident it replaces:
`RandomVariable[Probability] + RandomVariable[Probability]` used to reach `join`, which
returned `RandomVariable[Probability]` for a sum that may exceed 1. It now yields
`RandomVariable[NonNegativeReal]`.

### Symmetry is declared and tested, not assumed

| form | canonical treatment | why |
|---|---|---|
| `correlated`, `associated` | operands **sorted** | the relations are symmetric |
| `causes` | operands **ordered** | direction is the content of the claim |
| `independent(X, Y \| Z)` | both lists **sorted** | symmetric in operands and in the conditioning set |
| `expectation(X \| Y, Z)` | `given` **sorted** | conditioning on Y and Z generates one sigma-algebra — the treatment `Law.given` already receives |
| `joint(X, Y)` | components **ordered** | the type is `Product[T1, T2]` and a product is ordered |

Measured: `correlated(X,Y)` and `causes(X,Y)` do not hash equal; `causes(X,Y)` and
`causes(Y,X)` do not hash equal; `correlated(X,Y)` and `correlated(Y,X)` do.

`implies(P, Q)` was **not** added, though `GRAMMAR_CONTRACT.md` §2 lists it. `=>` and the
`implies` keyword already denote it and already produce one canonical form; a third
spelling of one object would be two implementations waiting to disagree.

### Three deviations from `docs/hml_v2/GRAMMAR_CONTRACT.md` §2

The contract says an agent that believes a form is wrong must say so and stop, not
improvise. These are said, with the evidence.

1. **`E[...]` and `P(...)` are not the surface; `expectation(...)` and
   `probability(...)` are.** `E[X]` collides with indexing — `parse_postfix` already
   reads `IDENT [ ... ]` as an `Index` — so `E` would have to be reserved in the value
   namespace. It cannot be: `benchmarks/representations/hamiltonian/p01_normal_scale_role.hml`
   line 3 declares `var E : RandomVariable[Real]`, and this is a language called
   *Hamiltonian* Lang, where `E` is energy and `P` is pressure or momentum. A form whose
   reading depends on whether the author also wanted a variable called `E` is the
   ambiguity `CLAUDE.md` rule 1 forbids. The mathematics is unaffected — every form the
   contract lists is expressible, under a spelling that has one reading.
2. **Binders carry a mandatory type annotation**: `derivative(f, x : Real)`, not
   `derivative(f, x)`. Governing principle 1 already forced this twice —
   `HML-P236` on quantifiers ("untyped quantification is rejected: the domain must be
   explicit") and `HML-P214` on transform parameters (D-015). An inferred binder type
   here would be inferred from the *point* or the *bounds*, which is the implicit
   coupling both decisions refused.
3. **Conditional independence is `independent(X, Y | Z)`**, not a `given` keyword. It
   reuses the `|` that `law y | x ~ ...` already uses, per the contract's own rule 2,
   and keeps one construct where a second spelling would let the two drift.

`{` and `}` are the one place a new sigil was added. An undelimited
`set x : Real | x > 0.0` gives the predicate no right-hand end, so
`require v in set x : Real | x > 0.0 and p` has two readings; braces have one.

### Backward compatibility, measured

All 43 `.hml` files under `examples/` — 15 of which compile to a real content hash,
28 being the non-HML candidate-syntax grammars — produce **byte-identical** output under
this compiler and the v1 compiler at `/Users/moheet/hamiltonian_lang`. Cross-worktree
`diff`: identical. `tests/golden/hashes.json` gained four rows and changed none.

`uses_v2` was **extended** to walk expressions, which `docs/hml_v2/SEMANTICS.md` §4.5
already required ("include *every* V2-introduced field, not only the new statement
kinds"). Without it a module whose only V2 content is `expectation(X | Y)` would be
tagged `hml-canonical-0.1.0` while carrying a `"kind": "Moment"` node no 0.1.0 reader
knows — a tag that is actively misleading rather than merely absent.

`spec/ir.schema.json` was extended in the same change, as §4.5 requires. This also
corrected an omission from D-025: `Goal`, `Derivation` and `ProofClaim` were emitted by
`backends/canonical.py` but were never added to the statement enum, so every V2
reasoning document failed schema validation.

### Zero silent backend loss

Every backend renders the eleven forms or declares the loss. Two **pre-existing** silent
holes were closed on the way: `backends/latex.py` returned `\text{?}` and
`backends/english.py` returned "an unrepresented expression" for any unknown node, both
while reporting `faithful=True`. `backends/graph` had a third, of a different shape:
`_children` returned `()` for unknown nodes, so `require probability(X > 0.0)` would
have appeared in the semantic graph with **no dependency edge on X at all**.

| target | treatment |
|---|---|
| `hml` | all eleven rendered; round-trip hash-stable and idempotent |
| `english` | all eleven; the three causal relations get three different sentences |
| `latex` | nine exact; `joint` weakened (no standard operator for a joint law); the three analysis binders weakened (standard notation carries the binder's name but not its domain) |
| `lean` | membership and comprehension exact (Mathlib's `Set` *is* HML's `Set[T]`); nine dropped with specific reasons |
| `stan` | all eleven dropped with specific reasons |
| `sympy` | all eleven dropped; the reason for `Integral`/`Derivative`/`Limit` is specific and is a real gap — see below |

**Known limitation, recorded rather than half-done.** SymPy genuinely has `Integral`,
`Derivative`, `Limit` and `ConditionSet`. They are dropped because the bound variable
would need a `Symbol` carrying the assumptions of the HML binder type, and this backend
declares symbols only from *declarations*. Two sibling binders spelled alike with
different refinements — `integral(f, x : Real, ...)` beside
`integral(g, x : PositiveReal, ...)`, legal because HML forbids shadowing but not reuse
across disjoint scopes — would silently share one symbol, and a wrong assumption in a
symbolic algebra system propagates into simplification results with no error. Closing
this needs a scoped symbol name per binder.

### Freeze manifest

`tests/freeze/frozen_subset.py` was amended deliberately, never suppressed: 11 keywords
and 2 type constructors admitted, **0 statement kinds** — these forms compose inside the
statements that already exist. The three questions D-025 answered were answered again for
each: none reaches `hamiltonian_lang.v1` (the import barrier is untouched), none promotes
a `QUARANTINED_SURFACE_FORM` (all 18 remain rejected), and each is *enforced* rather than
merely parsed — 23 new diagnostics reject the corresponding misuse.

`docs/evaluation/V1_FREEZE_MANIFEST.md` was **not** amended, and this is deliberate
rather than an omission. It is the frozen evidence document for the V1 language; its rows
are pinned by `REQUIRED_MANIFEST_ROWS`, and D-025 set the precedent that V2 additions are
evidenced in `DECISIONS.md` and `docs/hml_v2/` rather than backdated into a document
describing a language state that no longer obtains. The executed rejection for each new
diagnostic lives in `tests/adversarial/test_v2_expression_rejections.py`.

### A scientific-integrity pin

`tests/syntax_acquisition/test_candidate_surfaces.py` requires every shipped example to
round-trip through candidate surfaces A–D. Those surfaces are a **frozen tournament
artefact**: specified against the V1 surface, run against it, and D-033 has already
recorded eliminations on that basis. Feeding them V2 modules would retroactively change
the tournament's inputs, and extending A–D with new productions would mean the surfaces
that were scored are not the surfaces that exist.

The corpus is therefore pinned with `uses_v2`. Nothing is weakened: a V1 example that
stops round-tripping still fails, a companion test asserts the pinned corpus is not
silently empty, and a second companion test asserts every excluded V2 example is
**refused loudly** by all four surfaces — so an exclusion can never hide a surface that
quietly drops a construct.

**Verification.**
`pytest`: 6226 passed, 5 skipped, 7 xfailed, 7 xpassed, 0 failed.
`ruff check src tests`: clean.
`mypy` over `ast types parser lexer type_system semantics backends graph`: clean.
`hml check` on each of the four new examples: exit 0.
Cross-compiler hash diff over `examples/`: identical.

**Risks / limitations.**
- SymPy analysis forms dropped rather than rendered (above).
- HML still does not distinguish *sure* from *almost-sure*: `require probability(A) = 1.0`
  is the only spelling, and it means the former.
- The audit's C-7 hole is unchanged: `law y ~ Normal(...)` on a plain `var y : Real`
  still compiles, so a Bayesian `param` with a prior is not `RandomVariable`-typed and
  therefore forms propositions rather than events. This is inherited, is recorded in
  `docs/hml_v2/SEMANTICS.md` §1.3, and D-026 does not claim to close it.
- `variance` of a vector-valued random variable is refused rather than typed: the answer
  is a covariance matrix, which v2 does not represent.

---

## D-028 — wire the refinement environment into the type checker

**Date:** 2026-08-07 · **Branch:** `feature/hml-reasoning-kernel-v2` · **After:** `f0e3340`

**Context.** D-025 shipped `reasoning/refinement.py` with a working `refine()` and
claimed that `assume` had become load-bearing. The capability-audit rerun measured
otherwise: Γ was consumed only by `reasoning/check.py`, so an assumption could discharge
a kernel-generated obligation while the **type checker never saw it**. The V2 directive's
§7 pathological example still failed:

```
var x : Real
assume x > 0.0
require log(x) = log(x)     -> HML-T427: expected PositiveReal, found Real
```

**This was a half-fix reported as a whole one**, and the claim in D-025 and in the
`7a98427` commit message that "`assume` is load-bearing against the type/domain checker"
was not true as written. It is true now.

**Decision.** `TypeChecker` owns a `RefinementEnv`, populated by `_collect_assumptions()`
before checking starts, and `_sym_type()` returns `refine(sid, declared)` rather than the
declared type raw.

**Order-independence.** Assumptions are collected in one pass up front, so an assumption
stated below a use still constrains it. This matches the resolver's existing treatment of
binders (D-008) rather than introducing a second, contradictory scoping policy. Only
*module-level* assumptions are collected: one nested in a quantifier body or a concept is
scoped to that body, and hoisting it would leak it — the one direction that is unsound.

**Why this is safe.** Narrowing only ever moves DOWN the refinement lattice
(`Real -> PositiveReal`), and `RefinementEnv.refine` returns the declared type unchanged
unless an assumption strictly justifies a narrower one. Nothing that was an error becomes
accepted for the wrong reason. The negative cases are the point and are all pinned in
`tests/reasoning/test_type_refinement.py`:

| program | verdict |
|---|---|
| `assume x > 0.0` then `log(x)` | **accepted** |
| `assume x >= 0.0` then `log(x)` | **rejected** — 0 is admitted and log(0) is undefined |
| `assume x >= 0.0` then `sqrt(x)` | accepted |
| `assume x > 5.0` then `log(x)` | accepted — a stronger bound entails a weaker one |
| assumption about another symbol | rejected |
| `assume x > 0.0 or x < 0.0` | rejected — a disjunction asserts neither disjunct |
| `require x > 0.0` then `log(x)` | rejected — a requirement is not a fact |
| `prove x > 0.0` then `log(x)` | rejected |
| `assume p > 0.0` widening `Probability` to `PositiveReal` | rejected |
| an assumption defeating a dimension check | rejected |

**Verification.** `pytest`: 6240 passed, 0 failed (6226 before). Hash stability: **every
example hash byte-identical**, 0 changed and 0 added — the change is invisible to any
module that states no assumption.

**What this does NOT fix.** Maturity criterion 3.4 remains FAIL: `1/x`, `1/0`, `tan` and
`0^-1` still compile with zero obligations. Narrowing a symbol's type is not the same as
a coherent partiality policy, which the directive's §8 asks for and which is not built.

---

## D-034 … D-039 — the architectural freeze

**Date:** 2026-08-07 · **Base:** `0715bfc` · **Full text:** `docs/hml_v2/ARCHITECTURE_FREEZE.md`

Six architectural questions frozen as binding contracts before steps 2-9 implement them.
Numbered D-034…D-039 after the collision notice at the top of this file was written; an
earlier draft used D-029…D-034, every one of which was already taken.

- **D-034 evidence semantics** — semantic identity and evidence never mix. `content_hash`
  is invariant under verification; a status is evidence, not source; premise order IS
  identity. Consequence stated plainly: *a content hash certifies what was claimed, never
  that it holds.*
- **D-035 Γ and scope** — Γ becomes a stack of frames (MODULE/QUANTIFIER/CONCEPT/SCOPE).
  No fact escapes its frame; obligations discharge only against facts visible at their own
  frame; `require`/`prove` never contribute facts; narrowing moves down the lattice only;
  within a frame, order-independent (D-008 consistency).
- **D-036 definedness** — one policy: TOTAL / GUARDED / CONTRACTED / PARTIAL_UNDECIDABLE.
  Every operation classified in one registry; an unclassified operation is a **build
  error**. Division, `tan`, negative powers, indexing, matrix inverse, conditional
  probability and normalisation become CONTRACTED and always generate a precondition.
  Totalisation (Lean-style) rejected *for HML specifically*: HML's product is surfacing
  the condition to a model that must repair, and totalising hides the signal the repair
  loop consumes.
- **D-037 approximation** — a distinct relation, never equality; no coercion; does not
  chain without explicit bound arithmetic; a bound or an explicit UNBOUNDED, never silence.
- **D-038 certificates** — one evidence path for internal and external checkers alike.
  `UNSUPPORTED` and `INCONCLUSIVE` never collapse; `REFUTED` means REJECTED, not OPEN; a
  TIMEOUT is never an approximation of DISCHARGED.
- **D-039 extension trust** — CORE / LIBRARY / USER, one-way. **A claim's effective trust
  is the MINIMUM over its dependency closure.** No `trusted` keyword exists and none will;
  a USER rule can never reach VERIFIED. Prevents "VERIFIED" degrading into "somebody wrote
  a rule that said so".

**Why freeze first.** V2 shipped three defects of one shape: a mechanism half-built, with
the missing half being the half that made it load-bearing — `assume` not narrowing types;
`push`/`pop` that nothing called; `goal` kept out of Γ and let into the premise pool.
Freezing the contract before implementing is the countermeasure.

**Verification.** `tests/reasoning/test_architecture_freeze.py` — 12 tests, all passing,
pinning every frozen decision that is *already* true (E1, E3, E5, G3, G4, G5, X1, X3).
Decisions describing unbuilt work are deliberately NOT tested: an xfail pretending to be a
guard is worse than an absent test.

**Explicitly not decided:** whether the AST needs a generic Apply/Bind/Attribute core
(step 5's fork, being measured); the route to the 0.85 closure target; import syntax; and
whether `prove` migrates to a goal (a real contract-vs-implementation divergence, deferred
to step 6).

---

## D-040 — the explicit evidence graph

**Date:** 2026-08-07 · **After:** `e435c77` · **Implements:** directive §3 (E1-E10)

**Problem.** V2's acyclicity rested entirely on one rule: a derivation may cite only
claims declared earlier in the module. Measured: `grep -rn "def .*cycle"` over
`reasoning/` returned nothing.

That rule is sound for a single module built in one pass from source order, and **only**
for that. It does not hold for imports, batch graph construction, or any assembly whose
order is not textual order. Worse, it never saw the `proved` edge at all — which is the
edge that closed the loop in the original `goal g1 : 1.0 = 2.0` exploit.

**Decision.** Add `reasoning/evidence.py`: an explicit graph with a real validator that
walks **every** edge kind (PREMISE, OBLIGATION, PROOF, DISCHARGE). The ordering rule stays
as a cheap first line; the graph is the argument.

**The three-way evidence split**, which the previous code conflated:

| class | may support a conclusion? |
|---|---|
| `ESTABLISHED` | yes — an in-scope `assume`, or a VERIFIED derivation |
| `PROVISIONAL` | only by carrying its unresolved obligations forward — a CHECKED derivation |
| `NOT_EVIDENCE` | never — `goal`, `require`, `prove` |

**A naming correction.** The premise pool was called `propositions` and its comment called
its contents "established". It holds PROVISIONAL claims too. The *behaviour* was already
right — a step resting on a CHECKED premise inherits its obligation and stays CHECKED —
but the label was wrong, and the directive is explicit that a CHECKED claim is not
established. Comment corrected; no behavioural change.

**Independent confirmation that the graph earns its place.** Driven directly with the
exploit's shape — `d1 --premise--> g1` and `g1 --proof--> d1` — the validator reports
**three** violations that the incremental rules would have to catch separately: E1 (cycle,
found only because PROOF edges are walked), E2 (a not-evidence premise), E3 (a VERIFIED
claim whose premise closure is not established).

**Verification.**
- `pytest`: **6270 passed, 0 failed** (6252 before)
- `tests/reasoning/`: 98 passed, of which 18 are new evidence-graph tests
- `ruff`: clean · `mypy src/hamiltonian_lang`: clean, 89 files
- hash stability: **0 changes**
- the original exploit remains blocked, now by two independent mechanisms

**Deliberate design points.** `transitive_open_obligations` and `effective_class` are both
cycle-safe (bounded by a visited set), because a soundness routine that can hang is one
that will eventually be bypassed. `find_cycle` is iterative, because a RecursionError
inside the soundness check would be a crash in exactly the wrong place.

**Not done here.** E5/E6 (status changes cannot manufacture evidence; source cannot write
VERIFIED) are already enforced elsewhere and pinned by
`tests/reasoning/test_architecture_freeze.py`. E10 is D-034. E8 has a node field and a
validator check but no import mechanism to exercise it yet — the field exists so the
import work lands against a contract rather than inventing one.

---

## D-041 — the AST fork: do NOT introduce a generic Apply/Bind/Attribute core

**Date:** 2026-08-07 · **After:** `a69261f` · **Decides:** directive §7/§8
**Evidence:** `docs/hml_v2/COMPOSITIONALITY_STUDY.md`

**The question.** Two research reports recommended replacing HML's 21 position-specific
expression node kinds with a generic internal core (APPLICATION / BINDING / ATTRIBUTION).
Directive filter A forbade accepting that on recommendation and required measurement
first. This record is that decision.

**What was measured.** The 48 `COMPOSITION_TESTS.json` specimens had never been executed —
they are prose, so running them meant *writing* 48 HML encodings. Done, plus 57 controls
and 29 mechanical checks on the checked tree (rendered types, canonical-hash inequalities,
print/reparse stability, declared backend losses), so "it compiled" is never the verdict.

```
STRICT     20/48 = 0.417
FRAMEWORK  20/38 = 0.526   (10 UNSUPPORTED excluded)
```

Failure attribution over the 28 failures:

| class | n |
|---|---|
| GRAMMAR | 14 |
| TYPE | 8 |
| COMPILER | 3 |
| CONSTRAINT | 2 |
| SCOPE | 1 |
| **CANONICAL** | **0** (12 predicted) |
| **BACKEND** | **0** (6 predicted) |
| SPECIMEN | 0 |

**Decision: REJECT the rewrite.** Three measurements decide it, and the third is decisive:

1. **21 of 28 failures never touch `ast/nodes.py`.** They are a missing builtin signature,
   a registry entry, a type rule, or a pass.
2. **The 7 that need something new reduce to two additions, not three primitives** —
   *abstraction* (there is no derivative-at-a-point anywhere in HML, because
   `derivative(...)` yields a value) and *a binder over statements* (`law` is a statement
   and `forall` an expression, so indexed families of laws are unwritable).
3. **The generic core alone reaches 27/48 = 0.563 — below the 0.70 Level 2 threshold.**
   Targeted repairs alone reach **41/48 = 0.854**, clearing the 0.85 target. *The rewrite
   is neither necessary nor sufficient; the repairs are both.*

**What is accepted instead.** Local repairs, the two targeted additions, and a ~40-line
generic **binder protocol** (`binder_of` / `scoped_children`) — not a generic node set.
This addresses the real measured duplication: 79 binder dispatch sites across 298 lines in
17 files, of which **7 handle only `Quantifier`**. Live consequence already present:
`free_names` returns `[]` for `integral(y, x : Real, 0.0, 1.0)` where `y` is free, latent
only because an unrelated guard masks it.

**Costs of the rejected option, recorded so the decision can be revisited on evidence.**
v1 canonical identity dies wholesale — the `uses_v2` mechanism cannot protect it; the 53
`HML-T*` rejection rules would be rewritten with no regression baseline; D-003's
*parse-time* refusal of positional distribution arguments degrades to a checker error; a
generic surface costs ×1.69 tokens against a directive that optimises for LLM writability.

**The strongest argument against this decision**, recorded because it is good: D-026 added
four binders one commit earlier and 7 of 17 consumers are *already* stale with one latent
unsoundness — a project that cannot keep four binders in sync will not keep eight. The
rebuttal is that this argues for removing the traversals, not the classes, which is what
the binder protocol does. **Falsification condition:** if the binder protocol lands and
consumers still drift, or if a third and fourth new binder are needed within the next two
milestones, reopen this decision.

**Confidence: ~0.75.** Not higher, because the two additions are real and their eventual
shape may yet argue for generality.

---

## D-042 — circular probability laws are rejected (HML-S607)

**Date:** 2026-08-07 · **Found by:** the compositionality study, specimen CT-022

`prior a ~ Normal(location := b, ...)` with `prior b ~ Normal(location := a, ...)`
**compiled clean with zero diagnostics.** Such a pair specifies no joint distribution:
there is no density to factor and nothing to infer from. It is authoritative-looking
output for something that denotes nothing — this project's worst failure mode.

Implemented in the resolver beside the existing definition- and concept-cycle checks,
reusing `_find_cycle`. Edges run from a law's target to every symbol its distribution and
its `given` list mention, which is the direction of dependency.

**This check immediately found a latent defect in an existing test fixture.**
`tests/roundtrip/test_importers.py` contained `law m ~ Normal(location := m, scale := s)`
— a self-referential law that had gone unnoticed because nothing checked for one. The
fixture's subject is Stan's closed lower bound, not `m`'s law, so the fixture was
corrected rather than the check relaxed.

**Verification.** `pytest`: 6279 passed, 0 failed. Rejected: mutual pairs, 3-cycles,
self-reference through a parameter, self-reference through `given`. Accepted: two- and
three-level hierarchical models, and every shipped probabilistic example. Hash stability:
0 changes.

---

## Correction to the compositionality study: CT-018

The study reported three silent composition losses. **Two reproduce; one is overstated.**

CT-018 claimed `E[X | G]` types as `Real`, "identical to unconditional `E[X]`". Measured:

| conditioning on | `E[X]` | `E[X | ·]` | same identity? |
|---|---|---|---|
| a `RandomVariable[Real]` | `Real` | `RandomVariable[Real]` | no |
| a deterministic `Real` | `Real` | `Real` | **no** |

Conditioning on a random variable yields a random variable, which is correct. Conditioning
on a *deterministic* quantity yields a value — also correct, since conditioning on a
degenerate variable returns a constant. And in both cases the **canonical identities
differ**, so the two expressions are not conflated. This is therefore not a silent loss.
CT-022 and CT-038 are real; CT-038 is exactly what D-036's precondition contracts close.

---

## D-043 — `scope … end`: scoped Γ becomes load-bearing

**Date:** 2026-08-07 · **After:** `ae9a2a0` · **Implements:** D-035, directive §3

**Problem.** Γ was flat. `assume x > 0.0` licensed `log(x)` for the entire module, and
there was no way to say "assume this *for the purposes of this argument*".
`RefinementEnv.push`/`pop` existed and **nothing called them** — the third instance in
this project of a mechanism built and left unwired, after `assume` not reaching the type
checker (D-028) and the premise-pool guard covering one of two channels (D-027 V2).

**Decision.** Γ is a stack of `Frame`s, and `scope … end` is the surface form that opens
one. The block reuses the `end` terminator `concept` already established, so HML keeps one
block convention rather than two.

**Semantics, all measured:**

| | |
|---|---|
| inside the scope | `assume x > 0.0` licenses `log(x)` |
| after `end` | it does not |
| before the block | it does not |
| sibling scopes | do not share |
| nested scopes | expire innermost first |
| outer facts | remain visible inside |
| within a frame | order-independent (D-008, G5) |

**Contradiction is contained, not banned.** A frame whose own assumptions are jointly
unsatisfiable is marked `INCONSISTENT_LOCAL` and produces a **warning**, not an error.
Globally rejecting contradictory contexts would make proof by contradiction inexpressible,
which is the pattern this construct exists to enable. What is contained is *explosion*:
nothing inside an inconsistent frame licenses anything outside it — verified.

`pop()` returns the frame so that a future assumption-discharge rule can inspect its
consistency, which is exactly what concluding `not P` from a contradiction under `P`
requires.

**Detection is deliberately syntactic and incomplete.** It catches `x > 0` with `x < 0`
and `x = 0` with `x != 0`; it attempts no arithmetic. An undetected contradiction is not a
soundness hole — the frame simply is not flagged, and its facts still cannot leave.

**`consistency` is a verdict and is absent from the canonical form** (D-034 E1). Two
modules stating the same scoped argument are the same module whether or not one is
contradictory. Asserted by a test.

**Verification.** `pytest`: **6299 passed, 0 failed** (6279 before), 20 of them new.
`ruff`, `mypy` (89 files): clean. Hash stability: **0 changes**. Round-trip through the
`hml` backend is faithful and hash-stable. The freeze guard fired on the new keyword and
statement kind and was updated deliberately, not suppressed.

**Composition effect: 20/48 → 21/48 (0.417 → 0.438).** The single SCOPE-class failure
closed. This is the honest number: scoped Γ was never going to move a suite whose failures
are 14 GRAMMAR and 8 TYPE.

---

## D-044 — definedness is a property of TERMS, not of rules (closes a CRITICAL exploit)

**Date:** 2026-08-07 · **After:** `9877379` · **Implements:** D-036 · **Severity:** CRITICAL

**The exploit.** Found by adversarial review of the trusted-rule kernel, reproduced before
fixing:

```hml
assume p1 : a = b
goal   g1 : a * (1.0 / 0.0) = b * (1.0 / 0.0)
derive d1 : a * (1.0 / 0.0) = b * (1.0 / 0.0) from p1 by multiply_both_sides(by := 1.0 / 0.0)
proved g1 by d1
```
→ `d1 VERIFIED`, `g1 PROVED`, **0 obligations, 0 diagnostics, exit 0** — a literal
division by zero inside a certified statement.

**Root cause.** `ObligationSpec` was keyed on the **rule name**. `divide_both_sides`
declared `k != 0`; `multiply_both_sides` declared nothing, so the identical step spelled
differently walked past the guard. The rule was blameless — multiplying both sides by
anything really is valid. Nobody asked whether the thing being multiplied by was *defined*.

**Decision.** Definedness is a property of a **term**. `reasoning/partiality.py` holds one
contract registry (TOTAL / GUARDED / CONTRACTED / PARTIAL_UNDECIDABLE) and a pass that
walks every expression a derivation touches — conclusion and rule arguments alike —
generating a precondition for each CONTRACTED operation it finds, at any depth.
**A rule cannot evade a requirement it does not know about.**

**Measured after the fix:**

| | |
|---|---|
| `multiply_both_sides(by := 1.0 / 0.0)` | **REJECTED** |
| the same via `add_`/`subtract_both_sides` | **REJECTED** |
| nested `1.0 + (2.0 * (3.0 / 0.0))` | **REJECTED** |
| `1.0 / k`, nothing assumed | CHECKED |
| `1.0 / k` with `assume k != 0.0` | **VERIFIED** |
| `1.0 / k` with `assume k >= 0.0` | CHECKED — `>=` admits 0 |
| `x * 2.0` | VERIFIED |

**Refutation (D-038 V5).** An obligation decidably false by closed-literal inspection is
`FAILED`, not `OPEN`, and makes the derivation `REJECTED`. Reporting a known falsehood as
ignorance is strictly worse than saying nothing, and it is what let `1.0 / 0.0` look merely
unproven.

**The one genuine TCB reduction.** `divide_both_sides` lost its `ObligationSpec` — the term
pass covers it, and keeping it was worse than redundant, because it made the guard *look*
complete. Predicted by the rule audit as available only after this pass existed.

**Two defects introduced and caught while building this**, recorded because both were
self-inflicted:
1. The definedness obligations were appended to the list but the `entails` call lived
   inside the rule-obligation loop, so **nothing ever asked Γ about them** and they were
   permanently OPEN. One loop, one policy now.
2. `y / k = 2.0 * x / k` generated the same `k != 0` three times. Deduplicated by canonical
   identity — the language's own notion of "the same proposition", not a second one.

**Also fixed: `HML-T435`.** `Matrix[2,3] + Matrix[4,5]` compiled clean, while vector `+`
and matrix `@` were both checked — a silent shape loss in the one family where shape is
the whole point. Found by the full-ontology probe among 32 enforcement gaps (7 critical).

**Verification.** `pytest`: **6322 passed, 0 failed** (6299 before). `ruff`, `mypy` (90
files): clean. Hash stability: **0 changes**. Composition unchanged at 21/48 — this was a
soundness fix, not a coverage one, and it should not be reported as progress toward the
composition gate.

---

## D-045 — D-006 governs value declarations, not mathematical binders

**Date:** 2026-08-07 · **After:** `5888cd0` · **Severity:** high (coverage, not soundness)

**The defect.** D-006 rejects shadowing so that a nested *value* declaration cannot
silently change what a name means. That reasoning was applied to binders as well, and the
consequence was that **you could not differentiate with respect to a variable you had
declared**:

```
var x : Real
require derivative(f, x : Real) = 0.0     -> HML-N302
require integral(f, x : Real, 0.0, 1.0)   -> HML-N302
require forall x : Real . x = x           -> HML-N302
```

An ODE could not be written in one time variable. A gradient could not be taken with
respect to its own decision variable. The full-ontology probe traced 0% coverage in
several whole families back to this one rule.

**Decision.** Binder kinds are exempt from the shadowing rule. Values are not.

**Why this is safe, rather than a weakened barrier.** The machinery that makes it safe
already existed and was never at risk: `SymbolId` carries `(depth, ordinal)` and
canonicalises to `sym:#depth.ordinal`, so a binder and an outer value have distinct
identities regardless of spelling; resolution is lexical, so capture cannot occur.
Measured after the change:

| | |
|---|---|
| `derivative`/`integral`/`forall` over a declared name | accepted |
| nested same-name binders | accepted |
| body reference inside `forall x` where `x` is also a module var | resolves to `sym:#1.0`, **the binder** |
| `derivative(f, x)` vs `derivative(f, z)` | **identical content hash** — alpha-equivalence holds |
| a concept parameter shadowing a module `var` | **still HML-N302** |

Binding occurrences in a body is not an accident a binder might commit — it is what a
binder *is*. `integral(f(x), x, 0, 1)` where `x` is also a global is ordinary mathematical
notation, not an ambiguity.

**Eight tests asserted the old behaviour and were reversed deliberately**, each with the
reason recorded in place. The constitutional test of D-006 was not deleted: it was
re-pointed at a *value* declaration, which is what D-006 was always about.

**Verification.** `pytest`: **6328 passed, 0 failed** (6322 before).
**Composition: 21/48 → 22/48 (0.438 → 0.458).**

**On that number, plainly.** This fix was expected to be high-leverage for composition and
it moved one specimen. It is unambiguously right — it restores differentiation with respect
to declared variables — but the prediction that it would unlock a large share of the 14
GRAMMAR failures was **wrong**, and the remaining failures need their own diagnosis rather
than another hopeful structural fix.

---

## D-046 — the binder protocol, and the `free_names` omission it fixes

**Date:** 2026-08-07 · **After:** `63df820` · **Severity:** latent-critical (see measurement)

**The defect.** `verification/obligations/evaluate.py::free_names` dispatched by whitelist
— a branch for `Quantifier` and five operator kinds — and **fell through silently** for
everything else. D-026 added four binders and seven expression forms; none was added here.

```
free_names( integral(y, x : Real, 0.0, 1.0) > 0.0 )  ->  []       # y IS free
free_names( forall x : Real . y > x )                ->  ['y']    # correct
```

No exception, no diagnostic — just a shorter set.

**Measured consequence.** `free_names` feeds `ObligationTask.closed()`, which decides
whether an obligation may be treated as a ground term:

| | `free_names` | `closed()` |
|---|---|---|
| before | `[]` | **`True`** — claims fully pinned |
| after | `['y']` | `False` |

It also feeds the feasibility checker's domain construction, where an unseen name gets no
sampling domain and the joint-satisfiability search silently omits a dimension.

Both fail in the **dangerous** direction. End-to-end the wrong verdict is currently
prevented by an unrelated "outside the symbolic subset" guard downstream — so this is a
wrong answer produced and accidentally masked, not a wrong answer delivered. The mask
disappears the moment that subset is widened, which is planned work.

**The fix is a protocol, not eleven more branches.** Adding eleven branches would rebuild
exactly the fragility the compositionality study measured — 79 binder dispatch sites across
17 files, 7 of them handling only `Quantifier`. Instead `ast/nodes.py` gains:

* `binder_of(e) -> (bound_name, scoped_children, unscoped_children)`
* `expr_children(e)` — **structural**, so a node kind nobody has written a branch for still
  reports its children
* `BINDER_KINDS`

and `free_names` walks those. The twelfth expression kind is handled the day it is written.

**The part that must not be flattened.** The bound variable of an integral covers the
integrand and **not the limits**: in the integral of `x` from `0` to `y`, that `y` is free.
Same for a limit's approach point. A protocol reporting "all children are in scope" would
be as wrong as no protocol, only less visibly — so `binder_of` returns the two groups
separately and there are tests that fail on that specific over-correction.

**Verification.** `pytest`: **6342 passed, 0 failed** (6328 before), 14 new.
`ruff`, `mypy` (90 files): clean. Hash stability: **0 changes**.
Measured: free names reported inside quantifier, integral, derivative and comprehension;
bound names still not reported; an integral limit and a limit's approach point correctly
reported as free.

**Guard against recurrence.** `test_every_binder_kind_is_handled_by_the_protocol` iterates
`BINDER_KINDS` and fails if a sixth binder is added without a `binder_of` branch, and
`test_an_unknown_expression_kind_still_descends_structurally` pins the structural
fall-through on a node type that does not exist in the language.

---

## D-047 — the checked-certificate boundary, certified underdetermination, and the quantifier core

**Date:** 2026-08-09 · **After:** `22b4bb7` · **Implements:** Gold-10 GAP-0003, GAP-0004
· **Spec:** `docs/hml_v2/GOLD10_CORE_SEMANTICS_SPEC.md`

**Problem.** A forensic Gold-10 triage (Codex, corpus `467a486`, pinned HML `164d1946`;
`git diff --name-only 164d1946..22b4bb7 -- src/` is empty, so it inspected this exact core)
found the original 13.04% CoreGapRate did not survive review. Only **two** genuine generic
core-semantic gaps remained, plus one integration problem:

* **GAP-0003** — no sound terminal state meaning "the premises entail neither Q nor not-Q".
  `GoalStatus` had `OPEN`/`PROVED`/`REFUTED`/`UNSUBSTANTIATED` and nothing for a *certified*
  result.
* **GAP-0004** — no checked reasoning under a binder. `RULES` had sixteen rules and not one
  quantified; `_substitute` deliberately refuses to enter a `Quantifier`.
* **Integration** — HML already contained an exact rational evaluator with definitional
  unfolding, and none of it could feed the v2 `derive`/`proved` path, which admits exactly
  one source of truth: a kernel rule.

**Decision, in three parts.**

**1. One certificate boundary, not many rules.** Adding a rule per capability grows the TCB
once per mathematical fact anyone wants. Instead `reasoning/certificates/` provides a single
gate: envelope (claim/context/premise hashes, checker id) → **static** trusted registry →
`CheckedEvidence` or rejection. There is no registration path reachable from HML source or
library data; a library that could register `def always_valid(...): return VALID` would end
the TCB. Three checkers ship, each wrapping capability that already existed:
`closed_eval_v1`, `definition_unfold_v1`, `propositional_underdetermination_v1`.

**`equivalence/symbolic.py` is deliberately NOT registered.** Its own docstring is explicit
that `simplify(a - b) == 0` certifies equality and validity is decided by `satisfiable(...)`;
HML performs no independent replay of either. It is `UNTRUSTED_ORACLE` and may not certify a
derivation, regardless of the module using the word "certificate". The consequence is
recorded rather than engineered around: **Gold-10 G07's body `n + 0 = n` remains
library-level**, and the quantifier core is tested without it.

**2. Underdetermination is a judgment, not a status.** `Adjudication` binds verdict, target
hash, context hash, ordered premise hashes, support and checker; `GoalStatus.UNDERDETERMINED`
is its *projection*. The reason is monotonicity: Γ ⊭ P for a subset says nothing about Γ, so
a status word — which cannot say which Γ it was about — is not enough. Two consequences are
enforced and separately tested: a non-entailment certificate must **cover every established
claim in scope**, and it is **not spendable after the context changes**.

`UNKNOWN` and `UNDERDETERMINED` are different values and nothing converts one into the
other. Search failure, timeout, unsupported fragment, partial model, absent evidence — all
land on `OPEN`. Certified underdetermination carries two validated models of Γ that disagree
on the target; requiring both to satisfy Γ also certifies Γ satisfiable, so an inconsistent
context cannot acquire the status by this route.

**3. `forall_intro` / `forall_elim`, with a real eigenvariable condition.** Not a vague
"theorem application" primitive: ordinary theorem use composes from library theorem +
elimination + existing substitution.

The construction is the subtle part. HML's identity is locally nameless — `SymbolId.canonical()`
is `sym:#<depth>.<ordinal>` — and the resolver numbers a binder at nesting depth *d* as
`depth=d`, module declarations as `depth=0`. Measured:

```
assume a1 : n + 0.0 = n                        -- refs are sym:#0.0
goal   g1 : forall n : Natural . n + 0.0 = n   -- binder and refs are sym:#1.0
```

So wrapping the premise in a `Quantifier` builds a term the resolver would never produce and
the step would be rejected for a reason unrelated to its validity. `reasoning/binders.py`
re-depths the subtree instead. **No second notion of identity is introduced** — the point is
to let the existing `expr_identity` decide the comparison, and
`test_abstract_reproduces_the_resolvers_own_numbering` uses the resolver as the oracle for
five shapes rather than asserting hand-written expectations.

**The eigenvariable condition is deliberately stronger than the textbook one.** The textbook
rule quantifies over "undischarged assumptions the body proof depends on"; implemented as the
premise closure that would leave a hole, because HML discharges obligations against Γ via
`RefinementEnv.entails`, not only through cited premise edges — a derivation can rest on an
assumption it never names. So the implemented condition is: **no assumption in scope may
mention the variable freely**, including inside `scope` frames. This over-rejects, and that is
the safe direction.

**The kernel stays context-free.** `RuleSpec` gains `side_conditions: tuple[str, ...]`; the
kernel names them, `check.py` answers them from a static table, and an **unknown name
rejects** — a rule can never be admitted by a guard nobody implemented.

**Grammar.** Two statement forms, four keywords:

```
evidence     <id> : entails|determines_neither <prop> [from <id>,...] by <checker>[(<role> := e,...)]
undetermined <goal> by <evidence>
```

The judgement word is **mandatory**. `evidence e : P` would have to mean either "P holds" or
"P is exactly what the premises fail to settle" — opposites — and a reader must not infer
which from the checker's name. `entails` also appears in `QUARANTINED_SURFACE_FORMS` as the
head of the quarantined L3 form `entails p3 from [...] via ...`; here it is never a statement
head, the parser dispatches no statement on it, and that form remains rejected.

**Verification.** `pytest -q`: see the commit body for exact counts; 73 new tests across
`test_binders.py`, `test_certificates.py`, `test_underdetermination.py`,
`test_quantifiers.py`. `ruff check src/`: clean. The freeze gate fired as designed —
`FROZEN_KEYWORDS` and `FROZEN_STATEMENT_KINDS` had to be amended deliberately in the same
change, which is the mechanism working.

**Deliberately not implemented.** Existential introduction/elimination (Gold-10 exposed no
such gap; recorded as an expected sibling). Probability laws. Calculus laws. Arithmetic
rewrite rules. Any `x - 0 -> x`, `f(3)` or `n + 0 = n` special case. Those are libraries, and
the boundary above is how they will arrive without touching the kernel.

---

## D-048 — an absent domain annotation is unavailable evidence, not a violation

**Date:** 2026-08-10 · **After:** `7c9137a` · **Adjudicates:**
`docs/agent_handoffs/CLAUDE_SEMANTIC_FIREWALL_CLOSEOUT.md` §3, Decision 2 (`output_domain`)
· **Spec:** SF-R13, `experiments/semantic_firewall/requirements_handoff.json`

**Problem.** `7c9137a` recorded a divergence and kept it: this verifier checks
`action.typing.output_domain` against the produced claim's domain, and the frozen reference
checker never reads `output_domain` at all. The recorded justification was that the check is
*strictly stricter*, so it "cannot admit a corrupted transition — only question a
well-formed one". A purpose-built differential probe (26 candidate cases, both checkers)
showed that justification was too generous, and found two further divergences nobody had
written down.

Measured, production vs the frozen reference:

| case | produced / declared | this verifier | reference |
|---|---|---|---|
| both present, incompatible | `Boolean` / `Integer` | INVALID | VALID |
| both present, contained | `Integer` / `Real` | VALID | VALID |
| both present, reversed | `Real` / `Integer` | INVALID | VALID |
| **produced domain `null`** | `null` / `Integer` | **INVALID** | VALID |
| **produced domain key absent** | — / `Integer` | **INVALID** | VALID |
| control: no `output_domain` declared | `null` / — | VALID | VALID |
| **input domain `null`** | `null` / `Integer` required | **INVALID** | **UNRESOLVED** |

The guard was `not inhabits(produced.domain or "", expected_out)`. That `or ""` converts an
*absent* annotation into the empty string, which inhabits nothing — so a transition was
refused for **carrying no domain** rather than for carrying a wrong one. The control pins
the cause exactly: the same record with `output_domain` removed is VALID, so the rejection
is caused by the pair *(declaration present, annotation absent)* and by nothing else.

Two facts make that indefensible rather than merely strict. **SF-R13 is explicit** — *"return
unresolved rather than guessing when domain evidence is unavailable"* — and an absent
annotation is unavailability, not disagreement. And the neutral format **cannot represent the
alternative**: `semantic_case.schema.json` lists `domain` in the `claim` required set, while
this adapter's `_drop_none` omits null-valued keys on export, so "carries no domain" is
currently not expressible in a way that is both schema-valid and lossless. A transition was
being rejected for occupying a state the format cannot encode.

**Decision, in three parts.**

**1. Absence is collected as an unknown, not reported as a violation.** A claim the action
types whose domain the state does not declare, and a produced claim with no domain where
`output_domain` is declared, both now short-circuit to `UNRESOLVED` with the other unknowns.
Only annotations the action actually depends on are consulted — an unannotated claim nobody
typed is not this check's business, so this does not turn every sparse record unresolved.

**2. The `output_domain` check is retained where both annotations are present.** This is the
half that survives adjudication. Two annotations of one transition that disagree is a real
inconsistency, and the reference simply does not look. Classification: **REFERENCE_GAP** for
the both-present cases, **HML_OVERSTRICTNESS** for the absent-annotation cases, which is why
this record repairs one and keeps the other rather than choosing a side wholesale.

**3. The input-side null case is a repair, not a divergence.** `null` input domain now
returns `UNRESOLVED`, matching the reference exactly (`_type_domain` treats `None` and
`"UNKNOWN"` alike). It was reported as closed at `7c9137a` and was not: the containment
repair fixed the *comparison* and left the *absent* case reporting a hard mismatch.

**What was NOT changed.** `_collect_unknowns` sweeps claim domains in **both** states while
the reference reads only `state_before`, so an `UNKNOWN` domain on a produced claim is
`UNRESOLVED` here and `VALID` there. That divergence is **retained and recorded**: not
knowing the domain of the claim you just produced is unavailable evidence under SF-R13, and
the reference's silence is a gap in the reference. Classified **REFERENCE_GAP**, unchanged.

**Reversal cost.** Low. The behaviour is three conditions in `_check_type_domain` and
`_collect_unknowns`; no object, schema or surface changed. Reverting would restore a
verifier that rejects a transition for lacking an annotation.

**Verification.** All 30 frozen acceptance fixtures unchanged — none of them exercises any
of this, because `output_domain` is `"Proposition"` in 30/30 and equals the produced claim's
domain in 30/30, so the check is a no-op across the entire acceptance set. That is precisely
why the behaviour survived two commits: **nothing external tests it.**

**Recorded, not repaired here.** `experiments/semantic_firewall/schemas/semantic_case.schema.json`
declares `$defs/action` with `"additionalProperties": false` and no `properties` block while
`required` lists fifteen properties — an unsatisfiable subschema that rejects all 30 of its
own fixtures. That is a corpus-side defect and is reported through the handoff, not patched
from here.

---

## D-049 — the frame condition, and dependency-scoped unknowns

**Date:** 2026-08-10 · **After:** `7c9137a` · **Closes:** five confirmed acceptance defects
found by an independent post-build audit · **Spec:** `reference_checker.py::_exact_state_change`

**Problem.** An independent audit of `7c9137a` attacked the verifier rather than reading its
tests, and every finding reproduced against pristine production code:

| probe | verdict at `7c9137a` |
|---|---|
| a claim asserting `0 = 1`, status VERIFIED, materialising in `state_after` with no evidence, no warrant and no epistemic effect | **VALID** |
| an existing premise rewritten `ASSUMED -> VERIFIED` with its proposition changed | **VALID** |
| a candidate walked `PROPOSED -> VERIFIED` with `candidate_effect.kind: NONE` and zero constraints checked | **VALID** |
| the same from `REJECTED`, which `model.py` documents as terminal | **VALID** |
| a mandatory OPEN obligation deleted outright | **VALID** |
| one unrelated `status: UNKNOWN` claim appended to a corrupted transition | **flips 10/10 ILLEGAL fixtures to UNRESOLVED** |

**Root cause, and it is a single one.** The ten invariants all examine what the action
*declares*. Not one of them examined whether the resulting state is what applying that
declaration to the prior state would produce. There was no frame condition. Every other
rule was therefore optional: a producer that simply declined to declare an effect was not
checked, because the checks are keyed on the declaration. The candidate lifecycle is the
clearest case — `_check_candidates` returns early unless `kind == "PROMOTE"`, so the entire
promotion protocol, including the constraint-subset rule this project treats as the point
of the candidate object, is skipped by writing `NONE`.

The frozen reference has carried this all along as `_exact_state_change`. It was not
ported, and **no fixture could have revealed the omission**: all thirty are well-formed
records whose delta already matches their action, so a verifier with no frame condition
passes every one. This is the second time in three commits that a 30/30 pass rate concealed
a real defect, and the first time the defects ran in the unsafe direction.

**Decision.**

**1. A frame condition, checked last.** `state_after` must be `state_before` plus exactly
what the action produces. Existing records must be unchanged unless a *declared* effect
licenses the change — and then the effect's own invariant decides whether the change was
legitimate, so the frame does not forbid the transitions the system exists to make.
Additions are limited to the action's `output_id` and the obligations it creates. Checked
last so a more specific invariant claims the error class first, and reported as
`DEPENDENCY_VIOLATION`, which is where the reference reports it.

**2. Extended beyond the reference to candidates, branches and obligations.** The reference
frames claims only, so three of the six probes above are accepted by the reference too.
Matching it exactly would have left a verifier whose promotion rules can be skipped by
declining to mention them. Recorded as deliberate strictness, not silently inherited.

**3. Unknowns are dependency-scoped.** Only records the action actually cites — its
dependencies, its output, the claims it types, the candidate and branches its effects name —
can make a transition UNRESOLVED. Evidence unknowns were already scoped this way, which is
how we know the principle was understood and simply not applied to the rest. Unscoped, the
rule was not fail-closed but a denial of service: one junk record suppressed detection
entirely, and UNRESOLVED is counted as neither accepted nor detected.

**Retained as a known divergence, not repaired.** The reference runs every check and only
then asks whether anything was unknown, so on a transition carrying both a violation and an
unknown the reference says INVALID and this says UNRESOLVED. Matching it requires each check
to skip unknown values individually rather than the verdict short-circuiting — a larger
change than can be validated against thirty fixtures that never exercise it. Now narrow,
since the unknown must be on a record the action cites.

**Correction to the record.** `SEMANTIC_STATE_CONTRACT.md` §5a said the retained
`output_domain` divergence made this verifier "strictly stricter, so it cannot let a
corrupted transition through". That is true of `output_domain` and **false as a general
claim**: on the behaviours above production was strictly *weaker* than the reference it is
specified to match. The sentence is corrected rather than deleted.

**Reversal cost.** Moderate. `_check_frame` is additive and self-contained, but it changes
verdicts for any transition whose recorded delta does not match its action — including
under-specified *test* payloads, three of which it caught in this repository on first run.

**Verification.** All 30 acceptance fixtures unchanged, 30/30 verdict and error class. All
six probes above now INVALID or ineffective; the UNKNOWN suppression measured 0/10 against
10/10 before. Full suite green.

**What this does not fix.** The trust boundary (D-050): evidence `status` is still read from
the imported record, so a producer that authors the transition still authors the verdict.
The frame condition makes the *state delta* honest; it does nothing about self-asserted
evidence.

---

## D-050 — who may create VALID evidence: the boundary does not exist, and that is a blocker

**Date:** 2026-08-10 · **After:** `7c9137a` · **Status:** **BLOCKER for any use where the
transition is not authored by a trusted producer.** Classification, not a repair.

**The question.** A neutral, model-authored or otherwise untrusted transition must not be
able to write `status = "VALID"` on an evidence record and thereby become true. The chain
this project requires elsewhere is: proposed record → trusted checker → certificate binding
target, exact premises, rule, context identity and checker identity/version → *verifier-owned*
status.

**Finding: the chain does not exist in `semantic_state`.** Traced end to end and confirmed
independently:

* `"VALID"` is **never produced** anywhere in `src/`, only compared. Four sites read it —
  `verify.py:272`, `:381`, `:467`, `:581` — each `record.status == "VALID"`. The sole writer
  is `neutral.py:307`: `status=payload.get("status", "UNKNOWN")`. **The proposed record is
  the certificate.**
* `import_transition` validates exactly one field, `schema_version`. There is no
  attestation, signature, checker identity, checker version or context hash on evidence.
* `semantic_state` imports **nothing** from `reasoning/certificates/`, which is where this
  repository's actual trust machinery lives — `CertificateEnvelope` with claim and context
  hashes, a static versioned checker registry, and no registration path reachable from HML
  source or library data. Two separate paths exist and the attested one is not this one.

**`EvidenceRecord.trusted` is genuinely provenance-only, and that claim survives audit.**
Every read in `src/` is import, export or render; `verify.py` never consults it, and
flipping it changes no verdict. That was the *inert* field. `status` is the live one, and
the same untrusted producer sets it.

**Decision: classify, document, and do not paper over it.**

**1. This is not a divergence from the reference.** `reference_checker._valid_evidence`
reads `status` the same way. The property is inherited from the corpus's own design, in
which evidence status is *external ground truth* supplied by a trusted corpus and the
verifier's job is structural consistency between an action and its evidence.

**2. For that scope, the implementation is correct.** Offline replay of corpus-authored
records is what this package was built for, and within it the boundary is coherent.

**3. For the stated downstream use, it is a blocker.** Feeding model output through this
verifier means the model authors the action *and* its own evidence. Measured at `7c9137a`:
a transition with model-authored evidence, `trusted: false`, self-asserting
`"status": "VALID"`, promoting a claim to VERIFIED, is accepted. It measures whether the
producer bothered to attack, not whether the reasoning is sound.

**4. The precondition is now stated where it can be read.** `SEMANTIC_STATE_CONTRACT.md` §2
said "status is computed, never asserted". That is true of `CandidateStatus` and
`BranchStatus` and **not** of `EvidenceRecord.status`, and a reader will over-read it. The
contract gains an explicit precondition instead.

**Why not repaired here.** The repair is not a patch to the verifier: it is a decision about
where the trusted boundary sits for state transitions, and it must reuse
`reasoning/certificates/` rather than grow a second registry. That is an architectural
change requiring its own design record, and inventing one under an audit finding is how a
second unattested path gets built. Recorded as a blocker with the gate named.

**What bounds the exposure today.** `semantic_state` is imported by nothing outside
`tests/`. It is not on the `hml` CLI and has no runtime ingestion path, so nothing live is
exposed. **This is the only reason the classification is BLOCKER-before-use rather than an
incident.**

**Reversal cost.** Not applicable — nothing was changed.
