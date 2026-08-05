# GOAL — Hamiltonian Lang

**A cross-domain, typed mathematical intermediate representation and verifier-guided
reasoning protocol, whose syntax, semantic organisation and concept system are treated as
experimentally optimisable variables.**

---

## 0. The correction that must come first

An earlier version of this document implied a novelty claim that is **no longer
defensible**:

> ~~"Nobody has built a ground-up mathematical language for AI, taught it to an AI, and
> used it to solve mathematics."~~

That slogan is occupied.

**Verified prior art.** *AoA: Theorem Proving Agent over Abstract Syntax Tree of Redesigned
Language* (Xu, Ong Jun Leang, Wang, Li, Li, Ong, Watt; arXiv 2607.16372, 17 July 2026).
Retrieved and checked, not cited from memory. It describes **Minilang** as "a recent proof
language that reaches SOTA on LLM-based proving but is too new for LLMs' training corpora",
and states that "the model supplies proofs as JSON representations of Minilang's AST —
native to tool-calling LLMs", reducing API cost and token consumption relative to a
source-editing agent.

**Therefore Hamiltonian may not claim novelty from any of these:**

- designing a new formal language aimed at LLMs
- exposing an AST as JSON for a model to edit
- teaching a language through demonstrations rather than corpus exposure
- using compiler or prover feedback in the loop
- reducing token cost relative to editing source text

**AoA has already demonstrated that package for theorem proving.**

*(One point in the source material — that Minilang and its tree-edit interface are too
tightly coupled to ablate cleanly — is **UNVERIFIED**: it does not appear in the abstract
retrieved. It is not relied upon below.)*

## 1. What is left, stated precisely

The remaining gap is a **conjunction**, and it is the whole claim:

> Has anyone built and rigorously tested a cross-domain, AI-optimised mathematical
> reasoning substrate that:
>
> 1. represents mathematical content canonically;
> 2. represents transformation and reasoning **state** explicitly;
> 3. types **epistemic strength** and statistical claims;
> 4. permits **formally governed concept creation**;
> 5. lowers into proof, probabilistic **and** computational engines;
> 6. lets the model **reason in** that representation, not merely emit it;
> 7. uses compiler feedback to change the reasoning **trajectory**;
> 8. and empirically **optimises the language itself** under matched-model,
>    matched-information and matched-compute controls?

No published system combining all eight was found. That is a **search-based negative**, not
a proof of absence, and it is recorded as such.

Each near neighbour occupies part of the space:

| system | occupies | does **not** occupy |
|--------|----------|---------------------|
| **Lean · Isabelle · Rocq** | exact definitions, kernel-checked proofs | a representation *empirically selected* for LLM cognition |
| **OpenMath** | unambiguous semantic exchange of mathematical objects | LLM reasoning performance; verifier-guided thought |
| **MMT / OMDoc** | foundation-independent knowledge and interoperability | a compact model-facing language chosen by controlled experiment |
| **DeepSeek-Prover · Seed-Prover · HunyuanProver** | training and search to generate Lean proofs | redesigning the cross-domain representation itself |
| **Harmonic · Axiom · OpenAI workflows** | discovery plus Lean-certified proof | one semantic layer spanning proof, probability, units, computation, epistemics |
| **Minilang / AoA** | an LLM-oriented proof language and AST interaction model | a general IR spanning statistics, probabilistic models, computation, concept creation, multiple backends |

"One semantic representation feeding multiple systems" is **not novel** — OpenMath and MMT
have done it for two decades. The novelty candidate is item **8**: treating the
representation as an *optimisable variable* and measuring it.

## 2. Where the world routes mathematics today

