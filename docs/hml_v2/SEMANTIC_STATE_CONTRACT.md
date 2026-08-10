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

## 4. Losslessness is a test

`export_transition` is the inverse of `import_transition`, asserted over all 30 fixtures.
An adapter that models the fields somebody thought of and drops the rest is the usual
failure, and it surfaces much later as a record that cannot be expressed. Unrecognised
`schema_version` is refused rather than optimistically parsed.

## 5. Acceptance — measured

30/30 fixtures match the frozen reference checker; 30/30 round-trip byte-for-byte.
Previously `CURRENT_HML_NOT_EXPRESSIBLE`: `FX-CAN-{LEGAL,ILLEGAL,UNKNOWN}`,
`FX-BRN-{LEGAL,ILLEGAL,UNKNOWN}` — all six now handled.

## 6. What this does NOT establish

Recorded because the fixtures are weaker than they look, and a later reader will otherwise
assume otherwise.

* **SF-R06 is not fully demonstrated.** It requires four candidate states; no fixture or
  benchmark case ever exercises `UNVERIFIED` or `REJECTED` — only `PROPOSED` and
  `VERIFIED`. Passing all 30 does not prove the lifecycle.
* **The two new ILLEGAL fixtures only test dangling evidence pointers.** They differ from
  their LEGAL twins solely in an `evidence_id` that names a missing record; the valid record
  is still present. The substantive rules — constraint subset, branch not CLOSED, branch
  conclusion mismatch — are exercised by *no* acceptance fixture. This implementation was
  built to the reference checker's source, not to fixture pass/fail.
* **Acceptance fixtures are not source-held-out** (`gold125_overlap: true` on some). Pass
  rates here are not evidence of generalisation. Only FINAL is held out.
* **The scope-discharge path is untested by any artifact.** `scope_effect.kind` is `NONE` in
  all 230 frozen records, so the discharge branch is dead relative to the corpus.

## 7. Deliberately deferred

The lossless HML renderer (SF-R15) — the brief sequences it after the semantic objects
stabilise, and they have existed for one build. Library extension (SF-R10/R14) beyond what
`libraries/` already provides. Existential branch modes, nested proof blocks, typed
close-and-advance vs close-and-collapse delimiters (MiniLang shows these matter; nothing in
the fixtures reaches them).
