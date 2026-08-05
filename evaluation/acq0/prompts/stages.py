"""Per-stage prompt construction for the three protocols.

The design rule that makes the arms comparable
----------------------------------------------
The formalisation stage is built **from the tournament's own prompt**
(``evaluation.syntax_gate.prompts.build_prompt``) rather than from a copy of it. Two
consequences, and both are load-bearing:

* ``DIRECT_FORMAL`` is byte-identical to the protocol the tournament runs today. It is
  the reference arm, so if it were a paraphrase the comparison would be against a
  protocol nobody is using.
* The candidate specifications cannot drift. A forked spec would eventually differ from
  the one the gate uses, and every protocol conclusion would then be about a syntax
  reference that no gate run ever saw.

``DRAFT_THEN_FORMAL`` and ``PLAN_THEN_FORMAL`` stage two are therefore *the same prompt*
plus one labelled block containing the model's own upstream text. Nothing else differs.

Why stage two keeps the problem statement
-----------------------------------------
A conversion-only stage two ("turn this into JSON") would drop any content the draft
failed to mention, and a preservation loss caused by that dropout would be indistinguish-
able from a loss caused by format restriction. Keeping the problem costs prompt tokens —
recorded, and visible in the ledger — and buys an interpretable contrast.

Why the upstream block is labelled non-authoritative
----------------------------------------------------
The draft is the model's own text and can be wrong. Presenting it as established fact
would convert a stage-one error into a stage-two constraint, which is a way of making the
two-stage arm look worse than it is. The block says what it is and what it is not.

Every builder here runs :func:`~evaluation.acq0.protocols.oracle.assert_no_oracle` before
returning. A prompt carrying the answer key cannot leave this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evaluation.corpus.cso import ANSWER_CLOSE, ANSWER_OPEN
from evaluation.syntax_gate.candidates import CANDIDATES, SE_CONTROL, SyntaxAdapter
from evaluation.syntax_gate.prompts import build_prompt
from evaluation.syntax_gate.tasks import GateTask

from ..protocols.core import PROTOCOL_STAGES, GenerationProtocol, StageKind
from ..protocols.oracle import (
    assert_demonstrations_disjoint,
    assert_no_oracle,
    stage_information,
)
from .field_order import (
    FieldOrderArm,
    field_order_instruction,
    order_for_arm,
    validate_field_order,
)
from .sensitivity import render_phrasing

__all__ = [
    "StagePrompt",
    "PromptStructureChanged",
    "DEFAULT_PHRASING",
    "PLAN_LINE_BUDGET",
    "UPSTREAM_HEADER",
    "draft_prompt",
    "plan_prompt",
    "formalise_prompt",
    "build_stage_prompt",
    "with_phrasing",
]

#: The phrasing the tournament already uses. Named so a probe result can say which arm
#: was the incumbent rather than "the first one".
DEFAULT_PHRASING = "P1_imperative"

#: The plan stage's cap. Bounded on purpose: an unbounded first stage lets the two-stage
#: arm win by emitting more text, which is a different explanation from "it helped to
#: separate reasoning from formatting" and would be indistinguishable without the cap.
PLAN_LINE_BUDGET = 12

UPSTREAM_HEADER = "YOUR EARLIER NOTES (your own working, not a given -- correct it if it is wrong)"


class PromptStructureChanged(RuntimeError):
    """The tournament prompt no longer has the block structure this module edits.

    Raised rather than silently returning an unmodified prompt: a phrasing probe that
    quietly failed to change the phrasing would report three identical arms as evidence
    of insensitivity.
    """


@dataclass(frozen=True)
class StagePrompt:
    """One stage's prompt, plus everything needed to reconstruct why it looks like this."""

    protocol: GenerationProtocol
    stage: StageKind
    condition: str
    task_id: str
    system: str
    user: str
    phrasing_id: str = DEFAULT_PHRASING
    field_order_arm: FieldOrderArm = FieldOrderArm.SEMANTIC_FIRST
    curriculum_size: int = 0
    #: True when this stage's prompt names a target syntax. False for draft and plan —
    #: that absence is the manipulation.
    format_restricted: bool = True
    demonstration_ids: tuple[str, ...] = ()

    @property
    def information(self) -> frozenset:
        return stage_information(
            self.stage,
            curriculum_size=self.curriculum_size,
            has_upstream=UPSTREAM_HEADER in self.user,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": str(self.protocol),
            "stage": str(self.stage),
            "condition": self.condition,
            "task_id": self.task_id,
            "phrasing_id": self.phrasing_id,
            "field_order_arm": str(self.field_order_arm),
            "curriculum_size": self.curriculum_size,
            "format_restricted": self.format_restricted,
            "demonstration_ids": list(self.demonstration_ids),
            "system_characters": len(self.system),
            "user_characters": len(self.user),
        }


