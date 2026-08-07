"""CAL-3 — the last four calibration calls (directive §2C).

CAL-1 returned 3/3 and CAL-2 returned 5/5. Eight for eight, none truncated (877–2392
completion tokens against an 8192 allowance, every one `finish=stop`), so the model is
not budget-limited: those task *patterns* are simply within its ability.

That matters for how these four are designed. CAL-1 and CAL-2 used the classic
semantic-trap genre — Bayes screening, extraneous roots, an infeasible unconstrained
optimum, quantifier order. Those patterns appear in training data in enormous quantity,
and novel constants do not make a memorised *pattern* novel.

So these four are hard in **kind** rather than in degree:

* sustained multi-step composition, where one early slip propagates and there is no
  shortcut to the answer;
* no recognisable trap to pattern-match;
* every key settled by **exhaustive computation**, not by a closed form I might get wrong.

This is the last of the 13-call calibration budget. If these saturate too, the honest
finding is that this task-generation approach cannot produce headroom for this model, and
the directive's answer is to stop rather than to spend another forty calls.
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluation.calibration.cal1 import (  # noqa: E402
    MAX_TOKENS,
    MODEL,
    PINNED_DIGEST,
    SYSTEM,
    TEMPERATURE,
    extract_final,
)
from evaluation.model_client import ModelClient, ModelConfig  # noqa: E402

#: Every key below was produced by exhaustive enumeration, reproduced in
#: `verify_keys()`, which runs before any model call.
KEYS = {
    "cal3_adjacent_sum": 2244,
    "cal3_reflecting_walk": "1/4",
    "cal3_lp_vertices": 24,
    "cal3_floor_identity": 24,
}


def verify_keys() -> bool:
    """Recompute every key by brute force. Runs before spending any call."""
    from fractions import Fraction
    from itertools import product

    ok = True
    n = sum(
        1
        for s in product(range(1, 8), repeat=5)
        if all(s[i] != s[i + 1] for i in range(4)) and sum(s) % 4 == 0
    )
    ok &= n == KEYS["cal3_adjacent_sum"]

    dist = {0: Fraction(1)}
    for _ in range(4):
        nd: dict[int, Fraction] = {}
        for st, p in dist.items():
            up, dn = min(st + 1, 3), max(st - 1, 0)
            nd[up] = nd.get(up, Fraction(0)) + p / 2
            nd[dn] = nd.get(dn, Fraction(0)) + p / 2
        dist = nd
    ok &= str(dist.get(2)) == KEYS["cal3_reflecting_walk"]

    best = min(
        3 * x + 5 * y
        for x in [i / 2 for i in range(41)]
        for y in [i / 2 for i in range(41)]
        if x + y >= 8 and 2 * x + y >= 10
    )
    ok &= abs(best - KEYS["cal3_lp_vertices"]) < 1e-9

    c = sum(1 for k in range(1, 2001) if k // 7 + k // 11 == k // 5)
    ok &= c == KEYS["cal3_floor_identity"]
    return bool(ok)


@dataclass(frozen=True)
class Task:
    id: str
    domain: str
    why_hard: str
    prompt: str


TASKS: list[Task] = [
    Task(
        "cal3_adjacent_sum",
        "combinatorics",
        "two interacting constraints; no closed form; requires systematic counting",
        "Consider strings of length 5 in which each character is one of the digits "
        "1, 2, 3, 4, 5, 6, 7 (repetition allowed).\n\n"
        "Count the strings that satisfy BOTH of the following:\n"
        "  (a) no two adjacent characters are equal;\n"
        "  (b) the sum of the five digits is divisible by 4.\n\n"
        "Give the final answer as a single integer.",
    ),
    Task(
        "cal3_reflecting_walk",
        "probability",
        "four-step state evolution with reflecting boundaries at both ends",
        "A particle moves on the positions 0, 1, 2, 3.\n"
        "It starts at position 0.\n"
        "At each step it attempts to move up by 1 with probability 1/2, and down by 1 "
        "with probability 1/2.\n"
        "An attempt to move below 0 leaves it at 0. An attempt to move above 3 leaves "
        "it at 3.\n\n"
        "After exactly 4 steps, what is the probability that the particle is at "
        "position 2?\n\n"
        "Give the final answer as an exact fraction in lowest terms.",
    ),
    Task(
        "cal3_lp_vertices",
        "optimisation",
        "the optimum is at an axis vertex, not the intersection of the two constraints",
        "Minimise 3x + 5y over real x and y, subject to all four constraints:\n\n"
        "    x + y >= 8\n    2x + y >= 10\n    x >= 0\n    y >= 0\n\n"
        "Give the final answer as a single number: the minimum VALUE of 3x + 5y.",
    ),
    Task(
        "cal3_floor_identity",
        "number theory",
        "no pattern; requires reasoning about floor behaviour over a large range",
        "For how many integers n with 1 <= n <= 2000 does\n\n"
        "    floor(n/7) + floor(n/11) = floor(n/5)\n\n"
        "hold, where floor(z) is the greatest integer not exceeding z?\n\n"
        "Give the final answer as a single integer.",
    ),
]


def _numbers(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s.replace(",", ""))]


def score(task_id: str, final: str) -> bool:
    low = final.lower().strip()
    if task_id == "cal3_reflecting_walk":
        if re.search(r"\b1\s*/\s*4\b", low):
            return True
        ns = _numbers(low)
        return any(abs(n - 0.25) < 1e-6 for n in ns)
    want = KEYS[task_id]
    ns = _numbers(low)
    return bool(ns) and any(abs(n - float(want)) < 1e-9 for n in ns)


SCORER_SELFTEST = [
    ("cal3_adjacent_sum", "2244", True),
    ("cal3_adjacent_sum", "2240", False),
    ("cal3_adjacent_sum", "", False),
    ("cal3_reflecting_walk", "1/4", True),
    ("cal3_reflecting_walk", "0.25", True),
    ("cal3_reflecting_walk", "3/8", False),
    ("cal3_lp_vertices", "24", True),
    ("cal3_lp_vertices", "36", False),
    ("cal3_floor_identity", "24", True),
    ("cal3_floor_identity", "0", False),
]


def main() -> int:
    print("key verification by exhaustive enumeration:", "OK" if verify_keys() else "FAILED")
    if not verify_keys():
        return 1
    bad = [(t, a, w) for t, a, w in SCORER_SELFTEST if score(t, a) is not w]
    print(f"scorer self-test: {len(SCORER_SELFTEST) - len(bad)}/{len(SCORER_SELFTEST)}")
    if bad:
        print("  REFUSING TO RUN:", bad)
        return 1

    client = ModelClient(
        ModelConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS)
    )
    live = (client.describe().get("digest") or "").replace("sha256:", "")
    if live != PINNED_DIGEST:
        print("REFUSING TO RUN: digest mismatch")
        return 1

    records, correct = [], 0
    for task in TASKS:
        t0 = time.time()
        c = client.complete(SYSTEM, task.prompt)
        final = extract_final(c.content)
        ok = score(task.id, final)
        correct += ok
        records.append(
            {
                **asdict(task),
                "key": str(KEYS[task.id]),
                "final_answer": final,
                "correct": ok,
                "completion_tokens": c.completion_tokens,
                "latency_s": round(time.time() - t0, 2),
                "finish_reason": c.finish_reason,
                "full_response": c.content,
            }
        )
        print(f"{task.id:24} {task.domain:16} correct={ok}  -> {final[:40]!r}")

    out = Path(__file__).resolve().parent / "results" / "CAL3.json"
    out.write_text(
        json.dumps(
            {
                "stage": "CAL-3",
                "arm": "STRUCTURED_ENGLISH_ONLY",
                "model": MODEL,
                "digest": live,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "keys_verified_by": "exhaustive enumeration in verify_keys()",
                "calls": len(TASKS),
                "correct": correct,
                "total": len(TASKS),
                "records": records,
            },
            indent=2,
        )
    )
    print(f"\nCAL-3: {correct}/{len(TASKS)} correct. Calls this stage: {len(TASKS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
