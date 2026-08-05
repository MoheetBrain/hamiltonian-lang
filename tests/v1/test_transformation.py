"""V1 layer 2/3 — transformation and inference edges.

The load-bearing tests here are the ones that keep ``yields``, ``implies`` and
``is equivalent to`` apart, and the ones that prove a step's side conditions survive it.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.v1.transformation import (
    CONVERSE_OPERATIONS,
    EDGE_DOMAIN,
    INFERENCE_RULES,
    OPERATIONS,
    PROHIBITED_EDGE_COERCIONS,
    ChainReport,
    EdgeKind,
    EdgeKindError,
    ObligationKind,
    Operation,
    Relatum,
    TransformationChain,
    WarrantKind,
    chain_of,
    definition,
    edge_kind_coercion_allowed,
    expression,
    implications_of_equivalence,
    proposition,
    rule,
    step,
    theorem,
)

# ---------------------------------------------------------------------------
# yields is not implies is not equivalent
# ---------------------------------------------------------------------------


def test_yields_may_not_be_used_where_implies_is_required():
    yields = step("s1", source="e1", operation=Operation.YIELD, target="e2")
    assert yields.kind is EdgeKind.ALGEBRAIC

    ok, reason = yields.may_be_used_as(EdgeKind.LOGICAL_IMPLICATION)
    assert ok is False
    assert "yields is not implies" in reason

    with pytest.raises(EdgeKindError):
        yields.require_kind(EdgeKind.LOGICAL_IMPLICATION)


def test_implies_may_not_be_used_where_yields_is_required():
    implies = step(
        "s1",
        source="p1",
        operation=Operation.IMPLY,
        target="p2",
        justification=rule("universal_instantiation"),
    )
    assert implies.kind is EdgeKind.LOGICAL_IMPLICATION

    ok, reason = implies.may_be_used_as(EdgeKind.ALGEBRAIC)
    assert ok is False
    assert "implies is not yields" in reason

    with pytest.raises(EdgeKindError):
        implies.require_kind(EdgeKind.ALGEBRAIC)


def test_equivalence_is_neither_yields_nor_implies():
    equiv = step("s1", source="p1", operation=Operation.EQUIVALENT, target="p2")
    assert equiv.kind is EdgeKind.EQUIVALENCE
    assert equiv.may_be_used_as(EdgeKind.ALGEBRAIC)[0] is False
    assert equiv.may_be_used_as(EdgeKind.LOGICAL_IMPLICATION)[0] is False

    implies = step(
        "s2",
        source="p1",
        operation=Operation.IMPLY,
        target="p2",
        justification=rule("universal_instantiation"),
    )
    ok, reason = implies.may_be_used_as(EdgeKind.EQUIVALENCE)
    assert ok is False
    assert "converse" in reason


def test_no_coercion_between_any_two_distinct_edge_kinds():
    """Default deny. A permissive default is how a rewrite acquires the word 'implies'."""
    for source in EdgeKind:
        for target in EdgeKind:
            ok, reason = edge_kind_coercion_allowed(source, target)
            assert ok is (source == target)
            if source != target:
                assert reason


def test_every_prohibited_pair_is_actually_prohibited():
    for (source, target), documented in PROHIBITED_EDGE_COERCIONS.items():
        ok, reason = edge_kind_coercion_allowed(source, target)
        assert ok is False
        assert reason == documented


def test_equivalence_gives_directed_implications_only_by_explicit_construction():
    equiv = step("s1", source="p1", operation=Operation.EQUIVALENT, target="p2")
    forward, backward = implications_of_equivalence(equiv)

    assert forward.kind is EdgeKind.LOGICAL_IMPLICATION
    assert backward.kind is EdgeKind.LOGICAL_IMPLICATION
    assert forward.entailment() == (("p1",), "p2")
    assert backward.entailment() == (("p2",), "p1")

    # The explicit construction does not open a coercion path.
    assert edge_kind_coercion_allowed(
        EdgeKind.EQUIVALENCE, EdgeKind.LOGICAL_IMPLICATION
    )[0] is False

    with pytest.raises(EdgeKindError):
        implications_of_equivalence(
            step("s2", source="e1", operation=Operation.YIELD, target="e2")
        )


def test_an_algebraic_edge_asserts_no_entailment():
    yields = step("s1", source="e1", operation=Operation.YIELD, target="e2")
    assert yields.entailment() is None


def test_edge_kind_is_derived_from_the_operation_and_not_settable():
    for operation, spec in OPERATIONS.items():
        assert step("s", source="a", operation=operation, target="b").kind is spec.kind


# ---------------------------------------------------------------------------
# expressions and propositions are not interchangeable
# ---------------------------------------------------------------------------


def test_a_yields_edge_over_propositions_is_rejected():
    chain = chain_of(
        [proposition("p1", "x > 0"), proposition("p2", "x != 0")],
        [step("s1", source="p1", operation=Operation.YIELD, target="p2")],
    )
    report = chain.validate()
    assert not report.valid
    first = report.first_invalid
    assert first is not None and first.code == "HML-X606"
    assert "implies is not yields" in first.message


def test_an_implies_edge_over_expressions_is_rejected():
    chain = chain_of(
        [expression("e1", "2x + 1"), expression("e2", "7")],
        [
            step(
                "s1",
                source="e1",
                operation=Operation.IMPLY,
                target="e2",
                justification=rule("universal_instantiation"),
            )
        ],
    )
    report = chain.validate()
    assert not report.valid
    first = report.first_invalid
    assert first is not None and first.code == "HML-X606"
    assert "yields is not implies" in first.message


def test_edge_domains_cover_every_kind():
    assert set(EDGE_DOMAIN) == set(EdgeKind)
    assert EDGE_DOMAIN[EdgeKind.ALGEBRAIC] is Relatum.EXPRESSION
    assert EDGE_DOMAIN[EdgeKind.LOGICAL_IMPLICATION] is Relatum.PROPOSITION
    # definition expansion is the only kind that works in either domain
    assert EDGE_DOMAIN[EdgeKind.DEFINITION_EXPANSION] is None


def test_definition_expansion_infers_its_domain_from_the_source():
    chain = chain_of(
        [proposition("p1", "X is a martingale")],
        [
            step(
                "s1",
                source="p1",
                operation=Operation.EXPAND_DEFINITION,
                target="p2",
                justification=definition("martingale"),
            )
        ],
    )
    report = chain.validate()
    assert report.valid, report.render()
    assert chain.validate().obligations


# ---------------------------------------------------------------------------
# side conditions
# ---------------------------------------------------------------------------


def test_divide_through_by_a_possibly_zero_quantity_generates_an_obligation():
    edge = step(
        "s1",
        source="e1",
        operation=Operation.DIVIDE_THROUGH,
        target="e2",
        arguments={"by": "x - 1"},
    )
    conditions = [o.condition for o in edge.obligations()]
    assert "x - 1 != 0" in conditions
    assert all(o.kind is ObligationKind.SIDE_CONDITION for o in edge.obligations())


def test_the_divisor_obligation_survives_into_the_chain_report():
    chain = chain_of(
        [expression("e1", "a*x = a*y")],
        [
            step(
                "s1",
                source="e1",
                operation=Operation.DIVIDE_THROUGH,
                target="e2",
                arguments={"by": "a"},
            )
        ],
    )
    report = chain.validate()
    assert report.valid, report.render()
    # Structurally valid and still not proved: the obligation is open, not discharged.
    assert [o.condition for o in report.obligations] == ["a != 0"]
    assert "a != 0" in report.render()


def test_divide_through_without_a_named_divisor_is_invalid_and_still_records_the_gap():
    edge = step("s1", source="e1", operation=Operation.DIVIDE_THROUGH, target="e2")
    report = chain_of([expression("e1")], [edge]).validate()
    first = report.first_invalid
    assert first is not None and first.code == "HML-X601"
    # The obligation is still recorded, naming what is missing rather than vanishing.
    assert "<missing argument 'by'>" in report.obligations[0].condition


def test_take_log_requires_a_positive_argument():
    edge = step(
        "s1",
        source="e1",
        operation=Operation.TAKE_LOG,
        target="e2",
        arguments={"of": "1 - p"},
    )
    assert [o.condition for o in edge.obligations()] == ["1 - p > 0"]


def test_cancel_and_divide_both_require_a_non_zero_factor():
    cancel = step(
        "s1", source="e1", operation=Operation.CANCEL, target="e2",
        arguments={"factor": "(x - 1)"},
    )
    divide = step(
        "s2", source="e1", operation=Operation.DIVIDE, target="e3",
        arguments={"by": "sigma"},
    )
    assert [o.condition for o in cancel.obligations()] == ["(x - 1) != 0"]
    assert [o.condition for o in divide.obligations()] == ["sigma != 0"]


def test_differentiate_requires_differentiability():
    edge = step(
        "s1",
        source="f",
        operation=Operation.DIFFERENTIATE,
        target="df",
        arguments={"wrt": "theta"},
    )
    assert edge.obligations()[0].condition == (
        "f is differentiable with respect to theta on its domain"
    )


def test_integrate_and_limit_generate_their_own_conditions():
    integral = step(
        "s1", source="f", operation=Operation.INTEGRATE, target="F",
        arguments={"wrt": "x", "over": "[0, 1]"},
    )
    lim = step(
        "s2", source="g", operation=Operation.LIMIT, target="L",
        arguments={"variable": "n", "approaches": "infinity"},
    )
    assert "integrable" in integral.obligations()[0].condition
    assert "limit of g as n -> infinity exists" in lim.obligations()[0].condition


def test_apply_requires_the_argument_to_be_in_the_domain():
    edge = step(
        "s1", source="x", operation=Operation.APPLY, target="y",
        arguments={"fn": "sqrt"},
    )
    assert edge.obligations()[0].condition == "x is in domain(sqrt)"


def test_sqrt_both_sides_records_a_case_split_on_the_sign_branch():
    edge = step("s1", source="e1", operation=Operation.SQRT_BOTH_SIDES, target="e2")
    kinds = {o.kind for o in edge.obligations()}
    assert ObligationKind.CASE_SPLIT in kinds
    assert ObligationKind.SIDE_CONDITION in kinds


def test_simplify_must_name_the_identity_it_used():
    unnamed = step("s1", source="e1", operation=Operation.SIMPLIFY, target="e2")
    report = chain_of([expression("e1")], [unnamed]).validate()
    first = report.first_invalid
    assert first is not None and first.code == "HML-X602"

    named = step(
        "s1", source="e1", operation=Operation.SIMPLIFY, target="e2",
        justification=rule("pythagorean_identity"),
    )
    ok = chain_of([expression("e1")], [named]).validate()
    assert ok.valid, ok.render()
    assert "pythagorean_identity" in ok.obligations[0].condition


def test_apply_theorem_generates_one_obligation_per_hypothesis():
    edge = step(
        "s1",
        source=["p1"],
        operation=Operation.APPLY_THEOREM,
        target="p2",
        arguments={"hypotheses": ("f is continuous on [a, b]", "f(a)*f(b) < 0")},
        justification=theorem("intermediate_value"),
    )
    conditions = [o.condition for o in edge.obligations()]
    assert "intermediate_value requires: f is continuous on [a, b]" in conditions
    assert "intermediate_value requires: f(a)*f(b) < 0" in conditions
    assert sum(o.kind is ObligationKind.HYPOTHESIS for o in edge.obligations()) == 3


def test_equivalence_owes_an_obligation_in_each_direction():
    edge = step("s1", source="p1", operation=Operation.EQUIVALENT, target="p2")
    conditions = [o.condition for o in edge.obligations()]
    assert conditions == ["p1 implies p2", "p2 implies p1"]
    assert all(o.kind is ObligationKind.DIRECTION for o in edge.obligations())


def test_every_operation_renders_its_obligations_without_a_missing_key_crash():
    for operation in Operation:
        edge = step("s", source=["a", "b"], operation=operation, target="c")
        edge.obligations()
        edge.weakening()
        edge.render()


# ---------------------------------------------------------------------------
# weakenings
# ---------------------------------------------------------------------------


def test_square_both_sides_records_a_weakening_not_an_equivalence():
    edge = step("s1", source="e1", operation=Operation.SQUARE_BOTH_SIDES, target="e2")

    weakening = edge.weakening()
    assert weakening is not None
    assert weakening.reversible is False
    assert "not reversible" in weakening.lost
    assert "extraneous" in weakening.lost

    assert edge.reversible is False
    assert edge.kind is not EdgeKind.EQUIVALENCE
    assert edge.may_be_used_as(EdgeKind.EQUIVALENCE)[0] is False
    # It generates no directional obligations, because it asserts no equivalence.
    assert edge.obligations() == ()


def test_the_weakening_reaches_the_chain_report():
    report = chain_of(
        [expression("e1", "x = -2")],
        [step("s1", source="e1", operation=Operation.SQUARE_BOTH_SIDES, target="e2")],
    ).validate()
    assert report.valid
    assert len(report.weakenings) == 1
    assert "[weakened]" in report.render()


def test_take_expectation_is_a_weakening_too():
    edge = step(
        "s1", source="e1", operation=Operation.TAKE_EXPECTATION, target="e2",
        arguments={"under": "P"},
    )
    weakening = edge.weakening()
    assert weakening is not None
    assert "E[X] = E[Y] does not recover X = Y" in weakening.lost
    assert edge.reversible is False


def test_approximation_and_numerical_evaluation_are_weakenings():
    approx = step(
        "s1", source="e1", operation=Operation.APPROXIMATE, target="e2",
        arguments={"bound": "O(n^-1)"},
    )
    numeric = step(
        "s2", source="e2", operation=Operation.EVALUATE, target="e3",
        arguments={"precision": "1e-9"},
    )
    assert approx.kind is EdgeKind.APPROXIMATION
    assert numeric.kind is EdgeKind.NUMERICAL
    assert approx.weakening() is not None
    assert numeric.weakening() is not None
    assert approx.may_be_used_as(EdgeKind.ALGEBRAIC)[0] is False
    assert numeric.may_be_used_as(EdgeKind.ALGEBRAIC)[0] is False


def test_a_reversible_operation_reports_no_weakening():
    for operation in (Operation.EXPAND, Operation.COLLECT, Operation.FACTOR):
        edge = step("s", source="e1", operation=operation, target="e2")
        assert edge.weakening() is None
        assert edge.reversible is True


# ---------------------------------------------------------------------------
# inference structure
# ---------------------------------------------------------------------------


def test_modus_ponens_needs_two_premises():
    report = chain_of(
        [proposition("p1"), proposition("p2")],
        [
            step(
                "s1",
                source="p1",
                operation=Operation.IMPLY,
                target="p2",
                justification=rule("modus_ponens"),
            )
        ],
    ).validate()
    first = report.first_invalid
    assert first is not None and first.code == "HML-X604"
    assert "modus_ponens needs at least 2 premises" in first.message


def test_an_unknown_inference_rule_is_rejected():
    report = chain_of(
        [proposition("p1"), proposition("p2")],
        [
            step(
                "s1",
                source="p1",
                operation=Operation.IMPLY,
                target="p2",
                justification=rule("affirming_the_consequent"),
            )
        ],
    ).validate()
    first = report.first_invalid
    assert first is not None and first.code == "HML-X603"
    assert set(INFERENCE_RULES) >= {"modus_ponens", "contraposition", "induction"}


def test_an_uncited_implication_is_rejected():
    report = chain_of(
        [proposition("p1"), proposition("p2")],
        [step("s1", source="p1", operation=Operation.IMPLY, target="p2")],
    ).validate()
    first = report.first_invalid
    assert first is not None and first.code == "HML-X602"


def test_necessary_and_sufficient_are_converses_of_one_another():
    sufficient = step("s1", source="p1", operation=Operation.SUFFICIENT, target="p2")
    necessary = step("s2", source="p1", operation=Operation.NECESSARY, target="p2")

    assert sufficient.entailment() == (("p1",), "p2")
    assert necessary.entailment() == (("p2",), "p1")
    assert sufficient.entailment() != necessary.entailment()
    assert CONVERSE_OPERATIONS[Operation.NECESSARY] is Operation.SUFFICIENT
    assert CONVERSE_OPERATIONS[Operation.SUFFICIENT] is Operation.NECESSARY


def test_stating_a_converse_does_not_assert_it():
    converse = step("s1", source="p1", operation=Operation.CONVERSE, target="p2")
    assert converse.asserted is False
    assert converse.entailment() is None

    obligation = converse.obligations()[0]
    assert obligation.kind is ObligationKind.CONVERSE
    assert "neither established nor refuted" in obligation.condition

    report = chain_of([proposition("p1"), proposition("p2")], [converse]).validate()
    assert report.valid
    assert report.unasserted == ("s1",)


def test_a_counterexample_refutes_and_is_not_an_implication():
    edge = step(
        "s1",
        source="p1",
        operation=Operation.COUNTEREXAMPLE,
        target="p2",
        arguments={"witness": "x = 0"},
    )
    assert edge.kind is EdgeKind.REFUTATION
    assert edge.may_be_used_as(EdgeKind.LOGICAL_IMPLICATION)[0] is False
    assert edge.obligations()[0].condition == "x = 0 satisfies p1 and violates p2"


def test_statistical_inference_is_not_logical_implication():
    edge = step(
        "s1",
        source="p1",
        operation=Operation.INFER,
        target="p2",
        arguments={"from_data": "D", "procedure": "OLS"},
    )
    assert edge.kind is EdgeKind.STATISTICAL
    ok, reason = edge.may_be_used_as(EdgeKind.LOGICAL_IMPLICATION)
    assert ok is False
    assert "Evidence-justified" in reason
    assert edge.weakening() is not None


# ---------------------------------------------------------------------------
# chains
# ---------------------------------------------------------------------------


def _worked_chain() -> TransformationChain:
    """y = 2x + 1 under x = 3, then divide through, then square. A realistic derivation."""
    return chain_of(
        [expression("e1", "y = 2x + 1"), expression("e2", "x = 3")],
        [
            step(
                "s1",
                source=["e1", "e2"],
                operation=Operation.SUBSTITUTE,
                target="e3",
                assumptions=["x is real"],
            ),
            step("s2", source="e3", operation=Operation.EXPAND, target="e4"),
            step(
                "s3",
                source="e4",
                operation=Operation.DIVIDE_THROUGH,
                target="e5",
                arguments={"by": "y - 1"},
            ),
        ],
    )


def test_a_valid_chain_still_carries_undischarged_obligations():
    report = _worked_chain().validate()
    assert report.valid
    assert report.first_invalid is None
    assert [o.condition for o in report.obligations] == ["y - 1 != 0"]
    assert report.dependencies == ("x is real",)
    assert "NOT discharged" in report.render()


def test_an_invalid_chain_is_located_at_the_offending_edge():
    chain = chain_of(
        [expression("e1", "y = 2x + 1")],
        [
            step("s1", source="e1", operation=Operation.EXPAND, target="e2"),
            # e9 was never declared and is not produced by an earlier step
            step("s2", source="e9", operation=Operation.COLLECT, target="e3"),
            step("s3", source="e3", operation=Operation.FACTOR, target="e4"),
        ],
    )
    report = chain.validate()
    assert not report.valid
    offending = report.first_invalid
    assert offending is not None
    assert offending.index == 1
    assert offending.edge == "s2"
    assert offending.code == "HML-X605"
    assert "e9" in offending.message
    # only that edge is faulted; the steps either side are fine
    assert [e.edge for e in report.errors] == ["s2"]


def test_a_forward_reference_is_not_grounded():
    report = chain_of(
        [expression("e1")],
        [
            step("s1", source="e2", operation=Operation.EXPAND, target="e3"),
            step("s2", source="e1", operation=Operation.COLLECT, target="e2"),
        ],
    ).validate()
    offending = report.first_invalid
    assert offending is not None and offending.index == 0 and offending.edge == "s1"


def test_duplicate_step_names_are_rejected():
    report = chain_of(
        [expression("e1")],
        [
            step("s1", source="e1", operation=Operation.EXPAND, target="e2"),
            step("s1", source="e2", operation=Operation.COLLECT, target="e3"),
        ],
    ).validate()
    assert report.first_invalid is not None
    assert report.first_invalid.code == "HML-X608"


def test_require_refuses_the_wrong_edge_kind_by_name():
    chain = _worked_chain()
    assert chain.require("s1", EdgeKind.ALGEBRAIC) is None

    error = chain.require("s1", EdgeKind.LOGICAL_IMPLICATION)
    assert error is not None
    assert error.code == "HML-X609"
    assert "yields is not implies" in error.message

    missing = chain.require("nope", EdgeKind.ALGEBRAIC)
    assert missing is not None and missing.code == "HML-X610"


def test_obligations_can_be_traced_back_to_the_step_that_made_them():
    report = _worked_chain().validate()
    assert report.obligations_of("s3")
    assert report.obligations_of("s2") == ()


def test_an_empty_report_is_valid_and_says_nothing_was_discharged():
    report = ChainReport()
    assert report.valid
    assert report.first_invalid is None
    assert "NOT discharged" in report.render()


def test_chain_exposes_its_nodes_and_edges():
    chain = _worked_chain()
    assert set(chain.nodes) == {"e1", "e2"}
    assert [e.name for e in chain.edges] == ["s1", "s2", "s3"]
    assert chain.edge("s2") is not None
    assert chain.edge("absent") is None


def test_the_step_surface_form_round_trips_into_a_readable_rendering():
    edge = step(
        "s1",
        source=["e1", "e2"],
        operation=Operation.SUBSTITUTE,
        target="e3",
        assumptions=["x is real"],
        justification=rule("substitution"),
    )
    rendered = edge.render()
    assert "step s1: source := [e1, e2]" in rendered
    assert "operation := substitute" in rendered
    assert "target := e3" in rendered
    assert "assumptions := [x is real]" in rendered
    assert "justification := rule substitution" in rendered


def test_a_warrant_is_not_an_epistemic_justification():
    """Citing a rule is not the same as holding a proof; the types are separate."""
    from hamiltonian_lang.v1 import epistemic

    assert not hasattr(epistemic.Justification, "RULE")
    assert set(WarrantKind) & set(epistemic.Justification) == set()
