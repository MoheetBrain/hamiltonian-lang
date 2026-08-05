"""Candidate C -- prefix / S-expression.

One shape for everything: ``(head . operands)``. Nesting is bracket nesting, so binder
scope is visible without a precedence table -- the property the ``c_sexpr`` sketch in
``examples/candidate_syntaxes`` was written to show.

Three rules keep it unambiguous:

* **Heads are a closed vocabulary.** Every list head is drawn from a fixed set. A user
  symbol never appears in head position: an ordinary function call is ``(call f x)``,
  never ``(f x)``. So no program can be read two ways depending on whether a name
  happens to collide with an operator.
* **Unary minus is ``neg``, not ``-``.** Dispatching ``-`` on arity would work, but it
  makes the arity load-bearing for the *meaning* of the head, which is the kind of
  context-dependence the v0 freeze excludes.
* **An unknown extent is written by omission**, exactly as in the linear surfaces, so
  no candidate carries an extent the others must infer.

Dimensions are transliterated term for term from the same normalised algebraic form the
linear surfaces print: ``Mass * Length^2 / Time^2`` becomes
``(div (mul Mass (pow Length 2)) (pow Time 2))``. An exponent-vector encoding would have
been shorter, but it would hand candidate C a normalisation the other three surfaces
leave to the reader.
"""

from __future__ import annotations

import re
from fractions import Fraction

