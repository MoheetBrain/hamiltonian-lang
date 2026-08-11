"""Proposed tests: the seventeen HIGH-severity invariants a mutation census found unguarded.

Every test below was written against a **measured** surviving mutant of production
`src/hamiltonian_lang/semantic_state/`, at `10c1879`. Each one names the exact edit that
removes the invariant it pins, and each was verified twice: it passes against unmutated
production, and it fails against its mutant. A proposed test that does not kill its mutant
is worse than none, so the mutant is quoted in the docstring rather than described.

Three of these exist because an **existing** test passes for the wrong reason rather than
because the property was never considered:

* `test_trust_boundary.py::test_an_attestation_cannot_be_routed_by_a_payload_controlled_id`
  passes **no attestations at all**, so it cannot tell `attestations[cited_as]` from
  `attestations[record.id]` — both lookups miss an empty mapping. See
  `test_a_genuine_attestation_does_not_transfer_through_a_payload_controlled_record_id`.
* `test_trust_boundary.py::test_the_scope_discharge_site_binds_its_claim` supplies an
  attestation that mismatches on **both** the claim and the premises, so either binding
  alone satisfies it. Removing either one individually is invisible to it. See the two
  `..._scope_discharge_...` tests.
* `test_reproduced_defects.py::test_a_cyclic_scope_tree_does_not_hang_the_verifier` picks a
  premise/conclusion pair whose containment answer is found on the **first** hop, so the
  loop guard it is named for is never entered. See
  `test_a_cyclic_scope_tree_terminates_when_the_answer_is_not_on_the_first_hop`.

The `GOAL_DISCHARGE` family is here in full. All three of its rules were unguarded: the
family's only fixture, `FX-GOL-ILLEGAL`, violates rule 1 *and* rule 3 at once, so each rule
covers for the other and neither can be removed detectably on its own.
"""

from __future__ import annotations

import copy
import threading

import pytest

import hamiltonian_lang.reasoning.certificates as C
from hamiltonian_lang.semantic_state import (
    verify,
    verify_replay,
    verify_runtime,
)
from hamiltonian_lang.semantic_state.neutral import import_transition
from hamiltonian_lang.semantic_state.trust import TrustMode, attest

SCHEMA = "semantic-firewall-case-0.1.0"

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


def _state(**over) -> dict:
    out = copy.deepcopy(_EMPTY)
    out.update(copy.deepcopy(over))
    return out


def _case(action=None, before=None, after=None, evidence=None) -> dict:
    return {
        "schema_version": SCHEMA, "case_id": "PROPOSED",
        "action": {**copy.deepcopy(_ACTION), **copy.deepcopy(action or {})},
        "state_before": before if before is not None else copy.deepcopy(_EMPTY),
        "state_after": after if after is not None else copy.deepcopy(_EMPTY),
        "evidence": copy.deepcopy(evidence or {}), "source": {},
    }


def _claim(cid, proposition="p", status="GIVEN", scope="global", deps=(), domain=None):
    out = {"id": cid, "proposition": proposition, "status": status,
           "scope": scope, "dependencies": list(deps)}
    if domain is not None:
        out["domain"] = domain
    return out


