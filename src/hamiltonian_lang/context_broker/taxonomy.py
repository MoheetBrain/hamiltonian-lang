"""The repair error taxonomy, and the mapping from diagnostic code to error class.

Why a second classification exists
----------------------------------
``improvement.diagnostics.DiagnosticCategory`` classifies a diagnostic by *which
compiler stage emitted it* — the code prefix. That is the right axis for attributing a
defect to a subsystem, and the wrong axis for deciding **what context a repair needs**.

``HML-T471`` (wrong arity) and ``HML-T472`` (an argument fails the parameter's refinement)
share the prefix ``T`` and therefore share the category ``TYPE``. They need entirely
different context: the first needs the callee's *signature and arity rule*, the second
needs the *refinement type demanded at that argument position*. Retrieving the type
vocabulary for an arity error is retrieval that looks successful and helps nothing.

So this module classifies by **what has to be fixed**, which is the axis a broker can act
on. The two classifications are kept separate rather than merged: the compiler's category
is a fact about the compiler and must not drift because a repair policy changed.

Honesty rule
------------
:data:`ERROR_CLASS_BY_CODE` contains only codes whose emission site was read in the
compiler source. Everything else is classified by *family prefix* and the result is marked
``exact=False``, so a consumer can tell a verified classification from an inferred one. A
code whose prefix is not a known family classifies to ``None`` and the broker answers
``UNSUPPORTED_ERROR_CLASS`` — it does not guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "TAXONOMY_VERSION",
    "ErrorClass",
    "CODE_PATTERN",
    "ERROR_CLASS_BY_CODE",
    "FAMILY_ERROR_CLASS",
    "Classification",
    "classify",
    "is_well_formed_code",
]

#: Bumped whenever a code moves between classes. Recorded on every retrieval result so a
#: record written under an older taxonomy stays interpretable.
TAXONOMY_VERSION = "hml-repair-taxonomy-1.0.0"

#: The one shape a Hamiltonian Lang diagnostic code may take.
CODE_PATTERN = re.compile(r"^HML-([A-Z])(\d{3})$")


class ErrorClass(StrEnum):
    """What kind of thing is wrong, stated in terms of what a repair must change.

    Twelve members, fixed by the H3 programme specification. They are not a lattice and
    they are not ordered: a diagnostic belongs to exactly one, and a code that plausibly
    belongs to two is a sign that the code conflates two defects.
    """

    #: The input does not lex or parse. There is no AST, so no semantic context applies.
    SYNTAX = "SYNTAX"
    #: A name or callee does not resolve to anything the module knows.
    RESOLUTION = "RESOLUTION"
    #: The callee resolves and the argument *count* is wrong.
    ARITY = "ARITY"
    #: A type is unknown, absent, or the wrong kind of type altogether.
    TYPE = "TYPE"
    #: The type is the right kind but fails the refinement demanded at that position
    #: (``PositiveReal`` where ``Real`` was supplied, ``Probability`` where ``PValue``).
    REFINEMENT = "REFINEMENT"
    #: A distribution parameter role is missing, unknown, duplicated, or misnamed.
    ROLE = "ROLE"
    #: The name exists but not here: shadowing, duplicate binding, visibility.
    SCOPE = "SCOPE"
    #: Physical dimensions do not agree.
    DIMENSION = "DIMENSION"
    #: A justification, epistemic status or probability kind is used where another is
    #: required, and no coercion between them exists.
    EPISTEMIC = "EPISTEMIC"
    #: A proof obligation, assumption or discharge requirement is unmet.
    OBLIGATION = "OBLIGATION"
    #: The program compiles and denotes something other than the target object.
    SEMANTIC_EQUIVALENCE = "SEMANTIC_EQUIVALENCE"
    #: A backend cannot express the construct, or expresses it with loss.
    BACKEND = "BACKEND"


#: Verified classifications. Every entry here was established by reading the diagnostic's
#: emission site in ``src/hamiltonian_lang/``; the comment names the file where it lives.
#: Adding an entry without doing that reintroduces exactly the guessing this table avoids.
ERROR_CLASS_BY_CODE: dict[str, ErrorClass] = {
    # -- lexer / parser: no AST exists -------------------------------------------
    "HML-L101": ErrorClass.SYNTAX,
    "HML-L102": ErrorClass.SYNTAX,
    "HML-L103": ErrorClass.SYNTAX,
    "HML-P201": ErrorClass.SYNTAX,
    "HML-P203": ErrorClass.SYNTAX,
    "HML-P204": ErrorClass.SYNTAX,
    "HML-P205": ErrorClass.SYNTAX,
    "HML-P207": ErrorClass.SYNTAX,
    "HML-P208": ErrorClass.SYNTAX,
    "HML-P220": ErrorClass.SYNTAX,
    "HML-P231": ErrorClass.SYNTAX,
    "HML-P240": ErrorClass.SYNTAX,
    "HML-P241": ErrorClass.SYNTAX,
    # `Foo[...]` where Foo is not a type constructor is a *vocabulary* defect that the
    # parser happens to catch; the repair edits a type name, not the punctuation.
    "HML-P221": ErrorClass.TYPE,
    "HML-P223": ErrorClass.TYPE,
    "HML-P225": ErrorClass.DIMENSION,
    "HML-P226": ErrorClass.DIMENSION,
    "HML-P227": ErrorClass.DIMENSION,
    # Distribution argument shape: the repair edits role labels.
    "HML-P232": ErrorClass.ROLE,
    "HML-P234": ErrorClass.ROLE,
    "HML-P235": ErrorClass.ROLE,
    # -- resolution and scope -----------------------------------------------------
    "HML-N301": ErrorClass.RESOLUTION,  # `x` is not bound
    "HML-N302": ErrorClass.SCOPE,  # shadows an outer binding
    "HML-N303": ErrorClass.SCOPE,  # already declared in this scope
    "HML-N304": ErrorClass.SCOPE,  # concept declared twice
    "HML-N305": ErrorClass.RESOLUTION,  # extends unknown concept
    "HML-N306": ErrorClass.RESOLUTION,  # not a known function
    "HML-N307": ErrorClass.SCOPE,  # name collides with a distribution family
    # -- types --------------------------------------------------------------------
    "HML-T401": ErrorClass.TYPE,  # has no type
    "HML-T402": ErrorClass.REFINEMENT,  # value does not inhabit its declared type
    "HML-T403": ErrorClass.REFINEMENT,  # body does not inhabit the declared result type
    "HML-T404": ErrorClass.TYPE,  # requires a proposition
    "HML-T405": ErrorClass.TYPE,  # objective must be a real-valued magnitude
    "HML-T410": ErrorClass.TYPE,  # a Distribution cannot itself be given a law
    "HML-T411": ErrorClass.REFINEMENT,  # support does not inhabit the declared type
    "HML-T412": ErrorClass.ROLE,  # unknown distribution family
    "HML-T413": ErrorClass.REFINEMENT,  # role argument fails the role's type
    "HML-T414": ErrorClass.ROLE,  # missing required role(s)
    "HML-T415": ErrorClass.ROLE,  # named misparameterisation (variance vs scale)
    "HML-T416": ErrorClass.ROLE,  # unknown role
    "HML-T417": ErrorClass.ROLE,  # cross-role constraint (lower < upper)
    "HML-T420": ErrorClass.TYPE,
    "HML-T421": ErrorClass.TYPE,
    "HML-T422": ErrorClass.TYPE,
    "HML-T423": ErrorClass.TYPE,
    "HML-T424": ErrorClass.ARITY,  # a vector takes exactly one index
    "HML-T425": ErrorClass.TYPE,
    "HML-T426": ErrorClass.ARITY,  # builtin takes 1 argument, n given
    "HML-T427": ErrorClass.TYPE,
    "HML-T428": ErrorClass.TYPE,
    "HML-T429": ErrorClass.TYPE,
    "HML-T430": ErrorClass.TYPE,
    "HML-T431": ErrorClass.TYPE,
    "HML-T432": ErrorClass.DIMENSION,
    "HML-T433": ErrorClass.DIMENSION,
    "HML-T434": ErrorClass.DIMENSION,
    "HML-T435": ErrorClass.TYPE,
    "HML-T436": ErrorClass.TYPE,
    "HML-T440": ErrorClass.TYPE,  # unknown type name
    "HML-T450": ErrorClass.TYPE,
    "HML-T460": ErrorClass.EPISTEMIC,
    "HML-T470": ErrorClass.TYPE,  # not callable
    "HML-T471": ErrorClass.ARITY,  # wrong number of arguments
    "HML-T472": ErrorClass.REFINEMENT,  # argument fails the parameter's refinement
    "HML-T473": ErrorClass.REFINEMENT,  # concept member body vs declared type
    # -- dimensions ---------------------------------------------------------------
    "HML-D501": ErrorClass.DIMENSION,
    "HML-D502": ErrorClass.DIMENSION,
    "HML-D503": ErrorClass.DIMENSION,
    "HML-D504": ErrorClass.DIMENSION,
    "HML-D505": ErrorClass.DIMENSION,
    # -- semantic / structural ----------------------------------------------------
    "HML-S601": ErrorClass.SEMANTIC_EQUIVALENCE,  # target already has a law
    "HML-S602": ErrorClass.SEMANTIC_EQUIVALENCE,  # circular concept hierarchy
    "HML-S603": ErrorClass.OBLIGATION,  # concept declares no invariant and no example
    "HML-S604": ErrorClass.SEMANTIC_EQUIVALENCE,  # cannot infer: no law
    "HML-S605": ErrorClass.ARITY,  # transform takes no argument
    "HML-S606": ErrorClass.SEMANTIC_EQUIVALENCE,  # circular definition
    "HML-S607": ErrorClass.SEMANTIC_EQUIVALENCE,
}

#: Fallback by code family, used only when the exact code is absent above. The result is
#: marked ``exact=False`` and a consumer may treat it as weaker evidence.
FAMILY_ERROR_CLASS: dict[str, ErrorClass] = {
    "L": ErrorClass.SYNTAX,
    "P": ErrorClass.SYNTAX,
    "N": ErrorClass.RESOLUTION,
    "T": ErrorClass.TYPE,
    "D": ErrorClass.DIMENSION,
    "S": ErrorClass.SEMANTIC_EQUIVALENCE,
    "B": ErrorClass.BACKEND,
    "E": ErrorClass.EPISTEMIC,
    "G": ErrorClass.OBLIGATION,
    "X": ErrorClass.SEMANTIC_EQUIVALENCE,
}


@dataclass(frozen=True)
class Classification:
    """The class of a diagnostic code, and how confidently it was determined."""

    code: str
    error_class: ErrorClass | None
    #: True when the code appears in :data:`ERROR_CLASS_BY_CODE` — its emission site was
    #: read. False when the class was inferred from the family prefix alone.
    exact: bool
    #: True when the code matches :data:`CODE_PATTERN`. A malformed code is a query fault,
    #: not an unsupported class, and the broker answers differently for the two.
    well_formed: bool

    @property
    def supported(self) -> bool:
        return self.error_class is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "error_class": None if self.error_class is None else str(self.error_class),
            "exact": self.exact,
            "well_formed": self.well_formed,
            "taxonomy_version": TAXONOMY_VERSION,
        }


def is_well_formed_code(code: str) -> bool:
    return bool(CODE_PATTERN.match(code))


def classify(code: str) -> Classification:
    """Classify one diagnostic code. Never raises, never guesses past the family table."""
    match = CODE_PATTERN.match(code)
    if match is None:
        return Classification(code, None, exact=False, well_formed=False)
    exact = ERROR_CLASS_BY_CODE.get(code)
    if exact is not None:
        return Classification(code, exact, exact=True, well_formed=True)
    family = FAMILY_ERROR_CLASS.get(match.group(1))
    return Classification(code, family, exact=False, well_formed=True)
