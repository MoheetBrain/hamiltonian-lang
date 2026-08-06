"""Report assembly. Two commands, and the difference between them is the point.

``--design`` reports facts about the **design**: the tasks, their predicted difficulty
bands, the contamination verdict, the matching table and the decision rule. It runs with no
data and calls no model, because none of it is a result.

``--run`` reports facts about a **run**. It requires rows.

Every report carries :data:`~evaluation.v1_benchmark.sequential.DEVELOPMENTAL_STANDING`,
and :func:`render_text` refuses to emit a verdict without it. A 24- or 40-task paired
comparison on one model is a developmental signal; the wording that says so is part of the
artefact rather than a note in the margin, because margins are where caveats go to be
dropped on the way to a summary.

The two claims are rendered in separate sections with separate denominators — answer
accuracy under one heading, verified completion under another — and the H3 line names what
it is not, using :attr:`Hypothesis.excluded_claim` from the canonical type rather than a
paraphrase.
"""

from __future__ import annotations

import json
from typing import Any

from evaluation.v1_benchmark import contamination
from evaluation.v1_benchmark.arms import (
    CALLS_PER_ARM,
    MATCHING,
    MODEL,
    MODEL_DIGEST,
    PER_CALL_BUDGET,
    RUNTIME,
    TEMPERATURE,
    TOTAL_COMPLETION_BUDGET,
)
from evaluation.v1_benchmark.difficulty import PREDICTED_NOT_MEASURED, TARGET_BAND
from evaluation.v1_benchmark.scoring import Aggregate, TrialResult, aggregate
from evaluation.v1_benchmark.sequential import (
    DEVELOPMENTAL_STANDING,
    NULL_THRESHOLD,
    PROBABILITY_THRESHOLD,
    UPLIFT_THRESHOLD_POINTS,
    Decision,
    decide,
)
from evaluation.v1_benchmark.tasks import (
    EXTENSION_COUNT,
    TASK_COUNT,
    V1_BENCHMARK_VERSION,
    build_tasks,
    by_domain,
)

from hamiltonian_lang.improvement.state import Hypothesis

__all__ = ["design_report", "run_report", "render_text", "MissingStanding"]


class MissingStanding(AssertionError):
    """A verdict was rendered without the standing that qualifies it."""


def design_report() -> dict[str, Any]:
    """Everything true about the design before any model is run."""
    tasks = build_tasks()
    return {
        "study": "HML-V1-MATCHED-BENCHMARK",
        "corpus_version": V1_BENCHMARK_VERSION,
        "bears_on": {
            "hypotheses": ["H2", "H3"],
            "H2": Hypothesis.H2.claim,
            "H3": Hypothesis.H3.claim,
            "H3_does_not_support": Hypothesis.H3.excluded_claim,
            "not_acq0": (
                "This benchmark is not ACQ0 and not H1. ACQ0 asks whether the model can "
                "write the syntax at all; a result here says nothing about that question, "
                "and an ACQ0 result says nothing about this one."
            ),
        },
        "runtime": {
            "model": MODEL,
            "model_digest": MODEL_DIGEST,
            "temperature": TEMPERATURE,
            "runtime": RUNTIME,
            "calls_per_arm": CALLS_PER_ARM,
            "per_call_completion_budget": PER_CALL_BUDGET,
            "total_completion_budget_per_task_per_arm": TOTAL_COMPLETION_BUDGET,
        },
        "matching": [m.to_dict() for m in MATCHING],
        "tasks": {
            "n": len(tasks),
            "pre_registered_tranche": TASK_COUNT,
            "extension": EXTENSION_COUNT,
            "domains": {d: len(v) for d, v in by_domain(tasks).items()},
            "difficulty_status": PREDICTED_NOT_MEASURED,
            "target_band": list(TARGET_BAND),
            "items": [t.to_dict() for t in tasks],
        },
        "contamination": contamination.summary(tasks),
        "decision_rule": {
            "posterior": "theta | D ~ Beta(1 + w, 1 + l); report P(theta > 0.5 | D)",
            "w": "solved by HML-V1 and not by SE",
            "l": "solved by SE and not by HML-V1",
            "strong_signal": (
                f"P >= {float(PROBABILITY_THRESHOLD)} AND absolute uplift >= "
                f"{UPLIFT_THRESHOLD_POINTS} points"
            ),
            "no_benefit": f"P <= {float(NULL_THRESHOLD)}",
            "otherwise": f"extend to {EXTENSION_COUNT}, then close as INCONCLUSIVE",
        },
        "standing": DEVELOPMENTAL_STANDING,
        "measured": False,
    }


