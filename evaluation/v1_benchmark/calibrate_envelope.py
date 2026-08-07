"""Measure the real prompt-token cost of this benchmark's largest envelopes.

Ollama 0.32.5 exposes no tokenizer endpoint, so a character estimate is the only thing
available offline. This module replaces the estimate with a measurement for the envelopes
that actually decide the slot, by issuing calls with ``max_tokens=1`` and reading
``usage.prompt_tokens`` back.

Those calls generate one token each. They are **not** scientific data and they cannot
contaminate scientific data: the adapter's cache key includes ``max_tokens``, so a
calibration call at ``max_tokens=1`` occupies a different key from every run call at 4096
and can never be replayed in place of one.

Run:
    .venv/bin/python -m evaluation.v1_benchmark.calibrate_envelope
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from evaluation.corpus.renderers import HML_SPEC
from evaluation.model_adapters.ollama import OllamaAdapter, OllamaConfig
from evaluation.v1_benchmark.arms import (
    MODEL,
    MODEL_DIGEST,
    TEMPERATURE,
    hml_initial_prompt,
    hml_repair_prompt,
    se_initial_prompt,
    se_review_prompt,
)
from evaluation.v1_benchmark.diagnostics_budget import bound_diagnostics
from evaluation.v1_benchmark.envelope import (
    RESERVE_TOKENS,
    _ceiling_body,
    _ceiling_module,
    render_envelopes,
)
from evaluation.v1_benchmark.protocol_v1_2 import (
    PER_CALL_COMPLETION_ALLOWANCE,
    PER_SLOT_CONTEXT,
)
from evaluation.v1_benchmark.tasks import build_tasks

#: Measured against this model's tokeniser on this benchmark's own prompts. English prose
#: and HML-like source tokenise at materially different densities, and using one figure for
#: both is what made the first calibration attempt incoherent.
ENGLISH_CHARS_PER_TOKEN = 4.4
HML_CHARS_PER_TOKEN = 3.0

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "evaluation" / "results" / "v1_benchmark" / "ENVELOPE_CALIBRATION.json"
CACHE = REPO / "evaluation" / "results" / "v1_benchmark" / "calibration_cache"


def measure(system: str, user: str, adapter: OllamaAdapter) -> int:
    gen = adapter.generate(system, user)
    if gen.error:
        raise RuntimeError(f"calibration call failed: {gen.error}")
    if not gen.prompt_tokens:
        raise RuntimeError("server reported no prompt_tokens; cannot calibrate")
    return gen.prompt_tokens


def main() -> int:
    tasks = build_tasks()
    cfg = OllamaConfig(
        model=MODEL, temperature=TEMPERATURE, max_tokens=1, seed=0, timeout_s=300
    )
    adapter = OllamaAdapter(cfg, cache_dir=CACHE)
    if adapter.digest != MODEL_DIGEST:
        print(
            f"REFUSED: live digest {adapter.digest} != pinned {MODEL_DIGEST}",
            file=sys.stderr,
        )
        return 2

    # Fillers are sized in TOKENS at the ratio each text shape actually measures against
    # this tokeniser (English ~4.4, HML-like source ~3.0). Sizing them in characters at an
    # invented ratio produced a body larger than the allowance permits -- a bound that was
    # not conservative but incoherent. See `envelope._ceiling_body`.
    envelopes = render_envelopes(
        tasks,
        allowance=PER_CALL_COMPLETION_ALLOWANCE,
        surface=HML_SPEC,
        chars_per_token=ENGLISH_CHARS_PER_TOKEN,
    )
    per_shape: dict[tuple[str, str], Any] = {}
    for e in envelopes:
        k = (e.arm, e.stage)
        if k not in per_shape or e.chars > per_shape[k].chars:
            per_shape[k] = e

    rows: list[dict[str, Any]] = []
    for (arm, stage), e in sorted(per_shape.items()):
        # Re-render the exact winning task so the measured bytes are the rendered bytes.
        task = next(t for t in tasks if t.id == e.task_id)
        carried = _ceiling_body(
            PER_CALL_COMPLETION_ALLOWANCE, chars_per_token=ENGLISH_CHARS_PER_TOKEN
        )
        module = _ceiling_module(
            PER_CALL_COMPLETION_ALLOWANCE, chars_per_token=HML_CHARS_PER_TOKEN
        )
        # Diagnostics are capped by the v1.2 budget, so the ceiling is the cap itself and
        # not some multiple of the module. A raw render is passed through the bound exactly
        # as the driver will pass it.
        diags = bound_diagnostics(
            _ceiling_body(100_000, chars_per_token=HML_CHARS_PER_TOKEN)
        ).text

        if (arm, stage) == ("SE", "initial"):
            p = se_initial_prompt(task.cso)
        elif (arm, stage) == ("SE", "review"):
            p = se_review_prompt(task.cso, carried)
        elif (arm, stage) == ("HML-V1", "initial"):
            p = hml_initial_prompt(task.cso, surface_spec=HML_SPEC)
        else:
            p = hml_repair_prompt(task.cso, module, diags, surface_spec=HML_SPEC)

        tokens = measure(p.system, p.user, adapter)
        chars = len(p.system) + len(p.user)
        required = tokens + PER_CALL_COMPLETION_ALLOWANCE + RESERVE_TOKENS
        rows.append(
            {
                "arm": arm,
                "stage": stage,
                "task_id": e.task_id,
                "synthetic_carry": e.synthetic_carry,
                "chars": chars,
                "measured_prompt_tokens": tokens,
                "chars_per_token": round(chars / tokens, 3),
                "required_total": required,
                "per_slot_context": PER_SLOT_CONTEXT,
                "headroom": PER_SLOT_CONTEXT - required,
                "fits": required <= PER_SLOT_CONTEXT,
            }
        )
        print(
            f"{arm:7s} {stage:8s} {e.task_id:34s} chars={chars:6d} "
            f"tokens={tokens:6d} req={required:6d} headroom={PER_SLOT_CONTEXT - required:6d} "
            f"{'FITS' if required <= PER_SLOT_CONTEXT else 'EXCEEDS'}"
        )

    report = {
        "model": MODEL,
        "digest": adapter.digest,
        "per_call_completion_allowance": PER_CALL_COMPLETION_ALLOWANCE,
        "reserve_tokens": RESERVE_TOKENS,
        "per_slot_context": PER_SLOT_CONTEXT,
        "rule": "measured_prompt_tokens + allowance + reserve <= per_slot_context",
        "note": (
            "Call-two rows are upper bounds. The carried body is synthetic and sized as a "
            "completion that consumed the entire allowance, and the HML module filler is "
            "denser than the ratio used to size it, so the measured repair envelope stands "
            "for a module LARGER than the 4096-token allowance can produce. The bound is "
            "therefore conservative in the safe direction. Diagnostics are at the v1.2 cap."
        ),
        "english_chars_per_token": ENGLISH_CHARS_PER_TOKEN,
        "hml_chars_per_token": HML_CHARS_PER_TOKEN,
        "all_fit": all(r["fits"] for r in rows),
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2))
    print(f"\nall_fit={report['all_fit']}  ->  {OUT.relative_to(REPO)}")
    return 0 if report["all_fit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
