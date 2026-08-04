# GOAL — Hamiltonian Lang

**A mathematical language designed for machine cognition, not human conversation.**

---

## 1. The Crux

Natural language was optimised for human communication. Mathematical notation was optimised
for human blackboards and printed pages. Programming languages were optimised for human
authorship of deterministic instructions. **None of them were designed as the internal
substrate in which a machine reasons about mathematics.**

Each of them leaves critical structure implicit — variable roles, assumptions, domains,
units, constraints, dependencies, uncertainty, equivalence classes, and proof obligations.
An AI system operating through these media must *re-infer* that structure, probabilistically,
every single time it reads a problem. Every re-inference is an opportunity for error.

Hamiltonian Lang is an investigation into a single hypothesis:

> **If mathematical structure is represented explicitly, compositionally, and machine-natively,
> then the same AI system — given the same problem and comparable compute — will reason more
> accurately and more verifiably than it does through prose, LaTeX, or conventional code.**

That is the entire project. Everything below is engineering in service of testing it.

---

## 2. The Worked Example

Consider the ordinary sentence:

> "$X$ follows a normal distribution with mean $\mu$ and standard deviation $\sigma$."

To a human this is one fact. To a machine it is at least six distinct semantic commitments,
none of which are written down:

| # | Implicit commitment |
|---|---------------------|
| 1 | $X$ is a **random variable**, not a constant or a free symbol |
| 2 | Its outcome domain is **real-valued** ($\mathbb{R}$) |
| 3 | Its probability law belongs to the **normal family** |
| 4 | $\mu$ occupies the **location / mean** role |
| 5 | $\sigma$ occupies the **scale / standard-deviation** role (not variance) |
| 6 | $\sigma > 0$ is a **required constraint**, silently assumed |

The AI must recover all six from surface text. Hamiltonian Lang's claim is that these should
be *stated*, once, in a form that is persistent, searchable, executable, and checkable — and
that the cost of stating them is repaid many times over in reasoning reliability.

**The unit of value is not shorter notation. It is eliminated inference.**

---

## 3. What Must Be Representable

A representation earns the name only if it can carry the whole problem. Hamiltonian Lang must
encode:

- mathematical objects and their **types**
- variables, constants, parameters, and observations
- domains, ranges, dimensions, and **units**
- assumptions and boundary conditions
- constraints and optimisation objectives
- functions, relations, transformations, and invariants
- probability distributions and uncertainty
- dependencies and conditional relationships
- equations, models, conjectures, and theorems
- intermediate deductions and **proof obligations**
- symbolic, numerical, probabilistic, and logical operations
- the formal definition of **new** mathematical concepts

---

## 4. The Four Governing Principles

$$
\boxed{
\begin{aligned}
&\textbf{1.}\ \ \text{Every object has a type.}\\
&\textbf{2.}\ \ \text{Every relation has defined semantics.}\\
&\textbf{3.}\ \ \text{Every inference has traceable dependencies.}\\
&\textbf{4.}\ \ \text{Every new concept has a formal definition.}
\end{aligned}
}
$$

These are not stylistic preferences. They are the invariants the implementation must enforce.
A construct that violates one of them does not belong in the language.

**Corollary on new terminology:** new mathematical terms may be introduced, but a term cannot
survive because it *sounds* plausible. Every new concept must carry a precise mathematical
identity — type, domain, definition, constraints, relationships, invariants, and **testable
consequences**. Plausibility is not admissible evidence.

---

## 5. The Three-Layer Architecture

Hamiltonian Lang is deliberately stratified. Conflating these layers is the failure mode of
most notation projects.

```
┌──────────────────────────────────────────────────────────────┐
│  LAYER 1 — SURFACE                                           │
│  Compact linear syntax. Cheap for an AI to emit and parse.   │
│  Token-efficient. Not intended to be beautiful on paper.     │
└──────────────────────────────────────────────────────────────┘
                              ↕  (bijective, meaning-preserving)
┌──────────────────────────────────────────────────────────────┐
│  LAYER 2 — SEMANTIC CORE                    ◄── the apparatus │
│  Typed structured representation: objects, roles, constraints,│
│  dependencies, transformations. The single source of          │
│  mathematical truth. Everything else is a projection.         │
└──────────────────────────────────────────────────────────────┘
                              ↕  (lowering / compilation)
┌──────────────────────────────────────────────────────────────┐
│  LAYER 3 — BACKENDS                                          │
│  formal verification · symbolic computation · probabilistic  │
│  inference · numerical execution · constraint solving ·      │
│  dimensional analysis                                        │
└──────────────────────────────────────────────────────────────┘
```

