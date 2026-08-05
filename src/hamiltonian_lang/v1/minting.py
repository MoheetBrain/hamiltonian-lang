"""V1 concept-minting protocol — HML-V1-CONCEPT-001 Phase 3.

**This is not a word generator.** The protocol's purpose is to refuse most candidates.
A candidate that type-checks but abbreviates nothing is a synonym, and a synonym dressed
as a definition is worse than no definition at all: it multiplies vocabulary without
multiplying expressible content, and it makes a registry look richer than it is.

:func:`mint` runs eight steps, in the order the specification fixes:

1. search the registry for equality, equivalence, renaming, specialisation, generalisation
2. distinguish a genuinely new abstraction from a new name for an old concept
3. require a valid type signature and a formal definition
4. verify the declared constraints
5. generate proof obligations for the claimed properties
6. run the supplied examples and counterexamples
7. **identify at least one recurring structure the concept compresses**
8. record, per claim, whether it is proved / tested / conjectured / unsupported

Every step runs, even after an earlier one has already decided the verdict, so that the
report is complete rather than truncated at the first objection. The verdict is then
resolved by a fixed precedence — ``rejected`` before ``duplicate`` before ``admitted`` —
documented at :func:`resolve_verdict`, so it does not depend on which step happened to
notice a fault first.

Two honesty rules run through the whole module:

* **A status is never raised above its evidence.** A claimed ``proved`` with no
  machine-checked proof does not stay ``proved``. Numerical agreement is ``tested``.
* **An executed test that fails is recorded, and blocks admission.** A concept whose own
  declared invariant is refuted by a test that actually ran is rejected, not annotated.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum

from hamiltonian_lang.v1.registry import (
    AdmissionRecord,
    Claim,
    ClaimStatus,
    Concept,
    ConceptRegistry,
    CounterexampleRecord,
    Lifecycle,
    RegistryError,
    RelationKind,
    normalise_type_signature,
    normalise_whitespace,
)

__all__ = [
    "MintingError",
    "TypeSignatureError",
    "Severity",
    "Finding",
    "Example",
    "CounterexampleTest",
    "PropertyClaim",
    "ConstraintCheck",
    "CompressionEvidence",
    "ConceptCandidate",
    "AdjudicatedClaim",
    "RegistrySearch",
    "AdmissionReport",
    "PLACEHOLDER_DEFINITIONS",
    "MINIMUM_RECURRENCE",
    "parse_type_signature",
    "search_registry",
    "adjudicate_claim",
    "resolve_verdict",
    "mint",
    "summarise",
]


class MintingError(RegistryError):
    """A minting run could not be performed at all — as distinct from a rejection."""


class TypeSignatureError(MintingError):
    """A type signature is not well formed."""


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


class Severity(StrEnum):
    """``NOTE`` records something; ``BLOCKING`` prevents admission."""

    NOTE = "note"
    BLOCKING = "blocking"


@dataclass(frozen=True)
class Finding:
    """One observation from one step, with the verdict it forces if it is blocking."""

    step: int
    code: str
    severity: Severity
    message: str
    implies: Lifecycle | None = None

    def blocks(self) -> bool:
        return self.severity is Severity.BLOCKING

    def render(self) -> str:
        return f"[step {self.step}] {self.code}: {self.message}"


# ---------------------------------------------------------------------------
# Candidate inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Example:
    """A witness that the concept is inhabited. ``run`` is actually executed."""

    description: str
    run: Callable[[], bool]


@dataclass(frozen=True)
class CounterexampleTest:
    """A witness that a NEARBY claim is false.

    ``run`` must return True when the witness genuinely refutes ``refutes``. A
    counterexample that refutes nothing is a false record and blocks admission: a boundary
    drawn where there is none misleads exactly as much as a missing one.
    """

    refutes: str
    witness: str
    run: Callable[[], bool]


@dataclass(frozen=True)
class PropertyClaim:
    """A property the author asserts of the concept, with whatever backs it.

    ``proof_checked`` is true ONLY if a real checker accepted ``proof``. A proof reference
    nobody ran is a reference, not a proof, and adjudicates to ``conjectured``.
    """

    statement: str
    claimed_status: ClaimStatus = ClaimStatus.CONJECTURED
    test: Callable[[], bool] | None = None
    proof: str | None = None
    proof_checked: bool = False


@dataclass(frozen=True)
class ConstraintCheck:
    """A declared constraint together with the executable check for it, if any.

    ``check is None`` is permitted and is recorded as *unverified*. It never counts as
    verified by default.
    """

    constraint: str
    check: Callable[[], bool] | None = None


#: A structure must appear at least this many times before it counts as *recurring*. One
#: occurrence is an instance, not a pattern, and abbreviating a single site saves nothing.
MINIMUM_RECURRENCE = 2


@dataclass(frozen=True)
class CompressionEvidence:
    """Evidence that the concept abbreviates a structure that actually recurs.

    This is the field that separates a concept from a synonym. It is deliberately
    concrete: name the structure, list the sites where it recurs, give the long form and
    the short form. "It is a useful abstraction" is not evidence.
    """

    structure: str
    occurrences: tuple[str, ...]
    expansion: str
    abbreviation: str

    @property
    def recurs(self) -> bool:
        return len(set(self.occurrences)) >= MINIMUM_RECURRENCE

    @property
    def shortens(self) -> bool:
        return len(normalise_whitespace(self.abbreviation)) < len(
            normalise_whitespace(self.expansion)
        )

    @property
    def demonstrated(self) -> bool:
        """Recurrence AND a genuine shortening. Either alone establishes nothing."""
        return self.recurs and self.shortens

    def why_not(self) -> str:
        if not self.recurs:
            return (
                f"{self.structure!r} is cited at {len(set(self.occurrences))} site(s); "
                f"a structure recurs only at {MINIMUM_RECURRENCE} or more"
            )
        if not self.shortens:
            return (
                f"{self.structure!r} abbreviates nothing: the short form is not shorter "
                f"than the expansion"
            )
        return ""


@dataclass(frozen=True)
class ConceptCandidate:
    """Everything the minting protocol is allowed to look at.

    The concept carries the schema record; the other fields carry the *executable*
    material — callables that are really run — which a JSON schema cannot hold.
    """

    concept: Concept
    examples: tuple[Example, ...] = ()
    counterexample_tests: tuple[CounterexampleTest, ...] = ()
    claims: tuple[PropertyClaim, ...] = ()
    constraint_checks: tuple[ConstraintCheck, ...] = ()
    compression: tuple[CompressionEvidence, ...] = ()

    @property
    def canonical_id(self) -> str:
        return self.concept.canonical_id


# ---------------------------------------------------------------------------
# Step 3 — type signatures and definitions
# ---------------------------------------------------------------------------

_TYPE_TOKEN = re.compile(r"(->|[\[\](),*]|[A-Za-z_][A-Za-z0-9_]*)")
_TYPE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _tokenise_type(text: str) -> list[str]:
    tokens: list[str] = []
    position = 0
    while position < len(text):
        if text[position].isspace():
            position += 1
            continue
        match = _TYPE_TOKEN.match(text, position)
        if match is None:
            raise TypeSignatureError(
                f"unexpected character {text[position]!r} at offset {position} in {text!r}"
            )
        tokens.append(match.group(1))
        position = match.end()
    return tokens


class _TypeParser:
    """A recursive-descent recogniser for the registry's type-expression surface.

    It recognises shape, not meaning: ``Dataset[Real] * LossFunction[Real, Real] ->
    ArgminSet[Real]`` parses, ``Real ->`` does not. It deliberately does not consult V0's
    type lattice — V0 is frozen, and a concept registry may legitimately name types the V0
    kernel has never heard of.
    """

    def __init__(self, tokens: Sequence[str], source: str) -> None:
        self.tokens = list(tokens)
        self.position = 0
        self.source = source

    def peek(self) -> str | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self) -> str:
        token = self.peek()
        if token is None:
            raise TypeSignatureError(
                f"type expression ends unexpectedly in {self.source!r}"
            )
        self.position += 1
        return token

    def expect(self, token: str) -> None:
        actual = self.take()
        if actual != token:
            raise TypeSignatureError(
                f"expected {token!r} but found {actual!r} in {self.source!r}"
            )

    def parse_expression(self) -> None:
        """``expression := product ('->' expression)?`` — right associative."""
        self.parse_product()
        if self.peek() == "->":
            self.take()
            self.parse_expression()

    def parse_product(self) -> None:
        self.parse_atom()
        while self.peek() == "*":
            self.take()
            self.parse_atom()

    def parse_atom(self) -> None:
        token = self.take()
        if token == "(":
            self.parse_expression()
            self.expect(")")
            return
        if not _TYPE_NAME.fullmatch(token):
            raise TypeSignatureError(
                f"expected a type name but found {token!r} in {self.source!r}"
            )
        if self.peek() == "[":
            self.take()
            self.parse_expression()
            while self.peek() == ",":
                self.take()
                self.parse_expression()
            self.expect("]")

    def finish(self) -> None:
        if self.position != len(self.tokens):
            raise TypeSignatureError(
                f"trailing {self.tokens[self.position]!r} in {self.source!r}"
            )


def _parse_whole(text: str) -> None:
    parser = _TypeParser(_tokenise_type(text), text)
    parser.parse_expression()
    parser.finish()


def _split_top_level_arrow(tokens: Sequence[str]) -> int:
    """Index of the first ``->`` at bracket depth zero, or -1."""
    depth = 0
    for index, token in enumerate(tokens):
        if token in ("[", "("):
            depth += 1
        elif token in ("]", ")"):
            depth -= 1
        elif token == "->" and depth == 0:
            return index
    return -1


def parse_type_signature(signature: str) -> tuple[str, str]:
    """Split ``signature`` into ``(domain, codomain)``, validating both sides.

    Raises :class:`TypeSignatureError` if there is no top-level arrow or if either side is
    not a well-formed type expression. An arrow nested inside brackets, as in
    ``Function[Sample -> ParameterSpace]``, is not a top-level arrow.
    """
    if not signature.strip():
        raise TypeSignatureError("the type signature is empty")
    tokens = _tokenise_type(signature)
    arrow = _split_top_level_arrow(tokens)
    if arrow < 0:
        raise TypeSignatureError(
            f"{signature!r} has no top-level '->'; a concept signature must state what it "
            f"maps from and what it maps to"
        )
    left, right = tokens[:arrow], tokens[arrow + 1 :]
    if not left or not right:
        raise TypeSignatureError(f"{signature!r} has an empty side of '->'")
    for side in (left, right):
        parser = _TypeParser(side, signature)
        parser.parse_expression()
        parser.finish()
    return " ".join(left), " ".join(right)


#: Strings that occupy the ``formal_definition`` slot without defining anything.
PLACEHOLDER_DEFINITIONS: frozenset[str] = frozenset(
    {
        "",
        "todo",
        "tbd",
        "n/a",
        "na",
        "none",
        "see above",
        "see below",
        "as usual",
        "the usual definition",
        "standard",
        "obvious",
        "clear",
        "clearly",
        "well known",
        "as is well known",
        "?",
        "-",
    }
)

_MIN_DEFINITION_CHARS = 12
_MIN_DEFINITION_TOKENS = 3


def _definition_is_substantive(concept: Concept) -> tuple[bool, str]:
    """A *syntactic* sufficiency check, and it is honest about being only that.

    It cannot tell a good definition from a bad one. It can tell a definition from a
    placeholder, from a restatement of the concept's own name, and from a copy of its type
    signature — the three ways the slot gets filled without being answered.
    """
    text = normalise_whitespace(concept.formal_definition)
    folded = text.casefold().rstrip(".")
    if folded in PLACEHOLDER_DEFINITIONS:
        return False, f"formal_definition is a placeholder ({text!r}), not a definition"
    if len(text) < _MIN_DEFINITION_CHARS or len(text.split()) < _MIN_DEFINITION_TOKENS:
        return False, (
            f"formal_definition {text!r} is too short to be a definition "
            f"(need >= {_MIN_DEFINITION_CHARS} characters and "
            f">= {_MIN_DEFINITION_TOKENS} tokens)"
        )
    for handle in concept.handles:
        if folded == handle.casefold():
            return False, (
                f"formal_definition restates the handle {handle!r}; a name is not a "
                f"definition"
            )
    if folded == normalise_type_signature(concept.type_signature).casefold():
        return False, (
            "formal_definition repeats the type signature; a signature constrains a "
            "definition, it does not supply one"
        )
    return True, ""


# ---------------------------------------------------------------------------
# Step 1 — registry search
# ---------------------------------------------------------------------------

_WORD = r"(?<![A-Za-z0-9_]){}(?![A-Za-z0-9_])"


def _substitute_self(text: str, concept: Concept) -> str:
    """Replace every handle of ``concept`` by ``#self``, so a pure rename is visible."""
    result = text
    for handle in sorted(concept.handles, key=len, reverse=True):
        result = re.sub(_WORD.format(re.escape(handle)), "#self", result)
    return result


