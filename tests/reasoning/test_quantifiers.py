"""Universal introduction and elimination.

Deliberately arithmetic-free. The Gold-10 case that motivated this rule is
``forall n : Natural . n + 0 = n``, whose *body* needs an algebra theorem HML does not
have and must not acquire as a kernel rule. Judging the quantifier core by whether that
one identity passes would be judging the wrong thing — so every positive test here builds
its body generically, mostly by eliminating an existing universal and re-introducing it.

That round trip is a real test: it exercises binder construction, re-depthing, capture
avoidance and the eigenvariable condition together, and it would fail loudly if the
locally-nameless numbering were even slightly wrong.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import DerivationStatus, GoalStatus
from hamiltonian_lang.reasoning import kernel


def _run(src: str):
    r = compile_source(src, "<q>")
    return r, r.reasoning


def _status(src: str, label: str) -> str:
    """The derivation's status, or ``<not reached>`` if an earlier pass rejected the module.

    Reasoning runs only after resolution and type checking succeed, so a module that fails
    earlier has no reasoning result at all. For a negative test that is still a pass --
    the step did not reach VERIFIED -- and collapsing the two into one sentinel keeps the
    assertions about the outcome rather than about which pass produced it.
    """
    _, reasoning = _run(src)
    if reasoning is None:
        return "<not reached>"
    return reasoning.derivation_status.get(label, "<absent>")


# --- the rules exist and declare their side conditions ----------------------


def test_the_quantifier_rules_are_in_the_kernel():
    assert "forall_intro" in kernel.RULES
    assert "forall_elim" in kernel.RULES


def test_the_quantifier_rules_declare_context_dependent_side_conditions():
    """The kernel is context-free; these two conditions are not, so they must be named."""
    assert kernel.RULES["forall_intro"].side_conditions == ("eigenvariable",)
    assert kernel.RULES["forall_elim"].side_conditions == ("instantiation_domain",)


def test_an_unimplemented_side_condition_rejects(monkeypatch):
    """A rule can never be admitted by a guard nobody wrote."""
    from dataclasses import replace

    monkeypatch.setitem(
        kernel.RULES,
        "forall_elim",
        replace(kernel.RULES["forall_elim"], side_conditions=("no_such_condition",)),
    )
    src = """module Q
var a : Natural
assume a1 : forall x : Natural . x >= 0.0
derive d1 : a >= 0.0 from a1 by forall_elim(at := a)
"""
    r, _ = _run(src)
    assert not r.ok()
    assert any("not implemented" in str(d) for d in r.diagnostics)


# --- positive ---------------------------------------------------------------


ROUND_TRIP = """module Q
var a : Natural
assume a1 : forall x : Natural . x >= 0.0
goal g1 : forall a : Natural . a >= 0.0
derive d1 : a >= 0.0 from a1 by forall_elim(at := a)
derive d2 : forall a : Natural . a >= 0.0 from d1 by forall_intro(var := a)
proved g1 by d2
"""


def test_elim_then_intro_round_trips_and_proves_the_goal():
    r, reasoning = _run(ROUND_TRIP)
    assert r.ok(), [str(d) for d in r.diagnostics]
    assert reasoning.derivation_status["d1"] == DerivationStatus.VERIFIED
    assert reasoning.derivation_status["d2"] == DerivationStatus.VERIFIED
    assert reasoning.goal_status["g1"] == GoalStatus.PROVED


def test_the_reintroduced_binder_may_be_renamed():
    """Alpha-equivalence: the theorem does not depend on the bound variable's spelling."""
    src = ROUND_TRIP.replace(
        "goal g1 : forall a : Natural . a >= 0.0",
        "goal g1 : forall zzz : Natural . zzz >= 0.0",
    )
    _, reasoning = _run(src)
    assert reasoning.goal_status["g1"] == GoalStatus.PROVED


def test_forall_intro_works_under_a_nested_binder():
    """The inner binder must descend a level when the outer one is introduced."""
    src = """module Q
var a : Natural
assume a1 : forall x : Natural . forall y : Natural . x + y >= 0.0
derive d1 : forall y : Natural . a + y >= 0.0 from a1 by forall_elim(at := a)
derive d2 : forall a : Natural . forall y : Natural . a + y >= 0.0 from d1 by forall_intro(var := a)
"""
    assert _status(src, "d1") == DerivationStatus.VERIFIED
    assert _status(src, "d2") == DerivationStatus.VERIFIED


def test_an_unrelated_assumption_does_not_block_generalisation():
    """The eigenvariable condition is about *this* variable, not about having assumptions."""
    src = ROUND_TRIP.replace(
        "assume a1 :", "var b : Natural\nassume a0 : b = 3.0\nassume a1 :"
    )
    assert _status(src, "d2") == DerivationStatus.VERIFIED


