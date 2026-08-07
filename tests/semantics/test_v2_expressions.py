"""The eleven V2 mathematical expression forms (D-026).

Organised by the eight parts ``CLAUDE.md`` rule 4 requires, so that a reader can check
coverage rather than infer it:

* **surface syntax** -- ``test_*_parses``
* **AST form**       -- ``test_*_parses`` asserts the node class
* **semantic rule**  -- the scope and alpha-equivalence sections
* **type rule**      -- ``test_*_type`` and the rejection module
* **valid examples** -- ``examples/`` compiles under ``tests/golden``
* **invalid examples** -- ``tests/adversarial/test_v2_expression_rejections.py``
* **backend behaviour** -- ``tests/backends/test_v2_expression_backends.py``
* **round trip**     -- the round-trip section at the bottom of this file

The two exhaustiveness guards at the very end are the most important tests here. Each
new form had to be added in five places, and four of those fail SILENTLY when missed: a
missing canonical branch collapses every instance of a form to one identity, a missing
renderer emits text that re-parses as something else, and a missing graph child drops a
dependency edge. The guards turn each of those into a failing test.
"""

from __future__ import annotations

import json

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import (
    BINDING_EXPRESSIONS,
    SYMMETRIC_RELATIONS,
    ContinuityExpr,
    DerivativeExpr,
    Expr,
    IndependenceExpr,
    IntegralExpr,
    JointExpr,
    LimitExpr,
    MembershipExpr,
    MomentExpr,
    ProbabilityExpr,
    RelationExpr,
    SetComprehension,
)
from hamiltonian_lang.backends.canonical import content_hash
from hamiltonian_lang.backends.hml import render_expr, render_module
from hamiltonian_lang.types import (
    DistributionType,
    EventType,
    ProductType,
    PropositionType,
    RandomVariableType,
    ScalarType,
    SetType,
)

RVS = (
    "rv X : RandomVariable[Real]\n"
    "rv Y : RandomVariable[Real]\n"
    "rv Z : RandomVariable[Real]\n"
)


def compiled(body: str, prelude: str = ""):
    src = "module M\n" + prelude + body
    r = compile_source(src)
    assert r.ok(), "\n" + r.diagnostics.render() + "\n--- source ---\n" + src
    return r


def codes(body: str, prelude: str = "") -> list[str]:
    return [
        d.code for d in compile_source("module M\n" + prelude + body).diagnostics.errors
    ]


def type_of_def(body: str, prelude: str = "", name: str = "t"):
    """The synthesised type of the single ``def`` in ``body``."""
    from hamiltonian_lang.ast.nodes import DefineStmt

    module = compiled(body, prelude).module
    for st in module.statements:
        if isinstance(st, DefineStmt) and st.name == name:
            return st.body.type_
    raise AssertionError(f"no definition named {name!r}")


def first_expr(body: str, prelude: str = ""):
    from hamiltonian_lang.ast.nodes import DefineStmt, RequireStmt

    for st in compiled(body, prelude).module.statements:
        if isinstance(st, DefineStmt):
            return st.body
        if isinstance(st, RequireStmt):
            return st.proposition
    raise AssertionError("no expression statement")


# ===========================================================================
# PROBABILITY -- expectation, conditional expectation, probability, joint,
#                independence
# ===========================================================================


def test_the_expectation_keyword_no_longer_shadows_the_type_rule():
    """The audit's finding 3, directly.

    `expectation` was a reserved keyword with no expression production, so
    `require expectation(X) > 0.0` failed at HML-P231 while a complete, correct type
    rule sat unreachable in the checker. This is the regression pin.
    """
    assert "HML-P231" not in codes("require expectation(X) > 0.0\n", RVS)
    compiled("require expectation(X) > 0.0\n", RVS)


def test_the_infer_query_still_works():
    """The other production that needs the keyword. Deleting the lexer entry -- the
    audit's suggested fix -- would have broken this one."""
    compiled(
        "infer expectation theta\n",
        "param theta : Probability\nprior theta ~ Beta(alpha := 1.0, beta := 1.0)\n",
    )
    compiled(
        "infer variance theta\n",
        "param theta : Probability\nprior theta ~ Beta(alpha := 1.0, beta := 1.0)\n",
    )


def test_expectation_parses_to_a_moment_node():
    e = first_expr("def t := expectation(X | Y)\n", RVS)
    assert isinstance(e, MomentExpr)
    assert e.kind == "expectation"
    assert len(e.given) == 1


