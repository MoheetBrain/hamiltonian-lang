"""Phase F2 — the partition, and the structural exclusion of Track B from the gate.

The load-bearing test in this file is
``test_track_b_cannot_change_the_gate_verdict``. The directive requires that it be
*structurally impossible* for Track B to affect the official gate, enforced by a test
rather than by a comment. The test is differential: it computes the verdict, appends a
Track B block engineered to fail every facet, recomputes, and asserts the two results are
bit-identical.
"""

from __future__ import annotations

import csv
import json
from collections import Counter

import pytest
from evaluation.syntax_gate import TRACK_A, TRACK_B
from evaluation.syntax_gate.candidates import (
    CANDIDATE_IDS,
    CORE_FEATURES,
    SHARED_CORE_FEATURES,
)
from evaluation.syntax_gate.partition import (
    CURRICULUM_SIZES,
    EXCLUDED_IDS,
    TRACK_A_DEMO_IDS,
    TRACK_A_G2_IDS,
    TRACK_A_G3_IDS,
    TRACK_A_GATE_IDS,
    TRACK_A_HELD_OUT_IDS,
    TRACK_A_REPLICATION_IDS,
    TRACK_B_IDS,
    demonstration_curriculum,
    partition,
    representability,
    track_a_membership,
    write_expressibility_matrix,
    write_partition_manifest,
)
from evaluation.syntax_gate.scorer import ScoredTrial
from evaluation.syntax_gate.stats import GATE_FACETS, gate_verdict
from evaluation.syntax_gate.tasks import (
    TRACK_A_DOMAINS,
    build_corpus,
    build_excluded,
    build_track_a,
    build_track_b,
    content_hash,
)

from hamiltonian_lang import compile_source

CORPUS = build_corpus()
TRACK_A_TASKS = build_track_a()


# ---------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------


def test_stage_pools_have_the_sizes_the_directive_requires():
    sizes = {k: len(v) for k, v in partition()["by_stage"].items()}
    assert sizes["G2_screening"] == 16
    assert sizes["G3_curriculum"] == 48
    assert sizes["G4_confirmatory"] == 80
    assert sizes["G4_replication"] == 40
    assert sizes["demonstration"] == 50


def test_g4_covers_eight_supported_domains_at_ten_each():
    by_domain = Counter(
        t.domain for t in TRACK_A_TASKS if t.id in TRACK_A_GATE_IDS
    )
    assert len(TRACK_A_DOMAINS) == 8
    assert set(by_domain) == set(TRACK_A_DOMAINS)
    assert set(by_domain.values()) == {10}


def test_curricula_are_nested_prefixes_of_the_demonstration_pool():
    assert CURRICULUM_SIZES == (0, 5, 10, 25, 50)
    previous: list[str] = []
    for n in CURRICULUM_SIZES:
        cur = demonstration_curriculum(n)
        assert len(cur) == n
        assert cur[: len(previous)] == previous, "curricula must nest"
        assert set(cur) <= TRACK_A_DEMO_IDS
        previous = cur


def test_the_ten_demonstration_curriculum_touches_every_domain():
    by_id = {t.id: t for t in TRACK_A_TASKS}
    domains = {by_id[i].domain for i in demonstration_curriculum(10)}
    assert domains == set(TRACK_A_DOMAINS)


# ---------------------------------------------------------------------------
# Disjointness, by content hash and not by name
# ---------------------------------------------------------------------------


def test_every_content_hash_in_the_corpus_is_unique():
    hashes = Counter(t.content_hash for t in CORPUS)
    duplicated = {h: c for h, c in hashes.items() if c > 1}
    assert not duplicated, f"{len(duplicated)} duplicated content hashes"


def test_demonstrations_and_held_out_tasks_are_disjoint_by_content_hash():
    by_id = {t.id: t for t in CORPUS}
    demo_hashes = {by_id[i].content_hash for i in TRACK_A_DEMO_IDS}
    held_out_hashes = {by_id[i].content_hash for i in TRACK_A_HELD_OUT_IDS}
    assert demo_hashes & held_out_hashes == set()
    assert len(demo_hashes) == 50
    assert len(held_out_hashes) == 184


def test_the_four_held_out_pools_are_mutually_disjoint():
    pools = [TRACK_A_G2_IDS, TRACK_A_G3_IDS, TRACK_A_GATE_IDS, TRACK_A_REPLICATION_IDS]
    for i, a in enumerate(pools):
        for b in pools[i + 1 :]:
            assert a & b == set()
    assert len(set().union(*pools)) == 184


def test_a_name_only_difference_would_not_defeat_the_hash_check():
    """The check must be on content, so an id change must not change the hash."""
    from dataclasses import replace

    t = TRACK_A_TASKS[0]
    renamed = replace(t, cso=replace(t.cso, id="totally_different_id"))
    assert renamed.content_hash == t.content_hash
    assert content_hash(renamed.cso) == content_hash(t.cso)


