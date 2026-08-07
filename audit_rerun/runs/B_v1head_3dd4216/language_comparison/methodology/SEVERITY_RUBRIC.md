# Severity Rubric

Status: normative. Governs how every finding in the comparison is classified and
how findings are surfaced in aggregates.

---

## 1. Two different things called "severity"

The comparison produces two distinct classifications, and conflating them is the
first mistake to avoid:

- **Atom criticality** — a property of the *ontology*, fixed in
  `../ontology/MATHEMATICAL_REASONING_ONTOLOGY_V1.json`, independent of any
  system. It answers: how central is this capability to mathematical reasoning?
- **Finding severity** — a property of a *(system, atom, observed behaviour)*
  triple, assigned by this rubric. It answers: how bad is what we observed?

Finding severity is a function of atom criticality **and** the observed failure
mode. A LOW-criticality atom can still yield a HIGH finding if the failure is a
silent one, because silent loss is a defect of the system's honesty, not of the
capability's importance.

---

## 2. Failure-mode axis

| Mode | Description | Honesty |
|---|---|---|
| `SILENT_LOSS` | Input accepted, semantics dropped/weakened/approximated, nothing reported. Output looks authoritative and is wrong. | Dishonest |
| `SILENT_WRONG` | Input accepted and a *different* fact is asserted (e.g. `=` recorded where `~` was meant). | Dishonest |
| `DECLARED_LOSS` | Input accepted, semantics reduced, and a machine-readable loss record names what went. | Honest |
| `SPURIOUS_REJECT` | A mathematically valid statement is rejected. | Honest but limiting |
| `ABSENT` | No representation; attempting it is rejected with a clear diagnostic. | Honest |
| `EXTERNAL_ONLY` | Only representable by delegating meaning outside the system. | Honest but hollow |
| `COMPOSITION_ONLY` | Works standalone, degrades when composed with another supported atom. | Depends on whether the degradation is declared |
| `UNKNOWN` | Not probed or inconclusive. | Neither |

**Ordering principle.** For a given atom criticality:

```
SILENT_WRONG  >  SILENT_LOSS  >  ABSENT  ≈  EXTERNAL_ONLY  >  DECLARED_LOSS  >  SPURIOUS_REJECT
        (worse) ─────────────────────────────────────────────────────────► (less bad)
```

A system that says "I cannot represent this" is better than one that pretends to
and quietly discards half the meaning. Any rubric that ranks silent acceptance
above honest refusal is inverted, and this one does not.

---

## 3. Severity levels

### CRITICAL

Assign when **any** of:

- **C-a.** A CRITICAL-criticality atom exhibits `ABSENT`, `SILENT_LOSS`,
  `SILENT_WRONG` or `EXTERNAL_ONLY`.
- **C-b.** Any atom exhibits `SILENT_WRONG` — a false fact is asserted — regardless
  of the atom's criticality.
- **C-c.** A prohibited conflation is *not* rejected: the system permits an
  identification the ontology declares must be maintained (e.g. accepts a
  distribution where a value of the underlying type is required, or admits an
  ordering on the complex numbers).
- **C-d.** Canonicalisation, round-trip, or a transformation changes meaning: two
  distinct objects become identical, or one object becomes two, or a qualifier is
  lost in transit.
- **C-e.** A CRITICAL atom that passes standalone exhibits `COMPOSES_SILENT_LOSS`
  in any composition specimen.

Meaning: the system will produce confidently wrong mathematics, or cannot express
something fundamental at all. This caps the maturity level (see the ladder) and
must be named in every aggregate that contains it.

### HIGH

Assign when **any** of:

- **H-a.** A HIGH-criticality atom exhibits `ABSENT`, `SILENT_LOSS` or
  `EXTERNAL_ONLY`.
- **H-b.** A CRITICAL-criticality atom exhibits `DECLARED_LOSS` — the system is
  honest, but a foundational capability is nevertheless degraded.
- **H-c.** A MEDIUM or LOW atom exhibits `SILENT_LOSS` in a construct that is
  *advertised* as supported. Advertising plus silent loss is a HIGH finding even
  for a peripheral capability.
- **H-d.** A CRITICAL atom exhibits `SPURIOUS_REJECT`: valid mathematics is
  refused, blocking a broad class of statements.
- **H-e.** A composition specimen involving two HIGH-or-above atoms yields
  `COMPOSES_SILENT_LOSS`.

Meaning: a substantial class of mathematics is unrepresentable or is
misrepresented. Not immediately dangerous in the way CRITICAL is, but it defines
the system's real ceiling.

### MEDIUM

Assign when **any** of:

- **M-a.** A MEDIUM-criticality atom exhibits `ABSENT`, `SILENT_LOSS` or
  `EXTERNAL_ONLY`.
- **M-b.** A HIGH-criticality atom exhibits `DECLARED_LOSS`.
- **M-c.** A HIGH-criticality atom exhibits `SPURIOUS_REJECT`.
- **M-d.** An atom is supported only via `COMPOSITION_ONLY` with a declared
  degradation, i.e. it works alone and honestly reports its degradation when
  composed.
