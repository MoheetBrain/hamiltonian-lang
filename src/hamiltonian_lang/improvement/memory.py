"""Phase 10 — four append-only stores, and the routing that decides which one.

The stores
----------
* **Positive** — first-attempt semantic fidelity, every required verifier passed, no
  unresolved obligation. The cleanest possible evidence and the rarest.
* **Repair** — the first attempt failed, a *structured* diagnostic was issued, exactly
  one repair was attempted, and the repaired form passed the required checks. Two
  repairs is not this store: with two, nothing says which one carried the fix.
* **Hard negative** — a minimal, attributable near-miss. "Minimal" is not a stylistic
  preference; it is the condition under which the example teaches one thing. It is
  encoded as *exactly one* declared near-miss kind plus at least one attributed skill.
* **Quarantine** — everything whose label cannot be trusted.

Routing fails closed
--------------------
An episode that matches none of the first three stores goes to quarantine with
``AMBIGUOUS_LABEL``. The alternative — a fifth, unlabelled bucket, or a default into
"positive" — puts unverified rows where trusted rows live, which is the failure this
whole design is arranged to prevent.

**Quarantine is never training-eligible.** Not by policy, not by convention, and not by
a comment: ``RoutingDecision.__post_init__`` refuses to *represent* an eligible
quarantined outcome at all, ``MemoryRecord.__post_init__`` rejects a quarantined record
marked eligible, ``MemoryStore.append`` rejects it again on the way in, and
``MemoryBank.training_batch`` cannot be asked for the quarantine store at all. Four
independent guards, because one guard is one edit away from being removed.

The router is the only authority on training eligibility
---------------------------------------------------------
Eligibility used to be decided twice: :func:`route` derived it from the facts, and the
episode record carried a caller-supplied ``training_eligible`` flag beside it. Two
authorities over one bit is a defect regardless of whether they currently agree — the
moment they disagree, quarantined data reaches training, and nothing in the record says
which of the two was believed.

There is now one decision. :func:`route` produces it, :class:`RoutingDecision` carries it
together with the evidence for it, and every consumer reads it from there. A caller
cannot supply a competing value: ``episodes.Episode`` derives ``training_eligible`` from
the stored decision and refuses the keyword outright, and :func:`build_record` re-derives
the decision from the facts and refuses one that disagrees.

**Hard negatives require an explicit policy.** A minimal attributable near-miss is
*usable* for training, but training on negatives is a decision about a training regime,
not a fact about the episode. ``route(facts)`` therefore reports a hard negative as
ineligible unless a :class:`TrainingPolicy` that says otherwise is passed in, so the
choice appears at the call site rather than as a default nobody chose.

Deduplication is structural, not semantic-by-similarity
-------------------------------------------------------
Two identifications are needed and they are different:

* **Exact** — SHA-256 of the source text. Byte-identical resubmission.
* **Alpha-equivalent** — the compiler's ``content_hash``, taken over the *nameless*
  canonical form. Renaming a bound variable changes the text and not this hash, which is
  precisely the equivalence a corpus needs.

There is no embedding model here and there is not going to be one as the primary
deduplicator. A nearest-neighbour threshold over vectors decides "same" by a tunable
number, and the tuning would silently change what the corpus contains. The canonical
hash is exact, explainable, and reproducible from source a year from now.

Hypotheses are never mixed
--------------------------
A store is keyed by ``(kind, hypothesis)``. Identical content submitted under H1 and
under H3 lands in two different stores and is **not** deduplicated across them: they are
answers to different questions, and dropping one as a "duplicate" would delete evidence
about one hypothesis because evidence about another arrived first.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from .state import Hypothesis

__all__ = [
    "MemoryStoreKind",
    "TRAINABLE_KINDS",
    "ELIGIBLE_KINDS",
    "QuarantineReason",
    "NearMissKind",
    "VerifierOutcome",
    "TrainingPolicy",
    "DEFAULT_TRAINING_POLICY",
    "ROUTER_ID",
    "RoutableEpisode",
    "RoutingFacts",
    "RoutingDecision",
    "RoutingDisagreement",
    "route",
    "route_episode",
    "MemoryRecord",
    "build_record",
    "routed_summary",
    "AppendStatus",
    "AppendOutcome",
    "MemoryStore",
    "MemoryBank",
    "QuarantineEligibilityError",
    "UnknownVerifierStatus",
    "verifier_outcome_from_status",
    "exact_hash_of",
    "canonical_hash_of",
]


class MemoryStoreKind(StrEnum):
    POSITIVE = "positive"
    REPAIR = "repair"
    HARD_NEGATIVE = "hard_negative"
    QUARANTINE = "quarantine"


#: The three stores from which training data may be drawn. Quarantine is not among them
#: and no code path adds it.
TRAINABLE_KINDS: frozenset[MemoryStoreKind] = frozenset(
    {MemoryStoreKind.POSITIVE, MemoryStoreKind.REPAIR, MemoryStoreKind.HARD_NEGATIVE}
)

#: The stores whose rows may *ever* carry ``training_eligible=True``. Identical to
#: ``TRAINABLE_KINDS`` today and kept separate on purpose: "a store training may draw
#: from" and "a row that may be marked eligible" are different claims, and collapsing
#: them is how a future edit to one silently changes the other.
ELIGIBLE_KINDS: frozenset[MemoryStoreKind] = TRAINABLE_KINDS

#: Identifies the authority that made a routing decision. Stored on every decision so a
#: record can be checked against the code that produced it.
ROUTER_ID = "hamiltonian_lang.improvement.memory.route"


class QuarantineReason(StrEnum):
    """Why a row cannot be trusted. Recorded individually; several may apply."""

    UNSUPPORTED_BACKEND = "unsupported_backend"
    INCONCLUSIVE_VERIFICATION = "inconclusive_verification"
    SEMANTIC_LOSS = "semantic_loss"
    AMBIGUOUS_LABEL = "ambiguous_label"
    POTENTIAL_EVALUATION_CONTAMINATION = "potential_evaluation_contamination"
    MISSING_PROVENANCE = "missing_provenance"
    UNTRUSTED_SYNTHETIC_TRUTH = "untrusted_synthetic_truth"
    #: The hypothesis is ``EXCLUDED``: engineering work, not evidence. Never trainable.
    EXCLUDED_HYPOTHESIS = "excluded_hypothesis"


@dataclass(frozen=True)
class TrainingPolicy:
    """What a *regime* permits, as opposed to what an episode *is*.

    Only one knob today, and it is the one that needs stating. A hard negative is a
    minimal attributable near-miss — genuinely useful, and genuinely a decision about
    how you want to train rather than a property of the row. Defaulting it to eligible
    would put negative examples into every batch because nobody wrote a line to stop it.
    """

    #: When false (the default) a hard negative is stored and is **not** eligible.
    hard_negatives_eligible: bool = False
    #: Free text, recorded on the decision, naming who chose and why.
    rationale: str = "default policy: hard negatives are stored but not trained on"

    def to_dict(self) -> dict[str, Any]:
        return {
            "hard_negatives_eligible": self.hard_negatives_eligible,
            "rationale": self.rationale,
        }


DEFAULT_TRAINING_POLICY = TrainingPolicy()


class NearMissKind(StrEnum):
    """The attributable ways an output can be one step wrong.

    Each names a distinction the type system or the semantics already draws, so that a
    hard negative always teaches a distinction the language actually makes.
    """

    WRONG_ARITY = "wrong_arity"
    WRONG_ROLE = "wrong_role"
    WRONG_SCOPE = "wrong_scope"
    INVALID_DIMENSION = "invalid_dimension"
    PVALUE_PROBABILITY_CONFLATION = "pvalue_probability_conflation"
    IMPLICATION_EQUIVALENCE_CORRUPTION = "implication_equivalence_corruption"
    EPISTEMIC_OVERCLAIM = "epistemic_overclaim"


class VerifierOutcome(StrEnum):
    """What a verifier reported. ``UNSUPPORTED`` and ``INCONCLUSIVE`` are not failures.

    They are also not passes. A required check that could not run leaves the episode
    unlabelled, which is a quarantine condition rather than a negative example.
    """

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    UNSUPPORTED = "unsupported"


class QuarantineEligibilityError(ValueError):
    """Raised on any attempt to mark quarantined data as training-eligible."""


class RoutingDisagreement(ValueError):
    """A supplied routing decision does not match the one the facts produce.

    Raised rather than resolved. There is no correct way to pick a winner between two
    disagreeing authorities over the same bit: whichever is chosen, the record no longer
    says what was believed at the time.
    """


class UnknownVerifierStatus(ValueError):
    """Raised when a verifier reports a status this router has no rule for."""


#: Translation from the verification protocol's status names to routing outcomes.
#:
#: Taken by *name*, not by importing the enum, so that this module keeps no dependency on
#: the verification layer and a rename over there fails loudly here instead of silently
#: mislabelling a row. ``SEMANTIC_LOSS`` is deliberately absent from the mapping: it is not
#: a verdict about the candidate, it is a statement that the translation lost meaning, and
#: it belongs in ``RoutingFacts.semantic_loss`` where it quarantines the episode.
_STATUS_TO_OUTCOME: Mapping[str, VerifierOutcome] = {
    "SUPPORTED_AND_VERIFIED": VerifierOutcome.PASS,
    "PASS": VerifierOutcome.PASS,
    "SUPPORTED_AND_FAILED": VerifierOutcome.FAIL,
    "INVALID": VerifierOutcome.FAIL,
    "FAIL": VerifierOutcome.FAIL,
    "INCONCLUSIVE": VerifierOutcome.INCONCLUSIVE,
    "UNSUPPORTED": VerifierOutcome.UNSUPPORTED,
}


def verifier_outcome_from_status(status: str) -> VerifierOutcome:
    """Map a verification-protocol status name onto a routing outcome.

    ``SEMANTIC_LOSS`` raises rather than being folded into ``FAIL``: an episode whose
    translation lost meaning has not been shown to be wrong, and filing it as a negative
    example would teach the wrong thing. Set ``RoutingFacts.semantic_loss`` instead.
    """
    name = status.upper()
    if name == "SEMANTIC_LOSS":
        raise UnknownVerifierStatus(
            "SEMANTIC_LOSS is not a verdict about the candidate. Record it as "
            "RoutingFacts.semantic_loss, which quarantines the episode, rather than "
            "converting it into a verifier outcome."
        )
    try:
        return _STATUS_TO_OUTCOME[name]
    except KeyError:
        raise UnknownVerifierStatus(
            f"no routing rule for verifier status {status!r}; known: "
            f"{sorted(_STATUS_TO_OUTCOME)} plus SEMANTIC_LOSS, which is handled separately"
        ) from None


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def exact_hash_of(text: str) -> str:
    """SHA-256 of the literal source. Detects byte-identical resubmission."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_hash_of(source: str) -> str | None:
    """The compiler's alpha-invariant content hash, or ``None`` if it does not compile.

    ``None`` is meaningful and is preserved: an output that does not compile has no
    canonical identity, so it can only be deduplicated exactly.
    """
    from .. import compile_source

    result = compile_source(source)
    if not result.ok():
        return None
    return result.hash()


