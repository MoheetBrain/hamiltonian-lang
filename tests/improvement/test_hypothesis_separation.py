"""H1, H2 and H3 must stay separable forever. This file is that requirement, mechanised.

Three claims are under test and they can come apart:

* **H1** — the representation *as input* improves the answer.
* **H2** — the representation *as a reasoning workspace* improves the answer.
* **H3** — *verifier-guided repair* improves the verified answer.

A win on H3 alone is a win for verifier-guided reasoning. It is not a win for the
representation: the same repair loop over any checkable notation would predict the same
gain. If these three ever merge — in a package field, in an aggregate, or in a gate —
then a year from now the record will not say what went right and what went wrong, and
the project loses the thing it was built to produce.

Four properties, each with its own test:

1. the hypothesis is a **type**, not free text, everywhere it is recorded;
2. **aggregation** never pools observations from two hypotheses;
3. **routing and storage** never pool episodes from two hypotheses;
4. the **controller** refuses evidence drawn from a hypothesis the gate does not name;

and one more that is really the point of all four: an H3 result is never rendered as a
result about the representation.
"""

from __future__ import annotations

import inspect

import pytest

from hamiltonian_lang.improvement.controller import (
    GATES,
    MetricEvidence,
    Stage,
    StagedController,
    TransitionBlocker,
)
from hamiltonian_lang.improvement.evidence import (
    DomainFloor,
    EvidencePackage,
    FalsifierFinding,
    PromotionBlocker,
    SuiteResult,
    SuiteStatus,
    TrainingDataProvenance,
    VerifierEvidence,
    build_evidence_package,
)
from hamiltonian_lang.improvement.memory import (
    MemoryBank,
    MemoryStore,
    MemoryStoreKind,
    RoutingFacts,
    VerifierOutcome,
    build_record,
)
from hamiltonian_lang.improvement.skills import (
    SkillLedger,
    SkillObservation,
    TokenAccount,
    TokenSource,
    aggregate_observations,
)
from hamiltonian_lang.improvement.state import (
    Hypothesis,
    HypothesisMixingError,
    StateComponent,
    SystemState,
    Unavailable,
    require_single_hypothesis,
)

H1 = Hypothesis.H1_REPRESENTATION_AS_INPUT
H2 = Hypothesis.H2_REPRESENTATION_AS_WORKSPACE
H3 = Hypothesis.H3_VERIFIER_GUIDED_REPAIR

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
CANDIDATE = INCUMBENT.evolve(diagnostic_policy_version="diag-1.1.0")


def observation(idx: int, hypothesis: Hypothesis, success: bool) -> SkillObservation:
    return SkillObservation(
        observation_id=f"o-{hypothesis.value}-{idx}",
        skill_id="syntax.role_label",
        hypothesis=hypothesis,
        episode_id=f"ep-{idx}",
        round_id="r1",
        success=success,
        tokens=TokenAccount(TokenSource.REPORTED, 10, 10),
    )


def facts(hypothesis: Hypothesis, episode_id: str = "ep-1") -> RoutingFacts:
    return RoutingFacts(
        episode_id=episode_id,
        hypothesis=hypothesis,
        exact_hash="e" * 64,
        canonical_hash="c" * 64,
        first_attempt_parsed=True,
        first_attempt_semantic_fidelity=True,
        required_verifiers=("canonical_form",),
        verifier_results={"canonical_form": VerifierOutcome.PASS},
        provenance_complete=True,
    )


def package(hypothesis: Hypothesis = H3, **overrides) -> EvidencePackage:
    # The provenance is built with a valid hypothesis even when the package is being
    # handed an invalid one on purpose, so that the package's own guard is what fires.
    drawn_under = hypothesis if isinstance(hypothesis, Hypothesis) else H3
    fields = {
        "experiment_id": "X-001",
        "incumbent_state": INCUMBENT,
        "candidate_state": CANDIDATE,
        "changed_component": StateComponent.DIAGNOSTIC_POLICY,
        "trigger_episode": "ep-0001",
        "hypothesis": hypothesis,
        "hypothesis_rationale": "the diagnostic is the input to the repair attempt",
        "incumbent_failure_reproduced": True,
        "candidate_target_passed": True,
        "target_probe_id": "probe-role-label",
        "constitutional_suite_result": SuiteResult("constitutional", SuiteStatus.PASS),
        "retention_suite_result": SuiteResult("retention", SuiteStatus.PASS),
        "domain_floor_results": (DomainFloor("statistics", True, SuiteStatus.PASS, 0.93, 0.90),),
        "semantic_fidelity": 0.93,
        "repair_success": 0.71,
        "token_cost": Unavailable("scripted adapter", "a live adapter"),
        "latency": Unavailable("no model call", "a live adapter"),
        "verifier_evidence": (VerifierEvidence("canonical_form", VerifierOutcome.PASS, True),),
        "falsifier_findings": (FalsifierFinding("whitespace disguise", False),),
        "unresolved_limitations": ("one task family only",),
        "training_data_provenance": TrainingDataProvenance(
            ("repair",), ("a" * 64,), 0, drawn_under, "repair memory"
        ),
        "rollback_state": INCUMBENT,
        "rollback_procedure": "revert the policy file",
    }
    fields.update(overrides)
    return build_evidence_package(**fields)


