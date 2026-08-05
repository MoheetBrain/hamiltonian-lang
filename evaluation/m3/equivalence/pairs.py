"""The paired benchmark for the equivalence scorer.

Every pair carries a *hand-checked* truth label and a category. The labels are the
ground truth against which precision is measured; they are not produced by the
scorer and must never be edited to make a run come out green.

Labels
------
``EQUIVALENT``
    The two encodings denote the same mathematical object. Calling this pair
    non-equivalent is a **false negative**: it costs coverage and, in an H1/H2
    aggregate, biases the hypothesis downward.
``NONEQUIVALENT``
    The two denote different objects. Calling this pair equivalent is a **false
    positive**: it silently declares a wrong answer right and corrupts every
    number computed from it. The approval criterion is zero of these.

Categories, one per requirement in the directive: ``identical``,
``structurally_equivalent``, ``near_miss``, ``assumption_sensitive``,
``scope_sensitive``, ``dimension_sensitive``, ``epistemic``, ``adversarial``.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["EQUIVALENT", "NONEQUIVALENT", "PairCase", "PAIRS", "CATEGORIES", "by_category"]

EQUIVALENT = "EQUIVALENT"
NONEQUIVALENT = "NONEQUIVALENT"


@dataclass(frozen=True)
class PairCase:
    """One reference/candidate pair with its hand-checked truth."""

    case_id: str
    category: str
    truth: str
    reference: str
    candidate: str
    rationale: str

    def __post_init__(self) -> None:
        if self.truth not in (EQUIVALENT, NONEQUIVALENT):
            raise ValueError(f"{self.case_id}: unknown truth label {self.truth!r}")
        if not self.rationale.strip():
            raise ValueError(f"{self.case_id}: a label without a rationale is a guess")


def _m(*lines: str) -> str:
    return "\n".join(("module M", *lines)) + "\n"


PAIRS: tuple[PairCase, ...] = (
    # -- identical ---------------------------------------------------------
    PairCase(
        "identical.same_text",
        "identical",
        EQUIVALENT,
        _m("param a : Real", "def f := a + 1"),
        _m("param a : Real", "def f := a + 1"),
        "byte-identical sources denote one object",
    ),
    PairCase(
        "identical.comments_and_layout",
        "identical",
        EQUIVALENT,
        _m("param a : Real", "def f := a + 1"),
        _m("# a comment", "param a : Real", "", "def f := a  +  1"),
        "comments and layout are not part of the object",
    ),
    PairCase(
        "identical.declaration_order",
        "identical",
        EQUIVALENT,
        _m("param a : Real", "param b : Real", "def f := a + b"),
        _m("param b : Real", "param a : Real", "def f := a + b"),
        "a module is a collection of statements; declaring b first changes nothing",
    ),
    PairCase(
        "identical.alpha_rename",
        "identical",
        EQUIVALENT,
        _m("param a : Real", "def f := a + 1"),
        "module Other\nparam z : Real\ndef g := z + 1\n",
        "a consistent renaming of every bound name, plus a different module label",
    ),
    # -- structurally different but equivalent ------------------------------
    PairCase(
        "equivalent.commutative_addition",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param a : Real", "param b : Real", "def f := a + b"),
        _m("param a : Real", "param b : Real", "def f := b + a"),
        "addition is commutative over the reals",
    ),
    PairCase(
        "equivalent.associative_regrouping",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param a : Real", "param b : Real", "param c : Real", "def f := (a + b) + c"),
        _m("param a : Real", "param b : Real", "param c : Real", "def f := a + (b + c)"),
        "addition is associative over the exact reals this language denotes",
    ),
    PairCase(
        "equivalent.constant_folding",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param x : Real", "def f := 2 * 3 * x"),
        _m("param x : Real", "def f := 6 * x"),
        "2*3 and 6 are the same number",
    ),
    PairCase(
        "equivalent.expansion",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param a : Real", "def f := (a + 1) * (a + 1)"),
        _m("param a : Real", "def f := a^2 + 2 * a + 1"),
        "the binomial expansion is an identity",
    ),
    PairCase(
        "equivalent.factorisation",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param a : Real", "def f := a^2 - 1"),
        _m("param a : Real", "def f := (a - 1) * (a + 1)"),
        "difference of two squares",
    ),
    PairCase(
        "equivalent.division_by_constant",
        "structurally_equivalent",
        EQUIVALENT,
        _m(
            "param m : Quantity[Mass]",
            "param v : Quantity[Length / Time]",
            "def ke := 0.5 * m * v^2",
        ),
        _m(
            "param m : Quantity[Mass]",
            "param v : Quantity[Length / Time]",
            "def ke := m * v^2 / 2",
        ),
        "multiplying by one half and dividing by two agree, and the dimensions match",
    ),
    PairCase(
        "equivalent.probability_expression",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param p : Probability", "def var_bernoulli := p * (1 - p)"),
        _m("param p : Probability", "def var_bernoulli := p - p^2"),
        "the Bernoulli variance, expanded",
    ),
    PairCase(
        "equivalent.linear_equation",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param x : Real", "require 2 * x = 6"),
        _m("param x : Real", "require x = 3"),
        "the two equations have the same solution set",
    ),
    PairCase(
        "equivalent.inequality_shift",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param x : Real", "require x + 1 < 3"),
        _m("param x : Real", "require x < 2"),
        "subtracting one from both sides preserves the direction",
    ),
    PairCase(
        "equivalent.inequality_positive_scale",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param x : Real", "require 2 * x < 4"),
        _m("param x : Real", "require x < 2"),
        "dividing by the positive constant 2 preserves the direction",
    ),
    PairCase(
        "equivalent.inequality_negative_scale",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param x : Real", "require -x < -2"),
        _m("param x : Real", "require x > 2"),
        "multiplying by -1 reverses the direction; the two describe the same set",
    ),
    PairCase(
        "equivalent.renamed_auxiliary",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param a : Real", "param b : Real", "def aux := a + b", "def f := aux * 2"),
        _m("param a : Real", "param b : Real", "def helper := a + b", "def f := helper * 2"),
        "the auxiliary definition is renamed; nothing else changes",
    ),
    PairCase(
        "equivalent.conjunction_commutes",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param p : Bool", "param q : Bool", "prove p and q"),
        _m("param p : Bool", "param q : Bool", "prove q and p"),
        "conjunction is commutative",
    ),
    PairCase(
        "equivalent.contrapositive",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param p : Bool", "param q : Bool", "prove p => q"),
        _m("param p : Bool", "param q : Bool", "prove (not q) => (not p)"),
        "a conditional and its contrapositive are equivalent",
    ),
    PairCase(
        "equivalent.de_morgan",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param p : Bool", "param q : Bool", "prove not (p and q)"),
        _m("param p : Bool", "param q : Bool", "prove (not p) or (not q)"),
        "De Morgan's law",
    ),
    PairCase(
        "equivalent.double_negation",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param p : Bool", "prove not (not p)"),
        _m("param p : Bool", "prove p"),
        "double negation elimination holds in the classical setting this language uses",
    ),
    PairCase(
        "equivalent.cancelling_difference",
        "structurally_equivalent",
        EQUIVALENT,
        _m("param b : Real", "param c : Real", "def f := b - b"),
        _m("param b : Real", "param c : Real", "def f := c - c"),
        "both sides are identically zero, though every sub-term differs",
    ),
    PairCase(
        "equivalent.quantifier_same_kind_swap",
        "structurally_equivalent",
        EQUIVALENT,
        _m("prove forall x : Real . forall y : Real . x + y = y + x"),
        _m("prove forall y : Real . forall x : Real . x + y = y + x"),
        "two adjacent universals commute; only alternation across kinds matters",
    ),
    # -- near-miss non-equivalent -------------------------------------------
    PairCase(
        "nearmiss.subtraction_order",
        "near_miss",
        NONEQUIVALENT,
        _m("param a : Real", "param b : Real", "def f := a - b"),
        _m("param a : Real", "param b : Real", "def f := b - a"),
        "subtraction is not commutative",
    ),
    PairCase(
        "nearmiss.division_order",
        "near_miss",
        NONEQUIVALENT,
        _m("param x : PositiveReal", "param y : PositiveReal", "def f := x / y"),
        _m("param x : PositiveReal", "param y : PositiveReal", "def f := y / x"),
        "division is not commutative",
    ),
    PairCase(
        "nearmiss.square_versus_double",
        "near_miss",
        NONEQUIVALENT,
        _m("param a : Real", "def f := a^2"),
        _m("param a : Real", "def f := 2 * a"),
        "squaring and doubling agree only at 0 and 2",
    ),
    PairCase(
        "nearmiss.strictness",
        "near_miss",
        NONEQUIVALENT,
        _m("param x : Real", "require x < 2"),
        _m("param x : Real", "require x <= 2"),
        "the boundary point 2 satisfies one and not the other",
    ),
    PairCase(
        "nearmiss.wrong_constant",
        "near_miss",
        NONEQUIVALENT,
        _m("param x : Real", "require 2 * x = 6"),
        _m("param x : Real", "require x = 6"),
        "the solution sets are {3} and {6}",
    ),
    PairCase(
        "nearmiss.conjunction_for_disjunction",
        "near_miss",
        NONEQUIVALENT,
        _m("param p : Bool", "param q : Bool", "prove p and q"),
        _m("param p : Bool", "param q : Bool", "prove p or q"),
        "conjunction is not disjunction",
    ),
    PairCase(
        "nearmiss.converse",
        "near_miss",
        NONEQUIVALENT,
        _m("param p : Bool", "param q : Bool", "prove p => q"),
        _m("param p : Bool", "param q : Bool", "prove q => p"),
        "a conditional is not its converse",
    ),
    # -- assumption-sensitive -----------------------------------------------
    PairCase(
        "assumption.positive_divisor",
        "assumption_sensitive",
        EQUIVALENT,
        _m("param a : PositiveReal", "param x : Real", "require a * x < 6"),
        _m("param a : PositiveReal", "param x : Real", "require x < 6 / a"),
        "dividing by a preserves the direction because a is declared positive",
    ),
    PairCase(
        "assumption.unknown_sign_divisor",
        "assumption_sensitive",
        NONEQUIVALENT,
        _m("param a : Real", "param x : Real", "require a * x < 6"),
        _m("param a : Real", "param x : Real", "require x < 6 / a"),
        "with a negative the direction reverses, so the two differ",
    ),
    PairCase(
        "assumption.sqrt_of_square_positive",
        "assumption_sensitive",
        EQUIVALENT,
        _m("param x : PositiveReal", "def f := sqrt(x^2)"),
        _m("param x : PositiveReal", "def f := x"),
        "sqrt(x^2) = x when x is declared positive",
    ),
    PairCase(
        "assumption.sqrt_of_square_real",
        "assumption_sensitive",
        NONEQUIVALENT,
        _m("param x : Real", "def f := sqrt(x^2)"),
        _m("param x : Real", "def f := x"),
        "sqrt(x^2) is |x|, which differs from x at every negative value",
    ),
    # -- scope-sensitive -----------------------------------------------------
    PairCase(
        "scope.forall_exists_swap",
        "scope_sensitive",
        NONEQUIVALENT,
        _m("prove forall x : Real . exists y : Real . y > x"),
        _m("prove exists y : Real . forall x : Real . y > x"),
        "the first is true over the reals and the second is false",
    ),
    PairCase(
        "scope.exists_forall_swap_in_require",
        "scope_sensitive",
        NONEQUIVALENT,
        _m("require exists y : Real . forall x : Real . y >= x"),
        _m("require forall x : Real . exists y : Real . y >= x"),
        "the same alternation, imposed as a constraint rather than a claim",
    ),
    # -- dimension-sensitive -------------------------------------------------
    PairCase(
        "dimension.mass_versus_length",
        "dimension_sensitive",
        NONEQUIVALENT,
        _m("param m : Quantity[Mass]", "def f := m"),
        _m("param m : Quantity[Length]", "def f := m"),
        "different exponent vectors are different magnitudes",
    ),
    PairCase(
        "dimension.same_dimension_renamed",
        "dimension_sensitive",
        EQUIVALENT,
        _m("param m : Quantity[Mass]", "def f := m * 2"),
        "module Other\nparam mass : Quantity[Mass]\ndef doubled := mass * 2\n",
        "the same dimensioned quantity under a different name",
    ),
    PairCase(
        "dimension.velocity_versus_acceleration",
        "dimension_sensitive",
        NONEQUIVALENT,
        _m("param v : Quantity[Length / Time]", "def f := v"),
        _m("param v : Quantity[Length / Time^2]", "def f := v"),
        "velocity and acceleration have different time exponents",
    ),
    # -- epistemically different ---------------------------------------------
    PairCase(
        "epistemic.pvalue_versus_posterior",
        "epistemic",
        NONEQUIVALENT,
        _m("const t : PValue = 0.05"),
        _m("const t : PosteriorProbability = 0.05"),
        "P(data this extreme | H0) is not P(H0 | data); the prosecutor's fallacy",
    ),
    PairCase(
        "epistemic.pvalue_versus_probability",
        "epistemic",
        NONEQUIVALENT,
        _m("const t : PValue = 0.05"),
        _m("const t : Probability = 0.05"),
        "a tail probability under a null is not a model probability",
    ),
    PairCase(
        "epistemic.observed_versus_unknown",
        "epistemic",
        NONEQUIVALENT,
        _m("obs n : Natural = 10"),
        _m("param n : Natural = 10"),
        "observed data and an unknown parameter are different epistemic objects",
    ),
    PairCase(
        "epistemic.assumed_versus_proved",
        "epistemic",
        NONEQUIVALENT,
        _m("param x : Real", "assume x > 0"),
        _m("param x : Real", "prove x > 0"),
        "granting a proposition and claiming to establish it are different assertions",
    ),
    PairCase(
        "epistemic.random_variable_versus_value",
        "epistemic",
        NONEQUIVALENT,
        _m("rv y : Real"),
        _m("param y : Real"),
        "a RandomVariable[Real] is a measurable function, not a real number",
    ),
    PairCase(
        "epistemic.conditional_versus_marginal",
        "epistemic",
        NONEQUIVALENT,
        _m(
            "param t : Probability",
            "rv y : Natural",
            "law y | t ~ Binomial(trials := 10, prob := t)",
        ),
        _m(
            "param t : Probability",
            "rv y : Natural",
            "law y ~ Binomial(trials := 10, prob := t)",
        ),
        "a conditional law and a marginal law are different objects",
    ),
    # -- adversarial: the five the directive names ---------------------------
    PairCase(
        "adversarial.implication_direction",
        "adversarial",
        NONEQUIVALENT,
        _m("param p : Bool", "param q : Bool", "prove p => q"),
        _m("param p : Bool", "param q : Bool", "prove q => p"),
        "p => q is not q => p",
    ),
    PairCase(
        "adversarial.quantifier_order",
        "adversarial",
        NONEQUIVALENT,
        _m("prove forall x : Real . exists y : Real . y > x"),
        _m("prove exists y : Real . forall x : Real . y > x"),
        "forall-exists is not exists-forall",
    ),
    PairCase(
        "adversarial.pvalue_posterior",
        "adversarial",
        NONEQUIVALENT,
        _m("param theta : Probability", "const observed : PValue = 0.03"),
        _m("param theta : Probability", "const observed : PosteriorProbability = 0.03"),
        "a p-value is not a posterior probability",
    ),
    PairCase(
        "adversarial.power_association",
        "adversarial",
        NONEQUIVALENT,
        _m(
            "param a : PositiveReal",
            "param b : Real",
            "param c : Real",
            "def f := (a^b)^c",
        ),
        _m(
            "param a : PositiveReal",
            "param b : Real",
            "param c : Real",
            "def f := a^(b^c)",
        ),
        "(a^b)^c is a^(b*c), not a^(b^c); a renderer in this repository once printed "
        "the first as `a^b^c`, which reads back as the second",
    ),
    PairCase(
        "adversarial.division_for_multiplication",
        "adversarial",
        NONEQUIVALENT,
        _m("param x : Real", "param y : PositiveReal", "def f := x / y"),
        _m("param x : Real", "param y : PositiveReal", "def f := x * y"),
        "x/y is not x*y",
    ),
)

CATEGORIES: tuple[str, ...] = (
    "identical",
    "structurally_equivalent",
    "near_miss",
    "assumption_sensitive",
    "scope_sensitive",
    "dimension_sensitive",
    "epistemic",
    "adversarial",
)


def by_category(category: str) -> tuple[PairCase, ...]:
    return tuple(p for p in PAIRS if p.category == category)
