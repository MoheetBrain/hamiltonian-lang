"""SymPy code generation.

Emits a *runnable* Python module. The generated file imports ``sympy``, declares one
SymPy symbol per HML binding with the assumptions its HML type justifies, and rebuilds
the definitions, constraints and claims as SymPy expression objects. Running the file
leaves those objects in the module namespace under predictable names
(``definitions``, ``requirements``, ``claims``, ``assumptions``, ``type_constraints``,
``objective``, ``solve_targets``) so a caller can pick them up.

What this backend deliberately does **not** do
----------------------------------------------
*Distributions.* SymPy does have ``sympy.stats``, and it does have ``Normal``,
``Beta`` and ``Binomial``. It does **not** have any representation of

* the distinction between a ``prior``, a ``likelihood`` and a bare ``law``;
* a conditioning set (``y | x beta sigma``);
* an inference query (``infer posterior theta``).

Emitting ``sympy.stats.Normal(...)`` would therefore reproduce one third of a law
statement and silently discard the rest, while looking complete. Every ``law``,
``prior`` and ``likelihood`` is instead reported as **dropped** and emitted as a
comment recording exactly what was lost. That is the honest answer, and it is the
answer the backend contract asks for.

*Quantifiers.* SymPy has no first-order quantifier. ``sympy.Q`` is an assumptions
predicate system, not a binder, and there is no sound way to encode
``forall x : Real . exists y : Real . y > x``. Dropped, with the structure recorded in
a comment.

*Dimensions.* ``sympy.physics.units`` exists, but the design freeze (§8) says v0 does
not reconcile units, and HML's ``Dimension`` is a bare rational-exponent vector with no
unit attached. Mapping it onto ``sympy.physics.units`` would require inventing a unit
for every dimension. Dropped.

Design choices worth stating
----------------------------
* **Numeric literals become ``sympy.Rational``**, not ``sympy.Float``. HML's ``0.5``
  is an exact decimal in the source text and the target is a *symbolic* algebra system;
  turning it into a binary float would introduce an inexactness the source does not
  have. Recorded as a note, not as loss, because the value is preserved exactly.
* **Refinement types become assumptions where SymPy has one, and constraints where it
  does not.** ``PositiveReal`` becomes ``positive=True``; ``Probability`` becomes
  ``nonnegative=True`` *plus* an entry in ``type_constraints`` for the upper bound,
  because SymPy assumptions cannot express ``x <= 1``.
* **Concept members are name-mangled** to ``Concept__member``. SymPy has no namespace
  for symbols, so the concept's scope is flattened; the mangling keeps it injective.

No claim is made that the emitted expressions are mathematically equivalent to the HML
source beyond the constructs listed as exact in ``docs/design/BACKEND_CONTRACT.md``.
"""

from __future__ import annotations

import keyword

from ..ast.nodes import (
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
    ModuleDecl,
    ObjectiveStmt,
    ProveStmt,
    Quantifier,
    Ref,
    RequireStmt,
    SolveStmt,
    Statement,
    UnaryOp,
)
from ..types import (
    ConceptType,
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
    UnknownType,
    VectorType,
)
from .base import Backend

__all__ = ["SympyBackend", "to_sympy", "SCALAR_ASSUMPTIONS"]


#: HML scalar -> (SymPy assumption keywords, extra bound that assumptions cannot carry)
#:
#: The second element is a comparison template applied to the symbol; ``None`` means
#: the assumptions capture the type exactly.
SCALAR_ASSUMPTIONS: dict[str, tuple[dict[str, bool], str | None]] = {
    "Real": ({"real": True}, None),
    "Rational": ({"rational": True}, None),
    "Integer": ({"integer": True}, None),
    "Natural": ({"integer": True, "nonnegative": True}, None),
    "PositiveNatural": ({"integer": True, "positive": True}, None),
    "NonNegativeReal": ({"real": True, "nonnegative": True}, None),
    "PositiveReal": ({"real": True, "positive": True}, None),
    # SymPy assumptions have no upper bound predicate, so [0, 1] splits into an
    # assumption for the lower half and an explicit relational for the upper half.
    "Probability": ({"real": True, "nonnegative": True}, "sympy.Le({name}, 1)"),
    "Bool": ({}, None),
}