def _alpha_normalise(text: str, concept: Concept) -> str:
    """``#self`` substitution plus positional placeholders for the *declared* parameters.

    ``f(x) = x^2`` and ``f(y) = y^2`` normalise to the same string when ``x`` and ``y`` are
    the declared parameters. That is a renaming, not a new abstraction.

    The limit is deliberate and worth stating: a symbol that the concept does not declare
    as a parameter is left alone. Two definitions differing only in a free bound symbol
    therefore do **not** compare equal, and the pair is reported as two concepts. Missing a
    duplicate costs a redundant entry; abstracting every identifier would report unrelated
    concepts as duplicates, which costs a real one. The check errs towards the first.
    """
    result = _substitute_self(text, concept)
    indexed = sorted(
        enumerate(concept.parameters), key=lambda pair: len(pair[1].name), reverse=True
    )
    for position, parameter in indexed:
        result = re.sub(
            _WORD.format(re.escape(parameter.name)), f"#p{position}", result
        )
    return result


def _fold(text: str) -> str:
    return normalise_whitespace(text).casefold()


def _equality_key(concept: Concept) -> tuple[str, frozenset[str], str]:
    """Same signature, same constraints, same definition once the name is abstracted."""
    return (
        normalise_type_signature(concept.type_signature).casefold(),
        frozenset(_fold(_substitute_self(c, concept)) for c in concept.constraints),
        _fold(_substitute_self(concept.formal_definition, concept)),
    )


