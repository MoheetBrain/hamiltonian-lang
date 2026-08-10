"""The rules that **no** acceptance fixture exercises.

`SEMANTIC_STATE_CONTRACT.md` §6 records why this file has to exist. The thirty frozen
fixtures are weaker than their pass rate suggests:

* SF-R06 specifies four candidate states; no fixture or benchmark case ever reaches
  ``UNVERIFIED`` or ``REJECTED``. Passing all thirty does not demonstrate the lifecycle.
* The two ILLEGAL fixtures added for candidates and branches differ from their LEGAL twins
  *only* in an ``evidence_id`` that names a missing record. The substantive rules — the
  constraint-subset check, "every branch CLOSED", and branch-conclusion agreement — are
  tested by no fixture at all. The implementation was written against the reference
  checker's source rather than against fixture pass/fail, so those paths shipped
  unexercised.
* ``scope_effect.kind`` is ``NONE`` in all 230 frozen records, which makes the
  discharge branch of the scope rule dead relative to the corpus.

These cases are synthetic and deliberately so. They are **not** a substitute for the
acceptance fixtures and must never be confused with them: the fixtures are external
criteria this repository does not control, whereas everything here was written by the same
author as the code it checks. Their value is narrower and real — they pin behaviour that
would otherwise be free to change silently, because nothing else would notice.

Payloads are built from scratch rather than by mutating a fixture, so this module runs in
a clean clone with no research corpus present.
"""

from __future__ import annotations

import copy

import pytest

from hamiltonian_lang.semantic_state import (
    Candidate,
    CandidateStatus,
    export_transition,
    import_transition,
    verify_payload,
)

SCHEMA = "semantic-firewall-case-0.1.0"


def _empty_state(**over) -> dict:
    state = {
        "active_scopes": ["global"],
        "branches": {},
        "candidates": {},
        "claims": {},
        "goals": {},
        "obligations": {},
    }
    state.update(over)
    return state


def _case(action: dict, before: dict, after: dict, evidence: dict) -> dict:
    """A minimal well-formed neutral record.

    Every axis the action does not exercise is left empty, so a verdict here is
    attributable to the one invariant under test rather than to an incidental interaction
    with the other nine.
    """
    base_action = {
        "id": "a1",
        "operation": "",
        "summary": "",
        "dependencies": [],
        "preconditions": [],
        "obligations_created": [],
        "obligations_discharged": [],
        "typing": {},
        "warrant": {},
        "goal_effect": {},
        "scope_effect": {},
        "branch_effect": {},
        "candidate_effect": {},
        "epistemic_effect": {},
    }
    base_action.update(action)
    return {
        "schema_version": SCHEMA,
        "case_id": "SYNTHETIC",
        "action": base_action,
        "state_before": before,
        "state_after": after,
        "evidence": evidence,
        "source": {},
    }


# ---------------------------------------------------------------------------
# SF-R06 — the four-state candidate lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "target", "permitted"),
    [
        (CandidateStatus.PROPOSED, CandidateStatus.UNVERIFIED, True),
        (CandidateStatus.PROPOSED, CandidateStatus.VERIFIED, True),
        (CandidateStatus.PROPOSED, CandidateStatus.REJECTED, True),
        (CandidateStatus.UNVERIFIED, CandidateStatus.VERIFIED, True),
        (CandidateStatus.UNVERIFIED, CandidateStatus.REJECTED, True),
        # Settled is settled. Reopening a candidate without a fresh proposal would let a
        # rejected object be retried until some evidence happened to accept it.
        (CandidateStatus.VERIFIED, CandidateStatus.REJECTED, False),
        (CandidateStatus.VERIFIED, CandidateStatus.UNVERIFIED, False),
        (CandidateStatus.REJECTED, CandidateStatus.VERIFIED, False),
        (CandidateStatus.REJECTED, CandidateStatus.UNVERIFIED, False),
        # UNKNOWN is representable but is not a lifecycle stage: it has no outgoing edges,
        # so a candidate whose status is not determined must be determined before it moves.
        (CandidateStatus.UNKNOWN, CandidateStatus.VERIFIED, False),
        (CandidateStatus.UNKNOWN, CandidateStatus.REJECTED, False),
    ],
)
def test_the_lifecycle_admits_exactly_the_specified_transitions(source, target, permitted):
    candidate = Candidate(id="k1", proposition="x = 2", status=source)
    assert candidate.may_transition_to(target) is permitted


