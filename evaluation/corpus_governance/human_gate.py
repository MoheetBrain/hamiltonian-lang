"""Gate 5 — the human review queue, which has no automatic exit.

Why this gate is mandatory rather than a fallback
-------------------------------------------------
A benchmark whose pipeline resolves its own hard cases is unfalsifiable. Every item it
retains is an item its own machinery was comfortable with, so the corpus measures the
machinery's blind spots and calls the result a property of the language. The only way out
is a stage the machinery *cannot* complete: this one.

So there is no ``auto_resolve``, no ``resolve_by_majority``, no timeout that lets a stale
request lapse into approval. :meth:`ReviewQueue.resolve` requires a named reviewer and a
written decision, and :meth:`ReviewQueue.assert_clear` raises while any request is open.
Promotion calls ``assert_clear`` first, which is what makes the stop real rather than
advisory.

The five triggers
-----------------
Enumerated in :class:`ReviewTrigger` and closed. A situation that is not one of the five
does not need a human; a situation that *is* one of the five cannot be settled without
one.

* ``PROMOTION_SET_AMBIGUITY`` — an item bound for the promotion set admits two readings.
* ``NEW_EQUIVALENCE_TRANSFORMATION`` — a transformation not previously accepted as
  meaning-preserving. Accepting one silently widens what counts as a correct answer, for
  every item, retroactively.
* ``NEW_VERIFIER_CLASS`` — an obligation class the verifier has not handled before. The
  first item of a new class defines how every later one is judged.
* ``INCONCLUSIVE_SEMANTIC_PAIR`` — gate 2 or gate 3 returned ``INCONCLUSIVE``, or
  independent judges disagreed. Disagreement is the signal; averaging it away is the loss.
* ``BENCHMARK_CORRECTION`` — a claim that a shipped item's ground truth is wrong. Never
  applied silently: a corpus that edits its own answers after seeing model output has no
  remaining evidential value.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "ReviewTrigger",
    "ReviewRequest",
    "ReviewDecision",
    "HumanReviewRequired",
    "ReviewQueue",
]


class ReviewTrigger(StrEnum):
    """The closed set of situations that require a person. See the module docstring."""

    PROMOTION_SET_AMBIGUITY = "promotion_set_ambiguity"
    NEW_EQUIVALENCE_TRANSFORMATION = "new_equivalence_transformation"
    NEW_VERIFIER_CLASS = "new_verifier_class"
    INCONCLUSIVE_SEMANTIC_PAIR = "inconclusive_semantic_pair"
    BENCHMARK_CORRECTION = "benchmark_correction"


@dataclass(frozen=True)
class ReviewRequest:
    """One thing a person must decide, with everything they need to decide it."""

    request_id: str
    trigger: ReviewTrigger
    item_id: str
    #: The question, phrased so it can be answered without reading this codebase.
    question: str
    #: Everything the automated stages found, including what they disagreed about.
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "trigger": str(self.trigger),
            "item_id": self.item_id,
            "question": self.question,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True)
class ReviewDecision:
    """A person's answer. ``reviewer`` and ``rationale`` are both mandatory.

    An anonymous decision is not reviewable later, and a decision without a rationale
    cannot be checked for consistency against the next one — which is how a review
    process drifts into rubber-stamping without anyone noticing.
    """

    request_id: str
    reviewer: str
    #: True to admit the item, False to reject it. There is no "defer" value: deferring
    #: is simply leaving the request open, which keeps the queue blocking.
    admit: bool
    rationale: str

    def __post_init__(self) -> None:
        if not self.reviewer.strip():
            raise ValueError("a review decision requires a named reviewer")
        if not self.rationale.strip():
            raise ValueError("a review decision requires a written rationale")


class HumanReviewRequired(Exception):
    """Raised to stop a pipeline that has reached a decision it may not make itself."""

    def __init__(self, requests: Iterable[ReviewRequest]) -> None:
        self.requests = tuple(requests)
        summary = "; ".join(f"{r.request_id} [{r.trigger}] {r.item_id}" for r in self.requests)
        super().__init__(
            f"{len(self.requests)} open human-review request(s) block this step: {summary}"
        )


class ReviewQueue:
    """Open requests block; resolved ones are kept forever as the audit trail."""

    def __init__(self) -> None:
        self._open: dict[str, ReviewRequest] = {}
        self._resolved: list[tuple[ReviewRequest, ReviewDecision]] = []

    def raise_request(self, request: ReviewRequest) -> None:
        if request.request_id in self._open:
            raise ValueError(f"duplicate open review request: {request.request_id}")
        self._open[request.request_id] = request

    def resolve(self, decision: ReviewDecision) -> ReviewRequest:
        """Close one request with a named person's written decision."""
        request = self._open.pop(decision.request_id, None)
        if request is None:
            raise KeyError(f"no open review request with id {decision.request_id!r}")
        self._resolved.append((request, decision))
        return request

    @property
    def open_requests(self) -> tuple[ReviewRequest, ...]:
        return tuple(self._open.values())

    @property
    def resolved(self) -> tuple[tuple[ReviewRequest, ReviewDecision], ...]:
        return tuple(self._resolved)

    def admitted_items(self) -> frozenset[str]:
        return frozenset(r.item_id for r, d in self._resolved if d.admit)

    def rejected_items(self) -> frozenset[str]:
        return frozenset(r.item_id for r, d in self._resolved if not d.admit)

    def is_clear(self) -> bool:
        return not self._open

    def assert_clear(self, *, context: str) -> None:
        """Stop the caller while anything is open.

        Called by every promotion path. This is the mechanism that turns "a human should
        look at this" into "no further step happens until one has".
        """
        if self._open:
            raise HumanReviewRequired(self.open_requests)
        del context

    def __iter__(self) -> Iterator[ReviewRequest]:
        return iter(self._open.values())

    def __len__(self) -> int:
        return len(self._open)

    def to_dict(self) -> dict[str, Any]:
        return {
            "open": [r.to_dict() for r in self._open.values()],
            "resolved": [
                {
                    "request": r.to_dict(),
                    "reviewer": d.reviewer,
                    "admit": d.admit,
                    "rationale": d.rationale,
                }
                for r, d in self._resolved
            ],
        }
