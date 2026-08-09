"""The theorem-library contract: what a domain fact is, and how it becomes evidence.

A theorem is not an inference rule
----------------------------------
An **inference rule** is a primitive universal reasoning operation — modus ponens,
universal introduction. It is part of the trusted kernel because *every* piece of
reasoning uses it, and there are about fifteen of them for all of mathematics.

A **theorem** is a mathematical proposition about a particular domain — ``x + 0 = x``,
``P(A ∩ B) = P(A)·P(B|A)``. There are unboundedly many, they are domain knowledge, and
putting them in ``kernel.RULES`` would grow the trusted computing base once per fact
anybody happens to need. Gold-10 needs three of them; Gold-100 would need dozens.

So: **nothing in this package is a kernel rule.** A theorem is a *record* that elaborates,
through the existing certificate boundary, into ordinary checked evidence sitting in the
ordinary evidence DAG. `forall_intro` and `forall_elim` remain the generic logical
operations; a theorem supplies only the domain fact they operate on.

What the boundary actually checks
---------------------------------
When ``library_theorem_v1`` validates an application it re-derives, from the theorem
record and the author's substitution:

* that the theorem id and version exist in the **static** registry;
* that every variable is substituted, none spuriously, and each substitution's resolved
  type inhabits the variable's declared domain;
* that the conclusion the theorem licenses under that substitution is canonically
  identical to the proposition the author claimed;
* that every premise the theorem requires is among the declared dependencies.

Side conditions are handled separately and more strictly: they become **ordinary
``ReasoningObligation``s** discharged against Γ by the existing machinery. There is no
second domain-condition system, and an undischarged mandatory side condition means the
certificate does not validate.

What is assumed, stated plainly
-------------------------------
:class:`VerificationKind` is the honest part. HML has no induction and no measure theory,
so ``add_zero`` and ``conditional_product`` are **not derived here** — they are asserted by
the library. Calling that "verified" because it lives in a shipped Python file would be
exactly the dishonesty this project exists to avoid.

They are therefore labelled ``LIBRARY_AXIOM``, every axiom carries a written justification,
:func:`axioms` enumerates them so an auditor can read the complete list of what is being
assumed, and a test requires the justification to be non-empty. The certificate records the
verification kind in its detail. What a certificate proves is "this instantiation of that
named axiom, correctly typed, with its side conditions discharged" — not the axiom itself.

``REPLAYED`` is the stronger kind: the checker re-derives the result itself and trusts no
proposal. Calculus uses it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from ..ast.nodes import Expr
from ..types import ScalarType, Type, is_subtype

__all__ = [
    "VerificationKind",
    "TheoremVariable",
    "SideCondition",
    "LibraryTheorem",
    "THEOREMS",
    "theorem_ids",
    "axioms",
    "instantiate",
    "InstantiationError",
]


class VerificationKind(StrEnum):
    """How much of a theorem HML itself establishes. Not decoration -- audit surface.

    ``LIBRARY_AXIOM``
        Asserted by the library, **not** derived in HML. The domain fact is taken on
        trust; what the certificate checks is the instantiation. Every one carries a
        justification and appears in :func:`axioms`.

    ``DEFINITIONAL``
        True by the definition of a construct HML already has, so accepting it adds
        nothing that was not already committed to by the construct's semantics.

    ``REPLAYED``
        The checker re-derives the result from primitive rules and compares. Nothing is
        taken from the proposal but the proposal itself.
    """

    LIBRARY_AXIOM = "LIBRARY_AXIOM"
    DEFINITIONAL = "DEFINITIONAL"
    REPLAYED = "REPLAYED"


#: Kinds whose truth rests on an assertion rather than an HML-side derivation. Enumerated
#: so the trusted computing base can be *listed* rather than described.
ASSUMED_KINDS = frozenset({VerificationKind.LIBRARY_AXIOM, VerificationKind.DEFINITIONAL})


class InstantiationError(Exception):
    """A theorem application was refused. Carries the reason for the diagnostic."""


@dataclass(frozen=True)
class TheoremVariable:
    """One typed variable of a theorem schema.

    ``domains`` lists the types the variable may range over. A substitution is admitted
    only when its **resolved** type is a subtype of one of them, using the language's own
    ``is_subtype`` -- not a private notion of compatibility.

    ``kind`` separates value variables from event variables. Probability theorems quantify
    over *events*, which in HML are propositions over random variables and are a distinct
    type; conflating the two would let ``P(3.0)`` through.
    """

    name: str
    #: Scalar type names, e.g. ``("Real",)``. Empty means "any type", used only for
    #: event variables, whose discipline is `kind` rather than the scalar lattice.
    domains: tuple[str, ...] = ()
    kind: str = "value"  # value | event

    def admits(self, t: Type | None) -> bool:
        if self.kind == "event":
            from ..types import EventType

            return isinstance(t, EventType)
        if t is None:
            return False
        return any(is_subtype(t, ScalarType(name=d)) for d in self.domains)

    def describe(self) -> str:
        if self.kind == "event":
            return f"{self.name} : Event"
        return f"{self.name} : {' | '.join(self.domains)}"


@dataclass(frozen=True)
class SideCondition:
    """A condition the theorem needs that HML must establish separately.

    Built from the substitution, then handed to the **existing** obligation machinery:
    it becomes a ``ReasoningObligation``, is discharged against Γ by
    ``RefinementEnv.entails``, and an undischarged mandatory one blocks the certificate.

    This is why ``conditional_product`` cannot silently totalise conditional probability
    at probability zero: ``P(A) > 0`` is generated here and nothing else can satisfy it.
    """

    build: Callable[[Mapping[str, Expr]], Expr]
    reason: str
    mandatory: bool = True


@dataclass(frozen=True)
class LibraryTheorem:
    """One domain fact, in a form the certificate boundary can check an application of."""

    id: str
    version: int
    library: str
    variables: tuple[TheoremVariable, ...]
    #: The proposition this theorem licenses, built from the substitution.
    conclusion: Callable[[Mapping[str, Expr]], Expr]
    #: Human-readable statement. Shown in diagnostics; never enters identity.
    statement: str
    verification_kind: VerificationKind
    #: Why this may be assumed, when it is assumed. Required non-empty for assumed kinds.
    justification: str
    #: Propositions that must already be established and cited as dependencies.
    premises: Callable[[Mapping[str, Expr]], tuple[Expr, ...]] = lambda s: ()
    side_conditions: tuple[SideCondition, ...] = ()
    provenance: str = ""

    @property
    def key(self) -> str:
        """Registry key. The version is part of it, so changed semantics is a changed key."""
        return f"{self.id}_v{self.version}"

    def variable(self, name: str) -> TheoremVariable | None:
        for v in self.variables:
            if v.name == name:
                return v
        return None


#: The static theorem registry. Populated at import by the library modules. There is **no
#: registration path reachable from HML source** -- a module being checked can name a
#: theorem and cannot supply one, exactly as it can name a checker and cannot supply one.
THEOREMS: dict[str, LibraryTheorem] = {}


def _register(theorem: LibraryTheorem) -> LibraryTheorem:
    """Package-private. Not exported; not reachable from source or library data."""
    if theorem.id in THEOREMS:
        raise RuntimeError(f"theorem {theorem.id!r} is already registered")
    if theorem.verification_kind in ASSUMED_KINDS and not theorem.justification.strip():
        raise RuntimeError(
            f"theorem {theorem.id!r} is assumed but carries no justification; an "
            f"unjustified assumption is an unaudited one"
        )
    THEOREMS[theorem.id] = theorem
    return theorem


def theorem_ids() -> tuple[str, ...]:
    return tuple(sorted(THEOREMS))


def axioms() -> tuple[LibraryTheorem, ...]:
    """Every theorem whose truth is asserted rather than derived here.

    The point of this function is that the assumed part of the trusted computing base can
    be *printed*. A TCB you can only describe is one nobody checks.
    """
    return tuple(
        THEOREMS[k] for k in theorem_ids() if THEOREMS[k].verification_kind in ASSUMED_KINDS
    )


@dataclass(frozen=True)
class Instantiation:
    """A theorem applied to a substitution, with everything the boundary must check."""

    theorem: LibraryTheorem
    substitution: Mapping[str, Expr]
    conclusion: Expr
    premises: tuple[Expr, ...]
    #: (proposition, reason, mandatory) -- the shape ``check.py`` already consumes.
    side_conditions: tuple[tuple[Expr, str, bool], ...] = ()


def instantiate(
    theorem: LibraryTheorem, substitution: Mapping[str, Expr]
) -> Instantiation:
    """Bind the theorem's variables and build what it licenses.

    Raises :class:`InstantiationError` on anything wrong: a missing variable, a spurious
    one, or a substitution whose resolved type does not inhabit the declared domain.
    Refusing a substitution HML cannot type is the whole point -- a theorem about reals
    applied to a random variable would otherwise produce a well-formed lie.
    """
    missing = [v.name for v in theorem.variables if v.name not in substitution]
    if missing:
        raise InstantiationError(
            f"theorem {theorem.id!r} needs {', '.join(missing)}; "
            f"it takes {', '.join(v.describe() for v in theorem.variables)}"
        )
    extra = [k for k in substitution if theorem.variable(k) is None]
    if extra:
        raise InstantiationError(
            f"theorem {theorem.id!r} has no variable "
            f"{', '.join(repr(e) for e in sorted(extra))}"
        )
    for var in theorem.variables:
        value = substitution[var.name]
        resolved: Type | None = getattr(value, "type_", None)
        if not var.admits(resolved):
            found = resolved.render() if resolved is not None else "unknown"
            raise InstantiationError(
                f"{var.name} must be {var.describe().split(' : ', 1)[1]}, but the "
                f"substitution has type {found}"
            )
    return Instantiation(
        theorem=theorem,
        substitution=dict(substitution),
        conclusion=theorem.conclusion(substitution),
        premises=tuple(theorem.premises(substitution)),
        side_conditions=tuple(
            (sc.build(substitution), sc.reason, sc.mandatory)
            for sc in theorem.side_conditions
        ),
    )


def describe(ids: Sequence[str] | None = None) -> str:
    """Human-readable inventory, for diagnostics and for the audit surface."""
    out = []
    for k in ids or theorem_ids():
        t = THEOREMS[k]
        out.append(f"{t.id} (v{t.version}, {t.library}, {t.verification_kind}): {t.statement}")
    return "\n".join(out)


