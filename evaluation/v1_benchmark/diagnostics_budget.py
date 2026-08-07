"""A bounded rendering of compiler diagnostics for the repair prompt.

The defect this exists to prevent
--------------------------------
:func:`evaluation.v1_benchmark.scoring.classify_diagnostics` renders the whole diagnostic
bag. That rendering is **unbounded relative to its input**. Measured on this compiler
before any scientific call was made:

===========================  ==========  ==============  =======
module                       source      rendered        ratio
===========================  ==========  ==============  =======
200 unresolved names          9,469 ch      59,760 ch      6.3x
200 parse errors              2,289 ch      52,580 ch     23.0x
200 type errors               6,289 ch      34,070 ch      5.4x
200 lines of garbage          3,199 ch     389,426 ch    121.7x
===========================  ==========  ==============  =======

389,426 characters is roughly 130,000 tokens. It overflows a 16,384-token slot by eight
times and a 32,768-token slot by four, so this is not a problem that a larger context
solves.

Why it would have corrupted the result rather than merely crashing
------------------------------------------------------------------
An over-long prompt does not raise; it truncates. The repair call would then have been made
against a mutilated prompt, and the mutilation would have been **worst exactly where the
model wrote the worst HML** — the garbage row above is the 122x row. The artefact is
therefore anti-correlated with the treatment: the HML arm would be penalised hardest on the
tasks it was already failing, and the resulting number would look like evidence about the
representation while actually being evidence about a rendering bug.

The cap, and why it is not a thumb on the scale
-----------------------------------------------
Diagnostics are truncated at a stated budget, on whole-diagnostic boundaries, with an
explicit count of what was omitted — the behaviour every production compiler has (``fatal
error: too many errors emitted``). It is decided here, before any scientific call, and it
applies to every HML trial identically.

It cannot flatter the HML arm: it can only *remove* information from the treatment, never
add any. Whenever it binds, the arm under test receives less help than it otherwise would,
so a positive HML result measured under this cap is a lower bound on the result an uncapped
run would have produced. Every record carries :attr:`BoundedDiagnostics.truncated` and
:attr:`BoundedDiagnostics.omitted` so a reviewer can count exactly how often it bound and
on which tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "DIAGNOSTICS_CHAR_CAP",
    "DIAGNOSTICS_COUNT_CAP",
    "BoundedDiagnostics",
    "bound_diagnostics",
]

#: Character ceiling on rendered diagnostics carried into the repair prompt. ~2,000 tokens
#: at the 3.0 chars/token measured for HML-like text. Chosen to be far above any realistic
#: diagnostic set for a module of the size this benchmark's tasks elicit, so that it binds
#: on pathological output only.
DIAGNOSTICS_CHAR_CAP = 6000

#: Ceiling on the number of individual diagnostics rendered. A module can emit hundreds;
#: after the first few dozen the marginal one tells the model nothing new.
DIAGNOSTICS_COUNT_CAP = 40


@dataclass(frozen=True)
class BoundedDiagnostics:
    """Rendered diagnostics, plus exactly what was withheld."""

    text: str
    total: int
    shown: int
    truncated: bool
    original_chars: int

    @property
    def omitted(self) -> int:
        return max(0, self.total - self.shown)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rendered_chars": len(self.text),
            "original_chars": self.original_chars,
            "diagnostics_total": self.total,
            "diagnostics_shown": self.shown,
            "diagnostics_omitted": self.omitted,
            "truncated": self.truncated,
            "char_cap": DIAGNOSTICS_CHAR_CAP,
            "count_cap": DIAGNOSTICS_COUNT_CAP,
        }


def bound_diagnostics(
    rendered: str,
    *,
    char_cap: int = DIAGNOSTICS_CHAR_CAP,
    count_cap: int = DIAGNOSTICS_COUNT_CAP,
) -> BoundedDiagnostics:
    """Cap a rendered diagnostic bag on whole-line boundaries.

    Truncation is never silent: when anything is withheld the returned text ends with a
    line stating how many diagnostics were omitted, so the model is told that the list it
    is looking at is partial rather than being left to assume it is complete.
    """
    original = rendered or ""
    lines = [ln for ln in original.splitlines() if ln.strip()]
    total = len(lines)

    kept: list[str] = []
    used = 0
    for ln in lines[:count_cap]:
        if used + len(ln) + 1 > char_cap:
            break
        kept.append(ln)
        used += len(ln) + 1

    truncated = len(kept) < total
    text = "\n".join(kept)
    if truncated:
        text += (
            f"\n... {total - len(kept)} further diagnostic(s) omitted; the compiler emits "
            "more than this prompt carries. Fix the errors shown first."
        )
    return BoundedDiagnostics(
        text=text or "(no diagnostics)",
        total=total,
        shown=len(kept),
        truncated=truncated,
        original_chars=len(original),
    )
