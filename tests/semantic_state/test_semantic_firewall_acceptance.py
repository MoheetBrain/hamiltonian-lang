"""Production HML against the 30 frozen Semantic Firewall acceptance fixtures.

The fixtures live in the research corpus, which is a sibling repository rather than a
dependency, so this skips when it is absent instead of failing. That is the right trade:
a clean clone of this repo must not fail for lacking a checkout it never declared, and a
developer who *has* the corpus gets the real check.

**The fixtures are never modified.** They are the acceptance criteria; editing one because
production HML disagrees with it would convert a failed test into a passed one without
changing any behaviour, which is the whole failure mode the frozen manifest exists to
prevent.

Two properties are asserted, and they are different:

* the verifier reaches the same verdict and error class as the frozen reference checker;
* the neutral adapter round-trips every fixture byte-for-byte, which is how "lossless"
  (SF-R03) is *checked* rather than claimed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hamiltonian_lang.semantic_state import (
    export_transition,
    import_transition,
    replay_payload,
)

CORPUS = Path("/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus")
FIXTURES = CORPUS / "experiments" / "semantic_firewall" / "acceptance" / "fixtures.json"

#: Record-level keys the adapter carries as provenance rather than interpreting.
_PROVENANCE = {"pair_id", "split", "semantic_focus"}
_STRUCTURAL = {
    "action", "case_id", "evidence", "schema_version", "source",
    "state_after", "state_before",
}


def _fixtures():
    if not FIXTURES.exists():
        pytest.skip(f"research corpus not present at {CORPUS}")
    return json.loads(FIXTURES.read_text())["fixtures"]


def _ids(fx):
    return [f["fixture_id"] for f in fx]


def test_the_fixture_set_is_the_expected_frozen_thirty():
    """Guards against silently testing a different or truncated fixture file."""
    fx = _fixtures()
    assert len(fx) == 30
    assert len({f["invariant"] for f in fx}) == 10
    assert sorted(f["boundary"] for f in fx).count("LEGAL") == 10


@pytest.mark.parametrize("fixture", _fixtures() if FIXTURES.exists() else [], ids=lambda f: f["fixture_id"])
def test_production_hml_matches_the_reference_checker(fixture):
    result = replay_payload(fixture["case"])
    assert str(result.verdict) == fixture["expected_reference_result"], (
        f"{fixture['fixture_id']}: {result.to_dict()}"
    )
    if fixture["expected_reference_result"] == "INVALID":
        assert result.error_class == fixture["expected_error_class"], (
            f"{fixture['fixture_id']}: {result.to_dict()}"
        )


@pytest.mark.parametrize("fixture", _fixtures() if FIXTURES.exists() else [], ids=lambda f: f["fixture_id"])
def test_the_neutral_adapter_round_trips_losslessly(fixture):
    case = fixture["case"]
    extras = {k: v for k, v in case.items() if k not in _STRUCTURAL}
    assert set(extras) <= _PROVENANCE, f"unmodelled record-level key: {sorted(extras)}"
    back = export_transition(import_transition(case), extras=extras)
    assert json.dumps(back, sort_keys=True) == json.dumps(case, sort_keys=True)


def test_the_six_previously_inexpressible_fixtures_are_now_handled():
    """The stated goal of this build, asserted by name rather than by a count.

    A count would pass if some other fixture regressed and one of these started working.
    """
    fx = {f["fixture_id"]: f for f in _fixtures()}
    for fid in (
        "FX-CAN-LEGAL", "FX-CAN-ILLEGAL", "FX-CAN-UNKNOWN",
        "FX-BRN-LEGAL", "FX-BRN-ILLEGAL", "FX-BRN-UNKNOWN",
    ):
        assert fx[fid]["current_hml_support"] == "CURRENT_HML_NOT_EXPRESSIBLE", (
            f"{fid} is no longer recorded as inexpressible; the corpus assessment moved"
        )
        result = replay_payload(fx[fid]["case"])
        assert str(result.verdict) == fx[fid]["expected_reference_result"], fid
