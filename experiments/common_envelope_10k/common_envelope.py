#!/usr/bin/env python3
"""Frozen driver for the HML/Neutral common-envelope 10K causal control."""
from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import math
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache
from safetensors import safe_open
from scipy.stats import binomtest, pearsonr
from transformers import AutoTokenizer

HML_SOURCE = Path("/Users/moheet/hml_vnext_worktree")
sys.path.insert(0, str(HML_SOURCE / "src"))
from hamiltonian_lang.semantic_state import export_state, parse_state  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CORPUS_REPO = Path("/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus")
CORPUS = CORPUS_REPO / "data/hml_50k_final"
OLD_EXP = REPO / "experiments/final_hml_signal"
ART = Path("/Users/moheet/hml_research_artifacts/common_envelope_10k")
MODEL_REV = "b968826d9c46dd6066d109eabc6255188de91218"
MODEL = Path("/Users/moheet/.cache/huggingface/hub/models--Qwen--Qwen3-8B/snapshots") / MODEL_REV
PYTHON = Path("/Users/moheet/hml-model-experiments/.venv/bin/python")
RECIPE = OLD_EXP / "lora_config.yaml"
RUNG_HASH = "1eeb0b2f79d3472b96f72b6b9ee47b12ee9c20b17a9de6e647877169b198bbff"
CORPUS_COMMIT = "627194144abd9396dadbebf0b7834e76b937d908"
PAYLOAD_COMMIT = "fb6e28edec0f77753d97486cbae759a59f1d1f38"
HML_AUTHORITY = "68178f07784d2a17a9aed9c4dedbea9c740c97a0"
MAXSEQ = 6144
N_TRAIN = 10_000
BOOTSTRAPS = 4_000
BOOTSTRAP_SEED = 20_260_823
ARMS = {"hml": "HML_WORKED_UTF8", "neutral": "STRUCTURED_NEUTRAL_WORKED"}
DEPTH_ORDER = ("1", "2-3", "4-5", "6-10", "11-20", "21+")
COMPLEXITY_MAP = {"EASY": "LOW", "MEDIUM": "MEDIUM", "HARD": "HIGH", "LONG_OR_STRUCTURALLY_DENSE": "VERY_HIGH"}
TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)

