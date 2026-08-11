"""The canonical typed semantic state: claims, candidates, branches, goals, obligations.

Why this package exists
-----------------------
HML's reasoning layer is organised around a *module* — a text the compiler checks once.
The research corpus is organised around a *transition* — a state, an action, and the state
that results. Those are different objects, and the Semantic Firewall experiment showed
exactly where the second one has no home: a neutral trajectory carries candidates and
branches that current HML can represent nowhere, so six of its thirty acceptance fixtures
were recorded ``CURRENT_HML_NOT_EXPRESSIBLE``.

This module supplies the missing objects. It is deliberately **not** new surface syntax:
``docs/04`` §6.14 makes the canonical typed state primary and HML text one rendering of it,
and the builder brief forbids adding syntax merely to support import. So the state lives
here as data, the verifier in :mod:`.verify` decides transitions over it, and a renderer can
come later once the objects have stopped moving.

Two rules govern everything below
---------------------------------
**Status is computed, never asserted.** A ``Candidate`` cannot be constructed VERIFIED and
a ``Branch`` cannot be constructed JOINED. Both statuses are reachable only through the
verifier, for the same reason ``DerivationStatus.VERIFIED`` has no surface syntax: a
generator that can write down its own verdict is not being checked.

**UNKNOWN is not TRUE, and it is not FALSE either.** Every judgement here is three-valued.
A transition whose evidence is UNKNOWN is ``UNRESOLVED`` — it is neither accepted nor
reported as a detected error, because calling ignorance a violation is as wrong as calling
it a proof.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "ClaimStatus",
    "CandidateStatus",
    "BranchStatus",
    "ObligationState",
    "Verdict",
    "ErrorClass",
    "Claim",
    "Candidate",
    "Branch",
    "Goal",
    "Obligation",
    "EvidenceRecord",
    "Action",
    "SemanticState",
    "Transition",
]


class ClaimStatus(StrEnum):
    """What is known about a proposition in the deductive state.

    ``UNKNOWN`` is a **value**, not an import failure. A neutral record that says "the
    status of this claim is not determined" is well-formed and must round-trip; refusing
    to represent it would force the adapter to either invent a status or reject a
    perfectly legitimate record. It is what makes the UNRESOLVED verdict reachable at all.

    ``UNRESOLVED`` is kept distinct: it records that adjudication ran and did not settle,
    whereas ``UNKNOWN`` records that nothing is claimed either way.
    """

    GIVEN = "GIVEN"
    ASSUMED = "ASSUMED"
    DERIVED = "DERIVED"
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"
    UNRESOLVED = "UNRESOLVED"
    UNKNOWN = "UNKNOWN"


class CandidateStatus(StrEnum):
    """The generic candidate lifecycle (SF-R06).

    ``PROPOSED`` → ``UNVERIFIED`` → ``VERIFIED`` | ``REJECTED``.

    One object for every domain. There is deliberately no ``root_candidate``,
    ``geometry_candidate`` or ``probability_candidate``: a candidate is "a mathematical
    object somebody proposed, together with the constraints it must satisfy", and that
    shape does not vary by subject. Specialising it per domain would put domain knowledge
    in the state model, which is exactly where this project keeps refusing to put it.
    """

    PROPOSED = "PROPOSED"
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    #: Representable, for the same reason ClaimStatus.UNKNOWN is. Not a lifecycle stage:
    #: it has no outgoing transitions, so a candidate whose status is unknown cannot be
    #: promoted from that position — it must first be determined.
    UNKNOWN = "UNKNOWN"


#: Transitions the lifecycle permits. Anything else is rejected by
#: :func:`Candidate.may_transition_to`, so a candidate cannot jump from PROPOSED straight
#: to VERIFIED without passing the promotion verifier, and a settled candidate cannot be
#: quietly reopened.
_CANDIDATE_TRANSITIONS: dict[CandidateStatus, frozenset[CandidateStatus]] = {
    CandidateStatus.PROPOSED: frozenset(
        {CandidateStatus.UNVERIFIED, CandidateStatus.VERIFIED, CandidateStatus.REJECTED}
    ),
    CandidateStatus.UNVERIFIED: frozenset(
        {CandidateStatus.VERIFIED, CandidateStatus.REJECTED}
    ),
    CandidateStatus.VERIFIED: frozenset(),
    CandidateStatus.REJECTED: frozenset(),
    CandidateStatus.UNKNOWN: frozenset(),
}


class BranchStatus(StrEnum):
    """A case-analysis branch. ``JOINED`` is verifier-owned (SF-R08)."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    JOINED = "JOINED"
    ABANDONED = "ABANDONED"
    UNKNOWN = "UNKNOWN"


