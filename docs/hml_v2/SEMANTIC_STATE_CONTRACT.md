# The canonical semantic-state contract

**Status: normative.** Specifies `src/hamiltonian_lang/semantic_state/`.

Companion to `GOLD10_CORE_SEMANTICS_SPEC.md` (the reasoning core) and
`MATHEMATICAL_LIBRARY_CONTRACT.md` (domain mathematics). This one specifies the layer that
holds a *transition* rather than a *module*.

Research basis: the Semantic Firewall experiment in the corpus at commit
`80b1640495d6c4ad9acc32da0353ad0c9bf91201`, pinned HML `5688aba`. Requirements SF-R01…R15
in `experiments/semantic_firewall/requirements_handoff.json`; acceptance in
`experiments/semantic_firewall/acceptance/fixtures.json`.

---

## 1. Why a second object exists

HML's reasoning layer checks a **module**: a text, once. The corpus records a
**transition**: `state_before --action--> state_after`, with evidence. Those are different
objects, and the firewall experiment found exactly where the second had no home — six of
its thirty fixtures were `CURRENT_HML_NOT_EXPRESSIBLE`, all of them about **candidates**
and **branch/join**.

This package supplies the missing object. It is **not** new surface syntax. `docs/04` §6.14
makes canonical typed state primary and HML text one rendering of it, and the builder brief
forbids adding syntax merely to support import. Verified mechanically: `git diff` is empty
for `ast/`, `lexer/`, `parser/`, `backends/` and all of `reasoning/`.

## 2. The objects

`Claim` · `Candidate` · `Branch` · `Goal` · `Obligation` · `EvidenceRecord` · `Action` ·
`SemanticState` · `Transition`.

Two rules govern all of them.

**Status is computed, never asserted.** `CandidateStatus.VERIFIED` and
`BranchStatus.JOINED` are reachable only through the verifier — the same reason
`DerivationStatus.VERIFIED` has no surface syntax.

**`UNKNOWN` is a representable value.** Not an import error, not an absence. A record
saying "this status is not determined" is well-formed and must round-trip. It is what makes
the `UNRESOLVED` verdict reachable, and the PRM800K audit is explicit that unknown and
un-adjudicated must be values rather than gaps.

### Candidate lifecycle (SF-R06)

```
PROPOSED ──> UNVERIFIED ──> VERIFIED
    │             │
    └─────────────┴───────> REJECTED
```

**One generic object.** No `root_candidate`, no `geometry_candidate`. A candidate is "a
proposed object plus the constraints it must satisfy", and that shape does not vary by
subject; specialising it would put domain knowledge in the state model.

`constraint_ids` is load-bearing: promotion checks **every** original constraint. Checking a
subset verifies a different claim than the one made.

### Branch/join (SF-R08)

Coverage is **required**; disjointness is **not**. Disjunction elimination is sound for
overlapping cases, so demanding disjointness would reject valid reasoning — confirmed
against the MiniLang `CONSIDER∨` semantics, whose obligations record coverage only.

A join additionally requires: every named branch CLOSED, a valid partition certificate
covering them, and every branch's conclusion equal to the published claim. Branches that
merely agree are not evidence that they exhaust the cases.

## 3. The verifier

Three-valued: `VALID` · `INVALID` (with a named error class) · `UNRESOLVED`.

`UNRESOLVED` is **not** a soft `INVALID`. Each invariant family ships LEGAL / ILLEGAL /
UNKNOWN, and the UNKNOWN case must be neither accepted nor counted as a detected
corruption. So UNKNOWNs are collected **first** and short-circuit: an invariant cannot be
checked against a field whose value is "we do not know", and guessing there would produce a
confident answer with nothing behind it.

**Check order is load-bearing.** `error_class` is the first violation found, so the order —
dependency, scope, preconditions, obligations, candidates, branch/join, warrant, epistemic,
goal-discharge, type/domain — must match the reference checker or the error classes diverge.

**`EvidenceRecord.trusted` is provenance, not permission.** Nothing reads it as authority.
Acceptance requires the structural facts: the record exists, it supports the rule being
applied, its premises are declared, its status is VALID. The corrupted fixtures attack the
*reference* — pointing an action at evidence that is not there — and a checker that believed
the flag would accept every one of them.

### Scope is containment

The rule is **not** "the output scope is active". `global` is always active, so that reading
accepts the corrupted fixture, which promotes a `branch:b1` conclusion straight to `global`.
A conclusion may not be wider than the narrowest premise it rests on; leaving a frame
requires an explicit discharge whose evidence is checked like any other.

### The domain lattice is library data (SF-R14)

`domains.py` holds the corpus's domain names and their containment order as versioned,
justified entries. Not a table in the verifier: a checker that hardcodes subject-matter
knowledge needs a code change for every later domain, which is the failure SF-R14 names.

It is **not** `types.py::_SCALAR_PARENTS` and must not be merged with it. That lattice
orders HML's own scalar types; this one carries the neutral schema's vocabulary. Two
lattices, two purposes, no subtyping path between them.

There is deliberately **no warrant-rule registry**. The reference checker consults no such
table — `UNRELATED_RULE` fails because it differs from the attached record's
`supports_rule`, not because it is unrecognised — so a closed-world registry would reject
warrants the reference accepts. Warrants are already data on the action rather than core
operations, which is what SF-R10 actually asks for.

## 4. Losslessness is a test

