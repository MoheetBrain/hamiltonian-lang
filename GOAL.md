# GOAL — Hamiltonian Lang

> **Hamiltonian Lang is a typed mathematical intermediate representation and externally
> inspectable reasoning protocol designed to test whether mathematical representation can
> be co-designed and empirically optimised with language models, compilers, verifiers and
> specialist execution engines.**

Its purpose is not to assert that a newly invented notation is intrinsically superior.
Its purpose is to make **mathematical representation itself a controlled experimental
variable**.

---

## 1. Governing research question

The primary research question is:

> **Can a mathematical representation co-designed with a language model, compiler and
> verifier produce reproducible improvements in semantic fidelity, verified completion,
> mathematical accuracy or generalisation over matched natural-language,
> conventional-notation and direct formal-system baselines?**

The secondary causal question is:

> **If an improvement exists, which component produces it: input representation, external
> reasoning workspace, verifier-guided repair, specialist-tool routing, model adaptation or
> redesign of the representation itself?**

Hamiltonian therefore separates:

$$
\text{surface syntax}
\neq
\text{semantic identity}
\neq
\text{external reasoning state}
\neq
\text{backend execution}
\neq
\text{verification}
\neq
\text{mathematical correctness}
$$

A parser accepting an output does not prove that its meaning is preserved.
A backend executing an output does not prove semantic equivalence.
A verifier accepting a claim does not establish trust unless the verifier itself is sound
for the construct being tested.

---

## 2. Scope

### 2.1 Meaning of "cross-domain"

Cross-domain means that one semantic layer is tested across several mathematical domains.
It does **not** mean that Hamiltonian currently represents all mathematics, replaces every
formal system or provides one universal foundation.

The initial empirical scope is limited to structures for which deterministic or
independently checkable semantic oracles can be constructed, including:

- logical propositions, binders, quantifiers and scope;
- algebraic expressions and verified transformations;
- typed functions, relations and dependencies;
- probability distributions and statistical models;
- statistical evidence and epistemic distinctions;
- units and physical dimensions;
- constrained optimisation;
- selected proof obligations;
- symbolic and numerical computation;
- selected concept-family and abstraction tasks.

A construct may enter a confirmatory experiment only when it can be:

1. parsed deterministically;
2. represented canonically under a declared equivalence contract;
3. checked or scored independently;
4. failed loudly when unsupported;
5. tested with both valid and adversarial examples.

### 2.2 Meaning of "reasoning in Hamiltonian"

Hamiltonian does not claim to observe or replace a model's private internal representation.

The phrase **reasoning in Hamiltonian** means:

> The model is required to construct, update and consume an externally inspectable
> Hamiltonian workspace containing intermediate mathematical objects, assumptions,
> dependencies, goals, transformations, obligations and conclusions.

The causal effect of that external workspace can be compared against matched alternatives.
No claim is made that the model's latent neural computation literally occurs in
Hamiltonian syntax.

---

## 3. Non-goals

Hamiltonian does not presently claim to:

- replace Lean, Isabelle, Rocq, Stan, SymPy, OpenMath, MMT or other specialist systems;
- represent every branch of mathematics;
- expose a model's private internal language;
- prove that additional formal structure necessarily improves reasoning;
- make a weak model mathematically expert through notation alone;
- infer mathematical novelty from linguistic novelty;
- admit concepts solely because a model judges them novel;
- treat parser acceptance as semantic correctness;
- treat backend execution as proof of equivalence;
- treat failed counterexample search as proof;
- begin model training before the representation has shown measurable value;
- begin reinforcement learning or self-play before rewards and verifiers are trustworthy;
- allow token efficiency to compensate for semantic corruption;
- claim benchmark superiority without frozen, reproducible evidence.

---

## 4. Novelty boundary

### 4.1 Correction of the earlier claim

An earlier description implied:

> ~~"Nobody has built a ground-up mathematical language for AI, taught it to an AI and used
> it to solve mathematics."~~

That claim is not defensible.

The project's prior-art audit identified:

> **AoA: Theorem Proving Agent over Abstract Syntax Tree of Redesigned Language**
> Xu, Ong Jun Leang, Wang, Li, Li, Ong and Watt
> arXiv:2607.16372, 17 July 2026