# ---------------------------------------------------------------------------
# Stage one: format-unrestricted
# ---------------------------------------------------------------------------

_UNRESTRICTED_SYSTEM = (
    "You are solving a mathematics problem. Be precise. Write in ordinary prose and "
    "notation of your own choosing. Do not use any particular file format, and do not "
    "produce a fenced code block."
)


def _unrestricted_user(task: GateTask, arm: FieldOrderArm, body: str) -> str:
    order = order_for_arm(arm)
    if arm is FieldOrderArm.SEMANTIC_FIRST:
        # The answer-first arm violates this by construction -- that is what it probes --
        # so the check applies only to the arm that claims to satisfy it.
        validate_field_order(order)
    return "\n\n".join(
        [
            f"PROBLEM\n{task.cso.prose}",
            f"QUESTION\n{task.cso.question}",
            field_order_instruction(order),
            body,
            f"Give the final answer wrapped in {ANSWER_OPEN} ... {ANSWER_CLOSE}, "
            f"as {task.cso.answer.render_instruction()}",
        ]
    )


def draft_prompt(
    task: GateTask,
    condition: str,
    *,
    field_order_arm: FieldOrderArm = FieldOrderArm.SEMANTIC_FIRST,
) -> StagePrompt:
    """Stage one of ``DRAFT_THEN_FORMAL``: unrestricted, unbounded, no target syntax.

    ``condition`` is recorded but never rendered. The draft must not be able to differ
    between candidates: if it did, the two-stage arm would be four different first stages
    and its result would not be a fact about the protocol.
    """
    body = (
        "Work the problem out. State your reasoning in full. You are not being asked "
        "for any particular notation at this step."
    )
    user = _unrestricted_user(task, field_order_arm, body)
    assert_no_oracle(user, task.cso, where=f"draft_prompt[{task.id}]")
    return StagePrompt(
        protocol=GenerationProtocol.DRAFT_THEN_FORMAL,
        stage=StageKind.DRAFT,
        condition=condition,
        task_id=task.id,
        system=_UNRESTRICTED_SYSTEM,
        user=user,
        field_order_arm=field_order_arm,
        format_restricted=False,
    )


def plan_prompt(
    task: GateTask,
    condition: str,
    *,
    field_order_arm: FieldOrderArm = FieldOrderArm.SEMANTIC_FIRST,
    line_budget: int = PLAN_LINE_BUDGET,
) -> StagePrompt:
    """Stage one of ``PLAN_THEN_FORMAL``: unrestricted in form, bounded in length."""
    body = (
        f"Write a compact plan of at most {line_budget} short lines, one fact per line. "
        "No paragraphs and no worked arithmetic -- name the objects, their types, what "
        "is assumed, what constrains them, and what must be produced."
    )
    user = _unrestricted_user(task, field_order_arm, body)
    assert_no_oracle(user, task.cso, where=f"plan_prompt[{task.id}]")
    return StagePrompt(
        protocol=GenerationProtocol.PLAN_THEN_FORMAL,
        stage=StageKind.PLAN,
        condition=condition,
        task_id=task.id,
        system=_UNRESTRICTED_SYSTEM,
        user=user,
        field_order_arm=field_order_arm,
        format_restricted=False,
    )


# ---------------------------------------------------------------------------
# Stage two: the tournament's own prompt, plus at most one upstream block
# ---------------------------------------------------------------------------

_METHOD_MARKER = "\n\nMETHOD\n"
_QUESTION_MARKER = "\n\nQUESTION\n"
_PROBLEM_MARKER = "\n\nPROBLEM\n"


def with_phrasing(user: str, phrasing_id: str, condition: str) -> str:
    """Replace the tournament prompt's METHOD body with an alternative phrasing.

    Operates on the assembled block structure rather than on a private constant, so a
    change to the tournament's method text does not need mirroring here. If the structure
    is gone, this raises: an unmodified prompt returned from a phrasing probe would look
    like evidence of insensitivity.
    """
    if phrasing_id == DEFAULT_PHRASING:
        return user
    if condition == SE_CONTROL:
        raise ValueError(
            "the phrasing probe applies to a candidate surface; the structured-English "
            "control has no fence tag and no encoding instruction to reword"
        )
    start = user.find(_METHOD_MARKER)
    end = user.find(_QUESTION_MARKER, start + 1) if start >= 0 else -1
    if start < 0 or end < 0:
        raise PromptStructureChanged(
            "the tournament prompt no longer contains a METHOD block followed by a "
            "QUESTION block; the phrasing substitution cannot be applied and must not "
            "be skipped silently"
        )
    tag = CANDIDATES[condition].fence_tags[0]
    replacement = f"{_METHOD_MARKER}{render_phrasing(phrasing_id, tag)}"
    return user[:start] + replacement + user[end:]


