"""Phase 11 — the versioned skill taxonomy, and attribution of outcomes to skills.

What a skill is here
--------------------
A skill is a *distinction the language makes* that an output can get right or wrong on
its own. "Writes good HML" is not a skill: it cannot be attributed, so it cannot be
improved deliberately. "Calls a function with the arity its signature declares" is a
skill: a single diagnostic attributes to it, and the count of successes and failures on
it means something.

The taxonomy lives in ``spec/skills/skill_taxonomy.yaml`` and is versioned there. This
module loads it; it does not carry a second copy. Three invariants of that file are
checked by tests rather than asserted in prose: every diagnostic code named exists in
the compiler, the code sets are pairwise disjoint so attribution is a function, and a
skill with no codes is explicitly marked as such rather than borrowing another's.

Why a Beta posterior
--------------------
Six successes out of six and sixty out of sixty are both "100%". A ratio cannot tell
them apart and a decision made on the ratio treats them the same. The Beta posterior
carries the count: ``mastery`` is its mean and ``uncertainty`` is its standard
deviation, so a gate can require both a level and a level of confidence. The prior is
uniform, ``Beta(1, 1)``, and is stated in the aggregate so a reader knows what was
assumed rather than inferring it.

Two things this module refuses to compute
-----------------------------------------
**Learning gain per token from one round.** A gain is a difference between two
measurements. With one round there is no difference to divide, and dividing the
*level* by the tokens spent would produce a number that looks like a rate and is not
one. ``learning_gain_per_token`` returns ``Unavailable`` with the count it has and the
count it needs, and there is no code path that returns a float from a single round.

**Token counts the adapter never reported.** A missing count is ``None``, never zero.
An aggregate over any observation with a missing count is ``Unavailable``, because a
sum that silently treats unreported as zero understates cost and the understatement is
invisible.

Forgetting is a declared hook, not an implementation
----------------------------------------------------
``ForgettingModel`` is a Protocol with one default: ``NoForgetting``, which returns the
raw counts and reports ``available = False``. Retention decay needs repeated exposure of
the same skill separated in time, and no such data exists yet. The hook exists so that
the shape of the eventual model is fixed now; the default exists so that nothing today
silently assumes decay it has not observed.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .state import Hypothesis, Measurement, Unavailable, require_single_hypothesis

__all__ = [
    "aggregate_observations",
    "TaxonomyError",
    "SKILL_TAXONOMY_PATH",
    "Skill",
    "SkillStatus",
    "SkillTaxonomy",
    "load_taxonomy",
    "default_taxonomy",
    "TokenSource",
    "TokenAccount",
    "SkillObservation",
    "BetaPosterior",
    "UNIFORM_PRIOR",
    "ForgettingModel",
    "NoForgetting",
    "RoundSummary",
    "SkillAggregate",
    "SkillLedger",
]

#: The taxonomy is repository data, beside the other specs. Same locating convention as
#: ``v1/registry.py``: three levels up from this file is the repository root.
SKILL_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[3] / "spec" / "skills" / "skill_taxonomy.yaml"
)


class TaxonomyError(ValueError):
    """Raised when the taxonomy file is missing, malformed, or self-inconsistent."""


# ---------------------------------------------------------------------------
# A deliberately small YAML reader
# ---------------------------------------------------------------------------
#
# This is not a YAML parser and does not try to be one. It reads the fixed subset the
# taxonomy uses — nested mappings at two-space indentation, double-quoted or bare
# scalars, inline lists of bare scalars, full-line comments — and raises on everything
# else. Adding PyYAML would put a dependency into a package whose core has none, for one
# file; guessing at the rest of YAML would let a malformed taxonomy load half-read, which
# is worse than not loading.

_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_BARE_SCALAR = re.compile(r"^[A-Za-z0-9_.\-+/]+$")


def _scalar(text: str, lineno: int) -> Any:
    if text.startswith('"'):
        if not text.endswith('"') or len(text) < 2:
            raise TaxonomyError(f"line {lineno}: unterminated quoted string")
        body = text[1:-1]
        if '"' in body or "\\" in body:
            raise TaxonomyError(
                f"line {lineno}: quoted strings in this subset carry no escapes or inner quotes"
            )
        return body
    if text.startswith("["):
        if not text.endswith("]"):
            raise TaxonomyError(f"line {lineno}: unterminated inline list")
        inner = text[1:-1].strip()
        if not inner:
            return []
        items = [part.strip() for part in inner.split(",")]
        for item in items:
            if not _BARE_SCALAR.match(item):
                raise TaxonomyError(
                    f"line {lineno}: inline list items must be bare scalars; got {item!r}"
                )
        return items
    if text in ("true", "false"):
        return text == "true"
    if _BARE_SCALAR.match(text):
        return text
    raise TaxonomyError(
        f"line {lineno}: {text!r} is outside the supported subset; quote it or simplify it"
    )


def _parse_subset(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-2, root)]
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw:
            raise TaxonomyError(f"line {lineno}: tabs are not permitted")
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2:
            raise TaxonomyError(f"line {lineno}: indentation must be a multiple of two spaces")
        line = raw.strip()
        if line.startswith("-"):
            raise TaxonomyError(f"line {lineno}: block sequences are outside the subset")
        if ":" not in line:
            raise TaxonomyError(f"line {lineno}: expected 'key:' or 'key: value'")
        key, _, rest = line.partition(":")
        key, rest = key.strip(), rest.strip()
        if not _KEY.match(key):
            raise TaxonomyError(f"line {lineno}: {key!r} is not a valid key")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise TaxonomyError(f"line {lineno}: indentation does not match any open mapping")
        parent_indent, parent = stack[-1]
        if indent != parent_indent + 2:
            raise TaxonomyError(
                f"line {lineno}: expected indentation {parent_indent + 2}, found {indent}"
            )
        if key in parent:
            raise TaxonomyError(f"line {lineno}: duplicate key {key!r} in this mapping")
        if rest:
            parent[key] = _scalar(rest, lineno)
        else:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
    return root


# ---------------------------------------------------------------------------
# The taxonomy
# ---------------------------------------------------------------------------


class SkillStatus(StrEnum):
    ENFORCED = "enforced"
    PARTIAL = "partial"
    NO_DEDICATED_DIAGNOSTIC = "no_dedicated_diagnostic"


@dataclass(frozen=True)
class Skill:
    skill_id: str
    family: str
    name: str
    description: str
    evidence: str
    status: SkillStatus
    diagnostics: tuple[str, ...]
    limitation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "family": self.family,
            "name": self.name,
            "description": self.description,
            "evidence": self.evidence,
            "status": self.status.value,
            "diagnostics": list(self.diagnostics),
            "limitation": self.limitation,
        }


@dataclass(frozen=True)
class SkillTaxonomy:
    version: str
    schema: str
    status: str
    basis: str
    skills: Mapping[str, Skill]
    source_path: Path

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.skills))

    def families(self) -> tuple[str, ...]:
        return tuple(sorted({s.family for s in self.skills.values()}))

    def skill(self, skill_id: str) -> Skill:
        try:
            return self.skills[skill_id]
        except KeyError:
            raise TaxonomyError(
                f"unknown skill {skill_id!r}; the taxonomy defines {', '.join(self.ids())}"
            ) from None

    def require_known(self, skill_ids: Iterable[str]) -> tuple[str, ...]:
        ids = tuple(skill_ids)
        unknown = [s for s in ids if s not in self.skills]
        if unknown:
            raise TaxonomyError(f"unknown skill id(s): {sorted(unknown)}")
        return ids

    def attribute(self, diagnostic_code: str) -> str | None:
        """The skill a diagnostic attributes to, or ``None`` if no skill claims it.

        A function, not a heuristic: the taxonomy's code sets are disjoint, and a test
        enforces that. ``None`` is returned rather than a guess.
        """
        for skill in self.skills.values():
            if diagnostic_code in skill.diagnostics:
                return skill.skill_id
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "schema": self.schema,
            "status": self.status,
            "basis": self.basis,
            "source_path": str(self.source_path),
            "skills": {k: v.to_dict() for k, v in sorted(self.skills.items())},
        }


_SKILL_REQUIRED = ("description", "evidence", "status", "diagnostics")
_SKILL_OPTIONAL = ("limitation",)


def load_taxonomy(path: Path | None = None) -> SkillTaxonomy:
    """Load and validate the taxonomy. Every failure raises; nothing is defaulted."""
    p = path or SKILL_TAXONOMY_PATH
    if not p.exists():
        raise TaxonomyError(
            f"skill taxonomy not found at {p}. It is repository data and is required; "
            "there is no built-in fallback, because a fallback taxonomy would be an "
            "unversioned one."
        )
    doc = _parse_subset(p.read_text(encoding="utf-8"))
    for key in ("version", "schema", "status", "basis", "families"):
        if key not in doc:
            raise TaxonomyError(f"{p}: missing top-level key {key!r}")
    families = doc["families"]
    if not isinstance(families, dict) or not families:
        raise TaxonomyError(f"{p}: 'families' must be a non-empty mapping")

    skills: dict[str, Skill] = {}
    for family_name, family in sorted(families.items()):
        if not isinstance(family, dict) or "skills" not in family:
            raise TaxonomyError(f"{p}: family {family_name!r} declares no skills")
        entries = family["skills"]
        if not isinstance(entries, dict) or not entries:
            raise TaxonomyError(f"{p}: family {family_name!r} has an empty skill mapping")
        for name, entry in sorted(entries.items()):
            if not isinstance(entry, dict):
                raise TaxonomyError(f"{p}: skill {family_name}.{name} is not a mapping")
            missing = [k for k in _SKILL_REQUIRED if k not in entry]
            if missing:
                raise TaxonomyError(f"{p}: skill {family_name}.{name} is missing {missing}")
            extra = set(entry) - set(_SKILL_REQUIRED) - set(_SKILL_OPTIONAL)
            if extra:
                raise TaxonomyError(
                    f"{p}: skill {family_name}.{name} carries unknown key(s) {sorted(extra)}"
                )
            try:
                status = SkillStatus(entry["status"])
            except ValueError:
                raise TaxonomyError(
                    f"{p}: skill {family_name}.{name} has unknown status {entry['status']!r}"
                ) from None
            codes = tuple(entry["diagnostics"])
            if bool(codes) == (status is SkillStatus.NO_DEDICATED_DIAGNOSTIC):
                raise TaxonomyError(
                    f"{p}: skill {family_name}.{name} must have an empty diagnostics list "
                    "exactly when its status is no_dedicated_diagnostic"
                )
            if status is not SkillStatus.ENFORCED and not entry.get("limitation", "").strip():
                raise TaxonomyError(
                    f"{p}: skill {family_name}.{name} has status {status.value} and must "
                    "state its limitation"
                )
            skill_id = f"{family_name}.{name}"
            skills[skill_id] = Skill(
                skill_id=skill_id,
                family=family_name,
                name=name,
                description=str(entry["description"]),
                evidence=str(entry["evidence"]),
                status=status,
                diagnostics=codes,
                limitation=str(entry.get("limitation", "")),
            )

    seen: dict[str, str] = {}
    for skill in skills.values():
        for code in skill.diagnostics:
            if code in seen:
                raise TaxonomyError(
                    f"{p}: diagnostic {code} is claimed by both {seen[code]} and "
                    f"{skill.skill_id}; attribution must be a function"
                )
            seen[code] = skill.skill_id

    return SkillTaxonomy(
        version=str(doc["version"]),
        schema=str(doc["schema"]),
        status=str(doc["status"]),
        basis=str(doc["basis"]),
        skills=skills,
        source_path=p,
    )


_CACHED: dict[Path, SkillTaxonomy] = {}


def default_taxonomy() -> SkillTaxonomy:
    """The repository taxonomy, loaded once per path."""
    if SKILL_TAXONOMY_PATH not in _CACHED:
        _CACHED[SKILL_TAXONOMY_PATH] = load_taxonomy(SKILL_TAXONOMY_PATH)
    return _CACHED[SKILL_TAXONOMY_PATH]


# ---------------------------------------------------------------------------
# Observations and token accounting
# ---------------------------------------------------------------------------


class TokenSource(StrEnum):
    """Where a token count came from. There is no ``ESTIMATED``, on purpose."""

    REPORTED = "reported"
    NOT_REPORTED = "not_reported"


@dataclass(frozen=True)
class TokenAccount:
    """Tokens for one exchange. Unreported is ``None`` and never zero."""

    source: TokenSource = TokenSource.NOT_REPORTED
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.source is TokenSource.NOT_REPORTED and (
            self.prompt_tokens is not None or self.completion_tokens is not None
        ):
            raise ValueError(
                "token counts are present but the source says they were not reported; "
                "one of the two is wrong and neither may be assumed"
            )
        if self.source is TokenSource.REPORTED and (
            self.prompt_tokens is None or self.completion_tokens is None
        ):
            raise ValueError(
                "source says the counts were reported, but one of them is missing"
            )
        for name in ("prompt_tokens", "completion_tokens"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative")

    @property
    def total(self) -> int | Unavailable:
        if self.source is TokenSource.NOT_REPORTED:
            return Unavailable(
                "the adapter reported no token counts",
                "a model adapter that returns usage counts",
            )
        assert self.prompt_tokens is not None and self.completion_tokens is not None
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, Any]:
        total = self.total
        return {
            "source": self.source.value,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": total.to_dict() if isinstance(total, Unavailable) else total,
        }


@dataclass(frozen=True)
class SkillObservation:
    """One attributable outcome for one skill, under one hypothesis, in one round."""

    observation_id: str
    skill_id: str
    hypothesis: Hypothesis
    episode_id: str
    round_id: str
    success: bool
    tokens: TokenAccount = field(default_factory=TokenAccount)
    state_fingerprint: str = ""
    diagnostic_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, Hypothesis):
            raise TypeError(
                "SkillObservation.hypothesis must be a Hypothesis member; an untyped "
                "hypothesis cannot be kept out of another hypothesis's statistics"
            )
        if not self.round_id.strip():
            raise ValueError("every observation belongs to a named round")

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "skill_id": self.skill_id,
            "hypothesis": self.hypothesis.value,
            "episode_id": self.episode_id,
            "round_id": self.round_id,
            "success": self.success,
            "tokens": self.tokens.to_dict(),
            "state_fingerprint": self.state_fingerprint,
            "diagnostic_codes": list(self.diagnostic_codes),
        }


# ---------------------------------------------------------------------------
# Beta posterior
# ---------------------------------------------------------------------------


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Lentz's method)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _regularised_incomplete_beta(a: float, b: float, x: float) -> float:
    """``I_x(a, b)`` — the Beta CDF. Standard library only; no SciPy in this project."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


