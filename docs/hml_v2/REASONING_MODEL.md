# HML v2 — the reasoning model

**Status: normative semantic model.** This file defines what a reasoning transition *is*
in HML v2. It is the document `src/hamiltonian_lang/ast/nodes.py` refers to when it says
`status` is computed by the checker and cannot be written in source.

**Companions.** `GRAMMAR_CONTRACT.md` fixes surface syntax (lead integrator, not this
document). `SEMANTICS.md` covers interaction with the v0 semantic barriers and with
canonical identity. `OBLIGATIONS.md` covers generation and discharge. `DESIGN_LOCK.md`
records every choice and every rejected alternative, including the places where this
document disagrees with a locked decision.

**Base.** Branch `feature/hml-reasoning-kernel-v2`, base SHA `3dd4216`; `src/` at that SHA
is byte-identical to the audited SHA `b1ac7bf`, so every audit finding applies unchanged.
Measurements in this document were taken against a pristine `git archive HEAD src` export,
not against the working tree, because the working tree is being edited concurrently by the
implementation workstream.

---

## 0. What is being fixed, in one paragraph

The audit's verdict is that HML "is a well-engineered notation for mathematical *state*
that does not represent mathematical *reasoning*"
(`report/EXECUTIVE_VERDICT.md`). Its three supporting findings are: zero transformation
forms in the surface grammar (C-5); `prove` proves nothing and `assume` discharges nothing
(C-6, C-1); and ladder criteria 3.4 and 3.5 — *obligations generated from partial
operations* and *transformations that check their own preservation* — fail with no
mechanism reachable from `.hml` source. This model addresses 3.4, 3.5, 3.3 and 3.6. It does
not address coverage (2.1, 2.2, 3.2) or composition (2.10, 3.9), which are a separate
programme.

**Verified by execution, not by citation.** The two headline claims were re-run here:

```
$ .venv/bin/hml check t1.hml          # module T1 / prove 1.0 = 2.0
ok: T1 (2 statements, 0 symbols, 1 proof obligation(s))        exit=0

$ .venv/bin/hml check t2.hml          # var x : Real / assume x > 0.0 / def y := log(x)
error HML-T427: the argument of log has the wrong type
  found: Real   expected: PositiveReal                          exit=1
```

Both reproduce. A third result, **not** in the audit and worse than what the audit records,
is reported in §9.3: today an `assume` does not merely fail to discharge — it lets the
verifier *refute* a goal that follows from it.

---

## 1. The objects

Seven objects. Each is listed with its identity, what it may contain, and — the load-bearing
column — **who is permitted to write it**.

| object | identity | written by |
|---|---|---|
| **GOAL** | `ClaimId` | source (`goal g : P`) |
| **DERIVATION** | `ClaimId` | source states it; **status written only by the kernel** |
| **RULE** | a name in the closed rule catalogue | neither: compiled in |
| **OBLIGATION** | `(derivation ClaimId, template index, instantiation)` | **generated only by the kernel** from a rule's spec |
| **DISCHARGE** | `(obligation identity, evidence reference)` | source *claims* it; kernel *adjudicates* it |
| **VERIFICATION STATUS** | a value of a closed enum | kernel only |
| **PROVENANCE** | an opaque record | kernel and tooling; never source; **never hashed** |

### 1.1 GOAL

A proposition the module intends to establish. Stating a goal asserts nothing — this is the
whole point of separating it from `require` (a constraint the model must satisfy) and from
v1's `prove` (which established nothing but read as though it did).

A goal carries a `ClaimId`, a proposition of type `Proposition` or `Bool`, and a
`GoalStatus`. It carries no proof.

### 1.2 DERIVATION

One inference: *from these premises, by this rule, with these parameters, this conclusion
follows.* Fields: label, premise claim references, rule name, role-labelled rule arguments,
stated conclusion, computed obligation set, computed status, computed dependency set.

Two properties make this more than vocabulary:

1. **The conclusion is stated by the author and checked by the kernel.** The kernel applies
   the rule to the premises, produces its own conclusion, and compares it to the stated one
   *by canonical form*. A derivation is not "accepted because it was written down".
2. **The rule identity is not the author's to choose freely.** `EdgeKind` is derived from
   the operation and is not overridable — this is already true in
   `v1/transformation.py:712-717` and the reason is stated there: "Letting a caller label an
   edge is how a rewrite acquires the word `implies`."

### 1.3 RULE

An entry in a **closed catalogue**. HML v2 does not admit user-defined trusted rules
(`GRAMMAR_CONTRACT.md` §6), and this model does not ask for them.

The catalogue is `v1/transformation.py::OPERATIONS`. Measured, not asserted:

```
$ .venv/bin/python -c "from hamiltonian_lang.v1 import transformation as T; ..."
Operation members: 30      OPERATIONS entries: 30      missing specs: []
EdgeKind: 9                ObligationKind: 5           INFERENCE_RULES: 8
PROHIBITED_EDGE_COERCIONS: 9
```

