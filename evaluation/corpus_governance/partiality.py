"""A conservative AST partiality scanner. A corpus gate, not a change to HML semantics.

Why this exists
---------------
The previous guard detected division by a **bare binder** and nothing else. It therefore
admitted `def pressure : ... := force / area` where `area` is a module-level
`Quantity[Length^2]` — a type that admits zero. That task was withdrawn rather than
guarded, because `require area != 0` does not even compile: HML-D502 refuses to compare a
dimensioned quantity to a dimensionless `0`. A guard that misses the case which actually
bit the corpus is not a guard.

What it does
------------
It walks every expression position of a module, carries the declared type of every name in
scope, follows definition dependencies (so partiality one or two `def`s deep is found), and
for each partial operation asks whether the operand's safety is *established* — by its
declared type, by a literal, or by an explicit in-scope `assume`/`require` naming it.

What it deliberately does not do
--------------------------------
It does not prove anything. It answers "is safety established here?" and fails closed when
it cannot tell. A conservative rejection costs one authored task; a missed partiality costs
the validity of every measurement taken with it.

The scanner never proposes a repair, because two of the plausible repairs are wrong: adding
`require x != 0` silently changes the mathematics the model is asked to encode, and for a
dimensioned quantity it does not compile at all. The remedy is to narrow a type or
reformulate the task, and that is an authoring decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "Establishment",
    "PartialityRisk",
    "PartialityReport",
    "Verdict",
    "scan_module",
    "scan_source",
    "PARTIAL_CALLS",
    "UnsupportedStatement",
]

#: Callee name -> what its argument must satisfy for the call to be defined.
#: `tan` is listed with `IMPOSSIBLE`: its partiality is at pi/2 + k*pi, which no HML
#: predicate in the frozen subset can exclude, so it can never be established.
PARTIAL_CALLS: dict[str, str] = {
    "sqrt": "nonnegative",
    "log": "positive",
    "ln": "positive",
    "log2": "positive",
    "log10": "positive",
    "tan": "impossible",
    "cot": "impossible",
    "sec": "impossible",
    "csc": "impossible",
    "asin": "unit_interval",
    "acos": "unit_interval",
    "arcsin": "unit_interval",
    "arccos": "unit_interval",
    "acosh": "at_least_one",
    "atanh": "open_unit_interval",
}

#: Scalar types whose inhabitants are all strictly positive.
_POSITIVE_SCALARS = frozenset({"PositiveReal", "PositiveNatural"})
#: Scalar types that admit zero but no negative value.
_NONNEGATIVE_SCALARS = frozenset(
    {"NonNegativeReal", "Natural", "Probability", "PValue", "PosteriorProbability"}
)


class Establishment(StrEnum):
    """What is known about a value. Never a guess: `UNKNOWN` is the honest default."""

    POSITIVE = "POSITIVE"
    NONNEGATIVE = "NONNEGATIVE"
    NONZERO = "NONZERO"
    UNKNOWN = "UNKNOWN"


class UnsupportedStatement(RuntimeError):
    """A statement kind with no partiality branch. Fails closed, never silently."""


class Verdict(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


@dataclass(frozen=True)
class PartialityRisk:
    """One unestablished partial operation, with the path that reaches it."""

    operation: str
    reason: str
    path: tuple[str, ...]
    unguardable: bool = False

    def render(self) -> str:
        arrow = "\n  -> ".join(self.path)
        tail = ("\n  -> UNGUARDABLE: a dimensioned quantity cannot be compared to a "
                "dimensionless 0 (HML-D502)" if self.unguardable else "")
        return f"{arrow}\n  -> {self.reason}{tail}"


@dataclass(frozen=True)
class PartialityReport:
    task_id: str
    risks: tuple[PartialityRisk, ...] = ()
    inspected: tuple[str, ...] = ()
    #: How many statements the walk actually reached. Without it, ACCEPT could not
    #: distinguish "no partial operation" from "never looked" -- and a module whose only
    #: division sat inside an unwalked `concept` block printed the same line as a clean one.
    statements_walked: int = 0

    @property
    def verdict(self) -> Verdict:
        return Verdict.REJECT if self.risks else Verdict.ACCEPT

    @property
    def admissible(self) -> bool:
        return not self.risks

    def render(self) -> str:
        if not self.risks:
            return (f"{self.task_id}: ACCEPT — {self.statements_walked} statement(s) "
                    f"walked, {len(self.inspected)} partial-operation site(s) inspected, "
                    f"all established")
        body = "\n\n".join(r.render() for r in self.risks)
        return f"{self.task_id}: REJECT — {len(self.risks)} unestablished risk(s)\n\n{body}"


# --- the environment ------------------------------------------------------------------


@dataclass
class _Env:
    """Declared types, definition bodies, and facts established by visible statements."""

    types: dict[str, Any] = field(default_factory=dict)
    consts: dict[str, Any] = field(default_factory=dict)
    defs: dict[str, Any] = field(default_factory=dict)
    positive: set[str] = field(default_factory=set)
    nonzero: set[str] = field(default_factory=set)
    nonnegative: set[str] = field(default_factory=set)

    def child(self) -> _Env:
        return _Env(dict(self.types), dict(self.consts), dict(self.defs),
                    set(self.positive), set(self.nonzero), set(self.nonnegative))


def _scalar_name(declared: Any) -> str | None:
    return getattr(declared, "name", None)


def _is_dimensioned(declared: Any) -> bool:
    from hamiltonian_lang.types import QuantityType
    return isinstance(declared, QuantityType)


def _from_type(declared: Any) -> Establishment:
    """What a declared type alone establishes. A `Quantity` establishes nothing."""
    name = _scalar_name(declared)
    if name in _POSITIVE_SCALARS:
        return Establishment.POSITIVE
    if name in _NONNEGATIVE_SCALARS:
        return Establishment.NONNEGATIVE
    return Establishment.UNKNOWN


def _collect_facts(env: _Env, proposition: Any) -> None:
    """Read `x != 0`, `x > 0`, `x >= 1`, `0 < x` and conjunctions of them.

    Deliberately shallow. A fact is only recorded when a *named* operand is compared to a
    *literal*, because anything cleverer would be inferring rather than reading.
    """
    from hamiltonian_lang.ast.nodes import Comparison, Literal, LogicalOp, Ref

    if isinstance(proposition, LogicalOp) and proposition.op == "and":
        _collect_facts(env, proposition.left)
        _collect_facts(env, proposition.right)
        return
    if not isinstance(proposition, Comparison):
        return

    left, right, op = proposition.left, proposition.right, proposition.op
    if isinstance(right, Ref) and isinstance(left, Literal):
        left, right, op = right, left, {"<": ">", ">": "<", "<=": ">=", ">=": "<="}.get(op, op)
    if not (isinstance(left, Ref) and isinstance(right, Literal)):
        return

    name, value = left.name, right.value
    if op == "!=" and value == 0:
        env.nonzero.add(name)
    elif op == ">" and value >= 0:
        env.positive.add(name)
        env.nonzero.add(name)
    elif op == ">=" and value > 0:
        env.positive.add(name)
        env.nonzero.add(name)
    elif op == ">=" and value == 0:
        env.nonnegative.add(name)


def _establish(expr: Any, env: _Env, depth: int = 0) -> Establishment:
    """What is established about `expr`. Compositional, conservative, never optimistic."""
    from hamiltonian_lang.ast.nodes import BinOp, Call, Literal, Ref, UnaryOp

    if expr is None or depth > 24:
        return Establishment.UNKNOWN

    if isinstance(expr, Literal):
        value = expr.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return Establishment.UNKNOWN
        if value > 0:
            return Establishment.POSITIVE
        if value == 0:
            return Establishment.NONNEGATIVE  # zero: established, and established as bad
        return Establishment.NONZERO

    if isinstance(expr, Ref):
        name = expr.name
        if name in env.positive:
            return Establishment.POSITIVE
        from_type = _from_type(env.types.get(name))
        if from_type is Establishment.POSITIVE:
            return from_type
        if name in env.nonzero:
            return Establishment.NONZERO
        if name in env.consts:  # a const's initialiser is part of the object
            return _establish(env.consts[name], env, depth + 1)
        if name in env.defs and not env.defs[name].params:
            return _establish(env.defs[name].body, env.child(), depth + 1)
        if name in env.nonnegative:
            return Establishment.NONNEGATIVE
        return from_type

    if isinstance(expr, UnaryOp) and expr.op == "-":
        inner = _establish(expr.operand, env, depth + 1)
        return Establishment.NONZERO if inner in (
            Establishment.POSITIVE, Establishment.NONZERO) else Establishment.UNKNOWN

    if isinstance(expr, BinOp):
        left = _establish(expr.left, env, depth + 1)
        right = _establish(expr.right, env, depth + 1)
        pos = (Establishment.POSITIVE,)
        nz = (Establishment.POSITIVE, Establishment.NONZERO)
        if expr.op == "*":
            if left in pos and right in pos:
                return Establishment.POSITIVE
            if left in nz and right in nz:
                return Establishment.NONZERO
        elif expr.op == "/":
            if left in pos and right in pos:
                return Establishment.POSITIVE
            if left in nz and right in nz:
                return Establishment.NONZERO
        elif expr.op == "+":
            if left in pos and right in pos:
                return Establishment.POSITIVE
            if left in pos and right is Establishment.NONNEGATIVE:
                return Establishment.POSITIVE
            if right in pos and left is Establishment.NONNEGATIVE:
                return Establishment.POSITIVE
        elif expr.op == "^":
            if left in pos:
                return Establishment.POSITIVE
            if left in nz:
                return Establishment.NONZERO
        return Establishment.UNKNOWN

    if isinstance(expr, Call):
        callee = expr.callee
        if callee in {"exp", "cosh"}:
            return Establishment.POSITIVE
        if callee == "sqrt":
            return (Establishment.POSITIVE
                    if _establish(expr.args[0] if expr.args else None, env, depth + 1)
                    is Establishment.POSITIVE else Establishment.UNKNOWN)
        if callee in env.defs:
            return Establishment.UNKNOWN  # the body's safety is checked, not its sign
    return Establishment.UNKNOWN


# --- the walk -------------------------------------------------------------------------


def _arg_values(node: Any) -> list[Any]:
    """Arguments of a `Call` or a role-labelled `DistExpr`, uniformly."""
    out: list[Any] = []
    for a in getattr(node, "args", ()) or ():
        out.append(getattr(a, "value", a))
    return out


class _Walker:
    def __init__(self, task_id: str, env: _Env) -> None:
        self.task_id = task_id
        self.env = env
        self.risks: list[PartialityRisk] = []
        self.inspected: list[str] = []
        self.statements_walked = 0
        self._active: list[str] = []  # definitions currently being expanded

    # -- reporting --
    def _flag(self, operation: str, reason: str, path: list[str],
              operand: Any, env: _Env) -> None:
        risk = PartialityRisk(operation, reason, tuple(path),
                              self._dimensioned(operand, env))
        if risk not in self.risks:  # the same site reached twice is one risk
            self.risks.append(risk)

    def _dimensioned(self, operand: Any, env: _Env) -> bool:
        """A dimensioned denominator is not merely unguarded -- it is UNGUARDABLE.

        `require area != 0` does not compile: HML-D502 refuses to compare a
        `Quantity[Length^2]` to a dimensionless `0`. Saying so in the risk path is the
        difference between "add a guard" and "reformulate the task".
        """
        from hamiltonian_lang.ast.nodes import Ref
        if not isinstance(operand, Ref):
            return False
        return _is_dimensioned(env.types.get(operand.name))

    def _describe(self, node: Any) -> str:
        from hamiltonian_lang.backends.hml import render_expr
        try:
            return render_expr(node)
        except Exception:  # a node with no surface form is still worth naming
            return type(node).__name__

    def _origin(self, name: str, env: _Env) -> str:
        """Name the operand precisely: a binder and a module variable fail differently."""
        if name in env.defs:
            return f"{name} is a definition"
        declared = env.types.get(name)
        kind = self._kinds.get(name) or ("binder" if name not in self.env.types else "name")
        rendered = declared.render() if declared is not None else "an inferred type"
        return f"{name} is a {kind} of type {rendered}"

    _kinds: dict[str, str] = {}

    # -- traversal --
    def expr(self, node: Any, path: list[str], env: _Env, depth: int = 0) -> None:
        from hamiltonian_lang.ast.nodes import (
            BinOp,
            Call,
            Comparison,
            DistExpr,
            Index,
            Literal,
            LogicalOp,
            Quantifier,
            Ref,
            UnaryOp,
        )

        if node is None or depth > 32:
            return

        if isinstance(node, BinOp):
            if node.op == "/":
                self._division(node, path, env, depth)
            elif node.op == "^":
                self._power(node, path, env, depth)
            self.expr(node.left, path, env, depth + 1)
            self.expr(node.right, path, env, depth + 1)
            return

        if isinstance(node, Call):
            self._call(node, path, env, depth)
            for arg in _arg_values(node):
                self.expr(arg, path, env, depth + 1)
            self._descend_into_definition(node.callee, path, env, depth)
            return

        if isinstance(node, Index):
            self.inspected.append(f"index {self._describe(node)}")
            self._flag(
                "indexing",
                "index bounds are not established; the frozen subset states no extent "
                "predicate a reader could check",
                [*path, f"indexing {self._describe(node)}"], node, env)
            self.expr(node.base, path, env, depth + 1)
            for i in node.indices:
                self.expr(i, path, env, depth + 1)
            return

        if isinstance(node, Ref):
            self._descend_into_definition(node.name, path, env, depth)
            return

        if isinstance(node, Quantifier):
            inner = env.child()
            if node.var_type is not None:
                inner.types[node.var] = node.var_type
            inner.positive.discard(node.var)
            inner.nonzero.discard(node.var)
            self.expr(node.body, [*path, f"under quantifier {node.kind} {node.var}"],
                      inner, depth + 1)
            return

        if isinstance(node, (UnaryOp, Comparison, LogicalOp, DistExpr, Literal)):
            for attr in ("operand", "left", "right"):
                self.expr(getattr(node, attr, None), path, env, depth + 1)
            for arg in _arg_values(node):
                self.expr(arg, path, env, depth + 1)
            return

    # -- the partial operations --
    def _division(self, node: Any, path: list[str], env: _Env, depth: int) -> None:
        from hamiltonian_lang.ast.nodes import Ref

        denominator = node.right
        text = self._describe(denominator)
        self.inspected.append(f"division by {text}")
        if _establish(denominator, env, 0) in (
                Establishment.POSITIVE, Establishment.NONZERO):
            return

        step = [*path, f"division denominator {text}"]
        if isinstance(denominator, Ref):
            step.append(self._origin(denominator.name, env))
            reason = "nonzero condition not established"
        else:
            step.append("the denominator is a compound expression")
            reason = ("nonzero condition not established for a compound denominator; "
                      "each factor would have to be established separately")
        self._flag("division", reason, step, denominator, env)

    def _power(self, node: Any, path: list[str], env: _Env, depth: int) -> None:
        from hamiltonian_lang.ast.nodes import Literal, UnaryOp

        exponent, base = node.right, node.left
        base_text, exp_text = self._describe(base), self._describe(exponent)
        negative = (isinstance(exponent, UnaryOp) and exponent.op == "-") or (
            isinstance(exponent, Literal) and isinstance(exponent.value, (int, float))
            and not isinstance(exponent.value, bool) and exponent.value < 0)
        fractional = (isinstance(exponent, Literal)
                      and isinstance(exponent.value, float)
                      and not float(exponent.value).is_integer())

        if negative:
            self.inspected.append(f"negative power {base_text} ^ {exp_text}")
            if _establish(base, env, 0) not in (
                    Establishment.POSITIVE, Establishment.NONZERO):
                self._flag("negative power",
                           "a negative exponent is a division; nonzero base not established",
                           [*path, f"negative power {base_text} ^ {exp_text}"], base, env)
            return
        if fractional:
            self.inspected.append(f"fractional power {base_text} ^ {exp_text}")
            if _establish(base, env, 0) not in (
                    Establishment.POSITIVE, Establishment.NONNEGATIVE):
                self._flag("fractional power",
                           "a fractional exponent requires a non-negative base; not "
                           "established",
                           [*path, f"fractional power {base_text} ^ {exp_text}"], base, env)
        if not isinstance(exponent, Literal) and not negative:
            self.inspected.append(f"variable exponent {base_text} ^ {exp_text}")
            if _establish(base, env, 0) is not Establishment.POSITIVE:
                self._flag("variable exponent",
                           "the exponent is not a literal, so a negative or fractional "
                           "value cannot be excluded; positive base not established",
                           [*path, f"power {base_text} ^ {exp_text}"], base, env)

    def _call(self, node: Any, path: list[str], env: _Env, depth: int) -> None:
        requirement = PARTIAL_CALLS.get(node.callee)
        if requirement is None:
            return
        args = _arg_values(node)
        argument = args[0] if args else None
        text = self._describe(argument) if argument is not None else "<no argument>"
        self.inspected.append(f"{node.callee}({text})")
        step = [*path, f"{node.callee} argument {text}"]

        if requirement == "impossible":
            self._flag(node.callee,
                       f"{node.callee} is partial at points no predicate in the frozen "
                       f"subset can exclude; it cannot be established",
                       step, argument, env)
            return
        established = _establish(argument, env, 0)
        if requirement == "positive" and established is not Establishment.POSITIVE:
            self._flag(node.callee, "positive argument not established", step, argument, env)
        elif requirement == "nonnegative" and established not in (
                Establishment.POSITIVE, Establishment.NONNEGATIVE):
            self._flag(node.callee, "non-negative argument not established", step, argument, env)
        elif requirement in {"unit_interval", "open_unit_interval", "at_least_one"}:
            self._flag(node.callee,
                       f"a bounded domain ({requirement.replace('_', ' ')}) is not "
                       f"established by any declared type in the frozen subset",
                       step, argument, env)

    def _descend_into_definition(self, name: str, path: list[str], env: _Env,
                                 depth: int) -> None:
        """Follow the dependency. Partiality one or two `def`s deep is still partiality."""
        define = env.defs.get(name)
        if define is None or name in self._active or depth > 24:
            return
        self._active.append(name)
        inner = env.child()
        for pname, ptype in define.params:
            inner.types[pname] = ptype
            inner.positive.discard(pname)
            inner.nonzero.discard(pname)
            inner.nonnegative.discard(pname)
        self.expr(define.body, [*path, f"through definition {name}"], inner, depth + 1)
        self._active.pop()


def scan_module(module: Any, task_id: str = "<module>") -> PartialityReport:
    """Scan every expression position of a compiled module.

    Statement order matters here as it does everywhere else: a `require` establishes a
    fact for the statements that follow it, and the scanner reads them in source order.
    """
    from hamiltonian_lang.ast.nodes import (
        AssumeStmt,
        CheckStmt,
        ConceptDecl,
        Declaration,
        DefineStmt,
        InferStmt,
        LawStmt,
        ModuleDecl,
        ObjectiveStmt,
        ProveStmt,
        RequireStmt,
        SolveStmt,
    )

    env = _Env()
    kinds: dict[str, str] = {}
    for st in module.statements:
        if isinstance(st, Declaration):
            env.types[st.name] = st.declared_type
            kinds[st.name] = st.kind
            if st.value is not None:
                env.consts[st.name] = st.value
        elif isinstance(st, DefineStmt):
            env.defs[st.name] = st
            kinds[st.name] = "definition"

    walker = _Walker(task_id, env)
    walker._kinds = kinds

    for st in module.statements:
        if isinstance(st, Declaration):
            # An uninitialised declaration has no expression to walk. It is still HANDLED
            # here rather than falling through to the unknown-kind guard: "nothing to
            # walk" and "no branch exists" must not look the same.
            if st.value is not None:
                walker.expr(st.value, [f"declaration {st.name}"], env)
        elif isinstance(st, DefineStmt):
            inner = env.child()
            for pname, ptype in st.params:
                # A binder SHADOWS any module-level name, so it inherits none of its
                # facts. `require mu != 0` at module scope says nothing about a binder
                # also called `mu`, and reading it as if it did would admit a partial
                # definition on the strength of an unrelated statement.
                inner.types[pname] = ptype
                inner.positive.discard(pname)
                inner.nonzero.discard(pname)
                inner.nonnegative.discard(pname)
                kinds[pname] = "binder"
            walker.expr(st.body, [f"definition {st.name}"], inner)
        elif isinstance(st, (AssumeStmt, RequireStmt)):
            label = "assumption" if isinstance(st, AssumeStmt) else "requirement"
            walker.expr(st.proposition, [label], env)
            _collect_facts(env, st.proposition)  # in scope for what follows
        elif isinstance(st, ProveStmt):
            walker.expr(st.proposition, ["goal"], env)
        elif isinstance(st, CheckStmt):
            walker.expr(st.subject, [f"check {st.check_kind}"], env)
        elif isinstance(st, LawStmt):
            walker.expr(st.distribution, [f"{st.role} law"], env)
        elif isinstance(st, (SolveStmt, InferStmt)):
            # `targets`, not `target`. The old fallback tried three attribute names none
            # of these nodes has, so `getattr(..., None)` walked nothing and said nothing.
            for target in (getattr(st, "targets", ()) or ()):
                walker.expr(target, [type(st).__name__], env)
            walker.expr(getattr(st, "proposition", None), [type(st).__name__], env)
        elif isinstance(st, ObjectiveStmt):
            for attr in ("expression", "objective", "proposition"):
                walker.expr(getattr(st, attr, None), ["objective"], env)
        elif isinstance(st, ConceptDecl):
            # A concept body is expressions like any other. Without this branch the walk
            # never reached them and reported "0 sites inspected, all established" for a
            # module whose transform divided by a concept parameter -- fail OPEN, and
            # indistinguishable from a clean module.
            inner = env.child()
            for member in st.members:
                if member.declared_type is not None:
                    inner.types[member.name] = member.declared_type
                    kinds[member.name] = f"concept {member.kind}"
            for member in st.members:
                body_env = inner.child()
                for pname, ptype in member.params:
                    body_env.types[pname] = ptype
                    body_env.positive.discard(pname)
                    body_env.nonzero.discard(pname)
                    body_env.nonnegative.discard(pname)
                    kinds[pname] = "binder"
                walker.expr(member.body,
                            [f"concept {st.name}", f"{member.kind} {member.name}"],
                            body_env)
        elif not isinstance(st, ModuleDecl):
            # No silent pass. A statement kind nobody wired up must stop the corpus, not
            # be waved through: that is the difference between "clean" and "never looked".
            raise UnsupportedStatement(
                f"{task_id}: {type(st).__name__} has no partiality branch. A statement "
                f"the scanner cannot walk must not be admitted -- add a branch or reject "
                f"the task.")
        walker.statements_walked += 1

    return PartialityReport(task_id, tuple(walker.risks), tuple(walker.inspected),
                            walker.statements_walked)


def scan_source(source: str, task_id: str = "<source>") -> PartialityReport:
    """Compile and scan. Raises if the source does not compile — that is a prior gate."""
    from hamiltonian_lang import compile_source

    result = compile_source(source, f"<{task_id}>")
    if not result.ok():
        raise ValueError(
            f"{task_id}: cannot scan a source that does not compile: "
            f"{[d.code for d in result.diagnostics.errors]}")
    return scan_module(result.module, task_id)