- **M-e.** Diagnostics for a HIGH-or-above atom are non-localised or misleading:
  the system rejects correctly but points at the wrong construct.

Meaning: a real limitation, workaroundable with explicit user effort, and not a
source of wrong output.

### LOW

Assign when **any** of:

- **L-a.** A LOW-criticality atom exhibits `ABSENT`, `DECLARED_LOSS` or
  `EXTERNAL_ONLY`.
- **L-b.** A MEDIUM atom exhibits `DECLARED_LOSS` or `SPURIOUS_REJECT`.
- **L-c.** Verbosity, naming or ergonomic friction with no semantic consequence.
- **L-d.** A documentation gap where the behaviour itself is correct.

Meaning: noted for completeness. LOW findings never affect a maturity level and
never gate a conclusion.

### LIBRARY-NOT-CORE

A distinct classification, **not a severity level**, used when the capability is
absent from the system as measured but is of a kind that mature systems supply
from a library rather than a language core, and the system's core demonstrably
*admits* such a library.

Assign only when **all four** hold:

1. The atom's essential semantics is achievable by definitions written in the
   system itself, with no change to the core (no new syntax, no new type former,
   no checker change).
2. A sketch of that definition is produced and **checked to typecheck**, or the
   reason it cannot be checked is recorded. An unverified sketch does not qualify.
3. The composition tests involving that atom still pass with the library form —
   i.e. the library version is not silently second-class when nested inside other
   constructs.
4. The atom's criticality is not CRITICAL. A CRITICAL capability that is absent
   is a CRITICAL finding even if a library could in principle supply it, because a
   representation's guarantees cannot rest on a library that does not exist.

Reported separately from the severity counts, as `LIBRARY-NOT-CORE (n)`, and
**never** silently folded into "supported". The distinction being drawn is
between "this system cannot do this" and "this system could do this and has not
yet"; both are real, and only the second is a roadmap item rather than a defect.

Misuse to guard against: classifying something LIBRARY-NOT-CORE without producing
the checked definition sketch. That is an unfalsifiable excuse, not a
classification, and is rejected at review.

---

## 4. Worked boundary examples

These are the cases where classification is genuinely arguable. Each gives the
verdict and the reason, so the same reasoning can be applied to new cases.

**B1 — Quantifier order flattened during canonicalisation.**
`∀x∃y P(x,y)` and `∃y∀x P(x,y)` canonicalise to the same form. Atom
`LOGIC.NESTED_QUANTIFIER_ORDER` is CRITICAL; mode is `SILENT_LOSS`; rule C-d also
fires. → **CRITICAL**. Not mitigated by the system "rarely being used that way":
the two statements are different theorems.

**B2 — `X ~ Normal(μ,σ)` accepted but stored as an equality.**
Mode is `SILENT_WRONG`: a false fact replaces the true one. Rule C-b fires
regardless of criticality; `PROB.DISTRIBUTED_AS` is also CRITICAL. →
**CRITICAL**.

**B3 — Units dropped when compiling to a numeric backend, with a loss record.**
`SCI.QUANTITY` is HIGH, mode is `DECLARED_LOSS`. Rule M-b fires. → **MEDIUM**.
Contrast B4.

**B4 — Same as B3 but with no loss record.**
Mode becomes `SILENT_LOSS` on a HIGH atom. Rule H-a fires. → **HIGH**. The only
difference between B3 and B4 is honesty, and it moves the finding a whole level.
That is intentional.

**B5 — p-adic numbers unrepresentable.**
`NUM.PADIC` is LOW, mode is `ABSENT`, honest rejection. Rule L-a. → **LOW**. Not
a defect worth reporting prominently; included so that its absence from the
findings is not mistaken for support.

**B6 — Matrix-valued random variables: `PROB.RANDOM_MATRIX` works, `ALG.MATRIX`
works, but composing them silently drops the positive-definiteness constraint.**
Both atoms are HIGH; mode is `COMPOSES_SILENT_LOSS`. Rule H-e fires. → **HIGH**.
If either atom had been CRITICAL, C-e would have fired instead → CRITICAL. The
lesson this case encodes: standalone capability claims are not composition
claims, and the comparison must probe both.

**B7 — Copulas absent, but expressible by user definitions that typecheck.**
`PROB.COPULA` is LOW; a checked definition sketch exists; composition tests pass
with the library form. All four LIBRARY-NOT-CORE conditions hold. →
**LIBRARY-NOT-CORE**, reported separately, not counted as a severity finding and
not counted as core support.

**B8 — Conditional expectation given a sigma-algebra absent, and the claimed
workaround is "the user can define it".**
`PROB.CONDITIONING_ON_SIGMA_ALGEBRA` requires `ANA.SIGMA_ALGEBRA` as a
representable object. If sigma-algebras are themselves unrepresentable, condition
1 of LIBRARY-NOT-CORE fails (a core change is required). Atom criticality is
MEDIUM, mode `ABSENT`. → **MEDIUM**, and explicitly *not* LIBRARY-NOT-CORE. The
boundary: a library can add definitions, it cannot add a missing type former.

