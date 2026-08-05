"""The record schema must make an unsupported claim impossible to construct.

Every one of these tests is a guard against a specific way a verifier degrades into
theatre: a discharge outside the subset, a failure with no witness, a skip with no
reason. If the schema stops refusing them, the report stops meaning anything, so each
refusal is asserted rather than assumed.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.verification.obligations.records import (
    SUPPORTED_CLASSES,
    ObligationClass,
    ObligationMode,
    ObligationRecord,
    ObligationStatus,
    SourceSpan,
    Witness,
    evidence_hash,
)


def _record(**kw) -> ObligationRecord:
    base = {
        "obligation_id": "OBL-000-abcdef01",
        "span": SourceSpan("t.hml", 3, 0, 3, 10),
        "obligation_class": ObligationClass.CLOSED_ARITHMETIC_EQUALITY,
        "checker": "closed_arithmetic_equality",
        "checker_version": "hml-obl-1.0.0",
        "status": ObligationStatus.DISCHARGED,
        "statement": "2 + 3 = 5",
    }
    base.update(kw)
    return ObligationRecord(**base)  # type: ignore[arg-type]


def test_out_of_subset_can_never_be_discharged() -> None:
    with pytest.raises(ValueError, match="outside the supported subset"):
        _record(obligation_class=ObligationClass.OUT_OF_SUBSET)


def test_supported_classes_are_exactly_the_nine_named_classes() -> None:
    assert ObligationClass.OUT_OF_SUBSET not in SUPPORTED_CLASSES
    assert len(SUPPORTED_CLASSES) == 9
    assert SUPPORTED_CLASSES == frozenset(ObligationClass) - {ObligationClass.OUT_OF_SUBSET}


def test_a_discharge_may_not_carry_a_witness() -> None:
    with pytest.raises(ValueError, match="cannot coexist with DISCHARGED"):
        _record(witness=Witness("x", evaluated="1 != 1"))


def test_failed_without_a_witness_is_refused() -> None:
    """'Not accepted' and 'false' are different facts, and only one has a witness."""
    with pytest.raises(ValueError, match="FAILED requires a witness"):
        _record(status=ObligationStatus.FAILED)


def test_unsupported_must_name_the_missing_capability() -> None:
    with pytest.raises(ValueError, match="must say which capability is missing"):
        _record(status=ObligationStatus.UNSUPPORTED, detail="   ")


def test_a_witness_must_carry_a_binding_or_an_evaluation() -> None:
    with pytest.raises(ValueError, match="non-acceptance, not a refutation"):
        Witness("the checker did not accept it")


def test_a_witness_must_describe_what_it_refutes() -> None:
    with pytest.raises(ValueError, match="must describe what it refutes"):
        Witness("  ", evaluated="1 = 2")


def test_every_required_field_survives_serialisation() -> None:
    record = _record(
        mode=ObligationMode.SATISFIABLE,
        evidence={"left": "5", "right": "5"},
        dependencies=("OBL-001-00000000",),
        detail="evaluated exactly",
    )
    payload = record.to_dict()
    required = {
        "obligation_id",
        "span",
        "class",
        "checker",
        "checker_version",
        "status",
        "evidence",
        "witness",
        "dependencies",
    }
    assert required <= set(payload)
    assert payload["mode"] == "satisfiable"
    assert payload["span"]["line"] == 3
    assert payload["dependencies"] == ["OBL-001-00000000"]


def test_evidence_hash_is_stable_and_order_independent() -> None:
    a = evidence_hash({"b": 2, "a": [1, {"z": 1, "y": 2}]})
    b = evidence_hash({"a": [1, {"y": 2, "z": 1}], "b": 2})
    assert a == b


def test_the_four_statuses_have_no_synonyms() -> None:
    assert {str(s) for s in ObligationStatus} == {
        "DISCHARGED",
        "FAILED",
        "UNSUPPORTED",
        "INCONCLUSIVE",
    }
