"""V1 concept-kernel ablation corpus — HML-V1-CONCEPT-001 Phase 10, deliverable 1.

Five arms, nested so that each is the previous plus exactly one layer. That nesting is
what makes this an *ablation* rather than a set of unrelated conditions:

    SE          structured English (the scaffolding control, retained from the pilot)
    V0          Hamiltonian V0 — the preserved baseline, tag `hml-v0-baseline`
    V1_nomint   V0 surface + V1 typed vocabulary, minting PROHIBITED
    V1_mint     V1_nomint + the admitted-concept registry + the minting protocol
    V1_full     V1_mint + transformation edges, epistemic status and discourse state

The contrast ladder each arm is the control for:

    V0        - SE          does the typed representation beat scaffolding?  (refuted at V0)
    V1_nomint - V0          does V1's added vocabulary alone cost or buy anything?
    V1_mint   - V1_nomint   does concept minting earn its place?
    V1_full   - V1_mint     do transformation + epistemic tracking earn theirs?

Why this corpus is built the way it is
--------------------------------------
The V0 pilot (`docs/evaluation/HML_EVAL_001_PILOT_REPORT.md`) found **no** representation
advantage, and its own §9 explains why that finding is nearly uninformative: 14 of 15
problems were answered correctly in every arm, the minimum detectable effect was about
33 percentage points, and six of seven paired contrasts had **zero** discordant pairs.

`docs/design/V1_EXPERIMENT_PLAN.md` §1 therefore requires a corpus targeting **50–60%**
baseline accuracy at **n >= 60** paired problems. This corpus carries 60 problems, 12 in
each of five blocks. Every item is built around a specific near-miss that a competent
careless reader takes, so the ceiling is structural rather than hoped for.

**The target accuracy is a design intent, not a measurement.** No model has been run
against this corpus. `calibration_status` on every problem is ``NOT YET RUN`` and the
report must say so until a pilot measures it.

Reuse, not rewrite
------------------
``CanonicalSemanticObject``, ``AnswerSpec``, ``SemanticFacts`` and the deterministic
``check_answer`` come from ``evaluation.corpus.cso``. ``SCHEMA_A_PRIME``, ``HML_SPEC``
and ``ANSWER_OPEN``/``ANSWER_CLOSE`` come from ``evaluation.corpus.renderers``. Only the
three V1 surface blocks below are new text.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from evaluation.corpus.cso import (
    ANSWER_CLOSE,
    ANSWER_OPEN,
    AnswerSpec,
    CanonicalSemanticObject,
    SemanticFacts,
)
from evaluation.corpus.renderers import HML_SPEC, SCHEMA_A_PRIME, ArmPrompt

from . import V1_EVAL_VERSION

__all__ = [
    "ARMS_V1",
    "ARM_LABELS_V1",
    "ABLATION_LADDER",
    "CATEGORY_TARGETS_V1",
    "ADMITTED_CONCEPTS",
    "HELD_OUT_CONCEPTS",
    "V1Facts",
    "AdversarialPair",
    "ADVERSARIAL_PAIRS",
    "build_all_v1",
    "build_demos_v1",
    "v1_facts",
    "render_v1_arm",
    "verify_v1_shared_content_identical",
    "V1_INFORMATION_ASYMMETRY",
]

ARMS_V1 = ["SE", "V0", "V1_nomint", "V1_mint", "V1_full"]

ARM_LABELS_V1 = {
    "SE": "structured English (scaffolding control)",
    "V0": "Hamiltonian V0 (preserved baseline)",
    "V1_nomint": "Hamiltonian V1, concept minting prohibited",
    "V1_mint": "Hamiltonian V1 + admitted concepts + minting protocol",
    "V1_full": "Hamiltonian V1 + transformation, epistemic and discourse tracking",
}

#: (treatment, control, what the contrast isolates). Consumed by `score_v1`.
ABLATION_LADDER = [
    ("V0", "SE", "does the V0 typed representation beat structured English?"),
    ("V1_nomint", "V0", "does V1's added vocabulary alone cost or buy anything?"),
    ("V1_mint", "V1_nomint", "does concept minting earn its place? (the decisive one)"),
    ("V1_full", "V1_mint", "do transformation and epistemic tracking earn theirs?"),
]

CATEGORY_TARGETS_V1 = {
    "concept_recognition": 12,
    "family_derivation": 12,
    "recurring_structure": 12,
    "transformation_chain": 12,
    "epistemic_calibration": 12,
}


def _rng(pid: str) -> random.Random:
    """Seeded per problem id, as in `evaluation/corpus/generators.py`.

    The *structure* is the thing under test; the numeric instance is randomised so the
    exact item is very unlikely to appear verbatim in any pretraining corpus.
    """
    return random.Random(f"hml-v1-ablation::{pid}")


_SYMS = ["alpha", "beta", "gamma", "delta", "kappa", "lambda", "mu", "nu",
         "rho", "sigma", "tau", "phi", "chi", "psi", "omega", "eta"]


# ---------------------------------------------------------------------------
# The admitted-concept registry supplied to the V1_mint and V1_full arms
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdmittedConcept:
    """One entry of the registry the minting arms are given.

    Mirrors the required fields of `spec/concept_registry.schema.json`, reduced to what
    fits in a prompt. ``compresses`` is carried because a concept that compresses nothing
    is a synonym and must be rejected as a duplicate — that is the field the false-novelty
    metric is defined against.
    """

    canonical_id: str
    type_signature: str
    formal_definition: str
    compresses: tuple[str, ...]

    def render(self) -> str:
        return (
            f"  {self.canonical_id} : {self.type_signature}\n"
            f"      definition  {self.formal_definition}\n"
            f"      compresses  {'; '.join(self.compresses)}"
        )


#: Concepts every minting arm may cite by name. Deliberately *incomplete*: for each of
#: six of these the corpus contains a problem whose correct answer is the concept's
#: weaker relative, which is NOT listed here. That is the transfer test.
ADMITTED_CONCEPTS: tuple[AdmittedConcept, ...] = (
    AdmittedConcept(
        "LocationScaleFamily",
        "Density[Real] * Real * PositiveReal -> Family[Distribution[Real]]",
        "f_{a,b}(x) = (1/b) * f_0((x - a)/b) for a fixed standard density f_0",
        ("re-deriving the shift-and-rescale identity for each named distribution",),
    ),
    AdmittedConcept(
        "ExponentialFamily",
        "Statistic * NaturalParameter -> Family[Distribution[Real]]",
        "p(x | eta) = h(x) * exp(eta . T(x) - A(eta)) with support NOT depending on eta",
        ("restating sufficiency, conjugacy and moment identities per distribution",),
    ),
    AdmittedConcept(
        "ConjugatePair",
        "Family[Distribution] * Family[Distribution] -> Proposition",
        "prior and likelihood families such that the posterior lies in the prior family",
        ("carrying out the same normalising integral for each new data set",),
    ),
    AdmittedConcept(
        "Convex",
        "Function[Real -> Real] -> Proposition",
        "f(t*x + (1-t)*y) <= t*f(x) + (1-t)*f(y) for all x, y and t in [0,1]",
        ("re-proving Jensen's inequality and unique-minimiser arguments per function",),
    ),
    AdmittedConcept(
        "Martingale",
        "Sequence[RandomVariable] * Filtration -> Proposition",
        "E[X_{n+1} | F_n] = X_n almost surely, with X_n adapted and integrable",
        ("restating the optional-stopping and convergence arguments per process",),
    ),
    AdmittedConcept(
        "MarkovProcess",
        "Sequence[RandomVariable] * Filtration -> Proposition",
        "the conditional law of X_{n+1} given F_n depends on X_n alone",
        ("re-deriving transition-kernel factorisations per process",),
    ),
    AdmittedConcept(
        "SufficientStatistic",
        "Statistic * Family[Distribution] -> Proposition",
        "p(x | theta) = g(T(x), theta) * h(x): the Fisher-Neyman factorisation",
        ("re-deriving data reduction for each estimator",),
    ),
    AdmittedConcept(
        "CompleteStatistic",
        "Statistic * Family[Distribution] -> Proposition",
        "E_theta[g(T)] = 0 for all theta implies g(T) = 0 almost surely",
        ("re-proving uniqueness of unbiased estimators per family",),
    ),
    AdmittedConcept(
        "Norm",
        "Function[V -> NonNegativeReal] -> Proposition",
        "absolutely homogeneous, subadditive, and ||v|| = 0 only for v = 0",
        ("restating the triangle inequality and separation of points per space",),
    ),
    AdmittedConcept(
        "Metric",
        "Function[X * X -> NonNegativeReal] -> Proposition",
        "symmetric, triangle inequality, and d(x,y) = 0 only when x = y",
        ("restating convergence and continuity arguments per space",),
    ),
    AdmittedConcept(
        "EquivalenceRelation",
        "Relation[X, X] -> Proposition",
        "reflexive, symmetric and transitive",
        ("re-deriving the partition induced by a relation per case",),
    ),
    AdmittedConcept(
        "Group",
        "Set * BinaryOperation -> Proposition",
        "associative, with identity, and every element invertible",
        ("re-proving cancellation and unique-solution arguments per structure",),
    ),
    AdmittedConcept(
        "SigmaAlgebra",
        "Set[Set[X]] -> Proposition",
        "contains X, closed under complement and under COUNTABLE unions",
        ("re-establishing measurability of limits per construction",),
    ),
    AdmittedConcept(
        "UnbiasedEstimator",
        "Function[Sample -> ParameterSpace] * ParameterSpace -> Proposition",
        "E_theta[T(X)] = theta for every theta; a property of the ESTIMATOR, not of a value",
        ("restating the bias calculation per estimator",),
    ),
    AdmittedConcept(
        "ConsistentEstimator",
        "Sequence[Function[Sample -> ParameterSpace]] * ParameterSpace -> Proposition",
        "T_n(X) converges in probability to theta as n -> infinity",
        ("restating the law-of-large-numbers argument per estimator sequence",),
    ),
)

#: Correct answers that are NOT in the registry above. Each is the strictly weaker
#: relative of an admitted concept, so the arm that has the registry must generalise
#: from it rather than look the answer up. This is the transfer denominator.
HELD_OUT_CONCEPTS = (
    "SCALE_FAMILY",        # weaker relative of LocationScaleFamily (location fixed at 0)
    "QUASICONVEX",         # weaker relative of Convex
    "SEMINORM",            # weaker relative of Norm
    "PSEUDOMETRIC",        # weaker relative of Metric
    "PREORDER",            # weaker relative of EquivalenceRelation
    "MONOID",              # weaker relative of Group
    "ALGEBRA_OF_SETS",     # weaker relative of SigmaAlgebra
)


# ---------------------------------------------------------------------------
# V1-specific ground truth, carried beside the CSO rather than inside it
# ---------------------------------------------------------------------------


@dataclass
class V1Facts:
    """Ground truth the V0 ``SemanticFacts`` has no slot for.

    Kept in a parallel table because ``evaluation/corpus/cso.py`` is the frozen V0
    contract and this package may not modify it (CLAUDE.md rule 2).
    """

    problem_id: str
    block: str

    #: Concepts a correct encoding may legitimately cite. Anything minted outside this
    #: set is a candidate false novelty and is scored as such.
    licensed_concepts: tuple[str, ...] = ()
    #: True when the correct answer is a concept absent from ``ADMITTED_CONCEPTS``.
    transfer_item: bool = False
    #: Which Estimation-family member the property attaches to, if any.
    family_member: str | None = None
    #: 1-based index of the first invalid step, 0 when the chain is wholly valid.
    first_invalid_step: int | None = None
    #: The one epistemic status a correct encoding must carry.
    epistemic_status: str | None = None
    #: Statuses that would be wrong here, and are the near-misses the item is built on.
    prohibited_statuses: tuple[str, ...] = ()
    #: Can V0 express this problem at all? "yes" | "partial" | "no", with the reason.
    v0_expressible: Literal["yes", "partial", "no"] = "yes"
    v0_expressible_reason: str = ""
    #: Which V1 layer the item is diagnostic for. Used for layer-by-layer kill criteria.
    diagnostic_for_layer: str = ""
    #: Set once a pilot has measured per-arm accuracy on this item. Never guessed.
    calibration_status: str = "NOT YET RUN"


_V1_FACTS: dict[str, V1Facts] = {}


def _register(f: V1Facts) -> V1Facts:
    _V1_FACTS[f.problem_id] = f
    return f


def v1_facts(problem_id: str) -> V1Facts:
    if not _V1_FACTS:
        build_all_v1()
    return _V1_FACTS[problem_id]


def _cso(
    pid: str,
    block: str,
    difficulty: str,
    prose: str,
    question: str,
    answer: AnswerSpec,
    *,
    distractors: list[str],
    semantics: SemanticFacts | None = None,
    reference_hml: str = "",
    generator: str = "",
) -> CanonicalSemanticObject:
    return CanonicalSemanticObject(
        id=pid,
        domain=block,
        difficulty=difficulty,  # type: ignore[arg-type]
        prose=prose,
        question=question,
        answer=answer,
        semantics=semantics or SemanticFacts(),
        distractors=distractors,
        reference_hml=reference_hml,
        generator=generator,
        corpus_version=V1_EVAL_VERSION,
    )


# ===========================================================================
# BLOCK 1 — concept recognition (12)
# ===========================================================================
#
# Every item pairs a structure with the concept that is *nearly* right. The lure is
# always the stronger or better-known relative, so naming the famous concept is the
# error. Six items are transfer items: the correct answer is deliberately absent from
# ADMITTED_CONCEPTS.

_CR_OPTIONS_A = ["LOCATION_SCALE_FAMILY", "SCALE_FAMILY", "EXPONENTIAL_FAMILY", "NONE"]
_CR_QUESTION = (
    "Which single concept does the structure above instantiate exactly? "
    "Answer with one of the listed names, or NONE if no listed concept applies exactly."
)


def _cr01_scale_family(pid: str) -> CanonicalSemanticObject:
    r = _rng(pid)
    b = r.choice([2, 3, 4, 5, 7])
    s = r.choice(_SYMS)
    _register(V1Facts(pid, "concept_recognition", licensed_concepts=("ScaleFamily",),
                      transfer_item=True, v0_expressible="partial",
                      v0_expressible_reason="V0 can declare the density but has no way to "
                                            "state that a family is closed under the map",
                      diagnostic_for_layer="concept_registry"))
    return _cso(
        pid, "concept_recognition", "medium",
        prose=(
            f"A family of densities on the positive reals is indexed by a single parameter "
            f"{s} > 0, and every member is obtained from one fixed density f0 by "
            f"g_{s}(x) = (1/{s}) * f0(x/{s}). No shift is available: the value at the "
            f"origin is the same for every member, and the family contains no member of "
            f"the form f0(x - {b})."
        ),
        question=f"{_CR_QUESTION}\nOptions: {', '.join(_CR_OPTIONS_A)}",
        answer=AnswerSpec(
            "choice", "SCALE_FAMILY", options=_CR_OPTIONS_A,
            justification="the family has a scale parameter and NO location parameter; "
                          "a location-scale family requires both",
        ),
        distractors=["naming LOCATION_SCALE_FAMILY, the better-known relative, "
                     "although no location parameter exists"],
        generator="_cr01_scale_family",
    )


_CR_OPTIONS_B = ["EXPONENTIAL_FAMILY", "LOCATION_SCALE_FAMILY", "CONJUGATE_PAIR", "NONE"]


def _cr02_support_depends_on_parameter(pid: str) -> CanonicalSemanticObject:
    r = _rng(pid)
    th = r.choice(_SYMS)
    _register(V1Facts(pid, "concept_recognition", licensed_concepts=(),
                      v0_expressible="partial",
                      v0_expressible_reason="V0 can declare the density; it cannot express "
                                            "that the support depends on the parameter",
                      diagnostic_for_layer="concept_registry"))
    return _cso(
        pid, "concept_recognition", "hard",
        prose=(
            f"A density is written p(x | {th}) = (1/{th}) for 0 < x < {th} and 0 "
            f"otherwise, with {th} > 0. It can be rewritten as "
            f"p(x | {th}) = exp(-log {th}) * 1[0 < x < {th}], which has the shape of a "
            f"one-parameter exponential family with h(x) = 1[0 < x < {th}]."
        ),
        question=f"{_CR_QUESTION}\nOptions: {', '.join(_CR_OPTIONS_B)}",
        answer=AnswerSpec(
            "choice", "NONE", options=_CR_OPTIONS_B,
            justification="the exponential-family definition requires the support to be "
                          "free of the parameter; here it is not, and the rewriting hides "
                          "the parameter inside the indicator",
        ),
        distractors=["accepting the rewriting and naming EXPONENTIAL_FAMILY"],
        generator="_cr02_support_depends_on_parameter",
    )


_CR_OPTIONS_C = ["CONVEX", "QUASICONVEX", "NONE"]


def _cr03_quasiconvex(pid: str) -> CanonicalSemanticObject:
    r = _rng(pid)
    c = r.choice([2, 3, 5, 6, 8])
    _register(V1Facts(pid, "concept_recognition", licensed_concepts=("Quasiconvex",),
                      transfer_item=True, v0_expressible="partial",
                      v0_expressible_reason="V0 can state the inequality pointwise but has "
                                            "no concept membership to assert",
                      diagnostic_for_layer="concept_registry"))
    return _cso(
        pid, "concept_recognition", "medium",
        prose=(
            f"A function h on the reals satisfies: every sublevel set "
            f"{{x : h(x) <= c}} is an interval, for every real c. It does not satisfy "
            f"h(t*x + (1-t)*y) <= t*h(x) + (1-t)*h(y) — for instance h(0) = 0, "
            f"h({c}) = 0 and h({c}/2) = {c}/4 violates it at t = 1/2."
        ),
        question=f"{_CR_QUESTION}\nOptions: {', '.join(_CR_OPTIONS_C)}",
        answer=AnswerSpec(
            "choice", "QUASICONVEX", options=_CR_OPTIONS_C,
            justification="interval sublevel sets is exactly quasiconvexity; the stated "
                          "violation rules out convexity",
        ),
        distractors=["naming CONVEX because sublevel sets are convex sets"],
        generator="_cr03_quasiconvex",
    )


_CR_OPTIONS_D = ["MARTINGALE", "MARKOV_PROCESS", "NONE"]


def _cr04_martingale_not_markov(pid: str) -> CanonicalSemanticObject:
    r = _rng(pid)
    n0 = r.choice([3, 4, 5, 6])
    _register(V1Facts(pid, "concept_recognition", licensed_concepts=("Martingale",),
                      v0_expressible="no",
                      v0_expressible_reason="V0 has no conditional-expectation operator and "
                                            "no filtration",
                      diagnostic_for_layer="concept_registry"))
    return _cso(
        pid, "concept_recognition", "hard",
        prose=(
            f"A sequence S_1, S_2, ... is adapted to a filtration F_n and each S_n is "
            f"integrable. It satisfies E[S_{{n+1}} | F_n] = S_n for every n. The "
            f"conditional law of S_{{n+1}} given F_n depends on the whole history "
            f"S_1, ..., S_n and not on S_n alone: at n = {n0} the increment's variance is "
            f"a function of S_1."
        ),
        question=f"{_CR_QUESTION}\nOptions: {', '.join(_CR_OPTIONS_D)}",
        answer=AnswerSpec(
            "choice", "MARTINGALE", options=_CR_OPTIONS_D,
            justification="the defining identity is the martingale property; the stated "
                          "history dependence explicitly denies the Markov property",
        ),
        distractors=["assuming a martingale is a Markov process"],
        generator="_cr04_martingale_not_markov",
    )


_CR_OPTIONS_E = ["SUFFICIENT_STATISTIC", "COMPLETE_STATISTIC", "NONE"]


def _cr05_sufficient_not_complete(pid: str) -> CanonicalSemanticObject:
    r = _rng(pid)
    n = r.choice([4, 6, 8, 10])
    _register(V1Facts(pid, "concept_recognition", licensed_concepts=("SufficientStatistic",),
                      v0_expressible="partial",
                      v0_expressible_reason="V0 can write the factorisation as an equation; "
                                            "it cannot assert concept membership",
                      diagnostic_for_layer="concept_registry"))
    return _cso(
        pid, "concept_recognition", "hard",
        prose=(
            f"For a sample of size {n} the joint density factorises as "
            f"p(x | theta) = g(T(x), theta) * h(x). It is also known that there is a "
            f"non-zero function q with E_theta[q(T)] = 0 for every theta."
        ),
        question=f"{_CR_QUESTION}\nOptions: {', '.join(_CR_OPTIONS_E)}",
        answer=AnswerSpec(
            "choice", "SUFFICIENT_STATISTIC", options=_CR_OPTIONS_E,
            justification="the factorisation gives sufficiency; the existence of a "
                          "non-zero q with zero expectation for all theta explicitly "
                          "denies completeness",
        ),
        distractors=["treating sufficiency and completeness as the same property"],
        generator="_cr05_sufficient_not_complete",
    )


_CR_OPTIONS_F = ["NORM", "SEMINORM", "NONE"]


def _cr06_seminorm(pid: str) -> CanonicalSemanticObject:
    r = _rng(pid)
    k = r.choice([2, 3, 4, 5])
    _register(V1Facts(pid, "concept_recognition", licensed_concepts=("Seminorm",),
                      transfer_item=True, v0_expressible="partial",
                      v0_expressible_reason="V0 can require the two inequalities; it has no "
                                            "way to say which named concept results",
                      diagnostic_for_layer="concept_registry"))
    return _cso(
        pid, "concept_recognition", "medium",
        prose=(
            f"A map p from a real vector space V of dimension {k} to the non-negative "
            f"reals satisfies p(c*v) = |c| * p(v) and p(u + v) <= p(u) + p(v) for all "
            f"u, v and all scalars c. There is a non-zero w in V with p(w) = 0."
        ),
        question=f"{_CR_QUESTION}\nOptions: {', '.join(_CR_OPTIONS_F)}",
        answer=AnswerSpec(
            "choice", "SEMINORM", options=_CR_OPTIONS_F,
            justification="homogeneity and subadditivity without separation of points is "
                          "exactly a seminorm; p(w) = 0 for w != 0 rules out a norm",
        ),
        distractors=["naming NORM because the two familiar axioms hold"],
        generator="_cr06_seminorm",
    )


_CR_OPTIONS_G = ["METRIC", "PSEUDOMETRIC", "NONE"]


def _cr07_pseudometric(pid: str) -> CanonicalSemanticObject:
    r = _rng(pid)
    a, b = r.sample(["u", "v", "w", "z"], 2)
    _register(V1Facts(pid, "concept_recognition", licensed_concepts=("Pseudometric",),
                      transfer_item=True, v0_expressible="partial",
                      v0_expressible_reason="same as the seminorm case",
                      diagnostic_for_layer="concept_registry"))
    return _cso(
        pid, "concept_recognition", "medium",
        prose=(
            f"A function d on X * X is non-negative, symmetric, satisfies d(x, x) = 0 and "
            f"the triangle inequality d(x, z) <= d(x, y) + d(y, z). For two distinct "
            f"points {a} and {b} of X it gives d({a}, {b}) = 0."
        ),
        question=f"{_CR_QUESTION}\nOptions: {', '.join(_CR_OPTIONS_G)}",
        answer=AnswerSpec(
            "choice", "PSEUDOMETRIC", options=_CR_OPTIONS_G,
            justification="all metric axioms except separation of points",
        ),
        distractors=["naming METRIC and overlooking that d vanishes off the diagonal"],
        generator="_cr07_pseudometric",
    )


_CR_OPTIONS_H = ["EQUIVALENCE_RELATION", "PREORDER", "NONE"]


def _cr08_preorder(pid: str) -> CanonicalSemanticObject:
    r = _rng(pid)
    x, y = r.sample(["p", "q", "r", "s"], 2)
    _register(V1Facts(pid, "concept_recognition", licensed_concepts=("Preorder",),
                      transfer_item=True, v0_expressible="partial",
                      v0_expressible_reason="V0 can state reflexivity and transitivity as "
                                            "quantified propositions; it cannot name the "
                                            "resulting concept",
                      diagnostic_for_layer="concept_registry"))
    return _cso(
        pid, "concept_recognition", "easy",
        prose=(
            f"A relation R on a set is reflexive and transitive. It is not symmetric: "
            f"{x} R {y} holds and {y} R {x} does not."
        ),
        question=f"{_CR_QUESTION}\nOptions: {', '.join(_CR_OPTIONS_H)}",
        answer=AnswerSpec(
            "choice", "PREORDER", options=_CR_OPTIONS_H,
            justification="reflexive and transitive, without symmetry",
        ),
        distractors=["naming EQUIVALENCE_RELATION from the two axioms that do hold"],
        generator="_cr08_preorder",
    )


_CR_OPTIONS_I = ["GROUP", "MONOID", "NONE"]


def _cr09_monoid(pid: str) -> CanonicalSemanticObject:
    r = _rng(pid)
    e = r.choice([0, 1])
    _register(V1Facts(pid, "concept_recognition", licensed_concepts=("Monoid",),
                      transfer_item=True, v0_expressible="partial",
                      v0_expressible_reason="V0 can state associativity and identity; it "
                                            "cannot name the algebraic structure",
                      diagnostic_for_layer="concept_registry"))
    return _cso(
        pid, "concept_recognition", "easy",
        prose=(
            f"A set carries an associative binary operation with a two-sided identity "
            f"element {e}. At least one element has no inverse: there is an x such that "
            f"no y satisfies x * y = {e}."
        ),
        question=f"{_CR_QUESTION}\nOptions: {', '.join(_CR_OPTIONS_I)}",
        answer=AnswerSpec(
            "choice", "MONOID", options=_CR_OPTIONS_I,
            justification="associativity plus identity, without inverses",
        ),
        distractors=["naming GROUP from associativity and identity alone"],
        generator="_cr09_monoid",
    )


_CR_OPTIONS_J = ["UNBIASED_ESTIMATOR", "CONSISTENT_ESTIMATOR", "NONE"]


def _cr10_consistent_not_unbiased(pid: str) -> CanonicalSemanticObject:
    r = _rng(pid)
    n = r.choice([10, 20, 25, 50])
    _register(V1Facts(pid, "concept_recognition",
                      licensed_concepts=("ConsistentEstimator",),
                      v0_expressible="partial",
                      v0_expressible_reason="V0 can declare the estimator; it has no "
                                            "convergence-in-probability predicate",
                      diagnostic_for_layer="concept_registry"))
    return _cso(
        pid, "concept_recognition", "medium",
        prose=(
            f"A sequence of estimators T_n satisfies E[T_n] = theta * n / (n + 1) for "
            f"every n, so at n = {n} the expectation is theta * {n}/{n + 1}. The T_n "
            f"converge in probability to theta as n grows."
        ),
        question=f"{_CR_QUESTION}\nOptions: {', '.join(_CR_OPTIONS_J)}",
        answer=AnswerSpec(
            "choice", "CONSISTENT_ESTIMATOR", options=_CR_OPTIONS_J,
            justification="the bias is non-zero at every finite n, so unbiasedness fails; "
                          "convergence in probability is exactly consistency",
        ),
        distractors=["reading 'bias vanishes in the limit' as 'unbiased'"],
        generator="_cr10_consistent_not_unbiased",
    )


_CR_OPTIONS_K = ["SIGMA_ALGEBRA", "ALGEBRA_OF_SETS", "NONE"]


def _cr11_algebra_of_sets(pid: str) -> CanonicalSemanticObject:
    r = _rng(pid)
    m = r.choice([2, 3, 4])
    _register(V1Facts(pid, "concept_recognition", licensed_concepts=("AlgebraOfSets",),
                      transfer_item=True, v0_expressible="no",
                      v0_expressible_reason="V0 has no set-of-sets type and no closure "
                                            "predicate over countable operations",
                      diagnostic_for_layer="concept_registry"))
    return _cso(
        pid, "concept_recognition", "medium",
        prose=(
            f"A collection C of subsets of X contains X, is closed under complement, and "
            f"is closed under unions of any {m} of its members, hence under all finite "
            f"unions. There is a countable sequence in C whose union is not in C."
        ),
        question=f"{_CR_QUESTION}\nOptions: {', '.join(_CR_OPTIONS_K)}",
        answer=AnswerSpec(
            "choice", "ALGEBRA_OF_SETS", options=_CR_OPTIONS_K,
            justification="finite but not countable closure",
        ),
        distractors=["naming SIGMA_ALGEBRA from complement and finite-union closure"],
        generator="_cr11_algebra_of_sets",
    )


_CR_OPTIONS_L = ["CONJUGATE_PAIR", "EXPONENTIAL_FAMILY", "LOCATION_SCALE_FAMILY", "NONE"]


def _cr12_conjugate_pair(pid: str) -> CanonicalSemanticObject:
    r = _rng(pid)
    a, b = r.choice([(2, 3), (1, 4), (5, 2), (3, 3)])
    n = r.choice([12, 18, 24, 30])
    k = r.randint(2, n - 2)
    _register(V1Facts(pid, "concept_recognition", licensed_concepts=("ConjugatePair",),
                      v0_expressible="yes",
                      v0_expressible_reason="V0 expresses both laws directly",
                      diagnostic_for_layer="concept_registry"))
    return _cso(
        pid, "concept_recognition", "medium",
        prose=(
            f"A parameter theta in [0,1] is given a Beta prior with shape parameters {a} "
            f"and {b}. Conditional on theta, a count of successes in {n} independent "
            f"trials is Binomial. After observing {k} successes the posterior for theta is "
            f"again a Beta distribution, with shape parameters {a + k} and {b + n - k}."
        ),
        question=f"{_CR_QUESTION}\nOptions: {', '.join(_CR_OPTIONS_L)}",
        answer=AnswerSpec(
            "choice", "CONJUGATE_PAIR", options=_CR_OPTIONS_L,
            justification="the posterior lies in the prior's family, which is exactly "
                          "conjugacy; both families are also exponential families, but "
                          "that is not the structure the display exhibits",
        ),
        distractors=["naming EXPONENTIAL_FAMILY, true of each family separately but not "
                     "the relation being displayed"],
        semantics=SemanticFacts(
            entities={"theta": "Probability", "trials": "Natural", "successes": "Natural"},
            declaration_kinds={"theta": "param", "trials": "obs", "successes": "obs"},
            laws={"theta": {"alpha": str(a), "beta": str(b)},
                  "successes": {"trials": "trials", "prob": "theta"}},
            law_families={"theta": "Beta", "successes": "Binomial"},
            conditioning={"successes": ["theta"]},
        ),
        reference_hml=(
            f"module ConjugatePair\n\nparam theta : Probability\n"
            f"obs trials : Natural = {n}\nobs successes : Natural = {k}\n\n"
            f"prior theta ~ Beta(alpha := {a}, beta := {b})\n"
            f"likelihood successes | theta ~ Binomial(trials := trials, prob := theta)\n"
        ),
        generator="_cr12_conjugate_pair",
    )


# ===========================================================================
# BLOCK 2 — concept-family derivation (12)
# ===========================================================================
#
# All twelve use the declared Estimation family of `docs/design/V1_KERNEL.md` §5:
# procedure / estimator / estimate / sampling_law / standard_error. The block tests the
# one confusion V1 claims to make a type error — "the estimate is unbiased".

_FAMILY_OPTIONS = ["PROCEDURE", "ESTIMATOR", "ESTIMATE", "SAMPLING_LAW",
                   "STANDARD_ERROR", "NONE"]

_FAMILY_PREAMBLE = (
    "The Estimation family has five distinct members:\n"
    "  procedure       the algorithm, defined without reference to any sample\n"
    "  estimator       a function from samples to the parameter space\n"
    "  estimate        the value obtained by applying the estimator to ONE sample\n"
    "  sampling_law    the distribution of the estimator under repeated sampling\n"
    "  standard_error  the standard deviation of the sampling law\n"
)

_FAMILY_QUESTION = (
    "Which single family member does the stated property attach to? Answer with one of "
    "PROCEDURE, ESTIMATOR, ESTIMATE, SAMPLING_LAW, STANDARD_ERROR, or NONE if the "
    "property attaches to no member as stated."
)


def _family_item(
    pid: str, difficulty: str, body: str, member: str, why: str, lure: str,
) -> CanonicalSemanticObject:
    _register(V1Facts(
        pid, "family_derivation", family_member=member,
        licensed_concepts=("Estimation",),
        v0_expressible="no",
        v0_expressible_reason="V0 has one flat namespace: procedure, estimator, estimate "
                              "and sampling law are all just declarations, so the "
                              "distinction cannot be stated, let alone checked",
        diagnostic_for_layer="concept_families",
    ))
    return _cso(
        pid, "family_derivation", difficulty,
        prose=f"{_FAMILY_PREAMBLE}\n{body}",
        question=_FAMILY_QUESTION,
        answer=AnswerSpec("choice", member, options=_FAMILY_OPTIONS, justification=why),
        distractors=[lure],
        generator="_family_item",
    )


def _fd_items() -> list[CanonicalSemanticObject]:
    out: list[CanonicalSemanticObject] = []
    r = _rng("fd_block")
    v = round(r.uniform(0.2, 0.9), 3)
    n = r.choice([25, 40, 64, 100])

    out.append(_family_item(
        "fd01_unbiasedness", "medium",
        "Consider the property: its expectation equals theta for every value of theta.",
        "ESTIMATOR",
        "unbiasedness is a statement about an expectation over samples, so it is a "
        "property of the function, not of any single realised number",
        "attaching unbiasedness to the ESTIMATE, which is one number and has no "
        "expectation over samples",
    ))
    out.append(_family_item(
        "fd02_realised_value", "easy",
        f"Consider the property: it takes the numerical value {v} for the sample that "
        f"was actually drawn.",
        "ESTIMATE",
        "a realised number obtained from one sample is exactly the estimate",
        "attaching a realised number to the ESTIMATOR",
    ))
    out.append(_family_item(
        "fd03_sd_of_what", "medium",
        "Consider the property: the standard error is its standard deviation.",
        "SAMPLING_LAW",
        "the standard error is by definition the standard deviation of the sampling law",
        "answering STANDARD_ERROR, which is the quantity asked about rather than the "
        "member it is a standard deviation of",
    ))
    out.append(_family_item(
        "fd04_consistency", "medium",
        f"Consider the property: as the sample size grows past {n}, it converges in "
        f"probability to theta.",
        "ESTIMATOR",
        "convergence in probability is a statement about a sequence of functions of the "
        "sample",
        "attaching consistency to the ESTIMATE, a fixed number that cannot converge",
    ))
    out.append(_family_item(
        "fd05_defined_before_data", "easy",
        "Consider the property: it is fully specified before any data are collected, and "
        "specifying it requires no sample.",
        "PROCEDURE",
        "the algorithm is the member that exists independently of any sample",
        "answering ESTIMATOR; the estimator is a function OF a sample, so it is "
        "sample-indexed even though it is not sample-valued",
    ))
    out.append(_family_item(
        "fd06_mse_decomposition", "hard",
        "Consider the property: its mean squared error decomposes as squared bias plus "
        "variance.",
        "ESTIMATOR",
        "both terms are expectations over repeated samples, so the object they describe "
        "is the function",
        "attaching the decomposition to the SAMPLING_LAW; the law is the distribution, "
        "the decomposition is a property of the estimator whose law it is",
    ))
    out.append(_family_item(
        "fd07_coverage", "hard",
        "Consider the property: it produces an interval containing theta in 95% of "
        "repeated applications.",
        "PROCEDURE",
        "coverage is a frequency over repeated applications of the algorithm",
        "attaching coverage to the ESTIMATE or to a realised interval, which either "
        "contains theta or does not",
    ))
    out.append(_family_item(
        "fd08_realised_interval", "hard",
        f"Consider the property: 'there is a 95% probability that theta lies between "
        f"{v} and {round(v + 0.15, 3)}', where both endpoints are numbers computed from "
        f"the sample that was drawn.",
        "NONE",
        "a realised interval with numeric endpoints either contains theta or does not; "
        "the 95% attaches to the procedure's coverage, so as stated the property "
        "attaches to no member",
        "answering PROCEDURE, which is the member coverage attaches to but not what the "
        "quoted sentence asserts",
    ))
    out.append(_family_item(
        "fd09_efficiency", "medium",
        "Consider the property: among all unbiased alternatives it has the smallest "
        "variance.",
        "ESTIMATOR",
        "a comparison of variances across a class of functions of the sample",
        "answering SAMPLING_LAW, which carries the variance but is not the thing being "
        "compared across alternatives",
    ))
    out.append(_family_item(
        "fd10_asymptotic_normality", "medium",
        f"Consider the property: after centring at theta and multiplying by the square "
        f"root of the sample size, it converges to a normal distribution as the sample "
        f"size passes {n}.",
        "SAMPLING_LAW",
        "the object that converges to a normal distribution is a distribution",
        "answering ESTIMATOR; the estimator is the function whose law converges, but the "
        "convergent object named in the sentence is the law",
    ))
    out.append(_family_item(
        "fd11_plug_in_rule", "easy",
        "Consider the property: it is the instruction 'replace each population moment by "
        "the corresponding sample moment and solve'.",
        "PROCEDURE",
        "an instruction stated without reference to a sample is the algorithm",
        "answering ESTIMATOR, the object the instruction produces once a sample exists",
    ))
    out.append(_family_item(
        "fd12_reported_number", "medium",
        "Consider the property: it is the number reported in the results table, "
        "alongside its standard error, for the study's single data set.",
        "ESTIMATE",
        "one number from one sample",
        "answering ESTIMATOR because the table's column header names the method",
    ))
    return out


# ===========================================================================
# BLOCK 3 — recurring unnamed structure (12)
# ===========================================================================
#
# Four displays per item, drawn from a pool of three structurally distinct variants of
# one motif, rendered with fresh symbols and constants. The answer is the number of
# distinct structures present, and it is COMPUTED from the draw rather than typed.
# This is the block that tests compression: the point of minting a concept is that a
# structure recurs, and recognising recurrence is the precondition.

_STRUCT_QUESTION = (
    "How many structurally distinct relations are shown? Two displays count as the same "
    "structure when one can be obtained from the other by renaming symbols and changing "
    "numerical constants; they count as different when the relation between the "
    "quantities differs. Answer with a single integer between 1 and 4."
)

#: motif name -> FOUR structurally distinct variant templates.
#: Placeholders: {a} {b} {c} {x} {y} {t} {n} {k}.
#:
#: Four variants, not three, so that the answer can be any of 1, 2, 3 or 4 and the
#: guessing floor on this block is 25% rather than 33%. The variants within a motif are
#: deliberately near-neighbours: they concern the same quantities and read similarly, and
#: they assert different relations between them.
_MOTIFS: list[tuple[str, str, tuple[str, str, str, str]]] = [
    ("conjugate_update", "posterior hyperparameters after observing data", (
        "{a}_post = {a} + {k}   and   {b}_post = {b} + {n} - {k}",
        "{a}_post = {a} * {k}   and   {b}_post = {b} * ({n} - {k})",
        "{a}_post = ({n}*{x} + {k}*{a}) / ({n} + {k})   (a weighted average of {a} and {x})",
        "{a}_post = {a} + {k}   and   {b}_post = {b}   (only one hyperparameter moves)",
    )),
    ("reparameterisation", "a change of parameter in a density", (
        "g({x}) = (1/{b}) * f(({x} - {a}) / {b})",
        "g({x}) = {b} * f({b} * {x} - {a})",
        "g({x}) = f({x} - {a}) + {b}",
        "g({x}) = f({x}) / integral f   (renormalisation, no argument is moved)",
    )),
    ("fixed_point", "an iteration and its limit", (
        "{x}_{{n+1}} = {a} * {x}_n + {b},   |{a}| < 1,   limit = {b} / (1 - {a})",
        "{x}_{{n+1}} = {a} * {x}_n * (1 - {x}_n),   limit satisfies {x} = {a}*{x}*(1-{x})",
        "{x}_{{n+1}} = {x}_n - f({x}_n) / f'({x}_n),   limit satisfies f({x}) = 0",
        "{x}_{{n+1}} = {a} / {x}_n,   the sequence has period 2 and does not converge",
    )),
    ("telescoping", "a sum or product over an index range", (
        "sum_{{{i}=1}}^{{{n}}} ({a}_{{{i}+1}} - {a}_{i}) = {a}_{{{n}+1}} - {a}_1",
        "sum_{{{i}=1}}^{{{n}}} {a}_{i} * {b}_{i}   where neither factor telescopes",
        "prod_{{{i}=1}}^{{{n}}} ({a}_{{{i}+1}} / {a}_{i}) = {a}_{{{n}+1}} / {a}_1",
        "sum_{{{i}=1}}^{{{n}}} {a}_{i} = ({n}/2) * ({a}_1 + {a}_{{{n}}})   "
        "for an arithmetic sequence",
    )),
    ("tail_bound", "a bound on a tail probability", (
        "P(|{x} - E[{x}]| >= {k}*{a}) <= 1 / {k}^2,   {a} = sd({x})",
        "P({x} >= {k}) <= E[{x}] / {k},   {x} >= 0",
        "P(union of {n} events) <= sum of the {n} individual probabilities",
        "P({x} >= {k}) <= exp(-{a}*{k}) * E[exp({a}*{x})],   {a} > 0",
    )),
    ("tower_property", "an expectation taken in stages", (
        "E[{x}] = E[ E[{x} | {y}] ]",
        "Var({x}) = E[Var({x} | {y})] + Var(E[{x} | {y}])",
        "E[{x} * {y}] = E[{x}] * E[{y}]   when {x} and {y} are independent",
        "E[{x} | {y}] = {x}   when {x} is a function of {y}",
    )),
    ("stationarity", "an optimality condition", (
        "grad f({x}) + {a} * grad g({x}) = 0   with g({x}) = 0",
        "f'({x}) = 0   and   f''({x}) > 0",
        "f({x} + h) - f({x}) >= grad f({x}) . h   for all h",
        "f({x}*) <= f({x})   for every {x} in the feasible set",
    )),
    ("log_partition", "an identity for a parametric family", (
        "d/d{a} A({a}) = E_{a}[T({x})]",
        "d^2/d{a}^2 A({a}) = Var_{a}(T({x}))",
        "A({a}) = log integral h({x}) exp({a} * T({x})) d{x}",
        "A({a}) is convex in {a}",
    )),
    ("change_of_variables", "a density after a map", (
        "p_{y}({y}) = p_{x}(w({y})) * |w'({y})|",
        "p_{y}({y}) = p_{x}(w({y}))",
        "E[u({y})] = integral u(v({x})) p_{x}({x}) d{x}",
        "p_{y}({y}) = sum over the branches j of p_{x}(w_j({y})) * |w_j'({y})|",
    )),
    ("inclusion_exclusion", "the size of a combination of sets", (
        "|{x} u {y}| = |{x}| + |{y}| - |{x} n {y}|",
        "|{x} u {y}| = |{x}| + |{y}|   when {x} n {y} is empty",
        "|{x} u {y}| <= |{x}| + |{y}|",
        "|{x} \\ {y}| = |{x}| - |{x} n {y}|",
    )),
    ("orthogonal_projection", "a property of a projection onto a subspace", (
        "<{x} - {op}{x}, {y}> = 0   for every {y} in the subspace",
        "||{x}||^2 = ||{op}{x}||^2 + ||{x} - {op}{x}||^2",
        "{op}({a}*{x} + {b}*{y}) = {a}*{op}{x} + {b}*{op}{y}",
        "{op}({op}{x}) = {op}{x}",
    )),
    ("convolution", "the law of a sum of independent variables", (
        "p_{{{x}+{y}}}({c}) = integral p_{x}({t}) p_{y}({c} - {t}) d{t}",
        "M_{{{x}+{y}}}({t}) = M_{x}({t}) * M_{y}({t})",
        "E[{x} + {y}] = E[{x}] + E[{y}]   with no independence needed",
        "Var({x} + {y}) = Var({x}) + Var({y})   when {x} and {y} are independent",
    )),
]

#: How many distinct structures each of the twelve items carries. Balanced three ways
#: each so that no constant answer beats 25%, then permuted once under a fixed seed so
#: the schedule is not aligned with motif order.
_STRUCT_TARGETS: list[int] = (
    lambda s: (s.shuffle(t := [1, 2, 3, 4] * 3), t)[1]
)(random.Random("hml-v1-ablation::struct-schedule"))


def _struct_item(
    index: int, motif: tuple[str, str, tuple[str, str, str, str]]
) -> CanonicalSemanticObject:
    name, what, variants = motif
    pid = f"rs{index:02d}_{name}"
    r = _rng(pid)
    # The number of distinct structures is fixed by the balanced schedule; which variants
    # realise it, and in what order, is drawn. The answer is COMPUTED from the draw.
    target = _STRUCT_TARGETS[index - 1]
    chosen = r.sample([0, 1, 2, 3], target)
    draw = list(chosen) + [r.choice(chosen) for _ in range(4 - target)]
    r.shuffle(draw)
    distinct = len(set(draw))
    assert distinct == target, (pid, draw, target)

    # EVERY symbol and constant is redrawn per display, and no two displays may render to
    # the same string. Without this, two displays of the same variant render
    # byte-identically and the item is answerable by string equality rather than by
    # structure -- which is the one thing this block must not be. Exhausting the retries
    # is a corpus defect and is raised, not silently accepted.
    def _render(vi: int) -> str:
        greek = r.sample(_SYMS, 3)
        caps = r.sample(["X", "Y", "Z", "U", "V", "W"], 2)
        return variants[vi].format(
            a=greek[0], b=greek[1], c=greek[2],
            x=caps[0], y=caps[1],
            i=r.choice(["i", "j", "m", "r"]),
            op=r.choice(["P", "Q", "R", "S"]),
            t=r.choice(["t", "s", "u"]),
            n=r.choice([5, 7, 9, 11, 13, 15]),
            k=r.choice([2, 3, 4, 6, 8]),
        )

    bodies: list[str] = []
    for vi in draw:
        for _ in range(200):
            text = _render(vi)
            if text not in bodies:
                bodies.append(text)
                break
        else:  # pragma: no cover - a corpus defect, not a runtime condition
            raise AssertionError(
                f"{pid}: could not render four surface-distinct displays; variant {vi} "
                f"has too few free symbols for this block to be about structure"
            )
    displays = [f"  ({j})  {b}" for j, b in enumerate(bodies, 1)]

    _register(V1Facts(
        pid, "recurring_structure",
        v0_expressible="partial",
        v0_expressible_reason="V0 can encode each display; it has no way to assert that "
                              "two displays share one structure, which is the question",
        diagnostic_for_layer="concept_minting",
    ))
    return _cso(
        pid, "recurring_structure", "hard",
        prose=(
            f"Four displays, each stating {what}. Symbol names and numerical constants "
            f"differ between displays and carry no information.\n\n" + "\n".join(displays)
        ),
        question=_STRUCT_QUESTION,
        answer=AnswerSpec(
            "numeric", float(distinct), tolerance=1e-9,
            justification=f"variant indices drawn were {draw}; {distinct} distinct",
        ),
        distractors=["answering 4 because all four displays are written differently",
                     "answering 1 because all four displays are about the same topic"],
        generator="_struct_item",
    )


# ===========================================================================
# BLOCK 4 — transformation chains (12)
# ===========================================================================
#
# Each item is a numbered chain of steps, each with a stated justification. The answer is
# the 1-based index of the FIRST step whose stated justification does not hold, or 0 when
# the chain is wholly valid. Four of twelve chains are valid, so "find the bug" is
# punished; a model that always reports a fault scores 8/12 at best on this block.

_CHAIN_QUESTION = (
    "Give the 1-based index of the first step whose stated justification does not hold. "
    "If every step's justification holds, answer 0. Answer with a single integer."
)

#: (id, difficulty, [(step text, justification)], first_invalid_index, why, lure)
_CHAINS: list[tuple[str, str, list[tuple[str, str]], int, str, str]] = [
    (
        "tc01_divide_by_possibly_zero", "medium",
        [("from a*x = a*y, conclude x = y", "divide both sides by a"),
         ("from x = y, conclude x - y = 0", "subtract y from both sides"),
         ("from x - y = 0, conclude (x-y)^2 = 0", "square both sides")],
        1,
        "dividing by a requires a != 0, which is nowhere established",
        "accepting step 1 because cancelling a common factor looks routine",
    ),
    (
        "tc02_cancel_vanishing_factor", "medium",
        [("expand (x-3)*(x+1) = (x-3)*(2x-5)", "expand both products"),
         ("cancel the factor (x-3)", "the factor appears on both sides"),
         ("solve x + 1 = 2x - 5 to get x = 6", "rearrange for x")],
        2,
        "cancelling (x-3) requires x != 3, and x = 3 is a solution of the original "
        "equation that this step silently discards",
        "reporting step 3, where the loss becomes visible, rather than step 2, where "
        "it is committed",
    ),
    (
        "tc03_square_treated_as_equivalence", "hard",
        [("from sqrt(x+2) = x, square both sides", "equivalently, x + 2 = x^2"),
         ("rearrange to x^2 - x - 2 = 0", "collect terms"),
         ("factor to (x-2)(x+1) = 0, so x = 2 or x = -1", "a product is zero when a "
          "factor is zero")],
        1,
        "squaring is not reversible: it is a weakening, not an equivalence, and the word "
        "'equivalently' is the false claim. x = -1 satisfies the squared equation and "
        "not the original",
        "accepting step 1 because the algebra is correct in the forward direction",
    ),
    (
        "tc04_differentiate_at_a_corner", "medium",
        [("define f(x) = |x| on the reals", "a definition"),
         ("observe that f attains its minimum over the reals at x = 0",
          "f(0) = 0 and f(x) > 0 for x != 0"),
         ("conclude f'(0) = 0", "at an interior minimum a differentiable function has "
          "zero derivative")],
        3,
        "the rule quoted in step 3 requires differentiability at the point; |x| is not "
        "differentiable at 0, so f'(0) does not exist and the conclusion has no referent. "
        "Steps 1 and 2 are both sound",
        "reporting step 2, which is a true statement about the minimum",
    ),
    (
        "tc05_valid_chain", "medium",
        [("from y = 2*x + 1 and x = 3, substitute x into the first", "substitution"),
         ("obtain y = 2*3 + 1", "evaluate the substituted expression"),
         ("conclude y = 7", "arithmetic")],
        0,
        "substitution generates no side condition and the arithmetic is correct",
        "inventing a fault because the block usually contains one",
    ),
    (
        "tc06_log_of_possibly_nonpositive", "medium",
        [("from a*b = c with a, b, c real and all non-zero, divide both sides by b",
          "b != 0 is given"),
         ("obtain a = c/b", "simplify the quotient"),
         ("take logarithms to obtain log a = log c - log b", "log turns quotients into "
          "differences")],
        3,
        "log is defined only on the positive reals; the premise gives non-zero, not "
        "positive, so a, b and c may be negative. The division in step 1 is safe, which "
        "is what makes step 3 the first failure",
        "reporting step 1 by analogy with the other division cases, although b != 0 is "
        "explicitly given",
    ),
    (
        "tc07_limit_sum_exchange", "hard",
        [("write S_n(x) = sum_{i=1}^{n} f_i(x), with every f_i continuous",
          "a definition"),
         ("observe that each partial sum S_n is continuous",
          "a finite sum of continuous functions is continuous"),
         ("conclude that the limit function S(x) = lim_n S_n(x) is continuous",
          "a limit of continuous functions is continuous")],
        3,
        "pointwise convergence does not preserve continuity; the quoted rule needs "
        "uniform convergence, which is never established. Steps 1 and 2 are both correct, "
        "and step 2's rule is genuinely a finite-sum theorem",
        "reporting step 2, whose finite-sum rule is correctly stated and correctly used",
    ),
    (
        "tc08_valid_chain_two", "medium",
        [("from x^2 - 5*x + 6 = 0, factor", "a polynomial identity, valid for all x"),
         ("obtain (x-2)*(x-3) = 0", "expand to check"),
         ("conclude x = 2 or x = 3", "a real product is zero only when a factor is zero")],
        0,
        "factoring is an identity and the zero-product step is unconditionally valid "
        "over the reals",
        "flagging step 3 by analogy with the cancellation cases",
    ),
    (
        "tc09_sqrt_drops_a_branch", "medium",
        [("from x^2 = 49, take square roots", "square-rooting both sides"),
         ("obtain x = 7", "the square root of 49 is 7"),
         ("substitute x = 7 into the next equation", "substitution")],
        2,
        "sqrt of both sides yields |x| = 7, a two-branch case split; step 2 keeps one "
        "branch and drops x = -7 without a case analysis",
        "reporting step 1: taking roots is legitimate, it is the unique-branch claim in "
        "step 2 that fails",
    ),
    (
        "tc10_rearrange_not_isolable", "hard",
        [("from x * exp(x) = k, isolate x", "rearrange for x"),
         ("obtain x = k / exp(x)", "divide both sides by exp(x)"),
         ("substitute the right-hand side into itself once", "substitution")],
        1,
        "x is not isolable in closed form in x*exp(x) = k; the stated justification "
        "'rearrange for x' asserts an isolability side condition that fails",
        "accepting step 1 and reporting step 2, whose division by exp(x) is in fact safe "
        "because exp is never zero",
    ),
    (
        "tc11_integrate_over_a_singularity", "hard",
        [("define g(x) = 1/x on [-1, 1] excluding 0", "a definition"),
         ("integrate g over [-1, 1]", "g is integrable over the interval"),
         ("conclude the integral is 0 by symmetry", "g is an odd function")],
        2,
        "1/x is not integrable over an interval containing 0; the symmetry argument in "
        "step 3 is applied to a quantity that does not exist",
        "reporting step 3, which is where the wrong answer appears, rather than step 2, "
        "where the false side condition is asserted",
    ),
    (
        "tc12_valid_chain_three", "hard",
        [("from a > b and c > 0, multiply both sides by c", "multiplying an inequality by "
          "a positive quantity preserves its direction"),
         ("obtain a*c > b*c", "the product is strictly larger"),
         ("add d to both sides", "adding the same quantity to both sides preserves the "
          "inequality")],
        0,
        "positivity of c is given, so the order-preserving side condition holds; "
        "translation preserves order unconditionally",
        "flagging step 1 by analogy with the division cases, although c > 0 is stated",
    ),
]


def _chain_items() -> list[CanonicalSemanticObject]:
    out = []
    for pid, difficulty, steps, first_bad, why, lure in _CHAINS:
        body = "\n".join(
            f"  step {i}:  {text}\n           justification: {just}"
            for i, (text, just) in enumerate(steps, 1)
        )
        _register(V1Facts(
            pid, "transformation_chain", first_invalid_step=first_bad,
            v0_expressible="no",
            v0_expressible_reason="V0 has no transformation edge and no side-condition "
                                  "obligation, so a chain of steps cannot be written down "
                                  "as steps at all",
            diagnostic_for_layer="L2_transformation",
        ))
        out.append(_cso(
            pid, "transformation_chain", difficulty,
            prose="A derivation is presented as numbered steps, each with its stated "
                  "justification.\n\n" + body,
            question=_CHAIN_QUESTION,
            answer=AnswerSpec("numeric", float(first_bad), tolerance=1e-9,
                              justification=why),
            distractors=[lure],
            generator="_chain_items",
        ))
    return out


# ===========================================================================
# BLOCK 5 — epistemic calibration (12)   [the highest-value block]
# ===========================================================================
#
# `docs/design/V1_KERNEL.md` §3: L4 exists mainly to make one error unrepresentable —
# "fail to reject H0" must never compile to "H0 is proved" or "there is no effect".
# Seven of the twelve items below have as their correct answer that the evidence does
# NOT support a conclusion. Every one of those items offers at least three fluent wrong
# readings, because an item whose only wrong option is obviously wrong measures nothing.

_EP_QUESTION = (
    "Which single statement is the correct reading of the situation above? Answer with "
    "exactly one of the listed labels."
)


def _ep_item(
    pid: str, difficulty: str, body: str, options: list[str], correct: str,
    why: str, lure: str, status: str, prohibited: tuple[str, ...],
    layer: str = "L4_epistemic",
) -> CanonicalSemanticObject:
    _register(V1Facts(
        pid, "epistemic_calibration", epistemic_status=status,
        prohibited_statuses=prohibited,
        v0_expressible="no",
        v0_expressible_reason="V0 has no epistemic status: `prove`, `assume` and `require` "
                              "carry no justification type, so every reading below has the "
                              "same V0 encoding",
        diagnostic_for_layer=layer,
    ))
    return _cso(
        pid, "epistemic_calibration", difficulty,
        prose=body,
        question=f"{_EP_QUESTION}\nOptions: {', '.join(options)}",
        answer=AnswerSpec("choice", correct, options=options, justification=why),
        distractors=[lure],
        generator="_ep_item",
    )


def _ep_items() -> list[CanonicalSemanticObject]:
    r = _rng("ep_block")
    out = []

    p1 = round(r.uniform(0.11, 0.42), 3)
    out.append(_ep_item(
        "ep01_fail_to_reject", "medium",
        f"A two-sided test of H0: mu = 0 against H1: mu != 0 is run at the 5% level. "
        f"The p-value is {p1}. The null is not rejected.",
        ["H0_IS_TRUE", "NO_EFFECT_EXISTS", "H0_IS_PROVED",
         "INSUFFICIENT_EVIDENCE_AGAINST_H0", "H1_IS_ESTABLISHED"],
        "INSUFFICIENT_EVIDENCE_AGAINST_H0",
        "a non-rejection is the absence of evidence against H0; it is not evidence for "
        "H0, and no amount of it becomes a proof",
        "reading a non-rejection as support for the null",
        "fail_to_reject", ("proved", "disproved", "definitionally_true"),
    ))

    p2 = round(r.uniform(0.012, 0.045), 3)
    out.append(_ep_item(
        "ep02_p_value_is_not_a_posterior", "hard",
        f"A test yields a p-value of {p2}. A colleague writes: 'the probability that H0 "
        f"is true given the data is {p2}'.",
        ["THE_COLLEAGUE_IS_CORRECT",
         "P_IS_THE_PROBABILITY_OF_DATA_AT_LEAST_AS_EXTREME_UNDER_H0",
         "P_IS_THE_PROBABILITY_H1_IS_TRUE",
         "P_IS_ONE_MINUS_THE_POWER"],
        "P_IS_THE_PROBABILITY_OF_DATA_AT_LEAST_AS_EXTREME_UNDER_H0",
        "a p-value is a tail probability computed UNDER H0; a posterior probability of "
        "H0 requires a prior and Bayes' rule, and there is no coercion between them",
        "reading the p-value as a posterior probability of the null",
        "reject", ("proved", "estimated"),
    ))

    p3 = round(r.uniform(0.0002, 0.004), 4)
    out.append(_ep_item(
        "ep03_rejection_does_not_prove_h1", "medium",
        f"A test of H0 against H1 at the 1% level yields p = {p3}. H0 is rejected.",
        ["H1_IS_PROVED", "H0_IS_DISPROVED",
         "EVIDENCE_AGAINST_H0_AT_THE_STATED_LEVEL",
         "THE_EFFECT_SIZE_IS_LARGE"],
        "EVIDENCE_AGAINST_H0_AT_THE_STATED_LEVEL",
        "rejecting at a level is evidence, not refutation, and it says nothing about the "
        "magnitude of any effect",
        "reading a small p-value as a proof of the alternative",
        "reject", ("proved", "disproved"),
    ))

    n4 = r.choice([6, 8, 9, 11])
    out.append(_ep_item(
        "ep04_underpowered_null", "hard",
        f"A trial with {n4} participants per arm finds no significant difference "
        f"(p = 0.61). The authors conclude that the two treatments are equivalent. A "
        f"power calculation shows the study could only detect differences more than "
        f"three times the size clinicians consider meaningful.",
        ["EQUIVALENCE_IS_ESTABLISHED", "THE_TREATMENTS_DIFFER",
         "THE_STUDY_CANNOT_DISTINGUISH_THE_TREATMENTS",
         "THE_NULL_IS_MORE_LIKELY_THAN_THE_ALTERNATIVE"],
        "THE_STUDY_CANNOT_DISTINGUISH_THE_TREATMENTS",
        "an underpowered non-rejection carries almost no information; concluding "
        "equivalence from it is the absence-of-evidence error, and an equivalence claim "
        "requires an equivalence test with a stated margin",
        "concluding equivalence from a non-significant result",
        "fail_to_reject", ("proved", "definitionally_true"),
    ))

    lo = round(r.uniform(-0.09, -0.01), 3)
    hi = round(r.uniform(0.30, 0.55), 3)
    out.append(_ep_item(
        "ep05_interval_contains_zero", "medium",
        f"A 95% confidence interval for a difference in means is [{lo}, {hi}]. It "
        f"contains 0.",
        ["THE_DIFFERENCE_IS_ZERO", "THERE_IS_NO_EFFECT",
         "ZERO_IS_NOT_EXCLUDED_AT_THE_STATED_LEVEL",
         "THE_PROBABILITY_THE_DIFFERENCE_IS_ZERO_IS_0.95"],
        "ZERO_IS_NOT_EXCLUDED_AT_THE_STATED_LEVEL",
        "an interval containing zero excludes nothing; the interval is also consistent "
        f"with a difference as large as {hi}, so 'no effect' is not what it says",
        "reading an interval that contains zero as establishing zero",
        "fail_to_reject", ("proved", "definitionally_true"),
    ))

    out.append(_ep_item(
        "ep06_almost_sure_is_not_pointwise", "hard",
        "A sequence of random variables Z_n converges to Z almost surely with respect to "
        "the probability measure P.",
        ["Z_N_CONVERGES_AT_EVERY_OUTCOME",
         "CONVERGENCE_HOLDS_OUTSIDE_A_SET_OF_MEASURE_ZERO",
         "THE_QUALIFIER_ALMOST_SURELY_MAY_BE_DROPPED",
         "CONVERGENCE_IS_ONLY_IN_PROBABILITY"],
        "CONVERGENCE_HOLDS_OUTSIDE_A_SET_OF_MEASURE_ZERO",
        "almost-sure is a measure-1 qualifier and is not removable; there may be "
        "outcomes at which the sequence does not converge",
        "dropping the almost-sure qualifier as a technicality",
        "almost_sure", ("proved",),
    ))

    eps = round(r.uniform(0.01, 0.2), 3)
    out.append(_ep_item(
        "ep07_whp_without_a_regime", "hard",
        f"A paper states: 'with high probability the estimator is within {eps} of the "
        f"true value'. No sample size, no bound and no asymptotic regime is given "
        f"anywhere in the statement.",
        ["THE_CLAIM_HOLDS_WITH_PROBABILITY_AT_LEAST_0.95",
         "THE_CLAIM_IS_NOT_WELL_FORMED_WITHOUT_A_REGIME",
         "THE_CLAIM_HOLDS_ALMOST_SURELY",
         "THE_CLAIM_IS_A_STATEMENT_ABOUT_ONE_SAMPLE"],
        "THE_CLAIM_IS_NOT_WELL_FORMED_WITHOUT_A_REGIME",
        "'with high probability' names a limit of a probability along a regime; with no "
        "regime and no explicit bound there is no proposition to evaluate",
        "supplying a conventional 0.95 that the statement does not contain",
        "with_high_probability", ("proved", "almost_sure"),
    ))

    q = round(r.uniform(0.6, 0.9), 2)
    out.append(_ep_item(
        "ep08_credence_is_not_probability", "medium",
        f"An analyst writes: 'I am {int(q*100)}% confident that this regression model is "
        f"correctly specified.'",
        ["A_PROBABILITY_COMPUTED_WITHIN_THE_MODEL",
         "A_DEGREE_OF_BELIEF_ABOUT_THE_MODEL",
         "THE_MODEL_R_SQUARED", "A_POSTERIOR_PREDICTIVE_PROBABILITY"],
        "A_DEGREE_OF_BELIEF_ABOUT_THE_MODEL",
        "a credence about a model sits outside that model's probability space; it is not "
        "a measure within it and cannot be combined with the model's own probabilities",
        "treating a stated confidence in a model as a probability inside it",
        "possible", ("proved", "estimated"),
    ))

    out.append(_ep_item(
        "ep09_assumption_does_not_discharge", "medium",
        "A result R is derived under the working assumption A, which is not established "
        "anywhere in the document. The goal of the section is to show R.",
        ["THE_GOAL_IS_DISCHARGED", "THE_GOAL_IS_DISCHARGED_IF_A_IS_PLAUSIBLE",
         "THE_GOAL_REMAINS_OPEN_AND_A_IS_A_DEPENDENCY",
         "THE_GOAL_IS_DISCHARGED_BECAUSE_THE_DERIVATION_IS_VALID"],
        "THE_GOAL_REMAINS_OPEN_AND_A_IS_A_DEPENDENCY",
        "an assumption is granted, not established; a derivation under it establishes the "
        "conditional, and the goal as stated is unconditional",
        "treating a valid derivation from an unestablished premise as a proof of the "
        "conclusion",
        "model_conditional", ("proved",),
        layer="L5_discourse",
    ))

    m = r.choice([18, 20, 24, 30])
    out.append(_ep_item(
        "ep10_multiplicity", "hard",
        f"{m} independent hypothesis tests are run at the 5% level on the same data set. "
        f"Exactly one returns p = 0.04 and is reported as the study's finding. No "
        f"correction for multiplicity is applied.",
        ["THE_FINDING_IS_ESTABLISHED_AT_THE_5_PERCENT_LEVEL",
         "THE_RESULT_IS_UNSURPRISING_UNDER_THE_GLOBAL_NULL",
         "THE_OTHER_TESTS_CONFIRM_THEIR_NULLS",
         "THE_FAMILYWISE_ERROR_RATE_IS_STILL_5_PERCENT"],
        "THE_RESULT_IS_UNSURPRISING_UNDER_THE_GLOBAL_NULL",
        f"under the global null the expected number of rejections at the 5% level among "
        f"{m} tests is about {round(m*0.05, 2)}, so one is exactly what chance predicts; "
        f"the per-test level is not the familywise level",
        "reporting the single significant test as if its stated level applied",
        "fail_to_reject", ("proved", "reject"),
    ))

    out.append(_ep_item(
        "ep11_absence_of_evidence", "medium",
        "A systematic review finds no study reporting an association between exposure E "
        "and outcome O. Only two small studies have ever examined the question, and "
        "neither was powered to detect an association.",
        ["NO_ASSOCIATION_EXISTS", "THE_ASSOCIATION_IS_DISPROVED",
         "THE_QUESTION_IS_UNRESOLVED_BY_THE_AVAILABLE_EVIDENCE",
         "THE_ASSOCIATION_IS_UNLIKELY_GIVEN_THE_REVIEW"],
        "THE_QUESTION_IS_UNRESOLVED_BY_THE_AVAILABLE_EVIDENCE",
        "no study reporting an association is not a study reporting no association; with "
        "two underpowered studies the evidence base cannot support either direction",
        "reading a silent literature as a negative literature",
        "unsupported", ("proved", "disproved"),
    ))

    eff = round(r.uniform(0.2, 0.6), 2)
    out.append(_ep_item(
        "ep12_model_conditional", "medium",
        f"Under a proportional-hazards model M, the estimated log hazard ratio is {eff}. "
        f"The proportional-hazards assumption is not tested anywhere in the paper. The "
        f"abstract reports the {eff} without mentioning M.",
        ["THE_ESTIMATE_IS_UNCONDITIONAL",
         "THE_ESTIMATE_HOLDS_ONLY_RELATIVE_TO_M_WHICH_IS_A_DEPENDENCY",
         "M_IS_ESTABLISHED_BY_THE_FIT",
         "THE_ESTIMATE_IS_PROVED_UNDER_M"],
        "THE_ESTIMATE_HOLDS_ONLY_RELATIVE_TO_M_WHICH_IS_A_DEPENDENCY",
        "a model-conditional claim carries the model as a dependency; dropping the model "
        "from the report converts a conditional claim into an unconditional one, and a "
        "good fit does not establish the assumption",
        "reporting a model-conditional estimate as if it were model-free",
        "model_conditional", ("proved", "definitionally_true"),
    ))
    return out


# ===========================================================================
# Corpus assembly
# ===========================================================================

_CR_BUILDERS = [
    ("cr01_scale_family", _cr01_scale_family),
    ("cr02_support_depends_on_parameter", _cr02_support_depends_on_parameter),
    ("cr03_quasiconvex", _cr03_quasiconvex),
    ("cr04_martingale_not_markov", _cr04_martingale_not_markov),
    ("cr05_sufficient_not_complete", _cr05_sufficient_not_complete),
    ("cr06_seminorm", _cr06_seminorm),
    ("cr07_pseudometric", _cr07_pseudometric),
    ("cr08_preorder", _cr08_preorder),
    ("cr09_monoid", _cr09_monoid),
    ("cr10_consistent_not_unbiased", _cr10_consistent_not_unbiased),
    ("cr11_algebra_of_sets", _cr11_algebra_of_sets),
    ("cr12_conjugate_pair", _cr12_conjugate_pair),
]

_CACHE: list[CanonicalSemanticObject] | None = None


def build_all_v1() -> list[CanonicalSemanticObject]:
    """The 60-problem ablation corpus. Deterministic; the same list on every call."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    _V1_FACTS.clear()
    out: list[CanonicalSemanticObject] = []
    for pid, fn in _CR_BUILDERS:
        out.append(fn(pid))
    out.extend(_fd_items())
    for i, motif in enumerate(_MOTIFS, 1):
        out.append(_struct_item(i, motif))
    out.extend(_chain_items())
    out.extend(_ep_items())
    _CACHE = out
    return out


