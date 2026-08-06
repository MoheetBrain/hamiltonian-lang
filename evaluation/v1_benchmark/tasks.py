"""The 24 matched-V1 benchmark tasks.

What this corpus is for
-----------------------
To produce the project's first evidence about whether HML **helps**, as distinct from
whether the model can write it. ACQ0 asks the second question. This asks the first.

Every task is authored as a :class:`~evaluation.corpus.cso.CanonicalSemanticObject`, so
both arms are projections of one structure and neither can be handed a differently-worded
problem. That is the same discipline HML-EVAL-001 used, and it is the only part of the
pilot design worth keeping.

The design constraint that dominates every other
------------------------------------------------
**Do not build another ceiling.** HML-EVAL-001 scored 93% in all seven arms, had a
minimum detectable effect near 33 points, and produced zero discordant pairs in six of
seven contrasts. It measured nothing. A paired design only sees the discordant pairs, so
a corpus everything gets right has no signal in it at all, regardless of sample size.

Each task therefore carries an **engineered attractor**: a specific wrong answer reachable
by a standard, plausible, invalid shortcut. That is recorded in ``distractors`` and graded
in :mod:`evaluation.v1_benchmark.difficulty`. Predicted base accuracy is
``PREDICTED_NOT_MEASURED`` and stays that way until a run measures it.

Every numeric answer key below was verified independently before authoring: by brute-force
enumeration where the space is finite (the ``max``/``min`` item, the quantifier items), by
exact rational arithmetic where a closed form exists (the law-of-total-variance item, the
Vieta item), and by numerical cross-check against a second method where neither applies
(the implicit second derivative was confirmed by a central finite difference on the
implicitly solved curve). A benchmark with a wrong key measures the key.

Tolerances
----------
Numeric tolerance is ``5e-3`` for values with a non-terminating decimal expansion and
``1e-9`` for exact integers. ``check_answer`` treats tolerance as
``max(absolute, relative)``, so ``5e-3`` accepts a three-decimal rounding of ``16/7`` and
still rejects every named attractor, each of which differs by orders of magnitude more.
The looser tolerance is deliberate: at the default ``1e-6`` the benchmark would be scoring
decimal formatting, and formatting is not the variable under study.

No reference encoding
---------------------
``reference_hml`` is empty on every task, and that is correct rather than missing. This is
a *reasoning* benchmark: producing a formalisation is part of the HML arm's work, so there
is no authored target to withhold. The consequence for the oracle guard is documented in
:mod:`evaluation.v1_benchmark.arms`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evaluation.corpus.cso import AnswerSpec, CanonicalSemanticObject, SemanticFacts
from evaluation.v1_benchmark.difficulty import (
    Attractor,
    DifficultyEstimate,
    estimate,
)

__all__ = [
    "BenchTask",
    "V1_BENCHMARK_VERSION",
    "DOMAINS",
    "TASK_COUNT",
    "EXTENSION_COUNT",
    "build_tasks",
    "by_domain",
]

#: Corpus version. Distinct from every other corpus version in the repository.
V1_BENCHMARK_VERSION = "v1bench-v1"

#: The seven domains the Lead specified. Order is fixed and is the report order.
DOMAINS: tuple[str, ...] = (
    "algebra",
    "probability_statistics",
    "logic_quantifier_scope",
    "dimensions_physics",
    "linear_algebra",
    "calculus",
    "epistemic_reasoning",
)

#: The pre-registered first tranche.
TASK_COUNT = 24

#: The size the study extends to when the first tranche is inconclusive.
EXTENSION_COUNT = 40

#: Tolerance for a value with a non-terminating decimal expansion.
_TOL_INEXACT = 5e-3
#: Tolerance for an exact integer answer.
_TOL_EXACT = 1e-9


@dataclass(frozen=True)
class BenchTask:
    """One task, its predicted difficulty, and the named error it is built around."""

    cso: CanonicalSemanticObject
    difficulty: DifficultyEstimate
    #: The invalid shortcut in one sentence. Prose, for the report.
    attractor_description: str
    #: How the answer key was independently confirmed.
    key_verification: str

    @property
    def id(self) -> str:
        return self.cso.id

    @property
    def domain(self) -> str:
        return self.cso.domain

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain,
            "question": self.cso.question,
            "answer_kind": self.cso.answer.kind,
            "difficulty": self.difficulty.to_dict(),
            "attractor": self.attractor_description,
            "key_verification": self.key_verification,
        }


def _task(
    number: int,
    slug: str,
    domain: str,
    prose: str,
    question: str,
    answer: AnswerSpec,
    semantics: SemanticFacts,
    distractor: str,
    attractor_description: str,
    key_verification: str,
    dependent_steps: int,
    attractor: Attractor,
    rationale: str,
) -> BenchTask:
    chance_floor = 0.0
    if answer.kind == "boolean":
        chance_floor = 0.5
    elif answer.kind == "choice" and answer.options:
        chance_floor = 1.0 / len(answer.options)

    cso = CanonicalSemanticObject(
        id=f"v1b_{number:02d}_{slug}",
        domain=domain,
        difficulty="hard",
        prose=prose.strip(),
        question=question.strip(),
        answer=answer,
        semantics=semantics,
        distractors=[distractor.strip()],
        reference_hml="",
        generator=f"{V1_BENCHMARK_VERSION}:{slug}",
        corpus_version=V1_BENCHMARK_VERSION,
    )
    return BenchTask(
        cso=cso,
        difficulty=estimate(
            dependent_steps=dependent_steps,
            attractor=attractor,
            chance_floor=chance_floor,
            rationale=rationale,
        ),
        attractor_description=attractor_description.strip(),
        key_verification=key_verification.strip(),
    )


def _facts(**kw: Any) -> SemanticFacts:
    return SemanticFacts(**kw)


# ===========================================================================
# algebra -- 3
# ===========================================================================


def _algebra() -> list[BenchTask]:
    return [
        _task(
            1,
            "radical_extraneous",
            "algebra",
            """
