# Chain-of-Repair and the Diagnostic Context Broker

**Status: built and tested offline. No model call has been made. No live run has been
authorised.**

This document describes two subsystems and the single constraint that binds them:

- `src/hamiltonian_lang/context_broker/` — error-conditioned retrieval of project-specific
  context, with an explicit result when there is none.
- `src/hamiltonian_lang/repair/` — role-separated repair, its three feedback arms, its
  budgets, and the A/B/C/D leakage study that checks whether the repair plan is doing the
  work it claims to.

The constraint: **the plan must never contain the answer.** It is enforced in code
(`repair/plan.py`) and tested (`tests/repair/test_repair_plan_non_leaking.py`), not
described in a prompt.

---

## 1. Why these two subsystems exist

### INTERVENOR — role separation

Self-repair fails when one model stays trapped in the interpretation that produced the
error. Asked to "try again", it re-derives the same wrong thing with more confidence.
This is Degeneration-of-Thought.

The reported fix is role separation. A **Teacher** receives the broken program, the
compiler error and the failed tests, and returns *the cause and a repair plan* —
explicitly **not the corrected program**. A **Learner** then applies the plan. Repair beat
extra prompting substantially, and gains continued through roughly three turns.

### COCOGEN — error-conditioned context retrieval

A diagnostic says *what* is wrong. It does not say *which* project-specific rule,
signature or type should replace the wrong thing. The reported fix is error-conditioned
retrieval over a structural project graph. Two details from the ablations shaped this
design:

1. **Compiler feedback alone did not deliver the full gain.** Retrieval was needed. This is
   why `RAW_DIAGNOSTIC` is a separate arm rather than the control for `CHAIN_OF_REPAIR` —
   without it, a positive result cannot be attributed to retrieval and role separation
   rather than to the diagnostic simply being present.
2. **Most of the easy gain arrived in the first iteration.** This is why the retrieval
   ladder is ordered by decreasing precision, and why the first rung is a dictionary
   lookup that costs nothing.

Neither result is reproduced here. Both are the *reason for the design*; whether either
holds for Hamiltonian Lang is unmeasured.

---

## 2. The Diagnostic Context Broker

### 2.1 The semantic index

`context_broker/index.py` builds an index over eleven facets, each transcribed from a real
artefact:

| facet | source |
|---|---|
| `type` | `types.py::_SCALAR_PARENTS`, `UNIT_INTERVAL_KINDS` |
| `constructor` | `type_system::TypeChecker._known_type_names` |
| `function_signature` | `type_system::_BUILTIN_SIGNATURES`, `semantics::_BUILTIN_FUNCTIONS`, and the program's own `def`s |
| `distribution_role` | `type_system/distributions.py::DISTRIBUTIONS`, `MISPARAMETERISATIONS` |
| `coercion_rule` | `types.py::_SCALAR_PARENTS` / `is_subtype` |
| `epistemic_rule` | `v1/epistemic.py::Justification`, `PROHIBITED_COERCIONS`, `DISCHARGES_GOALS`, `REQUIRED_CONTEXT` |
| `diagnostic_code` | `improvement/diagnostics.py::VIOLATED_INVARIANT_BY_CODE` |
| `example` | the `.hml` corpus under `examples/` |
| `rule_card` | the arity, argument-position and named-role rules, each pointing at the code that enforces it |
| `backend_support` | `v1/backend_support.py::SUPPORT` |
| `constitutional_invariant` | `CLAUDE.md`, prohibited conflations |

**Every item carries a `Provenance`**, and `SemanticIndex.unresolved_provenance()`
re-derives every source path from disk. A test asserts the list is empty. This is the
mechanism behind "never hallucinate a rule": an item whose origin cannot be located is
indistinguishable, inside a repair packet, from one that was invented — and it arrives with
exactly the same authority.

The index is deterministic: two builds in one process produce equal content.

### 2.2 Module-local indexing

The index also holds the *broken program's own* declarations (`index.local_items`). This is
the project-specific half. For a wrong-arity call on a user `def`, retrieving the global
built-in list is retrieval that looks successful and helps nothing; the model needs *that*
definition's parameter list. Showing a declaration the model itself wrote back to it is not
a leak — it is the program's own contract, restated where the call site broke it.

### 2.3 The retrieval ladder

