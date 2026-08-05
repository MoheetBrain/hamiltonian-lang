"""V1 layer 4 — the epistemic checker.

HML-V1-CONCEPT-001 Phase 6 (extension). :mod:`hamiltonian_lang.v1.epistemic` is the
contract — the statuses, the justification table, the prohibition table. It is imported
here and never modified.

This module is what *uses* that contract: a checker that takes named
:class:`~hamiltonian_lang.v1.epistemic.EpistemicClaim` s together with the sites where
they are used, and rejects any use that demands a stronger justification than the claim
carries. The canonical rejection::

    result r1 := fail_to_reject(test := t1, p_value := 0.18)   # Evidence
    prove r1                                                   # HML-E702

Three further things live here because they are checks rather than types:

* **statistical coherence** — ``fail_to_reject`` with ``p_value <= alpha`` contradicts its
  own test, and ``reject`` with ``p_value > alpha`` likewise. The contract requires the
  context to be *present*; this checks that it is *consistent*.
* **assumptions become dependencies** — an ``Assumption``-justified or
  ``model_conditional`` claim used anywhere is recorded, so the discourse layer can say
  what a result still rests on.
* **``likely`` is presentation-level only.** :class:`Likely` is deliberately **not** an
  ``EpistemicStatus``. An uncalibrated ``likely`` has no formal status at all and cannot
  be turned into one; a calibrated one becomes at most ``Credence``, which by
  :data:`~hamiltonian_lang.v1.epistemic.DISCHARGES_GOALS` discharges nothing and by
  :data:`~hamiltonian_lang.v1.epistemic.PROHIBITED_COERCIONS` never reaches ``Proof``.
  The gate decision licenses V1 to make errors catchable, not to launder a hedge into a
  trusted status.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from .epistemic import (
    DISCHARGES_GOALS,
    REQUIRED_CONTEXT,
    ContextError,
    EpistemicClaim,
    EpistemicStatus,
    Justification,
    coercion_allowed,
)

__all__ = [
    "Site",
    "REQUIRED_JUSTIFICATION_BY_SITE",
    "EpistemicViolation",
    "Dependency",
    "EpistemicReport",
    "EpistemicChecker",
    "Calibration",
    "Likely",
    "UncalibratedLikelyError",
    "check_test_coherence",
    "check_context",
]


# ---------------------------------------------------------------------------
# Use sites
# ---------------------------------------------------------------------------


class Site(StrEnum):
    """A place a claim can be used, each with its own justification demand."""

    PROVE = "prove"
    DISCHARGE = "discharge"
    ASSERT = "assert"
    REFUTE = "refute"
    ASSUME = "assume"
    CITE_AS_EVIDENCE = "cite_as_evidence"
    REPORT = "report"


#: What each site demands. ``REPORT`` is absent deliberately: reporting a claim imposes no
#: requirement, because the claim carries its own caveat in its type.
#: ``DISCHARGE`` is handled separately, through
#: :data:`~hamiltonian_lang.v1.epistemic.DISCHARGES_GOALS`, which admits a ``Refutation``
#: as well as a ``Proof``.
REQUIRED_JUSTIFICATION_BY_SITE: dict[Site, Justification] = {
    Site.PROVE: Justification.PROOF,
    Site.DISCHARGE: Justification.PROOF,
    Site.ASSERT: Justification.PROOF,
    Site.REFUTE: Justification.REFUTATION,
    Site.ASSUME: Justification.ASSUMPTION,
    Site.CITE_AS_EVIDENCE: Justification.EVIDENCE,
}


@dataclass(frozen=True)
class EpistemicViolation:
    code: str
    claim: str
    message: str
    site: Site | None = None
    required: Justification | None = None
    actual: Justification | None = None
    status: EpistemicStatus | None = None

    def render(self) -> str:
        where = f" at {self.site}" if self.site else ""
        return f"{self.code} [{self.claim}{where}] {self.message}"

    def __str__(self) -> str:
        return self.render()


@dataclass(frozen=True)
class Dependency:
    """Something a downstream result still rests on."""

    claim: str
    on: str
    reason: str

    def render(self) -> str:
        return f"{self.claim} depends on {self.on}: {self.reason}"

    def __str__(self) -> str:
        return self.render()


@dataclass(frozen=True)
class EpistemicReport:
    violations: tuple[EpistemicViolation, ...] = ()
    dependencies: tuple[Dependency, ...] = ()

    @property
    def clean(self) -> bool:
        return not self.violations

    def render(self) -> str:
        lines: list[str] = []
        if self.violations:
            lines.append(f"{len(self.violations)} epistemic violation(s):")
            lines.extend("  " + v.render() for v in self.violations)
        else:
            lines.append("no epistemic violations")
        if self.dependencies:
            lines.append(f"{len(self.dependencies)} dependency(ies):")
            lines.extend("  " + d.render() for d in self.dependencies)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Standalone checks
# ---------------------------------------------------------------------------


def check_context(status: EpistemicStatus, context: Mapping[str, str]) -> str | None:
    """The context keys ``status`` requires and does not have, or ``None``.

    :class:`~hamiltonian_lang.v1.epistemic.EpistemicClaim` already raises
    :class:`~hamiltonian_lang.v1.epistemic.ContextError` on construction; this is the
    non-raising form, for a checker that wants a diagnostic rather than an exception.
    """
    missing = [k for k in REQUIRED_CONTEXT.get(status, ()) if k not in context]
    if not missing:
        return None
    return (
        f"{status} requires {', '.join(missing)}; without it the claim is not a "
        f"mathematical statement"
    )


def _as_float(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def check_test_coherence(name: str, claim: EpistemicClaim) -> EpistemicViolation | None:
    """Whether a test outcome agrees with its own significance level.

    ``fail_to_reject`` requires ``p_value > alpha`` and ``reject`` requires
    ``p_value <= alpha``. When either number does not parse the check is **not decided**
    and returns ``None`` rather than guessing.
    """
    if claim.status not in (EpistemicStatus.FAIL_TO_REJECT, EpistemicStatus.REJECT):
        return None
    p = _as_float(claim.context.get("p_value", ""))
    alpha = _as_float(claim.context.get("alpha", ""))
    if p is None or alpha is None:
        return None
    if claim.status is EpistemicStatus.FAIL_TO_REJECT and p <= alpha:
        message = (
            f"fail_to_reject requires p_value > alpha, but p = {p} <= alpha = {alpha}; "
            f"the outcome contradicts the test it names"
        )
    elif claim.status is EpistemicStatus.REJECT and p > alpha:
        message = (
            f"reject requires p_value <= alpha, but p = {p} > alpha = {alpha}; "
            f"the outcome contradicts the test it names"
        )
    else:
        return None
    return EpistemicViolation(
        code="HML-E704",
        claim=name,
        message=message,
        status=claim.status,
        actual=claim.justification,
    )


# ---------------------------------------------------------------------------
# likely — presentation level only
# ---------------------------------------------------------------------------


class UncalibratedLikelyError(ValueError):
    """An uncalibrated hedge was asked to become a formal claim."""


@dataclass(frozen=True)
class Calibration:
    """What makes a degree of belief mean something: a number, a reference class, a source.

    All three are required. "Likely, with probability 0.8" against no reference class is
    a number attached to a feeling; it is not a calibrated credence and this layer does
    not treat it as one.
    """

    probability: float
    reference_class: str
    source: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(
                f"probability {self.probability} is outside [0, 1]; a credence is a "
                f"Probability"
            )
        if not self.reference_class or not self.source:
            raise ValueError(
                "a calibration needs both a reference class and a source; without them "
                "the number is not calibrated against anything"
            )

    def render(self) -> str:
        return (
            f"p = {self.probability} over {self.reference_class} (source: {self.source})"
        )


@dataclass(frozen=True)
class Likely:
    """A hedge. **Presentation level only — not an** ``EpistemicStatus``.

    ``likely`` is the phrase that most often smuggles an unearned formal status into a
    document, so it is kept out of the status enum entirely: there is no
    ``EpistemicStatus.LIKELY`` to be reached by any route.

    * uncalibrated — :meth:`as_claim` raises, :meth:`trusted_status` is ``None``,
      :meth:`justification` is ``None``. It renders as English and does nothing else.
    * calibrated — :meth:`as_claim` yields a ``possible`` claim, whose justification is
      ``Credence``. That still discharges no goal and still has no coercion to ``Proof``.

    In neither case does ``likely`` become trusted. Calibration buys a recorded number and
    a reference class, not an upgrade in kind.
    """

    body: str
    calibration: Calibration | None = None

    @property
    def calibrated(self) -> bool:
        return self.calibration is not None

    def is_kernel_state(self) -> bool:
        """``False`` always: a hedge changes no obligation, type or dependency.

        An uncalibrated ``likely`` fails the admission rule of
        `docs/design/V1_KERNEL.md` §0 outright. A calibrated one enters the kernel only
        once it has been converted with :meth:`as_claim`, at which point it is a
        ``Credence`` claim and not a ``Likely`` any more.
        """
        return False

    def trusted_status(self) -> EpistemicStatus | None:
        """The formal status this hedge carries. ``None`` when uncalibrated."""
        if self.calibration is None:
            return None
        return EpistemicStatus.POSSIBLE

    def justification(self) -> Justification | None:
        """``None`` when uncalibrated; ``Credence`` when calibrated. Never ``Proof``."""
        if self.calibration is None:
            return None
        return Justification.CREDENCE

    def discharges_goals(self) -> bool:
        """``False`` in both cases."""
        return False

    def as_claim(self) -> EpistemicClaim:
        """Promote to a formal claim, or refuse.

        Raises :class:`UncalibratedLikelyError` when there is no calibration. This is the
        single door between the presentation level and the kernel, and it is shut unless
        a probability, a reference class and a source are supplied.
        """
        if self.calibration is None:
            raise UncalibratedLikelyError(
                f"'likely: {self.body}' is uncalibrated and has no formal status; "
                f"supply a Calibration (probability, reference class, source) or leave "
                f"the hedge in the rendered prose, where it changes nothing"
            )
        return EpistemicClaim(
            status=EpistemicStatus.POSSIBLE,
            body=self.body,
            context={
                "probability": str(self.calibration.probability),
                "reference_class": self.calibration.reference_class,
                "source": self.calibration.source,
            },
        )

    def render_english(self) -> str:
        if self.calibration is None:
            return (
                f"It is likely that {self.body}. (Uncalibrated: this carries no formal "
                f"status and establishes nothing.)"
            )
        return f"It is likely that {self.body} ({self.calibration.render()})."


# ---------------------------------------------------------------------------
# The checker
# ---------------------------------------------------------------------------


@dataclass
class EpistemicChecker:
    """Holds named claims and rejects uses that demand a stronger justification.

    Every method records its own findings and returns them, rather than raising: the
    product here is a report of everything wrong, not the first thing wrong.
    """

    _claims: dict[str, EpistemicClaim] = field(default_factory=dict)
    _hedges: dict[str, Likely] = field(default_factory=dict)
    _violations: list[EpistemicViolation] = field(default_factory=list)
    _dependencies: list[Dependency] = field(default_factory=list)

    # -- declaration ---------------------------------------------------------

    def declare(self, name: str, claim: EpistemicClaim) -> EpistemicViolation | None:
        if name in self._claims or name in self._hedges:
            return self._record(
                EpistemicViolation(
                    "HML-E703", name, f"claim {name!r} is already declared"
                )
            )
        self._claims[name] = claim
        coherence = check_test_coherence(name, claim)
        if coherence is not None:
            return self._record(coherence)
        return None

    def declare_status(
        self,
        name: str,
        status: EpistemicStatus,
        body: str,
        **context: str,
    ) -> EpistemicViolation | None:
        """Declare from raw parts, turning a :class:`ContextError` into a diagnostic."""
        try:
            claim = EpistemicClaim(status=status, body=body, context=dict(context))
        except ContextError as exc:
            return self._record(
                EpistemicViolation("HML-E706", name, str(exc), status=status)
            )
        return self.declare(name, claim)

    def declare_hedge(self, name: str, hedge: Likely) -> EpistemicViolation | None:
        """Record a ``likely``. It stays presentation-level until calibrated."""
        if name in self._claims or name in self._hedges:
            return self._record(
                EpistemicViolation(
                    "HML-E703", name, f"claim {name!r} is already declared"
                )
            )
        self._hedges[name] = hedge
        return None

    # -- use -----------------------------------------------------------------

    def use(self, name: str, site: Site) -> EpistemicViolation | None:
        """Use claim ``name`` at ``site``. Returns the violation, if any."""
        if name in self._hedges:
            return self._use_hedge(name, self._hedges[name], site)

        claim = self._claims.get(name)
        if claim is None:
            return self._record(
                EpistemicViolation(
                    "HML-E701", name, f"no claim named {name!r} is in scope", site=site
                )
            )

        self._note_dependencies(name, claim)

        if site is Site.REPORT:
            return None

        actual = claim.justification

        if site is Site.DISCHARGE:
            if DISCHARGES_GOALS[actual]:
                return None
            return self._record(
                EpistemicViolation(
                    "HML-E702",
                    name,
                    f"a goal is discharged only by a Proof (or a Refutation); "
                    f"{name} is {claim.status}, which is {actual}-justified. "
                    f"{coercion_allowed(actual, Justification.PROOF)[1]}",
                    site=site,
                    required=Justification.PROOF,
                    actual=actual,
                    status=claim.status,
                )
            )

        required = REQUIRED_JUSTIFICATION_BY_SITE[site]
        ok, reason = coercion_allowed(actual, required)
        if ok:
            return None
        return self._record(
            EpistemicViolation(
                "HML-E702",
                name,
                f"{site} requires {required}; {name} is {claim.status}, which is "
                f"{actual}-justified. {reason}",
                site=site,
                required=required,
                actual=actual,
                status=claim.status,
            )
        )

    def _use_hedge(
        self, name: str, hedge: Likely, site: Site
    ) -> EpistemicViolation | None:
        if site is Site.REPORT:
            return None
        if not hedge.calibrated:
            return self._record(
                EpistemicViolation(
                    "HML-E705",
                    name,
                    f"{site} requires a formal status, but {name} is an uncalibrated "
                    f"'likely'. An uncalibrated hedge has no status: it is presentation "
                    f"only and may not be used where a justification is required",
                    site=site,
                    required=REQUIRED_JUSTIFICATION_BY_SITE.get(site),
                )
            )
        # A calibrated hedge is a Credence claim, and is checked exactly as one.
        claim = hedge.as_claim()
        self._claims[name] = claim
        del self._hedges[name]
        return self.use(name, site)

    def _note_dependencies(self, name: str, claim: EpistemicClaim) -> None:
        if claim.justification is Justification.ASSUMPTION:
            self._add_dependency(
                Dependency(
                    name,
                    claim.context.get("model", claim.body),
                    "an assumption is granted, not established; it carries forward",
                )
            )
        if claim.status is EpistemicStatus.MODEL_CONDITIONAL:
            self._add_dependency(
                Dependency(
                    name,
                    claim.context["model"],
                    "the claim holds relative to this model and not outside it",
                )
            )

    def _add_dependency(self, dependency: Dependency) -> None:
        if dependency not in self._dependencies:
            self._dependencies.append(dependency)

    def _record(self, violation: EpistemicViolation) -> EpistemicViolation:
        self._violations.append(violation)
        return violation

    # -- results -------------------------------------------------------------

    def claim(self, name: str) -> EpistemicClaim | None:
        return self._claims.get(name)

    def check_all(self, uses: Iterable[tuple[str, Site]]) -> EpistemicReport:
        for name, site in uses:
            self.use(name, site)
        return self.report()

    def report(self) -> EpistemicReport:
        return EpistemicReport(
            violations=tuple(self._violations),
            dependencies=tuple(self._dependencies),
        )
