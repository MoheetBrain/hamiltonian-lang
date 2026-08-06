# INDEPENDENT_SEMANTIC_REVIEW — ACQ0 v2 corpus

**This is not human review.** Two read-only reviewers examined the corpus independently and
could not edit it. True human approval is still required before an official promotion
benchmark; it does not block this developmental acquisition screen, because both reviews
passed and every finding was repaired at the generator.

Two rounds: the original eight tasks, then the six authored after them. Round 2 mattered —
all four objective-bearing tasks are in it, so round 1 could not have seen the defect class
they carry.

---

## Round 1 — the original eight

**Reviewer A** (source vs ordered view vs prose, statement by statement): **45 rows —
31 EXACT, 14 AMBIGUOUS, 0 WRONG.** Every AMBIGUOUS verdict was backed by compiling the rival
reading and showing a different content hash, not by taste. The 14 collapsed into exactly
two systemic classes.

**Reviewer B** (partiality and well-posedness): **7 ACCEPT, 1 ACCEPT_WITH_EXPLICIT_LIMITATION,
0 REJECT.** The corpus contains exactly one partial-operation site: `eta / mu` with
`mu : PositiveReal`, total by the binder type alone.

| # | finding | repair |
|---|---|---|
| 1 | The **module header** appeared in no prose sentence, and the emission rule said "emit the records in encoding_statements" — which excludes it. The name is part of the content hash. | Prose line 0 names the module; the emission rule names the header explicitly. |
| 2 | A zero-binder `def` read "The value X … is defined by B", which also reads as `const X : T = B` and `var X : T = B`. All three compile; all three hash differently. | Prose names the statement kind: "The definition X takes no arguments, has codomain T and body B." |
| 3 | **`build_bundle` still served `structured_target()`** — the bucketed, order-free, `CheckStmt`-less view D-030 retired. Not on the run path, but it would have rebuilt the invalidating defect inside the "model-safe" bundle. | Serves `encoding_view`; demonstrations now carry their view as well as their encoding. |
| 4 | The bundle promised `MODEL_FILES/SHARED_HML_SEMANTICS.md`, **which does not exist in this repository.** With no glossary, finding 2 was load-bearing rather than pedantic. | The document is in-repo at `docs/evaluation/model_files/` and carried by value. |
| 5 | **`structured_target()` dropped `CheckStmt` everywhere downstream.** `required_public_facts` emitted no fact for the check; `check_prose_coverage` therefore certified full coverage for a task whose defining statement it could not see; and `acq0_semantic_diff` scored a submission that dropped the check as `equal: False` with an **empty difference list** — wrong, with no reason nameable. | `structured_target()` raises. The fact layer, the prose generator and the semantic diff all read `statement_records`, one traversal. A dropped `check` is now reported as `position 4, missing statement, kind check_dimension`. |

Reviewer B's summary of #5 — *"a schema advertising itself as `acq0.v2.lossless` is lossy
for the one task whose family it defines"* — is the reason `structured_target()` was retired
rather than patched.

---

## Round 2 — the six new tasks

**Reviewer A:** **28 source statements — 24 EXACT, 4 AMBIGUOUS, 0 WRONG**, plus 17
model-visible non-statement rows (13 EXACT, 4 AMBIGUOUS). Three root causes, not six
findings; the four AMBIGUOUS statement rows are one cause.

| # | finding | repair |
|---|---|---|
| 6 | **The objective was stated twice.** "The goal is to prove `X`." (the statement) sat beside "The goal is to prove X." (the objective) — one word apart, separated by other sentences. Emitting both **compiles** and hashes differently. The `objective` key was also the one model-visible field with no `emit` flag, and the emission rule excluded only `emit=false` records. | The objective carries `emit: False`; the emission rule names it; the prose sentence describes the already-listed statement and forbids a second. |
| 7 | **`render_prose` filtered the objective clause when `objective is None`, while `check_prose_coverage` still scored it** — two tasks certified EXACT for a sentence the prose never showed. The coverage gate walked one path and the model read another. | `render_prose` emits every clause `prose_clauses` produces; a test asserts every scored clause appears verbatim in the prose. |
| 8 | **A derived fact's provenance leaked a line of the answer.** `derived_from=("param lambda : PositiveReal",)` is verbatim line 2 of the surface-A reference, and the leak scan matched only whole sources and whole renderings. | Provenance is prose ("the declared type of lambda"); construction rejects provenance that is a verbatim source line; the bundle scan now also matches individual A/B/C reference lines, with a negative control proving it fires. |
| — | `render_question` produced "Decide whether **whether** …". Not in the ACQ0 bundle (`question` is forced to `None`) but visible in `h2_view`. | The verb carries no conjunction; the statement does. |

