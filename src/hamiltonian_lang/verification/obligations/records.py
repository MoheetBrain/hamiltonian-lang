"""The record schema every obligation checker must fill in.

One rule shapes this whole module: **a status is a claim, and every claim carries the
evidence that would let someone else disagree with it.** A record that says
``DISCHARGED`` without naming the checker, the checker's version, and what it actually
computed is indistinguishable from a record that says ``DISCHARGED`` because nothing
ran. The dataclasses below make the second one impossible to construct.

Four statuses, no synonyms
--------------------------
``DISCHARGED``
    A checker in the supported subset decided the obligation **true**, soundly, and
    recorded how.
``FAILED``
    A checker decided the obligation **false** and produced a witness. A failure
    without a witness is not a failure here — it is ``INCONCLUSIVE``.
``UNSUPPORTED``
    No implemented checker can express this obligation. This is the honest answer for
    everything outside the subset, and it **blocks** ``VERIFIED``. It is not a pass.
``INCONCLUSIVE``
    A checker applied, ran, and could not decide — or an earlier stage prevented it
    from running at all. Also blocks ``VERIFIED``.

The asymmetry between ``UNSUPPORTED`` and ``INCONCLUSIVE`` is deliberate: the first
says *this system has no theory for that*, the second says *this system tried and came
back empty*. Collapsing them would hide which of the two is growing.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ...ast.nodes import Span

__all__ = [
    "OBLIGATION_SCHEMA_VERSION",
    "ObligationStatus",
    "ObligationMode",
    "ObligationClass",
    "SUPPORTED_CLASSES",
    "SourceSpan",
    "Witness",
    "ObligationRecord",
    "SemanticLossRecord",
    "evidence_hash",
]

#: Bump when a field is added or a status changes meaning. Recorded on every report so
#: an old evidence file can never be silently read under new rules.
OBLIGATION_SCHEMA_VERSION = "hml-obligation-record-1.0.0"


class ObligationStatus(StrEnum):
    DISCHARGED = "DISCHARGED"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class ObligationMode(StrEnum):
    """What it would *mean* for an obligation to hold. Getting this wrong is the
    easiest way to build a verifier that is confidently incorrect.

    ``UNIVERSAL``
        The proposition must hold for **every** admissible assignment. A ``prove``,
        a concept ``invariant``, a distribution's cross-role constraint, and a
        refinement bound are all of this kind. Discharged by a proof; refuted by one
        counterexample.
    ``SATISFIABLE``
        The proposition must have **at least one** model. An HML ``require`` is a
        constraint on the solution, not a claim about every value — the Lean backend
        says so in its own words: *"`require x >= 0` for a free real x"* read as a
        theorem "may be false". An ``assume`` is a hypothesis, and the obligation it
        carries is consistency. Discharged by exhibiting a model; refuted by proving
        none exists.
    ``STRUCTURAL``
        Not a proposition over values at all — a dimension equality, a call's arity.
        Decided by recomputation.

    Treating a ``require`` as ``UNIVERSAL`` produces confident false failures on
    perfectly good programs; treating a ``prove`` as ``SATISFIABLE`` produces
    confident false successes. Both are worse than reporting nothing.
    """

    UNIVERSAL = "universal"
    SATISFIABLE = "satisfiable"
    STRUCTURAL = "structural"


class ObligationClass(StrEnum):
    """The classes this system claims to decide, plus one for everything else.

    The membership of :data:`SUPPORTED_CLASSES` is the *entire* verification claim of
    this package. Widening it requires a checker, fixtures on both sides, and an entry
    in ``docs/architecture/HML_PROCESS_VERIFICATION.md``.
    """

    LITERAL_REFINEMENT_BOUND = "literal_refinement_bound"
    CLOSED_ARITHMETIC_EQUALITY = "closed_arithmetic_equality"
    CLOSED_INEQUALITY = "closed_inequality"
    DIMENSION_COMPATIBILITY = "dimension_compatibility"
    DECLARED_SIGNATURE_CONFORMANCE = "declared_signature_conformance"
    FINITE_SET_MEMBERSHIP = "finite_set_membership"
    LOGICAL_CONSISTENCY = "logical_consistency"
    SYMBOLIC_IDENTITY = "symbolic_identity"
    NUMERICAL_COUNTEREXAMPLE = "numerical_counterexample"
    #: Not a supported class. Anything landing here is ``UNSUPPORTED`` by construction.
    OUT_OF_SUBSET = "out_of_subset"


#: Exactly the nine classes named in the M3 directive. ``OUT_OF_SUBSET`` is absent on
#: purpose: it is the label for *not* being in the subset.
SUPPORTED_CLASSES: frozenset[ObligationClass] = frozenset(
    {
        ObligationClass.LITERAL_REFINEMENT_BOUND,
        ObligationClass.CLOSED_ARITHMETIC_EQUALITY,
        ObligationClass.CLOSED_INEQUALITY,
        ObligationClass.DIMENSION_COMPATIBILITY,
        ObligationClass.DECLARED_SIGNATURE_CONFORMANCE,
        ObligationClass.FINITE_SET_MEMBERSHIP,
        ObligationClass.LOGICAL_CONSISTENCY,
        ObligationClass.SYMBOLIC_IDENTITY,
        ObligationClass.NUMERICAL_COUNTEREXAMPLE,
    }
)


@dataclass(frozen=True)
class SourceSpan:
    """A span, detached from the AST so a record can be serialised and re-read."""

    file: str = "<input>"
    line: int = 0
    col: int = 0
    end_line: int = 0
    end_col: int = 0

    @staticmethod
    def of(span: Span) -> SourceSpan:
        return SourceSpan(span.file, span.line, span.col, span.end_line, span.end_col)

    def render(self) -> str:
        return f"{self.file}:{self.line}:{self.col + 1}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "end_line": self.end_line,
            "end_col": self.end_col,
        }


@dataclass(frozen=True)
class Witness:
    """A concrete assignment that refutes the obligation.

    ``bindings`` maps a free name to the value that breaks the claim. It may be empty
    for a closed obligation (``2 + 3 = 6`` needs no assignment), but ``evaluated`` must
    then say what the two sides actually came to. A ``Witness`` that explains nothing
    is refused at construction, because an unexplained one is how a mere non-acceptance
    gets promoted to a refutation.
    """

    description: str
    bindings: Mapping[str, str] = field(default_factory=dict)
    evaluated: str = ""
    produced_by: str = ""

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("a witness must describe what it refutes")
        if not self.bindings and not self.evaluated.strip():
            raise ValueError(
                "a witness must carry either a refuting assignment or the evaluated "
                "values; neither is present, so this is a non-acceptance, not a refutation"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "bindings": dict(self.bindings),
            "evaluated": self.evaluated,
            "produced_by": self.produced_by,
        }


@dataclass(frozen=True)
class SemanticLossRecord:
    """Loss reported by a backend, lifted into the verification report.

    Any loss at all blocks ``VERIFIED``. A module whose laws were dropped on the way to
    a target is not a module whose laws were checked.
    """

    target: str
    construct: str
    reason: str
    severity: str = "dropped"
    line: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "construct": self.construct,
            "reason": self.reason,
            "severity": self.severity,
            "line": self.line,
        }


@dataclass(frozen=True)
class ObligationRecord:
    """One obligation, its verdict, and everything needed to re-derive that verdict.

    The invariants enforced in ``__post_init__`` are the ones that would otherwise be
    enforced only by reviewer attention:

    * ``DISCHARGED`` requires a supported class. Nothing outside the subset may pass.
    * ``DISCHARGED`` forbids a witness. A refuted claim is not a discharged one.
    * ``FAILED`` requires a witness. See :class:`Witness`.
    * ``UNSUPPORTED`` requires a reason naming the missing capability.
    """

    obligation_id: str
    span: SourceSpan
    obligation_class: ObligationClass
    checker: str
    checker_version: str
    status: ObligationStatus
    statement: str
    mode: ObligationMode = ObligationMode.UNIVERSAL
    #: ``type_checker`` for obligations the compiler emitted; ``derived`` for ones this
    #: package constructs from the module (call sites, cross-obligation consistency).
    origin: str = "type_checker"
    #: The compiler's own obligation kind, preserved verbatim.
    source_kind: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)
    witness: Witness | None = None
    #: Obligation IDs this verdict depends on. A discharge that rests on another
    #: obligation is only as good as that one, and the graph makes that auditable.
    dependencies: tuple[str, ...] = ()
    detail: str = ""
    schema_version: str = OBLIGATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status is ObligationStatus.DISCHARGED:
            if self.obligation_class not in SUPPORTED_CLASSES:
                raise ValueError(
                    f"{self.obligation_id}: class {self.obligation_class} is outside the "
                    f"supported subset and can never be DISCHARGED"
                )
            if self.witness is not None:
                raise ValueError(
                    f"{self.obligation_id}: a witness refutes the obligation; it cannot "
                    f"coexist with DISCHARGED"
                )
        if self.status is ObligationStatus.FAILED and self.witness is None:
            raise ValueError(
                f"{self.obligation_id}: FAILED requires a witness. Without one this is "
                f"'not accepted', which is INCONCLUSIVE, not false"
            )
        if self.status is ObligationStatus.UNSUPPORTED and not self.detail.strip():
            raise ValueError(
                f"{self.obligation_id}: UNSUPPORTED must say which capability is missing; "
                f"an unexplained skip looks identical to a check that silently did nothing"
            )

    @property
    def discharged(self) -> bool:
        return self.status is ObligationStatus.DISCHARGED

    def to_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "span": self.span.to_dict(),
            "class": str(self.obligation_class),
            "checker": self.checker,
            "checker_version": self.checker_version,
            "status": str(self.status),
            "statement": self.statement,
            "mode": str(self.mode),
            "origin": self.origin,
            "source_kind": self.source_kind,
            "evidence": _plain(self.evidence),
            "witness": self.witness.to_dict() if self.witness else None,
            "dependencies": list(self.dependencies),
            "detail": self.detail,
            "schema_version": self.schema_version,
        }

    def render(self) -> str:
        head = (
            f"[{self.status}] {self.obligation_id} "
            f"({self.obligation_class}/{self.mode}) {self.statement}"
        )
        tail = f"    {self.span.render()} via {self.checker}@{self.checker_version}"
        if self.witness is not None:
            tail += f"\n    witness: {self.witness.description}"
        if self.detail:
            tail += f"\n    {self.detail}"
        return f"{head}\n{tail}"


def _plain(value: Any) -> Any:
    """Coerce evidence into something ``json.dumps`` accepts, without losing shape."""
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Sequence):
        return [_plain(v) for v in value]
    return str(value)


def evidence_hash(payload: Any) -> str:
    """A stable digest of any evidence payload. Used to make a report reproducible."""
    blob = json.dumps(_plain(payload), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()