# -- the barrier the mission names explicitly -------------------------------


def test_unconditional_expectation_is_a_value_not_a_random_variable():
    assert type_of_def("def t : Real := expectation(X)\n", RVS) == ScalarType("Real")
    assert "HML-T403" in codes(
        "def t : RandomVariable[Real] := expectation(X)\n", RVS
    )


def test_conditional_expectation_on_a_random_variable_IS_a_random_variable():
    t = type_of_def("def t : RandomVariable[Real] := expectation(X | Y)\n", RVS)
    assert t == RandomVariableType(ScalarType("Real"))
    assert "HML-T403" in codes("def t : Real := expectation(X | Y)\n", RVS)


def test_conditioning_on_a_parameter_leaves_a_value():
    """A deterministic function of a constant is a constant. This is what makes
    `expectation(X | theta) = A(theta) @ x` a well-formed equation."""
    t = type_of_def(
        "def t : Real := expectation(X | theta)\n", RVS + "param theta : Real\n"
    )
    assert t == ScalarType("Real")


def test_expectation_is_never_a_distribution():
    assert not isinstance(
        type_of_def("def t := expectation(X)\n", RVS), DistributionType
    )


def test_expectation_of_a_law_is_rejected():
    assert "HML-T428" in codes(
        "def t := expectation(d)\n", "param d : Distribution[Real]\n"
    )


def test_expectation_of_a_fixed_quantity_is_rejected():
    assert "HML-T481" in codes("def t := expectation(a)\n", "param a : Real\n")


def test_conditioning_on_a_law_is_rejected():
    assert "HML-T428" in codes(
        "def t := expectation(X | d)\n", RVS + "param d : Distribution[Real]\n"
    )


def test_expectation_leaves_the_support_for_its_convex_hull():
    """E[N] for a count is not a count. Returning the codomain unchanged -- the obvious
    implementation -- would make `expectation(N) : Natural` compile, which is false."""
    t = type_of_def(
        "def t := expectation(N)\n", "rv N : RandomVariable[Natural]\n"
    )
    assert t == ScalarType("NonNegativeReal")
    assert "HML-T403" in codes(
        "def t : Natural := expectation(N)\n", "rv N : RandomVariable[Natural]\n"
    )


def test_the_expectation_of_an_indicator_is_a_probability():
    t = type_of_def("def t := expectation(B)\n", "rv B : RandomVariable[Bool]\n")
    assert t == ScalarType("Probability")


def test_expectation_does_not_cross_the_unit_interval_kinds():
    """D-022 holds through the new operator: averaging p-values yields p-values, and
    there is still no path from one epistemic kind to another."""
    t = type_of_def("def t := expectation(P)\n", "rv P : RandomVariable[PValue]\n")
    assert t == ScalarType("PValue")
    assert "HML-T403" in codes(
        "def t : PosteriorProbability := expectation(P)\n",
        "rv P : RandomVariable[PValue]\n",
    )


# -- measurable lifting -----------------------------------------------------


def test_a_function_of_a_random_variable_is_a_random_variable():
    t = type_of_def("def t := log(W)\n", "rv W : RandomVariable[PositiveReal]\n")
    assert t == RandomVariableType(ScalarType("Real"))


def test_arithmetic_on_a_random_variable_is_a_random_variable():
    assert type_of_def("def t := 2.0 * X\n", RVS) == RandomVariableType(
        ScalarType("Real")
    )


def test_a_user_function_of_a_random_variable_is_a_random_variable():
    t = type_of_def(
        "def t := f(X)\n", RVS + "def f(u : Real) : Real := u * 2.0\n"
    )
    assert t == RandomVariableType(ScalarType("Real"))


def test_lifting_is_not_a_subtyping_path():
    """The barrier this whole mechanism must not weaken. Lifting happens at operator
    and application sites and RE-WRAPS; it never erases the wrapper into a value."""
    assert "HML-T403" in codes("def t : Real := X\n", RVS)
    assert "HML-T403" in codes("def t : Real := 2.0 * X\n", RVS)
    assert "HML-T403" in codes(
        "def t : Real := log(W)\n", "rv W : RandomVariable[PositiveReal]\n"
    )
    assert "HML-T402" in codes("param p : Real = X\n", RVS)


