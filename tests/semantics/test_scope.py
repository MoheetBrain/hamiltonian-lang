"""Name resolution and scope tests.

The language's claim is that binding errors become impossible rather than unlikely.
These tests are where that claim is either true or false.
"""

from __future__ import annotations

from hamiltonian_lang import compile_source


def codes(src: str) -> list[str]:
    return [d.code for d in compile_source(src).diagnostics.errors]


def ok(src: str):
    r = compile_source(src)
    assert r.ok(), "\n" + r.diagnostics.render()
    return r


# -- resolution ----------------------------------------------------------


def test_every_reference_gets_a_symbol_id():
    from hamiltonian_lang.ast.nodes import Ref, walk

    r = ok("param a : Real\nparam b : Real\ndef c := a + b")
    refs = [n for n in walk(r.module) if isinstance(n, Ref)]
    assert refs, "expected references"
    assert all(x.symbol_id is not None for x in refs)


def test_module_scope_is_order_independent():
    """A declarative model must not depend on statement order for visibility."""
    ok("def c := a + b\nparam a : Real\nparam b : Real")


def test_unbound_symbol_rejected():
    assert "HML-N301" in codes("def c := a + 1")


def test_unbound_symbol_suggests_near_miss():
    r = compile_source("param sigma : PositiveReal\ndef c := sigmaa + 1")
    d = next(x for x in r.diagnostics.errors if x.code == "HML-N301")
    assert "sigma" in (d.correction or "")


def test_duplicate_declaration_rejected():
    assert "HML-N303" in codes("param a : Real\nparam a : Real")


def test_a_binder_may_reuse_a_declared_name():
    """D-045. Reversed deliberately: this used to assert HML-N302.

    A binder binds occurrences in its body -- that is what a binder is. Rejecting it
    made `derivative(f, x)` unwritable whenever `x` was declared, i.e. always.
    """
    assert "HML-N302" not in codes("param x : Real\nrequire forall x : Real . x > 0")


def test_a_binder_may_reuse_a_declared_index_name():
    """D-045. `sum over i` where `i` is a declared index is the normal idiom."""
    assert "HML-N302" not in codes(
        "index i : Natural\nrequire forall i : Natural . i > 0"
    )


def test_nested_quantifiers_do_not_collide_when_distinct():
    ok("require forall x : Real . exists y : Real . y > x")


def test_nested_quantifier_reusing_a_name_is_permitted():
    """D-045. Legal and unambiguous: the inner binder wins, and the two carry distinct
    SymbolIds, so canonical identity and alpha-equivalence are unaffected."""
    assert "HML-N302" not in codes(
        "require forall x : Real . exists x : Real . x > 0"
    )


def test_quantifier_variable_not_visible_outside_its_body():
    assert "HML-N301" in codes(
        "require forall x : Real . x > 0\nrequire x > 1"
    )


def test_unknown_function_rejected():
    assert "HML-N306" in codes("param a : Real\ndef c := wibble(a)")


def test_builtin_functions_resolve():
    ok("param a : PositiveReal\ndef c := log(a) + exp(a)")


# -- laws ----------------------------------------------------------------


def test_law_on_unbound_target_rejected():
    assert "HML-N301" in codes(
        "param m : Real\nparam s : PositiveReal\nlaw z ~ Normal(location := m, scale := s)"
    )


def test_two_laws_for_one_symbol_rejected():
    src = (
        "param m : Real\nparam s : PositiveReal\nvar x : RandomVariable[Real]\n"
        "law x ~ Normal(location := m, scale := s)\n"
        "law x ~ Normal(location := m, scale := s)"
    )
    assert "HML-S601" in codes(src)


def test_symbol_marked_stochastic_after_law():
    r = ok(
        "param theta : Probability\nprior theta ~ Beta(alpha := 1, beta := 1)\n"
        "infer posterior theta"
    )
    sym = next(s for s in r.symbols.module_symbols() if s.name == "theta")
    assert sym.stochastic
    assert sym.law_family == "Beta"


def test_posterior_without_prior_rejected():
    assert "HML-S604" in codes("param theta : Probability\ninfer posterior theta")


# -- concepts ------------------------------------------------------------


def test_concept_without_invariant_or_example_rejected():
    src = "concept Vague\n    parameter a : Real\nend"
    assert "HML-S603" in codes(src)


def test_concept_with_invariant_accepted():
    ok("concept F\n    parameter s : PositiveReal\n    invariant pos := s > 0\nend")


def test_concept_extending_unknown_concept_rejected():
    assert "HML-N305" in codes(
        "concept F extends Missing\n    parameter a : Real\n    invariant i := a > 0\nend"
    )


def test_self_extending_concept_rejected():
    assert "HML-S602" in codes(
        "concept F extends F\n    parameter a : Real\n    invariant i := a > 0\nend"
    )


def test_transform_visible_to_invariant_declared_before_it():
    ok(
        "concept F\n"
        "    invariant affine := standardise(location) = 0\n"
        "    parameter location : Real\n"
        "    parameter scale : PositiveReal\n"
        "    transform standardise(u : Real) := (u - location) / scale\n"
        "end"
    )
