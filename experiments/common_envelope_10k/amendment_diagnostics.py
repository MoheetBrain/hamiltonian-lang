#!/usr/bin/env python3
"""Frozen diagnostic amendment: base-model baseline, strict parity, training sanity."""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache
from transformers import AutoTokenizer

import common_envelope as common


def strict_semantic_parity() -> dict:
    canonical = common.canonical_lookup()
    totals = collections.Counter()
    split_results = {}
    for split, expected in (("train", 10_000), ("dev", 3_000), ("final", 3_000)):
        hrows, nrows = common.load_split(split)
        assert len(hrows) == len(nrows) == expected
        counts = collections.Counter()
        for hml, neutral in zip(hrows, nrows):
            pair = common.paired_projection(hml, neutral)
            authority = canonical[pair["record_id"]]["neutral_transition"]["state_before"]
            hml_state = common.export_state(common.parse_state(pair["hml_state"]))
            neutral_state = json.loads(pair["neutral_state"])
            counts["pairs"] += 1
            counts["full_state_mismatches"] += hml_state != authority or neutral_state != authority
            counts["claims_or_facts_mismatches"] += hml_state["claims"] != authority["claims"]
            counts["goals_mismatches"] += hml_state["goals"] != authority["goals"]
            counts["scope_or_local_context_mismatches"] += hml_state["active_scopes"] != authority["active_scopes"]
            counts["branches_mismatches"] += hml_state["branches"] != authority["branches"]
            counts["candidates_mismatches"] += hml_state["candidates"] != authority["candidates"]
            counts["obligations_mismatches"] += hml_state["obligations"] != authority["obligations"]
            hml_goal_markers = [claim["proposition"].count("⊢") for claim in hml_state["claims"].values()]
            authority_goal_markers = [claim["proposition"].count("⊢") for claim in authority["claims"].values()]
            counts["embedded_goal_marker_mismatches"] += hml_goal_markers != authority_goal_markers
            counts["candidate_context_outside_state_mismatches"] += pair["hml_prompt"].split("\n</STATE>", 1)[1] != pair["neutral_prompt"].split("\n</STATE>", 1)[1]
            counts["hml_extra_semantic_information"] += hml_state != neutral_state
        split_results[split] = dict(counts)
        totals.update(counts)
    failures = {key: value for key, value in totals.items() if key != "pairs" and value}
    result = {
        "result": "PASS" if not failures else "FAIL", "total_pairs": totals["pairs"],
        "splits": split_results, "totals": dict(totals),
        "claims_facts_hypotheses": "full typed claim objects compared exactly",
        "goals": "typed goals and embedded Lean goal markers compared exactly",
        "scope_local_context": "active scopes plus full propositions compared exactly",
        "candidate_context": "byte-identical outside <STATE> and excluded from semantic parser",
        "extra_hml_information": "forbidden; parsed HML must equal canonical Neutral state",
    }
    common.write_json(common.HERE / "audits/strict_semantic_parity.json", result, exclusive=False)
    assert result["result"] == "PASS"
    return result