PREFIX = (
    "Choose the single most useful next mathematical tactic from the six candidates.\n\n"
    "<STATE>\n"
)
SUFFIX_HEAD = "\n</STATE>\n\n<CANDIDATES>\n"
SUFFIX_TAIL = (
    "\n</CANDIDATES>\n\n"
    "Answer with exactly one label:\n"
    "C0 / C1 / C2 / C3 / C4 / C5"
)
HML_OLD_PREFIX = "Below is a mathematical proof state.\n\n"
HML_OLD_MARKER = "\nChoose the single most useful next tactic from this candidate set.\n"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def read_rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def write_json(path: Path, value: object, exclusive: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if exclusive else "w"
    with path.open(mode, encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def percentile(values: list[int | float], q: float) -> float:
    return float(np.quantile(np.asarray(values), q))


def stats(values: list[int | float]) -> dict:
    return {
        "mean": statistics.fmean(values), "median": statistics.median(values),
        "p95": percentile(values, .95), "max": max(values), "total": sum(values),
    }


def swap_mb() -> float:
    text = subprocess.check_output(["sysctl", "-n", "vm.swapusage"], text=True)
    match = re.search(r"used = ([0-9.]+)([MG])", text)
    if not match:
        return math.nan
    value = float(match.group(1))
    return value * (1024 if match.group(2) == "G" else 1)


def memory_snapshot() -> dict:
    vm = subprocess.check_output(["vm_stat"], text=True)
    page_match = re.search(r"page size of (\d+) bytes", vm)
    page = int(page_match.group(1)) if page_match else 16_384
    values = {key: int(value.replace(".", "")) for key, value in re.findall(r"^([^:]+):\s+(\d+\.)$", vm, re.M)}
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "swap_used_mb": swap_mb(),
        "free_gib": values.get("Pages free", 0) * page / 2**30,
        "active_gib": values.get("Pages active", 0) * page / 2**30,
        "wired_gib": values.get("Pages wired down", 0) * page / 2**30,
        "compressed_gib": values.get("Pages occupied by compressor", 0) * page / 2**30,
    }


def source_path(split: str, arm: str) -> Path:
    view = ARMS[arm]
    if split == "train":
        return CORPUS / "rungs/10k/NEXT_ACTION_SELECT" / view / "train.jsonl.gz"
    return CORPUS / "tasks/NEXT_ACTION_SELECT" / view / f"{split}.jsonl.gz"


def load_split(split: str) -> tuple[list[dict], list[dict]]:
    return list(read_rows(source_path(split, "hml"))), list(read_rows(source_path(split, "neutral")))


def extract_hml_state(row: dict) -> str:
    value = row["input_text"]
    assert value.startswith(HML_OLD_PREFIX) and HML_OLD_MARKER in value
    return value[len(HML_OLD_PREFIX):].split(HML_OLD_MARKER, 1)[0]


def candidate_block(candidates: list[dict]) -> str:
    assert [item["candidate_id"] for item in candidates] == [f"C{i}" for i in range(6)]
    return "\n".join(f"{item['candidate_id']}: {item['tactic_text']}" for item in candidates)


def suffix(candidates: list[dict]) -> str:
    return SUFFIX_HEAD + candidate_block(candidates) + SUFFIX_TAIL


def paired_projection(hml: dict, neutral: dict) -> dict:
    neutral_obj = json.loads(neutral["input_text"])
    candidates = neutral_obj["candidates"]
    old_block = "\n".join(f"{item['candidate_id']} :: {item['tactic_text']}" for item in candidates)
    assert old_block in hml["input_text"]
    hml_payload = extract_hml_state(hml)
    neutral_payload = canonical(neutral_obj["state_before"])
    shared_suffix = suffix(candidates)
    return {
        "record_id": hml["record_id"], "parent_id": hml["parent_id"],
        "target": hml["target_text"], "candidates": candidates,
        "canonical_transition_sha256": hml["audit_metadata"]["canonical_transition_sha256"],
        "hml_state": hml_payload, "neutral_state": neutral_payload,
        "hml_prompt": PREFIX + hml_payload + shared_suffix,
        "neutral_prompt": PREFIX + neutral_payload + shared_suffix,
        "prefix": PREFIX, "suffix": shared_suffix,
    }


def canonical_lookup() -> dict[str, dict]:
    return {row["record_id"]: row for row in read_rows(CORPUS / "canonical/records.jsonl.gz")}


def model_hash() -> str:
    digest = hashlib.sha256()
    for path in [MODEL / "config.json", MODEL / "model.safetensors.index.json", *sorted(MODEL.glob("model-*.safetensors"))]:
        digest.update(path.name.encode())
        digest.update(bytes.fromhex(sha(path)))
    return digest.hexdigest()


def run_audits() -> dict:
    audits_dir = HERE / "audits"
    audits_dir.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)
    canon = canonical_lookup()
    byte_total = collections.Counter()
    semantic_total = collections.Counter()
    byte_splits = {}
    semantic_splits = {}
    token_values = {arm: {key: [] for key in ("state_chars", "state_bytes", "state_tokens", "prompt_chars", "prompt_bytes", "prompt_tokens", "chat_prompt_tokens", "full_train_tokens")} for arm in ARMS}
    overflow = {arm: 0 for arm in ARMS}
    train_ids = set()
    train_parents = set()
    final_ids = set()
    final_parents = set()
    for split, expected in (("train", 10_000), ("dev", 3_000), ("final", 3_000)):
        hrows, nrows = load_split(split)
        assert len(hrows) == len(nrows) == expected
        bc = collections.Counter()
        sc = collections.Counter()
        for hml, neutral in zip(hrows, nrows):
            pair = paired_projection(hml, neutral)
            bc["pairs"] += 1
            bc["record_id_mismatches"] += hml["record_id"] != neutral["record_id"]
            bc["parent_id_mismatches"] += hml["parent_id"] != neutral["parent_id"]
            bc["target_mismatches"] += hml["target_text"] != neutral["target_text"]
            bc["semantic_source_mismatches"] += hml["audit_metadata"]["canonical_transition_sha256"] != neutral["audit_metadata"]["canonical_transition_sha256"]
            bc["prefix_mismatches"] += pair["hml_prompt"][:len(PREFIX)] != pair["neutral_prompt"][:len(PREFIX)]
            h_suffix = pair["hml_prompt"].split("\n</STATE>", 1)[1]
            n_suffix = pair["neutral_prompt"].split("\n</STATE>", 1)[1]
            bc["suffix_mismatches"] += h_suffix != n_suffix
            bc["candidate_mismatches"] += candidate_block(pair["candidates"]) not in pair["suffix"]
            bc["state_payload_differences"] += pair["hml_state"] != pair["neutral_state"]
            bc["unexpected_differences"] += not (
                pair["hml_prompt"] == PREFIX + pair["hml_state"] + pair["suffix"]
                and pair["neutral_prompt"] == PREFIX + pair["neutral_state"] + pair["suffix"]
            )

            source = canon[pair["record_id"]]
            canonical_state = source["neutral_transition"]["state_before"]
            parsed_hml = export_state(parse_state(pair["hml_state"]))
            parsed_neutral = json.loads(pair["neutral_state"])
            sc["pairs"] += 1
            sc["hml_parse_failures"] += parsed_hml != canonical_state
            sc["neutral_parse_failures"] += parsed_neutral != canonical_state
            sc["cross_view_semantic_mismatches"] += parsed_hml != parsed_neutral
            claim = canonical_state["claims"]["p0"]
            sc["identifier_mismatches"] += parsed_hml["claims"]["p0"]["id"] != claim["id"]
            sc["mathematical_content_mismatches"] += parsed_hml["claims"]["p0"]["proposition"] != claim["proposition"]
            sc["status_mismatches"] += parsed_hml["claims"]["p0"]["status"] != claim["status"]
            sc["scope_mismatches"] += parsed_hml["active_scopes"] != canonical_state["active_scopes"]
            sc["extra_or_missing_facts"] += set(parsed_hml["claims"]) != set(canonical_state["claims"])
            sc["future_or_gold_fields"] += any(key in pair["hml_prompt"] or key in pair["neutral_prompt"] for key in ("state_after", "gold_candidate_id", "selected_action", "warrant", "verdict"))

            for arm in ARMS:
                state = pair[f"{arm}_state"]
                prompt = pair[f"{arm}_prompt"]
                raw_prompt = tokenizer.encode(prompt, add_special_tokens=False)
                chat = tokenizer.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True, tokenize=False, enable_thinking=False)
                chat_tokens = tokenizer.encode(chat)
                full = tokenizer.apply_chat_template([{"role": "user", "content": prompt}, {"role": "assistant", "content": pair["target"]}], return_dict=False)
                token_values[arm]["state_chars"].append(len(state))
                token_values[arm]["state_bytes"].append(len(state.encode()))
                token_values[arm]["state_tokens"].append(len(tokenizer.encode(state, add_special_tokens=False)))
                token_values[arm]["prompt_chars"].append(len(prompt))
                token_values[arm]["prompt_bytes"].append(len(prompt.encode()))
                token_values[arm]["prompt_tokens"].append(len(raw_prompt))
                token_values[arm]["chat_prompt_tokens"].append(len(chat_tokens))
                token_values[arm]["full_train_tokens"].append(len(full))
                overflow[arm] += len(full) > MAXSEQ
            if split == "train":
                train_ids.add(pair["record_id"]); train_parents.add(pair["parent_id"])
            if split == "final":
                final_ids.add(pair["record_id"]); final_parents.add(pair["parent_id"])
        byte_splits[split] = dict(bc); semantic_splits[split] = dict(sc)
        byte_total.update(bc); semantic_total.update(sc)

    required_byte_zero = ("prefix_mismatches", "suffix_mismatches", "candidate_mismatches", "target_mismatches",
                          "record_id_mismatches", "parent_id_mismatches", "semantic_source_mismatches", "unexpected_differences")
    byte_result = {
        "result": "PASS" if all(byte_total[key] == 0 for key in required_byte_zero) else "FAIL",
        "total_pairs": byte_total["pairs"], "splits": byte_splits, "totals": dict(byte_total),
        "only_permitted_difference": "bytes inside <STATE>...</STATE>",
    }
    required_semantic_zero = tuple(key for key in semantic_total if key != "pairs")
    semantic_result = {
        "result": "PASS" if all(semantic_total[key] == 0 for key in required_semantic_zero) else "FAIL",
        "total_pairs": semantic_total["pairs"], "splits": semantic_splits, "totals": dict(semantic_total),
        "parser_authority": HML_AUTHORITY,
        "parser_worktree_head": git(HML_SOURCE, "rev-parse", "HEAD"),
        "semantic_state_diff_from_authority": git(HML_SOURCE, "diff", "--name-only", f"{HML_AUTHORITY}..HEAD", "--", "src/hamiltonian_lang/semantic_state"),
    }
    token_result = {
        "result": "PASS" if not any(overflow.values()) else "FAIL", "maxseq": MAXSEQ,
        "pairs": 16_000, "arms": {arm: {key: stats(values) for key, values in fields.items()} for arm, fields in token_values.items()},
        "overflow_counts": overflow,
        "mean_state_token_ratio_hml_over_neutral": statistics.fmean(token_values["hml"]["state_tokens"]) / statistics.fmean(token_values["neutral"]["state_tokens"]),
        "mean_chat_prompt_token_ratio_hml_over_neutral": statistics.fmean(token_values["hml"]["chat_prompt_tokens"]) / statistics.fmean(token_values["neutral"]["chat_prompt_tokens"]),
        "train_final_record_overlap": len(train_ids & final_ids), "train_final_parent_overlap": len(train_parents & final_parents),
    }
    write_json(audits_dir / "envelope_byte_diff.json", byte_result, exclusive=False)
    write_json(audits_dir / "state_semantic_parity.json", semantic_result, exclusive=False)
    write_json(audits_dir / "token_audit.json", token_result, exclusive=False)
    assert byte_result["result"] == semantic_result["result"] == token_result["result"] == "PASS"
    assert token_result["train_final_record_overlap"] == token_result["train_final_parent_overlap"] == 0
    return {"byte": byte_result, "semantic": semantic_result, "token": token_result}


