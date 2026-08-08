"""Harness and statistics.

Nothing in this file calls a model. The phase-ordering guard is itself under test: a
backend that reports ``LIVE = True`` must be refused until the Phase F4 freeze manifest
exists, because a call made before the offline equivalence gate passes would contaminate
the experiment.
"""

from __future__ import annotations

import json

import pytest
from evaluation.syntax_gate.candidates import (
    A_V0_LINEAR,
    CANDIDATE_IDS,
    SE_CONTROL,
    V0LinearAdapter,
)
from evaluation.syntax_gate.harness import (
    CONCURRENCY_CITATION,
    MAX_WORKERS,
    SCORING_WORKERS,
    PhaseGateError,
    RunConfig,
    StubAdapter,
    append_raw,
    run_tournament,
)
from evaluation.syntax_gate.partition import TRACK_A_GATE_IDS
from evaluation.syntax_gate.scorer import score_many
from evaluation.syntax_gate.stats import (
    GATE_THRESHOLDS,
    Proportion,
    condition_summary,
    design_facts,
    gate_verdict,
    pairwise_contrasts,
    proportion,
    token_cost_ratio,
)
from evaluation.syntax_gate.tasks import build_track_a
from evaluation.v1.score_v1 import NotMeasured

TASKS = build_track_a()
BY_ID = {t.id: t for t in TASKS}
GATE_TASKS = [BY_ID[i] for i in sorted(TRACK_A_GATE_IDS)]


# ---------------------------------------------------------------------------
# Measured concurrency
# ---------------------------------------------------------------------------


def test_model_call_concurrency_is_pinned_to_the_measured_optimum():
    """Four, not eight and not 18. Eight workers measured *worse* than four (1.43x vs
    2.08x) on this host, and the 18 cores do not decode a GPU-resident model at all."""
    assert MAX_WORKERS == 4
    assert "EXECUTION_ENVIRONMENT.md" in CONCURRENCY_CITATION
    assert "2.08x" in CONCURRENCY_CITATION and "1.43x" in CONCURRENCY_CITATION


def test_scoring_uses_the_cores_that_model_calls_cannot():
    """Scoring must not be throttled below what the machine can actually give it.

    The bare ``SCORING_WORKERS >= MAX_WORKERS`` was a portability error: ``MAX_WORKERS``
    is a *measured Ollama slot count* (a frozen scientific constant), while
    ``SCORING_WORKERS`` is *this machine's CPU capacity*. On the 18-core host the two
    happened to satisfy the inequality; on a 2-CPU CI runner it read ``2 >= 4`` and
    failed, asserting that hardware must exceed a constant it has nothing to do with.

    The invariant that was actually meant is throttle-freedom: scoring gets every core
    available, up to the point where more would not help. That is portable, and it still
    catches the regression this test was written for -- ``HML_JOBS=1`` leaking into
    scoring gives ``1 >= min(4, cpu)`` and fails on any machine with 2 or more cores.
    """
    import os

    assert SCORING_WORKERS >= min(MAX_WORKERS, os.cpu_count() or 1)


