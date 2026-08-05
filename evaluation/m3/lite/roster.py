"""Rosters: one hypothesis each, explicit domain floors, and a reported H3 restriction.

Why a roster type at all
------------------------
Rule 5 of the hypothesis register: *every episode, result row, evidence package and report
carries exactly one ``hypothesis_id``.* A bare list of 40 items cannot satisfy that rule,
because nothing on it says which claim the run is about. :class:`LiteRoster` is the object
that does, and :func:`~hamiltonian_lang.improvement.state.require_single_hypothesis` accepts
it directly.

Building a roster for a different hypothesis produces a **different roster** with its own
stamped items and its own manifest. It never mixes: there is no method that returns items
for two hypotheses, so an aggregate combining H1 and H3 evidence cannot be assembled from
this module.

Why floors rather than an average
---------------------------------
FormalMATH found sharp domain bias — algebra, calculus and number theory behaved so
differently that a single overall number described none of them. An overall 55% is
compatible with six domains at 65% and one at 5%, and those are different corpora with
different conclusions. :data:`DOMAIN_FLOORS` therefore states a minimum item count per
domain, and :meth:`LiteRoster.floor_report` evaluates each domain separately. Nothing in
this module reports an overall figure without the per-domain breakdown beside it.

Why the H3 roster is smaller, and why that is stated rather than hidden
----------------------------------------------------------------------
The implemented verifier subset cannot state an obligation about an indexed term or a
limit, so linear algebra and calculus are outside it —
``evaluation/m3/verification/task_subset.py::EXCLUDED_DOMAINS`` says so before any task is
examined. An H3 roster therefore drops 11 of the 40 items and covers five domains, not
seven. :attr:`LiteRoster.excluded_domains` carries the drop with its reason so that an H3
result is never read as a claim about the whole corpus. A filter that silently keeps only
the tasks the verifier happens to handle makes H3 unfalsifiable.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from hamiltonian_lang.improvement.state import Hypothesis, require_single_hypothesis

from . import DOMAINS, ERROR_CATEGORIES, M3_LITE_VERSION
from .items import H3_INELIGIBLE_DOMAINS, LiteItem, build_items

__all__ = [
    "DOMAIN_FLOORS",
    "ERROR_CATEGORY_FLOOR",
    "LiteRoster",
    "build_roster",
    "FloorReport",
]

#: Minimum items per domain, evaluated **per domain**, never as an average. The corpus is
#: authored at exactly these counts; the floor exists so that a later edit that drains a
#: domain fails a test instead of quietly changing what the benchmark measures.
DOMAIN_FLOORS: dict[str, int] = {
    "algebra": 6,
    "probability_statistics": 6,
    "logic_and_scope": 6,
    "dimensions_physics": 6,
    "linear_algebra": 6,
    "calculus": 5,
    "epistemic_reasoning": 5,
}

#: Minimum items per structural-error category. Five each, so a per-category error rate has
#: the same denominator everywhere and is comparable across categories.
ERROR_CATEGORY_FLOOR = 5

#: Floors for a roster restricted to the verifier-eligible domains. Stated separately rather
#: than derived, so that an H3 run cannot inherit floors for domains it structurally lacks.
H3_DOMAIN_FLOORS: dict[str, int] = {
    d: n for d, n in DOMAIN_FLOORS.items() if d not in H3_INELIGIBLE_DOMAINS
}


@dataclass(frozen=True)
class FloorReport:
    """Per-domain and per-category counts against their floors. No overall pass field.

    There is deliberately no single ``ok`` boolean that hides which domain failed: callers
    read :meth:`shortfalls`, which names them.
    """

    counts: dict[str, int]
    floors: dict[str, int]
    kind: str

    def shortfalls(self) -> dict[str, tuple[int, int]]:
        """``{name: (have, need)}`` for every stratum below its floor."""
        return {
            name: (self.counts.get(name, 0), need)
            for name, need in self.floors.items()
            if self.counts.get(name, 0) < need
        }

    def met(self) -> bool:
        return not self.shortfalls()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "counts": dict(sorted(self.counts.items())),
            "floors": dict(sorted(self.floors.items())),
            "shortfalls": {k: {"have": h, "need": n} for k, (h, n) in self.shortfalls().items()},
            "met": self.met(),
        }


@dataclass(frozen=True)
class LiteRoster:
    """A task set stamped with exactly one hypothesis."""

    hypothesis: Hypothesis
    items: tuple[LiteItem, ...]
    #: ``(domain, why it is absent)`` for every domain this roster cannot cover.
    excluded_domains: tuple[tuple[str, str], ...] = ()
    version: str = M3_LITE_VERSION

    def __post_init__(self) -> None:
        # The rule, enforced at construction rather than at report time: one hypothesis per
        # roster. An empty roster raises here too -- "no hypothesis" is not a hypothesis.
        stamped = require_single_hypothesis(
            self.items, context=f"M3-Lite roster for {self.hypothesis}"
        )
        if stamped is not self.hypothesis:
            raise ValueError(
                f"roster declares {self.hypothesis} but its items carry {stamped}"
            )

    def __iter__(self) -> Iterator[LiteItem]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(i.id for i in self.items)

    def domain_counts(self) -> dict[str, int]:
        return dict(Counter(i.domain for i in self.items))

    def category_counts(self) -> dict[str, int]:
        return dict(Counter(i.error_category for i in self.items))

    def domain_floor_report(self) -> FloorReport:
        floors = H3_DOMAIN_FLOORS if self.hypothesis is Hypothesis.H3 else DOMAIN_FLOORS
        return FloorReport(self.domain_counts(), dict(floors), "domain")

    def category_floor_report(self) -> FloorReport:
        # An H3 roster drops whole domains, so its category balance is necessarily uneven.
        # Requiring the full floor there would be a floor nothing could meet; the honest
        # move is to state a reduced floor and say why, not to drop the check.
        floor = ERROR_CATEGORY_FLOOR if self.hypothesis is not Hypothesis.H3 else 3
        return FloorReport(
            self.category_counts(), dict.fromkeys(ERROR_CATEGORIES, floor), "error_category"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "hypothesis": str(self.hypothesis),
            "hypothesis_claim": self.hypothesis.claim,
            "hypothesis_excluded_claim": self.hypothesis.excluded_claim,
            "n": len(self.items),
            "ids": list(self.ids),
            "domain_floor": self.domain_floor_report().to_dict(),
            "category_floor": self.category_floor_report().to_dict(),
            "excluded_domains": [
                {"domain": d, "why": w} for d, w in self.excluded_domains
            ],
            "items": [i.to_dict() for i in self.items],
        }


#: Why each domain is unavailable to H3. Quoted from the pre-declared exclusions in
#: ``evaluation/m3/verification/task_subset.py`` rather than restated, so the two cannot
#: drift into disagreeing about what the verifier can do.
_H3_EXCLUSION_REASONS: dict[str, str] = {
    "linear_algebra": (
        "the evaluator refuses indexing and the matrix product; a claim about w[i] is "
        "outside the implemented obligation subset"
    ),
    "calculus": (
        "v0 has no surface syntax for limits, derivatives or integrals, so no obligation "
        "of this kind can even be stated"
    ),
}


def build_roster(
    hypothesis: Hypothesis = Hypothesis.H2,
    *,
    items: Sequence[LiteItem] | None = None,
) -> LiteRoster:
    """The roster for one hypothesis.

    ``H1`` and ``H2`` get all 40 items across seven domains. ``H3`` gets the 29 items whose
    obligations the implemented verifier can state, across five domains, with the two
    dropped domains recorded on the roster.

    ``ACQ0`` and ``EXCLUDED`` raise. ACQ0 is the syntax-acquisition prerequisite and has its
    own corpus and its own endpoints; building an ACQ0 roster out of a mathematical-reasoning
    benchmark is the exact conflation ``docs/evaluation/HYPOTHESIS_REGISTER.md`` rule 1
    forbids.
    """
    if hypothesis in {Hypothesis.ACQ0, Hypothesis.EXCLUDED}:
        raise ValueError(
            f"M3-Lite has no {hypothesis} roster. ACQ0 is a prerequisite with its own corpus "
            f"(evaluation/syntax_gate) and its own endpoints (repaired parse rate, semantic "
            f"preservation); EXCLUDED is engineering work and is never evidence. Neither is "
            f"answered by a mathematical-reasoning task set"
        )
    pool = list(items) if items is not None else build_items()
    if hypothesis is Hypothesis.H3:
        kept = [i for i in pool if i.h3_eligible]
        excluded = tuple(
            (d, _H3_EXCLUSION_REASONS[d]) for d in sorted(H3_INELIGIBLE_DOMAINS)
        )
    else:
        kept = list(pool)
        excluded = ()
    return LiteRoster(
        hypothesis=hypothesis,
        items=tuple(i.for_hypothesis(hypothesis) for i in kept),
        excluded_domains=excluded,
    )


def corpus_shape() -> dict[str, Any]:
    """The authored shape, for the manifest and for the governance document."""
    items = build_items()
    return {
        "version": M3_LITE_VERSION,
        "n": len(items),
        "domains": {d: sum(1 for i in items if i.domain == d) for d in DOMAINS},
        "error_categories": {
            c: sum(1 for i in items if i.error_category == c) for c in ERROR_CATEGORIES
        },
        "difficulty": dict(Counter(i.difficulty for i in items)),
        "h3_eligible": sum(1 for i in items if i.h3_eligible),
    }
