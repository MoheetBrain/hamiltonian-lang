"""Candidate D -- constrained JSON / graph.

A node-typed tree with named edges, serialised as JSON with sorted keys. Informed by the
``e_graph_triple`` sketch, with one deliberate and load-bearing departure.

**References are by name, not by node identity.** The triple sketch writes
``_:q1cl refTo _:q1y`` -- an edge straight from a use to its binder. That would hand
candidate D the result of name resolution, which candidates A, B and C all have to earn
by walking scopes. It is precisely the information leak that would invalidate the
tournament, so D writes ``{"node": "reference", "name": "y"}`` and lets the shared
resolver do the same work it does for the other three.

For the same reason D carries no node ids, no ordinals, no depths, no inferred types,
no distribution supports, and no proof obligations. Everything in a D document is
something an author typed.

Shape constraints, enforced on read:

* every object carries a ``node`` discriminator drawn from a closed set;
* no additional keys are tolerated -- an unexpected key is an error, not a comment, so a
  future field cannot be smuggled in and silently ignored;
* numbers keep their JSON kind, so the integer ``1`` and the real ``1.0`` stay distinct
  as they do in the canonical form;
* rational dimension exponents are strings (``"3/2"``), because JSON has no rationals
  and a float exponent would not be exact.
"""

from __future__ import annotations

import json
from fractions import Fraction
from typing import Any

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

from ._infix import read_dimension_text
from .core import (
    BINARY_OPS,
    COMPARISON_OPS,
    DECL_KINDS,
    INFER_QUERIES,
    LAW_ROLES,
    LOGICAL_OPS,
    MEMBER_KINDS,
    QUANTIFIER_KINDS,
    UNARY_OPS,
    SurfaceParseError,
    SyntaxCandidate,
    UnsupportedConstruct,
    validate_supported,
)

__all__ = ["CandidateD", "render_module_d", "D_DOCUMENT_VERSION"]

SURFACE = "D"
D_DOCUMENT_VERSION = "hml-graph-d-1"

_SCALAR_CTORS = frozenset(
    {"Bool", "PositiveNatural", "Natural", "Integer", "Rational", "Real",
     "NonNegativeReal", "PositiveReal", "Probability"}
)


def _fail(message: str) -> None:
    raise SurfaceParseError(SURFACE, message)


def _obj(x: Any, ctx: str) -> dict:
    if not isinstance(x, dict):
        _fail(f"expected an object {ctx}, found {type(x).__name__}")
    return x


def _fields(x: Any, ctx: str, required: tuple[str, ...], optional: tuple[str, ...] = ()) -> dict:
    """Read an object and reject both missing and unexpected keys.

    Tolerating an unknown key is how a surface acquires a private channel: the key
    carries information, nothing complains, and the tournament silently stops comparing
    like with like.
    """
    d = _obj(x, ctx)
    allowed = set(required) | set(optional)
    missing = [k for k in required if k not in d]
    if missing:
        _fail(f"{ctx} is missing {', '.join(sorted(missing))}")
    extra = [k for k in d if k not in allowed]
    if extra:
        _fail(f"{ctx} carries unexpected key(s) {', '.join(sorted(extra))}")
    return d


def _name(x: Any, ctx: str) -> str:
    if not isinstance(x, str) or not x:
        _fail(f"expected a name {ctx}")
    return x  # type: ignore[return-value]


def _choice(x: Any, allowed, ctx: str) -> str:
    value = _name(x, ctx)
    if value not in allowed:
        _fail(f"{value!r} is not a valid {ctx}")
    return value


# ---------------------------------------------------------------------------
# Dimensions and types
# ---------------------------------------------------------------------------


def _dump_dimension(d: Dimension) -> dict[str, list[list[str]]]:
    """A term-for-term mirror of the algebraic form the linear surfaces print.

    ``Mass * Length^2 / Time^2`` becomes numerator ``[["Length","2"],["Mass","1"]]`` and
    denominator ``[["Time","2"]]``: the same terms, the same grouping, the same positive
    exponents. A signed exponent *vector* would have been shorter and is what the IR
    stores, but publishing it would hand candidate D a normalisation -- "the exponent of
    Time is -2" -- that readers of the other three surfaces have to perform themselves.
    That is precisely the kind of asymmetry that would invalidate a tournament.

    Exponents are exact rational strings because JSON has no rationals and ``1/2`` is
    not representable as a float without loss.
    """
    terms = list(d.exponents) + list(d.variables)
    return {
        "numerator": [[k, str(v)] for k, v in terms if v > 0],
        "denominator": [[k, str(-v)] for k, v in terms if v < 0],
    }


