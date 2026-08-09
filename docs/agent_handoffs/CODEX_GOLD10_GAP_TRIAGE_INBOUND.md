# Gold-10 semantic-gap triage handoff

Status: forensic review only. No trajectory, dataset, or `hml_core` file was
modified.

Pinned HML inspected: `hml_core` at `164d1946e91216c093478132caa0d06427259682`.

## Executive finding

The original `13.04%` CoreGapRate does not survive. Two of the three
transition-level core labels are genuine generic HML reasoning omissions:

- G06's certified `P`-is-undetermined terminal result;
- G07's generic quantified theorem discharge.

The G09 conditional-product step is a domain-law/library problem, not a new
core-language semantic. The arithmetic and function-evaluation reports also
overstate what the pinned implementation can do: HML already contains an exact
obligation evaluator, recursive definition unfolding, and a symbolic-equivalence
engine. Those capabilities are not wired into the v2 `derive`/`proved` path used by
the Gold-10 renderings. Their primary class is therefore
`TRANSLATION/CANONICALIZATION_PROBLEM`, not `CORE_SEMANTIC_MISSING`.

No gap is a `CORE_SEMANTIC_BUG`: the current implementation fails closed rather
than returning a wrong mathematical result. No gap is `SURFACE_SYNTAX_ONLY`: all
six target operations have either a current representation or a deeper semantic
failure. No gap is primarily caused by `schemas/trajectory.schema.json`.

### Revised headline numbers

Counting the same 23 verified transitions and assigning one primary class per
transition, the forensic split is:

| Primary transition class | Count | Rate |
|---|---:|---:|
| `EXPRESSIBLE_CURRENT_HML` | 11 | 47.83% |
| `CORE_SEMANTIC_MISSING` | 2 | 8.70% |
| `LIBRARY_MISSING` | 3 | 13.04% |
| `TRANSLATION/CANONICALIZATION_PROBLEM` | 7 | 30.43% |
| Total | 23 | 100.00% |

The arithmetic and calculus portions of G10 overlap in the same transition; the
table assigns that transition to the more substantive calculus-library class.
Gap IDs are not additive because GAP-0001 is referenced by several other gaps.

## Evidence from the pinned HML implementation

The following current constructs were inspected read-only:

- `hml_core/src/hamiltonian_lang/reasoning/kernel.py`: the v2 closed rule catalogue
  and structural conclusion checking.
- `hml_core/src/hamiltonian_lang/reasoning/check.py`: derivation and goal
  adjudication; `VERIFIED` requires a kernel-checked derivation and discharged
  obligations.
- `hml_core/src/hamiltonian_lang/ast/nodes.py`: `GoalStatus`, quantifier nodes,
  derivation nodes, and their closed status sets.
- `hml_core/src/hamiltonian_lang/backends/canonical.py`: canonical identity is
  structural/alpha-safe identity, not a general arithmetic normalizer.
- `hml_core/src/hamiltonian_lang/verification/obligations/evaluate.py`: exact
  rational evaluation, definitional unfolding, function-call unfolding, and
  interval evaluation.
- `hml_core/src/hamiltonian_lang/verification/obligations/checkers.py`: exact
  `closed_arithmetic_equality` and related bounded checkers.
- `hml_core/src/hamiltonian_lang/verification/obligations/engine.py`: the
  obligation engine and `verify_source` endpoint.
- `hml_core/src/hamiltonian_lang/equivalence/symbolic.py` and
  `hml_core/src/hamiltonian_lang/equivalence/sympy_bridge.py`: symbolic identity and
  relation-equivalence certificates, with explicit refusal on unsupported forms.
- `hml_core/src/hamiltonian_lang/type_system/__init__.py`: probability and derivative
  typing, definedness, and dimension checks.
- `hml_core/docs/hml_v2/GRAMMAR_CONTRACT.md`: the v2 design lock explicitly excludes
  a theorem library and user-defined trusted inference rules.
- `hml_core/docs/hml_v2/REASONING_MODEL.md`: the v2 proof-state contract and closed
  rule-kernel model.
- `hml_core/docs/hml_v2/OBLIGATIONS.md`: the bounded obligation-discharge subset.
- `hml_core/docs/design/BACKEND_CONTRACT.md`: target-backend loss contracts.

