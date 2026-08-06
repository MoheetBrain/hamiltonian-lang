"""Assembling the authoritative budget report and walking the slot ladder.

Which prompt gets probed
------------------------
The budget must hold for **every** held-out task, and there are 184 of them across five
conditions. Probing all 920 prompts at every rung is not a sensible spend, so the probe
targets the **longest** prompt in each condition.

Character length picks the target; it never decides the verdict. Those are different
uses and only the second one is forbidden: choosing which of two prompts to measure is a
job an estimate does perfectly well, because being wrong costs a slightly suboptimal
choice of probe target, whereas deciding eligibility from an estimate costs a silently
truncated experiment. :func:`worst_case_task` therefore documents its own limits, and
:attr:`BudgetReport.margin_is_thin` flags the case where the runner-up prompt is close
enough that the pick could have been wrong.

Why the ladder returns one policy for everyone
----------------------------------------------
:func:`walk_ladder` descends until it finds a rung where **every** candidate fits, and
returns that single policy. There is no branch in which one candidate is promoted to a
larger slot: the return type is a :class:`~.slots.ComparisonPlan`, which holds one policy
and one curriculum, so the asymmetry is not expressible rather than merely discouraged.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from evaluation.syntax_gate.candidates import CANDIDATE_IDS, SyntaxAdapter, resolve_adapters
from evaluation.syntax_gate.partition import TRACK_A_HELD_OUT_IDS
from evaluation.syntax_gate.prompts import CONDITIONS, build_prompt
from evaluation.syntax_gate.tasks import GateTask, build_corpus

from .probe import OfflineTokenCounter, PromptProbe, TokenCounter, probe_prompt
from .slots import (
    COMPLETION_ALLOWANCE,
    DEFAULT_SAFETY_RESERVE,
    SLOT_LADDER,
    ComparisonPlan,
    Fit,
    SlotPolicy,
)

__all__ = [
    "worst_case_task",
    "probe_curriculum",
    "walk_ladder",
    "BudgetReport",
    "LadderResult",
    "THIN_MARGIN_CHARACTERS",
]

#: If the second-longest prompt is within this many characters of the longest, the
#: choice of probe target was close and both should be measured. ~200 characters is
#: roughly 50-80 tokens, comfortably inside the reserve but not inside a wrong verdict.
THIN_MARGIN_CHARACTERS = 200


def _corpus() -> dict[str, GateTask]:
    return {t.id: t for t in build_corpus()}


def worst_case_task(
    condition: str,
    curriculum: Sequence[GateTask],
    adapters: dict[str, SyntaxAdapter | None] | None = None,
    *,
    pool: Sequence[GateTask] | None = None,
) -> tuple[GateTask, int, int]:
    """The held-out task with the longest assembled prompt in this condition.

    Returns ``(task, characters, runner_up_characters)``. The runner-up is returned so
    the caller can tell a decisive pick from a coin flip; see
    :data:`THIN_MARGIN_CHARACTERS`.
    """
    tasks = list(pool) if pool is not None else [
        _corpus()[i] for i in sorted(TRACK_A_HELD_OUT_IDS) if i in _corpus()
    ]
    if not tasks:
        raise ValueError("no held-out tasks to measure")
    ad = adapters if adapters is not None else resolve_adapters()
    sized: list[tuple[int, str, GateTask]] = []
    for t in tasks:
        p = build_prompt(t, condition, list(curriculum), ad)
        sized.append((len(p.system) + 1 + len(p.user), t.id, t))
    # Descending size, ascending id: deterministic when two prompts are the same length.
    sized.sort(key=lambda row: (-row[0], row[1]))
    longest = sized[0]
    runner_up = sized[1][0] if len(sized) > 1 else 0
    return longest[2], longest[0], runner_up


def probe_curriculum(
    curriculum: Sequence[GateTask],
    policy: SlotPolicy,
    counter: TokenCounter | None = None,
    *,
    conditions: Sequence[str] = CONDITIONS,
    adapters: dict[str, SyntaxAdapter | None] | None = None,
    completion_allowance: int = COMPLETION_ALLOWANCE,
    safety_reserve: int = DEFAULT_SAFETY_RESERVE,
    pool: Sequence[GateTask] | None = None,
) -> list[PromptProbe]:
    """Measure the worst-case prompt of every condition against one slot policy.

    Every condition is probed under the **same** policy and the **same** curriculum. That
    is not a convenience: it is the invariant that keeps candidate D's token cost a
    reported property rather than a parameter the harness quietly adjusts.
    """
    ad = adapters if adapters is not None else resolve_adapters()
    counter = counter or OfflineTokenCounter()
    demo_ids = tuple(t.id for t in curriculum)
    probes: list[PromptProbe] = []
    for condition in conditions:
        task, chars, runner_up = worst_case_task(condition, curriculum, ad, pool=pool)
        prompt = build_prompt(task, condition, list(curriculum), ad)
        probe = probe_prompt(
            prompt.system,
            prompt.user,
            condition=condition,
            task_id=task.id,
            policy=policy,
            counter=counter,
            curriculum=demo_ids,
            completion_allowance=completion_allowance,
            safety_reserve=safety_reserve,
        )
        notes = list(probe.notes)
        if chars - runner_up < THIN_MARGIN_CHARACTERS:
            notes.append(
                f"probe target chosen by character length, and the runner-up is within "
                f"{chars - runner_up} characters; the longest prompt by characters may "
                "not be the longest by tokens, so treat a near-ceiling verdict here as "
                "provisional and measure the runner-up too"
            )
        from dataclasses import replace

        probes.append(replace(probe, notes=tuple(notes)))
    return probes


@dataclass(frozen=True)
class LadderResult:
    """One rung's outcome: every condition's probe, and whether the rung is usable."""

    policy: SlotPolicy
    probes: tuple[PromptProbe, ...]

    @property
    def every_condition_fits(self) -> bool:
        return bool(self.probes) and all(p.fits for p in self.probes)

    @property
    def undetermined(self) -> tuple[str, ...]:
        return tuple(
            p.condition for p in self.probes if p.eligibility.fit is Fit.UNDETERMINED
        )

    @property
    def overflowing(self) -> tuple[str, ...]:
        return tuple(
            p.condition for p in self.probes if p.eligibility.fit is Fit.OVERFLOWS
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy.to_dict(),
            "every_condition_fits": self.every_condition_fits,
            "overflowing": list(self.overflowing),
            "undetermined": list(self.undetermined),
            "probes": [p.to_dict() for p in self.probes],
        }


@dataclass(frozen=True)
class BudgetReport:
    """The whole ladder walk, and the plan it licenses.

    :attr:`plan` is ``None`` whenever no rung was fully determined and fitting. That is
    the honest outcome of an offline run, and it is what keeps this machinery from
    manufacturing a green light before the Lead authorises the probe.
    """

    ladder: tuple[LadderResult, ...]
    plan: ComparisonPlan | None
    curriculum: tuple[str, ...]
    authoritative: bool
    completion_allowance: int = COMPLETION_ALLOWANCE
    safety_reserve: int = DEFAULT_SAFETY_RESERVE
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def official(self) -> bool:
        """Usable as the ACQ0 execution decision.

        Requires both a plan and an authoritative counter. A stub can produce a plan;
        it can never produce an official one.
        """
        return self.plan is not None and self.authoritative

    @property
    def margin_is_thin(self) -> bool:
        for rung in self.ladder:
            for p in rung.probes:
                h = p.eligibility.headroom
                if p.fits and h is not None and h < DEFAULT_SAFETY_RESERVE:
                    return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "curriculum": list(self.curriculum),
            "completion_allowance": self.completion_allowance,
            "safety_reserve": self.safety_reserve,
            "authoritative": self.authoritative,
            "official": self.official,
            "margin_is_thin": self.margin_is_thin,
            "selected_plan": self.plan.to_dict() if self.plan else None,
            "ladder": [r.to_dict() for r in self.ladder],
            "notes": list(self.notes),
            "_eligibility_rule": (
                "prompt_eval_count + completion_allowance + safety_reserve <= "
                "per_slot_context, decided only on a measured prompt_eval_count; "
                "UNDETERMINED is never a pass"
            ),
        }


def walk_ladder(
    curriculum: Sequence[GateTask],
    counter: TokenCounter | None = None,
    *,
    conditions: Sequence[str] = CONDITIONS,
    adapters: dict[str, SyntaxAdapter | None] | None = None,
    completion_allowance: int = COMPLETION_ALLOWANCE,
    safety_reserve: int = DEFAULT_SAFETY_RESERVE,
    ladder: Sequence[SlotPolicy] = SLOT_LADDER,
    pool: Sequence[GateTask] | None = None,
    stop_at_first_fit: bool = True,
) -> BudgetReport:
    """Try each rung in order and stop at the first that fits every condition.

    ``stop_at_first_fit=False`` measures every rung, which is what the documentation run
    wants: knowing *how much* headroom the fallback rungs have is worth the extra probes
    when the chosen rung is marginal.
    """
    counter = counter or OfflineTokenCounter()
    results: list[LadderResult] = []
    plan: ComparisonPlan | None = None
    notes: list[str] = []
    for policy in ladder:
        probes = probe_curriculum(
            curriculum,
            policy,
            counter,
            conditions=conditions,
            adapters=adapters,
            completion_allowance=completion_allowance,
            safety_reserve=safety_reserve,
            pool=pool,
        )
        rung = LadderResult(policy=policy, probes=tuple(probes))
        results.append(rung)
        if rung.every_condition_fits and plan is None:
            plan = ComparisonPlan(
                policy=policy,
                curriculum=tuple(t.id for t in curriculum),
                candidates=tuple(c for c in conditions),
            )
            notes.append(
                f"{policy.label} is the highest-throughput rung on which every "
                f"condition fits (measured speedup {policy.speedup}x)"
            )
            if stop_at_first_fit:
                break
        elif rung.undetermined:
            notes.append(
                f"{policy.label}: {list(rung.undetermined)} undetermined, so this rung "
                "cannot be selected. An undetermined prompt is not a fitting prompt."
            )
        else:
            notes.append(
                f"{policy.label}: {list(rung.overflowing)} overflow. Descending the "
                "ladder moves EVERY candidate together; the overflowing candidate is "
                "not given a larger slot than the others, and its demonstrations are "
                "not trimmed, because its token cost is a measured property of the "
                "representation."
            )
    if plan is None:
        notes.append(
            "no rung fits every condition on measured counts. The permitted responses "
            "are to shorten the curriculum FOR EVERY CANDIDATE TOGETHER, or to record "
            "that the comparison cannot be run at this curriculum size. Trimming one "
            "candidate is not among them."
        )
    return BudgetReport(
        ladder=tuple(results),
        plan=plan,
        curriculum=tuple(t.id for t in curriculum),
        authoritative=bool(getattr(counter, "AUTHORITATIVE", False)),
        completion_allowance=completion_allowance,
        safety_reserve=safety_reserve,
        notes=tuple(notes),
    )


def candidate_conditions() -> tuple[str, ...]:
    """The four candidate surfaces, without the structured-English control."""
    return CANDIDATE_IDS
