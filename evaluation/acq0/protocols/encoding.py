"""ACQ0 encoding prompts: the target is given, and only the encoding is asked for.

Why this module exists at all, and why it is *here*
---------------------------------------------------
``evaluation/acq0/prompts/stages.py`` builds the prompts every hypothesis shares, and it
calls :func:`~.oracle.assert_no_oracle` with no exemption argument. That file is left
untouched on purpose. The ACQ0 disclosure is applied **here**, by wrapping the prompt that
module produced, so the exemption has exactly one call site and an H1/H2/H3 prompt cannot
acquire one without an edit that shows up in review as a new import.

What is disclosed, and what the disclosure costs
------------------------------------------------
Per the user's ACQ0 addendum §1 an ACQ0 prompt carries the original problem statement, the
known answer / target proposition, the assumptions, the declared entities, the
mathematical roles, and the domains and dimensions where relevant. It does **not** carry
the reference HML encoding: see :data:`~.oracle.NEVER_DISCLOSED`. Producing the encoding
is the task; being told the mathematics is the removal of a confound.

The cost is stated in :data:`~.oracle.ACQ0_ANSWER_FACET_VOID` and carried into every
record this module produces: with the target supplied, ``answer_correct`` is uninformative
by construction and may never later be cited as evidence about the representation.

Quarantine
----------
:func:`assert_mathematics_fixed_independently` refuses a task whose expected mathematics is
not already pinned in the corpus before execution. A task whose ground truth could be
written after seeing a model's output would make exact semantic preservation a measurement
of the scorer's willingness to agree with the model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from evaluation.corpus.cso import CanonicalSemanticObject

from .core import GenerationProtocol, StageKind
from .oracle import (
    ACQ0_ANSWER_FACET_VOID,
    ACQ0_ENCODING_EXEMPTION,
    Hypothesis,
    LeakFinding,
    assert_no_oracle,
)

__all__ = [
    "ACQ0_TARGET_HEADER",
    "ACQ0_ENCODING_INSTRUCTION",
    "TaskQuarantined",
    "QuarantineFinding",
    "render_disclosure",
    "assert_mathematics_fixed_independently",
    "quarantine_report",
    "acq0_encoding_prompt",
]

ACQ0_TARGET_HEADER = "GIVEN MATHEMATICS (this is the answer; do not re-derive it)"

#: Said in the prompt, not only in the docstring. A model that re-derives and disagrees
#: with the given target would be scored on an object nobody asked it to produce.
ACQ0_ENCODING_INSTRUCTION = (
    "The mathematics above is given and is correct. Your task is to ENCODE it, not to "
    "solve it, check it, or improve it. Reproduce exactly the entities, roles, "
    "quantifier order, dimensions and target stated above -- no more and no fewer. Do "
    "not add facts that are not stated. Do not omit facts that are stated."
)


class TaskQuarantined(AssertionError):
    """A task's expected mathematics is not fixed independently of execution."""


@dataclass(frozen=True)
class QuarantineFinding:
    task_id: str
    reason: str

    def __str__(self) -> str:  # pragma: no cover - message formatting
        return f"{self.task_id}: {self.reason}"


def _lines(cso: CanonicalSemanticObject) -> list[str]:
    """The disclosure body, field by field, in the addendum's order."""
    f = cso.semantics
    out: list[str] = []

    if cso.assumptions:
        out.append("Assumptions:")
        out += [f"  - {a}" for a in cso.assumptions]

    if f.entities:
        out.append("Declared entities (name : declared type):")
        out += [f"  - {k} : {v}" for k, v in sorted(f.entities.items())]

    if f.declaration_kinds:
        out.append("Declaration kinds:")
        out += [f"  - {k} is declared as {v}" for k, v in sorted(f.declaration_kinds.items())]

    if f.laws:
        out.append("Mathematical roles (target <- role := symbol):")
        for target, roles in sorted(f.laws.items()):
            body = ", ".join(f"{role} := {sym}" for role, sym in sorted(roles.items()))
            out.append(f"  - {target}({body})")

    if f.law_families:
        out.append("Law families:")
        out += [f"  - {k} ~ {v}" for k, v in sorted(f.law_families.items())]

    if f.conditioning:
        out.append(f"Conditioning: {f.conditioning}")
    if f.constraints:
        out.append("Constraints:")
        out += [f"  - {c}" for c in f.constraints]
    if f.quantifier_order:
        out.append("Quantifier order (outermost first): " + " . ".join(f.quantifier_order))
    if f.dependencies:
        out.append("Dependency structure (defined symbol <- what it depends on):")
        out += [f"  - {k} depends on {', '.join(v)}" for k, v in sorted(f.dependencies.items())]
    if f.dimensions:
        out.append("Domains and dimensions:")
        out += [f"  - {k} has dimension {v}" for k, v in sorted(f.dimensions.items())]
    if f.objective:
        out.append(f"Objective: {f.objective}")

    if cso.answer.value is not None:
        out.append(f"Target proposition / known answer: {cso.answer.value}")

    return out


def render_disclosure(cso: CanonicalSemanticObject) -> str:
    """The block appended to an ACQ0 prompt. Empty body raises rather than degrading.

    An empty disclosure would silently turn an ACQ0 encoding prompt back into a solving
    prompt while still carrying the label, and the whole arm would be mislabelled.
    """
    body = _lines(cso)
    if not body:
        raise TaskQuarantined(
            f"task {cso.id!r} has no structured mathematics to disclose, so an ACQ0 "
            "encoding prompt built from it would ask the model to solve the problem "
            "while being recorded as an encoding trial"
        )
    return "\n".join([ACQ0_TARGET_HEADER, *body, "", ACQ0_ENCODING_INSTRUCTION])


