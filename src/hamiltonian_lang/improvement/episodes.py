"""The episode — Phase 6, the atomic unit of the improvement record.

An episode is one attempt at one task under one experimental condition. It is immutable,
versioned, and it is written so that somebody re-reading it in a year can tell what went
right, what went wrong, and — the part that is easy to lose — *which claim the evidence
actually supports*.

Why ``hypothesis_id`` is mandatory
-----------------------------------
This project tests three hypotheses that can come apart:

**H1** — a Hamiltonian *input* representation improves the answer.
**H2** — a Hamiltonian *reasoning workspace* improves the answer.
**H3** — verifier-guided repair improves the *verified* answer.

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
    "InputRepresentation",
    "Condition",
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


class HypothesisId(StrEnum):
    """Which claim this episode is evidence about. ``NONE`` is not a default."""

    H1 = "H1"
    H2 = "H2"
    H3 = "H3"
    #: Engineering work: a smoke run, a fixture, a pipeline check. Never aggregated with
    #: H1, H2 or H3.
    NONE = "NONE"


#: What each hypothesis asserts, and — the part that decays fastest from memory — what a
#: win does **not** license. Written into the record so a future reader does not have to
#: reconstruct it from a commit message.
HYPOTHESIS_CLAIMS: Mapping[HypothesisId, str] = {
    HypothesisId.H1: (
        "H1: presenting the problem in the Hamiltonian representation, rather than in "
        "English, improves the answer. A win is about the INPUT representation only. It "
        "does not license any claim about a reasoning workspace (H2) or about "
        "verifier-guided repair (H3)."
    ),
    HypothesisId.H2: (
        "H2: requiring a Hamiltonian derivation as the reasoning workspace improves the "
        "answer. A win is about the WORKSPACE. It does not license a claim that the "
        "input representation helped (H1), nor any claim about repair (H3)."
    ),
    HypothesisId.H3: (
        "H3: supplying verifier feedback and permitting repair improves the VERIFIED "
        "answer. A win here is a win for verifier-guided reasoning and MUST NEVER be "
        "reported as a win for the representation. H3 machinery is available to English "
        "encodings too; if the comparison did not hold representation fixed, the result "
        "is about the loop, not the language."
    ),
    HypothesisId.NONE: (
        "NONE: an engineering episode. It is not evidence for or against any hypothesis "
        "and is excluded from every hypothesis-level aggregate."
    ),
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

    def check_against(self, hypothesis: HypothesisId) -> None:
        """Refuse a condition that confounds the hypothesis it claims to test."""
        if hypothesis in (HypothesisId.H1, HypothesisId.H2):
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


@dataclass(frozen=True)
class Episode:
    """One immutable attempt at one task.

    **A repair never overwrites the initial attempt.** ``initial_output`` and
    ``initial_output_hash`` are set once; :meth:`with_repair` returns a *new* episode with
    the repair fields filled and copies the initial fields verbatim, refusing to run if
    the caller tries to alter them. The full sequence of attempts lives in the event
    ledger, keyed by ``episode_id``.
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

    # -- outcome --------------------------------------------------------------------
    final_answer: str | None = None
    final_verdict: Verdict = Verdict.INCONCLUSIVE
    confidence_tier: ConfidenceTier = ConfidenceTier.UNVERIFIED
    training_eligible: bool = False
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

    def _check_outcome_fields(self) -> None:
        if self.final_verdict not in TERMINAL_VERDICTS:
            raise ValueError(f"{self.final_verdict!r} is not a terminal verdict")
        if self.training_eligible and self.exclusion_reason:
            raise ValueError(
                "an episode cannot be training-eligible and carry an exclusion reason"
            )
        if not self.training_eligible and not self.exclusion_reason:
            raise ValueError(
                "an episode excluded from training must say why; silent exclusion is how "
                "a filtered corpus stops being reproducible"
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
            "final_answer": self.final_answer,
            "final_verdict": str(self.final_verdict),
            "confidence_tier": str(self.confidence_tier),
            "training_eligible": self.training_eligible,
            "exclusion_reason": self.exclusion_reason,
            "prompt_tokens": self.prompt_tokens.to_dict(),
            "completion_tokens": self.completion_tokens.to_dict(),
            "latency_ms": self.latency_ms.to_dict(),
            "verification_protocol_version": VERIFICATION_PROTOCOL_VERSION,
        }

    def digest(self) -> str:
        """Content hash of the whole episode, for citing it from a report."""
        return sha256_hex(canonical_blob(self.to_dict()))


def _hash_text(text: str) -> str:
    return sha256_hex(canonical_blob({"text": text}))


def output_hash(text: str) -> str:
    """The hash an episode expects for ``initial_output`` / ``repair_output``."""
    return _hash_text(text)


# ---------------------------------------------------------------------------
# Aggregation guards
# ---------------------------------------------------------------------------


def assert_single_hypothesis(episodes: Iterable[Episode]) -> HypothesisId:
    """Return the shared ``hypothesis_id``, or raise :class:`HypothesisMixing`.

    Every aggregate must go through this. Averaging an H3 repair result together with an
    H1 representation result produces a number that means nothing and looks like it
    means something, which is precisely the failure this guard exists to prevent.
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
    return next(iter(seen))


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