The important distinction is between “the source tree contains a verifier or
library that can decide a proposition” and “the v2 HML derivation kernel consumes
that decision as a checked transition.” Gold-10 currently tests the latter.

## GAP-0001 — arithmetic normalization and numeric evaluation

### Revised class

`TRANSLATION/CANONICALIZATION_PROBLEM`

### Exact operation and source transitions

The operation is exact arithmetic normalization after an equality-preserving
step:

- G01 `a2`: `x - 0 = 5 - 2` to `x = 3`;
- G02 `a1`: `b = 2 + 3` to `b = 5`;
- G09 `a1`: `P(A and B) = 0.5 * 0.8` to `P(A and B) = 0.4`;
- G10 `a2`: substitute `x = 2` into `-1/x^2` and normalize to `-1/4`.

### Required mathematical meaning

The output must preserve the source equality and its dependencies while recording
an exact, rationally justified result. Decimal literals in these examples are
exact decimals, not floating-point approximations. A rewrite must not erase a
partiality condition or silently turn a satisfiable constraint into an entailment.

### What current HML can represent

The parser and AST represent the arithmetic trees. The v2 kernel can apply the
structural equality rules that produce `x - 0 = 5 - 2`. The obligation subsystem
already evaluates closed rational expressions exactly. The equivalence subsystem
already has a symbolic difference/relational comparison path, with explicit
assumption tracking for symbolic denominators and inequality signs.

### Exact failure point

`reasoning/kernel.py` compares a claimed `derive` conclusion with the structural
output of the named rule. It does not invoke the closed evaluator or the symbolic
equivalence certificate after constructing that output. `canonical.py` also
deliberately defines identity, not simplification. Consequently, the HML rendering
can carry the pre-normalized expression, but the v2 `derive`/`proved` path has no
checked computation edge for the final normalized fact.

This is not evidence that HML has no arithmetic capability. It is evidence that the
existing capability is not connected to this trajectory transition. For example,
the obligation engine can certify closed equalities such as `-1 / (2^2) = -1/4`,
but that is different from a kernel derivation from a prior claim.

### Relevant constructs and layer decision

- Parser arithmetic expressions: current surface and AST support.
- `reasoning/kernel.py`: structural transformations; no arithmetic normalizer.
- `backends/canonical.py`: intentionally structural canonical identity.
- `verification/obligations/evaluate.py` and `checkers.py`: existing exact evaluator.
- `equivalence/symbolic.py`: existing symbolic equivalence certificate path.

This belongs in translation/canonicalization because no existing HML denotation
needs to change. A corpus adapter can map a neutral arithmetic action to an exact
evaluation/equivalence certificate and preserve it as evidence. Adding special
rules for `x - 0`, `5 - 2`, or `0.5 * 0.8` to the trusted core would be the wrong
layer.

### Smallest remedy

Add a corpus-side arithmetic certificate adapter that consumes the existing exact
evaluator/equivalence API, emits the normalized fact plus dependencies, and records
whether the result is closed evaluation or symbolic equivalence. If HML-native
derivations must consume it, expose a general library-evidence hook rather than
adding example-specific arithmetic rules to the v2 core.

### Semantic impact

Rendering and operational verification/evidence only. No change to HML denotation,
typing, epistemic status, or proof-state vocabulary is required.

### Dependencies and overfitting risk

Independent of GAP-0003, GAP-0005, and GAP-0006 at the core level. It is a shared
dependency for their numeric terminal steps. The general remedy has low risk; a
handwritten simplifier for the four Gold-10 expressions has high overfitting risk
and must be rejected.

## GAP-0002 — function evaluation and dependency chains

### Revised class

`TRANSLATION/CANONICALIZATION_PROBLEM`

### Exact operation and source transitions

G03 is a three-transition dependency evaluation:

- `a0`: from `f(x) = x + 1`, compute `f(3) = 4`;
- `a1`: use the established `f(3)` inside `g(x) = 2f(x)`, obtaining `g(3) = 2 * 4`;
- `a2`: compute `g(3) = 8`.

### Required mathematical meaning

Definition unfolding must be capture-safe, respect declared arity/types, preserve
the dependency order, and produce exact values with local evidence for each step.
The final value must not be presented as a proof merely because a function call is
syntactically well-typed.

