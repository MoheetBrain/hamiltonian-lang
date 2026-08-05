"""What a prompt may carry, and the mechanical check that it carries nothing more.

The failure this prevents
-------------------------
``DRAFT_THEN_FORMAL`` runs an extra call. If that call's prompt carried any of the answer
key — the reference encoding, the gold answer, or the structured ``SemanticFacts`` — the
two-stage arm would win, and it would win **for the wrong reason**: not because splitting
the reasoning from the formatting helps, but because the draft stage was told what the
answer was. The protocol comparison would then be measuring an information asymmetry that
this study itself introduced, and every conclusion drawn from it about format restriction
would be false.

The guard has two halves, and both are needed:

:func:`assert_no_oracle`
    Scans a rendered prompt for the task's oracle content. Catches a leak introduced by
    an edit to a prompt template.

:func:`assert_information_parity`
    Asserts the **union** of what a protocol's stages are permitted to see equals what
    the one-stage protocol sees. Catches a leak introduced by adding a field to one arm's
    prompt builder, which the per-prompt scan alone would pass as long as the added field
    was not itself an oracle field.

Why a bare substring scan is not enough
---------------------------------------
The gold answer for a numeric task can be a short string like ``40.0`` that legitimately
occurs in the problem prose. Flagging that would make the guard fire on correct prompts,
and a guard that fires on correct prompts gets switched off. So the rule implemented here
is: an oracle field leaks when its rendering appears in the prompt **and does not already
appear in the permitted content**. The permitted content is the prose, the question and
the answer-format instruction — the three things every arm receives by construction in
``evaluation/syntax_gate/prompts.py``.

Why demonstrations are checked by content hash and not by substring
--------------------------------------------------------------------
**Measured on this corpus**, a substring scan over a prompt carrying the 50-demonstration
curriculum flags 281 of 320 confirmatory-gate prompts. Every one of those is a false
alarm. The corpus reuses a module name per domain (``module ApproximationStatus`` appears
in 6 demonstration tasks) and draws symbols from a shared pool (``varrho : Real`` appears
in 7, across 3 different domains), so a demonstration of a *different* task legitimately
contains strings that also occur in the task-under-test's answer key.

A guard with an 88% false-alarm rate would be turned off within a week, and the real leak
it exists to catch would go with it. So the two questions are asked with the two
instruments that can actually answer them:

* *did this harness compose any of the answer key into the prompt?* — substring scan over
  the **task-composed** portion, built with zero demonstrations;
* *is any demonstration actually this task?* — :func:`assert_demonstrations_disjoint`,
  on the **content hash**, which is the same instrument
  ``evaluation/syntax_gate/partition.py`` uses and which catches a task duplicated under a
  different id.

Substring identity was never the right instrument for the second question, and the
measurement above is what makes that concrete rather than arguable.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from evaluation.corpus.cso import CanonicalSemanticObject

from .core import PROTOCOL_STAGES, GenerationProtocol, StageKind

__all__ = [
    "TaskInformation",
    "PERMITTED_TASK_INFORMATION",
    "ORACLE_FIELDS",
    "OracleLeak",
    "InformationAsymmetry",
    "permitted_text",
    "oracle_renderings",
    "scan_for_oracle",
    "assert_no_oracle",
    "assert_demonstrations_disjoint",
    "stage_information",
    "protocol_information",
    "assert_information_parity",
    "parity_report",
    "LeakFinding",
]


class TaskInformation(StrEnum):
    """Every distinguishable thing a prompt could carry about one task."""

    #: The mathematical content in neutral prose. Every arm gets this verbatim.
    PROSE = "prose"
    #: The question asked. Every arm gets this verbatim.
    QUESTION = "question"
    #: How to shape the final answer (``AnswerSpec.render_instruction``). Format, not
    #: content: it names the *kind* of answer, never the answer.
    ANSWER_INSTRUCTION = "answer_instruction"
    #: The candidate surface's grammar reference. Present only in a restricted stage —
    #: its absence is what makes the draft/plan stage unrestricted.
    SYNTAX_SPECIFICATION = "syntax_specification"
    #: Worked examples in the candidate surface. Same restriction as the specification.
    DEMONSTRATIONS = "demonstrations"
    #: The model's own prior output, carried between stages. Model-generated, never
    #: key-generated, which is precisely why it is not an oracle field.
    UPSTREAM_MODEL_OUTPUT = "upstream_model_output"

    # -- oracle fields: never permitted in any stage of any protocol ----------
    #: The reference HML-L1 encoding. The thing ACQ0 asks the model to produce.
    REFERENCE_ENCODING = "reference_encoding"
    #: The verified answer value.
    GOLD_ANSWER = "gold_answer"
    #: The structured ground truth (``SemanticFacts``) preservation is scored against.
    SEMANTIC_FACTS = "semantic_facts"
    #: What a careless reader concludes. Naming them would teach the failure modes.
    DISTRACTORS = "distractors"


#: What any stage of any protocol may carry about the task itself. Note what is absent:
#: every field that the scorer reads as ground truth.
PERMITTED_TASK_INFORMATION: frozenset[TaskInformation] = frozenset(
    {
        TaskInformation.PROSE,
        TaskInformation.QUESTION,
        TaskInformation.ANSWER_INSTRUCTION,
    }
)

#: Never permitted, in any stage, in any arm, at any curriculum size.
ORACLE_FIELDS: frozenset[TaskInformation] = frozenset(
    {
        TaskInformation.REFERENCE_ENCODING,
        TaskInformation.GOLD_ANSWER,
        TaskInformation.SEMANTIC_FACTS,
        TaskInformation.DISTRACTORS,
    }
)


class OracleLeak(AssertionError):
    """A prompt carried part of the answer key."""


class InformationAsymmetry(AssertionError):
    """Two protocol arms are not matched in the information they receive."""


def permitted_text(cso: CanonicalSemanticObject) -> str:
    """Everything every arm receives by construction, concatenated.

    The denominator of the leak test: content already here cannot leak, because the
    one-stage protocol carries it too.
    """
    return "\n".join([cso.prose, cso.question, cso.answer.render_instruction()])


def _facts_renderings(cso: CanonicalSemanticObject) -> list[str]:
    """Distinctive strings that only the structured ground truth would produce.

    Individual symbol names are *not* used: they occur in the prose legitimately. What is
    used is the **pairing** — ``name`` with its declared HML type, a law target with its
    family, a quantifier chain — because a pairing is the ground truth's contribution and
    cannot arrive from the prose by accident.
    """
    f = cso.semantics
    out: list[str] = []
    out += [f"{k} : {v}" for k, v in f.entities.items()]
    out += [f"{k} is a {v}" for k, v in f.entities.items()]
    out += [f"{k} ~ {v}" for k, v in f.law_families.items()]
    for target, roles in f.laws.items():
        out += [f"{target}({role} := {sym}" for role, sym in roles.items()]
    if f.quantifier_order:
        out.append(" . ".join(f.quantifier_order))
    out += [f"{k} has dimension {v}" for k, v in f.dimensions.items()]
    return [s for s in out if len(s.strip()) >= 6]


def oracle_renderings(cso: CanonicalSemanticObject) -> Mapping[TaskInformation, list[str]]:
    """Concrete strings whose presence in a prompt would constitute a leak.

    The reference encoding contributes its **statement lines** rather than the whole
    blob: a leak that pasted half the reference would evade a whole-text comparison.
    Lines shorter than six characters are dropped — ``solve x`` fragments are not
    distinctive enough to accuse a prompt on.
    """
    ref_lines = [
        line.strip()
        for line in (cso.reference_hml or "").splitlines()
        if len(line.strip()) >= 6 and not line.strip().startswith("#")
    ]
    gold = "" if cso.answer.value is None else str(cso.answer.value)
    return {
        TaskInformation.REFERENCE_ENCODING: ref_lines,
        TaskInformation.GOLD_ANSWER: [gold] if len(gold.strip()) >= 2 else [],
        TaskInformation.SEMANTIC_FACTS: _facts_renderings(cso),
        TaskInformation.DISTRACTORS: [
            d.strip() for d in cso.distractors if len(d.strip()) >= 8
        ],
    }


def _normalise(text: str) -> str:
    """Collapse whitespace so a leak cannot hide behind reformatting."""
    return re.sub(r"\s+", " ", text or "").strip()


@dataclass(frozen=True)
class LeakFinding:
    field: TaskInformation
    fragment: str
    where: str

    def __str__(self) -> str:  # pragma: no cover - message formatting
        return f"{self.where}: {self.field} leaked via {self.fragment!r}"


def scan_for_oracle(
    prompt_text: str, cso: CanonicalSemanticObject, *, where: str = "<prompt>"
) -> tuple[LeakFinding, ...]:
    """Every oracle fragment present in ``prompt_text`` and absent from permitted content.

    Returns findings rather than raising, so a caller can report all of them at once. The
    assertion wrapper is :func:`assert_no_oracle`.
    """
    haystack = _normalise(prompt_text)
    allowed = _normalise(permitted_text(cso))
    findings: list[LeakFinding] = []
    for field, fragments in oracle_renderings(cso).items():
        for fragment in fragments:
            needle = _normalise(fragment)
            if not needle:
                continue
            if needle in allowed:
                # Already in content every arm receives; its presence is not a leak.
                continue
            if needle in haystack:
                findings.append(LeakFinding(field, fragment, where))
    return tuple(findings)


def assert_no_oracle(
    prompt_text: str, cso: CanonicalSemanticObject, *, where: str = "<prompt>"
) -> None:
    """Raise :class:`OracleLeak` if the prompt carries any of the answer key."""
    findings = scan_for_oracle(prompt_text, cso, where=where)
    if findings:
        raise OracleLeak(
            f"{len(findings)} oracle fragment(s) reached {where}. A stage that is told "
            "the answer makes its protocol win for the wrong reason:\n  "
            + "\n  ".join(str(f) for f in findings)
        )


def assert_demonstrations_disjoint(task: Any, demonstrations: Sequence[Any]) -> None:
    """No demonstration may be the task under test.

    Checked on ``content_hash`` as well as on ``id``. Asserting on ids alone would pass
    for the same task duplicated under a different name, which is precisely the leak
    worth catching: a prompt that shows the model the answer encoding for the very task
    it is being asked to encode measures nothing at all.

    The id check is kept alongside it because an id collision is the likelier mistake and
    its error message is the more useful one.
    """
    if not demonstrations:
        return
    task_id = getattr(task, "id", None)
    same_id = [d for d in demonstrations if getattr(d, "id", None) == task_id]
    if same_id:
        raise OracleLeak(
            f"task {task_id!r} appears in its own demonstration curriculum. Its "
            "reference encoding would be pasted into the prompt as a worked example, so "
            "the trial would measure copying rather than encoding."
        )
    task_hash = getattr(task, "content_hash", None)
    if task_hash is None:
        return
    same_content = [
        getattr(d, "id", "?")
        for d in demonstrations
        if getattr(d, "content_hash", None) == task_hash
    ]
    if same_content:
        raise OracleLeak(
            f"demonstration(s) {same_content} have the same content hash as task "
            f"{task_id!r}. Different ids, identical content: the model would be shown "
            "the answer to the task it is being asked to solve."
        )


def stage_information(
    stage: StageKind, *, curriculum_size: int = 0, has_upstream: bool = False
) -> frozenset[TaskInformation]:
    """What one stage's prompt is permitted to contain.

    The unrestricted stages are defined by **subtraction**: they receive the task, and
    they do not receive the grammar or the worked examples. That absence is the
    manipulation the paper's two-stage arm depends on; a draft prompt that named the
    target syntax would be a restricted prompt wearing an unrestricted label.
    """
    base = set(PERMITTED_TASK_INFORMATION)
    if stage is StageKind.FORMALISE:
        base.add(TaskInformation.SYNTAX_SPECIFICATION)
        if curriculum_size > 0:
            base.add(TaskInformation.DEMONSTRATIONS)
        if has_upstream:
            base.add(TaskInformation.UPSTREAM_MODEL_OUTPUT)
    return frozenset(base)


def protocol_information(
    protocol: GenerationProtocol, *, curriculum_size: int = 0
) -> frozenset[TaskInformation]:
    """The union over a protocol's stages of what each may contain."""
    stages = PROTOCOL_STAGES[protocol]
    has_upstream = len(stages) > 1
    out: set[TaskInformation] = set()
    for stage in stages:
        out |= stage_information(
            stage,
            curriculum_size=curriculum_size,
            has_upstream=has_upstream and stage is StageKind.FORMALISE,
        )
    return frozenset(out)


