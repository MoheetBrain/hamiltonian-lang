"""The Diagnostic Context Broker: the ladder, the four statuses, and no invention."""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.context_broker import (
    ContextItem,
    ContextQuery,
    ContextStatus,
    DiagnosticContextBroker,
    ErrorClass,
    FacetKind,
    Provenance,
    RetrievalStage,
    SemanticIndex,
    build_index,
)
from hamiltonian_lang.context_broker.broker import (
    DETERMINISTIC_CODE_NOTE,
    DETERMINISTIC_FACETS,
)
from hamiltonian_lang.improvement.diagnostics import (
    DiagnosticCategory,
    SourceSpan,
    StructuredDiagnostic,
    adapt,
)

# --- fixtures: real broken programs, compiled by the real compiler ---------------

SOURCES: dict[str, str] = {
    "HML-T471": "module M\ndef f(a : Real, b : Real) : Real := a + b\ndef g : Real := f(1.0)\n",
    "HML-T472": (
        "module M\ndef f(a : Real, b : PositiveReal) : Real := a + b\n"
        "def c : Real := f(1.0, -2.0)\n"
    ),
    "HML-T415": (
        "module M\nparam s : PositiveReal\nvar X : Real\n"
        "law X ~ Normal(location := 0.0, variance := s)\n"
    ),
    "HML-T440": "module M\nparam x : Frobnicator\n",
    "HML-N306": "module M\nparam a : Real\ndef c : Real := wibble(a)\n",
}


def first_diagnostic(source: str, code: str) -> StructuredDiagnostic:
    errors = compile_source(source).diagnostics.errors
    assert errors, f"expected {code} but the source compiled clean"
    match = next((d for d in errors if d.code == code), errors[0])
    assert match.code == code, f"expected {code}, compiler reported {match.code}"
    return adapt(match)


@pytest.fixture(scope="module")
def broker() -> DiagnosticContextBroker:
    return DiagnosticContextBroker()


# --- index integrity -------------------------------------------------------------


def test_every_index_item_has_resolvable_provenance() -> None:
    """The anti-hallucination guarantee. An item whose source cannot be located on disk
    is indistinguishable, in a repair packet, from one that was invented."""
    index = build_index()
    unresolved = index.unresolved_provenance()
    assert not unresolved, [i.provenance.render() for i in unresolved]


def test_index_covers_all_eleven_facets() -> None:
    index = build_index()
    assert set(index.facets()) == {f.value for f in FacetKind}


def test_index_construction_is_deterministic() -> None:
    a, b = build_index(include_examples=False), build_index(include_examples=False)
    assert [i.to_dict() for i in a] == [i.to_dict() for i in b]


def test_provenance_rejects_an_unsourced_origin() -> None:
    with pytest.raises(ValueError, match="module:' or 'file:"):
        Provenance("somewhere", "a table")


def test_context_item_rejects_empty_content() -> None:
    prov = Provenance("module:hamiltonian_lang.types", "SCALARS")
    with pytest.raises(ValueError, match="teaches nothing"):
        ContextItem(facet=FacetKind.TYPE, key="Real", content="   ", provenance=prov)


# --- the four statuses -----------------------------------------------------------


def test_status_context_found(broker: DiagnosticContextBroker) -> None:
    d = first_diagnostic(SOURCES["HML-T415"], "HML-T415")
    result = broker.retrieve(ContextQuery(diagnostic=d, source=SOURCES["HML-T415"]))
    assert result.status is ContextStatus.CONTEXT_FOUND
    assert result.found
    assert result.items


def test_status_query_invalid_for_a_malformed_code(broker: DiagnosticContextBroker) -> None:
    d = StructuredDiagnostic(
        code="not-a-code",
        category=DiagnosticCategory.UNCLASSIFIED,
        source_span=SourceSpan(),
    )
    result = broker.retrieve(ContextQuery(diagnostic=d))
    assert result.status is ContextStatus.QUERY_INVALID
    assert result.reason
    assert result.items == ()


def test_status_query_invalid_for_an_empty_code(broker: DiagnosticContextBroker) -> None:
    d = StructuredDiagnostic(
        code="", category=DiagnosticCategory.UNCLASSIFIED, source_span=SourceSpan()
    )
    result = broker.retrieve(ContextQuery(diagnostic=d))
    assert result.status is ContextStatus.QUERY_INVALID


def test_status_unsupported_error_class(broker: DiagnosticContextBroker) -> None:
    d = StructuredDiagnostic(
        code="HML-Z999",
        category=DiagnosticCategory.UNCLASSIFIED,
        source_span=SourceSpan(),
    )
    result = broker.retrieve(ContextQuery(diagnostic=d))
    assert result.status is ContextStatus.UNSUPPORTED_ERROR_CLASS
    assert "taxonomy" in result.reason


def test_status_no_relevant_context_is_explicit(broker: DiagnosticContextBroker) -> None:
    """The index holds nothing for this code. Saying so is the product."""
    d = StructuredDiagnostic(
        code="HML-P206",
        category=DiagnosticCategory.PARSE,
        source_span=SourceSpan(),
        message="",
    )
    result = broker.retrieve(ContextQuery(diagnostic=d))
    assert result.status is ContextStatus.NO_RELEVANT_CONTEXT
    assert result.items == ()
    assert "invented" in result.reason
    assert result.render().startswith("[NO_RELEVANT_CONTEXT]")


def test_the_four_statuses_are_the_whole_enum() -> None:
    assert {s.name for s in ContextStatus} == {
        "CONTEXT_FOUND",
        "NO_RELEVANT_CONTEXT",
        "QUERY_INVALID",
        "UNSUPPORTED_ERROR_CLASS",
    }


