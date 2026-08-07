# HML v2 — reasoning-semantics design lock

**Status: decision record.** One entry per semantic choice made in `REASONING_MODEL.md`,
`SEMANTICS.md` and `OBLIGATIONS.md`. Format follows `DECISIONS.md`: question, options,
evidence, chosen, rejected and why, confidence, reversal cost.

The last section, §D — **Disagreements with locked decisions** — is the part written to be
read first. Silent compliance is not useful here; each disagreement is backed by an executed
measurement or a cited line of code, and each says exactly what would change my mind.

Base SHA `3dd4216` (`src/` byte-identical to audited `b1ac7bf`). All measurements were taken
against a pristine `git archive HEAD src` export, because the working tree is being edited
concurrently by the implementation workstream. **Nothing in this design is implemented, so
nothing in it has been tested.** Where a result is quoted, it is a measurement of the
*existing* base.

---

## D-V2-001 — Four derivation states, and VERIFIED has no surface spelling

**Question.** How many derivation states, and can source assert one?
**Options.** (a) two (`STATED` / `CHECKED`) · (b) four
(`PROPOSED` / `CHECKED` / `VERIFIED` / `REJECTED`) · (c) four plus
`VERIFIED_MODULO_ASSUMPTIONS`.
**Evidence.** `engine.py::_verdict` already demonstrates the pattern of writing a
verification conjunction exactly once so no caller can weaken it. The audit's C-6 shows what
happens when a reasoning word is not load-bearing.
**Chosen.** (b), with the CHECKED / VERIFIED distinction load-bearing: CHECKED means *the
rule applied correctly*, VERIFIED means *CHECKED and every mandatory obligation discharged*.
No surface production yields any status.
**Rejected.** (a) — collapsing them means "the algebra is right" and "the side conditions
hold" become one claim, and `divide_through by k` with `k = 0` would read as verified.
(c) — a fifth state duplicates what the dependency set already carries, and a status cannot
carry a set. A conditional result is VERIFIED with a non-empty dependency set.
**Confidence.** High. **Reversal cost.** Low while unimplemented; high afterwards, since
every backend and report keys on the enum.

---

## D-V2-002 — Reuse `v1/transformation.py` as a **catalogue**, not as the kernel

**Question.** The lead has locked "V2 reuses this registry". Reuses it as what?
**Options.** (a) as the kernel — derivations become `TransformationEdge`s ·
(b) as a catalogue of operations, edge kinds, prohibitions and obligation *taxonomy*, with a
new AST-level kernel · (c) ignore it and start fresh.
**Evidence, measured and read.**

* The module's own docstring: *"Nothing here claims to check a side condition."*
* `TransformationEdge.source: tuple[str, ...]`, `target: str`, `Node.text: str`. There is no
  `Expr` anywhere in the module, so it cannot reproduce a rule's output and compare canonical
  forms — check R8 of `REASONING_MODEL.md` §2.1, the check that distinguishes CHECKED from
  "written down".
* `OperationSpec.obligations` is `tuple[tuple[str, ObligationKind], ...]`; obligations are
  produced by `template.format_map(ctx)` and are **strings**. Every checker in
  `verification/obligations/checkers.py` consumes `Expr`.
* Its validation surface is genuinely valuable and genuinely complete: 30 operations, 30
  specs, 9 edge kinds, 5 obligation kinds, 8 inference rules with arities, 9 recorded
  prohibited coercions, plus `EDGE_DOMAIN` relatum checking and codes `HML-X601`–`X608`.
  Verified by execution.

**Chosen.** (b). The catalogue is reused essentially unchanged: `Operation`, `EdgeKind`,
`EDGE_DOMAIN`, `PROHIBITED_EDGE_COERCIONS`, `WarrantKind`, `INFERENCE_RULES`,
`CONVERSE_OPERATIONS`, `ObligationKind`, `Weakening`, the `asserted` / `reversed_entailment`
flags, and the structural checks R1–R7. The obligation *payload* changes from a format string
to an `Expr` builder, with the string retained for rendering.
**Rejected.** (a) — **it does not work, and the failure is silent rather than loud.** A kernel
built on string obligations generates obligations no checker can accept, so every derivation
sits at UNKNOWN forever. Ladder criterion 3.4 would pass and 3.5 would still fail, and the
VERIFIED rate would be structurally zero for any rule that generates an obligation, which is
most of them. (c) — throws away a correct 1,165-line taxonomy including a prohibition table
that took real thought.
**Confidence.** High on the diagnosis; medium on the `Expr`-builder shape, which is one of
several workable encodings.
**Reversal cost.** Low. The change is confined to one field of `OperationSpec`.

