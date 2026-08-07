"""Final-answer extraction and scoring.

Two rules, both learned from this project's earlier scoring defects:

1. **Score the declared FINAL line only.** Searching the whole response for a matching
   number credits a model that reasoned to the wrong answer but mentioned the right one in
   passing. The previous benchmarks' scoring problems all ran in that generous direction.
2. **Unparseable is wrong.** Never reinterpret generously.
"""

from __future__ import annotations

import re
from fractions import Fraction

__all__ = ["extract_final", "score", "SCORER_VERSION"]

SCORER_VERSION = "difficulty-lab-scorer-1.0.0"

_FINAL = re.compile(r"^\s*FINAL\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_WORD = re.compile(r"\b(TRUE|FALSE|UNDETERMINED)\b", re.IGNORECASE)


def extract_final(text: str) -> str:
    """The LAST declared FINAL line. Empty when the model never declared one."""
    hits = _FINAL.findall(text or "")
    return hits[-1].strip() if hits else ""


def _as_fraction(s: str) -> Fraction | None:
    s = s.strip().rstrip(".").replace(" ", "").replace("$", "")
    m = re.fullmatch(r"(-?\d+)\s*/\s*(-?\d+)", s)
    if m:
        try:
            return Fraction(int(m.group(1)), int(m.group(2)))
        except ZeroDivisionError:
            return None
    m = re.fullmatch(r"-?\d+(?:\.\d+)?", s)
    if m:
        return Fraction(s)
    return None


def score(expected: str, final: str, answer_format: str) -> bool:
    if not final:
        return False
    if answer_format in ("TRUE or FALSE", "TRUE, FALSE or UNDETERMINED"):
        words = _WORD.findall(final)
        if len(words) != 1:
            # Two verdicts in one line is not an answer.
            return False
        return words[0].upper() == expected.upper()
    want, got = _as_fraction(expected), _as_fraction(final)
    return want is not None and got is not None and want == got


#: (expected, final, format, verdict). Exercised before any model call.
SELFTEST = [
    ("7", "7", "an exact integer or fraction", True),
    ("7", "7.0", "an exact integer or fraction", True),
    ("7", "-7", "an exact integer or fraction", False),
    ("7/3", "7/3", "an exact integer or fraction", True),
    ("7/3", "14/6", "an exact integer or fraction", True),
    ("7/3", "2.333", "an exact integer or fraction", False),
    ("7", "", "an exact integer or fraction", False),
    ("7", "seven", "an exact integer or fraction", False),
    ("TRUE", "TRUE", "TRUE or FALSE", True),
    ("TRUE", "true", "TRUE or FALSE", True),
    ("TRUE", "FALSE", "TRUE or FALSE", False),
    ("UNDETERMINED", "UNDETERMINED", "TRUE, FALSE or UNDETERMINED", True),
    ("UNDETERMINED", "TRUE", "TRUE, FALSE or UNDETERMINED", False),
    ("TRUE", "TRUE or FALSE", "TRUE or FALSE", False),
    ("TRUE", "", "TRUE or FALSE", False),
]


def selftest() -> list[tuple]:
    """Returns the failing cases; empty means the scorer is behaving."""
    return [
        (e, f, fmt, want, score(e, f, fmt))
        for e, f, fmt, want in SELFTEST
        if score(e, f, fmt) is not want
    ]


def extraction_selftest() -> list[tuple]:
    cases = [
        ("blah\nFINAL: 42", "42"),
        ("FINAL: 3\nmore\nFINAL: 5", "5"),          # the LAST one wins
        ("I think 42 is right but\nFINAL: 7", "7"),  # reasoning numbers are ignored
        ("no marker here", ""),
        ("final: TRUE", "TRUE"),
    ]
    return [(t, want, extract_final(t)) for t, want in cases if extract_final(t) != want]