def build_demos_v1() -> list[CanonicalSemanticObject]:
    """Two worked demonstrations, disjoint from the benchmark.

    Every arm receives the same two, rendered in its own notation. Giving demonstrations
    only to the treatment arms would measure demonstrations, not representation — the
    same rule `evaluation/corpus/renderers.py` enforces for the V0 experiment.
    """
    d1 = _cso(
        "demo1_family_member", "family_derivation", "easy",
        prose=(
            _FAMILY_PREAMBLE
            + "\nConsider the property: it is a function whose argument is a sample."
        ),
        question=_FAMILY_QUESTION,
        answer=AnswerSpec("choice", "ESTIMATOR", options=_FAMILY_OPTIONS,
                          justification="a function from samples is the estimator"),
        distractors=[], generator="build_demos_v1",
    )
    d2 = _cso(
        "demo2_chain", "transformation_chain", "easy",
        prose=(
            "A derivation is presented as numbered steps, each with its stated "
            "justification.\n\n"
            "  step 1:  from u = v, conclude u + 4 = v + 4\n"
            "           justification: add the same quantity to both sides\n"
            "  step 2:  from u + 4 = v + 4, conclude (u+4)/w = (v+4)/w\n"
            "           justification: divide both sides by w"
        ),
        question=_CHAIN_QUESTION,
        answer=AnswerSpec("numeric", 2.0, tolerance=1e-9,
                          justification="division by w requires w != 0, never established"),
        distractors=[], generator="build_demos_v1",
    )
    return [d1, d2]


