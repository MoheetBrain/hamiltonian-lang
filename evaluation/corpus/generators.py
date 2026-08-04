"""Problem generators for HML-EVAL-001.

Every problem is generated from a seeded template, so the exact numeric instance in the
benchmark has essentially no chance of appearing verbatim in any pretraining corpus while
the *structure* remains the thing under test. That is the leakage control required by §5.

Ground truth is **computed**, never typed by hand, wherever computation is possible. A
hand-typed answer is a place for a silent error to live.

Categories and counts (§5):
    probability      25
    binding          25
    quantifier       25
    dimensional      25
    algebraic        20
                    ---
                    120
"""

from __future__ import annotations

import math
import random

from .cso import AnswerSpec, CanonicalSemanticObject, SemanticFacts

__all__ = ["build_all", "build_demos", "CATEGORY_TARGETS"]

CATEGORY_TARGETS = {
    "probability": 25,
    "binding": 25,
    "quantifier": 25,
    "dimensional": 25,
    "algebraic": 20,
}

_NAMES = ["alpha", "beta_", "gamma_", "delta_", "kappa", "lambda_", "omega", "psi",
          "rho", "tau", "phi", "chi", "eta", "zeta", "iota", "nu_"]
_UNITS = ["metre", "second", "kilogram", "kelvin", "ampere", "mole", "candela"]


def _rng(pid: str) -> random.Random:
    return random.Random(f"hml-eval-001::{pid}")


# ---------------------------------------------------------------------------
# Probability and statistics
# ---------------------------------------------------------------------------


def _prob_scale_vs_variance(i: int) -> CanonicalSemanticObject:
    pid = f"p{i:02d}_scale_vs_variance"
    r = _rng(pid)
    var = r.choice([4, 9, 16, 25, 36, 49, 64, 81, 100, 121, 144])
    mean = r.randint(-40, 40)
    sd = math.sqrt(var)
    return CanonicalSemanticObject(
        id=pid, domain="probability", difficulty="easy",
        prose=(
            f"A measurement W is normally distributed. Its mean is {mean} and its "
            f"variance is {var}."
        ),
        question=(
            "What is the numerical value of the scale parameter of this distribution, "
            "where the scale parameter is the standard deviation?"
        ),
        answer=AnswerSpec("numeric", sd, justification=f"sd = sqrt({var}) = {sd}"),
        semantics=SemanticFacts(
            entities={"W": "RandomVariable[Real]", "mu": "Real", "sigma": "PositiveReal"},
            declaration_kinds={"W": "rv", "mu": "const", "sigma": "const"},
            laws={"W": {"location": "mu", "scale": "sigma"}},
            law_families={"W": "Normal"},
            prohibited_assumptions=["that the given variance is itself the scale"],
        ),
        distractors=[f"answering {var}, the variance, as if it were the scale"],
        reference_hml=(
            f"module ScaleVsVariance\n\nrv W : RandomVariable[Real]\n"
            f"const mu : Real = {mean}\nconst sigma : PositiveReal = {sd}\n\n"
            f"law W ~ Normal(location := mu, scale := sigma)\n"
        ),
        generator="_prob_scale_vs_variance",
    )


def _prob_exponential_rate(i: int) -> CanonicalSemanticObject:
    pid = f"p{i:02d}_exponential_rate"
    r = _rng(pid)
    mean = r.choice([2, 4, 5, 8, 10, 16, 20, 25, 40, 50])
    rate = 1.0 / mean
    return CanonicalSemanticObject(
        id=pid, domain="probability", difficulty="easy",
        prose=(
            f"The time T between successive events follows an exponential distribution. "
            f"The mean time between events is {mean} hours."
        ),
        question=(
            "What is the numerical value of the rate parameter of this distribution, "
            "in events per hour?"
        ),
        answer=AnswerSpec("numeric", rate, tolerance=1e-6,
                          justification=f"rate = 1/mean = 1/{mean}"),
        semantics=SemanticFacts(
            entities={"T": "RandomVariable[PositiveReal]", "lam": "PositiveReal"},
            declaration_kinds={"T": "rv", "lam": "const"},
            laws={"T": {"rate": "lam"}}, law_families={"T": "Exponential"},
            prohibited_assumptions=["that the given mean is the rate"],
        ),
        distractors=[f"answering {mean}, the mean, as if it were the rate"],
        reference_hml=(
            f"module ExponentialRate\n\nrv T : RandomVariable[PositiveReal]\n"
            f"const lam : PositiveReal = {rate}\n\nlaw T ~ Exponential(rate := lam)\n"
        ),
        generator="_prob_exponential_rate",
    )


