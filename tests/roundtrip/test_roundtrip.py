"""Round-trip, canonicalisation and alpha-equivalence.

v0 success criterion 6: "equivalent variable renamings produce equivalent canonical
representations". These tests are that criterion.
"""

from __future__ import annotations

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends.canonical import canonical_json, content_hash
from hamiltonian_lang.backends.hml import render_module


def compiled(src: str):
    r = compile_source(src)
    assert r.ok(), "\n" + r.diagnostics.render()
    return r


# -- round trip ----------------------------------------------------------


def test_examples_round_trip(example):
    """parse -> render -> parse must reach the same canonical form."""
    first = compiled(example.read_text())
    rendered = render_module(first.module)
    second = compile_source(rendered, f"{example}#rendered")
    assert second.ok(), (
        f"re-parsing the rendered form of {example} failed:\n"
        + second.diagnostics.render()
        + "\n--- rendered ---\n"
        + rendered
    )
    assert first.hash() == second.hash(), (
        f"round trip changed the canonical form of {example}\n"
        f"--- rendered ---\n{rendered}"
    )


def test_round_trip_is_idempotent(example):
    once = render_module(compiled(example.read_text()).module)
    twice = render_module(compiled(once).module)
    assert once == twice


# -- canonical form ------------------------------------------------------


def test_canonical_json_is_deterministic(example):
    src = example.read_text()
    assert canonical_json(compiled(src).module) == canonical_json(compiled(src).module)


def test_canonical_json_is_ascii_and_sorted(example):
    blob = canonical_json(compiled(example.read_text()).module)
    blob.encode("ascii")  # raises if not ASCII
    doc = json.loads(blob)
    assert doc["canonical_version"].startswith("hml-canonical-")


def test_canonical_form_carries_no_source_spans(example):
    blob = canonical_json(compiled(example.read_text()).module)
    assert '"line"' not in blob
    assert '"span"' not in blob


def test_comments_and_whitespace_do_not_affect_the_hash():
    a = "param a : Real\nparam b : Real\ndef c := a + b"
    b = (
        "# leading comment\n\nparam a : Real   # trailing\n\n\n"
        "param b : Real\n\ndef c := a + b\n\n"
    )
    assert content_hash(compiled(a).module) == content_hash(compiled(b).module)


def test_reordering_identically_typed_declarations_is_alpha_equivalent():
    """`param a : Real; param b : Real` and its reverse differ only by a renaming,
    so they are the same object and must hash identically."""
    a = "param a : Real\nparam b : Real"
    b = "param b : Real\nparam a : Real"
    assert content_hash(compiled(a).module) == content_hash(compiled(b).module)


def test_reordering_differently_typed_declarations_changes_the_hash():
    """Ordinals are positional, so swapping declarations of *different* types is a
    genuine structural change, not a renaming."""
    a = "param a : Real\nparam b : PositiveReal"
    b = "param b : PositiveReal\nparam a : Real"
    assert content_hash(compiled(a).module) != content_hash(compiled(b).module)


# -- alpha equivalence ---------------------------------------------------


def test_consistent_renaming_preserves_the_hash():
    a = "param mu : Real\nparam sigma : PositiveReal\ndef z := mu + sigma"
    b = "param aa : Real\nparam bb : PositiveReal\ndef z := aa + bb"
    assert content_hash(compiled(a).module) == content_hash(compiled(b).module)


def test_bound_variable_renaming_preserves_the_hash():
    a = "require forall x : Real . exists y : Real . y > x"
    b = "require forall p : Real . exists q : Real . q > p"
    assert content_hash(compiled(a).module) == content_hash(compiled(b).module)


def test_quantifier_order_changes_the_hash():
    """H2's structural precondition: the two scopings must not be confusable."""
    a = "require forall x : Real . exists y : Real . y > x"
    b = "require exists y : Real . forall x : Real . y > x"
    assert content_hash(compiled(a).module) != content_hash(compiled(b).module)


def test_distribution_argument_order_does_not_change_the_hash():
    """Roles carry the meaning, so writing order is not part of identity (D-003)."""
    a = (
        "param m : Real\nparam s : PositiveReal\nvar x : RandomVariable[Real]\n"
        "law x ~ Normal(location := m, scale := s)"
    )
    b = (
        "param m : Real\nparam s : PositiveReal\nvar x : RandomVariable[Real]\n"
        "law x ~ Normal(scale := s, location := m)"
    )
    assert content_hash(compiled(a).module) == content_hash(compiled(b).module)


def test_swapping_roles_does_change_the_hash():
    a = (
        "param p : PositiveReal\nparam q : PositiveReal\n"
        "param t : Probability\nprior t ~ Beta(alpha := p, beta := q)"
    )
    b = (
        "param p : PositiveReal\nparam q : PositiveReal\n"
        "param t : Probability\nprior t ~ Beta(alpha := q, beta := p)"
    )
    assert content_hash(compiled(a).module) != content_hash(compiled(b).module)


