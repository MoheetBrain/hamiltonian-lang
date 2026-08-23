#!/usr/bin/env python3
"""Score the fixed HML50K FINAL candidate set with one trained adapter."""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import re
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache

HERE = Path(__file__).resolve().parent
CORPUS = Path("/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus/data/hml_50k_final")
ART = Path("/Users/moheet/hml_research_artifacts/final_hml_signal")
MODEL_REVISION = "b968826d9c46dd6066d109eabc6255188de91218"
MODEL = Path("/Users/moheet/.cache/huggingface/hub/models--Qwen--Qwen3-8B/snapshots") / MODEL_REVISION
VIEWS = {"hml": "HML_WORKED_UTF8", "neutral": "STRUCTURED_NEUTRAL_WORKED"}
TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def sha256(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def softmax(values: list[float]) -> list[float]:
    maximum = max(values)
    exp = [math.exp(value - maximum) for value in values]
    total = sum(exp)
    return [value / total for value in exp]


def depth_bin(value: int) -> str:
    if value <= 1:
        return "1"
    if value <= 3:
        return "2-3"
    if value <= 5:
        return "4-5"
    if value <= 10:
        return "6-10"
    if value <= 20:
        return "11-20"
    return "21+"


def canonical_metadata() -> dict[str, dict]:
    all_rows = list(rows(CORPUS / "canonical/records.jsonl.gz"))
    by_parent: dict[str, list[dict]] = collections.defaultdict(list)
    for row in all_rows:
        by_parent[row["parent_id"]].append(row)
    complete: dict[str, bool] = {}
    for parent, values in by_parent.items():
        indices = sorted(value["trajectory_step_index"] for value in values)
        complete[parent] = indices == list(range(values[0]["proof_length"]))
    result = {}
    for row in all_rows:
        if row["split"] != "final":
            continue
        candidates = row["candidate_audit"]["candidates"]
        gold_id = row["candidate_audit"]["gold_candidate_id"]
        gold = next(candidate for candidate in candidates if candidate["candidate_id"] == gold_id)
        state = row["neutral_transition"]["state_before"]["claims"]["p0"]["proposition"]
        state_tokens = set(TOKEN_RE.findall(state.lower()))
        overlaps = []
        for candidate in candidates:
            candidate_tokens = set(TOKEN_RE.findall(candidate["tactic_text"].lower()))
            union = state_tokens | candidate_tokens
            overlaps.append(len(state_tokens & candidate_tokens) / len(union) if union else 0.0)
        lexical_index = max(range(len(overlaps)), key=overlaps.__getitem__)
        result[row["record_id"]] = {
            "complexity": {"EASY": "LOW", "MEDIUM": "MEDIUM", "HARD": "HIGH",
                           "LONG_OR_STRUCTURALLY_DENSE": "VERY_HIGH"}[row["complexity_bin"]],
            "depth": row["depth"], "depth_bin": row["depth_bin"],
            "trajectory_step_index": row["trajectory_step_index"],
            "proof_length": row["proof_length"], "trajectory_length_bin": depth_bin(row["proof_length"]),
            "fact_count": len(row["source_structural_record"]["state_before"]["hypotheses"]),
            "candidate_count": len(candidates), "tactic_family": gold["tactic_text"].strip().split(maxsplit=1)[0],
            "probability_statistics_related": row["probability_statistics_related"],
            "complete_trajectory": complete[row["parent_id"]],
            "complete_multi_step_trajectory": complete[row["parent_id"]] and row["proof_length"] > 1,
            "lexical_pred": lexical_index, "lexical_correct": candidates[lexical_index]["candidate_id"] == gold_id,
            "lexical_overlaps": overlaps,
        }
    assert len(result) == 3_000
    return result


def candidate_ids(row: dict) -> list[str]:
    assert row["candidate_count"] == 6
    return [f"C{index}" for index in range(6)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rung", default="10k", choices=("10k", "30k", "50k"))
    parser.add_argument("--arm", required=True, choices=VIEWS)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    cell = ART / args.rung / args.arm / f"seed_{args.seed}"
    cell_result = json.loads((cell / "cell_result.json").read_text())
    adapter = Path(cell_result["adapter_path"])
    suffix = f"_{args.limit}" if args.limit else ""
    output = HERE / "raw_predictions" / f"{args.rung}_{args.arm}_s{args.seed}{suffix}.json"
    if output.exists():
        print(output)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    view_path = CORPUS / "tasks/NEXT_ACTION_SELECT" / VIEWS[args.arm] / "final.jsonl.gz"
    evaluation = list(rows(view_path))
    if args.limit:
        evaluation = evaluation[:args.limit]
    meta = canonical_metadata()
    model, tokenizer = load(str(MODEL), adapter_path=str(adapter))
    model.eval()
    label_tokens = [tokenizer.encode(f"C{index}", add_special_tokens=False) for index in range(6)]
    assert all(len(tokens) == 2 for tokens in label_tokens)
    assert len({tokens[0] for tokens in label_tokens}) == 1
    shared_first = label_tokens[0][0]
    results = []
    started = time.time()
    for index, row in enumerate(evaluation, 1):
        labels = candidate_ids(row)
        assert row["target_text"] in labels
        gold = labels.index(row["target_text"])
        chat = tokenizer.apply_chat_template(
            [{"role": "user", "content": row["input_text"]}],
            add_generation_prompt=True, tokenize=False, enable_thinking=False,
        )
        prompt_ids = tokenizer.encode(chat)
        cache = make_prompt_cache(model)
        logits = model(mx.array([prompt_ids]), cache=cache)
        first = nn.log_softmax(logits[:, -1, :].astype(mx.float32), axis=-1)[0, shared_first]
        digit_logits = model(mx.array([[shared_first]]), cache=cache)
        digit_logprobs = nn.log_softmax(digit_logits[:, -1, :].astype(mx.float32), axis=-1)[0]
        scores_sum = [float(first + digit_logprobs[tokens[1]]) for tokens in label_tokens]
        scores_mean = [value / 2 for value in scores_sum]
        order = sorted(range(6), key=lambda item: -scores_mean[item])
        probs = softmax(scores_mean)
        best_other = max(scores_mean[item] for item in range(6) if item != gold)
        record = {
            "record_id": row["record_id"], "parent_id": row["parent_id"], "answer_index": gold,
            "candidate_ids": labels, "scores_sum": scores_sum, "scores_mean": scores_mean,
            "candidate_probabilities": probs, "pred_index": order[0], "rank": order.index(gold) + 1,
            "reciprocal_rank": 1 / (order.index(gold) + 1),
            "correct": order[0] == gold, "nll": -math.log(max(probs[gold], 1e-12)),
            "entropy": -sum(value * math.log(max(value, 1e-12)) for value in probs),
            "correct_action_logprob_margin": scores_mean[gold] - best_other,
            "n_prompt_tokens": len(prompt_ids), **meta[row["record_id"]],
        }
        results.append(record)
        if index % 100 == 0:
            elapsed = time.time() - started
            top1 = sum(item["correct"] for item in results) / len(results)
            print(f"{index}/{len(evaluation)} {elapsed/index:.3f}s/row top1={top1:.4f}", flush=True)
        del cache, logits, digit_logits
        mx.clear_cache()
    wall = time.time() - started
    summary = {
        "rung": args.rung, "arm": args.arm, "seed": args.seed, "rows": len(results),
        "top1": sum(row["correct"] for row in results) / len(results),
        "mrr": sum(1 / row["rank"] for row in results) / len(results),
        "nll": sum(row["nll"] for row in results) / len(results),
        "entropy": sum(row["entropy"] for row in results) / len(results),
        "correct_action_logprob_margin": sum(row["correct_action_logprob_margin"] for row in results) / len(results),
        "mean_prompt_tokens": sum(row["n_prompt_tokens"] for row in results) / len(results),
        "wall_seconds": wall, "seconds_per_row": wall / len(results),
        "peak_memory_gib": mx.get_peak_memory() / 2**30,
        "adapter_path": str(adapter), "adapter_sha256": sha256(adapter / "adapters.safetensors"),
        "view_sha256": sha256(view_path), "model_revision": MODEL_REVISION,
        "thinking_enabled": False, "candidate_scoring": "mean token log probability",
    }
    payload = {"summary": summary, "rows": results}
    with output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
        stream.write("\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
