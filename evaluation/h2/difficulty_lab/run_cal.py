"""CAL-S runner — structured-English only, synthetic tasks (directive §7).

A NEW protocol. Its results must not be merged with the previous calibration's accuracy
estimate: that one measured canonical textbook traps, this one measures machine-generated
interacting state, and averaging two different instruments produces a number about
neither.

Calibration seeds live in a reserved high band so a calibration instance can never
silently reappear in the paired pilot.

`finish_reason == "length"` is recorded as **INVALID**, never as incorrect. Truncation is
not a mathematical failure, and counting it as one is how a corpus manufactures headroom
it does not have.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from evaluation.h2.difficulty_lab.families import GENERATOR_VERSION, generate  # noqa: E402
from evaluation.h2.difficulty_lab.scorer import (  # noqa: E402
    SCORER_VERSION,
    extract_final,
    score,
)
from evaluation.model_client import ModelClient, ModelConfig  # noqa: E402

MODEL = "gemma4:31b"
PINNED_DIGEST = "6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7"
TEMPERATURE = 0.0
MAX_TOKENS = 8192

#: Reserved seed band for calibration. Pilot tasks draw from a disjoint band.
CALIBRATION_SEED_BASE = 900_000

SYSTEM = """You are solving a mathematics problem.

Work carefully but concisely. Track the given facts; some may be irrelevant.
Do not restate the problem. Do not pad your reasoning.

End your response with exactly one line of the form:
FINAL: <answer>"""


def run(stage: str, plan: list[tuple[str, str, int]]) -> int:
    client = ModelClient(
        ModelConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS)
    )
    live = (client.describe().get("digest") or "").replace("sha256:", "")
    if live != PINNED_DIGEST:
        print(f"REFUSING TO RUN: live digest {live} != pinned")
        return 1

    records, correct, valid = [], 0, 0
    for family, level, seed in plan:
        spec = generate(family, level, CALIBRATION_SEED_BASE + seed)
        t0 = time.time()
        c = client.complete(SYSTEM, spec.prompt)
        final = extract_final(c.content)
        truncated = c.finish_reason == "length"
        ok = score(spec.answer, final, spec.answer_format) if not truncated else None
        if not truncated:
            valid += 1
            correct += bool(ok)
        records.append(
            {
                **spec.to_dict(),
                "final_answer": final,
                "correct": ok,
                "truncated": truncated,
                "completion_tokens": c.completion_tokens,
                "latency_s": round(time.time() - t0, 1),
                "finish_reason": c.finish_reason,
                "full_response": c.content,
            }
        )
        flag = "INVALID(truncated)" if truncated else ("correct" if ok else "WRONG")
        print(
            f"{spec.family:28} {level}  {flag:18} "
            f"got={final[:22]!r:26} want={spec.answer!r:14} tok={c.completion_tokens}"
        )

    out = Path(__file__).resolve().parent / f"{stage}.json"
    out.write_text(
        json.dumps(
            {
                "protocol": "CAL-S (synthetic difficulty lab)",
                "stage": stage,
                "arm": "STRUCTURED_ENGLISH_ONLY",
                "generator_version": GENERATOR_VERSION,
                "scorer_version": SCORER_VERSION,
                "model": MODEL,
                "digest": live,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "calls": len(plan),
                "valid": valid,
                "correct": correct,
                "records": records,
            },
            indent=2,
        )
    )
    print(f"\n{stage}: {correct}/{valid} correct on valid observations "
          f"({len(plan) - valid} truncated, invalid). Calls: {len(plan)}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "CAL_S1"
    plans = {
        # CAL-S1: three L3 tasks from three different families (§7).
        "CAL_S1": [
            ("ALGEBRAIC_DEPENDENCY_GRAPH", "L3", 1),
            ("FINITE_LOGIC_WORLD", "L3", 2),
            ("FINITE_QUANTIFIER_WORLD", "L3", 3),
        ],
        "CAL_S2_L5": [
            ("ALGEBRAIC_DEPENDENCY_GRAPH", "L5", 11),
            ("MIXED_STATE_COMPOSITION", "L5", 12),
            ("FINITE_LOGIC_WORLD", "L5", 13),
        ],
        "CAL_S3_L7": [
            ("ALGEBRAIC_DEPENDENCY_GRAPH", "L7", 31),
            ("MIXED_STATE_COMPOSITION", "L7", 32),
            ("FINITE_LOGIC_WORLD", "L7", 33),
        ],
        "CAL_S3_L6": [
            ("ALGEBRAIC_DEPENDENCY_GRAPH", "L6", 41),
            ("MIXED_STATE_COMPOSITION", "L6", 42),
            ("FINITE_LOGIC_WORLD", "L6", 43),
        ],
        "CAL_S2_L4": [
            ("ALGEBRAIC_DEPENDENCY_GRAPH", "L4", 21),
            ("MIXED_STATE_COMPOSITION", "L4", 22),
            ("FINITE_LOGIC_WORLD", "L4", 23),
        ],
    }
    raise SystemExit(run(stage, plans[stage]))
