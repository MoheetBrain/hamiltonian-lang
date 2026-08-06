"""The frozen ACQ0 v2 prompt assembly. One builder, used by the probe and the run.

If the probe measured a different string from the one sent, the budget would be a fiction.
That is the v1 failure -- the 5,893-token figure was measured on legacy material and
carried forward as though it described the real curriculum.
"""

from __future__ import annotations

import hashlib
import json

from evaluation.corpus_governance.v2_corpus import PROOF_CORPUS
from evaluation.corpus_governance.v2_render import acq0_view, render_surface
from evaluation.syntax_gate import prompts as _spec

__all__ = ["DEMONSTRATIONS", "build_prompt", "prompt_hash", "COMPLETION_ALLOWANCE",
           "SAFETY_RESERVE", "SLOT_CONTEXT", "CEILING"]

#: The five frozen demonstrations, in frozen order. A task never demonstrates itself.
DEMONSTRATIONS = PROOF_CORPUS[:5]

COMPLETION_ALLOWANCE = 6144
SAFETY_RESERVE = 256
SLOT_CONTEXT = 16384          # 2 slots x 16384; the server is fixed at -c 32768 -np 2
CEILING = SLOT_CONTEXT - COMPLETION_ALLOWANCE - SAFETY_RESERVE   # 9984


def build_prompt(task, surface: str) -> str:
    """Exactly what is sent. No hidden material: no reference, no hash, no answer key."""
    view = acq0_view(task)
    demos = "\n\n".join(
        f"### {d.task_id}\n{render_surface(d, surface)}"
        for d in DEMONSTRATIONS if d.task_id != task.task_id
    )
    return (
        f"{view['instruction']}\n\n"
        f"=== SURFACE SPECIFICATION ===\n{_spec.render_spec(surface)}\n\n"
        f"=== DEMONSTRATIONS ===\n{demos}\n\n"
        f"=== TASK ===\n{view['prose']}\n\n"
        f"STRUCTURED TARGET:\n{json.dumps(view['structured_target'], indent=2)}\n\n"
        f"Output only the encoding in the assigned surface.\n"
    )


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