# ---------------------------------------------------------------------------
# What routing needs from an episode
# ---------------------------------------------------------------------------


@runtime_checkable
class RoutableEpisode(Protocol):
    """The narrow view of an episode that routing consumes.

    Deliberately structural. The episode record itself is built elsewhere; this module
    needs these attributes and nothing else, and any object exposing them can be routed.
    """

    episode_id: str
    hypothesis: Hypothesis

    def routing_facts(self) -> RoutingFacts: ...


@dataclass(frozen=True)
class RoutingFacts:
    """Everything routing decides on, as plain immutable data.

    Booleans here are *observations*, never inferences. ``first_attempt_semantic_fidelity``
    means a comparison against a reference was performed and matched — not that nothing
    contradicted it.
    """

    episode_id: str
    hypothesis: Hypothesis
    exact_hash: str
    canonical_hash: str | None = None

    first_attempt_parsed: bool = False
    first_attempt_semantic_fidelity: bool = False
    unresolved_obligations: int = 0
    required_verifiers: tuple[str, ...] = ()
    verifier_results: Mapping[str, VerifierOutcome] = field(default_factory=dict)

    structured_diagnostic_codes: tuple[str, ...] = ()
    repair_attempts: int = 0
    repair_verified: bool | None = None

    near_miss_kinds: tuple[NearMissKind, ...] = ()
    attributed_skill_ids: tuple[str, ...] = ()

    provenance_complete: bool = False
    semantic_loss: bool = False
    unsupported_backend_dependency: bool = False
    ambiguous_label: bool = False
    evaluation_contamination: bool = False
    untrusted_synthetic_truth: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, Hypothesis):
            raise TypeError(
                "RoutingFacts.hypothesis must be a Hypothesis member; a routed episode "
                "with an untyped hypothesis cannot be kept separable"
            )
        if self.repair_attempts < 0:
            raise ValueError("repair_attempts cannot be negative")
        if self.repair_attempts == 0 and self.repair_verified is not None:
            raise ValueError(
                "repair_verified is set but no repair was attempted; that combination "
                "records a verification of something that did not happen"
            )

    def required_verifier_outcomes(self) -> tuple[tuple[str, VerifierOutcome | None], ...]:
        return tuple((name, self.verifier_results.get(name)) for name in self.required_verifiers)


