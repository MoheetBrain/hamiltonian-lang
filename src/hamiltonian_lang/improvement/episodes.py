"""The episode — Phase 6, the atomic unit of the improvement record.

An episode is one attempt at one task under one experimental condition. It is immutable,
versioned, and it is written so that somebody re-reading it in a year can tell what went
right, what went wrong, and — the part that is easy to lose — *which claim the evidence
actually supports*.

There is exactly one hypothesis type
------------------------------------
``HypothesisId`` **is** :class:`~hamiltonian_lang.improvement.state.Hypothesis` — the
same object, re-exported under the name this module has always used. It used to be a
second, parallel enumeration, and two enumerations of the same concept is how a
quarantined row eventually reaches a store it does not belong in: the two drift, one
grows a member the other lacks, and a conversion at the boundary silently picks a
default. The old ``NONE`` member is now ``EXCLUDED``, because ``NONE`` reads as "not
recorded yet" — a default — rather than "deliberately outside the scientific record".

Why ``hypothesis_id`` is mandatory
-----------------------------------
This project tests three hypotheses that can come apart, behind one prerequisite:

**ACQ0** — the model can *express* a frozen canonical object in a candidate surface.
**H1** — a Hamiltonian *input* representation improves the answer.
**H2** — a Hamiltonian *reasoning workspace* improves the answer.
**H3** — verifier-guided repair improves the *verified* answer.

ACQ0 is a prerequisite, not a result, and its repair mechanism is ``ACQ0_REPAIR`` rather
than H3: repairing a malformed encoding and repairing a wrong argument are different
acts. An ACQ0 episode therefore may carry a repair and can still never be aggregated
with an H3 episode, because :func:`assert_single_hypothesis` refuses to mix them.

H3 can win while H1 and H2 lose. A repair loop that fixes broken output is a result about
verifier-guided reasoning; it says nothing about whether the representation helped, and
reporting it as if it did would be the single most damaging error this record could make.
So the hypothesis is a required field, the condition metadata that reconstructs the
contrast travels with it, and the schema makes the confounded combinations
*unconstructible*:

* an H1 or H2 episode may not carry verifier feedback — that would confound the
  representation with the repair loop;
* an H1 or H2 episode may not carry a repair — same reason, and it is why a repair
  episode is distinguishable from an H1/H2 episode by construction rather than by
  convention;
* an H1 episode may not require a Hamiltonian derivation — that is H2's manipulation;
* an H2 episode must require one.

:func:`assert_single_hypothesis` refuses to aggregate across differing ``hypothesis_id``
values, so a mixed pool cannot be averaged into a single headline number by accident.

**What this rules out, deliberately.** A factorial design that turns the repair loop on in
*both* arms of the H1 contrast would also be interpretable — repair is held constant, so a
difference is still attributable to the representation. This schema forbids it: an H1 or
H2 episode may not carry verifier feedback at all. The trade is intentional. A schema that
permits the confounded and the factorial design cannot tell them apart from the record
alone a year later, and that is the property being protected. Running the factorial design
requires a schema change and a decision record, which is the correct amount of friction.

Why the stage of a failure is recorded, not inferred
-----------------------------------------------------
``CompileResult.ok()`` is a verdict about the **whole pipeline**, and it was being read
as "the output parsed". It is not. Measured on this compiler: ``HML-T426`` (wrong
arity), ``HML-T415`` (wrong role label) and ``HML-T403`` (declared-type mismatch) all
**parse cleanly and resolve cleanly**, failing only in the type checker. A harness that
reports ``ok()`` as the parse verdict therefore understates first-attempt parse rate and
blames the surface syntax for the compiler's type checking — which would corrupt ACQ0's
headline number in the direction that most flatters a rejection of the syntax.

:class:`StageOutcome` records each stage's verdict separately, and
:func:`classify_stages` obtains them by *running each stage in its own right* rather
than inferring them from a single boolean.

Why token counts are not integers
----------------------------------
Every measured quantity is a :class:`Measurement`, and a :class:`Measurement` knows
whether it was measured or is simply absent. ``prompt_tokens=1200`` will not type-check
into an episode; ``Measurement.measured(1200, instrument=...)`` requires naming an
instrument from :data:`KNOWN_INSTRUMENTS`, and an instrument that is not installed cannot
be named. Offline, the honest value is :meth:`Measurement.absent`, and the record says so
in the field rather than leaving a plausible-looking number behind.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from .diagnostics import DIAGNOSTIC_ADAPTER_VERSION, StructuredDiagnostic
from .events import canonical_blob, sha256_hex
from .memory import MemoryStoreKind, QuarantineEligibilityError, RoutingDecision
from .state import REPAIR_MECHANISM, Hypothesis
from .verification import (
    VERIFICATION_PROTOCOL_VERSION,
    Counterexample,
    VerificationResult,
    VerifierStatus,
)

__all__ = [
    "EPISODE_SCHEMA_VERSION",
    "HypothesisId",
    "HYPOTHESIS_CLAIMS",
    "REPAIR_MECHANISM",
    "InputRepresentation",
    "Condition",
    "StageStatus",
    "TerminalOutcome",
    "StageOutcome",
    "classify_stages",
    "Verdict",
    "TERMINAL_VERDICTS",
    "ConfidenceTier",
    "Provenance",
    "Measurement",
    "KNOWN_INSTRUMENTS",
    "instrument_available",
    "offline_absence",
    "output_hash",
    "FabricatedMeasurement",
    "HypothesisMixing",
    "ConfoundedCondition",
    "TrainingEligibility",
    "TrainingEligibilityOverride",
    "Episode",
    "assert_single_hypothesis",
    "group_by_contrast",
]

#: Bumped whenever a field is added, removed or changes meaning. Old episodes keep the
#: version they were written under.
EPISODE_SCHEMA_VERSION = "hml-episode-1.0.0"


# ---------------------------------------------------------------------------
# Hypotheses and conditions
# ---------------------------------------------------------------------------


#: **The** hypothesis type, not a second one. Kept as a name because this module's
#: field is called ``hypothesis_id`` and reads better with it; ``HypothesisId is
#: Hypothesis`` is true, and a test asserts it so the two can never diverge again.
HypothesisId = Hypothesis


#: What each hypothesis asserts, and — the part that decays fastest from memory — what a
#: win does **not** license. Written into the record so a future reader does not have to
#: reconstruct it from a commit message. Sourced from the canonical type so there is one
#: wording, not two.
HYPOTHESIS_CLAIMS: Mapping[Hypothesis, str] = {
    h: f"{h.claim} {h.excluded_claim}" for h in Hypothesis
}


class InputRepresentation(StrEnum):
    """What the model was given as the problem statement."""

    HAMILTONIAN = "hamiltonian"
    ENGLISH = "english"
    #: Both were supplied. Recorded as its own value because it is neither arm of the H1
    #: contrast and must not be silently counted as one.
    BOTH = "both"


class ConfoundedCondition(ValueError):
    """The condition and the hypothesis cannot both be true of one episode."""


@dataclass(frozen=True)
class Condition:
    """The experimental condition, in the three dimensions that define the contrasts.

    These three flags are sufficient to reconstruct which arm of which contrast an
    episode belongs to, without consulting an external run manifest that may not survive
    a year.
    """

    #: H1's manipulation.
    input_representation: InputRepresentation
    #: H2's manipulation: was a Hamiltonian derivation required as the workspace?
    derivation_required: bool
    #: H3's manipulation: was verifier feedback supplied back to the model?
    verifier_feedback_supplied: bool

    def contrast_key(self) -> tuple[str, bool, bool]:
        return (
            str(self.input_representation),
            self.derivation_required,
            self.verifier_feedback_supplied,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_representation": str(self.input_representation),
            "derivation_required": self.derivation_required,
            "verifier_feedback_supplied": self.verifier_feedback_supplied,
        }

    def check_against(self, hypothesis: Hypothesis) -> None:
        """Refuse a condition that confounds the hypothesis it claims to test."""
        if hypothesis is Hypothesis.EXCLUDED:
            # An engineering episode asserts nothing, so there is no contrast to
            # confound. It is also never aggregated, which is what makes this safe.
            return
        if hypothesis is Hypothesis.ACQ0:
            # ACQ0's manipulation is the candidate surface. Verifier feedback is
            # legitimate here -- that arm is ACQ0_REPAIR -- but requiring a Hamiltonian
            # derivation is H2's manipulation and would make the episode ambiguous
            # between the prerequisite and the workspace hypothesis.
            if self.derivation_required:
                raise ConfoundedCondition(
                    "ACQ0 asks whether the model can express a frozen object in a "
                    "candidate surface. Requiring a Hamiltonian derivation is H2's "
                    "manipulation; an episode carrying both is evidence about neither."
                )
            return
        if hypothesis in (Hypothesis.H1, Hypothesis.H2):
            if self.verifier_feedback_supplied:
                raise ConfoundedCondition(
                    f"{hypothesis} tests the representation, but verifier feedback was "
                    f"supplied; any gain would be confounded with H3. Record this as an "
                    f"H3 episode, or run it without feedback."
                )
        if hypothesis is HypothesisId.H1 and self.derivation_required:
            raise ConfoundedCondition(
                "H1 tests the input representation; requiring a Hamiltonian derivation "
                "is H2's manipulation and would confound the two."
            )
        if hypothesis is HypothesisId.H2 and not self.derivation_required:
            raise ConfoundedCondition(
                "H2 tests the Hamiltonian derivation as a reasoning workspace; an "
                "episode that did not require one is not evidence about H2."
            )
        if hypothesis is HypothesisId.H3 and not self.verifier_feedback_supplied:
            raise ConfoundedCondition(
                "H3 tests verifier-guided repair; an episode with no verifier feedback "
                "is not evidence about H3."
            )


# ---------------------------------------------------------------------------
# Per-stage outcomes — what actually failed, and where
# ---------------------------------------------------------------------------


class StageStatus(StrEnum):
    """One compiler stage's verdict.

    ``NOT_RUN`` and ``NOT_APPLICABLE`` are deliberately different from ``FAIL``. A stage
    the pipeline never reached has *no* verdict — counting it as a failure would attach
    a defect to a stage that was never given the input — and a stage that does not apply
    to this trial (no reference object, no verifier) was never in question at all.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class TerminalOutcome(StrEnum):
    """How far one attempt got. Exactly one applies.

    The ordering is the pipeline's. Each value names the **last stage that succeeded**
    together with the stage that stopped it, so a reader never has to guess whether
    "failed" meant the surface or the semantics.
    """

    #: The text is not in the language. This — and only this — is a parse failure.
    PARSE_FAILED = "PARSE_FAILED"
    #: Grammatical, but a name does not resolve. An unknown identifier is a *scope*
    #: defect, not a syntax defect; the model wrote well-formed text about the wrong
    #: thing.
    PARSE_PASSED_RESOLUTION_FAILED = "PARSE_PASSED_RESOLUTION_FAILED"
    #: Grammatical and fully resolved, rejected by the type system. Wrong arity
    #: (HML-T426), wrong role label (HML-T415), declared-type mismatch (HML-T403) and
    #: epistemic-kind mismatch all land here. **None of them is a parse failure.**
    RESOLVED_TYPE_FAILED = "RESOLVED_TYPE_FAILED"
    #: Compiles, but the translation lost meaning. Not a verdict about the candidate.
    TYPED_SEMANTIC_LOSS = "TYPED_SEMANTIC_LOSS"
    #: Compiles and recovers the exact expected canonical object.
    SEMANTICALLY_PRESERVED = "SEMANTICALLY_PRESERVED"
    #: Preserved *and* every required verifier reported a pass.
    VERIFIED = "VERIFIED"
    #: Nothing could be determined — a transport failure, a crash, an absent oracle.
    #: Never a pass and never a failure.
    INCONCLUSIVE = "INCONCLUSIVE"
    #: The machinery required to decide does not exist for this input. Absence of a
    #: measurement, which is not a failed measurement.
    UNSUPPORTED = "UNSUPPORTED"