Consider the equation sqrt(2*x + 7) - sqrt(x + 3) = 1, where sqrt denotes the
non-negative square root and x ranges over the real numbers for which both radicands
are non-negative.
""",
            "Report the sum of all real solutions x of this equation.",
            AnswerSpec(
                kind="numeric",
                value=-2.0,
                tolerance=_TOL_EXACT,
                justification=(
                    "Setting u = sqrt(2x+7), v = sqrt(x+3) gives u - v = 1 and "
                    "u^2 - v^2 = x + 4, so u + v = x + 4 and v = (x+3)/2. Then "
                    "(x+3)^2 = 4(x+3), so x = -3 or x = 1. BOTH satisfy the original "
                    "equation: at x = -3, sqrt(1) - sqrt(0) = 1; at x = 1, 3 - 2 = 1. "
                    "Neither is extraneous. Sum = -2."
                ),
            ),
            _facts(
                entities={"x": "Real"},
                declaration_kinds={"x": "unknown"},
                constraints=["2*x + 7 >= 0", "x + 3 >= 0"],
            ),
            "1 -- reporting only x = 1, having discarded x = -3 as extraneous without substituting it back",
            "Squaring introduces extraneous roots often enough that discarding the "
            "boundary root becomes reflexive; here the boundary root is genuine, so the "
            "habit that usually protects the solver is exactly what defeats them.",
            "Both candidate roots substituted back into the original equation in exact "
            "arithmetic; both satisfy it to machine precision.",
            4,
            Attractor.HIGH,
            "Four dependent steps (rationalise, reduce, factor, verify each root) with a "
            "high-reachability attractor: the verification step is the one solvers skip.",
        ),
        _task(
            2,
            "vieta_reciprocal_squares",
            "algebra",
            """
Let a, b and c be the three roots of the cubic polynomial x^3 - 5*x^2 + 6*x - 1.
All three roots are real and none of them is rational.
""",
            "Report the exact value of 1/a^2 + 1/b^2 + 1/c^2.",
            AnswerSpec(
                kind="numeric",
                value=26.0,
                tolerance=_TOL_EXACT,
                justification=(
                    "With e1 = 5, e2 = 6, e3 = 1 the identity "
                    "sum 1/a^2 = (e2^2 - 2*e3*e1) / e3^2 gives (36 - 10)/1 = 26."
                ),
            ),
            _facts(
                entities={"a": "Real", "b": "Real", "c": "Real"},
                declaration_kinds={"a": "root", "b": "root", "c": "root"},
                constraints=["a + b + c = 5", "a*b + b*c + c*a = 6", "a*b*c = 1"],
            ),
            "36 -- using e2^2 alone and omitting the -2*e3*e1 cross term",
            "The symmetric-function identity for reciprocal squares needs the cross term; "
            "dropping it leaves a clean-looking 36. The roots are irrational by "
            "construction so no numeric shortcut rescues the omission.",
            "Cubic confirmed to have three real irrational roots by sign-change bisection "
            "over [-20, 20]; the numerical sum of 1/r^2 over the located roots agrees with "
            "the Vieta value to 9 decimal places.",
            5,
            Attractor.MEDIUM,
            "Five dependent steps (identify the symmetric functions, recall or derive the "
            "identity, apply, and confirm no rational root permits a shortcut).",
        ),
        _task(
            3,
            "mobius_iteration_period",
            "algebra",
            """
Define f(x) = 1 / (1 - x) for every real x other than 1. Write f^[n] for the n-fold
composition of f with itself, so that f^[1] = f and f^[n](x) = f(f^[n-1](x)).
""",
            "Report the value of f^[2024](3).",
            AnswerSpec(
                kind="numeric",
                value=0.6666666666666666,
                tolerance=_TOL_INEXACT,
                justification=(
                    "f has period 3: f(x) = 1/(1-x), f^[2](x) = (x-1)/x, f^[3](x) = x. "
                    "2024 mod 3 = 2, so f^[2024] = f^[2] and f^[2](3) = 2/3."
                ),
            ),
            _facts(
                entities={"f": "Function[Real, Real]", "x": "Real"},
                declaration_kinds={"f": "definition"},
                dependencies={"f_iterate": ["f"]},
            ),
            "3 -- concluding 2024 is a multiple of the period and returning the input unchanged",
            "The period is 3 and 2024 is not a multiple of it, but 2+0+2+4 = 8 offers no "
            "divisibility cue and the identity answer feels like the intended elegance.",
            "Verified by exact rational iteration of all 2024 compositions with "
            "fractions.Fraction, which returned 2/3.",
            4,
            Attractor.HIGH,
            "Four dependent steps (compute the orbit, detect the period, reduce the index "
            "modulo it, evaluate) with an off-by-one index reduction as the attractor.",
        ),
    ]


# ===========================================================================
# probability and statistics -- 4
# ===========================================================================


def _probability() -> list[BenchTask]:
    return [
        _task(
            4,
            "conditional_min_given_max",
            "probability_statistics",
            """
X and Y are independent and identically distributed, each uniform on the set
{1, 2, 3, 4, 5, 6}.
""",
            "Report the conditional expectation of min(X, Y) given that max(X, Y) = 4.",
            AnswerSpec(
                kind="numeric",
                value=2.2857142857142856,
                tolerance=_TOL_INEXACT,
                justification=(
                    "Seven ordered pairs have max 4: (4,1),(1,4),(4,2),(2,4),(4,3),(3,4),"
                    "(4,4). Their minima are 1,1,2,2,3,3,4, summing to 16, so the "
                    "conditional expectation is 16/7."
                ),
            ),
            _facts(
                entities={"X": "RandomVariable[Integer]", "Y": "RandomVariable[Integer]"},
                declaration_kinds={"X": "observation", "Y": "observation"},
                law_families={"X": "DiscreteUniform", "Y": "DiscreteUniform"},
                conditioning={"min": ["max(X,Y) = 4"]},
            ),
            "2.5 -- treating min as uniform on {1,2,3,4} given the conditioning event",
            "Conditioning on the maximum leaves the minimum non-uniform: the diagonal "
            "outcome (4,4) has half the weight of each off-diagonal value, and assuming "
            "uniformity gives the tidy 2.5.",
            "Exhaustive enumeration of all 36 ordered pairs, filtering on max == 4.",
            5,
            Attractor.HIGH,
            "Five dependent steps (characterise the event, enumerate it, weight the "
            "diagonal correctly, sum, divide) with a strong uniformity attractor.",
        ),
        _task(
            5,
            "sd_of_linear_combination",
            "probability_statistics",
            """