# ===========================================================================
# Adversarial case table — the source of truth for tests/v1/test_adversarial_v1.py
# ===========================================================================


@dataclass
class AdversarialPair:
    """One thing V1 must reject, with the matched near-miss it must accept.

    Without the near-miss only recall is measurable, and a checker that rejects
    everything has perfect recall. `docs/design/V1_EXPERIMENT_PLAN.md` §5 (V1-H2) makes
    precision a preregistered hypothesis, so every rejection case here carries an
    acceptance twin that differs in the smallest way that makes it correct.
    """

    id: str
    layer: str
    #: What must be REJECTED, and why.
    reject_case: str
    reject_reason: str
    #: The matched near-miss that must be ACCEPTED, and why it is legitimate.
    accept_case: str
    accept_reason: str
    #: The V1 module and callable this case is written against. Empty when the case is
    #: checkable with the V0 compiler alone.
    required_interface: str = ""
    #: What V0 does today: "accepts" (a semantic hole), "rejects", or "not_expressible".
    #: Verified live by tests/v1/test_adversarial_v1.py where a V0 source exists.
    v0_status: Literal["accepts", "rejects", "not_expressible"] = "not_expressible"
    #: A V0 source for the reject case, when one can be written at all. Used to verify
    #: `v0_status` against the real compiler rather than asserting it in prose.
    v0_source: str = ""
    #: A V0 source for the accept case, where applicable.
    v0_accept_source: str = ""
    expected_code: str = ""
    notes: str = ""