**B9 — The system rejects `1 m + 1 s`.**
This is `REJECTED_CORRECT`, a *pass*, not a finding. Recorded as evidence for
metaphysical adequacy. No severity assigned. Included here because
reject-behaviour is easy to mis-log as a failure.

**B10 — The system rejects `∫₀¹ x² dx` because integration over an interval is
unimplemented, with a clear diagnostic.**
`ANA.INTEGRAL_DEFINITE` is CRITICAL, mode `SPURIOUS_REJECT` (the mathematics is
valid). Rule H-d fires, not C-a, because the system did not lie. → **HIGH**, and
the maturity ladder's criticality gate does *not* fire (that gate covers `0` and
`L(silent)`; a spurious reject is coded `0` only if no faithful encoding exists —
which here it does not, so in practice this pair is coded `0` and the gate does
fire). *Recording note:* when `SPURIOUS_REJECT` leaves no faithful encoding at
all, the coverage code is `0` and the CRITICAL rule C-a applies; `SPURIOUS_REJECT`
as a distinct, milder mode applies only when a faithful-but-awkward encoding
exists and only some valid inputs are refused. This distinction must be recorded
explicitly per finding.

**B11 — An approximate result printed with `=`.**
Atom `NUMER.APPROXIMATION_MARKER` is HIGH; the printed form asserts exact
equality where only approximate equality holds → `SILENT_WRONG`. Rule C-b fires
on the failure mode alone. → **CRITICAL**. This is the clearest illustration that
severity is not simply read off criticality.

**B12 — A capability present but reachable only through an undocumented internal
API.**
Not `EXTERNAL_ONLY` (the semantics is inside the system) but not usable as
represented. Coded `C` with a `composition_cost` penalty, finding severity
**MEDIUM** under M-e if diagnostics suffer, otherwise **LOW** under L-c.

---

## 5. Aggregation: an aggregate must never hide a critical zero

This is the binding rule of the whole rubric.

**5.1 No masking.** No aggregate score — coverage percentage, weighted
completeness, density mean, maturity level, or any composite — may be reported in
a form that permits a CRITICAL finding to be offset by strength elsewhere.

**5.2 Mandatory adjacency.** Every reported aggregate carries, in the same visual
unit (same table row, same summary block, same JSON object), the fields:

```json
{
  "score": 0.82,
  "critical_findings": 3,
  "critical_atom_ids": ["LOGIC.NESTED_QUANTIFIER_ORDER",
                        "PROB.DISTRIBUTED_AS",
                        "XFORM.CANONICALIZATION"],
  "unknown_count": 11,
  "provisional": true
}
```

A score published without `critical_findings` is a specification violation, not a
formatting choice.

**5.3 Score ceiling.** Any aggregate for a system with `critical_findings > 0` is
reported as `min(score, 0.60)` **with the unclipped value shown alongside**, so
that the clipping is visible and reversible by the reader:

```
weighted completeness: 0.60 (capped; raw 0.82; 3 CRITICAL findings)
```

The cap exists so that a headline number cannot be quoted out of context in a way
that survives the loss of the surrounding table.

**5.4 Verdict vocabulary.** Systems with any CRITICAL finding are described using
the fixed phrase **"not sound for general use in the affected areas"**, naming the
areas. Phrases implying overall adequacy ("broadly complete", "production ready",
"comprehensive") are prohibited for such systems regardless of other scores.

**5.5 Critical findings are enumerated first.** In any report section about a
system, CRITICAL findings appear before aggregates, not after. Ordering is part of
the specification because reading order determines what a reader takes away.

**5.6 Zero-suppression is prohibited.** A domain with zero coverage is shown as a
row with `0.00`, never omitted for brevity. Omission reads as absence of a
problem.

**5.7 Unknowns are not favourable.** `?` never counts as support in any
aggregate, and the `?` count travels with every figure. A mostly-unprobed system
is reported as unprobed, not as passing.

**5.8 Severity counts are reported as a vector.**
`(CRITICAL, HIGH, MEDIUM, LOW, LIBRARY-NOT-CORE, UNKNOWN)` — always all six,
always in this order, never summed into a single "issue count", because summing
would let twenty LOW findings appear equivalent to one CRITICAL.

---

## 6. Review checklist for each finding

Before a finding is admitted to the report:

- [ ] The atom id is named and its criticality quoted from the ontology.
- [ ] The failure mode is one of the eight in §2 and is justified in one line.
- [ ] The probe source and the verbatim system response are stored.
- [ ] The severity rule that fired (C-a … L-d, or LIBRARY-NOT-CORE) is cited by id.
- [ ] For LIBRARY-NOT-CORE: the checked definition sketch is attached.
- [ ] If the finding is CRITICAL, the affected aggregates are annotated per §5.
- [ ] If the classification is disputed, both readings and their score effects are
      recorded rather than one being chosen silently.
