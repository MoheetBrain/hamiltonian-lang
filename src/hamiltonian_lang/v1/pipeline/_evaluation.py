"""The one boundary between the shipped library and the ``evaluation/`` research tree.

Why this module exists, rather than six ``from evaluation... import`` lines
---------------------------------------------------------------------------
The pipeline genuinely depends on three things that live outside ``src/``: the candidate
registry and its front ends (``evaluation.syntax_gate.candidates``), the canonical
semantic object and its deterministic answer checker (``evaluation.corpus.cso``) and the
no-oracle guard (``evaluation.acq0.protocols.oracle``). Those are the right dependencies —
rebuilding any of them here would produce a second implementation that drifts from the
first, and the drift would be invisible.

But the dependency runs *outward*, and it has two consequences that are worth handling in
one place instead of six:

**Type checking.** ``[tool.mypy] files = ["src/hamiltonian_lang"]``. A direct import makes
mypy follow the edge and type-check the evaluation tree as part of the library, which it
is not: doing so surfaces eleven pre-existing errors in files this package does not own
and did not change. Resolving them here would mean editing another agent's files;
silencing them repo-wide would mean editing shared configuration to hide errors that are
real in their own tree. Importing through :func:`importlib.import_module` keeps the edge
out of mypy's graph, which is an accurate statement of the boundary: from the library's
side, the evaluation tree is untyped external code.

**Availability.** ``evaluation`` is a namespace package resolved from the working
directory, so it is importable when the process runs from the repository root and not
otherwise. Each accessor below therefore fails loudly and says what to do. In particular
:func:`oracle` guards a *safety* property: if it could not be imported, the pipeline must
refuse to build a prompt rather than build an unscanned one and record it as scanned.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = ["EvaluationTreeUnavailable", "candidates", "cso", "oracle"]


class EvaluationTreeUnavailable(RuntimeError):
    """A required module from the ``evaluation/`` tree could not be imported."""


def _load(name: str, what: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:  # pragma: no cover - environment defect
        raise EvaluationTreeUnavailable(
            f"{name} could not be imported, so {what}. `evaluation` is a namespace "
            "package resolved from the working directory; run from the repository root."
        ) from exc


def candidates() -> Any:
    """``evaluation.syntax_gate.candidates`` — the candidate registry and front ends."""
    return _load(
        "evaluation.syntax_gate.candidates",
        "the configured surface cannot be resolved",
    )


def cso() -> Any:
    """``evaluation.corpus.cso`` — the canonical object and the answer checker."""
    return _load(
        "evaluation.corpus.cso",
        "problem files cannot be read and answers cannot be graded",
    )


def oracle() -> Any:
    """``evaluation.acq0.protocols.oracle`` — the no-oracle guard. Never optional."""
    return _load(
        "evaluation.acq0.protocols.oracle",
        "the no-oracle guard cannot run and no prompt may be built",
    )
