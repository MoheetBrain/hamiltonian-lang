# Project Status

Snapshot date: 2026-08-04. Maintained per the commit continuity protocol.

## Project Objective

Hamiltonian Lang is a **cross-domain, typed mathematical intermediate representation and
verifier-guided reasoning protocol whose syntax, semantic organisation and concept system
are treated as experimentally optimisable variables**, tested under matched conditions
against natural language, conventional notation and existing formal systems.

Specified as eight components in `GOAL.md`: Σ surface · 𝒢 front end · 𝒮 semantic core ·
ℛ reasoning state · ℰ epistemics · 𝒞 concept registry · ℬ backends · **𝒪 empirical language
optimisation — the novelty candidate**.

**The broad novelty claim is withdrawn.** Minilang/AoA (arXiv 2607.16372, 17 July 2026,
retrieved and verified) already demonstrated an LLM-oriented proof language, a JSON AST
interface, demonstration-based teaching, prover feedback and reduced token cost. Hamiltonian
may not claim novelty from any of those. What remains is the **conjunction** of eight
properties in `GOAL.md` §1, of which item 8 — optimising the representation itself under
matched controls — is the defensible candidate.

The project succeeds only if a reproducible advantage is demonstrated on at least one
important mathematical task. **A pilot measurement has now been taken and found no
advantage — see `docs/evaluation/HML_EVAL_001_PILOT_REPORT.md`. The decision is REDESIGN
AND RETEST.** The pilot was saturated at 93% accuracy across all seven arms and had almost
no power, so it is not evidence that no advantage exists.

## Current Stage

**D-050 IS CLOSED (D-051). Evidence status is no longer authority at runtime.**

`TrustMode.RUNTIME` ignores a record's `status` entirely and requires an `Attestation`
carrying a `CheckedEvidence` that only `reasoning.certificates.check` can mint — no second
registry was added; `semantic_state/trust.py` is a seam into the existing machinery.
`OFFLINE_REPLAY` stays the default so the frozen corpus still replays: **30/30 unchanged.**

17 adversarial tests. A self-asserted `"status": "VALID"` is refused at runtime; `trusted:
true` buys nothing; certificates for another claim, other premises, another rule or another
evidence id are all refused; `CheckedEvidence` cannot be constructed directly. The suite
found a real hole in the first implementation — the candidate site bound only the rule, so a
certificate for a different proposition was accepted.

**Phase VI is currently not runnable.** No training stack exists on this machine (`torch`,
`transformers`, `peft`, `trl`, `mlx_lm` all absent). Ollama is present but is inference-only
and cannot do LoRA adaptation. The matched Gemma experiment needs an environment decision.

---

**AN INDEPENDENT AUDIT OF `7c9137a` FOUND SIX DEFECTS — FIVE ACCEPTED TRANSITIONS THAT
SHOULD HAVE BEEN REFUSED, PLUS ONE DETECTION BYPASS. All six are repaired.**

> **Correction (2026-08-10).** This section, and the title of commit `8bcd9a5`, previously
> said "six accepted transitions" and "the sixth is a classified blocker". Both are wrong on
> the count. **Five** probes returned VALID; the sixth — appending one unrelated
> `status: UNKNOWN` claim — returned UNRESOLVED across 10/10 ILLEGAL fixtures, which is a
> *suppression of detection*, not an acceptance. All six were repaired at `8bcd9a5`. The
> "classified blocker" is D-050, a separate finding that was never one of the six, and it is
> now closed by D-051. Caught by the third cognition-ledger audit; the pushed commit title
> cannot be rewritten, so the correction is recorded here.

Every finding reproduced against pristine production code before repair. All six were
**VALID** at `7c9137a`:

| probe | was |
|---|---|
| a claim asserting `0 = 1`, VERIFIED, materialising with no evidence, warrant or epistemic effect | VALID |
| an existing premise rewritten `ASSUMED -> VERIFIED`, proposition changed | VALID |
| a candidate walked `PROPOSED -> VERIFIED` with `candidate_effect: NONE`, zero constraints checked | VALID |
| the same from the terminal `REJECTED` | VALID |
| a mandatory OPEN obligation deleted outright | VALID |
| one unrelated `status: UNKNOWN` claim appended | **flipped 10/10 ILLEGAL fixtures to UNRESOLVED** |

**One root cause (D-049).** There was no frame condition. The ten invariants examine what the
action *declares*; none examined whether `state_after` is what applying that declaration
would produce. Every other rule was therefore optional — a producer that declined to declare
an effect was not checked, because the checks key on the declaration. The frozen reference
has carried this all along as `_exact_state_change`; it was not ported. **No fixture could
have revealed it:** all thirty are well-formed records whose delta already matches their
action.

Repaired: frame condition over claims, candidates, branches and obligations (the reference
frames claims only); unknowns dependency-scoped. Measured after repair: all six probes
INVALID or ineffective, UNKNOWN suppression **0/10** against 10/10 before, **30/30 acceptance
fixtures unchanged**.

**Not repaired — D-050, the trust boundary. BLOCKER before any model-authored input.**
`EvidenceRecord.status` is read from the imported record and is never *produced* by anything
in `src/`. Acceptance turns on `record.status == "VALID"`; the sole writer is
`neutral.py:307`, `payload.get("status", "UNKNOWN")`. There is no attestation, checker
identity, checker version or context hash, and `semantic_state` imports nothing from
`reasoning/certificates/`, where the real trust machinery lives. `trusted` **is**
provenance-only — that claim survived audit. `status` is the live field and the same
untrusted producer sets it. Bounded today only because `semantic_state` is imported by
nothing outside `tests/`.

**A correction to this document and to the contract.** `SEMANTIC_STATE_CONTRACT.md` §5a said
the retained `output_domain` divergence made this verifier "strictly stricter, so it cannot
let a corrupted transition through". True of `output_domain`; **false as a general claim**. On
the behaviours above production was strictly *weaker* than the reference it is specified to
match. Corrected in place rather than deleted.

**Also this session.** D-048: an absent domain annotation is unavailable evidence
(UNRESOLVED per SF-R13), not a violation — production was rejecting transitions for *lacking*
an annotation the format cannot losslessly represent. D-049 and D-050 as above. Decision-ID
referential integrity is now enforced by `tests/freeze/test_decision_ids.py` rather than
asserted in prose.

---

### Previously

**SEMANTIC FIREWALL BUILD COMPLETE — every requirement in the builder handoff is now either
implemented and measured, or refused in writing with the reason.**

The lossless HML view (SF-R15) exists, the domain lattice (SF-R14) is library data, the
rules no fixture reaches have their own mutation-checked tests, and **two latent divergences
from the frozen reference checker were found by reading its source and closed.**

* **Lossless view (SF-R15)** — `parse_transition(render_transition(t)) == t` over all 30
  fixtures, on `frozen=True` dataclasses, so that is structural equality of the whole
  transition rather than a hash. Chained: corpus JSON → state → view → state → corpus JSON,
  byte-identical. The view is HML-shaped where there is semantics and JSON-literal where the
  record is opaque; values it cannot carry back are **refused**, not approximated.
* **Domain lattice (SF-R14)** — `semantic_state/domains.py`, versioned and justified
  entries rather than a table inside the verifier. Not merged with `types.py`; two lattices,
  two purposes.
* **Divergence 1, closed** — input domains were compared with `!=` while the reference walks
  a parent chain. A claim in `Natural` offered where `Integer` was required was **rejected
  here and accepted by the reference**: a false INVALID on sound reasoning.
* **Divergence 2, closed** — the warrant premise envelope was a subset test; the reference
  compares the lists outright, and SF-R09 binds the *exact* premise list. The old reading
  failed in the dangerous direction: evidence resting on fewer premises than the action
  declared was accepted, so a conclusion could acquire ancestry its warrant never covered.
* **Divergence 3, kept and recorded** — this verifier checks `output_domain`, which the
  reference never reads. Deleting a sound check to agree with a gap would be the wrong
  repair. Strictly stricter, so it cannot admit a corrupted transition.

Neither closed divergence was detectable from the fixtures: every fixture declares the
domain the claim already has, and every premise envelope already equals its dependency list.
A differential test now compares against the frozen source directly, over the whole cross
product of domain names, rather than against examples somebody thought of.

**Refused in writing, with reasons** (`SEMANTIC_STATE_CONTRACT.md` §7): no warrant-rule
registry (a closed-world table would reject warrants the reference accepts); no theorem
ingestion for SF-R10 (no fixture names a theorem); no warrant replay (the reference
re-derives nothing); no `source_span_hash` verification (no oracle to verify against).

**Still no syntax.** `git diff` remains empty for `ast/`, `lexer/`, `parser/`, `backends/`
and all of `reasoning/`, asserted by a test rather than by prose.

---

**CANONICAL SEMANTIC STATE EXISTS — the Semantic Firewall's six inexpressible fixtures are
closed, and the trusted core did not change to close them.**

`src/hamiltonian_lang/semantic_state/` adds the object HML did not have: a *transition*
(`state_before --action--> state_after` plus evidence), as opposed to a *module*. The
Semantic Firewall experiment (corpus `80b1640`, pinned HML `5688aba`) recorded 6 of its 30
acceptance fixtures as `CURRENT_HML_NOT_EXPRESSIBLE`, all of them candidate-lifecycle
(`FX-CAN-*`) and branch/join (`FX-BRN-*`).

Measured: **30/30 fixtures match the frozen reference checker; 30/30 round-trip
byte-for-byte.** No fixture was modified.

* **Candidate lifecycle (SF-R06/R07)** — one generic object, no per-domain variants.
  Promotion is verifier-owned and checks *every* original constraint.
* **Certified branch/join (SF-R08)** — coverage required, disjointness **not** (disjunction
  elimination is sound for overlapping cases). Branches that merely agree are not evidence
  that they exhaust the cases.
* **Neutral adapter (SF-R03)** — versioned, and lossless *as a test* rather than a claim.
* **Fail-closed three-valued verdict (SF-R04/R13)** — `UNRESOLVED` is not a soft `INVALID`;
  UNKNOWNs are collected first and short-circuit.

**No syntax was added.** `git diff` is empty for `ast/`, `lexer/`, `parser/`, `backends/`
and all of `reasoning/`. The canonical object is the typed state; HML text remains one
rendering of it (`docs/04` §6.14).

**Four bugs found by running rather than reasoning**, all now fixed: obligations use
`status`/`mandatory` not `state`; discharges are `{id, evidence_id}` records; `UNKNOWN` must
be a *representable value*, not an import error; and the scope rule is **containment**, not
"output scope is active" — `global` is always active, so the weaker reading accepts the
corrupted fixture.

**What this does NOT establish** (see `docs/hml_v2/SEMANTIC_STATE_CONTRACT.md` §6): SF-R06
is not fully demonstrated — no fixture exercises `UNVERIFIED` or `REJECTED`. The two new
ILLEGAL fixtures test only dangling evidence pointers, so the substantive rules are
exercised by no fixture; this was built to the reference checker's source. Acceptance
fixtures are not source-held-out, so pass rates are not evidence of generalisation.

---

**GOLD-10 LIBRARY CLOSEOUT COMPLETE — the three remaining library capabilities exist, and
the trusted kernel did not change to get them.**

Codex's rerun at `5688aba` gave 11/23 native · 8/23 certificate · 4/23 library-blocked ·
CoreGapRate 0/23. The four blocked transitions reduced to **three upstream library
capabilities**, now built as `src/hamiltonian_lang/libraries/`:

* **algebra** — five typed identities, all `LIBRARY_AXIOM`. `add_zero` is G07's body; the
  other four are exactly what the calculus normalisation needed and nothing more.
* **probability** — `conditional_product`, `DEFINITIONAL`, with `P(A) > 0` as an ordinary
  obligation. Built against HML's *actual* conventions, verified against the compiler:
  `probability(...)` needs an **Event** (from `rv` declarations), not a `Bool`;
  `probability(B | A)` is `event=B, given=[A]`; `joint(...)` is a distribution, not
  intersection.
* **calculus** — a **replay**, not a table. Six primitive rules; the checker
  differentiates the expression itself and compares, so a CAS proposal is a claim rather
  than evidence. The quotient rule's `v != 0` flows through the existing obligation system.

