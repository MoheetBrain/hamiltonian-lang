"""Apply the idiom corrections to the D_after_idiom and E_v1head_idiom probe copies.

Every replacement below is reproduced verbatim in docs/hml_v2/AUDIT_RERUN.md under
"PROBE CHANGES".  The same corrected probes are applied to BOTH the V2 tree and the v1
baseline tree, so that any atom that passes only after correction can be attributed to
the language change rather than to the correction.

Nothing in ontology/ is touched.  No denominator changes: the same 64 critical atoms and
the same 13 composition specimens are probed.
"""

from __future__ import annotations

import pathlib
import sys

RUNS = pathlib.Path(__file__).resolve().parent / "runs"
LABELS = ("D_after_idiom", "E_v1head_idiom")

# (file, old fragment, new fragment, probe id, justification)
CHANGES: list[tuple[str, str, str, str, str]] = [
    # ---------------- critical-atom suite ----------------
    (
        "probe_critical_atoms.py",
        'M + "var S : Set[Real]\\ndef T := { x : Real . x > 0.0 }", "observe", ""',
        'M + "var S : Set[Real]\\ndef T := { x : Real | x > 0.0 }", "observe", ""',
        "LOGIC.SET_COMPREHENSION",
        "separator is '|' not '.' (EXPRESSION_COVERAGE.md 1). The '.' spelling parsed in "
        "neither v1 nor v2; it was the audit's guess.",
    ),
    (
        "probe_critical_atoms.py",
        'M + "var f : Function[Real -> Real]\\ndef l := limit(f, 0.0)", "observe", ""',
        'M + "var f : Function[Real -> Real]\\ndef l := limit(f(x), x : Real -> 0.0)", '
        '"observe", ""',
        "ANA.LIMIT",
        "v2 limit binds an explicitly typed variable and takes an expression body: "
        "limit(<expr>, <name> : <T> -> <point>).",
    ),
    (
        "probe_critical_atoms.py",
        'M + "var f : Function[Real -> Real]\\nrequire continuous(f)", "observe", ""',
        'M + "var f : Function[Real -> Real]\\nvar D : Set[Real]\\n'
        'require continuous(f, on := D)", "observe", ""',
        "ANA.CONTINUITY",
        "continuity in v2 requires the domain, with the role label 'on' (D-003 rationale).",
    ),
    (
        "probe_critical_atoms.py",
        'M + "var f : Function[Real -> Real]\\ndef d := derivative(f, x)", "observe", ""',
        'M + "var f : Function[Real -> Real]\\ndef d := derivative(f(x), x : Real)", '
        '"observe", ""',
        "ANA.DERIVATIVE",
        "typed binder. NOTE the original probe referenced an undeclared 'x' and was "
        "ill-formed under v1 as well (HML-N301).",
    ),
    (
        "probe_critical_atoms.py",
        'M + "var f : Function[Real -> Real]\\ndef a := integral(f, x, 0.0, 1.0)", "observe", ""',
        'M + "var f : Function[Real -> Real]\\ndef a := integral(f(x), x : Real, 0.0, 1.0)", '
        '"observe", ""',
        "ANA.INTEGRAL_DEFINITE",
        "typed binder; same undeclared-'x' defect in the original.",
    ),
    (
        "probe_critical_atoms.py",
        'M + "rv X : RandomVariable[Real]\\nrequire E[X] = 0.0", "observe",',
        'M + "rv X : RandomVariable[Real]\\nrequire expectation(X) = 0.0", "observe",',
        "PROB.EXPECTATION",
        "D-026 chose expectation(...) as the primary surface over E[...]; E[...] collides "
        "with indexing and 'E' must stay usable as a value name.",
    ),
    (
        "probe_critical_atoms.py",
        '"law Y ~ Normal(location := 0.0, scale := 1.0)\\nrequire joint(X, Y) = joint(X, Y)"',
        '"law Y ~ Normal(location := 0.0, scale := 1.0)\\ndef j := joint(X, Y)"',
        "PROB.JOINT",
        "joint(X, Y) is a Distribution. Comparing two laws with '=' is refused by the "
        "pre-existing HML-T428 barrier, which the project's own contract requires. The "
        "'= itself' was an inert well-formedness filler; 'def' keeps the intent.",
    ),
    (
        "probe_critical_atoms.py",
        'M + "var A : Proposition\\nvar B : Proposition\\nrequire Pr(A | B) = 0.5", "observe", ""',
        'M + "var A : Event\\nvar B : Event\\nrequire probability(A | B) = 0.5", "observe", ""',
        "PROB.CONDITIONAL_PROBABILITY",
        "TWO changes: spelling Pr -> probability, AND the declared type Proposition -> "
        "Event. The second is the aggressive one: v2 makes Event and Proposition "
        "incomparable on purpose (EXPRESSION_COVERAGE.md 3), so probability() of a "
        "Proposition is refused by design (HML-T482).",
    ),
    (
        "probe_critical_atoms.py",
        'M + "var x : Real\\nvar y : Real\\nrequire x causes y", "observe",',
        'M + "rv X : RandomVariable[Real]\\nrv Y : RandomVariable[Real]\\n'
        'require causes(X, Y)", "observe",',
        "EPIS.CORRELATION_VS_CAUSATION",
        "TWO changes: infix -> prefix, AND the operands become random variables. v2 "
        "refuses a causal relation between constants (HML-T495).",
    ),
    (
        "probe_critical_atoms.py",
        '"PROB.RANDOM_VARIABLE": (M + "rv X : RandomVariable[Real]\\nrequire X = X", "accept", "")',
        '"PROB.RANDOM_VARIABLE": (M + "rv X : RandomVariable[Real]\\n'
        'require probability(X = X) = 1.0", "accept", "")',
        "PROB.RANDOM_VARIABLE",
        "REGRESSION REPAIR. v2 types 'X = X' between random variables as an Event and "
        "'require' refuses events (HML-T480). This is the documented barrier of "
        "EXPRESSION_COVERAGE.md 3, not an accident. The unmodified probe is reported too.",
    ),
    # ---------------- composition suite ----------------
    (
        "probe_composition.py",
        '"module M\\nrv S : RandomVariable[Matrix[Real, 3, 3]]\\n"\n            "require S = S"',
        '"module M\\nrv S : RandomVariable[Matrix[Real, 3, 3]]\\n"\n            '
        '"require probability(S = S) = 1.0"',
        "COMP.MATRIX_VALUED_RV",
        "REGRESSION REPAIR, same Event barrier. This one moves the compositional-closure "
        "number, so it is the single most consequential correction in this file.",
    ),
    (
        "probe_composition.py",
        '"module M\\nrv W : RandomVariable[Function[Real -> Real]]\\nrequire W = W"',
        '"module M\\nrv W : RandomVariable[Function[Real -> Real]]\\n'
        'require probability(W = W) = 1.0"',
        "RT.STOCHASTIC_PROCESS",
        "REGRESSION REPAIR, same Event barrier. Red-team group; not in any headline "
        "denominator.",
    ),
    (
        "probe_composition.py",
        '"module M\\nrv X : RandomVariable[Real]\\nparam t : Probability\\n"\n            '
        '"require E[X | t] = t"',
        '"module M\\nrv X : RandomVariable[Real]\\nparam t : Probability\\n"\n            '
        '"require expectation(X | t) = t"',
        "RT.CONDITIONAL_EXPECTATION",
        "E[...] -> expectation(...). Red-team group.",
    ),
    (
        "probe_composition.py",
        'source="module M\\nvar f : Function[Real -> Real]\\ndef a := integral(f, 0.0, 1.0)"',
        'source="module M\\nvar f : Function[Real -> Real]\\n'
        'def a := integral(f(x), x : Real, 0.0, 1.0)"',
        "RT.INTEGRAL",
        "typed binder. Red-team group.",
    ),
    (
        "probe_composition.py",
        'source="module M\\nvar f : Function[Real -> Real]\\ndef d := derivative(f)"',
        'source="module M\\nvar f : Function[Real -> Real]\\n'
        'def d := derivative(f(x), x : Real)"',
        "RT.DERIVATIVE",
        "typed binder. Red-team group.",
    ),
    (
        "probe_composition.py",
        'source="module M\\nvar f : Function[Real -> Real]\\ndef l := limit(f, 0.0)"',
        'source="module M\\nvar f : Function[Real -> Real]\\n'
        'def l := limit(f(x), x : Real -> 0.0)"',
        "RT.LIMIT",
        "typed binder. Red-team group.",
    ),
    (
        "probe_composition.py",
        '"module M\\nrv X : RandomVariable[Real]\\nrv Y : RandomVariable[Real]\\n"\n            '
        '"require E[X | Y] = Y"',
        '"module M\\nrv X : RandomVariable[Real]\\nrv Y : RandomVariable[Real]\\n"\n            '
        '"def m := expectation(X | Y)"',
        "RT.SIGMA_ALGEBRA_CONDITIONING",
        "E[X|Y] -> expectation(X|Y); and E[X|Y] is a RandomVariable in v2, so '= Y' forms "
        "an Event that 'require' refuses. Red-team group.",
    ),
]


def main() -> int:
    for label in LABELS:
        base = RUNS / label / "language_comparison" / "tools"
        for fname, old, new, pid, _why in CHANGES:
            p = base / fname
            t = p.read_text()
            if old not in t:
                print(f"FAILED to locate fragment for {pid} in {label}/{fname}")
                return 1
            if t.count(old) != 1:
                print(f"AMBIGUOUS fragment for {pid} in {label}/{fname}: {t.count(old)} hits")
                return 1
            p.write_text(t.replace(old, new))
        print(f"{label}: applied {len(CHANGES)} corrections")
    return 0


if __name__ == "__main__":
    sys.exit(main())
