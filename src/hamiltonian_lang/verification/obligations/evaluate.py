"""Exact evaluation, definitional unfolding, and sound interval propagation.

Everything decidable in this package bottoms out here. Two traversals share one set of
unfolding rules:

``evaluate(expr, env, assignment)``
    Computes the value of ``expr`` under a **total** concrete assignment. Exact
    wherever the arithmetic is rational; it marks itself inexact the moment a
    transcendental or a fractional power is involved, and an inexact value may never
    settle an equality.

``interval_of(expr, env)``
    Computes a set guaranteed to *contain* every value ``expr`` can take. Over-
    approximating is always sound here, so every unhandled shape falls back to
    ``UNBOUNDED`` rather than to a guess.

Unfolding is definitional, not inferential
------------------------------------------
``const g : Real = 9.81`` and ``def ke := 0.5 * m * v^2`` are substituted by their own
declared right-hand sides. That is the same rewriting the canonical form already
performs conceptually; it introduces no new axiom. Recursion is capped and cycles are
detected, because a self-referential definition would otherwise unfold forever and an
infinite loop inside a verifier is a failure that looks like a hang.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from fractions import Fraction

from ...ast.nodes import (
    BinOp,
    Call,
    Comparison,
    ConceptDecl,
    Declaration,
    DefineStmt,
    Expr,
    Index,
    Literal,
    LogicalOp,
    Module,
    Quantifier,
    Ref,
    UnaryOp,
    binder_of,
)
from ...semantics import SymbolTable
from ...types import ScalarType, Type
from .domains import UNBOUNDED, Domain, Interval, domain_of_type

__all__ = [
    "Undecidable",
    "Value",
    "Environment",
    "build_environment",
    "evaluate",
    "interval_of",
    "free_names",
    "EXACT_BUILTINS",
    "INEXACT_BUILTINS",
]

#: Relative tolerance below which an inexact comparison is refused rather than decided.
INEXACT_TOLERANCE = 1e-9

MAX_UNFOLD_DEPTH = 32

#: Builtins whose value is exactly representable as a rational for rational input.
EXACT_BUILTINS = frozenset({"abs"})
#: Builtins evaluated in floating point. Their results are marked inexact, which bars
#: them from settling any equality.
INEXACT_BUILTINS = frozenset({"exp", "log", "sqrt", "sin", "cos", "tan"})


class Undecidable(Exception):
    """Raised when a shape is outside the implemented subset.

    The message is propagated verbatim into the ``UNSUPPORTED`` record's ``detail``,
    so it must name the construct, not merely say that something went wrong.
    """


@dataclass(frozen=True)
class Value:
    """A number or a truth value, with an honesty bit.

    ``exact`` is False as soon as a float enters the computation. An inexact ``Value``
    can still refute a claim by a wide margin, but it can never establish an equality:
    ``sqrt(2)^2 == 2`` is false in floating point and true in mathematics, and a
    verifier that cannot tell those apart is worse than no verifier.
    """

    number: Fraction | float | None = None
    boolean: bool | None = None
    exact: bool = True

    @staticmethod
    def of_number(value: Fraction | float, *, exact: bool = True) -> Value:
        return Value(number=value, exact=exact and isinstance(value, Fraction))

    @staticmethod
    def of_bool(value: bool) -> Value:
        return Value(boolean=value)

    def as_number(self) -> Fraction | float:
        if self.number is None:
            raise Undecidable("a truth value was used where a number is required")
        return self.number

    def as_bool(self) -> bool:
        if self.boolean is None:
            raise Undecidable("a number was used where a truth value is required")
        return self.boolean

    def render(self) -> str:
        if self.boolean is not None:
            return "true" if self.boolean else "false"
        n = self.number
        if isinstance(n, Fraction):
            return str(n.numerator) if n.denominator == 1 else f"{n.numerator}/{n.denominator}"
        return repr(n)


@dataclass
class Environment:
    """Everything an evaluation needs that is not in the expression itself."""

    domains: dict[str, Domain] = field(default_factory=dict)
    #: Non-parameterised definitions, unfolded on reference.
    definitions: dict[str, DefineStmt] = field(default_factory=dict)
    #: Parameterised definitions, unfolded on call.
    functions: dict[str, DefineStmt] = field(default_factory=dict)
    #: Names the resolver bound but whose type this package does not model.
    unmodelled: dict[str, str] = field(default_factory=dict)
    #: Declared type per module-level name. Read by the dimensional re-derivation so it
    #: never has to consult ``Expr.type_``, which is the type checker's own answer.
    declared_types: dict[str, Type] = field(default_factory=dict)
    #: Names of ``Bool`` sort. Assignments are carried as rationals so one grid can
    #: serve every domain; this set is what turns 0/1 back into a truth value at the
    #: point of use, so ``b = true`` is compared as a proposition and not as a number.
    bool_names: frozenset[str] = frozenset()

    def domain(self, name: str) -> Domain | None:
        return self.domains.get(name)

    def with_bool(self, name: str) -> Environment:
        return replace(self, bool_names=self.bool_names | {name})

    def value_of(self, name: str, raw: Fraction) -> Value:
        if name in self.bool_names:
            return Value.of_bool(raw != 0)
        return Value.of_number(raw)


def _literal_fraction(value: object) -> Fraction:
    if isinstance(value, bool):
        return Fraction(1 if value else 0)
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise Undecidable(f"the literal {value!r} is not a finite rational")
        return Fraction(value)
    raise Undecidable(f"unsupported literal {value!r}")


def build_environment(module: Module, symbols: SymbolTable | None) -> Environment:
    """Read the module's declarations into domains, pins, and unfoldable definitions."""
    env = Environment()
    for st in module.statements:
        if isinstance(st, Declaration):
            if st.declared_type is not None:
                env.declared_types[st.name] = st.declared_type
            _add_declaration(env, st)
        elif isinstance(st, DefineStmt):
            if st.params:
                env.functions[st.name] = st
            else:
                env.definitions[st.name] = st
        elif isinstance(st, ConceptDecl):
            # Concept members live in a scope one level below the module. A declared
            # ``parameter`` still carries a refinement type, and inside the concept that
            # type bounds it exactly as a module-level declaration would — so its domain
            # is modelled. Transforms and properties are not values and stay unmodelled,
            # which is why an invariant that calls one reports the real reason instead of
            # "unknown name".
            for m in st.members:
                if m.kind == "parameter" and m.declared_type is not None:
                    interval = domain_of_type(m.declared_type)
                    if interval is not None and m.name not in env.domains:
                        env.declared_types.setdefault(m.name, m.declared_type)
                        env.domains[m.name] = Domain(
                            name=m.name,
                            interval=interval,
                            type_name=_type_name(m.declared_type),
                            reason=f"parameter of concept {st.name!r}",
                        )
                        continue
                env.unmodelled.setdefault(
                    m.name, f"{m.name!r} is a {m.kind} of concept {st.name!r}, not a value"
                )
    if symbols is not None:
        for sym in symbols.module_symbols():
            if sym.declared_type is not None:
                env.declared_types.setdefault(sym.name, sym.declared_type)
            if sym.name in env.domains or sym.name in env.definitions:
                continue
            if sym.name in env.functions:
                continue
            interval = domain_of_type(sym.declared_type)
            if interval is None:
                env.unmodelled.setdefault(
                    sym.name,
                    f"{sym.name!r} has type "
                    f"{sym.declared_type.render() if sym.declared_type else 'unknown'}, "
                    f"which has no modelled numeric domain",
                )
            else:
                env.domains[sym.name] = Domain(
                    name=sym.name,
                    interval=interval,
                    type_name=_type_name(sym.declared_type),
                )
    env.bool_names = frozenset(
        name for name, d in env.domains.items() if d.type_name == "Bool"
    )
    return env


