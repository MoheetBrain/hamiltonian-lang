"""Contamination control — disjointness by content, never by name.

The requirement
---------------
No M3-Lite item may appear in any ACQ0 split, in the HML-EVAL-001 corpus, or in any
demonstration curriculum. An item the model has already been shown, or will be trained or
demonstrated on, measures memory rather than reasoning, and a benchmark that cannot rule
that out reports an unknown quantity.

Why identifiers are not enough
------------------------------
Checking ids would pass for two items that differ only in their id — which is precisely the
leak the check exists to catch, and precisely what a generator that renames its output
produces. ``evaluation/syntax_gate/partition.py`` already makes this point for the ACQ0
stage pools; this module extends the same discipline across corpora.

Three checks, deliberately redundant
------------------------------------
1. :func:`content_digest` — SHA-256 over the *content fields* (specification, question,
   answer, reference encoding), in a canonical JSON encoding. Exact-duplicate detection.
2. :func:`normalised_digest` — the same, after case folding, punctuation stripping and
   whitespace collapse. Catches an item reused with cosmetic edits, which an exact hash
   would not.
3. :func:`shingle_overlap` — Jaccard over 5-token shingles of the specification. Catches a
   paraphrase that survives both hashes.

The third is the only one with a threshold, and the threshold is set at
:data:`NEAR_DUPLICATE_THRESHOLD` = 0.60 — low enough that a rewritten-but-structurally-
identical item is flagged, high enough that two items in the same domain sharing standard
vocabulary are not. A flag is not a rejection: it is a
:class:`~.human_gate.ReviewTrigger.BENCHMARK_CORRECTION` request, because whether two items
are "the same problem" is a judgement and this module does not make judgements.

Registered splits
-----------------
:func:`acq0_splits` enumerates every split by *building it from its own source of truth*
rather than from a copied list. If the ACQ0 partition gains a stage tomorrow, the
contamination test sees the new stage without anyone remembering to add it here. A hard-
coded list of split names is the version of this check that quietly stops covering things.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "ContentFields",
    "content_digest",
    "normalised_digest",
    "shingles",
    "shingle_overlap",
    "NEAR_DUPLICATE_THRESHOLD",
    "SHINGLE_WIDTH",
    "CorpusFingerprint",
    "fingerprint",
    "ContaminationReport",
    "check_contamination",
    "acq0_splits",
]

#: 5-token shingles. Wide enough that shared boilerplate ("let x be a real number") does not
#: match on its own; narrow enough to survive a rewritten clause.
SHINGLE_WIDTH = 5

#: Jaccard over shingles above which two items are flagged as possible near-duplicates and
#: sent to a human. Not a rejection threshold — see the module docstring.
NEAR_DUPLICATE_THRESHOLD = 0.60


@dataclass(frozen=True)
class ContentFields:
    """The fields that constitute an item's *content*. Its id is not among them."""

    specification: str
    question: str
    answer: str
    reference: str

    def payload(self) -> str:
        return json.dumps(
            {
                "specification": self.specification,
                "question": self.question,
                "answer": self.answer,
                "reference": self.reference,
            },
            sort_keys=True,
            ensure_ascii=True,
        )


def content_digest(fields: ContentFields) -> str:
    """SHA-256 of the exact content. Identical bytes in, identical digest out."""
    return hashlib.sha256(fields.payload().encode()).hexdigest()


_PUNCT = re.compile(r"[^\w\s]+")
_SPACE = re.compile(r"\s+")


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = _PUNCT.sub(" ", text)
    return _SPACE.sub(" ", text).strip()


def normalised_digest(fields: ContentFields) -> str:
    """SHA-256 after case folding, punctuation stripping and whitespace collapse.

    Catches the reuse an exact hash misses: the same problem with different capitalisation,
    a comma moved, or an em dash swapped for a hyphen.
    """
    folded = ContentFields(
        specification=_fold(fields.specification),
        question=_fold(fields.question),
        answer=_fold(fields.answer),
        reference=_fold(fields.reference),
    )
    return hashlib.sha256(folded.payload().encode()).hexdigest()


def shingles(text: str, width: int = SHINGLE_WIDTH) -> frozenset[tuple[str, ...]]:
    tokens = _fold(text).split()
    if len(tokens) < width:
        return frozenset({tuple(tokens)}) if tokens else frozenset()
    return frozenset(tuple(tokens[i : i + width]) for i in range(len(tokens) - width + 1))


def shingle_overlap(a: str, b: str, width: int = SHINGLE_WIDTH) -> float:
    sa, sb = shingles(a, width), shingles(b, width)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


@dataclass(frozen=True)
class CorpusFingerprint:
    """One corpus reduced to what a contamination check needs."""

    name: str
    #: ``item_id -> exact digest``
    exact: Mapping[str, str]
    #: ``item_id -> normalised digest``
    normalised: Mapping[str, str]
    #: ``item_id -> specification text``, for the shingle pass.
    text: Mapping[str, str]

    def __len__(self) -> int:
        return len(self.exact)


def fingerprint(
    name: str, items: Iterable[Any], extract: Callable[[Any], tuple[str, ContentFields]]
) -> CorpusFingerprint:
    """Reduce any corpus to a fingerprint via a per-corpus ``extract``.

    The extractor is a parameter so that a foreign corpus needs no modification to be
    checked against — this module owns no other package's files and reads them only through
    their public dataclasses.
    """
    exact: dict[str, str] = {}
    normalised: dict[str, str] = {}
    text: dict[str, str] = {}
    for item in items:
        item_id, fields = extract(item)
        exact[item_id] = content_digest(fields)
        normalised[item_id] = normalised_digest(fields)
        text[item_id] = fields.specification
    return CorpusFingerprint(name=name, exact=exact, normalised=normalised, text=text)