X and Y are random variables. The standard deviation of X is 3, the standard deviation
of Y is 4, and the correlation between X and Y is -0.5.
""",
            "Report the standard deviation of the random variable 2*X - Y.",
            AnswerSpec(
                kind="numeric",
                value=8.717797887081348,
                tolerance=_TOL_INEXACT,
                justification=(
                    "Cov(X,Y) = -0.5 * 3 * 4 = -6. "
                    "Var(2X - Y) = 4*Var(X) + Var(Y) - 2*2*Cov(X,Y) "
                    "= 36 + 16 + 24 = 76, so the standard deviation is sqrt(76)."
                ),
            ),
            _facts(
                entities={"X": "RandomVariable[Real]", "Y": "RandomVariable[Real]"},
                declaration_kinds={"X": "observation", "Y": "observation"},
                constraints=["sd(X) = 3", "sd(Y) = 4", "corr(X, Y) = -0.5"],
            ),
            "7.2111 -- computing sqrt(4*9 + 16) and ignoring the covariance term entirely",
            "Two sign flips have to survive at once: the minus in 2X - Y and the negative "
            "correlation, whose product makes the covariance term add rather than subtract. "
            "Dropping the term altogether is the commoner failure and gives sqrt(52).",
            "Closed-form bilinear expansion of Var(aX + bY); arithmetic recomputed "
            "independently.",
            4,
            Attractor.HIGH,
            "Four dependent steps with a double sign inversion, the classic point at which "
            "a variance calculation silently loses a term.",
        ),
        _task(
            6,
            "simpson_reversal",
            "probability_statistics",
            """
A treatment and a control were each given to 150 patients, split across two severity
strata.

Mild stratum: the treatment succeeded for 60 of 70 patients; the control succeeded for
90 of 110 patients.

Severe stratum: the treatment succeeded for 30 of 80 patients; the control succeeded for
10 of 40 patients.
""",
            """
Pooling both strata, report the overall treatment success rate minus the overall control
success rate, as a decimal fraction rather than a percentage.
""",
            AnswerSpec(
                kind="numeric",
                value=-0.06666666666666665,
                tolerance=_TOL_INEXACT,
                justification=(
                    "Treatment: (60+30)/150 = 0.6. Control: (90+10)/150 = 0.666667. "
                    "Difference = -1/15. The treatment wins in the mild stratum "
                    "(0.857 vs 0.818) and in the severe stratum (0.375 vs 0.250) yet "
                    "loses overall, because the treatment arm is concentrated in the "
                    "severe stratum where both rates are low."
                ),
            ),
            _facts(
                entities={
                    "treatment_rate": "Probability",
                    "control_rate": "Probability",
                },
                declaration_kinds={
                    "treatment_rate": "derived",
                    "control_rate": "derived",
                },
                constraints=["stratum sizes are unequal between arms"],
                prohibited_assumptions=[
                    "a within-stratum advantage transfers to the pooled comparison"
                ],
            ),
            "+0.0455 -- averaging the two within-stratum differences instead of pooling the counts",
            "The treatment is superior in both strata, so a positive pooled difference "
            "feels forced; the reversal only appears if the raw counts are pooled rather "
            "than the rates averaged.",
            "Both stratum-level comparisons and the pooled comparison computed from the "
            "raw counts; the within-stratum advantage and the pooled reversal both confirmed.",
            6,
            Attractor.HIGH,
            "Six dependent steps (four stratum rates, two pooled rates, then the "
            "difference) against the strongest attractor in the corpus: the direction of "
            "the answer contradicts every intermediate result.",
        ),
        _task(
            7,
            "law_of_total_variance",
            "probability_statistics",
            """
A coin's bias P is drawn once from the uniform distribution on the interval [0, 1].
That same coin is then flipped 10 times. Let H be the total number of heads.
""",
            "Report the variance of H.",
            AnswerSpec(
                kind="numeric",
                value=10.0,
                tolerance=_TOL_EXACT,
                justification=(
                    "Var(H) = E[Var(H|P)] + Var(E[H|P]) = E[10P(1-P)] + Var(10P) "
                    "= 10*(1/2 - 1/3) + 100*(1/12) = 5/3 + 25/3 = 10."
                ),
            ),
            _facts(
                entities={
                    "P": "RandomVariable[Probability]",
                    "H": "RandomVariable[Integer]",
                },
                declaration_kinds={"P": "parameter", "H": "observation"},
                law_families={"P": "Uniform", "H": "Binomial"},
                conditioning={"H": ["P"]},
                dependencies={"H": ["P"]},
                prohibited_assumptions=["P may be replaced by its mean"],
            ),
            "2.5 -- substituting the mean bias 0.5 and reporting the binomial variance 10*0.5*0.5",
            "Replacing a random parameter by its expectation preserves the mean of H but "
            "destroys the between-coin variance, which here is five times the within-coin "
            "variance. The substitution is invisible unless the hierarchy is made explicit.",
            "Both components computed in exact rational arithmetic with "
            "fractions.Fraction: E[Var(H|P)] = 5/3 and Var(E[H|P]) = 25/3.",
            6,
            Attractor.HIGH,
            "Six dependent steps across two levels of a hierarchy; the attractor collapses "
            "the hierarchy, which is precisely the structure a formal representation makes "
            "explicit.",
        ),
    ]


# ===========================================================================
# logic and quantifier scope -- 4
# ===========================================================================


def _logic() -> list[BenchTask]:
    return [
        _task(
            8,
            "quantifier_order_repair",
            "logic_quantifier_scope",
            """
The domain of discourse is D = {1, 2, 3}. A binary relation R on D holds for exactly
these four ordered pairs: (1,1), (2,2), (3,3) and (1,2). It holds for no other pair.
""",
            """