def test_the_conformance_serial_knob_does_not_throttle_scoring():
    """``HML_JOBS=1`` must not reach ``SCORING_WORKERS``.

    ``scripts/conformance.sh`` documents ``HML_JOBS=1`` as the way to force a serial
    pytest run when diagnosing an ordering-dependent failure. Reading the same variable
    here made that knob fail this module's own concurrency assertion on ``1 >= 4``, so
    the debugging tool broke the build for a reason unrelated to the bug being chased.

    A subprocess is used deliberately: ``importlib.reload`` rebinds the module's exception
    classes, so a reloaded ``PhaseGateError`` is no longer the one sibling tests catch.
    Verifying an import-time constant must not mutate this interpreter.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    env = {**os.environ, "HML_JOBS": "1"}
    env.pop("HML_SCORING_WORKERS", None)

    result = subprocess.run(
        [
            sys.executable, "-c",
            "from evaluation.syntax_gate.harness import SCORING_WORKERS, MAX_WORKERS;"
            "print(SCORING_WORKERS, MAX_WORKERS)",
        ],
        capture_output=True, text=True, cwd=repo, env=env, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    scoring, model = (int(x) for x in result.stdout.split())
    # Same portability correction as `test_scoring_uses_the_cores_that_model_calls_cannot`:
    # compare against what this machine can supply, not against the frozen slot count.
    expected = min(model, os.cpu_count() or 1)
    assert scoring >= expected, (
        f"HML_JOBS=1 leaked into scoring concurrency again: {scoring} < {expected}"
    )


def test_overriding_max_workers_is_recorded_in_the_run_notes():
    cfg = RunConfig(run_id="r", stage="G2_screening", max_workers=8)
    assert any("max_workers overridden" in n for n in cfg.notes)
    assert any("EXECUTION_ENVIRONMENT.md" in n for n in cfg.notes)


# ---------------------------------------------------------------------------
# Phase ordering
# ---------------------------------------------------------------------------


class _FakeLiveBackend:
    LIVE = True

    def generate(self, system, user):  # pragma: no cover - must never be reached
        raise AssertionError("a model call was made before the freeze")


def test_a_live_backend_is_refused_before_the_phase_f4_freeze(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "evaluation.syntax_gate.harness.RESULTS", tmp_path / "no-such-dir"
    )
    with pytest.raises(PhaseGateError) as e:
        run_tournament(
            TASKS[:1], [A_V0_LINEAR], _FakeLiveBackend(),
            RunConfig(run_id="r", stage="G2_screening", raw_dir=tmp_path),
        )
    assert "F3" in str(e.value) and "F4" in str(e.value)


def test_the_freeze_guard_is_what_blocks_the_live_backend(tmp_path, monkeypatch):
    """Negative control. With the freeze manifest present the guard lets the call
    through and the fake backend's own assertion fires, so the refusal above is the
    phase gate and not an unrelated failure."""
    results = tmp_path / "results"
    results.mkdir()
    (results / "FREEZE_MANIFEST.json").write_text('{"frozen": true}')
    monkeypatch.setattr("evaluation.syntax_gate.harness.RESULTS", results)
    with pytest.raises(AssertionError, match="a model call was made before the freeze"):
        run_tournament(
            TASKS[:1], [A_V0_LINEAR], _FakeLiveBackend(),
            RunConfig(run_id="r", stage="G2_screening", raw_dir=tmp_path),
        )


def test_a_prompt_over_the_slot_budget_is_refused_rather_than_truncated(
    tmp_path, monkeypatch
):
    """The server would silently truncate it, and a truncated curriculum is a different
    experimental condition wearing the same label."""
    from evaluation.syntax_gate.harness import ContextBudgetError

    results = tmp_path / "results"
    results.mkdir()
    (results / "FREEZE_MANIFEST.json").write_text('{"frozen": true}')
    monkeypatch.setattr("evaluation.syntax_gate.harness.RESULTS", results)

    class _Live(_FakeLiveBackend):
        pass

    with pytest.raises(ContextBudgetError) as e:
        run_tournament(
            TASKS[:1], [A_V0_LINEAR], _Live(),
            RunConfig(run_id="r", stage="G2_screening", raw_dir=tmp_path,
                      per_slot_token_budget=10),
        )
    assert "truncated curriculum is a different experimental condition" in str(e.value)


def test_an_acknowledged_overflow_is_recorded_in_the_run_notes(tmp_path, monkeypatch):
    results = tmp_path / "results"
    results.mkdir()
    (results / "FREEZE_MANIFEST.json").write_text('{"frozen": true}')
    monkeypatch.setattr("evaluation.syntax_gate.harness.RESULTS", results)
    cfg = RunConfig(
        run_id="ack", stage="G2_screening", raw_dir=tmp_path,
        per_slot_token_budget=10, acknowledge_context_overflow=True,
    )
    with pytest.raises(AssertionError):  # the fake backend's own guard fires
        run_tournament(TASKS[:1], [A_V0_LINEAR], _FakeLiveBackend(), cfg)
    assert any("context overflow acknowledged" in n for n in cfg.notes)


def test_the_run_manifest_records_the_context_budget_estimate(tmp_path):
    stub = StubAdapter(lambda s, u: "<ANSWER>1</ANSWER>")
    run_tournament(
        TASKS[:1], [A_V0_LINEAR], stub,
        RunConfig(run_id="budget", stage="G2_screening", raw_dir=tmp_path),
    )
    first = json.loads((tmp_path / "budget.jsonl").read_text().split("\n")[0])
    assert first["kind"] == "run_manifest"
    b = first["context_budget"]
    assert b["per_slot_token_budget"] == 8192
    assert b["estimate_only"] is True
    assert b["fits"] is True
    assert b["estimated_tokens_conservative"] > 0


def test_a_stub_backend_runs_without_a_freeze(tmp_path):
    stub = StubAdapter(lambda s, u: "<ANSWER>1</ANSWER>")
    trials = run_tournament(
        TASKS[:2], [A_V0_LINEAR], stub,
        RunConfig(run_id="stub", stage="G2_screening", raw_dir=tmp_path),
    )
    assert len(trials) == 2
    assert len(stub.calls) == 2


def test_the_ollama_backend_reports_itself_live():
    from evaluation.syntax_gate.harness import OllamaBackend

    assert OllamaBackend.LIVE is True
    assert StubAdapter.LIVE is False


# ---------------------------------------------------------------------------
# Raw log: append-only
# ---------------------------------------------------------------------------


def test_the_raw_log_is_append_only(tmp_path):
    append_raw("run1", {"kind": "a"}, raw_dir=tmp_path)
    append_raw("run1", {"kind": "b"}, raw_dir=tmp_path)
    lines = (tmp_path / "run1.jsonl").read_text().strip().split("\n")
    assert [json.loads(x)["kind"] for x in lines] == ["a", "b"]


def test_a_second_run_appends_and_never_overwrites(tmp_path):
    stub = StubAdapter(lambda s, u: "<ANSWER>1</ANSWER>")
    cfg = RunConfig(run_id="rerun", stage="G2_screening", raw_dir=tmp_path)
    run_tournament(TASKS[:1], [A_V0_LINEAR], stub, cfg)
    first = (tmp_path / "rerun.jsonl").read_text()
    run_tournament(TASKS[:1], [A_V0_LINEAR], stub, cfg)
    second = (tmp_path / "rerun.jsonl").read_text()
    assert second.startswith(first)
    assert len(second) > len(first)


def test_a_transport_failure_is_retried_with_every_attempt_preserved(tmp_path):
    stub = StubAdapter(lambda s, u: "<ANSWER>1</ANSWER>", fail_transport_times=2)
    trials = run_tournament(
        TASKS[:1], [A_V0_LINEAR], stub,
        RunConfig(run_id="retry", stage="G2_screening", raw_dir=tmp_path,
                  transport_retries=2, transport_backoff_s=0.0),
    )
    t = trials[0]
    assert t.error is None, "the third attempt succeeded"
    assert len(t.attempts) == 3
    assert [a["response"]["error"] is not None for a in t.attempts] == [True, True, False]
    # The original request is preserved on every attempt, not only the last.
    assert all(a["request"]["user"] == t.attempts[0]["request"]["user"] for a in t.attempts)


def test_an_empty_completion_is_never_retried(tmp_path):
    """The shared OllamaAdapter retries an empty completion once; this harness must not.
    An empty visible answer is a model failure under this milestone's contract."""
    stub = StubAdapter(lambda s, u: "")
    trials = run_tournament(
        TASKS[:1], [A_V0_LINEAR], stub,
        RunConfig(run_id="empty", stage="G2_screening", raw_dir=tmp_path,
                  transport_backoff_s=0.0),
    )
    assert len(stub.calls) == 1
    assert len(trials[0].attempts) == 1
    assert trials[0].content == ""


