"""Shared machinery for the two linear infix surfaces (candidates A and B).

Holds three things that A and B must not implement twice, because two implementations
of the same precedence table is two chances to get it wrong:

* a precedence- *and associativity-* correct expression printer;
* a type and dimension printer that emits syntax the HML-L1 parser actually accepts;
* a small ASCII tokeniser and a precedence-climbing expression reader, used by
  candidate B (candidate A reads with the real HML-L1 front end, since it *is* HML-L1).

Two spellings deliberately differ from ``Type.render()``. ``FunctionType.render()``
and ``PredicateType.render()`` separate domain components with ``*``
(``Function[Real * Real -> Real]``), but ``parser.parse_type`` reads a **comma**
separated domain. Emitting ``render()`` verbatim therefore produces source the compiler
rejects for every arity above one. These printers emit the comma form.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from hamiltonian_lang.ast.nodes import (
    Arg,
    BinOp,
    Call,
    Comparison,
    DistExpr,
    Expr,
    Index,
    Literal,
    LogicalOp,
    Quantifier,
    Ref,
    Span,
    UnaryOp,
)
from hamiltonian_lang.types import (
    BASE_DIMENSIONS,
    ConceptType,
    Dimension,
    DistributionType,
    FunctionType,
    MatrixType,
    PredicateType,
    PropositionType,
    QuantityType,
    RandomVariableType,
    ScalarType,
    SetType,
    TensorType,
    Type,
    VectorType,
    is_dimension_variable,
    parse_scalar_name,
)

from .core import SurfaceParseError, UnsupportedConstruct

__all__ = [
    "Vocab",
    "render_expr",
    "render_expr_at",
    "render_type",
    "render_dimension",
    "render_literal",
    "read_dimension_text",
    "Tok",
    "tokenise",
    "Reader",
]


# ---------------------------------------------------------------------------
# Precedence table -- mirrors parser/__init__.py exactly, including associativity
# ---------------------------------------------------------------------------

_PREC: dict[str, int] = {
    "iff": 1, "implies": 1,
    "or": 2,
    "and": 3,
    "=": 4, "!=": 4, "<": 4, "<=": 4, ">": 4, ">=": 4,
    "+": 5, "-": 5,
    "*": 6, "/": 6, "@": 6,
    "^": 8,
}

#: ``implies``/``iff`` and ``^`` are right-associative in ``parser.parse_implication``
#: and ``parser.parse_power``; comparisons are non-associative (chaining is HML-P230).
#: Getting this wrong is not cosmetic: a printer that treats ``^`` as left-associative
#: turns ``(a ^ b) ^ c`` into ``a ^ b ^ c``, which reads back as ``a ^ (b ^ c)``.
_ASSOC: dict[str, str] = {
    "iff": "right", "implies": "right",
    "or": "left", "and": "left",
    "=": "none", "!=": "none", "<": "none", "<=": "none", ">": "none", ">=": "none",
    "+": "left", "-": "left",
    "*": "left", "/": "left", "@": "left",
    "^": "right",
}

_UNARY_PREC = 7
_PRIMARY_PREC = 10
_QUANTIFIER_PREC = 0

_COMPARISONS = ("=", "!=", "<", "<=", ">", ">=")


@dataclass(frozen=True)
class Vocab:
    """The words that distinguish one linear surface from another."""

    forall: str = "forall"
    exists: str = "exists"
    exists_unique: str = "exists unique"
    true: str = "true"
    false: str = "false"
    conj: str = "and"
    disj: str = "or"
    neg: str = "not"


HML_L1 = Vocab()


def _node_prec(e: Expr) -> int:
    if isinstance(e, BinOp | Comparison | LogicalOp):
        return _PREC[e.op]
    if isinstance(e, UnaryOp):
        return _UNARY_PREC
    if isinstance(e, Quantifier):
        return _QUANTIFIER_PREC
    return _PRIMARY_PREC


def _wrap(child: Expr, parent_prec: int, parent_assoc: str, side: str, vocab: Vocab) -> str:
    text = render_expr(child, vocab)
    cp = _node_prec(child)
    if cp < parent_prec or (cp == parent_prec and parent_assoc != side):
        return f"({text})"
    return text


def render_literal(value: float | int | bool) -> str:
    """One spelling per value, shared by every candidate.

    ``Literal.raw`` is deliberately ignored. It is notation, not content, and using it
    would make a rendering depend on how the *source* happened to spell a number.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return repr(float(value))


