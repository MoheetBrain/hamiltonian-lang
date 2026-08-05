"""Phase 13 — the evidence package, and the promotion dry-run.

What this module is for
-----------------------
A change is promoted when someone can read one document and check, without trusting the
author, that: the failure was real and reproduced; the change fixes *that* failure and
not a neighbouring one; nothing else regressed; exactly one component moved; the data
behind it is traceable and none of it was quarantined; and there is a way back.

The package is the document. ``eligibility()`` is the checklist, evaluated in code so
that the answer does not depend on who is reading.

Three properties worth stating plainly
--------------------------------------
**The decision cannot be written by hand.** ``decision`` is a stored field — the
directive requires it — but ``__post_init__`` recomputes it from the evidence and raises
if the two disagree. A package that says ``PROMOTE_RECOMMENDED`` over failing evidence
cannot be constructed.

**A suite that did not run is not a suite that passed.** ``SuiteStatus.NOT_RUN`` blocks
promotion exactly like ``FAIL``. This is the single most common way a green report gets
written about an untested change.

**Nothing here creates a pull request.** ``emit_pr_report`` returns a string. There is
no network client, no subprocess, and no repository token anywhere in this module; a
test asserts the absence rather than the intention. Human approval is not a step this
code can perform, so it does not claim to.

Hypotheses are typed, and the exclusion is printed
--------------------------------------------------
``hypothesis`` is an ``H1``/``H2``/``H3`` member, never free text. Every rendered report
prints both what a win on that hypothesis supports and what it does not, verbatim from
``Hypothesis``. A year from now the record will say which question was being asked, and
an H3 result will not read as a result about the representation.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .memory import VerifierOutcome
from .state import (
    Hypothesis,
    Measurement,
    RollbackPlan,
    StateComponent,
    StateTransitionProposal,
    SystemState,
    Unavailable,
)

__all__ = [
    "build_evidence_package",
    "SuiteStatus",
    "SuiteResult",
    "DomainFloor",
    "VerifierEvidence",
    "FalsifierFinding",
    "TrainingDataProvenance",
    "PromotionDecision",
    "PromotionBlocker",
    "PromotionEligibility",
    "EvidencePackage",
    "EvidenceInconsistencyError",
]


class SuiteStatus(StrEnum):
    """``NOT_RUN`` is a distinct outcome and is never treated as a pass."""

    PASS = "pass"
    FAIL = "fail"
    NOT_RUN = "not_run"


@dataclass(frozen=True)
class SuiteResult:
    name: str
    status: SuiteStatus
    command: str = ""
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is SuiteStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "command": self.command,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class DomainFloor:
    """A per-domain minimum that a change must not fall below."""

    domain: str
    required: bool
    status: SuiteStatus
    value: Measurement = 0.0
    floor: float = 0.0
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is SuiteStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "required": self.required,
            "status": self.status.value,
            "value": self.value.to_dict() if isinstance(self.value, Unavailable) else self.value,
            "floor": self.floor,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class VerifierEvidence:
    verifier: str
    outcome: VerifierOutcome
    required: bool = True
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "verifier": self.verifier,
            "outcome": self.outcome.value,
            "required": self.required,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class FalsifierFinding:
    """Something that was tried in order to break the claim, and what happened."""

    probe: str
    broke_the_claim: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe": self.probe,
            "broke_the_claim": self.broke_the_claim,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class TrainingDataProvenance:
    """Where the data came from, and proof that none of it was quarantined."""

    memory_stores_used: tuple[str, ...]
    record_hashes: tuple[str, ...]
    quarantined_records_used: int
    hypothesis: Hypothesis
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, Hypothesis):
            raise TypeError("TrainingDataProvenance.hypothesis must be a Hypothesis member")
        if self.quarantined_records_used < 0:
            raise ValueError("quarantined_records_used cannot be negative")

    @property
    def complete(self) -> bool:
        return bool(self.memory_stores_used and self.record_hashes and self.description.strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_stores_used": list(self.memory_stores_used),
            "record_count": len(self.record_hashes),
            "record_hashes": list(self.record_hashes),
            "quarantined_records_used": self.quarantined_records_used,
            "hypothesis": self.hypothesis.value,
            "description": self.description,
            "complete": self.complete,
        }


class PromotionDecision(StrEnum):
    PROMOTE_RECOMMENDED = "promote_recommended"
    DO_NOT_PROMOTE = "do_not_promote"


class PromotionBlocker(StrEnum):
    INCUMBENT_FAILURE_NOT_REPRODUCED = "incumbent_failure_not_reproduced"
    CANDIDATE_TARGET_NOT_PASSED = "candidate_target_not_passed"
    TARGET_PROBE_UNIDENTIFIED = "target_probe_unidentified"
    CONSTITUTIONAL_SUITE_NOT_PASSED = "constitutional_suite_not_passed"
    RETENTION_SUITE_NOT_PASSED = "retention_suite_not_passed"
    DOMAIN_FLOOR_NOT_MET = "domain_floor_not_met"
    NOT_EXACTLY_ONE_COMPONENT = "not_exactly_one_component"
    PROVENANCE_INCOMPLETE = "provenance_incomplete"
    QUARANTINED_DATA_USED = "quarantined_data_used"
    ROLLBACK_UNDEFINED = "rollback_undefined"
    REQUIRED_VERIFIER_UNSATISFIED = "required_verifier_unsatisfied"
    HYPOTHESIS_MISMATCH = "hypothesis_mismatch"


@dataclass(frozen=True)
class PromotionEligibility:
    eligible: bool
    blockers: tuple[tuple[PromotionBlocker, str], ...]

    def codes(self) -> tuple[PromotionBlocker, ...]:
        return tuple(code for code, _ in self.blockers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "blockers": [{"code": c.value, "detail": d} for c, d in self.blockers],
        }


class EvidenceInconsistencyError(ValueError):
    """Raised when a package's stated decision does not follow from its own evidence."""


