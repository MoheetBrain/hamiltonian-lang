"""Disjointness by content hash, against every corpus the model has seen or will see.

This module owns no checking logic. Every hash, every threshold and every comparison comes
from :mod:`evaluation.corpus_governance.contamination`, imported and not reimplemented.
What is here is the *wiring*: which foreign corpora this benchmark must be disjoint from,
and how a :class:`~evaluation.v1_benchmark.tasks.BenchTask` is reduced to the content
fields that machinery compares.

Checked by content, never by name
---------------------------------
The upstream module makes the argument in full. In short: comparing identifiers passes two
items that differ only in their id, which is exactly the leak the check exists to catch.
Three redundant checks run — exact digest, digest after case folding and punctuation
stripping, and a 5-token shingle Jaccard for paraphrase — and only the first two are
disqualifying. A shingle flag is a request for human judgement, not a rejection.

The registered foreign corpora
------------------------------
:func:`foreign_corpora` assembles them, and every one is built from *its own source of
truth* rather than from a copied list of ids, so a corpus that gains items upstream is
covered without anyone remembering to edit this file:

* ``acq0_splits()`` — every syntax-gate stage pool discovered from the partition itself,
  plus Track B, the recorded Track A exclusions, the HML-EVAL-001 corpus of 120 objects and
  its demonstrations. This is the superset that contains **ACQ0 Round 1**: Round 1 draws
  from the held-out stages (G2 screening, G3 curriculum, G4 confirmatory, G4 replication)
  and no separate Round-1 corpus exists in the tree yet, so checking every stage pool
  covers it now and will keep covering it after Round 1 is named.
* the **five frozen demonstrations** by their pinned ids, as a separately named fingerprint.
  They are already inside the demonstration stage pool, and the duplication is deliberate:
  the report has to be able to say "disjoint from the frozen five" as its own line, and a
  test that only checks the containing pool would still pass if the five were renamed.
* the **ACQ0 calibration tasks**, from ``calibration_tasks()``.
* every **M3-Lite partition**, from ``partitioned()`` — development, adversarial, promotion
  and transfer, each as its own fingerprint so a collision names the partition it hit.
* the **V1 concept-ablation corpus**, which is not on the Lead's list but is 60 authored
  problems in adjacent domains sitting in the same tree. Omitting it would leave the
  likeliest accidental overlap unchecked.

A hard collision is a build failure, not a warning
--------------------------------------------------
:func:`assert_clean` raises. A contaminated benchmark measures memory, and a memory
measurement that is reported as a reasoning measurement is worse than no benchmark.
"""

from __future__ import annotations

from typing import Any

from evaluation.corpus_governance.contamination import (
    ContaminationReport,
    ContentFields,
    CorpusFingerprint,
    check_contamination,
    fingerprint,
)
from evaluation.v1_benchmark.tasks import BenchTask, build_tasks

__all__ = [
    "ContaminationFailure",
    "bench_fields",
    "bench_fingerprint",
    "foreign_corpora",
    "check",
    "assert_clean",
]


class ContaminationFailure(AssertionError):
    """A benchmark task collided with a corpus the model has seen."""


def bench_fields(task: BenchTask) -> tuple[str, ContentFields]:
    """Reduce a benchmark task to the four content fields. Its id is not among them.

    ``reference`` is the empty string for every task in this corpus, because a reasoning
    benchmark has no authored encoding. That weakens the exact-digest check by one field
    and is stated here rather than left to be discovered: the specification and question
    still carry all the discriminating content, and the shingle pass runs over the
    specification regardless.
    """
    cso = task.cso
    return (
        cso.id,
        ContentFields(
            specification=cso.prose,
            question=cso.question,
            answer=str(cso.answer.value),
            reference=cso.reference_hml,
        ),
    )


def bench_fingerprint(tasks: list[BenchTask] | None = None) -> CorpusFingerprint:
    return fingerprint(
        "v1_benchmark",
        tasks if tasks is not None else build_tasks(),
        bench_fields,
    )


def _cso_fields(obj: Any) -> tuple[str, ContentFields]:
    """Extractor for anything exposing a CSO-shaped object."""
    cso = getattr(obj, "cso", obj)
    return (
        cso.id,
        ContentFields(
            specification=cso.prose,
            question=cso.question,
            answer=str(cso.answer.value),
            reference=cso.reference_hml,
        ),
    )


def foreign_corpora() -> list[CorpusFingerprint]:
    """Every corpus this benchmark must be disjoint from. Built from their own sources.

    Imports are local so that importing this module does not drag in the whole evaluation
    apparatus, matching the upstream module's convention.
    """
    from evaluation.acq0.protocols.calibration import (
        FROZEN_CURRICULUM_IDS,
        calibration_tasks,
    )
    from evaluation.corpus_governance.contamination import acq0_splits
    from evaluation.m3.lite.partitions import partitioned
    from evaluation.syntax_gate.tasks import build_track_a

    out: list[CorpusFingerprint] = list(acq0_splits())

    # The five frozen demonstrations, named in their own right.
    track_a = {t.id: t for t in build_track_a()}
    frozen = [track_a[i] for i in FROZEN_CURRICULUM_IDS if i in track_a]
    out.append(fingerprint("acq0::frozen_demonstrations_5", frozen, _cso_fields))

    # The ACQ0 calibration tasks.
    out.append(fingerprint("acq0::calibration_tasks", list(calibration_tasks()), _cso_fields))

    # Every M3-Lite partition, each named separately.
    for partition, items in sorted(partitioned().items(), key=lambda kv: str(kv[0])):
        out.append(fingerprint(f"m3_lite::{partition}", list(items), _cso_fields))

    # The V1 concept-ablation corpus and its demonstrations. Not on the Lead's list;
    # checked anyway, because 60 authored problems in adjacent domains in the same tree are
    # the likeliest place for an accidental overlap.
    from evaluation.v1.corpus import build_all_v1, build_demos_v1

    out.append(fingerprint("v1_concept_ablation::corpus", build_all_v1(), _cso_fields))
    out.append(fingerprint("v1_concept_ablation::demonstrations", build_demos_v1(), _cso_fields))

    return out


def check(tasks: list[BenchTask] | None = None) -> ContaminationReport:
    """Run all three checks against every registered foreign corpus."""
    return check_contamination(bench_fingerprint(tasks), foreign_corpora())


def assert_clean(tasks: list[BenchTask] | None = None) -> ContaminationReport:
    """Raise on any exact or normalised collision. Near-duplicates are returned, not raised."""
    report = check(tasks)
    if not report.clean():
        detail = "\n  ".join(
            f"{c.candidate_id} == {c.foreign_corpus}:{c.foreign_id} ({c.kind})"
            for c in report.hard_collisions
        )
        raise ContaminationFailure(
            f"{len(report.hard_collisions)} benchmark task(s) collided with a corpus the "
            f"model has already been shown:\n  {detail}\n"
            "A contaminated task measures memory. Reporting that as reasoning is worse "
            "than reporting nothing."
        )
    return report


def summary(tasks: list[BenchTask] | None = None) -> dict[str, Any]:
    report = check(tasks)
    return {
        "candidate_corpus": report.candidate_corpus,
        "n_tasks": len(bench_fingerprint(tasks)),
        "checked_against": list(report.checked_against),
        "n_foreign_corpora": len(report.checked_against),
        "clean": report.clean(),
        "hard_collisions": [c.to_dict() for c in report.hard_collisions],
        "flagged_near_duplicates": [c.to_dict() for c in report.flagged],
        "method": "content hash, never id: exact digest, normalised digest, 5-token shingle Jaccard",
    }
