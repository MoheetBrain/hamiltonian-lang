"""Domain mathematics, deliberately outside the trusted reasoning kernel.

Three V0 libraries — algebra, probability, calculus — reachable only through the existing
certificate boundary. Nothing here is a kernel inference rule, nothing here can register a
trusted checker, and nothing here has a ``trust_me_this_is_true`` path.

The contract is in :mod:`hamiltonian_lang.libraries.theorem`; the normative specification
is ``docs/hml_v2/MATHEMATICAL_LIBRARY_CONTRACT.md``.

Why these live inside `hamiltonian_lang` for now: Gold-10 exposes exactly three library
capabilities. A separate distribution would buy versioning and orchestration cost against
almost no scientific value at that size. The theorem API is the seam along which they can
be split later, if a corpus ever shows the domains growing independently.
"""

from __future__ import annotations

from .theorem import (
    THEOREMS,
    InstantiationError,
    LibraryTheorem,
    SideCondition,
    TheoremVariable,
    VerificationKind,
    axioms,
    describe,
    instantiate,
    theorem_ids,
)

# Imported for the side effect of registering their theorems. Kept here rather than in
# `theorem.py` so the contract module stays free of domain content and no import cycle
# can form: the domain modules import the contract, never the reverse.
from . import algebra, calculus, probability  # noqa: E402,F401  isort:skip

__all__ = [
    "THEOREMS",
    "InstantiationError",
    "LibraryTheorem",
    "SideCondition",
    "TheoremVariable",
    "VerificationKind",
    "axioms",
    "describe",
    "instantiate",
    "theorem_ids",
    "algebra",
    "calculus",
    "probability",
]
