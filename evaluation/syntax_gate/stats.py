"""Statistics and the Gate 2 verdict. Standard library only.

The no-dependency constraint is inherited, not invented here: ``evaluation/analyse.py``
implements the percentile bootstrap, exact McNemar and Cohen's h in twenty lines each
precisely so the project core stays dependency-free. This module **imports those** rather
than reimplementing them, so a change to the estimator changes both studies at once.

Three commitments carried forward from ``evaluation/analyse.py``
---------------------------------------------------------------
* **Paired analysis only over cells both conditions completed.** Ragged coverage from a
  truncated run would otherwise compare different task sets and call it a difference
  between syntaxes.
* **Unrun is reported as unrun**, never as zero and never omitted. Every proportion here
  carries its exact numerator, its exact denominator, and the count excluded as
  ``NOT MEASURED`` with the reasons.
* **Parser acceptance is never presented as evidence of a language advantage.** Gate 2
  is a *feasibility* gate: it decides whether a surface is writable enough to be tested
  at all. It is not, and must never be reported as, a result about reasoning.

Track B cannot move this gate
-----------------------------
``gate_verdict`` filters to ``partition.TRACK_A_GATE_IDS`` — the 80 G4 confirmatory
Track A tasks — before it counts anything, and reports how many rows it dropped.
``tests/evaluation/test_syntax_gate_partition.py`` proves the exclusion by differential
test: the verdict is bit-identical with and without arbitrary Track B trials appended,
including a Track B block engineered to fail every facet.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from evaluation.analyse import Interval, bootstrap_mean, cohens_h, mcnemar_exact, paired_diff
from evaluation.v1.score_v1 import NotMeasured

from . import SYNTAX_GATE_VERSION
from .candidates import CANDIDATE_IDS, SE_CONTROL
from .partition import TRACK_A_GATE_IDS
from .scorer import ScoredTrial

__all__ = [
    "GATE_THRESHOLDS",
    "GATE_FACETS",
    "Proportion",
    "proportion",
    "acq0_metrics",
    "gate_verdict",
    "condition_summary",
    "pairwise_contrasts",
    "token_cost_ratio",
    "bootstrap_mean",
    "paired_diff",
    "mcnemar_exact",
    "cohens_h",
]

#: Fixed before any result is seen, per the preregistration §8: thresholds may not be
#: lowered after seeing results.
GATE_THRESHOLDS = {
    "repaired_parse_min": 0.95,
    "semantic_preservation_min": 0.90,
    "domain_repaired_parse_floor": 0.70,
    "max_completion_token_ratio_vs_structured_english": 2.0,
}

#: The facets the gate reads. Concept admission is deliberately **absent**: it is a
#: Track B measurement, it is known to fail, and it must not influence the gate at all.
#: A test asserts no concept-admission facet appears here.
GATE_FACETS = frozenset(
    {"repaired_parse", "preserved", "completion_tokens_reasoning_inclusive"}
)


@dataclass(frozen=True)
class Proportion:
    """A rate with its exact numerator, denominator and excluded count.

    A bare float hides whether 0.95 came from 19/20 or 950/1000, and hides whether the
    other 400 rows were failures or were never measured. Both matter to the gate.
    """

    numerator: int
    denominator: int
    not_measured: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    @property
    def value(self) -> float | None:
        return (self.numerator / self.denominator) if self.denominator else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "rate": (round(self.value, 6) if self.value is not None else None),
            "not_measured": self.not_measured,
            "not_measured_reasons": dict(sorted(self.reasons.items())),
            "note": (
                None
                if self.denominator
                else "NOT MEASURED: no row contributed a denominator"
            ),
        }


def _reason_of(x: Any) -> str:
    return x.reason if isinstance(x, NotMeasured) else "not measured"


def proportion(rows: list[ScoredTrial], field_name: str) -> Proportion:
    """Count a boolean facet, excluding NotMeasured rows and recording why."""
    num = den = nm = 0
    reasons: dict[str, int] = defaultdict(int)
    for r in rows:
        v = getattr(r, field_name)
        if isinstance(v, NotMeasured):
            nm += 1
            reasons[v.reason[:120]] += 1
            continue
        den += 1
        if v:
            num += 1
    return Proportion(num, den, nm, dict(reasons))


def _numeric(rows: list[ScoredTrial], field_name: str) -> list[float]:
    out = []
    for r in rows:
        v = getattr(r, field_name)
        if not isinstance(v, NotMeasured) and v is not None:
            out.append(float(v))
    return out


def _gate_rows(scored: list[ScoredTrial]) -> tuple[list[ScoredTrial], dict[str, int]]:
    """Filter to the official gate set. **The only entry point Track B could take.**"""
    kept = [s for s in scored if s.task_id in TRACK_A_GATE_IDS]
    dropped: dict[str, int] = defaultdict(int)
    for s in scored:
        if s.task_id not in TRACK_A_GATE_IDS:
            dropped["not_in_G4_confirmatory_track_a"] += 1
    return kept, dict(dropped)


def condition_summary(scored: list[ScoredTrial], condition: str) -> dict[str, Any]:
    """Every measured facet for one condition, with exact numerators and denominators."""
    rows = [s for s in scored if s.condition == condition]
    tokens = _numeric(rows, "completion_tokens_reasoning_inclusive")
    latency = _numeric(rows, "latency_s")
    lengths = _numeric(rows, "visible_output_length")
    categories: dict[str, int] = defaultdict(int)
    for r in rows:
        categories[r.failure_category] += 1
    return {
        "condition": condition,
        "trials": len(rows),
        "first_attempt_parse": proportion(rows, "first_attempt_parse").to_dict(),
        # The whole-pipeline verdict, under its own name. It is NOT the parse rate; see
        # scorer.py's module docstring for why the two were conflated and what it cost.
        "first_attempt_compiled": proportion(rows, "first_attempt_compiled").to_dict(),
        "repaired_parse": proportion(rows, "repaired_parse").to_dict(),
        "semantic_preservation": proportion(rows, "preserved").to_dict(),
        "exact_canonical_match": proportion(rows, "exact_canonical_match").to_dict(),
        "answer_correct": proportion(rows, "answer_correct").to_dict(),
        "empty_or_truncated": proportion(rows, "empty_or_truncated").to_dict(),
        "completion_tokens_reasoning_inclusive": _interval(tokens),
        "latency_s": _interval(latency),
        "visible_output_length": _interval(lengths),
        "failure_categories": dict(sorted(categories.items())),
    }


def _interval(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "NOT MEASURED": True,
            "reason": "no row carried a measured value",
            "denominator": "0 rows",
        }
    iv: Interval = bootstrap_mean(values)
    return {
        "mean": round(iv.point, 4),
        "ci95": [round(iv.lo, 4), round(iv.hi, 4)],
        "n": iv.n,
        "sum": round(sum(values), 4),
    }


def _paired(
    scored: list[ScoredTrial], a: str, b: str, field_name: str
) -> tuple[list[float], list[float], list[str]]:
    """Vectors over task ids **both** conditions measured. Ragged coverage is excluded."""
    idx: dict[tuple[str, str], ScoredTrial] = {(s.condition, s.task_id): s for s in scored}
    ids = sorted(
        {s.task_id for s in scored if s.condition == a}
        & {s.task_id for s in scored if s.condition == b}
    )
    va, vb, used = [], [], []
    for tid in ids:
        ra, rb = idx[(a, tid)], idx[(b, tid)]
        xa, xb = getattr(ra, field_name), getattr(rb, field_name)
        if isinstance(xa, NotMeasured) or isinstance(xb, NotMeasured):
            continue
        va.append(float(xa))
        vb.append(float(xb))
        used.append(tid)
    return va, vb, used


def pairwise_contrasts(
    scored: list[ScoredTrial], field_name: str = "repaired_parse"
) -> list[dict[str, Any]]:
    """Every candidate against every other, paired, with McNemar and Cohen's h."""
    out = []
    conditions = list(CANDIDATE_IDS) + [SE_CONTROL]
    for i, a in enumerate(conditions):
        for b in conditions[i + 1 :]:
            va, vb, used = _paired(scored, a, b, field_name)
            if not used:
                out.append({
                    "treatment": a, "control": b, "field": field_name,
                    "NOT MEASURED": True,
                    "reason": "no task id was measured in both conditions",
                })
                continue
            disc_b = sum(1 for x, y in zip(va, vb, strict=True) if x > y)
            disc_c = sum(1 for x, y in zip(va, vb, strict=True) if x < y)
            pa = sum(va) / len(va)
            pb = sum(vb) / len(vb)
            diff = paired_diff(va, vb)
            h = cohens_h(pa, pb)
            out.append({
                "treatment": a,
                "control": b,
                "field": field_name,
                "n_pairs": len(used),
                "treatment_rate": {"numerator": int(sum(va)), "denominator": len(va)},
                "control_rate": {"numerator": int(sum(vb)), "denominator": len(vb)},
                "paired_difference": {
                    "point": round(diff.point, 6),
                    "ci95": [round(diff.lo, 6), round(diff.hi, 6)],
                    "n": diff.n,
                },
                "discordant_treatment_better": disc_b,
                "discordant_control_better": disc_c,
                "mcnemar_exact_p": round(mcnemar_exact(disc_b, disc_c), 6),
                "cohens_h": round(h, 4),
            })
    return out