@dataclass(frozen=True)
class RoutingDecision:
    """**The** training-eligibility decision, with the evidence that produced it.

    ``training_eligible`` here is authoritative. Nothing downstream may hold a second
    opinion; consumers read this field, and the constructors below make the illegal
    combinations unrepresentable rather than merely discouraged.
    """

    store: MemoryStoreKind
    training_eligible: bool
    reasons: tuple[str, ...]
    quarantine_reasons: tuple[QuarantineReason, ...] = ()
    near_miss: NearMissKind | None = None
    #: Which code decided. A decision with no author cannot be checked against the rules
    #: that were in force when it was made.
    decided_by: str = ROUTER_ID
    policy: TrainingPolicy = field(default_factory=lambda: DEFAULT_TRAINING_POLICY)

    def __post_init__(self) -> None:
        if self.training_eligible and self.store not in ELIGIBLE_KINDS:
            raise QuarantineEligibilityError(
                f"a {self.store.value} routing decision cannot be training-eligible. "
                "Quarantined data is never trainable, under any flag, and a decision "
                "object that says otherwise cannot be constructed."
            )
        if self.training_eligible and self.quarantine_reasons:
            raise QuarantineEligibilityError(
                "a training-eligible decision cannot carry quarantine reasons "
                f"{[r.value for r in self.quarantine_reasons]}; the row is either "
                "trusted or it is not"
            )
        if (
            self.training_eligible
            and self.store is MemoryStoreKind.HARD_NEGATIVE
            and not self.policy.hard_negatives_eligible
        ):
            raise QuarantineEligibilityError(
                "a hard negative is training-eligible only under a policy that says so. "
                "Pass TrainingPolicy(hard_negatives_eligible=True) with a rationale; "
                "training on negatives is a choice, not a default."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "store": self.store.value,
            "training_eligible": self.training_eligible,
            "reasons": list(self.reasons),
            "quarantine_reasons": [r.value for r in self.quarantine_reasons],
            "near_miss": self.near_miss.value if self.near_miss else None,
            "decided_by": self.decided_by,
            "policy": self.policy.to_dict(),
        }