def assert_information_parity(
    protocols: Iterable[GenerationProtocol], *, curriculum_size: int = 0
) -> None:
    """Every arm must see the same **task** information.

    ``UPSTREAM_MODEL_OUTPUT`` is excluded from the comparison, and that exclusion is the
    whole subtlety. It is the only difference the two-stage arms are allowed to have, and
    it is admissible because it is the model's own text produced under a prompt this
    module has already asserted carries no oracle content. Every other difference is an
    information asymmetry and is refused.
    """
    seen: dict[GenerationProtocol, frozenset[TaskInformation]] = {}
    for p in protocols:
        info = protocol_information(p, curriculum_size=curriculum_size)
        seen[p] = frozenset(info - {TaskInformation.UPSTREAM_MODEL_OUTPUT})
    distinct = set(seen.values())
    if len(distinct) > 1:
        detail = "; ".join(
            f"{p}: {sorted(str(i) for i in v)}" for p, v in sorted(seen.items())
        )
        raise InformationAsymmetry(
            "protocol arms do not carry matched task information, so a difference "
            f"between them would not be attributable to the protocol. {detail}"
        )
    leaked = distinct.pop() & ORACLE_FIELDS if distinct else frozenset()
    if leaked:
        raise OracleLeak(
            f"a protocol declares it may carry oracle fields {sorted(str(i) for i in leaked)}"
        )


def parity_report(
    protocols: Sequence[GenerationProtocol], *, curriculum_size: int = 0
) -> dict[str, Any]:
    """The parity table, for the audit record rather than for a test."""
    return {
        "curriculum_size": curriculum_size,
        "permitted_task_information": sorted(str(i) for i in PERMITTED_TASK_INFORMATION),
        "oracle_fields_never_permitted": sorted(str(i) for i in ORACLE_FIELDS),
        "per_protocol": {
            str(p): sorted(
                str(i) for i in protocol_information(p, curriculum_size=curriculum_size)
            )
            for p in protocols
        },
        "only_permitted_difference": str(TaskInformation.UPSTREAM_MODEL_OUTPUT),
        "why": (
            "upstream output is the model's own text, produced under a prompt asserted "
            "to carry no oracle content; every other difference would be an asymmetry "
            "this study introduced itself"
        ),
    }
