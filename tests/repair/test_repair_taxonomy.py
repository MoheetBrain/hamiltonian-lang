"""The repair error taxonomy: total, exact where claimed, and never guessing."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hamiltonian_lang.context_broker.taxonomy import (
    CODE_PATTERN,
    ERROR_CLASS_BY_CODE,
    FAMILY_ERROR_CLASS,
    ErrorClass,
    classify,
    is_well_formed_code,
)

REPO = Path(__file__).resolve().parents[2]

#: The twelve classes fixed by the H3 programme specification.
EXPECTED_CLASSES = {
    "SYNTAX", "RESOLUTION", "ARITY", "TYPE", "REFINEMENT", "ROLE", "SCOPE",
    "DIMENSION", "EPISTEMIC", "OBLIGATION", "SEMANTIC_EQUIVALENCE", "BACKEND",
}


def test_taxonomy_is_exactly_the_twelve_specified_classes() -> None:
    assert {c.name for c in ErrorClass} == EXPECTED_CLASSES
    assert {c.value for c in ErrorClass} == EXPECTED_CLASSES


def test_every_code_in_the_exact_table_is_well_formed() -> None:
    for code in ERROR_CLASS_BY_CODE:
        assert CODE_PATTERN.match(code), code


def test_exact_table_only_names_codes_the_compiler_actually_emits() -> None:
    """A classification for a code that does not exist is a classification of nothing."""
    emitted: set[str] = set()
    for path in (REPO / "src" / "hamiltonian_lang").rglob("*.py"):
        emitted.update(re.findall(r"HML-[A-Z]\d{3}", path.read_text(encoding="utf-8")))
    missing = sorted(set(ERROR_CLASS_BY_CODE) - emitted)
    assert not missing, f"classified but never emitted by the compiler: {missing}"


def test_arity_and_refinement_are_not_collapsed_into_type() -> None:
    """The whole reason this taxonomy exists rather than reusing the code prefix.

    ``HML-T471`` and ``HML-T472`` share the ``T`` prefix and need entirely different
    context. If they classify the same, retrieval cannot tell them apart.
    """
    assert classify("HML-T471").error_class is ErrorClass.ARITY
    assert classify("HML-T472").error_class is ErrorClass.REFINEMENT
    assert classify("HML-T440").error_class is ErrorClass.TYPE


def test_the_five_hard_coded_codes_classify_exactly() -> None:
    expected = {
        "HML-T471": ErrorClass.ARITY,
        "HML-T472": ErrorClass.REFINEMENT,
        "HML-T415": ErrorClass.ROLE,
        "HML-T440": ErrorClass.TYPE,
        "HML-N306": ErrorClass.RESOLUTION,
    }
    for code, want in expected.items():
        result = classify(code)
        assert result.error_class is want, code
        assert result.exact, f"{code} must be a read-the-source classification, not a guess"


def test_family_fallback_is_marked_inexact() -> None:
    """A code classified by prefix alone must not claim the confidence of a verified one."""
    code = "HML-T499"
    assert code not in ERROR_CLASS_BY_CODE
    result = classify(code)
    assert result.error_class is ErrorClass.TYPE
    assert result.exact is False
    assert result.well_formed is True


@pytest.mark.parametrize("code", ["", "T471", "HML-T47", "HML-471", "hml-t471", "nonsense"])
def test_malformed_codes_are_not_well_formed_and_get_no_class(code: str) -> None:
    result = classify(code)
    assert result.well_formed is False
    assert result.error_class is None
    assert result.supported is False
    assert is_well_formed_code(code) is False


def test_unknown_family_is_unsupported_rather_than_guessed() -> None:
    """The letter is not in the family table, so no class may be assigned."""
    assert "Z" not in FAMILY_ERROR_CLASS
    result = classify("HML-Z999")
    assert result.well_formed is True
    assert result.error_class is None
    assert result.supported is False


def test_classification_is_deterministic() -> None:
    for code in ("HML-T471", "HML-Q123", "junk"):
        assert classify(code) == classify(code)
