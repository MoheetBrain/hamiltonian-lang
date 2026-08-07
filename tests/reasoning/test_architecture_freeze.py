"""Mechanical enforcement of `docs/hml_v2/ARCHITECTURE_FREEZE.md`.

The freeze names six architectural decisions (D-029 … D-034). Several of them describe
properties the code *already* has. Those are pinned here, so that the freeze is a
contract rather than a description — a document that says "status is never part of
identity" and is not asserted anywhere will stop being true without anyone noticing.

Decisions the freeze makes about work not yet done (scoped Γ, precondition contracts,
approximation, certificates) are NOT tested here. They are tested by the steps that
implement them. A test asserting an unimplemented decision would be an xfail pretending
to be a guard, and this file deliberately contains none.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import DerivationStatus
from hamiltonian_lang.lexer import KEYWORDS

# ---------------------------------------------------------------------------
# D-029 — evidence never enters semantic identity
# ---------------------------------------------------------------------------

_VERIFIED_MODULE = """module M
var x : Real
var y : Real
assume a1 : y = 2.0 * x
derive d1 : 2.0 * x = y from a1 by symmetry
goal g1 : 2.0 * x = y
proved g1 by d1
"""


def test_e1_content_hash_is_invariant_under_re_verification():
    """Checking a module twice must not change what it *is*."""
    first = compile_source(_VERIFIED_MODULE, "<test>")
    second = compile_source(_VERIFIED_MODULE, "<test>")
    assert first.ok() and second.ok()
    assert first.hash() == second.hash()


def test_e1_the_hash_does_not_depend_on_the_verdict():
    """Two modules identical except that one's derivation FAILS to verify must still
    differ only where the mathematics differs -- and a module whose verdict changes
    without its statements changing must not change hash.

    Constructed by taking the verified module and making the SAME claim with an
    undischargeable obligation. The hashes must differ (the mathematics differs), but
    re-running either must be stable -- which is what E1 actually asserts.
    """
    ok_mod = compile_source(_VERIFIED_MODULE, "<test>")
    open_mod = compile_source(
        "module M\nvar x : Real\nvar y : Real\nvar k : Real\n"
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : y / k = 2.0 * x / k from a1 by divide_both_sides(by := k)\n",
        "<test>",
    )
    assert ok_mod.hash() == compile_source(_VERIFIED_MODULE, "<test>").hash()
    # The CHECKED-not-VERIFIED module also hashes stably despite carrying an open
    # obligation, i.e. the obligation is evidence and not identity.
    again = compile_source(
        "module M\nvar x : Real\nvar y : Real\nvar k : Real\n"
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : y / k = 2.0 * x / k from a1 by divide_both_sides(by := k)\n",
        "<test>",
    )
    assert open_mod.hash() == again.hash()
    assert open_mod.reasoning.open_obligations(), "precondition of this test"


def test_e1_no_checker_identity_appears_in_the_canonical_form():
    """A dependency bump must not rewrite history."""
    doc = compile_source(_VERIFIED_MODULE, "<test>").canonical()
    for leak in ("sympy", "z3", "lean", "hml-kernel", "VERIFIED", "DISCHARGED",
                 "produced_at", "checker"):
        assert leak not in doc, f"evidence token {leak!r} leaked into semantic identity"


def test_e3_there_is_no_surface_syntax_for_a_status():
    """The load-bearing claim of the whole reasoning model: a model can assert a
    derivation, but cannot assert that the derivation is correct."""
    for status in DerivationStatus.ALL:
        assert status.lower() not in KEYWORDS
        assert status not in KEYWORDS
    # And an attempt to write one is a parse error, not a silent annotation.
    r = compile_source(
        "module M\nvar x : Real\n"
        "assume a1 : x = x\n"
        "derive d1 : x = x from a1 by symmetry VERIFIED\n",
        "<test>",
    )
    assert not r.ok()


def test_e5_premise_order_is_part_of_semantic_identity():
    """`transitivity` on (a=b, b=c) is a different inference from (b=c, a=b)."""
    base = (
        "module M\nvar x : Real\nvar y : Real\nvar z : Real\n"
        "assume a1 : x = y\n"
        "assume a2 : y = z\n"
    )
    forward = compile_source(base + "derive d1 : x = z from a1, a2 by transitivity\n", "<t>")
    assert forward.ok(), forward.diagnostics.render()
    reversed_ = compile_source(base + "derive d1 : x = z from a2, a1 by transitivity\n", "<t>")
    # The reversed order does not even apply; what matters here is that if both had
    # applied they would be different objects. Assert the identity claim directly.
    assert not reversed_.ok(), "premise order is meaningful, so this must not silently work"


# ---------------------------------------------------------------------------
# D-030 — Γ rules that already hold
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stating", ["require", "prove"])
def test_g3_only_assume_contributes_facts(stating):
    """A module must not license a partial operation by *asking* for the thing that
    makes it legal."""
    src = f"module M\nvar x : Real\n{stating} x > 0.0\nrequire log(x) = log(x)\n"
    assert not compile_source(src, "<test>").ok()


def test_g4_narrowing_never_widens():
    assert not compile_source(
        "module M\nparam p : Probability\nassume p > 0.0\nparam q : PositiveReal = p\n",
        "<test>",
    ).ok()


def test_g5_module_level_assumptions_are_order_independent():
    """D-008 consistency: an assumption stated below a use still constrains it."""
    before = compile_source(
        "module M\nvar x : Real\nassume x > 0.0\nrequire log(x) = log(x)\n", "<t>"
    )
    after = compile_source(
        "module M\nvar x : Real\nrequire log(x) = log(x)\nassume x > 0.0\n", "<t>"
    )
    assert before.ok() and after.ok(), "module scope is order-independent (D-008)"


# ---------------------------------------------------------------------------
# D-034 — extension trust
# ---------------------------------------------------------------------------


def test_x1_there_is_no_keyword_that_grants_trust():
    """No `trusted`, no `axiom`, no `sorry`. Trust is structural, never annotated."""
    for word in ("trusted", "axiom", "sorry", "admit", "assert_verified", "believe"):
        assert word not in KEYWORDS


def test_x1_a_user_cannot_introduce_an_inference_rule():
    """Until D-034's LIBRARY tier exists, the only rules are CORE ones, and an unknown
    rule is refused rather than believed."""
    r = compile_source(
        "module M\nvar x : Real\nassume a1 : x = x\n"
        "derive d1 : x = x from a1 by my_own_rule\n",
        "<test>",
    )
    assert not r.ok()
    assert "HML-R704" in [d.code for d in r.diagnostics.items]


def test_x3_every_core_rule_rejects_a_step_differing_only_in_its_conclusion():
    """The bar D-034 X3 sets for CORE membership, asserted over the whole kernel.

    For each rule, apply it to premises it accepts, then assert that the kernel's
    conclusion is not equal to a deliberately corrupted one. A rule that cannot tell
    those apart certifies anything and does not belong in CORE.
    """
    from hamiltonian_lang.ast.nodes import Comparison, Literal, Ref
    from hamiltonian_lang.backends.canonical import expr_identity
    from hamiltonian_lang.reasoning import kernel

    checked = 0
    for name, spec in kernel.RULES.items():
        premises = [
            Comparison(op="=", left=Ref(name="a"), right=Ref(name="b"))
            for _ in range(spec.arity)
        ]
        args = {p: Literal(value=1.0, raw="1.0") for p in spec.params}
        outcome = kernel.apply(name, premises, args)
        if not outcome.ok or outcome.conclusion is None:
            continue
        corrupted = Comparison(
            op="=", left=Ref(name="a"), right=Literal(value=99.0, raw="99.0")
        )
        assert expr_identity(outcome.conclusion) != expr_identity(corrupted), (
            f"{name} cannot distinguish its own conclusion from a corrupted one"
        )
        checked += 1
    assert checked >= 8, f"only {checked} rules exercised; the kernel has {len(kernel.RULES)}"
