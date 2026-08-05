"""Lexicographic protocol selection. Never a weighted score, never parse rate alone.

Why lexicographic and not weighted
----------------------------------
A weighted score lets token efficiency compensate for semantic corruption. Under any
positive weight on cost, a protocol that produces cheaper, subtly wrong encodings can
outrank one that produces correct expensive ones, and the trade is invisible in the
headline number. Lexicographic ordering makes the trade impossible to express: a
difference on an earlier key decides, and no amount of advantage on a later key reaches
back past it.

This module therefore exposes no weighted combiner, and
:func:`assert_no_weighted_scorer` asserts that it never acquires one.

Why not parse rate
------------------
Parse rate is not in the key list at all as a primary criterion. Tam et al. observed a
0.148% parse-error rate alongside a >38-point reasoning gap: a protocol can produce text
that parses essentially always and means the wrong thing essentially always. Selecting on
parse rate would prefer exactly that protocol. Repaired parse rate appears third, after
semantic preservation, where it can break a tie but cannot create a winner.

The order, and what each key is for
-----------------------------------
1. ``constitutional_validity`` — a design violation disqualifies before any number is
   read. A protocol that leaked oracle information does not get to compete on quality.
2. ``semantic_preservation`` — exact recovery of the canonical object. The thing ACQ0
   exists to measure.
3. ``repaired_parse_rate`` — does a single repair recover the surface. Breaks ties.
4. ``domain_stability`` — worst per-domain preservation. A protocol that is excellent on
   three domains and broken on the fourth is not a protocol that works.
5. ``token_cost`` — including the draft. See :class:`~.core.TokenLedger`.
6. ``latency``.

Ties all the way down are **not** a selection. :func:`select_protocol` returns
``AMBIGUOUS`` and the escalation is to run ``PLAN_THEN_FORMAL``, not to pick the cheapest.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .metrics import ArmSummary

__all__ = [
    "LEXICOGRAPHIC_KEYS",
    "MATERIALITY",
    "SelectionStatus",
    "Selection",
    "select_protocol",
    "assert_no_weighted_scorer",
]

#: In order. Read by the selector and by the audit document; not duplicated in prose.
LEXICOGRAPHIC_KEYS: tuple[str, ...] = (
    "constitutional_validity",
    "semantic_preservation",
    "repaired_parse_rate",
    "domain_stability",
    "token_cost",
    "latency",
)

#: What counts as a real difference on each key. **Pre-registered**: fixed here before any
#: model call was made, which is what makes them thresholds rather than post-hoc choices.
#:
#: The calibration design runs 8 trials per arm (4 syntaxes x 2 tasks), so one trial is
#: 0.125. A 0.25 threshold is two trials' worth: coarse, and honestly so — 8 trials
#: cannot resolve less, and pretending otherwise would turn sampling noise into a
#: protocol decision.
MATERIALITY: dict[str, float] = {
    "semantic_preservation": 0.25,
    "repaired_parse_rate": 0.25,
    "domain_stability": 0.25,
    #: Relative, not absolute: token totals differ by orders of magnitude between
    #: curriculum sizes and an absolute threshold would mean different things at each.
    "token_cost": 0.20,
    "latency": 0.20,
}


class SelectionStatus(StrEnum):
    SELECTED = "SELECTED"
    #: Every key tied. Escalate to PLAN_THEN_FORMAL rather than break the tie on cost.
    AMBIGUOUS = "AMBIGUOUS"
    #: Nothing was measured, or a key needed for the comparison is absent.
    UNSTABLE = "UNSTABLE"


@dataclass(frozen=True)
class Selection:
    status: SelectionStatus
    protocol: str | None
    #: The key that decided it, or ``""`` when nothing decided it.
    decided_by: str = ""
    reasons: tuple[str, ...] = ()
    disqualified: tuple[str, ...] = ()
    #: The full comparison, key by key, for the record.
    trace: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": str(self.status),
            "protocol": self.protocol,
            "decided_by": self.decided_by,
            "reasons": list(self.reasons),
            "disqualified": list(self.disqualified),
            "trace": [dict(t) for t in self.trace],
            "keys_in_order": list(LEXICOGRAPHIC_KEYS),
            "note": (
                "lexicographic: a difference on an earlier key decides, so token "
                "efficiency can never compensate for semantic corruption"
            ),
        }


def _value_for(arm: ArmSummary, key: str) -> tuple[float | None, str]:
    """The arm's value on one key, plus why it is absent when it is.

    Sign convention: **higher is better** for every key. Cost keys are negated so the
    comparison is uniform and no call site has to remember which way round a key runs.
    """
    if key == "semantic_preservation":
        v = arm.rates.get("semantic_preservation_exact")
        return v, "" if v is not None else "no trial measured exact preservation"
    if key == "repaired_parse_rate":
        v = arm.rates.get("repair_success")
        if v is None:
            # No repair was attempted, which is not a failed repair. Fall back to the
            # first-attempt parse rate so the key is still comparable, and say so.
            v = arm.rates.get("parse_success")
            return v, (
                "no repair was attempted; first-attempt parse rate used and labelled"
                if v is not None
                else "neither repair nor parse was measured"
            )
        return v, ""
    if key == "domain_stability":
        vals = [v for v in arm.per_domain_preservation.values() if v is not None]
        if not vals:
            return None, "no per-domain preservation was recorded"
        return min(vals), ""
    if key == "token_cost":
        m = arm.total_completion_tokens
        if not m.is_measured or m.value is None:
            return None, m.reason
        return -float(m.value), ""
    if key == "latency":
        m = arm.total_latency_s
        if not m.is_measured or m.value is None:
            return None, m.reason
        return -float(m.value), ""
    raise ValueError(f"unknown key {key!r}")


def _material(key: str, best: float, other: float) -> bool:
    """Is ``best`` ahead of ``other`` by enough to call it a difference?"""
    threshold = MATERIALITY[key]
    if key in ("token_cost", "latency"):
        # Relative on a negated magnitude. Zero magnitudes cannot differ relatively.
        scale = max(abs(best), abs(other))
        if scale == 0:
            return False
        return (best - other) / scale >= threshold
    return (best - other) >= threshold


def select_protocol(arms: Sequence[ArmSummary]) -> Selection:
    """Choose one protocol, or refuse to.

    Refuses in three situations, and the refusals matter more than the selection:

    * nothing measured — an arm with zero trials has produced no evidence, and a
      selection made from it would be a preference presented as a result;
    * a key absent for one of the arms still in contention — the comparison is
      unavailable, not tied;
    * every key tied — escalate, do not fall through to cost.
    """
    if not arms:
        return Selection(
            SelectionStatus.UNSTABLE,
            None,
            reasons=("no arms were supplied; there is nothing to select from",),
        )

    measured = [a for a in arms if a.n_trials > 0]
    if not measured:
        return Selection(
            SelectionStatus.UNSTABLE,
            None,
            reasons=(
                "every arm has zero trials. No model call has been made, so no protocol "
                "can be selected; a choice made now would be a preference wearing the "
                "label of a result.",
            ),
        )

    disqualified = tuple(
        f"{a.protocol}: {'; '.join(a.constitutional_findings) or 'constitutionally invalid'}"
        for a in measured
        if not a.constitutionally_valid
    )
    live = [a for a in measured if a.constitutionally_valid]
    if not live:
        return Selection(
            SelectionStatus.UNSTABLE,
            None,
            decided_by="constitutional_validity",
            reasons=("every measured arm failed constitutional validity",),
            disqualified=disqualified,
        )
    if len(live) == 1:
        return Selection(
            SelectionStatus.SELECTED,
            live[0].protocol,
            decided_by="constitutional_validity",
            reasons=(
                f"{live[0].protocol} is the only constitutionally valid measured arm",
            ),
            disqualified=disqualified,
        )

    trace: list[dict[str, Any]] = []
    for key in LEXICOGRAPHIC_KEYS[1:]:
        values: dict[str, float | None] = {}
        absences: dict[str, str] = {}
        for arm in live:
            v, why = _value_for(arm, key)
            values[arm.protocol] = v
            if v is None:
                absences[arm.protocol] = why
        trace.append({"key": key, "values": dict(values), "absences": dict(absences)})
        if absences:
            return Selection(
                SelectionStatus.UNSTABLE,
                None,
                decided_by=key,
                reasons=(
                    f"{key} is absent for {sorted(absences)}: "
                    + "; ".join(f"{k}: {v}" for k, v in sorted(absences.items()))
                    + ". An absent key is unavailable, not tied, so the arms below it "
                    "were never compared.",
                ),
                disqualified=disqualified,
                trace=tuple(trace),
            )
        ranked = sorted(live, key=lambda a: values[a.protocol] or 0.0, reverse=True)
        best, runner_up = ranked[0], ranked[1]
        b, r = values[best.protocol] or 0.0, values[runner_up.protocol] or 0.0
        if _material(key, b, r):
            return Selection(
                SelectionStatus.SELECTED,
                best.protocol,
                decided_by=key,
                reasons=(
                    f"{best.protocol} leads {runner_up.protocol} on {key} "
                    f"({b:.4g} vs {r:.4g}), a difference of at least the pre-registered "
                    f"materiality threshold {MATERIALITY[key]}. Keys after {key} were "
                    "not consulted: that is what lexicographic means.",
                ),
                disqualified=disqualified,
                trace=tuple(trace),
            )
        # Not material. Drop arms that are materially *behind* the leader, then continue.
        live = [a for a in live if not _material(key, b, values[a.protocol] or 0.0)]
        if len(live) == 1:
            return Selection(
                SelectionStatus.SELECTED,
                live[0].protocol,
                decided_by=key,
                reasons=(
                    f"{live[0].protocol} is the only arm not materially behind on {key}",
                ),
                disqualified=disqualified,
                trace=tuple(trace),
            )

    return Selection(
        SelectionStatus.AMBIGUOUS,
        None,
        decided_by="",
        reasons=(
            "every key tied within its pre-registered materiality threshold. The "
            "escalation is to run PLAN_THEN_FORMAL, not to break the tie on cost: "
            "breaking a tie on cost is a weighted score with all the weight on one key.",
        ),
        disqualified=disqualified,
        trace=tuple(trace),
    )


def assert_no_weighted_scorer(module: Any = None) -> None:
    """Assert this module has acquired no weighted combiner.

    Cheap, and it protects the property the whole design rests on. A helper called
    ``overall_score`` would be added in good faith by someone who wanted a single number
    for a table, and it would silently reintroduce the compensation the lexicographic
    order exists to forbid.
    """
    import sys

    mod = module or sys.modules[__name__]
    banned = ("weighted", "overall_score", "composite", "combined_score", "total_score")
    found = [
        name
        for name in dir(mod)
        if any(b in name.lower() for b in banned) and not name.startswith("assert_")
    ]
    if found:
        raise AssertionError(
            f"{getattr(mod, '__name__', mod)} exposes {found}, which would let token "
            "efficiency compensate for semantic corruption. Selection is lexicographic."
        )
