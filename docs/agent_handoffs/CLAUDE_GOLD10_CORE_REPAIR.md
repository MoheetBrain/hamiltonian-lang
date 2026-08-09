# Gold-10 core repair — handoff to Codex

Response to `reports/GOLD_10_GAP_TRIAGE_HANDOFF.md` (corpus `467a486`), a copy of which is
preserved here as `CODEX_GOLD10_GAP_TRIAGE_INBOUND.md` with an identical SHA-256.

**No corpus file was read for write, modified, or created. No frozen experimental artifact
was touched. 0 model calls, 0 training, 0 arena calls.**

---

## SHAs

| | |
|---|---|
| **BASE_SHA** | `22b4bb79e589dcd5e9b52d92d6d20c94ee2e0b7c` |
| **FINAL_SHA / PIN THIS** | `5688aba18632b65a8709aa1d85577d31a67dba6a` |
| branch | `feature/hml-reasoning-kernel-v2` |
| corpus pin inspected | `164d1946e91216c093478132caa0d06427259682` |

**Pin `5688aba`.** It contains every source change. Any commit after it on this branch is
documentation only — verify with `git diff --stat 5688aba..HEAD -- src/`, which must be
empty.

**Your triage inspected exactly the right core.** `git diff --name-only 164d1946..22b4bb7 --
src/` is **empty**: the three commits between the pin and this work were all
arena/evaluation. Nothing in your report needed re-deriving against later semantics, and the
brief's "current HEAD has conflicting later semantics" stop condition did not apply.

One correction to the triage, minor but worth having: it describes `reasoning/evidence.py`
as the "evidence/provenance boundary". It is a dependency **graph** over claims with cycle
validation and evidence classes; it has no concept of a certificate, a checker or an
external result. That is why the boundary below is new code rather than an extension of it.

---

## 1. Certificate architecture

One gate, not a rule per capability. Adding a trusted rule for every mathematical fact
anyone wants grows the TCB without limit; arithmetic, probability and calculus are domain
knowledge, not universal reasoning semantics.

```
claim + context + dependencies + payload + checker id
    → registered trusted checker
    → REJECT  |  CheckedEvidence
```

**`CertificateEnvelope`** binds a certificate to the exact mathematics it was issued about:
`certificate_type`, `certificate_version`, `checker`, `judgement`, `claim_hash`,
`context_hash`, `premise_hashes`. Execution metadata — timestamps, durations, log paths —
**never** enters semantic identity.

**`CheckedEvidence`** is the only object the reasoning layer accepts as certificate-derived
support, and it is constructible **only** by the validation path (module-private mint
token). Direct construction raises; a test asserts it. Surface HML cannot produce one and
neither can library data.

**Evidence kinds are orthogonal to claim status.** `NATIVE_KERNEL` and
`CHECKED_CERTIFICATE` may support VERIFIED. `UNTRUSTED_ORACLE`, `NUMERIC_BOUND` and `NONE`
never can.

Fail-closed, each with a test: unknown checker · checker reaching a judgement it does not
offer · unresolvable dependency · claim/context/premise hash mismatch · malformed payload ·
unsupported fragment · VALID without naming what was established · establishing something
other than the claim · **any exception a checker raises**.

## 2. Trusted checkers

The registry is **static and in-repository**. There is no registration API reachable from
HML source, from a module being checked, or from library data — a library able to register
`def always_valid(...): return VALID` would end the TCB. Libraries may *refer* to a checker
by name. The version is part of the key, so changed semantics means a changed name and old
modules stop validating rather than silently acquiring new behaviour.

| checker | judgement | fragment | trust rests on |
|---|---|---|---|
| `closed_eval_v1` | ENTAILS | closed propositions over exact rationals; no free names, no definitions | `verification/obligations/evaluate` — HML-owned exact evaluator. No CAS, no solver. Floats rejected, not rounded. |
| `definition_unfold_v1` | ENTAILS | claims closed after unfolding user definitions and parameterised functions | the same evaluator, with bounded recursive unfolding and cycle detection. Records which definitions it used. |
| `propositional_underdetermination_v1` | DETERMINES_NEITHER | finite ground classical propositional logic over declared `Bool` names | the same evaluator used as a model checker. **No SAT/SMT solver participates** — both models come from the author and are re-evaluated here. |