def _load_dimension_terms(x: Any, ctx: str) -> Dimension:
    if not isinstance(x, list):
        _fail(f"the {ctx} of a dimension is a list of [name, exponent] pairs")
    acc = Dimension()
    seen: set[str] = set()
    for pair in x:
        if not isinstance(pair, list) or len(pair) != 2:
            _fail(f"a {ctx} term is a [name, exponent] pair")
        name, raw = pair
        name = _name(name, "as a dimension name")
        if name in seen:
            _fail(f"dimension {name!r} appears more than once in the {ctx}")
        seen.add(name)
        if not isinstance(raw, str):
            _fail("a dimension exponent is an exact rational written as a string")
        try:
            exponent = Fraction(raw)
        except (ValueError, ZeroDivisionError):
            _fail(f"{raw!r} is not a rational exponent")
            raise AssertionError from None
        if name in BASE_DIMENSIONS:
            term = Dimension.of(**{name: 1})
        elif is_dimension_variable(name):
            term = Dimension.variable(name)
        else:
            _fail(f"{name!r} is neither a base dimension nor a dimension variable")
            raise AssertionError("unreachable")
        acc = acc * term.power(exponent)
    return acc


def _load_dimension(x: Any) -> Dimension:
    f = _fields(x, "a dimension", ("numerator", "denominator"))
    return _load_dimension_terms(f["numerator"], "numerator") / _load_dimension_terms(
        f["denominator"], "denominator"
    )


def _dump_type(t: Type | None) -> Any:
    if t is None:
        return None
    if isinstance(t, ScalarType):
        return {"ctor": t.name}
    if isinstance(t, PropositionType):
        return {"ctor": "Proposition"}
    if isinstance(t, QuantityType):
        return {"ctor": "Quantity", "dimension": _dump_dimension(t.dimension)}
    if isinstance(t, VectorType):
        return {"ctor": "Vector", "element": _dump_type(t.element), "length": t.length}
    if isinstance(t, MatrixType):
        if t.rows is None and t.cols is not None:
            raise UnsupportedConstruct(
                SURFACE, "a Matrix with an unknown row extent and a known column extent"
            )
        return {
            "ctor": "Matrix", "element": _dump_type(t.element),
            "rows": t.rows, "columns": t.cols,
        }
    if isinstance(t, TensorType):
        if not t.shape or any(d is None for d in t.shape):
            raise UnsupportedConstruct(SURFACE, "a Tensor with an empty or unknown shape")
        return {"ctor": "Tensor", "element": _dump_type(t.element), "shape": list(t.shape)}
    if isinstance(t, SetType):
        return {"ctor": "Set", "element": _dump_type(t.element)}
    if isinstance(t, FunctionType):
        return {
            "ctor": "Function",
            "domain": [_dump_type(d) for d in t.domain],
            "codomain": _dump_type(t.codomain),
        }
    if isinstance(t, PredicateType):
        return {"ctor": "Predicate", "domain": [_dump_type(d) for d in t.domain]}
    if isinstance(t, RandomVariableType):
        return {"ctor": "RandomVariable", "codomain": _dump_type(t.codomain)}
    if isinstance(t, DistributionType):
        return {"ctor": "Distribution", "support": _dump_type(t.support)}
    if isinstance(t, ConceptType):
        return {"ctor": "Concept", "name": t.name}
    raise UnsupportedConstruct(SURFACE, f"the type {type(t).__name__}")


def _load_extent(x: Any, ctx: str) -> str | int | None:
    if x is None:
        return None
    if isinstance(x, bool):
        _fail(f"a boolean is not a shape extent {ctx}")
    if isinstance(x, int):
        return x
    if isinstance(x, str) and x:
        return x
    _fail(f"expected an integer, a name or null {ctx}")
    raise AssertionError("unreachable")