def _renaming_key(concept: Concept) -> tuple[str, frozenset[str], str]:
    """As :func:`_equality_key`, but with the parameter names abstracted as well."""
    return (
        normalise_type_signature(concept.type_signature).casefold(),
        frozenset(_fold(_alpha_normalise(c, concept)) for c in concept.constraints),
        _fold(_alpha_normalise(concept.formal_definition, concept)),
    )


@dataclass(frozen=True)
class RegistrySearch:
    """What the registry already contains that is near the candidate."""

    performed: bool = False
    equality_matches: tuple[str, ...] = ()
    equivalence_matches: tuple[str, ...] = ()
    renaming_matches: tuple[str, ...] = ()
    specialisation_of: tuple[str, ...] = ()
    generalisation_of: tuple[str, ...] = ()
    id_collision: str | None = None

    @property
    def is_old_concept_under_a_new_name(self) -> bool:
        """Step 2's question, answered from step 1's evidence."""
        return bool(self.equality_matches or self.renaming_matches or self.id_collision)

    @property
    def nearest_duplicate(self) -> str | None:
        for group in (self.equality_matches, self.renaming_matches):
            if group:
                return group[0]
        return self.id_collision


#: A match against a registry entry in one of these states does not count. A duplicate of
#: something already rejected is not a duplicate; the ground it occupied is free again.
_SEARCH_EXCLUDED_STATES: frozenset[Lifecycle] = frozenset(
    {Lifecycle.REJECTED, Lifecycle.DUPLICATE}
)


def search_registry(candidate: Concept, registry: ConceptRegistry) -> RegistrySearch:
    """Step 1. Search for equality, equivalence, renaming, specialisation, generalisation.

    Matching is over *typed structure*, never over the name: a concept renamed is still the
    same concept, and a concept with the same name but a different definition is not the
    same concept.
    """
    equality: list[str] = []
    renaming: list[str] = []
    specialisation: list[str] = []
    generalisation: list[str] = []
    equivalence: list[str] = []

    collision = None
    existing = registry.find(candidate.canonical_id)
    if existing is not None and existing.admission_status not in _SEARCH_EXCLUDED_STATES:
        collision = existing.canonical_id

    candidate_equality = _equality_key(candidate)
    candidate_renaming = _renaming_key(candidate)
    candidate_signature = normalise_type_signature(candidate.type_signature).casefold()
    candidate_constraints = frozenset(
        _fold(_alpha_normalise(c, candidate)) for c in candidate.constraints
    )

    for other in registry:
        if other.canonical_id == candidate.canonical_id:
            continue
        if other.admission_status in _SEARCH_EXCLUDED_STATES:
            continue
        if _equality_key(other) == candidate_equality:
            equality.append(other.canonical_id)
            continue
        if _renaming_key(other) == candidate_renaming:
            renaming.append(other.canonical_id)
            continue
        if (
            normalise_type_signature(other.type_signature).casefold()
            == candidate_signature
        ):
            other_constraints = frozenset(
                _fold(_alpha_normalise(c, other)) for c in other.constraints
            )
            if candidate_constraints > other_constraints:
                specialisation.append(other.canonical_id)
            elif candidate_constraints < other_constraints:
                generalisation.append(other.canonical_id)

    for relation in (*candidate.equivalences, *candidate.implications):
        if registry.find(relation.other) is None:
            continue
        if relation.kind is RelationKind.EQUIVALENT_TO:
            equivalence.append(relation.other)
        elif relation.kind is RelationKind.SPECIALISES:
            specialisation.append(relation.other)
        elif relation.kind is RelationKind.GENERALISES:
            generalisation.append(relation.other)

    def unique(items: Iterable[str]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(items))

    return RegistrySearch(
        performed=True,
        equality_matches=unique(equality),
        equivalence_matches=unique(equivalence),
        renaming_matches=unique(renaming),
        specialisation_of=unique(specialisation),
        generalisation_of=unique(generalisation),
        id_collision=collision,
    )


