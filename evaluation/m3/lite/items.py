"""The 40 M3-Lite items.

Every item is authored **once**, as a :class:`~evaluation.corpus.cso.CanonicalSemanticObject`
— the frozen contract — so that each arm is a projection of one structure rather than a
separately-written prose variant. Authoring per-arm prose by hand is how information
asymmetry enters without anyone deciding to introduce it.

What each item additionally carries, and why
--------------------------------------------
``error_category``   one of the eight balanced structural-error categories. Five items each.
``common_error``     the *named one-step mistake* that produces the recorded distractor. An
                     item with a distractor nobody would actually reach classifies nothing.
``negated_claim``    the gate-4 input: a statement whose truth would **refute** the recorded
                     ground truth. Where the answer is arithmetically recomputable this is a
                     SymPy relation comparing an independent recomputation against the
                     recorded literal, which is a real audit of the answer key — a mistyped
                     key is *proved wrong*. Where it is not recomputable the field holds the
                     natural-language negation and SymPy declines; that decline is recorded
                     per item, never silently treated as a pass.
``reasoning_steps``  distinct inferential steps in the reference derivation. Input to the
                     difficulty index in :mod:`.calibration`; ``1`` would be a ceiling item.
``h3_eligible``      whether the implemented verifier subset can express this item's
                     obligations at all. Calculus and linear algebra are ``False`` by
                     construction — see ``EXCLUDED_DOMAINS`` in
                     ``evaluation/m3/verification/task_subset.py``. Recording it per item is
                     what stops an H3 roster silently inheriting domains its verifier cannot
                     reach and reporting the result as a property of the language.

Contract with gate 2
--------------------
``semantics.entities`` lists **every** name the reference encoding declares or defines —
no more and no fewer. ``run_semantic_checks`` enforces both directions: an encoding missing
a named entity is incomplete, and an encoding with an extra one is a different model that
happens to contain the right one.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from evaluation.corpus.cso import AnswerSpec, CanonicalSemanticObject, SemanticFacts
from hamiltonian_lang.improvement.state import Hypothesis

from . import ERROR_CATEGORIES, M3_LITE_VERSION, SEED_NAMESPACE

__all__ = ["LiteItem", "build_items", "H3_INELIGIBLE_DOMAINS"]

#: Domains whose obligations the implemented verifier subset cannot state. Items in them are
#: valid H1/H2 material and are structurally unavailable to H3. Kept as data so the roster
#: can drop them mechanically and *report* the drop.
H3_INELIGIBLE_DOMAINS = frozenset({"linear_algebra", "calculus"})


@dataclass(frozen=True)
class LiteItem:
    """One benchmark item, carrying exactly one hypothesis identifier."""

    cso: CanonicalSemanticObject
    error_category: str
    common_error: str
    negated_claim: str
    reasoning_steps: int
    h3_eligible: bool
    #: Exactly one. ``ACQ0`` is a prerequisite and is never a value here; ``EXCLUDED`` is
    #: engineering work and is never a value here either. Enforced in ``__post_init__``.
    hypothesis: Hypothesis = Hypothesis.H2

    def __post_init__(self) -> None:
        if self.error_category not in ERROR_CATEGORIES:
            raise ValueError(f"{self.id}: unknown error category {self.error_category!r}")
        if self.hypothesis in {Hypothesis.ACQ0, Hypothesis.EXCLUDED}:
            raise ValueError(
                f"{self.id}: M3-Lite is a mathematical-reasoning corpus. ACQ0 is the "
                f"syntax-acquisition prerequisite and is not evidence for H1, H2 or H3; "
                f"EXCLUDED is engineering work and is never evidence at all"
            )
        if self.reasoning_steps < 2:
            raise ValueError(
                f"{self.id}: a one-step item is a ceiling item. HML-EVAL-001 saturated at "
                f"93.3% on exactly this kind of task and measured nothing"
            )
        if (self.domain in H3_INELIGIBLE_DOMAINS) and self.h3_eligible:
            raise ValueError(
                f"{self.id}: domain {self.domain} is outside the implemented verifier "
                f"subset, so it cannot be marked H3-eligible"
            )

    @property
    def id(self) -> str:
        return self.cso.id

    @property
    def domain(self) -> str:
        return self.cso.domain

    @property
    def difficulty(self) -> str:
        return self.cso.difficulty

    def for_hypothesis(self, hypothesis: Hypothesis) -> LiteItem:
        return replace(self, hypothesis=hypothesis)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain,
            "difficulty": self.difficulty,
            "error_category": self.error_category,
            "hypothesis": str(self.hypothesis),
            "reasoning_steps": self.reasoning_steps,
            "h3_eligible": self.h3_eligible,
            "common_error": self.common_error,
        }


def _item(
    number: int,
    slug: str,
    domain: str,
    difficulty: str,
    prose: str,
    question: str,
    answer: AnswerSpec,
    semantics: SemanticFacts,
    reference: str,
    distractor: str,
    error_category: str,
    common_error: str,
    negated_claim: str,
    reasoning_steps: int,
) -> LiteItem:
    pid = f"m3l_{number:02d}_{slug}"
    cso = CanonicalSemanticObject(
        id=pid,
        domain=domain,
        difficulty=difficulty,  # type: ignore[arg-type]
        prose=prose.strip(),
        question=question.strip(),
        answer=answer,
        semantics=semantics,
        distractors=[distractor],
        reference_hml=reference.strip() + "\n",
        generator=f"{SEED_NAMESPACE}{slug}",
        corpus_version=M3_LITE_VERSION,
    )
    return LiteItem(
        cso=cso,
        error_category=error_category,
        common_error=common_error,
        negated_claim=negated_claim,
        reasoning_steps=reasoning_steps,
        h3_eligible=domain not in H3_INELIGIBLE_DOMAINS,
    )


def _facts(
    entities: dict[str, str],
    kinds: dict[str, str],
    **rest: Any,
) -> SemanticFacts:
    return SemanticFacts(entities=entities, declaration_kinds=kinds, **rest)


_BOOL = ["TRUE", "FALSE"]


# ===========================================================================
# algebra -- 6
# ===========================================================================


def _algebra() -> list[LiteItem]:
    return [
        _item(
            1, "implication_converse", "algebra", "medium",
            prose=(
                "Two real quantities a and b are related by a single stated rule: whenever a "
                "is strictly greater than zero, b is strictly greater than zero as well. "
                "Nothing at all is stated about what holds when b is strictly greater than "
                "zero, and no further relation between the two is given."
            ),
            question=(
                "Does the stated rule entail that whenever b is strictly greater than zero, "
                "a is strictly greater than zero?"
            ),
            answer=AnswerSpec(
                kind="boolean", value=False, options=_BOOL,
                justification=(
                    "the converse of an implication is not entailed by it; a = -1, b = 1 "
                    "satisfies the stated rule vacuously and violates the converse"
                ),
            ),
            semantics=_facts({"a": "Real", "b": "Real"}, {"a": "var", "b": "var"}),
            reference="""
