# The mathematical-library contract

**Status: normative.** Code that disagrees with this document is wrong, or this document
must be amended first and the amendment justified.

Companion to `GOLD10_CORE_SEMANTICS_SPEC.md`, which specifies the *core* repair. This one
specifies the layer above it: how domain mathematics reaches the reasoning graph without
becoming part of the trusted kernel.

---

## A. What belongs in universal HML core

The core is the part every piece of reasoning uses, regardless of subject:

* canonical IR and identity (`SymbolId`, `expr_identity`);
* name resolution, scopes, binders;
* type and refinement checking;
* the evidence DAG, its invariants and claim statuses;
* the **inference kernel** — modus ponens, universal introduction, substitution: about
  eighteen operations for the whole of mathematics;
* the certificate boundary itself, and the small checkers registered in it;
* obligation generation and discharge against Γ.

It is small on purpose and it does not grow when mathematics does.

## B. What belongs in domain libraries

Everything that is true of a *subject* rather than of reasoning:

* algebraic identities (`x + 0 = x`);
* probability laws (`P(A ∩ B) = P(A)·P(B|A)`);
* calculus rules (quotient, product, power).

There are unboundedly many of these. Putting them in `kernel.RULES` would grow the trusted
computing base once per fact anybody needed, and each addition is a new place for an
unsound step to enter. Gold-10 needs three; Gold-100 would need dozens.

**The test that keeps this honest** is `test_no_library_theorem_became_a_kernel_rule`,
which asserts no theorem id appears in `kernel.RULES`, and
`test_the_kernel_rule_set_is_unchanged_by_this_layer`, which pins the rule set exactly.

## C. Theorem schema

`libraries/theorem.py`:

```
LibraryTheorem
    id, version          -> key is `<id>_v<version>`; changed semantics means a changed key
    library              -> algebra | probability | calculus
    variables            -> TheoremVariable(name, domains, kind)
    premises(sub)        -> propositions that must already be established AND declared
    side_conditions      -> SideCondition(build, reason, mandatory)
    conclusion(sub)      -> the proposition the theorem licenses
    statement            -> human-readable; never enters identity
    verification_kind    -> LIBRARY_AXIOM | DEFINITIONAL | REPLAYED
    justification        -> required non-empty for assumed kinds
    provenance
```

`TheoremVariable.kind` separates `value` from `event`. Probability quantifies over
**events**, which in HML are propositions over random variables and a distinct type;
without the distinction `P(3.0)` would instantiate.

`domains` are checked with the language's own `is_subtype`, never a private notion of
compatibility.

## D. Theorem instantiation

```
retrieve theorem from the STATIC registry
    -> bind variables (every one, no extras)
    -> check each substitution's resolved type against the declared domain
    -> build the licensed conclusion
    -> compare it to the author's claim under expr_identity
    -> require every declared premise
    -> emit side conditions as ordinary obligations
    -> CheckedEvidence
    -> ordinary evidence DAG
```

A theorem does **not** get its own proof state, its own graph, or its own status
vocabulary. It elaborates into the existing ones. `forall_intro` and `forall_elim` remain
the generic logical operations, and a theorem supplies only the domain fact they act on —
G07 is `add_zero` (fact) composed with `forall_intro` (logic), not a rule that knows about
`n + 0`.

## E. Side-condition generation

Side conditions become **`ReasoningObligation`s** and are discharged against Γ by
`RefinementEnv.entails` — the same code path that discharges a `divide_both_sides`
obligation. There is no library-specific condition system.

An undischarged mandatory side condition means the certificate **does not validate**. This
is stricter than a derivation, which would be `CHECKED`-but-not-`VERIFIED`, and
deliberately so: a certificate is all-or-nothing. There is no "provisionally certified"
state for it to occupy, and inventing one would let a conditional probability be used at
probability zero pending a repair that might never come.

Two conditions exist in V0:

| theorem | condition | why |
|---|---|---|
| `conditional_product` | `P(A) > 0` | `P(B\|A)` is undefined at zero |
| `derivative_trace_v1` quotient step | `v != 0` | on the **original denominator**, not the derived `v^2` |

## F. Certificate checking

Two checkers, deliberately different in shape because they rest on different things.

**`library_theorem_v1`** checks the *instantiation* — registry membership, variable
coverage, type conformance, conclusion identity, premise declaration. It does **not** check
the theorem, and says so.

**`derivative_trace_v1`** checks by *replay* — it differentiates the expression itself from
primitive rules and compares. Nothing in the proposal is trusted, so a derivative from a
CAS, a model or a guess is worth exactly what one typed by hand is: a claim the replay
decides.

Normalisation after a replay uses the **oriented algebra identities**, each a named
registered theorem, applied deterministically to a fixed point. Termination is structural —
every rewrite strictly reduces the term. `sympy.simplify` is not used anywhere on this
path, and `test_no_untrusted_oracle_is_imported_on_the_calculus_path` asserts it over the
import graph.

## G. Provenance and versioning

The version is part of the registry key. When a theorem's semantics change, the key
changes, and modules naming the old key stop validating rather than silently acquiring new
behaviour. The certificate's `detail` records the theorem, its version, its library, its
verification kind and the substitution used.

Execution metadata — timestamps, durations, host — never enters semantic identity.

