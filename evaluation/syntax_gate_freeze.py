"""Phase F4 experimental freeze for the syntax tournament — write it, then verify it.

    .venv/bin/python -m evaluation.syntax_gate_freeze --write --version 1.0
    .venv/bin/python -m evaluation.syntax_gate_freeze --verify

`evaluation/freeze.py` froze HML-EVAL-001. This module freezes the *syntax gate*, whose
components differ: four renderers and importers, a repair policy, and a per-slot context
budget that the earlier experiment did not have.

The directive says "after the tag, no silent modifications are allowed". A manifest that is
only ever written cannot enforce that — nothing reads it. `--verify` recomputes every hash
and reports drift, so a change becomes a visible failure instead of a quiet one. That is
the whole point of the file.

Provenance for the discipline: EVAL-DEFECT-001 was found *after* comparative results had
been seen. It was handled correctly only because v1.0 had been frozen and could be
preserved verbatim beside v1.1. Freezing first is what made an honest rescore possible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "evaluation" / "results" / "syntax_gate"

#: Sampling and transport settings. Any change here changes the experiment.
SAMPLING = {
    "model": "gemma4:31b",
    "temperature": 0.0,
    "primary_condition": "temperature 0, deterministic",
    "replication_condition": "fixed nonzero temperature with a recorded seed",
    "max_repairs": 1,
    "endpoint": "http://localhost:11434/v1/chat/completions",
    # Measured in docs/evaluation/EXECUTION_ENVIRONMENT.md: 4 slots x 8192 tokens.
    # 4 client workers give 2.08x; 8 workers degrade to 1.43x.
    "ollama_num_parallel": 4,
    "client_max_workers": 4,
    "context_tokens_per_slot": 8192,
    "measured_prompt_tokens_at_50_demos": 5893,
}

#: Stated here so a reader need not reconstruct them from code.
POLICIES = {
    "raw_output": (
        "Append-only. Raw generations are never overwritten and never deleted. A rescore "
        "reads stored outputs; it does not re-generate them."
    ),
    "empty_output": (
        "An empty visible answer is a MODEL FAILURE and is scored as one. It is never "
        "silently replaced by a retry."
    ),
    "transport_failure": (
        "May be retried under the uniform adapter policy, but the original request and "
        "response are preserved alongside the retry."
    ),
    "repair": (
        "At most one compiler-guided repair per task, explicitly recorded. First-attempt "
        "and repaired performance are reported separately, never merged."
    ),
    "truncation": (
        "A completion that hits the token limit is its own failure category. It is NOT a "
        "parse failure -- conflating them would understate the token cost of the syntax."
    ),
}

GATE_2 = {
    "repaired_parse_success": ">= 0.95",
    "semantic_preservation": ">= 0.90",
    "min_domain_repaired_parse": ">= 0.70",
    "completion_token_cost_vs_structured_english": "<= 2.0x",
    "note": "Reasoning-inclusive completion tokens. Ollama bills reasoning to completion_tokens.",
}

#: Files whose contents can change a reported number. Missing files are recorded as
#: missing rather than skipped -- a silently absent component is how a freeze rots.
FROZEN_FILES = [
    # compiler / semantic contract
    "src/hamiltonian_lang/types.py",
    "src/hamiltonian_lang/ast/nodes.py",
    "src/hamiltonian_lang/lexer/__init__.py",
    "src/hamiltonian_lang/parser/__init__.py",
    "src/hamiltonian_lang/semantics/__init__.py",
    "src/hamiltonian_lang/type_system/__init__.py",
    "src/hamiltonian_lang/type_system/distributions.py",
    "src/hamiltonian_lang/backends/canonical.py",
    "src/hamiltonian_lang/v1/epistemic.py",
    # schema
    "spec/ir.schema.json",
    "spec/v1/semantic_objects.yaml",
    # the freeze decision itself
    "docs/evaluation/V1_FREEZE_MANIFEST.md",
    "docs/evaluation/EXECUTION_ENVIRONMENT.md",
]

#: Directories frozen wholesale: every file is hashed, so an added file is also drift.
FROZEN_TREES = [
    "evaluation/syntax_acquisition",
    "benchmarks/syntax_gate",
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _show(path: Path) -> str:
    """Repo-relative when possible, absolute otherwise.

    `Path.relative_to` raises for anything outside the repo, and a reporting helper that
    can crash is worse than a slightly longer path.
    """
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return f"<unavailable: {exc}>"


def _file_hashes() -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in FROZEN_FILES:
        p = REPO / rel
        out[rel] = _sha256(p.read_bytes()) if p.is_file() else "<MISSING>"
    for tree in FROZEN_TREES:
        root = REPO / tree
        if not root.is_dir():
            out[tree + "/"] = "<MISSING>"
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                out[str(p.relative_to(REPO))] = _sha256(p.read_bytes())
    return out


def _model_digest() -> dict:
    """Identify the model by digest, not just by tag -- a tag can be reassigned."""
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/show",
            data=json.dumps({"model": SAMPLING["model"]}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            show = json.loads(r.read())
        req2 = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req2, timeout=60) as r:
            tags = json.loads(r.read())
        digest = next(
            (m.get("digest") for m in tags.get("models", [])
             if m.get("name") == SAMPLING["model"]), None
        )
        return {
            "name": SAMPLING["model"],
            "digest": digest,
            "family": show.get("details", {}).get("family"),
            "parameter_size": show.get("details", {}).get("parameter_size"),
            "quantization_level": show.get("details", {}).get("quantization_level"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"name": SAMPLING["model"], "ERROR": f"ollama unreachable: {exc}"}


def build_manifest(version: str) -> dict:
    files = _file_hashes()
    return {
        "manifest_version": version,
        "phase": "HML-PHASE-FG-001 / F4",
        "git": {
            "commit": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "tag": "hml-v1-eval-freeze",
            "dirty": bool(_git("status", "--porcelain")),
        },
        "model": _model_digest(),
        "sampling": SAMPLING,
        "policies": POLICIES,
        "gate_2": GATE_2,
        "files": files,
        "combined_sha256": _sha256(
            "\n".join(f"{k}:{v}" for k, v in sorted(files.items())).encode()
        ),
    }


def verify(path: Path) -> int:
    """Recompute every hash and report drift. Exit non-zero if the freeze was broken."""
    if not path.exists():
        print(f"NO MANIFEST at {_show(path)}; nothing is frozen yet.")
        return 1
    frozen = json.loads(path.read_text())
    current = _file_hashes()
    old = frozen["files"]

    changed = sorted(k for k in old.keys() & current.keys() if old[k] != current[k])
    removed = sorted(old.keys() - current.keys())
    added = sorted(current.keys() - old.keys())

    for label, items in (("CHANGED", changed), ("REMOVED", removed), ("ADDED", added)):
        for k in items:
            print(f"  {label}: {k}")

    model_now = _model_digest()
    if model_now.get("digest") != frozen.get("model", {}).get("digest"):
        print(f"  CHANGED: model digest {frozen.get('model', {}).get('digest')} "
              f"-> {model_now.get('digest')}")
        changed.append("<model>")

    if changed or removed or added:
        print(
            f"\nFREEZE VIOLATED: {len(changed)} changed, {len(removed)} removed, "
            f"{len(added)} added.\n"
            "A defect found after the freeze requires a NEW version, preservation of the "
            "frozen result, and a documented rescore-or-rerun decision. It does not permit "
            "editing the frozen manifest."
        )
        return 1
    print(f"FREEZE INTACT: {len(old)} files match manifest {frozen['manifest_version']}.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write a new manifest")
    ap.add_argument("--verify", action="store_true", help="check for drift")
    ap.add_argument("--version", default="1.0")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"FREEZE_MANIFEST_v{args.version}.json"

    if args.write:
        if path.exists():
            print(
                f"REFUSING to overwrite {_show(path)}.\n"
                "A frozen manifest is preserved verbatim; supersede it with a new "
                "--version instead."
            )
            return 1
        manifest = build_manifest(args.version)
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(f"wrote {_show(path)}")
        print(f"  files hashed:   {len(manifest['files'])}")
        print(f"  combined:       {manifest['combined_sha256']}")
        print(f"  commit:         {manifest['git']['commit']}")
        print(f"  model digest:   {manifest['model'].get('digest')}")
        if manifest["git"]["dirty"]:
            print("  WARNING: working tree is dirty; the commit does not describe the "
                  "hashed files.")
        missing = [k for k, v in manifest["files"].items() if v == "<MISSING>"]
        if missing:
            print(f"  WARNING: {len(missing)} frozen path(s) missing: {missing}")
        return 0

    if args.verify:
        return verify(path)

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