# --- the five hard-coded deterministic mappings ----------------------------------


@pytest.mark.parametrize("code", sorted(DETERMINISTIC_FACETS))
def test_deterministic_codes_answer_from_stage_one(
    broker: DiagnosticContextBroker, code: str
) -> None:
    """No search, and no model call, for a failure whose answer is a dictionary lookup."""
    source = SOURCES[code]
    result = broker.retrieve(
        ContextQuery(diagnostic=first_diagnostic(source, code), source=source)
    )
    assert result.status is ContextStatus.CONTEXT_FOUND
    assert result.stages_used[0] is RetrievalStage.DETERMINISTIC_CODE_MAP
    assert result.deterministic_note == DETERMINISTIC_CODE_NOTE[code]


def test_t471_retrieves_the_programs_own_signature_and_the_arity_rule(
    broker: DiagnosticContextBroker,
) -> None:
    source = SOURCES["HML-T471"]
    result = broker.retrieve(
        ContextQuery(diagnostic=first_diagnostic(source, "HML-T471"), source=source)
    )
    assert result.error_class is ErrorClass.ARITY
    first = result.items[0]
    assert "local" in first.tags
    assert "f(a : Real, b : Real)" in first.content
    assert any(i.facet is FacetKind.RULE_CARD for i in result.items)


def test_t472_retrieves_the_required_refinement_type(
    broker: DiagnosticContextBroker,
) -> None:
    source = SOURCES["HML-T472"]
    result = broker.retrieve(
        ContextQuery(diagnostic=first_diagnostic(source, "HML-T472"), source=source)
    )
    assert result.error_class is ErrorClass.REFINEMENT
    joined = " ".join(i.content for i in result.items)
    assert "PositiveReal" in joined


def test_t415_retrieves_the_named_roles_of_the_offending_family(
    broker: DiagnosticContextBroker,
) -> None:
    source = SOURCES["HML-T415"]
    result = broker.retrieve(
        ContextQuery(diagnostic=first_diagnostic(source, "HML-T415"), source=source)
    )
    assert result.error_class is ErrorClass.ROLE
    joined = " ".join(i.content for i in result.items)
    assert "'variance' is not a parameter role in Normal" in joined
    assert "location : Real, scale : PositiveReal" in joined


def test_t440_retrieves_the_type_vocabulary_first(
    broker: DiagnosticContextBroker,
) -> None:
    source = SOURCES["HML-T440"]
    result = broker.retrieve(
        ContextQuery(diagnostic=first_diagnostic(source, "HML-T440"), source=source,
                     max_items=2)
    )
    assert result.error_class is ErrorClass.TYPE
    assert "complete scalar type vocabulary" in result.items[0].content


def test_n306_retrieves_the_known_function_list_first(
    broker: DiagnosticContextBroker,
) -> None:
    source = SOURCES["HML-N306"]
    result = broker.retrieve(
        ContextQuery(diagnostic=first_diagnostic(source, "HML-N306"), source=source,
                     max_items=2)
    )
    assert result.error_class is ErrorClass.RESOLUTION
    assert "built-in function names are" in result.items[0].content


# --- ladder behaviour ------------------------------------------------------------


def test_max_items_is_respected(broker: DiagnosticContextBroker) -> None:
    source = SOURCES["HML-T415"]
    d = first_diagnostic(source, "HML-T415")
    for n in (1, 2, 5):
        result = broker.retrieve(ContextQuery(diagnostic=d, source=source, max_items=n))
        assert len(result.items) <= n


def test_zero_max_items_is_a_query_fault(broker: DiagnosticContextBroker) -> None:
    d = first_diagnostic(SOURCES["HML-T440"], "HML-T440")
    result = broker.retrieve(ContextQuery(diagnostic=d, max_items=0))
    assert result.status is ContextStatus.QUERY_INVALID


def test_retrieval_is_deterministic(broker: DiagnosticContextBroker) -> None:
    source = SOURCES["HML-T471"]
    d = first_diagnostic(source, "HML-T471")
    a = broker.retrieve(ContextQuery(diagnostic=d, source=source))
    b = broker.retrieve(ContextQuery(diagnostic=d, source=source))
    assert a.to_dict() == b.to_dict()


def test_an_empty_index_yields_no_relevant_context_rather_than_a_guess() -> None:
    """The failure mode this whole design exists to prevent, exercised directly."""
    empty = DiagnosticContextBroker(index=SemanticIndex())
    source = SOURCES["HML-T415"]
    result = empty.retrieve(
        ContextQuery(diagnostic=first_diagnostic(source, "HML-T415"), source=source)
    )
    assert result.status is ContextStatus.NO_RELEVANT_CONTEXT
    assert result.items == ()


def test_every_rendered_item_carries_its_source(broker: DiagnosticContextBroker) -> None:
    source = SOURCES["HML-T415"]
    result = broker.retrieve(
        ContextQuery(diagnostic=first_diagnostic(source, "HML-T415"), source=source)
    )
    rendered = result.render()
    assert rendered.count("source:") == len(result.items)
    assert len(result.provenance()) == len(result.items)


def test_neighbourhood_stage_uses_the_failing_span(
    broker: DiagnosticContextBroker,
) -> None:
    """A code with no deterministic mapping still reaches the source-local names."""
    source = "module M\nparam s : PositiveReal\nvar X : Real\nlaw X ~ Normal(scale := s)\n"
    errors = compile_source(source).diagnostics.errors
    assert errors and errors[0].code == "HML-T414"
    result = broker.retrieve(
        ContextQuery(diagnostic=adapt(errors[0]), source=source)
    )
    assert result.status is ContextStatus.CONTEXT_FOUND
    assert any("Normal declares the roles" in i.content for i in result.items)
