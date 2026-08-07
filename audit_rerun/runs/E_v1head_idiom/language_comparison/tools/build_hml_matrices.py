"""Emit the epistemic-state and transformation-capability matrices for HML.

Both are required deliverables (mission sections 11 and 12) and both are HML-specific, so
they are built here from executed probe evidence rather than from the genome's static read.

The two matrices answer different questions and are kept apart deliberately:

* **Epistemic states** — can the language *say* "this is assumed" as opposed to "this is
  derived", and does anything *check* it? A syntax-only epistemic system records an
  intention that nothing enforces, which is worth much less than it looks.
* **Transformations** — can the language represent an inference as a first-class object,
  with input state, rule, side conditions, output state and provenance? Section 12 requires
  REPRESENTABLE / EXECUTABLE / VERIFIABLE / PROVENANCE-PRESERVING to be scored separately,
  because they are different properties and a system can have the first without the rest.
"""

from __future__ import annotations

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "matrices"

# --------------------------------------------------------------------------
# Epistemic states. `enforced` is the load-bearing column.
# --------------------------------------------------------------------------
EPISTEMIC = [
    # state, expressible, syntax, enforced_by, evidence
    ("DECLARED", "YES", "var x : T", "type checker",
     "var x : Real compiles; type participates in checking"),
    ("DEFINED", "YES", "def d := e / const c : T = v", "type checker",
     "def/const distinguished from var in the AST and canonical form"),
    ("ASSUMED", "YES", "assume <prop>", "NOTHING",
     "assume x > 0.0 does NOT discharge log's PositiveReal domain (HML-T427); "
     "contradictory assumes compile clean"),
    ("REQUIRED", "YES", "require <prop>", "obligation recorded, discharged by nothing",
     "SPEC 9: 'v0 discharges none of them'"),
    ("OBSERVED", "YES", "obs n : T = v", "weak",
     "distinct declaration keyword; no downstream check found that treats obs "
     "differently from const"),
    ("PARAMETER", "YES", "param p : T", "YES",
     "infer posterior on a symbol with no law -> HML-S604"),
    ("GOAL / PROOF_OBLIGATION", "YES", "prove <prop>", "NOTHING",
     "prove 1 = 2 compiles clean, zero diagnostics"),
    ("OBJECTIVE", "YES", "minimise / maximise <expr>", "YES",
     "objective over a derived quantity compiles; distinct statement form"),
    ("CONJECTURED", "NO", "-", "-", "conjecture ... -> HML-P205"),
    ("REFUTED", "NO", "-", "-", "refute ... -> HML-P205"),
    ("APPROXIMATE", "NO", "-", "-", "~= -> HML-P204; ~ is reserved for law"),
    ("UNCERTAIN", "NO", "-", "-",
     "9.81 +- 0.02 silently parses as 9.81 + (-0.02); no uncertainty semantics"),
    ("PROHIBITED_ASSUMPTION", "NO", "-", "-", "prohibit ... -> HML-P205"),
]

# --------------------------------------------------------------------------
# Transformations. Section 12's four properties scored separately.
# --------------------------------------------------------------------------
TRANSFORMS = [
    "substitution", "rewrite", "simplify", "rearrange", "cancel", "factor", "expand",
    "differentiate", "integrate", "change of variables", "case split", "contradiction",
    "induction", "implication application", "equality substitution",
    "probability conditioning", "Bayesian update", "optimisation update", "approximation",
]

#: The surface grammar has no statement form meaning "from A, by rule R, infer B".
#: Verified against the full statement list in SPEC.md section 3 and against
#: Parser.parse_statement. The Python layer (improvement/, repair/, equivalence/) models
#: transformations, but `compile_source` never reaches it, so none of it is reachable from
#: a .hml file.
SURFACE_NOTE = (
    "no statement form in the surface grammar expresses an inference step; the "
    "improvement/repair/equivalence machinery is Python-only and unreachable from .hml"
)

EXCEPTIONS = {
    # The two things that ARE reachable from source, and what they actually are.
    "probability conditioning": (
        "PARTIAL", "likelihood t | g ~ D expresses a conditional LAW, not a conditioning STEP"
    ),
    "Bayesian update": (
        "PARTIAL", "infer posterior x REQUESTS an update; it does not represent one as an event"
    ),
    "optimisation update": (
        "PARTIAL", "minimise/maximise states an objective; no optimisation STEP is representable"
    ),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    p1 = OUT / "EPISTEMIC_STATE_MATRIX.csv"
    with p1.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["state", "expressible_in_HML", "hml_syntax", "enforced_by", "evidence"])
        w.writerows(EPISTEMIC)

    p2 = OUT / "TRANSFORMATION_CAPABILITY_MATRIX.csv"
    with p2.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["transformation", "representable", "executable", "verifiable",
             "provenance_preserving", "note"]
        )
        for t in TRANSFORMS:
            if t in EXCEPTIONS:
                status, note = EXCEPTIONS[t]
                w.writerow([t, status, "NO", "NO", "NO", note])
            else:
                w.writerow([t, "NO", "NO", "NO", "NO", SURFACE_NOTE])

    expressible = sum(1 for r in EPISTEMIC if r[1] == "YES")
    enforced = sum(1 for r in EPISTEMIC if r[3] not in {"NOTHING", "-", "weak"})
    representable = sum(1 for t in TRANSFORMS if t in EXCEPTIONS)

    print(f"EPISTEMIC:      {expressible}/{len(EPISTEMIC)} expressible, "
          f"{enforced}/{len(EPISTEMIC)} enforced in a load-bearing way")
    print(f"TRANSFORMATION: {representable}/{len(TRANSFORMS)} partially representable, "
          f"0/{len(TRANSFORMS)} fully representable, 0 executable, 0 verifiable, "
          f"0 provenance-preserving")
    print(f"-> {p1}\n-> {p2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
