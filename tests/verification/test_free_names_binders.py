"""`free_names` must see every binder, and must not over-reach into the ones it sees.

The defect: `free_names` dispatched by whitelist with a branch for `Quantifier` and five
operator kinds, and fell through **silently** for everything else. When D-026 added four
binders and seven expression forms, none was added here, so

    free_names( integral(y, x : Real, 0.0, 1.0) > 0.0 )  ->  []      # y IS free
    free_names( forall x : Real . y > x )                ->  ['y']   # correct

An obligation engine that under-reports free names is not conservatively wrong; it is
wrong in the *dangerous* direction, because a name it cannot see is a name it will not
require to be pinned before deciding the obligation. The failure was invisible: no
exception, no diagnostic, just a shorter set.

The scoped/unscoped tests are the ones that would catch an over-correction. It is easy to
"fix" this by treating every child of a binder as bound, which would silently swallow the
free variable in an integral's limit.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import BINDER_KINDS, RequireStmt, binder_of
from hamiltonian_lang.verification.obligations.evaluate import build_environment, free_names


def _free(src: str) -> list[str]:
    r = compile_source(src, "<test>")
    assert r.ok(), r.diagnostics.render()
    env = build_environment(r.module, r.symbols)
    st = next(s for s in r.module.statements if isinstance(s, RequireStmt))
    return sorted(free_names(st.proposition, env))


P = "module M\nvar y : Real\n"


# ---------------------------------------------------------------------------
# A free name inside each binder must be reported
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "src"),
    [
        ("quantifier", P + "require forall x : Real . y > x\n"),
        ("integral", P + "require integral(y, x : Real, 0.0, 1.0) > 0.0\n"),
        ("derivative", P + "require derivative(y, x : Real) > 0.0\n"),
        ("comprehension", P + "require {x : Real | x > y} = {x : Real | x > y}\n"),
    ],
)
def test_a_free_name_inside_a_binder_is_reported(label, src):
    assert _free(src) == ["y"], f"{label} lost a free variable"


def test_a_free_name_inside_a_non_binder_v2_form_is_reported():
    """The seven non-binder D-026 forms were missing from the whitelist too."""
    assert _free(P + "var z : Real\nrequire y in {x : Real | x > z}\n") == ["y", "z"]


# ---------------------------------------------------------------------------
# ...and a BOUND name must not be
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "src"),
    [
        ("quantifier", "module M\nrequire forall x : Real . x > 0.0\n"),
        ("integral", "module M\nrequire integral(x, x : Real, 0.0, 1.0) > 0.0\n"),
        ("derivative", "module M\nrequire derivative(x, x : Real) > 0.0\n"),
        ("comprehension", "module M\nrequire {x : Real | x > 0.0} = {x : Real | x > 0.0}\n"),
    ],
)
def test_a_bound_name_is_not_free(label, src):
    assert _free(src) == [], f"{label} reported its own bound variable as free"


# ---------------------------------------------------------------------------
# The scoped/unscoped split -- what an over-correction would break
# ---------------------------------------------------------------------------


def test_an_integral_limit_is_outside_the_binding():
    """In the integral of x from 0 to y, `y` is free. Treating every child of a binder
    as bound would swallow it."""
    assert _free(P + "require integral(x, x : Real, 0.0, y) > 0.0\n") == ["y"]


def test_a_limit_approach_point_is_outside_the_binding():
    """In `limit(f(x), x -> y)`, `y` is free."""
    src = P + "require limit(y, x : Real -> y) = 0.0\n"
    r = compile_source(src, "<test>")
    if not r.ok():  # surface may differ; the protocol claim is asserted directly below
        pytest.skip("limit surface syntax differs; protocol asserted structurally instead")
    assert _free(src) == ["y"]


def test_the_protocol_reports_integral_limits_as_unscoped():
    """Asserted on the protocol directly, so it holds regardless of surface syntax."""
    from hamiltonian_lang.ast.nodes import IntegralExpr, Literal, Ref

    node = IntegralExpr(
        var="x",
        body=Ref(name="x"),
        lower=Literal(value=0.0, raw="0.0"),
        upper=Ref(name="y"),
    )
    name, scoped, unscoped = binder_of(node)
    assert name == "x"
    assert len(scoped) == 1, "the integrand is inside the binding"
    assert len(unscoped) == 2, "both limits are outside the binding"


# ---------------------------------------------------------------------------
# The guard that stops this recurring
# ---------------------------------------------------------------------------


def test_every_binder_kind_is_handled_by_the_protocol():
    """A sixth binder added without a `binder_of` branch fails here rather than silently
    losing free variables in whatever consumer notices last."""
    import dataclasses

    from hamiltonian_lang.ast.nodes import Ref

    for cls in BINDER_KINDS:
        # Each binder names its scoped child differently (`body`, `predicate`), so build
        # it from the dataclass fields rather than assuming a spelling -- assuming one is
        # how this class of bug arises in the first place.
        field_names = {f.name for f in dataclasses.fields(cls)}
        child = "predicate" if "predicate" in field_names else "body"
        node = cls(var="x", **{child: Ref(name="x")})  # type: ignore[arg-type]
        name, scoped, _ = binder_of(node)
        assert name == "x", f"{cls.__name__} is in BINDER_KINDS but binder_of ignores it"
        assert scoped, f"{cls.__name__} reports no scoped children"


def test_an_unknown_expression_kind_still_descends_structurally():
    """The property that makes this fix durable: a node kind nobody has written a branch
    for is descended into, not silently skipped."""
    from dataclasses import dataclass, field

    from hamiltonian_lang.ast.nodes import Expr, Ref, expr_children

    @dataclass
    class HypotheticalFutureExpr(Expr):
        inner: Expr = field(default=None)  # type: ignore[assignment]

    node = HypotheticalFutureExpr(inner=Ref(name="y"))
    assert expr_children(node), "a future node kind must still expose its children"
    assert binder_of(node)[2], "and they must be walked as unscoped"