def token_cost_ratio(scored: list[ScoredTrial], condition: str) -> dict[str, Any]:
    """Reasoning-inclusive completion-token cost relative to structured English.

    Paired over the task ids both arms completed, and reported as an explicit ratio of
    two sums so the numerator and denominator are visible. Ollama bills the reasoning
    channel to ``completion_tokens``; the facet is reasoning-inclusive by construction.
    """
    va, vb, used = _paired(
        scored, condition, SE_CONTROL, "completion_tokens_reasoning_inclusive"
    )
    if not used:
        return {
            "condition": condition,
            "NOT MEASURED": True,
            "reason": (
                "no task id carried a measured completion-token count in both this "
                "condition and the structured-English control"
            ),
            "denominator": "0 paired tasks",
            "required_field": "a matched SE_structured_english arm on the same tasks",
        }
    num, den = sum(va), sum(vb)
    diff = paired_diff(va, vb)
    return {
        "condition": condition,
        "n_pairs": len(used),
        "condition_completion_tokens_total": int(num),
        "structured_english_completion_tokens_total": int(den),
        "ratio": (round(num / den, 4) if den else None),
        "paired_mean_difference": {
            "point": round(diff.point, 3),
            "ci95": [round(diff.lo, 3), round(diff.hi, 3)],
            "n": diff.n,
        },
        "threshold": GATE_THRESHOLDS["max_completion_token_ratio_vs_structured_english"],
        "reasoning_inclusive": True,
    }


