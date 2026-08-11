"""Metamorphic properties: classes of correctness, not examples of it.

Every other suite here asserts a verdict on a payload someone wrote. That is exactly the
failure mode the omission audit exists to catch — the author decides what to look at, so
the check inherits the author's blind spots. These properties instead assert *relations*
that must hold across generated inputs, and the generator does not know what the verifier
checks.

Two kinds of property, and the distinction is the point:

**Semantics-preserving transformations must not change the verdict.** A bijective rename of
every identifier, a permutation of dictionary insertion order, a neutral round trip, a
render/parse round trip, an added record the action never consults. If any of these moves a
verdict, the verifier is keying on something that is not semantic.

**Semantics-changing transformations must change it predictably.** Removing a premise,
deleting a state a licence depends on, or presenting self-authored evidence at RUNTIME must
degrade the verdict, never improve it.

The one relation that must never hold in either direction is a transformation that turns a
refusal into an acceptance. ``_ordering`` below states that as a partial order and every
property is checked against it.
"""

from __future__ import annotations

import copy

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from hamiltonian_lang.semantic_state import (
    neutral,
    parse_transition,
    render_transition,
    verify_replay,
    verify_runtime,
)
from hamiltonian_lang.semantic_state.neutral import NeutralImportError, import_transition

SETTINGS = settings(max_examples=60, deadline=None,
                    suppress_health_check=[HealthCheck.too_slow])

#: Hostile but legal identifiers. The renderer must quote what the grammar cannot carry
#: bare, and the reader must give it back unchanged.
IDENT = st.one_of(
    st.text(alphabet="abcxyz_0123456789", min_size=1, max_size=6),
    st.sampled_from(["a,b", 'a"b', "a b", "a\tb", "α→β", "schema", "source", "claim",
                     "x" * 40]),
)
PROP = st.text(min_size=0, max_size=24)
SCOPE = st.sampled_from(["global", "frame1", "frame2"])
CLAIM_STATUS = st.sampled_from(["GIVEN", "ASSUMED", "DERIVED", "VERIFIED", "REFUTED"])


@st.composite
def transition_payload(draw) -> dict:
    """A structurally well-formed transition. Not necessarily a VALID one.

    Validity is deliberately not guaranteed: a property that only holds on accepted
    transitions is a property about the happy path, and the interesting metamorphic
    relations are the ones that must hold when the verdict is INVALID too.
    """
    premise = draw(IDENT)
    produced = draw(IDENT.filter(lambda x: x != premise))
    scope = draw(SCOPE)
    summary = draw(PROP)
    claim = {"id": premise, "proposition": draw(PROP), "status": draw(CLAIM_STATUS),
             "scope": scope, "dependencies": [], "domain": "Integer"}
    out = {"id": produced, "proposition": summary, "status": "DERIVED", "scope": scope,
           "dependencies": [premise], "domain": "Proposition"}
    scopes = sorted({scope, "global"})
    return {
        "schema_version": "semantic-firewall-case-0.1.0",
        "case_id": draw(IDENT),
        "action": {
            "id": "a0", "operation": "DERIVE", "summary": summary,
            "dependencies": [premise], "preconditions": [], "obligations_created": [],
            "obligations_discharged": [],
            "typing": {"input_domains": {premise: "Integer"},
                       "output_domain": "Proposition"},
            "warrant": {}, "goal_effect": {}, "scope_effect": {}, "branch_effect": {},
            "candidate_effect": {}, "epistemic_effect": {}, "output_id": produced,
        },
        "state_before": {"active_scopes": scopes, "branches": {}, "candidates": {},
                         "goals": {}, "obligations": {}, "claims": {premise: claim}},
        "state_after": {"active_scopes": scopes, "branches": {}, "candidates": {},
                        "goals": {}, "obligations": {},
                        "claims": {premise: claim, produced: out}},
        "evidence": {},
        "source": {"origin": "synthetic", "rationale": "metamorphic"},
    }


def _verdict(payload: dict, runtime: bool = False) -> tuple[str, str | None]:
    t = import_transition(payload)
    r = verify_runtime(t) if runtime else verify_replay(t)
    return str(r.verdict), r.error_class


