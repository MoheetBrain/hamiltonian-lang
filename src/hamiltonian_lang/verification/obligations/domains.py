"""Refinement domains, sound interval arithmetic, and the sample grid.

Two facts about a name are what make an obligation decidable at all:

1. **What set can it range over?** A ``param sigma : PositiveReal`` ranges over
   ``(0, inf)``. That is not a guess; it is what the scalar lattice in
   :mod:`hamiltonian_lang.types` already means, restated as an interval so arithmetic
   can be done on it.
2. **Is it pinned to a value?** A ``const g : Real = 9.81`` is a point. So is an
   ``obs n : Natural = 7``. Substituting a point is definitional unfolding, not
   inference.

Soundness contract
------------------
:class:`Interval` is an **over-approximation**. ``interval_of(e)`` returns a set
guaranteed to *contain* every value ``e`` can take under the declared domains; it may
contain more. Two consequences, and only two, may be drawn from it:

* ``I ⊆ S``  ⟹ the property ``S`` holds for every assignment. Usable for
  ``DISCHARGED``.
* ``I ∩ S = ∅`` ⟹ the property holds for no assignment. **Not** used here for
  ``FAILED``: a refutation must exhibit a witness, and an empty intersection with an
  over-approximation does not hand you one. Refutation goes through
  :mod:`.numeric` instead, which evaluates a concrete assignment.

Nothing else may be concluded. In particular ``I ∩ S != ∅`` means nothing at all.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from ...types import (
    QuantityType,
    ScalarType,
    Type,
)

__all__ = [
    "Interval",
    "Domain",
    "UNBOUNDED",
    "EMPTY",
    "domain_of_type",
    "SAMPLE_GRID",
    "sample_points",
    "constant_points",
    "assignments",
]

Number = Fraction


@dataclass(frozen=True)
class Interval:
    """A closed/open interval over the rationals, with optional integrality.

    ``lo``/``hi`` of ``None`` mean unbounded on that side. ``integral`` restricts the
    set to integers, which is what makes ``Natural`` different from ``NonNegativeReal``
    and is load-bearing for finite-domain exhaustion.
    """

    lo: Fraction | None = None
    lo_closed: bool = False
    hi: Fraction | None = None
    hi_closed: bool = False
    integral: bool = False
    empty: bool = False

    @staticmethod
    def point(value: Fraction) -> Interval:
        return Interval(value, True, value, True, integral=value.denominator == 1)

    def contains(self, v: Fraction) -> bool:
        if self.empty:
            return False
        if self.integral and v.denominator != 1:
            return False
        if self.lo is not None:
            if v < self.lo or (v == self.lo and not self.lo_closed):
                return False
        if self.hi is not None:
            if v > self.hi or (v == self.hi and not self.hi_closed):
                return False
        return True

    # -- the only two sound queries -------------------------------------
    def entirely_above(self, c: Fraction, *, strict: bool) -> bool:
        """True when every member satisfies ``v > c`` (strict) / ``v >= c``."""
        if self.empty:
            return False  # a vacuous domain proves nothing; say so rather than pass
        if self.lo is None:
            return False
        if self.lo > c:
            return True
        return self.lo == c and (not strict or not self.lo_closed)

    def entirely_below(self, c: Fraction, *, strict: bool) -> bool:
        if self.empty:
            return False
        if self.hi is None:
            return False
        if self.hi < c:
            return True
        return self.hi == c and (not strict or not self.hi_closed)

    def intersect(self, other: Interval) -> Interval:
        """The exact intersection. Used to decide whether a constraint set has a model."""
        if self.empty or other.empty:
            return Interval(empty=True)
        lo, lo_closed = self.lo, self.lo_closed
        if other.lo is not None and (lo is None or other.lo > lo):
            lo, lo_closed = other.lo, other.lo_closed
        elif other.lo is not None and lo is not None and other.lo == lo:
            lo_closed = lo_closed and other.lo_closed
        hi, hi_closed = self.hi, self.hi_closed
        if other.hi is not None and (hi is None or other.hi < hi):
            hi, hi_closed = other.hi, other.hi_closed
        elif other.hi is not None and hi is not None and other.hi == hi:
            hi_closed = hi_closed and other.hi_closed
        integral = self.integral or other.integral
        if lo is not None and hi is not None:
            if lo > hi or (lo == hi and not (lo_closed and hi_closed)):
                return Interval(empty=True)
            if integral and not any(
                Fraction(n) >= lo and Fraction(n) <= hi
                for n in range(int(lo) - 1, int(hi) + 2)
                if Interval(lo, lo_closed, hi, hi_closed, True).contains(Fraction(n))
            ):
                return Interval(empty=True)
        return Interval(lo, lo_closed, hi, hi_closed, integral)

    def is_point(self) -> bool:
        return (
            not self.empty
            and self.lo is not None
            and self.hi is not None
            and self.lo == self.hi
            and self.lo_closed
            and self.hi_closed
        )

    def finite_members(self, limit: int = 64) -> list[Fraction] | None:
        """Every member, when the set is finite and small. ``None`` otherwise.

        Only integral bounded intervals are finite. This is what lets
        ``forall b : Bool . ...`` and ``forall n : Natural in [0, 3] . ...`` be decided
        by exhaustion rather than sampled.
        """
        if self.empty:
            return []
        if not self.integral or self.lo is None or self.hi is None:
            return None
        lo = int(self.lo) + (0 if (self.lo_closed and self.lo.denominator == 1) else 1)
        if self.lo.denominator != 1:
            lo = int(self.lo) + 1
        hi = int(self.hi) - (0 if (self.hi_closed and self.hi.denominator == 1) else 1)
        if self.hi.denominator != 1:
            hi = int(self.hi)
        if hi < lo:
            return []
        if hi - lo + 1 > limit:
            return None
        return [Fraction(n) for n in range(lo, hi + 1)]

    def render(self) -> str:
        if self.empty:
            return "{}"
        left = "[" if self.lo_closed else "("
        right = "]" if self.hi_closed else ")"
        lo = "-inf" if self.lo is None else _num(self.lo)
        hi = "+inf" if self.hi is None else _num(self.hi)
        suffix = " ∩ Z" if self.integral else ""
        return f"{left}{lo}, {hi}{right}{suffix}"


def _num(f: Fraction) -> str:
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


UNBOUNDED = Interval()
EMPTY = Interval(empty=True)

#: Boolean is the one genuinely finite scalar domain in v0. Encoded as {0, 1}.
_BOOL = Interval(Fraction(0), True, Fraction(1), True, integral=True)

_SCALAR_DOMAINS: dict[str, Interval] = {
    "Bool": _BOOL,
    "Real": UNBOUNDED,
    "Rational": UNBOUNDED,
    "Integer": Interval(integral=True),
    "Natural": Interval(Fraction(0), True, None, False, integral=True),
    "PositiveNatural": Interval(Fraction(1), True, None, False, integral=True),
    "NonNegativeReal": Interval(Fraction(0), True, None, False),
    "PositiveReal": Interval(Fraction(0), False, None, False),
    # The three unit-interval kinds are numerically identical and epistemically
    # incomparable. Their *domains* coincide; the type system keeps them apart, and
    # nothing here merges them — this table is consulted by name, never by subtyping.
    "Probability": Interval(Fraction(0), True, Fraction(1), True),
    "PValue": Interval(Fraction(0), True, Fraction(1), True),
    "PosteriorProbability": Interval(Fraction(0), True, Fraction(1), True),
}


@dataclass(frozen=True)
class Domain:
    """What one bound name may range over, and why."""

    name: str
    interval: Interval
    type_name: str
    #: Set when a declaration pinned the name to a literal.
    pinned: Fraction | None = None
    sampleable: bool = True
    reason: str = ""

    def render(self) -> str:
        if self.pinned is not None:
            return f"{self.name} = {_num(self.pinned)}"
        return f"{self.name} ∈ {self.interval.render()}  ({self.type_name})"


def domain_of_type(t: Type | None) -> Interval | None:
    """The interval a declared type confines a value to. ``None`` when unmodelled.

    Only scalars and dimensionless quantities are modelled. A dimensioned
    ``Quantity[Length]`` is deliberately excluded: its numeric value is
    unit-relative, so comparing it against a bare literal is not a well-posed
    numeric question and pretending otherwise would be exactly the silent-coercion
    failure this codebase forbids.
    """
    if isinstance(t, ScalarType):
        return _SCALAR_DOMAINS.get(t.name)
    if isinstance(t, QuantityType):
        if t.dimension.is_dimensionless():
            return UNBOUNDED
        return None
    return None


#: Deterministic representative points per scalar domain, ordered so that the cheapest
#: and most discriminating candidates come first. The grid is a **refutation** device:
#: finding a point that breaks a claim disproves it; finding none proves nothing.
SAMPLE_GRID: dict[str, tuple[Fraction, ...]] = {
    "Bool": (Fraction(0), Fraction(1)),
    "Real": tuple(
        Fraction(x) for x in ("0", "1", "-1", "1/2", "-1/2", "2", "-2", "10", "-10", "7/2")
    ),
    "Rational": tuple(Fraction(x) for x in ("0", "1", "-1", "1/2", "-1/2", "2", "-2", "10")),
    "Integer": tuple(Fraction(x) for x in ("0", "1", "-1", "2", "-2", "7", "-7", "10")),
    "Natural": tuple(Fraction(x) for x in ("0", "1", "2", "3", "7", "10")),
    "PositiveNatural": tuple(Fraction(x) for x in ("1", "2", "3", "7", "10")),
    "NonNegativeReal": tuple(Fraction(x) for x in ("0", "1/2", "1", "2", "7/2", "10")),
    "PositiveReal": tuple(Fraction(x) for x in ("1/1000", "1/2", "1", "2", "7/2", "10")),
    "Probability": tuple(Fraction(x) for x in ("0", "1/4", "1/2", "3/4", "1")),
    "PValue": tuple(Fraction(x) for x in ("0", "1/20", "1/2", "1")),
    "PosteriorProbability": tuple(Fraction(x) for x in ("0", "1/4", "1/2", "3/4", "1")),
}


def sample_points(
    domain: Domain, *, limit: int = 24, extra: Sequence[Fraction] = ()
) -> tuple[Fraction, ...]:
    """Candidate values for ``domain``, in a fixed order. Never random.

    ``extra`` carries the constants that appear in the obligation itself, together with
    their neighbours — see :func:`constant_points`. A constraint written ``spend >= 50``
    is satisfied nowhere on a generic grid that stops at 10, and reporting "no model
    found" there would say more about the grid than about the constraint. Adding the
    problem's own numbers changes only the *power* of the search: the grid is a search
    heuristic, and every verdict it produces is checked by evaluating the candidate, so
    a wider grid can never make an unsound claim.
    """
    if domain.pinned is not None:
        return (domain.pinned,)
    exhaustive = domain.interval.finite_members()
    if exhaustive is not None:
        return tuple(exhaustive[:limit])
    grid = SAMPLE_GRID.get(domain.type_name, SAMPLE_GRID["Real"])
    seen: list[Fraction] = []
    for value in (*extra, *grid):
        if not domain.interval.contains(value):
            continue
        if value in seen:
            continue
        seen.append(value)
    return tuple(seen[:limit])


def constant_points(constants: Iterable[Fraction]) -> tuple[Fraction, ...]:
    """The constants of an obligation, plus one step either side, deduplicated.

    A boundary constraint is satisfied at, just above, or just below its own constant;
    those three points are where a model is most likely to be, and where a
    counterexample to a boundary claim is most likely to sit.
    """
    out: list[Fraction] = []
    for c in constants:
        for candidate in (c, c - 1, c + 1, c / 2 if c != 0 else Fraction(0)):
            if candidate not in out:
                out.append(candidate)
    return tuple(out)


def assignments(
    domains: Mapping[str, Domain],
    *,
    budget: int = 4096,
    limit: int = 24,
    extra: Sequence[Fraction] = (),
) -> Iterator[dict[str, Fraction]]:
    """Every combination of sample points, in a deterministic order, up to ``budget``.

    Yields nothing when the search space would exceed ``budget``: an exhausted budget
    must not be reported as "searched and found nothing", so the caller sees an empty
    iterator and the checker reports ``UNSUPPORTED`` for exceeding its own bound.
    """
    names = sorted(domains)
    grids = [sample_points(domains[n], limit=limit, extra=extra) for n in names]
    if any(len(g) == 0 for g in grids):
        return
    total = 1
    for g in grids:
        total *= len(g)
        if total > budget:
            return
    indices = [0] * len(names)
    for _ in range(total):
        yield {n: grids[i][indices[i]] for i, n in enumerate(names)}
        for i in range(len(names) - 1, -1, -1):
            indices[i] += 1
            if indices[i] < len(grids[i]):
                break
            indices[i] = 0
