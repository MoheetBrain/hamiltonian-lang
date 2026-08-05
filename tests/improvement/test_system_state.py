"""Phase 5 — the one-component-at-a-time rule, and the hidden-drift check.

The four cases the directive names are the first four tests. The rest cover the ways a
proposal can be well-formed on the surface and unattributable underneath.
"""

from __future__ import annotations

import dataclasses

import pytest

from hamiltonian_lang.improvement.state import (
    Hypothesis,
    HypothesisMixingError,
    ProposalRejection,
    RollbackPlan,
    StateComponent,
    StateTransitionProposal,
    SystemState,
    Unavailable,
    diff_states,
    require_single_hypothesis,
)

INCUMBENT = SystemState(
    semantic_kernel_version="kernel-1.0.0",
    surface_language_version="surface-1.0.0",
    diagnostic_policy_version="diag-1.0.0",
    model_version="model-a",
    curriculum_policy_version="curriculum-1.0.0",
    memory_schema_version="memory-1.0.0",
    verifier_configuration_version="verifier-1.0.0",
    compiler_commit="967e95d",
)


def proposal(candidate: SystemState, component: StateComponent, **kw) -> StateTransitionProposal:
    fields = {
        "proposal_id": "P-001",
        "incumbent": INCUMBENT,
        "candidate": candidate,
        "declared_component": component,
        "hypothesis": Hypothesis.H3_VERIFIER_GUIDED_REPAIR,
        "hypothesis_rationale": "the diagnostic drives the repair loop under test",
        "trigger_episode_id": "ep-0001",
        "rollback": RollbackPlan(INCUMBENT, "revert the policy file and re-run conformance"),
    }
    fields.update(kw)
    return StateTransitionProposal(**fields)


def test_one_diagnostic_policy_change_passes():
    p = proposal(
        INCUMBENT.evolve(diagnostic_policy_version="diag-1.1.0"),
        StateComponent.DIAGNOSTIC_POLICY,
    )
    verdict = p.validate()
    assert verdict.ok, verdict.render()
    assert verdict.diff.changed_components == frozenset({StateComponent.DIAGNOSTIC_POLICY})


def test_one_language_change_passes():
    p = proposal(
        INCUMBENT.evolve(surface_language_version="surface-1.1.0"),
        StateComponent.SURFACE_LANGUAGE,
        hypothesis=Hypothesis.H1_REPRESENTATION_AS_INPUT,
        hypothesis_rationale="the surface is what H1 is about",
    )
    assert p.validate().ok


def test_simultaneous_language_and_model_change_fails():
    p = proposal(
        INCUMBENT.evolve(surface_language_version="surface-1.1.0", model_version="model-b"),
        StateComponent.SURFACE_LANGUAGE,
    )
    verdict = p.validate()
    assert not verdict.ok
    assert ProposalRejection.MULTIPLE_COMPONENTS_CHANGED in verdict.codes()
    # And the undeclared half is named explicitly, not merely counted.
    assert ProposalRejection.UNDECLARED_VERSION_DRIFT in verdict.codes()
    assert "model_version" in verdict.render()


def test_hidden_version_drift_fails():
    """The declared change is real; the compiler moved too and nobody said so."""
    p = proposal(
        INCUMBENT.evolve(diagnostic_policy_version="diag-1.1.0", compiler_commit="deadbee"),
        StateComponent.DIAGNOSTIC_POLICY,
    )
    verdict = p.validate()
    assert not verdict.ok
    assert ProposalRejection.UNDECLARED_VERSION_DRIFT in verdict.codes()
    assert "compiler_commit" in verdict.render()
    # Exactly one *component* moved, so the naive count would have accepted this.
    assert verdict.diff.changed_components == frozenset({StateComponent.DIAGNOSTIC_POLICY})


def test_hidden_drift_in_the_memory_schema_also_fails():
    p = proposal(
        INCUMBENT.evolve(model_version="model-b", memory_schema_version="memory-2.0.0"),
        StateComponent.MODEL,
    )
    verdict = p.validate()
    assert not verdict.ok
    assert ProposalRejection.UNDECLARED_VERSION_DRIFT in verdict.codes()


def test_zero_component_proposal_is_rejected():
    verdict = proposal(INCUMBENT, StateComponent.MODEL).validate()
    assert not verdict.ok
    assert ProposalRejection.NO_COMPONENT_CHANGED in verdict.codes()