@dataclass(frozen=True)
class BetaPosterior:
    """``Beta(alpha, beta)`` over a success probability, with the prior kept visible."""

    alpha: float
    beta: float
    prior_alpha: float = 1.0
    prior_beta: float = 1.0

    def __post_init__(self) -> None:
        if self.alpha <= 0 or self.beta <= 0:
            raise ValueError("Beta parameters must be positive")

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self) -> float:
        a, b = self.alpha, self.beta
        return (a * b) / ((a + b) ** 2 * (a + b + 1.0))

    @property
    def sd(self) -> float:
        return math.sqrt(self.variance)

    def cdf(self, x: float) -> float:
        return _regularised_incomplete_beta(self.alpha, self.beta, x)

    def quantile(self, p: float) -> float:
        """Inverse CDF by bisection. Deterministic to ~1e-15 in 60 iterations."""
        if not 0.0 < p < 1.0:
            raise ValueError("quantile probability must lie strictly inside (0, 1)")
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if self.cdf(mid) < p:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    def credible_interval(self, mass: float = 0.95) -> tuple[float, float]:
        """Equal-tailed interval. Equal-tailed, not highest-density — stated, not implied."""
        if not 0.0 < mass < 1.0:
            raise ValueError("credible mass must lie strictly inside (0, 1)")
        tail = (1.0 - mass) / 2.0
        return self.quantile(tail), self.quantile(1.0 - tail)

    def to_dict(self) -> dict[str, Any]:
        lo, hi = self.credible_interval()
        return {
            "alpha": self.alpha,
            "beta": self.beta,
            "prior": {"alpha": self.prior_alpha, "beta": self.prior_beta},
            "mean": self.mean,
            "sd": self.sd,
            "credible_interval_95_equal_tailed": [lo, hi],
        }


