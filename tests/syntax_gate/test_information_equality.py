"""All four candidate surfaces must carry identical mathematical information.

This is the fairness property the whole tournament rests on. If candidate D's JSON
resolves an ambiguity that candidate C must infer, D wins for a reason that has nothing
to do with model acquisition, and the result is worthless.

The oracle is the content hash from `backends/canonical.py`: alpha-normalised, names
excluded. String equality is the wrong test -- rendering strips comments and normalises
layout, so the recovered text is legitimately different while the object is the same.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest
from evaluation.syntax_gate import candidates as C

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = [
    "examples/statistics/bayesian_coin.hml",
    "examples/statistics/linear_regression.hml",
    "examples/physics/kinetic_energy.hml",
    "examples/logic/quantifier_scope.hml",
]


def _hash(text: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".hml", delete=False) as t:
        t.write(text)
        path = t.name
    r = subprocess.run(
        [str(REPO / ".venv/bin/hml"), "hash", path],
        capture_output=True, text=True, cwd=REPO, timeout=120,
    )
    assert r.returncode == 0, f"hml hash failed: {r.stderr}"
    return r.stdout.strip()


@pytest.mark.parametrize("rel", EXAMPLES)
def test_every_surface_recovers_the_same_canonical_object(rel: str):
    path = REPO / rel
    if not path.is_file():
        pytest.skip(f"{rel} not present")
    source = path.read_text()
    expected = _hash(source)

    adapters = C.resolve_adapters()
    measured = 0
    for cid, adapter in adapters.items():
        if adapter is None:
            continue  # not built yet is NOT MEASURED, never a silent pass
        outcome = adapter.parse(adapter.render(source))
        assert outcome.ok, f"{cid} failed to parse its own rendering: {outcome.diagnostics}"
        assert outcome.hml_l1, f"{cid} produced no HML-L1 normalisation"
        assert _hash(outcome.hml_l1) == expected, (
            f"{cid} recovered a DIFFERENT canonical object. Either the renderer loses "
            f"information or the importer invents it; both invalidate the tournament."
        )
        measured += 1
    assert measured >= 1, "no adapter resolved; the test would otherwise pass vacuously"


def test_all_four_candidates_resolve():
    """A candidate silently resolving to None would drop out of the tournament unnoticed."""
    availability = C.adapter_availability()
    assert len(availability) == 4, availability
    unavailable = {k: v for k, v in availability.items() if not v.startswith("available")}
    assert not unavailable, f"candidates not built: {unavailable}"
