"""One executed probe for every CRITICAL atom in MATHEMATICAL_REASONING_ONTOLOGY_V1.

Why only the critical atoms get exhaustive treatment
----------------------------------------------------
The ontology holds 423 atoms. Writing a faithful HML specimen for each is not the best use
of effort, and a coverage percentage over all 423 would mostly measure how many probes
someone bothered to write. The 58 CRITICAL atoms are different: the severity rubric defines
CRITICAL as "a language lacking it cannot faithfully represent a broad, important class of
mathematics", and the mission requires that no aggregate hide a critical zero. So every
critical atom is probed, and CRITICAL coverage is reported as its own number.

Each probe is tagged with the exact ontology id so `build_coverage.py` joins on it directly
rather than by fuzzy string matching.

Fairness rule applied throughout: where HML has an idiom for the concept, the probe uses
HML's idiom rather than a foreign spelling. A probe must fail because the language cannot
express the mathematics, never because the audit guessed the syntax wrong.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hml_probe import Probe, emit, run_all, summarise  # noqa: E402

M = "module M\n"

#: ontology_id -> (hml source, mode, note)
SPECS: dict[str, tuple[str, str, str]] = {
    # ---- A. FOUNDATIONS / LOGIC ----
    "LOGIC.PROPOSITION": (M + "var p : Proposition\nrequire p", "accept", "Proposition is a type"),
    "LOGIC.NEGATION": (M + "var x : Real\nrequire not (x > 0.0)", "accept", ""),
    "LOGIC.CONJUNCTION": (M + "var x : Real\nrequire x > 0.0 and x < 1.0", "accept", ""),
    "LOGIC.DISJUNCTION": (M + "var x : Real\nrequire x > 0.0 or x < 1.0", "accept", ""),
    "LOGIC.IMPLICATION": (M + "var x : Real\nrequire x > 1.0 => x > 0.0", "accept", ""),
    "LOGIC.PREDICATE": (M + "var P : Predicate[Real]\nrequire forall x : Real . P(x)", "accept", ""),
    "LOGIC.FORALL": (M + "require forall x : Real . x = x", "accept", ""),
    "LOGIC.EXISTS": (M + "require exists x : Real . x = x", "accept", ""),
    "LOGIC.NESTED_QUANTIFIER_ORDER": (
        M + "require forall x : Real . exists y : Real . y > x", "accept",
        "order sensitivity separately verified by content hash",
    ),
    "LOGIC.VARIABLE_BINDING": (M + "require forall x : Real . x = x", "accept", ""),
    "LOGIC.FREE_VS_BOUND": (
        M + "var y : Real\nrequire forall x : Real . x = y", "accept",
        "x bound, y free in the same proposition",
    ),
    "LOGIC.SUBSTITUTION": (
        M + "var x : Real\ndef f(u : Real) : Real := u * u\nrequire f(x) = x * x", "accept",
        "substitution via application; there is no substitution STATEMENT",
    ),
    "LOGIC.EQUALITY": (M + "var x : Real\nrequire x = x", "accept", ""),
    "LOGIC.DEFINITIONAL_EQUALITY": (
        M + "const c : Real = 2.0\ndef d := c + 1.0", "accept",
        ":= definition vs = assertion are distinct forms",
    ),
    "LOGIC.SET_MEMBERSHIP": (M + "var S : Set[Real]\nvar x : Real\nrequire x in S", "observe", ""),
    "LOGIC.SET_COMPREHENSION": (
        M + "var S : Set[Real]\ndef T := { x : Real . x > 0.0 }", "observe", ""
    ),
    "LOGIC.INDEXED_FAMILY": (M + "index i : Natural\nvar x : Real", "observe", ""),
    "LOGIC.FUNCTION_AS_OBJECT": (
        M + "var f : Function[Real -> Real]\nrequire f = f", "accept", ""
    ),
    "LOGIC.APPLICATION": (
        M + "def f(u : Real) : Real := u * u\nrequire f(2.0) = 4.0", "accept", ""
    ),
    "LOGIC.TYPE_JUDGEMENT": (M + "var x : Real", "accept", "x : T is the declaration form"),
    "LOGIC.THEOREM_STATEMENT": (
        M + "prove forall x : Real . x > 0.0 => x >= 0.0", "accept",
        "statable; NOT provable -- see C-6",
    ),
    # ---- B. NUMBER SYSTEMS ----
    "NUM.NATURAL": (M + "const n : Natural = 3", "accept", ""),
    "NUM.INTEGER": (M + "const n : Integer = -3", "accept", ""),
    "NUM.REAL": (M + "const x : Real = 1.5", "accept", ""),
    "NUM.ORDER_RELATION": (M + "var x : Real\nrequire x <= x", "accept", ""),
    "NUM.VECTOR_OF_SCALARS": (M + "var v : Vector[Real, 3]\nrequire v = v", "accept", ""),
    # ---- C. ALGEBRA ----
    "ALG.SYMBOLIC_VARIABLE": (M + "var x : Real", "accept", "unbound indeterminate"),
    "ALG.EQUATION": (M + "var x : Real\nrequire x + 1.0 = 2.0", "accept", ""),
    "ALG.INEQUALITY": (M + "var x : Real\nrequire x + 1.0 > 2.0", "accept", ""),
    "ALG.MATRIX": (M + "var A : Matrix[Real, 3, 3]\nrequire A = A", "accept", ""),
    "ALG.MATRIX_SHAPE_TYPING": (
        M + "var A : Matrix[Real, 2, 3]\nvar B : Matrix[Real, 2, 3]\ndef C := A @ B",
        "reject", "non-conformable product must be rejected",
    ),
    "ALG.MATRIX_ARITHMETIC": (
        M + "var A : Matrix[Real, 3, 3]\nvar B : Matrix[Real, 3, 3]\ndef C := A @ B\ndef D := A + B",
        "accept", "",
    ),
    # ---- D. ANALYSIS ----
    "ANA.DOMAIN_CODOMAIN": (
        M + "var f : Function[Real -> NonNegativeReal]\nrequire f = f", "accept", ""
    ),
    "ANA.FUNCTION_REAL": (M + "def f(u : Real) : Real := u * u", "accept", ""),
    "ANA.LIMIT": (M + "var f : Function[Real -> Real]\ndef l := limit(f, 0.0)", "observe", ""),
    "ANA.CONTINUITY": (
        M + "var f : Function[Real -> Real]\nrequire continuous(f)", "observe", ""
    ),
    "ANA.DERIVATIVE": (
        M + "var f : Function[Real -> Real]\ndef d := derivative(f, x)", "observe", ""
    ),
    "ANA.INTEGRAL_DEFINITE": (
        M + "var f : Function[Real -> Real]\ndef a := integral(f, x, 0.0, 1.0)", "observe", ""
    ),
    # ---- E. PROBABILITY ----
    "PROB.PROBABILITY_MEASURE": (
        M + "var P : Function[Set[Real] -> Probability]\nrequire P = P", "observe",
        "no primitive probability space; encoded as a set function",
    ),
    "PROB.RANDOM_VARIABLE": (M + "rv X : RandomVariable[Real]\nrequire X = X", "accept", ""),
    "PROB.DISTRIBUTION_OBJECT": (
        M + "def d : Distribution[Real] := Normal(location := 0.0, scale := 1.0)",
        "accept", "distribution as a first-class value",
    ),
    "PROB.DISTRIBUTED_AS": (
        M + "rv X : RandomVariable[Real]\nlaw X ~ Normal(location := 0.0, scale := 1.0)",
        "accept", "",
    ),
    "PROB.EXPECTATION": (
        M + "rv X : RandomVariable[Real]\nrequire E[X] = 0.0", "observe",
        "expectation as a TERM; `infer expectation X` exists as a statement",
    ),
    "PROB.JOINT": (
        M + "rv X : RandomVariable[Real]\nrv Y : RandomVariable[Real]\n"
        "law X ~ Normal(location := 0.0, scale := 1.0)\n"
        "law Y ~ Normal(location := 0.0, scale := 1.0)\nrequire joint(X, Y) = joint(X, Y)",
        "observe", "",
    ),
    "PROB.CONDITIONAL_PROBABILITY": (
        M + "var A : Proposition\nvar B : Proposition\nrequire Pr(A | B) = 0.5", "observe", ""
    ),
    "PROB.CONDITIONAL_DISTRIBUTION": (
        M + "param t : Probability\nrv X : RandomVariable[Bool]\n"
        "likelihood X | t ~ Bernoulli(prob := t)", "accept",
        "conditional law via the `|` given-list -- HML's own idiom",
    ),
    "PROB.INDEPENDENCE": (
        M + "rv X : RandomVariable[Real]\nrv Y : RandomVariable[Real]\n"
        "require independent(X, Y)", "observe", ""
    ),
    "PROB.INDEXED_FAMILY_RV": (
        M + "index i : Natural\nrv X : RandomVariable[Real]\n"
        "law X ~ Normal(location := 0.0, scale := 1.0)", "observe",
        "no way to say X_i depends on i",
    ),
    "PROB.FUNCTION_RETURNING_DISTRIBUTION": (
        M + "def kern(s : PositiveReal) : Distribution[Real] := "
        "Normal(location := 0.0, scale := s)", "accept", "Markov kernel",
    ),
    # ---- F. STATISTICS ----
    "STAT.POPULATION_VS_SAMPLE": (
        M + "param theta : Real\nobs y : Real = 1.0", "accept",
        "param vs obs is a genuine population/sample distinction",
    ),
    "STAT.ESTIMATOR": (
        M + "obs y : Real = 1.0\ndef theta_hat := y", "observe",
        "an estimator is a function OF DATA; no dataset type exists",
    ),
    "STAT.LIKELIHOOD_FUNCTION": (
        M + "param t : Probability\nobs y : Bool = true\n"
        "likelihood y | t ~ Bernoulli(prob := t)", "accept", "",
    ),
    # ---- G. DISCRETE ----
    "DISC.SUMMATION": (
        M + "index i : Natural\ndef s := sum(i, 1, 10, i)", "observe", ""
    ),
    # ---- I. OPTIMIZATION ----
    "OPT.DECISION_VARIABLE": (M + "param x : Real\ndef f := x * x\nminimise f", "accept", ""),
    "OPT.OBJECTIVE": (M + "param x : Real\ndef f := x * x\nminimise f", "accept", ""),
    "OPT.FEASIBLE_SET": (
        M + "param x : Real\nrequire x >= 0.0\ndef f := x * x\nminimise f", "observe",
        "is `require` scoped to the optimisation, or a global assertion?",
    ),
    "OPT.EQUALITY_CONSTRAINT": (
        M + "param x : Real\nparam y : Real\nrequire x + y = 1.0\ndef f := x * x\nminimise f",
        "observe", "",
    ),
    "OPT.INEQUALITY_CONSTRAINT": (
        M + "param x : Real\nrequire x >= 0.0\ndef f := x * x\nminimise f", "observe", ""
    ),
    # ---- L. REASONING / EPISTEMICS and M. TRANSFORMATIONS ----
    "EPIS.ASSERTION_VS_DEFINITION": (
        M + "const c : Real = 2.0\nvar x : Real\nrequire x = 3.0", "accept",
        "def/const := is definition; require = is assertion. Distinct statement forms.",
    ),
    "EPIS.ASSUMPTION": (
        M + "var x : Real\nassume x > 0.0", "accept",
        "expressible; NOT enforced -- does not discharge a domain restriction (C-1)",
    ),
    "EPIS.CONSISTENCY_CHECK": (
        M + "var x : Real\nrequire y > 0.0", "reject",
        "an undeclared symbol must be rejected",
    ),
    "EPIS.CORRELATION_VS_CAUSATION": (
        M + "var x : Real\nvar y : Real\nrequire x causes y", "observe",
        "the project forbids conflating implication with causation; is causation SAYABLE?",
    ),
    "XFORM.CANONICALIZATION": (
        M + "require forall x : Real . exists y : Real . y > x", "accept",
        "canonical form exists; order-sensitivity checked separately by content hash",
    ),
    "XFORM.TYPE_INFERENCE": (
        M + "param mu : Real\nparam sigma : PositiveReal\nvar z : Real\n"
        "def v := mu + sigma * z", "accept",
        "inferred type of a compound expression",
    ),
}


PROBES = [
    Probe(
        id=oid,
        group="critical_atom",
        capability=oid,
        source=src,
        expectation=note or f"critical ontology atom {oid}",
        mode=mode,
        notes=note,
    )
    for oid, (src, mode, note) in SPECS.items()
]


def main() -> int:
    results = run_all(PROBES)
    out = Path(__file__).resolve().parents[1] / "matrices" / "HML_CRITICAL_ATOM_PROBES.json"
    emit(results, out)
    for r in results:
        flag = "" if r.ok else "  <-- not accepted"
        print(
            f"{r.probe.id:40s} {r.verdict:9s} ok={str(r.ok):5s} "
            f"{','.join(r.codes) if r.codes else 'clean':28s}{flag}"
        )
    s = summarise(results)
    print(f"\n{s['by_verdict']}")
    accepted = sum(1 for r in results if r.ok)
    print(f"compiles clean: {accepted}/{len(results)}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