ADVERSARIAL_PAIRS: tuple[AdversarialPair, ...] = (
    AdversarialPair(
        id="adv01_duplicate_concept_new_name",
        layer="concept_minting",
        reject_case=(
            "concept BoundedVariation2\n"
            "    parameter f : Function[Real -> Real]\n"
            "    invariant same_as_bounded_variation := true\n"
            "end"
        ),
        reject_reason=(
            "the formal definition is identical to an already-admitted concept, so this "
            "is the same concept under a new name. `spec/concept_registry.schema.json` "
            "gives it lifecycle `duplicate`, not `admitted`"
        ),
        accept_case=(
            "concept BoundedVariationOnAnInterval\n"
            "    parameter f : Function[Real -> Real]\n"
            "    parameter a : Real\n"
            "    invariant restricted_to_a_compact_interval := true\n"
            "end"
        ),
        accept_reason=(
            "a genuine specialisation: it adds an interval parameter, so it is not the "
            "same object under a new name and its admission_report records "
            "`specialisation_of`"
        ),
        required_interface="hamiltonian_lang.v1.minting:mint",
        v0_status="accepts",
        v0_source=(
            "module DuplicateConcept\n\n"
            "concept BoundedVariation2\n"
            "    parameter f : Function[Real -> Real]\n"
            "    invariant same_as_bounded_variation := 1 > 0\n"
            "end\n"
        ),
        v0_accept_source=(
            "module SpecialisedConcept\n\n"
            "concept BoundedVariationOnAnInterval\n"
            "    parameter f : Function[Real -> Real]\n"
            "    parameter a : Real\n"
            "    invariant restricted_to_a_compact_interval := a > 0\n"
            "end\n"
        ),
        expected_code="HML-V1-C001",
        notes="V0 has no registry, so it cannot see the duplication at all.",
    ),
    AdversarialPair(
        id="adv02_property_not_held",
        layer="concept_minting",
        reject_case=(
            "concept SymmetricKernel\n"
            "    parameter k : Function[Real -> Real]\n"
            "    property positive_definite := true\n"
            "    invariant symmetry := true\n"
            "end"
        ),
        reject_reason=(
            "`positive_definite` is asserted with no proof obligation and no witness. "
            "The registry schema requires every claim to carry a `claimStatus`; an "
            "unsupported claim may not be recorded as established"
        ),
        accept_case=(
            "concept SymmetricKernelConjecturedPD\n"
            "    parameter k : Function[Real -> Real]\n"
            "    property positive_definite := true\n"
            "    invariant symmetry := true\n"
            "    counterexample not_pd_without_symmetry := true\n"
            "end"
        ),
        accept_reason=(
            "the same property, but recorded as `conjectured` with a counterexample "
            "delimiting the boundary; the claim is present and its status is honest"
        ),
        required_interface="hamiltonian_lang.v1.minting:mint",
        v0_status="accepts",
        v0_source=(
            "module UnprovedProperty\n\n"
            "concept SymmetricKernel\n"
            "    parameter k : Function[Real -> Real]\n"
            "    property positive_definite := 1 > 0\n"
            "    invariant symmetry := 1 > 0\n"
            "end\n"
        ),
        expected_code="HML-V1-C002",
        notes="V0 checks that SOME invariant or example exists, never that a claim holds.",
    ),
    AdversarialPair(
        id="adv03_pure_synonym",
        layer="concept_minting",
        reject_case=(
            "concept AverageValue\n"
            "    parameter X : RandomVariable[Real]\n"
            "    invariant equals_the_expectation := true\n"
            "end"
        ),
        reject_reason=(
            "the concept abbreviates nothing: its `compresses` list is empty and its "
            "definition is a one-to-one renaming of an existing primitive. The registry "
            "schema states that a concept compressing nothing is a synonym and must be "
            "rejected as `duplicate`"
        ),
        accept_case=(
            "concept CenteredSecondMoment\n"
            "    parameter X : RandomVariable[Real]\n"
            "    invariant expands_to_a_recurring_two_term_expression := true\n"
            "end"
        ),
        accept_reason=(
            "it abbreviates a two-term expression that recurs across the corpus, so "
            "`compression_demonstrated` is true against at least one recorded occurrence"
        ),
        required_interface="hamiltonian_lang.v1.minting:mint",
        v0_status="accepts",
        v0_source=(
            "module PureSynonym\n\n"
            "concept AverageValue\n"
            "    parameter X : RandomVariable[Real]\n"
            "    invariant equals_the_expectation := 1 > 0\n"
            "end\n"
        ),
        expected_code="HML-V1-C003",
        notes="This is the case the minting protocol most needs to catch and the one "
              "most vulnerable to being gamed by a fabricated `compresses` entry — see "
              "audits/V1_RED_TEAM.md §3.",
    ),
    AdversarialPair(
        id="adv04_fabricated_member",
        layer="semantic_morphology",
        reject_case="ArbitraryConcept.density",
        reject_reason=(
            "`density` is a member of distribution-like concepts. `ArbitraryConcept` "
            "declares no such member, and there is no morphological rule that manufactures "
            "one. `docs/design/V1_KERNEL.md` §5: members are DECLARED, never GENERATED"
        ),
        accept_case="Normal.density",
        accept_reason=(
            "`Normal` declares `density` as a member, so the reference resolves against a "
            "declaration rather than against a suffix rule"
        ),
        required_interface="hamiltonian_lang.v1.morphology:Morphology.resolve",
        v0_status="not_expressible",
        notes="The matched pair is the whole point: a checker that rejects every dotted "
              "member reference passes the reject case and fails the accept case.",
    ),
    AdversarialPair(
        id="adv05_yields_used_as_implies",
        layer="L2_L3_boundary",
        reject_case="entails e3 from [e1, e2] via substitute",
        reject_reason=(
            "`substitute` is an L2 operation relating expressions; `entails` relates "
            "propositions via an inference rule. `Derivation` is not `Entailment` and "
            "there is no coercion between them (V1_KERNEL §2, §7 item 4)"
        ),
        accept_case="derive e3 from [e1, e2] via substitute",
        accept_reason="the same step, stated at the layer it belongs to",
        required_interface="hamiltonian_lang.v1.transformation:edge_kind_coercion_allowed",
        v0_status="not_expressible",
        notes="V0 has neither construct, so V0 cannot commit this error and equally "
              "cannot catch it. Recorded as not_expressible, not as a V0 success.",
    ),
    AdversarialPair(
        id="adv06_goal_discharged_by_evidence",
        layer="L5_discourse",
        reject_case="discharge g1 by consistent_with(P, data := D)",
        reject_reason=(
            "`discharge` requires a `Proof`. `consistent_with` returns `Evidence`, and "
            "`DISCHARGES_GOALS[Justification.EVIDENCE]` is False"
        ),
        accept_case="discharge g1 by proved(P, via := lemma_2)",
        accept_reason="a Proof discharges a goal, which is the only thing that does",
        required_interface="hamiltonian_lang.v1.epistemic_checks:EpistemicChecker",
        v0_status="not_expressible",
        expected_code="HML-V1-E004",
    ),
    AdversarialPair(
        id="adv07_prove_fail_to_reject",
        layer="L4_epistemic",
        reject_case="prove fail_to_reject(test := t1, p_value := 0.18)",
        reject_reason=(
            "`fail_to_reject` yields `Evidence`; `prove` demands `Proof`; the pair "
            "(Evidence, Proof) is in `PROHIBITED_COERCIONS`. This is the single error L4 "
            "exists to make unrepresentable"
        ),
        accept_case="assert insufficient_evidence_against(H0, under := t1)",
        accept_reason=(
            "the correct encoding of a non-rejection: it stays `Evidence` and claims "
            "nothing a non-rejection does not support"
        ),
        required_interface="hamiltonian_lang.v1.epistemic:coercion_allowed",
        v0_status="not_expressible",
        expected_code="HML-V1-E001",
    ),
    AdversarialPair(
        id="adv08_p_value_as_posterior",
        layer="L4_epistemic",
        reject_case="def posterior_h0 : Probability := p_value",
        reject_reason=(
            "`PValue` is a distinct refinement with no coercion to a posterior "
            "probability (spec/v1/semantic_objects.yaml, no_coercion_between)"
        ),
        accept_case="def tail_probability_under_h0 : PValue := p_value",
        accept_reason="the p-value used as what it is, with its own type preserved",
        required_interface="hamiltonian_lang.v1.types:PValue",
        v0_status="accepts",
        v0_source=(
            "module PValueAsPosterior\n\n"
            "const p_value : Probability = 0.03\n"
            "def posterior_h0 : Probability := p_value\n"
        ),
        expected_code="HML-V1-E002",
        notes="V0 types both as Probability, so the conflation type-checks today. This "
              "is a genuine V0 semantic hole and is verified live.",
    ),
    AdversarialPair(
        id="adv09_whp_without_regime",
        layer="L4_epistemic",
        reject_case="with_high_probability(P)",
        reject_reason=(
            "`REQUIRED_CONTEXT[WITH_HIGH_PROBABILITY]` demands a bound or regime; without "
            "one the phrase names no proposition"
        ),
        accept_case="with_high_probability(P, regime := n -> infinity)",
        accept_reason="the regime is supplied, so the claim has a referent",
        required_interface="hamiltonian_lang.v1.epistemic:EpistemicClaim",
        v0_status="not_expressible",
        expected_code="HML-V1-E003",
    ),
    AdversarialPair(
        id="adv10_estimate_is_unbiased",
        layer="concept_families",
        reject_case="require unbiased(estimate)",
        reject_reason=(
            "unbiasedness is a property of the estimator — a function — not of a "
            "realised value. `estimate : ParameterSpace` and `unbiased` requires "
            "`Function[Sample -> ParameterSpace]`"
        ),
        accept_case="require unbiased(estimator)",
        accept_reason="the property applied to the member that can carry it",
        required_interface="hamiltonian_lang.v1.morphology:attribute_property",
        v0_status="accepts",
        v0_source=(
            "module EstimateIsUnbiased\n\n"
            "param theta : Real\n"
            "const estimate : Real = 1.4\n"
            "def unbiased(z : Real) : Proposition := z = theta\n"
            "require unbiased(estimate)\n"
        ),
        expected_code="HML-V1-F001",
        notes="V0 has one flat namespace, so estimator and estimate are indistinguishable "
              "declarations and the confusion type-checks.",
    ),
    AdversarialPair(
        id="adv11_non_exhaustive_case_split",
        layer="L5_discourse",
        reject_case="case c1 := x > 0 ... case c2 := x < 0 ... end_case",
        reject_reason=(
            "the two branches do not cover x = 0 and no `otherwise` is present; "
            "exhaustiveness is a checked property of a case split"
        ),
        accept_case="case c1 := x > 0 ... otherwise ... end_case",
        accept_reason="`otherwise` is the complement branch, so the split is exhaustive "
                      "by construction",
        required_interface="hamiltonian_lang.v1.discourse:check_exhaustive",
        v0_status="not_expressible",
        expected_code="HML-V1-D001",
    ),
)