def render_expr(e: Expr, vocab: Vocab = HML_L1) -> str:
    if isinstance(e, Literal):
        if isinstance(e.value, bool):
            return vocab.true if e.value else vocab.false
        return render_literal(e.value)

    if isinstance(e, Ref):
        return e.name

    if isinstance(e, UnaryOp):
        operand = _wrap(e.operand, _UNARY_PREC, "right", "right", vocab)
        return f"{vocab.neg} {operand}" if e.op == "not" else f"-{operand}"

    if isinstance(e, BinOp | Comparison | LogicalOp):
        prec = _PREC[e.op]
        assoc = _ASSOC[e.op]
        left = _wrap(e.left, prec, assoc, "left", vocab)
        right = _wrap(e.right, prec, assoc, "right", vocab)
        symbol = {"implies": "=>", "iff": "<=>", "and": vocab.conj, "or": vocab.disj}.get(
            e.op, e.op
        )
        return f"{left} {symbol} {right}"

    if isinstance(e, Call):
        return f"{e.callee}({', '.join(render_expr(a, vocab) for a in e.args)})"

    if isinstance(e, Index):
        base = _wrap(e.base, _PRIMARY_PREC, "left", "left", vocab)
        return f"{base}[{', '.join(render_expr(i, vocab) for i in e.indices)}]"

    if isinstance(e, DistExpr):
        if not e.args:
            return e.family
        args = ", ".join(f"{a.role} := {render_expr(a.value, vocab)}" for a in e.args)
        return f"{e.family}({args})"

    if isinstance(e, Quantifier):
        word = {
            "forall": vocab.forall,
            "exists": vocab.exists,
            "exists_unique": vocab.exists_unique,
        }[e.kind]
        return f"{word} {e.var} : {render_type(e.var_type)} . {render_expr(e.body, vocab)}"

    raise UnsupportedConstruct("infix", f"the expression node {type(e).__name__}")


def render_expr_at(e: Expr, min_prec: int, vocab: Vocab = HML_L1) -> str:
    """Render ``e`` parenthesised if it binds looser than ``min_prec``.

    Used where the grammar enters the expression hierarchy below the top, most notably
    ``check dimension``, whose subject is read at the additive level so that the ``=``
    which may follow introduces a *dimension* and not an equation.
    """
    text = render_expr(e, vocab)
    return f"({text})" if _node_prec(e) < min_prec else text


# ---------------------------------------------------------------------------
# Types and dimensions
# ---------------------------------------------------------------------------


def render_dimension(d: Dimension) -> str:
    """The canonical algebraic spelling. Identical to ``Dimension.render()``.

    Kept as its own function rather than calling ``Dimension.render()`` so that the
    round-trip property is a property of this module and cannot be broken by an
    unrelated change to the display layer.
    """
    if not d.exponents and not d.variables:
        return "Dimensionless"
    terms = list(d.exponents) + list(d.variables)
    num = [(k, v) for k, v in terms if v > 0]
    den = [(k, -v) for k, v in terms if v < 0]

    def term(k: str, v: Fraction) -> str:
        return k if v == 1 else f"{k}^{v}"

    numerator = " * ".join(term(k, v) for k, v in num) or "1"
    if not den:
        return numerator
    denominator = " * ".join(term(k, v) for k, v in den)
    if len(den) > 1:
        denominator = f"({denominator})"
    return f"{numerator} / {denominator}"


def _extent(e: str | int | None) -> str:
    if e is None:
        # `?` appears in `parser.parse_extent` and in the v0 freeze's reserved-token
        # table, but it is absent from the lexer's operator list, so `Vector[Real, ?]`
        # never reaches the parser: it dies at HML-L101. An unknown extent is therefore
        # written by *omission*, which the parser reads back as None.
        raise UnsupportedConstruct("infix", "an explicit '?' extent", "'?' is not a lexable token")
    return str(e)


