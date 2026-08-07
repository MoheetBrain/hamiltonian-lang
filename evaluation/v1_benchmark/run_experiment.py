"""One command that runs the complete experiment, gate included, without supervision.

    caffeinate -dimsu .venv/bin/python -m evaluation.v1_benchmark.run_experiment \
        --run-id decisive_01 > evaluation/results/v1_benchmark/logs/decisive_01.log 2>&1

The order is not a convenience, it is the design
------------------------------------------------
SE runs to completion **first**, and the headroom gate is evaluated on the complete SE
matrix **before a single HML call is made**. Two consequences, both intended:

* an insufficient-headroom finding costs no HML compute at all;
* the gate cannot be reached after the treatment results are already visible, so it cannot
  be argued with once the answer is inconvenient.

Resumption is safe at any point. Every stage checks what is already recorded and fills only
what is missing, so re-running this command after a crash continues rather than restarting,
and cannot overwrite a record.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from typing import Any

from evaluation.v1_benchmark.analyse import analyse
from evaluation.v1_benchmark.arms import Arm
from evaluation.v1_benchmark.driver import RunPaths, build_manifest, run_arm
from evaluation.v1_benchmark.protocol_v1_2 import EXCLUDED_TASKS, PROTOCOL
from evaluation.v1_benchmark.tasks import build_tasks

__all__ = ["headroom_verdict", "main"]

#: The pre-registered headroom bands, stated for 24 tasks and scaled proportionally.
IDEAL_LOW, IDEAL_HIGH = 8 / 24, 16 / 24
USABLE_LOW, USABLE_HIGH = 6 / 24, 18 / 24

#: The minimum number of valid paired tasks the measurement requires.
MIN_VALID_TASKS = 20


def headroom_verdict(correct: int, n: int) -> dict[str, Any]:
    """Classify the SE matrix. Bands are proportional, so N in 20..23 scales cleanly."""
    lo_ideal, hi_ideal = round(IDEAL_LOW * n), round(IDEAL_HIGH * n)
    lo_use, hi_use = round(USABLE_LOW * n), round(USABLE_HIGH * n)

    if lo_ideal <= correct <= hi_ideal:
        band = "IDEAL"
    elif lo_use <= correct <= hi_use:
        band = "USABLE"
    else:
        band = "INSUFFICIENT"

    return {
        "se_correct": correct,
        "n": n,
        "accuracy": round(correct / n, 4) if n else None,
        "band": band,
        "ideal_interval": [lo_ideal, hi_ideal],
        "usable_interval": [lo_use, hi_use],
        "proceed_to_hml": band in {"IDEAL", "USABLE"},
        "rule": (
            "For 24 tasks: ideal 8-16 correct, usable 6-18 excluding the ideal interval, "
            "insufficient 0-5 or 19-24. Scaled proportionally for N in 20-23."
        ),
    }


def _se_correct(paths: RunPaths, order: list[str]) -> tuple[int, int]:
    n = correct = 0
    for tid in order:
        p = paths.record(tid, str(Arm.SE))
        if not p.exists():
            continue
        n += 1
        if json.loads(p.read_text())["answer_correct"]:
            correct += 1
    return correct, n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the complete SE-vs-HML-V1 experiment")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--note", default="Decisive SE-versus-HML-V1 measurement.")
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args(argv)

    paths = RunPaths(args.run_id)
    paths.ensure()

    order = [t.id for t in build_tasks() if t.id not in EXCLUDED_TASKS]
    if len(order) < MIN_VALID_TASKS:
        verdict = {
            "verdict": "HML_BENCHMARK_FAILED_NO_SIGNAL",
            "reason": (
                f"only {len(order)} valid paired tasks survive pre-run exclusion, against a "
                f"required minimum of {MIN_VALID_TASKS}"
            ),
            "excluded": EXCLUDED_TASKS,
        }
        (paths.root / "DECISION.json").write_text(json.dumps(verdict, indent=2))
        print(json.dumps(verdict, indent=2))
        return 0

    build_manifest(paths, task_ids=order, note=args.note)
    print(f"=== {PROTOCOL} | run {args.run_id} | {len(order)} valid tasks ===", flush=True)
    for tid, why in EXCLUDED_TASKS.items():
        print(f"EXCLUDED {tid}: {why[:100]}...", flush=True)

    t0 = time.time()

    # ---- Stage 1: SE, the control and the headroom gate --------------------
    print("\n=== STAGE 1: SE arm (control, and the headroom gate) ===", flush=True)
    run_arm(paths, Arm.SE, workers=args.workers)

    correct, n = _se_correct(paths, order)
    gate = headroom_verdict(correct, n)
    (paths.root / "HEADROOM_GATE.json").write_text(json.dumps(gate, indent=2))
    print(
        f"\n=== HEADROOM GATE: {gate['band']} — SE {correct}/{n} "
        f"(ideal {gate['ideal_interval']}, usable {gate['usable_interval']}) ===",
        flush=True,
    )

    if not gate["proceed_to_hml"]:
        decision = {
            "verdict": "HML_BENCHMARK_FAILED_NO_SIGNAL",
            "protocol": PROTOCOL,
            "run_id": args.run_id,
            "reason": (
                f"The SE control scored {correct}/{n}, which falls in the INSUFFICIENT band. "
                "A corpus the control saturates or floors cannot discriminate between "
                "representations, so no HML call was made and no HML compute was spent."
            ),
            "headroom_gate": gate,
            "hml_arm_run": False,
            "wall_clock_s": round(time.time() - t0, 1),
        }
        (paths.root / "DECISION.json").write_text(json.dumps(decision, indent=2))
        print(json.dumps(decision, indent=2), flush=True)
        return 0

    # ---- Stage 2: HML-V1, the treatment ------------------------------------
    print("\n=== STAGE 2: HML-V1 arm (treatment) ===", flush=True)
    run_arm(paths, Arm.HML_V1, workers=args.workers)

    # ---- Stage 3: analysis and the mechanical decision ---------------------
    print("\n=== STAGE 3: paired analysis ===", flush=True)
    report = analyse(paths.root)
    report["headroom_gate"] = gate
    report["wall_clock_s"] = round(time.time() - t0, 1)
    (paths.root / "ANALYSIS.json").write_text(json.dumps(report, indent=2))

    decision = {
        "verdict": report["decision"]["verdict"],
        "protocol": PROTOCOL,
        "run_id": args.run_id,
        "model": report["model"],
        "model_digest": report["model_digest"],
        "n_valid_paired_tasks": report["paired_table"]["n"],
        "se_correct": report["paired_table"]["se_correct"],
        "hml_correct": report["paired_table"]["hml_correct"],
        "paired_difference": report["paired_table"]["paired_difference_hml_minus_se"],
        "mcnemar": report["mcnemar"],
        "bootstrap": report["bootstrap"],
        "headroom_gate": gate,
        "continuation_conditions": report["decision"]["continuation_conditions"],
        "kill_conditions": report["decision"]["kill_conditions"],
        "excluded_tasks": EXCLUDED_TASKS,
        "hml_arm_run": True,
        "wall_clock_s": report["wall_clock_s"],
    }
    (paths.root / "DECISION.json").write_text(json.dumps(decision, indent=2))

    print(f"\n=== DECISION: {decision['verdict']} ===", flush=True)
    print(
        f"SE {decision['se_correct']}/{decision['n_valid_paired_tasks']}  "
        f"HML {decision['hml_correct']}/{decision['n_valid_paired_tasks']}  "
        f"diff {decision['paired_difference']:+d}  "
        f"McNemar p={report['mcnemar']['p_value']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
