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

## Open questions

| id | question | blocked on |
|----|----------|------------|
| Q-01 | Does the mandatory-role token cost exceed its accuracy benefit? | H5 measurement |
| Q-02 | Is the shadowing prohibition (D-006) too strict in practice? | H1 measurement |
| Q-03 | Is OpenMath reusable? No licence statement was found on openmath.org. | legal review |
| Q-04 | Does arm E's out-of-distribution status confound every comparison? | benchmark design |
| Q-05 | Should `Call` arguments be role-labelled too, or only `DistExpr`? | usage evidence |