def _type_name(t: Type | None) -> str:
    if isinstance(t, ScalarType):
        return t.name
    return "Real"


def _add_declaration(env: Environment, st: Declaration) -> None:
    interval = domain_of_type(st.declared_type)
    if interval is None:
        env.unmodelled[st.name] = (
            f"{st.name!r} is declared "
            f"{st.declared_type.render() if st.declared_type else 'without a type'}, "
            f"which has no modelled numeric domain"
        )
        return
    pinned: Fraction | None = None
    if isinstance(st.value, Literal):
        try:
            pinned = _literal_fraction(st.value.value)
        except Undecidable:
            pinned = None
    env.domains[st.name] = Domain(
        name=st.name,
        interval=Interval.point(pinned) if pinned is not None else interval,
        type_name=_type_name(st.declared_type),
        pinned=pinned,
    )


# ---------------------------------------------------------------------------
# Concrete evaluation
# ---------------------------------------------------------------------------


def evaluate(
    expr: Expr,
    env: Environment,
    assignment: Mapping[str, Fraction] | None = None,
    *,
    _depth: int = 0,
    _unfolding: frozenset[str] = frozenset(),
) -> Value:
    """Evaluate ``expr`` under ``assignment``. Raises :class:`Undecidable` otherwise."""
    if _depth > MAX_UNFOLD_DEPTH:
        raise Undecidable(f"definitional unfolding exceeded depth {MAX_UNFOLD_DEPTH}")
    assign = dict(assignment or {})

    def rec(e: Expr, extra: Mapping[str, Fraction] | None = None, unfolding=_unfolding) -> Value:
        merged = dict(assign)
        if extra:
            merged.update(extra)
        return evaluate(e, env, merged, _depth=_depth + 1, _unfolding=unfolding)

    if isinstance(expr, Literal):
        if isinstance(expr.value, bool):
            return Value.of_bool(expr.value)
        return Value.of_number(_literal_fraction(expr.value))

    if isinstance(expr, Ref):
        return _eval_ref(expr, env, assign, _depth, _unfolding)

    if isinstance(expr, UnaryOp):
        inner = rec(expr.operand)
        if expr.op == "-":
            return Value.of_number(-inner.as_number(), exact=inner.exact)
        if expr.op == "not":
            return Value.of_bool(not inner.as_bool())
        raise Undecidable(f"unary operator {expr.op!r} is outside the subset")

    if isinstance(expr, BinOp):
        return _eval_binop(expr, rec(expr.left), rec(expr.right))

    if isinstance(expr, Comparison):
        return _eval_comparison(expr.op, rec(expr.left), rec(expr.right))

    if isinstance(expr, LogicalOp):
        left = rec(expr.left).as_bool()
        right = rec(expr.right).as_bool()
        table = {
            "and": left and right,
            "or": left or right,
            "implies": (not left) or right,
            "=>": (not left) or right,
            "iff": left == right,
            "<=>": left == right,
        }
        if expr.op not in table:
            raise Undecidable(f"logical operator {expr.op!r} is outside the subset")
        return Value.of_bool(table[expr.op])

    if isinstance(expr, Call):
        return _eval_call(expr, env, assign, _depth, _unfolding)

    if isinstance(expr, Quantifier):
        return _eval_quantifier(expr, env, assign, _depth, _unfolding)

    if isinstance(expr, Index):
        raise Undecidable("indexing is outside the implemented subset")

    raise Undecidable(f"{type(expr).__name__} is outside the implemented subset")


