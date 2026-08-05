"""V1 typed concept registry — HML-V1-CONCEPT-001 Phase 2.

``spec/concept_registry.schema.json`` is the contract; this module is an implementation
of it and never the other way round. Every dataclass here carries the schema's field
names verbatim so that a reader can diff the two by eye.

Three commitments, each of which the schema states and this module enforces:

* **A name is only a handle.** ``canonical_id`` and ``aliases`` carry no semantics. Two
  concepts may not share a handle, and a handle collision is an error rather than a
  silent overwrite.
* **A concept may only be cited once it is ``admitted``.** Dependencies of a ``checked``
  or ``admitted`` concept must themselves be ``admitted``; dependency cycles are rejected
  outright, at insertion and again at whole-registry validation.
* **Lifecycle is a walk, not an assignment.** ``proposed -> defined -> checked ->
  admitted``, with ``rejected``, ``duplicate`` and ``deprecated`` terminal. Skipping a
  stage is not expressible through :meth:`ConceptRegistry.transition`.

The claim vocabulary (``proved | tested | conjectured | unsupported``) is mapped onto the
frozen justification contract in :mod:`hamiltonian_lang.v1.epistemic` rather than
duplicating it: ``tested`` is ``Evidence`` and therefore never discharges a goal.

V0 (``hamiltonian_lang.types``, ``hamiltonian_lang.ast.nodes``) is frozen at tag
``hml-v0-baseline`` and is deliberately not imported here.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from hamiltonian_lang.v1.epistemic import DISCHARGES_GOALS, Justification

__all__ = [
    "REGISTRY_VERSION",
    "SCHEMA_PATH",
    "Lifecycle",
    "ClaimStatus",
    "RelationKind",
    "ComputationBackend",
    "CLAIM_JUSTIFICATION",
    "LIFECYCLE_TRANSITIONS",
    "TERMINAL_STATES",
    "Parameter",
    "Claim",
    "Relation",
    "CounterexampleRecord",
    "ComputationMethod",
    "BackendSupport",
    "Provenance",
    "AdmissionRecord",
    "Concept",
    "ConceptRegistry",
    "RegistryError",
    "SchemaValidationError",
    "DuplicateConceptError",
    "AliasCollisionError",
    "UnknownConceptError",
    "DependencyCycleError",
    "UnadmittedDependencyError",
    "LifecycleError",
    "claim_discharges_goal",
    "load_schema",
    "validate_document",
    "normalise_whitespace",
    "normalise_type_signature",
]

#: Version stamped into a registry document this module writes.
REGISTRY_VERSION = "hml-v1-concept-registry-0.1.0"

#: The contract. Read-only from this module's point of view.
SCHEMA_PATH = Path(__file__).resolve().parents[3] / "spec" / "concept_registry.schema.json"

_CANONICAL_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


# ---------------------------------------------------------------------------
# Enumerations — mirrors of the schema's `$defs`
# ---------------------------------------------------------------------------


class Lifecycle(StrEnum):
    """Where a concept sits in the minting protocol. Mirrors ``$defs/lifecycle``."""

    PROPOSED = "proposed"
    DEFINED = "defined"
    CHECKED = "checked"
    ADMITTED = "admitted"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    DEPRECATED = "deprecated"


class ClaimStatus(StrEnum):
    """How well a single claim is established. Mirrors ``$defs/claimStatus``."""

    PROVED = "proved"
    TESTED = "tested"
    CONJECTURED = "conjectured"
    UNSUPPORTED = "unsupported"


class RelationKind(StrEnum):
    """Mirrors ``$defs/relation.kind``."""

    EQUIVALENT_TO = "equivalent_to"
    IMPLIES = "implies"
    IMPLIED_BY = "implied_by"
    SPECIALISES = "specialises"
    GENERALISES = "generalises"
    DISJOINT_FROM = "disjoint_from"


class ComputationBackend(StrEnum):
    """Mirrors ``$defs/concept.computation_methods.items.backend``."""

    SYMPY = "sympy"
    PYTHON = "python"
    STAN = "stan"
    LEAN = "lean"
    NONE = "none"


#: Registry claim vocabulary mapped onto the frozen epistemic contract. ``tested`` is
#: ``Evidence``: numerical agreement is evidence and is never promoted to a proof.
CLAIM_JUSTIFICATION: dict[ClaimStatus, Justification] = {
    ClaimStatus.PROVED: Justification.PROOF,
    ClaimStatus.TESTED: Justification.EVIDENCE,
    ClaimStatus.CONJECTURED: Justification.NONE,
    ClaimStatus.UNSUPPORTED: Justification.NONE,
}

#: The only legal lifecycle moves. There is no edge back out of a terminal state, and no
#: edge that skips a stage: a concept cannot become ``admitted`` without being ``checked``.
LIFECYCLE_TRANSITIONS: dict[Lifecycle, frozenset[Lifecycle]] = {
    Lifecycle.PROPOSED: frozenset(
        {Lifecycle.DEFINED, Lifecycle.REJECTED, Lifecycle.DUPLICATE}
    ),
    Lifecycle.DEFINED: frozenset(
        {Lifecycle.CHECKED, Lifecycle.REJECTED, Lifecycle.DUPLICATE}
    ),
    Lifecycle.CHECKED: frozenset(
        {Lifecycle.ADMITTED, Lifecycle.REJECTED, Lifecycle.DUPLICATE}
    ),
    Lifecycle.ADMITTED: frozenset({Lifecycle.DEPRECATED}),
    Lifecycle.REJECTED: frozenset(),
    Lifecycle.DUPLICATE: frozenset(),
    Lifecycle.DEPRECATED: frozenset(),
}

#: States with no outgoing edge.
TERMINAL_STATES: frozenset[Lifecycle] = frozenset(
    {Lifecycle.REJECTED, Lifecycle.DUPLICATE, Lifecycle.DEPRECATED}
)

#: Statuses at which a concept's own dependencies must already be ``admitted``. A concept
#: may be *proposed* while resting on something still being defined; it may not be checked
#: or admitted on that basis.
_REQUIRES_ADMITTED_DEPENDENCIES: frozenset[Lifecycle] = frozenset(
    {Lifecycle.CHECKED, Lifecycle.ADMITTED}
)


def claim_discharges_goal(status: ClaimStatus) -> bool:
    """Whether a claim at ``status`` closes an obligation.

    Delegated to the frozen table in :mod:`hamiltonian_lang.v1.epistemic` so that the
    registry cannot drift from the epistemic contract.
    """
    return DISCHARGES_GOALS[CLAIM_JUSTIFICATION[status]]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RegistryError(Exception):
    """Base class for every registry rejection."""


class SchemaValidationError(RegistryError):
    """A document did not validate against ``spec/concept_registry.schema.json``."""


class DuplicateConceptError(RegistryError):
    """A ``canonical_id`` was offered twice."""


class AliasCollisionError(RegistryError):
    """A handle would resolve to two different concepts."""


class UnknownConceptError(RegistryError):
    """A ``canonical_id`` or alias is not in the registry."""


class DependencyCycleError(RegistryError):
    """The dependency graph is not acyclic. The cycle is named in the message."""


class UnadmittedDependencyError(RegistryError):
    """A concept cites something that is not ``admitted``."""


class LifecycleError(RegistryError):
    """An illegal lifecycle move."""


# ---------------------------------------------------------------------------
# Normalisation helpers, shared with the minting protocol
# ---------------------------------------------------------------------------


def normalise_whitespace(text: str) -> str:
    """Collapse all runs of whitespace to a single space and strip the ends."""
    return " ".join(text.split())


def normalise_type_signature(signature: str) -> str:
    """A whitespace-insensitive form of a type signature, for comparison only.

    This is *not* a type checker. It exists so that ``A * B -> C`` and ``A*B->C`` compare
    equal when the minting protocol searches for an existing concept.
    """
    text = normalise_whitespace(signature)
    text = text.replace(" ->", "->").replace("-> ", "->")
    for token in ("[", "]", "(", ")", ",", "*"):
        text = text.replace(f" {token}", token).replace(f"{token} ", token)
    return text


def _put(doc: dict[str, Any], key: str, value: Any) -> None:
    """Write ``key`` only when there is something to write.

    Absence is meaningful in this schema — ``backend_support`` with no entry for a backend
    means *unsupported*, never *assumed fine* — so an empty collection is written as an
    omission rather than as an empty container claiming coverage.
    """
    if value:
        doc[key] = value


# ---------------------------------------------------------------------------
# Record types — one per `$defs` entry in the schema
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Parameter:
    """A typed role, not a position. Roles are meaning (V0 decision D-003)."""

    name: str
    type: str
    role: str
    optional: bool | None = None

    def to_json(self) -> dict[str, Any]:
        doc: dict[str, Any] = {"name": self.name, "type": self.type, "role": self.role}
        if self.optional is not None:
            doc["optional"] = self.optional
        return doc

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> Parameter:
        return cls(
            name=doc["name"],
            type=doc["type"],
            role=doc["role"],
            optional=doc.get("optional"),
        )


@dataclass(frozen=True)
class Claim:
    """A statement together with the grounds on which it is held.

    ``discharged_by is None`` means NOT established, and is always serialised explicitly
    as ``null`` — an omitted field could be misread as an oversight, whereas an explicit
    null is a record.
    """

    statement: str
    status: ClaimStatus
    evidence: str | None = None
    discharged_by: str | None = None

    @property
    def justification(self) -> Justification:
        return CLAIM_JUSTIFICATION[self.status]

    def discharges_goal(self) -> bool:
        return claim_discharges_goal(self.status)

    def to_json(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "statement": self.statement,
            "status": self.status.value,
            "discharged_by": self.discharged_by,
        }
        if self.evidence is not None:
            doc["evidence"] = self.evidence
        return doc

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> Claim:
        return cls(
            statement=doc["statement"],
            status=ClaimStatus(doc["status"]),
            evidence=doc.get("evidence"),
            discharged_by=doc.get("discharged_by"),
        )


@dataclass(frozen=True)
class Relation:
    """A typed relation to another concept, with its own claim status.

    ``conditions`` exists to prevent the specific error of asserting an unconditional
    equivalence that in fact holds only under side conditions.
    """

    other: str
    kind: RelationKind
    status: ClaimStatus
    conditions: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "other": self.other,
            "kind": self.kind.value,
            "status": self.status.value,
        }
        _put(doc, "conditions", list(self.conditions))
        return doc

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> Relation:
        return cls(
            other=doc["other"],
            kind=RelationKind(doc["kind"]),
            status=ClaimStatus(doc["status"]),
            conditions=tuple(doc.get("conditions", ())),
        )


@dataclass(frozen=True)
class CounterexampleRecord:
    """A witness refuting a NEARBY claim — this is how a concept's boundary is recorded."""

    refutes: str
    witness: str
    verified: bool | None = None

    def to_json(self) -> dict[str, Any]:
        doc: dict[str, Any] = {"refutes": self.refutes, "witness": self.witness}
        if self.verified is not None:
            doc["verified"] = self.verified
        return doc

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> CounterexampleRecord:
        return cls(
            refutes=doc["refutes"], witness=doc["witness"], verified=doc.get("verified")
        )