def _prob_beta_binomial_posterior(i: int) -> CanonicalSemanticObject:
    pid = f"p{i:02d}_beta_binomial_posterior"
    r = _rng(pid)
    a, b = r.choice([(1, 1), (2, 2), (1, 3), (3, 1), (2, 5), (5, 2)])
    n = r.choice([10, 12, 16, 20, 24, 30, 40])
    k = r.randint(1, n - 1)
    post_mean = (a + k) / (a + b + n)
    return CanonicalSemanticObject(
        id=pid, domain="probability", difficulty="medium",
        prose=(
            f"A coin has an unknown probability theta of landing heads. Before observing "
            f"any data, theta is given a Beta prior with first shape parameter {a} and "
            f"second shape parameter {b}. The coin is then tossed {n} times, "
            f"independently, and {k} heads are observed."
        ),
        question="What is the numerical value of the posterior mean of theta?",
        answer=AnswerSpec(
            "numeric", post_mean, tolerance=1e-6,
            justification=f"({a}+{k})/({a}+{b}+{n}) = {post_mean}",
        ),
        semantics=SemanticFacts(
            entities={"theta": "Probability", "trials": "Natural", "successes": "Natural"},
            declaration_kinds={"theta": "param", "trials": "obs", "successes": "obs"},
            laws={"theta": {"alpha": str(a), "beta": str(b)},
                  "successes": {"trials": "trials", "prob": "theta"}},
            law_families={"theta": "Beta", "successes": "Binomial"},
            conditioning={"successes": ["theta"]},
            prohibited_assumptions=["that the prior is uniform when it is not"],
        ),
        distractors=[f"answering the sample proportion {k}/{n} and ignoring the prior"],
        reference_hml=(
            f"module BetaBinomial\n\nparam theta : Probability\n"
            f"prior theta ~ Beta(alpha := {a}, beta := {b})\n\n"
            f"obs trials : Natural = {n}\nobs successes : Natural = {k}\n\n"
            f"likelihood successes | theta ~ Binomial(trials := trials, prob := theta)\n\n"
            f"infer posterior theta\n"
        ),
        generator="_prob_beta_binomial_posterior",
    )


def _prob_role_map(i: int) -> CanonicalSemanticObject:
    pid = f"p{i:02d}_role_map"
    r = _rng(pid)
    loc, scl = r.sample(_NAMES, 2)
    return CanonicalSemanticObject(
        id=pid, domain="probability", difficulty="medium",
        prose=(
            f"A quantity Y is normally distributed. Its centre is written {loc} and the "
            f"spread, expressed as a standard deviation, is written {scl}."
        ),
        question=(
            "Using the role names 'location' and 'scale', state which symbol fills each "
            "role."
        ),
        answer=AnswerSpec(
            "role_map", {"location": loc, "scale": scl},
            justification="the centre is the location; a standard deviation is the scale",
        ),
        semantics=SemanticFacts(
            entities={"Y": "RandomVariable[Real]", loc: "Real", scl: "PositiveReal"},
            declaration_kinds={"Y": "rv", loc: "param", scl: "param"},
            laws={"Y": {"location": loc, "scale": scl}}, law_families={"Y": "Normal"},
        ),
        distractors=["swapping location and scale"],
        reference_hml=(
            f"module RoleMap\n\nrv Y : RandomVariable[Real]\nparam {loc} : Real\n"
            f"param {scl} : PositiveReal\n\n"
            f"law Y ~ Normal(location := {loc}, scale := {scl})\n"
        ),
        generator="_prob_role_map",
    )


def _prob_rv_vs_distribution(i: int) -> CanonicalSemanticObject:
    pid = f"p{i:02d}_rv_vs_distribution"
    r = _rng(pid)
    fam, param_desc, val = r.choice([
        ("Poisson", "rate", r.randint(2, 9)),
        ("Binomial", "number of trials", r.randint(5, 30)),
    ])
    return CanonicalSemanticObject(
        id=pid, domain="probability", difficulty="medium",
        prose=(
            f"Let N be a random variable whose probability law is a {fam} distribution "
            f"with {param_desc} equal to {val}. Let L denote that probability law itself."
        ),
        question=(
            "Is the expression L + 1 a well-defined real number? Answer TRUE or FALSE."
        ),
        answer=AnswerSpec(
            "boolean", False,
            justification="L is a probability law, not a value; adding 1 to a law is "
                          "undefined. Only N, or a summary of N, is numeric.",
        ),
        semantics=SemanticFacts(
            entities={"N": "RandomVariable[Natural]", "L": "Distribution[Natural]"},
            declaration_kinds={"N": "rv", "L": "var"},
            prohibited_assumptions=["that a distribution can be treated as a value"],
        ),
        distractors=["treating the law as if it were a sampled value"],
        reference_hml=(
            "module LawIsNotAValue\n\nrv N : RandomVariable[Natural]\n"
            "var L : Distribution[Natural]\n"
        ),
        generator="_prob_rv_vs_distribution",
    )


def _prob_binomial_moments(i: int) -> CanonicalSemanticObject:
    pid = f"p{i:02d}_binomial_moments"
    r = _rng(pid)
    n = r.choice([12, 15, 18, 20, 24, 28, 32, 36, 44, 50])
    p = r.choice([0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.6, 0.75, 0.8])
    want_var = r.random() < 0.5
    val = n * p * (1 - p) if want_var else n * p
    what = "variance" if want_var else "expected value"
    return CanonicalSemanticObject(
        id=pid, domain="probability", difficulty="easy",
        prose=(
            f"A trial is repeated {n} times independently. Each repetition succeeds with "
            f"probability {p}. Let S be the total number of successes."
        ),
        question=f"What is the numerical {what} of S?",
        answer=AnswerSpec("numeric", val, tolerance=1e-6,
                          justification=f"{'n p (1-p)' if want_var else 'n p'} = {val}"),
        semantics=SemanticFacts(
            entities={"S": "RandomVariable[Natural]", "trials": "Natural",
                      "prob": "Probability"},
            declaration_kinds={"S": "rv", "trials": "const", "prob": "const"},
            laws={"S": {"trials": "trials", "prob": "prob"}},
            law_families={"S": "Binomial"},
        ),
        distractors=["confusing the variance n p (1-p) with the mean n p"],
        reference_hml=(
            f"module BinomialMoments\n\nrv S : RandomVariable[Natural]\n"
            f"const trials : Natural = {n}\nconst prob : Probability = {p}\n\n"
            f"law S ~ Binomial(trials := trials, prob := prob)\n\n"
            f"infer {'variance' if want_var else 'expectation'} S\n"
        ),
        generator="_prob_binomial_moments",
    )