def test_lifting_is_more_precise_than_the_accident_it_replaced():
    """Two random probabilities may sum above one. Before D-026 this reached `join`,
    which returned RandomVariable[Probability] unchanged."""
    t = type_of_def("def t := P + Q\n", "rv P : RandomVariable[Probability]\n"
                    "rv Q : RandomVariable[Probability]\n")
    assert t == RandomVariableType(ScalarType("NonNegativeReal"))


# -- events -----------------------------------------------------------------


def test_a_comparison_over_a_random_variable_is_an_event():
    assert isinstance(first_expr("require probability(X > 0.0) = 0.5\n", RVS), Expr)
    module = compiled("require probability(X > 0.0) = 0.5\n", RVS).module
    prob = module.statements[-1].proposition.left
    assert isinstance(prob, ProbabilityExpr)
    assert isinstance(prob.event.type_, EventType)


def test_a_comparison_over_fixed_quantities_stays_a_proposition():
    module = compiled("require a > 0.0\n", "param a : Real\n").module
    assert isinstance(module.statements[-1].proposition.type_, PropositionType)


def test_an_event_may_not_be_asserted_as_a_proposition():
    """`require X > 0.0` claims a random inequality holds on every draw while looking
    exactly like an ordinary constraint. The checker makes the author choose."""
    for statement in ("require", "assume", "prove", "check"):
        assert "HML-T480" in codes(f"{statement} X > 0.0\n", RVS), statement


def test_the_event_rejection_names_the_repair():
    diags = compile_source("module M\n" + RVS + "require X > 0.0\n").diagnostics
    hit = next(d for d in diags.errors if d.code == "HML-T480")
    assert "probability(X > 0.0)" in hit.correction


def test_an_event_combined_with_anything_is_still_an_event():
    assert "HML-T480" in codes("require X > 0.0 and a > 0.0\n", RVS + "param a : Real\n")
    assert "HML-T480" in codes("require not (X > 0.0)\n", RVS)


def test_probability_is_a_probability_and_not_the_other_two_kinds():
    assert type_of_def("def t := probability(X > 0.0)\n", RVS) == ScalarType(
        "Probability"
    )
    assert "HML-T403" in codes("def t : PValue := probability(X > 0.0)\n", RVS)
    assert "HML-T403" in codes(
        "def t : PosteriorProbability := probability(X > 0.0)\n", RVS
    )


def test_probability_of_a_non_event_is_rejected():
    assert "HML-T482" in codes(
        "def t := probability(a > 0.0)\n", "param a : Real\n"
    )
    assert "HML-T482" in codes("def t := probability(X)\n", RVS)


def test_conditional_probability_parses_and_checks():
    e = first_expr("def t := probability(X > 0.0 | Y > 0.0)\n", RVS)
    assert isinstance(e, ProbabilityExpr)
    assert len(e.given) == 1


# -- joint and independence -------------------------------------------------


def test_joint_is_a_law_not_a_variable_and_not_a_value():
    t = type_of_def("def t := joint(X, N)\n", RVS + "rv N : RandomVariable[Natural]\n")
    assert t == DistributionType(
        ProductType((ScalarType("Real"), ScalarType("Natural")))
    )
    # Every existing barrier applies to it untouched.
    assert "HML-T428" in codes("require joint(X, Y) > 0.0\n", RVS)
    assert "HML-T430" in codes("def t := joint(X, Y) + 1.0\n", RVS)


def test_joint_needs_random_operands():
    assert "HML-T485" in codes("def t := joint(X, a)\n", RVS + "param a : Real\n")


def test_joint_needs_at_least_two_operands():
    assert "HML-P261" in codes("def t := joint(X)\n", RVS)


def test_independence_is_a_proposition_not_an_event():
    """It is a claim about the LAWS, so it holds or does not and may be asserted."""
    assert isinstance(
        type_of_def("def t := independent(X, Y)\n", RVS), PropositionType
    )
    compiled("require independent(X, Y)\n", RVS)


def test_conditional_independence_parses():
    e = first_expr("def t := independent(X, Y | Z)\n", RVS)
    assert isinstance(e, IndependenceExpr)
    assert len(e.parts) == 2
    assert len(e.given) == 1


def test_independence_needs_random_operands():
    assert "HML-T485" in codes(
        "require independent(X, a)\n", RVS + "param a : Real\n"
    )