class ObligationState(StrEnum):
    OPEN = "OPEN"
    DISCHARGED = "DISCHARGED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class GoalStatus(StrEnum):
    """What is being proved, and whether it has been (D-059).

    Added because ``Goal.status`` was the **only** record status in the model that was a
    bare ``str``: claims, candidates, branches and obligations all validated theirs against
    an enum at the import boundary, and goals validated nothing. Measured at `136cdb9`, a
    goal accepted all twenty probed values including ``''``, ``'open'``, ``'DISCHARGED '``
    and ``'NOT_A_STATUS_AT_ALL'``, while every other kind refused all sixteen foreign ones.

    The two members the corpus actually uses are ``OPEN`` (63) and ``DISCHARGED`` (63).
    ``UNKNOWN`` is here for the same reason it is on every other status enum: a status that
    cannot be read must be representable as unread rather than guessed.
    """

    OPEN = "OPEN"
    DISCHARGED = "DISCHARGED"
    UNKNOWN = "UNKNOWN"


class Verdict(StrEnum):
    """The three-valued outcome of checking one transition.

    ``UNRESOLVED`` is not a soft ``INVALID``. The firewall fixtures make the distinction
    load-bearing: each invariant family ships LEGAL / ILLEGAL / **UNKNOWN** cases, and the
    UNKNOWN case must be neither accepted nor counted as a detected corruption.
    """

    VALID = "VALID"
    INVALID = "INVALID"
    UNRESOLVED = "UNRESOLVED"


class ErrorClass(StrEnum):
    """Named violation classes, matching the neutral fixtures' ``expected_error_class``."""

    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    SCOPE_VIOLATION = "SCOPE_VIOLATION"
    PRECONDITION_VIOLATION = "PRECONDITION_VIOLATION"
    OBLIGATION_VIOLATION = "OBLIGATION_VIOLATION"
    CANDIDATE_PROMOTION = "CANDIDATE_PROMOTION"
    INVALID_BRANCH_JOIN = "INVALID_BRANCH_JOIN"
    WARRANT_VIOLATION = "WARRANT_VIOLATION"
    EPISTEMIC_VIOLATION = "EPISTEMIC_VIOLATION"
    GOAL_DISCHARGE = "GOAL_DISCHARGE"
    TYPE_DOMAIN_VIOLATION = "TYPE_DOMAIN_VIOLATION"


@dataclass(frozen=True)
class Claim:
    """One proposition in the deductive state, with its ancestry and scope."""

    id: str
    proposition: str
    status: ClaimStatus = ClaimStatus.GIVEN
    scope: str = "global"
    domain: str | None = None
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class Candidate:
    """A proposed mathematical object and the constraints it must satisfy.

    ``constraint_ids`` is the load-bearing field. A candidate is only ever "a solution to
    *these* constraints", and promotion must check **every** one of them — checking a
    subset is how a spurious root gets promoted because it satisfied the equation somebody
    remembered to test.
    """

    id: str
    proposition: str
    status: CandidateStatus = CandidateStatus.PROPOSED
    scope: str = "global"
    #: IDs of the original constraints this candidate must satisfy.
    constraint_ids: tuple[str, ...] = ()
    #: Where it came from: a guess, a solver, a source span, an earlier derivation.
    origin: str | None = None
    #: Claims this candidate's proposal rests on.
    dependencies: tuple[str, ...] = ()
    #: Evidence id that promoted or rejected it. Set by the verifier only.
    evidence_id: str | None = None
    #: The verifier's recorded outcome, for provenance.
    verification_result: str | None = None

    def may_transition_to(self, target: CandidateStatus) -> bool:
        return target in _CANDIDATE_TRANSITIONS[self.status]


