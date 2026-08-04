"""Positive and negative parse tests for HML-L1."""

from __future__ import annotations

import pytest

from hamiltonian_lang import parse
from hamiltonian_lang.ast.nodes import (
    CheckStmt,
    ConceptDecl,
    Declaration,
    DistExpr,
    InferStmt,
    LawStmt,
    ObjectiveStmt,
    Quantifier,
    RequireStmt,
)
from hamiltonian_lang.types import (
    Dimension,
    MatrixType,
    QuantityType,
    ScalarType,
    VectorType,
)


def p(src: str):
    module, bag = parse(src)
    assert bag.ok(), bag.render()
    return module


# -- positive ------------------------------------------------------------


def test_module_declaration():
    m = p("module Demo\nvar x : Real")
    assert m.name == "Demo"


def test_declaration_kinds():
    m = p(
        "var a : Real\nparam b : PositiveReal\nconst c : Real = 1\n"
        "obs d : Natural = 7\nindex i : Natural\nrv e : RandomVariable[Real]"
    )
    decls = [s for s in m.statements if isinstance(s, Declaration)]
    assert [d.kind for d in decls] == ["var", "param", "const", "obs", "index", "rv"]
    assert decls[3].value is not None


@pytest.mark.parametrize(
    "src,expected",
    [
        ("var x : Real", ScalarType("Real")),
        ("var x : Probability", ScalarType("Probability")),
        ("var x : Vector[Real, N]", VectorType(ScalarType("Real"), "N")),
        ("var x : Matrix[Real, M, P]", MatrixType(ScalarType("Real"), "M", "P")),
        ("var x : Quantity[Mass]", QuantityType(Dimension.of(Mass=1))),
        (
            "var x : Quantity[Length / Time]",
            QuantityType(Dimension.of(Length=1, Time=-1)),
        ),
        (
            "var x : Quantity[Mass * Length^2 / Time^2]",
            QuantityType(Dimension.of(Mass=1, Length=2, Time=-2)),
        ),
    ],
)
def test_type_parsing(src, expected):
    m = p(src)
    assert m.statements[0].declared_type == expected


def test_law_with_conditioning():
    m = p("law y | x beta ~ Normal(location := mu, scale := sigma)")
    law = m.statements[0]
    assert isinstance(law, LawStmt)
    assert law.target == "y"
    assert [g.name for g in law.given] == ["x", "beta"]
    assert isinstance(law.distribution, DistExpr)
    assert law.distribution.family == "Normal"
    assert law.distribution.arg("scale") is not None


def test_law_roles_distinguished():
    m = p(
        "prior a ~ Normal(location := m, scale := s)\n"
        "likelihood b ~ Normal(location := m, scale := s)\n"
        "law c ~ Normal(location := m, scale := s)"
    )
    assert [s.role for s in m.statements] == ["prior", "likelihood", "law"]


def test_quantifier_nesting_is_structural():
    a = p("require forall x : Real . exists y : Real . y > x").statements[0]
    b = p("require exists y : Real . forall x : Real . y > x").statements[0]
    assert isinstance(a, RequireStmt) and isinstance(b, RequireStmt)
    outer_a, outer_b = a.proposition, b.proposition
    assert isinstance(outer_a, Quantifier) and isinstance(outer_b, Quantifier)
    assert outer_a.kind == "forall" and outer_a.body.kind == "exists"
    assert outer_b.kind == "exists" and outer_b.body.kind == "forall"


def test_operator_precedence():
    from hamiltonian_lang.backends.hml import render_expr

    m = p("def f := 1 + 2 * 3 ^ 2")
    assert render_expr(m.statements[0].body) == "1 + 2 * 3 ^ 2"
    m2 = p("def f := (1 + 2) * 3")
    assert render_expr(m2.statements[0].body) == "(1 + 2) * 3"


def test_unary_minus_and_power_right_assoc():
    from hamiltonian_lang.backends.hml import render_expr

    m = p("def f := 2 ^ 3 ^ 2")
    assert render_expr(m.statements[0].body) == "2 ^ 3 ^ 2"


def test_concept_block():
    m = p(
        "concept F\n"
        "    parameter location : Real\n"
        "    transform standardise(u : Real) := (u - location) / scale\n"
        "    invariant ok := scale > 0\n"
        "end"
    )
    c = m.statements[0]
    assert isinstance(c, ConceptDecl)
    assert [x.kind for x in c.members] == ["parameter", "transform", "invariant"]
    assert c.members[1].param_names() == ["u"]
    assert c.members[1].params == [("u", ScalarType("Real"))]


def test_concept_transform_parameter_may_be_typed():
    """Governing principle 1: every object has a type, including a transform binder."""
    m = p(
        "concept F\n"
        "    parameter location : Real\n"
        "    transform standardise(x : Real) := x - location\n"
        "    invariant ok := location = location\n"
        "end"
    )
    tr = m.statements[0].members[1]
    assert tr.params == [("x", ScalarType("Real"))]


def test_check_dimension_with_assertion():
    m = p("check dimension e = Mass * Length^2 / Time^2")
    st = m.statements[0]
    assert isinstance(st, CheckStmt)
    assert st.check_kind == "dimension"
    # Dimensions render in a canonical (alphabetical, numerator-then-denominator)
    # order, so 'Mass * Length^2 / Time^2' normalises to this form.
    assert st.expected == "Length^2 * Mass / Time^2"


