"""The v0 distribution registry.

Each family declares its parameter **roles** with the type each role demands, and the
type of its support. Roles are mandatory and positional arguments are a parse error
(D-003), so `Normal(scale := s)` and `Normal(variance := s)` can never be confused —
the second is rejected with a diagnostic that names the confusion explicitly.

``MISPARAMETERISATIONS`` encodes role names that are *wrong but common*, so that the
diagnostic names the confusion instead of reporting a generic unknown argument.

No claim is made here about what that is worth. Whether naming the confusion improves
anything an AI system does is hypothesis H5/H3 in ``docs/research/BENCHMARK_PROTOCOL.md``
and has not been measured. (An earlier version of this docstring called it "the clearest
single demonstration of the project thesis" — a claim about evidence, made in a file
containing none. Withdrawn.)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ..types import (
    DistributionType,
    ScalarType,
    Type,
    VectorType,
)

__all__ = ["DistributionSpec", "DISTRIBUTIONS", "MISPARAMETERISATIONS", "lookup"]

REAL = ScalarType("Real")
POS = ScalarType("PositiveReal")
NONNEG = ScalarType("NonNegativeReal")
PROB = ScalarType("Probability")
NAT = ScalarType("Natural")
INT = ScalarType("Integer")
BOOL = ScalarType("Bool")


@dataclass(frozen=True)
class DistributionSpec:
    name: str
    roles: dict[str, Type]
    support: Type
    optional_roles: frozenset[str] = frozenset()
    note: str = ""
    #: computes the support from the resolved argument types, when it depends on them
    support_from_args: Callable[[dict[str, Type]], Type] | None = field(
        default=None, compare=False
    )
    #: Relations that must hold *between* roles: (left, operator, right, description).
    #: Checking each role independently is not enough — `Uniform(lower := 5, upper := 1)`
    #: has both roles correctly typed and denotes a law over the empty set.
    #: (Red-team finding 1.5.)
    cross_constraints: tuple[tuple[str, str, str, str], ...] = ()

    def required(self) -> set[str]:
        return set(self.roles) - set(self.optional_roles)

    def distribution_type(self, arg_types: dict[str, Type] | None = None) -> DistributionType:
        if self.support_from_args is not None and arg_types is not None:
            return DistributionType(self.support_from_args(arg_types))
        return DistributionType(self.support)


def _normal_vector_support(args: dict[str, Type]) -> Type:
    loc = args.get("location")
    if isinstance(loc, VectorType):
        return VectorType(REAL, loc.length)
    return VectorType(REAL, None)


DISTRIBUTIONS: dict[str, DistributionSpec] = {
    "Normal": DistributionSpec(
        "Normal",
        {"location": REAL, "scale": POS},
        REAL,
        note="scale is the standard deviation, not the variance",
    ),
    "HalfNormal": DistributionSpec("HalfNormal", {"scale": POS}, POS),
    "LogNormal": DistributionSpec("LogNormal", {"location": REAL, "scale": POS}, POS),
    "StudentT": DistributionSpec(
        "StudentT", {"degrees_of_freedom": POS, "location": REAL, "scale": POS}, REAL
    ),
    "Cauchy": DistributionSpec("Cauchy", {"location": REAL, "scale": POS}, REAL),
    "Uniform": DistributionSpec(
        "Uniform",
        {"lower": REAL, "upper": REAL},
        REAL,
        cross_constraints=(("lower", "<", "upper", "the support must be non-empty"),),
    ),
    "Beta": DistributionSpec(
        "Beta",
        {"alpha": POS, "beta": POS},
        PROB,
        note="the support of Beta is the unit interval, hence Probability",
    ),
    "Bernoulli": DistributionSpec("Bernoulli", {"prob": PROB}, BOOL),
    "Binomial": DistributionSpec(
        "Binomial",
        {"trials": NAT, "prob": PROB},
        NAT,
        note="trials is a count, prob is a success probability in [0, 1]",
    ),
    "Poisson": DistributionSpec("Poisson", {"rate": POS}, NAT),
    "Exponential": DistributionSpec(
        "Exponential",
        {"rate": POS},
        POS,
        note="parameterised by rate, not by mean; rate = 1 / mean",
    ),
    "Gamma": DistributionSpec("Gamma", {"shape": POS, "rate": POS}, POS),
    "InverseGamma": DistributionSpec("InverseGamma", {"shape": POS, "scale": POS}, POS),
    "Dirichlet": DistributionSpec(
        "Dirichlet", {"concentration": VectorType(POS, None)}, VectorType(PROB, None)
    ),
    "Categorical": DistributionSpec("Categorical", {"probs": VectorType(PROB, None)}, NAT),
    "NormalVector": DistributionSpec(
        "NormalVector",
        {"location": VectorType(REAL, None), "scale": POS},
        VectorType(REAL, None),
        note="an i.i.d. vector of normals with a shared scale",
        support_from_args=_normal_vector_support,
    ),
}


#: role name -> (offending family or None for any, explanation, canonical role)
MISPARAMETERISATIONS: dict[str, tuple[str | None, str, str]] = {
    "variance": (
        "Normal",
        "Normal is parameterised by its scale (standard deviation) in Hamiltonian Lang. "
        "Passing a variance here is the single most common cross-library error "
        "(R and NumPy take sd; MATLAB and some texts take variance).",
        "scale",
    ),
    "sd": ("Normal", "the canonical role name is 'scale'.", "scale"),
    "stddev": ("Normal", "the canonical role name is 'scale'.", "scale"),
    "sigma": ("Normal", "'sigma' names a symbol, not a role.", "scale"),
    "mean": (
        None,
        "'mean' is a derived property, not a parameter role. The location parameter "
        "coincides with the mean only for some families.",
        "location",
    ),
    "mu": (None, "'mu' names a symbol, not a role.", "location"),
    "loc": (None, "the canonical role name is 'location'.", "location"),
    "n": ("Binomial", "the canonical role name is 'trials'.", "trials"),
    "p": ("Binomial", "the canonical role name is 'prob'.", "prob"),
    "lambda": (
        "Exponential",
        "'lambda' is ambiguous between rate and mean across libraries.",
        "rate",
    ),
    "scale_": (None, "typo", "scale"),
    "a": ("Beta", "the canonical role name is 'alpha'.", "alpha"),
    "b": ("Beta", "the canonical role name is 'beta'.", "beta"),
}


def lookup(name: str) -> DistributionSpec | None:
    return DISTRIBUTIONS.get(name)
