"""V1 layers 2 and 3 — transformation edges and inferential relations.

HML-V1-CONCEPT-001 Phase 5. Additive over V0, which is frozen at ``hml-v0-baseline``.

A derivation is not a sequence of expressions with the reasoning left implicit. Here every
step is an explicit, typed edge::

    step s1: source := e1, operation := substitute, arguments := {...},
             target := e2, assumptions := [...], justification := rule_or_theorem

**The distinction this module exists to draw.** ``yields``, ``implies`` and
``is equivalent to`` are three different relations and are represented by three different
:class:`EdgeKind` values with **no coercion between them**
(:data:`PROHIBITED_EDGE_COERCIONS`, :func:`edge_kind_coercion_allowed`):

* ``yields`` (``EdgeKind.ALGEBRAIC``) relates **expressions**. Rewriting ``y = 2x + 1``
  into ``y = 2*3 + 1`` under ``x = 3`` asserts nothing about entailment between
  propositions.
* ``implies`` (``EdgeKind.LOGICAL_IMPLICATION``) relates **propositions**, in one
  direction only, under a named inference rule.
* ``is equivalent to`` (``EdgeKind.EQUIVALENCE``) relates propositions in **both**
  directions and therefore generates an obligation in each.

The second reason the layer earns its place is side conditions. Every operation declares
the proof obligations it generates: ``divide_through`` requires a non-zero divisor,
``take_log`` a positive argument, ``differentiate`` differentiability. An algebra step that
silently divides by zero is exactly the error class V0 cannot catch.

``square_both_sides`` records a :class:`Weakening`, never an equivalence: ``x = -2`` and
``x^2 = 4`` are not interchangeable, and a backend or reader that treats the step as
reversible is wrong.

Nothing here claims to *check* a side condition. The layer records the obligation, names
the edge that generated it, and refuses to let it disappear. Discharging obligations
requires a prover, which `docs/design/V1_KERNEL.md` §8 deliberately does not build.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum

__all__ = [
    "Relatum",
    "Node",
    "expression",
    "proposition",
    "EdgeKind",
    "EDGE_DOMAIN",
    "PROHIBITED_EDGE_COERCIONS",
    "edge_kind_coercion_allowed",
    "WarrantKind",
    "Warrant",
    "rule",
    "theorem",
    "definition",
    "Operation",
    "OperationSpec",
    "OPERATIONS",
    "INFERENCE_RULES",
    "CONVERSE_OPERATIONS",
    "ObligationKind",
    "Obligation",
    "Weakening",
    "EdgeKindError",
    "TransformationEdge",
    "step",
    "implications_of_equivalence",
    "EdgeError",
    "ChainReport",
    "TransformationChain",
    "chain_of",
]


# ---------------------------------------------------------------------------
# What an edge may relate
# ---------------------------------------------------------------------------


class Relatum(StrEnum):
    """The kind of thing an edge endpoint is.

    Expressions and propositions are not interchangeable. ``2x + 1`` is an expression and
    has no truth value; ``x > 0`` is a proposition and has one. An edge that relates
    expressions cannot relate propositions and vice versa, which is what stops ``yields``
    being written where ``implies`` is meant.
    """

    EXPRESSION = "expression"
    PROPOSITION = "proposition"


@dataclass(frozen=True)
class Node:
    """A named endpoint of the derivation graph."""

    name: str
    relatum: Relatum
    text: str = ""

    def render(self) -> str:
        body = f": {self.text}" if self.text else ""
        return f"{self.name} [{self.relatum}]{body}"


def expression(name: str, text: str = "") -> Node:
    return Node(name=name, relatum=Relatum.EXPRESSION, text=text)


def proposition(name: str, text: str = "") -> Node:
    return Node(name=name, relatum=Relatum.PROPOSITION, text=text)


# ---------------------------------------------------------------------------
# Edge kinds, and the prohibition on treating them as synonyms
# ---------------------------------------------------------------------------


class EdgeKind(StrEnum):
    """The eight edge kinds of `docs/design/V1_KERNEL.md` §2, plus ``REFUTATION``.

    ``REFUTATION`` is required by the ``counterexample`` operation: a counterexample
    refutes a claimed implication and is not itself an implication. Folding it into
    ``LOGICAL_IMPLICATION`` would make "the converse fails" indistinguishable from "the
    converse holds", which is the opposite of the point.
    """

    ALGEBRAIC = "algebraic_transformation"
    LOGICAL_IMPLICATION = "logical_implication"
    EQUIVALENCE = "equivalence"
    APPROXIMATION = "approximation"
    NUMERICAL = "numerical_computation"
    STATISTICAL = "statistical_inference"
    DEFINITION_EXPANSION = "definition_expansion"
    THEOREM_APPLICATION = "theorem_application"
    REFUTATION = "refutation"


#: The relatum domain each edge kind operates on. ``None`` means "either, but the whole
#: edge must be homogeneous": expanding a definition rewrites an expression *or* unfolds a
#: proposition, never both at once.
EDGE_DOMAIN: dict[EdgeKind, Relatum | None] = {
    EdgeKind.ALGEBRAIC: Relatum.EXPRESSION,
    EdgeKind.LOGICAL_IMPLICATION: Relatum.PROPOSITION,
    EdgeKind.EQUIVALENCE: Relatum.PROPOSITION,
    EdgeKind.APPROXIMATION: Relatum.EXPRESSION,
    EdgeKind.NUMERICAL: Relatum.EXPRESSION,
    EdgeKind.STATISTICAL: Relatum.PROPOSITION,
    EdgeKind.DEFINITION_EXPANSION: None,
    EdgeKind.THEOREM_APPLICATION: Relatum.PROPOSITION,
    EdgeKind.REFUTATION: Relatum.PROPOSITION,
}

#: Pairs that are commonly conflated in prose, with the reason each conflation is wrong.
#: The table is documentation; :func:`edge_kind_coercion_allowed` denies *every*
#: non-identity pair whether or not it is listed, exactly as
#: :func:`hamiltonian_lang.v1.epistemic.coercion_allowed` does for justifications.
PROHIBITED_EDGE_COERCIONS: dict[tuple[EdgeKind, EdgeKind], str] = {
    (EdgeKind.ALGEBRAIC, EdgeKind.LOGICAL_IMPLICATION): (
        "yields is not implies: an algebraic rewrite relates expressions and asserts "
        "nothing about entailment between propositions"
    ),
    (EdgeKind.LOGICAL_IMPLICATION, EdgeKind.ALGEBRAIC): (
        "implies is not yields: an entailment between propositions is not a rewrite of "
        "one expression into another"
    ),
    (EdgeKind.LOGICAL_IMPLICATION, EdgeKind.EQUIVALENCE): (
        "asserting P implies Q does not license Q implies P; the converse must be "
        "separately established or refuted"
    ),
    (EdgeKind.EQUIVALENCE, EdgeKind.LOGICAL_IMPLICATION): (
        "an equivalence carries an obligation in each direction; use "
        "implications_of_equivalence to construct a directed edge explicitly, which "
        "keeps the obligation attached"
    ),
    (EdgeKind.ALGEBRAIC, EdgeKind.EQUIVALENCE): (
        "not every rewrite is reversible; squaring both sides is the standing "
        "counterexample"
    ),
    (EdgeKind.APPROXIMATION, EdgeKind.ALGEBRAIC): (
        "an approximation is not an identity; the error term does not vanish because it "
        "stopped being written down"
    ),
    (EdgeKind.NUMERICAL, EdgeKind.ALGEBRAIC): (
        "a numerical evaluation at finite precision is not a symbolic identity"
    ),
    (EdgeKind.STATISTICAL, EdgeKind.LOGICAL_IMPLICATION): (
        "a statistical inference is Evidence-justified; it does not entail its "
        "conclusion (see v1.epistemic.PROHIBITED_COERCIONS)"
    ),
    (EdgeKind.REFUTATION, EdgeKind.LOGICAL_IMPLICATION): (
        "a counterexample refutes a claim; it does not establish one"
    ),
}


def edge_kind_coercion_allowed(source: EdgeKind, target: EdgeKind) -> tuple[bool, str]:
    """Whether an edge of kind ``source`` may stand where ``target`` is required.

    Identity only. Everything else is refused, with the recorded reason when there is
    one. A permissive default is how ``yields`` quietly becomes ``implies``.
    """
    if source == target:
        return True, ""
    reason = PROHIBITED_EDGE_COERCIONS.get((source, target))
    if reason:
        return False, reason
    return False, f"no coercion from {source} to {target} is defined"


# ---------------------------------------------------------------------------
# Warrants — the rule or theorem cited for a step
# ---------------------------------------------------------------------------


class WarrantKind(StrEnum):
    RULE = "rule"
    THEOREM = "theorem"
    DEFINITION = "definition"
    AXIOM = "axiom"
    COMPUTATION = "computation"
    UNSTATED = "unstated"


@dataclass(frozen=True)
class Warrant:
    """The named rule or theorem an edge is justified by.

    This is **not** :class:`hamiltonian_lang.v1.epistemic.Justification`. That type says
    on what epistemic grounds a *claim* is held; this one names the rewrite rule or
    theorem cited for a *step*. Conflating them would let "I cited a rule" read as
    "I have a proof".
    """

    kind: WarrantKind = WarrantKind.UNSTATED
    name: str = ""

    @property
    def stated(self) -> bool:
        return self.kind is not WarrantKind.UNSTATED and bool(self.name)

    def render(self) -> str:
        return f"{self.kind} {self.name}" if self.stated else "unstated"

    def __str__(self) -> str:
        return self.render()


UNSTATED = Warrant()


def rule(name: str) -> Warrant:
    return Warrant(WarrantKind.RULE, name)


def theorem(name: str) -> Warrant:
    return Warrant(WarrantKind.THEOREM, name)


def definition(name: str) -> Warrant:
    return Warrant(WarrantKind.DEFINITION, name)


#: Inference rules, with the minimum number of premises each needs. Applying
#: ``modus_ponens`` to a single premise is a structural error, not a stylistic one.
INFERENCE_RULES: dict[str, int] = {
    "modus_ponens": 2,
    "modus_tollens": 2,
    "universal_instantiation": 1,
    "existential_generalisation": 1,
    "contraposition": 1,
    "induction": 2,
    "case_analysis": 2,
    "contradiction": 1,
}


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


class Operation(StrEnum):
    """Every operation an edge may carry. The set is closed."""

    # --- algebraic and analytic rewriting (L2) ---
    SUBSTITUTE = "substitute"
    REARRANGE = "rearrange"
    EXPAND = "expand"
    COLLECT = "collect"
    FACTOR = "factor"
    SIMPLIFY = "simplify"
    CANCEL = "cancel"
    DIVIDE = "divide"
    DIVIDE_THROUGH = "divide_through"
    TAKE_LOG = "take_log"
    SQUARE_BOTH_SIDES = "square_both_sides"
    SQRT_BOTH_SIDES = "sqrt_both_sides"
    DIFFERENTIATE = "differentiate"
    INTEGRATE = "integrate"
    LIMIT = "limit"
    APPLY = "apply"
    TAKE_EXPECTATION = "take_expectation"
    DERIVE = "derive"
    YIELD = "yield"
    # --- lossy rewriting ---
    APPROXIMATE = "approximate"
    EVALUATE = "evaluate"
    # --- unfolding and citation ---
    EXPAND_DEFINITION = "expand_definition"
    APPLY_THEOREM = "apply_theorem"
    # --- inferential relations (L3) ---
    IMPLY = "imply"
    EQUIVALENT = "equivalent"
    NECESSARY = "necessary"
    SUFFICIENT = "sufficient"
    CONVERSE = "converse"
    COUNTEREXAMPLE = "counterexample"
    INFER = "infer"


class ObligationKind(StrEnum):
    SIDE_CONDITION = "side_condition"
    CASE_SPLIT = "case_split"
    DIRECTION = "direction"
    HYPOTHESIS = "hypothesis"
    CONVERSE = "converse"


@dataclass(frozen=True)
class OperationSpec:
    """The full contract of one operation: what it needs and what it owes."""

    operation: Operation
    kind: EdgeKind
    #: argument names that must be present; a missing one makes the edge invalid
    required_arguments: tuple[str, ...] = ()
    #: warrant kinds that satisfy this operation; empty means no warrant is required
    required_warrant: tuple[WarrantKind, ...] = ()
    #: obligation templates, formatted against the edge's arguments plus ``source``,
    #: ``sources``, ``target`` and ``warrant``
    obligations: tuple[tuple[str, ObligationKind], ...] = ()
    #: (argument name, template) — one obligation per item of a sequence-valued argument
    per_item_obligation: tuple[str, str] | None = None
    #: what the step irreversibly loses, if anything
    weakening: str | None = None
    min_sources: int = 1
    max_sources: int | None = 1
    #: False for ``converse``: stating a converse does not assert it
    asserted: bool = True
    #: True for ``necessary``: "P is necessary for Q" entails Q -> P, not P -> Q
    reversed_entailment: bool = False
    note: str = ""

    @property
    def reversible(self) -> bool:
        """False whenever the step records a weakening. Never assume otherwise."""
        return self.weakening is None


def _spec(
    operation: Operation,
    kind: EdgeKind,
    *,
    required_arguments: tuple[str, ...] = (),
    required_warrant: tuple[WarrantKind, ...] = (),
    obligations: tuple[tuple[str, ObligationKind], ...] = (),
    per_item_obligation: tuple[str, str] | None = None,
    weakening: str | None = None,
    min_sources: int = 1,
    max_sources: int | None = 1,
    asserted: bool = True,
    reversed_entailment: bool = False,
    note: str = "",
) -> OperationSpec:
    return OperationSpec(
        operation=operation,
        kind=kind,
        required_arguments=required_arguments,
        required_warrant=required_warrant,
        obligations=obligations,
        per_item_obligation=per_item_obligation,
        weakening=weakening,
        min_sources=min_sources,
        max_sources=max_sources,
        asserted=asserted,
        reversed_entailment=reversed_entailment,
        note=note,
    )


_SIDE = ObligationKind.SIDE_CONDITION

#: The operation table. This is the layer's contract: adding an operation without its
#: obligations is how a checker starts producing authoritative-looking output that is
#: wrong.
OPERATIONS: dict[Operation, OperationSpec] = {
    Operation.SUBSTITUTE: _spec(
        Operation.SUBSTITUTE,
        EdgeKind.ALGEBRAIC,
        min_sources=1,
        max_sources=None,
        note="rewrites expressions; asserts no entailment between propositions",
    ),
    Operation.REARRANGE: _spec(
        Operation.REARRANGE,
        EdgeKind.ALGEBRAIC,
        required_arguments=("for",),
        obligations=(("{for} is isolable in {source}", _SIDE),),
    ),
    Operation.EXPAND: _spec(Operation.EXPAND, EdgeKind.ALGEBRAIC),
    Operation.COLLECT: _spec(Operation.COLLECT, EdgeKind.ALGEBRAIC),
    Operation.FACTOR: _spec(Operation.FACTOR, EdgeKind.ALGEBRAIC),
    Operation.SIMPLIFY: _spec(
        Operation.SIMPLIFY,
        EdgeKind.ALGEBRAIC,
        required_warrant=(WarrantKind.RULE, WarrantKind.THEOREM, WarrantKind.DEFINITION),
        obligations=(("the identity {warrant} holds on the domain of {source}", _SIDE),),
        note="must record WHICH identity was used, or the step is not checkable",
    ),
    Operation.CANCEL: _spec(
        Operation.CANCEL,
        EdgeKind.ALGEBRAIC,
        required_arguments=("factor",),
        obligations=(("{factor} != 0", _SIDE),),
    ),
    Operation.DIVIDE: _spec(
        Operation.DIVIDE,
        EdgeKind.ALGEBRAIC,
        required_arguments=("by",),
        obligations=(("{by} != 0", _SIDE),),
    ),
    Operation.DIVIDE_THROUGH: _spec(
        Operation.DIVIDE_THROUGH,
        EdgeKind.ALGEBRAIC,
        required_arguments=("by",),
        obligations=(("{by} != 0", _SIDE),),
        note="dividing an equation through by a quantity that may vanish is the error "
        "class this layer exists to catch",
    ),
    Operation.TAKE_LOG: _spec(
        Operation.TAKE_LOG,
        EdgeKind.ALGEBRAIC,
        required_arguments=("of",),
        obligations=(("{of} > 0", _SIDE),),
    ),
    Operation.SQUARE_BOTH_SIDES: _spec(
        Operation.SQUARE_BOTH_SIDES,
        EdgeKind.ALGEBRAIC,
        weakening="squaring is not reversible: x = -2 and x^2 = 4 are not "
        "interchangeable, and the step admits extraneous roots that must be checked "
        "against {source}",
        note="records a weakening, NOT an equivalence",
    ),
    Operation.SQRT_BOTH_SIDES: _spec(
        Operation.SQRT_BOTH_SIDES,
        EdgeKind.ALGEBRAIC,
        obligations=(
            ("both sides of {source} are >= 0", _SIDE),
            ("the sign branch of the root is not unique: both branches of {target} "
             "must be considered", ObligationKind.CASE_SPLIT),
        ),
    ),
    Operation.DIFFERENTIATE: _spec(
        Operation.DIFFERENTIATE,
        EdgeKind.ALGEBRAIC,
        required_arguments=("wrt",),
        obligations=(
            ("{source} is differentiable with respect to {wrt} on its domain", _SIDE),
        ),
    ),
    Operation.INTEGRATE: _spec(
        Operation.INTEGRATE,
        EdgeKind.ALGEBRAIC,
        required_arguments=("wrt", "over"),
        obligations=(
            ("{source} is integrable with respect to {wrt} over {over}", _SIDE),
        ),
    ),
    Operation.LIMIT: _spec(
        Operation.LIMIT,
        EdgeKind.ALGEBRAIC,
        required_arguments=("variable", "approaches"),
        obligations=(
            ("the limit of {source} as {variable} -> {approaches} exists", _SIDE),
        ),
    ),
    Operation.APPLY: _spec(
        Operation.APPLY,
        EdgeKind.ALGEBRAIC,
        required_arguments=("fn",),
        obligations=(("{source} is in domain({fn})", _SIDE),),
    ),
    Operation.TAKE_EXPECTATION: _spec(
        Operation.TAKE_EXPECTATION,
        EdgeKind.ALGEBRAIC,
        required_arguments=("under",),
        obligations=(("E_{under}[{source}] exists (integrability)", _SIDE),),
        weakening="an identity between random variables is strictly stronger than an "
        "identity between their expectations: E[X] = E[Y] does not recover X = Y",
    ),
    Operation.DERIVE: _spec(
        Operation.DERIVE,
        EdgeKind.ALGEBRAIC,
        required_warrant=(WarrantKind.RULE, WarrantKind.THEOREM, WarrantKind.AXIOM),
        obligations=(("the rule {warrant} applies to {source}", _SIDE),),
        min_sources=1,
        max_sources=None,
    ),
    Operation.YIELD: _spec(
        Operation.YIELD,
        EdgeKind.ALGEBRAIC,
        min_sources=1,
        max_sources=None,
        note="the canonical L2 edge: {source} yields {target}. It does NOT assert that "
        "{source} implies {target}",
    ),
    Operation.APPROXIMATE: _spec(
        Operation.APPROXIMATE,
        EdgeKind.APPROXIMATION,
        required_arguments=("bound",),
        obligations=(
            ("the error of replacing {source} by {target} is bounded by {bound}", _SIDE),
        ),
        weakening="an approximation is not an equality; every downstream equality "
        "inherits the error term {bound}",
    ),
    Operation.EVALUATE: _spec(
        Operation.EVALUATE,
        EdgeKind.NUMERICAL,
        required_arguments=("precision",),
        obligations=(
            ("the evaluation of {source} is exact to {precision}", _SIDE),
        ),
        weakening="a numerical value at finite precision is not a symbolic identity; "
        "rounding error propagates",
    ),
    Operation.EXPAND_DEFINITION: _spec(
        Operation.EXPAND_DEFINITION,
        EdgeKind.DEFINITION_EXPANSION,
        required_warrant=(WarrantKind.DEFINITION,),
        obligations=(
            ("the definition {warrant} is in scope and its arguments match {source}",
             _SIDE),
        ),
    ),
    Operation.APPLY_THEOREM: _spec(
        Operation.APPLY_THEOREM,
        EdgeKind.THEOREM_APPLICATION,
        required_warrant=(WarrantKind.THEOREM,),
        obligations=(
            ("the hypotheses of {warrant} hold for {sources}", ObligationKind.HYPOTHESIS),
        ),
        per_item_obligation=("hypotheses", "{warrant} requires: {item}"),
        min_sources=1,
        max_sources=None,
    ),
    Operation.IMPLY: _spec(
        Operation.IMPLY,
        EdgeKind.LOGICAL_IMPLICATION,
        required_warrant=(WarrantKind.RULE,),
        obligations=(
            ("the premises {sources} of {warrant} are established", _SIDE),
        ),
        min_sources=1,
        max_sources=None,
        note="one direction only; the converse is a separate, unasserted claim",
    ),
    Operation.EQUIVALENT: _spec(
        Operation.EQUIVALENT,
        EdgeKind.EQUIVALENCE,
        obligations=(
            ("{source} implies {target}", ObligationKind.DIRECTION),
            ("{target} implies {source}", ObligationKind.DIRECTION),
        ),
        note="bidirectional; asserting it owes a proof in each direction",
    ),
    Operation.SUFFICIENT: _spec(
        Operation.SUFFICIENT,
        EdgeKind.LOGICAL_IMPLICATION,
        obligations=(("{source} implies {target}", _SIDE),),
        note="'{source} is sufficient for {target}' entails source -> target",
    ),
    Operation.NECESSARY: _spec(
        Operation.NECESSARY,
        EdgeKind.LOGICAL_IMPLICATION,
        obligations=(("{target} implies {source}", _SIDE),),
        reversed_entailment=True,
        note="'{source} is necessary for {target}' entails target -> source; it is the "
        "converse of sufficient and must not be written for it",
    ),
    Operation.CONVERSE: _spec(
        Operation.CONVERSE,
        EdgeKind.LOGICAL_IMPLICATION,
        obligations=(
            ("the converse '{target} implies {source}' is neither established nor "
             "refuted", ObligationKind.CONVERSE),
        ),
        asserted=False,
        reversed_entailment=True,
        note="stating a converse does not assert it",
    ),
    Operation.COUNTEREXAMPLE: _spec(
        Operation.COUNTEREXAMPLE,
        EdgeKind.REFUTATION,
        required_arguments=("witness",),
        obligations=(
            ("{witness} satisfies {source} and violates {target}", _SIDE),
        ),
        note="refutes '{source} implies {target}'; it is not itself an implication",
    ),
    Operation.INFER: _spec(
        Operation.INFER,
        EdgeKind.STATISTICAL,
        required_arguments=("from_data", "procedure"),
        obligations=(
            ("the assumptions of {procedure} hold for {from_data}", _SIDE),
        ),
        weakening="a statistical inference yields Evidence, not Proof; the conclusion "
        "does not follow deductively from {from_data}",
        min_sources=1,
        max_sources=None,
    ),
}

#: Operations that state converse claims of one another. Writing one where the other is
#: meant is the single most common inferential slip in prose.
CONVERSE_OPERATIONS: dict[Operation, Operation] = {
    Operation.NECESSARY: Operation.SUFFICIENT,
    Operation.SUFFICIENT: Operation.NECESSARY,
}


# ---------------------------------------------------------------------------
# Obligations and weakenings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Obligation:
    """A side condition a step generated and did not discharge."""

    edge: str
    operation: Operation
    condition: str
    kind: ObligationKind = ObligationKind.SIDE_CONDITION

    def render(self) -> str:
        return f"[{self.kind}] {self.edge} ({self.operation}): {self.condition}"

    def __str__(self) -> str:
        return self.render()


@dataclass(frozen=True)
class Weakening:
    """Information a step destroyed. Never an equivalence, never reversible."""

    edge: str
    operation: Operation
    lost: str

    @property
    def reversible(self) -> bool:
        """Always False. Present so no caller has to infer reversibility."""
        return False

    def render(self) -> str:
        return f"[weakened] {self.edge} ({self.operation}): {self.lost}"

    def __str__(self) -> str:
        return self.render()


class EdgeKindError(TypeError):
    """An edge of one kind was demanded where another kind is required."""


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------

Argument = str | tuple[str, ...]


class _Ctx(dict[str, str]):
    """Formatting context that names what is missing instead of raising."""

    def __missing__(self, key: str) -> str:
        return f"<missing argument {key!r}>"


@dataclass(frozen=True)
class TransformationEdge:
    """One step of a derivation, with its operation, warrant and assumptions explicit."""

    name: str
    operation: Operation
    source: tuple[str, ...]
    target: str
    arguments: Mapping[str, Argument] = field(default_factory=dict)
    assumptions: tuple[str, ...] = ()
    justification: Warrant = UNSTATED

    @property
    def spec(self) -> OperationSpec:
        return OPERATIONS[self.operation]

    @property
    def kind(self) -> EdgeKind:
        """Derived from the operation and not overridable.

        Letting a caller label an edge is how a rewrite acquires the word ``implies``.
        """
        return self.spec.kind

    @property
    def asserted(self) -> bool:
        return self.spec.asserted

    @property
    def reversible(self) -> bool:
        return self.spec.reversible

    def entailment(self) -> tuple[tuple[str, ...], str] | None:
        """The entailment this edge asserts, as ``(premises, conclusion)``.

        ``None`` when the edge asserts no entailment — every L2 rewrite, and ``converse``,
        which states a claim without asserting it.
        """
        if self.kind is not EdgeKind.LOGICAL_IMPLICATION or not self.asserted:
            return None
        if not self.source:
            return None
        if self.spec.reversed_entailment:
            return (self.target,), self.source[0]
        return self.source, self.target

    def may_be_used_as(self, required: EdgeKind) -> tuple[bool, str]:
        """Whether this edge can stand where an edge of kind ``required`` is needed."""
        return edge_kind_coercion_allowed(self.kind, required)

    def require_kind(self, required: EdgeKind) -> None:
        """Raise :class:`EdgeKindError` unless this edge is already of kind ``required``."""
        ok, reason = self.may_be_used_as(required)
        if not ok:
            raise EdgeKindError(
                f"step {self.name} is a {self.kind} edge but a {required} edge is "
                f"required: {reason}"
            )

    def _context(self) -> _Ctx:
        ctx = _Ctx()
        for key, value in self.arguments.items():
            ctx[key] = value if isinstance(value, str) else ", ".join(value)
        ctx["source"] = self.source[0] if self.source else "<no source>"
        ctx["sources"] = ", ".join(self.source) if self.source else "<no source>"
        ctx["target"] = self.target
        ctx["warrant"] = self.justification.name or self.justification.render()
        return ctx

    def obligations(self) -> tuple[Obligation, ...]:
        """Every proof obligation this step generates and does not discharge."""
        ctx = self._context()
        out = [
            Obligation(self.name, self.operation, template.format_map(ctx), kind)
            for template, kind in self.spec.obligations
        ]
        per_item = self.spec.per_item_obligation
        if per_item is not None:
            arg_name, template = per_item
            raw = self.arguments.get(arg_name, ())
            items = (raw,) if isinstance(raw, str) else tuple(raw)
            for item in items:
                item_ctx = _Ctx(ctx)
                item_ctx["item"] = item
                out.append(
                    Obligation(
                        self.name,
                        self.operation,
                        template.format_map(item_ctx),
                        ObligationKind.HYPOTHESIS,
                    )
                )
        return tuple(out)

    def weakening(self) -> Weakening | None:
        """The information this step irreversibly loses, or ``None``."""
        lost = self.spec.weakening
        if lost is None:
            return None
        return Weakening(self.name, self.operation, lost.format_map(self._context()))

    def render(self) -> str:
        args = ", ".join(
            f"{k} := {v if isinstance(v, str) else list(v)}"
            for k, v in self.arguments.items()
        )
        parts = [
            f"step {self.name}: source := [{', '.join(self.source)}]",
            f"operation := {self.operation}",
        ]
        if args:
            parts.append(f"arguments := {{{args}}}")
        parts.append(f"target := {self.target}")
        if self.assumptions:
            parts.append(f"assumptions := [{', '.join(self.assumptions)}]")
        parts.append(f"justification := {self.justification.render()}")
        return ", ".join(parts)


def step(
    name: str,
    *,
    source: str | Sequence[str],
    operation: Operation,
    target: str,
    arguments: Mapping[str, Argument] | None = None,
    assumptions: Sequence[str] = (),
    justification: Warrant = UNSTATED,
) -> TransformationEdge:
    """Build a :class:`TransformationEdge` in the surface order of the step form."""
    sources = (source,) if isinstance(source, str) else tuple(source)
    return TransformationEdge(
        name=name,
        operation=operation,
        source=sources,
        target=target,
        arguments=dict(arguments or {}),
        assumptions=tuple(assumptions),
        justification=justification,
    )


def implications_of_equivalence(
    edge: TransformationEdge,
) -> tuple[TransformationEdge, TransformationEdge]:
    """The two directed implications an equivalence owes.

    This is an explicit **construction**, not a coercion: it returns two new
    ``LOGICAL_IMPLICATION`` edges, each carrying its own obligation, and it leaves
    :func:`edge_kind_coercion_allowed` unchanged. An equivalence still cannot be
    *silently* read as an implication.
    """
    if edge.kind is not EdgeKind.EQUIVALENCE:
        raise EdgeKindError(
            f"step {edge.name} is a {edge.kind} edge; only an equivalence has two "
            f"directed implications"
        )
    forward = replace(
        edge,
        name=f"{edge.name}_forward",
        operation=Operation.SUFFICIENT,
        source=(edge.source[0],),
        target=edge.target,
    )
    backward = replace(
        edge,
        name=f"{edge.name}_backward",
        operation=Operation.SUFFICIENT,
        source=(edge.target,),
        target=edge.source[0],
    )
    return forward, backward


# ---------------------------------------------------------------------------
# Chains
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EdgeError:
    """A defect located at one edge. ``index`` is the edge's position in the chain."""

    code: str
    index: int
    edge: str
    message: str

    def render(self) -> str:
        return f"{self.code} [step {self.index}: {self.edge}] {self.message}"

    def __str__(self) -> str:
        return self.render()