**The architectural claim, and it is checked mechanically:** `git diff` is **empty** for
`reasoning/kernel.py`, `binders.py`, `adjudication.py`, `side_conditions.py`,
`refinement.py`, `evidence.py`, `partiality.py`, `ast/`, `lexer/`, `parser/` and
`backends/`. No inference rule, no keyword, no statement form, no AST node was added. A
domain fact composes with the *unchanged* `forall_intro` to close G07. **CoreGapRate = 0
survives the test this mission was designed to be.**

**Honesty surface:** a library is shipped Python, so what it *assumes* is enumerable —
`libraries.axioms()` prints the complete list, the registry refuses an assumed theorem with
no written justification, and a certificate proves "this instantiation, correctly typed,
with side conditions discharged", never the axiom itself.

**One new core-adjacent gap found and reported, not silently patched:**
`RefinementEnv.entails` cannot discharge an obligation whose subject is not a declared
variable, even when Γ asserts it verbatim. Worked around locally by exact canonical
membership; the proper widening belongs to the core track.

Conformance **PASS** 8/8. `pytest`: **6981 passed, 0 failed** (65 new library tests).
Record: `docs/hml_v2/MATHEMATICAL_LIBRARY_CONTRACT.md`.

---

**GOLD-10 CORE REPAIR COMPLETE — the two generic core-semantic gaps are closed and a
checked-certificate boundary exists. Zero model calls, zero training, deterministic
engineering throughout.**

A forensic Gold-10 triage on the separate corpus track (Codex, corpus `467a486`, pinned HML
`164d1946`) found the original 13.04% CoreGapRate did not survive review: only **2/23
transitions** were genuine generic core-semantic gaps. `git diff --name-only
164d1946..22b4bb7 -- src/` is **empty**, so that triage inspected exactly this core and
nothing needed re-deriving. Three things were built, and nothing else:

1. **The checked-certificate boundary** (`reasoning/certificates/`) — one gate through
   which non-kernel capability may become evidence, with a **static** trusted registry.
   Source cannot define, override or extend a checker. Three checkers ship, each wrapping
   capability that already existed in the tree: `closed_eval_v1`, `definition_unfold_v1`,
   `propositional_underdetermination_v1`. Fail-closed on unknown checker, wrong judgement,
   hash mismatch, malformed payload, unsupported fragment, and **any exception**.
2. **GAP-0003, certified underdetermination** — a four-valued `EntailmentVerdict`
   (`ENTAILED | REFUTED | UNDERDETERMINED | UNKNOWN`) is the semantic source of truth and
   `GoalStatus.UNDERDETERMINED` is its projection. Certified by two models of Γ that
   disagree on the target, each independently re-evaluated here. **Nothing converts
   `UNKNOWN` into `UNDERDETERMINED`.**
3. **GAP-0004, the quantifier core** — `forall_intro` / `forall_elim` with a real
   eigenvariable condition, capture-avoiding instantiation, and locally-nameless binder
   re-depthing verified against the resolver's own parse.

**Two findings recorded rather than engineered around.** (a) `equivalence/symbolic.py` is
**not** registered as a trusted checker: its verdicts rest on raw SymPy flags
(`simplify(a-b) == 0`, `satisfiable(...)`) with no independent HML replay, so it is an
untrusted oracle and may not certify a derivation. (b) Consequently Gold-10 **G07's body
`n + 0 = n` remains library-level**; the quantifier core is therefore tested on
generically-established bodies, never on a hard-coded arithmetic identity.

Conformance: **PASS** on all eight stages. `pytest`: **6765 passed, 0 failed**, 80 of them
new. Record: `DECISIONS.md` D-047, `docs/hml_v2/GOLD10_CORE_SEMANTICS_SPEC.md`.

**Handed off. `5688aba` is the SHA for Codex to pin** — it carries every source change, and
anything after it on this branch is documentation only (`git diff --stat 5688aba..HEAD --
src/` is empty). `docs/agent_handoffs/CLAUDE_GOLD10_CORE_REPAIR.md` states the per-gap
expected reclassification as predictions to be checked, and leads with the two findings the
corpus owner will not like — the SymPy trust classification and G07's body remaining open —
rather than burying them. Ownership of the next step is Codex's; Gold-10 was not rerun here
and the corpus was not touched.

---

**THE REPRESENTATION ARENA EXISTS AND IS GREEN — `arena-1.0.0`, zero model calls.**
`evaluation/arena/` renders one neutral semantic world in three provably
information-matched notations — structured English (SE), a generic semantic AST (the
required control), and real HML — and scores answers with deterministic oracles. Parity is
**proved per world** by round trip, `canonical_world(decode_X(render_X(w))) ==
canonical_world(w)`: measured **1800 round trips over 600 worlds, 0 failures**. The
pre-flight gate passes all eight checks (306 items, 69 minimal-contrast pairs) and 100 arena
tests pass. Design record: `docs/evaluation/ARENA_DESIGN.md`.

The handoff's plan to bolt a rendering layer onto `difficulty_lab/families.py` was **not
executable**: that generator builds its English inline and discards the structure, so
nothing survives to render a second way. The arena rebuilds the worlds structure-first;
`difficulty-lab-1.0.0` is untouched and byte-identical.

**ENDPOINT B2 RESULT — AST_V2 4/8 > HML 3/8 > SE 1/8 pairs (items 12/16, 10/16, 8/16).**
On the mechanism HML was *designed* for, structure clearly beats prose — SE scored exactly
chance (8/16) with perfectly symmetric errors, i.e. coin-flipping — but **a plain generic
S-expression beat HML**. AST_V2 never lost to SE on a single item (Δ̂ +0.250) and edged HML
(Δ̂ +0.125). The length explanation is unavailable: AST_V2 is the *shortest* arm (243 vs SE
280, HML 346). Verdict **`HML_STRUCTURE_ONLY_SIGNAL`** — structure does the work, HML's
specific ontology does not. 48 calls, 0 invalid, 0 truncations. Descriptive at N=8.

**GENERIC_AST_V2 BUILT; ENDPOINT B2 (QUANTIFIER SCOPE) FROZEN.** A compact generic
S-expression control — `forall(x, D, exists(y, D, R(x, y)))` — with nesting carried by
parenthesis depth and **no HML machinery** (asserted by test). AST-v1 preserved and excluded:
the binder diagnostic showed it cannot read nesting. The length confound is *reversed* —
AST_V2 190.9 mean tokens vs SE 229.2 and HML 295.4 — so an HML win over it cannot be a
terseness effect. 16 audit checks pass; parity 150 worlds / 0 failures across four arms.
Frozen at 8 pairs × 3 arms = 48 scientific calls (+6 excluded smoke).

**CAUSAL SCOUT: NO CONDITION RESCUES HML. CASE D — frozen zero-shot branch closed.**
SE 5/6 · HML_BASIC 4/6 · HML_EPI 3/6 · HML_VERIFY 3/6 · HML_OBF 2/6 (30 calls, 0 truncations).
Three sub-findings: (1) ~~`HML_OBF` answered UNDETERMINED on all six items — a degenerate
constant, so obfuscation stopped the model engaging~~ — **WITHDRAWN 2026-08-10, see the box
below**;
(2) `HML_VERIFY` failed a two-bit lookup — handed *both* proof signals false, it still
answered TRUE, so deterministic feedback did **not** repair unsupported commitment;
(3) `HML_EPI` made over-commitment worse (UNDET→definite 2/2 vs 1/2 baseline). H3 and H4
unsupported. **Four measurements now, none showing frozen zero-shot HML helping.**

> **`HML_OBF` is withdrawn as causal evidence** — `INVALID_AS_CAUSAL_EVIDENCE` /
> `WITHDRAWN_PENDING_CLEAN_RERUN`. Record:
> `evaluation/arena/results/HML_OBF_WITHDRAWAL.md`.
>
> The obfuscation map substitutes the ordinary English words `or` and `not`, and
> `causal_diag.py:121-125` applies it to the **question text**. Re-derived from the frozen
> builder, the question reached the model as *"Is P6 necessarily true, necessarily false,
> `zeta8` is it `zeta9` determined by these assumptions?"* — the clause naming the third
> answer option destroyed, in the one arm that then answered UNDETERMINED on 6/6.
>
> Withdrawn: `HML_OBF` as positive evidence for H2, and as the justification for the LoRA
> adaptation experiment. This paragraph previously ended "H2 has the only positive
> signature, arguing for matched adaptation" — that signature **was** `HML_OBF`. **H2 /
> familiarity is now UNRESOLVED, not refuted**: withdrawing evidence for a hypothesis is not
> evidence against it. The other four arms and the CASE D verdict are unaffected. Nothing
> was deleted or re-run; the frozen manifest gained one additive `WITHDRAWN` key.

**ERROR-TOPOLOGY BRANCH CLOSED OFFLINE (0 calls).** The motivating signal is compatible
with chance: HML made ~5 errors per family, and P(0 of a subtype | 5 errors) = (2/3)^5 =
0.13. Error opportunity is also confounded with family — polarity errors exist only on logic
items. A power simulation showed direction alone is a coin flip under the null. **Causal
diagnosis scout frozen instead**: 5 matched conditions (SE, HML_BASIC, HML_EPI, HML_OBF,
HML_VERIFY), 6 items, 30 calls, band 800 000+.

**ENDPOINT A RESULT: the N=12 signal did NOT replicate. CASE B — advantage not
demonstrated.** Micro-pilot (12 items) gave SE 3/12 vs HML 9/12, Δ̂ = +0.500. The
independent 18-item expansion gave **11/18 in both arms, Δ̂ = 0.000**. Pooled 30 items:
SE 14/30, HML 20/30, Δ̂ = +0.200 — carried entirely by the first half. SE's micro-pilot
3/12 was exactly chance; on fresh items the same renderer scored 11/18, confirming that was
small-sample variance. 68 calls spent, 0 invalid, 0 truncations. **No escalation, no agent
build, no verifier loop justified.** One qualitative difference survives as a *hypothesis*:
HML's errors fell entirely into precondition/no-progress roles — zero invalid-arithmetic and
zero logic-polarity errors, against five for SE.

**ENDPOINT A (next-action) INSTRUMENT IS FROZEN — 24-check adversarial audit passed, zero
model calls spent.** Built by reusing the existing oracle-verified `next_action` generator;
new seed band `ENDPOINT_A` (700 000+); arms SE and HML only. A real defect was found and
fixed before freezing: answer positions were A2/B4/C1/D5, now 3/3/3/3. Surface-heuristic
tests (longest/shortest option, numeric magnitude, prompt length, just-established-variable)
all fail to beat chance. Frozen in `ENDPOINT_A_MANIFEST.json` with correct indices and
per-arm prompt hashes.

**THE FIRST HML-vs-SE REASONING RESULT EXISTS. IT IS NEGATIVE FOR HML.**

Pilot B1 (12 `IMPLICATION_DIRECTION` minimal-contrast pairs, 72 calls, `gemma3:4b`, temp 0,
0 truncations, 0 invalid):

| arm | pairs BOTH-CORRECT | items | mean prompt tokens |
|---|---|---|---|
| **SE** | **5/12 = 0.417** | 15/24 = 0.625 | 347 |
| **HML** | **1/12 = 0.083** | 10/24 = 0.417 | 285 |
| **AST** | **0/12 = 0.000** | 6/24 = 0.250 | 505 |

Ordering **SE > HML > AST**. Paired discordances all agree: HML vs SE Δ̂ = −0.208, AST vs SE
Δ̂ = −0.375, HML vs AST Δ̂ = +0.167. Per the pre-declared table, SE > HML ⇒
**`HML_REPRESENTATION_HARM_SIGNAL`** — on this endpoint, at this difficulty, with this
model, formalisation cost dominates.

**Not explainable away, and the obvious escapes are closed:** HML had the *shortest* prompts
and still lost to SE, so this is not a length penalty. HML scored 5/6 on acquisition and 8/8
on the binder diagnostic, so it is not a readability failure. Every error in every arm was a
wrong semantic conclusion — zero format failures, zero truncations. The dominant error is
collapsing `UNDETERMINED` into a definite verdict (HML 10 of its 14 errors).

**Equally, this is not a refutation.** N=12 pairs, one semantic mechanism, one level, one
4.3B model; no significance is claimed or computable. Quantifier scope — the mechanism HML
was designed for — is endpoint B2 and remains unrun, deliberately excluded because the AST
control cannot read binder nesting.

