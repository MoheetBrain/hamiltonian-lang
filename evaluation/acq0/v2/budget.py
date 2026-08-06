"""Re-measure the ACQ0 prompt budget against the frozen runtime.

The target and the corpus both changed, so every earlier token count is obsolete. The rule
this module enforces is the one v1 broke: **the probe and the scientific run must build the
same bytes.** v1 measured a 5,893-token figure on legacy material and carried it forward as
though it described the real curriculum, and 56 of 76 generations then hit the completion
cap.

`build_prompt` is the only prompt builder. Nothing here shortens, truncates or samples a
prompt: the measurement is of what will actually be sent, or it is worthless.

Selection rule (from the directive): render all twelve prompts per surface offline, take the
longest, and additionally measure every prompt within 2% of it. Measuring only the longest
would miss a prompt whose character count is slightly lower but whose tokenisation is worse
-- and candidate D's JSON is exactly the shape where that happens.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from evaluation.corpus_governance.v2_render import SUPPORTED_SURFACES

from .prompt import (
    CEILING,
    COMPLETION_ALLOWANCE,
    SAFETY_RESERVE,
    SLOT_CONTEXT,
    build_prompt,
    prompt_hash,
)

__all__ = ["PromptMeasurement", "SurfaceBudget", "select_prompts", "measure_surface",
           "RESULTS", "TOTAL_CONTEXT", "PARALLEL_SLOTS"]

TOTAL_CONTEXT = 32768
PARALLEL_SLOTS = 2
RESULTS = Path(__file__).resolve().parents[3] / "evaluation" / "results" / "acq0" / "v2_budget"


@dataclass(frozen=True)
class PromptMeasurement:
    task_id: str
    surface: str
    characters: int
    prompt_hash: str
    bundle_hash: str
    prompt_eval_count: int = 0
    headroom: int = 0
    fits: bool = False
    error: str = ""


@dataclass(frozen=True)
class SurfaceBudget:
    surface: str
    measured: tuple[PromptMeasurement, ...]

    @property
    def worst(self) -> PromptMeasurement:
        return max(self.measured, key=lambda m: m.prompt_eval_count)

    @property
    def fits(self) -> bool:
        return all(m.fits for m in self.measured) and bool(self.measured)

    def render(self) -> str:
        w = self.worst
        verdict = "FITS" if self.fits else "EXCEEDS"
        return (f"{self.surface:34s} worst {w.prompt_eval_count:6d} tok "
                f"({w.task_id}) + {COMPLETION_ALLOWANCE} + {SAFETY_RESERVE} "
                f"= {w.prompt_eval_count + COMPLETION_ALLOWANCE + SAFETY_RESERVE:6d} "
                f"/ {SLOT_CONTEXT}  headroom {w.headroom:5d}  {verdict}")


def select_prompts(tasks, surface: str, *, tolerance: float = 0.02
                   ) -> list[tuple[Any, str]]:
    """The longest prompt, plus every prompt within `tolerance` of it, by characters."""
    rendered = [(task, build_prompt(task, surface)) for task in tasks]
    longest = max(len(text) for _, text in rendered)
    cutoff = longest * (1.0 - tolerance)
    return [(task, text) for task, text in rendered if len(text) >= cutoff]


def measure_surface(tasks, surface: str, adapter, *, bundle_hash_of=None) -> SurfaceBudget:
    """Measure the authoritative `prompt_eval_count` for the selected prompts.

    `adapter` must be an object with `.generate(system, user)` returning an object carrying
    `prompt_tokens`. One token of completion is requested: the point is the prompt count,
    and generating more would change nothing about it while costing minutes.
    """
    out: list[PromptMeasurement] = []
    for task, text in select_prompts(tasks, surface):
        bundle_hash = bundle_hash_of(task, surface) if bundle_hash_of else ""
        try:
            gen = adapter.generate("", text)
        except Exception as exc:  # noqa: BLE001 - a transport failure must be recorded
            out.append(PromptMeasurement(
                task.task_id, surface, len(text), prompt_hash(text), bundle_hash,
                error=f"{type(exc).__name__}: {exc}"))
            continue
        count = gen.prompt_tokens
        headroom = CEILING - count
        out.append(PromptMeasurement(
            task_id=task.task_id, surface=surface, characters=len(text),
            prompt_hash=prompt_hash(text), bundle_hash=bundle_hash,
            prompt_eval_count=count, headroom=headroom,
            fits=count + COMPLETION_ALLOWANCE + SAFETY_RESERVE <= SLOT_CONTEXT))
    return SurfaceBudget(surface, tuple(out))


def write_report(budgets: list[SurfaceBudget], path: Path | None = None) -> Path:
    path = path or (RESULTS / "budget.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "runtime": {"total_context": TOTAL_CONTEXT, "parallel_slots": PARALLEL_SLOTS,
                    "slot_context": SLOT_CONTEXT,
                    "completion_allowance": COMPLETION_ALLOWANCE,
                    "safety_reserve": SAFETY_RESERVE, "ceiling": CEILING},
        "surfaces": {b.surface: {"fits": b.fits,
                                 "measurements": [asdict(m) for m in b.measured]}
                     for b in budgets},
        "all_fit": all(b.fits for b in budgets),
        "surfaces_measured": [s for s in SUPPORTED_SURFACES],
    }, indent=2))
    return path
