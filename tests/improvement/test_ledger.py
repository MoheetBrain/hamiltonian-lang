"""The append-only ledger: append-only, replayable, and tamper-evident.

The load-bearing tests here are the ones that alter a historical line and prove
verification fails. A hash chain nobody checks is decoration.
"""

from __future__ import annotations

import json

import pytest

from hamiltonian_lang.improvement.events import EventType
from hamiltonian_lang.improvement.ledger import (
    EventLedger,
    LedgerCorrupt,
    LedgerLock,
    LedgerLocked,
    VerificationFailure,
)

CLOCK_TIMES = [f"2026-08-05T00:00:{i:02d}+00:00" for i in range(60)]


def fixed_clock():
    """A deterministic clock, so replay is byte-reproducible."""
    counter = iter(CLOCK_TIMES)
    return lambda: next(counter)


def make_ledger(tmp_path, name="events.jsonl") -> EventLedger:
    return EventLedger(tmp_path / name, clock=fixed_clock())


def seed(ledger: EventLedger, n: int = 4) -> None:
    types = [
        EventType.EPISODE_CREATED,
        EventType.MODEL_GENERATED,
        EventType.PARSE_ATTEMPTED,
        EventType.EPISODE_CLASSIFIED,
    ]
    for i in range(n):
        ledger.append(
            episode_id=f"ep-{i % 2}",
            event_type=types[i % len(types)],
            payload={"i": i},
        )


# --- basic append-only behaviour ---------------------------------------------------


def test_appends_verify(tmp_path):
    ledger = make_ledger(tmp_path)
    seed(ledger)
    result = ledger.verify()
    assert result.ok
    assert result.events_read == 4


def test_chain_links_each_event_to_its_predecessor(tmp_path):
    ledger = make_ledger(tmp_path)
    seed(ledger)
    events = ledger.read_all()
    for previous, current in zip(events, events[1:], strict=False):
        assert current.previous_event_hash == previous.event_hash


def test_the_ledger_exposes_no_mutation_api(tmp_path):
    ledger = make_ledger(tmp_path)
    for forbidden in ("update", "delete", "remove", "set", "overwrite", "rewrite"):
        assert not hasattr(ledger, forbidden)


def test_events_for_episode_filters(tmp_path):
    ledger = make_ledger(tmp_path)
    seed(ledger)
    assert [e.payload["i"] for e in ledger.events_for("ep-0")] == [0, 2]


# --- tamper detection: the point of the whole file ---------------------------------


def _rewrite(path, index, mutate):
    lines = path.read_text().splitlines()
    doc = json.loads(lines[index])
    mutate(doc)
    lines[index] = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n")


def test_altering_a_historical_payload_fails_verification(tmp_path):
    ledger = make_ledger(tmp_path)
    seed(ledger)

    def mutate(doc):
        doc["payload"] = {"i": 999}

    _rewrite(ledger.path, 1, mutate)
    result = ledger.verify()
    assert not result.ok
    assert result.failure is VerificationFailure.HASH_MISMATCH
    assert result.failed_line == 2


def test_altering_a_historical_timestamp_fails_verification(tmp_path):
    ledger = make_ledger(tmp_path)
    seed(ledger)

    def mutate(doc):
        doc["timestamp"] = "1999-01-01T00:00:00+00:00"

    _rewrite(ledger.path, 0, mutate)
    assert ledger.verify().failure is VerificationFailure.HASH_MISMATCH


def test_recomputing_the_hash_of_a_forged_line_is_still_caught(tmp_path):
    """The strongest tamper: edit the payload AND recompute that line's own hash.

    The line is then internally consistent, so only the chain catches it -- which is
    exactly why the chain exists.
    """
    ledger = make_ledger(tmp_path)
    seed(ledger)
    from hamiltonian_lang.improvement.events import Event

    lines = ledger.path.read_text().splitlines()
    original = Event.from_dict(json.loads(lines[1]))
    forged = Event.create(
        event_id=original.event_id,
        episode_id=original.episode_id,
        event_type=original.event_type,
        payload={"i": 999},
        previous_event_hash=original.previous_event_hash,
        timestamp=original.timestamp,
    )
    lines[1] = forged.to_line()
    ledger.path.write_text("\n".join(lines) + "\n")

    result = ledger.verify()
    assert not result.ok
    assert result.failure is VerificationFailure.CHAIN_BREAK
    assert result.failed_line == 3


