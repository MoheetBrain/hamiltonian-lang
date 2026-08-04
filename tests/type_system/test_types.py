"""Type-system, distribution-role and dimensional tests."""

from __future__ import annotations

from fractions import Fraction

from hamiltonian_lang import compile_source
from hamiltonian_lang.types import (
    Dimension,
    DistributionType,
    RandomVariableType,
    ScalarType,
    is_subtype,
    join,
)


def codes(src: str) -> list[str]:
    return [d.code for d in compile_source(src).diagnostics.errors]


def ok(src: str):
    r = compile_source(src)
    assert r.ok(), "\n" + r.diagnostics.render()
    return r


S = ScalarType


# -- the scalar lattice --------------------------------------------------


def test_natural_is_an_integer_is_a_real():
    assert is_subtype(S("Natural"), S("Integer"))
    assert is_subtype(S("Natural"), S("Real"))


def test_probability_is_not_a_positive_real():
    """0 is a probability and is not a positive real. The order is a poset."""
    assert not is_subtype(S("Probability"), S("PositiveReal"))


def test_positive_real_is_not_a_probability():
    """2.0 is a positive real and is not a probability."""
    assert not is_subtype(S("PositiveReal"), S("Probability"))


def test_probability_and_positive_real_meet_at_non_negative_real():
    assert join(S("Probability"), S("PositiveReal")) == S("NonNegativeReal")


def test_positive_natural_inhabits_both_natural_and_positive_real():
    assert is_subtype(S("PositiveNatural"), S("Natural"))
    assert is_subtype(S("PositiveNatural"), S("PositiveReal"))


def test_random_variable_is_not_its_codomain():
    assert not is_subtype(RandomVariableType(S("Real")), S("Real"))
    assert not is_subtype(S("Real"), RandomVariableType(S("Real")))


def test_distribution_is_not_its_support():
    assert not is_subtype(DistributionType(S("Real")), S("Real"))
    assert not is_subtype(S("Real"), DistributionType(S("Real")))


def test_distribution_is_not_a_random_variable():
    assert not is_subtype(DistributionType(S("Real")), RandomVariableType(S("Real")))
    assert not is_subtype(RandomVariableType(S("Real")), DistributionType(S("Real")))


# -- declarations --------------------------------------------------------


def test_untyped_declaration_rejected():
    assert "HML-T401" in codes("param a")


def test_value_outside_declared_type_rejected():
    assert "HML-T402" in codes("const a : Natural = -3")


def test_probability_literal_accepted():
    ok("const a : Probability = 1")


# -- distribution roles --------------------------------------------------


def test_correct_roles_accepted():
    ok(
        "param m : Real\nparam s : PositiveReal\nvar x : RandomVariable[Real]\n"
        "law x ~ Normal(location := m, scale := s)"
    )


def test_variance_role_rejected_with_targeted_message():
    src = (
        "param m : Real\nparam s : PositiveReal\nvar x : RandomVariable[Real]\n"
        "law x ~ Normal(location := m, variance := s)"
    )
    r = compile_source(src)
    d = next(x for x in r.diagnostics.errors if x.code == "HML-T415")
    assert d.correction == "scale := ..."
    assert "variance" in " ".join(d.notes).lower()


def test_mean_role_rejected():
    src = (
        "param m : Real\nparam s : PositiveReal\nvar x : RandomVariable[Real]\n"
        "law x ~ Normal(mean := m, scale := s)"
    )
    assert "HML-T415" in codes(src)


def test_unknown_role_rejected():
    src = (
        "param m : Real\nparam s : PositiveReal\nvar x : RandomVariable[Real]\n"
        "law x ~ Normal(location := m, scale := s, wibble := m)"
    )
    assert "HML-T416" in codes(src)


def test_missing_role_rejected():
    assert "HML-T414" in codes(
        "param m : Real\nvar x : RandomVariable[Real]\nlaw x ~ Normal(location := m)"
    )


def test_scale_must_be_positive():
    """A Real scale is rejected: negative standard deviations are unrepresentable."""
    src = (
        "param m : Real\nparam s : Real\nvar x : RandomVariable[Real]\n"
        "law x ~ Normal(location := m, scale := s)"
    )
    r = compile_source(src)
    d = next(x for x in r.diagnostics.errors if x.code == "HML-T413")
    assert d.expected == "PositiveReal"
    assert d.found == "Real"


def test_unknown_family_rejected():
    assert "HML-T412" in codes("var x : RandomVariable[Real]\nlaw x ~ Gaussian(mu := 1)")


def test_support_must_inhabit_target_type():
    """Beta is supported on [0,1]; a Natural-typed target cannot receive it."""
    assert "HML-T411" in codes(
        "param k : Natural\nprior k ~ Beta(alpha := 1, beta := 1)"
    )