def _prob_conditional_independence(i: int) -> CanonicalSemanticObject:
    pid = f"p{i:02d}_conditional_independence"
    return CanonicalSemanticObject(
        id=pid, domain="probability", difficulty="hard",
        prose=(
            "Two sensors A and B each measure the same underlying temperature Z, and "
            "their measurement errors are independent of one another. Nothing else "
            "influences either reading."
        ),
        question=(
            "Are A and B unconditionally independent of each other? "
            "Answer TRUE or FALSE."
        ),
        answer=AnswerSpec(
            "boolean", False,
            justification="A and B are conditionally independent GIVEN Z, but "
                          "marginally dependent, because both carry information about Z.",
        ),
        semantics=SemanticFacts(
            entities={"Z": "Real", "A": "RandomVariable[Real]",
                      "B": "RandomVariable[Real]"},
            declaration_kinds={"Z": "param", "A": "rv", "B": "rv"},
            conditioning={"A": ["Z"], "B": ["Z"]},
            prohibited_assumptions=[
                "that conditional independence implies marginal independence"
            ],
        ),
        distractors=["reading 'errors are independent' as 'A and B are independent'"],
        reference_hml=(
            "module SensorPair\n\n# Z is the latent temperature. It is declared as a\n"
            "# param, not an rv: v0 has no subtyping path from RandomVariable[Real] to\n"
            "# Real, so a random variable cannot fill a `location` role. See the\n"
            "# expressiveness note in docs/evaluation/PRE_EVALUATION_AUDIT.md.\n"
            "param Z : Real\n"
            "rv A : RandomVariable[Real]\nrv B : RandomVariable[Real]\n"
            "param s : PositiveReal\n\n"
            "law A | Z ~ Normal(location := Z, scale := s)\n"
            "law B | Z ~ Normal(location := Z, scale := s)\n"
        ),
        generator="_prob_conditional_independence",
    )


def _prob_param_vs_observation(i: int) -> CanonicalSemanticObject:
    pid = f"p{i:02d}_param_vs_observation"
    r = _rng(pid)
    n = r.choice([18, 24, 30, 36, 42])
    k = r.randint(2, n - 2)
    return CanonicalSemanticObject(
        id=pid, domain="probability", difficulty="medium",
        prose=(
            f"In a study, {n} seeds were planted and {k} germinated. The germination "
            f"probability p is not known and is to be estimated from this data."
        ),
        question=(
            "Which of these is the observed quantity and which is the unknown? "
            "Answer with exactly one of: SEEDS_OBSERVED_P_UNKNOWN or "
            "P_OBSERVED_SEEDS_UNKNOWN."
        ),
        answer=AnswerSpec(
            "choice", "SEEDS_OBSERVED_P_UNKNOWN",
            options=["SEEDS_OBSERVED_P_UNKNOWN", "P_OBSERVED_SEEDS_UNKNOWN"],
            justification="counts were observed; the probability is the parameter",
        ),
        semantics=SemanticFacts(
            entities={"p": "Probability", "planted": "Natural", "germinated": "Natural"},
            declaration_kinds={"p": "param", "planted": "obs", "germinated": "obs"},
            laws={"germinated": {"trials": "planted", "prob": "p"}},
            law_families={"germinated": "Binomial"},
            conditioning={"germinated": ["p"]},
        ),
        distractors=["treating the estimate of p as if it were data"],
        reference_hml=(
            f"module Germination\n\nparam p : Probability\n"
            f"obs planted : Natural = {n}\nobs germinated : Natural = {k}\n\n"
            f"likelihood germinated | p ~ Binomial(trials := planted, prob := p)\n\n"
            f"# The prose states no prior, so the query is an MLE. Encoding a posterior\n"
            f"# here would make the encoding say more than the problem does.\n"
            f"infer mle p\n"
        ),
        generator="_prob_param_vs_observation",
    )


# ---------------------------------------------------------------------------
# Variable binding and index tracking
# ---------------------------------------------------------------------------


def _bind_shadowing(i: int) -> CanonicalSemanticObject:
    pid = f"b{i:02d}_shadowing"
    r = _rng(pid)
    outer = r.randint(2, 30)
    inner_add = r.randint(2, 15)
    return CanonicalSemanticObject(
        id=pid, domain="binding", difficulty="medium",
        prose=(
            f"Let x be {outer}. Define f as the function that takes an argument, which is "
            f"also called x inside the definition of f, and returns that argument plus "
            f"{inner_add}. Now evaluate f at the value 1."
        ),
        question="What is the numerical value of f evaluated at 1?",
        answer=AnswerSpec(
            "numeric", 1 + inner_add,
            justification=f"the inner x is the argument 1, so the result is 1+{inner_add}; "
                          f"the outer x = {outer} is shadowed and irrelevant",
        ),
        semantics=SemanticFacts(
            entities={"x": "Real", "f": "Function[Real -> Real]"},
            declaration_kinds={"x": "const", "f": "def"},
            dependencies={"f": []},
            prohibited_assumptions=["that the inner x refers to the outer x"],
        ),
        distractors=[f"answering {outer + inner_add}, using the outer x"],
        reference_hml=(
            f"module Shadowing\n\nconst x : Real = {outer}\n"
            f"def f(u : Real) : Real := u + {inner_add}\n"
        ),
        information_asymmetry=[
            "Hamiltonian rejects the shadowing spelling outright (HML-N302), so the "
            "reference encoding renames the binder. The prose deliberately does not."
        ],
        generator="_bind_shadowing",
    )