Each `OperationSpec` already carries: the edge kind, required arguments, required warrant
kinds, obligation templates tagged by `ObligationKind`, an optional per-item obligation, an
optional `weakening`, source arity bounds, an `asserted` flag, and a `reversed_entailment`
flag. That is the right shape. **It is not yet usable as a kernel** — see §9.1 and
`DESIGN_LOCK.md` D-V2-002; the obligations are Python format strings, and the edges relate
*names*, not expressions.

### 1.4 OBLIGATION

A side condition that a rule application owes. Generated, never authored: the surface form
`obligation n : P` in `GRAMMAR_CONTRACT.md` §1 exists for tests and for restating a
generated obligation, and an authored obligation that does not correspond to a generated one
is a diagnostic, not a new obligation. Allowing source to invent obligations would let a
module manufacture an easy one and then discharge it.

### 1.5 DISCHARGE

A *claim* that a named piece of evidence establishes an obligation. `discharge o by a1` is
adjudicated exactly as `proved g by d` is: writing it does not make it so. The admissible
evidence forms and the exact conservative rules are in `OBLIGATIONS.md` §4.

### 1.6 VERIFICATION STATUS

Three closed enums, §2–§4. None of their values has a surface spelling.

### 1.7 PROVENANCE

Which checker decided a status, at which version, on what evidence, with which witness, at
which source span. This is exactly the payload `verification/obligations/records.py`
already defines and enforces (`ObligationRecord.__post_init__` refuses `DISCHARGED` outside
the supported class set, refuses `DISCHARGED` with a witness, refuses `FAILED` without one,
refuses `UNSUPPORTED` without a stated missing capability). V2 reuses that record type
rather than inventing a second one.

**Provenance is never part of mathematical identity.** The argument is in `SEMANTICS.md` §4.

---

## 2. Derivation status — the finite state machine

```
                     (kernel applies the rule)
   PROPOSED ──────────────┬────────────────────► CHECKED
      │                   │                         │
      │                   └────────────────────► REJECTED
      │                                              ▲
      │  (a premise is unresolved / cyclic /         │
      │   the rule is unknown / arity is wrong)      │
      └──────────────────────────────────────────────┘

   CHECKED ── all mandatory obligations DISCHARGED ──► VERIFIED
```

Four states. No others. In particular there is no `PARTIALLY_VERIFIED`, no
`VERIFIED_MODULO_ASSUMPTIONS` and no probabilistic state: a conditional result is a
`VERIFIED` derivation with a **non-empty dependency set** (§6), which is a field, not a
status.

### 2.1 Entry conditions, stated as necessary and sufficient

**PROPOSED** — the initial value. Entered when, and only when, the parser constructed the
derivation node. It asserts: *the source contains a syntactically well-formed inference
claim.* Nothing more. It is the value of `status` at the moment the AST node exists and it
is never re-entered.

**REJECTED** — entered when the kernel ran and any of these holds:

| R1 | a premise label does not resolve in the claim namespace |
| R2 | the premise set makes the derivation graph cyclic (§5) |
| R3 | the rule name is not in the catalogue |
| R4 | a `required_arguments` entry of the rule's spec is absent |
| R5 | the number of premises is outside `[min_sources, max_sources]` |
| R6 | the rule requires a warrant kind the citation does not supply |
| R7 | a premise's relatum does not match `EDGE_DOMAIN[kind]` — an expression where a proposition is required, or the reverse |
| R8 | the kernel applied the rule and its output is **not** canonically identical to the stated conclusion |

R1–R7 are structural and are already implemented, by index and by name, in
`TransformationChain.validate` (`v1/transformation.py:1021-1159`, codes `HML-X601`–
`HML-X608`). R8 is the one that does not exist today and is the reason §9.1 says the
existing module is a catalogue and not a kernel.

REJECTED carries a `rejection_reason`. A rejection without a locatable cause is itself a
defect: this project's diagnostics contract (`diagnostics/__init__.py`) requires a code, a
span and, where one exists, a correction.

**CHECKED** — entered when, and only when, **all** of these hold:

| C1 | none of R1–R7 holds |
| C2 | the kernel independently computed the rule's output from the premises and the rule arguments |
| C3 | that output and the stated conclusion have the **same canonical form** under `backends.canonical` with `include_names=False` |

C3 is where alpha-equivalence earns its keep: `y = 2*x` and `y = 2*w` are the same
derivation output iff the binders correspond, which the nameless canonical form already
decides (`SymbolId.canonical()` → `sym:#depth.ordinal`).

CHECKED asserts exactly this and no more: **the rule was applied correctly.** It says
nothing about whether the rule's side conditions hold. `divide_through by k` is CHECKED
when the algebra is right, and CHECKED is compatible with `k` being zero.

**VERIFIED** — entered when, and only when:

| V1 | the derivation is CHECKED |
| V2 | every **mandatory** obligation generated by this derivation is DISCHARGED (§4.2, §7) |
| V3 | every premise claim is itself VERIFIED, or is an assumption/declaration admitted as a hypothesis (§6) |

