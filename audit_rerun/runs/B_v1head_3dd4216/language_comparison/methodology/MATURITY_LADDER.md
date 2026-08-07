# Maturity Ladder

Status: normative. Assigns each compared system a level 0–4 by mechanically
checkable criteria.

---

## 0. How to read this ladder, and how not to

**Higher is not universally better.** The levels describe *what kind of artefact*
a system is, not how good it is. Several of the most successful mathematical
systems in existence deliberately occupy a lower level and are correct to do so:

- A well-designed **domain DSL** (level 1) is often better for its domain than a
  general IR: it can make the domain's invariants unavoidable and its notation
  match the field's conventions exactly.
- A **general mathematical IR** (level 2) that translates between formats does
  not need proof checking and is not deficient for lacking it.
- A **formal system** (level 4) buys soundness with a very large cost in
  writability and in the amount of mathematics that has been formalised at all.
  Levesque and Brachman's expressiveness/tractability tradeoff is real: level 4
  systems are less able to accept an informal-but-useful statement.

The ladder is therefore used to answer "what is this system, and does it satisfy
the necessary conditions for what it claims to be?" — not to rank systems on a
single axis. A system that claims level *n* and fails a level-*n* criterion has a
falsified claim; a system that is honestly level *n−1* has not.

**Level assignment is the minimum of all criteria.** A system is at level *n* iff
it satisfies **every** mandatory criterion for levels 0..*n*. One failed
criterion caps the system at the level below, regardless of how many higher-level
criteria it satisfies. Partially satisfied criteria never round up.

**Criticality gate.** Independent of the criteria below, a system with any
CRITICAL ontology atom scored `0` or `L(silent)` is capped at **level 1**,
because a critical silent loss disqualifies an artefact from being a general
representation whatever else it can do. The failing atom ids must be named
wherever the level is reported.

**Evidence.** Every criterion is marked `MECHANICAL` (checkable by running a
command or a script) or `NEAR-MECHANICAL` (checkable by inspecting a named
artefact against a stated rule, with the judgement recorded). No criterion is a
matter of impression. Each criterion below is stated so that a third party with
access to the system can reach the same verdict.

---

## LEVEL 0 — TOY SYNTAX

*A notation that exists but is not yet a system.*

Mandatory criteria (all must hold to be **at least** level 0):

| # | Criterion | Check |
|---|---|---|
| 0.1 | A grammar exists in some written form (BNF, PEG, parser source). | MECHANICAL: the artefact exists. |
| 0.2 | A parser accepts at least one non-trivial example and rejects at least one malformed input. | MECHANICAL: run both. |
| 0.3 | The set of accepted inputs is not obviously ambiguous by construction — or the ambiguity is documented. | NEAR-MECHANICAL: inspect grammar for unresolved ambiguity; document findings. |

Characteristic of level 0 (satisfied 0.x but not all of 1.x): parsing exists, but
meaning does not. There is no type discipline, no rejection of semantically
ill-formed input, and no defined semantics for the accepted forms. Whether a
statement means anything is decided by the reader.

---

## LEVEL 1 — DOMAIN DSL

*A notation with real semantics, scoped to a bounded domain.*

Necessary conditions for the transition 0 → 1: **1.1 through 1.7 all hold.**

| # | Criterion | Check |
|---|---|---|
| 1.1 | A written specification states the meaning of every accepted construct, not merely its syntax. | NEAR-MECHANICAL: for each grammar production, locate its semantic clause. Report the fraction with no clause; must be 0. |
| 1.2 | Semantically ill-formed but syntactically valid inputs are **rejected**, not accepted-and-ignored. | MECHANICAL: an adversarial suite of ill-formed inputs; every one must produce a non-zero exit and a diagnostic. |
| 1.3 | Name resolution: every identifier is resolved or the input is rejected. No silent treatment of unknown names as opaque atoms. | MECHANICAL: probe with an undeclared name; must be rejected. |
| 1.4 | A type or sort discipline exists and is enforced for at least the domain's own kinds. | MECHANICAL: probe a type violation within the domain; must be rejected. |
| 1.5 | The declared domain of applicability is stated explicitly in the documentation. | NEAR-MECHANICAL: locate the statement. |
| 1.6 | An executable test suite exists that covers accept and reject cases and runs to green. | MECHANICAL: run it; record the command and result. |
| 1.7 | Every example shipped with the system parses and checks, or is explicitly marked as illustrative. | MECHANICAL: run the checker over all shipped examples. |

