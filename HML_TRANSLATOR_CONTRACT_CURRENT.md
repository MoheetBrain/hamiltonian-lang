# HML TRANSLATOR CONTRACT — CURRENT FROZEN RELEASE

**Authoritative for:** tag `hml-semantic-pre-gemma-v1`
**HML SHA:** `84bf9897689b0ed78a2caaefc1db850d49b81260`
**Corpus SHA:** `9d67e54450b9db897ee2ed20ec2e4cbbc16a3780`
**Neutral schema version:** `semantic-firewall-case-0.1.0` (the ONLY supported value)

Everything below was read out of the frozen implementation at that SHA, not from
recollection. Where a rule is stated, the file that enforces it is named. If this document
and the source ever disagree, **the source wins and this document is wrong** — re-derive it.

> **Scope of this document.** It tells you how to turn a worked mathematical solution into
> (1) a representation-neutral canonical trajectory, (2) valid current HML, (3) a matched
> AST. It does not authorise changing HML. HML is frozen and read-only.

---

## 0. AUTHORITATIVE FILES

| Rule area | File (under `src/hamiltonian_lang/semantic_state/`) |
|---|---|
| Record shapes, enums, lifecycle table | `model.py` |
| All eleven invariants, verdicts, trust seam | `verify.py` |
| JSON import/export, boundary refusals | `neutral.py` |
| HML surface grammar, render + parse | `view.py` |
| Attestations, trust modes | `trust.py` |
| Domain lattice, `inhabits` | `domains.py` |

Corpus-side (read-only, Codex-owned):
`experiments/semantic_firewall/schemas/semantic_case.schema.json`,
`experiments/semantic_firewall_v2/schemas/semantic_case_v2.schema.json`,
`data/derived/gold125_ontology_v1/` (canonical trajectory precedent),
`schemas/reasoning_operation_registry_gold125_v1.json` (operation vocabulary precedent).

---

## 1. THE THREE LAYERS, AND WHICH IS THE TRUTH

```
WORKED SOLUTION  (prose, untrusted)
        │  human/model translation  ← the lossy step; everything else is mechanical
        ▼
CANONICAL TRAJECTORY  (representation-neutral)   ← THE TRUTH
        │  deterministic rendering
        ├──────────────► HML view      (view.py render_transition)
        ├──────────────► neutral JSON  (neutral.py export_transition)
        └──────────────► matched AST   (experiment-side, see §17)
```

**The canonical record is the truth. HML is a rendering of it.** Never author HML first and
back-derive the canonical record: the renderings must be provably the same object, and that
property is only checkable if one artefact is primary.

---

## 2. EXACT STATE SCHEMA (`model.py`)

`SemanticState` has exactly six fields. Dictionary **keys** are the citable identifiers.

```python
SemanticState:
    claims:        dict[str, Claim]        = {}
    candidates:    dict[str, Candidate]    = {}
    branches:      dict[str, Branch]       = {}
    goals:         dict[str, Goal]         = {}
    obligations:   dict[str, Obligation]   = {}
    active_scopes: tuple[str, ...]         = ("global",)
```

### 2.1 Records — every field, every default

```python
Claim:
    id: str
    proposition: str
    status: ClaimStatus = GIVEN
    scope: str = "global"
    domain: str | None = None
    dependencies: tuple[str, ...] = ()

Candidate:
    id: str
    proposition: str
    status: CandidateStatus = PROPOSED
    scope: str = "global"
    constraint_ids: tuple[str, ...] = ()
    origin: str | None = None
    dependencies: tuple[str, ...] = ()
    evidence_id: str | None = None
    verification_result: str | None = None

Branch:
    id: str
    predicate: str                      # NOTE: `predicate`, NOT `proposition`
    status: BranchStatus = OPEN
    scope: str = "global"
    conclusion: str | None = None
    partition_id: str | None = None

Goal:
    id: str
    proposition: str
    status: GoalStatus = OPEN
    scope: str = "global"

Obligation:
    id: str
    proposition: str
    status: ObligationState = OPEN
    mandatory: bool = True
    origin: str | None = None
    dependencies: tuple[str, ...] = ()
    discharge_evidence_id: str | None = None

EvidenceRecord:
    id: str
    kind: str
    status: str = "UNKNOWN"             # free string, NOT an enum
    trusted: bool = False               # NEVER read as authority (see §11)
    supports_rule: str | None = None
    premise_ids: tuple[str, ...] = ()
    payload: dict[str, Any] = {}
```

### 2.2 THE KEY-vs-`id` RULE (D-053) — read this twice

The dictionary key and `record.id` are permitted to differ, and **an action always cites the
KEY, never `record.id`**. The exporter preserves the key. Do not "helpfully" normalise them.
Enforced in `neutral.py`; pinned by tests.

**Translator rule: set `id` equal to the key. Do not exercise the freedom to differ.**

---

## 3. STATUSES — the complete closed sets (`model.py`)

Anything outside these sets is **refused at the import boundary** with `NeutralImportError`.
That includes case and whitespace variants: `"open"` and `"DISCHARGED "` are both refused.

| Record | Enum | Permitted values |
|---|---|---|
| Claim | `ClaimStatus` | `GIVEN` `ASSUMED` `DERIVED` `VERIFIED` `REFUTED` `UNRESOLVED` `UNKNOWN` |
| Candidate | `CandidateStatus` | `PROPOSED` `UNVERIFIED` `VERIFIED` `REJECTED` `UNKNOWN` |
| Branch | `BranchStatus` | `OPEN` `CLOSED` `JOINED` `ABANDONED` `UNKNOWN` |
| Obligation | `ObligationState` | `OPEN` `DISCHARGED` `FAILED` `UNKNOWN` |
| Goal | `GoalStatus` | `OPEN` `DISCHARGED` `UNKNOWN` — **only three** |
| Verdict | `Verdict` | `VALID` `INVALID` `UNRESOLVED` |