@dataclass(frozen=True)
class ChainReport:
    """The result of validating a derivation."""

    obligations: tuple[Obligation, ...] = ()
    weakenings: tuple[Weakening, ...] = ()
    errors: tuple[EdgeError, ...] = ()
    dependencies: tuple[str, ...] = ()
    unasserted: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def first_invalid(self) -> EdgeError | None:
        """The offending edge, or ``None``. Chains fail at a *location*, not globally."""
        return self.errors[0] if self.errors else None

    def obligations_of(self, edge: str) -> tuple[Obligation, ...]:
        return tuple(o for o in self.obligations if o.edge == edge)

    def render(self) -> str:
        lines: list[str] = []
        if self.errors:
            lines.append(f"{len(self.errors)} invalid step(s):")
            lines.extend("  " + e.render() for e in self.errors)
        else:
            lines.append("chain structurally valid; obligations are NOT discharged")
        if self.obligations:
            lines.append(f"{len(self.obligations)} open obligation(s):")
            lines.extend("  " + o.render() for o in self.obligations)
        if self.weakenings:
            lines.append(f"{len(self.weakenings)} weakening(s):")
            lines.extend("  " + w.render() for w in self.weakenings)
        if self.dependencies:
            lines.append("assumptions carried forward: " + ", ".join(self.dependencies))
        if self.unasserted:
            lines.append("stated but not asserted: " + ", ".join(self.unasserted))
        return "\n".join(lines)


