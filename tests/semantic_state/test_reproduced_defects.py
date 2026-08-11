"""The four defects an independent audit reproduced against `a21fdb7` (D-053).

Each was measured on pristine production code before repair, and none of the thirty frozen
acceptance fixtures could detect any of them — every fixture has at most one branch scope
active, keys that equal their record ids, well-typed fields, and branch conclusions that are
already present. This is the fourth consecutive time a 30/30 pass rate has concealed real
defects.

Two of these are attacks that need **no forged evidence at all**: a duplicated entry in
`active_scopes`, and a join over branches that concluded nothing.
"""

from __future__ import annotations

import copy
import json

import pytest

from hamiltonian_lang.semantic_state import (
    export_transition,
    import_transition,
    verify_replay,
    verify_runtime,
)
from hamiltonian_lang.semantic_state.neutral import NeutralImportError

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


# ---------------------------------------------------------------------------
# A. Scope is containment, derived from the branch tree — never list position
# ---------------------------------------------------------------------------


def _scoped(scopes, premise_scope, conclusion_scope, branches):
    p = {"id": "p", "proposition": "q", "status": "ASSUMED",
         "scope": premise_scope, "dependencies": []}
    c = {"id": "c", "proposition": "q", "status": "DERIVED",
         "scope": conclusion_scope, "dependencies": ["p"]}
    state = lambda claims: {  # noqa: E731
        "active_scopes": list(scopes), "branches": branches,
        "candidates": {}, "goals": {}, "obligations": {}, "claims": claims,
    }
    return {
        "schema_version": SCHEMA, "case_id": "SCOPE",
        "action": {**copy.deepcopy(_ACTION), "dependencies": ["p"], "output_id": "c"},
        "state_before": state({"p": p}), "state_after": state({"p": p, "c": c}),
        "evidence": {}, "source": {},
    }


def _branches(**parents):
    return {k: {"id": k, "predicate": "x", "status": "OPEN", "scope": v}
            for k, v in parents.items()}


def test_sibling_scopes_behave_symmetrically():
    """The defect: identical situations got opposite verdicts from list order alone.

    `branch:a` and `branch:b` are both children of `global`. Neither contains the other, so
    a conclusion may not cross between them in *either* direction.
    """
    siblings = _branches(a=None, b=None)
    forward = verify_replay(import_transition(
        _scoped(["global", "branch:a", "branch:b"], "branch:a", "branch:b", siblings)))
    mirror = verify_replay(import_transition(
        _scoped(["global", "branch:a", "branch:b"], "branch:b", "branch:a", siblings)))
    assert str(forward.verdict) == str(mirror.verdict) == "INVALID"
    assert forward.error_class == mirror.error_class == "SCOPE_LEAK"


def test_the_verdict_does_not_depend_on_the_order_of_active_scopes():
    siblings = _branches(a=None, b=None)
    one = verify_replay(import_transition(
        _scoped(["global", "branch:a", "branch:b"], "branch:a", "branch:b", siblings)))
    other = verify_replay(import_transition(
        _scoped(["global", "branch:b", "branch:a"], "branch:a", "branch:b", siblings)))
    assert str(one.verdict) == str(other.verdict)


def test_genuine_nesting_is_directional():
    """Containment must still *work*: narrowing is fine, widening is a leak."""
    nested = _branches(a=None, b="branch:a")  # b sits inside a
    narrowing = verify_replay(import_transition(
        _scoped(["global", "branch:a", "branch:b"], "branch:a", "branch:b", nested)))
    widening = verify_replay(import_transition(
        _scoped(["global", "branch:a", "branch:b"], "branch:b", "branch:a", nested)))
    assert str(narrowing.verdict) == "VALID", narrowing.to_dict()
    assert widening.error_class == "SCOPE_LEAK"


def test_a_duplicated_active_scope_fails_closed():
    """The worst of the four: a complete scope bypass needing no forged evidence.

    `index` returns the *first* occurrence, so prepending a copy of an inner frame made it
    look outermost and let any premise escape to `global`.
    """
    escape = _scoped(["global", "branch:x"], "branch:x", "global", _branches(x=None))
    assert verify_replay(import_transition(escape)).error_class == "SCOPE_LEAK"

    attack = _scoped(["branch:x", "global", "branch:x"], "branch:x", "global",
                     _branches(x=None))
    result = verify_replay(import_transition(attack))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "SCOPE_LEAK"
    # Containment alone already refuses this, because it never consults list order — so the
    # explicit duplicate guard is defence in depth rather than the load-bearing fix. It is
    # pinned on its diagnostic, which is the part a reader debugging a malformed frame list
    # actually needs, and which the containment rule cannot supply.
    assert "repeats" in result.findings[0].detail


