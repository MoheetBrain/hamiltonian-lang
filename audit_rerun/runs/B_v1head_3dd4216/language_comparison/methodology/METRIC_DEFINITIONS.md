# Metric Definitions

Status: normative for the language comparison. Every number reported in the
comparison must trace to a definition in this file or in
`SEMANTIC_DENSITY_DEFINITION.md`.

## 0. Method commitments

**0.1 The framework is specified before, and independently of, any system it
scores.** The ontology in `../ontology/` was written by asking "what must a
faithful representation of mathematics be able to express?" — not by enumerating
what any candidate system happens to provide. A framework derived from the
artefact under test measures only self-consistency.

**0.2 Prefer established terminology.** Where a concept already has a name in the
literature we use that name and cite it, rather than minting a new one. Invented
vocabulary hides the fact that a claim is already understood — and often already
refuted.

**0.3 Every metric is red-teamed before use.** For each metric this document
states (a) the naive definition someone would reach for, (b) the concrete way
that definition is gameable or vacuous, (c) the operational definition actually
used, and (d) the residual weakness that remains after hardening.

**0.4 No metric may be reported without its denominator and its scope.** A bare
percentage with an unstated atom set is not a measurement.

### References used for terminology

- McCarthy, J. and Hayes, P. J. (1969). "Some Philosophical Problems from the
  Standpoint of Artificial Intelligence." *Machine Intelligence 4*. Source of the
  triad **metaphysical / epistemological / heuristic adequacy**, and of the
  general framing that a representation is judged by what it can *say*, what it
  can *know* from available information, and what it can *reason with*.
- Levesque, H. J. and Brachman, R. J. (1985). "A Fundamental Tradeoff in
  Knowledge Representation and Reasoning." Source of the expressiveness /
  tractability tradeoff — more expressive power is not monotonically better.
- Post, E. L. (1941). *The Two-Valued Iterative Systems of Mathematical Logic*.
  Source of **functional completeness** as the correct formal notion of
  "complete set of connectives".
- Frege's compositionality principle, as formalised in Montague, R. (1970),
  "Universal Grammar": the meaning of a compound is a function of the meanings of
  its parts and their mode of combination. Used for **compositionality**.
- Shoenfield, J. R. (1967). *Mathematical Logic*. Source of **conservative
  extension** — an extension proving no new theorems in the original language.
- Felleisen, M. (1991). "On the Expressive Power of Programming Languages."
  Source of the notion of expressiveness as **macro-expressibility**: language A
  is at least as expressive as B if B's constructs translate into A by a local,
  meaning-preserving transformation. This is the right notion for judging whether
  a construct is "compositionally representable".
- OpenMath Content Dictionaries, and the MathML content/presentation split.
  Source of the idea of a **phrasebook** translation between formalisms and of
  treating translation loss as the normal case that must be documented.
- Trybulec's Mizar Mathematical Library, and the mathlib organisation practice in
  Lean, as evidence of what "standard library derivation" means in a mature
  mathematical system — the S category below.

---

## 1. Coverage classification: P / S / C / B / L / 0 / ?

Every (system, atom) pair is assigned exactly one code. This is the atomic
judgement from which all coverage metrics are derived.

| Code | Name | Meaning |
|---|---|---|
| `P` | **Primitive** | The atom's essential semantics is realised by a dedicated construct in the language core: dedicated syntax, a dedicated node in the abstract syntax, or a dedicated type former, and the checker enforces its rules. |
| `S` | **Standard derivation** | Not a core primitive, but supplied by the system's own canonical/standard library in a form that carries the same semantics, and is the way the community actually writes it. |
| `C` | **Compositional** | Not supplied, but expressible by a *local, meaning-preserving* combination of constructs the system does have, such that every fact in the atom's essential semantics survives and remains machine-inspectable. |
| `B` | **Backend-dependent** | Representable only by delegating to an external system, so the semantics lives outside the representation. The representation itself cannot check, transform or reason about it. |
| `L` | **Lossy** | Something can be written, and it is accepted, but at least one fact in the atom's essential semantics is dropped, weakened or approximated **without being recorded as such**. |
| `0` | **Absent** | No representation exists. Attempting it is rejected, or the only available encoding is a comment/string that the system does not interpret. |
| `?` | **Unknown** | Not yet probed, or probed with an inconclusive result. `?` is a legitimate and required answer; it must never be silently rounded to `0` or to `C`. |

