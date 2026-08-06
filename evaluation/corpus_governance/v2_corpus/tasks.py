"""Eight canonical v2 tasks, one per family.

Each originates as a `CanonicalAcq0TaskV2` -- none is a repaired v1 JSON record. The ids
are new and unexposed; v1 ids stay quarantined with their evidence.
"""

from __future__ import annotations

from ..canonical_v2 import (
    CanonicalAcq0TaskV2,
    DerivedFact,
    Provenance,
    TaskFamily,
)

_P = Provenance(
    author="Lead Architect",
    created_utc="2026-08-06T00:00:00+00:00",
    generator="canonical v2 proof corpus",
    notes="authored directly as canonical objects after the v1 instrument audit",
)


def build_corpus() -> tuple[CanonicalAcq0TaskV2, ...]:
    return (
        CanonicalAcq0TaskV2(
            task_id="v2_binding_dependency_001",
            family=TaskFamily.BINDING_DEPENDENCY,
            source=(
                "module BindingDependency\n"
                "const alpha : Real = 3\n"
                "const beta : Real = 4\n"
                "def gamma : Real := alpha + beta\n"
                "def delta : Real := gamma * alpha\n"
            ),
            provenance=_P,
            notes="every value is supplied; delta depends on gamma which depends on both",
        ),
        CanonicalAcq0TaskV2(
            task_id="v2_assumption_boundary_001",
            family=TaskFamily.ASSUMPTION_BOUNDARY,
            source=(
                "module AssumptionBoundary\n"
                "const eta : Real = 5\n"
                "var digamma : Real\n"
                "assume digamma > 4\n"
                "def varrho(mu : PositiveReal) : Real := eta / mu\n"
            ),
            derived_facts=(DerivedFact("digamma != 0", ("digamma > 4",)),),
            provenance=_P,
            notes=(
                "the v1 task this replaces hid eta's value and varrho's body, and filed "
                "the derived non-zero fact as an input premise. The binder is "
                "PositiveReal, not Real: eta / mu is not total at zero, and the hardening "
                "audit rejected the Real spelling rather than let the corpus assume "
                "non-zeroness on the model's behalf"
            ),
        ),
        CanonicalAcq0TaskV2(
            task_id="v2_implication_equivalence_001",
            family=TaskFamily.IMPLICATION_VS_EQUIVALENCE,
            source=(
                "module ImplicationDirection\n"
                "var p : Bool\n"
                "var q : Bool\n"
                "def forward : Proposition := p implies q\n"
                "def backward : Proposition := q implies p\n"
                "assume p implies q\n"
            ),
            prohibited_assumptions=("that the converse holds",),
            provenance=_P,
            notes="direction is the content; a swap must change the canonical identity",
        ),
        CanonicalAcq0TaskV2(
            task_id="v2_approximation_equality_002",
            family=TaskFamily.APPROXIMATION_VS_EQUALITY,
            source=(
                "module ApproximationBoundary\n"
                "const target : Real = 2\n"
                "var estimate : Real\n"
                "const tolerance : PositiveReal = 0.01\n"
                "require estimate - target < tolerance\n"
                "require target - estimate < tolerance\n"
            ),
            provenance=_P,
            notes=(
                "supersedes v2_approximation_equality_001, whose single inequality was a "
                "ONE-SIDED bound satisfied by an estimate arbitrarily far below target -- "
                "it encoded uniquely but did not express the approximation-vs-equality "
                "contrast its family claims. Two explicit inequalities give a genuine "
                "two-sided bound; HML has no absolute-value form. Fresh id because the "
                "mathematics changed"
            ),
        ),
        CanonicalAcq0TaskV2(
            task_id="v2_quantifier_scope_001",
            family=TaskFamily.QUANTIFIER_SCOPE,
            source=(
                "module QuantifierScope\n"
                "def every_x_has_a_y : Proposition := "
                "forall x : Real . exists y : Real . y > x\n"
                "assume every_x_has_a_y\n"
            ),
            prohibited_assumptions=("that the quantifiers may be exchanged",),
            provenance=_P,
            notes="order is the content; exchanging it must change the identity",
        ),
        CanonicalAcq0TaskV2(
            task_id="v2_probability_law_role_001",
            family=TaskFamily.PROBABILITY_LAW_ROLE,
            source=(
                "module ProbabilityRole\n"
                "param theta : Probability\n"
                "prior theta ~ Beta(alpha := 2, beta := 5)\n"
                "obs successes : Natural = 7\n"
                "obs trials : Natural = 10\n"
                "likelihood successes | theta ~ "
                "Binomial(trials := trials, prob := theta)\n"
            ),
            provenance=_P,
            notes="role labels carry the meaning; swapping alpha and beta must differ",
        ),
        CanonicalAcq0TaskV2(
            task_id="v2_dimensional_algebra_002",
            family=TaskFamily.DIMENSIONAL_ALGEBRA,
            source=(
                "module DimensionalAlgebra\n"
                "var force : Quantity[Mass * Length / Time^2]\n"
                "var duration : Quantity[Time]\n"
                "def impulse : Quantity[Mass * Length / Time] := force * duration\n"
                "check dimension impulse = Mass * Length / Time\n"
            ),
            provenance=_P,
            notes=(
                "supersedes v2_dimensional_algebra_001, which divided by `area` -- a "
                "module-level var admitting zero, outside the reach of the binder-only "
                "partiality guard, and unguardable because `require area != 0` does not "
                "compile (HML-D502: a Quantity[Length^2] cannot be compared to a "
                "dimensionless 0). Multiplication is total, so no definedness question "
                "arises. The dimension check is now present in the model-visible ordered "
                "view; in the superseded task it existed only in the reference. Fresh id "
                "because the mathematics changed"
            ),
        ),
        CanonicalAcq0TaskV2(
            task_id="v2_transformation_side_condition_001",
            family=TaskFamily.TRANSFORMATION_SIDE_CONDITION,
            source=(
                "module TransformationSideCondition\n"
                "var lhs : Real\n"
                "var rhs : Real\n"
                "var scale : Real\n"
                "require scale != 0\n"
                "assume lhs * scale = rhs * scale\n"
            ),
            provenance=_P,
            notes=(
                "cancellation needs scale != 0; the side condition is a supplied "
                "constraint here, not a derived fact"
            ),
        ),
    )


PROOF_CORPUS: tuple[CanonicalAcq0TaskV2, ...] = build_corpus()