Report the minimum number of ordered pairs that must be added to R so that the statement
"there exists y in D such that for all x in D, R(x, y)" becomes true.
""",
            AnswerSpec(
                kind="numeric",
                value=1.0,
                tolerance=_TOL_EXACT,
                justification=(
                    "Choosing y = 2 requires (1,2), (2,2), (3,2); only (3,2) is missing, "
                    "so one addition suffices. y = 1 needs two additions and y = 3 needs "
                    "two. The minimum is 1. Note the statement is currently FALSE even "
                    "though 'for all x there exists y' is currently TRUE."
                ),
            ),
            _facts(
                entities={"R": "Relation[Integer, Integer]", "D": "Set[Integer]"},
                declaration_kinds={"R": "relation"},
                quantifier_order=["exists y", "forall x"],
            ),
            "0 -- judging the statement already true by reading it as 'for all x there exists y', which is true",
            "The relation is reflexive, so the swapped reading is satisfied by every "
            "element and returns zero. Only the exists-then-forall order exposes the gap.",
            "Exhaustive search over all three candidate witnesses y, counting missing "
            "pairs for each; both quantifier orders evaluated independently by brute force.",
            5,
            Attractor.HIGH,
            "Five dependent steps and the corpus's cleanest scope attractor: the swapped "
            "reading is true, so the wrong answer is internally consistent.",
        ),
        _task(
            9,
            "negation_prenex_prefix",
            "logic_quantifier_scope",
            """
Let phi be the statement

    for all epsilon > 0, there exists delta > 0, for all x,
        ( |x - a| < delta  implies  |f(x) - L| < epsilon )

Consider the negation of phi, written in prenex normal form, that is, with every
quantifier moved to the front and the negation driven inward as far as it will go.
""",
            """
Report the quantifier prefix of the prenex normal form of the negation of phi, as a
sequence of the tokens exists and forall separated by single spaces, in order.
""",
            AnswerSpec(
                kind="exact_string",
                value="exists forall exists",
                justification=(
                    "Negating dualises each quantifier in order: for-all/exists/for-all "
                    "becomes exists/for-all/exists. The matrix becomes "
                    "|x - a| < delta AND NOT(|f(x) - L| < epsilon); the implication "
                    "becomes a conjunction and contributes no quantifier."
                ),
            ),
            _facts(
                entities={"epsilon": "PositiveReal", "delta": "PositiveReal", "x": "Real"},
                declaration_kinds={"epsilon": "bound", "delta": "bound", "x": "bound"},
                quantifier_order=["forall epsilon", "exists delta", "forall x"],
            ),
            "forall exists forall -- reproducing the original prefix unchanged",
            "The prefix must dualise position by position; copying it across is the "
            "failure, and the embedded implication invites the separate error of negating "
            "it to an implication rather than a conjunction.",
            "Dualisation applied position by position and checked against the standard "
            "epsilon-delta discontinuity statement, whose prefix is exists/for-all/exists.",
            4,
            Attractor.MEDIUM,
            "Four dependent steps (dualise three quantifiers, then rewrite the matrix); "
            "the answer space is small but the string is not guessable.",
        ),
        _task(
            10,
            "vacuous_truth_count",
            "logic_quantifier_scope",
            """
Let S be the set of integers n satisfying 1 < n < 2. Consider these three statements.

  (i)   For all n in S, n is prime.
  (ii)  There exists n in S such that n is prime.
  (iii) For all n in S, n is not prime.
""",
            "Report how many of the three statements are true.",
            AnswerSpec(
                kind="numeric",
                value=2.0,
                tolerance=_TOL_EXACT,
                justification=(
                    "S is empty: no integer lies strictly between 1 and 2. A universal "
                    "statement over an empty domain is vacuously true, so (i) and (iii) "
                    "are both true; an existential over an empty domain is false, so (ii) "
                    "is false. Exactly two are true."
                ),
            ),
            _facts(
                entities={"S": "Set[Integer]", "n": "Integer"},
                declaration_kinds={"S": "definition", "n": "bound"},
                constraints=["S is empty"],
                prohibited_assumptions=[
                    "a universal and its apparent contrary cannot both hold"
                ],
            ),
            "1 -- refusing to let (i) and (iii) both be true on the grounds that they contradict each other",
            "Vacuous truth makes a universal and its apparent contrary hold simultaneously. "
            "The contradiction is only apparent, but resisting it is the natural reading.",
            "Emptiness of S confirmed by enumeration over the integers in [-10, 10]; the "
            "three statements evaluated under standard empty-domain semantics.",
            4,
            Attractor.HIGH,
            "Four dependent steps (establish emptiness, then evaluate three quantified "
            "statements under empty-domain semantics) with a strong consistency attractor.",
        ),
        _task(
            11,
            "negation_scope_choice",
            "logic_quantifier_scope",
            """
The domain of discourse is students. P(x) means "x passed" and Q(x) means "x cheated".
Consider the English sentence

    Not every student who passed cheated.

Five candidate formalisations are offered.

  A:  for all x ( P(x) implies not Q(x) )
  B:  not for all x ( P(x) implies Q(x) )
  C:  there exists x ( P(x) and not Q(x) )
  D:  both B and C are correct formalisations
  E:  not there exists x ( P(x) and Q(x) )
""",
            "Report the letter of the correct option.",
            AnswerSpec(
                kind="choice",
                value="D",
                options=["A", "B", "C", "D", "E"],
                justification=(
                    "B is the direct negation. Pushing the negation inward gives "
                    "exists x ( P(x) and not Q(x) ), which is C. B and C are logically "
                    "equivalent, so both are correct and D is the answer. A says no "
                    "passing student cheated, which is strictly stronger. E says no "
                    "student both passed and cheated, equivalent to A."
                ),
            ),
            _facts(
                entities={"P": "Predicate", "Q": "Predicate"},
                declaration_kinds={"P": "predicate", "Q": "predicate"},
                quantifier_order=["not", "forall x"],
            ),
            "A -- reading 'not every ... cheated' as 'every ... did not cheat', which moves the negation inside the quantifier",
            "The negation scopes over the quantifier, not over the predicate. Option A is "
            "the inside reading and is strictly stronger; recognising that B and C are "
            "equivalent requires a second step after rejecting A.",
            "Equivalence of B and C checked by the standard De Morgan dualisation of a "
            "universally quantified implication.",
            4,
            Attractor.MEDIUM,
            "Four dependent steps; the 0.20 chance floor applies but does not bind, since "
            "the rubric's prediction stays above it.",
        ),
    ]


# ===========================================================================
# dimensions and physics -- 3
# ===========================================================================


def _dimensions() -> list[BenchTask]:
    return [
        _task(
            12,
            "kinematic_viscosity_dimension",
            "dimensions_physics",
            """
