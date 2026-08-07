"""Backend behaviour for the eleven V2 expression forms (D-026).

One property dominates this file and it is the one ``backends/base.py`` calls the worst
failure mode in the codebase:

    a backend that emits a placeholder while reporting ``faithful=True``

D-025 had to fix two instances of exactly that when the reasoning spine landed --
``backends/hml.py`` emitted ``# <unrenderable DeriveStmt>`` and four targets dropped the
V2 statements in silence. Both were introduced by adding node types without adding the
branches that consume them, which is precisely what this change does eleven more times.

The tests below therefore check the CONJUNCTION, not the parts: it is fine to drop, and
fine to render, and never fine to do neither while claiming the former.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends import available, render

#: Every V2 expression form, in one module. Each backend sees all eleven at once,
#: which is how a missing branch shows up as a placeholder rather than as an absence.
EVERY_FORM = """module Coverage

rv X : RandomVariable[Real]
rv Y : RandomVariable[Real]
rv Z : RandomVariable[Real]

param a : Real
param A : Set[Real]
param f : Function[Real -> Real]

def moment := expectation(X | Y)
def spread := variance(X)
def law_of_pair := joint(X, Y)
def chance := probability(X > 0.0 | Y > 0.0)
def positives := {u : Real | u > 0.0}
def decay := limit(1.0 / u, u : PositiveReal -> 1.0)
def slope := derivative(u ^ 2.0, u : Real)
def area := integral(u ^ 2.0, u : Real, 0.0, 1.0)

