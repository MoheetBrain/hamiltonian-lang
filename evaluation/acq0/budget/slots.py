"""Slot policy and the eligibility arithmetic. Zero tolerance for hidden truncation.

The quantity that decides everything
------------------------------------
A prompt is eligible for a slot when, and only when::

    prompt_eval_count + completion_allowance + safety_reserve <= per_slot_context

``prompt_eval_count`` is the server's own count of the tokens it evaluated. It is the
only admissible input. A character-derived estimate is not a smaller version of this
number, it is a different kind of thing, and :func:`eligibility` will not accept one —
see :class:`EstimateOfferedAsMeasurement`.

Why the reserve is not optional
-------------------------------
If a prompt exceeds the slot, ``llama-server`` does not fail; it **evicts the front of
the context**. The run continues, the reply looks plausible, and the demonstrations the
model was supposed to learn from are the part that silently went missing. That failure
mode produces a *lower* score for the affected candidate with no error anywhere in the
record, which is indistinguishable from that candidate being worse. The reserve exists
because the boundary is a cliff with no guard rail on the far side.

Hidden reasoning tokens count against the completion allowance
--------------------------------------------------------------
A provider that streams a reasoning channel charges for those tokens and they occupy the
same slot. :data:`COMPLETION_ALLOWANCE` is therefore the allowance for *everything the
model emits*, visible or not. Budgeting only for the visible answer is how a run that
looked comfortable overruns.

The ladder, and the rule that makes it fair
-------------------------------------------
``4 x 8192`` is tried first because it is the configuration the tournament is tuned for
(2.08x throughput, ``docs/evaluation/EXECUTION_ENVIRONMENT.md`` Finding 2). If a common
curriculum does not fit *every* candidate there, the whole comparison drops to
``2 x 16384``, and then to ``1 x 32768``.

**Every candidate moves together.** :class:`ComparisonPlan` refuses to hold two policies,
because giving the expensive candidate a bigger slot would convert its token cost — a
measured property of the representation — into a free parameter of the harness. The same
reasoning forbids trimming one candidate's demonstrations: see
:class:`UnequalCurriculum`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from hamiltonian_lang.improvement.episodes import Measurement

__all__ = [
    "TOTAL_CONTEXT",
    "COMPLETION_ALLOWANCE",
    "MIN_COMPLETION_ALLOWANCE",
    "MIN_SAFETY_RESERVE",
    "DEFAULT_SAFETY_RESERVE",
    "SlotPolicy",
    "SLOT_LADDER",
    "Fit",
    "Eligibility",
    "eligibility",
    "ComparisonPlan",
    "assert_symmetric",
    "AsymmetricSlotAllocation",
    "UnequalCurriculum",
    "EstimateOfferedAsMeasurement",
    "InsufficientReserve",
    "InsufficientAllowance",
    "policy_for_slots",
    "next_policy",
]

#: The server's total context, from the required configuration in
#: ``docs/evaluation/EXECUTION_ENVIRONMENT.md`` (``-c 32768``).
TOTAL_CONTEXT = 32768

#: Tokens reserved for everything the model emits — visible completion *and* any hidden
#: reasoning channel. Fixed across protocols by design: ``DIRECT_FORMAL`` and
#: ``DRAFT_THEN_FORMAL`` get the **same maximum total completion allowance**, so neither
#: arm wins by having been allowed to emit more.
COMPLETION_ALLOWANCE = 2048

#: The floor. A reserve below this is refused rather than warned about.
MIN_SAFETY_RESERVE = 256

#: The floor on the completion allowance. Below this a slot cannot hold even a minimal
#: reply, so the configuration is not a tighter budget but a broken one.
#:
#: This floor exists because the allowance is the *other* way the inequality can be
#: gamed. Shrinking it — or passing a negative value, which is arithmetic nonsense —
#: raises the ceiling and buys a ``FITS`` verdict for a prompt that provably overflows
#: the slot. That is the same silent-eviction failure the reserve guards against,
#: reached from the opposite side, and it is refused the same way.
MIN_COMPLETION_ALLOWANCE = 256

#: What this study uses. Above the floor because the eviction failure mode is silent and
#: the cost of a slightly smaller curriculum is a design decision we can see.
DEFAULT_SAFETY_RESERVE = 256


class AsymmetricSlotAllocation(AssertionError):
    """Two candidates were placed under different slot policies in one comparison."""


class UnequalCurriculum(AssertionError):
    """Candidates in one comparison were given different numbers of demonstrations."""


class EstimateOfferedAsMeasurement(TypeError):
    """A character-derived estimate was passed where ``prompt_eval_count`` belongs."""


class InsufficientReserve(ValueError):
    """A safety reserve below :data:`MIN_SAFETY_RESERVE` was requested."""


class InsufficientAllowance(ValueError):
    """A completion allowance below :data:`MIN_COMPLETION_ALLOWANCE` was requested."""


@dataclass(frozen=True)
class SlotPolicy:
    """One server configuration: how many parallel slots, and how big each one is.

    ``per_slot_context`` is derived, never passed. ``-np N`` divides the context evenly,
    so a policy whose slot size did not follow from its slot count would describe a
    server that cannot exist.
    """

    parallel_slots: int
    #: Measured aggregate throughput relative to ``-np 1``, from Finding 2. Carried so
    #: the cost of dropping down the ladder is visible at the point of the decision.
    speedup: float
    total_context: int = TOTAL_CONTEXT

    def __post_init__(self) -> None:
        if self.parallel_slots < 1:
            raise ValueError("a policy must have at least one slot")
        if self.total_context % self.parallel_slots:
            raise ValueError(
                f"{self.total_context} does not divide evenly into "
                f"{self.parallel_slots} slots; the resulting per-slot size would not be "
                "the size the server actually allocates"
            )

    @property
    def per_slot_context(self) -> int:
        return self.total_context // self.parallel_slots

    @property
    def label(self) -> str:
        return f"{self.parallel_slots} x {self.per_slot_context}"

    def prompt_ceiling(
        self,
        *,
        completion_allowance: int = COMPLETION_ALLOWANCE,
        safety_reserve: int = DEFAULT_SAFETY_RESERVE,
    ) -> int:
        """The largest ``prompt_eval_count`` that fits. May be negative, and that is real.

        A negative ceiling means the allowance and the reserve alone exceed the slot, so
        no prompt of any size fits. Clamping it to zero would report "your prompt is too
        big" for a configuration whose actual defect is that it cannot run at all.
        """
        if safety_reserve < MIN_SAFETY_RESERVE:
            raise InsufficientReserve(
                f"safety_reserve={safety_reserve} is below the {MIN_SAFETY_RESERVE} "
                "floor. The overflow failure mode is silent context eviction, not an "
                "error, so the reserve is the only thing standing between a marginal "
                "prompt and a curriculum that vanishes without a diagnostic."
            )
        if completion_allowance < MIN_COMPLETION_ALLOWANCE:
            raise InsufficientAllowance(
                f"completion_allowance={completion_allowance} is below the "
                f"{MIN_COMPLETION_ALLOWANCE} floor. Shrinking the allowance raises the "
                "ceiling and buys a FITS verdict for a prompt that overflows the slot — "
                "the same silent-eviction failure the safety reserve guards against, "
                "reached from the opposite side. A negative allowance is arithmetic "
                "nonsense and would put the ceiling above the slot itself."
            )
        ceiling = self.per_slot_context - completion_allowance - safety_reserve
        # Belt and braces: the ceiling can never exceed the slot it is a ceiling for.
        # With both floors enforced this is unreachable, and it is kept because it is the
        # invariant a future edit to either floor would break.
        if ceiling > self.per_slot_context:
            raise InsufficientAllowance(
                f"a ceiling of {ceiling} exceeds the {self.per_slot_context}-token slot "
                "it bounds; that describes a server that cannot exist"
            )
        return ceiling

    def to_dict(self) -> dict[str, Any]:
        return {
            "parallel_slots": self.parallel_slots,
            "per_slot_context": self.per_slot_context,
            "total_context": self.total_context,
            "measured_speedup": self.speedup,
            "prompt_ceiling": self.prompt_ceiling(),
        }


#: The ladder, in the order it must be tried. Descending parallelism, ascending slot
#: size, descending throughput — the trade the Lead is making when a rung is refused.
SLOT_LADDER: tuple[SlotPolicy, ...] = (
    SlotPolicy(parallel_slots=4, speedup=2.08),
    SlotPolicy(parallel_slots=2, speedup=1.54),
    SlotPolicy(parallel_slots=1, speedup=1.00),
)


def policy_for_slots(parallel_slots: int) -> SlotPolicy:
    for p in SLOT_LADDER:
        if p.parallel_slots == parallel_slots:
            return p
    raise ValueError(
        f"no rung of the ladder runs {parallel_slots} slots; the ladder is "
        f"{[p.label for p in SLOT_LADDER]}"
    )


def next_policy(policy: SlotPolicy) -> SlotPolicy | None:
    """The next rung down, or ``None`` at the bottom.

    ``None`` is a real answer: it means the curriculum does not fit even the whole
    context, and the response is to shorten the curriculum **for every candidate
    together**, never to keep descending a ladder that has ended.
    """
    for i, p in enumerate(SLOT_LADDER):
        if p.parallel_slots == policy.parallel_slots:
            return SLOT_LADDER[i + 1] if i + 1 < len(SLOT_LADDER) else None
    raise ValueError(f"{policy.label} is not a rung of the ladder")


class Fit(StrEnum):
    """The eligibility verdict. Three values, and the third is not a soft pass.

    ``UNDETERMINED`` is what an unmeasured prompt gets. It is **not** eligibility, it
    does not become eligibility if nothing else is available, and no rung of the ladder
    may be selected on the strength of it.
    """

    FITS = "FITS"
    OVERFLOWS = "OVERFLOWS"
    UNDETERMINED = "UNDETERMINED"


@dataclass(frozen=True)
class Eligibility:
    """One prompt against one slot policy.

    ``headroom`` is ``ceiling - prompt_eval_count``: the number of tokens by which the
    prompt could grow before the server begins evicting it. Absent when the count is.
    """

    fit: Fit
    policy: SlotPolicy
    prompt_eval_count: Measurement
    completion_allowance: int
    safety_reserve: int
    ceiling: int
    headroom: int | None
    detail: str

    @property
    def fits(self) -> bool:
        """True only for :attr:`Fit.FITS`. ``UNDETERMINED`` is false here on purpose."""
        return self.fit is Fit.FITS

    def to_dict(self) -> dict[str, Any]:
        return {
            "fit": str(self.fit),
            "policy": self.policy.to_dict(),
            "prompt_eval_count": self.prompt_eval_count.to_dict(),
            "completion_allowance": self.completion_allowance,
            "safety_reserve": self.safety_reserve,
            "ceiling": self.ceiling,
            "headroom": self.headroom,
            "detail": self.detail,
        }


def eligibility(
    prompt_eval_count: Measurement,
    policy: SlotPolicy,
    *,
    completion_allowance: int = COMPLETION_ALLOWANCE,
    safety_reserve: int = DEFAULT_SAFETY_RESERVE,
) -> Eligibility:
    """Decide the inequality. The only admissible input is an authoritative count.

    Raises :class:`EstimateOfferedAsMeasurement` when handed a measurement whose
    instrument is not a token counter. That check is the reason this function takes a
    :class:`Measurement` rather than an ``int``: an ``int`` carries no provenance, and a
    character-derived estimate is exactly as much an ``int`` as a real count is.
    """
    ceiling = policy.prompt_ceiling(
        completion_allowance=completion_allowance, safety_reserve=safety_reserve
    )
    if not prompt_eval_count.is_measured:
        return Eligibility(
            fit=Fit.UNDETERMINED,
            policy=policy,
            prompt_eval_count=prompt_eval_count,
            completion_allowance=completion_allowance,
            safety_reserve=safety_reserve,
            ceiling=ceiling,
            headroom=None,
            detail=(
                "no authoritative prompt_eval_count, so eligibility is undetermined. "
                "This is not a pass: running on an undetermined prompt is how a "
                "curriculum gets silently evicted. "
                f"({prompt_eval_count.reason})"
            ),
        )
    if prompt_eval_count.instrument not in _TOKEN_INSTRUMENTS:
        raise EstimateOfferedAsMeasurement(
            f"prompt_eval_count carries instrument {prompt_eval_count.instrument!r}, "
            f"which is not one of {sorted(_TOKEN_INSTRUMENTS)}. A character-derived "
            "estimate must never decide eligibility: the divisor that makes it right "
            "for prose is wrong for punctuation-dense formal text by exactly the margin "
            "that matters at the boundary."
        )
    count = int(prompt_eval_count.value or 0)
    headroom = ceiling - count
    fits = headroom >= 0
    return Eligibility(
        fit=Fit.FITS if fits else Fit.OVERFLOWS,
        policy=policy,
        prompt_eval_count=prompt_eval_count,
        completion_allowance=completion_allowance,
        safety_reserve=safety_reserve,
        ceiling=ceiling,
        headroom=headroom,
        detail=(
            f"{count} + {completion_allowance} + {safety_reserve} = "
            f"{count + completion_allowance + safety_reserve} "
            f"{'<=' if fits else '>'} {policy.per_slot_context}"
        ),
    )


#: Instruments whose output is a real token count. ``provider_usage`` is the Ollama
#: ``prompt_eval_count`` path; a local tokeniser would be added here if one were ever
#: installed. Character estimates are deliberately absent and must stay absent.
_TOKEN_INSTRUMENTS: frozenset[str] = frozenset({"provider_usage"})


@dataclass(frozen=True)
class ComparisonPlan:
    """One slot policy and one curriculum, for every candidate in the comparison.

    Both fields are singular, and that is the whole design. The two ways this experiment
    could be quietly rigged in the expensive candidate's favour are giving it a bigger
    slot and giving it fewer demonstrations; neither is expressible here, because there
    is nowhere to put a per-candidate value.
    """

    policy: SlotPolicy
    #: Demonstration task ids, in order. The same list for every candidate.
    curriculum: tuple[str, ...]
    candidates: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.candidates:
            raise ValueError("a comparison needs at least one candidate")
        if len(set(self.candidates)) != len(self.candidates):
            raise ValueError(f"duplicate candidate in {self.candidates}")

    @property
    def curriculum_size(self) -> int:
        return len(self.curriculum)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy.to_dict(),
            "curriculum": list(self.curriculum),
            "curriculum_size": self.curriculum_size,
            "candidates": list(self.candidates),
            "invariant": (
                "one policy and one curriculum for every candidate; candidate D is "
                "never given a larger slot or a shorter curriculum than A/B/C, because "
                "its token cost is a measured property of the representation and not a "
                "harness parameter to be normalised away"
            ),
        }


def assert_symmetric(
    per_candidate_policy: Mapping[str, SlotPolicy],
    per_candidate_curriculum: Mapping[str, Sequence[str]],
) -> None:
    """Refuse a comparison whose candidates were not treated identically.

    Used at the boundary where results assembled elsewhere are read back in. A
    :class:`ComparisonPlan` cannot express the asymmetry; a pair of dictionaries can,
    and this is where that is caught.
    """
    policies = {c: p.label for c, p in per_candidate_policy.items()}
    if len(set(policies.values())) > 1:
        raise AsymmetricSlotAllocation(
            f"candidates were run under different slot policies: {policies}. A candidate "
            "given a larger slot than the others is not being measured on the same "
            "experiment; its extra token cost has been paid for by the harness rather "
            "than reported as a property of the representation."
        )
    sizes = {c: len(v) for c, v in per_candidate_curriculum.items()}
    if len(set(sizes.values())) > 1:
        raise UnequalCurriculum(
            f"candidates were given different curricula: {sizes}. Trimming the expensive "
            "candidate's demonstrations makes it look affordable by teaching it less, "
            "and the resulting score difference would be read as a property of the "
            "syntax."
        )
    contents = {c: tuple(v) for c, v in per_candidate_curriculum.items()}
    if len(set(contents.values())) > 1:
        raise UnequalCurriculum(
            "candidates were given curricula of equal length but different content; "
            f"{ {c: list(v) for c, v in contents.items()} }. Demonstrations differ in "
            "difficulty, so a same-sized but different curriculum is still a different "
            "experimental condition."
        )