def prepare() -> None:
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)
    for arm in ARMS:
        destination = ART / "prepared" / arm
        manifest_path = destination / "dataset_manifest.json"
        if manifest_path.exists():
            continue
        destination.mkdir(parents=True, exist_ok=True)

        def convert(split: str, limit: int | None = None) -> tuple[list[dict], dict]:
            hrows, nrows = load_split(split)
            source = hrows if arm == "hml" else nrows
            other = nrows if arm == "hml" else hrows
            converted = []
            prompt_tokens = full_tokens = supervised = 0
            for row, paired in zip(source, other):
                pair = paired_projection(row, paired) if arm == "hml" else paired_projection(paired, row)
                prompt = pair[f"{arm}_prompt"]
                messages = [{"role": "user", "content": prompt}, {"role": "assistant", "content": pair["target"]}]
                full = tokenizer.apply_chat_template(messages, return_dict=False)
                offset = len(tokenizer.apply_chat_template(messages[:-1], add_generation_prompt=True, return_dict=False))
                assert len(full) <= MAXSEQ and offset < len(full)
                converted.append({"record_id": pair["record_id"], "prompt": prompt, "completion": pair["target"], "tokens": len(full)})
                prompt_tokens += offset; full_tokens += len(full); supervised += len(full) - offset
                if limit and len(converted) >= limit:
                    break
            # Identical record order makes the seeded minibatch sequence paired
            # across arms; representation length must not alter example order.
            converted.sort(key=lambda item: item["record_id"])
            return converted, {"rows": len(converted), "prompt_tokens": prompt_tokens, "full_tokens": full_tokens,
                               "supervised_suffix_tokens": supervised, "max_full_tokens": max(item["tokens"] for item in converted)}

        train, train_stats = convert("train")
        valid, valid_stats = convert("dev", 64)
        for name, values in (("train", train), ("valid", valid)):
            with (destination / f"{name}.jsonl").open("x", encoding="utf-8") as stream:
                for item in values:
                    stream.write(json.dumps({"prompt": item["prompt"], "completion": item["completion"]}, ensure_ascii=False) + "\n")
        write_json(manifest_path, {
            "arm": arm, "train": train_stats, "valid": valid_stats,
            "train_sha256": sha(destination / "train.jsonl"), "valid_sha256": sha(destination / "valid.jsonl"),
        })


