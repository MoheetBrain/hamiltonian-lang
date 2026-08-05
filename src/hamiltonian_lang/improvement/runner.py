"""Phase 14 — the offline one-repair arena.

One task, one generation, at most one repair, and an independent verdict on both. No
model provider is contacted from this module: the model is an injected interface and the
adapter this project ships for it is a deterministic script.

The shape of a run
------------------
1. a canonical task, with a reference encoding that compiles
2. the model's first attempt
3. an independent verification of that attempt
4. if it failed, a **structured** diagnostic — codes, not prose
5. exactly one repair
6. an independent verification of the repair
7. an immutable outcome, a ledger that can replay it, and a routing decision

Rules encoded rather than documented
------------------------------------
**The initial failure is preserved.** A repaired episode still carries the first
attempt's text, hashes, verdict and diagnostic codes. An arena that overwrites the first
attempt with the repaired one reports a first-attempt success rate that is really a
post-repair success rate.

**Exactly one repair.** ``ScriptedModel`` raises on a second repair call for the same
task, and the runner never issues one. Two repairs make the outcome unattributable:
nothing says which one carried the fix.

**Verification is independent of the model.** The runner refuses a verifier that is the
model object. The default verifier is the compiler's own canonical form, which is the
deterministic oracle the Lead audit identifies as the only trustworthy one available.

**An unsupported backend is not a failure.** Backend probes are recorded and never
affect the verdict, the status, or the routing. The verdict comes from the canonical
form; a Lean or Stan backend that cannot express a construct says nothing about whether
the model got the task right. Translation loss in a probe is likewise not ``semantic_loss``
for the episode.

**No token cost is fabricated.** A scripted adapter performs no inference, so it reports
no tokens — not zero tokens. ``ArenaOutcome.token_cost`` is ``Unavailable`` in that case
and stays that way through every aggregate.

Seams for the durable subsystem
-------------------------------
``Verifier``, ``DiagnosticSource`` and ``LedgerSink`` are Protocols. The concrete classes
here are defaults that keep the arena runnable and testable on its own; the durable
verification, structured-diagnostic and ledger implementations replace them by injection
without a change to this module.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from .memory import (
    NearMissKind,
    RoutingDecision,
    RoutingFacts,
    VerifierOutcome,
    exact_hash_of,
    route,
)
from .skills import SkillTaxonomy, TokenAccount, TokenSource, default_taxonomy
from .state import Hypothesis, SystemState, Unavailable

__all__ = [
    "ArenaTask",
    "ModelResponse",
    "ModelBackend",
    "ScriptedTurns",
    "ScriptedModel",
    "ScriptError",
    "RepairBudgetExceeded",
    "ArenaVerification",
    "Verifier",
    "CanonicalFormVerifier",
    "ArenaDiagnostic",
    "DiagnosticSource",
    "CompilerDiagnostics",
    "EventName",
    "ArenaEvent",
    "LedgerSink",
    "InMemoryLedger",
    "BackendSupportReport",
    "AttemptRecord",
    "ArenaStatus",
    "ArenaConfig",
    "ArenaOutcome",
    "run_arena",
    "replay",
]


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArenaTask:
    """One canonical task with a reference encoding that is known to compile."""

    task_id: str
    prompt: str
    reference_source: str
    required_verifiers: tuple[str, ...] = ("canonical_form",)
    description: str = ""
    backend_probes: tuple[str, ...] = ()

    def reference_hash(self) -> str:
        """Content hash of the reference. Raises if the reference itself is broken."""
        from .. import compile_source

        result = compile_source(self.reference_source, f"<reference:{self.task_id}>")
        if not result.ok():
            raise ValueError(
                f"task {self.task_id!r} has a reference that does not compile:\n"
                + result.diagnostics.render()
            )
        return result.hash()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "required_verifiers": list(self.required_verifiers),
            "backend_probes": list(self.backend_probes),
            "reference_hash": self.reference_hash(),
        }


# ---------------------------------------------------------------------------
# The model interface
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelResponse:
    """What an adapter returns. ``tokens`` defaults to *not reported*, never to zero."""

    text: str
    tokens: TokenAccount = field(default_factory=TokenAccount)
    latency_s: float | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "tokens": self.tokens.to_dict(),
            "latency_s": self.latency_s,
            "error": self.error,
        }


@runtime_checkable
class ModelBackend(Protocol):
    """The two calls the arena makes. Nothing else is assumed about a model."""

    name: str
    live: bool

    def generate(self, task: ArenaTask, prompt: str) -> ModelResponse: ...

    def repair(
        self, task: ArenaTask, broken_output: str, diagnostic: str
    ) -> ModelResponse: ...


class ScriptError(RuntimeError):
    """Raised when the script has no entry for what the arena asked for."""


class RepairBudgetExceeded(RuntimeError):
    """Raised on a second repair for one task. The budget is one, by design."""


@dataclass(frozen=True)
class ScriptedTurns:
    generation: str
    repair: str | None = None


class ScriptedModel:
    """A deterministic stand-in for a model. Contacts nothing.

    It exists so the whole arena — diagnostics, repair, verification, routing, evidence —
    can be exercised end to end and asserted on, with no provider, no network and no
    sampling variance. It reports **no** token counts, because it consumed none.
    """

    name = "scripted"
    live = False

    def __init__(self, script: Mapping[str, ScriptedTurns]) -> None:
        self._script = dict(script)
        self._generations: dict[str, int] = {}
        self._repairs: dict[str, int] = {}

    def _turns(self, task: ArenaTask) -> ScriptedTurns:
        try:
            return self._script[task.task_id]
        except KeyError:
            raise ScriptError(
                f"no scripted turns for task {task.task_id!r}; known tasks: "
                f"{sorted(self._script)}"
            ) from None

    def generate(self, task: ArenaTask, prompt: str) -> ModelResponse:
        self._generations[task.task_id] = self._generations.get(task.task_id, 0) + 1
        return ModelResponse(
            text=self._turns(task).generation,
            tokens=TokenAccount(TokenSource.NOT_REPORTED),
        )

    def repair(self, task: ArenaTask, broken_output: str, diagnostic: str) -> ModelResponse:
        count = self._repairs.get(task.task_id, 0)
        if count >= 1:
            raise RepairBudgetExceeded(
                f"a second repair was requested for {task.task_id!r}; the budget is one, "
                "because two repairs leave the outcome unattributable"
            )
        self._repairs[task.task_id] = count + 1
        turns = self._turns(task)
        if turns.repair is None:
            raise ScriptError(f"task {task.task_id!r} has no scripted repair")
        return ModelResponse(
            text=turns.repair, tokens=TokenAccount(TokenSource.NOT_REPORTED)
        )

    def call_counts(self) -> dict[str, dict[str, int]]:
        return {"generate": dict(self._generations), "repair": dict(self._repairs)}


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArenaVerification:
    """A verdict about one candidate encoding of one task.

    ``INCONCLUSIVE`` is used when the output does not compile: there is no canonical form
    to compare, so the *semantic* question has no answer. The parse failure is recorded
    separately in ``parsed``. Collapsing the two would report "wrong meaning" for output
    whose meaning was never determined.
    """

    verifier: str
    outcome: VerifierOutcome
    parsed: bool
    checked: bool
    canonical_hash: str | None
    detail: str
    diagnostic_codes: tuple[str, ...] = ()
    unresolved_obligations: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "verifier": self.verifier,
            "outcome": self.outcome.value,
            "parsed": self.parsed,
            "checked": self.checked,
            "canonical_hash": self.canonical_hash,
            "detail": self.detail,
            "diagnostic_codes": list(self.diagnostic_codes),
            "unresolved_obligations": self.unresolved_obligations,
        }


@runtime_checkable
class Verifier(Protocol):
    name: str

    def verify(self, task: ArenaTask, source: str) -> ArenaVerification: ...


class CanonicalFormVerifier:
    """The deterministic oracle: compile, then compare the alpha-invariant content hash.

    No model judges anything here. The hash excludes bound-variable names, so a correct
    answer that renames a binder passes, and a wrong-arity call — which canonicalises
    differently — fails.

    ``parsed`` and ``checked`` are separate facets and are measured separately. A
    wrong-arity call **parses** and fails the type check; reporting it as a parse failure
    would understate first-attempt parse rate and misattribute the defect to the surface
    syntax. The parser is therefore run in its own right rather than inferred from the
    compile verdict.
    """

    name = "canonical_form"

    def verify(self, task: ArenaTask, source: str) -> ArenaVerification:
        from .. import compile_source, parse

        file = f"<candidate:{task.task_id}>"
        _, parse_bag = parse(source, file)
        parsed = parse_bag.ok()
        result = compile_source(source, file)
        codes = tuple(d.code for d in result.diagnostics.errors)
        if not result.ok():
            stage = "parse" if not parsed else "resolution or type checking"
            return ArenaVerification(
                verifier=self.name,
                outcome=VerifierOutcome.INCONCLUSIVE,
                parsed=parsed,
                checked=False,
                canonical_hash=None,
                detail=(
                    f"the candidate fails at {stage}, so it has no canonical form to "
                    "compare; the semantic question is unanswered rather than answered no"
                ),
                diagnostic_codes=codes,
            )
        candidate_hash = result.hash()
        matched = candidate_hash == task.reference_hash()
        return ArenaVerification(
            verifier=self.name,
            outcome=VerifierOutcome.PASS if matched else VerifierOutcome.FAIL,
            parsed=True,
            checked=True,
            canonical_hash=candidate_hash,
            detail=(
                "canonical form matches the reference"
                if matched
                else "compiles, but its canonical form differs from the reference"
            ),
            diagnostic_codes=codes,
            unresolved_obligations=len(result.obligations),
        )


# ---------------------------------------------------------------------------
# Structured diagnostics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArenaDiagnostic:
    """Codes first, prose second. A repair loop acts on the codes."""

    codes: tuple[str, ...]
    text: str
    primary_skill_id: str | None = None

    @property
    def actionable(self) -> bool:
        return bool(self.codes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "codes": list(self.codes),
            "text": self.text,
            "primary_skill_id": self.primary_skill_id,
        }


@runtime_checkable
class DiagnosticSource(Protocol):
    name: str

    def diagnose(self, task: ArenaTask, source: str) -> ArenaDiagnostic: ...


class CompilerDiagnostics:
    """Structured diagnostics from the compiler's own bag, attributed via the taxonomy.

    A verified failure with **no** diagnostic is possible and is reported as such: the
    output compiles and means the wrong thing. That case is unrepairable by this loop,
    which is a finding about the diagnostics, not about the model.
    """

    name = "compiler"

    def __init__(self, taxonomy: SkillTaxonomy | None = None) -> None:
        self._taxonomy = taxonomy

    def _tax(self) -> SkillTaxonomy:
        if self._taxonomy is None:
            self._taxonomy = default_taxonomy()
        return self._taxonomy

    def diagnose(self, task: ArenaTask, source: str) -> ArenaDiagnostic:
        from .. import compile_source

        result = compile_source(source, f"<candidate:{task.task_id}>")
        errors = result.diagnostics.errors
        codes = tuple(d.code for d in errors)
        if not codes:
            return ArenaDiagnostic(
                codes=(),
                text=(
                    "the candidate compiles; no diagnostic was issued. The failure is "
                    "semantic and the checker did not object to it."
                ),
            )
        skill = self._tax().attribute(codes[0])
        return ArenaDiagnostic(
            codes=codes, text=result.diagnostics.render(), primary_skill_id=skill
        )


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


class EventName(StrEnum):
    TASK_STARTED = "task_started"
    GENERATION_RECEIVED = "generation_received"
    VERIFICATION_COMPLETED = "verification_completed"
    DIAGNOSTIC_ISSUED = "diagnostic_issued"
    REPAIR_REQUESTED = "repair_requested"
    REPAIR_RECEIVED = "repair_received"
    BACKEND_SUPPORT_PROBED = "backend_support_probed"
    EPISODE_SEALED = "episode_sealed"


@dataclass(frozen=True)
class ArenaEvent:
    sequence: int
    name: EventName
    episode_id: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "name": self.name.value,
            "episode_id": self.episode_id,
            "payload": dict(self.payload),
        }


@runtime_checkable
class LedgerSink(Protocol):
    def record(self, event: ArenaEvent) -> None: ...

    def events(self) -> tuple[ArenaEvent, ...]: ...


class InMemoryLedger:
    """Append-only, in-process. A durable ledger substitutes for it through the Protocol."""

    def __init__(self) -> None:
        self._events: list[ArenaEvent] = []

    def record(self, event: ArenaEvent) -> None:
        self._events.append(event)

    def events(self) -> tuple[ArenaEvent, ...]:
        return tuple(self._events)


# ---------------------------------------------------------------------------
# Outcome
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackendSupportReport:
    """What a backend could and could not express. Never a pass/fail for the episode."""

    target: str
    available: bool
    faithful: bool
    unsupported: tuple[str, ...] = ()
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "available": self.available,
            "faithful": self.faithful,
            "unsupported": list(self.unsupported),
            "error": self.error,
        }


@dataclass(frozen=True)
class AttemptRecord:
    """One model output and everything measured about it. Immutable, and kept forever."""

    label: str
    text: str
    exact_hash: str
    verification: ArenaVerification
    tokens: TokenAccount
    latency_s: float | None = None

    @property
    def canonical_hash(self) -> str | None:
        return self.verification.canonical_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "text": self.text,
            "exact_hash": self.exact_hash,
            "canonical_hash": self.canonical_hash,
            "verification": self.verification.to_dict(),
            "tokens": self.tokens.to_dict(),
            "latency_s": self.latency_s,
        }


class ArenaStatus(StrEnum):
    FIRST_ATTEMPT_PASS = "first_attempt_pass"
    REPAIRED_PASS = "repaired_pass"
    REPAIR_FAILED = "repair_failed"
    UNREPAIRABLE_NO_DIAGNOSTIC = "unrepairable_no_diagnostic"
    TRANSPORT_FAILURE = "transport_failure"


@dataclass(frozen=True)
class ArenaConfig:
    """What a run is evidence about, and under which versions it was produced."""

    hypothesis: Hypothesis
    state: SystemState
    episode_prefix: str = "ep"

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, Hypothesis):
            raise TypeError(
                "ArenaConfig.hypothesis must be a Hypothesis member. A repair-arena run "
                "is normally evidence about H3; it must be declared, not assumed."
            )


@dataclass(frozen=True)
class ArenaOutcome:
    """The immutable record of one run. Frozen: an episode is evidence, not a workspace."""

    episode_id: str
    task_id: str
    hypothesis: Hypothesis
    state: SystemState
    model_name: str
    verifier_name: str
    required_verifiers: tuple[str, ...]
    reference_hash: str
    first_attempt: AttemptRecord
    diagnostic: ArenaDiagnostic | None
    repair_attempt: AttemptRecord | None
    backend_reports: tuple[BackendSupportReport, ...]
    status: ArenaStatus
    events: tuple[ArenaEvent, ...]

    # -- derived facts -----------------------------------------------------

    @property
    def repair_attempts(self) -> int:
        return 1 if self.repair_attempt is not None else 0

    @property
    def final_verification(self) -> ArenaVerification:
        return (
            self.repair_attempt.verification
            if self.repair_attempt is not None
            else self.first_attempt.verification
        )

    @property
    def token_cost(self) -> int | Unavailable:
        total = 0
        for attempt in (self.first_attempt, self.repair_attempt):
            if attempt is None:
                continue
            value = attempt.tokens.total
            if isinstance(value, Unavailable):
                return Unavailable(
                    f"the {self.model_name!r} adapter reported no token counts for the "
                    f"{attempt.label} attempt",
                    "an adapter that returns usage counts",
                )
            total += value
        return total

    @property
    def latency(self) -> float | Unavailable:
        values = [
            a.latency_s
            for a in (self.first_attempt, self.repair_attempt)
            if a is not None and a.latency_s is not None
        ]
        if not values:
            return Unavailable(
                f"the {self.model_name!r} adapter measured no latency",
                "an adapter that times its own calls",
            )
        return sum(values)

    def routing_facts(self, near_miss: NearMissKind | None = None) -> RoutingFacts:
        """The facts the memory router consumes.

        ``near_miss`` is supplied by a caller that has classified the defect. The arena
        does not invent one: an unclassified failure is unlabelled, and unlabelled is a
        quarantine condition rather than a guess.
        """
        final = self.final_verification
        attributed: tuple[str, ...] = ()
        if self.diagnostic is not None and self.diagnostic.primary_skill_id:
            attributed = (self.diagnostic.primary_skill_id,)
        return RoutingFacts(
            episode_id=self.episode_id,
            hypothesis=self.hypothesis,
            exact_hash=(
                self.repair_attempt.exact_hash
                if self.repair_attempt is not None
                else self.first_attempt.exact_hash
            ),
            canonical_hash=final.canonical_hash,
            first_attempt_parsed=self.first_attempt.verification.parsed,
            first_attempt_semantic_fidelity=(
                self.first_attempt.verification.outcome is VerifierOutcome.PASS
            ),
            unresolved_obligations=final.unresolved_obligations,
            required_verifiers=self.required_verifiers,
            verifier_results={final.verifier: final.outcome},
            structured_diagnostic_codes=(
                self.diagnostic.codes if self.diagnostic is not None else ()
            ),
            repair_attempts=self.repair_attempts,
            repair_verified=(
                None
                if self.repair_attempt is None
                else self.repair_attempt.verification.outcome is VerifierOutcome.PASS
            ),
            near_miss_kinds=(near_miss,) if near_miss is not None else (),
            attributed_skill_ids=attributed,
            provenance_complete=self.provenance_complete(),
            # A backend probe that cannot express a construct says nothing about this
            # episode: the verdict came from the canonical form, not from the backend.
            semantic_loss=False,
            unsupported_backend_dependency=False,
        )

    def provenance_complete(self) -> bool:
        return bool(
            self.episode_id
            and self.task_id
            and self.model_name
            and self.verifier_name
            and self.reference_hash
            and self.state.fingerprint()
        )

    def route(self, near_miss: NearMissKind | None = None) -> RoutingDecision:
        return route(self.routing_facts(near_miss))

    def replay_projection(self) -> dict[str, Any]:
        """The facts a ledger replay must reproduce. Compared field by field in tests."""
        return {
            "episode_id": self.episode_id,
            "task_id": self.task_id,
            "hypothesis": self.hypothesis.value,
            "state_fingerprint": self.state.fingerprint(),
            "model_name": self.model_name,
            "verifier_name": self.verifier_name,
            "reference_hash": self.reference_hash,
            "first_attempt_exact_hash": self.first_attempt.exact_hash,
            "first_attempt_outcome": self.first_attempt.verification.outcome.value,
            "diagnostic_codes": list(self.diagnostic.codes) if self.diagnostic else [],
            "repair_attempts": self.repair_attempts,
            "repair_exact_hash": (
                self.repair_attempt.exact_hash if self.repair_attempt else None
            ),
            "final_outcome": self.final_verification.outcome.value,
            "status": self.status.value,
        }

    def to_dict(self) -> dict[str, Any]:
        token_cost = self.token_cost
        latency = self.latency
        return {
            "episode_id": self.episode_id,
            "task_id": self.task_id,
            "hypothesis": self.hypothesis.value,
            "hypothesis_claim": self.hypothesis.claim,
            "hypothesis_excluded_claim": self.hypothesis.excluded_claim,
            "state": self.state.to_dict(),
            "state_fingerprint": self.state.fingerprint(),
            "model_name": self.model_name,
            "verifier_name": self.verifier_name,
            "required_verifiers": list(self.required_verifiers),
            "reference_hash": self.reference_hash,
            "first_attempt": self.first_attempt.to_dict(),
            "diagnostic": self.diagnostic.to_dict() if self.diagnostic else None,
            "repair_attempt": (
                self.repair_attempt.to_dict() if self.repair_attempt else None
            ),
            "backend_reports": [b.to_dict() for b in self.backend_reports],
            "status": self.status.value,
            "token_cost": (
                token_cost.to_dict() if isinstance(token_cost, Unavailable) else token_cost
            ),
            "latency": latency.to_dict() if isinstance(latency, Unavailable) else latency,
            "routing": self.route().to_dict(),
            "events": [e.to_dict() for e in self.events],
        }


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


def _probe_backends(task: ArenaTask, source: str) -> tuple[BackendSupportReport, ...]:
    """Render ``source`` through each requested backend. Never affects the verdict."""
    if not task.backend_probes:
        return ()
    from .. import compile_source
    from ..backends import REGISTRY, render

    result = compile_source(source, f"<candidate:{task.task_id}>")
    if not result.ok():
        return tuple(
            BackendSupportReport(t, t in REGISTRY, False, (), "candidate does not compile")
            for t in task.backend_probes
        )
    reports: list[BackendSupportReport] = []
    for target in task.backend_probes:
        if target not in REGISTRY:
            reports.append(
                BackendSupportReport(target, False, False, (), "no backend registered")
            )
            continue
        try:
            rendered = render(target, result.module, result.symbols)
        except Exception as exc:  # a backend failure is a backend fact, not a model fact
            reports.append(
                BackendSupportReport(target, True, False, (), f"{type(exc).__name__}: {exc}")
            )
            continue
        reports.append(
            BackendSupportReport(
                target=target,
                available=True,
                faithful=rendered.faithful,
                unsupported=tuple(u.render() for u in rendered.unsupported),
            )
        )
    return tuple(reports)


def run_arena(
    task: ArenaTask,
    model: ModelBackend,
    config: ArenaConfig,
    *,
    verifier: Verifier | None = None,
    diagnostics: DiagnosticSource | None = None,
    ledger: LedgerSink | None = None,
    episode_id: str | None = None,
) -> ArenaOutcome:
    """Run one task through generate, verify, diagnose, repair once, verify again."""
    checker: Verifier = verifier or CanonicalFormVerifier()
    if checker is model:
        raise ValueError(
            "the verifier and the model are the same object; a model that grades its own "
            "output is not an independent verification"
        )
    diagnoser: DiagnosticSource = diagnostics or CompilerDiagnostics()
    sink: LedgerSink = ledger if ledger is not None else InMemoryLedger()
    ep = episode_id or f"{config.episode_prefix}-{task.task_id}"
    reference_hash = task.reference_hash()

    counter = _Counter()

    def emit(name: EventName, **payload: Any) -> None:
        sink.record(ArenaEvent(counter.next(), name, ep, payload))

    emit(
        EventName.TASK_STARTED,
        task_id=task.task_id,
        hypothesis=config.hypothesis.value,
        state_fingerprint=config.state.fingerprint(),
        model_name=model.name,
        model_live=model.live,
        verifier_name=checker.name,
        required_verifiers=list(task.required_verifiers),
        reference_hash=reference_hash,
    )

    first_response = model.generate(task, task.prompt)
    emit(
        EventName.GENERATION_RECEIVED,
        exact_hash=exact_hash_of(first_response.text),
        error=first_response.error,
        tokens=first_response.tokens.to_dict(),
    )

    if not first_response.ok:
        first = AttemptRecord(
            label="first",
            text=first_response.text,
            exact_hash=exact_hash_of(first_response.text),
            verification=ArenaVerification(
                verifier=checker.name,
                outcome=VerifierOutcome.INCONCLUSIVE,
                parsed=False,
                checked=False,
                canonical_hash=None,
                detail=f"the adapter reported an error: {first_response.error}",
            ),
            tokens=first_response.tokens,
            latency_s=first_response.latency_s,
        )
        emit(
            EventName.EPISODE_SEALED,
            status=ArenaStatus.TRANSPORT_FAILURE.value,
            repair_attempts=0,
            final_outcome=first.verification.outcome.value,
            first_attempt_outcome=first.verification.outcome.value,
            repair_exact_hash=None,
        )
        return ArenaOutcome(
            episode_id=ep,
            task_id=task.task_id,
            hypothesis=config.hypothesis,
            state=config.state,
            model_name=model.name,
            verifier_name=checker.name,
            required_verifiers=task.required_verifiers,
            reference_hash=reference_hash,
            first_attempt=first,
            diagnostic=None,
            repair_attempt=None,
            backend_reports=(),
            status=ArenaStatus.TRANSPORT_FAILURE,
            events=sink.events(),
        )

    first_verification = checker.verify(task, first_response.text)
    emit(EventName.VERIFICATION_COMPLETED, attempt="first", **first_verification.to_dict())
    first = AttemptRecord(
        label="first",
        text=first_response.text,
        exact_hash=exact_hash_of(first_response.text),
        verification=first_verification,
        tokens=first_response.tokens,
        latency_s=first_response.latency_s,
    )

    diagnostic: ArenaDiagnostic | None = None
    repair: AttemptRecord | None = None
    status: ArenaStatus

    if first_verification.outcome is VerifierOutcome.PASS:
        status = ArenaStatus.FIRST_ATTEMPT_PASS
    else:
        diagnostic = diagnoser.diagnose(task, first_response.text)
        emit(EventName.DIAGNOSTIC_ISSUED, **diagnostic.to_dict())
        if not diagnostic.actionable:
            status = ArenaStatus.UNREPAIRABLE_NO_DIAGNOSTIC
        else:
            emit(EventName.REPAIR_REQUESTED, codes=list(diagnostic.codes))
            repair_response = model.repair(task, first_response.text, diagnostic.text)
            emit(
                EventName.REPAIR_RECEIVED,
                exact_hash=exact_hash_of(repair_response.text),
                error=repair_response.error,
                tokens=repair_response.tokens.to_dict(),
            )
            repair_verification = checker.verify(task, repair_response.text)
            emit(
                EventName.VERIFICATION_COMPLETED,
                attempt="repair",
                **repair_verification.to_dict(),
            )
            repair = AttemptRecord(
                label="repair",
                text=repair_response.text,
                exact_hash=exact_hash_of(repair_response.text),
                verification=repair_verification,
                tokens=repair_response.tokens,
                latency_s=repair_response.latency_s,
            )
            status = (
                ArenaStatus.REPAIRED_PASS
                if repair_verification.outcome is VerifierOutcome.PASS
                else ArenaStatus.REPAIR_FAILED
            )

    final_source = repair.text if repair is not None else first.text
    backend_reports = _probe_backends(task, final_source)
    if backend_reports:
        emit(
            EventName.BACKEND_SUPPORT_PROBED,
            reports=[b.to_dict() for b in backend_reports],
            note="backend support is recorded and never changes the verdict",
        )

    emit(
        EventName.EPISODE_SEALED,
        status=status.value,
        repair_attempts=1 if repair is not None else 0,
        final_outcome=(repair or first).verification.outcome.value,
        first_attempt_outcome=first.verification.outcome.value,
        repair_exact_hash=repair.exact_hash if repair else None,
    )

    return ArenaOutcome(
        episode_id=ep,
        task_id=task.task_id,
        hypothesis=config.hypothesis,
        state=config.state,
        model_name=model.name,
        verifier_name=checker.name,
        required_verifiers=task.required_verifiers,
        reference_hash=reference_hash,
        first_attempt=first,
        diagnostic=diagnostic,
        repair_attempt=repair,
        backend_reports=backend_reports,
        status=status,
        events=sink.events(),
    )


class _Counter:
    def __init__(self) -> None:
        self._n = 0

    def next(self) -> int:
        self._n += 1
        return self._n


def replay(events: Sequence[ArenaEvent]) -> dict[str, Any]:
    """Reconstruct the episode's facts from the event stream alone.

    Nothing is read from the outcome object. If this disagrees with
    ``ArenaOutcome.replay_projection`` then the ledger is not a faithful record, which is
    exactly what the test comparing them is for.
    """
    if not events:
        raise ValueError("no events to replay")
    ordered = sorted(events, key=lambda e: e.sequence)
    if [e.sequence for e in ordered] != list(range(1, len(ordered) + 1)):
        raise ValueError("event sequence numbers are not contiguous from 1")
    episode_ids = {e.episode_id for e in ordered}
    if len(episode_ids) != 1:
        raise ValueError(f"events span {len(episode_ids)} episodes; replay one at a time")

    out: dict[str, Any] = {
        "episode_id": ordered[0].episode_id,
        "task_id": None,
        "hypothesis": None,
        "state_fingerprint": None,
        "model_name": None,
        "verifier_name": None,
        "reference_hash": None,
        "first_attempt_exact_hash": None,
        "first_attempt_outcome": None,
        "diagnostic_codes": [],
        "repair_attempts": 0,
        "repair_exact_hash": None,
        "final_outcome": None,
        "status": None,
    }
    for event in ordered:
        p = event.payload
        if event.name is EventName.TASK_STARTED:
            out["task_id"] = p["task_id"]
            out["hypothesis"] = p["hypothesis"]
            out["state_fingerprint"] = p["state_fingerprint"]
            out["model_name"] = p["model_name"]
            out["verifier_name"] = p["verifier_name"]
            out["reference_hash"] = p["reference_hash"]
        elif event.name is EventName.GENERATION_RECEIVED:
            out["first_attempt_exact_hash"] = p["exact_hash"]
        elif event.name is EventName.DIAGNOSTIC_ISSUED:
            out["diagnostic_codes"] = list(p["codes"])
        elif event.name is EventName.REPAIR_RECEIVED:
            out["repair_attempts"] += 1
            out["repair_exact_hash"] = p["exact_hash"]
        elif event.name is EventName.EPISODE_SEALED:
            out["status"] = p["status"]
            out["final_outcome"] = p.get("final_outcome")
            out["first_attempt_outcome"] = p.get("first_attempt_outcome")
    return out