#: The prior every aggregate uses unless told otherwise, recorded in every output.
UNIFORM_PRIOR = (1.0, 1.0)


# ---------------------------------------------------------------------------
# Forgetting: a declared hook with a null default
# ---------------------------------------------------------------------------


@runtime_checkable
class ForgettingModel(Protocol):
    """Maps a history of observations to effective counts.

    The eventual model will weight older observations down. The interface is fixed now
    so the aggregate's shape does not change when one arrives.
    """

    @property
    def name(self) -> str: ...

    @property
    def available(self) -> bool: ...

    def effective_counts(
        self, observations: Sequence[SkillObservation]
    ) -> tuple[float, float]: ...


@dataclass(frozen=True)
class NoForgetting:
    """The default: no decay, because no retention data has been collected.

    ``available`` is ``False`` so that a report can state that forgetting was not
    modelled, rather than leaving a reader to assume it was.
    """

    name: str = "none"
    available: bool = False

    def effective_counts(
        self, observations: Sequence[SkillObservation]
    ) -> tuple[float, float]:
        successes = sum(1 for o in observations if o.success)
        return float(successes), float(len(observations) - successes)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoundSummary:
    round_id: str
    attempts: int
    successes: int
    tokens: int | Unavailable

    @property
    def success_rate(self) -> float | Unavailable:
        if not self.attempts:
            return Unavailable("no attempts in this round", "at least one observation")
        return self.successes / self.attempts

    def to_dict(self) -> dict[str, Any]:
        rate = self.success_rate
        return {
            "round_id": self.round_id,
            "attempts": self.attempts,
            "successes": self.successes,
            "tokens": self.tokens.to_dict() if isinstance(self.tokens, Unavailable) else self.tokens,
            "success_rate": rate.to_dict() if isinstance(rate, Unavailable) else rate,
        }