AoA describes Minilang as a proof language designed for LLM-based theorem proving and uses
JSON representations of Minilang's abstract syntax tree as the model interface. It reports
substantial reductions in token use, tool calls, API cost and runtime relative to a
source-editing agent.

Consequently, Hamiltonian may not claim novelty merely from:

- designing a formal language for LLM use;
- teaching an unfamiliar language through demonstrations;
- exposing an abstract syntax tree as JSON;
- allowing a model to manipulate a proof tree;
- using compiler or prover feedback;
- reducing token cost relative to source editing.

AoA and Minilang occupy enough of that package in theorem proving that these ingredients
cannot be presented as independently novel without a more granular comparison.

### 4.2 Established neighbouring systems

| System family | Established contribution | Hamiltonian's different question |
|---|---|---|
| Lean, Isabelle, Rocq | Exact definitions and kernel-checked proof | Is direct interaction with an existing proof language the best model-facing representation? |
| OpenMath | Semantic exchange of mathematical objects | Can semantic organisation be selected according to measured model performance? |
| MMT and OMDoc | Foundation-independent mathematical knowledge and interoperability | Can one higher-level representation function as a model-facing reasoning workspace and experimental variable? |
| Stan | Probabilistic modelling and inference | Can probabilistic models coexist with proof, dimensions, epistemics and other domains in one semantic layer? |
| SymPy and symbolic engines | Symbolic mathematical execution | Can symbolic execution be coordinated without making symbolic syntax the authoritative semantic representation? |
| DeepSeek-Prover, Seed-Prover, HunyuanProver and related systems | Training and search over existing formal proof languages | Should the representation itself be redesigned and experimentally compared? |
| Harmonic, Axiom and related workflows | Mathematical discovery or formalisation with machine-checked proof | Can a cross-domain intermediate workspace improve reasoning before destination-language compilation? |
| Minilang and AoA | LLM-oriented proof language and AST interaction | Can the same experimental principle extend across proof, probability, computation, dimensions, epistemics and concept governance? |

"One semantic representation feeding multiple systems" is not novel. OpenMath, MMT and
related systems have pursued that objective for decades.

### 4.3 Defensible novelty candidate

Hamiltonian's strongest novelty candidate is not any individual component.
It is the conjunction:

1. a cross-domain typed semantic intermediate representation;
2. an externally inspectable mathematical reasoning state;
3. explicit epistemic and statistical types;
4. formally governed concept proposals;
5. lowering into proof, probabilistic, symbolic and numerical engines;
6. model use of the representation as an intermediate workspace;
7. compiler feedback that changes the model's subsequent trajectory;
8. causal experiments treating representation design as an optimisable component of the AI
   system.

The central candidate contribution is item 8:

> **Treat mathematical representation as a controllable capability lever and test it under
> matched-model, matched-information and appropriately matched-compute conditions.**

Any statement that no other system combines all eight properties is a dated, search-based
negative result, not proof of absence.
Private, unpublished or undiscovered work may exist.

---

## 5. System architecture

Hamiltonian is defined as:

$$
\mathrm{HML}
=
\left(
\Sigma,\;
\mathcal{G},\;
\mathcal{S},\;
\mathcal{R},\;
\mathcal{E},\;
\mathcal{C},\;
\mathcal{B},\;
\mathcal{O}
\right)
$$

```text
NATURAL-LANGUAGE OR FORMAL TASK
                |
                v
     MODEL-FACING SURFACE  Σ
                |
                v
      GRAMMAR / COMPILER  G
                |
                v
       TYPED SEMANTIC CORE  S
          /          |          \
         v           v           v
 REASONING STATE R  EPISTEMICS E  CONCEPTS C
          \          |          /
                     v
       VERIFIER-GUIDED LOOP  O
  generate → check → diagnose → repair
                     |
                     v
       BACKEND LOWERING  B
       /       |       |       \
      v        v       v        v
    LEAN     STAN    SYMPY   NUMERICAL
```

---

## 6. The eight components

### 6.1 Σ — model-facing surface language

The surface language is the representation directly read or generated by a model.

Candidate families may include:

* labelled linear syntax;
* restricted symbolic ASCII;
* prefix or S-expression syntax;
* indentation-based blocks;
* constrained JSON;
* graph or triple representations;
* controlled mathematical English.

The surface is not selected because it appears elegant.
Candidates compete on:

