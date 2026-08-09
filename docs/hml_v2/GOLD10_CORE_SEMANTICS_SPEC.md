# Gold-10 core semantics — normative specification

**Status: normative.** This is the design record for the Gold-10 core repair. Code that
disagrees with this document is wrong, or this document must be amended first and the
amendment justified. Written before implementation, per the engineering brief §I.

Base SHA `22b4bb7` (branch `feature/hml-reasoning-kernel-v2`). The corpus pinned
`164d1946`; `git diff --name-only 164d1946..22b4bb7 -- src/` is **empty**, so the forensic
triage in `docs/agent_handoffs/CODEX_GOLD10_GAP_TRIAGE_INBOUND.md` describes exactly this
core. Nothing in it needed re-deriving.

Scope: the two generic core-semantic gaps Gold-10 exposed (GAP-0003, GAP-0004) and the one
integration boundary (checked certificates). Probability, calculus, arithmetic rewriting
and function-evaluation *laws* are explicitly out of scope and stay in libraries.

---

## 0. What is being added, in one paragraph

Three things. (1) A **context-relative entailment judgment** — a four-valued adjudication
of a target against a premise set, of which certified underdetermination is one value and
"we could not tell" is a *different* value. (2) A **checked-certificate boundary** — one
gate through which non-kernel capability may become evidence, with a static registry of
trusted checkers, so that mathematics can grow without the trusted kernel growing. (3)
**Universal introduction and elimination** — the generic quantifier basis, with a real
eigenvariable condition and capture-avoiding instantiation. Nothing else. No domain
mathematics enters the kernel.

---

## 1. Mapping onto the existing repository

Extend, do not duplicate. Concretely:

| Concern | Existing structure | Action |
|---|---|---|
| evidence dependency graph | `reasoning/evidence.py` `EvidenceGraph`, `EvidenceClass`, `EdgeKind` | **extend** — new claims join this graph; no second graph is built |
| inference rules | `reasoning/kernel.py` `RULES`, `RuleSpec` | **extend** — two rules, plus a `side_conditions` field |
| goal vocabulary | `ast/nodes.py` `GoalStatus` | **extend** — `UNDERDETERMINED` added as a *projection* (§3.4) |
| exact evaluation | `verification/obligations/evaluate.py` `evaluate`, `Environment`, `build_environment` | **reuse unchanged** — wrapped by checkers, never reimplemented |
| free variables | `evaluate.free_names`, plus `binders.free_symbols` for symbol-level questions | **reuse** |
| binder identity / alpha-equivalence | `SymbolId.canonical()`, `backends/canonical.expr_identity` | **reuse** — the only notion of identity anywhere in this work |
| substitution | `kernel._substitute` (refuses to enter binders) | **not extended** — see §4.4 |
| certificates | *none exists* | **new** — `reasoning/certificates/` |
| binder abstraction/instantiation | *none exists* | **new** — `reasoning/binders.py` |

`reasoning/evidence.py` is a *dependency graph*, not a certificate boundary. The inbound
triage describes it as the "evidence/provenance boundary", which overstates it: it
classifies claims and validates acyclicity, and has no concept of a certificate, a checker
or an external result. That is why §2 is new code rather than an extension.

---

## 2. The checked-certificate boundary

### 2.1 Why one boundary and not many rules

HML already contains capability that can decide real questions — exact rational
evaluation, definitional unfolding, symbolic equivalence, partiality analysis — and none
of it could feed the v2 `derive`/`proved` path, which admits exactly one source of truth: a
rule in the kernel. Adding a rule per capability grows the trusted computing base once per
mathematical fact anyone wants. Arithmetic, probability and calculus are not universal
reasoning semantics; they are domain knowledge, and domain knowledge belongs in libraries.

So: one gate.

```
    claim + context + dependencies + payload + checker id
        -> registered trusted checker
        -> REJECT  |  CheckedEvidence
```

### 2.2 The envelope

`CertificateEnvelope` binds a certificate to the *exact* mathematics it was issued about:

```
certificate_type       what kind of certificate this is
certificate_version    schema version of the payload
checker                registry key; the version is part of the key (§2.3)
claim_hash             expr_identity of the conclusion
context_hash           identity of Γ (§3.3)
premise_hashes         ordered expr_identity of each declared dependency
payload                checker-specific, opaque to the boundary
```

**Execution metadata — timestamps, durations, log paths, host, solver build — must never
enter semantic identity.** Provenance is recorded beside the mathematics, never inside it.
This is the existing rule (`GRAMMAR_CONTRACT.md` §0.5, D-034 E1/E10) applied to
certificates.

The hashes are the anti-replay mechanism. A certificate is about one claim in one context
resting on one premise list. Change any of them and the envelope no longer matches, so the
certificate does not apply. It does not "mostly apply" and it does not degrade to a
warning: it fails closed.

### 2.3 The static trusted registry

`CHECKERS` is a table in the repository. It is populated at import by the checker modules
themselves and there is **no registration API reachable from HML source, from a module
being checked, or from library data.** The reason is blunt: if a library could register a
checker, a library could register

```python
def always_valid(envelope, ctx): return VALID
```

and the entire trusted computing base would be gone. Libraries may *refer* to a checker by
name. They may not supply one.

The version is part of the registry key — `closed_eval_v1`, not `closed_eval` at version
1. When semantics change, the key changes, and modules naming the old key stop validating
instead of silently acquiring new behaviour. An unknown key is a rejection, never a
warning and never "unsupported, continue".

### 2.4 Fail-closed, exhaustively

Every one of these is INVALID, and each has a test:

* unknown checker key;
* checker not permitted to reach the stated judgement;
* a declared dependency that does not resolve;
* `claim_hash` / `context_hash` / any `premise_hash` disagreeing with the actual claim,
  context or premises;
* malformed, incomplete or wrongly-typed payload;
* an expression outside the checker's supported fragment;
* the checker reporting VALID without naming what it established;
* the checker establishing something not canonically identical to the stated claim;
* **any exception raised by a checker at all.**

There is no code path on which a failure becomes a pass. A checker that raises has
established nothing; letting the exception escape would abort the compile, and treating it
as a pass would be catastrophic, so it is INVALID with the cause preserved.

### 2.5 `CheckedEvidence` is unforgeable

`CheckedEvidence` is the only object the reasoning layer accepts as certificate-derived
support. It is constructible **only** by the trusted validation path — enforced by a
module-private construction token, and asserted by a test that direct construction raises.
Surface HML cannot produce one; library data cannot produce one; a payload cannot contain
one.

### 2.6 Evidence kinds are orthogonal to claim status

A separate axis from `DerivationStatus` / `GoalStatus`. What *kind* of support a claim has:

| kind | may establish VERIFIED? |
|---|---|
| `NATIVE_KERNEL` | yes, when dependencies and obligations close |
| `CHECKED_CERTIFICATE` | yes, **only** after the HML-side trusted checker validates the exact envelope |
| `UNTRUSTED_ORACLE` | **never** directly |
| `NUMERIC_BOUND` | never for exact equality; only for the corresponding bounded/approximate proposition |
| `NONE` | no verification |

"SymPy says true", "Z3 says sat", "the model said proved", "the CAS returned a result" are
all `UNTRUSTED_ORACLE`. They may be recorded. They never manufacture VERIFIED.

### 2.7 Trust classification of `equivalence/symbolic.py` — decided

**`UNTRUSTED_ORACLE`. It is not routed through the boundary.**

The module is named for certificates and its docstring calls its three procedures
"trusted", but the decisions ultimately rest on raw SymPy success flags:
`simplify(a - b) == 0` certifies equality, and propositional validity is decided by
`satisfiable(...)` returning `False`. HML performs **no independent replay** of either. Per
brief §XI.C that keeps it below VERIFIED, and promoting it merely because the source uses
the word "certificate" is exactly the error the brief names.