**`equivalence/symbolic.py` is NOT registered, and this is a decision, not an oversight.**
Its own docstring states that `simplify(a - b) == 0` certifies equality and that
propositional validity is decided by `satisfiable(...)`. HML performs **no independent
replay** of either, so the verdict rests on a raw SymPy success flag. That makes it
`UNTRUSTED_ORACLE`: available for equivalence scoring where it already lives, and barred
from certifying a v2 derivation. A test asserts no checker with `symbolic`/`sympy` in its
name is ever registered, so if someone adds one later the trust argument has to be made
explicitly.

## 3. Underdetermination

### Exact semantic contract

```
adjudicate(Γ, P) → ENTAILED | REFUTED | UNDERDETERMINED | UNKNOWN
```

`UNDERDETERMINED` holds when there are checked models `M⁺ ⊨ Γ` with `M⁺ ⊨ P` and `M⁻ ⊨ Γ`
with `M⁻ ⊨ ¬P`. The checker independently validates: both models range over exactly the
declared signature; every value is a Boolean literal (so the evaluator's `raw != 0`
convention cannot be exploited with `P := 2`); every free atom of Γ ∪ {P} is assigned;
**every premise evaluates TRUE under both models**; P is true under M⁺ and false under M⁻;
every evaluation is exact.

Requiring both models to satisfy Γ also certifies **Γ satisfiable**, so an inconsistent
context — which entails everything — cannot reach this status by this route.

### Unsupported behaviour

Anything outside finite ground propositional logic over declared `Bool` names is `UNKNOWN`
and the goal stays `OPEN`. **No first-order completeness is claimed.**

**`UNKNOWN` never becomes `UNDERDETERMINED`.** Not from a failed search, a timeout, an
unsupported fragment, a partial model, an external solver shrugging, or absence of evidence.
The separation is structural: `EntailmentVerdict` is a four-valued type and is the semantic
source of truth; `GoalStatus.UNDERDETERMINED` is its *projection*, writable only by the
adjudication path.

### Context binding

Two requirements neither the triage nor the engineering brief spelled out. Both are
soundness, not polish, and both are enforced and tested:

1. **A non-entailment certificate must cover every established claim in scope.** Entailment
   is monotone, so Γ ⊭ P proved against a subset says nothing about Γ. A certificate that
   omits a premise is rejected, naming the missing one.
2. **A certificate is not spendable after the context changes.** `context_hash` is computed
   at issuance and re-derived at adjudication; a premise asserted in between invalidates it.

## 4. Quantifiers

```
    Γ, a : D (arbitrary) ⊢ φ(a)              Γ ⊢ ∀x : D . φ(x)     t : D
    ---------------------------              ------------------------------
        Γ ⊢ ∀x : D . φ(x)                             Γ ⊢ φ[t/x]
```

**Eigenvariable condition — deliberately stronger than the textbook rule.** Read literally
it quantifies over "undischarged assumptions the body proof depends on", which as a premise
closure would leave a hole: HML discharges obligations against Γ through
`RefinementEnv.entails`, not only through cited premise edges, so a derivation can rest on
an assumption it never names. Implemented instead: **no assumption in scope, including
inside `scope` frames, may mention the variable freely.** This over-rejects; that is the
safe direction.

**Capture avoidance.** `forall_elim` refuses any instantiation term mentioning a bound name.
Domain conformance is required via the existing `types.is_subtype` and fails closed when
either type is unknown.

**Binder construction is re-depthing, not wrapping** — the part most likely to be got wrong
by a reimplementation. Identity is locally nameless (`sym:#<depth>.<ordinal>`), so a
premise's module-level `n` (`sym:#0.0`) and a conclusion's bound `n` (`sym:#1.0`) are
different symbols. Wrapping the premise in a `Quantifier` builds a term the resolver never
produces, and the step would be rejected for a reason unrelated to its validity.
`reasoning/binders.py` re-depths the subtree. **No second notion of identity was
introduced** — the test uses the resolver's own parse as the oracle, on five shapes.

