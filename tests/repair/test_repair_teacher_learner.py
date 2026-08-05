"""Role separation: the Teacher diagnoses, the Learner applies, neither does both."""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.context_broker import (
    ContextStatus,
    DiagnosticContextBroker,
    ErrorClass,
    SemanticIndex,
)
from hamiltonian_lang.improvement.diagnostics import (
    DiagnosticCategory,
    SourceSpan,
    StructuredDiagnostic,
    adapt,
)
from hamiltonian_lang.improvement.state import Hypothesis
from hamiltonian_lang.repair import (
    CLASS_INVARIANT,
    CLASS_REPAIR_STEPS,
    CLASS_SEMANTIC_CATEGORY,
    UNIVERSAL_PRESERVATION,
    DeterministicRepairTeacher,
    FeedbackArm,
    LearnerScriptError,
    LiveComponentRefused,
    NoPlan,
    RepairBudget,
    RepairEndpoint,
    RepairLearner,
    RepairPlan,
    RepairTeacher,
    ScriptedRepairLearner,
    build_payload,
    default_checker,
    run_repair_chain,
)

BROKEN = "module M\ndef f(a : Real, b : Real) : Real := a + b\ndef g : Real := f(1.0)\n"
FIXED = "module M\ndef f(a : Real, b : Real) : Real := a + b\ndef g : Real := f(1.0, 2.0)\n"


def diag(source: str) -> StructuredDiagnostic:
    return adapt(compile_source(source).diagnostics.errors[0])


# --- the class tables are total ---------------------------------------------------


@pytest.mark.parametrize("table", [CLASS_INVARIANT, CLASS_SEMANTIC_CATEGORY, CLASS_REPAIR_STEPS])
def test_class_tables_are_total_over_the_error_taxonomy(table: dict) -> None:
    """A missing entry would make the Teacher silently return NoPlan for a whole class."""
    assert set(table) == set(ErrorClass)


def test_no_class_repair_step_supplies_a_value() -> None:
    for error_class, steps in CLASS_REPAIR_STEPS.items():
        for step in steps:
            assert ":=" not in step, (error_class, step)


# --- the Teacher's contract -------------------------------------------------------


def test_the_teacher_is_offline() -> None:
    teacher = DeterministicRepairTeacher()
    assert isinstance(teacher, RepairTeacher)
    assert teacher.live is False


def test_the_teacher_returns_all_six_fields() -> None:
    context, plan = DeterministicRepairTeacher().diagnose(
        broken_output=BROKEN, diagnostic=diag(BROKEN)
    )
    assert isinstance(plan, RepairPlan)
    assert plan.failing_invariant
    assert plan.cause
    assert plan.source_span.located
    assert plan.expected_semantic_category
    assert plan.repair_steps
    assert plan.preservation_constraints
    assert plan.error_class is ErrorClass.ARITY
    assert plan.context_status is context.status


def test_every_plan_carries_the_universal_preservation_constraints() -> None:
    _, plan = DeterministicRepairTeacher().diagnose(
        broken_output=BROKEN, diagnostic=diag(BROKEN)
    )
    assert isinstance(plan, RepairPlan)
    for constraint in UNIVERSAL_PRESERVATION:
        assert constraint in plan.preservation_constraints


def test_the_invariant_source_is_recorded() -> None:
    """'Never hallucinate a rule' is only auditable if the rule's origin is on the record."""
    _, plan = DeterministicRepairTeacher().diagnose(
        broken_output=BROKEN, diagnostic=diag(BROKEN)
    )
    assert isinstance(plan, RepairPlan)
    assert plan.invariant_source
    assert plan.invariant_source in {
        "compiler_invariant_table",
        f"class_invariant:{ErrorClass.ARITY}",
    } or plan.invariant_source.startswith("module:")