def test_variance_of_a_random_variable_squares_the_dimension():
    t = type_of_def(
        "def t : Quantity[Length^2] := variance(H)\n",
        "rv H : RandomVariable[Quantity[Length]]\n",
    )
    assert t.dimension.render() == "Length^2"
    assert "HML-T403" in codes(
        "def t : Quantity[Length] := variance(H)\n",
        "rv H : RandomVariable[Quantity[Length]]\n",
    )


def test_the_aggregate_reading_of_variance_is_preserved():
    """`variance(v)` over a Vector is the dispersion of a fixed sample. It predates
    V2 and behaves exactly as it did, now that the keyword no longer blocks it."""
    t = type_of_def(
        "def t := variance(v)\n",
        "const n : PositiveNatural = 3\nparam v : Vector[Real, n]\n",
    )
    assert t == ScalarType("NonNegativeReal")


def test_a_fixed_aggregate_cannot_be_conditioned():
    assert "HML-T483" in codes(
        "def t := variance(v | X)\n",
        RVS + "const n : PositiveNatural = 3\nparam v : Vector[Real, n]\n",
    )


# ===========================================================================
# SETS
# ===========================================================================


def test_membership_parses_to_its_own_node():
    e = first_expr("require a in A\n", "param a : Real\nparam A : Set[Real]\n")
    assert isinstance(e, MembershipExpr)


def test_membership_requires_a_set_on_the_right():
    assert "HML-T486" in codes(
        "require a in b\n", "param a : Real\nparam b : Real\n"
    )


def test_membership_checks_the_element_type():
    assert "HML-T487" in codes(
        "require b in A\n", "param b : Bool\nparam A : Set[Real]\n"
    )


def test_comprehension_has_a_set_type():
    assert type_of_def("def t := {x : Real | x > 0.0}\n") == SetType(ScalarType("Real"))


def test_a_comprehension_needs_a_proposition():
    assert "HML-T488" in codes("def t := {x : Real | x + 1.0}\n")


def test_a_comprehension_may_not_be_selected_by_an_event():
    """The set it would define is itself random, and v2 has no random-set type."""
    assert "HML-T488" in codes("def t := {x : Real | X > x}\n", RVS)


def test_a_comprehension_binder_needs_an_explicit_type():
    assert "HML-P262" in codes("def t := {x | x > 0.0}\n")


def test_sets_compose_with_quantifiers_and_constraints_and_continuity():
    compiled(
        "require forall x : Real . x in A => x in B\n"
        "require a in {u : Real | u > 0.0}\n"
        "require continuous(f, on := {u : Real | u > 0.0})\n",
        "param a : Real\nparam A : Set[Real]\nparam B : Set[Real]\n"
        "param f : Function[Real -> Real]\n",
    )


def test_membership_of_a_random_variable_is_an_event():
    assert "HML-T480" in codes("require X in A\n", RVS + "param A : Set[Real]\n")


def test_membership_does_not_chain():
    assert "HML-P230" in codes(
        "require a in A in B\n",
        "param a : Real\nparam A : Set[Real]\nparam B : Set[Real]\n",
    )


def test_continuity_requires_a_function_and_a_set():
    assert "HML-T492" in codes(
        "require continuous(a, on := A)\n", "param a : Real\nparam A : Set[Real]\n"
    )
    assert "HML-T493" in codes(
        "require continuous(f, on := a)\n",
        "param f : Function[Real -> Real]\nparam a : Real\n",
    )


def test_continuity_domain_must_lie_inside_the_function_domain():
    assert "HML-T494" in codes(
        "require continuous(f, on := A)\n",
        "param f : Function[Natural -> Real]\nparam A : Set[Real]\n",
    )


def test_continuity_requires_the_on_role():
    assert "HML-P266" in codes(
        "require continuous(f, A)\n",
        "param f : Function[Real -> Real]\nparam A : Set[Real]\n",
    )


# ===========================================================================
# ANALYSIS
# ===========================================================================


def test_the_analysis_forms_parse_to_their_own_nodes():
    assert isinstance(first_expr("def t := limit(1.0 / x, x : PositiveReal -> 1.0)\n"),
                      LimitExpr)
    assert isinstance(first_expr("def t := derivative(x ^ 2.0, x : Real)\n"),
                      DerivativeExpr)
    assert isinstance(
        first_expr("def t := integral(x ^ 2.0, x : Real, 0.0, 1.0)\n"), IntegralExpr
    )
    assert isinstance(
        first_expr(
            "def t := continuous(f, on := A)\n",
            "param f : Function[Real -> Real]\nparam A : Set[Real]\n",
        ),
        ContinuityExpr,
    )