module AlgImplicationConverse
var a : Real
var b : Real
require a > 0.0 implies b > 0.0
prove not (b > 0.0 implies a > 0.0)
""",
            distractor="TRUE",
            error_category="equality_vs_implication",
            common_error="reading the stated implication as a biconditional",
            negated_claim="Eq(And(1 > 0, -1 > 0), True)",
            reasoning_steps=3,
        ),
        _item(
            2, "unstated_sign", "algebra", "medium",
            prose=(
                "A real quantity x satisfies x squared equals nine. The problem statement "
                "records no constraint on the sign of x and no other constraint of any kind."
            ),
            question="Is it consistent with everything stated that x is negative?",
            answer=AnswerSpec(
                kind="boolean", value=True, options=_BOOL,
                justification="negative three satisfies the only stated constraint, and no stated constraint excludes it",
            ),
            semantics=_facts({"x": "Real"}, {"x": "var"}),
            reference="""
module AlgUnstatedSign
var x : Real
require x^2 = 9.0
solve x
""",
            distractor="FALSE",
            error_category="assumption_boundary",
            common_error="importing an unstated positivity assumption from the square root",
            negated_claim="Or(Ne((-3)**2, 9), Eq(-3, 3))",
            reasoning_steps=3,
        ),
        _item(
            3, "shadowed_scale", "algebra", "hard",
            prose=(
                "A model declares a scale factor named s at module level and fixes it to four. "
                "A separate definition introduces its own local argument, also written s, and "
                "returns twice that argument. The definition is then applied to the value seven."
            ),
            question=(
                "What number does applying the definition to seven produce? Give a single number."
            ),
            answer=AnswerSpec(
                kind="numeric", value=14.0,
                justification="the local argument shadows the module-level s, so 2 * 7 = 14",
            ),
            semantics=_facts(
                {"s": "Real", "scaled": "Function"},
                {"s": "const"},
            ),
            reference="""
module AlgShadowedScale
const s : Real = 4.0
def scaled(local_s : Real) := 2.0 * local_s
require scaled(7.0) = 14.0
""",
            distractor="28",
            error_category="binding_scope",
            common_error=(
                "resolving the definition's parameter to the module-level constant, giving "
                "4 * 7"
            ),
            negated_claim="Ne(2*7, 14)",
            reasoning_steps=3,
        ),
        _item(
            4, "rounded_intermediate", "algebra", "medium",
            prose=(
                "A quantity r is defined as one third, and a quantity t is defined as r "
                "multiplied by six. A working note replaces r with the two-decimal decimal "
                "approximation zero point three three before computing t."
            ),
            question=(
                "Is the value of t obtained after that replacement equal to the exact value "
                "of t?"
            ),
            answer=AnswerSpec(
                kind="boolean", value=False, options=_BOOL,
                justification="1/3 * 6 = 2 exactly, whereas 0.33 * 6 = 1.98",
            ),
            semantics=_facts(
                {"r": "Rational", "t": "Real"},
                {"r": "const"},
            ),
            reference="""
module AlgRoundedIntermediate
const r : Rational
def t := r * 6.0
require r = 1.0 / 3.0
prove t = 2.0
""",
            distractor="TRUE",
            error_category="approximation_vs_equality",
            common_error="treating a rounded intermediate as an exact substitution",
            negated_claim="Eq(Rational(33,100)*6, Rational(1,3)*6)",
            reasoning_steps=3,
        ),
        _item(
            5, "bound_order", "algebra", "hard",
            prose=(
                "Consider real numbers. Statement one says: for every real u there exists a "
                "real w with w strictly greater than u. Statement two says: there exists a "
                "real w such that for every real u, w is strictly greater than u."
            ),
            question="Do statement one and statement two differ in truth value over the reals?",
            answer=AnswerSpec(
                kind="boolean", value=True, options=_BOOL,
                justification=(
                    "statement one is true over an unbounded order; statement two asserts a "
                    "greatest real, which does not exist"
                ),
            ),
            semantics=SemanticFacts(
                entities={},
                declaration_kinds={},
                quantifier_order=["forall u", "exists w", "exists w", "forall u"],
            ),
            reference="""
module AlgBoundOrder
require forall u : Real . exists w : Real . w > u
prove exists w : Real . forall u : Real . w > u
""",
            distractor="FALSE",
            error_category="quantifier_order",
            common_error="treating the quantifier prefix as commutative",
            negated_claim=(
                "statement one and statement two denote the same proposition over the reals"
            ),
            reasoning_steps=4,
        ),
        _item(
            6, "ratio_roles", "algebra", "medium",
            prose=(
                "A conversion is specified by a numerator factor named top, fixed to nine, and "
                "a denominator factor named bottom, fixed to three. The conversion of an input "
                "is the input multiplied by top and divided by bottom."
            ),
            question="What is the conversion of the input two? Give a single number.",
            answer=AnswerSpec(
                kind="numeric", value=6.0,
                justification="2 * 9 / 3 = 6",
            ),
            semantics=_facts(
                {"top": "Real", "bottom": "Real", "convert": "Function"},
                {"top": "const", "bottom": "const"},
            ),
            reference="""
module AlgRatioRoles
const top : Real = 9.0
const bottom : Real = 3.0
def convert(u : Real) := u * top / bottom
require convert(2.0) = 6.0
""",
            distractor="0.667",
            error_category="role_assignment",
            common_error="exchanging the numerator and denominator factors",
            negated_claim="Ne(2*9/3, 6)",
            reasoning_steps=3,
        ),
    ]


# ===========================================================================
# probability and statistics -- 6
# ===========================================================================


def _probability() -> list[LiteItem]:
    return [
        _item(
            7, "prior_is_not_value", "probability_statistics", "medium",
            prose=(
                "A success probability named theta is given a Beta prior whose two shape "
                "parameters are fixed. A colleague states that assigning this prior changes "
                "theta from a number in the unit interval into a probability distribution."
            ),
            question="Does assigning a prior change the type of theta from a value to a distribution?",
            answer=AnswerSpec(
                kind="boolean", value=False, options=_BOOL,
                justification=(
                    "the prior statement relates a symbol to a law; neither becomes the other, "
                    "and theta remains a Probability"
                ),
            ),
            semantics=_facts(
                {"theta": "Probability", "a0": "PositiveReal", "b0": "PositiveReal"},
                {"theta": "param", "a0": "const", "b0": "const"},
                law_families={"theta": "Beta"},
                laws={"theta": {"alpha": "a0", "beta": "b0"}},
            ),
            reference="""