def render_type(t: Type | None) -> str:
    if t is None:
        raise UnsupportedConstruct("infix", "a missing type")
    if isinstance(t, ScalarType):
        return t.name
    if isinstance(t, PropositionType):
        return "Proposition"
    if isinstance(t, QuantityType):
        return f"Quantity[{render_dimension(t.dimension)}]"
    if isinstance(t, VectorType):
        if t.length is None:
            return f"Vector[{render_type(t.element)}]"
        return f"Vector[{render_type(t.element)}, {_extent(t.length)}]"
    if isinstance(t, MatrixType):
        if t.rows is None and t.cols is None:
            return f"Matrix[{render_type(t.element)}]"
        if t.rows is None:
            raise UnsupportedConstruct(
                "infix", "a Matrix with an unknown row extent and a known column extent"
            )
        if t.cols is None:
            return f"Matrix[{render_type(t.element)}, {_extent(t.rows)}]"
        return f"Matrix[{render_type(t.element)}, {_extent(t.rows)}, {_extent(t.cols)}]"
    if isinstance(t, TensorType):
        if not t.shape:
            raise UnsupportedConstruct("infix", "Tensor with an empty shape")
        dims = ", ".join(_extent(d) for d in t.shape)
        return f"Tensor[{render_type(t.element)}, {dims}]"
    if isinstance(t, SetType):
        return f"Set[{render_type(t.element)}]"
    if isinstance(t, FunctionType):
        # Comma separated, not the '*' that FunctionType.render() emits: the parser
        # reads a comma-separated domain and rejects '*'.
        domain = ", ".join(render_type(d) for d in t.domain)
        return f"Function[{domain} -> {render_type(t.codomain)}]"
    if isinstance(t, PredicateType):
        return f"Predicate[{', '.join(render_type(d) for d in t.domain)}]"
    if isinstance(t, RandomVariableType):
        return f"RandomVariable[{render_type(t.codomain)}]"
    if isinstance(t, DistributionType):
        return f"Distribution[{render_type(t.support)}]"
    if isinstance(t, ConceptType):
        return t.name
    raise UnsupportedConstruct("infix", f"the type {type(t).__name__}")


# ---------------------------------------------------------------------------
# A small ASCII tokeniser and reader, used by candidate B
# ---------------------------------------------------------------------------

_OPERATORS = [
    "<=>", ":=", "->", "=>", "<=", ">=", "!=",
    ":", "~", "|", "@", "^", "+", "-", "*", "/", "=", "<", ">",
    "(", ")", "[", "]", ",", ".",
]

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?")


@dataclass
class Tok:
    kind: str  # ident | number | op | newline | eof
    value: str
    line: int
    col: int

    def is_op(self, *ops: str) -> bool:
        return self.kind == "op" and self.value in ops

    def is_word(self, *words: str) -> bool:
        return self.kind == "ident" and self.value in words


def tokenise(text: str, surface: str, comment: str = "#") -> list[Tok]:
    """ASCII-only tokeniser. Any non-ASCII byte is an error, not a silent pass."""
    toks: list[Tok] = []
    line, col, i = 1, 0, 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            if toks and toks[-1].kind != "newline":
                toks.append(Tok("newline", "\\n", line, col))
            i += 1
            line += 1
            col = 0
            continue
        if ch in " \t\r":
            i += 1
            col += 1
            continue
        if ch == comment:
            while i < n and text[i] != "\n":
                i += 1
                col += 1
            continue
        if not ch.isascii():
            raise SurfaceParseError(surface, f"non-ASCII character {ch!r} at line {line}")
        m = _NUMBER_RE.match(text, i)
        if m and (ch.isdigit() or (ch == "." and i + 1 < n and text[i + 1].isdigit())):
            toks.append(Tok("number", m.group(0), line, col))
            col += len(m.group(0))
            i = m.end()
            continue
        m = _IDENT_RE.match(text, i)
        if m:
            toks.append(Tok("ident", m.group(0), line, col))
            col += len(m.group(0))
            i = m.end()
            continue
        for op in _OPERATORS:
            if text.startswith(op, i):
                toks.append(Tok("op", op, line, col))
                i += len(op)
                col += len(op)
                break
        else:
            raise SurfaceParseError(surface, f"unexpected character {ch!r} at line {line}")
    if toks and toks[-1].kind != "newline":
        toks.append(Tok("newline", "\\n", line, col))
    toks.append(Tok("eof", "", line, col))
    return toks


#: Same bound and the same reason as ``parser.MAX_EXPR_DEPTH``: recursive descent must
#: reject a degenerate nesting rather than raise RecursionError and take the run down.
MAX_DEPTH = 50


