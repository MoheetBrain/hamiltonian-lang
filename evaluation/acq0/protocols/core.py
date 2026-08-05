"""The three generation protocols and their per-stage cost record.

The protocols
-------------
``DIRECT_FORMAL``
    problem -> target syntax. One call. **This is the protocol the syntax tournament
    currently runs**, so it is the arm every other arm is compared against; it is not a
    strawman built for this study.

``DRAFT_THEN_FORMAL``
    problem -> unrestricted natural-language semantic draft; draft -> target syntax. Two
    calls. The paper's NL-to-Format arm, which came closest to unrestricted performance.

``PLAN_THEN_FORMAL``
    problem -> compact semantic plan; plan -> target syntax. Two calls. A cheaper middle
    point: the first stage is bounded, so the arm cannot win merely by being allowed to
    emit an unbounded amount of text.

Why the token ledger is per-stage and never a single number
-----------------------------------------------------------
A two-stage protocol that reports only its formalisation tokens looks as cheap as the
one-stage protocol and is not. :class:`TokenLedger` therefore keeps every stage's cost in
its own slot and :meth:`TokenLedger.total_completion_tokens` is a derived view that
refuses to produce a number when any component is absent. There is no field on this class
that a caller can set to a single conflated total.

Why a transcript checks its own stage count
-------------------------------------------
:class:`ProtocolTranscript` refuses to be constructed for ``DRAFT_THEN_FORMAL`` with one
stage recorded. A two-stage run whose draft call went unrecorded would report the
two-stage protocol's quality at the one-stage protocol's price, which is the single most
flattering error this study could make about its own preferred arm.

Why counts are ``Measurement`` and not ``int``
----------------------------------------------
:class:`~hamiltonian_lang.improvement.episodes.Measurement` will not hold a number that no
instrument produced. Offline, the honest value is an explicit absence carrying a reason,
not a zero that later reads as "this call was free".
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from hamiltonian_lang.improvement.episodes import Measurement, offline_absence

__all__ = [
    "GenerationProtocol",
    "StageKind",
    "PROTOCOL_STAGES",
    "PROTOCOL_RATIONALE",
    "UNRESTRICTED_STAGES",
    "StageCall",
    "TokenLedger",
    "ProtocolTranscript",
    "StageAccountingError",
    "token_instrument",
]


class GenerationProtocol(StrEnum):
    """How a formal encoding was obtained. Recorded on every trial, never assumed."""

    DIRECT_FORMAL = "DIRECT_FORMAL"
    DRAFT_THEN_FORMAL = "DRAFT_THEN_FORMAL"
    PLAN_THEN_FORMAL = "PLAN_THEN_FORMAL"


class StageKind(StrEnum):
    """One call within a protocol.

    ``DRAFT`` and ``PLAN`` are **format-unrestricted**: no candidate syntax is named, no
    fenced block is requested and no grammar is supplied. That is the manipulation. A
    stage that leaks the target grammar into the unrestricted stage would make the
    two-stage arm a two-shot version of the one-stage arm rather than a different
    protocol.
    """

    DRAFT = "draft"
    PLAN = "plan"
    FORMALISE = "formalise"


#: Which stages each protocol runs, in order. The single source of truth: the runner, the
#: token ledger and the tests all read this rather than each hard-coding a stage count.
PROTOCOL_STAGES: Mapping[GenerationProtocol, tuple[StageKind, ...]] = {
    GenerationProtocol.DIRECT_FORMAL: (StageKind.FORMALISE,),
    GenerationProtocol.DRAFT_THEN_FORMAL: (StageKind.DRAFT, StageKind.FORMALISE),
    GenerationProtocol.PLAN_THEN_FORMAL: (StageKind.PLAN, StageKind.FORMALISE),
}

#: Stages in which the model is under **no** format restriction. Kept as data because the
#: oracle guard and the prompt builders both need the same answer and must not disagree.
UNRESTRICTED_STAGES: frozenset[StageKind] = frozenset({StageKind.DRAFT, StageKind.PLAN})

#: Why each protocol is in the design. Written into the record so a reader a year from now
#: does not have to reconstruct the argument from a commit message.
PROTOCOL_RATIONALE: Mapping[GenerationProtocol, str] = {
    GenerationProtocol.DIRECT_FORMAL: (
        "the protocol the syntax tournament runs today. Included as the reference arm: "
        "if it is not measured, no other arm's result means anything about ACQ0."
    ),
    GenerationProtocol.DRAFT_THEN_FORMAL: (
        "the paper's two-stage NL-to-Format arm, which came closest to unrestricted "
        "performance. If format restriction is damaging reasoning here, this arm is "
        "where the damage becomes visible."
    ),
    GenerationProtocol.PLAN_THEN_FORMAL: (
        "a bounded first stage. Run only if DIRECT and DRAFT leave genuine ambiguity: "
        "it separates 'the model needed to think first' from 'the model needed to emit "
        "more text first', which an unbounded draft cannot."
    ),
}


class StageAccountingError(ValueError):
    """A transcript's stages do not match the protocol it claims to have run."""


