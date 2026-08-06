"""Executing the 16-condition ACQ0 protocol calibration. One phase, one authorisation.

Everything a condition produced is written to disk before the next condition starts: raw
task, raw prompt, raw draft, **raw formal attempt zero**, per-stage compiler outcomes, raw
diagnostic, raw repair, ``prompt_eval_count``, ``eval_count``, latency, emptiness,
truncation and transport retries. A run that crashes at condition 11 therefore still has
ten complete records rather than none.

Two rules this module will not break
------------------------------------
* **A transport retry never erases the original failed call.** Every attempt is appended to
  ``transport_attempts``; the retry is an additional record, not a replacement.
* **An empty visible answer is never retried.** It is the outcome the paper predicts and
  retrying it until text appears deletes the measurement.

``num_ctx`` is sent on every call and held **constant** at the frozen rung. Changing it
between calls forces a 24 GB reload; that is what produced five 120 s timeouts in the
budget probe.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evaluation.syntax_gate.candidates import (
    CANDIDATES,
    extract_fenced,
    resolve_adapters,
)

from hamiltonian_lang.improvement.episodes import (
    StageStatus,
)

from .core import PROTOCOL_STAGES, GenerationProtocol, StageKind
from .encoding import acq0_encoding_prompt, assert_mathematics_fixed_independently
from .ledger import (
    FROZEN_RUNTIME,
    PROTOCOL_TOKEN_SPLIT,
    REPAIR_MAX_TOKENS,
    derive_call_ledger,
)
from .oracle import ACQ0_ANSWER_FACET_VOID
from .runner import AuthorisedSession

__all__ = [
    "OllamaBackend",
    "RESULTS_DIR",
    "TERMINAL_STATUSES",
    "ConditionRecord",
    "execute_phase",
]

RESULTS_DIR = Path("evaluation/results/acq0/protocol_calibration_v2")

#: The v1 run. Retained, never overwritten: it is valid evidence of a budget failure.
V1_RESULTS_DIR = Path("evaluation/results/acq0/protocol_calibration")

#: Exactly one **earliest** terminal status per attempt. Ordered; the first that applies
#: wins. FORMAT_FAILED precedes PARSE_FAILED because a reply with no fenced block was
#: never handed to the parser.
TERMINAL_STATUSES: tuple[str, ...] = (
    "FORMAT_FAILED",
    "PARSE_FAILED",
    "RESOLUTION_FAILED",
    "TYPE_FAILED",
    "SEMANTIC_LOSS",
    "OBLIGATION_FAILED",
    "VERIFIED",
    "INCONCLUSIVE",
    "UNSUPPORTED",
)


class OllamaBackend:
    """``POST /api/chat`` at temperature 0, ``num_ctx`` pinned to the frozen rung."""

    LIVE = True

    def __init__(
        self,
        *,
        model: str = str(FROZEN_RUNTIME["model"]),
        url: str = "http://localhost:11434",
        num_ctx: int = int(FROZEN_RUNTIME["num_ctx"]),
        timeout_s: float = float(FROZEN_RUNTIME["timeout_s"]),
    ) -> None:
        self.model = model
        self.url = url.rstrip("/")
        self.num_ctx = num_ctx
        self.timeout_s = timeout_s
        self.num_predict = 0

    def generate(self, system: str, user: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": 0.0,
                # Constant across every call in the phase. See the module docstring.
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }
        req = urllib.request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                body = json.loads(r.read().decode())
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            return {
                "content": "",
                "prompt_tokens": None,
                "completion_tokens": None,
                "latency_s": time.perf_counter() - start,
                "finish_reason": "",
                "error": f"{type(exc).__name__}: {exc}",
            }
        elapsed = time.perf_counter() - start
        return {
            "content": (body.get("message") or {}).get("content", "") or "",
            "reasoning": (body.get("message") or {}).get("thinking", "") or "",
            "prompt_tokens": body.get("prompt_eval_count"),
            "completion_tokens": body.get("eval_count"),
            "latency_s": elapsed,
            "finish_reason": body.get("done_reason", "") or "",
            "error": None,
        }


def _earliest_terminal(
    *,
    adherent: bool,
    supported: bool,
    outcome: Any,
    transport_error: bool,
    expected_hash: str | None = None,
) -> str:
    """One status, the earliest that applies. Never derived from ``CompileResult.ok()``.

    Wrong arity, wrong role, declared-type mismatch and epistemic mismatch all parse and
    resolve cleanly and fail only in the type checker; an unknown identifier fails at
    resolution. Reading a single pipeline boolean here would attribute every one of those
    to the parser.
    """
    if transport_error:
        return "INCONCLUSIVE"
    if not supported:
        return "UNSUPPORTED"
    if not adherent:
        return "FORMAT_FAILED"
    if outcome is None:
        return "INCONCLUSIVE"
    if outcome.parse_status is StageStatus.FAIL:
        return "PARSE_FAILED"
    if outcome.resolution_status is StageStatus.FAIL:
        return "RESOLUTION_FAILED"
    if outcome.type_status is StageStatus.FAIL:
        return "TYPE_FAILED"
    if outcome.semantic_status is StageStatus.FAIL:
        return "SEMANTIC_LOSS"
    # ``SyntaxAdapter.parse`` classifies without an expected object, so ``semantic_status``
    # comes back NOT_RUN even on a clean parse. Falling through to INCONCLUSIVE there would
    # silently report every well-formed encoding as unmeasured and no arm would ever record
    # a semantic result. The comparison is therefore done here, against the reference hash
    # fixed in the corpus before execution.
    if expected_hash is not None:
        produced = getattr(outcome, "canonical_hash", None)
        if produced is None:
            return "INCONCLUSIVE"
        if produced != expected_hash:
            return "SEMANTIC_LOSS"
        if outcome.verification_status is StageStatus.FAIL or getattr(
            outcome, "unresolved_obligations", ()
        ):
            return "OBLIGATION_FAILED"
        return "VERIFIED"
    # ``TerminalOutcome`` has no OBLIGATION_FAILED member; the obligation stage is carried
    # by ``verification_status`` and ``unresolved_obligations``. Reading it from those two
    # rather than inventing an enum member keeps this classifier downstream of the
    # compiler's own record.
    if outcome.verification_status is StageStatus.FAIL or getattr(
        outcome, "unresolved_obligations", ()
    ):
        return "OBLIGATION_FAILED"
    if outcome.semantic_status is StageStatus.PASS:
        # Exact canonical-hash recovery. ACQ0's success criterion is preservation, so
        # SEMANTICALLY_PRESERVED and VERIFIED both land here; the compiler's own terminal
        # is preserved verbatim in the record alongside this status.
        return "VERIFIED"
    return "INCONCLUSIVE"


@dataclass
class ConditionRecord:
    """Everything one condition produced. Written verbatim, once, before the next starts."""

    condition: str
    task_id: str
    domain: str
    protocol: str
    stages: list[dict[str, Any]] = field(default_factory=list)
    formal_attempt_zero: str = ""
    draft: str = ""
    repair: str = ""
    diagnostic: str = ""
    terminal: str = ""
    repair_terminal: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition,
            "task_id": self.task_id,
            "domain": self.domain,
            "protocol": self.protocol,
            "stages": self.stages,
            "raw_formal_attempt_zero": self.formal_attempt_zero,
            "raw_draft": self.draft,
            "raw_repair": self.repair,
            "raw_diagnostic": self.diagnostic,
            "terminal": self.terminal,
            "repair_terminal": self.repair_terminal,
            "notes": self.notes,
            "answer_facet": ACQ0_ANSWER_FACET_VOID,
        }


def _call_with_transport_retries(
    backend: Any,
    system: str,
    user: str,
    *,
    session: AuthorisedSession | None,
    what: str,
    retries: int = 1,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Every attempt preserved. The retry is an extra record, never a replacement."""
    attempts: list[dict[str, Any]] = []
    gen: dict[str, Any] = {}
    for attempt in range(retries + 1):
        if getattr(backend, "LIVE", False) and session is not None:
            session.charge(f"{what}#attempt{attempt}")
        gen = backend.generate(system, user)
        attempts.append(
            {
                "attempt": attempt,
                "error": gen.get("error"),
                "prompt_eval_count": gen.get("prompt_tokens"),
                "eval_count": gen.get("completion_tokens"),
                "latency_s": gen.get("latency_s"),
                "finish_reason": gen.get("finish_reason"),
                "content_characters": len(gen.get("content") or ""),
            }
        )
        if not gen.get("error"):
            break
        # An empty completion is NOT an error and never reaches here: only transport does.
    return gen, attempts