## H. Library trust status

**This is the section that matters most.**

A library is shipped Python. If living in a shipped Python file were enough to make an
assertion `VERIFIED`, the trusted computing base would be "everything anyone ever added to
`libraries/`", which is no boundary at all.

So the assumed part is *enumerable*:

| theorem | kind | what is actually being trusted |
|---|---|---|
| `add_zero`, `zero_mul`, `one_mul`, `mul_one`, `zero_sub` | `LIBRARY_AXIOM` | the identity itself. HML has no induction and no ring-structure contract, so these are **asserted**, not derived. |
| `conditional_product` | `DEFINITIONAL` | nothing beyond the definition of conditional probability, which HML's probability ontology already commits to. |
| the differentiation rules | `REPLAYED` | nothing. The checker re-derives the answer. |

`libraries.axioms()` prints the complete assumed set, every entry carries a written
justification, and the registry **refuses** an assumed theorem with an empty one. A trusted
computing base you can only describe is one nobody checks; this one can be listed.

What a certificate proves is *"this instantiation of that named axiom, correctly typed,
with its side conditions discharged"* — never the axiom itself.

## I. Relationship to the evidence DAG

Every `CheckedEvidence` joins the ordinary graph and is subject to every existing
invariant: acyclicity, no goal/requirement/conjecture laundered into evidence, transitive
open obligations blocking `VERIFIED`, complete provenance, environment tagging on imported
evidence. No second graph is built.

`EvidenceKind` keeps the axes separate: `NATIVE_KERNEL` and `CHECKED_CERTIFICATE` may
support `VERIFIED`; `UNTRUSTED_ORACLE`, `NUMERIC_BOUND` and `NONE` never can.

## J. Relationship to `forall_elim` and substitution

Theorem application is *not* a rival to universal instantiation. A theorem schema is
instantiated by binding its variables — which is what `forall_elim` does for a universal
already in the module — and the resulting concrete fact then flows through the ordinary
machinery. A theorem stated with an explicit `forall` in HML source would be eliminated
with `forall_elim`; a theorem in the library is instantiated at the boundary. Same
operation, different residence.

The calculus checker performs one substitution of its own, documented at
`calculus._instantiate_binder`: `derivative(body, x : T) = g(x)` binds `x` on the left and
refers to the free module-level `x` on the right, and the notation means them to be the
same point. That is an *interpretation of an existing construct*, not a change to binder
semantics.

## K. Fail-closed behaviour

Every one of these is a rejection, each with a test:

unknown theorem id · unknown checker · wrong theorem version (a different key, hence
unknown) · missing variable · spurious variable · wrongly typed substitution · conclusion
the theorem does not license · undeclared premise · undischarged side condition · reversed
conditioning direction · non-event operand where an event is required · incorrect
derivative · wrong differentiation variable · malformed certificate · argument passed to a
checker that takes none · expression outside the differentiation fragment · any exception
raised by a checker.

There is no path on which a failure becomes a pass, and no `trust_me_this_is_true`.

## L. Theorem vs inference rule vs execution vs oracle

Four things this document keeps apart, because collapsing any pair is a way to get a wrong
answer that looks authoritative:

| | what it is | where it lives | trusted? |
|---|---|---|---|
| **inference rule** | a primitive universal reasoning operation | `reasoning/kernel.py` | yes — it is the kernel |
| **theorem** | a proposition about a domain | `libraries/` | the *instantiation* is checked; the statement may be assumed, and is labelled |
| **executable computation** | evaluating a closed term exactly | `verification/obligations/evaluate.py` | yes, deliberately admitted; it is HML-owned and exact |
| **oracle** | an external system's answer | SymPy, a CAS, an SMT solver, a model | **no.** May propose; never establishes |

`equivalence/symbolic.py` is an oracle by this classification and is not registered — its
verdicts rest on raw SymPy flags with no independent replay. That decision is recorded in
`GOLD10_CORE_SEMANTICS_SPEC.md` §2.7 and is unchanged by this layer.

---

## M. Deliberately deferred

Recorded so nobody has to re-derive that they were considered: e-graphs and equality
saturation · a broad `simp` tactic · a complete ring normaliser · measure-theoretic
probability · a full undergraduate probability library · Bayes · expectation and variance ·
distributions · integration · MVT/FTC · transcendental derivatives · interval-domain
calculus · a locally-nameless AST refactor · an external Lean dependency · CAS-guided
search · Gold-100 · training.

Gold-10 needs one algebraic identity, one probability law and a five-rule differentiation
fragment. None of the above is justified by that, and equality saturation in particular
would add a search subsystem with its own proof-extraction and termination questions to
solve a four-step normalisation.

## N. Known limitation, reported not patched

`RefinementEnv.entails` destructures an obligation as `<Ref> <op> <bound>` and returns
`None` the moment the subject is not a declared variable. So a side condition like
`probability(X > 0.0) > 0.0` stays `UNKNOWN` even when the module asserts it verbatim.

The library path works around this with `check._assumed_verbatim`, which does the strictly
weakest sound thing — exact canonical membership of Γ, no reasoning at all. Widening
`entails` itself is the better repair and belongs to the **core track**, because
`reasoning/refinement.py` is context machinery and this mission was told to stop rather
than change context semantics silently.
