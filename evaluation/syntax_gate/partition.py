"""Phase F2 — the fair benchmark partition.

Three jobs.

**Decide Track A membership mechanically.** A task is Track A iff every feature it uses
is supported by all four candidates *and* every ground-truth facet it populates is
scoreable in all four. Both halves are set containments over the tables in
``candidates``; neither is a judgement. A task that fails is **recorded with the axis and
the evidence**, never dropped, which is what ``EXPRESSIBILITY_MATRIX.csv`` exists to show.

**Cut disjoint stage pools.** Demonstrations (50, from which the 0/5/10/25/50 curricula
are nested prefixes) and the four held-out pools — G2 screening 16, G3 curriculum 48,
G4 confirmatory 80, G4 stochastic replication 40 — partition the 234 Track A tasks with
no overlap. Disjointness is asserted on the **content hash**, not the id, because two
tasks that differ only in their id would pass an id check and still leak a demonstration
into the held-out set.

**Name the official gate set once.** ``TRACK_A_GATE_IDS`` is the 80 G4 confirmatory
tasks and nothing else. ``stats.gate_verdict`` reads that frozenset and no other, which
is how Track B is kept structurally incapable of moving the gate.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from . import SYNTAX_GATE_VERSION, TRACK_A, TRACK_B
from .candidates import (
    CANDIDATE_IDS,
    CANDIDATES,
    CORE_FEATURES,
    FEATURE_EVIDENCE,
    SHARED_CORE_FEATURES,
    adapter_availability,
)
from .tasks import (
    TRACK_A_DOMAINS,
    GateTask,
    build_corpus,
    build_excluded,
    build_track_b,
)

__all__ = [
    "STAGES",
    "CURRICULUM_SIZES",
    "Placement",
    "representability",
    "track_a_membership",
    "partition",
    "demonstration_curriculum",
    "TRACK_A_GATE_IDS",
    "TRACK_A_REPLICATION_IDS",
    "TRACK_A_DEMO_IDS",
    "TRACK_B_IDS",
    "write_expressibility_matrix",
    "write_partition_manifest",
    "MATRIX_PATH",
    "MANIFEST_PATH",
]

REPO = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO / "benchmarks" / "syntax_gate" / "EXPRESSIBILITY_MATRIX.csv"
MANIFEST_PATH = REPO / "benchmarks" / "syntax_gate" / "PARTITION_MANIFEST.json"

#: (stage name, per-domain count, what the stage is for)
STAGES: tuple[tuple[str, int, str], ...] = (
    ("demonstration", 0, "worked examples; never scored, never held out"),
    ("G2_screening", 2, "screen the four candidates; 16 tasks"),
    ("G3_curriculum", 6, "select the demonstration curriculum; 48 tasks"),
    ("G4_confirmatory", 10, "the official Gate 2 set; 80 tasks, ~10 per domain"),
    ("G4_replication", 5, "stochastic replication at a second seed; 40 tasks"),
)

#: Nested prefixes of the demonstration pool. 0 is the zero-shot condition.
CURRICULUM_SIZES = (0, 5, 10, 25, 50)


@dataclass(frozen=True)
class Placement:
    task_id: str
    domain: str
    track: str
    stage: str
    content_hash: str
    in_track_a: bool
    exclusion_axis: str
    exclusion_reason: str


# ---------------------------------------------------------------------------
# Representability and scoreability
# ---------------------------------------------------------------------------


def representability(task: GateTask) -> dict[str, tuple[bool, str]]:
    """Per candidate: can this task be represented, and — always — why.

    The "why" is populated for a *yes* as well as a *no*. A matrix that explains only
    its refusals invites the reading that acceptance needed no reason.
    """
    out: dict[str, tuple[bool, str]] = {}
    for cid in CANDIDATE_IDS:
        cand = CANDIDATES[cid]
        missing = sorted(task.features - cand.features)
        if not missing:
            contested = sorted(task.features - SHARED_CORE_FEATURES)
            if contested:
                why = "; ".join(
                    FEATURE_EVIDENCE.get((f, cid), f"supported: {f}") for f in contested
                )
            else:
                why = "every feature used is in the shared core"
            out[cid] = (True, why)
        else:
            out[cid] = (
                False,
                "; ".join(
                    FEATURE_EVIDENCE.get(
                        (f, cid), f"{f}: not in this candidate's feature set"
                    )
                    for f in missing
                ),
            )
    return out


def scoreability(task: GateTask) -> dict[str, tuple[bool, str]]:
    """Per candidate: can the ground-truth facets be recovered from that surface."""
    out: dict[str, tuple[bool, str]] = {}
    for cid in CANDIDATE_IDS:
        missing = sorted(task.scored_facets - CANDIDATES[cid].scoreable_facets)
        if missing:
            out[cid] = (False, f"facets not recoverable from this surface: {missing}")
        elif not task.scored_facets:
            out[cid] = (
                False,
                "the answer key populates no comparable facet, so semantic "
                "preservation has no denominator here and would be NOT MEASURED",
            )
        else:
            out[cid] = (True, f"facets recoverable: {sorted(task.scored_facets)}")
    return out


def track_a_membership(task: GateTask) -> tuple[bool, str, str]:
    """(is Track A, exclusion axis, exclusion reason). Axis is "" when included."""
    if task.track == TRACK_B:
        return False, "v1_capability_track", (
            "Track B by construction: uses "
            f"{sorted(task.features & (CORE_FEATURES - SHARED_CORE_FEATURES))}. "
            "Engineering validation only; excluded from the gate."
        )
    repr_ = representability(task)
    unrepresentable = [c for c in CANDIDATE_IDS if not repr_[c][0]]
    if unrepresentable:
        missing = sorted(task.features - SHARED_CORE_FEATURES)
        return False, ("+".join(missing) or "unrepresentable"), (
            "not representable in "
            + ", ".join(unrepresentable)
            + " -- "
            + " | ".join(f"{c}: {repr_[c][1]}" for c in unrepresentable)
        )
    score_ = scoreability(task)
    unscoreable = [c for c in CANDIDATE_IDS if not score_[c][0]]
    if unscoreable:
        return False, "not_scoreable", (
            "representable everywhere but not scoreable in "
            + ", ".join(unscoreable)
            + " -- "
            + " | ".join(f"{c}: {score_[c][1]}" for c in unscoreable)
        )
    return True, "", ""


# ---------------------------------------------------------------------------
# Stage assignment
# ---------------------------------------------------------------------------


def _assign_stages(tasks: list[GateTask]) -> dict[str, str]:
    """Deterministic per-domain slicing. Demonstrations take the remainder.

    Held-out counts are fixed first, so a change in corpus size can only change the
    number of demonstrations. Silently shrinking the confirmatory set to make a corpus
    fit would change the gate's power without changing the gate.
    """
    stage_of: dict[str, str] = {}
    held_out = [(name, n) for name, n, _ in STAGES if name != "demonstration"]
    for domain in TRACK_A_DOMAINS:
        items = sorted(
            (t for t in tasks if t.domain == domain and t.track == TRACK_A
             and not t.intentionally_excluded),
            key=lambda t: t.id,
        )
        need = sum(n for _, n in held_out)
        if len(items) < need:
            raise AssertionError(
                f"domain {domain}: {len(items)} tasks cannot fill {need} held-out slots"
            )
        n_demo = len(items) - need
        cursor = 0
        for t in items[:n_demo]:
            stage_of[t.id] = "demonstration"
        cursor = n_demo
        for name, n in held_out:
            for t in items[cursor : cursor + n]:
                stage_of[t.id] = name
            cursor += n
    return stage_of


def _demo_order(tasks: list[GateTask], stage_of: dict[str, str]) -> list[str]:
    """Round-robin over domains, so every curriculum prefix is as balanced as it can be.

    A 5-demonstration curriculum drawn in id order would be five tasks from one domain,
    which measures that domain rather than the curriculum size.
    """
    per_domain: dict[str, list[str]] = {d: [] for d in TRACK_A_DOMAINS}
    for t in sorted(tasks, key=lambda t: t.id):
        if stage_of.get(t.id) == "demonstration":
            per_domain[t.domain].append(t.id)
    order: list[str] = []
    row = 0
    while any(len(v) > row for v in per_domain.values()):
        for d in TRACK_A_DOMAINS:
            if len(per_domain[d]) > row:
                order.append(per_domain[d][row])
        row += 1
    return order


_CACHE: dict | None = None


def partition() -> dict:
    """The frozen partition. Deterministic; identical on every call and every machine."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    corpus = build_corpus()
    placements: list[Placement] = []
    track_a: list[GateTask] = []
    for t in corpus:
        ok, axis, reason = track_a_membership(t)
        if ok:
            track_a.append(t)
        placements.append(
            Placement(
                task_id=t.id, domain=t.domain, track=TRACK_A if ok else TRACK_B,
                stage="", content_hash=t.content_hash,
                in_track_a=ok, exclusion_axis=axis, exclusion_reason=reason,
            )
        )

    stage_of = _assign_stages(track_a)
    demo_order = _demo_order(track_a, stage_of)
    placements = [
        Placement(
            p.task_id, p.domain, p.track, stage_of.get(p.task_id, "excluded"),
            p.content_hash, p.in_track_a, p.exclusion_axis, p.exclusion_reason,
        )
        for p in placements
    ]

    by_stage: dict[str, list[str]] = {}
    for p in placements:
        by_stage.setdefault(p.stage, []).append(p.task_id)

    _CACHE = {
        "version": SYNTAX_GATE_VERSION,
        "placements": placements,
        "stage_of": stage_of,
        "demo_order": demo_order,
        "by_stage": {k: sorted(v) for k, v in by_stage.items()},
        "hash_of": {p.task_id: p.content_hash for p in placements},
    }
    return _CACHE