#: Outcomes in which the text was grammatical. The predicate ACQ0's first-attempt parse
#: rate counts, kept as data so no call site re-derives it and gets it wrong.
PARSED_OUTCOMES: frozenset[TerminalOutcome] = frozenset(
    {
        TerminalOutcome.PARSE_PASSED_RESOLUTION_FAILED,
        TerminalOutcome.RESOLVED_TYPE_FAILED,
        TerminalOutcome.TYPED_SEMANTIC_LOSS,
        TerminalOutcome.SEMANTICALLY_PRESERVED,
        TerminalOutcome.VERIFIED,
    }
)


@dataclass(frozen=True)
class StageOutcome:
    """Every stage's verdict for one attempt, plus the single terminal classification.

    The five statuses are not redundant with ``terminal``: ``terminal`` says where the
    attempt stopped, the statuses say what each stage reported on the way, and a
    downstream metric that needs "did this parse" must read ``parse_status`` rather than
    inferring it from an overall boolean. That inference is the defect this type exists
    to remove.
    """

    parse_status: StageStatus
    resolution_status: StageStatus
    type_status: StageStatus
    semantic_status: StageStatus
    verification_status: StageStatus
    terminal: TerminalOutcome
    diagnostic_codes: tuple[str, ...] = ()
    canonical_hash: str | None = None
    #: Proof obligations the checker left open. Only meaningful once the type stage
    #: passed; zero elsewhere because no obligation was ever generated.
    unresolved_obligations: int = 0
    detail: str = ""

    def __post_init__(self) -> None:
        if (self.terminal in PARSED_OUTCOMES) != (self.parse_status is StageStatus.PASS):
            raise ValueError(
                f"terminal {self.terminal} and parse_status {self.parse_status} "
                "disagree about whether the text parsed; that disagreement is exactly "
                "the confusion this type exists to prevent"
            )

    @property
    def parsed(self) -> bool:
        """Whether the text was in the language. **Not** whether it compiled."""
        return self.parse_status is StageStatus.PASS

    @property
    def compiled(self) -> bool:
        """Whether every compiler stage passed. A different question from ``parsed``."""
        return (
            self.parse_status is StageStatus.PASS
            and self.resolution_status is StageStatus.PASS
            and self.type_status is StageStatus.PASS
        )

    @property
    def preserved(self) -> bool:
        """Whether the exact expected canonical object was recovered."""
        return self.semantic_status is StageStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "parse_status": str(self.parse_status),
            "resolution_status": str(self.resolution_status),
            "type_status": str(self.type_status),
            "semantic_status": str(self.semantic_status),
            "verification_status": str(self.verification_status),
            "terminal": str(self.terminal),
            "diagnostic_codes": list(self.diagnostic_codes),
            "canonical_hash": self.canonical_hash,
            "unresolved_obligations": self.unresolved_obligations,
            "detail": self.detail,
        }