def manifest() -> None:
    output = HERE / "RUN_MANIFEST.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    inventory = {}
    params = 0
    dtypes = collections.Counter()
    for shard in sorted(MODEL.glob("model-*.safetensors")):
        with safe_open(shard, framework="numpy") as source:
            for key in source.keys():
                tensor = source.get_slice(key)
                params += math.prod(tensor.get_shape())
                dtypes[str(tensor.get_dtype())] += 1
    inventory = {"parameter_count": params, "tensor_dtypes": dict(dtypes), "quantization_config": json.loads((MODEL / "config.json").read_text()).get("quantization_config")}
    candidate_signature = "\\n.join(f\"{candidate_id}: {raw_tactic_text}\" for candidates C0..C5 in frozen order)"
    renderer_source = HML_SOURCE / "src/hamiltonian_lang/semantic_state/view.py"
    value = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "pre_protocol_parent_sha": git(REPO, "rev-parse", "HEAD"),
        "branch": git(REPO, "branch", "--show-current"), "corpus_commit": git(CORPUS_REPO, "rev-parse", "HEAD"),
        "expected_corpus_commit": CORPUS_COMMIT, "payload_commit": PAYLOAD_COMMIT, "rung_record_ids_sha256": sha(CORPUS / "rungs/10k/record_ids.json"),
        "expected_rung_sha256": RUNG_HASH, "model_id": "Qwen/Qwen3-8B", "model_revision": MODEL_REV,
        "model_snapshot_sha256": model_hash(), "model_inventory": inventory,
        "tokenizer_sha256": sha(MODEL / "tokenizer.json"),
        "renderers": {"hml_authority": HML_AUTHORITY, "hml_renderer_source_sha256": sha(renderer_source),
                      "neutral_renderer": "RFC8259 canonical JSON, ensure_ascii=false, sort_keys=true, compact separators",
                      "neutral_renderer_sha256": digest_text("json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))")},
        "envelope_template_sha256": digest_text(PREFIX + "{STATE_SERIALIZATION}" + SUFFIX_HEAD + "{CANDIDATE_BLOCK}" + SUFFIX_TAIL),
        "candidate_formatter_sha256": digest_text(candidate_signature),
        "training_recipe_sha256": sha(RECIPE), "evaluation_code_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(HERE / "COMMON_ENVELOPE_PROTOCOL.md"),
        "prepared_data": {arm: json.loads((ART / "prepared" / arm / "dataset_manifest.json").read_text()) for arm in ARMS},
        "audits": {name: sha(HERE / "audits" / name) for name in ("envelope_byte_diff.json", "state_semantic_parity.json", "token_audit.json")},
        "stack": subprocess.check_output([str(PYTHON), "-c", "import importlib.metadata as m; print('mlx='+m.version('mlx')); print('mlx-lm='+m.version('mlx-lm')); print('transformers='+m.version('transformers'))"], text=True).splitlines(),
        "hardware": {"platform": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count()},
    }
    assert value["corpus_commit"] == CORPUS_COMMIT and value["rung_record_ids_sha256"] == RUNG_HASH
    assert inventory["tensor_dtypes"] == {"BF16": 399} and inventory["quantization_config"] is None
    write_json(output, value)