def score_zero_shot() -> None:
    output_paths = {arm: common.HERE / "raw" / f"zero_shot_{arm}_predictions.jsonl" for arm in common.ARMS}
    summary_path = common.HERE / "diagnostics/zero_shot_summary.json"
    analysis_path = common.HERE / "diagnostics/zero_shot_analysis.json"
    if summary_path.exists() and analysis_path.exists() and all(path.exists() for path in output_paths.values()):
        return
    assert not summary_path.exists() and not analysis_path.exists() and not any(path.exists() for path in output_paths.values())
    for path in output_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    hrows, nrows = common.load_split("final")
    projections = [common.paired_projection(hml, neutral) for hml, neutral in zip(hrows, nrows)]
    metadata = common.canonical_metadata()
    model, tokenizer = load(str(common.MODEL))
    model.eval()
    label_tokens = [tokenizer.encode(f"C{i}", add_special_tokens=False) for i in range(6)]
    assert all(len(item) == 2 for item in label_tokens) and len({item[0] for item in label_tokens}) == 1
    shared = label_tokens[0][0]
    summaries = {}
    for arm in common.ARMS:
        temporary = output_paths[arm].with_suffix(".jsonl.partial")
        assert not temporary.exists()
        started = time.time()
        totals = collections.Counter()
        metric_totals = collections.Counter()
        prompt_lengths = []
        with temporary.open("x", encoding="utf-8") as stream:
            for index, pair in enumerate(projections, 1):
                prompt = pair[f"{arm}_prompt"]
                chat = tokenizer.apply_chat_template(
                    [{"role": "user", "content": prompt}], add_generation_prompt=True,
                    tokenize=False, enable_thinking=False,
                )
                prompt_ids = tokenizer.encode(chat)
                cache = make_prompt_cache(model)
                logits = model(mx.array([prompt_ids]), cache=cache)
                first = nn.log_softmax(logits[:, -1, :].astype(mx.float32), axis=-1)[0, shared]
                digits = model(mx.array([[shared]]), cache=cache)
                digit_log_probs = nn.log_softmax(digits[:, -1, :].astype(mx.float32), axis=-1)[0]
                sums = [float(first + digit_log_probs[item[1]]) for item in label_tokens]
                means = [value / 2 for value in sums]
                order = sorted(range(6), key=lambda item: -means[item])
                gold = int(pair["target"][1:])
                probabilities = np.exp(np.asarray(means) - max(means))
                probabilities /= probabilities.sum()
                best_other = max(means[item] for item in range(6) if item != gold)
                item = {
                    "record_id": pair["record_id"], "parent_id": pair["parent_id"],
                    "answer_index": gold, "scores_sum": sums, "scores_mean": means,
                    "candidate_probabilities": probabilities.tolist(), "pred_index": order[0],
                    "rank": order.index(gold) + 1, "correct": order[0] == gold,
                    "nll": -math.log(max(float(probabilities[gold]), 1e-12)),
                    "entropy": -sum(float(value) * math.log(max(float(value), 1e-12)) for value in probabilities),
                    "gold_margin": means[gold] - best_other, "prompt_tokens": len(prompt_ids),
                    "prompt_sha256": common.digest_text(prompt),
                    "state_sha256": common.digest_text(pair[f"{arm}_state"]),
                    "candidate_sha256": [common.digest_text(candidate["tactic_text"]) for candidate in pair["candidates"]],
                    **metadata[pair["record_id"]],
                }
                stream.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
                totals["correct"] += item["correct"]
                metric_totals["mrr"] += 1 / item["rank"]
                metric_totals["nll"] += item["nll"]
                metric_totals["entropy"] += item["entropy"]
                metric_totals["gold_margin"] += item["gold_margin"]
                prompt_lengths.append(len(prompt_ids))
                if index % 100 == 0:
                    print(f"{arm} {index}/3000", flush=True)
                del cache, logits, digits
                mx.clear_cache()
        temporary.rename(output_paths[arm])
        n = len(projections)
        summaries[arm] = {
            "n": n, "top1": totals["correct"] / n,
            **{metric: metric_totals[metric] / n for metric in ("mrr", "nll", "entropy", "gold_margin")},
            "mean_prompt_tokens": statistics.fmean(prompt_lengths), "wall_seconds": time.time() - started,
            "peak_mlx_gib": mx.get_peak_memory() / 2**30, "raw_sha256": common.sha(output_paths[arm]),
        }
    common.write_json(summary_path, {
        "base_model": "Qwen/Qwen3-8B", "revision": common.MODEL_REV,
        "adapter": None, "thinking_enabled": False, "scorer": "identical shared-prefix C0-C5 scorer",
        "arms": summaries,
    })
    hml = {row["record_id"]: row for row in (json.loads(line) for line in output_paths["hml"].read_text().splitlines())}
    neutral = {row["record_id"]: row for row in (json.loads(line) for line in output_paths["neutral"].read_text().splitlines())}
    ids = sorted(hml)
    common.write_json(analysis_path, {
        "overall": common.subset(ids, hml, neutral),
        "strata": {
            "depth": {name: common.subset([rid for rid in ids if hml[rid]["depth_bin"] == name], hml, neutral, 700 + i)
                      for i, name in enumerate(common.DEPTH_ORDER)},
            "complexity": {name: common.subset([rid for rid in ids if hml[rid]["complexity"] == name], hml, neutral, 800 + i)
                           for i, name in enumerate(("LOW", "MEDIUM", "HIGH", "VERY_HIGH"))},
        },
    })