### What current HML can represent

`def` declarations, typed parameters, calls, dependency structure, and signature
conformance are all current. More importantly, the pinned
`verification/obligations/evaluate.py` has an `Environment` containing definitions
and parameterized functions, recursively unfolds calls, caps recursion, detects
cycles, and evaluates exact rational results. A `verify_source` obligation of the
form `g(3) = 8` can therefore be discharged in the supported closed-evaluation
subset.

### Exact failure point

The Gold-10 HML rendering contains the definitions and `value_at_3`, but no checked
goal/obligation or v2 derivation edge for `f(3) = 4`, `g(3) = 2 * 4`, and `g(3) = 8`.
The v2 reasoning kernel does not call the evaluator during `derive`, and the
SymPy lowering deliberately treats non-built-in calls as uninterpreted rather than
as proof evidence. Thus the claim “HML cannot execute this” is too broad; the real
gap is that existing execution is not projected into the canonical trajectory's
three-step evidence chain.

### Relevant constructs and layer decision

- Parser/type system: current definitions, calls, arity, and parameter types.
- `verification/obligations/evaluate.py`: current recursive evaluator.
- `verification/obligations/checkers.py`: current exact closed equality checker.
- `reasoning/kernel.py`: no evaluator-backed derivation rule.
- `backends/sympy.py`: foreign lowering intentionally reports user-defined calls as
  uninterpreted.

This is a translation/observability problem, not a missing HML denotation and not a
new core semantic. The neutral trajectory has three observable steps; the current
HML evaluator has a correct final computation but does not expose the internal
unfolding trace as v2 derivation evidence.

### Smallest remedy

Use the existing evaluator to generate a dependency-preserving execution certificate
for each neutral action, or render an HML obligation whose evidence names the
unfolded definitions and exact values. Do not add a G03-specific evaluation rule.

### Semantic impact

Operational execution/evidence and rendering only. Existing function denotation,
typing, and epistemic semantics remain unchanged.

### Dependencies and overfitting risk

Shares the certificate adapter boundary with GAP-0001. It does not depend on the
GAP-0003 or GAP-0004 core changes. A general call graph/evaluator trace is low risk;
hard-coding `f`, `g`, or the point `3` would overfit.

## GAP-0003 — first-class undetermined epistemic result

### Revised class

`CORE_SEMANTIC_MISSING`

### Exact operation and source transitions

G06:

- `a0`: from `P -> Q` and `Q`, construct evidence that `P` is not entailed;
- `a1`: assign the terminal epistemic status “`P` is undetermined,” meaning neither
  `P` nor `not P` follows from the premises.

For a sound certificate, one model of the premises with `P = false` is needed to
show non-entailment, and one model of the premises with `P = true` is needed to
show non-refutation. With Boolean `P,Q`, both models exist while satisfying
`P -> Q` and `Q`.

### Required mathematical meaning

“Undetermined” must be a certified result, not “the prover stopped” and not
`UNSUBSTANTIATED`. The state must preserve the premises, the candidate claim, the
two-sided non-entailment evidence, and the fact that no proof or refutation was
found within the stated semantics.

### What current HML can represent

HML represents Boolean propositions, implication, negation, MP, MT, goals, and
countermodel-like evidence in separate equivalence/verification components. The
equivalence tests also distinguish a genuine propositional countermodel from an
inconclusive dependent-atom model. The trajectory schema itself permits an
`undetermined` claim status and `verified_as_undetermined` action status.

### Exact failure point

`ast/nodes.py::GoalStatus` has `OPEN`, `PROVED`, `REFUTED`, and
`UNSUBSTANTIATED`, but no certified underdetermination state. `reasoning/check.py`
only adjudicates a goal by a verified derivation matching the goal; absent that, it
leaves the goal open/unsubstantiated. `reasoning/kernel.py` has no operation that
proves non-entailment from a pair of models or an equivalent entailment certificate.
The current equivalence countermodel path is not connected to v2 goal adjudication.

### Relevant constructs and layer decision

- `ast/nodes.py::GoalStatus`: closed proof-state vocabulary.
- `reasoning/check.py`: goal adjudication and verified-derivation gate.
- `reasoning/evidence.py`: evidence/provenance boundary.
- `equivalence/symbolic.py`: propositional countermodel capability that can inform a
  future certificate, but does not itself settle a v2 goal.