#: The wrong-domain diagnostic gets an explicit gloss for the two kinds most often
#: conflated, because "expected an expression, got a proposition" does not by itself tell
#: the reader that they wrote ``yields`` where they meant ``implies``.
_DOMAIN_GLOSS: dict[tuple[EdgeKind, Relatum], str] = {
    (EdgeKind.ALGEBRAIC, Relatum.PROPOSITION): PROHIBITED_EDGE_COERCIONS[
        (EdgeKind.LOGICAL_IMPLICATION, EdgeKind.ALGEBRAIC)
    ],
    (EdgeKind.LOGICAL_IMPLICATION, Relatum.EXPRESSION): PROHIBITED_EDGE_COERCIONS[
        (EdgeKind.ALGEBRAIC, EdgeKind.LOGICAL_IMPLICATION)
    ],
    (EdgeKind.EQUIVALENCE, Relatum.EXPRESSION): (
        "an equivalence relates propositions; two expressions that rewrite into each "
        "other are related by an algebraic edge, not by 'is equivalent to'"
    ),
}


def _domain_message(
    kind: EdgeKind, domain: Relatum, name: str, actual: Relatum
) -> str:
    gloss = _DOMAIN_GLOSS.get((kind, actual), "")
    tail = f" — {gloss}" if gloss else ""
    return f"a {kind} edge relates {domain}s, but {name!r} is a {actual}{tail}"