_PREC = {
    "iff": 1, "implies": 2, "or": 3, "and": 4,
    "+": 6, "-": 6,
    "*": 7, "/": 7, "@": 7,
    "unary": 8,
    "^": 9,
}
_ATOM = 100

_KNOWN_CALLS = {
    "exp": "sympy.exp", "log": "sympy.log", "sqrt": "sympy.sqrt",
    "sin": "sympy.sin", "cos": "sympy.cos", "tan": "sympy.tan",
    "abs": "sympy.Abs",
}

_REL = {
    "=": "sympy.Eq", "!=": "sympy.Ne", "<": "sympy.Lt", "<=": "sympy.Le",
    ">": "sympy.Gt", ">=": "sympy.Ge",
}

_LOGIC = {
    "and": "sympy.And", "or": "sympy.Or",
    "implies": "sympy.Implies", "iff": "sympy.Equivalent",
}


def _py_name(name: str) -> str:
    """A Python identifier that cannot collide with a keyword or builtin binding."""
    if keyword.iskeyword(name) or keyword.issoftkeyword(name) or name in {
        "sympy", "definitions", "requirements", "claims", "assumptions",
        "type_constraints", "objective", "objective_direction", "solve_targets",
        "symbols_by_name",
    }:
        return f"{name}_"
    return name


