"""Offline prompt-envelope rendering, and the context-slot arithmetic it feeds.

Why this module exists
----------------------
Developmental protocol v1.2 raises the per-call completion allowance from 1024 to 4096.
That is a fourfold increase in the space a completion may occupy, and the second call of
both arms *carries the first call's output forward*. So raising the allowance enlarges the
call-two prompt as well, and a budget that fits at 1024 can silently stop fitting at 4096.

The failure it prevents is specific and has already happened once in this project (see
``docs/evaluation/ACQ0_CONTEXT_BUDGET.md`` §"transport failures"): a prompt that exceeds
the slot does not raise, it *truncates*, and a truncated prompt produces a real-looking
completion derived from a mutilated question. That is measurement-invalid data that looks
exactly like measurement-valid data.

The rule, from the amendment
----------------------------
For every arm and every call::

    prompt_envelope + PER_CALL_COMPLETION_ALLOWANCE + RESERVE <= per_slot_context

Rendering is **conservative and offline**. The call-two envelope cannot be known exactly
before call one runs, so it is bounded above rather than guessed: the carried body is
modelled as a completion that used the entire allowance. That upper bound is what the
arithmetic is checked against, so the check holds for every run this protocol can produce,
not merely for the run we happened to observe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evaluation.corpus.renderers import HML_SPEC
from evaluation.v1_benchmark.arms import (
    Arm,
    hml_initial_prompt,
    hml_repair_prompt,
    se_initial_prompt,
    se_review_prompt,
)
from evaluation.v1_benchmark.tasks import BenchTask

__all__ = [
    "RESERVE_TOKENS",
    "Envelope",
    "render_envelopes",
    "worst_case",
    "fits",
]

#: Head-room held back from the slot on top of the completion allowance. Covers chat
#: template scaffolding, BOS/EOS, and the role framing the server adds around our text --
#: none of which appear in the strings this module renders.
RESERVE_TOKENS = 256


@dataclass(frozen=True)
class Envelope:
    """One rendered prompt, measured in characters. Tokens are attached later."""

    task_id: str
    arm: str
    stage: str
    system_chars: int
    user_chars: int
    #: True when the body carried forward was synthesised at the allowance ceiling rather
    #: than taken from a real completion. Call-two envelopes are always synthetic.
    synthetic_carry: bool
    prompt_tokens: int | None = None

    @property
    def chars(self) -> int:
        return self.system_chars + self.user_chars

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "arm": self.arm,
            "stage": self.stage,
            "system_chars": self.system_chars,
            "user_chars": self.user_chars,
            "chars": self.chars,
            "synthetic_carry": self.synthetic_carry,
            "prompt_tokens": self.prompt_tokens,
        }


def _ceiling_body(allowance: int, *, chars_per_token: float) -> str:
    """A stand-in for a completion that consumed the whole allowance.

    **Sized in tokens, not characters.** An earlier version of this function took a
    characters-per-token figure and multiplied, which produced a filler whose *own*
    tokenisation exceeded the allowance: at an assumed 5.0 chars/token the HML-shaped
    filler measured 3.0 chars/token in reality, so a body meant to stand for 4,096 tokens
    actually measured 6,800. The bound it produced was not conservative, it was incoherent
    — it modelled a completion the allowance forbids.

    ``chars_per_token`` is therefore the *measured* ratio for the text shape being
    generated, and the result is the body that costs ``allowance`` tokens at that ratio.

    Deliberately word-shaped rather than random bytes: random characters tokenise far worse
    than prose and would overstate the envelope threefold. Real carried bodies are English
    working and HML source.
    """
    target_chars = int(allowance * chars_per_token)
    unit = "the quantity satisfies the stated constraint and the bound is attained. "
    reps = target_chars // len(unit) + 1
    return (unit * reps)[:target_chars]


def _ceiling_module(allowance: int, *, chars_per_token: float) -> str:
    """A stand-in for an emitted HML module at the allowance ceiling.

    Same token-sizing contract as :func:`_ceiling_body`. HML-like source measures ~3.0
    chars/token against this model's tokeniser, materially denser than English.
    """
    target_chars = int(allowance * chars_per_token)
    unit = "let x_000 : Real = 1.0\nassume p_000 : Probability = 0.5\n"
    reps = target_chars // len(unit) + 1
    return (unit * reps)[:target_chars]


def render_envelopes(
    tasks: list[BenchTask],
    *,
    allowance: int,
    surface: str = HML_SPEC,
    chars_per_token: float = 4.0,
    diagnostics_ceiling_ratio: float = 1.0,
) -> list[Envelope]:
    """Render all four prompt shapes for every task.

    ``chars_per_token`` sizes the synthetic carried body only. It is set from the
    *measured* ratio for this model where one is available; 4.0 is the English default.
    ``diagnostics_ceiling_ratio`` bounds compiler output as a multiple of the module it
    describes -- diagnostics quote the offending source lines, so they scale with the
    module rather than being independently unbounded.
    """
    carried = _ceiling_body(allowance, chars_per_token=chars_per_token)
    module = _ceiling_module(allowance, chars_per_token=chars_per_token)
    diagnostics = _ceiling_body(
        int(allowance * diagnostics_ceiling_ratio), chars_per_token=chars_per_token
    )

    out: list[Envelope] = []
    for t in tasks:
        p = se_initial_prompt(t.cso)
        out.append(Envelope(t.id, str(Arm.SE), "initial", len(p.system), len(p.user), False))

        p = se_review_prompt(t.cso, carried)
        out.append(Envelope(t.id, str(Arm.SE), "review", len(p.system), len(p.user), True))

        p = hml_initial_prompt(t.cso, surface_spec=surface)
        out.append(
            Envelope(t.id, str(Arm.HML_V1), "initial", len(p.system), len(p.user), False)
        )

        p = hml_repair_prompt(t.cso, module, diagnostics, surface_spec=surface)
        out.append(Envelope(t.id, str(Arm.HML_V1), "repair", len(p.system), len(p.user), True))
    return out


def worst_case(envelopes: list[Envelope]) -> dict[str, Envelope]:
    """The largest envelope per arm. The comparison is made on these, not on averages."""
    out: dict[str, Envelope] = {}
    for e in envelopes:
        cur = out.get(e.arm)
        if cur is None or e.chars > cur.chars:
            out[e.arm] = e
    return out


@dataclass
class FitResult:
    per_slot_context: int
    allowance: int
    reserve: int
    rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def all_fit(self) -> bool:
        return all(r["fits"] for r in self.rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "per_slot_context": self.per_slot_context,
            "per_call_completion_allowance": self.allowance,
            "reserve_tokens": self.reserve,
            "rule": "prompt_tokens + allowance + reserve <= per_slot_context",
            "all_fit": self.all_fit,
            "rows": self.rows,
        }


def fits(
    envelopes: list[Envelope],
    *,
    per_slot_context: int,
    allowance: int,
    chars_per_token: float,
    reserve: int = RESERVE_TOKENS,
) -> FitResult:
    """Apply the amendment's inequality to every rendered envelope.

    Token counts come from ``prompt_tokens`` when a measurement is attached, and from the
    character estimate otherwise. The estimate divides by ``chars_per_token``, so a
    *smaller* ratio is the conservative direction and the caller is expected to pass a
    ratio at or below the measured one.
    """
    res = FitResult(per_slot_context=per_slot_context, allowance=allowance, reserve=reserve)
    for e in envelopes:
        tokens = e.prompt_tokens
        source = "measured"
        if tokens is None:
            tokens = int(e.chars / chars_per_token) + 1
            source = f"estimated at {chars_per_token} chars/token"
        required = tokens + allowance + reserve
        res.rows.append(
            {
                **e.to_dict(),
                "prompt_tokens_used": tokens,
                "token_source": source,
                "required": required,
                "headroom": per_slot_context - required,
                "fits": required <= per_slot_context,
            }
        )
    return res
