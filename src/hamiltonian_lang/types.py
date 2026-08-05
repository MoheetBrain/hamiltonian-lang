"""Hamiltonian Lang type system.

This module is the single source of truth for what a *type* is in Hamiltonian Lang.
It is deliberately free of parser and AST dependencies so that it can be imported by
the checker, the backends, and the benchmark harness without cycles.

Design commitments (see ``docs/design/V0_DESIGN_FREEZE.md``, decisions D-004..D-007):

* Scalar refinement types form a **partial order**, not a chain. In particular
  ``Probability`` is NOT a subtype of ``PositiveReal`` (0 and 1 are probabilities but
  are not positive reals under the open-interval reading), and ``PositiveReal`` is not
  a subtype of ``Probability``. Getting this wrong is a semantic error, not a style
  choice.
* Dimensions are rational-exponent vectors over seven SI base dimensions, so
  dimensional algebra is exact and decidable.
* ``RandomVariable[T]`` and ``Distribution[T]`` are *distinct* constructors. A
  distribution is never a value of its own support; conflating them is prohibited by
  ``CLAUDE.md`` rule 9 and is enforced here.
* The three **epistemic kinds of a number in [0, 1]** — ``Probability``, ``PValue``,
  ``PosteriorProbability`` — are mutually incomparable scalars meeting at
  ``NonNegativeReal`` (D-022). They are numerically identical subsets of the unit
  interval, which is precisely why they are confused; the distinction is epistemic and
  can only live in the type.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction

__all__ = [
    "Type",
    "ScalarType",
    "SCALARS",
    "Dimension",
    "DIMENSIONLESS",
    "BASE_DIMENSIONS",
    "QuantityType",
    "VectorType",
    "MatrixType",
    "TensorType",
    "SetType",
    "FunctionType",
    "PredicateType",
    "RandomVariableType",
    "DistributionType",
    "PropositionType",
    "UnknownType",
    "ConceptType",
    "is_subtype",
    "join",
    "meet",
    "parse_scalar_name",
    "is_dimension_variable",
    "UNIT_INTERVAL_KINDS",
]


class Type:
    """Base class for all Hamiltonian Lang types."""

    def render(self) -> str:  # pragma: no cover - overridden everywhere
        raise NotImplementedError

    def __str__(self) -> str:
        return self.render()


# ---------------------------------------------------------------------------
# Scalars and the refinement lattice
# ---------------------------------------------------------------------------

# The scalar refinement order, expressed as immediate-parent edges.
# Read "A: (B,)" as "every A is a B".
_SCALAR_PARENTS: dict[str, tuple[str, ...]] = {
    "Bool": (),
    # PositiveNatural is the meet of Natural and PositiveReal. Without it the literal
    # 1 could not simultaneously inhabit Natural (a count) and PositiveReal (a scale
    # parameter), because Natural contains 0 and so is not a subtype of PositiveReal.
    "PositiveNatural": ("Natural", "PositiveReal"),
    "Natural": ("Integer", "NonNegativeReal"),
    "Integer": ("Rational",),
    "Rational": ("Real",),
    "Real": (),
    "NonNegativeReal": ("Real",),
    "PositiveReal": ("NonNegativeReal",),
    # Probability is the closed unit interval [0, 1]. It is non-negative but it is
    # *not* positive (0 is a probability) and it is bounded above (2.0 is a positive
    # real but not a probability). Hence Probability and PositiveReal are incomparable.
    "Probability": ("NonNegativeReal",),
    # PValue and PosteriorProbability are the other two epistemic kinds of a number in
    # [0, 1] (D-022). Each has NonNegativeReal as its only parent, so the three are
    # pairwise INCOMPARABLE: there is deliberately no subtyping path between any pair in
    # either direction. This mirrors, in the source language, the refusal already
    # encoded by ``v1/epistemic.py::PROHIBITED_PROBABILITY_COERCIONS``, which admits no
    # non-identity coercion among the three.
    #
    # A p-value is P(data at least this extreme | H0); a posterior is P(H0 | data);
    # a model probability is neither. Reading the first as the second is the
    # prosecutor's fallacy. The values are indistinguishable, so only the type can
    # separate them.
    "PValue": ("NonNegativeReal",),
    "PosteriorProbability": ("NonNegativeReal",),
}

SCALARS: tuple[str, ...] = tuple(_SCALAR_PARENTS)

#: The three scalars whose values all lie in [0, 1] and whose difference is epistemic
#: rather than numeric. Exported so that a backend can detect, in one place, that it is
#: about to erase the distinction — every current target erases it, and each must say so.
UNIT_INTERVAL_KINDS: frozenset[str] = frozenset(
    {"Probability", "PValue", "PosteriorProbability"}
)


@dataclass(frozen=True, order=True)
class ScalarType(Type):
    name: str

    def __post_init__(self) -> None:
        if self.name not in _SCALAR_PARENTS:
            raise ValueError(f"unknown scalar type {self.name!r}")

    def render(self) -> str:
        return self.name


def parse_scalar_name(name: str) -> ScalarType | None:
    return ScalarType(name) if name in _SCALAR_PARENTS else None


def _scalar_ancestors(name: str) -> set[str]:
    seen: set[str] = {name}
    stack = list(_SCALAR_PARENTS[name])
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(_SCALAR_PARENTS[cur])
    return seen


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------

BASE_DIMENSIONS: tuple[str, ...] = (
    "Mass",
    "Length",
    "Time",
    "Temperature",
    "Current",
    "Amount",
    "Luminosity",
)


#: A dimension VARIABLE is constrained to a single capital letter.
#:
#: This constraint is load-bearing, not cosmetic. If any unrecognised identifier could
#: stand for a dimension variable, then `Quantity[Lenght]` -- a typo -- would silently
#: become a variable instead of an error, reintroducing exactly the unknown-name hole
#: that HML-T440 closes for ordinary types. A single capital cannot be a plausible typo
#: for `Length`, so the two cases stay separable.
_DIM_VARIABLE = re.compile(r"^[A-Z]$")


def is_dimension_variable(name: str) -> bool:
    return bool(_DIM_VARIABLE.match(name)) and name not in BASE_DIMENSIONS


@dataclass(frozen=True)
class Dimension:
    """A rational-exponent vector over :data:`BASE_DIMENSIONS`, plus optional variables.

    Stored as a canonical mapping with zero exponents elided, so structural equality
    is the correct notion of dimensional equality.

    ``variables`` carries unknown dimensions such as `Quantity[D]`. A dimension with any
    variable is *not* concrete: it can be unified, but it cannot be compared for equality
    against a concrete dimension, and it can never be silently treated as dimensionless.
    """

    exponents: tuple[tuple[str, Fraction], ...] = ()
    variables: tuple[tuple[str, Fraction], ...] = ()

    @staticmethod
    def of(**kwargs: int | Fraction) -> Dimension:
        return Dimension.from_mapping(kwargs)

    @staticmethod
    def variable(name: str, exponent: int | Fraction = 1) -> Dimension:
        if not is_dimension_variable(name):
            raise ValueError(
                f"{name!r} is not a valid dimension variable; use a single capital letter"
            )
        f = Fraction(exponent)
        return Dimension(variables=((name, f),) if f else ())

    def is_concrete(self) -> bool:
        """True when no dimension variable remains. Only concrete dimensions may be
        compared for equality in a dimensional-consistency check."""
        return not self.variables

    def free_variables(self) -> set[str]:
        return {k for k, _ in self.variables}

    @staticmethod
    def from_mapping(
        m: Mapping[str, int | Fraction],
        variables: Mapping[str, int | Fraction] | None = None,
    ) -> Dimension:
        items: list[tuple[str, Fraction]] = []
        for k, v in m.items():
            if k not in BASE_DIMENSIONS:
                raise ValueError(f"unknown base dimension {k!r}")
            f = Fraction(v)
            if f != 0:
                items.append((k, f))
        items.sort()
        vitems: list[tuple[str, Fraction]] = []
        for k, v in (variables or {}).items():
            if not is_dimension_variable(k):
                raise ValueError(f"invalid dimension variable {k!r}")
            f = Fraction(v)
            if f != 0:
                vitems.append((k, f))
        vitems.sort()
        return Dimension(tuple(items), tuple(vitems))

    def as_dict(self) -> dict[str, Fraction]:
        return dict(self.exponents)

    def variables_dict(self) -> dict[str, Fraction]:
        return dict(self.variables)

    def is_dimensionless(self) -> bool:
        """Dimensionless means no base exponents AND no variables.

        A dimension carrying an unresolved variable is not dimensionless -- it is unknown,
        which is a different thing and must not be silently treated as scalar.
        """
        return not self.exponents and not self.variables

    def __mul__(self, other: Dimension) -> Dimension:
        acc = self.as_dict()
        for k, v in other.exponents:
            acc[k] = acc.get(k, Fraction(0)) + v
        vacc = self.variables_dict()
        for k, v in other.variables:
            vacc[k] = vacc.get(k, Fraction(0)) + v
        return Dimension.from_mapping(acc, vacc)

    def __truediv__(self, other: Dimension) -> Dimension:
        return self * other.inverse()

    def inverse(self) -> Dimension:
        return Dimension.from_mapping(
            {k: -v for k, v in self.exponents}, {k: -v for k, v in self.variables}
        )

    def power(self, n: int | Fraction) -> Dimension:
        f = Fraction(n)
        return Dimension.from_mapping(
            {k: v * f for k, v in self.exponents},
            {k: v * f for k, v in self.variables},
        )

    def unify(self, other: Dimension) -> dict[str, Dimension] | None:
        """Solve for the variables that make ``self`` equal ``other``, or None.

        Deliberately narrow: only the single-variable case is solved, which covers
        `Quantity[D]` against a concrete dimension. Anything richer would be a
        constraint solver, which no measured requirement justifies.
        """
        if self == other:
            return {}
        if self.is_concrete() and other.is_concrete():
            return None
        free = self.free_variables() | other.free_variables()
        if len(free) != 1:
            return None
        name = next(iter(free))
        a_exp = self.variables_dict().get(name, Fraction(0))
        b_exp = other.variables_dict().get(name, Fraction(0))
        net = a_exp - b_exp
        if net == 0:
            return None
        # base(other) / base(self), distributed over the net variable exponent
        residual = Dimension(other.exponents) / Dimension(self.exponents)
        return {name: residual.power(Fraction(1, 1) / net)}

    def render(self) -> str:
        if not self.exponents and not self.variables:
            return "Dimensionless"
        allx = list(self.exponents) + list(self.variables)
        num = [(k, v) for k, v in allx if v > 0]
        den = [(k, -v) for k, v in allx if v < 0]

        def term(k: str, v: Fraction) -> str:
            return k if v == 1 else f"{k}^{v}"

        n = " * ".join(term(k, v) for k, v in num) or "1"
        if not den:
            return n
        d = " * ".join(term(k, v) for k, v in den)
        if len(den) > 1:
            d = f"({d})"
        return f"{n} / {d}"

    def __str__(self) -> str:
        return self.render()


DIMENSIONLESS = Dimension()


@dataclass(frozen=True)
class QuantityType(Type):
    """A real-valued magnitude carrying a physical dimension."""

    dimension: Dimension = DIMENSIONLESS
    base: ScalarType = field(default_factory=lambda: ScalarType("Real"))

    def render(self) -> str:
        return f"Quantity[{self.dimension.render()}]"


# ---------------------------------------------------------------------------
# Structured constructors
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VectorType(Type):
    element: Type
    length: str | int | None = None  # symbolic dimension name, literal, or unknown

    def render(self) -> str:
        n = "?" if self.length is None else str(self.length)
        return f"Vector[{self.element.render()}, {n}]"


@dataclass(frozen=True)
class MatrixType(Type):
    element: Type
    rows: str | int | None = None
    cols: str | int | None = None

    def render(self) -> str:
        r = "?" if self.rows is None else str(self.rows)
        c = "?" if self.cols is None else str(self.cols)
        return f"Matrix[{self.element.render()}, {r}, {c}]"


@dataclass(frozen=True)
class TensorType(Type):
    element: Type
    shape: tuple[str | int | None, ...] = ()

    def render(self) -> str:
        dims = ", ".join("?" if d is None else str(d) for d in self.shape)
        return f"Tensor[{self.element.render()}, {dims}]"


@dataclass(frozen=True)
class SetType(Type):
    element: Type

    def render(self) -> str:
        return f"Set[{self.element.render()}]"


@dataclass(frozen=True)
class FunctionType(Type):
    domain: tuple[Type, ...]
    codomain: Type

    def render(self) -> str:
        d = " * ".join(t.render() for t in self.domain) or "Unit"
        return f"Function[{d} -> {self.codomain.render()}]"


@dataclass(frozen=True)
class PredicateType(Type):
    domain: tuple[Type, ...]

    def render(self) -> str:
        d = " * ".join(t.render() for t in self.domain) or "Unit"
        return f"Predicate[{d}]"


@dataclass(frozen=True)
class RandomVariableType(Type):
    """A measurable function into ``codomain``. NOT a value of ``codomain``."""

    codomain: Type

    def render(self) -> str:
        return f"RandomVariable[{self.codomain.render()}]"


@dataclass(frozen=True)
class DistributionType(Type):
    """A probability law over ``support``. NOT a value of ``support``."""

    support: Type

    def render(self) -> str:
        return f"Distribution[{self.support.render()}]"


@dataclass(frozen=True)
class PropositionType(Type):
    def render(self) -> str:
        return "Proposition"


@dataclass(frozen=True)
class ConceptType(Type):
    """The type of a user-minted concept instance (see spec/concept_schema.yaml)."""

    name: str

    def render(self) -> str:
        return self.name


@dataclass(frozen=True)
class UnknownType(Type):
    """Inference placeholder. Never appears in a well-typed frozen program."""

    reason: str = ""

    def render(self) -> str:
        return "Unknown"


# ---------------------------------------------------------------------------
# Subtyping
# ---------------------------------------------------------------------------


def _dims_compatible(a: str | int | None, b: str | int | None) -> bool:
    """Shape agreement. ``None`` is an unknown extent and unifies with anything."""
    return a is None or b is None or a == b


def is_subtype(sub: Type, sup: Type) -> bool:
    """Return True when every value of ``sub`` is a value of ``sup``.

    Deliberately conservative: when in doubt this returns False so that the checker
    reports an error rather than silently admitting an unsound program.
    """
    if isinstance(sub, UnknownType) or isinstance(sup, UnknownType):
        # Unknown is permissive during inference; the checker separately reports any
        # Unknown that survives to the end of checking.
        return True
    if sub == sup:
        return True

    if isinstance(sub, ScalarType) and isinstance(sup, ScalarType):
        return sup.name in _scalar_ancestors(sub.name)

    if isinstance(sub, QuantityType) and isinstance(sup, QuantityType):
        return sub.dimension == sup.dimension and is_subtype(sub.base, sup.base)

    # A dimensionless quantity and a bare scalar are interconvertible.
    if isinstance(sub, QuantityType) and isinstance(sup, ScalarType):
        return sub.dimension.is_dimensionless() and is_subtype(sub.base, sup)
    if isinstance(sub, ScalarType) and isinstance(sup, QuantityType):
        return sup.dimension.is_dimensionless() and is_subtype(sub, sup.base)

    if isinstance(sub, VectorType) and isinstance(sup, VectorType):
        return is_subtype(sub.element, sup.element) and _dims_compatible(
            sub.length, sup.length
        )

    if isinstance(sub, MatrixType) and isinstance(sup, MatrixType):
        return (
            is_subtype(sub.element, sup.element)
            and _dims_compatible(sub.rows, sup.rows)
            and _dims_compatible(sub.cols, sup.cols)
        )

    if isinstance(sub, SetType) and isinstance(sup, SetType):
        return is_subtype(sub.element, sup.element)

    if isinstance(sub, RandomVariableType) and isinstance(sup, RandomVariableType):
        return is_subtype(sub.codomain, sup.codomain)

    if isinstance(sub, DistributionType) and isinstance(sup, DistributionType):
        return is_subtype(sub.support, sup.support)

    if isinstance(sub, FunctionType) and isinstance(sup, FunctionType):
        if len(sub.domain) != len(sup.domain):
            return False
        # contravariant in the domain, covariant in the codomain
        return all(
            is_subtype(sp, sb) for sb, sp in zip(sub.domain, sup.domain, strict=True)
        ) and is_subtype(sub.codomain, sup.codomain)

    return False


def join(a: Type, b: Type) -> Type:
    """Least common supertype, or ``UnknownType`` when the types are unrelated.

    Only implemented for scalars and quantities; every other pair either coincides or
    is treated as unrelated. This is enough for v0 arithmetic and is honest about the
    rest rather than guessing.
    """
    if is_subtype(a, b):
        return b
    if is_subtype(b, a):
        return a
    if isinstance(a, ScalarType) and isinstance(b, ScalarType):
        common = _scalar_ancestors(a.name) & _scalar_ancestors(b.name)
        if not common:
            return UnknownType("no common scalar supertype")
        # Pick the most specific common ancestor: the one with the largest ancestor set.
        best = max(common, key=lambda n: (len(_scalar_ancestors(n)), n))
        return ScalarType(best)
    if isinstance(a, QuantityType) and isinstance(b, QuantityType):
        if a.dimension != b.dimension:
            return UnknownType("incompatible dimensions")
        base = join(a.base, b.base)
        if not isinstance(base, ScalarType):
            return UnknownType("no common base type")
        return QuantityType(a.dimension, base)
    return UnknownType("no join")


#: Value-level membership predicates for the scalar refinement types. A *literal* has a
#: known value, so it can be checked against the refinement directly rather than through
#: its nominal type. Without this, `const p : Probability = 1` would be rejected: the
#: nominal type of the literal 1 is PositiveNatural, which is not a subtype of
#: Probability, even though the value 1 plainly is a probability.
_SCALAR_PREDICATES = {
    "Bool": lambda v: isinstance(v, bool),
    "Natural": lambda v: isinstance(v, int) and v >= 0,
    "PositiveNatural": lambda v: isinstance(v, int) and v > 0,
    "Integer": lambda v: isinstance(v, int),
    "Rational": lambda v: isinstance(v, (int, float)),
    "Real": lambda v: isinstance(v, (int, float)),
    "NonNegativeReal": lambda v: isinstance(v, (int, float)) and v >= 0,
    "PositiveReal": lambda v: isinstance(v, (int, float)) and v > 0,
    "Probability": lambda v: isinstance(v, (int, float)) and 0 <= v <= 1,
    # A bare numeric literal carries no epistemic provenance, so it inhabits all three
    # unit-interval kinds. What is refused is the *coercion of a typed symbol* from one
    # kind to another, which is where the conflation actually happens.
    "PValue": lambda v: isinstance(v, (int, float)) and 0 <= v <= 1,
    "PosteriorProbability": lambda v: isinstance(v, (int, float)) and 0 <= v <= 1,
}


def literal_inhabits(value: object, t: Type) -> bool:
    """Whether a known literal value inhabits ``t``.

    Returns False for non-scalar targets: only the scalar refinements have value-level
    predicates, and guessing about the rest would be unsound.
    """
    if isinstance(value, bool):
        return isinstance(t, ScalarType) and t.name == "Bool"
    if not isinstance(value, (int, float)):
        return False
    if isinstance(t, ScalarType):
        pred = _SCALAR_PREDICATES.get(t.name)
        return bool(pred and pred(value))
    if isinstance(t, QuantityType):
        return t.dimension.is_dimensionless() and literal_inhabits(value, t.base)
    return False


def meet(a: Type, b: Type) -> Type:
    if is_subtype(a, b):
        return a
    if is_subtype(b, a):
        return b
    return UnknownType("no meet")


def dimension_of(t: Type) -> Dimension | None:
    """The physical dimension of ``t``, or None when ``t`` is not a magnitude."""
    if isinstance(t, QuantityType):
        return t.dimension
    if isinstance(t, ScalarType) and t.name != "Bool":
        return DIMENSIONLESS
    return None


def iter_scalar_names() -> Iterable[str]:
    return SCALARS