> This is a **partial disagreement with the lead's locked decision**, recorded in full at
> §D-1. The decision to reuse is right. The scope of the reuse cannot be "as-is".

---

## D-V2-003 — Mandatory iff asserted

**Question.** Which `ObligationKind`s gate VERIFIED?
**Options.** (a) all five · (b) a hand-maintained list · (c) a rule derived from existing
metadata.
**Evidence.** `OperationSpec.asserted` already exists and is `False` for exactly one
operation, `Operation.CONVERSE`, with the stated reason "stating a converse does not assert
it". An unasserted edge claims nothing, so nothing rests on its side conditions.
**Chosen.** (c). **An obligation is mandatory iff the edge that generated it is asserted.**
This makes `SIDE_CONDITION`, `HYPOTHESIS`, `CASE_SPLIT` and `DIRECTION` mandatory and
`CONVERSE` advisory, and it keeps working when an operation is added.
**Rejected.** (a) — would make a stated-but-unasserted converse block VERIFIED, which
punishes the author for being explicit about what they are *not* claiming. (b) — a second
place where the answer lives, guaranteed to drift.
**Confidence.** High. **Reversal cost.** Low.

---

## D-V2-004 — An obligation is not a goal; an assumption may close the first, never the second

**Question.** `v1/epistemic.py::DISCHARGES_GOALS[ASSUMPTION]` is `False`. The build requires
`assume x > 0` to discharge an `x > 0` obligation. Which gives way?
**Options.** (a) weaken `DISCHARGES_GOALS` · (b) refuse discharge-by-assumption ·
(c) distinguish the two objects and keep both rules.
**Evidence.** The audit's C-1 calls "assume x > 0; then log x is defined" *"every ordinary
mathematical argument"* and records that it is currently unwritable without discarding the
assumption's provenance. `v1/epistemic.py` declares itself the contract and says agents "must
not change it". `TransformationEdge.assumptions` and `ChainReport.dependencies` already exist
to carry assumptions forward.
**Chosen.** (c). A goal is something we set out to establish and is closed by proof or
refutation. An obligation is a side condition and is closed by the condition being
*available*. An assumption makes a condition available and records a dependency; it can never
make a goal PROVED.
**Rejected.** (a) — deleting the one table that stops "we failed to reject it, so we're done"
from closing an obligation. (b) — leaves C-1 open, which is the audit's "most serious
finding", and the whole reason for this build.
**Confidence.** High on the substance. Medium on the *word*: if "discharge" next to
"assumption" reads wrongly to the lead, renaming the operation (`satisfy`,
`assume-discharge`) costs nothing and the model is unchanged.
**Reversal cost.** Low.
**Guard tests.** `test_assumption_cannot_prove_a_goal`;
`test_dependency_survives_to_the_goal`.

---

## D-V2-005 — Semantic identity excludes every verdict, checker and witness

**Question.** What is in a derivation's content hash?
**Options.** (a) everything, including status · (b) the mathematics only · (c) the
mathematics plus the discharge evidence.
**Evidence.** Two arguments, both grounded in the existing codebase.
*Reproducibility:* `SymbolicIdentityChecker.version` is `"sympy-1.14.0"`. If checker version
were hashed, upgrading SymPy would rewrite the identity of every derivation that used it and
every ACQ0/H2 record would cease to be reconstructible.
*Falsifiability:* if status were hashed, "is this the same derivation?" and "did it check?"
become one question and a verification regression becomes undetectable, because the two runs
would look like different objects.
Precedent: `VerificationOutcome` already carries `content_hash` **and** `evidence_digest` as
two separate fields — the object and the run.
**Chosen.** (b). In: kind, rule name, canonical premise ids, role-sorted rule arguments as
`Expr`, conclusion as `Expr`, the generated obligation set as canonical propositions with
their kinds, any recorded weakening, and a discharge's target/evidence pair. Out: every
status, checker name and version, witness, evidence, detail, rejection reason, span, label
spelling, timestamp.
**Rejected.** (a) and (c) — both by the arguments above.
**Consequence that must be said out loud.** A content hash certifies *what was claimed*,
never *that it holds*. Two modules with the same hash may have different verdicts. Any tool
treating "hash matches a known-good hash" as "verified" is reading the artefact wrongly.
**Confidence.** High. **Reversal cost.** High once evidence has been recorded against the
hashes.