### 1.1 Decision procedure

Apply the tests in order. The first test that fires assigns the code.

1. **Probe.** Write the atom's `canonical_example` in the system. Record the exact
   source text and the exact system response (accepted / rejected / diagnostic).
   If no probe was run: `?`. Stop.
2. **Rejection test.** If the system rejects every faithful encoding and no
   encoding preserves the semantics: `0`.
3. **Loss test.** Enumerate the facts in `essential_semantics`. For each, ask: can
   the system's own machinery (type checker, printer, canonicaliser, query
   interface) *recover* that fact from the encoded form? If any fact is
   unrecoverable **and** the system does not emit a loss record naming it: `L`.
   Stop. (If the system *does* emit a loss record, the pair is still `L` but is
   tagged `declared_loss: true`; see §1.4.)
4. **Externality test.** If all facts survive only because the encoding names an
   external tool that holds the semantics: `B`.
5. **Primitivity test.** If a dedicated core construct realises the atom: `P`.
6. **Library test.** If the system's own shipped library realises it with full
   semantics: `S`.
7. Otherwise, if a local meaning-preserving composition exists: `C`.

### 1.2 Adjudicating the hard boundary: C versus L

This is the boundary that decides most disputes, so it gets an explicit test.

An encoding earns `C` only if **all four** hold:

- **(C1) Fact preservation.** Every fact in the atom's `essential_semantics`
  is derivable from the encoded form by the system, not merely by a human reading
  the identifiers. A variable named `sigma_positive` does not encode positivity.
- **(C2) Locality.** The encoding is a bounded, context-independent rewriting of
  the construct — Felleisen's macro-expressibility. If encoding one atom requires
  a whole-program transformation, or requires the user to maintain a separate
  side-table of invariants, it is not compositional.
- **(C3) Enforcement.** The system rejects the corresponding *invalid* case. If
  positivity is encoded but a negative value is accepted, the encoding is
  decorative and the pair is `L`.
- **(C4) Composability inward.** The encoded form can itself be placed inside the
  other constructs the atom `composes_with`, without the encoding breaking.

If (C1) fails: `L`. If (C1) holds but (C3) fails: `L`. If (C1) and (C3) hold but
(C2) fails: `C` with a `composition_cost` penalty recorded (see §4), unless the
required transformation is global, in which case `L`.

Worked cases:

- *"σ > 0 written as a comment."* Fails C1 and C3. → `L`.
- *"σ > 0 written as a runtime assertion executed at construction."* Passes C1
  weakly (the fact exists in the program text) but fails C3 statically. Score `C`
  only if the comparison's scope includes runtime checking; otherwise `L`. The
  scope choice must be stated once, globally, and applied to all systems.
- *"σ > 0 written as a refinement type the checker enforces."* All four hold, and
  no dedicated construct was needed. → `C` (or `P`/`S` if the refinement type is
  itself the core construct, in which case an earlier test fires).
- *"∀x∃y encoded by Skolemising to a function f(x), with no record of the
  Skolemisation."* The alternation order is unrecoverable. → `L`, and because
  quantifier order is CRITICAL, this is a critical finding.
- *"A distribution encoded as a sampler closure."* Facts such as the family name,
  parameter roles and support are unrecoverable from a closure. → `L`.

### 1.3 Adjudicating B versus C

`B` applies when the *semantics* leaves the representation, not merely the
*computation*. Delegating numeric evaluation of an integral to a quadrature
library while the integral remains a first-class object in the representation is
`P`/`S`/`C` for the integral atom and a separate concern for the numerical atom.
Delegating the *meaning* of the integral — i.e. the representation holds only an
opaque call to an external routine — is `B`.

### 1.4 Declared versus silent loss

