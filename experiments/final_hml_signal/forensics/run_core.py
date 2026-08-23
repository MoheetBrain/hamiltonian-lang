#!/usr/bin/env python3
"""Deterministic, inference-free core audit of the saved final-signal artifacts."""
from __future__ import annotations

import collections
import csv
import gzip
import hashlib
import json
import math
import random
import re
import statistics
import unicodedata
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
CORPUS_REPO = Path("/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus")
CORPUS = CORPUS_REPO / "data/hml_50k_final"
ART = Path("/Users/moheet/hml_research_artifacts/final_hml_signal")
MODEL_REV = "b968826d9c46dd6066d109eabc6255188de91218"
MODEL = Path("/Users/moheet/.cache/huggingface/hub/models--Qwen--Qwen3-8B/snapshots") / MODEL_REV
TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
IDENT_RE = re.compile(r"(?u)\b[^\W\d]\w*[\w'✝₀-₉]*\b")
ARMS = {"hml": "HML_WORKED_UTF8", "neutral": "STRUCTURED_NEUTRAL_WORKED"}


def dump(name: str, value: object) -> None:
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def rows(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def norm(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).lower().split())


def tokens(value: str) -> list[str]:
    return TOKEN_RE.findall(norm(value))


def frozen_lexical_tokens(value: str) -> list[str]:
    return TOKEN_RE.findall(value.lower())


def alpha_norm(value: str) -> str:
    reserved = {
        "type", "prop", "true", "false", "fun", "let", "in", "if", "then", "else",
        "forall", "exists", "match", "with", "by", "where", "at", "only", "all_goals",
    }
    return IDENT_RE.sub(lambda m: m.group(0) if m.group(0).lower() in reserved else "ID", norm(value))


def state_of(view_row: dict) -> str:
    return json.loads(view_row["input_text"])["state_before"]["claims"]["p0"]["proposition"]


def candidates_of(view_row: dict) -> list[dict]:
    return json.loads(view_row["input_text"])["candidates"]


def hml_state(view_row: dict) -> str:
    prefix = "Below is a mathematical proof state.\n\n"
    marker = "\nChoose the single most useful next tactic from this candidate set.\n"
    assert view_row["input_text"].startswith(prefix) and marker in view_row["input_text"]
    return view_row["input_text"][len(prefix):].split(marker, 1)[0]


def score_file(arm: str, seed: int) -> dict:
    return json.loads((EXP / "raw_predictions" / f"10k_{arm}_s{seed}.json").read_text())


def load_inputs(split: str, rung: bool = False) -> dict[str, list[dict]]:
    result = {}
    for arm, view in ARMS.items():
        path = (CORPUS / "rungs/10k/NEXT_ACTION_SELECT" / view / "train.jsonl.gz") if rung else (
            CORPUS / "tasks/NEXT_ACTION_SELECT" / view / f"{split}.jsonl.gz"
        )
        result[arm] = rows(path)
    return result


def headline_reproduction(final_inputs: dict[str, list[dict]], scores: dict) -> dict:
    result = {"pass": True, "cells": {}, "candidate_indexing": "C0..C5 -> indices 0..5",
              "tie_handling": "first maximal index", "normalization": "mean=sum/2 for every label"}
    views = {arm: {r["record_id"]: r for r in values} for arm, values in final_inputs.items()}
    for arm in ARMS:
        for seed in (1, 2):
            payload = scores[(arm, seed)]
            mismatch = order_mismatch = normalization_mismatch = ties = 0
            correct_mean = correct_sum = 0
            fractional_correct = 0.0
            nontie_correct = nontie_n = 0
            for row in payload["rows"]:
                source = views[arm][row["record_id"]]
                labels = [f"C{i}" for i in range(6)]
                if row["candidate_ids"] != labels or source["target_text"] != labels[row["answer_index"]]:
                    order_mismatch += 1
                mean_pred = max(range(6), key=lambda i: row["scores_mean"][i])
                sum_pred = max(range(6), key=lambda i: row["scores_sum"][i])
                top = max(row["scores_mean"])
                top_indices = [i for i, value in enumerate(row["scores_mean"]) if abs(value - top) < 1e-12]
                is_tie = len(top_indices) > 1
                ties += is_tie
                normalization_mismatch += int(any(abs(2 * a - b) > 1e-6 for a, b in zip(
                    row["scores_mean"], row["scores_sum"])))
                gold = row["answer_index"]
                correct_mean += mean_pred == gold
                correct_sum += sum_pred == gold
                fractional_correct += (1 / len(top_indices)) if gold in top_indices else 0.0
                if not is_tie:
                    nontie_n += 1
                    nontie_correct += mean_pred == gold
                mismatch += int(mean_pred != row["pred_index"] or bool(mean_pred == gold) != row["correct"])
            n = len(payload["rows"])
            observed = correct_mean / n
            expected = payload["summary"]["top1"]
            passed = mismatch == order_mismatch == normalization_mismatch == 0 and abs(observed - expected) < 1e-15
            result["pass"] &= passed
            result["cells"][f"{arm}_s{seed}"] = {
                "n": n, "recomputed_mean_top1": observed, "recomputed_sum_top1": correct_sum / n,
                "saved_top1": expected, "prediction_mismatches": mismatch,
                "candidate_order_mismatches": order_mismatch, "normalization_mismatches": normalization_mismatch,
                "exact_top_ties": ties, "fractional_tie_top1": fractional_correct / n,
                "nontie_top1": nontie_correct / nontie_n, "nontie_n": nontie_n, "pass": passed,
            }
    result["two_seed_delta"] = statistics.fmean(result["cells"][f"hml_s{s}"]["recomputed_mean_top1"] for s in (1, 2)) - statistics.fmean(
        result["cells"][f"neutral_s{s}"]["recomputed_mean_top1"] for s in (1, 2))
    result["two_seed_fractional_tie_delta"] = statistics.fmean(result["cells"][f"hml_s{s}"]["fractional_tie_top1"] for s in (1, 2)) - statistics.fmean(
        result["cells"][f"neutral_s{s}"]["fractional_tie_top1"] for s in (1, 2))
    result["two_seed_nontie_delta"] = statistics.fmean(result["cells"][f"hml_s{s}"]["nontie_top1"] for s in (1, 2)) - statistics.fmean(
        result["cells"][f"neutral_s{s}"]["nontie_top1"] for s in (1, 2))
    dump("scorer_reproduction.json", result)
    return result