# ---------------------------------------------------------------------------
# Step 8 — claim adjudication
# ---------------------------------------------------------------------------

#: Marker prefix on the evidence string of a claim an executed test actually refuted, as
#: distinct from one that is merely unsupported.
REFUTED_PREFIX = "refuted:"


@dataclass(frozen=True)
class AdjudicatedClaim:
    """What the author claimed, next to what the evidence supports."""

    statement: str
    claimed_status: ClaimStatus
    status: ClaimStatus
    evidence: str
    discharged_by: str | None = None

    @property
    def downgraded(self) -> bool:
        return _CLAIM_RANK[self.status] < _CLAIM_RANK[self.claimed_status]

    @property
    def refuted(self) -> bool:
        """The claim was tested and the test failed — a demonstrated falsehood."""
        return self.status is ClaimStatus.UNSUPPORTED and self.evidence.startswith(
            REFUTED_PREFIX
        )

    def to_claim(self) -> Claim:
        return Claim(
            statement=self.statement,
            status=self.status,
            evidence=self.evidence,
            discharged_by=self.discharged_by,
        )


#: Used only to detect a downgrade. It is NOT a coercion order: nothing in this module
#: ever promotes a claim up this ranking without evidence for the higher rung.
_CLAIM_RANK: dict[ClaimStatus, int] = {
    ClaimStatus.UNSUPPORTED: 0,
    ClaimStatus.CONJECTURED: 1,
    ClaimStatus.TESTED: 2,
    ClaimStatus.PROVED: 3,
}


def adjudicate_claim(claim: PropertyClaim) -> AdjudicatedClaim:
    """Decide a claim's real status from its real evidence.

    The table, in order of consultation:

    ==================================  ==================
    evidence                            adjudicated status
    ==================================  ==================
    proof reference, checker accepted   ``proved``
    executable test, it passed          ``tested``
    executable test, it failed/raised   ``unsupported``
    proof reference, nobody checked it  ``conjectured``
    nothing, and claimed conjectured    ``conjectured``
    nothing, and claimed anything else  ``unsupported``
    ==================================  ==================

    The last two rows are the point: an honest conjecture keeps its status, while asserting
    ``proved`` with nothing behind it lands strictly lower than admitting a conjecture.
    """
    if claim.proof is not None and claim.proof_checked:
        return AdjudicatedClaim(
            statement=claim.statement,
            claimed_status=claim.claimed_status,
            status=ClaimStatus.PROVED,
            evidence=f"proof accepted by a checker: {claim.proof}",
            discharged_by=claim.proof,
        )

    if claim.test is not None:
        try:
            passed = bool(claim.test())
        except Exception as exc:  # noqa: BLE001 - the failure itself is the finding
            return AdjudicatedClaim(
                statement=claim.statement,
                claimed_status=claim.claimed_status,
                status=ClaimStatus.UNSUPPORTED,
                evidence=f"{REFUTED_PREFIX} the test raised {type(exc).__name__}: {exc}",
                discharged_by=None,
            )
        if passed:
            return AdjudicatedClaim(
                statement=claim.statement,
                claimed_status=claim.claimed_status,
                status=ClaimStatus.TESTED,
                evidence="an executed test passed; this is evidence, not a proof",
                discharged_by=None,
            )
        return AdjudicatedClaim(
            statement=claim.statement,
            claimed_status=claim.claimed_status,
            status=ClaimStatus.UNSUPPORTED,
            evidence=f"{REFUTED_PREFIX} an executed test returned False",
            discharged_by=None,
        )

    if claim.proof is not None:
        return AdjudicatedClaim(
            statement=claim.statement,
            claimed_status=claim.claimed_status,
            status=ClaimStatus.CONJECTURED,
            evidence=(
                f"a proof is cited ({claim.proof}) but no checker accepted it; "
                f"an unverified proof is a reference, not a proof"
            ),
            discharged_by=None,
        )

    if claim.claimed_status is ClaimStatus.CONJECTURED:
        return AdjudicatedClaim(
            statement=claim.statement,
            claimed_status=claim.claimed_status,
            status=ClaimStatus.CONJECTURED,
            evidence="declared as a conjecture and supplied as one",
            discharged_by=None,
        )

    return AdjudicatedClaim(
        statement=claim.statement,
        claimed_status=claim.claimed_status,
        status=ClaimStatus.UNSUPPORTED,
        evidence=(
            f"claimed {claim.claimed_status.value} with no proof and no executable test"
        ),
        discharged_by=None,
    )


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdmissionReport:
    """The full result of a minting run.

    :meth:`to_record` narrows it to the subset the registry schema stores. The extra fields
    here — findings, adjudications, obligations — are the working detail a reader needs in
    order to see why the verdict came out the way it did.
    """

    candidate_id: str
    search: RegistrySearch
    type_valid: bool
    definition_present: bool
    constraints_verified: bool
    obligations: tuple[Claim, ...]
    examples_tested: int
    examples_passed: int
    counterexamples_tested: int
    counterexamples_verified: int
    compression_demonstrated: bool
    claim_adjudications: tuple[AdjudicatedClaim, ...]
    findings: tuple[Finding, ...]
    verdict: Lifecycle
    concept: Concept
    duplicate_of: str | None = None
    recorded: bool = False

    @property
    def admitted(self) -> bool:
        return self.verdict is Lifecycle.ADMITTED

    @property
    def obligations_generated(self) -> int:
        return len(self.obligations)

    @property
    def blocking_findings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.blocks())

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(f.code for f in self.findings)

    @property
    def blocking_codes(self) -> tuple[str, ...]:
        return tuple(f.code for f in self.blocking_findings)

    def claim(self, statement: str) -> AdjudicatedClaim:
        """The adjudication of one claim, by its statement."""
        for adjudicated in self.claim_adjudications:
            if adjudicated.statement == statement:
                return adjudicated
        raise KeyError(statement)

    def reason(self) -> str:
        blocking = self.blocking_findings
        if not blocking:
            return "every check passed"
        return "; ".join(f.render() for f in blocking)

    def render(self) -> str:
        lines = [f"{self.candidate_id}: {self.verdict.value}"]
        lines += [f"  {f.render()}" for f in self.findings]
        for adjudicated in self.claim_adjudications:
            lines.append(
                f"  claim {adjudicated.statement!r}: claimed "
                f"{adjudicated.claimed_status.value}, recorded "
                f"{adjudicated.status.value} ({adjudicated.evidence})"
            )
        return "\n".join(lines)

    def to_record(self) -> AdmissionRecord:
        return AdmissionRecord(
            registry_search_performed=self.search.performed,
            equality_matches=self.search.equality_matches,
            equivalence_matches=self.search.equivalence_matches,
            renaming_matches=self.search.renaming_matches,
            specialisation_of=self.search.specialisation_of,
            generalisation_of=self.search.generalisation_of,
            type_valid=self.type_valid,
            definition_present=self.definition_present,
            constraints_verified=self.constraints_verified,
            obligations_generated=self.obligations_generated,
            examples_tested=self.examples_tested,
            examples_passed=self.examples_passed,
            counterexamples_tested=self.counterexamples_tested,
            compression_demonstrated=self.compression_demonstrated,
            verdict=self.verdict,
        )