def train(arm: str, seed: int) -> None:
    cell = ART / "train" / arm / f"seed_{seed}"
    adapter = cell / "adapter"
    result_path = HERE / "diagnostics" / f"train_{arm}_seed{seed}.json"
    log_path = HERE / "diagnostics" / f"train_{arm}_seed{seed}.log"
    telemetry_path = HERE / "diagnostics" / f"train_{arm}_seed{seed}_telemetry.jsonl"
    if result_path.exists():
        print(result_path)
        return
    cell.mkdir(parents=True, exist_ok=True); log_path.parent.mkdir(parents=True, exist_ok=True)
    assert not adapter.exists() and not log_path.exists() and not telemetry_path.exists()
    command = [str(PYTHON), "-m", "mlx_lm", "lora", "--model", str(MODEL), "--train",
               "--data", str(ART / "prepared" / arm), "-c", str(RECIPE), "--batch-size", "2",
               "--iters", "5000", "--learning-rate", "1e-4", "--max-seq-length", str(MAXSEQ),
               "--grad-checkpoint", "--steps-per-report", "100", "--steps-per-eval", "100000",
               "--val-batches", "1", "--adapter-path", str(adapter), "--save-every", "100", "--seed", str(seed)]
    started = time.time(); swap_start = swap_mb()
    with log_path.open("x", encoding="utf-8") as log, telemetry_path.open("x", encoding="utf-8") as telemetry:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, text=True)
        while process.poll() is None:
            telemetry.write(json.dumps(memory_snapshot(), separators=(",", ":")) + "\n"); telemetry.flush()
            try:
                process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                pass
        returncode = process.returncode
        telemetry.write(json.dumps(memory_snapshot(), separators=(",", ":")) + "\n")
    wall = time.time() - started
    text = log_path.read_text(errors="replace")
    losses = [float(x) for x in re.findall(r"Train loss ([0-9.]+)", text)]
    val = [float(x) for x in re.findall(r"Iter 1: Val loss ([0-9.]+)", text)]
    iterations = [int(x) for x in re.findall(r"Iter ([0-9]+): Train loss", text)]
    rates = [float(x) for x in re.findall(r"Tokens/sec ([0-9.]+)", text)]
    peaks = [float(x) for x in re.findall(r"Peak mem ([0-9.]+) GB", text)]
    trained = [int(x) for x in re.findall(r"Trained Tokens ([0-9]+)", text)]
    telemetry = [json.loads(line) for line in telemetry_path.read_text().splitlines()]
    passed = returncode == 0 and iterations[-1] == 5000 and len(losses) == 50 and all(math.isfinite(x) for x in losses) and (adapter / "adapters.safetensors").exists()
    result = {
        "result": "PASS" if passed else "FAIL", "arm": arm, "seed": seed, "command": command,
        "protocol_commit": git(REPO, "rev-parse", "HEAD"), "base_model_revision": MODEL_REV,
        "base_model_sha256": json.loads((HERE / "RUN_MANIFEST.json").read_text())["model_snapshot_sha256"],
        "config_sha256": sha(RECIPE), "dataset_manifest_sha256": sha(ART / "prepared" / arm / "dataset_manifest.json"),
        "initial_validation_loss": val[0] if val else None, "first_training_loss": losses[0] if losses else None,
        "final_training_loss": losses[-1] if losses else None, "loss_checkpoints": losses,
        "iterations": iterations[-1] if iterations else None, "examples_seen": 10_000,
        "reported_tokens_seen": trained[-1] if trained else None, "mean_reported_tokens_per_second": statistics.fmean(rates) if rates else None,
        "peak_mlx_gb": max(peaks) if peaks else None, "swap_start_mb": swap_start, "swap_end_mb": swap_mb(),
        "swap_delta_mb": swap_mb() - swap_start, "minimum_free_gib": min(item["free_gib"] for item in telemetry),
        "maximum_compressed_gib": max(item["compressed_gib"] for item in telemetry), "wall_seconds": wall,
        "adapter_path": str(adapter), "adapter_sha256": sha(adapter / "adapters.safetensors") if (adapter / "adapters.safetensors").exists() else None,
        "returncode": returncode, "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(result_path, result)
    if not passed:
        raise SystemExit(f"training failed: {log_path}")


def canonical_metadata() -> dict[str, dict]:
    result = {}
    for row in read_rows(CORPUS / "canonical/records.jsonl.gz"):
        if row["split"] != "final":
            continue
        candidates = row["candidate_audit"]["candidates"]
        gold_id = row["candidate_audit"]["gold_candidate_id"]
        gold = next(item for item in candidates if item["candidate_id"] == gold_id)
        state = row["neutral_transition"]["state_before"]["claims"]["p0"]["proposition"]
        state_tokens = set(TOKEN_RE.findall(state.lower()))
        overlaps = []
        for candidate in candidates:
            candidate_tokens = set(TOKEN_RE.findall(candidate["tactic_text"].lower()))
            union = state_tokens | candidate_tokens
            overlaps.append(len(state_tokens & candidate_tokens) / len(union) if union else 0.0)
        lexical = max(range(6), key=lambda index: overlaps[index])
        result[row["record_id"]] = {
            "depth": row["depth"], "depth_bin": row["depth_bin"], "complexity": COMPLEXITY_MAP[row["complexity_bin"]],
            "domain": row["neutral_transition"]["state_before"]["claims"]["p0"]["domain"],
            "statistics_probability": row["probability_statistics_related"], "lexical_correct": candidates[lexical]["candidate_id"] == gold_id,
            "tactic_family": gold["tactic_text"].strip().split(maxsplit=1)[0] if gold["tactic_text"].strip() else "<EMPTY>",
            "trajectory_step_index": row["trajectory_step_index"], "proof_length": row["proof_length"],
        }
    assert len(result) == 3_000
    return result


def score(arm: str, seed: int) -> None:
    output = HERE / "raw" / f"{arm}_seed{seed}_predictions.jsonl"
    summary_path = HERE / "diagnostics" / f"score_{arm}_seed{seed}.json"
    if output.exists() and summary_path.exists():
        print(output)
        return
    assert not output.exists() and not summary_path.exists()
    output.parent.mkdir(parents=True, exist_ok=True); summary_path.parent.mkdir(parents=True, exist_ok=True)
    result = json.loads((HERE / "diagnostics" / f"train_{arm}_seed{seed}.json").read_text())
    adapter = result["adapter_path"]
    hrows, nrows = load_split("final")
    projections = [paired_projection(h, n) for h, n in zip(hrows, nrows)]
    meta = canonical_metadata()
    model, tokenizer = load(str(MODEL), adapter_path=adapter); model.eval()
    label_tokens = [tokenizer.encode(f"C{i}", add_special_tokens=False) for i in range(6)]
    assert all(len(item) == 2 for item in label_tokens) and len({item[0] for item in label_tokens}) == 1
    shared = label_tokens[0][0]
    temporary = output.with_suffix(".jsonl.partial")
    assert not temporary.exists()
    started = time.time(); correct = 0; mrr = nll = entropy = margin = 0.0; prompt_lengths = []
    with temporary.open("x", encoding="utf-8") as stream:
        for index, pair in enumerate(projections, 1):
            prompt = pair[f"{arm}_prompt"]
            chat = tokenizer.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True, tokenize=False, enable_thinking=False)
            prompt_ids = tokenizer.encode(chat)
            cache = make_prompt_cache(model)
            logits = model(mx.array([prompt_ids]), cache=cache)
            first = nn.log_softmax(logits[:, -1, :].astype(mx.float32), axis=-1)[0, shared]
            digits = model(mx.array([[shared]]), cache=cache)
            digit_lp = nn.log_softmax(digits[:, -1, :].astype(mx.float32), axis=-1)[0]
            sums = [float(first + digit_lp[item[1]]) for item in label_tokens]
            means = [value / 2 for value in sums]
            order = sorted(range(6), key=lambda item: -means[item])
            gold = int(pair["target"][1:])
            probs = np.exp(np.asarray(means) - max(means)); probs = probs / probs.sum()
            best_other = max(means[item] for item in range(6) if item != gold)
            row_meta = meta[pair["record_id"]]
            item = {
                "record_id": pair["record_id"], "parent_id": pair["parent_id"], "answer_index": gold,
                "scores_sum": sums, "scores_mean": means, "candidate_probabilities": probs.tolist(),
                "pred_index": order[0], "rank": order.index(gold) + 1, "correct": order[0] == gold,
                "nll": -math.log(max(float(probs[gold]), 1e-12)),
                "entropy": -sum(float(value) * math.log(max(float(value), 1e-12)) for value in probs),
                "gold_margin": means[gold] - best_other, "prompt_tokens": len(prompt_ids),
                "prompt_sha256": digest_text(prompt), "state_sha256": digest_text(pair[f"{arm}_state"]),
                "candidate_sha256": [digest_text(candidate["tactic_text"]) for candidate in pair["candidates"]], **row_meta,
            }
            stream.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
            correct += item["correct"]; mrr += 1 / item["rank"]; nll += item["nll"]; entropy += item["entropy"]; margin += item["gold_margin"]
            prompt_lengths.append(len(prompt_ids))
            if index % 100 == 0:
                print(f"{index}/3000 {time.time()-started:.1f}s", flush=True)
            del cache, logits, digits
            mx.clear_cache()
    temporary.rename(output)
    n = len(projections)
    write_json(summary_path, {
        "arm": arm, "seed": seed, "n": n, "top1": correct / n, "mrr": mrr / n, "nll": nll / n,
        "entropy": entropy / n, "gold_margin": margin / n, "mean_prompt_tokens": statistics.fmean(prompt_lengths),
        "wall_seconds": time.time() - started, "peak_mlx_gib": mx.get_peak_memory() / 2**30,
        "adapter_path": adapter, "adapter_sha256": result["adapter_sha256"], "base_revision": MODEL_REV,
        "raw_sha256": sha(output), "thinking_enabled": False,
    })