* exact semantic fidelity;
* first-attempt and repaired parse success;
* error localisation;
* one-step repairability;
* robustness to truncation and corruption;
* token consumption;
* latency;
* cross-domain consistency;
* transfer to unseen semantic structures.

A surface is expendable.
No syntax is part of the permanent scientific claim unless it survives controlled
comparison.

---

### 6.2 𝒢 — grammar and compiler front end

The compiler front end must:

* parse valid Hamiltonian deterministically;
* reject unknown or invented types;
* preserve variable binding and quantifier scope;
* distinguish declarations, definitions, assumptions, constraints, observations and claims;
* enforce distribution and function parameter roles;
* detect unresolved names and incompatible types;
* recover safely from malformed or truncated model output;
* terminate on arbitrary input;
* preserve valid substructures surrounding local errors;
* emit actionable diagnostics with precise source locations;
* avoid leaking the complete target solution through repair messages.

Compiler diagnostics are part of the experimental intervention.
Their wording, error codes, source spans and suggested repairs may be optimised only through
controlled experiments.

---

### 6.3 𝒮 — typed semantic core

The semantic core represents:

* object identity;
* type;
* domain and codomain;
* variable, parameter and observation roles;
* assumptions;
* constraints;
* units and dimensions;
* functions and relations;
* dependencies;
* probability laws;
* definitions;
* invariants;
* equivalence conditions;
* obligations;
* provenance.

#### Canonicality

Hamiltonian does not require one permanent tree or surface for every mathematical object.
It requires:

> **Stable semantic identity and canonical comparison within explicitly declared
> equivalence contracts, while preserving multiple valid representations and verified
> transformations between them.**

Therefore:

```text
same semantic identity  ≠  same surface string
same denotation         ≠  same derivation
equivalent              ≠  structurally identical
analogous               ≠  equivalent
```

A linear transformation may validly have:

* a matrix view;
* a function view;
* a graph view;
* a tensor view.

Canonicalisation must not erase mathematically useful alternative representations.

#### Hashing and identity

Canonical hashing may be invariant under:

* verified binder-aware alpha-renaming;
* declared commutative reordering;
* certified normalisation rules;
* explicitly order-insensitive fields.

It must remain sensitive to:

* free-symbol identity;
* quantifier order;
* parameter roles;
* assumptions;
* dependencies;
* epistemic strength;
* dimensional structure;
* provenance where provenance is semantically relevant.

---

### 6.4 ℛ — external reasoning-state representation

Hamiltonian represents the movement of reasoning, not only final propositions.

Reasoning-state constructs may include:

* current goal;
* subgoal;
* assumption;
* pending obligation;
* case split;
* transformation;
* derivation;
* implication;
* equivalence;
* approximation;
* dependency;
* counterexample;
* unresolved branch;
* discharged obligation;
* final conclusion.

These relations must remain distinct:

```text
yields             ≠ implies
implies            ≠ equivalent
approximately      ≠ exactly equal
evidence           ≠ proof
failed refutation  ≠ verification
failure to reject  ≠ proof of the null
```

No silent coercion may convert a weaker relation into a stronger one.

---

### 6.5 ℰ — epistemic type system

Hamiltonian explicitly types the status and strength of mathematical and statistical claims.

Initial epistemic forms may include:

```text
definitionally_true
proved
disproved
conjectured
model_conditional
estimated
approximately_equal
almost_sure
with_high_probability(regime := ...)
fail_to_reject(alpha := ..., p_value := ...)
unsupported
unresolved
```

The purpose is to block silent upgrades such as:

```text
compatible with evidence
        ↓
apparently true
        ↓
certain
        ↓
mathematically proved
```

Required distinctions include:

```text
PValue                 ≠ Probability
PValue                 ≠ PosteriorProbability
ConfidenceInterval     ≠ CredibleInterval
Evidence               ≠ Proof
Estimate               ≠ ExactValue
ModelConditionalClaim  ≠ UnconditionalTruth
```

An epistemic claim may be promoted only by an explicitly permitted evidence transition.

---

### 6.6 𝒞 — concept registry and governed concept proposals

A model may propose candidate mathematical concepts.
It may not grant them official status by its own judgment.

A candidate concept must include:

* a proposed name;
* type;
* formal definition;
* domain and codomain;
* assumptions;
* constraints;
* invariants;
* known equivalences;
* examples;
* counterexamples;
* proof obligations;
* computation method;
* relationships to existing concepts;
* intended mathematical or computational utility.