@dataclass(frozen=True)
class SkillAggregate:
    """Everything known about one skill under **one** hypothesis."""

    skill_id: str
    hypothesis: Hypothesis
    attempts: int
    successes: int
    failures: int
    posterior: BetaPosterior
    rounds: tuple[RoundSummary, ...]
    forgetting_model: str
    forgetting_available: bool
    total_tokens: int | Unavailable

    @property
    def mastery(self) -> float:
        """Posterior mean. A point estimate that carries its count in ``uncertainty``."""
        return self.posterior.mean

    @property
    def uncertainty(self) -> float:
        return self.posterior.sd

    def credible_interval(self, mass: float = 0.95) -> tuple[float, float]:
        return self.posterior.credible_interval(mass)

    def learning_gain_per_token(self) -> Measurement:
        """Mastery gained per token spent, or an explicit statement that it is unknown.

        Requires at least two rounds with complete token accounting: a gain is a
        difference, and one round has none. There is deliberately no branch that returns
        a float when ``len(self.rounds) < 2``.
        """
        if len(self.rounds) < 2:
            return Unavailable(
                f"a gain needs two comparable rounds; this aggregate has {len(self.rounds)}",
                "at least two rounds of observations for this skill under this hypothesis",
            )
        first, last = self.rounds[0], self.rounds[-1]
        spent = 0
        for r in self.rounds[1:]:
            if isinstance(r.tokens, Unavailable):
                return Unavailable(
                    f"round {r.round_id!r} has no token counts, so cost is unknown",
                    "a model adapter that reports usage counts for every round",
                )
            spent += r.tokens
        if spent <= 0:
            return Unavailable(
                "the rounds after the first reported zero tokens",
                "a non-zero measured token cost",
            )
        before, after = first.success_rate, last.success_rate
        if isinstance(before, Unavailable) or isinstance(after, Unavailable):
            return Unavailable(
                "a round has no attempts, so there is no rate to difference",
                "at least one observation in the first and last round",
            )
        return (after - before) / spent

    def to_dict(self) -> dict[str, Any]:
        gain = self.learning_gain_per_token()
        return {
            "skill_id": self.skill_id,
            "hypothesis": self.hypothesis.value,
            "attempts": self.attempts,
            "successes": self.successes,
            "failures": self.failures,
            "mastery": self.mastery,
            "uncertainty": self.uncertainty,
            "posterior": self.posterior.to_dict(),
            "rounds": [r.to_dict() for r in self.rounds],
            "forgetting": {"model": self.forgetting_model, "available": self.forgetting_available},
            "total_tokens": (
                self.total_tokens.to_dict()
                if isinstance(self.total_tokens, Unavailable)
                else self.total_tokens
            ),
            "learning_gain_per_token": gain.to_dict() if isinstance(gain, Unavailable) else gain,
        }