`L` splits into two sub-cases which are reported separately and never merged:

- `L(declared)`: the system emits a machine-readable record naming what it
  dropped, approximated or weakened.
- `L(silent)`: the system produces confident output with no record.

`L(silent)` is strictly worse than `0`. A system that refuses to represent
something tells the truth; a system that accepts it and quietly discards half its
meaning produces authoritative-looking output that is wrong. Any aggregate that
ranks `L(silent)` above `0` is mis-specified.

### 1.5 Evidence requirement

Every non-`?` code must be backed by a stored artefact: the probe source, the
verbatim system output, and a one-line justification referencing the specific
clause of `essential_semantics` that was or was not preserved. Codes without
evidence are downgraded to `?` at report time.

---

## 2. Completeness

**Naive definition.** The fraction of ontology atoms a system supports.

**Why it is gameable.**

- *Denominator selection.* Any system scores near 100% against an ontology built
  from its own feature list. This is the central failure mode and is why §0.1
  exists.
- *Credit for `L`.* If lossy encodings count as "supported", a system is rewarded
  for accepting input it does not understand. Counting `L` as support inverts the
  metric: the most permissive system wins.
- *Atom granularity.* Splitting one capability into eight atoms inflates any
  system that has it and deflates any that does not. Coverage percentages are
  extremely sensitive to how finely the ontology is cut.
- *Uniform weighting.* Treating `LOGIC.FORALL` and `NUM.PADIC` as equal units
  lets a system offset a foundational gap with a pile of exotica.

**Operational definition.** Completeness is reported as a *vector*, never as a
single number:

```
coverage_profile(S) = (n_P, n_S, n_C, n_B, n_L_declared, n_L_silent, n_0, n_?)
```

with the derived weighted scalars

```
faithful_weight(S)   = Σ w(a) for a with code in {P, S, C}
degraded_weight(S)   = Σ w(a) for a with code in {B, L_declared}
absent_weight(S)     = Σ w(a) for a with code in {L_silent, 0}
known_weight         = Σ w(a) over all a with code ≠ ?
completeness(S)      = faithful_weight(S) / known_weight
```

Rules:

- `?` atoms are excluded from *both* numerator and denominator, and the count of
  `?` is reported alongside every completeness figure. A completeness of 0.8 with
  40% unknown is not comparable to 0.8 with 2% unknown.
- `L(silent)` contributes to `absent_weight`, i.e. it is scored **as bad as
  absence** and never counted as coverage.
- Completeness is additionally reported per domain (13 figures) and per
  criticality band (4 figures). The per-band figures are the ones that matter;
  the global figure is a headline that must never be quoted alone.
- The atom-granularity sensitivity is disclosed by also reporting completeness at
  the *domain* level (13 units, one per domain, each scored by its worst
  CRITICAL atom) as a granularity-robust cross-check.

**Residual weakness.** The ontology's own cut points remain a judgement call.
Mitigation: the ontology is versioned, published, and its atom set is fixed
before any system is probed; changes after probing require a recorded rationale.

---

## 3. Expressivity (expressive adequacy)

**Naive definition.** "How much can the language say?", often operationalised as
the number of distinct constructs it has.

**Why it is gameable.** Construct count rewards surface bloat. Two systems can
have identical expressive power with a factor-of-five difference in construct
count. It is also *anti-correlated* with quality in one direction: a language can
gain "constructs" by adding ambiguous sugar. And the naive reading ignores the
Levesque–Brachman tradeoff — unbounded expressiveness makes checking undecidable,
so more is not simply better.

**Established terminology.** McCarthy and Hayes' **epistemological adequacy** is
the right target: can the representation express the facts that are actually
available and needed, in a form usable for reasoning? Felleisen's
**macro-expressibility** is the right formal test for relative expressiveness.

**Operational definition.** Two separate measures, never combined:

```
EA(S)  (expressive adequacy)
   = faithful_weight(S) / total_weight        # over ALL atoms including ?
       computed twice: optimistic (? counted as C) and pessimistic (? as 0),
       and reported as the interval [pessimistic, optimistic].

MER(S, T)  (macro-expressibility relation)
   = for each atom a supported by T but not by S, whether a local
     meaning-preserving encoding into S exists. Reported as a directed
     comparison between two systems, not as a scalar.
```

