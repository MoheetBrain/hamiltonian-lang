"""User-defined call signatures: arity, argument types, return type, callability.

D-023. Before this, a call to a user ``def`` checked **nothing** — neither the number of
arguments nor their types — because ``_call_type`` returned the callee's declared type
without looking at the call. Only the seven ``_BUILTIN_SIGNATURES`` were enforced.
Reproduced by the Lead at commit ``967e95d``
(``docs/evaluation/PHASE1_LEAD_AUDIT.md`` §2a, defect A) and by the adversarial agent
(``docs/evaluation/V1_FREEZE_MANIFEST.md`` §2a).

The last section of this file is not about types at all. It asserts that these
diagnostics do not contain the repaired program, because they are H3 machinery and an
answer-bearing diagnostic silently converts an H3 result into an unmeasurable one.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source

TWO_PARAM_DEF = "def f(x : Real, y : PositiveReal) : Real := x + y"


def compile_hml(*lines: str):
    return compile_source("module M\n" + "\n".join(lines) + "\n", "<sig-probe>")


def codes(*lines: str) -> list[str]:
    return [d.code for d in compile_hml(*lines).diagnostics.items]


def first(code: str, *lines: str):
    result = compile_hml(*lines)
    for d in result.diagnostics.items:
        if d.code == code:
            return d
    raise AssertionError(
        f"expected {code}; got {[x.code for x in result.diagnostics.items]}\n"
        + result.diagnostics.render()
    )


# ---------------------------------------------------------------------------
# The three programs the directive names, each of which used to compile clean
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_too_few_arguments_is_rejected():
    assert "HML-T471" in codes(TWO_PARAM_DEF, "def a : Real := f(1.0)")


@pytest.mark.adversarial
def test_too_many_arguments_is_rejected():
    assert "HML-T471" in codes(TWO_PARAM_DEF, "def b : Real := f(1.0, 2.0, 3.0)")


@pytest.mark.adversarial
def test_an_argument_that_violates_its_parameter_type_is_rejected():
    """Argument 2 is -2.0 where the parameter is PositiveReal."""
    assert "HML-T472" in codes(TWO_PARAM_DEF, "def c : Real := f(1.0, -2.0)")


def test_a_correct_call_still_compiles():
    result = compile_hml(TWO_PARAM_DEF, "def ok : Real := f(1.0, 2.0)")
    assert result.ok(), result.diagnostics.render()


# ---------------------------------------------------------------------------
# What the signature record has to carry
# ---------------------------------------------------------------------------


def test_the_signature_records_ordered_names_types_return_and_origin():
    from hamiltonian_lang.type_system import TypeChecker

    result = compile_hml(TWO_PARAM_DEF, "def ok : Real := f(1.0, 2.0)")
    checker = TypeChecker(result.module, result.symbols, result.diagnostics)
    sig = checker.signatures["f"]

    assert sig.param_names == ("x", "y")
    assert [t.render() for t in sig.param_types] == ["Real", "PositiveReal"]
    assert sig.return_type is not None and sig.return_type.render() == "Real"
    assert sig.arity == 2
    # Source definition identity, not a spelling match.
    assert sig.origin is not None and sig.origin.name == "f"
    assert sig.span.line == 2
    assert sig.render() == "f(x : Real, y : PositiveReal) : Real"


def test_arguments_bind_by_position_not_by_matching_the_multiset_of_types():
    """`p(2.0, true)` supplies both required types, in the wrong two positions.

    A checker that merely asked "are these the right types, in some order?" would accept
    it. Both positions must fail, and each diagnostic must name its own parameter.
    """
    result = compile_hml(
        "def p(flag : Bool, size : PositiveReal) : PositiveReal := size",
        "def c : PositiveReal := p(2.0, true)",
    )
    failures = [d for d in result.diagnostics.items if d.code == "HML-T472"]
    assert len(failures) == 2, [d.message for d in result.diagnostics.items]
    assert "'flag'" in failures[0].message and "argument 1" in failures[0].message
    assert "'size'" in failures[1].message and "argument 2" in failures[1].message
    # And the correctly ordered call compiles.
    assert compile_hml(
        "def p(flag : Bool, size : PositiveReal) : PositiveReal := size",
        "def c : PositiveReal := p(true, 2.0)",
    ).ok()


def test_the_declared_return_type_is_what_the_call_expression_has():
    """A call returning Real cannot inhabit a PositiveReal definition."""
    assert "HML-T403" in codes(
        "def g(x : Real) : Real := x",
        "param p : Real",
        "def bad : PositiveReal := g(p)",
    )


def test_a_call_is_checked_even_when_it_precedes_the_definition():
    """Module scope is order-independent (D-008), so enforcement must be too."""
    assert "HML-T471" in codes("def a : Real := f(1.0)", TWO_PARAM_DEF)


def test_a_concept_transform_call_is_checked_for_arity():
    assert "HML-T471" in codes(
        "concept C",
        "    parameter location : Real",
        "    parameter scale : PositiveReal",
        "    transform standardise(u : Real) := (u - location) / scale",
        "    invariant affine := standardise(location, scale) = 0",
        "end",
    )


def test_the_shipped_concept_example_still_compiles():
    """The one user-defined call in `examples/` — a guard against over-rejection."""
    from pathlib import Path

    path = Path("examples/concepts/location_scale_family.hml")
    result = compile_source(path.read_text(), str(path))
    assert result.ok(), result.diagnostics.render()


# ---------------------------------------------------------------------------
# Callability
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_applying_a_definition_that_binds_a_value_is_rejected():
    """`def v : Real := 1.0` is a value. `v(2.0)` is a category error, not a typo."""
    d = first("HML-T470", "def v : Real := 1.0", "def w : Real := v(2.0)")
    assert "not callable" in d.message
    assert any("binds a value, not a function" in n for n in d.notes)


@pytest.mark.adversarial
def test_applying_a_declared_parameter_is_rejected():
    assert "HML-T470" in codes("param k : Real", "def w : Real := k(2.0)")


@pytest.mark.adversarial
def test_an_undefined_callee_is_still_rejected_by_name_resolution():
    assert "HML-N306" in codes("def w : Real := nowhere(2.0)")


def test_an_unannotated_parameter_constrains_nothing_but_arity_still_holds():
    """Honest partiality: an untyped binder cannot check its argument.

    Arity is still exact, because arity does not depend on the annotation.
    """
    assert "HML-T471" in codes("def h(a) : Real := 1.0", "def w : Real := h(1.0, 2.0)")
    assert compile_hml("def h(a) : Real := 1.0", "def w : Real := h(1.0)").ok()


# ---------------------------------------------------------------------------
# H3 hygiene — the diagnostics must not contain the answer
# ---------------------------------------------------------------------------
#
# H1 (representation as input), H2 (representation as workspace) and H3 (verifier-guided
# repair) can come apart, and only H3 is affected by diagnostic quality. A diagnostic
# that carries the corrected program makes a repair loop succeed by transcription, so a
# later H3 number would measure copying and would still be reported as a repair result.
# These tests are the guard on that.

_LEAK_CASES = (
    # (broken program, the repaired statement a leaky diagnostic might contain)
    ((TWO_PARAM_DEF, "def a : Real := f(1.0)"), "def a : Real := f(1.0, 2.0)"),
    ((TWO_PARAM_DEF, "def b : Real := f(1.0, 2.0, 3.0)"), "def b : Real := f(1.0, 2.0)"),
    ((TWO_PARAM_DEF, "def c : Real := f(1.0, -2.0)"), "def c : Real := f(1.0, 2.0)"),
)


@pytest.mark.parametrize(("lines", "repaired"), _LEAK_CASES)
def test_no_signature_diagnostic_leaks_a_repair(lines, repaired):
    text = compile_hml(*lines).diagnostics.render()
    assert repaired not in text, (
        "a diagnostic contains the corrected statement. That makes verifier-guided "
        "repair (H3) a transcription task and destroys the measurement."
    )
    # Nor any complete statement of the repaired form, however spelled.
    for line in text.splitlines():
        stripped = line.strip()
        assert not (stripped.startswith("def ") and ":=" in stripped), stripped


def test_a_signature_correction_names_a_repair_class_not_a_value():
    """The hint may name parameters, types, counts and a direction. Never a value."""
    too_few = first("HML-T471", TWO_PARAM_DEF, "def a : Real := f(1.0)")
    assert "supply 1 more argument(s)" in too_few.correction
    assert "(x : Real, y : PositiveReal)" in too_few.correction
    assert "2.0" not in too_few.correction

    too_many = first("HML-T471", TWO_PARAM_DEF, "def b : Real := f(1.0, 2.0, 3.0)")
    assert "remove 1 argument(s)" in too_many.correction

    bad_type = first("HML-T472", TWO_PARAM_DEF, "def c : Real := f(1.0, -2.0)")
    # It says which value failed; it does not say which value would pass.
    assert "-2.0" in bad_type.correction
    assert "PositiveReal" in bad_type.correction
    assert ":=" not in bad_type.correction


def test_a_signature_diagnostic_carries_span_expectation_and_actual():
    """A repair loop needs where, what was wanted, and what arrived. All three."""
    d = first("HML-T471", TWO_PARAM_DEF, "def a : Real := f(1.0)")
    assert d.line == 3 and d.code == "HML-T471"
    assert d.expected == "f(x : Real, y : PositiveReal) : Real"
    assert d.found == "1 argument(s)"
    assert any("declared at line 2" in n for n in d.notes)