def test_declaring_a_component_that_did_not_change_is_rejected():
    p = proposal(INCUMBENT.evolve(model_version="model-b"), StateComponent.CURRICULUM)
    codes = p.validate().codes()
    assert ProposalRejection.DECLARED_COMPONENT_UNCHANGED in codes
    assert ProposalRejection.UNDECLARED_VERSION_DRIFT in codes


def test_a_non_component_change_alone_is_still_not_a_transition():
    p = proposal(INCUMBENT.evolve(compiler_commit="deadbee"), StateComponent.SEMANTIC_KERNEL)
    codes = p.validate().codes()
    assert ProposalRejection.DECLARED_COMPONENT_UNCHANGED in codes


def test_missing_trigger_episode_is_rejected():
    p = proposal(
        INCUMBENT.evolve(model_version="model-b"), StateComponent.MODEL, trigger_episode_id="  "
    )
    assert ProposalRejection.MISSING_TRIGGER_EPISODE in p.validate().codes()


def test_missing_hypothesis_rationale_is_rejected():
    p = proposal(
        INCUMBENT.evolve(model_version="model-b"),
        StateComponent.MODEL,
        hypothesis_rationale="",
    )
    assert ProposalRejection.MISSING_HYPOTHESIS_RATIONALE in p.validate().codes()


def test_rollback_must_return_to_the_incumbent():
    elsewhere = INCUMBENT.evolve(curriculum_policy_version="curriculum-9.9.9")
    p = proposal(
        INCUMBENT.evolve(model_version="model-b"),
        StateComponent.MODEL,
        rollback=RollbackPlan(elsewhere, "restore an older snapshot"),
    )
    assert ProposalRejection.ROLLBACK_TARGET_NOT_INCUMBENT in p.validate().codes()


def test_rollback_requires_a_procedure():
    with pytest.raises(ValueError, match="procedure"):
        RollbackPlan(INCUMBENT, "   ")


def test_hypothesis_must_be_typed_not_free_text():
    with pytest.raises(TypeError, match="Hypothesis"):
        proposal(
            INCUMBENT.evolve(model_version="model-b"),
            StateComponent.MODEL,
            hypothesis="verifier guided repair helps",
        )


def test_state_is_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        INCUMBENT.model_version = "model-b"  # type: ignore[misc]


def test_every_field_is_required_and_non_empty():
    with pytest.raises(ValueError, match="non-empty"):
        INCUMBENT.evolve(model_version="")


def test_fingerprint_changes_when_any_field_changes():
    base = INCUMBENT.fingerprint()
    for f in dataclasses.fields(SystemState):
        moved = INCUMBENT.evolve(**{f.name: "moved"})
        assert moved.fingerprint() != base, f.name


def test_diff_reports_component_and_non_component_fields_separately():
    d = diff_states(INCUMBENT, INCUMBENT.evolve(model_version="model-b", compiler_commit="x"))
    assert d.changed_components == frozenset({StateComponent.MODEL})
    assert d.changed_non_component_fields == ("compiler_commit",)


def test_unavailable_refuses_to_become_a_number():
    u = Unavailable("no adapter reported tokens", "an adapter that reports usage")
    with pytest.raises(TypeError):
        float(u)
    assert u.to_dict()["UNAVAILABLE"] is True


def test_require_single_hypothesis_rejects_a_mixed_or_empty_set():
    with pytest.raises(HypothesisMixingError, match="separable"):
        require_single_hypothesis(
            [Hypothesis.H1_REPRESENTATION_AS_INPUT, Hypothesis.H3_VERIFIER_GUIDED_REPAIR],
            context="test",
        )
    with pytest.raises(HypothesisMixingError, match="no observations"):
        require_single_hypothesis([], context="test")


def test_every_component_maps_to_a_distinct_state_field():
    from hamiltonian_lang.improvement.state import COMPONENT_FIELD, NON_COMPONENT_FIELDS

    assert set(COMPONENT_FIELD) == set(StateComponent)
    assert len(set(COMPONENT_FIELD.values())) == len(StateComponent)
    names = {f.name for f in dataclasses.fields(SystemState)}
    assert set(COMPONENT_FIELD.values()) | set(NON_COMPONENT_FIELDS) == names