Expressivity is reported *with* the checking commitment it entails: a system that
can express arbitrary first-order statements but decides nothing about them is
recorded as high `EA`, low `adequacy` (§7).

**Residual weakness.** `MER` requires a judgement about "local", which §1.2 (C2)
pins down only informally. Disputed cases are recorded as disputed, with both
readings' effect on the score shown.

---

## 4. Compositionality

**Naive definition.** "Constructs can be nested."

**Why it is vacuous.** Almost every system permits nesting at the level of
concrete syntax. Nesting that parses but loses meaning, or that is rejected by
the type checker for spurious reasons, is not compositionality. The naive test
passes trivially and therefore discriminates nothing.

**Established terminology.** Frege/Montague **compositionality**: the meaning of
a compound expression is a function of the meanings of its constituents and the
mode of combination. The operational content is that composing two constructs
must not change what either one means, and the compound's meaning must be
recoverable from the parts.

**Operational definition.** Measured against the composition specimens in
`../ontology/COMPOSITION_TESTS.json`. For each specimen the system is scored:

| Outcome | Meaning |
|---|---|
| `COMPOSES` | The compound is accepted and every fact of every participating atom remains recoverable. |
| `COMPOSES_DEGRADED` | Accepted, but at least one participating atom drops from its standalone code (e.g. `P` alone but `L` in composition), with the loss declared. |
| `COMPOSES_SILENT_LOSS` | Accepted, a fact is lost, nothing is declared. |
| `REJECTED_SPURIOUS` | Rejected although both parts are individually supported and the composition is mathematically valid. |
| `REJECTED_CORRECT` | Rejected because the composition is genuinely ill-formed — a *correct* outcome, scored as a pass. |
| `UNSUPPORTED` | At least one participating atom is `0` for this system, so the specimen is not diagnostic; excluded from the denominator. |

```
compositionality(S) = |COMPOSES| + |REJECTED_CORRECT|
                      ---------------------------------------------
                      |specimens| - |UNSUPPORTED| - |not attempted|
```

The **compositional closure gap** is the set of atoms whose standalone code is
better than their in-composition code. This set is the primary diagnostic output
of the whole comparison: it is where a system's advertised capability and its
real capability diverge.

`composition_cost` (referenced in §1.2) is recorded per specimen as the ratio of
tokens in the composed encoding to the sum of tokens in the standalone
encodings. A ratio far above 1 signals that composition is possible only by
re-encoding, which is a compositionality failure even when the outcome is
`COMPOSES`.

**Residual weakness.** The specimen set is finite and hand-designed; it can miss
a failure mode nobody thought of. Mitigation: specimens are published, and any
newly discovered failure mode is added as a specimen rather than reported ad hoc.

---

## 5. Semantic density

Defined in full in `SEMANTIC_DENSITY_DEFINITION.md`. Summary of the trap: the
naive definition (semantic facts per token) rewards *dropping* semantics, because
a representation that omits half the meaning has fewer tokens and the same
nominal fact count if facts are counted from the source statement rather than
from the encoding. The operational definition counts only **faithfully
represented** facts in the numerator, so dropping a fact reduces the numerator
and can never improve the ratio. See that document for the formula and the frozen
tokenizer requirement.

---

## 6. Writability

**Naive definition.** Fewer characters is better.

**Why it is gameable, and why it is dangerous.** Character count is the easiest
metric to optimise and the one most likely to reward the wrong thing. Compressing
`X ~ Normal(mu, sigma)` to `X~N(m,s)` improves the metric and degrades the
representation: it loses the family name's disambiguation and the parameter
roles. Brevity achieved by making a reading ambiguous is a regression, not an
improvement. Writability also has no meaning without holding fidelity fixed.

**Operational definition.** Writability is measured **only among encodings that
are fidelity-equivalent**, i.e. that represent the same faithful fact set.