def _bind_index_substitution(i: int) -> CanonicalSemanticObject:
    pid = f"b{i:02d}_index_substitution"
    r = _rng(pid)
    n = r.randint(3, 6)
    vals = [r.randint(1, 9) for _ in range(n)]
    j = r.randint(1, n)
    total = sum(vals)
    answer = total - vals[j - 1]
    return CanonicalSemanticObject(
        id=pid, domain="binding", difficulty="medium",
        prose=(
            f"A vector v of length {n} has entries, in order, "
            f"{', '.join(str(x) for x in vals)}. Consider the sum of v[i] taken over "
            f"every index i from 1 to {n} for which i is not equal to {j}."
        ),
        question="What is the numerical value of that sum?",
        answer=AnswerSpec(
            "numeric", answer,
            justification=f"total {total} minus the excluded entry v[{j}]={vals[j-1]}",
        ),
        semantics=SemanticFacts(
            entities={"v": "Vector[Real, N]", "N": "Natural"},
            declaration_kinds={"v": "const", "N": "index"},
            constraints=[f"i != {j}"],
        ),
        distractors=[f"summing all entries, giving {total}",
                     f"excluding the entry at position {j+1} by off-by-one"],
        reference_hml=(
            "module IndexSubstitution\n\nindex N : Natural\nconst v : Vector[Real, N]\n"
        ),
        generator="_bind_index_substitution",
    )


def _bind_alpha_equivalence(i: int) -> CanonicalSemanticObject:
    pid = f"b{i:02d}_alpha_equivalence"
    r = _rng(pid)
    a, b = r.sample(["u", "w", "t", "s", "q"], 2)
    c = r.randint(2, 12)
    return CanonicalSemanticObject(
        id=pid, domain="binding", difficulty="easy",
        prose=(
            f"Function F is defined as: F of {a} equals {a} times {c}. "
            f"Function G is defined as: G of {b} equals {b} times {c}."
        ),
        question=(
            "Do F and G denote the same function? Answer TRUE or FALSE."
        ),
        answer=AnswerSpec(
            "boolean", True,
            justification="the two definitions differ only by the name of a bound "
                          "variable, which is not part of a function's identity",
        ),
        semantics=SemanticFacts(
            entities={"F": "Function[Real -> Real]", "G": "Function[Real -> Real]"},
            declaration_kinds={"F": "def", "G": "def"},
        ),
        distractors=["treating a renamed bound variable as a different function"],
        reference_hml=(
            f"module AlphaEquivalence\n\ndef F({a} : Real) : Real := {a} * {c}\n"
            f"def G({b} : Real) : Real := {b} * {c}\n"
        ),
        generator="_bind_alpha_equivalence",
    )


def _bind_interface_rename(i: int) -> CanonicalSemanticObject:
    pid = f"b{i:02d}_interface_rename"
    r = _rng(pid)
    loc, scl = r.sample(_NAMES, 2)
    return CanonicalSemanticObject(
        id=pid, domain="binding", difficulty="hard",
        prose=(
            f"Model 1 states that a quantity is normally distributed with location {loc} "
            f"and scale {scl}. Model 2 states that the same quantity is normally "
            f"distributed with location {scl} and scale {loc}."
        ),
        question=(
            "Do Model 1 and Model 2 describe the same distribution for every choice of "
            f"{loc} and {scl}? Answer TRUE or FALSE."
        ),
        answer=AnswerSpec(
            "boolean", False,
            justification="swapping which symbol fills which ROLE is not a renaming; "
                          "location and scale are different roles with different meanings",
        ),
        semantics=SemanticFacts(
            entities={"Q": "RandomVariable[Real]", loc: "Real", scl: "PositiveReal"},
            declaration_kinds={"Q": "rv", loc: "param", scl: "param"},
            laws={"Q": {"location": loc, "scale": scl}}, law_families={"Q": "Normal"},
            prohibited_assumptions=["that swapping role fillers is a mere renaming"],
        ),
        distractors=["treating a role swap as an alpha-renaming"],
        reference_hml=(
            f"module InterfaceRename\n\nrv Q : RandomVariable[Real]\n"
            f"param {loc} : Real\nparam {scl} : PositiveReal\n\n"
            f"law Q ~ Normal(location := {loc}, scale := {scl})\n"
        ),
        generator="_bind_interface_rename",
    )


def _bind_conditioning_set(i: int) -> CanonicalSemanticObject:
    pid = f"b{i:02d}_conditioning_set"
    r = _rng(pid)
    extra = r.choice(["a covariate matrix X", "a group index g", "a baseline level c"])
    return CanonicalSemanticObject(
        id=pid, domain="binding", difficulty="medium",
        prose=(
            f"An outcome Y depends on a coefficient vector b, a noise scale s, and "
            f"{extra}. The law of Y is stated conditionally on all three of those, and "
            f"on nothing else."
        ),
        question=(
            "How many distinct symbols appear in the conditioning set of the law of Y? "
            "Give a single number."
        ),
        answer=AnswerSpec("numeric", 3, justification="b, s and the third listed object"),
        semantics=SemanticFacts(
            entities={"Y": "RandomVariable[Real]", "b": "Real", "s": "PositiveReal",
                      "c": "Real"},
            declaration_kinds={"Y": "rv", "b": "param", "s": "param", "c": "obs"},
            conditioning={"Y": ["b", "s", "c"]},
        ),
        distractors=["counting Y itself as part of its own conditioning set"],
        reference_hml=(
            "module ConditioningSet\n\nrv Y : RandomVariable[Real]\nparam b : Real\n"
            "param s : PositiveReal\nobs c : Real = 0\n\n"
            "law Y | b s c ~ Normal(location := b, scale := s)\n"
        ),
        generator="_bind_conditioning_set",
    )