module ProbPriorIsNotValue
const a0 : PositiveReal
const b0 : PositiveReal
param theta : Probability
prior theta ~ Beta(alpha := a0, beta := b0)
infer posterior theta
""",
            distractor="TRUE",
            error_category="distribution_vs_value",
            common_error="promoting the parameter to its own prior law",
            negated_claim=(
                "assigning a prior to theta replaces its type with Distribution[Probability]"
            ),
            reasoning_steps=3,
        ),
        _item(
            8, "location_scale_roles", "probability_statistics", "medium",
            prose=(
                "An observation y follows a normal law. The centre of the law is a parameter "
                "named centre and its spread is a parameter named spread. A summary reports "
                "the pair of role fillers for that law."
            ),
            question=(
                "Give the role map for the normal law of y, as a JSON object from role to symbol."
            ),
            answer=AnswerSpec(
                kind="role_map",
                value={"location": "centre", "scale": "spread"},
                justification="the centre fills location and the spread fills scale",
            ),
            semantics=_facts(
                {"centre": "Real", "spread": "PositiveReal", "y": "Real"},
                {"centre": "param", "spread": "param", "y": "obs"},
                law_families={"y": "Normal"},
                laws={"y": {"location": "centre", "scale": "spread"}},
                conditioning={"y": ["centre", "spread"]},
            ),
            reference="""
module ProbLocationScaleRoles
param centre : Real
param spread : PositiveReal
obs y : Real
law y | centre spread ~ Normal(location := centre, scale := spread)
""",
            distractor='{"location": "spread", "scale": "centre"}',
            error_category="role_assignment",
            common_error="filling the roles in declaration order rather than by name",
            negated_claim="the normal law of y is filled location := spread, scale := centre",
            reasoning_steps=2,
        ),
        _item(
            9, "expectation_is_not_variable", "probability_statistics", "hard",
            prose=(
                "A random variable z follows a normal law centred at zero with a fixed positive "
                "spread named sd. A note asserts that because the law is centred at zero, the "
                "random variable z is itself equal to zero."
            ),
            question="Can the random variable z take a value other than the centre of its law?",
            answer=AnswerSpec(
                kind="boolean", value=True, options=_BOOL,
                justification=(
                    "a random variable is not the mean of its law; only the expectation is zero"
                ),
            ),
            semantics=_facts(
                {"sd": "PositiveReal", "zero": "Real", "z": "RandomVariable[Real]"},
                {"sd": "const", "zero": "const", "z": "rv"},
                law_families={"z": "Normal"},
                laws={"z": {"location": "zero", "scale": "sd"}},
            ),
            reference="""
module ProbExpectationIsNotVariable
const sd : PositiveReal
const zero : Real = 0.0
rv z : RandomVariable[Real]
law z ~ Normal(location := zero, scale := sd)
infer expectation z
""",
            distractor="FALSE",
            error_category="distribution_vs_value",
            common_error="identifying a random variable with the mean of its law",
            negated_claim="the random variable z is equal to the location of its law",
            reasoning_steps=3,
        ),
        _item(
            10, "correlation_not_conditioning", "probability_statistics", "hard",
            prose=(
                "Two observations u and w are each given a normal law conditioned on a shared "
                "parameter named common. No law relates u to w directly. A note concludes that "
                "u therefore determines w."
            ),
            question="Does the stated model entail that u determines w?",
            answer=AnswerSpec(
                kind="boolean", value=False, options=_BOOL,
                justification=(
                    "sharing a conditioning parameter induces dependence, not determination; "
                    "no law from u to w is stated"
                ),
            ),
            semantics=_facts(
                {"centre0": "Real", "common": "Real", "sd": "PositiveReal", "u": "Real",
                 "w": "Real"},
                {"centre0": "const", "common": "param", "sd": "const", "u": "obs",
                 "w": "obs"},
                law_families={"common": "Normal", "u": "Normal", "w": "Normal"},
                conditioning={"u": ["common"], "w": ["common"]},
            ),
            reference="""
module ProbCorrelationNotConditioning
const sd : PositiveReal
const centre0 : Real
param common : Real
obs u : Real
obs w : Real
prior common ~ Normal(location := centre0, scale := sd)
law u | common ~ Normal(location := common, scale := sd)
law w | common ~ Normal(location := common, scale := sd)
infer posterior common
""",
            distractor="TRUE",
            error_category="equality_vs_implication",
            common_error="reading shared conditioning as a functional dependence",
            negated_claim="the stated model contains a law whose target is w and whose given set contains u",
            reasoning_steps=4,
        ),
        _item(
            11, "hyperparameter_shadow", "probability_statistics", "hard",
            prose=(
                "A hierarchical model declares a top-level spread named spread, fixed to two. "
                "A helper definition takes its own argument, also written spread, and returns "
                "three times that argument. The helper is applied to the value five."
            ),
            question="What number does the helper return for the input five? Give a single number.",
            answer=AnswerSpec(
                kind="numeric", value=15.0,
                justification="the helper's argument shadows the module-level spread, so 3 * 5 = 15",
            ),
            semantics=_facts(
                {"spread": "PositiveReal", "widen": "Function"},
                {"spread": "const"},
            ),
            reference="""
module ProbHyperparameterShadow
const spread : PositiveReal = 2.0
def widen(local_spread : Real) := 3.0 * local_spread
require widen(5.0) = 15.0
""",
            distractor="6",
            error_category="binding_scope",
            common_error="resolving the helper's argument to the module-level spread",
            negated_claim="Ne(3*5, 15)",
            reasoning_steps=3,
        ),
        _item(
            12, "interval_endpoint", "probability_statistics", "medium",
            prose=(
                "An interval estimate is reported as the centre estimate plus or minus two "
                "spread units. The centre estimate is eight and one spread unit is one half. "
                "A summary rounds the half-width to the nearest whole number before reporting "
                "the lower endpoint."
            ),
            question="Give the exact lower endpoint of the interval, as a single number.",
            answer=AnswerSpec(
                kind="numeric", value=7.0,
                justification="8 - 2 * 0.5 = 7 exactly; the rounded half-width would give 7 too "
                "only if the rounding were to one, which it is not",
            ),
            semantics=_facts(
                {"centre": "Real", "unit": "PositiveReal", "lower": "Real"},
                {"centre": "const", "unit": "const"},
            ),
            reference="""
