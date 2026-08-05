"""The append-only event ledger — Phase 7, the storage half.

A JSONL file, one :class:`~hamiltonian_lang.improvement.events.Event` per line, each
committing to its predecessor by SHA-256.

Guarantees, each with the mechanism that provides it
-----------------------------------------------------
============================  ==============================================================
append-only                   the file is opened ``"a"``; the class exposes no update or
                              delete method, and :class:`Event` is frozen
deterministic replay          ``event_id`` is the writer-assigned position and timestamps
                              are supplied by the caller, so replaying the same events
                              into a fresh ledger reproduces byte-identical lines
detectable tampering          :meth:`EventLedger.verify` recomputes every event hash and
                              walks the chain; an edited, deleted or reordered historical
                              line fails at that line
no silent mutation            an append refuses to run on a ledger that does not already
                              verify, so a corrupted file cannot be extended into a
                              longer file that looks healthy
complete provenance           every event carries its ``episode_id``; the ledger, not the
                              episode record, is the history of a repaired episode
single writer                 an exclusive ``flock`` on a sidecar lock file, held for the
                              whole append; see :class:`LedgerLock`
============================  ==============================================================

The limitation the chain does not cover
---------------------------------------
Truncating the tail leaves a valid prefix, which is a valid chain. :meth:`checkpoint`
writes the length and the tail hash to a sidecar; :meth:`verify` compares against it when
present and reports ``TRUNCATED``. Without a checkpoint, truncation is undetectable, and
this module says so rather than implying otherwise.
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .events import (
    EVENT_SCHEMA_VERSION,
    GENESIS_HASH,
    Event,
    EventType,
    canonical_blob,
    sha256_hex,
    utc_now,
)

__all__ = [
    "LedgerError",
    "LedgerCorrupt",
    "LedgerLocked",
    "VerificationFailure",
    "LedgerVerification",
    "LedgerLock",
    "EventLedger",
]


class LedgerError(Exception):
    """Base class for ledger problems."""


class LedgerCorrupt(LedgerError):
    """The stored chain does not verify. Raised on append, never swallowed."""


class LedgerLocked(LedgerError):
    """Another writer holds the single-writer lock."""


class VerificationFailure(StrEnum):
    NONE = "none"
    UNPARSEABLE_LINE = "unparseable_line"
    HASH_MISMATCH = "hash_mismatch"
    CHAIN_BREAK = "chain_break"
    BAD_POSITION = "bad_position"
    TRUNCATED = "truncated"
    CHECKPOINT_MISMATCH = "checkpoint_mismatch"


@dataclass(frozen=True)
class LedgerVerification:
    """The result of walking a ledger. ``ok`` is the only field callers may trust."""

    ok: bool
    events_read: int
    failure: VerificationFailure = VerificationFailure.NONE
    #: 1-based line number of the first bad line, 0 when the whole file is intact.
    failed_line: int = 0
    detail: str = ""
    tail_hash: str = GENESIS_HASH
    #: True when no checkpoint sidecar existed, so tail truncation was NOT ruled out.
    truncation_unchecked: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "events_read": self.events_read,
            "failure": str(self.failure),
            "failed_line": self.failed_line,
            "detail": self.detail,
            "tail_hash": self.tail_hash,
            "truncation_unchecked": self.truncation_unchecked,
        }


class LedgerLock:
    """Explicit single-writer lock: an exclusive ``flock`` on ``<ledger>.lock``.

    POSIX advisory locking is per open file description, so it coordinates separate
    processes as well as threads that each open the lock. It does not stop a process
    that never takes the lock -- which is why the append path always does.
    """

    def __init__(self, path: Path, *, blocking: bool = False) -> None:
        self.path = path
        self.blocking = blocking
        self._fd: int | None = None

    def __enter__(self) -> LedgerLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o644)
        flags = fcntl.LOCK_EX if self.blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
        try:
            fcntl.flock(fd, flags)
        except BlockingIOError as exc:
            os.close(fd)
            raise LedgerLocked(
                f"another writer holds {self.path}; this ledger is single-writer by "
                f"design, so the append was refused rather than interleaved"
            ) from exc
        self._fd = fd
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None


class EventLedger:
    """An append-only, hash-chained JSONL event log.

    ``clock`` produces the timestamp for an append that does not supply one. Tests pass
    a fixed clock so that replay is byte-reproducible.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], str] = utc_now,
        blocking_lock: bool = False,
    ) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.checkpoint_path = self.path.with_suffix(self.path.suffix + ".checkpoint")
        self.clock = clock
        self.blocking_lock = blocking_lock

    # -- reading -----------------------------------------------------------------

    def raw_lines(self) -> list[str]:
        if not self.path.exists():
            return []
        return [ln for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def __len__(self) -> int:
        return len(self.raw_lines())

    def __iter__(self) -> Iterator[Event]:
        return iter(self.read_all())

    def read_all(self) -> list[Event]:
        """Every event, in order. Raises :class:`LedgerCorrupt` on a bad line.

        Reading is the same walk as :meth:`verify`; a caller that wants the diagnosis
        rather than the exception calls :meth:`verify` first.
        """
        events: list[Event] = []
        for i, line in enumerate(self.raw_lines(), start=1):
            try:
                events.append(Event.from_dict(json.loads(line)))
            except Exception as exc:
                raise LedgerCorrupt(f"{self.path}:{i}: {exc}") from exc
        return events

    def events_for(self, episode_id: str) -> list[Event]:
        """Every event belonging to one episode, in ledger order.

        This is where the history of a repaired episode lives: the episode record keeps
        the initial output and the latest repair side by side, and the full sequence of
        attempts is reconstructed from here.
        """
        return [e for e in self.read_all() if e.episode_id == episode_id]

    # -- verification ------------------------------------------------------------

    def verify(self) -> LedgerVerification:
        """Recompute every hash and walk the chain. Never raises for bad content."""
        previous = GENESIS_HASH
        count = 0
        for i, line in enumerate(self.raw_lines(), start=1):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError as exc:
                return LedgerVerification(
                    False, count, VerificationFailure.UNPARSEABLE_LINE, i, str(exc), previous
                )
            try:
                event = Event.from_dict(doc)
            except Exception as exc:
                # ``Event.__post_init__`` recomputes the hash, so an edited payload,
                # timestamp or event_id lands here.
                return LedgerVerification(
                    False, count, VerificationFailure.HASH_MISMATCH, i, str(exc), previous
                )
            if event.previous_event_hash != previous:
                return LedgerVerification(
                    False, count, VerificationFailure.CHAIN_BREAK, i,
                    f"expected previous_event_hash {previous}, found "
                    f"{event.previous_event_hash}",
                    previous,
                )
            if event.event_id != _position_id(i - 1):
                return LedgerVerification(
                    False, count, VerificationFailure.BAD_POSITION, i,
                    f"event_id {event.event_id!r} does not match ledger position {i - 1}",
                    previous,
                )
            previous = event.event_hash
            count += 1

        result = LedgerVerification(True, count, tail_hash=previous)
        return self._apply_checkpoint(result)

    def _apply_checkpoint(self, result: LedgerVerification) -> LedgerVerification:
        if not self.checkpoint_path.exists():
            return result
        try:
            doc = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            anchored_count = int(doc["events"])
            anchored_tail = str(doc["tail_hash"])
        except Exception as exc:
            return LedgerVerification(
                False, result.events_read, VerificationFailure.CHECKPOINT_MISMATCH, 0,
                f"checkpoint is unreadable: {exc}", result.tail_hash,
                truncation_unchecked=True,
            )
        if result.events_read < anchored_count:
            return LedgerVerification(
                False, result.events_read, VerificationFailure.TRUNCATED,
                result.events_read + 1,
                f"checkpoint anchors {anchored_count} events; only {result.events_read} "
                f"remain, so the tail was removed",
                result.tail_hash, truncation_unchecked=False,
            )
        if result.events_read == anchored_count and result.tail_hash != anchored_tail:
            return LedgerVerification(
                False, result.events_read, VerificationFailure.CHECKPOINT_MISMATCH,
                result.events_read,
                "checkpoint tail hash disagrees with the file", result.tail_hash,
                truncation_unchecked=False,
            )
        return LedgerVerification(
            True, result.events_read, tail_hash=result.tail_hash, truncation_unchecked=False
        )

    def checkpoint(self) -> dict[str, Any]:
        """Anchor the current length and tail hash outside the chain.

        The chain alone cannot detect tail truncation, because a prefix of a valid chain
        verifies. This sidecar is the only thing that can, and it is only as trustworthy
        as its own storage.
        """
        result = self.verify()
        if not result.ok:
            raise LedgerCorrupt(
                f"refusing to checkpoint a ledger that does not verify: "
                f"{result.failure} at line {result.failed_line}: {result.detail}"
            )
        doc = {
            "events": result.events_read,
            "tail_hash": result.tail_hash,
            "schema_version": EVENT_SCHEMA_VERSION,
            "written_at": self.clock(),
        }
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path.write_text(canonical_blob(doc) + "\n", encoding="utf-8")
        return doc

    # -- appending ---------------------------------------------------------------

    def append(
        self,
        *,
        episode_id: str,
        event_type: EventType,
        payload: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> Event:
        """Append one event under the single-writer lock.

        Refuses if the existing chain does not verify: extending a corrupted ledger
        would bury the corruption under healthy-looking lines.
        """
        with LedgerLock(self.lock_path, blocking=self.blocking_lock):
            state = self.verify()
            if not state.ok:
                raise LedgerCorrupt(
                    f"{self.path}: refusing to append to a ledger that does not verify "
                    f"({state.failure} at line {state.failed_line}: {state.detail})"
                )
            event = Event.create(
                event_id=_position_id(state.events_read),
                episode_id=episode_id,
                event_type=event_type,
                payload=dict(payload or {}),
                previous_event_hash=state.tail_hash,
                timestamp=timestamp if timestamp is not None else self.clock(),
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(event.to_line() + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            return event

    # -- replay ------------------------------------------------------------------

    def replay_into(self, other: EventLedger) -> list[Event]:
        """Write every event of this ledger into ``other``, preserving timestamps.

        Deterministic: ``other`` must be empty, positions are reassigned identically,
        and the resulting file is byte-identical to this one. That equality is the test
        of deterministic replay.
        """
        if len(other) != 0:
            raise LedgerError("replay target must be empty; replay does not merge")
        written = []
        for event in self.read_all():
            written.append(
                other.append(
                    episode_id=event.episode_id,
                    event_type=event.event_type,
                    payload=event.payload,
                    timestamp=event.timestamp,
                )
            )
        return written

    def digest(self) -> str:
        """A single hash over the whole ledger, for citing a run in a report."""
        return sha256_hex(canonical_blob([e.event_hash for e in self.read_all()]))


def _position_id(index: int) -> str:
    return f"ev-{index:08d}"