def test_a_cyclic_scope_tree_does_not_hang_the_verifier():
    """`parents` is derived from producer-supplied data, so it may be malformed."""
    cyclic = _branches(a="branch:b", b="branch:a")
    result = verify_replay(import_transition(
        _scoped(["global", "branch:a", "branch:b"], "branch:a", "branch:b", cyclic)))
    assert str(result.verdict) in {"VALID", "INVALID"}


# ---------------------------------------------------------------------------
# B. The mapping key and the record id are distinct, and both survive
# ---------------------------------------------------------------------------


def _keyed(claims):
    return {
        "schema_version": SCHEMA, "case_id": "KEYS",
        "action": copy.deepcopy(_ACTION),
        "state_before": {**copy.deepcopy(_EMPTY), "claims": claims},
        "state_after": {**copy.deepcopy(_EMPTY), "claims": {}},
        "evidence": {}, "source": {},
    }


def test_a_record_whose_id_differs_from_its_key_round_trips_exactly():
    """`export` keyed by `record.id`, so the key namespace was destroyed on the way out."""
    case = _keyed({
        "p0": {"id": "p0", "proposition": "a", "status": "GIVEN",
               "scope": "global", "dependencies": []},
        "p1": {"id": "p_other", "proposition": "b", "status": "GIVEN",
               "scope": "global", "dependencies": []},
    })
    back = export_transition(import_transition(case))
    assert sorted(back["state_before"]["claims"]) == ["p0", "p1"]
    assert back["state_before"]["claims"]["p1"]["id"] == "p_other"
    assert json.dumps(back, sort_keys=True) == json.dumps(case, sort_keys=True)


def test_two_records_sharing_an_id_do_not_collapse():
    """They collapsed silently to one, with the survivor decided by iteration order."""
    case = _keyed({
        "k1": {"id": "same", "proposition": "a", "status": "GIVEN",
               "scope": "global", "dependencies": []},
        "k2": {"id": "same", "proposition": "b", "status": "GIVEN",
               "scope": "global", "dependencies": []},
    })
    back = export_transition(import_transition(case))
    assert len(back["state_before"]["claims"]) == 2
    assert json.dumps(back, sort_keys=True) == json.dumps(case, sort_keys=True)


def test_the_verdict_is_stable_under_the_adapters_own_round_trip():
    """It was not: `VALID` became `INVALID / DEPENDENCY_VIOLATION` after export(import(x)).

    The verifier consumes the key namespace; export emitted the id namespace. A verdict
    that changes when a document is written out and read back is not a verdict about the
    document.
    """
    case = _keyed({
        "p0": {"id": "p0", "proposition": "a", "status": "GIVEN",
               "scope": "global", "dependencies": []},
        "p1": {"id": "p_other", "proposition": "b", "status": "GIVEN",
               "scope": "global", "dependencies": []},
    })
    first = verify_replay(import_transition(case))
    second = verify_replay(import_transition(export_transition(import_transition(case))))
    assert str(first.verdict) == str(second.verdict)
    assert first.error_class == second.error_class


# ---------------------------------------------------------------------------
# C. Malformed input is refused, never raised
# ---------------------------------------------------------------------------

_BAD_VALUES = [
    None, [], {}, "oops", 0, -1, 1.5, float("nan"), float("inf"),
    [{"x": 1}], [[1], [2]], {"a": {"b": 1}}, True, [None], {1: 2}, 10**400,
]


def _fuzz_targets():
    base = {
        "schema_version": SCHEMA, "case_id": "F", "action": copy.deepcopy(_ACTION),
        "state_before": copy.deepcopy(_EMPTY), "state_after": copy.deepcopy(_EMPTY),
        "evidence": {}, "source": {},
    }
    paths = [("action", k) for k in _ACTION]
    paths += [("state_before", k) for k in _EMPTY]
    paths += [("state_after", k) for k in _EMPTY]
    paths += [("evidence",), ("source",), ("schema_version",), ("case_id",),
              ("action",), ("state_before",)]
    return base, paths


