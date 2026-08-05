"""HML-PHASE-FG-001 F3 — four surfaces over one canonical object.

Four deterministic renderer/parser pairs (A, B, C, D) that all project the *same*
canonical Hamiltonian object. The point of the phase is that the surface becomes an
experimentally comparable variable: if any candidate carried more mathematical
information than the others, a later model tournament would be measuring the leak
rather than the syntax.

Read ``core`` first. It holds the interface, the frozen supported subset, and the
information-parity normaliser that the fairness tests are built on.
"""

from __future__ import annotations

from .core import (
    CANDIDATES,
    FROZEN_SUBSET_VERSION,
    SurfaceParseError,
    SyntaxCandidate,
    UnsupportedConstruct,
    candidate,
    declared_content,
    recover,
    round_trip,
    validate_supported,
)

__all__ = [
    "CANDIDATES",
    "FROZEN_SUBSET_VERSION",
    "SurfaceParseError",
    "SyntaxCandidate",
    "UnsupportedConstruct",
    "candidate",
    "declared_content",
    "recover",
    "round_trip",
    "validate_supported",
]