class Reader:
    """Precedence-climbing reader over :func:`tokenise` output.

    Deliberately mirrors ``parser/__init__.py`` production for production, so that a
    program accepted by one surface is accepted by the other for the same reasons.
    """

    def __init__(self, toks: list[Tok], surface: str, vocab: Vocab) -> None:
        self.toks = toks
        self.k = 0
        self.surface = surface
        self.vocab = vocab
        self.depth = 0

    # -- token helpers ----------------------------------------------------
    @property
    def cur(self) -> Tok:
        return self.toks[min(self.k, len(self.toks) - 1)]

    def peek(self, n: int = 1) -> Tok:
        return self.toks[min(self.k + n, len(self.toks) - 1)]

    def next(self) -> Tok:
        t = self.cur
        if self.k < len(self.toks) - 1:
            self.k += 1
        return t

    def fail(self, message: str) -> None:
        raise SurfaceParseError(
            self.surface, f"{message} (line {self.cur.line}, found {self.cur.value!r})"
        )

    def accept_op(self, *ops: str) -> Tok | None:
        return self.next() if self.cur.is_op(*ops) else None

    def expect_op(self, op: str, ctx: str) -> Tok:
        if not self.cur.is_op(op):
            self.fail(f"expected {op!r} {ctx}")
        return self.next()

    def accept_word(self, *words: str) -> Tok | None:
        return self.next() if self.cur.is_word(*words) else None

    def expect_ident(self, ctx: str) -> Tok:
        if self.cur.kind != "ident":
            self.fail(f"expected an identifier {ctx}")
        return self.next()

    def skip_newlines(self) -> None:
        while self.cur.kind == "newline":
            self.next()

    def end_line(self, ctx: str) -> None:
        if self.cur.kind == "newline":
            self.next()
            return
        if self.cur.kind == "eof":
            return
        self.fail(f"unexpected token after {ctx}")

    # -- types ------------------------------------------------------------
    def read_type(self) -> Type:
        tok = self.cur
        if tok.kind != "ident":
            self.fail("expected a type")
        self.next()
        head = tok.value
        if not self.cur.is_op("["):
            scalar = parse_scalar_name(head)
            if scalar is not None:
                return scalar
            if head == "Proposition":
                return PropositionType()
            if head == "Dimensionless":
                return QuantityType()
            if head in (
                "Quantity", "Vector", "Matrix", "Tensor", "Set", "Function",
                "Predicate", "RandomVariable", "Distribution",
            ):
                self.fail(f"type constructor {head!r} requires arguments")
            return ConceptType(head)

        self.next()  # '['
        if head == "Quantity":
            dim = self.read_dimension()
            self.expect_op("]", "to close Quantity[...]")
            return QuantityType(dim)
        if head == "Function":
            domain = [self.read_type()]
            while self.accept_op(","):
                domain.append(self.read_type())
            if not self.accept_op("->"):
                self.fail("Function requires '->' between domain and codomain")
            codomain = self.read_type()
            self.expect_op("]", "to close Function[...]")
            return FunctionType(tuple(domain), codomain)

        first = self.read_type()
        if head == "Set":
            self.expect_op("]", "to close Set[...]")
            return SetType(first)
        if head == "RandomVariable":
            self.expect_op("]", "to close RandomVariable[...]")
            return RandomVariableType(first)
        if head == "Distribution":
            self.expect_op("]", "to close Distribution[...]")
            return DistributionType(first)
        if head == "Predicate":
            domain = [first]
            while self.accept_op(","):
                domain.append(self.read_type())
            self.expect_op("]", "to close Predicate[...]")
            return PredicateType(tuple(domain))

        extents: list[str | int | None] = []
        while self.accept_op(","):
            extents.append(self.read_extent())
        self.expect_op("]", f"to close {head}[...]")
        if head == "Vector":
            return VectorType(first, extents[0] if extents else None)
        if head == "Matrix":
            return MatrixType(
                first,
                extents[0] if len(extents) > 0 else None,
                extents[1] if len(extents) > 1 else None,
            )
        if head == "Tensor":
            return TensorType(first, tuple(extents))
        self.fail(f"unknown parameterised type {head!r}")
        raise AssertionError("unreachable")

    def read_extent(self) -> str | int | None:
        if self.cur.kind == "number":
            return int(float(self.next().value))
        if self.cur.kind == "ident":
            return self.next().value
        if self.cur.is_op("?"):
            self.next()
            return None
        # '?' is not in the operator table; the renderer emits it as a bare token.
        self.fail("expected a shape extent")
        raise AssertionError("unreachable")

    def read_dimension(self) -> Dimension:
        dim = self._dim_term()
        while True:
            if self.accept_op("*"):
                dim = dim * self._dim_term()
            elif self.accept_op("/"):
                dim = dim / self._dim_term()
            else:
                return dim

    def _dim_term(self) -> Dimension:
        if self.accept_op("("):
            inner = self.read_dimension()
            self.expect_op(")", "to close a dimension group")
            return self._dim_power(inner)
        if self.cur.kind == "number" and self.cur.value in ("1", "1.0"):
            self.next()
            return Dimension()
        if self.cur.kind != "ident":
            self.fail("expected a base dimension")
        name = self.next().value
        if name == "Dimensionless":
            return self._dim_power(Dimension())
        if name in BASE_DIMENSIONS:
            return self._dim_power(Dimension.of(**{name: 1}))
        if is_dimension_variable(name):
            return self._dim_power(Dimension.variable(name))
        self.fail(f"{name!r} is not a base dimension")
        raise AssertionError("unreachable")

    def _dim_power(self, base: Dimension) -> Dimension:
        if not self.accept_op("^"):
            return base
        negative = bool(self.accept_op("-"))
        if self.cur.kind != "number":
            self.fail("dimension exponents must be rational literals")
        exp = Fraction(self.next().value)
        if self.cur.is_op("/") and self.peek().kind == "number":
            self.next()
            denom = Fraction(self.next().value)
            if denom == 0:
                self.fail("a dimension exponent may not have a zero denominator")
            exp = exp / denom
        return base.power(-exp if negative else exp)

    # -- expressions ------------------------------------------------------
    def read_expr(self) -> Expr:
        self.depth += 1
        try:
            if self.depth > MAX_DEPTH:
                self.fail(f"expression nested more than {MAX_DEPTH} levels deep")
            return self._implication()
        finally:
            self.depth -= 1

    def _implication(self) -> Expr:
        left = self._disjunction()
        if self.cur.is_op("=>", "<=>"):
            op = "implies" if self.next().value == "=>" else "iff"
            return LogicalOp(op=op, left=left, right=self._implication(), span=Span())
        return left

    def _disjunction(self) -> Expr:
        left = self._conjunction()
        while self.cur.is_word(self.vocab.disj):
            self.next()
            left = LogicalOp(op="or", left=left, right=self._conjunction(), span=Span())
        return left

    def _conjunction(self) -> Expr:
        left = self._negation()
        while self.cur.is_word(self.vocab.conj):
            self.next()
            left = LogicalOp(op="and", left=left, right=self._negation(), span=Span())
        return left

    def _negation(self) -> Expr:
        if self.cur.is_word(self.vocab.neg):
            self.next()
            return UnaryOp(op="not", operand=self._negation(), span=Span())
        return self._comparison()

    def _comparison(self) -> Expr:
        left = self.read_additive()
        if self.cur.is_op(*_COMPARISONS):
            op = self.next().value
            node = Comparison(op=op, left=left, right=self.read_additive(), span=Span())
            if self.cur.is_op(*_COMPARISONS):
                self.fail("chained comparisons are not permitted")
            return node
        return left

    def read_additive(self) -> Expr:
        left = self._multiplicative()
        while self.cur.is_op("+", "-"):
            op = self.next().value
            left = BinOp(op=op, left=left, right=self._multiplicative(), span=Span())
        return left

    def _multiplicative(self) -> Expr:
        left = self._unary()
        while self.cur.is_op("*", "/", "@"):
            op = self.next().value
            left = BinOp(op=op, left=left, right=self._unary(), span=Span())
        return left

    def _unary(self) -> Expr:
        if self.cur.is_op("-"):
            self.next()
            return UnaryOp(op="-", operand=self._unary(), span=Span())
        return self._power()

    def _power(self) -> Expr:
        base = self._postfix()
        if self.accept_op("^"):
            return BinOp(op="^", left=base, right=self._unary(), span=Span())
        return base

    def _postfix(self) -> Expr:
        node = self._primary()
        while self.accept_op("["):
            indices = [self.read_expr()]
            while self.accept_op(","):
                indices.append(self.read_expr())
            self.expect_op("]", "to close an index")
            node = Index(base=node, indices=indices, span=Span())
        return node

    def _primary(self) -> Expr:
        tok = self.cur
        if tok.kind == "number":
            self.next()
            raw = tok.value
            value: float | int = int(raw) if raw.isdigit() else float(raw)
            return Literal(value=value, raw=raw, span=Span())
        if tok.is_word(self.vocab.true, self.vocab.false):
            self.next()
            return Literal(value=(tok.value == self.vocab.true), raw=tok.value, span=Span())
        if tok.is_word(self.vocab.forall, self.vocab.exists, self.vocab.exists_unique):
            return self._quantifier()
        if tok.kind == "ident":
            self.next()
            if self.cur.is_op("("):
                return self._call(tok.value)
            return Ref(name=tok.value, span=Span())
        if tok.is_op("("):
            self.next()
            inner = self.read_expr()
            self.expect_op(")", "to close a parenthesised expression")
            return inner
        self.fail("expected an expression")
        raise AssertionError("unreachable")

    def _call(self, callee: str) -> Expr:
        self.expect_op("(", "to open an argument list")
        labelled: list[Arg] = []
        positional: list[Expr] = []
        if not self.cur.is_op(")"):
            while True:
                if self.cur.kind == "ident" and self.peek().is_op(":="):
                    role = self.next().value
                    self.next()
                    labelled.append(Arg(role=role, value=self.read_expr(), span=Span()))
                else:
                    positional.append(self.read_expr())
                if not self.accept_op(","):
                    break
        self.expect_op(")", f"to close the arguments of {callee!r}")
        if labelled and positional:
            self.fail(f"{callee!r} mixes role-labelled and positional arguments")
        if labelled:
            self._reject_repeated_roles(callee, labelled)
            return DistExpr(family=callee, args=labelled, span=Span())
        return Call(callee=callee, args=positional, span=Span())

    def _reject_repeated_roles(self, family: str, args: list[Arg]) -> None:
        seen: set[str] = set()
        for a in args:
            if a.role in seen:
                self.fail(f"role {a.role!r} is given more than once to {family!r}")
            seen.add(a.role)

    def read_dist(self) -> DistExpr:
        if self.cur.kind != "ident":
            self.fail("expected a distribution family")
        family = self.next().value
        if not self.cur.is_op("("):
            return DistExpr(family=family, args=[], span=Span())
        self.next()
        args: list[Arg] = []
        if not self.cur.is_op(")"):
            while True:
                if not (self.cur.kind == "ident" and self.peek().is_op(":=")):
                    self.fail(
                        f"positional arguments are not permitted for distribution {family!r}"
                    )
                role = self.next().value
                self.next()
                args.append(Arg(role=role, value=self.read_expr(), span=Span()))
                if not self.accept_op(","):
                    break
        self.expect_op(")", f"to close the arguments of {family!r}")
        self._reject_repeated_roles(family, args)
        return DistExpr(family=family, args=args, span=Span())

    def _quantifier(self) -> Quantifier:
        word = self.next().value
        kind = {
            self.vocab.forall: "forall",
            self.vocab.exists: "exists",
            self.vocab.exists_unique: "exists_unique",
        }[word]
        if kind == "exists" and self.vocab.exists_unique.startswith(self.vocab.exists + " "):
            # HML-L1 spells the unique quantifier as two words, 'exists unique'.
            tail = self.vocab.exists_unique.split(" ", 1)[1]
            if self.cur.is_word(tail):
                self.next()
                kind = "exists_unique"
        var = self.expect_ident("after a quantifier")
        if not self.accept_op(":"):
            self.fail("a quantified variable requires an explicit type")
        var_type = self.read_type()
        if not self.accept_op("."):
            self.fail("expected '.' between the quantifier binding and its body")
        return Quantifier(
            kind=kind, var=var.value, var_type=var_type, body=self.read_expr(), span=Span()
        )

    def read_name_list(self) -> list[Ref]:
        refs: list[Ref] = []
        while self.cur.kind == "ident":
            refs.append(Ref(name=self.next().value, span=Span()))
            self.accept_op(",")
        if not refs:
            self.fail("expected at least one symbol")
        return refs


def read_dimension_text(text: str, surface: str) -> Dimension:
    """Re-read a rendered dimension string back into a :class:`Dimension`.

    ``CheckStmt.expected`` is a ``str`` in the frozen IR, not a ``Dimension``, so every
    surface has to reconstruct the value before it can print it in its own notation.
    One reader is used by all of them, so they cannot disagree about what the stored
    string means.
    """
    reader = Reader(tokenise(text, surface), surface, HML_L1)
    dim = reader.read_dimension()
    if reader.cur.kind not in ("newline", "eof"):
        reader.fail("trailing tokens after a dimension")
    return dim