def test_every_lifecycle_state_round_trips_through_the_adapter():
    """Including the two the corpus never produces.

    An adapter is only lossless for the values it has seen. ``UNVERIFIED`` and
    ``REJECTED`` appear in no fixture, so nothing else would catch an importer that
    refused them.
    """
    for status in CandidateStatus:
        case = _case(
            action={"operation": "PROPOSE_CANDIDATE"},
            before=_empty_state(
                candidates={
                    "k1": {
                        "id": "k1",
                        "proposition": "x = 2",
                        "status": str(status),
                        "scope": "global",
                        "constraint_ids": ["c1"],
                    }
                }
            ),
            after=_empty_state(),
            evidence={},
        )
        assert export_transition(import_transition(case)) == case, status


# ---------------------------------------------------------------------------
# SF-R07 — promotion checks every original constraint
# ---------------------------------------------------------------------------


def _promotion(
    *,
    before_status: str = "PROPOSED",
    after_status: str = "VERIFIED",
    constraints: tuple[str, ...] = ("c1", "c2"),
    checked: tuple[str, ...] | None = ("c1", "c2"),
    operation: str = "VERIFY_CANDIDATE",
    evidence_status: str = "VALID",
    supports_rule: str | None = "VERIFY_CANDIDATE",
    trusted: bool = False,
    cited_evidence_id: str = "e1",
    evidence_candidate_id: str | None = None,
) -> dict:
    record: dict = {
        "id": "e1",
        "kind": "CONSTRAINT_CHECK",
        "status": evidence_status,
        "supports_rule": supports_rule,
        "trusted": trusted,
        "premise_ids": [],
    }
    if checked is not None:
        record["checked_constraints"] = list(checked)
    if evidence_candidate_id is not None:
        record["candidate_id"] = evidence_candidate_id
    return _case(
        action={
            "operation": operation,
            "candidate_effect": {
                "kind": "PROMOTE",
                "candidate_id": "k1",
                "evidence_id": cited_evidence_id,
            },
        },
        before=_empty_state(
            candidates={
                "k1": {
                    "id": "k1",
                    "proposition": "x = 2",
                    "status": before_status,
                    "scope": "global",
                    "constraint_ids": list(constraints),
                }
            }
        ),
        after=_empty_state(
            candidates={
                "k1": {
                    "id": "k1",
                    "proposition": "x = 2",
                    "status": after_status,
                    "scope": "global",
                    "constraint_ids": list(constraints),
                }
            }
        ),
        evidence={"e1": record},
    )


def test_a_fully_checked_promotion_is_valid():
    """The baseline. Every negative case below is one edit away from this record."""
    result = verify_payload(_promotion())
    assert str(result.verdict) == "VALID", result.to_dict()


def test_promotion_that_checked_a_subset_of_the_constraints_is_rejected():
    """The rule the ILLEGAL fixture does not reach.

    This is the substantive failure the candidate invariant exists to stop: a proposed
    object satisfies the constraint somebody remembered to test, is promoted, and the
    constraint nobody tested is the one it violates. Verifying a subset establishes a
    different claim than the one being made.
    """
    result = verify_payload(_promotion(checked=("c1",)))
    assert str(result.verdict) == "INVALID"
    assert result.error_class == "CANDIDATE_PROMOTION"
    assert "c2" in result.findings[0].detail


def test_promotion_with_no_constraint_check_at_all_is_rejected():
    result = verify_payload(_promotion(checked=None))
    assert result.error_class == "CANDIDATE_PROMOTION"


