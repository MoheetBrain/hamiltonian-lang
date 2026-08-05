"""Repair budgets, and the refusal to pool across them.

Two budgets exist and they are never mixed
------------------------------------------
Official ACQ0 and official H3 allow **exactly one** repair. A developmental ablation
allows up to three, because INTERVENOR reported gains continuing through roughly three
turns and that claim deserves to be checked against this language.

Those two settings do not produce comparable numbers. A three-turn arm has three chances
to hit the same target and consumes three times the compute; averaging it with a one-turn
arm produces a figure that is neither, and — this is the part that destroys the record —
the mixed figure looks exactly like a clean one. :func:`require_single_budget` therefore
raises rather than warns, mirroring
:func:`hamiltonian_lang.improvement.state.require_single_hypothesis`.

The developmental budget is also barred from official runs outright
(:func:`assert_official`), so a three-turn number cannot reach a preregistered endpoint by
being relabelled downstream.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Any

from ..improvement.state import Hypothesis

__all__ = [
    "RepairBudget",
    "MAX_REPAIRS",
    "RepairBudgetExceeded",
    "RepairBudgetPoolingError",
    "NonOfficialBudgetError",
    "max_repairs",
    "require_single_budget",
    "assert_official",
]


class RepairBudget(StrEnum):
    """How many repair turns one task may receive."""

    #: One repair. The only budget admissible for official ACQ0 and official H3.
    OFFICIAL_ONE = "official_one"
    #: Up to three repairs. Developmental ablation only; never an official endpoint.
    DEVELOPMENTAL_THREE = "developmental_three"

    @property
    def official(self) -> bool:
        return self is RepairBudget.OFFICIAL_ONE

    @property
    def limit(self) -> int:
        return MAX_REPAIRS[self]


#: Total over :class:`RepairBudget`. There is no default and no unbounded option.
MAX_REPAIRS: dict[RepairBudget, int] = {
    RepairBudget.OFFICIAL_ONE: 1,
    RepairBudget.DEVELOPMENTAL_THREE: 3,
}


class RepairBudgetExceeded(RuntimeError):
    """A repair was requested past the budget's limit."""


class RepairBudgetPoolingError(ValueError):
    """Results from two different repair budgets would enter one statistic."""


class NonOfficialBudgetError(ValueError):
    """A developmental budget was used where a preregistered endpoint was claimed."""


def max_repairs(budget: RepairBudget) -> int:
    return MAX_REPAIRS[budget]


def require_single_budget(items: Iterable[Any], *, context: str) -> RepairBudget:
    """Return the one budget carried by ``items``, or raise.

    ``items`` may be :class:`RepairBudget` values or any object exposing ``.budget``. An
    empty input raises: an aggregate over nothing has no budget, and defaulting one would
    be the exact fabrication this function exists to stop.
    """
    seen: set[RepairBudget] = set()
    for item in items:
        b = item if isinstance(item, RepairBudget) else getattr(item, "budget", None)
        if not isinstance(b, RepairBudget):
            raise RepairBudgetPoolingError(
                f"{context}: item {item!r} carries no typed RepairBudget; an untyped or "
                "absent budget cannot be aggregated"
            )
        seen.add(b)
    if not seen:
        raise RepairBudgetPoolingError(
            f"{context}: no observations, so no repair budget to report"
        )
    if len(seen) > 1:
        names = ", ".join(sorted(b.value for b in seen))
        raise RepairBudgetPoolingError(
            f"{context}: observations span {len(seen)} repair budgets ({names}). A "
            "one-repair arm and a three-repair arm do not measure the same quantity and "
            "are never combined into one statistic."
        )
    return seen.pop()


def assert_official(budget: RepairBudget, *, hypothesis: Hypothesis, context: str) -> None:
    """Refuse a developmental budget under a preregistered hypothesis.

    ``ACQ0`` and ``H3`` both preregister *one* repair. ``EXCLUDED`` is engineering work
    and may use either. ``H1`` and ``H2`` do not involve a repair loop at all, so reaching
    here with one is itself the error worth reporting.
    """
    if hypothesis is Hypothesis.EXCLUDED:
        return
    if budget.official:
        return
    raise NonOfficialBudgetError(
        f"{context}: hypothesis {hypothesis.name} preregisters a maximum of one repair, "
        f"but the budget is {budget.value} (limit {budget.limit}). A developmental "
        "ablation is not evidence for a preregistered endpoint; record it as EXCLUDED."
    )
