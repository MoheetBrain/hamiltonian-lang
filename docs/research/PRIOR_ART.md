# Prior Art Analysis — Hamiltonian Lang

Author role: Prior-Art Investigator (Wave 1 research)
Date of investigation: 2026-08-04
Subject of audit: `GOAL.md` and `docs/design/V0_DESIGN_FREEZE.md`, against the implemented
kernel in `src/hamiltonian_lang/types.py` and `src/hamiltonian_lang/ast/nodes.py`.

---

## 0. Method and evidence conventions

Every substantive statement below is tagged:

- **[E]** EVIDENCE — verified this session against a primary source (spec text, licence file,
  repository, or a file in this repository). A citation is given.
- **[I]** INFERENCE — my judgement, reasoning over the evidence. Not independently sourced.
- **[U]** UNVERIFIED — I believe this but did not confirm it this session. Treat as a to-do,
  not as a fact.

Licence statements were checked against canonical `LICENSE` files or official terms pages
where reachable. **Nothing here is legal advice.** Licence compatibility for a private
commercial product must be confirmed by a lawyer before any code is vendored.

Systems examined: Lean 4, mathlib4, Rocq/Coq, Isabelle/HOL, Mizar, Metamath, Dedukti /
Logipedia, OpenMath 2.0, Content MathML 3 (incl. Strict), OMDoc, MMT/UniFormal, SMT-LIB 2.6,
Z3, Stan, PyMC, NumPyro, Turing.jl, SciPy `stats`, ProbOnto, SymPy, Wolfram Language, MLIR,
Naproche/ForTheL, Attempto Controlled English, Lojban, AlphaGeometry's geometry DSL,
MathScheme/Chiron, F# units-of-measure, Unitful.jl, sTeX, Alectryon, Theorema, and the
formalisation formats used by miniF2F / ProofNet.

---

## 1. Executive verdict

**Read this paragraph before anything else in the repository.**

Essentially every *representational* idea in `GOAL.md` and `V0_DESIGN_FREEZE.md` already exists,
implemented and published, usually more than once, usually decades ago. The three-layer
architecture is the standard architecture of every modern proof assistant. The "one shared
semantic representation connecting many mathematical systems" is the explicit, stated,
funded mission of OpenMath, OMDoc, MMT and Dedukti/Logipedia. Presentation/content separation
is the founding premise of MathML. Role-labelled distribution parameters are ordinary practice
in PyMC and SciPy and are formally catalogued in ProbOnto. Rational-exponent dimension vectors
are Kennedy's units-of-measure and Unitful.jl. Alpha-invariant canonical forms are de Bruijn
(1972). Requiring every minted concept to carry formal properties and examples is the OpenMath
Content Dictionary `FMP`/`Example` structure.

The honest position is: **Hamiltonian Lang's Layer 2 contains no structurally new
representational construct that I could identify.** What is potentially new is narrow: (a) the
*combination* in one small artefact, (b) a handful of hard prohibitions where prior systems
offer conventions, and (c) most defensibly, the *optimisation target and the experiment* —
designing and then empirically measuring a representation against matched arms for LLM
generation reliability. Even (c) is weaker than it looks, and §6 explains why.

This is not a reason to stop. It is a reason to stop describing the project as a
representational contribution and start describing it as an empirical one.

---

## 2. The layer map of the field

`GOAL.md` §5 defines three layers. Here is where each surveyed system actually sits. [E] for
layer placement follows from the cited specs in §3.

| Layer | Systems that occupy it |
|---|---|
| L1 surface syntax | Gallina, Isar, Lean 4 `Syntax`, ForTheL, ACE, Lojban, sTeX, Presentation MathML, Stan's `.stan`, Wolfram's input form, AlphaGeometry's problem strings |
| L2 semantic representation | Lean `Expr`, Rocq kernel CIC terms, Isabelle/Pure terms, OpenMath objects, Strict Content MathML, OMDoc, MMT, Dedukti λΠ-modulo, MLIR, SMT-LIB terms, ProbOnto OWL |
| L3 execution / verification | Lean & Rocq & Isabelle kernels, Z3, Stan/CmdStan, PyMC/NumPyro/Turing, SymPy, Wolfram Engine, AlphaGeometry DD+AR |

Hamiltonian Lang's stated position — "above proof assistants, PPLs, CAS, and numerical
environments" — is precisely the position OpenMath/OMDoc/MMT already occupy, and the position
Dedukti occupies for proofs specifically. [I]

---

## 3. System-by-system findings

### 3.A Proof assistants and their libraries

#### Lean 4 (+ mathlib4)

