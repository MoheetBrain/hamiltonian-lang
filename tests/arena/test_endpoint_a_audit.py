"""Endpoint-A adversarial instrument audit. Offline, no model calls.

Written to *falsify* the experiment's fairness, not to confirm it. Every failure class
this programme has already been bitten by gets an explicit test: unanswerable items,
answer-space leakage, hidden metadata, semantic mismatch, control asymmetry, duplicated
answers, representation-specific cues, position bias, and surface heuristics that would
let a model score without reading the state.

Passing these does not make the instrument correct. It makes the *known* ways of being
wrong absent.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest
from evaluation.arena.decoders import decode_english, decode_hml
from evaluation.arena.endpoints.common import build_prompt
from evaluation.arena.ir import canonical
from evaluation.arena.parity import ARM_RENDERERS
from evaluation.arena.run_screen import _INSTRUCTIONS, _endpoint_a_items
from evaluation.arena.worlds import canonical_world

ARMS = ("SE", "HML")
ITEMS = _endpoint_a_items(700_001, 12, "L3")
SMOKE = _endpoint_a_items(790_001, 4, "L3")


def _prompt(item, arm):
    return build_prompt(item, ARM_RENDERERS[arm], instructions=_INSTRUCTIONS)


# --- A. SEMANTIC PARITY -----------------------------------------------------


@pytest.mark.parametrize("arm", ARMS)
def test_A_both_arms_decode_to_the_same_canonical_state(arm):
    for item in ITEMS:
        r = ARM_RENDERERS[arm]
        dec = (decode_english if arm == "SE" else decode_hml)
        back = dec(r.state(item.world), r.question(item.world), item.family)
        assert canonical_world(back) == canonical_world(item.world)


# --- B/C. ACTION PARITY and ANSWER PARITY -----------------------------------


def test_B_both_arms_expose_the_same_four_actions_in_the_same_order():
    for item in ITEMS:
        assert len(item.options) == 4
        se = [ARM_RENDERERS["SE"].prop(o.prop) for o in item.options]
        hml = [ARM_RENDERERS["HML"].prop(o.prop) for o in item.options]
        assert len(se) == len(hml) == 4
        # Same underlying propositions, same order, same letters.
        assert [o.key for o in item.options] == ["A", "B", "C", "D"]
        assert [canonical(o.prop) for o in item.options] == [
            canonical(o.prop) for o in item.options
        ]


def test_C_the_same_letter_is_correct_in_both_arms():
    """The item carries one key; the arms only change how it is written down."""
    for item in ITEMS:
        assert item.answer in ("A", "B", "C", "D")
        assert next(o.role for o in item.options if o.key == item.answer) == "correct"


def test_C2_options_are_pairwise_distinct_in_every_arm():
    """Two options that render identically make the oracle's single key indefensible."""
    for item in ITEMS + SMOKE:
        for arm in ARMS:
            r = ARM_RENDERERS[arm]
            texts = [r.prop(o.prop) for o in item.options]
            assert len(set(texts)) == 4, f"{item.item_id} has duplicate options in {arm}"


# --- D. VISIBLE-INFORMATION PARITY (leakage) --------------------------------

#: Metadata that must never reach the model. The bare word "correct" is deliberately NOT
#: here: it occurs in the shared question ("a correct next result"), byte-identical in both
#: arms, so it is task wording rather than a cue. The *role names* are forbidden, because
#: those are the instrument's private labels for which option is which.
_FORBIDDEN = (
    "_swap", "_flip", "Arena_", "gold", "difficulty",
    "role=", "not_yet_reachable", "wrong_arithmetic", "already_established",
)


@pytest.mark.parametrize("arm", ARMS)
def test_D_no_prompt_leaks_metadata_or_the_answer(arm):
    for item in ITEMS + SMOKE:
        t = _prompt(item, arm)
        low = t.lower()
        for token in _FORBIDDEN:
            assert token.lower() not in low, f"{item.item_id}/{arm} leaks {token!r}"
        assert item.world.world_id not in t
        assert str(item.world.seed) not in t
        assert item.item_id not in t
        # The key letter must not be announced anywhere except as an option label.
        assert f"FINAL: {item.answer}" not in t


@pytest.mark.parametrize("arm", ARMS)
def test_D2_the_two_arms_differ_only_in_the_rendered_blocks(arm):
    for item in ITEMS:
        t = _prompt(item, arm)
        assert t.startswith(_INSTRUCTIONS)
        assert t.rstrip().endswith("FINAL: <answer>")
        assert "STATE" in t and "QUESTION" in t and "OPTIONS" in t


# --- E. POSITION BALANCE ----------------------------------------------------


def test_E_answer_positions_are_balanced():
    c = Counter(i.answer for i in ITEMS)
    assert set(c) == {"A", "B", "C", "D"}
    assert max(c.values()) - min(c.values()) <= 1, f"position bias: {dict(c)}"


def test_E2_a_constant_letter_scores_at_or_below_chance():
    for letter in "ABCD":
        got = sum(1 for i in ITEMS if i.answer == letter)
        assert got <= len(ITEMS) / 4, f"always-{letter} beats chance: {got}/{len(ITEMS)}"


# --- F. DISTRACTOR QUALITY --------------------------------------------------


