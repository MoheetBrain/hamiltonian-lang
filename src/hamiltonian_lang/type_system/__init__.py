"""Type checking, dimensional analysis, and proof-obligation collection.

Runs after name resolution. Annotates every expression node with ``type_`` and emits
diagnostics naming the *role* that failed, not merely the mismatch.

Three enforcement points carry most of the design's weight:

1. ``~`` demands ``Distribution[S]`` on the right and a compatible support on the left.
   ``RandomVariable[T]``, ``Distribution[T]`` and ``T`` are three distinct types with no
   subtyping path between them, so the three prohibited conflations in the master
   directive are unrepresentable rather than merely discouraged.
2. Distribution roles are checked against :mod:`.distributions`, with targeted
   diagnostics for known misparameterisations (scale vs variance, rate vs mean).
3. Dimensions are checked exactly with rational exponents; adding a Mass to a Length is
   an error with both dimensions printed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from ..ast.nodes import (
    Arg,
    AssumeStmt,
    BinOp,
    Call,
    CheckStmt,
    Comparison,
    ConceptDecl,
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
    SymbolId,
    UnaryOp,
)
from ..diagnostics import DiagnosticBag
from ..semantics import SymbolTable
from ..types import (
    ConceptType,
    DistributionType,
    FunctionType,
    MatrixType,
    PropositionType,
    QuantityType,
    RandomVariableType,
    ScalarType,
    TensorType,
    Type,
    UnknownType,
    VectorType,
    dimension_of,
    is_subtype,
    join,
    literal_inhabits,
)
from .distributions import DISTRIBUTIONS, MISPARAMETERISATIONS, lookup

__all__ = ["ProofObligation", "CheckResult", "TypeChecker", "check"]

REAL = ScalarType("Real")
BOOL = ScalarType("Bool")
NAT = ScalarType("Natural")
PROP = PropositionType()

_BUILTIN_SIGNATURES: dict[str, tuple[tuple[Type, ...], Type]] = {
    "exp": ((REAL,), ScalarType("PositiveReal")),
    "log": ((ScalarType("PositiveReal"),), REAL),
    "sqrt": ((ScalarType("NonNegativeReal"),), ScalarType("NonNegativeReal")),
    "abs": ((REAL,), ScalarType("NonNegativeReal")),
    "sin": ((REAL,), REAL),
    "cos": ((REAL,), REAL),
    "tan": ((REAL,), REAL),
}


@dataclass
class ProofObligation:
    """Something the language asserts but does not itself prove."""

    kind: str  # constraint | parameter_positivity | dimension | assumption | theorem
    description: str
    span: Span
    expression: Expr | None = None
    discharged_by: str | None = None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "description": self.description,
            "line": self.span.line,
            "discharged_by": self.discharged_by,
        }


@dataclass
class CheckResult:
    module: Module
    symbols: SymbolTable
    diagnostics: DiagnosticBag
    obligations: list[ProofObligation] = field(default_factory=list)

    def ok(self) -> bool:
        return self.diagnostics.ok()


class TypeChecker:
    def __init__(self, module: Module, symbols: SymbolTable, diags: DiagnosticBag) -> None:
        self.module = module
        self.symbols = symbols
        self.diags = diags
        self.obligations: list[ProofObligation] = []
        self.concepts: dict[str, ConceptDecl] = {
            s.name: s for s in module.statements if isinstance(s, ConceptDecl)
        }

    # -- helpers ----------------------------------------------------------
    def _sym_type(self, sid: SymbolId | None) -> Type:
        if sid is None:
            return UnknownType("unresolved")
        sym = self.symbols.get(sid)
        if sym is None or sym.declared_type is None:
            return UnknownType("no declared type")
        return sym.declared_type

    def _obligate(self, kind: str, desc: str, span: Span, expr: Expr | None = None) -> None:
        self.obligations.append(ProofObligation(kind, desc, span, expr))

    # -- driver -----------------------------------------------------------
    def run(self) -> CheckResult:
        for st in self.module.statements:
            self.check_statement(st)
        self._check_positivity_obligations()
        self._check_no_unknown_types_survive()
        return CheckResult(self.module, self.symbols, self.diags, self.obligations)

    def _check_no_unknown_types_survive(self) -> None:
        """Enforce the invariant that ``ast/nodes.py`` documents.

        ``UnknownType`` is permissive on both sides of ``is_subtype`` so that inference
        can proceed without cascading. That permissiveness is only sound if no Unknown
        reaches the end of checking — otherwise a comparison against an untyped
        expression silently succeeds while nothing has actually been typed.
        Previously documented and unenforced. (Red-team finding 1.8.)
        """
        if not self.diags.ok():
            # Unknowns downstream of an existing error are consequences, not findings.
            return
        from ..ast.nodes import walk

        for node in walk(self.module):
            if not isinstance(node, Expr):
                continue
            if isinstance(node.type_, UnknownType):
                self.diags.error(
                    "HML-T450",
                    "this expression could not be given a type",
                    node.span,
                    found="Unknown",
                    correction="annotate the operands, or use a construct v0 supports",
                    notes=[
                        node.type_.reason or "no reason recorded",
                        "an untyped expression compares equal to anything, so it must "
                        "not survive a successful check",
                    ],
                )

    def _check_positivity_obligations(self) -> None:
        """Every PositiveReal / Probability binding carries a standing obligation."""
        for sym in self.symbols.module_symbols():
            t = sym.declared_type
            if isinstance(t, ScalarType):
                if t.name == "PositiveReal":
                    self._obligate(
                        "parameter_positivity", f"{sym.name} > 0", sym.span
                    )
                elif t.name == "Probability":
                    self._obligate(
                        "parameter_positivity",
                        f"0 <= {sym.name} <= 1",
                        sym.span,
                    )
                elif t.name == "NonNegativeReal":
                    self._obligate(
                        "parameter_positivity", f"{sym.name} >= 0", sym.span
                    )

    # -- statements -------------------------------------------------------
    def check_statement(self, st: Statement) -> None:
        if isinstance(st, ModuleDecl):
            return

        if isinstance(st, Declaration):
            if st.declared_type is None:
                self.diags.error(
                    "HML-T401",
                    f"{st.name!r} has no type",
                    st.span,
                    correction=f"{st.kind} {st.name} : Real",
                    notes=["every object has a type (governing principle 1)"],
                )
                return
            st.type_ = st.declared_type
            if st.value is not None:
                vt = self.expr_type(st.value)
                if not self._inhabits(st.value, vt, st.declared_type):
                    self.diags.error(
                        "HML-T402",
                        f"the value assigned to {st.name!r} does not inhabit its "
                        f"declared type",
                        st.value.span,
                        expected=st.declared_type.render(),
                        found=vt.render(),
                        correction=self._retype_hint(st.name, st.kind, vt),
                    )
            return

        if isinstance(st, DefineStmt):
            bt = self.expr_type(st.body)
            st.type_ = st.declared_type or bt
            if st.declared_type is not None and not is_subtype(bt, st.declared_type):
                self.diags.error(
                    "HML-T403",
                    f"the body of {st.name!r} does not inhabit its declared type",
                    st.body.span,
                    expected=st.declared_type.render(),
                    found=bt.render(),
                )
            sym = self.symbols.get(st.symbol_id) if st.symbol_id else None
            if sym is not None and sym.declared_type is None:
                sym.declared_type = st.type_
            return

        if isinstance(st, LawStmt):
            self.check_law(st)
            return

        if isinstance(st, (AssumeStmt, RequireStmt, ProveStmt)):
            pt = self.expr_type(st.proposition)
            if not (isinstance(pt, PropositionType) or is_subtype(pt, BOOL)):
                self.diags.error(
                    "HML-T404",
                    f"{type(st).__name__.replace('Stmt', '').lower()} requires a "
                    f"proposition",
                    st.proposition.span,
                    expected="Proposition",
                    found=pt.render(),
                    correction="write a comparison or logical formula, e.g. 'x + y >= 10'",
                )
            kind = {
                AssumeStmt: "assumption",
                RequireStmt: "constraint",
                ProveStmt: "theorem",
            }[type(st)]
            self._obligate(kind, _render_proposition(st.proposition), st.span, st.proposition)
            return

        if isinstance(st, ObjectiveStmt):
            et = self.expr_type(st.expression)
            if dimension_of(et) is None:
                self.diags.error(
                    "HML-T405",
                    f"the {st.direction} objective must be a real-valued magnitude",
                    st.expression.span,
                    expected="Real or Quantity[...]",
                    found=et.render(),
                )
            return

        if isinstance(st, SolveStmt):
            for r in st.targets:
                r.type_ = self._sym_type(r.symbol_id)
            return

        if isinstance(st, InferStmt):
            for r in st.targets:
                r.type_ = self._sym_type(r.symbol_id)
                sym = self.symbols.get(r.symbol_id) if r.symbol_id else None
                # Every query kind needs a law, not just 'posterior'. An MLE without a
                # likelihood is exactly as ill-posed as a posterior without a prior.
                if sym is not None and not sym.stochastic:
                    why = {
                        "posterior": "a posterior requires a prior",
                        "map": "a maximum-a-posteriori estimate requires a prior",
                        "mle": "a maximum-likelihood estimate requires a likelihood",
                        "expectation": "an expectation is taken with respect to a law",
                        "variance": "a variance is taken with respect to a law",
                    }[st.query]
                    self.diags.error(
                        "HML-S604",
                        f"cannot infer {st.query} for {r.name!r}: it has no "
                        f"probability law",
                        r.span,
                        correction=(
                            f"add 'prior {r.name} ~ <Distribution>' or "
                            f"'likelihood {r.name} | ... ~ <Distribution>' first"
                        ),
                        notes=[f"{why}; without one this query is not well posed"],
                    )
            return

        if isinstance(st, CheckStmt):
            self.check_check(st)
            return

        if isinstance(st, ConceptDecl):
            self.check_concept(st)
            return

    def _retype_hint(self, name: str, kind: str, found: Type) -> str:
        return f"declare it as '{kind} {name} : {found.render()}', or correct the value"

    # -- law --------------------------------------------------------------
    def check_law(self, st: LawStmt) -> None:
        if st.distribution is None:
            return
        dist_type = self.dist_type(st.distribution)
        st.distribution.type_ = dist_type
        if not isinstance(dist_type, DistributionType):
            return
        support = dist_type.support

        target_type = self._sym_type(st.target_symbol)
        if isinstance(target_type, UnknownType):
            return

        if isinstance(target_type, DistributionType):
            self.diags.error(
                "HML-T410",
                f"{st.target!r} is a Distribution and cannot itself be given a law",
                st.span,
                expected="RandomVariable[T] or a value type T",
                found=target_type.render(),
                notes=[
                    "a distribution is a probability law, not a value drawn from one; "
                    "conflating them is prohibited"
                ],
            )
            return

        target_sym = self.symbols.get(st.target_symbol) if st.target_symbol else None
        if target_sym is not None:
            if st.role == "prior" and target_sym.kind in ("obs", "const"):
                self.diags.error(
                    "HML-S607",
                    f"{st.target!r} is declared as "
                    f"{'observed data' if target_sym.kind == 'obs' else 'a constant'} "
                    f"and cannot be given a prior",
                    st.span,
                    expected="a param, var or rv target",
                    found=f"{target_sym.kind} {st.target}",
                    correction=(
                        f"use 'likelihood {st.target} | ... ~ ...' for observed data, "
                        f"or declare {st.target} as a param"
                    ),
                    notes=[
                        "a prior expresses belief about an unknown; a value already "
                        "observed is not unknown"
                    ],
                )
            elif st.role == "likelihood" and target_sym.kind == "const":
                self.diags.error(
                    "HML-S607",
                    f"{st.target!r} is a constant and cannot have a likelihood",
                    st.span,
                    found=f"const {st.target}",
                    correction=f"declare {st.target} as 'obs' if it is data",
                )

        codomain = (
            target_type.codomain
            if isinstance(target_type, RandomVariableType)
            else target_type
        )

        if not is_subtype(support, codomain):
            self.diags.error(
                "HML-T411",
                f"the support of {st.distribution.family} does not inhabit the "
                f"declared type of {st.target!r}",
                st.span,
                expected=codomain.render(),
                found=f"support {support.render()}",
                correction=(
                    f"declare '{st.target} : {support.render()}', or choose a family "
                    f"whose support is {codomain.render()}"
                ),
                notes=[
                    f"{st.distribution.family} is supported on {support.render()}"
                ],
            )

    def dist_type(self, d: DistExpr) -> Type:
        spec = lookup(d.family)
        if spec is None:
            close = sorted(
                DISTRIBUTIONS,
                key=lambda n: (0 if n.lower().startswith(d.family[:2].lower()) else 1, n),
            )[:3]
            self.diags.error(
                "HML-T412",
                f"unknown distribution family {d.family!r}",
                d.span,
                correction=f"known families include: {', '.join(close)}",
                notes=[
                    "v0 implements a deliberately small registry; see "
                    "src/hamiltonian_lang/type_system/distributions.py"
                ],
            )
            return UnknownType("unknown family")

        given = {a.role for a in d.args}
        arg_types: dict[str, Type] = {}

        for a in d.args:
            at = self.expr_type(a.value)
            arg_types[a.role] = at
            if a.role not in spec.roles:
                self._report_bad_role(d, a, spec, at)
                continue
            want = spec.roles[a.role]
            if not self._role_compatible(at, want, a.value):
                self.diags.error(
                    "HML-T413",
                    f"the {a.role!r} role of {d.family} requires "
                    f"{want.render()}",
                    a.value.span,
                    expected=want.render(),
                    found=at.render(),
                    correction=self._role_correction(a, want),
                    notes=[spec.note] if spec.note else [],
                )

        self._check_cross_role_constraints(d, spec)

        missing = spec.required() - given
        if missing:
            self.diags.error(
                "HML-T414",
                f"{d.family} is missing required role(s): "
                f"{', '.join(sorted(missing))}",
                d.span,
                expected=", ".join(f"{r} : {t.render()}" for r, t in spec.roles.items()),
                correction=(
                    f"{d.family}("
                    + ", ".join(f"{r} := <expr>" for r in spec.roles)
                    + ")"
                ),
            )
            return UnknownType("incomplete distribution")

        return spec.distribution_type(arg_types)

    def _inhabits(self, expr: Expr, actual: Type, want: Type) -> bool:
        """Subtyping, refined by the exact value when the expression is a literal."""
        if is_subtype(actual, want):
            return True
        lit = _as_literal(expr)
        return lit is not None and literal_inhabits(lit, want)

    def _check_cross_role_constraints(self, d: DistExpr, spec) -> None:
        """Relations that must hold *between* roles.

        Decided when both sides are literals; otherwise recorded as a proof obligation.
        Deciding what is decidable and obligating the rest is the honest split.
        """
        ops = {
            "<": lambda a, b: a < b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            ">=": lambda a, b: a >= b,
        }
        for left_role, op, right_role, why in spec.cross_constraints:
            left, right = d.arg(left_role), d.arg(right_role)
            if left is None or right is None:
                continue
            lv, rv = _as_literal(left), _as_literal(right)
            if lv is not None and rv is not None:
                if not ops[op](lv, rv):
                    self.diags.error(
                        "HML-T417",
                        f"{d.family} requires {left_role} {op} {right_role}",
                        d.span,
                        expected=f"{left_role} {op} {right_role}",
                        found=f"{left_role} = {lv}, {right_role} = {rv}",
                        notes=[why],
                        correction="swap the two roles, or correct the values",
                    )
            else:
                from ..backends.hml import render_expr

                self._obligate(
                    "constraint",
                    f"{render_expr(left)} {op} {render_expr(right)}",
                    d.span,
                )

    def _role_compatible(self, actual: Type, want: Type, expr: Expr | None = None) -> bool:
        if is_subtype(actual, want):
            return True
        if expr is not None:
            lit = _as_literal(expr)
            if lit is not None and literal_inhabits(lit, want):
                return True
        # A vector-valued role accepts any vector of a compatible element type,
        # regardless of a symbolic extent the checker cannot evaluate.
        if isinstance(want, VectorType) and isinstance(actual, VectorType):
            return is_subtype(actual.element, want.element)
        return False

    def _role_correction(self, a: Arg, want: Type) -> str:
        if isinstance(a.value, Ref):
            return f"declare '{a.value.name} : {want.render()}'"
        return f"supply an expression of type {want.render()}"

    def _report_bad_role(self, d: DistExpr, a: Arg, spec, actual: Type) -> None:
        hit = MISPARAMETERISATIONS.get(a.role)
        if hit is not None:
            family, explanation, canonical = hit
            if family is None or family == d.family:
                if canonical in spec.roles:
                    self.diags.error(
                        "HML-T415",
                        f"{d.family} has no role {a.role!r}",
                        a.span,
                        expected=f"{canonical} : {spec.roles[canonical].render()}",
                        found=a.role,
                        correction=f"{canonical} := ...",
                        notes=[explanation],
                    )
                    return
        self.diags.error(
            "HML-T416",
            f"{d.family} has no role {a.role!r}",
            a.span,
            expected=", ".join(sorted(spec.roles)),
            found=a.role,
            correction=f"use one of: {', '.join(f'{r} := ...' for r in spec.roles)}",
        )

    # -- check statements -------------------------------------------------
    def check_check(self, st: CheckStmt) -> None:
        if st.subject is None:
            return
        t = self.expr_type(st.subject)
        if st.check_kind == "dimension":
            dim = dimension_of(t)
            if dim is None:
                self.diags.error(
                    "HML-D503",
                    "this expression has no physical dimension",
                    st.subject.span,
                    found=t.render(),
                    correction="check dimension applies to Quantity[...] and real scalars",
                )
                return
            st.type_ = t
            if st.expected is not None and st.expected != dim.render():
                self.diags.error(
                    "HML-D504",
                    "the computed dimension does not match the asserted dimension",
                    st.span,
                    expected=st.expected,
                    found=dim.render(),
                )
            else:
                self._obligate(
                    "dimension",
                    f"dimension = {dim.render()}",
                    st.span,
                    st.subject,
                )
                self.obligations[-1].discharged_by = "hamiltonian_lang.type_system"
        else:
            if not (isinstance(t, PropositionType) or is_subtype(t, BOOL)):
                self.diags.error(
                    "HML-T404",
                    "check requires a proposition",
                    st.subject.span,
                    expected="Proposition",
                    found=t.render(),
                )

    def check_concept(self, st: ConceptDecl) -> None:
        # Type the transforms first and publish a FunctionType for each, so that an
        # invariant calling a transform gets a real type instead of Unknown. Without
        # this, `standardise(location) = 0` compared Unknown against a literal and
        # succeeded vacuously. (Red-team finding 1.8.)
        for tr in st.members_of("transform"):
            if tr.body is None:
                continue
            body_type = self.expr_type(tr.body)
            domain = tuple(t if t is not None else REAL for _, t in tr.params)
            sym = self._concept_member_symbol(st, tr.name)
            if sym is not None:
                sym.declared_type = FunctionType(domain, body_type)

        for m in st.members:
            if m.body is not None and m.kind != "transform":
                self.expr_type(m.body)
        transforms = st.members_of("transform")
        for tr in transforms:
            if not tr.params:
                self.diags.warn(
                    "HML-S605",
                    f"transform {tr.name!r} takes no argument",
                    tr.span,
                    notes=["a transform with no argument is a property, not a transform"],
                )
        for inv in st.members_of("invariant"):
            if inv.body is not None:
                self._obligate(
                    "constraint",
                    f"{st.name}.{inv.name}: {_render_proposition(inv.body)}",
                    inv.span,
                    inv.body,
                )

    def _concept_member_symbol(self, st: ConceptDecl, name: str):
        """The resolver binds concept members in a scope one level below the module."""
        for sym in self.symbols.all.values():
            if (
                sym.name == name
                and sym.kind in ("concept_transform", "concept_param")
                and sym.id.depth == 1
            ):
                return sym
        return None

    # -- expressions ------------------------------------------------------
    def expr_type(self, e: Expr) -> Type:
        t = self._expr_type(e)
        e.type_ = t
        return t

    def _expr_type(self, e: Expr) -> Type:
        if isinstance(e, Literal):
            if isinstance(e.value, bool):
                return BOOL
            if isinstance(e.value, int):
                if e.value > 0:
                    return ScalarType("PositiveNatural")
                return NAT if e.value == 0 else ScalarType("Integer")
            if e.value > 0:
                return ScalarType("PositiveReal")
            if e.value == 0:
                return ScalarType("NonNegativeReal")
            return REAL

        if isinstance(e, Ref):
            t = self._sym_type(e.symbol_id)
            sym = self.symbols.get(e.symbol_id) if e.symbol_id else None
            if sym is not None and sym.kind == "concept":
                return ConceptType(sym.name)
            return t

        if isinstance(e, UnaryOp):
            ot = self.expr_type(e.operand)
            if e.op == "not":
                if not (isinstance(ot, PropositionType) or is_subtype(ot, BOOL)):
                    self.diags.error(
                        "HML-T420", "'not' requires a proposition", e.span,
                        expected="Proposition", found=ot.render(),
                    )
                return PROP
            # Negation destroys every positivity refinement: -(PositiveNatural) is an
            # Integer, not a PositiveNatural. Preserving `ot` here would make
            # `const a : Natural = -3` type-check, which is exactly wrong.
            if isinstance(ot, ScalarType):
                return {
                    "PositiveNatural": ScalarType("Integer"),
                    "Natural": ScalarType("Integer"),
                    "PositiveReal": REAL,
                    "NonNegativeReal": REAL,
                    "Probability": REAL,
                }.get(ot.name, ot)
            return ot

        if isinstance(e, Comparison):
            lt = self.expr_type(e.left)
            rt = self.expr_type(e.right)
            self._require_comparable(e, lt, rt)
            return PROP

        if isinstance(e, LogicalOp):
            lt = self.expr_type(e.left)
            rt = self.expr_type(e.right)
            for side, t in ((e.left, lt), (e.right, rt)):
                if not (isinstance(t, PropositionType) or is_subtype(t, BOOL)):
                    self.diags.error(
                        "HML-T421",
                        f"the operands of {e.op!r} must be propositions",
                        side.span,
                        expected="Proposition",
                        found=t.render(),
                        notes=[
                            "implication is not correlation and not arithmetic; both "
                            "sides must be truth-valued"
                        ],
                    )
            return PROP

        if isinstance(e, Quantifier):
            sym = self.symbols.get(e.symbol_id) if e.symbol_id else None
            if sym is not None and e.var_type is not None:
                sym.declared_type = e.var_type
            bt = self.expr_type(e.body)
            if not (isinstance(bt, PropositionType) or is_subtype(bt, BOOL)):
                self.diags.error(
                    "HML-T422",
                    f"the body of '{e.kind} {e.var}' must be a proposition",
                    e.body.span,
                    expected="Proposition",
                    found=bt.render(),
                )
            return PROP

        if isinstance(e, BinOp):
            return self._binop_type(e)

        if isinstance(e, Index):
            bt = self.expr_type(e.base)
            for i in e.indices:
                it = self.expr_type(i)
                if not is_subtype(it, ScalarType("Integer")):
                    self.diags.error(
                        "HML-T423", "an index must be an integer", i.span,
                        expected="Natural or Integer", found=it.render(),
                    )
            if isinstance(bt, VectorType):
                if len(e.indices) != 1:
                    self.diags.error(
                        "HML-T424",
                        f"a vector takes exactly one index, {len(e.indices)} given",
                        e.span,
                    )
                return bt.element
            if isinstance(bt, MatrixType):
                if len(e.indices) != 2:
                    self.diags.error(
                        "HML-T424",
                        f"a matrix takes exactly two indices, {len(e.indices)} given",
                        e.span,
                    )
                return bt.element
            if isinstance(bt, TensorType):
                return bt.element
            if isinstance(bt, UnknownType):
                return bt
            self.diags.error(
                "HML-T425", f"{bt.render()} cannot be indexed", e.span, found=bt.render()
            )
            return UnknownType("not indexable")

        if isinstance(e, DistExpr):
            return self.dist_type(e)

        if isinstance(e, Call):
            return self._call_type(e)

        return UnknownType(f"unhandled node {type(e).__name__}")

    #: How a scalar element type behaves under repeated addition. Summing
    #: probabilities may exceed 1, so Probability widens to NonNegativeReal; summing
    #: positives stays positive. Getting this wrong would let `sum(w) : Probability`
    #: through, which is exactly the class of error the refinement poset exists to stop.
    _ADDITIVE_CLOSURE = {
        "Probability": "NonNegativeReal",
        "PositiveNatural": "PositiveNatural",
        "Natural": "Natural",
        "Integer": "Integer",
        "Rational": "Rational",
        "PositiveReal": "PositiveReal",
        "NonNegativeReal": "NonNegativeReal",
        "Real": "Real",
    }

    def _aggregate_type(self, e: Call, arg_types: list[Type]) -> Type | None:
        """Signatures for the shape-polymorphic builtins.

        These previously fell through to UnknownType, which is permissive on both sides
        of ``is_subtype`` — so `require sum(w) = 1.0` type-checked while nothing had
        actually been typed. (Red-team finding 1.8.)
        """
        name = e.callee
        if name not in ("sum", "prod", "mean", "variance", "expectation", "transpose"):
            return None

        if len(arg_types) != 1:
            self.diags.error(
                "HML-T426",
                f"{name} takes 1 argument, {len(arg_types)} given",
                e.span,
            )
            return UnknownType(f"wrong arity for {name}")
        t = arg_types[0]

        if name == "transpose":
            if isinstance(t, MatrixType):
                return MatrixType(t.element, t.cols, t.rows)
            self.diags.error(
                "HML-T427", "transpose requires a matrix", e.span,
                expected="Matrix[...]", found=t.render(),
            )
            return UnknownType("transpose of a non-matrix")

        if name == "expectation":
            if isinstance(t, RandomVariableType):
                return t.codomain
            if isinstance(t, DistributionType):
                self.diags.error(
                    "HML-T428",
                    "expectation applies to a random variable, not to a law",
                    e.span,
                    found=t.render(),
                    notes=["bind the law to a symbol with '~', then take its expectation"],
                )
                return UnknownType("expectation of a distribution")
            return t

        element = t.element if isinstance(t, (VectorType, MatrixType, TensorType)) else None
        if element is None:
            self.diags.error(
                "HML-T427",
                f"{name} requires a vector, matrix or tensor",
                e.span,
                expected="Vector[...] or Matrix[...]",
                found=t.render(),
            )
            return UnknownType(f"{name} of a non-aggregate")

        if name == "variance":
            return ScalarType("NonNegativeReal")
        if name == "mean":
            # The mean of a set of values lies in their own range, so the element
            # refinement is preserved -- unlike the sum.
            return element
        base = element if isinstance(element, ScalarType) else None
        if base is None:
            return element
        if name == "prod":
            return ScalarType(
                {"Probability": "Probability"}.get(
                    base.name, self._ADDITIVE_CLOSURE.get(base.name, "Real")
                )
            )
        return ScalarType(self._ADDITIVE_CLOSURE.get(base.name, "Real"))

    def _call_type(self, e: Call) -> Type:
        arg_types = [self.expr_type(a) for a in e.args]
        aggregate = self._aggregate_type(e, arg_types)
        if aggregate is not None:
            return aggregate
        sig = _BUILTIN_SIGNATURES.get(e.callee)
        if sig is not None:
            domain, codomain = sig
            if len(arg_types) != len(domain):
                self.diags.error(
                    "HML-T426",
                    f"{e.callee} takes {len(domain)} argument(s), "
                    f"{len(arg_types)} given",
                    e.span,
                )
                return codomain
            for a, at, want in zip(e.args, arg_types, domain, strict=True):
                if not is_subtype(at, want):
                    self.diags.error(
                        "HML-T427",
                        f"the argument of {e.callee} has the wrong type",
                        a.span,
                        expected=want.render(),
                        found=at.render(),
                    )
            return codomain

        sym = None
        for candidate in self.symbols.all.values():
            if candidate.name == e.callee:
                sym = candidate
                break
        if sym is not None and isinstance(sym.declared_type, FunctionType):
            return sym.declared_type.codomain
        if sym is not None and sym.kind == "def":
            return sym.declared_type or UnknownType("definition without inferred type")
        return UnknownType(f"unknown function {e.callee}")

    def _require_comparable(self, e: Comparison, lt: Type, rt: Type) -> None:
        ld, rd = dimension_of(lt), dimension_of(rt)
        if ld is not None and rd is not None:
            if ld != rd:
                self.diags.error(
                    "HML-D502",
                    "cannot compare quantities with different dimensions",
                    e.span,
                    expected=ld.render(),
                    found=rd.render(),
                    notes=["comparison requires dimensional equality"],
                )
            return
        if isinstance(lt, DistributionType) or isinstance(rt, DistributionType):
            self.diags.error(
                "HML-T428",
                "a distribution cannot be compared with a value",
                e.span,
                found=f"{lt.render()} {e.op} {rt.render()}",
                notes=[
                    "compare a random variable's realisations or a summary such as "
                    "its expectation, not the law itself"
                ],
            )
            return
        if isinstance(join(lt, rt), UnknownType) and not (
            isinstance(lt, UnknownType) or isinstance(rt, UnknownType)
        ):
            self.diags.error(
                "HML-T429",
                "these operands are not comparable",
                e.span,
                expected=lt.render(),
                found=rt.render(),
            )

    def _binop_type(self, e: BinOp) -> Type:
        lt = self.expr_type(e.left)
        rt = self.expr_type(e.right)

        for side, t in ((e.left, lt), (e.right, rt)):
            if isinstance(t, DistributionType):
                self.diags.error(
                    "HML-T430",
                    "arithmetic on a probability law is not defined",
                    side.span,
                    found=t.render(),
                    notes=[
                        "a Distribution[T] is not a value of T; sample it or take a "
                        "summary such as expectation first"
                    ],
                )
                return UnknownType("arithmetic on a distribution")

        if e.op == "@":
            return self._matmul_type(e, lt, rt)

        if e.op == "^":
            return self._power_type(e, lt, rt)

        if e.op in ("+", "-"):
            ld, rd = dimension_of(lt), dimension_of(rt)
            if ld is not None and rd is not None and ld != rd:
                self.diags.error(
                    "HML-D502",
                    f"cannot {'add' if e.op == '+' else 'subtract'} quantities with "
                    f"different dimensions",
                    e.span,
                    expected=ld.render(),
                    found=rd.render(),
                    correction="convert one operand so both sides share a dimension",
                )
                return UnknownType("dimensional mismatch")
            if isinstance(lt, (VectorType, MatrixType)) or isinstance(
                rt, (VectorType, MatrixType)
            ):
                return self._elementwise(e, lt, rt)
            result = join(lt, rt)
            if isinstance(result, UnknownType):
                self.diags.error(
                    "HML-T431",
                    f"{e.op!r} is not defined for these operand types",
                    e.span,
                    expected=lt.render(),
                    found=rt.render(),
                )
                return result
            # Subtraction leaves the refined subsets: PositiveReal - PositiveReal : Real
            if e.op == "-" and isinstance(result, ScalarType) and result.name in (
                "Natural", "PositiveReal", "NonNegativeReal", "Probability"
            ):
                return REAL
            if e.op == "+" and isinstance(result, ScalarType) and result.name == "Probability":
                # two probabilities may sum above 1
                return ScalarType("NonNegativeReal")
            return result

        if e.op in ("*", "/"):
            ld, rd = dimension_of(lt), dimension_of(rt)
            if isinstance(lt, (VectorType, MatrixType)) or isinstance(
                rt, (VectorType, MatrixType)
            ):
                return self._elementwise(e, lt, rt)
            if ld is not None and rd is not None:
                dim = ld * rd if e.op == "*" else ld / rd
                base = join(_base_of(lt), _base_of(rt))
                if isinstance(base, UnknownType):
                    base = REAL
                if dim.is_dimensionless():
                    if e.op == "/" and isinstance(base, ScalarType) and base.name in (
                        "Natural", "PositiveReal"
                    ):
                        return ScalarType("PositiveReal")
                    return base if not isinstance(base, UnknownType) else REAL
                return QuantityType(dim, base if isinstance(base, ScalarType) else REAL)
            self.diags.error(
                "HML-T431",
                f"{e.op!r} is not defined for these operand types",
                e.span,
                expected=lt.render(),
                found=rt.render(),
            )
            return UnknownType("bad operands")

        return UnknownType(f"unknown operator {e.op}")

    def _elementwise(self, e: BinOp, lt: Type, rt: Type) -> Type:
        shaped = lt if isinstance(lt, (VectorType, MatrixType)) else rt
        other = rt if shaped is lt else lt
        if isinstance(other, (VectorType, MatrixType)):
            if type(other) is not type(shaped):
                self.diags.error(
                    "HML-T432",
                    "elementwise operation between incompatible shapes",
                    e.span,
                    expected=shaped.render(),
                    found=other.render(),
                )
                return UnknownType("shape mismatch")
            if isinstance(shaped, VectorType) and isinstance(other, VectorType):
                if (
                    shaped.length is not None
                    and other.length is not None
                    and shaped.length != other.length
                ):
                    self.diags.error(
                        "HML-T433",
                        "vector lengths do not agree",
                        e.span,
                        expected=str(shaped.length),
                        found=str(other.length),
                    )
                    return UnknownType("length mismatch")
        return shaped

    def _matmul_type(self, e: BinOp, lt: Type, rt: Type) -> Type:
        if isinstance(lt, MatrixType) and isinstance(rt, VectorType):
            if lt.cols is not None and rt.length is not None and lt.cols != rt.length:
                self.diags.error(
                    "HML-T434",
                    "inner dimensions do not agree in a matrix-vector product",
                    e.span,
                    expected=f"Vector[..., {lt.cols}]",
                    found=rt.render(),
                )
                return UnknownType("shape mismatch")
            return VectorType(lt.element, lt.rows)
        if isinstance(lt, MatrixType) and isinstance(rt, MatrixType):
            if lt.cols is not None and rt.rows is not None and lt.cols != rt.rows:
                self.diags.error(
                    "HML-T434",
                    "inner dimensions do not agree in a matrix product",
                    e.span,
                    expected=f"Matrix[..., {lt.cols}, ...]",
                    found=rt.render(),
                )
                return UnknownType("shape mismatch")
            return MatrixType(lt.element, lt.rows, rt.cols)
        if isinstance(lt, VectorType) and isinstance(rt, VectorType):
            return lt.element  # inner product
        if isinstance(lt, UnknownType) or isinstance(rt, UnknownType):
            return UnknownType("propagated")
        self.diags.error(
            "HML-T435",
            "'@' requires matrix or vector operands",
            e.span,
            expected="Matrix[...] @ Vector[...] or Matrix[...] @ Matrix[...]",
            found=f"{lt.render()} @ {rt.render()}",
        )
        return UnknownType("bad matmul")

    def _power_type(self, e: BinOp, lt: Type, rt: Type) -> Type:
        ld = dimension_of(lt)
        if ld is not None and not ld.is_dimensionless():
            if not isinstance(e.right, Literal) or isinstance(e.right.value, bool):
                self.diags.error(
                    "HML-D505",
                    "a dimensional quantity may only be raised to a literal rational "
                    "power",
                    e.span,
                    found=rt.render(),
                    notes=[
                        "a symbolic exponent would make the dimension undecidable at "
                        "check time"
                    ],
                )
                return UnknownType("symbolic exponent on a dimensional quantity")
            exp = Fraction(str(e.right.value))
            return QuantityType(ld.power(exp), _base_of(lt))
        if not is_subtype(rt, REAL):
            self.diags.error(
                "HML-T436", "an exponent must be real", e.span, found=rt.render()
            )
            return UnknownType("bad exponent")
        if isinstance(e.right, Literal) and not isinstance(e.right.value, bool):
            v = e.right.value
            if isinstance(v, int) and v % 2 == 0 and v > 0:
                return ScalarType("NonNegativeReal")
        return REAL


def _as_literal(e: Expr):
    """The exact value of ``e`` when it is a (possibly negated) numeric literal."""
    if isinstance(e, Literal) and not isinstance(e.value, bool):
        return e.value
    if isinstance(e, UnaryOp) and e.op == "-":
        inner = _as_literal(e.operand)
        return None if inner is None else -inner
    if isinstance(e, Literal) and isinstance(e.value, bool):
        return e.value
    return None


def _base_of(t: Type) -> ScalarType:
    if isinstance(t, QuantityType):
        return t.base
    if isinstance(t, ScalarType):
        return t
    return REAL


def _render_proposition(e: Expr) -> str:
    from ..backends.hml import render_expr

    return render_expr(e)


def check(module: Module, symbols: SymbolTable, diags: DiagnosticBag) -> CheckResult:
    return TypeChecker(module, symbols, diags).run()