# ===========================================================================
# Arm rendering — five projections of one Canonical Semantic Object
# ===========================================================================
#
# `prose` and `question` are inserted verbatim and identically into every arm, and
# `verify_v1_shared_content_identical` asserts it. Everything that differs between arms
# is a METHOD block, and the differences are enumerated in V1_INFORMATION_ASYMMETRY.

_BASE_SYSTEM_V1 = (
    "You are solving a mathematics problem. Be precise. Do not restate the problem. "
    "Your reply must end with the final answer wrapped in "
    f"{ANSWER_OPEN} and {ANSWER_CLOSE} markers, and nothing after the closing marker."
)

V1_VOCAB_SPEC = """HAMILTONIAN V1 — ADDITIONAL VOCABULARY (layers above V0)

V0 above is unchanged. V1 adds four layers. They are separate: no construct of one layer
coerces to a construct of another.

L2 TRANSFORMATION — what rewrites to what, algebraically.
  step  <name> := <operation>(<role> := <expr>, ...)
  derive <result> from [<expr>, ...] via <step>
  Operations and the obligations they generate:
    substitute(source, into)      -- none
    divide(expr, by)              -- by != 0
    cancel(expr, factor)          -- factor != 0
    sqrt_both_sides(expr)         -- both sides >= 0; the sign branch is NOT unique
    square_both_sides(expr)       -- records a WEAKENING, not an equivalence
    differentiate(expr, wrt)      -- expr differentiable on its domain
    integrate(expr, wrt, over)    -- expr integrable over `over`
    limit(expr, variable, approaches) -- the limit exists
    apply(fn, to)                 -- `to` in domain(fn)
    rearrange(expr, for)          -- `for` is isolable in expr

L3 INFERENCE — what follows from what, logically.
  entails <q> from [<p>, ...] via <rule>
  equivalent(<p>, <q>)     counterexample_to(<p>, witness := <w>)
  rules: modus_ponens modus_tollens contraposition universal_instantiation
         existential_generalisation induction case_analysis contradiction
  A Derivation (L2) is NOT an Entailment (L3). Rewriting is not implying.

L4 EPISTEMIC STATUS — how strongly, and on what grounds.
  Justification is NOT a chain: Proof | Assumption | Evidence | Credence.
  Only a Proof discharges a goal. There is NO coercion Evidence -> Proof,
  Assumption -> Proof, or Credence -> Probability.
    proved(P, via := <proof>)          by_definition(P)        assumed(P)
    almost_sure(P)                     likely(P, probability := q)     possible(P)
    with_high_probability(P, regime := <regime>)   -- regime is MANDATORY
    consistent_with(P, data := D)      model_conditional(P, model := M)
    hypothesis_test(null, alternative, alpha)
    fail_to_reject(test, p_value)      -- returns Evidence
    insufficient_evidence_against(H, under := <test>)  -- the ONLY correct reading of a
                                                          non-rejection
  PValue is its own type. It does NOT coerce to a posterior probability.

L5 DISCOURSE STATE — what remains to be shown.
  goal <g> := <proposition>          opens an obligation
  discharge <g> by <Proof>           closes it; Evidence and Assumption are REJECTED
  case <c> := <condition> ... otherwise ... end_case    exhaustiveness is CHECKED"""

