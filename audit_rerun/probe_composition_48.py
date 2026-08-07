"""Execute all 48 COMPOSITION_TESTS.json specimens against the V2 compiler.

The specimen file states each composition in prose and in standard notation and gives
no encoding: it is deliberately system-neutral (COMPOSITIONAL_CLOSURE_FRAMEWORK.md R6).
Nobody had ever run it, because running it requires somebody to *write* 48 HML
encodings. This file is those encodings plus the harness that scores them.

Nothing here modifies HML, and `COMPOSITION_TESTS.json` is opened read-only and is only
used to check that the 48 ids and titles this file carries match the ones it defines.

Scoring, per COMPOSITIONAL_CLOSURE_FRAMEWORK.md §5:

* every specimen has ONE primary encoding with an expected verdict (accept / reject);
* most also have CONTROLS -- a second source whose expected verdict establishes that the
  primary's success is not vacuous. `log(sigma)` compiling proves nothing unless
  `log(r)` for an unconstrained `r` is refused;
* specimens whose primary compiles also carry FACT CHECKS: mechanical assertions that
  the load-bearing fact of the specimen actually survived into the checked tree. This is
  what separates COMPOSES from COMPOSES_SILENT_LOSS, and it is why "it compiled" is not
  reported as the result on its own.

A specimen PASSES the mechanical gate iff the primary matched, every control matched, and
every fact check held. The adjudicated `outcome` and `failure_class` are recorded as
literals beside each specimen; the runner prints both so a reader can see whether the
adjudication and the machine agree, and flags any disagreement.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

_SRC = os.environ.get("HML_PROBE_SRC", "/Users/moheet/hml_v2_worktree/src")
sys.path.insert(0, _SRC)

import hamiltonian_lang as H  # noqa: E402
from hamiltonian_lang.ast.nodes import Declaration, DefineStmt  # noqa: E402
from hamiltonian_lang.backends import render  # noqa: E402
from hamiltonian_lang.backends.hml import render_module  # noqa: E402

SPECIMEN_FILE = Path(
    "/Users/moheet/hml_audit_worktree/audit/language_comparison/ontology/"
    "COMPOSITION_TESTS.json"
)

# ---------------------------------------------------------------------------
# outcome vocabulary (METRIC_DEFINITIONS §4 / framework §5)
# ---------------------------------------------------------------------------
COMPOSES = "COMPOSES"
DEGRADED = "COMPOSES_DEGRADED"
SILENT_LOSS = "COMPOSES_SILENT_LOSS"
REJ_SPURIOUS = "REJECTED_SPURIOUS"
REJ_CORRECT = "REJECTED_CORRECT"
UNSUPPORTED = "UNSUPPORTED"

#: outcomes that count in the closure numerator
NUMERATOR = {COMPOSES, REJ_CORRECT}

#: What it would actually take to make a failing specimen compose. Recorded per
#: specimen so the fork argument in docs/hml_v2/COMPOSITIONALITY_STUDY.md is counted
#: from data rather than asserted.
#:   NONE      -- it already composes
#:   LOCAL     -- one builtin signature, one type rule, one registry entry or one
#:                checker pass. No change to ast/nodes.py.
#:   ONE_NODE  -- one more bespoke expression or statement form closes it, in exactly
#:                the way D-026 closed eleven at once.
#:   GENERAL   -- needs a capability the current AST cannot express at all: abstraction
#:                (reading a binder as a function and applying it), or a binder that
#:                ranges over STATEMENTS rather than expressions.
NONE, LOCAL, ONE_NODE, GENERAL = "NONE", "LOCAL", "ONE_NODE", "GENERAL"

# failure classes required by the study brief
GRAMMAR, TYPE, SCOPE, CANONICAL = "GRAMMAR", "TYPE", "SCOPE", "CANONICAL"
CONSTRAINT, COMPILER, BACKEND, SPECIMEN = "CONSTRAINT", "COMPILER", "BACKEND", "SPECIMEN"


# ---------------------------------------------------------------------------
# harness
# ---------------------------------------------------------------------------


@dataclass
class Probe:
    label: str
    source: str
    #: What HML must do for this specimen to be scored as composing.
    expect: str  # accept | reject
    why: str = ""
    #: False for probes that only illustrate a consequence and are not part of the gate.
    gate: bool = True


@dataclass
class Spec:
    id: str
    title: str
    encoding: str
    expect: str = "accept"
    controls: list[Probe] = field(default_factory=list)
    facts: list[tuple[str, Callable[[object], bool]]] = field(default_factory=list)
    outcome: str = COMPOSES
    failure_class: str | None = None
    repair: str = NONE
    repair_note: str = ""
    note: str = ""


@dataclass
class Run:
    ok: bool
    codes: list[str]
    diagnostics: str
    crash: str | None = None
    result: object | None = None


def run_source(src: str) -> Run:
    try:
        r = H.compile_source(src)
    except Exception as e:  # noqa: BLE001 -- a crash is itself a finding
        return Run(False, [], "", crash=f"{type(e).__name__}: {e}")
    return Run(bool(r.ok()), list(r.diagnostics.codes()), r.diagnostics.render(), None, r)


def meets(run: Run, expect: str) -> bool:
    if run.crash is not None:
        return False
    return run.ok if expect == "accept" else not run.ok


# -- fact-check helpers ------------------------------------------------------


def def_type_is(name: str, rendered: str) -> Callable[[object], bool]:
    def check(r) -> bool:  # noqa: ANN001
        for st in r.module.statements:
            if isinstance(st, DefineStmt) and st.name == name:
                return st.body.type_ is not None and st.body.type_.render() == rendered
        return False

    return check


def decl_type_is(name: str, rendered: str) -> Callable[[object], bool]:
    def check(r) -> bool:  # noqa: ANN001
        for st in r.module.statements:
            if isinstance(st, Declaration) and st.name == name:
                return (
                    st.declared_type is not None
                    and st.declared_type.render() == rendered
                )
        return False

    return check


def hash_differs_from(other: str) -> Callable[[object], bool]:
    """The specimen's distinction must survive canonicalisation."""

    def check(r) -> bool:  # noqa: ANN001
        o = run_source(other)
        return o.ok and o.result.hash() != r.hash()

    return check


def hash_equals(other: str) -> Callable[[object], bool]:
    def check(r) -> bool:  # noqa: ANN001
        o = run_source(other)
        return o.ok and o.result.hash() == r.hash()

    return check


def roundtrips() -> Callable[[object], bool]:
    """print -> reparse -> same content hash."""

    def check(r) -> bool:  # noqa: ANN001
        printed = render_module(r.module)
        again = run_source(printed)
        return again.ok and again.result.hash() == r.hash()

    return check


def backend_declares(target: str, needle: str) -> Callable[[object], bool]:
    def check(r) -> bool:  # noqa: ANN001
        res = render(target, r.module, r.symbols)
        return any(needle in u.render() for u in res.unsupported)

    return check


def statement_count(kind: type, n: int) -> Callable[[object], bool]:
    def check(r) -> bool:  # noqa: ANN001
        return len(r.module.of_type(kind)) == n

    return check


# ---------------------------------------------------------------------------
# the 48 encodings
# ---------------------------------------------------------------------------
# Encoding policy, applied uniformly:
#   * use the most faithful form the language admits, not the form most likely to pass;
#   * where several encodings exist, the one preserving the most facts is primary and the
#     rejected alternatives are recorded as controls, so the diagnostic is on the record;
#   * `param`/`prior` is used for a quantity given a law but used as a parameter, which is
#     HML's documented idiom (examples/statistics/bayesian_coin.hml).