- `schemas/trajectory.schema.json`: can record a textual undetermined claim, but does
  not define a typed countermodel certificate.

This is core because it changes the terminal proof-state/epistemic contract and the
trusted operational meaning of a goal. It is not a syntax-only extension, and it is
not fixed by adding a library theorem for the particular letters `P` and `Q`.

### Smallest remedy

Add a generic certified underdetermination result to the core proof-state contract:
an explicit terminal status plus a kernel-checked non-entailment certificate that
contains the relevant premises and sufficient countermodels/witnesses for both
directions. Reuse existing Boolean countermodel machinery where sound; do not add a
pattern recognizer for `P -> Q, Q`.

### Semantic impact

Denotation of `P` and `Q`: none. Proof state, epistemic status, operational
verification, and evidence/provenance: yes. Typing: no, except for checking the
certificate's model assignments against declared types.

### Dependencies and overfitting risk

Depends on existing Boolean semantics, model validation, and evidence identity. It
does not depend on GAP-0004, GAP-0005, or GAP-0006. General finite-model
non-entailment is broadly reusable; a rule specialized to implication-plus-one
consequent would be severe overfitting.

## GAP-0004 — quantified theorem discharge

### Revised class

`CORE_SEMANTIC_MISSING`

### Exact operation and source transition

G07 `a1`: preserve a fresh arbitrary binder `n : Natural`, apply the additive
identity theorem to the body, and discharge:

`forall n : Natural . n + 0 = n`.

G07 `a0`, resolving the binder and scope, is already current HML and is not a gap.

### Required mathematical meaning

The proof must establish the body for an arbitrary fresh `n`, prevent variable
capture, preserve the binder's declared domain, and then introduce the universal
quantifier. The result is a theorem, not a finite sample of Natural values and not
an assertion that the goal text is true.

### What current HML can represent

The parser, quantifier AST, binder identity, alpha-equivalence, canonical form, and
scope graph all represent the statement. The v1 transformation data model names
some generic inference operations, but the v2 trusted kernel is the operative path
for the Gold-10 rendering. Its closed `RULES` table has no universal-introduction,
universal-instantiation, or theorem-under-binder rule. The v2 design also explicitly
has no theorem library or user-definable trusted rules.

### Exact failure point

The quantifier is parsed and canonicalized, but there is no checked derivation that
creates a fresh arbitrary variable, proves `n + 0 = n` under that binder, and closes
the universal goal. HML therefore represents the proposition while leaving the
proof state open.

### Relevant constructs and layer decision

- Parser/AST/canonical binder machinery: current and sufficient for scope identity.
- `reasoning/kernel.py::RULES`: no quantified inference rule.
- `reasoning/check.py`: no theorem-under-binder goal adjudication.
- `hml_core/docs/hml_v2/GRAMMAR_CONTRACT.md`: no theorem library and no
  user-defined trusted rules.
- `hml_core/examples/logic/quantifier_scope.hml`: scope representation example,
  not quantified proof discharge.

The generic binder introduction/instantiation semantics belong in core. The theorem
`n + 0 = n` itself belongs in an algebra library. Calling the whole gap a library
gap would hide the missing trusted operation that makes any quantified theorem
usable.

### Smallest remedy

Add generic, freshness-checked quantified inference and theorem-application hooks to
the core reasoning contract, then supply the additive identity as a library theorem
or canonicalization certificate. Do not add a Natural-specific “forall identity” rule.

### Semantic impact

Proof state and operational semantics: yes. Epistemic status: yes, because a goal can
move to proved. Typing/scope checking: the existing binder checks are reused, with
freshness and domain obligations strengthened. HML expression denotation: no.

### Dependencies and overfitting risk

Depends on existing binder identity/alpha-equivalence and on the general arithmetic
certificate boundary from GAP-0001 for the theorem body. It does not depend on the
probability or calculus gaps. A generic binder rule is high-generality; a rule that
recognizes only `n + 0 = n` is high-risk overfitting.

## GAP-0005 — conditional-probability product inference

### Revised class

`LIBRARY_MISSING`

### Exact operation and source transition