@dataclass(frozen=True)
class Branch:
    """One case of a case analysis, with its local assumption and local conclusion."""

    id: str
    #: The case predicate — the assumption that holds inside this branch and nowhere else.
    predicate: str
    status: BranchStatus = BranchStatus.OPEN
    scope: str = "global"
    #: What was concluded inside the branch. Local until a certified join.
    conclusion: str | None = None
    #: The partition this branch belongs to, when one is declared.
    partition_id: str | None = None


@dataclass(frozen=True)
class Goal:
    id: str
    proposition: str
    status: GoalStatus = GoalStatus.OPEN
    scope: str = "global"


@dataclass(frozen=True)
class Obligation:
    """Proof debt. Field names follow the neutral schema exactly.

    ``status`` rather than ``state``, and ``mandatory`` rather than an inferred severity:
    the adapter's job is to carry the corpus's vocabulary, not to improve on it. Renaming
    here would have been invisible until the round-trip test caught it, which is what it
    did.
    """

    id: str
    proposition: str
    status: ObligationState = ObligationState.OPEN
    mandatory: bool = True
    origin: str | None = None
    dependencies: tuple[str, ...] = ()
    discharge_evidence_id: str | None = None


@dataclass(frozen=True)
class EvidenceRecord:
    """A neutral evidence record as it arrives from the corpus.

    ``trusted`` is **provenance, not permission**. It records that the producer was a
    trusted one; it does not by itself license anything, and :mod:`.verify` never reads it
    as authority. Acceptance requires the structural checks — that the record exists, that
    it supports the rule being applied, that its premises are among the action's declared
    dependencies, and that its status is VALID. A field a generator can set must never be
    the thing that makes a generator's output true.
    """

    id: str
    kind: str
    status: str = "UNKNOWN"
    trusted: bool = False
    supports_rule: str | None = None
    premise_ids: tuple[str, ...] = ()
    #: Kind-specific payload: checked_constraints, branch_ids, source_span_hash, ...
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Action:
    """One proposed transition: the five orthogonal axes of ``docs/04`` §2."""

    id: str
    operation: str
    summary: str = ""
    output_id: str | None = None
    dependencies: tuple[str, ...] = ()
    preconditions: tuple[dict[str, Any], ...] = ()
    obligations_created: tuple[dict[str, Any], ...] = ()
    #: The neutral schema records each discharge as ``{id, evidence_id}``, not a bare id.
    obligations_discharged: tuple[dict[str, Any], ...] = ()
    #: {"input_domains": {claim_id: domain}, "output_domain": domain}
    typing: dict[str, Any] = field(default_factory=dict)
    #: {"kind", "rule", "evidence_id"}
    warrant: dict[str, Any] = field(default_factory=dict)
    goal_effect: dict[str, Any] = field(default_factory=dict)
    scope_effect: dict[str, Any] = field(default_factory=dict)
    branch_effect: dict[str, Any] = field(default_factory=dict)
    candidate_effect: dict[str, Any] = field(default_factory=dict)
    epistemic_effect: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticState:
    """A complete typed mathematical state. The canonical machine object."""

    claims: dict[str, Claim] = field(default_factory=dict)
    candidates: dict[str, Candidate] = field(default_factory=dict)
    branches: dict[str, Branch] = field(default_factory=dict)
    goals: dict[str, Goal] = field(default_factory=dict)
    obligations: dict[str, Obligation] = field(default_factory=dict)
    active_scopes: tuple[str, ...] = ("global",)

    def visible(self, claim_id: str) -> bool:
        """Whether ``claim_id`` may be cited from the currently active scopes.

        Scope is enforced by membership rather than by ordering: a fact established inside
        a frame that is no longer active is not visible, which is what stops a branch-local
        conclusion from leaking into the global state without a join.
        """
        claim = self.claims.get(claim_id)
        if claim is None:
            return False
        return claim.scope in self.active_scopes


@dataclass(frozen=True)
class Transition:
    """``state_before --action--> state_after``, with the evidence offered for it."""

    case_id: str
    action: Action
    state_before: SemanticState
    state_after: SemanticState
    evidence: dict[str, EvidenceRecord] = field(default_factory=dict)
    schema_version: str = "semantic-firewall-case-0.1.0"
    #: Provenance, never semantics: dataset row, hashes, level, category.
    source: dict[str, Any] = field(default_factory=dict)