def _inconclusive(detail: str, codes: tuple[str, ...] = ()) -> StageOutcome:
    return StageOutcome(
        parse_status=StageStatus.NOT_RUN,
        resolution_status=StageStatus.NOT_RUN,
        type_status=StageStatus.NOT_RUN,
        semantic_status=StageStatus.NOT_RUN,
        verification_status=StageStatus.NOT_RUN,
        terminal=TerminalOutcome.INCONCLUSIVE,
        diagnostic_codes=codes,
        detail=detail,
    )


def classify_stages(
    source: str,
    *,
    expected_canonical_hash: str | None = None,
    file: str = "<candidate>",
    verifier_passed: bool | None = None,
) -> StageOutcome:
    """Run each compiler stage in its own right and report all five verdicts.

    The pipeline is re-walked here rather than read off ``CompileResult.ok()`` because
    ``ok()`` is one boolean over four stages. Measured on this compiler, ``HML-T426``,
    ``HML-T415`` and ``HML-T403`` all parse and resolve cleanly; a caller that treated
    ``ok()`` as the parse verdict would record three type defects as syntax defects.

    ``expected_canonical_hash`` is the reference object. Without one the semantic stage
    is ``NOT_APPLICABLE`` — there was no reference to preserve — and the attempt
    terminates at ``SEMANTICALLY_PRESERVED`` no higher than the compiler can justify.
    ``verifier_passed`` is likewise the caller's; this function runs no verifier.

    Each stage is driven directly, with its **own** diagnostic bag, rather than by
    calling ``compile_source`` after the fact. Two reasons, and both matter: a shared bag
    cannot say which stage raised what, and re-entering ``compile_source`` would parse
    and resolve a second time — this is the per-trial hot path of a study that scores
    thousands of trials across four candidate surfaces.
    """
    from ..backends.canonical import content_hash
    from ..diagnostics import DiagnosticBag
    from ..parser import parse as _parse
    from ..semantics import resolve as _resolve
    from ..type_system import check as _check

    if not (source or "").strip():
        return StageOutcome(
            parse_status=StageStatus.FAIL,
            resolution_status=StageStatus.NOT_RUN,
            type_status=StageStatus.NOT_RUN,
            semantic_status=StageStatus.NOT_RUN,
            verification_status=StageStatus.NOT_RUN,
            terminal=TerminalOutcome.PARSE_FAILED,
            diagnostic_codes=("EMPTY",),
            detail="the attempt produced no text to parse",
        )

    try:
        module, parse_bag = _parse(source, file)
    except Exception as exc:  # noqa: BLE001 -- a crash decides nothing
        return _inconclusive(
            f"the parser raised {type(exc).__name__}; the stage has no verdict",
            (f"CRASH:{type(exc).__name__}",),
        )
    parse_codes = tuple(d.code for d in parse_bag.errors)
    if parse_codes:
        return StageOutcome(
            parse_status=StageStatus.FAIL,
            resolution_status=StageStatus.NOT_RUN,
            type_status=StageStatus.NOT_RUN,
            semantic_status=StageStatus.NOT_RUN,
            verification_status=StageStatus.NOT_RUN,
            terminal=TerminalOutcome.PARSE_FAILED,
            diagnostic_codes=parse_codes,
            detail="the text is not in the language",
        )

    resolve_bag = DiagnosticBag(source, file)
    try:
        symbols = _resolve(module, resolve_bag)
    except Exception as exc:  # noqa: BLE001
        return _inconclusive(
            f"resolution raised {type(exc).__name__} on text that parsed",
            (f"CRASH:{type(exc).__name__}",),
        )
    resolve_codes = tuple(d.code for d in resolve_bag.errors)
    if resolve_codes:
        return StageOutcome(
            parse_status=StageStatus.PASS,
            resolution_status=StageStatus.FAIL,
            type_status=StageStatus.NOT_RUN,
            semantic_status=StageStatus.NOT_RUN,
            verification_status=StageStatus.NOT_RUN,
            terminal=TerminalOutcome.PARSE_PASSED_RESOLUTION_FAILED,
            diagnostic_codes=resolve_codes,
            detail="grammatical, but a name does not resolve; a scope defect, not syntax",
        )

    type_bag = DiagnosticBag(source, file)
    try:
        checked = _check(module, symbols, type_bag)
    except Exception as exc:  # noqa: BLE001
        return _inconclusive(
            f"type checking raised {type(exc).__name__} on text that resolved",
            (f"CRASH:{type(exc).__name__}",),
        )
    type_codes = tuple(d.code for d in type_bag.errors)
    if type_codes:
        return StageOutcome(
            parse_status=StageStatus.PASS,
            resolution_status=StageStatus.PASS,
            type_status=StageStatus.FAIL,
            semantic_status=StageStatus.NOT_RUN,
            verification_status=StageStatus.NOT_RUN,
            terminal=TerminalOutcome.RESOLVED_TYPE_FAILED,
            diagnostic_codes=type_codes,
            detail=(
                "parsed and resolved; rejected by the type system. This is NOT a parse "
                "failure and must not be counted as one."
            ),
        )

    obligations = len(checked.obligations)
    try:
        canonical_hash = content_hash(module)
    except Exception as exc:  # noqa: BLE001
        return _inconclusive(
            f"canonicalisation raised {type(exc).__name__} on a module that compiled",
            (f"CRASH:{type(exc).__name__}",),
        )
    if expected_canonical_hash is None:
        semantic = StageStatus.NOT_APPLICABLE
        terminal = TerminalOutcome.SEMANTICALLY_PRESERVED
        detail = "compiles; no reference object was supplied, so nothing was compared"
    elif canonical_hash == expected_canonical_hash:
        semantic = StageStatus.PASS
        terminal = TerminalOutcome.SEMANTICALLY_PRESERVED
        detail = "compiles and recovers the exact expected canonical object"
    else:
        semantic = StageStatus.FAIL
        terminal = TerminalOutcome.TYPED_SEMANTIC_LOSS
        detail = (
            "compiles, but its canonical form differs from the reference: the surface "
            "was written well and the meaning is not the one asked for"
        )

    if verifier_passed is None:
        verification = StageStatus.NOT_RUN
    elif verifier_passed:
        verification = StageStatus.PASS
        if semantic is not StageStatus.FAIL:
            terminal = TerminalOutcome.VERIFIED
    else:
        verification = StageStatus.FAIL

    return StageOutcome(
        parse_status=StageStatus.PASS,
        resolution_status=StageStatus.PASS,
        type_status=StageStatus.PASS,
        semantic_status=semantic,
        verification_status=verification,
        terminal=terminal,
        diagnostic_codes=type_codes,
        canonical_hash=canonical_hash,
        unresolved_obligations=obligations,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Verdicts and confidence
# ---------------------------------------------------------------------------


class Verdict(StrEnum):
    """The six terminal verdicts. Each is a different fact about the world."""

    VERIFIED = "VERIFIED"
    DISPROVED = "DISPROVED"
    INVALID = "INVALID"
    UNSUPPORTED = "UNSUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    SEMANTIC_LOSS = "SEMANTIC_LOSS"


TERMINAL_VERDICTS: frozenset[Verdict] = frozenset(Verdict)


class ConfidenceTier(StrEnum):
    """How much weight the verdict can bear.

    Ordered from strongest to weakest. ``EXECUTED_ONLY`` exists because running a
    generated module is genuinely informative and genuinely not a proof of equivalence,
    and collapsing it into either neighbour would misstate what happened.
    """

    MACHINE_VERIFIED = "machine_verified"
    MACHINE_CHECKED = "machine_checked"
    EXECUTED_ONLY = "executed_only"
    UNVERIFIED = "unverified"


# ---------------------------------------------------------------------------
# Measurements that cannot be faked
# ---------------------------------------------------------------------------

#: Instruments this repository knows how to use. A measurement must name one of these,
#: and the named instrument must actually be available, so a plausible-looking number
#: cannot be dropped into a token field and pass as measured. Adding an entry here is a
#: deliberate, reviewable act.
KNOWN_INSTRUMENTS: frozenset[str] = frozenset(
    {
        "tiktoken",            # optional extra; counts tokens for a named encoding
        "provider_usage",      # a provider's own usage block from a real API response
        "time.perf_counter",   # wall-clock latency around a call that really happened
    }
)

#: Instruments whose presence cannot be probed from inside this process. They must cite
#: the artefact the number came from instead; the citation is the evidence.
_UNPROBEABLE_INSTRUMENTS: frozenset[str] = frozenset({"provider_usage"})


def instrument_available(name: str) -> bool:
    """Whether ``name`` can produce a measurement on this machine right now.

    ``tiktoken`` is an optional extra and is **not** installed here, so naming it is
    refused. That refusal is the point: an uninstalled tokeniser cannot have counted
    anything.
    """
    if name == "tiktoken":
        return importlib.util.find_spec("tiktoken") is not None
    if name == "time.perf_counter":
        return True
    return name in _UNPROBEABLE_INSTRUMENTS


class Provenance(StrEnum):
    MEASURED = "measured"
    ABSENT = "absent"


class FabricatedMeasurement(ValueError):
    """A value was presented as measured without an instrument that could measure it."""


@dataclass(frozen=True)
class Measurement:
    """A number, or an explicit statement that there is no number.

    The two constructors are the whole point:

    * :meth:`measured` requires an instrument from :data:`KNOWN_INSTRUMENTS` that is
      actually available on this machine;
    * :meth:`absent` requires a reason and forbids a value.

    There is no third path, and the raw constructor enforces the same rules, so an
    invented token count cannot enter an episode wearing the ``measured`` label.
    """

    value: int | float | None
    provenance: Provenance
    instrument: str = ""
    #: Why the measurement is absent, or -- for an instrument whose presence cannot be
    #: probed -- the artefact the number was read from.
    reason: str = ""

    def __post_init__(self) -> None:
        if self.provenance is Provenance.MEASURED:
            if self.value is None:
                raise FabricatedMeasurement(
                    "a measured quantity must have a value; use Measurement.absent() "
                    "when there is none"
                )
            if self.instrument not in KNOWN_INSTRUMENTS:
                raise FabricatedMeasurement(
                    f"instrument {self.instrument!r} is not in KNOWN_INSTRUMENTS "
                    f"{sorted(KNOWN_INSTRUMENTS)}; a number without an instrument that "
                    f"could have produced it is not a measurement"
                )
            if not instrument_available(self.instrument):
                raise FabricatedMeasurement(
                    f"instrument {self.instrument!r} is not available in this "
                    f"environment; it cannot have produced {self.value!r}"
                )
            if self.instrument in _UNPROBEABLE_INSTRUMENTS and not self.reason.strip():
                raise FabricatedMeasurement(
                    f"{self.instrument!r} cannot be probed from here, so the measurement "
                    f"must cite the artefact it was read from; the citation is the only "
                    f"evidence that a real call happened"
                )
            if isinstance(self.value, bool) or self.value < 0:
                raise FabricatedMeasurement(
                    f"a measured count or duration cannot be {self.value!r}"
                )
        else:
            if self.value is not None:
                raise FabricatedMeasurement(
                    f"an absent measurement cannot carry the value {self.value!r}"
                )
            if not self.reason.strip():
                raise FabricatedMeasurement(
                    "an absent measurement must say why it is absent; a silent None is "
                    "indistinguishable from a value nobody looked for"
                )

    @classmethod
    def measured(
        cls, value: int | float, *, instrument: str, citation: str = ""
    ) -> Measurement:
        return cls(
            value=value,
            provenance=Provenance.MEASURED,
            instrument=instrument,
            reason=citation,
        )

    @classmethod
    def absent(cls, reason: str) -> Measurement:
        return cls(value=None, provenance=Provenance.ABSENT, reason=reason)

    @property
    def is_measured(self) -> bool:
        return self.provenance is Provenance.MEASURED

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "provenance": str(self.provenance),
            "instrument": self.instrument,
            "reason": self.reason,
        }


