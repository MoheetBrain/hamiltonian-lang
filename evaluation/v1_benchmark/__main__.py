"""Command line. ``--design`` is always safe; ``--run`` needs the Lead's authorisation.

    python -m evaluation.v1_benchmark --design
    python -m evaluation.v1_benchmark --design --json > evaluation/results/v1_benchmark/design.json

    python -m evaluation.v1_benchmark --run \
        --authorised-by "<Lead>" \
        --scope "HML-V1 matched benchmark, 24 tasks" \
        --contention-cleared \
        --surface frozen_l1

``--run`` opens a model connection. It refuses without ``--contention-cleared``, which is
the operator asserting that no other study holds the Ollama server: a concurrent call
destroys the other study's latency measurements and cannot be undone.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evaluation.v1_benchmark.pipeline import (
    FROZEN_L1_SURFACE,
    RunAuthorisation,
    live_client,
    run_benchmark,
)
from evaluation.v1_benchmark.report import design_report, render_text, run_report, to_json
from evaluation.v1_benchmark.tasks import build_tasks

RESULTS = Path("evaluation/results/v1_benchmark")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="evaluation.v1_benchmark")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--design", action="store_true", help="design facts; no model, no data")
    mode.add_argument("--run", action="store_true", help="execute the benchmark (needs authorisation)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    ap.add_argument("--out", type=Path, default=None, help="write the report to this path")
    ap.add_argument("--authorised-by", default="", help="who authorised the run")
    ap.add_argument("--scope", default="", help="what the authorisation covers")
    ap.add_argument(
        "--contention-cleared",
        action="store_true",
        help="assert that no other study is holding the Ollama server",
    )
    ap.add_argument(
        "--surface",
        default="frozen_l1",
        choices=["frozen_l1"],
        help="the HML surface under test; extend once the syntax gate names a winner",
    )
    args = ap.parse_args(argv)

    if args.design:
        report = design_report()
    else:
        auth = RunAuthorisation(
            authorised_by=args.authorised_by,
            scope=args.scope,
            ollama_contention_cleared=args.contention_cleared,
        )
        result = run_benchmark(
            build_tasks(),
            client=live_client(auth),
            surface=FROZEN_L1_SURFACE,
            authorisation=auth,
        )
        report = run_report(result["_rows"])
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / "rows.json").write_text(json.dumps(result["rows"], indent=2, sort_keys=True))

    text = to_json(report) if args.json else render_text(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
