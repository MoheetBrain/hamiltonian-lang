"""The phase call ledger, derived before execution, and the authorisation written on it.

Why this is a separate module from :mod:`.calibration`
------------------------------------------------------
``calibration.py`` states the **design** (16 cells, 24 generation calls). This module
states the **spend**, which is a different number, because repair is a fourth call class
that the design does not mention: one repair per cell is eligible, so the design's 24 calls
sit inside a hard maximum of 40.

Why the authorisation is phase-specific and equals the derived maximum
----------------------------------------------------------------------
The previous probe was authorised at 400 calls against a 15-call plan. An authorisation
that exceeds its plan by 26x is not a budget; it authorises whatever happens. It is
recorded as a governance defect in :data:`GOVERNANCE_NOTES`, and the correction is
mechanical: :func:`phase_authorisation` refuses any budget that is not exactly the derived
hard maximum, so the number cannot be rounded up for comfort.

The frozen runtime
------------------
:data:`FROZEN_RUNTIME` is the Lead's freeze, copied verbatim and not re-derived here. Note
``num_ctx`` in particular: ``budget/probe.py`` sends it per call, and changing it between
calls forces a 24 GB model reload -- the cause of five 120 s timeouts in the budget probe.
It is held constant at the frozen rung and ``timeout_s`` is generous.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from evaluation.syntax_gate.candidates import CANDIDATE_IDS

from .core import PROTOCOL_STAGES, GenerationProtocol, StageKind

__all__ = [
    "FROZEN_RUNTIME",
    "TOTAL_GENERATION_ALLOWANCE",
    "PROTOCOL_TOKEN_SPLIT",
    "REPAIR_MAX_TOKENS",
    "CallLedger",
    "derive_call_ledger",
    "phase_authorisation",
    "GOVERNANCE_NOTES",
    "PHASE_SCOPE",
]

#: The Lead's freeze. Copied, not re-derived.
FROZEN_RUNTIME: Mapping[str, Any] = {
    "server": "2 x 16384 slots (llama-server -c 32768 -np 2)",
    "client_workers": 2,
    "num_ctx": 16384,
    "model": "gemma4:31b",
    "model_digest": "6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7",
    "temperature": 0.0,
    "timeout_s": 600,
    "curriculum_size": 5,
    "curriculum_ids": (
        "binding_chain_000",
        "quantifier_scope_000",
        "distribution_law_000",
        "dimensional_algebra_000",
        "transformation_chain_000",
    ),
    "completion_allowance": 6144,
    "safety_reserve": 256,
    "allowed_truncation": 0,
    "measured_prompt_eval_count_worst_task": {
        "task": "transformation_chain_022",
        "A_v0_labelled_linear": 1880,
        "B_v1_labelled_linear_simplified": 1887,
        "C_prefix_sexpr": 2074,
        "D_constrained_json_graph": 4907,
        "SE_control": 1831,
        "ceiling": 9984,
        "worst_headroom": {"condition": "D_constrained_json_graph", "headroom": 5077},
        "headroom_check": "4907 + 6144 + 256 = 11307 <= 16384",
    },
    "commit": "21687cf",
    "tag": "hml-m2-context-budget",
}

#: Total generated tokens, matched across protocols. The match is the point: an arm allowed
#: more total generation would win on budget rather than on protocol.
TOTAL_GENERATION_ALLOWANCE = 6144

PROTOCOL_TOKEN_SPLIT: Mapping[GenerationProtocol, Mapping[str, int]] = {
    GenerationProtocol.DIRECT_FORMAL: {"formalise": 6144},
    GenerationProtocol.DRAFT_THEN_FORMAL: {"draft": 2048, "formalise": 4096},
}

#: v1's split, kept so the retained v1 records remain interpretable. It was rejected as a
#: syntax measurement: 56 of 76 generation events hit ``finish_reason="length"`` with
#: ``eval_count`` capping at exactly 2048, and all 8 draft stages hit the 768 cap, so that
#: arm was really "truncated draft, then formalise". The table measured the completion
#: allowance, not the representation.
SUPERSEDED_V1_TOKEN_SPLIT: Mapping[str, Mapping[str, int]] = {
    "DIRECT_FORMAL": {"formalise": 2048},
    "DRAFT_THEN_FORMAL": {"draft": 768, "formalise": 1280},
    "repair": {"max": 1024},
    "num_ctx": {"per_slot": 8192},
}

#: Repair is a separate allowance and is **not** inside the matched total. It is charged
#: only after an eligible formal attempt has already failed, so it cannot inflate an arm
#: that was succeeding.
REPAIR_MAX_TOKENS = 2048

PHASE_SCOPE = (
    "ACQ0 protocol calibration v2 (16384-token slot, 6144-token completion allowance): "
    "4 candidates x 2 fresh non-evaluation tasks x {DIRECT_FORMAL, DRAFT_THEN_FORMAL}, "
    "curriculum 5, plus at most one repair per cell. Supersedes the v1 run, which is "
    "retained on disk as an invalid-measurement record."
)

GOVERNANCE_NOTES: tuple[str, ...] = (
    "the budget probe was authorised at 400 calls against a 15-call plan. A 26x margin "
    "authorises whatever happens rather than a specific study; recorded here as a "
    "governance defect and corrected by phase_authorisation refusing any budget that is "
    "not exactly the derived hard maximum.",
    "this authorisation is phase-specific. The budget-probe authorisation is not reused: "
    "an authorisation carried across phases loses the connection between the number and "
    "the plan it was written for.",
    "the v1 authorisation (40 calls, 8192-token slot, 2048-token allowance) is NOT "
    "reused. v2 is a different experiment on a different runtime; carrying an "
    "authorisation across runtimes would attach a spend to a plan it was not written for. "
    "The derived maximum is again 40 because the matrix is unchanged -- an identical "
    "number, a new authorisation.",
    "the hard maximum is derived, not chosen. It is not a round number and must not be "
    "rounded to one.",
)


@dataclass(frozen=True)
class CallLedger:
    """Every call class, counted before execution."""

    conditions: int
    direct_generation: int
    draft_generation: int
    formalisation: int
    max_repair: int

    @property
    def generation_total(self) -> int:
        """Draft + formalisation. ``direct_generation`` is a *subset* of formalisation."""
        return self.draft_generation + self.formalisation

    @property
    def hard_maximum_total(self) -> int:
        return self.generation_total + self.max_repair

    def to_dict(self) -> dict[str, Any]:
        return {
            "conditions": self.conditions,
            "direct_generation_invocations": self.direct_generation,
            "draft_generation_invocations": self.draft_generation,
            "formalisation_invocations": self.formalisation,
            "max_eligible_repair_invocations": self.max_repair,
            "generation_total": self.generation_total,
            "hard_maximum_total": self.hard_maximum_total,
            "arithmetic": (
                f"{self.draft_generation} draft + {self.formalisation} formalisation "
                f"(of which {self.direct_generation} are the DIRECT_FORMAL arm's only "
                f"call) + {self.max_repair} repair = {self.hard_maximum_total}"
            ),
            "note": (
                "direct_generation is a subset of formalisation, not an addend. Adding it "
                "again would double-count the DIRECT_FORMAL arm."
            ),
        }


def derive_call_ledger(
    protocols: tuple[GenerationProtocol, ...] = (
        GenerationProtocol.DIRECT_FORMAL,
        GenerationProtocol.DRAFT_THEN_FORMAL,
    ),
    *,
    tasks: int = 2,
    conditions_per_protocol: int | None = None,
) -> CallLedger:
    """Count the four call classes from :data:`~.core.PROTOCOL_STAGES`, never by hand."""
    per_protocol = (
        conditions_per_protocol
        if conditions_per_protocol is not None
        else len(CANDIDATE_IDS) * tasks
    )
    cells = per_protocol * len(protocols)
    draft = sum(
        per_protocol
        for p in protocols
        for s in PROTOCOL_STAGES[p]
        if s in (StageKind.DRAFT, StageKind.PLAN)
    )
    formalise = sum(
        per_protocol for p in protocols for s in PROTOCOL_STAGES[p] if s is StageKind.FORMALISE
    )
    direct = per_protocol if GenerationProtocol.DIRECT_FORMAL in protocols else 0
    return CallLedger(
        conditions=cells,
        direct_generation=direct,
        draft_generation=draft,
        formalisation=formalise,
        max_repair=cells,
    )


def phase_authorisation(
    ledger: CallLedger,
    *,
    authorised_by: str,
    conformance_state: str,
    granted_utc: str = "",
):
    """A :class:`~.runner.LiveCallAuthorisation` for exactly this phase's hard maximum.

    Constructed here rather than at the call site so the budget cannot be typed in. The
    only number this function will accept is the one the ledger derived.
    """
    from .runner import LiveCallAuthorisation

    return LiveCallAuthorisation(
        authorised_by=authorised_by,
        call_budget=ledger.hard_maximum_total,
        scope=PHASE_SCOPE,
        conformance_state=conformance_state,
        granted_utc=granted_utc,
        citation=(
            f"commit {FROZEN_RUNTIME['commit']} / tag {FROZEN_RUNTIME['tag']}; "
            f"budget derived: {ledger.to_dict()['arithmetic']}"
        ),
    )