#: The standard absence for an offline run. Used so the phrasing is identical everywhere
#: and a reader can grep for it.
def offline_absence(what: str) -> Measurement:
    return Measurement.absent(
        f"{what} was not measured: this episode was produced offline, with no model "
        f"provider call and no token-counting instrument installed"
    )


# ---------------------------------------------------------------------------
# The episode
# ---------------------------------------------------------------------------


class HypothesisMixing(ValueError):
    """An attempt to aggregate episodes that test different hypotheses."""


class TrainingEligibilityOverride(TypeError):
    """A caller tried to set ``training_eligible`` on an episode directly."""


@dataclass(frozen=True)
class TrainingEligibility:
    """The router's decision, copied verbatim onto the episode with its evidence.

    Constructed only from a :class:`~.memory.RoutingDecision`. There is no path that
    builds one from a bare boolean, which is what makes "the router is authoritative" a
    property of the type rather than a rule someone has to remember.
    """

    eligible: bool
    store: str
    reasons: tuple[str, ...]
    quarantine_reasons: tuple[str, ...] = ()
    decided_by: str = ""
    policy_rationale: str = ""

    def __post_init__(self) -> None:
        if self.eligible and self.store == MemoryStoreKind.QUARANTINE.value:
            raise QuarantineEligibilityError(
                "a quarantined episode is never training-eligible, under any flag"
            )
        if self.eligible and self.quarantine_reasons:
            raise QuarantineEligibilityError(
                f"training-eligible with quarantine reasons {list(self.quarantine_reasons)}"
            )
        if not self.decided_by.strip():
            raise ValueError(
                "a training-eligibility decision must name the authority that made it; "
                "an unattributed decision cannot be checked against the rules in force"
            )

    @classmethod
    def from_decision(cls, decision: RoutingDecision) -> TrainingEligibility:
        return cls(
            eligible=decision.training_eligible,
            store=decision.store.value,
            reasons=tuple(decision.reasons),
            quarantine_reasons=tuple(r.value for r in decision.quarantine_reasons),
            decided_by=decision.decided_by,
            policy_rationale=decision.policy.rationale,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "store": self.store,
            "reasons": list(self.reasons),
            "quarantine_reasons": list(self.quarantine_reasons),
            "decided_by": self.decided_by,
            "policy_rationale": self.policy_rationale,
        }