G09 `a0`: from `P(A) = 0.5` and `P(B | A) = 0.8`, apply

`P(A and B) = P(A) * P(B | A)`

under the definedness condition `P(A) > 0`. The subsequent numeric product is
G09 `a1` and is covered by GAP-0001.

### Required mathematical meaning

The rule must preserve event identity, conditioning direction, probability-kind
typing, and the positive-denominator precondition. It must not conflate a model
probability with a p-value or posterior, and it must retain the joint event rather
than treating the product as an arbitrary arithmetic rewrite.

### What current HML can represent

The parser and AST represent conditional probability, joint events, and probability
expressions. The type system checks event/probability kinds, unit-interval constraints,
and several probability semantic barriers. Existing examples represent and
type-check conditional probability.

### Exact failure point

The v2 rule catalogue has no probability-law rule, and the bounded obligation engine
explicitly refuses distributional/random-variable claims outside its supported
subset. The type checker can establish that the expressions are well-typed; it does
not establish the conditional-product identity. HML G09's current rendering also
exposes a translation concern (random-variable declarations versus event-valued
claims), but that is secondary to the missing domain-law certificate.

### Relevant constructs and layer decision

- `ast/nodes.py::ProbabilityExpr` and `JointExpr`: current representation.
- `type_system/__init__.py`: current probability typing and barriers.
- `examples/statistics/conditional_expectation.hml`: current representational
  precedent.
- `reasoning/kernel.py`: no conditional-product rule.
- `verification/obligations/__init__.py`: probability/random-variable claims are
  outside the bounded discharge subset.

This belongs in a probability law library. The identity is domain knowledge over
existing HML objects, not a new primitive denotation or epistemic state. The core
needs a safe way to consume a library certificate, but it should not own the
probability axiom.

### Smallest remedy

Provide a named probability-law certificate/library entry for conditional product,
with explicit event compatibility and `P(A) > 0` obligations, and connect it through
the general theorem/evidence boundary. Keep the existing ProbabilityExpr surface and
types.

### Semantic impact

Proof state, operational rule application, and domain-law evidence: yes. Denotation,
typing, and epistemic status vocabulary: no new core meaning. The rule's precondition
must be recorded as a proof obligation.

### Dependencies and overfitting risk

Depends on a general theorem/evidence adapter and GAP-0001 for the final exact
product. It does not depend on GAP-0003 or GAP-0004. A reusable probability-law
library is general; a single hard-coded `0.5 * 0.8` rule is unacceptable overfitting.

## GAP-0006 — calculus rule execution and derivative evaluation

### Revised class

`LIBRARY_MISSING`

### Exact operation and source transitions

G10:

- `a1`: from `f(x) = 1/x` and `x != 0`, derive `f'(x) = -1/x^2`;
- `a2`: substitute `x = 2` and normalize to `f'(2) = -1/4`.

The denominator precondition is G10 `a0` and is already current HML.

### Required mathematical meaning

Differentiation must use a sound symbolic calculus rule, preserve the binder and
domain, and carry the nonzero-domain condition. Evaluation at a point must reuse
that condition and produce an exact rational result.

### What current HML can represent

HML has `DerivativeExpr`, typed binders, dimension analysis, and partiality/domain
obligations. The analysis example explicitly treats derivative expressions as
represented and checked for type/dimension, not evaluated. The exact evaluator
handles arithmetic but not symbolic derivative construction. The SymPy backend's
contract explicitly reports derivative expressions as dropped rather than pretending
to preserve them.

### Exact failure point

The current core can parse and type-check `derivative(1/x, x : Real)` and can record
`x != 0`; no trusted calculus rule or calculus evaluator turns it into `-1/x^2`.
The final rational evaluation is available once that formula exists, but the
derivative formula itself is not produced or certified by the current pipeline.

### Relevant constructs and layer decision

- Parser/AST `DerivativeExpr`: current representation.
- `type_system/__init__.py`: derivative type/dimension rules.
- `reasoning/partiality.py`: current denominator obligations.
- `examples/analysis/derivative_and_integral.hml`: explicit no-evaluation boundary.
- `backends/sympy.py`: derivative lowering is intentionally dropped.
- `verification/obligations/evaluate.py`: exact arithmetic after a formula exists.