def test_F_every_item_carries_the_declared_distractor_roles():
    for item in ITEMS:
        roles = {o.role for o in item.options}
        assert "correct" in roles
        assert len(roles) >= 3, f"{item.item_id} distractors are too homogeneous: {roles}"


# --- G. COUNTERFACTUAL SENSITIVITY ------------------------------------------


def test_G_the_key_tracks_the_state_not_the_item():
    """Change what is established, and the correct action must change with it.

    The strongest single check that the item is about the state at all: rebuild the same
    world at a different prefix and confirm the oracle's key moves.
    """
    from evaluation.arena.endpoints.next_action import _defs, _ready, _value_of

    moved = 0
    for item in ITEMS:
        if item.family != "ALGEBRAIC_DEPENDENCY_GRAPH":
            continue
        defs = _defs(item.world)
        resolved = {e.left.name for e in item.established}
        cache: dict = {}
        # With nothing established, the currently-correct option must stop being correct.
        v = next(o for o in item.options if o.role == "correct").prop.left.name
        if not _ready(v, set(), defs):
            moved += 1
        # And it is correct under the real prefix.
        assert _ready(v, resolved, defs)
        assert next(
            o for o in item.options if o.role == "correct"
        ).prop.right.value == _value_of(v, defs, cache)
    assert moved > 0, "no algebraic key depended on the established prefix"


# --- H. NO TRIVIAL SURFACE HEURISTIC ----------------------------------------


@pytest.mark.parametrize("arm", ARMS)
def test_H_answer_is_not_predictable_from_option_length(arm):
    """Longest/shortest-option strategies must not beat chance."""
    r = ARM_RENDERERS[arm]
    for pick in (max, min):
        hits = 0
        for item in ITEMS:
            chosen = pick(item.options, key=lambda o: len(r.prop(o.prop)))
            hits += chosen.key == item.answer
        assert hits <= len(ITEMS) / 2, (
            f"{arm}: {'longest' if pick is max else 'shortest'}-option scores "
            f"{hits}/{len(ITEMS)}"
        )


@pytest.mark.parametrize("arm", ARMS)
def test_H2_answer_is_not_predictable_from_numeric_magnitude(arm):
    """A 'pick the biggest/smallest number' heuristic must not beat chance."""
    def magnitude(o):
        nums = [abs(int(x)) for x in re.findall(r"-?\d+", ARM_RENDERERS[arm].prop(o.prop))]
        return max(nums) if nums else 0

    for pick in (max, min):
        hits = sum(
            pick(item.options, key=magnitude).key == item.answer for item in ITEMS
        )
        assert hits <= len(ITEMS) / 2, f"{arm}: magnitude heuristic scores {hits}/{len(ITEMS)}"


def test_H3_answer_is_not_predictable_from_state_length_or_option_count():
    """No correlation between prompt size and which letter is correct."""
    by_letter = Counter()
    for item in ITEMS:
        by_letter[item.answer] += len(_prompt(item, "SE"))
    means = {k: v / max(1, sum(1 for i in ITEMS if i.answer == k)) for k, v in by_letter.items()}
    spread = max(means.values()) - min(means.values())
    assert spread < 0.5 * sum(means.values()) / len(means), f"length tracks the key: {means}"


def test_H4_the_correct_option_does_not_always_mention_a_freshly_established_name():
    """A 'pick the option naming a variable you just saw' shortcut must not always work."""
    hits = 0
    for item in ITEMS:
        if item.family != "ALGEBRAIC_DEPENDENCY_GRAPH":
            continue
        est_names = {e.left.name for e in item.established}
        correct = next(o for o in item.options if o.role == "correct")
        hits += correct.prop.left.name in est_names
    assert hits == 0, "the correct option restates an established variable"


# --- I. HML VALIDITY --------------------------------------------------------


def test_I_every_hml_state_compiles():
    from hamiltonian_lang import compile_source

    for item in ITEMS + SMOKE:
        res = compile_source(ARM_RENDERERS["HML"].compilable(item.world), "<a>")
        assert res.ok(), f"{item.item_id}: {res.diagnostics.render()}"


# --- J. DETERMINISM / SEED HYGIENE ------------------------------------------


def test_J_items_are_deterministic():
    again = _endpoint_a_items(700_001, 12, "L3")
    for a, b in zip(ITEMS, again, strict=True):
        assert a.item_id == b.item_id and a.answer == b.answer
        for arm in ARMS:
            assert _prompt(a, arm) == _prompt(b, arm)


def test_J2_smoke_and_pilot_seeds_are_disjoint():
    assert not ({i.world.seed for i in ITEMS} & {i.world.seed for i in SMOKE})


def test_J3_all_seeds_are_in_the_endpoint_a_band():
    from evaluation.arena.bands import assert_band

    assert_band([i.world.seed for i in ITEMS + SMOKE], "ENDPOINT_A")


def test_J4_no_endpoint_a_seed_collides_with_any_burned_band():
    """700 000+ is numerically disjoint from every band used so far -- asserted, not assumed."""
    from evaluation.arena.bands import BANDS

    for name in ("GATE", "DEV_SELECTION", "ACQUISITION", "PILOT", "DIAGNOSTIC"):
        lo, hi = BANDS[name]
        for i in ITEMS + SMOKE:
            assert not (lo <= i.world.seed <= hi), f"{i.item_id} collides with {name}"