# ---------------------------------------------------------------------------
# Track A membership is mechanical
# ---------------------------------------------------------------------------


def test_every_track_a_task_uses_only_shared_core_features():
    for t in TRACK_A_TASKS:
        assert t.features <= SHARED_CORE_FEATURES, (t.id, sorted(t.features))


def test_every_declared_feature_is_in_the_closed_vocabulary():
    for t in CORPUS:
        assert t.features <= CORE_FEATURES, (t.id, sorted(t.features - CORE_FEATURES))


def test_every_track_a_task_is_representable_in_all_four_candidates():
    for t in TRACK_A_TASKS:
        repr_ = representability(t)
        assert all(repr_[c][0] for c in CANDIDATE_IDS), (t.id, repr_)


def test_excluded_tasks_are_recorded_with_an_axis_and_a_reason():
    axes = set()
    for t in build_excluded():
        ok, axis, reason = track_a_membership(t)
        assert ok is False
        assert axis, t.id
        assert len(reason) > 40, (t.id, reason)
        axes.add(axis)
    assert axes == {
        "quantifier_exists_unique",
        "concept_named_invariant",
        "surface_precedence_disambiguation",
    }
    assert len(EXCLUDED_IDS) == 12


def test_track_b_is_excluded_on_the_v1_capability_axis():
    for t in build_track_b():
        ok, axis, reason = track_a_membership(t)
        assert ok is False
        assert axis == "v1_capability_track"
        assert "Engineering validation only" in reason


# ---------------------------------------------------------------------------
# Corpus self-consistency
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("task", TRACK_A_TASKS, ids=[t.id for t in TRACK_A_TASKS])
def test_track_a_reference_encoding_compiles(task):
    result = compile_source(task.cso.reference_hml, task.id)
    assert result.ok(), [d.code for d in result.diagnostics.errors]


@pytest.mark.parametrize("task", TRACK_A_TASKS, ids=[t.id for t in TRACK_A_TASKS])
def test_track_a_reference_encoding_preserves_its_own_ground_truth(task):
    """A reference encoding that disagrees with its own facts makes every number
    computed from either of them suspect. This is the check that caught a real drift in
    the V0 corpus (60 of 120 references scored below 1.0)."""
    from evaluation.semantic_equiv import compare_semantics

    cmp = compare_semantics(task.cso, task.cso.reference_hml)
    score = cmp.score()
    if task.scored_facets:
        assert score == 1.0, (task.id, cmp.to_dict())
    else:
        assert score is None


def test_track_b_references_are_never_claimed_to_compile():
    for t in build_track_b():
        assert t.reference_syntax == "hml_v1_proposed"


def test_answer_options_never_leak_the_answer_by_ordering():
    """The correct option must not always be first, or the modal-guess floor is 1.0."""
    positions = Counter()
    for t in CORPUS:
        if t.cso.answer.kind == "choice" and t.cso.answer.options:
            positions[t.cso.answer.options.index(str(t.cso.answer.value))] += 1
    assert len(positions) > 1, positions


# ---------------------------------------------------------------------------
# The load-bearing test: Track B cannot move the gate
# ---------------------------------------------------------------------------


def _row(task_id, domain, condition, *, good: bool, tokens: int) -> ScoredTrial:
    return ScoredTrial(
        trial_id=f"t:{condition}:{task_id}", run_id="synthetic", task_id=task_id,
        domain=domain, condition=condition, curriculum_size=0,
        first_attempt_parse=good, repaired_parse=good,
        semantic_preservation=1.0 if good else 0.0, preserved=good,
        empty_or_truncated=not good, visible_output_length=100 if good else 0,
        completion_tokens_reasoning_inclusive=tokens,
        first_attempt_completion_tokens=tokens, latency_s=1.0,
        failure_category="ok" if good else "syntax_failure", answer_correct=good,
    )


def _clean_gate_rows(condition: str) -> list[ScoredTrial]:
    by_id = {t.id: t for t in CORPUS}
    rows = []
    for tid in sorted(TRACK_A_GATE_IDS):
        rows.append(_row(tid, by_id[tid].domain, condition, good=True, tokens=300))
        rows.append(
            _row(tid, by_id[tid].domain, "SE_structured_english", good=True, tokens=250)
        )
    return rows


def test_gate_verdict_passes_on_a_clean_synthetic_run():
    v = gate_verdict(_clean_gate_rows(CANDIDATE_IDS[0]), CANDIDATE_IDS[0])
    assert v["verdict"] == "PASS", v
    assert v["rows_considered"] == 80
    c1 = v["criteria"][0]
    assert (c1["numerator"], c1["denominator"]) == (80, 80)