Each repair has a regression test; the leak scan and the duplicate-goal reading both have
negative controls.

**Reviewer B:** **2 ACCEPT, 2 ACCEPT_WITH_EXPLICIT_LIMITATION, 2 REJECT.** Both rejections
were correct and both tasks were replaced under fresh ids. Neither was a partiality defect —
the scanner's ACCEPT was right in both cases; the defects were in the *mathematics*.

| # | finding | outcome |
|---|---|---|
| 9 | **`v2_quantifier_scope_002`'s premise is FALSE.** `exists b : Real . forall x : Real . x < b` — instantiate the inner binder at `x := b` and it asserts `b < b`. An inconsistent premise entails everything, **including the converse the task explicitly prohibited**, so the discrimination it existed to make was vacuous; and its goal is a theorem of the reals, so the assumption did no work either. | Replaced by **`v2_quantifier_scope_003`**, quantifying over `Probability` — a **bounded** domain, where the premise is satisfiable, the goal is not a theorem, and the entailment holds only because the domain is non-empty. |
| 10 | **`v2_dimensional_algebra_003` named a definition `kinetic_energy` while omitting the 1/2.** `0.5 * mass * speed ^ 2` compiles *and* passes the dimension check, and every other occurrence of that identifier in this repository writes the coefficient. A model that knows physics — or that had seen the prior track_a item, which is this task with the `0.5` deleted — would be scored FAIL on a hash difference. Reviewer B named it "more dangerous than the false premise, because a vacuous `prove` yields a *null* measurement while this yields a *confidently wrong* one". | Replaced by **`v2_dimensional_algebra_004`**: the second moment of a point mass, `m * r^2`, which carries no coefficient, so identifier and body agree. |
| 11 | **The scanner failed OPEN on `concept` blocks.** A module whose only division sat in a concept transform printed the same ACCEPT line as a clean module. `SolveStmt`/`InferStmt` targets were also silently unwalked — the fallback tried three attribute names none of those nodes has. | `ConceptDecl` is walked with its members and binders; `targets` is walked; an unwired statement kind now **raises** instead of being skipped. |
| 12 | **ACCEPT carried no evidence of coverage** — "0 sites inspected" read identically for "clean" and "never looked". | The report counts statements walked: `ACCEPT — 5 statement(s) walked, 1 partial-operation site(s) inspected`. |
| 13 | **The v2 corpus was never contamination-checked.** `acq0_splits()` enumerates only v1 pools and nothing ran `PROOF_CORPUS` against them. | Wired in as a test: **0 collisions**, highest overlap 0.021 against a 0.60 threshold. Recorded honestly — it would *not* have caught finding 10, which scores ~0.04. The semantic review caught that one. |

Reviewer B's ACCEPT_WITH_EXPLICIT_LIMITATION verdicts, both retained as authored:

- **`v2_probability_law_role_002`** — roles verified complete against the distribution
  registry (`Gamma{shape,rate}`, `Poisson{rate}`), `lambda : PositiveReal` is *required* not
  merely appropriate (`Real` fails HML-T413), and the Gamma density is bounded at
  `shape = 2`. *Limitation:* a conjugate Gamma/Poisson pair with `objective=None` is the
  shape most likely to invite an unrequested `infer posterior lambda`.
- **`v2_assumption_boundary_002`** — jointly satisfiable, and nothing is entailed by
  anything else (`gain = 0.5` refutes the entailment of `amplified > input`), so every
  premise does work. *Limitation:* the premise set also entails `gain > 1`,
  `amplified > 0` and `input < 100`, none of which is listed as a derived fact.

---

## Standing limitations, not repaired

- **Task 2's `digamma` is a decoy** — declared, constrained by `digamma > 4`, and never
  used. Its derived fact `digamma != 0` is a red herring, since the only division is by the
  binder `mu`. Harmless (`emit=false`), and left as authored.
- **Prohibitions telegraph the family.** "Do not assume the converse holds" names an entity
  the formal object lacks. It is a capability hint, not a correctness fault.
- **Reviewer A's round-1 pass overlapped edits to the tree.** Their scope was prose and the
  view; the partiality scanner landed mid-pass and is what Reviewer B assessed. No finding
  from either was invalidated, and round 2 re-checked the repairs.
- **A derived fact stated in prose can be an H2 answer.** `render_prose` feeds `h2_view`
  too, and for `v2_quantifier_scope_002` the derived fact plus the assumption *is* the proof.
  Correct for ACQ0, which is translation-only; it must be revisited before H2 uses this task.

## Verdict

`INDEPENDENT_SEMANTIC_REVIEW: PASSED` — 0 WRONG across both rounds, 0 REJECT, every
ambiguity repaired at the generator and pinned by a test.