#### Concept-admission pipeline

Every proposal must pass:

1. binder-aware semantic canonicalisation;
2. comparison against existing equivalence classes;
3. symbolic or domain-specific equivalence checks where available;
4. bidirectional counterexample search;
5. classification of its relationship to existing concepts;
6. explicit unresolved status when equivalence cannot be decided;
7. measurable utility testing;
8. adversarial review;
9. prior-art review before any claim of world novelty.

Permitted relationship classifications include:

```text
EXACT_DUPLICATE
ALPHA_EQUIVALENT
SYNONYM
REFORMULATION
SPECIAL_CASE_OF
GENERALISATION_OF
DUAL_OF
TRANSFORMATION_OF
COMBINATION_OF
INDEPENDENT_BUT_RELATED
DISTINCT
UNRESOLVED
```

Permitted lifecycle states include:

```text
PROPOSED
NORMALISED
DUPLICATE
RELATED
PROBATIONARY
ADMITTED
REJECTED
UNRESOLVED
```

A concept must demonstrate at least one measurable form of utility:

* compression of recurring structure;
* derivational reuse;
* shorter or more reliable proofs;
* improved transfer to related tasks;
* improved retrieval;
* reduced computation or search;
* discovery of valid relationships among existing concepts.

A concept can be new to Hamiltonian without being new to mathematics.
The project must distinguish:

```text
new to the registry
new representation of a known concept
independent rediscovery
new relationship between known concepts
candidate new mathematics
externally supported mathematical novelty
```

The governing law is:

> **The model proposes; independent evidence admits.**

---

### 6.7 ℬ — backend lowering

Hamiltonian coordinates specialist systems rather than replacing them.

Potential backends include:

* Lean and other proof assistants;
* Stan and other probabilistic systems;
* SymPy and symbolic engines;
* numerical solvers;
* optimisation systems;
* SMT or constraint solvers;
* graphs;
* LaTeX;
* controlled natural language.

Every lowering must produce more than executable code.
It must produce:

1. the backend representation;
2. a field-level semantic-preservation report;
3. residual proof or execution obligations;
4. provenance linking the result to the source semantic object.

For each semantic field $s_i$:

$$
\operatorname{status}(s_i)
\in
\left\{
\texttt{EXACT},\;
\texttt{ENCODED\_WITH\_OBLIGATION},\;
\texttt{APPROXIMATED},\;
\texttt{DROPPED},\;
\texttt{UNSUPPORTED}
\right\}
$$

Each complete lowering receives one overall status:

```text
EXACT
CONDITIONAL
LOSSY
REJECTED
```

Rules:

* A task-critical field may not be dropped silently.
* A translation that loses a critical field must be rejected.
* A lossy translation may proceed only when the caller explicitly permits the identified
  loss.
* Backend parsing or execution does not prove semantic equivalence.
* Successful theorem-prover execution counts only when the trusted kernel verifies the
  relevant claim without prohibited axioms or placeholders.
* Backend support must be stated per construct, not as a global yes-or-no claim.

#### Round-trip tests

Two forms of round-trip must remain distinct:

```text
PURE ROUND-TRIP
HML → backend representation → recovered HML

PASSPORT-ASSISTED ROUND-TRIP
HML → backend representation + semantic passport → recovered HML
```

The pure round-trip measures what the backend representation itself preserves.
The passport-assisted round-trip measures whether the complete Hamiltonian system preserves
the source semantics.
These results must not be conflated.

---

### 6.8 𝒪 — empirical representation optimisation

The language is not sacred.
Its surface syntax, selected semantic organisations, diagnostic policies and concept
governance mechanisms survive only when measured evidence supports them.

However, optimisation must be **constrained and phase-specific**.
An unrestricted weighted score is prohibited because it could allow token savings to
compensate for corrupted meaning.

#### Acquisition phase

Let:

* $F_L$ be exact semantic fidelity;
* $P^{\mathrm{repair}}_L$ be parse success after the permitted repair budget;
* $R_L$ be one-step repair success;
* $T_L$ be token consumption;
* $C_L$ be compute or latency;
* $K_L$ be constitutional failures;
* $U_L$ be truncation;
* $F_{L,d}$ be fidelity in domain $d$.

The eligible set is:

$$
\mathcal{E}_{\mathrm{acq}}
=
\left\{
L \;:\;
K_L = 0,\;
U_L = 0,\;
F_L \geq F_{\min},\;
P^{\mathrm{repair}}_L \geq P_{\min},\;
\min_d F_{L,d} \geq F_{\mathrm{floor}}
\right\}
$$

Among eligible candidates:

$$
L_{\mathrm{acq}}^{*}
=
\operatorname*{LexMax}_{L \in \mathcal{E}_{\mathrm{acq}}}
\left(
F_L,\;
P^{\mathrm{repair}}_L,\;
R_L,\;
-T_L,\;
-C_L
\right)
$$

Semantic fidelity and constitutional validity are gates.
Efficiency is considered only after those gates are satisfied.

#### Reasoning phase

Let:

* $V_L$ be task-appropriate verified completion;
* $A_L$ be final-answer accuracy;
* $G_L$ be generalisation;
* $E^{\mathrm{struct}}_L$ be structural-error rate;
* $T_L$ be token use;
* $C_L$ be compute or latency.

Among candidates satisfying semantic-preservation and safety constraints:

$$
L_{\mathrm{reason}}^{*}
=
\operatorname*{LexMax}
\left(
V_L,\;
A_L,\;
G_L,\;
-E^{\mathrm{struct}}_L,\;
-T_L,\;
-C_L
\right)
$$

The exact ordering and primary endpoint must be preregistered for each experiment.
No ordering may be changed after results are observed.

#### Language mutation

A proposed mutation may modify only one major causal component per controlled experiment:

```text
surface syntax
semantic organisation
diagnostic policy
curriculum policy
model
verifier coverage
concept-governance policy
```

Formally:

$$
\left\lVert \Delta S \right\rVert_0 = 1
$$

The mutation must:

1. reproduce a measured incumbent failure;
2. state the proposed causal mechanism;
3. preserve all frozen comparison conditions;
4. pass retention and adversarial tests;
5. improve the preregistered endpoint;
6. replicate before promotion.

Models and agents may propose mutations.
Only external verification and controlled evidence may promote them.

---

## 7. World today versus Hamiltonian's target

```text
WORLD TODAY
===========
natural-language task
        |
        v
informal reasoning or planning
        |
        v
destination-specific formalisation
        |
   ┌────┼─────┐
   v    v     v
 Lean  Stan  SymPy

The model learns each destination representation separately.
Cross-domain meaning, reasoning state and epistemic status may remain fragmented.


HAMILTONIAN TARGET
==================
natural-language or formal task
        |
        v
empirically selected surface
        |
        v
typed semantic identity
        |
   ┌────┼────────────┐
   v    v            v
state  epistemics  obligations
   \    |            /
        v
verifier-guided reasoning loop
        |
        v
task-appropriate backend
```

Hamiltonian's proposed role is that of a mathematical compiler frontend, semantic workspace
and experimental control layer.

---

## 8. Causal hypotheses

The project separates the following hypotheses.
They may succeed or fail independently.

### H1 — input representation

> Providing a problem in Hamiltonian improves the final mathematical result.

Isolation rule:

* same underlying semantic object;
* same model and checkpoint;
* same reasoning protocol;
* same output format;
* vary only the input representation.

A positive H1 result does not establish that the model benefits from using Hamiltonian as an
intermediate workspace.

---

### H2 — external reasoning workspace

> Requiring the model to construct and use a Hamiltonian workspace improves the final
> mathematical result.

Isolation rule:

* same input representation;
* same final answer format;
* Hamiltonian workspace versus a matched structured-English or conventional workspace;
* equivalent mathematical information;
* preregistered compute and call budgets.

A Hamiltonian derivation must contain genuine intermediate state.
Merely wrapping the final answer in Hamiltonian syntax does not test H2.

---

### H3-system — verifier-guided repair as a complete intervention

> Adding compiler or verifier feedback and a bounded repair opportunity improves verified
> completion.

Isolation rule:

* same input;
* same workspace;
* same model;
* feedback and repair added only to the treatment condition.

This measures the practical value of the complete feedback system.

---

### H3-compute-matched — information value of feedback

> Verifier feedback remains advantageous when the comparator receives an equivalent
> additional inference budget.

Isolation rule:

* matched calls or generation budget;
* comparator receives additional unguided compute;
* treatment receives diagnostic information;
* all other conditions remain fixed.