```
1  DETERMINISTIC_CODE_MAP   the code alone fixes the answer
2  EXACT_SYMBOL             the offending name, looked up verbatim
3  AST_NEIGHBOURHOOD        identifiers on and around the failing span
4  SEMANTIC_EXAMPLE         a compiling example exercising the same construct
5  (none)                   an explicit no-context result
```

Stages 1 and 2 always run and their results are pooled; 3 and 4 run only while the item
budget is unspent. Within stage 1 results are ranked by specificity: a declaration from the
program under repair, then a global table entry matching the offending name, then the
governing rule, then a vocabulary list, then everything else.

### 2.4 The five hard-coded mappings

These account for the bulk of observed encoding failures and each has exactly one right
answer. **None of them may cost a model call.**

| code | mapping |
|---|---|
| `HML-T471` | function signature and arity rule |
| `HML-T472` | argument position and required refinement type |
| `HML-T415` | named distribution roles |
| `HML-T440` | valid type vocabulary (with nearest-name suggestion) |
| `HML-N306` | unknown callee / known function list |

Each is verified end to end against a real broken program compiled by the real compiler
(`tests/repair/test_repair_context_broker.py`).

### 2.5 Four outcomes, and no fifth

```
CONTEXT_FOUND            at least one item was retrieved
NO_RELEVANT_CONTEXT      the query was valid; the index has nothing — said so
QUERY_INVALID            no code, or a code of the wrong shape
UNSUPPORTED_ERROR_CLASS  well-formed code, family unknown to the taxonomy
```

There is deliberately no "best effort" outcome.

### 2.6 The error taxonomy

`SYNTAX · RESOLUTION · ARITY · TYPE · REFINEMENT · ROLE · SCOPE · DIMENSION · EPISTEMIC ·
OBLIGATION · SEMANTIC_EQUIVALENCE · BACKEND`

This is a **second** classification, kept separate from
`improvement.diagnostics.DiagnosticCategory`. That one classifies by which compiler stage
emitted the diagnostic — the right axis for attributing a defect to a subsystem, the wrong
axis for deciding what context a repair needs. `HML-T471` and `HML-T472` share the `T`
prefix and therefore the category `TYPE`, but need entirely different context.

`ERROR_CLASS_BY_CODE` contains only codes whose emission site was read in the compiler
source; a test asserts every entry names a code the compiler actually emits. Everything else
falls back to the family prefix and is marked `exact=False`. An unknown family classifies to
`None`, and the broker answers `UNSUPPORTED_ERROR_CLASS`.

---

## 3. Chain-of-Repair

### 3.1 The Teacher's output, and its boundary

The **Repair Teacher** receives: broken output, structured diagnostic, retrieved context,
verified prefix/state. It returns exactly six things:

- failing invariant
- cause
- source span
- expected semantic category
- repair plan (steps)
- preservation constraints

`expected_semantic_category` is a *category*, never a value: "a positive real scale
parameter", never `0.5`. That distinction is the difference between telling a student the
argument must be positive and telling them the answer.

**It must not return the corrected full program or the final mathematical answer.** A plan
containing the answer converts H3 from a measurement into a tautology: the Learner copies,
the verifier passes, and the reported number measures transcription. Nothing in the
resulting transcript distinguishes that run from a real one.

`plan_leak_reasons` enumerates every way the boundary is crossed:

- the plan contains the complete corrected program
- the plan contains the final answer
- a step spans more than `MAX_STEP_LINES` lines (a patch, not an instruction)
- a step contains more than one statement keyword (a program fragment)
- a step binds a concrete value (`scale := 0.5` rather than `scale := ...`)
- **at a mathematical endpoint**, the plan introduces a numeral not present in the broken
  output, the diagnostic or the retrieved context

The last check is opt-in via `forbid_novel_numerals`, which `run_repair_chain` sets exactly
when the endpoint is `MATHEMATICAL_ANSWER`. At a syntactic endpoint an arity count is
ordinary; at a mathematical endpoint an unexplained numeral is indistinguishable from the
answer.

`assert_plan_non_leaking` raises `PlanLeak`. It does not warn, and it does not trim.

### 3.2 Where the invariant comes from