@pytest.mark.parametrize("bad", _BAD_VALUES, ids=lambda v: type(v).__name__ + str(v)[:8])
def test_no_malformed_payload_raises_from_the_verifier(bad):
    """A runtime verifier handed hostile or model-authored output must never throw.

    The audit found **15** distinct uncaught signatures, six of them inside `verify()`
    itself after a successful import. Every failure is now a controlled refusal or a
    verdict.
    """
    base, paths = _fuzz_targets()
    for path in paths:
        case = copy.deepcopy(base)
        target = case
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = bad
        for check in (verify_replay, verify_runtime):
            try:
                result = check(import_transition(case))
            except NeutralImportError:
                continue  # a refusal is the contract
            assert str(result.verdict) in {"VALID", "INVALID", "UNRESOLVED"}


def test_nan_does_not_defeat_the_frame_condition():
    """`NaN != NaN`, and the frame compares records structurally.

    A record byte-identical in both states reported "changed without a licensed state
    effect". It failed *safe*, but it is a false INVALID on any float-bearing payload, and
    the value has no place in a mathematical state. Refused at the boundary.
    """
    case = {
        "schema_version": SCHEMA, "case_id": "NAN",
        "action": {**copy.deepcopy(_ACTION), "typing": {"weight": float("nan")}},
        "state_before": copy.deepcopy(_EMPTY), "state_after": copy.deepcopy(_EMPTY),
        "evidence": {}, "source": {},
    }
    with pytest.raises(NeutralImportError, match="not a representable value"):
        import_transition(case)


def test_an_unhashable_identifier_is_refused_not_raised():
    for field in ("dependencies", "obligations_created", "obligations_discharged"):
        case = {
            "schema_version": SCHEMA, "case_id": "H",
            "action": {**copy.deepcopy(_ACTION), field: [[1], [2]]},
            "state_before": copy.deepcopy(_EMPTY), "state_after": copy.deepcopy(_EMPTY),
            "evidence": {}, "source": {},
        }
        with pytest.raises(NeutralImportError):
            import_transition(case)


# ---------------------------------------------------------------------------
# D. Coverage without conclusions is not a proof
# ---------------------------------------------------------------------------


def _join(conclusions, published="n is even or n is odd"):
    branches = {
        bid: {"id": bid, "predicate": f"case {bid}", "status": "CLOSED",
              "partition_id": "p1", **({"conclusion": c} if c is not None else {})}
        for bid, c in conclusions.items()
    }
    state = lambda claims: {  # noqa: E731
        "active_scopes": ["global"], "branches": branches, "candidates": {},
        "goals": {}, "obligations": {}, "claims": claims,
    }
    return {
        "schema_version": SCHEMA, "case_id": "JOIN",
        "action": {**copy.deepcopy(_ACTION), "operation": "JOIN_BRANCHES",
                   "output_id": "cl", "summary": published,
                   "branch_effect": {"kind": "JOIN", "branch_ids": list(conclusions),
                                     "coverage_evidence_id": "e1"}},
        "state_before": state({}),
        "state_after": state({"cl": {"id": "cl", "proposition": published,
                                     "status": "DERIVED", "scope": "global",
                                     "dependencies": []}}),
        "evidence": {"e1": {"id": "e1", "kind": "EXHAUSTIVE_PARTITION", "status": "VALID",
                            "supports_rule": "JOIN_BRANCHES", "trusted": False,
                            "premise_ids": [], "branch_ids": list(conclusions)}},
        "source": {},
    }


def test_a_join_over_null_branches_cannot_publish_an_arbitrary_claim():
    """Measured before repair: three null branches publishing `"0 = 1"` verified VALID."""
    result = verify_replay(import_transition(
        _join({"b1": None, "b2": None, "b3": None}, published="0 = 1")))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "INVALID_BRANCH_JOIN"


def test_one_null_branch_is_enough_to_block_the_join():
    result = verify_replay(import_transition(
        _join({"b1": "n is even or n is odd", "b2": None})))
    assert result.error_class == "INVALID_BRANCH_JOIN"
    # The mismatch check would also catch a null conclusion, since `None != published`. The
    # dedicated guard exists for the diagnostic: "records no conclusion" is a different
    # defect from "concluded something else", and telling them apart is the whole reason a
    # reader reads the finding.
    assert "records no conclusion" in result.findings[0].detail


