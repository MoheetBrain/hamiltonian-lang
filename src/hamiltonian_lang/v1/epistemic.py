"""V1 epistemic status types — the semantic contract.

HML-V1-CONCEPT-001 Phase 6. **This module is the contract.** Agents build against it and
must not change it; a change here is a semantic-contract change requiring a `DECISIONS.md`
record.

The layer exists to make one class of error unrepresentable rather than discouraged:

    result r1 := fail_to_reject(test := t1, p_value := 0.18)
    prove r1                      # TYPE ERROR

`fail_to_reject` yields ``Evidence``. ``prove`` demands ``Proof``. There is **no coercion
between them**, exactly as V0 keeps ``Distribution[T]``, ``RandomVariable[T]`` and ``T``
apart. "Failed to reject" therefore cannot become "proved", "there is no effect", or
"H0 is true" by any route the type system admits.

Nothing here imports the V0 kernel's mutable state; V0 is frozen at ``hml-v0-baseline``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "PValue",
    "PosteriorProbability",
    "ProbabilityKind",
    "probability_coercion_allowed",
    "Justification",
    "EpistemicStatus",
    "STATUS_JUSTIFICATION",
    "REQUIRED_CONTEXT",
    "DISCHARGES_GOALS",
    "EpistemicClaim",
    "ContextError",
    "coercion_allowed",
    "PROHIBITED_COERCIONS",
]


class Justification(StrEnum):
    """The grounds on which a claim is held. Deliberately **not** an ordered chain."""

    PROOF = "Proof"
    ASSUMPTION = "Assumption"
    EVIDENCE = "Evidence"
    CREDENCE = "Credence"
    REFUTATION = "Refutation"
    NONE = "None"


class EpistemicStatus(StrEnum):
    """Every status a claim may carry. The set is closed."""

    DEFINITIONALLY_TRUE = "definitionally_true"
    PROVED = "proved"
    DISPROVED = "disproved"
    CONJECTURED = "conjectured"
    POSSIBLE = "possible"
    CONSISTENT_WITH = "consistent_with"
    MODEL_CONDITIONAL = "model_conditional"
    ESTIMATED = "estimated"
    APPROXIMATELY_EQUAL = "approximately_equal"
    ASYMPTOTICALLY_EQUIVALENT = "asymptotically_equivalent"
    ALMOST_SURE = "almost_sure"
    CONVERGES_IN_PROBABILITY = "converges_in_probability"
    WITH_HIGH_PROBABILITY = "with_high_probability"
    FAIL_TO_REJECT = "fail_to_reject"
    REJECT = "reject"
    UNSUPPORTED = "unsupported"


#: What kind of justification each status rests on.
STATUS_JUSTIFICATION: dict[EpistemicStatus, Justification] = {
    EpistemicStatus.DEFINITIONALLY_TRUE: Justification.PROOF,
    EpistemicStatus.PROVED: Justification.PROOF,
    EpistemicStatus.DISPROVED: Justification.REFUTATION,
    EpistemicStatus.CONJECTURED: Justification.NONE,
    EpistemicStatus.POSSIBLE: Justification.CREDENCE,
    EpistemicStatus.CONSISTENT_WITH: Justification.EVIDENCE,
    EpistemicStatus.MODEL_CONDITIONAL: Justification.ASSUMPTION,
    EpistemicStatus.ESTIMATED: Justification.EVIDENCE,
    EpistemicStatus.APPROXIMATELY_EQUAL: Justification.EVIDENCE,
    EpistemicStatus.ASYMPTOTICALLY_EQUIVALENT: Justification.PROOF,
    EpistemicStatus.ALMOST_SURE: Justification.PROOF,
    EpistemicStatus.CONVERGES_IN_PROBABILITY: Justification.PROOF,
    EpistemicStatus.WITH_HIGH_PROBABILITY: Justification.PROOF,
    EpistemicStatus.FAIL_TO_REJECT: Justification.EVIDENCE,
    EpistemicStatus.REJECT: Justification.EVIDENCE,
    EpistemicStatus.UNSUPPORTED: Justification.NONE,
}

#: Only a Proof discharges a goal. This single table is what stops "we failed to reject
#: it, so we're done" from closing an obligation.
DISCHARGES_GOALS: dict[Justification, bool] = {
    Justification.PROOF: True,
    Justification.REFUTATION: True,       # discharges by refuting
    Justification.ASSUMPTION: False,
    Justification.EVIDENCE: False,
    Justification.CREDENCE: False,
    Justification.NONE: False,
}

#: Context a status is meaningless without. A probabilistic qualifier with no regime, or a
#: test result with no alpha, is not a mathematical statement and is rejected as ill-formed
#: rather than accepted and quietly ignored.
REQUIRED_CONTEXT: dict[EpistemicStatus, tuple[str, ...]] = {
    EpistemicStatus.MODEL_CONDITIONAL: ("model",),
    EpistemicStatus.FAIL_TO_REJECT: ("null", "alpha", "p_value"),
    EpistemicStatus.REJECT: ("null", "alpha", "p_value"),
    EpistemicStatus.WITH_HIGH_PROBABILITY: ("bound_or_regime",),
    EpistemicStatus.CONVERGES_IN_PROBABILITY: ("sequence", "limit"),
    EpistemicStatus.ASYMPTOTICALLY_EQUIVALENT: ("regime",),
    EpistemicStatus.APPROXIMATELY_EQUAL: ("tolerance",),
    EpistemicStatus.ESTIMATED: ("estimator", "sample"),
    EpistemicStatus.CONSISTENT_WITH: ("data",),
    EpistemicStatus.ALMOST_SURE: ("measure",),
}

#: Pairs that may never be coerced, with the reason. Enforced by ``coercion_allowed``.
PROHIBITED_COERCIONS: dict[tuple[Justification, Justification], str] = {
    (Justification.EVIDENCE, Justification.PROOF): (
        "absence of evidence against a hypothesis is not evidence for it; "
        "failing to reject H0 does not prove H0"
    ),
    (Justification.CREDENCE, Justification.PROOF): (
        "a degree of belief about a model is not a proof within it"
    ),
    (Justification.ASSUMPTION, Justification.PROOF): (
        "an assumption is granted, not established; it carries forward as a dependency"
    ),
    (Justification.NONE, Justification.PROOF): (
        "a conjecture is not a theorem"
    ),
    (Justification.EVIDENCE, Justification.REFUTATION): (
        "rejecting at a significance level is not a disproof"
    ),
}


class ContextError(ValueError):
    """A status was used without the context that gives it meaning."""


class ProbabilityKind(StrEnum):
    """What a number in [0, 1] actually *is*.

    All three are reals in the unit interval, which is exactly why they get confused. The
    distinction is epistemic, not numeric, so the type system has to carry it — the value
    alone never can.
    """

    P_VALUE = "PValue"
    POSTERIOR = "PosteriorProbability"
    MODEL_PROBABILITY = "Probability"


#: Pairs that may never be coerced, with the reason. A p-value is P(data at least this
#: extreme | H0); a posterior is P(H0 | data). Reading one as the other is the
#: prosecutor's fallacy, and it is the single most common misreading in applied
#: statistics -- so it is prevented by typing rather than by a comment.
PROHIBITED_PROBABILITY_COERCIONS: dict[tuple[ProbabilityKind, ProbabilityKind], str] = {
    (ProbabilityKind.P_VALUE, ProbabilityKind.POSTERIOR): (
        "a p-value is P(data at least this extreme | H0); a posterior is P(H0 | data). "
        "Reading a p-value as a posterior is the prosecutor's fallacy"
    ),
    (ProbabilityKind.POSTERIOR, ProbabilityKind.P_VALUE): (
        "a posterior is not a tail probability under the null and cannot be compared "
        "to a significance level"
    ),
    (ProbabilityKind.P_VALUE, ProbabilityKind.MODEL_PROBABILITY): (
        "a p-value is a property of a test procedure, not a probability within the model"
    ),
    (ProbabilityKind.MODEL_PROBABILITY, ProbabilityKind.P_VALUE): (
        "a model probability is not the output of a hypothesis test"
    ),
}


def probability_coercion_allowed(
    source: ProbabilityKind, target: ProbabilityKind
) -> tuple[bool, str]:
    """Identity only. Everything else is refused by default, as elsewhere in the kernel."""
    if source == target:
        return True, ""
    reason = PROHIBITED_PROBABILITY_COERCIONS.get((source, target))
    if reason:
        return False, reason
    return False, f"no coercion from {source} to {target} is defined"


@dataclass(frozen=True)
class PValue:
    """The tail probability from a test. Numerically in [0, 1]; epistemically not a belief.

    Deliberately NOT a subclass of any probability type: subclassing would create exactly
    the coercion path this exists to forbid.
    """

    value: float
    kind: ProbabilityKind = ProbabilityKind.P_VALUE

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"a p-value must lie in [0, 1]; got {self.value}")

    def may_be_used_as(self, target: ProbabilityKind) -> tuple[bool, str]:
        return probability_coercion_allowed(self.kind, target)

    def as_posterior(self) -> float:
        raise TypeError(
            PROHIBITED_PROBABILITY_COERCIONS[
                (ProbabilityKind.P_VALUE, ProbabilityKind.POSTERIOR)
            ]
        )


@dataclass(frozen=True)
class PosteriorProbability:
    """P(hypothesis | data). Requires the prior it was computed against."""

    value: float
    prior: str
    kind: ProbabilityKind = ProbabilityKind.POSTERIOR

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"a probability must lie in [0, 1]; got {self.value}")
        if not self.prior:
            raise ContextError(
                "a posterior probability requires the prior it was computed against; "
                "without one it is not a posterior"
            )

    def may_be_used_as(self, target: ProbabilityKind) -> tuple[bool, str]:
        return probability_coercion_allowed(self.kind, target)



def coercion_allowed(source: Justification, target: Justification) -> tuple[bool, str]:
    """Whether ``source`` may stand where ``target`` is required.

    Identity only, plus the explicit prohibitions above. Everything else is refused by
    default: a permissive default is how a conflation gets in.
    """
    if source == target:
        return True, ""
    reason = PROHIBITED_COERCIONS.get((source, target))
    if reason:
        return False, reason
    return False, f"no coercion from {source} to {target} is defined"


@dataclass(frozen=True)
class EpistemicClaim:
    """A proposition together with how strongly, and on what grounds, it is held."""

    status: EpistemicStatus
    body: str
    context: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        missing = [k for k in REQUIRED_CONTEXT.get(self.status, ()) if k not in self.context]
        if missing:
            raise ContextError(
                f"{self.status} requires {', '.join(missing)}; "
                f"without it the claim is not a mathematical statement"
            )

    @property
    def justification(self) -> Justification:
        return STATUS_JUSTIFICATION[self.status]

    def discharges_goals(self) -> bool:
        return DISCHARGES_GOALS[self.justification]

    def may_be_used_as(self, target: Justification) -> tuple[bool, str]:
        return coercion_allowed(self.justification, target)

    def render_english(self) -> str:
        """Controlled English. The caveat is carried by the *type*, not by good manners."""
        c = self.context
        if self.status is EpistemicStatus.FAIL_TO_REJECT:
            return (
                f"The test did not reject {c['null']} at the "
                f"{c['alpha']} level (p = {c['p_value']}). "
                f"This is not evidence that {c['null']} is true."
            )
        if self.status is EpistemicStatus.REJECT:
            return (
                f"The test rejected {c['null']} at the {c['alpha']} level "
                f"(p = {c['p_value']}). This does not establish the alternative."
            )
        if self.status is EpistemicStatus.MODEL_CONDITIONAL:
            return f"Under model {c['model']}, {self.body}."
        if self.status is EpistemicStatus.WITH_HIGH_PROBABILITY:
            return f"With high probability ({c['bound_or_regime']}), {self.body}."
        if self.status is EpistemicStatus.ALMOST_SURE:
            return f"Almost surely with respect to {c['measure']}, {self.body}."
        if self.status is EpistemicStatus.CONJECTURED:
            return f"It is conjectured, and not established, that {self.body}."
        if self.status is EpistemicStatus.PROVED:
            return f"It is proved that {self.body}."
        if self.status is EpistemicStatus.DEFINITIONALLY_TRUE:
            return f"By definition, {self.body}."
        if self.status is EpistemicStatus.CONSISTENT_WITH:
            return (
                f"The data {c['data']} are consistent with {self.body}. "
                f"Compatibility is not support."
            )
        return f"[{self.status}] {self.body}"
