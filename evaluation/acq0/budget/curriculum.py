"""The deterministic five-example curriculum.

The objective
-------------
``F(S) = sum_u max_{s in S} coverage(u, s) - lambda * TokenCost(S)`` maximised subject to
``|S| = 5``.

The first term is set coverage over the **shared core features** — the features every
candidate can express. Coverage is the right shape because a second demonstration of an
already-covered feature teaches almost nothing, and a plain sum over features used would
select five near-duplicates from whichever domain happens to be verbose.

Why ``lambda`` is small, and why that is not a fudge
---------------------------------------------------
With ``|S|`` fixed at five, the cost term cannot trade quantity against quality — it can
only choose between sets that cover equally well. :data:`DEFAULT_LAMBDA` is therefore set
so that the most expensive plausible demonstration (~700 tokens in candidate D) costs
about 0.07 coverage units: enough to break a tie towards the cheaper set, never enough to
discard a demonstration that covers one extra feature. A lambda large enough to override
a real coverage gain would be optimising the prompt's size rather than its content.

``TokenCost`` is the worst case across candidates, on purpose
-------------------------------------------------------------
The binding constraint is that all five demonstrations fit **every** candidate, so the
cost that matters is the one paid by the most expensive representation. Taking the mean,
or costing each candidate separately, would let the curriculum be cheap on average while
overflowing candidate D — and the repair for that would be trimming D's demonstrations,
which is precisely the normalisation this study forbids. D's token cost is a measured
property of the JSON-graph representation and it is allowed to constrain the design; it
is not allowed to be hidden.

Determinism
-----------
Every step sorts by ``(-gain, task_id)``, so ties resolve by id and never by dictionary
or set iteration order. :func:`select_curriculum` takes **no target task**, which makes
per-task curricula structurally unrepresentable — the primary ACQ0 run uses one fixed
curriculum and no dynamic retrieval, and that is enforced by the signature rather than by
a convention someone can forget.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from evaluation.syntax_gate.candidates import CANDIDATE_IDS, SHARED_CORE_FEATURES
from evaluation.syntax_gate.partition import (
    TRACK_A_DEMO_IDS,
    TRACK_A_HELD_OUT_IDS,
    partition,
)
from evaluation.syntax_gate.tasks import GateTask, build_corpus

from hamiltonian_lang.improvement.episodes import Measurement

__all__ = [
    "CURRICULUM_SIZE",
    "DEFAULT_LAMBDA",
    "CostModel",
    "CurriculumSelection",
    "SelectionStep",
    "HeldOutLeakage",
    "NoFeasibleCurriculum",
    "select_curriculum",
    "provisional_cost_model",
    "cost_model_from_probes",
    "demonstration_pool",
]

#: Five. Fixed by the design, not a tunable: a curriculum size chosen after seeing the
#: results is a researcher degree of freedom.
CURRICULUM_SIZE = 5

#: Coverage units charged per token. See the module docstring: small enough that it can
#: only break ties, never override a genuine coverage gain.
DEFAULT_LAMBDA = 1e-4


class HeldOutLeakage(AssertionError):
    """A selected demonstration is a held-out task, or is not in the demonstration pool."""


class NoFeasibleCurriculum(RuntimeError):
    """No set of the required size satisfies the constraints."""


def demonstration_pool() -> list[GateTask]:
    """The eligible demonstrations, in the frozen round-robin order.

    Read from the frozen partition rather than re-derived, so this module cannot disagree
    with the partition manifest about which tasks are demonstrations.
    """
    tasks = {t.id: t for t in build_corpus()}
    return [tasks[i] for i in partition()["demo_order"] if i in tasks]


@dataclass(frozen=True)
class CostModel:
    """Per-demonstration token cost, per candidate.

    Costs are plain integers, not
    :class:`~hamiltonian_lang.improvement.episodes.Measurement`. That is deliberate:
    ``Measurement`` refuses the instrument ``character_count`` outright — there is no
    instrument on this machine that could have produced a token count from a character
    count — so a provisional model physically cannot be expressed in that type. Rather
    than inventing an instrument to get around the guard, the estimates travel as
    integers and :meth:`as_measurement` is the single gate that decides whether a number
    may leave this module wearing the measured label.

    ``authoritative`` is the load-bearing field. A selection made on a provisional model
    is a design draft; only a selection made on measured ``prompt_eval_count`` values may
    be recorded as the official ACQ0 curriculum.
    """

    #: ``(demonstration_id, condition) -> marginal token cost``. ``None`` is unknown.
    cost: Mapping[tuple[str, str], int | None]
    authoritative: bool
    source: str
    conditions: tuple[str, ...] = CANDIDATE_IDS

    def worst_case(self, demo_id: str) -> int | None:
        """The most expensive candidate's cost for this demonstration.

        ``None`` if any candidate's cost is unknown: a worst case computed over a subset
        of the candidates is not a worst case, and using one would understate exactly the
        representation most likely to overflow.
        """
        parts = [self.cost.get((demo_id, c)) for c in self.conditions]
        if any(p is None for p in parts):
            return None
        return max(int(p) for p in parts if p is not None)

    def total(self, demo_ids: Sequence[str]) -> int | None:
        parts = [self.worst_case(d) for d in demo_ids]
        if any(p is None for p in parts):
            return None
        return sum(int(p) for p in parts if p is not None)

    def as_measurement(self, value: int | None, what: str) -> Measurement:
        """The only route from an integer in this module to a ``Measurement``.

        A provisional model always yields an absence carrying the estimate in its reason,
        so the number stays visible to a reader while remaining unusable by
        :func:`~evaluation.acq0.budget.slots.eligibility`.
        """
        if value is None:
            return Measurement.absent(f"{what} is unknown: at least one component is unmeasured")
        if not self.authoritative:
            return Measurement.absent(
                f"{what} is a PROVISIONAL estimate of {value} tokens from {self.source}, "
                "not a measurement. It is recorded so the design is legible and is "
                "deliberately not usable for an eligibility decision."
            )
        return Measurement.measured(
            value,
            instrument="provider_usage",
            citation=f"{what}: summed worst-case demonstration costs ({self.source})",
        )


def provisional_cost_model(
    demonstrations: Sequence[GateTask] | None = None,
    *,
    adapters: dict[str, Any] | None = None,
    chars_per_token: float = 3.0,
) -> CostModel:
    """A character-derived cost model. **Provisional, and it says so.**

    Usable for design work before the Lead authorises the probe. It is marked
    ``authoritative=False`` and its instrument is ``character_count``, so
    :func:`~evaluation.acq0.budget.slots.eligibility` will reject any attempt to decide a
    fit with it and :class:`~evaluation.acq0.budget.report.BudgetReport` will refuse to
    go official on it.
    """
    from evaluation.syntax_gate.candidates import resolve_adapters
    from evaluation.syntax_gate.prompts import render_demonstration

    demos = list(demonstrations) if demonstrations is not None else demonstration_pool()
    ad = adapters if adapters is not None else resolve_adapters()
    cost: dict[tuple[str, str], Measurement] = {}
    for task in demos:
        for condition in CANDIDATE_IDS:
            try:
                rendered = render_demonstration(task, condition, ad)
            except Exception:  # a missing front end is an unknown, never a zero
                cost[(task.id, condition)] = None
                continue
            block = f"--- Example ---\nProblem: {task.cso.prose}\n\n{rendered}\n"
            cost[(task.id, condition)] = max(1, int(len(block) / chars_per_token))
    return CostModel(
        cost=cost,
        authoritative=False,
        source=f"character estimate at {chars_per_token} chars/token",
    )


def cost_model_from_probes(probes: Sequence[Any]) -> CostModel:
    """Build a cost model from measured single-demonstration probes.

    Each probe must carry ``condition``, a one-item ``curriculum`` and a measured
    ``prompt_eval_count`` **already net of the zero-demonstration baseline** — the caller
    subtracts the baseline, because doing it here would require assuming which probe was
    the baseline and that assumption belongs at the call site where it can be checked.
    """
    cost: dict[tuple[str, str], int | None] = {}
    authoritative = True
    sources: set[str] = set()
    for p in probes:
        curriculum = tuple(getattr(p, "curriculum", ()))
        if len(curriculum) != 1:
            raise ValueError(
                f"a marginal cost needs a one-demonstration probe; got {len(curriculum)}"
            )
        m = p.prompt_eval_count
        cost[(curriculum[0], p.condition)] = int(m.value) if m.is_measured else None
        authoritative = authoritative and bool(getattr(p, "authoritative", False))
        sources.add(getattr(p, "counter_name", "?"))
    return CostModel(
        cost=cost,
        authoritative=authoritative,
        source=f"measured marginal prompt_eval_count via {sorted(sources)}",
    )


@dataclass(frozen=True)
class SelectionStep:
    """One greedy step, recorded so the choice can be re-derived by hand."""

    rank: int
    chosen: str
    marginal_coverage: int
    cumulative_coverage: int
    cost_penalty: float
    objective: float
    #: Ids that tied on gain and lost the id sort. Empty when the winner was unique.
    ties: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "chosen": self.chosen,
            "marginal_coverage": self.marginal_coverage,
            "cumulative_coverage": self.cumulative_coverage,
            "cost_penalty": round(self.cost_penalty, 8),
            "objective": round(self.objective, 8),
            "ties_broken_by_id": list(self.ties),
        }


@dataclass(frozen=True)
class CurriculumSelection:
    """The chosen five, the objective they maximise, and the trace that produced them."""

    task_ids: tuple[str, ...]
    covered: tuple[str, ...]
    uncovered: tuple[str, ...]
    universe_size: int
    objective: float
    token_cost: Measurement
    lambda_: float
    steps: tuple[SelectionStep, ...]
    cost_model_source: str
    #: True only when every input cost was a measured ``prompt_eval_count``.
    authoritative: bool
    digest: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def coverage_fraction(self) -> float:
        return len(self.covered) / self.universe_size if self.universe_size else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_ids": list(self.task_ids),
            "covered_features": list(self.covered),
            "uncovered_features": list(self.uncovered),
            "universe_size": self.universe_size,
            "coverage_fraction": round(self.coverage_fraction, 6),
            "objective": round(self.objective, 8),
            "token_cost": self.token_cost.to_dict(),
            "lambda": self.lambda_,
            "steps": [s.to_dict() for s in self.steps],
            "cost_model_source": self.cost_model_source,
            "authoritative": self.authoritative,
            "digest": self.digest,
            "notes": list(self.notes),
            "_status": (
                "OFFICIAL-ELIGIBLE" if self.authoritative else "PROVISIONAL: selected on "
                "estimated costs; must be re-selected on measured prompt_eval_count "
                "before it can be the ACQ0 curriculum"
            ),
        }


def _assert_no_leakage(ids: Sequence[str]) -> None:
    held = [i for i in ids if i in TRACK_A_HELD_OUT_IDS]
    if held:
        raise HeldOutLeakage(
            f"{held} are held-out tasks. A demonstration drawn from the held-out set "
            "shows the model an item it will later be scored on, and every downstream "
            "number becomes a measurement of memorisation."
        )
    outside = [i for i in ids if i not in TRACK_A_DEMO_IDS]
    if outside:
        raise HeldOutLeakage(
            f"{outside} are not in the demonstration pool. Only tasks the frozen "
            "partition assigned to the demonstration stage may be shown."
        )


def select_curriculum(
    size: int = CURRICULUM_SIZE,
    *,
    cost_model: CostModel | None = None,
    lambda_: float = DEFAULT_LAMBDA,
    pool: Sequence[GateTask] | None = None,
    universe: frozenset[str] | None = None,
) -> CurriculumSelection:
    """Constrained greedy maximisation of ``F``. Deterministic by construction.

    Takes **no target task**: the primary ACQ0 run uses one fixed curriculum for every
    item, and a signature that cannot see the target cannot accidentally grow into
    per-task retrieval.
    """
    tasks = list(pool) if pool is not None else demonstration_pool()
    if len(tasks) < size:
        raise NoFeasibleCurriculum(
            f"the demonstration pool holds {len(tasks)} tasks; {size} were requested"
        )
    features = universe if universe is not None else SHARED_CORE_FEATURES
    model = cost_model or provisional_cost_model(tasks)

    # Sorting the pool by id first makes every downstream iteration order deterministic
    # regardless of how the corpus was built.
    by_id = {t.id: t for t in sorted(tasks, key=lambda t: t.id)}
    coverable = {tid: (t.features & features) for tid, t in by_id.items()}

    chosen: list[str] = []
    covered: set[str] = set()
    steps: list[SelectionStep] = []

    for rank in range(1, size + 1):
        scored: list[tuple[int, float, str]] = []
        for tid in sorted(by_id):
            if tid in chosen:
                continue
            gain = len(coverable[tid] - covered)
            c = model.worst_case(tid)
            # An unknown cost is charged nothing here and the selection is marked
            # non-authoritative below; inventing a cost would be worse than declining to
            # rank on one.
            penalty = lambda_ * (c if c is not None else 0)
            scored.append((gain, penalty, tid))
        # Deterministic: highest gain, then lowest penalty, then lowest id.
        scored.sort(key=lambda row: (-row[0], row[1], row[2]))
        best_gain, best_penalty, best_id = scored[0]
        ties = tuple(
            tid for g, p, tid in scored[1:] if g == best_gain and p == best_penalty
        )
        chosen.append(best_id)
        covered |= coverable[best_id]
        steps.append(
            SelectionStep(
                rank=rank,
                chosen=best_id,
                marginal_coverage=best_gain,
                cumulative_coverage=len(covered),
                cost_penalty=best_penalty,
                objective=len(covered) - lambda_ * _cost_value(model, chosen),
                ties=ties,
            )
        )

    _assert_no_leakage(chosen)
    total_value = model.total(chosen)
    total = model.as_measurement(total_value, "curriculum token cost")
    objective = len(covered) - lambda_ * (total_value if total_value is not None else 0)
    notes: list[str] = []
    if not model.authoritative:
        notes.append(
            "selected against a PROVISIONAL character-derived cost model. The five ids "
            "are stable, but the selection must be re-run against measured "
            "prompt_eval_count before it is recorded as the ACQ0 curriculum."
        )
    selection = CurriculumSelection(
        task_ids=tuple(chosen),
        covered=tuple(sorted(covered)),
        uncovered=tuple(sorted(features - covered)),
        universe_size=len(features),
        objective=objective,
        token_cost=total,
        lambda_=lambda_,
        steps=tuple(steps),
        cost_model_source=model.source,
        authoritative=model.authoritative,
        notes=tuple(notes),
    )
    return _with_digest(selection, size=size, pool_ids=sorted(by_id), lambda_=lambda_)


def _cost_value(model: CostModel, ids: Sequence[str]) -> int:
    t = model.total(ids)
    return t if t is not None else 0


def _with_digest(
    selection: CurriculumSelection, *, size: int, pool_ids: Sequence[str], lambda_: float
) -> CurriculumSelection:
    """Hash the inputs and the result together.

    The digest is the mechanical form of "the same inputs must always give the same
    five": a reader who recomputes it and gets a different value knows the pool, the
    lambda or the objective changed, without having to diff five ids by eye.
    """
    from dataclasses import replace

    payload = json.dumps(
        {
            "size": size,
            "lambda": lambda_,
            "pool": list(pool_ids),
            "universe_size": selection.universe_size,
            "cost_model_source": selection.cost_model_source,
            "selected": list(selection.task_ids),
            "covered": list(selection.covered),
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return replace(selection, digest=hashlib.sha256(payload.encode()).hexdigest())