def test_a_fully_concluded_agreeing_join_still_passes():
    """The repair must not forbid the transition the mechanism exists for."""
    claim = "n is even or n is odd"
    result = verify_replay(import_transition(_join({"b1": claim, "b2": claim})))
    assert str(result.verdict) == "VALID", result.to_dict()


# ---------------------------------------------------------------------------
# P-01 (D-054): evidence-rule authority lives in the typed effect channel
# ---------------------------------------------------------------------------


def _state(**over):
    out = copy.deepcopy(_EMPTY)
    out.update(over)
    return out


def _case(action=None, before=None, after=None, evidence=None):
    return {
        "schema_version": SCHEMA, "case_id": "P01",
        "action": {**copy.deepcopy(_ACTION), **(action or {})},
        "state_before": before if before is not None else copy.deepcopy(_EMPTY),
        "state_after": after if after is not None else copy.deepcopy(_EMPTY),
        "evidence": evidence or {}, "source": {},
    }


def _promotion(effect_rule=None, supports="VERIFY_CANDIDATE", operation="VERIFY_CANDIDATE"):
    effect = {"kind": "PROMOTE", "candidate_id": "k1", "evidence_id": "e1"}
    if effect_rule is not None:
        effect["rule"] = effect_rule
    cand = lambda s: {"id": "k1", "proposition": "x = 2", "status": s,  # noqa: E731
                      "scope": "global", "constraint_ids": ["c1"]}
    return _case(
        action={"operation": operation, "candidate_effect": effect},
        before=_state(candidates={"k1": cand("PROPOSED")}),
        after=_state(candidates={"k1": cand("VERIFIED")}),
        evidence={"e1": {"id": "e1", "kind": "CANDIDATE_CHECK", "status": "VALID",
                         "supports_rule": supports, "trusted": False,
                         "premise_ids": [], "checked_constraints": ["c1"]}},
    )


def test_an_effect_without_a_rule_falls_back_to_the_operation_label():
    """Backward compatibility is the whole reason the migration is safe.

    All thirty frozen fixtures rely on this fallback. Demoting the label before the effects
    could carry a rule would have left evidence matching keyed on nothing.
    """
    assert str(verify_replay(import_transition(_promotion())).verdict) == "VALID"


def test_an_explicit_effect_rule_is_authoritative():
    result = verify_replay(import_transition(
        _promotion(effect_rule="VERIFY_CANDIDATE", supports="VERIFY_CANDIDATE")))
    assert str(result.verdict) == "VALID", result.to_dict()


def test_an_explicit_effect_rule_that_the_evidence_does_not_support_is_refused():
    """The authority genuinely moved: the effect's rule decides, not the label."""
    result = verify_replay(import_transition(
        _promotion(effect_rule="SOMETHING_ELSE", supports="VERIFY_CANDIDATE")))
    assert str(result.verdict) == "INVALID", result.to_dict()
    assert result.error_class == "CANDIDATE_PROMOTION"


def test_the_effect_rule_overrides_the_label_rather_than_being_overridden_by_it():
    """Label says one thing, effect says another, evidence supports the effect.

    Under P-01 the typed channel wins. If this returned INVALID the migration would be
    cosmetic — the label would still be deciding.
    """
    result = verify_replay(import_transition(
        _promotion(effect_rule="CHECK_ROOT", supports="CHECK_ROOT")))
    assert str(result.verdict) == "VALID", result.to_dict()


def test_the_branch_join_label_never_had_authority():
    """`JOIN_BRANCHES` is compared as a string nowhere; the effect kind gates the check.

    Recorded as a test because the P-01 brief assumed both labels held authority, and only
    one ever did. A future reader planning the demotion needs to know this one is already
    done.
    """
    from pathlib import Path

    # Resolved from the repository, not by importing the module: the package re-exports
    # `verify` as a FUNCTION, which shadows the submodule of the same name.
    source = (Path(__file__).resolve().parents[2]
              / "src/hamiltonian_lang/semantic_state/verify.py").read_text()
    assert "JOIN_BRANCHES" not in source, (
        "a raw JOIN_BRANCHES string comparison has been reintroduced; branch join must key "
        "on the typed effect, not on the operation label"
    )
    assert 'kind != "JOIN"' in source