Dynamic viscosity mu has dimension Mass / (Length * Time). Mass density rho has
dimension Mass / Length^3. Kinematic viscosity nu is defined as nu = mu / rho.
""",
            "Report the dimension of nu.",
            AnswerSpec(
                kind="dimension",
                value="Length^2 / Time",
                justification=(
                    "nu = mu / rho = [M / (L*T)] * [L^3 / M] = L^2 / T. The mass "
                    "dimension cancels exactly."
                ),
            ),
            _facts(
                entities={"mu": "Real", "rho": "Real", "nu": "Real"},
                declaration_kinds={"mu": "parameter", "rho": "parameter", "nu": "derived"},
                dimensions={
                    "mu": "Mass / Length / Time",
                    "rho": "Mass / Length^3",
                    "nu": "Length^2 / Time",
                },
                dependencies={"nu": ["mu", "rho"]},
            ),
            "Length / Time -- reporting a velocity, on the strength of the name 'viscosity' sounding like a rate of flow",
            "Dividing by a density inverts a Length^3, which is the step that turns "
            "L^-1 into L^2. Losing one power of length yields the velocity dimension, "
            "which looks physically plausible for a flow quantity.",
            "Exponent arithmetic on each base dimension carried out separately and "
            "confirmed against the parser used to score the answer.",
            4,
            Attractor.MEDIUM,
            "Four dependent steps of exponent arithmetic with an attractor that is "
            "dimensionally adjacent, so it survives a rough plausibility check.",
        ),
        _task(
            13,
            "permittivity_from_dimensionless",
            "dimensions_physics",
            """
The fine-structure constant alpha = e^2 / (4 * pi * epsilon_0 * hbar * c) is
dimensionless. Elementary charge e has dimension Current * Time. Reduced Planck constant
hbar has dimension Mass * Length^2 / Time. The speed of light c is a velocity. The factor
4 * pi is a pure number.
""",
            "Report the dimension of epsilon_0.",
            AnswerSpec(
                kind="dimension",
                value="Current^2 * Time^4 / Mass / Length^3",
                justification=(
                    "Dimensionlessness forces [epsilon_0] = [e^2] / ([hbar][c]) = "
                    "(I*T)^2 / ((M*L^2/T)*(L/T)) = I^2*T^2 / (M*L^3/T^2) "
                    "= I^2 * T^4 / (M * L^3), which is the SI dimension of the vacuum "
                    "permittivity."
                ),
            ),
            _facts(
                entities={
                    "e": "Real",
                    "hbar": "Real",
                    "c": "Real",
                    "epsilon_0": "Real",
                    "alpha": "Real",
                },
                declaration_kinds={"epsilon_0": "derived", "alpha": "derived"},
                dimensions={
                    "e": "Current * Time",
                    "hbar": "Mass * Length^2 / Time",
                    "c": "Length / Time",
                    "alpha": "1",
                },
                constraints=["alpha is dimensionless"],
            ),
            "Current * Time^2 / Mass / Length^3 -- failing to square the charge dimension",
            "The constraint has to be inverted rather than evaluated: the target appears in "
            "the denominator of a quantity asserted to be dimensionless. Missing the square "
            "on e is the single commonest slip, and the two time exponents compound it.",
            "Exponent arithmetic performed separately per base dimension and checked "
            "against the known SI dimension of vacuum permittivity.",
            7,
            Attractor.MEDIUM,
            "Seven dependent steps: five exponent reductions plus the inversion of the "
            "dimensionless constraint, which is the step that has no analogue in a "
            "forward dimensional check.",
        ),
        _task(
            14,
            "pendulum_consistency_count",
            "dimensions_physics",
            """
Three students each propose a formula for the period T of a simple pendulum, where L is a
length, g is an acceleration, and theta is an angle in radians and therefore dimensionless.

  (1)  T = 2*pi*sqrt(L/g) * (1 + theta^2/16)
  (2)  T = 2*pi*sqrt(g/L)
  (3)  T = 2*pi*sqrt(L*g)
""",
            """
Report how many of the three proposals are dimensionally consistent with T being a time.
""",
            AnswerSpec(
                kind="numeric",
                value=1.0,
                tolerance=_TOL_EXACT,
                justification=(
                    "sqrt(L/g) = sqrt(L / (L/T^2)) = sqrt(T^2) = T, and the bracket is "
                    "dimensionless, so (1) is consistent. sqrt(g/L) has dimension 1/Time "
                    "and sqrt(L*g) has dimension Length/Time, so (2) and (3) are not. "
                    "Exactly one is consistent."
                ),
            ),
            _facts(
                entities={"L": "Real", "g": "Real", "theta": "Real", "T": "Real"},
                declaration_kinds={"T": "derived"},
                dimensions={
                    "L": "Length",
                    "g": "Length / Time^2",
                    "theta": "1",
                    "T": "Time",
                },
            ),
            "2 -- accepting (2) as well, on the grounds that the ratio is merely inverted and a square root forgives it",
            "Inverting the ratio inside the square root produces a frequency, not a "
            "period. The two are so often used interchangeably in prose that the "
            "inversion reads as harmless.",
            "Each proposal reduced to base dimensions independently; only proposal (1) "
            "reduces to Time.",
            5,
            Attractor.MEDIUM,
            "Five dependent steps (three separate reductions plus the dimensionless-bracket "
            "judgement and the count).",
        ),
    ]


# ===========================================================================
# linear algebra -- 3
# ===========================================================================


def _linear_algebra() -> list[BenchTask]:
    return [
        _task(
            15,
            "sylvester_rank_range",
            "linear_algebra",
            """