# ---------------------------------------------------------------------------
# Quantifier and logical scope
# ---------------------------------------------------------------------------


def _quant_order(i: int) -> CanonicalSemanticObject:
    pid = f"q{i:02d}_order"
    r = _rng(pid)
    forall_first = (i % 2 == 0)
    rel = r.choice([("greater than", ">"), ("less than", "<")])
    if forall_first:
        prose = (
            f"Consider the following statement about the real numbers: for every real "
            f"number x, there exists a real number y such that y is {rel[0]} x."
        )
        truth = True
        why = "for each x, pick y = x ± 1; the choice of y may depend on x"
        order = ["forall x", "exists y"]
    else:
        prose = (
            f"Consider the following statement about the real numbers: there exists a "
            f"real number y such that, for every real number x, y is {rel[0]} x."
        )
        truth = False
        why = "no single y exceeds (or is below) every real; the reals are unbounded"
        order = ["exists y", "forall x"]
    return CanonicalSemanticObject(
        id=pid, domain="quantifier", difficulty="medium",
        prose=prose,
        question="Is the statement true over the real numbers? Answer TRUE or FALSE.",
        answer=AnswerSpec("boolean", truth, justification=why),
        semantics=SemanticFacts(
            quantifier_order=order,
            prohibited_assumptions=["that the two quantifier orders are interchangeable"],
        ),
        distractors=["reading the quantifiers in the opposite order"],
        reference_hml=(
            "module QuantifierOrder\n\n"
            + (
                f"prove forall x : Real . exists y : Real . y {rel[1]} x\n"
                if forall_first
                else f"prove exists y : Real . forall x : Real . y {rel[1]} x\n"
            )
        ),
        generator="_quant_order",
    )


def _quant_negation(i: int) -> CanonicalSemanticObject:
    pid = f"q{i:02d}_negation"
    r = _rng(pid)
    inside = r.random() < 0.5
    if inside:
        prose = (
            "Consider the statement: for every real number x, it is not the case that "
            "x squared is negative."
        )
        truth = True
        why = "no real square is negative, so the inner negation holds for every x"
    else:
        prose = (
            "Consider the statement: it is not the case that, for every real number x, "
            "x squared is negative."
        )
        truth = True
        why = ("the inner universal claim is false, so its negation is true; note this "
               "is true for a different reason than the other placement")
    return CanonicalSemanticObject(
        id=pid, domain="quantifier", difficulty="hard",
        prose=prose,
        question="Is the statement true over the real numbers? Answer TRUE or FALSE.",
        answer=AnswerSpec("boolean", truth, justification=why),
        semantics=SemanticFacts(
            # Negation placement is structural and is recorded in sequence: the
            # comparator walks `not` as part of the chain.
            quantifier_order=(["forall x", "not"] if inside else ["not", "forall x"]),
        ),
        distractors=["moving the negation across the quantifier"],
        reference_hml=(
            "module NegationPlacement\n\n"
            + (
                "prove forall x : Real . not x ^ 2 < 0\n"
                if inside
                else "prove not forall x : Real . x ^ 2 < 0\n"
            )
        ),
        generator="_quant_negation",
    )


def _quant_bounded(i: int) -> CanonicalSemanticObject:
    pid = f"q{i:02d}_bounded"
    r = _rng(pid)
    lo, hi = r.choice([(0, 1), (-1, 1), (0, 10), (2, 5)])
    exists_first = (i % 2 == 1)
    if exists_first:
        prose = (
            f"Consider the statement: there exists a real number y with y greater than "
            f"or equal to every real number x lying in the closed interval from {lo} "
            f"to {hi}."
        )
        truth = True
        why = f"y = {hi} works; the interval is bounded above"
        order = ["exists y", "forall x"]
    else:
        prose = (
            f"Consider the statement: for every real number x in the closed interval "
            f"from {lo} to {hi}, there exists a real number y greater than or equal "
            f"to x."
        )
        truth = True
        why = "trivially true; y may be chosen after x"
        order = ["forall x", "exists y"]
    return CanonicalSemanticObject(
        id=pid, domain="quantifier", difficulty="hard",
        prose=prose,
        question="Is the statement true? Answer TRUE or FALSE.",
        answer=AnswerSpec("boolean", truth, justification=why),
        semantics=SemanticFacts(
            quantifier_order=order,
            constraints=[f"{lo} <= x and x <= {hi}"],
        ),
        distractors=["assuming a bounded domain behaves like the whole real line"],
        reference_hml=(
            "module BoundedDomain\n\n"
            + (
                "prove exists y : Real . forall x : Real . y >= x\n"
                if exists_first
                else "prove forall x : Real . exists y : Real . y >= x\n"
            )
        ),
        generator="_quant_bounded",
    )


def _quant_unique(i: int) -> CanonicalSemanticObject:
    pid = f"q{i:02d}_unique"
    r = _rng(pid)
    c = r.randint(2, 20)
    return CanonicalSemanticObject(
        id=pid, domain="quantifier", difficulty="medium",
        prose=(
            f"Consider the statement: there exists exactly one real number x such that "
            f"x cubed equals {c}."
        ),
        question="Is the statement true over the real numbers? Answer TRUE or FALSE.",
        answer=AnswerSpec(
            "boolean", True,
            justification="cubing is a bijection on the reals, so the real cube root is "
                          "unique (the other two roots are non-real)",
        ),
        semantics=SemanticFacts(quantifier_order=["exists_unique x"]),
        distractors=["counting the two complex roots as real solutions"],
        reference_hml=(
            f"module UniqueCubeRoot\n\nprove exists unique x : Real . x ^ 3 = {c}\n"
        ),
        generator="_quant_unique",
    )