@dataclass(frozen=True)
class Episode:
    """One immutable attempt at one task.

    **A repair never overwrites the initial attempt.** ``initial_output`` and
    ``initial_output_hash`` are set once; :meth:`with_repair` returns a *new* episode with
    the repair fields filled and copies the initial fields verbatim, refusing to run if
    the caller tries to alter them. The full sequence of attempts lives in the event
    ledger, keyed by ``episode_id``.

    **Training eligibility is not a field here.** ``training_eligible`` is a read-only
    property over :attr:`eligibility`, which can only be built from a routing decision.
    Passing ``training_eligible=`` to the constructor raises
    :class:`TrainingEligibilityOverride` rather than being quietly accepted, because the
    combination this class must make impossible is "the router said quarantine and the
    episode says trainable".
    """

    # -- identity ----------------------------------------------------------------
    episode_id: str
    experiment_id: str
    task_id: str
    canonical_object_id: str

    # -- what claim this episode bears on ----------------------------------------
    hypothesis_id: HypothesisId
    condition: Condition

    # -- provenance of the software that produced it ------------------------------
    language_version: str
    compiler_version: str
    #: ``None`` when no model was involved. Never a placeholder string.
    model_version: str | None = None
    diagnostic_version: str = DIAGNOSTIC_ADAPTER_VERSION
    verifier_versions: Mapping[str, str] = field(default_factory=dict)
    schema_version: str = EPISODE_SCHEMA_VERSION

    # -- task framing -------------------------------------------------------------
    skill_ids: tuple[str, ...] = ()
    dataset_split: str = "unassigned"

    # -- the initial attempt, never overwritten ------------------------------------
    input_representation: InputRepresentation = InputRepresentation.ENGLISH
    initial_output: str = ""
    initial_output_hash: str = ""
    parsed_object_id: str | None = None

    # -- what the machinery said ---------------------------------------------------
    diagnostics: tuple[StructuredDiagnostic, ...] = ()
    verifier_results: tuple[VerificationResult, ...] = ()
    counterexamples: tuple[Counterexample, ...] = ()

    # -- the repair, kept separately -----------------------------------------------
    repair_output: str | None = None
    repair_output_hash: str | None = None
    repaired_object_id: str | None = None
    #: What changed semantically between the initial object and the repaired one.
    #: ``None`` when no repair was attempted; ``"none"`` when a repair changed nothing.
    semantic_edit: str | None = None
    repair_count: int = 0

    # -- per-stage outcomes ------------------------------------------------------------
    #: Where the first attempt stopped, stage by stage. ``None`` when nothing was
    #: classified; that is an absence, and no rate may count it.
    initial_stages: StageOutcome | None = None
    #: The same for the repaired attempt, when there was one.
    repair_stages: StageOutcome | None = None

    # -- outcome --------------------------------------------------------------------
    final_answer: str | None = None
    final_verdict: Verdict = Verdict.INCONCLUSIVE
    confidence_tier: ConfidenceTier = ConfidenceTier.UNVERIFIED
    #: The router's decision, verbatim. **Not** a caller's opinion: ``training_eligible``
    #: is a read-only property derived from this, and passing the keyword raises.
    eligibility: TrainingEligibility | None = None
    exclusion_reason: str | None = None

    # -- measured cost ---------------------------------------------------------------
    prompt_tokens: Measurement = field(
        default_factory=lambda: offline_absence("prompt token count")
    )
    completion_tokens: Measurement = field(
        default_factory=lambda: offline_absence("completion token count")
    )
    latency_ms: Measurement = field(
        default_factory=lambda: offline_absence("latency")
    )

    def __post_init__(self) -> None:
        for name in ("episode_id", "experiment_id", "task_id", "canonical_object_id"):
            if not getattr(self, name):
                raise ValueError(f"{name} is required; an unattributed episode is not a record")
        if not self.language_version or not self.compiler_version:
            raise ValueError(
                "language_version and compiler_version are required: a result whose "
                "compiler is unknown cannot be reproduced"
            )

        self.condition.check_against(self.hypothesis_id)

        if self.condition.input_representation is not self.input_representation:
            raise ValueError(
                f"input_representation {self.input_representation} disagrees with the "
                f"condition's {self.condition.input_representation}; the contrast this "
                f"episode belongs to would be ambiguous"
            )

        for name in ("prompt_tokens", "completion_tokens", "latency_ms"):
            value = getattr(self, name)
            if not isinstance(value, Measurement):
                raise TypeError(
                    f"{name} must be a Measurement, not {type(value).__name__}. A bare "
                    f"number carries no evidence that anything was measured."
                )

        self._check_repair_fields()
        self._check_outcome_fields()

    # -- invariants ----------------------------------------------------------------

    def _check_repair_fields(self) -> None:
        repaired = self.repair_output is not None
        if repaired != (self.repair_count > 0):
            raise ValueError(
                f"repair_count is {self.repair_count} but repair_output is "
                f"{'set' if repaired else 'absent'}; the two must agree"
            )
        if repaired and self.repair_output_hash != _hash_text(self.repair_output or ""):
            raise ValueError("repair_output_hash does not commit to repair_output")
        if self.initial_output and self.initial_output_hash != _hash_text(self.initial_output):
            raise ValueError("initial_output_hash does not commit to initial_output")
        if repaired and self.hypothesis_id in (HypothesisId.H1, HypothesisId.H2):
            # This is the structural guarantee, not a convention: an H1/H2 episode with a
            # repair cannot be constructed, so a repair result can never be counted as a
            # representation result.
            raise ConfoundedCondition(
                f"{self.hypothesis_id} carries a repair. Repair is H3's manipulation; "
                f"a gain measured here would be a gain for verifier-guided reasoning, "
                f"not for the representation."
            )

    # -- training eligibility, decided elsewhere ------------------------------------

    @property
    def training_eligible(self) -> bool:
        """The **router's** verdict. Read-only, and ``False`` when nothing routed this.

        An episode that was never routed is not eligible. That is fail-closed on
        purpose: the absence of a decision is not a decision to include.
        """
        return bool(self.eligibility is not None and self.eligibility.eligible)

    @property
    def repair_mechanism(self) -> str | None:
        """What a repair on this episode *is*, named per hypothesis.

        ``ACQ0_REPAIR`` for the syntax-acquisition prerequisite and
        ``H3_VERIFIER_GUIDED_REPAIR`` for the reasoning hypothesis. They are different
        acts, and the record says which one happened rather than leaving a later reader
        to assume the second.
        """
        if not self.repaired:
            return None
        return REPAIR_MECHANISM.get(self.hypothesis_id, "UNDECLARED_REPAIR")

    def _check_outcome_fields(self) -> None:
        if self.final_verdict not in TERMINAL_VERDICTS:
            raise ValueError(f"{self.final_verdict!r} is not a terminal verdict")
        if self.eligibility is not None and not isinstance(
            self.eligibility, TrainingEligibility
        ):
            raise TypeError(
                "Episode.eligibility must be a TrainingEligibility built from a routing "
                f"decision, not {type(self.eligibility).__name__}"
            )
        if self.training_eligible and not self.hypothesis_id.scientific:
            raise QuarantineEligibilityError(
                f"episode {self.episode_id!r} is recorded under "
                f"{self.hypothesis_id.value}, which is engineering work rather than "
                "evidence, and cannot be training-eligible"
            )
        if self.training_eligible and self.exclusion_reason:
            raise ValueError(
                "an episode cannot be training-eligible and carry an exclusion reason"
            )
        if not self.training_eligible and not self.exclusion_reason:
            raise ValueError(
                "an episode excluded from training must say why; silent exclusion is how "
                "a filtered corpus stops being reproducible"
            )
        if self.initial_stages is not None and self.parsed_object_id is not None:
            if not self.initial_stages.parsed:
                raise ValueError(
                    f"episode {self.episode_id!r} records a parsed object but its stage "
                    f"outcome says parse_status={self.initial_stages.parse_status}"
                )
        if (
            self.confidence_tier is ConfidenceTier.MACHINE_VERIFIED
            and self.final_verdict is not Verdict.VERIFIED
        ):
            raise ValueError(
                f"confidence_tier MACHINE_VERIFIED with verdict {self.final_verdict} is "
                f"contradictory"
            )
        if self.final_verdict is Verdict.VERIFIED and not any(
            r.status is VerifierStatus.SUPPORTED_AND_VERIFIED for r in self.verifier_results
        ):
            raise ValueError(
                "a VERIFIED episode must carry at least one verifier result that "
                "actually verified something"
            )

    # -- repair ---------------------------------------------------------------------

    def with_repair(
        self,
        *,
        repair_output: str,
        repaired_object_id: str | None = None,
        semantic_edit: str = "unrecorded",
        verifier_results: Sequence[VerificationResult] | None = None,
        final_verdict: Verdict | None = None,
        confidence_tier: ConfidenceTier | None = None,
    ) -> Episode:
        """Return a NEW episode carrying this repair.

        The initial output and its hash are copied unchanged. Nothing in this class can
        replace them, which is what makes "an episode is never overwritten when repaired"
        a property of the type rather than a habit of its callers.
        """
        if self.hypothesis_id in (HypothesisId.H1, HypothesisId.H2):
            raise ConfoundedCondition(
                f"cannot attach a repair to an {self.hypothesis_id} episode: repair is "
                f"H3's manipulation"
            )
        return replace(
            self,
            repair_output=repair_output,
            repair_output_hash=_hash_text(repair_output),
            repaired_object_id=repaired_object_id,
            semantic_edit=semantic_edit,
            repair_count=self.repair_count + 1,
            verifier_results=tuple(verifier_results)
            if verifier_results is not None
            else self.verifier_results,
            final_verdict=final_verdict if final_verdict is not None else self.final_verdict,
            confidence_tier=confidence_tier
            if confidence_tier is not None
            else self.confidence_tier,
        )

    @property
    def repaired(self) -> bool:
        return self.repair_count > 0

    # -- serialisation ---------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "task_id": self.task_id,
            "canonical_object_id": self.canonical_object_id,
            "hypothesis_id": str(self.hypothesis_id),
            "hypothesis_claim": HYPOTHESIS_CLAIMS[self.hypothesis_id],
            "condition": self.condition.to_dict(),
            "skill_ids": list(self.skill_ids),
            "dataset_split": self.dataset_split,
            "language_version": self.language_version,
            "compiler_version": self.compiler_version,
            "model_version": self.model_version,
            "diagnostic_version": self.diagnostic_version,
            "verifier_versions": dict(self.verifier_versions),
            "input_representation": str(self.input_representation),
            "initial_output": self.initial_output,
            "initial_output_hash": self.initial_output_hash,
            "parsed_object_id": self.parsed_object_id,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "verifier_results": [r.to_dict() for r in self.verifier_results],
            "counterexamples": [c.to_dict() for c in self.counterexamples],
            "repair_output": self.repair_output,
            "repair_output_hash": self.repair_output_hash,
            "repaired_object_id": self.repaired_object_id,
            "semantic_edit": self.semantic_edit,
            "repair_count": self.repair_count,
            "repair_mechanism": self.repair_mechanism,
            "initial_stages": (
                self.initial_stages.to_dict() if self.initial_stages else None
            ),
            "repair_stages": (
                self.repair_stages.to_dict() if self.repair_stages else None
            ),
            "final_answer": self.final_answer,
            "final_verdict": str(self.final_verdict),
            "confidence_tier": str(self.confidence_tier),
            "training_eligible": self.training_eligible,
            "training_eligibility": (
                self.eligibility.to_dict() if self.eligibility else None
            ),
            "exclusion_reason": self.exclusion_reason,
            "prompt_tokens": self.prompt_tokens.to_dict(),
            "completion_tokens": self.completion_tokens.to_dict(),
            "latency_ms": self.latency_ms.to_dict(),
            "verification_protocol_version": VERIFICATION_PROTOCOL_VERSION,
        }

    def digest(self) -> str:
        """Content hash of the whole episode, for citing it from a report."""
        return sha256_hex(canonical_blob(self.to_dict()))


