"""The ordered funnel. Gate 1 is the cheap one; it is never the last one.

::

    1. parser/compiler validation
    2. deterministic semantic checks
    3. back-translation consistency
    4. counterexample or negation attack
    5. human review when unresolved or promotion-critical

Ordering is total and short-circuiting: a later gate never runs on an item an earlier gate
rejected. That is not an optimisation. Asking whether a non-compiling object back-translates
faithfully is asking about the meaning of something that has no meaning, and recording an
answer would put a fabricated verdict in the audit trail.

The funnel's own drop rate is the headline number
-------------------------------------------------
:class:`FunnelReport` reports survival at every stage, so the FormalMATH comparison is
available directly: their funnel went from ~92% compiler-valid to ~32% retained. A run of
this funnel that reports ~92% at gate 1 and ~92% at gate 5 has not validated a corpus; it
has demonstrated that gates 2 to 5 are not doing anything, and that is the first thing to
check about any corpus this package blesses.

Rejections are recorded, never deleted
--------------------------------------
Every rejected candidate stays in :attr:`FunnelReport.decisions` with the gate that
rejected it and why. A funnel that discards its own rejects cannot report a drop rate, and
a drop rate that cannot be reported cannot be audited.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from hamiltonian_lang import compile_source

from . import CORPUS_GOVERNANCE_VERSION, GATE_ORDER
from .back_translation import Alignment, JudgePanel
from .human_gate import ReviewQueue, ReviewRequest, ReviewTrigger
from .negation import NegationOutcome, Refutation
from .semantic_checks import SemanticReport

__all__ = [
    "Gate",
    "GateOutcome",
    "ItemDecision",
    "FunnelReport",
    "compiler_gate",
    "run_funnel",
]


class Gate(StrEnum):
    COMPILER = "compiler"
    DETERMINISTIC_SEMANTICS = "deterministic_semantics"
    BACK_TRANSLATION = "back_translation"
    NEGATION_ATTACK = "negation_attack"
    HUMAN_REVIEW = "human_review"


assert tuple(g.value for g in Gate) == GATE_ORDER, "Gate enum drifted from GATE_ORDER"


class GateOutcome(StrEnum):
    PASSED = "passed"
    REJECTED = "rejected"
    #: Sent to gate 5. Not a pass and not a rejection; the machinery declined to decide.
    ESCALATED = "escalated"


@dataclass(frozen=True)
class GateRecord:
    gate: Gate
    outcome: GateOutcome
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"gate": str(self.gate), "outcome": str(self.outcome), "detail": self.detail}


@dataclass(frozen=True)
class ItemDecision:
    """One candidate's whole journey, including the gates it never reached."""

    item_id: str
    records: tuple[GateRecord, ...]

    @property
    def final_gate(self) -> Gate:
        return self.records[-1].gate

    @property
    def outcome(self) -> GateOutcome:
        return self.records[-1].outcome

    def admitted(self) -> bool:
        """Admitted only by passing **every** gate. Reaching gate 5 is not passing it."""
        return len(self.records) == len(Gate) and all(
            r.outcome is GateOutcome.PASSED for r in self.records
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "admitted": self.admitted(),
            "final_gate": str(self.final_gate),
            "outcome": str(self.outcome),
            "records": [r.to_dict() for r in self.records],
        }


@dataclass
class FunnelReport:
    """Survival at every stage. The drop rate is the point of the report."""

    governance_version: str = CORPUS_GOVERNANCE_VERSION
    decisions: list[ItemDecision] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.decisions)

    @property
    def admitted(self) -> tuple[ItemDecision, ...]:
        return tuple(d for d in self.decisions if d.admitted())

    def reached(self, gate: Gate) -> int:
        """How many candidates were evaluated *at* this gate."""
        return sum(1 for d in self.decisions if any(r.gate is gate for r in d.records))

    def survived(self, gate: Gate) -> int:
        """How many passed it."""
        return sum(
            1
            for d in self.decisions
            for r in d.records
            if r.gate is gate and r.outcome is GateOutcome.PASSED
        )

    def survival_curve(self) -> dict[str, dict[str, float | int]]:
        out: dict[str, dict[str, float | int]] = {}
        for gate in Gate:
            reached = self.reached(gate)
            survived = self.survived(gate)
            out[str(gate)] = {
                "reached": reached,
                "survived": survived,
                "rate_of_reached": round(survived / reached, 6) if reached else 0.0,
                "rate_of_total": round(survived / self.total, 6) if self.total else 0.0,
            }
        return out

    def compiler_only_illusion(self) -> float:
        """What the retention rate *would* have been on gate 1 alone.

        Printed beside the true retention so the gap is a number in the report rather
        than a claim in a paragraph. FormalMATH's gap was ~92% against ~32%.
        """
        if not self.total:
            return 0.0
        return round(self.survived(Gate.COMPILER) / self.total, 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "governance_version": self.governance_version,
            "total_candidates": self.total,
            "admitted": len(self.admitted),
            "retention": round(len(self.admitted) / self.total, 6) if self.total else 0.0,
            "compiler_only_illusion": self.compiler_only_illusion(),
            "survival_curve": self.survival_curve(),
            "decisions": [d.to_dict() for d in self.decisions],
        }