def test_a_derivative_divides_the_dimension():
    t = type_of_def(
        "def t := derivative(s, u : Quantity[Time])\n", "param s : Quantity[Length]\n"
    )
    assert t.dimension.render() == "Length / Time"
    assert "HML-T403" in codes(
        "def t : Quantity[Length] := derivative(s, u : Quantity[Time])\n",
        "param s : Quantity[Length]\n",
    )


def test_an_integral_multiplies_the_dimension():
    t = type_of_def(
        "def t := integral(v, u : Quantity[Time], t0, t1)\n",
        "param v : Quantity[Length / Time]\n"
        "param t0 : Quantity[Time]\nparam t1 : Quantity[Time]\n",
    )
    assert t.dimension.render() == "Length"


def test_the_integral_bounds_must_inhabit_the_binder_type():
    assert "HML-T489" in codes(
        "def t := integral(v, u : Quantity[Time], 0.0, 1.0)\n",
        "param v : Quantity[Length / Time]\n",
    )


def test_the_limit_point_must_inhabit_the_binder_type():
    assert "HML-T489" in codes("def t := limit(1.0 / x, x : PositiveReal -> b)\n",
                               "param b : Bool\n")


def test_a_limit_lands_in_the_closure_of_the_body_type():
    """Every value of 1.0 / x here is positive and the limit need not be. Returning the
    body's own type would let a construction that provably escapes an open set keep the
    refinement that says it cannot."""
    assert type_of_def("def t := limit(1.0 / x, x : PositiveReal -> 1.0)\n") == (
        ScalarType("NonNegativeReal")
    )
    assert "HML-T403" in codes(
        "def t : PositiveReal := limit(1.0 / x, x : PositiveReal -> 1.0)\n"
    )


def test_a_limit_of_a_closed_interval_kind_keeps_its_kind():
    assert type_of_def(
        "def t := limit(p, x : Real -> 1.0)\n", "param p : Probability\n"
    ) == ScalarType("Probability")


def test_an_analysis_form_needs_a_dimensioned_body():
    assert "HML-T491" in codes(
        "def t := derivative(b, u : Real)\n", "param b : Bool\n"
    )


def test_analysis_binders_require_an_explicit_type():
    assert "HML-P262" in codes("def t := derivative(x ^ 2.0, x)\n")


def test_a_limit_needs_an_arrow():
    assert "HML-P265" in codes("def t := limit(1.0 / x, x : PositiveReal)\n")


# ===========================================================================
# CAUSAL
# ===========================================================================


def test_the_three_relations_are_propositions_over_random_variables():
    for relation in ("associated", "correlated", "causes"):
        assert isinstance(
            type_of_def(f"def t := {relation}(X, Y)\n", RVS), PropositionType
        ), relation
        assert "HML-T495" in codes(
            f"require {relation}(a, b)\n", "param a : Real\nparam b : Real\n"
        ), relation


def test_the_relations_parse_to_distinct_relation_names():
    for relation in ("associated", "correlated", "causes"):
        e = first_expr(f"def t := {relation}(X, Y)\n", RVS)
        assert isinstance(e, RelationExpr)
        assert e.relation == relation


def test_the_symmetry_table_is_what_the_nodes_report():
    assert SYMMETRIC_RELATIONS == {"associated", "correlated"}
    assert first_expr("def t := correlated(X, Y)\n", RVS).symmetric
    assert not first_expr("def t := causes(X, Y)\n", RVS).symmetric


def test_a_relation_needs_two_operands():
    assert "HML-P263" in codes("def t := causes(X)\n", RVS)


def test_implication_is_untouched_and_stays_a_connective():
    """`implies(P, Q)` is deliberately NOT added: `=>` and the `implies` keyword already
    denote it, and a third spelling of one object would be two canonical forms waiting
    to disagree."""
    a = content_hash(compiled("require p > 0.5 => q > 0.5\n", _PQ).module)
    b = content_hash(compiled("require p > 0.5 implies q > 0.5\n", _PQ).module)
    assert a == b


_PQ = "param p : Probability\nparam q : Probability\n"


# ===========================================================================
# CANONICAL IDENTITY -- the claims the mission asks to be made testable
# ===========================================================================


def h(body: str, prelude: str = RVS) -> str:
    return content_hash(compiled(body, prelude).module)


