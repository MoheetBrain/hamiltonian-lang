"""Mutation testing: each tier must be able to both pass and fail.

A tier that always passes certifies nothing; a tier that always fails refutes
everything. Each test below takes a pair that a specific tier certifies, applies a
mutation that changes the meaning, and requires the certificate to disappear.

The load-bearing assertion in every case is the same one: after a
meaning-changing mutation the scorer must **not** say ``VERIFIED_EQUIVALENT``. A
false positive silently declares a wrong answer right; a false negative only costs
coverage.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.equivalence import (
    Endpoint,
    EquivalenceScorer,
    EquivalenceStatus,
)


def verdict(left: str, right: str) -> EquivalenceStatus:
    for source in (left, right):
        assert compile_source(source).ok(), f"test input does not compile:\n{source}"
    return EquivalenceScorer().compare(
        left, right, endpoint=Endpoint.ENCODING_EQUIVALENCE
    ).status


def certified(left: str, right: str) -> bool:
    return verdict(left, right) is EquivalenceStatus.VERIFIED_EQUIVALENT


def decided_by(left: str, right: str) -> str | None:
    report = EquivalenceScorer().compare(left, right)
    return str(report.decided_by) if report.decided_by else None


ARITH = "module M\nparam a : Real\nparam b : Real\n"
BOOL = "module M\nparam p : Bool\nparam q : Bool\n"
REAL = "module M\nparam x : Real\n"


# -- TIER 0 can pass and can fail -------------------------------------------


def test_tier0_passes_on_identity_and_fails_on_any_change():
    base = f"{ARITH}def f := a + b\n"
    assert decided_by(base, base) == "TIER0_CANONICAL_IDENTITY"
    mutated = f"{ARITH}def f := a - b\n"
    assert decided_by(base, mutated) != "TIER0_CANONICAL_IDENTITY"


# -- TIER 1 can pass and can fail -------------------------------------------


def test_tier1_passes_on_renaming_and_fails_on_a_swapped_operand():
    assert decided_by(f"{ARITH}def f := a - b\n", "module Z\nparam u : Real\nparam v : Real\ndef g := u - v\n") == "TIER1_ALPHA_NORMALISATION"
    assert not certified(f"{ARITH}def f := a - b\n", f"{ARITH}def f := b - a\n")


@pytest.mark.parametrize(
    "mutation",
    [
        ("a + b", "a - b"),
        ("a * b", "a / b"),
        ("a + b", "a + b + 1"),
    ],
)
def test_tier1_rejects_operator_and_operand_mutations(mutation):
    original, mutated = mutation
    assert not certified(f"{ARITH}def f := {original}\n", f"{ARITH}def f := {mutated}\n")


# -- TIER 2, difference-is-zero ---------------------------------------------


def test_tier2_algebra_passes_and_a_coefficient_mutation_breaks_it():
    good = certified(
        f"{ARITH}def f := (a + 1) * (a + 1)\n", f"{ARITH}def f := a^2 + 2 * a + 1\n"
    )
    assert good
    assert not certified(
        f"{ARITH}def f := (a + 1) * (a + 1)\n", f"{ARITH}def f := a^2 + 3 * a + 1\n"
    )
    assert not certified(
        f"{ARITH}def f := (a + 1) * (a + 1)\n", f"{ARITH}def f := a^2 + 2 * a - 1\n"
    )


def test_tier2_algebra_rejects_an_exponent_mutation():
    assert certified(f"{ARITH}def f := a * a\n", f"{ARITH}def f := a^2\n")
    assert not certified(f"{ARITH}def f := a * a\n", f"{ARITH}def f := a^3\n")


# -- TIER 2, relation proportionality ---------------------------------------


def test_tier2_relations_pass_and_break_on_direction_strictness_and_constant():
    assert certified(f"{REAL}require 2 * x < 4\n", f"{REAL}require x < 2\n")
    # direction
    assert not certified(f"{REAL}require 2 * x < 4\n", f"{REAL}require x > 2\n")
    # strictness
    assert not certified(f"{REAL}require 2 * x < 4\n", f"{REAL}require x <= 2\n")
    # constant
    assert not certified(f"{REAL}require 2 * x < 4\n", f"{REAL}require x < 3\n")


def test_tier2_relations_break_when_the_sign_assumption_is_removed():
    positive = "module M\nparam a : PositiveReal\nparam x : Real\n"
    unknown = "module M\nparam a : Real\nparam x : Real\n"
    assert certified(f"{positive}require a * x < 6\n", f"{positive}require x < 6 / a\n")
    assert not certified(f"{unknown}require a * x < 6\n", f"{unknown}require x < 6 / a\n")


# -- TIER 2, propositional --------------------------------------------------


def test_tier2_propositional_passes_and_breaks_on_a_negation_mutation():
    assert certified(f"{BOOL}prove p => q\n", f"{BOOL}prove (not q) => (not p)\n")
    assert not certified(f"{BOOL}prove p => q\n", f"{BOOL}prove (not q) => p\n")
    assert not certified(f"{BOOL}prove p => q\n", f"{BOOL}prove q => (not p)\n")


def test_tier2_propositional_breaks_on_a_connective_mutation():
    assert certified(f"{BOOL}prove not (p and q)\n", f"{BOOL}prove (not p) or (not q)\n")
    assert not certified(f"{BOOL}prove not (p and q)\n", f"{BOOL}prove (not p) and (not q)\n")


# -- TIER 3 can refute and can decline --------------------------------------


def test_tier3_refutes_a_real_difference_and_declines_on_an_identity():
    powers = "module M\nparam a : PositiveReal\nparam b : Real\nparam c : Real\n"
    assert (
        verdict(f"{powers}def f := (a^b)^c\n", f"{powers}def f := a^(b^c)\n")
        is EquivalenceStatus.COUNTEREXAMPLE_FOUND
    )
    # The identity case never reaches Tier 3 with a counterexample.
    assert certified(f"{ARITH}def f := a + b\n", f"{ARITH}def f := b + a\n")


# -- guards can fire and can stay silent ------------------------------------


@pytest.mark.parametrize(
    "reference,mutated,control",
    [
        (
            "module M\nconst t : PValue = 0.05\n",
            "module M\nconst t : PosteriorProbability = 0.05\n",
            "module M\nconst t : PValue = 0.05\n",
        ),
        (
            "module M\nparam m : Quantity[Mass]\n",
            "module M\nparam m : Quantity[Length]\n",
            "module M\nparam m : Quantity[Mass]\n",
        ),
        (
            "module M\nparam x : Real\nminimise x^2\n",
            "module M\nparam x : Real\nmaximise x^2\n",
            "module M\nparam x : Real\nminimise x^2\n",
        ),
        (
            "module M\nrv y : Real\n",
            "module M\nparam y : Real\n",
            "module M\nrv y : Real\n",
        ),
    ],
)
def test_each_guard_fires_on_the_mutation_and_not_on_the_control(
    reference, mutated, control
):
    assert verdict(reference, mutated) is EquivalenceStatus.VERIFIED_NONEQUIVALENT
    assert certified(reference, control)


# -- the mutation that matters most -----------------------------------------


MEANING_CHANGING_MUTATIONS = [
    # (reference, mutated) -- every one must fail to certify
    (f"{ARITH}def f := a + b\n", f"{ARITH}def f := a - b\n"),
    (f"{ARITH}def f := a * b\n", f"{ARITH}def f := a + b\n"),
    (f"{ARITH}def f := a / b\n", f"{ARITH}def f := b / a\n"),
    (f"{ARITH}def f := a^2\n", f"{ARITH}def f := 2 * a\n"),
    (f"{REAL}require x > 0\n", f"{REAL}require x >= 0\n"),
    (f"{REAL}require x > 0\n", f"{REAL}require x < 0\n"),
    (f"{BOOL}prove p => q\n", f"{BOOL}prove q => p\n"),
    (f"{BOOL}prove p and q\n", f"{BOOL}prove p or q\n"),
    (f"{BOOL}prove p\n", f"{BOOL}prove not p\n"),
    (
        "module M\nprove forall x : Real . exists y : Real . y > x\n",
        "module M\nprove exists y : Real . forall x : Real . y > x\n",
    ),
    (
        "module M\nobs n : Natural = 10\n",
        "module M\nobs n : Natural = 11\n",
    ),
    (
        "module M\nparam t : Probability\nrv y : Natural\n"
        "law y | t ~ Binomial(trials := 10, prob := t)\n",
        "module M\nparam t : Probability\nrv y : Natural\n"
        "law y | t ~ Binomial(trials := 12, prob := t)\n",
    ),
    (
        "module M\nparam r : PositiveReal\nrv y : Natural\nlaw y | r ~ Poisson(rate := r)\n",
        "module M\nparam r : PositiveReal\nrv y : Natural\n"
        "law y | r ~ Binomial(trials := 10, prob := 0.5)\n",
    ),
    (
        "module M\nparam t : Probability\nprior t ~ Beta(alpha := 1, beta := 2)\n",
        "module M\nparam t : Probability\nprior t ~ Beta(alpha := 2, beta := 1)\n",
    ),
]


@pytest.mark.parametrize(
    "reference,mutated", MEANING_CHANGING_MUTATIONS, ids=lambda v: None
)
def test_no_meaning_changing_mutation_is_ever_certified_equivalent(reference, mutated):
    assert verdict(reference, mutated) is not EquivalenceStatus.VERIFIED_EQUIVALENT


MEANING_PRESERVING_REWRITES = [
    (f"{ARITH}def f := a + b\n", f"{ARITH}def f := b + a\n"),
    (f"{ARITH}def f := a * (b + 1)\n", f"{ARITH}def f := a * b + a\n"),
    (f"{REAL}require 3 * x <= 9\n", f"{REAL}require x <= 3\n"),
    (f"{BOOL}prove p and q\n", f"{BOOL}prove q and p\n"),
    (f"{BOOL}prove p => q\n", f"{BOOL}prove (not p) or q\n"),
]


@pytest.mark.parametrize(
    "reference,rewritten", MEANING_PRESERVING_REWRITES, ids=lambda v: None
)
def test_a_meaning_preserving_rewrite_is_never_called_wrong(reference, rewritten):
    status = verdict(reference, rewritten)
    assert status not in (
        EquivalenceStatus.VERIFIED_NONEQUIVALENT,
        EquivalenceStatus.COUNTEREXAMPLE_FOUND,
    )