@dataclass(frozen=True)
class ComputationMethod:
    """``exact=False`` means numerical evidence, which is NOT proof."""

    method: str
    backend: ComputationBackend
    exact: bool | None = None

    def to_json(self) -> dict[str, Any]:
        doc: dict[str, Any] = {"method": self.method, "backend": self.backend.value}
        if self.exact is not None:
            doc["exact"] = self.exact
        return doc

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> ComputationMethod:
        return cls(
            method=doc["method"],
            backend=ComputationBackend(doc["backend"]),
            exact=doc.get("exact"),
        )


@dataclass(frozen=True)
class BackendSupport:
    """What survives translation to one backend.

    ``verified_by_toolchain`` is true ONLY if a real compiler accepted the output. An
    unproved theorem is never labelled verified.
    """

    supported: bool = False
    losses: tuple[str, ...] = ()
    verified_by_toolchain: bool = False

    def to_json(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "supported": self.supported,
            "verified_by_toolchain": self.verified_by_toolchain,
        }
        _put(doc, "losses", list(self.losses))
        return doc

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> BackendSupport:
        return cls(
            supported=bool(doc.get("supported", False)),
            losses=tuple(doc.get("losses", ())),
            verified_by_toolchain=bool(doc.get("verified_by_toolchain", False)),
        )


