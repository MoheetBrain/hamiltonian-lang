"""Certified underdetermination, and the four-way distinction it lives inside.

The property under test is not "does the G06 case work". It is: **can anything that is
merely ignorance reach ``UNDERDETERMINED``?** Every negative below is an attempt to make
that happen — a violated premise, a partial model, a duplicated witness, a stale context, a
context that omits a premise, an unsupported fragment, a target the premises actually
settle. All of them must land on ``OPEN``/``UNKNOWN``.

The asymmetry is deliberate and worth stating: a false negative here costs a user an
expressible result, while a false positive records "this cannot be decided" about something
that can be. Only one of those is a lie.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import EvidenceStatus, GoalStatus
from hamiltonian_lang.reasoning.adjudication import EntailmentVerdict

#: Γ = {P -> Q, Q}, target P. The Gold-10 G06 shape: Q's truth does not give you P.
G06 = """module G06
var P : Bool
var Q : Bool
assume a1 : P implies Q
assume a2 : Q
goal g1 : P
"""

WITNESSES = "holds := P and Q, fails := (not P) and Q"
CERT = "evidence e1 : determines_neither P from a1, a2 by propositional_underdetermination_v1({w})\n"
CLAIM = "undetermined g1 by e1\n"


def _run(src: str):
    r = compile_source(src, "<ud>")
    return r, r.reasoning


def _goal(src: str, goal: str = "g1") -> str:
    _, reasoning = _run(src)
    return reasoning.goal_status.get(goal, "<absent>")


def _verdict(src: str, goal: str = "g1"):
    _, reasoning = _run(src)
    a = reasoning.adjudications.get(goal)
    return a.verdict if a else None


# --- A/B/C/D: the four-way distinction --------------------------------------


def test_A_entailed_reaches_proved_not_underdetermined():
    """Γ = {P -> Q, P}, target Q. Modus ponens settles it."""
    src = """module A
var P : Bool
var Q : Bool
assume a1 : P implies Q
assume a2 : P
goal g1 : Q
derive d1 : Q from a2, a1 by modus_ponens
proved g1 by d1
"""
    assert _goal(src) == GoalStatus.PROVED
    assert _verdict(src) is EntailmentVerdict.ENTAILED


def test_B_a_context_that_refutes_the_target_cannot_be_certified_underdetermined():
    """Γ = {not P}, target P.

    ``REFUTED`` has no adjudicating statement form (nor did it before this work), so what
    is asserted is the safety property: the underdetermination route must be *closed*.
    No model of Γ makes P true, so no positive witness exists and the certificate fails.
    """
    src = """module B
var P : Bool
assume a1 : not P
goal g1 : P
evidence e1 : determines_neither P from a1 by propositional_underdetermination_v1(holds := P, fails := not P)
undetermined g1 by e1
"""
    assert _goal(src) != GoalStatus.UNDERDETERMINED
    assert _verdict(src) is EntailmentVerdict.UNKNOWN


def test_C_underdetermined_is_certified_for_the_G06_shape():
    src = G06 + CERT.format(w=WITNESSES) + CLAIM
    r, reasoning = _run(src)
    assert r.ok(), [str(d) for d in r.diagnostics]
    assert reasoning.evidence_status["e1"] == EvidenceStatus.VALID
    assert reasoning.goal_status["g1"] == GoalStatus.UNDERDETERMINED
    a = reasoning.adjudications["g1"]
    assert a.verdict is EntailmentVerdict.UNDERDETERMINED
    assert a.support == "e1"
    assert a.checker == "propositional_underdetermination_v1"
    assert a.context_hash and a.target_hash
    assert reasoning.underdetermined() == ["g1"]


def test_D_an_unsupported_fragment_is_UNKNOWN_never_UNDERDETERMINED():
    """A Real-typed atom is outside finite propositional logic. That is ignorance."""
    src = """module D
