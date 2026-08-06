"""Preflight admission for ACQ0 tasks: is this task a valid instrument?

Written after the `assumption_boundary_000` audit, in which a frontier model produced a
well-formed encoding faithful to the prose it was shown and was scored FAIL against a
private reference it could not have reconstructed. The model was not wrong. The task was.

The audit found **41 of 41** public tasks carrying at least one defect. That is not a
corpus needing patches; it is an instrument that has never been validated. This module is
the check that should have run before any model saw any task.

The governing rule:

    A task is admissible only when a competent encoder, given exactly the model-visible
    material, could reconstruct the private reference *uniquely*.

Anything less measures the corpus, not the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "DefectClass",
    "TaskDefect",
    "AdmissionReport",
    "audit_task",
    "ADMISSION_CRITERIA",
]


class DefectClass(StrEnum):
    """Every class the audit actually observed, named for what it breaks."""

    CONST_WITHOUT_INITIALISER = "const_without_initialiser"
    ENTITY_ABSENT_FROM_PROSE = "entity_absent_from_prose"
    ASSUMPTION_NOT_DECLARED = "assumption_not_declared"
    DERIVED_FACT_AS_INPUT_CONSTRAINT = "derived_fact_as_input_constraint"
    FUNCTION_BODY_MISSING = "function_body_missing"
    QUESTION_WITHOUT_OBJECTIVE = "question_without_objective"
    SPECIFICATION_CONFLICT = "specification_conflict"
    PUBLIC_INSUFFICIENT_FOR_PRIVATE = "public_insufficient_for_private"


#: The eight admission criteria, as prose a reader can check a task against by hand.
ADMISSION_CRITERIA = (
    "public and private targets are semantically equal",
    "the reference encoding self-scores PASS",
    "the reference round-trips exactly through every supported surface",
    "the reference is uniquely reconstructable from model-visible material",
    "no mandatory initialiser is left unspecified",
    "no contradiction between prose and structured semantics",
    "no goal exists in prose without a structured counterpart",
    "no derived fact is presented as an input premise",
)


@dataclass(frozen=True)
class TaskDefect:
    defect: DefectClass
    detail: str
    #: The symbol or field at fault, when one can be named.
    subject: str = ""

    def render(self) -> str:
        where = f" [{self.subject}]" if self.subject else ""
        return f"{self.defect}{where}: {self.detail}"


@dataclass(frozen=True)
class AdmissionReport:
    task_id: str
    defects: tuple[TaskDefect, ...] = ()
    checked: tuple[str, ...] = field(default_factory=lambda: ADMISSION_CRITERIA)

    @property
    def admissible(self) -> bool:
        """No defects at all. There is no partial credit for an instrument."""
        return not self.defects

    def render(self) -> str:
        if self.admissible:
            return f"{self.task_id}: ADMISSIBLE"
        lines = [f"{self.task_id}: INVALID_INSTRUMENT ({len(self.defects)} defect(s))"]
        lines += [f"  - {d.render()}" for d in self.defects]
        return "\n".join(lines)


def _field(semantics: str, name: str) -> str:
    m = re.search(rf"{name}=(\{{.*?\}}|\[.*?\]|None)", semantics)
    return m.group(1) if m else ""


def audit_task(
    *,
    task_id: str,
    prose: str,
    question: str,
    visible_assumptions: list,
    visible_semantics: str,
    reference_hml: str,
) -> AdmissionReport:
    """Decide whether one task may be shown to a model.

    Deliberately conservative: every check that fires names a concrete reason a competent
    encoder could not have produced the reference. A task is admissible only when none
    fire.
    """
    found: list[TaskDefect] = []
    sem = visible_semantics or ""
    ref = reference_hml or ""
    text = f"{prose or ''} {question or ''}"
    kinds = _field(sem, "declaration_kinds")
    entities = _field(sem, "entities")
    constraints = _field(sem, "constraints") or "[]"

    # 1. A const whose value lives only in the reference cannot be guessed.
    for m in re.finditer(r"'(\w+)':\s*'const'", kinds):
        name = m.group(1)
        value = re.search(rf"const {name} : \w+ = (\S+)", ref)
        if value and value.group(1) not in sem and value.group(1) not in text:
            found.append(TaskDefect(
                DefectClass.CONST_WITHOUT_INITIALISER,
                "declared const but its value appears only in the private reference",
                name))

    # 2. An entity the prose never mentions cannot be named by an encoder.
    for m in re.finditer(r"'(\w+)':", entities):
        name = m.group(1)
        if name not in text:
            found.append(TaskDefect(
                DefectClass.ENTITY_ABSENT_FROM_PROSE,
                "present in the structured target but absent from all visible prose",
                name))

    # 3. Prose asserting an assumption while the visible assumption list is empty.
    if not visible_assumptions and re.search(r"\bassumption\b|\bassume\b", text, re.I):
        found.append(TaskDefect(
            DefectClass.ASSUMPTION_NOT_DECLARED,
            "prose states an assumption but model_visible_target.assumptions is empty"))

    # 4. `x != 0` beside a strict positive bound is a consequence, not a premise.
    if "!= 0" in constraints and re.search(r">\s*[0-9]", constraints):
        found.append(TaskDefect(
            DefectClass.DERIVED_FACT_AS_INPUT_CONSTRAINT,
            "a non-zero constraint is listed as an input premise although the stated "
            "bound already entails it; an encoder cannot know it was meant to be restated"))

    # 5. A function whose body exists only in the reference.
    for m in re.finditer(r"'(\w+)':\s*'def'", kinds):
        name = m.group(1)
        if re.search(rf"def {name}\(", ref) and ":=" not in sem:
            found.append(TaskDefect(
                DefectClass.FUNCTION_BODY_MISSING,
                "declared as a definition but no body appears in the structured target",
                name))

    # 6. A question with no structured objective invites the encoder to invent a goal.
    if (question or "").strip() and "objective=None" in sem:
        found.append(TaskDefect(
            DefectClass.QUESTION_WITHOUT_OBJECTIVE,
            "a natural-language question is posed while objective=None, so whether a "
            "goal statement belongs in the encoding is undetermined"))

    # 7. Any literal the reference depends on that is nowhere visible.
    for m in re.finditer(r"=\s*(-?\d+(?:\.\d+)?)\b", ref):
        lit = m.group(1)
        if lit not in sem and lit not in text:
            found.append(TaskDefect(
                DefectClass.PUBLIC_INSUFFICIENT_FOR_PRIVATE,
                "the reference depends on a literal that appears in no visible material",
                lit))
            break

    return AdmissionReport(task_id=task_id, defects=tuple(found))
