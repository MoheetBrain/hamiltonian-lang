"""Unsupported constructs must fail loudly, in all four surfaces, identically.

``CLAUDE.md`` names the worst failure mode in this codebase: a backend that silently
omits a construct and produces authoritative-looking output that is wrong. A renderer
has the same obligation. Every object below is a legal ``Module`` in the sense that it
can be built from ``ast/nodes.py``, and outside the frozen subset in the sense that no
surface can write it down. Each must raise :class:`UnsupportedConstruct` in every
candidate -- never render, never round-trip, never silently lose the offending part.

The uniformity matters as much as the rejection. A subset that differed per candidate
would not be a subset, and the tournament would be comparing surfaces on different
languages.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from evaluation.syntax_acquisition.core import CANDIDATES, UnsupportedConstruct

from hamiltonian_lang.ast.nodes import (
    Arg,
    BinOp,
    Call,
    CheckStmt,
    Comparison,
    ConceptDecl,
    ConceptMember,
    Declaration,
    DefineStmt,
    DistExpr,
    Expr,
    InferStmt,
    LawStmt,
    Literal,
    LogicalOp,
    Module,
    ModuleDecl,
    ProveStmt,
    Quantifier,
    Ref,
    RequireStmt,
    SolveStmt,
    Statement,
    UnaryOp,
)
from hamiltonian_lang.types import (
    FunctionType,
    MatrixType,
    PropositionType,
    ScalarType,
    TensorType,
    VectorType,
)

REAL = ScalarType("Real")
CANDIDATE_IDS = tuple(sorted(CANDIDATES))


def _module(*statements: Statement, name: str = "Unsupported") -> Module:
    return Module(name=name, statements=[ModuleDecl(name=name), *statements])


def _true() -> Literal:
    return Literal(value=True, raw="true")


class _InventedStatement(Statement):
    """A statement node no surface knows about."""


@dataclass
class _InventedExpr(Expr):
    """An expression node no surface knows about."""

    tag: str = "?"


CASES: dict[str, Module] = {
    # -- fields that exist in the IR but have no surface production ------
    "check_kind 'type'": _module(
        CheckStmt(check_kind="type", subject=Ref(name="a_"))
    ),
    "labelled require": _module(
        RequireStmt(proposition=_true(), label="positivity")
    ),
    "labelled prove": _module(ProveStmt(proposition=_true(), label="lemma_1")),
    # -- literals --------------------------------------------------------
    "negative integer literal": _module(
        Declaration(kind="const", name="k_", declared_type=REAL, value=Literal(value=-3, raw="-3"))
    ),
    "negative real literal": _module(
        Declaration(
            kind="const", name="k_", declared_type=REAL, value=Literal(value=-1.5, raw="-1.5")
        )
    ),
    "not-a-number literal": _module(
        Declaration(
            kind="const", name="k_", declared_type=REAL,
            value=Literal(value=float("nan"), raw="nan"),
        )
    ),
    "infinite literal": _module(
        Declaration(
            kind="const", name="k_", declared_type=REAL,
            value=Literal(value=float("inf"), raw="inf"),
        )
    ),
    "string literal": _module(
        Declaration(kind="const", name="k_", declared_type=REAL, value=Literal(value="x"))  # type: ignore[arg-type]
    ),
    # -- types -----------------------------------------------------------
    "untyped declaration": _module(
        Declaration(kind="param", name="a_", declared_type=None)
    ),
    "empty Tensor shape": _module(
        Declaration(kind="param", name="t_", declared_type=TensorType(REAL, ()))
    ),
    "Tensor with an unknown extent": _module(
        Declaration(kind="param", name="t_", declared_type=TensorType(REAL, (2, None)))
    ),
    "Matrix with unknown rows and known columns": _module(
        Declaration(kind="param", name="m_", declared_type=MatrixType(REAL, None, 3))
    ),
    "Function with an empty domain": _module(
        Declaration(kind="param", name="f_", declared_type=FunctionType((), REAL))
    ),
    # -- binders ---------------------------------------------------------
    "untyped quantifier binder": _module(
        RequireStmt(
            proposition=Quantifier(kind="forall", var="x_", var_type=None, body=_true())
        )
    ),
    "invented quantifier kind": _module(
        RequireStmt(
            proposition=Quantifier(kind="exists_many", var="x_", var_type=REAL, body=_true())
        )
    ),
    "untyped transform parameter": _module(
        ConceptDecl(
            name="C",
            members=[
                ConceptMember(kind="transform", name="t", params=[("x", None)], body=Ref(name="x")),
                ConceptMember(kind="invariant", name="i", body=_true()),
            ],
        )
    ),
    # -- operators and heads --------------------------------------------
    "invented binary operator": _module(
        DefineStmt(name="z_", body=BinOp(op="%", left=Ref(name="a_"), right=Ref(name="b_")))
    ),
    "invented comparison operator": _module(
        RequireStmt(proposition=Comparison(op="~=", left=Ref(name="a_"), right=Ref(name="b_")))
    ),
    "invented logical operator": _module(
        RequireStmt(proposition=LogicalOp(op="nand", left=_true(), right=_true()))
    ),
    "invented unary operator": _module(
        DefineStmt(name="z_", body=UnaryOp(op="!", operand=Ref(name="a_")))
    ),
    "invented declaration kind": _module(
        Declaration(kind="letx", name="a_", declared_type=REAL)
    ),
    "invented law role": _module(
        LawStmt(
            role="posterior", target="x_",
            distribution=DistExpr(family="Normal", args=[Arg("scale", Ref(name="s_"))]),
        )
    ),
    "invented inference query": _module(InferStmt(query="mode", targets=[Ref(name="a_")])),
    "invented concept member kind": _module(
        ConceptDecl(name="C", members=[ConceptMember(kind="lemma", name="l", body=_true())])
    ),
    # -- shape -----------------------------------------------------------
    "solve with no targets": _module(SolveStmt(targets=[])),
    "infer with no targets": _module(InferStmt(query="posterior", targets=[])),
    "index with no subscripts": _module(
        DefineStmt(name="z_", body=__import__(
            "hamiltonian_lang.ast.nodes", fromlist=["Index"]
        ).Index(base=Ref(name="v_"), indices=[]))
    ),
    "law with no distribution": _module(LawStmt(role="law", target="x_", distribution=None)),
    "repeated distribution role": _module(
        LawStmt(
            role="law", target="x_",
            distribution=DistExpr(
                family="Normal",
                args=[Arg("scale", Ref(name="s_")), Arg("scale", Ref(name="s_"))],
            ),
        )
    ),
    "bare distribution in expression position": _module(
        DefineStmt(name="z_", body=DistExpr(family="Beta", args=[]))
    ),
    "role-labelled ordinary call": _module(
        DefineStmt(
            name="z_",
            body=Call(callee="f", args=[Arg("x", Ref(name="a_"))]),  # type: ignore[list-item]
        )
    ),
    # -- names -----------------------------------------------------------
    "name reserved in HML-L1": _module(
        Declaration(kind="param", name="law", declared_type=REAL)
    ),
    "name reserved only in candidate B": _module(
        Declaration(kind="param", name="all", declared_type=REAL)
    ),
    "non-ASCII name": _module(
        Declaration(kind="param", name="thetaθ", declared_type=REAL)
    ),
    "name starting with a digit": _module(
        Declaration(kind="param", name="1a", declared_type=REAL)
    ),
    "empty name": _module(Declaration(kind="param", name="", declared_type=REAL)),
    "non-ASCII module name": Module(name="Mé", statements=[]),
    # -- unknown node classes -------------------------------------------
    "invented statement node": _module(_InventedStatement()),
    "invented expression node": _module(
        RequireStmt(proposition=_InventedExpr(tag="a_"))
    ),
}


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
@pytest.mark.parametrize("label", sorted(CASES))
def test_unsupported_constructs_raise_in_every_surface(candidate_id, label):
    with pytest.raises(UnsupportedConstruct):
        CANDIDATES[candidate_id].render(CASES[label])


@pytest.mark.parametrize("label", sorted(CASES))
def test_the_four_surfaces_agree_on_what_is_unsupported(label):
    """The subset is a property of the phase, not of any one candidate."""
    outcomes = {}
    for cid, cand in sorted(CANDIDATES.items()):
        try:
            cand.render(CASES[label])
            outcomes[cid] = "rendered"
        except UnsupportedConstruct:
            outcomes[cid] = "rejected"
    assert set(outcomes.values()) == {"rejected"}, f"{label}: {outcomes}"


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
@pytest.mark.parametrize("label", sorted(CASES))
def test_an_unsupported_construct_never_round_trips(candidate_id, label):
    """Not merely 'raises' -- it must never produce text at all.

    A renderer that emitted the rest of the module and dropped the offending statement
    would still 'fail' some later check, but it would have produced authoritative-looking
    output on the way. That is the failure mode being excluded.
    """
    from evaluation.syntax_acquisition.core import round_trip

    outcome = round_trip(CANDIDATES[candidate_id], CASES[label], label)
    assert not outcome.ok
    assert outcome.stage == "render", f"{label}: rejected at {outcome.stage}, not at render"
    assert outcome.rendered == "", f"{label}: emitted text before failing"


def test_a_supported_construct_is_not_caught_by_the_same_net():
    """Guard the guard: the validator must not simply reject everything."""
    from evaluation.syntax_acquisition.core import validate_supported

    good = _module(
        Declaration(kind="param", name="a_", declared_type=REAL),
        Declaration(kind="param", name="v_", declared_type=VectorType(REAL, None)),
        DefineStmt(name="z_", declared_type=PropositionType(), body=_true()),
    )
    validate_supported(good, "test")
    for cand in CANDIDATES.values():
        assert cand.render(good)
