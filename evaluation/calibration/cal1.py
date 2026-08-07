"""CAL-1 — structured-English-only difficulty calibration (directive §23).

**No HML is involved.** This measures the TASK CORPUS, not the language: does a region
exist where this model sits between roughly 30% and 70%? That question is independent of
every remaining compiler task, and it is the question that destroyed both previous
benchmark attempts — each built a corpus from *predicted* difficulty and each found the
structured-English control at 93% and 100% respectively, leaving no headroom for any
treatment to occupy.

So the design rule here is: **span difficulty, do not predict it.** Three tasks are placed
at deliberately different levels, and the point of the run is to find out which bracket the
model actually falls in, not to confirm a guess.

Task selection criteria, all of which the previous corpora failed on at least one count:

1. **Objectively scorable.** One unambiguous final answer, checked numerically or by exact
   case, never by judgement.
2. **Semantic error classes, not arithmetic.** Each task fails, when it fails, for a reason
   HML claims to address — a base-rate/role confusion, an ignored constraint, or an ignored
   domain restriction. A task whose difficulty is long multiplication would tell us nothing
   about a reasoning notation.
3. **Contamination-resistant.** Non-standard constants, so a memorised textbook answer does
   not score.

One call per task, temperature 0, no review call. Calibration responses are recorded and
**must never be reused in the paired pilot** (§23).
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluation.model_client import ModelClient, ModelConfig  # noqa: E402

MODEL = "gemma4:31b"
PINNED_DIGEST = "6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7"
TEMPERATURE = 0.0
MAX_TOKENS = 8192

#: The structured-English workspace. Deliberately notation-free: this arm must be a fair
#: control, so it gets an explicit place to work and an explicit answer format, and
#: nothing else. Anything more would be coaching; anything less would be a straw man.
SYSTEM = """You are solving a mathematics problem. Work in a structured written workspace.

Use these sections, in order:
GIVEN: the quantities and constraints stated in the problem.
GOAL: what must be determined.
REASONING: numbered steps. State any condition a step depends on.
CHECK: verify the result against the constraints in GIVEN.
FINAL ANSWER: the answer alone, on one line.

Be precise about conditions and constraints. If a step is only valid under some
condition, say so."""


@dataclass(frozen=True)
class Task:
    id: str
    intended_band: str  # a PREDICTION, recorded so it can be falsified
    error_class: str
    prompt: str
    #: Returns True when the extracted final answer is correct.
    answer_note: str


TASKS: list[Task] = [
    Task(
        id="cal1_screening",
        intended_band="easier",
        error_class="probability role / base rate",
        prompt=(
            "A screening test is applied to a population in which 3 people in every 500 "
            "have a certain condition.\n"
            "The test correctly returns positive for 94% of people who have the "
            "condition.\n"
            "The test correctly returns negative for 91% of people who do not have the "
            "condition.\n\n"
            "One person, chosen uniformly at random from this population, tests "
            "positive.\n"
            "What is the probability that this person has the condition?\n\n"
            "Give the final answer as a decimal rounded to four decimal places."
        ),
        answer_note="0.0593 (0.00564 / 0.09510)",
    ),
    Task(
        id="cal1_constrained_min",
        intended_band="middle",
        error_class="ignored constraint",
        prompt=(
            "Let f(x) = x^2 - 6x + 13, defined for real x.\n"
            "Subject to the constraint x >= 5, find the minimum value of f(x).\n\n"
            "Give the final answer as a single number: the minimum VALUE of f."
        ),
        answer_note="8 at x=5; the unconstrained minimum 4 at x=3 is infeasible",
    ),
    Task(
        id="cal1_domain_trap",
        intended_band="harder",
        error_class="ignored domain restriction (partiality)",
        prompt=(
            "Find every real number x satisfying\n\n"
            "    (x^2 - 9) / (x - 3) = 6\n\n"
            "If there are no such real numbers, say so explicitly.\n"
            "Give the final answer as either the complete list of solutions, or the "
            "words: no solution."
        ),
        answer_note="no solution: cancelling gives x=3, which the denominator excludes",
    ),
]


def extract_final(text: str) -> str:
    m = re.findall(r"FINAL ANSWER\s*:?\s*(.+)", text, flags=re.IGNORECASE)
    return m[-1].strip() if m else ""


def _numbers(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s.replace(",", ""))]


def score(task_id: str, final: str) -> bool:
    """Score semantically, and conservatively. An unparseable answer is WRONG, never
    generously reinterpreted -- the previous benchmarks' credibility problems all ran in
    the generous direction."""
    low = final.lower()
    if task_id == "cal1_screening":
        ns = _numbers(final)
        return any(abs(n - 0.0593) <= 0.0002 for n in ns) or any(
            abs(n - 5.93) <= 0.02 for n in ns
        )
    if task_id == "cal1_constrained_min":
        ns = _numbers(final)
        # The trap answer is 4 (the unconstrained minimum). Only 8 is correct.
        return bool(ns) and any(abs(n - 8.0) < 1e-9 for n in ns)
    if task_id == "cal1_domain_trap":
        if re.search(r"\bno\s+(real\s+)?solution", low) or "none" in low or "empty" in low:
            return True
        # Stating x = 3 as a solution is exactly the failure the task probes.
        return False
    raise KeyError(task_id)


def main() -> int:
    client = ModelClient(
        ModelConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS)
    )
    info = client.describe()
    live = (info.get("digest") or "").replace("sha256:", "")
    if live != PINNED_DIGEST:
        print(f"REFUSING TO RUN: live digest {live} != pinned {PINNED_DIGEST}")
        return 1

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    records = []
    correct = 0
    for task in TASKS:
        t0 = time.time()
        c = client.complete(SYSTEM, task.prompt)
        final = extract_final(c.content)
        ok = score(task.id, final)
        correct += ok
        records.append(
            {
                **asdict(task),
                "final_answer": final,
                "correct": ok,
                "completion_tokens": c.completion_tokens,
                "prompt_tokens": c.prompt_tokens,
                "latency_s": round(time.time() - t0, 2),
                "full_response": c.content,
                "finish_reason": c.finish_reason,
                "error": c.error,
            }
        )
        print(f"{task.id:24} band={task.intended_band:8} correct={ok}  -> {final[:70]!r}")

    doc = {
        "stage": "CAL-1",
        "arm": "STRUCTURED_ENGLISH_ONLY",
        "model": MODEL,
        "digest": live,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "calls": len(TASKS),
        "correct": correct,
        "total": len(TASKS),
        "records": records,
    }
    path = out_dir / "CAL1.json"
    path.write_text(json.dumps(doc, indent=2))
    print(f"\nCAL-1: {correct}/{len(TASKS)} correct. Gemma calls used: {len(TASKS)}")
    print(f"-> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
