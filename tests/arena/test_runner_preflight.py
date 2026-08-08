"""Runner preflight: drive the entire path with a fake client, before any model is called.

This file exists because of a specific, expensive failure. The first developmental screen
completed all 24 of its model calls and then died in `main()` with
`NameError: _summarise`, because the module-entry guard had been placed above that
function's definition. Nothing was written. ~36 minutes of compute produced no record.

The lesson is not "be careful with module layout" -- it is that **the persistence path must
never be exercised for the first time by a run that costs something**. So the whole chain
is tested here end to end with a client that returns canned responses:

    CLI argv -> build items -> calls -> incremental JSONL -> summary JSON -> reload -> assert

Every assertion below is about plumbing, not about a model. A fake client with scripted
answers is exactly right for that: it makes the expected scores knowable in advance, so a
scoring or persistence regression shows up as a mismatch rather than as a plausible number.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evaluation.arena.endpoints import contrast
from evaluation.arena.run_screen import STAGES, RunSpec, build_dev_pairs, run_screen


class _FakeCompletion:
    def __init__(self, content, finish_reason="stop", ctok=42):
        self.content = content
        self.reasoning = "fake reasoning"
        self.prompt_tokens = 100
        self.completion_tokens = ctok
        self.total_tokens = 100 + ctok
        self.latency_s = 0.01
        self.finish_reason = finish_reason
        self.model_reported = "fake"
        self.error = None
        self.raw = {}


class _FakeClient:
    """Answers correctly, wrongly, or by truncating, on a fixed rotation.

    The rotation is deterministic, so the expected valid/correct counts are arithmetic and
    a change in scoring or persistence cannot hide behind a plausible-looking score.
    """

    def __init__(self, script):
        self.script = script
        self.n = 0
        self.seen_prompts = []

    def describe(self):
        return {"model": "fake", "digest": "0" * 64, "parameter_size": "0B"}

    def complete(self, system, user, *, attempt=0):
        self.seen_prompts.append(user)
        mode = self.script[self.n % len(self.script)]
        self.n += 1
        if mode == "truncate":
            return _FakeCompletion("thinking forever", finish_reason="length", ctok=8192)
        if mode == "correct":
            return _FakeCompletion(f"reasoning\n\nFINAL: {self._expected(user)}")
        return _FakeCompletion("reasoning\n\nFINAL: NOT_AN_ANSWER")

    @staticmethod
    def _expected(prompt):
        """Read the answer off the prompt is impossible, so the harness injects it."""
        return _FakeClient.answer_for(prompt)

    answers: dict = {}

    @classmethod
    def answer_for(cls, prompt):
        return cls.answers.get(prompt, "TRUE")


@pytest.fixture
def micro_pairs():
    cfg = STAGES["micro"]
    return build_dev_pairs(
        cfg["band"], "L3", cfg["n_per_contrast"], contrast.CONTRASTS,
        pair_offset=cfg["pair_offset"],
    )


def _spec(tmp_path, **kw):
    cfg = dict(STAGES["micro"])
    cfg.update(kw)
    return RunSpec(run_id="preflight", model="fake", level="L3", max_tokens=8192, **cfg)


def test_micro_stage_shape_is_six_pairs_two_per_contrast(micro_pairs):
    from collections import Counter

    assert len(micro_pairs) == 6
    counts = Counter(p[0].metrics["contrast"] for p in micro_pairs)
    assert set(counts.values()) == {2}, "micro screen must be balanced 2/2/2"
    assert len(counts) == 3


def test_micro_pairs_are_fresh_relative_to_the_first_dev_attempt(micro_pairs):
    """The 12B attempt spent pair indices 0..3 of each contrast; these must not overlap."""
    spent = build_dev_pairs("DEV_SELECTION", "L3", 4, contrast.CONTRASTS, pair_offset=0)
    spent_ids = {it.item_id for p in spent for it in p}
    fresh_ids = {it.item_id for p in micro_pairs for it in p}
    assert not (spent_ids & fresh_ids), "micro screen reuses items already spent on 12B"


def test_end_to_end_persistence_and_scoring(tmp_path, micro_pairs):
    """CLI-shaped run -> JSONL per call -> summary JSON -> reload -> assertions."""
    items = [it for p in micro_pairs for it in p]
    _FakeClient.answers = {}
    out_path = tmp_path / "run.json"

    # Script: every call answers correctly, so pair both-correct must be a clean 6/6.
    client = _FakeClient(["correct"])
    # Teach the fake which answer each prompt expects.
    from evaluation.arena.endpoints.common import build_prompt
    from evaluation.arena.parity import ARM_RENDERERS
    from evaluation.arena.run_screen import _INSTRUCTIONS

    for it in items:
        _FakeClient.answers[
            build_prompt(it, ARM_RENDERERS["SE"], instructions=_INSTRUCTIONS)
        ] = it.answer

    out = run_screen(
        _spec(tmp_path), items, pairs=micro_pairs, out_path=str(out_path), client=client
    )

    # --- incremental persistence: one JSONL line per call, written as it happened
    jsonl = Path(str(out_path) + "l")
    assert jsonl.exists(), "no incremental sidecar was written"
    lines = [json.loads(x) for x in jsonl.read_text().splitlines()]
    assert len(lines) == len(items) == 12

    # --- summary JSON on disk, reloadable, and agreeing with the in-memory result
    reloaded = json.loads(out_path.read_text())
    assert reloaded["summary"] == out["summary"]
    assert len(reloaded["records"]) == 12

    se = reloaded["summary"]["by_arm"]["SE"]
    assert se["items"] == 12 and se["valid"] == 12 and se["invalid"] == 0
    assert se["truncated"] == 0
    assert se["single_item_correct"] == 12
    assert se["pairs_scored"] == 6 and se["both_correct"] == 6
    assert se["both_correct_rate"] == 1.0
    assert reloaded["summary"]["any_truncation"] is False

    # --- every required per-call field is present
    for r in lines:
        for field in (
            "item_id", "pair_id", "arm", "seed", "band", "prompt_sha256", "expected",
            "raw_response", "parsed_answer", "valid", "correct", "latency_s",
            "prompt_tokens", "completion_tokens", "finish_reason",
        ):
            assert field in r, f"record is missing {field}"


def test_truncation_is_never_counted_as_wrong(tmp_path, micro_pairs):
    """A truncated response is absence of data. It must not be scored, and it invalidates."""
    items = [it for p in micro_pairs for it in p]
    out_path = tmp_path / "trunc.json"
    client = _FakeClient(["truncate"])

    out = run_screen(
        _spec(tmp_path), items, pairs=micro_pairs, out_path=str(out_path), client=client
    )
    se = out["summary"]["by_arm"]["SE"]
    assert se["valid"] == 0 and se["truncated"] == 12
    assert se["single_item_correct"] == 0
    assert se["single_item_accuracy"] is None, "accuracy over zero valid items is not 0.0"
    assert se["pairs_scored"] == 0 and se["pairs_dropped"] == 6
    assert se["both_correct_rate"] is None
    assert out["summary"]["any_truncation"] is True


def test_cli_entry_point_runs_end_to_end(tmp_path, monkeypatch):
    """Through `main()` with real argv -- the path that actually broke.

    The NameError that discarded 24 calls was only reachable via the module entry point,
    because that is where `main()` is invoked. Calling `run_screen` directly would never
    have caught it, so this test drives argv exactly as the command line does.
    """
    import evaluation.model_client as mc
    from evaluation.arena.endpoints.common import build_prompt
    from evaluation.arena.parity import ARM_RENDERERS
    from evaluation.arena.run_screen import _INSTRUCTIONS, main

    cfg = STAGES["micro"]
    pairs = build_dev_pairs(
        cfg["band"], "L3", cfg["n_per_contrast"], contrast.CONTRASTS,
        pair_offset=cfg["pair_offset"],
    )
    _FakeClient.answers = {
        build_prompt(it, ARM_RENDERERS["SE"], instructions=_INSTRUCTIONS): it.answer
        for p in pairs for it in p
    }
    monkeypatch.setattr(mc, "ModelClient", lambda cfg_: _FakeClient(["correct"]))

    out_path = tmp_path / "cli.json"
    rc = main(["micro", "--model", "fake", "--out", str(out_path), "--max-tokens", "8192"])
    assert rc == 0

    reloaded = json.loads(out_path.read_text())
    assert reloaded["spec"]["stage"] == "DEV_SELECTION"
    assert reloaded["spec"]["arms"] == ["SE"]
    assert reloaded["spec"]["max_tokens"] == 8192
    assert reloaded["summary"]["by_arm"]["SE"]["pairs_scored"] == 6
    assert len(Path(str(out_path) + "l").read_text().splitlines()) == 12


def test_cli_refuses_a_dev_stage_with_treatment_arms(tmp_path, monkeypatch):
    """The contamination guard must hold at the CLI level, not just in the library."""
    import evaluation.arena.run_screen as rs

    monkeypatch.setitem(rs.STAGES, "micro", dict(rs.STAGES["micro"], arms=("SE", "HML")))
    with pytest.raises(ValueError, match="structured-English only"):
        rs.main(["micro", "--model", "fake", "--out", str(tmp_path / "x.json")])


def test_a_crash_after_calls_cannot_destroy_records(tmp_path, micro_pairs, monkeypatch):
    """The exact failure that cost 24 calls: summarising blows up after the calls land."""
    import evaluation.arena.run_screen as rs

    items = [it for p in micro_pairs for it in p]
    out_path = tmp_path / "crash.json"
    monkeypatch.setattr(
        rs, "_summarise", lambda *a, **k: (_ for _ in ()).throw(NameError("boom"))
    )
    out = run_screen(
        _spec(tmp_path), items, pairs=micro_pairs, out_path=str(out_path),
        client=_FakeClient(["correct"]),
    )
    assert "summary_error" in out["summary"]
    assert out["summary"]["n_calls"] == 12
    # The expensive part survived, on disk, both ways.
    assert len(json.loads(out_path.read_text())["records"]) == 12
    assert len(Path(str(out_path) + "l").read_text().splitlines()) == 12
