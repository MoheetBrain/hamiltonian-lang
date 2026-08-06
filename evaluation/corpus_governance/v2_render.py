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
           "render_surface_source",
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
    from .v2_facts import prose_clauses

    # ONE generator. `prose_clauses` walks the ordered view and tags each sentence with the
    # facts it carries; this joins them. A second, independent renderer is how the
    # kind-bucket clause generator came to omit a `check` statement this one emitted --
    # two prose paths that agreed by luck until they did not.
    # EVERY clause, unconditionally. Filtering the objective clause when `objective is
    # None` made `check_prose_coverage` certify an `objective` fact the prose never
    # stated -- the coverage gate walked `prose_clauses` while the model read this.
    return "\n".join(clause.text for clause in prose_clauses(task))


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
    # "Decide whether" + a statement that already begins "whether"/"that" produced
    # "Decide whether whether ...". The verb carries no conjunction; the statement does.
    verb = {"prove": "Prove", "solve": "Solve for", "infer": "Infer",
            "decide": "Establish"}[task.objective.kind]
    return f"{verb} {task.objective.statement}."


def render_surface_source(source: str, surface: str) -> str:
    """Render arbitrary HML-L1 into one candidate surface.

    Separate from :func:`render_surface` because demonstrations are authored modules, not
    canonical tasks -- drawing them from the scored corpus would show a model the answer to
    one task while it encodes another.
    """
    if surface not in SUPPORTED_SURFACES:
        raise ValueError(f"unsupported surface {surface!r}")
    from evaluation.syntax_gate.candidates import resolve_adapters
    adapter = resolve_adapters()[surface]
    if adapter is None:
        raise RuntimeError(f"{surface} has no adapter; NOT MEASURED, never assumed empty")
    return adapter.render(source)


def render_surface(task: CanonicalAcq0TaskV2, surface: str) -> str:
    """Render the authoritative source into one candidate surface."""
    return render_surface_source(task.source, surface)


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