def resolve_verdict(findings: Sequence[Finding]) -> Lifecycle:
    """Fixed precedence: ``rejected`` beats ``duplicate`` beats ``admitted``.

    Precedence is by *kind*, never by order of discovery, so a candidate that is both
    malformed and a duplicate always reports ``rejected`` — the more fundamental fault —
    regardless of which step noticed first.
    """
    implied = {f.implies for f in findings if f.blocks()}
    if Lifecycle.REJECTED in implied:
        return Lifecycle.REJECTED
    if Lifecycle.DUPLICATE in implied:
        return Lifecycle.DUPLICATE
    return Lifecycle.ADMITTED


# ---------------------------------------------------------------------------
# The protocol
# ---------------------------------------------------------------------------


@dataclass
class _Run:
    """Mutable working state for one minting run."""

    candidate: ConceptCandidate
    registry: ConceptRegistry
    findings: list[Finding] = field(default_factory=list)
    obligations: list[Claim] = field(default_factory=list)

    def note(self, step: int, code: str, message: str) -> None:
        self.findings.append(Finding(step, code, Severity.NOTE, message))

    def block(self, step: int, code: str, message: str, implies: Lifecycle) -> None:
        self.findings.append(Finding(step, code, Severity.BLOCKING, message, implies))


@dataclass(frozen=True)
class _ExampleResults:
    examples_tested: int
    examples_passed: int
    counterexample_verified: tuple[bool, ...]

    @property
    def counterexamples_tested(self) -> int:
        return len(self.counterexample_verified)

    @property
    def counterexamples_verified(self) -> int:
        return sum(self.counterexample_verified)


def _step_1_search(run: _Run) -> RegistrySearch:
    search = search_registry(run.candidate.concept, run.registry)
    if search.equality_matches:
        run.note(
            1,
            "REGISTRY_EQUALITY_MATCH",
            f"structurally identical to {', '.join(search.equality_matches)}",
        )
    if search.renaming_matches:
        run.note(
            1,
            "REGISTRY_RENAMING_MATCH",
            f"identical up to renaming to {', '.join(search.renaming_matches)}",
        )
    if search.specialisation_of:
        run.note(
            1,
            "REGISTRY_SPECIALISATION",
            f"specialises {', '.join(search.specialisation_of)}",
        )
    if search.generalisation_of:
        run.note(
            1,
            "REGISTRY_GENERALISATION",
            f"generalises {', '.join(search.generalisation_of)}",
        )
    if search.equivalence_matches:
        run.note(
            1,
            "REGISTRY_EQUIVALENCE_DECLARED",
            f"declares an equivalence to {', '.join(search.equivalence_matches)}; a "
            f"declared equivalence is a claim and carries its own obligation",
        )
    return search


def _step_2_novelty(run: _Run, search: RegistrySearch) -> None:
    """Is this a new abstraction, or a new name for an old one?"""
    if search.id_collision is not None:
        run.block(
            2,
            "CANONICAL_ID_TAKEN",
            f"canonical_id {search.id_collision!r} is already registered and is not in a "
            f"terminal state",
            Lifecycle.DUPLICATE,
        )
    for match in search.equality_matches:
        run.block(
            2,
            "DUPLICATE_OF_EXISTING",
            f"the same typed structure, constraints and definition are already registered "
            f"as {match!r}; a new handle over an old concept is a duplicate",
            Lifecycle.DUPLICATE,
        )
    for match in search.renaming_matches:
        run.block(
            2,
            "RENAMING_OF_EXISTING",
            f"identical to {match!r} up to renaming of its parameters; renaming is not "
            f"abstraction",
            Lifecycle.DUPLICATE,
        )
    if not search.is_old_concept_under_a_new_name:
        detail = "no equality or renaming match in the registry"
        if search.specialisation_of:
            detail += (
                f"; it adds constraints to {', '.join(search.specialisation_of)}, which is "
                f"a genuine specialisation"
            )
        if search.generalisation_of:
            detail += (
                f"; it drops constraints from {', '.join(search.generalisation_of)}, which "
                f"is a genuine generalisation"
            )
        run.note(2, "NOVEL_STRUCTURE", detail)