def token_instrument(citation: str) -> str:
    """The only instrument name a token count from this harness may carry.

    ``provider_usage`` is unprobeable from inside this process, so
    :class:`Measurement` requires the artefact to be cited. The citation is the evidence
    that a call really happened; ``citation`` is threaded through so the requirement
    cannot be satisfied with an empty string.
    """
    if not citation.strip():
        raise ValueError(
            "a token count read from a provider's usage block must cite the artefact it "
            "came from; without the citation there is no evidence a call was made"
        )
    return "provider_usage"


@dataclass(frozen=True)
class StageCall:
    """One model call's record. Costs are per-call and stay per-call.

    ``content`` is the visible completion. ``reasoning`` is kept separate because a
    provider that streams a reasoning trace charges for it, and folding it into
    ``content`` would make a protocol that reasons more look like a protocol that answers
    more.
    """

    stage: StageKind
    protocol: GenerationProtocol
    #: The condition (candidate surface) this stage served. The unrestricted stages carry
    #: it for bookkeeping only; their prompts never name it.
    condition: str
    content: str = ""
    reasoning: str = ""
    prompt_tokens: Measurement = field(
        default_factory=lambda: offline_absence("prompt tokens")
    )
    completion_tokens: Measurement = field(
        default_factory=lambda: offline_absence("completion tokens")
    )
    latency_s: Measurement = field(default_factory=lambda: offline_absence("latency"))
    finish_reason: str = ""
    #: Transport failure. Distinct from an empty completion, which is a model failure.
    error: str | None = None
    #: The exact prompt sent, preserved so a leak can be audited after the fact rather
    #: than argued about.
    system: str = ""
    user: str = ""

    def __post_init__(self) -> None:
        if self.stage not in PROTOCOL_STAGES[self.protocol]:
            raise StageAccountingError(
                f"protocol {self.protocol} does not run stage {self.stage}; "
                f"its stages are {[str(s) for s in PROTOCOL_STAGES[self.protocol]]}"
            )

    @property
    def empty(self) -> bool:
        """The call succeeded and produced no visible text. Not an error."""
        return self.error is None and not (self.content or "").strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": str(self.stage),
            "protocol": str(self.protocol),
            "condition": self.condition,
            "content": self.content,
            "reasoning": self.reasoning,
            "prompt_tokens": self.prompt_tokens.to_dict(),
            "completion_tokens": self.completion_tokens.to_dict(),
            "latency_s": self.latency_s.to_dict(),
            "finish_reason": self.finish_reason,
            "error": self.error,
        }


@dataclass(frozen=True)
class TokenLedger:
    """Per-stage cost. The two-stage protocol's real price, made unhideable.

    There is deliberately **no** settable total. ``total_*`` are derived, and they return
    an absent :class:`Measurement` when any component is absent — a partially measured
    run has no total, and inventing one by treating an unmeasured stage as zero is how a
    two-stage protocol comes to look free.
    """

    #: Cost of the format-unrestricted stage (draft or plan). Absent for DIRECT_FORMAL —
    #: which never ran one, a different fact from "it cost nothing".
    unrestricted: tuple[Measurement, Measurement] = field(
        default_factory=lambda: (
            Measurement.absent("DIRECT_FORMAL runs no unrestricted stage"),
            Measurement.absent("DIRECT_FORMAL runs no unrestricted stage"),
        )
    )
    #: Cost of the formalisation stage: (prompt, completion).
    formalisation: tuple[Measurement, Measurement] = field(
        default_factory=lambda: (
            offline_absence("formalisation prompt tokens"),
            offline_absence("formalisation completion tokens"),
        )
    )
    #: Did an unrestricted stage run at all?
    #:
    #: This separates the two reasons a component can be missing, and the separation is
    #: what makes the protocols comparable on cost. ``False`` means the stage **did not
    #: exist**, so its contribution to a total is a structural zero — DIRECT_FORMAL has a
    #: real, complete token total. ``True`` with an absent measurement means the stage
    #: ran and its cost is unknown, and then the total is genuinely absent. Collapsing
    #: the two would either make DIRECT_FORMAL's cost unavailable (blocking the very
    #: comparison this ledger exists for) or make an unmeasured draft look free.
    unrestricted_stage_ran: bool = False

    @property
    def unrestricted_prompt_tokens(self) -> Measurement:
        return self.unrestricted[0]

    @property
    def unrestricted_completion_tokens(self) -> Measurement:
        return self.unrestricted[1]

    @property
    def formalisation_prompt_tokens(self) -> Measurement:
        return self.formalisation[0]

    @property
    def formalisation_completion_tokens(self) -> Measurement:
        return self.formalisation[1]

    @staticmethod
    def _sum(parts: Sequence[Measurement], what: str) -> Measurement:
        """Sum, or an explicit absence naming the component that was not measured.

        A stage that was never run contributes an absence, and the total is therefore
        absent too. That is correct: the comparison a total is wanted for — one protocol
        against another — is unavailable when one side is unmeasured, and a total that
        silently substituted zero would make that unavailability invisible.
        """
        missing = [p.reason for p in parts if not p.is_measured]
        if missing:
            return Measurement.absent(
                f"{what} has no total: {len(missing)} of {len(parts)} components are "
                f"absent ({'; '.join(missing[:2])})"
            )
        values = [p.value for p in parts if p.value is not None]
        return Measurement.measured(
            sum(values),
            instrument="provider_usage",
            citation=f"summed from per-stage provider usage blocks ({what})",
        )

    def _components(self, index: int) -> list[Measurement]:
        parts = [self.formalisation[index]]
        if self.unrestricted_stage_ran:
            parts.append(self.unrestricted[index])
        return parts

    @property
    def total_prompt_tokens(self) -> Measurement:
        return self._sum(self._components(0), "total prompt tokens")

    @property
    def total_completion_tokens(self) -> Measurement:
        return self._sum(self._components(1), "total completion tokens")

    def to_dict(self) -> dict[str, Any]:
        return {
            "unrestricted_prompt_tokens": self.unrestricted[0].to_dict(),
            "unrestricted_completion_tokens": self.unrestricted[1].to_dict(),
            "formalisation_prompt_tokens": self.formalisation[0].to_dict(),
            "formalisation_completion_tokens": self.formalisation[1].to_dict(),
            "unrestricted_stage_ran": self.unrestricted_stage_ran,
            "total_prompt_tokens": self.total_prompt_tokens.to_dict(),
            "total_completion_tokens": self.total_completion_tokens.to_dict(),
            "note": (
                "draft/plan cost is recorded separately from formalisation cost so the "
                "two-stage protocol's true price is visible; there is no settable total"
            ),
            "absence_semantics": (
                "unrestricted_stage_ran=False means the stage did not exist and "
                "contributes a structural zero; True with an absent count means the "
                "stage ran and its cost is unknown, and then the total is absent too"
            ),
        }


