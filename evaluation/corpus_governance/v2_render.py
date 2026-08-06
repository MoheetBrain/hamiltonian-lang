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
    """Prose in ENCODING ORDER, one clause per emitted statement.

    The previous version walked kind-buckets, so prose order and source order diverged
    whenever a module interleaved kinds -- three of eight tasks. Since `content_hash` is
    order-sensitive, that made them unencodable. Prose now follows
    `encoding_view()["encoding_statements"]` by position, so the reader sees the order the
    answer requires.
    """
    from .v2_view import encoding_view

    view = encoding_view(task)
    lines: list[str] = []
    for r in sorted(view["encoding_statements"], key=lambda x: x["position"]):
        kind = r["kind"]
        if kind == "const":
            lines.append(f"The constant {r['name']} has type {r['type']} and the value "
                         f"{r.get('value')}.")
        elif kind == "obs":
            lines.append(f"The observed quantity {r['name']} has type {r['type']} and the "
                         f"value {r.get('value')}.")
        elif kind in {"var", "param", "index", "rv"}:
            lines.append(f"The quantity {r['name']} is declared as {kind} with type "
                         f"{r['type']}.")
        elif kind == "def":
            binders = ", ".join(f"{b['name']} of type {b['type']}" for b in r["binders"])
            lines.append(
                f"The function {r['name']} takes {binders}, returns {r['codomain']}, and "
                f"is defined by {r['body']}." if binders else
                f"The value {r['name']} has type {r['codomain']} and is defined by "
                f"{r['body']}.")
        elif kind == "assume":
            lines.append(f"It is assumed that {r['expression']}.")
        elif kind == "require":
            lines.append(f"It is required that {r['expression']}.")
        elif kind == "prove":
            lines.append(f"The goal is to prove that {r['expression']}.")
        elif kind in {"prior", "likelihood", "law", "posterior"}:
            given = f" given {', '.join(r['given'])}" if r.get("given") else ""
            lines.append(f"The {kind} of {r['target']}{given} is {r['distribution']}.")
        elif kind.startswith("check_"):
            lines.append(f"It is checked that the {kind[len('check_'):]} of "
                         f"{r['subject']} is {r['expression']}.")
        else:
            raise ValueError(f"no prose form for statement kind {kind!r}")

    for fact in task.derived_facts:
        if fact.state_in_prose:
            lines.append(
                f"It follows from {' and '.join(fact.derived_from)} that {fact.statement}; "
                f"this is a consequence, not a further restriction, and must not be "
                f"encoded.")
    for p_ in task.prohibited_assumptions:
        lines.append(f"Do not assume {p_}. This is guidance and must not be encoded.")
    return "\n".join(lines)


def _ordered_view(task: CanonicalAcq0TaskV2) -> dict[str, Any]:
    """What the model actually receives: the ordered encoding view.

    Kind-buckets are not handed to a model. `content_hash` is order-sensitive, so a bucketed
    view is not sufficient to reconstruct the answer -- three of eight tasks were
    unencodable under it.
    """
    from .v2_view import encoding_view

    return encoding_view(task)


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
        "structured_target": _ordered_view(task),
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