V3 is not redundant with V2. Without it, a derivation could be VERIFIED on top of a
REJECTED premise, and "VERIFIED" would mean "this one step is fine" rather than "this
conclusion is established". The audit's criterion 3.5 asks for a *preservation check*, and a
preservation check that does not look at its input has not checked preservation.

### 2.2 Why VERIFIED is unreachable without a checker

This is the property the whole design exists to protect, so it is argued rather than
asserted. The argument has four parts, and each part names the mechanical test that
discharges it. **None of these tests has been run: the implementation does not exist yet.**
They are stated here as obligations on the implementation workstream.

**(a) VERIFIED has no surface spelling.** The lexer's `KEYWORDS` set
(`lexer/__init__.py:35-55`) is a frozenset of 47 names; no token lexes to a status value,
and `GRAMMAR_CONTRACT.md` §1 introduces no production in which a status appears. There is
therefore no parse of any input that produces a node with `status == VERIFIED`.
*Test:* `test_no_source_text_produces_verified` — for every `.hml` under `examples/` and
`tests/fixtures/`, and for a generated corpus containing the literal strings `VERIFIED`,
`verified`, `status := VERIFIED`, assert that after `parse()` alone (before checking) no
derivation node has a status other than `PROPOSED`. This is mechanically checkable and must
be a property test, not three examples.

**(b) The status field has exactly one writer.** The default value is `PROPOSED`; the only
other assignment to `DeriveStmt.status` in the entire source tree is inside the kernel's
adjudication function. *Test:* `test_status_has_one_writer` — a static check over
`src/` asserting that the set of syntactic assignments to `.status` on a derivation node is
a singleton, located in the kernel module. A grep-based test is adequate and is the kind of
test this repository already writes (`tests/golden/test_golden.py::test_no_superiority_claim_in_public_docs`
is the same shape).

**(c) The VERIFIED branch is guarded by a conjunction that is written once.** This mirrors
`verification/obligations/engine.py::_verdict`, whose docstring states the reason
explicitly: the conjunction "is written once … so no caller can assemble a weaker version of
it". V2 must do the same. *Test:* `test_verified_requires_every_conjunct` — for each of V1,
V2, V3, construct a module in which exactly that conjunct fails and assert the status is not
VERIFIED. Three targeted negatives, plus a mutation check that flipping any conjunct in the
kernel makes at least one of them fail.

**(d) The status is not transmissible.** A derivation cannot inherit VERIFIED from another
object, and no serialisation round trip may introduce it. *Test:*
`test_status_not_restorable_from_canonical` — serialise a VERIFIED module, reparse the HML
surface, and assert every derivation is back at `PROPOSED`. This falls out of §4 of
`SEMANTICS.md` (status is not in the canonical form) and is the test that proves the two
decisions are consistent rather than merely compatible.

**What this argument does not establish.** It establishes that VERIFIED implies *the kernel
ran and its conjunction held*. It does **not** establish that the kernel is *correct* — that
the rule catalogue's rules are sound, or that the discharge procedure never discharges a
false obligation. That is a soundness argument (ladder criterion 4.5) and this project does
not have one. The honest statement of what VERIFIED means in HML v2 is:

> **VERIFIED means: the trusted rule kernel applied the named rule, reproduced the stated
> conclusion up to canonical form, and found every mandatory side condition discharged by a
> procedure in the declared decidable subset — relative to the recorded dependency set.**
> It does not mean the conclusion is true.

Any documentation, diagnostic or English rendering that shortens this to "proved" is a
defect, in the same way that `v1/epistemic.py` treats "failed to reject" → "proved" as a
defect.

---

## 3. Goal status — the finite state machine

```
   OPEN ──── proved g by d,  d VERIFIED, conclusion(d) ≡ P ────► PROVED
     │
     ├────── a REFUTATION-kind derivation targets P ───────────► REFUTED
     │
     └────── v1 `prove P` with no `proved` claim ──────────────► ASSERTED_UNCHECKED
```

**OPEN** — the initial and default value.

**PROVED** — entered when, and only when, a `proved g by d` statement exists **and** the
kernel adjudicates it: `d` is VERIFIED, and `d`'s conclusion is canonically identical to
`g`'s proposition. Both conjuncts are required. Without the second, `proved g by d` would
prove whatever `d` concluded, regardless of what `g` says.

**REFUTED** — entered only via a derivation whose rule has `EdgeKind.REFUTATION`
(`Operation.COUNTEREXAMPLE`), which requires a `witness` argument
(`v1/transformation.py:605-613`). This mirrors `records.py`'s rule that a `FAILED` obligation
must carry a witness: "A failure without a witness is not a failure here — it is
`INCONCLUSIVE`."

**ASSERTED_UNCHECKED** — the reclassification of v1's `prove`. `GRAMMAR_CONTRACT.md` §1
retains `prove` and gives it this status. It is a terminal, non-load-bearing state: it never
becomes PROVED, and any English or LaTeX rendering must say so in words.

