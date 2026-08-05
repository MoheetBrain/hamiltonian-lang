# Constitutional integration — conflict register

HML-MARKOV-TRANSITION-002 §4. Every conflict between agents, or between an agent and a
previously frozen expectation, is recorded here with its resolution and its reversal cost.

The governing rule: **a failure caused by a deliberate contract change is a migration
event, not a regression.** Restoring a stale test to make the suite green would encode the
old contract as if it were still true. Equally, weakening a constitutional invariant to get
a green suite is forbidden.

---

## CONF-001 — `PValue` promoted from quarantined to supported

| | |
|---|---|
| **old assumption** | `PValue` is `KNOWN_FAILED` and quarantined. Phase F1 wrote `tests/freeze/test_quarantine.py::test_a_quarantined_type_name_is_not_admissible_in_type_position[PValue]` and `test_the_scalar_lattice_is_exactly_the_frozen_set` to pin it. |
| **new contract** | HML-CONSTITUTIONAL-CORE-001 Task 1C requires `PValue` in the HML source vocabulary, distinct from `Probability` and from posterior probability, with no implicit coercion either way. |
| **affected tests** | the two above, plus the scalar-lattice closure test |
| **chosen resolution** | **Migrate.** Update the quarantine expectation and the frozen scalar lattice; add `PValue` as `SUPPORTED_ENFORCED`. |
| **rejected alternative 1** | Restore the stale expectation — would re-quarantine a type the directive requires. |
| **rejected alternative 2** | Delete the quarantine tests — they are the mechanism that forced this decision to be explicit. Deleting them would remove the only thing that noticed. |
| **evidence** | `const pv : PValue = 0.05` -> ok. `def posterior_h0 : Probability := pv` -> `HML-T403`. `const p : Probability = 0.5; def observed_pvalue : PValue := p` -> `HML-T403`. Both directions rejected. |
| **reversal cost** | Low. Remove `PValue` from the scalar set and restore the two quarantine rows. The reversal is mechanical because the migration was recorded rather than applied silently. |

**Note on the mechanism working as designed.** Phase F1 wrote what it called
"known-failure pins that assert the open holes are *still* open, so a fix fails the suite
and forces re-classification rather than letting a stale `KNOWN_FAILED` persist." The first
real fix tripped exactly that pin. This is the intended behaviour of `frozen_subset.py`,
not a defect in it.

**`PosteriorProbability` was NOT added.** Its name appears in a quarantine test, but no
implemented construct requires it, and the directive forbids adding a type merely because a
test mentions the name. It remains unavailable in source.

### Migration record

| field | value |
|---|---|
| old state | `KNOWN_FAILED` / quarantined |
| new state | `SUPPORTED_ENFORCED` |
| evidence | parser, renderer, canonicalisation, type checking and adversarial tests all pass |
| reversal | remove from `FROZEN_SCALARS`; restore both quarantine rows; re-run `tests/freeze` |

---

## CONF-002 — Ownership of `improvement/__init__.py`

| | |
|---|---|
| **old assumption** | Each subagent owns a disjoint file set inside `src/hamiltonian_lang/improvement/`. |
| **new contract** | Both B and C needed the package to exist before either could import it. |
| **affected files** | `src/hamiltonian_lang/improvement/__init__.py` |
| **chosen resolution** | Accept C's version. Both were docstring-only with no imports, so the overwrite lost nothing. Verified by inspection, not assumed. |
| **rejected alternative** | Have the Lead pre-create the package — correct in hindsight; recorded so the next multi-agent package split does it that way. |
| **evidence** | B reported it created a docstring-only stub and that C replaced it with another docstring-only version; no imports either way; suite passes. |
| **reversal cost** | None. |

---

## CONF-003 — The canonical comparator is exact in one direction only

Raised by Subagent B as explicitly needing a Lead decision "before any H1/H2 number is
computed".

| | |
|---|---|
| **the issue** | `CanonicalComparatorVerifier` treats hash equality as sameness (sound) but treats hash inequality as *wrongness*. An equivalent-but-differently-shaped encoding lands in `SUPPORTED_AND_FAILED` and classifies `DISPROVED`. |
| **chosen resolution** | **Correct for ACQ0. Forbidden for H1/H2 without a different comparator.** |

The reasoning is that ACQ0 and H1/H2 ask different questions:

- **ACQ0** asks whether the model reproduced *the same canonical object*. Exact hash match
  **is** the definition of semantic preservation there. Being strict is the point, and a
  rephrasing that yields a different object genuinely failed the task.