@dataclass(frozen=True)
class Provenance:
    """Who proposed it, when, and — if it did not survive — why not."""

    proposed_by: str
    proposed_at: str
    source: str | None = None
    admitted_at: str | None = None
    rejected_reason: str | None = None
    duplicate_of: str | None = None

    def to_json(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at,
        }
        for key in ("source", "admitted_at", "rejected_reason", "duplicate_of"):
            value = getattr(self, key)
            if value is not None:
                doc[key] = value
        return doc

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> Provenance:
        return cls(
            proposed_by=doc["proposed_by"],
            proposed_at=doc["proposed_at"],
            source=doc.get("source"),
            admitted_at=doc.get("admitted_at"),
            rejected_reason=doc.get("rejected_reason"),
            duplicate_of=doc.get("duplicate_of"),
        )


#: The fields the schema requires to be present before a concept may be `admitted`.
_ADMISSION_RECORD_FIELDS: tuple[str, ...] = (
    "registry_search_performed",
    "equality_matches",
    "equivalence_matches",
    "renaming_matches",
    "specialisation_of",
    "generalisation_of",
    "type_valid",
    "definition_present",
    "constraints_verified",
    "obligations_generated",
    "examples_tested",
    "examples_passed",
    "counterexamples_tested",
    "compression_demonstrated",
    "verdict",
)