V1_MINTING_SPEC = """CONCEPT MINTING PROTOCOL

A concept survives because it has a formal identity with testable consequences, not
because it sounds plausible. Before minting, you must:

  1. search the registry below for an equality, equivalence or renaming match
  2. give a formal definition, a type signature, and typed parameters with ROLES
  3. state at least one invariant or example -- a concept with neither is REJECTED
  4. state what recurring structure it COMPRESSES

A concept that compresses nothing is a synonym and is rejected as a duplicate. A concept
whose definition matches an admitted one is rejected as a duplicate regardless of its
name. Members are DECLARED, never GENERATED: there is no suffix rule. `vary -> variance`
and `estimate -> estimator` are not rules, and applying them manufactures nonsense.

Surface form:
  concept <Name> [extends <Name>, ...]
      parameter <name> : <Type>
      transform <name>(<p> : <Type>) : <Type> := <expr>
      invariant <name> := <proposition>
      example   <name> := <proposition>
      counterexample <name> := <proposition>
  end

ADMITTED CONCEPTS -- these may be cited by name. The list is not exhaustive: a structure
may correspond to a concept that is not listed, and naming a listed concept that does not
apply exactly is an error.
"""

V1_FAMILY_SPEC = """DECLARED CONCEPT FAMILIES

A family is a declared set of independently typed members with explicit relations. There
is no derivation engine and no way to mint a member by pattern.

  family Estimation of theta : ParameterSpace
      member procedure      : EstimationProcedure
      member estimator      : Function[Sample -> ParameterSpace]
      member estimate       : ParameterSpace
      member sampling_law   : Distribution[ParameterSpace]
      member standard_error : PositiveReal
      relation estimate = apply(estimator, to := sample)
      relation sampling_law = law_of(estimator, under := sampling_model)
      invariant estimator_is_a_function_not_a_value
      invariant estimate_depends_on_sample
  end

"The estimate is unbiased" is therefore a TYPE ERROR: unbiasedness is a property of the
estimator, not of a number."""

