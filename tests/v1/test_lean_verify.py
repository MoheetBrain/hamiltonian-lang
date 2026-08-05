"""Lean verification must be unable to certify a false theorem.

Every trap below was confirmed by direct experiment on Lean 4.32.2, not assumed:

    $ cat False.lean
    theorem definitely_false : (1 : Nat) = 2 := by sorry
    $ lean False.lean ; echo $?
    warning: declaration uses `sorry`
    0                      <-- exit 0 on a demonstrably FALSE theorem

`#print axioms` is the only discriminator (`sorryAx`). Separately, with `autoImplicit` at
its default Lean silently invents a missing type, so `∀ x : Real, x = x` elaborates
vacuously even though `Real` does not exist without Mathlib.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.v1.lean_verify import (
    FORBIDDEN_TACTICS,
    LeanVerdict,
    lean_available,
    verify,
)

needs_lean = pytest.mark.skipif(not lean_available(), reason="no `lean` on PATH")


# -- checks that hold with or without a toolchain ------------------------


@pytest.mark.parametrize("tactic", FORBIDDEN_TACTICS)
def test_a_goal_closing_tactic_is_rejected_before_lean_runs(tactic):
    r = verify(f"theorem t : (1 : Nat) = 2 := by {tactic}")
    assert r.verdict is LeanVerdict.REJECTED_FORBIDDEN_TACTIC
    assert not r.verified


def test_a_statement_mismatch_is_rejected():
    """Compiling proves something; it does not prove it was the intended thing."""
    r = verify(
        "theorem t (n : Nat) : n = n := by rfl",
        expected_statement="theorem t (n : Nat) : n = n + 1",
    )
    assert r.verdict is LeanVerdict.REJECTED_STATEMENT_MISMATCH


def test_source_with_no_theorem_is_rejected():
    assert verify("def f (n : Nat) : Nat := n").verdict is LeanVerdict.REJECTED_NO_THEOREM


def test_verified_is_the_only_property_that_licenses_a_proved_label():
    for verdict in LeanVerdict:
        if verdict is not LeanVerdict.VERIFIED:
            from hamiltonian_lang.v1.lean_verify import LeanResult

            assert not LeanResult(verdict).verified


# -- checks that require the real toolchain ------------------------------


@needs_lean
def test_a_real_proof_is_verified():
    r = verify("theorem t_refl (n : Nat) : n = n := by rfl")
    assert r.verified, r.detail
    assert r.axioms["t_refl"] == []


@needs_lean
def test_a_decidable_truth_is_verified():
    assert verify("theorem t_two : 1 + 1 = 2 := by decide").verified


@needs_lean
def test_standard_classical_axioms_are_accepted():
    r = verify("theorem t_em (p : Prop) : p ∨ ¬p := Classical.em p")
    assert r.verified
    assert set(r.axioms["t_em"]) <= {"propext", "Classical.choice", "Quot.sound"}


@needs_lean
def test_autoimplicit_vacuity_is_rejected():
    """Without Mathlib `Real` does not exist. At Lean's default settings this compiles
    anyway, auto-binding `Real` as an arbitrary sort — proving nothing. `autoImplicit
    false` turns that into a compile error, which is the point."""
    r = verify("theorem t_vac : forall x : Real, x = x := by intro x; rfl")
    assert not r.verified
    assert r.verdict is LeanVerdict.REJECTED_COMPILE_ERROR


@needs_lean
def test_a_matching_statement_still_verifies():
    r = verify(
        "theorem t_refl (n : Nat) : n = n := by rfl",
        expected_statement="theorem t_refl (n : Nat) : n = n",
    )
    assert r.verified


@needs_lean
def test_the_two_quantifier_scopings_are_distinguishable_to_the_kernel():
    """The distinction HML keeps structurally, checked independently by Lean.

    Over the naturals, `∀ n, ∃ m, m > n` is provable and `∃ m, ∀ n, m > n` is false —
    so the kernel agrees the two orderings are different propositions.
    """
    forward = verify(
        "theorem qs : ∀ n : Nat, ∃ m : Nat, m > n := by\n"
        "  intro n; exact ⟨n + 1, Nat.lt_succ_self n⟩"
    )
    assert forward.verified, forward.detail
    reversed_ = verify(
        "theorem qs_rev : ∃ m : Nat, ∀ n : Nat, m > n := by\n"
        "  exact ⟨0, by intro n; exact Nat.lt_irrefl 0 (by omega)⟩"
    )
    assert not reversed_.verified, "the false scoping must NOT verify"