@dataclass(frozen=True)
class EvidencePackage:
    """One change, all of its evidence, and the decision that evidence supports."""

    experiment_id: str
    incumbent_state: SystemState
    candidate_state: SystemState
    changed_component: StateComponent
    trigger_episode: str
    hypothesis: Hypothesis
    hypothesis_rationale: str

    incumbent_failure_reproduced: bool
    candidate_target_passed: bool
    target_probe_id: str

    constitutional_suite_result: SuiteResult
    retention_suite_result: SuiteResult
    domain_floor_results: tuple[DomainFloor, ...]

    semantic_fidelity: Measurement
    repair_success: Measurement
    token_cost: Measurement
    latency: Measurement

    verifier_evidence: tuple[VerifierEvidence, ...]
    falsifier_findings: tuple[FalsifierFinding, ...]
    unresolved_limitations: tuple[str, ...]

    training_data_provenance: TrainingDataProvenance
    rollback_state: SystemState | None
    rollback_procedure: str

    decision: PromotionDecision
    requires_human_approval: bool = True
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, Hypothesis):
            raise TypeError(
                "EvidencePackage.hypothesis must be an H1/H2/H3 member, not "
                f"{type(self.hypothesis).__name__}. Free text cannot be separated a year "
                "later, and separating them is the point."
            )
        if not isinstance(self.changed_component, StateComponent):
            raise TypeError("EvidencePackage.changed_component must be a StateComponent member")
        if not self.requires_human_approval:
            raise EvidenceInconsistencyError(
                "human approval is mandatory and cannot be waived by a field"
            )
        computed = self.compute_decision()
        if self.decision is not computed:
            raise EvidenceInconsistencyError(
                f"package states {self.decision.value} but its own evidence supports "
                f"{computed.value}. Blockers: "
                f"{[c.value for c in self.eligibility().codes()]}"
            )

    # -- evaluation --------------------------------------------------------

    def transition_proposal(self) -> StateTransitionProposal:
        """The state transition implied by this package, for the ``|dS|_0 = 1`` check."""
        rollback = RollbackPlan(
            target_state=self.rollback_state or self.incumbent_state,
            procedure=self.rollback_procedure or "(none stated)",
        )
        return StateTransitionProposal(
            proposal_id=self.experiment_id,
            incumbent=self.incumbent_state,
            candidate=self.candidate_state,
            declared_component=self.changed_component,
            hypothesis=self.hypothesis,
            hypothesis_rationale=self.hypothesis_rationale or "(none stated)",
            trigger_episode_id=self.trigger_episode or "",
            rollback=rollback,
        )

    def eligibility(self) -> PromotionEligibility:
        blockers: list[tuple[PromotionBlocker, str]] = []

        if not self.incumbent_failure_reproduced:
            blockers.append(
                (
                    PromotionBlocker.INCUMBENT_FAILURE_NOT_REPRODUCED,
                    "the incumbent failure was not reproduced, so there is no demonstrated "
                    "defect for this change to be the fix for",
                )
            )
        if not self.candidate_target_passed:
            blockers.append(
                (
                    PromotionBlocker.CANDIDATE_TARGET_NOT_PASSED,
                    "the candidate does not pass the target probe",
                )
            )
        if not self.target_probe_id.strip():
            blockers.append(
                (
                    PromotionBlocker.TARGET_PROBE_UNIDENTIFIED,
                    "no target probe is named, so 'the same probe' cannot be checked",
                )
            )
        if not self.constitutional_suite_result.ok:
            blockers.append(
                (
                    PromotionBlocker.CONSTITUTIONAL_SUITE_NOT_PASSED,
                    f"constitutional suite: {self.constitutional_suite_result.status.value}"
                    + (
                        " (a suite that did not run has not passed)"
                        if self.constitutional_suite_result.status is SuiteStatus.NOT_RUN
                        else ""
                    ),
                )
            )
        if not self.retention_suite_result.ok:
            blockers.append(
                (
                    PromotionBlocker.RETENTION_SUITE_NOT_PASSED,
                    f"retention suite: {self.retention_suite_result.status.value}"
                    + (
                        " (a suite that did not run has not passed)"
                        if self.retention_suite_result.status is SuiteStatus.NOT_RUN
                        else ""
                    ),
                )
            )
        for floor in self.domain_floor_results:
            if floor.required and not floor.ok:
                blockers.append(
                    (
                        PromotionBlocker.DOMAIN_FLOOR_NOT_MET,
                        f"required domain floor {floor.domain!r}: {floor.status.value}",
                    )
                )
        verdict = self.transition_proposal().validate()
        if not verdict.ok:
            blockers.append(
                (
                    PromotionBlocker.NOT_EXACTLY_ONE_COMPONENT,
                    "the state transition is not a single declared component change: "
                    + "; ".join(f"{c.value} ({d})" for c, d in verdict.rejections),
                )
            )
        if not self.training_data_provenance.complete:
            blockers.append(
                (
                    PromotionBlocker.PROVENANCE_INCOMPLETE,
                    "training-data provenance is incomplete: stores, record hashes and a "
                    "description are all required",
                )
            )
        if self.training_data_provenance.quarantined_records_used:
            blockers.append(
                (
                    PromotionBlocker.QUARANTINED_DATA_USED,
                    f"{self.training_data_provenance.quarantined_records_used} quarantined "
                    "record(s) were used; quarantined data is never training-eligible",
                )
            )
        if self.training_data_provenance.hypothesis is not self.hypothesis:
            blockers.append(
                (
                    PromotionBlocker.HYPOTHESIS_MISMATCH,
                    f"the package is about {self.hypothesis.name} and its data was drawn "
                    f"under {self.training_data_provenance.hypothesis.name}",
                )
            )
        if self.rollback_state is None or not self.rollback_procedure.strip():
            blockers.append(
                (
                    PromotionBlocker.ROLLBACK_UNDEFINED,
                    "no rollback state or no rollback procedure is recorded",
                )
            )
        for ev in self.verifier_evidence:
            if ev.required and ev.outcome is not VerifierOutcome.PASS:
                blockers.append(
                    (
                        PromotionBlocker.REQUIRED_VERIFIER_UNSATISFIED,
                        f"required verifier {ev.verifier!r} reported {ev.outcome.value}",
                    )
                )
        if not self.verifier_evidence:
            blockers.append(
                (
                    PromotionBlocker.REQUIRED_VERIFIER_UNSATISFIED,
                    "no verifier evidence at all; nothing checked the candidate",
                )
            )

        return PromotionEligibility(not blockers, tuple(blockers))

    def compute_decision(self) -> PromotionDecision:
        return (
            PromotionDecision.PROMOTE_RECOMMENDED
            if self.eligibility().eligible
            else PromotionDecision.DO_NOT_PROMOTE
        )

    # -- emission ----------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "hypothesis": {
                "id": self.hypothesis.value,
                "name": self.hypothesis.name,
                "supports": self.hypothesis.claim,
                "does_not_support": self.hypothesis.excluded_claim,
                "rationale": self.hypothesis_rationale,
            },
            "incumbent_state": self.incumbent_state.to_dict(),
            "incumbent_state_fingerprint": self.incumbent_state.fingerprint(),
            "candidate_state": self.candidate_state.to_dict(),
            "candidate_state_fingerprint": self.candidate_state.fingerprint(),
            "changed_component": self.changed_component.value,
            "trigger_episode": self.trigger_episode,
            "target_probe_id": self.target_probe_id,
            "incumbent_failure_reproduced": self.incumbent_failure_reproduced,
            "candidate_target_passed": self.candidate_target_passed,
            "constitutional_suite_result": self.constitutional_suite_result.to_dict(),
            "retention_suite_result": self.retention_suite_result.to_dict(),
            "domain_floor_results": [d.to_dict() for d in self.domain_floor_results],
            "metrics": {
                "semantic_fidelity": _num(self.semantic_fidelity),
                "repair_success": _num(self.repair_success),
                "token_cost": _num(self.token_cost),
                "latency": _num(self.latency),
            },
            "verifier_evidence": [v.to_dict() for v in self.verifier_evidence],
            "falsifier_findings": [f.to_dict() for f in self.falsifier_findings],
            "unresolved_limitations": list(self.unresolved_limitations),
            "training_data_provenance": self.training_data_provenance.to_dict(),
            "rollback": {
                "state": self.rollback_state.to_dict() if self.rollback_state else None,
                "procedure": self.rollback_procedure,
            },
            "state_transition_verdict": self.transition_proposal().validate().to_dict(),
            "eligibility": self.eligibility().to_dict(),
            "decision": self.decision.value,
            "requires_human_approval": self.requires_human_approval,
            "notes": list(self.notes),
        }

    def emit_json(self, indent: int = 2) -> str:
        """Machine-readable. Deterministic key order so two runs diff cleanly."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, ensure_ascii=True)

    def emit_markdown(self) -> str:
        e = self.eligibility()
        lines: list[str] = [
            f"# Evidence package — {self.experiment_id}",
            "",
            f"**Decision: {self.decision.value.replace('_', ' ').upper()}** — "
            "human approval is mandatory and this document does not grant it.",
            "",
            "## Hypothesis",
            "",
            f"- **{self.hypothesis.name}** (`{self.hypothesis.value}`)",
            f"- Supports: {self.hypothesis.claim}",
            f"- Does **not** support: {self.hypothesis.excluded_claim}",
            f"- Rationale: {self.hypothesis_rationale or '(none stated)'}",
            "",
            "## Change",
            "",
            f"- Changed component: `{self.changed_component.value}`",
            f"- Incumbent fingerprint: `{self.incumbent_state.fingerprint()[:16]}`",
            f"- Candidate fingerprint: `{self.candidate_state.fingerprint()[:16]}`",
            f"- Trigger episode: `{self.trigger_episode or '(none)'}`",
            f"- Target probe: `{self.target_probe_id or '(none)'}`",
            "",
            "## Reproduction",
            "",
            f"- Incumbent failure reproduced: {_yn(self.incumbent_failure_reproduced)}",
            f"- Candidate passes the same probe: {_yn(self.candidate_target_passed)}",
            "",
            "## Suites",
            "",
            "| suite | status | passed | failed | skipped | command |",
            "|---|---|---|---|---|---|",
            _suite_row(self.constitutional_suite_result),
            _suite_row(self.retention_suite_result),
            "",
            "## Domain floors",
            "",
            "| domain | required | status | value | floor |",
            "|---|---|---|---|---|",
        ]
        for d in self.domain_floor_results or ():
            lines.append(
                f"| {d.domain} | {_yn(d.required)} | {d.status.value} | "
                f"{_show(d.value)} | {d.floor} |"
            )
        if not self.domain_floor_results:
            lines.append("| (none recorded) | — | — | — | — |")
        lines += [
            "",
            "## Measurements",
            "",
            "| quantity | value |",
            "|---|---|",
            f"| semantic fidelity | {_show(self.semantic_fidelity)} |",
            f"| repair success | {_show(self.repair_success)} |",
            f"| token cost | {_show(self.token_cost)} |",
            f"| latency | {_show(self.latency)} |",
            "",
            "## Verifiers",
            "",
            "| verifier | required | outcome | detail |",
            "|---|---|---|---|",
        ]
        for v in self.verifier_evidence or ():
            lines.append(
                f"| {v.verifier} | {_yn(v.required)} | {v.outcome.value} | {v.detail or '—'} |"
            )
        if not self.verifier_evidence:
            lines.append("| (none) | — | — | nothing checked the candidate |")
        lines += ["", "## Falsifier findings", ""]
        if self.falsifier_findings:
            for f in self.falsifier_findings:
                mark = "BROKE THE CLAIM" if f.broke_the_claim else "did not break the claim"
                lines.append(f"- `{f.probe}` — {mark}. {f.detail}".rstrip())
        else:
            lines.append("- None recorded. Nothing was tried against this claim.")
        lines += ["", "## Unresolved limitations", ""]
        if self.unresolved_limitations:
            lines.extend(f"- {item}" for item in self.unresolved_limitations)
        else:
            lines.append("- None recorded.")
        lines += [
            "",
            "## Training data provenance",
            "",
            f"- Stores: {', '.join(self.training_data_provenance.memory_stores_used) or '(none)'}",
            f"- Records: {len(self.training_data_provenance.record_hashes)}",
            f"- Quarantined records used: "
            f"{self.training_data_provenance.quarantined_records_used}",
            f"- Drawn under: {self.training_data_provenance.hypothesis.name}",
            f"- Complete: {_yn(self.training_data_provenance.complete)}",
            "",
            "## Rollback",
            "",
            f"- Target state recorded: {_yn(self.rollback_state is not None)}",
            f"- Procedure: {self.rollback_procedure or '(none stated)'}",
            "",
            "## Eligibility",
            "",
        ]
        if e.eligible:
            lines.append("- Every promotion condition is met. A human must still approve.")
        else:
            lines.extend(f"- **{code.value}** — {detail}" for code, detail in e.blockers)
        return "\n".join(lines) + "\n"

    def emit_pr_report(self) -> str:
        """A pull-request-shaped summary. **No pull request is created by this code.**"""
        e = self.eligibility()
        title = (
            f"[dry run] {self.changed_component.value}: {self.experiment_id} "
            f"({self.decision.value})"
        )
        body = [
            f"### {title}",
            "",
            "> This is a dry run. No pull request was created, none was pushed, and this "
            "> function has no network access. Promotion requires a human.",
            "",
            f"**Hypothesis {self.hypothesis.name}** — {self.hypothesis.claim}",
            "",
            f"**Scope of this result.** {self.hypothesis.excluded_claim}",
            "",
            "**What changed**",
            "",
            f"- exactly one component: `{self.changed_component.value}`",
            f"- `{self.incumbent_state.version_of(self.changed_component)}` -> "
            f"`{self.candidate_state.version_of(self.changed_component)}`",
            "",
            "**Why**",
            "",
            f"- trigger episode `{self.trigger_episode or '(none)'}`, target probe "
            f"`{self.target_probe_id or '(none)'}`",
            f"- incumbent failure reproduced: {_yn(self.incumbent_failure_reproduced)}",
            f"- candidate passes the same probe: {_yn(self.candidate_target_passed)}",
            "",
            "**Checks**",
            "",
            f"- constitutional suite: `{self.constitutional_suite_result.status.value}`",
            f"- retention suite: `{self.retention_suite_result.status.value}`",
            f"- required verifiers: "
            f"{_verifier_summary(self.verifier_evidence)}",
            f"- quarantined training data used: "
            f"{self.training_data_provenance.quarantined_records_used}",
            "",
            "**Decision**",
            "",
        ]
        if e.eligible:
            body.append("- Eligible for promotion. Awaiting human approval.")
        else:
            body.append("- Not eligible. Blocking:")
            body.extend(f"  - `{code.value}` {detail}" for code, detail in e.blockers)
        body += [
            "",
            "**Unresolved limitations**",
            "",
        ]
        body.extend(
            f"- {item}" for item in (self.unresolved_limitations or ("None recorded.",))
        )
        body += ["", f"**Rollback** — {self.rollback_procedure or '(none stated)'}", ""]
        return "\n".join(body)


def _num(value: Measurement) -> Any:
    return value.to_dict() if isinstance(value, Unavailable) else value


def _show(value: Measurement) -> str:
    return f"UNAVAILABLE ({value.reason})" if isinstance(value, Unavailable) else str(value)


def _yn(flag: bool) -> str:
    return "yes" if flag else "no"


def _suite_row(s: SuiteResult) -> str:
    return (
        f"| {s.name} | {s.status.value} | {s.passed} | {s.failed} | {s.skipped} | "
        f"`{s.command or '—'}` |"
    )


def _verifier_summary(evidence: Sequence[VerifierEvidence]) -> str:
    required = [v for v in evidence if v.required]
    if not required:
        return "none declared"
    passed = sum(1 for v in required if v.outcome is VerifierOutcome.PASS)
    return f"{passed}/{len(required)} passed"


def build_evidence_package(**evidence: Any) -> EvidencePackage:
    """Construct a package with ``decision`` derived rather than asserted.

    The stored field still exists and is still validated by ``__post_init__``; this
    helper removes the opportunity to get it wrong by hand. Both branches below go
    through the same validation, so neither can produce a package whose decision does
    not follow from its evidence.
    """
    if "decision" in evidence:
        raise TypeError(
            "decision is derived from the evidence; pass the evidence and let the "
            "package compute it"
        )
    try:
        return EvidencePackage(decision=PromotionDecision.DO_NOT_PROMOTE, **evidence)
    except EvidenceInconsistencyError:
        return EvidencePackage(decision=PromotionDecision.PROMOTE_RECOMMENDED, **evidence)