---

## D-V2-006 — `CANONICAL_VERSION` is **not** bumped; a `spec_version` key is emitted only when the module uses V2

**Question.** How is the schema change signalled without changing historical identity?
**Options.** (a) bump `CANONICAL_VERSION` to `hml-canonical-0.2.0` · (b) add an
unconditional `spec_version` key · (c) add a `spec_version` key gated on `uses_v2(module)`.
**Evidence, measured.**

```
A. V1-only module unchanged by adding a Statement subclass : True  (8b3acca3691c334c…)

unconditional extra field on the Assumption record:
  baseline hash : cc1c1a002958408c9f601d7ab51199a56055e10b83afc5d43e6ff28769fb20a1
  after   hash  : a4c37069e480d5fea44da4e7930608409b8acf3b149c7e5b39ffa593924f9cd1
  BYTE-IDENTICAL: False
```

`CANONICAL_VERSION` is emitted on every document (`canonical.py:259`), so (a) changes every
hash in the repository's history. (b) is measurably the same failure by a different route.
**Chosen.** (c). `uses_v2(module)` must be true for *every* V2-introduced field, not only the
new statement kinds — in particular, if a `label` is added to `AssumeStmt`, a module whose
assumptions are all unlabelled must omit the key rather than emit `null`.
**Rejected.** (a) and (b) — both violate the locked backward-compatibility rule, measurably.
**Acknowledged tension.** `canonical.py`'s docstring gives `CANONICAL_VERSION`'s purpose as
"tagging the schema version so a future change is detectable rather than silent". Freezing it
while the schema grows is exactly the silent change it was written to prevent. The gated
`spec_version` key restores detectability *for documents that changed*, which is the most
that can be had without breaking historical identity. This is a genuine cost and it is
recorded rather than argued away.
**Confidence.** High. **Reversal cost.** High — the hashes are load-bearing evidence.
**Guard test.** `test_v1_canonical_identity_is_unchanged` must compare against **committed
fixture hashes**, not hashes recomputed by the same build; otherwise a change that alters
every hash consistently passes.

---

## D-V2-007 — Close the canonical and surface fall-throughs in the same change

**Question.** What happens to a V2 statement the serialiser and the printer do not know?
**Options.** (a) leave the fall-throughs; the schema gate will catch it · (b) close both.
**Evidence, measured on the pristine base.**

```
canonical of an unknown statement : {"canonical_version":"hml-canonical-0.1.0",
                                     "module":"X","statements":[{"kind":"DeriveStmt"}]}
two DIFFERENT derivations collide in content_hash : True
hml surface text                  : 'module X\n\n# <unrenderable DeriveStmt>\n'
hml backend reports faithful      : True   (unsupported == [])
```

`canonical.py:244` returns `{"kind": type(st).__name__}`; `hml.py:225` emits a comment;
neither calls `drop()`.
**Chosen.** (b) — replace the canonical fall-through with a raise, and the printer
fall-through with `drop()`, and extend both dispatchers for the V2 statements.
**Rejected.** (a). The schema gate does fire —
`'DeriveStmt' is not one of ['Declaration', …]` — but only inside
`scripts/conformance.sh` and only over `examples/`. Meanwhile the in-process behaviour would
**identify objects that differ** (criterion 2.4, currently `PASS`) and **omit a construct
silently** (criterion 2.7, currently `PASS` with "0 truly silent losses", and named in
`backends/base.py` as the worst failure mode in the codebase). Landing V2 without this
demotes two criteria the project passes today.
**Also required.** `ast/nodes.py::walk` descends only into `Node`, `Arg` and `ConceptMember`
(lines 369-385). A rule-argument class that is none of those is invisible to `walk`, and
`walk` is what `engine.py::_provenance_map`, `_signature_tasks` and the backends use to find
expressions. Make the rule-argument class a `Node`, or reuse the existing `Arg`.
**Confidence.** High — all three are measured or read directly.
**Reversal cost.** Low.