def test_the_ollama_backend_disables_the_shared_modules_empty_retry():
    """Read the constructed config rather than trusting the docstring."""
    import inspect

    from evaluation.syntax_gate.harness import OllamaBackend

    src = inspect.getsource(OllamaBackend.__init__)
    assert "retries=0" in src


# ---------------------------------------------------------------------------
# End to end, offline
# ---------------------------------------------------------------------------


def _responder(condition_ok: bool):
    def respond(system, user):
        # Recover which task this prompt is for by matching the reference encoding.
        for t in GATE_TASKS:
            if t.cso.prose in user:
                if not condition_ok:
                    return f"```hml\nmodule Broken\nconst a : Real = ((\n```\n<ANSWER>{t.cso.answer.value}</ANSWER>"
                return (
                    f"```hml\n{t.cso.reference_hml}```\n\n"
                    f"<ANSWER>{t.cso.answer.value}</ANSWER>"
                )
        return "<ANSWER>0</ANSWER>"

    return respond


def _run(condition, ok, tmp_path, run_id):
    stub = StubAdapter(_responder(ok))
    return run_tournament(
        GATE_TASKS, [condition], stub,
        RunConfig(run_id=run_id, stage="G4_confirmatory", raw_dir=tmp_path),
        adapters={A_V0_LINEAR: V0LinearAdapter()},
    )