This is a decision about *trust*, not about quality — the module is careful, and its
refusals (dependent atoms, symbolic signs) are well-judged. It stays available for
equivalence scoring, where it already lives. It simply may not certify a v2 derivation.

**Consequence, recorded honestly:** the Gold-10 G07 body `n + 0 = n` has a free variable,
so `closed_eval_v1` cannot decide it, and symbolic equivalence may not certify it. G07's
body therefore remains **library-level** after this work. That is the correct layering, and
per brief §XII the quantifier core is tested independently of it (§4.5).

---

## 3. GAP-0003 — context-relative entailment judgment

### 3.1 Four values, and the one that matters

```
adjudicate(Γ, P) -> ENTAILED | REFUTED | UNDERDETERMINED | UNKNOWN
```

| verdict | meaning |
|---|---|
| `ENTAILED` | Γ ⊨ P |
| `REFUTED` | Γ ⊨ ¬P |
| `UNDERDETERMINED` | there are checked models M⁺ ⊨ Γ with M⁺ ⊨ P, and M⁻ ⊨ Γ with M⁻ ⊨ ¬P |
| `UNKNOWN` | the supported checker cannot establish any of the above |

**`UNKNOWN` is not `UNDERDETERMINED`, and no code path converts one into the other.** None
of the following may ever produce `UNDERDETERMINED`: search failed, proof not found,
timeout, unsupported syntax, unsupported semantic fragment, partial model, incomplete
assignment, an external solver answering "unknown", or absence of evidence. Certified
underdetermination is a *positive* result carrying two models. Ignorance carries nothing.
This is hard scientific invariant §XVIII.1 and it is the single most important property in
this document.

### 3.2 The two-model certificate, V0 fragment

**Supported fragment: finite ground classical propositional logic** over declared `Bool`
names. No first-order completeness is claimed, now or by implication.

`propositional_underdetermination_v1` payload: a positive model and a negative model, each
a total assignment of declared Boolean atoms to literal `true`/`false`.

The checker independently validates, and rejects on any failure:

1. both models range over exactly the declared semantic signature;
2. every assigned value is a Boolean literal of a `Bool`-typed name — no numeric coercion,
   so the evaluator's `raw != 0` convention cannot be exploited with `2`;
3. every free atom of Γ ∪ {P} is assigned — partial models are rejected, not completed;
4. no name is assigned twice or assigned outside the signature;
5. **every premise of Γ evaluates TRUE under both models**;
6. P evaluates TRUE under M⁺;
7. P evaluates FALSE under M⁻;
8. envelope `claim_hash`, `context_hash` and `premise_hashes` match the actual claim,
   context and premises;
9. anything the evaluator raises `Undecidable` on fails closed as `UNKNOWN`, never
   `UNDERDETERMINED`;
10. every evaluation is `exact`; an inexact value settles nothing.

Condition 5 does double duty: two models satisfying Γ also **certify that Γ is
satisfiable**, so an inconsistent Γ — which entails everything — cannot reach
`UNDERDETERMINED` by this route. That is not a happy accident; it is why the certificate
demands models of Γ rather than of P alone.

The existing evaluator is sound for this job. Verified on the G06 fragment: with
`P implies Q`, `Q`, the four assignments give exactly the classical truth table, every
value `exact`, and `Environment.bool_names` correctly identifies the `Bool` atoms. It is
reused unchanged rather than reimplemented.

### 3.3 Context binding, and why Γ is hashed

An underdetermination certificate is a claim about a *theory*. Non-entailment from a
subset of Γ says nothing about Γ: adding premises can only increase what is entailed, so a
certificate issued against `{a1}` must not survive into a module that also asserts `a2`.

Therefore adjudication requires that the certificate's declared dependencies **cover every
established claim in scope at the goal**. A certificate that omits one is rejected with a
diagnostic naming the missing premise. `context_hash` binds the whole set, so a later edit
to Γ invalidates the certificate rather than silently carrying it forward. This is brief
§III's invariant "change Γ ⇒ the previous certificate does not silently apply", and
hard invariant §XVIII.8.

