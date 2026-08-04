"""Corpus self-consistency for HML-EVAL-001.

The reference encoding of a problem is, by definition, a correct encoding of it. If the
ground-truth facts and the reference encoding disagree, one of them is wrong and every
number computed from them is suspect.

This caught a real drift: 60 of 120 reference encodings scored below 1.0 because the
facts said `param` where the encoding said `const`, because quantifier binders were
listed as module declarations, and because the dimensional references were generic
boilerplate that never carried the case's own dimension.
"""

from __future__ import annotations

import pytest
from evaluation.corpus.cso import check_answer, parse_dimension
from evaluation.corpus.generators import CATEGORY_TARGETS, build_all, build_demos
from evaluation.corpus.renderers import ARMS, render_arm, verify_shared_content_identical
from evaluation.semantic_equiv import compare_semantics

from hamiltonian_lang import compile_source

CORPUS = build_all()
DEMOS = build_demos()


def test_corpus_size_and_category_balance():
    assert len(CORPUS) == sum(CATEGORY_TARGETS.values()) == 120
    counts: dict[str, int] = {}
    for c in CORPUS:
        counts[c.domain] = counts.get(c.domain, 0) + 1
    assert counts == CATEGORY_TARGETS


def test_problem_ids_are_unique():
    ids = [c.id for c in CORPUS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("cso", CORPUS, ids=[c.id for c in CORPUS])
def test_reference_encoding_compiles(cso):
    r = compile_source(cso.reference_hml, cso.id)
    assert r.ok(), "\n" + r.diagnostics.render()


@pytest.mark.parametrize("cso", CORPUS, ids=[c.id for c in CORPUS])
def test_reference_encoding_scores_perfectly_against_its_own_ground_truth(cso):
    """If the reference does not score 1.0, the facts and the encoding disagree."""
    cmp = compare_semantics(cso, cso.reference_hml)
    score = cmp.score()
    assert score is not None, f"{cso.id}: nothing checkable — the facts assert nothing"
    assert score == 1.0, f"{cso.id}: {cmp.to_dict()}"


@pytest.mark.parametrize("cso", CORPUS, ids=[c.id for c in CORPUS])
def test_every_arm_carries_the_problem_and_question_verbatim(cso):
    verify_shared_content_identical(cso)


def test_demonstrations_are_disjoint_from_the_benchmark():
    demo_ids = {d.id for d in DEMOS}
    demo_prose = {d.prose for d in DEMOS}
    assert not ({c.id for c in CORPUS} & demo_ids)
    assert not [c.id for c in CORPUS if c.prose in demo_prose]


def test_answer_checker_accepts_the_ground_truth_answer():
    """A ground truth its own checker rejects would silently zero an entire family."""
    for c in CORPUS:
        v = c.answer.value
        if c.answer.kind == "boolean":
            raw = "TRUE" if v else "FALSE"
        elif c.answer.kind == "role_map":
            import json

            raw = json.dumps(v)
        else:
            raw = str(v)
        ok, _ = check_answer(c.answer, f"<ANSWER>{raw}</ANSWER>")
        assert ok, f"{c.id}: checker rejected its own answer {raw!r}"


def test_answer_checker_rejects_a_wrong_answer():
    for c in CORPUS:
        if c.answer.kind == "boolean":
            wrong = "FALSE" if c.answer.value else "TRUE"
        elif c.answer.kind == "numeric":
            wrong = str(float(c.answer.value) + 17.5)
        elif c.answer.kind == "dimension":
            wrong = "Amount^7"
        elif c.answer.kind == "choice":
            others = [o for o in c.answer.options if o != c.answer.value]
            wrong = others[0]
        else:
            continue
        ok, _ = check_answer(c.answer, f"<ANSWER>{wrong}</ANSWER>")
        assert not ok, f"{c.id}: checker accepted the wrong answer {wrong!r}"


@pytest.mark.parametrize(
    "a,b",
    [
        ("Mass * Length^2 / Time^2", "Length^2 * Mass / Time^2"),
        ("Mass * Length^2 / (Time^2 * Temperature)", "Length^2 * Mass / Time^2 / Temperature"),
        ("1 / Time", "Time^-1"),
    ],
)
def test_dimension_comparison_is_order_and_grouping_independent(a, b):
    assert parse_dimension(a) == parse_dimension(b)


def test_arm_prompts_differ_only_in_treatment():
    """Every arm must differ from arm A only by added instructions, never by a changed
    problem statement."""
    c = CORPUS[0]
    base = render_arm("A", c)
    for arm in ARMS:
        p = render_arm(arm, c)
        assert c.prose in p.user and c.question in p.user
        assert p.system == base.system