def _quant_scope_swap_pair(i: int) -> CanonicalSemanticObject:
    """The adversarial pair required by §5: same syntax, altered scope."""
    pid = f"q{i:02d}_scope_swap"
    r = _rng(pid)
    eps = r.choice(["every positive tolerance", "each positive epsilon"])
    swapped = (i % 2 == 0)
    if not swapped:
        prose = (
            f"A function f on the reals is said to have property P when: for {eps}, "
            "there exists a positive delta, possibly depending on both the tolerance and "
            "on the point, such that the usual closeness condition holds at that point."
        )
        ans = "POINTWISE"
    else:
        prose = (
            f"A function f on the reals is said to have property P when: for {eps}, "
            "there exists a positive delta, depending on the tolerance alone and not on "
            "the point, such that the usual closeness condition holds at every point."
        )
        ans = "UNIFORM"
    return CanonicalSemanticObject(
        id=pid, domain="quantifier", difficulty="hard",
        prose=prose,
        question=(
            "Is property P pointwise continuity or uniform continuity? Answer with "
            "exactly one of: POINTWISE or UNIFORM."
        ),
        answer=AnswerSpec(
            "choice", ans, options=["POINTWISE", "UNIFORM"],
            justification="the distinction is solely whether delta may depend on the "
                          "point, i.e. the order of the point and delta quantifiers",
        ),
        semantics=SemanticFacts(
            quantifier_order=(
                ["forall eps", "forall x", "exists delta"] if not swapped
                else ["forall eps", "exists delta", "forall x"]
            ),
            prohibited_assumptions=["that quantifier order is a stylistic choice"],
        ),
        distractors=["treating the two orderings as equivalent"],
        reference_hml=(
            "module ContinuityKind\n\n"
            + (
                "prove forall eps : PositiveReal . forall x : Real . "
                "exists delta : PositiveReal . delta > 0\n"
                if not swapped
                else "prove forall eps : PositiveReal . exists delta : PositiveReal . "
                "forall x : Real . delta > 0\n"
            )
        ),
        generator="_quant_scope_swap_pair",
    )


# ---------------------------------------------------------------------------
# Dimensional reasoning
# ---------------------------------------------------------------------------

_DIM_CASES = [
    ("kinetic energy, one half times mass times speed squared",
     "Mass * Length^2 / Time^2", "m: Mass, v: Length/Time"),
    ("momentum, mass times speed", "Mass * Length / Time", "m: Mass, v: Length/Time"),
    ("pressure, force divided by area", "Mass / (Length * Time^2)",
     "F: Mass*Length/Time^2, A: Length^2"),
    ("power, energy divided by time", "Mass * Length^2 / Time^3", "E: energy, t: Time"),
    ("density, mass divided by volume", "Mass / Length^3", "m: Mass, V: Length^3"),
    ("angular frequency, speed divided by radius", "1 / Time", "v: Length/Time, r: Length"),
    ("charge, current times time", "Current * Time", "I: Current, t: Time"),
    ("energy per unit temperature", "Mass * Length^2 / (Time^2 * Temperature)",
     "E: energy, T: Temperature"),
    ("acceleration, speed divided by time", "Length / Time^2", "v: Length/Time, t: Time"),
    ("force, mass times acceleration", "Mass * Length / Time^2",
     "m: Mass, a: Length/Time^2"),
    ("molar energy, energy divided by amount of substance",
     "Mass * Length^2 / (Time^2 * Amount)", "E: energy, n: Amount"),
    ("luminous efficacy, luminous intensity divided by power",
     "Luminosity * Time^3 / (Mass * Length^2)", "I: Luminosity, P: power"),
]


def _dim_derive(i: int) -> CanonicalSemanticObject:
    pid = f"d{i:02d}_derive"
    r = _rng(pid)
    desc, dim, given = r.choice(_DIM_CASES)
    return CanonicalSemanticObject(
        id=pid, domain="dimensional", difficulty="medium",
        prose=(
            f"Consider the physical quantity defined as {desc}. The dimensions of the "
            f"inputs are: {given}."
        ),
        question="What is the physical dimension of the resulting quantity?",
        answer=AnswerSpec("dimension", dim, justification=f"dimension of {desc}"),
        semantics=SemanticFacts(dimensions={"result": dim}),
        distractors=["dropping an exponent or inverting the denominator"],
        reference_hml=(
            f"module DimensionDerivation\n\nparam q : Quantity[{dim}]\n\n"
            f"check dimension q = {dim}\n"
        ),
        generator="_dim_derive",
    )


def _dim_invalid_addition(i: int) -> CanonicalSemanticObject:
    pid = f"d{i:02d}_invalid_addition"
    r = _rng(pid)
    a, b = r.sample(
        [("a mass", "Mass"), ("a length", "Length"), ("a duration", "Time"),
         ("a temperature", "Temperature"), ("an electric current", "Current")], 2
    )
    return CanonicalSemanticObject(
        id=pid, domain="dimensional", difficulty="easy",
        prose=(
            f"An expression adds {a[0]} to {b[0]}, and then multiplies the result by a "
            f"dimensionless constant."
        ),
        question=(
            "Is this expression dimensionally valid? Answer TRUE or FALSE."
        ),
        answer=AnswerSpec(
            "boolean", False,
            justification=f"{a[1]} and {b[1]} are different dimensions and cannot be added",
        ),
        semantics=SemanticFacts(dimensions={"x": a[1], "y": b[1]}),
        distractors=["assuming a dimensionless multiplier repairs the addition"],
        reference_hml=(
            f"module InvalidAddition\n\nparam x : Quantity[{a[1]}]\n"
            f"param y : Quantity[{b[1]}]\n"
        ),
        generator="_dim_invalid_addition",
    )


