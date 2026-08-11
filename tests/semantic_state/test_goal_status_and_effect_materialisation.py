"""D-059: the three omissions the goal record carried after D-057 closed its frame.

D-057 brought `goals` inside the frame condition. This module closes what that repair did
not reach, all three found by an omission audit that enumerated the model rather than the
verifier — the same method, applied to the enumerations D-057 did not touch.

**(a) A declared discharge did not have to be performed.** The frame licenses a goal to
change *because* `goal_effect` names it. Nothing then checked that the licensed change was
the one declared, so an action could declare `kind: DISCHARGE`, produce the right claim, and
leave the goal `OPEN` — VALID in both trust modes. The identical shape on an obligation was
already refused (`OBLIGATION_DROP`), which is what makes this an omission rather than a
judgement.

**(b) `Goal.status` was the only record status in the model that was a bare `str`.** Claims,
candidates, branches and obligations each validated theirs through `_enum` at the import
boundary; goals validated nothing, in all three enforcement paths — the neutral adapter, the
renderer and the view parser. Measured at `136cdb9`: goals accepted all 20 probed values
including `''`, `'open'` and `'DISCHARGED '`; every other kind refused all 16 foreign ones.

**(c) `_collect_unknowns` enumerated claims, candidates and branches — not goals or
obligations.** An action citing one whose status could not be read was answered `INVALID`,
a definite verdict on unreadable input, where the same shape elsewhere is `UNRESOLVED`. Not
fail-open, but it converts a non-answer into a detection, and the third verdict exists
precisely to keep those apart.
"""

from __future__ import annotations

import copy

import pytest

from hamiltonian_lang.semantic_state import model as M
from hamiltonian_lang.semantic_state import neutral, verify_replay, verify_runtime
from hamiltonian_lang.semantic_state.neutral import NeutralImportError, import_transition

GOAL_PROPOSITION = "the hard lemma"


def _payload() -> dict:
    """A VALID derivation carrying one goal, exported through the production adapter.

    Built from model objects rather than a hand-written dict so the field names cannot
    drift from the schema this test claims to be about.
    """
    p0 = M.Claim(id="p0", proposition="n > 0", status=M.ClaimStatus.GIVEN, scope="global",
                 domain="Natural")
    c1 = M.Claim(id="c1", proposition=GOAL_PROPOSITION, status=M.ClaimStatus.DERIVED,
                 scope="global", domain="Proposition", dependencies=("p0",))
    goal = M.Goal(id="g0", proposition=GOAL_PROPOSITION, status=M.GoalStatus.OPEN)
    action = M.Action(id="a0", operation="DERIVE", summary=GOAL_PROPOSITION, output_id="c1",
                      dependencies=("p0",),
                      typing={"input_domains": {"p0": "Integer"},
                              "output_domain": "Proposition"},
                      goal_effect={"goal_id": "g0", "kind": "DISCHARGE"})
    t = M.Transition(
        case_id="D059", action=action,
        state_before=M.SemanticState(claims={"p0": p0}, goals={"g0": goal},
                                     active_scopes=("global",)),
        state_after=M.SemanticState(
            claims={"p0": p0, "c1": c1},
            goals={"g0": M.Goal(id="g0", proposition=GOAL_PROPOSITION,
                                status=M.GoalStatus.DISCHARGED)},
            active_scopes=("global",)),
        evidence={}, schema_version="semantic-firewall-case-0.1.0",
        source={"origin": "synthetic", "rationale": "D-059"})
    return neutral.export_transition(t)


def _verdict(payload: dict, runtime: bool = False) -> tuple[str, str | None]:
    t = import_transition(payload)
    r = verify_runtime(t) if runtime else verify_replay(t)
    return str(r.verdict), r.error_class


# ---------------------------------------------------------------------------
# (a) a declared effect must materialise
# ---------------------------------------------------------------------------


def test_the_baseline_discharge_is_valid():
    """Guards the other tests: if this ever fails they are all vacuous."""
    assert _verdict(_payload()) == ("VALID", None)


@pytest.mark.parametrize("runtime", [False, True], ids=["replay", "runtime"])
def test_a_declared_discharge_must_leave_the_goal_discharged(runtime):
    """The mutant is deleting the `settled.status != "DISCHARGED"` block from
    `_check_goal_discharge`. Declaring a discharge is not performing one.
    """
    payload = _payload()
    payload["state_after"]["goals"]["g0"]["status"] = "OPEN"
    assert _verdict(payload, runtime) == ("INVALID", "FALSE_GOAL_DISCHARGE")