**The first SE-only developmental screen is INVALID and no model has been selected.**
`gemma4:12b` (11.9B, Q4_K_M, digest `4eb23ef187e2c546…`) was pulled as the first of at most
three candidates — the 31B is excluded because it is known to saturate. The screen ran 24
structured-English calls and failed twice: a misplaced module-entry guard crashed the runner
after every call had completed, discarding all records (~36 min of compute, log preserved at
`evaluation/arena/results/DEV_gemma4-12b_ATTEMPT1_LOST.console.txt`); and **12 of 24 responses were
truncated** at `max_tokens=4096`, because `gemma4:12b` is a thinking model whose finished
responses averaged 2395 completion tokens. Ten of twelve pairs were dropped whole, so the
model cannot be placed in the 30–70% target band. Both faults were mine, not the model's.

The runner is repaired — records are now written incrementally, and
`tests/arena/test_runner_preflight.py` drives CLI → calls → JSONL → summary → reload with a
fake client before any model is touched.

**A DEVELOPMENTAL ORGANISM IS FROZEN: `gemma3:4b` at 3/6 pairs.** The SE-only micro-screen
was run down a fixed ladder, one frozen 6-pair / 12-call set (offset 6, L3, temp 0,
`max_tokens` 8192) reused unchanged for every candidate:

| model | params | pair BOTH-CORRECT | single-item | trunc | mean ctok | mean lat | verdict |
|---|---|---|---|---|---|---|---|
| `gemma4:e4b` | 8.0B | 6/6 | 12/12 | 0 | 1004 | 15.4 s | too strong |
| `gemma4:e2b` | 5.1B | 6/6 | 12/12 | 0 | 996 | 7.6 s | too strong |
| **`gemma3:4b`** | **4.3B** | **3/6 = 0.50** | **7/12 = 0.583** | **0** | **180** | **3.8 s** | **SELECTED** |
| `llama3.2:3b` | 3.2B | 0/6 = 0.00 | 4/12 = 0.333 | 0 | 108 | 0.8 s | too weak + 2 responses with no `FINAL:` line → rejected |

Every screen was clean — no truncations, no invalid responses, nothing dropped. `gemma3:4b`
is perfect on algebra, half on quantifier order and zero on implication direction, with
**12/12 correctly formatted responses**: it follows instructions and reasons imperfectly,
which is the organism the protocol wants. The ladder **brackets** the choice — 6/6 above, 0/6 below, `gemma3:4b` alone in band — so it
was not a knife-edge call between neighbours. Frozen in
`evaluation/arena/results/FREEZE_gemma3-4b.json` — model + digest `a2af6cc3eb7fa8be…`,
runtime, prompt hashes, endpoint, scoring, and generator/scorer versions.

**Caveat recorded, not buried:** `gemma3:4b` is a *different family* from the gemma4
candidates. Acceptable because the pilot compares SE/AST/HML **within** this one frozen
model, so family never enters the contrast — but its results cannot be pooled with or
compared against the gemma4 screens. Note also that Endpoint B at L3 remains saturated for
every gemma4 candidate tried; headroom exists for this organism specifically, not for the
endpoint in general. And N=6 pairs makes 0.50 a selection signal, not an estimate.

**MODEL CONFIRMED AND FINAL-FROZEN: `gemma3:4b` — 5/6 out-of-sample, 8/12 pooled.**
Stated precisely because the two halves play different roles: offset 6 scored **3/6 and is
the set that *selected* the model**; offset 8 scored **5/6 and is the only genuinely
out-of-sample half**. The headline 8/12 (0.667) pools selection with confirmation.
Six additional fresh pairs (offset 8) gave 5/6, added to the earlier 3/6. Inside the 4–8
target band, so `FREEZE_FINAL_gemma3-4b.json` supersedes the provisional freeze. Three
caveats are recorded in it: 8/12 is on the **upper edge** and outside the preferred 5–7; the
halves disagree sharply (3/6 then 5/6), so the estimate is unstable; and **`OPERAND_ORDER`
is 4/4 — saturated**, so one third of frozen pilot pairs are expected to be
non-discriminating. The composition was deliberately not changed, because altering task
semantics after selection would invalidate the selection.

**SEMANTIC AUDIT PASSED — 62 checks, read-only, no production change.**
`tests/arena/test_semantic_audit.py` keeps the seven judgment classes separate rather than
collapsing them into one `VALID` flag, and verifies exactly the properties the pilot depends
on: entities, types, free/bound variables, binder order and scope, assumptions, implication
direction, goal/query, and that the oracle answer is *literally shared* across arms. A
negative control confirms a binder swap is observable in every arm. `EXECUTES` and
`IS_PROVEN` are recorded not-applicable **with an assertion**, not skipped. Constitution:
`docs/semantics/HML_SEMANTIC_CONSTITUTION_V1.md`.

**FINAL ACQUISITION: HML 5/6 PASSES, AST CONTROL 4/6 FAILS. Case B — pilot NOT run.**

Attempts #1 and #2 are permanently `INVALID_INSTRUMENT` / instrument-defective and are not
carried forward. Attempt #3 ran on the frozen instrument (seeds 400201–400206) and is the
first valid acquisition measurement in this programme:

| KIND | SE | AST | HML |
|---|---|---|---|
| SORT · FACT_CONTENT · RELATION_LOOKUP · GOAL_TARGET | correct | correct | correct |
| **BINDER_ORDER** | correct | **WRONG** | correct |
| FACT_COUNT | WRONG | WRONG | WRONG |
| **total** | **5/6** | **4/6** | **5/6** |

0 invalid, 0 truncations across all 18 calls. **HML cleared the ≥5/6 bar; the AST control
did not.** No rescoring, no item deleted, threshold unmoved, no fourth attempt.

**The repairs are vindicated by the data:** `GOAL_TARGET` went from wrong in *all three*
arms to correct in *all three* — the exact signature of the diagnosed defect (the world
query was shadowed and never rendered). `FACT_COUNT` failed identically in every arm with
the byte-identical `10\nFINAL: 10`, as predicted from the zero-based-label lure recorded in
the freeze *before* the run.

**This is a readability gate, not evidence about reasoning.** Zero Endpoint-B reasoning
calls have been made in any arm. "AST is harder to read than HML" is **not** established —
its deficit is one item, n=1. HML's own miss is not HML-specific. HML used ~2× the
completion tokens of either control (48.5 vs 23.7/25.0).

**Why this blocks the pilot:** the AST arm is the control that makes the experiment
interpretable at all, and its failure is on `BINDER_ORDER` — half the frozen pilot
composition is `QUANTIFIER_ORDER`. An HML > AST result there could be reasoning, or could be
that the control could not see the distinction.

**BINDER DIAGNOSTIC: the AST control cannot read binder nesting.** SE 8/8, HML 8/8,
**AST 6/8** — and AST's answers are predicted on 5/5 configurations by "say `forall` if
`forall` appears anywhere, else `exists`", a token-presence rule that never reads nesting.
All three misses (2 diagnostic + the ACQ3 gate item) are `exists → forall`. The arm is not
75% reliable at binder order; it is ~0% reliable and 75% lucky. Consequently the first pilot
is **B1 = 12 × IMPLICATION_DIRECTION, 0 × QUANTIFIER_ORDER** — quantifier scope becomes
endpoint B2, after a `GENERIC_AST_V2` exists. Frozen in `PILOT_MANIFEST_B1.json`.

**Pilot composition was decided and documented before any pilot call** —
`docs/evaluation/PILOT_COMPOSITION_DECISION.md`: 6 `QUANTIFIER_ORDER` + 6
`IMPLICATION_DIRECTION` + 0 `OPERAND_ORDER`, calibrated from the SE-only control (4/4
ceiling vs 2/4, 2/4).

**Zero pilot calls have been made.** The PILOT seed band is untouched; ACQUISITION seeds are
burned.

**CI IS GREEN ON THIS BRANCH.** Two dependency-declaration defects, same class, fixed in
sequence: SymPy (ported from `8e1c4df`) and now **tiktoken**, which the Representation
Arena introduced. `evaluation/arena/budget.py` does a bare `import tiktoken` — correctly
bare, since a silently degraded token measurement beats no failure — but `[dev]` did not
pull in the already-defined `tokenizers` extra, so a clean runner failed three Arena budget
tests while a long-lived local venv passed. `.[dev]` is now the complete conformance
environment. An AST audit of every third-party import confirms **tiktoken was the only
genuine gap reachable by conformance**; numpy/scipy/transformers/yaml appear only under
`audit_rerun/` and `experiments/`, which pytest never collects.

Previously: **CI IS GREEN ON THIS BRANCH.** The reproducible environment repair proven on
`integration/m1.5-paper-derived-closeout` @ `8e1c4df` was never propagated here, so this
branch stayed red for an environment reason while the fix sat on a divergent branch. Ported
now: SymPy declared as an `equivalence` extra (`>=1.14,<2`) that `[dev]` installs, the
scoring-worker test made portable, and workflow concurrency bounded. No mathematical
semantics changed and no test weakened.

**HML V2 REASONING KERNEL — PHASE I LANDED (branch `feature/hml-reasoning-kernel-v2`).**
The language now has a surface form for a reasoning *transition*, which the language
audit found it entirely lacked (0/19 transformation forms representable in `.hml`).
Three statement forms — `goal`, `derive`, `proved` — plus a 16-rule trusted kernel,
generated proof obligations, and a scoped refinement environment that makes `assume`
load-bearing. `DeriveStmt.status` is computed by the checker and has no surface syntax,
so a model can assert a derivation but cannot assert that it is correct. See `D-025` and
`docs/hml_v2/`.

Strictly additive: all 43 `examples/**/*.hml` hash byte-identically under the V2 and v1
compilers, so ACQ0/H2 records stay reconstructible under their original language version.

**Phase II is now done too (D-026):** all eleven critical coverage zeros are closed and
enforced — expectation/conditional/joint/independence, set membership and comprehension,
limit/derivative/integral/continuity, and correlation-vs-causation. Four ship as examples.

**Adversarial review found a critical defect in the phase-I spine and it is fixed
(D-027):** a `goal` was admissible as a derivation premise, so `goal g1 : 1.0 = 2.0`
could prove itself with zero diagnostics. Premises must now be ESTABLISHED, and
obligations propagate along derivation chains.

**The capability audit has been rerun (`docs/hml_v2/AUDIT_RERUN.md`).** Critical zeros
11 → 0 and critical faithful 79.7% → 96.9% under corrected probes (8 zeros / 82.8% under
unmodified probes; both readings published). Transformation representability 0/19 → 7/19
and verifiability 0/19 → 7/19. Backend silent loss held at 0. **Maturity is still
LEVEL 1 — DOMAIN DSL**: compositional closure measured 0.692 against a Level 2 threshold
of 0.70, and coverage is `NOT_ASSESSED` with 408/486 atoms unprobed. Criterion 3.5 —
transformations that check their own preservation, which the ladder names as the
distinguishing Level 3 capability — moved FAIL → PASS.

**READ `docs/handoff/HML_HANDOFF_2026-08-08_SIGNAL_PIVOT.md` FIRST.** It is the
authoritative, verified entry point for a fresh context and supersedes any stale figure
elsewhere in this file.

**STRATEGIC PIVOT.** The plan is no longer "finish HML → harder maths → paired benchmark".
It is a neutral semantic world factory rendered three ways (structured English / generic
AST / HML) feeding representation microbenchmarks — next-action prediction, paired minimal
contrasts, corruption detection. **A generic AST is a required control**: without it, any
HML benefit could be a benefit of structure in general.

**SYNTHETIC CALIBRATION ALSO SATURATED — `SYNTHETIC_STATE_COMPLEXITY_SATURATED`.** A
neutral machine-generated difficulty lab (four families, deterministic oracles, validated
offline with independent cross-checks) returned **9 valid / 9 correct / 0 truncations**
across L3, L5 and L7 — L7 being depth-16 dependency chains with 6 distractors and
10-variable logic worlds with 26 constraints. Two independent instruments have now failed
to find headroom for this model. See `docs/evaluation/SYNTHETIC_CALIBRATION_REPORT.md`.
Total local Gemma calls across all protocols: **22. HML calls: 0.**

