"""Production HML against the second-generation acceptance suite (FX2).

**FX2 is weaker evidence than the frozen thirty, and the distinction matters.** The original
fixtures were authored on the corpus side against a reference checker *before* this
implementation existed — they are external criteria. FX2 was authored by the integrator
*after* the defects it covers were known, so it cannot show the implementation was right;
it can only show that a defect found once cannot return unnoticed. Never cite a green FX2
run as external validation.

What it is for. Four consecutive audits found real defects the frozen thirty could not
detect, because every one of them has at most one branch scope active, mapping keys equal to
record ids, well-typed fields, and branch conclusions already present. The thirty are a good
sample of *well-formed* transitions and no sample at all of hostile ones.

Expectations are hand-written from the semantic contract in the suite's generator, not read
off a verifier run — generating them by execution would record what the code does rather
than what it should do.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from hamiltonian_lang.semantic_state import verify_replay, verify_runtime
from hamiltonian_lang.semantic_state.neutral import NeutralImportError, import_transition

CORPUS = Path("/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus")
SUITE = CORPUS / "experiments" / "semantic_firewall_v2" / "fixtures_v2.json"

_NONFINITE = {"nan": math.nan, "inf": math.inf, "-inf": -math.inf}


def _suite():
    if not SUITE.exists():
        pytest.skip(f"FX2 suite not present at {SUITE}")
    return json.loads(SUITE.read_text())


def _materialise(fixture: dict) -> dict:
    """Apply values RFC 8259 cannot express.

    The artifact carries these as instructions rather than literals: a `NaN` in the file
    makes the whole document unreadable to any conforming parser, which an independent Ruby
    parse confirmed before the suite was committed.
    """
    case = copy.deepcopy(fixture["case"])
    for step in fixture.get("materialise", []):
        target = case
        for key in step["path"][:-1]:
            target = target[key]
        target[step["path"][-1]] = _NONFINITE[step["set_nonfinite"]]
    return case


def _run(fixture: dict) -> tuple[str, str | None]:
    try:
        transition = import_transition(_materialise(fixture))
    except NeutralImportError:
        return "REFUSED", None
    check = verify_runtime if fixture["trust_mode"] == "RUNTIME" else verify_replay
    result = check(transition)
    return str(result.verdict), result.error_class


_FIXTURES = _suite()["fixtures"] if SUITE.exists() else []


def test_the_suite_is_the_expected_shape():
    """Guards against silently testing a truncated or different suite."""
    suite = _suite()
    assert suite["suite_version"] == "semantic-firewall-fx2-1.0.0"
    assert suite["counts"]["total"] == len(suite["fixtures"]) == 40
    ids = [f["fixture_id"] for f in suite["fixtures"]]
    assert len(set(ids)) == len(ids)
    assert all(i.startswith("FX2-") for i in ids), (
        "an FX2 id must not be able to collide with one of the frozen thirty"
    )


def test_the_suite_declares_that_it_is_not_external_evidence():
    """The honesty of the record is part of the artifact, so it is pinned like anything else.

    A future reader finding a green FX2 run must not be able to mistake it for the external
    acceptance result, and the only thing standing between them is this text.
    """
    suite = _suite()
    assert suite["authored_by"] == "integrator"
    assert "WEAKER THAN THE FROZEN THIRTY" in suite["status_of_evidence"]
    assert all(f["authored_by"] == "integrator" for f in suite["fixtures"])


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda f: f["fixture_id"])
def test_production_matches_the_hand_written_expectation(fixture):
    verdict, error_class = _run(fixture)
    assert verdict == fixture["expected_result"], (
        f"{fixture['fixture_id']}: {fixture['rationale']}"
    )
    if fixture["expected_error_class"] is not None:
        assert error_class == fixture["expected_error_class"], fixture["fixture_id"]


def test_the_trust_mode_is_load_bearing_for_the_trust_family():
    """The two TRU fixtures are the same bytes and must differ only by mode.

    If they agreed, either the runtime gate is not doing anything or replay has stopped
    replaying — and a parametrised sweep would not notice, because each fixture would still
    match its own expectation.
    """
    fx = {f["fixture_id"]: f for f in _suite()["fixtures"]}
    replay = fx["FX2-TRU-SELFVALID-REPLAY-LEGAL"]
    runtime = fx["FX2-TRU-SELFVALID-RUNTIME-ILLEGAL"]
    assert replay["case"]["action"] == runtime["case"]["action"]
    assert replay["case"]["evidence"] == runtime["case"]["evidence"]
    assert _run(replay)[0] == "VALID"
    assert _run(runtime)[0] == "INVALID"


def test_the_sibling_scope_pair_agrees_with_itself():
    """The defect these two exist for was an ASYMMETRY, which one fixture cannot detect."""
    fx = {f["fixture_id"]: f for f in _suite()["fixtures"]}
    forward = _run(fx["FX2-SCP-SIBLING-AB-ILLEGAL"])
    mirror = _run(fx["FX2-SCP-SIBLING-BA-ILLEGAL"])
    assert forward == mirror == ("INVALID", "SCOPE_LEAK")


def test_the_divergences_from_the_frozen_reference_are_declared():
    """Where production is deliberately stricter, the suite says so per fixture.

    An undeclared divergence would look like agreement, and this project has twice shipped a
    claim that production matched a reference it had quietly moved away from.
    """
    suite = _suite()
    diverging = [f for f in suite["fixtures"]
                 if f["frozen_reference_checker"] == "DIVERGES"]
    assert len(diverging) == suite["counts"]["diverges_from_frozen_reference"] == 13
    for fixture in diverging:
        assert fixture["frozen_reference_note"].strip(), fixture["fixture_id"]


def test_the_amps_derived_fixtures_carry_their_provenance_caveat():
    """They rest on a community mirror, and the artifact must keep saying so."""
    amps = [f for f in _suite()["fixtures"]
            if f["case"]["source"]["origin"] == "amps_khan"]
    assert amps, "the externally grounded candidate fixtures are missing"
    for fixture in amps:
        caveat = fixture["case"]["source"]["provenance_caveat"]
        assert "COMMUNITY MIRROR" in caveat
        assert fixture["case"]["source"]["external_file_sha256"]


def test_fx2_exercises_the_lifecycle_states_no_frozen_fixture_reaches():
    """SF-R06 requires four candidate states and the frozen suite reaches only two.

    `FX2-CAN-EXTRANEOUS-REJECTED-LEGAL` is the first externally grounded REJECTED case in
    this project — the pattern is a real one from AMPS-Khan, not an invention.
    """
    fx = {f["fixture_id"]: f for f in _suite()["fixtures"]}
    rejected = fx["FX2-CAN-EXTRANEOUS-REJECTED-LEGAL"]
    after = rejected["case"]["state_after"]["candidates"]["k_root"]
    assert after["status"] == "REJECTED"
    assert _run(rejected)[0] == "VALID"