def _ids(stage: str) -> frozenset[str]:
    return frozenset(partition()["by_stage"].get(stage, ()))


def demonstration_curriculum(size: int) -> list[str]:
    """The first ``size`` demonstrations in round-robin order. Curricula are nested."""
    if size not in CURRICULUM_SIZES:
        raise ValueError(f"curriculum size must be one of {CURRICULUM_SIZES}, got {size}")
    return partition()["demo_order"][:size]


TRACK_A_DEMO_IDS = _ids("demonstration")
TRACK_A_G2_IDS = _ids("G2_screening")
TRACK_A_G3_IDS = _ids("G3_curriculum")

#: **The official gate set.** ``stats.gate_verdict`` reads this and nothing else.
TRACK_A_GATE_IDS = _ids("G4_confirmatory")
TRACK_A_REPLICATION_IDS = _ids("G4_replication")
TRACK_A_HELD_OUT_IDS = (
    TRACK_A_G2_IDS | TRACK_A_G3_IDS | TRACK_A_GATE_IDS | TRACK_A_REPLICATION_IDS
)
TRACK_B_IDS = frozenset(t.id for t in build_track_b())
EXCLUDED_IDS = frozenset(t.id for t in build_excluded())


# ---------------------------------------------------------------------------
# Artefacts
# ---------------------------------------------------------------------------