---

## D-V2-008 — Surface `UNKNOWN` is a presentation of `{UNSUPPORTED, INCONCLUSIVE}`

**Question.** Two four-valued obligation vocabularies exist. Which wins?
**Options.** (a) replace `records.py`'s enum with the contract's · (b) use `records.py`'s
five-valued set at the surface · (c) map, and keep both.
**Evidence.** `records.py` argues that collapsing `UNSUPPORTED` and `INCONCLUSIVE` "would
hide which of the two is growing" — the first means *this system has no theory for that*, the
second *this system tried and came back empty*. That is a real distinction and it is the kind
of thing this project measures.
**Chosen.** (c). Surface and diagnostics use `OPEN | DISCHARGED | FAILED | UNKNOWN`; the
record retains which of the two `UNKNOWN` was. The mapping is total and gate-preserving:
`OPEN`, `UNSUPPORTED` and `INCONCLUSIVE` all block VERIFIED, so nothing is lost but a word.
**Rejected.** (a) — destroys a distinction the project deliberately built. (b) — pushes a
verification-internal distinction into the language surface, where a model writing HML has no
way to act on it.
**Confidence.** High. **Reversal cost.** Low.
**Guard test.** `test_unknown_retains_its_record_class`.

---

## D-V2-009 — Five goal states, not four

**Question.** `GRAMMAR_CONTRACT.md` §3 gives `OPEN | PROVED | REFUTED | ASSERTED_UNCHECKED`.
The AST being written in the implementation workstream gives
`OPEN | PROVED | REFUTED | UNSUBSTANTIATED`, with a different meaning for the fourth.
**Evidence.** They are different states. `ASSERTED_UNCHECKED` is a v1 `prove` that nobody
tried to establish. `UNSUBSTANTIATED` is a `proved g by d` claim that was adjudicated and did
not hold up. Merging them makes "nobody tried" indistinguishable from "somebody tried and it
failed" — the same collapse `records.py` refuses for `UNSUPPORTED` / `INCONCLUSIVE`, for the
same reason.
**Chosen.** Five: `OPEN | PROVED | REFUTED | ASSERTED_UNCHECKED | UNSUBSTANTIATED`.
**Rejected.** Either four-valued set alone.
**Confidence.** High on the distinction; this needs the lead's arbitration on the naming.
**Reversal cost.** Low while unimplemented.

---

## D-V2-010 — A stated definedness policy: restrict by type where expressible, otherwise generate an obligation

**Question.** `MINIMAL_SEMANTIC_BASIS.md` §5 finds HML has *no* policy — `sqrt` and `log`
restricted, division / `tan` / `^` / indexing unguarded, "not a design, it is a pair of
special cases".
**Options.** (a) totalise, as Lean does (`(1:Nat)/0 = 0` by `rfl`) · (b) underspecified total
functions, as SMT-LIB · (c) preserve the failure as data, as OpenMath's `OME` ·
(d) restrict by argument type where the scalar lattice can express it, and generate an
obligation where it cannot.
**Evidence.** The audit explicitly corrects one of its own criticisms here: *"it is not a
defect that HML fails to prove `x ≠ 0`; Lean does not either"*. Any of the five observed
treatments applied consistently would be defensible. What is not defensible is having none.
**Chosen.** (d). Type restriction applies at a *declaration*; an obligation applies at a
*use site*. `log(x)` can restrict what `x` may be; `a / b` cannot, because `b` is an
arbitrary expression.
**Rejected.** (a) — the most rigorous system in the panel does this, so it is defensible in
general, but it makes the "divided by something that might vanish" error *disappear* rather
than be caught, and that error is the one HML's thesis names. (b) and (c) — coherent, but
each requires machinery (underspecification, an error term in the expression language) that
does not exist and that no measured requirement justifies.
**Cost, stated.** Previously-clean modules will report UNKNOWN obligations and the VERIFIED
rate on any existing corpus will fall. That is the intended direction, but it must be
measured before and after, not discovered afterwards.
**Confidence.** Medium-high. **Reversal cost.** Medium.

---