@dataclass(frozen=True)
class ProtocolTranscript:
    """Every call one protocol made for one (task, condition), plus its ledger.

    Constructing this for a two-stage protocol with one recorded call raises. The check
    is cheap and it is the only thing standing between an honest cost comparison and a
    two-stage arm that reports one-stage prices.
    """

    protocol: GenerationProtocol
    task_id: str
    condition: str
    calls: tuple[StageCall, ...]
    #: The text the formalisation stage produced, verbatim. Extraction into a candidate
    #: encoding happens in :mod:`.metrics`, not here.
    formal_output: str = ""
    #: The unrestricted stage's text, verbatim; ``""`` for DIRECT_FORMAL.
    unrestricted_output: str = ""
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        expected = PROTOCOL_STAGES[self.protocol]
        got = tuple(c.stage for c in self.calls)
        if got != expected:
            raise StageAccountingError(
                f"{self.protocol} runs stages {[str(s) for s in expected]} but the "
                f"transcript records {[str(s) for s in got]}. A two-stage protocol whose "
                "first call went unrecorded would report two-stage quality at one-stage "
                "cost."
            )
        for call in self.calls:
            if call.protocol is not self.protocol:
                raise StageAccountingError(
                    f"call recorded under {call.protocol} inside a {self.protocol} "
                    "transcript"
                )

    @property
    def ledger(self) -> TokenLedger:
        unrestricted = [c for c in self.calls if c.stage in UNRESTRICTED_STAGES]
        formal = [c for c in self.calls if c.stage is StageKind.FORMALISE]
        if unrestricted:
            u = (unrestricted[0].prompt_tokens, unrestricted[0].completion_tokens)
        else:
            absent = Measurement.absent(
                f"{self.protocol} runs no unrestricted stage, so none was measured"
            )
            u = (absent, absent)
        f = (
            (formal[0].prompt_tokens, formal[0].completion_tokens)
            if formal
            else (
                offline_absence("formalisation prompt tokens"),
                offline_absence("formalisation completion tokens"),
            )
        )
        return TokenLedger(
            unrestricted=u,
            formalisation=f,
            unrestricted_stage_ran=bool(unrestricted),
        )

    @property
    def latency_s(self) -> Measurement:
        parts = [c.latency_s for c in self.calls]
        missing = [p for p in parts if not p.is_measured]
        if missing:
            return Measurement.absent(
                f"end-to-end latency has no total: {len(missing)} of {len(parts)} "
                f"stage latencies are absent"
            )
        return Measurement.measured(
            sum(p.value for p in parts if p.value is not None),
            instrument="time.perf_counter",
        )

    @property
    def transport_failed(self) -> bool:
        return any(c.error is not None for c in self.calls)

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": str(self.protocol),
            "task_id": self.task_id,
            "condition": self.condition,
            "calls": [c.to_dict() for c in self.calls],
            "ledger": self.ledger.to_dict(),
            "latency_s": self.latency_s.to_dict(),
            "transport_failed": self.transport_failed,
            "notes": list(self.notes),
        }