def test_deleting_a_historical_line_is_detected(tmp_path):
    ledger = make_ledger(tmp_path)
    seed(ledger)
    lines = ledger.path.read_text().splitlines()
    del lines[1]
    ledger.path.write_text("\n".join(lines) + "\n")
    result = ledger.verify()
    assert not result.ok
    assert result.failure in (
        VerificationFailure.CHAIN_BREAK,
        VerificationFailure.BAD_POSITION,
    )


def test_reordering_lines_is_detected(tmp_path):
    ledger = make_ledger(tmp_path)
    seed(ledger)
    lines = ledger.path.read_text().splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    ledger.path.write_text("\n".join(lines) + "\n")
    assert not ledger.verify().ok


def test_a_corrupt_ledger_cannot_be_extended(tmp_path):
    ledger = make_ledger(tmp_path)
    seed(ledger)
    _rewrite(ledger.path, 0, lambda d: d.__setitem__("payload", {"i": -1}))
    with pytest.raises(LedgerCorrupt):
        ledger.append(episode_id="ep-9", event_type=EventType.MODEL_GENERATED)


def test_read_all_raises_on_a_corrupt_line(tmp_path):
    ledger = make_ledger(tmp_path)
    seed(ledger)
    _rewrite(ledger.path, 0, lambda d: d.__setitem__("payload", {"i": -1}))
    with pytest.raises(LedgerCorrupt):
        ledger.read_all()


# --- truncation, the limitation the chain does not cover ---------------------------


def test_truncation_is_unchecked_without_a_checkpoint(tmp_path):
    ledger = make_ledger(tmp_path)
    seed(ledger)
    lines = ledger.path.read_text().splitlines()
    ledger.path.write_text("\n".join(lines[:2]) + "\n")
    result = ledger.verify()
    assert result.ok, "a prefix of a valid chain is a valid chain"
    assert result.truncation_unchecked is True


def test_a_checkpoint_detects_truncation(tmp_path):
    ledger = make_ledger(tmp_path)
    seed(ledger)
    ledger.checkpoint()
    lines = ledger.path.read_text().splitlines()
    ledger.path.write_text("\n".join(lines[:2]) + "\n")
    result = ledger.verify()
    assert not result.ok
    assert result.failure is VerificationFailure.TRUNCATED
    assert result.truncation_unchecked is False


def test_checkpoint_refuses_a_corrupt_ledger(tmp_path):
    ledger = make_ledger(tmp_path)
    seed(ledger)
    _rewrite(ledger.path, 0, lambda d: d.__setitem__("payload", {"i": -1}))
    with pytest.raises(LedgerCorrupt):
        ledger.checkpoint()


# --- deterministic replay ----------------------------------------------------------


def test_replay_reproduces_the_file_byte_for_byte(tmp_path):
    source = make_ledger(tmp_path, "a.jsonl")
    seed(source)
    target = make_ledger(tmp_path, "b.jsonl")
    source.replay_into(target)
    assert target.path.read_bytes() == source.path.read_bytes()
    assert target.digest() == source.digest()


def test_replay_refuses_a_non_empty_target(tmp_path):
    source = make_ledger(tmp_path, "a.jsonl")
    seed(source)
    target = make_ledger(tmp_path, "b.jsonl")
    seed(target, 1)
    with pytest.raises(Exception, match="empty"):
        source.replay_into(target)


# --- single writer -----------------------------------------------------------------


def test_append_refuses_while_another_writer_holds_the_lock(tmp_path):
    ledger = make_ledger(tmp_path)
    seed(ledger, 1)
    with LedgerLock(ledger.lock_path):
        with pytest.raises(LedgerLocked):
            ledger.append(episode_id="ep-x", event_type=EventType.MODEL_GENERATED)


def test_the_lock_is_released_afterwards(tmp_path):
    ledger = make_ledger(tmp_path)
    with LedgerLock(ledger.lock_path):
        pass
    ledger.append(episode_id="ep-x", event_type=EventType.MODEL_GENERATED)
    assert ledger.verify().ok
