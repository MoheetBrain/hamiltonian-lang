"""Measuring ``prompt_eval_count`` on the real frozen prompts.

What this module refuses to do
------------------------------
It never divides a character count by a constant. ``evaluation/syntax_gate/prompts.py``
offers :func:`~evaluation.syntax_gate.prompts.estimate_tokens` with a conservative
divisor of 3.0, and that estimate is a reasonable design aid, but it is not a
measurement and it may not decide eligibility. Measured on the frozen material,
candidate D's five-demonstration prompt estimates at ~5.4k tokens against a ceiling of
5,888 — a margin of about 8%, well inside the error of any characters-per-token
constant, and JSON triple text (``["_:e1","lhs","_:e2"]``) tokenises *worse* than prose.
The estimate cannot tell us which side of the line D falls on. Only the server can.

The truncation trap this module exists to close
-----------------------------------------------
Asking the server for a token count is itself a request served in a slot. If the probe
runs with a larger context than the tournament will, it reports a count for a prompt the
tournament will not actually send. If it runs with the *same* context and the prompt
overflows, ``llama-server`` evicts the front of the context and returns
``prompt_eval_count`` for **what survived** — a number below the ceiling, describing a
prompt that was already destroyed.

So :class:`OllamaPromptEvalCounter` pins ``num_ctx`` to the slot under test and treats a
count at or near the context limit as evidence of eviction: the true size is unknown and
strictly greater, which is ``OVERFLOWS``, never ``FITS``. It is reported as an *absent*
measurement carrying that reason rather than as an exception, because a truncated probe
is a fact about one prompt and the ladder walk must be able to record it and carry on to
the next rung. A probe that cannot distinguish those two cases is worse than no probe,
because it returns a comfortable number in exactly the situation that should have stopped
the run.

Authorisation
-------------
The live counter is a model call and is governed by the same
:class:`~evaluation.acq0.protocols.runner.LiveCallAuthorisation` the protocol runner
uses — one authorisation object for the milestone, not one per subsystem. Constructing
the counter without one raises. ``num_predict=0`` makes the call cheap, not free.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from hamiltonian_lang.improvement.episodes import Measurement

from ..protocols.runner import LiveCallAuthorisation, UnauthorisedModelCall
from .slots import (
    COMPLETION_ALLOWANCE,
    DEFAULT_SAFETY_RESERVE,
    Eligibility,
    Fit,
    SlotPolicy,
    eligibility,
)

__all__ = [
    "TokenCounter",
    "OfflineTokenCounter",
    "StubTokenCounter",
    "OllamaPromptEvalCounter",
    "PromptProbe",
    "probe_prompt",
    "TRUNCATION_MARGIN",
]

#: How close to ``num_ctx`` a reported count may come before it is treated as evidence
#: of eviction rather than as a measurement. The server does not announce truncation, so
#: proximity to the limit is the only signal available; a prompt that genuinely lands in
#: the last few tokens of the slot is indistinguishable from one that was cut, and both
#: are refused.
TRUNCATION_MARGIN = 8


@runtime_checkable
class TokenCounter(Protocol):
    """Something that can say how many tokens a prompt occupies.

    ``AUTHORITATIVE`` separates a real server count from a test double. It is read by
    :class:`~evaluation.acq0.budget.report.BudgetReport`, which refuses to be marked
    official on the strength of a stub — the one way this machinery could produce a
    confident, entirely fictional eligibility verdict.
    """

    AUTHORITATIVE: bool
    name: str

    def count(self, system: str, user: str, *, num_ctx: int) -> Measurement: ...


class OfflineTokenCounter:
    """Counts nothing and says so. The default.

    Records what it *would* have probed, so an offline run still produces the full list
    of prompts awaiting measurement rather than an empty report that looks complete.
    """

    AUTHORITATIVE = False
    name = "offline"

    def __init__(self, reason: str = "") -> None:
        self.reason = reason or (
            "no model call was authorised, and no local tokeniser for this model is "
            "installed, so prompt_eval_count is unavailable"
        )
        self.requested: list[tuple[str, str, int]] = []

    def count(self, system: str, user: str, *, num_ctx: int) -> Measurement:
        self.requested.append((system, user, num_ctx))
        return Measurement.absent(self.reason)


class StubTokenCounter:
    """A deterministic counter for tests. Never touches a network.

    Marked non-authoritative. The default rule is a fixed divisor, which is exactly the
    thing this package forbids for a real decision — it is acceptable here *only*
    because :attr:`AUTHORITATIVE` is ``False`` and the report refuses to go official on
    it. ``fixed`` lets a test place a prompt precisely on either side of a ceiling.
    """

    AUTHORITATIVE = False
    name = "stub"

    def __init__(
        self,
        fixed: int | None = None,
        *,
        chars_per_token: float = 4.0,
        by_prompt: dict[str, int] | None = None,
    ) -> None:
        self.fixed = fixed
        self.chars_per_token = chars_per_token
        self.by_prompt = by_prompt or {}
        self.calls: list[dict[str, Any]] = []

    def count(self, system: str, user: str, *, num_ctx: int) -> Measurement:
        self.calls.append({"system": system, "user": user, "num_ctx": num_ctx})
        text = f"{system}\n{user}"
        if text in self.by_prompt:
            value = self.by_prompt[text]
        elif self.fixed is not None:
            value = self.fixed
        else:
            value = max(1, int(len(text) / self.chars_per_token))
        return Measurement.measured(
            value,
            instrument="provider_usage",
            citation=(
                "StubTokenCounter: a deterministic test double, not a server count. "
                "Any report built on it is non-authoritative by construction."
            ),
        )


class OllamaPromptEvalCounter:
    """The real thing: ``POST /api/generate`` with ``num_predict=0``.

    The response's ``prompt_eval_count`` is the server's own count of the tokens it
    evaluated — the exact quantity the eligibility inequality is written in terms of, and
    the reason this probe exists rather than a tokeniser approximation.

    ``num_ctx`` is pinned to the slot under test on every call, so the probe measures the
    prompt under the configuration the tournament will actually run.
    """

    AUTHORITATIVE = True
    name = "ollama:prompt_eval_count"

    def __init__(
        self,
        model: str,
        authorisation: LiveCallAuthorisation | None = None,
        *,
        native_url: str = "http://localhost:11434",
        timeout_s: float = 120.0,
    ) -> None:
        if authorisation is None:
            raise UnauthorisedModelCall(
                "the prompt-eval probe is a model call and needs a LiveCallAuthorisation "
                "naming the Lead, its budget and the recorded conformance state. "
                "num_predict=0 makes the call cheap; it does not make it unbudgeted, and "
                "an unauthorised probe is exactly the accidental spend the authorisation "
                "object exists to prevent."
            )
        self.model = model
        self.authorisation = authorisation
        self.native_url = native_url.rstrip("/")
        self.timeout_s = timeout_s
        self.calls: list[dict[str, Any]] = []

    def count(self, system: str, user: str, *, num_ctx: int) -> Measurement:
        payload = {
            "model": self.model,
            "prompt": user,
            "system": system,
            "stream": False,
            # Evaluate the prompt, generate nothing. The prompt-eval pass is the whole
            # measurement; sampling even one token would add latency and a completion
            # cost to a call whose only purpose is to count the input.
            "options": {"num_predict": 0, "num_ctx": num_ctx, "temperature": 0.0},
        }
        req = urllib.request.Request(
            f"{self.native_url}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                body = json.loads(r.read().decode())
        except (urllib.error.URLError, OSError, ValueError) as e:
            return Measurement.absent(
                f"the prompt-eval probe failed at transport ({type(e).__name__}: {e}); "
                "no count was obtained, and a transport failure is not a small prompt"
            )
        elapsed = time.perf_counter() - started
        raw = body.get("prompt_eval_count")
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
            return Measurement.absent(
                f"the server returned prompt_eval_count={raw!r}, which is not a count; "
                "the probe cannot proceed on a value it cannot interpret"
            )
        if raw >= num_ctx - TRUNCATION_MARGIN:
            return Measurement.absent(
                f"prompt_eval_count={raw} is within {TRUNCATION_MARGIN} tokens of the "
                f"{num_ctx}-token slot. The server evicts the front of an oversized "
                "context and reports the count for what survived, so this number is a "
                "lower bound on a prompt that was already truncated, not a measurement "
                "of the prompt that was sent. Treated as OVERFLOWS."
            )
        self.calls.append(
            {"num_ctx": num_ctx, "prompt_eval_count": raw, "latency_s": elapsed}
        )
        return Measurement.measured(
            raw,
            instrument="provider_usage",
            citation=(
                f"Ollama /api/generate prompt_eval_count for model {self.model} at "
                f"num_ctx={num_ctx}, num_predict=0"
            ),
        )


@dataclass(frozen=True)
class PromptProbe:
    """One prompt, measured against one slot policy.

    ``condition`` and ``curriculum_size`` are carried so a report row identifies itself
    without reference to the order it was produced in.
    """

    condition: str
    task_id: str
    curriculum_size: int
    characters: int
    prompt_eval_count: Measurement
    eligibility: Eligibility
    counter_name: str
    authoritative: bool
    curriculum: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def fits(self) -> bool:
        return self.eligibility.fits

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition,
            "task_id": self.task_id,
            "curriculum_size": self.curriculum_size,
            "curriculum": list(self.curriculum),
            "characters": self.characters,
            "prompt_eval_count": self.prompt_eval_count.to_dict(),
            "eligibility": self.eligibility.to_dict(),
            "counter": self.counter_name,
            "authoritative": self.authoritative,
            "notes": list(self.notes),
        }


def probe_prompt(
    system: str,
    user: str,
    *,
    condition: str,
    task_id: str,
    policy: SlotPolicy,
    counter: TokenCounter,
    curriculum: Sequence[str] = (),
    completion_allowance: int = COMPLETION_ALLOWANCE,
    safety_reserve: int = DEFAULT_SAFETY_RESERVE,
) -> PromptProbe:
    """Measure one prompt and decide its eligibility. No estimate is consulted.

    ``characters`` is recorded alongside the count because the *ratio* between them is
    itself a finding — it is how the stale 3.0 divisor was shown to be wrong for the JSON
    candidate — but it never participates in the verdict.
    """
    measurement = counter.count(system, user, num_ctx=policy.per_slot_context)
    verdict = eligibility(
        measurement,
        policy,
        completion_allowance=completion_allowance,
        safety_reserve=safety_reserve,
    )
    notes: list[str] = []
    if verdict.fit is Fit.UNDETERMINED and "truncat" in measurement.reason:
        # The counter refused a truncated reading. That is an overflow with an unknown
        # magnitude, not an unmeasured prompt, and recording it as merely undetermined
        # would let a later pass re-probe it under a bigger slot and call it fine.
        verdict = Eligibility(
            fit=Fit.OVERFLOWS,
            policy=verdict.policy,
            prompt_eval_count=measurement,
            completion_allowance=completion_allowance,
            safety_reserve=safety_reserve,
            ceiling=verdict.ceiling,
            headroom=None,
            detail=(
                "the server truncated the prompt, so its size is unknown and strictly "
                "greater than the slot; this OVERFLOWS regardless of the exact value"
            ),
        )
        notes.append("truncation detected by the probe; treated as OVERFLOWS")
    return PromptProbe(
        condition=condition,
        task_id=task_id,
        curriculum_size=len(curriculum),
        characters=len(system) + 1 + len(user),
        prompt_eval_count=measurement,
        eligibility=verdict,
        counter_name=counter.name,
        authoritative=bool(getattr(counter, "AUTHORITATIVE", False)),
        curriculum=tuple(curriculum),
        notes=tuple(notes),
    )