def _eval_ref(
    expr: Ref,
    env: Environment,
    assign: Mapping[str, Fraction],
    depth: int,
    unfolding: frozenset[str],
) -> Value:
    name = expr.name
    if name in assign:
        return env.value_of(name, assign[name])
    domain = env.domain(name)
    if domain is not None and domain.pinned is not None:
        return env.value_of(name, domain.pinned)
    definition = env.definitions.get(name)
    if definition is not None:
        if name in unfolding:
            raise Undecidable(f"definition {name!r} is cyclic; refusing to unfold")
        return evaluate(
            definition.body,
            env,
            assign,
            _depth=depth + 1,
            _unfolding=unfolding | {name},
        )
    if name in env.unmodelled:
        raise Undecidable(env.unmodelled[name])
    raise Undecidable(f"{name!r} is free and no value was supplied")


def _eval_binop(expr: BinOp, left: Value, right: Value) -> Value:
    if expr.op == "@":
        raise Undecidable("the matrix/vector product is outside the implemented subset")
    a, b = left.as_number(), right.as_number()
    exact = left.exact and right.exact
    if expr.op == "+":
        return Value.of_number(a + b, exact=exact)
    if expr.op == "-":
        return Value.of_number(a - b, exact=exact)
    if expr.op == "*":
        return Value.of_number(a * b, exact=exact)
    if expr.op == "/":
        if b == 0:
            raise Undecidable("division by zero in a closed expression")
        return Value.of_number(a / b, exact=exact)
    if expr.op in ("^", "**"):
        if isinstance(b, Fraction) and b.denominator == 1 and abs(b) <= 64:
            n = int(b)
            if n < 0 and a == 0:
                raise Undecidable("zero raised to a negative power")
            return Value.of_number(a**n, exact=exact)
        return Value.of_number(float(a) ** float(b), exact=False)
    raise Undecidable(f"operator {expr.op!r} is outside the subset")


