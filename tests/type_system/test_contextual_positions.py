"""Which expression positions are checked *contextually*, and which are not.

D-023 part 2. The audit (`docs/evaluation/PHASE1_LEAD_AUDIT.md` §2) measured two of
roughly a dozen expression-bearing positions routing through ``TypeChecker.check``, and
recorded that the module docstring claimed more than that (defect C). This file is the
mechanical half of the corrected claim: the table in
``hamiltonian_lang.type_system.__init__``'s docstring is asserted here, position by
position, so neither the table nor the code can move without the other.

**Read the second half of this file as carefully as the first.** It asserts what is
*not* checked contextually. Those assertions exist so that "the checker is
bidirectional" cannot be said of this implementation without a test failing first.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.type_system import CheckedExpr, TypeChecker


def compile_hml(*lines: str):
    return compile_source("module M\n" + "\n".join(lines) + "\n", "<position-probe>")


def codes(*lines: str) -> list[str]:
    return [d.code for d in compile_hml(*lines).diagnostics.items]


@pytest.fixture
def recorded(monkeypatch):
    """Record every ``check`` call made while compiling a program.

    Instrumenting the method itself is what makes this an assertion about the *code
    path* rather than about an error code. A site could produce the right diagnostic
    from a hand-rolled comparison and still not be in checking mode; that is exactly the
    state ``DefineStmt`` was in.
    """
    seen: list[str] = []
    original = TypeChecker.check

    def spy(
        self,
        e,
        expected,
        *,
        role,
        code="HML-T460",
        note=None,
        message=None,
        lift_random=False,
    ):
        seen.append(role)
        return original(
            self,
            e,
            expected,
            role=role,
            code=code,
            note=note,
            message=message,
            lift_random=lift_random,
        )

    monkeypatch.setattr(TypeChecker, "check", spy)

    def run(*lines: str) -> list[str]:
        seen.clear()
        compile_hml(*lines)
        return list(seen)

    return run


# ---------------------------------------------------------------------------
# The five positions that DO route through checking mode
# ---------------------------------------------------------------------------


def test_declaration_initialiser_is_checked(recorded):
    assert any("declared type of 'a'" in r for r in recorded("const a : Natural = 3"))


def test_definition_body_is_checked(recorded):
    """Was a bare ``is_subtype``; this is defect B's fix at the code-path level."""
    assert any("declared type of 'p'" in r for r in recorded("def p : Probability := 0.5"))


def test_user_function_argument_is_checked(recorded):
    roles = recorded(
        "def f(x : Real, y : PositiveReal) : Real := x + y",
        "def a : Real := f(1.0, 2.0)",
    )
    assert any("parameter 'x' (argument 1) of f" in r for r in roles)
    assert any("parameter 'y' (argument 2) of f" in r for r in roles)


def test_distribution_role_argument_is_checked(recorded):
    roles = recorded(
        "param s : Real",
        "rv y : RandomVariable[Real]",
        "law y ~ Normal(location := 0.0, scale := s)",
    )
    assert any("'scale' role of Normal" in r for r in roles)


def test_typed_concept_member_body_is_checked(recorded):
    roles = recorded(
        "concept C",
        "    parameter a : Real",
        "    property q : Probability := 0.5",
        "    invariant ok := a > 0",
        "end",
    )
    assert any("declared type of C.q" in r for r in roles)


def test_exactly_five_positions_are_documented_as_checked():
    """Guards the count in the module docstring's table."""
    import hamiltonian_lang.type_system as ts

    rows = [
        line
        for line in ts.__doc__.splitlines()
        if line.startswith(("declaration", "definition", "user-function", "distribution",
                            "concept member", "builtin", "proof", "objective", "check-",
                            "index", "binary", "concept transform"))
    ]
    checked = [r for r in rows if "**yes**" in r]
    assert len(rows) == 12, rows
    assert len(checked) == 5, checked
    assert "Five of twelve positions check contextually." in ts.__doc__


