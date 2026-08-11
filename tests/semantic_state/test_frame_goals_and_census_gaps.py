"""The goal frame (D-057), and the census survivors that a probe battery reproduced.

Two kinds of test live here, and the difference matters when reading a failure.

**D-057 — goals were outside the frame condition.** Not a missing test: a missing check.
Measured at ``3fe87ac``, ``_check_frame`` iterated claims, candidates, branches and
obligations, and simply did not mention ``goals``. So an ``OPEN`` goal could be deleted
from ``state_after`` with no discharge and no evidence, flipped to ``DISCHARGED`` with
neither, or have its proposition rewritten — every one accepted as ``VALID`` **at
RUNTIME**, while the identical three shapes on an obligation were correctly refused. The
goal is the thing being proved. This was found by the P-03 goal-ancestry investigation
rather than by the mutation census, and it could not have been found by that census: no
mutation can target a record kind that is absent from the loop.

**The census survivors.** Each remaining test was written against a *measured* surviving
mutant of production at ``3fe87ac`` and names the exact edit it pins. Each was verified
against a 219-probe differential battery: the property is observable through the public
contract, and the pristine and mutated results differ. A test whose mutant it cannot kill
is worse than none, so the mutant is quoted rather than described.
"""

from __future__ import annotations

import threading

import pytest

from hamiltonian_lang.semantic_state import (
    domains,
    neutral,
    parse_transition,
    render_transition,
    verify_replay,
    verify_runtime,
)
from hamiltonian_lang.semantic_state.neutral import import_transition
from hamiltonian_lang.semantic_state.view import ViewError

GOAL = {"id": "g0", "proposition": "the hard lemma", "status": "OPEN", "scope": "global"}


def _base() -> dict:
    """A minimal VALID derivation. Every case below is a copy with one thing changed."""
    return {
        "schema_version": "semantic-firewall-case-0.1.0",
        "case_id": "FRAME-GOALS",
        "action": {
            "id": "a0", "operation": "DERIVE", "summary": "q",
            "dependencies": ["p0"], "preconditions": [], "obligations_created": [],
            "obligations_discharged": [],
            "typing": {"input_domains": {"p0": "Integer"}, "output_domain": "Proposition"},
            "warrant": {}, "goal_effect": {}, "scope_effect": {}, "branch_effect": {},
            "candidate_effect": {}, "epistemic_effect": {}, "output_id": "c1",
        },
        "state_before": {
            "active_scopes": ["global"], "branches": {}, "candidates": {}, "goals": {},
            "obligations": {},
            "claims": {"p0": {"id": "p0", "proposition": "n > 0", "status": "GIVEN",
                              "scope": "global", "dependencies": [], "domain": "Natural"}},
        },
        "state_after": {
            "active_scopes": ["global"], "branches": {}, "candidates": {}, "goals": {},
            "obligations": {},
            "claims": {
                "p0": {"id": "p0", "proposition": "n > 0", "status": "GIVEN",
                       "scope": "global", "dependencies": [], "domain": "Natural"},
                "c1": {"id": "c1", "proposition": "q", "status": "DERIVED",
                       "scope": "global", "dependencies": ["p0"], "domain": "Proposition"},
            },
        },
        "evidence": {},
        "source": {"origin": "synthetic", "rationale": "frame/goals"},
    }


def _verdict(payload: dict, runtime: bool = False) -> tuple[str, str | None]:
    transition = import_transition(payload)
    result = verify_runtime(transition) if runtime else verify_replay(transition)
    return str(result.verdict), result.error_class


# ---------------------------------------------------------------------------
# D-057 -- the goal frame
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("runtime", [False, True], ids=["replay", "runtime"])
def test_an_open_goal_may_not_simply_vanish(runtime):
    """The mutant is the absence of ``("goals", ...)`` from ``_check_frame``'s loop.

    An unproven goal disappearing is the one thing a proof checker exists to refuse. It was
    accepted in both trust modes.
    """
    payload = _base()
    payload["state_before"]["goals"] = {"g0": dict(GOAL)}
    payload["state_after"]["goals"] = {}
    assert _verdict(payload, runtime)[0] == "INVALID"


@pytest.mark.parametrize("runtime", [False, True], ids=["replay", "runtime"])
def test_a_goal_may_not_be_discharged_without_declaring_a_goal_effect(runtime):
    """``OPEN -> DISCHARGED`` with no ``goal_effect``, no evidence and no warrant.

    Undeclared, so ``_check_goal_discharge`` never runs: it keys on
    ``goal_effect.kind == "DISCHARGE"``. Without the frame nothing else looked.
    """
    payload = _base()
    payload["state_before"]["goals"] = {"g0": dict(GOAL)}
    payload["state_after"]["goals"] = {"g0": {**GOAL, "status": "DISCHARGED"}}
    assert _verdict(payload, runtime)[0] == "INVALID"