def _mint(monkeypatch, *, checker="census_probe_v1"):
    """Mint a genuine `CheckedEvidence` through the real gate.

    Same pattern as `test_trust_boundary.py::_mint`: the object passes through
    `certificates.check`, so it carries the private mint token and is not a double.
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
    envelope = C.CertificateEnvelope(
        certificate_type=checker, certificate_version=1, checker=checker,
        judgement=C.JudgementKind.ENTAILS, claim_hash=expr_identity(claim),
        context_hash="ctx", premise_hashes=(),
    )
    evidence, reason = C.check(envelope, claim, C.CheckerContext(), current_context_hash="ctx")
    assert evidence is not None, f"could not mint through the real gate: {reason}"
    return evidence


# ---------------------------------------------------------------------------
# TRUST / EVIDENCE AUTHORITY
# ---------------------------------------------------------------------------


def test_a_genuine_attestation_does_not_transfer_through_a_payload_controlled_record_id(
    monkeypatch,
):
    """D-052's routing repair, pinned by an attestation that is actually present.

    The defect: `_accepted` filed attestations under `record.id` rather than under the id
    the **action** cites. `record.id` is payload-controlled and the neutral schema lets it
    differ from the mapping key, so a producer holding a genuine certificate for
    `e_genuine` could cite the record as `e_forged` and have the certificate applied to it.

    Nothing else catches this. `test_an_attestation_cannot_be_routed_by_a_payload_controlled_id`
    is named for exactly this hole but calls `verify_runtime` with **no attestations**, so
    both keyings miss an empty mapping and it returns INVALID either way. Measured: with
    `attestations.get(cited_as or record.id)` reverted to
    `attestations.get(record.id or cited_as)` that test still passes and this one fails.
    """
    checked = _mint(monkeypatch)
    premise = _claim("p", "q")
    case = _case(
        action={"operation": "ASSERT", "dependencies": ["p"],
                "warrant": {"kind": "X", "rule": "R", "evidence_id": "e_forged"}},
        before=_state(claims={"p": premise}),
        after=_state(claims={"p": premise}),
        # Cited as `e_forged`; the record's own id says `e_genuine`.
        evidence={"e_forged": {"id": "e_genuine", "kind": "K", "status": "VALID",
                               "supports_rule": "R", "trusted": False,
                               "premise_ids": ["p"]}},
    )
    genuine = attest("e_genuine", checked, claim="q", premises=("p",), rule="R")
    result = verify_runtime(import_transition(case), {"e_genuine": genuine})
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert "no checker attestation" in result.findings[0].detail

    # The control: filed under the id the action actually cites, the same certificate works.
    proper = attest("e_forged", checked, claim="q", premises=("p",), rule="R")
    assert str(verify_runtime(import_transition(case),
                             {"e_forged": proper}).verdict) == "VALID"


def test_join_coverage_evidence_that_is_not_valid_does_not_certify_the_partition():
    """The BRANCH_JOIN trust site. Removing it accepts an explicitly rejected certificate.

    The defect: dropping `if not ok: return [Finding("BRANCH_JOIN", ...)]` from
    `_check_branch_join` leaves the join gated only on the certificate's *existence* and its
    branch list. Measured: a partition certificate recorded `"status": "INVALID"` — and one
    recorded `"REJECTED"` — verified VALID, and at RUNTIME a self-asserted certificate with
    no checker attestation verified VALID too, which is D-050's hole reopened at this site.

    Nothing else catches it. `test_agreement_between_branches_is_not_a_partition_certificate`
    deletes the record entirely, which the separate null guard refuses; no test offers a
    certificate that exists and is not acceptable.
    """
    for status in ("INVALID", "REJECTED"):
        result = verify_replay(import_transition(_join(evidence_status=status)))
        assert str(result.verdict) == "INVALID", (status, result.to_dict())
        assert result.error_class == "INVALID_BRANCH_JOIN"

    # The effect states its rule explicitly, so this reaches the authority seam rather than
    # being turned away earlier by the runtime rule-fallback refusal.
    runtime = verify_runtime(import_transition(_join(rule="JOIN_BRANCHES")))
    assert str(runtime.verdict) == "INVALID", runtime.to_dict()
    assert runtime.error_class == "INVALID_BRANCH_JOIN"
    assert "no checker attestation" in runtime.findings[0].detail


def test_join_coverage_evidence_must_support_the_join_rule():
    """The second unguarded BRANCH_JOIN evidence rule.

    The defect: dropping `if not _supports(record, _effect_rule(effect, t.action))` from
    `_check_branch_join` lets any certificate certify a join. Measured: a record whose
    `supports_rule` is `"SIMPLIFY"` certified a `JOIN_BRANCHES` partition as VALID.

    In OFFLINE_REPLAY this is the *only* rule check at this site — `_accepted` ignores
    `rule` in replay mode — so its removal is invisible to every replayed fixture, and no
    synthetic test supplies a mismatched `supports_rule` on coverage evidence.
    """
    result = verify_replay(import_transition(_join(supports="SIMPLIFY")))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "INVALID_BRANCH_JOIN"
    assert "SIMPLIFY" in result.findings[0].detail


def test_at_runtime_a_join_effect_that_states_no_rule_does_not_fall_back_to_the_label():
    """P-01's runtime no-fallback rule, at the join site. **Requires `aac4483` or later.**

    That commit scoped the legacy `action.operation` fallback in `_effect_rule` to
    OFFLINE_REPLAY, and wired the resulting refusal into `_check_candidates` *and*
    `_check_branch_join`. Only the candidate wiring is covered: dropping
    `if refusal: return [Finding("CANDIDATES", ...)]` fails a test, and dropping the
    identical `BRANCH_JOIN` line fails nothing. Measured on the branch-join site: with that
    guard removed, a runtime join whose effect states no rule silently recovers authority
    from the operation label the producer also wrote — which is the exact claim the commit
    was made to establish.

    This is the one test in this file that is **not** expected to pass before `aac4483`: at
    `10c1879` the runtime fallback still existed, so the same payload is refused for a
    different reason ("no checker attestation").
    """
    result = verify_runtime(import_transition(_join()))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "INVALID_BRANCH_JOIN"
    assert "carries no authority" in result.findings[0].detail


def test_a_warrant_citing_evidence_that_does_not_exist_is_refused():
    """SF-R09's most basic reference check, and no test held it.

    The defect: dropping the inner `if warrant.get("evidence_id"):` from `_check_warrant`
    makes a warrant that names a record which is not in the bundle produce **no finding at
    all** — the function returns `[]` and the transition is accepted. Measured VALID in both
    OFFLINE_REPLAY and RUNTIME.

    Nothing else catches it. `FX-WAR-ILLEGAL` corrupts `warrant.rule` rather than
    `warrant.evidence_id`, so the frozen family exercises the *mismatch* branch and never the
    *missing* branch; and `_check_epistemic`'s fallback to the warrant's evidence only runs
    when the action also declares an epistemic promotion.
    """
    premise = _claim("p", "q")
    case = _case(
        action={"dependencies": ["p"],
                "warrant": {"kind": "X", "rule": "R", "evidence_id": "ghost"}},
        before=_state(claims={"p": premise}), after=_state(claims={"p": premise}),
    )
    for check in (verify_replay, verify_runtime):
        result = check(import_transition(case))
        assert str(result.verdict) == "INVALID", result.to_dict()
        assert result.error_class == "WARRANT_MISMATCH"
        assert "does not exist" in result.findings[0].detail


# ---------------------------------------------------------------------------
# SCOPE
# ---------------------------------------------------------------------------


def _branches(**parents):
    return {k: {"id": k, "predicate": "x", "status": "OPEN", "scope": v}
            for k, v in parents.items()}


def test_a_cyclic_scope_tree_terminates_when_the_answer_is_not_on_the_first_hop():
    """The `seen` guard in `_contains`, pinned by an input that actually enters the loop.

    The defect: `_scope_parents` is derived from producer-supplied branch records, so the
    containment walk can be handed a cycle. Removing `and current not in seen` from
    `_contains` makes the walk run forever whenever the answer is not on the chain — a
    complete denial of service against the verifier, from a payload with no evidence in it
    at all. Measured: the verification never returned.

    Nothing else catches it. `test_a_cyclic_scope_tree_does_not_hang_the_verifier` builds the
    same cycle but asks whether `branch:a` contains `branch:b`, and `parents["branch:b"]` *is*
    `branch:a`, so the answer is found on the first hop and the loop is never re-entered.
    Here the premise sits in `global`, which the cycle never reaches.
    """
    cyclic = _branches(a="branch:b", b="branch:a")
    premise = _claim("p", "q", "ASSUMED")
    case = _case(
        action={"output_id": "c", "summary": "q", "dependencies": ["p"]},
        before=_state(active_scopes=["global", "branch:a", "branch:b"],
                      branches=cyclic, claims={"p": premise}),
        after=_state(active_scopes=["global", "branch:a", "branch:b"], branches=cyclic,
                     claims={"p": premise,
                             "c": _claim("c", "q", "DERIVED", scope="branch:b",
                                         deps=["p"])}),
    )
    box: dict = {}
    worker = threading.Thread(
        target=lambda: box.setdefault("r", verify_replay(import_transition(case))),
        daemon=True,
    )
    worker.start()
    worker.join(10.0)
    assert not worker.is_alive(), (
        "the containment walk did not terminate on a cyclic scope tree; a malformed "
        "producer-supplied branch record must not be able to hang the verifier"
    )
    assert str(box["r"].verdict) in {"VALID", "INVALID"}


def test_a_premise_in_a_closed_frame_cannot_be_cited_by_an_action_that_produces_no_claim():
    """The visibility half of SF-R05, which only the containment rule was covering.

    The defect: dropping `if claim is not None and claim.scope not in order` from
    `_check_scope`. When the action *does* produce a claim the containment rule catches the
    same records, which is why every existing scope test still passes — but `_check_scope`
    returns early when `produced is None`, so an action with no `output_id` (a candidate
    promotion, an obligation discharge, a join) may cite a premise from a frame that is no
    longer open. Measured VALID.
    """
    stale = _claim("p", "q", "ASSUMED", scope="branch:closed")
    case = _case(
        action={"dependencies": ["p"]},
        before=_state(active_scopes=["global"], claims={"p": stale}),
        after=_state(active_scopes=["global"], claims={"p": stale}),
    )
    result = verify_replay(import_transition(case))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "SCOPE_LEAK"
    assert "inactive scope" in result.findings[0].detail


def test_a_conclusion_cannot_be_written_into_a_frame_that_is_not_open():
    """`active_scopes` answers "is this frame open?", and something has to ask it.

    The defect: dropping `if produced.scope not in order` from `_check_scope`. Containment
    does not cover this case — `branch:z` is a *declared* branch whose own scope is
    `global`, so `_contains(parents, "global", "branch:z")` is True and the escape check
    finds nothing to complain about. Measured VALID: a conclusion written into a frame that
    was never opened, and again into it with no premises at all.
    """
    branches = {"z": {"id": "z", "predicate": "x", "status": "OPEN", "scope": "global"}}
    premise = _claim("p", "q")
    case = _case(
        action={"output_id": "c", "summary": "q", "dependencies": ["p"]},
        before=_state(active_scopes=["global"], branches=branches,
                      claims={"p": premise}),
        after=_state(active_scopes=["global"], branches=branches,
                     claims={"p": premise,
                             "c": _claim("c", "q", "DERIVED", scope="branch:z",
                                         deps=["p"])}),
    )
    result = verify_replay(import_transition(case))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "SCOPE_LEAK"
    assert "not active" in result.findings[0].detail


def _discharge_case(*, claim_text: str, premises: tuple[str, ...], checked):
    """A branch-local premise concluded into `global` behind a runtime discharge."""
    local = _claim("p", "q", "ASSUMED", scope="branch:b1")
    case = _case(
        action={"operation": "ASSERT", "output_id": "c", "dependencies": ["p"],
                "scope_effect": {"kind": "DISCHARGE", "discharge_evidence_id": "e_d"}},
        before=_state(active_scopes=["global", "branch:b1"], claims={"p": local}),
        after=_state(active_scopes=["global", "branch:b1"],
                     claims={"p": local,
                             "c": _claim("c", "q", "DERIVED", deps=["p"])}),
        evidence={"e_d": {"id": "e_d", "kind": "K", "status": "VALID",
                          "supports_rule": None, "trusted": False, "premise_ids": []}},
    )
    attestation = attest("e_d", checked, claim=claim_text, premises=premises)
    return import_transition(case), {"e_d": attestation}


def test_the_scope_discharge_site_refuses_an_attestation_issued_for_a_different_claim(
    monkeypatch,
):
    """One of the two bindings D-052 added, isolated so it can fail on its own.

    The defect: passing `claim=None` instead of `claim=produced.proposition` from
    `_discharge_licenses_escape`. Measured VALID: an attestation certifying `2 + 2 = 4`,
    checked against exactly the premises the action declares, licensed a branch-local fact
    into `global`.

    `test_the_scope_discharge_site_binds_its_claim` cannot fail on this alone: its
    attestation mismatches on the claim **and** on the premises, so the premise binding
    refuses it whether or not the claim binding is there.
    """
    checked = _mint(monkeypatch)
    transition, attestations = _discharge_case(
        claim_text="2 + 2 = 4", premises=("p",), checked=checked)
    result = verify_runtime(transition, attestations)
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "SCOPE_LEAK"


def test_the_scope_discharge_site_refuses_an_attestation_checked_against_no_premises(
    monkeypatch,
):
    """The other binding, isolated the same way — and the more dangerous of the two.

    The defect: passing `premises=()` instead of `premises=t.action.dependencies`. Measured
    VALID: an attestation for exactly the right proposition but checked against **nothing**
    licensed the escape. That is precisely the shape a closed-evaluation checker produces —
    a true statement established from no premises — and it must not discharge a frame whose
    conclusion rests on a local assumption.
    """
    checked = _mint(monkeypatch)
    transition, attestations = _discharge_case(
        claim_text="q", premises=(), checked=checked)
    result = verify_runtime(transition, attestations)
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "SCOPE_LEAK"


def test_a_correctly_bound_runtime_discharge_still_licenses_the_escape(monkeypatch):
    """The positive runtime path, which nothing exercised.

    `test_a_valid_discharge_licenses_the_escape` runs in OFFLINE_REPLAY, where `_accepted`
    reads the recorded status and never consults an attestation at all. So the runtime
    discharge could have been "refuse everything" — or, as measured, could have started
    refusing correct attestations when the premise binding was tightened — and every
    existing test would still pass.
    """
    checked = _mint(monkeypatch)
    transition, attestations = _discharge_case(
        claim_text="q", premises=("p",), checked=checked)
    result = verify_runtime(transition, attestations)
    assert str(result.verdict) == "VALID", result.to_dict()


# ---------------------------------------------------------------------------
# GOAL DISCHARGE — all three rules, none of which was individually guarded
# ---------------------------------------------------------------------------


def test_the_produced_claim_must_state_what_the_action_says_it_states():
    """`GOAL_DISCHARGE` rule 1: `produced.proposition != action.summary`.

    The defect: disabling that comparison. Measured VALID — an action may announce one
    conclusion in its summary and write a different proposition into the resulting state,
    with no goal effect involved at all and no evidence forged.

    `FX-GOL-ILLEGAL` cannot detect its removal, because that fixture violates rule 1 *and*
    rule 3 simultaneously: with rule 1 gone, rule 3 still reports `FALSE_GOAL_DISCHARGE` and
    the fixture's expected error class still matches. This case carries no `goal_effect`, so
    rule 1 is the only rule that can speak.
    """
    premise = _claim("p", "q")
    case = _case(
        action={"output_id": "c", "summary": "the sum is 7", "dependencies": ["p"]},
        before=_state(claims={"p": premise}),
        after=_state(claims={"p": premise,
                             "c": _claim("c", "the sum is 8", "DERIVED", deps=["p"])}),
    )
    result = verify_replay(import_transition(case))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "FALSE_GOAL_DISCHARGE"


def test_discharging_a_goal_that_is_not_in_the_prior_state_is_refused_rather_than_raised():
    """`GOAL_DISCHARGE` rule 2, and it is also the guard that keeps `verify` from throwing.

    The defect: disabling `if goal is None`. The following `elif` then reads
    `goal.proposition` on `None`, so the mutant does not merely mis-verdict — it raises
    `AttributeError: 'NoneType' object has no attribute 'proposition'` straight out of
    `verify()`, which is contracted never to throw on producer-authored input.

    The fuzz sweep in `test_no_malformed_payload_raises_from_the_verifier` does not reach it:
    it substitutes junk values into whole fields, and this needs a *well-formed*
    `goal_effect` naming a goal id that the prior state does not carry.
    """
    premise = _claim("p", "q")
    case = _case(
        action={"output_id": "c", "summary": "q", "dependencies": ["p"],
                "goal_effect": {"kind": "DISCHARGE", "goal_id": "g_absent"}},
        before=_state(claims={"p": premise}),
        after=_state(claims={"p": premise,
                             "c": _claim("c", "q", "DERIVED", deps=["p"])}),
    )
    result = verify_replay(import_transition(case))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "FALSE_GOAL_DISCHARGE"
    assert "not in the prior state" in result.findings[0].detail


def test_a_goal_is_discharged_only_by_a_claim_that_states_it():
    """`GOAL_DISCHARGE` rule 3, isolated from rule 1.

    The defect: disabling `produced.proposition != goal.proposition`. Measured VALID: a goal
    asking for one proposition was closed by a claim asserting another. Here the action's
    `summary` **agrees** with the claim it produced, so rule 1 has nothing to say and rule 3
    is the only thing standing between an open goal and a false discharge.
    """
    premise = _claim("p", "q")
    goals = {"g1": {"id": "g1", "proposition": "x is prime", "status": "OPEN",
                    "scope": "global"}}
    case = _case(
        action={"output_id": "c", "summary": "x is odd", "dependencies": ["p"],
                "goal_effect": {"kind": "DISCHARGE", "goal_id": "g1"}},
        before=_state(goals=goals, claims={"p": premise}),
        after=_state(goals=goals,
                     claims={"p": premise,
                             "c": _claim("c", "x is odd", "DERIVED", deps=["p"])}),
    )
    result = verify_replay(import_transition(case))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "FALSE_GOAL_DISCHARGE"
    assert "does not state it" in result.findings[0].detail


# ---------------------------------------------------------------------------
# PRECONDITIONS, OBLIGATIONS, DEPENDENCY, DOMAIN
# ---------------------------------------------------------------------------


def test_an_unsatisfied_precondition_refuses_the_transition():
    """SF-R04 names three outcomes and the corpus exercises only two of them.

    The defect: adding `"UNSATISFIED"` to the set of statuses `_check_preconditions` lets
    through. Measured VALID. `_check_preconditions`' own docstring names UNSATISFIED as *the*
    refusal case, yet `FX-PRE-ILLEGAL` records its failing precondition as `"FAILED"`, so the
    literal the rule is written about appears in no fixture and in no test — and a
    permissive list is exactly the edit a future reader would make while "aligning
    vocabulary with the corpus".
    """
    result = verify_replay(import_transition(
        _case(action={"preconditions": [{"id": "pre0", "status": "UNSATISFIED",
                                         "description": "denominator is non-zero"}]})))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "PRECONDITION_VIOLATION"


def test_a_precondition_resting_on_unknown_evidence_is_unresolved_rather_than_valid():
    """A precondition's `evidence_id` is load-bearing, and only through the unknown scope.

    `_check_preconditions` reads nothing but `status`, so the *only* thing that consults a
    precondition's evidence is `_cited_evidence_ids`. The defect: dropping preconditions from
    that list. Measured VALID — a precondition recorded SATISFIED against evidence whose own
    status is UNKNOWN executed as an ordinary valid transition, which is the fail-open
    direction of the three-valued rule.
    """
    case = _case(
        action={"preconditions": [{"id": "pre0", "status": "SATISFIED",
                                   "evidence_id": "e_pre"}]},
        evidence={"e_pre": {"id": "e_pre", "kind": "K", "status": "UNKNOWN",
                            "supports_rule": None, "trusted": False, "premise_ids": []}},
    )
    result = verify_replay(import_transition(case))
    assert str(result.verdict) == "UNRESOLVED", result.to_dict()
    assert any("e_pre" in u for u in result.unknowns)


def test_an_obligation_cannot_change_state_without_a_declared_discharge():
    """Proof debt must not be erasable by declaring nothing.

    The defect: making `_licensed_change` return True for obligations. The frame's *removal*
    check is separate and still refuses a deleted obligation — which is what
    `test_a_mandatory_obligation_cannot_be_deleted` pins — but nothing tested an obligation
    that is still present and has quietly been rewritten. Measured VALID: a mandatory
    obligation walked `OPEN -> DISCHARGED` with `obligations_discharged` empty, so
    `_check_obligations` never looked at it either.
    """
    def obligation(status):
        return {"o": {"id": "o", "proposition": "d != 0", "status": status,
                      "mandatory": True, "dependencies": []}}

    result = verify_replay(import_transition(
        _case(before=_state(obligations=obligation("OPEN")),
              after=_state(obligations=obligation("DISCHARGED")))))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "DEPENDENCY_VIOLATION"
    assert "without a licensed state effect" in result.findings[0].detail


def test_a_conclusion_may_not_under_record_the_premises_the_action_declared():
    """Ancestry must match exactly; the dangerous drift is the one that *drops* a premise.

    The defect: weakening `set(produced.dependencies) != set(action.dependencies)` to a
    subset test. Measured VALID: an action declaring `["p", "r"]` wrote a conclusion
    recording `["p"]`. Every existing dependency test adds an ancestor rather than removing
    one, and the added-ancestor direction is still refused by the subset reading, so the
    weakening is invisible to all of them.

    A claim that under-records its ancestry is laundered provenance: the state then says it
    rests on less than it does, and nothing downstream re-derives the truth.
    """
    before = _state(claims={"p": _claim("p"), "r": _claim("r")})
    after = _state(claims={"p": _claim("p"), "r": _claim("r"),
                           "c": _claim("c", "q", "DERIVED", deps=["p"])})
    result = verify_replay(import_transition(
        _case(action={"output_id": "c", "summary": "q", "dependencies": ["p", "r"]},
              before=before, after=after)))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "DEPENDENCY_VIOLATION"


def test_an_output_domain_the_produced_claim_does_not_carry_is_unresolved_not_valid():
    """SF-R13's other half of D-048: absence is unavailability, not agreement.

    The defect: dropping the `state_after.claims[output].domain is None` entry from
    `_collect_unknowns`. `_check_type_domain` then skips its output comparison — it requires
    `produced.domain is not None` — so the transition is simply accepted. Measured
    UNRESOLVED at HEAD and VALID under the mutant.

    The input-side twin of this rule is covered by `FX2-DOM-ABSENT-UNKNOWN`; the output side
    is covered by nothing, because no fixture declares an `output_domain` at all.
    """
    premise = _claim("p", "n > 0", domain="Integer")
    case = _case(
        action={"output_id": "c", "summary": "q", "dependencies": ["p"],
                "typing": {"output_domain": "Integer"}},
        before=_state(claims={"p": premise}),
        after=_state(claims={"p": premise,
                             "c": _claim("c", "q", "DERIVED", deps=["p"])}),
    )
    result = verify_replay(import_transition(case))
    assert str(result.verdict) == "UNRESOLVED", result.to_dict()
    assert any("domain is not declared" in u for u in result.unknowns)


# ---------------------------------------------------------------------------
# shared join builder
# ---------------------------------------------------------------------------

_JOINED = "n is even or n is odd"


def _join(*, evidence_status: str = "VALID", supports: str = "JOIN_BRANCHES",
          rule: str | None = None) -> dict:
    branches = {
        bid: {"id": bid, "predicate": bid, "status": "CLOSED", "partition_id": "p1",
              "conclusion": _JOINED}
        for bid in ("b1", "b2")
    }
    effect = {"kind": "JOIN", "branch_ids": ["b1", "b2"], "coverage_evidence_id": "e1"}
    if rule is not None:
        effect["rule"] = rule
    return _case(
        action={"operation": "JOIN_BRANCHES", "output_id": "cl", "summary": _JOINED,
                "branch_effect": effect},
        before=_state(branches=branches),
        after=_state(branches=branches,
                     claims={"cl": _claim("cl", _JOINED, "DERIVED")}),
        evidence={"e1": {"id": "e1", "kind": "PARTITION_CERTIFICATE",
                         "status": evidence_status, "supports_rule": supports,
                         "trusted": False, "premise_ids": [],
                         "branch_ids": ["b1", "b2"]}},
    )


# `verify` and `TrustMode` are imported for the reader's benefit at the call sites above;
# `pytest` is imported because a future addition here will need it.
_ = (verify, TrustMode, pytest)