def test_checking_extra_constraints_is_not_an_error():
    """Over-checking is sound. Only the *original* constraints are mandatory."""
    result = verify_payload(_promotion(checked=("c1", "c2", "c3")))
    assert str(result.verdict) == "VALID", result.to_dict()


def test_promotion_from_a_terminal_state_is_rejected():
    result = verify_payload(_promotion(before_status="REJECTED"))
    assert result.error_class == "CANDIDATE_PROMOTION"


def test_promotion_to_unverified_is_permitted_and_still_needs_the_constraints():
    """``PROPOSED -> UNVERIFIED`` is a legal edge, so it must be reachable here."""
    assert str(verify_payload(_promotion(after_status="UNVERIFIED")).verdict) == "VALID"
    assert (
        verify_payload(_promotion(after_status="UNVERIFIED", checked=("c1",))).error_class
        == "CANDIDATE_PROMOTION"
    )


def test_only_verify_candidate_promotes():
    result = verify_payload(_promotion(operation="ASSERT"))
    assert result.error_class == "CANDIDATE_PROMOTION"


def test_promotion_evidence_about_another_candidate_is_rejected():
    result = verify_payload(_promotion(evidence_candidate_id="k9"))
    assert result.error_class == "CANDIDATE_PROMOTION"


def test_promotion_evidence_must_support_the_rule_being_applied():
    result = verify_payload(_promotion(supports_rule="SIMPLIFY"))
    assert result.error_class == "CANDIDATE_PROMOTION"


def test_a_candidate_absent_from_either_state_is_rejected():
    case = _promotion()
    case["state_after"]["candidates"] = {}
    assert verify_payload(case).error_class == "CANDIDATE_PROMOTION"


@pytest.mark.parametrize(
    "defect",
    [
        {"checked": ("c1",)},
        {"evidence_status": "INVALID"},
        {"supports_rule": "SIMPLIFY"},
        {"evidence_candidate_id": "k9"},
    ],
)
def test_the_trusted_flag_rescues_nothing(defect):
    """``EvidenceRecord.trusted`` is provenance, not permission.

    A field the producer of the record can set must never be the thing that makes the
    producer's output true. Nothing in the verifier reads it as authority, and this asserts
    that directly rather than leaving it to the docstring.
    """
    assert verify_payload(_promotion(trusted=True, **defect)).error_class == (
        "CANDIDATE_PROMOTION"
    )


# ---------------------------------------------------------------------------
# SF-R08 — certified branch/join
# ---------------------------------------------------------------------------

_JOINED = "n is even or n is odd"


def _join(
    *,
    statuses: dict[str, str] | None = None,
    conclusions: dict[str, str | None] | None = None,
    covered: tuple[str, ...] | None = ("b1", "b2"),
    branch_ids: tuple[str, ...] = ("b1", "b2"),
    published: str = _JOINED,
    evidence_status: str = "VALID",
    predicates: dict[str, str] | None = None,
) -> dict:
    statuses = statuses or {"b1": "CLOSED", "b2": "CLOSED"}
    conclusions = conclusions if conclusions is not None else {"b1": _JOINED, "b2": _JOINED}
    predicates = predicates or {"b1": "n mod 2 = 0", "b2": "n mod 2 = 1"}
    branches = {
        bid: {
            "id": bid,
            "predicate": predicates[bid],
            "status": statuses[bid],
            "partition_id": "p1",
            **({"conclusion": conclusions[bid]} if conclusions.get(bid) else {}),
        }
        for bid in statuses
    }
    record: dict = {
        "id": "e1",
        "kind": "PARTITION_CERTIFICATE",
        "status": evidence_status,
        "supports_rule": "JOIN_BRANCHES",
        "trusted": False,
        "premise_ids": [],
    }
    if covered is not None:
        record["branch_ids"] = list(covered)
    return _case(
        action={
            "operation": "JOIN_BRANCHES",
            "output_id": "cl_join",
            "branch_effect": {
                "kind": "JOIN",
                "branch_ids": list(branch_ids),
                "coverage_evidence_id": "e1",
            },
        },
        before=_empty_state(branches=branches),
        after=_empty_state(
            branches=branches,
            claims={
                "cl_join": {
                    "id": "cl_join",
                    "proposition": published,
                    "status": "DERIVED",
                    "scope": "global",
                    "dependencies": [],
                }
            },
        ),
        evidence={"e1": record},
    )


