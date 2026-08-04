"""Run the deterministic harness over the hamiltonian arm and emit a baseline.

    .venv/bin/python evaluation/run_baseline.py

Writes ``evaluation/results/baseline.json``.

READ THE HEADER OF THE OUTPUT FILE BEFORE QUOTING ANY NUMBER FROM IT.

These numbers measure **the compiler**, with no model in the loop. They are a regression
baseline for the toolchain and a check that the benchmark corpus is well formed. They are
**not evidence for or against the project thesis**, which concerns whether an AI system
reasons better through this representation than through prose, LaTeX, code or an existing
formal language. Testing that requires model-in-the-loop arms A, A', B, C, D, E and E' as
specified in ``docs/research/BENCHMARK_PROTOCOL.md``. Those arms do not exist yet.
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))
if str(REPO / "evaluation") not in sys.path:
    sys.path.insert(0, str(REPO / "evaluation"))

from score import (  # noqa: E402
    TOKENIZER_IS_APPROXIMATE,
    TOKENIZER_NAME,
    aggregate,
    arm_path,
    diagnostic_line_accuracy,
    load_problems,
    score_problem,
    token_summary,
)

import hamiltonian_lang  # noqa: E402

RESULTS = REPO / "evaluation" / "results"

HEADER = {
    "WHAT_THIS_IS": (
        "Deterministic compiler-side baseline for the Hamiltonian Lang benchmark corpus. "
        "No language model was called at any point in producing this file."
    ),
    "WHAT_THIS_IS_NOT": (
        "This is NOT evidence for the project thesis. The thesis is that an AI system "
        "reasons more accurately and more verifiably through this representation than "
        "through prose, LaTeX, conventional code, or an existing formal language. "
        "Testing it requires model-in-the-loop arms A, A', B, C, D, E and E'. Those arms "
        "have not been built and no comparative measurement has been run. Any reading of "
        "these numbers as support for the thesis is a misreading."
    ),
    "WHAT_IT_MEASURES": [
        "that the benchmark corpus compiles as authored (a corpus sanity check)",
        "that the negative items are rejected with the diagnostic code the dataset asserts",
        "that structural ground truth authored from prose agrees with what the compiler "
        "recovers -- disagreements are findings, not reasons to edit the ground truth",
        "representation length in tokens, per arm",
        "whether the compiler points at the line that was actually broken",
    ],
    "KNOWN_INSTRUMENT_DEFECTS": (
        "See docs/research/BENCHMARK_PROTOCOL.md section 12 and audits/RED_TEAM_REPORT.md. "
        "Three defects named in earlier runs of this file have since been fixed and the "
        "claims are withdrawn: alpha-renaming now leaves the content hash unchanged "
        "(DECISIONS.md D-010, D-016 finding 1.9); unary minus no longer preserves a "
        "positivity refinement, so 'param s : PositiveReal = -1.0' is rejected; and Stan, "
        "SymPy and Lean backends now exist. Standing limitations: no backend is faithful "
        "-- each reports its own translation loss -- no proof obligation other than a "
        "dimensional check is ever discharged, and eight further findings in the red-team "
        "report remain open."
    ),
}


def main() -> int:
    items = load_problems()
    scores = [score_problem(i) for i in items]
    agg = aggregate(scores)
    toks = token_summary(scores)
    diag = diagnostic_line_accuracy(s.problem_id for s in scores)

    # Arm coverage: every problem must exist in every arm, or the comparison is unbalanced.
    arm_coverage: dict[str, dict] = {}
    for arm in ("english", "latex", "python", "stan_or_lean", "hamiltonian"):
        present = [i["id"] for i in items if arm_path(i["id"], arm) is not None]
        missing = [i["id"] for i in items if arm_path(i["id"], arm) is None]
        arm_coverage[arm] = {"present": len(present), "missing": missing}

    failures = [
        {
            "problem_id": s.problem_id,
            "failed": [a.to_dict() for a in s.assertions if not a.passed],
        }
        for s in scores if not s.all_assertions_passed
    ]

    doc = {
        "header": HEADER,
        "run": {
            "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "hamiltonian_lang_version": hamiltonian_lang.__version__,
            "canonical_version": __import__(
                "hamiltonian_lang.backends.canonical", fromlist=["CANONICAL_VERSION"]
            ).CANONICAL_VERSION,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "tokenizer": TOKENIZER_NAME,
            "token_counts_are_APPROXIMATE": TOKENIZER_IS_APPROXIMATE,
        },
        "arm_coverage": arm_coverage,
        "aggregate": agg,
        "tokens": toks,
        "diagnostic_quality": {
            "trials": diag["trials"],
            "detection_rate": diag["detection_rate"],
            "line_accuracy": diag["line_accuracy"],
            "by_injection": diag["by_injection"],
        },
        "assertion_failures": failures,
        "per_problem": [s.to_dict() for s in scores],
        "diagnostic_detail": diag["detail"],
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "baseline.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")

    print("=" * 78)
    print("COMPILER BASELINE -- NOT EVIDENCE FOR THE THESIS")
    print("=" * 78)
    print(f"problems scored ................ {agg['problems_scored']}")
    print(f"  expected valid ............... {agg['problems_expected_valid']}")
    print(f"  expected rejected ............ {agg['problems_expected_rejected']}")
    print(f"valid parse success rate ....... {agg['valid_parse_success_rate']}")
    print(f"negative rejection rate ........ {agg['negative_rejection_rate']}")
    print(f"assertions passed .............. {agg['assertions_passed']}/{agg['assertions_total']}")
    print(f"problems with all assertions ... {agg['problems_all_assertions_passed']}"
          f"/{agg['problems_scored']}")
    print(f"unintended hash collisions ..... {agg['content_hash_collisions_UNINTENDED'] or 'none'}")
    shared = [v["problems"] for v in agg["content_hash_shared"].values() if v["intended"]]
    print(f"intended shared hashes ......... {shared or 'none'}")
    print()
    print("per-metric assertion rates:")
    for k, v in sorted(agg["per_metric"].items()):
        print(f"  {k:26s} {v['passed']}/{v['total']}  = {v['rate']:.3f}")
    print()
    label = "  (APPROXIMATE)" if TOKENIZER_IS_APPROXIMATE else ""
    print(f"representation tokens, tokenizer = {TOKENIZER_NAME}{label}:")
    for arm, v in toks["by_arm"].items():
        ratio = v.get("ratio_to_english")
        r = f"  ratio_to_english={ratio}" if ratio is not None else ""
        print(f"  {arm:14s} total={v['total_tokens']:6d}  mean={v['mean_tokens']:7.1f}{r}")
    print("  NOT LIKE FOR LIKE: the non-hamiltonian arms carry the problem statement,")
    print("  the hamiltonian arm carries only the finished encoding. See tokens.CAVEAT.")
    print()
    print(f"diagnostic line accuracy ....... {diag['line_accuracy']} "
          f"over {diag['trials']} single-line injections")
    for name, b in sorted(diag["by_injection"].items()):
        print(f"  {name:36s} detect={b['detection_rate']:.3f} line={b['line_accuracy']:.3f}"
              f"  (n={b['n']})")
    if failures:
        print()
        print("ASSERTION FAILURES:")
        for f in failures:
            for a in f["failed"]:
                print(f"  {f['problem_id']:38s} {a['assert']:20s} {a['detail']}")
    print()
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