def _quarantine_reasons(facts: RoutingFacts) -> list[tuple[QuarantineReason, str]]:
    found: list[tuple[QuarantineReason, str]] = []
    if not facts.hypothesis.scientific:
        found.append(
            (
                QuarantineReason.EXCLUDED_HYPOTHESIS,
                "the hypothesis is EXCLUDED: this is engineering work, not evidence, "
                "and it is never training-eligible and never aggregated",
            )
        )
    if facts.unsupported_backend_dependency:
        found.append(
            (
                QuarantineReason.UNSUPPORTED_BACKEND,
                "the verdict depends on a backend that does not support the construct",
            )
        )
    for name, outcome in facts.required_verifier_outcomes():
        if outcome is None:
            found.append(
                (
                    QuarantineReason.INCONCLUSIVE_VERIFICATION,
                    f"required verifier {name!r} reported nothing",
                )
            )
        elif outcome is VerifierOutcome.INCONCLUSIVE:
            found.append(
                (
                    QuarantineReason.INCONCLUSIVE_VERIFICATION,
                    f"required verifier {name!r} was inconclusive",
                )
            )
        elif outcome is VerifierOutcome.UNSUPPORTED:
            found.append(
                (
                    QuarantineReason.UNSUPPORTED_BACKEND,
                    f"required verifier {name!r} does not support this construct, so the "
                    "episode has no verdict rather than a negative one",
                )
            )
    if facts.semantic_loss:
        found.append(
            (QuarantineReason.SEMANTIC_LOSS, "a translation step dropped or weakened meaning")
        )
    if facts.ambiguous_label:
        found.append((QuarantineReason.AMBIGUOUS_LABEL, "the label was declared ambiguous"))
    if facts.evaluation_contamination:
        found.append(
            (
                QuarantineReason.POTENTIAL_EVALUATION_CONTAMINATION,
                "the item may overlap the held-out evaluation set",
            )
        )
    if not facts.provenance_complete:
        found.append(
            (
                QuarantineReason.MISSING_PROVENANCE,
                "provenance is incomplete; the row cannot be traced to its source",
            )
        )
    if facts.untrusted_synthetic_truth:
        found.append(
            (
                QuarantineReason.UNTRUSTED_SYNTHETIC_TRUTH,
                "the reference answer is synthetic and was not independently checked",
            )
        )
    return found


