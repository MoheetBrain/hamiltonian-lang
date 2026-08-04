"""Backend contract.

**Every backend must report what it could not translate.** A backend that silently
drops a construct is worse than one that refuses, because it produces output that looks
authoritative and is not. `BackendResult.faithful` is False whenever anything was
dropped or approximated, and the CLI surfaces that.

Backends are *lossy by default*. The burden is on the backend to declare the loss.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ast.nodes import Module
from ..semantics import SymbolTable

__all__ = ["BackendResult", "Backend", "Unsupported"]


@dataclass
class Unsupported:
    construct: str
    reason: str
    line: int = 0
    severity: str = "dropped"  # dropped | approximated | weakened

    def render(self) -> str:
        loc = f" (line {self.line})" if self.line else ""
        return f"[{self.severity}] {self.construct}{loc}: {self.reason}"


@dataclass
class BackendResult:
    target: str
    text: str
    unsupported: list[Unsupported] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def faithful(self) -> bool:
        """True only when nothing was dropped, approximated, or weakened."""
        return not self.unsupported

    def report(self) -> str:
        if self.faithful:
            return f"# {self.target}: no loss reported"
        lines = [f"# {self.target}: {len(self.unsupported)} construct(s) not fully preserved"]
        lines.extend("#   " + u.render() for u in self.unsupported)
        return "\n".join(lines)

    def with_report(self, comment: str = "#") -> str:
        header = "\n".join(
            f"{comment} {line.lstrip('# ')}" for line in self.report().splitlines()
        )
        return f"{header}\n\n{self.text}"

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "faithful": self.faithful,
            "text": self.text,
            "unsupported": [
                {"construct": u.construct, "reason": u.reason, "line": u.line,
                 "severity": u.severity}
                for u in self.unsupported
            ],
            "notes": list(self.notes),
        }


class Backend:
    """Base class. Subclasses implement :meth:`emit`."""

    target: str = "abstract"
    #: human-readable statement of what this backend fundamentally cannot express
    limitations: tuple[str, ...] = ()

    def __init__(self, module: Module, symbols: SymbolTable | None = None) -> None:
        self.module = module
        self.symbols = symbols
        self.unsupported: list[Unsupported] = []
        self.notes: list[str] = []

    def drop(self, construct: str, reason: str, line: int = 0) -> None:
        self.unsupported.append(Unsupported(construct, reason, line, "dropped"))

    def approximate(self, construct: str, reason: str, line: int = 0) -> None:
        self.unsupported.append(Unsupported(construct, reason, line, "approximated"))

    def weaken(self, construct: str, reason: str, line: int = 0) -> None:
        self.unsupported.append(Unsupported(construct, reason, line, "weakened"))

    def emit(self) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def run(self) -> BackendResult:
        text = self.emit()
        return BackendResult(
            target=self.target,
            text=text,
            unsupported=list(self.unsupported),
            notes=[*self.limitations, *self.notes],
        )
