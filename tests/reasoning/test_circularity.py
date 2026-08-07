"""Only ESTABLISHED claims may serve as premises.

These tests exist because of a real defect, found by adversarial review after the first
V2 commit and not by the suite. `check.py` correctly kept `goal`/`require`/`prove` out of
the refinement environment Γ -- and said so in a comment naming the exact hazard -- then
wrote them into the premise pool anyway. The result compiled with zero diagnostics:

    goal   g1 : 1.0 = 2.0
    derive d1 : 2.0 = 1.0 from g1 by symmetry
    derive d2 : 1.0 = 2.0 from d1 by symmetry
    proved g1 by d2                             -> g1 PROVED, exit 0

Both derivations really are valid applications of symmetry, so the trusted kernel was
blameless. The hole was admitting an unestablished claim as a premise, which let a goal
support the derivation that proved it.

The lesson generalises past this one bug: the forward-reference ordering rule is only an
acyclicity argument if every claim in the namespace is *established* when it is cited.
Textual order alone is not enough.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import DerivationStatus, DeriveStmt, GoalStatus

PRELUDE = "module M\nvar x : Real\nvar y : Real\nvar k : Real\n"


def _compile(body: str):
    return compile_source(PRELUDE + body, "<test>")


def _codes(result) -> list[str]:
    return [d.code for d in result.diagnostics.items]


def _status(result, label: str) -> str:
    for st in result.module.statements:
        if isinstance(st, DeriveStmt) and st.label == label:
            return st.status
    raise AssertionError(f"no derivation {label!r}")


# ---------------------------------------------------------------------------
# The exploit itself
# ---------------------------------------------------------------------------


def test_a_goal_cannot_prove_itself():
    """The original exploit, verbatim. Must not reach PROVED."""
    r = compile_source(
        "module M\n"
        "goal   g1 : 1.0 = 2.0\n"
        "derive d1 : 2.0 = 1.0 from g1 by symmetry\n"
        "derive d2 : 1.0 = 2.0 from d1 by symmetry\n"
        "proved g1 by d2\n",
        "<test>",
    )
    assert not r.ok(), "a self-proving goal must not compile clean"
    assert "HML-R712" in _codes(r)
    assert r.reasoning.goal_status.get("g1") != GoalStatus.PROVED


@pytest.mark.parametrize(
    ("kind", "line"),
    [
        ("goal", "goal g0 : y = 2.0 * x"),
        ("require", "require r0 : y = 2.0 * x"),
        ("prove", "prove p0 : y = 2.0 * x"),
    ],
)
def test_an_unestablished_claim_cannot_be_a_premise(kind, line):
    label = {"goal": "g0", "require": "r0", "prove": "p0"}[kind]
    r = _compile(f"{line}\nderive d1 : 2.0 * x = y from {label} by symmetry\n")
    assert not r.ok(), f"{kind} was accepted as a premise"
    assert "HML-R712" in _codes(r)
    assert _status(r, "d1") == DerivationStatus.REJECTED


def test_prove_cannot_launder_a_falsehood():
    """`prove` states a claim. If it could be a premise, `prove 1 = 2` would be a proof."""
    r = compile_source(
        "module M\n"
        "prove  p1 : 1.0 = 2.0\n"
        "derive d1 : 2.0 = 1.0 from p1 by symmetry\n",
        "<test>",
    )
    assert not r.ok()
    assert "HML-R712" in _codes(r)


def test_an_assumption_is_still_a_valid_premise():
    """The fix must not break the legitimate case: `assume` IS established."""
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : 2.0 * x = y from a1 by symmetry\n"
    )
    assert r.ok(), r.diagnostics.render()
    assert _status(r, "d1") == DerivationStatus.VERIFIED


def test_a_derivation_is_a_valid_premise_for_a_later_derivation():
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : 2.0 * x = y from a1 by symmetry\n"
        "derive d2 : y = 2.0 * x from d1 by symmetry\n"
    )
    assert r.ok(), r.diagnostics.render()
    assert _status(r, "d2") == DerivationStatus.VERIFIED


# ---------------------------------------------------------------------------
# Obligation propagation
# ---------------------------------------------------------------------------


def test_an_open_obligation_propagates_to_dependent_steps():
    """A conclusion is no better established than the weakest premise it stands on.

    The assertion is on STATUS, not on which diagnostic fires. Since D-036 made
    definedness a property of terms, `d2`'s own conclusion `2.0 * x / k = y / k`
    contains a division and so raises its *own* obligation (HML-R707) as well as
    inheriting `d1`'s (HML-R713). Pinning the code here would have been pinning an
    implementation detail; the property under test is that neither step is certified.
    """
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : y / k = 2.0 * x / k from a1 by divide_both_sides(by := k)\n"
        "derive d2 : 2.0 * x / k = y / k from d1 by symmetry\n"
    )
    assert _status(r, "d1") == DerivationStatus.CHECKED, "k != 0 is not established"
    assert _status(r, "d2") == DerivationStatus.CHECKED, (
        "d2 rests on d1's undischarged obligation and must not be VERIFIED"
    )
    codes = _codes(r)
    assert "HML-R707" in codes or "HML-R713" in codes


def test_propagation_holds_when_the_dependent_step_has_no_partial_term():
    """Isolates propagation from term-level definedness.

    `d2`'s conclusion mentions no partial operation, so its only reason not to be
    certified is the obligation it inherits from `d1`. This is the case the previous
    test was written to cover before terms carried their own obligations.
    """
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : y / k = 2.0 * x / k from a1 by divide_both_sides(by := k)\n"
        "derive d2 : y / k = 2.0 * x / k and y = 2.0 * x from d1, a1 by and_intro\n"
        "derive d3 : y = 2.0 * x from d2 by and_elim_right\n"
    )
    # d3's conclusion mentions no partial operation at all, so the ONLY thing standing
    # between it and VERIFIED is the obligation it inherits through d2 from d1.
    assert _status(r, "d3") == DerivationStatus.CHECKED
    assert "HML-R713" in _codes(r), "inheritance must be reported in its own right"


def test_discharging_the_root_obligation_certifies_the_whole_chain():
    r = _compile(
        "assume a0 : k != 0.0\n"
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : y / k = 2.0 * x / k from a1 by divide_both_sides(by := k)\n"
        "derive d2 : 2.0 * x / k = y / k from d1 by symmetry\n"
    )
    assert r.ok(), r.diagnostics.render()
    assert _status(r, "d1") == DerivationStatus.VERIFIED
    assert _status(r, "d2") == DerivationStatus.VERIFIED


def test_a_propagated_obligation_blocks_proved():
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : y / k = 2.0 * x / k from a1 by divide_both_sides(by := k)\n"
        "derive d2 : 2.0 * x / k = y / k from d1 by symmetry\n"
        "goal g1 : 2.0 * x / k = y / k\n"
        "proved g1 by d2\n"
    )
    assert not r.ok()
    assert "HML-R710" in _codes(r)
    assert r.reasoning.goal_status.get("g1") != GoalStatus.PROVED
