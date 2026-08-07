"""Scoped Γ: `scope … end`, and what must never cross a frame boundary (D-035, D-043).

Before this, Γ was flat: `assume x > 0.0` licensed `log(x)` for the whole module and
there was no way to say "assume this *for the purposes of this argument*". `push`/`pop`
existed on `RefinementEnv` and **nothing called them** — the third instance in this
project of a mechanism built and left unwired.

The leak tests are the point. A scoping construct that only ever *adds* facts is not
scoping; the value is entirely in what it refuses.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.reasoning.refinement import Consistency, RefinementEnv

P = "module M\nvar x : Real\nvar y : Real\n"


def _ok(body: str) -> bool:
    return compile_source(P + body, "<test>").ok()


def _codes(body: str) -> list[str]:
    r = compile_source(P + body, "<test>")
    return [d.code for d in r.diagnostics.items]


# ---------------------------------------------------------------------------
# The fact is available inside, and only inside
# ---------------------------------------------------------------------------


def test_an_assumption_holds_inside_its_scope():
    assert _ok("scope\n    assume x > 0.0\n    require log(x) = log(x)\nend\n")


def test_an_assumption_does_not_survive_its_scope():
    """The single most important test in this file."""
    assert not _ok(
        "scope\n    assume x > 0.0\nend\nrequire log(x) = log(x)\n"
    )


def test_an_assumption_is_not_visible_before_its_scope():
    assert not _ok(
        "require log(x) = log(x)\nscope\n    assume x > 0.0\nend\n"
    )


def test_sibling_scopes_do_not_share_facts():
    assert not _ok(
        "scope\n    assume x > 0.0\nend\n"
        "scope\n    require log(x) = log(x)\nend\n"
    )


def test_an_outer_fact_is_visible_inside_an_inner_scope():
    """Frames nest: lookup goes innermost outward, so the outer fact is still in scope."""
    assert _ok("assume x > 0.0\nscope\n    require log(x) = log(x)\nend\n")


def test_nested_scopes_expire_innermost_first():
    assert not _ok(
        "scope\n"
        "    scope\n"
        "        assume x > 0.0\n"
        "    end\n"
        "    require log(x) = log(x)\n"
        "end\n"
    )


def test_a_scope_is_internally_order_independent():
    """D-008 consistency: within a frame, an assumption below a use still constrains it."""
    assert _ok("scope\n    require log(x) = log(x)\n    assume x > 0.0\nend\n")


# ---------------------------------------------------------------------------
# The refusals the directive names, now inside a scope
# ---------------------------------------------------------------------------


def test_non_strict_does_not_establish_strict_inside_a_scope():
    assert not _ok("scope\n    assume x >= 0.0\n    require log(x) = log(x)\nend\n")


def test_an_unrelated_symbol_does_not_discharge_inside_a_scope():
    assert not _ok("scope\n    assume y > 0.0\n    require log(x) = log(x)\nend\n")


def test_require_is_still_not_a_fact_inside_a_scope():
    assert not _ok("scope\n    require x > 0.0\n    require log(x) = log(x)\nend\n")


# ---------------------------------------------------------------------------
# Contradiction: contained, not banned
# ---------------------------------------------------------------------------


def test_a_contradictory_scope_is_reported_but_not_an_error():
    """Assuming something false and deriving a contradiction is how proof by
    contradiction works. Globally banning it would make that pattern inexpressible."""
    r = compile_source(P + "scope\n    assume x > 0.0\n    assume x < 0.0\nend\n", "<t>")
    assert r.ok(), "a locally inconsistent scope must not be a hard error"
    assert "HML-T496" in [d.code for d in r.diagnostics.items]


def test_a_contradiction_does_not_escape_its_scope():
    """The containment that matters: anything follows from a contradiction, so nothing
    inside may license anything outside."""
    assert not _ok(
        "scope\n    assume x > 0.0\n    assume x < 0.0\nend\n"
        "require log(x) = log(x)\n"
    )


def test_equality_and_disequality_are_contradictory():
    r = compile_source(P + "scope\n    assume x = 0.0\n    assume x != 0.0\nend\n", "<t>")
    assert "HML-T496" in [d.code for d in r.diagnostics.items]


def test_a_consistent_scope_is_not_flagged():
    r = compile_source(P + "scope\n    assume x > 0.0\n    assume y > 0.0\nend\n", "<t>")
    assert "HML-T496" not in [d.code for d in r.diagnostics.items]


# ---------------------------------------------------------------------------
# The frame stack itself
# ---------------------------------------------------------------------------


def test_the_module_frame_cannot_be_popped():
    env = RefinementEnv()
    with pytest.raises(RuntimeError):
        env.pop()


def test_pop_returns_the_frame_so_a_discharge_rule_can_inspect_it():
    """An assumption-discharge rule needs to know the frame was inconsistent in order to
    conclude `not P` from a contradiction derived under `P`."""
    env = RefinementEnv()
    env.push("scope")
    frame = env.pop()
    assert frame.kind == "scope"
    assert frame.consistency is Consistency.CONSISTENT


def test_frames_nest_and_report_depth():
    env = RefinementEnv()
    assert env.depth == 0
    env.push("scope")
    assert env.depth == 1
    env.push("quantifier")
    assert env.depth == 2
    env.pop()
    env.pop()
    assert env.depth == 0


# ---------------------------------------------------------------------------
# Round-trip and identity
# ---------------------------------------------------------------------------


def test_a_scope_round_trips_through_the_hml_backend():
    src = P + "scope\n    assume x > 0.0\n    require log(x) = log(x)\nend\n"
    first = compile_source(src, "<test>")
    assert first.ok(), first.diagnostics.render()
    rendered = first.render("hml")
    assert rendered.faithful, "the round-trip backend must not lose a scope"
    second = compile_source(rendered.text, "<test>")
    assert second.ok(), second.diagnostics.render()
    assert first.hash() == second.hash()


def test_consistency_is_not_part_of_semantic_identity():
    """A verdict is evidence, not source (D-034 E1). Two modules stating the same scoped
    argument are the same module regardless of whether one is contradictory."""
    doc = compile_source(
        P + "scope\n    assume x > 0.0\n    assume x < 0.0\nend\n", "<t>"
    ).canonical()
    assert "INCONSISTENT" not in doc
    assert "consistency" not in doc


def test_an_unterminated_scope_is_a_parse_error():
    r = compile_source(P + "scope\n    assume x > 0.0\n", "<test>")
    assert not r.ok()
    assert "HML-P255" in [d.code for d in r.diagnostics.items]
