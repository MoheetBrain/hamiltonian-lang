"""The engine: compile, derive, discharge, and reduce to one verdict.

``VERIFIED`` is emitted only when **all four** of these hold, and the conjunction is
written once, in :func:`_verdict`, so no caller can assemble a weaker version of it:

1. every required stage (lex, parse, resolve, type-check) reported no error;
2. every obligation — the compiler's and this engine's — is ``DISCHARGED``;
3. no semantic-preserving view of the module reported loss, and the HML surface
   round-trips to the same canonical content hash;
4. no obligation remains ``UNSUPPORTED``.

Condition 4 is the one that does the work. Dropping it would turn every gap in the
supported subset into a silent pass, and the endpoint would stop being able to fail —
which is the only reason it is worth measuring.

Semantic loss, split honestly
-----------------------------
Loss reported by ``latex``, ``lean``, ``stan`` and ``sympy`` is *lowering* loss: those
targets are known not to express everything HML expresses, and blocking on them would
make ``VERIFIED`` unreachable again for a reason that has nothing to do with the
obligation. Loss reported by ``hml``, ``json``, ``graph`` and ``triples`` is different
in kind — those views claim to *be* the semantic object — and it blocks. Both are
recorded; only the second gates.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Any

from ... import CompileResult, compile_source
from ...ast.nodes import (
    AssumeStmt,
    Call,
    CheckStmt,
    Comparison,
    ConceptDecl,
    DefineStmt,
    DistExpr,
    Expr,
    Module,
    ProveStmt,
    Ref,
    RequireStmt,
    Span,
    walk,
)
from ...type_system import ProofObligation
from ...types import Type
from .checkers import DEFAULT_CHECKERS, Checker, Judgement, ObligationTask
from .domains import Interval
from .evaluate import Environment, Undecidable, build_environment, evaluate
from .records import (
    OBLIGATION_SCHEMA_VERSION,
    ObligationClass,
    ObligationMode,
    ObligationRecord,
    ObligationStatus,
    SemanticLossRecord,
    SourceSpan,
    evidence_hash,
)

__all__ = [
    "ENGINE_VERSION",
    "GlobalVerdict",
    "SEMANTIC_PRESERVING_TARGETS",
    "LOWERING_TARGETS",
    "VerificationOutcome",
    "discharge",
    "verify_source",
    "verify_result",
]

ENGINE_VERSION = "hml-obligation-engine-1.0.0"

#: Views that claim to *be* the semantic object. Loss here blocks ``VERIFIED``.
SEMANTIC_PRESERVING_TARGETS: tuple[str, ...] = ("hml", "json", "graph", "triples")
#: Lowerings to foreign targets. Their loss is recorded and reported, never gating.
LOWERING_TARGETS: tuple[str, ...] = ("latex", "english", "lean", "stan", "sympy")


class GlobalVerdict(StrEnum):
    """One terminal label per module. Ordered worst-first in :func:`_verdict`."""

    INVALID = "INVALID"
    SEMANTIC_LOSS = "SEMANTIC_LOSS"
    DISPROVED = "DISPROVED"
    UNSUPPORTED = "UNSUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    VERIFIED = "VERIFIED"


@dataclass(frozen=True)
class VerificationOutcome:
    """The complete, reproducible answer for one module."""

    verdict: GlobalVerdict
    records: tuple[ObligationRecord, ...]
    diagnostics: tuple[str, ...]
    semantic_loss: tuple[SemanticLossRecord, ...]
    lowering_loss: tuple[SemanticLossRecord, ...]
    content_hash: str | None
    engine_version: str = ENGINE_VERSION
    schema_version: str = OBLIGATION_SCHEMA_VERSION
    detail: str = ""
    notes: tuple[str, ...] = ()

    # -- counts -----------------------------------------------------------
    def counts(self) -> dict[str, int]:
        out = {str(s): 0 for s in ObligationStatus}
        for r in self.records:
            out[str(r.status)] += 1
        return out

    def by_class(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.records:
            out[str(r.obligation_class)] = out.get(str(r.obligation_class), 0) + 1
        return out

    @property
    def verified(self) -> bool:
        return self.verdict is GlobalVerdict.VERIFIED

    @property
    def substantive(self) -> bool:
        """True when at least one discharge was **not** definitional.

        A module whose only discharged obligations restate their own declarations has
        been checked for nothing. It can still be ``VERIFIED`` — the conjunction in
        :func:`_verdict` is about soundness, not interest — but the H3 task filter
        refuses it, because a task that passes for free measures nothing.
        """
        return any(
            r.discharged and not r.evidence.get("definitional", False) for r in self.records
        )

    @property
    def discharged_fraction(self) -> float:
        if not self.records:
            return 1.0
        return sum(1 for r in self.records if r.discharged) / len(self.records)

    def first_failure(self) -> ObligationRecord | None:
        for r in self.records:
            if r.status is ObligationStatus.FAILED:
                return r
        return None

    def blocking(self) -> tuple[ObligationRecord, ...]:
        return tuple(r for r in self.records if not r.discharged)

    def evidence_digest(self) -> str:
        return evidence_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": str(self.verdict),
            "verified": self.verified,
            "substantive": self.substantive,
            "engine_version": self.engine_version,
            "schema_version": self.schema_version,
            "content_hash": self.content_hash,
            "counts": self.counts(),
            "by_class": self.by_class(),
            "discharged_fraction": round(self.discharged_fraction, 6),
            "diagnostics": list(self.diagnostics),
            "semantic_loss": [s.to_dict() for s in self.semantic_loss],
            "lowering_loss": [s.to_dict() for s in self.lowering_loss],
            "obligations": [r.to_dict() for r in self.records],
            "detail": self.detail,
            "notes": list(self.notes),
        }

    def render(self) -> str:
        head = f"{self.verdict}  ({len(self.records)} obligation(s))  {self.detail}".strip()
        lines = [head]
        for r in self.records:
            lines.append(r.render())
        for loss in self.semantic_loss:
            lines.append(f"[SEMANTIC LOSS] {loss.target}: {loss.construct} — {loss.reason}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Obligation identity
# ---------------------------------------------------------------------------


def _obligation_id(index: int, kind: str, statement: str, span: Span) -> str:
    digest = hashlib.sha256(
        f"{kind}|{statement}|{span.line}:{span.col}:{span.end_line}:{span.end_col}".encode()
    ).hexdigest()[:8]
    return f"OBL-{index:03d}-{digest}"


#: ``(id, kind, statement, span, proposition, mode, context)``
_Seed = tuple[str, str, str, Span, "Expr | None", ObligationMode, dict[str, Any]]


# ---------------------------------------------------------------------------
# Provenance -> mode
# ---------------------------------------------------------------------------


def _provenance_map(module: Module) -> dict[tuple[int, int], str]:
    """Map a statement span to the construct that produced its obligation.

    The type checker labels a ``require``, a concept ``invariant`` and a distribution's
    cross-role constraint all as ``kind == "constraint"``, but they do not mean the same
    thing: the first must merely have a model, the other two must hold universally.
    Recovering the difference from the module is therefore not optional — without it the
    verifier would report a confident, wrong failure on every ordinary ``require``.
    """
    out: dict[tuple[int, int], str] = {}
    for st in module.statements:
        key = (st.span.line, st.span.col)
        if isinstance(st, RequireStmt):
            out[key] = "require"
        elif isinstance(st, AssumeStmt):
            out[key] = "assume"
        elif isinstance(st, ProveStmt):
            out[key] = "prove"
        elif isinstance(st, ConceptDecl):
            for member in st.members_of("invariant"):
                out[(member.span.line, member.span.col)] = "invariant"
    for node in walk(module):
        if isinstance(node, DistExpr):
            out.setdefault((node.span.line, node.span.col), "distribution_cross_constraint")
    return out


#: How each provenance is to be read. ``require`` and ``assume`` are constraints on the
#: solution; everything else is a claim about every admissible value.
_MODE_BY_PROVENANCE: dict[str, ObligationMode] = {
    "require": ObligationMode.SATISFIABLE,
    "assume": ObligationMode.SATISFIABLE,
    "prove": ObligationMode.UNIVERSAL,
    "invariant": ObligationMode.UNIVERSAL,
    "distribution_cross_constraint": ObligationMode.UNIVERSAL,
}


def _mode_of(obligation: ProofObligation, provenance: Mapping[tuple[int, int], str]) -> tuple[
    ObligationMode, str
]:
    if obligation.kind == "dimension":
        return ObligationMode.STRUCTURAL, "check dimension"
    if obligation.kind == "parameter_positivity":
        return ObligationMode.UNIVERSAL, "declared refinement type"
    where = provenance.get((obligation.span.line, obligation.span.col))
    if where is None:
        # An obligation whose producing statement cannot be identified is read the
        # strict way. Guessing "satisfiable" here would be the permissive guess, and
        # the permissive guess is the one that manufactures false passes.
        return ObligationMode.UNIVERSAL, "unattributed"
    return _MODE_BY_PROVENANCE.get(where, ObligationMode.UNIVERSAL), where


# ---------------------------------------------------------------------------
# Derived obligations
# ---------------------------------------------------------------------------


def _signature_tasks(module: Module, env: Environment, start: int) -> list[_Seed]:
    """One obligation per call site into a declared signature.

    Every construct the compiler could call is covered: module-level ``def`` with
    parameters, and ``transform`` members of a concept.
    """
    signatures: dict[str, tuple[Sequence[tuple[str, Type | None]], str]] = {}
    for st in module.statements:
        if isinstance(st, DefineStmt) and st.params:
            signatures[st.name] = (st.params, "definition")
        elif isinstance(st, ConceptDecl):
            for member in st.members_of("transform"):
                if member.params:
                    signatures[member.name] = (member.params, "concept transform")
    out: list[_Seed] = []
    index = start
    for node in walk(module):
        if not isinstance(node, Call):
            continue
        entry = signatures.get(node.callee)
        if entry is None:
            continue
        params, source = entry
        statement = (
            f"the call to {node.callee} matches its declared arity and parameter types"
        )
        out.append(
            (
                _obligation_id(index, "signature", statement, node.span),
                "signature",
                statement,
                node.span,
                None,
                ObligationMode.STRUCTURAL,
                {
                    "derived": "signature",
                    "callee": node.callee,
                    "params": list(params),
                    "args": list(node.args),
                    "declared_in": source,
                },
            )
        )
        index += 1
    return out


def _feasibility_task(
    tasks: Sequence[ObligationTask], env: Environment, start: int
) -> list[_Seed]:
    """One module-level obligation: *the constraint set has a model*.

    ``require x > 5`` and ``require x < 3`` are each satisfiable alone. Together they
    have none, and neither constraint on its own reveals it. That joint fact belongs to
    no individual obligation, so the engine derives it and makes every contributing
    constraint a dependency of it — which is what the ``dependencies`` field is for.
    """
    constraints = [
        t
        for t in tasks
        if t.mode is ObligationMode.SATISFIABLE and t.proposition is not None
    ]
    if len(constraints) < 2:
        return []

    # Sound infeasibility: per-variable interval intersection. Only simple
    # ``<name> op <closed>`` bounds contribute, because those are the only ones whose
    # interval is exact rather than over-approximated.
    bounds: dict[str, list[tuple[Interval, str]]] = {}
    for task in constraints:
        expr = task.proposition
        if not isinstance(expr, Comparison) or expr.op not in ("<", "<=", ">", ">="):
            continue
        if not isinstance(expr.left, Ref) or env.domain(expr.left.name) is None:
            continue
        try:
            right = evaluate(expr.right, env)
        except Undecidable:
            continue
        constant = right.number
        if not isinstance(constant, Fraction):
            continue
        interval = {
            ">": Interval(lo=constant, lo_closed=False),
            ">=": Interval(lo=constant, lo_closed=True),
            "<": Interval(hi=constant, hi_closed=False),
            "<=": Interval(hi=constant, hi_closed=True),
        }[expr.op]
        bounds.setdefault(expr.left.name, []).append(
            (interval, f"{{{expr.left.name} {expr.op} {right.render()}}}")
        )

    empty_variables: dict[str, list[str]] = {}
    for name, entries in sorted(bounds.items()):
        domain = env.domain(name)
        assert domain is not None
        feasible = domain.interval
        for interval, _label in entries:
            feasible = feasible.intersect(interval)
        if feasible.empty:
            empty_variables[name] = [domain.interval.render(), *[e[1] for e in entries]]

    statement = "the module's constraint set has a model"
    span = Span()
    return [
        (
            _obligation_id(start, "feasibility", statement, span),
            "feasibility",
            statement,
            span,
            None,
            ObligationMode.SATISFIABLE,
            {
                "derived": "feasibility",
                "propositions": [t.proposition for t in constraints],
                "empty_variables": empty_variables,
                "dependencies": [t.obligation_id for t in constraints],
            },
        )
    ]


# ---------------------------------------------------------------------------
# Discharge
# ---------------------------------------------------------------------------


def _asserted_dimension(module: Module, span: Span) -> str | None:
    for st in module.statements:
        if isinstance(st, CheckStmt) and st.check_kind == "dimension":
            if st.span.line == span.line and st.span.col == span.col:
                return st.expected
    return None


def discharge(
    result: CompileResult, *, checkers: Sequence[Checker] = DEFAULT_CHECKERS
) -> tuple[ObligationRecord, ...]:
    """Run the checker pipeline over every obligation, compiler-emitted and derived."""
    env = build_environment(result.module, result.symbols)
    provenance = _provenance_map(result.module)
    seeds: list[_Seed] = []
    for index, obligation in enumerate(result.obligations):
        mode, where = _mode_of(obligation, provenance)
        context: dict[str, Any] = {"provenance": where}
        if obligation.kind == "dimension":
            context["asserted_dimension"] = _asserted_dimension(result.module, obligation.span)
        seeds.append(
            (
                _obligation_id(index, obligation.kind, obligation.description, obligation.span),
                obligation.kind,
                obligation.description,
                obligation.span,
                obligation.expression,
                mode,
                context,
            )
        )
    seeds.extend(_signature_tasks(result.module, env, len(seeds)))
    seeds.extend(_feasibility_task(_to_tasks(seeds, env), env, len(seeds)))

    tasks = _to_tasks(seeds, env)
    spans = {seed[0]: seed[3] for seed in seeds}

    records: list[ObligationRecord] = []
    for task in tasks:
        enriched = ObligationTask(
            obligation_id=task.obligation_id,
            kind=task.kind,
            statement=task.statement,
            proposition=task.proposition,
            env=task.env,
            mode=task.mode,
            siblings=tasks,
            context=task.context,
        )
        records.append(_run_pipeline(enriched, spans[task.obligation_id], checkers))
    return tuple(records)


def _to_tasks(seeds: Sequence[_Seed], env: Environment) -> tuple[ObligationTask, ...]:
    return tuple(
        ObligationTask(
            obligation_id=oid,
            kind=kind,
            statement=statement,
            proposition=proposition,
            env=env,
            mode=mode,
            context=context,
        )
        for oid, kind, statement, _span, proposition, mode, context in seeds
    )


def _run_pipeline(
    task: ObligationTask, span: Span, checkers: Sequence[Checker]
) -> ObligationRecord:
    attempted: list[str] = []
    fallback: tuple[Checker, Judgement] | None = None
    for checker in checkers:
        judgement = checker.judge(task)
        if judgement is None:
            continue
        attempted.append(checker.name)
        if judgement.status in (ObligationStatus.DISCHARGED, ObligationStatus.FAILED):
            return _record(task, span, checker, judgement, attempted)
        if fallback is None:
            fallback = (checker, judgement)
    if fallback is not None:
        checker, judgement = fallback
        return _record(task, span, checker, judgement, attempted)
    return ObligationRecord(
        obligation_id=task.obligation_id,
        span=SourceSpan.of(span),
        obligation_class=ObligationClass.OUT_OF_SUBSET,
        checker="none",
        checker_version=ENGINE_VERSION,
        status=ObligationStatus.UNSUPPORTED,
        statement=task.statement,
        mode=task.mode,
        origin="derived" if task.context.get("derived") else "type_checker",
        source_kind=task.kind,
        evidence={
            "checkers_attempted": attempted,
            "shape": type(task.proposition).__name__,
            "provenance": task.context.get("provenance", ""),
        },
        detail=(
            "no implemented checker claims this obligation; it lies outside the "
            "supported verification subset"
        ),
    )


def _record(
    task: ObligationTask,
    span: Span,
    checker: Checker,
    judgement: Judgement,
    attempted: Sequence[str],
) -> ObligationRecord:
    evidence = dict(judgement.evidence)
    evidence["checkers_attempted"] = list(attempted)
    evidence.setdefault("provenance", task.context.get("provenance", ""))
    return ObligationRecord(
        obligation_id=task.obligation_id,
        span=SourceSpan.of(span),
        obligation_class=judgement.obligation_class,
        checker=checker.name,
        checker_version=checker.version,
        status=judgement.status,
        statement=task.statement,
        mode=task.mode,
        origin="derived" if task.context.get("derived") else "type_checker",
        source_kind=task.kind,
        evidence=evidence,
        witness=judgement.witness,
        dependencies=judgement.dependencies,
        detail=judgement.detail,
    )


# ---------------------------------------------------------------------------
# Semantic-loss probe
# ---------------------------------------------------------------------------


def _probe_loss(
    result: CompileResult, targets: Iterable[str]
) -> tuple[list[SemanticLossRecord], list[str]]:
    losses: list[SemanticLossRecord] = []
    notes: list[str] = []
    for target in targets:
        try:
            rendered = result.render(target)
        except Exception as exc:  # noqa: BLE001 - a crashing view is itself a finding
            notes.append(f"{target}: the view could not be produced ({type(exc).__name__}: {exc})")
            continue
        for u in rendered.unsupported:
            losses.append(SemanticLossRecord(target, u.construct, u.reason, u.severity, u.line))
    return losses, notes


def _roundtrip_loss(result: CompileResult) -> tuple[list[SemanticLossRecord], str | None]:
    """Render the module back to HML, recompile, and compare canonical hashes.

    A backend that reports no loss has said only that it noticed none. Comparing the
    alpha-invariant content hash is the check that does not depend on the backend's own
    self-report.
    """
    try:
        original = result.hash()
    except Exception as exc:  # noqa: BLE001
        return (
            [
                SemanticLossRecord(
                    "hml", "content hash", f"the module has no canonical hash: {exc}", "dropped"
                )
            ],
            None,
        )
    try:
        surface = result.render("hml").text
    except Exception as exc:  # noqa: BLE001
        return (
            [
                SemanticLossRecord(
                    "hml", "surface", f"the HML view could not be produced: {exc}", "dropped"
                )
            ],
            original,
        )
    again = compile_source(surface, "<roundtrip>")
    if not again.ok():
        return (
            [
                SemanticLossRecord(
                    "hml",
                    "round trip",
                    "the rendered HML surface does not recompile: "
                    + ", ".join(d.code for d in again.diagnostics.errors),
                    "dropped",
                )
            ],
            original,
        )
    if again.hash() != original:
        return (
            [
                SemanticLossRecord(
                    "hml",
                    "round trip",
                    f"the canonical content hash changed across the HML round trip "
                    f"({original[:12]} -> {again.hash()[:12]})",
                    "weakened",
                )
            ],
            original,
        )
    return [], original


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


def _verdict(
    ok: bool,
    records: Sequence[ObligationRecord],
    semantic_loss: Sequence[SemanticLossRecord],
) -> tuple[GlobalVerdict, str]:
    if not ok:
        return GlobalVerdict.INVALID, "a required compiler stage reported an error"
    if semantic_loss:
        return (
            GlobalVerdict.SEMANTIC_LOSS,
            f"{len(semantic_loss)} semantic-preserving view(s) reported loss",
        )
    statuses = [r.status for r in records]
    if ObligationStatus.FAILED in statuses:
        return GlobalVerdict.DISPROVED, "at least one obligation was refuted with a witness"
    # UNSUPPORTED outranks INCONCLUSIVE: the first names a capability this system does
    # not have, the second names an attempt that came back empty. Reporting the second
    # while the first is present would understate the gap.
    if ObligationStatus.UNSUPPORTED in statuses:
        return (
            GlobalVerdict.UNSUPPORTED,
            f"{statuses.count(ObligationStatus.UNSUPPORTED)} obligation(s) lie outside "
            f"the supported subset",
        )
    if ObligationStatus.INCONCLUSIVE in statuses:
        return (
            GlobalVerdict.INCONCLUSIVE,
            f"{statuses.count(ObligationStatus.INCONCLUSIVE)} obligation(s) were "
            f"attempted and not decided",
        )
    return GlobalVerdict.VERIFIED, "every obligation is discharged and no semantic loss was found"


def verify_result(
    result: CompileResult,
    *,
    checkers: Sequence[Checker] = DEFAULT_CHECKERS,
    semantic_targets: Sequence[str] = SEMANTIC_PRESERVING_TARGETS,
    lowering_targets: Sequence[str] = LOWERING_TARGETS,
) -> VerificationOutcome:
    """Verify an already-compiled module."""
    diagnostics = tuple(d.code for d in result.diagnostics.errors)
    if not result.ok():
        verdict, detail = _verdict(False, (), ())
        return VerificationOutcome(
            verdict=verdict,
            records=(),
            diagnostics=diagnostics,
            semantic_loss=(),
            lowering_loss=(),
            content_hash=None,
            detail=detail,
            notes=("obligation discharge did not run because compilation failed",),
        )

    records = discharge(result, checkers=checkers)
    semantic, notes = _probe_loss(result, semantic_targets)
    roundtrip, content = _roundtrip_loss(result)
    semantic.extend(roundtrip)
    lowering, lowering_notes = _probe_loss(result, lowering_targets)
    verdict, detail = _verdict(True, records, semantic)
    return VerificationOutcome(
        verdict=verdict,
        records=records,
        diagnostics=diagnostics,
        semantic_loss=tuple(semantic),
        lowering_loss=tuple(lowering),
        content_hash=content,
        detail=detail,
        notes=tuple(notes + lowering_notes),
    )


def verify_source(
    source: str,
    file: str = "<input>",
    *,
    checkers: Sequence[Checker] = DEFAULT_CHECKERS,
    semantic_targets: Sequence[str] = SEMANTIC_PRESERVING_TARGETS,
    lowering_targets: Sequence[str] = LOWERING_TARGETS,
) -> VerificationOutcome:
    """Compile ``source`` and verify it end to end."""
    return verify_result(
        compile_source(source, file),
        checkers=checkers,
        semantic_targets=semantic_targets,
        lowering_targets=lowering_targets,
    )