**THE EARLIER SE CALIBRATION ALSO FOUND NO USABLE HEADROOM.** 13/13 calls used;
**10 valid observations, 10 correct**. The two apparent failures were `finish=length`
truncations at 8192 tokens, one of them mid-way through a correct argument — recorded
MEASUREMENT_INVALID rather than counted as difficulty. This is the third corpus in the
project's history to saturate (93%, 100%, 10/10). The one difficulty axis discovered
(length) is unusable for this hypothesis, because HML is more verbose than prose and would
truncate sooner. See `docs/evaluation/SE_CALIBRATION_REPORT.md`.
**No HML model call has been made. Total Gemma calls: 13, all structured English.**

**Superseded note — SE difficulty calibration was under way (signal-first directive).** Structured-English
only, no HML. CAL-1 3/3 and CAL-2 5/5 against tasks built around the exact semantic traps
HML targets; CAL-3 pending. 9 of the 13-call budget used. No truncation (877-2392 tokens of
8192). This is the third corpus in the project's history to saturate.

**A binder protocol now exists (D-046),** added to fix `free_names`, which dispatched by
whitelist and silently reported NO free variables inside an integral, derivative or
comprehension. Measured: `ObligationTask.closed()` returned **True** for a proposition
with a free variable. Masked end-to-end by an unrelated subset guard, so no wrong verdict
was delivered — but wrong in the dangerous direction. `binder_of` / `expr_children` /
`BINDER_KINDS` are structural, so an unknown node kind is descended into rather than
skipped. Used by `free_names` only; the other ~78 binder dispatch sites are unaudited.

**The binder/shadowing defect is fixed (D-045).** D-006 was being applied to mathematical
binders, so `derivative(f, x)` was rejected whenever `x` was declared. Composition moved
0.438 -> 0.458 — one specimen, against a prediction of high leverage that was wrong.

**A CRITICAL soundness exploit was found and closed (D-044).** Obligations were keyed on
the inference rule, so `multiply_both_sides(by := 1.0 / 0.0)` reached VERIFIED and its goal
reached PROVED with zero diagnostics. Definedness is now a property of TERMS: one contract
registry, and a pass over every expression a derivation touches. Refuted obligations REJECT
rather than sit OPEN. Also closed: `Matrix[2,3] + Matrix[4,5]` compiled clean (HML-T435).

**The full 486-atom ontology is now classified with executed states:** PASS 162, PARTIAL 71,
LOSSY 207, ABSENT 21, BACKEND_ONLY 1, NOT_MEASURED 24. Of the 64 CRITICAL: PASS 47,
PARTIAL 15, LOSSY 2, **ABSENT 0**. Whole-ontology PASS+PARTIAL is 233/486 = 47.9%.

**Scoped Γ is implemented (D-043):** `scope … end` opens a real assumption frame; facts
do not survive it, precede it, cross to siblings, or escape nesting. Local contradiction
is warned and contained rather than banned, so proof by contradiction stays expressible.
Composition moved **0.417 → 0.438** — one specimen; the gate is 0.85 and the remaining
failures are 14 GRAMMAR / 8 TYPE.

**The AST fork is decided on measurement: no rewrite (D-041).** The 48 composition
specimens were encoded and executed for the first time — STRICT closure **20/48 = 0.417**
(the legacy 13-probe subset reads 0.692 at the same SHA; they are different instruments).
Failure attribution over 28 failures: GRAMMAR 14 · TYPE 8 · COMPILER 3 · CONSTRAINT 2 ·
SCOPE 1 · CANONICAL 0 · BACKEND 0. A generic Apply/Bind/Attribute core would reach
**0.563 — below the Level 2 threshold** — while targeted repairs reach **0.854**. The
rewrite is neither necessary nor sufficient. Circular probability laws are now rejected
(HML-S607, D-042).

**An explicit evidence graph now backs the reasoning layer** (`reasoning/evidence.py`,
D-040). Acyclicity previously rested on a single textual-order rule that was sound only
for single-module source-order construction and never saw `proved` edges; there is now a
validator walking all four edge kinds, a three-way ESTABLISHED / PROVISIONAL /
NOT_EVIDENCE split, and named checks for E1/E2/E3/E4/E7/E8.

**Research-integration decisions are recorded** in
`docs/hml_v2/RESEARCH_INTEGRATION_DECISIONS.md`: 14 recommendations classified against
measured state, with the generic Apply/Bind AST core explicitly DEFERRED pending failure
attribution rather than accepted on recommendation. Measured corrections to inherited
figures: tests are 6252 (not 6240); the full 48-specimen composition set closes **20/48**,
which is not the same measurement as the 0.692 reported over a 13-specimen subset.

**A 16-step programme is now underway; step 1 (architectural freeze) is done.**
`docs/hml_v2/ARCHITECTURE_FREEZE.md` freezes six decisions as binding contracts —
evidence semantics, Γ/scope, definedness, approximation, verifier certificates and
extension trust (D-034…D-039) — each with its rejected alternatives recorded. Twelve
tests pin the decisions that already hold. **The freeze is a contract, not an
implementation**: scoped Γ, precondition contracts, approximation and certificates are
all still absent from the compiler. Steps 2–4 implement them next; step 5's AST fork
(generic Apply/Bind/Attribute core vs bespoke nodes) is being measured, not assumed.

**Phases III-IV are NOT done** — compositional-closure measurement, the extension/module
mechanism, the synthetic trajectory generator, the 100+ specimen suite and the
capability-audit rerun all remain. **No maturity-ladder claim is made until the audit is
rerun**, and no BEFORE/AFTER coverage percentages exist yet.

**THE 24-TASK V1 BENCHMARK IS RETIRED FOR H2 — `HML_BENCHMARK_FAILED_NO_SIGNAL`.**
The SE control scored **23/23 (100%)** against a usable headroom band of 6-17, so the gate
returned INSUFFICIENT and **no HML-V1 call was made**. See
`docs/evaluation/V1_HEADROOM_GATE_REPORT.md`.

**This is a verdict about the corpus, not about HML.** No HML scientific call exists.

Run `decisive_01`, developmental protocol v1.3: 23 valid paired tasks, 46 calls, 2.27 h,
132,571 completion tokens. Integrity complete -- 0 truncations, 0 transport errors, all 46
calls scored `ok`, exactly one answer marker per reply, one model digest, **zero drift in the
scientific-input hash across the whole run**, and all 23 results reconstruct exactly by
re-scoring the raw content.

**Two purpose-built corpora have now been lost to saturation in a row** -- eval001 at mean
accuracy 0.961, and this one at 1.000 against a predicted 0.556. All three tied-hardest tasks
and every convention trap were answered correctly. The difficulty estimates, all marked
`PREDICTED_NOT_MEASURED`, carried no signal.

**The transferable finding is that headroom is a function of the completion budget.** On the
same tasks with the same model at temperature 0: at 4096 tokens the probe truncated and
`v1b_06` returned **zero characters of content**; at 8192 the model scored 23/23. The
reasoning trace alone costs ~3,000-4,000 tokens. Below ~5,000 the corpus floors on a
measurement artefact; above it, it ceilings. A corpus must be calibrated **at the budget it
will be run at**, and a difficulty estimate that ignores the completion budget is not an
estimate of difficulty.

Recorded plainly: the v1.2 -> v1.3 budget raise was necessary (4096 produced no answer at
all) and is also what moved this corpus from floor to ceiling. Both changes were committed
before any scientific call, but the budget decision and the saturation outcome are causally
linked.

**Where the value landed.** The measurement returned no signal; the pre-run work returned
four demonstrated scorer/prompt defects, two harness defects, one excluded task, and 24/24
independently re-derived answer keys. Had the corpus not saturated, the run would have
proceeded on a scorer that mis-scored exact-form answers **differentially by arm** -- which
could have produced a confident, wrong verdict.


**DEVELOPMENTAL PROTOCOL v1.3 — v1.2 WAS FALSIFIED BY ITS OWN PROBE, AND FOUR HARNESS
DEFECTS WERE FOUND AND FIXED. NO SCIENTIFIC CALL HAS BEEN MADE.**

The operational probe ran the two pre-declared tasks at v1.2's 4096-token allowance and
**both truncated**. The cause is a model property v1.2 did not account for: `gemma4:31b` is
a reasoning model whose thinking trace is billed to `completion_tokens` but returned in a
separate field. On `v1b_06` the trace consumed the entire allowance and returned **zero
characters of content** — an absent answer, which is exactly the artefact the amendment
exists to prevent, reproduced one rung lower.

- **Allowance raised to 8192 per call / 16384 per arm**, identically in both arms.
- **Runtime reconfigured to `1 x 32768`** — the mission's stated contingency. Total KV
  context is unchanged (`16384 x 2` → `32768 x 1`), so it costs no memory; it trades
  parallelism for slot size. Digest re-verified after restart.
- **Four harness defects, demonstrated and repaired** (all independently reproduced before
  any change): **D1** the *first* `<ANSWER>` span was scored rather than the last, which
  penalised the second call exactly when it worked; **D2** the first number-like substring
  was mined out of the answer, so `16/7 → 16.0` and `ln(5/2) → 5.0` — a **differential**
  error, since a formal arm is likelier to write exact forms, so it fell on the treatment;
  **D3** a reply with no marker was scored against its whole text, so
  `"flipped 10 times … Var(H) = 2.5"` scored **correct** against key 10; **D4** SE carried
  its whole first reply into call two while HML carried only the extracted fence, which
  handicapped the treatment and contradicted the design's own claim that the arms "differ
  in exactly one respect".
- **`v1b_11_negation_scope_choice` excluded** for a pre-run defect: its options are not
  mutually exclusive and the choice scorer cannot accept an explained answer. **23 valid
  paired tasks remain against a required 20.**

Previously: **DEVELOPMENTAL PROTOCOL v1.2 COMMITTED; THE DECISIVE SE-vs-HML-V1 RUN IS ARMED BUT NOT YET
RUN.** The 24-task benchmark has an amended runtime budget, a crash-safe driver, and two
pre-run defects fixed. No scientific call has been made at the time of this commit.

- **Amendment (`docs/evaluation/V1_PROTOCOL_AMENDMENT_v1_2.md`).** Per-call completion
  allowance 1024 → **4096**; total per arm 2048 → **8192**; applied identically to both
  arms. Everything else — temperature 0.0, model digest, two calls, task set and order,
  scorer, matched information, matched revision — held exactly as frozen. 1024 was unsafe
  because eval001 truncated 11 of 285 completions at a **2400** cap, and a truncated
  completion is an *absent* answer scored as a failure of the representation. HML must emit
  a module *in addition to* its reasoning, so it is the more verbose arm by construction and
  the artefact would have been **anti-correlated with the treatment**.
- **The recorded runtime was wrong.** `arms.RUNTIME` says `4 x 8192`; the live server runs
  `OLLAMA_NUM_PARALLEL=2 OLLAMA_CONTEXT_LENGTH=16384` — a **`2 x 16384`** arrangement. The
  measured value is now recorded and the driver refuses to start if the server disagrees.
- **Context fit is measured, not estimated.** Ollama 0.32.5 has no tokenizer endpoint, so
  envelopes were measured with `max_tokens=1` calls (which cannot collide with scientific
  cache keys). Worst case is HML repair at **10,857 of 16,384**, leaving 5,527 tokens spare.
  **The two-slot arrangement fits; the 32,768 single slot is not required.**
- **Defect fixed — unbounded compiler diagnostics.** `classify_diagnostics()` renders without
  bound: 200 lines of garbage HML produce **389,426 characters (~130,000 tokens), a 122×
  blowup** that overflows *any* slot. It would have truncated the repair prompt hardest
  exactly where the model wrote the worst HML — again anti-correlated with the treatment.
  Capped at 6,000 chars / 40 diagnostics with an explicit omission notice. The cap can only
  *remove* help from the treatment arm, so a positive HML result under it is a lower bound.
- **Defect fixed — no crash safety.** `pipeline.run_benchmark` held all results in memory and
  interleaved the arms, making the SE-first headroom gate impossible. Replaced by
  `evaluation/v1_benchmark/driver.py`: write-once records, immediate save, resume-missing-only,
  immutable manifest, source-level drift hashing over tasks/prompts/scorer/compiler/extraction,
  halt on truncation and on transport error.

