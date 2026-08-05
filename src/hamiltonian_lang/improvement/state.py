"""Phase 5 — the versioned system state, and the hypothesis under test.

Why this module exists
----------------------
An improvement loop that changes two things at once cannot attribute its own result.
If the surface language and the model both move between two measurements, a difference
in the outcome is evidence about *the pair*, and no amount of later analysis recovers
which half carried it. The rule this module enforces mechanically is therefore:

    exactly one major component changes per transition — ``|ΔS|₀ = 1``

and, equally important, **every version that moved must have been declared**. A
component that changes without being named in the proposal is *hidden drift*: the
experiment still runs, the numbers still differ, and the write-up attributes the
difference to the wrong cause. Hidden drift is rejected here, not warned about.

Two fields are versioned but are not major components: ``memory_schema_version`` and
``compiler_commit``. They are not independently promotable, but they are recorded, and
they are covered by the drift check — a proposal that moves the compiler commit while
claiming to change only the diagnostic policy is rejected exactly like any other
undeclared change.

The hypothesis lives here too
-----------------------------
``Hypothesis`` is defined in this module rather than in the evidence module because it
is part of the *identity* of an experiment, alongside the versions. Three hypotheses
are under test and they can come apart:

* **H1** — the representation *as input* improves the answer.
* **H2** — the representation *as a reasoning workspace* improves the answer.
* **H3** — *verifier-guided repair* improves the verified answer.

A win on H3 alone is a win for verifier-guided reasoning. It is **not** a win for the
representation, and it must never be reported as one: the same repair loop over any
checkable notation would predict the same gain. The type is an enumeration and not a
string so that a year from now the record says which question was being asked, and so
that no aggregation can quietly average two of them together.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, fields, replace
from enum import StrEnum
from typing import Any

__all__ = [
    "Hypothesis",
    "REPAIR_MECHANISM",
    "HypothesisMixingError",
    "require_single_hypothesis",
    "Unavailable",
    "Measurement",
    "StateComponent",
    "SystemState",
    "COMPONENT_FIELD",
    "NON_COMPONENT_FIELDS",
    "StateDiff",
    "diff_states",
    "RollbackPlan",
    "ProposalRejection",
    "ProposalVerdict",
    "StateTransitionProposal",
]


# ---------------------------------------------------------------------------
# The hypothesis under test
# ---------------------------------------------------------------------------


class Hypothesis(StrEnum):
    """**The one hypothesis type.** Which separable claim a piece of evidence speaks to.

    Separability is the point. ``H1``, ``H2`` and ``H3`` are not three phrasings of one
    idea; they are three claims that can each be true or false independently, and the
    project's whole value in retrospect depends on never merging them.

    Two members are not ordinary scientific hypotheses and are named so that they cannot
    be mistaken for one:

    * ``ACQ0`` — the **syntax-acquisition prerequisite**. Can the model express a frozen
      canonical object in a candidate surface at all? Passing it says nothing about
      whether the representation *helps*. Compiler-assisted repair during ACQ0 is
      ``ACQ0_REPAIR`` and is **not H3**: fixing a malformed encoding and fixing a wrong
      argument are different acts with different success conditions, and conflating them
      would let "the model learned to write the syntax with compiler help" be read later
      as "verifier feedback improved mathematical reasoning".
      See ``docs/evaluation/HYPOTHESIS_REGISTER.md``.
    * ``EXCLUDED`` — engineering work: a smoke run, a fixture, a pipeline check. It is
      **never training-eligible** and is **never routed into a scientific aggregate**.
      It replaces the old ``episodes.HypothesisId.NONE``, whose spelling invited reading
      it as "no hypothesis recorded yet" — a default — rather than "deliberately outside
      the scientific record".

    ``scientific`` partitions the two groups, and :func:`require_single_hypothesis` uses
    it to keep ``EXCLUDED`` out of every statistic.

    The short spellings are canonical; the descriptive spellings
    (``H1_REPRESENTATION_AS_INPUT`` and friends) are enum **aliases** for the same
    members, kept because they read better at a call site that declares an experiment.
    ``Hypothesis.H1 is Hypothesis.H1_REPRESENTATION_AS_INPUT`` is true.
    """

    ACQ0 = "ACQ0"
    H1_REPRESENTATION_AS_INPUT = "H1"
    H2_REPRESENTATION_AS_WORKSPACE = "H2"
    H3_VERIFIER_GUIDED_REPAIR = "H3"
    EXCLUDED = "EXCLUDED"

    #: Short aliases. Same members, not new ones.
    H1 = "H1"
    H2 = "H2"
    H3 = "H3"

    @property
    def claim(self) -> str:
        """The exact claim that a win on this hypothesis supports."""
        return _HYPOTHESIS_CLAIM[self]

    @property
    def excluded_claim(self) -> str:
        """The claim a win on this hypothesis does **not** support.

        Printed verbatim in every report so that a reader a year later cannot take a
        repair-loop result for a representation result.
        """
        return _HYPOTHESIS_EXCLUSION[self]

    @property
    def scientific(self) -> bool:
        """Whether this identifier may appear in a scientific aggregate.

        ``EXCLUDED`` is the only member for which this is false. ``ACQ0`` **is**
        scientific — it is a real prerequisite experiment with its own preregistered
        thresholds — it is simply not evidence for or against H1, H2 or H3, which
        :func:`require_single_hypothesis` already enforces by refusing to mix.
        """
        return self is not Hypothesis.EXCLUDED


#: The name under which repair is recorded, per hypothesis. The distinction ``ACQ0``
#: draws here is the whole reason ``ACQ0`` exists as its own identifier.
REPAIR_MECHANISM: dict[Hypothesis, str] = {
    Hypothesis.ACQ0: "ACQ0_REPAIR",
    Hypothesis.H3_VERIFIER_GUIDED_REPAIR: "H3_VERIFIER_GUIDED_REPAIR",
}


_HYPOTHESIS_CLAIM: dict[Hypothesis, str] = {
    Hypothesis.ACQ0: (
        "ACQ0: the model can express a frozen canonical semantic object in a candidate "
        "surface such that it parses and recovers the same object. This is a "
        "PREREQUISITE, not a result: passing it means the language is writable, not "
        "that it helps."
    ),
    Hypothesis.EXCLUDED: (
        "EXCLUDED: an engineering episode — a smoke run, a fixture, a pipeline check. "
        "It asserts nothing and is excluded from every hypothesis-level aggregate."
    ),
    Hypothesis.H1_REPRESENTATION_AS_INPUT: (
        "Supplying the problem in the representation, as input, improves the answer "
        "relative to the same problem in prose."
    ),
    Hypothesis.H2_REPRESENTATION_AS_WORKSPACE: (
        "Reasoning *in* the representation, as an intermediate workspace, improves the "
        "answer relative to reasoning in prose and answering in either notation."
    ),
    Hypothesis.H3_VERIFIER_GUIDED_REPAIR: (
        "A structured diagnostic plus one repair attempt improves the verified answer "
        "relative to a single unassisted attempt."
    ),
}

_HYPOTHESIS_EXCLUSION: dict[Hypothesis, str] = {
    Hypothesis.ACQ0: (
        "It does NOT support any claim about H1, H2 or H3. A candidate syntax that "
        "passes ACQ0 has been shown writable and nothing more. In particular, a gain "
        "from compiler-assisted repair during ACQ0 is ACQ0_REPAIR — repairing a "
        "malformed encoding — and is not evidence that verifier feedback improved "
        "mathematical reasoning (H3)."
    ),
    Hypothesis.EXCLUDED: (
        "It supports NOTHING. An EXCLUDED episode is not evidence, is never "
        "training-eligible, and never enters an aggregate."
    ),
    Hypothesis.H1_REPRESENTATION_AS_INPUT: (
        "It does not support the claim that reasoning in the representation helps (H2), "
        "nor that the repair loop helps (H3)."
    ),
    Hypothesis.H2_REPRESENTATION_AS_WORKSPACE: (
        "It does not support the claim that the representation helps as input (H1), nor "
        "that the repair loop helps (H3)."
    ),
    Hypothesis.H3_VERIFIER_GUIDED_REPAIR: (
        # NOTE: deliberately phrased WITHOUT the substring "win for the representation".
        # tests/improvement/test_hypothesis_separation.py bans that phrase from every
        # rendered H3 report, and a negated occurrence here would still trip a reader
        # skimming for it. The prohibition is stated, not quoted.
        "It does NOT support any claim about the representation. A win here is a win for "
        "verifier-guided reasoning; any checkable notation with a comparable checker "
        "would predict the same gain. Reporting it as a representation result (H1 or H2) "
        "misattributes the cause."
    ),
}


class HypothesisMixingError(ValueError):
    """Raised when evidence from two hypotheses would enter one statistic.

    This is an error and not a warning because the failure it prevents is silent: a
    mixed mean is a number, it looks like every other number, and nothing downstream can
    tell it apart from a clean one.
    """


def require_single_hypothesis(
    items: Iterable[Any], *, context: str, allow_excluded: bool = False
) -> Hypothesis:
    """Return the one hypothesis carried by ``items``, or raise.

    ``items`` may be ``Hypothesis`` values or any object exposing ``.hypothesis``. An
    empty input raises: "no hypothesis" is not a hypothesis, and defaulting one would be
    the exact fabrication this function exists to stop.

    A free-text or absent hypothesis raises. So does a bare string that happens to spell
    a member: ``"H1"`` is not ``Hypothesis.H1``, and accepting it would let an arbitrary
    string — including a misspelling — reach an aggregate untyped.

    ``EXCLUDED`` raises unless ``allow_excluded`` is set. Engineering episodes are not
    evidence, so a statistic computed over them is not a result; the only legitimate
    callers are tallies that deliberately count non-evidence.
    """
    seen: set[Hypothesis] = set()
    for item in items:
        h = item if isinstance(item, Hypothesis) else getattr(item, "hypothesis", None)
        if not isinstance(h, Hypothesis):
            raise HypothesisMixingError(
                f"{context}: item {item!r} carries no typed Hypothesis; "
                "a free-text or absent hypothesis cannot be aggregated"
            )
        seen.add(h)
    if not seen:
        raise HypothesisMixingError(f"{context}: no observations, so no hypothesis to report")
    if len(seen) > 1:
        names = ", ".join(sorted(h.name for h in seen))
        raise HypothesisMixingError(
            f"{context}: observations span {len(seen)} hypotheses ({names}). "
            "ACQ0, H1, H2 and H3 are separable claims and are never combined into one "
            "statistic."
        )
    only = seen.pop()
    if only is Hypothesis.EXCLUDED and not allow_excluded:
        raise HypothesisMixingError(
            f"{context}: every observation is EXCLUDED. An EXCLUDED episode is "
            "engineering work, not evidence; a statistic over it is not a result. Pass "
            "allow_excluded=True only to count non-evidence deliberately."
        )
    return only


# ---------------------------------------------------------------------------
# Quantities that do not exist yet
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Unavailable:
    """A quantity that has no value, with the reason and what would produce one.

    Mirrors ``evaluation.v1.score_v1.NotMeasured`` deliberately: same discipline, same
    JSON shape, applied to the improvement subsystem. Serialises with ``UNAVAILABLE`` as
    the first key, and raises on ``float()`` so a consumer that expects a number fails
    loudly instead of averaging in a zero.
    """

    reason: str
    requires: str = ""

    def __float__(self) -> float:
        raise TypeError(
            f"value is unavailable ({self.reason}); it has no numeric value. "
            f"Requires: {self.requires or 'unstated'}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {"UNAVAILABLE": True, "reason": self.reason, "requires": self.requires}


#: A number, or an explicit statement that there is no number.
Measurement = float | Unavailable


# ---------------------------------------------------------------------------
# The state
# ---------------------------------------------------------------------------


class StateComponent(StrEnum):
    """The six independently promotable components of the system."""

    SEMANTIC_KERNEL = "semantic_kernel"
    SURFACE_LANGUAGE = "surface_language"
    DIAGNOSTIC_POLICY = "diagnostic_policy"
    MODEL = "model"
    CURRICULUM = "curriculum"
    VERIFIER = "verifier"


#: Component to the state field that carries its version. Total over ``StateComponent``.
COMPONENT_FIELD: Mapping[StateComponent, str] = {
    StateComponent.SEMANTIC_KERNEL: "semantic_kernel_version",
    StateComponent.SURFACE_LANGUAGE: "surface_language_version",
    StateComponent.DIAGNOSTIC_POLICY: "diagnostic_policy_version",
    StateComponent.MODEL: "model_version",
    StateComponent.CURRICULUM: "curriculum_policy_version",
    StateComponent.VERIFIER: "verifier_configuration_version",
}

#: Versioned, recorded, drift-checked — but not independently promotable.
NON_COMPONENT_FIELDS: tuple[str, ...] = ("memory_schema_version", "compiler_commit")


@dataclass(frozen=True)
class SystemState:
    """An immutable, fully versioned description of the system at one moment.

    Every field is required. There is no default anywhere in this class: a default
    version is an undeclared version, and the whole module exists to stop those.
    """

    semantic_kernel_version: str
    surface_language_version: str
    diagnostic_policy_version: str
    model_version: str
    curriculum_policy_version: str
    memory_schema_version: str
    verifier_configuration_version: str
    compiler_commit: str

    def __post_init__(self) -> None:
        for f in fields(self):
            value = getattr(self, f.name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"SystemState.{f.name} must be a non-empty version string; got {value!r}"
                )

    def to_dict(self) -> dict[str, str]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def fingerprint(self) -> str:
        """SHA-256 over the whole state. Two states are the same run condition iff equal."""
        blob = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def version_of(self, component: StateComponent) -> str:
        return str(getattr(self, COMPONENT_FIELD[component]))

    def evolve(self, **changes: str) -> SystemState:
        """Return a new state with the named fields replaced. Never mutates."""
        unknown = set(changes) - {f.name for f in fields(self)}
        if unknown:
            raise ValueError(f"unknown state fields: {sorted(unknown)}")
        return replace(self, **changes)


@dataclass(frozen=True)
class StateDiff:
    """What actually moved between two states, independent of what was claimed."""

    changed_fields: tuple[str, ...]
    changed_components: frozenset[StateComponent]
    changed_non_component_fields: tuple[str, ...]

    def is_empty(self) -> bool:
        return not self.changed_fields

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed_fields": list(self.changed_fields),
            "changed_components": sorted(c.value for c in self.changed_components),
            "changed_non_component_fields": list(self.changed_non_component_fields),
        }


def diff_states(incumbent: SystemState, candidate: SystemState) -> StateDiff:
    """Compare two states field by field. This is the ground truth about a transition."""
    changed = tuple(
        f.name
        for f in fields(SystemState)
        if getattr(incumbent, f.name) != getattr(candidate, f.name)
    )
    field_to_component = {v: k for k, v in COMPONENT_FIELD.items()}
    components = frozenset(
        field_to_component[name] for name in changed if name in field_to_component
    )
    non_component = tuple(name for name in changed if name in NON_COMPONENT_FIELDS)
    return StateDiff(changed, components, non_component)


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RollbackPlan:
    """How to get back. Recorded before the change, not after it fails."""

    target_state: SystemState
    procedure: str
    verified_reversible: bool = False

    def __post_init__(self) -> None:
        if not self.procedure.strip():
            raise ValueError("RollbackPlan.procedure must state how the change is undone")

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_state": self.target_state.to_dict(),
            "target_state_fingerprint": self.target_state.fingerprint(),
            "procedure": self.procedure,
            "verified_reversible": self.verified_reversible,
        }


class ProposalRejection(StrEnum):
    """Every way a transition proposal can fail. Codes are stable; messages are not."""

    NO_COMPONENT_CHANGED = "no_component_changed"
    MULTIPLE_COMPONENTS_CHANGED = "multiple_components_changed"
    DECLARED_COMPONENT_UNCHANGED = "declared_component_unchanged"
    UNDECLARED_VERSION_DRIFT = "undeclared_version_drift"
    MISSING_TRIGGER_EPISODE = "missing_trigger_episode"
    MISSING_HYPOTHESIS_RATIONALE = "missing_hypothesis_rationale"
    ROLLBACK_TARGET_NOT_INCUMBENT = "rollback_target_not_incumbent"


@dataclass(frozen=True)
class ProposalVerdict:
    """The result of validating a proposal, with every reason it failed — not the first."""

    ok: bool
    rejections: tuple[tuple[ProposalRejection, str], ...]
    diff: StateDiff

    def codes(self) -> tuple[ProposalRejection, ...]:
        return tuple(code for code, _ in self.rejections)

    def render(self) -> str:
        if self.ok:
            comp = sorted(c.value for c in self.diff.changed_components)
            return f"accepted: exactly one component changed ({comp[0]})"
        lines = ["rejected:"]
        lines.extend(f"  {code.value}: {detail}" for code, detail in self.rejections)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "rejections": [{"code": c.value, "detail": d} for c, d in self.rejections],
            "diff": self.diff.to_dict(),
        }


@dataclass(frozen=True)
class StateTransitionProposal:
    """One proposed change of exactly one component, with its reason and its way back.

    ``declared_component`` is what the proposer says changed. ``validate`` compares that
    claim against the actual field-by-field difference, and disagreement in either
    direction is a rejection.
    """

    proposal_id: str
    incumbent: SystemState
    candidate: SystemState
    declared_component: StateComponent
    hypothesis: Hypothesis
    hypothesis_rationale: str
    trigger_episode_id: str
    rollback: RollbackPlan
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, Hypothesis):
            raise TypeError(
                "StateTransitionProposal.hypothesis must be a Hypothesis member, not "
                f"{type(self.hypothesis).__name__}. Free text cannot be separated later."
            )
        if not isinstance(self.declared_component, StateComponent):
            raise TypeError(
                "StateTransitionProposal.declared_component must be a StateComponent member"
            )

    def diff(self) -> StateDiff:
        return diff_states(self.incumbent, self.candidate)

    def validate(self) -> ProposalVerdict:
        d = self.diff()
        rejections: list[tuple[ProposalRejection, str]] = []

        if d.is_empty():
            rejections.append(
                (
                    ProposalRejection.NO_COMPONENT_CHANGED,
                    "incumbent and candidate are identical; there is nothing to attribute",
                )
            )
        if len(d.changed_components) > 1:
            names = ", ".join(sorted(c.value for c in d.changed_components))
            rejections.append(
                (
                    ProposalRejection.MULTIPLE_COMPONENTS_CHANGED,
                    f"{len(d.changed_components)} components changed ({names}); "
                    "|dS|_0 = 1 is required so the result is attributable",
                )
            )
        if d.changed_components and self.declared_component not in d.changed_components:
            rejections.append(
                (
                    ProposalRejection.DECLARED_COMPONENT_UNCHANGED,
                    f"declared component {self.declared_component.value} has the same "
                    f"version in both states "
                    f"({self.incumbent.version_of(self.declared_component)!r})",
                )
            )
        if not d.changed_components and not d.is_empty():
            rejections.append(
                (
                    ProposalRejection.DECLARED_COMPONENT_UNCHANGED,
                    f"declared component {self.declared_component.value} did not change; "
                    f"only {', '.join(d.changed_non_component_fields)} moved",
                )
            )

        undeclared = [
            name
            for name in d.changed_fields
            if name != COMPONENT_FIELD[self.declared_component]
        ]
        if undeclared:
            rejections.append(
                (
                    ProposalRejection.UNDECLARED_VERSION_DRIFT,
                    "these versions changed without being declared: "
                    f"{', '.join(undeclared)}. A result measured across an undeclared "
                    "change is attributed to the wrong cause.",
                )
            )

        if not self.trigger_episode_id.strip():
            rejections.append(
                (
                    ProposalRejection.MISSING_TRIGGER_EPISODE,
                    "no trigger episode; a change with no observed failure behind it has "
                    "nothing to reproduce and nothing to falsify",
                )
            )
        if not self.hypothesis_rationale.strip():
            rejections.append(
                (
                    ProposalRejection.MISSING_HYPOTHESIS_RATIONALE,
                    f"hypothesis {self.hypothesis.name} is declared but unexplained; "
                    "state why this change bears on that hypothesis and not another",
                )
            )
        if self.rollback.target_state != self.incumbent:
            rejections.append(
                (
                    ProposalRejection.ROLLBACK_TARGET_NOT_INCUMBENT,
                    "rollback target is not the incumbent state; a rollback that lands "
                    "somewhere else is a third condition, not a revert",
                )
            )

        return ProposalVerdict(not rejections, tuple(rejections), d)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "incumbent": self.incumbent.to_dict(),
            "incumbent_fingerprint": self.incumbent.fingerprint(),
            "candidate": self.candidate.to_dict(),
            "candidate_fingerprint": self.candidate.fingerprint(),
            "declared_component": self.declared_component.value,
            "hypothesis": self.hypothesis.value,
            "hypothesis_name": self.hypothesis.name,
            "hypothesis_claim": self.hypothesis.claim,
            "hypothesis_excluded_claim": self.hypothesis.excluded_claim,
            "hypothesis_rationale": self.hypothesis_rationale,
            "trigger_episode_id": self.trigger_episode_id,
            "rollback": self.rollback.to_dict(),
            "notes": list(self.notes),
            "verdict": self.validate().to_dict(),
        }
