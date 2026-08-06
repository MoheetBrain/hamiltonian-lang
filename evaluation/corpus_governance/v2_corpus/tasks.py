"""The frozen ACQ0 v2 corpus: twelve development tasks and two sealed spares.

Each originates as a `CanonicalAcq0TaskV2` -- none is a repaired v1 JSON record. The ids
are new and unexposed; v1 ids stay quarantined with their evidence.

Every task is authored ONLY as HML-L1 source. The AST, ordered view, prose, surfaces,
identities and bundles are all derived from it, so no two artefacts can disagree.

The twelve fill the frozen feature taxonomy in
`docs/evaluation/ACQ0_V2_TAXONOMY.md`; the two spares exist to replace a development task
that a later review rejects, and cover the highest-risk cells (dimensional/CheckStmt and
objective-bearing implication) so a replacement never costs coverage.
"""

from __future__ import annotations

from ..canonical_v2 import (
    CanonicalAcq0TaskV2,
    DerivedFact,
    Objective,
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
        # --- taxonomy continuation: cells 9-12 and the second carriers ----------------
        CanonicalAcq0TaskV2(
            task_id="v2_quantifier_scope_003",
            family=TaskFamily.QUANTIFIER_SCOPE,
            source=(
                "module BoundedQuantifierProof\n"
                "var threshold : Real\n"
                "def all_below : Proposition := forall x : Probability . x < threshold\n"
                "def some_below : Proposition := exists x : Probability . x < threshold\n"
                "assume all_below\n"
                "prove some_below\n"
            ),
            provenance=_P,
            objective=Objective("prove", "some_below"),
            derived_facts=(
                DerivedFact("all_below => some_below",
                            ("the non-emptiness of Probability",), state_in_prose=True),
            ),
            prohibited_assumptions=(
                "that the converse holds; exists does not give forall",
            ),
            notes=(
                "taxonomy cell 9 (objective-bearing proof) and the second quantifier "
                "carrier. SUPERSEDES v2_quantifier_scope_002, whose premise "
                "`exists b : Real . forall x : Real . x < b` is FALSE in the reals -- "
                "instantiate the inner binder at x := b and it asserts b < b. An "
                "inconsistent premise entails everything, including the converse the task "
                "explicitly prohibits, so the one discrimination it existed to make was "
                "vacuous; and its goal was a theorem, so the assumption did no work "
                "either. Here the domain is Probability = [0,1], which is BOUNDED: "
                "`all_below` is satisfiable (threshold = 2), `some_below` is not a theorem "
                "(threshold = 0 refutes it), and the entailment holds only because the "
                "domain is non-empty. Premise and goal both do work"
            ),
        ),
        CanonicalAcq0TaskV2(
            task_id="v2_dimensional_algebra_004",
            family=TaskFamily.DIMENSIONAL_ALGEBRA,
            source=(
                "module SecondMomentCheck\n"
                "var mass : Quantity[Mass]\n"
                "var radius : Quantity[Length]\n"
                "def second_moment : Quantity[Mass * Length^2] := mass * radius ^ 2\n"
                "check dimension second_moment = Mass * Length^2\n"
            ),
            provenance=_P,
            objective=Objective("decide",
                                "that second_moment has dimension Mass * Length^2"),
            notes=(
                "taxonomy cell 10 (objective-bearing check) plus the second dimensional "
                "and second CheckStmt carrier. SUPERSEDES v2_dimensional_algebra_003, "
                "which named its definition `kinetic_energy` while omitting the 1/2. "
                "Every other occurrence of that identifier in this repository writes "
                "`0.5 * ...`, and `0.5 * mass * speed ^ 2` compiles AND passes the "
                "dimension check -- so a model that knows physics, or that had seen the "
                "prior track_a item, would be scored FAIL on a hash difference. That is "
                "the exact v1 defect this corpus exists to retire. The second moment of a "
                "point mass is m*r^2 with no coefficient, so the identifier and the body "
                "agree. `radius ^ 2` still squares a VALUE of base type Real (the "
                "dimension squaring is a consequence, not the operation), and the literal "
                "exponent is a positive integer, so it is total"
            ),
        ),
        CanonicalAcq0TaskV2(
            task_id="v2_probability_law_role_002",
            family=TaskFamily.PROBABILITY_LAW_ROLE,
            source=(
                "module RateLaw\n"
                "param lambda : PositiveReal\n"
                "prior lambda ~ Gamma(shape := 2, rate := 3)\n"
                "obs count : Natural = 4\n"
                "likelihood count | lambda ~ Poisson(rate := lambda)\n"
            ),
            provenance=_P,
            derived_facts=(
                DerivedFact("lambda > 0", ("the declared type of lambda",),
                            state_in_prose=True),
            ),
            prohibited_assumptions=(
                "that a Gamma rate and a Poisson rate are the same role; the first "
                "parameterises the prior, the second is the observed process intensity",
            ),
            notes=(
                "taxonomy cell 11 (state-only, state_in_prose=True) and the second "
                "probability-role carrier. The role word `rate` appears in BOTH laws "
                "meaning different things, which is the discrimination this family "
                "exists to test. `lambda > 0` is stated in prose and must NOT be encoded: "
                "it is already carried by the declared type, and re-encoding it as a "
                "premise is the v1 DERIVED_FACT_AS_INPUT_CONSTRAINT defect"
            ),
        ),
        CanonicalAcq0TaskV2(
            task_id="v2_assumption_boundary_002",
            family=TaskFamily.ASSUMPTION_BOUNDARY,
            source=(
                "module MixedOrderTransformation\n"
                "var input : Real\n"
                "require input > 0\n"
                "var gain : PositiveReal\n"
                "def amplified : Real := input * gain\n"
                "assume amplified > input\n"
                "require amplified < 100\n"
            ),
            provenance=_P,
            derived_facts=(
                DerivedFact("input != 0", ("input > 0",)),
            ),
            notes=(
                "taxonomy cell 12: six statements interleaving four kinds, with a "
                "derived fact deliberately NOT stated in prose. Declaration, requirement, "
                "declaration, definition, assumption, requirement -- any kind-bucketed "
                "view of this module is unencodable, so it is the direct regression "
                "carrier for the defect D-030 closed. `require` and `assume` alternate on "
                "purpose: the second requirement is a domain constraint, the assumption "
                "between them is a supplied premise, and neither entails the other"
            ),
        ),
    )


