"""Regression tests for the ACQ0 task-admission audit.

Every case here reproduces a defect actually found in `assumption_boundary_000`, where a
frontier model produced a well-formed encoding faithful to the prose it was shown and was
scored FAIL against a private reference it could not have reconstructed.

The corpus audit found 41 of 41 public tasks carrying at least one of these. The point of
these tests is that the *validator* keeps detecting them, so a regenerated corpus cannot
quietly reintroduce them.

Each defect test is paired with a clean control, because a validator that fires on
everything is as useless as one that fires on nothing.
"""

from __future__ import annotations

from evaluation.corpus_governance.task_admission import (
    ADMISSION_CRITERIA,
    DefectClass,
    audit_task,
)

CLEAN = dict(
    task_id="clean_000",
    prose="A quantity d is greater than 4. A function f is defined by f of x equals 5 "
          "divided by x. The constant e equals 5.",
    question="",
    visible_assumptions=["d > 4"],
    visible_semantics=(
        "SemanticFacts(entities={'e': 'Real', 'd': 'Real', 'f': 'Function[Real -> Real]'}, "
        "declaration_kinds={'e': 'const', 'd': 'var', 'f': 'def'}, "
        "constraints=['d > 4'], objective='decide', body={'f': ':= 5 / x'}, "
        "dimensions={})"
    ),
    reference_hml="module M\nconst e : Real = 5\nvar d : Real\nassume d > 4\n",
)


def test_a_well_specified_task_is_admissible():
    """The control. Without it, every test below could pass by over-firing."""
    report = audit_task(**CLEAN)
    assert report.admissible, report.render()


def test_a_const_whose_value_lives_only_in_the_reference_is_rejected():
    """`assumption_boundary_000` verbatim: `eta` was `const` with no visible value."""
    bad = dict(CLEAN)
    # `e` is still declared const in the structured target, and `e` is still named in the
    # prose -- but its VALUE (7) exists only in the reference. That is the exact shape of
    # the defect: an encoder knows the symbol and cannot know the number.
    bad["prose"] = ("A quantity d is greater than 4. A function f is defined by f of x "
                    "equals e divided by x. The constant e is fixed.")
    bad["reference_hml"] = "module M\nconst e : Real = 7\nvar d : Real\n"
    report = audit_task(**bad)
    assert not report.admissible, "an unguessable constant value must be rejected"
    assert any(d.defect in (DefectClass.CONST_WITHOUT_INITIALISER,
                            DefectClass.PUBLIC_INSUFFICIENT_FOR_PRIVATE)
               for d in report.defects), report.render()


def test_an_entity_absent_from_the_prose_is_rejected():
    bad = dict(CLEAN, prose="A quantity d is greater than 4.")
    report = audit_task(**bad)
    assert any(d.defect is DefectClass.ENTITY_ABSENT_FROM_PROSE for d in report.defects), \
        report.render()


def test_prose_asserting_an_assumption_with_an_empty_assumption_list_is_rejected():
    bad = dict(CLEAN, visible_assumptions=[],
               prose=CLEAN["prose"] + " Assumption: d is strictly greater than 4.")
    report = audit_task(**bad)
    assert any(d.defect is DefectClass.ASSUMPTION_NOT_DECLARED for d in report.defects), \
        report.render()


def test_a_derived_fact_presented_as_an_input_premise_is_rejected():
    """`d != 0` beside `d > 4` is a consequence, not a premise.

    An encoder cannot know whether a consequence was meant to be restated, so scoring it
    as a required statement penalises a correct reading.
    """
    bad = dict(CLEAN)
    bad["visible_semantics"] = CLEAN["visible_semantics"].replace(
        "constraints=['d > 4']", "constraints=['d > 4', 'd != 0']")
    report = audit_task(**bad)
    assert any(d.defect is DefectClass.DERIVED_FACT_AS_INPUT_CONSTRAINT
               for d in report.defects), report.render()


def test_a_function_without_a_body_in_the_structured_target_is_rejected():
    bad = dict(CLEAN)
    bad["visible_semantics"] = CLEAN["visible_semantics"].replace(
        ", body={'f': ':= 5 / x'}", "")
    bad["reference_hml"] = CLEAN["reference_hml"] + "def f(x : Real) : Real := e / x\n"
    report = audit_task(**bad)
    assert any(d.defect is DefectClass.FUNCTION_BODY_MISSING for d in report.defects), \
        report.render()


def test_a_question_without_a_structured_objective_is_rejected():
    """This is what led the model to invent a `prove` statement the reference lacks."""
    bad = dict(CLEAN, question="Is d = 4 admissible?")
    bad["visible_semantics"] = CLEAN["visible_semantics"].replace(
        "objective='decide'", "objective=None")
    report = audit_task(**bad)
    assert any(d.defect is DefectClass.QUESTION_WITHOUT_OBJECTIVE for d in report.defects), \
        report.render()


def test_the_report_names_every_defect_it_found():
    """A count alone would not tell a corpus author what to regenerate."""
    bad = dict(CLEAN, visible_assumptions=[], question="Is d = 4 admissible?",
               prose="Assumption: d is strictly greater than 4.")
    bad["visible_semantics"] = CLEAN["visible_semantics"].replace(
        "objective='decide'", "objective=None")
    report = audit_task(**bad)
    assert len(report.defects) >= 2
    rendered = report.render()
    assert "INVALID_INSTRUMENT" in rendered
    for d in report.defects:
        assert str(d.defect) in rendered


def test_the_eight_admission_criteria_are_stated():
    assert len(ADMISSION_CRITERIA) == 8
    joined = " ".join(ADMISSION_CRITERIA)
    for phrase in ("uniquely reconstructable", "self-scores PASS", "round-trips",
                   "derived fact"):
        assert phrase in joined