### 3.4 Representation: judgment first, status as projection

`Adjudication` is the semantic source of truth. It binds verdict, target identity, context
identity, ordered premise identities, evidence identity, and checker identity.

`GoalStatus.UNDERDETERMINED` exists as a **projection** of a successfully checked
`Adjudication` — present so existing consumers keep working. Setting the enum is not a
proof and never constitutes one: the status is written only by the adjudication path, from
a validated certificate. No certificate ⇒ no `UNDERDETERMINED`.

The five goal states remain semantically distinct and are separately tested:
`OPEN` (nothing adjudicated) · `PROVED` (verified derivation) · `REFUTED` ·
`UNSUBSTANTIATED` (a proof was claimed and failed) · `UNDERDETERMINED` (certified).

---

## 4. GAP-0004 — the quantifier core

### 4.1 Two rules, not a "theorem application" primitive

`forall_intro` and `forall_elim`. Ordinary theorem application composes from *library
theorem + forall elimination + existing substitution/rewrite machinery* rather than
becoming a third large trusted primitive. Existential introduction and elimination are
**deliberately not implemented** — Gold-10 exposed no such gap. Recorded as an expected
sibling for a future mission, not scope-crept into this one.

### 4.2 Universal introduction

```
    Γ, a : D (arbitrary) ⊢ φ(a)
    ---------------------------
        Γ ⊢ ∀x : D . φ(x)
```

The eigenvariable condition: **`a` must not occur free in any undischarged assumption on
which the body proof depends.**

HML discharges obligations against Γ by `RefinementEnv.entails`, not only through cited
premise edges, so a derivation can depend on an assumption without a premise edge to it.
Checking only the premise closure would therefore leave a hole. The implemented condition
is deliberately stronger and simpler: **`a` may not occur free in any assumption in scope
at the derivation.** This rejects some sound generalisations — but every assumption it
trips on genuinely constrains `a`, and over-rejection is the safe direction.

`assume a = 0` followed by generalisation to `forall x : D . φ(x)` is therefore rejected.
That is red-team case §VII.negative.1 and it is the whole point of the condition.

### 4.3 Binder construction is re-depthing, not wrapping

HML's canonical identity is locally nameless: `SymbolId.canonical()` is
`sym:#<depth>.<ordinal>`. The resolver numbers a binder at nesting depth *d* as `depth=d`
and module-level declarations as `depth=0`. Measured on this tree:

```
var n : Natural
assume a1 : n + 0 = n                        -- refs are sym:#0.0
goal   g1 : forall n : Natural . n + 0 = n   -- binder and refs are sym:#1.0
```

So the premise's `n` and the conclusion's `n` are **different symbols**, and wrapping the
premise in a `Quantifier` would build a term that is *not* canonically identical to the one
the resolver builds from the same text — the step would be rejected for a reason unrelated
to its validity.

`binders.abstract` performs the real operation: every binder and every reference to a
binder descends one level, the eigenvariable becomes the new outermost binder, and
references to other module-level names stay at depth 0. Verified against the resolver's own
parse for the flat case, a free module constant, nested `forall`/`forall`, mixed
`forall`/`exists`, and a second free module variable.

This introduces **no second notion of identity**. It rearranges symbols so that the
existing `expr_identity` can decide the comparison.

### 4.4 Universal elimination

```
    Γ ⊢ ∀x : D . φ(x)      t : D
    ----------------------------
            Γ ⊢ φ[t/x]
```

* substitution is capture-avoiding: `binders.instantiate` refuses any `t` mentioning a
  bound name, because such a term is only meaningful relative to a binder that does not
  enclose the substitution site;
* nested binders retain identity — the inverse re-depthing of §4.3, one shared traversal;
* alpha-renamed inputs behave identically, by construction, since identity ignores
  spelling;
* domain conformance is required: `t`'s resolved type must conform to `D` via the existing
  `types.is_subtype`. A mismatch rejects;