def test_a_certified_join_is_valid():
    assert str(verify_payload(_join()).verdict) == "VALID", verify_payload(_join()).to_dict()


def test_a_join_over_an_open_branch_is_rejected():
    """The rule the ILLEGAL fixture does not reach. An open branch has not concluded."""
    result = verify_payload(_join(statuses={"b1": "CLOSED", "b2": "OPEN"}))
    assert result.error_class == "INVALID_BRANCH_JOIN"
    assert "b2" in result.findings[0].detail


def test_a_join_over_an_abandoned_branch_is_rejected():
    result = verify_payload(_join(statuses={"b1": "CLOSED", "b2": "ABANDONED"}))
    assert result.error_class == "INVALID_BRANCH_JOIN"


def test_a_join_publishing_something_no_branch_concluded_is_rejected():
    """The second rule no fixture reaches.

    A join publishes what every branch established. Branches that concluded different
    things have not jointly proved the published proposition, however plausible it is.
    """
    result = verify_payload(_join(conclusions={"b1": _JOINED, "b2": "n is prime"}))
    assert result.error_class == "INVALID_BRANCH_JOIN"
    assert "b2" in result.findings[0].detail


def test_a_certificate_that_omits_a_branch_does_not_cover_the_join():
    result = verify_payload(_join(covered=("b1",)))
    assert result.error_class == "INVALID_BRANCH_JOIN"
    assert "b2" in result.findings[0].detail


def test_agreement_between_branches_is_not_a_partition_certificate():
    """Both branches CLOSED, both concluding the published claim, no coverage evidence.

    This is the failure mode SF-R08 exists for: the cases agree, so the join looks sound,
    but nothing establishes that those cases are all the cases.
    """
    case = _join()
    case["evidence"] = {}
    result = verify_payload(case)
    assert result.error_class == "INVALID_BRANCH_JOIN"


def test_a_join_naming_no_branches_is_rejected():
    result = verify_payload(_join(branch_ids=()))
    assert result.error_class == "INVALID_BRANCH_JOIN"


def test_a_join_over_a_branch_missing_from_the_prior_state_is_rejected():
    case = _join(branch_ids=("b1", "b2", "b3"), covered=("b1", "b2", "b3"))
    assert verify_payload(case).error_class == "INVALID_BRANCH_JOIN"


def test_overlapping_branches_are_accepted():
    """Coverage is required; disjointness deliberately is not.

    Disjunction elimination is sound for overlapping cases, so a checker that demanded
    disjointness would reject valid reasoning. The MiniLang ``CONSIDER-or`` obligations
    record coverage only, which is the same choice. Asserted here because a later reader
    is likely to think the missing check is an oversight and add it.
    """
    result = verify_payload(
        _join(predicates={"b1": "n <= 10", "b2": "n >= 5"})
    )
    assert str(result.verdict) == "VALID", result.to_dict()


def test_an_unconcluded_branch_does_not_block_a_join_it_covers():
    """``conclusion`` is optional; only a *conflicting* conclusion is a violation."""
    result = verify_payload(_join(conclusions={"b1": _JOINED, "b2": None}))
    assert str(result.verdict) == "VALID", result.to_dict()


# ---------------------------------------------------------------------------
# The scope-discharge path — dead in all 230 frozen records
# ---------------------------------------------------------------------------