_NOMINT_RULE = (
    "You may NOT introduce a new named concept. Every object must be written in the "
    "primitives above. If a structure recurs, write it out again."
)


def _registry_block() -> str:
    return "\n".join(c.render() for c in ADMITTED_CONCEPTS)


def _answer_block(cso: CanonicalSemanticObject) -> str:
    return (
        f"QUESTION\n{cso.question}\n\n"
        f"Give your final answer as {cso.answer.render_instruction()}\n"
        f"The answer must appear exactly once, wrapped in {ANSWER_OPEN} … {ANSWER_CLOSE}."
    )


def _demo_block(demos: list[tuple[str, str]]) -> str:
    if not demos:
        return ""
    out = ["WORKED EXAMPLES\n"]
    for i, (prose, solution) in enumerate(demos, 1):
        out.append(f"--- Example {i} ---\nProblem: {prose}\n\n{solution}\n")
    return "\n".join(out)


def render_v1_arm(
    arm: str,
    cso: CanonicalSemanticObject,
    demos: list[tuple[str, str]] | None = None,
) -> ArmPrompt:
    """Project one CSO into one arm. Returns the existing ``ArmPrompt`` so a harness
    written against the V0 apparatus can consume these without change."""
    if arm not in ARMS_V1:
        raise ValueError(f"unknown V1 arm {arm!r}")
    problem = f"PROBLEM\n{cso.prose}"
    answer = _answer_block(cso)
    demo = _demo_block(demos or [])

    if arm == "SE":
        parts = [demo, problem, "METHOD\n" + SCHEMA_A_PRIME, answer]
        return ArmPrompt("SE", cso.id, _BASE_SYSTEM_V1,
                         "\n\n".join(p for p in parts if p))

    if arm == "V0":
        method = (
            "METHOD\nEncode the problem in Hamiltonian Lang, using the reference above. "
            "Put the encoding in a fenced block marked ```hml. Then answer the question."
        )
        parts = [HML_SPEC, demo, problem, method, answer]
        return ArmPrompt("V0", cso.id, _BASE_SYSTEM_V1,
                         "\n\n".join(p for p in parts if p), formal_encoding=True)

    if arm == "V1_nomint":
        method = (
            "METHOD\nEncode the problem in Hamiltonian V1, using both references above. "
            f"{_NOMINT_RULE} Put the encoding in a fenced block marked ```hml. Then "
            "answer the question."
        )
        parts = [HML_SPEC, V1_VOCAB_SPEC, demo, problem, method, answer]
        return ArmPrompt("V1_nomint", cso.id, _BASE_SYSTEM_V1,
                         "\n\n".join(p for p in parts if p), formal_encoding=True)

    if arm == "V1_mint":
        method = (
            "METHOD\nEncode the problem in Hamiltonian V1, using the references above. "
            "You may cite an admitted concept by name, and you may mint a new concept if "
            "and only if it passes the minting protocol. Put the encoding in a fenced "
            "block marked ```hml. Then answer the question."
        )
        parts = [HML_SPEC, V1_VOCAB_SPEC, V1_MINTING_SPEC + _registry_block(),
                 V1_FAMILY_SPEC, demo, problem, method, answer]
        return ArmPrompt("V1_mint", cso.id, _BASE_SYSTEM_V1,
                         "\n\n".join(p for p in parts if p), formal_encoding=True)

    method = (
        "METHOD\nEncode the problem in Hamiltonian V1, using the references above. You "
        "may cite an admitted concept by name and mint a new one if it passes the "
        "minting protocol. Record every algebraic step as an L2 `step`/`derive` with its "
        "obligations, every logical move as an L3 `entails`, the epistemic status of "
        "every claim with an L4 constructor, and every open obligation as an L5 `goal`. "
        "Put the encoding in a fenced block marked ```hml. Then answer the question."
    )
    parts = [HML_SPEC, V1_VOCAB_SPEC, V1_MINTING_SPEC + _registry_block(),
             V1_FAMILY_SPEC, demo, problem, method, answer]
    return ArmPrompt("V1_full", cso.id, _BASE_SYSTEM_V1,
                     "\n\n".join(p for p in parts if p), formal_encoding=True)


