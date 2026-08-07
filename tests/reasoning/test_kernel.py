"""The trusted inference kernel, tested for what it REFUSES as much as what it accepts.

A rule engine that accepts every correct step is easy. The property that matters here is
that it accepts *only* correct steps, so most of this file is negative.
"""

from __future__ import annotations

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import DerivationStatus, DeriveStmt, GoalStatus, GoalStmt
from hamiltonian_lang.reasoning import kernel

PRELUDE = "module M\nvar x : Real\nvar y : Real\nvar k : Real\n"


def _compile(body: str):
    return compile_source(PRELUDE + body, "<test>")


def _status(result, label: str) -> str:
    for st in result.module.statements:
        if isinstance(st, DeriveStmt) and st.label == label:
            return st.status
    raise AssertionError(f"no derivation {label!r}")


def _codes(result) -> list[str]:
    return [d.code for d in result.diagnostics.items]


# ---------------------------------------------------------------------------
# Positive: a correct step reaches VERIFIED
# ---------------------------------------------------------------------------


def test_a_correct_step_with_no_side_condition_is_verified():
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : y + 1.0 = 2.0 * x + 1.0 from a1 by add_both_sides(by := 1.0)\n"
    )
    assert r.ok(), r.diagnostics.render()
    assert _status(r, "d1") == DerivationStatus.VERIFIED


def test_symmetry_transitivity_and_congruence_verify():
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : 2.0 * x = y from a1 by symmetry\n"
        "assume a2 : 2.0 * x = k\n"
        "derive d2 : y = k from a1, a2 by transitivity\n"
        "derive d3 : exp(y) = exp(2.0 * x) from a1 by congruence(fn := exp)\n"
    )
    assert r.ok(), r.diagnostics.render()
    for label in ("d1", "d2", "d3"):
        assert _status(r, label) == DerivationStatus.VERIFIED


def test_modus_ponens_verifies():
    r = _compile(
        "assume a1 : x > 0.0\n"
        "assume a2 : x > 0.0 implies y > 0.0\n"
        "derive d1 : y > 0.0 from a1, a2 by modus_ponens\n"
    )
    assert r.ok(), r.diagnostics.render()
    assert _status(r, "d1") == DerivationStatus.VERIFIED


# ---------------------------------------------------------------------------
# Negative: the kernel must reject
# ---------------------------------------------------------------------------


def test_a_false_conclusion_is_rejected():
    """The whole point. Same premise, same rule, a conclusion the rule does not license."""
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : y + 1.0 = 2.0 * x + 99.0 from a1 by add_both_sides(by := 1.0)\n"
    )
    assert not r.ok()
    assert "HML-R706" in _codes(r)
    assert _status(r, "d1") == DerivationStatus.REJECTED


def test_transitivity_refuses_a_mismatched_middle_term():
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "assume a2 : k = 3.0 * x\n"
        "derive d1 : y = 3.0 * x from a1, a2 by transitivity\n"
    )
    assert not r.ok()
    assert "HML-R705" in _codes(r) or "HML-R706" in _codes(r)
    assert _status(r, "d1") == DerivationStatus.REJECTED


def test_modus_ponens_refuses_affirming_the_consequent():
    """`Q` and `P implies Q` does NOT give `P`. The classic fallacy, mechanically refused."""
    r = _compile(
        "assume a1 : y > 0.0\n"
        "assume a2 : x > 0.0 implies y > 0.0\n"
        "derive d1 : x > 0.0 from a1, a2 by modus_ponens\n"
    )
    assert not r.ok()
    assert _status(r, "d1") == DerivationStatus.REJECTED


def test_no_rule_strengthens_a_non_strict_premise_into_a_strict_conclusion():
    """`a <= b` |- `a < b` is unsound and no rule may do it.

    Asserted by *running* every rule against a non-strict premise and inspecting the
    conclusion it produces, not by matching the doc string. A rule could be documented
    as weakening and implemented as strengthening; only execution catches that.
    """
    from hamiltonian_lang.ast.nodes import Comparison, Literal, Ref

    def premise() -> Comparison:
        return Comparison(
            op="<=",
            left=Ref(name="a"),
            right=Ref(name="b"),
        )

    offenders: list[str] = []
    for name, spec in kernel.RULES.items():
        args = {p: Literal(value=1.0, raw="1.0") for p in spec.params}
        premises = [premise() for _ in range(spec.arity)]
        outcome = kernel.apply(name, premises, args)
        if not outcome.ok or outcome.conclusion is None:
            continue
        for node in _comparisons(outcome.conclusion):
            if node.op in ("<", ">"):
                offenders.append(name)
    assert not offenders, f"rules producing a strict conclusion from `<=`: {offenders}"


