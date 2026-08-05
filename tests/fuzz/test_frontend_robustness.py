"""Front-end robustness — HML-COMPILER-CORE-003 Phase 1.

The contract the evaluation harness depends on, for **arbitrary** input:

    finite runtime  ->  no uncaught exception  ->  at least one diagnostic or a valid parse

Arbitrary model output reaches the parser. A crash here takes down a run rather than
scoring a bad generation, so these are correctness tests, not hygiene.

Both defects pinned below were found by measurement, not by review:
`docs/evaluation/COMPILER_CORE_AUDIT.md` §1.5.
"""

from __future__ import annotations

import random
import string

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from hamiltonian_lang import compile_source, parse
from hamiltonian_lang.parser import MAX_EXPR_DEPTH

MALFORMED = {
    "incomplete declaration": "param x :",
    "missing operand": "def f := 1 +",
    "missing close paren": "def f := (1 + 2",
    "missing close bracket": "var v : Vector[Real, N",
    "unknown unicode": "var x : ℝ⊗℘",
    "duplicated operators": "def f := 1 ++ 2",
    "truncated mid-token": "param sigma : Positiv",
    "prose mixed with hml": "First we note that\nparam x : Real\nand therefore x>0",
    "unexpected indentation": "    param x : Real\n        var y : Real",
    "invalid role label": "law X ~ Normal(loc := m, sd := s)",
    "unfinished quantifier": "require forall x : Real .",
    "malformed dimension": "param q : Quantity[Mass^ / Time]",
    "empty input": "",
    "only whitespace": "   \n\n  \t ",
    "markdown fence leaked": "```hml\nparam x : Real\n```",
    "json instead of hml": '{"module": "M", "params": []}',
    "latex instead of hml": r"\begin{align} X &\sim \mathcal{N}(\mu,\sigma) \end{align}",
    "half a concept": "concept F\n  parameter a : Real",
    "nested unclosed": "def f := (((((1",
    "very long identifier": "param " + "a" * 5000 + " : Real",
    "deep nesting": "def f := " + "(" * 400 + "1" + ")" * 400,
    "absurd nesting": "def f := " + "(" * 5000 + "1",
    "many statements": "\n".join(f"param p{i} : Real" for i in range(2000)),
}


@pytest.mark.parametrize("src", MALFORMED.values(), ids=list(MALFORMED))
def test_malformed_input_never_crashes(src):
    module, bag = parse(src)
    assert bag.ok() or bag.errors, "neither a valid parse nor any diagnostic"


@pytest.mark.parametrize("src", MALFORMED.values(), ids=list(MALFORMED))
def test_malformed_input_survives_the_whole_pipeline(src):
    """Resolution and type checking must be as robust as the parser."""
    r = compile_source(src)
    assert r.ok() or r.diagnostics.errors


_ALPHABET = string.ascii_letters + string.digits + " \n:=~|()[]{}.,^*/+-<>!?#\t"


@settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.text(alphabet=_ALPHABET, min_size=0, max_size=220))
def test_random_text_never_crashes(src):
    module, bag = parse(src)
    assert bag.ok() or bag.errors


_TOKENS = [
    "param", "var", "law", "~", "::", ":=", ":", "forall", "exists", ".", "(", ")",
    "[", "]", "Real", "Normal", "x", "1", "+", "^", "|", "=>", "end", "concept",
    "module", "require", "prove", "check", "dimension", "infer", "posterior", ",",
]


@settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.sampled_from(_TOKENS), min_size=1, max_size=40))
def test_token_soup_never_crashes(tokens):
    module, bag = parse(" ".join(tokens))
    assert bag.ok() or bag.errors


def test_deep_nesting_is_rejected_not_crashed():
    """Measured defect: 400 nested parens raised RecursionError before the depth bound.

    Each nesting level costs ~12.2 Python stack frames and the default limit of 1000
    breaks at depth 82, so a bound of 120 was never reached. MAX_EXPR_DEPTH is now derived
    from that measurement.
    """
    _, bag = parse("def f := " + "(" * 400 + "1" + ")" * 400)
    assert not bag.ok()
    assert "HML-P240" in bag.codes()


def test_the_depth_bound_is_below_the_measured_recursion_ceiling():
    """If the expression grammar gains levels, this fails before a user finds a crash."""
    assert MAX_EXPR_DEPTH <= 60, (
        f"MAX_EXPR_DEPTH={MAX_EXPR_DEPTH} is close to the measured ceiling of 82; "
        "re-measure frames per level"
    )


def test_nesting_just_below_the_bound_still_parses():
    depth = MAX_EXPR_DEPTH - 10
    _, bag = parse("def f := " + "(" * depth + "1" + ")" * depth)
    assert bag.ok(), bag.render()


def test_randomised_truncation_of_valid_programs_never_crashes():
    """A generation cut off by a token budget is the commonest malformed input there is."""
    valid = (
        "module M\n\nparam mu : Real\nparam sigma : PositiveReal\n"
        "rv X : RandomVariable[Real]\n\nlaw X ~ Normal(location := mu, scale := sigma)\n"
        "require forall a : Real . exists b : Real . b > a\n"
    )
    rng = random.Random(20260804)
    for _ in range(200):
        cut = rng.randrange(0, len(valid))
        _, bag = parse(valid[:cut])
        assert bag.ok() or bag.errors