def _is_positive(facts: RoutingFacts) -> tuple[bool, list[str]]:
    misses: list[str] = []
    if not facts.first_attempt_parsed:
        misses.append("first attempt did not parse")
    if not facts.first_attempt_semantic_fidelity:
        misses.append("first attempt did not match the reference semantics")
    if facts.repair_attempts:
        misses.append(f"{facts.repair_attempts} repair(s) were used")
    if facts.unresolved_obligations:
        misses.append(f"{facts.unresolved_obligations} obligation(s) unresolved")
    for name, outcome in facts.required_verifier_outcomes():
        if outcome is not VerifierOutcome.PASS:
            misses.append(f"required verifier {name!r} did not pass")
    if not facts.required_verifiers:
        misses.append("no required verifier was declared, so nothing was required to pass")
    return (not misses), misses


def _is_repair(facts: RoutingFacts) -> tuple[bool, list[str]]:
    misses: list[str] = []
    if facts.first_attempt_semantic_fidelity and facts.first_attempt_parsed:
        misses.append("the first attempt already succeeded; there was nothing to repair")
    if not facts.structured_diagnostic_codes:
        misses.append("no structured diagnostic was issued")
    if facts.repair_attempts != 1:
        misses.append(f"exactly one repair is required; {facts.repair_attempts} were attempted")
    if facts.repair_verified is not True:
        misses.append("the repaired form was not verified")
    for name, outcome in facts.required_verifier_outcomes():
        if outcome is not VerifierOutcome.PASS:
            misses.append(f"required verifier {name!r} did not pass after repair")
    if not facts.required_verifiers:
        misses.append("no required verifier was declared, so the repair proved nothing")
    return (not misses), misses


def _is_hard_negative(facts: RoutingFacts) -> tuple[bool, list[str]]:
    misses: list[str] = []
    if len(facts.near_miss_kinds) != 1:
        misses.append(
            f"a hard negative must declare exactly one near-miss kind; "
            f"{len(facts.near_miss_kinds)} were declared"
        )
    if not facts.attributed_skill_ids:
        misses.append("no skill was attributed, so the example teaches nothing specific")
    if facts.repair_verified is True:
        misses.append("the episode was repaired and verified, so it is not a negative")
    return (not misses), misses