_GENERATED_EPISODE_INIT = Episode.__init__


def _guarded_episode_init(self: Episode, *args: Any, **kwargs: Any) -> None:
    """Refuse ``training_eligible=`` with an explanation rather than a bare TypeError.

    The dataclass would already reject the keyword — there is no such field — but the
    message it produces ("unexpected keyword argument") reads like a typo. This one says
    what is actually true: the router decides, and the caller may not.
    """
    if "training_eligible" in kwargs:
        raise TrainingEligibilityOverride(
            "training_eligible cannot be set on an Episode. It is derived from the "
            "router's decision: build one with "
            "TrainingEligibility.from_decision(memory.route(facts)) and pass it as "
            "`eligibility=`. A caller-supplied flag could disagree with the router, and "
            "when it did, quarantined data would reach training."
        )
    _GENERATED_EPISODE_INIT(self, *args, **kwargs)


setattr(Episode, "__init__", _guarded_episode_init)  # noqa: B010


def _hash_text(text: str) -> str:
    return sha256_hex(canonical_blob({"text": text}))


def output_hash(text: str) -> str:
    """The hash an episode expects for ``initial_output`` / ``repair_output``."""
    return _hash_text(text)


# ---------------------------------------------------------------------------
# Aggregation guards
# ---------------------------------------------------------------------------


