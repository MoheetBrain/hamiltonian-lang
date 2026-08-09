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

    def report_reasoning_loss(self) -> None:
        """Declare every V2 reasoning construct this backend cannot carry.

        Lives on the base class on purpose. When V2 landed, four backends dropped
        ``derive``/``goal``/``proved`` and reported nothing about them, because each
        backend's statement dispatch simply had no branch for the new node types and
        fell through silently. A per-backend fix would have to be remembered five times
        and again for the next construct; this is remembered once.

        A backend that *can* represent a construct should render it and not call this
        for that node. A backend that cannot must call this, so the loss is machine-
        readable rather than invisible -- the discipline ``BackendResult.faithful``
        exists to enforce.
        """
        from ..ast.nodes import (
            DeriveStmt,
            EvidenceStmt,
            GoalStmt,
            ProvedStmt,
            UndeterminedStmt,
        )

        for st in self.module.statements:
            if isinstance(st, GoalStmt):
                self.drop(
                    f"goal {st.label}",
                    f"{self.target} has no goal state; the proposition is not carried "
                    f"and its OPEN/PROVED status is erased",
                    st.span.line,
                )
            elif isinstance(st, DeriveStmt):
                self.drop(
                    f"derive {st.label}",
                    f"{self.target} has no derivation form; the inference "
                    f"({st.rule} from {', '.join(st.premises) or 'no premise'}), its "
                    f"generated obligations and its verification status are all erased",
                    st.span.line,
                )
            elif isinstance(st, ProvedStmt):
                self.drop(
                    f"proved {st.goal}",
                    f"{self.target} cannot express that a goal was adjudicated; the "
                    f"proof claim and the checker's verdict are erased",
                    st.span.line,
                )
            elif isinstance(st, EvidenceStmt):
                # The loss here is unusually dangerous and the message says so. Stripping
                # the judgement from a `determines_neither` certificate leaves a bare
                # proposition sitting in the output, and a reader downstream will take
                # that as an assertion of the very thing the certificate says is
                # unsettled. That is the exact inversion this construct exists to prevent.
                self.drop(
                    f"evidence {st.label}",
                    f"{self.target} has no checked-certificate form; the judgement "
                    f"({st.judgement}), the checker identity ({st.checker}), the declared "
                    f"dependencies and the context the certificate was issued against are "
                    f"all erased. For a determines_neither certificate what survives is a "
                    f"bare proposition, which READS AS AN ASSERTION OF THE OPPOSITE of "
                    f"what the certificate states",
                    st.span.line,
                )
            elif isinstance(st, UndeterminedStmt):
                self.drop(
                    f"undetermined {st.goal}",
                    f"{self.target} cannot express that a goal was certified "
                    f"underdetermined; the two-model evidence is erased, and with it the "
                    f"distinction between 'the premises settle neither way' and 'nobody "
                    f"proved it'",
                    st.span.line,
                )

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