def test_the_compiler_invariant_table_wins_when_it_has_an_entry() -> None:
    source = "module M\nparam x : Frobnicator\n"
    _, plan = DeterministicRepairTeacher().diagnose(
        broken_output=source, diagnostic=diag(source)
    )
    assert isinstance(plan, RepairPlan)
    assert plan.invariant_source == "compiler_invariant_table"
    assert plan.failing_invariant == "a type annotation must name a type the checker knows"


def test_the_teacher_refuses_to_plan_for_an_unsupported_error_class() -> None:
    """No error class means no rule was broken that this taxonomy can name. Inventing one
    would put text of unknown provenance into the training record."""
    unknown = StructuredDiagnostic(
        code="HML-Z999",
        category=DiagnosticCategory.UNCLASSIFIED,
        source_span=SourceSpan(),
    )
    _, result = DeterministicRepairTeacher().diagnose(
        broken_output=BROKEN, diagnostic=unknown
    )
    assert isinstance(result, NoPlan)
    assert "no error class" in result.reason
    assert result.context_status is ContextStatus.UNSUPPORTED_ERROR_CLASS


def test_an_empty_index_still_yields_a_plan_but_says_context_was_empty() -> None:
    """Retrieval failure is degraded service, not a crash — and it is stated in the plan."""
    from hamiltonian_lang.context_broker import ContextQuery

    broker = DiagnosticContextBroker(index=SemanticIndex())
    teacher = DeterministicRepairTeacher(broker=broker)
    diagnostic = diag(BROKEN)
    # ``include_local=False`` removes the last remaining source of context — the broken
    # program's own declarations — so retrieval genuinely has nothing.
    context = broker.retrieve(
        ContextQuery(diagnostic=diagnostic, source=BROKEN, include_local=False)
    )
    plan = teacher.teach(
        broken_output=BROKEN, diagnostic=diagnostic, context=context
    )
    assert context.status is ContextStatus.NO_RELEVANT_CONTEXT
    assert isinstance(plan, RepairPlan)
    assert plan.context_status is ContextStatus.NO_RELEVANT_CONTEXT
    assert plan.context_provenance == ()
    assert any("do not assume a rule" in s for s in plan.repair_steps)


def test_the_plan_cites_the_provenance_of_everything_it_used() -> None:
    context, plan = DeterministicRepairTeacher().diagnose(
        broken_output=BROKEN, diagnostic=diag(BROKEN)
    )
    assert isinstance(plan, RepairPlan)
    assert plan.context_provenance == context.provenance()
    assert plan.context_provenance


# --- the Learner's contract --------------------------------------------------------


def test_the_scripted_learner_is_offline_and_satisfies_the_protocol() -> None:
    learner = ScriptedRepairLearner(script={})
    assert isinstance(learner, RepairLearner)
    assert learner.live is False


def test_the_learner_refuses_a_turn_it_has_no_script_for() -> None:
    learner = ScriptedRepairLearner(script={})
    payload = build_payload(FeedbackArm.NO_FEEDBACK, broken_output=BROKEN)
    with pytest.raises(LearnerScriptError, match="no scripted response"):
        learner.apply(task_id="t", turn=1, payload=payload)


def test_the_learner_refuses_a_no_feedback_payload_carrying_feedback() -> None:
    """Defence in depth: the arm contract is asserted from both sides."""
    from hamiltonian_lang.repair.arms import FeedbackPayload

    learner = ScriptedRepairLearner(script={("t", FeedbackArm.NO_FEEDBACK, 1): FIXED})
    contaminated = FeedbackPayload(
        arm=FeedbackArm.NO_FEEDBACK,
        broken_output=BROKEN,
        diagnostic_text="error HML-T471: f takes 2 argument(s), 1 given",
    )
    with pytest.raises(LearnerScriptError, match="arm contract was broken"):
        learner.apply(task_id="t", turn=1, payload=contaminated)


# --- the chain wires the two roles together ----------------------------------------


def script_for(arms: tuple[FeedbackArm, ...], reply: str) -> dict:
    return {("t1", arm, 1): reply for arm in arms}


