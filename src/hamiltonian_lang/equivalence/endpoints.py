"""Tier 4 -- endpoint-specific answer verification.

H1 and H2 ask whether the representation improved the *answer*. That question is
not the equivalence question, and this tier keeps the two apart: a matching answer
yields ``VERIFIED_CORRECT_ANSWER`` and never ``VERIFIED_EQUIVALENT``, because two
encodings can reach the same number by different -- and differently wrong -- routes.

Three comparison kinds, each with an explicit rule:

* ``numeric`` -- compare as exact rationals when both parse exactly, otherwise
  within a relative tolerance;
* ``exact`` -- compare symbolically, so ``1/2`` and ``0.5`` and ``2^-1`` agree
  while ``1/2`` and ``0.51`` do not;
* ``set`` -- compare as multisets, so the order of a solution set does not matter.

An answer that cannot be parsed is ``INCONCLUSIVE``, never wrong. A unit that is
present on one side and different on the other is ``INCONCLUSIVE`` too: this
module has no unit algebra, and guessing at one would be worse than declining.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .status import (
    Certificate,
    Counterexample,
    EquivalenceResult,
    EquivalenceStatus,
    Tier,
)
from .sympy_bridge import SYMPY_AVAILABLE

if SYMPY_AVAILABLE:  # pragma: no branch - sympy is present on this host
    import sympy

__all__ = ["AnswerSpec", "parse_answer", "verify_answer"]

_UNIT = re.compile(r"^\s*(?P<value>[-+0-9./eE^*() ]+?)\s*(?P<unit>[A-Za-z][A-Za-z0-9^/*· -]*)?\s*$")
_NUMBERISH = re.compile(r"^[-+0-9./eE^*() ]+$")


@dataclass(frozen=True)
class AnswerSpec:
    """What counts as the right answer for one task."""

    expected: str
    kind: str = "numeric"  # numeric | exact | set
    tolerance: float = 1e-9
    unit: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("numeric", "exact", "set"):
            raise ValueError(f"unknown answer kind {self.kind!r}")
        if self.tolerance < 0:
            raise ValueError("tolerance may not be negative")


def parse_answer(text: str) -> tuple[Any | None, str | None]:
    """``(value, unit)``; ``value`` is None when the text is not a number."""
    if not SYMPY_AVAILABLE:  # pragma: no cover
        return None, None
    raw = (text or "").strip()
    if not raw:
        return None, None
    match = _UNIT.match(raw)
    if match is None:
        return None, None
    body = (match.group("value") or "").strip()
    unit = (match.group("unit") or "").strip() or None
    if not body or not _NUMBERISH.match(body):
        return None, None
    try:
        value = sympy.sympify(body.replace("^", "**"), rational=True)
    except (sympy.SympifyError, TypeError, ValueError, SyntaxError):
        return None, None
    if value.free_symbols:
        return None, unit
    return value, unit


def _tier4(status: EquivalenceStatus, detail: str, **kw: Any) -> EquivalenceResult:
    return EquivalenceResult(Tier.TIER4_ENDPOINT_ANSWER, status, detail, **kw)


def _split_set(text: str) -> list[str]:
    stripped = (text or "").strip().strip("{}[]()")
    return [part for part in (p.strip() for p in stripped.split(",")) if part]


def verify_answer(spec: AnswerSpec, actual: str | None) -> EquivalenceResult:
    """Compare a candidate's final answer with the expected one."""
    if not SYMPY_AVAILABLE:  # pragma: no cover
        return _tier4(EquivalenceStatus.UNSUPPORTED, "sympy is not importable")
    if actual is None or not str(actual).strip():
        return _tier4(
            EquivalenceStatus.INCONCLUSIVE,
            "the candidate produced no final answer; that is a missing answer, not a "
            "wrong one, and it is not scored as wrong here",
        )

    if spec.kind == "set":
        return _verify_set(spec, str(actual))

    expected_value, expected_unit = parse_answer(spec.expected)
    actual_value, actual_unit = parse_answer(str(actual))
    if expected_value is None:
        return _tier4(
            EquivalenceStatus.UNSUPPORTED,
            f"the expected answer {spec.expected!r} is not a number this tier can parse",
        )
    if actual_value is None:
        return _tier4(
            EquivalenceStatus.INCONCLUSIVE,
            f"the candidate answer {str(actual)!r} could not be parsed as a number; no "
            f"verdict is issued",
        )

    want_unit = spec.unit or expected_unit
    if want_unit and actual_unit and _normalise_unit(actual_unit) != _normalise_unit(want_unit):
        return _tier4(
            EquivalenceStatus.INCONCLUSIVE,
            f"the answers carry different units ({want_unit} and {actual_unit}) and this "
            f"tier has no unit algebra, so no comparison is made",
        )

    if spec.kind == "exact":
        same = bool(sympy.simplify(expected_value - actual_value) == 0)
    else:
        difference = abs(complex(expected_value - actual_value))
        scale = max(1.0, abs(complex(expected_value)))
        same = difference <= spec.tolerance * scale

    if same:
        return _tier4(
            EquivalenceStatus.VERIFIED_CORRECT_ANSWER,
            f"the final answer matches the expected value under the {spec.kind} rule",
            certificate=Certificate(
                "tier4.final_answer_match",
                f"expected {expected_value}, produced {actual_value}; equal under the "
                f"{spec.kind} comparison rule",
                witness={"expected": str(expected_value), "actual": str(actual_value)},
            ),
        )
    return _tier4(
        EquivalenceStatus.COUNTEREXAMPLE_FOUND,
        "the final answer differs from the expected one",
        counterexample=Counterexample(
            "tier3.numeric_counterexample",
            "the candidate's final answer is not the expected value",
            left_value=str(expected_value),
            right_value=str(actual_value),
        ),
    )