## D-V2-011 — Substitution is capture-avoiding and probability-kind-aware

**Question.** `Operation.SUBSTITUTE` is the first substitution HML has ever had. What does it
have to respect?
**Evidence.** The audit's 2.8 result is *"PASS (partial) … Capture-avoidance is untested
because HML has no substitution statement."* And `domains.py:198-203` gives `Probability`,
`PValue` and `PosteriorProbability` the **same interval**, with the mitigation "this table is
consulted by name, never by subtyping" — a mitigation that holds only because nothing today
can replace one name with another.
**Chosen.** Substitution alpha-renames any binder whose name occurs free in the substituted
term, and is checked against `probability_coercion_allowed` before any interval reasoning.
Both are preconditions for admitting `substitute` to the trusted rule set.
**Rejected.** Naive substitution — unsound, and *silently* so: the captured result type-checks.
**Note.** `HML-N302` rejects shadowing at the source level, which removes one class of
capture there. It removes none at the derived level unless the kernel re-runs resolution on
the conclusion, which `SEMANTICS.md` §0 requires it to.
**Confidence.** High. **Reversal cost.** Low.

---

## D-V2-012 — The claim namespace is disjoint from the value namespace, and claim labels are binders

**Question.** Do `d1`, `g1`, `a1` live with `x`, `theta`?
**Chosen.** Disjoint. `d1 + 1` is a scope error (`HML-R902`), not a type error. Labels
canonicalise positionally as `claim:#<ordinal>`, mirroring `SymbolId.canonical()`, assigned by
a deterministic declaration-order traversal.
**Rejected.** A shared namespace — it would let a derivation be smuggled into an expression,
putting provenance inside the mathematics and defeating D-V2-005 directly.
**Confidence.** High. **Reversal cost.** Low.
*(The implementation workstream has already written this. It is endorsed and made normative.)*

---

## D-V2-013 — Reuse `Resolver._find_cycle` for the derivation DAG

**Question.** New cycle detector or existing one?
**Chosen.** Existing. `semantics/__init__.py:290-325` is an iterative DFS with three-colouring
that returns one cycle as a path and is generic over `dict[str, list[str]]`. The claim graph
is that shape.
**Rejected.** A second detector — two cycle detectors with different behaviour on the same
repository is a liability, and this one already carries the reasoning the project wants
("every inference needs traceable dependencies").
**Confidence.** High. **Reversal cost.** Low.

---

## D-V2-014 — `HML-R9xx` for the reasoning layer

**Question.** Which diagnostic range?
**Evidence.** `grep -rc "HML-R" src` returns no matches: the family is free. `HML-X6xx`
(used by `transformation.py`) shares its numeric range with the documented `HML-S6xx`
semantic family, and the range table in `diagnostics/__init__.py:7-14` does not mention the
`E`, `G`, `V` or `X` families already in use.
**Chosen.** `HML-R901`–`HML-R910`, and extend the documented range table in the same change.
**Confidence.** High. **Reversal cost.** Low.

---

# §D — Disagreements with the lead's locked decisions

Four. Ordered by how much they would cost if not addressed.

## D-1 — "V2 reuses `v1/transformation.py`" is right; "reuses it as the kernel" is not workable

**The locked decision.** *"The LEAD HAS DECIDED: V2 REUSES this registry rather than
inventing a new one."*

**Where I agree.** Completely, for the taxonomy. The 30 operations, 9 edge kinds, the
prohibition table with its recorded reasons, the `asserted` / `reversed_entailment` flags and
the structural checks are correct, complete (30/30 specs, verified) and better than anything
that would be written from scratch under time pressure.

**Where the code says it cannot be reused as-is.** Two facts, both read directly:

1. **Obligations are Python format strings.** `OperationSpec.obligations` is
   `tuple[tuple[str, ObligationKind], ...]`; `TransformationEdge.obligations()` produces
   `Obligation.condition: str` via `template.format_map(ctx)`. Every checker in
   `verification/obligations/checkers.py` consumes `Expr` and pattern-matches on
   `Comparison`, `Ref`, `Call`, `Quantifier`.
2. **Edges relate names, not expressions.** `source: tuple[str, ...]`, `target: str`,
   `Node.text: str`. There is no `Expr` in the module.