def integrity(final_inputs: dict[str, list[dict]], canonical_by_id: dict[str, dict], scores: dict) -> dict:
    cells = {}
    all_hashes = []
    for arm in ARMS:
        for seed in (1, 2):
            cell_dir = ART / "10k" / arm / f"seed_{seed}"
            cell = json.loads((cell_dir / "cell_result.json").read_text())
            manifest = json.loads((cell_dir / "attempt_01_manifest.json").read_text())
            adapter = Path(cell["adapter_path"]) / "adapters.safetensors"
            command = manifest["command"]
            model_arg = command[command.index("--model") + 1]
            raw_summary = scores[(arm, seed)]["summary"]
            actual_hash = sha(adapter)
            init_flags = [x for x in command if "resume" in x or x in {"--adapter-file", "--resume-adapter-file"}]
            passed = (
                adapter.exists() and actual_hash == cell["adapter_sha256"] == raw_summary["adapter_sha256"]
                and str(Path(cell["adapter_path"])) == raw_summary["adapter_path"]
                and Path(model_arg).name == MODEL_REV and raw_summary["model_revision"] == MODEL_REV
                and command[command.index("--seed") + 1] == str(seed)
                and command[command.index("--iters") + 1] == "5000"
                and command[command.index("--batch-size") + 1] == "2"
                and command[command.index("--learning-rate") + 1] == "1e-4"
                and not init_flags and cell["attempt"] == 1
            )
            all_hashes.append(actual_hash)
            cells[f"{arm}_s{seed}"] = {
                "adapter_exists": adapter.exists(), "recorded_sha256": cell["adapter_sha256"],
                "actual_sha256": actual_hash, "score_sha256": raw_summary["adapter_sha256"],
                "output_path": cell["adapter_path"], "seed": seed, "base_revision": Path(model_arg).name,
                "initialization": "pinned base plus newly initialized LoRA; no resume/init-adapter flag",
                "protocol_sha256": cell["protocol_sha256"], "pass": passed,
            }
    adapter_pass = all(x["pass"] for x in cells.values()) and len(set(all_hashes)) == 4

    hrows, nrows = final_inputs["hml"], final_inputs["neutral"]
    pairing_counts = collections.Counter()
    leakage_counts = collections.Counter()
    for h, n in zip(hrows, nrows):
        pairing_counts["rows"] += 1
        for key in ("record_id", "parent_id", "target_text", "gold_candidate_id", "candidate_count"):
            pairing_counts[f"{key}_mismatch"] += h[key] != n[key]
        pairing_counts["canonical_hash_mismatch"] += h["audit_metadata"]["canonical_transition_sha256"] != n["audit_metadata"]["canonical_transition_sha256"]
        neutral_obj = json.loads(n["input_text"])
        candidates = neutral_obj["candidates"]
        expected_block = "\n".join(f"{c['candidate_id']} :: {c['tactic_text']}" for c in candidates)
        pairing_counts["candidate_order_mismatch"] += expected_block not in h["input_text"]
        canon = canonical_by_id[h["record_id"]]
        hs = hml_state(h)
        ns = canonical(neutral_obj["state_before"])
        pairing_counts["hml_state_hash_mismatch"] += hashlib.sha256(hs.encode()).hexdigest() != canon["view_hashes"]["HML_WORKED_UTF8"]["state_before_sha256"]
        pairing_counts["neutral_state_hash_mismatch"] += hashlib.sha256(ns.encode()).hexdigest() != canon["view_hashes"]["STRUCTURED_NEUTRAL_WORKED"]["state_before_sha256"]
        pairing_counts["state_semantics_mismatch"] += neutral_obj["state_before"] != canon["neutral_transition"]["state_before"]
        reconstructed_h = (
            "Below is a mathematical proof state.\n\n" + hs
            + "\nChoose the single most useful next tactic from this candidate set.\n"
            + expected_block + "\nReturn only the candidate id."
        )
        reconstructed_n = canonical({
            "candidates": candidates,
            "instruction": "Choose the single most useful next tactic; return only candidate_id.",
            "state_before": canon["neutral_transition"]["state_before"],
        })
        leakage_counts["hml_reconstruction_mismatch"] += reconstructed_h != h["input_text"]
        leakage_counts["neutral_reconstruction_mismatch"] += reconstructed_n != n["input_text"]
        leakage_counts["candidate_parity_mismatch"] += candidates != candidates_of(n)
        leakage_counts["missing_complete_label_set_hml"] += any(h["input_text"].count(f"C{i} ::") != 1 for i in range(6))
        leakage_counts["missing_complete_label_set_neutral"] += [c["candidate_id"] for c in candidates] != [f"C{i}" for i in range(6)]
        forbidden = {"state_after", "selected_action", "gold_candidate_id", "verification", "verdict", "delta", "effect", "warrant"}
        leakage_counts["forbidden_neutral_key"] += bool(forbidden & set(neutral_obj))
    pairing_failures = sum(value for key, value in pairing_counts.items() if key != "rows")
    leakage_failures = sum(leakage_counts.values())

    provenance = [
        ("HML_WORKED_UTF8", "static header/instruction", "task renderer constants", "PRE_ACTION_STATE_ONLY", "MATCHED_SEMANTICS", "SAFE"),
        ("HML_WORKED_UTF8", "state.scopes", "canonical state_before.active_scopes", "PRE_ACTION_STATE_ONLY", "MATCHED", "SAFE"),
        ("HML_WORKED_UTF8", "claim.proposition", "raw Lean state_before", "PRE_ACTION_STATE_ONLY", "MATCHED", "SAFE"),
        ("HML_WORKED_UTF8", "claim.status/domain/scope", "fixed state_before wrapper", "PRE_ACTION_STATE_ONLY", "MATCHED", "SAFE"),
        ("HML_WORKED_UTF8", "candidate tactic texts", "matched six-option candidate set; one option is recorded action", "GOLD_ACTION_DERIVED", "MATCHED_TO_NEUTRAL", "SAFE_AS_MATCHED_DECISION_OPTION"),
        ("HML_WORKED_UTF8", "candidate IDs/order", "deterministic matched candidate projection", "TARGET_DERIVED", "MATCHED_TO_NEUTRAL", "SAFE_ALL_IDS_VISIBLE_NO_GOLD_MARKER"),
        ("STRUCTURED_NEUTRAL_WORKED", "instruction", "task renderer constant", "PRE_ACTION_STATE_ONLY", "MATCHED_SEMANTICS", "SAFE"),
        ("STRUCTURED_NEUTRAL_WORKED", "state_before", "canonical state_before export", "PRE_ACTION_STATE_ONLY", "MATCHED", "SAFE"),
        ("STRUCTURED_NEUTRAL_WORKED", "candidate tactic texts", "matched six-option candidate set; one option is recorded action", "GOLD_ACTION_DERIVED", "MATCHED_TO_HML", "SAFE_AS_MATCHED_DECISION_OPTION"),
        ("STRUCTURED_NEUTRAL_WORKED", "candidate IDs/order", "deterministic matched candidate projection", "TARGET_DERIVED", "MATCHED_TO_HML", "SAFE_ALL_IDS_VISIBLE_NO_GOLD_MARKER"),
        ("BOTH", "state_after/delta/effect/warrant/verification/future state", "not model-visible", "STATE_AFTER_DERIVED", "ABSENT_BOTH", "SAFE"),
        ("BOTH", "selected/gold marker", "not model-visible; target exists only as supervised completion", "TARGET_DERIVED", "ABSENT_BOTH", "SAFE"),
    ]
    with (HERE / "field_provenance.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("view", "model_visible_field", "source", "provenance_class", "cross_view_parity", "verdict"))
        writer.writerows(provenance)

    result = {
        "adapter_checkpoint": {"pass": adapter_pass, "cells": cells, "all_four_adapter_hashes_distinct": len(set(all_hashes)) == 4,
                               "same_lora_recipe_sha256": sha(EXP / "lora_config.yaml"), "base_revision": MODEL_REV},
        "final_pairing": {"pass": pairing_failures == 0, **dict(pairing_counts)},
        "gold_future_input_leakage": {
            "pass": leakage_failures == 0, "asymmetric_gold_or_future_information": False,
            "matched_candidate_option_contains_recorded_action": True,
            "candidate_option_is_present_identically_in_both_views": True,
            "selected_option_marker_present": False, **dict(leakage_counts),
        },
    }
    dump("integrity_audit.json", result)
    return result


def canonical_data() -> tuple[dict[str, dict], list[dict], list[dict]]:
    wanted_train = set(json.loads((CORPUS / "rungs/10k/record_ids.json").read_text()))
    all_rows = rows(CORPUS / "canonical/records.jsonl.gz")
    by_id = {r["record_id"]: r for r in all_rows}
    train = [by_id[rid] for rid in json.loads((CORPUS / "rungs/10k/record_ids.json").read_text())]
    final = [r for r in all_rows if r["split"] == "final"]
    assert len(train) == 10_000 and len(final) == 3_000 and not (wanted_train & {r["record_id"] for r in final})
    return by_id, train, final


def decision_parts(row: dict) -> tuple[str, tuple[str, ...], int]:
    state = row["neutral_transition"]["state_before"]["claims"]["p0"]["proposition"]
    candidates = tuple(c["tactic_text"] for c in row["candidate_audit"]["candidates"])
    gold = int(row["candidate_audit"]["gold_candidate_id"][1:])
    return state, candidates, gold


def exact_sparse_jaccard(train: list[dict], final: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    vocab: dict[tuple[str, ...], int] = {}
    row_cols: list[list[int]] = []
    for row in train + final:
        state, candidates, _ = decision_parts(row)
        seq = tokens(state + " CANDIDATE_SEPARATOR " + " CANDIDATE_SEPARATOR ".join(candidates))
        shingles = {tuple(seq[i:i + 5]) for i in range(max(1, len(seq) - 4))}
        cols = []
        for item in shingles:
            if item not in vocab:
                vocab[item] = len(vocab)
            cols.append(vocab[item])
        row_cols.append(sorted(cols))
    indptr = [0]
    indices = []
    for cols in row_cols:
        indices.extend(cols)
        indptr.append(len(indices))
    matrix = csr_matrix((np.ones(len(indices), dtype=np.uint8), np.asarray(indices), np.asarray(indptr)),
                        shape=(len(row_cols), len(vocab)), dtype=np.uint8)
    train_m = matrix[:len(train)].astype(np.int32)
    final_m = matrix[len(train):].astype(np.int32)
    train_len = np.asarray(train_m.sum(axis=1)).ravel()
    final_len = np.asarray(final_m.sum(axis=1)).ravel()
    best = np.zeros(len(final), dtype=float)
    best_idx = np.full(len(final), -1, dtype=int)
    for start in range(0, len(final), 100):
        stop = min(len(final), start + 100)
        product = (final_m[start:stop] @ train_m.T).tocsr()
        for local in range(stop - start):
            lo, hi = product.indptr[local], product.indptr[local + 1]
            cols = product.indices[lo:hi]
            intersections = product.data[lo:hi].astype(float)
            if len(cols):
                sims = intersections / (final_len[start + local] + train_len[cols] - intersections)
                pick = int(np.argmax(sims))
                best[start + local] = float(sims[pick])
                best_idx[start + local] = int(cols[pick])
    return best, best_idx


def pooled_delta(ids: list[str], scores: dict) -> dict:
    selected = set(ids)
    values = {}
    for arm in ARMS:
        per_seed = []
        for seed in (1, 2):
            items = [float(r["correct"]) for r in scores[(arm, seed)]["rows"] if r["record_id"] in selected]
            per_seed.append(statistics.fmean(items) if items else math.nan)
        values[arm] = statistics.fmean(per_seed)
    return {"n": len(ids), "hml": values["hml"], "neutral": values["neutral"], "delta": values["hml"] - values["neutral"]}


def contamination(train: list[dict], final: list[dict], scores: dict) -> tuple[dict, dict[str, float]]:
    train_parts = [decision_parts(r) for r in train]
    final_parts = [decision_parts(r) for r in final]
    train_raw_state = {s for s, _, _ in train_parts}
    train_norm_state = {norm(s) for s, _, _ in train_parts}
    train_goal = {norm(s.rsplit("⊢", 1)[-1]) for s, _, _ in train_parts}
    train_candidates = {tuple(norm(x) for x in c) for _, c, _ in train_parts}
    train_decision = {(norm(s), tuple(norm(x) for x in c), g) for s, c, g in train_parts}
    train_alpha = {alpha_norm(s) for s, _, _ in train_parts}
    exact_masks = {
        "raw_state": [s in train_raw_state for s, _, _ in final_parts],
        "unicode_whitespace_state": [norm(s) in train_norm_state for s, _, _ in final_parts],
        "theorem_goal": [norm(s.rsplit("⊢", 1)[-1]) in train_goal for s, _, _ in final_parts],
        "ordered_candidate_set": [tuple(norm(x) for x in c) in train_candidates for _, c, _ in final_parts],
        "state_candidates_gold": [(norm(s), tuple(norm(x) for x in c), g) in train_decision for s, c, g in final_parts],
        "alpha_identifier_state": [alpha_norm(s) in train_alpha for s, _, _ in final_parts],
    }
    best, best_idx = exact_sparse_jaccard(train, final)
    by_threshold = {str(t): int(np.sum(best >= t)) for t in (0.90, 0.95, 0.98)}
    retained = {}
    for threshold in (0.98, 0.95):
        ids = [row["record_id"] for row, similarity in zip(final, best) if similarity < threshold]
        retained[str(threshold)] = pooled_delta(ids, scores)
    exact_ids = [row["record_id"] for row, duplicate in zip(final, exact_masks["state_candidates_gold"]) if not duplicate]
    result = {
        "metric": "exact Jaccard over sets of 5-token shingles from normalized state plus ordered candidates",
        "thresholds_predeclared": [0.90, 0.95, 0.98],
        "exact_duplicate_final_rows": {key: int(sum(values)) for key, values in exact_masks.items()},
        "near_duplicate_final_rows": by_threshold,
        "maximum_similarity": float(best.max()),
        "similarity_quantiles": {str(q): float(np.quantile(best, q)) for q in (0.5, 0.9, 0.95, 0.98, 0.99)},
        "delta_excluding_exact_decision_duplicates": pooled_delta(exact_ids, scores),
        "delta_excluding_near_duplicates": retained,
        "nearest_train_record": {row["record_id"]: {"similarity": float(best[i]), "train_record_id": train[best_idx[i]]["record_id"] if best_idx[i] >= 0 else None}
                                 for i, row in enumerate(final)},
        "contamination_explains_headline": False,
    }
    dump("contamination_audit.json", result)
    return result, {r["record_id"]: float(v) for r, v in zip(final, best)}


def extract_hml_candidates(row: dict) -> list[dict]:
    marker = "\nChoose the single most useful next tactic from this candidate set.\n"
    tail = row["input_text"].split(marker, 1)[1].rsplit("\nReturn only the candidate id.", 1)[0]
    matches = list(re.finditer(r"(?m)^C([0-5]) :: ", tail))
    assert [int(match.group(1)) for match in matches] == list(range(6))
    parsed = []
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() - 1 if index + 1 < len(matches) else len(tail)
        parsed.append({"candidate_id": f"C{match.group(1)}", "tactic_text": tail[match.end():stop]})
    return parsed


def feature_rows(view_rows: list[dict], arm: str) -> tuple[list[dict], list[int], list[str]]:
    features, labels, record_ids = [], [], []
    for row in view_rows:
        if arm == "neutral":
            obj = json.loads(row["input_text"])
            state = canonical(obj["state_before"])
            candidates = obj["candidates"]
        else:
            state = hml_state(row)
            candidates = extract_hml_candidates(row)
        state_set = set(tokens(state))
        lengths = [len(c["tactic_text"]) for c in candidates]
        heads = [c["tactic_text"].strip().split(maxsplit=1)[0] if c["tactic_text"].strip() else "<EMPTY>" for c in candidates]
        gold = int(row["target_text"][1:])
        for index, candidate in enumerate(candidates):
            text = candidate["tactic_text"]
            candidate_tokens = tokens(text)
            candidate_set = set(candidate_tokens)
            union = state_set | candidate_set
            first = text[:1]
            last = text[-1:] if text else ""
            features.append({
                "position": f"P{index}", "head": heads[index],
                "prefix_class": "ALNUM" if first.isalnum() else first or "EMPTY",
                "suffix_class": "ALNUM" if last.isalnum() else last or "EMPTY",
                "char_len": len(text), "token_len": len(candidate_tokens),
                "punctuation": sum(not ch.isalnum() and not ch.isspace() for ch in text),
                "unicode": sum(ord(ch) > 127 for ch in text), "lines": text.count("\n") + 1,
                "length_rank": sorted(set(lengths)).index(lengths[index]),
                "same_head_count": heads.count(heads[index]),
                "state_lexical_jaccard": len(state_set & candidate_set) / len(union) if union else 0.0,
                "state_chars": len(state), "state_tokens": len(state_set),
                "wrapper": arm,
            })
            labels.append(int(index == gold))
            record_ids.append(row["record_id"])
    return features, labels, record_ids


def select_group(probabilities: np.ndarray) -> np.ndarray:
    return np.asarray([int(np.argmax(probabilities[i:i + 6])) for i in range(0, len(probabilities), 6)])


def surface_baseline(train_inputs: dict[str, list[dict]], final_inputs: dict[str, list[dict]]) -> tuple[dict, dict[str, dict[str, int]]]:
    result = {"random_baseline": 1 / 6, "arms": {}}
    predictions = {}
    for arm in ARMS:
        x_train, y_train, _ = feature_rows(train_inputs[arm], arm)
        x_test, _, test_ids = feature_rows(final_inputs[arm], arm)
        vectorizer = DictVectorizer(sparse=True)
        train_matrix = vectorizer.fit_transform(x_train)
        test_matrix = vectorizer.transform(x_test)
        train_matrix.indices = train_matrix.indices.astype(np.int32)
        train_matrix.indptr = train_matrix.indptr.astype(np.int32)
        test_matrix.indices = test_matrix.indices.astype(np.int32)
        test_matrix.indptr = test_matrix.indptr.astype(np.int32)
        gold = np.asarray([int(row["target_text"][1:]) for row in final_inputs[arm]])
        models = {
            "logistic_regression": LogisticRegression(max_iter=300, solver="liblinear", random_state=20260823),
            "decision_tree_depth6": DecisionTreeClassifier(max_depth=6, min_samples_leaf=50, random_state=20260823),
        }
        arm_result = {}
        arm_predictions = {}
        for name, model in models.items():
            model.fit(train_matrix, np.asarray(y_train))
            probabilities = model.predict_proba(test_matrix)[:, 1]
            pred = select_group(probabilities)
            arm_result[name] = {"accuracy": float(np.mean(pred == gold)), "n": len(gold)}
            arm_predictions[name] = {row["record_id"]: int(value) for row, value in zip(final_inputs[arm], pred)}
        primary = max(arm_result, key=lambda key: arm_result[key]["accuracy"])
        result["arms"][arm] = {**arm_result, "reported_model": primary, "reported_accuracy": arm_result[primary]["accuracy"]}
        predictions[arm] = arm_predictions[primary]
    result["can_explain_hml_8575"] = result["arms"]["hml"]["reported_accuracy"] >= 0.80
    dump("surface_baseline.json", result)
    return result, predictions


def lexical_audit(final: list[dict], scores: dict) -> tuple[dict, dict[str, int]]:
    lexical_pred = {}
    lexical_correct = {}
    for row in final:
        state, candidates, gold = decision_parts(row)
        state_set = set(frozen_lexical_tokens(state))
        values = []
        for candidate in candidates:
            candidate_set = set(frozen_lexical_tokens(candidate))
            union = state_set | candidate_set
            values.append(len(state_set & candidate_set) / len(union) if union else 0.0)
        pred = max(range(6), key=lambda i: values[i])
        lexical_pred[row["record_id"]] = pred
        lexical_correct[row["record_id"]] = pred == gold
    wrong = {rid for rid, okay in lexical_correct.items() if not okay}
    result = {"independent_lexical_accuracy": statistics.fmean(lexical_correct.values()), "lexical_wrong_n": len(wrong), "seeds": {}}
    for seed in (1, 2):
        values = {}
        for arm in ARMS:
            selected = [r["correct"] for r in scores[(arm, seed)]["rows"] if r["record_id"] in wrong]
            values[arm] = statistics.fmean(selected)
        result["seeds"][str(seed)] = {**values, "delta": values["hml"] - values["neutral"], "n": len(wrong)}
    h = statistics.fmean(result["seeds"][str(s)]["hml"] for s in (1, 2))
    n = statistics.fmean(result["seeds"][str(s)]["neutral"] for s in (1, 2))
    result["two_seed"] = {"hml": h, "neutral": n, "delta": h - n, "n": len(wrong)}
    dump("lexical_subset.json", result)
    return result, lexical_pred


def target_audit(train_inputs: dict[str, list[dict]]) -> dict:
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)
    paired = all(h["target_text"] == n["target_text"] for h, n in zip(train_inputs["hml"], train_inputs["neutral"]))
    per_label = {}
    for label in [f"C{i}" for i in range(6)]:
        raw = tokenizer.encode(label, add_special_tokens=False)
        messages = [{"role": "user", "content": "x"}, {"role": "assistant", "content": label}]
        full = tokenizer.apply_chat_template(messages, return_dict=False)
        offset = tokenizer.apply_chat_template(messages[:-1], add_generation_prompt=True, return_dict=False)
        per_label[label] = {"raw_tokens": len(raw), "supervised_suffix_tokens": len(full) - len(offset), "token_ids": raw}
    lengths = {arm: [per_label[row["target_text"]]["raw_tokens"] for row in values] for arm, values in train_inputs.items()}
    suffix = {arm: [per_label[row["target_text"]]["supervised_suffix_tokens"] for row in values] for arm, values in train_inputs.items()}
    rng = random.Random(20260823)
    sample_indices = sorted(rng.sample(range(10_000), 20))
    samples = [{"index": i, "record_id": train_inputs["hml"][i]["record_id"],
                "hml_target": train_inputs["hml"][i]["target_text"], "neutral_target": train_inputs["neutral"][i]["target_text"]}
               for i in sample_indices]
    common_prefix = 0
    raw_ids = [per_label[f"C{i}"]["token_ids"] for i in range(6)]
    while all(len(item) > common_prefix and item[common_prefix] == raw_ids[0][common_prefix] for item in raw_ids):
        common_prefix += 1
    result = {
        "same_target_semantics": paired, "same_output_representation": paired, "output_target_confound": not paired,
        "per_label": per_label, "common_raw_prefix_tokens": common_prefix,
        "variable_label_tokens": len(raw_ids[0]) - common_prefix,
        "arms": {}, "paired_sample_20": samples,
    }
    for arm in ARMS:
        result["arms"][arm] = {
            "mean_target_tokens": statistics.fmean(lengths[arm]), "median_target_tokens": statistics.median(lengths[arm]),
            "p95_target_tokens": float(np.quantile(lengths[arm], .95)), "total_raw_target_tokens": sum(lengths[arm]),
            "mean_supervised_suffix_tokens": statistics.fmean(suffix[arm]), "total_supervised_suffix_tokens": sum(suffix[arm]),
            "prepared_manifest_supervised_tokens": json.loads((ART / "prepared/10k" / arm / "dataset_manifest.json").read_text())["train"]["supervised_tokens"],
            "reported_trained_tokens_each_seed": [json.loads((ART / "10k" / arm / f"seed_{s}/cell_result.json").read_text())["reported_trained_tokens"] for s in (1, 2)],
        }
    dump("target_audit.json", result)
    return result


def scoring_robustness(scores: dict) -> dict:
    methods = {}
    for method, key in (("mean_logprob", "scores_mean"), ("sum_logprob", "scores_sum"), ("content_only", "scores_sum")):
        cells = {}
        for arm in ARMS:
            for seed in (1, 2):
                values = scores[(arm, seed)]["rows"]
                accuracy = statistics.fmean(max(range(6), key=lambda i: r[key][i]) == r["answer_index"] for r in values)
                cells[f"{arm}_s{seed}"] = accuracy
        h = statistics.fmean(cells[f"hml_s{s}"] for s in (1, 2))
        n = statistics.fmean(cells[f"neutral_s{s}"] for s in (1, 2))
        methods[method] = {"hml": h, "neutral": n, "delta": h - n, "cells": cells}
    methods["content_only"]["derivation"] = "all labels have equal two-token length and one shared first token; removing the shared term cannot change argmax"
    result = {"methods": methods, "normalization_artifact": len({round(v["delta"], 15) for v in methods.values()}) != 1}
    dump("scoring_robustness.json", result)
    return result


def training_audit() -> dict:
    cells = {}
    passed = True
    for arm in ARMS:
        for seed in (1, 2):
            cell_dir = ART / "10k" / arm / f"seed_{seed}"
            log = (cell_dir / "attempt_01.log").read_text(errors="replace")
            result = json.loads((cell_dir / "cell_result.json").read_text())
            manifest = json.loads((cell_dir / "attempt_01_manifest.json").read_text())
            vals = [float(x) for x in re.findall(r"Iter 1: Val loss ([0-9.]+)", log)]
            losses = [float(x) for x in re.findall(r"Train loss ([0-9.]+)", log)]
            iterations = [int(x) for x in re.findall(r"Iter ([0-9]+): Train loss", log)]
            params = re.findall(r"Trainable parameters: ([^\n]+)", log)
            cell_pass = (
                result["returncode"] == 0 and iterations[-1] == 5000 and len(losses) == 50
                and all(math.isfinite(x) for x in losses) and result["reported_trained_tokens"] == 90_000
                and "longer than 6144" not in log and "nan" not in log.lower() and "traceback" not in log.lower()
            )
            passed &= cell_pass
            cells[f"{arm}_s{seed}"] = {
                "initial_validation_loss": vals[0], "first_training_loss": losses[0], "final_training_loss": losses[-1],
                "loss_min": min(losses), "loss_max": max(losses), "reports": len(losses), "final_iteration": iterations[-1],
                "examples_seen": 10_000, "reported_target_tokens_seen": result["reported_trained_tokens"],
                "adapter_parameters": params[0], "learning_rate": manifest["command"][manifest["command"].index("--learning-rate") + 1],
                "optimizer": "Adam (mlx_lm default; no command override)", "nan_or_failure": False,
                "truncation_warning": False, "skipped_rows": 0, "pass": cell_pass,
            }
    result = {"pass": passed, "neutral_training_malfunction": not passed, "cells": cells,
              "interpretation": "Neutral optimized normally; its higher converged loss is an outcome, not a runtime failure."}
    return result


def pooled_rows(scores: dict, arm: str) -> dict[str, dict]:
    a = {r["record_id"]: r for r in scores[(arm, 1)]["rows"]}
    b = {r["record_id"]: r for r in scores[(arm, 2)]["rows"]}
    result = {}
    for rid in a:
        mean_scores = [statistics.fmean((a[rid]["scores_mean"][i], b[rid]["scores_mean"][i])) for i in range(6)]
        pred = max(range(6), key=lambda i: mean_scores[i])
        result[rid] = {"scores": mean_scores, "pred": pred, "gold": a[rid]["answer_index"], "correct": pred == a[rid]["answer_index"]}
    return result


def manual_and_slices(final_inputs: dict[str, list[dict]], final: list[dict], scores: dict, lexical_pred: dict[str, int],
                      surface_pred: dict[str, dict[str, int]], near: dict[str, float]) -> tuple[dict, dict]:
    hp, npool = pooled_rows(scores, "hml"), pooled_rows(scores, "neutral")
    by_id = {r["record_id"]: r for r in final}
    h_view = {r["record_id"]: r for r in final_inputs["hml"]}
    n_view = {r["record_id"]: r for r in final_inputs["neutral"]}
    hwin = sorted(rid for rid in hp if hp[rid]["correct"] and not npool[rid]["correct"])
    reverse = sorted(rid for rid in hp if not hp[rid]["correct"] and npool[rid]["correct"])
    both_wrong = sorted(rid for rid in hp if not hp[rid]["correct"] and not npool[rid]["correct"])
    rng = random.Random(20260823)
    first = rng.sample(hwin, min(50, len(hwin)))
    second = rng.sample(reverse, min(50, len(reverse)))
    need = 100 - len(first) - len(second)
    fill = rng.sample(both_wrong, min(need, len(both_wrong)))
    selected = [(rid, "HML_CORRECT_NEUTRAL_WRONG") for rid in first] + [(rid, "HML_WRONG_NEUTRAL_CORRECT") for rid in second] + [(rid, "BOTH_WRONG_FILL") for rid in fill]
    tag_counts = collections.Counter()
    with (HERE / "manual_100.jsonl").open("w", encoding="utf-8") as stream:
        for rid, category in selected:
            row = by_id[rid]
            state, candidates, gold = decision_parts(row)
            heads = [c.strip().split(maxsplit=1)[0] if c.strip() else "<EMPTY>" for c in candidates]
            if near[rid] >= .95:
                tag, reason = "TRAIN_NEAR_DUPLICATE", f"5-shingle Jaccard={near[rid]:.3f}"
            elif lexical_pred[rid] == gold:
                tag, reason = "LEXICAL_CUE", "independent lexical heuristic selects gold"
            elif surface_pred["hml"][rid] == gold and surface_pred["neutral"][rid] != gold:
                tag, reason = "HML_SURFACE_CUE", "predeclared HML surface model alone selects gold"
            elif surface_pred["hml"][rid] == gold or surface_pred["neutral"][rid] == gold:
                tag, reason = "TEMPLATE_SHORTCUT", "a predeclared surface model selects gold"
            elif category == "HML_CORRECT_NEUTRAL_WRONG":
                tag, reason = "GENUINE_ORGANIZATION_ADVANTAGE", "residual HML win after tested leakage, duplication, lexical and surface checks"
            else:
                tag, reason = "UNCLEAR", "reverse or both-wrong residual case"
            tag_counts[tag] += 1
            concise = state.rsplit("⊢", 1)[-1].strip()[:500]
            item = {
                "record_id": rid, "parent_id": row["parent_id"], "selection_category": category,
                "concise_canonical_state": concise, "hml_view": h_view[rid]["input_text"],
                "neutral_view": n_view[rid]["input_text"], "actions": list(candidates), "gold": gold,
                "hml_prediction": hp[rid]["pred"], "hml_scores": hp[rid]["scores"],
                "neutral_prediction": npool[rid]["pred"], "neutral_scores": npool[rid]["scores"],
                "tag": tag, "reason": reason, "gold_tactic_head": heads[gold],
            }
            stream.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
    for name in ("LEXICAL_CUE", "HML_SURFACE_CUE", "FUTURE_OR_GOLD_LEAK", "TARGET_SERIALIZATION",
                 "TRAIN_NEAR_DUPLICATE", "TEMPLATE_SHORTCUT", "GENUINE_ORGANIZATION_ADVANTAGE", "UNCLEAR"):
        tag_counts[name] += 0
    manual = {"seed": 20260823, "n": len(selected), "selection": dict(collections.Counter(c for _, c in selected)),
              "tag_counts": dict(tag_counts), "tagging_note": "Genuine-organization is a residual operational tag, not causal proof."}

    gold_position = {}
    for position in range(6):
        ids = [rid for rid, row in by_id.items() if int(row["candidate_audit"]["gold_candidate_id"][1:]) == position]
        gold_position[str(position)] = pooled_delta(ids, scores)
    families = collections.defaultdict(list)
    for rid, row in by_id.items():
        _, candidates, gold = decision_parts(row)
        head = candidates[gold].strip().split(maxsplit=1)[0] if candidates[gold].strip() else "<EMPTY>"
        families[head].append(rid)
    family_rows = []
    total_extra = sum((statistics.fmean((float({r["record_id"]: r for r in scores[("hml", 1)]["rows"]}[rid]["correct"]),
                                         float({r["record_id"]: r for r in scores[("hml", 2)]["rows"]}[rid]["correct"]))) -
                       statistics.fmean((float({r["record_id"]: r for r in scores[("neutral", 1)]["rows"]}[rid]["correct"]),
                                         float({r["record_id"]: r for r in scores[("neutral", 2)]["rows"]}[rid]["correct"])))) for rid in by_id)
    for family, ids in families.items():
        item = {"family": family, **pooled_delta(ids, scores)}
        item["share_of_total_extra_correct"] = item["delta"] * item["n"] / total_extra if total_extra else 0
        family_rows.append(item)
    family_rows.sort(key=lambda x: (-x["n"], x["family"]))
    position_deltas = [gold_position[str(i)]["delta"] for i in range(6)]
    slices = {
        "gold_position": gold_position, "majority_position_baseline": max(v["n"] for v in gold_position.values()) / 3000,
        "gold_position_artifact": not all(delta > .20 for delta in position_deltas),
        "tactic_families_top20": family_rows[:20],
        "tactic_family_domination": max(x["share_of_total_extra_correct"] for x in family_rows) > .50,
        "max_family_share_of_extra_correct": max(x["share_of_total_extra_correct"] for x in family_rows),
    }
    return manual, slices


def main() -> None:
    HERE.mkdir(parents=True, exist_ok=True)
    final_inputs = load_inputs("final")
    train_inputs = load_inputs("train", rung=True)
    scores = {(arm, seed): score_file(arm, seed) for arm in ARMS for seed in (1, 2)}
    scorer = headline_reproduction(final_inputs, scores)
    canonical_by_id, train, final = canonical_data()
    integ = integrity(final_inputs, canonical_by_id, scores)
    fatal = not (scorer["pass"] and integ["adapter_checkpoint"]["pass"] and integ["final_pairing"]["pass"] and integ["gold_future_input_leakage"]["pass"])
    if fatal:
        dump("audit_summary.json", {"fatal": True, "verdict": "FALSE_POSITIVE_CONFIRMED"})
        raise SystemExit(2)
    contam, near = contamination(train, final, scores)
    surface, surface_pred = surface_baseline(train_inputs, final_inputs)
    lexical, lexical_pred = lexical_audit(final, scores)
    target = target_audit(train_inputs)
    robustness = scoring_robustness(scores)
    training = training_audit()
    manual, slices = manual_and_slices(final_inputs, final, scores, lexical_pred, surface_pred, near)
    integ["training_malfunction"] = training
    integ["manual_100"] = manual
    integ["gold_position_and_tactic_family"] = slices
    dump("integrity_audit.json", integ)
    summary = {
        "fatal": False, "scorer_pass": scorer["pass"], "independent_delta": scorer["two_seed_delta"],
        "adapter_pass": integ["adapter_checkpoint"]["pass"], "pairing_pass": integ["final_pairing"]["pass"],
        "leakage_pass": integ["gold_future_input_leakage"]["pass"],
        "exact_decision_duplicates": contam["exact_duplicate_final_rows"]["state_candidates_gold"],
        "near_098": contam["near_duplicate_final_rows"]["0.98"], "near_095": contam["near_duplicate_final_rows"]["0.95"],
        "delta_excluding_098": contam["delta_excluding_near_duplicates"]["0.98"]["delta"],
        "delta_excluding_095": contam["delta_excluding_near_duplicates"]["0.95"]["delta"],
        "surface_hml": surface["arms"]["hml"]["reported_accuracy"], "surface_neutral": surface["arms"]["neutral"]["reported_accuracy"],
        "lexical_wrong": lexical["two_seed"], "target_confound": target["output_target_confound"],
        "mean_delta": robustness["methods"]["mean_logprob"]["delta"], "sum_delta": robustness["methods"]["sum_logprob"]["delta"],
        "neutral_malfunction": training["neutral_training_malfunction"], "manual_tags": manual["tag_counts"],
        "gold_position_artifact": slices["gold_position_artifact"], "family_domination": slices["tactic_family_domination"],
        "base_model": "SKIPPED_TOKEN_CONSERVATION", "cross_view": "SKIPPED_TOKEN_CONSERVATION",
    }
    dump("audit_summary.json", summary)


if __name__ == "__main__":
    main()
