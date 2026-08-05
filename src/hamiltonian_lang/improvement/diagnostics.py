"""Structured diagnostics adapter — Phase 8.

The compiler's :class:`hamiltonian_lang.diagnostics.Diagnostic` is unchanged and remains
the source of truth. This module is a **versioned adapter** that presents the same
diagnostic in the shape a repair loop can consume: a code, a category, a span, what was
expected, what was found, the invariant that was violated, a local hint and, where one
exists, a counterexample.

Five properties, and the one that is easy to lose
--------------------------------------------------
*Local* -- the span names one construct, not the module.
*Causal* -- the invariant explains why the construct is wrong, not merely that it is.
*Actionable* -- the hint names a correction that can be applied at the span.
*Stable* -- :meth:`StructuredDiagnostic.fingerprint` is invariant under line numbers and
free text, so the same defect groups with itself across runs.
*Non-leaking* -- and this is the one that quietly destroys an experiment.

A diagnostic that contains the complete target program, the final mathematical answer, or
an unrestricted replacement patch does not measure verifier-guided repair; it measures
copying. The H3 hypothesis then returns a number that cannot be interpreted, and nothing
in the resulting record shows why. :func:`assert_non_leaking` is the mechanical guard, it
is called by :func:`adapt_and_check`, and it refuses rather than warns.

Gaps are recorded, never filled
--------------------------------
Most compiler diagnostics do not carry a counterexample, and the great majority have no
entry in :data:`VIOLATED_INVARIANT_BY_CODE`. The adapter leaves those fields ``None`` and
appends the field name to :attr:`StructuredDiagnostic.gaps`. Inventing a plausible
invariant would put text of unknown provenance into the training record, which is exactly
the failure this project exists to avoid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..diagnostics import Diagnostic, Severity
from .events import canonical_blob, sha256_hex

__all__ = [
    "DIAGNOSTIC_ADAPTER_VERSION",
    "DiagnosticCategory",
    "SourceSpan",
    "StructuredDiagnostic",
    "DiagnosticLeak",
    "VIOLATED_INVARIANT_BY_CODE",
    "adapt",
    "adapt_all",
    "adapt_and_check",
    "assert_non_leaking",
    "leak_reasons",
]

#: Bumped whenever the mapping below changes meaning. Every adapted diagnostic carries
#: it, so a record written under an older adapter stays interpretable.
DIAGNOSTIC_ADAPTER_VERSION = "hml-diagnostic-adapter-1.0.0"


class DiagnosticCategory(StrEnum):
    """Derived from the code prefix. See ``hamiltonian_lang/diagnostics/__init__.py``."""

    LEXICAL = "lexical"
    PARSE = "parse"
    RESOLUTION = "resolution"
    TYPE = "type"
    DIMENSIONAL = "dimensional"
    SEMANTIC = "semantic"
    BACKEND = "backend"
    EPISTEMIC = "epistemic"
    DISCOURSE = "discourse"
    TRANSFORMATION = "transformation"
    #: The code does not match any known family. Recorded, not guessed.
    UNCLASSIFIED = "unclassified"


_CATEGORY_BY_PREFIX: dict[str, DiagnosticCategory] = {
    "L": DiagnosticCategory.LEXICAL,
    "P": DiagnosticCategory.PARSE,
    "N": DiagnosticCategory.RESOLUTION,
    "T": DiagnosticCategory.TYPE,
    "D": DiagnosticCategory.DIMENSIONAL,
    "S": DiagnosticCategory.SEMANTIC,
    "B": DiagnosticCategory.BACKEND,
    "E": DiagnosticCategory.EPISTEMIC,
    "G": DiagnosticCategory.DISCOURSE,
    "X": DiagnosticCategory.TRANSFORMATION,
}

_CODE = re.compile(r"^HML-([A-Z])(\d{3})$")

#: Invariants stated only where the compiler's own rule is unambiguous and written down
#: in ``SPEC.md`` or ``CLAUDE.md``. Everything absent from this table produces a gap.
#:
#: Deliberately short. A long table assembled by guessing at what a code "probably" means
#: would be indistinguishable, in the record, from one assembled by reading the rules.
VIOLATED_INVARIANT_BY_CODE: dict[str, str] = {
    "HML-N301": "every name must resolve to a binding that is in scope at its use site",
    "HML-N302": "a name may be bound at most once in a scope",
    "HML-T402": "a declared value must inhabit its declared type",
    "HML-T403": "a definition body must inhabit the definition's declared result type",
    "HML-T413": "a distribution argument must inhabit the type its role demands",
    "HML-T440": "a type annotation must name a type the checker knows",
    "HML-D501": (
        "operands of an additive operator must have equal physical dimension"
    ),
    "HML-D502": (
        "a comparison requires dimensional equality on both sides"
    ),
}


@dataclass(frozen=True)
class SourceSpan:
    """Where the defect is. Zero line means the compiler did not attribute a location."""

    line: int = 0
    col: int = 0
    end_line: int = 0
    end_col: int = 0
    file: str = "<input>"

    @property
    def located(self) -> bool:
        return self.line > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "line": self.line, "col": self.col, "end_line": self.end_line,
            "end_col": self.end_col, "file": self.file,
        }


class DiagnosticLeak(Exception):
    """A structured diagnostic carried information a repair loop must not receive."""


@dataclass(frozen=True)
class StructuredDiagnostic:
    """The adapted form. The compiler's diagnostic is not modified to produce it."""

    code: str
    category: DiagnosticCategory
    source_span: SourceSpan
    #: Human-readable text, kept so that :meth:`render` reproduces what a user would see.
    #: The structured fields, not this string, are the machine-readable form.
    message: str = ""
    severity: Severity = Severity.ERROR
    expected: str | None = None
    actual: str | None = None
    violated_invariant: str | None = None
    local_hint: str | None = None
    counterexample: str | None = None
    #: Field names the source diagnostic did not carry. Never filled by inference.
    gaps: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    diagnostic_version: str = DIAGNOSTIC_ADAPTER_VERSION

    # -- rendering ---------------------------------------------------------------

    def render(self) -> str:
        """The human-readable diagnostic, composed from the structured fields.

        The message survives verbatim: the structured form is a refinement of the
        compiler's diagnostic, not a replacement for it.
        """
        parts = [f"{self.severity.value} {self.code}: {self.message}"]
        if self.source_span.located:
            parts.append(
                f"  --> {self.source_span.file}:{self.source_span.line}:"
                f"{self.source_span.col + 1}"
            )
        if self.actual is not None:
            parts.append(f"  found:    {self.actual}")
        if self.expected is not None:
            parts.append(f"  expected: {self.expected}")
        if self.violated_invariant is not None:
            parts.append(f"  invariant: {self.violated_invariant}")
        if self.counterexample is not None:
            parts.append(f"  counterexample: {self.counterexample}")
        for note in self.notes:
            parts.append(f"  note: {note}")
        if self.local_hint is not None:
            parts.append(f"  help: {self.local_hint}")
        return "\n".join(parts)

    def text_fields(self) -> list[str]:
        """Every free-text field. What :func:`leak_reasons` inspects."""
        out = [self.message]
        for value in (
            self.expected, self.actual, self.violated_invariant,
            self.local_hint, self.counterexample,
        ):
            if value is not None:
                out.append(value)
        out.extend(self.notes)
        return out

    # -- stability ---------------------------------------------------------------

    def fingerprint(self) -> str:
        """Identity of the *defect*, not of the occurrence.

        Excludes the span and the message so that the same defect at a different line,
        or reworded in a later release, still groups with itself a year later.
        """
        return sha256_hex(
            canonical_blob(
                {
                    "code": self.code,
                    "category": str(self.category),
                    "expected": self.expected,
                    "actual": self.actual,
                    "violated_invariant": self.violated_invariant,
                    "diagnostic_version": self.diagnostic_version,
                }
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "category": str(self.category),
            "source_span": self.source_span.to_dict(),
            "message": self.message,
            "severity": self.severity.value,
            "expected": self.expected,
            "actual": self.actual,
            "violated_invariant": self.violated_invariant,
            "local_hint": self.local_hint,
            "counterexample": self.counterexample,
            "gaps": list(self.gaps),
            "notes": list(self.notes),
            "diagnostic_version": self.diagnostic_version,
            "fingerprint": self.fingerprint(),
        }


# ---------------------------------------------------------------------------
# Adaptation
# ---------------------------------------------------------------------------


def _category_of(code: str) -> tuple[DiagnosticCategory, bool]:
    match = _CODE.match(code)
    if match is None:
        return DiagnosticCategory.UNCLASSIFIED, False
    category = _CATEGORY_BY_PREFIX.get(match.group(1))
    if category is None:
        return DiagnosticCategory.UNCLASSIFIED, False
    return category, True


def adapt(diagnostic: Diagnostic) -> StructuredDiagnostic:
    """Convert one compiler diagnostic. Absent information becomes a recorded gap."""
    category, known = _category_of(diagnostic.code)
    gaps: list[str] = []
    if not known:
        gaps.append("category")

    span = SourceSpan(
        line=diagnostic.line, col=diagnostic.col,
        end_line=diagnostic.end_line, end_col=diagnostic.end_col,
        file=diagnostic.file,
    )
    if not span.located:
        gaps.append("source_span")

    if diagnostic.expected is None:
        gaps.append("expected")
    if diagnostic.found is None:
        gaps.append("actual")

    invariant = VIOLATED_INVARIANT_BY_CODE.get(diagnostic.code)
    if invariant is None:
        gaps.append("violated_invariant")

    if diagnostic.correction is None:
        gaps.append("local_hint")

    # No compiler diagnostic carries a counterexample today. The field exists because
    # verifiers produce them (see improvement/verification.py); the gap records that this
    # one did not, rather than leaving the reader to guess whether it was searched for.
    gaps.append("counterexample")

    return StructuredDiagnostic(
        code=diagnostic.code,
        category=category,
        source_span=span,
        message=diagnostic.message,
        severity=diagnostic.severity,
        expected=diagnostic.expected,
        actual=diagnostic.found,
        violated_invariant=invariant,
        local_hint=diagnostic.correction,
        counterexample=None,
        gaps=tuple(gaps),
        notes=tuple(diagnostic.notes),
    )


def adapt_all(diagnostics: object) -> list[StructuredDiagnostic]:
    """Adapt a :class:`~hamiltonian_lang.diagnostics.DiagnosticBag` or any iterable."""
    return [adapt(d) for d in diagnostics]  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# The non-leaking contract
# ---------------------------------------------------------------------------

#: A hint longer than this many non-blank lines stops being a local correction and
#: becomes a patch. Three lines is generous for "annotate the operand as Quantity[...]".
MAX_HINT_LINES = 3

#: HML statement keywords. A hint containing more than one is a program fragment, not a
#: correction to one construct.
_STATEMENT_KEYWORDS = (
    "module", "param", "const", "var", "result", "def", "law", "prior", "likelihood",
    "assume", "require", "prove", "minimise", "maximise", "minimize", "maximize",
    "solve", "infer", "check", "concept",
)

#: Below this many significant tokens, a "program" is too short for containment to mean
#: anything -- every diagnostic mentioning ``x`` would otherwise be a leak.
_MIN_PROGRAM_TOKENS = 4


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _significant_tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[0-9.]+", text)]


def leak_reasons(
    diagnostic: StructuredDiagnostic,
    *,
    target_program: str | None = None,
    final_answer: str | None = None,
) -> list[str]:
    """Every way ``diagnostic`` violates the non-leaking contract. Empty means clean."""
    reasons: list[str] = []
    fields = diagnostic.text_fields()
    haystack = _normalise(" \n ".join(fields))

    if target_program:
        needle = _normalise(target_program)
        if len(_significant_tokens(needle)) >= _MIN_PROGRAM_TOKENS and needle in haystack:
            reasons.append(
                "contains the complete target program; a repair loop given the answer "
                "measures copying, not verifier-guided reasoning"
            )

    if final_answer:
        answer = _normalise(final_answer)
        if answer and answer in haystack:
            reasons.append(
                "contains the final mathematical answer; any H3 result computed from "
                "this episode would be uninterpretable"
            )

    hint = diagnostic.local_hint
    if hint:
        lines = [ln for ln in hint.splitlines() if ln.strip()]
        if len(lines) > MAX_HINT_LINES:
            reasons.append(
                f"local_hint spans {len(lines)} lines (limit {MAX_HINT_LINES}); a hint "
                f"that long is a replacement patch rather than a local correction"
            )
        found = {
            kw for kw in _STATEMENT_KEYWORDS
            if re.search(rf"(?<![A-Za-z0-9_]){kw}\s", hint)
        }
        if len(found) > 1:
            reasons.append(
                f"local_hint contains multiple statement keywords {sorted(found)}; it is "
                f"a program fragment, not a correction to one construct"
            )
    return reasons


def assert_non_leaking(
    diagnostic: StructuredDiagnostic,
    *,
    target_program: str | None = None,
    final_answer: str | None = None,
) -> StructuredDiagnostic:
    """Raise :class:`DiagnosticLeak` if the contract is violated; return it otherwise."""
    reasons = leak_reasons(
        diagnostic, target_program=target_program, final_answer=final_answer
    )
    if reasons:
        raise DiagnosticLeak(
            f"{diagnostic.code}: " + "; ".join(reasons)
        )
    return diagnostic


def adapt_and_check(
    diagnostic: Diagnostic,
    *,
    target_program: str | None = None,
    final_answer: str | None = None,
) -> StructuredDiagnostic:
    """Adapt, then enforce the non-leaking contract. The path a repair loop should use."""
    return assert_non_leaking(
        adapt(diagnostic), target_program=target_program, final_answer=final_answer
    )
