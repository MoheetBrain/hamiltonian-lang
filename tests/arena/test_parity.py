"""Representation parity -- the load-bearing test of the whole arena.

If these fail, no result from the arena means anything: a difference between arms could
be a difference in what each arm was told, and no amount of careful scoring recovers
from that.
"""

from __future__ import annotations

import pytest
from evaluation.arena.decoders import DecodeError, decode_english
from evaluation.arena.ir import Atom, Conn, Not, canonical
from evaluation.arena.parity import ARM_RENDERERS, check_corpus, check_world
from evaluation.arena.worlds import FAMILIES, LEVELS, generate

SEEDS = range(200_001, 200_011)


@pytest.mark.parametrize("family", sorted(FAMILIES))
@pytest.mark.parametrize("level", sorted(LEVELS))
def test_every_arm_round_trips_to_the_same_canonical_world(family, level):
    worlds = [generate(family, level, s) for s in SEEDS]
    n, bad = check_corpus(worlds)
    assert n == len(worlds)
    assert not bad, "\n".join(r.report() for r in bad[:3])


def test_parity_detects_a_dropped_fact():
    """A parity check that cannot fail is not evidence. This proves it can."""
    from dataclasses import replace

    w = generate("FINITE_LOGIC_WORLD", "L3", 200_001)
    lying = replace(w, facts=w.facts[:-1])

    class DroppingRenderer:
        """Renders one fact short -- exactly the defect parity exists to catch."""

        def state(self, _):
            return ARM_RENDERERS["SE"].state(lying)

        def question(self, world):
            return ARM_RENDERERS["SE"].question(world)

        def prop(self, p):
            return ARM_RENDERERS["SE"].prop(p)

    original = ARM_RENDERERS["SE"]
    ARM_RENDERERS["SE"] = DroppingRenderer()
    try:
        result = check_world(w)
    finally:
        ARM_RENDERERS["SE"] = original
    assert not result.ok and "SE" in result.failures


@pytest.mark.parametrize("level", sorted(LEVELS))
def test_hml_arm_compiles_under_the_real_compiler(level):
    """An HML arm the compiler would reject is authoritative-looking output that is wrong."""
    from hamiltonian_lang import compile_source

    r = ARM_RENDERERS["HML"]
    for family in FAMILIES:
        for s in SEEDS:
            w = generate(family, level, s)
            result = compile_source(r.compilable(w), f"<{w.world_id}>")
            assert result.ok(), (
                f"{w.world_id} did not compile:\n{result.diagnostics.render()}"
            )


def test_english_is_unambiguous_for_nested_connectives():
    """The prefix markers are what make recursive descent deterministic.

    `both A and B` and `both B and A` differ, and a left-nested conjunction renders
    differently from a right-nested one -- so the two readings that plague bare
    `A and B or C` cannot both arise here.
    """
    se = ARM_RENDERERS["SE"]
    left = Conn("and", Conn("and", Atom("P1"), Atom("P2")), Atom("P3"))
    right = Conn("and", Atom("P1"), Conn("and", Atom("P2"), Atom("P3")))
    assert se.prop(left) != se.prop(right)

    from evaluation.arena.decoders import _Cursor, _en_prop, _tok

    for p in (left, right, Not(Conn("or", Atom("P1"), Atom("P2")))):
        back = _en_prop(_Cursor(_tok(se.prop(p))))
        assert canonical(back) == canonical(p)


def test_decoder_rejects_text_it_cannot_read():
    with pytest.raises(DecodeError):
        decode_english("DECLARATIONS\n  nonsense line\n", "", "FINITE_LOGIC_WORLD")


@pytest.mark.parametrize("arm", sorted(ARM_RENDERERS))
def test_renderings_are_non_empty_and_stable(arm):
    r = ARM_RENDERERS[arm]
    for family in FAMILIES:
        w = generate(family, "L3", 200_001)
        a, b = r.state(w), r.state(w)
        assert a == b and a.strip()
        assert r.question(w).strip()
