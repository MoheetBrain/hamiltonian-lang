"""P-value versus posterior — closing a conflation that was specified and not implemented.

Found by the adversarial agent: `spec/v1/semantic_objects.yaml` names PValue as a distinct
type with no coercion to a posterior, and no such type existed. Both sides were typed
`Probability`, so `posterior(H0 | data) := p_value` type-checked. L4's kill criterion is
"any prohibited conflation type-checks", so L4 was failing its own criterion.

All three quantities are reals in [0, 1], which is exactly why they get confused. The
distinction is epistemic, not numeric, so the value can never carry it — only the type can.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.v1.epistemic import (
    ContextError,
    PosteriorProbability,
    ProbabilityKind,
    PValue,
    probability_coercion_allowed,
)


def test_a_p_value_is_not_a_posterior():
    ok, why = PValue(0.18).may_be_used_as(ProbabilityKind.POSTERIOR)
    assert not ok
    assert "prosecutor" in why.lower()


def test_as_posterior_raises_rather_than_converting():
    with pytest.raises(TypeError):
        PValue(0.18).as_posterior()


def test_a_posterior_is_not_a_p_value():
    ok, _ = PosteriorProbability(0.31, prior="Beta(1,1)").may_be_used_as(
        ProbabilityKind.P_VALUE
    )
    assert not ok


def test_a_p_value_is_not_a_model_probability():
    assert not PValue(0.04).may_be_used_as(ProbabilityKind.MODEL_PROBABILITY)[0]


def test_a_posterior_requires_the_prior_it_was_computed_against():
    with pytest.raises(ContextError):
        PosteriorProbability(0.3, prior="")


@pytest.mark.parametrize("bad", [-0.1, 1.5, 2.0])
def test_out_of_range_values_are_rejected(bad):
    with pytest.raises(ValueError):
        PValue(bad)
    with pytest.raises(ValueError):
        PosteriorProbability(bad, prior="Beta(1,1)")


def test_identity_is_the_only_permitted_coercion():
    for k in ProbabilityKind:
        assert probability_coercion_allowed(k, k)[0]
    for a in ProbabilityKind:
        for b in ProbabilityKind:
            if a != b:
                assert not probability_coercion_allowed(a, b)[0], f"{a} -> {b} allowed"


def test_p_value_is_not_a_subclass_of_any_probability_type():
    """Subclassing would create the very coercion path this exists to forbid."""
    assert not issubclass(PValue, PosteriorProbability)
    assert not issubclass(PosteriorProbability, PValue)