def test_a_goals_proposition_may_not_be_rewritten_in_place():
    """Moving the goalposts: prove an easier statement, record it against the hard one."""
    payload = _base()
    payload["state_before"]["goals"] = {"g0": dict(GOAL)}
    payload["state_after"]["goals"] = {"g0": {**GOAL, "proposition": "something easier"}}
    assert _verdict(payload)[0] == "INVALID"


def test_a_goal_may_not_materialise_unlicensed():
    """No action can declare that it creates subgoals, so a new goal is refused.

    This is the honest state of the vocabulary rather than a judgement about goal creation:
    HML does not represent it (D-056), and fail-closed is the correct reading of a
    structure the language cannot express. The corpus contains zero goal-creating
    transitions in 631, so nothing legitimate is refused.
    """
    payload = _base()
    payload["state_after"]["goals"] = {"g9": dict(GOAL)}
    assert _verdict(payload)[0] == "INVALID"


def test_a_declared_discharge_of_the_named_goal_is_still_accepted():
    """The frame must not forbid the transition the system exists to make.

    Guards the repair against over-strictness: ``FX-GOL-LEGAL`` is exactly this shape, and
    a frame that refused it would have broken the frozen thirty.
    """
    payload = _base()
    payload["action"]["goal_effect"] = {"goal_id": "g0", "kind": "DISCHARGE"}
    payload["action"]["summary"] = GOAL["proposition"]
    payload["state_before"]["goals"] = {"g0": dict(GOAL)}
    payload["state_after"]["goals"] = {"g0": {**GOAL, "status": "DISCHARGED"}}
    payload["state_after"]["claims"]["c1"]["proposition"] = GOAL["proposition"]
    assert _verdict(payload) == ("VALID", None)


def test_a_goal_effect_may_not_license_a_goal_it_does_not_name():
    """``kind`` alone licenses nothing; the effect must say *which* goal it acts on.

    Otherwise an action moves any goal it likes by mentioning the channel. The mutant is
    ``return True`` in the ``goals`` branch of ``_licensed_change``.
    """
    payload = _base()
    payload["action"]["goal_effect"] = {"kind": "DISCHARGE"}       # no goal_id
    payload["state_before"]["goals"] = {"g0": dict(GOAL)}
    payload["state_after"]["goals"] = {"g0": {**GOAL, "status": "DISCHARGED"}}
    assert _verdict(payload)[0] == "INVALID"


# ---------------------------------------------------------------------------
# Census survivors, each with its measured mutant
# ---------------------------------------------------------------------------


def test_an_obligation_claimed_discharged_must_actually_be_discharged():
    """M049: ``if str(settled.status) != "DISCHARGED":`` -> ``if False and ...``.

    The action says it discharged ``ob1``; ``ob1`` is still ``OPEN`` in the resulting
    state. Accepted as VALID before this test existed.
    """
    payload = _base()
    payload["action"]["obligations_discharged"] = ["ob1"]
    open_ob = {"id": "ob1", "proposition": "the denominator is non-zero", "status": "OPEN",
               "mandatory": True, "origin": "probe", "dependencies": [],
               "discharge_evidence_id": None}
    payload["state_before"]["obligations"] = {"ob1": dict(open_ob)}
    payload["state_after"]["obligations"] = {"ob1": dict(open_ob)}
    assert _verdict(payload) == ("INVALID", "OBLIGATION_DROP")


def test_visible_enforces_scope_membership():
    """M119: ``return claim.scope in self.active_scopes`` -> ``return True``.

    ``visible`` is the scope boundary itself. With it constant-true every claim in the
    bundle is citable from anywhere, which is the whole of scope containment.
    """
    payload = _base()
    payload["state_before"]["claims"]["hidden"] = {
        "id": "hidden", "proposition": "a branch-local fact", "status": "GIVEN",
        "scope": "a_dead_scope", "dependencies": [], "domain": "Integer"}
    state = import_transition(payload).state_before
    assert state.visible("p0") is True
    assert state.visible("hidden") is False
    assert state.visible("no_such_claim") is False


def test_a_domain_entry_without_justification_is_refused():
    """M124: the ``justification.strip()`` guard in ``_register`` -> ``if False``.

    Provenance for a containment edge is the reason the lattice may be trusted at all.
    """
    with pytest.raises(RuntimeError):
        domains._register(domains.DomainEntry(
            name="ProbeNoJustification", parent="Integer", version=1,
            justification="", provenance="test"))
    assert "ProbeNoJustification" not in domains.DOMAINS


