"""Diagnostics for Hamiltonian Lang.

Diagnostics are *mathematical and actionable*: they name the role a symbol was being
used in, the type that role demands, the type that was supplied, and a concrete
correction. A diagnostic that only says "type error" is a bug in this module.

Code ranges:
  HML-L1xx  lexical
  HML-P2xx  parse
  HML-N3xx  name resolution / scope
  HML-T4xx  type
  HML-D5xx  dimensional
  HML-S6xx  semantic / structural
  HML-B7xx  backend
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

__all__ = ["Severity", "Diagnostic", "DiagnosticBag", "HamiltonianError"]


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


@dataclass
class Diagnostic:
    code: str
    message: str
    line: int = 0
    col: int = 0
    end_line: int = 0
    end_col: int = 0
    severity: Severity = Severity.ERROR
    expected: str | None = None
    found: str | None = None
    correction: str | None = None
    notes: list[str] = field(default_factory=list)
    file: str = "<input>"

    def render(self, source: str | None = None) -> str:
        head = f"{self.severity.value} {self.code}: {self.message}"
        loc = f"  --> {self.file}:{self.line}:{self.col + 1}"
        parts = [head, loc]
        if source is not None and self.line > 0:
            lines = source.splitlines()
            if 0 < self.line <= len(lines):
                text = lines[self.line - 1]
                gutter = f"{self.line:>4} | "
                parts.append(f"{gutter}{text}")
                width = max(1, (self.end_col - self.col) if self.end_line == self.line else 1)
                parts.append(" " * len(gutter) + " " * self.col + "^" * width)
        if self.found is not None:
            parts.append(f"  found:    {self.found}")
        if self.expected is not None:
            parts.append(f"  expected: {self.expected}")
        for n in self.notes:
            parts.append(f"  note: {n}")
        if self.correction:
            parts.append(f"  help: {self.correction}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "line": self.line,
            "col": self.col,
            "expected": self.expected,
            "found": self.found,
            "correction": self.correction,
            "notes": list(self.notes),
        }


class DiagnosticBag:
    def __init__(self, source: str | None = None, file: str = "<input>") -> None:
        self.items: list[Diagnostic] = []
        self.source = source
        self.file = file

    def add(self, d: Diagnostic) -> None:
        if d.file == "<input>":
            d.file = self.file
        self.items.append(d)

    def error(self, code: str, message: str, span=None, **kw) -> None:
        self.add(_make(code, message, span, Severity.ERROR, **kw))

    def warn(self, code: str, message: str, span=None, **kw) -> None:
        self.add(_make(code, message, span, Severity.WARNING, **kw))

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self.items if d.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.items if d.severity is Severity.WARNING]

    def ok(self) -> bool:
        return not self.errors

    def codes(self) -> list[str]:
        return [d.code for d in self.items]

    def render(self) -> str:
        return "\n\n".join(d.render(self.source) for d in self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def extend(self, other: DiagnosticBag | Sequence[Diagnostic]) -> None:
        for d in other:
            self.add(d)


def _make(code, message, span, severity, **kw) -> Diagnostic:
    d = Diagnostic(code=code, message=message, severity=severity, **kw)
    if span is not None:
        d.line, d.col = span.line, span.col
        d.end_line, d.end_col = span.end_line, span.end_col
        d.file = getattr(span, "file", "<input>")
    return d


class HamiltonianError(Exception):
    """Raised only at API boundaries where a caller asked for exceptions."""

    def __init__(self, bag: DiagnosticBag) -> None:
        self.bag = bag
        super().__init__(bag.render())