def acq0_metrics(scored: list[ScoredTrial], condition: str) -> dict[str, Any]:
    """ACQ0's three headline rates, each with its exact numerator and denominator.

    Defined here rather than assembled at a report site, because the definitions are the
    thing that was wrong:

    * ``first_attempt_parse_rate`` = ``count(parse_status = PASS) / total``. **Parse**,
      not compile. Wrong arity, wrong argument type, wrong role label and an epistemic
      mismatch all parse; classifying them as parse failures would understate this rate
      and blame the candidate surface for the type checker.
    * ``repaired_parse_rate`` = ``count(repair_parse_status = PASS) /
      repair_eligible_total``, where a trial is repair-eligible exactly when its first
      attempt did **not** parse. A trial that parsed first time was never a candidate for
      repair, and including it would dilute the repair loop's measured effect toward the
      first-attempt rate.
    * ``semantic_preservation_rate`` = ``count(exact expected canonical object recovered)
      / total`` — hash equality over the nameless canonical form.

    ``parse_rate_after_at_most_one_repair`` is reported alongside because it, not
    ``repaired_parse_rate``, is what the Gate 2 threshold is written against. The two are
    different quantities and are named differently so a report cannot quote one as the
    other.
    """
    rows = [s for s in scored if s.condition == condition]
    first = proportion(rows, "first_attempt_parse")
    combined = proportion(rows, "repaired_parse")
    preserved_exact = proportion(rows, "exact_canonical_match")

    # Repair-eligible: the first attempt was measured and did not parse.
    eligible = [
        s
        for s in rows
        if not isinstance(s.first_attempt_parse, NotMeasured)
        and s.first_attempt_parse is False
    ]
    repaired = proportion(eligible, "repaired_parse")

    terminals: dict[str, int] = defaultdict(int)
    for r in rows:
        terminals[r.terminal_outcome or "UNCLASSIFIED"] += 1

    return {
        "version": SYNTAX_GATE_VERSION,
        "condition": condition,
        "total_trials": len(rows),
        "first_attempt_parse_rate": {
            **first.to_dict(),
            "definition": "count(parse_status = PASS) / total",
        },
        "repaired_parse_rate": {
            **repaired.to_dict(),
            "definition": (
                "count(repair_parse_status = PASS) / repair_eligible_total, where "
                "repair-eligible means the first attempt was measured and did not parse"
            ),
            "repair_eligible_total": len(eligible),
        },
        "semantic_preservation_rate": {
            **preserved_exact.to_dict(),
            "definition": (
                "count(exact expected canonical object recovered) / total, by hash "
                "equality over the nameless canonical form"
            ),
        },
        "parse_rate_after_at_most_one_repair": {
            **combined.to_dict(),
            "definition": (
                "count(parse PASS after at most one repair) / total. This is the "
                "quantity GATE_THRESHOLDS['repaired_parse_min'] is written against, and "
                "it is NOT repaired_parse_rate above."
            ),
        },
        "terminal_outcomes": dict(sorted(terminals.items())),
        "interpretation": (
            "A parse rate counts parses. CompileResult.ok() is a whole-pipeline verdict "
            "and is reported separately as first_attempt_compiled; substituting it here "
            "would attribute type and scope defects to the candidate syntax."
        ),
    }