def route(
    facts: RoutingFacts, policy: TrainingPolicy | None = None
) -> RoutingDecision:
    """Decide the store **and** the training eligibility. Quarantine wins over all.

    This is the single authority. It fails closed on every one of: an ``EXCLUDED``
    hypothesis, missing provenance, an inconclusive or absent required verifier, semantic
    loss, an unsupported backend dependency, evaluation contamination, an untrusted
    synthetic reference, and an unclassifiable row. Any of them routes to quarantine with
    the reason recorded, and quarantine is never eligible.
    """
    pol = policy if policy is not None else DEFAULT_TRAINING_POLICY
    quarantine = _quarantine_reasons(facts)
    if quarantine:
        return RoutingDecision(
            store=MemoryStoreKind.QUARANTINE,
            training_eligible=False,
            reasons=tuple(detail for _, detail in quarantine),
            quarantine_reasons=tuple(dict.fromkeys(code for code, _ in quarantine)),
            policy=pol,
        )

    positive, positive_misses = _is_positive(facts)
    if positive:
        return RoutingDecision(
            store=MemoryStoreKind.POSITIVE,
            training_eligible=True,
            reasons=("first attempt was faithful and every required verifier passed",),
            policy=pol,
        )

    repair, repair_misses = _is_repair(facts)
    if repair:
        return RoutingDecision(
            store=MemoryStoreKind.REPAIR,
            training_eligible=True,
            reasons=(
                "one structured diagnostic, one repair, and the repaired form passed "
                f"every required check (diagnostics: {', '.join(facts.structured_diagnostic_codes)})",
            ),
            policy=pol,
        )

    hard_negative, hard_negative_misses = _is_hard_negative(facts)
    if hard_negative:
        why = (
            f"minimal attributable near-miss: {facts.near_miss_kinds[0].value} "
            f"attributed to {', '.join(facts.attributed_skill_ids)}"
        )
        return RoutingDecision(
            store=MemoryStoreKind.HARD_NEGATIVE,
            training_eligible=pol.hard_negatives_eligible,
            reasons=(
                why,
                (
                    f"training-eligible under the declared policy: {pol.rationale}"
                    if pol.hard_negatives_eligible
                    else "stored but NOT training-eligible: no policy permits training "
                    f"on hard negatives ({pol.rationale})"
                ),
            ),
            near_miss=facts.near_miss_kinds[0],
            policy=pol,
        )

    return RoutingDecision(
        store=MemoryStoreKind.QUARANTINE,
        training_eligible=False,
        reasons=(
            "not positive: " + "; ".join(positive_misses),
            "not repair: " + "; ".join(repair_misses),
            "not a hard negative: " + "; ".join(hard_negative_misses),
        ),
        quarantine_reasons=(QuarantineReason.AMBIGUOUS_LABEL,),
        policy=pol,
    )


def route_episode(
    episode: RoutableEpisode, policy: TrainingPolicy | None = None
) -> RoutingDecision:
    """Route an episode object by asking it for its routing facts."""
    facts = episode.routing_facts()
    if facts.episode_id != episode.episode_id:
        raise ValueError(
            f"episode {episode.episode_id!r} produced facts for {facts.episode_id!r}"
        )
    if facts.hypothesis is not episode.hypothesis:
        raise RoutingDisagreement(
            f"episode {episode.episode_id!r} is recorded under "
            f"{episode.hypothesis.value} but produced facts under "
            f"{facts.hypothesis.value}; the two cannot both be true of one episode"
        )
    return route(facts, policy)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryRecord:
    """One immutable row. Frozen: a stored row is evidence and evidence is not edited."""

    record_id: str
    episode_id: str
    hypothesis: Hypothesis
    store: MemoryStoreKind
    exact_hash: str
    canonical_hash: str | None
    training_eligible: bool
    decision: RoutingDecision
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, Hypothesis):
            raise TypeError("MemoryRecord.hypothesis must be a Hypothesis member")
        if self.store is MemoryStoreKind.QUARANTINE and self.training_eligible:
            raise QuarantineEligibilityError(
                f"record {self.record_id!r} is quarantined and marked training-eligible. "
                "Quarantined data is never training-eligible, under any flag."
            )
        if self.training_eligible and not self.hypothesis.scientific:
            raise QuarantineEligibilityError(
                f"record {self.record_id!r} carries hypothesis "
                f"{self.hypothesis.value}, which is not evidence, and is marked "
                "training-eligible. An EXCLUDED episode is never trainable."
            )
        if self.decision.store is not self.store:
            raise ValueError(
                f"record {self.record_id!r} claims store {self.store.value} but its routing "
                f"decision says {self.decision.store.value}"
            )
        if self.decision.training_eligible != self.training_eligible:
            raise ValueError(
                f"record {self.record_id!r} disagrees with its routing decision about "
                "training eligibility"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "episode_id": self.episode_id,
            "hypothesis": self.hypothesis.value,
            "store": self.store.value,
            "exact_hash": self.exact_hash,
            "canonical_hash": self.canonical_hash,
            "training_eligible": self.training_eligible,
            "decision": self.decision.to_dict(),
            "payload": dict(self.payload),
        }