def load_scores(arm: str, seed: int) -> dict[str, dict]:
    path = HERE / "raw" / f"{arm}_seed{seed}_predictions.jsonl"
    return {row["record_id"]: row for row in (json.loads(line) for line in path.read_text().splitlines())}


def cluster_bootstrap(deltas: list[float], parents: list[str], offset: int = 0) -> dict:
    grouped = collections.defaultdict(list)
    for index, parent in enumerate(parents):
        grouped[parent].append(index)
    groups = [np.asarray(grouped[key], dtype=int) for key in sorted(grouped)]
    values = np.asarray(deltas, dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED + offset)
    draws = np.empty(BOOTSTRAPS)
    for draw in range(BOOTSTRAPS):
        selected = rng.integers(0, len(groups), len(groups))
        indices = np.concatenate([groups[item] for item in selected])
        draws[draw] = values[indices].mean()
    return {"delta": float(values.mean()), "ci95": [float(x) for x in np.percentile(draws, (2.5, 97.5))],
            "p_gt_zero": float(np.mean(draws > 0)), "parents": len(groups), "n": len(values)}


def subset(ids: list[str], hml: dict[str, dict], neutral: dict[str, dict], offset: int = 0) -> dict:
    result = {"n": len(ids), "parents": len({hml[rid]["parent_id"] for rid in ids})}
    for metric in ("top1", "mrr", "nll", "entropy", "gold_margin"):
        if metric == "top1":
            hv = [float(hml[rid]["correct"]) for rid in ids]; nv = [float(neutral[rid]["correct"]) for rid in ids]
        elif metric == "mrr":
            hv = [float(hml[rid].get("reciprocal_rank", 1 / hml[rid]["rank"])) for rid in ids]
            nv = [float(neutral[rid].get("reciprocal_rank", 1 / neutral[rid]["rank"])) for rid in ids]
        else:
            hv = [float(hml[rid][metric]) for rid in ids]; nv = [float(neutral[rid][metric]) for rid in ids]
        result[metric] = {"hml": statistics.fmean(hv), "neutral": statistics.fmean(nv),
                          **cluster_bootstrap([a - b for a, b in zip(hv, nv)], [hml[rid]["parent_id"] for rid in ids], offset)}
    return result


