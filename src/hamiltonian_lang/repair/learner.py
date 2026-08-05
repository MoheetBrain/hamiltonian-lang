"""The Repair Learner — the role that applies a plan and produces the next candidate.

The Learner is deliberately thin. It receives a :class:`~.arms.FeedbackPayload` and
returns text; it does not decide what feedback it gets, and it does not know which arm it
is in beyond what the payload carries. Keeping the arm logic out of the Learner is what
makes the three arms comparable: a Learner that behaved differently under
``CHAIN_OF_REPAIR`` for reasons of its own would confound the treatment with itself.

Nothing here calls a model. :class:`ScriptedRepairLearner` replays fixed responses so the
whole chain — retrieval, teaching, arm construction, budget enforcement, verification and
record-keeping — can be exercised end to end offline, with no provider and no sampling
variance. A live Learner is a separate implementation of the same Protocol, and the chain
driver refuses to run one unless explicitly allowed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .arms import FeedbackArm, FeedbackPayload

__all__ = [
    "RepairLearner",
    "LearnerScriptError",
    "ScriptedRepairLearner",
    "ScriptKey",
]

#: ``(task_id, arm, repair_turn_index)``. Keying on the arm is what lets one fixture
#: express "this task is repaired under CHAIN_OF_REPAIR but not under RAW_DIAGNOSTIC",
#: which is the whole shape of the measurement.
ScriptKey = tuple[str, FeedbackArm, int]


class LearnerScriptError(RuntimeError):
    """The script has no entry for the turn the chain asked for."""


@runtime_checkable
class RepairLearner(Protocol):
    """The Learner role."""

    name: str
    #: True if this Learner contacts a model or a network.
    live: bool

    def apply(self, *, task_id: str, turn: int, payload: FeedbackPayload) -> str: ...


@dataclass
class ScriptedRepairLearner:
    """A deterministic Learner. Contacts nothing; reports no token counts because it
    consumed none.

    ``strict_payload`` makes the fixture assert the arm contract from the Learner's side
    as well: under ``NO_FEEDBACK`` a script entry that depends on diagnostic text would be
    silently wrong, so the Learner refuses a payload whose arm does not match the key it
    was asked for.
    """

    script: Mapping[ScriptKey, str]
    name: str = "scripted"
    live: bool = False
    strict_payload: bool = True
    calls: list[ScriptKey] = field(default_factory=list)

    def apply(self, *, task_id: str, turn: int, payload: FeedbackPayload) -> str:
        key: ScriptKey = (task_id, payload.arm, turn)
        if self.strict_payload and payload.arm is FeedbackArm.NO_FEEDBACK:
            if payload.diagnostic_text or payload.context_text or payload.plan_text:
                raise LearnerScriptError(
                    f"{key}: a NO_FEEDBACK payload arrived carrying feedback text; the "
                    "arm contract was broken upstream"
                )
        try:
            out = self.script[key]
        except KeyError:
            raise LearnerScriptError(
                f"no scripted response for {key}; scripted keys: "
                f"{sorted((t, str(a), n) for t, a, n in self.script)}"
            ) from None
        self.calls.append(key)
        return out

    def call_count(self) -> int:
        return len(self.calls)