- **Layer:** L1 + L2 + L3, cleanly separated. [E] The Lean 4 metaprogramming book states that
  parsing produces a `Syntax` object and that "the elaborator is the component in charge of
  turning the user facing `Syntax` into something with which the rest of the compiler can
  work, most of the time translating `Syntax` into `Expr`s"
  (<https://leanprover-community.github.io/lean4-metaprogramming-book/main/07_elaboration.html>).
  `Expr` is described as "an abstract syntax tree for Lean programs"
  (<https://leanprover-community.github.io/lean4-metaprogramming-book/main/03_expressions.html>).
- **Typed semantic core separable from surface syntax:** Yes, exactly and by design. **This is
  the single most direct hit against the novelty of `GOAL.md` §5.** [E]
- **Binding & scope:** de Bruijn indices in `Expr`; macro hygiene tracked at the `Syntax`
  level. [E] (hygiene: metaprogramming book, macros chapter). Alpha-equivalence is definitional.
- **Quantifiers:** dependent function types (`∀` is `Pi`); scope is structural. [E]
- **Argument labelling:** named and optional arguments, implicit/instance-implicit binders,
  structure field names, anonymous constructor notation. Named arguments exist and are
  optional, not mandatory. [E via Lean docs] [I on "not mandatory"]
- **Refinement types:** subtypes (`Subtype`, `{x : α // p x}`) are first-class and *dependent*,
  which is strictly more expressive than HML's fixed scalar poset. [I]
- **Dimensions/units:** no built-in dimensional system in core or mathlib. [U — I did not find
  one; absence not proven.]
- **Probability laws first-class:** yes, via `MeasureTheory.Measure`, `PMF`, `ProbabilityTheory`
  in mathlib; random variables are measurable functions, formally distinct from their laws. [U
  on the exact namespaces; the measure-theoretic development in mathlib is well known but I did
  not open the files this session.]
- **Provenance:** proof terms *are* the dependency trace; every declaration is checked against
  its dependencies by the kernel. [I]
- **Target author:** human, with heavy recent machine-generation use (autoformalization,
  DeepSeek-Prover, etc.). [E — Wu et al. 2022, <https://arxiv.org/abs/2205.12615>]
- **Licence:** Lean 4 — **Apache License 2.0** [E,
  <https://raw.githubusercontent.com/leanprover/lean4/master/LICENSE>]. mathlib4 — **Apache
  License 2.0** [E,
  <https://raw.githubusercontent.com/leanprover-community/mathlib4/master/LICENSE>].
- **Reusable in a private commercial project:** Yes. Apache-2.0 permits commercial and private
  use with notice/attribution obligations and an express patent grant. [E on licence identity;
  [I] on the practical conclusion; not legal advice.]
- **Reuse rather than rebuild:** the `Syntax → Expr` elaborator architecture as a design
  template; Lean as the v0 verification backend target; mathlib as a source of *statement*
  vocabulary.
- **Beats v0 at:** everything in the type system. Dependent types, universes, typeclass
  inference, real subtypes, and a kernel that actually checks proofs. HML v0 explicitly ships
  `sorry` skeletons (`V0_DESIGN_FREEZE.md` §8).

#### Rocq (formerly Coq)

- **Layer:** L1 (Gallina) + L2 (CIC kernel terms) + L3 (kernel checker). [E]
- **Typed semantic core separable from surface syntax:** Yes, and the documentation makes the
  separation an explicit architectural principle: notations, implicit arguments and tactics are
  "translated into the core language (the Calculus of Inductive Constructions) that the kernel
  understands", and "this separation between the kernel on one hand and the elaboration engine
  and tactics on the other follows what is known as the de Bruijn criterion"
  [E, <https://rocq-prover.org/doc/master/refman/language/core/index.html>].
  **The de Bruijn criterion is the named, 50-year-old principle that `GOAL.md` §5 restates
  without attribution.** [I]
- **Licence:** **LGPL 2.1 only** — the `LICENSE` file is the LGPL 2.1 text of February 1999
  with no "or later" clause [E,
  <https://raw.githubusercontent.com/rocq-prover/rocq/master/LICENSE>].
- **Reusable in a private commercial project:** Invoking `rocqc`/`coqc` as a separate process
  does not create a derivative work and is safe. Vendoring or linking Rocq source into a
  proprietary binary triggers LGPL obligations. [I — not legal advice.] Prefer subprocess
  invocation only.
- **Beats v0 at:** proof checking, a mature tactic language, extraction to OCaml/Haskell.

#### Isabelle/HOL

- **Layer:** L1 (Isar) + L2 (Pure/HOL terms) + L3 (LCF-style kernel). [I]
- **Typed semantic core:** Yes — simply-typed λ-calculus (Pure) with type classes; not
  dependent. [U on the precise formulation this session.]
- **Licence:** **BSD 3-Clause ("revised BSD")**; the distribution `COPYRIGHT` names the
  University of Cambridge and Technische Universität München [E,
  <https://raw.githubusercontent.com/isabelle-prover/mirror-isabelle/master/COPYRIGHT>]. The
  full distribution bundles add-on tools under other licences including GPL/LGPL [U — widely
  stated; check per-component before vendoring].
- **Reusable in a private commercial project:** the core, yes; bundled components must be
  audited individually. [I]
- **Beats v0 at:** structured human-readable proof (Isar), sledgehammer-style automation,
  and — via Naproche — an actual working controlled-natural-language front end.

#### Mizar

- **Layer:** L1 (Mizar language, deliberately close to mathematical vernacular) + L2/L3.
- **Licence:** Mizar system — **GPL v3 or later**; the Mizar Mathematical Library is
  **dual-licensed GPL and CC-BY-SA** (GPL treating MML as code, CC-BY-SA treating it as text)
  [E via search of `MizarProject/system` and `JUrban/MMLLicense`; see
  <https://github.com/MizarProject/system> and <https://github.com/JUrban/MMLLicense>. Flagged
  [U] on the exact GPL version pinned in the current release — I did not open the LICENSE file
  itself.]
- **Reusable in a private commercial project:** Not for embedding. GPL-3 copyleft. Subprocess
  use is the only defensible pattern, and even that requires care. [I]
- **Beats v0 at:** a soft type system with *attributes* and *adjectives* (`non empty`,
  `finite`) that behave much like the refinement lattice HML is attempting, but with automatic
  registration and inference. [U on mechanism details — worth a dedicated follow-up, because
  Mizar's adjective/cluster mechanism is arguably a better answer to HML's `Probability` vs
  `PositiveReal` poset problem than a hand-maintained parent table.]

#### Metamath

- **Layer:** L2 (a substitution-and-proof-step format with essentially no type theory) + L3.
- **Licence:** the `metamath` program is **GPL v2 or later**; the `set.mm` database is released
  under **CC0** (public domain dedication) [E via
  <https://directory.fsf.org/wiki/Metamath> and the Metamath project statements; flagged [U] on
  the exact current LICENSE file, which I could not fetch at the canonical path].
- **Reusable in a private commercial project:** `set.mm` yes (CC0). The verifier binary: GPL,
  but third-party MIT/BSD verifiers exist [U].
- **Beats v0 at:** verifier simplicity. A conforming Metamath verifier is a few hundred lines.
  Nothing in HML v0 is remotely as auditable.

#### Dedukti / Logipedia

- **Layer:** L2 — λΠ-calculus modulo rewriting, explicitly designed as an *interchange* logical
  framework into which Coq, HOL Light, Matita, Zenon, iProver, FoCaLiZe proofs are encoded.
  Logipedia is "a multi-system online encyclopedia of formal proofs expressed in a standard
  language" [E via <https://github.com/Deducteam/Dedukti> and
  <https://arxiv.org/pdf/2305.00064>].
- **Licence:** **CeCILL-B** (a French BSD-like permissive licence) [E via the Dedukti
  repository].
- **Why this matters to us:** Dedukti/Logipedia is a direct, funded, published instance of
  "one shared semantic representation that addresses multiple formal systems coherently,
  without losing meaning in translation" — the exact question `GOAL.md` §5 poses as "narrower,
  harder". They have been answering it since ~2012. [I]

### 3.B Semantic interchange formats — the hardest hits

#### OpenMath 2.0

This is the system that most directly overlaps the stated contribution.

- **Layer:** L2, purely. OpenMath is a semantic representation with several encodings; the
  encoding is not the object.
- **Object model** [E, OpenMath 2.0 standard,
  <https://openmath.org/standard/om20-2019-07-01/omstd20.html>]:
  - **Binding objects** — §2.1.3(iv) defines `binding(B, v1..vn, C)`; XML encoding `OMBIND`
    with `OMBVAR` (§3.1.2). So binding and quantifier scope are first-class and structural,
    exactly as in HML's `Quantifier` node.
  - **Attributions** — §2.1.3(iii) defines `attribution(A, S1 A1, …, Sn An)`, encoded `OMATTR`.
    Attributions are the generic mechanism for attaching *keyed* metadata to any object, and
    §2.2 shows `attribution(A, type t)` used as a type judgement.
  - **Symbols** — §2.1.1(v): a symbol carries a name, a Content Dictionary name, and optionally
    a CD base URI. Meaning is externalised into CDs, i.e. every symbol is a resolvable
    reference to a definition.
  - **Symbol roles** — §2.1.4 defines roles (`binder`, `attribution`, `semantic-attribution`,
    `error`, `application`, `constant`) restricting how a symbol may be used structurally.
- **Typed semantic core:** OpenMath is deliberately type-agnostic at the core, with types
  layered on via CDs. A **Small Type System (STS)** exists to give signatures to OpenMath
  symbols, published as signature dictionaries at <https://openmath.org/sts/> [E via
  <https://openmath.org/cd/sts.html> and Davenport, "A Small OpenMath Type System",
  <https://people.bath.ac.uk/masjhd/OpenMath/sts2.pdf>].
- **Role-labelled arguments:** application is positional (`OMA`); there is **no keyword-argument
  form** in the core object model [E, §2.1.3]. Role labelling must be simulated with `OMATTR`
  or with CD conventions. **This is the one place where HML's D-003 is genuinely not directly
  supported by OpenMath.** [I]
- **Dimensions and units:** the CD groups `dimensions1`, `units_metric1`, `units_imperial1`,
  `units_us1`, `units_time1`, `units_siprefix1`, `units_ops1`, `physical_consts1` exist [E,
  <https://openmath.org/cdgroups/units>, <https://openmath.org/cd/units_metric1.html>; and
  Davenport & Naylor, "Units and Dimensions in OpenMath",
  <https://openmath.org/documents/Units.pdf>].
- **Probability:** statistics CDs exist [U on which distributions and how parameterised].
- **Content Dictionary structure — direct hit on `GOAL.md` §4's "corollary on new terminology":**
  a `CDDefinition` contains `Name`, `Description`, **`CMP`** (Commented Mathematical Property),
  **`FMP`** (Formal Mathematical Property) and **`Example`** [E, OpenMath 2.0 §4.3.2,
  <https://openmath.org/standard/om20-2004-06-30/omstd20html-4.xml>]. HML's `ConceptDecl`
  rule — "a concept that declares no invariant and no example is rejected"
  (`src/hamiltonian_lang/ast/nodes.py`, `ConceptDecl` docstring) — is the OpenMath
  `FMP` + `Example` requirement, restated and made mandatory.
- **Target author:** machine exchange between mathematical software systems (its founding
  purpose), authored by humans writing CDs. [I]
- **Licence / IPR:** **UNVERIFIED.** The OpenMath Society coordinates the standard from
  Helsinki [E, <https://openmath.org/about/>] but I could not find an explicit licence or IPR
  statement on the site. Do not assume the CDs are freely reusable until this is confirmed. [U]

#### Content MathML 3 (and Strict Content MathML)

- **Layer:** L2 (Content) alongside L1 (Presentation) in the same standard. Presentation/content
  separation is the founding premise of MathML, published by W3C.
- **Constructs** [E, W3C MathML 3 Chapter 4, <https://www.w3.org/TR/MathML3/chapter4.html>]:
  `cn`, `ci`, `csymbol`, `cs` (§4.2); `apply` and `bind` with `bvar` for bound variables
  (§4.2.6); qualifiers `domainofapplication`, `condition`, `lowlimit`, `uplimit`, `interval`,
  `degree`, `momentabout`, `logbase` (§4.3.3); `type` attributes on `ci` mapping to the
  `mathmltypes` Content Dictionary (§4.2.2.1); `csymbol/@cd` referencing OpenMath CDs (§4.1.4);
  `semantics`/`annotation`/`annotation-xml` (§4.2.8).
- **Strict Content MathML** is "an XML encoding of OpenMath Objects", with an element-by-element
  mapping `cn↔OMI/OMF`, `csymbol↔OMS`, `ci↔OMV`, `cs↔OMSTR`, `apply↔OMA`, `bind↔OMBIND`
  [E, §4.1.3].
- **Named/role-labelled arguments:** no keyword arguments; roles are carried by operator
  position and by qualifier elements [E, §4.3.3].
- **Address this head-on:** the `condition` and `domainofapplication` qualifiers are a
  *content-level* mechanism for exactly the "domains, ranges, restrictions" that `GOAL.md` §3
  lists as things "left implicit" by existing notation. They are not left implicit by MathML;
  they have had dedicated elements since 1998. [I]
- **Licence:** W3C specification, W3C Document Licence [U — not verified this session]. The
  *format* is a standard, not code; implementing a MathML emitter creates no licence
  obligation. [I]

#### OMDoc

- **Layer:** L2, extended above the formula level. OMDoc conceptualises mathematics at three
  levels — **object** (formulae), **statement** (definitions, theorems, proofs), and **theory**
  (collections of statements) — explicitly going beyond MathML (formulae only) and OpenMath
  (formulae + CDs) to cover "the whole range of written mathematics" [E via
  <https://en.wikipedia.org/wiki/OMDoc> and <https://www.omdoc.org/OMDoc1.6/>; also the OMDoc
  1.2 book, Kohlhase, Springer LNAI 4180].
- **Directly overlaps** HML's statement inventory (`V0_DESIGN_FREEZE.md` §3): `assume`,
  `require`, `prove`, `def`, `concept` are the OMDoc statement level, with two decades of
  prior design. [I]
- **Provenance:** OMDoc carries Dublin-Core-style metadata [U — asserted in the literature; not
  verified section-by-section this session].
- **Licence:** **UNVERIFIED** for both the specification and reference tooling. [U]

#### MMT / UniFormal

- **Layer:** L2, meta-level. MMT is "a framework for representing declarative languages such as
  logics, type theories, set theories" that "achieves a high level of generality by
  systematically avoiding a commitment to a particular syntax or semantics", and which "does not
  build in any primitive features like function types or propositions" [E via
  <https://uniformal.github.io/> and <https://kwarc.info/systems/mmt/>].
- **Realised interoperability, not proposed:** the OAF (Open Archive of Formalizations) project
  exports Isabelle's distribution and the full Archive of Formal Proofs (12,000+ theories) into
  OMDoc/MMT via `isabelle mmt_import`, and has represented the Coq library as a theory graph and
  translated the IMPS library [E via <https://uniformal.github.io/doc/archives/oaf.html> and
  <https://arxiv.org/pdf/1905.07244>].
- **Concept families / morphology:** MMT's theory graphs, theory morphisms and "little theories"
  are the mature form of `GOAL.md` §6's "concept families" and "if knowing one member of a family
  does not help you derive its siblings, the design has failed". Views and morphisms *transport*
  results between families automatically. HML has `concept ... extends ...` and nothing else. [I]
- **Licence:** **BSD 3-Clause**, "Copyright (c) 2016-20, Florian Rabe and contributors"
  [E, <https://raw.githubusercontent.com/UniFormal/MMT/master/COPYING.txt>].
- **Reusable in a private commercial project:** Yes (BSD-3, attribution only). Written in Scala.
  [E on licence; [I] on conclusion.]
- **The most important sentence in this document:** Kohlhase and Rabe — the people who built
  OpenMath tooling, OMDoc and MMT — published a 2020 survey of languages for formalising
  mathematics whose stated conclusion is that **"no existing language is truly good enough yet"**
  [E, <https://arxiv.org/abs/2005.12876>]. That is simultaneously the strongest available
  external support for the *premise* of this project and the clearest proof that the premise is
  not original to it.

### 3.C Solver and compiler interfaces

#### SMT-LIB 2.6

Verified directly against the standard (Barrett, Fontaine, Tinelli, v2.6 r2021-05-12,
<https://smt-lib.org/papers/smt-lib-reference-v2.6-r2021-05-12.pdf>). All of the following are [E]
with section numbers:

- **Sorts (§3.5):** "each [term] is associated with a (unique) *sort*". Sorts may be parametric
  (`(List (Array Int Real))`). **Ranks (§3.5.1)** assign sorts to function symbols. There is
  **no subtyping and no refinement type** — well-sortedness (§3.6.4) is exact matching, and
  ambiguous symbols must be disambiguated with `(as f σ)`.
- **Binders (§3.6.1):** four binders — `let`, `forall`, `exists`, `match`. `(forall ((x1 σ1) …
  (xn σn)) φ)` is defined to have the same semantics as the nested form (eqns 3.1/3.2), so
  quantifier order is structural, and shadowing follows a lexical scoping discipline (§3.6.3,
  "Shadowing").
- **Annotations (§3.6.5):** `(! t α1 … αn)`. Crucially: "Term attributes have no logical
  meaning — semantically, `(! t α1 … αn)` is equivalent to `t` — but they are a convenient
  mechanism for adding meta-logical information for SMT solvers."
- **Attributes (§3.4):** keyword/value pairs, e.g. `:named`, `:pattern` (§3.6.6). So SMT-LIB has
  role-*labelled metadata* but not role-labelled *arguments*: function application (§3.6) is
  strictly positional.
- **Theory declarations (§3.7) and logic declarations (§3.8)** are the modularity mechanism.
- **Target author:** machine generation, overwhelmingly. SMT-LIB is a machine-to-machine
  interchange format whose human ergonomics were never the point. [I] This is a real precedent
  for HML's "designed to be emitted, not to be beautiful".
- **Note for the design freeze:** HML reserves `!` as a proof-obligation marker
  (`V0_DESIGN_FREEZE.md` §1). SMT-LIB already uses `!` as its annotation operator with an
  established, different meaning. A backend author will trip over this. [I]

#### Z3

- **Layer:** L3 solver, with SMT-LIB 2 as its L2 input.
- **Licence:** **MIT License**, "Copyright (c) Microsoft Corporation"
  [E, <https://raw.githubusercontent.com/Z3Prover/z3/master/LICENSE.txt>].
- **Reusable in a private commercial project:** Yes, without practical restriction beyond
  notice. [E on licence; [I] on conclusion.]
- **Reuse:** use it. Do not build a constraint solver.

#### MLIR (LLVM)

- **Layer:** L2, and the single best engineering precedent for a multi-target semantic core.
- **Structure:** dialects group operations, types and attributes; every SSA value has a type;
  each operation carries an **attribute dictionary mapping attribute *names* to values**
  [E, <https://mlir.llvm.org/docs/DefiningDialects/AttributesAndTypes.md> and
  <https://en.wikipedia.org/wiki/MLIR_(software)>].
- **Role-labelled arguments already exist here.** MLIR's named attribute dictionary is the
  general form of HML's `Arg(role, value)`. [I]
- **Licence:** **Apache 2.0 with LLVM exceptions** [E, LLVM project].
- **Reusable in a private commercial project:** Yes. [I]
- **Beats v0 at:** progressive lowering, verification of IR invariants, and a mature story for
  "one object, many backends" — the exact claim in `GOAL.md` §5.

### 3.D Probabilistic modelling — the domain HML picked as its wedge

#### Stan

- **Layer:** L1 + L2 + L3 (its own compiler and HMC sampler).
- **Constrained types:** `real<lower=0>` etc. The reference manual is explicit that these are
  *not* part of the underlying type: "Constraints are not part of the underlying data type for a
  variable, but determine error checking in the transformed data, transformed parameter, and
  generated quantities block", and "a bounded real may be assigned to an unconstrained real and
  vice-versa" [E, <https://mc-stan.org/docs/reference-manual/types.html>].
  **This is genuinely a point where HML v0 does something different**: HML's `Probability`,
  `PositiveReal`, `NonNegativeReal` are part of the type and participate in a subtype relation
  (`src/hamiltonian_lang/types.py`, `_SCALAR_PARENTS` and `is_subtype`). Whether that difference
  is an improvement or merely a different tradeoff is untested. [I]
- **Physical units:** none. "The documentation makes no mention of unit tracking, dimensional
  analysis, or any mechanism for specifying physical quantities" [E, same source].
- **Distribution arguments:** positional (`normal(mu, sigma)`). [U — the types page does not
  cover this; I did not verify against the functions reference.]
- **Licence:** **BSD 3-Clause**, "Copyright (c) 2011--2020, Stan Developers and their Assignees"
  [E, <https://raw.githubusercontent.com/stan-dev/stan/develop/LICENSE.md>].
- **Reusable in a private commercial project:** Yes. [I]

#### PyMC — the most damaging single finding for decision D-003

- `pymc.Normal` takes **named** parameters `mu`, `sigma`, `tau`, documents that "Normal
  distribution can be parameterized either in terms of precision or standard deviation" with
  τ = 1/σ², and requires the user to supply exactly one of `sigma` or `tau`
  [E, <https://www.pymc.io/projects/docs/en/stable/api/distributions/generated/pymc.Normal.html>].
- That is: **the exact ambiguity D-003 claims to eliminate is already eliminated, in a widely
  used production PPL, by exactly the same mechanism (named parameters keyed to roles), with the
  additional feature that alternative parameterisations are named distinctly rather than
  prohibited.**
- HML's delta over PyMC on this point is that labels are *mandatory* and positional form is a
  parse error. That is a policy hardening of an existing mechanism, not a new mechanism. [I]
- **Licence:** **Apache License 2.0** ("Copyright 2020 The PyMC Developers"), with MIT-licensed
  portions derived from AePPL/Aesara
  [E, <https://raw.githubusercontent.com/pymc-devs/pymc/main/LICENSE>].

#### SciPy `stats`

- `scipy.stats.norm` uses the keyword role names `loc` and `scale`: "The location (`loc`)
  keyword specifies the mean. The scale (`scale`) keyword specifies the standard deviation"
  [E, <https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.norm.html>].
- Role-labelled distribution parameters, in the most widely installed scientific Python library
  in existence. [I]

#### NumPyro / Turing.jl

- NumPyro — **Apache License 2.0**
  [E, <https://github.com/pyro-ppl/numpyro/blob/master/LICENSE.md>].
- Turing.jl — **MIT License**, "Copyright (c) 2016 The Turing Language"
  [E, <https://raw.githubusercontent.com/TuringLang/Turing.jl/master/LICENCE>].
- Both keep distributions as first-class objects distinct from samples (Julia's
  `Distributions.jl` types; NumPyro's `dist.Normal`). [I]
- Both reusable in a private commercial project. [I]

#### ProbOnto — the direct precedent for role-labelled distribution semantics

- An OWL ontology and knowledge base of **80+ univariate and multivariate distributions** with
  "their defining functions, characteristics, relationships and re-parameterization formulas",
  motivated explicitly by the fact that "in multiple cases, two or more parameterizations exist
  and it becomes essential to specify correctly the parameters"; it contains, for example,
  "six alternative parameterizations of the log-normal or five of the negative binomial"
  [E, Swat et al., *Bioinformatics* 32(17):2719,
  <https://academic.oup.com/bioinformatics/article/32/17/2719/2450721>].
- **Licence: CC-BY 4.0** [E,
  <https://raw.githubusercontent.com/probonto/ontology/master/LICENCE.md>].
- **Reusable in a private commercial project:** Yes, with attribution. CC-BY is a content licence
  and is a reasonable fit for an ontology. [I]
- **Reuse rather than rebuild:** HML should not hand-author its distribution family table with
  ad-hoc role names. It should adopt ProbOnto's parameter names and parameterisation identifiers
  and cite them, which both saves work and makes the role vocabulary defensible instead of
  invented. **This is the highest-value concrete reuse recommendation in this document.** [I]

### 3.E Computer algebra

#### SymPy

- **Licence:** **BSD 3-Clause**, "Copyright (c) 2006-2023 SymPy Development Team", with
  BSD-3 submodule copyrights and an MIT-licensed `latex2sympy` component
  [E, <https://raw.githubusercontent.com/sympy/sympy/master/LICENSE>].
- **Reusable in a private commercial project:** Yes. [I]
- **Reuse:** symbolic simplification, `sympy.physics.units` (which does dimensional analysis and
  unit conversion), and assumptions (`positive=True`, `real=True`) as an existing refinement
  mechanism. [U on the units module details this session.]

#### Wolfram Language

- **Distributions are first-class symbolic objects.** `NormalDistribution[μ,σ]` is a symbolic
  expression manipulable by `Expectation`, `Probability`, `TransformedDistribution`,
  `ProductDistribution`, `CopulaDistribution`, `PDF`, `CDF`, `Quantile`
  [E, <https://reference.wolfram.com/language/ref/NormalDistribution.html>]. Parameters are
  **positional** — one place where HML's choice differs. [E, same source.]
- **Units and dimensions.** `Quantity[magnitude, unit]` covers the NIST SP 811 unit set;
  `UnitDimensions` gives physical dimensions; `CompatibleUnitQ` tests dimensional compatibility;
  `UnitConvert` performs conversion; temperatures and temperature *differences* are separate
  units so that invalid arithmetic is blocked
  [E, <https://reference.wolfram.com/language/ref/Quantity.html>].
- **Beats v0 at dimensions outright.** `V0_DESIGN_FREEZE.md` §8 explicitly excludes unit
  conversion; Wolfram has done conversion, prefix handling and the temperature-difference
  subtlety for over a decade. [I]
- **Licence:** proprietary. The Free Wolfram Engine for Developers is "licensed for
  pre-production use in developing software and is not licensed for generating outputs for
  commercial or organizational use"
  [E, <https://www.wolfram.com/legal/terms/wolfram-engine.html> and
  <https://www.wolfram.com/engine/faq/>].
- **Reusable in a private commercial project: NO** under the free developer terms. A paid
  production licence would be required. Treat Wolfram as a *design reference*, never as a
  dependency. [I]

### 3.F Controlled natural languages and human-facing formalisation

#### Naproche / ForTheL

- ForTheL is a controlled natural language "designed to approximate the mathematical vernacular,
  while at the same time being a completely formal language"; Naproche is bundled with Isabelle
  and can also emit Lean code [E via <https://naproche.github.io/> and the Isabelle/Naproche
  papers].
- **Licence: GPL-3** [E, <https://github.com/naproche/naproche>].
- **Reusable in a private commercial project:** No embedding. Subprocess only, with care. [I]
- **Relevance:** ForTheL is the counter-thesis. It bets that *closeness to natural mathematical
  language* is the right substrate — the opposite of `GOAL.md` §12. If arm E loses to a prose or
  ForTheL-like arm, that is not a null result, it is a positive result for the other hypothesis,
  and the benchmark protocol should be able to detect it. [I]

#### Attempto Controlled English (ACE)

- "A precisely defined subset of English that can automatically and unambiguously be translated
  into first-order logic"; the APE parser produces Discourse Representation Structures
  [E via <https://attempto.ifi.uzh.ch/> and <https://github.com/Attempto/APE>].
- **Licence:** APE is **LGPL** [E via the Attempto project and AceWiki statements; [U] on the
  exact LGPL version].

#### Lojban — an uncomfortably close structural precedent

- Lojban predications (`bridi`) consist of a relation (`selbri`) with arguments (`sumti`), where
  **each root word's *place structure* fixes the semantic role of each argument position**, and
  place tags allow explicit role labelling; the grammar is machine-parsable and formalised in
  YACC/EBNF [E, The Complete Lojban Language, <https://lojban.github.io/cll/>].
- Compound words (`lujvo`) are built morphologically from root-word affixes (`rafsi`) so that
  related concepts have systematically related forms [E, same source].
- **This is `GOAL.md` §6 — "morphological regularity", "concept families", "knowing one member of
  a family should help you derive its siblings" — implemented in a designed language since
  1987.** HML should cite Lojban rather than gesture at "the morphological organisation found in
  human languages". [I]
- **Licence:** **UNVERIFIED.** The CLL reference grammar is © 1997 The Logical Language Group
  with a rights reservation notice; current LLG licensing (CC-BY-SA has been used for some
  materials) was not confirmed this session. The *language design* is not itself copyrightable
  and can be cited freely. [U]

#### sTeX, Alectryon, Theorema

- sTeX — semantic extension of LaTeX, **LPPL** (LaTeX Project Public License)
  [E via <https://ctan.org/pkg/stex> package documentation and <https://github.com/slatex/sTeX>].
  Occupies L1 and feeds OMDoc/MMT.
- Alectryon — mixes Rocq code and prose with recorded prover output; **MIT**
  [E via <https://github.com/cpitclaudel/alectryon>]. Relevant as a model for HML's
  "compiler feedback" arm (H4).
- Theorema — a Mathematica package for theorem proving and theory exploration, conceived by
  Buchberger [E via <https://github.com/windsteiger/Theorema>]. **Licence UNVERIFIED**, and in
  any case it requires a Mathematica licence, so it is not usable in a private commercial
  project. [I]

### 3.G AI-facing DSLs and benchmark formats

#### AlphaGeometry's geometry DSL

- Problems are stated as premises + constructions + conclusion in a compact, positional,
  machine-emitted string language (`a b = segment a b; d = on_tline d b a c … ? perp a d b c`),
  consumed by a DD (deductive database) + AR (algebraic reasoning) engine
  [E, <https://github.com/google-deepmind/alphageometry>].
- **Licence:** code **Apache 2.0**; checkpoints **CC BY 4.0** [E, same source].
- **Why this matters:** AlphaGeometry is an existence proof that a *purpose-built, compact,
  machine-emitted DSL plus a deterministic checker* produces state-of-the-art AI mathematical
  performance. It is the closest thing in the literature to HML's thesis being confirmed — for
  one narrow domain, with a domain-specific solver doing most of the work. It is also a warning:
  the win there is plausibly attributable to the *solver*, not the *notation*. [I]

#### miniF2F / ProofNet and the autoformalization literature

- miniF2F: 488 olympiad-level problems in multiple formal languages; ProofNet: 371
  undergraduate problems with paired natural and formal statements
  [E via <https://arxiv.org/abs/2205.12615> and the ProofNet paper].
- Wu et al. (NeurIPS 2022) showed LLMs translating competition problems into Isabelle/HOL and
  raised miniF2F proof rate from 29.6% to 35.2% [E, <https://arxiv.org/abs/2205.12615>].
- **These are the benchmark arms HML must beat.** Arm D of `GOAL.md` §8 ("direct interaction
  with an existing formal language") is a well-populated research area with strong baselines and
  published numbers. The benchmark protocol should reuse miniF2F/ProofNet problem sets rather
  than authoring fresh ones, or it will be unable to compare against anything. [I]

### 3.H Dimensions and units as a solved problem

- **F# units of measure** (Kennedy): units appear as type parameters (`float<kg>`) and are
  checked by the type checker; the checking is decidable and the algebra is on rational
  exponents [E, <https://learn.microsoft.com/en-us/dotnet/fsharp/language-reference/units-of-measure>
  and <https://fsharp.github.io/fslang-spec/units-of-measure/>; Kennedy, "Types for
  Units-of-Measure: Theory and Practice", 2010, and "Dimension Types", ESOP 1994].
- **Unitful.jl**: `Quantity{T<:Number, D, U}` where `D <: Dimensions` and `U <: Units`,
  separating dimension from unit so that quantities of the same dimension in different units
  can be combined [E, <https://painterqubits.github.io/Unitful.jl/v0.1/types/>]. **Licence
  UNVERIFIED** — the LICENSE path I tried 404'd. [U]
- **Wolfram `Quantity`** — see §3.E.
- **OpenMath units CDs** — see §3.A.
- **Verdict:** `V0_DESIGN_FREEZE.md` §6 and `types.py`'s `Dimension` class reproduce Kennedy's
  1994 dimension types with a seven-element SI basis and `Fraction` exponents. There is nothing
  new here, and three of the four listed systems already do the unit *conversion* that HML v0
  explicitly defers. [I]

### 3.I Theory organisation

- **MathScheme / Chiron** (Carette & Farmer, McMaster): a framework "in which formal deduction
  and symbolic computation are tightly integrated", built on **biform theories** — "a
  combination of an axiomatic theory and an algorithmic theory that supports the integration of
  reasoning and computation", organised as "a network of biform theories"
  [E, <https://arxiv.org/pdf/1805.02709> and <https://imps.mcmaster.ca/wmfarmer/publications.html>].
- This is `GOAL.md` §5's "one object, many equivalent views — proof assistant, CAS, numerical
  program" as a named research programme with two decades of publications. [I]

---

## 4. Claim-by-claim audit

Each row: a claim as stated in `GOAL.md` or `V0_DESIGN_FREEZE.md`, and the system(s) that
already do it. "Already done" means the capability exists in a shipped, documented system — not
that HML's particular encoding is identical.

| # | Claim (source) | Already done by | Status |
|---|---|---|---|
| 1 | Three layers: surface / semantic core / backends, with the core as single source of truth (`GOAL.md` §5) | Rocq (de Bruijn criterion, Gallina→CIC), Lean 4 (`Syntax`→`Expr`), MathML (Presentation/Content), OpenMath (object vs encoding), MLIR | **Already done** [E] |
| 2 | "One shared semantic representation addressing proof assistants, PPLs, CAS, numerics coherently" (`GOAL.md` §5) | OpenMath, OMDoc, MMT/OAF, Dedukti/Logipedia | **Already done, and it is their stated mission** [E] |
| 3 | Bijective, meaning-preserving surface↔core round-trip (`GOAL.md` §5) | Lean's delaborator/pretty-printer; MMT notations; Strict Content MathML↔OpenMath element mapping | **Already done** [E] |
| 4 | "Every object has a type" (`GOAL.md` §4.1) | Every typed proof assistant; SMT-LIB well-sortedness §3.6.4 | **Already done** [E] |
| 5 | "Every relation has defined semantics" (`GOAL.md` §4.2) | OpenMath Content Dictionaries, §4.3.2 `Description`/`CMP`/`FMP` | **Already done** [E] |
| 6 | "Every inference has traceable dependencies" (`GOAL.md` §4.3) | Proof terms in Lean/Rocq/Isabelle; Metamath proof steps | **Already done** [I] — and **not implemented in HML v0**, see §7 |
| 7 | "Every new concept has a formal definition" with invariants and examples required (`GOAL.md` §4 corollary; `nodes.py` `ConceptDecl`) | OpenMath CD `FMP` + `Example`, §4.3.2 | **Already done** [E] |
| 8 | Role-labelled distribution arguments eliminate `Normal(mu, sigma)` vs `Normal(mu, sigma^2)` (`V0_DESIGN_FREEZE.md` §2, D-003) | PyMC (`mu`/`sigma`/`tau`), SciPy (`loc`/`scale`), R named args, ProbOnto (6 log-normal parameterisations catalogued) | **Already done**; HML's delta is *mandatory* labels only [E] |
| 9 | Role-labelled arguments as a general IR mechanism (`nodes.py` `Arg`) | MLIR named attribute dictionaries; SMT-LIB attributes §3.4; OpenMath `OMATTR` §2.1.3(iii) | **Already done** [E] |
| 10 | `RandomVariable[T]` ≠ `Distribution[T]` ≠ `T` as distinct types (`V0_DESIGN_FREEZE.md` §4) | mathlib measure theory; Distributions.jl; Wolfram's symbolic distribution objects | **Already done** [I/U] |
| 11 | Refinement/subset scalar types as a poset (`types.py`) | Lean/Rocq `Subtype` (dependent, strictly stronger); Mizar adjectives; SMT-LIB has none | **Already done, better** [E for Lean/Rocq; U for Mizar detail] |
| 12 | Rational-exponent dimension vectors over 7 SI base dimensions (`V0_DESIGN_FREEZE.md` §6) | Kennedy dimension types / F# UoM; Unitful.jl; Wolfram `UnitDimensions`; OpenMath `dimensions1` | **Already done** [E] |
| 13 | Dimensional checking is decidable and exact (`V0_DESIGN_FREEZE.md` §6) | F# UoM type checker; Unitful.jl | **Already done** [E] |
| 14 | Explicit quantifier scope so `∀x∃y` ≠ `∃y∀x` structurally (`nodes.py` `Quantifier`, H2) | SMT-LIB §3.6.1 eqns 3.1/3.2; OpenMath `OMBIND` §2.1.3(iv); Content MathML `bind`/`bvar` §4.2.6 | **Already done** [E] |
| 15 | Locally-nameless canonical form; alpha-renaming preserves the hash (`V0_DESIGN_FREEZE.md` §5) | de Bruijn indices (1972); Lean/Rocq kernel term representation; locally-nameless is a named standard technique | **Already done** [E for Lean/Rocq; I for the general technique] |
| 16 | Deterministic canonical serialisation, sha256 as object identity (`V0_DESIGN_FREEZE.md` §7) | Content-addressed code (Unison), hash-consing, IPLD | **Already done** [I — not verified this session] |
| 17 | Concept families with derivable siblings / morphological regularity (`GOAL.md` §6) | Lojban `gismu`/`rafsi`/`lujvo`; MMT theory morphisms; MathScheme theory combinators; Isabelle locales | **Already done** [E for Lojban and MMT] |
| 18 | Compact, machine-emitted syntax not optimised for print (`GOAL.md` §5, L1) | SMT-LIB; AlphaGeometry's DSL; Metamath | **Already done** [E] |
| 19 | Provenance carried in the semantic core (`GOAL.md` §5, L2) | OMDoc metadata; MMT source refs; W3C PROV-O; proof terms | **Already done elsewhere; NOT in HML v0** [E on the HML gap] |
| 20 | "AI systems participate in refining the language" (`GOAL.md` §7) | No direct precedent found for *language* refinement; adjacent work exists on learned DSLs and library learning (DreamCoder-style) | **Partially open** [U] |
| 21 | Empirical comparison of representations for LLM math accuracy (`GOAL.md` §8) | Autoformalization literature (Wu 2022, Draft-Sketch-Prove); format-restriction studies (Tam 2024); structured-template studies | **Adjacent work exists; the specific matched-arm design appears open** [E on the adjacent work] |

---

## 5. Residual Novelty Assessment

I looked hard for a structurally new representational idea and did not find one. Here is what
actually remains, ranked by how defensible it is.

### 5.1 Defensible: the experiment, not the representation

`GOAL.md` §8 specifies a five-arm comparison (prose / LaTeX / code / existing formal language /
HML) with deterministic scoring, preregistered null hypotheses, and a commitment to publish
negative results. I found **no published study that does exactly this** [U — absence of evidence
after a targeted search, not proof of absence]. The autoformalization literature measures LLMs
generating *into existing* formal languages; the prompt-format literature measures *presentation*
of prose. A controlled comparison where the representation itself is the independent variable,
with compiler-deterministic scoring, is a real and useful piece of science.

**This is the project's contribution. It is a methodological and empirical contribution, not a
representational one.** [I]

### 5.2 Weakly defensible: mandatory-ness where others offer conventions

Three hardenings are, as far as I can tell, not enforced by any system I examined:

1. **Positional distribution arguments are a parse error** (D-003). PyMC *allows* named
   parameters; HML *requires* them. [E on PyMC; I on the delta.]
2. **No subtyping path between `T`, `RandomVariable[T]` and `Distribution[T]`**, enforced
   structurally by the `~` rule. Many PPLs blur this in practice. [I]
3. **A `concept` with no invariant and no example is rejected by the checker.** OpenMath CDs
   *provide* `FMP` and `Example` slots; they are not, to my knowledge, mandatory. [I]

These are each one sentence of policy. They are real design choices with real consequences for
generation reliability, and they are exactly the kind of thing an experiment can measure. They
are not "structurally new representational constructs" and must not be described as such.

### 5.3 Weakly defensible: the scalar refinement *poset*

`types.py` deliberately makes `Probability` and `PositiveReal` incomparable, meeting at
`NonNegativeReal`, and the freeze says "implementations that linearise this order are wrong".
Stan's constraints are explicitly outside the type system [E]; SMT-LIB has no subtyping [E];
Lean's `Subtype` is strictly more powerful but requires proof terms to inhabit. A *cheap,
decidable, non-linear* refinement lattice sitting between "no refinement" and "full dependent
subtypes" is a plausible sweet spot for machine generation. Whether it is one is an empirical
question, and it is a good hypothesis to test. [I]

### 5.4 Not defensible

The three-layer architecture, the semantic-core-as-source-of-truth framing, dimension vectors,
alpha-invariant hashing, quantifier scoping, role-labelled arguments as a mechanism, concept
families, content-addressed identity, the "one object, many views" pipeline, and the
"connect all mathematical systems" ambition. Each has at least one, usually several, prior
implementations named in §3 and §4. [E]

---

## 6. Adversarial pressure on the residual novelty

If §5.1 is the contribution, then the threats to §5.1 are the threats to the project. Four are
serious and only one of them appears in `GOAL.md` §8.

### 6.1 The out-of-distribution problem — the largest unlisted threat

Arms A–D use representations that are massively present in LLM pretraining data: prose, LaTeX,
Python, Lean/Isabelle. Arm E uses a language invented last month with zero tokens in any
pretraining corpus. **A null or negative result for arm E is therefore heavily confounded with
familiarity, and a positive result is that much more surprising.** [I]

`GOAL.md` §8 lists five failure conditions. None of them is "the model has never seen this
language". This omission should be corrected in the benchmark protocol before any run, along
with a stated mitigation (few-shot grammar in context, a fine-tuning arm, or a
grammar-constrained decoder — each of which changes what is being measured).

### 6.2 Format restriction is known to *hurt* reasoning

Tam et al., "Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of
Large Language Models" (EMNLP 2024 Industry Track) reports "a significant decline in LLMs'
reasoning abilities under format restrictions", with "stricter format constraints generally
lead[ing] to greater performance degradation in reasoning tasks"
[E, <https://arxiv.org/abs/2408.02442>, <https://aclanthology.org/2024.emnlp-industry.91/>].

HML is, from the model's point of view, a strict format restriction with mandatory role labels
and a parse error for the natural positional form. This is published prior evidence pointing the
*opposite* way to the thesis. It must be cited in the benchmark protocol as a preregistered
alternative hypothesis, not discovered after the fact. [I]

### 6.3 The scaffolding confound is real and already half-conceded

`GOAL.md` §8 failure condition 3 anticipates it. The structured-template literature (e.g.
arXiv 2508.19069) reports gains of roughly +6 pts on GSM8K and +2 pts on AIME from structured
solution templates *without any new representation* [E via search; [U] on the exact numbers,
which I did not verify against the paper body]. That is the size of effect a well-designed
prose-with-checklist control arm can produce. Arm E must beat that control, not just plain prose.

### 6.4 AlphaGeometry cuts both ways

It is the best evidence that a compact machine-emitted DSL plus a deterministic checker wins.
It is also the best evidence that the win comes from the *checker* (DD+AR), not the notation
[E on the architecture, <https://github.com/google-deepmind/alphageometry>; I on the attribution].
If HML's gains vanish when the compiler feedback loop is removed, the finding is "compiler
feedback helps", which is already known.

---

## 7. Implementation gaps found while auditing

These are factual observations about this repository, not about prior art.

1. **Provenance is claimed but not implemented.** `GOAL.md` §5 says Layer 2 carries
   "objects, roles, constraints, dependencies, transformations, **provenance**", and §4.3 makes
   "every inference has traceable dependencies" a governing invariant. `src/hamiltonian_lang/ast/nodes.py`
   contains no provenance field on any node — only `Span` (source location) and `type_`. There is
   no dependency edge, no derivation record, no justification field, and no `InferenceStep` node.
   [E, direct file read.] Either implement it or remove the claim.
2. **`!` collides with SMT-LIB.** `V0_DESIGN_FREEZE.md` §1 reserves `!` as a proof-obligation
   marker; SMT-LIB 2.6 §3.6 uses `!` as the annotation operator [E]. Backend authors and
   models trained on SMT-LIB will conflate them.
3. **`Arg` is defined but `Call` does not use it.** `nodes.py` defines `Arg(role, value)` and
   documents that "positional arguments are not permitted in distribution expressions", but
   `Call` carries `args: list[Expr]` (positional) and only `DistExpr` carries `list[Arg]`. [E,
   direct file read.] The role-labelling discipline is therefore narrower than the freeze text
   implies — it applies to distributions only.
4. **`join` on quantities is lossy.** `types.py::join` builds `QuantityType(a.dimension,
   ScalarType(str(join(a.base, b.base))))` — if the inner join returns `UnknownType`, `str()`
   yields `"Unknown"` and `ScalarType("Unknown")` raises `ValueError`. [E, direct file read.]
   Out of scope for prior art, but worth a ticket.

---

## 8. What to reuse rather than rebuild

Ordered by value.

| Reuse | From | Licence | Why |
|---|---|---|---|
| Distribution family names, parameter role names, and parameterisation identifiers | **ProbOnto** | CC-BY 4.0 [E] | Makes D-003's role vocabulary citable rather than invented; 80+ distributions already catalogued with alternative parameterisations |
| Benchmark problem sets | **miniF2F, ProofNet** | check per-repo [U] | Comparability with published baselines; authoring fresh problems makes arm D uncomparable |
| Constraint / arithmetic solving | **Z3** | MIT [E] | Do not build a solver |
| Symbolic manipulation and unit algebra | **SymPy** (incl. `sympy.physics.units`) | BSD-3 [E] | Do not build a CAS |
| Verification backend | **Lean 4 + mathlib4** | Apache-2.0 [E] | Already the chosen target; Apache-2.0 is clean for commercial use |
| Probabilistic backend | **PyMC** or **NumPyro** | Apache-2.0 [E] | Both permissive; PyMC's named-parameter API maps almost 1:1 onto `DistExpr` |
| Dimension algebra design | **Unitful.jl** type structure `Quantity{T,D,U}` | UNVERIFIED [U] | Its dimension/unit separation is what v0 will need when it adds conversion |
| Semantic interchange target / export format | **OMDoc + MMT** | MMT: BSD-3 [E]; OMDoc spec: UNVERIFIED [U] | An OMDoc export makes the "one representation, many systems" claim demonstrable rather than asserted, and connects to OAF's existing Isabelle/Coq exports |
| Multi-target IR architecture | **MLIR** (design, not code) | Apache-2.0 w/ LLVM exception [E] | Progressive lowering and IR verification are solved problems |
| Elaborator architecture | **Lean 4** `Syntax`→`Expr` (design) | Apache-2.0 [E] | The reference implementation of HML's L1↔L2 split |
| Prose-and-output document rendering for the H4 feedback arm | **Alectryon** | MIT [E] | Do not build a literate prover-output renderer |

**Avoid as dependencies:** Wolfram Language (proprietary; free Engine forbids commercial output
[E]); Mizar and Naproche (GPL-3, embedding-hostile [E]); Rocq (LGPL-2.1 — subprocess only [E]).

---

## 9. Licence summary

Full per-system detail is in `PRIOR_ART_MATRIX.csv`. Verified this session:

| Permissive, safe for a private commercial project | Copyleft — subprocess only, no embedding | Proprietary / blocked | Unverified |
|---|---|---|---|
| Lean 4 (Apache-2.0), mathlib4 (Apache-2.0), Z3 (MIT), SymPy (BSD-3), Stan (BSD-3), Isabelle core (BSD-3), MMT (BSD-3), Turing.jl (MIT), PyMC (Apache-2.0 + MIT parts), NumPyro (Apache-2.0), MLIR (Apache-2.0 + LLVM exception), Dedukti (CeCILL-B), AlphaGeometry code (Apache-2.0), Alectryon (MIT), ProbOnto (CC-BY-4.0), set.mm (CC0), sTeX (LPPL) | Rocq (LGPL-2.1 only), Mizar system (GPL-3+), MML (GPL / CC-BY-SA), Naproche (GPL-3), metamath program (GPL-2+), ACE/APE (LGPL) | Wolfram Language / Wolfram Engine; Theorema (requires Mathematica) | OpenMath standard & CDs; OMDoc spec; Unitful.jl; Lojban CLL; Isabelle bundled add-ons; miniF2F/ProofNet repos; Theorema |

**Not legal advice.** The "subprocess only" guidance reflects the common reading that invoking an
independent executable does not create a derivative work; that reading is not universally agreed
and has never been settled for these specific projects. Get counsel before shipping.

---

## 10. Claims We Cannot Make

These are specific sentences the project must not write, in the repository, in a paper, in a
README, or in a pitch. Each is followed by the system that makes it false and, where useful, a
sentence that *is* defensible.

1. ❌ "Hamiltonian Lang introduces a semantic layer separate from surface syntax."
   → Lean 4 (`Syntax`/`Expr`), Rocq (Gallina/CIC kernel, the de Bruijn criterion), MathML
   (Presentation/Content). ✅ "Hamiltonian Lang follows the standard elaborator architecture
   established by Lean and Rocq."

2. ❌ "No existing system provides a common semantic representation connecting proof assistants,
   CAS, probabilistic and numerical tools."
   → OpenMath, OMDoc, MMT/OAF, Dedukti/Logipedia. This claim is simply false and easily
   falsified by a reviewer in thirty seconds. ✅ "OpenMath, OMDoc and MMT already pursue this
   goal; Hamiltonian Lang differs in its optimisation target, not its ambition."

3. ❌ "Hamiltonian Lang is the first language to separate mathematical content from
   presentation."
   → Content MathML (W3C, 1998), and Strict Content MathML is literally an XML encoding of
   OpenMath objects (MathML 3 §4.1.3).

4. ❌ "Role-labelled distribution parameters are a novel mechanism for eliminating
   parameterisation ambiguity."
   → PyMC (`mu`/`sigma`/`tau` with a documented precision-vs-sd note), SciPy (`loc`/`scale`),
   ProbOnto (six catalogued log-normal parameterisations). ✅ "Hamiltonian Lang makes role
   labels *mandatory*, where PyMC and SciPy make them available; whether mandatory labelling
   improves machine generation reliability is hypothesis H-D003."

5. ❌ "Existing notation leaves domains, ranges and restrictions implicit."
   → Content MathML has had `domainofapplication` and `condition` qualifier elements since
   MathML 2 (§4.3.3). ✅ "Existing *human-facing* notation leaves these implicit; existing
   *content* markup does not, but is not what LLMs are trained on."

6. ❌ "Hamiltonian Lang's dimension system is a novel contribution."
   → Kennedy's dimension types (ESOP 1994), F# units of measure, Unitful.jl, Wolfram
   `UnitDimensions`, OpenMath `dimensions1`. Three of those also do unit conversion, which HML
   v0 explicitly does not (`V0_DESIGN_FREEZE.md` §8).

7. ❌ "Alpha-invariant canonical hashing is a novel property of the design."
   → de Bruijn indices (1972); every proof-assistant kernel; content-addressed code systems.

8. ❌ "Requiring every new concept to carry a formal definition and testable consequences is
   without precedent."
   → OpenMath Content Dictionaries have `CMP`, `FMP` and `Example` elements (OpenMath 2.0
   §4.3.2). ✅ "Hamiltonian Lang makes the OpenMath `FMP`/`Example` structure mandatory and
   machine-checked."

9. ❌ "Encoding relationships between concepts in the language itself, the way morphology does
   in human languages, is a new idea."
   → Lojban's `gismu`/`rafsi`/`lujvo` system does exactly this and has since 1987; MMT theory
   morphisms and MathScheme theory combinators do it formally.

10. ❌ "Existing traditions optimise for human rigour or human ergonomics, not for machines."
    (`GOAL.md` §11)
    → SMT-LIB is a machine-to-machine interchange format with no ergonomic pretensions;
    OpenMath's founding purpose is software-to-software exchange; MMT/OAF exists to move
    12,000+ Isabelle theories between systems. ✅ "Existing traditions optimise for
    machine *execution* and *exchange*; none was designed around the failure modes of
    autoregressive generation."

11. ❌ "Hamiltonian Lang improves AI mathematical reasoning." (or any tensed variant:
    "improves", "makes more reliable", "reduces errors")
    → Nothing has been measured. `V0_DESIGN_FREEZE.md` §9 already says so; keep it that way
    everywhere. ✅ "Hamiltonian Lang is an untested hypothesis about AI mathematical reasoning."

12. ❌ "Structured representation is known to help language models reason."
    → Tam et al. (EMNLP 2024) report the opposite for format restrictions. The literature is
    contested. ✅ "The literature is split: structured templates have been reported to help,
    while format restrictions have been reported to hurt; this is why the comparison must be
    run."

13. ❌ "Layer 2 carries provenance." (`GOAL.md` §5)
    → Not true of this repository as of this audit: `ast/nodes.py` has no provenance field.
    Implement it or delete the word.

14. ❌ "The semantic core is the actual contribution." (`GOAL.md` §5, the annotation on the
    Layer 2 box)
    → On the evidence in this document, the semantic core is a competent re-implementation of
    known constructs. ✅ "The experiment is the actual contribution; the semantic core is the
    apparatus."

---

## 11. Recommendations to the Lead Architect

1. **Rewrite `GOAL.md` §11 ("Intellectual Lineage") into a citation section.** Name Lean, Rocq,
   OpenMath, OMDoc, MMT, Dedukti, Lojban, Kennedy, ProbOnto and MLIR explicitly. A project that
   names its precedents is credible; one that gestures at "traditions" invites the reviewer to
   go find them. This costs nothing and buys most of the project's defensibility back.
2. **Demote Layer 2 from "the actual contribution" to "the apparatus", and promote §8 (the
   experiment) to the contribution.** This is the single highest-value edit available.
3. **Add a sixth failure condition to `GOAL.md` §8:** "Arm E underperforms because the
   representation is absent from pretraining data, and the gap does not close under in-context
   grammar provision or fine-tuning." Pre-register the mitigation.
4. **Cite Tam et al. 2024 as a preregistered alternative hypothesis** in
   `docs/research/BENCHMARK_PROTOCOL.md`.
5. **Adopt ProbOnto parameter names** for the distribution role vocabulary before the family
   table is written by hand.
6. **Either implement provenance in `ast/nodes.py` or strike it from `GOAL.md` §5.**
7. **Resolve the `!` collision with SMT-LIB** before the token is un-reserved.
8. **Open a follow-up on Mizar's adjective/cluster system** as a possible better answer to the
   scalar refinement problem than the hand-maintained `_SCALAR_PARENTS` table.
9. **Resolve the UNVERIFIED register in §12** before any external claim about reusability.

---

## 12. UNVERIFIED register

Open items. Each is a factual question that this audit could not answer and that someone should
close before the corresponding claim is made externally.

| # | Question | Why it matters |
|---|---|---|
| U1 | What licence/IPR governs the OpenMath standard and its Content Dictionaries? | Blocks reusing CD symbol names or definitions |
| U2 | What licence governs the OMDoc specification and reference tooling? | Blocks an OMDoc export path |
| U3 | Unitful.jl licence (LICENSE path 404'd) | Blocks borrowing its dimension/unit type design in code |
| U4 | Exact GPL version and terms in the current Mizar system release | Only matters if we ever invoke Mizar |
| U5 | Current Logical Language Group licensing of Lojban materials | Only matters for quoting the CLL |
| U6 | Metamath program's current LICENSE file (canonical path not reachable) | Low stakes; `set.mm` is CC0 regardless |
| U7 | miniF2F and ProofNet repository licences | Blocks reusing their problem sets in the benchmark |
| U8 | Whether Stan's distribution arguments are strictly positional in the functions reference | Affects the D-003 comparison table |
| U9 | mathlib4's exact treatment of random variables vs measures (`PMF`, `Measure`, `IsProbabilityMeasure`) | Affects the claim in row 10 of §4 |
| U10 | Whether any published system enforces *mandatory* role labels on distribution constructors | The core of the §5.2 novelty claim rests on this negative |
| U11 | Whether any prior work runs a matched-arm representation comparison for LLM math | The core of the §5.1 novelty claim rests on this negative |
| U12 | Isabelle distribution's bundled add-on licences (LGPL/GPL components) | Only matters if we vendor rather than invoke |
| U13 | Theorema's licence | Low stakes; blocked by Mathematica dependency anyway |
| U14 | Exact effect sizes in the structured-template literature (arXiv 2508.19069) | Needed to size the control arm in §6.3 |
| U15 | Whether OpenMath statistics CDs already fix distribution parameter roles | Would strengthen or weaken §5.2 item 1 |

---

## 13. Sources

Primary sources consulted and cited above:

- Lean 4 LICENSE — <https://raw.githubusercontent.com/leanprover/lean4/master/LICENSE>
- mathlib4 LICENSE — <https://raw.githubusercontent.com/leanprover-community/mathlib4/master/LICENSE>
- Lean 4 metaprogramming book — <https://leanprover-community.github.io/lean4-metaprogramming-book/>
- Rocq core language / de Bruijn criterion — <https://rocq-prover.org/doc/master/refman/language/core/index.html>
- Rocq LICENSE — <https://raw.githubusercontent.com/rocq-prover/rocq/master/LICENSE>
- Isabelle COPYRIGHT — <https://raw.githubusercontent.com/isabelle-prover/mirror-isabelle/master/COPYRIGHT>
- Mizar system — <https://github.com/MizarProject/system> ; MML licensing — <https://github.com/JUrban/MMLLicense>
- Metamath (FSF directory) — <https://directory.fsf.org/wiki/Metamath>
- Dedukti — <https://github.com/Deducteam/Dedukti> ; Logipedia — <https://arxiv.org/pdf/2305.00064>
- OpenMath 2.0 standard — <https://openmath.org/standard/om20-2019-07-01/omstd20.html>
- OpenMath CD chapter (CMP/FMP/Example, §4.3.2) — <https://openmath.org/standard/om20-2004-06-30/omstd20html-4.xml>
- OpenMath STS — <https://openmath.org/cd/sts.html> ; <https://people.bath.ac.uk/masjhd/OpenMath/sts2.pdf>
- OpenMath units CDs — <https://openmath.org/cdgroups/units> ; <https://openmath.org/documents/Units.pdf>
- MathML 3 Chapter 4 (Content MathML) — <https://www.w3.org/TR/MathML3/chapter4.html>
- OMDoc 1.6 — <https://www.omdoc.org/OMDoc1.6/>
- MMT — <https://uniformal.github.io/> ; <https://kwarc.info/systems/mmt/> ; COPYING.txt — <https://raw.githubusercontent.com/UniFormal/MMT/master/COPYING.txt>
- OAF (Open Archive of Formalizations) — <https://uniformal.github.io/doc/archives/oaf.html> ; <https://arxiv.org/pdf/1905.07244>
- Kohlhase & Rabe, "A Survey of Languages for Formalizing Mathematics" — <https://arxiv.org/abs/2005.12876>
- SMT-LIB 2.6 standard — <https://smt-lib.org/papers/smt-lib-reference-v2.6-r2021-05-12.pdf>
- Z3 LICENSE — <https://raw.githubusercontent.com/Z3Prover/z3/master/LICENSE.txt>
- MLIR — <https://mlir.llvm.org/docs/DefiningDialects/AttributesAndTypes.md> ; <https://en.wikipedia.org/wiki/MLIR_(software)>
- Stan types reference — <https://mc-stan.org/docs/reference-manual/types.html> ; LICENSE — <https://raw.githubusercontent.com/stan-dev/stan/develop/LICENSE.md>
- PyMC Normal — <https://www.pymc.io/projects/docs/en/stable/api/distributions/generated/pymc.Normal.html> ; LICENSE — <https://raw.githubusercontent.com/pymc-devs/pymc/main/LICENSE>
- NumPyro LICENSE — <https://github.com/pyro-ppl/numpyro/blob/master/LICENSE.md>
- Turing.jl LICENCE — <https://raw.githubusercontent.com/TuringLang/Turing.jl/master/LICENCE>
- SciPy norm — <https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.norm.html>
- ProbOnto — <https://academic.oup.com/bioinformatics/article/32/17/2719/2450721> ; LICENCE — <https://raw.githubusercontent.com/probonto/ontology/master/LICENCE.md>
- SymPy LICENSE — <https://raw.githubusercontent.com/sympy/sympy/master/LICENSE>
- Wolfram Quantity — <https://reference.wolfram.com/language/ref/Quantity.html> ; NormalDistribution — <https://reference.wolfram.com/language/ref/NormalDistribution.html> ; Engine terms — <https://www.wolfram.com/legal/terms/wolfram-engine.html>
- Naproche — <https://github.com/naproche/naproche> ; <https://naproche.github.io/>
- Attempto APE — <https://github.com/Attempto/APE>
- Lojban CLL — <https://lojban.github.io/cll/>
- AlphaGeometry — <https://github.com/google-deepmind/alphageometry>
- Wu et al., "Autoformalization with Large Language Models" — <https://arxiv.org/abs/2205.12615>
- Tam et al., "Let Me Speak Freely?" — <https://arxiv.org/abs/2408.02442> ; <https://aclanthology.org/2024.emnlp-industry.91/>
- Farmer & Carette, "Biform Theories: Project Description" — <https://arxiv.org/pdf/1805.02709>
- F# units of measure — <https://fsharp.github.io/fslang-spec/units-of-measure/>
- Unitful.jl types — <https://painterqubits.github.io/Unitful.jl/v0.1/types/>
- sTeX — <https://github.com/slatex/sTeX> ; Alectryon — <https://github.com/cpitclaudel/alectryon> ; Theorema — <https://github.com/windsteiger/Theorema>