def _dim_fractional_power(i: int) -> CanonicalSemanticObject:
    pid = f"d{i:02d}_fractional_power"
    r = _rng(pid)
    case = r.choice([
        ("the square root of a length divided by an acceleration", "Time",
         "sqrt(Length / (Length/Time^2)) = sqrt(Time^2) = Time"),
        ("the square root of an area", "Length", "sqrt(Length^2) = Length"),
        # NOTE: a case with a half-integer exponent was removed here. HML type syntax
        # cannot express `Quantity[Mass^1/2 * Length]` -- `^` takes an integer literal
        # and the following `/` is read as dimension division. Recorded as a v0
        # limitation in docs/evaluation/PRE_EVALUATION_AUDIT.md rather than encoded wrong.
        ("the cube root of a volume", "Length", "cbrt(Length^3) = Length"),
    ])
    desc, dim, why = case
    return CanonicalSemanticObject(
        id=pid, domain="dimensional", difficulty="hard",
        prose=f"Consider the quantity given by {desc}.",
        question="What is the physical dimension of that quantity?",
        answer=AnswerSpec("dimension", dim, justification=why),
        semantics=SemanticFacts(dimensions={"result": dim}),
        distractors=["failing to halve the exponents under a square root"],
        reference_hml=(
            f"module FractionalPower\n\nparam q : Quantity[{dim}]\n\n"
            f"check dimension q = {dim}\n"
        ),
        generator="_dim_fractional_power",
    )


def _dim_unknown_constant(i: int) -> CanonicalSemanticObject:
    pid = f"d{i:02d}_unknown_constant"
    r = _rng(pid)
    case = r.choice([
        ("an energy equals a constant k times a temperature",
         "Mass * Length^2 / (Time^2 * Temperature)"),
        ("a force equals a constant k times a length", "Mass / Time^2"),
        ("a speed equals a constant k times a duration", "Length / Time^2"),
        ("a pressure equals a constant k times a density",
         "Length^2 / Time^2"),
    ])
    desc, dim = case
    return CanonicalSemanticObject(
        id=pid, domain="dimensional", difficulty="hard",
        prose=(
            f"In a physical relationship, {desc}. The relationship is dimensionally "
            f"consistent."
        ),
        question="What is the physical dimension of the constant k?",
        answer=AnswerSpec("dimension", dim,
                          justification="divide the left dimension by the right"),
        semantics=SemanticFacts(dimensions={"k": dim}),
        distractors=["inverting the ratio"],
        reference_hml=(
            f"module UnknownConstant\n\nparam k : Quantity[{dim}]\n\n"
            f"check dimension k = {dim}\n"
        ),
        generator="_dim_unknown_constant",
    )


# ---------------------------------------------------------------------------
# Algebraic constraints and semantic equivalence
# ---------------------------------------------------------------------------


def _alg_constrained_min(i: int) -> CanonicalSemanticObject:
    pid = f"a{i:02d}_constrained_min"
    r = _rng(pid)
    c = r.choice([6, 8, 10, 12, 14, 16, 20, 24])
    val = c * c / 2.0
    return CanonicalSemanticObject(
        id=pid, domain="algebraic", difficulty="medium",
        prose=(
            f"Two real numbers x and y are both non-negative, and their sum is at least "
            f"{c}."
        ),
        question=(
            "What is the minimum possible numerical value of x squared plus y squared?"
        ),
        answer=AnswerSpec(
            "numeric", val, tolerance=1e-6,
            justification=f"minimum on x+y={c} at x=y={c/2}, giving 2*({c/2})^2 = {val}",
        ),
        semantics=SemanticFacts(
            entities={"x": "Real", "y": "Real"},
            declaration_kinds={"x": "var", "y": "var"},
            constraints=[f"x + y >= {c}", "x >= 0", "y >= 0"],
            objective="minimise x^2 + y^2",
        ),
        distractors=[f"answering {c*c}, using a corner rather than the symmetric point"],
        reference_hml=(
            f"module ConstrainedMin\n\nvar x : Real\nvar y : Real\n\n"
            f"require x + y >= {c}\nrequire x >= 0\nrequire y >= 0\n\n"
            f"minimise x ^ 2 + y ^ 2\n\nsolve x y\n"
        ),
        generator="_alg_constrained_min",
    )


def _alg_equivalence(i: int) -> CanonicalSemanticObject:
    pid = f"a{i:02d}_equivalence"
    r = _rng(pid)
    a = r.randint(2, 9)
    equivalent = (i % 2 == 0)
    if equivalent:
        e1 = f"(x + {a}) squared"
        e2 = f"x squared plus {2*a} x plus {a*a}"
        truth = True
        why = "binomial expansion"
    else:
        e1 = f"(x + {a}) squared"
        e2 = f"x squared plus {a*a}"
        truth = False
        why = f"the cross term {2*a}x is missing"
    return CanonicalSemanticObject(
        id=pid, domain="algebraic", difficulty="easy",
        prose=f"Consider two expressions in a real variable x: {e1}, and {e2}.",
        question=(
            "Are the two expressions equal for every real x? Answer TRUE or FALSE."
        ),
        answer=AnswerSpec("boolean", truth, justification=why),
        semantics=SemanticFacts(entities={"x": "Real"}),
        distractors=["dropping the cross term"],
        reference_hml=(
            f"module Equivalence\n\nvar x : Real\n\n"
            f"prove (x + {a}) ^ 2 = x ^ 2 + {2*a} * x + {a*a}\n"
        ),
        generator="_alg_equivalence",
    )


