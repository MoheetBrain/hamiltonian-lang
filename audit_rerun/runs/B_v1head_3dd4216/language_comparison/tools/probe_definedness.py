"""Definedness / partiality audit for HML (mission section 10).

The question this answers
-------------------------
Every one of these operations is a *partial function*. A language that claims to be a
mathematical reasoning IR has to do something principled when one appears:

* generate a side condition (`x != 0`) as a proof obligation, or
* infer a domain restriction from the declared type, or
* reject the expression, or
* totalise it (define `1/0 = 0`, as Lean and Coq do), or
* delegate to a runtime NaN/Inf, which is the option that loses the mathematics.

Silently producing a well-typed program with an undefined subterm is the failure mode
that matters, because the resulting object *looks* verified.

Each probe below is written so that the only interesting variable is the partial
operation. Nothing here modifies HML; a probe that reveals a gap is the deliverable.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hml_probe import Probe, emit, run_all, summarise  # noqa: E402

G = "definedness"

PROBES: list[Probe] = [
    Probe(
        id="DEF.DIV.LITERAL_ZERO",
        group=G,
        capability="NUM.DIVISION / DEFINEDNESS.DIVISION_BY_ZERO",
        source="module M\nconst x : Real = 1.0 / 0.0",
        expectation=(
            "Division by a literal zero is undefined. An adequate system rejects it or "
            "records an unsatisfiable side condition; it must not accept silently."
        ),
        mode="observe",
    ),
    Probe(
        id="DEF.DIV.UNCONSTRAINED_VAR",
        group=G,
        capability="DEFINEDNESS.DIVISION_BY_ZERO",
        source="module M\nvar x : Real\ndef y := 1.0 / x",
        expectation=(
            "1/x with x : Real unconstrained requires the side condition x != 0. Ideally "
            "a proof obligation is emitted."
        ),
        mode="observe",
    ),
    Probe(
        id="DEF.DIV.GUARDED_BY_ASSUME",
        group=G,
        capability="DEFINEDNESS.DISCHARGE_BY_ASSUMPTION",
        source="module M\nvar x : Real\nassume x != 0\ndef y := 1.0 / x",
        expectation=(
            "An explicit assumption should discharge the side condition. Tests whether "
            "assumptions participate in definedness at all."
        ),
        mode="observe",
    ),
    Probe(
        id="DEF.DIV.GUARDED_BY_TYPE",
        group=G,
        capability="DEFINEDNESS.DOMAIN_FROM_TYPE",
        source="module M\nvar x : PositiveReal\ndef y := 1.0 / x",
        expectation=(
            "x : PositiveReal makes 1/x total. If the system reports the same thing here "
            "as for unconstrained Real, the refinement type is not doing definedness work."
        ),
        mode="observe",
    ),
    Probe(
        id="DEF.SQRT.NEGATIVE_DOMAIN",
        group=G,
        capability="DEFINEDNESS.SQRT",
        source="module M\nvar x : Real\ndef y := sqrt(x)",
        expectation="sqrt over unconstrained Real needs x >= 0 (or a complex codomain).",
        mode="observe",
    ),
    Probe(
        id="DEF.LOG.NONPOSITIVE",
        group=G,
        capability="DEFINEDNESS.LOG",
        source="module M\nvar x : Real\ndef y := log(x)",
        expectation="log needs x > 0.",
        mode="observe",
    ),
    Probe(
        id="DEF.POW.ZERO_NEGATIVE",
        group=G,
        capability="DEFINEDNESS.POWER",
        source="module M\nconst y : Real = 0.0 ^ -1.0",
        expectation="0^(-1) is undefined.",
        mode="observe",
    ),
    Probe(
        id="DEF.TAN.POLE",
        group=G,
        capability="DEFINEDNESS.TAN",
        source="module M\nvar x : Real\ndef y := tan(x)",
        expectation=(
            "tan has poles at pi/2 + k*pi. The builtin table types it (Real,) -> Real, so "
            "the poles are unmodelled -- inconsistent with sqrt/log, which ARE domain-restricted."
        ),
        mode="observe",
    ),
    Probe(
        id="DEF.MATRIX.INVERSE",
        group=G,
        capability="ALG.MATRIX.INVERSE / DEFINEDNESS.SINGULAR",
        source="module M\nvar A : Matrix[Real, 3, 3]\ndef B := inverse(A)",
        expectation="Matrix inversion requires non-singularity (det A != 0).",
        mode="observe",
    ),
    Probe(
        id="DEF.MATRIX.SHAPE_MISMATCH",
        group=G,
        capability="ALG.MATRIX.PRODUCT / TYPE.SHAPE",
        source=(
            "module M\nvar A : Matrix[Real, 2, 3]\nvar B : Matrix[Real, 2, 3]\n"
            "def C := A @ B"
        ),
        expectation=(
            "A 2x3 @ 2x3 product is undefined. A shape-aware type system MUST reject this. "
            "This is the single clearest test of whether Matrix dimensions are checked."
        ),
        mode="reject",
    ),
    Probe(
        id="DEF.MATRIX.SHAPE_OK",
        group=G,
        capability="ALG.MATRIX.PRODUCT",
        source=(
            "module M\nvar A : Matrix[Real, 2, 3]\nvar B : Matrix[Real, 3, 4]\n"
            "def C := A @ B"
        ),
        expectation="A conformable product must be accepted (control for the probe above).",
        mode="accept",
    ),
    Probe(
        id="DEF.COND_PROB.ZERO_CONDITION",
        group=G,
        capability="PROB.CONDITIONAL / DEFINEDNESS.CONDITIONING",
        source=(
            "module M\nparam p : Probability\nassume p = 0.0\n"
            "rv X : RandomVariable[Real]\nlikelihood X | p ~ Bernoulli(prob := p)"
        ),
        expectation=(
            "Conditioning on a probability-zero event is undefined without a density "
            "argument. Tests whether conditioning carries any definedness side condition."
        ),
        mode="observe",
    ),
    Probe(
        id="DEF.EMPTY_DOMAIN.QUANTIFIER",
        group=G,
        capability="LOGIC.VACUOUS_TRUTH",
        source="module M\nrequire forall x : PositiveNatural . x > 1000000",
        expectation=(
            "Not empty-domain, but tests whether a plainly false universal is accepted "
            "as a requirement without complaint."
        ),
        mode="observe",
    ),
    Probe(
        id="DEF.DIMENSION.ADD_MISMATCH",
        group=G,
        capability="SCI.DIMENSIONAL_EQUALITY",
        source=(
            "module M\nparam a : Quantity[Length]\n"
            "param b : Quantity[Time]\ndef c := a + b"
        ),
        expectation=(
            "Adding a length to a time is dimensionally invalid and MUST be rejected. "
            "This is the flagship claim of a dimension system."
        ),
        mode="reject",
    ),
    Probe(
        id="DEF.DIMENSION.MUL_OK",
        group=G,
        capability="SCI.DIMENSIONAL_ALGEBRA",
        source=(
            "module M\nparam a : Quantity[Length]\n"
            "param b : Quantity[Time]\ndef c := a / b"
        ),
        expectation="Length/Time is well formed and should yield a velocity dimension.",
        mode="accept",
    ),
    Probe(
        id="DEF.PROB.OUT_OF_RANGE_LITERAL",
        group=G,
        capability="NUM.REFINEMENT.PROBABILITY",
        source="module M\nconst p : Probability = 1.5",
        expectation=(
            "1.5 is not a probability. The spec says literals are checked by VALUE against "
            "refinements (D-009), so this must be rejected."
        ),
        mode="reject",
    ),
    Probe(
        id="DEF.PROB.IN_RANGE_LITERAL",
        group=G,
        capability="NUM.REFINEMENT.PROBABILITY",
        source="module M\nconst p : Probability = 1",
        expectation="The spec explicitly states this is well typed (D-009). Control probe.",
        mode="accept",
    ),
    Probe(
        id="DEF.NEGATIVE_INTO_NATURAL",
        group=G,
        capability="NUM.REFINEMENT.NATURAL",
        source="module M\nconst n : Natural = -3",
        expectation="A negative literal is not a Natural.",
        mode="reject",
    ),
    Probe(
        id="DEF.INDEX.OUT_OF_RANGE",
        group=G,
        capability="ALG.INDEXING / DEFINEDNESS.INDEX",
        source="module M\nvar v : Vector[Real, 3]\ndef y := v[10]",
        expectation="Index 10 into a length-3 vector is out of range and statically known.",
        mode="observe",
    ),
]


def main() -> int:
    results = run_all(PROBES)
    out = Path(__file__).resolve().parents[1] / "matrices" / "HML_DEFINEDNESS_PROBES.json"
    emit(results, out)
    print(f"{'PROBE':38s} {'VERDICT':9s} {'OK':5s} CODES")
    print("-" * 100)
    for r in results:
        print(
            f"{r.probe.id:38s} {r.verdict:9s} {str(r.ok):5s} "
            f"{','.join(r.codes) if r.codes else '(none)'}"
        )
    s = summarise(results)
    print(f"\n{s['by_verdict']}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
