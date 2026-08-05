"""Translation from the HML AST into SymPy, with an explicit refusal channel.

Two rules govern everything here.

**Both sides must be translated in one shared context.** A residual is a pair of
subtrees that live in two different modules; if each side invented its own
symbols, ``x`` on the left and ``x`` on the right would be unrelated and every
comparison would come out non-equivalent. The context therefore names symbols by
the *matched* symbol identity from :mod:`.matching`, so corresponding symbols on
the two sides become the same SymPy symbol and non-corresponding ones do not.

**A construct with no faithful SymPy image is refused, not approximated.** SymPy
has no first-order binder, so a quantifier is refused; ``sympy.Q`` is a predicate
namespace, not a binder, and encoding ``forall x . exists y`` through it would
erase the nesting order this language exists to make explicit. Refusal produces a
:class:`~.status.SemanticLossNote` and, upstream, an ``UNSUPPORTED`` verdict --
never a failure.

Assumptions are carried across from declared types, because they are load-bearing:
``a*x < b`` and ``x < b/a`` are equivalent only when ``a > 0``, and the only place
that fact lives is ``a``'s declared type or an ``assume`` statement.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..ast.nodes import (
    BinOp,
    Call,
    Comparison,
    Declaration,
    DefineStmt,
    DistExpr,
    Expr,
    Index,
    Literal,
    LogicalOp,
    Module,
    Quantifier,
    Ref,
    SymbolId,
    UnaryOp,
)
from ..types import QuantityType, ScalarType, Type
from .status import Assumption, SemanticLossNote

__all__ = [
    "SYMPY_AVAILABLE",
    "TranslationContext",
    "Translation",
    "collect_declared_types",
    "type_assumptions",
    "is_propositional",
    "expression_size",
]

try:  # pragma: no cover - exercised by whichever branch this machine takes
    import sympy

    SYMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    sympy = None  # type: ignore[assignment]
    SYMPY_AVAILABLE = False


#: Calls with a faithful SymPy image. Anything else becomes an *uninterpreted*
#: ``sympy.Function``, which is sound: two identical applications are equal, and
#: two different ones are never proved equal.
_KNOWN_CALLS: Mapping[str, str] = {
    "exp": "exp",
    "log": "log",
    "ln": "log",
    "sqrt": "sqrt",
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "abs": "Abs",
}

#: Declared scalar type -> SymPy symbol assumptions. Deliberately conservative:
#: an assumption that is not certainly implied by the type is not asserted.
_SCALAR_ASSUMPTIONS: Mapping[str, dict[str, bool]] = {
    "Bool": {},
    "Integer": {"integer": True, "real": True},
    "Natural": {"integer": True, "nonnegative": True, "real": True},
    "PositiveNatural": {"integer": True, "positive": True, "real": True},
    "Rational": {"rational": True, "real": True},
    "Real": {"real": True},
    "NonNegativeReal": {"nonnegative": True, "real": True},
    "PositiveReal": {"positive": True, "real": True},
    "Probability": {"nonnegative": True, "real": True},
    "PValue": {"nonnegative": True, "real": True},
    "PosteriorProbability": {"nonnegative": True, "real": True},
}

#: Types whose values are confined to ``[0, 1]``. Recorded as an explicit upper
#: bound because SymPy has no assumption for it.
_UNIT_INTERVAL = frozenset({"Probability", "PValue", "PosteriorProbability"})

#: Refuse to hand SymPy anything larger than this. A refusal is a coverage loss;
#: an unbounded ``simplify`` on a pathological tree is a hung evaluation.
_MAX_NODES = 400


def expression_size(e: object) -> int:
    """Node count, used to bound the work handed to SymPy."""
    if not isinstance(e, Expr):
        return 1
    total = 1
    for value in vars(e).values():
        if isinstance(value, Expr):
            total += expression_size(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, Expr):
                    total += expression_size(item)
                elif hasattr(item, "value") and isinstance(item.value, Expr):
                    total += expression_size(item.value)
    return total


def collect_declared_types(module: Module) -> dict[SymbolId, Type]:
    """Map every module-level bound symbol to its declared type."""
    out: dict[SymbolId, Type] = {}
    for st in module.statements:
        if isinstance(st, (Declaration, DefineStmt)) and st.symbol_id is not None:
            if st.declared_type is not None:
                out[st.symbol_id] = st.declared_type
    return out


def type_assumptions(name: str, t: Type | None) -> tuple[dict[str, bool], list[Assumption]]:
    """SymPy assumptions plus the human-readable side conditions they encode."""
    if t is None:
        return {}, []
    base: ScalarType | None = None
    if isinstance(t, ScalarType):
        base = t
    elif isinstance(t, QuantityType):
        base = t.base
    if base is None:
        return {}, []
    flags = dict(_SCALAR_ASSUMPTIONS.get(base.name, {}))
    notes: list[Assumption] = []
    if flags.get("positive"):
        notes.append(Assumption(f"{name} > 0", "declared type"))
    elif flags.get("nonnegative"):
        notes.append(Assumption(f"{name} >= 0", "declared type"))
    if base.name in _UNIT_INTERVAL:
        notes.append(Assumption(f"{name} <= 1", "declared type"))
    return flags, notes


def is_propositional(e: Expr | None) -> bool:
    """Whether ``e`` denotes a proposition rather than a magnitude."""
    if isinstance(e, (Comparison, LogicalOp, Quantifier)):
        return True
    if isinstance(e, UnaryOp) and e.op == "not":
        return True
    if isinstance(e, Literal) and isinstance(e.value, bool):
        return True
    if isinstance(e, Ref):
        return isinstance(e.type_, ScalarType) and e.type_.name == "Bool"
    return False


class Refused(Exception):
    """Raised internally when a construct has no faithful SymPy image."""

    def __init__(self, note: SemanticLossNote) -> None:
        super().__init__(note.reason)
        self.note = note


@dataclass
class Translation:
    """The outcome of translating one subtree."""

    expr: Any = None
    losses: tuple[SemanticLossNote, ...] = ()
    assumptions: tuple[Assumption, ...] = ()
    #: Atoms introduced for propositional reasoning, keyed by SymPy symbol name.
    #: ``derived`` means the atom stands for a compound proposition (a comparison),
    #: so a satisfying assignment over the atoms may not be realisable.
    atoms: Mapping[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.expr is not None and not self.losses


class TranslationContext:
    """Shared naming and assumptions for both sides of a comparison.

    ``pairing`` maps a *right-hand* symbol to its matched *left-hand* symbol. Two
    matched symbols therefore receive one SymPy symbol; unmatched ones receive
    distinct fresh symbols, which is exactly the behaviour that makes a genuine
    difference show up as a difference.
    """

    def __init__(
        self,
        *,
        left_types: Mapping[SymbolId, Type] | None = None,
        right_types: Mapping[SymbolId, Type] | None = None,
        pairing: Mapping[SymbolId, SymbolId] | None = None,
    ) -> None:
        self.left_types = dict(left_types or {})
        self.right_types = dict(right_types or {})
        self.pairing = dict(pairing or {})
        self._symbols: dict[str, Any] = {}
        self._symbol_types: dict[str, Type | None] = {}
        self._names: dict[SymbolId, str] = {}
        self._atoms: dict[str, str] = {}
        self._atom_symbols: dict[str, Any] = {}
        self.assumptions: list[Assumption] = []
        self._counter = 0

    # -- naming ------------------------------------------------------------

    def canonical_symbol_id(self, sid: SymbolId, *, side: str) -> SymbolId:
        if side == "right":
            return self.pairing.get(sid, sid)
        return sid

    def name_for(self, sid: SymbolId, side: str) -> str:
        key = self.canonical_symbol_id(sid, side=side)
        if key not in self._names:
            self._counter += 1
            self._names[key] = f"{key.name}__{self._counter}"
        return self._names[key]

    def declared_type(self, sid: SymbolId, side: str) -> Type | None:
        table = self.left_types if side == "left" else self.right_types
        found = table.get(sid)
        if found is not None:
            return found
        mirror = self.canonical_symbol_id(sid, side=side)
        return self.left_types.get(mirror)

    def symbol(self, sid: SymbolId, side: str, declared: Type | None = None) -> Any:
        name = self.name_for(sid, side)
        if name not in self._symbols:
            t = declared if declared is not None else self.declared_type(sid, side)
            flags, notes = type_assumptions(sid.name, t)
            self._symbols[name] = sympy.Symbol(name, **flags)
            self._symbol_types[name] = t
            self.assumptions.extend(notes)
        return self._symbols[name]

    def symbol_table(self) -> dict[str, Any]:
        return dict(self._symbols)

    def symbol_types(self) -> dict[str, Type | None]:
        """Declared type per SymPy symbol name, for domain-aware sampling."""
        return dict(self._symbol_types)

    # -- propositional atoms ----------------------------------------------

    def atom(self, key: str, derived: bool) -> Any:
        if key not in self._atom_symbols:
            self._atom_symbols[key] = sympy.Symbol(f"atom_{len(self._atom_symbols)}")
            self._atoms[key] = "derived" if derived else "free"
        return self._atom_symbols[key]

    def atoms(self) -> dict[str, str]:
        return dict(self._atoms)

    @property
    def atoms_independent(self) -> bool:
        """True when every atom is a free boolean, so a model over atoms is realisable.

        When an atom stands for a comparison such as ``x > 0``, a propositional
        model may assign it independently of ``x > -1`` and describe a world that
        does not exist. In that case a countermodel proves nothing and the tier
        reports ``INCONCLUSIVE`` rather than a refutation.
        """
        return all(v == "free" for v in self._atoms.values())

    # -- translation -------------------------------------------------------

    def translate(
        self,
        e: Expr | None,
        side: str,
        *,
        binder_types: Mapping[SymbolId, Type | None] | None = None,
    ) -> Translation:
        if not SYMPY_AVAILABLE:  # pragma: no cover - sympy is present on this host
            return Translation(
                None,
                (SemanticLossNote("sympy", "sympy is not importable", "dropped"),),
            )
        if e is None:
            return Translation(
                None, (SemanticLossNote("expression", "no expression", "dropped"),)
            )
        if expression_size(e) > _MAX_NODES:
            return Translation(
                None,
                (
                    SemanticLossNote(
                        "expression",
                        f"larger than the {_MAX_NODES}-node bound handed to SymPy",
                        "dropped",
                    ),
                ),
            )
        before = len(self.assumptions)
        try:
            expr = self._expr(e, side, dict(binder_types or {}))
        except Refused as refusal:
            return Translation(None, (refusal.note,))
        return Translation(
            expr,
            (),
            tuple(self.assumptions[before:]),
            self.atoms(),
        )

    def translate_proposition(
        self,
        e: Expr | None,
        side: str,
        *,
        binder_types: Mapping[SymbolId, Type | None] | None = None,
    ) -> Translation:
        """Translate ``e`` as a *propositional* formula over shared atoms.

        Comparisons become atoms rather than SymPy relations, so a propositional
        decision procedure can be applied. Atoms standing for comparisons are
        flagged ``derived``; see :attr:`atoms_independent` for why that matters.
        """
        if not SYMPY_AVAILABLE:  # pragma: no cover
            return Translation(
                None, (SemanticLossNote("sympy", "sympy is not importable", "dropped"),)
            )
        if e is None:
            return Translation(
                None, (SemanticLossNote("proposition", "no proposition", "dropped"),)
            )
        if expression_size(e) > _MAX_NODES:
            return Translation(
                None,
                (
                    SemanticLossNote(
                        "proposition",
                        f"larger than the {_MAX_NODES}-node bound handed to SymPy",
                        "dropped",
                    ),
                ),
            )
        before = len(self.assumptions)
        try:
            expr = self._prop(e, side, dict(binder_types or {}))
        except Refused as refusal:
            return Translation(None, (refusal.note,))
        return Translation(expr, (), tuple(self.assumptions[before:]), self.atoms())

    def _expr(self, e: Expr, side: str, binders: dict[SymbolId, Type | None]) -> Any:
        if isinstance(e, Literal):
            if isinstance(e.value, bool):
                return sympy.true if e.value else sympy.false
            raw = e.raw or repr(e.value)
            return sympy.Rational(str(raw))

        if isinstance(e, Ref):
            if e.symbol_id is None:
                raise Refused(
                    SemanticLossNote(
                        f"reference {e.name}",
                        "unresolved name; a module that did not resolve denotes nothing",
                        "dropped",
                    )
                )
            declared = binders.get(e.symbol_id)
            return self.symbol(e.symbol_id, side, declared)

        if isinstance(e, UnaryOp):
            if e.op == "not":
                return sympy.Not(self._prop(e.operand, side, binders))
            return -self._expr(e.operand, side, binders)

        if isinstance(e, BinOp):
            left = self._expr(e.left, side, binders)
            right = self._expr(e.right, side, binders)
            if e.op == "+":
                return left + right
            if e.op == "-":
                return left - right
            if e.op == "*":
                return left * right
            if e.op == "/":
                return left / right
            if e.op == "^":
                # sympy.Pow keeps `(a**b)**c` unevaluated for general symbols, so
                # exponent association survives the translation intact.
                return sympy.Pow(left, right, evaluate=True)
            if e.op == "@":
                raise Refused(
                    SemanticLossNote(
                        "matrix product",
                        "SymPy overloads `*` for matrix composition, so `@` and `*` "
                        "would become indistinguishable and a scalar/matrix confusion "
                        "could be certified as equivalent",
                        "dropped",
                    )
                )
            raise Refused(
                SemanticLossNote(f"operator {e.op}", "no SymPy image", "dropped")
            )

        if isinstance(e, Comparison):
            left = self._expr(e.left, side, binders)
            right = self._expr(e.right, side, binders)
            rel = {
                "=": sympy.Eq,
                "!=": sympy.Ne,
                "<": sympy.Lt,
                "<=": sympy.Le,
                ">": sympy.Gt,
                ">=": sympy.Ge,
            }[e.op]
            return rel(left, right, evaluate=False)

        if isinstance(e, LogicalOp):
            left = self._prop(e.left, side, binders)
            right = self._prop(e.right, side, binders)
            return {
                "and": sympy.And,
                "or": sympy.Or,
                "implies": sympy.Implies,
                "iff": sympy.Equivalent,
            }[e.op](left, right)

        if isinstance(e, Call):
            args = [self._expr(a, side, binders) for a in e.args]
            fn = _KNOWN_CALLS.get(e.callee)
            if fn is not None:
                return getattr(sympy, fn)(*args)
            return sympy.Function(e.callee)(*args)

        if isinstance(e, Quantifier):
            raise Refused(
                SemanticLossNote(
                    f"{e.kind} quantifier",
                    "SymPy has no first-order binder. Encoding a quantifier through "
                    "sympy.Q would discard the nesting order, which is precisely the "
                    "property that must not be lost",
                    "dropped",
                )
            )

        if isinstance(e, DistExpr):
            raise Refused(
                SemanticLossNote(
                    f"{e.family} distribution",
                    "a law carries a role and a conditioning set that sympy.stats "
                    "cannot represent; translating only the family and parameters "
                    "would compare less than the object",
                    "dropped",
                )
            )

        if isinstance(e, Index):
            raise Refused(
                SemanticLossNote(
                    "index expression",
                    "HML fixes no index origin, so a subscript has no unambiguous "
                    "SymPy image",
                    "dropped",
                )
            )

        raise Refused(
            SemanticLossNote(
                type(e).__name__, "no SymPy image for this node kind", "dropped"
            )
        )

    def _prop(self, e: Expr | None, side: str, binders: dict[SymbolId, Type | None]) -> Any:
        """Translate a proposition, atomising anything that is not boolean structure."""
        if e is None:
            raise Refused(SemanticLossNote("proposition", "missing", "dropped"))
        if isinstance(e, (LogicalOp, Quantifier)) or (
            isinstance(e, UnaryOp) and e.op == "not"
        ):
            return self._expr(e, side, binders)
        if isinstance(e, Literal) and isinstance(e.value, bool):
            return sympy.true if e.value else sympy.false
        if isinstance(e, Ref):
            sym = self._expr(e, side, binders)
            return self.atom(str(sym), derived=False)
        # A comparison is an atom whose truth is *not* independent of the others.
        translated = self._expr(e, side, binders)
        return self.atom(sympy.srepr(translated), derived=True)