def _insert_upstream(user: str, upstream: str) -> str:
    """Put the model's own earlier text immediately after the PROBLEM block.

    After the problem so it reads as working on that problem, and before the METHOD block
    so the instruction the model acts on is still the last thing it reads.
    """
    marker = user.find(_METHOD_MARKER)
    if marker < 0:
        raise PromptStructureChanged(
            "the tournament prompt has no METHOD block, so there is no defined place to "
            "insert the upstream draft"
        )
    block = f"\n\n{UPSTREAM_HEADER}\n{upstream.strip()}"
    return user[:marker] + block + user[marker:]


def formalise_prompt(
    task: GateTask,
    condition: str,
    protocol: GenerationProtocol,
    *,
    upstream: str | None = None,
    demonstrations: list[GateTask] | None = None,
    adapters: dict[str, SyntaxAdapter | None] | None = None,
    phrasing_id: str = DEFAULT_PHRASING,
    field_order_arm: FieldOrderArm = FieldOrderArm.SEMANTIC_FIRST,
) -> StagePrompt:
    """Stage two (or the only stage): the tournament prompt, optionally plus the draft.

    ``upstream`` is required for the two-stage protocols and refused for
    ``DIRECT_FORMAL``. Accepting it for the one-stage protocol would silently create a
    fourth, undeclared arm.
    """
    stages = PROTOCOL_STAGES[protocol]
    two_stage = len(stages) > 1
    if two_stage and not (upstream or "").strip():
        raise ValueError(
            f"{protocol} formalisation requires the upstream stage's output; without it "
            "this is DIRECT_FORMAL wearing a two-stage label, and its token ledger "
            "would charge a draft that never informed anything"
        )
    if not two_stage and (upstream or "").strip():
        raise ValueError(
            "DIRECT_FORMAL has no upstream stage; supplying one creates an undeclared "
            "fourth arm whose result would be attributed to DIRECT_FORMAL"
        )

    demos = demonstrations or []
    # Question one: is a demonstration actually this task? Answered on the content hash,
    # because ids can differ while content does not. A substring scan cannot answer this
    # on a corpus that reuses module and symbol names across tasks by design.
    assert_demonstrations_disjoint(task, demos)

    base = build_prompt(task, condition, demos, adapters)
    user = with_phrasing(base.user, phrasing_id, condition)

    # Question two: did this harness compose any of the answer key into the prompt?
    # Scanned over the **task-composed** portion -- the prompt rebuilt with zero
    # demonstrations -- for two separate reasons:
    #
    #  * demonstrations are other tasks' content by design, and question one has already
    #    established they are not this one. Scanning them here produced 281 false alarms
    #    in 320 gate prompts when measured, because the corpus shares module and symbol
    #    names between tasks;
    #  * the upstream block is the model's own text, produced under a stage-one prompt
    #    this module already asserted is oracle-free. A model that solved the problem
    #    writes the gold answer into its own draft, and flagging that would accuse the
    #    harness of revealing an answer the model derived.
    #
    # Rebuilding with no demonstrations is cheap precisely when the real build is not:
    # it performs no adapter rendering at all.
    task_composed = with_phrasing(
        build_prompt(task, condition, [], adapters).user, phrasing_id, condition
    )
    assert_no_oracle(
        task_composed, task.cso, where=f"formalise_prompt[{condition}/{task.id}]"
    )
    if upstream:
        user = _insert_upstream(user, upstream)
    return StagePrompt(
        protocol=protocol,
        stage=StageKind.FORMALISE,
        condition=condition,
        task_id=task.id,
        system=base.system,
        user=user,
        phrasing_id=phrasing_id,
        field_order_arm=field_order_arm,
        curriculum_size=base.curriculum_size,
        format_restricted=condition != SE_CONTROL,
        demonstration_ids=base.demonstration_ids,
    )


def build_stage_prompt(
    task: GateTask,
    condition: str,
    protocol: GenerationProtocol,
    stage: StageKind,
    **kw: Any,
) -> StagePrompt:
    """Dispatch to the right builder. One entry point for the runner."""
    if stage not in PROTOCOL_STAGES[protocol]:
        raise ValueError(f"{protocol} does not run stage {stage}")
    if stage is StageKind.DRAFT:
        return draft_prompt(task, condition, **kw)
    if stage is StageKind.PLAN:
        return plan_prompt(task, condition, **kw)
    return formalise_prompt(task, condition, protocol, **kw)
