"""Emit the Phase F2 artefacts and run the offline self-check.

    PYTHONPATH=. .venv/bin/python -m evaluation.syntax_gate.build --write
    PYTHONPATH=. .venv/bin/python -m evaluation.syntax_gate.build --self-check

Nothing here calls a model. ``--self-check`` runs the mutation suite, so the honest
answer to "does the scorer work" is a command with a result, not an assurance.
"""

from __future__ import annotations

import argparse
import json
import sys

from .candidates import SYNTAX_ACQUISITION_INTERFACE, adapter_availability
from .mutations import MUTATIONS, run_mutation
from .partition import (
    summary,
    write_expressibility_matrix,
    write_partition_manifest,
)
from .prompts import spec_size_report
from .stats import design_facts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write the CSV and the manifest")
    ap.add_argument("--self-check", action="store_true", help="run the mutation suite")
    ap.add_argument("--report", action="store_true", help="print the design report")
    args = ap.parse_args(argv)
    if not (args.write or args.self_check or args.report):
        args.report = True

    rc = 0
    if args.write:
        print("wrote", write_expressibility_matrix())
        print("wrote", write_partition_manifest())

    if args.self_check:
        failures = []
        for m in MUTATIONS:
            ok, detail = run_mutation(m)
            if not ok:
                failures.append(detail)
        print(f"mutations: {len(MUTATIONS) - len(failures)}/{len(MUTATIONS)} satisfied")
        for f in failures:
            print("  FAIL", f)
        rc = rc or (1 if failures else 0)

    if args.report:
        print(
            json.dumps(
                {
                    "partition": summary(),
                    "prompt_matching": spec_size_report(),
                    "design_facts": design_facts(),
                    "adapters": adapter_availability(),
                    "required_interface": SYNTAX_ACQUISITION_INTERFACE,
                },
                indent=2,
                default=str,
            )
        )
    return rc


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