**The kernel stays context-free.** Neither condition is local to the premises, so
`RuleSpec.side_conditions` names them and `check.py` answers them from a static table. An
unknown name **rejects**.

Existential intro/elim: **deliberately not implemented.** Gold-10 exposed no such gap.
Recorded as an expected sibling for a future mission.

## 5. Existing capabilities reused, not rebuilt

| capability | module | how it is used |
|---|---|---|
| exact rational evaluation | `verification/obligations/evaluate.evaluate` | unchanged; wrapped by all three checkers |
| definition/function unfolding | same | unchanged; `definition_unfold_v1` records the dependency set |
| `Environment`, `bool_names`, assignments | same | a model is a `Mapping[str, Fraction]`; verified to implement correct classical propositional semantics on the G06 fragment before being relied on |
| free names | `evaluate.free_names` | signature computation for the model checker |
| binder identity / alpha-equivalence | `SymbolId.canonical`, `backends/canonical.expr_identity` | the only notion of sameness anywhere in this work |
| scope frames | `reasoning/refinement`, `ScopeStmt` | walked by the eigenvariable condition |
| symbolic equivalence | `equivalence/symbolic.py` | **classified `UNTRUSTED_ORACLE`, not routed through the boundary** (§2) |

## 6. Expected Gold-10 effect

Predictions to be checked by your rerun, not results.

| gap | expected classification after this change |
|---|---|
| **GAP-0001** arithmetic normalisation | **exposable now**, no core change and no corpus schema change: `evidence e : entails 5.0 - 2.0 = 3.0 by closed_eval_v1()`. Verified locally on the `5-2=3` and `-1/(2^2) = -1/4` shapes. |
| **GAP-0002** function evaluation | **exposable now** via `definition_unfold_v1`, which records the definitions unfolded. Verified locally on the `f(x)=x+1`, `g(x)=2f(x)`, `g(3)=8` chain. |
| **GAP-0003** underdetermination | **CLOSED IN CORE.** The G06 shape certifies end to end. |
| **GAP-0004** quantified discharge | **CORE CLOSED; G07's BODY STILL LIBRARY-LEVEL.** `forall_intro`/`forall_elim` exist and are checked. `n + 0 = n` has a free variable, so `closed_eval_v1` cannot decide it and symbolic equivalence may not certify it (§2). G07 will still not report as natively verified. |
| **GAP-0005** conditional product | **REMAINS LIBRARY.** Unchanged by decision. |
| **GAP-0006** calculus | **REMAINS LIBRARY.** Unchanged by decision. |

Two new statement forms exist if you want to render them:

```
evidence     <id> : entails|determines_neither <prop> [from <ref>,...] by <checker> [( <role> := <expr>,... )]
undetermined <goal> by <evidence>
```

Working examples that compile: `examples/logic/certified_underdetermination.hml`,
`examples/logic/quantified_inference.hml`.

## 7. Behavioural / API changes

* `GoalStatus` gains `UNDERDETERMINED` (five values now). `GoalStatus.ALL` changed.
* New `EvidenceStatus` (`PROPOSED | VALID | REJECTED`). Deliberately **not** called
  VERIFIED: that word stays reserved for a kernel-checked derivation.
* New AST nodes `EvidenceStmt`, `UndeterminedStmt`; `V2_STATEMENTS` changed.
* `check_reasoning(module, diags)` gains an optional third parameter `symbols`. Existing
  callers keep working; without it, checkers needing declared domains fail closed.
* `ReasoningResult` gains `evidence_status`, `adjudications`, `underdetermined()`.
* `RuleSpec` gains `side_conditions`.
* Four new keywords: `evidence`, `undetermined`, `entails`, `determines_neither`. **The
  quarantined L3 form `entails p3 from [...] via ...` remains rejected** — `entails` here is
  a judgement qualifier, never a statement head, and the quarantine test still asserts it.
* `spec/ir.schema.json` gains `Evidence` and `UnderdeterminationClaim`.
* Canonical identity: an `Evidence` statement carries its **checker name** (two modules
  resting on different trusted code are not the same module) but **not its status**.
* New diagnostics `HML-R716`…`HML-R725`, `HML-P256`…`HML-P258`.

## 8. Tests