#: How much a verdict accepts. A semantics-preserving transformation must not move a
#: transition *up* this order, and no transformation in this file may move one up.
_ORDER = {"INVALID": 0, "UNRESOLVED": 1, "VALID": 2}


# ---------------------------------------------------------------------------
# A / B -- the two representations that claim to be lossless
# ---------------------------------------------------------------------------


@SETTINGS
@given(transition_payload())
def test_the_neutral_adapter_is_lossless(payload):
    """export(import(x)) == x, for generated records rather than for fixtures."""
    assert neutral.export_transition(import_transition(payload)) == payload


@SETTINGS
@given(transition_payload())
def test_the_hml_view_round_trips(payload):
    """parse(render(t)) == t, including identifiers the grammar cannot carry bare."""
    t = import_transition(payload)
    back = parse_transition(render_transition(t))
    assert neutral.export_transition(back) == neutral.export_transition(t)


# ---------------------------------------------------------------------------
# C -- a lossless transformation cannot move the verdict
# ---------------------------------------------------------------------------


@SETTINGS
@given(transition_payload())
def test_a_round_trip_preserves_the_verdict(payload):
    direct = _verdict(payload)
    t = import_transition(payload)
    assert _verdict(neutral.export_transition(t)) == direct
    reparsed = parse_transition(render_transition(t))
    assert _verdict(neutral.export_transition(reparsed)) == direct


# ---------------------------------------------------------------------------
# D -- identifiers carry no meaning beyond their identity
# ---------------------------------------------------------------------------


@SETTINGS
@given(transition_payload(), st.integers(min_value=0, max_value=9999))
def test_a_bijective_rename_preserves_the_verdict(payload, salt):
    """Every claim id is rewritten consistently. Renaming is not a semantic act.

    A verifier whose answer depends on the *spelling* of an identifier is keying on
    something it must not, and the most likely cause is a lookup by ``record.id`` where the
    dictionary key was meant (D-053).
    """
    before = _verdict(payload)
    names = set(payload["state_after"]["claims"])
    mapping = {n: f"r{salt}_{i}" for i, n in enumerate(sorted(names))}

    renamed = copy.deepcopy(payload)
    for state in ("state_before", "state_after"):
        renamed[state]["claims"] = {
            mapping[k]: {**v, "id": mapping.get(v["id"], v["id"]),
                         "dependencies": [mapping.get(d, d) for d in v["dependencies"]]}
            for k, v in renamed[state]["claims"].items()
        }
    act = renamed["action"]
    act["dependencies"] = [mapping.get(d, d) for d in act["dependencies"]]
    act["output_id"] = mapping.get(act["output_id"], act["output_id"])
    act["typing"]["input_domains"] = {mapping.get(k, k): v
                                      for k, v in act["typing"]["input_domains"].items()}
    assert _verdict(renamed) == before


# ---------------------------------------------------------------------------
# E -- dictionary order is not information
# ---------------------------------------------------------------------------


@SETTINGS
@given(transition_payload())
def test_dictionary_insertion_order_does_not_change_the_verdict(payload):
    before = _verdict(payload)
    shuffled = copy.deepcopy(payload)
    for state in ("state_before", "state_after"):
        claims = shuffled[state]["claims"]
        shuffled[state]["claims"] = dict(reversed(list(claims.items())))
    assert _verdict(shuffled) == before


# ---------------------------------------------------------------------------
# G -- an irrelevant record must not rescue or disable a transition
# ---------------------------------------------------------------------------


@SETTINGS
@given(transition_payload())
def test_an_unconsulted_record_cannot_improve_the_verdict(payload):
    """The D-049 failure, as a property rather than as the one measured instance.

    Appending an unrelated ``UNKNOWN`` claim once turned all ten ILLEGAL fixtures from
    INVALID into UNRESOLVED — a total detection bypass, because UNRESOLVED counts as
    neither accepted nor detected. It must not weaken a refusal, and it must not
    strengthen an acceptance either.
    """
    before = _verdict(payload)
    for status in ("UNKNOWN", "GIVEN", "REFUTED"):
        noisy = copy.deepcopy(payload)
        bystander = {"id": "zz_unconsulted", "proposition": "nobody cites this",
                     "status": status, "scope": "global", "dependencies": [],
                     "domain": "Integer"}
        for state in ("state_before", "state_after"):
            noisy[state]["claims"]["zz_unconsulted"] = dict(bystander)
        assert _verdict(noisy) == before, f"an unconsulted {status} claim moved the verdict"