def _eval_comparison(op: str, left: Value, right: Value) -> Value:
    if left.boolean is not None or right.boolean is not None:
        lb, rb = left.as_bool(), right.as_bool()
        if op == "=":
            return Value.of_bool(lb == rb)
        if op == "!=":
            return Value.of_bool(lb != rb)
        raise Undecidable(f"comparison {op!r} is not defined on truth values")
    a, b = left.as_number(), right.as_number()
    exact = left.exact and right.exact
    if not exact:
        scale = max(1.0, abs(float(a)), abs(float(b)))
        if abs(float(a) - float(b)) <= INEXACT_TOLERANCE * scale:
            raise Undecidable(
                "the two sides are within floating-point tolerance; an inexact "
                "computation may not settle this comparison"
            )
    table = {
        "=": a == b,
        "!=": a != b,
        "<": a < b,
        "<=": a <= b,
        ">": a > b,
        ">=": a >= b,
    }
    if op not in table:
        raise Undecidable(f"comparison {op!r} is outside the subset")
    if op in ("=", "!=") and not exact:
        raise Undecidable(
            "an equality decided in floating point is not a proof; the subset admits "
            "exact rational equality only"
        )
    return Value.of_bool(table[op])


def _eval_call(
    expr: Call,
    env: Environment,
    assign: Mapping[str, Fraction],
    depth: int,
    unfolding: frozenset[str],
) -> Value:
    name = expr.callee
    definition = env.functions.get(name)
    if definition is not None:
        if name in unfolding:
            raise Undecidable(f"definition {name!r} is cyclic; refusing to unfold")
        if len(expr.args) != len(definition.params):
            raise Undecidable(
                f"{name} takes {len(definition.params)} argument(s) but was given "
                f"{len(expr.args)}"
            )
        bound: dict[str, Fraction] = dict(assign)
        for (pname, _ptype), arg in zip(definition.params, expr.args, strict=True):
            value = evaluate(arg, env, assign, _depth=depth + 1, _unfolding=unfolding)
            n = value.as_number()
            if not isinstance(n, Fraction):
                raise Undecidable(f"argument {pname!r} did not evaluate to an exact rational")
            bound[pname] = n
        return evaluate(
            definition.body, env, bound, _depth=depth + 1, _unfolding=unfolding | {name}
        )
    if name == "abs":
        if len(expr.args) != 1:
            raise Undecidable("abs takes exactly one argument")
        inner = evaluate(expr.args[0], env, assign, _depth=depth + 1, _unfolding=unfolding)
        magnitude = inner.as_number()
        return Value.of_number(
            -magnitude if magnitude < 0 else magnitude, exact=inner.exact
        )
    if name in INEXACT_BUILTINS:
        if len(expr.args) != 1:
            raise Undecidable(f"{name} takes exactly one argument")
        inner = evaluate(expr.args[0], env, assign, _depth=depth + 1, _unfolding=unfolding)
        fn = getattr(math, name)
        try:
            return Value.of_number(float(fn(float(inner.as_number()))), exact=False)
        except (ValueError, OverflowError) as exc:
            raise Undecidable(f"{name} is undefined at this argument: {exc}") from exc
    raise Undecidable(f"call to {name!r} is outside the implemented subset")


def _eval_quantifier(
    expr: Quantifier,
    env: Environment,
    assign: Mapping[str, Fraction],
    depth: int,
    unfolding: frozenset[str],
) -> Value:
    """Decide a quantifier **only** by exhausting a finite domain.

    ``forall b : Bool . P(b)`` is two cases and is decided. ``forall x : Real . P(x)``
    is not finite and is refused here; refutation by sampling lives in :mod:`.numeric`
    and is never reported as a proof.
    """
    interval = domain_of_type(expr.var_type)
    if interval is None:
        raise Undecidable(
            f"quantifier variable {expr.var!r} has no modelled domain, so it cannot be "
            f"exhausted"
        )
    members = interval.finite_members()
    if members is None:
        raise Undecidable(
            f"the domain of {expr.var!r} "
            f"({expr.var_type.render() if expr.var_type else '?'}) is infinite; "
            f"exhaustion does not apply and sampling is not a proof"
        )
    if expr.kind not in ("forall", "exists", "exists_unique"):
        raise Undecidable(f"quantifier {expr.kind!r} is outside the subset")
    inner_env = env
    if isinstance(expr.var_type, ScalarType) and expr.var_type.name == "Bool":
        inner_env = env.with_bool(expr.var)
    truths: list[bool] = []
    for member in members:
        inner = dict(assign)
        inner[expr.var] = member
        truths.append(
            evaluate(
                expr.body, inner_env, inner, _depth=depth + 1, _unfolding=unfolding
            ).as_bool()
        )
    if expr.kind == "forall":
        return Value.of_bool(all(truths))
    if expr.kind == "exists":
        return Value.of_bool(any(truths))
    return Value.of_bool(sum(1 for t in truths if t) == 1)