This is a symbolic-calculus library problem. The existing derivative denotation and
domain machinery should remain stable; the calculus library supplies the theorem and
its side conditions.

### Smallest remedy

Add a calculus-law library/evidence adapter capable of differentiating the supported
symbolic fragment, returning a formula certificate plus domain obligations. Reuse
the existing partiality checker and exact rational evaluator for G10 `a2`.

### Semantic impact

Operational proof/evidence and rendering: yes. Existing derivative denotation,
typing, dimension semantics, and epistemic vocabulary: no new core meaning.

### Dependencies and overfitting risk

Depends on current partiality checks and GAP-0001's exact arithmetic adapter. It is
independent of GAP-0003, GAP-0004, and GAP-0005. A general differentiation library is
appropriate; a reciprocal-only rule is high-risk overfitting.

## Ranked triage table

“Current class” is the class recorded by the original gap report. “Revised class” is
the single primary class assigned here; secondary observations are described above.
“Fix now?” means on the Claude/HML-core track, not whether a corpus-side adapter is
worth scheduling.

| GAP | Current class | Revised class | Severity | Generality | Minimal fix | Fix now? |
|---|---|---|---|---|---|---|
| GAP-0003 | `REQUIRES_NEW_CORE_SEMANTIC` | `CORE_SEMANTIC_MISSING` | High | High | Certified underdetermination status plus generic non-entailment evidence | Yes |
| GAP-0004 | `REQUIRES_NEW_CORE_SEMANTIC` | `CORE_SEMANTIC_MISSING` | High | High | Generic quantified inference; additive identity supplied by library | Yes, after GAP-0003 design |
| GAP-0005 | `REQUIRES_NEW_CORE_SEMANTIC` | `LIBRARY_MISSING` | High | Medium-High | Conditional-product law with positive-denominator obligation | No, library track |
| GAP-0006 | `EXPRESSIBLE_WITH_LIBRARY` | `LIBRARY_MISSING` | Medium-High | High | Symbolic-calculus certificate plus existing domain guard | No, library track |
| GAP-0001 | `EXPRESSIBLE_WITH_LIBRARY` | `TRANSLATION/CANONICALIZATION_PROBLEM` | Medium | High | Wire existing exact evaluator/equivalence certificates to trajectory actions | No core change |
| GAP-0002 | `EXPRESSIBLE_WITH_LIBRARY` | `TRANSLATION/CANONICALIZATION_PROBLEM` | Medium | High | Expose existing definition unfolding as dependency-preserving evidence | No core change |

## A. What Claude should fix in `hamiltonian-lang` now

1. GAP-0003: add a generic, sound underdetermination result and certificate to the
   proof-state/evidence contract. The two-sided model evidence must be validated; an
   open goal must not be relabelled merely because a search timed out.
2. GAP-0004: add generic quantified theorem application/introduction with binder
   freshness and scope obligations. Do not add a Natural-specific identity rule.
3. Add or expose a general evidence/theorem-library boundary so domain libraries can
   participate without becoming ad hoc trusted core rules.

Claude should not add arithmetic, probability, or calculus primitives to the core in
response to these ten examples. GAP-0001 and GAP-0002 should use capabilities that
already exist in the pinned tree. GAP-0005 and GAP-0006 belong in libraries.

## B. Which gaps should become libraries

- GAP-0001: exact arithmetic normalization/evaluation and symbolic-equivalence
  certificates. The exact evaluator/equivalence code already provides much of this;
  the missing work is a stable adapter and evidence format.
- GAP-0002: definition-unfolding/function-execution traces. The recursive evaluator
  already exists; the library/adapter should expose intermediate dependency results.
- GAP-0005: probability laws, beginning with conditional product and its definedness
  obligations.
- GAP-0006: symbolic calculus laws and exact evaluation, beginning with reciprocal
  differentiation.

These libraries must return typed, provenance-bearing certificates. They must not
mutate HML syntax or silently mark a v2 derivation `VERIFIED` without a registered
checker/evidence record.

## C. Which gaps are caused by the corpus schema rather than HML

None of GAP-0001 through GAP-0006 is primarily a schema-caused mathematical gap.
`schemas/trajectory.schema.json` correctly makes the neutral trajectory canonical,
allows `GAP_DOCUMENTED`, and permits `undetermined`/`verified_as_undetermined` at
the corpus level.

