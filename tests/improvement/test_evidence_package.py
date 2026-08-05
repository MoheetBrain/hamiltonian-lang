"""Phase 13 — the evidence package and the promotion dry-run.

The package's value is that its decision cannot be written by hand. Most of these tests
remove one condition from a complete package and assert both that the decision flips and
that the blocker says which condition was removed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hamiltonian_lang.improvement.evidence import (
    DomainFloor,
    EvidenceInconsistencyError,
    EvidencePackage,
    FalsifierFinding,
    PromotionBlocker,
    PromotionDecision,
    SuiteResult,
    SuiteStatus,
    TrainingDataProvenance,
    VerifierEvidence,
    build_evidence_package,
)
from hamiltonian_lang.improvement.memory import VerifierOutcome
from hamiltonian_lang.improvement.state import (
    Hypothesis,
    StateComponent,
    SystemState,
    Unavailable,
)

MODULE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hamiltonian_lang"
    / "improvement"
    / "evidence.py"
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
CANDIDATE = INCUMBENT.evolve(diagnostic_policy_version="diag-1.1.0")
H3 = Hypothesis.H3_VERIFIER_GUIDED_REPAIR


def package(**overrides) -> EvidencePackage:
    fields = {
        "experiment_id": "X-001",
        "incumbent_state": INCUMBENT,
        "candidate_state": CANDIDATE,
        "changed_component": StateComponent.DIAGNOSTIC_POLICY,
        "trigger_episode": "ep-0001",
        "hypothesis": H3,
        "hypothesis_rationale": "the diagnostic is the input to the repair attempt",
        "incumbent_failure_reproduced": True,
        "candidate_target_passed": True,
        "target_probe_id": "probe-role-label",
        "constitutional_suite_result": SuiteResult(
            "constitutional", SuiteStatus.PASS, "pytest -q", passed=3454
        ),
        "retention_suite_result": SuiteResult("retention", SuiteStatus.PASS, "pytest -q -k golden"),
        "domain_floor_results": (
            DomainFloor("statistics", True, SuiteStatus.PASS, 0.93, 0.90),
            DomainFloor("dimension", False, SuiteStatus.NOT_RUN, 0.0, 0.90),
        ),
        "semantic_fidelity": 0.93,
        "repair_success": 0.71,
        "token_cost": Unavailable("the scripted adapter reported no tokens", "a live adapter"),
        "latency": Unavailable("no model call was made", "a live adapter"),
        "verifier_evidence": (
            VerifierEvidence("canonical_form", VerifierOutcome.PASS, True, "hash match"),
            VerifierEvidence("lean", VerifierOutcome.UNSUPPORTED, False, "Mathlib absent"),
        ),
        "falsifier_findings": (
            FalsifierFinding("whitespace disguise", False, "the canonical hash is unchanged"),
        ),
        "unresolved_limitations": ("the repair loop has been run on one task family only",),
        "training_data_provenance": TrainingDataProvenance(
            memory_stores_used=("repair",),
            record_hashes=("a" * 64,),
            quarantined_records_used=0,
            hypothesis=H3,
            description="repair memory for H3, drawn at memory schema memory-1.0.0",
        ),
        "rollback_state": INCUMBENT,
        "rollback_procedure": "revert the diagnostic policy file and re-run conformance",
    }
    fields.update(overrides)
    return build_evidence_package(**fields)


def test_a_complete_package_is_eligible_and_the_decision_is_derived():
    p = package()
    assert p.eligibility().eligible, p.eligibility().blockers
    assert p.decision is PromotionDecision.PROMOTE_RECOMMENDED
    assert p.requires_human_approval is True


def test_a_decision_that_contradicts_the_evidence_cannot_be_constructed():
    """Hand-writing PROMOTE over failing evidence raises rather than being believed."""
    with pytest.raises(EvidenceInconsistencyError, match="supports"):
        EvidencePackage(
            experiment_id="X-002",
            incumbent_state=INCUMBENT,
            candidate_state=CANDIDATE,
            changed_component=StateComponent.DIAGNOSTIC_POLICY,
            trigger_episode="ep-1",
            hypothesis=H3,
            hypothesis_rationale="r",
            incumbent_failure_reproduced=False,
            candidate_target_passed=False,
            target_probe_id="",
            constitutional_suite_result=SuiteResult("c", SuiteStatus.NOT_RUN),
            retention_suite_result=SuiteResult("r", SuiteStatus.NOT_RUN),
            domain_floor_results=(),
            semantic_fidelity=0.0,
            repair_success=0.0,
            token_cost=0.0,
            latency=0.0,
            verifier_evidence=(),
            falsifier_findings=(),
            unresolved_limitations=(),
            training_data_provenance=TrainingDataProvenance((), (), 0, H3),
            rollback_state=None,
            rollback_procedure="",
            decision=PromotionDecision.PROMOTE_RECOMMENDED,
        )


@pytest.mark.parametrize(
    ("overrides", "blocker"),
    [
        (
            {"incumbent_failure_reproduced": False},
            PromotionBlocker.INCUMBENT_FAILURE_NOT_REPRODUCED,
        ),
        ({"candidate_target_passed": False}, PromotionBlocker.CANDIDATE_TARGET_NOT_PASSED),
        ({"target_probe_id": "  "}, PromotionBlocker.TARGET_PROBE_UNIDENTIFIED),
        (
            {"constitutional_suite_result": SuiteResult("c", SuiteStatus.FAIL, failed=2)},
            PromotionBlocker.CONSTITUTIONAL_SUITE_NOT_PASSED,
        ),
        (
            {"constitutional_suite_result": SuiteResult("c", SuiteStatus.NOT_RUN)},
            PromotionBlocker.CONSTITUTIONAL_SUITE_NOT_PASSED,
        ),
        (
            {"retention_suite_result": SuiteResult("r", SuiteStatus.NOT_RUN)},
            PromotionBlocker.RETENTION_SUITE_NOT_PASSED,
        ),
        (
            {"domain_floor_results": (DomainFloor("statistics", True, SuiteStatus.FAIL),)},
            PromotionBlocker.DOMAIN_FLOOR_NOT_MET,
        ),
        ({"rollback_state": None}, PromotionBlocker.ROLLBACK_UNDEFINED),
        ({"rollback_procedure": ""}, PromotionBlocker.ROLLBACK_UNDEFINED),
        ({"verifier_evidence": ()}, PromotionBlocker.REQUIRED_VERIFIER_UNSATISFIED),
        (
            {
                "verifier_evidence": (
                    VerifierEvidence("canonical_form", VerifierOutcome.INCONCLUSIVE, True),
                )
            },
            PromotionBlocker.REQUIRED_VERIFIER_UNSATISFIED,
        ),
    ],
)
def test_each_removed_condition_blocks_promotion_and_says_which(overrides, blocker):
    p = package(**overrides)
    assert p.decision is PromotionDecision.DO_NOT_PROMOTE
    assert blocker in p.eligibility().codes()


def test_a_suite_that_did_not_run_has_not_passed():
    p = package(constitutional_suite_result=SuiteResult("c", SuiteStatus.NOT_RUN))
    detail = dict(p.eligibility().blockers)[PromotionBlocker.CONSTITUTIONAL_SUITE_NOT_PASSED]
    assert "did not run has not passed" in detail


def test_quarantined_training_data_blocks_promotion():
    p = package(
        training_data_provenance=TrainingDataProvenance(
            memory_stores_used=("repair", "quarantine"),
            record_hashes=("a" * 64,),
            quarantined_records_used=1,
            hypothesis=H3,
            description="mixed draw",
        )
    )
    assert PromotionBlocker.QUARANTINED_DATA_USED in p.eligibility().codes()


def test_incomplete_provenance_blocks_promotion():
    p = package(
        training_data_provenance=TrainingDataProvenance((), (), 0, H3, description="")
    )
    assert PromotionBlocker.PROVENANCE_INCOMPLETE in p.eligibility().codes()


def test_a_two_component_change_blocks_promotion():
    p = package(candidate_state=INCUMBENT.evolve(diagnostic_policy_version="d2", model_version="m2"))
    codes = p.eligibility().codes()
    assert PromotionBlocker.NOT_EXACTLY_ONE_COMPONENT in codes
    detail = dict(p.eligibility().blockers)[PromotionBlocker.NOT_EXACTLY_ONE_COMPONENT]
    assert "multiple_components_changed" in detail


def test_hidden_drift_blocks_promotion_here_too():
    p = package(
        candidate_state=INCUMBENT.evolve(diagnostic_policy_version="d2", compiler_commit="beef")
    )
    detail = dict(p.eligibility().blockers)[PromotionBlocker.NOT_EXACTLY_ONE_COMPONENT]
    assert "undeclared_version_drift" in detail


def test_human_approval_cannot_be_waived():
    with pytest.raises(EvidenceInconsistencyError, match="human approval"):
        package(requires_human_approval=False)


def test_the_hypothesis_must_be_typed():
    with pytest.raises(TypeError, match="H1/H2/H3"):
        package(hypothesis="verifier guided repair")


def test_json_is_machine_readable_and_deterministic():
    p = package()
    blob = p.emit_json()
    assert json.loads(blob) == p.to_dict()
    assert p.emit_json() == blob
    parsed = json.loads(blob)
    assert parsed["decision"] == "promote_recommended"
    assert parsed["metrics"]["token_cost"]["UNAVAILABLE"] is True
    assert parsed["incumbent_state_fingerprint"] != parsed["candidate_state_fingerprint"]


def test_the_markdown_report_carries_every_section_a_reviewer_needs():
    md = package().emit_markdown()
    for heading in (
        "## Hypothesis",
        "## Change",
        "## Reproduction",
        "## Suites",
        "## Domain floors",
        "## Measurements",
        "## Verifiers",
        "## Falsifier findings",
        "## Unresolved limitations",
        "## Training data provenance",
        "## Rollback",
        "## Eligibility",
    ):
        assert heading in md, heading
    assert "UNAVAILABLE" in md  # the token cost is not rendered as a number
    assert "human approval is mandatory" in md


def test_the_pr_report_is_a_dry_run_and_says_so():
    report = package().emit_pr_report()
    assert "dry run" in report
    assert "No pull request was created" in report
    assert "Awaiting human approval" in report


def test_the_pr_report_of_a_refused_package_lists_every_blocker():
    p = package(incumbent_failure_reproduced=False, candidate_target_passed=False)
    report = p.emit_pr_report()
    assert "Not eligible" in report
    assert "incumbent_failure_not_reproduced" in report
    assert "candidate_target_not_passed" in report


def test_nothing_in_this_module_can_reach_the_network_or_a_shell():
    """The dry run is a dry run because the module has no way to be anything else."""
    import ast

    banned = {
        "urllib",
        "requests",
        "http",
        "httpx",
        "socket",
        "subprocess",
        "os",
        "shutil",
        "smtplib",
        "ftplib",
        "webbrowser",
        "github",
    }
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert not (imported & banned), f"evidence.py imports {sorted(imported & banned)}"