from hamiltonian_lang.ast.nodes import (
    Arg,
    AssumeStmt,
    BinOp,
    Call,
    CheckStmt,
    Comparison,
    ConceptDecl,
    ConceptMember,
    Declaration,
    DefineStmt,
    DistExpr,
    Expr,
    Index,
    InferStmt,
    LawStmt,
    Literal,
    LogicalOp,
    Module,
    ModuleDecl,
    ObjectiveStmt,
    ProveStmt,
    Quantifier,
    Ref,
    RequireStmt,
    SolveStmt,
    Span,
    Statement,
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

from ._infix import read_dimension_text, render_literal
from .core import (
    DECL_KINDS,
    INFER_QUERIES,
    LAW_ROLES,
    MEMBER_KINDS,
    SurfaceParseError,
    SyntaxCandidate,
    UnsupportedConstruct,
    validate_supported,
)

__all__ = ["CandidateC", "render_module_c", "C_HEADS"]

SURFACE = "C"

#: Absent type / absent body. Not a legal identifier, so it can never collide with a
#: user symbol.
NONE_ATOM = "#none"
TRUE_ATOM = "#t"
FALSE_ATOM = "#f"

_BINARY_HEADS = {
    "+": "+", "-": "-", "*": "*", "/": "/", "^": "^", "@": "@",
}
_COMPARISON_HEADS = {"=": "=", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">="}
_LOGICAL_HEADS = {"and": "and", "or": "or", "=>": "implies", "<=>": "iff"}
_LOGICAL_TAIL = {v: k for k, v in _LOGICAL_HEADS.items()}
_QUANTIFIER_HEADS = {
    "forall": "forall",
    "exists": "exists",
    "exists-unique": "exists_unique",
}
_QUANTIFIER_TAIL = {v: k for k, v in _QUANTIFIER_HEADS.items()}

_TYPE_HEADS = frozenset(
    {"Quantity", "Vector", "Matrix", "Tensor", "Set", "Function", "Predicate",
     "RandomVariable", "Distribution"}
)

#: The complete closed head vocabulary, for the written grammar and for the tests.
C_HEADS = (
    frozenset({"module", "dec", "def", "law", "given", "assume", "require", "prove",
               "check", "check-dim", "objective", "solve", "infer", "concept", "extends"})
    | frozenset(MEMBER_KINDS)
    | frozenset(_BINARY_HEADS) | frozenset(_COMPARISON_HEADS) | frozenset(_LOGICAL_HEADS)
    | frozenset({"neg", "not", "call", "index", "dist"})
    | frozenset(_QUANTIFIER_HEADS)
    | _TYPE_HEADS
    | frozenset({"mul", "div", "pow"})
)

_NUMBER_RE = re.compile(r"\A\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\Z")


# ---------------------------------------------------------------------------
# Reader for the S-expression skeleton
# ---------------------------------------------------------------------------

Sexp = str | list


def read_sexps(text: str) -> list[Sexp]:
    """Tokenise and nest. Raises on unbalanced or non-ASCII input."""
    if not text.isascii():
        raise SurfaceParseError(SURFACE, "source is not ASCII")
    out: list[Sexp] = []
    stack: list[list] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in " \t\r\n":
            i += 1
            continue
        if ch == ";":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "(":
            node: list = []
            (stack[-1] if stack else out).append(node)
            stack.append(node)
            i += 1
            continue
        if ch == ")":
            if not stack:
                raise SurfaceParseError(SURFACE, "unbalanced ')'")
            stack.pop()
            i += 1
            continue
        j = i
        while j < n and text[j] not in " \t\r\n();":
            j += 1
        (stack[-1] if stack else out).append(text[i:j])
        i = j
    if stack:
        raise SurfaceParseError(SURFACE, "unbalanced '(': input ends inside a list")
    return out


def _fail(message: str) -> None:
    raise SurfaceParseError(SURFACE, message)


def _as_list(x: Sexp, ctx: str) -> list:
    if not isinstance(x, list):
        _fail(f"expected a list {ctx}, found the atom {x!r}")
    return x  # type: ignore[return-value]


def _as_atom(x: Sexp, ctx: str) -> str:
    if not isinstance(x, str):
        _fail(f"expected an atom {ctx}, found a list")
    return x  # type: ignore[return-value]


def _head(x: Sexp, ctx: str) -> tuple[str, list]:
    items = _as_list(x, ctx)
    if not items:
        _fail(f"empty list {ctx}")
    return _as_atom(items[0], f"in head position {ctx}"), items[1:]


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------


def _render_exponent(v: Fraction) -> str:
    return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"


def _render_dim_term(name: str, exponent: Fraction) -> str:
    return name if exponent == 1 else f"(pow {name} {_render_exponent(exponent)})"


def render_dimension_c(d: Dimension) -> str:
    if not d.exponents and not d.variables:
        return "Dimensionless"
    terms = list(d.exponents) + list(d.variables)
    num = [(k, v) for k, v in terms if v > 0]
    den = [(k, -v) for k, v in terms if v < 0]

    def group(items: list[tuple[str, Fraction]]) -> str:
        rendered = [_render_dim_term(k, v) for k, v in items]
        if not rendered:
            return "1"
        if len(rendered) == 1:
            return rendered[0]
        return "(mul " + " ".join(rendered) + ")"

    if not den:
        return group(num)
    return f"(div {group(num)} {group(den)})"


def _read_dimension(x: Sexp) -> Dimension:
    if isinstance(x, str):
        if x == "Dimensionless":
            return Dimension()
        if x == "1":
            return Dimension()
        if x in BASE_DIMENSIONS:
            return Dimension.of(**{x: 1})
        if is_dimension_variable(x):
            return Dimension.variable(x)
        _fail(f"{x!r} is not a base dimension")
    head, rest = _head(x, "in a dimension")
    if head == "mul":
        if len(rest) < 2:
            _fail("'mul' needs at least two dimension operands")
        acc = _read_dimension(rest[0])
        for r in rest[1:]:
            acc = acc * _read_dimension(r)
        return acc
    if head == "div":
        if len(rest) != 2:
            _fail("'div' takes exactly two dimension operands")
        return _read_dimension(rest[0]) / _read_dimension(rest[1])
    if head == "pow":
        if len(rest) != 2:
            _fail("'pow' takes a dimension and an exponent")
        base = _read_dimension(rest[0])
        raw = _as_atom(rest[1], "as a dimension exponent")
        try:
            exponent = Fraction(raw)
        except (ValueError, ZeroDivisionError):
            _fail(f"{raw!r} is not a rational exponent")
            raise AssertionError from None
        return base.power(exponent)
    _fail(f"{head!r} is not a dimension operator")
    raise AssertionError("unreachable")


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


def render_type_c(t: Type | None) -> str:
    if t is None:
        return NONE_ATOM
    if isinstance(t, ScalarType):
        return t.name
    if isinstance(t, PropositionType):
        return "Proposition"
    if isinstance(t, QuantityType):
        return f"(Quantity {render_dimension_c(t.dimension)})"
    if isinstance(t, VectorType):
        if t.length is None:
            return f"(Vector {render_type_c(t.element)})"
        return f"(Vector {render_type_c(t.element)} {t.length})"
    if isinstance(t, MatrixType):
        if t.rows is None and t.cols is None:
            return f"(Matrix {render_type_c(t.element)})"
        if t.rows is None:
            raise UnsupportedConstruct(
                SURFACE, "a Matrix with an unknown row extent and a known column extent"
            )
        if t.cols is None:
            return f"(Matrix {render_type_c(t.element)} {t.rows})"
        return f"(Matrix {render_type_c(t.element)} {t.rows} {t.cols})"
    if isinstance(t, TensorType):
        if not t.shape or any(d is None for d in t.shape):
            raise UnsupportedConstruct(SURFACE, "a Tensor with an empty or unknown shape")
        return f"(Tensor {render_type_c(t.element)} " + " ".join(str(d) for d in t.shape) + ")"
    if isinstance(t, SetType):
        return f"(Set {render_type_c(t.element)})"
    if isinstance(t, FunctionType):
        domain = " ".join(render_type_c(d) for d in t.domain)
        return f"(Function ({domain}) {render_type_c(t.codomain)})"
    if isinstance(t, PredicateType):
        return "(Predicate " + " ".join(render_type_c(d) for d in t.domain) + ")"
    if isinstance(t, RandomVariableType):
        return f"(RandomVariable {render_type_c(t.codomain)})"
    if isinstance(t, DistributionType):
        return f"(Distribution {render_type_c(t.support)})"
    if isinstance(t, ConceptType):
        return t.name
    raise UnsupportedConstruct(SURFACE, f"the type {type(t).__name__}")


def _read_extent(x: Sexp) -> str | int:
    atom = _as_atom(x, "as a shape extent")
    if atom.isdigit():
        return int(atom)
    return atom


def _read_type(x: Sexp) -> Type | None:
    if isinstance(x, str):
        if x == NONE_ATOM:
            return None
        scalar = parse_scalar_name(x)
        if scalar is not None:
            return scalar
        if x == "Proposition":
            return PropositionType()
        if x == "Dimensionless":
            return QuantityType()
        if x in _TYPE_HEADS:
            _fail(f"type constructor {x!r} requires arguments")
        return ConceptType(x)
    head, rest = _head(x, "in a type")
    if head == "Quantity":
        if len(rest) != 1:
            _fail("Quantity takes exactly one dimension")
        return QuantityType(_read_dimension(rest[0]))
    if head == "Vector":
        if len(rest) == 1:
            return VectorType(_require_type(rest[0]), None)
        if len(rest) == 2:
            return VectorType(_require_type(rest[0]), _read_extent(rest[1]))
        _fail("Vector takes an element type and at most one extent")
    if head == "Matrix":
        if len(rest) == 1:
            return MatrixType(_require_type(rest[0]), None, None)
        if len(rest) == 2:
            return MatrixType(_require_type(rest[0]), _read_extent(rest[1]), None)
        if len(rest) == 3:
            return MatrixType(
                _require_type(rest[0]), _read_extent(rest[1]), _read_extent(rest[2])
            )
        _fail("Matrix takes an element type and at most two extents")
    if head == "Tensor":
        if len(rest) < 2:
            _fail("Tensor takes an element type and at least one extent")
        return TensorType(_require_type(rest[0]), tuple(_read_extent(e) for e in rest[1:]))
    if head == "Set":
        if len(rest) != 1:
            _fail("Set takes exactly one element type")
        return SetType(_require_type(rest[0]))
    if head == "Function":
        if len(rest) != 2:
            _fail("Function takes a domain list and a codomain")
        domain = _as_list(rest[0], "as a Function domain")
        if not domain:
            _fail("a Function domain may not be empty")
        return FunctionType(tuple(_require_type(d) for d in domain), _require_type(rest[1]))
    if head == "Predicate":
        if not rest:
            _fail("a Predicate domain may not be empty")
        return PredicateType(tuple(_require_type(d) for d in rest))
    if head == "RandomVariable":
        if len(rest) != 1:
            _fail("RandomVariable takes exactly one codomain")
        return RandomVariableType(_require_type(rest[0]))
    if head == "Distribution":
        if len(rest) != 1:
            _fail("Distribution takes exactly one support type")
        return DistributionType(_require_type(rest[0]))
    _fail(f"{head!r} is not a type constructor")
    raise AssertionError("unreachable")


def _require_type(x: Sexp) -> Type:
    t = _read_type(x)
    if t is None:
        _fail("a type is required here")
        raise AssertionError("unreachable")
    return t


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------


def render_expr_c(e: Expr) -> str:
    if isinstance(e, Literal):
        if isinstance(e.value, bool):
            return TRUE_ATOM if e.value else FALSE_ATOM
        return render_literal(e.value)
    if isinstance(e, Ref):
        return e.name
    if isinstance(e, UnaryOp):
        head = "neg" if e.op == "-" else "not"
        return f"({head} {render_expr_c(e.operand)})"
    if isinstance(e, BinOp | Comparison):
        return f"({e.op} {render_expr_c(e.left)} {render_expr_c(e.right)})"
    if isinstance(e, LogicalOp):
        return f"({_LOGICAL_TAIL[e.op]} {render_expr_c(e.left)} {render_expr_c(e.right)})"
    if isinstance(e, Call):
        args = "".join(f" {render_expr_c(a)}" for a in e.args)
        return f"(call {e.callee}{args})"
    if isinstance(e, Index):
        indices = "".join(f" {render_expr_c(i)}" for i in e.indices)
        return f"(index {render_expr_c(e.base)}{indices})"
    if isinstance(e, DistExpr):
        args = "".join(f" ({a.role} {render_expr_c(a.value)})" for a in e.args)
        return f"(dist {e.family}{args})"
    if isinstance(e, Quantifier):
        binder = f"({e.var} {render_type_c(e.var_type)})"
        return f"({_QUANTIFIER_TAIL[e.kind]} {binder} {render_expr_c(e.body)})"
    raise UnsupportedConstruct(SURFACE, f"the expression node {type(e).__name__}")


def _read_expr(x: Sexp, depth: int = 0) -> Expr:
    if depth > 200:
        _fail("expression nested too deeply")
    if isinstance(x, str):
        if x == TRUE_ATOM:
            return Literal(value=True, raw="true", span=Span())
        if x == FALSE_ATOM:
            return Literal(value=False, raw="false", span=Span())
        if _NUMBER_RE.match(x):
            value: float | int = int(x) if x.isdigit() else float(x)
            return Literal(value=value, raw=x, span=Span())
        if not x[:1].isalpha() and x[:1] != "_":
            _fail(f"{x!r} is not a reference, a number or a boolean")
        return Ref(name=x, span=Span())

    head, rest = _head(x, "in an expression")

    if head in _BINARY_HEADS:
        if len(rest) != 2:
            _fail(f"{head!r} takes exactly two operands")
        return BinOp(
            op=head, left=_read_expr(rest[0], depth + 1),
            right=_read_expr(rest[1], depth + 1), span=Span(),
        )
    if head in _COMPARISON_HEADS:
        if len(rest) != 2:
            _fail(f"{head!r} takes exactly two operands")
        return Comparison(
            op=head, left=_read_expr(rest[0], depth + 1),
            right=_read_expr(rest[1], depth + 1), span=Span(),
        )
    if head in _LOGICAL_HEADS:
        if len(rest) != 2:
            _fail(f"{head!r} takes exactly two operands")
        return LogicalOp(
            op=_LOGICAL_HEADS[head], left=_read_expr(rest[0], depth + 1),
            right=_read_expr(rest[1], depth + 1), span=Span(),
        )
    if head in ("neg", "not"):
        if len(rest) != 1:
            _fail(f"{head!r} takes exactly one operand")
        return UnaryOp(
            op="-" if head == "neg" else "not",
            operand=_read_expr(rest[0], depth + 1), span=Span(),
        )
    if head == "call":
        if not rest:
            _fail("'call' needs a callee")
        return Call(
            callee=_as_atom(rest[0], "as a callee"),
            args=[_read_expr(a, depth + 1) for a in rest[1:]],
            span=Span(),
        )
    if head == "index":
        if len(rest) < 2:
            _fail("'index' needs a base and at least one subscript")
        return Index(
            base=_read_expr(rest[0], depth + 1),
            indices=[_read_expr(i, depth + 1) for i in rest[1:]],
            span=Span(),
        )
    if head == "dist":
        return _read_dist(x, depth)
    if head in _QUANTIFIER_HEADS:
        if len(rest) != 2:
            _fail(f"{head!r} takes a binder and a body")
        binder = _as_list(rest[0], "as a quantifier binder")
        if len(binder) != 2:
            _fail("a quantifier binder is (name type)")
        return Quantifier(
            kind=_QUANTIFIER_HEADS[head],
            var=_as_atom(binder[0], "as a quantified variable"),
            var_type=_require_type(binder[1]),
            body=_read_expr(rest[1], depth + 1),
            span=Span(),
        )
    _fail(f"{head!r} is not an expression operator")
    raise AssertionError("unreachable")


def _read_dist(x: Sexp, depth: int = 0) -> DistExpr:
    head, rest = _head(x, "in a distribution")
    if head != "dist":
        _fail(f"expected a (dist ...) form, found {head!r}")
    if not rest:
        _fail("'dist' needs a family name")
    family = _as_atom(rest[0], "as a distribution family")
    args: list[Arg] = []
    seen: set[str] = set()
    for item in rest[1:]:
        pair = _as_list(item, "as a role-labelled argument")
        if len(pair) != 2:
            _fail("a distribution argument is (role value)")
        role = _as_atom(pair[0], "as a parameter role")
        if role in seen:
            _fail(f"role {role!r} is given more than once to {family!r}")
        seen.add(role)
        args.append(Arg(role=role, value=_read_expr(pair[1], depth + 1), span=Span()))
    return DistExpr(family=family, args=args, span=Span())


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------


def _render_params(params: list[tuple[str, Type | None]]) -> str:
    return "(" + " ".join(
        f"({n})" if t is None else f"({n} {render_type_c(t)})" for n, t in params
    ) + ")"


def _read_params(x: Sexp, *, require_types: bool) -> list[tuple[str, Type | None]]:
    out: list[tuple[str, Type | None]] = []
    for item in _as_list(x, "as a parameter list"):
        pair = _as_list(item, "as a parameter")
        if len(pair) == 1:
            if require_types:
                _fail(f"transform parameter {pair[0]!r} needs an explicit type")
            out.append((_as_atom(pair[0], "as a parameter name"), None))
        elif len(pair) == 2:
            out.append((_as_atom(pair[0], "as a parameter name"), _require_type(pair[1])))
        else:
            _fail("a parameter is (name) or (name type)")
    return out


def render_statement_c(st: Statement, indent: str = "  ") -> str:
    if isinstance(st, ModuleDecl):
        return ""  # the module name is the head of the whole document
    if isinstance(st, Declaration):
        parts = [st.kind, st.name, render_type_c(st.declared_type)]
        if st.value is not None:
            parts.append(render_expr_c(st.value))
        return f"{indent}(dec " + " ".join(parts) + ")"
    if isinstance(st, DefineStmt):
        return (
            f"{indent}(def {st.name} {_render_params(st.params)} "
            f"{render_type_c(st.declared_type)} {render_expr_c(st.body)})"
        )
    if isinstance(st, LawStmt):
        given = "(given" + "".join(f" {g.name}" for g in st.given) + ")"
        return (
            f"{indent}(law {st.role} {st.target} {given} "
            f"{render_expr_c(st.distribution)})"
        )
    if isinstance(st, AssumeStmt):
        return f"{indent}(assume {render_expr_c(st.proposition)})"
    if isinstance(st, RequireStmt):
        return f"{indent}(require {render_expr_c(st.proposition)})"
    if isinstance(st, ProveStmt):
        return f"{indent}(prove {render_expr_c(st.proposition)})"
    if isinstance(st, ObjectiveStmt):
        return f"{indent}(objective {st.direction} {render_expr_c(st.expression)})"
    if isinstance(st, SolveStmt):
        return f"{indent}(solve " + " ".join(t.name for t in st.targets) + ")"
    if isinstance(st, InferStmt):
        return (
            f"{indent}(infer {st.query} " + " ".join(t.name for t in st.targets) + ")"
        )
    if isinstance(st, CheckStmt):
        if st.check_kind == "dimension":
            body = f"(check-dim {render_expr_c(st.subject)}"
            if st.expected is not None:
                body += f" {render_dimension_c(_dimension_from_text(st.expected))}"
            return f"{indent}{body})"
        return f"{indent}(check {render_expr_c(st.subject)})"
    if isinstance(st, ConceptDecl):
        head = f"{indent}(concept {st.name} (extends" + "".join(
            f" {b}" for b in st.extends
        ) + ")"
        lines = [head]
        for m in st.members:
            lines.append(
                f"{indent}  ({m.kind} {m.name} {_render_params(m.params)} "
                f"{render_type_c(m.declared_type)} "
                f"{render_expr_c(m.body) if m.body is not None else NONE_ATOM})"
            )
        lines[-1] += ")"
        return "\n".join(lines)
    raise AssertionError(f"validate_supported let through {type(st).__name__}")


def _dimension_from_text(text: str) -> Dimension:
    """Re-read ``CheckStmt.expected``, which the frozen IR stores as a rendered string."""
    try:
        return read_dimension_text(text, SURFACE)
    except SurfaceParseError as exc:  # pragma: no cover - `expected` always comes from render()
        raise UnsupportedConstruct(SURFACE, f"the dimension text {text!r}", str(exc)) from exc


def render_module_c(module: Module) -> str:
    validate_supported(module, SURFACE)
    body = [
        render_statement_c(st)
        for st in module.statements
        if not isinstance(st, ModuleDecl)
    ]
    lines = [f"(module {module.name}", *body]
    return "\n".join(lines) + ")\n"


def _read_statement(x: Sexp) -> Statement:
    head, rest = _head(x, "in a statement")

    if head == "dec":
        if len(rest) not in (3, 4):
            _fail("(dec kind name type [value])")
        kind = _as_atom(rest[0], "as a declaration kind")
        if kind not in DECL_KINDS:
            _fail(f"{kind!r} is not a declaration kind")
        return Declaration(
            kind=kind,
            name=_as_atom(rest[1], "as a declared name"),
            declared_type=_require_type(rest[2]),
            value=_read_expr(rest[3]) if len(rest) == 4 else None,
            span=Span(),
        )
    if head == "def":
        if len(rest) != 4:
            _fail("(def name (params) type body)")
        return DefineStmt(
            name=_as_atom(rest[0], "as a definition name"),
            params=_read_params(rest[1], require_types=False),
            declared_type=_read_type(rest[2]),
            body=_read_expr(rest[3]),
            span=Span(),
        )
    if head == "law":
        if len(rest) != 4:
            _fail("(law role target (given ...) dist)")
        role = _as_atom(rest[0], "as a law role")
        if role not in LAW_ROLES:
            _fail(f"{role!r} is not a law role")
        given_head, given_rest = _head(rest[2], "as a conditioning set")
        if given_head != "given":
            _fail("the third element of a law is a (given ...) list")
        return LawStmt(
            role=role,
            target=_as_atom(rest[1], "as a law target"),
            given=[Ref(name=_as_atom(g, "as a conditioning reference"), span=Span())
                   for g in given_rest],
            distribution=_read_dist(rest[3]),
            span=Span(),
        )
    if head in ("assume", "require", "prove", "check"):
        if len(rest) != 1:
            _fail(f"({head} proposition)")
        e = _read_expr(rest[0])
        if head == "assume":
            return AssumeStmt(proposition=e, span=Span())
        if head == "require":
            return RequireStmt(proposition=e, span=Span())
        if head == "prove":
            return ProveStmt(proposition=e, span=Span())
        return CheckStmt(check_kind="proposition", subject=e, span=Span())
    if head == "check-dim":
        if len(rest) not in (1, 2):
            _fail("(check-dim expr [dimension])")
        expected = _read_dimension(rest[1]).render() if len(rest) == 2 else None
        return CheckStmt(
            check_kind="dimension", subject=_read_expr(rest[0]), expected=expected, span=Span()
        )
    if head == "objective":
        if len(rest) != 2:
            _fail("(objective direction expr)")
        direction = _as_atom(rest[0], "as an objective direction")
        if direction not in ("minimise", "maximise"):
            _fail(f"{direction!r} is not an objective direction")
        return ObjectiveStmt(direction=direction, expression=_read_expr(rest[1]), span=Span())
    if head == "solve":
        if not rest:
            _fail("(solve target ...) needs at least one target")
        return SolveStmt(
            targets=[Ref(name=_as_atom(t, "as a solve target"), span=Span()) for t in rest],
            span=Span(),
        )
    if head == "infer":
        if len(rest) < 2:
            _fail("(infer query target ...)")
        query = _as_atom(rest[0], "as an inference query")
        if query not in INFER_QUERIES:
            _fail(f"{query!r} is not an inference query")
        return InferStmt(
            query=query,
            targets=[Ref(name=_as_atom(t, "as an infer target"), span=Span()) for t in rest[1:]],
            span=Span(),
        )
    if head == "concept":
        if len(rest) < 2:
            _fail("(concept Name (extends ...) member ...)")
        extends_head, extends_rest = _head(rest[1], "as an extends list")
        if extends_head != "extends":
            _fail("the second element of a concept is an (extends ...) list")
        members: list[ConceptMember] = []
        for item in rest[2:]:
            mkind, mrest = _head(item, "as a concept member")
            if mkind not in MEMBER_KINDS:
                _fail(f"{mkind!r} is not a concept member kind")
            if len(mrest) != 4:
                _fail("(memberkind name (params) type body)")
            body_sexp = mrest[3]
            members.append(
                ConceptMember(
                    kind=mkind,
                    name=_as_atom(mrest[0], "as a member name"),
                    params=_read_params(mrest[1], require_types=True),
                    declared_type=_read_type(mrest[2]),
                    body=None if body_sexp == NONE_ATOM else _read_expr(body_sexp),
                    span=Span(),
                )
            )
        return ConceptDecl(
            name=_as_atom(rest[0], "as a concept name"),
            extends=[_as_atom(b, "as an extended concept") for b in extends_rest],
            members=members,
            span=Span(),
        )
    _fail(f"{head!r} does not begin a statement")
    raise AssertionError("unreachable")


class CandidateC(SyntaxCandidate):
    id = "C"
    name = "prefix / S-expression"
    family = "fully bracketed prefix notation with a closed head vocabulary"

    def render(self, module: Module) -> str:
        return render_module_c(module)

    def parse(self, text: str) -> Module:
        forms = read_sexps(text)
        if len(forms) != 1:
            raise SurfaceParseError(
                SURFACE, f"expected exactly one top-level form, found {len(forms)}"
            )
        head, rest = _head(forms[0], "at the top level")
        if head != "module":
            raise SurfaceParseError(SURFACE, f"the top-level form is (module ...), not {head!r}")
        if not rest:
            raise SurfaceParseError(SURFACE, "(module ...) needs a name")
        name = _as_atom(rest[0], "as a module name")
        module = Module(name=name, source_file=f"<candidate-{SURFACE}>", span=Span())
        module.statements.append(ModuleDecl(name=name, span=Span()))
        module.statements.extend(_read_statement(s) for s in rest[1:])
        return module
