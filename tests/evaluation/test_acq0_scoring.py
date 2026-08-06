"""The Tranche A scorer: it must be exactly as strict as the reference, and no stricter.

The fence test is the reason this file exists. On the first Tranche A attempt the model
answered candidate C inside a ```lisp fence — a tag that candidate's own specification
advertises — and the encoding inside it was **hash-identical to the reference**. The raw
text went to the importer fence and all, the import failed, and surface C would have been
eliminated on a harness defect reported as a property of the notation.
"""

from __future__ import annotations

import pytest
from evaluation.acq0.v2.run import _evaluate, strip_fence
from evaluation.corpus_governance.v2_corpus import PROOF_CORPUS
from evaluation.corpus_governance.v2_render import SUPPORTED_SURFACES, render_surface


@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
@pytest.mark.parametrize("surface", SUPPORTED_SURFACES)
def test_the_reference_self_scores_exact(task, surface):
    """A scorer that cannot score the reference cannot score anything."""
    assert _evaluate(render_surface(task, surface), surface, task)["exact"]


@pytest.mark.parametrize("surface", SUPPORTED_SURFACES)
@pytest.mark.parametrize("tag", ["", "lisp", "sexpr", "scheme", "hml", "json", "text"])
def test_a_fenced_answer_scores_the_same_as_an_unfenced_one(surface: str, tag: str):
    task = PROOF_CORPUS[0]
    body = render_surface(task, surface)
    assert _evaluate(f"```{tag}\n{body}\n```", surface, task)["exact"], (
        f"a ```{tag} fence changed the verdict for {surface}")


def test_stripping_leaves_unfenced_text_untouched():
    assert strip_fence("(module M)", "C_prefix_sexpr") == "(module M)"


def test_a_lone_backtick_line_is_not_treated_as_a_fence():
    assert strip_fence("```", "C_prefix_sexpr") == "```"


@pytest.mark.parametrize("task", PROOF_CORPUS[:4], ids=lambda t: t.task_id)
def test_a_dropped_statement_does_not_score_exact(task):
    """The scorer must still fail on a real defect — stripping must not loosen it."""
    surface = "B_v1_labelled_linear_simplified"
    truncated = "\n".join(render_surface(task, surface).rstrip().splitlines()[:-1])
    assert not _evaluate(truncated, surface, task)["exact"]


def test_a_reordered_answer_does_not_score_exact():
    """Order is content, and the scorer is the thing that has to know it."""
    task = next(t for t in PROOF_CORPUS if t.task_id == "v2_assumption_boundary_002")
    surface = "B_v1_labelled_linear_simplified"
    lines = render_surface(task, surface).rstrip().splitlines()
    swapped = "\n".join([lines[0], *lines[1:][::-1]])
    assert not _evaluate(swapped, surface, task)["exact"]


def test_prose_returned_instead_of_an_encoding_scores_not_exact():
    task = PROOF_CORPUS[0]
    result = _evaluate("Here is the encoding you asked for.", "A_v0_labelled_linear", task)
    assert not result["exact"]
    assert not result["parse_ok"] or not result["type_ok"]