```
WORLD TODAY                              HAMILTONIAN TARGET
===========                              ==================
  natural-language problem                 natural-language problem
            |                                        |
   informal argument / plan                          v
            |                          HAMILTONIAN SURFACE  (Σ)
  formalisation or tool routing         empirically selected, not chosen by taste
            |                                        |
   ┌────────┼────────┐                               v
   v        v        v                   TYPED CANONICAL OBJECT  (S)
 LEAN     STAN    SYMPY                              |
   |        |        |                   ┌───────────┼───────────┐
   v        v        v                   v           v           v
theorem  posterior expression      transformations epistemic  obligations
                                    dependencies    state      goals  (R, E)
representations stay separate;             └───────────┼───────────┘
the AI learns each destination                         v
                                        VERIFIER-GUIDED LOOP  (O)
                                     generate → check → diagnose → repair
                                                       |
                                        ┌──────┬───────┼───────┐
                                        v      v       v       v
                                      LEAN   STAN   SYMPY  NUMERICAL   (B)
```

## 3. The system, specified as eight components

$$\mathrm{HML} = (\Sigma,\; \mathcal{G},\; \mathcal{S},\; \mathcal{R},\; \mathcal{E},\; \mathcal{C},\; \mathcal{B},\; \mathcal{O})$$

### Σ — model-facing surface language
Compact linear, prefix, JSON or graph syntax. **Not chosen by taste.** Candidates compete
on *parseability · semantic fidelity · token cost · repairability*.
→ status: four candidates built; the Gemma tournament is the current bottleneck.

### 𝒢 — grammar and compiler front end
Rejects invented and truncated types · preserves binding and quantifier scope · checks
parameter roles · recovers from malformed output · emits **actionable repair diagnostics**.
→ status: implemented; `HML-T440` closes the invented-type hole with nearest-name repair
hints; 800 fuzz inputs produce 0 hangs and 0 crashes.

### 𝒮 — typed semantic core
Object identity · type · domain and codomain · variable role · parameter role · constraints
· units and dimensions · dependencies · probability law · assumptions · definitions ·
equivalence conditions.
**Different surface strings must map to one object when they genuinely mean the same thing.**
→ status: implemented; content hashing is invariant under renaming and sensitive to
quantifier order and role assignment.

### ℛ — reasoning-state representation
Encodes the *movement* of reasoning, not only final propositions: goal · subgoal ·
assumption · pending obligation · case split · transformation · derivation · implication ·
equivalence · counterexample · dependency.

The distinctions that justify the layer:

```
yields             ≠  implies
implies            ≠  equivalent
evidence           ≠  proof
failure to reject  ≠  proof of the null
```

→ status: implemented with no coercion between edge kinds.

### ℰ — epistemic type system
`definitionally_true · proved · disproved · conjectured · model_conditional · estimated ·
approximately_equal · almost_sure · with_high_probability(regime=…) ·
fail_to_reject(alpha, p_value) · unsupported`

Purpose: block the silent upgrade

```
compatible with evidence  →  apparently true  →  mathematically proved
```

→ status: implemented. `fail_to_reject` yields `Evidence`; `prove` demands `Proof`; no
coercion exists. `PValue` and `PosteriorProbability` are distinct types.

### 𝒞 — concept registry and controlled invention
A new term is admitted only with name · type · formal definition · domain · constraints ·
invariants · equivalences · counterexamples · proof obligations · computation method ·
relationship to existing concepts — **and it must compress recurring structure and survive
duplicate detection.**
→ status: **NOT TRUSTWORTHY.** Red-teaming admitted three disguised duplicates of one
concept. This subsystem currently fails its own kill criterion.

### ℬ — backend lowering
Lean statements and proofs · Stan programs · SymPy calculations · numerical execution ·
graphs, LaTeX, controlled English. **Each lowering reports its semantic loss** rather than
implying equivalence.
→ status: implemented and measured. Stan cannot express strict positivity, so most
distribution families cannot round-trip. Lean silently loses probability laws. Mathlib is
absent locally, so nearly nothing HML emits is Lean-expressible today.

### 𝒪 — empirical language optimisation *(the novelty candidate)*

$$L^{*} = \arg\max_{L}\ \mathbb{E}\Big[A_L + \alpha V_L + \beta G_L + \gamma F_L - \lambda T_L - \mu C_L - \nu P_L\Big]$$

