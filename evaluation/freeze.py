"""Freeze the evaluation specification — EVAL_SPEC_v1.0.

    .venv/bin/python -m evaluation.freeze --version 1.0

Records the exact state of every component that can influence a reported number:
language commit and tag, corpus content hash, per-arm prompt-template hashes, scorer and
comparator source hashes, model identity and sampling configuration, and a manifest of
completed raw outputs.

Why this exists: once arm-level comparative results have been seen, any further change to
the scorer is unfalsifiable — it can always be rationalised, and it will always tend to
move numbers in the direction the author already expects. Freezing first makes a later
change visible as a *versioned rescore* with the v1.0 result preserved alongside it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "evaluation" / "results" / "runs"
OUT = REPO / "evaluation" / "results"

#: Every file whose contents can change a reported number.
SCORER_FILES = [
    "evaluation/corpus/cso.py",
    "evaluation/corpus/generators.py",
    "evaluation/corpus/renderers.py",
    "evaluation/semantic_equiv.py",
    "evaluation/analyse.py",
    "evaluation/harness.py",
    "evaluation/model_client.py",
]

LANGUAGE_FILES = [
    "src/hamiltonian_lang/types.py",
    "src/hamiltonian_lang/ast/nodes.py",
    "src/hamiltonian_lang/lexer/__init__.py",
    "src/hamiltonian_lang/parser/__init__.py",
    "src/hamiltonian_lang/semantics/__init__.py",
    "src/hamiltonian_lang/type_system/__init__.py",
    "src/hamiltonian_lang/type_system/distributions.py",
    "src/hamiltonian_lang/backends/canonical.py",
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_hash(rel: str) -> str | None:
    p = REPO / rel
    return _sha256(p.read_bytes()) if p.exists() else None


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"<unavailable: {e}>"


def corpus_hash() -> tuple[str, dict]:
    """Content hash over every canonical semantic object, order-independent."""
    from .corpus.generators import build_all

    per = {}
    for c in build_all():
        per[c.id] = _sha256(c.to_json().encode())
    combined = _sha256(
        "\n".join(f"{k}:{v}" for k, v in sorted(per.items())).encode()
    )
    return combined, per


def prompt_template_hashes() -> dict:
    """Hash each arm's prompt template, holding the problem fixed.

    Hashing a rendered prompt with the problem *removed* isolates the template, so a
    change to the instructions is detectable independently of a change to the corpus.
    """
    from .corpus.generators import build_all
    from .corpus.renderers import ARMS, render_arm
    from .harness import _demo_pairs

    probe = build_all()[0]
    out = {}
    for arm in ARMS:
        p = render_arm(arm, probe, _demo_pairs(arm))
        template = p.user.replace(probe.prose, "<PROSE>").replace(
            probe.question, "<QUESTION>"
        )
        out[arm] = {
            "system_sha256": _sha256(p.system.encode()),
            "template_sha256": _sha256(template.encode()),
            "template_chars": len(template),
            "feedback_enabled": p.feedback,
        }
    return out


def raw_manifest(run_id: str, generation: int | None) -> dict:
    path = RUNS / f"{run_id}.jsonl"
    if not path.exists():
        return {"ERROR": f"no run at {path}"}
    rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    if generation is not None:
        rows = [r for r in rows if r["generation"] == generation]
    per_cell = {
        f"{r['problem_id']}|{r['arm']}|{r['generation']}": _sha256(
            (r.get("raw_output") or "").encode()
        )
        for r in rows
    }
    return {
        "run_id": run_id,
        "generation_filter": generation,
        "n_trials": len(rows),
        "jsonl_sha256": _sha256(path.read_bytes()),
        "raw_output_hashes": per_cell,
        "combined_sha256": _sha256(
            "\n".join(f"{k}:{v}" for k, v in sorted(per_cell.items())).encode()
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.0")
    ap.add_argument("--run", default="eval001-pilot")
    ap.add_argument("--generation", type=int, default=0)
    ap.add_argument("--supersedes", default=None)
    ap.add_argument("--defect-file", default=None)
    args = ap.parse_args(argv)

    meta_path = RUNS / f"{args.run}.meta.json"
    run_meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    combined_corpus, per_problem = corpus_hash()

    spec = {
        "eval_spec_version": f"EVAL_SPEC_v{args.version}",
        "frozen_at_utc": _git("log", "-1", "--format=%cI") or None,
        "PURPOSE": (
            "Pins every component that can influence a reported number. After arm-level "
            "comparative results have been seen, no scorer change may be made under this "
            "version. A genuine defect requires a new version, the v1.0 result preserved, "
            "and a transparent rescore of the stored raw outputs."
        ),
        "language": {
            "git_commit": _git("rev-parse", "HEAD"),
            "git_tag": _git("describe", "--tags", "--always"),
            "git_describe_exact": _git("tag", "--points-at", "HEAD"),
            "working_tree_clean": _git("status", "--porcelain") == "",
            "file_hashes": {f: _file_hash(f) for f in LANGUAGE_FILES},
        },
        "corpus": {
            "combined_sha256": combined_corpus,
            "n_problems": len(per_problem),
            "per_problem_sha256": per_problem,
        },
        "prompt_templates": prompt_template_hashes(),
        "scorer": {
            "file_hashes": {f: _file_hash(f) for f in SCORER_FILES},
            "combined_sha256": _sha256(
                "\n".join(
                    f"{f}:{_file_hash(f)}" for f in sorted(SCORER_FILES)
                ).encode()
            ),
        },
        "model": {
            "info": run_meta.get("model_info"),
            "sampling": run_meta.get("sampling"),
            "endpoint": run_meta.get("model_info", {}).get("base_url"),
        },
        "run_configuration": {
            "run_id": args.run,
            "arms": run_meta.get("arms"),
            "problems": run_meta.get("problems"),
            "seed": run_meta.get("seed"),
            "max_repairs_arm_E": run_meta.get("max_repairs_arm_E"),
            "analysed_generation": args.generation,
        },
        "raw_output_manifest": raw_manifest(args.run, args.generation),
        "information_asymmetry": run_meta.get("information_asymmetry"),
    }
    if args.supersedes:
        spec["supersedes"] = args.supersedes
    if args.defect_file:
        spec["defect_record"] = json.loads(Path(args.defect_file).read_text())

    out = OUT / f"EVAL_SPEC_v{args.version}.json"
    out.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")

    print(f"EVAL_SPEC_v{args.version}")
    print(f"  language commit ....... {spec['language']['git_commit'][:12]}")
    print(f"  language tag .......... {spec['language']['git_tag']}")
    print(f"  working tree clean .... {spec['language']['working_tree_clean']}")
    print(f"  corpus sha256 ......... {combined_corpus[:16]}  ({len(per_problem)} problems)")
    print(f"  scorer sha256 ......... {spec['scorer']['combined_sha256'][:16]}")
    print(f"  model ................. {(spec['model']['info'] or {}).get('model')} "
          f"digest={(spec['model']['info'] or {}).get('digest', '')[:12]}")
    print(f"  sampling .............. {spec['model']['sampling']}")
    rm = spec["raw_output_manifest"]
    print(f"  raw outputs ........... {rm.get('n_trials')} trials, "
          f"combined {rm.get('combined_sha256','')[:16]}")
    print("  prompt templates:")
    for arm, h in spec["prompt_templates"].items():
        print(f"    {arm:8s} {h['template_sha256'][:12]}  {h['template_chars']:6d} chars")
    print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