def verify_v1_shared_content_identical(cso: CanonicalSemanticObject) -> None:
    """Assert every arm carries the problem statement and question verbatim.

    The same guard `evaluation/corpus/renderers.py` applies to the V0 arms, for the same
    reason: this is the only thing standing between the experiment and an
    information-asymmetry confound introduced by a typo.
    """
    for arm in ARMS_V1:
        p = render_v1_arm(arm, cso)
        if cso.prose not in p.user:
            raise AssertionError(f"arm {arm}: problem prose not carried verbatim")
        if cso.question not in p.user:
            raise AssertionError(f"arm {arm}: question not carried verbatim")


#: Differences between arms that cannot be removed by prompt construction. Each is
#: stated with the direction in which it biases the comparison.
V1_INFORMATION_ASYMMETRY = [
    "Prompt length rises monotonically along the ablation ladder: SE < V0 < V1_nomint < "
    "V1_mint = V1_full. Every added layer is more text about a language invented weeks "
    "ago. Direction: against the V1 arms, and it grows with the treatment, which is the "
    "worst possible confound structure. Prompt tokens are recorded per call so the "
    "difference is measured rather than assumed away.",
    "V1_mint and V1_full receive a list of 15 admitted concepts. Six corpus items have a "
    "correct answer that is deliberately NOT in that list, so the registry is not an "
    "answer key; but on the other six recognition items the registry does name the "
    "answer. Direction: in favour of the minting arms on non-transfer items. Transfer "
    "and non-transfer items are therefore scored separately and never pooled.",
    "The option list for every choice item is carried in the `question`, so it is "
    "identical in all five arms. No arm is told which options are plausible.",
    "V1_full is asked to record steps, entailments, statuses and goals. That is more "
    "output for the same answer, so V1_full is expected to be the slowest and most "
    "expensive arm before any accuracy is considered. Direction: raises V1_full cost; "
    "cost is reported, not netted off.",
    "Arms V0..V1_full carry a language specification; SE does not. This is the same "
    "out-of-distribution confound the V0 pilot recorded and prompt construction cannot "
    "remove it. Direction: against every Hamiltonian arm.",
    "The model under test decomposes internally in every arm, which compresses the "
    "SE-to-V0 contrast and therefore inflates any V0-to-V1 difference. Direction: in "
    "favour of the V1 arms.",
]
