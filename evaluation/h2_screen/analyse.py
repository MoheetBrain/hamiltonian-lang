"""Integrity audit and headroom analysis of the H2 eval001 screen. Read-only."""
from __future__ import annotations

import collections
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from evaluation.h2_screen.screen import SEEDS, load_corpus  # noqa: E402

OUT = pathlib.Path("evaluation/results/h2_headroom_screen/full")


def main() -> dict:
    manifest = json.loads((OUT / "MANIFEST.json").read_text())
    recs = [json.loads(p.read_text()) for p in sorted(OUT.glob("*seed*.json"))]
    pids = manifest["frozen_order"]

    # --- integrity ---
    have = {(r["task_id"], r["seed"]) for r in recs}
    want = {(p, s) for p in pids for s in SEEDS}
    integrity = {
        "matrix_complete": have == want,
        "missing": sorted(want - have),
        "extra": sorted(have - want),
        "duplicates": len(recs) - len(have),
        "truncations": sum(r["truncated"] for r in recs),
        "transport_failures": sum(1 for r in recs if r["transport_error"]),
        "scoring_failures": sum(1 for r in recs if r["scoring_failure"]),
        "prompt_hash_stable": all(
            r["prompt_sha256"] == manifest["prompt_hashes"][r["task_id"]] for r in recs),
        "model_digest_stable": len({r["model_digest"] for r in recs}) == 1,
        "records": len(recs),
    }

    # --- headroom ---
    by_task = collections.defaultdict(list)
    for r in recs:
        by_task[r["task_id"]].append(r["correct"])
    score = {t: sum(v) for t, v in by_task.items()}
    hist = collections.Counter(score.values())
    headroom = sorted(t for t, s in score.items() if s in (1, 2))

    problems = load_corpus()
    by_domain = collections.defaultdict(lambda: collections.Counter())
    for t, s in score.items():
        by_domain[problems[t]["domain"]][s] += 1

    # --- reliability: do the three samples agree? ---
    unanimous = sum(1 for v in by_task.values() if len(set(v)) == 1)

    cost = {
        "calls": len(recs),
        "prompt_tokens": sum(r["prompt_tokens"] for r in recs),
        "completion_tokens": sum(r["completion_tokens"] for r in recs),
        "median_latency_s": round(statistics.median(r["latency_s"] for r in recs), 1),
        "total_latency_h": round(sum(r["latency_s"] for r in recs) / 3600, 2),
    }

    n = len(headroom)
    verdict = ("HEADROOM_SUFFICIENT" if n >= 50 else
               "HEADROOM_LIMITED_BUT_PILOT_POSSIBLE" if n >= 30 else
               "HEADROOM_INSUFFICIENT")

    report = {"integrity": integrity, "histogram": {str(k): hist.get(k, 0) for k in range(4)},
              "per_domain": {d: {str(k): c.get(k, 0) for k in range(4)}
                             for d, c in sorted(by_domain.items())},
              "headroom_set": headroom, "headroom_count": n,
              "unanimous_tasks": unanimous, "cost": cost, "verdict": verdict,
              "mean_accuracy": round(sum(score.values()) / (len(score) * 3), 3)}
    (OUT.parent / "SCREEN_REPORT.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    r = main()
    i = r["integrity"]
    print(f"integrity: matrix_complete={i['matrix_complete']} dup={i['duplicates']} "
          f"trunc={i['truncations']} transport={i['transport_failures']} "
          f"scoring_fail={i['scoring_failures']} prompt_stable={i['prompt_hash_stable']} "
          f"digest_stable={i['model_digest_stable']} records={i['records']}")
    print(f"\nmean plain-English accuracy: {r['mean_accuracy']}")
    print("histogram  0/3 {0}  1/3 {1}  2/3 {2}  3/3 {3}".format(*[r["histogram"][str(k)] for k in range(4)]))
    print(f"headroom (1/3 or 2/3): {r['headroom_count']}  -> {r['verdict']}")
    print(f"unanimous across seeds: {r['unanimous_tasks']}/{sum(r['histogram'][str(k)] for k in range(4))}")
    print("\nper domain (0/3 1/3 2/3 3/3):")
    for d, h in r["per_domain"].items():
        print(f"  {d:16s} {h['0']:3d} {h['1']:3d} {h['2']:3d} {h['3']:3d}")
    c = r["cost"]
    print(f"\ncost: {c['calls']} calls, {c['completion_tokens']} completion tokens, "
          f"median {c['median_latency_s']}s, {c['total_latency_h']}h total")
