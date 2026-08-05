"""Conservative, endpoint-specific mathematical-equivalence scoring.

Why this package exists
-----------------------
The project's only deterministic equivalence oracle was the canonical content
hash. It is sound in one direction -- equal hashes mean the same object -- and was
being read in both: an unequal hash was treated as *wrongness*. That reading is
correct for ACQ0, where exact recovery of the reference object **is** the
definition of semantic preservation, and wrong for H1/H2, where a mathematically
equivalent encoding with a different shape is not a wrong answer. Scoring such a
candidate ``DISPROVED`` would bias both hypotheses downward, against the project's
own thesis. See CONF-003 in
``docs/evaluation/CONSTITUTIONAL_INTEGRATION_DECISIONS.md``.

The two rules that shape every decision here
--------------------------------------------
1. **No false-positive equivalences.** A false positive silently declares a wrong
   answer right and corrupts every number computed downstream. A false negative
   only costs coverage. When in doubt the answer is ``INCONCLUSIVE``.
2. **Unsupported and inconclusive are never failures.** Converting "I could not
   tell" into "wrong" is the same defect being fixed, pointed the other way.
   :data:`~.status.NEGATIVE_STATUSES` names the only two statuses an aggregate may
   read as wrongness.

Usage::

    from hamiltonian_lang.equivalence import EquivalenceScorer, Endpoint

    report = EquivalenceScorer().compare(reference_hml, candidate_hml,
                                         endpoint=Endpoint.ENCODING_EQUIVALENCE)
    if report.status is EquivalenceStatus.VERIFIED_EQUIVALENT:
        ...

This package does not modify, wrap or replace ACQ0's exact-preservation scoring in
``evaluation/syntax_gate/``. ``Endpoint.ACQ0_EXACT_PRESERVATION`` reproduces that
rule here so the difference between the two endpoints is explicit and testable.
"""

from __future__ import annotations

from .adjudication import AdjudicationItem, AdjudicationQueue
from .endpoints import AnswerSpec, verify_answer
from .guards import run_guards
from .matching import Alignment, Env, Pairing, Residual, align, skeleton, strict_match
from .scorer import ComparisonReport, EquivalenceScorer
from .search import search_disagreement, varies_with
from .status import (
    ANSWER_METHODS,
    CERTIFYING_METHODS,
    EQUIVALENCE_PROTOCOL_VERSION,
    NEGATIVE_STATUSES,
    REFUTING_METHODS,
    SEARCH_ONLY_METHODS,
    Assumption,
    Certificate,
    Counterexample,
    Endpoint,
    EquivalenceResult,
    EquivalenceStatus,
    NonEquivalenceProof,
    NoRefutation,
    SemanticLossNote,
    Tier,
    TierOutcome,
    register_certifying_method,
)
from .symbolic import compare_expressions
from .sympy_bridge import SYMPY_AVAILABLE, TranslationContext, collect_declared_types

__all__ = [
    "EQUIVALENCE_PROTOCOL_VERSION",
    "SYMPY_AVAILABLE",
    "EquivalenceScorer",
    "ComparisonReport",
    "Endpoint",
    "EquivalenceStatus",
    "EquivalenceResult",
    "Tier",
    "TierOutcome",
    "Assumption",
    "Certificate",
    "NonEquivalenceProof",
    "Counterexample",
    "NoRefutation",
    "SemanticLossNote",
    "CERTIFYING_METHODS",
    "REFUTING_METHODS",
    "ANSWER_METHODS",
    "SEARCH_ONLY_METHODS",
    "NEGATIVE_STATUSES",
    "register_certifying_method",
    "AnswerSpec",
    "verify_answer",
    "AdjudicationItem",
    "AdjudicationQueue",
    "Alignment",
    "Env",
    "Pairing",
    "Residual",
    "align",
    "skeleton",
    "strict_match",
    "run_guards",
    "compare_expressions",
    "search_disagreement",
    "varies_with",
    "TranslationContext",
    "collect_declared_types",
]