def test_correlation_and_causation_do_not_hash_equal():
    assert h("require correlated(X, Y)\n") != h("require causes(X, Y)\n")
    assert h("require associated(X, Y)\n") != h("require correlated(X, Y)\n")
    assert h("require associated(X, Y)\n") != h("require causes(X, Y)\n")


def test_causation_is_directed():
    assert h("require causes(X, Y)\n") != h("require causes(Y, X)\n")


def test_correlation_and_association_are_symmetric():
    assert h("require correlated(X, Y)\n") == h("require correlated(Y, X)\n")
    assert h("require associated(X, Y)\n") == h("require associated(Y, X)\n")


def test_independence_is_symmetric_in_both_lists():
    assert h("require independent(X, Y)\n") == h("require independent(Y, X)\n")
    assert h("require independent(X, Y | Y, Z)\n") == h(
        "require independent(Y, X | Z, Y)\n"
    )


def test_conditioning_changes_identity():
    assert h("require independent(X, Y)\n") != h("require independent(X, Y | Z)\n")
    assert h("def t := expectation(X)\n") != h("def t := expectation(X | Y)\n")


def test_a_conditioning_set_is_a_set():
    assert h("def t := expectation(X | Y, Z)\n") == h("def t := expectation(X | Z, Y)\n")


def test_a_joint_law_is_ordered():
    """Unlike independence. `Product[T1, T2]` is ordered, so the components are too."""
    assert h("def t := joint(X, Y)\n") != h("def t := joint(Y, X)\n")


def test_expectation_and_variance_are_different_operators():
    assert h("def t := expectation(X)\n") != h("def t := variance(X)\n")


def test_the_analysis_forms_are_distinguished_from_each_other():
    a = h("def t := integral(x ^ 2.0, x : Real, 0.0, 1.0)\n", "")
    b = h("def t := derivative(x ^ 2.0, x : Real)\n", "")
    c = h("def t := limit(x ^ 2.0, x : Real -> 1.0)\n", "")
    assert len({a, b, c}) == 3


def test_the_bounds_and_the_point_are_part_of_identity():
    assert h("def t := integral(x, x : Real, 0.0, 1.0)\n", "") != h(
        "def t := integral(x, x : Real, 0.0, 2.0)\n", ""
    )
    assert h("def t := limit(x, x : Real -> 1.0)\n", "") != h(
        "def t := limit(x, x : Real -> 2.0)\n", ""
    )


# -- alpha equivalence for the new binders ----------------------------------


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("{x : Real | x > 0.0}", "{u : Real | u > 0.0}"),
        ("limit(1.0 / x, x : PositiveReal -> 1.0)",
         "limit(1.0 / u, u : PositiveReal -> 1.0)"),
        ("derivative(x ^ 2.0, x : Real)", "derivative(u ^ 2.0, u : Real)"),
        ("integral(x ^ 2.0, x : Real, 0.0, 1.0)",
         "integral(u ^ 2.0, u : Real, 0.0, 1.0)"),
    ],
)
def test_the_new_binders_are_alpha_equivalent(a: str, b: str):
    """v0 success criterion 6 must hold for every binder, not only for quantifiers.
    It holds here because these forms go through the SAME resolver machinery."""
    assert h(f"def t := {a}\n", "") == h(f"def t := {b}\n", "")


def test_a_binder_is_scoped_to_its_own_body():
    assert "HML-N301" in codes("def t := {x : Real | x > 0.0}\ndef u := x\n")


def test_a_limit_point_is_outside_the_binder():
    """`limit(1.0 / x, x : Real -> x)` would otherwise bind the point to the variable
    being taken to it, which denotes nothing."""
    assert "HML-N301" in codes("def t := limit(1.0 / x, x : PositiveReal -> x)\n")


def test_integral_bounds_are_outside_the_binder():
    assert "HML-N301" in codes("def t := integral(x, x : Real, x, 1.0)\n")


def test_the_new_binders_reject_shadowing_like_every_other_binder():
    assert "HML-N302" in codes("def t := {x : Real | x > 0.0}\n", "param x : Real\n")


def test_a_definition_cycle_through_a_new_form_is_detected():
    """`_refs_in` must descend into every new node or a cycle running through an
    integrand would be invisible and the definition unfoldable."""
    assert "HML-S606" in codes(
        "def t := integral(u, x : Real, 0.0, 1.0)\ndef u := t + 1.0\n"
    )


# ===========================================================================
# ROUND TRIP
# ===========================================================================

