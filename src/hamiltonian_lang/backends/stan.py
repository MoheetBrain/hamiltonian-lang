"""Stan code generation.

Stan is an *executable* target: the emitted program is meant to be compiled by
``stanc`` and run. That makes silent loss far more dangerous here than in a
presentation backend, because a wrong program still runs and still produces numbers.

The single load-bearing job of this backend is the **role -> position** mapping.
Hamiltonian Lang names every distribution argument by its semantic role
(``Normal(location := mu, scale := sigma)``); Stan takes them positionally
(``normal(mu, sigma)``). The translation table :data:`STAN_DISTRIBUTIONS` is therefore
written once, explicitly, as an ordered tuple of roles per family, and is cross-checked
against :mod:`hamiltonian_lang.type_system.distributions` by
:func:`audit_distribution_table`. A mismatch there is a silent correctness bug of
exactly the kind the language exists to prevent, so it is asserted in the test suite
rather than trusted.

Declared losses
---------------
* Stan is dimensionless: ``Quantity[D]`` becomes ``real`` and the dimension vector is
  gone. ``check dimension`` has no Stan encoding at all.
* Stan has no quantifiers, no propositions, no proof obligations. ``require``,
  ``prove``, ``assume`` and ``check`` are emitted as comments and reported as dropped.
* Stan's sampling statement carries no conditioning set and no prior/likelihood
  distinction; ``prior``, ``likelihood`` and ``law`` all become ``~``.
* Stan has no exact rationals and no ``Set``/``Function``/``Predicate`` types.
* ``HalfNormal`` has no Stan density. It is realised the idiomatic way, as
  ``normal(0, scale)`` on a variable whose declaration carries ``<lower=0>``. The
  truncation therefore lives in the *declaration*, not in the sampling statement; if
  the declared type does not induce a lower bound the emitted model is a full normal
  and the backend says so.

No Stan toolchain is invoked by this module. Nothing here has been validated by
``stanc``; the structural checks in ``tests/backends/test_stan.py`` are the only
verification performed.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ast.nodes import (
    Arg,
    AssumeStmt,
    BinOp,
    Call,
    CheckStmt,
    Comparison,
    ConceptDecl,
    Declaration,
    DeclKind,
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
    walk,
)
from ..type_system.distributions import DISTRIBUTIONS
from ..types import (
    UNIT_INTERVAL_KINDS,
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

__all__ = [
    "StanBackend",
    "to_stan",
    "STAN_DISTRIBUTIONS",
    "StanDist",
    "stan_signature",
    "audit_distribution_table",
]


# ---------------------------------------------------------------------------
# The role -> position table. This is the point of the backend.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StanDist:
    """A Stan density and the HML roles that fill its positional slots, in order.

    A slot beginning with ``"#"`` is a literal constant injected by the translation
    (used only by ``HalfNormal``, whose location slot is a hard 0). Every other slot
    is an HML role name that must exist in the registry for this family.
    """

    fn: str
    slots: tuple[str, ...]
    fidelity: str = "exact"  # exact | approximated | weakened
    reason: str = ""
    #: True when the emitted density is only correct because the *declaration* of the
    #: sampled variable carries a constraint (Stan's truncation-by-declaration idiom).
    needs_lower_bound: bool = False

    @property
    def roles(self) -> tuple[str, ...]:
        """The HML role names, in Stan positional order, literals excluded."""
        return tuple(s for s in self.slots if not s.startswith("#"))


#: HML family name -> Stan density with its argument order.
#:
#: Every ordering below is stated explicitly rather than inferred from dict order in
#: the registry, because dict order is an implementation detail and the argument order
#: of a density is a correctness property.
STAN_DISTRIBUTIONS: dict[str, StanDist] = {
    # normal(mu, sigma) -- Stan's second argument is the standard deviation.
    "Normal": StanDist("normal", ("location", "scale")),
    # Stan has no half_normal. The idiom is a lower-bounded declaration plus a normal
    # centred at 0: `real<lower=0> sigma; sigma ~ normal(0, s);`
    "HalfNormal": StanDist(
        "normal",
        ("#0", "scale"),
        "approximated",
        "Stan has no half_normal density; emitted as normal(0, scale), which is a "
        "half-normal only because the sampled variable's declaration carries "
        "<lower=0>. The truncation lives in the declaration, not in this statement.",
        needs_lower_bound=True,
    ),
    "LogNormal": StanDist("lognormal", ("location", "scale")),
    # student_t(nu, mu, sigma)
    "StudentT": StanDist("student_t", ("degrees_of_freedom", "location", "scale")),
    "Cauchy": StanDist("cauchy", ("location", "scale")),
    "Uniform": StanDist("uniform", ("lower", "upper")),
    # beta(alpha, beta) -- both shape parameters, alpha first.
    "Beta": StanDist("beta", ("alpha", "beta")),
    "Bernoulli": StanDist("bernoulli", ("prob",)),
    # binomial(N, theta) -- the count comes first, the probability second.
    "Binomial": StanDist("binomial", ("trials", "prob")),
    # Stan's poisson is rate-parameterised, matching HML's `rate` role.
    "Poisson": StanDist("poisson", ("rate",)),
    # Stan's exponential is rate-parameterised (beta = rate), matching HML.
    "Exponential": StanDist("exponential", ("rate",)),
    # gamma(alpha, beta) is shape-rate in Stan, matching HML's shape/rate roles.
    "Gamma": StanDist("gamma", ("shape", "rate")),
    # inv_gamma(alpha, beta) is shape-scale, matching HML's shape/scale roles.
    "InverseGamma": StanDist("inv_gamma", ("shape", "scale")),
    "Dirichlet": StanDist("dirichlet", ("concentration",)),
    "Categorical": StanDist(
        "categorical",
        ("probs",),
        "weakened",
        "Stan's categorical outcomes are 1-based indices into the probability "
        "simplex; HML's support is Natural, which includes 0. The index origin is "
        "not preserved.",
    ),
    # An i.i.d. vector of normals with a shared scale is exactly what Stan's
    # vectorised normal statement means.
    "NormalVector": StanDist(
        "normal",
        ("location", "scale"),
        "approximated",
        "emitted as Stan's vectorised normal sampling statement; the i.i.d. structure "
        "is implied by Stan's broadcasting rules rather than stated.",
    ),
}


def stan_signature(family: str) -> StanDist | None:
    return STAN_DISTRIBUTIONS.get(family)


def audit_distribution_table() -> list[str]:
    """Cross-check :data:`STAN_DISTRIBUTIONS` against the HML distribution registry.

    Returns a list of human-readable problems; empty means the two agree. This is
    called by the test suite, not at import time, so that a registry addition fails a
    test rather than breaking every import.
    """
    problems: list[str] = []
    for name, spec in DISTRIBUTIONS.items():
        mapped = STAN_DISTRIBUTIONS.get(name)
        if mapped is None:
            problems.append(f"{name}: no Stan mapping")
            continue
        registry_roles = set(spec.roles)
        mapped_roles = set(mapped.roles)
        if mapped_roles != registry_roles:
            problems.append(
                f"{name}: Stan slots {sorted(mapped_roles)} != registry roles "
                f"{sorted(registry_roles)}"
            )
        if len(mapped.roles) != len(set(mapped.roles)):
            problems.append(f"{name}: duplicate role in Stan slot list")
    for name in STAN_DISTRIBUTIONS:
        if name not in DISTRIBUTIONS:
            problems.append(f"{name}: mapped to Stan but absent from the HML registry")
    return problems


# ---------------------------------------------------------------------------
# Names and operators
# ---------------------------------------------------------------------------

_STAN_RESERVED = {
    "for", "in", "while", "repeat", "until", "if", "then", "else", "true", "false",
    "return", "break", "continue", "void", "int", "real", "complex", "vector",
    "simplex", "unit_vector", "ordered", "positive_ordered", "row_vector", "matrix",
    "cholesky_factor_corr", "cholesky_factor_cov", "corr_matrix", "cov_matrix",
    "array", "functions", "data", "transformed", "parameters", "model", "generated",
    "quantities", "print", "reject", "target", "lower", "upper", "offset",
    "multiplier", "profile", "fatal_error",
}

# Stan expression precedence, high binds tighter.
_PREC = {
    "iff": 1, "implies": 2, "or": 3, "and": 4,
    "=": 5, "!=": 5, "<": 5, "<=": 5, ">": 5, ">=": 5,
    "+": 6, "-": 6,
    "*": 7, "/": 7, "@": 7,
    "unary": 8,
    "^": 9,
}
_ATOM = 100


def _stan_name(name: str) -> str:
    return f"{name}_" if name in _STAN_RESERVED else name


def _extent(n: str | int | None) -> str | None:
    if n is None:
        return None
    return _stan_name(str(n)) if isinstance(n, str) else str(n)


#: Scalar types whose Stan declaration carries a lower bound of 0 (or higher).
_LOWER_BOUNDED_SCALARS = frozenset(
    {
        "PositiveReal", "NonNegativeReal", "Probability", "Natural",
        "PositiveNatural", "Bool",
    }
)


def _induces_lower_bound(t: Type | None) -> bool:
    """Whether the Stan declaration for ``t`` restricts the variable to >= 0.

    Used to decide whether a ``HalfNormal`` law is actually realised as a half-normal
    in the emitted program, or has silently become a full normal.
    """
    if isinstance(t, ScalarType):
        return t.name in _LOWER_BOUNDED_SCALARS
    if isinstance(t, QuantityType):
        return t.base.name in _LOWER_BOUNDED_SCALARS
    if isinstance(t, RandomVariableType):
        return _induces_lower_bound(t.codomain)
    if isinstance(t, VectorType):
        return _induces_lower_bound(t.element)
    if isinstance(t, MatrixType):
        return _induces_lower_bound(t.element)
    return False


class StanBackend(Backend):
    target = "stan"
    limitations = (
        "Stan is dimensionless and has no exact rationals: Quantity[D] collapses to "
        "real and the dimension vector is unrecoverable.",
        "Stan has no propositions, quantifiers or proof obligations: require, prove, "
        "assume and check have no encoding and are emitted as comments only.",
        "Stan's `~` carries no conditioning set and no prior/likelihood distinction; "
        "all three HML law roles collapse to the same statement form.",
        "Stan does not distinguish RandomVariable[T] from a value of T; the "
        "three-way separation of T, RandomVariable[T] and Distribution[T] is lost.",
        "Constraint intervals are attached to *declarations*, not to statements, so "
        "some density translations (notably HalfNormal) are correct only in "
        "combination with the declared type of the sampled variable.",
        "No stanc toolchain is invoked by this backend; the emitted program has not "
        "been compiled or validated by any Stan implementation.",
    )

    def __init__(self, module, symbols=None) -> None:
        super().__init__(module, symbols)
        self._data_names: set[str] = set()
        self._param_names: set[str] = set()
        #: symbol name -> True when its Stan declaration carries a lower bound at 0
        self._lower_bounded: dict[str, bool] = {}

    # -- entry point ------------------------------------------------------

    def emit(self) -> str:
        self.report_reasoning_loss()
        self._classify()

        header: list[str] = [
            f"// Stan program generated from Hamiltonian Lang module {self.module.name}.",
            "// Generated code. Not compiled or validated by stanc.",
        ]
        header.extend(self._fixed_data_comment())

        data: list[str] = []
        tdata: list[str] = []
        params: list[str] = []
        tparams: list[str] = []
        functions: list[str] = []
        model: list[str] = []
        genq: list[str] = []

        for st in self.module.statements:
            self._statement(st, data, tdata, params, tparams, functions, model, genq)

        out = list(header)
        for name, body in (
            ("functions", functions),
            ("data", data),
            ("transformed data", tdata),
            ("parameters", params),
            ("transformed parameters", tparams),
        ):
            if body:
                out.append("")
                out.append(f"{name} {{")
                out.extend("  " + line for line in body)
                out.append("}")
        # The model block is always emitted: a Stan program without one is legal but
        # meaningless, and an empty one makes the emptiness explicit.
        out.append("")
        out.append("model {")
        out.extend("  " + line for line in model)
        out.append("}")
        if genq:
            out.append("")
            out.append("generated quantities {")
            out.extend("  " + line for line in genq)
            out.append("}")
        return "\n".join(out) + "\n"

    # -- classification ---------------------------------------------------

    def _classify(self) -> None:
        for st in self.module.statements:
            if isinstance(st, Declaration):
                # Precomputed independently of emission order, because a law may
                # textually precede the declaration of the variable it constrains and
                # HalfNormal's correctness depends on the declared bound.
                self._lower_bounded[st.name] = _induces_lower_bound(st.declared_type)
                if st.kind in (DeclKind.OBS, DeclKind.CONST, DeclKind.INDEX):
                    self._data_names.add(st.name)
                else:
                    self._param_names.add(st.name)
            elif isinstance(st, DefineStmt):
                # A definition is data-only when it mentions no parameter.
                if self._refs_parameters(st.body):
                    self._param_names.add(st.name)
                else:
                    self._data_names.add(st.name)

    def _refs_parameters(self, e: Expr | None) -> bool:
        if e is None:
            return False
        return any(
            isinstance(n, Ref) and n.name in self._param_names for n in walk(e)
        )

    def _fixed_data_comment(self) -> list[str]:
        fixed = [
            (st.name, self.expr(st.value))
            for st in self.module.statements
            if isinstance(st, Declaration)
            and st.value is not None
            and st.kind in (DeclKind.OBS, DeclKind.CONST, DeclKind.INDEX)
        ]
        if not fixed:
            return []
        lines = [
            "//",
            "// Values fixed in the HML source. Stan takes data from the data file, "
            "not from",
            "// the program text, so these are recorded here and must be supplied at "
            "run time:",
        ]
        lines.extend(f"//   {n} = {v}" for n, v in fixed)
        return lines

    # -- statements -------------------------------------------------------

    def _statement(
        self,
        st: Statement,
        data: list[str],
        tdata: list[str],
        params: list[str],
        tparams: list[str],
        functions: list[str],
        model: list[str],
        genq: list[str],
    ) -> None:
        if isinstance(st, ModuleDecl):
            return

        if isinstance(st, Declaration):
            self._declaration(st, data, params)
            return

        if isinstance(st, DefineStmt):
            self._define(st, tdata, tparams, functions)
            return

        if isinstance(st, LawStmt):
            self._law(st, model)
            return

        if isinstance(st, RequireStmt):
            self.drop(
                "require",
                "Stan cannot state a hard constraint on parameters. Expressing it "
                "would need either a <lower=>/<upper=> declaration bound or a "
                "reject() call, and reject() truncates the posterior discontinuously; "
                "neither is a faithful translation, so the constraint is emitted as a "
                "comment only.",
                st.span.line,
            )
            model.append(f"// require: {self.expr(st.proposition)}   (NOT ENFORCED)")
            return

        if isinstance(st, AssumeStmt):
            self.drop(
                "assume",
                "Stan has no assumption context; the proposition is unrepresentable "
                "and is emitted as a comment.",
                st.span.line,
            )
            model.append(f"// assume: {self.expr(st.proposition)}")
            return

        if isinstance(st, ProveStmt):
            self.drop(
                "prove",
                "Stan is a probabilistic programming language, not a prover; a proof "
                "obligation has no Stan encoding.",
                st.span.line,
            )
            model.append(f"// prove: {self.expr(st.proposition)}   (NOT PROVED)")
            return

        if isinstance(st, CheckStmt):
            if st.check_kind == "dimension":
                subject = self.expr(st.subject) if st.subject is not None else "?"
                self.drop(
                    "check dimension",
                    "Stan has no dimensional analysis; the asserted dimension "
                    f"({st.expected or '?'}) cannot be carried into the program.",
                    st.span.line,
                )
                model.append(f"// check dimension: [{subject}] = {st.expected or '?'}")
            else:
                self.drop(
                    "check",
                    "Stan has no proposition type; the check is emitted as a comment.",
                    st.span.line,
                )
                if st.subject is not None:
                    model.append(f"// check: {self.expr(st.subject)}")
            return

        if isinstance(st, ObjectiveStmt):
            self.drop(
                f"{st.direction}",
                "the Stan *language* has no objective statement. Stan's interfaces "
                "can maximise the log density (`optimize`), but that is a different "
                "objective from the one written here and substituting it would be a "
                "fabrication.",
                st.span.line,
            )
            model.append(
                f"// {st.direction}: {self.expr(st.expression)}   (NO STAN ENCODING)"
            )
            return

        if isinstance(st, SolveStmt):
            self.drop(
                "solve",
                "Stan has no deterministic solver statement; algebra_solver exists but "
                "solves user-supplied systems of equations, which is not what `solve` "
                "means here.",
                st.span.line,
            )
            model.append(
                "// solve for: " + ", ".join(_stan_name(t.name) for t in st.targets)
            )
            return

        if isinstance(st, InferStmt):
            names = ", ".join(_stan_name(t.name) for t in st.targets)
            mapping = {
                "posterior": "this is Stan's default: run the sampler",
                "mle": "run the interface's `optimize` method (penalised MLE)",
                "map": "run the interface's `optimize` method",
                "expectation": "post-process the draws; not part of the program text",
                "variance": "post-process the draws; not part of the program text",
            }.get(st.query, "no Stan equivalent")
            self.weaken(
                f"infer {st.query}",
                "the inference query is an instruction to the *interface* (CmdStan, "
                "CmdStanPy, RStan), not a statement in the Stan language, so it "
                f"cannot appear in the program: {mapping}.",
                st.span.line,
            )
            model.append(f"// infer {st.query} {names}: {mapping}")
            return

        if isinstance(st, ConceptDecl):
            self.drop(
                f"concept {st.name}",
                "Stan has no user-defined type or concept mechanism; parameters, "
                "transforms, invariants, examples and counterexamples have no "
                "encoding.",
                st.span.line,
            )
            return

    def _declaration(self, st: Declaration, data: list[str], params: list[str]) -> None:
        decl = self.stan_type(st.declared_type, st.name, st.span.line)
        if decl is None:
            return
        name = _stan_name(st.name)
        line = f"{decl} {name};"
        if st.kind in (DeclKind.OBS, DeclKind.CONST, DeclKind.INDEX):
            if st.value is not None:
                self.weaken(
                    f"{st.kind} {st.name}",
                    "Stan data values come from the data file, not the program text; "
                    f"the value {self.expr(st.value)} is recorded in a header comment "
                    "and must be supplied at run time.",
                    st.span.line,
                )
                line += f"  // = {self.expr(st.value)} in the HML source"
            data.append(line)
        else:
            if st.value is not None:
                self.drop(
                    f"{st.kind} {st.name} initialiser",
                    "a Stan parameter cannot be given a value in the program; the "
                    f"initialiser {self.expr(st.value)} is dropped.",
                    st.span.line,
                )
            params.append(line)

    def _define(
        self, st: DefineStmt, tdata: list[str], tparams: list[str], functions: list[str]
    ) -> None:
        t = st.declared_type or st.type_
        decl = self.stan_type(t, st.name, st.span.line)
        if decl is None:
            return
        name = _stan_name(st.name)
        if st.params:
            arg_decls = []
            for pname, ptype in st.params:
                pdecl = self.stan_type(ptype, pname, st.span.line) if ptype else None
                if pdecl is None:
                    self.approximate(
                        f"def {st.name} parameter {pname}",
                        "the parameter has no declared HML type; Stan requires one, so "
                        "`real` is assumed.",
                        st.span.line,
                    )
                    pdecl = "real"
                arg_decls.append(f"{pdecl} {_stan_name(pname)}")
            functions.append(
                f"{decl} {name}({', '.join(arg_decls)}) {{ return {self.expr(st.body)}; }}"
            )
            return
        line = f"{decl} {name} = {self.expr(st.body)};"
        if st.name in self._param_names:
            tparams.append(line)
        else:
            tdata.append(line)

    def _law(self, st: LawStmt, model: list[str]) -> None:
        if st.distribution is None:
            self.drop("law", "no distribution expression", st.span.line)
            return
        if st.role != "law" or st.given:
            cond = (
                " | " + ", ".join(g.name for g in st.given) if st.given else ""
            )
            self.weaken(
                f"{st.role} {st.target}{cond}",
                "Stan's sampling statement records neither the conditioning set nor "
                "the prior/likelihood distinction: `prior`, `likelihood` and `law` all "
                "become `~`, and the conditioning is left implicit in which symbols "
                "appear on the right-hand side.",
                st.span.line,
            )
        rhs = self.dist(st.distribution, sampled=st.target)
        model.append(f"{_stan_name(st.target)} ~ {rhs};")

    # -- types ------------------------------------------------------------

    def stan_type(self, t: Type | None, who: str, line: int) -> str | None:
        """Map an HML type to a Stan declaration prefix, or None when undeclarable."""
        if t is None or isinstance(t, UnknownType):
            self.approximate(
                who, "no resolved HML type; `real` assumed by the Stan backend", line
            )
            return "real"

        if isinstance(t, ScalarType):
            return self._scalar_type(t, who, line)

        if isinstance(t, QuantityType):
            self.weaken(
                who,
                f"Stan is dimensionless: the dimension {t.dimension.render()} is "
                "dropped and the quantity becomes a bare real.",
                line,
            )
            base = self._scalar_type(t.base, who, line)
            return base

        if isinstance(t, RandomVariableType):
            self.weaken(
                who,
                "Stan does not distinguish a random variable from a value of its "
                f"support; RandomVariable[{t.codomain.render()}] is declared as its "
                "codomain.",
                line,
            )
            return self.stan_type(t.codomain, who, line)

        if isinstance(t, VectorType):
            n = _extent(t.length)
            if n is None:
                self.drop(who, "vector of unknown length cannot be declared in Stan", line)
                return None
            bound = self._element_bound(t.element, who, line)
            return f"vector{bound}[{n}]"

        if isinstance(t, MatrixType):
            r, c = _extent(t.rows), _extent(t.cols)
            if r is None or c is None:
                self.drop(who, "matrix of unknown extent cannot be declared in Stan", line)
                return None
            bound = self._element_bound(t.element, who, line)
            return f"matrix{bound}[{r}, {c}]"

        if isinstance(t, TensorType):
            self.drop(
                who,
                "Stan has no rank-n tensor type; arrays of matrices would need a "
                "shape convention this backend will not invent.",
                line,
            )
            return None

        if isinstance(t, DistributionType):
            self.drop(
                who,
                "Stan has no first-class distribution values; a distribution can only "
                "appear on the right of `~`, never as a declared object.",
                line,
            )
            return None

        for cls, why in (
            (SetType, "Stan has no set type"),
            (FunctionType, "Stan has no first-class function values"),
            (PredicateType, "Stan has no predicate type"),
            (PropositionType, "Stan has no proposition type"),
            (ConceptType, "Stan has no concept mechanism"),
        ):
            if isinstance(t, cls):
                self.drop(who, f"{why}; the declaration is omitted.", line)
                return None

        self.drop(who, f"no Stan encoding for type {t.render()}", line)
        return None

    def _scalar_type(self, t: ScalarType, who: str, line: int) -> str:
        name = t.name
        if name == "Real":
            return "real"
        if name == "PositiveReal":
            # Stan's <lower=0> is a closed bound; HML's PositiveReal is open at 0.
            self.weaken(
                who,
                "PositiveReal is open at 0 but Stan's <lower=0> is a closed bound; the "
                "emitted constraint admits 0, which HML's type does not.",
                line,
            )
            return "real<lower=0>"
        if name == "NonNegativeReal":
            return "real<lower=0>"
        if name == "Probability":
            return "real<lower=0,upper=1>"
        if name in UNIT_INTERVAL_KINDS:
            # PValue / PosteriorProbability. Stan has one unit-interval declaration and
            # no way to record which kind it is, so the numeric bound survives and the
            # epistemic kind does not.
            self.weaken(
                who,
                f"{name} becomes the same real<lower=0,upper=1> as Probability; Stan "
                "cannot carry the epistemic kind, so the p-value / posterior / model "
                "probability separation is lost in the emitted program.",
                line,
            )
            return "real<lower=0,upper=1>"
        if name == "Natural":
            return "int<lower=0>"
        if name == "PositiveNatural":
            return "int<lower=1>"
        if name == "Integer":
            return "int"
        if name == "Rational":
            self.approximate(
                who,
                "Stan has no exact rational type; Rational becomes a floating-point "
                "real and exactness is lost.",
                line,
            )
            return "real"
        if name == "Bool":
            self.approximate(
                who,
                "Stan has no boolean type; Bool becomes int<lower=0,upper=1>.",
                line,
            )
            return "int<lower=0,upper=1>"
        self.approximate(who, f"unmapped scalar {name}; `real` assumed", line)
        return "real"

    def _element_bound(self, element: Type, who: str, line: int) -> str:
        """Constraint suffix for a vector/matrix element type."""
        if isinstance(element, ScalarType):
            if element.name in ("PositiveReal", "NonNegativeReal"):
                return "<lower=0>"
            if element.name == "Probability":
                return "<lower=0,upper=1>"
            if element.name in ("Natural", "Integer", "PositiveNatural"):
                self.approximate(
                    who,
                    f"Stan's vector/matrix element type is always real; "
                    f"{element.name} elements become reals.",
                    line,
                )
                return ""
        return ""

    # -- distributions ----------------------------------------------------

    def dist(self, d: DistExpr, sampled: str | None = None) -> str:
        mapped = STAN_DISTRIBUTIONS.get(d.family)
        if mapped is None:
            self.drop(
                f"{d.family}",
                "no Stan density is registered for this family; the sampling "
                "statement would be invalid Stan, so a placeholder is emitted.",
                d.span.line,
            )
            args = ", ".join(f"/* {a.role} = */ {self.expr(a.value)}" for a in d.args)
            return f"UNMAPPED_{d.family}({args})"

        by_role: dict[str, Arg] = {a.role: a for a in d.args}
        rendered: list[str] = []
        missing: list[str] = []
        for slot in mapped.slots:
            if slot.startswith("#"):
                rendered.append(slot[1:])
                continue
            arg = by_role.get(slot)
            if arg is None:
                missing.append(slot)
                rendered.append(f"/* MISSING role {slot} */")
            else:
                rendered.append(self.expr(arg.value))

        if missing:
            self.drop(
                f"{d.family} arguments",
                "required role(s) " + ", ".join(missing) + " absent; the emitted "
                "call has holes and is not valid Stan.",
                d.span.line,
            )
        extra = sorted(set(by_role) - set(mapped.roles))
        if extra:
            self.drop(
                f"{d.family} arguments",
                "role(s) " + ", ".join(extra) + " have no Stan slot and are dropped.",
                d.span.line,
            )

        if d.args:
            # The role names themselves do not survive into Stan; only their order does.
            self.weaken(
                f"{d.family} argument roles",
                "role labels ("
                + ", ".join(a.role for a in d.args)
                + f") become positional in Stan as {mapped.fn}("
                + ", ".join(mapped.slots)
                + "); a reader of the Stan file must recover them from the manual.",
                d.span.line,
            )

        if mapped.fidelity == "approximated":
            self.approximate(f"{d.family}", mapped.reason, d.span.line)
        elif mapped.fidelity == "weakened":
            self.weaken(f"{d.family}", mapped.reason, d.span.line)

        if mapped.needs_lower_bound and sampled is not None:
            if not self._lower_bounded.get(sampled, False):
                self.drop(
                    f"{d.family} support",
                    f"{d.family} requires the sampled variable {sampled} to be "
                    "declared with a lower bound of 0; its declared HML type induced "
                    "no such bound, so the emitted Stan model is a full normal, not a "
                    "half-normal. This is a genuine semantic difference.",
                    d.span.line,
                )

        return f"{mapped.fn}({', '.join(rendered)})"

    # -- expressions ------------------------------------------------------

    def expr(self, e: Expr | None) -> str:
        text, _ = self._expr(e)
        return text

    def _wrap(self, e: Expr | None, outer: int, *, right: bool = False) -> str:
        text, prec = self._expr(e)
        if prec < outer or (right and prec == outer):
            return f"({text})"
        return text

    def _expr(self, e: Expr | None) -> tuple[str, int]:
        if e is None:
            return "/* missing */", _ATOM

        if isinstance(e, Literal):
            if isinstance(e.value, bool):
                return ("1" if e.value else "0"), _ATOM
            return (e.raw or str(e.value)), _ATOM

        if isinstance(e, Ref):
            return _stan_name(e.name), _ATOM

        if isinstance(e, UnaryOp):
            p = _PREC["unary"]
            if e.op == "not":
                return f"!{self._wrap(e.operand, p)}", p
            return f"-{self._wrap(e.operand, p)}", p

        if isinstance(e, BinOp):
            if e.op == "@":
                # Stan spells matrix/vector product as ordinary multiplication.
                p = _PREC["*"]
                return (
                    f"{self._wrap(e.left, p)} * {self._wrap(e.right, p, right=True)}",
                    p,
                )
            if e.op == "^":
                p = _PREC["^"]
                # right-associative
                return f"{self._wrap(e.left, p, right=True)} ^ {self._wrap(e.right, p)}", p
            p = _PREC.get(e.op, 6)
            return (
                f"{self._wrap(e.left, p)} {e.op} {self._wrap(e.right, p, right=True)}",
                p,
            )

        if isinstance(e, Comparison):
            p = _PREC["="]
            op = "==" if e.op == "=" else e.op
            return f"{self._wrap(e.left, p)} {op} {self._wrap(e.right, p)}", p

        if isinstance(e, LogicalOp):
            if e.op == "and":
                p = _PREC["and"]
                return f"{self._wrap(e.left, p)} && {self._wrap(e.right, p)}", p
            if e.op == "or":
                p = _PREC["or"]
                return f"{self._wrap(e.left, p)} || {self._wrap(e.right, p)}", p
            if e.op == "implies":
                self.approximate(
                    "implication",
                    "Stan has no implication operator; rewritten as !a || b, which is "
                    "the material conditional but reads nothing like one.",
                    e.span.line,
                )
                return f"(!({self.expr(e.left)}) || ({self.expr(e.right)}))", _ATOM
            if e.op == "iff":
                self.approximate(
                    "biconditional",
                    "Stan has no biconditional; rewritten as an equality of "
                    "truth-valued integers.",
                    e.span.line,
                )
                return f"(({self.expr(e.left)}) == ({self.expr(e.right)}))", _ATOM
            return f"{self.expr(e.left)} {e.op} {self.expr(e.right)}", _ATOM

        if isinstance(e, Call):
            args = ", ".join(self.expr(a) for a in e.args)
            known = {
                "exp": "exp", "log": "log", "sqrt": "sqrt", "sin": "sin",
                "cos": "cos", "tan": "tan", "abs": "abs",
            }
            fn = known.get(e.callee)
            if fn is None:
                self.approximate(
                    f"call {e.callee}",
                    "no Stan built-in of this name is known to the backend; emitted "
                    "verbatim and assumed to be user-supplied in the functions block.",
                    e.span.line,
                )
                fn = _stan_name(e.callee)
            return f"{fn}({args})", _ATOM

        if isinstance(e, Index):
            self.weaken(
                "index expression",
                "Stan containers are 1-based; HML does not fix an index origin, so "
                "the subscript is emitted verbatim and may be off by one.",
                e.span.line,
            )
            idx = ", ".join(self.expr(i) for i in e.indices)
            return f"{self.expr(e.base)}[{idx}]", _ATOM

        if isinstance(e, DistExpr):
            return self.dist(e), _ATOM

        if isinstance(e, Quantifier):
            self.drop(
                f"{e.kind} quantifier",
                "Stan has no quantifiers. A bounded universal could sometimes be "
                "unrolled into a for loop, but the domain here is Real, which cannot "
                "be enumerated; nothing sound can be emitted.",
                e.span.line,
            )
            return f"/* {e.kind} {e.var} : NOT EXPRESSIBLE IN STAN */", _ATOM

        self.drop("expression", f"no Stan encoding for {type(e).__name__}", e.span.line)
        return "/* unrepresented */", _ATOM


def to_stan(module, symbols=None):
    return StanBackend(module, symbols).run()