| suite | result |
|---|---|
| `scripts/conformance.sh` | **CONFORMANCE: PASS**, exit 0, all 8 stages |
| full `pytest` | **6765 passed, 6 skipped, 7 xfailed, 7 xpassed, 0 failed** |
| the five new files | 80 passed, 1 skipped |
| `ruff check src tests` | All checks passed |
| `mypy src/hamiltonian_lang` | no issues in 95 source files |

New files: `tests/reasoning/test_{binders,certificates,underdetermination,quantifiers}.py`,
`tests/backends/test_certificate_backends.py`.

Attacks executed and repelled: unknown checker · wrong judgement · checker that raises ·
checker establishing something else · VALID naming nothing · claim-hash mismatch · **stale
context** · premise-hash mismatch · certificate omitting a premise of Γ · witness violating
a premise · duplicated witness · partial model · swapped witnesses · undeclared atom ·
numeric witness value · unsupported fragment · `determines_neither` used as a premise ·
forged `CheckedEvidence` · witness-specific ∀-intro (also inside a `scope`) · wrong-domain
∀-elim · capturing instantiation · body/conclusion mismatch · unimplemented side condition ·
universal forged from a finite sample.

## 9. Trusted computing base

**Trusted:** canonical IR and identity · name/scope resolution · type and refinement
checking · evidence graph and status checker · the inference kernel · the certificate
boundary · the three registered checkers · `verification/obligations/evaluate`, deliberately
admitted.

**Untrusted:** SymPy and `equivalence/symbolic.py` · any SMT/CAS output · LLMs · search and
tactics · corpus extraction · arbitrary libraries · pretty printers · external heuristics.

The TCB grew by the boundary, three small checkers, and one evaluator already in the tree.
It did not grow by any domain mathematics.

## 10. Unresolved questions, and things you should know

1. **`REFUTED` has no adjudicating statement form.** It did not before this change either.
   It is named in the verdict vocabulary so the judgment is total over the four semantic
   outcomes rather than shaped by which statements happen to exist. If the corpus needs it,
   say so and it is a small addition.
2. **G07 cannot report natively verified** without an algebra library. This was the correct
   layering call, but it means your rerun will still show GAP-0004's *body* open. Judge the
   quantifier core by `examples/logic/quantified_inference.hml`, not by G07.
3. **`GRAMMAR_CONTRACT.md` drift, found and reported rather than repaired** (a broad grammar
   rewrite was out of scope): it specifies `obligation` and `discharge` statements that were
   **never implemented**; omits `scope`, which **is**; shows `derive ... yields <prop>` where
   the implementation is `derive <name> : <prop> from ... by <rule>`; and names a
   `GoalStatus` value `ASSERTED_UNCHECKED` that is not in the AST. Corrected only where
   D-047's own additions would otherwise read untruthfully.
4. **The measurement ambiguity your §C raised is untouched here** — `action.hml_support`
   conflating "can represent", "can verify natively" and "a library can verify" is a corpus
   schema matter and yours to decide. This change makes the distinction *representable* on
   the HML side: `EvidenceKind` separates `NATIVE_KERNEL` from `CHECKED_CERTIFICATE` from
   `UNTRUSTED_ORACLE`.
5. **Commit granularity deviated from the requested six.** The AST/grammar/`check.py`
   substrate is shared by all three features; splitting would have produced intermediate
   commits that do not pass. The normative spec was still written first, as instructed.

## 11. Repository state

| | |
|---|---|
| branch | `feature/hml-reasoning-kernel-v2` |
| SHA to pin | `5688aba18632b65a8709aa1d85577d31a67dba6a` |
| worktree | clean |
| local vs remote | equal (verify with `git rev-parse HEAD @{u}`) |

Records: `DECISIONS.md` D-047 · `docs/hml_v2/GOLD10_CORE_SEMANTICS_SPEC.md` (normative) ·
`docs/hml_v2/{GRAMMAR_CONTRACT,REASONING_MODEL,OBLIGATIONS}.md`.

**Next step is yours.** Repin `hml_core` and rerun the **same** Gold-10. Gold-100 only if the
classifications are stable. Gold-10 was not rerun here, and the corpus was not touched.
