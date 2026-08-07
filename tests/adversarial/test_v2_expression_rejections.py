"""What the V2 expression forms must REFUSE (D-026).

Rejection is the product (``CLAUDE.md`` rule 9). Adding eleven expression forms adds
eleven new ways to smuggle a value across a barrier, so this file is the invalid half
of ``CLAUDE.md`` rule 4's eight parts, kept separate from the valid half so that the
count of each is visible.

Each case names the conflation it prevents. A case that only asserts "some error" would
pass if the checker rejected it for an unrelated reason, so every assertion names the
diagnostic code.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source

pytestmark = pytest.mark.adversarial

RVS = (
    "rv X : RandomVariable[Real]\n"
    "rv Y : RandomVariable[Real]\n"
    "rv Z : RandomVariable[Real]\n"
)


def codes(prelude: str, *lines: str) -> list[str]:
    src = "module M\n" + prelude + "\n".join(lines) + "\n"
    return [d.code for d in compile_source(src).diagnostics.errors]


# ---------------------------------------------------------------------------
# The prohibited conflations, retested through every new construct
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "prelude", "line", "why"),
    [
        # Distribution is not a value of its support -- through each new operator.
        ("HML-T428", "param d : Distribution[Real]\n", "def m := expectation(d)",
         "a law has no expectation; bind it to a symbol with '~' first"),
        ("HML-T428", RVS + "param d : Distribution[Real]\n",
         "def m := expectation(X | d)",
         "conditioning is on the value a variable took, not on the law"),
        ("HML-T485", RVS + "param d : Distribution[Real]\n", "def j := joint(X, d)",
         "a law is not a random variable and has no joint law with one"),
        ("HML-T428", RVS, "require joint(X, Y) > 0.0",
         "the joint law is a Distribution and cannot be compared with a value"),
        ("HML-T430", RVS, "def t := joint(X, Y) + 1.0",
         "arithmetic on a probability law is not defined"),
        # RandomVariable is not a value of its codomain.
        ("HML-T403", RVS, "def t : Real := X", "an RV is not a value"),
        ("HML-T403", RVS, "def t : Real := 2.0 * X",
         "lifting tracks the randomness, it does not erase it"),
        ("HML-T403", RVS, "def t : Real := expectation(X | Y)",
         "E[X | Y] is a random variable, not a number"),
        ("HML-T403", RVS, "def t : RandomVariable[Real] := expectation(X)",
         "E[X] is a number, not a random variable"),
        # Probability is not PValue and not PosteriorProbability (D-022).
        ("HML-T403", RVS, "def t : PValue := probability(X > 0.0)",
         "a model probability is not the output of a hypothesis test"),
        ("HML-T403", RVS,
         "def t : PosteriorProbability := probability(X > 0.0)",
         "a probability within the model is not a posterior over hypotheses"),
        ("HML-T403", "rv P : RandomVariable[PValue]\n",
         "def t : PosteriorProbability := expectation(P)",
         "averaging p-values does not produce a posterior"),
        # An event is not a proposition.
        ("HML-T480", RVS, "require X > 0.0",
         "asserting an event claims it holds on every draw"),
        ("HML-T480", RVS, "assume X = Y",
         "an identity between random variables is an event, not a constraint"),
        ("HML-T480", RVS + "param A : Set[Real]\n", "require X in A",
         "whether a draw lands in a set depends on the draw"),
        ("HML-T480", RVS + "param a : Real\n", "require X > 0.0 and a > 0.0",
         "an event combined with a proposition is still an event"),
        # An event is not a probability, and a probability is not an event.
        ("HML-T482", "param a : Real\n", "def t := probability(a > 0.0)",
         "the probability of a fixed proposition is 0 or 1 and states nothing"),
        ("HML-T482", RVS, "def t := probability(X)",
         "a random variable is not an event"),
        ("HML-T482", RVS + "param p : Probability\n", "def t := probability(p)",
         "a probability is not an event"),
    ],
)
def test_a_prohibited_conflation_is_rejected(code, prelude, line, why):
    assert code in codes(prelude, line), why


# ---------------------------------------------------------------------------
# Operand-kind rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("relation", ["associated", "correlated", "causes"])
def test_a_causal_relation_refuses_constants(relation):
    """A constant does not vary, so no claim about how it co-varies is informative."""
    assert "HML-T495" in codes(
        "param a : Real\nparam b : Real\n", f"require {relation}(a, b)"
    )


@pytest.mark.parametrize("relation", ["associated", "correlated", "causes"])
def test_a_causal_relation_refuses_a_law(relation):
    assert "HML-T495" in codes(
        RVS + "param d : Distribution[Real]\n", f"require {relation}(X, d)"
    )


def test_independence_refuses_a_fixed_quantity():
    assert "HML-T485" in codes(RVS + "param a : Real\n", "require independent(X, a)")


def test_expectation_refuses_a_fixed_quantity():
    assert "HML-T481" in codes("param a : Real\n", "def t := expectation(a)")


def test_variance_of_a_vector_valued_random_variable_is_refused():
    """The variance of a vector RV is a covariance matrix, which v2 does not
    represent. Returning NonNegativeReal would be quietly wrong."""
    assert "HML-T484" in codes(
        "const n : PositiveNatural = 3\nrv V : RandomVariable[Vector[Real, n]]\n",
        "def t := variance(V)",
    )


def test_a_fixed_aggregate_cannot_be_conditioned():
    assert "HML-T483" in codes(
        RVS + "const n : PositiveNatural = 3\nparam v : Vector[Real, n]\n",
        "def t := variance(v | X)",
    )


# ---------------------------------------------------------------------------
# Sets
# ---------------------------------------------------------------------------


def test_membership_refuses_a_non_set():
    assert "HML-T486" in codes("param a : Real\nparam b : Real\n", "require a in b")


def test_membership_refuses_an_element_of_the_wrong_type():
    assert "HML-T487" in codes(
        "param b : Bool\nparam A : Set[Real]\n", "require b in A"
    )


def test_membership_refuses_a_unit_interval_conflation():
    """`Set[PValue]` does not admit a `PosteriorProbability`, and the diagnostic
    carries the recorded reason rather than a generic mismatch."""
    from hamiltonian_lang.type_system import _UNIT_INTERVAL_CONFLATIONS

    src = (
        "module M\nparam q : PosteriorProbability\nparam A : Set[PValue]\n"
        "require q in A\n"
    )
    diags = compile_source(src).diagnostics
    hit = next(d for d in diags.errors if d.code == "HML-T487")
    # The exact recorded prohibition, not a generic type mismatch. Membership is a new
    # site where one unit-interval kind could stand in for another, so it has to route
    # through the same table `_conflation_note` uses everywhere else.
    assert _UNIT_INTERVAL_CONFLATIONS[("PosteriorProbability", "PValue")] in hit.notes


def test_a_comprehension_refuses_a_non_proposition():
    assert "HML-T488" in codes("", "def t := {x : Real | x + 1.0}")


def test_a_comprehension_refuses_a_random_predicate():
    """The set it would define is itself random; v2 has no random-set type and will
    not pretend the membership is fixed."""
    assert "HML-T488" in codes(RVS, "def t := {x : Real | X > x}")


def test_continuity_refuses_a_non_function():
    assert "HML-T492" in codes(
        "param a : Real\nparam A : Set[Real]\n", "require continuous(a, on := A)"
    )


def test_continuity_refuses_a_multi_argument_function():
    """Joint continuity is a different property from continuity in each argument, and
    v2 will not silently pick one."""
    assert "HML-T492" in codes(
        "param g : Function[Real, Real -> Real]\nparam A : Set[Real]\n",
        "require continuous(g, on := A)",
    )


def test_continuity_refuses_a_domain_outside_the_function_domain():
    assert "HML-T494" in codes(
        "param f : Function[Natural -> Real]\nparam A : Set[Real]\n",
        "require continuous(f, on := A)",
    )


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def test_a_derivative_refuses_a_body_with_no_dimension():
    assert "HML-T491" in codes("param b : Bool\n", "def t := derivative(b, u : Real)")


def test_an_integral_refuses_bounds_outside_the_binder_type():
    assert "HML-T489" in codes(
        "param v : Quantity[Length / Time]\n",
        "def t := integral(v, u : Quantity[Time], 0.0, 1.0)",
    )


def test_a_limit_refuses_a_non_magnitude_body():
    assert "HML-T490" in codes(
        "param A : Set[Real]\n", "def t := limit(A, x : Real -> 1.0)"
    )


def test_a_limit_may_not_keep_an_open_refinement():
    """1.0 / x is positive for every positive x and its limit need not be."""
    assert "HML-T403" in codes(
        "", "def t : PositiveReal := limit(1.0 / x, x : PositiveReal -> 1.0)"
    )


def test_a_dimensional_derivative_may_not_keep_the_body_dimension():
    assert "HML-T403" in codes(
        "param s : Quantity[Length]\n",
        "def t : Quantity[Length] := derivative(s, u : Quantity[Time])",
    )


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


def test_a_binder_does_not_escape_its_body():
    assert "HML-N301" in codes("", "def t := {x : Real | x > 0.0}", "def u := x")


def test_the_limit_point_is_evaluated_outside_the_binder():
    assert "HML-N301" in codes(
        "", "def t := limit(1.0 / x, x : PositiveReal -> x)"
    )


def test_integral_bounds_are_evaluated_outside_the_binder():
    assert "HML-N301" in codes("", "def t := integral(x, x : Real, x, 1.0)")


def test_a_new_binder_may_not_shadow(monkeypatch=None):
    """D-006 applies to every binder, not only to quantifiers."""
    assert "HML-N302" in codes("param x : Real\n", "def t := {x : Real | x > 0.0}")


# ---------------------------------------------------------------------------
# Surface syntax
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "line"),
    [
        ("HML-P262", "def t := {x | x > 0.0}"),
        ("HML-P262", "def t := derivative(x ^ 2.0, x)"),
        ("HML-P264", "def t := {x : Real}"),
        ("HML-P265", "def t := limit(1.0 / x, x : PositiveReal)"),
        ("HML-P261", "def t := joint(X)"),
        ("HML-P261", "def t := independent(X)"),
        ("HML-P263", "def t := causes(X)"),
        ("HML-P267", "var j : Distribution[Product[Real]]"),
    ],
)
def test_a_malformed_form_is_a_parse_error(code, line):
    assert code in codes(RVS, line)


def test_a_new_keyword_may_not_be_used_as_a_name():
    """Contextual heads would have left two meanings for one spelling. These are full
    keywords, so the collision is a parse error with a rename suggestion."""
    for word in ("limit", "integral", "causes", "probability", "joint", "in"):
        assert "HML-P202" in codes("", f"param {word} : Real"), word


def test_membership_does_not_chain():
    assert "HML-P230" in codes(
        "param a : Real\nparam A : Set[Real]\nparam B : Set[Real]\n",
        "require a in A in B",
    )


def test_a_comparison_may_not_chain_into_membership():
    assert "HML-P230" in codes(
        "param a : Real\nparam A : Set[Real]\n", "require a < 1.0 in A"
    )


def test_continuity_refuses_a_positional_domain():
    assert "HML-P266" in codes(
        "param f : Function[Real -> Real]\nparam A : Set[Real]\n",
        "require continuous(f, A)",
    )


def test_continuity_refuses_an_unknown_role():
    assert "HML-P266" in codes(
        "param f : Function[Real -> Real]\nparam A : Set[Real]\n",
        "require continuous(f, over := A)",
    )
