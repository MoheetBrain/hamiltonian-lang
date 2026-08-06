"""The AST partiality scanner: positive and negative controls.

The guard this replaces detected division by a **bare binder** and nothing else. It
therefore admitted `force / area` where `area` is a module-level `Quantity[Length^2]` — the
case that actually cost the corpus a task, and one that cannot be repaired by adding a
guard, because `require area != 0` does not compile (HML-D502).

Every negative test below is a partiality the previous guard would have waved through.
"""

from __future__ import annotations

import pytest
from evaluation.corpus_governance.partiality import (
    Establishment,
    Verdict,
    scan_module,
    scan_source,
)
from evaluation.corpus_governance.v2_corpus import PROOF_CORPUS

# --- positive controls: safe code must not be rejected --------------------------------
#
# A scanner that rejects everything is not conservative, it is useless. These pin the
# other direction.

SAFE = {
    "literal denominator": "module M\nvar x : Real\ndef f : Real := x / 2\n",
    "positive binder": (
        "module M\nconst e : Real = 5\ndef f(mu : PositiveReal) : Real := e / mu\n"),
    "positive const denominator": (
        "module M\nconst k : Real = 4\nvar x : Real\ndef f : Real := x / k\n"),
    "explicit nonzero requirement": (
        "module M\nvar y : Real\nrequire y != 0\nvar x : Real\ndef f : Real := x / y\n"),
    "explicit positivity assumption": (
        "module M\nvar y : Real\nassume y > 0\nvar x : Real\ndef f : Real := x / y\n"),
    "total body": "module M\nconst e : Real = 5\ndef f(mu : Real) : Real := e * mu\n",
    "sqrt of a non-negative": "module M\nvar x : NonNegativeReal\ndef f : Real := sqrt(x)\n",
    "log of a positive": "module M\nvar x : PositiveReal\ndef f : Real := log(x)\n",
    "product of positives as denominator": (
        "module M\nvar a : PositiveReal\nvar b : PositiveReal\nvar x : Real\n"
        "def f : Real := x / (a * b)\n"),
}


@pytest.mark.parametrize("label", sorted(SAFE))
def test_safe_code_is_accepted(label: str):
    report = scan_source(SAFE[label], label)
    assert report.verdict is Verdict.ACCEPT, report.render()


# --- negative controls: each is a partiality the binder-only guard missed --------------

UNSAFE = {
    "binder denominator": (
        "module M\nconst e : Real = 5\ndef f(mu : Real) : Real := e / mu\n",
        "mu is a binder of type Real"),
    "module variable denominator": (
        "module M\nvar y : Real\nvar x : Real\ndef f : Real := x / y\n",
        "y is a var of type Real"),
    "dimensioned module variable": (
        "module M\nvar force : Quantity[Mass * Length / Time^2]\n"
        "var area : Quantity[Length^2]\n"
        "def p : Quantity[Mass / (Length * Time^2)] := force / area\n",
        "UNGUARDABLE"),
    "nested denominator": (
        "module M\nvar a : Real\nvar b : Real\nvar c : Real\n"
        "def f : Real := a / (b + c)\n",
        "compound denominator"),
    "denominator inside a larger expression": (
        "module M\nvar a : Real\nvar b : Real\ndef f : Real := (a + 1) * (a / b) - 3\n",
        "b is a var"),
    "partiality one definition deep": (
        "module M\nvar x : Real\nvar y : Real\ndef g : Real := x / y\n"
        "def h : Real := g + 1\n",
        "through definition g"),
    "partiality two definitions deep": (
        "module M\nvar x : Real\nvar y : Real\ndef g : Real := x / y\n"
        "def h : Real := g + 1\ndef k : Real := h * 2\n",
        "through definition h"),
    "negative power": (
        "module M\nvar x : Real\ndef f : Real := x ^ -1\n",
        "negative exponent is a division"),
    "fractional power": (
        "module M\nvar x : Real\ndef f : Real := x ^ 0.5\n",
        "fractional exponent requires a non-negative base"),
    "variable exponent": (
        "module M\nvar x : Real\nvar n : Real\ndef f : Real := x ^ n\n",
        "not a literal"),
    "tangent": (
        "module M\nvar x : Real\ndef f : Real := tan(x)\n",
        "cannot be established"),
    "division in an assumption": (
        "module M\nvar a : Real\nvar b : Real\nassume a / b > 1\n",
        "b is a var"),
    "division in a goal": (
        "module M\nvar a : Real\nvar b : Real\nprove a / b > 1\n",
        "b is a var"),
}


@pytest.mark.parametrize("label", sorted(UNSAFE))
def test_unsafe_code_is_rejected_with_a_risk_path(label: str):
    source, expected = UNSAFE[label]
    report = scan_source(source, label)
    assert report.verdict is Verdict.REJECT, f"{label} was accepted:\n{report.render()}"
    assert expected in report.render(), report.render()


def test_the_risk_path_names_each_step():
    """A verdict without a path is not actionable — this is the format the audit asked for."""
    report = scan_source(
        "module M\nvar force : Quantity[Mass * Length / Time^2]\n"
        "var area : Quantity[Length^2]\n"
        "def pressure : Quantity[Mass / (Length * Time^2)] := force / area\n", "dim")
    path = report.risks[0].path
    assert path[0] == "definition pressure"
    assert path[1] == "division denominator area"
    assert "area is a var of type Quantity[Length^2]" in path[2]
    assert report.risks[0].reason == "nonzero condition not established"
    assert report.risks[0].unguardable is True