module ProbIntervalEndpoint
const centre : Real = 8.0
const unit : PositiveReal
def lower := centre - 2.0 * unit
require unit = 0.5
prove lower = 7.0
""",
            distractor="6",
            error_category="approximation_vs_equality",
            common_error="rounding the spread unit up to one before multiplying",
            negated_claim="Ne(8 - 2*Rational(1,2), 7)",
            reasoning_steps=3,
        ),
    ]


# ===========================================================================
# logic and scope -- 6
# ===========================================================================


def _logic() -> list[LiteItem]:
    return [
        _item(
            13, "prefix_swap_naturals", "logic_and_scope", "hard",
            prose=(
                "Over the natural numbers, statement P says that for every n there exists an m "
                "strictly greater than n. Statement Q says that there exists an m such that for "
                "every n, m is strictly greater than n."
            ),
            question="Is statement Q strictly stronger than statement P over the naturals?",
            answer=AnswerSpec(
                kind="boolean", value=True, options=_BOOL,
                justification="P holds over an unbounded order; Q asserts a greatest natural",
            ),
            semantics=SemanticFacts(
                entities={},
                declaration_kinds={},
                quantifier_order=["forall n", "exists m", "exists m", "forall n"],
            ),
            reference="""
module LogicPrefixSwapNaturals
require forall n : Natural . exists m : Natural . m > n
prove exists m : Natural . forall n : Natural . m > n
""",
            distractor="FALSE",
            error_category="quantifier_order",
            common_error="treating the two prefixes as notational variants",
            negated_claim="statement P entails statement Q over the naturals",
            reasoning_steps=4,
        ),
        _item(
            14, "negation_crosses_prefix", "logic_and_scope", "hard",
            prose=(
                "A claim states that for every real v, some real z satisfies a stated relation "
                "with v. A rewriting moves a negation across the whole claim without changing "
                "either quantifier."
            ),
            question=(
                "Which quantifier prefix does the correct negation of the claim carry? Answer "
                "with one of the given options."
            ),
            answer=AnswerSpec(
                kind="choice", value="exists_forall",
                options=["forall_exists", "exists_forall", "forall_forall", "exists_exists"],
                justification="negating a forall-exists prefix yields exists-forall",
            ),
            semantics=SemanticFacts(
                entities={},
                declaration_kinds={},
                quantifier_order=["forall v", "exists z", "exists v", "forall z"],
            ),
            reference="""
module LogicNegationCrossesPrefix
require forall v : Real . exists z : Real . z > v
prove exists v : Real . forall z : Real . not (z > v)
""",
            distractor="forall_exists",
            error_category="quantifier_order",
            common_error="pushing the negation inward without dualising the quantifiers",
            negated_claim="the negation of a forall-exists claim carries a forall-exists prefix",
            reasoning_steps=3,
        ),
        _item(
            15, "reused_bound_name", "logic_and_scope", "hard",
            prose=(
                "A specification binds a variable named k inside one quantified claim and, "
                "separately, declares a module-level constant also named k and fixes it to ten. "
                "A definition multiplies its own argument, again written k, by four; the "
                "definition is applied to the value three."
            ),
            question="What number does the definition produce for the input three? Give a single number.",
            answer=AnswerSpec(
                kind="numeric", value=12.0,
                justification="the definition's argument shadows the constant, so 4 * 3 = 12",
            ),
            semantics=_facts(
                {"k": "Natural", "quadruple": "Function"},
                {"k": "const"},
            ),
            reference="""
module LogicReusedBoundName
const k : Natural = 10
def quadruple(local_k : Real) := 4.0 * local_k
require quadruple(3.0) = 12.0
""",
            distractor="40",
            error_category="binding_scope",
            common_error="resolving the definition's argument to the module-level constant",
            negated_claim="Ne(4*3, 12)",
            reasoning_steps=3,
        ),
        _item(
            16, "biconditional_claimed", "logic_and_scope", "medium",
            prose=(
                "A specification states a single directed rule: proposition p entails "
                "proposition q. A reader records the rule as an equivalence between p and q."
            ),
            question="Is recording the rule as an equivalence a faithful reading of the specification?",
            answer=AnswerSpec(
                kind="boolean", value=False, options=_BOOL,
                justification="an entailment constrains one direction; an equivalence constrains two",
            ),
            semantics=_facts(
                {"p": "Proposition", "q": "Proposition"},
                {"p": "const", "q": "const"},
            ),
            reference="""
module LogicBiconditionalClaimed
const p : Proposition
const q : Proposition
require p implies q
prove not (p iff q)
""",
            distractor="TRUE",
            error_category="equality_vs_implication",
            common_error="strengthening an entailment into a biconditional",
            negated_claim="p implies q and q implies p follow from p implies q alone",
            reasoning_steps=3,
        ),
        _item(
            17, "totality_not_stated", "logic_and_scope", "medium",
            prose=(
                "A relation is stated to hold for every element of a declared subset of the "
                "reals. The subset is not stated to be the whole of the reals, and no further "
                "statement about its extent is made."
            ),
            question="Could the relation fail at some real number outside the declared subset?",
            answer=AnswerSpec(
                kind="boolean", value=True, options=_BOOL,
                justification="the quantifier is restricted to a subset whose extent is unstated",
            ),
            semantics=_facts(
                {"domain_set": "Set[Real]", "holds": "Proposition"},
                {"domain_set": "const", "holds": "const"},
            ),
            reference="""
module LogicTotalityNotStated
const domain_set : Set[Real]
const holds : Proposition
assume holds
prove not (forall t : Real . holds)
""",
            distractor="FALSE",
            error_category="assumption_boundary",
            common_error="widening a restricted quantifier to the ambient type",
            negated_claim="a claim restricted to a subset entails the same claim over the ambient type",
            reasoning_steps=3,
        ),
        _item(
            18, "uniqueness_versus_existence", "logic_and_scope", "medium",
            prose=(
                "A specification asserts that some real solves a stated linear equation. A "
                "second specification asserts that exactly one real solves the same equation."
            ),
            question="Does the first specification entail the second?",
            answer=AnswerSpec(
                kind="boolean", value=False, options=_BOOL,
                justification="existence does not carry uniqueness; the stronger claim adds content",
            ),
            semantics=SemanticFacts(
                entities={},
                declaration_kinds={},
                quantifier_order=["exists c", "exists_unique c"],
            ),
            reference="""