def _stage_record(
    stage: StageKind, prompt: Any, gen: dict[str, Any], attempts: list[dict[str, Any]]
) -> dict[str, Any]:
    completion = gen.get("completion_tokens")
    allowance = _allowance_for(prompt.protocol, stage)
    return {
        "stage": str(stage),
        "system": prompt.system,
        "user": prompt.user,
        "content": gen.get("content", ""),
        # Persisted rather than dropped. In v1, 27 of 38 calls returned an empty visible
        # answer with finish_reason="length": the model spent its whole allowance on
        # reasoning tokens, which this provider routes to ``message.thinking``. Dropping
        # the field made that failure undiagnosable from the record.
        "reasoning": gen.get("reasoning", ""),
        "reasoning_characters": len(gen.get("reasoning") or ""),
        "prompt_eval_count": gen.get("prompt_tokens"),
        "eval_count": completion,
        "latency_s": gen.get("latency_s"),
        "finish_reason": gen.get("finish_reason"),
        "empty_output": not (gen.get("content") or "").strip() and not gen.get("error"),
        "truncated": bool(completion is not None and allowance and completion >= allowance),
        "num_predict": allowance,
        "transport_attempts": attempts,
        "transport_retried": len(attempts) > 1,
        "error": gen.get("error"),
    }