var x : Real
var Q : Bool
assume a1 : x > 0.0
assume a2 : Q
goal g1 : Q
evidence e1 : determines_neither Q from a1, a2 by propositional_underdetermination_v1(holds := Q, fails := not Q)
undetermined g1 by e1
"""
    assert _goal(src) != GoalStatus.UNDERDETERMINED
    assert _verdict(src) is EntailmentVerdict.UNKNOWN


def test_the_four_goal_states_are_distinct_values():
    """OPEN, PROVED, UNSUBSTANTIATED and UNDERDETERMINED must not collapse."""
    assert len({
        GoalStatus.OPEN,
        GoalStatus.PROVED,
        GoalStatus.REFUTED,
        GoalStatus.UNSUBSTANTIATED,
        GoalStatus.UNDERDETERMINED,
    }) == 5
    assert GoalStatus.UNDERDETERMINED in GoalStatus.ALL


def test_an_unadjudicated_goal_is_open_not_underdetermined():
    """Nobody said anything about it. That is OPEN, and it is the honest answer."""
    assert _goal(G06) == GoalStatus.OPEN


# --- attacks on the certificate ---------------------------------------------


@pytest.mark.parametrize(
    "name,witnesses",
    [
        # `fails` sets Q false, which violates premise a2. A witness outside Γ says
        # nothing about entailment from Γ.
        ("witness violates a premise", "holds := P and Q, fails := (not P) and (not Q)"),
        # One model cannot give the target both truth values.
        ("duplicated witness", "holds := P and Q, fails := P and Q"),
        # Q unassigned: an incomplete model is rejected, never completed.
        ("partial model", "holds := P, fails := not P"),
        # Both witnesses agree on the target, so nothing is shown.
        ("both witnesses agree", "holds := P and Q, fails := P and Q"),
        # The target is true in `fails`, which is backwards.
        ("witnesses swapped", "holds := (not P) and Q, fails := P and Q"),
    ],
)
def test_a_broken_witness_pair_never_certifies(name, witnesses):
    src = G06 + CERT.format(w=witnesses) + CLAIM
    r, reasoning = _run(src)
    assert not r.ok(), name
    assert reasoning.evidence_status["e1"] == EvidenceStatus.REJECTED, name
    assert reasoning.goal_status["g1"] != GoalStatus.UNDERDETERMINED, name
    assert reasoning.adjudications["g1"].verdict is EntailmentVerdict.UNKNOWN, name


def test_an_undeclared_atom_in_a_witness_is_rejected():
    src = G06.replace("goal g1 : P\n", "var R : Bool\ngoal g1 : P\n") + CERT.format(
        w="holds := P and Q and R, fails := (not P) and Q and R"
    ) + CLAIM
    r, reasoning = _run(src)
    assert not r.ok()
    assert reasoning.evidence_status["e1"] == EvidenceStatus.REJECTED


def test_a_numeric_witness_value_never_certifies():
    """The evaluator restores booleans with ``raw != 0``, so ``P := 2`` would mean true.

    Two independent barriers stop that, and this asserts the outcome rather than which one
    fired: the type system rejects ``P = 2.0`` for a ``Bool`` P before the checker runs at
    all, and the witness grammar would reject it if it ever got through. Depth here is
    deliberate — the convention that makes the attack conceivable lives two modules away
    in the evaluator, so it should not be one barrier's job alone.
    """
    src = G06 + CERT.format(w="holds := P = 2.0, fails := (not P) and Q") + CLAIM
    r, reasoning = _run(src)
    assert not r.ok()
    if reasoning is not None:
        assert reasoning.evidence_status.get("e1") != EvidenceStatus.VALID
        assert reasoning.goal_status.get("g1") != GoalStatus.UNDERDETERMINED


@pytest.mark.parametrize(
    "witness",
    [
        "5.0",  # not a conjunction of literals at all
        "P or Q",  # disjunction is not an assignment
        "P and P",  # the same name twice
        "P implies Q",  # a constraint, not a model
    ],
)
def test_the_witness_grammar_rejects_anything_that_is_not_a_total_assignment(witness):
    """Checked directly, so the guard is tested even where the type system fires first."""
    from hamiltonian_lang.reasoning.certificates.builtin import extract_model

    r = compile_source(
        f"module W\nvar P : Bool\nvar Q : Bool\nassume a1 : {witness}\n", "<w>"
    )
    if not r.ok():
        pytest.skip("rejected earlier than the witness grammar, which is also correct")
    prop = r.module.statements[-1].proposition
    with pytest.raises(ValueError):
        extract_model(prop)


def test_a_certificate_omitting_a_premise_is_rejected():
    """Entailment is monotone: Γ ⊭ P for a subset says nothing about Γ."""
    src = (
        G06
        + "evidence e1 : determines_neither P from a1 by "
        "propositional_underdetermination_v1(" + WITNESSES + ")\n"
        + CLAIM
    )
    r, reasoning = _run(src)
    assert not r.ok()
    assert any("does not rest on every established claim" in str(d) for d in r.diagnostics)
    assert reasoning.goal_status["g1"] != GoalStatus.UNDERDETERMINED


def test_a_certificate_is_not_spendable_after_the_context_changes():
    """The stale-context replay. A premise added later may settle the target."""
    src = G06 + CERT.format(w=WITNESSES) + "assume a3 : P\n" + CLAIM
    r, reasoning = _run(src)
    assert not r.ok()
    assert any("different context" in str(d) for d in r.diagnostics)
    assert reasoning.goal_status["g1"] != GoalStatus.UNDERDETERMINED
    assert reasoning.adjudications["g1"].verdict is EntailmentVerdict.UNKNOWN


def test_a_certificate_about_another_proposition_cannot_settle_this_goal():
    src = G06.replace("goal g1 : P\n", "goal g1 : Q\n") + CERT.format(w=WITNESSES) + CLAIM
    r, reasoning = _run(src)
    assert not r.ok()
    assert reasoning.goal_status["g1"] != GoalStatus.UNDERDETERMINED


def test_entails_evidence_cannot_show_underdetermination():
    """Establishing P and showing P is unsettled are opposite results."""
    src = """module E
var P : Bool
assume a1 : P
goal g1 : 5.0 - 2.0 = 3.0
evidence e1 : entails 5.0 - 2.0 = 3.0 from a1 by closed_eval_v1()
undetermined g1 by e1
"""
    r, reasoning = _run(src)
    assert not r.ok()
    assert reasoning.goal_status["g1"] != GoalStatus.UNDERDETERMINED


def test_a_rejected_certificate_leaves_the_goal_open():
    src = G06 + CERT.format(w="holds := P and Q, fails := P and Q") + CLAIM
    _, reasoning = _run(src)
    assert reasoning.goal_status["g1"] == GoalStatus.OPEN


# --- the laundering barrier -------------------------------------------------


def test_determines_neither_evidence_can_never_be_a_premise():
    """"P is undetermined" must never become "P". The worst failure available here."""
    src = G06 + CERT.format(w=WITNESSES) + "derive d1 : Q from e1, a1 by modus_ponens\n"
    r, reasoning = _run(src)
    assert not r.ok()
    assert any("cannot be a premise" in str(d) for d in r.diagnostics)
    assert "d1" not in reasoning.verified()


def test_underdetermination_does_not_make_the_goal_provable():
    src = G06 + CERT.format(w=WITNESSES) + CLAIM
    _, reasoning = _run(src)
    assert reasoning.goal_status["g1"] != GoalStatus.PROVED