module LogicUniquenessVersusExistence
require exists c : Real . c + 1.0 = 2.0
prove exists unique c : Real . c + 1.0 = 2.0
""",
            distractor="TRUE",
            error_category="quantifier_order",
            common_error="reading a bare existential as a unique existential",
            negated_claim="a bare existential claim entails the corresponding unique-existence claim",
            reasoning_steps=3,
        ),
    ]


# ===========================================================================
# dimensions and physics -- 6
# ===========================================================================


def _dimensions() -> list[LiteItem]:
    return [
        _item(
            19, "momentum_flux", "dimensions_physics", "medium",
            prose=(
                "A density has dimension mass per length cubed and a speed has dimension length "
                "per time. A flux quantity is formed as the density multiplied by the speed "
                "squared."
            ),
            question="What is the physical dimension of that flux quantity?",
            answer=AnswerSpec(
                kind="dimension", value="Mass / Length / Time^2",
                justification="(M L^-3)(L T^-1)^2 = M L^-1 T^-2",
            ),
            semantics=_facts(
                {"density": "Quantity[Mass / Length^3]", "speed": "Quantity[Length / Time]",
                 "flux": "Quantity"},
                {"density": "param", "speed": "param"},
                dimensions={"density": "Quantity[Mass / Length^3]",
                            "speed": "Quantity[Length / Time]"},
            ),
            reference="""
module DimMomentumFlux
param density : Quantity[Mass / Length^3]
param speed : Quantity[Length / Time]
def flux := density * speed^2
check dimension flux = Mass / Length / Time^2
""",
            distractor="Mass / Length^2 / Time^2",
            error_category="dimensional_consistency",
            common_error="squaring only the length part of the speed",
            negated_claim="Ne(-3 + 2, -1)",
            reasoning_steps=3,
        ),
        _item(
            20, "pendulum_half_power", "dimensions_physics", "hard",
            prose=(
                "A length quantity and an acceleration quantity, the latter with dimension "
                "length per time squared, are combined by taking the square root of the length "
                "divided by the acceleration."
            ),
            question="What is the physical dimension of the resulting quantity?",
            answer=AnswerSpec(
                kind="dimension", value="Time",
                justification="(L / (L T^-2))^(1/2) = (T^2)^(1/2) = T",
            ),
            semantics=_facts(
                {"span": "Quantity[Length]", "accel": "Quantity[Length / Time^2]",
                 "interval": "Quantity"},
                {"span": "param", "accel": "param"},
                dimensions={"span": "Quantity[Length]",
                            "accel": "Quantity[Length / Time^2]"},
            ),
            reference="""
module DimPendulumHalfPower
param span : Quantity[Length]
param accel : Quantity[Length / Time^2]
def interval := (span / accel)^0.5
check dimension interval = Time
""",
            distractor="Time^2",
            error_category="dimensional_consistency",
            common_error="omitting the one-half exponent after forming the ratio",
            negated_claim="Ne(2*Rational(1,2), 1)",
            reasoning_steps=3,
        ),
        _item(
            21, "additive_mismatch", "dimensions_physics", "medium",
            prose=(
                "An energy quantity has dimension mass times length squared per time squared. "
                "A second quantity has dimension mass times length per time squared. A working "
                "note adds the two together."
            ),
            question="Do the two quantities carry different base-dimension exponent vectors?",
            answer=AnswerSpec(
                kind="boolean", value=True, options=_BOOL,
                justification="addition requires identical dimension vectors; the length exponents differ",
            ),
            semantics=_facts(
                {"energy": "Quantity[Mass * Length^2 / Time^2]",
                 "force": "Quantity[Mass * Length / Time^2]"},
                {"energy": "param", "force": "param"},
                dimensions={"energy": "Quantity[Mass * Length^2 / Time^2]",
                            "force": "Quantity[Mass * Length / Time^2]"},
            ),
            reference="""
module DimAdditiveMismatch
param energy : Quantity[Mass * Length^2 / Time^2]
param force : Quantity[Mass * Length / Time^2]
check dimension energy = Mass * Length^2 / Time^2
check dimension force = Mass * Length / Time^2
""",
            distractor="FALSE",
            error_category="dimensional_consistency",
            common_error="adding quantities that share every base dimension but not every exponent",
            negated_claim="Eq(2, 1)",
            reasoning_steps=3,
        ),
        _item(
            22, "small_angle_substitution", "dimensions_physics", "hard",
            prose=(
                "A derivation replaces a dimensionless angle by its small-angle approximation "
                "and then reports the resulting relation with an equals sign. The replacement "
                "is exact only in the limit of vanishing angle."
            ),
            question="Is the reported relation an exact equality?",
            answer=AnswerSpec(
                kind="boolean", value=False, options=_BOOL,
                justification="a limiting substitution yields an approximation, not an identity",
            ),
            semantics=_facts(
                {"angle": "Dimensionless", "approx_form": "Dimensionless"},
                {"angle": "param", "approx_form": "param"},
            ),
            reference="""
module DimSmallAngleSubstitution
param angle : Dimensionless
param approx_form : Dimensionless
assume angle > 0.0
prove not (angle = approx_form)
""",
            distractor="TRUE",
            error_category="approximation_vs_equality",
            common_error="recording a limiting approximation with an equality sign",
            negated_claim="a small-angle substitution yields an exact identity for every angle",
            reasoning_steps=3,
        ),
        _item(
            23, "unstated_constant_dimension", "dimensions_physics", "hard",
            prose=(
                "A proportionality is stated between a mass quantity and a length quantity via "
                "an unnamed constant. The dimension of the constant is not stated anywhere in "
                "the problem."
            ),
            question="Can the dimension of the proportionality constant be determined from the statement alone?",
            answer=AnswerSpec(
                kind="boolean", value=True, options=_BOOL,
                justification=(
                    "a stated equality between the two sides forces the constant to carry "
                    "mass per length; the dimension is determined even though it is unstated"
                ),
            ),
            semantics=_facts(
                {"body_mass": "Quantity[Mass]", "body_span": "Quantity[Length]",
                 "coefficient": "Quantity[Mass / Length]", "predicted": "Quantity"},
                {"body_mass": "param", "body_span": "param", "coefficient": "param"},
                dimensions={"body_mass": "Quantity[Mass]",
                            "body_span": "Quantity[Length]",
                            "coefficient": "Quantity[Mass / Length]"},
            ),
            reference="""
module DimUnstatedConstant
param body_mass : Quantity[Mass]
param body_span : Quantity[Length]
param coefficient : Quantity[Mass / Length]
def predicted := coefficient * body_span
check dimension predicted = Mass
""",
            distractor="FALSE",
            error_category="assumption_boundary",
            common_error="treating an unstated dimension as an undeterminable one",
            negated_claim="the proportionality constant's dimension is not fixed by the stated equality",
            reasoning_steps=3,
        ),
        _item(
            24, "pressure_roles", "dimensions_physics", "medium",
            prose=(
                "A pressure is formed from a force quantity, of dimension mass times length per "
                "time squared, and an area quantity, of dimension length squared. The force is "
                "the numerator and the area is the denominator."
            ),
            question="What is the physical dimension of the pressure?",
            answer=AnswerSpec(
                kind="dimension", value="Mass / Length / Time^2",
                justification="(M L T^-2) / L^2 = M L^-1 T^-2",
            ),
            semantics=_facts(
                {"push": "Quantity[Mass * Length / Time^2]", "face": "Quantity[Length^2]",
                 "pressure": "Quantity"},
                {"push": "param", "face": "param"},
                dimensions={"push": "Quantity[Mass * Length / Time^2]",
                            "face": "Quantity[Length^2]"},
            ),
            reference="""
