"""Seed bands, and the mechanical guarantee that they never overlap.

One of the named stop conditions for this programme is *any pilot seed leaking into
model-selection data*. That is a contamination failure which is invisible once it has
happened -- the numbers still look fine -- so it is enforced here rather than remembered.

| band | range | may a model see it? | purpose |
|---|---|---|---|
| `GATE` | 200 000–299 999 | **no** | offline pre-flight corpus only |
| `DEV_SELECTION` | 300 000–399 999 | yes, **SE only** | choosing the developmental model |
| `ACQUISITION` | 400 000–499 999 | yes, all arms | literal state-recovery sanity check |
| `PILOT` | 500 000–599 999 | yes, all arms | held-out representation pilot |
| `CALIBRATION_LEGACY` | 900 000–999 999 | already used | the older synthetic calibration |

`DEV_SELECTION` seeds are burned the moment a model sees them. They select the
experimental organism, so measuring on them afterwards would be measuring the thing that
was optimised. The same holds for `ACQUISITION`: those items are diagnostic, chosen to be
throwaway, and never scored as evidence.
"""

from __future__ import annotations

__all__ = ["BANDS", "band_of", "band_range", "assert_band", "assert_disjoint"]

BANDS: dict[str, tuple[int, int]] = {
    "GATE": (200_000, 299_999),
    "DEV_SELECTION": (300_000, 399_999),
    "ACQUISITION": (400_000, 499_999),
    "PILOT": (500_000, 599_999),
    #: Control characterisation -- probing what an *arm* can read, not what the model can
    #: reason. Its own band so a diagnostic can never consume a gate or pilot seed, and so
    #: it is unmistakably not a fourth acquisition attempt.
    "DIAGNOSTIC": (600_000, 699_999),
    #: Endpoint A -- next-action selection. Its own band so it consumes nothing already
    #: burned by developmental selection, the acquisition gate, the binder diagnostic or
    #: the B1 pilot.
    "ENDPOINT_A": (700_000, 799_999),
    #: Causal diagnosis of the B1 loss -- five matched conditions, mechanism triage.
    "CAUSAL_DIAGNOSIS": (800_000, 899_999),
    #: Endpoint B2 -- quantifier scope with a fair compact structured control.
    "ENDPOINT_B2": (110_000, 119_999),
    "CALIBRATION_LEGACY": (900_000, 999_999),
}

#: Bands whose seeds have been shown to a model, or are reserved so they can be.
MODEL_FACING = ("DEV_SELECTION", "ACQUISITION", "PILOT", "CALIBRATION_LEGACY")


class BandError(RuntimeError):
    """A seed is outside its declared band, or two bands were allowed to touch."""


def band_range(name: str) -> range:
    lo, hi = BANDS[name]
    return range(lo, hi + 1)


def band_of(seed: int) -> str:
    for name, (lo, hi) in BANDS.items():
        if lo <= seed <= hi:
            return name
    raise BandError(f"seed {seed} belongs to no declared band")


def assert_band(seeds, expected: str) -> None:
    """Every seed must sit in the band the caller claims it does."""
    wrong = sorted({s for s in seeds if band_of(s) != expected})
    if wrong:
        raise BandError(
            f"{len(wrong)} seed(s) are not in band {expected}: {wrong[:8]} "
            f"(first belongs to {band_of(wrong[0])})"
        )


def assert_disjoint(seeds_a, label_a: str, seeds_b, label_b: str) -> None:
    """Two seed sets that must never intersect. Raises with the offending seeds named."""
    overlap = sorted(set(seeds_a) & set(seeds_b))
    if overlap:
        raise BandError(
            f"{len(overlap)} seed(s) appear in both {label_a} and {label_b}: {overlap[:8]}"
        )