def test_end_to_end_offline_gate_pass(tmp_path):
    trials = _run(A_V0_LINEAR, True, tmp_path, "e2e-pass")
    control = run_tournament(
        GATE_TASKS, [SE_CONTROL], StubAdapter(_responder(True)),
        RunConfig(run_id="e2e-se", stage="G4_confirmatory", raw_dir=tmp_path),
        adapters={},
    )
    scored = score_many(
        trials + control, BY_ID, {A_V0_LINEAR: V0LinearAdapter()}, workers=4
    )
    v = gate_verdict(scored, A_V0_LINEAR)
    assert v["verdict"] == "PASS", json.dumps(v, indent=1, default=str)[:2000]
    assert v["criteria"][0]["numerator"] == 80
    assert v["criteria"][0]["denominator"] == 80
    assert v["criteria"][2]["domains_below_floor"] == []


def test_end_to_end_offline_gate_fail(tmp_path):
    trials = _run(A_V0_LINEAR, False, tmp_path, "e2e-fail")
    control = run_tournament(
        GATE_TASKS, [SE_CONTROL], StubAdapter(_responder(True)),
        RunConfig(run_id="e2e-se2", stage="G4_confirmatory", raw_dir=tmp_path),
        adapters={},
    )
    scored = score_many(trials + control, BY_ID, {A_V0_LINEAR: V0LinearAdapter()})
    v = gate_verdict(scored, A_V0_LINEAR)
    assert v["verdict"] == "FAIL"
    assert "repaired_parse" in v["criteria_failed"]
    assert v["criteria"][0]["numerator"] == 0
    assert v["criteria"][0]["denominator"] == 80


def test_a_run_with_no_control_arm_reports_the_cost_criterion_as_not_measured(tmp_path):
    trials = _run(A_V0_LINEAR, True, tmp_path, "e2e-nocontrol")
    scored = score_many(trials, BY_ID, {A_V0_LINEAR: V0LinearAdapter()})
    v = gate_verdict(scored, A_V0_LINEAR)
    assert v["verdict"] == "NOT MEASURED"
    assert "completion_token_cost_vs_structured_english" in v["criteria_not_measured"]


def test_a_candidate_with_no_front_end_is_not_measured_rather_than_failed(tmp_path):
    trials = _run(CANDIDATE_IDS[2], True, tmp_path, "e2e-nofrontend")
    scored = score_many(trials, BY_ID, {})
    v = gate_verdict(scored, CANDIDATE_IDS[2])
    assert v["verdict"] == "NOT MEASURED"
    c1 = v["criteria"][0]
    assert c1["NOT MEASURED"] is True
    assert c1["not_measured_rows"] == 80
    assert any("syntax_acquisition" in r for r in c1["not_measured_reasons"])


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def test_every_proportion_reports_its_exact_numerator_and_denominator():
    p = Proportion(19, 20, 3, {"reason": 3})
    d = p.to_dict()
    assert (d["numerator"], d["denominator"], d["not_measured"]) == (19, 20, 3)
    assert d["rate"] == 0.95