`failing_invariant` is taken, in order, from: the compiler's own
`VIOLATED_INVARIANT_BY_CODE`; a retrieved `diagnostic_code` context item; the class-level
rule in `teacher.CLASS_INVARIANT`. The choice is recorded on the plan as
`invariant_source`, which is what makes "never hallucinate a rule" auditable after the
fact.

When none of the three applies, the Teacher returns `NoPlan(reason=...)` — a first-class
result, not `None`. "The invariant is unknown and retrieval found nothing" is a real,
reportable outcome of a repair turn; collapsing it into a missing value would let a null be
counted as a failure of the Learner.

Every plan also carries `UNIVERSAL_PRESERVATION`, because these three failures have been
observed in generated code and all three pass the checker:

1. deleting the failing construct;
2. weakening a declared type or check so the error goes away;
3. rewriting statements the diagnostic did not name.

### 3.3 The Learner

Deliberately thin: it receives a `FeedbackPayload` and returns text. It does not decide what
feedback it gets. A Learner that behaved differently under `CHAIN_OF_REPAIR` for reasons of
its own would confound the treatment with itself.

`ScriptedRepairLearner` replays fixed responses. It also asserts the arm contract from its
own side — a `NO_FEEDBACK` payload arriving with feedback text is refused rather than used.

---

## 4. The three feedback arms

| arm | payload |
|---|---|
| `NO_FEEDBACK` | broken output only |
| `RAW_DIAGNOSTIC` | broken output + rendered diagnostic |
| `CHAIN_OF_REPAIR` | broken output + structured diagnostic + retrieved context + plan |

Every result identifies its arm separately.

Payload construction is one function with one definition per arm, and `build_payload`
**verifies its own output**: the `NO_FEEDBACK` payload is checked not to contain the
diagnostic code (including the case where the broken output itself quotes an earlier
compiler message), and the `RAW_DIAGNOSTIC` payload is checked to carry no context and no
plan step. A violation raises `ArmContamination` rather than being trimmed — silently
removing leaked material would hide the bug that put it there.

---

## 5. Repair budgets

| budget | limit | admissible for |
|---|---|---|
| `OFFICIAL_ONE` | 1 | official ACQ0, official H3 |
| `DEVELOPMENTAL_THREE` | 3 | developmental ablation only, recorded as `EXCLUDED` |

**They are never pooled.** A three-turn arm has three chances at the same target and
consumes three times the compute; averaging it with a one-turn arm produces a figure that
is neither — and the mixed figure looks exactly like a clean one.
`require_single_budget` raises `RepairBudgetPoolingError`, mirroring
`improvement.state.require_single_hypothesis`.

`assert_official` additionally bars the developmental budget from any preregistered
hypothesis, so a three-turn number cannot reach an official endpoint by being relabelled
downstream.

---

## 6. Hypothesis discipline

Compiler-assisted **syntax** repair during ACQ0 is `ACQ0_REPAIR`, **not H3**. H3 requires a
mathematical reasoning endpoint. See `docs/evaluation/HYPOTHESIS_REGISTER.md` rule 2.

The register states this as a rule. Here it is a type. Every `RepairRecord` carries exactly
one `improvement.state.Hypothesis` and one `RepairEndpoint`, and refuses:

- `H3` with a syntactic endpoint — a syntax fix relabelled as reasoning repair;
- `ACQ0` with a mathematical endpoint — a reasoning result relabelled as acquisition;
- `H1` or `H2` with any repair turn at all — neither hypothesis involves a repair loop.

`RepairRecord.mechanism` reads `REPAIR_MECHANISM`, so a serialised record says
`ACQ0_REPAIR` or `H3_VERIFIER_GUIDED_REPAIR` explicitly, alongside the hypothesis's
`excluded_claim` — the sentence stating what a win here does *not* support.

`summarise` refuses to aggregate across endpoints, then across hypotheses, then across
budgets. Arms *are* pooled: comparing them is the point.

First-attempt and repaired rates are reported separately and never merged.

---

## 7. The leakage study

Four conditions:

```
A  broken output only
B  plan only (no broken output)
C  broken output + correct plan
D  broken output + shuffled plan
```

- A plan is **useful** when `C > A` **and** `C > D`.
- A plan **leaks** when **B alone** reconstructs the target at a rate above the threshold.

The `C > D` half is the control most self-repair evaluations omit. If C beats A but not D,
the gain came from being prompted again with structured text, not from the plan's content.

