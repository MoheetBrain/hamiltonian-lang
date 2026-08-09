"""Binder abstraction and instantiation.

The single most important test here is
:func:`test_abstract_reproduces_the_resolvers_own_numbering`. HML's identity is locally
nameless, so ``forall_intro`` must build a term whose binder and bound references carry the
depths the *resolver* would have assigned to the same text. If that ever drifts, the rule
starts rejecting valid steps (or, worse, accepting terms that are not what they read as),
and it would drift silently — the kernel would simply report "the stated conclusion is not
what forall_intro yields" and blame the author.

So the test does not assert a hand-written expectation. It compiles the quantified
statement from source and requires the constructed term to be canonically identical to it.
The resolver is the oracle.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import AssumeStmt, GoalStmt, Quantifier, Ref, walk
from hamiltonian_lang.backends.canonical import expr_identity
from hamiltonian_lang.reasoning.binders import (
    CaptureError,
    abstract,
    free_symbols,
    instantiate,
    occurs_free,
)


def _compile(src: str):
    r = compile_source(src, "<binders>")
    assert r.ok(), [str(d) for d in r.diagnostics]
    return r


def _premise_and_goal(decls: str, premise: str, quantified: str):
    r = _compile(f"module B\n{decls}\nassume a1 : {premise}\ngoal g1 : {quantified}\n")
    prem = next(s.proposition for s in r.module.statements if isinstance(s, AssumeStmt))
    goal = next(s.proposition for s in r.module.statements if isinstance(s, GoalStmt))
    return prem, goal


#: (declarations, premise, quantified form, eigenvariable). Chosen to cover the cases the
#: re-depthing must get right: a flat body, a free module constant that must NOT move,
#: nested binders that must all descend, a mixed quantifier prefix, and a second free
#: module variable that stays free.
CASES = [
    ("var n : Natural", "n + 0.0 = n", "forall n : Natural . n + 0.0 = n", "n"),
    (
        "var n : Natural\nconst c : Natural",
        "n + c = n",
        "forall n : Natural . n + c = n",
        "n",
    ),
    (
        "var n : Natural",
        "forall y : Natural . n + y = y + n",
        "forall n : Natural . forall y : Natural . n + y = y + n",
        "n",
    ),
    (
        "var n : Natural",
        "exists y : Natural . n + y = y",
        "forall n : Natural . exists y : Natural . n + y = y",
        "n",
    ),
    (
        "var n : Real\nvar m : Real",
        "n * m = m * n",
        "forall n : Real . n * m = m * n",
        "n",
    ),
]


@pytest.mark.parametrize("decls,premise,quantified,eigen", CASES)
def test_abstract_reproduces_the_resolvers_own_numbering(decls, premise, quantified, eigen):
    prem, goal = _premise_and_goal(decls, premise, quantified)
    sid = next(
        x.symbol_id for x in walk(prem) if isinstance(x, Ref) and x.name == eigen
    )
    built = abstract(prem, sid, kind="forall", var_type=goal.var_type)
    assert expr_identity(built) == expr_identity(goal), (
        "the constructed quantifier is not what the resolver builds from the same text; "
        "forall_intro would reject valid steps"
    )


@pytest.mark.parametrize("decls,premise,quantified,eigen", CASES)
def test_instantiate_inverts_abstract(decls, premise, quantified, eigen):
    """Round trip: abstracting then instantiating at the same variable is the identity."""
    prem, goal = _premise_and_goal(decls, premise, quantified)
    ref = next(x for x in walk(prem) if isinstance(x, Ref) and x.name == eigen)
    built = abstract(prem, ref.symbol_id, kind="forall", var_type=goal.var_type)
    assert isinstance(built, Quantifier)
    assert expr_identity(instantiate(built, ref)) == expr_identity(prem)


def test_abstract_refuses_an_already_bound_variable():
    """Generalising over something already bound is meaningless, not merely unusual."""
    _, goal = _premise_and_goal(
        "var n : Natural", "n + 0.0 = n", "forall n : Natural . n + 0.0 = n"
    )
    inner = next(
        x.symbol_id for x in walk(goal) if isinstance(x, Ref) and x.symbol_id.depth > 0
    )
    with pytest.raises(CaptureError):
        abstract(goal.body, inner, kind="forall", var_type=goal.var_type)


def test_instantiate_refuses_a_capturing_term():
    """A term mentioning a bound name is refused rather than substituted.

    This is the classic unsoundness: the term means something relative to a binder that
    does not enclose the substitution site, so inserting it silently changes what it says.
    """
    r = _compile(
        "module B\n"
        "goal g1 : forall x : Natural . x >= 0.0\n"
        "goal g2 : forall y : Natural . y >= 1.0\n"
    )
    outer = next(
        s.proposition for s in r.module.statements if getattr(s, "label", None) == "g1"
    )
    other = next(
        s.proposition for s in r.module.statements if getattr(s, "label", None) == "g2"
    )
    bound_ref = next(
        x for x in walk(other) if isinstance(x, Ref) and x.symbol_id.depth > 0
    )
    with pytest.raises(CaptureError):
        instantiate(outer, bound_ref)


def test_free_symbols_sees_module_level_names_only():
    prem, goal = _premise_and_goal(
        "var n : Natural\nconst c : Natural",
        "n + c = n",
        "forall n : Natural . n + c = n",
    )
    n_sid = next(x.symbol_id for x in walk(prem) if isinstance(x, Ref) and x.name == "n")
    c_sid = next(x.symbol_id for x in walk(prem) if isinstance(x, Ref) and x.name == "c")
    assert occurs_free(prem, n_sid)
    assert occurs_free(prem, c_sid)
    # Once abstracted, `n` is bound and only `c` remains free.
    built = abstract(prem, n_sid, kind="forall", var_type=goal.var_type)
    assert not occurs_free(built, n_sid)
    assert occurs_free(built, c_sid)
    assert free_symbols(built) == {c_sid.canonical()}


def test_alpha_renaming_the_binder_does_not_change_identity():
    """The theorem is the same theorem whatever the bound variable is called."""
    a = _compile("module B\ngoal g : forall n : Natural . n >= 0.0\n")
    b = _compile("module B\ngoal g : forall zzz : Natural . zzz >= 0.0\n")
    pa = next(s.proposition for s in a.module.statements if isinstance(s, GoalStmt))
    pb = next(s.proposition for s in b.module.statements if isinstance(s, GoalStmt))
    assert expr_identity(pa) == expr_identity(pb)
