"""A probability law may not depend on itself (HML-S607).

Found by the compositional-failure study as CT-022, one of three specimens that compiled
clean while losing meaning. `prior a ~ Normal(location := b)` together with
`prior b ~ Normal(location := a)` specifies no joint distribution: there is no density to
factor and nothing to infer from. Before this check it produced zero diagnostics.

The positive cases matter as much as the negatives. Hierarchical models are the ordinary
idiom this language exists for, and a cycle check that rejected them would be worse than
no check at all.
"""

from __future__ import annotations

import pathlib

import pytest

from hamiltonian_lang import compile_source


def _codes(src: str) -> list[str]:
    r = compile_source(src, "<test>")
    return [d.code for d in r.diagnostics.items if d.severity == "error"]


def _ok(src: str) -> bool:
    return compile_source(src, "<test>").ok()


# ---------------------------------------------------------------------------
# Rejected
# ---------------------------------------------------------------------------


def test_a_mutually_recursive_pair_is_rejected():
    assert "HML-S607" in _codes(
        "module M\nparam a : Real\nparam b : Real\n"
        "prior a ~ Normal(location := b, scale := 1.0)\n"
        "prior b ~ Normal(location := a, scale := 1.0)\n"
    )


def test_a_three_cycle_is_rejected():
    assert "HML-S607" in _codes(
        "module M\nparam a : Real\nparam b : Real\nparam c : Real\n"
        "prior a ~ Normal(location := b, scale := 1.0)\n"
        "prior b ~ Normal(location := c, scale := 1.0)\n"
        "prior c ~ Normal(location := a, scale := 1.0)\n"
    )


def test_self_reference_through_a_conditioning_variable_is_rejected():
    """`law x | x ~ ...` is a one-node cycle and the same walk must catch it."""
    assert "HML-S607" in _codes(
        "module M\nparam a : Real\n"
        "prior a | a ~ Normal(location := 0.0, scale := 1.0)\n"
    )


def test_self_reference_through_a_parameter_is_rejected():
    assert "HML-S607" in _codes(
        "module M\nparam a : Real\n"
        "prior a ~ Normal(location := a, scale := 1.0)\n"
    )


# ---------------------------------------------------------------------------
# Accepted -- the idioms this language is for
# ---------------------------------------------------------------------------


def test_a_hierarchical_model_is_accepted():
    assert _ok(
        "module M\nparam mu : Real\nparam y : Real\n"
        "prior mu ~ Normal(location := 0.0, scale := 1.0)\n"
        "likelihood y | mu ~ Normal(location := mu, scale := 1.0)\n"
    )


def test_a_three_level_hierarchy_is_accepted():
    assert _ok(
        "module M\nparam tau : PositiveReal\nparam mu : Real\nparam y : Real\n"
        "prior tau ~ Gamma(shape := 2.0, rate := 1.0)\n"
        "prior mu ~ Normal(location := 0.0, scale := tau)\n"
        "likelihood y | mu ~ Normal(location := mu, scale := 1.0)\n"
    )


def test_a_symbol_with_no_law_is_not_a_node():
    """Only symbols that HAVE a law can participate in a law cycle."""
    assert _ok(
        "module M\nparam c : Real\nparam a : Real\n"
        "prior a ~ Normal(location := c, scale := 1.0)\n"
    )


@pytest.mark.parametrize(
    "example",
    [
        "examples/statistics/bayesian_coin.hml",
        "examples/statistics/normal_distribution.hml",
    ],
)
def test_shipped_probabilistic_examples_still_compile(example):
    root = pathlib.Path(__file__).resolve().parents[2]
    src = (root / example).read_text()
    assert compile_source(src, example).ok()