* definedness and refinement obligations generated by the resulting term survive, because
  `check.py` derives obligations from the conclusion's *terms* (the term-level pass), not
  from the rule.

`kernel._substitute` is **not** extended to enter binders. It deliberately refuses, and
that refusal is load-bearing for the existing rules. `binders.instantiate` is the
capture-avoiding path, used only where a binder is genuinely being eliminated. One
substitution system per job, neither reimplementing the other.

### 4.5 Testing the quantifier core independently of arithmetic

Per §2.7 the G07 body is not certifiable in this mission. `forall_intro` is therefore
tested on bodies established by generic means — an assumption over an arbitrary variable,
and a kernel-derived equality — so that the rule's correctness is demonstrated without any
arithmetic identity being hard-coded. Hard invariant §XVIII.4 and §XVIII.7: a `forall`
proof over an arbitrary variable is not a check of sample values, and arithmetic
computation is not a primitive logical inference rule.

### 4.6 Side conditions in a context-free kernel

The kernel is deliberately context-free: it builds a conclusion from premises and arguments
and never consults the claim. The eigenvariable condition and domain conformance are
*context-dependent*, so they cannot live inside `kernel.apply`.

`RuleSpec` gains `side_conditions: tuple[str, ...]`. The kernel still builds the conclusion
blind; `check.py` — which holds the module, the symbol table and the evidence graph —
evaluates the named conditions from a static table. An unknown side-condition name is a
**rejection**, so a rule can never be admitted by a condition nobody implemented.

---

## 5. Invariants this work must not break

Carried from `reasoning/evidence.py` `INVARIANTS` and the semantic constitution. Every
`CheckedEvidence` joins the ordinary evidence graph and is subject to all of them:

* the evidence graph is acyclic (E1/E9);
* a goal, requirement or conjecture cannot be laundered into evidence (E2) —
  and **`DETERMINES_NEITHER` evidence may never be a premise**: "P is undetermined" does
  not give you P, and treating it as though it did would be the worst failure available
  here, so it is classified `NOT_EVIDENCE`;
* VERIFIED depends only on valid scoped assumptions and verified evidence (E3);
* transitive open obligations prevent VERIFIED (E4);
* provenance is complete (E7);
* imported evidence carries an explicit environment version (E8);
* `PARSES` ≠ `TYPECHECKS` ≠ `HAS_DEFINED_DENOTATION` ≠ `IS_SEMANTICALLY_EQUIVALENT` ≠
  `IS_ENTAILED` ≠ `EXECUTES` ≠ `IS_PROVEN`.

## 6. Trusted computing base after this work

**Trusted:** canonical IR and identity · name/scope resolution · type and refinement
checking · the evidence graph and status checker · the inference kernel · the certificate
boundary itself · the registered checkers listed in §2.3 · the exact HML-owned evaluator
(`verification/obligations/evaluate.py`), deliberately admitted.

**Untrusted:** SymPy and `equivalence/symbolic.py` · any SMT/CAS output · LLMs · search
and tactics · corpus extraction · arbitrary libraries · pretty printers · model
suggestions · external heuristics.

The TCB grew by: the boundary, three small checkers, and one evaluator that was already in
the tree. It did not grow by any domain mathematics.

## 7. Grammar-contract drift — recorded, not fixed here

`docs/hml_v2/GRAMMAR_CONTRACT.md` §1 specifies five statement forms including `obligation`
and `discharge`, which are **not implemented**; the parser instead implements `scope`,
which the contract does not list. Its `derive` production (`... by <rule> yields <prop>`)
also differs from the implemented form (`derive <name> : <prop> from ... by <rule>`), and
its `GoalStatus` line lists `ASSERTED_UNCHECKED`, which is not in `ast/nodes.py`.

This drift predates this mission and is **not repaired here** — a broad grammar rewrite is
out of scope. The contract is amended only where required to make the new semantics
truthful, and the remaining discrepancies are reported to Codex in the handoff.
