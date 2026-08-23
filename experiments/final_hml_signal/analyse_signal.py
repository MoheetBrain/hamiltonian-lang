#!/usr/bin/env python3
"""Paired parent-clustered analysis and mechanical gate for the final HML signal test."""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
BOOTSTRAPS = 4_000
BOOTSTRAP_SEED = 20_260_823
METRICS = ("top1", "mrr", "nll", "entropy", "correct_action_logprob_margin")
DEPTH_ORDER = ("1", "2-3", "4-5", "6-10", "11-20", "21+")
COMPLEXITY_ORDER = ("LOW", "MEDIUM", "HIGH", "VERY_HIGH")


def load(rung: str, arm: str, seed: int) -> dict[str, dict]:
    path = HERE / "raw_predictions" / f"{rung}_{arm}_s{seed}.json"
    return {row["record_id"]: row for row in json.loads(path.read_text())["rows"]}


def value(row: dict, metric: str) -> float:
    if metric == "top1":
        return float(row["correct"])
    if metric == "mrr":
        return float(row.get("reciprocal_rank", 1 / row["rank"]))
    return float(row[metric])


def cluster_bootstrap(deltas: list[float], parents: list[str], seed_offset: int = 0) -> dict:
    grouped: dict[str, list[int]] = collections.defaultdict(list)
    for index, parent in enumerate(parents):
        grouped[parent].append(index)
    keys = sorted(grouped)
    groups = [np.asarray(grouped[key], dtype=int) for key in keys]
    data = np.asarray(deltas, dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED + seed_offset)
    draws = np.empty(BOOTSTRAPS)
    for draw in range(BOOTSTRAPS):
        chosen = rng.integers(0, len(groups), len(groups))
        indices = np.concatenate([groups[index] for index in chosen])
        draws[draw] = data[indices].mean()
    lo, hi = np.percentile(draws, (2.5, 97.5))
    return {"delta": float(data.mean()), "ci95": [float(lo), float(hi)],
            "p_gt_zero": float((draws > 0).mean()), "groups": len(keys), "n": len(data)}


def analyse_subset(hml: dict[str, dict], neutral: dict[str, dict], ids: list[str], seed_offset: int = 0) -> dict:
    if not ids:
        return {"n": 0}
    result = {"n": len(ids), "parents": len({hml[rid]["parent_id"] for rid in ids})}
    for metric in METRICS:
        hv = [value(hml[rid], metric) for rid in ids]
        nv = [value(neutral[rid], metric) for rid in ids]
        result[metric] = {
            "hml": statistics.fmean(hv), "neutral": statistics.fmean(nv),
            **cluster_bootstrap([a - b for a, b in zip(hv, nv)], [hml[rid]["parent_id"] for rid in ids], seed_offset),
        }
    return result


def combine_seeds(rung: str, seeds: list[int]) -> tuple[dict[str, dict], dict[str, dict], dict]:
    per_seed = {}
    raw = {arm: [load(rung, arm, seed) for seed in seeds] for arm in ("hml", "neutral")}
    ids = sorted(set.intersection(*(set(part) for values in raw.values() for part in values)))
    for seed_index, seed in enumerate(seeds):
        hml, neutral = raw["hml"][seed_index], raw["neutral"][seed_index]
        per_seed[str(seed)] = analyse_subset(hml, neutral, ids, seed_index)
    combined = {}
    for arm in ("hml", "neutral"):
        for rid in ids:
            template = dict(raw[arm][0][rid])
            template["correct"] = statistics.fmean(float(part[rid]["correct"]) for part in raw[arm])
            template["rank"] = statistics.fmean(part[rid]["rank"] for part in raw[arm])
            template["reciprocal_rank"] = statistics.fmean(1 / part[rid]["rank"] for part in raw[arm])
            for metric in ("nll", "entropy", "correct_action_logprob_margin"):
                template[metric] = statistics.fmean(part[rid][metric] for part in raw[arm])
            combined.setdefault(arm, {})[rid] = template
    return combined["hml"], combined["neutral"], per_seed