@dataclass(frozen=True)
class AdmissionRecord:
    """The serialisable residue of a minting run.

    :mod:`hamiltonian_lang.v1.minting` produces a much richer report; this is the part of
    it the schema stores. Every field must be present before ``admitted``, which
    :meth:`is_complete` checks.
    """

    registry_search_performed: bool | None = None
    equality_matches: tuple[str, ...] | None = None
    equivalence_matches: tuple[str, ...] | None = None
    renaming_matches: tuple[str, ...] | None = None
    specialisation_of: tuple[str, ...] | None = None
    generalisation_of: tuple[str, ...] | None = None
    type_valid: bool | None = None
    definition_present: bool | None = None
    constraints_verified: bool | None = None
    obligations_generated: int | None = None
    examples_tested: int | None = None
    examples_passed: int | None = None
    counterexamples_tested: int | None = None
    compression_demonstrated: bool | None = None
    verdict: Lifecycle | None = None

    def is_complete(self) -> bool:
        """True when every schema field is populated, as admission requires."""
        return all(getattr(self, name) is not None for name in _ADMISSION_RECORD_FIELDS)

    def missing_fields(self) -> tuple[str, ...]:
        return tuple(
            name for name in _ADMISSION_RECORD_FIELDS if getattr(self, name) is None
        )

    def to_json(self) -> dict[str, Any]:
        doc: dict[str, Any] = {}
        for name in _ADMISSION_RECORD_FIELDS:
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, Lifecycle):
                doc[name] = value.value
            elif isinstance(value, tuple):
                doc[name] = list(value)
            else:
                doc[name] = value
        return doc

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> AdmissionRecord:
        def seq(key: str) -> tuple[str, ...] | None:
            value = doc.get(key)
            return None if value is None else tuple(value)

        verdict = doc.get("verdict")
        return cls(
            registry_search_performed=doc.get("registry_search_performed"),
            equality_matches=seq("equality_matches"),
            equivalence_matches=seq("equivalence_matches"),
            renaming_matches=seq("renaming_matches"),
            specialisation_of=seq("specialisation_of"),
            generalisation_of=seq("generalisation_of"),
            type_valid=doc.get("type_valid"),
            definition_present=doc.get("definition_present"),
            constraints_verified=doc.get("constraints_verified"),
            obligations_generated=doc.get("obligations_generated"),
            examples_tested=doc.get("examples_tested"),
            examples_passed=doc.get("examples_passed"),
            counterexamples_tested=doc.get("counterexamples_tested"),
            compression_demonstrated=doc.get("compression_demonstrated"),
            verdict=None if verdict is None else Lifecycle(verdict),
        )