def combine(seeds: list[int]) -> tuple[dict[str, dict], dict[str, dict], dict]:
    raw = {arm: [load_scores(arm, seed) for seed in seeds] for arm in ARMS}
    ids = sorted(set.intersection(*(set(item) for values in raw.values() for item in values)))
    per_seed = {}
    for index, seed in enumerate(seeds):
        per_seed[str(seed)] = subset(ids, raw["hml"][index], raw["neutral"][index], index)
    combined = {arm: {} for arm in ARMS}
    for arm in ARMS:
        for rid in ids:
            template = dict(raw[arm][0][rid])
            template["correct"] = statistics.fmean(float(value[rid]["correct"]) for value in raw[arm])
            template["rank"] = statistics.fmean(value[rid]["rank"] for value in raw[arm])
            template["reciprocal_rank"] = statistics.fmean(1 / value[rid]["rank"] for value in raw[arm])
            for metric in ("nll", "entropy", "gold_margin"):
                template[metric] = statistics.fmean(value[rid][metric] for value in raw[arm])
            template["scores_mean"] = [statistics.fmean(value[rid]["scores_mean"][i] for value in raw[arm]) for i in range(6)]
            template["pred_index"] = max(range(6), key=lambda i: template["scores_mean"][i])
            combined[arm][rid] = template
    return combined["hml"], combined["neutral"], per_seed


def failure_analysis(hml: dict[str, dict], neutral: dict[str, dict], ids: list[str]) -> None:
    old = {(arm, seed): {row["record_id"]: row for row in json.loads((OLD_EXP / "raw_predictions" / f"10k_{arm}_s{seed}.json").read_text())["rows"]}
           for arm in ARMS for seed in (1, 2)}
    changed = {arm: [] for arm in ARMS}
    for arm, current in (("hml", hml), ("neutral", neutral)):
        for rid in ids:
            old_scores = [statistics.fmean(old[(arm, seed)][rid]["scores_mean"][i] for seed in (1, 2)) for i in range(6)]
            old_pred = max(range(6), key=lambda i: old_scores[i])
            if old_pred != current[rid]["pred_index"]:
                changed[arm].append(rid)
    def aggregate(rows_: list[str]) -> dict:
        return {
            "n": len(rows_), "depth": dict(collections.Counter(hml[rid]["depth_bin"] for rid in rows_)),
            "complexity": dict(collections.Counter(hml[rid]["complexity"] for rid in rows_)),
            "tactic_family_top20": collections.Counter(hml[rid]["tactic_family"] for rid in rows_).most_common(20),
            "gold_position": dict(collections.Counter(hml[rid]["answer_index"] for rid in rows_)),
            "lexical_correct": sum(hml[rid]["lexical_correct"] for rid in rows_),
            "mean_hml_tokens": statistics.fmean(hml[rid]["prompt_tokens"] for rid in rows_) if rows_ else None,
            "mean_neutral_tokens": statistics.fmean(neutral[rid]["prompt_tokens"] for rid in rows_) if rows_ else None,
        }
    h_regress = sorted(ids, key=lambda rid: (float(hml[rid]["correct"]) - statistics.fmean(float(old[("hml", seed)][rid]["correct"]) for seed in (1, 2)), rid))[:25]
    n_improve = sorted(ids, key=lambda rid: -(float(neutral[rid]["correct"]) - statistics.fmean(float(old[("neutral", seed)][rid]["correct"]) for seed in (1, 2))))[:25]
    path = HERE / "diagnostics/failure_analysis.md"
    content = ["# Common-envelope failure analysis", "", "Generated automatically because delta < +15pp.", "",
               f"- HML predictions changed: {len(changed['hml'])}", f"- Neutral predictions changed: {len(changed['neutral'])}", "",
               "## Changed-row aggregates", "", "```json", json.dumps({arm: aggregate(values) for arm, values in changed.items()}, indent=2), "```", "",
               "## Deterministic diagnostic samples", "", f"Largest HML regressions: `{h_regress}`", "", f"Largest Neutral improvements: `{n_improve}`", ""]
    path.write_text("\n".join(content))


def analyse(seeds: list[int]) -> dict:
    output = HERE / "diagnostics" / ("analysis_seed1.json" if seeds == [1] else "analysis_two_seed.json")
    if output.exists():
        return json.loads(output.read_text())
    hml, neutral, per_seed = combine(seeds)
    ids = sorted(hml); assert len(ids) == 3_000
    overall = subset(ids, hml, neutral)
    strata = {
        "depth": {name: subset([rid for rid in ids if hml[rid]["depth_bin"] == name], hml, neutral, 100 + i) for i, name in enumerate(DEPTH_ORDER)},
        "complexity": {name: subset([rid for rid in ids if hml[rid]["complexity"] == name], hml, neutral, 200 + i) for i, name in enumerate(("LOW", "MEDIUM", "HIGH", "VERY_HIGH"))},
        "lexical_correct": subset([rid for rid in ids if hml[rid]["lexical_correct"]], hml, neutral, 300),
        "lexical_failure": subset([rid for rid in ids if not hml[rid]["lexical_correct"]], hml, neutral, 301),
        "statistics_probability": subset([rid for rid in ids if hml[rid]["statistics_probability"]], hml, neutral, 302),
    }
    h_only = sum(float(hml[rid]["correct"]) > float(neutral[rid]["correct"]) for rid in ids)
    n_only = sum(float(hml[rid]["correct"]) < float(neutral[rid]["correct"]) for rid in ids)
    mcnemar = binomtest(h_only, h_only + n_only, .5).pvalue if len(seeds) == 1 and h_only + n_only else None
    delta = overall["top1"]["delta"]
    if len(seeds) == 1:
        if delta <= 0:
            gate = "STOP_FAILED"
        elif delta < .05 and not (overall["top1"]["ci95"][0] > 0 or (mcnemar is not None and mcnemar < .05)):
            gate = "STOP_WEAK"
        else:
            gate = "RUN_SEED2"
    else:
        gate = "COMPLETE"
    result = {"seeds": seeds, "overall": overall, "per_seed": per_seed, "strata": strata,
              "mcnemar": {"hml_only": h_only, "neutral_only": n_only, "p": mcnemar}, "gate": gate}
    write_json(output, result)
    if len(seeds) == 2:
        old_h, old_n, old_delta = .8575, .5020, .3555
        result["comparison_previous"] = {"old_hml": old_h, "old_neutral": old_n, "old_delta": old_delta,
                                         "new_hml": overall["top1"]["hml"], "new_neutral": overall["top1"]["neutral"],
                                         "new_delta": delta, "hml_change": overall["top1"]["hml"] - old_h,
                                         "neutral_change": overall["top1"]["neutral"] - old_n,
                                         "delta_retained_fraction": delta / old_delta}
        write_json(output, result, exclusive=False)
        paired_diagnostics(hml, neutral, ids, seeds, result)
        if delta < .15:
            failure_analysis(hml, neutral, ids)
    return result