def build_spares() -> tuple[CanonicalAcq0TaskV2, ...]:
    """Two sealed replacements, admitted but never scored in tranche A.

    They cover the two highest-risk cells: a dimensional CheckStmt task, and an
    objective-bearing implication task. If a later review rejects a development task in
    either area, the replacement is already admitted rather than authored under pressure.
    """
    return (
        CanonicalAcq0TaskV2(
            task_id="v2_dimensional_algebra_spare_001",
            family=TaskFamily.DIMENSIONAL_ALGEBRA,
            source=(
                "module WorkCheck\n"
                "var force : Quantity[Mass * Length / Time^2]\n"
                "var distance : Quantity[Length]\n"
                "def work : Quantity[Mass * Length^2 / Time^2] := force * distance\n"
                "check dimension work = Mass * Length^2 / Time^2\n"
            ),
            provenance=_P,
            objective=Objective("decide",
                                "that work has dimension Mass * Length^2 / Time^2"),
            notes="sealed spare for the dimensional/CheckStmt cells; multiplication only",
        ),
        CanonicalAcq0TaskV2(
            task_id="v2_implication_equivalence_spare_001",
            family=TaskFamily.IMPLICATION_VS_EQUIVALENCE,
            source=(
                "module BiconditionalCare\n"
                "var p : Bool\n"
                "var q : Bool\n"
                "assume p => q\n"
                "assume q => p\n"
                "def equivalent : Proposition := p <=> q\n"
                "prove equivalent\n"
            ),
            provenance=_P,
            objective=Objective("prove", "equivalent"),
            prohibited_assumptions=(
                "that either implication alone establishes the biconditional",
            ),
            notes=(
                "sealed spare for the objective-bearing and implication-direction cells. "
                "BOTH implications are stated; a model that encodes one has changed the "
                "mathematics, and a model that writes <=> in place of the two assumptions "
                "has changed it differently"
            ),
        ),
    )


PROOF_CORPUS: tuple[CanonicalAcq0TaskV2, ...] = build_corpus()
SEALED_SPARES: tuple[CanonicalAcq0TaskV2, ...] = build_spares()