# ---------------------------------------------------------------------------
# Gate 1
# ---------------------------------------------------------------------------


def compiler_gate(item_id: str, source: str) -> tuple[GateRecord, Any]:
    """Lex, parse, resolve, type-check. Returns the record and the module (or ``None``).

    ``compile_source(...).ok()`` is the full-pipeline verdict, not a parse verdict — wrong
    arity, a wrong role label and an unknown identifier all parse cleanly and fail later.
    For gate 1 the full verdict is the right one: an item whose reference encoding does not
    type-check has no business in a benchmark. What must never happen is the converse, and
    the whole rest of this package exists because of it: **passing here means the encoding
    is well-formed, not that it says what the specification says.**
    """
    result = compile_source(source, file=item_id)
    if result.ok():
        return (
            GateRecord(
                Gate.COMPILER,
                GateOutcome.PASSED,
                "lex, parse, resolve and type-check all accepted the reference encoding",
            ),
            result.module,
        )
    errors = "; ".join(f"{d.code}: {d.message}" for d in result.diagnostics.errors[:3])
    return (
        GateRecord(Gate.COMPILER, GateOutcome.REJECTED, f"the reference encoding fails: {errors}"),
        None,
    )


# ---------------------------------------------------------------------------
# The funnel
# ---------------------------------------------------------------------------


def run_funnel(
    candidates: Sequence[tuple[str, str]],
    *,
    semantic: Mapping[str, SemanticReport],
    panels: Mapping[str, JudgePanel],
    negations: Mapping[str, NegationOutcome],
    queue: ReviewQueue,
    promotion_critical: frozenset[str] = frozenset(),
) -> FunnelReport:
    """Run all five gates over ``(item_id, reference_source)`` pairs.

    Gates 2, 3 and 4 are supplied as pre-computed mappings rather than recomputed here.
    That keeps this function a pure sequencer — it decides *ordering and admission*, not
    *content* — and it is what lets the tests drive the funnel with a rejecting gate 2 and
    a passing gate 1 to prove the two are independent.

    An item missing from a mapping is **escalated**, not skipped and not passed. A gate
    with no result is an unrun gate, and an unrun gate that defaults to a pass is exactly
    the failure this package is built to prevent.
    """
    report = FunnelReport()
    for item_id, source in candidates:
        records: list[GateRecord] = []

        compiled, module = compiler_gate(item_id, source)
        records.append(compiled)
        if compiled.outcome is not GateOutcome.PASSED:
            report.decisions.append(ItemDecision(item_id, tuple(records)))
            continue
        del module  # gate 1's only product is a verdict; later gates carry their own.

        records.append(_semantic_record(item_id, semantic.get(item_id)))
        if records[-1].outcome is GateOutcome.REJECTED:
            report.decisions.append(ItemDecision(item_id, tuple(records)))
            continue
        semantic_escalated = records[-1].outcome is GateOutcome.ESCALATED

        records.append(_back_translation_record(item_id, panels.get(item_id)))
        if records[-1].outcome is GateOutcome.REJECTED:
            report.decisions.append(ItemDecision(item_id, tuple(records)))
            continue
        bt_escalated = records[-1].outcome is GateOutcome.ESCALATED

        records.append(_negation_record(item_id, negations.get(item_id)))
        if records[-1].outcome is GateOutcome.REJECTED:
            report.decisions.append(ItemDecision(item_id, tuple(records)))
            continue

        needs_human = (
            semantic_escalated or bt_escalated or item_id in promotion_critical
        )
        records.append(_human_record(item_id, queue, needs_human, panels.get(item_id)))
        report.decisions.append(ItemDecision(item_id, tuple(records)))
    return report