| term | meaning |
|------|---------|
| $A_L$ | answer accuracy |
| $V_L$ | verified-solution rate |
| $G_L$ | generalisation |
| $F_L$ | semantic fidelity |
| $T_L$ | token use |
| $C_L$ | compute and latency |
| $P_L$ | parse or generation failure |

**The language is not sacred.** Its syntax, and potentially its semantic organisation,
survive only where they improve measured performance.

## 4. The one-sentence claim

**Do not say:** *"We invented the first mathematical language for AI."* That is false.

**Say:**

> Hamiltonian Lang is a cross-domain, typed mathematical intermediate representation and
> verifier-guided reasoning protocol whose syntax, semantic organisation and concept system
> are treated as experimentally optimisable variables, tested under matched conditions
> against natural language, conventional notation and existing formal systems.

## 5. The three hypotheses, kept apart

The pilot conflated these. They can come apart — a representation might be a poor *input*
format and a good *reasoning* format, or worthless without a verifier and valuable with one.

| id | hypothesis | isolated by |
|----|-----------|-------------|
| **H1** | representation as **input** improves the answer | vary the input, fix the output format |
| **H2** | representation as **reasoning workspace** improves the answer | English input, Hamiltonian derivation *required* |
| **H3** | **verifier-guided repair** improves the verified answer | same input and derivation, feedback added |

A win on H3 alone is a win for verifier-guided reasoning and **must not** be reported as a
win for the representation.

## 6. The result that would matter

> Using the same base model, mathematical information and compute budget, Hamiltonian
> reasoning increased paired answer accuracy by **X** points, increased kernel-verified
> completion by **Y** points, reduced structural errors by **Z%**, and transferred better to
> unseen formally defined concepts than structured English, LaTeX and direct formal-language
> interaction.

That is materially different from "we also trained an AI to write Lean." It would show that
**representation design is itself a controllable capability lever.**

**No such result exists.** X, Y and Z are unmeasured.

## 7. Honest status

| | |
|---|---|
| compiler, semantic core, epistemics, reasoning state | built, tested, conformance-clean |
| preregistration, benchmark harness, blinded audit, freeze protocol | built |
| concept registry | built but **gameable**; fails its own criterion |
| **H1 / H2 / H3** | **untested** |
| **𝒪, the novelty candidate** | **untested** |

The HML-EVAL-001 pilot found no advantage, and that finding is **not a refutation**: 14 of
15 problems were solved by nearly every arm and the minimum detectable effect was ~33
percentage points. The precise conclusion is:

> Zero-shot Hamiltonian did not improve answer accuracy on this small, low-discrimination
> pilot. The experiment was underpowered and had a severe ceiling effect.

**Status of the thesis: UNPROVEN, NOT REFUTED.**

## 8. The immediate bottleneck

**Can `gemma4:31b` acquire one Hamiltonian surface at ≥95% repaired parse success and ≥90%
semantic fidelity?**

V0 achieved 50–73%. Until a surface clears the gate, every null result is uninterpretable —
a language the model cannot reliably write is not being tested. **Only after that does the
novelty experiment begin.**

## 9. How this project can fail

1. No improvement over matched baselines on adequately powered comparisons.
2. Improvement that vanishes once tokens and compute are equalised.
3. Improvement attributable to **scaffolding** — structured English closes the gap.
4. Translation loss: round-tripping through the core changes meaning.
5. Accurate but too expensive to produce.
6. **Distribution, not representation.** Baselines are saturated in pretraining; Hamiltonian
   has effectively zero tokens. A win must survive the objection that a purpose-built format
   merely constrains the output space.
7. **Format restriction may hurt.** Tam et al. (EMNLP 2024) report reasoning degradation
   under format constraints — published evidence pointing the other way.
8. The model cannot reliably write the language at all — currently the live risk.

Failure on well-posed questions will be reported, not buried. A negative result obtained
honestly is a contribution; a positive one obtained by moving goalposts is not.