# ---------------------------------------------------------------------------
# Interval propagation
# ---------------------------------------------------------------------------


def interval_of(expr: Expr, env: Environment, *, _depth: int = 0) -> Interval:
    """A set containing every value ``expr`` can take. ``UNBOUNDED`` when unknown."""
    if _depth > MAX_UNFOLD_DEPTH:
        return UNBOUNDED
    if isinstance(expr, Literal):
        if isinstance(expr.value, bool):
            return Interval.point(Fraction(1 if expr.value else 0))
        try:
            return Interval.point(_literal_fraction(expr.value))
        except Undecidable:
            return UNBOUNDED
    if isinstance(expr, Ref):
        domain = env.domain(expr.name)
        if domain is not None:
            return domain.interval
        definition = env.definitions.get(expr.name)
        if definition is not None:
            return interval_of(definition.body, env, _depth=_depth + 1)
        return UNBOUNDED
    if isinstance(expr, UnaryOp) and expr.op == "-":
        return _negate(interval_of(expr.operand, env, _depth=_depth + 1))
    if isinstance(expr, BinOp):
        left = interval_of(expr.left, env, _depth=_depth + 1)
        right = interval_of(expr.right, env, _depth=_depth + 1)
        if expr.op == "+":
            return _add(left, right)
        if expr.op == "-":
            return _add(left, _negate(right))
        if expr.op == "*":
            return _multiply(left, right)
        if expr.op == "/":
            return _divide(left, right)
        if expr.op in ("^", "**") and right.is_point() and right.lo is not None:
            exponent = right.lo
            if exponent.denominator == 1 and 0 <= int(exponent) <= 16:
                out = Interval.point(Fraction(1))
                for _ in range(int(exponent)):
                    out = _multiply(out, left)
                return out
        return UNBOUNDED
    if isinstance(expr, Call) and len(expr.args) == 1:
        if expr.callee == "abs":
            return _absolute(interval_of(expr.args[0], env, _depth=_depth + 1))
        if expr.callee == "exp":
            # exp is strictly positive on the whole real line. Recording that keeps
            # `log(exp(t))` inside the totality guard instead of being refused for a
            # fact the checker already knows.
            return Interval(lo=Fraction(0), lo_closed=False)
        if expr.callee == "sqrt":
            return Interval(lo=Fraction(0), lo_closed=True)
    return UNBOUNDED


def _negate(i: Interval) -> Interval:
    if i.empty:
        return i
    return Interval(
        lo=None if i.hi is None else -i.hi,
        lo_closed=i.hi_closed,
        hi=None if i.lo is None else -i.lo,
        hi_closed=i.lo_closed,
        integral=i.integral,
    )


def _add(a: Interval, b: Interval) -> Interval:
    if a.empty or b.empty:
        return Interval(empty=True)
    lo = None if a.lo is None or b.lo is None else a.lo + b.lo
    hi = None if a.hi is None or b.hi is None else a.hi + b.hi
    return Interval(
        lo=lo,
        lo_closed=lo is not None and a.lo_closed and b.lo_closed,
        hi=hi,
        hi_closed=hi is not None and a.hi_closed and b.hi_closed,
        integral=a.integral and b.integral,
    )