def gate_verdict(scored: list[ScoredTrial], condition: str) -> dict[str, Any]:
    """The Gate 2 verdict for one candidate, over the official gate set only.

    Every threshold is reported with its exact numerator and denominator, and every
    criterion that could not be evaluated is reported as NOT MEASURED with the reason —
    never as a pass and never as a zero.
    """
    if condition == SE_CONTROL:
        return {
            "condition": condition,
            "NOT APPLICABLE": True,
            "reason": (
                "the structured-English control is the denominator of the cost "
                "threshold, not a candidate; it cannot pass or fail the syntax gate"
            ),
        }

    gate_rows, dropped = _gate_rows(scored)
    rows = [s for s in gate_rows if s.condition == condition]

    repaired = proportion(rows, "repaired_parse")
    preserved = proportion(rows, "preserved")
    first = proportion(rows, "first_attempt_parse")

    by_domain: dict[str, list[ScoredTrial]] = defaultdict(list)
    for r in rows:
        by_domain[r.domain].append(r)
    domain_rates = {
        d: proportion(v, "repaired_parse").to_dict() for d, v in sorted(by_domain.items())
    }
    floor = GATE_THRESHOLDS["domain_repaired_parse_floor"]
    below = sorted(
        d for d, p in domain_rates.items()
        if p["rate"] is not None and p["rate"] < floor
    )
    unmeasured_domains = sorted(
        d for d, p in domain_rates.items() if p["rate"] is None
    )

    cost = token_cost_ratio(gate_rows, condition)

    def crit(name: str, p: Proportion, threshold: float) -> dict[str, Any]:
        if p.denominator == 0:
            return {
                "criterion": name, "NOT MEASURED": True,
                "reason": "no row contributed a denominator",
                "not_measured_rows": p.not_measured,
                "not_measured_reasons": dict(sorted(p.reasons.items())),
                "threshold": threshold, "passes": None,
            }
        return {
            "criterion": name, **p.to_dict(), "threshold": threshold,
            "passes": p.value is not None and p.value >= threshold,
        }

    c1 = crit("repaired_parse", repaired, GATE_THRESHOLDS["repaired_parse_min"])
    c2 = crit(
        "semantic_preservation", preserved, GATE_THRESHOLDS["semantic_preservation_min"]
    )
    if unmeasured_domains or not domain_rates:
        c3: dict[str, Any] = {
            "criterion": "no_domain_below_floor", "NOT MEASURED": True,
            "reason": f"domains with no measured denominator: {unmeasured_domains}",
            "threshold": floor, "passes": None, "per_domain": domain_rates,
        }
    else:
        c3 = {
            "criterion": "no_domain_below_floor", "threshold": floor,
            "domains_below_floor": below, "passes": not below,
            "per_domain": domain_rates,
        }
    if cost.get("NOT MEASURED"):
        c4: dict[str, Any] = {
            "criterion": "completion_token_cost_vs_structured_english",
            "NOT MEASURED": True, "reason": cost["reason"],
            "threshold": GATE_THRESHOLDS[
                "max_completion_token_ratio_vs_structured_english"
            ],
            "passes": None,
        }
    else:
        c4 = {
            "criterion": "completion_token_cost_vs_structured_english",
            **cost,
            "passes": cost["ratio"] is not None
            and cost["ratio"]
            <= GATE_THRESHOLDS["max_completion_token_ratio_vs_structured_english"],
        }

    criteria = [c1, c2, c3, c4]
    unmeasured = [c["criterion"] for c in criteria if c.get("passes") is None]
    failed = [c["criterion"] for c in criteria if c.get("passes") is False]
    if unmeasured:
        verdict = "NOT MEASURED"
    elif failed:
        verdict = "FAIL"
    else:
        verdict = "PASS"

    return {
        "version": SYNTAX_GATE_VERSION,
        "condition": condition,
        "gate_stage": "G4_confirmatory",
        "gate_task_pool_size": len(TRACK_A_GATE_IDS),
        "rows_considered": len(rows),
        "rows_dropped_before_counting": dropped,
        "first_attempt_parse": first.to_dict(),
        "criteria": criteria,
        "criteria_not_measured": unmeasured,
        "criteria_failed": failed,
        "verdict": verdict,
        "interpretation": (
            "Gate 2 is a feasibility gate: it decides whether a surface is writable "
            "enough to be tested at all. Passing it is not evidence of any reasoning "
            "advantage and must never be reported as one."
        ),
    }


