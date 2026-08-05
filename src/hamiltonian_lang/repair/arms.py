"""The three feedback arms, and the payload each is allowed to carry.

Why the arms are constructed here rather than at the call site
--------------------------------------------------------------
The comparison this whole subsystem exists to make is *between arms*. If ``NO_FEEDBACK``
quietly receives the diagnostic — because a prompt template interpolated it, or because a
caller passed the wrong variable — then the contrast is between two arms that both saw the
error, the measured difference collapses toward zero, and nothing in the output shows why.

So payload construction is a single function with a single definition per arm, and
:func:`build_payload` **verifies its own output**: the ``NO_FEEDBACK`` payload is checked
not to contain the diagnostic code, and the ``RAW_DIAGNOSTIC`` payload is checked not to
contain any line of the plan. A violated check raises :class:`ArmContamination`.

COCOGEN's ablation is the reason ``RAW_DIAGNOSTIC`` exists as its own arm rather than as
the control for ``CHAIN_OF_REPAIR``: compiler feedback alone did not deliver the full
gain. Without the middle arm, a positive ``CHAIN_OF_REPAIR`` result cannot be attributed
to retrieval and role separation rather than to the diagnostic simply being present.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..context_broker import RetrievedContext
from ..improvement.diagnostics import StructuredDiagnostic
from .plan import NoPlan, RepairPlan

__all__ = [
    "FeedbackArm",
    "ARM_DESCRIPTION",
    "ArmContamination",
    "FeedbackPayload",
    "build_payload",
]


class FeedbackArm(StrEnum):
    """What the Learner is shown on a repair turn. Separately identified in every result."""

    #: The broken output and the task, and nothing about why it failed. The floor: it
    #: measures resampling, which is what an unassisted retry actually is.
    NO_FEEDBACK = "NO_FEEDBACK"
    #: The broken output plus the compiler's rendered diagnostic. No retrieval, no plan.
    RAW_DIAGNOSTIC = "RAW_DIAGNOSTIC"
    #: The broken output, the structured diagnostic, the retrieved project context, and
    #: the Teacher's plan. Role-separated: the plan comes from a different role than the
    #: one that produced the broken output.
    CHAIN_OF_REPAIR = "CHAIN_OF_REPAIR"


ARM_DESCRIPTION: dict[FeedbackArm, str] = {
    FeedbackArm.NO_FEEDBACK: (
        "resample with no information about the failure; the floor against which any "
        "feedback effect is measured"
    ),
    FeedbackArm.RAW_DIAGNOSTIC: (
        "the compiler diagnostic verbatim; isolates 'the error was shown' from "
        "'the error was diagnosed and contextualised'"
    ),
    FeedbackArm.CHAIN_OF_REPAIR: (
        "structured diagnostic, retrieved project context and a role-separated repair "
        "plan; the treatment"
    ),
}


class ArmContamination(AssertionError):
    """A payload contained information its arm is not permitted to carry."""


@dataclass(frozen=True)
class FeedbackPayload:
    """Exactly what one repair turn shows the Learner, and under which arm."""

    arm: FeedbackArm
    broken_output: str
    #: Rendered diagnostic. Empty under ``NO_FEEDBACK``.
    diagnostic_text: str = ""
    #: Rendered retrieved context. Empty except under ``CHAIN_OF_REPAIR``.
    context_text: str = ""
    #: Rendered plan, or the recorded reason there is none. Empty except under
    #: ``CHAIN_OF_REPAIR``.
    plan_text: str = ""

    def render(self) -> str:
        parts = ["--- output under repair ---", self.broken_output]
        if self.diagnostic_text:
            parts += ["--- diagnostic ---", self.diagnostic_text]
        if self.context_text:
            parts += ["--- retrieved project context ---", self.context_text]
        if self.plan_text:
            parts += ["--- repair plan (from the Teacher; apply it) ---", self.plan_text]
        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": str(self.arm),
            "broken_output": self.broken_output,
            "diagnostic_text": self.diagnostic_text,
            "context_text": self.context_text,
            "plan_text": self.plan_text,
        }


def build_payload(
    arm: FeedbackArm,
    *,
    broken_output: str,
    diagnostic: StructuredDiagnostic | None = None,
    context: RetrievedContext | None = None,
    plan: RepairPlan | NoPlan | None = None,
) -> FeedbackPayload:
    """Assemble the payload for one arm, then verify the arm's exclusions hold.

    Raises :class:`ArmContamination` rather than trimming: silently removing leaked
    material would hide the bug that put it there, and the next caller would reintroduce
    it. A contaminated arm is a broken experiment and should stop the run.
    """
    if not isinstance(arm, FeedbackArm):
        raise TypeError(f"arm must be a FeedbackArm member, got {type(arm).__name__}")

    if arm is FeedbackArm.NO_FEEDBACK:
        payload = FeedbackPayload(arm=arm, broken_output=broken_output)
    elif arm is FeedbackArm.RAW_DIAGNOSTIC:
        payload = FeedbackPayload(
            arm=arm,
            broken_output=broken_output,
            diagnostic_text=diagnostic.render() if diagnostic is not None else "",
        )
    else:
        if isinstance(plan, RepairPlan):
            plan_text = plan.render()
        elif isinstance(plan, NoPlan):
            plan_text = (
                f"no repair plan was produced ({plan.reason}). Repair from the "
                "diagnostic alone."
            )
        else:
            plan_text = ""
        payload = FeedbackPayload(
            arm=arm,
            broken_output=broken_output,
            diagnostic_text=diagnostic.render() if diagnostic is not None else "",
            context_text=context.render() if context is not None else "",
            plan_text=plan_text,
        )

    _assert_arm_exclusions(payload, diagnostic=diagnostic, plan=plan)
    return payload


def _assert_arm_exclusions(
    payload: FeedbackPayload,
    *,
    diagnostic: StructuredDiagnostic | None,
    plan: RepairPlan | NoPlan | None,
) -> None:
    rendered = payload.render()

    if payload.arm is FeedbackArm.NO_FEEDBACK:
        if payload.diagnostic_text or payload.context_text or payload.plan_text:
            raise ArmContamination(
                "NO_FEEDBACK payload carries diagnostic, context or plan text; the arm "
                "is defined by their absence"
            )
        if diagnostic is not None and diagnostic.code and diagnostic.code in rendered:
            raise ArmContamination(
                f"NO_FEEDBACK payload contains the diagnostic code {diagnostic.code}; "
                "the no-feedback floor would then measure feedback"
            )
        return

    if payload.arm is FeedbackArm.RAW_DIAGNOSTIC:
        if payload.context_text or payload.plan_text:
            raise ArmContamination(
                "RAW_DIAGNOSTIC payload carries retrieved context or a plan; the arm "
                "exists precisely to isolate the diagnostic from both"
            )
        if isinstance(plan, RepairPlan):
            for step in plan.repair_steps:
                if step.strip() and step.strip() in rendered:
                    raise ArmContamination(
                        "RAW_DIAGNOSTIC payload contains a repair-plan step; the "
                        "contrast with CHAIN_OF_REPAIR would then be uninterpretable"
                    )