def assert_single_hypothesis(
    episodes: Iterable[Episode], *, allow_excluded: bool = False
) -> Hypothesis:
    """Return the shared ``hypothesis_id``, or raise :class:`HypothesisMixing`.

    Every aggregate must go through this. Averaging an H3 repair result together with an
    H1 representation result produces a number that means nothing and looks like it
    means something, which is precisely the failure this guard exists to prevent. The
    same applies to ACQ0: a prerequisite about writing the syntax is not evidence about
    reasoning, and an aggregate that mixed the two would report the prerequisite's pass
    rate as a hypothesis result.

    ``EXCLUDED`` raises unless ``allow_excluded`` is set. It is not a hypothesis, and a
    scientific aggregate that admitted it would be counting engineering episodes.
    """
    seen = {e.hypothesis_id for e in episodes}
    if not seen:
        raise HypothesisMixing("no episodes to aggregate")
    if len(seen) > 1:
        names = sorted(str(h) for h in seen)
        raise HypothesisMixing(
            f"refusing to aggregate across hypotheses {names}. These test different "
            f"claims: "
            + " ".join(HYPOTHESIS_CLAIMS[h] for h in sorted(seen, key=str))
        )
    only = next(iter(seen))
    if not only.scientific and not allow_excluded:
        raise HypothesisMixing(
            "refusing to aggregate EXCLUDED episodes into a scientific result. "
            + HYPOTHESIS_CLAIMS[only]
        )
    return only


def group_by_contrast(
    episodes: Iterable[Episode],
) -> dict[tuple[str, bool, bool], list[Episode]]:
    """Bucket episodes by their condition, after checking they share a hypothesis."""
    items = list(episodes)
    assert_single_hypothesis(items)
    buckets: dict[tuple[str, bool, bool], list[Episode]] = {}
    for episode in items:
        buckets.setdefault(episode.condition.contrast_key(), []).append(episode)
    return buckets
