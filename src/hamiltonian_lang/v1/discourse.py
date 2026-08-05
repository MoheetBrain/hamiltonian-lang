"""V1 layer 5 — discourse state.

HML-V1-CONCEPT-001 Phase 7. Executable state, not decoration.

A goal opens an obligation. ``established`` closes it and **requires a Proof-justified
claim**, which is decided by :data:`~hamiltonian_lang.v1.epistemic.DISCHARGES_GOALS`
imported from the contract module — Evidence and Assumption close nothing. Case splits are
checked for exhaustiveness. Everything still open at end of module is reported.

That last sentence is the admission test of `docs/design/V1_KERNEL.md` §0. A phrase enters
this layer only if it changes an obligation, a dependency or the open-goal set. "We now
show" does; "for completeness" does not, and :func:`classify_phrase` says so explicitly
rather than leaving the exclusion to editorial discipline — see :data:`RHETORICAL_PHRASES`
and :meth:`DiscourseState.apply_phrase`, which cannot change state for such a phrase.

Exhaustiveness is decided only where it is decidable without a solver: a split on
comparisons of one variable against numeric thresholds. Anything else is reported as
**not shown exhaustive** rather than assumed to be. An unchecked "otherwise the argument
is similar" is precisely the gap this layer exists to expose.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from .epistemic import DISCHARGES_GOALS, EpistemicClaim
from .transformation import ChainReport, Obligation, Weakening

__all__ = [
    "DiscourseConstruct",
    "OpenItem",
    "PendingObligation",
    "Case",
    "CaseSplit",
    "Exhaustiveness",
    "check_exhaustive",
    "DiscourseError",
    "DependencyNotice",
    "PhraseClass",
    "PhraseMapping",
    "KERNEL_PHRASES",
    "RHETORICAL_PHRASES",
    "classify_phrase",
    "DiscourseReport",
    "DiscourseState",
]


class DiscourseConstruct(StrEnum):
    """The closed set of discourse constructs."""

    GOAL = "goal"
    SUBGOAL = "subgoal"
    PENDING_OBLIGATION = "pending_obligation"
    CONSIDER_CASE = "consider_case"
    OTHERWISE = "otherwise"
    END_CASE = "end_case"
    RETURN_TO_GOAL = "return_to_goal"
    ESTABLISHED = "established"
    REMAINS_TO_SHOW = "remains_to_show"
    CONVERSE_GOAL = "converse_goal"
    DEPENDENCY_NOTICE = "dependency_notice"


#: The constructs that open something that must later be closed.
_OPENING = (
    DiscourseConstruct.GOAL,
    DiscourseConstruct.SUBGOAL,
    DiscourseConstruct.PENDING_OBLIGATION,
    DiscourseConstruct.CONVERSE_GOAL,
)


# ---------------------------------------------------------------------------
# Open items
# ---------------------------------------------------------------------------


@dataclass
class OpenItem:
    """Something that has been opened and may or may not have been closed."""

    name: str
    statement: str
    construct: DiscourseConstruct
    parent: str | None = None
    cases: tuple[str, ...] = ()
    origin: str = ""
    closed_by: EpistemicClaim | None = None

    @property
    def open(self) -> bool:
        return self.closed_by is None


@dataclass(frozen=True)
class PendingObligation:
    """A derived view of one open item. Never written by hand; it *is* the open set."""

    name: str
    statement: str
    construct: DiscourseConstruct
    origin: str = ""
    cases: tuple[str, ...] = ()

    def render(self) -> str:
        where = f" [in case {' & '.join(self.cases)}]" if self.cases else ""
        via = f" (from {self.origin})" if self.origin else ""
        return f"{self.construct} {self.name}{where}: {self.statement}{via}"

    def __str__(self) -> str:
        return self.render()


# ---------------------------------------------------------------------------
# Cases and exhaustiveness
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Case:
    name: str
    condition: str
    complement: bool = False


@dataclass
class CaseSplit:
    name: str
    branches: list[Case] = field(default_factory=list)
    closed: bool = False
    exhaustive_by: EpistemicClaim | None = None

    @property
    def has_otherwise(self) -> bool:
        return any(b.complement for b in self.branches)


@dataclass(frozen=True)
class Exhaustiveness:
    """Whether a case split covers everything — and whether that was even decidable.

    ``decided`` False is an honest answer and is reported as *not shown exhaustive*. It is
    never silently treated as exhaustive.
    """

    decided: bool
    exhaustive: bool
    reason: str
    uncovered: str = ""

    @property
    def shown(self) -> bool:
        return self.decided and self.exhaustive


_COMPARISON = re.compile(
    r"^\s*([A-Za-z_][A-Za-z_0-9]*)\s*(<=|>=|!=|==|<|>|=)\s*(-?\d+(?:\.\d+)?)\s*$"
)


def _fmt(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


def _holds(op: str, x: float, threshold: float) -> bool:
    if op == "<":
        return x < threshold
    if op == "<=":
        return x <= threshold
    if op == ">":
        return x > threshold
    if op == ">=":
        return x >= threshold
    if op in ("=", "=="):
        return x == threshold
    return x != threshold  # "!="


def check_exhaustive(conditions: Sequence[str]) -> Exhaustiveness:
    """Whether a union of conditions covers the real line.

    Decided **only** for a split on comparisons of a single variable against numeric
    thresholds — ``x > 0`` / ``x < 0`` / ``x = 0`` and the like. That fragment is exactly
    the example `docs/design/V1_KERNEL.md` §4 uses, and it is decidable by finite case
    analysis with no solver. Anything richer returns ``decided=False``.
    """
    if not conditions:
        return Exhaustiveness(True, False, "a case split with no branches covers nothing")

    parsed: list[tuple[str, str, float]] = []
    for condition in conditions:
        match = _COMPARISON.match(condition)
        if match is None:
            return Exhaustiveness(
                False,
                False,
                f"condition {condition!r} is outside the decidable fragment "
                f"(one variable compared to a number); exhaustiveness is not shown",
            )
        parsed.append((match.group(1), match.group(2), float(match.group(3))))

    variables = {p[0] for p in parsed}
    if len(variables) != 1:
        return Exhaustiveness(
            False,
            False,
            f"the branches split on more than one variable ({', '.join(sorted(variables))}); "
            f"exhaustiveness is not shown",
        )

    variable = parsed[0][0]
    thresholds = sorted({p[2] for p in parsed})
    cells: list[tuple[float, str]] = [
        (thresholds[0] - 1.0, f"{variable} < {_fmt(thresholds[0])}")
    ]
    for i, t in enumerate(thresholds):
        cells.append((t, f"{variable} = {_fmt(t)}"))
        if i + 1 < len(thresholds):
            nxt = thresholds[i + 1]
            cells.append(
                ((t + nxt) / 2.0, f"{_fmt(t)} < {variable} < {_fmt(nxt)}")
            )
    cells.append((thresholds[-1] + 1.0, f"{variable} > {_fmt(thresholds[-1])}"))

    for representative, description in cells:
        if not any(_holds(op, representative, value) for _, op, value in parsed):
            return Exhaustiveness(
                True,
                False,
                f"the branches leave {description} uncovered",
                uncovered=description,
            )
    return Exhaustiveness(
        True, True, f"the branches cover every value of {variable}"
    )


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscourseError:
    code: str
    construct: DiscourseConstruct
    subject: str
    message: str

    def render(self) -> str:
        return f"{self.code} [{self.construct} {self.subject}] {self.message}"

    def __str__(self) -> str:
        return self.render()


@dataclass(frozen=True)
class DependencyNotice:
    """Something a result rests on and that travels with it."""

    subject: str
    on: str
    reason: str = ""

    def render(self) -> str:
        tail = f" ({self.reason})" if self.reason else ""
        return f"{self.subject} depends on {self.on}{tail}"

    def __str__(self) -> str:
        return self.render()


# ---------------------------------------------------------------------------
# Controlled-English phrase mapping
# ---------------------------------------------------------------------------


class PhraseClass(StrEnum):
    KERNEL = "kernel"
    RENDERER_ONLY = "renderer_only"
    UNRECOGNISED = "unrecognised"


#: Phrases that change checker state, and the construct each maps to. The left-hand side
#: is a **renderer output and a reading aid, never a source keyword**; the kernel is the
#: right-hand side.
KERNEL_PHRASES: dict[str, DiscourseConstruct] = {
    "we now show": DiscourseConstruct.GOAL,
    "we will show": DiscourseConstruct.GOAL,
    "we now prove": DiscourseConstruct.GOAL,
    "our goal is to show": DiscourseConstruct.GOAL,
    "we claim that": DiscourseConstruct.GOAL,
    "it suffices to show": DiscourseConstruct.SUBGOAL,
    "we first show": DiscourseConstruct.SUBGOAL,
    "it remains to establish": DiscourseConstruct.PENDING_OBLIGATION,
    "it remains to show": DiscourseConstruct.PENDING_OBLIGATION,
    "it remains to prove": DiscourseConstruct.PENDING_OBLIGATION,
    "consider first the special case": DiscourseConstruct.CONSIDER_CASE,
    "consider the special case": DiscourseConstruct.CONSIDER_CASE,
    "consider the case": DiscourseConstruct.CONSIDER_CASE,
    "in the special case": DiscourseConstruct.CONSIDER_CASE,
    "in the remaining case": DiscourseConstruct.OTHERWISE,
    "otherwise": DiscourseConstruct.OTHERWISE,
    "returning to the main goal": DiscourseConstruct.RETURN_TO_GOAL,
    "we return to": DiscourseConstruct.RETURN_TO_GOAL,
    "we have established": DiscourseConstruct.ESTABLISHED,
    "this establishes": DiscourseConstruct.ESTABLISHED,
    "this completes the proof": DiscourseConstruct.ESTABLISHED,
    "which was to be shown": DiscourseConstruct.ESTABLISHED,
    "the converse need not hold": DiscourseConstruct.CONVERSE_GOAL,
    "the converse fails": DiscourseConstruct.CONVERSE_GOAL,
    "the converse is false": DiscourseConstruct.CONVERSE_GOAL,
    "under the assumption that": DiscourseConstruct.DEPENDENCY_NOTICE,
    "assuming that": DiscourseConstruct.DEPENDENCY_NOTICE,
    "this depends on": DiscourseConstruct.DEPENDENCY_NOTICE,
}

#: Phrases that are **excluded from the kernel** because they alter no obligation, no
#: dependency and no open-goal set. The exclusion is implemented, not merely advised:
#: :meth:`DiscourseState.apply_phrase` cannot change state for any of these.
#:
#: "clearly", "obviously" and "trivially" are listed here for a sharper reason than the
#: others — they assert without a warrant. Admitting them would let a step be closed by
#: emphasis. They are dropped, which leaves whatever they were covering still open.
RHETORICAL_PHRASES: dict[str, str] = {
    "for completeness": "changes no obligation, dependency or open-goal set",
    "recall that": "restates something already in scope",
    "note that": "draws attention; alters nothing",
    "it is worth observing": "draws attention; alters nothing",
    "it is worth noting": "draws attention; alters nothing",
    "as is well known": "an appeal to familiarity is not a citation",
    "clearly": "asserts without a warrant; the step it covers stays open",
    "obviously": "asserts without a warrant; the step it covers stays open",
    "trivially": "asserts without a warrant; the step it covers stays open",
    "of course": "asserts without a warrant; the step it covers stays open",
    "needless to say": "draws attention; alters nothing",
    "in passing": "draws attention; alters nothing",
}


@dataclass(frozen=True)
class PhraseMapping:
    """How a controlled-English phrase is classified."""

    text: str
    classification: PhraseClass
    construct: DiscourseConstruct | None = None
    matched: str = ""
    reason: str = ""
    rhetorical: tuple[str, ...] = ()

    @property
    def enters_kernel(self) -> bool:
        return self.classification is PhraseClass.KERNEL

    def render(self) -> str:
        head = f"{self.classification}"
        if self.construct is not None:
            head += f" -> {self.construct}"
        dropped = f"; dropped: {', '.join(self.rhetorical)}" if self.rhetorical else ""
        return f"{head} ({self.reason}){dropped}"


_PUNCTUATION = re.compile(r"[.,;:!?]")


def _normalise(text: str) -> str:
    return " ".join(_PUNCTUATION.sub(" ", text).lower().split())


def classify_phrase(text: str) -> PhraseMapping:
    """Map a controlled-English phrase onto a kernel construct, or refuse to.

    Longest match wins, so "it remains to show" is not read as "we now show". Rhetorical
    material is stripped and recorded; a phrase made only of rhetorical material is
    ``RENDERER_ONLY`` and carries no construct at all.
    """
    normalised = _normalise(text)
    rhetorical = tuple(sorted(p for p in RHETORICAL_PHRASES if p in normalised))

    best: str | None = None
    for phrase in KERNEL_PHRASES:
        if phrase in normalised and (best is None or len(phrase) > len(best)):
            best = phrase
    if best is not None:
        return PhraseMapping(
            text=text,
            classification=PhraseClass.KERNEL,
            construct=KERNEL_PHRASES[best],
            matched=best,
            reason=f"{best!r} changes checker state",
            rhetorical=rhetorical,
        )

    if rhetorical:
        return PhraseMapping(
            text=text,
            classification=PhraseClass.RENDERER_ONLY,
            matched=rhetorical[0],
            reason=RHETORICAL_PHRASES[rhetorical[0]],
            rhetorical=rhetorical,
        )

    return PhraseMapping(
        text=text,
        classification=PhraseClass.UNRECOGNISED,
        reason="no discourse construct recognised; nothing entered the kernel",
    )


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscourseReport:
    module: str
    open_obligations: tuple[PendingObligation, ...] = ()
    errors: tuple[DiscourseError, ...] = ()
    dependencies: tuple[DependencyNotice, ...] = ()
    established: tuple[str, ...] = ()
    splits: tuple[tuple[str, Exhaustiveness], ...] = ()
    weakenings: tuple[Weakening, ...] = ()

    @property
    def clean(self) -> bool:
        """True only when nothing is open and nothing was reported."""
        return not self.errors and not self.open_obligations

    def codes(self) -> tuple[str, ...]:
        return tuple(e.code for e in self.errors)

    def render(self) -> str:
        lines = [f"# module {self.module}"]
        if self.open_obligations:
            lines.append(f"{len(self.open_obligations)} obligation(s) remain to show:")
            lines.extend("  " + o.render() for o in self.open_obligations)
        else:
            lines.append("nothing remains to show")
        if self.errors:
            lines.append(f"{len(self.errors)} discourse error(s):")
            lines.extend("  " + e.render() for e in self.errors)
        if self.splits:
            lines.append("case splits:")
            for name, ex in self.splits:
                verdict = "exhaustive" if ex.shown else "NOT shown exhaustive"
                lines.append(f"  {name}: {verdict} — {ex.reason}")
        if self.dependencies:
            lines.append("dependencies:")
            lines.extend("  " + d.render() for d in self.dependencies)
        if self.weakenings:
            lines.append("weakenings carried in from transformation steps:")
            lines.extend("  " + w.render() for w in self.weakenings)
        if self.established:
            lines.append("established: " + ", ".join(self.established))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# The state machine
# ---------------------------------------------------------------------------


class DiscourseState:
    """Executable discourse state for one module.

    Every method records what it finds and returns it rather than raising, because the
    product is a report of everything wrong, not the first thing wrong. The one thing
    that is *not* negotiable is :meth:`established`: a goal is closed only by a claim
    that :data:`~hamiltonian_lang.v1.epistemic.DISCHARGES_GOALS` admits.
    """

    def __init__(self, module: str = "module") -> None:
        self.module = module
        self._items: dict[str, OpenItem] = {}
        self._order: list[str] = []
        self._open_splits: list[CaseSplit] = []
        self._splits: list[CaseSplit] = []
        self._errors: list[DiscourseError] = []
        self._dependencies: list[DependencyNotice] = []
        self._weakenings: list[Weakening] = []
        self._current_goal: str | None = None

    # -- internals -----------------------------------------------------------

    def _case_context(self) -> tuple[str, ...]:
        names: list[str] = []
        for split in self._open_splits:
            if split.branches:
                names.append(split.branches[-1].name)
        return tuple(names)

    def _record(self, error: DiscourseError) -> DiscourseError:
        self._errors.append(error)
        return error

    def _open(
        self,
        name: str,
        statement: str,
        construct: DiscourseConstruct,
        parent: str | None = None,
        origin: str = "",
    ) -> DiscourseError | None:
        if name in self._items:
            return self._record(
                DiscourseError(
                    "HML-G801", construct, name, f"{name!r} is already declared"
                )
            )
        self._items[name] = OpenItem(
            name=name,
            statement=statement,
            construct=construct,
            parent=parent,
            cases=self._case_context(),
            origin=origin,
        )
        self._order.append(name)
        return None

    # -- goals ---------------------------------------------------------------

    def goal(self, name: str, proposition: str) -> DiscourseError | None:
        """"We now show P." Opens an obligation named ``name``."""
        error = self._open(name, proposition, DiscourseConstruct.GOAL)
        if error is None:
            self._current_goal = name
        return error

    def subgoal(
        self, name: str, proposition: str, of: str | None = None
    ) -> DiscourseError | None:
        """"It suffices to show Q." Opens an obligation beneath a goal."""
        parent = of if of is not None else self._current_goal
        if parent is not None and parent not in self._items:
            return self._record(
                DiscourseError(
                    "HML-G802",
                    DiscourseConstruct.SUBGOAL,
                    name,
                    f"parent goal {parent!r} is not in scope",
                )
            )
        error = self._open(name, proposition, DiscourseConstruct.SUBGOAL, parent=parent)
        if error is None:
            self._current_goal = name
        return error

    def pending_obligation(
        self, name: str, statement: str, origin: str = ""
    ) -> DiscourseError | None:
        """"It remains to establish R." Opens an obligation with no proof structure yet.

        The open *set* is derived and never written by hand; this opens one member of it,
        which is what the phrase actually does to the state.
        """
        return self._open(
            name, statement, DiscourseConstruct.PENDING_OBLIGATION, origin=origin
        )

    def converse_goal(
        self, name: str, of: str, statement: str = ""
    ) -> DiscourseError | None:
        """"The converse need not hold."

        Stating a converse does not resolve it. This opens an obligation that must be
        either established or **refuted** — ``DISCHARGES_GOALS`` admits ``Refutation``, so
        a counterexample closes it and a shrug does not.
        """
        text = statement or f"the converse of {of}"
        return self._open(
            name,
            text,
            DiscourseConstruct.CONVERSE_GOAL,
            origin=f"converse of {of}",
        )

    def return_to_goal(self, name: str) -> DiscourseError | None:
        """"Returning to the main goal." Restores ``name`` as the current goal."""
        if name not in self._items:
            return self._record(
                DiscourseError(
                    "HML-G802",
                    DiscourseConstruct.RETURN_TO_GOAL,
                    name,
                    f"no goal named {name!r} is in scope",
                )
            )
        if self._open_splits:
            return self._record(
                DiscourseError(
                    "HML-G807",
                    DiscourseConstruct.RETURN_TO_GOAL,
                    name,
                    f"case split {self._open_splits[-1].name!r} is still open; "
                    f"returning to a goal from inside a case would make the goal's "
                    f"state conditional on that case",
                )
            )
        self._current_goal = name
        return None

    def established(self, name: str, by: EpistemicClaim) -> DiscourseError | None:
        """Close an obligation. **Requires a Proof-justified claim.**

        The decision is :data:`~hamiltonian_lang.v1.epistemic.DISCHARGES_GOALS`, imported
        from the contract: ``Proof`` and ``Refutation`` close an obligation; ``Evidence``,
        ``Assumption``, ``Credence`` and ``None`` do not, and the obligation stays open.
        """
        item = self._items.get(name)
        if item is None:
            return self._record(
                DiscourseError(
                    "HML-G802",
                    DiscourseConstruct.ESTABLISHED,
                    name,
                    f"no obligation named {name!r} is in scope",
                )
            )
        if not item.open:
            return self._record(
                DiscourseError(
                    "HML-G811",
                    DiscourseConstruct.ESTABLISHED,
                    name,
                    f"{name!r} was already established",
                )
            )
        justification = by.justification
        if not DISCHARGES_GOALS[justification]:
            return self._record(
                DiscourseError(
                    "HML-G803",
                    DiscourseConstruct.ESTABLISHED,
                    name,
                    f"a goal is discharged only by a Proof (or a Refutation); the claim "
                    f"offered is {by.status}, which is {justification}-justified. "
                    f"{name!r} remains open",
                )
            )
        here = self._case_context()
        if item.cases != here and not set(item.cases) >= set(here):
            self._record(
                DiscourseError(
                    "HML-G806",
                    DiscourseConstruct.ESTABLISHED,
                    name,
                    f"{name!r} was opened outside case(s) {' & '.join(here)} but is "
                    f"being established inside them; the discharge is conditional on "
                    f"those cases and does not close the unconditional obligation",
                )
            )
            return self._errors[-1]
        item.closed_by = by
        return None

    # -- cases ---------------------------------------------------------------

    def consider_case(
        self, name: str, condition: str, split: str | None = None
    ) -> DiscourseError | None:
        """"Consider first the special case C." Opens (or extends) a case split."""
        if not self._open_splits or (
            split is not None and self._open_splits[-1].name != split
        ):
            self._open_splits.append(CaseSplit(name=split or f"split_{name}"))
        self._open_splits[-1].branches.append(Case(name=name, condition=condition))
        return None

    def otherwise(self, name: str = "otherwise") -> DiscourseError | None:
        """The complement branch. Its presence makes the split exhaustive by construction."""
        if not self._open_splits:
            return self._record(
                DiscourseError(
                    "HML-G809",
                    DiscourseConstruct.OTHERWISE,
                    name,
                    "no case split is open",
                )
            )
        split = self._open_splits[-1]
        if split.has_otherwise:
            return self._record(
                DiscourseError(
                    "HML-G809",
                    DiscourseConstruct.OTHERWISE,
                    split.name,
                    "the split already has a complement branch",
                )
            )
        split.branches.append(
            Case(name=name, condition="complement of the stated cases", complement=True)
        )
        return None

    def end_case(self, exhaustive_by: EpistemicClaim | None = None) -> DiscourseError | None:
        """Close the current split and check exhaustiveness.

        A split is exhaustive if it has an ``otherwise``, if ``exhaustive_by`` is a claim
        that discharges goals, or if the decidable fragment of :func:`check_exhaustive`
        says so. Otherwise it is **reported**, not assumed.
        """
        if not self._open_splits:
            return self._record(
                DiscourseError(
                    "HML-G809",
                    DiscourseConstruct.END_CASE,
                    "-",
                    "no case split is open",
                )
            )
        split = self._open_splits.pop()
        split.closed = True
        split.exhaustive_by = exhaustive_by
        self._splits.append(split)
        result = self._exhaustiveness(split)
        if not result.shown:
            return self._record(
                DiscourseError(
                    "HML-G804",
                    DiscourseConstruct.END_CASE,
                    split.name,
                    f"the case split is not shown exhaustive: {result.reason}",
                )
            )
        return None

    def _exhaustiveness(self, split: CaseSplit) -> Exhaustiveness:
        if split.has_otherwise:
            return Exhaustiveness(
                True, True, "an explicit complement branch covers the remainder"
            )
        claim = split.exhaustive_by
        if claim is not None and DISCHARGES_GOALS[claim.justification]:
            return Exhaustiveness(
                True, True, f"exhaustiveness is proved by {claim.status}"
            )
        if claim is not None:
            return Exhaustiveness(
                True,
                False,
                f"exhaustiveness was offered on {claim.justification} grounds "
                f"({claim.status}); only a Proof establishes it",
            )
        return check_exhaustive([b.condition for b in split.branches])

    # -- dependencies --------------------------------------------------------

    def dependency_notice(
        self, subject: str, on: str, reason: str = ""
    ) -> DiscourseError | None:
        """"Under the assumption that A." Records what a result rests on."""
        notice = DependencyNotice(subject=subject, on=on, reason=reason)
        if notice not in self._dependencies:
            self._dependencies.append(notice)
        return None

    # -- integration with layer 2 -------------------------------------------

    def absorb(self, report: ChainReport, prefix: str = "") -> tuple[str, ...]:
        """Take a derivation's undischarged obligations into the open set.

        The side conditions a transformation chain generated do not stop existing because
        the chain ended. They become pending obligations here and are reported at end of
        module like any other. Weakenings are carried through separately: they are not
        obligations — nothing discharges them — but a reader must still see them.
        """
        opened = list(self.absorb_obligations(report.obligations, prefix=prefix))
        self._weakenings.extend(report.weakenings)
        for dependency in report.dependencies:
            self.dependency_notice(
                self._current_goal or self.module,
                dependency,
                "assumption carried forward from a transformation step",
            )
        return tuple(opened)

    def absorb_obligations(
        self, obligations: Iterable[Obligation], prefix: str = ""
    ) -> tuple[str, ...]:
        """:meth:`absorb` for a bare sequence of obligations."""
        opened: list[str] = []
        for index, obligation in enumerate(obligations):
            name = f"{prefix}{obligation.edge}#{index}"
            error = self.pending_obligation(
                name, obligation.condition, origin=f"step {obligation.edge}"
            )
            if error is None:
                opened.append(name)
        return tuple(opened)

    # -- controlled English --------------------------------------------------

    def apply_phrase(
        self,
        text: str,
        name: str = "",
        statement: str = "",
        claim: EpistemicClaim | None = None,
    ) -> PhraseMapping:
        """Apply a controlled-English phrase to the state.

        A phrase that :func:`classify_phrase` does not put in the kernel **cannot change
        state**: this method returns before touching anything. That is the implemented
        form of the exclusion in `docs/design/V1_KERNEL.md` §0 — "for completeness" is not
        merely discouraged, it has no path into the machine.
        """
        mapping = classify_phrase(text)
        if not mapping.enters_kernel:
            return mapping

        construct = mapping.construct
        subject = name or _slug(statement or text)
        if construct is DiscourseConstruct.GOAL:
            self.goal(subject, statement)
        elif construct is DiscourseConstruct.SUBGOAL:
            self.subgoal(subject, statement)
        elif construct is DiscourseConstruct.PENDING_OBLIGATION:
            self.pending_obligation(subject, statement)
        elif construct is DiscourseConstruct.CONVERSE_GOAL:
            self.converse_goal(subject, statement or text)
        elif construct is DiscourseConstruct.CONSIDER_CASE:
            self.consider_case(subject, statement)
        elif construct is DiscourseConstruct.OTHERWISE:
            self.otherwise(subject)
        elif construct is DiscourseConstruct.RETURN_TO_GOAL:
            self.return_to_goal(subject)
        elif construct is DiscourseConstruct.DEPENDENCY_NOTICE:
            self.dependency_notice(self._current_goal or self.module, statement or text)
        elif construct is DiscourseConstruct.ESTABLISHED:
            if claim is None:
                self._record(
                    DiscourseError(
                        "HML-G803",
                        DiscourseConstruct.ESTABLISHED,
                        subject,
                        "a closing phrase was used with no claim; a goal is discharged "
                        "by a Proof, not by a sentence announcing that it is finished",
                    )
                )
            else:
                self.established(subject, claim)
        return mapping

    # -- results -------------------------------------------------------------

    @property
    def current_goal(self) -> str | None:
        return self._current_goal

    def item(self, name: str) -> OpenItem | None:
        return self._items.get(name)

    def is_open(self, name: str) -> bool:
        item = self._items.get(name)
        return item is not None and item.open

    def remains_to_show(self) -> tuple[PendingObligation, ...]:
        """The derived open set, in declaration order."""
        return tuple(
            PendingObligation(
                name=item.name,
                statement=item.statement,
                construct=item.construct,
                origin=item.origin,
                cases=item.cases,
            )
            for item in (self._items[n] for n in self._order)
            if item.open and item.construct in _OPENING
        )

    def errors(self) -> tuple[DiscourseError, ...]:
        return tuple(self._errors)

    def snapshot(self) -> tuple[object, ...]:
        """A comparable summary of everything this layer holds.

        Used to assert that a rhetorical phrase changed nothing at all — the strongest
        available statement of "it did not enter the kernel".
        """
        return (
            tuple(self._order),
            tuple((n, self._items[n].open) for n in self._order),
            tuple(s.name for s in self._open_splits),
            tuple(s.name for s in self._splits),
            tuple(e.code for e in self._errors),
            tuple(d.render() for d in self._dependencies),
            self._current_goal,
        )

    def end_module(self) -> DiscourseReport:
        """Close the module and report everything still open."""
        for split in list(self._open_splits):
            self._record(
                DiscourseError(
                    "HML-G805",
                    DiscourseConstruct.END_CASE,
                    split.name,
                    "the case split is still open at end of module",
                )
            )
        open_now = self.remains_to_show()
        for obligation in open_now:
            self._record(
                DiscourseError(
                    "HML-G808",
                    obligation.construct,
                    obligation.name,
                    f"still open at end of module: {obligation.statement}",
                )
            )
        splits = tuple(
            (s.name, self._exhaustiveness(s)) for s in self._splits + self._open_splits
        )
        return DiscourseReport(
            module=self.module,
            open_obligations=open_now,
            errors=tuple(self._errors),
            dependencies=tuple(self._dependencies),
            established=tuple(
                n for n in self._order if not self._items[n].open
            ),
            splits=splits,
            weakenings=tuple(self._weakenings),
        )


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return cleaned[:40] or "anonymous"