def paired_diagnostics(hml: dict[str, dict], neutral: dict[str, dict], ids: list[str], seeds: list[int], analysis: dict) -> None:
    output = HERE / "diagnostics/paired_final_diagnostics.jsonl"
    summary_path = HERE / "diagnostics/disagreement_summary.json"
    if output.exists() or summary_path.exists():
        raise SystemExit("refusing to overwrite paired diagnostics")
    raw = {(arm, seed): load_scores(arm, seed) for arm in ARMS for seed in seeds}
    categories = collections.Counter(); token_deltas = []; row_deltas = []
    with output.open("x", encoding="utf-8") as stream:
        for rid in ids:
            h_correct = hml[rid]["pred_index"] == hml[rid]["answer_index"]
            n_correct = neutral[rid]["pred_index"] == neutral[rid]["answer_index"]
            category = "BOTH_CORRECT" if h_correct and n_correct else "HML_ONLY" if h_correct else "NEUTRAL_ONLY" if n_correct else "BOTH_WRONG"
            categories[category] += 1
            token_delta = hml[rid]["prompt_tokens"] - neutral[rid]["prompt_tokens"]
            correctness_delta = int(h_correct) - int(n_correct)
            token_deltas.append(token_delta); row_deltas.append(correctness_delta)
            item = {
                "record_id": rid, "parent_id": hml[rid]["parent_id"], "depth": hml[rid]["depth"],
                "complexity": hml[rid]["complexity"], "domain": hml[rid]["domain"],
                "lexical_heuristic_correct": hml[rid]["lexical_correct"], "gold_index": hml[rid]["answer_index"],
                "hml_prompt_hash": hml[rid]["prompt_sha256"], "neutral_prompt_hash": neutral[rid]["prompt_sha256"],
                "hml_state_hash": hml[rid]["state_sha256"], "neutral_state_hash": neutral[rid]["state_sha256"],
                "hml_prompt_tokens": hml[rid]["prompt_tokens"], "neutral_prompt_tokens": neutral[rid]["prompt_tokens"],
                "candidate_hashes": hml[rid]["candidate_sha256"],
                "hml_scores_by_seed": {str(seed): raw[("hml", seed)][rid]["scores_mean"] for seed in seeds},
                "neutral_scores_by_seed": {str(seed): raw[("neutral", seed)][rid]["scores_mean"] for seed in seeds},
                "hml_prediction": hml[rid]["pred_index"], "neutral_prediction": neutral[rid]["pred_index"],
                "hml_correct": h_correct, "neutral_correct": n_correct, "disagreement_category": category,
            }
            stream.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
    correlation = pearsonr(token_deltas, row_deltas)
    position = {str(i): subset([rid for rid in ids if hml[rid]["answer_index"] == i], hml, neutral, 400 + i)["top1"] for i in range(6)}
    families = collections.defaultdict(list)
    for rid in ids: families[hml[rid]["tactic_family"]].append(rid)
    family_summary = []
    for family, values in families.items():
        hv = [float(hml[rid]["correct"]) for rid in values]
        nv = [float(neutral[rid]["correct"]) for rid in values]
        family_summary.append({"family": family, "n": len(values), "hml": statistics.fmean(hv),
                               "neutral": statistics.fmean(nv),
                               "delta": statistics.fmean(a - b for a, b in zip(hv, nv))})
    family_summary.sort(key=lambda item: -item["n"])
    write_json(summary_path, {
        "seeds": seeds, "categories": dict(categories), "token_length_vs_correctness_delta": {"pearson_r": float(correlation.statistic), "p": float(correlation.pvalue)},
        "gold_position": position, "tactic_families_top20": family_summary[:20], "depth": analysis["strata"]["depth"],
        "complexity": analysis["strata"]["complexity"], "comparison_previous": analysis.get("comparison_previous"),
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit"); sub.add_parser("prepare"); sub.add_parser("manifest")
    tr = sub.add_parser("train"); tr.add_argument("--arm", choices=ARMS, required=True); tr.add_argument("--seed", type=int, required=True)
    sc = sub.add_parser("score"); sc.add_argument("--arm", choices=ARMS, required=True); sc.add_argument("--seed", type=int, required=True)
    an = sub.add_parser("analyse"); an.add_argument("--seeds", nargs="+", type=int, required=True)
    args = parser.parse_args()
    if args.command == "audit": run_audits()
    elif args.command == "prepare": prepare()
    elif args.command == "manifest": manifest()
    elif args.command == "train": train(args.arm, args.seed)
    elif args.command == "score": score(args.arm, args.seed)
    else: analyse(args.seeds)


if __name__ == "__main__":
    main()