def test_comments_and_blank_lines_ignored():
    m = p("# a comment\n\nvar x : Real  # trailing\n\n\nvar y : Real\n")
    assert len([s for s in m.statements if isinstance(s, Declaration)]) == 2


def test_infer_and_objective_and_solve():
    m = p("infer posterior a b\nminimise x ^ 2\nsolve x y")
    assert isinstance(m.statements[0], InferStmt)
    assert m.statements[0].query == "posterior"
    assert isinstance(m.statements[1], ObjectiveStmt)
    assert m.statements[1].direction == "minimise"
    assert [t.name for t in m.statements[2].targets] == ["x", "y"]


def test_unicode_identifiers_fold_to_ascii_with_warning():
    module, bag = parse("param μ : Real")
    assert bag.ok()
    assert module.statements[0].name == "mu"
    assert "HML-L102" in bag.codes()


def test_micro_sign_and_greek_mu_fold_identically():
    a, _ = parse("param µ : Real")  # MICRO SIGN
    b, _ = parse("param μ : Real")  # GREEK SMALL LETTER MU
    assert a.statements[0].name == b.statements[0].name == "mu"


# -- negative ------------------------------------------------------------


def errs(src: str) -> list[str]:
    _, bag = parse(src)
    return [d.code for d in bag.errors]


def test_positional_distribution_arguments_rejected():
    assert "HML-P234" in errs("law x ~ Normal(mu, sigma)")


def test_mixed_labelled_and_positional_rejected():
    assert "HML-P232" in errs("def f := g(a := 1, 2)")


def test_duplicate_role_rejected():
    assert "HML-P235" in errs("law x ~ Normal(scale := a, scale := b)")


def test_law_without_tilde_rejected():
    assert "HML-P208" in errs("law x Normal(scale := a)")


def test_definition_requires_walrus():
    assert "HML-P207" in errs("def f = 1")


def test_untyped_quantifier_rejected():
    assert "HML-P236" in errs("require forall x . x > 0")


def test_quantifier_without_dot_rejected():
    assert "HML-P237" in errs("require forall x : Real x > 0")


def test_chained_comparison_rejected():
    assert "HML-P230" in errs("require 0 < x < 1")


def test_keyword_as_name_rejected():
    assert "HML-P202" in errs("var law : Real")


def test_unknown_statement_head_rejected():
    assert "HML-P205" in errs("wibble x : Real")


def test_two_statements_on_one_line_rejected():
    assert "HML-P204" in errs("var x : Real var y : Real")


def test_unnamed_concept_invariant_reported_precisely():
    """`invariant scale > 0` consumes the name as the start of the expression. The
    diagnostic must say that, not report a stray operator further along the line."""
    _, bag = parse("concept F\n    invariant scale > 0\nend")
    d = next(x for x in bag.errors if x.code == "HML-P213")
    assert "must be named" in d.message
    assert d.correction.startswith("invariant <name> :=")


def test_unclosed_concept_reported():
    assert "HML-P210" in errs("concept F\n    parameter a : Real")


def test_non_ascii_character_rejected():
    assert "HML-L101" in errs("var x ≡ Real")


def test_unknown_base_dimension_rejected():
    assert "HML-D501" in errs("var x : Quantity[Fluffiness]")


def test_parse_error_does_not_cascade():
    """One bad line must not poison the lines after it."""
    module, bag = parse("var x : Real\nlaw y ~ Normal(1, 2)\nvar z : Real")
    assert len([d for d in bag.errors]) == 1
    names = [s.name for s in module.statements if isinstance(s, Declaration)]
    assert names == ["x", "z"]


# -- termination ---------------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        "ℝ",                    # DOUBLE-STRUCK CAPITAL R
        "var x : ℝ",
        "x ∈ ℝ",           # ELEMENT OF
        "variable (theta : ℝ)",  # verbatim line from the Lean backend
        "ℕ ℤ ℚ",      # N, Z, Q
        "def f := ∫ x",         # INTEGRAL
        "中文",              # CJK letters
        "\U0001d70b",                # MATHEMATICAL ITALIC SMALL PI
    ],
)
def test_lexer_terminates_on_unfolded_non_ascii_letters(src):
    """The lexer must never consume zero characters.

    `str.isalpha()` is true for every Unicode letter, so characters with no ASCII
    spelling were dispatched into the identifier routine, which consumed nothing and
    left the caller re-dispatching on the same character forever. Any model output
    containing a mathematical symbol would have hung the evaluation harness. (D-019.)
    """
    module, bag = parse(src)
    assert not bag.ok(), "expected a lexical error rather than silent acceptance"
    assert "HML-L101" in bag.codes()


def test_lean_backend_output_does_not_hang_the_parser():
    """Regression for the exact path that surfaced D-019: the Lean renderer emits real
    Lean, which contains non-ASCII type names, and the audit fed that back in."""
    import pathlib

    from hamiltonian_lang import compile_source
    from hamiltonian_lang.backends import render

    r = compile_source(pathlib.Path("examples/statistics/bayesian_coin.hml").read_text())
    text = render("lean", r.module, r.symbols).text
    back = compile_source(text)          # must terminate; correctness is not claimed
    assert not back.ok(), "Lean is not HML-L1 and must not parse as if it were"
