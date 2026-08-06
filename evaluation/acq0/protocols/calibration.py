"""The 16-call calibration design. Specified and asserted here; executed elsewhere.

The design
----------
``4 syntaxes x 2 representative non-evaluation tasks x 2 protocols = 16 calls``, where the
two protocols are ``DIRECT_FORMAL`` and ``DRAFT_THEN_FORMAL``.

Note the arithmetic: 16 **cells**, not 16 model calls. ``DRAFT_THEN_FORMAL`` runs two
stages, so the cell count and the call count differ, and :data:`CALIBRATION_CALL_COUNT`
states the real number. A budget written against the cell count would be short by exactly
the draft stage — the same omission the token ledger exists to prevent, transplanted into
the authorisation.

``PLAN_THEN_FORMAL`` is deliberately excluded from the first pass. It is the escalation,
run only if the first 16 leave a genuine ambiguity, because a third arm run
unconditionally costs 50% more and answers a question the first two may already settle.

Task selection
--------------
Two tasks drawn from the **demonstration** stage of the frozen partition. That stage is
the only pool that never scores anything: G2 screening, G3 curriculum, G4 confirmatory and
G4 replication are all held out, and a task shown to the model during calibration can no
longer be scored honestly. :func:`assert_calibration_tasks_are_not_evaluation` asserts
this against ``TRACK_A_HELD_OUT_IDS`` rather than trusting the selection.

The two are drawn from **different domains** — one structural, one distributional — so a
protocol that helps only one kind of content cannot look like a protocol that helps.

Curriculum size
---------------
Zero, by decision, with the reason recorded in :data:`CALIBRATION_DECISIONS`. Two grounds:

* the calibration tasks are drawn from the demonstration pool, so a non-zero curriculum
  could place a task in its own demonstration set — a leak that would flatter whichever
  protocol happened to draw it;
* stage two of ``DRAFT_THEN_FORMAL`` carries the specification, the problem *and* the
  draft. At curriculum 0 that is comfortably inside the 8192-token slot; at the measured
  50-demonstration curriculum (5,893 prompt tokens) the draft would risk truncation, and
  a truncated prompt is a different experimental condition wearing the same label.

The consequence is stated rather than hidden: the selected protocol is calibrated at
curriculum 0 and its transfer to the gate's curriculum is an assumption, recorded in
:data:`CALIBRATION_LIMITATIONS`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from evaluation.syntax_gate.candidates import CANDIDATE_IDS
from evaluation.syntax_gate.tasks import GateTask

from .core import PROTOCOL_STAGES, GenerationProtocol

__all__ = [
    "CALIBRATION_PROTOCOLS",
    "ESCALATION_PROTOCOL",
    "CALIBRATION_CURRICULUM_SIZE",
    "CALIBRATION_DOMAINS",
    "CalibrationCell",
    "CALIBRATION_DECISIONS",
    "CALIBRATION_LIMITATIONS",
    "calibration_tasks",
    "calibration_cells",
    "escalation_cells",
    "call_count",
    "CALIBRATION_CELL_COUNT",
    "CALIBRATION_CALL_COUNT",
    "assert_calibration_tasks_are_not_evaluation",
    "calibration_design",
    "budget_report",
]

#: The first pass. Two arms, because two arms answer the question if they disagree.
CALIBRATION_PROTOCOLS: tuple[GenerationProtocol, ...] = (
    GenerationProtocol.DIRECT_FORMAL,
    GenerationProtocol.DRAFT_THEN_FORMAL,
)

#: Run only on ambiguity. See :func:`escalation_cells`.
ESCALATION_PROTOCOL = GenerationProtocol.PLAN_THEN_FORMAL

CALIBRATION_CURRICULUM_SIZE = 0

#: One structural domain and one distributional domain. Chosen for contrast, not at
#: random: a protocol effect that appears on both is a protocol effect, and one that
#: appears on neither leaves the design ambiguous rather than falsely settled.
CALIBRATION_DOMAINS: tuple[str, str] = ("binding_chain", "distribution_law")

CALIBRATION_CELL_COUNT = len(CANDIDATE_IDS) * 2 * len(CALIBRATION_PROTOCOLS)


def call_count(protocols: Sequence[GenerationProtocol], *, cells_per_protocol: int) -> int:
    """Model calls, not cells. A two-stage protocol costs two calls per cell."""
    return sum(len(PROTOCOL_STAGES[p]) * cells_per_protocol for p in protocols)


#: The real spend: 8 cells x 1 call (DIRECT) + 8 cells x 2 calls (DRAFT) = 24 calls.
CALIBRATION_CALL_COUNT = call_count(
    CALIBRATION_PROTOCOLS, cells_per_protocol=len(CANDIDATE_IDS) * 2
)


@dataclass(frozen=True)
class CalibrationCell:
    """One (syntax, task, protocol) cell of the design."""

    condition: str
    task_id: str
    domain: str
    protocol: GenerationProtocol
    curriculum_size: int = CALIBRATION_CURRICULUM_SIZE

    @property
    def calls(self) -> int:
        return len(PROTOCOL_STAGES[self.protocol])

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition,
            "task_id": self.task_id,
            "domain": self.domain,
            "protocol": str(self.protocol),
            "curriculum_size": self.curriculum_size,
            "calls": self.calls,
        }


CALIBRATION_DECISIONS: tuple[str, ...] = (
    "curriculum size 0: the calibration tasks come from the demonstration pool, so a "
    "non-zero curriculum could place a task in its own demonstration set; and stage two "
    "of DRAFT_THEN_FORMAL carries specification + problem + draft, which must fit the "
    "8192-token per-slot budget without truncation.",
    "two protocols, not three: PLAN_THEN_FORMAL is the escalation. Running it "
    "unconditionally costs 50% more calls to answer a question the first two arms may "
    "already settle.",
    "two domains, not one: a protocol that helps only structural content would otherwise "
    "be indistinguishable from a protocol that helps.",
    "temperature 0, as pinned in evaluation/manifests/environment_manifest.json. A "
    "sampled calibration would need repeats this budget does not cover.",
)

CALIBRATION_LIMITATIONS: tuple[str, ...] = (
    "8 trials per arm. One trial is 0.125, so the pre-registered materiality threshold "
    "of 0.25 is two trials' worth. This design can detect a large protocol effect and "
    "cannot detect a small one; it is a calibration, not the gate.",
    "calibrated at curriculum size 0. Transfer to the gate's curriculum is an "
    "assumption, not a measurement: demonstrations may themselves mitigate format "
    "restriction, in which case the protocol difference measured here is an upper bound "
    "on the difference at the gate's curriculum size.",
    "one model, one quantisation, one host. gemma4:31b Q4_K_M under Ollama 0.32.5; the "
    "result licenses no claim about other models.",
    "the two calibration tasks are demonstration-pool tasks and will subsequently appear "
    "in gate curricula. That is not contamination of the gate's *scoring* set, but it "
    "does mean these two tasks are no longer usable as held-out items.",
)


#: The Lead's freeze supersedes :data:`CALIBRATION_CURRICULUM_SIZE` for **execution**. The
#: pre-registered 0 is kept above with its reasoning intact rather than overwritten, so the
#: record shows that the change came from the freeze and not from a result.
FROZEN_CALIBRATION_CURRICULUM_SIZE = 5

#: The frozen curriculum, in the Lead's exact order.
FROZEN_CURRICULUM_IDS: tuple[str, ...] = (
    "binding_chain_000",
    "quantifier_scope_000",
    "distribution_law_000",
    "dimensional_algebra_000",
    "transformation_chain_000",
)


#: Tasks the model has already been shown by a previous calibration run. They are not
#: contaminated for the gate -- they were never held out -- but they are no longer clean
#: for a *protocol* comparison: a second exposure measures recall as well as encoding.
#: Appended to, never rewritten, so the exposure history stays legible.
EXPOSED_TASK_IDS: tuple[str, ...] = (
    # v1 calibration run, 2026-08-06, retained at
    # evaluation/results/acq0/protocol_calibration/
    "binding_chain_001",
    "distribution_law_001",
)

#: What a fresh calibration must avoid: the frozen curriculum (a task in its own
#: demonstration set measures copying) and every previously exposed task.
CALIBRATION_EXCLUSIONS: tuple[str, ...] = FROZEN_CURRICULUM_IDS + EXPOSED_TASK_IDS


def calibration_tasks(
    corpus: Sequence[GateTask] | None = None,
    *,
    exclude_ids: Sequence[str] = CALIBRATION_EXCLUSIONS,
) -> tuple[GateTask, GateTask]:
    """The two non-evaluation tasks, chosen deterministically.

    Deterministic selection matters more than clever selection: the first
    demonstration-stage task in each chosen domain, in id order, **excluding the frozen
    curriculum**. A different rule would need a justification that could later be read as
    having been chosen to produce a result.

    The exclusion is not cosmetic. Measured at ``21687cf``, the unexcluded rule returns
    ``binding_chain_000`` and ``distribution_law_000``, and both are in the Lead's frozen
    5-demonstration curriculum. Running those at curriculum 5 would paste each task's own
    reference encoding into its own prompt as a worked example: the trial would measure
    copying, and ``assert_demonstrations_disjoint`` would (correctly) refuse to build the
    prompt at all. Skipping to the next id in the same domain preserves both the domain
    contrast and the determinism.
    """
    from evaluation.syntax_gate.partition import partition

    tasks = list(corpus) if corpus is not None else _track_a()
    stage_of = partition()["stage_of"]
    banned = set(exclude_ids)
    picked: list[GateTask] = []
    for domain in CALIBRATION_DOMAINS:
        candidates = sorted(
            (
                t
                for t in tasks
                if t.domain == domain
                and stage_of.get(t.id) == "demonstration"
                and t.id not in banned
            ),
            key=lambda t: t.id,
        )
        if not candidates:
            raise AssertionError(
                f"no demonstration-stage task in domain {domain!r}; the calibration "
                "cannot fall back to a held-out task, so this is a hard failure"
            )
        picked.append(candidates[0])
    return (picked[0], picked[1])


def _track_a() -> list[GateTask]:
    from evaluation.syntax_gate.tasks import build_track_a

    return build_track_a()


def assert_calibration_tasks_are_not_evaluation(
    tasks: Sequence[GateTask] | None = None,
) -> None:
    """Assert no calibration task can ever score the gate."""
    from evaluation.syntax_gate.partition import (
        TRACK_A_GATE_IDS,
        TRACK_A_HELD_OUT_IDS,
    )

    chosen = list(tasks) if tasks is not None else list(calibration_tasks())
    held = sorted({t.id for t in chosen} & set(TRACK_A_HELD_OUT_IDS))
    if held:
        gate = sorted({t.id for t in chosen} & set(TRACK_A_GATE_IDS))
        raise AssertionError(
            f"calibration would touch held-out task(s) {held} "
            f"(of which {len(gate)} are in the confirmatory gate set). A task the model "
            "has seen during calibration cannot afterwards score the gate."
        )


def calibration_cells(
    tasks: Sequence[GateTask] | None = None,
    protocols: Sequence[GenerationProtocol] = CALIBRATION_PROTOCOLS,
) -> tuple[CalibrationCell, ...]:
    """Every cell, in a deterministic order."""
    chosen = list(tasks) if tasks is not None else list(calibration_tasks())
    assert_calibration_tasks_are_not_evaluation(chosen)
    cells: list[CalibrationCell] = []
    for protocol in protocols:
        for condition in CANDIDATE_IDS:
            for task in chosen:
                cells.append(
                    CalibrationCell(
                        condition=condition,
                        task_id=task.id,
                        domain=task.domain,
                        protocol=protocol,
                    )
                )
    return tuple(cells)


def escalation_cells(
    tasks: Sequence[GateTask] | None = None,
) -> tuple[CalibrationCell, ...]:
    """The ``PLAN_THEN_FORMAL`` cells. Run **only** on an AMBIGUOUS selection."""
    return calibration_cells(tasks, protocols=(ESCALATION_PROTOCOL,))


def budget_report(cells: Sequence[CalibrationCell] | None = None) -> dict[str, Any]:
    """Cells, calls and the per-protocol split. The number an authorisation is written on."""
    rows = list(cells) if cells is not None else list(calibration_cells())
    per_protocol: dict[str, dict[str, int]] = {}
    for c in rows:
        entry = per_protocol.setdefault(str(c.protocol), {"cells": 0, "calls": 0})
        entry["cells"] += 1
        entry["calls"] += c.calls
    return {
        "cells": len(rows),
        "calls": sum(c.calls for c in rows),
        "per_protocol": per_protocol,
        "warning": (
            "cells and calls are different numbers. DRAFT_THEN_FORMAL runs two stages "
            "per cell, so an authorisation written against the cell count is short by "
            "exactly the draft stage."
        ),
    }


def calibration_design(tasks: Sequence[GateTask] | None = None) -> dict[str, Any]:
    """The whole design as a record, for the audit document and for the Lead."""
    chosen = list(tasks) if tasks is not None else list(calibration_tasks())
    cells = calibration_cells(chosen)
    from .selection import LEXICOGRAPHIC_KEYS, MATERIALITY

    return {
        "design": "4 syntaxes x 2 non-evaluation tasks x 2 protocols",
        "conditions": list(CANDIDATE_IDS),
        "protocols": [str(p) for p in CALIBRATION_PROTOCOLS],
        "escalation_protocol": str(ESCALATION_PROTOCOL),
        "tasks": [
            {"id": t.id, "domain": t.domain, "stage": "demonstration"} for t in chosen
        ],
        "curriculum_size": CALIBRATION_CURRICULUM_SIZE,
        "budget": budget_report(cells),
        "escalation_budget": budget_report(escalation_cells(chosen)),
        "selection": {
            "keys_in_order": list(LEXICOGRAPHIC_KEYS),
            "materiality": dict(MATERIALITY),
            "never": (
                "never by parse rate alone, and never by a weighted score in which "
                "token efficiency can compensate for semantic corruption"
            ),
        },
        "decisions": list(CALIBRATION_DECISIONS),
        "limitations": list(CALIBRATION_LIMITATIONS),
        "executed": False,
        "executed_note": (
            "no model call has been made. Selection awaits the Lead's authorisation; "
            "until then the protocol is UNSTABLE by construction, not by measurement."
        ),
    }
