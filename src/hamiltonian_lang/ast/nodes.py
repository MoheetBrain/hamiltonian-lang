"""Typed AST / semantic-graph node definitions for Hamiltonian Lang.

**This module is the frozen IR contract for v0.** Backends, renderers, the graph
builder, and the benchmark harness all consume these nodes. Changing a field here is a
semantic-contract change and requires a `/design-change` record in ``DECISIONS.md``.

Structure
---------
``Module`` holds an ordered list of ``Statement``. Statements carry ``Expr`` trees.
Name resolution attaches a ``SymbolId`` to every binding occurrence and every
reference, so downstream consumers never need to re-resolve names by spelling.

Invariants after a successful ``check``:

* every ``Ref`` has a non-None ``symbol_id`` that appears as some binder's id;
* every node has a non-None ``type_`` (no ``UnknownType`` survives);
* every ``Span`` is populated (diagnostics depend on it).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from ..types import Type

__all__ = [
    "Span",
    "SymbolId",
    "Node",
    "Expr",
    "Literal",
    "Ref",
    "BinOp",
    "UnaryOp",
    "Call",
    "Index",
    "DistExpr",
    "Arg",
    "Quantifier",
    "Comparison",
    "LogicalOp",
    "Statement",
    "ModuleDecl",
    "Declaration",
    "DeclKind",
    "LawStmt",
    "DefineStmt",
    "AssumeStmt",
    "RequireStmt",
    "ObjectiveStmt",
    "SolveStmt",
    "InferStmt",
    "CheckStmt",
    "ProveStmt",
    "ConceptDecl",
    "ConceptMember",
    "Module",
    # -- V2 reasoning spine ------------------------------------------------
    "ClaimId",
    "DerivationStatus",
    "GoalStatus",
    "GoalStmt",
    "DeriveStmt",
    "ProvedStmt",
    "RuleArg",
    "V2_STATEMENTS",
    "uses_v2",
]


# ---------------------------------------------------------------------------
# Source locations and symbol identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Span:
    """A half-open source range, 1-based line, 0-based column."""

    line: int = 0
    col: int = 0
    end_line: int = 0
    end_col: int = 0
    file: str = "<input>"

    def render(self) -> str:
        return f"{self.file}:{self.line}:{self.col + 1}"

    @staticmethod
    def merge(a: Span, b: Span) -> Span:
        return Span(a.line, a.col, b.end_line, b.end_col, a.file)


@dataclass(frozen=True, order=True)
class SymbolId:
    """A stable identity for a bound name, independent of its spelling.

    ``ordinal`` is assigned by the resolver in declaration order within a scope.
    ``depth`` is the binder nesting depth (0 for module-level). Together these give a
    locally-nameless canonical form: alpha-renaming changes ``name`` but never
    ``(depth, ordinal)``, which is what canonicalisation hashes.
    """

    name: str
    ordinal: int
    depth: int = 0

    def render(self) -> str:
        return f"sym:{self.name}:{self.depth}.{self.ordinal}"

    def canonical(self) -> str:
        """Spelling-independent identity used for hashing and alpha-equivalence."""
        return f"sym:#{self.depth}.{self.ordinal}"


@dataclass
class Node:
    span: Span = field(default_factory=Span, kw_only=True)
    type_: Type | None = field(default=None, kw_only=True)


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------


@dataclass
class Expr(Node):
    pass


@dataclass
class Literal(Expr):
    value: float | int | bool
    raw: str = ""


@dataclass
class Ref(Expr):
    """A reference to a bound name. ``symbol_id`` is filled by the resolver."""

    name: str
    symbol_id: SymbolId | None = None


@dataclass
class BinOp(Expr):
    op: str  # + - * / ^ @   (@ = matrix/vector product)
    left: Expr = field(default=None)  # type: ignore[assignment]
    right: Expr = field(default=None)  # type: ignore[assignment]


@dataclass
class UnaryOp(Expr):
    op: str  # - not
    operand: Expr = field(default=None)  # type: ignore[assignment]


@dataclass
class Comparison(Expr):
    op: str  # = != < <= > >=
    left: Expr = field(default=None)  # type: ignore[assignment]
    right: Expr = field(default=None)  # type: ignore[assignment]


@dataclass
class LogicalOp(Expr):
    op: str  # and or implies iff
    left: Expr = field(default=None)  # type: ignore[assignment]
    right: Expr = field(default=None)  # type: ignore[assignment]


@dataclass
class Arg:
    """A **role-labelled** argument. Positional arguments are not permitted in
    distribution expressions: the role name is the whole point (see D-003)."""

    role: str
    value: Expr
    span: Span = field(default_factory=Span)


@dataclass
class Call(Expr):
    callee: str = ""
    args: list[Expr] = field(default_factory=list)


@dataclass
class Index(Expr):
    base: Expr = field(default=None)  # type: ignore[assignment]
    indices: list[Expr] = field(default_factory=list)


@dataclass
class DistExpr(Expr):
    """A distribution *law*, e.g. ``Normal(location := mu, scale := sigma)``.

    Its type is ``Distribution[T]``, never ``T``. Arguments are keyed by role.
    """

    family: str = ""
    args: list[Arg] = field(default_factory=list)

    def arg(self, role: str) -> Expr | None:
        for a in self.args:
            if a.role == role:
                return a.value
        return None


@dataclass
class Quantifier(Expr):
    """``forall x : T . body`` / ``exists x : T . body``.

    Scope is explicit and nesting order is structural, so
    ``forall x . exists y . P`` and ``exists y . forall x . P`` are different trees
    and different canonical hashes. This is benchmark hypothesis H2.
    """

    kind: str = "forall"  # forall | exists | exists_unique
    var: str = ""
    var_type: Type | None = None
    symbol_id: SymbolId | None = None
    body: Expr = field(default=None)  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------


@dataclass
class Statement(Node):
    pass


@dataclass
class ModuleDecl(Statement):
    name: str = ""


class DeclKind:
    VAR = "var"
    PARAM = "param"
    CONST = "const"
    OBS = "obs"
    INDEX = "index"
    RANDOM = "rv"


@dataclass
class Declaration(Statement):
    """``param theta : Probability``, ``obs successes : Natural = 7`` etc."""

    kind: str = DeclKind.VAR
    name: str = ""
    declared_type: Type | None = None
    value: Expr | None = None
    symbol_id: SymbolId | None = None


@dataclass
class DefineStmt(Statement):
    """``def kinetic_energy := 0.5 * m * v^2``"""

    name: str = ""
    declared_type: Type | None = None
    body: Expr = field(default=None)  # type: ignore[assignment]
    params: list[tuple[str, Type | None]] = field(default_factory=list)
    symbol_id: SymbolId | None = None


@dataclass
class LawStmt(Statement):
    """``law successes | theta ~ Binomial(trials := n, prob := theta)``

    ``target`` is the random variable being given a law; ``given`` is the
    conditioning set. ``role`` distinguishes prior/likelihood/posterior usage without
    changing the underlying semantics.
    """

    target: str = ""
    target_symbol: SymbolId | None = None
    given: list[Ref] = field(default_factory=list)
    distribution: DistExpr | None = None
    role: str = "law"  # law | prior | likelihood


@dataclass
class AssumeStmt(Statement):
    proposition: Expr = field(default=None)  # type: ignore[assignment]
    #: Optional V2 claim label. ``None`` for every v1 module, and the canonical
    #: serializer omits the key entirely in that case, so v1 hashes are unchanged.
    label: str | None = None
    claim_id: ClaimId | None = None


@dataclass
class RequireStmt(Statement):
    """A constraint the model must satisfy. Generates a proof obligation."""

    proposition: Expr = field(default=None)  # type: ignore[assignment]
    label: str | None = None
    claim_id: ClaimId | None = None


@dataclass
class ObjectiveStmt(Statement):
    direction: str = "minimise"  # minimise | maximise
    expression: Expr = field(default=None)  # type: ignore[assignment]


@dataclass
class SolveStmt(Statement):
    targets: list[Ref] = field(default_factory=list)


@dataclass
class InferStmt(Statement):
    query: str = "posterior"  # posterior | expectation | variance | mle | map
    targets: list[Ref] = field(default_factory=list)


@dataclass
class CheckStmt(Statement):
    """``check dimension kinetic_energy`` or ``check <proposition>``."""

    check_kind: str = "proposition"  # proposition | dimension | type
    subject: Expr | None = None
    expected: str | None = None


@dataclass
class ProveStmt(Statement):
    proposition: Expr = field(default=None)  # type: ignore[assignment]
    label: str | None = None
    claim_id: ClaimId | None = None


@dataclass
class ConceptMember:
    kind: str  # parameter | transform | invariant | property | example | counterexample
    name: str
    declared_type: Type | None = None
    body: Expr | None = None
    #: (name, declared type) pairs, matching ``DefineStmt.params``. The annotation is
    #: optional because the type is usually inferable from use, but the slot exists
    #: because governing principle 1 says every object has a type. See D-015.
    params: list[tuple[str, Type | None]] = field(default_factory=list)
    span: Span = field(default_factory=Span)

    def param_names(self) -> list[str]:
        return [n for n, _ in self.params]


@dataclass
class ConceptDecl(Statement):
    """A minted concept. See ``spec/concept_schema.yaml`` for the required fields.

    A concept that declares no invariant and no example is rejected by the checker:
    "sounds plausible" is not an admissible definition (CLAUDE.md rule 4).
    """

    name: str = ""
    extends: list[str] = field(default_factory=list)
    members: list[ConceptMember] = field(default_factory=list)
    symbol_id: SymbolId | None = None

    def members_of(self, kind: str) -> list[ConceptMember]:
        return [m for m in self.members if m.kind == kind]


# ---------------------------------------------------------------------------
# V2 reasoning spine
# ---------------------------------------------------------------------------
#
# The v1 language represents mathematical *state*. These three statement forms are
# the whole of what it takes to represent a reasoning *transition*, and they are
# deliberately the smallest set that closes the audit's central finding:
#
#     goal   g : P               -- something we intend to establish
#     derive d : Q from p1,p2 by rule(...)   -- one inference, with its inputs named
#     proved g by d              -- a claim that d establishes g, which the checker adjudicates
#
# What makes this more than vocabulary is that ``status`` on a derivation is
# **computed by the checker and cannot be written in source**. There is no surface
# syntax for VERIFIED. A model can assert a derivation; it cannot assert that the
# derivation is correct. See docs/hml_v2/REASONING_MODEL.md.


@dataclass(frozen=True, order=True)
class ClaimId:
    """Identity of a labelled claim: assumption, requirement, goal, or derivation.

    Claims live in a namespace **disjoint** from values. ``d1`` names an inference,
    not a number, and writing ``d1 + 1`` is a scope error rather than a type error.
    Keeping the namespaces apart is what stops a derivation being smuggled into an
    expression, which would let provenance leak into mathematical identity.
    """

    name: str
    ordinal: int

    def render(self) -> str:
        return f"claim:{self.name}"

    def canonical(self) -> str:
        """Spelling-independent identity, mirroring :meth:`SymbolId.canonical`."""
        return f"claim:#{self.ordinal}"


class DerivationStatus:
    """The lifecycle of one inference. Assigned by the checker, never by source.

    PROPOSED  -- parsed and well-scoped; the rule has not been applied.
    CHECKED   -- the trusted kernel applied the rule to the premises and the stated
                 output is canonically identical to what the rule produces.
    VERIFIED  -- CHECKED **and** every mandatory obligation is DISCHARGED.
    REJECTED  -- the kernel applied the rule and the stated output is *not* what the
                 rule produces, or a premise is missing/ill-formed.

    VERIFIED is unreachable except through the kernel: nothing in the parser or the
    surface grammar can produce it.
    """

    PROPOSED = "PROPOSED"
    CHECKED = "CHECKED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"

    ALL = (PROPOSED, CHECKED, VERIFIED, REJECTED)


class GoalStatus:
    """OPEN until a ``proved`` claim is adjudicated against a VERIFIED derivation."""

    OPEN = "OPEN"
    PROVED = "PROVED"
    REFUTED = "REFUTED"
    UNSUBSTANTIATED = "UNSUBSTANTIATED"

    ALL = (OPEN, PROVED, REFUTED, UNSUBSTANTIATED)


@dataclass
class RuleArg:
    """A role-labelled rule parameter, e.g. ``by := k`` in ``divide_both_sides``.

    Role labels are mandatory here for the same reason they are mandatory on
    distributions (D-003): ``multiply_both_sides(2.0)`` does not say whether 2.0 is
    the multiplier or the side.
    """

    role: str
    value: Expr
    span: Span = field(default_factory=Span)


@dataclass
class GoalStmt(Statement):
    """``goal g1 : x > 0.0`` -- a proposition we intend to establish.

    Stating a goal asserts nothing. ``status`` starts OPEN and only an adjudicated
    ``proved`` statement can move it.
    """

    label: str = ""
    proposition: Expr = field(default=None)  # type: ignore[assignment]
    claim_id: ClaimId | None = None
    status: str = GoalStatus.OPEN


@dataclass
class DeriveStmt(Statement):
    """``derive d1 : y = 2.0 * x from a1 by multiply_both_sides(by := 2.0)``

    ``conclusion`` is what the author claims follows. ``premises`` are claim labels,
    resolved against the claim namespace. ``rule`` names an entry in the trusted rule
    kernel. ``obligations`` and ``status`` are filled by the checker.
    """

    label: str = ""
    conclusion: Expr = field(default=None)  # type: ignore[assignment]
    premises: list[str] = field(default_factory=list)
    premise_ids: list[ClaimId | None] = field(default_factory=list)
    rule: str = ""
    rule_args: list[RuleArg] = field(default_factory=list)
    claim_id: ClaimId | None = None
    #: Computed by the checker. Source cannot set this.
    status: str = DerivationStatus.PROPOSED
    #: Human-readable reason attached when status is REJECTED, for the repair loop.
    rejection_reason: str | None = None


@dataclass
class ProvedStmt(Statement):
    """``proved g1 by d1`` -- a *claim*, which the checker adjudicates.

    Writing this does not make the goal proved. The checker requires that ``d1`` is
    VERIFIED and that its conclusion is canonically identical to the goal's
    proposition; otherwise the goal becomes UNSUBSTANTIATED and a diagnostic is
    raised.
    """

    goal: str = ""
    goal_id: ClaimId | None = None
    derivation: str = ""
    derivation_id: ClaimId | None = None


#: Every statement form introduced by V2. A module containing none of these is a v1
#: module and MUST serialise byte-identically to the way it did before V2 existed.
V2_STATEMENTS: tuple[type, ...] = (GoalStmt, DeriveStmt, ProvedStmt)


def uses_v2(module: Module) -> bool:
    """True when ``module`` uses any V2 reasoning construct.

    This is the switch that keeps historical canonical identity intact: the canonical
    serializer only emits the v0.2 schema tag for modules where this is True, so every
    ACQ0/H2 record remains reconstructible under its original language version
    (directive §28).
    """
    for st in module.statements:
        if isinstance(st, V2_STATEMENTS):
            return True
        # A label on a v1 statement is itself V2 syntax: `assume a1 : P` does not
        # parse under v1. All three labellable forms must be checked, or a module
        # using only `require r1 : P` would be mis-tagged as v1.
        if isinstance(st, (AssumeStmt, RequireStmt, ProveStmt)) and st.label is not None:
            return True
    return False


@dataclass
class Module(Node):
    name: str = "Main"
    statements: list[Statement] = field(default_factory=list)
    source_file: str = "<input>"

    def of_type(self, cls: type) -> list[Statement]:
        return [s for s in self.statements if isinstance(s, cls)]


def walk(node: object) -> Sequence[object]:
    """Yield ``node`` and every nested Node/Arg/ConceptMember/RuleArg beneath it."""
    out: list[object] = []

    def rec(n: object) -> None:
        out.append(n)
        if isinstance(n, (Node, Arg, ConceptMember, RuleArg)):
            for value in vars(n).values():
                if isinstance(value, (Node, Arg, ConceptMember, RuleArg)):
                    rec(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, (Node, Arg, ConceptMember, RuleArg)):
                            rec(item)

    rec(node)
    return out
