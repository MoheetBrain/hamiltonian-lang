"""The world factory: determinism, oracle agreement, and no drift from the difficulty lab."""

from __future__ import annotations

import pytest
from evaluation.arena.ir import canonical
from evaluation.arena.oracles import entailment, eval_prop, solve_values
from evaluation.arena.worlds import (
    FAMILIES,
    FAMILY_CODES,
    LEVELS,
    canonical_world,
    generate,
)

SEEDS = range(200_001, 200_013)


@pytest.mark.parametrize("family", sorted(FAMILIES))
@pytest.mark.parametrize("level", sorted(LEVELS))
def test_generation_is_deterministic_in_the_seed(family, level):
    for s in SEEDS:
        a, b = generate(family, level, s), generate(family, level, s)
        assert canonical_world(a) == canonical_world(b)
        assert a.query.answer == b.query.answer


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_different_seeds_give_different_worlds(family):
    forms = {canonical_world(generate(family, "L3", s)) for s in SEEDS}
    assert len(forms) == len(list(SEEDS)), "seeds collapsed onto the same world"


def test_family_codes_are_unique():
    """Both finite families begin 'fini'; a truncation scheme would collide silently."""
    assert len(set(FAMILY_CODES.values())) == len(FAMILY_CODES)
    assert set(FAMILY_CODES) == set(FAMILIES)


def test_levels_have_not_drifted_from_the_difficulty_lab():
    """The arena copies difficulty-lab-1.0.0's ladder rather than importing it.

    Copying keeps the frozen evidence free of new importers; this test is what stops
    the two from quietly diverging, which would make arena difficulty incomparable to
    the levels already calibrated.
    """
    from evaluation.h2.difficulty_lab.families import LEVELS as LAB

    for level in LEVELS:
        assert LEVELS[level] == LAB[level], f"{level} differs from the difficulty lab"


@pytest.mark.parametrize("level", sorted(LEVELS))
def test_algebraic_answer_matches_an_independent_resolve(level):
    for s in SEEDS:
        w = generate("ALGEBRAIC_DEPENDENCY_GRAPH", level, s)
        values = solve_values([f.prop for f in w.facts])
        assert str(values[w.query.target]) == w.query.answer


@pytest.mark.parametrize("level", sorted(LEVELS))
def test_logic_answer_matches_exhaustive_enumeration(level):
    for s in SEEDS:
        w = generate("FINITE_LOGIC_WORLD", level, s)
        atoms = [d.name for d in w.decls]
        assert entailment(atoms, [f.prop for f in w.facts], w.query.target) == w.query.answer


@pytest.mark.parametrize("level", sorted(LEVELS))
def test_quantifier_answer_matches_table_evaluation(level):
    for s in SEEDS:
        w = generate("FINITE_QUANTIFIER_WORLD", level, s)
        truth = eval_prop(w.query.claim, table=w.relation.table(), domain=w.domain)
        assert ("TRUE" if truth else "FALSE") == w.query.answer


def test_relation_is_stored_as_a_full_extension():
    w = generate("FINITE_QUANTIFIER_WORLD", "L3", 200_001)
    table = w.relation.table()
    assert len(table) == len(w.domain) ** 2, "the table must cover every ordered pair"
    assert all(t in table for t in w.relation.true_tuples)


def test_canonical_world_is_insensitive_to_fact_order():
    """Fact order is a rendering choice; two orders of the same content are one world."""
    from dataclasses import replace

    w = generate("FINITE_LOGIC_WORLD", "L3", 200_002)
    shuffled = replace(w, facts=tuple(reversed(w.facts)))
    assert canonical_world(shuffled) == canonical_world(w)


def test_canonical_world_is_sensitive_to_content():
    from dataclasses import replace

    w = generate("FINITE_LOGIC_WORLD", "L3", 200_002)
    dropped = replace(w, facts=w.facts[:-1])
    assert canonical_world(dropped) != canonical_world(w)


def test_no_undefined_terms_are_generated():
    """Division never appears, so no world can depend on a definedness side condition."""
    for level in LEVELS:
        for s in SEEDS:
            w = generate("ALGEBRAIC_DEPENDENCY_GRAPH", level, s)
            for f in w.facts:
                assert " / " not in canonical(f.prop)
