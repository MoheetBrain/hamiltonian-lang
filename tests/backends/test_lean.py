"""Lean backend tests.

**No Lean toolchain validated any of this output.** ``lean``/``lake``/Mathlib are not
installed in this environment and are not invoked anywhere in this file. Nothing here
establishes that the emitted file elaborates. The assertions are structural:
namespace balance, `sorry`-termination of every obligation, absence of any tactic other
than `sorry`, and — the load-bearing one — that quantifier nesting order is preserved.

The quantifier-order test is the reason this backend exists as a separate target.
``examples/logic/quantifier_scope.hml`` and its ``_reversed`` companion differ only in
the nesting order of a ``forall``/``exists`` pair. The first statement is true over the
reals and the second is false, so a translation that reordered them would produce a
Lean file asserting the wrong theorem. The two Lean outputs are therefore asserted to
DIFFER, and the specific binder order of each is pinned.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends import render
from hamiltonian_lang.backends.lean import LEAN_SCALARS, to_lean

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def example_files() -> list[Path]:
    return sorted(
        p for p in EXAMPLES.rglob("*.hml") if "candidate_syntaxes" not in p.parts
    )


def compile_ok(source: str):
    result = compile_source(source)
    assert result.ok(), "\n" + result.diagnostics.render()
    return result


def lean_of(path: Path):
    result = compile_ok(path.read_text())
    return render("lean", result.module, result.symbols)


def _code_lines(text: str) -> list[str]:
    """Non-comment, non-blank lines of the emitted file."""
    out: list[str] = []
    in_block = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("/-"):
            in_block = True
        if in_block:
            if line.endswith("-/"):
                in_block = False
            continue
        if not line or line.startswith("--"):
            continue
        out.append(line)
    return out


# ---------------------------------------------------------------------------
# 1. Every example survives the backend
# ---------------------------------------------------------------------------


def test_every_example_renders_without_crashing(example):
    out = lean_of(example)
    assert out.target == "lean"
    assert out.text.strip()


def test_to_lean_entry_point_matches_registry(example):
    result = compile_ok(example.read_text())
    assert to_lean(result.module, result.symbols).text == (
        render("lean", result.module, result.symbols).text
    )


# ---------------------------------------------------------------------------
# 2. Quantifier nesting order. The load-bearing test.
# ---------------------------------------------------------------------------


class TestQuantifierOrder:
    def _pair(self):
        a = next(p for p in example_files() if p.name == "quantifier_scope.hml")
        b = next(p for p in example_files() if p.name == "quantifier_scope_reversed.hml")
        return lean_of(a), lean_of(b), a, b

    def test_the_two_outputs_differ(self):
        """The whole hypothesis H2, reduced to one assertion."""
        forward, reversed_, fa, fb = self._pair()
        assert forward.text != reversed_.text, (
            f"{fa.name} and {fb.name} differ only in quantifier nesting order; "
            "identical Lean output would mean the order was silently discarded"
        )

    def test_forall_exists_is_emitted_in_that_order(self):
        forward, _, _, _ = self._pair()
        # require forall x : Real . exists y : Real . y > x
        assert "theorem require_1 : ∀ x : ℝ, ∃ y : ℝ, y > x := by sorry" in forward.text

    def test_exists_forall_is_emitted_in_that_order(self):
        _, reversed_, _, _ = self._pair()
        # require exists y : Real . forall x : Real . y > x
        assert "theorem require_1 : ∃ y : ℝ, ∀ x : ℝ, y > x := by sorry" in reversed_.text

    def test_binder_sequence_is_the_source_sequence(self):
        forward, reversed_, _, _ = self._pair()

        def binders(text: str) -> list[str]:
            line = next(
                ln for ln in text.splitlines() if ln.startswith("theorem require_1")
            )
            return re.findall(r"[∀∃]", line)

        assert binders(forward.text) == ["∀", "∃"]
        assert binders(reversed_.text) == ["∃", "∀"]

    def test_deeper_nesting_is_preserved(self):
        out = compile_ok(
            "module M\n"
            "prove forall a : Real . exists b : Real . forall c : Real . "
            "a + b > c\n"
        ).render("lean")
        assert "∀ a : ℝ, ∃ b : ℝ, ∀ c : ℝ, a + b > c" in out.text

    def test_exists_unique_maps_to_the_unique_existential(self):
        out = compile_ok(
            "module M\nprove exists unique z : Real . z = z\n"
        ).render("lean")
        assert "∃! z : ℝ," in out.text


# ---------------------------------------------------------------------------
# 3. Statement skeletons only -- no proof search (design freeze §8)
# ---------------------------------------------------------------------------


def test_every_theorem_is_closed_with_sorry(example):
    for line in _code_lines(lean_of(example).text):
        if line.startswith(("theorem ", "lemma ")):
            assert line.endswith(":= by sorry"), (
                f"{example}: theorem not closed with sorry: {line!r}"
            )


def test_no_tactic_other_than_sorry_is_emitted(example):
    code = "\n".join(_code_lines(lean_of(example).text))
    tactics = set(re.findall(r"\bby\s+(\w+)", code))
    assert tactics <= {"sorry"}, f"{example}: proof search attempted: {tactics}"


def test_no_proof_term_is_invented(example):
    """`:= by sorry` or `:= <expr>` for defs; never a hand-written proof term."""
    for line in _code_lines(lean_of(example).text):
        if line.startswith("theorem "):
            assert " := by sorry" in line


# ---------------------------------------------------------------------------
# 4. Structural checks (NOT compiler validation -- see the module docstring)
# ---------------------------------------------------------------------------


def test_namespace_is_opened_and_closed(example):
    lines = _code_lines(lean_of(example).text)
    opens = [ln for ln in lines if ln.startswith("namespace ")]
    closes = [ln for ln in lines if ln.startswith("end ")]
    assert len(opens) == 1 and len(closes) == 1
    assert opens[0].split()[1] == closes[0].split()[1]


def test_mathlib_is_imported(example):
    assert "import Mathlib" in lean_of(example).text


def test_parentheses_are_balanced(example):
    for line in _code_lines(lean_of(example).text):
        assert line.count("(") == line.count(")"), f"{example}: unbalanced {line!r}"


def test_every_binder_names_a_type(example):
    """`variable (x : T)` -- never an untyped binder."""
    for line in _code_lines(lean_of(example).text):
        if line.startswith("variable "):
            assert re.fullmatch(r"variable \([^:]+ : .+\)", line), (
                f"{example}: malformed variable binder {line!r}"
            )


def test_every_reference_is_bound_somewhere(example):
    """Declaration/usage consistency over the emitted file."""
    text = lean_of(example).text
    lines = _code_lines(text)
    bound: set[str] = set()
    for line in lines:
        m = re.match(r"variable \(([A-Za-z_]\w*) :", line)
        if m:
            bound.add(m.group(1))
        m = re.match(r"def ([A-Za-z_]\w*)", line)
        if m:
            bound.add(m.group(1))
            bound.update(re.findall(r"\(([A-Za-z_]\w*) : ", line))
        m = re.match(r"theorem ([A-Za-z_]\w*)", line)
        if m:
            bound.add(m.group(1))
    # Lean/Mathlib names and syntax that need no local binder
    ambient = {
        "Matrix", "mulVec", "Fin", "Set", "Real", "exp", "log", "sqrt", "sin", "cos",
        "tan", "abs", "HMul", "hMul", "Prop", "Bool", "True", "False", "by", "sorry",
        "import", "Mathlib", "namespace", "end", "variable", "def", "theorem",
    }
    for line in lines:
        if line.startswith(("import", "namespace", "end")):
            continue
        # quantifier-bound variables are local to their statement
        local = set(re.findall(r"[∀∃][!]? (\w+) :", line))
        body = line.split(":=", 1)[-1] if line.startswith("def ") else line
        for name in re.findall(r"\b[A-Za-z_]\w*\b", body):
            if name in ambient or name in local or name in bound or name.isdigit():
                continue
            pytest.fail(f"{example}: {name!r} used in {line!r} without a binder")


def test_generated_text_has_a_provenance_header(example):
    text = lean_of(example).text
    assert text.startswith("/-")
    assert "Not elaborated or type-checked by any Lean toolchain" in text
    assert "performs no proof" in text


# ---------------------------------------------------------------------------
# 5. Type mapping
# ---------------------------------------------------------------------------


def test_scalar_lattice_is_fully_mapped():
    from hamiltonian_lang.types import SCALARS

    for name in SCALARS:
        assert name in LEAN_SCALARS, f"{name} has no Lean carrier type"


@pytest.mark.parametrize(
    ("hml_type", "carrier", "hypothesis"),
    [
        ("Real", "ℝ", None),
        ("Integer", "ℤ", None),
        ("Rational", "ℚ", None),
        ("Natural", "ℕ", None),
        ("PositiveReal", "ℝ", "0 < s"),
        ("NonNegativeReal", "ℝ", "0 ≤ s"),
        ("Probability", "ℝ", "0 ≤ s"),
    ],
)
def test_refinements_become_hypotheses_over_a_carrier_type(hml_type, carrier, hypothesis):
    out = compile_ok(f"module M\nparam s : {hml_type}\n").render("lean")
    assert f"variable (s : {carrier})" in out.text
    if hypothesis is None:
        assert "h_s_" not in out.text
    else:
        assert hypothesis in out.text
        assert any(
            u.severity == "weakened" and "hypothesis" in u.reason
            for u in out.unsupported
        ), "encoding a refinement as a hypothesis is a weakening and must be reported"


def test_probability_gets_both_bounds():
    out = compile_ok("module M\nparam p : Probability\n").render("lean")
    assert "variable (h_p_nonneg : 0 ≤ p)" in out.text
    assert "variable (h_p_le_one : p ≤ 1)" in out.text


def test_subtype_encoding_is_not_used():
    """The choice documented in the module docstring, asserted so it stays a choice."""
    out = compile_ok("module M\nparam s : PositiveReal\n").render("lean")
    assert "//" not in out.text  # Lean subtype syntax {x : T // p x}


# ---------------------------------------------------------------------------
# 6. Loss reporting
# ---------------------------------------------------------------------------


def test_no_example_is_losslessly_expressible_in_lean(example):
    out = lean_of(example)
    assert out.unsupported, f"{example}: no loss reported"
    assert out.faithful is False
    for u in out.unsupported:
        assert u.severity in ("dropped", "approximated", "weakened")
        assert u.reason.strip()


def test_probability_laws_are_reported_as_dropped():
    """§8 and the brief: no measure-theoretic encoding is to be invented."""
    for name in ("bayesian_coin.hml", "normal_distribution.hml", "linear_regression.hml"):
        out = lean_of(next(p for p in example_files() if p.name == name))
        law_drops = [
            u for u in out.unsupported
            if u.severity == "dropped"
            and any(u.construct.startswith(r) for r in ("law", "prior", "likelihood"))
        ]
        assert law_drops, f"{name}: law statements must be reported as dropped"
        assert all("measure" in u.reason for u in law_drops)
    # and nothing measure-theoretic is fabricated in the output
    text = lean_of(
        next(p for p in example_files() if p.name == "bayesian_coin.hml")
    ).text
    for invented in ("MeasureTheory", "ProbabilityTheory", "pdf", "Measure"):
        assert invented not in _joined(text), f"{invented!r} was invented in the output"


def _joined(text: str) -> str:
    """Code lines only -- comments may legitimately name what was dropped."""
    return "\n".join(_code_lines(text))


def test_inference_queries_are_reported_as_dropped():
    out = lean_of(next(p for p in example_files() if p.name == "bayesian_coin.hml"))
    assert any(
        u.construct.startswith("infer") and u.severity == "dropped"
        for u in out.unsupported
    )


def test_dimensions_are_reported_as_dropped():
    out = lean_of(next(p for p in example_files() if p.name == "kinetic_energy.hml"))
    assert any(
        u.construct == "check dimension" and u.severity == "dropped"
        for u in out.unsupported
    )
    assert any("dimension" in u.reason for u in out.unsupported)


def test_require_is_reported_as_weakened_into_a_theorem():
    out = lean_of(
        next(p for p in example_files() if p.name == "constrained_optimisation.hml")
    )
    weakened = [u for u in out.unsupported if u.construct.startswith("require")]
    assert weakened and all(u.severity == "weakened" for u in weakened)
    assert any("constraint" in u.reason for u in weakened)


def test_objective_and_solve_are_reported_as_dropped():
    out = lean_of(
        next(p for p in example_files() if p.name == "constrained_optimisation.hml")
    )
    kinds = {u.construct for u in out.unsupported if u.severity == "dropped"}
    assert "minimise" in kinds
    assert "solve" in kinds


def test_random_variable_type_is_dropped_not_conflated():
    """RandomVariable[Real] must NOT silently become ℝ."""
    out = compile_ok(
        "module M\nvar X : RandomVariable[Real]\n"
    ).render("lean")
    assert "variable (X :" not in out.text
    assert any(
        u.severity == "dropped" and "measurable function" in u.reason
        for u in out.unsupported
    )


def test_declaration_kind_loss_is_reported():
    out = lean_of(next(p for p in example_files() if p.name == "bayesian_coin.hml"))
    assert any("declaration kind" in u.reason for u in out.unsupported)


def test_limitations_are_declared_on_the_class():
    from hamiltonian_lang.backends.lean import LeanBackend

    assert LeanBackend.limitations
    assert all(isinstance(s, str) and s.strip() for s in LeanBackend.limitations)
