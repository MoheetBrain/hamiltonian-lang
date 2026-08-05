"""Blinded evaluator audit — EVAL_SPEC_v1.0.

    .venv/bin/python -m evaluation.blind_audit sample --n 20
    .venv/bin/python -m evaluation.blind_audit unblind

``sample`` writes anonymised cases: the problem, the question, the verified answer, the
model's raw output and the automated verdict — with the **arm label removed** and cases
shuffled under a recorded seed. The auditor records agreement per case in
``audit_verdicts.json``. ``unblind`` then joins verdicts to arms and reports agreement.

Blinding matters because the auditor here knows which arm the project would prefer to
win. Auditing "does the scorer agree with me" while able to see the arm is not an audit.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "evaluation" / "results" / "runs"
OUT = REPO / "evaluation" / "results" / "audit"


def sample(run_id: str, n: int, generation: int, seed: int) -> int:
    from .corpus.generators import build_all

    corpus = {c.id: c for c in build_all()}
    from .analyse import rescore

    rows = [
        json.loads(x)
        for x in (RUNS / f"{run_id}.jsonl").read_text().splitlines() if x.strip()
    ]
    rows = [r for r in rows if r["generation"] == generation]
    # Re-score with the current comparator. Auditing the score written during the run
    # would audit a version of the scorer that no longer exists.
    rows = rescore(rows)
    rng = random.Random(seed)
    picked = rng.sample(rows, min(n, len(rows)))
    rng.shuffle(picked)

    OUT.mkdir(parents=True, exist_ok=True)
    key = {}
    cases = []
    for i, r in enumerate(picked, 1):
        cid = f"case{i:02d}"
        key[cid] = {
            "problem_id": r["problem_id"], "arm": r["arm"],
            "generation": r["generation"],
        }
        c = corpus[r["problem_id"]]
        cases.append({
            "case": cid,
            "problem": c.prose,
            "question": c.question,
            "verified_answer": c.answer.value,
            "answer_kind": c.answer.kind,
            "answer_justification": c.answer.justification,
            "ground_truth_facts": {
                k: v for k, v in c.semantics.__dict__.items() if v
            },
            "model_output": r["raw_output"],
            "model_encoding": r["encoding_text"] or None,
            "AUTOMATED_VERDICT": {
                "extracted_answer": r["extracted_answer"],
                "answer_correct": r["answer_correct"],
                "encoding_present": r["encoding_present"],
                "parse_success": r["parse_success"],
                "diagnostics": r["diagnostics"],
                "semantic_score": r["semantic_score"],
                "semantic_detail": r.get("semantic_detail"),
                "failure_class": r["failure_class"],
            },
        })

    (OUT / "blind_cases.json").write_text(json.dumps(cases, indent=2) + "\n")
    (OUT / "blind_key.json").write_text(
        json.dumps({"seed": seed, "run": run_id, "generation": generation, "key": key},
                   indent=2, sort_keys=True) + "\n"
    )
    print(f"wrote {len(cases)} blinded cases to {OUT / 'blind_cases.json'}")
    print(f"key withheld in {OUT / 'blind_key.json'} — do not read before auditing")
    return 0


def unblind() -> int:
    cases = json.loads((OUT / "blind_cases.json").read_text())
    key = json.loads((OUT / "blind_key.json").read_text())["key"]
    vpath = OUT / "audit_verdicts.json"
    if not vpath.exists():
        raise SystemExit(f"no verdicts at {vpath}; audit first")
    verdicts = json.loads(vpath.read_text())

    rows = []
    agree_answer = agree_semantic = 0
    counted_semantic = 0
    for c in cases:
        cid = c["case"]
        v = verdicts.get(cid)
        if v is None:
            continue
        auto = c["AUTOMATED_VERDICT"]
        a_ok = v["auditor_answer_correct"] == auto["answer_correct"]
        agree_answer += a_ok
        s_ok = None
        if v.get("auditor_semantic_reasonable") is not None:
            counted_semantic += 1
            s_ok = bool(v["auditor_semantic_reasonable"])
            agree_semantic += s_ok
        rows.append({
            "case": cid, "arm": key[cid]["arm"], "problem_id": key[cid]["problem_id"],
            "auto_answer_correct": auto["answer_correct"],
            "auditor_answer_correct": v["auditor_answer_correct"],
            "answer_agreement": a_ok,
            "auto_semantic_score": auto["semantic_score"],
            "auditor_semantic_reasonable": v.get("auditor_semantic_reasonable"),
            "semantic_agreement": s_ok,
            "auditor_note": v.get("note", ""),
        })

    by_arm: dict[str, dict] = {}
    for r in rows:
        b = by_arm.setdefault(r["arm"], {"n": 0, "answer_agree": 0})
        b["n"] += 1
        b["answer_agree"] += r["answer_agreement"]

    doc = {
        "n_audited": len(rows),
        "answer_agreement": f"{agree_answer}/{len(rows)}",
        "answer_agreement_rate": round(agree_answer / len(rows), 4) if rows else None,
        "semantic_agreement": f"{agree_semantic}/{counted_semantic}",
        "semantic_agreement_rate": (
            round(agree_semantic / counted_semantic, 4) if counted_semantic else None
        ),
        "by_arm": by_arm,
        "disagreements": [r for r in rows if not r["answer_agreement"]
                          or r["semantic_agreement"] is False],
        "cases": rows,
    }
    (OUT / "audit_result.json").write_text(json.dumps(doc, indent=2) + "\n")
    print(f"answer agreement ....... {doc['answer_agreement']} "
          f"({doc['answer_agreement_rate']})")
    print(f"semantic agreement ..... {doc['semantic_agreement']} "
          f"({doc['semantic_agreement_rate']})")
    print(f"arms represented ....... {sorted(by_arm)}")
    if doc["disagreements"]:
        print("\nDISAGREEMENTS:")
        for d in doc["disagreements"]:
            print(f"  {d['case']} arm={d['arm']} {d['problem_id']}: {d['auditor_note']}")
    else:
        print("\nno disagreements")
    print(f"\nwritten: {OUT / 'audit_result.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--run", default="eval001-pilot")
    s.add_argument("--n", type=int, default=20)
    s.add_argument("--generation", type=int, default=0)
    s.add_argument("--seed", type=int, default=424242)
    sub.add_parser("unblind")
    args = ap.parse_args(argv)
    if args.cmd == "sample":
        return sample(args.run, args.n, args.generation, args.seed)
    return unblind()


if __name__ == "__main__":
    raise SystemExit(main())