A is a 4-by-6 real matrix of rank 3. B is a 6-by-5 real matrix of rank 4. The product
A*B is therefore a 4-by-5 matrix.
""",
            """
Let M be the largest rank that A*B can have and m the smallest rank that A*B can have,
over all matrices A and B meeting these conditions. Report M - m.
""",
            AnswerSpec(
                kind="numeric",
                value=2.0,
                tolerance=_TOL_EXACT,
                justification=(
                    "rank(AB) <= min(rank A, rank B) = 3, and this is attained, so M = 3. "
                    "Sylvester's rank inequality gives rank(AB) >= rank A + rank B - n "
                    "where n = 6 is the shared inner dimension, so rank(AB) >= 1, and "
                    "this is attained, so m = 1. M - m = 2."
                ),
            ),
            _facts(
                entities={"A": "Matrix", "B": "Matrix"},
                declaration_kinds={"A": "parameter", "B": "parameter"},
                constraints=["rank(A) = 3", "rank(B) = 4", "inner dimension = 6"],
            ),
            "3 -- taking the minimum possible rank to be 0, which would make the difference 3",
            "The upper bound is the familiar one and is usually correct; the lower bound "
            "requires Sylvester's inequality, and without it zero looks attainable because "
            "nothing obviously forbids the product from vanishing.",
            "Both bounds checked against the standard statements of the rank of a product "
            "and of Sylvester's rank inequality with inner dimension 6.",
            5,
            Attractor.HIGH,
            "Five dependent steps; the lower bound is the discriminating one and the "
            "attractor (rank zero) is what an argument from the upper bound alone yields.",
        ),
        _task(
            16,
            "defective_matrix_trace",
            "linear_algebra",
            """
Let A be the 2-by-2 real matrix with first row (3, 1) and second row (0, 3). Let k be the
number of linearly independent eigenvectors of A.
""",
            "Report the trace of A^5 divided by k.",
            AnswerSpec(
                kind="numeric",
                value=486.0,
                tolerance=_TOL_EXACT,
                justification=(
                    "A is a Jordan block with the single eigenvalue 3, whose eigenspace is "
                    "spanned by (1,0) alone, so k = 1 rather than 2. "
                    "A^5 = [[3^5, 5*3^4], [0, 3^5]], so trace(A^5) = 486 and the quotient "
                    "is 486/1 = 486."
                ),
            ),
            _facts(
                entities={"A": "Matrix", "k": "Integer"},
                declaration_kinds={"A": "parameter", "k": "derived"},
                constraints=["A is upper triangular", "A is not diagonalisable"],
            ),
            "243 -- taking k = 2 because the characteristic polynomial has a double root, halving the trace",
            "Algebraic multiplicity 2 does not give geometric multiplicity 2. The matrix "
            "is defective, and assuming one eigenvector per root is the standard error; it "
            "divides the correct trace by exactly two.",
            "Trace of the fifth power computed from the closed form for a Jordan block; "
            "the eigenspace dimension confirmed by solving (A - 3I)v = 0.",
            5,
            Attractor.HIGH,
            "Five dependent steps combining a defectiveness judgement with a matrix power; "
            "the attractor gives a clean answer that is exactly half the correct one.",
        ),
        _task(
            17,
            "determinant_scalar_similarity",
            "linear_algebra",
            """
A and B are 3-by-3 real matrices. A is invertible. det(A) = 2 and det(B) = -3. B^T
denotes the transpose of B.
""",
            "Report det( 2 * A^(-1) * B^T * A ), where the leading 2 multiplies every entry of the product.",
            AnswerSpec(
                kind="numeric",
                value=-24.0,
                tolerance=_TOL_EXACT,
                justification=(
                    "det(A^-1 B^T A) = det(A)^-1 * det(B^T) * det(A) = det(B) = -3, since "
                    "transposition preserves the determinant and the similarity cancels. "
                    "Scaling a 3-by-3 matrix by 2 multiplies its determinant by 2^3 = 8. "
                    "Hence 8 * (-3) = -24."
                ),
            ),
            _facts(
                entities={"A": "Matrix", "B": "Matrix"},
                declaration_kinds={"A": "parameter", "B": "parameter"},
                constraints=["det(A) = 2", "det(B) = -3", "dimension = 3"],
            ),
            "-6 -- treating the scalar 2 as multiplying the determinant once instead of raising it to the third power",
            "Two independent facts must both land: similarity leaves the determinant "
            "unchanged, and a scalar multiple raises it to the power of the dimension. "
            "The second is the one that is dropped, and det(A) = 2 is a decoy that invites "
            "a spurious cancellation.",
            "Determinant identities applied step by step; the scalar exponent checked "
            "against the 3-by-3 dimension.",
            5,
            Attractor.HIGH,
            "Five dependent steps with a decoy value; the attractor arises from applying "
            "the scalar rule as though the matrix were 1-by-1.",
        ),
    ]


# ===========================================================================
# calculus -- 3
# ===========================================================================


def _calculus() -> list[BenchTask]:
    return [
        _task(
            18,
            "frullani_integral",
            "calculus",
            """
Consider the improper integral

    integral from 0 to infinity of ( exp(-2*x) - exp(-5*x) ) / x  dx

Each term individually produces a divergent integral near x = 0, but their difference
does not.
""",
            "Report the value of the integral.",
            AnswerSpec(
                kind="numeric",
                value=0.9162907318741551,
                tolerance=_TOL_INEXACT,
                justification=(
                    "By Frullani's integral, the integral of "
                    "(f(a x) - f(b x))/x from 0 to infinity equals "
                    "(f(0) - f(infinity)) * ln(b/a) for suitable f. With "
                    "f(t) = exp(-t), a = 2 and b = 5 this gives ln(5/2) = 0.9162907."
                ),
            ),
            _facts(
                entities={"x": "PositiveReal"},
                declaration_kinds={"x": "bound"},
                objective="evaluate a convergent difference of two divergent integrals",
            ),
            "-0.9163 -- returning ln(2/5) with the ratio inverted",
            "The ratio's orientation is set by which exponent belongs to the subtracted "
            "term; inverting it flips the sign of an answer that must be positive, since "
            "the integrand is positive throughout.",
            "Value cross-checked against the closed form ln(5/2) evaluated to 16 "
            "significant figures.",
            5,
            Attractor.MEDIUM,
            "Five dependent steps (establish convergence, identify the Frullani form, fix "
            "the orientation of the ratio, evaluate) with an attractor that inverts the sign.",
        ),
        _task(
            19,
            "implicit_second_derivative",
            "calculus",
            """