Previously: **eval001 IS SATURATED AND UNUSABLE FOR H2 — HEADROOM_INSUFFICIENT (complete, 285/285).**
The plain-English headroom screen (95 deduplicated problems x 3 seeds, temperature 0.7)
returns **mean accuracy 0.961**: **90 of 95 tasks are 3/3 correct** and only **3** fall in
the 1/3-2/3 headroom band against a required 30. **Three of five domains — algebraic,
binding and quantifier — are at 3/3 on every single task**, so they carry no signal at all;
the three headroom tasks are two dimensional and one probability. 92/95 tasks are unanimous
across all three seeds, which makes this corpus saturation rather than sampling noise.
Integrity: matrix complete, 0 duplicates, 0 transport failures, 0 scoring failures, every
prompt hash matching the manifest, one model digest, 11 truncations at the inherited
max_tokens of 2400. The pilot's 93.3% was not an
artefact of its 15-problem sample — the whole corpus is saturated.

This closes a wrong path cheaply and confirms the right one: the purpose-built **24-task v1
benchmark** (`evaluation/v1_benchmark/tasks.py`) is the H2 corpus. Its claims were verified
independently — 24 tasks, mean predicted accuracy **0.556** exactly, all 24 inside the
0.40-0.70 band (range 0.45-0.67), contamination clean against 517 items across 18 corpora,
24/24 carrying independent key verification, and its 3 apparent answer leaks cleared as
multiple-choice letters that necessarily appear in their own options.

Previously: **PYRIGHT CONFIGURED; ONE STALE RE-EXPORT CLOSED.** The repository had no Pyright
configuration at all, so 126 of 484 baseline diagnostics were unresolved imports of
installed packages — and every file carrying one was analysed against a partly-blind view.
Configuring the environment truthfully (no mode weakened, nothing excluded that matters)
drops the count to 374. One confirmed runtime defect is fixed: `hamiltonian_lang.
verification.__all__` named `obligations` without importing it, so attribute access raised
and `import *` bound nothing; a test now walks every package and asserts each `__all__`
entry exists. The remaining 374 are largely untriaged — see
`docs/audits/PYRIGHT_OVERNIGHT_AUDIT.md`.

Previously: **CAP_CALIBRATION_FAILED — THE SURVIVOR RERUN IS BLOCKED, AND A BIGGER CAP IS NOT THE
FIX.** Both cap probes at 12,288 reached the cap exactly and truncated, on the same task
that truncated at 6,144. The transcripts show why: the model restates the module header
**229 times** in surface A and **161 times** in surface C, cycling on the identifier
`varrho` which it repeatedly mistypes as `vvarrho` and restarts over. Two allowances a
factor of two apart, both fully consumed, with the repetition count scaling with the
budget — that is non-termination, not an undersized budget. The proposed 1 x 32,768
configuration is recorded as required but is **not recommended**: it predicts ~500
restatements, still truncates, and costs ~10 hours at halved concurrency. It is one task,
not one surface: the other seven surface-A tasks finished with `stop`, and this task
completed cleanly in surface B.

Previously: **TRANCHE A VOID ON TRUNCATION; SURFACE D ELIMINATED BY UPPER BOUND.** The 32-condition
run completed and is `MEASUREMENT_INVALID` (D-033). Everything except the cap audited clean:
matrix complete 8x4, no duplicates, no missing, 0 transport failures, no prompt drift, no
bundle drift, no repository mutation during measurement. Three conditions hit the 6,144-token
completion allowance, and the truncation decides the verdict for two of four surfaces, so no
surface-selection or continuation decision is derived from it. All 32 records are preserved
with a hash manifest, admissible for debugging only.

**Surface D is eliminated without a rerun**: repaired parse 0/8, one truncated record and
only in repair, so the best attainable count is 1/8 against a frozen 6/8 threshold. Its
failure class is schema conformance — every attempt emitted a *triples* encoding where the
candidate specifies a `statements` array, and all failed at import, none at the compiler.

Previously: **MEASUREMENT_INSTRUMENT_GREEN; TRANCHE A RUNNING.** All green conditions hold: 12/12
development tasks and 2/2 spares admitted, view-only reconstruction 14/14, round-trips
56/56, leakage clean with a firing negative control, mutation controls firing, full tests
and conformance passing. Green means **suitable for a developmental model experiment** — it
does not mean officially human-approved, promotion-ready, or mathematically exhaustive.

The prompt budget is re-measured against the frozen runtime (`-c 32768 -np 2`, slot 16384,
completion 6144, reserve 256, ceiling 9984) with the **same builder the run uses**: worst
case A 3177 / B 3179 / C 3329 / D 5056 tokens, all four fitting with 4928–6807 headroom.