The pipeline:

$$
\text{Mathematical problem}
\;\rightarrow\;
\text{Hamiltonian representation}
\;\rightarrow\;
\begin{cases}
\text{formal verification}\\
\text{symbolic computation}\\
\text{probabilistic inference}\\
\text{numerical execution}\\
\text{constraint solving}
\end{cases}
$$

**One object, many equivalent views.** A single Hamiltonian object may be rendered as compact
linear syntax, as conventional mathematical notation, as a semantic graph, as an executable
statistical model, as a numerical program, or as a formal statement submitted to a proof
assistant — *without changing what it means*.

> **Amendment (post prior-art review, `DECISIONS.md` D-011, D-012).** This section
> originally called Layer 2 "the actual contribution" and listed provenance among the
> things it records. Both claims were wrong and are corrected above.
>
> **Provenance is not implemented.** The IR carries source spans and types. The semantic
> graph carries dependency edges, which is not a derivation record.
>
> **The three-layer architecture is not novel.** Rocq's documentation describes
> surface-to-kernel translation as *the de Bruijn criterion*, a named principle; Lean 4's
> elaborator is the same architecture; OpenMath Content Dictionaries already mandate
> formal-property and example fields; Content MathML has carried `domainofapplication`
> and `condition` since 1998; MMT/OAF has already exported Isabelle, the AFP and the Coq
> library as theory graphs. See `docs/research/PRIOR_ART.md`.
>
> The defensible contribution is **§8, the experiment** — not the representation.

### Positioning

Hamiltonian Lang sits **above** proof assistants, probabilistic programming languages,
computer algebra systems, and numerical environments. It does not attempt to reimplement
their solvers or libraries, and it does not claim one printed syntax should replace every
existing tool. It asks a narrower, harder question: **can one shared semantic representation
address all of these systems coherently, without losing meaning in translation?**

---

## 6. Semantic Compositionality

The central design principle:

> **The structure of a mathematical expression should reflect the structure of the concept it
> represents.**

Related concepts belong to explicit **concept families**. Objects, properties, predicates,
transformations, inverse transformations, estimators, distributions, proofs, and
counterexamples must not exist as isolated vocabulary items with arbitrary names. Their formal
relationships are encoded *in the language itself*, the way morphology encodes relationships
in human languages — but with mathematical rather than phonological regularity.

If knowing one member of a family does not help you derive its siblings, the design has failed.

---

## 7. The Language as an Optimisation Problem

Hamiltonian Lang does not assume a human-designed grammar is optimal. Multiple candidate
representations can be generated and evaluated empirically:

$$
L^{*} = \arg\max_{L}\Big[
\underbrace{\text{accuracy} + \text{generalisation} + \text{verification} + \text{semantic compression}}_{\text{maximise}}
\;-\;
\underbrace{\text{ambiguity} + \text{computational cost}}_{\text{minimise}}
\Big]
$$

Measured criteria:

- mathematical-answer accuracy
- formally verified completion rate
- variable-binding reliability
- quantifier and scope accuracy
- generalisation to unfamiliar problems
- semantic-equivalence preservation
- error visibility (do mistakes become *loud* rather than silent?)
- token efficiency
- inference cost
- cross-domain structure transfer

**AI systems do not merely *use* Hamiltonian Lang — they participate in refining it**, by
proposing candidate representations, testing them on controlled tasks, and retaining the
structures that measurably improve reasoning and verification.

---

## 8. Falsifiability — How This Project Can Fail

This is the section that matters most. A representation project without a falsification
condition is aesthetics.

**The central experiment.** Take the same AI system, the same mathematical problems, and
comparable compute. Run it through:

| Arm | Representation |
|-----|----------------|
| A | Ordinary mathematical prose |
| B | LaTeX |
| C | Conventional code (Python / etc.) |
| D | Direct interaction with an existing formal language |
| E | **Hamiltonian Lang** |

Compare using deterministic compilers, solvers, and verification systems wherever possible —
so that scoring does not itself depend on a language model's judgement.

**Success condition:** arm E measurably beats arms A–D on the criteria in §7.

**Failure conditions — any of these falsifies the thesis:**

1. No measurable improvement over the baselines on matched problems.
2. Improvement that disappears once token/compute budgets are equalised.
3. Improvement attributable to the *scaffolding* (structured prompting, explicit checklists)
   rather than to the representation — i.e. a plain-prose arm given the same structural
   prompting closes the gap.
4. Translation loss: round-tripping through the semantic core changes the meaning.
5. The representation is accurate but so expensive to produce that it is unusable in practice.
6. **Distribution, not representation.** Arms A–D are saturated in model pretraining; arm E
   has effectively zero tokens in it. If arm E loses, the cause may be unfamiliarity rather
   than any property of the representation — and if arm E *wins*, the result must survive
   the objection that a purpose-built format merely constrains the output space. This is
   the hardest confound in the design and it was missing from the first draft of this list.
7. **Format restriction may hurt reasoning outright.** Tam et al. (EMNLP 2024) report
   measurable degradation in LLM reasoning under format constraints. That is published
   evidence pointing against the thesis, and it belongs here as a preregistered alternative
   hypothesis rather than as a surprise.

**These outcomes will be reported, not buried.** A negative result on a well-posed question is
a real contribution; a positive result obtained by moving the goalposts is not.

---

## 9. Initial Scope

Deliberately narrow and structurally demanding. Early work targets domains where implicit
structure is known to cause failures:

- probability and statistical models
- variable binding
- nested assumptions
- conditional dependence
- dimensional consistency
- algebraic transformations
- formally checkable conclusions

Breadth is earned by results, not asserted at the start.

---

## 10. Long-Term Vision

An extensible mathematical operating layer, with specialised modules for pure mathematics,
statistics, physics, optimisation, scientific computing, engineering, quantitative finance,
chemistry, and other disciplines that depend on precise formal models. Each field keeps its
native concepts and execution engines while sharing one semantic foundation.

The goal is mathematical reasoning that is **less ambiguous, more structurally explicit, more
compositional, more computationally efficient, more interoperable, more auditable, more
reliably verifiable, and more capable of supporting artificial mathematical discovery.**

---

## 11. Intellectual Lineage

Hamiltonian Lang draws on — without being reducible to — formal mathematical logic, dependent
type systems, proof assistants, controlled natural languages, symbolic computation,
probabilistic programming, semantic knowledge representation, compiler intermediate
representations, graph-based knowledge systems, and the morphological organisation found in
human languages.

What differs is the **optimisation target**. Those traditions largely optimise for human
rigour, human ergonomics, or machine execution of already-formalised content. Hamiltonian Lang
optimises for one thing: *increasing the mathematical capability of artificial intelligence by
improving the representation in which its reasoning occurs.*

---

## 12. Governing Thesis

> **Natural language should not be assumed to be the optimal internal substrate for machine
> mathematics. Mathematical structure should be represented in a language designed
> specifically for mathematical cognition.**

Hamiltonian Lang is neither merely a new notation nor merely a compiler. It is an attempt to
engineer the representational substrate through which AI systems understand, manipulate,
verify, and advance mathematics.

---

## 13. What "Done" Looks Like for v0

The first milestone is not a language. It is an **experiment that can return a verdict.**

1. A semantic core (Layer 2) capable of representing the §9 domains.
2. A surface syntax (Layer 1) with a parser and a printer that round-trip losslessly.
3. At least two backends (Layer 3) — one verification, one probabilistic or numerical.
4. A benchmark set of problems from §9, authored in all five arms of §8.
5. Deterministic scoring harness.
6. A results document reporting the outcome **honestly**, including negative results.

Until item 6 exists, the thesis is untested and should be described as such.