The curve C is defined implicitly by x^2 * y + y^3 = 10. The point (3, 1) lies on C,
since 9*1 + 1 = 10.
""",
            "Report the value of the second derivative d^2y/dx^2 at the point (3, 1).",
            AnswerSpec(
                kind="numeric",
                value=0.20833333333333334,
                tolerance=_TOL_INEXACT,
                justification=(
                    "Implicit differentiation gives y' = -2xy / (x^2 + 3y^2), so at (3,1) "
                    "y' = -6/12 = -1/2. Differentiating the quotient with N = -2xy and "
                    "D = x^2 + 3y^2 gives N' = -2y - 2x y' = 1 and D' = 2x + 6y y' = 3, "
                    "so y'' = (N'D - N D')/D^2 = (12 + 18)/144 = 5/24."
                ),
            ),
            _facts(
                entities={"x": "Real", "y": "Real"},
                declaration_kinds={"x": "unknown", "y": "unknown"},
                dependencies={"y": ["x"]},
                constraints=["x^2 * y + y^3 = 10"],
            ),
            "-0.4167 -- differentiating the quotient without re-substituting y', so the sign and magnitude are both wrong",
            "The second differentiation must treat y as a function of x in three separate "
            "places and must feed y' back in before evaluating. Omitting any one of them "
            "produces a plausible negative value, matching the sign of y'.",
            "Confirmed by a central finite-difference second derivative on the curve, "
            "with y solved implicitly by Newton's method at each of three abscissae; the "
            "numerical result matched 5/24 to 8 decimal places.",
            7,
            Attractor.MEDIUM,
            "Seven dependent steps, the longest chain in the corpus, with a re-substitution "
            "that is easy to omit and produces an answer of the wrong sign.",
        ),
        _task(
            20,
            "series_order_limit",
            "calculus",
            """
Consider the limit as x approaches 0 of ( sin(x) - x*cos(x) ) / x^3. Both the numerator
and the denominator approach 0.
""",
            "Report the value of the limit.",
            AnswerSpec(
                kind="numeric",
                value=0.3333333333333333,
                tolerance=_TOL_INEXACT,
                justification=(
                    "sin x = x - x^3/6 + O(x^5) and x cos x = x - x^3/2 + O(x^5), so the "
                    "numerator is x^3/3 + O(x^5) and the limit is 1/3."
                ),
            ),
            _facts(
                entities={"x": "Real"},
                declaration_kinds={"x": "bound"},
                objective="evaluate an indeterminate 0/0 limit of third order",
            ),
            "0.1667 -- expanding sin x to third order but leaving cos x at leading order, which drops the -x^3/2 term",
            "Both terms contribute at third order. Truncating either expansion one order "
            "too early loses exactly one of the two contributions and yields 1/6 or 1/2, "
            "both of which look like credible closed forms.",
            "Confirmed numerically at x = 1e-4, which agreed with 1/3 to 8 significant "
            "figures.",
            5,
            Attractor.MEDIUM,
            "Five dependent steps requiring both expansions to be carried to matching "
            "order; the attractor is an order-truncation rather than an arithmetic slip.",
        ),
    ]


# ===========================================================================
# epistemic reasoning -- 4
# ===========================================================================


def _epistemic() -> list[BenchTask]:
    return [
        _task(
            21,
            "two_detector_posterior",
            "epistemic_reasoning",
            """
A signal is present with prior probability 0.1. Two detectors observe the same channel.
Each detector fires with probability 0.9 when the signal is present and with probability
0.2 when it is absent. Conditional on whether the signal is present, the two detectors
are independent. Both detectors fire.
""",
            "Report the posterior probability that the signal is present.",
            AnswerSpec(
                kind="numeric",
                value=0.6923076923076923,
                tolerance=_TOL_INEXACT,
                justification=(
                    "P(both | signal) = 0.81 and P(both | no signal) = 0.04. "
                    "Posterior = (0.1*0.81) / (0.1*0.81 + 0.9*0.04) "
                    "= 0.081 / 0.117 = 9/13 = 0.692308."
                ),
            ),
            _facts(
                entities={
                    "signal": "RandomVariable[Boolean]",
                    "d1": "RandomVariable[Boolean]",
                    "d2": "RandomVariable[Boolean]",
                },
                declaration_kinds={"signal": "latent", "d1": "observation", "d2": "observation"},
                conditioning={"d1": ["signal"], "d2": ["signal"]},
                dependencies={"d1": ["signal"], "d2": ["signal"]},
                prohibited_assumptions=["the detectors are unconditionally independent"],
            ),
            "0.9 -- reporting the detector's hit rate as though it were the posterior, the standard base-rate error",
            "The low prior survives two confirmations because the false-alarm rate is not "
            "negligible; the posterior stays well under the 0.9 reliability figure that the "
            "problem foregrounds.",
            "Bayes' rule applied with both likelihoods squared under conditional "
            "independence; result equals the exact fraction 9/13.",
            5,
            Attractor.HIGH,
            "Five dependent steps; the attractor is the base-rate neglect that this problem "
            "shape is specifically built to elicit.",
        ),
        _task(
            22,
            "correlated_testimony",
            "epistemic_reasoning",
            """
The proposition p is either true or false, with prior probability 0.5. Three sources
report.

  S1 asserts p. S1 is right with probability 0.7 whatever the truth of p.
  S2 asserts not-p. S2 is right with probability 0.6 whatever the truth of p.
  S3 asserts p. S3's report is a verbatim copy of S1's report and carries no
     information that S1 does not already carry.