# ---------------------------------------------------------------------------
# Property 1 — the hypothesis is a type
# ---------------------------------------------------------------------------


def test_the_evidence_package_hypothesis_is_typed_and_not_free_text():
    assert isinstance(package().hypothesis, Hypothesis)
    with pytest.raises(TypeError, match="H1/H2/H3"):
        package(hypothesis="verifier guided repair improved the answer")
    with pytest.raises(TypeError, match="H1/H2/H3"):
        package(hypothesis="H3")  # even the right string is not the type


def test_every_place_a_hypothesis_is_recorded_rejects_an_untyped_one():
    with pytest.raises(TypeError):
        RoutingFacts(episode_id="e", hypothesis="H1", exact_hash="x")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        SkillObservation("o", "syntax.role_label", "H1", "e", "r1", True)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        MetricEvidence(hypothesis="H1", values={}, provenance="p")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        MemoryStore(MemoryStoreKind.POSITIVE, "H1")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        TrainingDataProvenance((), (), 0, "H1")  # type: ignore[arg-type]


def test_each_hypothesis_states_what_it_supports_and_what_it_does_not():
    for h in Hypothesis:
        assert h.claim.strip()
        assert h.excluded_claim.strip()
        assert h.claim != h.excluded_claim
    assert "representation" in H3.excluded_claim.lower()


# ---------------------------------------------------------------------------
# Property 2 — aggregation never pools two hypotheses
# ---------------------------------------------------------------------------


def test_the_same_skill_under_two_hypotheses_produces_two_aggregates():
    ledger = SkillLedger()
    for i in range(4):
        ledger.add(observation(i, H1, success=True))
    for i in range(4):
        ledger.add(observation(i, H3, success=False))

    h1 = ledger.aggregate("syntax.role_label", H1)
    h3 = ledger.aggregate("syntax.role_label", H3)
    assert (h1.successes, h1.failures) == (4, 0)
    assert (h3.successes, h3.failures) == (0, 4)
    assert h1.mastery > 0.5 > h3.mastery
    # And the pooled figure — 4 of 8 — appears nowhere.
    assert h1.attempts == h3.attempts == 4


def test_a_mixed_sequence_cannot_be_aggregated_at_all():
    with pytest.raises(HypothesisMixingError, match="separable"):
        aggregate_observations([observation(0, H1, True), observation(1, H3, True)])
    with pytest.raises(HypothesisMixingError):
        require_single_hypothesis([observation(0, H1, True), observation(1, H2, True)], context="t")


def test_no_aggregation_accessor_can_be_called_without_a_hypothesis():
    """The separation is structural: there is no call that would pool them."""
    for method in (SkillLedger.aggregate, SkillLedger.observations, SkillLedger.aggregates,
                   SkillLedger.skills_observed, SkillLedger.report):
        params = inspect.signature(method).parameters
        assert "hypothesis" in params, method.__name__
        assert params["hypothesis"].default is inspect.Parameter.empty, method.__name__


def test_a_report_is_scoped_to_one_hypothesis_and_names_it():
    ledger = SkillLedger()
    ledger.add(observation(0, H3, True))
    ledger.add(observation(1, H1, True))
    report = ledger.report(H3)
    assert report["hypothesis"] == "H3"
    assert set(report["skills"]) == {"syntax.role_label"}
    assert report["skills"]["syntax.role_label"]["hypothesis"] == "H3"


# ---------------------------------------------------------------------------
# Property 3 — routing and storage never pool two hypotheses
# ---------------------------------------------------------------------------


def test_stores_are_keyed_by_hypothesis_and_refuse_foreign_records():
    bank = MemoryBank()
    bank.admit(build_record("r-h1", facts(H1)))
    bank.admit(build_record("r-h3", facts(H3)))
    assert bank.counts() == {("positive", "H1"): 1, ("positive", "H3"): 1}
    assert bank.hypotheses() == (H1, H3)

    store = bank.store(MemoryStoreKind.POSITIVE, H1)
    with pytest.raises(ValueError, match="never merged"):
        store.append(build_record("r-h3b", facts(H3)))


def test_identical_content_under_two_hypotheses_is_not_a_duplicate():
    """Dropping one as a duplicate would delete evidence about a different question."""
    bank = MemoryBank()
    assert bank.admit(build_record("a", facts(H1))).accepted
    assert bank.admit(build_record("b", facts(H3))).accepted
    assert len(bank.records(MemoryStoreKind.POSITIVE, H1)) == 1
    assert len(bank.records(MemoryStoreKind.POSITIVE, H3)) == 1