# ---------------------------------------------------------------------------
# Defect B: the two forms must now agree
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("declaration", "definition"),
    [
        ("const p : Probability = 0.5", "def p : Probability := 0.5"),
        ("const n : Natural = 3", "def n : Natural := 3"),
        ("const s : PositiveReal = 1", "def s : PositiveReal := 1"),
        ("const pv : PValue = 0.05", "def pv : PValue := 0.05"),
    ],
)
def test_const_and_def_agree_on_the_same_literal(declaration, definition):
    """Identical mathematics; the keyword must not decide the verdict.

    This mattered beyond correctness: a syntax tournament in which a candidate surface
    preferring ``def`` was penalised for a reason unrelated to the surface would produce
    a confounded comparison.
    """
    assert compile_hml(declaration).ok(), declaration
    assert compile_hml(definition).ok(), definition


@pytest.mark.parametrize(
    ("declaration", "definition"),
    [
        ("const p : Probability = 2.0", "def p : Probability := 2.0"),
        ("const n : Natural = -3", "def n : Natural := -3"),
    ],
)
def test_const_and_def_agree_on_rejection_too(declaration, definition):
    """Agreement must not have been bought by making both accept everything."""
    assert not compile_hml(declaration).ok(), declaration
    assert not compile_hml(definition).ok(), definition


def test_the_define_diagnostic_keeps_its_code_and_headline():
    """`HML-T403` and its wording are cited in the freeze manifest; both are retained."""
    result = compile_hml("param p : Real", "def q : Probability := p")
    hit = next(d for d in result.diagnostics.items if d.code == "HML-T403")
    assert hit.message == "the body of 'q' does not inhabit its declared type"
    assert hit.expected == "Probability" and hit.found == "Real"
    # ...and it now carries what checking mode adds: an actionable correction.
    assert hit.correction


# ---------------------------------------------------------------------------
# The seven positions that do NOT check contextually — asserted, not assumed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("lines", "expected_code"),
    [
        # A proposition position imposes a PREDICATE (proposition-or-Bool), not a single
        # expected type, so there is nothing for checking mode to carry.
        (("param m : Real", "require m"), "HML-T404"),
        (("param m : Real", "prove m"), "HML-T404"),
        (("param m : Real", "assume m"), "HML-T404"),
        (("param m : Real", "check m"), "HML-T404"),
        # An objective imposes "has a dimension".
        (("rv y : RandomVariable[Real]", "minimise y"), "HML-T405"),
        # An index imposes "is an integer" on the index and "is indexable" on the base.
        (("param v : Vector[Real, 3]", "param i : Real", "def a : Real := v[i]"),
         "HML-T423"),
        # A builtin argument is still an inline is_subtype loop, not `check`.
        (("param x : Real", "def g : Real := log(x)"), "HML-T427"),
    ],
)
def test_an_unchecked_position_still_rejects_but_by_a_predicate(lines, expected_code):
    assert expected_code in codes(*lines)


def test_the_unchecked_positions_do_not_call_check(recorded):
    """The honest half of the claim, stated as a test rather than as prose.

    Each program is chosen to contain *only* the position under test — a definition
    wrapper would call ``check`` for its own body and mask the result.
    """
    assert recorded("param m : Real", "require m") == []
    assert recorded("rv y : RandomVariable[Real]", "minimise y") == []
    assert recorded("param x : Real", "require log(x) > 0.0") == []
    assert recorded("param v : Vector[Real, 3]", "param i : Real", "require v[i] > 0.0") == []


def test_a_builtin_argument_failure_is_not_a_checked_expr(recorded):
    """`HML-T427` is produced without an expectation object, so no CheckedExpr exists.

    Recorded because this is the most tempting position to describe as "checked": it
    does compare an argument against a declared domain. It carries no role, so a repair
    loop gets no name for what wanted the type — which is the half of checking mode that
    the repair loop actually consumes.
    """
    assert recorded("param x : Real", "require log(x) > 0.0") == []
    hit = next(
        d
        for d in compile_hml("param x : Real", "require log(x) > 0.0").diagnostics.items
        if d.code == "HML-T427"
    )
    assert hit.message == "the argument of log has the wrong type"
    assert hit.correction is None  # no role, so no role-named repair hint
    assert issubclass(CheckedExpr, object)  # the type exists; this path does not use it
