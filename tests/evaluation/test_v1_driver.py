"""The driver's crash-safety guarantees, tested without a model.

Every test here drives the real driver through a fake adapter. The point is that the
properties the experiment relies on — write-once records, resume-missing-only, refusal on
input drift, halt on truncation, halt on transport error — are *measured* rather than
asserted in a docstring.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from evaluation.model_adapters.ollama import Generation
from evaluation.v1_benchmark.arms import Arm
from evaluation.v1_benchmark.driver import (
    DriftDetected,
    RunPaths,
    build_manifest,
    run_arm,
    scientific_input_hash,
)
from evaluation.v1_benchmark.tasks import build_tasks


@dataclass
class FakeAdapter:
    """Serves canned generations. Records every prompt it was asked for."""

    content: str = "working here. <ANSWER>-2</ANSWER>"
    finish_reason: str = "stop"
    error: str | None = None
    digest: str = "fake"
    seen: list[tuple[str, str]] = field(default_factory=list)

    def generate(self, system: str, user: str, *, force: bool = False) -> Generation:
        self.seen.append((system, user))
        return Generation(
            content=self.content,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_s=0.01,
            finish_reason=self.finish_reason,
            error=self.error,
            cache_key="fake",
            model_digest=self.digest,
            captured_utc="2026-01-01T00:00:00Z",
        )


@pytest.fixture()
def paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RunPaths:
    import evaluation.v1_benchmark.driver as drv

    monkeypatch.setattr(drv, "RESULTS", tmp_path)
    p = RunPaths("t")
    p.ensure()
    return p


def _two_ids() -> list[str]:
    return [t.id for t in build_tasks()][:2]


def test_records_are_written_once_and_resume_skips_them(paths: RunPaths) -> None:
    ids = _two_ids()
    build_manifest(paths, task_ids=ids, note="test")

    a = FakeAdapter()
    run_arm(paths, Arm.SE, workers=1, adapter=a)
    assert len(list(paths.records.glob("*.json"))) == 2
    calls_after_first = len(a.seen)
    assert calls_after_first == 4  # 2 tasks x 2 calls

    # A second run must make no calls at all: everything is already recorded.
    b = FakeAdapter()
    prog = run_arm(paths, Arm.SE, workers=1, adapter=b)
    assert b.seen == []
    assert prog.done == 2


def test_a_partial_run_resumes_only_the_missing_task(paths: RunPaths) -> None:
    ids = _two_ids()
    build_manifest(paths, task_ids=ids, note="test")

    a = FakeAdapter()
    run_arm(paths, Arm.SE, task_ids=[ids[0]], workers=1, adapter=a)
    assert len(list(paths.records.glob("*.json"))) == 1

    b = FakeAdapter()
    run_arm(paths, Arm.SE, workers=1, adapter=b)
    assert len(b.seen) == 2  # only the one missing task, two calls
    assert len(list(paths.records.glob("*.json"))) == 2


def test_existing_record_is_never_clobbered(paths: RunPaths) -> None:
    ids = _two_ids()
    build_manifest(paths, task_ids=ids, note="test")
    run_arm(paths, Arm.SE, workers=1, adapter=FakeAdapter())

    target = paths.record(ids[0], str(Arm.SE))
    original = target.read_text()
    # Force a re-run of an already-recorded task with different content.
    run_arm(paths, Arm.SE, task_ids=[ids[0]], workers=1, adapter=FakeAdapter(content="DIFFERENT"))
    assert target.read_text() == original


def test_truncation_halts_the_run(paths: RunPaths) -> None:
    ids = _two_ids()
    build_manifest(paths, task_ids=ids, note="test")
    with pytest.raises(RuntimeError) as e:
        run_arm(paths, Arm.SE, workers=1, adapter=FakeAdapter(finish_reason="length"))
    assert "TruncationDetected" in str(e.value) or "allowance" in str(e.value)
    assert list(paths.records.glob("*.json")) == []


def test_transport_error_halts_the_run(paths: RunPaths) -> None:
    ids = _two_ids()
    build_manifest(paths, task_ids=ids, note="test")
    with pytest.raises(RuntimeError):
        run_arm(paths, Arm.SE, workers=1, adapter=FakeAdapter(error="HTTP 500"))
    assert list(paths.records.glob("*.json")) == []


def test_prompt_drift_is_refused(paths: RunPaths, monkeypatch: pytest.MonkeyPatch) -> None:
    ids = _two_ids()
    build_manifest(paths, task_ids=ids, note="test")

    manifest = json.loads(paths.manifest.read_text())
    manifest["scientific_input_hash"]["prompts"] = "0" * 64
    paths.manifest.write_text(json.dumps(manifest))

    with pytest.raises(DriftDetected) as e:
        run_arm(paths, Arm.SE, workers=1, adapter=FakeAdapter())
    assert "prompts" in str(e.value)


@pytest.mark.parametrize(
    "surface", ["tasks", "scorer", "compiler", "extraction", "diagnostics_budget"]
)
def test_every_scientific_surface_is_covered_by_the_drift_hash(surface: str) -> None:
    """A surface missing from the hash is a surface that can move undetected."""
    assert surface in scientific_input_hash()


def test_manifest_is_immutable_once_written(paths: RunPaths) -> None:
    ids = _two_ids()
    first = build_manifest(paths, task_ids=ids, note="original")
    second = build_manifest(paths, task_ids=ids[:1], note="changed")
    assert second == first
    assert second["note"] == "original"
    assert second["frozen_task_order"] == ids


def test_hml_arm_preserves_module_diagnostics_and_verdict(paths: RunPaths) -> None:
    ids = _two_ids()
    build_manifest(paths, task_ids=ids, note="test")
    a = FakeAdapter(
        content="reasoning\n```hml\nlet x : Real = undefined_name\n```\n<ANSWER>-2</ANSWER>"
    )
    run_arm(paths, Arm.HML_V1, task_ids=[ids[0]], workers=1, adapter=a)

    rec: dict[str, Any] = json.loads(paths.record(ids[0], str(Arm.HML_V1)).read_text())
    assert rec["hml"]["initial_module_emitted"] is True
    assert "undefined_name" in rec["hml"]["initial_module"]
    assert rec["hml"]["initial_verdict"]["emitted"] is True
    assert rec["hml"]["diagnostics_shown"]["truncated"] is False
    assert len(rec["calls"]) == 2
    for c in rec["calls"]:
        assert c["system"] and c["user"] and c["prompt_sha256"]
        assert c["requested_max_tokens"] == 4096


def test_both_arms_make_exactly_two_calls_per_task(paths: RunPaths) -> None:
    ids = _two_ids()
    build_manifest(paths, task_ids=ids, note="test")

    se = FakeAdapter()
    run_arm(paths, Arm.SE, task_ids=[ids[0]], workers=1, adapter=se)
    hml = FakeAdapter(content="```hml\nlet x : Real = 1.0\n```\n<ANSWER>-2</ANSWER>")
    run_arm(paths, Arm.HML_V1, task_ids=[ids[0]], workers=1, adapter=hml)

    assert len(se.seen) == 2
    assert len(hml.seen) == 2


def test_both_arms_receive_byte_identical_problem_text(paths: RunPaths) -> None:
    """The matched-content claim, checked on the prompts the driver actually sends."""
    ids = _two_ids()
    build_manifest(paths, task_ids=ids, note="test")
    task = next(t for t in build_tasks() if t.id == ids[0])

    se = FakeAdapter()
    run_arm(paths, Arm.SE, task_ids=[ids[0]], workers=1, adapter=se)
    hml = FakeAdapter(content="```hml\nlet x : Real = 1.0\n```\n<ANSWER>-2</ANSWER>")
    run_arm(paths, Arm.HML_V1, task_ids=[ids[0]], workers=1, adapter=hml)

    assert task.cso.prose in se.seen[0][1]
    assert task.cso.prose in hml.seen[0][1]
    assert task.cso.question in se.seen[0][1]
    assert task.cso.question in hml.seen[0][1]
    assert se.seen[0][0] == hml.seen[0][0]  # identical system prompt