def test_a_domain_may_not_be_silently_re_registered():
    """M127: the ``entry.name in DOMAINS`` guard in ``_register`` -> ``if False``.

    Re-registration replaces a containment edge in place, so a later import could quietly
    change what every earlier domain judgement meant.
    """
    before = domains.DOMAINS["Integer"]
    with pytest.raises(RuntimeError):
        domains._register(domains.DomainEntry(
            name="Integer", parent=None, version=99,
            justification="test", provenance="test"))
    assert domains.DOMAINS["Integer"] is before


def test_inhabits_terminates_on_a_cyclic_lattice():
    """M123: ``while (entry := ...) is not None and current not in seen:`` loses its guard.

    ``_assert_acyclic`` runs at import and forbids a cycle, and M125 removes *that* — so
    each guard hides the other and a one-at-a-time census can never see either. The cycle
    is injected straight into the table so this test does not depend on the import check.

    Run on a worker with a deadline rather than called directly: without the guard this
    does not raise, it **never returns**, and a test that detects non-termination by
    hanging stops the suite instead of failing it. The census recorded exactly that —
    ``TIMEOUT`` rather than ``KILLED`` — which is a far weaker signal than a red test.
    """
    saved = dict(domains.DOMAINS)
    result: list[object] = []

    def _call() -> None:
        result.append(domains.inhabits("CycA", "Integer"))

    try:
        domains.DOMAINS["CycA"] = domains.DomainEntry(
            name="CycA", parent="CycB", version=1, justification="t", provenance="t")
        domains.DOMAINS["CycB"] = domains.DomainEntry(
            name="CycB", parent="CycA", version=1, justification="t", provenance="t")
        worker = threading.Thread(target=_call, daemon=True)
        worker.start()
        worker.join(timeout=10)
        assert not worker.is_alive(), (
            "inhabits() did not terminate on a cyclic lattice within 10s"
        )
        assert result == [False]
    finally:
        domains.DOMAINS.clear()
        domains.DOMAINS.update(saved)


def test_an_unterminated_quoted_name_in_an_identifier_list_is_refused():
    """M137: the ``if in_string:`` guard at the end of ``_split_idents`` -> ``if False``.

    ``_split_idents`` splits a comma list without cutting a quoted name in half, so the
    unterminated case is *its* business and not ``_read_ident``'s — an unterminated quote
    in a claim name is caught elsewhere, which is why this has to attack a `depends` list.
    """
    good = render_transition(import_transition(_base()))
    assert "depends p0" in good
    with pytest.raises(ViewError):
        parse_transition(good.replace("depends p0", 'depends "p0'))


def test_a_schema_line_outside_the_transition_header_is_refused():
    """M142: ``if line.depth != 1 and line.keyword in ("schema", "source"):`` -> ``if False``.

    A second ``schema`` line at depth 0 is not a header line, and without the guard it is
    read as one — silently replacing the schema version the document declared, which is the
    field every downstream compatibility decision keys on.
    """
    good = render_transition(import_transition(_base()))
    with pytest.raises(ViewError):
        parse_transition(good + '\nschema "a-different-schema-version"\n')
    with pytest.raises(ViewError):
        parse_transition(good + '\nsource {"origin": "elsewhere"}\n')


def test_the_lattice_is_checked_acyclic():
    """M125: the module-level ``_assert_acyclic()`` call is deleted.

    Pinned as a property of the function rather than of import order, so the check cannot
    be satisfied by an assertion that never runs.
    """
    saved = dict(domains.DOMAINS)
    try:
        domains.DOMAINS["CycC"] = domains.DomainEntry(
            name="CycC", parent="CycD", version=1, justification="t", provenance="t")
        domains.DOMAINS["CycD"] = domains.DomainEntry(
            name="CycD", parent="CycC", version=1, justification="t", provenance="t")
        with pytest.raises(RuntimeError):
            domains._assert_acyclic()
    finally:
        domains.DOMAINS.clear()
        domains.DOMAINS.update(saved)


@pytest.mark.parametrize("kind,extra", [
    ("branches", {"proposition": "case A", "status": "CLOSED", "scope": "global",
                  "conclusion": "q"}),
    ("goals", {"proposition": "show q", "status": "OPEN", "scope": "global"}),
    ("candidates", {"proposition": "q", "status": "UNVERIFIED", "scope": "global",
                    "constraints": []}),
    ("obligations", {"proposition": "d != 0", "status": "OPEN", "mandatory": True,
                     "origin": "probe", "dependencies": [],
                     "discharge_evidence_id": None}),
])
def test_the_export_preserves_the_dictionary_key_not_the_payload_id(kind, extra):
    """M110 / X1 / X2 / X3: ``state.<kind>.items()`` -> ``((r.id, r) for r in ...values())``.

    The neutral schema lets a record's own ``id`` differ from the key it is filed under, and
    an action cites the **key**. Re-keying the export on the payload-controlled ``record.id``
    silently renames every record, so a citation that resolved before the round trip does
    not resolve after it (D-053).
    """
    payload = _base()
    for state in ("state_before", "state_after"):
        payload[state][kind] = {"KEY": {"id": "A_DIFFERENT_ID", **extra}}
    exported = neutral.export_transition(import_transition(payload))
    assert sorted(exported["state_before"][kind]) == ["KEY"]