def _verify_set(spec: AnswerSpec, actual: str) -> EquivalenceResult:
    raw_want = [parse_answer(p)[0] for p in _split_set(spec.expected)]
    raw_got = [parse_answer(p)[0] for p in _split_set(actual)]
    if not raw_want or any(v is None for v in raw_want):
        return _tier4(
            EquivalenceStatus.UNSUPPORTED,
            f"the expected set {spec.expected!r} could not be parsed element-wise",
        )
    if not raw_got or any(v is None for v in raw_got):
        return _tier4(
            EquivalenceStatus.INCONCLUSIVE,
            f"the candidate set {actual!r} could not be parsed element-wise; no verdict",
        )
    want: list[Any] = [v for v in raw_want if v is not None]
    got: list[Any] = [v for v in raw_got if v is not None]
    remaining = list(got)
    for element in want:
        match = next(
            (g for g in remaining if abs(complex(element - g)) <= spec.tolerance
             * max(1.0, abs(complex(element)))),
            None,
        )
        if match is None:
            return _tier4(
                EquivalenceStatus.COUNTEREXAMPLE_FOUND,
                f"the expected element {element} is absent from the candidate set",
                counterexample=Counterexample(
                    "tier3.numeric_counterexample",
                    f"expected element {element} is missing",
                    left_value=str(want),
                    right_value=str(got),
                ),
            )
        remaining.remove(match)
    if remaining:
        return _tier4(
            EquivalenceStatus.COUNTEREXAMPLE_FOUND,
            f"the candidate set carries {len(remaining)} element(s) the expected set does not",
            counterexample=Counterexample(
                "tier3.numeric_counterexample",
                f"unexpected element(s) {remaining}",
                left_value=str(want),
                right_value=str(got),
            ),
        )
    return _tier4(
        EquivalenceStatus.VERIFIED_CORRECT_ANSWER,
        "the two solution sets agree as multisets",
        certificate=Certificate(
            "tier4.final_answer_match",
            f"expected {want}, produced {got}; equal as multisets within tolerance",
            witness={"expected": str(want), "actual": str(got)},
        ),
    )


def _normalise_unit(unit: str) -> str:
    return re.sub(r"\s+", "", unit).lower().rstrip("s")
