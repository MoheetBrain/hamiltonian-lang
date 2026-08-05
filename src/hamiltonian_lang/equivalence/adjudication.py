"""Tier 5 -- the queue of pairs no automated tier could decide.

The last tier is not an algorithm; it is an admission. Everything the earlier
tiers could not settle lands here as an explicit, serialisable item for a human to
look at, with the residuals that defeated the automation attached.

The queue exists so that ``INCONCLUSIVE`` has somewhere to go other than a
silently-dropped row or, worse, a bucket that gets counted as a failure at
aggregation time. An engine whose unresolved cases vanish is an engine whose
coverage cannot be measured.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .status import EquivalenceStatus

__all__ = ["AdjudicationItem", "AdjudicationQueue"]


@dataclass(frozen=True)
class AdjudicationItem:
    """One undecided comparison, with enough context to decide it by hand."""

    item_id: str
    status: EquivalenceStatus
    reason: str
    reference: str = ""
    candidate: str = ""
    residuals: tuple[str, ...] = ()
    tiers_tried: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "status": str(self.status),
            "reason": self.reason,
            "reference": self.reference,
            "candidate": self.candidate,
            "residuals": list(self.residuals),
            "tiers_tried": list(self.tiers_tried),
        }


@dataclass
class AdjudicationQueue:
    """An ordered, serialisable collection of undecided comparisons."""

    items: list[AdjudicationItem] = field(default_factory=list)

    def add(self, item: AdjudicationItem) -> AdjudicationItem:
        self.items.append(item)
        return item

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[AdjudicationItem]:
        return iter(self.items)

    def by_status(self, status: EquivalenceStatus) -> list[AdjudicationItem]:
        return [i for i in self.items if i.status is status]

    def to_dict(self) -> dict[str, Any]:
        return {"count": len(self.items), "items": [i.to_dict() for i in self.items]}

    def write_json(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")
        return target

    @staticmethod
    def from_items(items: Sequence[AdjudicationItem]) -> AdjudicationQueue:
        return AdjudicationQueue(list(items))