def test_not_measured_rows_are_excluded_from_the_denominator_not_counted_as_zero():
    from evaluation.syntax_gate.scorer import ScoredTrial

    def row(v):
        return ScoredTrial(
            trial_id="t", run_id="r", task_id="x", domain="d", condition="c",
            curriculum_size=0, first_attempt_parse=v, repaired_parse=v,
            semantic_preservation=1.0, preserved=True, empty_or_truncated=False,
            visible_output_length=1, completion_tokens_reasoning_inclusive=1,
            first_attempt_completion_tokens=1, latency_s=1.0, failure_category="ok",
            answer_correct=True,
        )

    nm = NotMeasured(reason="no front end", denominator="0")
    p = proportion([row(True), row(False), row(nm)], "first_attempt_parse")
    assert (p.numerator, p.denominator, p.not_measured) == (1, 2, 1)
    assert p.value == 0.5


def test_the_gate_thresholds_are_the_preregistered_ones():
    assert GATE_THRESHOLDS == {
        "repaired_parse_min": 0.95,
        "semantic_preservation_min": 0.90,
        "domain_repaired_parse_floor": 0.70,
        "max_completion_token_ratio_vs_structured_english": 2.0,
    }


def test_statistics_are_standard_library_only():
    import evaluation.syntax_gate.stats as mod

    src = (mod.__file__ or "")
    text = open(src).read()
    for banned in ("import numpy", "import scipy", "import pandas", "from numpy",
                   "from scipy", "from pandas", "import statsmodels"):
        assert banned not in text, banned


def test_design_facts_are_computed_not_asserted():
    facts = design_facts()
    assert facts["gate_pool"] == 80
    mde = facts["minimum_detectable_effect"]
    assert mde["n_pairs"] == 80
    assert mde["min_one_directional_discordant_pairs"] >= 1
    assert facts["sanity"]["cohens_h_zero_for_equal_proportions"] is True
    assert facts["sanity"]["mcnemar_no_discordance_is_one"] is True


def test_token_cost_ratio_without_a_control_is_not_measured():
    r = token_cost_ratio([], CANDIDATE_IDS[0])
    assert r["NOT MEASURED"] is True
    assert "structured-English control" in r["reason"]


def test_pairwise_contrasts_report_discordant_pairs_and_exact_p(tmp_path):
    trials = _run(A_V0_LINEAR, True, tmp_path, "contrast-a")
    broken = _run(CANDIDATE_IDS[1], False, tmp_path, "contrast-b")
    scored = score_many(
        trials + broken, BY_ID,
        {A_V0_LINEAR: V0LinearAdapter(), CANDIDATE_IDS[1]: V0LinearAdapter()},
    )
    rows = pairwise_contrasts(scored, "repaired_parse")
    pair = next(
        r for r in rows
        if {r["treatment"], r["control"]} == {A_V0_LINEAR, CANDIDATE_IDS[1]}
    )
    assert pair["n_pairs"] == 80
    assert pair["discordant_treatment_better"] + pair["discordant_control_better"] == 80
    assert pair["mcnemar_exact_p"] < 0.001
    assert abs(pair["cohens_h"]) > 1.0


def test_condition_summary_carries_failure_categories(tmp_path):
    trials = _run(A_V0_LINEAR, False, tmp_path, "summary")
    scored = score_many(trials, BY_ID, {A_V0_LINEAR: V0LinearAdapter()})
    s = condition_summary(scored, A_V0_LINEAR)
    assert s["trials"] == 80
    assert s["failure_categories"]["syntax_failure"] == 80
    assert s["repaired_parse"]["numerator"] == 0
    assert s["repaired_parse"]["denominator"] == 80