# --- negative ---------------------------------------------------------------


def test_a_witness_specific_assumption_blocks_generalisation():
    """The rule the whole condition exists for: a proof about 0 is not a proof about all."""
    src = """module Q
var a : Natural
assume a1 : forall x : Natural . x >= 0.0
assume a2 : a = 0.0
derive d1 : a >= 0.0 from a1 by forall_elim(at := a)
derive d2 : forall a : Natural . a >= 0.0 from d1 by forall_intro(var := a)
"""
    r, _ = _run(src)
    assert not r.ok()
    assert _status(src, "d2") == DerivationStatus.REJECTED
    assert any("is not arbitrary" in str(d) for d in r.diagnostics)


def test_a_witness_specific_assumption_inside_a_scope_also_blocks_it():
    """Scope frames are walked too; an assumption does not become invisible by nesting."""
    src = """module Q
var a : Natural
assume a1 : forall x : Natural . x >= 0.0
scope
assume a2 : a = 0.0
end
derive d1 : a >= 0.0 from a1 by forall_elim(at := a)
derive d2 : forall a : Natural . a >= 0.0 from d1 by forall_intro(var := a)
"""
    assert _status(src, "d2") == DerivationStatus.REJECTED


def test_wrong_domain_instantiation_is_rejected():
    src = """module Q
var r : Real
assume a1 : forall x : Natural . x >= 0.0
derive d1 : r >= 0.0 from a1 by forall_elim(at := r)
"""
    r, _ = _run(src)
    assert not r.ok()
    assert _status(src, "d1") == DerivationStatus.REJECTED
    assert any("does not inhabit the binder's domain" in str(d) for d in r.diagnostics)


def test_a_body_that_does_not_match_the_claimed_quantification_is_rejected():
    src = """module Q
var a : Natural
assume a1 : forall x : Natural . x >= 0.0
derive d1 : a >= 0.0 from a1 by forall_elim(at := a)
derive d2 : forall a : Natural . a >= 1.0 from d1 by forall_intro(var := a)
"""
    assert _status(src, "d2") == DerivationStatus.REJECTED


def test_forall_elim_needs_a_universal_premise():
    src = """module Q
var a : Natural
assume a1 : a >= 0.0
derive d1 : a >= 0.0 from a1 by forall_elim(at := a)
"""
    assert _status(src, "d1") == DerivationStatus.REJECTED


def test_forall_intro_needs_a_variable_not_an_expression():
    src = """module Q
var a : Natural
assume a1 : forall x : Natural . x >= 0.0
derive d1 : a >= 0.0 from a1 by forall_elim(at := a)
derive d2 : forall a : Natural . a >= 0.0 from d1 by forall_intro(var := a + 1.0)
"""
    assert _status(src, "d2") == DerivationStatus.REJECTED


def test_a_universal_cannot_be_forged_from_a_finite_sample():
    """Checking values is not a proof, and there is no rule that turns one into the other.

    ``forall_intro`` takes exactly one premise and generalises the variable named in
    ``var``; there is no path from a conjunction of instances to a quantified statement.
    """
    src = """module Q
var a : Natural
assume a1 : 0.0 >= 0.0
assume a2 : 1.0 >= 0.0
derive d1 : forall x : Natural . x >= 0.0 from a1, a2 by forall_intro(var := a)
"""
    r, _ = _run(src)
    assert not r.ok()
    assert _status(src, "d1") != DerivationStatus.VERIFIED


@pytest.mark.parametrize("rule", ["forall_intro", "forall_elim"])
def test_the_kernel_still_never_sees_the_claim(rule):
    """The rule builds its conclusion from premises and arguments only.

    Asserted structurally: neither implementation may reference the author's conclusion,
    because a rule that consulted the claim could agree with it by construction.
    """
    import ast as pyast
    import inspect
    import textwrap

    fn = kernel.RULES[rule].apply
    tree = pyast.parse(textwrap.dedent(inspect.getsource(fn)))
    # Strip the docstring: it *describes* the claim comparison at length, and matching on
    # prose would make this test about wording rather than about behaviour.
    for node in pyast.walk(tree):
        if isinstance(node, pyast.FunctionDef) and pyast.get_docstring(node):
            node.body = node.body[1:]
    code = pyast.unparse(tree)
    assert set(inspect.signature(fn).parameters) == {"premises", "args"}, (
        f"{rule} takes something other than premises and arguments"
    )
    for forbidden in ("conclusion", "claimed"):
        assert forbidden not in code, f"{rule} appears to consult the claim"
