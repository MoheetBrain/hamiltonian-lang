"""Phase 12 — one executable stage, six gates, and refusals that explain themselves.

The controller's job right now is to say no accurately. A refusal that does not name the
missing metrics is a refusal nobody can act on, so every test below checks the
explanation as well as the verdict.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from hamiltonian_lang.improvement.controller import (
    CALIBRATION_PROPOSED,
    EXECUTABLE_STAGES,
    GATES,
    NOT_IMPLEMENTED_MECHANISMS,
    MetricEvidence,
    PrematureTransitionError,
    Stage,
    StagedController,
    StageNotExecutable,
    TransitionBlocker,
)
from hamiltonian_lang.improvement.state import Hypothesis, Unavailable

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "hamiltonian_lang" / "improvement"
H1 = Hypothesis.H1_REPRESENTATION_AS_INPUT
H3 = Hypothesis.H3_VERIFIER_GUIDED_REPAIR


def full_evidence(hypothesis: Hypothesis = H1) -> MetricEvidence:
    gate = GATES[(Stage.STAGE_0_COMPILER_TRUST, Stage.STAGE_1_SYNTAX_ACQUISITION)]
    return MetricEvidence(
        hypothesis=hypothesis,
        values={r.metric: 1.0 for r in gate.requirements},
        provenance="tests/improvement/test_stage_controller.py",
    )


def test_only_stage_zero_is_executable():
    assert EXECUTABLE_STAGES == frozenset({Stage.STAGE_0_COMPILER_TRUST})
    assert len(Stage) == 7


def test_stage_zero_runs_and_later_stages_refuse():
    controller = StagedController()
    assert controller.execute(Stage.STAGE_0_COMPILER_TRUST, lambda: "ran") == "ran"
    with pytest.raises(StageNotExecutable, match="no implementation"):
        controller.execute(Stage.STAGE_2_ON_POLICY_REPAIR, lambda: "ran")


def test_the_refusal_names_what_is_not_implemented_anywhere():
    controller = StagedController()
    with pytest.raises(StageNotExecutable) as excinfo:
        controller.execute(Stage.STAGE_5_SELF_PLAY, lambda: None)
    for mechanism in NOT_IMPLEMENTED_MECHANISMS:
        assert mechanism in str(excinfo.value)


def test_a_transition_is_refused_even_when_every_metric_clears_its_threshold():
    verdict = StagedController().evaluate_transition(
        Stage.STAGE_1_SYNTAX_ACQUISITION, full_evidence()
    )
    assert not verdict.allowed
    assert verdict.codes() == (TransitionBlocker.STAGE_NOT_IMPLEMENTED,)
    assert not verdict.missing_metrics


def test_missing_metrics_are_named_one_by_one():
    evidence = MetricEvidence(hypothesis=H1, values={}, provenance="test")
    verdict = StagedController().evaluate_transition(Stage.STAGE_1_SYNTAX_ACQUISITION, evidence)
    gate = GATES[(Stage.STAGE_0_COMPILER_TRUST, Stage.STAGE_1_SYNTAX_ACQUISITION)]
    assert set(verdict.missing_metrics) == set(gate.metric_names())
    rendered = verdict.render()
    for metric in gate.metric_names():
        assert metric in rendered


def test_a_metric_below_its_threshold_is_reported_with_both_numbers():
    values = {r.metric: 1.0 for r in GATES[(Stage(0), Stage(1))].requirements}
    values["diagnostic_precision"] = 0.5
    verdict = StagedController().evaluate_transition(
        Stage.STAGE_1_SYNTAX_ACQUISITION,
        MetricEvidence(hypothesis=H1, values=values, provenance="test"),
    )
    assert TransitionBlocker.METRIC_BELOW_THRESHOLD in verdict.codes()
    assert verdict.below_threshold == (("diagnostic_precision", 0.5, 0.90),)
    assert "0.5 < required 0.9" in verdict.render()


def test_an_unavailable_metric_is_not_treated_as_a_pass():
    values: dict[str, object] = {r.metric: 1.0 for r in GATES[(Stage(0), Stage(1))].requirements}
    values["required_verifier_coverage"] = Unavailable("no verifier ran", "a verifier")
    verdict = StagedController().evaluate_transition(
        Stage.STAGE_1_SYNTAX_ACQUISITION,
        MetricEvidence(hypothesis=H1, values=values, provenance="test"),  # type: ignore[arg-type]
    )
    assert TransitionBlocker.METRIC_UNAVAILABLE in verdict.codes()
    assert verdict.unavailable_metrics == ("required_verifier_coverage",)


def test_stages_cannot_be_skipped():
    verdict = StagedController().evaluate_transition(Stage.STAGE_3_HARD_NEGATIVE_PREFERENCE, full_evidence())
    assert TransitionBlocker.NOT_THE_NEXT_STAGE in verdict.codes()
    assert TransitionBlocker.UNKNOWN_TRANSITION in verdict.codes()


def test_evidence_without_provenance_is_refused():
    gate = GATES[(Stage(0), Stage(1))]
    verdict = StagedController().evaluate_transition(
        Stage.STAGE_1_SYNTAX_ACQUISITION,
        MetricEvidence(
            hypothesis=H1, values={r.metric: 1.0 for r in gate.requirements}, provenance=" "
        ),
    )
    assert TransitionBlocker.PROVENANCE_MISSING in verdict.codes()


def test_advance_raises_and_leaves_the_stage_where_it_was():
    controller = StagedController()
    with pytest.raises(PrematureTransitionError) as excinfo:
        controller.advance(Stage.STAGE_1_SYNTAX_ACQUISITION, full_evidence())
    assert controller.stage is Stage.STAGE_0_COMPILER_TRUST
    assert "REFUSED" in str(excinfo.value)
    assert excinfo.value.verdict.gate is not None


def test_every_consecutive_pair_has_a_gate_and_every_gate_names_a_hypothesis():
    expected = {(Stage(i), Stage(i + 1)) for i in range(len(Stage) - 1)}
    assert set(GATES) == expected
    for gate in GATES.values():
        assert isinstance(gate.hypothesis, Hypothesis)
        assert gate.requirements
        assert gate.rationale.strip()


def test_no_threshold_claims_to_be_calibrated():
    """Every number here was written down in advance, not measured. It says so."""
    for gate in GATES.values():
        for requirement in gate.requirements:
            assert requirement.calibration == CALIBRATION_PROPOSED, requirement.metric


def test_the_roadmap_states_the_absences():
    roadmap = StagedController().roadmap()
    assert roadmap["executable_stages"] == ["STAGE_0_COMPILER_TRUST"]
    assert roadmap["threshold_calibration"] == CALIBRATION_PROPOSED
    assert set(roadmap["not_implemented"]) == set(NOT_IMPLEMENTED_MECHANISMS)


# ---------------------------------------------------------------------------
# The absences are real
# ---------------------------------------------------------------------------

_BANNED_EXACT = {"sft", "dpo", "grpo", "lora", "conjecturer", "solver", "falsifier"}
_BANNED_SUBSTRINGS = (
    "fine_tune",
    "finetune",
    "best_of_n",
    "bestofn",
    "promote_weights",
    "policy_gradient",
    "mutate_syntax",
    "reward_model",
    "train_step",
)


def test_no_training_or_search_mechanism_is_defined_in_this_package():
    """The prohibition is checked against the code, not against the docstrings."""
    offenders: list[str] = []
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            name = node.name.lower()
            if name in _BANNED_EXACT or any(b in name for b in _BANNED_SUBSTRINGS):
                offenders.append(f"{path.name}:{node.name}")
    assert not offenders, f"prohibited mechanism defined: {offenders}"