def _multiply(a: Interval, b: Interval) -> Interval:
    """Sound product. Falls back to ``UNBOUNDED``, which contains every result.

    Endpoint closedness is widened to closed whenever a corner product is taken. A
    closed interval contains the open one, so this loses precision and never
    soundness.
    """
    if a.empty or b.empty:
        return Interval(empty=True)
    if None not in (a.lo, a.hi, b.lo, b.hi):
        corners = [
            a.lo * b.lo,  # type: ignore[operator]
            a.lo * b.hi,  # type: ignore[operator]
            a.hi * b.lo,  # type: ignore[operator]
            a.hi * b.hi,  # type: ignore[operator]
        ]
        return Interval(
            lo=min(corners),
            lo_closed=True,
            hi=max(corners),
            hi_closed=True,
            integral=a.integral and b.integral,
        )
    # Unbounded on some side: the only fact still worth keeping is a sign.
    a_nonneg = a.lo is not None and a.lo >= 0
    b_nonneg = b.lo is not None and b.lo >= 0
    if a_nonneg and b_nonneg:
        assert a.lo is not None and b.lo is not None
        strict = (a.lo > 0 or not a.lo_closed) and (b.lo > 0 or not b.lo_closed)
        return Interval(
            lo=Fraction(0),
            lo_closed=not strict,
            hi=None,
            hi_closed=False,
            integral=a.integral and b.integral,
        )
    return UNBOUNDED


def _divide(a: Interval, b: Interval) -> Interval:
    if a.empty or b.empty:
        return Interval(empty=True)
    if b.lo is None or b.hi is None:
        return UNBOUNDED
    if b.lo <= 0 <= b.hi:
        return UNBOUNDED  # the divisor may be zero or straddle it
    reciprocal = Interval(
        lo=Fraction(1) / b.hi,
        lo_closed=b.hi_closed,
        hi=Fraction(1) / b.lo,
        hi_closed=b.lo_closed,
    )
    return _multiply(a, reciprocal)


def _absolute(i: Interval) -> Interval:
    if i.empty:
        return i
    if i.lo is not None and i.lo >= 0:
        return i
    if i.hi is not None and i.hi <= 0:
        return _negate(i)
    hi = None
    if i.lo is not None and i.hi is not None:
        hi = max(-i.lo, i.hi)
    return Interval(lo=Fraction(0), lo_closed=True, hi=hi, hi_closed=hi is not None,
                    integral=i.integral)


def free_names(expr: Expr, env: Environment, *, bound: frozenset[str] = frozenset()) -> set[str]:
    """Names still free after definitional unfolding and pinning.

    A pinned constant is not free. A reference to a non-parameterised ``def`` is not
    free either — it is replaced by its body, whose own free names are reported
    instead.
    """
    out: set[str] = set()

    def walk(e: object, scope: frozenset[str], depth: int) -> None:
        if depth > MAX_UNFOLD_DEPTH:
            return
        if isinstance(e, Ref):
            if e.name in scope:
                return
            domain = env.domain(e.name)
            if domain is not None:
                if domain.pinned is None:
                    out.add(e.name)
                return
            definition = env.definitions.get(e.name)
            if definition is not None and e.name not in scope:
                walk(definition.body, scope | {e.name}, depth + 1)
                return
            out.add(e.name)
            return
        if isinstance(e, Call):
            # Special-cased because a call may unfold a user definition, which the
            # generic structural descent below knows nothing about.
            for arg in e.args:
                walk(arg, scope, depth + 1)
            definition = env.functions.get(e.callee)
            if definition is not None and e.callee not in scope:
                inner = scope | {e.callee} | {n for n, _ in definition.params}
                walk(definition.body, inner, depth + 1)
            return

        # Everything else: the binder protocol plus a STRUCTURAL descent.
        #
        # This replaces a whitelist with a branch for `Quantifier` and five operator
        # kinds that fell through **silently** for anything else. When D-026 added four
        # more binders and seven more expression forms, none was added here, so free
        # variables inside them were never reported:
        #
        #     free_names( integral(y, x : Real, 0.0, 1.0) > 0.0 )  ->  []   # y IS free
        #
        # An obligation engine that under-reports free names is not conservatively wrong,
        # it is wrong in the dangerous direction: a name it cannot see is a name it will
        # not require to be pinned before it decides the obligation.
        #
        # Structural descent means the twelfth expression kind is handled the day it is
        # written rather than the day somebody notices.
        bound_name, scoped, unscoped = binder_of(e)
        if bound_name is not None:
            inner = scope | {bound_name}
            for child in scoped:
                walk(child, inner, depth + 1)
        # An integral's limits and a limit's approach point sit OUTSIDE the binding, so a
        # name appearing there is free even when spelled like the bound variable.
        for child in unscoped:
            walk(child, scope, depth + 1)
        return

    walk(expr, bound, 0)
    return out