def test_no_storage_accessor_can_be_called_without_a_hypothesis():
    for method in (MemoryBank.records, MemoryBank.training_batch, MemoryBank.store,
                   MemoryBank.provenance_hashes, MemoryBank.quarantined_ids):
        params = inspect.signature(method).parameters
        assert "hypothesis" in params, method.__name__
        assert params["hypothesis"].default is inspect.Parameter.empty, method.__name__


def test_a_training_batch_is_drawn_for_one_hypothesis_only():
    bank = MemoryBank()
    bank.admit(build_record("h1", facts(H1, "ep-1")))
    bank.admit(build_record("h3", facts(H3, "ep-2")))
    assert [r.record_id for r in bank.training_batch(H1)] == ["h1"]
    assert [r.record_id for r in bank.training_batch(H3)] == ["h3"]


def test_an_evidence_package_may_not_draw_its_data_from_another_hypothesis():
    p = package(
        H3,
        training_data_provenance=TrainingDataProvenance(("repair",), ("a" * 64,), 0, H1, "H1 data"),
    )
    assert PromotionBlocker.HYPOTHESIS_MISMATCH in p.eligibility().codes()


# ---------------------------------------------------------------------------
# Property 4 — a gate is opened only by evidence about the hypothesis it names
# ---------------------------------------------------------------------------


def test_the_controller_refuses_evidence_from_a_hypothesis_the_gate_does_not_name():
    gate = GATES[(Stage.STAGE_0_COMPILER_TRUST, Stage.STAGE_1_SYNTAX_ACQUISITION)]
    assert gate.hypothesis is H1

    perfect_but_wrong = MetricEvidence(
        hypothesis=H3,
        values={r.metric: 1.0 for r in gate.requirements},
        provenance="an H3 repair-loop run",
    )
    verdict = StagedController().evaluate_transition(
        Stage.STAGE_1_SYNTAX_ACQUISITION, perfect_but_wrong
    )
    assert TransitionBlocker.HYPOTHESIS_MISMATCH in verdict.codes()
    assert "H3_VERIFIER_GUIDED_REPAIR" in verdict.render()
    assert "does NOT support any claim about the representation" in verdict.render()


def test_the_mismatch_is_reported_for_every_gate_whose_hypothesis_differs():
    controller = StagedController()
    for (source, target), gate in GATES.items():
        other = next(h for h in Hypothesis if h is not gate.hypothesis)
        verdict = controller.evaluate_transition(
            target,
            MetricEvidence(
                hypothesis=other,
                values={r.metric: 1.0 for r in gate.requirements},
                provenance="p",
            ),
            source=source,
        )
        assert TransitionBlocker.HYPOTHESIS_MISMATCH in verdict.codes(), gate.target.name


# ---------------------------------------------------------------------------
# The point of all four
# ---------------------------------------------------------------------------

_REPRESENTATION_WIN_PHRASES = (
    "win for the representation",
    "the representation improves",
    "the representation helps",
    "hamiltonian representation improves",
)


def test_an_h3_result_is_never_rendered_as_a_result_about_the_representation():
    p = package(H3)
    assert p.eligibility().eligible

    for rendered in (p.emit_markdown(), p.emit_pr_report(), p.emit_json()):
        lowered = rendered.lower()
        assert "does not support any claim about the representation" in lowered
        for phrase in _REPRESENTATION_WIN_PHRASES:
            assert phrase not in lowered, phrase


def test_an_h1_result_states_its_own_scope_too():
    p = package(
        H1,
        hypothesis_rationale="the surface form of the input is what changed",
        training_data_provenance=TrainingDataProvenance(
            ("positive",), ("a" * 64,), 0, H1, "positive memory"
        ),
    )
    report = p.emit_pr_report()
    assert "Scope of this result." in report
    assert "does not support the claim that reasoning in the representation helps (H2)" in report


def test_the_three_hypotheses_are_distinct_values_and_stay_that_way():
    assert len({H1, H2, H3}) == 3
    assert H3 is not H1 and H3 != H1


def test_the_canonical_identifier_set_is_pinned():
    """One type, five values. ``ACQ0`` is the syntax-acquisition prerequisite and
    ``EXCLUDED`` is engineering work; both are named here so that adding a sixth is a
    deliberate act with a test to update, not a quiet widening."""
    assert [h.value for h in Hypothesis] == ["ACQ0", "H1", "H2", "H3", "EXCLUDED"]
    # The short spellings are aliases of the descriptive ones, not extra members.
    assert Hypothesis.H1 is Hypothesis.H1_REPRESENTATION_AS_INPUT
    assert Hypothesis.H2 is Hypothesis.H2_REPRESENTATION_AS_WORKSPACE
    assert Hypothesis.H3 is Hypothesis.H3_VERIFIER_GUIDED_REPAIR


def test_only_excluded_is_outside_the_scientific_record():
    assert {h.value for h in Hypothesis if not h.scientific} == {"EXCLUDED"}
    assert Hypothesis.ACQ0.scientific is True