**Consequence if the decision is taken literally.** Every generated obligation is `UNKNOWN`
by construction, because nothing can turn `"{by} != 0"` into something a checker accepts. And
no derivation can ever reach CHECKED, because reaching CHECKED requires reproducing the
rule's output and comparing canonical forms, and the module never holds an output. The build
would ship a reasoning layer that states obligations it can never discharge and asserts steps
it can never check — which is the state the audit already records, relocated to a new file.
The module says this about itself: *"Nothing here claims to check a side condition."*

**Recommendation.** Keep the catalogue. Change `OperationSpec.obligations` from a string
template to an `Expr` builder taking the edge's typed arguments and premise/conclusion
expressions, retaining the string alongside for rendering. The templates that cannot become
expressions — *"the identity `{warrant}` holds on the domain of `{source}`"*,
*"`{source}` is differentiable with respect to `{wrt}`"* — stay textual and stay permanently
`UNKNOWN`, which is the correct and honest answer and blocks VERIFIED as it should.

**What would change my mind.** A demonstration that a string obligation can be routed to a
checker without a round trip through the parser, or a decision that V2 ships obligation
*generation* only (criterion 3.4) and defers discharge (3.5) — in which case the string form
is adequate and this objection disappears. But `EXECUTIVE_VERDICT.md` is explicit that P1,
P2 and P4 buy Level 3 "**only as a set**. Any one alone is close to worthless."

---

## D-2 — Strict canonical additivity is achievable, but `GRAMMAR_CONTRACT.md` §5 as written violates it

**The locked decision.** *"a module using NO V2 construct must produce BYTE-IDENTICAL
canonical JSON and the same content_hash as it does today."* And `GRAMMAR_CONTRACT.md` §5:
*"`canonical_json` gains `"spec_version": 2`."*

**Verdict on achievability: yes, and it was tested.** `_statement` dispatches by `isinstance`
and `_to_canonical` computes nothing module-wide, so a module containing no V2 statement
traverses exactly the branches it did before. Measured: a v1-only module is byte-identical
after a new `Statement` subclass is defined, hash `8b3acca3691c334c…`.

**The two clauses are in direct conflict as written.** Adding a top-level key unconditionally
changes every hash. Demonstrated with an unconditional field addition:

```
baseline : cc1c1a002958408c9f601d7ab51199a56055e10b83afc5d43e6ff28769fb20a1
after    : a4c37069e480d5fea44da4e7930608409b8acf3b149c7e5b39ffa593924f9cd1
BYTE-IDENTICAL: False
```

And it is rejected by the schema:

```
spec_version doc REJECTED by schema:
  Additional properties are not allowed ('spec_version' was unexpected)
```

**Resolution.** §5's *intent* — "v1 modules must canonicalise byte-identically to their v1
form" — is right; its *mechanism* must be gated. Emit `spec_version` only when
`uses_v2(module)`; do not bump `CANONICAL_VERSION`; extend `spec/ir.schema.json` in the same
change. The implementation workstream has already written the gating predicate; this document
makes it normative and extends its scope to every V2-introduced field, including an
`AssumeStmt.label` that must be omitted rather than emitted as `null`.

**Residual cost, not argued away.** `CANONICAL_VERSION` exists "so a future change is
detectable rather than silent". Freezing it while the schema grows is precisely the silent
change it was written to prevent. A gated `spec_version` restores detectability for the
documents that changed, which is the most that can be had without breaking historical
identity. That is a real loss and it should be recorded in `DECISIONS.md` proper, not only
here.

---

## D-3 — Landing V2 without closing two fall-throughs would demote two criteria the project currently passes

**Not a disagreement with a stated decision** — it is a consequence of the plan that does not
appear to have been costed.

`backends/canonical.py:244` returns `{"kind": type(st).__name__}` for an unknown statement.
`backends/hml.py:225` emits `# <unrenderable X>`. Neither calls `drop()`. Measured:

* two structurally different derivations **share a content hash** (`True`);
* the HML backend reports **`faithful == True`** while replacing the statement with a comment.

The first identifies objects that differ — maturity criterion 2.4, currently `PASS`, whose
check is stated in exactly those terms. The second is a silent omission — criterion 2.7,
currently `PASS` with "0 truly silent losses", and named in `backends/base.py` as the worst
failure mode in this codebase.