def _allowance_for(protocol: GenerationProtocol, stage: StageKind) -> int:
    split = PROTOCOL_TOKEN_SPLIT[protocol]
    if stage is StageKind.FORMALISE:
        return int(split["formalise"])
    return int(split.get("draft", 0))


def execute_phase(
    *,
    backend: Any,
    session: AuthorisedSession | None,
    tasks: Sequence[Any],
    demonstrations: Sequence[Any],
    conditions: Sequence[str],
    protocols: Sequence[GenerationProtocol],
    out_dir: Path = RESULTS_DIR,
) -> list[ConditionRecord]:
    """Run every cell, writing each record to disk as soon as it is complete."""
    from evaluation.acq0.prompts.stages import build_stage_prompt
    from evaluation.syntax_gate.scorer import _reference_canonical_hash

    assert_mathematics_fixed_independently(tasks)
    out_dir.mkdir(parents=True, exist_ok=True)
    adapters = resolve_adapters()
    records: list[ConditionRecord] = []

    for protocol in protocols:
        for condition in conditions:
            for task in tasks:
                rec = ConditionRecord(
                    condition=condition,
                    task_id=task.id,
                    domain=task.domain,
                    protocol=str(protocol),
                )
                upstream = ""
                transport_error = False
                for stage in PROTOCOL_STAGES[protocol]:
                    kw: dict[str, Any] = {}
                    if stage is StageKind.FORMALISE:
                        kw["demonstrations"] = list(demonstrations)
                        kw["adapters"] = adapters
                        if len(PROTOCOL_STAGES[protocol]) > 1:
                            kw["upstream"] = upstream or "(the draft stage produced no text)"
                    base = build_stage_prompt(task, condition, protocol, stage, **kw)
                    prompt = acq0_encoding_prompt(base, task)
                    backend.num_predict = _allowance_for(protocol, stage)
                    gen, attempts = _call_with_transport_retries(
                        backend,
                        prompt.system,
                        prompt.user,
                        session=session,
                        what=f"{protocol}/{stage}/{condition}/{task.id}",
                    )
                    rec.stages.append(_stage_record(stage, prompt, gen, attempts))
                    if gen.get("error"):
                        transport_error = True
                    if stage is StageKind.FORMALISE:
                        rec.formal_attempt_zero = gen.get("content", "")
                    else:
                        rec.draft = gen.get("content", "")
                        upstream = gen.get("content", "")

                # -- scoring, per stage, never from a single boolean ------------
                tags = CANDIDATES[condition].fence_tags if condition in CANDIDATES else ()
                adapter = adapters.get(condition)
                reply = rec.formal_attempt_zero
                adherent = bool(tags) and extract_fenced(reply, tags) is not None
                encoding = extract_fenced(reply, tags) if tags else None
                expected = _reference_canonical_hash(task.cso.reference_hml)
                outcome = None
                if adapter is not None and encoding:
                    parsed = adapter.parse(encoding)
                    outcome = getattr(parsed, "stages", None)
                rec.terminal = _earliest_terminal(
                    adherent=adherent,
                    supported=adapter is not None,
                    outcome=outcome,
                    transport_error=transport_error,
                    expected_hash=expected,
                )
                if outcome is not None:
                    rec.diagnostic = "; ".join(getattr(outcome, "diagnostic_codes", ()) or ())
                    rec.notes.append(
                        f"expected_canonical_hash={expected}; "
                        f"produced={getattr(outcome, 'canonical_hash', None)}"
                    )

                # -- repair: only after an eligible formal attempt FAILED -------
                if rec.terminal not in ("VERIFIED", "UNSUPPORTED", "INCONCLUSIVE"):
                    diag = (
                        rec.diagnostic or "the reply did not contain the expected fenced block"
                    )
                    repair_user = (
                        f"{prompt.user}\n\nYOUR PREVIOUS ATTEMPT\n{reply}\n\n"
                        f"COMPILER DIAGNOSTIC\n{diag}\n\n"
                        "Correct the encoding. Change nothing the diagnostic did not name."
                    )
                    backend.num_predict = REPAIR_MAX_TOKENS
                    rgen, rattempts = _call_with_transport_retries(
                        backend,
                        prompt.system,
                        repair_user,
                        session=session,
                        what=f"repair/{protocol}/{condition}/{task.id}",
                    )
                    rec.repair = rgen.get("content", "")
                    rec.stages.append(
                        {
                            **_stage_record(StageKind.FORMALISE, prompt, rgen, rattempts),
                            "stage": "repair",
                            "user": repair_user,
                            "num_predict": REPAIR_MAX_TOKENS,
                        }
                    )
                    rencoding = extract_fenced(rec.repair, tags) if tags else None
                    routcome = (
                        adapter.parse(rencoding).stages
                        if adapter is not None and rencoding
                        else None
                    )
                    rec.repair_terminal = _earliest_terminal(
                        adherent=bool(rencoding),
                        supported=adapter is not None,
                        outcome=routcome,
                        transport_error=bool(rgen.get("error")),
                        expected_hash=expected,
                    )
                else:
                    rec.notes.append(
                        "no repair: an already-valid (or unsupported/inconclusive) "
                        "attempt is never repaired"
                    )

                records.append(rec)
                path = out_dir / f"{protocol}__{condition}__{task.id}.json"
                path.write_text(json.dumps(rec.to_dict(), indent=2), encoding="utf-8")

    return records


def phase_ledger_record() -> dict[str, Any]:
    """The derived ledger, for printing before execution and for the audit record."""
    ledger = derive_call_ledger()
    return {
        "frozen_runtime": dict(FROZEN_RUNTIME),
        "token_matching": {str(k): dict(v) for k, v in PROTOCOL_TOKEN_SPLIT.items()},
        "repair_max_tokens": REPAIR_MAX_TOKENS,
        "ledger": ledger.to_dict(),
    }