def quarantine_report(task: Any) -> tuple[QuarantineFinding, ...]:
    """Every reason this task's expected mathematics is not independently fixed.

    Returns findings rather than raising, so the whole calibration set can be screened in
    one pass and the record shows which tasks were considered, not only which survived.
    """
    cso = task.cso
    f = cso.semantics
    out: list[QuarantineFinding] = []
    if not (cso.reference_hml or "").strip():
        out.append(
            QuarantineFinding(
                cso.id,
                "no reference_hml in the corpus: there is no expected canonical object "
                "fixed before execution, so exact semantic preservation would have "
                "nothing to compare against",
            )
        )
    if not f.entities:
        out.append(
            QuarantineFinding(
                cso.id, "SemanticFacts declares no entities; the ground truth is not pinned"
            )
        )
    # Which structure fixes the mathematics is domain-dependent and the predicate must
    # say so: a binding-chain task's ground truth is its dependency graph and its
    # declaration kinds, and it has no laws or quantifiers at all. Requiring laws here
    # would quarantine a task whose mathematics is perfectly well fixed, which would make
    # the quarantine an obstacle rather than a control.
    if not (
        f.laws
        or f.law_families
        or f.quantifier_order
        or f.constraints
        or f.dimensions
        or f.dependencies
        or f.conditioning
        or f.objective
        or f.declaration_kinds
    ):
        out.append(
            QuarantineFinding(
                cso.id,
                "SemanticFacts states no laws, families, quantifier order, constraints, "
                "dimensions, dependencies, conditioning, objective or declaration kinds: "
                "entity names alone do not fix the mathematics",
            )
        )
    if not getattr(task, "content_hash", ""):
        out.append(QuarantineFinding(cso.id, "no content_hash, so the task text is not pinned"))
    return tuple(out)


def assert_mathematics_fixed_independently(tasks: Sequence[Any]) -> None:
    """Refuse to execute against any task whose mathematics is not pre-fixed."""
    findings: list[QuarantineFinding] = []
    for t in tasks:
        findings.extend(quarantine_report(t))
    if findings:
        raise TaskQuarantined(
            f"{len(findings)} quarantine finding(s); these tasks may not be executed:\n  "
            + "\n  ".join(str(f) for f in findings)
        )


@dataclass(frozen=True)
class Acq0Prompt:
    """A stage prompt plus the record of what the exemption disclosed."""

    stage: StageKind
    protocol: GenerationProtocol
    condition: str
    task_id: str
    system: str
    user: str
    disclosed: tuple[LeakFinding, ...]
    format_restricted: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": str(self.stage),
            "protocol": str(self.protocol),
            "condition": self.condition,
            "task_id": self.task_id,
            "format_restricted": self.format_restricted,
            "system_characters": len(self.system),
            "user_characters": len(self.user),
            "exemption": ACQ0_ENCODING_EXEMPTION.to_dict(),
            "disclosed_fields": sorted({str(f.field) for f in self.disclosed}),
            "consequence": ACQ0_ANSWER_FACET_VOID,
        }


def acq0_encoding_prompt(base: Any, task: Any) -> Acq0Prompt:
    """Wrap a :class:`~..prompts.stages.StagePrompt` as an ACQ0 encoding prompt.

    The disclosure is appended to the **end** of the user message so the last thing the
    model reads before answering is the target it must encode, and so the upstream draft
    block (which stage two of ``DRAFT_THEN_FORMAL`` inserts mid-prompt) is not displaced.

    The same disclosure is applied to the draft stage as to the formalisation stage. That
    is required for information parity: an arm whose first stage lacked the target would
    differ from ``DIRECT_FORMAL`` in the task information it received, and the protocol
    difference would then be confounded with a disclosure difference this study
    introduced itself.

    **The exempted scan covers the appended block only**, and that is deliberate. ``base``
    has already been validated by ``formalise_prompt`` with the right instrument: a
    substring scan over the task-composed portion, plus a content-hash disjointness check
    on the demonstrations. Re-scanning the whole assembled prompt here would re-introduce
    the false alarm that instrument exists to avoid -- measured at ``21687cf``, scanning
    the assembled ``A_v0_labelled_linear`` / ``binding_chain_001`` prompt reports
    ``reference_encoding leaked via 'module BindingChain'``, which is a *demonstration's*
    module name and not this task's answer. Scanning only what this function adds also
    means the exemption is scoped to exactly the text the exemption exists for.
    """
    disclosure = render_disclosure(task.cso)
    user = f"{base.user}\n\n{disclosure}"
    disclosed = assert_no_oracle(
        disclosure,
        task.cso,
        where=f"acq0_encoding[{base.condition}/{base.task_id}/{base.stage}]",
        hypothesis=Hypothesis.ACQ0,
        exemption=ACQ0_ENCODING_EXEMPTION,
    )
    return Acq0Prompt(
        stage=base.stage,
        protocol=base.protocol,
        condition=base.condition,
        task_id=base.task_id,
        system=base.system,
        user=user,
        disclosed=tuple(disclosed),
        format_restricted=base.format_restricted,
    )