def _step_3_structure(run: _Run) -> tuple[bool, bool]:
    concept = run.candidate.concept
    type_valid = True
    try:
        domain, codomain = parse_type_signature(concept.type_signature)
    except TypeSignatureError as exc:
        type_valid = False
        run.block(3, "INVALID_TYPE_SIGNATURE", str(exc), Lifecycle.REJECTED)
    else:
        if normalise_type_signature(domain) != normalise_type_signature(concept.domain):
            type_valid = False
            run.block(
                3,
                "DOMAIN_MISMATCH",
                f"type_signature declares the domain {domain!r} but the domain field says "
                f"{concept.domain!r}; the two must agree or one of them is decoration",
                Lifecycle.REJECTED,
            )
        if normalise_type_signature(codomain) != normalise_type_signature(
            concept.codomain
        ):
            type_valid = False
            run.block(
                3,
                "CODOMAIN_MISMATCH",
                f"type_signature declares the codomain {codomain!r} but the codomain field "
                f"says {concept.codomain!r}",
                Lifecycle.REJECTED,
            )

    seen_roles: set[str] = set()
    seen_names: set[str] = set()
    for parameter in concept.parameters:
        if not parameter.name.strip() or not parameter.type.strip():
            type_valid = False
            run.block(
                3,
                "PARAMETER_INCOMPLETE",
                f"parameter {parameter.name!r} has no name or no type",
                Lifecycle.REJECTED,
            )
            continue
        if not parameter.role.strip():
            type_valid = False
            run.block(
                3,
                "PARAMETER_ROLE_MISSING",
                f"parameter {parameter.name!r} declares no role; roles are meaning, not "
                f"decoration (V0 decision D-003)",
                Lifecycle.REJECTED,
            )
        if parameter.name in seen_names:
            type_valid = False
            run.block(
                3,
                "PARAMETER_NAME_REPEATED",
                f"parameter name {parameter.name!r} appears twice",
                Lifecycle.REJECTED,
            )
        if parameter.role and parameter.role in seen_roles:
            type_valid = False
            run.block(
                3,
                "PARAMETER_ROLE_REPEATED",
                f"role {parameter.role!r} is claimed by two parameters; a role identifies "
                f"what a position means and cannot be shared",
                Lifecycle.REJECTED,
            )
        seen_names.add(parameter.name)
        seen_roles.add(parameter.role)
        try:
            _parse_whole(parameter.type)
        except TypeSignatureError as exc:
            type_valid = False
            run.block(
                3,
                "INVALID_PARAMETER_TYPE",
                f"parameter {parameter.name!r}: {exc}",
                Lifecycle.REJECTED,
            )

    definition_present, why = _definition_is_substantive(concept)
    if not definition_present:
        run.block(3, "NO_FORMAL_DEFINITION", why, Lifecycle.REJECTED)

    _check_dependencies(run)
    return type_valid, definition_present


def _check_dependencies(run: _Run) -> None:
    """Part of step 3: a concept may only cite what is already ``admitted``.

    A candidate resting on anything else cannot be admitted however good the rest of it is,
    because the citation would import an unestablished concept into an established one.
    """
    concept = run.candidate.concept
    for dependency in concept.dependencies:
        if dependency == concept.canonical_id:
            run.block(
                3,
                "SELF_DEPENDENCY",
                f"{concept.canonical_id} depends on itself",
                Lifecycle.REJECTED,
            )
            continue
        target = run.registry.find(dependency)
        if target is None:
            run.block(
                3,
                "DEPENDENCY_MISSING",
                f"depends on {dependency!r}, which is not registered",
                Lifecycle.REJECTED,
            )
        elif not target.may_be_cited():
            run.block(
                3,
                "DEPENDENCY_NOT_ADMITTED",
                f"cites {dependency!r}, whose status is "
                f"{target.admission_status.value}; a concept may only be cited once it is "
                f"admitted",
                Lifecycle.REJECTED,
            )


def _checks_by_constraint(
    candidate: ConceptCandidate,
) -> Mapping[str, ConstraintCheck]:
    return {c.constraint: c for c in candidate.constraint_checks}


def _step_4_constraints(run: _Run) -> bool:
    concept = run.candidate.concept
    checks = _checks_by_constraint(run.candidate)

    for supplied in run.candidate.constraint_checks:
        if supplied.constraint not in concept.constraints:
            run.note(
                4,
                "CONSTRAINT_CHECK_UNDECLARED",
                f"a check was supplied for {supplied.constraint!r}, which the concept does "
                f"not declare as a constraint",
            )

    if not concept.constraints:
        return True

    all_verified = True
    for constraint in concept.constraints:
        if not normalise_whitespace(constraint):
            all_verified = False
            run.block(
                4,
                "CONSTRAINT_EMPTY",
                "an empty constraint was declared",
                Lifecycle.REJECTED,
            )
            continue
        check = checks.get(constraint)
        if check is None or check.check is None:
            all_verified = False
            run.note(
                4,
                "CONSTRAINT_UNVERIFIED",
                f"constraint {constraint!r} has no executable check and is recorded as "
                f"unverified, not as satisfied",
            )
            continue
        try:
            satisfied = bool(check.check())
        except Exception as exc:  # noqa: BLE001 - the failure itself is the finding
            all_verified = False
            run.block(
                4,
                "CONSTRAINT_CHECK_RAISED",
                f"the check for {constraint!r} raised {type(exc).__name__}: {exc}",
                Lifecycle.REJECTED,
            )
            continue
        if not satisfied:
            all_verified = False
            run.block(
                4,
                "CONSTRAINT_VIOLATED",
                f"constraint {constraint!r} was checked and does not hold",
                Lifecycle.REJECTED,
            )
    return all_verified


def _collect_claims(candidate: ConceptCandidate) -> tuple[PropertyClaim, ...]:
    """The candidate's explicit claims plus any invariant declared on the concept itself.

    An invariant written straight into the concept record with a status but no evidence is
    still a claim, and is adjudicated on exactly the same terms as one supplied explicitly.
    """
    claims = list(candidate.claims)
    stated = {c.statement for c in claims}
    for invariant in candidate.concept.invariants:
        if invariant.statement not in stated:
            claims.append(
                PropertyClaim(
                    statement=invariant.statement,
                    claimed_status=invariant.status,
                    proof=invariant.discharged_by,
                    proof_checked=False,
                )
            )
    return tuple(claims)


