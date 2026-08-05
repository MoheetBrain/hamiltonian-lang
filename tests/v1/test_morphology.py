"""Phase 4 — semantic morphology.

Two things are being tested, and they are the same thing seen from opposite sides:

* a role **resolves** when it has been declared for that concept, with a type and a
  semantics — ``Normal.density``;
* a role **raises** when it has not, however plausible the string looks —
  ``SomeArbitraryConcept.density``, and, more pointedly, ``LogNormal.density`` in a
  morphology where ``Normal.density`` is already declared.

The second half of the file is the estimation family, where ``procedure``, ``estimator``,
``estimate`` and ``estimand`` are four distinct roles and no pair substitutes. "The estimate
is unbiased" has to fail, and it fails here.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.v1.morphology import (
    ESTIMATION_TYPES,
    PROPERTY_CARRIERS,
    ROLE_INTENT,
    ROLE_PREREQUISITES,
    DuplicateDeclarationError,
    EstimationRole,
    MissingPrerequisiteError,
    Morphology,
    MorphologyError,
    Role,
    RoleDeclaration,
    RoleTypeError,
    UndeclaredRoleError,
    UnknownConceptError,
    UnknownPropertyError,
    UnknownRoleError,
    attribute_property,
    carriers_of,
    check_substitution,
    may_substitute,
)
from hamiltonian_lang.v1.registry import (
    ClaimStatus,
    Concept,
    ConceptRegistry,
    Lifecycle,
    Parameter,
    Provenance,
)

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def a_concept(
    canonical_id: str,
    *,
    status: Lifecycle = Lifecycle.ADMITTED,
    **overrides: object,
) -> Concept:
    fields: dict[str, object] = {
        "canonical_id": canonical_id,
        "namespace": "hml.v1.statistics",
        "version": "0.1.0",
        "type_signature": "Real * PositiveReal -> Distribution[Real]",
        "domain": "Real * PositiveReal",
        "codomain": "Distribution[Real]",
        "formal_definition": (
            f"The {canonical_id} law on the real line, with location mu and scale sigma."
        ),
        "provenance": Provenance(proposed_by="tests", proposed_at="2026-08-05"),
        "parameters": (
            Parameter(name="mu", type="Real", role="location"),
            Parameter(name="sigma", type="PositiveReal", role="scale"),
        ),
        "admission_status": status,
    }
    fields.update(overrides)
    return Concept(**fields)  # type: ignore[arg-type]


def a_registry(*names: str) -> ConceptRegistry:
    return ConceptRegistry([a_concept(name) for name in names])


def with_normal_density() -> tuple[Morphology, ConceptRegistry]:
    """A morphology where ``Normal`` admits a density and nothing else does.

    ``LogNormal`` and ``SomeArbitraryConcept`` are registered and admitted, so any failure
    to resolve their density is about the *declaration*, never about the concept being
    unknown.
    """
    registry = a_registry("Normal", "LogNormal", "SomeArbitraryConcept")
    morphology = Morphology(registry)
    morphology.declare_role(
        "Normal",
        Role.MEASURE,
        "Measure[Real]",
        "Lebesgue measure on the real line",
        status=ClaimStatus.PROVED,
    )
    morphology.declare_role(
        "Normal",
        Role.DENSITY,
        "Real -> NonNegativeReal",
        "the Radon-Nikodym derivative of the Normal law with respect to Lebesgue measure",
        status=ClaimStatus.PROVED,
    )
    morphology.declare_role(
        "Normal",
        Role.LOGDENSITY,
        "Real -> Real",
        "the logarithm of the declared density, finite on the whole line",
        status=ClaimStatus.PROVED,
    )
    morphology.declare_role(
        "Normal",
        Role.LAW,
        "Distribution[Real]",
        "the Gaussian law itself",
        status=ClaimStatus.PROVED,
    )
    return morphology, registry


# ---------------------------------------------------------------------------
# Roles are a closed, documented set
# ---------------------------------------------------------------------------


def test_the_family_roles_are_exactly_the_specified_fourteen() -> None:
    assert {role.value for role in Role} == {
        "law",
        "density",
        "logdensity",
        "sample",
        "parameter",
        "property",
        "predicate",
        "transform",
        "inverse",
        "measure",
        "estimator",
        "estimand",
        "proof",
        "counterexample",
    }


def test_every_role_states_what_it_means() -> None:
    """A role with no stated meaning is a suffix."""
    assert set(ROLE_INTENT) == set(Role)
    assert all(text.strip() for text in ROLE_INTENT.values())


# ---------------------------------------------------------------------------
# Resolution is by declaration, never by string
# ---------------------------------------------------------------------------


def test_normal_density_resolves() -> None:
    morphology, _ = with_normal_density()

    declaration = morphology.resolve_path("Normal.density")
    assert declaration.role is Role.DENSITY
    assert declaration.concept_id == "Normal"
    assert declaration.type_signature == "Real -> NonNegativeReal"
    assert "Radon-Nikodym" in declaration.semantics
    assert declaration.path == "Normal.density"

    assert morphology.resolve("Normal", Role.DENSITY) == declaration
    assert morphology.resolve("Normal", "density") == declaration
    assert morphology.has("Normal", Role.DENSITY)


def test_an_arbitrary_concept_does_not_get_a_density() -> None:
    """The rejection this module exists for."""
    morphology, registry = with_normal_density()
    assert registry.get("SomeArbitraryConcept").may_be_cited()

    with pytest.raises(UndeclaredRoleError) as excinfo:
        morphology.resolve_path("SomeArbitraryConcept.density")

    message = str(excinfo.value)
    assert "not declared" in message
    assert "not derived by string rule" in message
    assert not morphology.has("SomeArbitraryConcept", Role.DENSITY)


def test_declaring_a_role_for_one_concept_gives_it_to_no_other() -> None:
    """`Normal.density` existing does not make `LogNormal.density` exist.

    A suffix engine would answer both. This one answers only what was declared.
    """
    morphology, _ = with_normal_density()
    assert morphology.has("Normal", Role.DENSITY)
    with pytest.raises(UndeclaredRoleError):
        morphology.resolve_path("LogNormal.density")
    assert morphology.roles_of("LogNormal") == ()


def test_a_registered_concept_starts_with_no_roles_at_all() -> None:
    registry = a_registry("Cauchy")
    morphology = Morphology(registry)
    assert morphology.roles_of("Cauchy") == ()
    for role in Role:
        assert not morphology.has("Cauchy", role)
        with pytest.raises(UndeclaredRoleError):
            morphology.resolve("Cauchy", role)


def test_a_role_outside_the_closed_set_is_unknown() -> None:
    morphology, _ = with_normal_density()
    with pytest.raises(UnknownRoleError):
        morphology.resolve("Normal", "variance")
    with pytest.raises(UnknownRoleError):
        morphology.resolve_path("Normal.densities")
    assert not morphology.has("Normal", "variance")


@pytest.mark.parametrize("path", ["Normal", "Normal.density.log", "", ".density", "Normal."])
def test_a_malformed_role_path_is_refused(path: str) -> None:
    morphology, _ = with_normal_density()
    with pytest.raises(MorphologyError):
        morphology.resolve_path(path)


def test_resolution_consults_the_declaration_table_and_nothing_else() -> None:
    """No name is split, extended or matched against a pattern anywhere in resolution."""
    morphology, registry = with_normal_density()
    registry.add(a_concept("NormalDensity"))  # a name a string rule would love
    with pytest.raises(UndeclaredRoleError):
        morphology.resolve_path("NormalDensity.density")


# ---------------------------------------------------------------------------
# Declaration is itself checked
# ---------------------------------------------------------------------------


def test_a_role_cannot_be_declared_for_a_concept_that_is_not_registered() -> None:
    morphology = Morphology(a_registry("Normal"))
    with pytest.raises(UnknownConceptError):
        morphology.declare_role("Imaginary", Role.LAW, "Distribution[Real]", "a law")


def test_a_role_cannot_be_resolved_on_a_concept_that_is_not_admitted() -> None:
    registry = ConceptRegistry([a_concept("Draft", status=Lifecycle.PROPOSED)])
    morphology = Morphology(registry)
    morphology.declare_role("Draft", Role.LAW, "Distribution[Real]", "a provisional law")
    with pytest.raises(UnknownConceptError) as excinfo:
        morphology.resolve_path("Draft.law")
    assert "admitted" in str(excinfo.value)


def test_a_role_cannot_be_resolved_on_a_concept_that_is_not_registered() -> None:
    morphology = Morphology(a_registry("Normal"))
    with pytest.raises(UnknownConceptError):
        morphology.resolve_path("Nowhere.law")


def test_a_declaration_needs_a_type_and_a_semantics() -> None:
    with pytest.raises(MorphologyError):
        RoleDeclaration("Normal", Role.LAW, "", "the Gaussian law")
    with pytest.raises(MorphologyError) as excinfo:
        RoleDeclaration("Normal", Role.LAW, "Distribution[Real]", "   ")
    assert "suffix" in str(excinfo.value)


def test_a_role_may_not_be_declared_twice() -> None:
    morphology, _ = with_normal_density()
    with pytest.raises(DuplicateDeclarationError):
        morphology.declare_role("Normal", Role.DENSITY, "Real -> Real", "a second density")


def test_a_density_needs_the_measure_it_is_taken_with_respect_to() -> None:
    """Derivation is relational: a density is a derivative with respect to something."""
    assert ROLE_PREREQUISITES[Role.DENSITY] == frozenset({Role.MEASURE})
    morphology = Morphology(a_registry("Cauchy"))
    with pytest.raises(MissingPrerequisiteError) as excinfo:
        morphology.declare_role(
            "Cauchy", Role.DENSITY, "Real -> NonNegativeReal", "the Cauchy density"
        )
    assert "measure" in str(excinfo.value)


def test_a_logdensity_needs_a_density() -> None:
    morphology = Morphology(a_registry("Cauchy"))
    with pytest.raises(MissingPrerequisiteError):
        morphology.declare_role(
            "Cauchy", Role.LOGDENSITY, "Real -> Real", "the log of the Cauchy density"
        )


def test_an_inverse_needs_a_transform() -> None:
    morphology = Morphology(a_registry("Normal"))
    with pytest.raises(MissingPrerequisiteError):
        morphology.declare_role(
            "Normal", Role.INVERSE, "Real -> Real", "the inverse of the transform"
        )
    morphology.declare_role("Normal", Role.TRANSFORM, "Real -> Real", "standardisation")
    inverse = morphology.declare_role(
        "Normal", Role.INVERSE, "Real -> Real", "the inverse of standardisation"
    )
    assert inverse.path == "Normal.inverse"


def test_a_realising_concept_must_itself_be_admitted() -> None:
    registry = ConceptRegistry(
        [a_concept("Normal"), a_concept("Draft", status=Lifecycle.PROPOSED)]
    )
    morphology = Morphology(registry)
    with pytest.raises(UnknownConceptError) as excinfo:
        morphology.declare_role(
            "Normal",
            Role.SAMPLE,
            "Sample[Real]",
            "a draw from the Gaussian law",
            realised_by="Draft",
        )
    assert "admitted" in str(excinfo.value)


def test_the_family_view_lists_only_what_was_declared() -> None:
    morphology, _ = with_normal_density()
    family = morphology.family("Normal")
    assert family.roles == (Role.DENSITY, Role.LAW, Role.LOGDENSITY, Role.MEASURE)
    assert Role.DENSITY in family
    assert Role.SAMPLE not in family
    with pytest.raises(UndeclaredRoleError):
        family.get(Role.SAMPLE)
    assert "Normal.density" in family.render()


# ---------------------------------------------------------------------------
# The estimation family — four distinct roles
# ---------------------------------------------------------------------------


def test_procedure_estimator_estimate_and_estimand_are_four_roles() -> None:
    assert len({member.value for member in EstimationRole}) == len(list(EstimationRole))
    assert ESTIMATION_TYPES[EstimationRole.PROCEDURE] == "EstimationProcedure"
    assert ESTIMATION_TYPES[EstimationRole.ESTIMATOR] == (
        "Function[Sample -> ParameterSpace]"
    )
    assert ESTIMATION_TYPES[EstimationRole.ESTIMATE] == "ParameterSpace"
    assert set(ESTIMATION_TYPES) == set(EstimationRole)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (a, b)
        for a in (
            EstimationRole.PROCEDURE,
            EstimationRole.ESTIMATOR,
            EstimationRole.ESTIMATE,
        )
        for b in (
            EstimationRole.PROCEDURE,
            EstimationRole.ESTIMATOR,
            EstimationRole.ESTIMATE,
        )
        if a is not b
    ],
)
def test_estimator_estimate_and_procedure_cannot_be_interchanged(
    source: EstimationRole, target: EstimationRole
) -> None:
    allowed, reason = may_substitute(source, target)
    assert not allowed
    assert reason
    with pytest.raises(RoleTypeError):
        check_substitution(source, target)


def test_a_role_stands_for_itself_and_nothing_else() -> None:
    for role in EstimationRole:
        allowed, _ = may_substitute(role, role)
        assert allowed
        check_substitution(role, role)


def test_a_shared_type_is_not_a_shared_meaning() -> None:
    """`estimate` and `estimand` are both ParameterSpace-typed, and still do not substitute."""
    assert (
        ESTIMATION_TYPES[EstimationRole.ESTIMATE]
        == ESTIMATION_TYPES[EstimationRole.ESTIMAND]
    )
    with pytest.raises(RoleTypeError):
        check_substitution(EstimationRole.ESTIMATE, EstimationRole.ESTIMAND)
    with pytest.raises(RoleTypeError):
        check_substitution(EstimationRole.ESTIMAND, EstimationRole.ESTIMATE)


def test_the_estimate_is_unbiased_is_a_type_error() -> None:
    """The sentence has to fail somewhere. It fails here."""
    with pytest.raises(RoleTypeError) as excinfo:
        attribute_property("unbiased", EstimationRole.ESTIMATE)

    message = str(excinfo.value)
    assert "unbiased" in message
    assert "estimator" in message
    assert "single number" in message

    # and it is a genuine TypeError, not a lint-level complaint
    assert isinstance(excinfo.value, TypeError)


def test_unbiasedness_belongs_to_the_estimator() -> None:
    attribute_property("unbiased", EstimationRole.ESTIMATOR)
    assert carriers_of("unbiased") == frozenset({EstimationRole.ESTIMATOR})


def test_unbiasedness_is_not_a_property_of_the_procedure_either() -> None:
    with pytest.raises(RoleTypeError):
        attribute_property("unbiased", EstimationRole.PROCEDURE)


def test_algorithmic_properties_belong_to_the_procedure() -> None:
    attribute_property("terminates", EstimationRole.PROCEDURE)
    for wrong in (
        EstimationRole.ESTIMATOR,
        EstimationRole.ESTIMATE,
        EstimationRole.ESTIMAND,
    ):
        with pytest.raises(RoleTypeError):
            attribute_property("terminates", wrong)


def test_identifiability_belongs_to_the_estimand() -> None:
    attribute_property("identifiable", EstimationRole.ESTIMAND)
    with pytest.raises(RoleTypeError) as excinfo:
        attribute_property("identifiable", EstimationRole.ESTIMATOR)
    assert "estimand" in str(excinfo.value)


def test_consistency_is_a_limit_and_a_number_has_none() -> None:
    attribute_property("consistent", EstimationRole.ESTIMATOR)
    with pytest.raises(RoleTypeError) as excinfo:
        attribute_property("consistent", EstimationRole.ESTIMATE)
    assert "limit" in str(excinfo.value)


def test_an_undeclared_property_is_refused_rather_than_allowed() -> None:
    with pytest.raises(UnknownPropertyError):
        carriers_of("vibes")
    with pytest.raises(UnknownPropertyError):
        attribute_property("vibes", EstimationRole.ESTIMATOR)


def test_every_declared_property_names_at_least_one_carrier() -> None:
    assert PROPERTY_CARRIERS
    for name, carriers in PROPERTY_CARRIERS.items():
        assert carriers, f"{name} is declared with no carrier"
        assert carriers <= set(EstimationRole)