@dataclass(frozen=True)
class Collision:
    kind: str  # exact | normalised | near_duplicate
    candidate_id: str
    foreign_corpus: str
    foreign_id: str
    score: float
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "candidate_id": self.candidate_id,
            "foreign_corpus": self.foreign_corpus,
            "foreign_id": self.foreign_id,
            "score": round(self.score, 4),
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ContaminationReport:
    candidate_corpus: str
    checked_against: tuple[str, ...]
    collisions: tuple[Collision, ...]

    @property
    def hard_collisions(self) -> tuple[Collision, ...]:
        """Exact and normalised matches. These are contamination, not a judgement call."""
        return tuple(c for c in self.collisions if c.kind in {"exact", "normalised"})

    @property
    def flagged(self) -> tuple[Collision, ...]:
        """Near-duplicates. A human decides; this module does not."""
        return tuple(c for c in self.collisions if c.kind == "near_duplicate")

    def clean(self) -> bool:
        return not self.hard_collisions

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_corpus": self.candidate_corpus,
            "checked_against": list(self.checked_against),
            "clean": self.clean(),
            "hard_collisions": [c.to_dict() for c in self.hard_collisions],
            "flagged_near_duplicates": [c.to_dict() for c in self.flagged],
        }


def check_contamination(
    candidate: CorpusFingerprint,
    foreign: Sequence[CorpusFingerprint],
    *,
    near_duplicate_threshold: float = NEAR_DUPLICATE_THRESHOLD,
) -> ContaminationReport:
    """Every candidate against every item of every foreign corpus, on all three checks."""
    collisions: list[Collision] = []
    for other in foreign:
        by_exact = {digest: cid for cid, digest in other.exact.items()}
        by_norm: dict[str, str] = {}
        for cid, digest in other.normalised.items():
            by_norm.setdefault(digest, cid)

        for cid, digest in candidate.exact.items():
            hit = by_exact.get(digest)
            if hit is not None:
                collisions.append(
                    Collision(
                        "exact",
                        cid,
                        other.name,
                        hit,
                        1.0,
                        "byte-identical content; the id differs but the item does not",
                    )
                )

        for cid, digest in candidate.normalised.items():
            hit = by_norm.get(digest)
            if hit is not None and not any(
                c.kind == "exact" and c.candidate_id == cid and c.foreign_id == hit
                for c in collisions
            ):
                collisions.append(
                    Collision(
                        "normalised",
                        cid,
                        other.name,
                        hit,
                        1.0,
                        "identical after case folding and punctuation stripping; a cosmetic "
                        "edit of an item the model has already seen is still that item",
                    )
                )

        for cid, spec in candidate.text.items():
            for fid, fspec in other.text.items():
                score = shingle_overlap(spec, fspec)
                if score >= near_duplicate_threshold:
                    collisions.append(
                        Collision(
                            "near_duplicate",
                            cid,
                            other.name,
                            fid,
                            score,
                            f"{SHINGLE_WIDTH}-token shingle Jaccard {score:.2f} exceeds "
                            f"{near_duplicate_threshold:.2f}; a person must decide whether "
                            f"these are the same problem",
                        )
                    )
    return ContaminationReport(
        candidate_corpus=candidate.name,
        checked_against=tuple(f.name for f in foreign),
        collisions=tuple(collisions),
    )


# ---------------------------------------------------------------------------
# The registered ACQ0 splits
# ---------------------------------------------------------------------------


def _cso_fields(cso: Any) -> tuple[str, ContentFields]:
    return (
        cso.id,
        ContentFields(
            specification=cso.prose,
            question=cso.question,
            answer=str(cso.answer.value),
            reference=cso.reference_hml,
        ),
    )


def acq0_splits() -> list[CorpusFingerprint]:
    """Every ACQ0 split and every previously-shown corpus, built from its own source.

    Enumerated by *discovery*, not by a copied list of names:

    * every stage pool of the syntax-gate partition (demonstration, G2 screening,
      G3 curriculum, G4 confirmatory, G4 stochastic replication) — read from
      ``evaluation.syntax_gate.partition.STAGES`` so a new stage is covered automatically;
    * Track B, the V1 capability track;
    * the recorded Track A exclusions, which are still items the corpus has been built from;
    * the HML-EVAL-001 corpus of 120 objects, which was run against this exact model;
    * the HML-EVAL-001 demonstrations.

    Imports are local to the function so that importing this module never drags in the
    whole ACQ0 apparatus, and so a test can call it exactly once.
    """
    from evaluation.corpus.generators import build_all, build_demos
    from evaluation.syntax_gate.partition import partition
    from evaluation.syntax_gate.tasks import build_excluded, build_track_a, build_track_b

    out: list[CorpusFingerprint] = []

    # Every stage the partition actually emits, discovered from the partition itself.
    # A stage added upstream tomorrow is covered without editing this function.
    by_stage_ids: Mapping[str, Sequence[str]] = partition()["by_stage"]
    track_a = {t.id: t for t in build_track_a()}
    for stage, ids in sorted(by_stage_ids.items()):
        members = [track_a[i].cso for i in ids if i in track_a]
        out.append(fingerprint(f"acq0::{stage}", members, _cso_fields))

    out.append(
        fingerprint("acq0::track_b", [t.cso for t in build_track_b()], _cso_fields)
    )
    out.append(
        fingerprint(
            "acq0::track_a_exclusions", [t.cso for t in build_excluded()], _cso_fields
        )
    )
    out.append(fingerprint("hml_eval_001::corpus", build_all(), _cso_fields))
    out.append(fingerprint("hml_eval_001::demonstrations", build_demos(), _cso_fields))
    return out