A positive H3-system result without a positive H3-compute-matched result may indicate that
the gain came primarily from additional inference rather than diagnostic information.

---

## 9. Matching contracts

The word "matched" must be operationally defined.

### Model matching

Conditions must use the same:

* model checkpoint;
* immutable model digest;
* quantisation;
* tokenizer;
* sampling configuration;
* system prompt policy;
* runtime implementation, unless runtime itself is the variable.

### Information matching

Conditions must receive mathematically equivalent task content generated from the same
canonical semantic object.
No treatment arm may receive hidden assumptions, answers or intermediate results unavailable
to its comparator.

### Semantic-exposure matching

Syntax-acquisition candidates must receive the same demonstrations by mathematical content.
A verbose syntax must not receive fewer examples merely to equalise token count.
Its token cost is an outcome of the representation.

### Compute matching

Where compute is part of the causal question, conditions must predeclare:

* maximum calls;
* generation tokens;
* repair opportunities;
* search width;
* wall-time policy;
* tool-use budget.

### Runtime matching

Primary representation comparisons must use one shared eligible runtime configuration with:

* zero prompt truncation;
* one common context policy;
* one common completion reserve;
* one common safety reserve.

### Backend matching

A task must be compared against the strongest appropriate native representation or system.
Not every backend is appropriate for every task.

| Task family | Appropriate direct comparator |
|---|---|
| formal proof | Lean, Isabelle, Rocq or another suitable prover |
| probabilistic modelling | Stan or another probabilistic language |
| symbolic algebra | SymPy or another symbolic engine |
| constraints | SMT or optimisation representation |
| general mathematical reasoning | English, structured English, LaTeX |
| semantic interchange | OpenMath, MMT or another semantic representation |

---

## 10. Endpoints and measurements

Every experiment must declare exactly one primary endpoint before execution.
The endpoint may differ by hypothesis.

Typical choices:

* H1 or H2: paired final-answer accuracy or task-appropriate verified completion;
* H3: paired verified-completion difference;
* acquisition: exact semantic fidelity;
* backend lowering: canonical semantic round-trip;
* concept admission: false-novelty and duplicate-rejection rates.

Key secondary endpoints may include:

* first-attempt parse success;
* repaired parse success;
* semantic-preservation rate;
* variable-binding errors;
* quantifier-scope errors;
* type errors;
* distribution-role errors;
* unsupported-assumption rate;
* dimensional errors;
* epistemic-calibration errors;
* one-step repair success;
* diagnostic localisation;
* token consumption;
* latency;
* generalisation to modified problems;
* transfer to unseen formally defined concepts.

The following outcomes must remain separate:

```text
format adherence
parsing
name resolution
type checking
semantic preservation
obligation discharge
backend execution
verifier acceptance
final mathematical correctness
```

No earlier stage may stand in for a later one.

---

## 11. Evidence levels

Every project claim must identify its evidential level.

```text
SPECIFIED
The behaviour is defined but not implemented.

IMPLEMENTED
Code exists.

UNIT_TESTED
The implementation passes local deterministic tests.

ADVERSARIALLY_TESTED
Targeted negative and corruption tests have been run.

DEVELOPMENTAL
A result was observed on development data and may guide allocation.

CONFIRMATORY
A frozen preregistered comparison passed its declared analysis.

REPLICATED
The effect reproduced on a fresh task tranche, model, checkpoint or laboratory.

SPECULATIVE
The claim remains a hypothesis or design ambition.
```

Implementation, test count and conformance are evidence about the research instrument.
They are not evidence that Hamiltonian improves mathematical reasoning.

---

## 12. Success ladder

Hamiltonian advances through explicit gates.

### G0 — trustworthy experimental instrument

Requirements include:

* deterministic parsing for the supported subset;
* sound type and role checking for declared supported constructs;
* actionable diagnostics;
* no silent unsupported features;
* reliable semantic comparison;
* preserved raw outputs;
* reproducible experiment state;
* trusted or explicitly bounded verifier behaviour.

Passing G0 means that the experiment can be run.
It does not support the central thesis.

### G1 — model acquisition

At least one surface must satisfy the frozen acquisition thresholds for:

* repaired parse success;
* exact semantic fidelity;
* domain floors;
* zero constitutional failures;
* zero truncation;
* acceptable cost.

Exact numerical thresholds belong to the preregistration and may not be altered after results
are observed.

