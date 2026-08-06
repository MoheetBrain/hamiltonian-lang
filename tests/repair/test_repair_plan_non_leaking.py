"""The load-bearing constraint: a plan states the cause, never the answer.

A plan that contains the corrected program converts H3 from a measurement into a
tautology — the Learner copies, the verifier passes, and the reported number measures
transcription. Nothing in the transcript afterwards distinguishes that run from a real
one, which is why the boundary is enforced in code and tested here rather than described
in a prompt.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.context_broker import ContextStatus, ErrorClass
from hamiltonian_lang.improvement.diagnostics import SourceSpan, adapt
from hamiltonian_lang.repair import (
    MAX_STEP_LINES,
    MAX_STEPS,
    DeterministicRepairTeacher,
    PlanLeak,
    RepairPlan,
    assert_plan_non_leaking,
    is_program_like,
    numerals_in,
    plan_leak_reasons,
    statement_lines,
)

# --- a minimal, valid plan to mutate ---------------------------------------------


def make_plan(**overrides: object) -> RepairPlan:
    base: dict[str, object] = {
        "failing_invariant": "a call must supply the callee's declared number of arguments",
        "cause": "f takes 2 arguments, 1 given",
        "source_span": SourceSpan(line=3, col=16, file="<input>"),
        "expected_semantic_category": "an argument list of the callee's declared length",
        "repair_steps": ("Add the missing argument at the call site.",),
        "preservation_constraints": ("Do not change the definition to match the call.",),
        "error_class": ErrorClass.ARITY,
        "context_status": ContextStatus.CONTEXT_FOUND,
    }
    base.update(overrides)
    return RepairPlan(**base)  # type: ignore[arg-type]


# --- structural validity ----------------------------------------------------------


@pytest.mark.parametrize(
    "field", ["failing_invariant", "cause", "expected_semantic_category"]
)
def test_a_plan_missing_a_required_field_is_refused(field: str) -> None:
    with pytest.raises(ValueError, match="unusable"):
        make_plan(**{field: "   "})


def test_a_plan_with_no_steps_is_refused() -> None:
    with pytest.raises(ValueError, match="tells the Learner nothing"):
        make_plan(repair_steps=())


def test_a_plan_with_no_preservation_constraint_is_refused() -> None:
    """Without one, deleting the failing construct is a valid repair. It passes the
    checker and destroys the meaning."""
    with pytest.raises(ValueError, match="delete the failing construct"):
        make_plan(preservation_constraints=())


def test_a_plan_longer_than_the_step_limit_is_refused() -> None:
    with pytest.raises(ValueError, match="corrected program written in prose"):
        make_plan(repair_steps=tuple(f"step {n}" for n in range(MAX_STEPS + 1)))


def test_the_six_semantic_fields_all_render() -> None:
    rendered = make_plan().render()
    for marker in (
        "failing invariant:",
        "cause:",
        "source span:",
        "expected semantic category:",
        "repair plan:",
        "preservation constraints:",
    ):
        assert marker in rendered


# --- leak detection ---------------------------------------------------------------


def test_a_plan_containing_the_corrected_program_leaks() -> None:
    fixed = "module M\ndef f(a : Real, b : Real) : Real := a + b\ndef g : Real := f(1.0, 2.0)"
    plan = make_plan(repair_steps=("Write this:", fixed))
    reasons = plan_leak_reasons(plan, target_program=fixed)
    assert any("corrected program" in r for r in reasons)
    with pytest.raises(PlanLeak):
        assert_plan_non_leaking(plan, target_program=fixed)


def test_a_plan_containing_the_final_answer_leaks() -> None:
    plan = make_plan(cause="the result should be 42.5")
    reasons = plan_leak_reasons(plan, final_answer="42.5")
    assert any("final mathematical answer" in r for r in reasons)


def test_a_step_that_binds_a_concrete_value_leaks() -> None:
    """``scale := ...`` is a correction. ``scale := 0.5`` is the answer."""
    plan = make_plan(repair_steps=("Set scale := 0.5 on the Normal.",))
    reasons = plan_leak_reasons(plan)
    assert any("binds a concrete value" in r for r in reasons)


def test_a_step_with_an_elided_right_hand_side_does_not_leak() -> None:
    plan = make_plan(repair_steps=("Rename the label so the call reads scale := ...",))
    assert plan_leak_reasons(plan) == []


def test_a_multi_line_step_is_a_patch_not_an_instruction() -> None:
    long_step = "\n".join(f"line {n}" for n in range(MAX_STEP_LINES + 2))
    reasons = plan_leak_reasons(make_plan(repair_steps=(long_step,)))
    assert any("replacement patch" in r for r in reasons)


def test_a_step_with_several_statement_keywords_is_a_program_fragment() -> None:
    step = "param theta : Probability and then def g : Real := theta"
    reasons = plan_leak_reasons(make_plan(repair_steps=(step,)))
    assert any("program fragment" in r for r in reasons)


def test_a_novel_numeral_leaks_only_at_a_mathematical_endpoint() -> None:
    """At a syntactic endpoint an arity count is ordinary. At a mathematical endpoint an
    unexplained numeral is indistinguishable from the answer."""
    plan = make_plan(cause="the intended value is 7")
    assert plan_leak_reasons(plan) == []
    reasons = plan_leak_reasons(plan, forbid_novel_numerals=True, known_numerals=("2", "1"))
    assert any("novel numeral" in r or "numerals not present" in r for r in reasons)


def test_a_numeral_already_visible_to_the_learner_is_not_novel() -> None:
    plan = make_plan(cause="f takes 2 arguments, 1 given")
    reasons = plan_leak_reasons(
        plan, forbid_novel_numerals=True, known_numerals=numerals_in("f takes 2, got 1")
    )
    assert reasons == []


def test_a_short_but_complete_corrected_statement_still_leaks() -> None:
    """The blind spot the leakage harness surfaced.

    ``param x : Real`` carries three significant tokens — below the fragment floor — and
    is nonetheless the entire answer to an unknown-type diagnostic. A pure token-count
    guard let exactly that class of short corrected statement through unflagged, so the
    boundary check and the reconstruction study disagreed about the same plan.
    """
    target = "param x : Real"
    plan = make_plan(repair_steps=(f"Replace the annotation: {target}",))
    assert is_program_like(target)
    reasons = plan_leak_reasons(plan, target_program=target)
    assert any("complete corrected program" in r for r in reasons)


@pytest.mark.parametrize("fragment", ["x", "Real", "f(1.0)", "the call site"])
def test_a_fragment_that_is_not_a_statement_is_not_treated_as_the_answer(
    fragment: str,
) -> None:
    """The floor still holds. Otherwise every plan naming a variable would 'leak'."""
    assert not is_program_like(fragment)
    plan = make_plan(repair_steps=(f"Look again at {fragment} and correct it.",))
    assert plan_leak_reasons(plan, target_program=fragment) == []


def test_the_two_leak_mechanisms_share_one_notion_of_a_statement() -> None:
    """A drift between them would show up as a silent disagreement, in either direction."""
    assert statement_lines("param x : Real\nRead the rule above.") == ["param x : Real"]
    assert all(is_program_like(s) for s in statement_lines("def g : Real := f(1.0, 2.0)"))


def test_a_clean_plan_passes_and_is_returned_unchanged() -> None:
    plan = make_plan()
    assert assert_plan_non_leaking(plan) is plan


# --- the Teacher itself never leaks ------------------------------------------------

BROKEN_AND_FIXED: dict[str, tuple[str, str]] = {
    "HML-T471": (
        "module M\ndef f(a : Real, b : Real) : Real := a + b\ndef g : Real := f(1.0)\n",
        "module M\ndef f(a : Real, b : Real) : Real := a + b\ndef g : Real := f(1.0, 2.0)\n",
    ),
    "HML-T472": (
        "module M\ndef f(a : Real, b : PositiveReal) : Real := a + b\n"
        "def c : Real := f(1.0, -2.0)\n",
        "module M\ndef f(a : Real, b : PositiveReal) : Real := a + b\n"
        "def c : Real := f(1.0, 2.0)\n",
    ),
    "HML-T415": (
        "module M\nparam s : PositiveReal\nvar X : Real\n"
        "law X ~ Normal(location := 0.0, variance := s)\n",
        "module M\nparam s : PositiveReal\nvar X : Real\n"
        "law X ~ Normal(location := 0.0, scale := s)\n",
    ),
    "HML-T440": (
        "module M\nparam x : Frobnicator\n",
        "module M\nparam x : Real\n",
    ),
    "HML-N306": (
        "module M\nparam a : Real\ndef c : Real := wibble(a)\n",
        "module M\nparam a : Real\ndef c : Real := exp(a)\n",
    ),
}


@pytest.mark.parametrize("code", sorted(BROKEN_AND_FIXED))
def test_the_teacher_never_emits_the_corrected_program(code: str) -> None:
    broken, fixed = BROKEN_AND_FIXED[code]
    errors = compile_source(broken).diagnostics.errors
    diagnostic = next(d for d in errors if d.code == code)
    teacher = DeterministicRepairTeacher()
    _, plan = teacher.diagnose(broken_output=broken, diagnostic=adapt(diagnostic))
    assert isinstance(plan, RepairPlan), plan

    rendered = " ".join(plan.render().split())
    for statement in fixed.strip().splitlines():
        statement = statement.strip()
        if statement and statement not in broken:
            assert statement not in rendered, (
                f"the plan for {code} contains the corrected statement {statement!r}"
            )
    assert plan_leak_reasons(plan, target_program=fixed) == []


@pytest.mark.parametrize("code", sorted(BROKEN_AND_FIXED))
def test_the_teachers_plan_does_not_compile_as_a_program(code: str) -> None:
    """A blunt structural check: if the plan were the answer, it would be a program."""
    broken, _ = BROKEN_AND_FIXED[code]
    errors = compile_source(broken).diagnostics.errors
    diagnostic = next(d for d in errors if d.code == code)
    _, plan = DeterministicRepairTeacher().diagnose(
        broken_output=broken, diagnostic=adapt(diagnostic)
    )
    assert isinstance(plan, RepairPlan)
    assert not compile_source(plan.render()).ok()
    for step in plan.repair_steps:
        assert not compile_source(step).ok()