def _load_type(x: Any) -> Type | None:
    if x is None:
        return None
    d = _obj(x, "as a type")
    ctor = _name(d.get("ctor"), "as a type constructor")
    if ctor in _SCALAR_CTORS:
        _fields(x, f"type {ctor}", ("ctor",))
        scalar = parse_scalar_name(ctor)
        if scalar is None:  # pragma: no cover - guarded by _SCALAR_CTORS
            _fail(f"{ctor!r} is not a scalar type")
        return scalar
    if ctor == "Proposition":
        _fields(x, "type Proposition", ("ctor",))
        return PropositionType()
    if ctor == "Quantity":
        f = _fields(x, "type Quantity", ("ctor", "dimension"))
        return QuantityType(_load_dimension(f["dimension"]))
    if ctor == "Vector":
        f = _fields(x, "type Vector", ("ctor", "element", "length"))
        return VectorType(_require_type(f["element"]), _load_extent(f["length"], "as a length"))
    if ctor == "Matrix":
        f = _fields(x, "type Matrix", ("ctor", "element", "rows", "columns"))
        rows = _load_extent(f["rows"], "as a row extent")
        cols = _load_extent(f["columns"], "as a column extent")
        if rows is None and cols is not None:
            _fail("a Matrix with a known column extent needs a known row extent")
        return MatrixType(_require_type(f["element"]), rows, cols)
    if ctor == "Tensor":
        f = _fields(x, "type Tensor", ("ctor", "element", "shape"))
        shape = f["shape"]
        if not isinstance(shape, list) or not shape:
            _fail("a Tensor shape is a non-empty list")
        extents = tuple(_load_extent(s, "in a Tensor shape") for s in shape)
        if any(e is None for e in extents):
            _fail("a Tensor shape may not contain an unknown extent")
        return TensorType(_require_type(f["element"]), extents)
    if ctor == "Set":
        f = _fields(x, "type Set", ("ctor", "element"))
        return SetType(_require_type(f["element"]))
    if ctor == "Function":
        f = _fields(x, "type Function", ("ctor", "domain", "codomain"))
        domain = f["domain"]
        if not isinstance(domain, list) or not domain:
            _fail("a Function domain is a non-empty list")
        return FunctionType(
            tuple(_require_type(d) for d in domain), _require_type(f["codomain"])
        )
    if ctor == "Predicate":
        f = _fields(x, "type Predicate", ("ctor", "domain"))
        domain = f["domain"]
        if not isinstance(domain, list) or not domain:
            _fail("a Predicate domain is a non-empty list")
        return PredicateType(tuple(_require_type(d) for d in domain))
    if ctor == "RandomVariable":
        f = _fields(x, "type RandomVariable", ("ctor", "codomain"))
        return RandomVariableType(_require_type(f["codomain"]))
    if ctor == "Distribution":
        f = _fields(x, "type Distribution", ("ctor", "support"))
        return DistributionType(_require_type(f["support"]))
    if ctor == "Concept":
        f = _fields(x, "type Concept", ("ctor", "name"))
        return ConceptType(_name(f["name"], "as a concept type name"))
    _fail(f"{ctor!r} is not a type constructor")
    raise AssertionError("unreachable")


def _require_type(x: Any) -> Type:
    t = _load_type(x)
    if t is None:
        _fail("a type is required here")
        raise AssertionError("unreachable")
    return t


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------


def _dump_expr(e: Expr) -> Any:
    if isinstance(e, Literal):
        return {"node": "literal", "value": e.value}
    if isinstance(e, Ref):
        return {"node": "reference", "name": e.name}
    if isinstance(e, UnaryOp):
        return {"node": "unary", "operator": e.op, "operand": _dump_expr(e.operand)}
    if isinstance(e, BinOp):
        return {
            "node": "binary", "operator": e.op,
            "left": _dump_expr(e.left), "right": _dump_expr(e.right),
        }
    if isinstance(e, Comparison):
        return {
            "node": "comparison", "operator": e.op,
            "left": _dump_expr(e.left), "right": _dump_expr(e.right),
        }
    if isinstance(e, LogicalOp):
        return {
            "node": "logical", "operator": e.op,
            "left": _dump_expr(e.left), "right": _dump_expr(e.right),
        }
    if isinstance(e, Call):
        return {"node": "call", "callee": e.callee, "arguments": [_dump_expr(a) for a in e.args]}
    if isinstance(e, Index):
        return {
            "node": "index", "base": _dump_expr(e.base),
            "indices": [_dump_expr(i) for i in e.indices],
        }
    if isinstance(e, DistExpr):
        return {
            "node": "distribution",
            "family": e.family,
            "arguments": [{"role": a.role, "value": _dump_expr(a.value)} for a in e.args],
        }
    if isinstance(e, Quantifier):
        return {
            "node": "quantifier",
            "quantifier": e.kind,
            "variable": e.var,
            "variable_type": _dump_type(e.var_type),
            "body": _dump_expr(e.body),
        }
    raise UnsupportedConstruct(SURFACE, f"the expression node {type(e).__name__}")


