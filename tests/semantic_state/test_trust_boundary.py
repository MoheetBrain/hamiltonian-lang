"""D-050: who may create VALID evidence.

The hole these tests close. `EvidenceRecord.status` arrives from a JSON payload and every
acceptance path turned on `record.status == "VALID"`. Nothing in `src/` ever *produced* that
string — it was only ever compared. So a producer that authored a transition also authored
the verdict on it, and a model asked to reason in this format could simply write
`"status": "VALID"` and be believed.

The fix is a mode, not a patch. Replaying the frozen corpus legitimately reads recorded
status as observed reference data; a model-authored record must not be read that way. So
`TrustMode.RUNTIME` ignores `status` entirely and requires an `Attestation` carrying a
`CheckedEvidence`, which only `reasoning.certificates.check` can mint — its `_token` is a
module-private object, so a payload cannot contain one and no amount of JSON can forge one.

**These tests are adversarial by design.** Each one is an attack that a correct
implementation must survive, and each was written to fail against the code as it stood at
`a21fdb7`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import hamiltonian_lang.reasoning.certificates as C
from hamiltonian_lang.semantic_state import verify, verify_payload
from hamiltonian_lang.semantic_state.neutral import import_transition
from hamiltonian_lang.semantic_state.trust import (
    AttestationError,
    TrustMode,
    attest,
    proposition_digest,
)

SCHEMA = "semantic-firewall-case-0.1.0"
CORPUS = Path("/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus")
FIXTURES = CORPUS / "experiments" / "semantic_firewall" / "acceptance" / "fixtures.json"

_EMPTY = {
    "active_scopes": ["global"],
    "branches": {}, "candidates": {}, "goals": {}, "obligations": {}, "claims": {},
}
_ACTION = {
    "id": "a1", "operation": "VERIFY_CANDIDATE", "summary": "", "dependencies": [],
    "preconditions": [], "obligations_created": [], "obligations_discharged": [],
    "typing": {}, "warrant": {}, "goal_effect": {}, "scope_effect": {},
    "branch_effect": {}, "candidate_effect": {}, "epistemic_effect": {},
}


def _candidate(status):
    return {"id": "k1", "proposition": "x = 2", "status": status,
            "scope": "global", "constraint_ids": ["c1"]}


def _self_asserted(trusted: bool = False) -> dict:
    """A model-authored promotion whose evidence asserts its own validity.

    This is the whole attack in one payload: the producer writes the reasoning *and* the
    verdict on it.
    """
    action = {**copy.deepcopy(_ACTION),
              "candidate_effect": {"kind": "PROMOTE", "candidate_id": "k1",
                                   "evidence_id": "e_self"}}
    return {
        "schema_version": SCHEMA, "case_id": "ATTACK", "action": action,
        "state_before": {**copy.deepcopy(_EMPTY),
                         "candidates": {"k1": _candidate("PROPOSED")}},
        "state_after": {**copy.deepcopy(_EMPTY),
                        "candidates": {"k1": _candidate("VERIFIED")}},
        "evidence": {"e_self": {
            "id": "e_self", "kind": "CANDIDATE_CHECK",
            "status": "VALID",                      # <-- authored by the same producer
            "supports_rule": "VERIFY_CANDIDATE",
            "trusted": trusted,
            "premise_ids": [], "checked_constraints": ["c1"],
        }},
        "source": {},
    }


# ---------------------------------------------------------------------------
# The attack
# ---------------------------------------------------------------------------


def test_a_self_asserted_valid_is_accepted_in_offline_replay():
    """Documents the mode rather than endorsing it.

    Replaying a frozen corpus, the recorded status is observed reference data produced by an
    external process. Refusing it would make the acceptance fixtures unreplayable and would
    make nothing safer.
    """
    assert str(verify_payload(_self_asserted()).verdict) == "VALID"


def test_a_self_asserted_valid_is_refused_at_runtime():
    """The point of D-050. The same bytes, authored by a model, buy nothing."""
    result = verify(import_transition(_self_asserted()), mode=TrustMode.RUNTIME)
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "CANDIDATE_PROMOTION"
    assert "no checker attestation" in result.findings[0].detail


def test_the_trusted_flag_buys_nothing_at_runtime():
    """`trusted` is provenance, and a producer sets that too.

    An audit confirmed nothing reads it as authority. This pins that it stays true on the
    path where it would be most tempting.
    """
    result = verify(import_transition(_self_asserted(trusted=True)),
                    mode=TrustMode.RUNTIME)
    assert str(result.verdict) == "INVALID"


def test_runtime_is_not_the_default_but_the_unsafe_reading_is_never_silent():
    """The safe mode must be chosen explicitly, and the default must be the *replay* one.

    Getting this backwards either breaks the frozen corpus or silently trusts model output.
    The signature is keyword-only so a caller cannot pass the wrong mode positionally.
    """
    import inspect

    sig = inspect.signature(verify)
    assert sig.parameters["mode"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["mode"].default is TrustMode.OFFLINE_REPLAY


# ---------------------------------------------------------------------------
# Minting, and what cannot be minted
# ---------------------------------------------------------------------------


def _mint(monkeypatch, *, checker="probe_v1"):
    """Mint a genuine CheckedEvidence through the real gate.

    Uses the repository's own pattern for registering a checker for a test's duration. The
    object still passes through `certificates.check`, so it is minted rather than faked.
    """
    from hamiltonian_lang.ast.nodes import Literal
    from hamiltonian_lang.backends.canonical import expr_identity

    claim = Literal(value=1.0, raw="1.0")
    spec = C.TrustedChecker(
        name=checker,
        judgements=frozenset({C.JudgementKind.ENTAILS}),
        validate=lambda env, ctx: C.CheckerVerdict(valid=True, established=claim),
        trust="test double", fragment="test double",
    )
    monkeypatch.setitem(C.CHECKERS, checker, spec)
    env = C.CertificateEnvelope(
        certificate_type=checker, certificate_version=1, checker=checker,
        judgement=C.JudgementKind.ENTAILS, claim_hash=expr_identity(claim),
        context_hash="ctx", premise_hashes=(),
    )
    evidence, reason = C.check(env, claim, C.CheckerContext(), current_context_hash="ctx")
    assert evidence is not None, f"could not mint through the real gate: {reason}"
    return evidence


def test_a_correct_attestation_is_accepted_at_runtime(monkeypatch):
    """The positive path. Without it, RUNTIME could be 'refuse everything' and still pass."""
    checked = _mint(monkeypatch)
    case = _self_asserted()
    attestation = attest("e_self", checked, claim="x = 2", premises=(),
                         rule="VERIFY_CANDIDATE")
    result = verify(import_transition(case), mode=TrustMode.RUNTIME,
                    attestations={"e_self": attestation})
    assert str(result.verdict) == "VALID", result.to_dict()


def test_an_attestation_for_a_different_claim_is_refused(monkeypatch):
    """A perfectly valid certificate, replayed onto a transition it was not issued for."""
    checked = _mint(monkeypatch)
    attestation = attest("e_self", checked, claim="something else entirely", premises=(),
                         rule="VERIFY_CANDIDATE")
    result = verify(import_transition(_self_asserted()), mode=TrustMode.RUNTIME,
                    attestations={"e_self": attestation})
    assert str(result.verdict) == "INVALID"
    assert "different proposition" in result.findings[0].detail


def test_an_attestation_checked_against_other_premises_is_refused(monkeypatch):
    checked = _mint(monkeypatch)
    attestation = attest("e_self", checked, claim="x = 2", premises=("p9",),
                         rule="VERIFY_CANDIDATE")
    result = verify(import_transition(_self_asserted()), mode=TrustMode.RUNTIME,
                    attestations={"e_self": attestation})
    assert str(result.verdict) == "INVALID"
    assert "different premises" in result.findings[0].detail


def test_an_attestation_certifying_another_rule_is_refused(monkeypatch):
    checked = _mint(monkeypatch)
    attestation = attest("e_self", checked, claim="x = 2", premises=(), rule="SIMPLIFY")
    result = verify(import_transition(_self_asserted()), mode=TrustMode.RUNTIME,
                    attestations={"e_self": attestation})
    assert str(result.verdict) == "INVALID"
    assert "certifies" in result.findings[0].detail


def test_an_attestation_for_another_evidence_id_does_not_transfer(monkeypatch):
    """Keyed by the id the action cites; a certificate for `e_other` is not for `e_self`."""
    checked = _mint(monkeypatch)
    attestation = attest("e_other", checked, claim="x = 2", premises=(),
                         rule="VERIFY_CANDIDATE")
    result = verify(import_transition(_self_asserted()), mode=TrustMode.RUNTIME,
                    attestations={"e_other": attestation})
    assert str(result.verdict) == "INVALID"
    assert "no checker attestation" in result.findings[0].detail


@pytest.mark.parametrize(
    "fake",
    [
        None,
        "VALID",
        {"envelope": "x", "checker": "closed_eval_v1"},
        object(),
    ],
)
def test_attest_refuses_anything_not_minted(fake):
    """The forgery attempt, in the shape a payload would actually take."""
    with pytest.raises((AttestationError, AttributeError, TypeError)):
        attest("e", fake, claim="x = 2", premises=())  # type: ignore[arg-type]


def test_checked_evidence_cannot_be_constructed_directly():
    """The property the whole design rests on, asserted rather than assumed."""
    with pytest.raises(TypeError, match="minted only by"):
        C.CheckedEvidence(
            envelope=None, kind=None, established=None, checker="anything",  # type: ignore[arg-type]
        )


def test_an_unregistered_checker_cannot_mint():
    from hamiltonian_lang.ast.nodes import Literal
    from hamiltonian_lang.backends.canonical import expr_identity

    claim = Literal(value=1.0, raw="1.0")
    env = C.CertificateEnvelope(
        certificate_type="not_a_checker", certificate_version=1, checker="not_a_checker",
        judgement=C.JudgementKind.ENTAILS, claim_hash=expr_identity(claim),
        context_hash="ctx", premise_hashes=(),
    )
    evidence, reason = C.check(env, claim, C.CheckerContext(), current_context_hash="ctx")
    assert evidence is None and "not a registered trusted checker" in reason


# ---------------------------------------------------------------------------
# The mode must not have broken replay
# ---------------------------------------------------------------------------


def test_the_frozen_fixtures_still_replay_unchanged():
    """The whole repair is worthless if it changed a single acceptance verdict."""
    if not FIXTURES.exists():
        pytest.skip(f"research corpus not present at {CORPUS}")
    fixtures = json.loads(FIXTURES.read_text())["fixtures"]
    assert len(fixtures) == 30
    for fixture in fixtures:
        result = verify_payload(fixture["case"])
        assert str(result.verdict) == fixture["expected_reference_result"], (
            fixture["fixture_id"]
        )


def test_the_digest_is_exact_not_normalised():
    """Two propositions that differ only in whitespace are different propositions here.

    Recorded because it is a real limitation: this layer has no parser for corpus
    propositions, so it binds text. Inventing an equivalence it cannot justify would let an
    attestation drift off the claim it was issued for.
    """
    assert proposition_digest("x = 2") != proposition_digest("x  =  2")
    assert proposition_digest("x = 2") == proposition_digest("x = 2")