S1 and S2 are conditionally independent given the truth of p.
""",
            "Report the posterior probability of p given all three reports.",
            AnswerSpec(
                kind="numeric",
                value=0.6086956521739131,
                tolerance=_TOL_INEXACT,
                justification=(
                    "S3 is a copy and contributes a likelihood ratio of 1. S1 contributes "
                    "0.7/0.3 = 7/3 and S2, asserting not-p, contributes 0.4/0.6 = 2/3. "
                    "Posterior odds = 1 * (7/3) * (2/3) = 14/9, so the posterior "
                    "probability is 14/23 = 0.608696."
                ),
            ),
            _facts(
                entities={"p": "RandomVariable[Boolean]"},
                declaration_kinds={"p": "latent"},
                conditioning={"S1": ["p"], "S2": ["p"]},
                dependencies={"S3": ["S1"]},
                prohibited_assumptions=["S3 is an independent source"],
            ),
            "0.7778 -- counting S3 as a third independent report, which multiplies in a spurious extra 7/3",
            "A duplicated report looks like corroboration. Counting it once more raises the "
            "posterior by roughly 17 points, and nothing in the arithmetic signals the "
            "double count unless the dependency is represented explicitly.",
            "Likelihood ratios composed in exact rational arithmetic; the posterior equals "
            "14/23.",
            6,
            Attractor.HIGH,
            "Six dependent steps across three sources, one of which must be assigned a "
            "likelihood ratio of exactly 1 on structural rather than numerical grounds.",
        ),
        _task(
            23,
            "knowledge_closure_choice",
            "epistemic_reasoning",
            """
Agent A knows that p implies q. Agent A believes p. Agent A does not know p: A's belief
in p is true but is not knowledge, because it rests on an unreliable source. Consider
whether it follows that A knows q.

  A:  Yes, knowledge is closed under known implication.
  B:  No. Knowing an implication together with merely believing its antecedent yields at
      most belief in q, never knowledge of q.
  C:  Yes, by modus ponens applied inside A's epistemic state.
  D:  No, but only because A might fail to perform the inference.
  E:  Yes, provided A is logically omniscient.
""",
            "Report the letter of the correct option.",
            AnswerSpec(
                kind="choice",
                value="B",
                options=["A", "B", "C", "D", "E"],
                justification=(
                    "Closure under known implication requires the antecedent to be KNOWN, "
                    "not merely believed. A knows p implies q and only believes p, so the "
                    "conclusion inherits the weaker status: A at most believes q. D names "
                    "a real but different obstacle, the failure to perform the inference, "
                    "which is not why the argument fails here; the argument fails on the "
                    "epistemic status of the premise, not on A's diligence."
                ),
            ),
            _facts(
                entities={"p": "Proposition", "q": "Proposition"},
                declaration_kinds={"p": "proposition", "q": "proposition"},
                prohibited_assumptions=["belief may substitute for knowledge in closure"],
            ),
            "C -- applying modus ponens without checking that both premises carry the same epistemic status",
            "The inference is valid as logic and invalid as epistemology. Distinguishing "
            "the two requires tracking the epistemic status of each premise separately, "
            "which the surface form of the argument does not display.",
            "Checked against the standard formulation of closure under known implication, "
            "which requires knowledge of the antecedent.",
            4,
            Attractor.MEDIUM,
            "Four dependent steps; option D is a near-miss distractor that is true of a "
            "different scenario, so eliminating it takes a further step.",
        ),
        _task(
            24,
            "licensed_conclusion_choice",
            "epistemic_reasoning",
            """
A dataset of 500 records is examined. In every record for which X = 1, it is also
observed that Y = 1. The 500 records were collected from a single hospital over one
month. Nothing else is known about how they were sampled.

  A:  X implies Y holds as a logical implication throughout the domain.
  B:  X causes Y.
  C:  P(Y = 1 | X = 1) = 1 in this sample.
  D:  X and Y are positively correlated in the population from which the sample is drawn.
  E:  Both A and C are licensed.
""",
            "Report the letter of the single conclusion that the evidence licenses.",
            AnswerSpec(
                kind="choice",
                value="C",
                options=["A", "B", "C", "D", "E"],
                justification=(
                    "Only C restates the observation. A generalises a sample regularity "
                    "into a domain-wide logical implication; B adds a causal claim no "
                    "observational regularity supports; D generalises to a population from "
                    "an unspecified and plainly non-random sampling frame; E inherits A's "
                    "defect. The distinction between an observed conditional frequency, a "
                    "logical implication and a causal claim is exactly the conflation the "
                    "project's type system refuses to permit."
                ),
            ),
            _facts(
                entities={"X": "RandomVariable[Boolean]", "Y": "RandomVariable[Boolean]"},
                declaration_kinds={"X": "observation", "Y": "observation"},
                prohibited_assumptions=[
                    "a sample regularity is a logical implication",
                    "a regularity is a causal relation",
                    "a convenience sample licenses a population claim",
                ],
            ),
            "E -- accepting the sample regularity as a logical implication alongside the correct conditional frequency",
            "A perfect in-sample regularity across 500 records reads as a law. Option E is "
            "the trap for a reasoner who is careful enough to accept C but not careful "
            "enough to reject A.",
            "Each option classified against what an observational sample of unspecified "
            "provenance can support; only the in-sample conditional frequency survives.",
            5,
            Attractor.HIGH,
            "Five dependent steps, one per option; the attractor E is strictly more "
            "attractive than the answer because it appears to concede more.",
        ),
    ]


def build_tasks() -> list[BenchTask]:
    """The 24 tasks, in fixed order. Deterministic: no randomness, no I/O, no model."""
    tasks = (
        _algebra()
        + _probability()
        + _logic()
        + _dimensions()
        + _linear_algebra()
        + _calculus()
        + _epistemic()
    )
    if len(tasks) != TASK_COUNT:
        raise AssertionError(
            f"the pre-registered tranche is {TASK_COUNT} tasks; {len(tasks)} were built. "
            "Changing the count after authoring changes the decision rule, so this is a "
            "hard failure rather than a warning."
        )
    return tasks


def by_domain(tasks: list[BenchTask] | None = None) -> dict[str, list[BenchTask]]:
    out: dict[str, list[BenchTask]] = {d: [] for d in DOMAINS}
    for t in tasks if tasks is not None else build_tasks():
        out[t.domain].append(t)
    return out