def _step_5_obligations(run: _Run, claims: Sequence[PropertyClaim]) -> None:
    """Generate one proof obligation for every claim not already carried by a real proof."""
    concept = run.candidate.concept
    checks = _checks_by_constraint(run.candidate)

    for claim in claims:
        if claim.proof is not None and claim.proof_checked:
            continue
        run.obligations.append(
            Claim(
                statement=claim.statement,
                status=ClaimStatus.CONJECTURED,
                evidence="obligation generated by the minting protocol",
                discharged_by=None,
            )
        )

    for constraint in concept.constraints:
        check = checks.get(constraint)
        if check is None or check.check is None:
            run.obligations.append(
                Claim(
                    statement=f"the declared constraint holds: {constraint}",
                    status=ClaimStatus.CONJECTURED,
                    evidence="no executable check was supplied",
                    discharged_by=None,
                )
            )

    for relation in (*concept.equivalences, *concept.implications):
        if relation.status is ClaimStatus.PROVED:
            continue
        conditions = (
            f" under {', '.join(relation.conditions)}" if relation.conditions else ""
        )
        run.obligations.append(
            Claim(
                statement=(
                    f"the declared relation {relation.kind.value} {relation.other} holds"
                    f"{conditions}"
                ),
                status=relation.status,
                evidence="declared relation, not established at minting time",
                discharged_by=None,
            )
        )

    run.note(
        5,
        "OBLIGATIONS_GENERATED",
        f"{len(run.obligations)} proof obligation(s) generated",
    )


def _step_6_examples(run: _Run) -> _ExampleResults:
    tested = 0
    passed = 0
    for example in run.candidate.examples:
        tested += 1
        try:
            ok = bool(example.run())
        except Exception as exc:  # noqa: BLE001 - the failure itself is the finding
            run.block(
                6,
                "EXAMPLE_RAISED",
                f"example {example.description!r} raised {type(exc).__name__}: {exc}",
                Lifecycle.REJECTED,
            )
            continue
        if ok:
            passed += 1
        else:
            run.block(
                6,
                "EXAMPLE_FAILED",
                f"example {example.description!r} was executed and did not hold",
                Lifecycle.REJECTED,
            )

    if tested == 0:
        run.block(
            6,
            "NO_EXAMPLE",
            "no example was supplied; a concept with no witness is uninhabited as far as "
            "the registry can tell",
            Lifecycle.REJECTED,
        )

    verified: list[bool] = []
    for counterexample in run.candidate.counterexample_tests:
        try:
            refutes = bool(counterexample.run())
        except Exception as exc:  # noqa: BLE001 - the failure itself is the finding
            verified.append(False)
            run.block(
                6,
                "COUNTEREXAMPLE_RAISED",
                f"the counterexample to {counterexample.refutes!r} raised "
                f"{type(exc).__name__}: {exc}",
                Lifecycle.REJECTED,
            )
            continue
        verified.append(refutes)
        if not refutes:
            run.block(
                6,
                "COUNTEREXAMPLE_DOES_NOT_REFUTE",
                f"the witness {counterexample.witness!r} does not refute "
                f"{counterexample.refutes!r}; a boundary recorded where there is none is a "
                f"false record",
                Lifecycle.REJECTED,
            )
    return _ExampleResults(tested, passed, tuple(verified))


def _step_7_compression(run: _Run) -> bool:
    """The step that separates a concept from a synonym.

    A candidate reaching this step has a valid signature, a definition and passing
    examples — by every syntactic measure it is fine. It is rejected anyway if it
    abbreviates nothing, because a well-typed name for something already sayable is a
    synonym, and a registry's value falls with every synonym it holds.
    """
    concept = run.candidate.concept
    evidence_by_structure = {e.structure: e for e in run.candidate.compression}

    for supplied in run.candidate.compression:
        if supplied.structure not in concept.compresses:
            run.note(
                7,
                "COMPRESSION_EVIDENCE_UNDECLARED",
                f"evidence was supplied for {supplied.structure!r}, which the concept does "
                f"not list under `compresses`",
            )

    if not concept.compresses:
        run.block(
            7,
            "COMPRESSES_NOTHING",
            "the concept lists no recurring structure that it abbreviates; a concept that "
            "compresses nothing is a synonym, not an abstraction",
            Lifecycle.DUPLICATE,
        )
        return False

    demonstrated: list[str] = []
    for structure in concept.compresses:
        evidence = evidence_by_structure.get(structure)
        if evidence is None:
            run.note(
                7,
                "COMPRESSION_UNEVIDENCED",
                f"{structure!r} is listed under `compresses` with no supplied evidence; "
                f"the claim is recorded, not accepted",
            )
            continue
        if evidence.demonstrated:
            demonstrated.append(structure)
        else:
            run.note(7, "COMPRESSION_NOT_DEMONSTRATED", evidence.why_not())

    if not demonstrated:
        run.block(
            7,
            "COMPRESSES_NOTHING",
            f"none of the {len(concept.compresses)} claimed compression(s) is "
            f"demonstrated: a structure must recur at {MINIMUM_RECURRENCE}+ sites and the "
            f"concept must be shorter than the structure it replaces. A concept that "
            f"compresses nothing is a synonym, not an abstraction",
            Lifecycle.DUPLICATE,
        )
        return False

    run.note(7, "COMPRESSION_DEMONSTRATED", f"abbreviates {', '.join(demonstrated)}")
    return True


def _step_8_claims(
    run: _Run, claims: Sequence[PropertyClaim]
) -> tuple[AdjudicatedClaim, ...]:
    adjudicated = tuple(adjudicate_claim(claim) for claim in claims)
    for entry in adjudicated:
        if entry.refuted:
            run.block(
                8,
                "CLAIM_REFUTED",
                f"claimed property {entry.statement!r} was tested and failed; it is "
                f"recorded as {entry.status.value}, not as {entry.claimed_status.value}",
                Lifecycle.REJECTED,
            )
        elif entry.status is ClaimStatus.UNSUPPORTED:
            run.block(
                8,
                "CLAIM_UNSUPPORTED",
                f"claimed property {entry.statement!r} is asserted as "
                f"{entry.claimed_status.value} with nothing behind it and is recorded as "
                f"unsupported; declare it as a conjecture or supply evidence",
                Lifecycle.REJECTED,
            )
        elif entry.downgraded:
            run.note(
                8,
                "CLAIM_DOWNGRADED",
                f"{entry.statement!r}: claimed {entry.claimed_status.value}, recorded "
                f"{entry.status.value} ({entry.evidence})",
            )
    return adjudicated


