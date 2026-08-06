"""H2 headroom screen: the PLAIN-ENGLISH arm only, over the existing eval001 corpus.

Purpose: find the problems on which the frozen model has neither floor nor ceiling
performance, so that a later representation comparison has statistical headroom. The pilot
returned 93.3% on all seven arms and could not have detected an effect of realistic size;
that is the defect this screen exists to remove.

Selection uses **no** arm-A-prime, HML or prior-pilot outcome, and no judgement about which
arm a task might favour. It reads the plain-English arm and the answer key, nothing else.

Prompts are the pre-generated files under `benchmarks/eval001/arms/A/`, so there is no
prompt-builder in the loop that could drift between screen and experiment.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
PROBLEMS = REPO / "benchmarks" / "eval001" / "problems"
ARM_A = REPO / "benchmarks" / "eval001" / "arms" / "A"
OUT = REPO / "evaluation" / "results" / "h2_headroom_screen"

#: Frozen by EVAL_SPEC_v1.1. Seeds were `null` there, so three are fixed here and recorded;
#: everything else is taken from the spec unchanged.
TEMPERATURE = 0.7
MAX_TOKENS = 2400
SEEDS = (101, 202, 303)


def _norm(text: str) -> str:
    return " ".join(str(text).lower().split())


def load_corpus() -> dict:
    return {p.stem: json.loads(p.read_text()) for p in sorted(PROBLEMS.glob("*.json"))}


def dedupe(problems: dict) -> tuple[list[str], list[tuple[str, str]]]:
    """Keep one representative per identical prose+question. Return (kept, excluded).

    16 groups in eval001 share a prose+question verbatim -- generator templates run at
    different seeds. Every group's answers agree, so they are true duplicates rather than
    contradictory keys. Screening all of them would inflate the headroom count and break
    the independence a paired analysis assumes.
    """
    seen: dict[str, str] = {}
    kept, excluded = [], []
    for pid in sorted(problems):
        d = problems[pid]
        key = _norm(d["prose"]) + " || " + _norm(d["question"])
        if key in seen:
            excluded.append((pid, f"duplicate prose+question of {seen[key]}"))
        else:
            seen[key] = pid
            kept.append(pid)
    return kept, excluded


def eligible(problems: dict) -> tuple[list[str], list[tuple[str, str]]]:
    kept, excluded = dedupe(problems)
    final = []
    for pid in kept:
        d = problems[pid]
        answer = d.get("answer") or {}
        if not answer.get("kind"):
            excluded.append((pid, "no answer kind: the target is not stated"))
            continue
        if answer["kind"] == "numeric" and answer.get("value") is None:
            excluded.append((pid, "numeric answer with no value"))
            continue
        if answer["kind"] == "choice" and not answer.get("options"):
            excluded.append((pid, "choice answer with no options"))
            continue
        if not (ARM_A / f"{pid}.txt").exists():
            excluded.append((pid, "no plain-English arm prompt on disk"))
            continue
        final.append(pid)
    return final, excluded


def prompt_parts(pid: str) -> tuple[str, str]:
    text = (ARM_A / f"{pid}.txt").read_text()
    system = text.split("### SYSTEM", 1)[1].split("### USER", 1)[0].strip()
    user = text.split("### USER", 1)[1].strip()
    return system, user


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def build_manifest(pids: list[str], excluded, digest: str) -> dict:
    problems = load_corpus()
    return {
        "experiment": "h2_headroom_screen",
        "arm": "A_plain_english",
        "purpose": "difficulty screening only; NOT a representation comparison",
        "model": "gemma4:31b",
        "model_digest": digest,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "seeds": list(SEEDS),
        "generations_per_problem": len(SEEDS),
        "scorer": "evaluation.corpus.cso.check_answer",
        "scorer_sha256": sha((REPO / "evaluation" / "corpus" / "cso.py").read_text()),
        "corpus_version": "eval001-v1",
        "original_problems": len(problems),
        "eligible_problems": len(pids),
        "excluded": [{"id": i, "reason": r} for i, r in excluded],
        "task_hashes": {p: sha(json.dumps(problems[p], sort_keys=True)) for p in pids},
        "prompt_hashes": {p: sha("".join(prompt_parts(p))) for p in pids},
        "frozen_order": pids,
    }