def test_a_declared_discharge_may_not_delete_the_goal_instead():
    """A goal is discharged, not deleted.

    Distinct from the frame check: here the effect *is* declared, so the frame licenses the
    change and would not object on its own.
    """
    payload = _payload()
    del payload["state_after"]["goals"]["g0"]
    assert _verdict(payload)[0] == "INVALID"


def test_an_unreadable_outcome_is_unresolved_and_not_a_false_discharge():
    """`UNKNOWN` must not be reported as a detected false discharge.

    The three-valued discipline is the point: this transition is not *wrong*, it is
    unreadable, and a verifier that called it INVALID would be claiming knowledge it does
    not have.
    """
    payload = _payload()
    payload["state_after"]["goals"]["g0"]["status"] = "UNKNOWN"
    assert _verdict(payload) == ("UNRESOLVED", None)


# ---------------------------------------------------------------------------
# (b) the goal status enum
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["OPEN", "DISCHARGED", "UNKNOWN"])
def test_every_goal_status_the_enum_admits_is_importable(value):
    payload = _payload()
    for state in ("state_before", "state_after"):
        payload[state]["goals"]["g0"]["status"] = value
    import_transition(payload)


@pytest.mark.parametrize("value", [
    "NOT_A_STATUS_AT_ALL", "", "open", "DISCHARGED ", "VERIFIED", "CLOSED", "FAILED",
])
def test_a_goal_status_outside_the_enum_is_refused_at_the_boundary(value):
    """Goals were the one record kind whose status bypassed `_enum`.

    `'open'` and `'DISCHARGED '` are in this list deliberately: a case or whitespace slip
    silently became a distinct status, and every other record kind already refused both.
    """
    payload = _payload()
    for state in ("state_before", "state_after"):
        payload[state]["goals"]["g0"]["status"] = value
    with pytest.raises(NeutralImportError):
        import_transition(payload)


def test_the_goal_status_survives_the_neutral_round_trip():
    payload = _payload()
    exported = neutral.export_transition(import_transition(payload))
    assert exported["state_before"]["goals"]["g0"]["status"] == "OPEN"
    assert exported["state_after"]["goals"]["g0"]["status"] == "DISCHARGED"
    assert exported == payload


def test_the_goal_status_survives_the_view_round_trip():
    """The renderer emitted the status quoted, unlike every other record kind.

    Left alone that is merely inconsistent; combined with a parser that read it back as
    free text it is how an unvalidated value would have survived a supposedly lossless
    round trip.
    """
    from hamiltonian_lang.semantic_state import parse_transition, render_transition

    t = import_transition(_payload())
    back = parse_transition(render_transition(t))
    assert back.state_after.goals["g0"].status is M.GoalStatus.DISCHARGED
    assert neutral.export_transition(back) == neutral.export_transition(t)


# ---------------------------------------------------------------------------
# (c) UNKNOWN relevance for goals and obligations
# ---------------------------------------------------------------------------


def test_an_unknown_goal_the_action_cites_is_unresolved():
    payload = _payload()
    for state in ("state_before", "state_after"):
        payload[state]["goals"]["g0"]["status"] = "UNKNOWN"
    assert _verdict(payload) == ("UNRESOLVED", None)


def test_an_unknown_obligation_the_action_discharges_is_unresolved():
    payload = _payload()
    payload["action"]["obligations_discharged"] = ["ob1"]
    unknown = {"id": "ob1", "proposition": "d != 0", "status": "UNKNOWN",
               "mandatory": True, "origin": "test", "dependencies": [],
               "discharge_evidence_id": None}
    for state in ("state_before", "state_after"):
        payload[state]["obligations"] = {"ob1": dict(unknown)}
    assert _verdict(payload)[0] == "UNRESOLVED"


@pytest.mark.parametrize("kind,record", [
    ("goals", {"id": "z", "proposition": "an unrelated goal", "status": "UNKNOWN",
               "scope": "global"}),
    ("obligations", {"id": "z", "proposition": "an unrelated obligation",
                     "status": "UNKNOWN", "mandatory": False, "origin": "test",
                     "dependencies": [], "discharge_evidence_id": None}),
])
def test_an_unknown_record_the_action_never_cites_does_not_disable_the_verifier(kind, record):
    """Relevance scoping, the other half of D-049.

    Widening UNKNOWN collection to two more record kinds is only safe if it stays scoped to
    what the action consults. Unscoped, one junk record turns every INVALID into UNRESOLVED,
    which is a total detection bypass — that is measured, not hypothetical.
    """
    payload = _payload()
    for state in ("state_before", "state_after"):
        payload[state][kind] = {**payload[state].get(kind, {}), "z": copy.deepcopy(record)}
    assert _verdict(payload) == ("VALID", None)
