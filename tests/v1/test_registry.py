"""Phase 2 — the typed concept registry.

The registry's job is to refuse things: colliding handles, citations of concepts that are
not admitted, cycles, and documents that do not match
``spec/concept_registry.schema.json``. These tests are written against those refusals.
"""

from __future__ import annotations

import json

import pytest

from hamiltonian_lang.v1.epistemic import Justification
from hamiltonian_lang.v1.registry import (
    CLAIM_JUSTIFICATION,
    LIFECYCLE_TRANSITIONS,
    REGISTRY_VERSION,
    SCHEMA_PATH,
    TERMINAL_STATES,
    AdmissionRecord,
    AliasCollisionError,
    BackendSupport,
    Claim,
    ClaimStatus,
    ComputationBackend,
    ComputationMethod,
    Concept,
    ConceptRegistry,
    CounterexampleRecord,
    DependencyCycleError,
    DuplicateConceptError,
    Lifecycle,
    LifecycleError,
    Parameter,
    Provenance,
    RegistryError,
    Relation,
    RelationKind,
    SchemaValidationError,
    UnadmittedDependencyError,
    UnknownConceptError,
    claim_discharges_goal,
    validate_document,
)

# ---------------------------------------------------------------------------
# Builders. Kept local to the file so that the fixtures a test relies on are visible
# beside it, and so that concurrent work in tests/v1 cannot change them underneath.
# ---------------------------------------------------------------------------


def concept(
    canonical_id: str,
    *,
    status: Lifecycle = Lifecycle.PROPOSED,
    aliases: tuple[str, ...] = (),
    dependencies: tuple[str, ...] = (),
    **overrides: object,
) -> Concept:
    fields: dict[str, object] = {
        "canonical_id": canonical_id,
        "namespace": "hml.v1.test",
        "version": "0.1.0",
        "type_signature": "Real * PositiveReal -> Distribution[Real]",
        "domain": "Real * PositiveReal",
        "codomain": "Distribution[Real]",
        "formal_definition": (
            "The Gaussian law on the real line with location mu and scale sigma."
        ),
        "provenance": Provenance(proposed_by="tests", proposed_at="2026-08-05"),
        "parameters": (
            Parameter(name="mu", type="Real", role="location"),
            Parameter(name="sigma", type="PositiveReal", role="scale"),
        ),
        "admission_status": status,
        "aliases": aliases,
        "dependencies": dependencies,
    }
    fields.update(overrides)
    return Concept(**fields)  # type: ignore[arg-type]


def admitted(canonical_id: str, **overrides: object) -> Concept:
    return concept(canonical_id, status=Lifecycle.ADMITTED, **overrides)


# ---------------------------------------------------------------------------
# The record types track the schema
# ---------------------------------------------------------------------------


def test_concept_fields_are_exactly_the_schema_properties() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_properties = set(schema["$defs"]["concept"]["properties"])
    dataclass_fields = set(Concept.__dataclass_fields__)
    assert dataclass_fields == schema_properties