A level-1 system is a legitimate, complete artefact. It is *not* claiming to
represent mathematics in general, and must not be scored as if it were: report
its coverage restricted to its declared domain **as well as** globally, and label
the global figure as out-of-declared-scope.

---

## LEVEL 2 — GENERAL MATHEMATICAL IR

*A representation for mathematical objects across domains, with a defined
internal form that other tools can consume.*

Necessary conditions for the transition 1 → 2: **all of 2.1 through 2.10.**

| # | Criterion | Check |
|---|---|---|
| 2.1 | Coverage: weighted faithful coverage (`P`/`S`/`C`) ≥ 0.60 across **all 13** ontology domains, and ≥ 0.40 in **each** domain individually. | MECHANICAL from the coverage matrix. |
| 2.2 | No CRITICAL atom scored `0` or `L(silent)`. | MECHANICAL from the coverage matrix. |
| 2.3 | A stable, documented internal representation (AST or equivalent) is exposed to consumers, with a versioned schema. | NEAR-MECHANICAL: the schema artefact exists and validates the emitted form. |
| 2.4 | A canonical form exists, is documented, and is **semantics-preserving**: it does not identify objects that differ (notably, it must not commute non-commutative operands, must not drop qualifiers, and must respect alpha-equivalence). | MECHANICAL: adversarial canonicalisation suite including `A*B` vs `B*A`, `∀∃` vs `∃∀`, `=` vs `≈`. |
| 2.5 | Round-trip fidelity: parse → print → parse yields an identical canonical form for the whole example corpus. | MECHANICAL: automated round-trip test over all examples. |
| 2.6 | Type checking is enforced across domain boundaries, not only within one domain (e.g. a shape error inside a probabilistic statement is caught). | MECHANICAL: cross-domain adversarial probes. |
| 2.7 | At least one translation to an external target exists, and translation **loss is reported in a machine-readable form** naming what was dropped, approximated or weakened. Silent omission of an unsupported construct is a hard failure of this criterion. | MECHANICAL: translate a construct the target lacks; assert a loss record is emitted. |
| 2.8 | Binding structure is correct: capture-avoiding substitution and alpha-equivalence are implemented and tested. | MECHANICAL: capture-avoidance test vectors. |
| 2.9 | Diagnostics are localised: a rejection names the offending construct and its position. | NEAR-MECHANICAL: sample 20 rejections; ≥ 90% must locate the error within the offending construct. |
| 2.10 | Compositionality: ≥ 0.70 on the composition specimen suite, with zero `COMPOSES_SILENT_LOSS` on specimens involving a CRITICAL atom. | MECHANICAL from the composition results. |

Level 2 is where "interchange format" claims live. Note that 2.7 is the criterion
most often failed in practice, and it is failed *silently* — which is why it is
mandatory here rather than aspirational.

---

## LEVEL 3 — MATHEMATICAL REASONING IR

*A representation that not only stores mathematics but supports meaning-preserving
manipulation and epistemic bookkeeping.*

Necessary conditions for the transition 2 → 3: **all of 3.1 through 3.9.**

| # | Criterion | Check |
|---|---|---|
| 3.1 | All level-2 criteria hold, with coverage raised to ≥ 0.80 weighted overall and ≥ 0.60 in every domain. | MECHANICAL. |
| 3.2 | Every CRITICAL and HIGH atom is scored `P`, `S` or `C`. No `B` or `L` in those bands. | MECHANICAL. |
| 3.3 | Assumptions are first-class and **scoped**: an assumption introduced in a local context does not leak out of it, and the active assumption set at any point is enumerable. | MECHANICAL: probe a locally scoped assumption and assert it is unavailable outside. |
| 3.4 | Side conditions are generated, not assumed: using a partial operation (division, inverse, log, square root) produces an inspectable obligation. | MECHANICAL: probe each partial operation; assert an obligation object is produced. |
| 3.5 | At least one non-trivial semantics-preserving transformation is implemented **with a preservation check** — not merely applied and asserted. | MECHANICAL: the transformation and its check both run; the check must fail on a deliberately broken variant. |
| 3.6 | Epistemic status is representable and preserved through transformation: assumed / derived / approximate / observed / unknown survive a round trip and a transformation. | MECHANICAL: status-preservation test vectors. |
| 3.7 | Approximation is a distinct relation from equality, carries an error term or bound, and does not silently degrade to equality anywhere in the pipeline. | MECHANICAL: adversarial `≈`-vs-`=` suite including chained approximations. |
| 3.8 | The representation is queryable: structural questions ("which statements assume independence?", "which results are approximate?") are answerable mechanically. | MECHANICAL: run three such queries and check the answers against a hand-audited ground truth. |
| 3.9 | Compositionality ≥ 0.85 with zero `COMPOSES_SILENT_LOSS` anywhere in the suite. | MECHANICAL. |

