"""Validate the project cognition ledger with a REAL YAML parser.

A regex scan is not a parser: it cannot tell a duplicate key from a nested one, and it
reports success on documents PyYAML refuses. The ledger is executable project state, so it
is loaded the way a consumer would load it and then checked structurally.

Read-only. The corpus repository is Codex-owned; this script never writes to it.

Written 2026-08-11 for the pre-Gemma semantic freeze gate (section 5).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

CORPUS = Path("/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus")
LEDGER = CORPUS / "experiments" / "project_cognition" / "project_memory.yaml"
HML = Path("/Users/moheet/hml_v2_worktree")
OUT = Path(__file__).resolve().parents[2] / "reports" / "artifacts"


class DuplicateKeyLoader(yaml.SafeLoader):
    """SafeLoader silently keeps the last of duplicated keys. That is data loss."""


def _no_duplicates(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


DuplicateKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates)


def main() -> None:
    report: dict = {"artifact_id": "cognition_ledger_validation", "ledger": str(LEDGER),
                    "checks": {}, "problems": []}

    if not LEDGER.exists():
        report["checks"]["exists"] = False
        report["problems"].append("ledger not found")
        (OUT / "COGNITION_LEDGER_VALIDATION.json").write_text(json.dumps(report, indent=1))
        print(json.dumps(report, indent=1))
        sys.exit(1)
    report["checks"]["exists"] = True
    report["bytes"] = LEDGER.stat().st_size

    # -- parse -------------------------------------------------------------
    try:
        doc = yaml.load(LEDGER.read_text(), Loader=DuplicateKeyLoader)
        report["checks"]["parses_with_real_yaml_parser"] = True
        report["checks"]["no_duplicate_mapping_keys"] = True
    except yaml.constructor.ConstructorError as exc:
        report["checks"]["parses_with_real_yaml_parser"] = True
        report["checks"]["no_duplicate_mapping_keys"] = False
        report["problems"].append(f"duplicate key: {exc}")
        doc = yaml.safe_load(LEDGER.read_text())
    except yaml.YAMLError as exc:
        report["checks"]["parses_with_real_yaml_parser"] = False
        report["problems"].append(f"YAML parse failure: {str(exc)[:400]}")
        (OUT / "COGNITION_LEDGER_VALIDATION.json").write_text(json.dumps(report, indent=1))
        print(json.dumps(report, indent=1))
        sys.exit(1)

    report["top_level_keys"] = sorted(doc) if isinstance(doc, dict) else type(doc).__name__

    # -- locate the X-entry collection, whatever it is called ---------------
    entries = None
    for key in ("entries", "memory", "records", "log", "items", "X"):
        if isinstance(doc, dict) and isinstance(doc.get(key), list):
            entries = doc[key]
            report["entries_key"] = key
            break
    if entries is None and isinstance(doc, dict):
        for key, value in doc.items():
            if isinstance(value, list) and value and isinstance(value[0], dict) and any(
                str(value[0].get(k, "")).startswith("X") for k in ("id", "x_id", "key")
            ):
                entries, report["entries_key"] = value, key
                break
    if entries is None:
        report["problems"].append("no X-entry list found; structural checks skipped")
        (OUT / "COGNITION_LEDGER_VALIDATION.json").write_text(json.dumps(report, indent=1))
        print(json.dumps(report, indent=1))
        return

    report["n_entries"] = len(entries)

    # -- ids: contiguous, unique -------------------------------------------
    ids, malformed = [], []
    for e in entries:
        raw = e.get("id") if isinstance(e, dict) else None
        m = re.fullmatch(r"X(\d+)", str(raw)) if raw is not None else None
        (ids.append(int(m.group(1))) if m else malformed.append(raw))
    report["checks"]["all_ids_well_formed"] = not malformed
    if malformed:
        report["problems"].append(f"malformed ids: {malformed[:10]}")
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    report["checks"]["ids_unique"] = not dupes
    if dupes:
        report["problems"].append(f"duplicate ids: X{dupes[:10]}")
    if ids:
        lo, hi = min(ids), max(ids)
        missing = sorted(set(range(lo, hi + 1)) - set(ids))
        report["id_range"] = [f"X{lo}", f"X{hi}"]
        report["checks"]["ids_contiguous"] = not missing
        if missing:
            report["problems"].append(f"gaps in id sequence: {[f'X{i}' for i in missing[:20]]}")

    # -- next_free_id ------------------------------------------------------
    declared = None
    for key in ("next_free_id", "next_id", "next_free"):
        if isinstance(doc, dict) and key in doc:
            declared, report["next_free_id_key"] = doc[key], key
            break
    if declared is not None and ids:
        m = re.fullmatch(r"X?(\d+)", str(declared))
        expected = max(ids) + 1
        actual = int(m.group(1)) if m else None
        report["next_free_id"] = {"declared": declared, "expected": f"X{expected}"}
        report["checks"]["next_free_id_correct"] = actual == expected
        if actual != expected:
            report["problems"].append(
                f"next_free_id is {declared!r}; highest entry is X{max(ids)}, so X{expected} expected")
    else:
        report["checks"]["next_free_id_declared"] = declared is not None

    # -- cross references ---------------------------------------------------
    known = {f"X{i}" for i in ids}
    dangling, self_refs = [], []
    for e in entries:
        if not isinstance(e, dict):
            continue
        eid = str(e.get("id"))
        refs = []
        for key in ("related", "related_to", "see_also", "refs", "supersedes", "depends_on"):
            value = e.get(key)
            if isinstance(value, str):
                refs += re.findall(r"X\d+", value)
            elif isinstance(value, list):
                for item in value:
                    refs += re.findall(r"X\d+", str(item))
        for ref in refs:
            if ref not in known:
                dangling.append((eid, ref))
            if ref == eid:
                self_refs.append(eid)
    report["checks"]["no_dangling_references"] = not dangling
    report["checks"]["no_self_references"] = not self_refs
    if dangling:
        report["problems"].append(f"dangling references: {dangling[:10]}")
    if self_refs:
        report["problems"].append(f"self references: {self_refs[:10]}")

    # -- cited commits resolve ---------------------------------------------
    text = LEDGER.read_text()
    shas = sorted(set(re.findall(r"\b[0-9a-f]{7,40}\b", text)))
    unresolved = []
    for sha in shas:
        ok = subprocess.run(["git", "-C", str(HML), "cat-file", "-e", f"{sha}^{{commit}}"],
                            capture_output=True).returncode == 0
        if not ok:
            ok = subprocess.run(["git", "-C", str(CORPUS), "cat-file", "-e", f"{sha}^{{commit}}"],
                                capture_output=True).returncode == 0
        if not ok:
            unresolved.append(sha)
    report["commit_like_tokens"] = len(shas)
    report["unresolved_commit_like_tokens"] = len(unresolved)
    report["unresolved_sample"] = unresolved[:15]
    report["note_on_commits"] = (
        "A 7-40 char hex run is not necessarily a commit id -- content hashes and truncated "
        "digests match the same pattern -- so an unresolved token is reported, not failed on.")

    report["VERDICT"] = "PASS" if not report["problems"] else "PROBLEMS FOUND"
    (OUT / "COGNITION_LEDGER_VALIDATION.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "unresolved_sample"}, indent=1))


if __name__ == "__main__":
    main()