def test_the_chain_records_the_repair_and_keeps_the_two_rates_apart() -> None:
    learner = ScriptedRepairLearner(script=script_for(tuple(FeedbackArm), FIXED))
    record = run_repair_chain(
        task_id="t1",
        hypothesis=Hypothesis.ACQ0,
        endpoint=RepairEndpoint.SYNTACTIC_ENCODING,
        budget=RepairBudget.OFFICIAL_ONE,
        arm=FeedbackArm.CHAIN_OF_REPAIR,
        initial_output=BROKEN,
        learner=learner,
    )
    assert record.initial_resolved is False
    assert record.repaired is True
    assert record.resolved is True
    assert record.repair_turns_used == 1
    assert record.mechanism == "ACQ0_REPAIR"
    turn = record.turns[0]
    assert turn.diagnostic_code == "HML-T471"
    assert turn.error_class is ErrorClass.ARITY
    assert isinstance(turn.plan, RepairPlan)


def test_a_failed_repair_is_recorded_not_discarded() -> None:
    """A repair that did not help is evidence. Keeping only the successes reports a rate
    that no longer means anything."""
    learner = ScriptedRepairLearner(script={("t1", FeedbackArm.NO_FEEDBACK, 1): BROKEN})
    record = run_repair_chain(
        task_id="t1",
        hypothesis=Hypothesis.ACQ0,
        endpoint=RepairEndpoint.SYNTACTIC_ENCODING,
        budget=RepairBudget.OFFICIAL_ONE,
        arm=FeedbackArm.NO_FEEDBACK,
        initial_output=BROKEN,
        learner=learner,
    )
    assert record.repair_turns_used == 1
    assert record.turns[0].resolved is False
    assert record.resolved is False


def test_only_the_chain_of_repair_arm_produces_a_plan() -> None:
    learner = ScriptedRepairLearner(script=script_for(tuple(FeedbackArm), FIXED))
    plans = {}
    for arm in FeedbackArm:
        record = run_repair_chain(
            task_id="t1",
            hypothesis=Hypothesis.ACQ0,
            endpoint=RepairEndpoint.SYNTACTIC_ENCODING,
            budget=RepairBudget.OFFICIAL_ONE,
            arm=arm,
            initial_output=BROKEN,
            learner=learner,
        )
        plans[arm] = record.turns[0].plan
    assert plans[FeedbackArm.NO_FEEDBACK] is None
    assert plans[FeedbackArm.RAW_DIAGNOSTIC] is None
    assert isinstance(plans[FeedbackArm.CHAIN_OF_REPAIR], RepairPlan)


def test_a_clean_first_attempt_consumes_no_repair_turn() -> None:
    learner = ScriptedRepairLearner(script={})
    record = run_repair_chain(
        task_id="t1",
        hypothesis=Hypothesis.ACQ0,
        endpoint=RepairEndpoint.SYNTACTIC_ENCODING,
        budget=RepairBudget.OFFICIAL_ONE,
        arm=FeedbackArm.CHAIN_OF_REPAIR,
        initial_output=FIXED,
        learner=learner,
    )
    assert record.initial_resolved is True
    assert record.repair_turns_used == 0
    assert record.repaired is False


def test_a_live_component_is_refused_unless_explicitly_allowed() -> None:
    """The offline suite cannot start making model calls because a component was swapped."""
    learner = ScriptedRepairLearner(script={}, live=True)
    with pytest.raises(LiveComponentRefused, match="allow_live"):
        run_repair_chain(
            task_id="t1",
            hypothesis=Hypothesis.ACQ0,
            endpoint=RepairEndpoint.SYNTACTIC_ENCODING,
            budget=RepairBudget.OFFICIAL_ONE,
            arm=FeedbackArm.NO_FEEDBACK,
            initial_output=BROKEN,
            learner=learner,
        )


def test_the_default_checker_uses_the_real_compiler() -> None:
    assert default_checker(FIXED).ok is True
    outcome = default_checker(BROKEN)
    assert outcome.ok is False
    assert outcome.first_error is not None
    assert outcome.first_error.code == "HML-T471"
