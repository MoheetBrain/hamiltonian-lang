"""Deterministic proof-obligation discharge over an explicitly bounded subset.

Why this package exists
-----------------------
The type checker collects proof obligations and discharges none of them. That is the
correct behaviour for a type checker, and it had one consequence that made an
experiment unrunnable: any module containing ``require`` ended at ``INCONCLUSIVE``, so
``VERIFIED`` was unreachable (CONF-004). H3's primary endpoint is *kernel-verified
completion rate*; an endpoint nothing can reach is not an endpoint.

This package makes ``VERIFIED`` reachable **without** making it easier. Nine narrow
classes are decided soundly; everything else is reported ``UNSUPPORTED``, and an
``UNSUPPORTED`` obligation blocks ``VERIFIED`` exactly as firmly as a failed one. The
subset is the claim, and it is written down in
``docs/architecture/HML_PROCESS_VERIFICATION.md``.

What is decided
---------------
======================================  ====================================================
class                                    decided by
======================================  ====================================================
``literal_refinement_bound``             interval entailment over declared refinement types
``closed_arithmetic_equality``           exact rational evaluation
``closed_inequality``                    exact rational evaluation
``dimension_compatibility``              independent re-derivation from declared types
``declared_signature_conformance``       arity and parameter-type re-check at each call site
``finite_set_membership``                exhaustion over a genuinely finite domain
``logical_consistency``                  closed propositional evaluation; interval feasibility
``symbolic_identity``                    SymPy, restricted operators and declared assumptions
``numerical_counterexample``             refutation by a fixed grid — never a proof
======================================  ====================================================

What is refused
---------------
Quantification over an infinite domain, distributional claims, integrals and limits,
anything involving a ``RandomVariable`` or ``Distribution``, dimensioned quantities in
numeric comparisons, indexing, and the matrix product. Each returns ``UNSUPPORTED``
with the reason, and each blocks ``VERIFIED``.

Usage::

    from hamiltonian_lang.verification.obligations import verify_source
    outcome = verify_source(open("model.hml").read())
    print(outcome.verdict, outcome.substantive)
"""

from __future__ import annotations

from .checkers import (
    DEFAULT_CHECKERS,
    Checker,
    ClosedArithmeticEqualityChecker,
    ClosedInequalityChecker,
    DeclaredSignatureChecker,
    DimensionCompatibilityChecker,
    FiniteSetMembershipChecker,
    Judgement,
    LiteralRefinementBoundChecker,
    LogicalConsistencyChecker,
    NumericalCounterexampleChecker,
    ObligationTask,
    SymbolicIdentityChecker,
)
from .domains import Domain, Interval, domain_of_type
from .engine import (
    ENGINE_VERSION,
    LOWERING_TARGETS,
    SEMANTIC_PRESERVING_TARGETS,
    GlobalVerdict,
    VerificationOutcome,
    discharge,
    verify_result,
    verify_source,
)
from .evaluate import Environment, Undecidable, build_environment, evaluate, interval_of
from .federation import ObligationDischargeVerifier
from .records import (
    OBLIGATION_SCHEMA_VERSION,
    SUPPORTED_CLASSES,
    ObligationClass,
    ObligationRecord,
    ObligationStatus,
    SemanticLossRecord,
    SourceSpan,
    Witness,
)

__all__ = [
    "OBLIGATION_SCHEMA_VERSION",
    "ENGINE_VERSION",
    "SUPPORTED_CLASSES",
    "SEMANTIC_PRESERVING_TARGETS",
    "LOWERING_TARGETS",
    "ObligationStatus",
    "ObligationClass",
    "ObligationRecord",
    "SemanticLossRecord",
    "SourceSpan",
    "Witness",
    "GlobalVerdict",
    "VerificationOutcome",
    "Judgement",
    "ObligationTask",
    "Checker",
    "DEFAULT_CHECKERS",
    "ClosedArithmeticEqualityChecker",
    "ClosedInequalityChecker",
    "DeclaredSignatureChecker",
    "DimensionCompatibilityChecker",
    "FiniteSetMembershipChecker",
    "LiteralRefinementBoundChecker",
    "LogicalConsistencyChecker",
    "NumericalCounterexampleChecker",
    "SymbolicIdentityChecker",
    "Domain",
    "Interval",
    "Environment",
    "Undecidable",
    "domain_of_type",
    "build_environment",
    "evaluate",
    "interval_of",
    "discharge",
    "verify_result",
    "verify_source",
    "ObligationDischargeVerifier",
]