module DimPressureRoles
param push : Quantity[Mass * Length / Time^2]
param face : Quantity[Length^2]
def pressure := push / face
check dimension pressure = Mass / Length / Time^2
""",
            distractor="Mass * Length^3 / Time^2",
            error_category="role_assignment",
            common_error="exchanging numerator and denominator when forming the ratio",
            negated_claim="Ne(1 - 2, -1)",
            reasoning_steps=3,
        ),
    ]


# ===========================================================================
# linear algebra -- 6   (H3-ineligible: the verifier subset cannot index terms)
# ===========================================================================


def _linear_algebra() -> list[LiteItem]:
    return [
        _item(
            25, "product_shape", "linear_algebra", "medium",
            prose=(
                "A matrix has row count N and column count P. A second matrix has row count P "
                "and column count N. Their product is formed in that order, first times second."
            ),
            question="What is the column count of the product? Answer with one of the given options.",
            answer=AnswerSpec(
                kind="choice", value="N",
                options=["N", "P", "N_times_P", "undefined"],
                justification="an N-by-P times a P-by-N product is N-by-N",
            ),
            semantics=_facts(
                {"N": "Natural", "P": "Natural", "Left": "Matrix[Real, N, P]",
                 "Right": "Matrix[Real, P, N]", "Product": "Matrix[Real, N, N]"},
                {"N": "index", "P": "index", "Left": "obs", "Right": "obs"},
            ),
            reference="""
module LinProductShape
index N : Natural
index P : Natural
obs Left : Matrix[Real, N, P]
obs Right : Matrix[Real, P, N]
def Product : Matrix[Real, N, N] := Left @ Right
""",
            distractor="P",
            error_category="dimensional_consistency",
            common_error="taking the inner dimension of the product as its column count",
            negated_claim="the product of an N-by-P and a P-by-N matrix has P columns",
            reasoning_steps=3,
        ),
        _item(
            26, "index_shadow", "linear_algebra", "hard",
            prose=(
                "A module declares an index named P and a definition that takes its own "
                "argument, also written P, returning that argument plus six. The definition is "
                "applied to the value five."
            ),
            question="What number does the definition produce for the input five? Give a single number.",
            answer=AnswerSpec(
                kind="numeric", value=11.0,
                justification="the argument shadows the index, so 5 + 6 = 11",
            ),
            semantics=_facts(
                {"P": "Natural", "grow": "Function"},
                {"P": "index"},
            ),
            reference="""
module LinIndexShadow
index P : Natural
def grow(local_p : Real) := local_p + 6.0
require grow(5.0) = 11.0
""",
            distractor="6",
            error_category="binding_scope",
            common_error="resolving the definition's argument to the module-level index",
            negated_claim="Ne(5 + 6, 11)",
            reasoning_steps=3,
        ),
        _item(
            27, "operand_order", "linear_algebra", "medium",
            prose=(
                "A design matrix has row count N and column count P. A coefficient vector has "
                "length P. The prediction is formed by applying the design matrix to the "
                "coefficient vector, in that order."
            ),
            question="What is the length of the prediction vector? Answer with one of the given options.",
            answer=AnswerSpec(
                kind="choice", value="N",
                options=["N", "P", "N_times_P", "undefined"],
                justification="an N-by-P matrix applied to a length-P vector yields a length-N vector",
            ),
            semantics=_facts(
                {"N": "Natural", "P": "Natural", "Design": "Matrix[Real, N, P]",
                 "coeff": "Vector[Real, P]", "prediction": "Vector[Real, N]"},
                {"N": "index", "P": "index", "Design": "obs", "coeff": "param"},
            ),
            reference="""
module LinOperandOrder
index N : Natural
index P : Natural
obs Design : Matrix[Real, N, P]
param coeff : Vector[Real, P]
def prediction : Vector[Real, N] := Design @ coeff
""",
            distractor="P",
            error_category="role_assignment",
            common_error="exchanging the operand roles and reporting the coefficient length",
            negated_claim="applying an N-by-P matrix to a length-P vector yields a length-P vector",
            reasoning_steps=3,
        ),
        _item(
            28, "invertibility_direction", "linear_algebra", "hard",
            prose=(
                "A square matrix is stated to be invertible. A note concludes from this that "
                "every square matrix of the same size is invertible."
            ),
            question="Does the stated fact entail the note's conclusion?",
            answer=AnswerSpec(
                kind="boolean", value=False, options=_BOOL,
                justification="a property of one instance does not generalise to the type",
            ),
            semantics=_facts(
                {"N": "Natural", "Square": "Matrix[Real, N, N]", "invertible": "Proposition"},
                {"N": "index", "Square": "obs", "invertible": "const"},
            ),
            reference="""
module LinInvertibilityDirection
index N : Natural
obs Square : Matrix[Real, N, N]
const invertible : Proposition
assume invertible
prove not (forall t : Real . invertible)
""",
            distractor="TRUE",
            error_category="equality_vs_implication",
            common_error="generalising an instance property to a universal claim",
            negated_claim="a property asserted of one matrix holds of every matrix of that size",
            reasoning_steps=3,
        ),
        _item(
            29, "row_column_prefix", "linear_algebra", "hard",
            prose=(
                "Statement one: for every row index there exists a column index whose entry is "
                "non-zero. Statement two: there exists a column index such that for every row "
                "index the entry is non-zero."
            ),
            question="Does statement one entail statement two?",
            answer=AnswerSpec(
                kind="boolean", value=False, options=_BOOL,
                justification=(
                    "statement two demands a single column that works for all rows; statement "
                    "one permits a different column per row"
                ),
            ),
            semantics=SemanticFacts(
                entities={},
                declaration_kinds={},
                quantifier_order=["forall row", "exists col", "exists col", "forall row"],
            ),
            reference="""