def _comparisons(e):
    from hamiltonian_lang.ast.nodes import Comparison, walk

    return [n for n in walk(e) if isinstance(n, Comparison)]


def test_an_unknown_rule_is_rejected_and_not_invented():
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : y = 2.0 * x from a1 by my_own_rule\n"
    )
    assert not r.ok()
    assert "HML-R704" in _codes(r)


def test_wrong_premise_count_is_rejected():
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : 2.0 * x = y from a1, a1 by symmetry\n"
    )
    assert not r.ok()


def test_a_premise_of_the_wrong_shape_is_rejected():
    """`symmetry` needs an equation; an inequality is not one."""
    r = _compile(
        "assume a1 : y > 2.0 * x\n"
        "derive d1 : 2.0 * x > y from a1 by symmetry\n"
    )
    assert not r.ok()
    assert "HML-R705" in _codes(r)


# ---------------------------------------------------------------------------
# Provenance and scope
# ---------------------------------------------------------------------------


def test_a_derivation_may_not_cite_itself():
    r = _compile(
        "derive d1 : y = y from d1 by symmetry\n"
    )
    assert not r.ok()
    assert "HML-R702" in _codes(r)


def test_a_derivation_may_not_cite_a_later_claim():
    """Forward references are what a provenance cycle would be made of."""
    r = _compile(
        "derive d1 : 2.0 * x = y from a1 by symmetry\n"
        "assume a1 : y = 2.0 * x\n"
    )
    assert not r.ok()
    assert "HML-R703" in _codes(r)


def test_duplicate_claim_labels_are_rejected():
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "assume a1 : x > 0.0\n"
    )
    assert not r.ok()
    assert "HML-R701" in _codes(r)


def test_a_claim_label_is_not_a_value():
    """`d1` names an inference. Using it as a number must be a scope error."""
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : 2.0 * x = y from a1 by symmetry\n"
        "require d1 > 0.0\n"
    )
    assert not r.ok()
    assert "HML-N301" in _codes(r)


# ---------------------------------------------------------------------------
# The goal lifecycle
# ---------------------------------------------------------------------------


def test_proved_is_adjudicated_not_accepted():
    """`proved g by d` where d is REJECTED must not mark g PROVED."""
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : y = 99.0 from a1 by symmetry\n"
        "goal g1 : y = 99.0\n"
        "proved g1 by d1\n"
    )
    assert not r.ok()
    assert "HML-R710" in _codes(r)
    goals = [s for s in r.module.statements if isinstance(s, GoalStmt)]
    assert goals[0].status == GoalStatus.UNSUBSTANTIATED


def test_proved_requires_the_derivation_to_conclude_the_goal():
    """A VERIFIED derivation of something *else* does not prove the goal."""
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : 2.0 * x = y from a1 by symmetry\n"
        "goal g1 : x > 0.0\n"
        "proved g1 by d1\n"
    )
    assert not r.ok()
    assert "HML-R711" in _codes(r)


def test_a_goal_with_a_verified_derivation_is_proved():
    r = _compile(
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : 2.0 * x = y from a1 by symmetry\n"
        "goal g1 : 2.0 * x = y\n"
        "proved g1 by d1\n"
    )
    assert r.ok(), r.diagnostics.render()
    goals = [s for s in r.module.statements if isinstance(s, GoalStmt)]
    assert goals[0].status == GoalStatus.PROVED


def test_prove_still_does_not_prove():
    """v1's `prove` is unchanged and still states an obligation rather than proving it.

    V2 does not silently reinterpret historical files (directive §9/§28): `prove P`
    keeps its v1 meaning. What V2 adds is `goal`/`derive`/`proved`, where the claim IS
    adjudicated. This test pins the distinction so neither drifts into the other.
    """
    r = compile_source("module M\nprove 1.0 = 2.0\n", "<test>")
    assert r.ok(), "the v1 meaning of `prove` is deliberately unchanged"
    assert any(o.kind == "theorem" for o in r.obligations)
    assert r.reasoning is not None
    assert r.reasoning.goal_status == {}, "`prove` creates no goal and proves nothing"