require independent(X, Y | Z)
require correlated(X, Y)
require causes(X, Y)
require associated(X, Y)
require a in A
require continuous(f, on := positives)
"""

#: Text a backend must never emit while calling itself faithful. Each is a real
#: placeholder that some backend in this tree produces on its fallthrough path.
PLACEHOLDERS = (
    "unrenderable",
    "unrepresented",
    r"\text{?}",
    "an unrepresented expression",
)


@pytest.fixture(scope="module")
def compiled():
    r = compile_source(EVERY_FORM, "<v2-coverage>")
    assert r.ok(), "\n" + r.diagnostics.render()
    return r


def _node_placeholders(text: str) -> list[str]:
    """Angle-bracketed class names, the shape ``render_expr`` falls through to."""
    from hamiltonian_lang.ast.nodes import Expr

    names = {c.__name__ for c in _subclasses(Expr)}
    return [n for n in names if f"<{n}>" in text]


def _subclasses(cls):
    out = []
    stack = [cls]
    while stack:
        cur = stack.pop()
        for sub in cur.__subclasses__():
            out.append(sub)
            stack.append(sub)
    return out


@pytest.mark.parametrize("target", sorted(available()))
def test_a_backend_never_reports_faithful_while_emitting_a_placeholder(target, compiled):
    """The one non-negotiable. Silence about a loss is worse than the loss."""
    result = render(target, compiled.module, compiled.symbols)
    found = [p for p in PLACEHOLDERS if p in result.text]
    found += _node_placeholders(result.text)
    if result.faithful:
        assert not found, (
            f"{target} reported faithful=True while emitting {found}. This is the "
            f"failure mode backends/base.py names as the worst in the codebase: output "
            f"that looks authoritative and is not."
        )


@pytest.mark.parametrize("target", sorted(available()))
def test_a_backend_never_emits_an_unrendered_node_name(target, compiled):
    """Even declared, `<MomentExpr>` is wrong output: for `hml` it re-parses as a
    comparison against undeclared names, and for every other target it is noise."""
    result = render(target, compiled.module, compiled.symbols)
    assert not _node_placeholders(result.text), (
        f"{target} emitted a raw AST class name; add a branch for it"
    )


@pytest.mark.parametrize("target", sorted(available()))
def test_every_backend_produces_output(target, compiled):
    assert render(target, compiled.module, compiled.symbols).text.strip()


@pytest.mark.parametrize("target", ["lean", "stan", "sympy"])
def test_the_lossy_targets_declare_a_reason_for_every_drop(target, compiled):
    result = render(target, compiled.module, compiled.symbols)
    assert not result.faithful, f"{target} cannot express these forms and must say so"
    assert result.unsupported
    for u in result.unsupported:
        assert u.reason and len(u.reason) > 20, (
            f"{target} recorded a loss with no usable reason: {u.render()}"
        )
        assert u.severity in ("dropped", "approximated", "weakened")


def test_hml_round_trips_every_form(compiled):
    """The round-trip backend has no licence to drop: its output IS the source."""
    from hamiltonian_lang.backends.canonical import content_hash
    from hamiltonian_lang.backends.hml import render_module

    result = render("hml", compiled.module, compiled.symbols)
    assert result.faithful
    again = compile_source(render_module(compiled.module))
    assert again.ok(), "\n" + again.diagnostics.render()
    assert content_hash(compiled.module) == content_hash(again.module)


def test_english_names_every_construct_explicitly(compiled):
    """The controlled-English view is what a reader audits the encoding against, so a
    construct that vanishes from it vanishes from the review."""
    text = render("english", compiled.module, compiled.symbols).text.lower()
    for phrase in (
        "expectation",
        "variance",
        "joint probability law",
        "the probability that",
        "independent",
        "correlated",
        "causes",
        "associated",
        "is a member of",
        "the set of every",
        "the limit of",
        "the derivative of",
        "definite integral",
        "continuous on",
    ):
        assert phrase in text, f"controlled English lost {phrase!r}"


def test_english_keeps_the_three_causal_relations_distinct(compiled):
    """Rendering all three as "is related to" would erase, in the view a human reads,
    the distinction the type system was extended to make."""
    text = render("english", compiled.module, compiled.symbols).text.lower()
    assert "is correlated with" in text
    assert "causes" in text
    assert "is statistically associated with" in text


def test_latex_declares_the_binder_domain_it_cannot_carry(compiled):
    r"""``\lim_{x \to 0}`` is written identically whether x ranges over the reals or the
    positives, and those are different limits."""
    result = render("latex", compiled.module, compiled.symbols)
    assert not result.faithful
    weakened = [u for u in result.unsupported if "binder domain" in u.construct]
    assert len(weakened) == 3, "one per limit, derivative and integral"
    assert all(u.severity == "weakened" for u in weakened)


def test_latex_uses_standard_notation_where_one_exists(compiled):
    text = render("latex", compiled.module, compiled.symbols).text
    for fragment in (r"\mathbb{E}", r"\operatorname{Var}", r"\Pr", r"\perp",
                     r"\in", r"\lim_", r"\int_", r"\operatorname{causes}"):
        assert fragment in text, f"latex lost {fragment}"


def test_lean_renders_the_two_forms_it_can_express_exactly(compiled):
    """Mathlib's `Set` IS HML's `Set[T]`, so membership and comprehension are exact.
    Everything else is dropped with a reason -- this backend invents nothing."""
    text = render("lean", compiled.module, compiled.symbols).text
    assert "∈" in text
    assert "Set ℝ" in text


def test_stan_drops_all_eleven_rather_than_commenting_them_away(compiled):
    """A comment in a `.stan` file is text a sampler ignores. Recording the drop is
    what makes the omission visible to a caller."""
    result = render("stan", compiled.module, compiled.symbols)
    assert not result.faithful
    dropped = {u.construct for u in result.unsupported}
    assert any("moment" in c for c in dropped)
    assert any("integral" in c for c in dropped)
    assert any("causes" in c for c in dropped)


def test_sympy_states_why_it_drops_the_forms_it_actually_has(compiled):
    """SympPy HAS Integral, Derivative and Limit. The reason for dropping them is
    specific -- a bound variable would need a Symbol this backend cannot declare --
    and the recorded reason must say so rather than claiming SymPy cannot."""
    result = render("sympy", compiled.module, compiled.symbols)
    reasons = " ".join(u.reason for u in result.unsupported)
    assert "Symbol" in reasons
    assert "assumptions" in reasons


def test_the_semantic_graph_records_dependencies_under_every_form(compiled):
    """`graph._children` drives the dependency edges. A form missing from it does not
    raise -- the constraint simply appears with no dependency at all."""
    import json

    from hamiltonian_lang.backends import render as render_backend

    doc = json.loads(render_backend("graph", compiled.module, compiled.symbols).text)
    constrained = {
        e["target"] for e in doc["edges"] if e["kind"] in ("constrains", "depends_on")
    }
    symbols = {s.id.canonical() for s in compiled.symbols.module_symbols()}
    # `require a in A` and `require causes(X, Y)` must each reach their operands.
    assert symbols & constrained, "no constraint reached any declared symbol"
    for name in ("X", "Y", "A", "a"):
        sym = next(
            s for s in compiled.symbols.module_symbols() if s.name == name
        )
        assert sym.id.canonical() in constrained, (
            f"{name} appears inside a V2 expression but the graph records no edge to it"
        )