def test_required_schema_fields_have_no_default() -> None:
    """A field the schema requires must not be silently defaultable."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    required = set(schema["$defs"]["concept"]["required"])
    # `parameters` and `admission_status` are required by the schema but are safe to
    # default (an empty parameter list and `proposed` are both meaningful). Everything
    # else the schema requires has to be supplied by the author.
    must_be_supplied = required - {"parameters", "admission_status"}
    for name in must_be_supplied:
        field = Concept.__dataclass_fields__[name]
        assert field.default is field.default_factory, (
            f"{name} is required by the schema but has a default"
        )


def test_canonical_id_pattern_is_enforced() -> None:
    for bad in ("2Sigma", "has-hyphen", "has space", "", "has.dot"):
        with pytest.raises(RegistryError):
            concept(bad)


def test_claim_status_maps_onto_the_frozen_epistemic_contract() -> None:
    assert CLAIM_JUSTIFICATION[ClaimStatus.PROVED] is Justification.PROOF
    assert CLAIM_JUSTIFICATION[ClaimStatus.TESTED] is Justification.EVIDENCE
    assert CLAIM_JUSTIFICATION[ClaimStatus.CONJECTURED] is Justification.NONE
    assert CLAIM_JUSTIFICATION[ClaimStatus.UNSUPPORTED] is Justification.NONE


def test_only_a_proved_claim_discharges_a_goal() -> None:
    """`tested` is Evidence. Numerical agreement never closes an obligation."""
    assert claim_discharges_goal(ClaimStatus.PROVED)
    assert not claim_discharges_goal(ClaimStatus.TESTED)
    assert not claim_discharges_goal(ClaimStatus.CONJECTURED)
    assert not claim_discharges_goal(ClaimStatus.UNSUPPORTED)


def test_undischarged_claim_serialises_an_explicit_null() -> None:
    """`null` means NOT established, so it is written rather than omitted."""
    doc = Claim(statement="p", status=ClaimStatus.CONJECTURED).to_json()
    assert "discharged_by" in doc
    assert doc["discharged_by"] is None


# ---------------------------------------------------------------------------
# Handles
# ---------------------------------------------------------------------------


def test_lookup_by_canonical_id_and_by_alias() -> None:
    registry = ConceptRegistry()
    normal = registry.add(admitted("Normal", aliases=("Gaussian", "gauss")))

    assert registry.get("Normal") is normal
    assert registry.by_alias("Gaussian") is normal
    assert registry.lookup("gauss") is normal
    assert registry.lookup("Normal") is normal
    assert "Normal" in registry


def test_a_canonical_id_is_not_an_alias() -> None:
    registry = ConceptRegistry([admitted("Normal", aliases=("Gaussian",))])
    with pytest.raises(UnknownConceptError):
        registry.by_alias("Normal")


def test_unknown_handles_raise() -> None:
    registry = ConceptRegistry([admitted("Normal")])
    with pytest.raises(UnknownConceptError):
        registry.get("Cauchy")
    with pytest.raises(UnknownConceptError):
        registry.lookup("Cauchy")
    assert registry.find("Cauchy") is None


def test_duplicate_canonical_id_is_refused() -> None:
    registry = ConceptRegistry([admitted("Normal")])
    with pytest.raises(DuplicateConceptError):
        registry.add(concept("Normal"))


def test_two_concepts_may_not_share_an_alias() -> None:
    registry = ConceptRegistry([admitted("Normal", aliases=("Bell",))])
    with pytest.raises(AliasCollisionError):
        registry.add(concept("Laplace", aliases=("Bell",)))


def test_an_alias_may_not_shadow_another_concepts_canonical_id() -> None:
    registry = ConceptRegistry([admitted("Normal")])
    with pytest.raises(AliasCollisionError):
        registry.add(concept("Laplace", aliases=("Normal",)))


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_lifecycle_walk_proposed_to_admitted() -> None:
    registry = ConceptRegistry([concept("Normal")])
    assert registry.get("Normal").admission_status is Lifecycle.PROPOSED
    registry.transition("Normal", Lifecycle.DEFINED)
    registry.transition("Normal", Lifecycle.CHECKED)
    registry.transition("Normal", Lifecycle.ADMITTED, admitted_at="2026-08-05")
    updated = registry.get("Normal")
    assert updated.admission_status is Lifecycle.ADMITTED
    assert updated.provenance.admitted_at == "2026-08-05"


def test_lifecycle_may_not_skip_a_stage() -> None:
    registry = ConceptRegistry([concept("Normal")])
    with pytest.raises(LifecycleError):
        registry.transition("Normal", Lifecycle.ADMITTED)
    with pytest.raises(LifecycleError):
        registry.transition("Normal", Lifecycle.CHECKED)


@pytest.mark.parametrize("terminal", sorted(TERMINAL_STATES, key=lambda s: s.value))
def test_terminal_states_have_no_outgoing_edge(terminal: Lifecycle) -> None:
    assert LIFECYCLE_TRANSITIONS[terminal] == frozenset()


def test_a_rejection_cannot_be_walked_back() -> None:
    registry = ConceptRegistry([concept("Normal")])
    registry.transition("Normal", Lifecycle.REJECTED, rejected_reason="no compression")
    assert registry.get("Normal").provenance.rejected_reason == "no compression"
    for target in Lifecycle:
        with pytest.raises(LifecycleError):
            registry.transition("Normal", target)


def test_only_an_admitted_concept_may_be_cited() -> None:
    registry = ConceptRegistry(
        [concept("Draft"), admitted("Settled"), concept("Gone", status=Lifecycle.REJECTED)]
    )
    assert registry.may_be_cited("Settled")
    assert not registry.may_be_cited("Draft")
    assert not registry.may_be_cited("Gone")
    assert not registry.may_be_cited("Absent")
    assert [c.canonical_id for c in registry.admitted] == ["Settled"]


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def test_a_concept_may_not_be_checked_while_a_dependency_is_unadmitted() -> None:
    registry = ConceptRegistry(
        [concept("Base"), concept("Derived", dependencies=("Base",))]
    )
    registry.transition("Derived", Lifecycle.DEFINED)
    with pytest.raises(UnadmittedDependencyError):
        registry.transition("Derived", Lifecycle.CHECKED)

    registry.transition("Base", Lifecycle.DEFINED)
    registry.transition("Base", Lifecycle.CHECKED)
    registry.transition("Base", Lifecycle.ADMITTED)
    registry.transition("Derived", Lifecycle.CHECKED)
    assert registry.get("Derived").admission_status is Lifecycle.CHECKED


def test_a_missing_dependency_is_not_quietly_tolerated() -> None:
    registry = ConceptRegistry([concept("Derived", dependencies=("Nowhere",))])
    with pytest.raises(UnknownConceptError):
        registry.check_dependencies("Derived")
    with pytest.raises(UnknownConceptError):
        registry.validate()


def test_dependency_order_is_topological() -> None:
    registry = ConceptRegistry(
        [
            admitted("Measure"),
            admitted("Density", dependencies=("Measure",)),
            admitted("LogDensity", dependencies=("Density",)),
        ]
    )
    order = registry.dependency_order("LogDensity")
    assert order == ("Measure", "Density", "LogDensity")
    assert registry.build_order().index("Measure") < registry.build_order().index("Density")
    registry.validate()


def test_a_cyclic_dependency_is_rejected_at_insertion() -> None:
    """The highest-value dependency case: a cycle is never repaired by reading further."""
    registry = ConceptRegistry([concept("Alpha", dependencies=("Beta",))])
    with pytest.raises(DependencyCycleError) as excinfo:
        registry.add(concept("Beta", dependencies=("Alpha",)))
    assert "cycle" in str(excinfo.value)
    # the rejected concept must not have been left behind
    assert registry.find("Beta") is None
    assert len(registry) == 1


def test_a_longer_cycle_is_rejected_and_named() -> None:
    registry = ConceptRegistry(
        [
            concept("Alpha", dependencies=("Beta",)),
            concept("Beta", dependencies=("Gamma",)),
        ]
    )
    with pytest.raises(DependencyCycleError) as excinfo:
        registry.add(concept("Gamma", dependencies=("Alpha",)))
    message = str(excinfo.value)
    assert "Alpha" in message and "Beta" in message and "Gamma" in message


def test_self_dependency_is_rejected() -> None:
    registry = ConceptRegistry()
    with pytest.raises(DependencyCycleError):
        registry.add(concept("Ouroboros", dependencies=("Ouroboros",)))


def test_a_cyclic_document_is_rejected_on_load() -> None:
    """A cycle assembled outside the registry is caught by whole-document validation."""
    alpha = concept("Alpha", dependencies=("Beta",))
    beta = concept("Beta", dependencies=("Alpha",))
    document = {
        "registry_version": REGISTRY_VERSION,
        "concepts": [alpha.to_json(), beta.to_json()],
    }
    validate_document(document)  # the cycle is legal JSON; the schema cannot see it
    with pytest.raises(DependencyCycleError):
        ConceptRegistry.from_json(document)


def test_validate_rejects_an_admitted_concept_citing_an_unadmitted_one() -> None:
    draft = concept("Draft")
    citing = admitted("Citing", dependencies=("Draft",))
    document = {
        "registry_version": REGISTRY_VERSION,
        "concepts": [draft.to_json(), citing.to_json()],
    }
    with pytest.raises(UnadmittedDependencyError):
        ConceptRegistry.from_json(document)


# ---------------------------------------------------------------------------
# JSON round-trip and schema validation
# ---------------------------------------------------------------------------


def _fully_populated() -> Concept:
    """One concept exercising every optional branch of the schema."""
    return Concept(
        canonical_id="LocationScaleFamily",
        namespace="hml.v1.statistics",
        version="0.2.1",
        type_signature="Distribution[Real] * Real * PositiveReal -> Distribution[Real]",
        domain="Distribution[Real] * Real * PositiveReal",
        codomain="Distribution[Real]",
        formal_definition=(
            "The law of mu + sigma * Z, where Z follows the given standard law, mu is the "
            "location and sigma the scale."
        ),
        provenance=Provenance(
            proposed_by="tests",
            proposed_at="2026-08-05T09:00:00Z",
            source="spec/v1/semantic_objects.yaml",
            admitted_at="2026-08-05T09:30:00Z",
        ),
        parameters=(
            Parameter(name="standard", type="Distribution[Real]", role="standard_law"),
            Parameter(name="mu", type="Real", role="location"),
            Parameter(name="sigma", type="PositiveReal", role="scale", optional=False),
        ),
        admission_status=Lifecycle.ADMITTED,
        aliases=("LocationScale", "shift_scale_family"),
        constraints=("sigma > 0",),
        invariants=(
            Claim(
                statement="the family is closed under affine maps",
                status=ClaimStatus.PROVED,
                evidence="closure under composition of affine maps",
                discharged_by="proofs/location_scale_closure",
            ),
            Claim(statement="every member has the same shape", status=ClaimStatus.TESTED),
        ),
        equivalences=(
            Relation(
                other="AffineImageOfStandardLaw",
                kind=RelationKind.EQUIVALENT_TO,
                status=ClaimStatus.CONJECTURED,
                conditions=("sigma > 0",),
            ),
        ),
        implications=(
            Relation(
                other="ScaleFamily",
                kind=RelationKind.GENERALISES,
                status=ClaimStatus.TESTED,
            ),
        ),
        counterexamples=(
            CounterexampleRecord(
                refutes="every location-scale family has a mean",
                witness="the Cauchy location-scale family",
                verified=True,
            ),
        ),
        proof_obligations=(
            Claim(statement="sigma > 0 on the whole domain", status=ClaimStatus.CONJECTURED),
        ),
        computation_methods=(
            ComputationMethod(
                method="affine transform of the standard law",
                backend=ComputationBackend.SYMPY,
                exact=True,
            ),
            ComputationMethod(
                method="monte carlo",
                backend=ComputationBackend.PYTHON,
                exact=False,
            ),
        ),
        backend_support={
            "stan": BackendSupport(
                supported=True, losses=("no symbolic scale",), verified_by_toolchain=False
            ),
            "lean": BackendSupport(supported=False),
        },
        dependencies=(),
        compresses=("mu + sigma * Z with Z standard",),
        admission_report=AdmissionRecord(
            registry_search_performed=True,
            equality_matches=(),
            equivalence_matches=("AffineImageOfStandardLaw",),
            renaming_matches=(),
            specialisation_of=(),
            generalisation_of=("ScaleFamily",),
            type_valid=True,
            definition_present=True,
            constraints_verified=True,
            obligations_generated=2,
            examples_tested=3,
            examples_passed=3,
            counterexamples_tested=1,
            compression_demonstrated=True,
            verdict=Lifecycle.ADMITTED,
        ),
    )


def test_registry_json_round_trips_and_validates_against_the_schema() -> None:
    registry = ConceptRegistry(concepts=[_fully_populated(), admitted("Normal")])

    document = registry.to_json()  # validates against the schema on the way out
    validate_document(document)  # and explicitly, so the test states what it checks

    restored = ConceptRegistry.from_json(document)
    assert restored == registry
    assert restored.to_json() == document

    original = registry.get("LocationScaleFamily")
    copy = restored.get("LocationScaleFamily")
    assert copy == original
    assert copy.admission_report is not None
    assert copy.admission_report.is_complete()
    assert copy.backend_support["stan"].losses == ("no symbolic scale",)
    assert copy.invariants[0].discharged_by == "proofs/location_scale_closure"
    assert copy.invariants[1].discharged_by is None


def test_registry_survives_a_file_round_trip(tmp_path) -> None:
    registry = ConceptRegistry(concepts=[_fully_populated()])
    path = registry.save(tmp_path / "registry.json")
    reloaded = ConceptRegistry.load(path)
    assert reloaded == registry
    # and the file on disk is a valid registry document in its own right
    validate_document(json.loads(path.read_text(encoding="utf-8")))


def test_schema_validation_rejects_a_bad_document() -> None:
    with pytest.raises(SchemaValidationError):
        validate_document({"registry_version": "x"})  # no `concepts`

    good = ConceptRegistry(concepts=[admitted("Normal")]).to_json()

    bad_status = json.loads(json.dumps(good))
    bad_status["concepts"][0]["admission_status"] = "probably_fine"
    with pytest.raises(SchemaValidationError):
        validate_document(bad_status)

    extra_key = json.loads(json.dumps(good))
    extra_key["concepts"][0]["vibes"] = "good"
    with pytest.raises(SchemaValidationError):
        validate_document(extra_key)

    bad_id = json.loads(json.dumps(good))
    bad_id["concepts"][0]["canonical_id"] = "2Sigma"
    with pytest.raises(SchemaValidationError):
        validate_document(bad_id)


def test_missing_required_field_is_rejected_by_the_schema() -> None:
    document = ConceptRegistry(concepts=[admitted("Normal")]).to_json()
    del document["concepts"][0]["formal_definition"]
    with pytest.raises(SchemaValidationError) as excinfo:
        validate_document(document)
    assert "formal_definition" in str(excinfo.value)


def test_admission_record_reports_what_is_missing() -> None:
    partial = AdmissionRecord(registry_search_performed=True, type_valid=True)
    assert not partial.is_complete()
    assert "compression_demonstrated" in partial.missing_fields()
    assert "verdict" in partial.missing_fields()
    assert "type_valid" not in partial.missing_fields()


def test_an_empty_collection_is_written_as_an_omission() -> None:
    """Absence means unsupported, so an empty container is not written as coverage."""
    document = admitted("Normal").to_json()
    assert "backend_support" not in document
    assert "compresses" not in document
    assert "aliases" not in document
    # the required fields are always present, empty or not
    assert document["parameters"]
    assert document["provenance"]["proposed_by"] == "tests"
