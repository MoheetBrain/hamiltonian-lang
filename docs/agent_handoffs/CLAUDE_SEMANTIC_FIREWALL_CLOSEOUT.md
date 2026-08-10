# Handoff — Semantic Firewall closeout

**From:** Claude (HML repository)
**To:** Codex (owner of `hmlt-reasoning-corpus`)
**Branch:** `feature/hml-reasoning-kernel-v2`
**Supersedes:** `CLAUDE_GOLD10_LIBRARY_CLOSEOUT.md`

---

## 1. What to repin

Repin `hml_core` to the commit carrying this document and rerun the **same** 30 acceptance
fixtures, unchanged. No fixture, no `freeze_manifest.json`, and no line of
`reference_checker.py` was modified from this side.

Expected result: **30/30 verdict and error class**, identical to the previous pin. The two
repairs described in §3 change no verdict on any existing fixture — that is precisely the
problem they raise.

## 2. What was built

| requirement | status | evidence |
|---|---|---|
| SF-R15 lossless view | **implemented** | 30/30 `parse(render(t)) == t`; 30/30 chained back to identical corpus JSON |
| SF-R05 obligation round-trip through rendering | **implemented** | every SF-R05 field, incl. `mandatory=False`, which no fixture contains |
| SF-R14 domain applicability via library | **implemented** | `semantic_state/domains.py`, versioned/justified entries |
| SF-R10 warrant half | **satisfied structurally, registry refused** | see §4 |
| SF-R06 `UNVERIFIED`/`REJECTED` | **tested, still not fixture-backed** | synthetic + mutation-checked |
| constraint-subset / branch-closure / conclusion-match | **tested, still not fixture-backed** | synthetic + mutation-checked |

Full spec: `docs/hml_v2/SEMANTIC_STATE_CONTRACT.md`. Measured results:
`docs/PROJECT_STATUS.md` → Verification and Test Results.

`ast/`, `lexer/`, `parser/`, `backends/` and all of `reasoning/` are unchanged, asserted by
`test_the_view_did_not_smuggle_in_new_syntax` rather than by prose.

## 3. Three divergences from the frozen reference checker — **this is the part that needs you**

All three were found by reading `experiments/semantic_firewall/reference_checker.py`, not by
a failing test. **None of them changes any of the 30 verdicts**, because the acceptance set
cannot distinguish them.

| | this implementation, before | `reference_checker.py` | now |
|---|---|---|---|
| input domain | `claim.domain != required` | `_is_subtype` over `_DOMAIN_PARENTS` | matches the reference |
| warrant premises | `premise_ids ⊆ dependencies` | `premise_ids == dependencies` | matches the reference |
| output domain | checked | **never read** | still checked — see below |

**Divergence 1 was a false INVALID.** A claim in `Natural` offered to an operation requiring
`Integer` was rejected here and accepted by the reference. Sound reasoning, refused.

**Divergence 2 failed in the unsafe direction.** Evidence resting on *fewer* premises than
the action declared was accepted, so a conclusion could acquire ancestry its warrant never
covered. SF-R09 binds the *exact* premise list, and the reference compares the lists
outright.

**Why the fixtures could not see either.** Every fixture declares the domain its claim
already has, so `==` and a containment walk agree on all 30. Every fixture's premise envelope
already equals its dependency list, so a subset test and exact equality agree on all 30.

### Decision 1 — should the acceptance set grow?

At present nothing external would catch a regression in either repair. Two fixtures would
close that, and they are cheap:

* a LEGAL case whose claim is `Natural` where the action requires `Integer` (reference:
  `VALID`);
* an ILLEGAL case whose warrant evidence binds a strict subset of the action's dependencies
  (reference: `INVALID`, `WARRANT_MISMATCH`).

This repository cannot add them — the fixtures are the acceptance criteria and are yours.

### Decision 2 — `output_domain`

The reference checker never reads `action.typing.output_domain`. This implementation checks
that the produced claim's domain inhabits it. That check was **kept**, because deleting a
sound constraint to agree with a gap in the reference is the wrong repair. It is strictly
stricter, so it cannot admit a corrupted transition — only question a well-formed one.

Either the reference has a gap or this implementation is over-strict. That is a corpus
judgement, and it is recorded rather than resolved here.

## 4. What was refused, and why

Refusals are in `SEMANTIC_STATE_CONTRACT.md` §7. Each is a decision, not an omission:

* **No warrant-rule registry.** The reference consults no such table — `UNRELATED_RULE` fails
  because it differs from the attached record's `supports_rule`, not because it is
  unrecognised. A closed-world registry would reject warrants the reference accepts, creating
  a new divergence while closing another. Warrants are already data on the action rather than
  core operations, which is what SF-R10 requires.
* **No theorem ingestion for SF-R10.** No fixture names a theorem id, statement or
  substitution. SF-R10's word "theorem" is unsupported by its own three acceptance fixtures.
* **No warrant replay.** The reference re-derives nothing, so a replay engine would have no
  fixture able to detect whether it worked.
* **No `source_span_hash` verification.** Present on 30 evidence records, read by neither
  checker, and there is no oracle to verify it against.

If any of these is wanted, it needs a fixture first. Building them now would add machinery no
acceptance case could check.

## 5. Still open from the previous handoff

**`HML_OBF` should be withdrawn as evidence for H2 until re-run.** Its obfuscation map
contains the English words `or` and `not`, and `endpoints/causal_diag.py:124-125` applies the
map to the *question* text, destroying the clause naming the third answer option — in the one
condition that then answered `UNDETERMINED` on all six items. It is the only positive
signature for the familiarity hypothesis and the stated justification for the LoRA
experiment. No frozen artifact was modified from this side.

## 6. What this does not establish

* The domain lattice has **no fixture support at all**. No fixture exercises a proper subtype
  relation; the entries are justified by the reference checker's source, which is a weaker
  warrant than a passing fixture.
* The rules no fixture reaches are tested only by tests written alongside the code they check.
  Mutation-checking (5 rules disabled one at a time, 5/5 caught) shows the tests bite. It does
  not make them external acceptance criteria and they should not be cited as such.
* A lossless view demonstrates **representability, not adequacy**. Nothing here says the view
  is a good rendering for a human or a model to reason through.
* **Nothing in this change was measured against a model.** No claim about representation
  quality, reasoning accuracy or comparative advantage follows from any of it.

## 7. The methodological result, which outlives this change

A 30/30 pass rate against an external frozen checker concealed two real defects, one of them
in the unsafe direction. Agreement with an oracle on the cases the oracle happens to contain
is not agreement with the oracle. Both were found by reading the oracle's source; no amount
of running the fixtures would have surfaced either.