`EvidenceRecord.status` is a **free string**, not an enum. The corpus uses `VALID`,
`REFUTED`, `UNKNOWN`. Only `UNKNOWN` and `VALID` have defined meaning to the verifier
(§11); anything else is simply "not VALID".

### 3.1 Candidate lifecycle — the ONLY transition table in the model

```
PROPOSED   → {UNVERIFIED, VERIFIED, REJECTED}
UNVERIFIED → {VERIFIED, REJECTED}
VERIFIED   → {}        terminal
REJECTED   → {}        terminal — a rejected candidate can never be reopened
UNKNOWN    → {}        terminal
```

There is **no transition table for claims, branches, goals or obligations**. Backwards moves
on those are refused by the frame condition instead (§9), because they are undeclared
mutations.

### 3.2 `GoalStatus` export gap — a real, current defect you must work around

`GoalStatus` exists in `model.py` but is **missing from
`hamiltonian_lang.semantic_state.__all__`**. `from hamiltonian_lang.semantic_state import
GoalStatus` **fails**. Import it directly:

```python
from hamiltonian_lang.semantic_state.model import GoalStatus
```

This is a packaging omission introduced with D-059, not a semantic issue — no verdict
depends on it. It is documented rather than fixed because the release is frozen.

---

## 4. EXACT ACTION SCHEMA (`model.py`)

```python
Action:
    id: str
    operation: str                                   # DESCRIPTIVE at runtime — see §5
    summary: str = ""                                # SEMANTIC: goal-discharge compares it
    output_id: str | None = None                     # licenses exactly ONE new claim
    dependencies: tuple[str, ...] = ()               # the premises cited, by KEY
    preconditions: tuple[dict, ...] = ()
    obligations_created: tuple[dict, ...] = ()
    obligations_discharged: tuple[dict, ...] = ()
    typing: dict = {}
    warrant: dict = {}
    goal_effect: dict = {}
    scope_effect: dict = {}
    branch_effect: dict = {}
    candidate_effect: dict = {}
    epistemic_effect: dict = {}
```

### 4.1 The five typed effect channels — exact keys the verifier reads

These are the **only** keys `verify.py` consults. Extra keys are carried through the round
trip but are inert.

| Channel | Keys read | Licenses changes to |
|---|---|---|
| `goal_effect` | `goal_id`, `kind` | `goals[goal_id]` |
| `scope_effect` | `kind`, `discharge_evidence_id` | `claims` (any, when `kind` ∉ {None,"NONE"}) |
| `branch_effect` | `branch_ids`, `kind`, `coverage_evidence_id`, `rule` | `branches[b]` for each id |
| `candidate_effect` | `candidate_id`, `kind`, `evidence_id`, `rule` | `candidates[candidate_id]` |
| `epistemic_effect` | `to_status`, `evidence_id`, `rule`, `claim_id` | **nothing** — see §4.3 |
| `typing` | `input_domains` (map key→domain), `output_domain` | — |
| `warrant` | `evidence_id`, `rule` | — |

Discriminating `kind` values the verifier tests literally:
`branch_effect.kind == "JOIN"`, `candidate_effect.kind == "PROMOTE"`,
`goal_effect.kind == "DISCHARGE"`, `scope_effect.kind` ∉ {`None`,`"NONE"`}.

### 4.2 Sub-record shapes

```jsonc
preconditions:            [{"id": "...", "statement": "...", "status": "SATISFIED",
                            "evidence_id": "..."}]     // evidence_id optional
obligations_created:      [{"id": "...", "statement": "..."}]
obligations_discharged:   [{"id": "...", "evidence_id": "..."}]   // or a bare id string
typing:                   {"input_domains": {"<claim key>": "<Domain>"},
                           "output_domain": "<Domain>"}
warrant:                  {"evidence_id": "...", "rule": "...", "premise_ids": [...]}
```

`obligations_discharged` accepts a bare string id **or** an object. Prefer the object form so
you can attach evidence.

### 4.3 In-place claim mutation is INTENTIONALLY UNREPRESENTABLE

`epistemic_effect` licenses **no** frame change (see `_licensed_change` in `verify.py`). You
cannot raise an existing claim's status in place. Epistemic promotion applies to the claim
the action **produces** (`output_id`). All thirty frozen fixtures use that shape.

This is the immutability discipline recorded in D-058: to strengthen a fact, **derive a new
claim** whose `dependencies` cite the old one. Deleting, restatusing or rewriting an existing
claim all return `INVALID`.

---

## 5. OPERATION vs EFFECT — semantic or descriptive?

| Field | Status |
|---|---|
| `action.operation` | **DESCRIPTIVE at RUNTIME.** Provenance only. |
| `action.operation` | **SEMANTIC in OFFLINE_REPLAY** — it is the fallback evidence-rule name. |
| `action.summary` | **SEMANTIC** — `_check_goal_discharge` compares it to the produced claim's proposition. |
| the five `*_effect` channels | **SEMANTIC** in both modes. |
| `evidence.trusted` | **NEVER authority.** Inert flag. |

This is P-01 / D-054. Measured: six different `operation` labels over an otherwise identical
transition produce **one** runtime verdict. Justified by LeanDojo: MI(tactic head; state
effect) / H(head) = 0.240 — a name carries ~24% of the information about what it does.

**Translator rule: never encode meaning in `operation` alone. Always state the typed
effect.** If you are writing for RUNTIME, an effect that omits its explicit `rule` gets **no**
fallback and the transition is refused.

