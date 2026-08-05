"""Statuses, evidence types, and the registries that decide who may certify what.

The asymmetry this module exists to enforce
-------------------------------------------
Searching for a counterexample and failing to find one is **not** a proof of
equivalence. That asymmetry is encoded in the *types*, not in a comment:

* :class:`Certificate` is the only object that can support
  ``VERIFIED_EQUIVALENT``, and it refuses to be constructed unless its ``method``
  is in :data:`CERTIFYING_METHODS`.
* :class:`NoRefutation` -- what a counterexample search returns when it finds
  nothing -- is a *different class*. It has no ``method`` field, it is not
  accepted anywhere a certificate is required, and its only boolean property is
  hard-coded to ``False``.
* The counterexample searcher's method id is deliberately absent from
  :data:`CERTIFYING_METHODS`, and :func:`register_certifying_method` refuses to
  add any id in :data:`SEARCH_ONLY_METHODS`.

The other rule, stated once here and enforced by
:meth:`EquivalenceResult.__post_init__`: **an unsupported or inconclusive result
is never a failure.** Turning "I could not tell" into "wrong" is the same error
as turning "different hash" into "wrong", pointed the other way.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "EQUIVALENCE_PROTOCOL_VERSION",
    "EquivalenceStatus",
    "Endpoint",
    "Tier",
    "Assumption",
    "Certificate",
    "NonEquivalenceProof",
    "Counterexample",
    "NoRefutation",
    "SemanticLossNote",
    "TierOutcome",
    "EquivalenceResult",
    "CERTIFYING_METHODS",
    "REFUTING_METHODS",
    "ANSWER_METHODS",
    "SEARCH_ONLY_METHODS",
    "NEGATIVE_STATUSES",
    "register_certifying_method",
]

EQUIVALENCE_PROTOCOL_VERSION = "hml-equivalence-1.0.0"


class EquivalenceStatus(StrEnum):
    """What the scorer concluded. Seven outcomes, none a synonym for another."""

    #: A certifying method established that both sides denote one object.
    VERIFIED_EQUIVALENT = "VERIFIED_EQUIVALENT"
    #: The endpoint answer matches. Says nothing about the encodings.
    VERIFIED_CORRECT_ANSWER = "VERIFIED_CORRECT_ANSWER"
    #: A sound argument shows the two denote different objects.
    VERIFIED_NONEQUIVALENT = "VERIFIED_NONEQUIVALENT"
    #: A concrete witness at which the two disagree was exhibited.
    COUNTEREXAMPLE_FOUND = "COUNTEREXAMPLE_FOUND"
    #: Translating into the checking medium lost something, so no claim is made.
    SEMANTIC_LOSS = "SEMANTIC_LOSS"
    #: The comparison was attempted and did not decide. **Not** a failure.
    INCONCLUSIVE = "INCONCLUSIVE"
    #: The comparison could not be attempted at all. **Not** a failure.
    UNSUPPORTED = "UNSUPPORTED"


#: The statuses a caller may read as "the candidate is wrong". ``INCONCLUSIVE``,
#: ``UNSUPPORTED`` and ``SEMANTIC_LOSS`` are deliberately absent: an aggregate that
#: counts them as failures reintroduces the bias this package was built to remove.
NEGATIVE_STATUSES: frozenset[EquivalenceStatus] = frozenset(
    {
        EquivalenceStatus.VERIFIED_NONEQUIVALENT,
        EquivalenceStatus.COUNTEREXAMPLE_FOUND,
    }
)


class Endpoint(StrEnum):
    """Which question is being asked. The tiers that may certify depend on it.

    ``ACQ0_EXACT_PRESERVATION`` reproduces the *existing* ACQ0 rule -- exact
    recovery of the reference object -- inside this engine so that the difference
    from H1/H2 is explicit and testable. It does not replace, wrap or modify
    ACQ0's own scorer in ``evaluation/syntax_gate/``; that code is untouched.
    """

    #: ACQ0. Only an exact canonical identity counts. Everything else is not
    #: preservation, because reproducing *the same object* is the task.
    ACQ0_EXACT_PRESERVATION = "ACQ0_EXACT_PRESERVATION"
    #: H1/H2 encoding endpoint. Any tier that can certify mathematical
    #: equivalence counts, because a differently-shaped equivalent encoding is
    #: not a wrong answer.
    ENCODING_EQUIVALENCE = "ENCODING_EQUIVALENCE"
    #: H1/H2 answer endpoint. The final answer is what is scored; the shape of
    #: the encoding is reported but does not decide the verdict.
    FINAL_ANSWER = "FINAL_ANSWER"


class Tier(StrEnum):
    TIER0_CANONICAL_IDENTITY = "TIER0_CANONICAL_IDENTITY"
    TIER1_ALPHA_NORMALISATION = "TIER1_ALPHA_NORMALISATION"
    TIER2_SYMBOLIC = "TIER2_SYMBOLIC"
    TIER3_COUNTEREXAMPLE_SEARCH = "TIER3_COUNTEREXAMPLE_SEARCH"
    TIER4_ENDPOINT_ANSWER = "TIER4_ENDPOINT_ANSWER"
    TIER5_ADJUDICATION = "TIER5_ADJUDICATION"
    #: Invariant guards. They run before the tiers and can only refute.
    GUARD = "GUARD"


# ---------------------------------------------------------------------------
# Method registries
# ---------------------------------------------------------------------------

#: Methods permitted to establish ``VERIFIED_EQUIVALENT``. Each is a decision
#: procedure or an exact structural identity -- never a search.
_CERTIFYING: set[str] = {
    "tier0.canonical_content_hash",
    "tier1.alpha_structural_match",
    "tier2.sympy_difference_is_zero",
    "tier2.sympy_relation_proportional",
    "tier2.propositional_tautology",
}

#: Methods permitted to establish ``VERIFIED_NONEQUIVALENT``. Each is a sound
#: argument that the two objects differ, not merely evidence that a check failed.
_REFUTING: set[str] = {
    "guard.declared_types_incomparable",
    "guard.epistemic_kind_differs",
    "guard.epistemic_role_differs",
    "guard.dimension_differs",
    "guard.random_variable_vs_value",
    "guard.objective_direction_differs",
    "guard.quantifier_alternation_differs",
    "guard.conditioning_set_differs",
    "tier2.propositional_countermodel",
}

#: Methods that answer the *endpoint* question. They may support
#: ``VERIFIED_CORRECT_ANSWER`` and nothing else -- a right answer is not a proof
#: that two encodings denote one object.
_ANSWER: set[str] = {
    "tier4.final_answer_match",
}

#: Methods that are searches. A search may exhibit a witness, so it may refute
#: through :class:`Counterexample`; it may never certify. Membership here is a
#: hard block in :func:`register_certifying_method`.
SEARCH_ONLY_METHODS: frozenset[str] = frozenset(
    {
        "tier3.numeric_counterexample",
        "tier3.dependence_witness",
    }
)

CERTIFYING_METHODS: frozenset[str] = frozenset(_CERTIFYING)
REFUTING_METHODS: frozenset[str] = frozenset(_REFUTING | SEARCH_ONLY_METHODS)
ANSWER_METHODS: frozenset[str] = frozenset(_ANSWER)


def register_certifying_method(method: str) -> None:
    """Add a method to the certifying set. Refuses anything that is a search.

    Exists so the block is executable rather than a naming convention: a future
    author who tries to promote the counterexample searcher gets a ``ValueError``,
    not a silently widened oracle.
    """
    global CERTIFYING_METHODS
    if method in SEARCH_ONLY_METHODS:
        raise ValueError(
            f"{method!r} is a search. Failing to find a counterexample is not a "
            f"proof of equivalence, so it cannot certify."
        )
    _CERTIFYING.add(method)
    CERTIFYING_METHODS = frozenset(_CERTIFYING)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Assumption:
    """A side condition the conclusion depends on.

    Sign assumptions are the reason this exists: ``a*x < b`` and ``x < b/a`` are
    equivalent only when ``a > 0``, and an equivalence claim that does not carry
    that condition is false half the time.
    """

    statement: str
    source: str = ""  # "declared type", "assume statement", "derived"

    def __post_init__(self) -> None:
        if not self.statement.strip():
            raise ValueError("an assumption must state what is assumed")

    def to_dict(self) -> dict[str, str]:
        return {"statement": self.statement, "source": self.source}


@dataclass(frozen=True)
class Certificate:
    """Positive evidence that two objects are the same.

    Only a method in :data:`CERTIFYING_METHODS` may build one. This is the type-level
    half of "absence of a counterexample proves nothing".
    """

    method: str
    detail: str
    assumptions: tuple[Assumption, ...] = ()
    witness: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.method not in CERTIFYING_METHODS and self.method not in ANSWER_METHODS:
            raise ValueError(
                f"{self.method!r} is not an approved certifying method; a certificate "
                f"may only be issued by a decision procedure or an exact structural "
                f"identity"
            )
        if not self.detail.strip():
            raise ValueError("a certificate must say what it established and how")

    @property
    def certifies_equivalence(self) -> bool:
        return self.method in CERTIFYING_METHODS

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "detail": self.detail,
            "assumptions": [a.to_dict() for a in self.assumptions],
            "witness": dict(self.witness),
        }


@dataclass(frozen=True)
class NonEquivalenceProof:
    """A sound argument that the two objects differ.

    Distinct from :class:`Counterexample`: this one is structural or decidable,
    the other exhibits a value. Both refute; neither is "a check that failed".
    """

    method: str
    detail: str
    left: str = ""
    right: str = ""
    assumptions: tuple[Assumption, ...] = ()

    def __post_init__(self) -> None:
        if self.method not in REFUTING_METHODS:
            raise ValueError(f"{self.method!r} is not an approved refuting method")
        if not self.detail.strip():
            raise ValueError("a non-equivalence proof must state its argument")

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "detail": self.detail,
            "left": self.left,
            "right": self.right,
            "assumptions": [a.to_dict() for a in self.assumptions],
        }


@dataclass(frozen=True)
class Counterexample:
    """A concrete assignment at which the two sides disagree."""

    method: str
    description: str
    assignment: Mapping[str, str] = field(default_factory=dict)
    left_value: str = ""
    right_value: str = ""

    def __post_init__(self) -> None:
        if self.method not in REFUTING_METHODS:
            raise ValueError(f"{self.method!r} is not an approved refuting method")
        if not self.description.strip():
            raise ValueError("a counterexample must describe what it witnesses")

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "description": self.description,
            "assignment": dict(self.assignment),
            "left_value": self.left_value,
            "right_value": self.right_value,
        }


@dataclass(frozen=True)
class NoRefutation:
    """What a search returns when it finds nothing.

    Deliberately *not* a :class:`Certificate` and deliberately not convertible into
    one. ``certifies_equivalence`` is a constant ``False`` so that a caller which
    reads the property uniformly across evidence objects cannot be misled.
    """

    method: str
    samples_tried: int
    detail: str = ""

    @property
    def certifies_equivalence(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "samples_tried": self.samples_tried,
            "detail": self.detail,
            "certifies_equivalence": False,
        }


@dataclass(frozen=True)
class SemanticLossNote:
    """Something the translation into the checking medium could not preserve."""

    construct: str
    reason: str
    severity: str = "dropped"  # dropped | approximated | weakened

    def to_dict(self) -> dict[str, str]:
        return {"construct": self.construct, "reason": self.reason, "severity": self.severity}


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EquivalenceResult:
    """One tier's or one guard's answer, with the evidence that justifies it.

    ``__post_init__`` is where the invariants live. In particular a
    ``VERIFIED_EQUIVALENT`` without a certificate, or with a certificate issued by
    an answer-only method, is rejected at construction time.
    """

    tier: Tier
    status: EquivalenceStatus
    detail: str = ""
    certificate: Certificate | None = None
    proof: NonEquivalenceProof | None = None
    counterexample: Counterexample | None = None
    no_refutation: NoRefutation | None = None
    semantic_loss: tuple[SemanticLossNote, ...] = ()
    assumptions: tuple[Assumption, ...] = ()
    evidence: Mapping[str, Any] = field(default_factory=dict)
    protocol_version: str = EQUIVALENCE_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        s = self.status
        if s is EquivalenceStatus.VERIFIED_EQUIVALENT:
            if self.certificate is None:
                raise ValueError(
                    "VERIFIED_EQUIVALENT requires a certificate; an equivalence claim "
                    "without one is exactly the false positive this package forbids"
                )
            if not self.certificate.certifies_equivalence:
                raise ValueError(
                    f"{self.certificate.method!r} answers the endpoint question, not the "
                    f"equivalence question; a correct answer does not make two encodings "
                    f"one object"
                )
            if self.counterexample is not None:
                raise ValueError("a counterexample and an equivalence claim cannot both hold")
        if s is EquivalenceStatus.VERIFIED_CORRECT_ANSWER and self.certificate is None:
            raise ValueError("VERIFIED_CORRECT_ANSWER requires the matching evidence")
        if s is EquivalenceStatus.VERIFIED_NONEQUIVALENT and self.proof is None:
            raise ValueError(
                "VERIFIED_NONEQUIVALENT requires a proof. A check that merely failed is "
                "INCONCLUSIVE"
            )
        if s is EquivalenceStatus.COUNTEREXAMPLE_FOUND and self.counterexample is None:
            raise ValueError("COUNTEREXAMPLE_FOUND requires the witness")
        if s is EquivalenceStatus.SEMANTIC_LOSS and not self.semantic_loss:
            raise ValueError("SEMANTIC_LOSS must name what was lost")
        if self.no_refutation is not None and s in NEGATIVE_STATUSES:
            raise ValueError(
                "a search that found nothing cannot support a negative verdict either"
            )

    @property
    def decisive(self) -> bool:
        """Whether the scorer may stop here.

        ``SEMANTIC_LOSS`` is *not* decisive: one tier failing to represent the
        problem faithfully says nothing about whether a later tier can.
        """
        return self.status not in (
            EquivalenceStatus.INCONCLUSIVE,
            EquivalenceStatus.UNSUPPORTED,
            EquivalenceStatus.SEMANTIC_LOSS,
        )

    @property
    def is_negative(self) -> bool:
        return self.status in NEGATIVE_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": str(self.tier),
            "status": str(self.status),
            "detail": self.detail,
            "certificate": self.certificate.to_dict() if self.certificate else None,
            "proof": self.proof.to_dict() if self.proof else None,
            "counterexample": (
                self.counterexample.to_dict() if self.counterexample else None
            ),
            "no_refutation": self.no_refutation.to_dict() if self.no_refutation else None,
            "semantic_loss": [s.to_dict() for s in self.semantic_loss],
            "assumptions": [a.to_dict() for a in self.assumptions],
            "evidence": dict(self.evidence),
            "protocol_version": self.protocol_version,
        }


@dataclass(frozen=True)
class TierOutcome:
    """A tier's result plus how long the scorer spent on it."""

    tier: Tier
    result: EquivalenceResult

    def to_dict(self) -> dict[str, Any]:
        return {"tier": str(self.tier), "result": self.result.to_dict()}


def summarise(outcomes: Sequence[TierOutcome]) -> str:
    return " -> ".join(f"{o.tier}:{o.result.status}" for o in outcomes)