```
For a specimen p and systems S, T with fidelity(S,p) = fidelity(T,p):
    writability_advantage(S over T, p) = tokens_T(p) / tokens_S(p)
```

Rules:

- Comparisons across different fidelity levels are **prohibited**. If `S` encodes
  8 of 10 facts and `T` encodes 10 of 10, their lengths are not comparable and no
  writability number is reported for that specimen.
- Both characters and tokens are reported. Characters are sensitive to identifier
  naming; tokens are sensitive to tokenizer choice. Reporting both makes the
  sensitivity visible.
- Three ancillary observations are recorded per specimen and reported with the
  number, because they are what brevity is usually traded against:
  `parse_ambiguity` (does any alternative parse exist?), `reading_distance`
  (does the surface form correspond to the standard mathematical notation?), and
  `error_locality` (does an induced single-token corruption produce a localised
  diagnostic or a misleading one?).

**Residual weakness.** Writability is a proxy for human effort and is not
validated against human subjects here. It is therefore reported as a descriptive
statistic and is *never* used as evidence of superiority.

---

## 7. Adequacy

**Naive definition.** "The system is good enough for its purpose."

**Why it is vacuous.** Unfalsifiable without a stated purpose, a stated corpus
and a stated threshold.

**Established terminology.** McCarthy & Hayes distinguish three adequacies. We
adopt all three, with operational tests:

- **Metaphysical adequacy** — the representation admits no state of affairs that
  is mathematically impossible. Test: for each *prohibited conflation* in the
  ontology (a distinction an atom declares must be maintained), attempt to
  violate it. The system must reject. Score = fraction of prohibited conflations
  mechanically rejected.
- **Epistemological adequacy** — the facts actually available can be expressed,
  including partial information (an unknown quantity, a bound rather than a
  value, an assumption rather than a fact). Test: the `EPIS.*` atoms plus the
  partial-information specimens. Score = weighted coverage of the epistemic
  domain.
- **Heuristic adequacy** — the representation supports the reasoning processes it
  is meant to support: the `XFORM.*` atoms. Score = weighted coverage of the
  transformation domain, with `XFORM.SEMANTICS_PRESERVING_CHECK` and
  `XFORM.ROUND_TRIP` as gating atoms (see the severity rubric).

```
adequacy(S) = (metaphysical, epistemological, heuristic)   # a triple, never a scalar
```

There is deliberately no scalar "adequacy score". Collapsing the triple would
hide exactly the asymmetries that matter: a system can be metaphysically strict
and heuristically inert, or expressive and permissive, and those are different
products with different failure modes.

**Residual weakness.** "Prohibited conflations" is itself a design judgement.
Mitigation: each is stated as an atom in the ontology with a rationale, so it can
be argued with.

---

## 8. Aggregation rules

These rules bind every reported figure.

1. **No aggregate may conceal a CRITICAL zero.** If any CRITICAL atom scores `0`
   or `L(silent)`, every aggregate containing it is annotated with the failing
   atom ids, and the system's maturity level is capped (see `MATURITY_LADDER.md`).
2. **Report the vector before the scalar.** Any scalar is accompanied by its
   coverage profile.
3. **Report `?` counts everywhere.** An aggregate over a partially probed atom set
   is labelled provisional.
4. **Never compare across fidelity levels.** Applies to writability, density and
   any per-statement comparison.
5. **No superiority claim without a measured, like-for-like comparison** run under
   this document's rules on a published specimen set, with the specimen set fixed
   before measurement.
6. **Ties are ties.** Differences within the reported measurement noise are
   reported as "no measured difference", not ranked.

---

## 9. What this framework deliberately does not measure

Stated explicitly so their absence is not mistaken for a finding:

- Runtime performance, memory use, compile time.
- Library breadth outside mathematical reasoning.
- Ecosystem size, adoption, documentation quality, tooling.
- Aesthetic preference.
- Suitability for general-purpose programming — explicitly out of scope, and a
  system is neither credited nor penalised for it.

A system that scores poorly here may be excellent at things this framework does
not measure. The converse also holds.
