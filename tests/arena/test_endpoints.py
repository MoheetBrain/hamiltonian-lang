"""The three endpoints: unique answers, minimal pairs, and a correct corruption oracle."""

from __future__ import annotations

from collections import Counter

import pytest
from evaluation.arena.corpus import INSTRUCTIONS, build_corpus, prompts_for
from evaluation.arena.endpoints import contrast, corruption, next_action
from evaluation.arena.endpoints.common import build_prompt
from evaluation.arena.ir import canonical
from evaluation.arena.oracles import entailment, eval_term
from evaluation.arena.parity import ARM_RENDERERS

SEEDS = range(200_001, 200_031)


# ---------------------------------------------------------------------------
# A. next-action
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "family", ["ALGEBRAIC_DEPENDENCY_GRAPH", "FINITE_LOGIC_WORLD"]
)
def test_next_action_items_build_and_have_one_key(family):
    items = next_action.build_items(family, "L3", SEEDS)
    assert len(items) >= 20, "too few items survived construction"
    for i in items:
        assert i.answer in [o.key for o in i.options]
        assert len({o.key for o in i.options}) == len(i.options)


def test_next_action_algebraic_key_is_the_only_reachable_correct_value():
    """Re-derive the oracle property here, independently of the constructor."""
    from evaluation.arena.endpoints.next_action import _defs, _ready, _value_of

    for i in next_action.build_items("ALGEBRAIC_DEPENDENCY_GRAPH", "L3", SEEDS):
        defs = _defs(i.world)
        resolved = {e.left.name for e in i.established}
        cache: dict = {}
        passing = [
            o.key
            for o in i.options
            if _ready(o.prop.left.name, resolved, defs)
            and o.prop.right.value == _value_of(o.prop.left.name, defs, cache)
        ]
        assert passing == [i.answer]


def test_next_action_logic_key_is_the_only_entailed_new_literal():
    from evaluation.arena.ir import Not

    for i in next_action.build_items("FINITE_LOGIC_WORLD", "L3", SEEDS):
        atoms = [d.name for d in i.world.decls]
        facts = [f.prop for f in i.world.facts]
        est = {
            (p.inner.name if isinstance(p, Not) else p.name) for p in i.established
        }
        passing = []
        for o in i.options:
            p = o.prop
            name = p.inner.name if isinstance(p, Not) else p.name
            want = "FALSE" if isinstance(p, Not) else "TRUE"
            if name not in est and entailment(atoms, facts, name) == want:
                passing.append(o.key)
        assert passing == [i.answer]


def test_next_action_distractors_cover_every_declared_role():
    items = next_action.build_items("ALGEBRAIC_DEPENDENCY_GRAPH", "L3", SEEDS)
    roles = Counter(o.role for i in items for o in i.options)
    for role in ("correct", "not_yet_reachable", "wrong_arithmetic", "already_established"):
        assert roles[role] > 0, f"role {role} never appeared"


# ---------------------------------------------------------------------------
# B. minimal contrasts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", contrast.CONTRASTS)
def test_contrast_pairs_are_minimal_and_answer_flipping(kind):
    pairs = contrast.build_pairs(kind, "L3", SEEDS)
    assert pairs, f"no pairs built for {kind}"
    for a, b in pairs:
        assert a.pair_id == b.pair_id
        assert a.answer != b.answer, "a pair whose members agree tests nothing"
        assert a.world.decls == b.world.decls
        assert a.world.domain == b.world.domain
        if a.world.relation is not None:
            assert a.world.relation == b.world.relation
            # The edit is in the claim; the facts must be untouched.
            assert a.world.facts == b.world.facts
        else:
            diff = [
                j
                for j, (x, y) in enumerate(zip(a.world.facts, b.world.facts, strict=True))
                if canonical(x.prop) != canonical(y.prop)
            ]
            assert len(diff) == 1, f"{len(diff)} facts differ; the pair is not minimal"


def test_quantifier_order_pairs_differ_only_by_binder_nesting():
    from evaluation.arena.ir import Quant

    for a, b in contrast.build_pairs("QUANTIFIER_ORDER", "L3", SEEDS):
        ca, cb = a.world.query.claim, b.world.query.claim
        assert isinstance(ca, Quant) and isinstance(cb, Quant)
        # Same two binders, opposite nesting; the innermost body is untouched.
        assert (ca.kind, ca.var) == (cb.body.kind, cb.body.var)
        assert (ca.body.kind, ca.body.var) == (cb.kind, cb.var)
        assert canonical(ca.body.body) == canonical(cb.body.body)


def test_pair_scoring_punishes_a_constant_answer():
    """The reason endpoint B is scored on pairs rather than items."""
    from evaluation.arena.scoring import Scored, pair_score

    pairs = contrast.build_pairs("QUANTIFIER_ORDER", "L3", SEEDS)
    always_true = {}
    for a, b in pairs:
        for it in (a, b):
            always_true[it.item_id] = Scored(it.item_id, True, it.answer == "TRUE", "TRUE")
    result = pair_score(always_true, pairs)
    assert result["both_correct"] == 0
    assert result["both_correct_rate"] == 0.0


# ---------------------------------------------------------------------------
# C. corruption
# ---------------------------------------------------------------------------


def test_corruption_key_is_the_first_wrong_line():
    items = corruption.build_items("L3", SEEDS)
    assert len(items) >= 10
    for i in items:
        values = {}
        first_bad = "NONE"
        for j, line in enumerate(i.derivation):
            name = line.left.name
            claimed = line.right.value
            rhs = next(f.prop.right for f in i.world.facts if f.prop.left.name == name)
            if eval_term(rhs, values) != claimed:
                first_bad = f"d{j}"
                break
            values[name] = claimed
        assert first_bad == i.answer


def test_corruption_corpus_is_not_all_corrupt_or_all_clean():
    items = corruption.build_items("L3", SEEDS)
    clean = sum(1 for i in items if i.answer == "NONE")
    assert 0 < clean < len(items), "a constant answer would score well"


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


def test_prompts_differ_only_in_the_rendered_blocks():
    """The instructions and answer rule are identical across arms, byte for byte."""
    items = next_action.build_items("ALGEBRAIC_DEPENDENCY_GRAPH", "L3", SEEDS)[:5]
    for i in items:
        texts = {a: build_prompt(i, ARM_RENDERERS[a], instructions=INSTRUCTIONS) for a in ARM_RENDERERS}
        for t in texts.values():
            assert t.startswith(INSTRUCTIONS)
            assert t.rstrip().endswith("FINAL: <answer>")
            assert "STATE" in t and "QUESTION" in t and "OPTIONS" in t
        assert len(set(texts.values())) == len(texts), "arms produced identical prompts"


def test_corpus_is_deterministic():
    a, b = build_corpus(levels=("L3",), n_seeds=8), build_corpus(levels=("L3",), n_seeds=8)
    for arm in ARM_RENDERERS:
        assert prompts_for(a.items, arm) == prompts_for(b.items, arm)


def test_no_prompt_leaks_the_answer_key():
    """A prompt that contains its own answer measures nothing.

    Only checked where the answer is a token that could plausibly appear -- the option
    letters and NONE are addressing, not content, so they are expected in the prompt.
    """
    c = build_corpus(levels=("L3",), n_seeds=10, endpoints=("CONTRAST",))
    for arm in ARM_RENDERERS:
        for item, text in zip(c.items, prompts_for(c.items, arm), strict=True):
            if item.world.query.kind == "TRUTH":
                assert "FINAL: TRUE" not in text and "FINAL: FALSE" not in text