def _load_expr(x: Any, depth: int = 0) -> Expr:
    if depth > 200:
        _fail("expression nested too deeply")
    d = _obj(x, "as an expression")
    node = _name(d.get("node"), "as an expression discriminator")

    if node == "literal":
        f = _fields(x, "literal", ("node", "value"))
        value = f["value"]
        if isinstance(value, bool):
            return Literal(value=value, raw="true" if value else "false", span=Span())
        if isinstance(value, int | float):
            return Literal(value=value, raw=str(value), span=Span())
        _fail("a literal value is a number or a boolean")
    if node == "reference":
        f = _fields(x, "reference", ("node", "name"))
        return Ref(name=_name(f["name"], "as a reference"), span=Span())
    if node == "unary":
        f = _fields(x, "unary", ("node", "operator", "operand"))
        return UnaryOp(
            op=_choice(f["operator"], UNARY_OPS, "unary operator"),
            operand=_load_expr(f["operand"], depth + 1),
            span=Span(),
        )
    if node in ("binary", "comparison", "logical"):
        f = _fields(x, node, ("node", "operator", "left", "right"))
        left = _load_expr(f["left"], depth + 1)
        right = _load_expr(f["right"], depth + 1)
        if node == "binary":
            return BinOp(
                op=_choice(f["operator"], BINARY_OPS, "binary operator"),
                left=left, right=right, span=Span(),
            )
        if node == "comparison":
            return Comparison(
                op=_choice(f["operator"], COMPARISON_OPS, "comparison operator"),
                left=left, right=right, span=Span(),
            )
        return LogicalOp(
            op=_choice(f["operator"], LOGICAL_OPS, "logical operator"),
            left=left, right=right, span=Span(),
        )
    if node == "call":
        f = _fields(x, "call", ("node", "callee", "arguments"))
        args = f["arguments"]
        if not isinstance(args, list):
            _fail("call arguments are a list")
        return Call(
            callee=_name(f["callee"], "as a callee"),
            args=[_load_expr(a, depth + 1) for a in args],
            span=Span(),
        )
    if node == "index":
        f = _fields(x, "index", ("node", "base", "indices"))
        indices = f["indices"]
        if not isinstance(indices, list) or not indices:
            _fail("an index needs at least one subscript")
        return Index(
            base=_load_expr(f["base"], depth + 1),
            indices=[_load_expr(i, depth + 1) for i in indices],
            span=Span(),
        )
    if node == "distribution":
        return _load_dist(x, depth)
    if node == "quantifier":
        f = _fields(x, "quantifier", ("node", "quantifier", "variable", "variable_type", "body"))
        return Quantifier(
            kind=_choice(f["quantifier"], QUANTIFIER_KINDS, "quantifier"),
            var=_name(f["variable"], "as a quantified variable"),
            var_type=_require_type(f["variable_type"]),
            body=_load_expr(f["body"], depth + 1),
            span=Span(),
        )
    _fail(f"{node!r} is not an expression node")
    raise AssertionError("unreachable")


def _load_dist(x: Any, depth: int = 0) -> DistExpr:
    f = _fields(x, "distribution", ("node", "family", "arguments"))
    if f["node"] != "distribution":
        _fail("expected a distribution node")
    arguments = f["arguments"]
    if not isinstance(arguments, list):
        _fail("distribution arguments are a list")
    args: list[Arg] = []
    seen: set[str] = set()
    family = _name(f["family"], "as a distribution family")
    for item in arguments:
        a = _fields(item, "distribution argument", ("role", "value"))
        role = _name(a["role"], "as a parameter role")
        if role in seen:
            _fail(f"role {role!r} is given more than once to {family!r}")
        seen.add(role)
        args.append(Arg(role=role, value=_load_expr(a["value"], depth + 1), span=Span()))
    return DistExpr(family=family, args=args, span=Span())


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------


def _dump_params(params: list[tuple[str, Type | None]]) -> list[dict]:
    return [{"name": n, "type": _dump_type(t)} for n, t in params]


