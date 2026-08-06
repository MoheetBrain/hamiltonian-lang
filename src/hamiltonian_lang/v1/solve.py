"""``python -m hamiltonian_lang.v1.solve`` — the one command.

::

    .venv/bin/python -m hamiltonian_lang.v1.solve --problem examples/v1_demo/algebra_rectangle.json

One command, one config file, one structured record, one compact summary. The record
goes to ``--json`` (or to the config's ``output_dir``) in full; the summary goes to
stdout and states the exact number of characters it omits wherever it shortens anything.

Exit codes
----------
``0`` the run completed and the final verdict was ``VERIFIED``
``1`` the run completed and the final verdict was anything else — a real result, not a
      crash, and the record says which
``2`` the run could not be made truthfully (bad config, missing front end, oracle leak)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .pipeline import (
    ConfigError,
    OracleGuardUnavailable,
    PipelineError,
    ProblemError,
    SolveConfig,
    SolveRecord,
    load_problem,
    render_summary,
    solve_problem,
)

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hamiltonian_lang.v1.solve",
        description=(
            "Run one mathematical problem through the V1 pipeline: reasoning draft, "
            "surface selection, parse, resolve, type-check, verify, first-failure "
            "diagnostic, one bounded repair, recompile, answer."
        ),
    )
    parser.add_argument("--problem", required=True, help="path to the problem JSON file")
    parser.add_argument("--config", default=None, help="path to the solve config JSON file")
    parser.add_argument(
        "--json",
        default=None,
        help="write the full structured record here (default: config output_dir, else none)",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="suppress the human-readable summary"
    )
    return parser


def _write_record(record: SolveRecord, config: SolveConfig, explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit)
    elif config.output_dir:
        path = Path(config.output_dir) / f"{record.problem['problem_id']}.solve.json"
    else:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.to_json() + "\n", encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = SolveConfig.load(args.config)
        problem = load_problem(args.problem)
        record = solve_problem(problem, config)
    except (ConfigError, ProblemError, PipelineError, OracleGuardUnavailable) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    written = _write_record(record, config, args.json)
    if not args.quiet:
        print(render_summary(record, max_chars=config.summary_max_chars))
        if written is not None:
            print(f"\nrecord  : {written}")
        else:
            print("\nrecord  : not written to disk (pass --json or set output_dir)")
    elif written is None:
        # --quiet with nowhere to write would discard the run; emit the record instead of
        # silently producing nothing.
        json.dump(record.to_dict(), sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
        sys.stdout.write("\n")
    return 0 if record.final_verdict == "VERIFIED" else 1


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    raise SystemExit(main())