class TransformationChain:
    """A derivation: declared nodes plus an ordered list of edges.

    :meth:`validate` returns the accumulated obligations and weakenings together with
    every structurally invalid edge, each located by index and name. It does **not**
    discharge any obligation; there is no prover here and pretending otherwise is the
    failure mode this project treats as worst.
    """

    def __init__(self, name: str = "chain") -> None:
        self.name = name
        self._nodes: dict[str, Node] = {}
        self._edges: list[TransformationEdge] = []

    # -- construction --------------------------------------------------------

    def declare(self, *nodes: Node) -> TransformationChain:
        for node in nodes:
            self._nodes[node.name] = node
        return self

    def add(self, *edges: TransformationEdge) -> TransformationChain:
        self._edges.extend(edges)
        return self

    @property
    def nodes(self) -> Mapping[str, Node]:
        return dict(self._nodes)

    @property
    def edges(self) -> tuple[TransformationEdge, ...]:
        return tuple(self._edges)

    def edge(self, name: str) -> TransformationEdge | None:
        for e in self._edges:
            if e.name == name:
                return e
        return None

    # -- queries -------------------------------------------------------------

    def require(self, edge_name: str, kind: EdgeKind) -> EdgeError | None:
        """Check that a named edge is of the required kind.

        This is the caller-facing form of the ``yields`` / ``implies`` prohibition: a
        consumer that needs an entailment asks for one and is refused an algebraic
        rewrite.
        """
        for index, e in enumerate(self._edges):
            if e.name == edge_name:
                ok, reason = e.may_be_used_as(kind)
                if ok:
                    return None
                return EdgeError(
                    "HML-X609",
                    index,
                    edge_name,
                    f"a {kind} edge is required here but {edge_name} is a {e.kind}: "
                    f"{reason}",
                )
        return EdgeError("HML-X610", -1, edge_name, f"no step named {edge_name}")

    # -- validation ----------------------------------------------------------

    def validate(self) -> ChainReport:
        errors: list[EdgeError] = []
        obligations: list[Obligation] = []
        weakenings: list[Weakening] = []
        dependencies: list[str] = []
        unasserted: list[str] = []

        known: dict[str, Node] = dict(self._nodes)
        produced: set[str] = set()
        seen_edges: set[str] = set()

        for index, edge in enumerate(self._edges):
            spec = edge.spec
            here: list[EdgeError] = []

            def fail(
                code: str,
                message: str,
                _here: list[EdgeError] = here,
                _index: int = index,
                _name: str = edge.name,
            ) -> None:
                _here.append(EdgeError(code, _index, _name, message))

            if edge.name in seen_edges:
                fail("HML-X608", f"duplicate step name {edge.name!r}")
            seen_edges.add(edge.name)

            # 1. required arguments
            missing = [a for a in spec.required_arguments if a not in edge.arguments]
            if missing:
                fail(
                    "HML-X601",
                    f"{edge.operation} requires argument(s) "
                    f"{', '.join(repr(m) for m in missing)}; without them the step "
                    f"generates a side condition that cannot be stated",
                )

            # 2. required warrant
            if spec.required_warrant:
                if not edge.justification.stated:
                    fail(
                        "HML-X602",
                        f"{edge.operation} must cite a "
                        f"{' or '.join(spec.required_warrant)}; an uncited step is not "
                        f"checkable",
                    )
                elif edge.justification.kind not in spec.required_warrant:
                    fail(
                        "HML-X602",
                        f"{edge.operation} must cite a "
                        f"{' or '.join(spec.required_warrant)}, not a "
                        f"{edge.justification.kind}",
                    )

            # 3. inference-rule name and arity
            if edge.operation is Operation.IMPLY and edge.justification.stated:
                rule_name = edge.justification.name
                if rule_name not in INFERENCE_RULES:
                    fail(
                        "HML-X603",
                        f"{rule_name!r} is not a known inference rule; known rules are "
                        f"{', '.join(sorted(INFERENCE_RULES))}",
                    )
                elif len(edge.source) < INFERENCE_RULES[rule_name]:
                    fail(
                        "HML-X604",
                        f"{rule_name} needs at least {INFERENCE_RULES[rule_name]} "
                        f"premises, {len(edge.source)} given",
                    )

            # 4. source arity
            if len(edge.source) < spec.min_sources:
                fail(
                    "HML-X604",
                    f"{edge.operation} needs at least {spec.min_sources} source(s), "
                    f"{len(edge.source)} given",
                )
            if spec.max_sources is not None and len(edge.source) > spec.max_sources:
                fail(
                    "HML-X604",
                    f"{edge.operation} takes at most {spec.max_sources} source(s), "
                    f"{len(edge.source)} given",
                )

            # 5. grounding and relatum domain
            domain = EDGE_DOMAIN[spec.kind]
            if domain is None:
                for name in edge.source:
                    if name in known:
                        domain = known[name].relatum
                        break
                else:
                    domain = Relatum.EXPRESSION

            for name in edge.source:
                node = known.get(name)
                if node is None:
                    fail(
                        "HML-X605",
                        f"source {name!r} is neither declared nor produced by an "
                        f"earlier step",
                    )
                elif node.relatum is not domain:
                    fail("HML-X606", _domain_message(spec.kind, domain, name, node.relatum))

            target_node = known.get(edge.target)
            if target_node is None:
                known[edge.target] = Node(edge.target, domain)
            elif target_node.relatum is not domain:
                fail(
                    "HML-X606",
                    f"a {spec.kind} edge produces a {domain}, but target "
                    f"{edge.target!r} is declared as a {target_node.relatum}",
                )
            produced.add(edge.target)

            # 6. accumulate. Obligations are recorded even for a defective edge: a
            # divisor that might be zero does not stop mattering because the step also
            # failed some other check.
            obligations.extend(edge.obligations())
            w = edge.weakening()
            if w is not None:
                weakenings.append(w)
            for assumption in edge.assumptions:
                if assumption not in dependencies:
                    dependencies.append(assumption)
            if not spec.asserted:
                unasserted.append(edge.name)

            errors.extend(here)

        return ChainReport(
            obligations=tuple(obligations),
            weakenings=tuple(weakenings),
            errors=tuple(errors),
            dependencies=tuple(dependencies),
            unasserted=tuple(unasserted),
        )


def chain_of(nodes: Iterable[Node], edges: Iterable[TransformationEdge],
             name: str = "chain") -> TransformationChain:
    """Convenience constructor for a fully specified chain."""
    return TransformationChain(name).declare(*nodes).add(*edges)
