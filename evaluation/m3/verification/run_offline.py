"""Offline evidence run. No model calls; every input is a fixture in this repository.

    .venv/bin/python -m evaluation.m3.verification.run_offline
    .venv/bin/python -m evaluation.m3.verification.run_offline --out evidence.json

What it produces
----------------
1. **fixture conformance** — every fixture's verdict against the verdict its manifest
   declares. A drift here is a regression in the engine, and the run exits non-zero.
2. **corpus coverage** — the verdict of every non-illustrative example under
   ``examples/``, with the share reaching ``VERIFIED`` and the share doing so
   *substantively*.
3. **H3 task subset** — which fixtures would be admitted as H3 tasks, with the reason
   for every exclusion.
4. **process metrics** — a scripted broken trace, its repair, and the effect.
5. **leakage control** — the four conditions over scripted responses, including a
   deliberately leaky diagnostic that the guard must reject.

The output is deterministic: no clocks, no randomness, no network. Two runs on the same
commit produce byte-identical JSON apart from the paths, which is what makes the
evidence re-derivable rather than merely re-readable.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections.abc import Sequence
from typing import Any

from hamiltonian_lang.verification.obligations import (
    ENGINE_VERSION,
    OBLIGATION_SCHEMA_VERSION,
    SUPPORTED_CLASSES,
    GlobalVerdict,
    verify_source,
)

from . import FIXTURES
from .leakage import Condition, Payload, find_answer_leak, run_conditions
from .process_metrics import Step, compare_repair, measure_trace
from .task_subset import build_subset, load_fixture_tasks

REPO = pathlib.Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Scripted trace fixtures — a derivation that goes wrong, and its repair
# ---------------------------------------------------------------------------

_BROKEN_TRACE_STEPS = (
    ("declare the variables", "module Budget\n\nvar spend : NonNegativeReal\n"),
    (
        "state the budget cap",
        "module Budget\n\nvar spend : NonNegativeReal\n\nrequire spend <= 100\n",
    ),
    (
        "state the floor -- wrong, it exceeds the cap",
        "module Budget\n\nvar spend : NonNegativeReal\n\n"
        "require spend <= 100\nrequire spend >= 150\n",
    ),
)

_REPAIRED_TRACE_STEPS = (
    ("declare the variables", "module Budget\n\nvar spend : NonNegativeReal\n"),
    (
        "state the budget cap",
        "module Budget\n\nvar spend : NonNegativeReal\n\nrequire spend <= 100\n",
    ),
    (
        "state the floor -- corrected",
        "module Budget\n\nvar spend : NonNegativeReal\n\n"
        "require spend <= 100\nrequire spend >= 50\n",
    ),
)

#: A safe diagnostic: it names the defect and the conflicting bounds, and supplies no
#: replacement program and no corrected value.
_SAFE_DIAGNOSTIC = (
    "The constraint set has no model. Two bounds on the same variable are mutually "
    "exclusive: an upper bound and a lower bound intersect to the empty set. Revisit "
    "which of the two bounds the problem actually states."
)

#: A leaky diagnostic, kept deliberately: the guard must reject it, and a control that
#: is never exercised on a positive case is not a control.
_LEAKY_DIAGNOSTIC = (
    "The constraint set has no model. Replace the program with:\n"
    "module Budget\n\nvar spend : NonNegativeReal\n\n"
    "require spend <= 100\nrequire spend >= 50\n"
)


def _scripted_responder(
    targets: dict[str, str], *, c_succeeds: bool = True
) -> Any:
    """A deterministic stand-in for a model.

    It encodes one hypothesis and nothing more: the correct diagnostic lets the repair
    land (condition C), the broken trace alone and a mismatched diagnostic do not (A and
    D), and the diagnostic alone cannot reconstruct the program (B). Running the harness
    against it checks the *harness*, not any model — which is the only thing that can be
    checked offline, and saying so is the point.
    """

    def respond(payload: Payload) -> str:
        if payload.condition is Condition.C_TRACE_PLUS_DIAGNOSTIC and c_succeeds:
            return targets[payload.task_id]
        return payload.broken_trace

    return respond


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def fixture_conformance() -> dict[str, Any]:
    manifest = json.loads((FIXTURES / "MANIFEST.json").read_text())
    rows: list[dict[str, Any]] = []
    mismatches = 0
    for entry in manifest["fixtures"]:
        path = FIXTURES / entry["file"]
        outcome = verify_source(path.read_text(), entry["file"])
        ok = (
            str(outcome.verdict) == entry["expected_verdict"]
            and outcome.substantive == entry["expected_substantive"]
        )
        mismatches += 0 if ok else 1
        rows.append(
            {
                "file": entry["file"],
                "expected_verdict": entry["expected_verdict"],
                "actual_verdict": str(outcome.verdict),
                "expected_substantive": entry["expected_substantive"],
                "actual_substantive": outcome.substantive,
                "classes": sorted({str(r.obligation_class) for r in outcome.records}),
                "match": ok,
            }
        )
    return {"mismatches": mismatches, "fixtures": rows}


def corpus_coverage() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in sorted((REPO / "examples").rglob("*.hml")):
        if any((parent / ".illustrative").exists() for parent in path.parents):
            continue
        outcome = verify_source(path.read_text(), str(path.relative_to(REPO)))
        rows.append(
            {
                "file": str(path.relative_to(REPO)),
                "verdict": str(outcome.verdict),
                "substantive": outcome.substantive,
                "obligations": len(outcome.records),
                "discharged_fraction": round(outcome.discharged_fraction, 6),
                "classes": sorted({str(r.obligation_class) for r in outcome.records}),
            }
        )
    total = len(rows)
    verified = sum(1 for r in rows if r["verdict"] == "VERIFIED")
    substantive = sum(1 for r in rows if r["verdict"] == "VERIFIED" and r["substantive"])
    return {
        "total": total,
        "verified": verified,
        "verified_fraction": round(verified / total, 6) if total else 0.0,
        "verified_substantively": substantive,
        "verified_substantively_fraction": round(substantive / total, 6) if total else 0.0,
        "examples": rows,
    }


def h3_subset() -> dict[str, Any]:
    return build_subset(load_fixture_tasks()).to_dict()


def process_section() -> dict[str, Any]:
    before = measure_trace(
        [Step(i, label, src) for i, (label, src) in enumerate(_BROKEN_TRACE_STEPS)]
    )
    after = measure_trace(
        [Step(i, label, src) for i, (label, src) in enumerate(_REPAIRED_TRACE_STEPS)]
    )
    return {
        "before_repair": before.to_dict(),
        "after_repair": after.to_dict(),
        "repair_effect": compare_repair(before, after).to_dict(),
    }


def leakage_section() -> dict[str, Any]:
    target = _REPAIRED_TRACE_STEPS[-1][1]
    broken = _BROKEN_TRACE_STEPS[-1][1]
    other_target = (FIXTURES / "positive_refinement_bound.hml").read_text()
    # Genuinely broken: `PositiveReal` is (0, inf), so `scale < 0` has no model at all.
    # A merely large bound would not do — `scale > 1000000` is satisfiable, and a
    # "broken" trace that verifies would inflate conditions A and D.
    other_broken = other_target.replace("require scale > 0", "require scale < 0")
    cases = [
        ("budget", broken, _SAFE_DIAGNOSTIC, target),
        (
            "refinement",
            other_broken,
            "A constraint is excluded by the declared type: the declared domain of the "
            "parameter cannot reach the bound the constraint demands. Reconsider the "
            "bound, or the declared type.",
            other_target,
        ),
    ]
    targets = {task_id: tgt for task_id, _b, _d, tgt in cases}
    report = run_conditions(cases, _scripted_responder(targets))
    leaky = find_answer_leak(_LEAKY_DIAGNOSTIC, target, broken)
    safe = find_answer_leak(_SAFE_DIAGNOSTIC, target, broken)
    return {
        "conditions": report.to_dict(),
        "guard_probe": {
            "leaky_diagnostic_rejected": bool(leaky),
            "leaky_findings": [f.to_dict() for f in leaky],
            "safe_diagnostic_rejected": bool(safe),
        },
    }


def build_report() -> dict[str, Any]:
    return {
        "engine_version": ENGINE_VERSION,
        "schema_version": OBLIGATION_SCHEMA_VERSION,
        "supported_classes": sorted(str(c) for c in SUPPORTED_CLASSES),
        "offline": True,
        "model_calls": 0,
        "fixture_conformance": fixture_conformance(),
        "corpus_coverage": corpus_coverage(),
        "h3_task_subset": h3_subset(),
        "process_metrics": process_section(),
        "leakage_control": leakage_section(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    report = build_report()
    blob = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(blob + "\n")

    coverage = report["corpus_coverage"]
    subset = report["h3_task_subset"]
    leak = report["leakage_control"]["conditions"]
    print(f"engine            : {report['engine_version']}")
    print(f"fixture mismatches: {report['fixture_conformance']['mismatches']}")
    print(
        f"corpus VERIFIED   : {coverage['verified']}/{coverage['total']} "
        f"({coverage['verified_fraction']:.1%}); substantively "
        f"{coverage['verified_substantively']}"
    )
    print(f"H3 admitted tasks : {subset['admitted']}/{subset['total']}")
    print(f"leakage admissible: {leak['admissible']}  rates {leak['rates']}")
    if args.out:
        print(f"evidence written  : {args.out}")

    failures = report["fixture_conformance"]["mismatches"]
    if not leak["admissible"]:
        print("NOT ADMISSIBLE: the scripted leakage control did not pass", file=sys.stderr)
        failures += 1
    if verify_source((FIXTURES / "positive_constraint_set.hml").read_text()).verdict is not (
        GlobalVerdict.VERIFIED
    ):
        print("NOT REACHABLE: a positive fixture failed to verify", file=sys.stderr)
        failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