- **H1/H2** ask whether the representation improved the *answer*. A mathematically
  equivalent encoding that hashes differently is not a wrong answer, and scoring it as
  `DISPROVED` would systematically bias those hypotheses downward — against the project's
  own thesis.

**Binding consequence:** no H1 or H2 number may be computed from
`CanonicalComparatorVerifier` alone. A separate equivalence comparator is a prerequisite
for M3 and is recorded as such in the hypothesis register. This costs nothing now because
H1 and H2 are UNTESTED.

| | |
|---|---|
| **reversal cost** | None yet — no H1/H2 number exists to invalidate. The cost rises sharply the moment one is computed. |

---

## CONF-004 — No episode containing `require` can reach `VERIFIED`

Measured by Subagent B: a well-formed candidate that exactly matches the reference
classifies `INCONCLUSIVE`, because the type checker collects an undischarged `constraint`
obligation and nothing discharges it.

| | |
|---|---|
| **chosen resolution** | **Accept as correct, and record the consequence loudly.** An undischarged obligation genuinely means the claim is not established. Auto-discharging constraints to obtain `VERIFIED` would make the verdict meaningless — precisely the "authoritative-looking output that is wrong" failure `CLAUDE.md` names as the worst in the codebase. |
| **consequence** | On this machine, `VERIFIED` is currently unreachable for any HML module containing a `require`. Since Lean cannot verify anything either (see CONF-005), **`VERIFIED` is effectively unreachable overall.** |
| **effect on ACQ0** | None. ACQ0's endpoints are parse rate and semantic preservation, neither of which needs `VERIFIED`. |
| **effect on H3** | Severe, and it must be resolved before M3. H3's primary endpoint is *kernel-verified completion rate*. If nothing can be verified, that endpoint is unmeasurable and H3 cannot be run as specified. |
| **reversal cost** | n/a — this is a recorded limitation, not a change. |

---

## CONF-005 — Lean is a sound gate with nothing able to pass through it

| | |
|---|---|
| **the issue** | The Lean backend closes every obligation with `sorry` **by design** (its own generated header says so). `sorry` is in `FORBIDDEN_TACTICS`, so `lean_verify.verify()` rejects the backend's own output textually, before Lean is invoked. Mathlib is also absent. |
| **chosen resolution** | Classify Lean `UNSUPPORTED`. Do **not** broaden Lean or Mathlib support during this directive. |
| **evidence** | B reproduced it as a test: render a real module, assert `"sorry" in emitted`, assert `verify()` returns `REJECTED_FORBIDDEN_TACTIC`. Independently reproduced by the Lead. |
| **required wording** | Lean must never be described as an available verification path for HML output. |
| **noted opportunity, out of scope** | Core Lean handles `Nat` fine — `(7:Nat) = 7` compiles while `(7:ℕ)` does not. The Mathlib dependency is partly a *notational* choice by the backend, so a Mathlib-free subset may be reachable by changing emission alone. Recorded so the option is not lost; not acted on, because this milestone freezes rather than extends. |
| **reversal cost** | n/a |

---

## CONF-006 — A hash chain cannot detect tail truncation

| | |
|---|---|
| **the issue** | A prefix of a valid chain is itself a valid chain, so deleting trailing events verifies clean. Reproduced by B as `test_truncation_is_unchecked_without_a_checkpoint`. |
| **chosen resolution** | Accept `checkpoint()`, which anchors length and tail hash in a sidecar, and keep the limitation stated in the module docstring rather than glossed. |
| **why it matters** | Truncation is the cheapest way to erase an inconvenient failure. A ledger that cannot detect it would satisfy the letter of "append-only" while failing its purpose. |
| **evidence** | Lead reproduced tamper detection independently: forging a payload **and** recomputing that line's own hash is still caught by the chain. |
| **reversal cost** | n/a |

---

## Open items for the Lead at M3, not resolvable now

1. **A different equivalence comparator is required before any H1/H2 number** (CONF-003).
2. **`VERIFIED` must become reachable before H3 can be run as specified** (CONF-004).
3. `VIOLATED_INVARIANT_BY_CODE` covers 8 of ~110 diagnostic codes; the rest record an
   explicit gap. Filling it requires reading the rule per code, not inferring it.
4. No compiler diagnostic carries a counterexample, so that field is an unconditional gap
   on every adapted diagnostic.