class SkillLedger:
    """Observations, partitioned by ``(skill, hypothesis)`` and never merged across them.

    There is no accessor that takes a skill id alone. That absence is the mechanism: a
    caller cannot accidentally pool H1 and H3 evidence because there is no call that
    would do it.
    """

    def __init__(
        self,
        taxonomy: SkillTaxonomy | None = None,
        forgetting: ForgettingModel | None = None,
        prior: tuple[float, float] = UNIFORM_PRIOR,
    ) -> None:
        self._taxonomy = taxonomy
        self._forgetting: ForgettingModel = forgetting or NoForgetting()
        self._prior = prior
        self._observations: dict[tuple[str, Hypothesis], list[SkillObservation]] = {}

    def add(self, observation: SkillObservation) -> None:
        if self._taxonomy is not None:
            self._taxonomy.require_known([observation.skill_id])
        key = (observation.skill_id, observation.hypothesis)
        self._observations.setdefault(key, []).append(observation)

    def extend(self, observations: Iterable[SkillObservation]) -> None:
        for o in observations:
            self.add(o)

    def observations(
        self, skill_id: str, hypothesis: Hypothesis
    ) -> tuple[SkillObservation, ...]:
        if not isinstance(hypothesis, Hypothesis):
            raise TypeError("a hypothesis is required; observations are never pooled")
        return tuple(self._observations.get((skill_id, hypothesis), ()))

    def skills_observed(self, hypothesis: Hypothesis) -> tuple[str, ...]:
        return tuple(sorted(s for (s, h) in self._observations if h is hypothesis))

    def aggregate(self, skill_id: str, hypothesis: Hypothesis) -> SkillAggregate:
        observations = self.observations(skill_id, hypothesis)
        if not observations:
            raise ValueError(
                f"no observations for {skill_id!r} under {hypothesis.name}; an aggregate "
                "over nothing would be a prior wearing the name of a measurement"
            )
        # Belt and braces: the key partition already guarantees this, and the guard stays
        # so that a future accessor cannot quietly reintroduce pooling.
        require_single_hypothesis(observations, context=f"aggregate({skill_id!r})")

        successes, failures = self._forgetting.effective_counts(observations)
        posterior = BetaPosterior(
            alpha=self._prior[0] + successes,
            beta=self._prior[1] + failures,
            prior_alpha=self._prior[0],
            prior_beta=self._prior[1],
        )
        return SkillAggregate(
            skill_id=skill_id,
            hypothesis=hypothesis,
            attempts=len(observations),
            successes=sum(1 for o in observations if o.success),
            failures=sum(1 for o in observations if not o.success),
            posterior=posterior,
            rounds=_summarise_rounds(observations),
            forgetting_model=self._forgetting.name,
            forgetting_available=self._forgetting.available,
            total_tokens=_sum_tokens(observations),
        )

    def aggregates(self, hypothesis: Hypothesis) -> dict[str, SkillAggregate]:
        return {
            skill_id: self.aggregate(skill_id, hypothesis)
            for skill_id in self.skills_observed(hypothesis)
        }

    def report(self, hypothesis: Hypothesis) -> dict[str, Any]:
        aggregates = self.aggregates(hypothesis)
        return {
            "hypothesis": hypothesis.value,
            "hypothesis_name": hypothesis.name,
            "hypothesis_claim": hypothesis.claim,
            "hypothesis_excluded_claim": hypothesis.excluded_claim,
            "taxonomy_version": self._taxonomy.version if self._taxonomy else None,
            "prior": {"alpha": self._prior[0], "beta": self._prior[1]},
            "skills": {k: v.to_dict() for k, v in sorted(aggregates.items())},
        }


