"""D-060: obligation discharge was outside the evidence-authority seam.

``_check_obligations`` documented the rule in its own first line — "discharged ones must
name their evidence" — and no code read the evidence. Measured at `136cdb9`, a discharge
citing a **nonexistent** record, a **REFUTED** one, or one supporting a **different rule**
was ``VALID`` in both trust modes, and at ``RUNTIME`` with no attestation, while the
identical citation at the promotion, join, warrant and epistemic sites was refused. Found by
enumerating the sites that consume evidence and checking each against the authority seam,
rather than by reading the seam and asking what reaches it.

**What this repair deliberately does not do.** It does not make evidence *required*. 486 of
the 487 obligation discharges in the corpus name no evidence at all — they are bare ids in
`data/derived/gold125_ontology_v1/` — so requiring it would redefine the semantics of a
frozen body of data rather than close a hole. The rule implemented is narrower and provable:
**a citation that is made must be honoured.** Citation without checking is worse than no
citation, because it puts something that looks like evidence in the record.

The residual gap is stated as a known limitation, not hidden: a producer can still discharge
a mandatory obligation by omitting the field.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.semantic_state import model as M
from hamiltonian_lang.semantic_state import neutral, verify_replay, verify_runtime
from hamiltonian_lang.semantic_state.neutral import import_transition

VALID_EVIDENCE = {"id": "e1", "kind": "PROOF", "status": "VALID",
                  "supports_rule": "DERIVE", "payload": {}}


def _payload(entry, evidence: dict | None = None) -> dict:
    p0 = M.Claim(id="p0", proposition="n > 0", status=M.ClaimStatus.GIVEN, scope="global",
                 domain="Natural")
    c1 = M.Claim(id="c1", proposition="q", status=M.ClaimStatus.DERIVED, scope="global",
                 domain="Proposition", dependencies=("p0",))
    ob = M.Obligation(id="ob1", proposition="the denominator is non-zero",
                      status=M.ObligationState.OPEN, mandatory=True, origin="test")
    done = M.Obligation(id="ob1", proposition="the denominator is non-zero",
                        status=M.ObligationState.DISCHARGED, mandatory=True, origin="test")
    action = M.Action(id="a0", operation="DERIVE", summary="q", output_id="c1",
                      dependencies=("p0",),
                      typing={"input_domains": {"p0": "Integer"},
                              "output_domain": "Proposition"},
                      obligations_discharged=(entry,))
    t = M.Transition(
        case_id="D060", action=action,
        state_before=M.SemanticState(claims={"p0": p0}, obligations={"ob1": ob},
                                     active_scopes=("global",)),
        state_after=M.SemanticState(claims={"p0": p0, "c1": c1},
                                    obligations={"ob1": done},
                                    active_scopes=("global",)),
        evidence={}, schema_version="semantic-firewall-case-0.1.0",
        source={"origin": "synthetic", "rationale": "D-060"})
    payload = neutral.export_transition(t)
    payload["evidence"] = evidence or {}
    return payload


def _verdict(payload: dict, runtime: bool = False) -> tuple[str, str | None]:
    t = import_transition(payload)
    r = verify_runtime(t) if runtime else verify_replay(t)
    return str(r.verdict), r.error_class


def test_a_discharge_naming_no_evidence_is_still_accepted():
    """The corpus shape, pinned so the repair's scope cannot drift silently.

    If this ever starts failing, 486 corpus transitions have been invalidated and that is a
    decision for whoever owns the corpus, not a passing change.
    """
    assert _verdict(_payload("ob1")) == ("VALID", None)


@pytest.mark.parametrize("runtime", [False, True], ids=["replay", "runtime"])
def test_a_discharge_citing_evidence_that_does_not_exist_is_refused(runtime):
    payload = _payload({"id": "ob1", "evidence_id": "e_missing"})
    assert _verdict(payload, runtime) == ("INVALID", "OBLIGATION_DROP")


@pytest.mark.parametrize("runtime", [False, True], ids=["replay", "runtime"])
def test_a_discharge_citing_refuted_evidence_is_refused(runtime):
    refuted = {"e1": {**VALID_EVIDENCE, "status": "REFUTED"}}
    payload = _payload({"id": "ob1", "evidence_id": "e1"}, refuted)
    assert _verdict(payload, runtime) == ("INVALID", "OBLIGATION_DROP")


def test_the_obligation_records_own_discharge_evidence_id_is_honoured():
    """The citation can come from the record as well as from the action entry.

    ``Obligation.discharge_evidence_id`` exists in the schema; honouring the action's entry
    but not the record's would leave exactly the same hole one field to the left.
    """
    payload = _payload("ob1")
    for state in ("state_before", "state_after"):
        payload[state]["obligations"]["ob1"]["discharge_evidence_id"] = "e_missing"
    assert _verdict(payload) == ("INVALID", "OBLIGATION_DROP")


def test_self_authored_evidence_does_not_discharge_an_obligation_at_runtime():
    """The trust boundary, at the site that did not have one.

    In ``OFFLINE_REPLAY`` the recorded status is observed reference data and is read as
    such. At ``RUNTIME`` the author of the record may be the party that benefits from the
    verdict, so a ``VALID`` it wrote itself is worth nothing without an attestation
    (D-050).
    """
    payload = _payload({"id": "ob1", "evidence_id": "e1"}, {"e1": dict(VALID_EVIDENCE)})
    assert _verdict(payload, runtime=False) == ("VALID", None)
    assert _verdict(payload, runtime=True) == ("INVALID", "OBLIGATION_DROP")
