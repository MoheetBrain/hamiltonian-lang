"""The Phase F4 freeze must actually detect drift, not merely record hashes.

A manifest nobody reads enforces nothing. These tests exercise the three properties the
directive depends on: a frozen manifest cannot be overwritten, a modified file is detected,
and an *added* file is detected too (a new renderer smuggled into a frozen tree changes the
experiment just as much as an edited one).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from evaluation import syntax_gate_freeze as F

REPO = Path(__file__).resolve().parents[2]


def _manifest_into(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(F, "OUT", tmp_path)
    return tmp_path / "FREEZE_MANIFEST_v1.0.json"


def test_verify_without_a_manifest_fails_rather_than_passing_vacuously(tmp_path, monkeypatch):
    """The dangerous failure is a verify that reports success because it found nothing."""
    assert F.verify(tmp_path / "absent.json") == 1


def test_write_then_verify_is_clean(tmp_path, monkeypatch):
    path = _manifest_into(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["freeze", "--write", "--version", "1.0"])
    assert F.main() == 0
    assert path.exists()
    assert F.verify(path) == 0


def test_a_frozen_manifest_is_never_overwritten(tmp_path, monkeypatch):
    _manifest_into(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["freeze", "--write", "--version", "1.0"])
    assert F.main() == 0
    # Second write of the same version must refuse: EVAL-DEFECT-001 was only handleable
    # because v1.0 survived verbatim next to v1.1.
    assert F.main() == 1


def test_modified_file_is_detected(tmp_path, monkeypatch):
    path = _manifest_into(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["freeze", "--write", "--version", "1.0"])
    assert F.main() == 0

    manifest = json.loads(path.read_text())
    victim = next(k for k, v in manifest["files"].items() if v != "<MISSING>")
    manifest["files"][victim] = "0" * 64
    path.write_text(json.dumps(manifest))

    assert F.verify(path) == 1, f"drift in {victim} went undetected"


def test_added_file_in_a_frozen_tree_is_detected(tmp_path, monkeypatch):
    """An added renderer changes the experiment as surely as an edited one."""
    path = _manifest_into(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["freeze", "--write", "--version", "1.0"])
    assert F.main() == 0

    manifest = json.loads(path.read_text())
    manifest["files"].pop(next(iter(manifest["files"])))  # simulate a file appearing later
    path.write_text(json.dumps(manifest))

    assert F.verify(path) == 1


def test_policies_state_the_rules_the_directive_requires():
    """These are load-bearing: each prevents a specific way of inflating a result."""
    p = F.POLICIES
    assert "MODEL FAILURE" in p["empty_output"]
    assert "never" in p["raw_output"].lower() or "append-only" in p["raw_output"].lower()
    assert "preserved" in p["transport_failure"]
    assert "separately" in p["repair"]
    assert "NOT a parse failure" in p["truncation"]


def test_gate_2_thresholds_match_the_directive():
    g = F.GATE_2
    assert g["repaired_parse_success"] == ">= 0.95"
    assert g["semantic_preservation"] == ">= 0.90"
    assert g["min_domain_repaired_parse"] == ">= 0.70"
    assert g["completion_token_cost_vs_structured_english"] == "<= 2.0x"


def test_client_workers_match_the_measured_slot_count():
    """4 workers measured 2.08x; 8 degraded to 1.43x. See EXECUTION_ENVIRONMENT.md."""
    assert F.SAMPLING["client_max_workers"] == F.SAMPLING["ollama_num_parallel"] == 4


def test_fifty_demo_curriculum_fits_the_measured_slot():
    s = F.SAMPLING
    assert s["measured_prompt_tokens_at_50_demos"] < s["context_tokens_per_slot"], (
        "the largest curriculum must fit one slot; if it stops fitting, lower "
        "OLLAMA_NUM_PARALLEL rather than truncating the curriculum"
    )


def test_module_runs_as_a_script():
    r = subprocess.run(
        [sys.executable, "-m", "evaluation.syntax_gate_freeze", "--verify"],
        capture_output=True, text=True, cwd=REPO, timeout=120,
    )
    assert r.returncode in (0, 1)
    assert "MANIFEST" in r.stdout or "FREEZE" in r.stdout


@pytest.mark.parametrize("rel", F.FROZEN_FILES)
def test_frozen_file_list_is_not_stale(rel: str):
    """A path that silently stopped existing would be frozen as '<MISSING>' forever."""
    path = REPO / rel
    if rel == "docs/evaluation/V1_FREEZE_MANIFEST.md" and not path.is_file():
        pytest.skip("produced by the Phase F1 audit; absent until that lands")
    assert path.is_file(), f"frozen path {rel} no longer exists"