def _load_params(x: Any, *, require_types: bool) -> list[tuple[str, Type | None]]:
    if not isinstance(x, list):
        _fail("a parameter list is a list")
    out: list[tuple[str, Type | None]] = []
    for item in x:
        f = _fields(item, "parameter", ("name", "type"))
        name = _name(f["name"], "as a parameter name")
        t = _load_type(f["type"])
        if require_types and t is None:
            _fail(f"transform parameter {name!r} needs an explicit type")
        out.append((name, t))
    return out


def _dump_statement(st: Statement) -> Any:
    if isinstance(st, Declaration):
        return {
            "node": "declaration",
            "declaration_kind": st.kind,
            "name": st.name,
            "type": _dump_type(st.declared_type),
            "value": _dump_expr(st.value) if st.value is not None else None,
        }
    if isinstance(st, DefineStmt):
        return {
            "node": "definition",
            "name": st.name,
            "parameters": _dump_params(st.params),
            "type": _dump_type(st.declared_type),
            "body": _dump_expr(st.body),
        }
    if isinstance(st, LawStmt):
        return {
            "node": "law",
            "role": st.role,
            "target": st.target,
            "given": [g.name for g in st.given],
            "distribution": _dump_expr(st.distribution),
        }
    if isinstance(st, AssumeStmt):
        return {"node": "assumption", "proposition": _dump_expr(st.proposition)}
    if isinstance(st, RequireStmt):
        return {"node": "constraint", "proposition": _dump_expr(st.proposition)}
    if isinstance(st, ProveStmt):
        return {"node": "theorem", "proposition": _dump_expr(st.proposition)}
    if isinstance(st, ObjectiveStmt):
        return {
            "node": "objective", "direction": st.direction,
            "expression": _dump_expr(st.expression),
        }
    if isinstance(st, SolveStmt):
        return {"node": "solve", "targets": [t.name for t in st.targets]}
    if isinstance(st, InferStmt):
        return {
            "node": "inference", "query": st.query,
            "targets": [t.name for t in st.targets],
        }
    if isinstance(st, CheckStmt):
        if st.check_kind == "dimension":
            expected = (
                _dump_dimension(read_dimension_text(st.expected, SURFACE))
                if st.expected is not None
                else None
            )
            return {
                "node": "dimension_check",
                "subject": _dump_expr(st.subject),
                "expected": expected,
            }
        return {"node": "check", "subject": _dump_expr(st.subject)}
    if isinstance(st, ConceptDecl):
        return {
            "node": "concept",
            "name": st.name,
            "extends": list(st.extends),
            "members": [
                {
                    "member_kind": m.kind,
                    "name": m.name,
                    "parameters": _dump_params(m.params),
                    "type": _dump_type(m.declared_type),
                    "body": _dump_expr(m.body) if m.body is not None else None,
                }
                for m in st.members
            ],
        }
    raise AssertionError(f"validate_supported let through {type(st).__name__}")


