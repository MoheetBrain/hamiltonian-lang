"""Analysis for HML-EVAL-001 §10 — paired comparisons, intervals, effect sizes.

    .venv/bin/python -m evaluation.analyse --run eval001-pilot

Standard library only. Bootstrap intervals, McNemar's exact test and Cohen's h are
implemented here rather than pulled in, because the project core has no dependencies and
these are twenty lines each.

Three commitments that matter more than the arithmetic:

* **Paired analysis only over cells both arms completed.** A run truncated by a time
  budget leaves ragged coverage; silently averaging over whatever exists would compare
  different problem sets and call it a difference between arms.
* **Unrun is reported as unrun**, never as zero and never omitted.
* **Parser acceptance is never presented as evidence of a language advantage.** The
  directive forbids it and the report separates it from answer accuracy throughout.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "evaluation" / "results" / "runs"

ARM_ORDER = ["A", "A_prime", "B", "C", "D", "E", "F"]
ARM_LABEL = {
    "A": "ordinary English",
    "A_prime": "structured English (scaffolding control)",
    "B": "LaTeX",
    "C": "Stan / Lean (existing formal language)",
    "D": "Hamiltonian, no feedback",
    "E": "Hamiltonian + compiler feedback",
    "F": "Hamiltonian graph view",
}

#: The comparisons the directive asks for, as (treatment, control, what it tests).
KEY_CONTRASTS = [
    ("A_prime", "A", "does explicit scaffolding alone help?"),
    ("D", "A", "does Hamiltonian beat ordinary English?"),
    ("D", "A_prime", "does Hamiltonian beat structured English? (the decisive one)"),
    ("D", "B", "does Hamiltonian beat LaTeX?"),
    ("D", "C", "does Hamiltonian beat an existing formal language?"),
    ("E", "D", "does compiler feedback produce the gain?"),
    ("F", "D", "does the graph view differ from linear Hamiltonian?"),
]


@dataclass
class Interval:
    point: float
    lo: float
    hi: float
    n: int

    def render(self, pct: bool = True) -> str:
        f = 100 if pct else 1
        unit = "%" if pct else ""
        return f"{self.point*f:.1f}{unit} [{self.lo*f:.1f}, {self.hi*f:.1f}] (n={self.n})"


def bootstrap_mean(values: list[float], iters: int = 4000, seed: int = 7) -> Interval:
    """Percentile bootstrap. Reported rather than a normal approximation because the
    per-cell counts here are small and proportions are bounded."""
    if not values:
        return Interval(float("nan"), float("nan"), float("nan"), 0)
    rng = random.Random(seed)
    n = len(values)
    point = sum(values) / n
    if n == 1:
        return Interval(point, point, point, 1)
    means = []
    for _ in range(iters):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return Interval(point, means[int(0.025 * iters)], means[int(0.975 * iters) - 1], n)


def paired_diff(treat: list[float], ctrl: list[float], iters: int = 4000) -> Interval:
    """Bootstrap interval on the paired difference treat - ctrl."""
    assert len(treat) == len(ctrl)
    diffs = [t - c for t, c in zip(treat, ctrl, strict=True)]
    return bootstrap_mean(diffs, iters=iters)


def _binom_sf(k: int, n: int, p: float = 0.5) -> float:
    """P(X >= k) for X ~ Binomial(n, p). Exact, via math.comb."""
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value for paired binary outcomes.

    ``b`` = treatment right / control wrong; ``c`` = treatment wrong / control right.
    Concordant pairs carry no information about a difference and are excluded — which is
    exactly why a raw accuracy gap can look large while the paired test says nothing.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = max(b, c)
    return min(1.0, 2 * _binom_sf(k, n))


def cohens_h(p1: float, p2: float) -> float:
    """Effect size for a difference between two proportions."""
    p1 = min(max(p1, 0.0), 1.0)
    p2 = min(max(p2, 0.0), 1.0)
    return 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))


def effect_label(h: float) -> str:
    a = abs(h)
    if a < 0.2:
        return "negligible"
    if a < 0.5:
        return "small"
    if a < 0.8:
        return "medium"
    return "large"


# ---------------------------------------------------------------------------


def rescore(rows: list[dict]) -> list[dict]:
    """Recompute encoding scores from the stored raw encoding.

    Scores are computed at trial time for the live log, but the comparator is a piece of
    *analysis*, not of data collection. Re-deriving them here means a comparator fix does
    not require re-running the model, and it keeps the reported numbers consistent with
    the code in the repository rather than with whatever version happened to be loaded
    while the run was in flight. The raw model output is never modified.
    """
    from evaluation.corpus.generators import build_all
    from evaluation.semantic_equiv import compare_semantics

    corpus = {c.id: c for c in build_all()}
    for r in rows:
        if r["arm"] not in ("D", "E") or not r.get("encoding_text"):
            continue
        cso = corpus.get(r["problem_id"])
        if cso is None:
            continue
        cmp = compare_semantics(cso, r["encoding_text"])
        r["parse_success"] = cmp.parsed
        r["diagnostics"] = cmp.diagnostics
        r["semantic_score"] = cmp.score()
        r["semantic_exact"] = cmp.exact()
        r["semantic_detail"] = cmp.to_dict()
        r["_rescored"] = True
    return rows


def load(run_id: str) -> tuple[list[dict], dict]:
    path = RUNS / f"{run_id}.jsonl"
    if not path.exists():
        raise SystemExit(f"no such run: {path}")
    rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    meta_path = RUNS / f"{run_id}.meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return rescore(rows), meta


def coverage(rows: list[dict], meta: dict) -> dict:
    planned = meta.get("planned_calls", 0)
    arms = meta.get("arms", ARM_ORDER)
    gens = meta.get("generations", 0)
    problems = meta.get("problems", [])
    have = {(r["problem_id"], r["arm"], r["generation"]) for r in rows}
    per_arm = {a: sum(1 for r in rows if r["arm"] == a) for a in arms}
    complete_cells = [
        (p, g) for p in problems for g in range(gens)
        if all((p, a, g) in have for a in arms)
    ]
    return {
        "planned_calls": planned,
        "completed_calls": len(rows),
        "completion_fraction": round(len(rows) / planned, 4) if planned else None,
        "trials_per_arm": per_arm,
        "problems_planned": len(problems),
        "generations_planned": gens,
        "fully_covered_problem_generations": len(complete_cells),
        "fully_covered_detail": complete_cells,
        "UNRUN_CELLS": planned - len(rows) if planned else None,
    }


def _paired_vectors(rows: list[dict], a: str, b: str, field: str):
    """Values for arms a and b over (problem, generation) cells present in BOTH."""
    idx: dict[tuple[str, str, int], dict] = {
        (r["problem_id"], r["arm"], r["generation"]): r for r in rows
    }
    keys = sorted(
        {(p, g) for (p, arm, g) in idx if arm == a}
        & {(p, g) for (p, arm, g) in idx if arm == b}
    )
    va, vb, ids = [], [], []
    for p, g in keys:
        ra, rb = idx[(p, a, g)], idx[(p, b, g)]
        if ra.get(field) is None or rb.get(field) is None:
            continue
        va.append(float(ra[field]))
        vb.append(float(rb[field]))
        ids.append((p, g))
    return va, vb, ids


def arm_summary(rows: list[dict], arms: list[str]) -> dict:
    out: dict[str, dict] = {}
    for a in arms:
        rs = [r for r in rows if r["arm"] == a]
        if not rs:
            out[a] = {"trials": 0, "NOTE": "no trials completed for this arm"}
            continue
        acc = [1.0 if r["answer_correct"] else 0.0 for r in rs]
        parse = [r["parse_success"] for r in rs if r.get("parse_success") is not None]
        sem = [r["semantic_score"] for r in rs if r.get("semantic_score") is not None]
        tax: dict[str, int] = defaultdict(int)
        for r in rs:
            tax[r["failure_class"]] += 1
        out[a] = {
            "label": ARM_LABEL.get(a, a),
            "trials": len(rs),
            "answer_accuracy": bootstrap_mean(acc).__dict__,
            "parse_success_rate": (
                round(sum(1 for x in parse if x) / len(parse), 4) if parse else None
            ),
            "parse_n": len(parse),
            "semantic_encoding_score": (
                bootstrap_mean(sem).__dict__ if sem else None
            ),
            "encoding_produced_rate": round(
                sum(1 for r in rs if r["encoding_present"]) / len(rs), 4
            ),
            "answer_marker_compliance": round(
                sum(1 for r in rs if r["answer_marker_present"]) / len(rs), 4
            ),
            "mean_prompt_tokens": round(sum(r["prompt_tokens"] for r in rs) / len(rs), 1),
            "mean_completion_tokens": round(
                sum(r["completion_tokens"] for r in rs) / len(rs), 1
            ),
            "mean_latency_s": round(sum(r["latency_s"] for r in rs) / len(rs), 1),
            "total_repair_calls": sum(r["repair_calls"] for r in rs),
            "trials_with_repair": sum(1 for r in rs if r["repair_calls"] > 0),
            "empty_output_rate": round(
                sum(1 for r in rs if not (r["raw_output"] or "").strip()) / len(rs), 4
            ),
            "semantic_encoding_score_parsing_only": (
                bootstrap_mean(
                    [r["semantic_score"] for r in rs
                     if r.get("semantic_score") is not None and r.get("parse_success")]
                ).__dict__
                if any(r.get("parse_success") for r in rs) else None
            ),
            "binding_error_rate": round(
                sum(1 for r in rs
                    if any(d.startswith("HML-N") for d in (r.get("diagnostics") or [])))
                / len(rs), 4
            ),
            "scope_error_rate": round(
                sum(1 for r in rs if (r.get("semantic_detail") or {}).get(
                    "quantifier_order", [0, 0])[1] and
                    (r["semantic_detail"]["quantifier_order"][0]
                     < r["semantic_detail"]["quantifier_order"][1]))
                / len(rs), 4
            ),
            "type_error_rate": round(
                sum(1 for r in rs
                    if any(d.startswith(("HML-T", "HML-D"))
                           for d in (r.get("diagnostics") or []))) / len(rs), 4
            ),
            "failure_taxonomy": dict(sorted(tax.items(), key=lambda kv: -kv[1])),
        }
    return out


def semantic_contrasts(rows: list[dict]) -> list[dict]:
    """Paired encoding-score contrasts, defined only between arms that produce one."""
    out = []
    for treat, ctrl in [("E", "D")]:
        va, vb, _ = _paired_vectors(rows, treat, ctrl, "semantic_score")
        if not va:
            out.append({"treatment": treat, "control": ctrl, "n_pairs": 0,
                        "status": "NOT ESTIMABLE"})
            continue
        d = paired_diff(va, vb)
        out.append({
            "treatment": treat, "control": ctrl, "n_pairs": len(va),
            "treatment_mean": round(sum(va) / len(va), 4),
            "control_mean": round(sum(vb) / len(vb), 4),
            "paired_difference": {"point": round(d.point, 4),
                                  "ci95": [round(d.lo, 4), round(d.hi, 4)]},
            "ci_excludes_zero": (d.lo > 0) or (d.hi < 0),
        })
    return out


def contrasts(rows: list[dict]) -> list[dict]:
    out = []
    for treat, ctrl, question in KEY_CONTRASTS:
        va, vb, ids = _paired_vectors(rows, treat, ctrl, "answer_correct")
        if not va:
            out.append({
                "treatment": treat, "control": ctrl, "question": question,
                "status": "NOT ESTIMABLE — no problem-generation cell completed in both arms",
                "n_pairs": 0,
            })
            continue
        b = sum(1 for t, c in zip(va, vb, strict=True) if t > c)
        c_ = sum(1 for t, c in zip(va, vb, strict=True) if t < c)
        diff = paired_diff(va, vb)
        p1, p2 = sum(va) / len(va), sum(vb) / len(vb)
        h = cohens_h(p1, p2)
        out.append({
            "treatment": treat, "control": ctrl, "question": question,
            "n_pairs": len(va),
            "treatment_accuracy": round(p1, 4),
            "control_accuracy": round(p2, 4),
            "paired_difference": {"point": round(diff.point, 4),
                                  "ci95": [round(diff.lo, 4), round(diff.hi, 4)]},
            "discordant_pairs": {"treatment_only_correct": b, "control_only_correct": c_},
            "mcnemar_exact_p": round(mcnemar_exact(b, c_), 4),
            "cohens_h": round(h, 4),
            "effect_size": effect_label(h),
            "ci_excludes_zero": (diff.lo > 0) or (diff.hi < 0),
        })
    return out


def by_domain(rows: list[dict], arms: list[str]) -> dict:
    out: dict[str, dict] = {}
    domains = sorted({r["domain"] for r in rows})
    for d in domains:
        sub = [r for r in rows if r["domain"] == d]
        out[d] = {
            a: round(
                sum(1 for r in sub if r["arm"] == a and r["answer_correct"])
                / max(1, sum(1 for r in sub if r["arm"] == a)), 4
            )
            for a in arms if any(r["arm"] == a for r in sub)
        }
        out[d]["n_per_arm"] = {
            a: sum(1 for r in sub if r["arm"] == a) for a in arms
        }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="eval001-pilot")
    ap.add_argument("--out", default=None)
    ap.add_argument(
        "--generation", type=int, default=None,
        help="restrict to one generation; the pilot's primary analysis is generation 0",
    )
    args = ap.parse_args(argv)

    rows, meta = load(args.run)
    if args.generation is not None:
        rows = [r for r in rows if r["generation"] == args.generation]
        meta = dict(meta)
        meta["generations"] = 1
        meta["planned_calls"] = len(meta.get("problems", [])) * len(meta.get("arms", []))
        meta["analysed_generation"] = args.generation
        # Coverage counts cells at generation 0 after the filter, so re-key them.
        for r in rows:
            r["generation"] = 0
    arms = meta.get("arms", ARM_ORDER)
    cov = coverage(rows, meta)

    doc = {
        "HEADER": {
            "WHAT_THIS_IS": (
                "Model-in-the-loop measurement for HML-EVAL-001. Every number here is a "
                "genuine observation of model behaviour, not a compiler property."
            ),
            "SCORING": (
                "Answer correctness and encoding comparison are deterministic. No model "
                "judged any output at any point."
            ),
            "PARSER_ACCEPTANCE_WARNING": (
                "Parser acceptance is reported separately and is NOT evidence of a "
                "language advantage. A Hamiltonian program can parse cleanly and "
                "mistranslate the problem entirely."
            ),
            "RESCORED": (
                "Encoding scores are recomputed from the stored raw output using the "
                "comparator in this repository, not read from the live run log. Raw "
                "model output is never modified."
            ),
            "COVERAGE_WARNING": (
                "Paired contrasts use only problem-generation cells completed in BOTH "
                "arms. Unrun cells are reported as unrun and are never imputed."
            ),
        },
        "run_meta": meta,
        "coverage": cov,
        "arm_summary": arm_summary(rows, arms),
        "contrasts": contrasts(rows),
        "semantic_contrasts": semantic_contrasts(rows),
        "by_domain": by_domain(rows, arms),
    }

    out_path = Path(args.out) if args.out else RUNS / f"{args.run}.analysis.json"
    out_path.write_text(json.dumps(doc, indent=2, default=str) + "\n")

    print("=" * 78)
    print(f"HML-EVAL-001 analysis — run {args.run}")
    print("=" * 78)
    print(f"completed {cov['completed_calls']} / {cov['planned_calls']} planned calls "
          f"({cov['completion_fraction']})   UNRUN: {cov['UNRUN_CELLS']}")
    print(f"fully covered problem-generation cells: "
          f"{cov['fully_covered_problem_generations']}")
    print()
    print(f"{'arm':9s} {'n':>4s} {'answer accuracy':>26s} {'sem':>6s} {'parse':>6s} "
          f"{'ctok':>6s} {'sec':>6s}")
    for a in arms:
        s = doc["arm_summary"][a]
        if not s.get("trials"):
            print(f"{a:9s} {0:4d}   (no trials completed)")
            continue
        acc = Interval(**s["answer_accuracy"])
        sem = s["semantic_encoding_score"]
        semtxt = f"{sem['point']:.2f}" if sem else "  -- "
        pr = s["parse_success_rate"]
        prtxt = f"{pr:.2f}" if pr is not None else "  -- "
        print(f"{a:9s} {s['trials']:4d} {acc.render():>26s} {semtxt:>6s} {prtxt:>6s} "
              f"{s['mean_completion_tokens']:6.0f} {s['mean_latency_s']:6.1f}")
    print()
    print("PAIRED CONTRASTS (only cells completed in both arms)")
    for c in doc["contrasts"]:
        if c.get("status"):
            print(f"  {c['treatment']:8s} vs {c['control']:8s}  {c['status']}")
            continue
        d = c["paired_difference"]
        star = "  *" if c["ci_excludes_zero"] else "   "
        print(f"  {c['treatment']:8s} vs {c['control']:8s} n={c['n_pairs']:3d} "
              f"diff={d['point']:+.3f} CI[{d['ci95'][0]:+.3f},{d['ci95'][1]:+.3f}]{star} "
              f"McNemar p={c['mcnemar_exact_p']:.3f}  h={c['cohens_h']:+.2f} "
              f"({c['effect_size']})")
        print(f"           {c['question']}")
    print()
    print(f"written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
