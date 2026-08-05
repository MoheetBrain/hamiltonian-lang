"""Diagnostic Context Broker — error-conditioned retrieval of project-specific context.

A diagnostic says *what* is wrong. It does not say which project-specific rule, signature
or type should replace the wrong thing. This package supplies that missing half, and it
supplies it from the compiler's own tables, with provenance, or it says it has nothing.

Entry point::

    from hamiltonian_lang.context_broker import ContextQuery, DiagnosticContextBroker

    broker = DiagnosticContextBroker()
    result = broker.retrieve(ContextQuery(diagnostic=structured, source=broken))
    if result.found:
        print(result.render())

Nothing in this package contacts a network or a model. Retrieval is a dictionary lookup
followed by three progressively broader scans of an in-process index.
"""

from __future__ import annotations

from .broker import (
    BROKER_VERSION,
    DETERMINISTIC_CODE_NOTE,
    DETERMINISTIC_FACETS,
    ContextQuery,
    ContextStatus,
    DiagnosticContextBroker,
    RetrievalStage,
    RetrievedContext,
)
from .index import (
    INDEX_VERSION,
    ContextItem,
    FacetKind,
    Provenance,
    SemanticIndex,
    build_index,
    repo_root,
)
from .taxonomy import (
    CODE_PATTERN,
    ERROR_CLASS_BY_CODE,
    FAMILY_ERROR_CLASS,
    TAXONOMY_VERSION,
    Classification,
    ErrorClass,
    classify,
    is_well_formed_code,
)

__all__ = [
    "BROKER_VERSION",
    "CODE_PATTERN",
    "DETERMINISTIC_CODE_NOTE",
    "DETERMINISTIC_FACETS",
    "ERROR_CLASS_BY_CODE",
    "FAMILY_ERROR_CLASS",
    "INDEX_VERSION",
    "TAXONOMY_VERSION",
    "Classification",
    "ContextItem",
    "ContextQuery",
    "ContextStatus",
    "DiagnosticContextBroker",
    "ErrorClass",
    "FacetKind",
    "Provenance",
    "RetrievalStage",
    "RetrievedContext",
    "SemanticIndex",
    "build_index",
    "classify",
    "is_well_formed_code",
    "repo_root",
]
