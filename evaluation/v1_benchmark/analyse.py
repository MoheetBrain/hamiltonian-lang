"""Paired analysis and the mechanical project decision.

Everything here is computed **from the raw records on disk**, never from a value carried in
memory from the run. That is deliberate: it means the analysis can be re-run against the
committed records by anyone, and that a number in the report which cannot be rebuilt from
the records is a bug rather than a matter of trust.

No judgement call is made at analysis time. The decision rules were fixed before the run
and are transcribed here as arithmetic; :func:`decide` returns one of four verdicts and has
no branch that returns "inconclusive".
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "load_records",
    "PairedTable",
    "mcnemar_exact",
    "bootstrap_ci",
    "decide",
    "analyse",
]

#: A domain counts as a catastrophic failure for an arm when the arm scores zero on it
#: while the other arm scores at least this many. Fixed before the run.
CATASTROPHIC_MIN_OTHER = 2
CATASTROPHIC_MIN_TASKS = 2

#: Cost ceiling used by the kill rules: "costs more than twice SE".
COST_RATIO_LIMIT = 2.0

#: HML must produce a valid final state on more than this fraction of tasks.
MAX_INVALID_FINAL_STATE_RATE = 0.10


def load_records(records_dir: Path) -> list[dict[str, Any]]:
    """Every record, in frozen task order, read from disk."""
    out = []
    for p in sorted(records_dir.glob("*.json")):
        out.append(json.loads(p.read_text()))
    return out


# ---------------------------------------------------------------------------
# The paired table
# ---------------------------------------------------------------------------


@dataclass
class PairedTable:
    """The 2x2 contingency of final-answer correctness, plus the per-task rows."""

    both_correct: int = 0
    se_only: int = 0  # SE correct, HML wrong  -> "c"
    hml_only: int = 0  # HML correct, SE wrong -> "b"
    both_wrong: int = 0
    rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def n(self) -> int:
        return self.both_correct + self.se_only + self.hml_only + self.both_wrong

    @property
    def se_correct(self) -> int:
        return self.both_correct + self.se_only

    @property
    def hml_correct(self) -> int:
        return self.both_correct + self.hml_only

    @property
    def difference(self) -> int:
        """Absolute paired difference, HML minus SE."""
        return self.hml_correct - self.se_correct

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "se_correct": self.se_correct,
            "hml_correct": self.hml_correct,
            "paired_difference_hml_minus_se": self.difference,
            "both_correct": self.both_correct,
            "hml_correct_se_wrong_b": self.hml_only,
            "se_correct_hml_wrong_c": self.se_only,
            "both_wrong": self.both_wrong,
            "discordant": self.hml_only + self.se_only,
        }


def build_paired_table(records: list[dict[str, Any]], order: list[str]) -> PairedTable:
    se = {r["task_id"]: r for r in records if r["arm"] == "SE"}
    hml = {r["task_id"]: r for r in records if r["arm"] == "HML-V1"}
    t = PairedTable()
    for tid in order:
        if tid not in se or tid not in hml:
            continue
        s, h = se[tid], hml[tid]
        sc, hc = bool(s["answer_correct"]), bool(h["answer_correct"])
        if sc and hc:
            t.both_correct += 1
        elif hc and not sc:
            t.hml_only += 1
        elif sc and not hc:
            t.se_only += 1
        else:
            t.both_wrong += 1
        t.rows.append(
            {
                "task_id": tid,
                "domain": s["domain"],
                "se_correct": sc,
                "hml_correct": hc,
                "classification": (
                    "both_correct"
                    if sc and hc
                    else "hml_only"
                    if hc
                    else "se_only"
                    if sc
                    else "both_wrong"
                ),
                "se_first_correct": bool(s["first_attempt_correct"]),
                "hml_first_correct": bool(h["first_attempt_correct"]),
                "se_changed": bool(s["second_call_changed_answer"]),
                "hml_changed": bool(h["second_call_changed_answer"]),
                "hml_verified": h.get("verified_completion"),
                "se_answer": s["normalised_answer"],
                "hml_answer": h["normalised_answer"],
                "se_completion_tokens": s["completion_tokens"],
                "hml_completion_tokens": h["completion_tokens"],
                "se_latency_s": s["latency_s"],
                "hml_latency_s": h["latency_s"],
            }
        )
    return t


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def mcnemar_exact(b: int, c: int) -> dict[str, Any]:
    """Two-sided exact McNemar, conditioning on the discordant pairs.

    Under the null the b discordant pairs favouring HML are Binomial(b+c, 0.5). The exact
    test is used rather than the chi-square approximation because with 24 tasks the
    discordant count is small enough that the approximation is not trustworthy — which is
    exactly the regime where a borderline verdict would be decided by the choice of test.
    """
    n = b + c
    if n == 0:
        return {
            "b_hml_only": b,
            "c_se_only": c,
            "n_discordant": 0,
            "p_value": 1.0,
            "note": "no discordant pairs; the arms agreed on every task",
        }
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5**n)
    p = min(1.0, 2 * tail)
    return {
        "b_hml_only": b,
        "c_se_only": c,
        "n_discordant": n,
        "p_value": round(p, 6),
        "test": "exact McNemar (two-sided binomial on discordant pairs)",
    }


def bootstrap_ci(
    rows: list[dict[str, Any]], *, iterations: int = 20000, seed: int = 0
) -> dict[str, Any]:
    """Paired bootstrap over tasks for the accuracy difference.

    Resamples **tasks**, not trials, keeping each task's SE and HML outcomes together. That
    is what makes it a paired interval: the pairing is the design, and a bootstrap that
    broke it would report an interval for an experiment nobody ran.
    """
    if not rows:
        return {"note": "no rows"}
    rng = random.Random(seed)
    n = len(rows)
    diffs = []
    for _ in range(iterations):
        sample = [rows[rng.randrange(n)] for _ in range(n)]
        se = sum(1 for r in sample if r["se_correct"])
        hml = sum(1 for r in sample if r["hml_correct"])
        diffs.append((hml - se) / n)
    diffs.sort()
    lo = diffs[int(0.025 * iterations)]
    hi = diffs[int(0.975 * iterations) - 1]
    point = (
        sum(1 for r in rows if r["hml_correct"]) - sum(1 for r in rows if r["se_correct"])
    ) / n
    return {
        "point_estimate_accuracy_difference": round(point, 4),
        "ci_95_low": round(lo, 4),
        "ci_95_high": round(hi, 4),
        "iterations": iterations,
        "seed": seed,
        "unit_resampled": "task (SE and HML outcomes kept together)",
    }


def domain_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    doms: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = doms.setdefault(
            r["domain"], {"domain": r["domain"], "n": 0, "se_correct": 0, "hml_correct": 0}
        )
        d["n"] += 1
        d["se_correct"] += int(r["se_correct"])
        d["hml_correct"] += int(r["hml_correct"])
    out = []
    for d in doms.values():
        d["difference"] = d["hml_correct"] - d["se_correct"]
        d["hml_catastrophic"] = bool(
            d["n"] >= CATASTROPHIC_MIN_TASKS
            and d["hml_correct"] == 0
            and d["se_correct"] >= CATASTROPHIC_MIN_OTHER
        )
        d["se_catastrophic"] = bool(
            d["n"] >= CATASTROPHIC_MIN_TASKS
            and d["se_correct"] == 0
            and d["hml_correct"] >= CATASTROPHIC_MIN_OTHER
        )
        out.append(d)
    return sorted(out, key=lambda x: x["domain"])


# ---------------------------------------------------------------------------
# Secondary endpoints
# ---------------------------------------------------------------------------


def secondary(records: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    se = [r for r in records if r["arm"] == "SE"]
    hml = [r for r in records if r["arm"] == "HML-V1"]

    def repair_stats(arm_records: list[dict[str, Any]]) -> dict[str, Any]:
        wrong_first = [r for r in arm_records if not r["first_attempt_correct"]]
        fixed = [r for r in wrong_first if r["answer_correct"]]
        right_first = [r for r in arm_records if r["first_attempt_correct"]]
        broken = [r for r in right_first if not r["answer_correct"]]
        return {
            "initially_wrong": len(wrong_first),
            "repaired_to_correct": len(fixed),
            "repair_rate": round(len(fixed) / len(wrong_first), 4) if wrong_first else None,
            "initially_correct": len(right_first),
            "broken_by_second_call": len(broken),
            "second_call_changed_answer": sum(
                1 for r in arm_records if r["second_call_changed_answer"]
            ),
        }

    # HML structured-error classes, first call vs final call.
    struct_initial = sum(
        r["hml"]["initial_verdict"]["structural_errors"] for r in hml if r.get("hml")
    )
    sem_initial = sum(
        r["hml"]["initial_verdict"]["semantic_errors"] for r in hml if r.get("hml")
    )
    struct_final = sum(r["hml"]["structural_errors"] for r in hml if r.get("hml"))
    sem_final = sum(r["hml"]["semantic_errors"] for r in hml if r.get("hml"))

    def reduction(a: int, b: int) -> float | None:
        return round((a - b) / a, 4) if a else None

    verified = sum(1 for r in hml if r.get("verified_completion") is True)
    invalid_final = sum(
        1 for r in hml if not (r.get("hml") or {}).get("repaired_module_emitted", False)
    )

    def tok(rs: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "prompt_tokens": sum(r["prompt_tokens"] for r in rs),
            "completion_tokens": sum(r["completion_tokens"] for r in rs),
            "latency_s": round(sum(r["latency_s"] for r in rs), 2),
        }

    se_tok, hml_tok = tok(se), tok(hml)
    se_total = se_tok["prompt_tokens"] + se_tok["completion_tokens"]
    hml_total = hml_tok["prompt_tokens"] + hml_tok["completion_tokens"]

    # Scoring-failure modes, per arm. Under v1.3 a wrong answer and a MISSING answer are
    # different events, and conflating them is how a formatting failure gets reported as a
    # reasoning failure. Counted per arm so any asymmetry is visible to the reviewers.
    def scoring_reasons(arm_records: list[dict[str, Any]]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        tasks_by_reason: dict[str, list[str]] = {}
        for r in arm_records:
            reason = (r["calls"][-1].get("scoring") or {}).get("reason", "unrecorded")
            counts[reason] = counts.get(reason, 0) + 1
            tasks_by_reason.setdefault(reason, []).append(r["task_id"])
        return {"counts": counts, "tasks": tasks_by_reason}

    def revised_within_reply(arm_records: list[dict[str, Any]]) -> list[str]:
        """Tasks where the model emitted more than one answer span in its final reply.

        Under the frozen scorer these were scored on the FIRST span. The count is reported
        so the size of that repaired defect is visible rather than asserted.
        """
        return [
            r["task_id"]
            for r in arm_records
            if ((r["calls"][-1].get("scoring") or {}).get("marker_count") or 0) > 1
        ]

    return {
        "verified_completion": {
            "verified": verified,
            "denominator": len(hml),
            "rate": round(verified / len(hml), 4) if hml else None,
            "note": (
                "HML arm only. The SE arm emits no checkable artefact, so no uplift ratio "
                "against SE is computed or computable."
            ),
        },
        "first_call_correctness": {
            "se": sum(1 for r in se if r["first_attempt_correct"]),
            "hml": sum(1 for r in hml if r["first_attempt_correct"]),
        },
        "second_call": {"se": repair_stats(se), "hml": repair_stats(hml)},
        "hml_structured_errors": {
            "structural_initial": struct_initial,
            "structural_final": struct_final,
            "structural_reduction": reduction(struct_initial, struct_final),
            "semantic_initial": sem_initial,
            "semantic_final": sem_final,
            "semantic_reduction": reduction(sem_initial, sem_final),
            "combined_initial": struct_initial + sem_initial,
            "combined_final": struct_final + sem_final,
            "combined_reduction": reduction(
                struct_initial + sem_initial, struct_final + sem_final
            ),
            "note": (
                "Within-arm, first call versus final call. The SE arm has no structured-error "
                "counts at all -- it emits prose -- so a cross-arm reduction is undefined and "
                "this is the only computable reading of the rule."
            ),
        },
        "hml_final_state": {
            "no_valid_final_module": invalid_final,
            "rate": round(invalid_final / len(hml), 4) if hml else None,
            "limit": MAX_INVALID_FINAL_STATE_RATE,
        },
        "cost": {
            "se": se_tok,
            "hml": hml_tok,
            "total_tokens_se": se_total,
            "total_tokens_hml": hml_total,
            "token_ratio_hml_over_se": round(hml_total / se_total, 4) if se_total else None,
            "completion_ratio_hml_over_se": (
                round(hml_tok["completion_tokens"] / se_tok["completion_tokens"], 4)
                if se_tok["completion_tokens"]
                else None
            ),
            "latency_ratio_hml_over_se": (
                round(hml_tok["latency_s"] / se_tok["latency_s"], 4)
                if se_tok["latency_s"]
                else None
            ),
        },
        "scoring_reasons": {
            "se": scoring_reasons(se),
            "hml": scoring_reasons(hml),
            "note": (
                "Under v1.3 'no_answer_marker' and 'unparseable_numeric' are FORMATTING "
                "failures, distinct from 'numeric_mismatch' which is a reasoning failure. "
                "An asymmetry here between the arms is a confound, not a result."
            ),
        },
        "revised_answer_within_final_reply": {
            "se": revised_within_reply(se),
            "hml": revised_within_reply(hml),
            "note": (
                "Replies containing more than one answer span. The frozen scorer would have "
                "scored these on the FIRST span; v1.3 scores the last. The count measures "
                "how much defect D1 was actually worth on this run."
            ),
        },
    }


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------


def decide(
    table: PairedTable, sec: dict[str, Any], domains: list[dict[str, Any]]
) -> dict[str, Any]:
    """The frozen rules, transcribed as arithmetic. No branch returns 'inconclusive'."""
    diff = table.difference
    verified = sec["verified_completion"]["verified"]
    lost = table.se_only  # final correct answers SE has that HML does not
    combined_reduction = sec["hml_structured_errors"]["combined_reduction"]
    cost_ratio = sec["cost"]["token_ratio_hml_over_se"] or 0.0
    invalid_rate = sec["hml_final_state"]["rate"] or 0.0
    hml_catastrophic = [d["domain"] for d in domains if d["hml_catastrophic"]]

    se_repaired = sec["second_call"]["se"]["repaired_to_correct"]
    hml_repaired = sec["second_call"]["hml"]["repaired_to_correct"]
    se_broken = sec["second_call"]["se"]["broken_by_second_call"]
    hml_broken = sec["second_call"]["hml"]["broken_by_second_call"]

    # -- continuation conditions ----------------------------------------
    c1 = diff >= 3 and not hml_catastrophic
    # Verified solutions have no SE counterpart, so "4 more verified solutions" is read
    # against the only available baseline: HML's own count, which SE cannot have at all.
    c2 = (
        verified >= 4
        and lost <= 1
        and combined_reduction is not None
        and combined_reduction >= 0.30
    )
    # The strict `>` is load-bearing and is not redundant with the 1.5x factor. Without it,
    # `0 >= 1.5 * 0` holds and the condition fires when NEITHER arm repaired anything --
    # "HML corrects 50% more" would be satisfied by nothing happening at all. A test caught
    # this before any data existed. When SE repairs nothing and HML repairs something, the
    # ratio is unbounded and the condition is genuinely met, which `>` preserves.
    c3 = (
        hml_repaired > se_repaired
        and hml_repaired >= 1.5 * se_repaired
        and hml_broken <= se_broken + 1
        and cost_ratio <= COST_RATIO_LIMIT
    )

    conditions = {
        "c1_three_more_correct_no_catastrophe": {
            "met": bool(c1),
            "detail": f"paired difference {diff:+d} (need >= +3); "
            f"catastrophic HML domains: {hml_catastrophic or 'none'}",
        },
        "c2_four_more_verified_lose_at_most_one_reduce_errors_30pct": {
            "met": bool(c2),
            "detail": f"verified {verified} (need >= 4); final correct answers lost to SE "
            f"{lost} (need <= 1); structured-error reduction {combined_reduction} "
            f"(need >= 0.30)",
        },
        "c3_fifty_pct_more_repairs_no_new_errors_cost_within_2x": {
            "met": bool(c3),
            "detail": f"HML repaired {hml_repaired} vs SE {se_repaired} (need >= 1.5x); "
            f"HML broke {hml_broken} vs SE {se_broken} (need <= SE+1); "
            f"cost ratio {cost_ratio} (need <= {COST_RATIO_LIMIT})",
        },
    }

    # -- kill conditions -------------------------------------------------
    k1 = diff <= 0 and verified < 3
    k2 = cost_ratio > COST_RATIO_LIMIT and diff < 3
    k3 = invalid_rate > MAX_INVALID_FINAL_STATE_RATE
    k4 = bool(hml_catastrophic)

    kills = {
        "k1_no_more_accurate_and_under_3_verified": {
            "met": bool(k1),
            "detail": f"difference {diff:+d}, verified {verified}",
        },
        "k2_over_2x_cost_under_3_more_correct": {
            "met": bool(k2),
            "detail": f"cost ratio {cost_ratio}, difference {diff:+d}",
        },
        "k3_invalid_final_state_over_10pct": {
            "met": bool(k3),
            "detail": f"no valid final module on {invalid_rate:.1%} of tasks "
            f"(limit {MAX_INVALID_FINAL_STATE_RATE:.0%})",
        },
        "k4_catastrophic_domain_failure": {
            "met": bool(k4),
            "detail": f"domains: {hml_catastrophic or 'none'}",
        },
    }

    any_continue = c1 or c2 or c3
    verdict = "HML_CONTINUE_SIGNAL" if any_continue else "HML_KILL_SIGNAL"

    return {
        "verdict": verdict,
        "continuation_conditions": conditions,
        "kill_conditions": kills,
        "any_continuation_condition_met": bool(any_continue),
        "any_kill_condition_met": bool(k1 or k2 or k3 or k4),
        "rule": (
            "CONTINUE if any continuation condition holds; otherwise KILL. This is a "
            "project-investment decision on a valid paired measurement, not universal "
            "scientific proof, and it never returns 'inconclusive'."
        ),
    }


def analyse(run_root: Path) -> dict[str, Any]:
    manifest = json.loads((run_root / "MANIFEST.json").read_text())
    records = load_records(run_root / "records")
    order = manifest["frozen_task_order"]

    table = build_paired_table(records, order)
    sec = secondary(records, table.rows)
    domains = domain_table(table.rows)
    stats = mcnemar_exact(table.hml_only, table.se_only)
    ci = bootstrap_ci(table.rows)
    decision = decide(table, sec, domains)

    return {
        "run_id": manifest["run_id"],
        "protocol": manifest["protocol"],
        "model": manifest["model"],
        "model_digest": manifest["model_digest_pinned"],
        "per_call_completion_allowance": manifest["per_call_completion_allowance"],
        "runtime": manifest["runtime_measured"],
        "n_records": len(records),
        "paired_table": table.to_dict(),
        "mcnemar": stats,
        "bootstrap": ci,
        "domains": domains,
        "secondary": sec,
        "per_task": table.rows,
        "decision": decision,
    }