def _semantic_record(item_id: str, report: SemanticReport | None) -> GateRecord:
    if report is None:
        return GateRecord(
            Gate.DETERMINISTIC_SEMANTICS,
            GateOutcome.ESCALATED,
            "no deterministic semantic report exists for this item; an unrun gate is not a "
            "passed gate",
        )
    if report.failures:
        names = ", ".join(r.name for r in report.failures)
        return GateRecord(
            Gate.DETERMINISTIC_SEMANTICS,
            GateOutcome.REJECTED,
            f"compiler-valid but semantically wrong: {names}",
        )
    if report.inconclusive:
        names = ", ".join(r.name for r in report.inconclusive)
        return GateRecord(
            Gate.DETERMINISTIC_SEMANTICS,
            GateOutcome.ESCALATED,
            f"inconclusive checks: {names}",
        )
    return GateRecord(
        Gate.DETERMINISTIC_SEMANTICS,
        GateOutcome.PASSED,
        f"all {len(report.results)} deterministic checks pass",
    )


def _back_translation_record(item_id: str, panel: JudgePanel | None) -> GateRecord:
    if panel is None:
        return GateRecord(
            Gate.BACK_TRANSLATION,
            GateOutcome.ESCALATED,
            "no back-translation panel exists for this item",
        )
    verdict = panel.verdict()
    if verdict is Alignment.MISALIGNED:
        return GateRecord(
            Gate.BACK_TRANSLATION,
            GateOutcome.REJECTED,
            "every judge found the rendering states a different proposition from the "
            "specification",
        )
    if verdict is Alignment.INCONCLUSIVE:
        detail = (
            "judges disagreed and their decisions were preserved, not voted on: "
            + ", ".join(f"{d.judge_id}={d.alignment}" for d in panel.decisions)
            if panel.is_disputed()
            else "at least one judge returned inconclusive"
        )
        return GateRecord(Gate.BACK_TRANSLATION, GateOutcome.ESCALATED, detail)
    return GateRecord(
        Gate.BACK_TRANSLATION,
        GateOutcome.PASSED,
        f"all {len(panel.decisions)} judges independently found the rendering aligned",
    )


def _negation_record(item_id: str, outcome: NegationOutcome | None) -> GateRecord:
    if outcome is None:
        return GateRecord(
            Gate.NEGATION_ATTACK,
            GateOutcome.ESCALATED,
            "no negation attack was recorded for this item",
        )
    if isinstance(outcome, Refutation):
        return GateRecord(Gate.NEGATION_ATTACK, GateOutcome.REJECTED, outcome.reason)
    return GateRecord(
        Gate.NEGATION_ATTACK,
        GateOutcome.PASSED,
        "the negation was not proved. This is *not* evidence the candidate is correct — "
        f"the attempt carries evidential weight {outcome.evidential_weight}; it only means "
        f"no refutation was found ({outcome.attempt.verdict}, via {outcome.attempt.procedure})",
    )


def _human_record(
    item_id: str, queue: ReviewQueue, needed: bool, panel: JudgePanel | None
) -> GateRecord:
    if not needed:
        return GateRecord(
            Gate.HUMAN_REVIEW,
            GateOutcome.PASSED,
            "no trigger fired: every automated stage was conclusive and the item is not "
            "promotion-critical",
        )
    if item_id in queue.admitted_items():
        return GateRecord(
            Gate.HUMAN_REVIEW, GateOutcome.PASSED, "admitted by a named human reviewer"
        )
    if item_id in queue.rejected_items():
        return GateRecord(
            Gate.HUMAN_REVIEW, GateOutcome.REJECTED, "rejected by a named human reviewer"
        )
    request = (panel.review_request() if panel is not None else None) or ReviewRequest(
        request_id=f"funnel::{item_id}",
        trigger=ReviewTrigger.PROMOTION_SET_AMBIGUITY,
        item_id=item_id,
        question=(
            "An automated stage declined to decide, or this item is promotion-critical. "
            "Admit it to the corpus?"
        ),
        evidence={"item_id": item_id},
    )
    if request.request_id not in {r.request_id for r in queue.open_requests}:
        queue.raise_request(request)
    return GateRecord(
        Gate.HUMAN_REVIEW,
        GateOutcome.ESCALATED,
        f"blocked pending human review ({request.request_id}); the pipeline stops here "
        f"rather than resolving the question itself",
    )