`export_transition` is the inverse of `import_transition`, asserted over all 30 fixtures.
An adapter that models the fields somebody thought of and drops the rest is the usual
failure, and it surfaces much later as a record that cannot be expressed. Unrecognised
`schema_version` is refused rather than optimistically parsed.

The same property, one layer up: `parse_transition` is the inverse of `render_transition`
(SF-R15). The model dataclasses are `frozen=True`, so that comparison is structural
equality of the whole transition — a stricter bar than the AST round trip in
`tests/roundtrip/`, which compares canonical hashes and is permitted to lose spans. The
chained check is the load-bearing one: corpus JSON → state → view → state → corpus JSON.

`view.py` is HML-shaped where there is semantics and JSON-literal where there is not. The
free-form fields — `source`, `typing`, `warrant`, the six `*_effect` maps, the
precondition/obligation lists, an evidence `payload` — are open dictionaries the corpus may
extend at any time, and `neutral.py` preserves them verbatim precisely because this codebase
does not know what is in them. Inventing a surface for content with no semantics attached
would make every upstream extension silently unrepresentable. Values JSON cannot carry back
unchanged are **refused**, per SF-R15's "reject unsupported fields instead of commenting
them away".

The view is not a backend. `backends.base.Backend` exists to declare loss — its whole API is
`drop`/`approximate`/`weaken` over `Module.statements` — and a lossless renderer of an object
with no statements and no spans would have to lie about both.

## 5. Acceptance — measured

30/30 fixtures match the frozen reference checker; 30/30 round-trip byte-for-byte through
the neutral adapter; 30/30 round-trip through the HML view and back out to identical corpus
JSON. Previously `CURRENT_HML_NOT_EXPRESSIBLE`: `FX-CAN-{LEGAL,ILLEGAL,UNKNOWN}`,
`FX-BRN-{LEGAL,ILLEGAL,UNKNOWN}` — all six now handled.

`tests/semantic_state`: 266 tests. Frozen core diff empty for `ast/`, `lexer/`, `parser/`,
`backends/`, `reasoning/`.

## 5a. Two divergences from the reference checker, found by reading its source

Neither was detectable from the fixtures. Every fixture declares the domain the claim
already has, and every fixture's premise envelope already equals its dependency list, so the
acceptance set cannot distinguish either pair of behaviours. Both were found by reading
`reference_checker.py` and are now covered by a differential test that compares against the
frozen source directly rather than against examples.

| | was | reference | now |
|---|---|---|---|
| input domain | `claim.domain != required` | `_is_subtype` over `_DOMAIN_PARENTS` | `inhabits()` over the lattice |
| warrant premises | `premise_ids ⊆ dependencies` | `premise_ids == dependencies` | exact list equality |

The first was a **false INVALID**: a claim in `Natural` offered where `Integer` is required
was rejected here and accepted by the reference. The second was the dangerous direction —
evidence resting on fewer premises than the action declared was accepted, so a conclusion
could acquire ancestry its warrant never covered. SF-R09 binds the *exact* premise list.

One divergence is **kept and recorded**: this verifier checks `output_domain`, which the
reference never reads. Deleting a sound check to agree with a gap would be the wrong repair.
It is strictly stricter, so it cannot let a corrupted transition through — only question a
well-formed one.

## 6. What this does NOT establish

Recorded because the fixtures are weaker than they look, and a later reader will otherwise
assume otherwise.

* **SF-R06 is still not demonstrated by the corpus.** It requires four candidate states; no
  fixture or benchmark case ever exercises `UNVERIFIED` or `REJECTED`. The lifecycle now has
  its own tests in `test_unfixtured_rules.py`, but those are synthetic and written by the
  same author as the code — they pin behaviour, they are not external acceptance.
* **The two new ILLEGAL fixtures only test dangling evidence pointers.** They differ from
  their LEGAL twins solely in an `evidence_id` that names a missing record. The substantive
  rules — constraint subset, branch not CLOSED, branch conclusion mismatch — are exercised
  by *no* acceptance fixture. They are now covered by synthetic tests, and each of those was
  mutation-checked: disabling the rule in `verify.py` makes the corresponding test fail.
  That establishes the tests bite; it does not make them external criteria.
* **The domain lattice has no fixture support at all.** No fixture exercises a proper
  subtype relation. The entries are justified by the reference checker's *source*, which the
  implementation is required to match — a weaker warrant than a passing fixture, and
  recorded as such.
* **Acceptance fixtures are not source-held-out** (`gold125_overlap: true` on some). Pass
  rates here are not evidence of generalisation. Only FINAL is held out.
* **The scope-discharge path is untested by any artifact.** `scope_effect.kind` is `NONE` in
  all 230 frozen records. It now has synthetic tests, including the case where a valid
  discharge *licenses* the escape — without which the rule could be deleted outright and
  every fixture would still pass.
* **Nothing here was measured against a model.** No claim about representation quality,
  reasoning accuracy or comparative advantage follows from any of it.

## 7. Deliberately deferred

Existential branch modes, nested proof blocks, typed close-and-advance vs
close-and-collapse delimiters — MiniLang shows these matter; nothing in the fixtures reaches
them. Broad theorem ingestion (SF-R10's theorem half): no fixture names a theorem id,
statement or substitution, so building it would add machinery no acceptance case could
check. Replay in the `derivative_trace_v1` sense for the warrant path, for the same reason —
the reference checker re-derives nothing. `source_span_hash` verification: present on 30
evidence records, read by neither checker, and there is no oracle to verify it against.