> **Conflict flagged, for the lead to arbitrate.** `GRAMMAR_CONTRACT.md` §3 names the fourth
> goal state `ASSERTED_UNCHECKED`. The AST currently being written in the implementation
> workstream names it `UNSUBSTANTIATED` and gives it a different meaning — a goal whose
> `proved` claim was adjudicated and failed. Those are two different states and the
> difference is real: "nobody tried" and "somebody tried and it did not hold up" must not be
> the same label, for the same reason `records.py` refuses to collapse `UNSUPPORTED` and
> `INCONCLUSIVE`. **This model requires both**, giving five goal states:
> `OPEN | PROVED | REFUTED | ASSERTED_UNCHECKED | UNSUBSTANTIATED`. See
> `DESIGN_LOCK.md` D-V2-009.
>
> **Resolved in the implementation, recorded here (D-047):** the AST carries
> `UNSUBSTANTIATED` — a `proved` claim that was adjudicated and failed — and not
> `ASSERTED_UNCHECKED`. The distinction this note demanded is preserved; it is drawn
> between `OPEN` ("nobody adjudicated") and `UNSUBSTANTIATED` ("somebody claimed and it did
> not hold up") rather than by a fifth name.

### 3a. Certified underdetermination (D-047)

```
   OPEN ──── undetermined g by e,  e VALID, judgement = determines_neither,
             proposition(e) ≡ P,  context(e) ≡ context here ────► UNDERDETERMINED
```

**UNDERDETERMINED** — the premises entail neither `P` nor `¬P`, and there is checked
evidence of it: two models of Γ, independently re-evaluated here, that disagree on `P`.

Four conditions, all required, each separately tested. The certificate must be VALID; it
must carry the `determines_neither` judgement; its proposition must be canonically
identical to the goal's; and its **context must still match**. The last exists because
entailment is monotone — Γ ⊭ P says nothing about Γ ∪ {a₃} — so a certificate issued
earlier in a module is not spendable after a premise has been added. For the same reason a
non-entailment certificate must rest on *every* established claim in scope; one that omits
a premise is rejected.

**What must never reach this state.** Search failed. Proof not found. Timeout. Unsupported
syntax. Unsupported semantic fragment. Partial model. An external solver answering
"unknown". Absence of evidence. Every one of those is `OPEN`.

The separation is structural rather than a matter of remembering to check a flag.
`reasoning/adjudication.py` carries a four-valued `EntailmentVerdict`
(`ENTAILED | REFUTED | UNDERDETERMINED | UNKNOWN`) which is the semantic source of truth,
and `GoalStatus` is its **projection**; `UNKNOWN` projects onto `OPEN`. Setting the enum is
not a proof, and nothing outside the adjudication path can set it.

**Why a judgment rather than a status.** A status word cannot say *which* Γ it was about,
and for a claim about a theory that is the load-bearing fact. `Adjudication` binds the
verdict to the target's identity, the context's identity, the ordered premise identities,
the supporting claim and the checker that validated it.

Supported fragment in V0: **finite ground classical propositional logic** over declared
`Bool` names. No first-order completeness is claimed. Anything outside it fails closed.

Requiring *both* witnesses to satisfy Γ also certifies Γ **satisfiable**, so an
inconsistent context — which entails everything — cannot acquire this status by this route.

### 3b. Quantified inference (D-047)

Two rules, `forall_intro` and `forall_elim`. Ordinary theorem application composes from a
library theorem plus elimination plus the existing substitution machinery, rather than
becoming a third trusted primitive. Existential intro/elim are deliberately absent.

```
    Γ, a : D (arbitrary) ⊢ φ(a)                Γ ⊢ ∀x : D . φ(x)     t : D
    ---------------------------                ------------------------------
        Γ ⊢ ∀x : D . φ(x)                              Γ ⊢ φ[t/x]
```

**The eigenvariable condition is stronger than the textbook one, deliberately.** The
textbook rule quantifies over "undischarged assumptions the body proof depends on"; read
as the transitive premise closure that would leave a hole, because HML discharges
obligations against Γ through `RefinementEnv.entails`, not only through cited premise
edges — a derivation can rest on an assumption it never names. The implemented condition is
therefore: **no assumption in scope, including inside `scope` frames, may mention the
variable freely.** It over-rejects, which is the safe direction.

**The kernel stays context-free.** It cannot answer either condition — one needs the whole
assumption set, the other the type environment — so `RuleSpec.side_conditions` names them
and `check.py` answers them from a static table. An unknown name **rejects**: a rule can
never be admitted by a guard nobody implemented.

**Binder construction is re-depthing, not wrapping.** Identity here is locally nameless
(`sym:#<depth>.<ordinal>`), so a premise's module-level `n` and a conclusion's bound `n`
are different symbols. `reasoning/binders.py` rebuilds the subtree so the result is exactly
what the resolver produces from the same text; no second notion of identity is introduced,
and the test uses the resolver itself as the oracle.

---

## 4. Obligation status — the finite state machine

```
   OPEN ──── an admissible discharge rule decided it TRUE ────► DISCHARGED
     │
     ├────── a witness was produced showing it FALSE ─────────► FAILED
     │
     └────── no rule applies, or one applied and could not
             decide within its stated bound ─────────────────► UNKNOWN
```

**OPEN** — generated by the kernel from a rule's `OperationSpec.obligations` and not yet
adjudicated. The default. An obligation that is never looked at stays OPEN, and OPEN blocks
VERIFIED exactly as firmly as FAILED does.

**DISCHARGED** — entered when, and only when, one of the conservative rules of
`OBLIGATIONS.md` §4 decided the obligation true **and** the record naming the deciding
checker, its version and its evidence was constructed successfully. The second conjunct is
not ceremony: `ObligationRecord.__post_init__` refuses to build a `DISCHARGED` record whose
class is outside `SUPPORTED_CLASSES`, so an unsupported discharge is a construction error
rather than a silent pass.

**FAILED** — entered when, and only when, a concrete refuting assignment was exhibited. The
existing `Witness` type enforces this at construction: a witness with neither bindings nor
evaluated values raises, with the message "this is a non-acceptance, not a refutation".

**UNKNOWN** — the honest default. Entered when no rule claims the obligation, or a rule
claims it and returns without a verdict. **UNKNOWN blocks VERIFIED.** This is the single
most important line in the state machine and it is the same design already made in
`verification/obligations/engine.py`, whose docstring says of the equivalent condition:
"Dropping it would turn every gap in the supported subset into a silent pass, and the
endpoint would stop being able to fail — which is the only reason it is worth measuring."

### 4.1 UNKNOWN is a presentation, not a loss of information

`GRAMMAR_CONTRACT.md` §3 specifies a four-valued obligation status ending in `UNKNOWN`. The
already-implemented record layer has a different four:
`DISCHARGED | FAILED | UNSUPPORTED | INCONCLUSIVE`, and `records.py` argues at length that
collapsing the last two "would hide which of the two is growing".

Both are right at their own layer. The resolution adopted here:

* the **surface / diagnostic** vocabulary is `OPEN | DISCHARGED | FAILED | UNKNOWN`;
* the **record** layer keeps `OPEN | DISCHARGED | FAILED | UNSUPPORTED | INCONCLUSIVE`;
* `UNKNOWN` is defined as the presentation of `{UNSUPPORTED, INCONCLUSIVE}` and the record
  always retains which one it was.

The mapping is total and gate-preserving: all of `OPEN`, `UNSUPPORTED`, `INCONCLUSIVE`
block VERIFIED, so no gating power is lost by presenting them together. See
`OBLIGATIONS.md` §5 for the table and `DESIGN_LOCK.md` D-V2-008.

### 4.2 Mandatory versus advisory

A derivation is VERIFIED iff **(the rule application is CHECKED) and (every mandatory
obligation is DISCHARGED)**. "Mandatory" therefore has to be defined precisely, and it must
be defined by a rule rather than by a list someone maintains.

> **The rule: an obligation is MANDATORY iff the edge that generated it is *asserted*.**

`OperationSpec.asserted` already exists and is `False` for exactly one operation —
`Operation.CONVERSE` — with the stated reason "stating a converse does not assert it"
(`v1/transformation.py:594-604`). An unasserted edge claims nothing, so nothing rests on its
side conditions.

Applying the rule to the five existing `ObligationKind` values:

| ObligationKind | mandatory? | why |
|---|---|---|
| `SIDE_CONDITION` | **mandatory** | it is the truth condition of the rewrite. `divide_through by k` without `k != 0` is the error class the layer exists to catch. |
| `HYPOTHESIS` | **mandatory** | a theorem applied outside its hypotheses concludes nothing. |
| `CASE_SPLIT` | **mandatory** | an unconsidered branch is an unsound argument, not an incomplete one. `sqrt_both_sides` generates one and it is load-bearing. |
| `DIRECTION` | **mandatory** | an equivalence owes a proof each way; discharging one direction and calling it done is precisely the `LOGICAL_IMPLICATION`→`EQUIVALENCE` conflation the prohibition table forbids. |
| `CONVERSE` | **advisory** | generated only by `Operation.CONVERSE`, whose `asserted` is `False`. |

So exactly one of five kinds is advisory, and the reason is mechanical rather than editorial.
*Test:* `test_advisory_iff_unasserted` — for every operation in the catalogue, assert
`obligation_is_mandatory(kind) == spec.asserted` for every obligation it generates. If a
future operation is added with `asserted=False`, the table follows automatically.

**Advisory does not mean invisible.** An advisory obligation still appears in the report, in
`hml obligations`, and in the canonical form (`SEMANTICS.md` §4.2). It does not gate
VERIFIED; it does gate the English rendering, which must state that the converse is neither
established nor refuted.

---

## 5. Acyclicity

Derivations form a **directed acyclic graph** whose vertices are claims (goals,
assumptions, declarations, derivations) and whose edges point from a derivation to each of
its premises.

**The rule.** A module is REJECTED if the premise graph contains a cycle of any length,
including a self-loop. Every derivation on the cycle is marked REJECTED with the cycle path
in the diagnostic.

**Why a cycle must be rejected rather than merely reported.** A cyclic argument establishes
nothing, and a checker that walked one would either loop forever or terminate at an
arbitrary depth and report a status that depended on the traversal order. The codebase has
already made this decision twice for the same reason: `Resolver._check_definition_cycles`
rejects circular definitions with the note "a definition must be reducible to non-circular
terms; every inference needs traceable dependencies (governing principle 3)"
(`semantics/__init__.py:327-355`), and `_check_concept_cycles` rejects circular `extends`.

**Reuse, not reinvention.** `Resolver._find_cycle` (`semantics/__init__.py:290-325`) is an
iterative DFS with three-colouring that returns one cycle as a path. It is generic over
`dict[str, list[str]]`. The claim graph is exactly that shape. Use it. A second cycle
detector with different behaviour on the same repository is a liability.

**Ordering policy.** Module scope is order-independent for *values* (D-008, implemented as a
two-pass resolver). The claim namespace is resolved the same way — a `proved` may appear
before the `derive` it names — because forcing textual order would make the reasoning layer
the only order-sensitive part of the language, and the round-trip printer would then be
constrained by an invisible rule. Order-independence is exactly what makes cycles possible,
which is why they are detected explicitly rather than assumed away. That sentence is copied
in substance from `semantics/__init__.py:245-248`; the same reasoning applies unchanged.

**Diagnostic code.** `HML-R901` (the `HML-R` family is unused at base: verified by
`grep -rc "HML-R" src` returning no matches).

---

## 6. Dependencies, and what VERIFIED means in their presence

A derivation's **dependency set** is the set of assumptions that were used, directly or
transitively, to discharge its obligations or to establish its premises.

`v1/transformation.py` already carries this: `TransformationEdge.assumptions` and
`ChainReport.dependencies`, accumulated across the chain and rendered as "assumptions carried
forward". V2 keeps it and makes it load-bearing.

**The rule.** VERIFIED is *relative to* the dependency set. A VERIFIED derivation with an
empty dependency set is unconditional; with a non-empty one it is conditional, and every
rendering must name the conditions. There is no separate status for this, because a status
cannot carry a set and a status that hid the set would be worse than one that did not exist.

This is what makes ladder criterion 3.3 (*assumptions first-class and scoped, and the active
assumption set at any point is enumerable*) reachable: the dependency set **is** the
enumeration.

---

## 7. The composition rule, stated once

```
derivation is VERIFIED
  ⟺  CHECKED
      ∧  ∀ o ∈ obligations(derivation) . mandatory(o) → status(o) = DISCHARGED
      ∧  ∀ p ∈ premises(derivation)   . established(p)

goal is PROVED
  ⟺  ∃ d . proved(goal, d) ∧ status(d) = VERIFIED
            ∧ canonical(conclusion(d)) = canonical(proposition(goal))
```

where `established(p)` holds when `p` is a VERIFIED derivation, or an `assume`/declaration
admitted as a hypothesis (in which case `p` joins the dependency set), and `mandatory` is
§4.2's rule.

Both conjunctions are to be written **once**, in the kernel, and every consumer must call
that function rather than re-deriving the condition. The precedent and the reason are in
`engine.py::_verdict`.

---

## 8. Composition with the existing epistemic layer

`v1/epistemic.py` declares itself the contract ("**This module is the contract.** Agents
build against it and must not change it"). V2 must therefore compose with it, not around it.
Three interactions, one of which is a genuine conflict.

### 8.1 Compatible: the justification lattice

`EpistemicStatus` (16 values) and `Justification` (6 values) classify **claims**; `Warrant`
classifies **steps**, and `transformation.py:227-236` already states that conflating them
"would let 'I cited a rule' read as 'I have a proof'". V2 keeps both and keeps them apart:
a derivation carries a `Warrant`; the goal it establishes carries an `EpistemicStatus`.

Mapping, for the English and report backends:

| derivation state | goal it supports reaches | `Justification` |
|---|---|---|
| VERIFIED, empty dependency set | `PROVED` | `PROOF` |
| VERIFIED, non-empty dependency set | `MODEL_CONDITIONAL` | `ASSUMPTION` |
| VERIFIED with rule kind `REFUTATION` | `DISPROVED` | `REFUTATION` |
| VERIFIED with rule kind `STATISTICAL` | `ESTIMATED` / `CONSISTENT_WITH` | `EVIDENCE` |
| CHECKED but obligations open | `CONJECTURED` | `NONE` |
| PROPOSED / REJECTED | `UNSUPPORTED` | `NONE` |

The fourth row is the one that matters. `Operation.INFER` carries the weakening "a
statistical inference yields Evidence, not Proof; the conclusion does not follow deductively"
(`transformation.py:614-625`), and `DISCHARGES_GOALS[EVIDENCE]` is `False`. So a VERIFIED
statistical derivation **does not make its goal PROVED**, and the kernel must not let it. A
`proved g by d` where `d`'s rule has `EdgeKind.STATISTICAL` is a diagnostic (`HML-R907`),
not a proof. This is the surface-language form of the prohibition
`v1/epistemic.py` was written to enforce.

### 8.2 Compatible: the probability-kind barrier

`PROHIBITED_PROBABILITY_COERCIONS` and the type lattice keep `Probability`, `PValue` and
`PosteriorProbability` pairwise incomparable. V2 introduces the first construct that could
breach this — substitution. Handled in `SEMANTICS.md` §3.2.

### 8.3 **Conflict: `DISCHARGES_GOALS[ASSUMPTION] = False` versus discharge-by-assumption**

This is a real conflict between an existing contract and a requirement of this build, and it
must be resolved explicitly rather than by whichever code runs last.

* `v1/epistemic.py:96-103` states: only `PROOF` and `REFUTATION` discharge goals;
  `ASSUMPTION` does not, with the reason "an assumption is granted, not established; it
  carries forward as a dependency".
* The build requires that `assume x > 0` **discharges** an `x > 0` obligation.

**Resolution: an obligation is not a goal, and the two words must not be run together.**

| | GOAL | OBLIGATION |
|---|---|---|
| what it is | something we set out to establish | a side condition a rule application owes |
| what closes it | a proof or a refutation | *availability* of the condition in the current context |
| may an assumption close it | **no** (`DISCHARGES_GOALS`) | **yes**, and doing so records a dependency |

An assumption cannot make a goal true. It can make a side condition *available*, which is
precisely what "assume x > 0; then log x is defined" means in ordinary mathematics — the
audit's C-1 calls this "every ordinary mathematical argument" and records that it is
currently unwritable.

The conflict is therefore terminological, not substantive, **provided** the dependency is
recorded and propagated (§6) and the goal-level prohibition stays intact. Two mechanical
tests keep it that way:

* `test_assumption_cannot_prove_a_goal` — `discharge o by a1` where `a1` is an `assume`
  succeeds; `proved g by a1` is a diagnostic.
* `test_dependency_survives_to_the_goal` — a goal PROVED through a derivation whose
  obligations were discharged by assumption reports a non-empty dependency set, and its
  English rendering uses `EpistemicClaim.render_english` for `MODEL_CONDITIONAL`
  ("Under model …"), not for `PROVED`.

**If the lead prefers not to accept this**, the alternative is to give the operation a
different name (`satisfy`, `assume-discharge`) so the word `discharge` never appears next to
an assumption. That is a naming decision, not a semantic one, and this model works under
either. It is recorded as `DESIGN_LOCK.md` D-V2-004.

### 8.4 Diagnostics

The `HML-R9xx` family is allocated to the reasoning layer. It is free at base: `grep -rc
"HML-R" src` returns no matches, whereas `HML-X6xx` (used by `transformation.py`) shares its
numeric range with the documented `HML-S6xx` semantic family and the documented range table
in `diagnostics/__init__.py:7-14` does not mention the `E`, `G`, `V` or `X` families that are
already in use. Extending that table is a small, separate hygiene item.

| code | meaning |
|---|---|
| `HML-R901` | circular derivation graph |
| `HML-R902` | premise does not resolve in the claim namespace |
| `HML-R903` | unknown rule |
| `HML-R904` | stated conclusion is not what the rule produces (this is R8, the check that matters) |
| `HML-R905` | `proved` names a derivation that is not VERIFIED |
| `HML-R906` | `proved` names a VERIFIED derivation whose conclusion is not the goal |
| `HML-R907` | `proved` by a derivation whose justification is Evidence, not Proof (§8.1) |
| `HML-R908` | `discharge` names evidence that does not entail the obligation |
| `HML-R909` | an authored `obligation` does not correspond to a generated one |

---

## 9. Where the existing code makes this harder than it looks

Three findings. All three are measured. The first two are the reason `DESIGN_LOCK.md`
disagrees with part of the locked plan; the third is, in this document's judgement, the
highest-value single fix in the build.

### 9.1 `v1/transformation.py` is a catalogue, not a kernel

Its own module docstring says so: *"Nothing here claims to check a side condition. The layer
records the obligation, names the edge that generated it, and refuses to let it disappear."*
Two structural facts follow, and both matter for the build:

* **Edges relate names, not expressions.** `TransformationEdge.source: tuple[str, ...]`,
  `target: str`, `Node.text: str`. There is no `Expr` anywhere in the module. It therefore
  cannot perform check R8 — reproducing the rule's output and comparing canonical forms —
  because it never holds an output to compare.
* **Obligations are format strings.** `OperationSpec.obligations` is
  `tuple[tuple[str, ObligationKind], ...]` and `TransformationEdge.obligations()` produces
  `Obligation.condition: str` by `template.format_map(ctx)`. The discharge machinery in
  `verification/obligations/checkers.py` consumes `Expr`, not text.

Consequence, stated plainly: **if V2 reuses the obligation templates verbatim, every
generated obligation is UNKNOWN by construction**, because nothing can parse `"{by} != 0"`
into something a checker can decide. The reasoning layer would be able to state obligations
and never discharge one — which is the state the audit already records, moved to a new file.

The reuse is still right; the *scope* of the reuse is what must be fixed. See
`DESIGN_LOCK.md` D-V2-002 for the recommendation and the two rejected alternatives.

### 9.2 Two silent-loss holes that V2 opens in the canonical and surface layers

Measured on the pristine base:

```
canonical of an unknown statement : {"canonical_version":"hml-canonical-0.1.0",
                                     "module":"X","statements":[{"kind":"DeriveStmt"}]}
two DIFFERENT derivations collide in content_hash : True
hml surface text                  : 'module X\n\n# <unrenderable DeriveStmt>\n'
hml backend reports faithful      : True   (unsupported == [])
```

`backends/canonical.py:244` falls through to `{"kind": type(st).__name__}` and
`backends/hml.py:225` falls through to a comment, neither calling `drop()`. Landing V2
statements without extending both would:

* **identify objects that differ**, which maturity criterion 2.4 forbids in terms and which
  the audit currently scores `PASS`; and
* **omit a construct silently**, which criterion 2.7 calls "a hard failure" and which
  `backends/base.py` calls the worst failure mode in the codebase — currently scored `PASS`
  with "0 truly silent losses".

V2 would demote two criteria the project passes today. The fix is small: close both
fall-throughs (raise, or `drop()`), and extend both dispatchers. There is one safety net
already in place — `spec/ir.schema.json` rejects an unknown `kind`, verified here:

```
fallthrough doc REJECTED by schema: 'DeriveStmt' is not one of
  ['Declaration','Definition','Law','Assumption','Constraint','Theorem',
   'Objective','Solve','Inference','Check','Concept']
```

but it only fires in `scripts/conformance.sh`, and only for files under `examples/`.

A third, smaller instance of the same class: `ast/nodes.py::walk` descends only into
`Node`, `Arg` and `ConceptMember` (lines 369-385). A new role-labelled rule-argument class
that is not one of those three is **invisible to `walk`**, and `walk` is what
`engine.py::_provenance_map`, `_signature_tasks` and the backends use to find expressions.
Rule arguments would silently escape every one of them. Either make the rule-argument class
a `Node`, or reuse the existing `Arg`.

### 9.3 `assume` does not merely fail to discharge — it lets the verifier *refute*

The audit records (C-1) that `assume x > 0.0` does not discharge `log`'s domain. The
situation is worse than that, and this appears not to be recorded anywhere. Measured:

```
module A                                    module B
var x : Real                                var x : PositiveReal
assume x > 0.0                              prove x > 0.0
prove x > 0.0
                                            → VERIFIED
→ DISPROVED
  [FAILED] numerical_counterexample/universal  x > 0.0
    witness: this assignment satisfies every declared type constraint
             and makes the obligation false
```

The verifier does not report "cannot tell". It reports **DISPROVED**, with a witness, for a
goal that follows in one step from the module's own stated assumption. The cause is exactly
one location: `verification/obligations/evaluate.py::build_environment` (lines 169-229)
reads `Declaration`, `DefineStmt` and `ConceptDecl`, and never reads `AssumeStmt`. The
counterexample search then draws `x = -1` from the *declared* domain of `Real`, which the
assumption was supposed to have narrowed.

This is a confident false negative, which `records.py` and `engine.py` both identify as the
failure mode they were built to prevent. It is also cheap to fix — assumptions must enter
the environment as interval narrowings, which is `OBLIGATIONS.md` §4.2 — and until it is
fixed, **no derivation that depends on an assumption can be VERIFIED, and some will be
actively refuted.** It is a precondition for the rest of this model, not an enhancement.

---

## 10. What was and was not run

| check | command | result |
|---|---|---|
| `prove 1.0 = 2.0` compiles clean | `.venv/bin/hml check t1.hml` | `ok: T1 (2 statements, …)`, exit 0 — **reproduces** |
| `assume` does not discharge `log` | `.venv/bin/hml check t2.hml` | `HML-T427`, exit 1 — **reproduces** |
| catalogue inventory | `python -c "from hamiltonian_lang.v1 import transformation …"` | 30 operations, 30 specs, 9 edge kinds, 5 obligation kinds, 8 inference rules, 9 prohibited coercions — **as stated by the lead** |
| strict canonical additivity | pristine-HEAD script, §9.2 | a v1-only module is **byte-identical** after adding a `Statement` subclass |
| canonical fall-through collision | pristine-HEAD script | two different derivations share a content hash — **True** |
| HML surface silent loss | pristine-HEAD script | `faithful == True` with the statement replaced by a comment |
| assumption discharge intervals | `Interval.entirely_above` on `(0,∞)` and `[0,∞)` | see `OBLIGATIONS.md` §6 — all three required cases behave correctly |
| `assume` + `prove` verdict | `verify_source` | **DISPROVED** with a witness (§9.3) |
| `HML-R` code family free | `grep -rc "HML-R" src` | no matches |
| schema rejects unknown kinds | `jsonschema.validate` | rejected, message quoted in §9.2 |
| **full test suite** | `python -m pytest -q` | **NOT RUN.** The worktree is being edited concurrently by the implementation workstream; a suite result taken mid-edit would not be attributable to anything. |
| **anything in this model** | — | **NOT IMPLEMENTED and therefore NOT TESTED.** Every test named in this document is a proposal, not a result. |