@pytest.mark.parametrize("ident", ["p0,x", 'p0"x', "{p0}"])
def test_an_unquotable_bare_name_is_refused_on_readback(ident):
    """M140: the ``_BARE.match(token)`` guard in ``_read_ident`` -> ``if False``.

    Without it the parser accepts a token the renderer could never have emitted bare, so a
    hand-edited view is read back as something the grammar does not license.
    """
    good = render_transition(import_transition(_base()))
    with pytest.raises(ViewError):
        parse_transition(good.replace("claim p0", f"claim {ident}"))


def test_a_promotion_whose_label_contradicts_its_effect_is_refused_in_replay():
    """H052: the label/effect agreement check on promotion is removed.

    ``operation`` and ``candidate_effect.kind`` disagree, and under ``OFFLINE_REPLAY`` the
    operation label is still the evidence rule (P-01, D-054), so the disagreement is
    load-bearing exactly here.
    """
    payload = _base()
    payload["action"]["operation"] = "SOMETHING_ELSE"
    payload["action"]["candidate_effect"] = {"candidate_id": "k1", "kind": "PROMOTE",
                                             "evidence_id": "e1"}
    payload["state_before"]["candidates"] = {
        "k1": {"id": "k1", "proposition": "q", "status": "UNVERIFIED", "scope": "global",
               "constraints": []}}
    payload["state_after"]["candidates"] = {
        "k1": {"id": "k1", "proposition": "q", "status": "VERIFIED", "scope": "global",
               "constraints": []}}
    payload["evidence"] = {"e1": {"id": "e1", "kind": "PROOF", "status": "VALID",
                                  "supports_rule": "SOMETHING_ELSE", "payload": {}}}
    assert _verdict(payload) == ("INVALID", "CANDIDATE_PROMOTION")


@pytest.mark.parametrize("site", ["typed_input", "candidate"])
def test_an_unknown_the_action_actually_consults_makes_the_transition_unresolved(site):
    """M003 / M004 / M010: relevance sources dropped from ``_relevant``, and the candidate
    UNKNOWN test disabled.

    UNKNOWN is fail-closed, and relevance is what keeps that from being a denial of
    service. Dropping a relevance *source* is the dangerous direction: the unknown stops
    being consulted and the transition is accepted outright.
    """
    payload = _base()
    if site == "typed_input":
        payload["action"]["dependencies"] = []
        payload["action"]["typing"]["input_domains"] = {"pX": "Integer"}
        payload["state_after"]["claims"]["c1"]["dependencies"] = []
        for state in ("state_before", "state_after"):
            payload[state]["claims"]["pX"] = {
                "id": "pX", "proposition": "unknown thing", "status": "UNKNOWN",
                "scope": "global", "dependencies": [], "domain": "Integer"}
    else:
        payload["action"]["candidate_effect"] = {"candidate_id": "k1", "kind": "OPEN"}
        for state in ("state_before", "state_after"):
            payload[state]["candidates"] = {
                "k1": {"id": "k1", "proposition": "maybe", "status": "UNKNOWN",
                       "scope": "global", "constraints": []}}
    assert _verdict(payload)[0] == "UNRESOLVED"


def test_an_unknown_branch_status_is_unresolved_and_not_merely_invalid():
    """M011: the branch UNKNOWN test is disabled.

    The distinction is the point of a three-valued verdict: with the test gone the
    transition is refused as ``INVALID``, which asserts the join is *wrong* when the truth
    is that its branch cannot be read. Recording a definite verdict on unreadable input is
    a different failure from missing the refusal, and a weaker test that only asserted
    "not VALID" would not see it.
    """
    payload = _base()
    payload["action"]["branch_effect"] = {"branch_ids": ["b1"], "kind": "JOIN",
                                          "coverage_evidence_id": "e_cov"}
    for state in ("state_before", "state_after"):
        payload[state]["branches"] = {
            "b1": {"id": "b1", "proposition": "case A", "status": "UNKNOWN",
                   "scope": "global", "conclusion": "q"}}
    payload["evidence"] = {"e_cov": {"id": "e_cov", "kind": "PARTITION", "status": "VALID",
                                     "supports_rule": "DERIVE",
                                     "payload": {"branch_ids": ["b1"]}}}
    assert _verdict(payload) == ("UNRESOLVED", None)