class AppendStatus(StrEnum):
    APPENDED = "appended"
    EXACT_DUPLICATE = "exact_duplicate"
    ALPHA_EQUIVALENT_DUPLICATE = "alpha_equivalent_duplicate"


@dataclass(frozen=True)
class AppendOutcome:
    status: AppendStatus
    record: MemoryRecord
    existing_record_id: str | None = None

    @property
    def accepted(self) -> bool:
        return self.status is AppendStatus.APPENDED


class MemoryStore:
    """One append-only store for one ``(kind, hypothesis)`` pair.

    There is no ``remove``, no ``clear`` and no ``__setitem__``. A rejected duplicate is
    still recorded in ``duplicates`` — the row is not added twice, and the fact that it
    arrived twice is not thrown away either.
    """

    def __init__(self, kind: MemoryStoreKind, hypothesis: Hypothesis) -> None:
        if not isinstance(hypothesis, Hypothesis):
            raise TypeError("MemoryStore requires a typed Hypothesis")
        self.kind = kind
        self.hypothesis = hypothesis
        self._records: list[MemoryRecord] = []
        self._by_exact: dict[str, str] = {}
        self._by_canonical: dict[str, str] = {}
        self._duplicates: list[AppendOutcome] = []

    def append(self, record: MemoryRecord) -> AppendOutcome:
        if record.store is not self.kind:
            raise ValueError(
                f"record for store {record.store.value} offered to the {self.kind.value} store"
            )
        if record.hypothesis is not self.hypothesis:
            raise ValueError(
                f"record for {record.hypothesis.name} offered to the "
                f"{self.hypothesis.name} store; hypotheses are never merged"
            )
        if self.kind is MemoryStoreKind.QUARANTINE and record.training_eligible:
            raise QuarantineEligibilityError(
                "quarantined records are never training-eligible"
            )

        existing = self._by_exact.get(record.exact_hash)
        if existing is not None:
            outcome = AppendOutcome(AppendStatus.EXACT_DUPLICATE, record, existing)
            self._duplicates.append(outcome)
            return outcome
        if record.canonical_hash is not None:
            existing = self._by_canonical.get(record.canonical_hash)
            if existing is not None:
                outcome = AppendOutcome(
                    AppendStatus.ALPHA_EQUIVALENT_DUPLICATE, record, existing
                )
                self._duplicates.append(outcome)
                return outcome

        self._records.append(record)
        self._by_exact[record.exact_hash] = record.record_id
        if record.canonical_hash is not None:
            self._by_canonical[record.canonical_hash] = record.record_id
        return AppendOutcome(AppendStatus.APPENDED, record)

    @property
    def records(self) -> tuple[MemoryRecord, ...]:
        return tuple(self._records)

    @property
    def duplicates(self) -> tuple[AppendOutcome, ...]:
        return tuple(self._duplicates)

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterator[MemoryRecord]:
        return iter(tuple(self._records))