The leak check **outranks** the usefulness check. A leaking plan that is also useful is not
a good plan; its usefulness is exactly the thing in doubt.

Shuffling has two modes. `STEP_PERMUTATION` reorders the plan's own steps — the same
instructions in an order that does not describe a repair — using a seeded, reproducible
permutation. `CROSS_TASK` substitutes another case's plan wholesale, the stronger control:
it holds "a plan was present" fixed while destroying relevance. A plan with fewer than two
distinct steps cannot be permuted; that D trial is **excluded with a stated reason** and
counted, because a D trial identical to its C trial silently inflates D.

Verdicts: `PLAN_USEFUL_AND_NON_LEAKING` · `PLAN_NOT_USEFUL` · `PLAN_LEAKS` ·
`INSUFFICIENT_EVIDENCE`. Every report records the leak threshold, the minimum-trials
setting, the shuffle mode and the seed, so a report produced under one threshold cannot be
read as though it were produced under another.

`DEFAULT_LEAK_THRESHOLD = 0.10` is **provisional and not preregistered.**

---

## 8. Offline guarantee

Neither package imports `http`, `httpx`, `requests`, `urllib`, `socket`, `ssl`,
`subprocess`, `asyncio`, or any model provider, and neither contains a URL. This is checked
by AST inspection in `tests/repair/test_repair_offline_guarantee.py`, together with a full
chain run under a disabled `socket` module.

`run_repair_chain` and `run_leakage_study` both refuse a component declaring `live = True`
unless the caller passes `allow_live=True`, so an offline suite cannot start making network
calls because a component was swapped upstream.

---

## 9. What has *not* been established

- **No model call has been made.** Every number this subsystem can currently produce comes
  from scripted fixtures and says nothing about any model.
- **No leakage study has been run against real plans and a real probe.** The harness is
  built and its verdict logic is tested against constructed rates; whether the
  `DeterministicRepairTeacher`'s plans are useful, and whether they leak, is unmeasured.
- **The class-level invariants in `teacher.CLASS_INVARIANT` are restatements**, one per
  error class, each annotated with the compiler location that enforces it. They are
  fallbacks used only when the code-specific table has no entry. They have not been
  independently reviewed against `SPEC.md`.
- **`DEFAULT_LEAK_THRESHOLD` is a placeholder.** It must be preregistered before any H3
  result is read against it.
- **The three arms have not been compared.** `ARM_DESCRIPTION` states what each is *for*;
  no measurement supports any ordering between them.
- **Nothing here bears on H1 or H2.** A win on H3 would be a win for verifier-guided
  reasoning; any checkable notation with a comparable checker would predict the same gain.

---

## 10. File map

```
src/hamiltonian_lang/context_broker/
  taxonomy.py   ErrorClass, ERROR_CLASS_BY_CODE, classify
  index.py      FacetKind, Provenance, ContextItem, SemanticIndex, build_index, local_items
  broker.py     ContextStatus, RetrievalStage, DETERMINISTIC_FACETS, DiagnosticContextBroker

src/hamiltonian_lang/repair/
  plan.py       RepairPlan, NoPlan, plan_leak_reasons, assert_plan_non_leaking
  teacher.py    RepairTeacher, DeterministicRepairTeacher, CLASS_* tables
  learner.py    RepairLearner, ScriptedRepairLearner
  arms.py       FeedbackArm, FeedbackPayload, build_payload, ArmContamination
  budget.py     RepairBudget, require_single_budget, assert_official
  record.py     RepairEndpoint, RepairRecord, run_repair_chain, summarise
  leakage.py    LeakageCondition, ShuffleMode, run_leakage_study, LeakageVerdict

tests/repair/
  test_repair_taxonomy.py            the twelve classes; exact vs inferred classification
  test_repair_context_broker.py      provenance, the ladder, the four statuses, the five maps
  test_repair_plan_non_leaking.py    the boundary the Teacher may not cross
  test_repair_teacher_learner.py     role separation and the chain
  test_repair_arms.py                arm exclusions and contamination
  test_repair_budget.py              budgets, pooling refusal, ACQ0/H3 discipline
  test_repair_leakage.py             A/B/C/D, shuffling, verdicts
  test_repair_offline_guarantee.py   no network, no provider, no URL
```