Passing G1 means:

> The model can faithfully use one Hamiltonian surface.

It does not mean that Hamiltonian improves mathematical reasoning.

### G2 — developmental reasoning signal

A bounded H2 or H3 scout must show a credible positive direction on held-out development
tasks without catastrophic domain regressions.

Passing G2 justifies a confirmatory experiment or small adaptation pilot.
It is not confirmatory evidence.

### G3 — confirmatory effect

A frozen, adequately powered comparison must support the preregistered primary endpoint.

Passing G3 supports a narrow causal claim for the tested model, task distribution and
intervention.

### G4 — replication

The effect must reproduce using at least one of:

* a fresh task tranche;
* another model or checkpoint;
* another curriculum;
* another random seed;
* an independent implementation or laboratory.

Passing G4 supports limited generalisation beyond the original experiment.

### G5 — adaptation adds value

A matched adapter or fine-tuning experiment must improve the intended endpoint without:

* catastrophic forgetting;
* semantic drift;
* hidden target leakage;
* mere memorisation of syntax;
* regression on transfer tasks.

### G6 — controlled language evolution

A model- or agent-proposed representation mutation must produce a replicated improvement over
the incumbent under frozen conditions.

Only at G6 has the project shown evidence that the language itself can be improved through a
closed empirical loop.

---

## 13. Constitutional invariants

The following rules are non-negotiable.

1. **Semantic fidelity is non-compensatory.**
2. **Unsupported constructs fail loudly.**
3. **No backend receives credit for semantics it did not preserve.**
4. **Models may propose changes; external checks determine promotion.**
5. **One major causal component changes per controlled experiment.**
6. **Raw attempts, failures, diagnostics and repairs are retained.**
7. **Development, promotion and transfer data remain separated.**
8. **Negative results are preserved and reported.**
9. **No current implementation status is promoted into a scientific conclusion.**
10. **Every claim states its evidence level.**
11. **No benchmark threshold is changed after observing the relevant result.**
12. **No repair diagnostic may reveal the hidden target answer.**
13. **Failed counterexample search is not proof of equivalence.**
14. **Semantic similarity is soft evidence, never a substitute for symbolic or independent
    checks.**
15. **A model-generated claim cannot verify itself.**
16. **Critical verifier uncertainty must propagate as unresolved, not verified.**
17. **Efficiency may break ties only after correctness and fidelity gates pass.**
18. **Experiment failures may trigger redesign, but may not be silently removed from the
    record.**

---

## 14. Failure modes

Hamiltonian may fail because:

1. no representation improves the preregistered endpoint over matched baselines;
2. any apparent gain disappears when information and compute are controlled;
3. structured English or ordinary formal notation closes the gap;
4. the gain comes from scaffolding rather than Hamiltonian semantics;
5. the model cannot reliably acquire any candidate surface;
6. formal restrictions improve parsing while damaging mathematical reasoning;
7. translation through the semantic core changes the intended meaning;
8. backend lowering drops or weakens task-critical information;
9. the representation is accurate but too expensive or slow to use;
10. apparent success depends on pretraining asymmetry rather than representation quality;
11. the verifier incorrectly accepts invalid results;
12. repair diagnostics leak the solution;
13. the winning syntax overfits the development tournament;
14. an effect disappears on hidden promotion or transfer tasks;
15. fine-tuning improves syntax compliance but not mathematical capability;
16. adaptation causes catastrophic forgetting or domain regression;
17. concept admission mistakes renaming or reformulation for novelty;
18. automatic concept creation generates complexity without measurable utility;
19. language mutation optimises benchmark artefacts instead of general capability;
20. positive effects fail independent replication.

Failure on a well-posed question must be reported.
A negative result obtained under frozen, fair conditions is a contribution.
A positive result obtained by moving goalposts is not.

---

## 15. Stopping and continuation rules

### Acquisition failure

```text
No candidate passes the developmental acquisition screen
        ↓
permit at most one evidence-targeted redesign
        ↓
rerun on fresh development tasks
        ↓
if still unsuccessful, stop acquisition work
```

A failed acquisition gate does not refute H1, H2 or H3 in principle.
It means the current surface and teaching protocol failed the prerequisite.

### Acquisition succeeds but no reasoning signal appears