def test_track_b_cannot_change_the_gate_verdict():
    """Differential proof, not an assurance.

    Append a Track B block engineered to fail every facet — every parse failed, nothing
    preserved, 333x the token cost — and assert every gate-bearing number is
    bit-identical. The **only** field permitted to change is the count of rows the gate
    explicitly refused, which exists so the refusal is visible rather than silent. If the
    gate ever reads a Track B row, this test fails loudly.
    """
    condition = CANDIDATE_IDS[0]
    clean = _clean_gate_rows(condition)
    poison = [
        _row(t.id, t.domain, condition, good=False, tokens=99_999)
        for t in build_track_b()
    ] + [
        _row(t.id, t.domain, "SE_structured_english", good=False, tokens=1)
        for t in build_track_b()
    ]

    v_before = gate_verdict(clean, condition)
    v_after = gate_verdict(clean + poison, condition)

    bookkeeping = "rows_dropped_before_counting"
    before = json.dumps(
        {k: v for k, v in v_before.items() if k != bookkeeping}, sort_keys=True
    )
    after = json.dumps(
        {k: v for k, v in v_after.items() if k != bookkeeping}, sort_keys=True
    )
    assert before == after, "Track B changed a gate-bearing number"
    assert v_after["verdict"] == v_before["verdict"] == "PASS"
    assert v_after["rows_considered"] == v_before["rows_considered"] == 80
    # The refusal is recorded, so "excluded" is auditable rather than assumed.
    assert v_before[bookkeeping] == {}
    assert v_after[bookkeeping]["not_in_G4_confirmatory_track_a"] == len(poison)


def test_known_failed_concept_admission_is_not_a_gate_facet():
    assert not any("concept" in f for f in GATE_FACETS)
    assert not any("admission" in f for f in GATE_FACETS)
    assert not any("mint" in f for f in GATE_FACETS)


def test_no_track_b_id_appears_in_any_track_a_stage():
    assert TRACK_B_IDS & TRACK_A_HELD_OUT_IDS == set()
    assert TRACK_B_IDS & TRACK_A_DEMO_IDS == set()
    assert TRACK_B_IDS & TRACK_A_GATE_IDS == set()


def test_excluded_task_ids_are_not_in_any_stage():
    assert EXCLUDED_IDS & TRACK_A_HELD_OUT_IDS == set()
    assert EXCLUDED_IDS & TRACK_A_DEMO_IDS == set()


# ---------------------------------------------------------------------------
# Artefacts
# ---------------------------------------------------------------------------


def test_expressibility_matrix_covers_every_task_with_a_reason(tmp_path):
    path = write_expressibility_matrix(tmp_path / "EXPRESSIBILITY_MATRIX.csv")
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == len(CORPUS)
    for r in rows:
        for c in CANDIDATE_IDS:
            assert r[f"representable_in_{c}"] in ("yes", "no")
            assert len(r[f"why_{c}"]) > 10, (r["task_id"], c)
        if r["in_track_a"] == "no":
            assert r["exclusion_axis"]
            assert len(r["exclusion_reason"]) > 40
    tracks = Counter(r["track"] for r in rows)
    assert tracks[TRACK_A] == 234
    assert tracks[TRACK_B] == 40
    assert tracks["A_candidate_excluded"] == 12


def test_committed_expressibility_matrix_matches_the_generator(tmp_path):
    """The committed CSV is a build artefact. If it drifts from the generator, the file
    a reader trusts and the partition the harness uses are two different things."""
    from evaluation.syntax_gate.partition import MATRIX_PATH

    fresh = write_expressibility_matrix(tmp_path / "fresh.csv")
    assert MATRIX_PATH.exists(), "run: python -m evaluation.syntax_gate.build --write"
    assert MATRIX_PATH.read_text() == fresh.read_text()


def test_partition_manifest_round_trips(tmp_path):
    path = write_partition_manifest(tmp_path / "PARTITION_MANIFEST.json")
    doc = json.loads(path.read_text())
    assert doc["official_gate_stage"] == "G4_confirmatory"
    assert doc["official_gate_size"] == 80
    assert doc["counts"]["track_a"] == 234
    assert doc["counts"]["track_b"] == 40
    assert set(doc["curricula"]) == {"0", "5", "10", "25", "50"}
    assert len(doc["content_hashes"]) == len(CORPUS)


def test_committed_partition_manifest_matches_the_generator(tmp_path):
    from evaluation.syntax_gate.partition import MANIFEST_PATH

    fresh = write_partition_manifest(tmp_path / "fresh.json")
    assert MANIFEST_PATH.exists(), "run: python -m evaluation.syntax_gate.build --write"
    assert MANIFEST_PATH.read_text() == fresh.read_text()