The schema gate does fire (`'DeriveStmt' is not one of [...]`) but only in
`scripts/conformance.sh` and only over `examples/`. In-process, the collision is real.

Third instance, same class: `walk` (`nodes.py:369-385`) descends only into `Node`, `Arg` and
`ConceptMember`. A new rule-argument class outside those three is invisible to `walk`, and
`walk` is how `_provenance_map`, `_signature_tasks` and the backends find expressions. Rule
arguments would silently escape all of them.

All three are cheap to fix and expensive to discover later.

---

## D-4 — The audit understates C-1: `assume` does not merely fail to discharge, it lets the verifier *refute*

**Not a disagreement with the lead** — a correction to the shared evidence base, and in my
judgement the highest-value single finding in this analysis.

The audit records that `assume x > 0.0` does not discharge `log`'s `PositiveReal` domain.
Reproduced. But the stronger fact is:

```
module A                                     module B
var x : Real                                 var x : PositiveReal
assume x > 0.0                               prove x > 0.0
prove x > 0.0
                                             → VERIFIED
→ DISPROVED
  [FAILED] numerical_counterexample/universal  x > 0.0
    witness: this assignment satisfies every declared type
             constraint and makes the obligation false
```

The verifier does not say "cannot tell". It says **DISPROVED, with a witness**, for a goal
that follows in one step from the module's own stated assumption. The same mathematics with
positivity moved into the declaration returns VERIFIED.

Cause, localised to one function: `verification/obligations/evaluate.py::build_environment`
(lines 169-229) reads `Declaration`, `DefineStmt` and `ConceptDecl` and **never reads
`AssumeStmt`**. The counterexample search then draws `x = -1` from `Real`'s unnarrowed domain.

This is a confident false negative. `ObligationMode`'s own docstring names the class:
"treating a `prove` as `SATISFIABLE` produces confident false successes" — this is the mirror
image. It is a **precondition** for the discharge rule in `OBLIGATIONS.md` §4 D2, not an
enhancement: until it is fixed, no derivation depending on an assumption can be VERIFIED and
some will be actively refuted.

**Related, and easy to miss.** No CLI subcommand invokes the discharge engine at all
(`cli/__init__.py:48-150`: `check`, `render`, `canonical`, `hash`, `graph`, `obligations`,
`views`). So the audit's headline is true of `hml check` and *not* of the engine — invoked
directly, `verify_source` refutes `prove 1.0 = 2.0` correctly, with a witness. The accurate
statement of the gap is therefore narrower and more actionable than "HML cannot refute
`1 = 2`": **the capability exists and is not wired to the surface.** Adding `hml verify` is a
small change with a large effect on whether the reasoning layer is visible to a user or a
model at all.

---

## Verification log

| check | command | result |
|---|---|---|
| `prove 1.0 = 2.0` compiles clean | `.venv/bin/hml check t1.hml` | `ok: T1 …`, exit 0 |
| `assume` does not discharge `log` | `.venv/bin/hml check t2.hml` | `HML-T427`, exit 1 |
| catalogue inventory | `python -c "from hamiltonian_lang.v1 import transformation …"` | 30/30 ops, 9 edge kinds, 5 obligation kinds, 8 rules, 9 prohibitions |
| v1-only canonical additivity | pristine-HEAD script | byte-identical, `8b3acca3691c334c…` |
| unconditional field cost | pristine-HEAD script | hash changes; both hashes recorded above |
| canonical fall-through collision | pristine-HEAD script | `True` |
| HML backend silent loss | pristine-HEAD script | `faithful == True` |
| schema rejects new kind and new key | `jsonschema.validate` | both rejected; messages quoted |
| interval discharge truth table | pristine-HEAD script | quoted in `OBLIGATIONS.md` §6 |
| `assume` + `prove` → DISPROVED | `verify_source` | reproduced |
| `verify_source` refutes `1.0 = 2.0` | `verify_source` | reproduced |
| `HML-R` family free | `grep -rc "HML-R" src` | no matches |
| **full test suite** | `python -m pytest -q` | **NOT RUN** — worktree under concurrent edit; a mid-edit result is not attributable |
| **any V2 behaviour** | — | **NOT IMPLEMENTED, NOT TESTED** |