# ---------------------------------------------------------------------------
# The concept itself
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Concept:
    """One entry in the typed registry.

    Field names are the schema's property names verbatim. Sequences are tuples so that a
    concept handed out by the registry cannot be mutated behind the registry's back.
    """

    canonical_id: str
    namespace: str
    version: str
    type_signature: str
    domain: str
    codomain: str
    formal_definition: str
    provenance: Provenance
    parameters: tuple[Parameter, ...] = ()
    admission_status: Lifecycle = Lifecycle.PROPOSED
    aliases: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    invariants: tuple[Claim, ...] = ()
    equivalences: tuple[Relation, ...] = ()
    implications: tuple[Relation, ...] = ()
    counterexamples: tuple[CounterexampleRecord, ...] = ()
    proof_obligations: tuple[Claim, ...] = ()
    computation_methods: tuple[ComputationMethod, ...] = ()
    backend_support: dict[str, BackendSupport] = field(default_factory=dict)
    dependencies: tuple[str, ...] = ()
    compresses: tuple[str, ...] = ()
    admission_report: AdmissionRecord | None = None

    def __post_init__(self) -> None:
        if not _CANONICAL_ID.match(self.canonical_id):
            raise RegistryError(
                f"canonical_id {self.canonical_id!r} does not match the schema pattern "
                f"^[A-Za-z][A-Za-z0-9_]*$"
            )

    # -- handles ----------------------------------------------------------
    @property
    def handles(self) -> tuple[str, ...]:
        """Every string that resolves to this concept. Handles carry no semantics."""
        return (self.canonical_id, *self.aliases)

    def may_be_cited(self) -> bool:
        """A concept may only be cited by another once ``admitted``."""
        return self.admission_status is Lifecycle.ADMITTED

    def with_status(self, status: Lifecycle) -> Concept:
        return replace(self, admission_status=status)

    def replace(self, **changes: Any) -> Concept:
        return replace(self, **changes)

    # -- serialisation ----------------------------------------------------
    def to_json(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "canonical_id": self.canonical_id,
            "namespace": self.namespace,
            "version": self.version,
            "type_signature": self.type_signature,
            "domain": self.domain,
            "codomain": self.codomain,
            "formal_definition": self.formal_definition,
            "parameters": [p.to_json() for p in self.parameters],
            "admission_status": self.admission_status.value,
            "provenance": self.provenance.to_json(),
        }
        _put(doc, "aliases", list(self.aliases))
        _put(doc, "constraints", list(self.constraints))
        _put(doc, "invariants", [c.to_json() for c in self.invariants])
        _put(doc, "equivalences", [r.to_json() for r in self.equivalences])
        _put(doc, "implications", [r.to_json() for r in self.implications])
        _put(doc, "counterexamples", [c.to_json() for c in self.counterexamples])
        _put(doc, "proof_obligations", [c.to_json() for c in self.proof_obligations])
        _put(doc, "computation_methods", [m.to_json() for m in self.computation_methods])
        _put(
            doc,
            "backend_support",
            {name: s.to_json() for name, s in self.backend_support.items()},
        )
        _put(doc, "dependencies", list(self.dependencies))
        _put(doc, "compresses", list(self.compresses))
        if self.admission_report is not None:
            doc["admission_report"] = self.admission_report.to_json()
        return doc

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> Concept:
        report = doc.get("admission_report")
        return cls(
            canonical_id=doc["canonical_id"],
            namespace=doc["namespace"],
            version=doc["version"],
            type_signature=doc["type_signature"],
            domain=doc["domain"],
            codomain=doc["codomain"],
            formal_definition=doc["formal_definition"],
            provenance=Provenance.from_json(doc["provenance"]),
            parameters=tuple(Parameter.from_json(p) for p in doc.get("parameters", ())),
            admission_status=Lifecycle(doc["admission_status"]),
            aliases=tuple(doc.get("aliases", ())),
            constraints=tuple(doc.get("constraints", ())),
            invariants=tuple(Claim.from_json(c) for c in doc.get("invariants", ())),
            equivalences=tuple(
                Relation.from_json(r) for r in doc.get("equivalences", ())
            ),
            implications=tuple(
                Relation.from_json(r) for r in doc.get("implications", ())
            ),
            counterexamples=tuple(
                CounterexampleRecord.from_json(c) for c in doc.get("counterexamples", ())
            ),
            proof_obligations=tuple(
                Claim.from_json(c) for c in doc.get("proof_obligations", ())
            ),
            computation_methods=tuple(
                ComputationMethod.from_json(m) for m in doc.get("computation_methods", ())
            ),
            backend_support={
                name: BackendSupport.from_json(entry)
                for name, entry in doc.get("backend_support", {}).items()
            },
            dependencies=tuple(doc.get("dependencies", ())),
            compresses=tuple(doc.get("compresses", ())),
            admission_report=None if report is None else AdmissionRecord.from_json(report),
        )


# ---------------------------------------------------------------------------
# Schema access
# ---------------------------------------------------------------------------

_SCHEMA_CACHE: dict[Path, Any] = {}


