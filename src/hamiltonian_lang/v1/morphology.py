"""V1 semantic morphology — HML-V1-CONCEPT-001 Phase 4.

**Derivation is by declared typed relation. It is never by string concatenation.**

``docs/design/V1_KERNEL.md`` §5 fixes this as a hard design constraint, and the reason is
that productive morphology over mathematical vocabulary manufactures plausible nonsense.
``vary -> variance`` is not a safe rule. ``estimate -> estimator`` is not a safe rule.
A suffix engine would happily produce ``Cauchy.mean`` and ``Dirac.logdensity``, both of
which are well formed as strings and neither of which denotes anything.

So this module has no suffix table, no pattern engine, and no fallback. ``Normal.density``
resolves because someone declared, for ``Normal``, a density with a type and a stated
semantics, with respect to a declared base measure. For a concept with no such declaration
the same request **raises**. There is no code path that fabricates one, and adding a
concept to the registry gives it no roles at all.

Two things a reader should be able to check by reading:

1. :meth:`Morphology.resolve` consults ``self._declarations`` and nothing else. It never
   inspects, splits or extends a concept's name.
2. The estimation family below gives ``procedure``, ``estimator``, ``estimate`` and
   ``estimand`` four distinct roles with no substitution between any pair, so
   *"the estimate is unbiased"* raises :class:`RoleTypeError`: unbiasedness is a property
   of the estimator, not of a number.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from hamiltonian_lang.v1.registry import (
    ClaimStatus,
    ConceptRegistry,
    UnknownConceptError,
)

__all__ = [
    "MorphologyError",
    "UnknownRoleError",
    "UndeclaredRoleError",
    "DuplicateDeclarationError",
    "MissingPrerequisiteError",
    "RoleTypeError",
    "UnknownPropertyError",
    "Role",
    "ROLE_INTENT",
    "ROLE_PREREQUISITES",
    "RoleDeclaration",
    "ConceptFamily",
    "Morphology",
    "EstimationRole",
    "ESTIMATION_TYPES",
    "ESTIMATION_RELATIONS",
    "ESTIMATION_INVARIANTS",
    "PROPERTY_CARRIERS",
    "may_substitute",
    "check_substitution",
    "carriers_of",
    "attribute_property",
    "STRING_DERIVATION_IS_PROHIBITED",
    "UnknownConceptError",
]

#: Stated as a constant so that a grep for it lands on the rule rather than on a comment.
#: Nothing in this module may consult it to enable a derivation; it is documentation with
#: a test attached.
STRING_DERIVATION_IS_PROHIBITED = True


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MorphologyError(Exception):
    """Base class for every morphology refusal."""


class UnknownRoleError(MorphologyError):
    """The requested role is not one of the declared family roles."""


class UndeclaredRoleError(MorphologyError):
    """The role exists, but has not been declared for this concept.

    This is the error that keeps the module honest. A morphology that answered this
    request by pattern would be producing an authoritative-looking answer about a concept
    it knows nothing about.
    """


class DuplicateDeclarationError(MorphologyError):
    """A role was declared twice for one concept."""


class MissingPrerequisiteError(MorphologyError):
    """A role was declared without the role it is defined in terms of."""


class RoleTypeError(MorphologyError, TypeError):
    """A value in one role was used where another role is required.

    Deliberately also a :class:`TypeError`: "the estimate is unbiased" is a type error, not
    a lint warning.
    """


class UnknownPropertyError(MorphologyError):
    """A property was attributed that no role is declared to carry."""


# ---------------------------------------------------------------------------
# Family roles
# ---------------------------------------------------------------------------


class Role(StrEnum):
    """The closed set of family roles a concept may declare.

    Membership in this enum makes a role *nameable*. It does not make it *available*: a
    concept has a role only once that role is declared for it, with a type and a semantics.
    """

    LAW = "law"
    DENSITY = "density"
    LOGDENSITY = "logdensity"
    SAMPLE = "sample"
    PARAMETER = "parameter"
    PROPERTY = "property"
    PREDICATE = "predicate"
    TRANSFORM = "transform"
    INVERSE = "inverse"
    MEASURE = "measure"
    ESTIMATOR = "estimator"
    ESTIMAND = "estimand"
    PROOF = "proof"
    COUNTEREXAMPLE = "counterexample"


#: What each role means. A role whose meaning is not stated here cannot be declared,
#: because a role with no semantics is a suffix.
ROLE_INTENT: dict[Role, str] = {
    Role.LAW: "the distribution or governing law of the object",
    Role.DENSITY: (
        "a Radon-Nikodym derivative with respect to a declared base measure; a density "
        "without a dominating measure is not well defined"
    ),
    Role.LOGDENSITY: (
        "the logarithm of a declared density; it exists only where the density does"
    ),
    Role.SAMPLE: "a draw, or the type of a draw, from the object's law",
    Role.PARAMETER: "a parameter the object is indexed by, in a named role",
    Role.PROPERTY: "a named attribute the object carries",
    Role.PREDICATE: "a Bool-valued function of the object, as distinct from an attribute",
    Role.TRANSFORM: "a declared map out of the object",
    Role.INVERSE: "the inverse of a declared transform; it exists only where that does",
    Role.MEASURE: "the base measure the object is defined with respect to",
    Role.ESTIMATOR: "a function from samples to the parameter space",
    Role.ESTIMAND: "the quantity an estimator targets; it does not depend on the sample",
    Role.PROOF: "a proof object establishing a stated claim about the concept",
    Role.COUNTEREXAMPLE: "a witness refuting a nearby claim about the concept",
}

#: Roles defined in terms of another role. Declaring the dependent role without its
#: prerequisite is refused, because the dependent role would have nothing to refer to.
#: This is the mechanism by which derivation is *relational*: ``.logdensity`` is available
#: because a density is declared, not because "log" can be prefixed to a word.
ROLE_PREREQUISITES: dict[Role, frozenset[Role]] = {
    Role.DENSITY: frozenset({Role.MEASURE}),
    Role.LOGDENSITY: frozenset({Role.DENSITY}),
    Role.INVERSE: frozenset({Role.TRANSFORM}),
}


@dataclass(frozen=True)
class RoleDeclaration:
    """One role, declared for one concept, with its type and its semantics.

    ``semantics`` is mandatory and non-empty. A declaration with a type and no stated
    meaning is exactly the failure mode this module exists to prevent: it would let
    ``AnyConcept.density`` type-check while denoting nothing.
    """

    concept_id: str
    role: Role
    type_signature: str
    semantics: str
    realised_by: str | None = None
    status: ClaimStatus = ClaimStatus.CONJECTURED
    conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.type_signature.strip():
            raise MorphologyError(
                f"{self.concept_id}.{self.role.value}: a role declaration needs a type"
            )
        if not self.semantics.strip():
            raise MorphologyError(
                f"{self.concept_id}.{self.role.value}: a role declaration needs stated "
                f"semantics; a role with a type but no meaning is a suffix"
            )

    @property
    def path(self) -> str:
        return f"{self.concept_id}.{self.role.value}"

    def render(self) -> str:
        conditions = f" [under {', '.join(self.conditions)}]" if self.conditions else ""
        return f"{self.path} : {self.type_signature} ({self.status.value}){conditions}"


@dataclass(frozen=True)
class ConceptFamily:
    """The roles declared for one concept — its family, as a read-only view.

    A family is a *declared set of independently typed members*, never a generated one, so
    two concepts of the same mathematical kind may perfectly well have different families.
    """

    concept_id: str
    declarations: Mapping[Role, RoleDeclaration]

    def __contains__(self, role: object) -> bool:
        return role in self.declarations

    @property
    def roles(self) -> tuple[Role, ...]:
        return tuple(sorted(self.declarations, key=lambda r: r.value))

    def get(self, role: Role) -> RoleDeclaration:
        declaration = self.declarations.get(role)
        if declaration is None:
            raise UndeclaredRoleError(_undeclared_message(self.concept_id, role, self.roles))
        return declaration

    def render(self) -> str:
        lines = [f"family {self.concept_id}"]
        lines += [f"    member {self.declarations[r].render()}" for r in self.roles]
        return "\n".join(lines)


def _undeclared_message(
    concept_id: str, role: Role, declared: Iterable[Role]
) -> str:
    available = ", ".join(r.value for r in declared) or "none"
    return (
        f"{concept_id}.{role.value} is not declared. Roles are not derived by string rule: "
        f"{concept_id!r} has a {role.value} only if one has been declared for it, with a "
        f"type and a semantics. Declared roles for {concept_id}: {available}."
    )


def _coerce_role(role: Role | str) -> Role:
    if isinstance(role, Role):
        return role
    try:
        return Role(role)
    except ValueError as exc:
        known = ", ".join(r.value for r in Role)
        raise UnknownRoleError(
            f"{role!r} is not a family role. The set of roles is closed: {known}"
        ) from exc


# ---------------------------------------------------------------------------
# The morphology
# ---------------------------------------------------------------------------


class Morphology:
    """Declared role resolution over a concept registry.

    Attach a :class:`~hamiltonian_lang.v1.registry.ConceptRegistry` and resolution
    additionally enforces the citation rule: a role may be resolved only on a concept that
    is ``admitted``, because resolving a role on a concept that is still ``proposed`` would
    be citing it.
    """

    def __init__(self, registry: ConceptRegistry | None = None) -> None:
        self.registry = registry
        self._declarations: dict[str, dict[Role, RoleDeclaration]] = {}

    # -- declaration ------------------------------------------------------
    def declare(self, declaration: RoleDeclaration) -> RoleDeclaration:
        """Record one role for one concept, checking its prerequisites.

        Refuses to declare a role for a concept the attached registry has never heard of:
        a role hanging off a name that denotes nothing is precisely the fabrication this
        module forbids.
        """
        concept_id = declaration.concept_id
        if self.registry is not None and self.registry.find(concept_id) is None:
            raise UnknownConceptError(
                f"cannot declare {declaration.path}: {concept_id!r} is not in the registry"
            )

        family = self._declarations.setdefault(concept_id, {})
        if declaration.role in family:
            raise DuplicateDeclarationError(
                f"{declaration.path} is already declared as "
                f"{family[declaration.role].type_signature!r}"
            )

        missing = [
            required
            for required in ROLE_PREREQUISITES.get(declaration.role, frozenset())
            if required not in family
        ]
        if missing:
            names = ", ".join(sorted(r.value for r in missing))
            raise MissingPrerequisiteError(
                f"{declaration.path} cannot be declared before {names}: "
                f"{ROLE_INTENT[declaration.role]}"
            )

        if declaration.realised_by is not None and self.registry is not None:
            target = self.registry.find(declaration.realised_by)
            if target is None:
                raise UnknownConceptError(
                    f"{declaration.path} is realised by {declaration.realised_by!r}, "
                    f"which is not registered"
                )
            if not target.may_be_cited():
                raise UnknownConceptError(
                    f"{declaration.path} cites {declaration.realised_by!r}, whose status "
                    f"is {target.admission_status.value}; a concept may only be cited once "
                    f"it is admitted"
                )

        family[declaration.role] = declaration
        return declaration

    def declare_role(
        self,
        concept_id: str,
        role: Role | str,
        type_signature: str,
        semantics: str,
        *,
        realised_by: str | None = None,
        status: ClaimStatus = ClaimStatus.CONJECTURED,
        conditions: tuple[str, ...] = (),
    ) -> RoleDeclaration:
        """Convenience wrapper over :meth:`declare`."""
        return self.declare(
            RoleDeclaration(
                concept_id=concept_id,
                role=_coerce_role(role),
                type_signature=type_signature,
                semantics=semantics,
                realised_by=realised_by,
                status=status,
                conditions=conditions,
            )
        )

    # -- resolution -------------------------------------------------------
    def family(self, concept_id: str) -> ConceptFamily:
        return ConceptFamily(
            concept_id=concept_id,
            declarations=dict(self._declarations.get(concept_id, {})),
        )

    def roles_of(self, concept_id: str) -> tuple[Role, ...]:
        return self.family(concept_id).roles

    def has(self, concept_id: str, role: Role | str) -> bool:
        """Whether the role is declared. Never a guess — this is a lookup."""
        try:
            resolved = _coerce_role(role)
        except UnknownRoleError:
            return False
        return resolved in self._declarations.get(concept_id, {})

    def resolve(self, concept_id: str, role: Role | str) -> RoleDeclaration:
        """Resolve one role on one concept, or raise.

        The only source consulted is the declaration table. The concept's *name* is used as
        a dictionary key and for nothing else: it is never split, extended or matched
        against a pattern.
        """
        resolved = _coerce_role(role)

        if self.registry is not None:
            concept = self.registry.find(concept_id)
            if concept is None:
                raise UnknownConceptError(
                    f"cannot resolve {concept_id}.{resolved.value}: {concept_id!r} is not "
                    f"in the registry"
                )
            if not concept.may_be_cited():
                raise UnknownConceptError(
                    f"cannot resolve {concept_id}.{resolved.value}: {concept_id!r} is "
                    f"{concept.admission_status.value}, and a concept may only be cited "
                    f"once it is admitted"
                )

        family = self._declarations.get(concept_id, {})
        declaration = family.get(resolved)
        if declaration is None:
            raise UndeclaredRoleError(
                _undeclared_message(concept_id, resolved, tuple(family))
            )
        return declaration

    def resolve_path(self, path: str) -> RoleDeclaration:
        """Resolve ``"Normal.density"``.

        ``Normal.density`` resolves iff a density has been declared for ``Normal``.
        ``SomeArbitraryConcept.density`` raises, whatever the string looks like.
        """
        parts = path.split(".")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise MorphologyError(
                f"{path!r} is not a role path; the form is <concept>.<role>"
            )
        return self.resolve(parts[0], parts[1])

    def __repr__(self) -> str:
        declared = sum(len(family) for family in self._declarations.values())
        return (
            f"Morphology(concepts={len(self._declarations)}, declarations={declared})"
        )


# ---------------------------------------------------------------------------
# The estimation family — four things ordinary prose blurs into one
# ---------------------------------------------------------------------------


class EstimationRole(StrEnum):
    """``procedure``, ``estimator``, ``estimate`` and ``estimand`` are four things.

    Collapsing them is the single most common category error in applied statistics, and it
    is what makes "the estimate is unbiased" sound like a sentence. It is not one: an
    estimate is a number obtained from one sample, and a number has no sampling behaviour
    to be unbiased about.
    """

    PROCEDURE = "procedure"
    ESTIMATOR = "estimator"
    ESTIMATE = "estimate"
    ESTIMAND = "estimand"
    SAMPLING_LAW = "sampling_law"
    STANDARD_ERROR = "standard_error"


#: The type of each member. Note that ``estimate`` and ``estimand`` carry the *same type
#: expression* and are still distinct roles: role is meaning, not type, so sharing a type
#: never licenses substitution.
ESTIMATION_TYPES: dict[EstimationRole, str] = {
    EstimationRole.PROCEDURE: "EstimationProcedure",
    EstimationRole.ESTIMATOR: "Function[Sample -> ParameterSpace]",
    EstimationRole.ESTIMATE: "ParameterSpace",
    EstimationRole.ESTIMAND: "ParameterSpace",
    EstimationRole.SAMPLING_LAW: "Distribution[ParameterSpace]",
    EstimationRole.STANDARD_ERROR: "PositiveReal",
}

#: What each member *is*, in one line, for use in error messages.
_ESTIMATION_INTENT: dict[EstimationRole, str] = {
    EstimationRole.PROCEDURE: "the algorithm, independent of any sample",
    EstimationRole.ESTIMATOR: "a function from samples to the parameter space",
    EstimationRole.ESTIMATE: "the value obtained from one particular sample",
    EstimationRole.ESTIMAND: "the true quantity being estimated; no sample enters it",
    EstimationRole.SAMPLING_LAW: "the estimator's distribution under repeated sampling",
    EstimationRole.STANDARD_ERROR: "a scale summary of the sampling law",
}

#: Declared relations between the members. These are how one member is obtained from
#: another — by a stated relation, never by rewriting a word.
ESTIMATION_RELATIONS: tuple[str, ...] = (
    "estimate = apply(estimator, to := sample)",
    "sampling_law = law_of(estimator, under := sampling_model)",
    "standard_error = scale_of(sampling_law)",
    "estimand does not depend on sample",
)

ESTIMATION_INVARIANTS: tuple[str, ...] = (
    "estimator_is_a_function_not_a_value",
    "estimate_depends_on_sample",
    "estimand_does_not_depend_on_sample",
    "procedure_is_not_its_output",
)

#: Which role can carry which property. A property attributed to a role that cannot carry
#: it is a type error, which is the mechanism the kill criterion in
#: ``docs/design/V1_KERNEL.md`` §8 names for this layer.
PROPERTY_CARRIERS: dict[str, frozenset[EstimationRole]] = {
    # properties of the sampling behaviour of a function — the estimator
    "unbiased": frozenset({EstimationRole.ESTIMATOR}),
    "biased": frozenset({EstimationRole.ESTIMATOR}),
    "consistent": frozenset({EstimationRole.ESTIMATOR}),
    "efficient": frozenset({EstimationRole.ESTIMATOR}),
    "admissible": frozenset({EstimationRole.ESTIMATOR}),
    "minimax": frozenset({EstimationRole.ESTIMATOR}),
    "asymptotically_normal": frozenset({EstimationRole.ESTIMATOR}),
    "sufficient": frozenset({EstimationRole.ESTIMATOR}),
    # properties of an algorithm — the procedure
    "terminates": frozenset({EstimationRole.PROCEDURE}),
    "deterministic": frozenset({EstimationRole.PROCEDURE}),
    "polynomial_time": frozenset({EstimationRole.PROCEDURE}),
    "numerically_stable": frozenset({EstimationRole.PROCEDURE}),
    # properties of the target quantity — the estimand
    "identifiable": frozenset({EstimationRole.ESTIMAND}),
    "estimable": frozenset({EstimationRole.ESTIMAND}),
    # properties of a number — the estimate
    "finite": frozenset({EstimationRole.ESTIMATE, EstimationRole.STANDARD_ERROR}),
    "within_tolerance": frozenset({EstimationRole.ESTIMATE}),
    # properties of a distribution — the sampling law
    "has_finite_variance": frozenset({EstimationRole.SAMPLING_LAW}),
    "absolutely_continuous": frozenset({EstimationRole.SAMPLING_LAW}),
    # properties of a positive scalar — the standard error
    "positive": frozenset({EstimationRole.STANDARD_ERROR}),
}

#: Extra explanation for the misattributions worth naming out loud.
_MISATTRIBUTION_NOTES: dict[tuple[str, EstimationRole], str] = {
    ("unbiased", EstimationRole.ESTIMATE): (
        "unbiasedness is a statement about the average of an estimator over repeated "
        "samples; a single number has no such average"
    ),
    ("unbiased", EstimationRole.PROCEDURE): (
        "a procedure is an algorithm; unbiasedness is a property of the function it "
        "defines, which is the estimator"
    ),
    ("consistent", EstimationRole.ESTIMATE): (
        "consistency is a limit along a sequence of sample sizes; one value has no limit"
    ),
    ("identifiable", EstimationRole.ESTIMATOR): (
        "identifiability is a property of the estimand under a model, not of the function "
        "used to estimate it"
    ),
}


def carriers_of(property_name: str) -> frozenset[EstimationRole]:
    """The roles that may carry ``property_name``, or raise if it is not declared."""
    carriers = PROPERTY_CARRIERS.get(property_name)
    if carriers is None:
        known = ", ".join(sorted(PROPERTY_CARRIERS))
        raise UnknownPropertyError(
            f"{property_name!r} is not a declared property of the estimation family. "
            f"Declared properties: {known}"
        )
    return carriers


def attribute_property(property_name: str, to: EstimationRole) -> None:
    """Attribute a property to a role, or raise :class:`RoleTypeError`.

    ``attribute_property("unbiased", EstimationRole.ESTIMATE)`` raises. That is the whole
    point of the family: the sentence "the estimate is unbiased" has to fail somewhere, and
    here is where.
    """
    carriers = carriers_of(property_name)
    if to in carriers:
        return
    allowed = ", ".join(sorted(role.value for role in carriers))
    note = _MISATTRIBUTION_NOTES.get((property_name, to))
    detail = f" — {note}" if note else ""
    raise RoleTypeError(
        f"{property_name!r} is not a property of the {to.value} "
        f"({_ESTIMATION_INTENT[to]}); it is a property of: {allowed}{detail}"
    )


def may_substitute(
    source: EstimationRole, target: EstimationRole
) -> tuple[bool, str]:
    """Whether a ``source`` may stand where a ``target`` is required.

    Identity only. Every distinct pair is refused, including
    ``estimate``/``estimand``, which share a type expression: a shared type is not a shared
    meaning, and V0 already refuses to let ``Distribution[T]`` stand for a ``T`` on exactly
    this reasoning.
    """
    if source is target:
        return True, ""
    return False, (
        f"a {source.value} ({_ESTIMATION_INTENT[source]}) cannot stand where a "
        f"{target.value} ({_ESTIMATION_INTENT[target]}) is required; there is no coercion "
        f"between estimation roles"
    )


def check_substitution(source: EstimationRole, target: EstimationRole) -> None:
    """Raise :class:`RoleTypeError` unless ``source`` and ``target`` are the same role."""
    allowed, reason = may_substitute(source, target)
    if not allowed:
        raise RoleTypeError(reason)
