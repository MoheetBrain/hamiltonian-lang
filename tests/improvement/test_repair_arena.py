"""Phase 14 — the offline one-repair arena, end to end.

Three fixtures, all deterministic and all offline: a first attempt that is already
correct, a first attempt that fails and is repaired once, and a first attempt that fails
and whose single repair also fails. The third exists because a subsystem that has only
been exercised on its success path has not been exercised.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from hamiltonian_lang.improvement.memory import (
    MemoryBank,
    MemoryStoreKind,
    QuarantineReason,
    VerifierOutcome,
    build_record,
)
from hamiltonian_lang.improvement.runner import (
    ArenaConfig,
    ArenaStatus,
    ArenaTask,
    CanonicalFormVerifier,
    EventName,
    InMemoryLedger,
    RepairBudgetExceeded,
    ScriptedModel,
    ScriptedTurns,
    replay,
    run_arena,
)
from hamiltonian_lang.improvement.state import Hypothesis, SystemState, Unavailable

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "hamiltonian_lang" / "improvement"
H3 = Hypothesis.H3_VERIFIER_GUIDED_REPAIR

STATE = SystemState(
    semantic_kernel_version="kernel-1.0.0",
    surface_language_version="surface-1.0.0",
    diagnostic_policy_version="diag-1.0.0",
    model_version="scripted-0",
    curriculum_policy_version="curriculum-1.0.0",
    memory_schema_version="memory-1.0.0",
    verifier_configuration_version="verifier-1.0.0",
    compiler_commit="967e95d",
)
CONFIG = ArenaConfig(hypothesis=H3, state=STATE)

WEIGHT_REFERENCE = """module Kinematics

const gravity : Real = 9.81
const mass : Real = 2.0
def weight : Real := gravity * mass
"""

WEIGHT_WRONG_ARITY = """module Kinematics

const gravity : Real = 9.81
const mass : Real = 2.0
def weight : Real := sqrt(gravity, mass)
"""

WEIGHT_STILL_BROKEN = """module Kinematics

