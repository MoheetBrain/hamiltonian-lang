"""Calculus V0 — a replay, not a lookup table.

The property under test is that **the proposal is never trusted**. Every negative below is
a plausible-looking derivative that a CAS, a model or a tired author might produce, and the
replay has to reject each one on its own arithmetic rather than on a list of known-bad
answers.

The domain condition gets equal weight. `d(1/x)` is only `-1/x^2` where `x != 0`, and a
certificate that forgets to say so is exactly the kind of authoritative-looking wrong
output this project treats as the worst failure mode.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import EvidenceStatus
from hamiltonian_lang.libraries import calculus

HEAD = "module C\nvar x : Real\n"
NONZERO = "assume a0 : x != 0.0\n"


def _compile(src: str):
    return compile_source(src, "<calc>")


def _status(src: str, label: str = "e1") -> str:
    r = _compile(src)
    if r.reasoning is None:
        return "<not reached>"
    return r.reasoning.evidence_status.get(label, "<absent>")


def _evidence(claim: str, *, prelude: str = "") -> str:
    return HEAD + prelude + f"evidence e1 : entails {claim} by derivative_trace_v1()\n"


# --- positive: the primitive rules ------------------------------------------


@pytest.mark.parametrize(
    "claim,rule",
    [
        ("derivative(3.0, x : Real) = 0.0", "derivative_constant"),
        ("derivative(x, x : Real) = 1.0", "derivative_variable"),
        ("derivative(x + x, x : Real) = 1.0 + 1.0", "derivative_sum"),
        ("derivative(x * x, x : Real) = 1.0 * x + x * 1.0", "derivative_product"),
        ("derivative(x ^ 3.0, x : Real) = 3.0 * x ^ 2.0 * 1.0", "derivative_integer_power"),
    ],
)
def test_each_primitive_rule_replays(claim, rule):
    assert rule in calculus.PRIMITIVE_RULES
    assert _status(_evidence(claim)) == EvidenceStatus.VALID, claim


def test_the_gold10_quotient_case_replays_under_a_nonzero_denominator():
    claim = "derivative(1.0 / x, x : Real) = (0.0 - 1.0) / (x ^ 2.0)"
    r = _compile(_evidence(claim, prelude=NONZERO))
    assert r.ok(), [str(d) for d in r.diagnostics]
    assert r.reasoning.evidence_status["e1"] == EvidenceStatus.VALID


def test_the_replay_reports_the_rules_and_identities_it_used():
    """A normalisation nobody can inspect is a simplifier. This one names its steps."""
    from hamiltonian_lang.ast.nodes import GoalStmt

    src = HEAD + "goal g1 : derivative(1.0 / x, x : Real) = (0.0 - 1.0) / (x ^ 2.0)\n"
    r = _compile(src)
    claim = next(s.proposition for s in r.module.statements if isinstance(s, GoalStmt))
    _, conditions, detail = calculus.check_derivative_claim(claim)
    assert "derivative_quotient" in detail["rules"]
    for identity in ("zero_mul", "one_mul", "zero_sub"):
        assert identity in detail["identities"], identity
    assert len(conditions) == 1


# --- the domain condition ---------------------------------------------------


def test_the_quotient_rule_requires_a_nonzero_denominator():
    claim = "derivative(1.0 / x, x : Real) = (0.0 - 1.0) / (x ^ 2.0)"
    r = _compile(_evidence(claim))
    assert not r.ok()
    assert r.reasoning.evidence_status["e1"] == EvidenceStatus.REJECTED
    assert any("x != 0" in str(d) for d in r.diagnostics)


def test_the_domain_condition_is_an_ordinary_obligation():
    claim = "derivative(1.0 / x, x : Real) = (0.0 - 1.0) / (x ^ 2.0)"
    r = _compile(_evidence(claim))
    reasons = {o.reason for o in r.reasoning.obligations}
    assert "differentiation_domain_condition" in reasons


def test_the_condition_is_on_the_original_denominator_not_the_squared_one():
    """`x != 0` is what the rule requires; `x^2 != 0` is a consequence of it.

    Recording the consequence in place of the premise would be a subtler kind of wrong --
    equivalent here, and not equivalent for a denominator that can vanish differently.
    """
    from hamiltonian_lang.ast.nodes import GoalStmt
    from hamiltonian_lang.backends.hml import render_expr

    src = HEAD + "goal g1 : derivative(1.0 / x, x : Real) = (0.0 - 1.0) / (x ^ 2.0)\n"
    r = _compile(src)
    claim = next(s.proposition for s in r.module.statements if isinstance(s, GoalStmt))
    _, conditions, _ = calculus.check_derivative_claim(claim)
    assert [render_expr(c) for c in conditions] == ["x != 0.0"]


# --- negative: wrong answers -----------------------------------------------


@pytest.mark.parametrize(
    "claim",
    [
        # Sign error -- the classic 1/x slip.
        "derivative(1.0 / x, x : Real) = 1.0 / (x ^ 2.0)",
        # Wrong constant derivative.
        "derivative(3.0, x : Real) = 1.0",
        # Wrong variable derivative.
        "derivative(x, x : Real) = 0.0",
        # Product rule replaced by the (false) product of derivatives.
        "derivative(x * x, x : Real) = 1.0 * 1.0",
        # Power rule off by one.
        "derivative(x ^ 3.0, x : Real) = 3.0 * x ^ 3.0 * 1.0",
    ],
)
def test_an_incorrect_derivative_is_rejected(claim):
    assert _status(_evidence(claim, prelude=NONZERO)) == EvidenceStatus.REJECTED, claim


def test_differentiating_with_respect_to_the_wrong_variable_is_rejected():
    """`d/dy (x)` is 0, not 1. A binder is not decoration."""
    src = (
        "module C\nvar x : Real\nvar y : Real\n"
        "evidence e1 : entails derivative(x, y : Real) = 1.0 by derivative_trace_v1()\n"
    )
    assert _status(src) == EvidenceStatus.REJECTED


def test_a_free_variable_is_constant_with_respect_to_the_binder():
    src = (
        "module C\nvar x : Real\nvar y : Real\n"
        "evidence e1 : entails derivative(y, x : Real) = 0.0 by derivative_trace_v1()\n"
    )
    assert _status(src) == EvidenceStatus.VALID


# --- negative: malformed certificates ---------------------------------------


def test_a_claim_that_is_not_an_equality_is_rejected():
    assert _status(_evidence("derivative(x, x : Real) > 0.0")) == EvidenceStatus.REJECTED


def test_a_claim_with_no_derivative_on_either_side_is_rejected():
    assert _status(_evidence("x + 0.0 = x")) == EvidenceStatus.REJECTED


def test_the_checker_takes_no_arguments():
    """It re-derives the answer; an argument could only be an attempt to steer it."""
    src = HEAD + NONZERO + (
        "evidence e1 : entails derivative(x, x : Real) = 1.0 "
        "by derivative_trace_v1(hint := 1.0)\n"
    )
    r = _compile(src)
    assert not r.ok()
    assert any("takes no arguments" in str(d) for d in r.diagnostics)


def test_an_unsupported_form_fails_closed():
    """Outside the fragment is a refusal, never "differentiate it as a constant"."""
    src = (
        "module C\nvar x : Real\nvar n : Real\n"
        "evidence e1 : entails derivative(x ^ n, x : Real) = 0.0 by derivative_trace_v1()\n"
    )
    assert _status(src) == EvidenceStatus.REJECTED


def test_the_chain_rule_is_not_claimed():
    """V0 does not implement it, and the fragment says so rather than guessing."""
    assert "derivative_chain" not in calculus.PRIMITIVE_RULES


def test_differentiate_raises_rather_than_guessing_outside_the_fragment():
    from hamiltonian_lang.ast.nodes import GoalStmt

    src = "module C\nvar x : Real\ngoal g1 : derivative(x, x : Real) = 1.0\n"
    r = _compile(src)
    claim = next(s.proposition for s in r.module.statements if isinstance(s, GoalStmt))
    d = claim.left
    from hamiltonian_lang.ast.nodes import MembershipExpr

    with pytest.raises(calculus.DifferentiationError):
        calculus.differentiate(
            MembershipExpr(element=d.body, collection=d.body), d.symbol_id
        )


# --- normalisation ----------------------------------------------------------


def test_normalisation_terminates_and_reports_its_identities():
    from hamiltonian_lang.ast.nodes import BinOp, Literal, Ref

    x = Ref(name="x")
    term = BinOp(
        op="-",
        left=BinOp(op="*", left=Literal(value=0.0, raw="0.0"), right=x),
        right=BinOp(
            op="*", left=Literal(value=1.0, raw="1.0"), right=Literal(value=1.0, raw="1.0")
        ),
    )
    out, used = calculus.normalise(term)
    assert set(used) <= {"zero_mul", "one_mul", "mul_one", "zero_sub", "add_zero"}
    assert "zero_sub" in used
    # Re-normalising a normal form is a no-op: the fixed point is really fixed.
    again, used_again = calculus.normalise(out)
    assert used_again == ()


def test_no_untrusted_oracle_is_imported_on_the_calculus_path():
    """The replay must not become a wrapper around a CAS.

    Asserted over the import graph rather than the source text: the module *discusses*
    SymPy at length in its docstring, and a substring check would either fail on the prose
    or be silenced into uselessness. What matters is whether the code can call it.
    """
    import ast as pyast
    import inspect

    from hamiltonian_lang.libraries import algebra
    from hamiltonian_lang.reasoning.certificates import library

    banned = {"sympy", "scipy", "numpy"}
    for module in (calculus, algebra, library):
        tree = pyast.parse(inspect.getsource(module))
        imported: set[str] = set()
        for node in pyast.walk(tree):
            if isinstance(node, pyast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, pyast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & banned), (
            f"{module.__name__} imports {imported & banned}; the trusted replay would "
            f"then rest on an untrusted oracle"
        )
