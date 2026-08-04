"""SymPy backend tests.

Unlike the Stan and Lean backends, this one *can* be verified end to end: the emitted
Python is written to a real file and executed, and the resulting SymPy objects are
inspected. Execution proves the file is syntactically valid Python and that every
SymPy call in it is well-formed. It does **not** prove that the expressions mean the
same thing as the HML source; the fidelity claims live in
``docs/design/BACKEND_CONTRACT.md`` and are argued there, not measured here.

If SymPy is not importable the execution tests skip with an explicit reason. They are
never faked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends import render
from hamiltonian_lang.backends.sympy import SCALAR_ASSUMPTIONS, to_sympy

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def example_files() -> list[Path]:
    return sorted(
        p for p in EXAMPLES.rglob("*.hml") if "candidate_syntaxes" not in p.parts
    )


def compile_ok(source: str):
    result = compile_source(source)
    assert result.ok(), "\n" + result.diagnostics.render()
    return result


def sympy_of(path: Path):
    result = compile_ok(path.read_text())
    return render("sympy", result.module, result.symbols)


def run_generated(text: str, tmp_path: Path, name: str = "generated") -> dict:
    """Write the emitted module to a real file, execute it, return its namespace."""
    pytest.importorskip(
        "sympy",
        reason="sympy is not installed in this environment; the generated code cannot "
        "be executed, and a pass would be meaningless. Install with "
        "`.venv/bin/pip install sympy`.",
    )
    path = tmp_path / f"{name}.py"
    path.write_text(text)
    namespace: dict = {"__name__": "__hml_generated__", "__file__": str(path)}
    exec(compile(path.read_text(), str(path), "exec"), namespace)  # noqa: S102
    return namespace


# ---------------------------------------------------------------------------
# 1. Every example survives the backend
# ---------------------------------------------------------------------------


def test_every_example_renders_without_crashing(example):
    out = sympy_of(example)
    assert out.target == "sympy"
    assert out.text.strip()


def test_to_sympy_entry_point_matches_registry(example):
    result = compile_ok(example.read_text())
    assert to_sympy(result.module, result.symbols).text == (
        render("sympy", result.module, result.symbols).text
    )


def test_generated_python_is_syntactically_valid(example):
    """Compiles even without sympy installed -- this is a pure-syntax check."""
    compile(sympy_of(example).text, str(example), "exec")


# ---------------------------------------------------------------------------
# 2. The generated code actually runs
# ---------------------------------------------------------------------------


def test_generated_code_executes(example, tmp_path):
    ns = run_generated(sympy_of(example).text, tmp_path, example.stem)
    # the fixed output surface the backend promises
    for key in (
        "definitions", "requirements", "claims", "assumptions", "type_constraints",
        "objective", "objective_direction", "solve_targets", "symbols_by_name",
    ):
        assert key in ns, f"{example}: generated module is missing {key!r}"


def test_kinetic_energy_expression_is_rebuilt_exactly(tmp_path):
    sp = pytest.importorskip("sympy", reason="sympy is not installed")
    src = next(p for p in example_files() if p.name == "kinetic_energy.hml")
    ns = run_generated(sympy_of(src).text, tmp_path, "kinetic_energy")
    m, v = ns["m"], ns["v"]
    assert sp.simplify(ns["kinetic_energy"] - m * v**2 / 2) == 0
    # the decimal literal became an exact rational, not a binary float
    assert sp.Rational(1, 2) in ns["kinetic_energy"].args


def test_assumptions_are_derived_from_the_hml_type(tmp_path):
    ns = run_generated(
        compile_ok(
            "module M\n"
            "param a : Real\n"
            "param b : PositiveReal\n"
            "param c : NonNegativeReal\n"
            "param d : Natural\n"
            "param e : Integer\n"
            "param f : Probability\n"
        ).render("sympy").text,
        tmp_path,
        "assumptions",
    )
    assert ns["a"].is_real is True
    assert ns["b"].is_positive is True
    assert ns["c"].is_nonnegative is True and ns["c"].is_positive is not True
    assert ns["d"].is_integer is True and ns["d"].is_nonnegative is True
    assert ns["e"].is_integer is True
    # Probability: the lower half is an assumption, the upper half is a constraint.
    assert ns["f"].is_nonnegative is True
    assert ns["type_constraints"], "the [0, 1] upper bound must be recorded somewhere"


def test_require_becomes_a_relational_object(tmp_path):
    sp = pytest.importorskip("sympy", reason="sympy is not installed")
    src = next(p for p in example_files() if p.name == "constrained_optimisation.hml")
    ns = run_generated(sympy_of(src).text, tmp_path, "constrained")
    assert len(ns["requirements"]) == 3
    assert all(isinstance(r, sp.core.relational.Relational) for r in ns["requirements"])
    x, y = ns["x"], ns["y"]
    assert sp.Ge(x + y, 10) in ns["requirements"]
    assert ns["objective_direction"] == "minimise"
    assert sp.simplify(ns["objective"] - (x**2 + y**2)) == 0


def test_prove_becomes_a_claim_not_a_proof(tmp_path):
    ns = run_generated(
        compile_ok(
            "module M\nparam x : Real\nprove x = x\n"
        ).render("sympy").text,
        tmp_path,
        "claims",
    )
    assert len(ns["claims"]) == 1


def test_concept_members_are_flattened_and_callable(tmp_path):
    sp = pytest.importorskip("sympy", reason="sympy is not installed")
    src = next(p for p in example_files() if p.name == "location_scale_family.hml")
    ns = run_generated(sympy_of(src).text, tmp_path, "concept")
    standardise = ns["LocationScaleFamily__standardise"]
    loc = ns["LocationScaleFamily__location"]
    scale = ns["LocationScaleFamily__scale"]
    assert isinstance(standardise, sp.Lambda)
    # standardise(location) = 0 is the concept's own invariant; it must hold in the
    # rebuilt SymPy expression too.
    assert sp.simplify(standardise(loc)) == 0
    assert sp.simplify(standardise(loc + scale)) == 1


def test_matrix_shapes_survive(tmp_path):
    sp = pytest.importorskip("sympy", reason="sympy is not installed")
    src = next(p for p in example_files() if p.name == "linear_regression.hml")
    ns = run_generated(sympy_of(src).text, tmp_path, "regression")
    assert ns["x"].shape == (ns["N"], ns["P"])
    assert ns["beta"].shape == (ns["P"], 1)
    assert ns["linear_predictor"].shape == (ns["N"], 1)
    assert isinstance(ns["linear_predictor"], sp.MatrixExpr)


# ---------------------------------------------------------------------------
# 3. Loss reporting
# ---------------------------------------------------------------------------


def test_no_example_is_losslessly_expressible_in_sympy(example):
    out = sympy_of(example)
    assert out.unsupported, f"{example}: no loss reported"
    assert out.faithful is False
    for u in out.unsupported:
        assert u.severity in ("dropped", "approximated", "weakened")
        assert u.reason.strip()


def test_distributions_are_dropped_not_faked():
    """The whole point: sympy.stats is NOT used to fake a partial translation."""
    out = sympy_of(next(p for p in example_files() if p.name == "bayesian_coin.hml"))
    assert "sympy.stats" not in out.text
    dropped = [u for u in out.unsupported if u.severity == "dropped"]
    assert any("prior theta" in u.construct for u in dropped)
    assert any("likelihood successes" in u.construct for u in dropped)
    assert any(u.construct.startswith("infer") for u in dropped)


def test_quantifiers_are_dropped_and_the_loss_is_stated_plainly():
    out = sympy_of(next(p for p in example_files() if p.name == "quantifier_scope.hml"))
    assert any(
        "quantifier" in u.construct and u.severity == "dropped"
        for u in out.unsupported
    )


def test_quantifier_scope_pair_is_indistinguishable_in_sympy():
    """An honest negative result, asserted so it cannot regress into a false positive.

    SymPy has no quantifier, so the two files that differ *only* in quantifier nesting
    order translate to the same thing. The backend must report that as loss rather
    than let a reader believe the order survived.
    """
    a = sympy_of(next(p for p in example_files() if p.name == "quantifier_scope.hml"))
    b = sympy_of(
        next(p for p in example_files() if p.name == "quantifier_scope_reversed.hml")
    )
    assert a.text == b.text
    assert a.faithful is False and b.faithful is False


def test_dimensions_are_dropped():
    out = sympy_of(next(p for p in example_files() if p.name == "kinetic_energy.hml"))
    assert any("dimension" in u.reason.lower() for u in out.unsupported)


def test_probability_upper_bound_is_reported_as_weakened():
    out = compile_ok("module M\nparam p : Probability\n").render("sympy")
    assert any(
        u.severity == "weakened" and "upper bound" in u.reason for u in out.unsupported
    )


def test_scalar_assumption_table_covers_the_lattice():
    from hamiltonian_lang.types import SCALARS

    for name in SCALARS:
        assert name in SCALAR_ASSUMPTIONS, f"{name} has no SymPy assumption mapping"


def test_limitations_are_declared_on_the_class():
    from hamiltonian_lang.backends.sympy import SympyBackend

    assert SympyBackend.limitations
    assert all(isinstance(s, str) and s.strip() for s in SympyBackend.limitations)