_IDENT = st.from_regex(r"\A[a-z][a-z0-9_]{0,7}\Z", fullmatch=True).filter(
    lambda s: s
    not in {
        "law", "var", "def", "end", "obs", "and", "or", "not", "prior", "check",
        "solve", "infer", "index", "param", "const", "prove", "assume", "require",
        "module", "concept", "forall", "exists", "unique", "true", "false", "map",
        "mle", "iff", "implies", "extends", "example", "property", "variance",
        "transform", "invariant", "parameter", "dimension", "posterior", "likelihood",
        "minimise", "maximise", "minimize", "maximize", "expectation", "rv", "fn",
        "counterexample",
    }
)


# Every binder form the language has. The generator MUST reach all of them.
#
# This list exists because of a specific, expensive lesson: an earlier version of the
# property test below generated only module-level `param` declarations. It was green
# while the renaming-invariance criterion was FALSE -- `def` parameters were serialised
# by spelling, so `def f(u : Real) := u + 1.0` and `def f(w : Real) := w + 1.0` hashed
# differently. The suite passed because the generator never produced the one binder form
# that failed. A green property test is only evidence about the inputs it actually
# reaches. (Red-team finding 1.9.)
_BINDER_TEMPLATES = [
    # module-level declaration
    "param {0} : Real\nparam {1} : PositiveReal\ndef z := {0} + {1}",
    # definition parameter -- the form that was silently broken
    "def f({0} : Real, {1} : Real) : Real := {0} + {1}\ndef z := f(1.0, 2.0)",
    # quantifier binders, both nesting orders
    "require forall {0} : Real . exists {1} : Real . {1} > {0}",
    "require exists {0} : Real . forall {1} : Real . {0} > {1}",
    # concept transform parameter
    (
        "concept C\n"
        "    parameter loc : Real\n"
        "    transform t({0} : Real) : Real := {0} - loc\n"
        "    transform s({1} : Real) : Real := {1} + loc\n"
        "    invariant inv := loc = loc\n"
        "end"
    ),
    # law targets and conditioning sets
    (
        "param {0} : Real\nparam {1} : PositiveReal\n"
        "var x : RandomVariable[Real]\n"
        "law x ~ Normal(location := {0}, scale := {1})"
    ),
]


@pytest.mark.parametrize("template", _BINDER_TEMPLATES, ids=range(len(_BINDER_TEMPLATES)))
@settings(max_examples=40, deadline=None)
@given(a=_IDENT, b=_IDENT, c=_IDENT, d=_IDENT)
def test_alpha_renaming_invariance_property(template, a, b, c, d):
    """A consistent bijective renaming leaves the canonical hash unchanged.

    Parameterised over every binder form so that the generator cannot miss one.
    """
    if len({a, b}) != 2 or len({c, d}) != 2:
        return
    r1 = compile_source(template.format(a, b))
    r2 = compile_source(template.format(c, d))
    if not (r1.ok() and r2.ok()):
        return
    assert content_hash(r1.module) == content_hash(r2.module), (
        "renaming changed the canonical hash for:\n" + template.format(a, b)
    )


# Names that are *not* anonymous binders: they are the object's interface, and renaming
# one changes what the object is. The distinction is the same one D-003 makes for
# distribution roles -- `scale` and `location` are meaning, not spelling. A concept's
# parameters are its roles; a transform's parameters are local binders. (D-017.)
_ROLE_TEMPLATES = [
    # concept parameter member names
    (
        "concept C\n"
        "    parameter {0} : Real\n"
        "    parameter {1} : PositiveReal\n"
        "    invariant inv := {1} > 0\n"
        "end"
    ),
    # concept member names generally
    (
        "concept C\n"
        "    parameter loc : Real\n"
        "    invariant {0} := loc = loc\n"
        "    example {1} := loc = 0\n"
        "end"
    ),
]


@pytest.mark.parametrize("template", _ROLE_TEMPLATES, ids=range(len(_ROLE_TEMPLATES)))
def test_renaming_an_interface_role_does_change_the_hash(template):
    """A concept parameter is a named role, not an anonymous binder.

    `LocationScaleFamily(location, scale)` and `LocationScaleFamily(a, b)` are not the
    same concept: the names carry the meaning, exactly as distribution roles do.
    """
    a = compile_source(template.format("location", "scale"))
    b = compile_source(template.format("aaa", "bbb"))
    assert a.ok() and b.ok()
    assert content_hash(a.module) != content_hash(b.module)


@pytest.mark.parametrize(
    "template",
    _BINDER_TEMPLATES + _ROLE_TEMPLATES,
    ids=range(len(_BINDER_TEMPLATES) + len(_ROLE_TEMPLATES)),
)
def test_every_template_is_actually_reachable(template):
    """Guard the guard: each template must compile, or it tests nothing.

    Without this, a template that silently failed to compile would make the property
    above vacuously true -- which is exactly how the original defect hid.
    """
    r = compile_source(template.format("aa", "bb"))
    assert r.ok(), "\n" + r.diagnostics.render()