**One harness defect was found by the first Tranche A attempt and the attempt was
discarded.** Candidate C's own specification advertises the fence tags `sexpr`, `lisp` and
`scheme`; the model answered inside a ```lisp fence with a **hash-identical** encoding, the
raw text went to the importer fence and all, and the import failed. Surface C would have
been eliminated on a harness bug reported as a property of the notation. The scorer now
strips any fence, with a regression matrix over every surface and seven tags.

Previously: **ACQ0 v2 DEVELOPMENT CORPUS ADMITTED — 12 TASKS + 2 SEALED SPARES.** The taxonomy is
frozen at twelve feature cells (`docs/evaluation/ACQ0_V2_TAXONOMY.md`), all twelve covered,
every coverage rule met. Two independent read-only reviewers examined the corpus in two
rounds and returned **0 WRONG and 0 REJECT**; all eight of their findings were repaired at
the **generator**, never at an individual answer, and each has a regression test.

The binder-only partiality guard is replaced by an **AST scanner** that walks every
expression position and follows definition dependencies — module variables, compound
denominators, negative and fractional powers, variable exponents, `sqrt`/`log`/`tan`,
indexing, and partiality one or two `def`s deep — reporting a named risk path and failing
closed. It marks a dimensioned denominator **UNGUARDABLE**, because `require area != 0`
does not compile (HML-D502).

Three defects the reviewers found were in the governance layer rather than in any task:
`build_bundle` still served the retired bucketed target; `structured_target()` dropped
`CheckStmt` everywhere downstream, so the semantic diff scored a dropped `check` as unequal
with an **empty difference list**; and the objective was stated twice in prose in a form
that compiles to a different hash. `structured_target()` now raises — the fact layer, the
prose generator and the semantic diff all read one traversal.

Previously: **ACQ0 v2 MODEL-VISIBLE VIEW REPAIRED.** A line-by-line
English-versus-formal review of all eight tasks found that the artefact handed to a model
was insufficient to produce the reference. `structured_target()` partitioned each module
into unordered kind-buckets while `content_hash` is order-sensitive, so three tasks were
unencodable; a fourth dropped its `check dimension` statement entirely because the function
had no `CheckStmt` branch. Two further tasks were mathematically defective — a one-sided
bound in the approximation family, and an unguardable division by a module-level `var` in
the dimensional family.

The repair is generator-level, not answer-level (D-030). The model now receives one ordered
`encoding_statements` list with explicit `emit` flags, prose follows encoding order, and
**admission requires that the view alone reconstruct the reference**: view → rebuild →
compile → `content_hash` equality. That gate is the first check in this project that crosses
the boundary where the loss occurred — the three previous checks each validated an artefact
against itself. It is now **8/8 exact**, with the two defective tasks replaced under fresh
ids and preserved. **No task is marked human-approved; that decision is not automatable.**

Previously: **ACQ0 v2 AUDIT COMPLETE; MODEL TESTING PAUSED.** All hardening sections executed. Five defects were found in v2 itself and fixed: metadata outside identity, unguarded partiality, a self-contradictory `state_in_prose` classification, an ambiguous omitted codomain, and a leak check that could not fail. Prose coverage 8/8 exact, reversibility 8/8, round-trips 32/32, firewall enforced.

Previously: **ACQ0 v2 HARDENED.** The hardening audit found two defects in v2 itself: semantic metadata sat outside canonical identity, and an unguarded partial definition was admitted. Both fixed; `canonical_hash` (encoding identity) is now distinguished from `semantic_identity` (task identity). Audit sections C, F, H, I, J remain incomplete.

Previously: **ACQ0 INSTRUMENT REBUILT (v2).** The v1 41-task corpus is quarantined `INVALID_INSTRUMENT` (0/41 admissible): mathematics was authored in three independent places and disagreed, so a frontier model that followed the prose was scored FAIL. `CanonicalAcq0TaskV2` makes one object the authority and derives every artefact from it; 8 proof tasks are admissible with exact round-trips through all four surfaces. Both protocol calibrations (v1 completion-cap, v2 invalid corpus) are void; no protocol has been validly selected.

Previously: **M2 CONTEXT BUDGET MEASURED.** Selected shared runtime `4x8192`, curriculum size 5, measured `prompt_eval_count`: A 1880 / B 1887 / C 2074 / D 4907 / SE 1829 against a 5888 ceiling. Worst case D, 981 tokens headroom (16.7%), full 2048 allowance and 256 reserve intact, zero truncation. The tokeniser beats 2.48 ch/tok everywhere, so candidate D is NOT eliminated on budget.

Previously: **M1.5 INTEGRATION.** All four resumed agents returned. Two blocking soundness defects found by an independent falsifier are closed (D-026 unsound VERIFIED behind a `def`; D-027 false-positive equivalence under a spare rename). Suite **4927 passed**, `CONFORMANCE: PASS`.

Previously: **RECOVERY.** Three subagents terminated on an API session limit mid-write. The dirty tree (152 files) is preserved verbatim on `recovery/session-limit-2026-08-05`; see `docs/evaluation/SESSION_LIMIT_RECOVERY_MANIFEST.md`. State at capture: **4721 passed**, `CONFORMANCE: PASS`. Four subsystems returned gate verdicts; three (Chain-of-Repair, format protocol, benchmark governance) are **INTERRUPTED and unaudited** — each stopped while writing its own tests, so their controls are the parts most likely missing.

**HML-CONSTITUTIONAL-CORE-001 — installing recursive improvement as a constitutional
subsystem.** Phase 0 baseline is recorded in
`docs/evaluation/CONSTITUTIONAL_CORE_BASELINE.md`. The compiler is the semantic truth
kernel; the new subsystem is an improvement control plane. Governing law: *models and
agents may propose changes; only external verification and controlled evidence may change
the official system.* After the constitutional baseline is frozen, every experimental
transition must change exactly one major state component (`|ΔS|₀ = 1`).

**Four identifiers are now maintained separately: ACQ0 (prerequisite), H1, H2, H3.** ACQ0 asks only whether the model can *write* the language; it is not evidence for any hypothesis, and its repair mechanism is `ACQ0_REPAIR`, not H3. See `docs/evaluation/HYPOTHESIS_REGISTER.md` and `evaluation/manifests/hypotheses.json`.

**H1, H2 and H3 are held apart mechanically, not by convention.** `Episode.hypothesis_id`
and `EvidencePackage.hypothesis` are typed values; episodes from different hypotheses may
not be aggregated; the controller may not advance a stage on evidence from a hypothesis its
gate does not name. **A win on H3 alone is a win for verifier-guided reasoning and must
never be reported as a win for the representation.** All three remain **UNTESTED**.

**F2/F3 ownership: resolved, no conflict existed.** `evaluation/syntax_gate/candidates.py`
is a binding layer over `evaluation/syntax_acquisition/`, not a second renderer. All four
candidate surfaces round-trip to **hash-identical** canonical objects on four examples, so
no candidate receives additional mathematical information.

Previously: **HML-PHASE-FG-001 — freezing the supported V1 subset and preparing the Gemma syntax
tournament.** Phases F1 (freeze-eligibility audit), F2 (fair benchmark partition) and F3
(offline equivalence gate) are in progress. No model call is legitimate until the offline
gate passes and the Lead tags `hml-v1-eval-freeze`.

Host tuning is measured and recorded in `docs/evaluation/EXECUTION_ENVIRONMENT.md`: stock
Ollama serialises every request at one slot (~23 tok/s regardless of client concurrency);
four batching slots with exactly four client workers give **2.08x**, and eight workers
*degrade* to 1.43x. The 18 CPU cores do not accelerate a GPU-resident 31B model — they
accelerate the offline round-trip matrix and the test suite (13.3s to 6.5s). The largest
curriculum (50 demonstrations, 5,893 prompt tokens) fits the 8192-token slot, so that
configuration is safe for the whole tournament.

The F4 freeze is **enforceable, not declarative**: `evaluation/syntax_gate_freeze.py
--verify` recomputes every hash and exits non-zero on drift, hashes frozen trees wholesale
so an added file also counts, and pins the model by digest rather than by its reassignable
tag. **The tournament has not been run. Nothing about syntax acquisition is yet known.**

**HML-EVAL-002 preregistered; V1 implementation in progress.**

**Status of the central thesis: UNPROVEN, NOT REFUTED.** The precise conclusion from the
pilot is: *zero-shot Hamiltonian did not improve answer accuracy on this small,
low-discrimination pilot; the experiment was underpowered and had a severe ceiling effect.*
A correction is recorded in `V1_GATE_DECISION.md` — an earlier version of that document
said "refuted", contradicting this project's own pilot report §9. The report was right.

The checker is a **component of a verifier-guided reasoning system (H3)**, not the
objective. The earlier drift toward treating it as the product is withdrawn.

Previously: **V0 closed and preserved; V1 in design.** V0 is tagged `hml-v0-baseline` — the language,
the frozen spec, and 221 stored model trials. `src/` does not change under that tag.
**Hamiltonian V1: Discourse, Transformation and Epistemics** is specified in
`docs/design/V1_KERNEL.md` with a preregistered comparison plan in
`docs/design/V1_EXPERIMENT_PLAN.md`. Nothing of V1 is implemented.

Previously: **HML-EVAL-001 — empirical evaluation phase.** v0 is frozen at tag `hml-v0-eval-freeze`.
No new language features, domains, or abstractions are being added. The sole objective is
to test whether a model reasons better through Hamiltonian Lang than through English,
structured English, LaTeX, or an existing formal representation.

## Current Branch

Active development: `feature/hml-reasoning-kernel-v2` (worktree
`/Users/moheet/hml_v2_worktree`, based on `3dd4216`, now carrying the CI repair `ff915ad`
and the Representation Arena). The scientific integration branch
`integration/m1.5-paper-derived-closeout` is unchanged and was not merged into.
The language-audit worktree `/Users/moheet/hml_audit_worktree` is read-only evidence.
V0 preserved on `main` at tag
`hml-v0-baseline`; the interrupted state is preserved on
`recovery/session-limit-2026-08-05`. Repository is private.

## Current System Architecture

Three layers, one identity:

1. **Surface** — HML-L1: ASCII-canonical, line-oriented, role-labelled, `end`-delimited.
2. **Semantic core** — typed AST + symbol table + proof obligations. The only source of
   truth. `src/hamiltonian_lang/ast/nodes.py` is the frozen contract.
3. **Backends** — projections: HML, canonical JSON, semantic graph, triples, LaTeX,
   controlled English, Stan, SymPy, Lean statement skeletons. Every one reports its own
   translation loss; **no example is faithful under Stan, SymPy or Lean**, and each says so.

Pipeline: source → lexer → parser → name resolution → type checking → canonical form →
views. Source spans are preserved through every stage.

## Capabilities Implemented

- Scalar refinement **poset** (`Probability` and `PositiveReal` incomparable, meeting at
  `NonNegativeReal`; `PositiveNatural` as their meet with `Natural`)
- Structurally distinct `T`, `RandomVariable[T]`, `Distribution[T]` with no subtyping path
- Rational-exponent dimensional algebra over seven SI base dimensions, exact and decidable
- Shape checking for `Vector`, `Matrix`, `Tensor`, including matrix-vector inner extents
- Lexer with ASCII canonicalisation and Unicode folding (μ U+03BC and µ U+00B5 both fold
  to `mu`, warned)
- Recursive-descent parser, LL(1) at statement level, non-cascading error recovery
- Name resolution with stable `SymbolId(name, ordinal, depth)`; shadowing rejected;
  order-independent module scope
- Distribution registry with **mandatory role labels** and targeted diagnostics for known
  misparameterisations (scale-vs-variance, rate-vs-mean, `n`/`p`, `a`/`b`)
- Proof-obligation collection — constraints, assumptions, theorems, concept invariants,
  and standing positivity requirements
- Canonical JSON + SHA-256 content hash: invariant under renaming, sensitive to quantifier
  order and role assignment
- Semantic graph with a closed edge vocabulary; triple output; transitive dependency query
- `hml` CLI: `check render canonical hash graph obligations views`
- **Representation Arena (`arena-1.0.0`)** — a structure-first neutral world factory over
  three families, three renderers (SE / generic AST / HML), a decoder per arm proving
  information parity by round trip, three endpoints (next-action, paired minimal contrast,
  corruption), a truncation-aware scorer, a token-budget instrument and an eight-check
  pre-flight gate. Every HML rendering compiles under the real compiler.

## Work Completed to Date

Repository initialised from `MoheetBrain/hamiltonian-lang` (which contained only a
README). Full directory structure, governance documents, ten agent definitions, five
project skills, deterministic conformance script, git hooks and CI created. Semantic
kernel, compiler and core backends implemented by the Lead Architect. Four subagents run
against isolated file ownership.

## Important Files and Artifacts

| file | role |
|------|------|
| `GOAL.md` | project thesis |
| `docs/design/V0_DESIGN_FREEZE.md` | the frozen v0 contract |
| `SPEC.md` | normative language reference |
| `DECISIONS.md` | D-001..D-032 with reversal costs |
| `docs/evaluation/ACQ0_V2_TAXONOMY.md` | **the frozen 12-cell taxonomy and feature matrix** |
| `docs/evaluation/ACQ0_V2_INDEPENDENT_SEMANTIC_REVIEW.md` | both review rounds, compact |
| `evaluation/corpus_governance/partiality.py` | **the AST partiality scanner** |
| `evaluation/acq0/v2/prompt.py` | the one frozen prompt builder |
| `evaluation/acq0/v2/run.py` | the Tranche A driver and preregistered gates |
| `evaluation/corpus_governance/canonical_v2.py` | **the single ACQ0 authority** |
| `evaluation/corpus_governance/v2_view.py` | **the ordered view and the admission gate** |
| `evaluation/corpus_governance/v2_render.py` | every model-visible artefact, all derived |
| `evaluation/corpus_governance/v2_corpus/tasks.py` | the eight proof tasks |
| `docs/evaluation/ACQ0_V2_HUMAN_REVIEW_PACKET_R2.md` | **private review packet — never model-visible** |
| `evaluation/results/acq0/superseded_tasks/SUPERSEDED.md` | withdrawn tasks, with reasons |
| `benchmarks/eval001/` | 120-problem corpus, 7 arms, 840 prompt files |
| `evaluation/harness.py` | model-evaluation harness |
| `evaluation/analyse.py` | paired intervals, McNemar, effect sizes |
| `docs/evaluation/HML_EVAL_001_PILOT_REPORT.md` | **the pilot result and decision** |
| `docs/design/V1_KERNEL.md` | **V1 five-layer design** |
| `docs/design/V1_EXPERIMENT_PLAN.md` | preregistered V0-vs-V1 plan |
| `spec/v1/semantic_objects.yaml` | V1 objects, machine-readable |
| `evaluation/results/EVAL_SPEC_v1.1.json` | frozen spec + defect record |
| `docs/evaluation/PRE_EVALUATION_AUDIT.md` | verified state before the experiment |
| `audits/RED_TEAM_REPORT.md` | adversarial review |
| `src/hamiltonian_lang/ast/nodes.py` | **frozen IR contract** |
| `src/hamiltonian_lang/types.py` | the type lattice |
| `src/hamiltonian_lang/type_system/distributions.py` | distribution roles |
| `spec/ir.schema.json` | canonical form JSON Schema |
| `scripts/conformance.sh` | deterministic gate |
| `docs/research/PRIOR_ART.md` | prior-art and novelty analysis |

## Data Sources and Provenance

No external data. The seven reference examples are authored from the master directive.
Prior-art licence claims were verified from canonical sources during Wave 1 and are
recorded in `docs/research/PRIOR_ART_MATRIX.csv` with an explicit UNVERIFIED register.

## Decisions and Rationale

D-001..D-021 in `DECISIONS.md`. Load-bearing ones:

- **D-003** mandatory role-labelled distribution arguments. Prior art shows the
  *mechanism* is not novel (PyMC, SciPy already use named parameters); the delta is that
  labels are mandatory rather than conventional.
- **D-004** the scalar order is a poset, not a chain. Linearising it would admit unsound
  programs.
- **D-005** hybrid binding: readable names, structural identity.
- **D-012** the claimed contribution is demoted from the representation to the experiment.
- **D-014** the frozen alphabet and grammar survive measurement across 8 real tokenisers.
- **D-016** eight adversarial defects found and fixed; all eight are now rejected with a
  named diagnostic code.
- **D-017** interface names (concept parameters, distribution roles) are meaning; only
  local binders are alpha-renameable.
- **D-018** a green property test is only evidence about the inputs its generator
  actually reaches.
- **D-019** the lexer did not terminate on non-ASCII letters; it would have hung the
  evaluation harness silently rather than failing it.
- **D-020** the five inference queries do not share a precondition; requiring a law for
  `mle` rejected the most common frequentist model in statistics.

## Verification and Test Results

**Current run — 2026-08-10, the post-build audit repair (D-048/049/050).** Executed:

| check | exact command | result |
|---|---|---|
| conformance gate | `bash scripts/conformance.sh` | **CONFORMANCE: PASS**, all stages |
| full suite | `.venv/bin/python -m pytest` | **7268 passed**, 6 skipped, 7 xfailed, 7 xpassed, **0 failed** |
| semantic state | `pytest tests/semantic_state` | **279 passed** (was 266) |
| 30 acceptance fixtures | `pytest tests/semantic_state/test_semantic_firewall_acceptance.py` | **30/30 unchanged by the repairs** |
| the six audit probes | re-run against repaired code | **6/6 now INVALID or ineffective** |
| UNKNOWN suppression | one junk claim vs 10 ILLEGAL fixtures | **0/10 suppressed** (was **10/10**) |
| mutation: frame condition disabled | suite re-run | **caught** (3+ tests fail) |
| mutation: unknown scoping reverted | suite re-run | **caught** |
| mutation: new decision-ID collision | `pytest tests/freeze/test_decision_ids.py` | **caught** |
| mutation: numbering gap / dangling citation | same | **caught** |
| lint | `.venv/bin/ruff check src tests` | All checks passed |
| types | `.venv/bin/mypy src/hamiltonian_lang` | no issues, 107 files (caught 1 real error) |
| **frozen core** | `git diff HEAD -- ast/ lexer/ parser/ backends/ reasoning/` | **empty** |

**Previously — 2026-08-10, the Semantic Firewall closeout (view, domain lattice, and the
two divergence repairs).** Executed, not estimated:

| check | exact command | result |
|---|---|---|
| conformance gate | `bash scripts/conformance.sh` | **CONFORMANCE: PASS**, all stages |
| full suite | `.venv/bin/python -m pytest` | **7248 passed**, 6 skipped, 7 xfailed, 7 xpassed, **0 failed** |
| semantic state | `pytest tests/semantic_state` | **266 passed** (was 62) |
| 30 acceptance fixtures vs frozen reference checker | `pytest tests/semantic_state/test_semantic_firewall_acceptance.py` | **30/30 verdict and error class, unchanged by the repairs** |
| neutral adapter round trip | same file | **30/30 byte-for-byte** |
| **HML view round trip** | `pytest tests/semantic_state/test_lossless_view.py` | **30/30 `parse(render(t)) == t`** on frozen dataclasses |
| **chained round trip** | same file | **30/30** corpus JSON → state → view → state → corpus JSON, byte-identical |
| **lattice vs frozen reference** | `test_the_lattice_agrees_with_the_frozen_reference_checker_on_every_pair` | **0 disagreements** over the full cross product of domain names |
| mutation check on the unfixtured rules | 5 rules disabled one at a time in `verify.py`, suite re-run | **5/5 caught**; `verify.py` restored, `git diff` empty |
| lint | `.venv/bin/ruff check src tests` | All checks passed |
| types | `.venv/bin/mypy src/hamiltonian_lang` | no issues in **107** source files |
| **frozen core** | `git diff HEAD -- ast/ lexer/ parser/ backends/ reasoning/` | **empty**, and asserted by `test_the_view_did_not_smuggle_in_new_syntax` |

The mutation check is recorded because the new rule tests passed on their first run, which
is not by itself evidence that they test anything. Disabling each rule in turn — the
constraint-subset check, "every branch CLOSED", branch-conclusion agreement, and both
directions of the scope discharge — made the corresponding test fail, and only then were
they treated as coverage.

**Previous run — 2026-08-09, the Gold-10 library closeout.** Executed, not estimated:

| check | exact command | result |
|---|---|---|
| conformance gate | `bash scripts/conformance.sh` | **CONFORMANCE: PASS**, exit 0, all 8 stages |
| full suite | `.venv/bin/python -m pytest` | **6981 passed**, 6 skipped, 7 xfailed, 7 xpassed, **0 failed** |
| library tests | `pytest tests/libraries` | **65 passed** |
| previous repair | `pytest tests/reasoning` | passes unchanged — underdetermination, UNKNOWN≠UNDERDETERMINED, forall rules, stale context, forged certificates |
| lint | `ruff check src tests` | All checks passed |
| types | `mypy src/hamiltonian_lang` | no issues in 101 source files |
| **kernel frozen** | `git diff 76b9989..HEAD -- kernel.py binders.py adjudication.py side_conditions.py refinement.py evidence.py partiality.py ast/ lexer/ parser/ backends/` | **empty** |
| new examples | `hml check` | G07 `1 PROVED`; G09 and G10 certificates VALID |

**Previous run — 2026-08-09, the Gold-10 core repair.** Executed, not estimated:

| check | exact command | result |
|---|---|---|
| conformance gate | `bash scripts/conformance.sh` | **CONFORMANCE: PASS**, exit 0, all 8 stages |
| full suite | `.venv/bin/python -m pytest` | **6765 passed**, 6 skipped, 7 xfailed, 7 xpassed, **0 failed** |
| new tests | the five new files | **80 passed, 1 skipped** |
| lint | `.venv/bin/ruff check src tests` | **All checks passed** |
| types | `.venv/bin/mypy src/hamiltonian_lang` | **no issues in 95 source files** |
| examples | `.venv/bin/hml check` over `examples/**` | all pass; the two new ones report `1 UNDERDETERMINED` and `2 VERIFIED / 1 PROVED` |
| IR schema | `jsonschema.validate` over every example | passes; `Evidence` and `UnderdeterminationClaim` added to `spec/ir.schema.json` after the gate caught their absence |
| binder numbering | `abstract()` vs the resolver's own parse | **5/5 shapes canonically identical** (flat, free constant, nested ∀∀, mixed ∀∃, second free var) |
| freeze gate | `tests/freeze` | fired as designed on the four new keywords and two new statement kinds; amended deliberately in the same change |

Two failures were found by the repo's own gates and fixed: `mypy` on the structural binder
rebuild, and the IR schema, which did not know the two new statement kinds. A third, the
golden tripwire, correctly refused the two new examples until they were blessed.

**Previous run — 2026-08-08, the Representation Arena commit.** Executed, not estimated:

| check | exact command | result |
|---|---|---|
| full suite | `.venv/bin/python -m pytest -q` | **6442 passed**, 5 skipped, 7 xfailed, 7 xpassed, **0 failed** |
| arena tests | `.venv/bin/python -m pytest -q tests/arena` | **100 passed**, exit 0 |
| arena pre-flight gate | `.venv/bin/python -m evaluation.arena.validate` | **exit 0, all 8 checks PASS** — 306 items, 69 pairs |
| arena lint | `.venv/bin/ruff check evaluation/arena tests/arena` | **All checks passed** |
| representation parity | 600 worlds x 3 arms | **1800 round trips, 0 failures** |
| HML arm compiles | 214 worlds, real compiler, inside the gate | **214/214** |

Baseline immediately before the arena was 6342 passed; the delta is exactly the 100 new
tests. Arena prompt budget (`cl100k_base`, 306 items): SE **328.8** mean tokens, HML
**338.0**, AST **576.3** — SE and HML within 2.8%, the AST control 1.75x the shortest arm.

`ruff format` was **not** run and is not claimed: the repository is not format-clean (146 of
220 files would be reformatted), so reformatting only the new files would make them
inconsistent with the tree.

**Earlier run — the repaired model-visible view, 2026-08-06.** Every number below was
executed, not estimated:

| check | result |
|---|---|
| `pytest` (full suite) | **5300 passed**, 4 skipped, 7 xfailed, 7 xpassed |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS** |
| `ruff check src tests evaluation/` | **All checks passed** |
| `mypy src` | **Success: no issues found in 84 source files** |
| view-only reconstruction (**the admission gate**) | **8/8 exact** |
| every emitted statement present exactly once | **8/8** |
| A/B/C/D surface round-trips | **32/32 exact** |
| reference self-score | **8/8** |
| `audit_task` admission | **8/8 admissible, 0 defects** |
| ACQ0 / H2 view separation | 8/8, `assert_views_distinct` raised nothing |
| model-safe bundle leak scan | 8/8 clean |
| `tests/evaluation/test_acq0_view_reconstruction.py` | 50 passed, incl. 9 negative controls |

The negative controls matter more than the pass counts: the gate is asserted to **fail** on
a removed statement, a swapped order, a swapped `assume`/`require` role, a dropped dimension
check, an emitted derived fact, an invented goal, and a missing initialiser, body or
codomain. Each is a defect that actually occurred or a near neighbour of one.

Commands executed and their real results (historical, cumulative):

| command | result |
|---------|--------|
| `.venv/bin/python -m pytest -n 18` | **3974 passed, 4 skipped, 1 xfailed** (was 1531) |
| `./scripts/conformance.sh` | **PASS without override** (all four V1 agents integrated) |
| `evaluation.analyse --generation 0` | 105/105 cells; all arms 93.3% except C 86.7% |
| `.venv/bin/hml check examples/*/*.hml` | **8/8 check cleanly** |
| `pytest tests/golden/test_examples_compile.py` | **23 passed** — recursive example gate |
| Ollama concurrency probe, stock `-np 1` | 23 tok/s at 1, 2, 4 and 6 workers — fully serialised |
| Ollama concurrency probe, `-np 4` | 22.8 / 35.1 / **47.4** / 32.7 tok/s at 1 / 2 / **4** / 8 workers |
| curriculum probe, `prompt_eval_count` | 0/5/10/25/50 demos = 66/643/1286/2967/**5893** tokens; all fit the 8192 slot |
| `pytest tests/freeze/test_syntax_gate_freeze.py` | **22 passed, 1 skipped** |
| `python -m evaluation.syntax_gate_freeze --verify` | correctly reports nothing frozen yet, exit 1 |
| four-surface hash round-trip | **MATCH on all 4 candidates x 4 examples** |
| `pytest tests/freeze` | 75 passed (52 quarantine + 23 freeze tooling) |
| `.venv/bin/ruff check src tests` | **All checks passed** |
| `.venv/bin/mypy src/hamiltonian_lang` | **Success: no issues found in 22 source files** |
| `experiments/alphabet/tokenisation_benchmark.py` | ran; 8 tokenisers real, Llama-3 gated and excluded |
| `./scripts/conformance.sh` | **CONFORMANCE: PASS** (all 8 stages) |

Test breakdown: backends 292 · golden 84 · adversarial 71 · roundtrip 65 · type_system 39 ·
parser 37 · semantics 21.

Property-based tests (hypothesis) cover alpha-renaming invariance and inconsistent-rename
detection, parameterised over **every** binder form with a companion test asserting each
template actually compiles. This followed D-018: the earlier generator was green while the
property it asserted was false, because it never produced `def` parameters.

## Known Failures and Limitations

**Representation Arena — what it does not establish.**

- **Zero model calls. Nothing in the arena is evidence about any model's behaviour.**
- **HML has no uninterpreted predicate.** A declared `Predicate` is not callable
  (`HML-T470`); the only callable form requires a body. A finite relation can therefore only
  be stated in closed form, which forced all three arms to state it once in their own idiom
  rather than by enumeration. An ontology gap independent of the arena.
- **The AST control carries a length penalty** — 576 mean tokens against SE 329 and HML 338.
  An HML > AST result therefore cannot yet be attributed entirely to HML semantics.
- **The HML renderer had a latent semantic defect caught only by parity.** A relativised
  nested quantifier parsed and meant the right thing solely because `implies` is
  right-associative; nested quantifiers are now bracketed. Compiling was not sufficient to
  detect it.
- **`MIXED_STATE_COMPOSITION` is not ported**, and next-action covers two families rather
  than three. All three ported families sit inside HML's covered ontology region, so the
  handoff's structural tension — the families where the tested model is weak are the
  families where HML's coverage is near zero — is untouched.
- **`OPERAND_ORDER` contrast twins have answers that are exact negations** of each other.
  Not exploitable within an independently scored item, but a corpus-level analysis should
  know it.

- **The Semantic Firewall acceptance set cannot detect either divergence that was just
  repaired.** Every fixture declares the domain its claim already has, so `==` and a
  containment walk agree on all 30; every fixture's premise envelope already equals its
  dependency list, so a subset test and exact equality agree on all 30. Both defects were
  real, both were invisible, and both were found by reading the reference checker's source
  rather than by any test. Until the corpus adds fixtures that distinguish them, the only
  thing standing between a regression and silence is a differential test in this repository
  against a file this repository does not own.
- **The domain lattice has no fixture support whatsoever.** No fixture exercises a proper
  subtype relation. It is justified by the reference checker's source, which is a weaker
  warrant than a passing fixture.
- **The rules no fixture reaches are tested only by tests written alongside the code they
  check.** SF-R06's `UNVERIFIED`/`REJECTED` states, the constraint-subset rule, branch
  closure, branch-conclusion agreement and the scope-discharge path now have coverage, and
  each was mutation-checked. That establishes the tests bite. It does not make them external
  acceptance criteria, and they should not be cited as such.
- **The lossless view proves representability, not adequacy.** That a transition renders and
  reads back says the fields survive a round trip. It says nothing about whether the view is
  a *good* rendering for a human or a model to reason through, and nothing here was measured
  against either.
- **The ACQ0 instrument has now failed its own audit twice.** v1 was 0/41 admissible
  because the mathematics was authored in three places and disagreed. v2 was built to
  remove that failure mode and still shipped a model-visible view from which three of eight
  tasks could not be encoded, plus a fourth whose `check dimension` statement appeared in no
  model-visible artefact. The lesson is specific and unresolved in general: **three separate
  "verifications" all validated an artefact against itself.** Only a check that crosses the
  boundary where information is lost can detect that class of defect.
- **No model has seen any v2 task.** Every property recorded for v2 is a property of the
  instrument, not an observation about model behaviour.
- **The partiality guard is narrow and fails closed.** The compiler generates no definedness
  obligation over a binder's declared domain, so admission rejects division by a **bare
  binder** only. Compound denominators, `sqrt`, `log`, negative or fractional powers,
  indexing, and partiality reachable through a chain of definitions are **not** detected.
  `v2_dimensional_algebra_001` divided by a module-level `var`, which sits outside that
  reach entirely; it was replaced rather than guarded, because `require area != 0` does not
  compile (HML-D502 — a `Quantity[Length^2]` is not comparable to a dimensionless `0`).
- **HML has no absolute-value form**, so a two-sided bound must be written as two explicit
  inequalities. `v2_approximation_equality_001` stated one and was therefore satisfiable by
  an estimate arbitrarily far below the target.
- **The pilot found no representation advantage *on a saturated benchmark*.** Every paired
  contrast was exactly zero with zero discordant pairs — but 14 of 15 problems were solved
  by nearly every arm, so the design could not have detected an effect of realistic size.
  This is not evidence of absence. Encoding fidelity was 0.648 and 27–50% of encodings did
  not compile.
- **Two blocking gates precede any HML-EVAL-002 reasoning result:** parse success ≥95%
  after at most one repair with ≥90% semantic preservation, and a benchmark of ≥200
  problems at 40–70% baseline accuracy.
- **Phase 5 is partly blocked:** only `gemma4:31b` is installed; the 7–14B non-reasoning
  arm needs a model download.
- **Phase 6 is blocked:** no training stack exists (torch, transformers, peft, datasets,
  trl, accelerate all absent). Recorded as blocked, not dropped.
- **The pilot was underpowered.** 14 of 15 problems were answered correctly by every arm;
  the design could only detect an effect of roughly 33 percentage points. The zero
  differences are not evidence that no difference exists.
- **The one positive signal:** compiler feedback raised encoding fidelity by +0.065
  (CI [0.006, 0.136]) and parse rate by 12–43 points across both generations, at +38%
  generated tokens. It did not change answer accuracy at all.
- **Round trips now measured, not assumed** (HML-EVAL-001 §9). Four routes implemented
  with explicitly declared narrow subsets: canonical IR (5/5 in-subset fixtures preserve
  the content hash), graph triples (2/2), Stan (2/2), Lean statement subset (2/2). What
  the measurement revealed matters more than the pass counts:
  - **Stan cannot express strict positivity.** `real<lower=0>` admits 0; `PositiveReal`
    does not. Every family with a `PositiveReal` role — Normal, Beta, Gamma, Exponential,
    Poisson, Cauchy and most others — therefore cannot round-trip at all. Only Uniform,
    Binomial and Bernoulli can.
  - **Stan loses observed values** (data comes from a data file, not the program text)
    and **destroys interleaved declaration order** (block structure), which changes the
    content hash because ordinals are positional.
  - **The Lean route silently loses probability laws**, and the reconstruction compiles
    perfectly happily. Only the content-hash comparison detects it. A one-way test cannot
    detect this class of loss at all.
- **`BackendResult.faithful` means "declared no per-construct loss", not "round-trips".**
  `english`, `json`, `graph` and `triples` report `faithful=True` while being one-way.
- **Every recorded benchmark number is a deterministic compiler property.** None is a
  model-performance observation.
- **No structural novelty was found in Layer 2.** Wave 1 prior-art review identified prior
  implementations of every representational claim. See D-012.
- **Provenance is not implemented** (D-011). The IR carries spans and types only.
  `GOAL.md` §5 originally claimed otherwise and has been corrected in place.
- Proof obligations are collected and, apart from dimensional checks, **not discharged**.
  This is by design; v0 proves nothing.
- Role-label discipline applies to `DistExpr` only, not to ordinary `Call`s (Q-05).
- The freeze document previously claimed the sd-vs-variance ambiguity "cannot be
  expressed". That was false as written: the *grammar* admits
  `Normal(location := mu, variance := s)` and the *type system* rejects it. Corrected
  (D-014).
- Statement order affects declaration ordinals, so reordering differently-typed
  declarations changes the content hash. Whether this is right is unresolved.

## Risks and Technical Debt

- **Out-of-distribution confound** — arms A–D are saturated in model pretraining; arm E has
  effectively zero tokens. This may dominate every comparison. Now recorded as falsification
  condition 6 in `GOAL.md`.
- **Published evidence points the other way** — Tam et al. (EMNLP 2024) report reasoning
  degradation under format restriction. Now recorded as falsification condition 7.
- **Scaffolding confound** — if English plus structural prompting closes the gap, the win
  is prompting, not representation.
- **D-006 (shadowing as an error) may be too strict** for practical authoring.
- **OpenMath IPR status is unresolved** (Q-03), blocking the highest-value reuse option.
- **The strongest argument against the project**, adopted rather than rebutted: the
  inference the thesis wants to eliminate happens when the file is *written*, not read.
  Someone had to decide `jitter` is a scale before `scale := jitter` could be typed. A
  correct-looking encoding of a misunderstanding compiles clean and is wrong. Reviewer's
  ESTIMATE: arm A' (prose + matched checklist) closes most of the gap.
- **One confound is not resolvable**: "structured formal notation helps" cannot be
  separated from "*this* notation helps", because Lean and Stan are far better represented
  in pretraining than a language invented weeks ago.

## Current Blockers

- **No official human review has happened.** `INDEPENDENT_SEMANTIC_REVIEW` is two
  read-only agent reviews, and is labelled as such. It clears the developmental screen; it
  does not clear a promotion benchmark.
- Q-03 (OpenMath licensing) blocks a reuse decision, not the build.

## Exact Next Actions

**LIVE: hand the Semantic Firewall closeout to Codex and stop.** Codex owns the corpus,
repins `hml_core`, and reruns the same frozen 30 acceptance fixtures against the pinned
implementation. Do not modify the corpus repository, the fixtures, or the frozen reference
checker from here. Handoff: `docs/agent_handoffs/CLAUDE_SEMANTIC_FIREWALL_CLOSEOUT.md`.

Three items in that handoff need a corpus-side decision and cannot be settled here:

1. **The two divergence repairs.** Both were found by reading `reference_checker.py`, not by
   a failing fixture, and neither changes any of the 30 verdicts. Codex should decide whether
   the acceptance set should grow a fixture that distinguishes them — a `Natural`/`Integer`
   subtype case and a premise-subset case — since at present nothing external would catch a
   regression in either.
2. **`output_domain` is checked here and nowhere in the reference.** Either the reference has
   a gap or this implementation is over-strict. That is a corpus judgement.
3. **`HML_OBF` should be withdrawn as evidence for H2** until re-run with the question text
   held fixed. Raised in the previous handoff and still open; it remains the only positive
   signature for the familiarity hypothesis and the stated justification for the LoRA
   experiment. No frozen artifact was modified.

---

**Superseded: hand `2af4998` to Codex and stop.** Codex owns the corpus, repins, and reruns
the same frozen 23 transitions to judge `23/23 HANDLED · CoreGapRate 0 · AdapterGapRate 0 ·
LibraryBlockedRate 0 · RegressionRate 0`. Only Codex may recommend Gold-100. Handoff:
`docs/agent_handoffs/CLAUDE_GOLD10_LIBRARY_CLOSEOUT.md`.

Expected effect on the four blocked transitions, as predictions to be checked:

| transition | expected |
|---|---|
| G07:a1 | **unblocked** — `add_zero` supplies the body, unchanged `forall_intro` generalises |
| G09:a0 | **unblocked, conditional on rendering** — needs Event-typed operands (`rv` declarations) and `P(A) > 0` in Γ. The one place a rendering choice, not a capability, decides the outcome. |
| G10:a1 | **unblocked** given `x != 0` in Γ |
| G10:a2 | already independently checked; unchanged |

Deferred, each needing a separate decision: e-graphs (recorded as a possible future
*backend*, not an architecture change), the chain rule, measure-theoretic probability,
Bayes, distributions, integration, a third repository for the libraries, Gold-100, and the
matched learning-curve experiment (training, still blocked).

---

**Superseded: hand the core-repair SHA to Codex.** The Gold-10 core repair is complete and
the workflow is explicitly sequential — Codex owns the corpus, repins `hml_core`, and
reruns the *same* Gold-10. Do not rerun Gold-10 here, do not modify the corpus repository,
and do not proceed to Gold-100 until the unchanged Gold-10 rerun shows the classifications
are stable. Handoff: `docs/agent_handoffs/CLAUDE_GOLD10_CORE_REPAIR.md`.

Expected corpus effect, stated as a prediction to be checked rather than a result:

| gap | expected after this change |
|---|---|
| GAP-0003 | **closed in core.** Certified underdetermination is expressible and enforced. |
| GAP-0004 | **core closed; G07's body still library-level.** The quantifier rules exist and are checked; `n + 0 = n` needs an algebra theorem this change deliberately did not add. |
| GAP-0001 | **exposable now** via `closed_eval_v1`, without a corpus schema change. |
| GAP-0002 | **exposable now** via `definition_unfold_v1`, which records the definitions it unfolded. |
| GAP-0005 / GAP-0006 | **remain library-level.** Probability and calculus are unchanged and out of scope by decision. |

Deferred and *not* started, each needing a separate decision: the probability-law library,
the calculus library, existential intro/elim, and the matched learning-curve experiment
(SE-LoRA vs HML-LoRA vs S-expression-LoRA) which is training and remains blocked.

---

**The signal pivot supersedes the ordering below.** Broad compiler completion is
deliberately not resumed. The live sequence is:

0. **Acquisition sanity check, then the Endpoint-B pilot.** The organism is frozen. Run 6 literal state-recovery items per arm on ACQUISITION seeds; require >=5/6 for AST and for HML before any pilot. Then 12 fresh PILOT pairs, SE/AST/HML.
1. ~~Find difficulty other than model size.~~ Superseded for this organism, but still open for the endpoint: Endpoint B at L3
   is saturated at 8B, so the pilot cannot run there. Re-screen SE-only at **L5**, then L7
   if needed, looking for a level where `gemma4:e4b` lands in 30–70% pair both-correct.
   Endpoint A (next-action) is the other candidate for headroom and has never been run
   against any model. Both are cheap: a 6-pair micro-screen is 12 calls and ~3 minutes.
1. ~~SE-only developmental model **size** search.~~ **CLOSED by rule.** Two candidates
   consumed: `gemma4:12b` (screen void — instrument failure, not a verdict on the model)
   and `gemma4:e4b` (6/6 pairs, too strong). `gemma4:e2b` deliberately not tried. The
   constraint that a model be chosen on structured English alone still holds for any future
   screen.
2. **Freeze** model, digest, runtime, instructions, endpoint implementation, generator and
   scorer versions. Generate a fresh held-out seed set.
3. **Acquisition sanity check** — 6 literal state-recovery items per structured arm,
   requiring no reasoning, on throwaway seeds. Require ≥5/6 for AST and for HML, so that
   unfamiliar syntax is not mistaken for a bad reasoning representation.
4. **First Endpoint-B representation pilot** — 12 fresh contrast pairs, SE/AST/HML, fresh
   context per item, deterministic order. No significance claims at N=12.
5. **Endpoint A only if B is non-degenerate.**

The AST length confound (576 vs 329/338 tokens) is recorded and deliberately not yet fixed:
an HML > AST result cannot be attributed entirely to HML semantics until a more compact
neutral control exists. No representation may be truncated to force equal length.

The pre-pivot backlog, retained for the record and **not** currently active:

0. **HML V2 phase II — close the 11 critical coverage zeros.** Expectation as an
   expression, conditional and joint probability, independence, set membership and
   comprehension, limit/derivative/integral/continuity, causal vs associational
   relations. Then rerun the 486-atom capability audit **unchanged** (do not edit the
   ontology) and report BEFORE/AFTER for critical coverage, critical zeros,
   compositional closure, transformation representability and backend silent loss.
   Do not run any HML-vs-English model experiment until V2 is frozen: V1 and V2
   conclusions must not be mixed.

1. **The decisive run, in this order and no other.** (a) 8-call operational probe on the
   largest-envelope and hardest predicted tasks; (b) **SE arm on all valid tasks as the
   headroom gate** — 8–16 of 24 correct is ideal, 6–18 usable, 0–5 or 19–24 insufficient;
   (c) HML-V1 only if the gate passes; (d) paired McNemar + bootstrap; (e) two read-only
   falsification reviewers; (f) `DECISION.json`. The prompt budget re-measurement against
   the frozen runtime is **done** — it is `2 x 16384`, recorded in
   `evaluation/results/v1_benchmark/ENVELOPE_CALIBRATION.json`.

1. Decide the D-003 cost/benefit question now that the token cost is measured at ~5.9%
   (D-014): is the explicitness worth it? This is H5 and is still open.
2. Build the scaffolding-ablation arm **first**, since it is the arm most likely to
   falsify the thesis.
3. Decide Q-05 (role labels on ordinary calls).
4. Run the morphology analysis — deferred in session 1 and a prerequisite for H6.
5. Work through the remaining findings in `audits/RED_TEAM_REPORT.md` that were not
   resolved in session 1.
7. **V1, in order:** redesign the corpus to a 50–60% baseline (n ≥ 60); raise the
   Hamiltonian parse rate to ≥ 90% — **a hard gate, since a language the model cannot
   write is not being tested**; then implement L4 epistemic first, because it has the
   clearest correctness claim and the strictest kill criterion.
6. **Cheapest high-value step, no model needed:** demonstrate HML → Stan → HML and
   HML → Lean → HML preserving the content hash, or characterise exactly where it fails.
   The only round trip verified today is HML → HML, which is the one that cannot lose
   anything.
