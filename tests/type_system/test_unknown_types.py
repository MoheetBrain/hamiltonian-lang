"""Unknown and truncated type names — HML-COMPILER-CORE-003 Phase 3.

The measured hole (`docs/evaluation/COMPILER_CORE_AUDIT.md` §3): an unknown capitalised
name parses as a *concept reference*, so a hallucinated or truncated type passed the
checker in silence. `param sigma : Positiv` — a truncation of `PositiveReal` — was
accepted, which is exactly the failure mode of generated code and corrupts encoding
fidelity with no diagnostic to trigger a repair.

The correction text matters as much as the rejection: one-repair success is a gate metric,
and a diagnostic that cannot be acted on does not help a repair loop.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source


def _t440(src: str):
    r = compile_source(src)
    return next((d for d in r.diagnostics.errors if d.code == "HML-T440"), None)


@pytest.mark.parametrize(
    "src,where",
    [
        ("param x : Frobnicator", "declaration"),
        ("index N : Natural\nparam v : Vector[Frobnicator, N]", "vector element"),
        ("param d : Distribution[Frobnicator]", "distribution support"),
        ("param r : RandomVariable[Frobnicator]", "random-variable codomain"),
        ("param s : Set[Frobnicator]", "set element"),
        ("require forall x : Frobnicator . x > 0", "quantifier binder"),
        ("def f(u : Frobnicator) : Real := 1.0", "definition parameter"),
        ("def g : Frobnicator := 1.0", "definition result"),
    ],
)
def test_unknown_type_is_rejected_everywhere_a_type_can_appear(src, where):
    d = _t440(src)
    assert d is not None, f"unknown type accepted in {where}"


@pytest.mark.parametrize(
    "typo,expected",
    [
        ("Positiv", "PositiveReal"),
        ("Realz", "Real"),
        ("Naturl", "Natural"),
        ("Probabilty", "Probability"),
        ("Integar", "Integer"),
    ],
)
def test_the_correction_names_the_intended_type(typo, expected):
    """A repair loop needs a candidate, not an observation."""
    d = _t440(f"param x : {typo}")
    assert d is not None
    assert expected in (d.correction or ""), f"{typo}: got {d.correction!r}"


def test_a_declared_concept_is_a_valid_type():
    r = compile_source(
        "concept F\n    parameter a : Real\n    invariant i := a > 0\nend\nparam z : F"
    )
    assert r.ok(), r.diagnostics.render()


def test_every_builtin_type_still_passes():
    from hamiltonian_lang.types import SCALARS

    for name in SCALARS:
        r = compile_source(f"param x : {name}")
        assert r.ok(), f"{name} rejected: {r.diagnostics.render()}"
    for src in (
        "index N : Natural\nparam v : Vector[Real, N]",
        "index N : Natural\nindex P : Natural\nparam m : Matrix[Real, N, P]",
        "param q : Quantity[Mass * Length^2 / Time^2]",
        "param d : Distribution[Real]",
        "param r : RandomVariable[Real]",
        "param f : Function[Real -> Real]",
        "param s : Set[Real]",
    ):
        assert compile_source(src).ok(), f"rejected: {src}"


def test_an_unknown_type_does_not_suppress_other_diagnostics():
    """One bad type must not mask a second, or a repair loop fixes one thing per round."""
    r = compile_source("param x : Frobnicator\nparam y : Wibble")
    codes = [d.code for d in r.diagnostics.errors]
    assert codes.count("HML-T440") == 2
