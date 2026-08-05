"""Evaluator validation for EVAL_SPEC_v1.0.

A scorer that cannot fail is not a scorer. For **every** facet the comparator reports,
this file demonstrates a mutation that must lower it and a control that must not — so a
facet silently stuck at full marks, or silently stuck at zero, is caught here rather than
appearing in a result as a difference between arms.

Also pins the five behaviours the directive names explicitly:
binder-renaming invariance · role-swap detection · quantifier-order detection ·
dimension comparison · omitted-structure detection.

**A gap this file makes explicit rather than hiding:** ``SemanticFacts`` carries a
``prohibited_assumptions`` field which the comparator does **not** score. Detecting a
hidden assumption in free prose is not deterministically decidable, and no facet claims
to do it. `test_prohibited_assumptions_are_not_scored` pins that so the report cannot
claim a capability the code lacks.
"""

from __future__ import annotations

import pytest
from evaluation.corpus.cso import AnswerSpec, CanonicalSemanticObject, SemanticFacts
from evaluation.semantic_equiv import classify, compare_semantics

BASE_HML = """module M

param mu : Real
param sigma : PositiveReal
rv X : RandomVariable[Real]

law X | mu ~ Normal(location := mu, scale := sigma)
"""


def _cso(**overrides) -> CanonicalSemanticObject:
    facts = SemanticFacts(
        entities={"mu": "Real", "sigma": "PositiveReal", "X": "RandomVariable[Real]"},
        declaration_kinds={"mu": "param", "sigma": "param", "X": "rv"},
        law_families={"X": "Normal"},
        laws={"X": {"location": "mu", "scale": "sigma"}},
        conditioning={"X": ["mu"]},
    )
    for k, v in overrides.items():
        setattr(facts, k, v)
    return CanonicalSemanticObject(
        id="probe", domain="probability", difficulty="easy",
        prose="probe", question="probe?",
        answer=AnswerSpec("numeric", 1.0), semantics=facts, reference_hml=BASE_HML,
    )


def _facet(cso, hml, name) -> tuple[int, int]:
    return getattr(compare_semantics(cso, hml), name)


# ---------------------------------------------------------------------------
# Control: the reference must score perfectly, or every failure below is vacuous
# ---------------------------------------------------------------------------


def test_control_reference_scores_one():
    cmp = compare_semantics(_cso(), BASE_HML)
    assert cmp.score() == 1.0, cmp.to_dict()
    assert cmp.exact()


# ---------------------------------------------------------------------------
# Every scored facet: one mutation that lowers it, control already above
# ---------------------------------------------------------------------------


def test_facet_entities_can_fail():
    """Dropping a declaration must reduce the entity count."""
    mutated = BASE_HML.replace("param sigma : PositiveReal\n", "").replace(
        "scale := sigma", "scale := mu"
    )
    m, e = _facet(_cso(), mutated, "entities")
    assert (m, e) == (2, 3), (m, e)


def test_facet_types_can_fail():
    mutated = BASE_HML.replace("param sigma : PositiveReal", "param sigma : Real")
    m, e = _facet(_cso(), mutated, "types")
    assert m < e, (m, e)


def test_facet_declaration_kinds_can_fail():
    """`param` and `obs` are different epistemic claims, not spelling variants."""
    mutated = BASE_HML.replace("param mu : Real", "obs mu : Real = 0")
    m, e = _facet(_cso(), mutated, "declaration_kinds")
    assert m < e, (m, e)


def test_facet_law_families_can_fail():
    mutated = BASE_HML.replace("Normal(location := mu, scale := sigma)",
                               "Cauchy(location := mu, scale := sigma)")
    m, e = _facet(_cso(), mutated, "law_families")
    assert (m, e) == (0, 1)


def test_facet_roles_can_fail():
    """The headline case: a role swap must be detected."""
    mutated = BASE_HML.replace("param sigma : PositiveReal", "param sigma : Real").replace(
        "location := mu, scale := sigma", "location := sigma, scale := mu"
    )
    m, e = _facet(_cso(), mutated, "roles")
    assert m < e, (m, e)


def test_facet_conditioning_can_fail():
    mutated = BASE_HML.replace("law X | mu ~", "law X ~")
    m, e = _facet(_cso(), mutated, "conditioning")
    assert (m, e) == (0, 1)


def test_facet_quantifier_order_can_fail_and_pass():
    cso = _cso(entities={}, declaration_kinds={}, law_families={}, laws={},
               conditioning={}, quantifier_order=["forall x", "exists y"])
    good = "module Q\n\nprove forall x : Real . exists y : Real . y > x\n"
    bad = "module Q\n\nprove exists y : Real . forall x : Real . y > x\n"
    assert _facet(cso, good, "quantifier_order") == (2, 2)
    assert _facet(cso, bad, "quantifier_order")[0] < 2


def test_facet_objective_can_fail_and_pass():
    cso = _cso(entities={"x": "Real"}, declaration_kinds={"x": "var"},
               law_families={}, laws={}, conditioning={}, objective="minimise x^2")
    good = "module O\n\nvar x : Real\n\nminimise x ^ 2\n"
    bad = "module O\n\nvar x : Real\n\nmaximise x ^ 2\n"
    assert _facet(cso, good, "objective") == (1, 1)
    assert _facet(cso, bad, "objective") == (0, 1)