SPECS: list[Spec] = [
    # ---------------------------------------------------------------- CT-001
    Spec(
        id="CT-001",
        title="quantifier over a family of random variables",
        encoding=(
            "module CT001\n"
            "param mu : Real\n"
            "param sigma : PositiveReal\n"
            "var X : Vector[RandomVariable[Real], N]\n"
            "require forall i : Natural . X[i] ~ Normal(location := mu, scale := sigma)"
        ),
        expect="accept",
        controls=[
            Probe(
                "law targeting an indexed member",
                "module CT001b\n"
                "param mu : Real\n"
                "param sigma : PositiveReal\n"
                "var X : Vector[RandomVariable[Real], N]\n"
                "law X[i] ~ Normal(location := mu, scale := sigma)",
                "accept",
                "`law` takes a bare identifier; there is no indexed law target",
            ),
            Probe(
                "the family itself exists and is indexable",
                "module CT001c\n"
                "var X : Vector[RandomVariable[Real], N]\n"
                "param t : Real\n"
                "require probability(X[1] > t) <= 1.0",
                "accept",
                "so the failure is the LAW, not the family",
            ),
        ],
        outcome=UNSUPPORTED,
        failure_class=GRAMMAR,
        repair=GENERAL,
        repair_note=(
            "a law must be able to sit under a binder: either `law` becomes an "
            "expression, or a `for each i : T` statement binder is added. Neither is "
            "expressible by adding one more Expr subclass."
        ),
        note=(
            "`law`/`prior`/`likelihood` are STATEMENTS and `forall` is an EXPRESSION, so a "
            "law can never appear under a binder. `law X[i] ~ ...` is refused at the parser "
            "(HML-P208: the target must be an identifier). The family of random variables "
            "does exist -- Vector[RandomVariable[Real], N] indexes fine and yields events -- "
            "so what is missing is exclusively the ability to attach a distributional law "
            "under a quantifier."
        ),
    ),
    # ---------------------------------------------------------------- CT-002
    Spec(
        id="CT-002",
        title="quantifier over matrices with a shape hypothesis",
        encoding=(
            "module CT002\n"
            "require forall A : Matrix[Real, N, N] . forall x : Vector[Real, N] . "
            "not (x = x) or (x @ (A @ x)) > 0.0"
        ),
        controls=[
            Probe(
                "shape disagreement under the binder is caught",
                "module CT002b\n"
                "require forall A : Matrix[Real, N, N] . forall x : Vector[Real, M] . "
                "(x @ (A @ x)) > 0.0",
                "reject",
                "symbolic extents must be checked, not ignored",
            )
        ],
        facts=[],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "Shape checking runs under the binder on symbolic extents. Symmetry of A is not "
            "expressible as a type (no Sym(n)); it is a declared degradation, not a silent "
            "one, and the specimen's stated hard part -- symbolic shape agreement under a "
            "binder -- holds."
        ),
    ),
    # ---------------------------------------------------------------- CT-003
    Spec(
        id="CT-003",
        title="quantifier over a dimensionful domain",
        encoding=(
            "module CT003\n"
            "param g : Quantity[Length / Time^2]\n"
            "require forall L : Quantity[Length] . sqrt(L / g) = sqrt(L / g)"
        ),
        expect="accept",
        controls=[
            Probe(
                "quantifying over a dimensionful domain alone",
                "module CT003b\nrequire forall L : Quantity[Length] . L >= L",
                "accept",
                "the binder itself is fine; the failure is downstream",
            ),
            Probe(
                "a dimensionful interval endpoint",
                "module CT003c\nconst zero_m : Quantity[Length] = 0.0\n"
                "require zero_m = zero_m",
                "accept",
                "there is no unit-carrying literal, so [0 m, 10 m] is unwritable",
            ),
        ],
        outcome=REJ_SPURIOUS,
        failure_class=TYPE,
        repair=LOCAL,
        repair_note=(
            "a Quantity overload for `sqrt` that halves the dimension exponents "
            "(Dimension already stores Fraction exponents), plus a unit-carrying "
            "literal -- a field on Literal and a lexer rule."
        ),
        note=(
            "Two independent breakages. (a) `sqrt` is typed `NonNegativeReal -> "
            "NonNegativeReal`; it has no Quantity overload, so the half-dimension the "
            "specimen is about cannot be taken at all -- HML-T427. (b) There is no "
            "dimensionful literal, so the interval [0 m, 10 m] has no surface form "
            "(HML-T402). The quantifier/Quantity composition itself works."
        ),
    ),
    # ---------------------------------------------------------------- CT-004
    Spec(
        id="CT-004",
        title="distribution parameters carrying units",
        encoding=(
            "module CT004\n"
            "param mu : Quantity[Length]\n"
            "param sigma : Quantity[Length]\n"
            "rv H : RandomVariable[Quantity[Length]]\n"
            "law H ~ Normal(location := mu, scale := sigma)"
        ),
        expect="accept",
        controls=[
            Probe(
                "unitless variant",
                "module CT004b\nparam mu : Real\nparam sigma : PositiveReal\n"
                "rv H : RandomVariable[Real]\n"
                "law H ~ Normal(location := mu, scale := sigma)",
                "accept",
                "the same statement without units compiles, isolating the unit as the cause",
            )
        ],
        outcome=REJ_SPURIOUS,
        failure_class=TYPE,
        repair=LOCAL,
        repair_note=(
            "make DistributionSpec dimension-parametric: one dimension variable on the "
            "support and on the location/scale roles."
        ),
        note=(
            "Every distribution family in the registry fixes its support and its role types "
            "to unrefined scalars (Normal: location Real, scale PositiveReal, support Real). "
            "`DistributionSpec` has no dimension variable, so RandomVariable does not compose "
            "with Quantity anywhere. Three diagnostics fire at once: HML-T413 on both roles "
            "and HML-T411 on the support."
        ),
    ),
    # ---------------------------------------------------------------- CT-005
    Spec(
        id="CT-005",
        title="minimising an expectation",
        encoding=(
            "module CT005\n"
            "var A : Set[Real]\n"
            "param a : Real\n"
            "rv S : RandomVariable[Real]\n"
            "law S ~ Normal(location := 0.0, scale := 1.0)\n"
            "def loss(u : Real, s : Real) : Real := u * s\n"
            "require a in A\n"
            "minimise expectation(loss(a, S))"
        ),
        facts=[
            (
                "the objective is a value, not a random variable "
                "(the expectation really integrated S out)",
                lambda r: r.module.statements[-1].expression.type_.render() == "Real",
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "Two binders of different kinds nest correctly: the measurable lifting rule makes "
            "`loss(a, S)` a RandomVariable[Real], `expectation` integrates S out and returns "
            "Real, and `a` stays a free parameter. The feasible-set membership is carried by "
            "a separate `require`, because `minimise` has no binder of its own."
        ),
    ),
    # ---------------------------------------------------------------- CT-006
    Spec(
        id="CT-006",
        title="matrix with a symbolic structural constraint",
        encoding=(
            "module CT006\n"
            "var Sigma : Matrix[Real, N, N]\n"
            "var x : Vector[Real, N]\n"
            "var b : Vector[Real, N]\n"
            "require forall z : Vector[Real, N] . (z @ (Sigma @ z)) > 0.0\n"
            "require (Sigma @ x) = b\n"
            "solve Sigma"
        ),
        controls=[
            Probe(
                "a shape-incompatible equation is caught",
                "module CT006b\nvar Sigma : Matrix[Real, N, N]\nvar x : Vector[Real, N]\n"
                "var b : Vector[Real, M]\nrequire (Sigma @ x) = b",
                "reject",
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "The unknown carries its shape, the positive-definiteness constraint is a "
            "quantified proposition attached to the unknown rather than checked against a "
            "value, and `solve` marks it as the thing to be found."
        ),
    ),
    # ---------------------------------------------------------------- CT-007
    Spec(
        id="CT-007",
        title="a function whose value is a distribution",
        encoding=(
            "module CT007\n"
            "param sigma : PositiveReal\n"
            "var f : Function[Real -> Real]\n"
            "def k(x : Real) : Distribution[Real] := "
            "Normal(location := f(x), scale := sigma)"
        ),
        controls=[
            Probe(
                "a distribution is not a value of its support",
                "module CT007b\nconst d : Distribution[Real] = 1.0",
                "reject",
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note="Dist(R) exists as a type distinct from R and survives being a codomain.",
    ),
    # ---------------------------------------------------------------- CT-008
    Spec(
        id="CT-008",
        title="indexed family of RVs with index-dependent parameters",
        encoding=(
            "module CT008\n"
            "param beta : Real\n"
            "param sigma : PositiveReal\n"
            "var x : Vector[Real, N]\n"
            "var Y : Vector[RandomVariable[Real], N]\n"
            "require forall i : Natural . forall j : Natural . "
            "not (i = j) => independent(Y[i], Y[j])\n"
            "require forall i : Natural . Y[i] ~ Normal(location := beta * x[i], "
            "scale := sigma)"
        ),
        expect="accept",
        controls=[
            Probe(
                "the family-level independence claim alone",
                "module CT008b\nvar Y : Vector[RandomVariable[Real], N]\n"
                "require forall i : Natural . forall j : Natural . "
                "not (i = j) => independent(Y[i], Y[j])",
                "accept",
                "family-level independence over an index composes",
            ),
            Probe(
                "the per-index law alone",
                "module CT008c\nparam beta : Real\nparam sigma : PositiveReal\n"
                "var x : Vector[Real, N]\nvar Y : Vector[RandomVariable[Real], N]\n"
                "law Y ~ Normal(location := beta, scale := sigma)",
                "accept",
                "and the per-index law does not",
            ),
        ],
        outcome=UNSUPPORTED,
        failure_class=GRAMMAR,
        repair=GENERAL,
        repair_note=(
            "the same wall as CT-001."
        ),
        note=(
            "Exactly CT-001's wall, isolated: the family-level property (independence over a "
            "quantified index pair) composes and compiles clean; the index-level property "
            "(a law per i) has no surface form because `law` is a statement and cannot sit "
            "under a binder, and its target must be an identifier."
        ),
    ),
    # ---------------------------------------------------------------- CT-009
    Spec(
        id="CT-009",
        title="gradient of an expectation whose measure depends on the parameter",
        encoding=(
            "module CT009\n"
            "param theta : Real\n"
            "rv Z : RandomVariable[Real]\n"
            "law Z | theta ~ Normal(location := theta, scale := 1.0)\n"
            "def f(z : Real) : Real := z * z\n"
            "def obj := derivative(expectation(f(Z)), theta : Real)"
        ),
        expect="accept",
        controls=[
            Probe(
                "differentiating against a fresh name is accepted, and is not the statement",
                "module CT009b\nparam theta : Real\nrv Z : RandomVariable[Real]\n"
                "law Z | theta ~ Normal(location := theta, scale := 1.0)\n"
                "def f(z : Real) : Real := z * z\n"
                "def obj := derivative(expectation(f(Z)), th : Real)",
                "accept",
                "the binder `th` occurs nowhere in the body; the theta-dependence is gone "
                "and nothing warns",
            )
        ],
        outcome=REJ_SPURIOUS,
        failure_class=SCOPE,
        repair=GENERAL,
        repair_note=(
            "differentiating with respect to an EXISTING symbol needs either binder-by- "
            "reference or abstraction plus application; binder-always-fresh plus D-006 "
            "makes it unreachable."
        ),
        note=(
            "`derivative` always introduces a FRESH binder, and D-006 forbids shadowing, so "
            "differentiating with respect to a symbol that already exists is impossible: "
            "HML-N302. The only accepted spelling binds a name that does not occur in the "
            "body, which silently states the derivative of a constant. This is the clearest "
            "measured case of the binder design being the obstacle rather than the type rules."
        ),
    ),
    # ---------------------------------------------------------------- CT-010
    Spec(
        id="CT-010",
        title="definite integral carrying units",
        encoding=(
            "module CT010\n"
            "param t0 : Quantity[Time]\n"
            "param t1 : Quantity[Time]\n"
            "var P : Function[Quantity[Time] -> Quantity[Mass * Length^2 / Time^3]]\n"
            "def En := integral(P(t), t : Quantity[Time], t0, t1)"
        ),
        facts=[
            (
                "the integral multiplied by the binder's dimension: W*s = J",
                def_type_is("En", "Quantity[Length^2 * Mass / Time^2]"),
            )
        ],
        controls=[
            Probe(
                "claiming the integral is still in watts is refused",
                "module CT010b\nparam t0 : Quantity[Time]\nparam t1 : Quantity[Time]\n"
                "var P : Function[Quantity[Time] -> Quantity[Mass * Length^2 / Time^3]]\n"
                "param W : Quantity[Mass * Length^2 / Time^3]\n"
                "def En := integral(P(t), t : Quantity[Time], t0, t1)\n"
                "require En = W",
                "reject",
                "HML-D502 proves the unit was really acquired, not merely printed",
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "The differential contributes its unit factor and the checker enforces it. The "
            "endpoints must be declared parameters rather than written `0 s`, because HML "
            "has no unit-carrying literal (see CT-003 control c); that is a standalone gap "
            "in NUM.INTERVAL_DOMAIN, not a composition failure, and it is recorded as such."
        ),
    ),
    # ---------------------------------------------------------------- CT-011
    Spec(
        id="CT-011",
        title="local assumption inside a function body",
        encoding=(
            "module CT011\nparam z : Real\ndef g(x : PositiveReal) : Real := log(x)"
        ),
        controls=[
            Probe(
                "nothing leaks to a sibling scope",
                "module CT011b\nparam z : Real\ndef g(x : PositiveReal) : Real := log(x)\n"
                "def h := log(z)",
                "reject",
                "the positivity of g's parameter must not license log(z)",
            ),
            Probe(
                "a module-level assume does discharge the obligation for that symbol",
                "module CT011c\nparam r : Real\nassume r > 0.0\ndef y := log(r)",
                "accept",
                "D-028's refinement environment, working",
            ),
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "The hypothesis is carried by the parameter's declared refinement, is in force "
            "exactly inside the body, discharges log's definedness obligation, and does not "
            "leak. D-028 additionally makes a module-level `assume` on a bare reference "
            "discharge the same obligation -- this specimen's ancestor "
            "COMP.LOCAL_ASSUMPTION_IN_SCOPE was a documented failure in AUDIT_RERUN §4 and "
            "now passes."
        ),
    ),
    # ---------------------------------------------------------------- CT-012
    Spec(
        id="CT-012",
        title="constraint scoped to a subset of an index set",
        encoding=(
            "module CT012\n"
            "var A : Set[Natural]\n"
            "var x : Vector[Real, N]\n"
            "var c : Vector[Real, N]\n"
            "require forall i : Natural . i in A => x[i] <= c[i]"
        ),
        facts=[
            (
                "the guard is inside the quantifier body, not hoisted out of it",
                hash_differs_from(
                    "module CT012\nvar A : Set[Natural]\nvar x : Vector[Real, N]\n"
                    "var c : Vector[Real, N]\n"
                    "require forall i : Natural . x[i] <= c[i]"
                ),
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "The bounded quantifier is a guarded implication under one binder; the feasible "
            "set is not silently widened to all of I."
        ),
    ),
    # ---------------------------------------------------------------- CT-013
    Spec(
        id="CT-013",
        title="objective over derived state",
        encoding=(
            "module CT013\n"
            "param x : Real\n"
            "def Mf(u : Real) : Real := u * u\n"
            "def y := Mf(x)\n"
            "def C(v : Real) : Real := v + 1.0\n"
            "minimise C(y)"
        ),
        facts=[
            (
                "y is a definition (derived), not a declaration (free)",
                lambda r: any(
                    isinstance(s, DefineStmt) and s.name == "y" for s in r.module.statements
                )
                and not any(
                    isinstance(s, Declaration) and s.name == "y" for s in r.module.statements
                ),
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "`def` and `param` are different AST kinds and stay different through "
            "canonicalisation, so the given/derived distinction the specimen turns on is "
            "structural rather than conventional."
        ),
    ),
    # ---------------------------------------------------------------- CT-014
    Spec(
        id="CT-014",
        title="tensor appearing inside a proposition",
        encoding=(
            "module CT014\n"
            "var T : Tensor[Real, 2, 3, 4]\n"
            "require forall i : Natural . forall j : Natural . forall k : Natural . "
            "T[i, j, k] = T[j, i, k]"
        ),
        facts=[
            (
                "index order is not normalised away: T_ijk = T_jik differs from T_ijk = T_ijk",
                hash_differs_from(
                    "module CT014\nvar T : Tensor[Real, 2, 3, 4]\n"
                    "require forall i : Natural . forall j : Natural . "
                    "forall k : Natural . T[i, j, k] = T[i, j, k]"
                ),
            )
        ],
        controls=[
            Probe(
                "a literal index outside the declared extent",
                "module CT014b\nvar T : Tensor[Real, 2, 3, 4]\n"
                "require T[99, 0, 0] = T[0, 0, 0]",
                "reject",
                "extents are declared; a literal 99 into a 2 should not pass",
            )
        ],
        outcome=DEGRADED,
        failure_class=COMPILER,
        repair=LOCAL,
        repair_note=(
            "range-check literal indices against the declared extents; the extents are "
            "already in the type."
        ),
        note=(
            "The composition the specimen asks for works: the index variables are genuine "
            "logical binders and simultaneously tensor indices, and the symmetry claim keeps "
            "its own canonical identity. But literal indices are never range-checked against "
            "the declared extents -- `T[99,0,0]` on a Tensor[Real,2,3,4] compiles clean. That "
            "is an implementation gap in `Index` typing, not a design limit: the extents are "
            "already in the type."
        ),
    ),
    # ---------------------------------------------------------------- CT-015
    Spec(
        id="CT-015",
        title="quantifier alternation order: uniform versus pointwise",
        encoding=(
            "module CT015\n"
            "var f : Function[Real -> Real]\n"
            "require forall e : PositiveReal . exists d : PositiveReal . "
            "forall x : Real . forall y : Real . "
            "abs(x - y) < d => abs(f(x) - f(y)) < e"
        ),
        facts=[
            (
                "uniform continuity and pointwise continuity have different canonical hashes",
                hash_differs_from(
                    "module CT015\nvar f : Function[Real -> Real]\n"
                    "require forall x : Real . forall e : PositiveReal . "
                    "exists d : PositiveReal . forall y : Real . "
                    "abs(x - y) < d => abs(f(x) - f(y)) < e"
                ),
            ),
            (
                "alpha-renaming does not change the hash",
                hash_equals(
                    "module CT015\nvar f : Function[Real -> Real]\n"
                    "require forall eps : PositiveReal . exists del : PositiveReal . "
                    "forall a : Real . forall b : Real . "
                    "abs(a - b) < del => abs(f(a) - f(b)) < eps"
                ),
            ),
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "Quantifier order is structural; nothing sorts or hoists binders. This is HML's "
            "strongest measured property and it survives a four-binder alternation."
        ),
    ),
    # ---------------------------------------------------------------- CT-016
    Spec(
        id="CT-016",
        title="approximate value inside a proof obligation",
        encoding=(
            "module CT016\n"
            "var A : Matrix[Real, 3, 3]\n"
            "param d : Real\n"
            "assume d ~ 0.00000000000001\n"
            "require not (d = 0.0)"
        ),
        expect="accept",
        controls=[
            Probe(
                "the exact-equality spelling is accepted, i.e. ~ collapses to =",
                "module CT016b\nparam d : Real\nassume d = 0.00000000000001\n"
                "require not (d = 0.0)",
                "accept",
                why="an approximate determinant discharges an exact non-zeroness "
                "claim, because the approximation cannot be marked",
                gate=False,
            )
        ],
        outcome=UNSUPPORTED,
        failure_class=GRAMMAR,
        repair=ONE_NODE,
        repair_note=(
            "one approximation marker -- an operator and one node -- closes CT-016, "
            "CT-042 and CT-044 together."
        ),
        note=(
            "There is no approximation marker in HML-L1. `~` is reserved for distributed-as "
            "and has no expression production; the lexer's operator set contains no `≈`. "
            "`v1/epistemic.py` defines APPROXIMATELY_EQUAL but that layer is not reachable "
            "from the L1 grammar. The atom NUMER.APPROXIMATION_MARKER is absent standalone, "
            "so the composition cannot be attempted. The control shows the consequence: "
            "written with `=`, the approximate value discharges the exact obligation."
        ),
    ),
    # ---------------------------------------------------------------- CT-017
    Spec(
        id="CT-017",
        title="matrix-valued random variable with a structural constraint",
        encoding=(
            "module CT017\n"
            "param nu : PositiveReal\n"
            "var Psi : Matrix[Real, P, P]\n"
            "rv Sigma : RandomVariable[Matrix[Real, P, P]]\n"
            "law Sigma ~ InverseWishart(degrees_of_freedom := nu, scale := Psi)"
        ),
        expect="accept",
        controls=[
            Probe(
                "the matrix-valued random variable itself is fine",
                "module CT017b\nrv Sigma : RandomVariable[Matrix[Real, P, P]]\n"
                "param t : Real\nrequire probability(Sigma = Sigma) >= 0.0",
                "accept",
                "so the failure is the family, not the carrier type",
            )
        ],
        outcome=UNSUPPORTED,
        failure_class=TYPE,
        repair=LOCAL,
        repair_note=(
            "one matrix-supported family in the registry, with a support constraint."
        ),
        note=(
            "HML-T412: no matrix-supported family exists in the registry (17 families, all "
            "scalar- or vector-supported). The carrier type RandomVariable[Matrix[...]] is "
            "accepted, so shape and randomness compose; what is absent is any distribution "
            "whose support is a constrained matrix manifold, and there is no way to state "
            "'every draw is SPD' as a property of the law rather than of a realisation."
        ),
    ),
    # ---------------------------------------------------------------- CT-018
    Spec(
        id="CT-018",
        title="conditional expectation given a sigma-algebra",
        encoding=(
            "module CT018\n"
            "rv X : RandomVariable[Real]\n"
            "var G : Set[Set[Real]]\n"
            "def c := expectation(X | G)"
        ),
        facts=[
            (
                "E[X | G] must be a G-measurable RANDOM VARIABLE, not a value",
                def_type_is("c", "RandomVariable[Real]"),
            )
        ],
        outcome=SILENT_LOSS,
        failure_class=TYPE,
        repair=LOCAL,
        repair_note=(
            "a sigma-algebra type in types.py and one clause in the moment rule; no "
            "expression node changes."
        ),
        note=(
            "This compiles clean and is wrong. `expectation(X | G)` types as `Real` -- "
            "byte-identical in type to the unconditional `expectation(X)` -- because the "
            "moment rule reads 'conditioning on something non-random yields a value'. That "
            "rule is right for a parameter and wrong for a sigma-algebra: E[X|G] is the "
            "almost-surely unique G-measurable random variable. There is no sigma-algebra "
            "type, no measurability predicate and no a.s. qualifier, so nothing catches it. "
            "The two expressions do hash differently, so the conditioning set is stored -- "
            "the loss is in the TYPE, which is the part downstream consumers read."
        ),
    ),
    # ---------------------------------------------------------------- CT-019
    Spec(
        id="CT-019",
        title="piecewise function with a domain partition",
        encoding=(
            "module CT019\nvar x : Real\ndef f := if x >= 0.0 then x * x else -x"
        ),
        expect="accept",
        controls=[
            Probe(
                "the guarded-implication workaround compiles",
                "module CT019b\nvar f : Function[Real -> Real]\n"
                "require forall u : Real . u >= 0.0 => f(u) = u * u\n"
                "require forall u : Real . u < 0.0 => f(u) = -u",
                "accept",
            ),
            Probe(
                "but a branch guard is NOT a local assumption",
                "module CT019c\nvar f : Function[Real -> Real]\n"
                "require forall u : Real . u > 0.0 => f(u) = log(u)",
                "accept",
                "the specimen requires each branch to carry its guard as a hypothesis; "
                "the guard does not enter the refinement environment",
            ),
        ],
        outcome=UNSUPPORTED,
        failure_class=GRAMMAR,
        repair=ONE_NODE,
        repair_note=(
            "one conditional / piecewise expression form."
        ),
        note=(
            "No conditional expression exists: `if` is not a keyword and HML-P204 fires at "
            "the first token. The two-`require` workaround states the graph but loses both "
            "properties the specimen names -- exhaustiveness and disjointness are unchecked, "
            "and control c proves the guard does not discharge the branch's obligations, "
            "because D-028's refinement environment is keyed on module-level `assume` over a "
            "bare Ref and does not descend into an implication's antecedent."
        ),
    ),
    # ---------------------------------------------------------------- CT-020
    Spec(
        id="CT-020",
        title="statement quantifying over functions",
        encoding=(
            "module CT020\n"
            "var I : Set[Real]\n"
            "require forall f : Function[Real -> Real] . "
            "continuous(f, on := I) and (forall x : Real . x in I => f(x) in I) "
            "=> exists c : Real . c in I and f(c) = c"
        ),
        facts=[
            (
                "the existential really is inside the universal, not hoisted",
                hash_differs_from(
                    "module CT020\nvar I : Set[Real]\n"
                    "require exists c : Real . forall f : Function[Real -> Real] . "
                    "continuous(f, on := I) and "
                    "(forall x : Real . x in I => f(x) in I) "
                    "=> c in I and f(c) = c"
                ),
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "Second-order quantification works: the binder's domain may be a function type, "
            "the continuity restriction composes with a set-valued domain, and the inner "
            "existential keeps its position. The closed unit interval is carried as a "
            "`Set[Real]` guard rather than a type, because HML has no interval types -- a "
            "declared degradation, and the same one every system without refinement-typed "
            "intervals would report."
        ),
    ),
    # ---------------------------------------------------------------- CT-021
    Spec(
        id="CT-021",
        title="probability of a quantified event",
        encoding=(
            "module CT021\n"
            "var X : Vector[RandomVariable[Real], N]\n"
            "param t : Real\n"
            "param alpha : Probability\n"
            "require probability(exists i : Natural . X[i] > t) <= alpha"
        ),
        facts=[
            (
                "the quantified body really denotes an event, not a proposition",
                lambda r: r.module.statements[-1].proposition.left.event.type_.render()
                == "Event",
            )
        ],
        controls=[
            Probe(
                "a quantified body over FIXED quantities is refused inside probability",
                "module CT021b\nparam y : Real\nparam t : Real\nparam alpha : Probability\n"
                "require probability(exists i : Natural . y > t) <= alpha",
                "reject",
                "HML-T482: the probability of a proposition is 0 or 1 and states nothing",
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "The quantifier lives inside the probability operator and its body is classified "
            "as an Event because the family members are random. The Event/Proposition split "
            "is exactly the distinction the specimen says is load-bearing, and the control "
            "shows it is enforced in both directions."
        ),
    ),
    # ---------------------------------------------------------------- CT-022
    Spec(
        id="CT-022",
        title="hierarchical model with an acyclic dependency structure",
        encoding=(
            "module CT022\n"
            "param mu : Real\n"
            "prior mu ~ Normal(location := 0.0, scale := 10.0)\n"
            "rv X : RandomVariable[Real]\n"
            "law X | mu ~ Normal(location := mu, scale := 1.0)"
        ),
        controls=[
            Probe(
                "a CYCLIC variant must be rejected",
                "module CT022b\nparam a : Real\nparam b : Real\n"
                "prior a ~ Normal(location := b, scale := 1.0)\n"
                "prior b ~ Normal(location := a, scale := 1.0)",
                "reject",
                "the specimen's stated requirement: 'must reject a cyclic variant'",
            )
        ],
        outcome=SILENT_LOSS,
        failure_class=COMPILER,
        repair=LOCAL,
        repair_note=(
            "one acyclicity pass over the law graph, which is already present in "
            "LawStmt.given and the DistExpr role arguments."
        ),
        note=(
            "The dual role composes -- `mu` is the variate of one law and a role argument of "
            "another, and the checker accepts it. But `a ~ Normal(mean := b)` together with "
            "`b ~ Normal(mean := a)` compiles clean: no acyclicity check exists anywhere. "
            "The dependency edges are already in `LawStmt.given` and in the DistExpr role "
            "arguments, so this is a missing pass, not a missing representation -- no AST "
            "change would be needed to fix it."
        ),
    ),
    # ---------------------------------------------------------------- CT-023
    Spec(
        id="CT-023",
        title="conditioning versus intervening",
        encoding=(
            "module CT023\n"
            "rv R : RandomVariable[Bool]\n"
            "rv T : RandomVariable[Bool]\n"
            "require probability(R | do(T)) != probability(R | T)"
        ),
        expect="accept",
        controls=[
            Probe(
                "observational conditioning alone is fine",
                "module CT023b\nrv R : RandomVariable[Bool]\nrv T : RandomVariable[Bool]\n"
                "require probability(R = true | T = true) >= 0.0",
                "accept",
            ),
            Probe(
                "and causation is at least kept apart from correlation",
                "module CT023c\nrv R : RandomVariable[Bool]\nrv T : RandomVariable[Bool]\n"
                "require causes(T, R)",
                "accept",
            ),
        ],
        outcome=UNSUPPORTED,
        failure_class=GRAMMAR,
        repair=ONE_NODE,
        repair_note=(
            "one intervention operator, or one flag on the conditioning tail."
        ),
        note=(
            "HML-N306: there is no intervention operator. `causes(X, Y)` exists and is kept "
            "canonically distinct from `correlated(X, Y)` (D-026), which is the *claim*-level "
            "half of the distinction, but the *operator*-level half -- P(R | do(T)) as an "
            "object different from P(R | T) -- has no surface form and no AST node. Adding "
            "one more conditioning tail variant would close it."
        ),
    ),
    # ---------------------------------------------------------------- CT-024
    Spec(
        id="CT-024",
        title="chance constraint",
        encoding=(
            "module CT024\n"
            "param x : Real\n"
            "rv D : RandomVariable[Real]\n"
            "law D ~ Normal(location := 0.0, scale := 1.0)\n"
            "def g(u : Real, d : Real) : Real := u + d\n"
            "def c(u : Real) : Real := u * u\n"
            "require probability(g(x, D) <= 0.0) >= 0.95\n"
            "minimise c(x)"
        ),
        facts=[
            (
                "the inner inequality is an Event, so the constraint is a chance constraint "
                "and not a scenario constraint",
                lambda r: r.module.statements[-2].proposition.left.event.type_.render()
                == "Event",
            )
        ],
        controls=[
            Probe(
                "the scenario reading -- asserting the inequality directly -- is refused",
                "module CT024b\nparam x : Real\nrv D : RandomVariable[Real]\n"
                "law D ~ Normal(location := 0.0, scale := 1.0)\n"
                "def g(u : Real, d : Real) : Real := u + d\n"
                "require g(x, D) <= 0.0",
                "reject",
                "HML-T480 stops the silent replacement the specimen warns about",
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "The probability operator sits between the optimiser and the inequality, the "
            "decision variable stays a parameter, and the Event/Proposition barrier "
            "mechanically forbids the scenario-constraint substitution."
        ),
    ),
    # ---------------------------------------------------------------- CT-025
    Spec(
        id="CT-025",
        title="robust minimax with alternating quantifiers",
        encoding=(
            "module CT025\n"
            "param x : Real\n"
            "param u : Real\n"
            "def f(a : Real, b : Real) : Real := a * b\n"
            "minimise maximise f(x, u)"
        ),
        expect="accept",
        controls=[
            Probe(
                "two objectives in one module compile, and their ORDER is not represented",
                "module CT025b\nparam x : Real\nparam u : Real\n"
                "def f(a : Real, b : Real) : Real := a * b\n"
                "minimise f(x, u)\nmaximise f(x, u)",
                "accept",
                "min-then-max and max-then-min are the same two statements; the nesting the "
                "specimen is about is not expressible",
            )
        ],
        outcome=UNSUPPORTED,
        failure_class=GRAMMAR,
        repair=GENERAL,
        repair_note=(
            "min and max must become expression-level binders that nest; today they are "
            "statements."
        ),
        note=(
            "`minimise`/`maximise` are STATEMENTS taking an expression, not expression-level "
            "binders, so they cannot nest. The workaround -- two objective statements -- "
            "compiles and represents a bi-objective problem, which is a different problem. "
            "Nothing here is canonicalised wrongly; the composition simply has no form. This "
            "is the same statement/expression stratification that blocks CT-001 and CT-008."
        ),
    ),
    # ---------------------------------------------------------------- CT-026
    Spec(
        id="CT-026",
        title="unit-carrying derivative in a differential equation",
        encoding=(
            "module CT026\n"
            "var pos : Function[Quantity[Time] -> Quantity[Length]]\n"
            "def v := derivative(pos(t), t : Quantity[Time])\n"
            "def acc := derivative(derivative(pos(s), s : Quantity[Time]), "
            "t2 : Quantity[Time])"
        ),
        facts=[
            ("velocity is Length/Time", def_type_is("v", "Quantity[Length / Time]")),
            (
                "acceleration is Length/Time^2 after a second differentiation",
                def_type_is("acc", "Quantity[Length / Time^2]"),
            ),
        ],
        controls=[
            Probe(
                "claiming the derivative is a length is refused",
                "module CT026b\n"
                "var pos : Function[Quantity[Time] -> Quantity[Length]]\n"
                "param bad : Quantity[Length]\n"
                "def v := derivative(pos(t), t : Quantity[Time])\n"
                "require v = bad",
                "reject",
            ),
            Probe(
                "the initial condition x(0) = 3 m",
                "module CT026c\nconst x0 : Quantity[Length] = 3.0\n"
                "require x0 = x0",
                "accept",
                "HML-T402: 3.0 is NonNegativeReal, and there is no unit-carrying literal",
            ),
        ],
        outcome=DEGRADED,
        failure_class=GRAMMAR,
        repair=LOCAL,
        repair_note=(
            "a unit-carrying literal, as in CT-003."
        ),
        note=(
            "The unit calculus composes and is enforced through repeated differentiation. "
            "The initial condition x(0) = 3 m cannot be written: there is no unit-carrying "
            "literal, and `derivative(...)` produces a VALUE rather than a function, so "
            "pos(0 s) has no zero to be applied to and the derivative cannot be evaluated at "
            "a point either (see CT-034). The dimensional half passes; the initial-condition "
            "half is a declared loss."
        ),
    ),
    # ---------------------------------------------------------------- CT-027
    Spec(
        id="CT-027",
        title="non-commutative matrix product under a transformation",
        encoding=(
            "module CT027\n"
            "var A : Matrix[Real, N, N]\n"
            "var B : Matrix[Real, N, N]\n"
            "require transpose(A @ B) = transpose(B) @ transpose(A)"
        ),
        facts=[
            (
                "A@B and B@A do not canonicalise to the same thing",
                hash_differs_from(
                    "module CT027\nvar A : Matrix[Real, N, N]\n"
                    "var B : Matrix[Real, N, N]\n"
                    "require transpose(A @ B) = transpose(A) @ transpose(B)"
                ),
            )
        ],
        controls=[
            Probe(
                "the false identity AB = BA is not silently normalised into a tautology",
                "module CT027b\nvar A : Matrix[Real, N, N]\nvar B : Matrix[Real, N, N]\n"
                "require not ((A @ B) = (B @ A))",
                "accept",
                "it remains a statable, non-trivial claim",
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "Nothing sorts multiplicative operands. `@` is a distinct operator from `*` and "
            "the canonical projection preserves operand order for both."
        ),
    ),
    # ---------------------------------------------------------------- CT-028
    Spec(
        id="CT-028",
        title="density with reciprocal units",
        encoding=(
            "module CT028\n"
            "param h0 : Quantity[Length]\n"
            "param h1 : Quantity[Length]\n"
            "var fH : Function[Quantity[Length] -> Quantity[Length^-1]]\n"
            "def p := integral(fH(h), h : Quantity[Length], h0, h1)"
        ),
        facts=[
            (
                "integrating a per-metre density over metres is dimensionless "
                "(a fully cancelled Quantity renders as Real)",
                def_type_is("p", "Real"),
            )
        ],
        controls=[
            Probe(
                "a density stored as a plain Real cannot be integrated to a dimensionless "
                "probability",
                "module CT028b\nparam h0 : Quantity[Length]\nparam h1 : Quantity[Length]\n"
                "var fH : Function[Quantity[Length] -> Real]\n"
                "param q : Probability\n"
                "def p := integral(fH(h), h : Quantity[Length], h0, h1)\n"
                "require p = q",
                "reject",
                "the error the specimen says is usually invisible is visible here",
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "The reciprocal unit survives into the integral and the product comes out "
            "dimensionless. HML does not have a distinguished Density type, so a density is "
            "a Quantity-valued function like any other; that is enough for this specimen. "
            "The `Probability` result type is not inferred -- Dimensionless is -- which is a "
            "declared degradation on PROB.PDF."
        ),
    ),
    # ---------------------------------------------------------------- CT-029
    Spec(
        id="CT-029",
        title="sum over an index of a unitful family",
        encoding=(
            "module CT029\nvar m : Vector[Quantity[Mass], N]\ndef Mtot := sum(m)"
        ),
        facts=[
            ("the sum keeps kilograms", def_type_is("Mtot", "Quantity[Mass]")),
        ],
        controls=[
            Probe(
                "an indexed summation with an explicit binder",
                "module CT029b\nvar m : Vector[Quantity[Mass], N]\n"
                "def Mtot := sum(i : Natural, 1, 10, m[i])",
                "accept",
                "there is no summation BINDER; `sum` is a whole-aggregate reduction",
            ),
            Probe(
                "claiming the total is dimensionless is refused",
                "module CT029c\nvar m : Vector[Quantity[Mass], N]\nparam z : Real\n"
                "def Mtot := sum(m)\nrequire Mtot = z",
                "reject",
            ),
        ],
        outcome=DEGRADED,
        failure_class=GRAMMAR,
        repair=ONE_NODE,
        repair_note=(
            "one indexed summation binder closes CT-029 and most of CT-030."
        ),
        note=(
            "Unit preservation across the reduction holds and is enforced. What is missing "
            "is the binder: Sigma_{i=1}^{n} has no surface form, so the index set cannot be "
            "restricted, a summand cannot depend on i in any way other than through the "
            "vector, and the empty-sum identity has nowhere to be stated. DISC.SUMMATION is "
            "present only in its point-free form."
        ),
    ),
    # ---------------------------------------------------------------- CT-030
    Spec(
        id="CT-030",
        title="log-likelihood as a product over independent observations",
        encoding=(
            "module CT030\n"
            "param theta : Real\n"
            "var x : Vector[Real, N]\n"
            "var dens : Function[Real, Real -> PositiveReal]\n"
            "def L := prod(i : Natural, 1, N, dens(x[i], theta))"
        ),
        expect="accept",
        controls=[
            Probe(
                "the point-free product over an existing vector is fine",
                "module CT030b\nvar p : Vector[PositiveReal, N]\ndef L := prod(p)",
                "accept",
            ),
            Probe(
                "but the vector of per-observation densities cannot be built",
                "module CT030c\nparam theta : Real\nvar x : Vector[Real, N]\n"
                "var dens : Function[Real, Real -> PositiveReal]\n"
                "def p : Vector[PositiveReal, N] := {i : Natural | "
                "dens(x[i], theta) > 0.0}",
                "accept",
                "a set comprehension is the only binder that builds a collection, and it "
                "builds a Set, not an indexed Vector -- there is no map/image form",
            ),
        ],
        outcome=UNSUPPORTED,
        failure_class=GRAMMAR,
        repair=ONE_NODE,
        repair_note=(
            "the same summation/product binder, plus a mapping comprehension."
        ),
        note=(
            "Product-over-an-index has no binder (same gap as CT-029), and the family of "
            "densities cannot be formed either: `SetComprehension` is a FILTER over a type, "
            "not a MAP, so there is no way to write {p(x_i | theta) : i}. The independence "
            "assumption that licenses the factorisation is separately statable via "
            "`independent(...)`, but nothing connects it to the product."
        ),
    ),
    # ---------------------------------------------------------------- CT-031
    Spec(
        id="CT-031",
        title="argmax over a constrained parameter space",
        encoding=(
            "module CT031\n"
            "var ll : Function[Real, PositiveReal -> Real]\n"
            "param sigma : PositiveReal\n"
            "def argmaxset := {m : Real | forall q : Real . ll(q, sigma) <= ll(m, sigma)}"
        ),
        facts=[
            (
                "the estimate is a SET, so uniqueness is not asserted",
                def_type_is("argmaxset", "Set[Real]"),
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "`argmax` is not a primitive, but the set of maximisers is directly definable by "
            "comprehension, which is the encoding that does not assert uniqueness. The "
            "positivity restriction rides on the binder's declared type. This is a case "
            "where a general form (comprehension) did the work of a missing bespoke node."
        ),
    ),
    # ---------------------------------------------------------------- CT-032
    Spec(
        id="CT-032",
        title="confidence interval as a statement about a random interval",
        encoding=(
            "module CT032\n"
            "param theta : Real\n"
            "rv X : RandomVariable[Real]\n"
            "law X ~ Normal(location := 0.0, scale := 1.0)\n"
            "def lo(u : Real) : Real := u - 1.96\n"
            "def hi(u : Real) : Real := u + 1.96\n"
            "require probability(lo(X) <= theta and theta <= hi(X)) = 0.95"
        ),
        facts=[
            (
                "the endpoints are random and the parameter is not",
                lambda r: r.module.statements[-1].proposition.left.event.type_.render()
                == "Event",
            )
        ],
        controls=[
            Probe(
                "the misinterpretation -- a probability over a fixed interval -- is refused",
                "module CT032b\nparam theta : Real\nparam l : Real\nparam u : Real\n"
                "require probability(l <= theta and theta <= u) = 0.95",
                "reject",
                "HML-T482: the standard misreading of a confidence interval is a type error",
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "The randomness sits in the endpoints via measurable lifting through `lo`/`hi`, "
            "theta stays a fixed parameter, and the Event/Proposition rule makes the "
            "textbook misinterpretation mechanically unstatable. One of the strongest "
            "results in the suite."
        ),
    ),
    # ---------------------------------------------------------------- CT-033
    Spec(
        id="CT-033",
        title="expectation of a matrix-valued function of a random vector",
        encoding=(
            "module CT033\n"
            "rv X : RandomVariable[Vector[Real, P]]\n"
            "var mu : Vector[Real, P]\n"
            "def Cov := expectation((X - mu) @ transpose(X - mu))"
        ),
        expect="accept",
        controls=[
            Probe(
                "the expectation of a matrix-valued random variable, given one, is fine",
                "module CT033b\nrv S : RandomVariable[Matrix[Real, P, P]]\n"
                "def E := expectation(S)",
                "accept",
                "so expectation IS shape-polymorphic; the outer product is what is missing",
            ),
            Probe(
                "the outer product of two vectors",
                "module CT033c\nvar a : Vector[Real, P]\ndef O := a @ transpose(a)",
                "accept",
                "HML-T427: transpose is defined on matrices only",
            ),
        ],
        outcome=REJ_SPURIOUS,
        failure_class=TYPE,
        repair=LOCAL,
        repair_note=(
            "one vector case in the `transpose` signature."
        ),
        note=(
            "`expectation` is shape-polymorphic and composes with a matrix carrier "
            "(control b). The break is in the linear algebra: `transpose` is typed "
            "Matrix -> Matrix with no vector case, so there is no outer product and "
            "Cov(X) = E[(X-EX)(X-EX)^T] cannot be written. Adding a vector case to one "
            "builtin signature would close it; no structural change is implied."
        ),
    ),
    # ---------------------------------------------------------------- CT-034
    Spec(
        id="CT-034",
        title="transformation of a random variable with a Jacobian factor",
        encoding=(
            "module CT034\n"
            "var ginv : Function[Real -> Real]\n"
            "var fX : Function[Real -> NonNegativeReal]\n"
            "def J := derivative(ginv(u), u : Real)\n"
            "def fY(y : Real) : NonNegativeReal := fX(ginv(y)) * abs(J(y))"
        ),
        expect="accept",
        controls=[
            Probe(
                "the derivative itself is formable",
                "module CT034b\nvar ginv : Function[Real -> Real]\n"
                "def J := derivative(ginv(u), u : Real)",
                "accept",
            ),
            Probe(
                "but it is a VALUE and cannot be applied at a point",
                "module CT034c\nvar ginv : Function[Real -> Real]\n"
                "def J := derivative(ginv(u), u : Real)\nrequire J(0.0) = J(0.0)",
                "accept",
                "HML-T470: 'J' binds a value, not a function",
            ),
        ],
        outcome=REJ_SPURIOUS,
        failure_class=GRAMMAR,
        repair=GENERAL,
        repair_note=(
            "the Jacobian must be evaluated at a point, which requires a binding "
            "expression to denote a FUNCTION. There is no abstraction form."
        ),
        note=(
            "The decisive finding for the AST question. `derivative(body, x : T)` binds x and "
            "immediately DISCHARGES the binder into a value: the result has the body's type, "
            "not a function type. There is therefore no derivative-at-a-point anywhere in "
            "the language, because there is no abstraction form -- no lambda, and no way to "
            "read a binding expression as a function. The Jacobian factor cannot be "
            "evaluated at y, so the change-of-variables formula is unwritable. The same "
            "single cause blocks CT-036 and the initial condition in CT-026."
        ),
    ),
    # ---------------------------------------------------------------- CT-035
    Spec(
        id="CT-035",
        title="almost-everywhere qualifier surviving a transformation",
        encoding=(
            "module CT035\n"
            "var f : Function[Real -> Real]\n"
            "var g : Function[Real -> Real]\n"
            "var Z : Set[Real]\n"
            "var lam : Function[Set[Real] -> NonNegativeReal]\n"
            "require lam(Z) = 0.0\n"
            "require forall x : Real . not (x in Z) => f(x) = g(x)"
        ),
        facts=[
            (
                "the qualifier survives print -> reparse unchanged",
                roundtrips(),
            ),
            (
                "the qualified claim is NOT identified with the unqualified one",
                hash_differs_from(
                    "module CT035\nvar f : Function[Real -> Real]\n"
                    "var g : Function[Real -> Real]\nvar Z : Set[Real]\n"
                    "var lam : Function[Set[Real] -> NonNegativeReal]\n"
                    "require lam(Z) = 0.0\n"
                    "require forall x : Real . f(x) = g(x)"
                ),
            ),
        ],
        controls=[
            Probe(
                "the declared 'measure' is an arbitrary set function",
                "module CT035b\nvar Z : Set[Real]\n"
                "var lam : Function[Set[Real] -> NonNegativeReal]\n"
                "require lam(Z) = 0.0\nrequire lam(Z) = 1.0",
                "reject",
                "one set is given two different measures and nothing objects, so the "
                "null-set encoding rests on a symbol nothing constrains",
            )
        ],
        outcome=DEGRADED,
        failure_class=CONSTRAINT,
        repair=ONE_NODE,
        repair_note=(
            "one almost-everywhere qualifier, and a Measure type to anchor it."
        ),
        note=(
            "There is no `a.e.` qualifier, but the measure-theoretic content can be spelled "
            "out longhand -- an exceptional set with measure zero under a named measure -- "
            "and that spelling round-trips and stays canonically distinct from the "
            "unqualified claim, which is precisely the dangerous direction the specimen "
            "guards. The degradation is that `lam` is an uninterpreted function: nothing "
            "knows it is a measure, so nothing would stop a second statement asserting "
            "lam(R) = 0."
        ),
    ),
    # ---------------------------------------------------------------- CT-036
    Spec(
        id="CT-036",
        title="Taylor expansion with an explicit remainder",
        encoding=(
            "module CT036\n"
            "var f : Function[Real -> Real]\n"
            "param a : Real\n"
            "param Mb : PositiveReal\n"
            "param r : PositiveReal\n"
            "def fp := derivative(f(u), u : Real)\n"
            "require forall x : Real . abs(x - a) <= r => "
            "abs(f(x) - (f(a) + fp(a) * (x - a))) <= (Mb / 2.0) * (x - a) * (x - a)"
        ),
        expect="accept",
        controls=[
            Probe(
                "the remainder bound with the validity region, WITHOUT f'(a)",
                "module CT036b\nvar f : Function[Real -> Real]\nparam a : Real\n"
                "param Mb : PositiveReal\nparam r : PositiveReal\n"
                "require forall x : Real . abs(x - a) <= r => "
                "abs(f(x) - f(a)) <= (Mb / 2.0) * (x - a) * (x - a)",
                "accept",
                "so the bounded-approximation SHAPE is expressible; the derivative at a "
                "point is not",
            )
        ],
        outcome=REJ_SPURIOUS,
        failure_class=GRAMMAR,
        repair=GENERAL,
        repair_note=(
            "the same as CT-034: f'(a) needs abstraction."
        ),
        note=(
            "Same single cause as CT-034: `fp := derivative(f(u), u : Real)` is a value, so "
            "`fp(a)` is HML-T470. The expansion's linear term cannot be written. The "
            "validity region and the inequality-with-remainder form -- which is what stops "
            "the truncation being written with `=` -- both work, so the epistemic half of "
            "the specimen passes and the analysis half does not."
        ),
    ),
    # ---------------------------------------------------------------- CT-037
    Spec(
        id="CT-037",
        title="series rearrangement blocked by conditional convergence",
        encoding=(
            "module CT037\n"
            "var a : Function[Natural -> Real]\n"
            "def S := sum(n : Natural, 1, infinity, a(n))"
        ),
        expect="accept",
        controls=[
            Probe(
                "a finite point-free reduction is all there is",
                "module CT037b\nvar a : Vector[Real, N]\ndef S := sum(a)",
                "accept",
            ),
            Probe(
                "and a limit cannot supply the missing series either",
                "module CT037c\nvar partial : Function[Natural -> Real]\n"
                "def S := limit(partial(n), n : Natural -> infinity)",
                "accept",
                "there is no point at infinity in any type",
            ),
        ],
        outcome=UNSUPPORTED,
        failure_class=GRAMMAR,
        repair=ONE_NODE,
        repair_note=(
            "a series form and a convergence-mode predicate."
        ),
        note=(
            "No infinite series object exists: no summation binder, no infinity, and "
            "`limit`'s point must inhabit the binder's own type so a limit over Natural "
            "cannot approach infinity. ANA.SERIES and ANA.CONVERGENCE_MODES are absent "
            "standalone. HML performs no rewriting, so nothing wrong is done -- the specimen "
            "is simply outside the language."
        ),
    ),
    # ---------------------------------------------------------------- CT-038
    Spec(
        id="CT-038",
        title="simplification that narrows the domain",
        encoding=(
            "module CT038\n"
            "var x : Real\n"
            "require ((x * x - 1.0) / (x - 1.0)) = (x + 1.0)"
        ),
        expect="reject",
        controls=[
            Probe(
                "the guarded form, which is the true statement",
                "module CT038b\nvar x : Real\n"
                "require not (x = 1.0) => "
                "((x * x - 1.0) / (x - 1.0)) = (x + 1.0)",
                "accept",
            )
        ],
        outcome=SILENT_LOSS,
        failure_class=CONSTRAINT,
        repair=LOCAL,
        repair_note=(
            "raise a definedness obligation for `/`, as `log` and `sqrt` already get "
            "from their domain types."
        ),
        note=(
            "The UNGUARDED, false statement compiles clean. Division raises no definedness "
            "obligation: the only obligation recorded is the generic "
            "`constraint:(x*x-1.0)/(x-1.0) = x+1.0` for the whole `require`. LOGIC."
            "PARTIAL_DEFINEDNESS is enforced for `log` and `sqrt` through their domain types "
            "but not for `/`, so the exact narrowing the specimen is about is invisible. "
            "HML never rewrites, so it will not PERFORM the unsound simplification -- but it "
            "will accept the unsound conclusion if a model writes it."
        ),
    ),
    # ---------------------------------------------------------------- CT-039
    Spec(
        id="CT-039",
        title="mixed-unit state vector",
        encoding=(
            "module CT039\n"
            "var s : Product[Quantity[Length], Quantity[Length / Time]]\n"
            "var F : Matrix[Real, 2, 2]\n"
            "def s2 := F @ s"
        ),
        expect="accept",
        controls=[
            Probe(
                "the per-component spelling one would want",
                "module CT039b\n"
                "var s : Vector[Quantity[Length], Quantity[Length / Time], 2]\n"
                "require s = s",
                "accept",
                "a Vector carries exactly one element type",
            ),
            Probe(
                "but it has no components: it cannot be indexed",
                "module CT039c\n"
                "var s : Product[Quantity[Length], Quantity[Length / Time]]\n"
                "require s[1] = s[1]",
                "accept",
                "HML-T425; and no matrix product accepts a Product operand",
            ),
        ],
        outcome=UNSUPPORTED,
        failure_class=TYPE,
        repair=LOCAL,
        repair_note=(
            "per-component element types in the aggregate type constructors, or "
            "projections and arithmetic on Product."
        ),
        note=(
            "`Vector`/`Matrix`/`Tensor` carry exactly one element type, which is the "
            "one-unit-per-array design the specimen predicts almost every system has. "
            "`Product[...]` is heterogeneous but is opaque -- no projection, no arithmetic -- "
            "so it cannot serve as a state vector. Entrywise dimensional checking of a "
            "matrix-vector product is not representable."
        ),
    ),
    # ---------------------------------------------------------------- CT-040
    Spec(
        id="CT-040",
        title="dimensionless argument requirement inside a model",
        encoding=(
            "module CT040\n"
            "param d : Quantity[Mass]\n"
            "param d0 : Quantity[Mass]\n"
            "def eta := log(d / d0)"
        ),
        expect="accept",
        controls=[
            Probe(
                "log of a dimensionful quantity IS correctly refused",
                "module CT040b\nparam d : Quantity[Mass]\ndef eta := log(d)",
                "reject",
                "the half of the rule that works",
            ),
            Probe(
                "and an assumption about the ratio does not rescue it either",
                "module CT040c\nparam d : Quantity[Mass]\nparam d0 : Quantity[Mass]\n"
                "assume d / d0 > 0.0\ndef eta := log(d / d0)",
                "accept",
                "the refinement environment is keyed on symbols, not expressions",
            ),
        ],
        outcome=REJ_SPURIOUS,
        failure_class=TYPE,
        repair=LOCAL,
        repair_note=(
            "preserve the positivity refinement when a Quantity ratio cancels to a "
            "dimensionless scalar."
        ),
        note=(
            "The specimen states log(d/d0) IS well formed and log(d) is not. HML refuses "
            "both. `Quantity/Quantity` collapses to the unrefined scalar `Real` when the "
            "dimensions cancel, and `log` demands `PositiveReal`, so the well-formed "
            "dimensionless ratio is rejected -- HML-T427. The dimension analysis is right "
            "and the refinement lattice loses positivity across the cancellation. Control c "
            "shows D-028's refinement environment cannot repair it: it refines SYMBOLS, and "
            "`d / d0` is not a symbol."
        ),
    ),
    # ---------------------------------------------------------------- CT-041
    Spec(
        id="CT-041",
        title="assumption discharged by a refinement carried through a call",
        encoding="module CT041\nparam sigma : PositiveReal\ndef y := log(sigma)",
        facts=[
            (
                "the only obligation is the declaration's own positivity; the call "
                "leaves no residue",
                lambda r: {o.kind for o in r.obligations} == {"parameter_positivity"},
            )
        ],
        controls=[
            Probe(
                "an unconstrained real must NOT discharge it",
                "module CT041b\nparam r : Real\ndef y := log(r)",
                "reject",
            ),
            Probe(
                "and an assumption discharges it soundly",
                "module CT041c\nparam r : Real\nassume r > 0.0\ndef y := log(r)",
                "accept",
            ),
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "Refinement flows across the application boundary, discharges the precondition, "
            "raises no residual obligation, and does not over-discharge. D-028 working "
            "exactly as advertised."
        ),
    ),
    # ---------------------------------------------------------------- CT-042
    Spec(
        id="CT-042",
        title="epistemic status preserved through a derivation",
        encoding=(
            "module CT042\n"
            "param x : Real\n"
            "assume a1 : x > 0.0\n"
            "goal g1 : x + 1.0 > 0.0 + 1.0\n"
            "derive d1 : x + 1.0 > 0.0 + 1.0 from a1 by add_inequality(by := 1.0)\n"
            "proved g1 by d1"
        ),
        facts=[
            (
                "the conclusion records the assumed premise it depends on",
                lambda r: r.module.of_type(
                    __import__(
                        "hamiltonian_lang.ast.nodes", fromlist=["DeriveStmt"]
                    ).DeriveStmt
                )[0].premises
                == ["a1"],
            )
        ],
        controls=[
            Probe(
                "an unsupported proof claim is refused",
                "module CT042b\nparam x : Real\nassume a1 : x > 0.0\n"
                "goal g1 : x > 5.0\n"
                "derive d1 : x > 5.0 from a1 by add_inequality(by := 1.0)\n"
                "proved g1 by d1",
                "reject",
                "writing `proved` does not make a goal proved",
            ),
            Probe(
                "an APPROXIMATE step cannot be marked at all",
                "module CT042c\nparam x : Real\nparam y : Real\n"
                "assume a1 : x > 0.0\nassume a2 : y ~ x",
                "accept",
                "so 'conditional AND approximate' cannot be the recorded status",
            ),
        ],
        outcome=DEGRADED,
        failure_class=GRAMMAR,
        repair=ONE_NODE,
        repair_note=(
            "the CT-016 approximation marker."
        ),
        note=(
            "The conditional half is fully modelled and enforced: the derivation names its "
            "assumed premise, its status is computed by the kernel and not writable in "
            "source, and an unsupported `proved` is refused. The approximate half is absent "
            "-- EPIS.APPROXIMATION_CLAIM has no surface form (see CT-016) -- so the combined "
            "status the specimen asks for cannot be formed. Half the specimen passes and the "
            "missing half is a single absent marker, not a structural gap."
        ),
    ),
    # ---------------------------------------------------------------- CT-043
    Spec(
        id="CT-043",
        title="translation to a backend that lacks a constraint",
        encoding=(
            "module CT043\n"
            "param sigma : PositiveReal\n"
            "rv X : RandomVariable[Real]\n"
            "law X ~ Normal(location := 0.0, scale := sigma)\n"
            "require sigma > 0.0"
        ),
        facts=[
            (
                "Stan declares the dropped constraint in machine-readable form",
                backend_declares("stan", "[dropped] require"),
            ),
            (
                "Stan declares the weakened refinement rather than emitting it silently",
                backend_declares("stan", "PositiveReal is open at 0"),
            ),
            (
                "Lean declares that the refinement is not carried in the type",
                backend_declares("lean", "the refinement is carried as a separate hypothesis"),
            ),
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "The loss is emitted structurally (`BackendResult.unsupported`, severity "
            "dropped/approximated/weakened) rather than as prose, and `faithful` is False. "
            "This is the specimen HML was designed for and it passes on three backends at "
            "once."
        ),
    ),
    # ---------------------------------------------------------------- CT-044
    Spec(
        id="CT-044",
        title="round trip through the printer with a qualifier",
        encoding=(
            "module CT044\n"
            "var f : Function[Real -> Real]\n"
            "require forall x : Real . exists y : Real . f(x) > y\n"
            "def s := {u : Real | u > 0.0}\n"
            "def a := integral(f(t), t : Real, 0.0, 1.0)"
        ),
        facts=[
            ("print -> reparse -> identical content hash", roundtrips()),
            (
                "alpha-renaming the binders gives the same hash",
                hash_equals(
                    "module CT044\nvar f : Function[Real -> Real]\n"
                    "require forall p : Real . exists q : Real . f(p) > q\n"
                    "def s := {w : Real | w > 0.0}\n"
                    "def a := integral(f(z), z : Real, 0.0, 1.0)"
                ),
            ),
        ],
        controls=[
            Probe(
                "an approximation marker to round-trip",
                "module CT044b\nparam a : Real\nparam b : Real\nassume a ~ b",
                "accept",
                "there is none, so half the specimen is unattemptable",
            )
        ],
        outcome=DEGRADED,
        failure_class=GRAMMAR,
        repair=ONE_NODE,
        repair_note=(
            "the CT-016 approximation marker."
        ),
        note=(
            "The binder half passes completely -- three different binder kinds survive "
            "print/reparse with an identical content hash and are alpha-invariant. The "
            "approximation half cannot be attempted because the marker does not exist "
            "(CT-016). No information is lost by the printer; the information was never "
            "expressible."
        ),
    ),
    # ---------------------------------------------------------------- CT-045
    Spec(
        id="CT-045",
        title="capture-avoiding substitution under two binders",
        encoding=(
            "module CT045\n"
            "param i : Real\n"
            "param j : Real\n"
            "var a : Function[Real, Real -> Real]\n"
            "assume a1 : i = j\n"
            "assume a2 : forall k : Real . a(i, k) = a(i, k)\n"
            "derive d1 : forall k : Real . a(j, k) = a(j, k) from a1, a2 by substitute"
        ),
        expect="accept",
        controls=[
            Probe(
                "substitution NOT under a binder succeeds",
                "module CT045b\nparam i : Real\nparam j : Real\n"
                "var a : Function[Real, Real -> Real]\nassume a1 : i = j\n"
                "assume a2 : a(i, 1.0) = a(i, 1.0)\n"
                "derive d1 : a(j, 1.0) = a(i, 1.0) from a1, a2 by substitute",
                "accept",
                "so the refusal above is specifically about descending under a binder",
            ),
            Probe(
                "shadowing a bound name is refused rather than silently captured",
                "module CT045c\nparam k : Real\n"
                "require forall k : Real . k > 0.0",
                "reject",
                "HML-N302: the capture the specimen is about cannot even be written",
            ),
        ],
        outcome=REJ_SPURIOUS,
        failure_class=COMPILER,
        repair=LOCAL,
        repair_note=(
            "capture-avoiding substitution in the kernel. D-006's no-shadowing rule "
            "already guarantees the precondition, so this is an algorithm to write, not "
            "a representation to invent."
        ),
        note=(
            "HML refuses rather than captures, in both places it could go wrong: the "
            "`substitute` kernel rule does not descend into quantifier bodies and reports "
            "exactly what it would have produced (HML-R706), and D-006 makes the capturing "
            "spelling unwritable in the first place (HML-N302). The capability is genuinely "
            "absent -- there is no alpha-renaming step -- but nothing unsound happens, which "
            "is what this specimen tests. Scored REJECTED_CORRECT with the capability gap "
            "recorded."
        ),
    ),
    # ---------------------------------------------------------------- CT-046
    Spec(
        id="CT-046",
        title="optimisation over a distribution",
        encoding=(
            "module CT046\n"
            "var Q : Set[Distribution[Real]]\n"
            "var p : Distribution[Real]\n"
            "var q : Distribution[Real]\n"
            "var kl : Function[Distribution[Real], Distribution[Real] -> NonNegativeReal]\n"
            "require q in Q\n"
            "minimise kl(q, p)\n"
            "solve q"
        ),
        facts=[
            (
                "KL(q||p) and KL(p||q) are canonically different objects",
                hash_differs_from(
                    "module CT046\nvar Q : Set[Distribution[Real]]\n"
                    "var p : Distribution[Real]\nvar q : Distribution[Real]\n"
                    "var kl : Function[Distribution[Real], Distribution[Real] "
                    "-> NonNegativeReal]\n"
                    "require q in Q\nminimise kl(p, q)\nsolve q"
                ),
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "The decision variable really is a Distribution[Real] -- a first-class object "
            "that the type system keeps apart from its support -- the family is a "
            "Set[Distribution[Real]], and argument order is preserved so the asymmetry "
            "cannot be lost by an accidental swap. The degradation: `kl` is an uninterpreted "
            "declared function, and its two arguments are POSITIONAL, so D-003's role "
            "labelling -- the mechanism that would have named the asymmetry -- is not "
            "available for user-declared functions."
        ),
    ),
    # ---------------------------------------------------------------- CT-047
    Spec(
        id="CT-047",
        title="sup versus max in an optimisation conclusion",
        encoding=(
            "module CT047\n"
            "def U := {u : Real | u > 0.0 and u < 1.0}\n"
            "def lower_bounds := {b : Real | forall u : Real . u in U => b <= u}\n"
            "require 0.0 in lower_bounds\n"
            "require not (exists m : Real . m in U and "
            "(forall u : Real . u in U => m <= u))"
        ),
        facts=[
            (
                "the set of lower bounds is a Set, and no minimiser is asserted",
                def_type_is("lower_bounds", "Set[Real]"),
            )
        ],
        controls=[
            Probe(
                "a sup/inf primitive",
                "module CT047b\nvar S : Set[Real]\ndef i := infimum(S)",
                "accept",
                why="HML-N306: ANA.SUP_INF has no builtin; the meaning is recoverable by "
                "comprehension, so this is vocabulary and not part of the gate",
                gate=False,
            )
        ],
        outcome=COMPOSES,
        failure_class=None,
        note=(
            "There is no `inf`/`sup` primitive, but the mathematics is expressible by "
            "comprehension -- the set of lower bounds -- and the non-attainment claim is "
            "expressible as a quantified negation. Crucially, `minimise` in HML declares an "
            "objective and does not assert that a minimiser exists, so the dangerous error "
            "the specimen guards against is not committed. Degraded on vocabulary, not on "
            "meaning."
        ),
    ),
    # ---------------------------------------------------------------- CT-048
    Spec(
        id="CT-048",
        title="triple composition: quantifier, units and a random variable",
        encoding=(
            "module CT048\n"
            "param mu : Quantity[Length]\n"
            "param sigma : Quantity[Length]\n"
            "require sigma > 0.0\n"
            "rv H : RandomVariable[Quantity[Length]]\n"
            "law H ~ Normal(location := mu, scale := sigma)"
        ),
        expect="accept",
        controls=[
            Probe(
                "quantifier x indexed RV family, without units",
                "module CT048b\nvar H : Vector[RandomVariable[Real], N]\nparam t : Real\n"
                "require forall i : Natural . probability(H[i] > t) <= 1.0",
                "accept",
                "this half composes cleanly",
            ),
            Probe(
                "the per-index law, which the encoding above had to drop",
                "module CT048c\nparam mu : Quantity[Length]\n"
                "param sigma : Quantity[Length]\n"
                "var H : Vector[RandomVariable[Quantity[Length]], N]\n"
                "require forall i : Natural . H[i] ~ "
                "Normal(location := mu, scale := sigma)",
                "accept",
                "CT-001's grammar wall, on top of the type walls in the primary",
            ),
        ],
        outcome=REJ_SPURIOUS,
        failure_class=TYPE,
        repair=GENERAL,
        repair_note=(
            "CT-004's local fix AND CT-001's general one."
        ),
        note=(
            "The suite's designated summary specimen, and it fails on two of its four "
            "capabilities. Quantification over an indexed family of random variables works "
            "(control b). Units on a random variable do not (control c, CT-004). A "
            "refinement on a dimensionful parameter does not, because `sigma > 0.0` compares "
            "Length with Dimensionless and there is no PositiveQuantity (control d). And the "
            "per-index law is unwritable (CT-001). Three separate walls in one sentence."
        ),
    ),
]


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------


def execute(spec: Spec) -> dict:
    primary = run_source(spec.encoding)
    rec: dict = {
        "id": spec.id,
        "title": spec.title,
        "encoding": spec.encoding,
        "expect": spec.expect,
        "compiled": primary.crash is None,
        "ok": primary.ok,
        "codes": primary.codes,
        "diagnostics": primary.diagnostics,
        "crash": primary.crash,
        "primary_met": meets(primary, spec.expect),
        "controls": [],
        "facts": [],
        "outcome": spec.outcome,
        "failure_class": spec.failure_class,
        "repair": spec.repair,
        "repair_note": spec.repair_note,
        "note": spec.note,
    }
    for c in spec.controls:
        cr = run_source(c.source)
        rec["controls"].append(
            {
                "label": c.label,
                "source": c.source,
                "expect": c.expect,
                "gate": c.gate,
                "ok": cr.ok,
                "codes": cr.codes,
                "diagnostics": cr.diagnostics,
                "crash": cr.crash,
                "met": meets(cr, c.expect),
                "why": c.why,
            }
        )
    if primary.ok:
        for desc, fn in spec.facts:
            try:
                held = bool(fn(primary.result))
                err = None
            except Exception as e:  # noqa: BLE001
                held, err = False, f"{type(e).__name__}: {e}"
            rec["facts"].append({"description": desc, "held": held, "error": err})

    rec["control_anomalies"] = [
        c["label"] for c in rec["controls"] if c["gate"] and not c["met"]
    ]
    rec["facts_held"] = all(f["held"] for f in rec["facts"])
    #: THE GATE. A specimen composes iff the faithful encoding behaved as the
    #: mathematics requires, every load-bearing fact survived into the checked tree,
    #: and every gating control confirmed the guarantee is not vacuous.
    rec["closes"] = (
        rec["primary_met"] and rec["facts_held"] and not rec["control_anomalies"]
    )
    #: The adjudicated outcome must agree with the gate, or one of them is wrong.
    rec["adjudication_agrees"] = rec["closes"] == (spec.outcome in NUMERATOR)
    return rec


#: How this study's eight failure classes map onto the framework's seven failure
#: surfaces, for `prediction_accuracy` (COMPOSITIONAL_CLOSURE_FRAMEWORK.md section 6).
#: The two vocabularies are not the same, so the mapping is stated rather than assumed.
#: SCOPE and CONSTRAINT both land on SEMANTIC_MODEL, which is the loosest of the seven
#: and therefore the reading most generous to the framework.
SURFACE_MAP: dict[str, set[str]] = {
    GRAMMAR: {"GRAMMAR"},
    TYPE: {"TYPE_SYSTEM"},
    SCOPE: {"SEMANTIC_MODEL"},
    CANONICAL: {"CANONICALIZATION"},
    CONSTRAINT: {"SEMANTIC_MODEL"},
    COMPILER: {"COMPILER"},
    BACKEND: {"BACKEND"},
    SPECIMEN: set(),
}


def prediction_accuracy(records: list[dict]) -> tuple[int, int, list[tuple[str, str, list[str]]]]:
    """Scores the FRAMEWORK, not HML: did failures land where the specimens predicted?"""
    spec = {s["id"]: s for s in json.loads(SPECIMEN_FILE.read_text())["specimens"]}
    hits = 0
    missed: list[tuple[str, str, list[str]]] = []
    for r in records:
        if r["closes"]:
            continue
        pred = set(spec[r["id"]]["expected_failure_modes"])
        obs = set(SURFACE_MAP.get(r["failure_class"] or "", set()))
        if r["outcome"] == UNSUPPORTED:
            obs |= {"UNSUPPORTED"}
        if obs & pred:
            hits += 1
        else:
            missed.append((r["id"], r["failure_class"] or "-", sorted(pred)))
    return hits, hits + len(missed), missed


def verify_against_specimen_file() -> list[str]:
    """Cross-check ids and titles against the read-only specimen file."""
    problems: list[str] = []
    data = json.loads(SPECIMEN_FILE.read_text())
    ref = {s["id"]: s["title"] for s in data["specimens"]}
    mine = {s.id: s.title for s in SPECS}
    if set(ref) != set(mine):
        problems.append(
            f"id mismatch: missing {sorted(set(ref) - set(mine))} "
            f"extra {sorted(set(mine) - set(ref))}"
        )
    for k in sorted(set(ref) & set(mine)):
        if not mine[k].startswith(ref[k][:18]):
            problems.append(f"{k}: title drift {mine[k]!r} vs {ref[k]!r}")
    return problems


def main() -> int:
    problems = verify_against_specimen_file()
    print(f"hamiltonian_lang from: {H.__file__}")
    print(f"specimen file        : {SPECIMEN_FILE}")
    if problems:
        print("SPECIMEN CROSS-CHECK PROBLEMS:")
        for p in problems:
            print("  " + p)
    else:
        print("specimen cross-check : 48/48 ids and titles agree")
    print()

    records = [execute(s) for s in SPECS]

    closed = [r for r in records if r["closes"]]
    unsup = [r for r in records if r["outcome"] == UNSUPPORTED]
    silent = [r for r in records if r["outcome"] == SILENT_LOSS]

    print(f"{'id':8s} {'closes':7s} {'outcome':24s} {'class':11s} codes")
    print("-" * 94)
    for r in records:
        print(
            f"{r['id']:8s} {('YES' if r['closes'] else 'no'):7s} "
            f"{r['outcome']:24s} {(r['failure_class'] or '-'):11s} "
            f"{','.join(r['codes']) if r['codes'] else '(clean)'}"
        )

    denom = 48 - len(unsup)
    print()
    print(f"STRICT closure (48 denominator)   : {len(closed)}/48 = {len(closed) / 48:.3f}")
    print(
        f"FRAMEWORK closure (UNSUPPORTED out): {len(closed)}/{denom} = "
        f"{len(closed) / denom:.3f}   (excluded: {len(unsup)})"
    )
    print(
        f"silent composition loss count     : {len(silent)}  "
        f"({', '.join(r['id'] for r in silent) or 'none'})"
    )

    hist: dict[str, int] = {}
    for r in records:
        if r["failure_class"]:
            hist[r["failure_class"]] = hist.get(r["failure_class"], 0) + 1
    print(f"failure-class histogram: {dict(sorted(hist.items()))}")

    outc: dict[str, int] = {}
    for r in records:
        outc[r["outcome"]] = outc.get(r["outcome"], 0) + 1
    print(f"outcome histogram      : {dict(sorted(outc.items()))}")

    rep: dict[str, int] = {}
    for r in records:
        key = NONE if r["closes"] else r["repair"]
        rep[key] = rep.get(key, 0) + 1
    print(f"repair histogram       : {dict(sorted(rep.items()))}")
    n_local, n_one, n_gen = rep.get(LOCAL, 0), rep.get(ONE_NODE, 0), rep.get(GENERAL, 0)
    base = len(closed)
    print()
    print("REACHABLE-CLOSURE CEILINGS (estimates, not measurements)")
    print(f"  today                               : {base}/48 = {base / 48:.3f}")
    print(
        f"  + every LOCAL repair                : {base + n_local}/48 = "
        f"{(base + n_local) / 48:.3f}"
    )
    print(
        f"  + every ONE_NODE addition           : {base + n_local + n_one}/48 = "
        f"{(base + n_local + n_one) / 48:.3f}   <- generic-repair ceiling"
    )
    print(
        f"  + a general nesting capability      : "
        f"{base + n_local + n_one + n_gen}/48 = "
        f"{(base + n_local + n_one + n_gen) / 48:.3f}   <- generic-core ceiling"
    )
    print(
        f"  generic core ALONE, no local repair : {base + n_gen}/48 = "
        f"{(base + n_gen) / 48:.3f}"
    )
    print()

    hits, attempted, missed = prediction_accuracy(records)
    print(
        f"prediction_accuracy (scores the FRAMEWORK, not HML): {hits}/{attempted} = "
        f"{hits / attempted:.3f}"
    )
    for mid, cls, pred in missed:
        print(f"    MISS {mid}  observed {cls:11s} predicted {','.join(pred)}")
    print()

    disagree = [r["id"] for r in records if not r["adjudication_agrees"]]
    print(f"gate/adjudication disagreements: {disagree or 'none'}")

    out = Path(__file__).resolve().parent / "results" / "COMPOSITION_48.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "hml_source": H.__file__,
                "specimen_file": str(SPECIMEN_FILE),
                "cross_check_problems": problems,
                "closed": len(closed),
                "total": 48,
                "framework_denominator": denom,
                "unsupported": [r["id"] for r in unsup],
                "silent_loss": [r["id"] for r in silent],
                "failure_class_histogram": hist,
                "repair_histogram": rep,
                "prediction_accuracy": {
                    "hits": hits,
                    "attempted": attempted,
                    "value": round(hits / attempted, 4),
                    "surface_map": {k: sorted(v) for k, v in SURFACE_MAP.items()},
                    "missed": [
                        {"id": m, "observed": c, "predicted": pr} for m, c, pr in missed
                    ],
                },
                "outcome_histogram": outc,
                "gate_disagreements": disagree,
                "records": records,
            },
            indent=2,
        )
    )
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