# ---------------------------------------------------------------------------
# H / I -- removing what the verdict rested on must never improve it
# ---------------------------------------------------------------------------


@SETTINGS
@given(transition_payload())
def test_removing_a_premise_never_improves_the_verdict(payload):
    before = _ORDER[_verdict(payload)[0]]
    stripped = copy.deepcopy(payload)
    stripped["action"]["dependencies"] = []
    stripped["state_before"]["claims"] = {}
    stripped["state_after"]["claims"] = {
        k: v for k, v in stripped["state_after"]["claims"].items()
        if k == stripped["action"]["output_id"]
    }
    assert _ORDER[_verdict(stripped)[0]] <= before


# ---------------------------------------------------------------------------
# J -- malformed input is refused, never raised and never hung
# ---------------------------------------------------------------------------


@SETTINGS
@given(transition_payload(),
       st.sampled_from(["action", "state_before", "state_after", "evidence", "claims"]),
       st.sampled_from([None, 1, "s", [], 1.5, True, float("nan"), float("inf")]))
def test_a_type_confused_field_is_a_controlled_refusal(payload, key, junk):
    """Anything the boundary refuses must refuse as ``NeutralImportError``.

    A verifier that may be handed model output must never throw: an uncontrolled exception
    is a crash in the caller's process and, worse, is not a verdict.
    """
    broken = copy.deepcopy(payload)
    if key == "claims":
        broken["state_before"]["claims"] = junk
    else:
        broken[key] = junk
    try:
        t = import_transition(broken)
    except NeutralImportError:
        return
    verify_replay(t)          # must not raise
    verify_runtime(t)


# ---------------------------------------------------------------------------
# K / L -- the trust boundary, as a property over generated evidence
# ---------------------------------------------------------------------------


@SETTINGS
@given(transition_payload(),
       st.sampled_from(["VALID", "REFUTED", "UNKNOWN", "PENDING"]))
def test_runtime_is_never_more_permissive_than_replay(payload, status):
    """Replay compatibility must not imply runtime authority.

    ``OFFLINE_REPLAY`` reads a recorded status as observed reference data. ``RUNTIME``
    ignores it entirely, because the author of the record may be the party that benefits.
    So runtime may refuse where replay accepts, and never the reverse.
    """
    attacked = copy.deepcopy(payload)
    attacked["evidence"] = {"e_self": {"id": "e_self", "kind": "PROOF", "status": status,
                                       "trusted": True, "supports_rule": "DERIVE",
                                       "payload": {}}}
    attacked["action"]["warrant"] = {"evidence_id": "e_self", "rule": "DERIVE",
                                     "premise_ids": attacked["action"]["dependencies"]}
    try:
        replay = _ORDER[_verdict(attacked)[0]]
        runtime = _ORDER[_verdict(attacked, runtime=True)[0]]
    except NeutralImportError:
        return
    assert runtime <= replay


@SETTINGS
@given(transition_payload())
def test_self_authored_evidence_never_reaches_valid_at_runtime(payload):
    """No ``status`` a producer writes about its own evidence may buy acceptance."""
    attacked = copy.deepcopy(payload)
    attacked["evidence"] = {"e_self": {"id": "e_self", "kind": "PROOF", "status": "VALID",
                                       "trusted": True, "supports_rule": "DERIVE",
                                       "payload": {}}}
    attacked["action"]["epistemic_effect"] = {"to_status": "VERIFIED",
                                              "evidence_id": "e_self", "rule": "DERIVE"}
    out = attacked["action"]["output_id"]
    attacked["state_after"]["claims"][out]["status"] = "VERIFIED"
    assert _verdict(attacked, runtime=True)[0] != "VALID"