_MATRIX_COLUMNS = (
    ["task_id", "track", "domain", "difficulty", "content_sha256", "stage",
     "features_used", "scored_facets"]
    + [f"representable_in_{c}" for c in CANDIDATE_IDS]
    + [f"why_{c}" for c in CANDIDATE_IDS]
    + [f"scoreable_in_{c}" for c in CANDIDATE_IDS]
    + ["in_track_a", "exclusion_axis", "exclusion_reason"]
)


def write_expressibility_matrix(path: Path | None = None) -> Path:
    """Deliverable 2. Every task, every candidate, and the evidence for each verdict."""
    path = Path(path or MATRIX_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    by_id = {t.id: t for t in build_corpus()}
    part = partition()
    rows = []
    for p in part["placements"]:
        t = by_id[p.task_id]
        repr_ = representability(t)
        score_ = scoreability(t)
        row = {
            "task_id": t.id,
            "track": TRACK_A if p.in_track_a else (
                TRACK_B if t.track == TRACK_B else "A_candidate_excluded"
            ),
            "domain": t.domain,
            "difficulty": t.cso.difficulty,
            "content_sha256": p.content_hash,
            "stage": p.stage,
            "features_used": " ".join(sorted(t.features)),
            "scored_facets": " ".join(sorted(t.scored_facets)) or "(none)",
            "in_track_a": "yes" if p.in_track_a else "no",
            "exclusion_axis": p.exclusion_axis,
            "exclusion_reason": p.exclusion_reason,
        }
        for c in CANDIDATE_IDS:
            row[f"representable_in_{c}"] = "yes" if repr_[c][0] else "no"
            row[f"why_{c}"] = repr_[c][1]
            row[f"scoreable_in_{c}"] = "yes" if score_[c][0] else "no"
        rows.append(row)
    with path.open("w", newline="", encoding="ascii", errors="strict") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(_MATRIX_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_partition_manifest(path: Path | None = None) -> Path:
    """The frozen partition, with content hashes, for the Phase F4 execution manifest."""
    path = Path(path or MANIFEST_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = partition()
    by_id = {t.id: t for t in build_corpus()}
    doc = {
        "version": SYNTAX_GATE_VERSION,
        "counts": {
            "corpus_total": len(by_id),
            "track_a": sum(1 for p in part["placements"] if p.in_track_a),
            "track_a_candidates_excluded": len(EXCLUDED_IDS),
            "track_b": len(TRACK_B_IDS),
        },
        "stage_sizes": {k: len(v) for k, v in sorted(part["by_stage"].items())},
        "official_gate_stage": "G4_confirmatory",
        "official_gate_size": len(TRACK_A_GATE_IDS),
        "curricula": {
            str(n): demonstration_curriculum(n) for n in CURRICULUM_SIZES
        },
        "stages": {
            stage: sorted(ids) for stage, ids in sorted(part["by_stage"].items())
        },
        "content_hashes": dict(sorted(part["hash_of"].items())),
        "shared_core_features": sorted(SHARED_CORE_FEATURES),
        "features_outside_shared_core": sorted(CORE_FEATURES - SHARED_CORE_FEATURES),
        "invariants_asserted_by_tests": [
            "demonstration and held-out content hashes are disjoint",
            "every content hash in the corpus is unique",
            "no Track B id appears in any Track A stage",
            "gate_verdict is bit-identical with and without arbitrary Track B trials",
        ],
    }
    path.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n")
    return path


def summary() -> dict:
    """Counts, for a caller that wants the shape of the partition without the ids."""
    part = partition()
    included = [p for p in part["placements"] if p.in_track_a]
    by_domain: dict[str, dict[str, int]] = {}
    for p in included:
        by_domain.setdefault(p.domain, {}).setdefault(p.stage, 0)
        by_domain[p.domain][p.stage] += 1
    return {
        "version": SYNTAX_GATE_VERSION,
        "track_a": len(included),
        "track_b": len(TRACK_B_IDS),
        "excluded_track_a_candidates": len(EXCLUDED_IDS),
        "stage_sizes": {k: len(v) for k, v in sorted(part["by_stage"].items())},
        "by_domain": by_domain,
        "adapter_availability": adapter_availability(),
    }