def training_sanity(seeds: list[int]) -> dict:
    recipe = (common.RECIPE).read_text()
    manifests = {arm: json.loads((common.ART / "prepared" / arm / "dataset_manifest.json").read_text()) for arm in common.ARMS}
    prepared = {arm: [json.loads(line) for line in (common.ART / "prepared" / arm / "train.jsonl").read_text().splitlines()]
                for arm in common.ARMS}
    results = {(arm, seed): json.loads((common.HERE / "diagnostics" / f"train_{arm}_seed{seed}.json").read_text())
               for arm in common.ARMS for seed in seeds}
    checks = {
        "single_shared_recipe": all(result["config_sha256"] == common.sha(common.RECIPE) for result in results.values()),
        "prompt_masking_identical": "mask_prompt: true" in recipe,
        "target_masking_identical": all(a["completion"] == b["completion"] for a, b in zip(prepared["hml"], prepared["neutral"])),
        "target_tokens_supervised_identically": manifests["hml"]["train"]["supervised_suffix_tokens"] == manifests["neutral"]["train"]["supervised_suffix_tokens"] == 80_000,
        "no_neutral_truncation": json.loads((common.HERE / "audits/token_audit.json").read_text())["overflow_counts"]["neutral"] == 0,
        "no_neutral_tokenization_issue": manifests["neutral"]["train"]["max_full_tokens"] <= common.MAXSEQ,
        "examples_seen_identical": all(results[("hml", seed)]["examples_seen"] == results[("neutral", seed)]["examples_seen"] == 10_000 for seed in seeds),
        "optimizer_steps_identical": all(results[("hml", seed)]["iterations"] == results[("neutral", seed)]["iterations"] == 5_000 for seed in seeds),
        "neutral_loss_falls": all(results[("neutral", seed)]["final_training_loss"] < results[("neutral", seed)]["first_training_loss"] for seed in seeds),
    }
    value = {
        "result": "PASS" if all(checks.values()) else "FAIL", "seeds": seeds, "checks": checks,
        "supervised_target_tokens": {arm: manifests[arm]["train"]["supervised_suffix_tokens"] for arm in common.ARMS},
        "training": {f"{arm}_seed{seed}": {
            "examples_seen": results[(arm, seed)]["examples_seen"], "optimizer_steps": results[(arm, seed)]["iterations"],
            "first_loss": results[(arm, seed)]["first_training_loss"], "final_loss": results[(arm, seed)]["final_training_loss"],
            "reported_tokens_seen": results[(arm, seed)]["reported_tokens_seen"],
        } for arm in common.ARMS for seed in seeds},
    }
    common.write_json(common.HERE / "diagnostics/neutral_training_sanity.json", value, exclusive=False)
    assert value["result"] == "PASS"
    return value


def finalize_seed1() -> dict:
    source = json.loads((common.HERE / "diagnostics/analysis_seed1.json").read_text())
    zero = json.loads((common.HERE / "diagnostics/zero_shot_analysis.json").read_text())
    hml = common.load_scores("hml", 1)
    neutral = common.load_scores("neutral", 1)
    ids = sorted(hml)
    old_hml, old_neutral, old_delta = 0.8575, 0.5020, 0.3555
    new_hml = source["overall"]["top1"]["hml"]
    new_neutral = source["overall"]["top1"]["neutral"]
    new_delta = source["overall"]["top1"]["delta"]
    comparison = {
        "old_hml": old_hml, "new_hml": new_hml, "hml_change": new_hml - old_hml,
        "old_neutral": old_neutral, "new_neutral": new_neutral, "neutral_change": new_neutral - old_neutral,
        "old_delta": old_delta, "new_delta": new_delta, "delta_retained_fraction": new_delta / old_delta,
        "mechanical_interpretation": "previous envelope disproportionately hurt Neutral",
    }
    value = {
        **source, "final_seed_count": 1, "seed2": "NOT_RUN_BY_FROZEN_GATE",
        "comparison_previous": comparison,
        "zero_shot": zero,
        "learning_gain": {
            "hml": new_hml - zero["overall"]["top1"]["hml"],
            "neutral": new_neutral - zero["overall"]["top1"]["neutral"],
        },
        "neutral_training_sanity": json.loads((common.HERE / "diagnostics/neutral_training_sanity.json").read_text()),
        "final_verdict": "COMMON_ENVELOPE_EFFECT_FAILED",
    }
    output = common.HERE / "diagnostics/final_analysis.json"
    common.write_json(output, value, exclusive=False)
    paired = common.HERE / "diagnostics/paired_final_diagnostics.jsonl"
    disagreements = common.HERE / "diagnostics/disagreement_summary.json"
    if not paired.exists() and not disagreements.exists():
        common.paired_diagnostics(hml, neutral, ids, [1], value)
    failure = common.HERE / "diagnostics/failure_analysis.md"
    if not failure.exists():
        common.failure_analysis(hml, neutral, ids)
    size = paired.stat().st_size
    assert size < 50 * 1024 * 1024
    value["diagnostic_file"] = {"path": str(paired), "bytes": size, "under_50_mb": True,
                                "contains_full_prompts": False}
    common.write_json(output, value, exclusive=False)
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("strict-parity")
    subparsers.add_parser("zero-shot")
    sanity = subparsers.add_parser("training-sanity")
    sanity.add_argument("--seeds", nargs="+", type=int, required=True)
    subparsers.add_parser("finalize-seed1")
    args = parser.parse_args()
    if args.command == "strict-parity":
        strict_semantic_parity()
    elif args.command == "zero-shot":
        score_zero_shot()
    elif args.command == "finalize-seed1":
        finalize_seed1()
    else:
        training_sanity(args.seeds)


if __name__ == "__main__":
    main()