def interaction(hml: dict[str, dict], neutral: dict[str, dict], hard_ids: list[str], easy_ids: list[str], offset: int) -> dict:
    ids = hard_ids + easy_ids
    labels = [1] * len(hard_ids) + [0] * len(easy_ids)
    row_delta = [float(hml[rid]["correct"]) - float(neutral[rid]["correct"]) for rid in ids]
    grouped: dict[str, list[int]] = collections.defaultdict(list)
    for index, rid in enumerate(ids):
        grouped[hml[rid]["parent_id"]].append(index)
    groups = [np.asarray(grouped[key], dtype=int) for key in sorted(grouped)]
    data = np.asarray(row_delta)
    strata = np.asarray(labels)
    observed = data[strata == 1].mean() - data[strata == 0].mean()
    rng = np.random.default_rng(BOOTSTRAP_SEED + offset)
    draws = []
    for _ in range(BOOTSTRAPS):
        chosen = rng.integers(0, len(groups), len(groups))
        sample = np.concatenate([groups[index] for index in chosen])
        hard = data[sample][strata[sample] == 1]
        easy = data[sample][strata[sample] == 0]
        if len(hard) and len(easy):
            draws.append(float(hard.mean() - easy.mean()))
    lo, hi = np.percentile(draws, (2.5, 97.5))
    hard_delta = float(data[strata == 1].mean())
    easy_delta = float(data[strata == 0].mean())
    clear = len(hard_ids) >= 100 and hard_delta - easy_delta >= 0.03 and lo > 0
    return {"hard_n": len(hard_ids), "easy_n": len(easy_ids), "hard_delta": hard_delta,
            "easy_delta": easy_delta, "interaction": float(observed), "ci95": [float(lo), float(hi)],
            "clear_positive": bool(clear)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rung", default="10k", choices=("10k", "30k", "50k"))
    parser.add_argument("--seeds", type=int, nargs="+", default=[1])
    args = parser.parse_args()
    hml, neutral, per_seed = combine_seeds(args.rung, args.seeds)
    ids = sorted(hml)
    assert ids == sorted(neutral) and len(ids) == 3_000
    overall = analyse_subset(hml, neutral, ids)
    strata = {}
    strata["depth"] = {name: analyse_subset(hml, neutral, [rid for rid in ids if hml[rid]["depth_bin"] == name], 100 + index)
                       for index, name in enumerate(DEPTH_ORDER)}
    strata["complexity"] = {name: analyse_subset(hml, neutral, [rid for rid in ids if hml[rid]["complexity"] == name], 200 + index)
                            for index, name in enumerate(COMPLEXITY_ORDER)}
    strata["statistics_probability"] = analyse_subset(hml, neutral, [rid for rid in ids if hml[rid]["probability_statistics_related"]], 300)
    strata["lexical_correct"] = analyse_subset(hml, neutral, [rid for rid in ids if hml[rid]["lexical_correct"]], 301)
    strata["lexical_failure"] = analyse_subset(hml, neutral, [rid for rid in ids if not hml[rid]["lexical_correct"]], 302)
    strata["complete_multi_step"] = analyse_subset(hml, neutral, [rid for rid in ids if hml[rid]["complete_multi_step_trajectory"]], 303)
    strata["other_trajectory"] = analyse_subset(hml, neutral, [rid for rid in ids if not hml[rid]["complete_multi_step_trajectory"]], 304)
    depth_hard = [rid for rid in ids if hml[rid]["depth_bin"] in {"11-20", "21+"}]
    depth_easy = [rid for rid in ids if hml[rid]["depth_bin"] not in {"11-20", "21+"}]
    complexity_hard = [rid for rid in ids if hml[rid]["complexity"] in {"HIGH", "VERY_HIGH"}]
    complexity_easy = [rid for rid in ids if hml[rid]["complexity"] in {"LOW", "MEDIUM"}]
    interactions = {"depth_11plus_vs_1to10": interaction(hml, neutral, depth_hard, depth_easy, 400),
                    "high_veryhigh_vs_low_medium": interaction(hml, neutral, complexity_hard, complexity_easy, 401)}
    h_only = sum(float(hml[rid]["correct"]) > float(neutral[rid]["correct"]) for rid in ids)
    n_only = sum(float(hml[rid]["correct"]) < float(neutral[rid]["correct"]) for rid in ids)
    if len(args.seeds) == 1:
        mcnemar_p = binomtest(h_only, h_only + n_only, 0.5).pvalue if h_only + n_only else 1.0
    else:
        mcnemar_p = None
    lexical_accuracy = sum(hml[rid]["lexical_correct"] for rid in ids) / len(ids)
    delta = overall["top1"]["delta"]
    if len(args.seeds) == 1:
        if delta <= 0:
            gate = "TERMINATE_DELTA_NONPOSITIVE"
        elif delta < 0.02 and not any(item["clear_positive"] for item in interactions.values()):
            gate = "TERMINATE_SUB_2PP_NO_CLEAR_INTERACTION"
        elif delta >= 0.05:
            gate = "RUN_SECOND_10K_SEED_MATERIAL"
        elif delta >= 0.02:
            gate = "RUN_SECOND_10K_SEED_AMBIGUOUS"
        else:
            gate = "RUN_SECOND_10K_SEED_SPECIALIZED_INTERACTION"
    else:
        seed_deltas = [per_seed[str(seed)]["top1"]["delta"] for seed in args.seeds]
        both = all(item > 0 for item in seed_deltas)
        mean_delta = statistics.fmean(seed_deltas)
        replicated_interaction = any(item["clear_positive"] for item in interactions.values())
        pass_gate = both and (mean_delta >= 0.03 or overall["top1"]["ci95"][0] > 0 or replicated_interaction)
        gate = "PROCEED_TO_30K" if pass_gate else "TERMINATE_SECOND_SEED_GATE"
    result = {
        "rung": args.rung, "seeds": args.seeds, "n": len(ids), "chance_top1": 1 / 6,
        "historical_3k": {"hml": 0.6835, "neutral": 0.6605, "delta": 0.0230, "ci95": [0.0078, 0.0390], "label": "PRIOR_EXPERIMENT"},
        "lexical_baseline_final": lexical_accuracy, "overall": overall, "per_seed": per_seed,
        "strata": strata, "interactions": interactions,
        "mcnemar": {"hml_only_correct": h_only, "neutral_only_correct": n_only, "exact_two_sided_p": mcnemar_p},
        "relative_error_reduction": delta / (1 - overall["top1"]["neutral"]),
        "gate": gate,
        "scientific_scope": "depth-conditioned one-step action selection; not a free-running rollout",
    }
    output = HERE / f"statistics_{args.rung}_s{'-'.join(map(str, args.seeds))}.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
