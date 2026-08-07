"""CAL-2 — substantially harder structured-English tasks (directive §2C).

CAL-1 returned **3/3**, including the domain-restriction trap that was predicted to be the
hardest of the three. The rule for that outcome is explicit: move substantially harder.

These five are a real step up. Each still fails, when it fails, for a *semantic* reason
rather than an arithmetic one — dependence structure, quantifier order, a non-obvious
binding constraint, unit tracking, and extraneous roots — because a task whose difficulty
is long multiplication would say nothing about a reasoning notation.

**Every answer key was verified independently with SymPy before any model call** (§2B: no
answer key may be trusted without independent checking). The verification is reproduced in
`KEY_VERIFICATION` below.

A scorer self-test runs before the first call (§15). The previous project repeatedly found
scoring defects, and a scorer bug discovered after scientific calls invalidates the run.
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

KEY_VERIFICATION = {
    "cal2_urn_conditional": "binomial(7,2)*binomial(5,1) / (C(12,3)-C(7,3)) = 21/37",
    "cal2_quantifier_order": "S1 true (y=sqrt(|x|)+1); S2 false (take x=y^2)",
    "cal2_two_constraints": "projection of (4,3) onto x+y=5 is (3,2), feasible, f=2",
    "cal2_units": "A=pi*0.12^2=0.0452389 m^2; Q=0.0075 m^3/s; v=0.165786 m/s",
    "cal2_extraneous": "sympy.solve(sqrt(2x+7)=x+2) -> [1]; x=-3 fails x+2>=0",
}


@dataclass(frozen=True)
class Task:
    id: str
    domain: str
    error_class: str
    prompt: str
    key: str


TASKS: list[Task] = [
    Task(
        "cal2_urn_conditional",
        "probability",
        "conditional dependence without replacement",
        "A box contains 7 red balls and 5 blue balls. Three balls are drawn at random "
        "without replacement.\n\n"
        "Given that at least one blue ball was drawn, what is the probability that "
        "exactly two of the three drawn balls are red?\n\n"
        "Give the final answer as an exact fraction in lowest terms.",
        "21/37",
    ),
    Task(
        "cal2_quantifier_order",
        "logic / quantifier scope",
        "quantifier order",
        "Consider these two statements about real numbers.\n\n"
        "S1: for every real number x, there exists a real number y such that y^2 > x.\n"
        "S2: there exists a real number y such that for every real number x, y^2 > x.\n\n"
        "Exactly which of S1 and S2 are true?\n\n"
        "Give the final answer as one of: both, neither, S1 only, S2 only.",
        "S1 only",
    ),
    Task(
        "cal2_two_constraints",
        "optimisation",
        "non-obvious binding constraint",
        "Minimise f(x, y) = (x - 4)^2 + (y - 3)^2 over real x and y, subject to all "
        "three constraints:\n\n"
        "    x + y <= 5\n    x >= 0\n    y >= 0\n\n"
        "Give the final answer as a single number: the minimum VALUE of f.",
        "2",
    ),
    Task(
        "cal2_units",
        "dimensions",
        "unit tracking across steps",
        "Water flows through a pipe of circular cross-section with radius 12 cm.\n"
        "The volumetric flow rate is 0.45 cubic metres per minute.\n\n"
        "What is the average speed of the water, in metres per second?\n\n"
        "Give the final answer as a decimal in m/s rounded to four decimal places.",
        "0.1658",
    ),
    Task(
        "cal2_extraneous",
        "algebra",
        "extraneous roots + domain",
        "Find every real number x satisfying\n\n"
        "    sqrt(2x + 7) = x + 2\n\n"
        "Give the final answer as the complete list of solutions, or the words: "
        "no solution.",
        "1",
    ),
]


def _numbers(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s.replace(",", ""))]


def score(task_id: str, final: str) -> bool:
    """Conservative scoring. Unparseable is WRONG, never generously reinterpreted."""
    low = final.lower().strip()
    if task_id == "cal2_urn_conditional":
        if re.search(r"\b21\s*/\s*37\b", low):
            return True
        ns = _numbers(low)
        return any(abs(n - 21 / 37) <= 0.0005 for n in ns)
    if task_id == "cal2_quantifier_order":
        # Must name S1 alone. "both"/"S2 only"/"neither" are the failure modes.
        if "s1 only" in low or re.fullmatch(r"s1\.?", low):
            return True
        return bool(re.search(r"\bs1\b", low)) and not re.search(r"\bs2\b", low)
    if task_id == "cal2_two_constraints":
        ns = _numbers(low)
        return bool(ns) and any(abs(n - 2.0) < 1e-9 for n in ns)
    if task_id == "cal2_units":
        ns = _numbers(low)
        return any(abs(n - 0.165786) <= 0.0002 for n in ns)
    if task_id == "cal2_extraneous":
        if "no solution" in low:
            return False
        ns = _numbers(low)
        # x = 1 and ONLY x = 1. Listing -3 is the extraneous-root failure.
        return ns == [1.0] or (set(ns) == {1.0})
    raise KeyError(task_id)


#: (task, synthetic final answer, expected verdict). Runs before any model call.
SCORER_SELFTEST = [
    ("cal2_urn_conditional", "21/37", True),
    ("cal2_urn_conditional", "0.5676", True),
    ("cal2_urn_conditional", "105/220", False),
    ("cal2_quantifier_order", "S1 only", True),
    ("cal2_quantifier_order", "both", False),
    ("cal2_quantifier_order", "S2 only", False),
    ("cal2_two_constraints", "2", True),
    ("cal2_two_constraints", "0", False),
    ("cal2_units", "0.1658 m/s", True),
    ("cal2_units", "9.9472", False),
    ("cal2_extraneous", "x = 1", True),
    ("cal2_extraneous", "x = -3, x = 1", False),
    ("cal2_extraneous", "no solution", False),
    ("cal2_extraneous", "", False),
]


def selftest() -> bool:
    bad = [
        (tid, ans, want, score(tid, ans))
        for tid, ans, want in SCORER_SELFTEST
        if score(tid, ans) is not want
    ]
    for tid, ans, want, got in bad:
        print(f"  SCORER DEFECT {tid}: {ans!r} -> {got}, expected {want}")
    return not bad


def main() -> int:
    print("scorer self-test (before any model call):")
    if not selftest():
        print("REFUSING TO RUN: scorer defect. Fix before spending scientific calls.")
        return 1
    print(f"  {len(SCORER_SELFTEST)}/{len(SCORER_SELFTEST)} cases correct\n")

    client = ModelClient(
        ModelConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS)
    )
    live = (client.describe().get("digest") or "").replace("sha256:", "")
    if live != PINNED_DIGEST:
        print(f"REFUSING TO RUN: live digest {live} != pinned")
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
                "final_answer": final,
                "correct": ok,
                "completion_tokens": c.completion_tokens,
                "prompt_tokens": c.prompt_tokens,
                "latency_s": round(time.time() - t0, 2),
                "finish_reason": c.finish_reason,
                "full_response": c.content,
            }
        )
        print(f"{task.id:24} {task.domain:22} correct={ok}  -> {final[:52]!r}")

    out = Path(__file__).resolve().parent / "results" / "CAL2.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "stage": "CAL-2",
                "arm": "STRUCTURED_ENGLISH_ONLY",
                "model": MODEL,
                "digest": live,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "key_verification": KEY_VERIFICATION,
                "scorer_selftest_cases": len(SCORER_SELFTEST),
                "calls": len(TASKS),
                "correct": correct,
                "total": len(TASKS),
                "records": records,
            },
            indent=2,
        )
    )
    print(f"\nCAL-2: {correct}/{len(TASKS)} correct. Gemma calls this stage: {len(TASKS)}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
