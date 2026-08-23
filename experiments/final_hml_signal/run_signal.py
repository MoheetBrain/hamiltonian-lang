#!/usr/bin/env python3
"""Minimal preflight, data adapter, and matched MLX LoRA launcher for the final signal test."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

from safetensors import safe_open
from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
HML_REPO = HERE.parents[1]
CORPUS_REPO = Path("/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus")
CORPUS = CORPUS_REPO / "data/hml_50k_final"
PREVIOUS_REPO = Path("/Users/moheet/hml-model-experiments")
ART = Path("/Users/moheet/hml_research_artifacts/final_hml_signal")
MODEL_REVISION = "b968826d9c46dd6066d109eabc6255188de91218"
MODEL = Path("/Users/moheet/.cache/huggingface/hub/models--Qwen--Qwen3-8B/snapshots") / MODEL_REVISION
PYTHON = Path("/Users/moheet/hml-model-experiments/.venv/bin/python")
VIEWS = {"hml": "HML_WORKED_UTF8", "neutral": "STRUCTURED_NEUTRAL_WORKED"}
RUNG_HASHES = {
    "10k": "1eeb0b2f79d3472b96f72b6b9ee47b12ee9c20b17a9de6e647877169b198bbff",
    "30k": "255832921459b25dfe29fb86b20e38ab62e3e2e04d2067e359b8c8423cf137b4",
    "50k": "4777d6e6a2751888473a6eec894da750c2394c1349c8e3be5582862b355f5391",
}
RUNG_N = {"10k": 10_000, "30k": 30_000, "50k": 50_000}
MAXSEQ = 6_144


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def read_rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for raw in stream:
            yield raw, json.loads(raw)


def write_once_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def swap_mb() -> float:
    text = subprocess.check_output(["sysctl", "-n", "vm.swapusage"], text=True)
    match = re.search(r"used = ([0-9.]+)([MG])", text)
    if not match:
        return math.nan
    value = float(match.group(1))
    return value * (1024 if match.group(2) == "G" else 1)


def model_inventory() -> dict:
    config = json.loads((MODEL / "config.json").read_text())
    tensors = 0
    params = 0
    dtypes: dict[str, int] = {}
    for shard in sorted(MODEL.glob("model-*.safetensors")):
        with safe_open(shard, framework="numpy") as source:
            for key in source.keys():
                tensor = source.get_slice(key)
                shape = tensor.get_shape()
                dtype = str(tensor.get_dtype())
                tensors += 1
                params += math.prod(shape)
                dtypes[dtype] = dtypes.get(dtype, 0) + 1
    tokenizer_files = [MODEL / name for name in ("tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt")]
    return {
        "model_id": "Qwen/Qwen3-8B",
        "revision": MODEL_REVISION,
        "snapshot": str(MODEL),
        "tensor_count": tensors,
        "parameter_count": params,
        "tensor_dtypes": dtypes,
        "quantization_config": config.get("quantization_config"),
        "tokenizer_files": {path.name: sha256(path) for path in tokenizer_files},
    }


def view_path(rung: str, arm: str, split: str) -> Path:
    view = VIEWS[arm]
    if split == "train":
        return CORPUS / "rungs" / rung / "NEXT_ACTION_SELECT" / view / "train.jsonl.gz"
    return CORPUS / "tasks" / "NEXT_ACTION_SELECT" / view / f"{split}.jsonl.gz"


def verify_pair(left: Path, right: Path) -> dict:
    count = 0
    ids: list[str] = []
    parents: set[str] = set()
    unicode_escape = re.compile(r"(?<!\\)\\u[0-9a-fA-F]{4}")
    li, ri = read_rows(left), read_rows(right)
    while True:
        try:
            lraw, lrow = next(li)
        except StopIteration:
            lraw = lrow = None
        try:
            rraw, rrow = next(ri)
        except StopIteration:
            rraw = rrow = None
        if lrow is None or rrow is None:
            assert lrow is None and rrow is None, "paired length mismatch"
            break
        identity = ("record_id", "parent_id", "split", "task", "target_text")
        assert tuple(lrow[k] for k in identity) == tuple(rrow[k] for k in identity)
        assert lrow["audit_metadata"]["canonical_transition_sha256"] == rrow["audit_metadata"]["canonical_transition_sha256"]
        assert lrow["audit_metadata"]["ensure_ascii"] is False
        assert rrow["audit_metadata"]["ensure_ascii"] is False
        assert not unicode_escape.search(lraw) and not unicode_escape.search(rraw)
        neutral_candidates = json.loads(rrow["input_text"])["candidates"]
        expected_block = "\n".join(
            f"{candidate['candidate_id']} :: {candidate['tactic_text']}"
            for candidate in neutral_candidates
        )
        assert expected_block in lrow["input_text"]
        assert len(neutral_candidates) == lrow["candidate_count"] == rrow["candidate_count"] == 6
        count += 1
        ids.append(lrow["record_id"])
        parents.add(lrow["parent_id"])
    return {"rows": count, "record_ids": ids, "parents": parents}


def preflight() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    out_path = ART / "preflight.json"
    if out_path.exists():
        existing = json.loads(out_path.read_text())
        if existing.get("result") != "PASS":
            raise SystemExit("existing preflight did not pass")
        print(json.dumps(existing, indent=2))
        return
    assert git(CORPUS_REPO, "rev-parse", "HEAD") == "627194144abd9396dadbebf0b7834e76b937d908"
    assert git(CORPUS_REPO, "status", "--porcelain") == ""
    immutable_paths = ["data/hml_50k_final/canonical", "data/hml_50k_final/rungs", "data/hml_50k_final/tasks", "data/hml_50k_final/structural_stress"]
    diff = git(CORPUS_REPO, "diff", "--name-only", "fb6e28edec0f77753d97486cbae759a59f1d1f38..HEAD", "--", *immutable_paths)
    assert diff == ""
    manifest_hash = sha256(CORPUS / "HML50K_MANIFEST.json")
    expected_manifest = (CORPUS / "HML50K_MANIFEST.sha256").read_text().split()[0]
    assert manifest_hash == expected_manifest
    rung_ids: dict[str, list[str]] = {}
    for rung, expected in RUNG_HASHES.items():
        path = CORPUS / "rungs" / rung / "record_ids.json"
        assert sha256(path) == expected
        rung_ids[rung] = json.loads(path.read_text())
    assert rung_ids["10k"] == rung_ids["30k"][:10_000]
    assert rung_ids["30k"] == rung_ids["50k"][:30_000]
    pair_summaries = {}
    train_all = verify_pair(view_path("50k", "hml", "train"), view_path("50k", "neutral", "train"))
    final = verify_pair(view_path("10k", "hml", "final"), view_path("10k", "neutral", "final"))
    assert len(train_all["record_ids"]) == 50_000 and len(final["record_ids"]) == 3_000
    assert not (set(train_all["record_ids"]) & set(final["record_ids"]))
    assert not (train_all["parents"] & final["parents"])
    for rung, n in RUNG_N.items():
        pair = verify_pair(view_path(rung, "hml", "train"), view_path(rung, "neutral", "train"))
        assert pair["rows"] == n and pair["record_ids"] == rung_ids[rung]
        pair_summaries[rung] = {"rows": n, "parents": len(pair["parents"])}
    model = model_inventory()
    assert model["tensor_dtypes"] == {"BF16": 399}
    assert model["quantization_config"] is None
    previous_config = PREVIOUS_REPO / "experiments/hml_phase2/synthetic_math/exec_lora_config.yaml"
    assert sha256(previous_config) == sha256(HERE / "lora_config.yaml")
    result = {
        "result": "PASS",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "corpus_commit": git(CORPUS_REPO, "rev-parse", "HEAD"),
        "payload_commit": "fb6e28edec0f77753d97486cbae759a59f1d1f38",
        "manifest_sha256": manifest_hash,
        "rung_hashes": RUNG_HASHES,
        "nested_rungs": True,
        "paired_rungs": pair_summaries,
        "final_rows": 3_000,
        "final_parents": len(final["parents"]),
        "train_final_record_overlap": 0,
        "train_final_parent_overlap": 0,
        "unicode_escape_count": 0,
        "model": model,
        "recipe_sha256": sha256(HERE / "lora_config.yaml"),
        "previous_recipe_sha256": sha256(previous_config),
        "python": sys.version,
        "platform": platform.platform(),
        "stack": subprocess.check_output([str(PYTHON), "-c", "import importlib.metadata as m; print('mlx='+m.version('mlx')); print('mlx-lm='+m.version('mlx-lm')); print('transformers='+m.version('transformers'))"], text=True).splitlines(),
    }
    write_once_json(out_path, result)
    print(json.dumps(result, indent=2))


def prepare(rung: str, arm: str) -> None:
    preflight()
    out = ART / "prepared" / rung / arm
    meta_path = out / "dataset_manifest.json"
    if meta_path.exists():
        print(meta_path.read_text())
        return
    out.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)

    def convert(path: Path, limit: int | None = None) -> tuple[list[dict], dict]:
        records = []
        raw_input = raw_target = total_tokens = supervised_tokens = 0
        max_tokens = 0
        for _, row in read_rows(path):
            prompt, completion = row["input_text"], row["target_text"]
            messages = [{"role": "user", "content": prompt}, {"role": "assistant", "content": completion}]
            tokens = tokenizer.apply_chat_template(messages, return_dict=False)
            offset = len(tokenizer.apply_chat_template(messages[:-1], add_generation_prompt=True, return_dict=False))
            assert offset < len(tokens) <= MAXSEQ
            records.append({"prompt": prompt, "completion": completion, "_n_tokens": len(tokens), "_record_id": row["record_id"]})
            raw_input += len(tokenizer.encode(prompt, add_special_tokens=False))
            raw_target += len(tokenizer.encode(completion, add_special_tokens=False))
            total_tokens += len(tokens)
            supervised_tokens += len(tokens) - offset
            max_tokens = max(max_tokens, len(tokens))
            if limit and len(records) >= limit:
                break
        records.sort(key=lambda item: (item["_n_tokens"], item["_record_id"]))
        padded = 0
        for index in range(0, len(records) - 1, 2):
            longest = max(records[index]["_n_tokens"], records[index + 1]["_n_tokens"])
            padded += 2 * min(MAXSEQ, 1 + 32 * math.ceil(longest / 32))
        stats = {"rows": len(records), "raw_input_tokens": raw_input, "raw_target_tokens": raw_target,
                 "chat_tokens": total_tokens, "supervised_tokens": supervised_tokens,
                 "padded_model_tokens": padded, "max_chat_tokens": max_tokens}
        return records, stats

    train, train_stats = convert(view_path(rung, arm, "train"))
    valid, valid_stats = convert(view_path(rung, arm, "dev"), limit=64)
    for name, records in (("train", train), ("valid", valid)):
        destination = out / f"{name}.jsonl"
        with destination.open("x", encoding="utf-8") as stream:
            for item in records:
                stream.write(json.dumps({"prompt": item["prompt"], "completion": item["completion"]}, ensure_ascii=False) + "\n")
    meta = {"rung": rung, "arm": arm, "view": VIEWS[arm], "train": train_stats, "valid": valid_stats,
            "source_sha256": sha256(view_path(rung, arm, "train")),
            "train_jsonl_sha256": sha256(out / "train.jsonl"), "valid_jsonl_sha256": sha256(out / "valid.jsonl")}
    write_once_json(meta_path, meta)
    print(json.dumps(meta, indent=2))


def train(rung: str, arm: str, seed: int) -> None:
    prepare(rung, arm)
    cell = ART / rung / arm / f"seed_{seed}"
    complete = cell / "cell_result.json"
    if complete.exists():
        print(complete.read_text())
        return
    cell.mkdir(parents=True, exist_ok=True)
    attempts = sorted(cell.glob("attempt_*.log"))
    attempt = len(attempts) + 1
    adapter = cell / f"adapter_attempt_{attempt}"
    log_path = cell / f"attempt_{attempt:02d}.log"
    command = [str(PYTHON), "-m", "mlx_lm", "lora", "--model", str(MODEL), "--train",
               "--data", str(ART / "prepared" / rung / arm), "-c", str(HERE / "lora_config.yaml"),
               "--batch-size", "2", "--iters", str(RUNG_N[rung] // 2), "--learning-rate", "1e-4",
               "--max-seq-length", str(MAXSEQ), "--grad-checkpoint", "--steps-per-report", "100",
               "--steps-per-eval", "100000", "--val-batches", "1", "--adapter-path", str(adapter),
               "--save-every", "100", "--seed", str(seed)]
    static = {
        "rung": rung, "arm": arm, "seed": seed, "attempt": attempt, "command": command,
        "git_sha": git(HML_REPO, "rev-parse", "HEAD"), "protocol_sha256": sha256(HERE / "FINAL_SIGNAL_PROTOCOL.md"),
        "dataset_manifest_sha256": sha256(ART / "prepared" / rung / arm / "dataset_manifest.json"),
        "swap_before_mb": swap_mb(), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_once_json(cell / f"attempt_{attempt:02d}_manifest.json", static)
    started = time.time()
    with log_path.open("x", encoding="utf-8") as log:
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, text=True)
        returncode = proc.wait()
    wall = time.time() - started
    text = log_path.read_text(errors="replace")
    peaks = [float(x) for x in re.findall(r"Peak mem ([0-9.]+) GB", text)]
    losses = [float(x) for x in re.findall(r"Train loss ([0-9.]+)", text)]
    trained = [int(x) for x in re.findall(r"Trained Tokens ([0-9]+)", text)]
    rates = [float(x) for x in re.findall(r"Tokens/sec ([0-9.]+)", text)]
    result = {**static, "returncode": returncode, "wall_seconds": wall, "swap_after_mb": swap_mb(),
              "swap_delta_mb": swap_mb() - static["swap_before_mb"], "peak_memory_gb": max(peaks, default=None),
              "loss_history": losses, "reported_trained_tokens": trained[-1] if trained else None,
              "mean_reported_supervised_tokens_per_second": sum(rates) / len(rates) if rates else None,
              "adapter_path": str(adapter), "adapter_sha256": sha256(adapter / "adapters.safetensors") if (adapter / "adapters.safetensors").exists() else None,
              "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    if returncode != 0 or not result["adapter_sha256"] or not losses or not all(math.isfinite(x) for x in losses):
        write_once_json(cell / f"attempt_{attempt:02d}_failure.json", result)
        raise SystemExit(f"training failed; see {log_path}")
    write_once_json(complete, result)
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    prep = sub.add_parser("prepare")
    prep.add_argument("--rung", choices=RUNG_N, default="10k")
    prep.add_argument("--arm", choices=VIEWS, required=True)
    tr = sub.add_parser("train")
    tr.add_argument("--rung", choices=RUNG_N, default="10k")
    tr.add_argument("--arm", choices=VIEWS, required=True)
    tr.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    if args.command == "preflight":
        preflight()
    elif args.command == "prepare":
        prepare(args.rung, args.arm)
    else:
        train(args.rung, args.arm, args.seed)


if __name__ == "__main__":
    main()