class SympyBackend(Backend):
    target = "sympy"
    limitations = (
        "SymPy has no representation of a probability law's *role*: the prior / "
        "likelihood / law distinction, the conditioning set, and inference queries "
        "have no encoding, so every law statement is dropped rather than partially "
        "translated via sympy.stats.",
        "SymPy has no first-order quantifiers. forall/exists cannot be encoded and "
        "are dropped; quantifier nesting order, the property HML exists to make "
        "explicit, is therefore not preserved at all in this target.",
        "SymPy assumptions are a fixed predicate set with no upper bounds and no "
        "element-wise assumptions on MatrixSymbol, so Probability and refined "
        "vector/matrix element types are only partially expressible.",
        "SymPy has no dimensional analysis in the form HML uses (bare rational "
        "exponent vectors with no attached unit), so Quantity[D] loses its dimension.",
        "SymPy has no constrained-optimisation solver; `minimise`/`maximise` with "
        "`require` constraints is emitted as a commented setup, never solved.",
        "The generated Python is executed by nothing in this repository except the "
        "backend test suite, which only checks that it runs without raising.",
    )

    def __init__(self, module, symbols=None) -> None:
        super().__init__(module, symbols)
        #: HML name -> emitted Python name (used for concept-scope flattening)
        self._alias: dict[str, str] = {}
        self._declared: list[str] = []
        #: HML names whose emission was DROPPED. A reference to one of these must also be
        #: dropped, or the generated module raises NameError on import.
        #:
        #: Measured defect: `def p := forall y : Real . y > x` followed by `prove p` emitted
        #: `claims.append(p)` for a `p` that was never assigned, because SymPy has no
        #: quantifiers so the definition was silently skipped. Rendering the file looked
        #: fine; only EXECUTING it revealed the failure. Found by the interoperability
        #: agent running the output rather than inspecting it.
        self._dropped_names: set[str] = set()

    # -- entry point ------------------------------------------------------

    def emit(self) -> str:
        head: list[str] = [
            '"""SymPy translation of Hamiltonian Lang module '
            f'{self.module.name}.',
            "",
            "Generated code. Losses are listed in the backend report, not here.",
            '"""',
            "",
            "import sympy",
            "",
            "definitions = {}",
            "requirements = []       # from `require` -- obligations, not facts",
            "claims = []             # from `prove` -- stated, never proved here",
            "assumptions = []        # from `assume`",
            "type_constraints = []   # refinements SymPy assumptions cannot carry",
            "objective = None",
            "objective_direction = None",
            "solve_targets = []",
            "",
        ]

        body: list[str] = []
        for st in self.module.statements:
            body.extend(self._statement(st))

        tail = [
            "",
            "symbols_by_name = {",
        ]
        tail.extend(f"    {n!r}: {n}," for n in self._declared)
        tail.append("}")
        return "\n".join(head + body + tail) + "\n"

    # -- statements -------------------------------------------------------

    def _statement(self, st: Statement) -> list[str]:
        if isinstance(st, ModuleDecl):
            return []

        if isinstance(st, Declaration):
            return self._declaration(st)

        if isinstance(st, DefineStmt):
            return self._define(st)

        if isinstance(st, LawStmt):
            cond = " | " + " ".join(g.name for g in st.given) if st.given else ""
            family = st.distribution.family if st.distribution else "?"
            roles = (
                ", ".join(f"{a.role} := ..." for a in st.distribution.args)
                if st.distribution
                else ""
            )
            self.drop(
                f"{st.role} {st.target}{cond}",
                "SymPy has no probability-law object that carries a role "
                f"({st.role}), a conditioning set, or an inference target. "
                "sympy.stats can build a random symbol for the "
                f"{family} family, but doing so would reproduce the family and its "
                "parameters while silently discarding the rest of the statement, so "
                "nothing is emitted.",
                st.span.line,
            )
            return [f"# DROPPED law: {st.role} {st.target}{cond} ~ {family}({roles})"]

        if isinstance(st, RequireStmt):
            rendered = self.expr(st.proposition)
            if rendered is None:
                return []
            return [f"requirements.append({rendered})"]

        if isinstance(st, AssumeStmt):
            rendered = self.expr(st.proposition)
            if rendered is None:
                return []
            self.weaken(
                "assume",
                "the proposition is built as a SymPy relational object but SymPy has "
                "no assumption *context*: nothing downstream will use it as a "
                "hypothesis, so it is inert data rather than an active assumption.",
                st.span.line,
            )
            return [f"assumptions.append({rendered})"]

        if isinstance(st, ProveStmt):
            rendered = self.expr(st.proposition)
            if rendered is None:
                return []
            self.weaken(
                "prove",
                "the claim becomes a SymPy relational object. SymPy is not a prover; "
                "the statement is recorded, not discharged (design freeze §8).",
                st.span.line,
            )
            return [f"claims.append({rendered})"]

        if isinstance(st, CheckStmt):
            if st.check_kind == "dimension":
                self.drop(
                    "check dimension",
                    "HML dimensions are bare rational-exponent vectors with no unit "
                    "attached; sympy.physics.units works in units, not dimensions, so "
                    "there is nothing to map onto without inventing a unit per "
                    "dimension.",
                    st.span.line,
                )
                subj = self.expr(st.subject) if st.subject is not None else "?"
                return [
                    f"# DROPPED check dimension: [{subj}] = {st.expected or '?'}"
                ]
            rendered = self.expr(st.subject) if st.subject is not None else None
            if rendered is None:
                return []
            self.weaken(
                "check",
                "the checked proposition becomes an inert SymPy relational; no "
                "checking is performed by the generated file.",
                st.span.line,
            )
            return [f"claims.append({rendered})"]

        if isinstance(st, ObjectiveStmt):
            rendered = self.expr(st.expression)
            if rendered is None:
                return []
            self.weaken(
                st.direction,
                "the objective *expression* is preserved exactly, but SymPy has no "
                "constrained-optimisation facility: with `require` constraints present "
                "this needs a KKT system the backend will not fabricate. Emitted as a "
                "commented setup.",
                st.span.line,
            )
            return [
                f"objective = {rendered}",
                f"objective_direction = {st.direction!r}",
                "# Optimisation setup (not executed -- SymPy has no constrained "
                "optimiser):",
                "#   stationarity = [sympy.diff(objective, v) for v in "
                "objective.free_symbols]",
                "#   unconstrained critical points: sympy.solve(stationarity, "
                "list(objective.free_symbols), dict=True)",
                "#   with `requirements` present the correct system is the KKT "
                "conditions,",
                "#   which must be written out by hand.",
            ]

        if isinstance(st, SolveStmt):
            names = [self._ref_name(t.name) for t in st.targets]
            self.weaken(
                "solve",
                "the solve targets are recorded, but SymPy's solvers need a system of "
                "*equations*; the HML `require` constraints here are inequalities, and "
                "sympy.solve does not handle multivariate inequality systems. No solve "
                "call is emitted.",
                st.span.line,
            )
            return [
                f"solve_targets = [{', '.join(names)}]",
                "# sympy.solve(requirements, solve_targets) is NOT emitted: "
                "requirements",
                "# are inequalities and SymPy has no multivariate inequality solver.",
            ]

        if isinstance(st, InferStmt):
            targets = ", ".join(t.name for t in st.targets)
            self.drop(
                f"infer {st.query}",
                "SymPy has no inference engine. sympy.stats can compute an "
                "expectation for a random symbol it constructed, but the laws this "
                "query ranges over were themselves dropped, so there is nothing to "
                "compute over.",
                st.span.line,
            )
            return [f"# DROPPED inference: infer {st.query} {targets}"]

        if isinstance(st, ConceptDecl):
            return self._concept(st)

        return []

    # -- declarations -----------------------------------------------------

    def _declaration(self, st: Declaration) -> list[str]:
        lines = self._declare_symbol(st.name, st.declared_type, st.span.line, st.kind)
        if st.value is not None:
            rendered = self.expr(st.value)
            if rendered is not None:
                self.weaken(
                    f"{st.kind} {st.name} value",
                    "SymPy has no notion of an observed or constant binding; the value "
                    "is recorded as an equation in `requirements` rather than "
                    "substituted, so the symbol stays free.",
                    st.span.line,
                )
                lines.append(
                    f"requirements.append(sympy.Eq({self._ref_name(st.name)}, "
                    f"{rendered}))"
                )
        return lines

    def _declare_symbol(
        self, name: str, t: Type | None, line: int, kind: str = "var"
    ) -> list[str]:
        py = self._ref_name(name)
        # SymPy has exactly one kind of symbol. `kind` (var/param/const/obs/index) is
        # a fact about the model's epistemology and has no SymPy encoding at all; it
        # is accepted here only so callers can pass it, and is otherwise discarded.
        del kind
        expr = self._symbol_expr(name, py, t, line)
        if expr is None:
            return []
        self._declared.append(py)
        out = [f"{py} = {expr}"]
        bound = self._upper_bound_constraint(py, t)
        if bound is not None:
            out.append(f"type_constraints.append({bound})")
        return out

    def _symbol_expr(
        self, hml_name: str, py: str, t: Type | None, line: int
    ) -> str | None:
        if t is None or isinstance(t, UnknownType):
            self.approximate(
                hml_name,
                "no resolved HML type; an unconstrained sympy.Symbol is emitted and "
                "every refinement is lost.",
                line,
            )
            return f"sympy.Symbol({py!r})"

        if isinstance(t, ScalarType):
            return f"sympy.Symbol({py!r}{self._assumption_suffix(hml_name, t, line)})"

        if isinstance(t, QuantityType):
            self.weaken(
                hml_name,
                f"the dimension {t.dimension.render()} is dropped; the symbol keeps "
                "only the assumptions of its base scalar.",
                line,
            )
            return (
                f"sympy.Symbol({py!r}{self._assumption_suffix(hml_name, t.base, line)})"
            )

        if isinstance(t, RandomVariableType):
            self.weaken(
                hml_name,
                "SymPy has no measurable-function type. The random variable is "
                f"emitted as a plain symbol over its codomain "
                f"({t.codomain.render()}); its randomness and the separation between "
                "RandomVariable[T] and T are lost.",
                line,
            )
            return self._symbol_expr(hml_name, py, t.codomain, line)

        if isinstance(t, VectorType):
            n = _extent_expr(t.length)
            if n is None:
                self.drop(
                    hml_name,
                    "a vector of unknown length has no MatrixSymbol shape.",
                    line,
                )
                return None
            if not _is_plain_real(t.element):
                self.drop(
                    f"{hml_name} element type",
                    f"MatrixSymbol carries no element assumptions, so the element "
                    f"refinement {t.element.render()} is lost.",
                    line,
                )
            self.approximate(
                hml_name,
                "SymPy has no vector type; Vector[T, n] becomes an n-by-1 "
                "MatrixSymbol, which is a column-matrix approximation rather than a "
                "vector.",
                line,
            )
            return f"sympy.MatrixSymbol({py!r}, {n}, 1)"

        if isinstance(t, MatrixType):
            r, c = _extent_expr(t.rows), _extent_expr(t.cols)
            if r is None or c is None:
                self.drop(
                    hml_name, "a matrix of unknown extent has no MatrixSymbol shape.",
                    line,
                )
                return None
            if not _is_plain_real(t.element):
                self.drop(
                    f"{hml_name} element type",
                    f"MatrixSymbol carries no element assumptions, so the element "
                    f"refinement {t.element.render()} is lost.",
                    line,
                )
            return f"sympy.MatrixSymbol({py!r}, {r}, {c})"

        if isinstance(t, TensorType):
            self.drop(
                hml_name,
                "SymPy has no rank-n symbolic tensor with the shape discipline HML "
                "declares (sympy.tensor.Array needs concrete entries).",
                line,
            )
            return None

        if isinstance(t, PropositionType):
            self.drop(
                hml_name,
                "SymPy has no free proposition symbol usable in relational algebra; "
                "boolean symbols exist but do not interoperate with the relational "
                "objects this backend builds.",
                line,
            )
            return None

        for cls, why in (
            (DistributionType, "SymPy has no first-class distribution value"),
            (SetType, "SymPy sets need concrete elements or an explicit interval"),
            (FunctionType, "SymPy's Function is applied, not a declarable value here"),
            (PredicateType, "SymPy has no predicate type"),
            (ConceptType, "SymPy has no concept mechanism"),
        ):
            if isinstance(t, cls):
                self.drop(hml_name, f"{why}; the declaration is omitted.", line)
                return None

        self.drop(hml_name, f"no SymPy encoding for type {t.render()}", line)
        return None

    def _assumption_suffix(self, hml_name: str, t: ScalarType, line: int) -> str:
        assumptions, extra = SCALAR_ASSUMPTIONS.get(t.name, ({}, None))
        if t.name == "Bool":
            self.approximate(
                hml_name,
                "SymPy's assumption system has no boolean-valued Symbol that works in "
                "the relational algebra used here; an unconstrained Symbol is emitted.",
                line,
            )
        if extra is not None:
            self.weaken(
                hml_name,
                f"SymPy assumptions cannot express the upper bound of {t.name}; the "
                "lower half becomes an assumption and the upper half is appended to "
                "`type_constraints`, where nothing enforces it.",
                line,
            )
        if not assumptions:
            return ""
        return "".join(f", {k}=True" for k in sorted(assumptions))

    def _upper_bound_constraint(self, py: str, t: Type | None) -> str | None:
        base: ScalarType | None = None
        if isinstance(t, ScalarType):
            base = t
        elif isinstance(t, QuantityType):
            base = t.base
        elif isinstance(t, RandomVariableType) and isinstance(t.codomain, ScalarType):
            base = t.codomain
        if base is None:
            return None
        extra = SCALAR_ASSUMPTIONS.get(base.name, ({}, None))[1]
        return None if extra is None else extra.format(name=py)

    def _define(self, st: DefineStmt) -> list[str]:
        py = self._ref_name(st.name)
        if st.params:
            args = [_py_name(p) for p, _ in st.params]
            pre = [f"{a} = sympy.Symbol({a!r})" for a in args]
            body = self.expr(st.body)
            if body is None:
                self._dropped_names.add(st.name)
                return [
                    f"# DROPPED definition {st.name}: no SymPy encoding for its body; "
                    f"references to it are dropped too"
                ]
            self.approximate(
                f"def {st.name}",
                "the parameter types are not carried onto the Lambda's bound symbols; "
                "SymPy Lambda arguments are untyped, so any refinement on them is "
                "lost.",
                st.span.line,
            )
            self._declared.append(py)
            return pre + [
                f"{py} = sympy.Lambda(({', '.join(args)},), {body})",
                f"definitions[{st.name!r}] = {py}",
            ]
        body = self.expr(st.body)
        if body is None:
            self._dropped_names.add(st.name)
            return [
                f"# DROPPED definition {st.name}: no SymPy encoding for its body; "
                f"references to it are dropped too"
            ]
        self._declared.append(py)
        return [f"{py} = {body}", f"definitions[{st.name!r}] = {py}"]

    # -- concepts ---------------------------------------------------------

    def _concept(self, st: ConceptDecl) -> list[str]:
        self.weaken(
            f"concept {st.name}",
            "SymPy has no namespace for symbols, so the concept's scope is flattened "
            f"by name-mangling every member to {st.name}__<member>. The concept "
            "itself, its `extends` relation and the distinction between an invariant, "
            "an example and a counterexample do not survive as structure.",
            st.span.line,
        )
        if st.extends:
            self.drop(
                f"concept {st.name} extends",
                "there is no SymPy encoding of concept inheritance; the parents ("
                + ", ".join(st.extends)
                + ") are dropped.",
                st.span.line,
            )
        lines = [f"# --- concept {st.name} (scope flattened by name-mangling) ---"]
        saved = dict(self._alias)
        for m in st.members:
            self._alias[m.name] = f"{_py_name(st.name)}__{_py_name(m.name)}"
        for m in st.members:
            lines.extend(self._concept_member(st, m))
        self._alias = saved
        return lines

    def _untyped_param(self, decl: ConceptDecl, m: ConceptMember, p: str) -> str:
        """Report a transform parameter with no declared HML type. Returns no suffix."""
        self.approximate(
            f"{decl.name}.{m.name} parameter {p}",
            "the parameter carries no declared HML type, so the SymPy symbol gets no "
            "assumptions at all; any refinement the transform relies on is lost.",
            m.span.line,
        )
        return ""

    def _concept_member(self, decl: ConceptDecl, m: ConceptMember) -> list[str]:
        py = self._alias[m.name]
        if m.kind == "parameter":
            return self._declare_symbol(m.name, m.declared_type, m.span.line)
        if m.kind == "transform":
            # ConceptMember.params is (name, declared type) pairs; the type is
            # optional (D-015), so fall back to an unconstrained symbol and say so.
            args = [_py_name(p) for p, _ in m.params]
            pre = [
                f"{_py_name(p)} = sympy.Symbol({_py_name(p)!r}"
                + (
                    self._assumption_suffix(p, pt, m.span.line)
                    if isinstance(pt, ScalarType)
                    else self._untyped_param(decl, m, p)
                )
                + ")"
                for p, pt in m.params
            ]
            body = self.expr(m.body) if m.body is not None else None
            if body is None:
                self.drop(
                    f"{decl.name}.{m.name}",
                    "transform has no body to translate.",
                    m.span.line,
                )
                return []
            self._declared.append(py)
            return pre + [f"{py} = sympy.Lambda(({', '.join(args)},), {body})"]
        if m.kind in ("invariant", "property"):
            body = self.expr(m.body) if m.body is not None else None
            if body is None:
                return []
            self.weaken(
                f"{decl.name}.{m.name}",
                f"the {m.kind} becomes an inert SymPy relational appended to "
                "`claims`; SymPy will not check it against the concept.",
                m.span.line,
            )
            self._declared.append(py)
            return [f"{py} = {body}", f"claims.append({py})"]
        if m.kind in ("example", "counterexample"):
            body = self.expr(m.body) if m.body is not None else None
            self.weaken(
                f"{decl.name}.{m.name}",
                f"a {m.kind} is a *witness* claim about the concept. SymPy has no "
                "place to attach it, so it is emitted as a bare relational object; "
                "the fact that it is a witness (and, for a counterexample, that it is "
                "meant to refute something) is lost.",
                m.span.line,
            )
            if body is None:
                return [f"# {m.kind} {decl.name}.{m.name}: no body"]
            self._declared.append(py)
            return [f"{py} = {body}  # {m.kind}"]
        self.drop(
            f"{decl.name}.{m.name}",
            f"concept member kind {m.kind!r} has no SymPy encoding.",
            m.span.line,
        )
        return []

    # -- expressions ------------------------------------------------------

    def _ref_name(self, name: str) -> str:
        return self._alias.get(name, _py_name(name))

    def expr(self, e: Expr | None) -> str | None:
        r = self._expr(e)
        return None if r is None else r[0]

    def _wrap(self, e: Expr | None, outer: int, *, right: bool = False) -> str:
        r = self._expr(e)
        if r is None:
            return "None"
        text, prec = r
        if prec < outer or (right and prec == outer):
            return f"({text})"
        return text

    def _expr(self, e: Expr | None) -> tuple[str, int] | None:
        if e is None:
            return None

        if isinstance(e, Literal):
            if isinstance(e.value, bool):
                return ("sympy.true" if e.value else "sympy.false"), _ATOM
            raw = e.raw or repr(e.value)
            # Exact by construction: Rational('0.5') is 1/2, not a binary float.
            return f"sympy.Rational({raw!r})", _ATOM

        if isinstance(e, Ref):
            if e.name in self._dropped_names:
                # Propagate the drop instead of emitting a name that was never bound.
                self.drop(
                    f"reference to {e.name}",
                    f"{e.name!r} has no SymPy encoding, so every expression mentioning "
                    f"it is dropped as well; emitting the bare name would produce a "
                    f"module that raises NameError on import.",
                    e.span.line,
                )
                # `None` is this function's established "no encoding" signal; callers
                # already propagate it, which is what drops the enclosing expression.
                return None
            return self._ref_name(e.name), _ATOM

        if isinstance(e, UnaryOp):
            if e.op == "not":
                inner = self.expr(e.operand)
                return (f"sympy.Not({inner})" if inner else "None"), _ATOM
            p = _PREC["unary"]
            return f"-{self._wrap(e.operand, p)}", p

        if isinstance(e, BinOp):
            if e.op == "^":
                p = _PREC["^"]
                return (
                    f"{self._wrap(e.left, p, right=True)} ** {self._wrap(e.right, p)}",
                    p,
                )
            if e.op == "@":
                # SymPy spells MatrixSymbol composition with `*`.
                p = _PREC["*"]
                self.weaken(
                    "matrix product",
                    "HML's `@` is a dedicated matrix/vector product; SymPy overloads "
                    "`*` for it, so the operator no longer distinguishes matrix "
                    "product from scalar multiplication.",
                    e.span.line,
                )
                return (
                    f"{self._wrap(e.left, p)} * {self._wrap(e.right, p, right=True)}",
                    p,
                )
            p = _PREC.get(e.op, 6)
            return (
                f"{self._wrap(e.left, p)} {e.op} {self._wrap(e.right, p, right=True)}",
                p,
            )

        if isinstance(e, Comparison):
            fn = _REL[e.op]
            left, right = self.expr(e.left), self.expr(e.right)
            if left is None or right is None:
                return None
            return f"{fn}({left}, {right})", _ATOM

        if isinstance(e, LogicalOp):
            fn = _LOGIC[e.op]
            left, right = self.expr(e.left), self.expr(e.right)
            if left is None or right is None:
                return None
            return f"{fn}({left}, {right})", _ATOM

        if isinstance(e, Call):
            args = [self.expr(a) for a in e.args]
            if any(a is None for a in args):
                return None
            rendered = ", ".join(a for a in args if a is not None)
            if e.callee in _KNOWN_CALLS:
                return f"{_KNOWN_CALLS[e.callee]}({rendered})", _ATOM
            if e.callee in self._alias:
                # a concept transform, emitted as a sympy.Lambda
                return f"{self._alias[e.callee]}({rendered})", _ATOM
            self.approximate(
                f"call {e.callee}",
                "not a SymPy built-in and not a known definition; emitted as an "
                "uninterpreted sympy.Function, which has no defining equation.",
                e.span.line,
            )
            return f"sympy.Function({e.callee!r})({rendered})", _ATOM

        if isinstance(e, Index):
            base = self.expr(e.base)
            idx = [self.expr(i) for i in e.indices]
            if base is None or any(i is None for i in idx):
                return None
            self.weaken(
                "index expression",
                "SymPy MatrixSymbol subscripts are 0-based and require an integer "
                "index; HML fixes no index origin, so the subscript may be off by one.",
                e.span.line,
            )
            return f"{base}[{', '.join(i for i in idx if i is not None)}]", _ATOM

        if isinstance(e, DistExpr):
            self.drop(
                f"{e.family} distribution expression",
                "see the module docstring: emitting sympy.stats here would preserve "
                "the family and its parameters while discarding the law's role and "
                "conditioning set, which is worse than emitting nothing.",
                e.span.line,
            )
            return None

        if isinstance(e, Quantifier):
            self.drop(
                f"{e.kind} quantifier",
                "SymPy has no first-order quantifier. sympy.Q is a predicate "
                "namespace, not a binder, so quantifier nesting order -- the exact "
                "property this language exists to make explicit -- cannot be "
                "represented at all.",
                e.span.line,
            )
            return None

        self.drop(
            "expression", f"no SymPy encoding for {type(e).__name__}", e.span.line
        )
        return None


def _extent_expr(n: str | int | None) -> str | None:
    if n is None:
        return None
    return _py_name(str(n)) if isinstance(n, str) else str(n)


def _is_plain_real(t: Type) -> bool:
    return isinstance(t, ScalarType) and t.name == "Real"


def to_sympy(module, symbols=None):
    return SympyBackend(module, symbols).run()
