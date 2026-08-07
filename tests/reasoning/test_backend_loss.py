"""No backend may drop a V2 reasoning construct without saying so.

This is the discipline `backends/base.py` calls the worst failure mode to breach:
authoritative-looking output that quietly lost the thing it was asked to carry. When
V2 landed, four backends breached it -- they had no branch for the new statement kinds
and fell through silently, reporting `faithful` on a module whose entire argument they
had discarded. These tests exist so that cannot recur, for these constructs or the next.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source

_V2_SOURCE = """module M
var x : Real
var y : Real
assume a1 : y = 2.0 * x
derive d1 : y + 1.0 = 2.0 * x + 1.0 from a1 by add_both_sides(by := 1.0)
goal g1 : y + 1.0 = 2.0 * x + 1.0
proved g1 by d1
"""

#: Backends that can carry the reasoning spine exactly and must NOT report a loss.
_LOSSLESS = ("hml", "english")
#: Backends with no derivation form. Each must declare the loss for all three nodes.
_LOWERING = ("latex", "lean", "sympy", "stan")

ALL_TARGETS = _LOSSLESS + _LOWERING


@pytest.fixture(scope="module")
def compiled():
    r = compile_source(_V2_SOURCE, "<test>")
    assert r.ok(), r.diagnostics.render()
    return r


@pytest.mark.parametrize("target", ALL_TARGETS)
def test_no_backend_emits_an_unrenderable_marker(compiled, target):
    """A placeholder in the output is a loss the report did not mention."""
    text = compiled.render(target).text or ""
    assert "unrenderable" not in text, f"{target} emitted a placeholder for a V2 node"


@pytest.mark.parametrize("target", _LOWERING)
def test_a_lowering_backend_declares_every_dropped_reasoning_node(compiled, target):
    out = compiled.render(target)
    dropped = {u.construct.split()[0] for u in out.unsupported}
    for kind in ("derive", "goal", "proved"):
        assert kind in dropped, (
            f"{target} dropped the {kind} statement without reporting it; "
            f"reported: {sorted(dropped)}"
        )
    assert not out.faithful


@pytest.mark.parametrize("target", _LOSSLESS)
def test_a_faithful_backend_really_is_faithful(compiled, target):
    """`faithful=True` has to mean the construct survived, not that nobody looked."""
    out = compiled.render(target)
    assert out.faithful
    for label in ("d1", "g1", "a1"):
        assert label in out.text, f"{target} claims faithful but lost {label}"


def test_the_hml_backend_round_trips_a_derivation_to_the_same_hash():
    """The strongest available statement of losslessness."""
    first = compile_source(_V2_SOURCE, "<test>")
    rendered = first.render("hml").text
    second = compile_source(rendered, "<test>")
    assert second.ok(), second.diagnostics.render()
    assert first.hash() == second.hash()


def test_a_v1_module_gains_no_reasoning_losses():
    """The reporting helper must fire only on modules that actually use V2."""
    v1 = compile_source(
        "module M\nvar x : Real\nassume x > 0.0\n", "<test>"
    )
    for target in ALL_TARGETS:
        out = v1.render(target)
        v2_losses = [
            u
            for u in out.unsupported
            if u.construct.split()[0] in ("derive", "goal", "proved")
        ]
        assert not v2_losses, f"{target} invented a V2 loss on a v1 module"