def _alg_domain_restriction(i: int) -> CanonicalSemanticObject:
    pid = f"a{i:02d}_domain_restriction"
    r = _rng(pid)
    k = r.randint(2, 9)
    return CanonicalSemanticObject(
        id=pid, domain="algebraic", difficulty="medium",
        prose=(
            f"Consider the equation involving a real variable x: the square root of x, "
            f"multiplied by itself, equals x. Separately consider the claim that this "
            f"holds for x equal to negative {k}."
        ),
        question=(
            "Is the claim about x equal to negative "
            f"{k} valid over the real numbers? Answer TRUE or FALSE."
        ),
        answer=AnswerSpec(
            "boolean", False,
            justification=f"the real square root is undefined at -{k}, so the claim has "
                          f"no truth value over the reals under the stated domain",
        ),
        semantics=SemanticFacts(
            entities={"x": "NonNegativeReal"},
            constraints=["x >= 0"],
            prohibited_assumptions=["that sqrt is total on the reals"],
        ),
        distractors=["applying the identity outside its domain"],
        reference_hml=(
            "module DomainRestriction\n\nvar x : NonNegativeReal\n\nrequire x >= 0\n"
        ),
        generator="_alg_domain_restriction",
    )


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

_PROB_FAMILIES = [
    _prob_scale_vs_variance, _prob_exponential_rate, _prob_beta_binomial_posterior,
    _prob_role_map, _prob_rv_vs_distribution, _prob_binomial_moments,
    _prob_conditional_independence, _prob_param_vs_observation,
]
_BIND_FAMILIES = [
    _bind_shadowing, _bind_index_substitution, _bind_alpha_equivalence,
    _bind_interface_rename, _bind_conditioning_set,
]
_QUANT_FAMILIES = [
    _quant_order, _quant_negation, _quant_bounded, _quant_unique,
    _quant_scope_swap_pair,
]
_DIM_FAMILIES = [
    _dim_derive, _dim_invalid_addition, _dim_fractional_power, _dim_unknown_constant,
]
_ALG_FAMILIES = [_alg_constrained_min, _alg_equivalence, _alg_domain_restriction]

_BY_CATEGORY = {
    "probability": _PROB_FAMILIES,
    "binding": _BIND_FAMILIES,
    "quantifier": _QUANT_FAMILIES,
    "dimensional": _DIM_FAMILIES,
    "algebraic": _ALG_FAMILIES,
}


def build_all() -> list[CanonicalSemanticObject]:
    """Generate the full corpus, round-robin over families within each category."""
    out: list[CanonicalSemanticObject] = []
    for category, target in CATEGORY_TARGETS.items():
        families = _BY_CATEGORY[category]
        for n in range(target):
            fam = families[n % len(families)]
            cso = fam(n + 1)
            cso.seed = n + 1
            out.append(cso)
    seen: dict[str, int] = {}
    for c in out:
        seen[c.id] = seen.get(c.id, 0) + 1
    dupes = {k: v for k, v in seen.items() if v > 1}
    if dupes:
        raise AssertionError(f"duplicate problem ids: {dupes}")
    return out


def build_demos() -> list[CanonicalSemanticObject]:
    """Two worked demonstrations, structurally distinct from every benchmark item.

    Held out: the ids are prefixed `demo_` and `build_all` never emits them, so no
    benchmark item appears in a demonstration (§5).
    """
    d1 = CanonicalSemanticObject(
        id="demo_normal_roles", domain="probability", difficulty="easy",
        prose=(
            "A reading R is normally distributed. Its centre is written c, and its "
            "spread, expressed as a standard deviation, is written d, where d is "
            "strictly positive."
        ),
        question="What is the name of the role that d fills?",
        answer=AnswerSpec("exact_string", "scale",
                          justification="a standard deviation is the scale parameter"),
        semantics=SemanticFacts(
            entities={"R": "RandomVariable[Real]", "c": "Real", "d": "PositiveReal"},
            declaration_kinds={"R": "rv", "c": "param", "d": "param"},
            laws={"R": {"location": "c", "scale": "d"}}, law_families={"R": "Normal"},
        ),
        reference_hml=(
            "module Demo\n\nrv R : RandomVariable[Real]\nparam c : Real\n"
            "param d : PositiveReal\n\nlaw R ~ Normal(location := c, scale := d)\n"
        ),
        generator="demo",
    )
    d2 = CanonicalSemanticObject(
        id="demo_dimension", domain="dimensional", difficulty="easy",
        prose=(
            "A quantity is defined as a mass multiplied by a speed, where speed has the "
            "dimension of length divided by time."
        ),
        question="What is the physical dimension of that quantity?",
        answer=AnswerSpec("dimension", "Mass * Length / Time",
                          justification="Mass times Length/Time"),
        semantics=SemanticFacts(dimensions={"result": "Mass * Length / Time"}),
        reference_hml=(
            "module DemoDim\n\nparam m : Quantity[Mass]\n"
            "param v : Quantity[Length / Time]\n\ndef p := m * v\n\n"
            "check dimension p = Mass * Length / Time\n"
        ),
        generator="demo",
    )
    return [d1, d2]
