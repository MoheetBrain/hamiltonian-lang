"""The eight metrics. Recorded separately, and there is no path that merges them.

The finding this module is built around
---------------------------------------
Tam et al. observed a condition with a **0.148% parse-error rate** and a **>38-point**
reasoning gap at the same time. Format adherence and content quality are not the same
measurement, are not correlated in the direction intuition suggests, and a harness that
reports one of them as evidence about the other will conclude that a badly damaging
format is a good one.

So the eight quantities are eight fields. There is no ``score()``, no weighted
combination, and no boolean that stands for "it worked".

``CompileResult.ok()`` is not the parse verdict
-----------------------------------------------
Measured on this compiler: ``HML-T426`` (wrong arity), ``HML-T415`` (wrong role label),
``HML-T403`` (declared-type mismatch) and the ``PValue``/``PosteriorProbability``
epistemic mismatch all **parse and resolve cleanly**, failing only in the type checker;
an unknown identifier parses cleanly and fails in resolution. Reading ``ok()`` as "it
parsed" therefore understates the parse rate and attributes the compiler's type checking
to the candidate surface.

Every field here is derived from
:func:`~hamiltonian_lang.improvement.episodes.classify_stages`, which runs each stage in
its own right. A helper that returns a single boolean is not used and
:func:`assert_no_conflated_verdict` exists to keep it that way.

``None`` means not measured
---------------------------
Never ``False``. A stage the pipeline never reached has no verdict, and recording one as
a failure attaches a defect to a stage that was never given an input.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from hamiltonian_lang.improvement.episodes import (
    Measurement,
    StageOutcome,
    StageStatus,
    TerminalOutcome,
    classify_stages,
    offline_absence,
)

from .core import TokenLedger

__all__ = [
    "EIGHT_METRICS",
    "ProtocolMetrics",
    "ConflatedVerdict",
    "format_adherence",
    "metrics_from_stage_outcome",
    "metrics_for_reply",
    "assert_no_conflated_verdict",
    "aggregate",
    "ArmSummary",
]

#: The eight, named once. Tests read this rather than a hand-maintained list, so adding a
#: ninth metric without deciding where it belongs is not possible by accident.
EIGHT_METRICS: tuple[str, ...] = (
    "format_adherence",
    "parse_success",
    "resolution_success",
    "type_success",
    "semantic_preservation_exact",
    "repair_success",
    "token_cost",
    "latency",
)


class ConflatedVerdict(AssertionError):
    """A single boolean was offered as the verdict for more than one stage."""


_FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\r?\n(.*?)```", re.S)


def format_adherence(reply: str, fence_tags: Sequence[str]) -> bool:
    """Did the reply carry a fenced block with one of the expected tags?

    **Deliberately not** "did the content parse". This is the paper's 0.148% number: the
    surface-level compliance rate, which can be near-perfect while the content inside is
    degraded. An untagged fence is *not* adherence — the scorer's extractor tolerates one
    as a fallback, and measuring the tolerance instead of the behaviour would report a
    compliance rate the model did not earn.
    """
    if not reply:
        return False
    wanted = {t.lower() for t in fence_tags}
    return any((m.group(1) or "").lower() in wanted for m in _FENCE.finditer(reply))


def _tri(status: StageStatus) -> bool | None:
    """PASS -> True, FAIL -> False, NOT_RUN / NOT_APPLICABLE -> None (not measured)."""
    if status is StageStatus.PASS:
        return True
    if status is StageStatus.FAIL:
        return False
    return None


@dataclass(frozen=True)
class ProtocolMetrics:
    """One trial's eight quantities. Eight fields, no aggregate.

    ``token_cost`` is a :class:`~.core.TokenLedger`, not an integer, so the two-stage
    protocol's draft cost cannot be dropped on the way into a metric record.
    """

    #: A fenced block with the expected tag was emitted. Surface compliance only.
    format_adherence: bool | None
    #: The text was in the language. From ``StageOutcome.parse_status``, never ``ok()``.
    parse_success: bool | None
    #: Every name resolved.
    resolution_success: bool | None
    #: The type checker accepted it.
    type_success: bool | None
    #: The **exact** expected canonical object was recovered (hash equality).
    semantic_preservation_exact: bool | None
    #: A single permitted repair produced text that parses. ``None`` when no repair was
    #: attempted -- which is different from a repair that failed.
    repair_success: bool | None
    token_cost: TokenLedger
    latency: Measurement
    terminal: str = ""
    diagnostic_codes: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        # The conflation, refused at the type. A record claiming the text failed to parse
        # while a later stage reported a verdict is the exact shape of the defect: a
        # later stage cannot have run on text that never parsed.
        if self.parse_success is False and (
            self.resolution_success is not None or self.type_success is not None
        ):
            raise ConflatedVerdict(
                "parse_success is False but a later stage carries a verdict. A stage "
                "that never received an input has no verdict; this record was built "
                "from a single boolean rather than from per-stage statuses."
            )
        if self.type_success is True and self.parse_success is not True:
            raise ConflatedVerdict(
                "type_success is True while parse_success is not; the type checker "
                "cannot have accepted text the parser did not"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_adherence": self.format_adherence,
            "parse_success": self.parse_success,
            "resolution_success": self.resolution_success,
            "type_success": self.type_success,
            "semantic_preservation_exact": self.semantic_preservation_exact,
            "repair_success": self.repair_success,
            "token_cost": self.token_cost.to_dict(),
            "latency": self.latency.to_dict(),
            "terminal": self.terminal,
            "diagnostic_codes": list(self.diagnostic_codes),
            "notes": list(self.notes),
            "_warning": (
                "these eight are not combinable. Format adherence near 1.0 alongside "
                "degraded semantic preservation is the documented failure mode, not a "
                "contradiction to be averaged away."
            ),
        }


def metrics_from_stage_outcome(
    outcome: StageOutcome,
    *,
    format_adherent: bool | None,
    token_cost: TokenLedger,
    latency: Measurement | None = None,
    repair_outcome: StageOutcome | None = None,
    notes: Sequence[str] = (),
) -> ProtocolMetrics:
    """Build the eight from per-stage statuses.

    ``repair_outcome`` is the single permitted repair attempt. Its contribution is
    ``parse_status``, not ``compiled``: a repair that fixes a syntax error and leaves a
    type error **did** repair the parse, and counting it as a failure would understate
    the repaired parse rate and blame the surface for the type checker.
    """
    repair = None if repair_outcome is None else _tri(repair_outcome.parse_status)
    return ProtocolMetrics(
        format_adherence=format_adherent,
        parse_success=_tri(outcome.parse_status),
        resolution_success=_tri(outcome.resolution_status),
        type_success=_tri(outcome.type_status),
        semantic_preservation_exact=_tri(outcome.semantic_status),
        repair_success=repair,
        token_cost=token_cost,
        latency=latency or offline_absence("latency"),
        terminal=str(outcome.terminal),
        diagnostic_codes=tuple(outcome.diagnostic_codes),
        notes=tuple(notes),
    )


def metrics_for_reply(
    reply: str,
    encoding: str | None,
    *,
    fence_tags: Sequence[str],
    expected_canonical_hash: str | None,
    token_cost: TokenLedger,
    latency: Measurement | None = None,
    repair_encoding: str | None = None,
    notes: Sequence[str] = (),
) -> ProtocolMetrics:
    """The whole trial, from raw reply text to the eight quantities.

    ``encoding`` is what a candidate's front end extracted and normalised to HML-L1, or
    ``None`` when nothing could be extracted. ``None`` is a parse failure only in the
    sense that there was no text in the language; it is reported with an ``EMPTY``
    diagnostic so it is distinguishable from text that was tried and rejected.
    """
    adherent = format_adherence(reply, fence_tags)
    outcome = classify_stages(
        encoding or "",
        expected_canonical_hash=expected_canonical_hash,
        file="acq0#protocol",
    )
    repair_outcome = (
        None
        if repair_encoding is None
        else classify_stages(
            repair_encoding,
            expected_canonical_hash=expected_canonical_hash,
            file="acq0#repair",
        )
    )
    extra = list(notes)
    if adherent and outcome.terminal is TerminalOutcome.PARSE_FAILED:
        extra.append(
            "format adherence with a parse failure: the reply complied with the "
            "requested shape and the content inside it was not in the language. This is "
            "the pairing the paper reports and it must not be summarised as one number."
        )
    return metrics_from_stage_outcome(
        outcome,
        format_adherent=adherent,
        token_cost=token_cost,
        latency=latency,
        repair_outcome=repair_outcome,
        notes=extra,
    )


def assert_no_conflated_verdict(record: object) -> None:
    """Refuse an object that offers one boolean where the eight belong.

    Used at the boundary where a third-party result object could be handed to this
    package. ``ok`` on such an object means "the whole pipeline accepted this", which is
    a real question with a real answer — it is simply not the parse verdict, and this
    package must never read it as one.
    """
    if isinstance(record, ProtocolMetrics):
        return
    if hasattr(record, "ok") and not hasattr(record, "stages"):
        raise ConflatedVerdict(
            f"{type(record).__name__} exposes ok() and no per-stage record. ok() is a "
            "verdict about the whole pipeline; HML-T426, HML-T415, HML-T403 and the "
            "epistemic-kind mismatch all parse and resolve cleanly and fail only in the "
            "type checker, so reading ok() as the parse verdict understates the parse "
            "rate and blames the surface syntax for the type checker."
        )


# ---------------------------------------------------------------------------
# Aggregation across trials -- still eight, never one
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArmSummary:
    """One protocol arm's aggregate. Every rate carries its own denominator.

    A rate with no denominator cannot be told apart from a rate over one trial, and the
    lexicographic selector refuses to compare arms whose denominators differ in kind.
    """

    protocol: str
    n_trials: int
    #: Trials on which each quantity was measured at all. Rates are over these, not over
    #: ``n_trials``: dividing by the number of attempts would count "not measured" as a
    #: failure.
    denominators: dict[str, int]
    rates: dict[str, float | None]
    total_prompt_tokens: Measurement
    total_completion_tokens: Measurement
    total_latency_s: Measurement
    #: Per-domain exact-preservation rate. The stability key in the selector reads this.
    per_domain_preservation: dict[str, float | None] = field(default_factory=dict)
    #: Set False by the caller when the arm violated a design constraint. Disqualifying,
    #: and it is checked before any number is read.
    constitutionally_valid: bool = True
    constitutional_findings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "n_trials": self.n_trials,
            "denominators": dict(self.denominators),
            "rates": dict(self.rates),
            "total_prompt_tokens": self.total_prompt_tokens.to_dict(),
            "total_completion_tokens": self.total_completion_tokens.to_dict(),
            "total_latency_s": self.total_latency_s.to_dict(),
            "per_domain_preservation": dict(self.per_domain_preservation),
            "constitutionally_valid": self.constitutionally_valid,
            "constitutional_findings": list(self.constitutional_findings),
        }


_BOOLEAN_METRICS = (
    "format_adherence",
    "parse_success",
    "resolution_success",
    "type_success",
    "semantic_preservation_exact",
    "repair_success",
)


def aggregate(
    protocol: str,
    trials: Sequence[ProtocolMetrics],
    *,
    domain_of: dict[int, str] | None = None,
    constitutionally_valid: bool = True,
    constitutional_findings: Sequence[str] = (),
) -> ArmSummary:
    """Rates over what was measured, never over what was attempted.

    Sums of token counts are absent whenever any trial's count is absent — a total over a
    partially measured arm invites comparison with a fully measured one, and the
    comparison would be wrong by an unknown amount rather than by a stated one.
    """
    denominators: dict[str, int] = {}
    rates: dict[str, float | None] = {}
    for name in _BOOLEAN_METRICS:
        observed = [getattr(t, name) for t in trials]
        measured = [v for v in observed if v is not None]
        denominators[name] = len(measured)
        rates[name] = (
            round(sum(1 for v in measured if v) / len(measured), 6) if measured else None
        )

    def _sum(values: Sequence[Measurement], what: str) -> Measurement:
        if not values:
            return Measurement.absent(f"{what}: no trials")
        if any(not v.is_measured for v in values):
            return Measurement.absent(
                f"{what} is absent for at least one trial, so the arm has no total; a "
                "partial total would be compared against a complete one"
            )
        return Measurement.measured(
            sum(v.value for v in values if v.value is not None),
            instrument="provider_usage",
            citation=f"summed across {len(values)} trial ledgers ({what})",
        )

    prompt_totals = [t.token_cost.total_prompt_tokens for t in trials]
    completion_totals = [t.token_cost.total_completion_tokens for t in trials]

    latencies = [t.latency for t in trials]
    if latencies and all(v.is_measured for v in latencies):
        latency_total = Measurement.measured(
            sum(v.value for v in latencies if v.value is not None),
            instrument="time.perf_counter",
        )
    else:
        latency_total = Measurement.absent(
            "latency is absent for at least one trial, so the arm has no total"
        )

    per_domain: dict[str, float | None] = {}
    if domain_of:
        buckets: dict[str, list[bool]] = {}
        for i, t in enumerate(trials):
            d = domain_of.get(i)
            if d is None or t.semantic_preservation_exact is None:
                continue
            buckets.setdefault(d, []).append(bool(t.semantic_preservation_exact))
        per_domain = {
            d: round(sum(1 for v in vs if v) / len(vs), 6) if vs else None
            for d, vs in sorted(buckets.items())
        }

    return ArmSummary(
        protocol=protocol,
        n_trials=len(trials),
        denominators=denominators,
        rates=rates,
        total_prompt_tokens=_sum(prompt_totals, "prompt tokens"),
        total_completion_tokens=_sum(completion_totals, "completion tokens"),
        total_latency_s=latency_total,
        per_domain_preservation=per_domain,
        constitutionally_valid=constitutionally_valid,
        constitutional_findings=tuple(constitutional_findings),
    )
