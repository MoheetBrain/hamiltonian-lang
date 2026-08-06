"""The four M3-Lite partitions, and what each one costs to look at.

A benchmark with one pool has one number, and that number is contaminated the first time
anybody tunes anything against it. The partitions exist so that "we looked at this" is a
recorded property of an item rather than an unwritten memory.

===================  =========  =====================================================
partition            visible?   what it is for
===================  =========  =====================================================
``development``      **yes**    the only pool anything may be tuned, demonstrated or
                                debugged against. Scores on it are diagnostics and are
                                never reported as a result.
``adversarial``      no         reserved for attacking the *pipeline* — deliberately
                                corrupted encodings, swapped roles, reversed prefixes.
                                Held out because an attack set the pipeline has been
                                fitted to stops being an attack set.
``promotion``        no         gates promotion decisions. Every item here is
                                ``promotion_critical`` in the funnel, so gate 5 stops
                                and asks rather than admitting on machine verdicts
                                alone.
``transfer``         no         the generalisation pool. Touched once, at the end, and
                                never used to choose between designs.
===================  =========  =====================================================

Held out means held out
-----------------------
:data:`HELD_OUT` is three of the four. Only ``development`` is visible. The requirement
this encodes is narrow and specific: **an ACQ0 demonstration must never come from a
held-out partition.** A model shown an item as a worked example and later scored on it is
being measured on recall.

Checked by content, not by name
-------------------------------
:func:`held_out_contamination` fingerprints each held-out partition and checks it against
the ACQ0 demonstration pools with :mod:`evaluation.corpus_governance.contamination`, which
compares SHA-256 digests over ``(specification, question, answer, reference)``. An id is
not among those fields. Renaming a reused item changes its id and nothing else, so a
name-based check passes exactly the case it exists to catch, and this one does not.

Why the assignment is a deal rather than a judgement
----------------------------------------------------
:func:`assign_partitions` deals items round-robin in a fixed order — domain by domain in
:data:`~evaluation.m3.lite.DOMAINS` order, items within a domain sorted by id, a single
global cursor carrying across domain boundaries. Three consequences, all of them the point:

* it is **reproducible** — the same 40 items always produce the same four partitions, so
  the manifest can be regenerated and compared rather than trusted;
* every domain lands in **every** partition, because each domain contributes five or six
  consecutive cursor values and four consecutive values already cover all four residues;
* nobody chooses which items are held out. Hand-picking the partition is how the easy
  items end up in the pool that gets reported.

The per-partition domain floor is :data:`MIN_DOMAIN_PRESENCE` = 1 and it is *checked*, not
assumed — :meth:`PartitionManifest.shortfalls` names any domain missing from any partition.
Ten items cannot carry the per-domain floors of :mod:`.roster`, and pretending otherwise
would be a floor that means nothing. What a partition of ten can honestly promise is that
no domain is absent from it, and that is what is enforced.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from evaluation.corpus_governance.contamination import (
    ContaminationReport,
    ContentFields,
    CorpusFingerprint,
    check_contamination,
    content_digest,
    fingerprint,
)

from . import DOMAINS, M3_LITE_VERSION, SEED_NAMESPACE
from .items import LiteItem, build_items

__all__ = [
    "Partition",
    "HELD_OUT",
    "VISIBLE",
    "PARTITION_ROLES",
    "MIN_DOMAIN_PRESENCE",
    "ProvenanceError",
    "PartitionManifest",
    "assign_partitions",
    "partitioned",
    "build_manifest",
    "validate_provenance",
    "promotion_critical_ids",
    "acq0_demonstration_splits",
    "held_out_contamination",
]


class Partition(StrEnum):
    """The four pools. Order is the deal order and is fixed."""

    DEVELOPMENT = "development"
    ADVERSARIAL = "adversarial"
    PROMOTION = "promotion"
    TRANSFER = "transfer"


#: The only partition anything may be tuned, demonstrated or debugged against.
VISIBLE: frozenset[Partition] = frozenset({Partition.DEVELOPMENT})

#: Everything else. An ACQ0 demonstration drawn from any of these is contamination.
HELD_OUT: frozenset[Partition] = frozenset(Partition) - VISIBLE

#: What each partition is for, and what looking at it spends. Carried into the manifest so
#: the rule travels with the data rather than living only in this docstring.
PARTITION_ROLES: dict[Partition, str] = {
    Partition.DEVELOPMENT: (
        "visible. Tuning, demonstrations and debugging happen here and only here. A score "
        "on this pool is a diagnostic, never a reported result"
    ),
    Partition.ADVERSARIAL: (
        "held out. Reserved for attacking the pipeline itself. An attack set the pipeline "
        "has been fitted against no longer attacks anything"
    ),
    Partition.PROMOTION: (
        "held out. Gates promotion decisions; every item is promotion-critical, so gate 5 "
        "stops and asks a person rather than admitting on machine verdicts alone"
    ),
    Partition.TRANSFER: (
        "held out. The generalisation pool. Read once, at the end, and never used to "
        "choose between designs"
    ),
}

#: Minimum items per domain **per partition**. One, and checked rather than assumed. A
#: ten-item partition cannot carry the roster's per-domain floors; claiming it could would
#: be a floor that no edit could ever violate, which is not a floor.
MIN_DOMAIN_PRESENCE = 1


class ProvenanceError(RuntimeError):
    """An item's provenance does not check out, or the partition is not a partition.

    Raised rather than returned. A provenance failure means the corpus is not the corpus
    the manifest describes, and there is nothing downstream that can sensibly be computed
    from it.
    """


def assign_partitions(items: Sequence[LiteItem]) -> dict[str, Partition]:
    """``item_id -> Partition``, dealt deterministically.

    Domain by domain in :data:`DOMAINS` order, items sorted by id within a domain, one
    global cursor carried across domain boundaries so the four pools stay level. Items in a
    domain outside :data:`DOMAINS` are a provenance failure rather than a silent drop.
    """
    order = list(Partition)
    known = set(DOMAINS)
    stray = sorted({i.domain for i in items} - known)
    if stray:
        raise ProvenanceError(
            f"items declare domains outside the declared strata: {stray}. A domain that is "
            f"not in DOMAINS has no floor, no stratum and no place in the deal"
        )
    out: dict[str, Partition] = {}
    cursor = 0
    for domain in DOMAINS:
        for item in sorted((i for i in items if i.domain == domain), key=lambda i: i.id):
            out[item.id] = order[cursor % len(order)]
            cursor += 1
    return out


def partitioned(
    items: Sequence[LiteItem] | None = None,
) -> dict[Partition, tuple[LiteItem, ...]]:
    """The four pools as item tuples, in deal order within each pool."""
    pool = list(items) if items is not None else build_items()
    assignment = assign_partitions(pool)
    by_id = {i.id: i for i in pool}
    out: dict[Partition, tuple[LiteItem, ...]] = {}
    for partition in Partition:
        member_ids = [i for i, p in assignment.items() if p is partition]
        out[partition] = tuple(by_id[i] for i in member_ids)
    return out


def _fields(item: LiteItem) -> tuple[str, ContentFields]:
    cso = item.cso
    return cso.id, ContentFields(
        specification=cso.prose,
        question=cso.question,
        answer=str(cso.answer.value),
        reference=cso.reference_hml,
    )


@dataclass(frozen=True)
class PartitionManifest:
    """The deal, its per-partition composition, and a content digest for every item.

    The digests are the part that matters. A partition recorded as a list of ids can be
    satisfied later by different items wearing those ids; a partition recorded as a list of
    content digests cannot.
    """

    version: str
    members: Mapping[Partition, tuple[str, ...]]
    #: ``item_id -> SHA-256 over (specification, question, answer, reference)``.
    digests: Mapping[str, str]
    domain_counts: Mapping[Partition, Mapping[str, int]]
    category_counts: Mapping[Partition, Mapping[str, int]]

    def sizes(self) -> dict[str, int]:
        return {str(p): len(ids) for p, ids in self.members.items()}

    def held_out_ids(self) -> frozenset[str]:
        return frozenset(i for p in HELD_OUT for i in self.members[p])

    def visible_ids(self) -> frozenset[str]:
        return frozenset(i for p in VISIBLE for i in self.members[p])

    def shortfalls(self) -> dict[str, dict[str, int]]:
        """``{partition: {domain: have}}`` for every domain below its presence floor."""
        out: dict[str, dict[str, int]] = {}
        for partition, counts in self.domain_counts.items():
            missing = {
                d: counts.get(d, 0)
                for d in DOMAINS
                if counts.get(d, 0) < MIN_DOMAIN_PRESENCE
            }
            if missing:
                out[str(partition)] = missing
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "seed_namespace": SEED_NAMESPACE,
            "sizes": self.sizes(),
            "min_domain_presence": MIN_DOMAIN_PRESENCE,
            "shortfalls": self.shortfalls(),
            "held_out": sorted(str(p) for p in HELD_OUT),
            "visible": sorted(str(p) for p in VISIBLE),
            "roles": {str(p): why for p, why in PARTITION_ROLES.items()},
            "members": {
                str(p): {
                    "ids": list(ids),
                    "digests": {i: self.digests[i] for i in ids},
                    "domains": dict(sorted(self.domain_counts[p].items())),
                    "error_categories": dict(sorted(self.category_counts[p].items())),
                }
                for p, ids in self.members.items()
            },
        }


def build_manifest(items: Sequence[LiteItem] | None = None) -> PartitionManifest:
    """Deal the partitions and record the deal, digests included."""
    pool = list(items) if items is not None else build_items()
    validate_provenance(pool)
    pools = partitioned(pool)
    return PartitionManifest(
        version=M3_LITE_VERSION,
        members={p: tuple(i.id for i in members) for p, members in pools.items()},
        digests={i.id: content_digest(_fields(i)[1]) for i in pool},
        domain_counts={
            p: dict(Counter(i.domain for i in members)) for p, members in pools.items()
        },
        category_counts={
            p: dict(Counter(i.error_category for i in members))
            for p, members in pools.items()
        },
    )


def validate_provenance(items: Sequence[LiteItem] | None = None) -> dict[str, Any]:
    """Every item traces to this study, and the deal is a partition.

    Four things are checked, and each of them has a specific failure it prevents:

    ``ids unique``          two items sharing an id make one of them unreachable and make
                            every per-item count wrong.
    ``seed namespace``      an item whose generator is not under
                            :data:`SEED_NAMESPACE` came from somewhere else, and
                            "somewhere else" is where the model may already have seen it.
    ``corpus version``      a mixed-version pool produces a manifest that describes neither
                            version.
    ``total and disjoint``  every item lands in exactly one partition. An unassigned item
                            is held out by nobody; a doubly-assigned one is both visible
                            and held out, which makes the distinction meaningless.

    Returns the counts it checked so a caller can record them; raises
    :class:`ProvenanceError` on any failure rather than returning a status nobody reads.
    """
    pool = list(items) if items is not None else build_items()
    if not pool:
        raise ProvenanceError("an empty corpus has no provenance to validate")

    ids = [i.id for i in pool]
    duplicates = sorted({i for i, n in Counter(ids).items() if n > 1})
    if duplicates:
        raise ProvenanceError(f"duplicate item ids: {duplicates}")

    foreign = sorted(i.id for i in pool if not i.cso.generator.startswith(SEED_NAMESPACE))
    if foreign:
        raise ProvenanceError(
            f"items whose generator is outside the {SEED_NAMESPACE!r} namespace: {foreign}. "
            f"A fresh corpus that reuses an earlier namespace is not fresh"
        )

    versions = sorted({i.cso.corpus_version for i in pool})
    if versions != [M3_LITE_VERSION]:
        raise ProvenanceError(
            f"mixed corpus versions {versions}; expected only {M3_LITE_VERSION!r}"
        )

    assignment = assign_partitions(pool)
    unassigned = sorted(set(ids) - set(assignment))
    if unassigned:
        raise ProvenanceError(f"items assigned to no partition: {unassigned}")
    if len(assignment) != len(pool):
        raise ProvenanceError(
            f"the deal covers {len(assignment)} items for a pool of {len(pool)}"
        )

    return {
        "n": len(pool),
        "seed_namespace": SEED_NAMESPACE,
        "corpus_version": M3_LITE_VERSION,
        "sizes": {str(p): sum(1 for v in assignment.values() if v is p) for p in Partition},
    }


def promotion_critical_ids(items: Sequence[LiteItem] | None = None) -> frozenset[str]:
    """The promotion partition, in the form :func:`~...gates.run_funnel` takes.

    Passing this makes gate 5 escalate every promotion item even when gates 1 to 4 all
    passed. That is the intended behaviour: a promotion decision is exactly the place where
    "the machinery was satisfied" is not a sufficient reason.
    """
    return frozenset(i.id for i in partitioned(items)[Partition.PROMOTION])


def acq0_demonstration_splits() -> list[CorpusFingerprint]:
    """Every pool that is ever *shown* to a model, fingerprinted.

    Discovered rather than listed: the syntax-gate demonstration stage is read from the
    partition's own output, so a demonstration pool added upstream is covered here without
    anyone remembering to update this function. The HML-EVAL-001 demonstrations are
    included because they were shown to this same model on this same host.

    The import is local so that importing this module does not drag in the whole ACQ0
    apparatus.
    """
    from evaluation.corpus_governance.contamination import acq0_splits

    demo = [
        split
        for split in acq0_splits()
        if "demonstration" in split.name or split.name.endswith("::demonstrations")
    ]
    if not demo:
        raise ProvenanceError(
            "no demonstration pool was discovered. A contamination check against an empty "
            "set of foreign corpora passes trivially and is worse than no check"
        )
    return demo


def held_out_contamination(
    items: Sequence[LiteItem] | None = None,
    foreign: Iterable[CorpusFingerprint] | None = None,
) -> dict[Partition, ContaminationReport]:
    """One contamination report per held-out partition, against the demonstration pools.

    Per partition rather than for the corpus as a whole, because "no M3-Lite item was
    demonstrated" and "no *held-out* M3-Lite item was demonstrated" are different claims
    and only the second one is the requirement. Comparison is on content digests; ids never
    enter it.
    """
    pools = partitioned(items)
    splits = list(foreign) if foreign is not None else acq0_demonstration_splits()
    if not splits:
        raise ProvenanceError(
            "no foreign corpus was supplied. A contamination check against an empty set of "
            "foreign corpora passes trivially and is worse than no check: it produces a "
            "clean report that means nothing"
        )
    return {
        partition: check_contamination(
            fingerprint(f"m3_lite::{partition}", pools[partition], _fields), splits
        )
        for partition in sorted(HELD_OUT)
    }