The schema does create a measurement ambiguity that should be corrected before the
next rate is treated as a product metric:

- `action.hml_support` is a single enum, so “HML can represent it,” “HML can verify
  it,” and “a library can verify it” are easy to conflate;
- `action.verification` records the canonical/oracle result but has no separate
  `hml_native_verification` field;
- `epistemic_status` is a free-form claim list and has no typed countermodel/evidence
  payload for underdetermination;
- the schema intentionally permits a `GOLD_CANONICAL_VERIFIED` trajectory whose HML
  rendering is `GAP_DOCUMENTED`, so canonical verification must never be read as HML
  verification.

This is a schema/metric refinement, not the cause of the six mathematical gaps.

## D. Does the 13.04% CoreGapRate survive?

No. The same denominator and the same 23 transitions yield `2/23 = 8.70%` after
reclassification. The third original core transition, G09 `a0`, is a probability
library law. The arithmetic/function labels move to the translation/canonicalization
boundary, while derivative evaluation remains library-level.

The revised rate is still nonzero and meaningful: generic underdetermination and
generic quantified inference are real core-semantic work. It is not evidence that
HML's entire design is wrong.

## E. Minimum HML changes before rerunning the same Gold-10

For an HML-native verification rerun, the minimum is:

1. GAP-0003: certified underdetermination status and sound non-entailment evidence;
2. GAP-0004: generic quantified inference with binder hygiene;
3. a stable, auditable certificate boundary that lets existing arithmetic/function
   evaluators and external probability/calculus libraries feed the v2 proof/evidence
   path without adding example-specific core rules.

No new HML syntax is required for GAP-0001, GAP-0002, GAP-0005, or GAP-0006. The
minimum library/adapters needed for the same Gold-10 are: exact arithmetic/function
evidence, conditional-product law, and reciprocal differentiation. Those are not
core-language changes.

If the rerun accepts the neutral trajectory as canonical and treats HML as a
rendering, even the first two can be measured as documented capabilities rather than
implemented immediately. If the success criterion is “the HML rendering itself
reports every Gold-10 transition as natively verified,” the two core changes and the
certificate boundary are required.

## F. Dependency order

1. Freeze the support taxonomy and separate native HML verification from external
   library/oracle verification in the measurement contract.
2. Specify the generic certificate boundary, reusing existing evidence/provenance
   records and exact evaluator interfaces.
3. Route GAP-0001 and GAP-0002 through that boundary; this supplies reusable numeric
   and definition-evaluation evidence.
4. Specify and implement GAP-0003's underdetermination result, including model
   validation and the distinction between `OPEN`, `UNSUBSTANTIATED`, and certified
   undetermined.
5. Specify and implement GAP-0004's generic quantified inference, using existing
   binder identity/alpha-equivalence and the arithmetic certificate for the body.
6. Add the probability-law library/certificate for GAP-0005, then reuse GAP-0001 for
   the numeric product.
7. Add the calculus-law library/certificate for GAP-0006, then reuse current
   partiality checks and GAP-0001 for the exact value.
8. Rerun the unchanged Gold-10 trajectories and compare per-transition native,
   library, translation, and core outcomes.

Steps 4 and 5 are the only core-semantic changes. Steps 3, 6, and 7 should not be
implemented by editing or weakening the frozen experimental HML artifacts.

## G. Strict recommendation

**FIX TWO GENERIC CORE SEMANTICS, REVISE THE SUPPORT METADATA, AND RERUN THE SAME
GOLD-10.**

This is a deliberately narrow version of “FIX CORE AND RERUN GOLD-10”: fix only
certified underdetermination and generic quantified inference in the HML-core track;
route arithmetic/function evaluation through existing capabilities; and build
probability/calculus as libraries. Do not expand to Gold-100 until the unchanged
Gold-10 rerun demonstrates that these classifications are stable.

The evidence does not support `HML CORE DESIGN IS FUNDAMENTALLY WRONG`. The core has
sound fail-closed boundaries, useful evaluator/equivalence components, typed
probability/derivative representations, and explicit scope semantics. It is missing
two generic reasoning-state operations and a clean integration boundary—not a new
mathematical universe.
