"""Round-trip, canonicalisation and alpha-equivalence.

v0 success criterion 6: "equivalent variable renamings produce equivalent canonical
representations". These tests are that criterion.
"""

from __future__ import annotations

import json

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


@settings(max_examples=60, deadline=None)
@given(a=_IDENT, b=_IDENT, c=_IDENT, d=_IDENT)
def test_alpha_renaming_invariance_property(a, b, c, d):
    """Any consistent bijective renaming leaves the canonical hash unchanged."""
    if len({a, b}) != 2 or len({c, d}) != 2:
        return
    src1 = f"param {a} : Real\nparam {b} : PositiveReal\ndef z := {a} + {b}"
    src2 = f"param {c} : Real\nparam {d} : PositiveReal\ndef z := {c} + {d}"
    r1, r2 = compile_source(src1), compile_source(src2)
    if not (r1.ok() and r2.ok()):
        return
    assert content_hash(r1.module) == content_hash(r2.module)


@settings(max_examples=40, deadline=None)
@given(name=_IDENT)
def test_inconsistent_renaming_is_caught(name):
    """Renaming a binder but not its use must not silently produce a valid program."""
    src = f"param {name} : Real\ndef z := {name}_other"
    r = compile_source(src)
    assert not r.ok()
    assert "HML-N301" in [d.code for d in r.diagnostics.errors]