def _escape(*, scope_effect: dict | None = None, evidence_status: str = "VALID") -> dict:
    return _case(
        action={
            "operation": "ASSERT",
            "output_id": "cl_out",
            "dependencies": ["p1"],
            "scope_effect": scope_effect or {},
        },
        before=_empty_state(
            active_scopes=["global", "branch:b1"],
            claims={
                "p1": {
                    "id": "p1",
                    "proposition": "n is even",
                    "status": "ASSUMED",
                    "scope": "branch:b1",
                    "dependencies": [],
                }
            },
        ),
        after=_empty_state(
            active_scopes=["global", "branch:b1"],
            claims={
                # Carried forward unchanged: the frame condition (D-049) refuses a
                # resulting state that quietly drops a premise the action never touched.
                "p1": {
                    "id": "p1",
                    "proposition": "n is even",
                    "status": "ASSUMED",
                    "scope": "branch:b1",
                    "dependencies": [],
                },
                "cl_out": {
                    "id": "cl_out",
                    "proposition": "n is even",
                    "status": "DERIVED",
                    "scope": "global",
                    "dependencies": ["p1"],
                },
            },
        ),
        evidence={
            "e1": {
                "id": "e1",
                "kind": "SCOPE_DISCHARGE",
                "status": evidence_status,
                "supports_rule": None,
                "trusted": False,
                "premise_ids": [],
            }
        },
    )


def test_leaving_a_frame_without_a_discharge_is_a_scope_leak():
    result = verify_payload(_escape())
    assert result.error_class == "SCOPE_LEAK", result.to_dict()


def test_a_valid_discharge_licenses_the_escape():
    """The live half of the rule, which no frozen record exercises.

    Without this the discharge branch could be deleted outright and every fixture would
    still pass — the rule would silently become "a conclusion may never leave its frame".
    """
    result = verify_payload(
        _escape(scope_effect={"kind": "DISCHARGE", "discharge_evidence_id": "e1"})
    )
    assert str(result.verdict) == "VALID", result.to_dict()


@pytest.mark.parametrize(
    "effect",
    [
        {"kind": "DISCHARGE", "discharge_evidence_id": "missing"},
        {"kind": "DISCHARGE"},
        {"kind": "ENTER", "discharge_evidence_id": "e1"},
    ],
)
def test_a_discharge_that_does_not_check_out_does_not_license_the_escape(effect):
    assert verify_payload(_escape(scope_effect=effect)).error_class == "SCOPE_LEAK"


def test_a_discharge_resting_on_invalid_evidence_does_not_license_the_escape():
    result = verify_payload(
        _escape(
            scope_effect={"kind": "DISCHARGE", "discharge_evidence_id": "e1"},
            evidence_status="INVALID",
        )
    )
    assert result.error_class == "SCOPE_LEAK"


def test_a_discharge_resting_on_unknown_evidence_is_unresolved_not_invalid():
    """Cited-but-unknown evidence must not be read as a violation.

    ``UNRESOLVED`` is not a soft ``INVALID``: reporting a detected corruption here would
    inflate the detection rate with cases where nothing was detected.
    """
    result = verify_payload(
        _escape(
            scope_effect={"kind": "DISCHARGE", "discharge_evidence_id": "e1"},
            evidence_status="UNKNOWN",
        )
    )
    assert str(result.verdict) == "UNRESOLVED", result.to_dict()


# ---------------------------------------------------------------------------
# Import refusals
# ---------------------------------------------------------------------------


def test_an_unrecognised_schema_version_is_refused_rather_than_parsed():
    from hamiltonian_lang.semantic_state import NeutralImportError

    case = _promotion()
    case["schema_version"] = "semantic-firewall-case-0.2.0"
    with pytest.raises(NeutralImportError):
        import_transition(case)


def test_an_unknown_status_literal_is_refused_rather_than_coerced():
    from hamiltonian_lang.semantic_state import NeutralImportError

    case = _promotion()
    case["state_before"]["candidates"]["k1"]["status"] = "PROBABLY_FINE"
    with pytest.raises(NeutralImportError):
        import_transition(case)


def test_importing_never_mutates_the_record_it_was_given():
    """The adapter is handed fixture dictionaries that other tests then compare against."""
    case = _promotion()
    original = copy.deepcopy(case)
    import_transition(case)
    assert case == original