ROUND_TRIP_CASES = [
    ("def t := expectation(X)\n", RVS),
    ("def t := expectation(X | Y, Z)\n", RVS),
    ("def t := variance(X)\n", RVS),
    ("def t := probability(X > 0.0)\n", RVS),
    ("def t := probability(X > 0.0 | Y > 0.0)\n", RVS),
    ("def t := joint(X, Y)\n", RVS),
    ("require independent(X, Y)\n", RVS),
    ("require independent(X, Y | Z)\n", RVS),
    ("require correlated(X, Y)\n", RVS),
    ("require causes(X, Y)\n", RVS),
    ("require associated(X, Y)\n", RVS),
    ("require a in A\n", "param a : Real\nparam A : Set[Real]\n"),
    ("require a + 1.0 in A\n", "param a : Real\nparam A : Set[Real]\n"),
    ("require a in A and a in B\n",
     "param a : Real\nparam A : Set[Real]\nparam B : Set[Real]\n"),
    ("def t := {x : Real | x > 0.0}\n", ""),
    ("require a in {x : Real | x > 0.0}\n", "param a : Real\n"),
    ("def t := limit(1.0 / x, x : PositiveReal -> 1.0)\n", ""),
    ("def t := derivative(x ^ 2.0, x : Real)\n", ""),
    ("def t := integral(x ^ 2.0, x : Real, 0.0, 1.0)\n", ""),
    ("require continuous(f, on := A)\n",
     "param f : Function[Real -> Real]\nparam A : Set[Real]\n"),
    ("require continuous(f, on := {x : Real | x > 0.0})\n",
     "param f : Function[Real -> Real]\n"),
]


@pytest.mark.parametrize(("body", "prelude"), ROUND_TRIP_CASES)
def test_render_reparse_preserves_the_canonical_form(body: str, prelude: str):
    first = compiled(body, prelude)
    rendered = render_module(first.module)
    second = compile_source(rendered)
    assert second.ok(), (
        "the rendered form did not re-parse:\n"
        + second.diagnostics.render()
        + "\n--- rendered ---\n"
        + rendered
    )
    assert content_hash(first.module) == content_hash(second.module), rendered


@pytest.mark.parametrize(("body", "prelude"), ROUND_TRIP_CASES)
def test_rendering_is_idempotent(body: str, prelude: str):
    # `compiled` prepends its own `module M` header, so the second pass has to go
    # through `compile_source` directly -- the rendered text already carries one.
    once = render_module(compiled(body, prelude).module)
    again = compile_source(once)
    assert again.ok(), "\n" + again.diagnostics.render()
    assert render_module(again.module) == once


# ===========================================================================
# EXHAUSTIVENESS GUARDS
# ===========================================================================
#
# Adding an Expr subclass without a canonical branch, a renderer or a graph child is
# silent in every case. These two tests are what make it loud.

#: One instance of every ``Expr`` subclass, built from real source so the nodes carry
#: resolved symbols and types. A new expression form makes ``test_every_expression_node
#: _is_covered`` fail until it is added here, which is the point.
def _one_of_each() -> dict[str, Expr]:
    from hamiltonian_lang.ast.nodes import walk

    src = (
        "module M\n"
        + RVS
        + "param a : Real\n"
        "param w : PositiveReal\n"
        "param A : Set[Real]\n"
        "param f : Function[Real -> Real]\n"
        "const n : PositiveNatural = 3\n"
        "param v : Vector[Real, n]\n"
        "param d : Quantity[Length]\n"
        "def e1 := expectation(X | Y)\n"
        "def e2 := variance(X)\n"
        "def e3 := joint(X, Y)\n"
        "def e4 := probability(X > 0.0 | Y > 0.0)\n"
        "def e5 := {x : Real | x > 0.0}\n"
        "def e6 := limit(1.0 / x, x : PositiveReal -> 1.0)\n"
        "def e7 := derivative(x ^ 2.0, x : Real)\n"
        "def e8 := integral(x ^ 2.0, x : Real, 0.0, 1.0)\n"
        "def e9 := -a + log(w) * 2.0 + v[1]\n"
        "require independent(X, Y | Z)\n"
        "require causes(X, Y)\n"
        "require a in A\n"
        "require continuous(f, on := A)\n"
        "require forall x : Real . x > 0.0 or not (x < 0.0)\n"
        "law X ~ Normal(location := a, scale := 1.0)\n"
    )
    r = compile_source(src)
    assert r.ok(), "\n" + r.diagnostics.render()
    found: dict[str, Expr] = {}
    for node in walk(r.module):
        if isinstance(node, Expr):
            found.setdefault(type(node).__name__, node)
    return found