def load_schema(path: Path | None = None) -> Any:
    """Load and cache ``spec/concept_registry.schema.json``."""
    target = (path or SCHEMA_PATH).resolve()
    cached = _SCHEMA_CACHE.get(target)
    if cached is None:
        if not target.exists():
            raise SchemaValidationError(f"concept registry schema not found at {target}")
        cached = json.loads(target.read_text(encoding="utf-8"))
        _SCHEMA_CACHE[target] = cached
    return cached


def validate_document(document: Mapping[str, Any], *, schema_path: Path | None = None) -> None:
    """Validate a registry document, raising :class:`SchemaValidationError` on failure.

    ``jsonschema`` is imported here rather than at module import so that the registry
    remains usable for in-memory work when the dev extra is not installed; validation
    itself is never silently skipped.
    """
    try:
        import jsonschema
    except ModuleNotFoundError as exc:  # pragma: no cover - dev extra always present
        raise SchemaValidationError(
            "jsonschema is required to validate a concept registry document; "
            "install the 'dev' extra"
        ) from exc

    validator = jsonschema.Draft202012Validator(load_schema(schema_path))
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    if errors:
        rendered = "\n".join(
            f"  at /{'/'.join(str(p) for p in e.absolute_path)}: {e.message}"
            for e in errors
        )
        raise SchemaValidationError(
            f"registry document failed schema validation:\n{rendered}"
        )


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------


