"""Hash-chained events — Phase 7, the record half of the append-only ledger.

:mod:`~hamiltonian_lang.improvement.ledger` owns the file; this module owns the *record*
and the hashing, so that an event can be built, hashed and checked without any storage
at all.

One hashing scheme, not two
---------------------------
:mod:`hamiltonian_lang.backends.canonical` already fixes how this project turns a
structure into bytes and bytes into an identity:

* ``json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=True)``
* ``hashlib.sha256(blob.encode("ascii")).hexdigest()``

:func:`canonical_blob` and :func:`sha256_hex` reproduce exactly that, and
``tests/improvement/test_events.py::test_event_hashing_agrees_with_content_hash``
recomputes a real module's :func:`~hamiltonian_lang.backends.canonical.content_hash`
through this module's functions and asserts byte equality. If the compiler's convention
ever changes, that test fails rather than the two schemes drifting apart in silence.

What the chain does and does not detect
---------------------------------------
Each event commits to its predecessor, so editing, deleting or reordering a historical
line invalidates every event after it and is detected by
:meth:`~hamiltonian_lang.improvement.ledger.EventLedger.verify`.

A hash chain alone cannot detect **truncation of the tail**: a prefix of a valid chain is
itself a valid chain. That is a real limitation, it is stated here rather than glossed,
and :meth:`~hamiltonian_lang.improvement.ledger.EventLedger.checkpoint` exists precisely
to close it by anchoring the length and the tail hash outside the file.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

__all__ = [
    "EVENT_SCHEMA_VERSION",
    "GENESIS_HASH",
    "EventType",
    "Event",
    "canonical_blob",
    "sha256_hex",
    "utc_now",
    "NonSerialisableValue",
]

#: Bumped whenever the hashed body of an event changes shape. Old lines keep their own
#: version, so a mixed-version ledger stays verifiable.
EVENT_SCHEMA_VERSION = "hml-event-1.0.0"

#: ``previous_event_hash`` of the first event in a ledger.
GENESIS_HASH = "0" * 64


class EventType(StrEnum):
    """The closed set of things that can happen to an episode.

    Closed on purpose: an unrecognised event type in a historical line is a signal that
    the file was written by software this build does not understand, and that is worth
    surfacing rather than accepting.
    """

    EPISODE_CREATED = "EPISODE_CREATED"
    TASK_VALIDATED = "TASK_VALIDATED"
    MODEL_GENERATED = "MODEL_GENERATED"
    PARSE_ATTEMPTED = "PARSE_ATTEMPTED"
    DIAGNOSTIC_ISSUED = "DIAGNOSTIC_ISSUED"
    REPAIR_GENERATED = "REPAIR_GENERATED"
    TYPE_CHECKED = "TYPE_CHECKED"
    SEMANTICALLY_COMPARED = "SEMANTICALLY_COMPARED"
    VERIFIER_EXECUTED = "VERIFIER_EXECUTED"
    EPISODE_CLASSIFIED = "EPISODE_CLASSIFIED"
    MEMORY_ROUTED = "MEMORY_ROUTED"
    EXPERIMENT_EVALUATED = "EXPERIMENT_EVALUATED"
    PROMOTION_DECIDED = "PROMOTION_DECIDED"


class NonSerialisableValue(TypeError):
    """Raised when a payload contains something that has no canonical byte form.

    Refusing is the point. Coercing an arbitrary object to ``str`` would produce a hash
    over its memory address, and the chain would then be unverifiable on replay while
    still looking sound.
    """


def _check_serialisable(value: Any, path: str = "payload") -> None:
    if value is None or isinstance(value, bool | int | str):
        return
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise NonSerialisableValue(
                f"{path}: {value!r} has no canonical JSON form; record it as a string "
                f"if the value itself is the fact worth keeping"
            )
        return
    if isinstance(value, dict):
        for key, sub in value.items():
            if not isinstance(key, str):
                raise NonSerialisableValue(
                    f"{path}: key {key!r} is not a string; key order would not be "
                    f"deterministic"
                )
            _check_serialisable(sub, f"{path}.{key}")
        return
    if isinstance(value, list | tuple):
        for i, sub in enumerate(value):
            _check_serialisable(sub, f"{path}[{i}]")
        return
    raise NonSerialisableValue(
        f"{path}: {type(value).__name__} is not JSON-representable; convert it "
        f"explicitly so the conversion is visible in the record"
    )


def canonical_blob(value: Any) -> str:
    """Deterministic JSON bytes for ``value``.

    Identical to the serialisation in :func:`hamiltonian_lang.backends.canonical.canonical_json`.
    Tuples serialise as lists, so a payload built from tuples and the same payload built
    from lists hash identically -- which is what a reader comparing two runs expects.
    """
    _check_serialisable(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(blob: str) -> str:
    """SHA-256 of ``blob``, encoded exactly as the canonical backend encodes it."""
    return hashlib.sha256(blob.encode("ascii")).hexdigest()


def utc_now() -> str:
    """Current time as an ISO-8601 UTC string.

    Callers that need a reproducible ledger pass their own timestamps instead; the
    timestamp is inside the hashed body, so a wall clock would make replay
    non-deterministic.
    """
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Event:
    """One immutable line of the ledger.

    ``event_id`` encodes the writer-assigned position (``ev-00000007``). It is part of
    the hashed body, so a line moved to a different position fails verification even if
    its own contents are untouched.
    """

    event_id: str
    episode_id: str
    event_type: EventType
    timestamp: str
    payload: dict[str, Any]
    previous_event_hash: str
    event_hash: str
    schema_version: str = EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id is required: it fixes the event's position")
        if not self.episode_id:
            raise ValueError("episode_id is required: an unattributed event is not provenance")
        if not self.timestamp:
            raise ValueError("timestamp is required")
        if len(self.previous_event_hash) != 64:
            raise ValueError(
                f"previous_event_hash must be a 64-character digest, got "
                f"{self.previous_event_hash!r}"
            )
        _check_serialisable(self.payload)
        expected = self.recompute_hash()
        if self.event_hash != expected:
            raise ValueError(
                f"event_hash does not commit to this event's contents "
                f"(stored {self.event_hash!r}, recomputed {expected!r})"
            )

    # -- hashing -----------------------------------------------------------------

    def body(self) -> dict[str, Any]:
        """Everything the hash commits to. ``event_hash`` itself is excluded."""
        return {
            "event_id": self.event_id,
            "episode_id": self.episode_id,
            "event_type": str(self.event_type),
            "payload": self.payload,
            "previous_event_hash": self.previous_event_hash,
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
        }

    def recompute_hash(self) -> str:
        return sha256_hex(canonical_blob(self.body()))

    # -- construction and serialisation ------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        episode_id: str,
        event_type: EventType,
        payload: dict[str, Any],
        previous_event_hash: str,
        timestamp: str | None = None,
        schema_version: str = EVENT_SCHEMA_VERSION,
    ) -> Event:
        """Build an event and compute its hash. The only supported constructor."""
        stamp = timestamp if timestamp is not None else utc_now()
        draft = {
            "event_id": event_id,
            "episode_id": episode_id,
            "event_type": str(event_type),
            "payload": payload,
            "previous_event_hash": previous_event_hash,
            "schema_version": schema_version,
            "timestamp": stamp,
        }
        _check_serialisable(payload)
        return cls(
            event_id=event_id,
            episode_id=episode_id,
            event_type=event_type,
            timestamp=stamp,
            payload=payload,
            previous_event_hash=previous_event_hash,
            event_hash=sha256_hex(canonical_blob(draft)),
            schema_version=schema_version,
        )

    def to_dict(self) -> dict[str, Any]:
        doc = self.body()
        doc["event_hash"] = self.event_hash
        return doc

    def to_line(self) -> str:
        """One JSONL line. Canonical, so a re-serialised ledger is byte-identical."""
        return canonical_blob(self.to_dict())

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> Event:
        """Rebuild an event from a stored line.

        Validation happens in ``__post_init__``: a line whose ``event_hash`` does not
        commit to its own contents raises here, which is how single-line tampering is
        caught even before the chain is walked.
        """
        try:
            event_type = EventType(doc["event_type"])
        except ValueError as exc:
            raise ValueError(
                f"unknown event_type {doc.get('event_type')!r}: this ledger was written "
                f"by software this build does not understand"
            ) from exc
        return cls(
            event_id=doc["event_id"],
            episode_id=doc["episode_id"],
            event_type=event_type,
            timestamp=doc["timestamp"],
            payload=doc["payload"],
            previous_event_hash=doc["previous_event_hash"],
            event_hash=doc["event_hash"],
            schema_version=doc.get("schema_version", EVENT_SCHEMA_VERSION),
        )