def run_report(rows: list[TrialResult], *, tranche: int | None = None) -> dict[str, Any]:
    """Facts about a run. Both claims, separated."""
    agg: Aggregate = aggregate(rows)
    overall: Decision = decide(agg.overall, tranche=tranche)
    h2_only: Decision = decide(agg.h2_restricted, tranche=tranche)
    return {
        "study": "HML-V1-MATCHED-BENCHMARK",
        "corpus_version": V1_BENCHMARK_VERSION,
        "n_rows": len(rows),
        "primary_decision": overall.to_dict(),
        "h2_restricted_decision": {
            "note": (
                "Restricted to tasks the repair did not move. This is the contrast that "
                "speaks to the representation. Its n is smaller and its verdict is not "
                "interchangeable with the primary one."
            ),
            **h2_only.to_dict(),
        },
        "aggregate": agg.to_dict(),
        "standing": DEVELOPMENTAL_STANDING,
        "measured": True,
    }


def _pct(x: float | None) -> str:
    return "--" if x is None else f"{100.0 * x:.1f}%"


def render_text(report: dict[str, Any]) -> str:
    """Human-readable rendering. Refuses to render a verdict without its standing."""
    if "standing" not in report or not str(report["standing"]).strip():
        raise MissingStanding(
            "a report was rendered without its standing. The standing is what stops a "
            "24-task developmental signal being quoted as a demonstration."
        )

    out: list[str] = []
    out.append("=" * 78)
    out.append(f"{report['study']}  ({report['corpus_version']})")
    out.append("=" * 78)

    if not report.get("measured", False):
        t = report["tasks"]
        out.append("")
        out.append(f"DESIGN ONLY -- no model has been run. {t['n']} tasks.")
        out.append("")
        out.append("Domains:")
        for d, n in t["domains"].items():
            out.append(f"  {d:26s} {n}")
        out.append("")
        out.append(
            f"Predicted base accuracy: {t['difficulty_status']}, "
            f"target band {t['target_band'][0]:.2f}-{t['target_band'][1]:.2f}"
        )
        c = report["contamination"]
        out.append(
            f"Contamination: {'CLEAN' if c['clean'] else 'FAILED'} against "
            f"{c['n_foreign_corpora']} corpora, {len(c['hard_collisions'])} hard "
            f"collisions, {len(c['flagged_near_duplicates'])} flagged for review"
        )
        out.append("")
        out.append("Matching:")
        for m in report["matching"]:
            mark = "matched    " if m["matched"] else "NOT MATCHED"
            out.append(f"  [{mark}] {m['dimension']}")
            out.append(f"                {m['detail']}")
    else:
        d = report["primary_decision"]
        c = d["counts"]
        a = report["aggregate"]
        out.append("")
        out.append("ANSWER ACCURACY (the paired contrast)")
        out.append(f"  SE       {_pct(c['se_accuracy'])}   ({c['se_accuracy']})")
        out.append(f"  HML-V1   {_pct(c['hml_accuracy'])}   ({c['hml_accuracy']})")
        out.append(f"  uplift   {c['uplift_points']:+.2f} percentage points")
        out.append(
            f"  discordant pairs: w={c['w_hml_only']} l={c['l_se_only']} "
            f"(both={c['both']}, neither={c['neither']}, n={c['n']})"
        )
        out.append(f"  P(theta > 0.5 | D) = {d['posterior_p_theta_gt_half']}  ({d['posterior_exact']})")
        out.append(f"  VERDICT: {d['verdict']}")
        out.append(f"  a change of {d['flips_to_change_verdict']} task outcome(s) would change this verdict")
        out.append("")
        out.append("VERIFIED COMPLETION (a different claim, a different denominator)")
        v = a["verified_completion"]
        out.append(f"  HML-V1 modules that compiled: {v['verified']}/{v['denominator']}  ({_pct(v['rate'])})")
        out.append("  SE: not applicable -- no checkable artefact, so no uplift is computed.")
        out.append("")
        out.append("H3 -- VERIFIER-GUIDED REPAIR (not evidence about the representation)")
        h3 = a["h3_repair"]
        out.append(
            f"  repair moved the answer on {h3['moved']} trial(s): "
            f"{h3['moved_to_correct']} to correct, {h3['moved_to_incorrect']} to incorrect"
        )
        h2 = report["h2_restricted_decision"]
        out.append(
            f"  H2-restricted verdict (repair-untouched tasks only, n={h2['counts']['n']}): "
            f"{h2['verdict']}, P={h2['posterior_p_theta_gt_half']}"
        )
        out.append("")
        out.append("ERRORS")
        out.append(f"  structural (lex/parse/absent): {a['errors']['structural']}")
        out.append(f"  semantic  (resolve/type/dim):  {a['errors']['semantic']}")

    out.append("")
    out.append("-" * 78)
    out.append("STANDING")
    out.append(report["standing"])
    out.append("-" * 78)
    return "\n".join(out)


def to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True, default=str)