There is **no closed operation vocabulary** in the frozen implementation. `operation` is a
free string. The Gold-125 registry's 19 `core_operation` values (`TRANSFORM`, `EVALUATE`,
`APPLY_THEOREM`, `APPLY_DEFINITION`, `CASE_SPLIT`, `SUBSTITUTE`, `COUNT`, `BOUND`, `SELECT`,
`VERIFY`, `CONTRADICTION`, `DISCHARGE`, `ENUMERATE`, `CONSTRUCT`, `MODEL`, `INDUCT`,
`DECLARE`, `RECORD`, `UNRESOLVED`) are **corpus precedent, not a constraint**. Reuse them for
consistency; the verifier does not check them.

---

## 6. THE ELEVEN INVARIANTS AND THEIR ERROR CLASSES (`verify.py`)

Checked in this order; the first finding claims the error class. `FRAME` runs **last** so a
more specific invariant reports first.

| # | Family | Error class emitted |
|---|---|---|
| 1 | `DEPENDENCY` | `DEPENDENCY_VIOLATION` |
| 2 | `SCOPE` | `SCOPE_LEAK` |
| 3 | `PRECONDITIONS` | `PRECONDITION_VIOLATION` |
| 4 | `OBLIGATIONS` | `OBLIGATION_DROP` |
| 5 | `CANDIDATES` | `CANDIDATE_PROMOTION` |
| 6 | `BRANCH_JOIN` | `INVALID_BRANCH_JOIN` |
| 7 | `WARRANT` | `WARRANT_MISMATCH` |
| 8 | `EPISTEMIC_STATUS` | `EPISTEMIC_PROMOTION` |
| 9 | `GOAL_DISCHARGE` | `FALSE_GOAL_DISCHARGE` |
| 10 | `TYPE_DOMAIN` | `TYPE_OR_DOMAIN_MISMATCH` |
| 11 | `FRAME` | `DEPENDENCY_VIOLATION` (deliberately shares the reference's class) |

> **`model.ErrorClass` is a DEAD enum.** It lists `MISSING_DEPENDENCY`, `SCOPE_VIOLATION`
> etc. — **seven of its ten members are never emitted**, and seven of the ten classes above
> are absent from it. Nothing reads it. **Match on the strings in the table above**, never on
> `ErrorClass`. Documented, deliberately unfixed, frozen.

---

## 7. VERDICTS AND UNKNOWN HANDLING

Three verdicts: `VALID`, `INVALID`, `UNRESOLVED`.

**`UNRESOLVED` is not a weak `INVALID`.** It means legality could not be determined because
something the action depends on is itself unknown. It is counted as **neither accepted nor
detected**. Unknowns are collected **first** and short-circuit the whole transition before any
invariant runs.

### 7.1 What counts as an unknown — and the relevance rule (D-049)

Only records the action **actually consults** are examined. An unrelated `UNKNOWN` record
does not disable the verifier. Measured: unscoped, one junk `UNKNOWN` claim turned all ten
ILLEGAL fixtures from `INVALID` to `UNRESOLVED` — a total detection bypass.

Relevance sets, from `_relevant()`:

- **claims**: `action.dependencies` ∪ `{output_id}` ∪ keys of `typing.input_domains`
- **candidates**: `{candidate_effect.candidate_id}`
- **branches**: `branch_effect.branch_ids`
- **goals**: `{goal_effect.goal_id}`
- **obligations**: ids in `obligations_discharged`
- **evidence**: every cited evidence id, from any channel, plus per-obligation and
  per-precondition `evidence_id`

An unknown is raised when a **relevant** record has `status == "UNKNOWN"`, or a claim has
`domain == "UNKNOWN"` or `scope == "UNKNOWN"`, or a branch has `conclusion == "UNKNOWN"`, or
a precondition has `status == "UNKNOWN"`, or a cited evidence record has `status ==
"UNKNOWN"`. An **absent** (`None`) domain on a claim the action types is also collected — as
"not declared", not as a mismatch.

**Translator rule: if the source genuinely does not say, write `UNKNOWN`. Do not guess.**
An honest `UNRESOLVED` is a correct outcome. A guessed `VALID` is data corruption.

---

## 8. RULE-BY-RULE REFERENCE

### 8.1 DEPENDENCY
Every id in `action.dependencies` must exist in `state_before.claims` (by **key**). The
produced claim's own `dependencies` must match the action's — ancestry may not drift, and the
check is not a subset test.

### 8.2 SCOPE
- A premise in a scope not in `active_scopes` may not be cited.
- A conclusion may not be written into an inactive scope.
- **A conclusion may not be wider than the narrowest premise it rests on.**
- Containment is read off the **scope tree**, not off position in `active_scopes` (D-053).
  `active_scopes` answers "is this frame open?" only.
- A repeated entry in `active_scopes` is refused outright.
- Escaping a frame requires an explicit `scope_effect.kind == "DISCHARGE"`; any other kind
  does not license an escape.
- The scope tree is cycle-guarded; a cyclic tree terminates rather than hanging.

### 8.3 PRECONDITIONS
Accepted statuses: **`SATISFIED`, `DEFERRED`, `DEFERRED_AS_OBLIGATION`**. Anything else
refuses — that is what fail-closed means here. `UNKNOWN` never reaches this check; it was
already collected and made the transition `UNRESOLVED`.

`DEFERRED` means the debt becomes explicit — pair it with an obligation.

### 8.4 OBLIGATIONS
- Every obligation in `obligations_created` must be present in `state_after.obligations`.
- An obligation named in `obligations_discharged` must actually be `DISCHARGED` in
  `state_after`, or the transition is `INVALID` (`OBLIGATION_DROP`).
- **If a discharge cites evidence** — from the action entry's `evidence_id` or the record's
  `discharge_evidence_id` — that evidence must exist and pass the authority seam (D-060).
- **Evidence is NOT required.** A discharge naming no evidence is accepted. 486 of 487 corpus
  discharges name none. **Known limitation, stated so you do not mistake it for a guarantee.**

### 8.5 CANDIDATES
- Identity must survive: the candidate must exist in **both** states.
- The lifecycle table (§3.1) is enforced.
- On `kind == "PROMOTE"`: promotion evidence must exist, pass the authority seam, and
  `supports_rule` must match the rule being applied.
- **Every original constraint is re-checked at promotion.** Promotion is verifier-owned.
- The promotion evidence must be about **that** candidate.

### 8.6 BRANCH_JOIN
- A join naming no branches is refused.
- Every joined branch must exist in `state_before` and must not be `OPEN` or `ABANDONED`.
- Coverage evidence must exist, be accepted, and support the rule.
- The partition certificate (`evidence.payload.branch_ids`) must **cover every joined
  branch**.
- Every branch must have concluded the **same** proposition, and it must be what the join
  publishes.
- **Disjointness is deliberately NOT required.** Disjunction elimination is sound for
  overlapping cases; demanding disjointness would reject valid reasoning. Coverage is the
  obligation.

### 8.7 WARRANT
- Cited warrant evidence must exist and be accepted.
- `evidence.supports_rule` must equal `warrant.rule`.
- The premise envelope is **order-sensitive** and is **not** a subset test: the evidence's
  premises must match the action's declared dependencies exactly.

### 8.8 EPISTEMIC_STATUS
Fires when `epistemic_effect.to_status` ∉ {`None`, `"PROPOSED"`, `"UNRESOLVED"`}. Requires
supporting evidence (from `epistemic_effect.evidence_id`, falling back to
`warrant.evidence_id`) that exists and is accepted. **Generation cannot self-certify.**

### 8.9 GOAL_DISCHARGE
- The produced claim's proposition must equal `action.summary` — a goal is discharged by its
  exact target, not an adjacent one.
- On `goal_effect.kind == "DISCHARGE"`: the goal must exist in `state_before`; the produced
  claim's proposition must equal the goal's; and (D-059) the goal must be `DISCHARGED` in
  `state_after` and must **not** be deleted. A goal is discharged, not removed.

### 8.10 TYPE_DOMAIN
- For each key in `typing.input_domains`, the claim's declared `domain` must **inhabit** the
  required domain — containment, not equality.
- An **absent** domain is unavailable evidence, not a violation (D-048): it becomes an
  unknown, not a mismatch.
- Registered domains: `Number`, `Real`, `Rational`, `Integer`, `Natural`, `PositiveReal`,
  `NonNegativeReal`, `Probability`. An unregistered name inhabits only itself.
- **`Probability` is not `PositiveReal`.** They are incomparable and meet at
  `NonNegativeReal`.

### 8.11 FRAME — the invariant nothing else enforces
`state_after` must be exactly what the action produced, and no more. Covers **all five**
record kinds: `claims`, `candidates`, `branches`, `obligations`, `goals`.

For each kind: a record removed → refused. A record changed without a **licensed** effect →
refused. A record appearing that the action does not produce → refused.

Licensed additions: `claims` ← `{output_id}`; `obligations` ← ids in `obligations_created`;
**`candidates`, `branches`, `goals` ← nothing at all.**

Licensed changes (`_licensed_change`): `candidates` by `candidate_effect.candidate_id`;
`branches` by membership in `branch_effect.branch_ids`; `obligations` by membership in
`obligations_discharged`; `claims` by `scope_effect.kind` ∉ {None,"NONE"}; `goals` by
`goal_effect.goal_id` **naming that goal** — a bare `kind` licenses nothing.

---

## 9. DECLARED-EFFECT MATERIALISATION

A declared effect must actually happen. Declaring is not performing (D-059).

| Declared | Must materialise as |
|---|---|
| `goal_effect.kind = DISCHARGE` on `g` | `state_after.goals[g].status == DISCHARGED`, record present |
| `obligations_created: [{id: o}]` | `o` present in `state_after.obligations` |
| `obligations_discharged: [{id: o}]` | `state_after.obligations[o].status == DISCHARGED` |
| `output_id = c` | `c` present in `state_after.claims` with matching ancestry |
| `candidate_effect.kind = PROMOTE` | lifecycle-legal status change, all constraints re-checked |

---

## 10. UNSUPPORTED CONSTRUCTS — do not attempt these

| Construct | Status |
|---|---|
| **Goal creation / subgoal decomposition** | **NOT REPRESENTABLE. FAILS CLOSED.** |
| Goal ancestry (`parent_goal_id`) | not modelled |
| Execution focus / scheduling / ordering | not modelled |
| Supersession of a fact | **not represented** — no status marks a claim superseded |
| Binder structure, variable elimination (`subst`) | not modelled; propositions are opaque strings |
| In-place claim mutation | refused (§4.3) |
| Proof search, planning, policy | out of scope |

### 10.1 THE GOAL-CREATION LIMITATION — the one you will hit most

**No action can declare that it creates subgoals.** A goal appearing in `state_after` that
was not in `state_before` is **refused** by the frame condition. There is no licensing
channel for it.

This is deliberate and measured: our corpus contains **zero** goal-creating transitions in
631, and the LeanDojo corpus has 18,315 which we **excluded** rather than accommodate.

**Translator procedure when a solution decomposes a goal:**
1. Do **not** invent goal records for the sub-parts.
2. Model the decomposition as a **case split** using branches (§8.6) if it is a genuine case
   analysis, **or**
3. Model each sub-result as an ordinary derived claim, with the final claim depending on
   them, **or**
4. If neither is faithful, **stop and emit a SEMANTIC GAP** (§14). Do not force it.

---

## 11. EVIDENCE AND TRUST (`trust.py`, `verify.py::_accepted`)

Two modes. **There is no default — the mode must be named** (D-050).

| | `OFFLINE_REPLAY` | `RUNTIME` |
|---|---|---|
| Use for | frozen, externally adjudicated corpus | anything a model/user/this repo authored |
| Recorded `status` | read as observed reference data; `VALID` accepts | **ignored entirely** |
| Requires | — | an `Attestation` carrying `CheckedEvidence` minted by `reasoning.certificates.check` |
| Missing `rule` on an effect | falls back to `action.operation` | **no fallback** — refused |
| API | `verify_replay(t)` | `verify_runtime(t, attestations)` |

`Attestation` fields: `evidence_id`, `evidence`, `claim_digest`, `premise_digests`, `rule`,
`checker`, `checker_version`. `binds(claim=…, premises=…, rule=…)` checks all three.

Attestations are keyed by **the id the action cites**, never by `record.id` — `record.id` is
payload-controlled and keying on it lets a producer route a genuine certificate onto a forged
record (D-052).

`evidence.trusted` is **never** authority. A checker that believed it would accept every
corrupted fixture.

**Translator rule: you are an untrusted author. Everything you produce is RUNTIME data.**
Verify with `verify_replay` only when reproducing a frozen corpus record verbatim.

---

## 12. BOUNDARY REFUSALS (`neutral.py`)

Refused with `NeutralImportError` — a refusal, never a partial import:

- unrecognised `schema_version` (only `semantic-firewall-case-0.1.0`)
- non-string `schema_version`
- a transition with no `action`
- a non-object where an object is required
- any status outside its enum
- non-string entries in identifier lists
- unhashable obligation entries
- **NaN, `Infinity`, `-Infinity` anywhere** in a free-form payload — `NaN != NaN` would make
  the frame condition report a false change on a byte-identical record

The importer **never throws anything else**. A verifier handed model output must not crash.

---

## 13. HML SURFACE GRAMMAR (`view.py`) — exact

Two-space indent. Depth carries structure. Tabs and misaligned indents are refused.

**Top-level keywords:** `transition` `schema` `source` `state` `scopes` `claim` `candidate`
`branch` `goal` `obligation` `action` `evidence`

**Field names per record** (these are the parser's accepted sets; an unknown field is
refused):

```
claim      : id proposition status scope domain depends
candidate  : id proposition status scope constraints origin depends evidence result
branch     : id predicate status scope conclusion partition
goal       : id proposition status scope
obligation : id proposition status mandatory origin depends discharge
action     : operation summary output depends
             preconditions obligations_created obligations_discharged
             typing warrant goal_effect scope_effect branch_effect
             candidate_effect epistemic_effect
evidence   : id kind status trusted supports premises payload
```

Value forms: `"quoted text"` for propositions/strings · bare identifiers for ids · comma
lists for id sets · JSON blobs for the free-form action fields · bare `true`/`false` ·
**status values are emitted BARE, not quoted** (`status GIVEN`).

An `id` field is emitted only when it differs from the key. `scope` is omitted when
`"global"`. A `schema` or `source` line at depth ≠ 1 is refused. Identifiers that cannot be
written bare must be quoted; an unterminated quote is refused.

### 13.1 Complete reference rendering — every construct

```
transition DEMO
  schema "semantic-firewall-case-0.1.0"
  source {"origin": "synthetic", "rationale": "grammar demo"}

state before
  scopes global, frame1
  claim p0
    proposition "x + 5 = 12"
    status GIVEN
    domain "Real"
  candidate k1
    proposition "x = 7"
    status UNVERIFIED
    constraints cn1
    origin "guess"
  branch b1
    predicate "x >= 0"
    status CLOSED
    conclusion "x = 7"
    partition part1
  goal g1
    proposition "x = 7"
    status OPEN
  obligation ob1
    proposition "denominator != 0"
    status OPEN
    mandatory true
    origin "DIVIDE at s2"
    depends p0

action a1
  operation "TRANSFORM"
  summary "x = 7"
  output c1
  depends p0
  preconditions [{"id": "pre1", "statement": "5 is subtractable", "status": "SATISFIED"}]
  obligations_created [{"id": "ob1", "statement": "denominator != 0"}]
  obligations_discharged [{"evidence_id": "e1", "id": "ob0"}]
  typing {"input_domains": {"p0": "Real"}, "output_domain": "Real"}
  warrant {"evidence_id": "e1", "premise_ids": ["p0"], "rule": "TRANSFORM"}
  goal_effect {"goal_id": "g1", "kind": "DISCHARGE"}
  scope_effect {"kind": "NONE"}
  branch_effect {"branch_ids": ["b1"], "coverage_evidence_id": "e1", "kind": "JOIN", "rule": "JOIN"}
  candidate_effect {"candidate_id": "k1", "evidence_id": "e1", "kind": "PROMOTE", "rule": "PROMOTE"}
  epistemic_effect {"claim_id": "c1", "evidence_id": "e1", "rule": "TRANSFORM", "to_status": "VERIFIED"}

evidence e1
  kind "ALGEBRA"
  status "VALID"
  trusted false
  supports "TRANSFORM"
  premises p0
  payload {"note": "subtract 5"}

state after
  scopes global, frame1
  claim p0
    proposition "x + 5 = 12"
    status GIVEN
    domain "Real"
  claim c1
    proposition "x = 7"
    status DERIVED
    domain "Real"
    depends p0
  ...
```

---

## 14. INVOCATION — parse, render, verify

```python
from hamiltonian_lang.semantic_state import (
    import_transition, export_transition,          # neutral JSON  <-> Transition
    parse_transition, render_transition,           # HML text      <-> Transition
    verify_replay, verify_runtime,                 # Transition    -> TransitionResult
    NeutralImportError, ViewError,
)
from hamiltonian_lang.semantic_state.model import GoalStatus   # see §3.2

t = import_transition(payload_dict)          # raises NeutralImportError on bad input
result = verify_runtime(t)                   # or verify_replay(t) for frozen corpus data
result.verdict                               # Verdict.VALID | INVALID | UNRESOLVED
result.error_class                           # str | None  — match the §6 table
result.findings                              # [Finding(invariant, error_class, detail)]
result.unknowns                              # [str] — populated only when UNRESOLVED
result.to_dict()

hml_text = render_transition(t)
t2       = parse_transition(hml_text)        # raises ViewError on malformed text
assert export_transition(t2) == export_transition(t)     # required round-trip identity
```

Run from the repo root with the frozen checkout:
`PYTHONPATH=src .venv/bin/python your_script.py`

---

## 15. HOW A PROPOSED TRANSLATION MUST BE VERIFIED

A translation is **accepted** only if all five hold:

1. `import_transition(payload)` succeeds.
2. `export_transition(import_transition(payload)) == payload` — neutral round trip is exact.
3. `parse_transition(render_transition(t))` reproduces the same object under
   `export_transition` — HML round trip is exact.
4. `verify_runtime(t).verdict` is `VALID`, **or** it is `UNRESOLVED` **and** the unknowns are
   genuine gaps in the source rather than translator laziness.
5. No `INVALID`. An `INVALID` means the translation asserts something the frozen semantics
   refuse — fix the translation, never the semantics.

Reject-and-report rather than "make it pass". The commonest way to make something pass is to
delete the information that made it fail.

---

## 16. WHAT MUST REMAIN REPRESENTATION-NEUTRAL

The canonical record must contain **no HML-specific naming**. It must be renderable to HML
and to a generic typed AST with **identical information content**, mechanically checkable:
same ids, same propositions, same dependencies, same goal, same effects, same labels, same
source identity.

**What must NEVER be inferred:**

- a dependency the source does not state
- a warrant, rule or theorem name the source does not name
- a precondition status the source does not establish
- an obligation the source never incurs
- a domain the source never declares (leave `None` → it becomes an unknown)
- a discharge the source never performs
- a branch conclusion the source never draws
- **the answer**, in any field
- anything at all from `state_after` when constructing `state_before`

If the source is silent, the value is `UNKNOWN` or absent. **Silence is data.**

---

## 17. MATCHED AST RENDERING

The AST arm is an experiment-side control, currently at
`hml-model-experiments/experiments/lean_domino_v2/renderers/lean_render.py`. It is **not part
of the frozen release**. It carries the same truth-relevant fields with ordinary generic
names:

```
State(
  Claim(id=p0, prop="x + 5 = 12", status=GIVEN),
  Obligation(id=ob1, prop="denominator != 0", status=OPEN),
)
Goal(prop="x = 7", open_goals=1)
Action(op=TRANSFORM, warrant=ALGEBRAIC_PRESERVATION, depends=[p0],
       goal_effect=DISCHARGE, produces="x = 7")
```

**The AST must never be deliberately degraded.** It is the control that tests whether HML
adds anything beyond generic explicit structure; handicapping it answers a worthless
question. Parity is asserted mechanically — extract the information set from both strings and
require set equality.

---

## 18. SEMANTIC-GAP PROCEDURE

When a worked solution needs something the frozen release cannot express:

1. **STOP.** Do not approximate, and do not change HML.
2. Emit a gap record instead of a transition:

```json
{ "gap_id": "...", "source_id": "...", "step": "...",
  "source_text": "<verbatim>",
  "reason": "GOAL_CREATION_NOT_REPRESENTABLE",
  "what_would_be_needed": "<one precise sentence>",
  "nearest_faithful_alternative": "<or null>",
  "hml_sha": "84bf9897689b0ed78a2caaefc1db850d49b81260" }
```

3. Keep it in an exclusions manifest. Exclusions are **evidence**, not failure — the LeanDojo
   build excluded 18,315 of 259,580 transitions this way and the count reconciled exactly.

Established reason codes: `GOAL_CREATION_NOT_REPRESENTABLE`, `UNCANONICALISED_OPERATION`,
`NO_GOAL_BEFORE`, `SUPERSESSION_REQUIRED`, `BINDER_STRUCTURE_REQUIRED`.

---

## 19. TRANSLATION ALGORITHM

```
WORKED SOLUTION
   │
   ├─ 1. SEGMENT into source steps. One step = one sentence/equation the author
   │     presents as a move. Keep the verbatim span as provenance.
   │
   ├─ 2. ATOMIC SEMANTIC DECOMPOSITION. Split any step doing two things
   │     ("factor and then substitute") into two transitions. One action changes
   │     one thing. If a step is pure narration, emit no transition.
   │
   ├─ 3. BUILD S_t by FORWARD ACCUMULATION from S_0. Never read ahead.
   │     S_0 = the problem's givens as claims (status GIVEN) + the question as a
   │     goal (status OPEN) + active_scopes ("global",).
   │
   ├─ 4. ACTION. Choose the typed effect channel FIRST, the operation label
   │     second. Set summary = the exact proposition being established.
   │     Set output_id for the new claim.
   │
   ├─ 5. WARRANT / PRECONDITIONS / DEPENDENCIES.
   │       dependencies  = the KEYS of every claim actually used
   │       warrant       = {evidence_id, rule, premise_ids} where the source names
   │                       a justification; otherwise omit and accept UNRESOLVED
   │       preconditions = SATISFIED only where the source establishes it;
   │                       DEFERRED + an obligation where it defers it
   │
   ├─ 6. S_t+1 = S_t + EXACTLY the declared delta. Nothing else moves.
   │     Copy every untouched record through unchanged.
   │
   ├─ 7. OBLIGATIONS / GOALS / STATUSES. Materialise every declared effect (§9).
   │
   ├─ 8. VALIDATE (§15): import → round trip → render → parse → round trip → verify.
   │
   ├─ 9. HML RENDERING via render_transition. Never hand-write HML.
   │
   └─ 10. VERDICT
           VALID       → accept
           UNRESOLVED  → accept ONLY if the unknowns are real gaps in the source
           INVALID     → fix the translation; if unfixable → SEMANTIC GAP (§18)
```

---

## 20. TEN WORKED MINIATURE TRANSLATIONS

Neutral-JSON action + state delta shown; the full record needs `state_before`, `state_after`,
`evidence`, `schema_version`, `case_id`.

### 20.1 Ordinary equality transformation
*"Since x + 5 = 12, we get x = 7."*
```jsonc
before: claims {p0: {proposition:"x + 5 = 12", status:"GIVEN", domain:"Real"}}
action: { operation:"TRANSFORM", summary:"x = 7", output_id:"c1", dependencies:["p0"],
          typing:{input_domains:{p0:"Real"}, output_domain:"Real"},
          warrant:{evidence_id:"e1", rule:"TRANSFORM", premise_ids:["p0"]} }
evidence: {e1:{kind:"ALGEBRA", status:"VALID", supports_rule:"TRANSFORM", premise_ids:["p0"]}}
after:  claims {p0 unchanged, c1:{proposition:"x = 7", status:"DERIVED",
                                 domain:"Real", dependencies:["p0"]}}
```

### 20.2 Cancellation requiring non-zero — precondition DEFERRED + obligation
*"Dividing both sides by (x − 2)…"* — the author does not justify `x ≠ 2`.
```jsonc
action: { operation:"TRANSFORM", summary:"x + 3 = 5", output_id:"c2", dependencies:["c1"],
          preconditions:[{id:"pre1", statement:"x - 2 != 0", status:"DEFERRED"}],
          obligations_created:[{id:"ob1", statement:"x - 2 != 0"}],
          warrant:{evidence_id:"e2", rule:"CANCEL", premise_ids:["c1"]} }
after:  obligations {ob1:{proposition:"x - 2 != 0", status:"OPEN", mandatory:true,
                          origin:"CANCEL at step 3"}}
```
The obligation **must** appear in `state_after` or the transition is `INVALID`.

### 20.3 Denominator restriction stated up front — SATISFIED
```jsonc
action: { operation:"APPLY_DEFINITION", summary:"f(x) is defined at x = 3",
          output_id:"c3", dependencies:["p1"],
          preconditions:[{id:"pre1", statement:"x - 1 != 0 at x = 3",
                          status:"SATISFIED", evidence_id:"e3"}],
          warrant:{evidence_id:"e3", rule:"APPLY_DEFINITION", premise_ids:["p1"]} }
```
No obligation: the source discharged it inline.

### 20.4 Case split — open two branches
*"Either x ≥ 0 or x < 0."* Branches are **state records**, and they cannot be added by an
action (§8.11) — they must be present in `state_before` of the transitions that use them, or
introduced by a transition whose `branch_effect` names them.
```jsonc
before: branches {b1:{predicate:"x >= 0", status:"OPEN", partition_id:"part1"},
                  b2:{predicate:"x < 0",  status:"OPEN", partition_id:"part1"}}
action: { operation:"CASE_SPLIT", summary:"case analysis on the sign of x",
          branch_effect:{branch_ids:["b1","b2"], kind:"OPEN", rule:"CASE_SPLIT"} }
```

### 20.5 Branch-local fact — must not leak
Inside `b1`, the conclusion is scoped to that frame:
```jsonc
before: active_scopes ["global","b1"]
action: { operation:"TRANSFORM", summary:"|x| = x", output_id:"c4", dependencies:["p2"] }
after:  claims {c4:{proposition:"|x| = x", status:"DERIVED", scope:"b1", dependencies:["p2"]}}
```
Writing `c4` with `scope:"global"` is a **SCOPE_LEAK**. A branch-local fact reaches the
global scope **only** through a join (20.6) or an explicit `scope_effect.kind = DISCHARGE`.

### 20.6 Branch join
*"In both cases |x| ≥ 0, so the result holds."*
```jsonc
before: branches {b1:{...status:"CLOSED", conclusion:"|x| >= 0"},
                  b2:{...status:"CLOSED", conclusion:"|x| >= 0"}}
action: { operation:"JOIN_BRANCHES", summary:"|x| >= 0", output_id:"c5",
          dependencies:["p2"],
          branch_effect:{branch_ids:["b1","b2"], kind:"JOIN",
                         coverage_evidence_id:"e5", rule:"JOIN"} }
evidence: {e5:{kind:"PARTITION", status:"VALID", supports_rule:"JOIN",
               payload:{branch_ids:["b1","b2"]}}}
```
Both conclusions must be **identical** and equal to `summary`. The certificate must cover
**every** joined branch. Disjointness is not required.

### 20.7 Candidate creation
*"Suppose the root is x = 7; we will check."*
```jsonc
before: candidates {}      // candidates cannot be ADDED by an action (§8.11);
                           // the candidate must already exist in state_before
before: candidates {k1:{proposition:"x = 7", status:"PROPOSED",
                        constraint_ids:["cn1","cn2"], origin:"trial root"}}
action: { operation:"SELECT", summary:"consider x = 7",
          candidate_effect:{candidate_id:"k1", kind:"OPEN", rule:"SELECT"} }
after:  candidates {k1:{...status:"UNVERIFIED"}}     // PROPOSED -> UNVERIFIED is legal
```

### 20.8 Candidate rejection
*"x = 7 fails the second condition, so discard it."*
```jsonc
action: { operation:"VERIFY_CANDIDATE", summary:"x = 7 is rejected",
          candidate_effect:{candidate_id:"k1", kind:"REJECT",
                            evidence_id:"e7", rule:"VERIFY_CANDIDATE"} }
after:  candidates {k1:{...status:"REJECTED", verification_result:"fails cn2"}}
```
`REJECTED` is **terminal**. A later transition reopening it is `INVALID`
(`CANDIDATE_PROMOTION`).

### 20.9 Theorem application
*"By the Pythagorean theorem, c² = a² + b²."*
```jsonc
action: { operation:"APPLY_THEOREM", summary:"c^2 = a^2 + b^2",
          output_id:"c8", dependencies:["p3","p4"],
          typing:{input_domains:{p3:"Real", p4:"Real"}, output_domain:"Real"},
          warrant:{evidence_id:"e8", rule:"APPLY_THEOREM", premise_ids:["p3","p4"]} }
evidence: {e8:{kind:"THEOREM", status:"VALID", supports_rule:"APPLY_THEOREM",
               premise_ids:["p3","p4"], payload:{name:"Pythagorean theorem"}}}
```
`premise_ids` must match `dependencies` **exactly and in order** (§8.7).

### 20.10 Obligation discharge, then final goal discharge
*"Since x = 5 ≠ 2 the earlier division was valid, and therefore x = 5."*
```jsonc
// (a) discharge the debt
action: { operation:"VERIFY", summary:"x - 2 != 0",
          obligations_discharged:[{id:"ob1", evidence_id:"e9"}] }
after:  obligations {ob1:{...status:"DISCHARGED", discharge_evidence_id:"e9"}}

// (b) discharge the goal
before: goals {g1:{proposition:"x = 5", status:"OPEN"}}
action: { operation:"DISCHARGE", summary:"x = 5", output_id:"c9", dependencies:["c8"],
          goal_effect:{goal_id:"g1", kind:"DISCHARGE"},
          warrant:{evidence_id:"e10", rule:"DISCHARGE", premise_ids:["c8"]} }
after:  goals  {g1:{proposition:"x = 5", status:"DISCHARGED"}}
        claims {c9:{proposition:"x = 5", status:"DERIVED", dependencies:["c8"]}}
```
`summary`, the produced claim's proposition and the goal's proposition must be the **same
string**. The goal must end `DISCHARGED` and must **not** be deleted (D-059).

---

## 21. TRANSLATOR CHECKLIST

- [ ] `schema_version` is exactly `semantic-firewall-case-0.1.0`
- [ ] every record's `id` equals its dictionary key
- [ ] every status is inside its enum, exact case, no trailing space
- [ ] `state_after` differs from `state_before` by **exactly** the declared delta
- [ ] every declared effect materialised
- [ ] `dependencies` cite keys that exist in `state_before.claims`
- [ ] `summary` equals the produced claim's proposition when a goal is discharged
- [ ] no goal created; no candidate/branch added by an action
- [ ] no `NaN`/`Infinity` anywhere
- [ ] unknowns written as `UNKNOWN`, not guessed
- [ ] neutral round trip exact; HML round trip exact
- [ ] `verify_runtime` returns `VALID`, or `UNRESOLVED` for a genuine source gap
- [ ] anything unrepresentable emitted as a SEMANTIC GAP, not forced

---

## 22. KNOWN LIMITATIONS CARRIED BY THIS RELEASE

Part of the release, not footnotes:

- goal creation fails closed and is not representable; goal ancestry not modelled
- execution focus / scheduling not modelled
- supersession not represented
- propositions are **opaque strings** — no binder structure, so variable elimination is not
  representable
- obligation discharge does **not require** evidence; a cited id is honoured, an omitted one
  is not demanded
- mutation score 92.5%; twelve `REDUNDANT_DEFENCE` survivors — non-observability through the
  public contract, **not** proved equivalence
- `model.ErrorClass` is a dead export with a false docstring (§6)
- `GoalStatus` missing from the package `__all__` (§3.2)
- **static HML superiority is UNPROVEN.** This release establishes engineering trust in the
  instrument, not any model reasoning benefit.

---

## 23. VALIDATION OF THIS DOCUMENT

Every schema, enum, field name and grammar fragment above was extracted mechanically from the frozen source at `84bf989`, not recalled. The behavioural claims were then executed against the real verifier:

| claim | expected | measured |
|---|---|---|
| §20.1 ordinary transformation | VALID | `VALID` |
| §10.1 goal created by an action | refused | `INVALID / DEPENDENCY_VIOLATION` |
| §8.11 candidate added by an action | refused | `INVALID / DEPENDENCY_VIOLATION` |
| §8.11 branch added by an action | refused | `INVALID / DEPENDENCY_VIOLATION` |
| §9 obligation declared, not materialised | refused | `INVALID / OBLIGATION_DROP` |
| §9 obligation declared and materialised | VALID | `VALID` |
| §3 lowercase goal status `open` | refused at import | `NeutralImportError` |
| §12 `NaN` in a payload | refused at import | `NeutralImportError` |

The reference rendering in §13.1 is verbatim `render_transition` output, not hand-written.

Two defects in the frozen release are documented rather than fixed, because the release is frozen: the dead `model.ErrorClass` enum (§6) and the missing `GoalStatus` export (§3.2). Both are packaging/documentation issues; no verdict depends on either.
