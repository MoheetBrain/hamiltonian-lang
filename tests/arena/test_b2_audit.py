"""Endpoint B2 adversarial audit: quantifier scope with a fair compact control.

B2 is the experiment HML was actually designed for — binder scope — and it was blocked
until a control existed that can *read* nesting. AST-v1 could not: its answers were
predicted on 5/5 configurations by "say `forall` if `forall` appears anywhere", and its
prompts ran 1.8x SE, so its B1 last place was confounded with length. AST_V2 replaces it
here; **AST-v1 and all its results are preserved untouched**, it is simply not an arm in
this experiment.

The audit below is written to falsify B2's fairness, not confirm it.
"""

from __future__ import annotations

import re

import pytest
from evaluation.arena.endpoints.common import build_prompt
from evaluation.arena.ir import Quant, canonical
from evaluation.arena.parity import ARM_RENDERERS, check_corpus
from evaluation.arena.run_screen import _INSTRUCTIONS, build_dev_pairs

ARMS = ("SE", "AST_V2", "HML")
PAIRS = build_dev_pairs("ENDPOINT_B2", "L3", 8, ("QUANTIFIER_ORDER",))
ITEMS = [it for p in PAIRS for it in p]


def _prompt(item, arm):
    return build_prompt(item, ARM_RENDERERS[arm], instructions=_INSTRUCTIONS)


def test_semantic_parity_across_all_three_arms():
    n, bad = check_corpus([i.world for i in ITEMS])
    assert not bad, "\n".join(r.report() for r in bad[:3])
    assert n == len(ITEMS)


def test_every_pair_flips_and_is_minimal():
    for a, b in PAIRS:
        assert a.answer != b.answer, "a pair whose members agree tests nothing"
        assert a.world.relation == b.world.relation, "the relation must be untouched"
        assert a.world.facts == b.world.facts
        assert a.world.domain == b.world.domain


def test_binder_swap_is_observable_in_every_arm():
    """If an arm renders both orders identically the endpoint measures nothing there."""
    for arm in ARMS:
        r = ARM_RENDERERS[arm]
        for a, b in PAIRS:
            assert r.question(a.world) != r.question(b.world), f"{arm} hides the swap"


def test_binder_nesting_survives_round_trip_in_every_arm():
    from evaluation.arena.parity import ARM_DECODERS

    for arm in ARMS:
        r = ARM_RENDERERS[arm]
        for item in ITEMS:
            back = ARM_DECODERS[arm](r.state(item.world), r.question(item.world), item.family)
            got, want = back.query.claim, item.world.query.claim
            assert canonical(got) == canonical(want)
            assert isinstance(got, Quant) and isinstance(want, Quant)
            assert (got.kind, got.var) == (want.kind, want.var)
            assert (got.body.kind, got.body.var) == (want.body.kind, want.body.var)


def test_ast_v2_carries_nesting_by_depth_not_by_token_presence():
    """The AST-v1 failure mode: both orders contain the same tokens.

    AST_V2 must distinguish them by structure, so the two renderings differ even though
    their multisets of tokens are identical.
    """
    r = ARM_RENDERERS["AST_V2"]
    for a, b in PAIRS:
        qa, qb = r.question(a.world), r.question(b.world)
        assert qa != qb
        assert sorted(re.findall(r"[A-Za-z_]+|\d+", qa)) == sorted(
            re.findall(r"[A-Za-z_]+|\d+", qb)
        ), "the orders should differ only in arrangement, which is the point"


@pytest.mark.parametrize("arm", ARMS)
def test_no_leakage(arm):
    for item in ITEMS:
        t = _prompt(item, arm)
        for bad in ("_swap", "_flip", "Arena_", "QUANTIFIER_ORDER", "gold"):
            assert bad not in t, f"{item.item_id}/{arm} leaks {bad!r}"
        assert item.world.world_id not in t
        assert str(item.world.seed) not in t
        assert f"FINAL: {item.answer}" not in t


def test_answer_key_is_balanced_and_no_constant_wins():
    from collections import Counter

    c = Counter(i.answer for i in ITEMS)
    assert c["TRUE"] == c["FALSE"], f"unbalanced key: {dict(c)}"
    for const in ("TRUE", "FALSE"):
        both = sum(1 for a, b in PAIRS if a.answer == const and b.answer == const)
        assert both == 0, f"always-{const} would score {both} pairs"


@pytest.mark.parametrize("arm", ARMS)
def test_deterministic_rendering(arm):
    for item in ITEMS:
        assert _prompt(item, arm) == _prompt(item, arm)


def test_hml_arm_still_compiles():
    from hamiltonian_lang import compile_source

    for item in ITEMS:
        assert compile_source(ARM_RENDERERS["HML"].compilable(item.world), "<b2>").ok()


def test_seed_band_is_fresh_and_disjoint_from_every_burned_band():
    from evaluation.arena.bands import BANDS, assert_band

    assert_band([i.world.seed for i in ITEMS], "ENDPOINT_B2")
    for name in ("GATE", "DEV_SELECTION", "ACQUISITION", "PILOT", "DIAGNOSTIC",
                 "ENDPOINT_A", "CAUSAL_DIAGNOSIS"):
        lo, hi = BANDS[name]
        for i in ITEMS:
            assert not (lo <= i.world.seed <= hi), f"{i.item_id} collides with {name}"


def test_ast_v2_is_not_longer_than_the_other_arms():
    """The control must not lose on length. AST-v1's B1 result was confounded that way."""
    # `tiktoken` is an optional dependency, not in the `dev` extra, so a clean clone must
    # skip this rather than fail collection. `budget.py` imports it lazily for the same
    # reason; a direct import here would have broken a fresh checkout.
    tiktoken = pytest.importorskip("tiktoken")

    enc = tiktoken.get_encoding("cl100k_base")
    means = {
        arm: sum(len(enc.encode(_prompt(i, arm))) for i in ITEMS) / len(ITEMS)
        for arm in ARMS
    }
    assert means["AST_V2"] <= means["SE"], means
    assert means["AST_V2"] <= means["HML"], means


def test_ast_v2_borrows_no_hml_machinery():
    """Generic means generic: no HML keyword may appear in the control."""
    r = ARM_RENDERERS["AST_V2"]
    for item in ITEMS:
        text = r.state(item.world) + r.question(item.world)
        for kw in ("assume", "goal", "var ", "Proposition", "module", "derive", "proved"):
            assert kw not in text, f"AST_V2 leaks HML construct {kw!r}"