def mint(
    candidate: ConceptCandidate,
    registry: ConceptRegistry,
    *,
    record: bool = True,
    admitted_at: str | None = None,
) -> AdmissionReport:
    """Run the minting protocol over ``candidate`` and return its :class:`AdmissionReport`.

    With ``record=True`` (the default) the outcome is written into ``registry``: an
    admitted concept is walked ``proposed -> defined -> checked -> admitted`` through
    :meth:`ConceptRegistry.transition`, and a rejected or duplicate candidate is recorded in
    its terminal state with the reason in its provenance. Recording rejections matters as
    much as recording admissions — a registry that keeps only its successes cannot tell you
    what has already been tried and refused.

    ``record=False`` leaves the registry untouched, which is what a caller wants when it is
    asking "would this be admitted?" rather than admitting it.
    """
    run = _Run(candidate=candidate, registry=registry)

    search = _step_1_search(run)
    _step_2_novelty(run, search)
    type_valid, definition_present = _step_3_structure(run)
    constraints_verified = _step_4_constraints(run)
    claims = _collect_claims(candidate)
    _step_5_obligations(run, claims)
    examples = _step_6_examples(run)
    compression_demonstrated = _step_7_compression(run)
    adjudicated = _step_8_claims(run, claims)

    findings = tuple(run.findings)
    verdict = resolve_verdict(findings)
    duplicate_of = search.nearest_duplicate if verdict is Lifecycle.DUPLICATE else None

    concept = _fold_results_into_concept(
        concept=candidate.concept,
        adjudicated=adjudicated,
        obligations=tuple(run.obligations),
        counterexamples=candidate.counterexample_tests,
        counterexample_verified=examples.counterexample_verified,
        verdict=verdict,
        duplicate_of=duplicate_of,
        findings=findings,
    )

    report = AdmissionReport(
        candidate_id=candidate.canonical_id,
        search=search,
        type_valid=type_valid,
        definition_present=definition_present,
        constraints_verified=constraints_verified,
        obligations=tuple(run.obligations),
        examples_tested=examples.examples_tested,
        examples_passed=examples.examples_passed,
        counterexamples_tested=examples.counterexamples_tested,
        counterexamples_verified=examples.counterexamples_verified,
        compression_demonstrated=compression_demonstrated,
        claim_adjudications=adjudicated,
        findings=findings,
        verdict=verdict,
        concept=concept,
        duplicate_of=duplicate_of,
    )
    report = replace(
        report, concept=replace(concept, admission_report=report.to_record())
    )

    if record:
        report = replace(
            report,
            concept=_write_to_registry(report, registry, admitted_at),
            recorded=True,
        )
    return report


def _fold_results_into_concept(
    *,
    concept: Concept,
    adjudicated: Sequence[AdjudicatedClaim],
    obligations: Sequence[Claim],
    counterexamples: Sequence[CounterexampleTest],
    counterexample_verified: Sequence[bool],
    verdict: Lifecycle,
    duplicate_of: str | None,
    findings: Sequence[Finding],
) -> Concept:
    """Fold the run's results back into the concept record.

    The adjudicated statuses **replace** whatever the author declared. That replacement is
    the whole mechanism: after minting, the registry states what the evidence supports, not
    what was asserted.
    """
    invariants = tuple(entry.to_claim() for entry in adjudicated)
    recorded_counterexamples = tuple(
        CounterexampleRecord(
            refutes=test.refutes,
            witness=test.witness,
            verified=verified,
        )
        for test, verified in zip(counterexamples, counterexample_verified, strict=True)
    )
    provenance = concept.provenance
    if verdict is Lifecycle.DUPLICATE and duplicate_of is not None:
        provenance = replace(provenance, duplicate_of=duplicate_of)
    if verdict in (Lifecycle.REJECTED, Lifecycle.DUPLICATE):
        provenance = replace(
            provenance,
            rejected_reason="; ".join(f.render() for f in findings if f.blocks()),
        )

    return replace(
        concept,
        invariants=invariants,
        proof_obligations=tuple(obligations),
        counterexamples=recorded_counterexamples or concept.counterexamples,
        provenance=provenance,
    )


def _write_to_registry(
    report: AdmissionReport, registry: ConceptRegistry, admitted_at: str | None
) -> Concept:
    """Insert or update, walking the lifecycle one legal step at a time."""
    concept = replace(report.concept, admission_status=Lifecycle.PROPOSED)
    existing = registry.find(concept.canonical_id)

    if existing is not None:
        if existing.admission_status not in (Lifecycle.REJECTED, Lifecycle.DUPLICATE):
            # The id collision is itself the verdict. Do not disturb the incumbent.
            return report.concept
        registry.replace_concept(concept)
    else:
        registry.add(concept)

    canonical_id = concept.canonical_id
    if report.verdict in (Lifecycle.REJECTED, Lifecycle.DUPLICATE):
        return registry.transition(
            canonical_id,
            report.verdict,
            rejected_reason=report.reason(),
            duplicate_of=report.duplicate_of,
        )

    registry.transition(canonical_id, Lifecycle.DEFINED)
    registry.transition(canonical_id, Lifecycle.CHECKED)
    return registry.transition(
        canonical_id, Lifecycle.ADMITTED, admitted_at=admitted_at
    )


def summarise(reports: Iterable[AdmissionReport]) -> Mapping[Lifecycle, int]:
    """Verdict counts over a batch of minting runs."""
    counts: dict[Lifecycle, int] = {}
    for report in reports:
        counts[report.verdict] = counts.get(report.verdict, 0) + 1
    return counts
