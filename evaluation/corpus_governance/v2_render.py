"""Every artefact a model or evaluator sees, generated from one canonical object.

Nothing here is hand-authored. Prose, the model-visible target, each surface rendering and
the private evaluator target are all functions of `CanonicalAcq0TaskV2`. That is the whole
point: in v1 the prose and the reference encoding were written separately, drifted apart,
and a correct model answer was scored FAIL.

The prose is deliberately plain. It is not meant to read well; it is meant to be complete,
faithful and deterministic, with no entity the formal object lacks and no premise the
formal object does not state.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from .canonical_v2 import CanonicalAcq0TaskV2

__all__ = ["ExperimentView", "render_prose", "render_question", "acq0_view",
           "h2_view", "render_surface", "SUPPORTED_SURFACES", "ViewConfusion"]

SUPPORTED_SURFACES = (
    "A_v0_labelled_linear",
    "B_v1_labelled_linear_simplified",
    "C_prefix_sexpr",
    "D_constrained_json_graph",
)


class ViewConfusion(RuntimeError):
    """Raised when an ACQ0 artefact would leak into an H2 prompt, or the reverse."""


class ExperimentView(StrEnum):
    ACQ0_TRANSLATION = "ACQ0_TRANSLATION"
    H2_REASONING = "H2_REASONING"
    H3_REPAIR = "H3_REPAIR"


def _type_phrase(t: str | None) -> str:
    return t or "an unspecified type"


def render_prose(task: CanonicalAcq0TaskV2) -> str:
    """Plain, complete, deterministic description of exactly what the object states.

    Every declared entity appears. Every supplied assumption appears. A **derived** fact
    appears only when it declares `state_in_prose`, and is then labelled as following from
    its premises -- never presented as an independent restriction. v1 said "the assumption
    is the only restriction given" while listing a second constraint.
    """
    st = task.structured_target()
    lines: list[str] = []

    for d in st["declarations"]:
        kind = d["kind"]
        if kind == "const":
            lines.append(
                f"The constant {d['name']} has type {_type_phrase(d['type'])} "
                f"and the value {d.get('value', '<missing>')}.")
        elif kind == "obs":
            lines.append(
                f"The observed quantity {d['name']} has type {_type_phrase(d['type'])}"
                + (f" and the value {d['value']}." if d.get("value") else "."))
        else:
            lines.append(
                f"The quantity {d['name']} is declared as {kind} "
                f"with type {_type_phrase(d['type'])}.")

    for f in st["definitions"]:
        binders = ", ".join(f"{b['name']} of type {_type_phrase(b['type'])}"
                            for b in f["binders"])
        if binders:
            lines.append(
                f"The function {f['name']} takes {binders}, returns "
                f"{_type_phrase(f['codomain'])}, and is defined by {f['body']}.")
        else:
            lines.append(
                f"The value {f['name']} has type {_type_phrase(f['codomain'])} "
                f"and is defined by {f['body']}.")

    for law in st["probability_laws"]:
        given = f" given {', '.join(law['given'])}" if law["given"] else ""
        lines.append(
            f"The {law['role']} of {law['target']}{given} is {law['distribution']}.")

    for a in st["assumptions"]:
        lines.append(f"It is assumed that {a}.")
    for c in st["domain_constraints"]:
        lines.append(f"It is required that {c}.")

    for f in task.derived_facts:
        if f.state_in_prose:
            lines.append(
                f"It follows from {' and '.join(f.derived_from)} that {f.statement}; "
                f"this is a consequence, not a further restriction.")

    for p in task.prohibited_assumptions:
        lines.append(f"Do not assume {p}.")

    return "\n".join(lines)


def render_question(task: CanonicalAcq0TaskV2) -> str | None:
    """A question exists only when an objective does. `None` means no question at all."""
    if task.objective is None:
        return None
    verb = {"prove": "Prove", "solve": "Solve for", "infer": "Infer",
            "decide": "Decide whether"}[task.objective.kind]
    return f"{verb} {task.objective.statement}."


def render_surface(task: CanonicalAcq0TaskV2, surface: str) -> str:
    """Render the authoritative source into one candidate surface."""
    if surface not in SUPPORTED_SURFACES:
        raise ValueError(f"unsupported surface {surface!r}")
    from evaluation.syntax_gate.candidates import resolve_adapters
    adapter = resolve_adapters()[surface]
    if adapter is None:
        raise RuntimeError(f"{surface} has no adapter; NOT MEASURED, never assumed empty")
    return adapter.render(task.source)


def acq0_view(task: CanonicalAcq0TaskV2) -> dict[str, Any]:
    """Translation view. The complete target is supplied; nothing must be inferred.

    A problem-solving question is **not** included. ACQ0 measures encoding, not reasoning,
    and a question with no formal counterpart is what let a model invent a goal in v1. A
    formal objective that is itself part of the object to be translated is already present
    in `structured_target`, so it needs no separate prompt question.
    """
    return {
        "view": str(ExperimentView.ACQ0_TRANSLATION),
        "task_id": task.task_id,
        "instruction": ("Encode the supplied mathematical object faithfully in the "
                        "assigned surface syntax. Do not solve, add, remove or change "
                        "anything."),
        "prose": render_prose(task),
        "structured_target": task.structured_target(),
        "question": None,
    }


def h2_view(task: CanonicalAcq0TaskV2) -> dict[str, Any]:
    """Reasoning view. Problem and question only -- never the target or the encoding."""
    return {
        "view": str(ExperimentView.H2_REASONING),
        "task_id": task.task_id,
        "instruction": ("Solve the problem, constructing a Hamiltonian workspace as you "
                        "reason."),
        "prose": render_prose(task),
        "question": render_question(task),
        "structured_target": None,
        "reference_encoding": None,
    }


def assert_views_distinct(acq0: dict[str, Any], h2: dict[str, Any]) -> None:
    """The two views must not be confusable. Checked, not assumed."""
    if acq0.get("structured_target") is None:
        raise ViewConfusion("the ACQ0 view must supply the structured target")
    if h2.get("structured_target") is not None:
        raise ViewConfusion(
            "the H2 view carries a structured target; that is answer-key exposure")
    if h2.get("reference_encoding") is not None:
        raise ViewConfusion("the H2 view carries a reference encoding")
    if acq0.get("question") is not None:
        raise ViewConfusion(
            "the ACQ0 view carries a problem-solving question; ACQ0 measures encoding, "
            "and a question invites the model to invent a goal")