def _load_statement(x: Any) -> Statement:
    d = _obj(x, "as a statement")
    node = _name(d.get("node"), "as a statement discriminator")

    if node == "declaration":
        f = _fields(x, "declaration", ("node", "declaration_kind", "name", "type", "value"))
        return Declaration(
            kind=_choice(f["declaration_kind"], DECL_KINDS, "declaration kind"),
            name=_name(f["name"], "as a declared name"),
            declared_type=_require_type(f["type"]),
            value=_load_expr(f["value"]) if f["value"] is not None else None,
            span=Span(),
        )
    if node == "definition":
        f = _fields(x, "definition", ("node", "name", "parameters", "type", "body"))
        return DefineStmt(
            name=_name(f["name"], "as a definition name"),
            params=_load_params(f["parameters"], require_types=False),
            declared_type=_load_type(f["type"]),
            body=_load_expr(f["body"]),
            span=Span(),
        )
    if node == "law":
        f = _fields(x, "law", ("node", "role", "target", "given", "distribution"))
        given = f["given"]
        if not isinstance(given, list):
            _fail("a conditioning set is a list of names")
        return LawStmt(
            role=_choice(f["role"], LAW_ROLES, "law role"),
            target=_name(f["target"], "as a law target"),
            given=[Ref(name=_name(g, "as a conditioning reference"), span=Span()) for g in given],
            distribution=_load_dist(f["distribution"]),
            span=Span(),
        )
    if node in ("assumption", "constraint", "theorem"):
        f = _fields(x, node, ("node", "proposition"))
        e = _load_expr(f["proposition"])
        if node == "assumption":
            return AssumeStmt(proposition=e, span=Span())
        if node == "constraint":
            return RequireStmt(proposition=e, span=Span())
        return ProveStmt(proposition=e, span=Span())
    if node == "objective":
        f = _fields(x, "objective", ("node", "direction", "expression"))
        return ObjectiveStmt(
            direction=_choice(f["direction"], ("minimise", "maximise"), "objective direction"),
            expression=_load_expr(f["expression"]),
            span=Span(),
        )
    if node == "solve":
        f = _fields(x, "solve", ("node", "targets"))
        targets = f["targets"]
        if not isinstance(targets, list) or not targets:
            _fail("'solve' needs at least one target")
        return SolveStmt(
            targets=[Ref(name=_name(t, "as a solve target"), span=Span()) for t in targets],
            span=Span(),
        )
    if node == "inference":
        f = _fields(x, "inference", ("node", "query", "targets"))
        targets = f["targets"]
        if not isinstance(targets, list) or not targets:
            _fail("'infer' needs at least one target")
        return InferStmt(
            query=_choice(f["query"], INFER_QUERIES, "inference query"),
            targets=[Ref(name=_name(t, "as an infer target"), span=Span()) for t in targets],
            span=Span(),
        )
    if node == "check":
        f = _fields(x, "check", ("node", "subject"))
        return CheckStmt(check_kind="proposition", subject=_load_expr(f["subject"]), span=Span())
    if node == "dimension_check":
        f = _fields(x, "dimension_check", ("node", "subject", "expected"))
        expected = (
            _load_dimension(f["expected"]).render() if f["expected"] is not None else None
        )
        return CheckStmt(
            check_kind="dimension",
            subject=_load_expr(f["subject"]),
            expected=expected,
            span=Span(),
        )
    if node == "concept":
        f = _fields(x, "concept", ("node", "name", "extends", "members"))
        extends = f["extends"]
        members_raw = f["members"]
        if not isinstance(extends, list) or not isinstance(members_raw, list):
            _fail("'extends' and 'members' are lists")
        members: list[ConceptMember] = []
        for item in members_raw:
            m = _fields(
                item, "concept member", ("member_kind", "name", "parameters", "type", "body")
            )
            members.append(
                ConceptMember(
                    kind=_choice(m["member_kind"], MEMBER_KINDS, "concept member kind"),
                    name=_name(m["name"], "as a member name"),
                    params=_load_params(m["parameters"], require_types=True),
                    declared_type=_load_type(m["type"]),
                    body=_load_expr(m["body"]) if m["body"] is not None else None,
                    span=Span(),
                )
            )
        return ConceptDecl(
            name=_name(f["name"], "as a concept name"),
            extends=[_name(b, "as an extended concept") for b in extends],
            members=members,
            span=Span(),
        )
    _fail(f"{node!r} is not a statement node")
    raise AssertionError("unreachable")


def render_module_d(module: Module) -> str:
    validate_supported(module, SURFACE)
    doc = {
        "surface": D_DOCUMENT_VERSION,
        "module": module.name,
        "statements": [
            _dump_statement(st) for st in module.statements if not isinstance(st, ModuleDecl)
        ],
    }
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


class CandidateD(SyntaxCandidate):
    id = "D"
    name = "constrained JSON / graph"
    family = "node-typed tree, named edges, name-based references"

    def render(self, module: Module) -> str:
        return render_module_d(module)

    def parse(self, text: str) -> Module:
        if not text.isascii():
            raise SurfaceParseError(SURFACE, "source is not ASCII")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SurfaceParseError(SURFACE, f"not valid JSON: {exc}") from exc
        f = _fields(doc, "the document", ("surface", "module", "statements"))
        if f["surface"] != D_DOCUMENT_VERSION:
            raise SurfaceParseError(
                SURFACE, f"unknown surface tag {f['surface']!r}; expected {D_DOCUMENT_VERSION!r}"
            )
        statements = f["statements"]
        if not isinstance(statements, list):
            raise SurfaceParseError(SURFACE, "'statements' is a list")
        name = _name(f["module"], "as a module name")
        module = Module(name=name, source_file=f"<candidate-{SURFACE}>", span=Span())
        module.statements.append(ModuleDecl(name=name, span=Span()))
        module.statements.extend(_load_statement(s) for s in statements)
        return module