def _sum_tokens(observations: Sequence[SkillObservation]) -> int | Unavailable:
    total = 0
    for o in observations:
        value = o.tokens.total
        if isinstance(value, Unavailable):
            return Unavailable(
                f"observation {o.observation_id!r} has no token counts, so the sum would "
                "understate cost by an unknown amount",
                "usage counts on every observation",
            )
        total += value
    return total


def _summarise_rounds(observations: Sequence[SkillObservation]) -> tuple[RoundSummary, ...]:
    order: list[str] = []
    grouped: dict[str, list[SkillObservation]] = {}
    for o in observations:
        if o.round_id not in grouped:
            order.append(o.round_id)
            grouped[o.round_id] = []
        grouped[o.round_id].append(o)
    summaries: list[RoundSummary] = []
    for round_id in order:
        rows = grouped[round_id]
        summaries.append(
            RoundSummary(
                round_id=round_id,
                attempts=len(rows),
                successes=sum(1 for r in rows if r.success),
                tokens=_sum_tokens(rows),
            )
        )
    return tuple(summaries)


def aggregate_observations(
    observations: Sequence[SkillObservation],
    *,
    taxonomy: SkillTaxonomy | None = None,
    forgetting: ForgettingModel | None = None,
) -> SkillAggregate:
    """Aggregate a hand-supplied sequence. Raises if the sequence mixes hypotheses."""
    if not observations:
        raise ValueError("no observations to aggregate")
    hypothesis = require_single_hypothesis(observations, context="aggregate_observations")
    skill_ids = {o.skill_id for o in observations}
    if len(skill_ids) != 1:
        raise ValueError(
            f"aggregate_observations expects one skill; got {sorted(skill_ids)}"
        )
    ledger = SkillLedger(taxonomy=taxonomy, forgetting=forgetting)
    ledger.extend(observations)
    return ledger.aggregate(next(iter(skill_ids)), hypothesis)
