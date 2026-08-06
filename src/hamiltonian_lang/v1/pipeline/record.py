"""The structured result record, and the compact summary a human reads.

Two outputs, one source of truth
--------------------------------
:class:`SolveRecord` is the record. :func:`render_summary` is a *projection* of it — it
computes nothing the record does not already contain, so the terminal and the JSON can
never disagree.

No hidden truncation
--------------------
The JSON record is never shortened. The terminal summary is width-limited, and every
place it shortens something says so and gives the exact number of omitted characters
(:func:`clip`). A summary that quietly drops the tail of a diagnostic is how a reader
concludes a run was clean when it was not.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "RECORD_SCHEMA_VERSION",
    "StepStatus",
    "StepRecord",
    "AttemptRecord",
    "AnswerRecord",
    "SolveRecord",
    "clip",
    "render_summary",
]

RECORD_SCHEMA_VERSION = "hml-v1-solve-record-1.0.0"


class StepStatus:
    """Pipeline-step verdicts. ``SKIPPED`` is never a failure and never a pass."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class StepRecord:
    """One named step of the pipeline, with what it actually did."""

    name: str
    status: str
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "data": self.data,
        }


@dataclass(frozen=True)
class AttemptRecord:
    """One compile-and-verify pass over one candidate encoding.

    There are at most two: the draft and, if the draft failed and a plan was produced,
    the single repaired attempt.
    """

    label: str
    model_call: str
    raw_model_text: str
    extracted_surface: str | None
    hml_l1: str | None
    #: ``StageOutcome.to_dict()``. ``None`` only when nothing was extracted to compile.
    stages: dict[str, Any] | None
    #: ``VerificationOutcome.to_dict()`` from the obligation engine, or ``None`` when the
    #: candidate never compiled and so had no obligations to discharge.
    obligations: dict[str, Any] | None
    federation_verdict: str
    federation_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "model_call": self.model_call,
            "raw_model_text": self.raw_model_text,
            "extracted_surface": self.extracted_surface,
            "hml_l1": self.hml_l1,
            "stages": self.stages,
            "obligations": self.obligations,
            "federation_verdict": self.federation_verdict,
            "federation_results": self.federation_results,
        }


@dataclass(frozen=True)
class AnswerRecord:
    """The answer, its basis, and whether it matched the withheld key.

    ``value is None`` with ``kind == "NOT_EXTRACTED"`` is a real outcome and is recorded
    as one. Nothing here ever fabricates a value to fill the field.
    """

    kind: str
    value: str | None
    basis: str
    #: ``True``/``False`` once compared against the key, ``None`` when never compared.
    matches_key: bool | None = None
    key_comparison: str = "not compared"
    normalised: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "basis": self.basis,
            "matches_key": self.matches_key,
            "key_comparison": self.key_comparison,
            "normalised": self.normalised,
        }


@dataclass(frozen=True)
class SolveRecord:
    """The complete, replayable account of one ``solve`` invocation."""

    problem: dict[str, Any]
    config: dict[str, Any]
    steps: tuple[StepRecord, ...]
    attempts: tuple[AttemptRecord, ...]
    answer: AnswerRecord
    final_verdict: str
    terminal: str
    repair_used: bool
    repair: dict[str, Any] | None = None
    first_failure: dict[str, Any] | None = None
    model_calls: tuple[dict[str, Any], ...] = ()
    errors: tuple[str, ...] = ()
    schema_version: str = RECORD_SCHEMA_VERSION
    #: Always present, and always ``False`` for the JSON. Recorded rather than assumed so
    #: a reader does not have to trust a docstring.
    json_truncated: bool = False

    def stages_reached(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.steps if s.status == StepStatus.PASS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "problem": self.problem,
            "config": self.config,
            "steps": [s.to_dict() for s in self.steps],
            "attempts": [a.to_dict() for a in self.attempts],
            "first_failure": self.first_failure,
            "repair_used": self.repair_used,
            "repair": self.repair,
            "answer": self.answer.to_dict(),
            "final_verdict": self.final_verdict,
            "terminal": self.terminal,
            "model_calls": list(self.model_calls),
            "errors": list(self.errors),
            "json_truncated": self.json_truncated,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# The human-readable summary
# ---------------------------------------------------------------------------


def clip(text: str, limit: int) -> str:
    """Shorten for display, stating exactly how much was omitted.

    ``limit <= 0`` disables clipping entirely. The elision marker is not decoration: it
    is the difference between a summary and a misleading one.
    """
    text = text or ""
    if limit <= 0 or len(text) <= limit:
        return text
    omitted = len(text) - limit
    return (
        f"{text[:limit]}\n[... {omitted} characters omitted from this terminal summary; "
        "the JSON record carries the full text ...]"
    )


_TICK = {
    StepStatus.PASS: "ok  ",
    StepStatus.FAIL: "FAIL",
    StepStatus.SKIPPED: "skip",
    StepStatus.NOT_APPLICABLE: "n/a ",
}


def render_summary(record: SolveRecord, *, max_chars: int = 1200) -> str:
    """The compact terminal view. A projection of the record; it derives nothing new."""
    problem = record.problem
    lines = [
        f"problem : {problem.get('problem_id')}  ({problem.get('domain')})",
        f"surface : {record.config.get('surface')}"
        f"   model: {record.config.get('model')}"
        f"   repair budget: {record.config.get('repair_limit')}",
        "",
        "pipeline:",
    ]
    for step in record.steps:
        mark = _TICK.get(step.status, step.status)
        lines.append(f"  [{mark}] {step.name:<14} {clip(step.detail, 90)}")

    if record.first_failure:
        lines += ["", "first failure:"]
        ff = record.first_failure
        lines.append(f"  {ff.get('code')} at {ff.get('where')}: {clip(str(ff.get('message', '')), 100)}")
        prefix_lines = ff.get("verified_prefix_lines")
        if prefix_lines is not None:
            lines.append(f"  verified prefix: {prefix_lines} line(s) before the defect")

    if record.repair:
        lines += ["", "repair (one, bounded):"]
        lines.append(f"  plan      : {record.repair.get('plan_kind')}")
        lines.append(f"  error class: {record.repair.get('error_class')}")
        lines.append(f"  cause     : {clip(str(record.repair.get('cause', '')), 110)}")
        lines.append(f"  outcome   : {record.repair.get('outcome')}")

    answer = record.answer
    match = {True: "matches the key", False: "DOES NOT match the key", None: "not compared"}[
        answer.matches_key
    ]
    lines += [
        "",
        f"answer  : {answer.value if answer.value is not None else '(none extracted)'}"
        f"   [{answer.kind}]",
        f"          basis: {clip(answer.basis, 110)}",
        f"          key  : {match}",
        "",
        f"verdict : {record.final_verdict}   (terminal: {record.terminal})",
    ]
    if record.errors:
        lines += ["", "errors:"]
        lines += [f"  - {clip(e, 140)}" for e in record.errors]
    return clip("\n".join(lines), 0 if max_chars <= 0 else max(max_chars, 400))
