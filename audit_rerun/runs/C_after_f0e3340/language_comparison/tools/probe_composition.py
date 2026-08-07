"""Compositional closure and red-team probes for HML (mission sections 9 and 26).

Feature checklists lie. A language can hold `forall` and `RandomVariable` and still be
unable to write "for every theta in (0,1), the conditional expectation of X given theta is
A(theta)x" — because the two features were built without reference to each other.
Compositional closure is where mathematical IRs actually fail, so it is measured directly
rather than inferred from the feature list.

Every probe is a composition of ontology atoms that ordinary mathematics combines freely.
A failure is classified by SOURCE, because "HML cannot express this" and "HML's grammar
cannot parse this particular spelling" are different findings with different remedies.

Nothing here modifies HML. The suite is adversarial by design: its purpose is to falsify
"HML is sufficiently expressive to serve as a general mathematical reasoning IR."
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hml_probe import Probe, emit, run_all, summarise  # noqa: E402

C = "composition"
R = "redteam"

PROBES: list[Probe] = [
    # ---------------- baseline controls: each feature ALONE ----------------
    Probe(
        id="BASE.QUANTIFIER_NESTED",
        group="baseline",
        capability="LOGIC.FORALL + LOGIC.EXISTS (order)",
        source="module M\nrequire forall x : Real . exists y : Real . y > x",
        expectation="Nested quantifiers alone. Documented as working.",
        mode="accept",
    ),
    Probe(
        id="BASE.RANDOM_VARIABLE",
        group="baseline",
        capability="PROB.RANDOM_VARIABLE",
        source="module M\nrv X : RandomVariable[Real]\nlaw X ~ Normal(location := 0.0, scale := 1.0)",
        expectation="A random variable with a law, alone.",
        mode="accept",
    ),
    Probe(
        id="BASE.MATRIX",
        group="baseline",
        capability="ALG.MATRIX",
        source="module M\nvar A : Matrix[Real, 3, 3]\nvar v : Vector[Real, 3]\ndef w := A @ v",
        expectation="Matrix-vector product alone.",
        mode="accept",
    ),
    Probe(
        id="BASE.QUANTITY",
        group="baseline",
        capability="SCI.PHYSICAL_QUANTITY",
        source="module M\nparam m : Quantity[Mass]\nparam v : Quantity[Length / Time]\ndef p := m * v",
        expectation="Dimensioned arithmetic alone.",
        mode="accept",
    ),
    # ---------------- pairwise compositions ----------------
    Probe(
        id="COMP.QUANT_X_PROB",
        group=C,
        capability="LOGIC.FORALL x PROB.RANDOM_VARIABLE",
        source=(
            "module M\nrv X : RandomVariable[Real]\n"
            "require forall t : Probability . X > 0.0"
        ),
        expectation=(
            "Quantifying a proposition that mentions a random variable. Ordinary in "
            "probability; tests whether RV terms may appear inside quantified propositions."
        ),
        mode="observe",
    ),
    Probe(
        id="COMP.QUANT_X_MATRIX",
        group=C,
        capability="LOGIC.FORALL x ALG.MATRIX",
        source=(
            "module M\nvar A : Matrix[Real, 3, 3]\n"
            "require forall v : Vector[Real, 3] . (A @ v) = (A @ v)"
        ),
        expectation="Quantifying over vectors with a matrix expression in the body.",
        mode="observe",
    ),
    Probe(
        id="COMP.QUANT_X_UNITS",
        group=C,
        capability="LOGIC.FORALL x SCI.PHYSICAL_QUANTITY",
        source=(
            "module M\nrequire forall d : Quantity[Length] . d >= d"
        ),
        expectation="Quantifying over a dimensioned domain.",
        mode="observe",
    ),
    Probe(
        id="COMP.PROB_X_UNITS",
        group=C,
        capability="PROB.RANDOM_VARIABLE x SCI.PHYSICAL_QUANTITY",
        source=(
            "module M\nrv H : RandomVariable[Quantity[Length]]\n"
            "law H ~ Normal(location := 1.0, scale := 0.1)"
        ),
        expectation=(
            "A dimensioned random variable -- a measured height in metres. Extremely "
            "common in scientific statistics. Tests whether RandomVariable composes with "
            "Quantity, and whether the law's parameters inherit the dimension."
        ),
        mode="observe",
    ),
    Probe(
        id="COMP.MATRIX_VALUED_RV",
        group=C,
        capability="PROB.RANDOM_VARIABLE x ALG.MATRIX",
        source=(
            "module M\nrv S : RandomVariable[Matrix[Real, 3, 3]]\n"
            "require S = S"
        ),
        expectation=(
            "A matrix-valued random variable (a random covariance matrix). Standard in "
            "multivariate statistics."
        ),
        mode="observe",
    ),
    Probe(
        id="COMP.INDEXED_RV_FAMILY",
        group=C,
        capability="PROB.RANDOM_VARIABLE x DISCRETE.INDEXED_FAMILY",
        source=(
            "module M\nindex i : Natural\nrv X : RandomVariable[Real]\n"
            "law X ~ Normal(location := 0.0, scale := 1.0)"
        ),
        expectation=(
            "An indexed family X_i -- the basis of every hierarchical model and every "
            "stochastic process. Tests whether `index` actually indexes anything."
        ),
        mode="observe",
    ),
    Probe(
        id="COMP.FUNCTION_RETURNING_DISTRIBUTION",
        group=C,
        capability="LOGIC.FUNCTION x PROB.DISTRIBUTION",
        source=(
            "module M\ndef prior_for(s : PositiveReal) : Distribution[Real] := "
            "Normal(location := 0.0, scale := s)"
        ),
        expectation=(
            "A function from a parameter to a distribution. This is what a prior IS in a "
            "hierarchical model. Tests first-class distributions."
        ),
        mode="observe",
    ),
    Probe(
        id="COMP.OBJECTIVE_OVER_DERIVED",
        group=C,
        capability="OPT.OBJECTIVE x EPISTEMIC.DERIVED",
        source=(
            "module M\nparam x : Real\ndef loss := x * x\nminimise loss"
        ),
        expectation="Minimising a derived quantity. The core of optimisation.",
        mode="observe",
    ),
    Probe(
        id="COMP.OBJECTIVE_OVER_PROBABILISTIC",
        group=C,
        capability="OPT.OBJECTIVE x PROB.EXPECTATION",
        source=(
            "module M\nparam t : Probability\nrv X : RandomVariable[Real]\n"
            "law X ~ Bernoulli(prob := t)\nmaximise t"
        ),
        expectation=(
            "Optimising with respect to a parameter that indexes a distribution -- MLE. "
            "Tests whether objectives and probabilistic structure interact at all."
        ),
        mode="observe",
    ),
    Probe(
        id="COMP.LOCAL_ASSUMPTION_IN_SCOPE",
        group=C,
        capability="EPISTEMIC.ASSUMED x BINDING.LOCAL_SCOPE",
        source=(
            "module M\nvar x : Real\nassume x > 0.0\nrequire log(x) = log(x)"
        ),
        expectation=(
            "Can an assumption discharge a domain restriction? log needs PositiveReal; "
            "x is Real with an assumption x > 0. If this fails, assumptions and the type "
            "system are disconnected -- a CRITICAL finding for a reasoning IR."
        ),
        mode="observe",
    ),
    Probe(
        id="COMP.TENSOR_IN_PROPOSITION",
        group=C,
        capability="ALG.TENSOR x LOGIC.PROPOSITION",
        source=(
            "module M\nvar T : Tensor[Real, 2, 3, 4]\nrequire T = T"
        ),
        expectation="A tensor inside a proposition.",
        mode="observe",
    ),
    Probe(
        id="COMP.QUANTIFY_OVER_FUNCTIONS",
        group=C,
        capability="LOGIC.FORALL x LOGIC.FUNCTION (higher order)",
        source=(
            "module M\nrequire forall f : Function[Real -> Real] . f = f"
        ),
        expectation=(
            "Quantifying over functions -- second-order. Needed for analysis "
            "('for every continuous f...'). Tests whether the quantifier domain may be a "
            "function type."
        ),
        mode="observe",
    ),
    Probe(
        id="COMP.APPROX_IN_OBLIGATION",
        group=C,
        capability="NUM.APPROXIMATE x EPISTEMIC.PROOF_OBLIGATION",
        source=(
            "module M\nconst pi_approx : Real = 3.14159\nrequire pi_approx > 3.0"
        ),
        expectation=(
            "An approximate value inside a proof obligation. Tests whether HML can mark a "
            "value as approximate at all, or whether 3.14159 is indistinguishable from an "
            "exact constant."
        ),
        mode="observe",
    ),
    # ---------------- red team: the hardest cases ----------------
    Probe(
        id="RT.CONDITIONAL_EXPECTATION",
        group=R,
        capability="PROB.CONDITIONAL_EXPECTATION",
        source=(
            "module M\nrv X : RandomVariable[Real]\nparam t : Probability\n"
            "require E[X | t] = t"
        ),
        expectation=(
            "E[X | theta] is the single most common object in statistics. If there is no "
            "expectation operator in the expression grammar, regression, conditional "
            "models and the law of total expectation are all unwritable."
        ),
        mode="observe",
    ),
    Probe(
        id="RT.INTEGRAL",
        group=R,
        capability="ANALYSIS.INTEGRAL",
        source="module M\nvar f : Function[Real -> Real]\ndef a := integral(f, 0.0, 1.0)",
        expectation="A definite integral. Core analysis.",
        mode="observe",
    ),
    Probe(
        id="RT.DERIVATIVE",
        group=R,
        capability="ANALYSIS.DERIVATIVE",
        source="module M\nvar f : Function[Real -> Real]\ndef d := derivative(f)",
        expectation="A derivative. Core analysis.",
        mode="observe",
    ),
    Probe(
        id="RT.LIMIT",
        group=R,
        capability="ANALYSIS.LIMIT",
        source="module M\nvar f : Function[Real -> Real]\ndef l := limit(f, 0.0)",
        expectation="A limit. Core analysis.",
        mode="observe",
    ),
    Probe(
        id="RT.SUMMATION",
        group=R,
        capability="ANALYSIS.SERIES / DISCRETE.SUM",
        source="module M\nindex i : Natural\ndef s := sum(i, 1, 10, i)",
        expectation=(
            "A summation. Without an indexed sum, no series, no sample mean, no "
            "log-likelihood over a dataset."
        ),
        mode="observe",
    ),
    Probe(
        id="RT.SET_MEMBERSHIP",
        group=R,
        capability="LOGIC.SET_MEMBERSHIP",
        source="module M\nvar S : Set[Real]\nvar x : Real\nrequire x in S",
        expectation="Set membership. Foundational.",
        mode="observe",
    ),
    Probe(
        id="RT.PIECEWISE",
        group=R,
        capability="LOGIC.PIECEWISE_DEFINITION",
        source=(
            "module M\nvar x : Real\ndef f := if x > 0.0 then x else -x"
        ),
        expectation="A piecewise definition (absolute value). Extremely common.",
        mode="observe",
    ),
    Probe(
        id="RT.EXISTS_UNIQUE",
        group=R,
        capability="LOGIC.UNIQUENESS",
        source="module M\nrequire exists! x : Real . x = 0.0",
        expectation=(
            "Unique existence. Every 'the' in mathematics ('the inverse', 'the limit') "
            "rests on it."
        ),
        mode="observe",
    ),
    Probe(
        id="RT.IMPLICATION_THEOREM",
        group=R,
        capability="LOGIC.IMPLICATION (theorem form)",
        source=(
            "module M\nvar x : Real\n"
            "prove forall y : Real . y > 0.0 => y * y > 0.0"
        ),
        expectation="A theorem-shaped implication under a quantifier.",
        mode="observe",
    ),
    Probe(
        id="RT.STOCHASTIC_PROCESS",
        group=R,
        capability="PROB.STOCHASTIC_PROCESS",
        source=(
            "module M\nrv W : RandomVariable[Function[Real -> Real]]\nrequire W = W"
        ),
        expectation=(
            "A process as a function-valued random variable (Brownian motion). Tests the "
            "outer limit of the RandomVariable constructor."
        ),
        mode="observe",
    ),
    Probe(
        id="RT.GROUP_STRUCTURE",
        group=R,
        capability="ALG.GROUP",
        source=(
            "module M\nconcept Group\n  parameter carrier : Set[Real]\n"
            "  invariant closure := forall a : Real . a = a\n"
            "  example integers := carrier = carrier\nend"
        ),
        expectation=(
            "An abstract algebraic structure via the concept mechanism. Tests whether "
            "`concept` can carry real algebraic content or is documentation."
        ),
        mode="observe",
    ),
    Probe(
        id="RT.MEASURE",
        group=R,
        capability="ANALYSIS.MEASURE",
        source="module M\nvar mu : Function[Set[Real] -> NonNegativeReal]\nrequire mu = mu",
        expectation="A measure as a set function. Tests Set as a function domain.",
        mode="observe",
    ),
    Probe(
        id="RT.COMPLEX_NUMBER",
        group=R,
        capability="NUM.COMPLEX",
        source="module M\nvar z : Complex\nrequire z = z",
        expectation=(
            "Complex numbers. Absent from the documented type list; probing whether they "
            "exist at all. Their absence excludes Fourier analysis, spectral theory, "
            "quantum mechanics and most of the eigenvalue theory."
        ),
        mode="observe",
    ),
    Probe(
        id="RT.EIGENVALUE",
        group=R,
        capability="ALG.EIGENVALUE",
        source=(
            "module M\nvar A : Matrix[Real, 3, 3]\nvar v : Vector[Real, 3]\n"
            "param lam : Real\nrequire (A @ v) = lam * v"
        ),
        expectation=(
            "The eigenvalue equation, written structurally rather than via a builtin. "
            "Tests scalar-times-vector and matrix-vector composition in a proposition."
        ),
        mode="observe",
    ),
    Probe(
        id="RT.SIGMA_ALGEBRA_CONDITIONING",
        group=R,
        capability="PROB.CONDITIONAL_ON_SIGMA_ALGEBRA",
        source=(
            "module M\nrv X : RandomVariable[Real]\nrv Y : RandomVariable[Real]\n"
            "require E[X | Y] = Y"
        ),
        expectation=(
            "Conditioning one random variable on another -- the general form of "
            "conditional expectation, and the basis of martingales and regression."
        ),
        mode="observe",
    ),
    Probe(
        id="RT.PROHIBITED_CONFLATION_DIST_VALUE",
        group=R,
        capability="TYPE.DISTRIBUTION_IS_NOT_VALUE",
        source=(
            "module M\nconst d : Distribution[Real] = 1.0"
        ),
        expectation=(
            "A Distribution[Real] is NOT a Real. The project's central type claim; this "
            "MUST be rejected."
        ),
        mode="reject",
    ),
    Probe(
        id="RT.PROHIBITED_CONFLATION_RV_VALUE",
        group=R,
        capability="TYPE.RV_IS_NOT_VALUE",
        source=(
            "module M\nrv X : RandomVariable[Real]\nconst y : Real = X"
        ),
        expectation="A RandomVariable[Real] is not a Real. MUST be rejected.",
        mode="reject",
    ),
    Probe(
        id="RT.PROHIBITED_CONFLATION_PROB_POSREAL",
        group=R,
        capability="TYPE.PROBABILITY_INCOMPARABLE_POSITIVEREAL",
        source=(
            "module M\nparam p : Probability\nconst q : PositiveReal = p"
        ),
        expectation=(
            "Probability and PositiveReal are declared INCOMPARABLE (D-004). Assigning "
            "one to the other must be rejected."
        ),
        mode="reject",
    ),
]


def main() -> int:
    results = run_all(PROBES)
    out = Path(__file__).resolve().parents[1] / "matrices" / "HML_COMPOSITION_PROBES.json"
    emit(results, out)
    cur = None
    for r in results:
        if r.probe.group != cur:
            cur = r.probe.group
            print(f"\n--- {cur.upper()} ---")
        print(
            f"{r.probe.id:44s} {r.verdict:9s} ok={str(r.ok):5s} "
            f"{','.join(r.codes) if r.codes else '(clean)'}"
        )
    s = summarise(results)
    print(f"\n{s['by_verdict']}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
