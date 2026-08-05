"""The structured diagnostics adapter: local, causal, actionable, stable, non-leaking.

The non-leaking tests are the ones that protect a future H3 measurement. A diagnostic
that hands back the target program, the answer, or a whole replacement patch turns
verifier-guided repair into copying, and nothing downstream would show that it had.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.diagnostics import Diagnostic, Severity
from hamiltonian_lang.improvement.diagnostics import (
    DIAGNOSTIC_ADAPTER_VERSION,
    VIOLATED_INVARIANT_BY_CODE,
    DiagnosticCategory,
    DiagnosticLeak,
    adapt,
    adapt_all,
    adapt_and_check,
    assert_non_leaking,
    leak_reasons,
)

TARGET = "module m\n\nparam theta : Probability\nlaw y ~ Bernoulli(p := theta)\n"
ANSWER = "theta = 0.5"


def make(**kw) -> Diagnostic:
    base = dict(
        code="HML-T402",
        message="the declared type and the value disagree",
        line=3,
        col=8,
        end_line=3,
        end_col=13,
        expected="Probability",
        found="Real",
        correction="annotate the value as Probability",
    )
    base.update(kw)
    return Diagnostic(**base)  # type: ignore[arg-type]


# --- structure ---------------------------------------------------------------------


def test_fields_map_across():
    s = adapt(make())
    assert s.code == "HML-T402"
    assert s.category is DiagnosticCategory.TYPE
    assert s.expected == "Probability"
    assert s.actual == "Real"
    assert s.local_hint == "annotate the value as Probability"
    assert s.source_span.line == 3 and s.source_span.end_col == 13
    assert s.diagnostic_version == DIAGNOSTIC_ADAPTER_VERSION


@pytest.mark.parametrize(
    "code,category",
    [
        ("HML-L101", DiagnosticCategory.LEXICAL),
        ("HML-P201", DiagnosticCategory.PARSE),
        ("HML-N301", DiagnosticCategory.RESOLUTION),
        ("HML-T402", DiagnosticCategory.TYPE),
        ("HML-D501", DiagnosticCategory.DIMENSIONAL),
        ("HML-S601", DiagnosticCategory.SEMANTIC),
        ("HML-E701", DiagnosticCategory.EPISTEMIC),
        ("HML-G801", DiagnosticCategory.DISCOURSE),
        ("HML-X601", DiagnosticCategory.TRANSFORMATION),
    ],
)
def test_category_comes_from_the_code_family(code, category):
    assert adapt(make(code=code)).category is category


def test_an_unrecognised_code_is_unclassified_not_guessed():
    s = adapt(make(code="WHAT-9999"))
    assert s.category is DiagnosticCategory.UNCLASSIFIED
    assert "category" in s.gaps


# --- gaps are recorded, never filled ------------------------------------------------


def test_absent_information_becomes_a_gap():
    s = adapt(make(expected=None, found=None, correction=None, line=0))
    assert {"expected", "actual", "local_hint", "source_span"} <= set(s.gaps)
    assert s.expected is None and s.actual is None and s.local_hint is None


def test_counterexample_is_always_a_gap_for_compiler_diagnostics():
    """No compiler diagnostic carries one. The gap says so rather than leaving silence."""
    assert adapt(make()).counterexample is None
    assert "counterexample" in adapt(make()).gaps


def test_an_invariant_is_stated_only_where_one_is_recorded():
    with_entry = adapt(make(code="HML-T402"))
    assert with_entry.violated_invariant == VIOLATED_INVARIANT_BY_CODE["HML-T402"]
    assert "violated_invariant" not in with_entry.gaps

    without = adapt(make(code="HML-T460"))
    assert without.violated_invariant is None
    assert "violated_invariant" in without.gaps


def test_the_invariant_table_only_names_real_codes():
    import re

    for code in VIOLATED_INVARIANT_BY_CODE:
        assert re.fullmatch(r"HML-[A-Z]\d{3}", code)


# --- the message survives as a rendering --------------------------------------------


def test_render_preserves_the_human_readable_message():
    d = make()
    text = adapt(d).render()
    assert d.message in text
    assert d.code in text
    assert "Probability" in text and "Real" in text


def test_render_includes_the_invariant_when_one_is_known():
    assert "invariant:" in adapt(make(code="HML-T402")).render()


def test_severity_is_carried_through():
    assert adapt(make(severity=Severity.WARNING)).severity is Severity.WARNING


# --- stability -----------------------------------------------------------------------


def test_fingerprint_ignores_position():
    assert adapt(make(line=3)).fingerprint() == adapt(make(line=41, col=2)).fingerprint()


def test_fingerprint_ignores_message_wording():
    a = adapt(make(message="the declared type and the value disagree"))
    b = adapt(make(message="declared type does not admit this value"))
    assert a.fingerprint() == b.fingerprint()


def test_fingerprint_separates_different_defects():
    assert adapt(make(code="HML-T402")).fingerprint() != adapt(
        make(code="HML-T403")
    ).fingerprint()
    assert adapt(make(expected="Real")).fingerprint() != adapt(make()).fingerprint()


# --- the non-leaking contract ---------------------------------------------------------


def test_a_normal_diagnostic_is_clean():
    assert leak_reasons(adapt(make()), target_program=TARGET, final_answer=ANSWER) == []
    adapt_and_check(make(), target_program=TARGET, final_answer=ANSWER)


def test_leaking_the_complete_target_program_is_refused():
    d = make(correction=f"replace the module with:\n{TARGET}")
    with pytest.raises(DiagnosticLeak, match="complete target program"):
        assert_non_leaking(adapt(d), target_program=TARGET)


def test_leaking_the_final_answer_is_refused():
    d = make(notes=[f"the intended result is {ANSWER}"])
    with pytest.raises(DiagnosticLeak, match="final mathematical answer"):
        assert_non_leaking(adapt(d), final_answer=ANSWER)


def test_an_unrestricted_replacement_patch_is_refused_by_length():
    patch = "\n".join(f"const c{i} : Real = {i}.0" for i in range(6))
    with pytest.raises(DiagnosticLeak, match="replacement patch"):
        assert_non_leaking(adapt(make(correction=patch)))


def test_an_unrestricted_replacement_patch_is_refused_by_breadth():
    d = make(correction="param x : Real then require x > 0.0")
    with pytest.raises(DiagnosticLeak, match="program fragment"):
        assert_non_leaking(adapt(d))


def test_a_single_statement_hint_is_allowed():
    """The contract restricts breadth, not the mention of a keyword."""
    assert_non_leaking(adapt(make(correction="declare param x : Probability")))


def test_leak_check_ignores_a_trivially_short_program():
    """Containment must mean something. A two-token 'program' would match everything."""
    assert leak_reasons(adapt(make()), target_program="x") == []


# --- against the real compiler ---------------------------------------------------------


def test_real_compiler_diagnostics_adapt_and_do_not_leak():
    result = compile_source("module m\n\nconst a : Real = 1.0\nrequire b > 0.0\n")
    assert not result.ok()
    structured = adapt_all(result.diagnostics.errors)
    assert structured
    for s in structured:
        assert s.code.startswith("HML-")
        assert s.category is not DiagnosticCategory.UNCLASSIFIED
        assert_non_leaking(s, target_program=result.source, final_answer="a = 1.0")


def test_every_real_diagnostic_renders_its_own_message():
    result = compile_source("module m\n\nparam p : Probability\ndef q : Probability := p + p\n")
    assert [d.code for d in result.diagnostics.errors] == ["HML-T403"]
    for d in result.diagnostics.errors:
        assert d.message in adapt(d).render()