class ConceptRegistry:
    """An ordered collection of :class:`Concept` with the citation rules enforced.

    Insertion order is preserved because a registry document is read by people as well as
    by machines, and a stable order makes a diff readable.
    """

    def __init__(
        self,
        concepts: Iterable[Concept] = (),
        *,
        registry_version: str = REGISTRY_VERSION,
    ) -> None:
        self.registry_version = registry_version
        self._concepts: dict[str, Concept] = {}
        for concept in concepts:
            self.add(concept)

    # -- container protocol ----------------------------------------------
    def __len__(self) -> int:
        return len(self._concepts)

    def __iter__(self) -> Iterator[Concept]:
        return iter(self._concepts.values())

    def __contains__(self, canonical_id: object) -> bool:
        return canonical_id in self._concepts

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConceptRegistry):
            return NotImplemented
        return (
            self.registry_version == other.registry_version
            and list(self._concepts.items()) == list(other._concepts.items())
        )

    def __repr__(self) -> str:
        return (
            f"ConceptRegistry(registry_version={self.registry_version!r}, "
            f"concepts={len(self._concepts)})"
        )

    @property
    def concepts(self) -> tuple[Concept, ...]:
        return tuple(self._concepts.values())

    @property
    def admitted(self) -> tuple[Concept, ...]:
        """Only these may be cited."""
        return tuple(c for c in self._concepts.values() if c.may_be_cited())

    # -- insertion --------------------------------------------------------
    def add(self, concept: Concept) -> Concept:
        """Insert ``concept``, rejecting handle collisions, self-loops and cycles.

        Dependency *existence* is deliberately not checked here: concepts arrive in some
        order, and a registry document may name a dependency that has not been read yet.
        Existence and admitted-status are checked by :meth:`check_dependencies`, by
        :meth:`transition` on the way to ``checked``/``admitted``, and by
        :meth:`validate`. Cycles, by contrast, are checked immediately, because a cycle is
        never repaired by reading more of the document.
        """
        if concept.canonical_id in self._concepts:
            raise DuplicateConceptError(
                f"canonical_id {concept.canonical_id!r} is already registered; "
                f"a registry never silently overwrites an entry"
            )
        self._check_handles(concept)
        if concept.canonical_id in concept.dependencies:
            raise DependencyCycleError(
                f"{concept.canonical_id} depends on itself; a concept cannot rest on "
                f"itself"
            )
        self._concepts[concept.canonical_id] = concept
        try:
            self._assert_acyclic()
        except DependencyCycleError:
            del self._concepts[concept.canonical_id]
            raise
        return concept

    def replace_concept(self, concept: Concept) -> Concept:
        """Replace an existing entry, re-running the same structural checks."""
        if concept.canonical_id not in self._concepts:
            raise UnknownConceptError(f"{concept.canonical_id!r} is not registered")
        previous = self._concepts[concept.canonical_id]
        del self._concepts[concept.canonical_id]
        try:
            return self.add(concept)
        except RegistryError:
            self._concepts[concept.canonical_id] = previous
            raise

    def _insert_unchecked(self, concept: Concept) -> None:
        """Used only by :meth:`from_json`, which validates the whole document after."""
        if concept.canonical_id in self._concepts:
            raise DuplicateConceptError(
                f"canonical_id {concept.canonical_id!r} appears twice in the document"
            )
        self._concepts[concept.canonical_id] = concept

    def _check_handles(self, concept: Concept) -> None:
        for handle in concept.handles:
            owner = self._owner_of_handle(handle)
            if owner is not None and owner.canonical_id != concept.canonical_id:
                raise AliasCollisionError(
                    f"handle {handle!r} already resolves to {owner.canonical_id!r}; "
                    f"a handle carries no semantics and may name exactly one concept"
                )

    def _owner_of_handle(self, handle: str) -> Concept | None:
        direct = self._concepts.get(handle)
        if direct is not None:
            return direct
        for concept in self._concepts.values():
            if handle in concept.aliases:
                return concept
        return None

    # -- lookup -----------------------------------------------------------
    def find(self, canonical_id: str) -> Concept | None:
        return self._concepts.get(canonical_id)

    def get(self, canonical_id: str) -> Concept:
        concept = self._concepts.get(canonical_id)
        if concept is None:
            raise UnknownConceptError(f"no concept with canonical_id {canonical_id!r}")
        return concept

    def by_alias(self, alias: str) -> Concept:
        """Resolve an alias. A canonical_id is not an alias; use :meth:`get` for that."""
        for concept in self._concepts.values():
            if alias in concept.aliases:
                return concept
        raise UnknownConceptError(f"no concept carries the alias {alias!r}")

    def lookup(self, handle: str) -> Concept:
        """Resolve a handle, canonical_id first, then alias."""
        concept = self._concepts.get(handle)
        if concept is not None:
            return concept
        return self.by_alias(handle)

    def may_be_cited(self, canonical_id: str) -> bool:
        concept = self.find(canonical_id)
        return concept is not None and concept.may_be_cited()

    # -- lifecycle --------------------------------------------------------
    def transition(
        self,
        canonical_id: str,
        to: Lifecycle,
        *,
        admitted_at: str | None = None,
        rejected_reason: str | None = None,
        duplicate_of: str | None = None,
    ) -> Concept:
        """Move one concept one legal step along the lifecycle.

        The move to ``checked`` or ``admitted`` additionally requires that every
        dependency exists and is itself ``admitted``.
        """
        concept = self.get(canonical_id)
        allowed = LIFECYCLE_TRANSITIONS[concept.admission_status]
        if to not in allowed:
            legal = ", ".join(sorted(s.value for s in allowed)) or "nothing (terminal)"
            raise LifecycleError(
                f"{canonical_id}: {concept.admission_status.value} -> {to.value} is not a "
                f"legal transition; from {concept.admission_status.value} the only legal "
                f"moves are {legal}"
            )
        if to in _REQUIRES_ADMITTED_DEPENDENCIES:
            self.check_dependencies(canonical_id)

        provenance = concept.provenance
        if admitted_at is not None:
            provenance = replace(provenance, admitted_at=admitted_at)
        if rejected_reason is not None:
            provenance = replace(provenance, rejected_reason=rejected_reason)
        if duplicate_of is not None:
            provenance = replace(provenance, duplicate_of=duplicate_of)

        updated = replace(concept, admission_status=to, provenance=provenance)
        self._concepts[canonical_id] = updated
        return updated

    # -- dependencies -----------------------------------------------------
    def check_dependencies(self, canonical_id: str) -> None:
        """Every dependency must exist, be ``admitted``, and lie on no cycle."""
        concept = self.get(canonical_id)
        for dependency in concept.dependencies:
            target = self.find(dependency)
            if target is None:
                raise UnknownConceptError(
                    f"{canonical_id} depends on {dependency!r}, which is not registered"
                )
            if not target.may_be_cited():
                raise UnadmittedDependencyError(
                    f"{canonical_id} cites {dependency!r}, whose status is "
                    f"{target.admission_status.value}; a concept may only be cited once "
                    f"it is admitted"
                )
        self.dependency_order(canonical_id)

    def dependency_order(self, canonical_id: str) -> tuple[str, ...]:
        """Transitive dependencies of ``canonical_id`` in a valid build order.

        The concept itself is the last element. Raises :class:`DependencyCycleError` if
        the reachable subgraph contains a cycle, naming the cycle.
        """
        self.get(canonical_id)
        order: list[str] = []
        state: dict[str, int] = {}  # 0 = in progress, 1 = done
        stack: list[str] = []

        def visit(node: str) -> None:
            mark = state.get(node)
            if mark == 1:
                return
            if mark == 0:
                cycle = stack[stack.index(node) :] + [node]
                raise DependencyCycleError(
                    "dependency cycle: " + " -> ".join(cycle)
                )
            state[node] = 0
            stack.append(node)
            concept = self.find(node)
            if concept is not None:
                for dependency in concept.dependencies:
                    visit(dependency)
            stack.pop()
            state[node] = 1
            order.append(node)

        visit(canonical_id)
        return tuple(order)

    def _assert_acyclic(self) -> None:
        state: dict[str, int] = {}
        stack: list[str] = []

        def visit(node: str) -> None:
            mark = state.get(node)
            if mark == 1:
                return
            if mark == 0:
                cycle = stack[stack.index(node) :] + [node]
                raise DependencyCycleError("dependency cycle: " + " -> ".join(cycle))
            state[node] = 0
            stack.append(node)
            concept = self._concepts.get(node)
            if concept is not None:
                for dependency in concept.dependencies:
                    visit(dependency)
            stack.pop()
            state[node] = 1

        for canonical_id in list(self._concepts):
            visit(canonical_id)

    def build_order(self) -> tuple[str, ...]:
        """A topological order over the whole registry."""
        self._assert_acyclic()
        order: list[str] = []
        seen: set[str] = set()
        for canonical_id in self._concepts:
            for node in self.dependency_order(canonical_id):
                if node not in seen and node in self._concepts:
                    seen.add(node)
                    order.append(node)
        return tuple(order)

    # -- whole-registry validation ---------------------------------------
    def validate(self) -> None:
        """Check every registry-level invariant. Raises on the first violation.

        1. handles resolve to exactly one concept
        2. the dependency graph is acyclic
        3. every dependency names a registered concept
        4. dependencies of a ``checked`` or ``admitted`` concept are themselves admitted
        """
        seen: dict[str, str] = {}
        for concept in self._concepts.values():
            for handle in concept.handles:
                owner = seen.get(handle)
                if owner is not None and owner != concept.canonical_id:
                    raise AliasCollisionError(
                        f"handle {handle!r} resolves to both {owner!r} and "
                        f"{concept.canonical_id!r}"
                    )
                seen[handle] = concept.canonical_id

        self._assert_acyclic()

        for concept in self._concepts.values():
            for dependency in concept.dependencies:
                target = self.find(dependency)
                if target is None:
                    raise UnknownConceptError(
                        f"{concept.canonical_id} depends on {dependency!r}, which is not "
                        f"registered"
                    )
                if (
                    concept.admission_status in _REQUIRES_ADMITTED_DEPENDENCIES
                    and not target.may_be_cited()
                ):
                    raise UnadmittedDependencyError(
                        f"{concept.canonical_id} is {concept.admission_status.value} but "
                        f"cites {dependency!r}, whose status is "
                        f"{target.admission_status.value}"
                    )

    # -- serialisation ----------------------------------------------------
    def to_json(self, *, validate_schema: bool = True) -> dict[str, Any]:
        document: dict[str, Any] = {
            "registry_version": self.registry_version,
            "concepts": [c.to_json() for c in self._concepts.values()],
        }
        if validate_schema:
            validate_document(document)
        return document

    @classmethod
    def from_json(
        cls,
        document: Mapping[str, Any],
        *,
        validate_schema: bool = True,
        validate_registry: bool = True,
    ) -> ConceptRegistry:
        if validate_schema:
            validate_document(document)
        registry = cls(registry_version=document["registry_version"])
        concepts: Sequence[Mapping[str, Any]] = document.get("concepts", ())
        for entry in concepts:
            registry._insert_unchecked(Concept.from_json(entry))
        if validate_registry:
            registry.validate()
        return registry

    def save(self, path: Path | str, *, validate_schema: bool = True) -> Path:
        target = Path(path)
        document = self.to_json(validate_schema=validate_schema)
        target.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return target

    @classmethod
    def load(
        cls,
        path: Path | str,
        *,
        validate_schema: bool = True,
        validate_registry: bool = True,
    ) -> ConceptRegistry:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_json(
            document,
            validate_schema=validate_schema,
            validate_registry=validate_registry,
        )