def test_binomial_support_matches_natural_target():
    ok(
        "param theta : Probability\nobs n : Natural = 10\nobs k : Natural = 7\n"
        "prior theta ~ Beta(alpha := 1, beta := 1)\n"
        "likelihood k | theta ~ Binomial(trials := n, prob := theta)"
    )


# -- conflation prohibitions --------------------------------------------


def test_arithmetic_on_a_distribution_rejected():
    assert "HML-T430" in codes("var d : Distribution[Real]\ndef y := d + 1")


def test_comparing_a_distribution_to_a_value_rejected():
    assert "HML-T428" in codes("var d : Distribution[Real]\nrequire d > 1")


def test_giving_a_law_to_a_distribution_rejected():
    assert "HML-T410" in codes(
        "var d : Distribution[Real]\nparam s : PositiveReal\nparam m : Real\n"
        "law d ~ Normal(location := m, scale := s)"
    )


def test_implication_requires_propositions():
    assert "HML-T421" in codes("param a : Real\nparam b : Real\nrequire a => b")


def test_require_needs_a_proposition():
    assert "HML-T404" in codes("param a : Real\nrequire a")


# -- dimensions ----------------------------------------------------------


def test_kinetic_energy_dimension():
    r = ok(
        "param m : Quantity[Mass]\nparam v : Quantity[Length / Time]\n"
        "def e := 0.5 * m * v^2\n"
        "check dimension e = Mass * Length^2 / Time^2"
    )
    assert any(o.kind == "dimension" for o in r.obligations)


def test_wrong_asserted_dimension_rejected():
    assert "HML-D504" in codes(
        "param m : Quantity[Mass]\nparam v : Quantity[Length / Time]\n"
        "def e := 0.5 * m * v^2\n"
        "check dimension e = Mass * Length^3 / Time^2"
    )


def test_adding_incompatible_dimensions_rejected():
    assert "HML-D502" in codes(
        "param m : Quantity[Mass]\nparam l : Quantity[Length]\ndef bad := m + l"
    )


def test_comparing_incompatible_dimensions_rejected():
    assert "HML-D502" in codes(
        "param m : Quantity[Mass]\nparam l : Quantity[Length]\nrequire m > l"
    )


def test_multiplying_dimensions_is_allowed():
    ok("param m : Quantity[Mass]\nparam l : Quantity[Length]\ndef p := m * l")


def test_symbolic_exponent_on_a_dimensional_quantity_rejected():
    assert "HML-D505" in codes(
        "param m : Quantity[Mass]\nparam n : Real\ndef bad := m ^ n"
    )


def test_dimension_algebra_is_exact():
    d = Dimension.of(Length=1, Time=-1)
    assert d.power(2) == Dimension.of(Length=2, Time=-2)
    assert (d * d.inverse()).is_dimensionless()
    assert Dimension.of(Length=Fraction(1, 2)).power(2) == Dimension.of(Length=1)


# -- shapes --------------------------------------------------------------


def test_matrix_vector_product_shape():
    from hamiltonian_lang.types import VectorType

    r = ok(
        "index N : Natural\nindex P : Natural\n"
        "obs x : Matrix[Real, N, P]\nparam b : Vector[Real, P]\n"
        "def mu : Vector[Real, N] := x @ b"
    )
    stmt = next(s for s in r.module.statements if getattr(s, "name", None) == "mu")
    assert stmt.body.type_ == VectorType(ScalarType("Real"), "N")


def test_inner_dimension_mismatch_rejected():
    assert "HML-T434" in codes(
        "index N : Natural\nindex P : Natural\nindex Q : Natural\n"
        "obs x : Matrix[Real, N, P]\nparam b : Vector[Real, Q]\ndef mu := x @ b"
    )


def test_matmul_on_scalars_rejected():
    assert "HML-T435" in codes("param a : Real\nparam b : Real\ndef c := a @ b")


def test_vector_length_mismatch_rejected():
    assert "HML-T433" in codes(
        "index N : Natural\nindex Q : Natural\n"
        "param a : Vector[Real, N]\nparam b : Vector[Real, Q]\ndef c := a + b"
    )


# -- proof obligations ---------------------------------------------------


def test_positive_parameters_generate_obligations():
    r = ok("param s : PositiveReal")
    assert any("s > 0" in o.description for o in r.obligations)


def test_probability_parameters_generate_bounds_obligations():
    r = ok("param t : Probability")
    assert any("0 <= t <= 1" in o.description for o in r.obligations)


def test_constraints_are_recorded_as_obligations_and_not_discharged():
    r = ok("var x : Real\nvar y : Real\nrequire x + y >= 10")
    o = next(o for o in r.obligations if o.kind == "constraint")
    assert o.description == "x + y >= 10"
    assert o.discharged_by is None, "v0 must not claim to have proved anything"