def test_facet_dimensions_can_fail_and_pass():
    cso = _cso(entities={}, declaration_kinds={}, law_families={}, laws={},
               conditioning={}, dimensions={"result": "Mass * Length^2 / Time^2"})
    good = ("module D\n\nparam q : Quantity[Mass * Length^2 / Time^2]\n\n"
            "check dimension q = Mass * Length^2 / Time^2\n")
    bad = ("module D\n\nparam q : Quantity[Mass * Length^3 / Time^2]\n\n"
           "check dimension q = Mass * Length^3 / Time^2\n")
    assert _facet(cso, good, "dimensions") == (1, 1)
    assert _facet(cso, bad, "dimensions") == (0, 1)


def test_every_scored_facet_appears_in_this_file():
    """If a facet is added to the comparator without a mutation test, fail loudly."""
    cmp = compare_semantics(_cso(), BASE_HML)
    scored = {name for name, _ in cmp._facets()}
    covered = {
        "entities", "types", "declaration_kinds", "law_families", "roles",
        "conditioning", "quantifier_order", "objective", "dimensions",
    }
    assert scored == covered, f"untested facets: {scored - covered}"


# ---------------------------------------------------------------------------
# The five behaviours the directive names
# ---------------------------------------------------------------------------


def test_binder_renaming_invariance():
    """Renaming module-level binders must not move the score at all."""
    renamed = (
        BASE_HML.replace("mu", "centre").replace("sigma", "spread").replace("X", "Y")
    )
    assert compare_semantics(_cso(), renamed).score() == 1.0


def test_role_swap_is_detected_even_when_both_fillers_are_declared():
    swapped = BASE_HML.replace("param sigma : PositiveReal", "param sigma : Real").replace(
        "location := mu, scale := sigma", "location := sigma, scale := mu"
    )
    assert compare_semantics(_cso(), swapped).score() < 1.0


def test_quantifier_order_is_detected():
    cso = _cso(entities={}, declaration_kinds={}, law_families={}, laws={},
               conditioning={}, quantifier_order=["forall x", "exists y"])
    a = compare_semantics(cso, "module Q\n\nprove forall x : Real . exists y : Real . y > x\n")
    b = compare_semantics(cso, "module Q\n\nprove exists y : Real . forall x : Real . y > x\n")
    assert a.score() == 1.0 and b.score() < 1.0


@pytest.mark.parametrize(
    "a,b,equal",
    [
        ("Mass * Length^2 / Time^2", "Length^2 * Mass / Time^2", True),
        ("Mass / (Length * Time^2)", "Mass / Length / Time^2", True),
        ("Mass * Length^2 / Time^2", "Mass * Length^3 / Time^2", False),
        ("1 / Time", "Time", False),
    ],
)
def test_dimension_comparison(a, b, equal):
    from evaluation.corpus.cso import parse_dimension

    assert (parse_dimension(a) == parse_dimension(b)) is equal


def test_omitted_structure_is_detected():
    """An encoding that simply says less must score lower. Otherwise 'encode nothing'
    would be a winning strategy."""
    minimal = "module M\n\nparam mu : Real\n"
    assert compare_semantics(_cso(), minimal).score() < 0.5


def test_prohibited_assumptions_are_not_scored():
    """Recorded so the report cannot claim a capability the code lacks.

    Detecting an unstated assumption in free prose is not deterministically decidable.
    The field exists for failure *classification* by a human reader; no facet scores it,
    and adding one here without an implementation would be a false claim.
    """
    with_field = _cso(prohibited_assumptions=["something never checked"])
    without = _cso(prohibited_assumptions=[])
    assert compare_semantics(with_field, BASE_HML).score() == \
        compare_semantics(without, BASE_HML).score() == 1.0


# ---------------------------------------------------------------------------
# Answer checking and taxonomy
# ---------------------------------------------------------------------------


def test_answer_checker_is_not_fooled_by_the_reasoning_trace():
    """A model that discusses the wrong value before giving the right one, or vice
    versa, must be scored on the marked answer only."""
    from evaluation.corpus.cso import check_answer

    spec = AnswerSpec("numeric", 12.0)
    ok, _ = check_answer(spec, "I first thought 5, then 9. <ANSWER>12</ANSWER>")
    assert ok
    bad, _ = check_answer(spec, "The answer is clearly 12. <ANSWER>5</ANSWER>")
    assert not bad


def test_taxonomy_assigns_exactly_one_bucket():
    cmp_ok = compare_semantics(_cso(), BASE_HML)
    assert classify(answer_correct=True, formal_arm=True, encoding_present=True,
                    comparison=cmp_ok, completion_ok=True) == "correct_solution"
    assert classify(answer_correct=False, formal_arm=False, encoding_present=False,
                    comparison=None, completion_ok=True) == "correct_reasoning_wrong_answer"
    assert classify(answer_correct=False, formal_arm=True, encoding_present=False,
                    comparison=None, completion_ok=True) == "no_encoding_produced"
    assert classify(answer_correct=False, formal_arm=True, encoding_present=True,
                    comparison=cmp_ok, completion_ok=True) == "correct_reasoning_wrong_answer"
    bad_syntax = compare_semantics(_cso(), "module M\n\nlaw X ~ Normal(mu, sigma)\n")
    assert classify(answer_correct=False, formal_arm=True, encoding_present=True,
                    comparison=bad_syntax, completion_ok=True) == "syntax_failure"
