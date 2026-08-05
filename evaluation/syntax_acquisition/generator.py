"""Deterministic generation of canonical shared-core objects.

A *shared-core object* here is a fully checked ``Module``: the thing all four surfaces
are projections of. Objects are produced by generating HML-L1 source and compiling it,
so every object in the corpus is by construction a program the frozen compiler accepts.
Anything that fails to compile is discarded and counted, never silently kept.

Coverage is enumerated rather than sampled. The axes the phase brief names --
declaration kinds, scalar refinements, dimensions (including rational exponents and
dimension variables), distribution families and parameter roles, quantifiers and binder
depth, definitions, constraints, inference queries -- each get an explicit family, and
:func:`coverage_report` asserts afterwards that the corpus actually reaches every value
on every axis. A generator that quietly stopped producing, say, ``exists_unique`` would
otherwise leave a green suite that proves nothing about it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from functools import lru_cache

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import Module

__all__ = [
    "GeneratedObject",
    "build_sources",
    "build_corpus",
    "corpus",
    "corpus_chunk",
    "coverage_report",
    "CORPUS_SEED",
    "CORPUS_CHUNKS",
    "MIN_CORPUS_SIZE",
]

CORPUS_SEED = 20260805
MIN_CORPUS_SIZE = 500

#: How many pieces the corpus is cut into for parametrised tests. 24 chunks x 4
#: candidates is 96 items, which spreads evenly over 18 xdist workers while keeping
#: per-item overhead small.
CORPUS_CHUNKS = 24


@dataclass
class GeneratedObject:
    id: str
    family: str
    source: str
    module: Module = field(repr=False)

    @property
    def line_count(self) -> int:
        return len(self.source.strip().splitlines())


# ---------------------------------------------------------------------------
# Ingredients
# ---------------------------------------------------------------------------

SCALARS = (
    "Bool", "Natural", "PositiveNatural", "Integer", "Rational", "Real",
    "NonNegativeReal", "PositiveReal", "Probability",
)

#: A literal that inhabits each scalar, for declarations that carry a value.
SCALAR_LITERAL = {
    "Bool": "true",
    "Natural": "0",
    "PositiveNatural": "3",
    "Integer": "7",
    "Rational": "2",
    "Real": "1.5",
    "NonNegativeReal": "0.0",
    "PositiveReal": "2.5",
    "Probability": "0.25",
}

DIMENSIONS = (
    "Dimensionless",
    "Mass",
    "Length",
    "Time",
    "Temperature",
    "Current",
    "Amount",
    "Luminosity",
    "Length^2",
    "Length^3",
    "1 / Time",
    "Mass * Length / Time^2",
    "Mass * Length^2 / Time^2",
    "Mass / (Length * Time^2)",
    "Length^1/2",
    "Length^3/2",
    "Mass^1/2 / Time",
    "Time^-1",
    "Length^2 / Time^-1",
    "D",
    "D^2",
    "Mass * D",
    "D / Time",
    "E^1/2",
)

STRUCTURED_TYPES = (
    "Vector[Real, 3]",
    "Vector[Real]",
    "Vector[PositiveReal, N]",
    "Matrix[Real, 2, 2]",
    "Matrix[Real, 3]",
    "Matrix[Real]",
    "Tensor[Real, 2, 3]",
    "Tensor[Integer, 2, 2, 2]",
    "Set[Real]",
    "Set[Natural]",
    "Function[Real -> Real]",
    "Function[Real, Real -> Real]",
    "Function[Natural, Real, Real -> Probability]",
    "Predicate[Real]",
    "Predicate[Real, Natural]",
    "RandomVariable[Real]",
    "RandomVariable[Probability]",
    "Distribution[Real]",
    "Quantity[Mass]",
    "Quantity[Mass * Length^2 / Time^2]",
    "Quantity[Length^1/2]",
    "Quantity[D]",
)

DECL_KINDS = ("var", "param", "const", "obs", "index", "rv")

#: family -> (list of (declaration, role expression) prerequisites, support type)
DISTRIBUTIONS: dict[str, tuple[tuple[tuple[str, str, str], ...], str]] = {
    # (role, declared type, symbol suffix)
    "Normal": ((("location", "Real", "m"), ("scale", "PositiveReal", "s")), "Real"),
    "HalfNormal": ((("scale", "PositiveReal", "s"),), "PositiveReal"),
    "LogNormal": ((("location", "Real", "m"), ("scale", "PositiveReal", "s")), "PositiveReal"),
    "StudentT": (
        (
            ("degrees_of_freedom", "PositiveReal", "d"),
            ("location", "Real", "m"),
            ("scale", "PositiveReal", "s"),
        ),
        "Real",
    ),
    "Cauchy": ((("location", "Real", "m"), ("scale", "PositiveReal", "s")), "Real"),
    "Beta": ((("alpha", "PositiveReal", "a"), ("beta", "PositiveReal", "b")), "Probability"),
    "Bernoulli": ((("prob", "Probability", "p"),), "Bool"),
    "Binomial": ((("trials", "Natural", "n"), ("prob", "Probability", "p")), "Natural"),
    "Poisson": ((("rate", "PositiveReal", "r"),), "Natural"),
    "Exponential": ((("rate", "PositiveReal", "r"),), "PositiveReal"),
    "Gamma": ((("shape", "PositiveReal", "k"), ("rate", "PositiveReal", "r")), "PositiveReal"),
    "InverseGamma": (
        (("shape", "PositiveReal", "k"), ("scale", "PositiveReal", "s")),
        "PositiveReal",
    ),
    "Dirichlet": (
        (("concentration", "Vector[PositiveReal, 3]", "c"),),
        "Vector[Probability, 3]",
    ),
    "Categorical": ((("probs", "Vector[Probability, 4]", "p"),), "Natural"),
    "NormalVector": (
        (("location", "Vector[Real, 5]", "m"), ("scale", "PositiveReal", "s")),
        "Vector[Real, 5]",
    ),
}

#: Uniform is handled separately: its cross-constraint ties the two roles together.
UNIFORM = ("Uniform", "Real")

LAW_ROLES = ("law", "prior", "likelihood")
INFER_QUERIES = ("posterior", "expectation", "variance", "mle", "map")
QUANTIFIERS = ("forall", "exists", "exists unique")
COMPARISONS = ("=", "!=", "<", "<=", ">", ">=")
ARITHMETIC = ("+", "-", "*", "/")
CONNECTIVES = ("and", "or", "=>", "<=>")
BUILTINS = ("exp", "log", "sqrt", "abs", "sin", "cos", "tan")


def _module(name: str, lines: list[str]) -> str:
    return "\n".join([f"module {name}", *lines]) + "\n"


# ---------------------------------------------------------------------------
# Families
# ---------------------------------------------------------------------------


def _f_declarations() -> list[tuple[str, str, str]]:
    """Every declaration kind against every scalar and structured type."""
    out: list[tuple[str, str, str]] = []
    for kind in DECL_KINDS:
        for scalar in SCALARS:
            out.append((
                f"decl_{kind}_{scalar}",
                "declarations",
                _module(
                    f"Decl{kind.capitalize()}{scalar}",
                    [f"{kind} subject_ : {scalar}", "require true"],
                ),
            ))
            out.append((
                f"declval_{kind}_{scalar}",
                "declarations",
                _module(
                    f"DeclVal{kind.capitalize()}{scalar}",
                    [f"{kind} subject_ : {scalar} = {SCALAR_LITERAL[scalar]}", "require true"],
                ),
            ))
    for i, structured in enumerate(STRUCTURED_TYPES):
        for kind in ("var", "param", "const"):
            out.append((
                f"declstruct_{kind}_{i}",
                "declarations",
                _module(
                    f"DeclStruct{kind.capitalize()}{i}",
                    [f"{kind} subject_ : {structured}", "require true"],
                ),
            ))
    return out


def _f_dimensions() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for i, dim in enumerate(DIMENSIONS):
        out.append((
            f"dim_decl_{i}",
            "dimensions",
            _module(f"DimDecl{i}", [f"param q_ : Quantity[{dim}]", "check dimension q_"]),
        ))
        out.append((
            f"dim_expected_{i}",
            "dimensions",
            _module(
                f"DimExpected{i}",
                [f"param q_ : Quantity[{dim}]", f"check dimension q_ = {dim}"],
            ),
        ))
    # products, quotients and powers of declared magnitudes
    out.append((
        "dim_kinetic",
        "dimensions",
        _module(
            "DimKinetic",
            [
                "param mass_ : Quantity[Mass]",
                "param speed_ : Quantity[Length / Time]",
                "def energy_ := 0.5 * mass_ * speed_ ^ 2",
                "check dimension energy_ = Mass * Length^2 / Time^2",
            ],
        ),
    ))
    out.append((
        "dim_pendulum",
        "dimensions",
        _module(
            "DimPendulum",
            [
                "param length_ : Quantity[Length]",
                "param gravity_ : Quantity[Length / Time^2]",
                "def period_ := (length_ / gravity_) ^ 0.5",
                "check dimension period_ = Time",
            ],
        ),
    ))
    out.append((
        "dim_pressure",
        "dimensions",
        _module(
            "DimPressure",
            [
                "param force_ : Quantity[Mass * Length / Time^2]",
                "param area_ : Quantity[Length^2]",
                "def pressure_ := force_ / area_",
                "check dimension pressure_ = Mass / (Length * Time^2)",
            ],
        ),
    ))
    out.append((
        "dim_variable_ratio",
        "dimensions",
        _module(
            "DimVariableRatio",
            [
                "param a_ : Quantity[D]",
                "param b_ : Quantity[D]",
                "def ratio_ := a_ / b_",
                "check dimension ratio_ = Dimensionless",
            ],
        ),
    ))
    return out


def _law_program(name: str, family: str, role: str, *, conditioned: bool, target_kind: str) -> str:
    roles, support = DISTRIBUTIONS[family]
    lines = [f"{'param' if r[1] != 'Bool' else 'const'} {r[2]}_ : {r[1]}" for r in roles]
    lines.append(f"{target_kind} target_ : RandomVariable[{support}]")
    args = ", ".join(f"{r[0]} := {r[2]}_" for r in roles)
    given = f" | {' '.join(r[2] + '_' for r in roles)}" if conditioned else ""
    lines.append(f"{role} target_{given} ~ {family}({args})")
    return _module(name, lines)


def _f_distributions() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for family in DISTRIBUTIONS:
        for role in LAW_ROLES:
            for conditioned in (False, True):
                suffix = "cond" if conditioned else "plain"
                out.append((
                    f"law_{family}_{role}_{suffix}",
                    "distributions",
                    _law_program(
                        f"Law{family}{role.capitalize()}{suffix.capitalize()}",
                        family,
                        role,
                        conditioned=conditioned,
                        target_kind="var" if role != "likelihood" else "obs",
                    ),
                ))
    # Uniform, whose two roles are tied by a cross-constraint.
    for role in LAW_ROLES:
        out.append((
            f"law_Uniform_{role}",
            "distributions",
            _module(
                f"LawUniform{role.capitalize()}",
                [
                    "const lower_ : Real = 0.0",
                    "const upper_ : Real = 1.0",
                    f"{'obs' if role == 'likelihood' else 'var'} target_ : RandomVariable[Real]",
                    f"{role} target_ ~ Uniform(lower := lower_, upper := upper_)",
                ],
            ),
        ))
    # role order is not identity: the same law written with its arguments swapped
    for family, (roles, support) in DISTRIBUTIONS.items():
        if len(roles) < 2:
            continue
        lines = [f"param {r[2]}_ : {r[1]}" for r in roles]
        lines.append(f"var target_ : RandomVariable[{support}]")
        args = ", ".join(f"{r[0]} := {r[2]}_" for r in reversed(roles))
        lines.append(f"law target_ ~ {family}({args})")
        out.append((
            f"law_{family}_reordered",
            "distributions",
            _module(f"Law{family}Reordered", lines),
        ))
    # literal-valued roles rather than symbol-valued ones
    out.append((
        "law_literal_roles",
        "distributions",
        _module(
            "LawLiteralRoles",
            [
                "param theta_ : Probability",
                "prior theta_ ~ Beta(alpha := 1, beta := 1)",
                "obs successes_ : Natural = 7",
                "const trials_ : Natural = 10",
                "likelihood successes_ | theta_ ~ Binomial(trials := trials_, prob := theta_)",
                "infer posterior theta_",
            ],
        ),
    ))
    return out


def _quantified_body(depth: int, scalar: str) -> str:
    """A closed proposition with ``depth`` nested binders."""
    names = [f"x{i}_" for i in range(depth)]
    inner = " and ".join(f"{n} = {n}" for n in names)
    return inner


def _f_quantifiers() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for depth in (1, 2, 3, 4):
        for combo_index, base in enumerate(QUANTIFIERS):
            binders = []
            for i in range(depth):
                q = QUANTIFIERS[(combo_index + i) % len(QUANTIFIERS)] if depth > 1 else base
                binders.append(f"{q} x{i}_ : Real .")
            body = _quantified_body(depth, "Real")
            out.append((
                f"quant_d{depth}_{combo_index}",
                "quantifiers",
                _module(
                    f"QuantD{depth}N{combo_index}",
                    [f"require {' '.join(binders)} {body}"],
                ),
            ))
    # the two orders of the same atoms, which must not collapse onto one object
    out.append((
        "quant_order_forall_exists",
        "quantifiers",
        _module(
            "QuantOrderA",
            ["def p_ : Proposition := forall x_ : Real . exists y_ : Real . y_ > x_", "prove p_"],
        ),
    ))
    out.append((
        "quant_order_exists_forall",
        "quantifiers",
        _module(
            "QuantOrderB",
            ["def p_ : Proposition := exists y_ : Real . forall x_ : Real . y_ > x_", "check not p_"],
        ),
    ))
    for scalar in SCALARS:
        if scalar == "Bool":
            continue
        out.append((
            f"quant_type_{scalar}",
            "quantifiers",
            _module(
                f"QuantType{scalar}",
                [f"require forall x_ : {scalar} . x_ = x_"],
            ),
        ))
    for i, structured in enumerate(("Vector[Real, 3]", "Set[Real]", "Quantity[Mass]")):
        out.append((
            f"quant_struct_{i}",
            "quantifiers",
            _module(f"QuantStruct{i}", [f"require forall x_ : {structured} . x_ = x_"]),
        ))
    out.append((
        "quant_mixed_connectives",
        "quantifiers",
        _module(
            "QuantMixed",
            [
                "require forall x_ : Real . exists unique y_ : Real . "
                "(y_ > x_ and y_ < x_ + 2.0) => y_ != x_",
            ],
        ),
    ))
    return out


def _f_definitions() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for op in ARITHMETIC + ("^",):
        out.append((
            f"def_binop_{op}",
            "definitions",
            _module(
                f"DefBinop{ARITHMETIC.index(op) if op in ARITHMETIC else 9}",
                [
                    "param a_ : PositiveReal",
                    "param b_ : PositiveReal",
                    f"def z_ := a_ {op} b_",
                ],
            ),
        ))
    out.append((
        "def_matrix_product",
        "definitions",
        _module(
            "DefMatrixProduct",
            [
                "param m_ : Matrix[Real, 3, 3]",
                "param v_ : Vector[Real, 3]",
                "def w_ := m_ @ v_",
            ],
        ),
    ))
    out.append((
        "def_index",
        "definitions",
        _module(
            "DefIndex",
            [
                "param v_ : Vector[Real, 4]",
                "index i_ : Natural",
                "def first_ := v_[i_]",
            ],
        ),
    ))
    out.append((
        "def_index_matrix",
        "definitions",
        _module(
            "DefIndexMatrix",
            [
                "param m_ : Matrix[Real, 3, 3]",
                "index i_ : Natural",
                "index j_ : Natural",
                "def cell_ := m_[i_, j_]",
            ],
        ),
    ))
    for fn in BUILTINS:
        out.append((
            f"def_builtin_{fn}",
            "definitions",
            _module(
                f"DefBuiltin{fn.capitalize()}",
                ["param a_ : PositiveReal", f"def z_ := {fn}(a_)"],
            ),
        ))
    for arity in (1, 2, 3):
        params = ", ".join(f"p{i}_ : Real" for i in range(arity))
        body = " + ".join(f"p{i}_" for i in range(arity))
        out.append((
            f"def_params_{arity}",
            "definitions",
            _module(
                f"DefParams{arity}",
                [f"def f_({params}) : Real := {body}", "def g_ := f_(" + ", ".join(["1.0"] * arity) + ")"],
            ),
        ))
    # An *unannotated* definition parameter parses (the grammar allows it) but never
    # type-checks: HML-T450, "this expression could not be given a type". It is
    # therefore outside the round-trippable subset, and the annotated form is generated
    # instead. Recorded here rather than in a comment elsewhere because the absence of a
    # generator case is otherwise indistinguishable from an oversight.
    out.append((
        "def_annotated_param",
        "definitions",
        _module("DefAnnotatedParam", ["def f_(p_ : Real) := p_ + 1.0", "def g_ := f_(2.0)"]),
    ))
    out.append((
        "def_chain",
        "definitions",
        _module(
            "DefChain",
            [
                "param a_ : Real",
                "def b_ := a_ + 1.0",
                "def c_ := b_ * 2.0",
                "def d_ := c_ - b_",
            ],
        ),
    ))
    out.append((
        "def_nested_power",
        "definitions",
        _module(
            "DefNestedPower",
            [
                "param a_ : PositiveReal",
                "param b_ : PositiveReal",
                "param c_ : PositiveReal",
                "def left_ := (a_ ^ b_) ^ c_",
                "def right_ := a_ ^ (b_ ^ c_)",
            ],
        ),
    ))
    out.append((
        "def_nested_subtraction",
        "definitions",
        _module(
            "DefNestedSubtraction",
            [
                "param a_ : Real",
                "param b_ : Real",
                "param c_ : Real",
                "def left_ := (a_ - b_) - c_",
                "def right_ := a_ - (b_ - c_)",
            ],
        ),
    ))
    out.append((
        "def_unary",
        "definitions",
        _module(
            "DefUnary",
            [
                "param a_ : Real",
                "def neg_ := -a_",
                "def negpow_ := -(a_ ^ 2)",
                "def doubleneg_ := -(-a_)",
            ],
        ),
    ))
    return out


def _f_constraints() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for op in COMPARISONS:
        for keyword in ("assume", "require", "check"):
            out.append((
                f"cmp_{keyword}_{COMPARISONS.index(op)}",
                "constraints",
                _module(
                    f"Cmp{keyword.capitalize()}{COMPARISONS.index(op)}",
                    ["param a_ : Real", "param b_ : Real", f"{keyword} a_ {op} b_"],
                ),
            ))
    for connective in CONNECTIVES:
        out.append((
            f"conn_{CONNECTIVES.index(connective)}",
            "constraints",
            _module(
                f"Conn{CONNECTIVES.index(connective)}",
                [
                    "param a_ : Real",
                    "param b_ : Real",
                    f"require a_ > 0.0 {connective} b_ > 0.0",
                ],
            ),
        ))
    out.append((
        "conn_negation",
        "constraints",
        _module(
            "ConnNegation",
            ["param a_ : Real", "require not (a_ > 0.0)", "assume not (a_ = 0.0)"],
        ),
    ))
    out.append((
        "conn_left_nested_implication",
        "constraints",
        _module(
            "ConnLeftNestedImplication",
            [
                "param a_ : Real",
                "param b_ : Real",
                "param c_ : Real",
                "require (a_ > 0.0 => b_ > 0.0) => c_ > 0.0",
                "assume a_ > 0.0 => (b_ > 0.0 => c_ > 0.0)",
            ],
        ),
    ))
    out.append((
        "prove_simple",
        "constraints",
        _module(
            "ProveSimple",
            ["def p_ : Proposition := forall x_ : Real . x_ = x_", "prove p_"],
        ),
    ))
    out.append((
        "objective_min",
        "constraints",
        _module(
            "ObjectiveMin",
            ["param a_ : Real", "param b_ : Real", "minimise a_ * a_ + b_ * b_", "solve a_, b_"],
        ),
    ))
    out.append((
        "objective_max",
        "constraints",
        _module(
            "ObjectiveMax",
            [
                "param a_ : Real",
                "param b_ : Real",
                "require a_ + b_ = 1.0",
                "maximise a_ * b_",
                "solve a_, b_",
            ],
        ),
    ))
    out.append((
        "objective_dimensional",
        "constraints",
        _module(
            "ObjectiveDimensional",
            [
                "param cost_ : Quantity[Mass]",
                "minimise cost_",
                "solve cost_",
            ],
        ),
    ))
    return out


def _f_inference() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for query in INFER_QUERIES:
        out.append((
            f"infer_{query}",
            "inference",
            _module(
                f"Infer{query.capitalize()}",
                [
                    "param theta_ : Probability",
                    "param a_ : PositiveReal",
                    "param b_ : PositiveReal",
                    "prior theta_ ~ Beta(alpha := a_, beta := b_)",
                    f"infer {query} theta_",
                ],
            ),
        ))
    out.append((
        "infer_mle_likelihood_only",
        "inference",
        _module(
            "InferMleLikelihoodOnly",
            [
                "param theta_ : Probability",
                "const trials_ : Natural = 10",
                "obs successes_ : Natural = 7",
                "likelihood successes_ | theta_ ~ Binomial(trials := trials_, prob := theta_)",
                "infer mle successes_",
            ],
        ),
    ))
    out.append((
        "infer_multiple_targets",
        "inference",
        _module(
            "InferMultipleTargets",
            [
                "param mu_ : Real",
                "param sigma_ : PositiveReal",
                "param nu_ : PositiveReal",
                "prior mu_ ~ Normal(location := 0.0, scale := 1.0)",
                "prior sigma_ ~ HalfNormal(scale := 1.0)",
                "prior nu_ ~ Exponential(rate := 1.0)",
                "infer posterior mu_ sigma_ nu_",
            ],
        ),
    ))
    out.append((
        "solve_multiple",
        "inference",
        _module(
            "SolveMultiple",
            [
                "param a_ : Real",
                "param b_ : Real",
                "param c_ : Real",
                "require a_ + b_ + c_ = 1.0",
                "solve a_, b_, c_",
            ],
        ),
    ))
    return out


def _f_concepts() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    out.append((
        "concept_minimal",
        "concepts",
        _module(
            "ConceptMinimal",
            [
                "concept LocationScale",
                "    parameter location : Real",
                "    parameter scale : PositiveReal",
                "    invariant positive_scale := scale > 0.0",
                "end",
            ],
        ),
    ))
    out.append((
        "concept_transform",
        "concepts",
        _module(
            "ConceptTransform",
            [
                "concept LocationScale",
                "    parameter location : Real",
                "    parameter scale : PositiveReal",
                "    transform standardise(x : Real) : Real := (x - location) / scale",
                "    invariant positive_scale := scale > 0.0",
                "    example unit := location = 0.0",
                "end",
            ],
        ),
    ))
    out.append((
        "concept_all_members",
        "concepts",
        _module(
            "ConceptAllMembers",
            [
                "concept Full",
                "    parameter location : Real",
                "    parameter scale : PositiveReal",
                "    transform shift(x : Real) : Real := x + location",
                "    transform scale_by(x : Real, y : Real) : Real := x * y * scale",
                "    invariant positive := scale > 0.0",
                "    property centred : Proposition := location = 0.0",
                "    example unit := scale = 1.0",
                "    counterexample degenerate := scale = 0.0",
                "end",
            ],
        ),
    ))
    out.append((
        "concept_extends_one",
        "concepts",
        _module(
            "ConceptExtendsOne",
            [
                "concept Base",
                "    parameter location : Real",
                "    invariant trivial := location = location",
                "end",
                "concept Derived extends Base",
                "    parameter scale : PositiveReal",
                "    invariant positive := scale > 0.0",
                "end",
            ],
        ),
    ))
    out.append((
        "concept_extends_many",
        "concepts",
        _module(
            "ConceptExtendsMany",
            [
                "concept First",
                "    parameter a : Real",
                "    invariant ia := a = a",
                "end",
                "concept Second",
                "    parameter b : Real",
                "    invariant ib := b = b",
                "end",
                "concept Third extends First, Second",
                "    parameter c : Real",
                "    invariant ic := c = c",
                "end",
            ],
        ),
    ))
    out.append((
        "concept_no_annotation",
        "concepts",
        _module(
            "ConceptNoAnnotation",
            [
                "concept Loose",
                "    parameter location : Real",
                "    invariant reflexive := location = location",
                "    example zero := location = 0.0",
                "end",
            ],
        ),
    ))
    out.append((
        "concept_quantified_invariant",
        "concepts",
        _module(
            "ConceptQuantifiedInvariant",
            [
                "concept Monotone",
                "    parameter slope : PositiveReal",
                "    invariant increasing := forall x_ : Real . exists y_ : Real . y_ > x_",
                "end",
            ],
        ),
    ))
    return out


def _f_expressions() -> list[tuple[str, str, str]]:
    """Operator and literal shapes that the printers have to parenthesise correctly."""
    shapes = [
        "a_ + b_ * c_",
        "(a_ + b_) * c_",
        "a_ * b_ + c_",
        "a_ - b_ - c_",
        "a_ - (b_ - c_)",
        "a_ / b_ / c_",
        "a_ / (b_ / c_)",
        "a_ ^ b_ ^ c_",
        "(a_ ^ b_) ^ c_",
        "-a_ + b_",
        "-(a_ + b_)",
        "-a_ ^ b_",
        "(-a_) ^ b_",
        "a_ * -b_",
        "a_ + b_ + c_ + a_ * b_ * c_",
        "(a_ + b_) * (a_ - b_)",
        "a_ ^ (b_ + c_)",
        "(a_ + b_) ^ c_",
        "a_ * (b_ + c_) / (a_ - c_)",
        "-(-(a_ + b_))",
    ]
    out: list[tuple[str, str, str]] = []
    for i, shape in enumerate(shapes):
        out.append((
            f"expr_shape_{i}",
            "expressions",
            _module(
                f"ExprShape{i}",
                [
                    "param a_ : PositiveReal",
                    "param b_ : PositiveReal",
                    "param c_ : PositiveReal",
                    f"def z_ := {shape}",
                ],
            ),
        ))
    props = [
        "a_ > 0.0 and b_ > 0.0 or c_ > 0.0",
        "a_ > 0.0 and (b_ > 0.0 or c_ > 0.0)",
        "not (a_ > 0.0) and b_ > 0.0",
        "not (a_ > 0.0 and b_ > 0.0)",
        "a_ > 0.0 => b_ > 0.0 => c_ > 0.0",
        "(a_ > 0.0 => b_ > 0.0) => c_ > 0.0",
        "a_ > 0.0 <=> b_ > 0.0",
        "(a_ > 0.0 <=> b_ > 0.0) <=> c_ > 0.0",
        "a_ > 0.0 <=> (b_ > 0.0 <=> c_ > 0.0)",
        "not not (a_ > 0.0)",
    ]
    for i, prop in enumerate(props):
        out.append((
            f"expr_prop_{i}",
            "expressions",
            _module(
                f"ExprProp{i}",
                [
                    "param a_ : Real",
                    "param b_ : Real",
                    "param c_ : Real",
                    f"require {prop}",
                ],
            ),
        ))
    literals = ["0", "1", "42", "0.0", "1.0", "0.5", "3.25", "1e-07", "1.5e10", "true", "false"]
    for i, literal in enumerate(literals):
        scalar = "Bool" if literal in ("true", "false") else "Real"
        out.append((
            f"expr_literal_{i}",
            "expressions",
            _module(
                f"ExprLiteral{i}",
                [f"const k_ : {scalar} = {literal}", "require true"],
            ),
        ))
    return out


# ---------------------------------------------------------------------------
# Composites
# ---------------------------------------------------------------------------

_COMPOSITE_BLOCKS: tuple[tuple[str, ...], ...] = (
    ("param p{i}_ : Real", "param q{i}_ : PositiveReal", "def d{i}_ := p{i}_ + q{i}_"),
    ("param t{i}_ : Probability", "prior t{i}_ ~ Beta(alpha := 1, beta := 1)",
     "infer posterior t{i}_"),
    ("param m{i}_ : Quantity[Mass]", "param a{i}_ : Quantity[Length / Time^2]",
     "def f{i}_ := m{i}_ * a{i}_", "check dimension f{i}_ = Mass * Length / Time^2"),
    ("require forall x{i}_ : Real . exists y{i}_ : Real . y{i}_ > x{i}_",),
    ("param u{i}_ : Real", "param v{i}_ : Real", "require u{i}_ + v{i}_ = 1.0",
     "maximise u{i}_ * v{i}_", "solve u{i}_, v{i}_"),
    ("var r{i}_ : RandomVariable[Real]", "param mu{i}_ : Real", "param sd{i}_ : PositiveReal",
     "law r{i}_ | mu{i}_ sd{i}_ ~ Normal(location := mu{i}_, scale := sd{i}_)"),
    ("concept C{i}", "    parameter loc{i} : Real", "    parameter sc{i} : PositiveReal",
     "    transform std{i}(x : Real) : Real := (x - loc{i}) / sc{i}",
     "    invariant pos{i} := sc{i} > 0.0", "end"),
    ("param vec{i}_ : Vector[Real, 3]", "param mat{i}_ : Matrix[Real, 3, 3]",
     "def prod{i}_ := mat{i}_ @ vec{i}_"),
    ("obs y{i}_ : Natural = 7", "const n{i}_ : Natural = 10", "param th{i}_ : Probability",
     "prior th{i}_ ~ Beta(alpha := 2, beta := 2)",
     "likelihood y{i}_ | th{i}_ ~ Binomial(trials := n{i}_, prob := th{i}_)",
     "infer posterior th{i}_"),
    ("param g{i}_ : PositiveReal", "def h{i}_ := log(g{i}_) + sqrt(g{i}_)",
     "assume g{i}_ > 0.0"),
)


def _f_composites(count: int) -> list[tuple[str, str, str]]:
    rng = random.Random(CORPUS_SEED)
    out: list[tuple[str, str, str]] = []
    for k in range(count):
        blocks = rng.sample(_COMPOSITE_BLOCKS, rng.randint(2, 4))
        lines: list[str] = []
        for i, block in enumerate(blocks):
            lines.extend(line.format(i=i) for line in block)
        out.append((f"composite_{k}", "composites", _module(f"Composite{k}", lines)))
    return out


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build_sources(composite_count: int = 150) -> list[tuple[str, str, str]]:
    """Every generated ``(id, family, source)`` before compilation filters them."""
    sources: list[tuple[str, str, str]] = []
    sources += _f_declarations()
    sources += _f_dimensions()
    sources += _f_distributions()
    sources += _f_quantifiers()
    sources += _f_definitions()
    sources += _f_constraints()
    sources += _f_inference()
    sources += _f_concepts()
    sources += _f_expressions()
    sources += _f_composites(composite_count)
    seen: set[str] = set()
    unique: list[tuple[str, str, str]] = []
    for oid, family, src in sources:
        if oid in seen:
            raise AssertionError(f"duplicate generated id {oid!r}")
        seen.add(oid)
        unique.append((oid, family, src))
    return unique


@lru_cache(maxsize=1)
def build_corpus() -> tuple[tuple[GeneratedObject, ...], tuple[tuple[str, str], ...]]:
    """Compile every generated source. Returns ``(objects, rejected)``.

    ``rejected`` carries ``(id, diagnostics)`` for sources the compiler refused, so a
    generator that quietly stopped producing valid programs is visible rather than
    inferred from a shrinking corpus.
    """
    objects: list[GeneratedObject] = []
    rejected: list[tuple[str, str]] = []
    for oid, family, src in build_sources():
        result = compile_source(src, f"<generated:{oid}>")
        if result.ok():
            objects.append(GeneratedObject(oid, family, src, result.module))
        else:
            rejected.append((oid, "; ".join(f"{d.code} {d.message}" for d in result.diagnostics.errors)))
    return tuple(objects), tuple(rejected)


def corpus() -> tuple[GeneratedObject, ...]:
    return build_corpus()[0]


def corpus_chunk(index: int, chunks: int = CORPUS_CHUNKS) -> tuple[GeneratedObject, ...]:
    """A strided slice of the corpus, so each chunk mixes every generator family."""
    return corpus()[index::chunks]


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def coverage_report() -> dict[str, dict[str, int]]:
    """Count how often each axis value is reached by the compiled corpus.

    Counted from the compiled ``Module``s, not from the generator's intentions: an axis
    value that every program using it failed to compile shows up as zero here.
    """
    from hamiltonian_lang.ast.nodes import (
        BinOp,
        CheckStmt,
        Comparison,
        ConceptDecl,
        Declaration,
        DefineStmt,
        DistExpr,
        InferStmt,
        LawStmt,
        LogicalOp,
        ObjectiveStmt,
        Quantifier,
        SolveStmt,
        UnaryOp,
        walk,
    )
    from hamiltonian_lang.types import QuantityType

    axes: dict[str, dict[str, int]] = {
        "family": {},
        "declaration_kind": {},
        "scalar_type": {},
        "dimension": {},
        "distribution_family": {},
        "parameter_role": {},
        "quantifier": {},
        "binder_depth": {},
        "statement": {},
        "operator": {},
        "infer_query": {},
        "concept_member": {},
    }

    def bump(axis: str, key: str) -> None:
        axes[axis][key] = axes[axis].get(key, 0) + 1

    def quantifier_depth(node, current: int = 0) -> int:
        best = current
        for child in walk(node):
            if isinstance(child, Quantifier) and child is not node:
                best = max(best, quantifier_depth(child, current + 1))
        return best

    for obj in corpus():
        bump("family", obj.family)
        for st in obj.module.statements:
            bump("statement", type(st).__name__)
            if isinstance(st, Declaration):
                bump("declaration_kind", st.kind)
                if st.declared_type is not None:
                    bump("scalar_type", st.declared_type.render())
                if isinstance(st.declared_type, QuantityType):
                    bump("dimension", st.declared_type.dimension.render())
            if isinstance(st, LawStmt):
                bump("statement", f"law:{st.role}")
            if isinstance(st, InferStmt):
                bump("infer_query", st.query)
            if isinstance(st, SolveStmt):
                bump("infer_query", "solve")
            if isinstance(st, ObjectiveStmt):
                bump("infer_query", st.direction)
            if isinstance(st, CheckStmt):
                bump("statement", f"check:{st.check_kind}")
            if isinstance(st, ConceptDecl):
                for m in st.members:
                    bump("concept_member", m.kind)
            if isinstance(st, DefineStmt) and st.params:
                bump("statement", "DefineStmt:with-params")
        for node in walk(obj.module):
            if isinstance(node, DistExpr):
                bump("distribution_family", node.family)
                for a in node.args:
                    bump("parameter_role", f"{node.family}.{a.role}")
            if isinstance(node, Quantifier):
                bump("quantifier", node.kind)
            if isinstance(node, BinOp | Comparison | LogicalOp | UnaryOp):
                bump("operator", node.op)
            if isinstance(node, QuantityType):  # pragma: no cover - types are not walked
                bump("dimension", node.dimension.render())
        depths = [
            quantifier_depth(n) + 1
            for n in walk(obj.module)
            if isinstance(n, Quantifier)
        ]
        if depths:
            bump("binder_depth", str(max(depths)))
    return axes
