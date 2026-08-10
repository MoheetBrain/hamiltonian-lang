"""The frame condition and dependency-scoped unknowns (D-049).

Every case here was a **passing** transition at `7c9137a`. They come from an independent
audit that attacked the verifier instead of reading its tests, and each one reproduced
against pristine production code before it was repaired.

The common cause is worth stating once. The ten invariants all examine what the action
*declares*; none examined whether the resulting state is what applying that declaration
would produce. So every rule was optional — a producer that declined to declare an effect
was not checked, because the checks key on the declaration. A candidate could be promoted
by writing `candidate_effect: {"kind": "NONE"}`, and the entire promotion protocol,
constraint-subset rule included, was skipped.

None of the thirty acceptance fixtures can detect any of this. All thirty are well-formed
records whose delta already matches their action, so a verifier with no frame condition
passes every one of them. That is the second time a 30/30 pass rate concealed real defects,
and the first time they ran in the unsafe direction.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hamiltonian_lang.semantic_state import verify_payload

SCHEMA = "semantic-firewall-case-0.1.0"
CORPUS = Path("/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus")
FIXTURES = CORPUS / "experiments" / "semantic_firewall" / "acceptance" / "fixtures.json"

_EMPTY = {
    "active_scopes": ["global"],
    "branches": {}, "candidates": {}, "goals": {}, "obligations": {}, "claims": {},
}
_ACTION = {
    "id": "a1", "operation": "ASSERT", "summary": "", "dependencies": [],
    "preconditions": [], "obligations_created": [], "obligations_discharged": [],
    "typing": {}, "warrant": {}, "goal_effect": {}, "scope_effect": {},
    "branch_effect": {}, "candidate_effect": {}, "epistemic_effect": {},
}


def _case(action=None, before=None, after=None, evidence=None) -> dict:
    return {
        "schema_version": SCHEMA,
        "case_id": "SYNTHETIC",
        "action": {**copy.deepcopy(_ACTION), **(action or {})},
        "state_before": copy.deepcopy(before or _EMPTY),
        "state_after": copy.deepcopy(after or _EMPTY),
        "evidence": evidence or {},
        "source": {},
    }


def _state(**over) -> dict:
    return {**copy.deepcopy(_EMPTY), **over}


def _claim(cid, proposition="p", status="GIVEN", scope="global", deps=()) -> dict:
    return {"id": cid, "proposition": proposition, "status": status,
            "scope": scope, "dependencies": list(deps)}


# ---------------------------------------------------------------------------
# Claims may not appear, vanish or change without a licensed effect
# ---------------------------------------------------------------------------


def test_a_claim_cannot_materialise_out_of_nothing():
    """The worst of the six, and no forgery is needed for it.

    No evidence, no warrant, no epistemic effect — the claim is simply written into the
    resulting state. Every invariant is keyed on a declaration, and this declares nothing,
    so before the frame condition there was nothing to key on.
    """
    after = _state(claims={"x": _claim("x", "0 = 1", "VERIFIED")})
    result = verify_payload(_case(after=after))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "DEPENDENCY_VIOLATION"


def test_an_existing_premise_cannot_be_rewritten():
    before = _state(claims={"p": _claim("p", "n > 0", "ASSUMED")})
    after = _state(claims={"p": _claim("p", "n < 0", "VERIFIED")})
    assert verify_payload(_case(before=before, after=after)).error_class == (
        "DEPENDENCY_VIOLATION"
    )


def test_a_premise_cannot_be_quietly_dropped():
    """Deleting an inconvenient premise is as good as rewriting it."""
    before = _state(claims={"p": _claim("p")})
    assert verify_payload(_case(before=before)).error_class == "DEPENDENCY_VIOLATION"


def test_the_declared_output_is_the_one_addition_permitted():
    before = _state(claims={"p": _claim("p")})
    after = _state(claims={"p": _claim("p"), "c": _claim("c", "q", "DERIVED", deps=["p"])})
    ok = _case(action={"output_id": "c", "dependencies": ["p"], "summary": "q"},
               before=before, after=after)
    assert str(verify_payload(ok).verdict) == "VALID", verify_payload(ok).to_dict()

    smuggled = copy.deepcopy(ok)
    smuggled["state_after"]["claims"]["extra"] = _claim("extra", "0 = 1", "VERIFIED")
    assert verify_payload(smuggled).error_class == "DEPENDENCY_VIOLATION"


# ---------------------------------------------------------------------------
# The lifecycle cannot be skipped by declining to declare it
# ---------------------------------------------------------------------------


def _candidate(status, cid="k"):
    return {"id": cid, "proposition": "x = 2", "status": status,
            "scope": "global", "constraint_ids": ["c1", "c2"]}


@pytest.mark.parametrize("source", ["PROPOSED", "UNVERIFIED", "REJECTED"])
def test_a_candidate_cannot_be_promoted_by_declaring_no_effect(source):
    """`_check_candidates` returns early unless the effect says PROMOTE.

    So the promotion protocol — including the constraint-subset rule this project treats as
    the whole point of the candidate object — was skipped by writing `NONE`. `REJECTED` is
    the sharpest case: `model.py` documents it as terminal, and it was not.
    """
    before = _state(candidates={"k": _candidate(source)})
    after = _state(candidates={"k": _candidate("VERIFIED")})
    result = verify_payload(_case(before=before, after=after))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "DEPENDENCY_VIOLATION"


def test_declaring_the_effect_hands_the_decision_back_to_the_promotion_rule():
    """The frame licenses a *declared* change; it does not bless it.

    This is what stops the frame condition forbidding the transitions the system exists to
    make. The candidate invariant still refuses, because the evidence checks one of two
    original constraints.
    """
    before = _state(candidates={"k": _candidate("PROPOSED")})
    after = _state(candidates={"k": _candidate("VERIFIED")})
    result = verify_payload(_case(
        action={"operation": "VERIFY_CANDIDATE",
                "candidate_effect": {"kind": "PROMOTE", "candidate_id": "k",
                                     "evidence_id": "e1"}},
        before=before, after=after,
        evidence={"e1": {"id": "e1", "kind": "CANDIDATE_CHECK", "status": "VALID",
                         "supports_rule": "VERIFY_CANDIDATE", "trusted": False,
                         "premise_ids": [], "checked_constraints": ["c1"]}},
    ))
    assert result.error_class == "CANDIDATE_PROMOTION", result.to_dict()


def test_a_mandatory_obligation_cannot_be_deleted():
    before = _state(obligations={
        "o": {"id": "o", "proposition": "d != 0", "status": "OPEN",
              "mandatory": True, "dependencies": []}
    })
    assert verify_payload(_case(before=before)).error_class == "DEPENDENCY_VIOLATION"


def test_a_branch_cannot_be_silently_reclosed():
    def branch(status):
        return {"id": "b", "predicate": "n even", "status": status,
                "scope": "global", "partition_id": "p"}
    before = _state(branches={"b": branch("OPEN")})
    after = _state(branches={"b": branch("CLOSED")})
    assert verify_payload(_case(before=before, after=after)).error_class == (
        "DEPENDENCY_VIOLATION"
    )


# ---------------------------------------------------------------------------
# Unknowns are dependency-scoped
# ---------------------------------------------------------------------------


def _fixtures():
    if not FIXTURES.exists():
        pytest.skip(f"research corpus not present at {CORPUS}")
    return json.loads(FIXTURES.read_text())["fixtures"]


def test_an_unrelated_unknown_no_longer_suppresses_detection():
    """The measured bypass: 10/10 ILLEGAL fixtures suppressed, from three lines of JSON.

    UNRESOLVED is counted as neither accepted nor detected, so this was not a fail-closed
    rule — it was a denial of service against the verifier, available to anyone who could
    append a record nothing cites.
    """
    illegal = [f for f in _fixtures() if f["boundary"] == "ILLEGAL"]
    assert illegal, "no ILLEGAL fixtures found"
    junk = _claim("junk_zzz", "entirely unrelated", "UNKNOWN")
    suppressed = []
    for fixture in illegal:
        case = copy.deepcopy(fixture["case"])
        case["state_before"]["claims"]["junk_zzz"] = junk
        case["state_after"]["claims"]["junk_zzz"] = junk
        if str(verify_payload(case).verdict) != "INVALID":
            suppressed.append(fixture["fixture_id"])
    assert not suppressed, f"detection still suppressed for: {suppressed}"


def test_an_unknown_on_a_record_the_action_cites_still_makes_it_unresolved():
    """Scoping must not have turned the rule off. UNKNOWN is still fail-closed where it counts."""
    before = _state(claims={"p": _claim("p", "n > 0", "UNKNOWN")})
    after = _state(claims={"p": _claim("p", "n > 0", "UNKNOWN"),
                           "c": _claim("c", "q", "DERIVED", deps=["p"])})
    result = verify_payload(_case(
        action={"output_id": "c", "dependencies": ["p"], "summary": "q"},
        before=before, after=after,
    ))
    assert str(result.verdict) == "UNRESOLVED", result.to_dict()


def test_an_unknown_domain_on_a_typed_input_still_makes_it_unresolved():
    claim = {**_claim("p", "n > 0"), "domain": "UNKNOWN"}
    before = _state(claims={"p": claim})
    after = _state(claims={"p": claim})
    result = verify_payload(_case(
        action={"dependencies": ["p"], "typing": {"input_domains": {"p": "Integer"}}},
        before=before, after=after,
    ))
    assert str(result.verdict) == "UNRESOLVED", result.to_dict()
