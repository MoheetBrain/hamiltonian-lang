"""The ``VERIFIED`` conjunction, tested one clause at a time.

``VERIFIED`` is worth nothing unless each of its four conditions can independently
withhold it. These tests remove one condition at a time and assert the verdict changes.
The most important of them is the ``UNSUPPORTED`` clause: if that ever stopped blocking,
every gap in the implemented subset would silently become a pass, and the endpoint would
lose the only property that makes it worth measuring.
"""

from __future__ import annotations

from hamiltonian_lang.verification.obligations import (
    GlobalVerdict,
    ObligationStatus,
    verify_source,
)
from hamiltonian_lang.verification.obligations.engine import _verdict

VERIFIABLE = "module M\nvar x : Real\nrequire x >= 0\nprove (x + 1)^2 = x^2 + 2 * x + 1\n"


def test_the_baseline_module_verifies() -> None:
    outcome = verify_source(VERIFIABLE)
    assert outcome.verdict is GlobalVerdict.VERIFIED
    assert outcome.verified and outcome.substantive
    assert all(r.discharged for r in outcome.records)


def test_a_compiler_error_blocks_and_no_obligation_is_reported() -> None:
    outcome = verify_source("module M\nvar x : Real\nrequire x > nonexistent\n")
    assert outcome.verdict is GlobalVerdict.INVALID
    assert outcome.records == ()
    assert outcome.notes


def test_a_refuted_obligation_blocks() -> None:
    outcome = verify_source(VERIFIABLE + "require 1 = 2\n")
    assert outcome.verdict is GlobalVerdict.DISPROVED
    assert outcome.first_failure() is not None


def test_an_unsupported_obligation_blocks_just_as_firmly_as_a_failure() -> None:
    outcome = verify_source(VERIFIABLE + "prove exists y : Real . forall z : Real . y > z\n")
    assert outcome.verdict is GlobalVerdict.UNSUPPORTED
    assert not outcome.verified
    assert any(r.status is ObligationStatus.UNSUPPORTED for r in outcome.records)


def test_an_undecided_obligation_blocks() -> None:
    outcome = verify_source(VERIFIABLE + "prove abs(sin(x)) <= 1\n")
    assert outcome.verdict is GlobalVerdict.INCONCLUSIVE
    assert not outcome.verified


def test_semantic_loss_blocks_even_when_every_obligation_is_discharged() -> None:
    """A view that claims to *be* the semantic object must not have lost anything."""
    from hamiltonian_lang.verification.obligations.records import SemanticLossRecord

    loss = SemanticLossRecord("hml", "round trip", "the content hash changed", "weakened")
    verdict, detail = _verdict(True, (), [loss])
    assert verdict is GlobalVerdict.SEMANTIC_LOSS
    assert "loss" in detail


def test_lowering_loss_is_recorded_but_does_not_block() -> None:
    """Lean and Stan lose things by construction; blocking on that measures the backend."""
    outcome = verify_source(VERIFIABLE)
    assert outcome.verdict is GlobalVerdict.VERIFIED
    assert outcome.lowering_loss, "the lowering probe should still have run"
    assert all(loss.target != "hml" for loss in outcome.lowering_loss)


def test_unsupported_outranks_inconclusive_in_the_report() -> None:
    """The missing capability is the more informative of the two, so it is reported."""
    outcome = verify_source(
        "module M\nvar x : Real\n"
        "prove abs(sin(x)) <= 1\n"
        "prove exists y : Real . forall z : Real . y > z\n"
    )
    assert outcome.verdict is GlobalVerdict.UNSUPPORTED


def test_the_verdict_is_deterministic_and_the_evidence_reproducible() -> None:
    first = verify_source(VERIFIABLE)
    second = verify_source(VERIFIABLE)
    assert first.verdict is second.verdict
    assert first.evidence_digest() == second.evidence_digest()
    assert [r.obligation_id for r in first.records] == [r.obligation_id for r in second.records]


def test_obligation_ids_are_content_addressed_and_stable() -> None:
    outcome = verify_source(VERIFIABLE)
    ids = [r.obligation_id for r in outcome.records]
    assert len(set(ids)) == len(ids)
    assert all(r.obligation_id.startswith("OBL-") for r in outcome.records)


def test_every_record_carries_the_full_required_schema() -> None:
    outcome = verify_source(VERIFIABLE)
    for record in outcome.records:
        payload = record.to_dict()
        assert payload["obligation_id"]
        assert payload["span"]["file"]
        assert payload["class"]
        assert payload["checker"] and payload["checker_version"]
        assert payload["status"]
        assert "evidence" in payload
        assert "witness" in payload
        assert "dependencies" in payload


def test_dependencies_are_recorded_for_a_derived_obligation() -> None:
    """The joint-feasibility obligation rests on the individual constraints; say so."""
    outcome = verify_source("module M\nvar x : Real\nrequire x >= 0\nrequire x <= 10\n")
    derived = [r for r in outcome.records if r.origin == "derived" and r.dependencies]
    assert derived, "the feasibility obligation should depend on its constraints"
    known = {r.obligation_id for r in outcome.records}
    for record in derived:
        assert set(record.dependencies) <= known


def test_an_empty_module_is_verified_but_never_substantive() -> None:
    """Vacuity is allowed by soundness and refused by the task filter, not hidden."""
    outcome = verify_source("module Empty\n")
    assert outcome.verdict is GlobalVerdict.VERIFIED
    assert not outcome.substantive