module LinRowColumnPrefix
require forall row : Natural . exists col : Natural . col > row
prove exists col : Natural . forall row : Natural . col > row
""",
            distractor="TRUE",
            error_category="quantifier_order",
            common_error="reading a per-row witness as a single shared witness",
            negated_claim="a per-row existential witness can always be taken uniformly",
            reasoning_steps=4,
        ),
        _item(
            30, "truncated_entry", "linear_algebra", "medium",
            prose=(
                "A vector entry is defined as one quarter, and a scaled entry is that value "
                "multiplied by eight. A working note truncates the entry to the single decimal "
                "digit zero point two before scaling."
            ),
            question="Give the exact value of the scaled entry, as a single number.",
            answer=AnswerSpec(
                kind="numeric", value=2.0,
                justification="0.25 * 8 = 2 exactly, whereas the truncated 0.2 * 8 = 1.6",
            ),
            semantics=_facts(
                {"entry": "Rational", "scaled_entry": "Real"},
                {"entry": "const"},
            ),
            reference="""
module LinTruncatedEntry
const entry : Rational
def scaled_entry := entry * 8.0
require entry = 1.0 / 4.0
prove scaled_entry = 2.0
""",
            distractor="1.6",
            error_category="approximation_vs_equality",
            common_error="scaling a truncated decimal instead of the exact rational",
            negated_claim="Ne(Rational(1,4)*8, 2)",
            reasoning_steps=3,
        ),
    ]


# ===========================================================================
# calculus -- 5   (H3-ineligible: no surface syntax for limits or derivatives)
# ===========================================================================


def _calculus() -> list[LiteItem]:
    return [
        _item(
            31, "linearisation_error", "calculus", "hard",
            prose=(
                "A smooth function is replaced by its first-order expansion about a point, and "
                "the resulting relation is written with an equals sign. The expansion neglects "
                "a remainder term that is not stated to vanish."
            ),
            question="Does the relation written with the equals sign neglect a term not stated to vanish?",
            answer=AnswerSpec(
                kind="boolean", value=True, options=_BOOL,
                justification="a truncated expansion is exact only where the remainder vanishes",
            ),
            semantics=_facts(
                {"exact_value": "Real", "linear_part": "Real", "remainder": "Real"},
                {"exact_value": "param", "linear_part": "param", "remainder": "param"},
            ),
            reference="""
module CalcLinearisationError
param exact_value : Real
param linear_part : Real
param remainder : Real
require exact_value = linear_part + remainder
assume remainder > 0.0
prove not (exact_value = linear_part)
""",
            distractor="FALSE",
            error_category="approximation_vs_equality",
            common_error="recording a truncated expansion as an identity",
            negated_claim="a first-order expansion equals the function away from the base point",
            reasoning_steps=3,
        ),
        _item(
            32, "differentiability_unstated", "calculus", "hard",
            prose=(
                "A function is stated to be continuous on an interval. A note applies a rule "
                "whose hypothesis is differentiability on that interval. Differentiability is "
                "not stated anywhere in the problem."
            ),
            question="Is the note's application of the rule licensed by the stated hypotheses?",
            answer=AnswerSpec(
                kind="boolean", value=False, options=_BOOL,
                justification="continuity does not entail differentiability; the rule's hypothesis is unmet",
            ),
            semantics=_facts(
                {"continuous_on": "Proposition", "differentiable_on": "Proposition"},
                {"continuous_on": "const", "differentiable_on": "const"},
            ),
            reference="""
module CalcDifferentiabilityUnstated
const continuous_on : Proposition
const differentiable_on : Proposition
assume continuous_on
prove not (continuous_on implies differentiable_on)
""",
            distractor="TRUE",
            error_category="assumption_boundary",
            common_error="silently upgrading continuity to differentiability",
            negated_claim="continuity on an interval entails differentiability on that interval",
            reasoning_steps=3,
        ),
        _item(
            33, "integration_variable_shadow", "calculus", "hard",
            prose=(
                "A module declares an upper limit named b and fixes it to nine. A definition "
                "takes its own argument, also written b, and returns that argument minus two. "
                "The definition is applied to the value five."
            ),
            question="What number does the definition produce for the input five? Give a single number.",
            answer=AnswerSpec(
                kind="numeric", value=3.0,
                justification="the argument shadows the module-level limit, so 5 - 2 = 3",
            ),
            semantics=_facts(
                {"b": "Real", "shift": "Function"},
                {"b": "const"},
            ),
            reference="""
module CalcIntegrationVariableShadow
const b : Real = 9.0
def shift(local_b : Real) := local_b - 2.0
require shift(5.0) = 3.0
""",
            distractor="7",
            error_category="binding_scope",
            common_error="resolving the definition's argument to the module-level limit",
            negated_claim="Ne(5 - 2, 3)",
            reasoning_steps=3,
        ),
        _item(
            34, "rate_dimension", "calculus", "medium",
            prose=(
                "A displacement quantity of dimension length is differentiated twice with "
                "respect to a time variable of dimension time. Each differentiation divides by "
                "one power of the differentiation variable's dimension."
            ),
            question="What is the physical dimension of the second derivative?",
            answer=AnswerSpec(
                kind="dimension", value="Length / Time^2",
                justification="L divided by T twice is L T^-2",
            ),
            semantics=_facts(
                {"displacement": "Quantity[Length]", "elapsed": "Quantity[Time]",
                 "second_rate": "Quantity"},
                {"displacement": "param", "elapsed": "param"},
                dimensions={"displacement": "Quantity[Length]", "elapsed": "Quantity[Time]"},
            ),
            reference="""
module CalcRateDimension
param displacement : Quantity[Length]
param elapsed : Quantity[Time]
def second_rate := displacement / elapsed^2
check dimension second_rate = Length / Time^2
""",
            distractor="Length / Time",
            error_category="dimensional_consistency",
            common_error="dividing by the time dimension once rather than twice",
            negated_claim="Ne(0 - 2, -2)",
            reasoning_steps=3,
        ),
        _item(
            35, "monotonicity_converse", "calculus", "hard",
            prose=(
                "A rule states that a strictly positive derivative on an interval entails that "
                "the function is strictly increasing there. A note reads the rule in the "
                "opposite direction."
            ),
            question="Is the opposite direction entailed by the stated rule?",
            answer=AnswerSpec(
                kind="boolean", value=False, options=_BOOL,
                justification=(
                    "a strictly increasing function may have a vanishing derivative at a point, "
                    "so the converse is not entailed"
                ),
            ),
            semantics=_facts(
                {"positive_derivative": "Proposition", "strictly_increasing": "Proposition"},
                {"positive_derivative": "const", "strictly_increasing": "const"},
            ),
            reference="""