Level 3 is the level at which a system can honestly claim to represent
*reasoning* rather than *notation*. The distinguishing capability is 3.4 + 3.5:
the system produces obligations and checks its own transformations.

---

## LEVEL 4 — FORMAL MATHEMATICAL SYSTEM

*A system in which mathematical claims are proved and the proofs are
independently checked.*

Necessary conditions for the transition 3 → 4: **all of 4.1 through 4.8.**

| # | Criterion | Check |
|---|---|---|
| 4.1 | All level-3 criteria hold. | MECHANICAL. |
| 4.2 | A formal deductive calculus is specified: the inference rules are enumerated, and no rule is implemented that is not specified. | NEAR-MECHANICAL: enumerate implemented rules; diff against the specification; the difference must be empty. |
| 4.3 | Proofs are objects that can be stored, transmitted and re-checked independently of the process that produced them. | MECHANICAL: export a proof, check it in a separate process, assert acceptance. |
| 4.4 | A **small trusted kernel**: the code that must be correct for soundness is identified, bounded, and separated from the rest. | NEAR-MECHANICAL: the kernel boundary is documented and the kernel's size is stated. |
| 4.5 | Soundness argument: a written argument (or machine-checked meta-theorem) that the calculus is sound with respect to the stated semantics. | NEAR-MECHANICAL: the artefact exists and references the semantics in 1.1. |
| 4.6 | Conservativity of definitions: definitional extensions are checked for freshness, well-foundedness and non-circularity, and rejected otherwise. | MECHANICAL: probe a circular and a non-fresh definition; both must be rejected. |
| 4.7 | A corpus of non-trivial formalised mathematics exists and re-checks from source. | MECHANICAL: run the full check; record the command, the corpus size and the result. |
| 4.8 | Axiomatic commitments (excluded middle, choice, impredicativity, extensionality) are explicit and their use is trackable per theorem. | MECHANICAL: query which axioms a given theorem depends on. |

Level 4 systems trade heavily against writability and against coverage of
informal-but-real mathematics; that trade is a design choice, not a defect. A
level-2 interchange format is not "behind" a level-4 prover; they are answering
different questions.

---

## 5. Level assignment procedure

1. Evaluate every criterion from 0.1 upward, in order, recording `PASS`, `FAIL`,
   `NOT_ASSESSED` with the evidence artefact for each.
2. Assign `level = max{ n : every criterion of levels 0..n is PASS }`.
3. Apply the criticality gate (§0): if any CRITICAL atom is `0` or `L(silent)`,
   cap at level 1 and name the atoms.
4. `NOT_ASSESSED` blocks progression exactly as `FAIL` does, but is reported
   distinctly. A level claimed on unassessed criteria is recorded as
   "level *n*, provisional (k criteria unassessed)".
5. Report, alongside the level: the **first failing criterion**, its evidence, and
   what would have to change to pass it. A level without a named blocking
   criterion is not a useful result.
6. Report the system's **claimed** level (from its own documentation) next to the
   assessed level. The gap between them, in either direction, is the finding.

## 6. Anti-gaming notes on the ladder itself

- **Threshold clustering.** The coverage thresholds (0.60/0.80) are gates, not
  scores; a system just above a threshold is not meaningfully better than one just
  below. Report the raw coverage next to the level always.
- **Criterion shopping.** The criteria are fixed before assessment. A criterion may
  not be reinterpreted after a system fails it; disputes are recorded as disputes,
  with the level reported under both readings.
- **Self-assessment.** Where a system's own documentation asserts a criterion is
  met, that assertion is not evidence. Only an executed check is evidence.
- **Level inflation by scope narrowing.** A system cannot reach level 2 by
  declaring 11 of the 13 domains out of scope; 2.1 requires all 13. A system that
  genuinely serves one domain should be assessed as level 1 and reported as such,
  which is not a criticism.
