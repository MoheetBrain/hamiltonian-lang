"""Every guard, in both directions: it fires on the difference and stays silent otherwise.

A guard that only ever fires is a guard that would refute the whole corpus, so
each case is paired with a control that must *not* fire.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.equivalence import (
    Endpoint,
    EquivalenceScorer,
    EquivalenceStatus,
    align,
    collect_declared_types,
    run_guards,
)
from hamiltonian_lang.equivalence.sympy_bridge import TranslationContext


def guards_for(left: str, right: str):
    a, b = compile_source(left), compile_source(right)
    assert a.ok() and b.ok(), "both sides must compile"
    alignment = align(a.module, b.module)
    ctx = TranslationContext(
        left_types=collect_declared_types(a.module),
        right_types=collect_declared_types(b.module),
        pairing=dict(alignment.env.bwd),
    )
    return run_guards(alignment, ctx)


def methods(left: str, right: str) -> set[str]:
    return {v.proof.method for v in guards_for(left, right) if v.proof is not None}


# -- epistemic kind ---------------------------------------------------------


@pytest.mark.parametrize(
    "a,b",
    [
        ("PValue", "PosteriorProbability"),
        ("PValue", "Probability"),
        ("Probability", "PosteriorProbability"),
    ],
)
def test_the_three_unit_interval_kinds_are_never_interchangeable(a, b):
    fired = methods(f"module M\nconst t : {a} = 0.05\n", f"module M\nconst t : {b} = 0.05\n")
    assert "guard.epistemic_kind_differs" in fired


def test_the_same_epistemic_kind_does_not_fire():
    assert not methods(
        "module M\nconst t : PValue = 0.05\n", "module M\nconst t : PValue = 0.05\n"
    )


# -- dimensions -------------------------------------------------------------


def test_different_dimensions_refute():
    fired = methods(
        "module M\nparam m : Quantity[Mass]\n", "module M\nparam m : Quantity[Length]\n"
    )
    assert "guard.dimension_differs" in fired


def test_the_same_dimension_does_not_fire():
    assert not methods(
        "module M\nparam m : Quantity[Mass]\n", "module M\nparam m : Quantity[Mass]\n"
    )


# -- random variables -------------------------------------------------------


def test_a_random_variable_is_not_a_value():
    fired = methods("module M\nrv y : Real\n", "module M\nparam y : Real\n")
    assert "guard.random_variable_vs_value" in fired


# -- epistemic role ---------------------------------------------------------


def test_observed_data_is_not_an_unknown_parameter():
    fired = methods(
        "module M\nobs n : Natural = 10\n", "module M\nparam n : Natural = 10\n"
    )
    assert "guard.epistemic_role_differs" in fired


def test_an_assumption_is_not_a_claim():
    fired = methods(
        "module M\nparam x : Real\nassume x > 0\n",
        "module M\nparam x : Real\nprove x > 0\n",
    )
    assert "guard.epistemic_role_differs" in fired


def test_a_constraint_is_not_an_assumption():
    fired = methods(
        "module M\nparam x : Real\nassume x > 0\n",
        "module M\nparam x : Real\nrequire x > 0\n",
    )
    assert "guard.epistemic_role_differs" in fired


# -- objective direction ----------------------------------------------------


def test_minimising_is_not_maximising():
    fired = methods(
        "module M\nparam x : Real\nminimise x^2\n", "module M\nparam x : Real\nmaximise x^2\n"
    )
    assert "guard.objective_direction_differs" in fired


def test_the_same_direction_does_not_fire():
    assert not methods(
        "module M\nparam x : Real\nminimise x^2\n", "module M\nparam x : Real\nminimise x^2\n"
    )


# -- conditioning -----------------------------------------------------------


def test_a_conditional_law_is_not_a_marginal_law():
    conditional = (
        "module M\nparam t : Probability\nrv y : Natural\n"
        "law y | t ~ Binomial(trials := 10, prob := t)\n"
    )
    marginal = (
        "module M\nparam t : Probability\nrv y : Natural\n"
        "law y ~ Binomial(trials := 10, prob := t)\n"
    )
    assert "guard.conditioning_set_differs" in methods(conditional, marginal)


# -- quantifier alternation -------------------------------------------------


def test_alternation_across_kinds_refutes_with_a_dependence_witness():
    fired = guards_for(
        "module M\nprove forall x : Real . exists y : Real . y > x\n",
        "module M\nprove exists y : Real . forall x : Real . y > x\n",
    )
    assert fired
    proof = fired[0].proof
    assert proof is not None
    assert proof.method == "guard.quantifier_alternation_differs"
    witnesses = fired[0].evidence["dependence_witnesses"]
    assert set(witnesses) == {"x", "y"}, "both binders must be witnessed to matter"


def test_two_universals_swapping_does_not_refute():
    assert not guards_for(
        "module M\nprove forall x : Real . forall y : Real . x > y\n",
        "module M\nprove forall y : Real . forall x : Real . x > y\n",
    )


def test_a_vacuous_binder_is_not_refuted():
    """``forall x . exists y . x = x`` does not depend on y, so order cannot matter."""
    assert not guards_for(
        "module M\nprove forall x : Real . exists y : Real . x = x\n",
        "module M\nprove exists y : Real . forall x : Real . x = x\n",
    )


# -- comparable types are not refuted ---------------------------------------


def test_a_comparable_type_widening_is_not_treated_as_a_difference():
    """``Probability`` is a ``NonNegativeReal``; that is a refinement, not a conflict."""
    fired = methods(
        "module M\nparam p : Probability\n", "module M\nparam p : NonNegativeReal\n"
    )
    assert "guard.declared_types_incomparable" not in fired
    assert "guard.epistemic_kind_differs" not in fired


def test_a_guessed_pairing_never_refutes():
    """Two same-kind declarations paired only positionally must not fire a guard."""
    left = (
        "module M\nparam alpha : Quantity[Mass]\nparam beta : Quantity[Length]\n"
        "def f := alpha\n"
    )
    right = (
        "module M\nparam gamma : Quantity[Length]\nparam delta : Quantity[Mass]\n"
        "def f := gamma\n"
    )
    report = EquivalenceScorer().compare(
        left, right, endpoint=Endpoint.ENCODING_EQUIVALENCE
    )
    assert report.status is not EquivalenceStatus.VERIFIED_EQUIVALENT
    guard_hits = [o for o in report.outcomes if str(o.tier) == "GUARD"]
    assert not guard_hits, "a positional guess must not become a refutation"