module CalcMonotonicityConverse
const positive_derivative : Proposition
const strictly_increasing : Proposition
require positive_derivative implies strictly_increasing
prove not (strictly_increasing implies positive_derivative)
""",
            distractor="TRUE",
            error_category="equality_vs_implication",
            common_error="reading a sufficient condition as a necessary one",
            negated_claim="the converse of the monotonicity rule follows from the rule itself",
            reasoning_steps=3,
        ),
    ]


# ===========================================================================
# epistemic reasoning -- 5
# ===========================================================================


def _epistemic() -> list[LiteItem]:
    return [
        _item(
            36, "pvalue_is_not_posterior", "epistemic_reasoning", "hard",
            prose=(
                "A report gives a tail probability computed under a null model and, separately, "
                "a posterior probability for a hypothesis. A summary treats the two numbers as "
                "interchangeable because both lie in the unit interval."
            ),
            question="Are the two reported quantities of different kinds?",
            answer=AnswerSpec(
                kind="boolean", value=True, options=_BOOL,
                justification=(
                    "they are pairwise incomparable scalars with no coercion path between them; "
                    "sharing a range is not sharing a meaning"
                ),
            ),
            semantics=_facts(
                {"tail_prob": "PValue", "hypothesis_prob": "PosteriorProbability"},
                {"tail_prob": "param", "hypothesis_prob": "param"},
            ),
            reference="""
module EpiPValueIsNotPosterior
param tail_prob : PValue
param hypothesis_prob : PosteriorProbability
assume tail_prob < 0.05
prove not (tail_prob = hypothesis_prob)
""",
            distractor="FALSE",
            error_category="distribution_vs_value",
            common_error="identifying two scalars because their ranges coincide",
            negated_claim="a tail probability and a posterior probability denote the same quantity",
            reasoning_steps=3,
        ),
        _item(
            37, "credence_is_not_frequency", "epistemic_reasoning", "hard",
            prose=(
                "A degree of belief about a single fixed event is reported alongside a long-run "
                "relative frequency for a repeatable trial. A summary averages the two numbers "
                "into one figure."
            ),
            question="Is averaging the two numbers a well-defined operation on the stated quantities?",
            answer=AnswerSpec(
                kind="boolean", value=False, options=_BOOL,
                justification=(
                    "a posterior probability about a fixed event and a frequency over repeated "
                    "trials are different objects; their arithmetic mean denotes nothing"
                ),
            ),
            semantics=_facts(
                {"belief": "PosteriorProbability", "frequency": "Probability"},
                {"belief": "param", "frequency": "param"},
            ),
            reference="""
module EpiCredenceIsNotFrequency
param belief : PosteriorProbability
param frequency : Probability
assume belief > 0.0
prove not (belief = frequency)
""",
            distractor="TRUE",
            error_category="distribution_vs_value",
            common_error="averaging two quantities that share a range but not a referent",
            negated_claim="a posterior probability and a relative frequency are the same kind of quantity",
            reasoning_steps=3,
        ),
        _item(
            38, "law_is_not_draw", "epistemic_reasoning", "hard",
            prose=(
                "A model declares a law over the reals and, separately, a random variable "
                "governed by that law. A note substitutes the law itself wherever the random "
                "variable appears in an arithmetic expression."
            ),
            question="Would substituting the law for the random variable be rejected as a type error?",
            answer=AnswerSpec(
                kind="boolean", value=True, options=_BOOL,
                justification=(
                    "a Distribution[Real] is not a value of Real and is not a "
                    "RandomVariable[Real]; no coercion path exists"
                ),
            ),
            semantics=_facts(
                {"sd": "PositiveReal", "centre": "Real", "draw": "RandomVariable[Real]"},
                {"sd": "const", "centre": "const", "draw": "rv"},
                law_families={"draw": "Normal"},
                laws={"draw": {"location": "centre", "scale": "sd"}},
            ),
            reference="""
module EpiLawIsNotDraw
const sd : PositiveReal
const centre : Real
rv draw : RandomVariable[Real]
law draw ~ Normal(location := centre, scale := sd)
infer expectation draw
""",
            distractor="FALSE",
            error_category="distribution_vs_value",
            common_error="using a distribution in a position that requires a value",
            negated_claim="a Distribution[Real] may stand where a Real is required",
            reasoning_steps=3,
        ),
        _item(
            39, "evidence_not_stated", "epistemic_reasoning", "medium",
            prose=(
                "A conclusion is drawn from a stated observation together with a background "
                "claim that the write-up never records. The write-up presents the conclusion as "
                "following from the observation alone."
            ),
            question="Does the conclusion depend on a premise the write-up never records?",
            answer=AnswerSpec(
                kind="boolean", value=True, options=_BOOL,
                justification="an unrecorded premise is not part of the recorded content",
            ),
            semantics=_facts(
                {"observation": "Proposition", "conclusion": "Proposition"},
                {"observation": "const", "conclusion": "const"},
                prohibited_assumptions=["the unrecorded background claim"],
            ),
            reference="""
module EpiEvidenceNotStated
const observation : Proposition
const conclusion : Proposition
assume observation
prove not (observation implies conclusion)
""",
            distractor="FALSE",
            error_category="assumption_boundary",
            common_error="supplying a missing premise from background knowledge",
            negated_claim="a conclusion requiring an unrecorded premise follows from the record alone",
            reasoning_steps=3,
        ),
        _item(
            40, "confidence_roles", "epistemic_reasoning", "medium",
            prose=(
                "A procedure reports two numbers: a threshold below which a result is called "
                "significant, and the tail probability actually observed. The threshold is one "
                "twentieth and the observed tail probability is one fiftieth."
            ),
            question=(
                "Give the role map for the two reported numbers, as a JSON object from role to "
                "symbol."
            ),
            answer=AnswerSpec(
                kind="role_map",
                value={"threshold": "cutoff", "observed": "tail_prob"},
                justification="the cutoff fills the threshold role and the tail probability the observed role",
            ),
            semantics=_facts(
                {"cutoff": "PValue", "tail_prob": "PValue"},
                {"cutoff": "const", "tail_prob": "param"},
            ),
            reference="""
module EpiConfidenceRoles
const cutoff : PValue
param tail_prob : PValue
assume cutoff > tail_prob
prove tail_prob < cutoff
""",
            distractor='{"threshold": "tail_prob", "observed": "cutoff"}',
            error_category="role_assignment",
            common_error="assigning the roles by order of appearance rather than by meaning",
            negated_claim="the observed tail probability fills the threshold role",
            reasoning_steps=3,
        ),
    ]


def build_items() -> list[LiteItem]:
    """The 40 items, in a fixed order. Deterministic; identical on every call."""
    items = (
        _algebra()
        + _probability()
        + _logic()
        + _dimensions()
        + _linear_algebra()
        + _calculus()
        + _epistemic()
    )
    ids = [i.id for i in items]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise AssertionError(f"duplicate item ids: {dupes}")
    return items