def test_a_guard_established_after_the_use_does_not_count():
    """Facts are read in source order, as everything else in this corpus is."""
    late = scan_source(
        "module M\nvar y : Real\nvar x : Real\ndef f : Real := x / y\nrequire y != 0\n",
        "late guard")
    early = scan_source(
        "module M\nvar y : Real\nrequire y != 0\nvar x : Real\ndef f : Real := x / y\n",
        "early guard")
    assert late.verdict is Verdict.REJECT
    assert early.verdict is Verdict.ACCEPT


def test_a_binder_cannot_inherit_a_module_level_guard_by_shadowing():
    """`require mu != 0` at module scope must not vouch for a *binder* also called `mu`.

    The compiler closes this one first: shadowing is an error (D-006, HML-N302), so the
    source does not even compile. The scanner still discards binder facts on entry, because
    a guard whose correctness depends on another gate staying strict is not a guard.
    """
    with pytest.raises(ValueError, match="HML-N302"):
        scan_source("module M\nvar mu : Real\nrequire mu != 0\nconst e : Real = 5\n"
                    "def f(mu : Real) : Real := e / mu\n", "shadowed")

    unrelated = scan_source(
        "module M\nvar nu : Real\nrequire nu != 0\nconst e : Real = 5\n"
        "def f(mu : Real) : Real := e / mu\n", "unrelated guard")
    assert unrelated.verdict is Verdict.REJECT, unrelated.render()
    assert "mu is a binder" in unrelated.render()


def test_indexing_is_flagged_because_bounds_are_not_expressible():
    from hamiltonian_lang.ast.nodes import Comparison, Index, Literal, Module, Ref, RequireStmt

    module = Module(name="M", statements=[
        RequireStmt(proposition=Comparison(
            op=">", left=Index(base=Ref(name="v"), indices=[Literal(value=3)]),
            right=Literal(value=0)))])
    report = scan_module(module, "indexing")
    assert report.verdict is Verdict.REJECT
    assert "index bounds are not established" in report.render()


# --- establishment logic ---------------------------------------------------------------

def test_a_quantity_type_establishes_nothing():
    """`Quantity[Length^2]` carries no sign information at all, unlike `PositiveReal`."""
    from evaluation.corpus_governance.partiality import _Env, _establish

    from hamiltonian_lang.ast.nodes import Ref
    from hamiltonian_lang.types import Dimension, QuantityType, ScalarType

    env = _Env(types={"a": QuantityType(dimension=Dimension.of(Length=1)),
                      "p": ScalarType("PositiveReal")})
    assert _establish(Ref(name="a"), env) is Establishment.UNKNOWN
    assert _establish(Ref(name="p"), env) is Establishment.POSITIVE


# --- the corpus ------------------------------------------------------------------------

@pytest.mark.parametrize("task", PROOF_CORPUS, ids=lambda t: t.task_id)
def test_every_admitted_task_passes_the_scanner(task):
    report = scan_module(task.module, task.task_id)
    assert report.verdict is Verdict.ACCEPT, report.render()


def test_the_scanner_is_the_construction_gate():
    """Rejection happens at construction, so an inadmissible task cannot exist."""
    from evaluation.corpus_governance.canonical_v2 import (
        CanonicalAcq0TaskV2,
        Provenance,
        SchemaViolation,
        TaskFamily,
    )

    with pytest.raises(SchemaViolation, match="unestablished partial operation"):
        CanonicalAcq0TaskV2(
            task_id="t", family=TaskFamily.BINDING_DEPENDENCY,
            provenance=Provenance(author="t", created_utc="2026-01-01T00:00:00+00:00"),
            source="module M\nvar y : Real\nvar x : Real\ndef f : Real := x / y\n")


# --- fail-open closures found by the second independent review -------------------------

def test_a_concept_body_is_walked():
    """A division inside a `concept` transform was never reached.

    `scan_module` dispatched on statement type with a silent fall-through, so a module
    whose only division sat in a concept block printed the same ACCEPT line as a clean
    one — fail OPEN, and indistinguishable from safe.
    """
    unsafe = ("module ConceptGap\n\nconcept Ratio\n"
              "  parameter scale : Real\n"
              "  transform standardise(u : Real) := u / scale\n"
              "  invariant nonzero := scale > 0\n"
              "  example unit := Normal(location := 0, scale := 1)\n"
              "end\n")
    report = scan_source(unsafe, "concept")
    assert report.verdict is Verdict.REJECT, report.render()
    assert "concept Ratio" in report.render()
    assert "scale is a concept parameter of type Real" in report.render()

    safe = unsafe.replace("parameter scale : Real", "parameter scale : PositiveReal")
    assert scan_source(safe, "concept-safe").verdict is Verdict.ACCEPT


def test_an_unwired_statement_kind_stops_the_corpus():
    """"No branch exists" must not look like "nothing to walk"."""
    from dataclasses import dataclass

    from evaluation.corpus_governance.partiality import UnsupportedStatement, scan_module

    from hamiltonian_lang.ast.nodes import Module, Statement

    @dataclass
    class InventedStatement(Statement):
        pass

    with pytest.raises(UnsupportedStatement, match="no partiality branch"):
        scan_module(Module(name="M", statements=[InventedStatement()]), "invented")


def test_an_uninitialised_declaration_is_handled_not_waved_through():
    """`var x : Real` has no expression, which is different from having no branch."""
    report = scan_source("module M\nvar x : Real\n", "bare")
    assert report.verdict is Verdict.ACCEPT
    assert report.statements_walked == 2


def test_accept_reports_how_much_was_actually_walked():
    """ACCEPT could not distinguish "clean" from "never looked"."""
    report = scan_source("module M\nvar x : Real\ndef f : Real := x / 2\n", "counted")
    assert report.statements_walked == 3
    assert "3 statement(s) walked" in report.render()
    assert "1 partial-operation site(s) inspected" in report.render()