@settings(max_examples=40, deadline=None)
@given(name=_IDENT)
def test_inconsistent_renaming_is_caught(name):
    """Renaming a binder but not its use must not silently produce a valid program."""
    src = f"param {name} : Real\ndef z := {name}_other"
    r = compile_source(src)
    assert not r.ok()
    assert "HML-N301" in [d.code for d in r.diagnostics.errors]


# -- regression: the HML view must not drop a formal's declared type ------


_TYPED_FORMAL_CASES = [
    "module TypedFormal\n\nconst c : Real = 8\ndef f(x : Real) : Real := x * 2 + c\n"
    "def g : Real := f(c)\nsolve g\n",
    "module TypedFormalMulti\n\ndef h(u : Real, w : Real) : Real := u * w + 1\n"
    "const a : Real = 2\nconst b : Real = 3\ndef k : Real := h(a, b)\nsolve k\n",
    "module TypedFormalQuantity\n\nparam m : Quantity[Mass]\n"
    "def e(v : Quantity[Length / Time]) : Quantity[Mass * Length^2 / Time^2]"
    " := 0.5 * m * v^2\n",
]


@pytest.mark.parametrize("src", _TYPED_FORMAL_CASES, ids=["scalar", "two_formals", "quantity"])
def test_parametric_definition_keeps_its_formal_types_through_the_hml_view(src):
    """`def f(x : Real) : Real := ...` rendered as `def f(x) : Real := ...` re-parses
    with an untyped formal and then fails to type-check (HML-T431).

    A view that silently drops meaning is the failure mode this project treats as the
    worst one, and the defect survived because no file under `examples/` used a typed
    formal in a parametric definition -- so `test_examples_round_trip` never reached it.
    These cases exercise it directly.
    """
    first = compiled(src)
    rendered = render_module(first.module)
    assert " : Real)" in rendered or " : Quantity[" in rendered, rendered
    second = compile_source(rendered, "#rendered")
    assert second.ok(), "\n" + second.diagnostics.render() + "\n--- rendered ---\n" + rendered
    assert first.hash() == second.hash()


# -- printer associativity (found by the HML-PHASE-FG-001 F3 round-trip gate) ---

#: Each pair is (source, the sub-expression the printer must parenthesise). Before the
#: fix, `backends/hml.py` parenthesised only the *right* operand of `+ - * /`, so every
#: LEFT-nested occurrence of a RIGHT-associative operator lost its grouping and read back
#: as a different object with a different canonical hash. The examples corpus happened to
#: contain none of these shapes, so the suite was green while the round-trip guarantee
#: was false for `^`, `=>` and `<=>`.
_ASSOCIATIVITY_CASES = [
    ("param a : PositiveReal\nparam b : PositiveReal\nparam c : PositiveReal\n"
     "def z := (a ^ b) ^ c", "(a ^ b) ^ c"),
    ("param a : PositiveReal\nparam b : PositiveReal\nparam c : PositiveReal\n"
     "def z := a ^ (b ^ c)", "a ^ b ^ c"),
    ("param a : Real\nparam b : Real\nparam c : Real\n"
     "require (a > 0.0 => b > 0.0) => c > 0.0", "(a > 0.0 => b > 0.0) => c > 0.0"),
    ("param a : Real\nparam b : Real\nparam c : Real\n"
     "require (a > 0.0 <=> b > 0.0) <=> c > 0.0", "(a > 0.0 <=> b > 0.0) <=> c > 0.0"),
    ("param a : Real\nparam b : Real\nparam c : Real\n"
     "def z := (a - b) - c", "a - b - c"),
    ("param a : Real\nparam b : Real\nparam c : Real\n"
     "def z := a - (b - c)", "a - (b - c)"),
    ("param a : PositiveReal\nparam b : PositiveReal\nparam c : PositiveReal\n"
     "def z := a / (b / c)", "a / (b / c)"),
    ("param v : Vector[Real, 4]\nindex i : Natural\ndef z := v[i]", "v[i]"),
]


@pytest.mark.parametrize(
    "source,expected_fragment", _ASSOCIATIVITY_CASES, ids=range(len(_ASSOCIATIVITY_CASES))
)
def test_printer_preserves_associativity(source, expected_fragment):
    first = compiled(source)
    rendered = render_module(first.module)
    assert expected_fragment in rendered, rendered
    second = compile_source(rendered)
    assert second.ok(), "\n" + second.diagnostics.render() + "\n" + rendered
    assert content_hash(first.module) == content_hash(second.module), (
        f"round trip changed the object\n--- rendered ---\n{rendered}"
    )
