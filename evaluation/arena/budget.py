"""Token/character budget per arm -- the instrument that keeps a length effect visible.

Parity proves the arms carry the same information. It does not, and cannot, make them
the same length: a tree serialisation is longer than infix notation, and HML's
relativised quantifiers are longer than English's `for every x in D`. Forcing the arms to
equal length would mean distorting at least one notation into something nobody writes.

So the difference is measured instead of removed. Any result where the arms differ in
accuracy **and** in length has two candidate explanations, and this module is what makes
that visible rather than letting "HML wins" quietly mean "the shortest prompt wins".

`tiktoken`'s `cl100k_base` is used as a stable, model-independent yardstick. It is not
the tokenizer of whatever model is eventually screened, and it is not meant to be -- it
is a fixed ruler for comparing arms to each other, and swapping it would change every
number without changing any conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

__all__ = ["ENCODING", "Budget", "measure", "budget_table"]

ENCODING = "cl100k_base"

_enc = None


def _encoder():
    global _enc
    if _enc is None:
        import tiktoken

        _enc = tiktoken.get_encoding(ENCODING)
    return _enc


@dataclass(frozen=True)
class Budget:
    arm: str
    n: int
    tokens_mean: float
    tokens_max: int
    chars_mean: float
    lines_mean: float

    def as_dict(self) -> dict:
        return {
            "arm": self.arm, "n": self.n,
            "tokens_mean": round(self.tokens_mean, 1), "tokens_max": self.tokens_max,
            "chars_mean": round(self.chars_mean, 1), "lines_mean": round(self.lines_mean, 1),
        }


def measure(arm: str, prompts: list[str]) -> Budget:
    enc = _encoder()
    toks = [len(enc.encode(p)) for p in prompts]
    return Budget(
        arm=arm,
        n=len(prompts),
        tokens_mean=mean(toks) if toks else 0.0,
        tokens_max=max(toks) if toks else 0,
        chars_mean=mean(len(p) for p in prompts) if prompts else 0.0,
        lines_mean=mean(p.count("\n") + 1 for p in prompts) if prompts else 0.0,
    )


def budget_table(prompts_by_arm: dict[str, list[str]]) -> dict:
    """Per-arm budgets plus the spread, so a reader cannot miss a lopsided corpus."""
    budgets = {arm: measure(arm, ps) for arm, ps in prompts_by_arm.items()}
    means = {a: b.tokens_mean for a, b in budgets.items()}
    lo = min(means.values()) if means else 0
    hi = max(means.values()) if means else 0
    return {
        "encoding": ENCODING,
        "arms": {a: b.as_dict() for a, b in budgets.items()},
        "tokens_mean_ratio_max_over_min": round(hi / lo, 2) if lo else None,
        "longest_arm": max(means, key=means.get) if means else None,
        "shortest_arm": min(means, key=means.get) if means else None,
    }
