"""Executing a protocol. Offline by default; a live call requires explicit authorisation.

Why authorisation is an object and not a flag
---------------------------------------------
A boolean ``live=True`` is set by whoever is running the script. This milestone's
constraint is different in kind: the calls are a **budgeted spend authorised by the
Lead**, and they may not happen while conformance is red — a result produced on a failing
tree cannot be attributed to the code that was reviewed.

:class:`LiveCallAuthorisation` therefore carries the authoriser, the budget, the scope and
the recorded conformance state, and :class:`AuthorisedSession` counts calls down against
the budget. Running without one raises :class:`UnauthorisedModelCall`. There is no keyword
that bypasses it.

What this module will not do
----------------------------
It will not retry an empty completion. An empty visible answer under a format restriction
is precisely the outcome the paper predicts and this study is trying to observe; retrying
it until text appears would delete the measurement.

Transport failures *are* retried, and every attempt is preserved, because a socket error
is a fact about the network and not about the protocol.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from evaluation.syntax_gate.candidates import CANDIDATES, SyntaxAdapter
from evaluation.syntax_gate.tasks import GateTask

from hamiltonian_lang.improvement.episodes import Measurement, offline_absence

from .core import (
    PROTOCOL_STAGES,
    GenerationProtocol,
    ProtocolTranscript,
    StageCall,
    StageKind,
)

if TYPE_CHECKING:  # pragma: no cover - imported lazily at runtime, see below
    from ..prompts.field_order import FieldOrderArm
    from ..prompts.stages import StagePrompt

# ``evaluation.acq0.prompts.stages`` imports this package's ``core`` for the protocol
# vocabulary, and importing a submodule runs its package ``__init__``, which imports this
# module. The cycle is broken here rather than there because the prompt layer is the
# lower one: prompts must be usable without the runner, but the runner cannot do anything
# without prompts. So the prompt imports happen inside :func:`run_protocol`, and the two
# defaults it needs are resolved there from their single source of truth rather than
# duplicated as literals in this signature.

__all__ = [
    "ModelBackend",
    "OfflineBackend",
    "ScriptedBackend",
    "LiveCallAuthorisation",
    "AuthorisedSession",
    "UnauthorisedModelCall",
    "CallBudgetExhausted",
    "ConformanceNotGreen",
    "run_protocol",
    "fence_tags_for",
]


@runtime_checkable
class ModelBackend(Protocol):
    """The same shape ``evaluation.syntax_gate.harness`` uses, so a backend is portable."""

    LIVE: bool

    def generate(self, system: str, user: str) -> dict[str, Any]: ...


class UnauthorisedModelCall(RuntimeError):
    """A live backend was used without a Lead authorisation."""


class CallBudgetExhausted(RuntimeError):
    """More calls were attempted than were authorised."""


class ConformanceNotGreen(RuntimeError):
    """A live run was attempted against a failing tree."""


@dataclass(frozen=True)
class LiveCallAuthorisation:
    """A named person authorising a bounded number of calls, on a green tree.

    ``conformance_state`` must be the literal ``"green"``. It is recorded rather than
    probed because the authoriser is the one asserting it: a probe run inside this
    process could be green while the tree the Lead reviewed was not.
    """

    authorised_by: str
    call_budget: int
    scope: str
    #: ``"green"`` or the failing state, verbatim. Anything but green refuses.
    conformance_state: str
    granted_utc: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.authorised_by.strip():
            raise ValueError("an authorisation must name who granted it")
        if self.call_budget <= 0:
            raise ValueError("an authorisation must permit at least one call")
        if not self.scope.strip():
            raise ValueError(
                "an authorisation must state its scope; an unbounded authorisation is "
                "not an authorisation for a specific study"
            )
        if self.conformance_state.strip().lower() != "green":
            raise ConformanceNotGreen(
                f"conformance is recorded as {self.conformance_state!r}. Calls are not "
                "authorised against a failing tree: a result produced on a red tree "
                "cannot be attributed to the code that was reviewed."
            )


@dataclass
class AuthorisedSession:
    """Counts calls down against a budget. Mutable on purpose — a budget is spent."""

    authorisation: LiveCallAuthorisation
    calls_made: int = 0
    log: list[str] = field(default_factory=list)

    @property
    def remaining(self) -> int:
        return self.authorisation.call_budget - self.calls_made

    def charge(self, what: str) -> None:
        if self.remaining <= 0:
            raise CallBudgetExhausted(
                f"the authorisation from {self.authorisation.authorised_by} covers "
                f"{self.authorisation.call_budget} calls and they are spent; {what} "
                "would be an unauthorised call"
            )
        self.calls_made += 1
        self.log.append(what)


class OfflineBackend:
    """Never calls anything. Every completion is an explicit absence.

    The default. A harness whose default backend reaches the network makes an accidental
    spend one missing argument away.
    """

    LIVE = False

    def __init__(self, reason: str = "offline: no model call was authorised") -> None:
        self.reason = reason
        self.calls: list[tuple[str, str]] = []

    def generate(self, system: str, user: str) -> dict[str, Any]:
        self.calls.append((system, user))
        return {
            "content": "",
            "reasoning": "",
            "prompt_tokens": None,
            "completion_tokens": None,
            "latency_s": None,
            "finish_reason": "",
            "error": None,
            "offline_reason": self.reason,
        }


class ScriptedBackend:
    """Deterministic replies for tests. Never touches a model or a network.

    ``responder`` is called with ``(stage, condition, task_id)`` so a test can make the
    draft stage and the formalisation stage behave differently, which is the only way to
    test that their costs are recorded separately.
    """

    LIVE = False

    def __init__(self, responder=None) -> None:
        self.responder = responder or (lambda stage, condition, task_id: "")
        self.calls: list[dict[str, Any]] = []
        self._context: tuple[str, str, str] = ("", "", "")

    def set_context(self, stage: str, condition: str, task_id: str) -> None:
        self._context = (stage, condition, task_id)

    def generate(self, system: str, user: str) -> dict[str, Any]:
        stage, condition, task_id = self._context
        self.calls.append(
            {"stage": stage, "condition": condition, "task_id": task_id, "user": user}
        )
        reply = self.responder(stage, condition, task_id)
        if isinstance(reply, dict):
            return reply
        text = reply or ""
        return {
            "content": text,
            "reasoning": "",
            "prompt_tokens": max(1, len(user) // 4),
            "completion_tokens": max(1, len(text) // 4),
            "latency_s": 0.01,
            "finish_reason": "stop",
            "error": None,
        }


def _measure(
    value: Any, *, instrument: str, citation: str, what: str
) -> Measurement:
    """A count from a provider, or an explicit absence. Never a substituted zero."""
    if value is None:
        return offline_absence(what)
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        return Measurement.absent(f"{what} was reported as {value!r}, which is not a count")
    return Measurement.measured(value, instrument=instrument, citation=citation)


def _one_call(
    backend: ModelBackend,
    prompt: StagePrompt,
    *,
    session: AuthorisedSession | None,
    transport_retries: int,
    transport_backoff_s: float,
) -> StageCall:
    """One stage. Transport failures retried; an empty completion never is."""
    if getattr(backend, "LIVE", False):
        if session is None:
            raise UnauthorisedModelCall(
                "a live backend was supplied with no LiveCallAuthorisation. The "
                "calibration calls are a budgeted spend authorised by the Lead; running "
                "them from a script that merely has a live backend in scope is exactly "
                "the accident the authorisation object exists to prevent."
            )
        session.charge(f"{prompt.protocol}/{prompt.stage}/{prompt.condition}/{prompt.task_id}")

    if isinstance(backend, ScriptedBackend):
        backend.set_context(str(prompt.stage), prompt.condition, prompt.task_id)

    gen: dict[str, Any] = {}
    for attempt in range(1, transport_retries + 2):
        gen = backend.generate(prompt.system, prompt.user)
        if not gen.get("error"):
            break
        if attempt <= transport_retries and transport_backoff_s > 0:
            time.sleep(transport_backoff_s * attempt)

    citation = (
        f"provider usage block for {prompt.protocol}/{prompt.stage}/"
        f"{prompt.condition}/{prompt.task_id}"
    )
    return StageCall(
        stage=prompt.stage,
        protocol=prompt.protocol,
        condition=prompt.condition,
        content=gen.get("content", "") or "",
        reasoning=gen.get("reasoning", "") or "",
        prompt_tokens=_measure(
            gen.get("prompt_tokens"),
            instrument="provider_usage",
            citation=citation,
            what="prompt tokens",
        ),
        completion_tokens=_measure(
            gen.get("completion_tokens"),
            instrument="provider_usage",
            citation=citation,
            what="completion tokens",
        ),
        latency_s=_measure(
            gen.get("latency_s"),
            instrument="time.perf_counter",
            citation="",
            what="latency",
        ),
        finish_reason=gen.get("finish_reason", "") or "",
        error=gen.get("error"),
        system=prompt.system,
        user=prompt.user,
    )


def run_protocol(
    task: GateTask,
    condition: str,
    protocol: GenerationProtocol,
    backend: ModelBackend | None = None,
    *,
    session: AuthorisedSession | None = None,
    demonstrations: list[GateTask] | None = None,
    adapters: dict[str, SyntaxAdapter | None] | None = None,
    #: ``None`` resolves to the prompt layer's own default, so there is one definition of
    #: "the incumbent phrasing" and this signature cannot drift from it.
    phrasing_id: str | None = None,
    field_order_arm: FieldOrderArm | None = None,
    transport_retries: int = 2,
    transport_backoff_s: float = 2.0,
    notes: Sequence[str] = (),
) -> ProtocolTranscript:
    """Run every stage of ``protocol`` for one (task, condition) and record all of it.

    The upstream stage's *visible content* is what stage two receives. Its reasoning
    trace is not forwarded: a provider that hides reasoning would make the two-stage arm
    unreproducible from the transcript, and an arm nobody can reconstruct is not evidence.
    """
    from ..prompts.field_order import FieldOrderArm as _Arm
    from ..prompts.stages import DEFAULT_PHRASING, build_stage_prompt

    backend = backend or OfflineBackend()
    phrasing_id = phrasing_id or DEFAULT_PHRASING
    arm = field_order_arm or _Arm.SEMANTIC_FIRST
    calls: list[StageCall] = []
    upstream_text = ""
    extra_notes = list(notes)

    for stage in PROTOCOL_STAGES[protocol]:
        kw: dict[str, Any] = {"field_order_arm": arm}
        if stage is StageKind.FORMALISE:
            kw.update(
                demonstrations=demonstrations,
                adapters=adapters,
                phrasing_id=phrasing_id,
            )
            if len(PROTOCOL_STAGES[protocol]) > 1:
                kw["upstream"] = upstream_text
        prompt = build_stage_prompt(task, condition, protocol, stage, **kw)
        call = _one_call(
            backend,
            prompt,
            session=session,
            transport_retries=transport_retries,
            transport_backoff_s=transport_backoff_s,
        )
        calls.append(call)
        if stage in (StageKind.DRAFT, StageKind.PLAN):
            upstream_text = call.content
            if call.empty:
                extra_notes.append(
                    f"the {stage} stage returned no visible text. Stage two receives an "
                    "empty upstream block, which is the honest representation of what "
                    "happened; substituting the problem statement would hide a "
                    "first-stage failure inside a second-stage result."
                )
            if call.error:
                extra_notes.append(
                    f"the {stage} stage failed at transport ({call.error}); the "
                    "formalisation stage still ran so the transcript is complete, and "
                    "this trial is INCONCLUSIVE rather than a protocol failure"
                )

    formal = next((c for c in calls if c.stage is StageKind.FORMALISE), None)
    return ProtocolTranscript(
        protocol=protocol,
        task_id=task.id,
        condition=condition,
        calls=tuple(calls),
        formal_output=formal.content if formal else "",
        unrestricted_output=upstream_text,
        notes=tuple(extra_notes),
    )


def fence_tags_for(condition: str) -> tuple[str, ...]:
    """The tags a condition's reply should carry. Empty for the structured-English arm."""
    candidate = CANDIDATES.get(condition)
    return candidate.fence_tags if candidate else ()
