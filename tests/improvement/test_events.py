"""Events: one hashing scheme, deterministic bytes, no fabricated payloads."""

from __future__ import annotations

import math

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends.canonical import content_hash, to_canonical
from hamiltonian_lang.improvement.events import (
    EVENT_SCHEMA_VERSION,
    GENESIS_HASH,
    Event,
    EventType,
    NonSerialisableValue,
    canonical_blob,
    sha256_hex,
)

SOURCE = "module m\n\nparam x : Real\nrequire x > 0.0\n"


def _event(**kw) -> Event:
    base = dict(
        event_id="ev-00000000",
        episode_id="ep-1",
        event_type=EventType.EPISODE_CREATED,
        payload={"k": 1},
        previous_event_hash=GENESIS_HASH,
        timestamp="2026-08-05T00:00:00+00:00",
    )
    base.update(kw)
    return Event.create(**base)  # type: ignore[arg-type]


# --- the single-hashing-scheme guarantee -----------------------------------------


def test_event_hashing_agrees_with_content_hash():
    """The ledger must not invent a second hashing scheme.

    Recomputing the compiler's own alpha-invariant content hash through this module's
    ``canonical_blob``/``sha256_hex`` must reproduce it byte for byte. If
    ``backends/canonical.py`` ever changes its serialisation, this fails rather than the
    two drifting apart in silence.
    """
    result = compile_source(SOURCE)
    assert result.ok()
    doc = to_canonical(result.module, include_names=False)
    assert sha256_hex(canonical_blob(doc)) == content_hash(result.module)


def test_canonical_blob_is_deterministic_across_key_order():
    assert canonical_blob({"b": 1, "a": 2}) == canonical_blob({"a": 2, "b": 1})


def test_canonical_blob_treats_tuples_and_lists_alike():
    assert canonical_blob({"x": (1, 2)}) == canonical_blob({"x": [1, 2]})


@pytest.mark.parametrize("bad", [object(), {1: "int key"}, float("nan"), math.inf])
def test_canonical_blob_refuses_values_with_no_canonical_form(bad):
    with pytest.raises(NonSerialisableValue):
        canonical_blob({"x": bad})


# --- event integrity --------------------------------------------------------------


def test_create_produces_a_self_committing_hash():
    event = _event()
    assert event.event_hash == event.recompute_hash()
    assert len(event.event_hash) == 64
    assert event.schema_version == EVENT_SCHEMA_VERSION


def test_identical_inputs_produce_identical_hashes():
    assert _event().event_hash == _event().event_hash


@pytest.mark.parametrize(
    "field,value",
    [
        ("payload", {"k": 2}),
        ("timestamp", "2026-08-05T00:00:01+00:00"),
        ("episode_id", "ep-2"),
        ("event_id", "ev-00000001"),
        ("event_type", EventType.MODEL_GENERATED),
    ],
)
def test_every_hashed_field_changes_the_hash(field, value):
    assert _event(**{field: value}).event_hash != _event().event_hash


def test_a_tampered_line_cannot_be_rebuilt():
    doc = _event().to_dict()
    doc["payload"] = {"k": 999}
    with pytest.raises(ValueError, match="does not commit"):
        Event.from_dict(doc)


def test_direct_construction_with_a_wrong_hash_is_refused():
    with pytest.raises(ValueError, match="does not commit"):
        Event(
            event_id="ev-00000000",
            episode_id="ep-1",
            event_type=EventType.EPISODE_CREATED,
            timestamp="2026-08-05T00:00:00+00:00",
            payload={},
            previous_event_hash=GENESIS_HASH,
            event_hash="0" * 64,
        )


def test_unknown_event_type_is_reported_not_accepted():
    doc = _event().to_dict()
    doc["event_type"] = "SOMETHING_LATER"
    with pytest.raises(ValueError, match="unknown event_type"):
        Event.from_dict(doc)


def test_round_trip_through_a_line_is_byte_stable():
    event = _event()
    assert Event.from_dict(__import__("json").loads(event.to_line())) == event
    assert Event.from_dict(__import__("json").loads(event.to_line())).to_line() == event.to_line()


def test_the_thirteen_required_event_types_exist():
    required = {
        "EPISODE_CREATED", "TASK_VALIDATED", "MODEL_GENERATED", "PARSE_ATTEMPTED",
        "DIAGNOSTIC_ISSUED", "REPAIR_GENERATED", "TYPE_CHECKED", "SEMANTICALLY_COMPARED",
        "VERIFIER_EXECUTED", "EPISODE_CLASSIFIED", "MEMORY_ROUTED",
        "EXPERIMENT_EVALUATED", "PROMOTION_DECIDED",
    }
    assert required <= {e.value for e in EventType}


def test_payload_is_validated_at_creation():
    with pytest.raises(NonSerialisableValue):
        _event(payload={"module": object()})