const gravity : Real = 9.81
const mass : Real = 2.0
def weight : Real := sqrt(gravity
"""

COIN_REFERENCE = """module CoinPrior

param theta : Probability
prior theta ~ Beta(alpha := 1, beta := 1)
"""

COIN_WRONG_ROLES = """module CoinPrior

param theta : Probability
prior theta ~ Beta(a := 1, b := 1)
"""


def weight_task(task_id: str = "weight", **kw) -> ArenaTask:
    return ArenaTask(
        task_id=task_id,
        prompt="State the weight of a 2 kg mass under standard gravity.",
        reference_source=WEIGHT_REFERENCE,
        description="two constants and one definition",
        **kw,
    )


COIN_TASK = ArenaTask(
    task_id="coin_prior",
    prompt="Give theta a uniform Beta prior.",
    reference_source=COIN_REFERENCE,
    description="a Beta prior with both roles named",
)


# ---------------------------------------------------------------------------
# The clean path
# ---------------------------------------------------------------------------


def test_a_correct_first_attempt_needs_no_repair_and_routes_to_positive():
    task = weight_task()
    model = ScriptedModel({"weight": ScriptedTurns(generation=WEIGHT_REFERENCE)})
    outcome = run_arena(task, model, CONFIG)

    assert outcome.status is ArenaStatus.FIRST_ATTEMPT_PASS
    assert outcome.repair_attempts == 0
    assert model.call_counts()["repair"] == {}
    assert outcome.diagnostic is None
    assert outcome.first_attempt.canonical_hash == task.reference_hash()
    assert outcome.route().store is MemoryStoreKind.POSITIVE


# ---------------------------------------------------------------------------
# The one-repair path
# ---------------------------------------------------------------------------


@pytest.fixture
def repaired_run():
    model = ScriptedModel(
        {"coin_prior": ScriptedTurns(generation=COIN_WRONG_ROLES, repair=COIN_REFERENCE)}
    )
    ledger = InMemoryLedger()
    outcome = run_arena(COIN_TASK, model, CONFIG, ledger=ledger)
    return outcome, model, ledger


def test_the_repaired_run_ends_in_a_verified_pass(repaired_run):
    outcome, _, _ = repaired_run
    assert outcome.status is ArenaStatus.REPAIRED_PASS
    assert outcome.final_verification.outcome is VerifierOutcome.PASS
    assert outcome.repair_attempt is not None
    assert outcome.repair_attempt.canonical_hash == COIN_TASK.reference_hash()


def test_the_initial_failure_is_preserved_rather_than_overwritten(repaired_run):
    """A repaired episode still shows what the first attempt actually was."""
    outcome, _, _ = repaired_run
    assert outcome.first_attempt.text == COIN_WRONG_ROLES
    assert outcome.first_attempt.verification.outcome is VerifierOutcome.INCONCLUSIVE
    # Unknown role labels parse and fail the role check: two different facets, and the
    # record keeps them apart rather than reporting one parse failure.
    assert outcome.first_attempt.verification.parsed is True
    assert outcome.first_attempt.verification.checked is False
    assert outcome.first_attempt.canonical_hash is None
    assert outcome.first_attempt.text != outcome.repair_attempt.text


def test_exactly_one_repair_is_performed(repaired_run):
    outcome, model, _ = repaired_run
    assert outcome.repair_attempts == 1
    assert model.call_counts()["repair"] == {"coin_prior": 1}
    assert model.call_counts()["generate"] == {"coin_prior": 1}


def test_the_diagnostic_is_structured_and_attributed(repaired_run):
    outcome, _, _ = repaired_run
    assert outcome.diagnostic is not None
    assert "HML-T415" in outcome.diagnostic.codes
    assert outcome.diagnostic.primary_skill_id == "syntax.role_label"


def test_the_repair_is_verified_by_something_that_is_not_the_model(repaired_run):
    outcome, model, _ = repaired_run
    assert outcome.verifier_name == "canonical_form"
    assert outcome.verifier_name != model.name
    # The verdict is a hash comparison against the reference, not a model judgement.
    assert outcome.repair_attempt.verification.detail.startswith("canonical form matches")


def test_the_verifier_may_not_be_the_model_itself():
    model = ScriptedModel({"weight": ScriptedTurns(generation=WEIGHT_REFERENCE)})
    with pytest.raises(ValueError, match="independent"):
        run_arena(weight_task(), model, CONFIG, verifier=model)  # type: ignore[arg-type]


def test_every_hash_and_every_version_is_present(repaired_run):
    outcome, _, _ = repaired_run
    doc = outcome.to_dict()
    assert doc["reference_hash"] and len(doc["reference_hash"]) == 64
    assert doc["first_attempt"]["exact_hash"] and doc["repair_attempt"]["exact_hash"]
    assert doc["repair_attempt"]["canonical_hash"] == COIN_TASK.reference_hash()
    assert doc["state_fingerprint"] == STATE.fingerprint()
    assert doc["state"] == STATE.to_dict()
    assert all(doc["state"].values())


def test_no_token_cost_is_fabricated_when_the_adapter_reports_none(repaired_run):
    outcome, _, _ = repaired_run
    assert isinstance(outcome.token_cost, Unavailable)
    assert isinstance(outcome.latency, Unavailable)
    with pytest.raises(TypeError):
        float(outcome.token_cost)
    assert outcome.to_dict()["token_cost"]["UNAVAILABLE"] is True


def test_the_ledger_replays_the_episode_from_events_alone(repaired_run):
    outcome, _, ledger = repaired_run
    names = [e.name for e in ledger.events()]
    assert names == [
        EventName.TASK_STARTED,
        EventName.GENERATION_RECEIVED,
        EventName.VERIFICATION_COMPLETED,
        EventName.DIAGNOSTIC_ISSUED,
        EventName.REPAIR_REQUESTED,
        EventName.REPAIR_RECEIVED,
        EventName.VERIFICATION_COMPLETED,
        EventName.EPISODE_SEALED,
    ]
    assert replay(ledger.events()) == outcome.replay_projection()


def test_the_episode_is_immutable(repaired_run):
    outcome, _, _ = repaired_run
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.status = ArenaStatus.FIRST_ATTEMPT_PASS  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.first_attempt.text = "rewritten"  # type: ignore[misc]


def test_the_repaired_episode_routes_to_repair_memory(repaired_run):
    outcome, _, _ = repaired_run
    decision = outcome.route()
    assert decision.store is MemoryStoreKind.REPAIR
    assert decision.training_eligible

    bank = MemoryBank()
    record = build_record(outcome.episode_id, outcome.routing_facts())
    assert bank.admit(record).accepted
    assert len(bank.records(MemoryStoreKind.REPAIR, H3)) == 1
    assert bank.training_batch(H3)[0].episode_id == outcome.episode_id


# ---------------------------------------------------------------------------
# The failed-repair path
# ---------------------------------------------------------------------------


@pytest.fixture
def failed_run():
    task = weight_task("weight_unfixable")
    model = ScriptedModel(
        {
            "weight_unfixable": ScriptedTurns(
                generation=WEIGHT_WRONG_ARITY, repair=WEIGHT_STILL_BROKEN
            )
        }
    )
    return run_arena(task, model, CONFIG), model


def test_a_failed_repair_is_recorded_as_a_failed_repair(failed_run):
    outcome, model = failed_run
    assert outcome.status is ArenaStatus.REPAIR_FAILED
    assert outcome.repair_attempts == 1
    assert model.call_counts()["repair"] == {"weight_unfixable": 1}
    assert "HML-T426" in outcome.diagnostic.codes
    assert outcome.first_attempt.verification.parsed is True  # wrong arity still parses


def test_a_failed_repair_routes_to_quarantine_and_is_never_training_eligible(failed_run):
    outcome, _ = failed_run
    decision = outcome.route()
    assert decision.store is MemoryStoreKind.QUARANTINE
    assert QuarantineReason.INCONCLUSIVE_VERIFICATION in decision.quarantine_reasons
    assert not decision.training_eligible

    bank = MemoryBank()
    bank.admit(build_record(outcome.episode_id, outcome.routing_facts()))
    assert bank.training_batch(H3) == ()
    assert bank.quarantined_ids(H3) == (outcome.episode_id,)


def test_a_second_repair_is_refused_by_the_adapter(failed_run):
    _, model = failed_run
    task = weight_task("weight_unfixable")
    with pytest.raises(RepairBudgetExceeded, match="unattributable"):
        model.repair(task, WEIGHT_WRONG_ARITY, "another diagnostic")


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


def test_an_unsupported_backend_does_not_become_a_failure():
    task = weight_task("weight_probed", backend_probes=("lean", "stan", "sympy", "not_a_backend"))
    model = ScriptedModel({"weight_probed": ScriptedTurns(generation=WEIGHT_REFERENCE)})
    outcome = run_arena(task, model, CONFIG)

    assert {r.target for r in outcome.backend_reports} == {
        "lean",
        "stan",
        "sympy",
        "not_a_backend",
    }
    missing = [r for r in outcome.backend_reports if not r.available]
    assert missing and missing[0].target == "not_a_backend"

    # The verdict, the status and the routing are all unchanged by any of it.
    assert outcome.status is ArenaStatus.FIRST_ATTEMPT_PASS
    facts = outcome.routing_facts()
    assert facts.unsupported_backend_dependency is False
    assert facts.semantic_loss is False
    assert outcome.route().store is MemoryStoreKind.POSITIVE


def test_backend_loss_is_recorded_even_though_it_changes_nothing():
    task = weight_task("weight_lossy", backend_probes=("lean",))
    model = ScriptedModel({"weight_lossy": ScriptedTurns(generation=WEIGHT_REFERENCE)})
    outcome = run_arena(task, model, CONFIG)
    lean = next(r for r in outcome.backend_reports if r.target == "lean")
    assert isinstance(lean.faithful, bool)
    sealed = [e for e in outcome.events if e.name is EventName.BACKEND_SUPPORT_PROBED]
    assert sealed and "never changes the verdict" in sealed[0].payload["note"]


# ---------------------------------------------------------------------------
# Offline by construction
# ---------------------------------------------------------------------------


def test_a_task_with_a_broken_reference_is_rejected_before_any_model_call():
    task = ArenaTask("bad", "prompt", "module X\n\nconst a : Real =\n")
    model = ScriptedModel({"bad": ScriptedTurns(generation=WEIGHT_REFERENCE)})
    with pytest.raises(ValueError, match="reference that does not compile"):
        run_arena(task, model, CONFIG)
    assert model.call_counts()["generate"] == {}


def test_the_scripted_adapter_declares_itself_not_live():
    model = ScriptedModel({})
    assert model.live is False


def test_the_arena_config_requires_a_typed_hypothesis():
    with pytest.raises(TypeError, match="Hypothesis"):
        ArenaConfig(hypothesis="H3", state=STATE)  # type: ignore[arg-type]


def test_the_verifier_reports_inconclusive_rather_than_wrong_when_nothing_compiles():
    result = CanonicalFormVerifier().verify(weight_task(), "module X\n\nconst a : Real =\n")
    assert result.outcome is VerifierOutcome.INCONCLUSIVE
    assert result.parsed is False
    assert result.checked is False
    assert "unanswered rather than answered no" in result.detail


def test_parsing_and_checking_are_measured_separately():
    """A wrong-arity call parses. Calling it a parse failure blames the wrong thing."""
    result = CanonicalFormVerifier().verify(weight_task(), WEIGHT_WRONG_ARITY)
    assert result.parsed is True
    assert result.checked is False
    assert result.diagnostic_codes == ("HML-T426",)
    # The stage record names the stage exactly, rather than "resolution or type
    # checking" -- those are two different failures and were being reported as one.
    assert result.stages is not None
    assert result.stages.terminal.value == "RESOLVED_TYPE_FAILED"
    assert result.stages.resolution_status.value == "PASS"
    assert result.stages.type_status.value == "FAIL"
    assert "RESOLVED_TYPE_FAILED" in result.detail


def test_an_unresolved_name_is_distinguished_from_a_type_error():
    """Both parse. They are different defects and the arena now says which."""
    result = CanonicalFormVerifier().verify(
        weight_task(), "module X\n\ndef y : Real := nosuchname + 1.0\n"
    )
    assert result.parsed is True
    assert result.stages is not None
    assert result.stages.terminal.value == "PARSE_PASSED_RESOLUTION_FAILED"
    assert result.stages.resolution_status.value == "FAIL"
    assert result.stages.type_status.value == "NOT_RUN"


def test_a_verification_may_not_disagree_with_its_own_stage_record():
    from hamiltonian_lang.improvement.episodes import classify_stages
    from hamiltonian_lang.improvement.runner import ArenaVerification

    stages = classify_stages("module X\n\nconst a : Real =\n")
    assert stages.parsed is False
    with pytest.raises(ValueError, match="disagrees with its stage record"):
        ArenaVerification(
            verifier="canonical_form",
            outcome=VerifierOutcome.INCONCLUSIVE,
            parsed=True,
            checked=False,
            canonical_hash=None,
            detail="",
            stages=stages,
        )


def test_a_verifier_status_from_the_verification_layer_maps_onto_a_routing_outcome():
    """The two vocabularies are bound by name, so a rename fails loudly."""
    from hamiltonian_lang.improvement.memory import (
        UnknownVerifierStatus,
        verifier_outcome_from_status,
    )

    assert verifier_outcome_from_status("SUPPORTED_AND_VERIFIED") is VerifierOutcome.PASS
    assert verifier_outcome_from_status("SUPPORTED_AND_FAILED") is VerifierOutcome.FAIL
    assert verifier_outcome_from_status("INVALID") is VerifierOutcome.FAIL
    assert verifier_outcome_from_status("UNSUPPORTED") is VerifierOutcome.UNSUPPORTED
    assert verifier_outcome_from_status("INCONCLUSIVE") is VerifierOutcome.INCONCLUSIVE
    with pytest.raises(UnknownVerifierStatus, match="semantic_loss"):
        verifier_outcome_from_status("SEMANTIC_LOSS")
    with pytest.raises(UnknownVerifierStatus, match="no routing rule"):
        verifier_outcome_from_status("PROBABLY_FINE")


def test_the_status_names_this_router_maps_are_the_ones_the_verification_layer_emits():
    """If the verification layer adds or renames a status, this test names it."""
    from hamiltonian_lang.improvement.memory import verifier_outcome_from_status
    from hamiltonian_lang.improvement.verification import VerifierStatus

    unmapped = []
    for status in VerifierStatus:
        try:
            verifier_outcome_from_status(status.value)
        except Exception:  # SEMANTIC_LOSS is handled by a routing flag, not an outcome
            if status.value.upper() != "SEMANTIC_LOSS":
                unmapped.append(status.value)
    assert not unmapped, f"verification statuses with no routing rule: {unmapped}"


#: No module in the package may import a model provider. This is the whole-package ban:
#: nothing in the improvement subsystem calls a model, on any code path.
_PROVIDER_MODULES = {"ollama", "openai", "anthropic", "torch", "transformers", "vllm"}

#: The network and shell ban applies to the modules that drive the arena. It cannot apply
#: to the whole package: ``verification`` runs external checkers (Lean, a SymPy
#: subprocess) and needs ``subprocess`` to do it.
_NETWORK_MODULES = {"urllib", "requests", "httpx", "http", "socket", "subprocess", "smtplib"}

_ARENA_MODULES = ("state.py", "memory.py", "skills.py", "controller.py", "evidence.py", "runner.py")


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add((node.module or "").split(".")[0])
    return names


def test_no_module_in_the_package_can_reach_a_model_provider():
    """Offline is a property of the imports, not of the intention."""
    offenders = [
        f"{p.name}: {sorted(_imports(p) & _PROVIDER_MODULES)}"
        for p in sorted(PACKAGE.glob("*.py"))
        if _imports(p) & _PROVIDER_MODULES
    ]
    assert not offenders, f"a model provider is imported by {offenders}"


def test_the_arena_modules_reach_neither_the_network_nor_a_shell():
    offenders = [
        f"{name}: {sorted(_imports(PACKAGE / name) & _NETWORK_MODULES)}"
        for name in _ARENA_MODULES
        if _imports(PACKAGE / name) & _NETWORK_MODULES
    ]
    assert not offenders, f"arena modules import {offenders}"