def _holds_expr(value: object) -> bool:
    """Whether a field carries a sub-expression, directly or through a role wrapper.

    ``DistExpr.args`` is a list of ``Arg``, not of ``Expr``, so a naive isinstance test
    would report the one node in the language whose children are wrapped as childless.
    """
    if isinstance(value, Expr):
        return True
    if isinstance(value, list):
        return any(_holds_expr(item) for item in value)
    return isinstance(getattr(value, "value", None), Expr)


def _all_expr_subclasses() -> set[str]:
    """Every ``Expr`` subclass **defined by the AST contract**.

    Scoped to ``hamiltonian_lang.ast.nodes`` on purpose. Test modules define their own
    throwaway ``Expr`` subclasses -- ``tests/syntax_acquisition/test_unsupported.py``
    has an ``_InventedExpr`` whose entire job is to be a node no surface knows about --
    and those are not part of the language. Without the filter this guard would pass or
    fail depending on which other test module had been imported first.
    """
    seen: set[str] = set()
    stack = [Expr]
    while stack:
        cls = stack.pop()
        for sub in cls.__subclasses__():
            if sub.__module__ == Expr.__module__:
                seen.add(sub.__name__)
            stack.append(sub)
    return seen


def test_the_probe_module_instantiates_every_expression_node():
    missing = _all_expr_subclasses() - set(_one_of_each())
    assert not missing, (
        f"no probe covers {sorted(missing)}. Add it to _one_of_each so the two guards "
        f"below actually see it."
    )


def test_every_expression_node_is_covered_by_the_canonical_form_and_the_renderer():
    """Three silent failures at once.

    * a missing canonical branch falls through to ``{"kind": "<ClassName>"}``, giving
      EVERY instance of a form the same identity -- so the reasoning kernel would treat
      one integral as a proof of another;
    * a missing ``render_expr`` branch emits ``<ClassName>``, which re-parses as a
      comparison against undeclared names;
    * a missing ``graph._children`` entry drops the dependency edges beneath the node.
    """
    from hamiltonian_lang.backends.canonical import _expr
    from hamiltonian_lang.graph import _children

    for name, node in sorted(_one_of_each().items()):
        doc = _expr(node)
        assert set(doc) != {"kind"}, (
            f"{name} has no branch in backends/canonical.py::_expr, so every instance "
            f"of it shares one canonical identity"
        )
        assert json.dumps(doc)  # serialisable

        text = render_expr(node)
        assert text != f"<{name}>", (
            f"{name} has no branch in backends/hml.py::render_expr, so it does not "
            f"round-trip"
        )

        # A node with sub-expressions must expose them, or the semantic graph loses
        # the dependency edges under it. Leaves legitimately expose none.
        children = tuple(_children(node))
        has_sub = any(
            _holds_expr(value)
            for key, value in vars(node).items()
            if key not in ("span", "type_")
        )
        assert bool(children) == has_sub, (
            f"{name} has sub-expressions that graph._children does not return, so the "
            f"semantic graph would omit their dependency edges"
        )


def test_the_binding_expression_table_is_complete():
    """Every node carrying a ``symbol_id`` binder must be listed, because that table is
    what a reader consults to know where alpha-equivalence has to hold."""
    binders = {
        name
        for name, node in _one_of_each().items()
        if "symbol_id" in vars(node) and "var" in vars(node)
    }
    assert binders == {c.__name__ for c in BINDING_EXPRESSIONS}


def test_every_new_binder_carries_a_resolved_symbol_id():
    for name, node in _one_of_each().items():
        if name in {c.__name__ for c in BINDING_EXPRESSIONS}:
            assert node.symbol_id is not None, name


def test_no_expression_survives_untyped():
    """HML-T450 exists because an untyped expression compares equal to anything. The
    new forms must not reintroduce one."""
    from hamiltonian_lang.types import UnknownType

    for name, node in _one_of_each().items():
        assert not isinstance(node.type_, UnknownType), name


def test_set_comprehension_is_a_binder_and_membership_is_not():
    assert SetComprehension in BINDING_EXPRESSIONS
    assert MembershipExpr not in BINDING_EXPRESSIONS
    assert JointExpr not in BINDING_EXPRESSIONS
