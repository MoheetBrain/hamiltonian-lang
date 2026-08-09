"""Representation parity: prove the three arms carry the same information.

`check_world` renders a world in all three arms, decodes each back, and compares
canonical forms. Anything that survives this has been shown -- not asserted -- to be a
pure re-encoding of one structure.

What parity does **not** claim: that the arms cost the same. They do not, and forcing
them to would mean distorting at least one notation into something nobody would write.
`budget.py` measures the residual difference so that a length effect can never be
mistaken for a representation effect; any result where the arms differ in accuracy *and*
in length has to be read with both numbers in view.
"""

from __future__ import annotations

from dataclasses import dataclass

from .decoders import DecodeError, decode_ast, decode_english, decode_hml, decode_sexpr
from .renderers.ast_json import AstRenderer
from .renderers.ast_sexpr import SexprRenderer
from .renderers.english import EnglishRenderer
from .renderers.hml import HmlRenderer
from .worlds import World, canonical_world

__all__ = ["ARM_RENDERERS", "ARM_DECODERS", "ParityResult", "check_world", "check_corpus"]

ARM_RENDERERS = {
    "SE": EnglishRenderer(),
    "AST": AstRenderer(),
    "AST_V2": SexprRenderer(),
    "HML": HmlRenderer(),
}

ARM_DECODERS = {
    "SE": decode_english,
    "AST": decode_ast,
    "AST_V2": decode_sexpr,
    "HML": decode_hml,
}


@dataclass
class ParityResult:
    world_id: str
    ok: bool
    #: arm -> None when it round-tripped, else the reason it did not.
    failures: dict[str, str]

    def report(self) -> str:
        if self.ok:
            return f"{self.world_id}: parity OK"
        lines = [f"{self.world_id}: PARITY FAILED"]
        for k, v in self.failures.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)


def check_world(w: World) -> ParityResult:
    want = canonical_world(w)
    failures: dict[str, str] = {}
    for arm, renderer in ARM_RENDERERS.items():
        try:
            state = renderer.state(w)
            question = renderer.question(w)
            back = ARM_DECODERS[arm](state, question, w.family)
            got = canonical_world(back)
            if got != want:
                failures[arm] = _first_difference(want, got)
        except DecodeError as exc:
            failures[arm] = f"decode error: {exc}"
        except Exception as exc:  # pragma: no cover - surfaced verbatim, never swallowed
            failures[arm] = f"{type(exc).__name__}: {exc}"
    return ParityResult(w.world_id, not failures, failures)


def _first_difference(want: str, got: str) -> str:
    """Point at the first divergence -- a full canonical form is unreadable in a failure."""
    for i, (a, b) in enumerate(zip(want, got, strict=False)):
        if a != b:
            lo = max(0, i - 60)
            return f"diverges at char {i}\n    want ...{want[lo:i + 60]}\n    got  ...{got[lo:i + 60]}"
    return f"length differs: want {len(want)}, got {len(got)}\n    want tail {want[len(got):][:80]!r}"


def check_corpus(worlds) -> tuple[int, list[ParityResult]]:
    """Returns (n_checked, failures)."""
    bad = []
    n = 0
    for w in worlds:
        n += 1
        r = check_world(w)
        if not r.ok:
            bad.append(r)
    return n, bad
