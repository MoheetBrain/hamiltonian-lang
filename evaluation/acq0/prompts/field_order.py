"""Field order is an inductive bias, not a presentation choice.

The observation being defended against
--------------------------------------
Tam et al. report JSON-mode outputs in which the answer field was emitted **before** the
reasoning field. A model that must emit ``"answer"`` first has to answer first: the
schema removed chain-of-thought by ordering alone, with no instruction to that effect and
no visible symptom. The output was valid JSON every time.

That failure applies directly to candidate D, whose surface is a JSON object, and applies
in weaker form to every candidate: an encoding whose result statement precedes its
declarations forces the model to commit to a result before it has written down what the
symbols mean.

The rule
--------
Semantic prerequisites precede result fields::

    assumptions -> declarations -> constraints -> derivation/state -> result

:func:`validate_field_order` enforces it. The order is a **partial** order, not a fixed
sequence: what is required is that no result field precede a prerequisite, not that a
prompt list every field.

The probe, and why it is developmental only
-------------------------------------------
:data:`CANDIDATE_D_FIELD_ORDER_PROBE` specifies one comparison — semantic-first against
answer-first, candidate D, development subset — whose purpose is to find out whether the
effect reproduces on this model and this corpus. It is developmental because it touches
tasks that must stay uncontaminated if they are ever to score the gate, and because a
probe that has not yet run cannot license a change to the official protocol.

Until it runs, :func:`official_gate_field_order` returns semantic-first and
:func:`assert_gate_field_order` refuses answer-first. That default is the conservative
one: answer-first is the arrangement with a published mechanism for harm, so it carries
the burden of proof.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

__all__ = [
    "FieldRole",
    "SEMANTIC_PREREQUISITES",
    "RESULT_FIELDS",
    "CANONICAL_FIELD_ORDER",
    "ANSWER_FIRST_ORDER",
    "FieldOrderArm",
    "FieldOrderViolation",
    "AnswerFirstNotLicensed",
    "validate_field_order",
    "order_for_arm",
    "official_gate_field_order",
    "assert_gate_field_order",
    "CANDIDATE_D_FIELD_ORDER_PROBE",
    "field_order_instruction",
]


class FieldRole(StrEnum):
    """What a field contributes. Ordering constraints are stated over roles."""

    #: What is taken as given without proof. Must precede anything that relies on it.
    ASSUMPTIONS = "assumptions"
    #: Symbols, their types and their epistemic status.
    DECLARATIONS = "declarations"
    #: Obligations, laws and relations that hold over the declared symbols.
    CONSTRAINTS = "constraints"
    #: The worked manipulation, or the state the encoding puts the problem in.
    DERIVATION = "derivation"
    #: The result: the objective, the query, the final answer.
    RESULT = "result"


#: Roles that must be established before a result can honestly be stated.
SEMANTIC_PREREQUISITES: tuple[FieldRole, ...] = (
    FieldRole.ASSUMPTIONS,
    FieldRole.DECLARATIONS,
    FieldRole.CONSTRAINTS,
    FieldRole.DERIVATION,
)

#: Roles that state an outcome.
RESULT_FIELDS: frozenset[FieldRole] = frozenset({FieldRole.RESULT})

#: The required order. Every prompt this package builds emits fields in this sequence.
CANONICAL_FIELD_ORDER: tuple[FieldRole, ...] = (*SEMANTIC_PREREQUISITES, FieldRole.RESULT)

#: The arrangement the paper observed doing harm. Defined here so the probe can be run
#: **and** so a reader can see exactly what is being refused, rather than trusting a
#: description of it.
ANSWER_FIRST_ORDER: tuple[FieldRole, ...] = (FieldRole.RESULT, *SEMANTIC_PREREQUISITES)


class FieldOrderArm(StrEnum):
    SEMANTIC_FIRST = "SEMANTIC_FIRST"
    ANSWER_FIRST = "ANSWER_FIRST"


class FieldOrderViolation(ValueError):
    """A result field precedes a semantic prerequisite."""


class AnswerFirstNotLicensed(AssertionError):
    """Answer-first was requested for an official gate run without evidence."""


def validate_field_order(order: Sequence[FieldRole]) -> None:
    """Raise unless every result field follows every prerequisite present in ``order``.

    Duplicates and omissions are permitted — the constraint is relative position, not a
    fixed template. What is refused is a result stated before the meaning it depends on.
    """
    seen_result: FieldRole | None = None
    for role in order:
        if role in RESULT_FIELDS:
            seen_result = role
            continue
        if seen_result is not None:
            raise FieldOrderViolation(
                f"{role} appears after the result field {seen_result}. Semantic "
                "prerequisites must precede result fields: a schema that puts the "
                "answer first induces direct answering in place of chain-of-thought, "
                "with valid output and degraded content."
            )


def order_for_arm(arm: FieldOrderArm) -> tuple[FieldRole, ...]:
    return (
        CANONICAL_FIELD_ORDER
        if arm is FieldOrderArm.SEMANTIC_FIRST
        else ANSWER_FIRST_ORDER
    )


def official_gate_field_order() -> tuple[FieldRole, ...]:
    """What the official ACQ0 gate uses. Semantic-first, and validated on every call."""
    validate_field_order(CANONICAL_FIELD_ORDER)
    return CANONICAL_FIELD_ORDER


def assert_gate_field_order(
    arm: FieldOrderArm, *, evidence: Mapping[str, Any] | None = None
) -> None:
    """Permit answer-first in the official gate only on recorded evidence of no harm.

    ``evidence`` must be the probe's own result and must state, in these exact keys, that
    answer-first did not degrade semantic preservation::

        {"probe_run": True, "degrades_semantic_preservation": False, "citation": "..."}

    Anything else — including a missing key, an unrun probe, or a citation-free claim —
    is refused. The asymmetry is intentional: semantic-first needs no evidence because it
    is the arrangement with no published mechanism for harm.
    """
    if arm is FieldOrderArm.SEMANTIC_FIRST:
        return
    e = dict(evidence or {})
    if not e.get("probe_run"):
        raise AnswerFirstNotLicensed(
            "answer-first is refused in the official gate: the field-order probe has "
            "not been run, so there is no evidence it does not degrade semantic "
            "preservation. Refusing is the conservative default — this arrangement is "
            "the one with a published mechanism for harm."
        )
    if e.get("degrades_semantic_preservation") is not False:
        raise AnswerFirstNotLicensed(
            "answer-first is refused in the official gate: the probe did not record "
            "'degrades_semantic_preservation': False. An unmeasured or positive result "
            "is not a licence."
        )
    if not str(e.get("citation", "")).strip():
        raise AnswerFirstNotLicensed(
            "answer-first requires the probe artefact to be cited; an uncited claim of "
            "no degradation is not evidence"
        )


@dataclass(frozen=True)
class FieldOrderProbe:
    """One developmental comparison. Specification only — running it is separate."""

    candidate_id: str
    arms: tuple[FieldOrderArm, ...]
    #: Which task pool the probe may draw from. Never the gate or replication stages.
    task_pool: str
    hypothesis: str
    decision_rule: str
    #: What may change as a result. Deliberately narrow.
    scope_of_conclusion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "arms": [str(a) for a in self.arms],
            "task_pool": self.task_pool,
            "hypothesis": self.hypothesis,
            "decision_rule": self.decision_rule,
            "scope_of_conclusion": self.scope_of_conclusion,
        }


#: The one field-order probe this milestone specifies. Candidate D only: it is the JSON
#: candidate, so it is the one whose surface can order the answer before the reasoning in
#: exactly the way the paper observed.
CANDIDATE_D_FIELD_ORDER_PROBE = FieldOrderProbe(
    candidate_id="D_constrained_json_graph",
    arms=(FieldOrderArm.SEMANTIC_FIRST, FieldOrderArm.ANSWER_FIRST),
    task_pool="demonstration-stage tasks only (never G2/G3/G4/replication)",
    hypothesis=(
        "emitting the result field before the declarations and constraints reduces "
        "exact semantic preservation without reducing parse success -- the paper's "
        "0.148%-parse-error / 38-point-gap pattern, reproduced on this corpus"
    ),
    decision_rule=(
        "answer-first is excluded from the official gate unless the probe records "
        "'degrades_semantic_preservation': False with a cited artefact. An unrun probe "
        "leaves semantic-first in place; it does not leave the question open."
    ),
    scope_of_conclusion=(
        "candidate D's prompt field order, on this model and this corpus. It licenses "
        "no claim about candidates A/B/C and no claim about JSON in general."
    ),
)


def field_order_instruction(order: Sequence[FieldRole] | None = None) -> str:
    """The prose that puts the required order into a prompt.

    Emitted from :data:`CANONICAL_FIELD_ORDER` rather than written out, so the
    instruction and the validator can never disagree about what the order is.
    """
    seq = tuple(order) if order is not None else official_gate_field_order()
    described = {
        FieldRole.ASSUMPTIONS: "what you are taking as given",
        FieldRole.DECLARATIONS: "every symbol, with its type and its epistemic status",
        FieldRole.CONSTRAINTS: "the laws, relations and obligations over those symbols",
        FieldRole.DERIVATION: "the manipulation that gets from those to the result",
        FieldRole.RESULT: "the result the question asks for",
    }
    steps = "\n".join(f"  {i}. {described[r]}" for i, r in enumerate(seq, 1))
    return f"Work in this order, and do not state a later item before an earlier one:\n{steps}"