class MemoryBank:
    """The four stores, per hypothesis.

    Every accessor requires a hypothesis. There is no method that returns rows from more
    than one, because such a method is the only way the separation could be lost by
    accident.
    """

    def __init__(self) -> None:
        self._stores: dict[tuple[MemoryStoreKind, Hypothesis], MemoryStore] = {}

    def store(self, kind: MemoryStoreKind, hypothesis: Hypothesis) -> MemoryStore:
        if not isinstance(hypothesis, Hypothesis):
            raise TypeError("MemoryBank.store requires a typed Hypothesis")
        key = (kind, hypothesis)
        if key not in self._stores:
            self._stores[key] = MemoryStore(kind, hypothesis)
        return self._stores[key]

    def admit(self, record: MemoryRecord) -> AppendOutcome:
        return self.store(record.store, record.hypothesis).append(record)

    def records(
        self, kind: MemoryStoreKind, hypothesis: Hypothesis
    ) -> tuple[MemoryRecord, ...]:
        return self.store(kind, hypothesis).records

    def training_batch(
        self, hypothesis: Hypothesis, kinds: Iterable[MemoryStoreKind] | None = None
    ) -> tuple[MemoryRecord, ...]:
        """Training-eligible rows for one hypothesis. Quarantine cannot be requested."""
        selected = frozenset(kinds) if kinds is not None else TRAINABLE_KINDS
        forbidden = selected - TRAINABLE_KINDS
        if forbidden:
            raise QuarantineEligibilityError(
                f"{sorted(k.value for k in forbidden)} cannot be drawn for training"
            )
        out: list[MemoryRecord] = []
        for kind in sorted(selected, key=lambda k: k.value):
            out.extend(r for r in self.records(kind, hypothesis) if r.training_eligible)
        return tuple(out)

    def counts(self) -> dict[tuple[str, str], int]:
        """Row counts keyed by ``(store, hypothesis)`` — never by store alone."""
        return {
            (kind.value, hypothesis.value): len(store)
            for (kind, hypothesis), store in sorted(
                self._stores.items(), key=lambda kv: (kv[0][0].value, kv[0][1].value)
            )
        }

    def hypotheses(self) -> tuple[Hypothesis, ...]:
        return tuple(sorted({h for _, h in self._stores}, key=lambda h: h.value))

    def provenance_hashes(self, hypothesis: Hypothesis) -> tuple[str, ...]:
        """Canonical (or exact, when uncompilable) hashes of the training-eligible rows."""
        return tuple(
            r.canonical_hash or r.exact_hash for r in self.training_batch(hypothesis)
        )

    def quarantined_ids(self, hypothesis: Hypothesis) -> tuple[str, ...]:
        return tuple(
            r.record_id for r in self.records(MemoryStoreKind.QUARANTINE, hypothesis)
        )


def build_record(
    record_id: str,
    facts: RoutingFacts,
    *,
    payload: Mapping[str, Any] | None = None,
    decision: RoutingDecision | None = None,
    policy: TrainingPolicy | None = None,
) -> MemoryRecord:
    """Route ``facts`` and wrap the result in the record the stores accept.

    ``decision`` used to be an override: whatever the caller passed was stored, and the
    facts were never consulted. It is now a **claim to be checked**. The decision is
    re-derived from the facts and a mismatch raises :class:`RoutingDisagreement`, so the
    parameter can still carry a decision computed earlier (avoiding a second routing
    pass) but can no longer smuggle a different verdict past the router.
    """
    derived = route(facts, policy)
    if decision is not None and (
        decision.store is not derived.store
        or decision.training_eligible != derived.training_eligible
        or set(decision.quarantine_reasons) != set(derived.quarantine_reasons)
    ):
        raise RoutingDisagreement(
            f"record {record_id!r}: the supplied decision says store="
            f"{decision.store.value} eligible={decision.training_eligible} but the facts "
            f"route to store={derived.store.value} "
            f"eligible={derived.training_eligible}. The router decides; a caller cannot "
            "hold a second opinion about the same bit."
        )
    d = derived
    return MemoryRecord(
        record_id=record_id,
        episode_id=facts.episode_id,
        hypothesis=facts.hypothesis,
        store=d.store,
        exact_hash=facts.exact_hash,
        canonical_hash=facts.canonical_hash,
        training_eligible=d.training_eligible,
        decision=d,
        payload=dict(payload or {}),
    )


def routed_summary(records: Sequence[MemoryRecord]) -> dict[str, Any]:
    """A per-hypothesis, per-store tally. Raises rather than merging hypotheses."""
    tally: dict[str, dict[str, int]] = {}
    for r in records:
        tally.setdefault(r.hypothesis.value, {}).setdefault(r.store.value, 0)
        tally[r.hypothesis.value][r.store.value] += 1
    return tally