def minimum_detectable_effect(n_pairs: int, alpha: float = 0.05) -> dict[str, Any]:
    """The smallest one-directional discordant count McNemar can call significant.

    Computed rather than asserted. The V0 pilot's dominating limitation was that at
    n = 15 with a 93% ceiling this corresponded to roughly 33 percentage points.
    """
    for k in range(1, n_pairs + 1):
        if mcnemar_exact(k, 0) <= alpha:
            return {
                "n_pairs": n_pairs,
                "alpha": alpha,
                "min_one_directional_discordant_pairs": k,
                "min_detectable_difference_pp": round(100 * k / n_pairs, 2),
                "NOTE": (
                    "assumes every discordant pair falls the same way, the most "
                    "favourable case; a realistic design needs more"
                ),
            }
    return {
        "n_pairs": n_pairs, "alpha": alpha,
        "min_one_directional_discordant_pairs": None,
        "NOTE": "no discordant count reaches significance at this n",
    }


def design_facts() -> dict[str, Any]:
    """Everything true about the gate before any model is run."""
    return {
        "version": SYNTAX_GATE_VERSION,
        "gate_stage": "G4_confirmatory",
        "gate_pool": len(TRACK_A_GATE_IDS),
        "thresholds": dict(GATE_THRESHOLDS),
        "gate_facets": sorted(GATE_FACETS),
        "minimum_detectable_effect": minimum_detectable_effect(len(TRACK_A_GATE_IDS)),
        "statistics": {
            "interval": "percentile bootstrap, 4000 iterations, seed 7",
            "paired_test": "exact McNemar (two-sided, binomial)",
            "effect_size": "Cohen's h",
            "dependencies": "standard library only",
            "source": "evaluation/analyse.py",
        },
        "sanity": {
            "cohens_h_zero_for_equal_proportions": math.isclose(
                cohens_h(0.5, 0.5), 0.0, abs_tol=1e-12
            ),
            "mcnemar_no_discordance_is_one": mcnemar_exact(0, 0) == 1.0,
        },
    }
