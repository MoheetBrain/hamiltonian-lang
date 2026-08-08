"""Seed-band separation and the contamination guards on the model-facing runner.

These are the tests for the failure mode that is invisible after the fact: a pilot seed
that was already used to select the model, or a developmental screen that peeked at a
treatment arm. Neither leaves a trace in the numbers, so both are enforced mechanically.
"""

from __future__ import annotations

import pytest
from evaluation.arena.bands import (
    BANDS,
    BandError,
    assert_band,
    assert_disjoint,
    band_of,
    band_range,
)
from evaluation.arena.endpoints import contrast
from evaluation.arena.run_screen import STAGES, RunSpec, build_dev_pairs, run_screen


def test_declared_bands_do_not_overlap():
    seen: dict[int, str] = {}
    for name, (lo, hi) in BANDS.items():
        for probe in (lo, (lo + hi) // 2, hi):
            assert probe not in seen, f"{name} overlaps {seen.get(probe)} at {probe}"
            seen[probe] = name


def test_band_of_round_trips():
    for name in BANDS:
        r = band_range(name)
        assert band_of(r.start) == name
        assert band_of(r.stop - 1) == name


def test_band_of_rejects_an_undeclared_seed():
    with pytest.raises(BandError):
        band_of(1)


def test_assert_band_names_the_offender():
    with pytest.raises(BandError, match="DEV_SELECTION"):
        assert_band([300_001, 500_001], "DEV_SELECTION")


def test_assert_disjoint_catches_a_shared_seed():
    with pytest.raises(BandError, match="both"):
        assert_disjoint([1, 2, 3], "A", [3, 4], "B")


def test_pilot_and_dev_seed_windows_cannot_intersect():
    """The named stop condition, checked on the real pair sets rather than on the ranges."""
    dev = build_dev_pairs("DEV_SELECTION", "L3", 4, contrast.CONTRASTS)
    pilot = build_dev_pairs("PILOT", "L3", 4, contrast.CONTRASTS)
    assert_disjoint(
        [it.world.seed for p in dev for it in p], "DEV_SELECTION",
        [it.world.seed for p in pilot for it in p], "PILOT",
    )


def test_dev_pairs_are_balanced_across_contrast_operators():
    from collections import Counter

    pairs = build_dev_pairs("DEV_SELECTION", "L3", 4, contrast.CONTRASTS)
    counts = Counter(p[0].metrics["contrast"] for p in pairs)
    assert set(counts) == set(contrast.CONTRASTS)
    assert set(counts.values()) == {4}, "selecting on one distinction would tune the organism"


def test_developmental_screen_refuses_treatment_arms():
    """Choosing a model after seeing AST or HML performance contaminates the experiment."""
    spec = RunSpec(
        run_id="t", stage="DEV_SELECTION", band="DEV_SELECTION",
        arms=("SE", "HML"), level="L3", n_per_contrast=1, model="none",
    )
    with pytest.raises(ValueError, match="structured-English only"):
        run_screen(spec, [])


def test_stage_shapes_are_fixed():
    """A run must not be quietly resized after its numbers have been seen."""
    assert STAGES["dev"]["arms"] == ("SE",)
    assert STAGES["pilot"]["arms"] == ("SE", "AST", "HML")
    assert STAGES["dev"]["band"] == "DEV_SELECTION"
    assert STAGES["pilot"]["band"] == "PILOT"


def test_run_spec_fingerprint_pins_everything_that_must_not_drift():
    spec = RunSpec(
        run_id="t", stage="PILOT", band="PILOT", arms=("SE", "AST", "HML"),
        level="L3", n_per_contrast=4, model="m",
    )
    fp = spec.fingerprint()
    for key in (
        "arena_version", "scorer_version", "system_prompt_sha256",
        "model", "temperature", "max_tokens", "order_seed", "arms", "level",
    ):
        assert key in fp, f"{key} is not pinned by the run fingerprint"
    assert fp["temperature"] == 0.0