```text
G1 passes
but
G2 shows no credible H2 or H3 signal
        ↓
do not fine-tune
do not begin RL
do not begin self-play
do not begin automatic language evolution
```

A learnable language is not necessarily a useful language.

### Developmental signal fails confirmation

```text
G2 positive
but
G3 negative
        ↓
report the confirmatory null
retain the developmental result as non-confirmatory
do not claim capability improvement
```

### Positive effect fails replication

```text
G3 positive
but
G4 negative
        ↓
classify the effect as local, unstable or distribution-specific
```

### Concept-governance failure

A concept system that cannot reliably reject disguised duplicates or false novelty may remain
available for candidate generation, but it may not automatically admit concepts or influence
confirmatory claims.

### Backend-preservation failure

A backend route that cannot preserve or explicitly account for task-critical semantics must
be classified unsupported for that construct.

---

## 16. Recursive improvement architecture

The fast inner loop is:

```text
GENERATE
   ↓
PARSE AND CHECK
   ↓
VERIFY OR FALSIFY
   ↓
DIAGNOSE
   ↓
BOUNDED REPAIR
   ↓
REVERIFY
   ↓
STORE COMPLETE EPISODE
```

A stored episode should include:

* canonical task identity;
* semantic-family and skill identifiers;
* model and language versions;
* raw attempt zero;
* parser, resolver and type outcomes;
* verifier evidence;
* diagnostic;
* repair plan;
* repaired output;
* counterexamples;
* final verdict;
* provenance;
* contamination status.

The model-improvement loop is:

```text
verified recurring failures
        ↓
targeted curriculum
        ↓
bounded adaptation
        ↓
retention and transfer tests
        ↓
promote or roll back
```

The slower language-improvement loop is:

```text
replicated failure pattern
        ↓
single-component language mutation
        ↓
matched incumbent-versus-candidate experiment
        ↓
retention and adversarial testing
        ↓
replication
        ↓
promote or roll back
```

The governing law is:

> **The compiler may improve the model, the model's verified errors may improve the
> curriculum, and replicated failure patterns may motivate language mutations. No stage may
> promote itself without independent evidence.**

---

## 17. The result that would matter

A meaningful confirmatory result would take the form:

> Using the same base model, mathematical information and preregistered compute policy,
> Hamiltonian reasoning increased paired answer accuracy by **X** percentage points,
> increased task-appropriate verified completion by **Y** percentage points, reduced
> structural errors by **Z%**, and transferred better to unseen formally defined concepts
> than matched structured English, conventional notation and direct formal-language
> interaction.

That result would differ materially from:

> "We trained another model to write Lean."

It would provide evidence that:

> **Representation design is itself a controllable capability lever.**

Until such a result survives confirmatory evaluation and replication, the central thesis
remains:

```text
UNPROVEN
NOT REFUTED
EMPIRICALLY TESTABLE
```

---

## 18. Defensible one-sentence claim

Do not say:

> "Hamiltonian is the first mathematical language for AI."

Do not say:

> "Hamiltonian makes AI better at mathematics."

Do not say:

> "Hamiltonian is a machine-native internal language."

Say:

> **Hamiltonian Lang is a cross-domain, typed mathematical intermediate representation and
> externally inspectable verifier-guided reasoning protocol whose surface syntax, selected
> semantic structures and concept-governance mechanisms are treated as controlled
> experimental variables, tested under matched conditions against natural language,
> conventional notation and existing formal systems.**

---

## 19. Document boundary

This file defines the project's stable mission, causal hypotheses, constitutional invariants,
success criteria and failure rules.
It must not become a volatile implementation log.

The following belong outside `GOAL.md`:

* current commit identifiers;
* current branch and tag names;
* test counts;
* active agent status;
* current hardware availability;
* temporary implementation defects;
* local Lean, Mathlib, Stan or SymPy installation status;
* current benchmark progress;
* current winning syntax;
* current model-call counts;
* mutable backend support details;
* live project bottlenecks.

Those belong in the roadmap, status reports, evaluation manifests, backend support matrices
and decision records.

Any change to this goal document must explain:

1. which scientific or governance problem requires the change;
2. whether the change affects a frozen hypothesis or endpoint;
3. whether previous results remain comparable;
4. which decision record authorises it;
5. whether a new experiment version is required.

The goal is not to protect Hamiltonian from failure.
The goal is to make success or failure **measurable, causal, reproducible and honest**.
