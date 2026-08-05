"""`PValue` and `PosteriorProbability` as source-language types (D-022).

Before this, `PValue` existed only in ``src/hamiltonian_lang/v1/epistemic.py``, a Python
API. ``param q : PValue`` was ``HML-T440: unknown type``, so no HML program could state
the distinction and the checker could not enforce it, while
``spec/v1/semantic_objects.yaml::kill_criteria.L4`` recorded the conflation as "Now
closed". The claim was true of the library and false of the language; it has been
corrected in the spec.

Covered here, in the order ``CLAUDE.md`` rule 4 requires: surface syntax · type rule ·
valid examples · invalid examples · canonicalisation · rendering · round trip ·
backend behaviour · adversarial.
"""

from __future__ import annotations

import itertools
import json

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends.canonical import canonical_json, content_hash
from hamiltonian_lang.backends.hml import render_module
from hamiltonian_lang.types import (
    UNIT_INTERVAL_KINDS,
    ScalarType,
    is_subtype,
    join,
    literal_inhabits,
)

KINDS = sorted(UNIT_INTERVAL_KINDS)


def compile_hml(*lines: str):
    return compile_source("module M\n" + "\n".join(lines) + "\n", "<pvalue-probe>")


def codes(*lines: str) -> list[str]:
    return [d.code for d in compile_hml(*lines).diagnostics.items]


def compiled(*lines: str):
    result = compile_hml(*lines)
    assert result.ok(), result.diagnostics.render()
    return result


# ---------------------------------------------------------------------------
# The lattice
# ---------------------------------------------------------------------------


def test_the_three_kinds_are_scalars():
    from hamiltonian_lang.types import SCALARS

    assert set(KINDS) <= set(SCALARS)
    assert KINDS == ["PValue", "PosteriorProbability", "Probability"]


@pytest.mark.parametrize(("a", "b"), [p for p in itertools.permutations(KINDS, 2)])
def test_no_coercion_exists_between_any_two_kinds(a, b):
    """Both directions, all six ordered pairs. Neither is a widening."""
    assert not is_subtype(ScalarType(a), ScalarType(b))


@pytest.mark.parametrize("kind", KINDS)
def test_each_kind_is_a_non_negative_real_and_a_real(kind):
    assert is_subtype(ScalarType(kind), ScalarType("NonNegativeReal"))
    assert is_subtype(ScalarType(kind), ScalarType("Real"))


@pytest.mark.parametrize("kind", KINDS)
def test_no_kind_is_comparable_with_positive_real(kind):
    """Same argument as `Probability` vs `PositiveReal`: 0 is admissible, 2.0 is not."""
    assert not is_subtype(ScalarType(kind), ScalarType("PositiveReal"))
    assert not is_subtype(ScalarType("PositiveReal"), ScalarType(kind))


@pytest.mark.parametrize(("a", "b"), [p for p in itertools.combinations(KINDS, 2)])
def test_two_kinds_meet_at_non_negative_real(a, b):
    assert join(ScalarType(a), ScalarType(b)) == ScalarType("NonNegativeReal")


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(("value", "inside"), [(0, True), (0.05, True), (1, True),
                                               (1.5, False), (-0.1, False)])
def test_values_are_the_closed_unit_interval(kind, value, inside):
    assert literal_inhabits(value, ScalarType(kind)) is inside


# ---------------------------------------------------------------------------
# Surface syntax and the required probes
# ---------------------------------------------------------------------------


def test_a_pvalue_declaration_checks_clean():
    """The directive's first required probe."""
    assert compile_hml("const pv : PValue := 0.05").ok()


def test_pvalue_is_accepted_by_every_declaration_keyword():
    for kw, sep in (("param", None), ("const", ":="), ("var", None), ("obs", "=")):
        line = f"{kw} q : PValue" + (f" {sep} 0.05" if sep else "")
        assert compile_hml(line).ok(), line


@pytest.mark.adversarial
def test_a_pvalue_may_not_stand_where_a_probability_is_required():
    """The directive's second required probe."""
    assert "HML-T403" in codes(
        "const pv : PValue := 0.05", "def posterior_h0 : Probability := pv"
    )


@pytest.mark.adversarial
def test_a_probability_may_not_stand_where_a_pvalue_is_required():
    """The directive's third required probe. The refusal is symmetric."""
    assert "HML-T403" in codes(
        "const p : Probability = 0.5", "def observed_pvalue : PValue := p"
    )


@pytest.mark.adversarial
@pytest.mark.parametrize(("a", "b"), [p for p in itertools.permutations(KINDS, 2)])
def test_every_ordered_pair_is_rejected_at_the_surface(a, b):
    assert "HML-T403" in codes(f"param q : {a}", f"def target : {b} := q")


@pytest.mark.adversarial
def test_a_value_outside_the_unit_interval_is_rejected():
    assert "HML-T402" in codes("const pv : PValue := 1.5")
    assert "HML-T402" in codes("const pv : PValue := -0.1")


def test_the_diagnostic_names_the_conflation_and_refuses_the_redeclaration_shortcut():
    """The hint must not tell a repair loop to commit the fallacy.

    The generic Ref hint would say "declare 'pv : PosteriorProbability'". Following it
    is exactly the prosecutor's fallacy, and a repair loop that follows compiler advice
    into an error is worse than one that gets no advice.
    """
    result = compile_hml(
        "const pv : PValue := 0.05", "def post : PosteriorProbability := pv"
    )
    hit = next(d for d in result.diagnostics.items if d.code == "HML-T403")
    assert "prosecutor's fallacy" in " ".join(hit.notes)
    assert "there is no conversion from PValue to PosteriorProbability" in hit.correction
    assert "declare 'pv" not in hit.correction


# ---------------------------------------------------------------------------
# Adversarial: laundering routes
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "body",
    [
        "pv * 1.0",
        "pv + 0.0",
        "pv / 1.0",
        "pv - 0.0",
        "-pv",
        "abs(pv)",
        "mean(w)",
    ],
)
def test_arithmetic_does_not_launder_a_pvalue_into_a_probability(body):
    """The join of two incomparable kinds is NonNegativeReal, which descends to none."""
    assert "HML-T403" in codes(
        "const pv : PValue := 0.05",
        "param w : Vector[PValue, 3]",
        f"def q : Probability := {body}",
    )


@pytest.mark.adversarial
def test_widening_to_real_is_one_way():
    """A kind widens to Real exactly as Probability does, and nothing brings it back."""
    assert compile_hml("const pv : PValue := 0.05", "def r : Real := pv").ok()
    assert "HML-T403" in codes(
        "const pv : PValue := 0.05",
        "def r : Real := pv",
        "def q : Probability := r",
    )


@pytest.mark.adversarial
def test_a_function_cannot_launder_a_kind_through_its_signature():
    assert "HML-T472" in codes(
        "def identity(x : Probability) : Probability := x",
        "const pv : PValue := 0.05",
        "def q : Probability := identity(pv)",
    )


@pytest.mark.adversarial
def test_a_distribution_role_does_not_accept_the_wrong_kind():
    assert "HML-T413" in codes(
        "const pv : PValue := 0.05",
        "rv flip : RandomVariable[Bool]",
        "law flip ~ Bernoulli(prob := pv)",
    )


@pytest.mark.adversarial
def test_a_kind_is_not_a_distribution_and_not_a_random_variable():
    assert "HML-T403" in codes(
        "rv pv : RandomVariable[PValue]", "def q : PValue := pv"
    )


# ---------------------------------------------------------------------------
# Canonicalisation, rendering and round trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
def test_the_declared_kind_survives_canonicalisation(kind):
    doc = json.loads(canonical_json(compiled(f"param q : {kind}").module))
    assert doc["statements"][0]["type"] == kind


def test_the_content_hash_separates_the_three_kinds():
    """The deterministic oracle. Same value, same statement shape, three identities."""
    hashes = {
        kind: content_hash(compiled(f"const q : {kind} := 0.05").module)
        for kind in KINDS
    }
    assert len(set(hashes.values())) == 3, hashes


@pytest.mark.parametrize("kind", KINDS)
def test_a_program_using_a_kind_round_trips(kind):
    first = compiled(
        f"param q : {kind}",
        "param alpha : PositiveReal",
        f"def report : {kind} := q",
        "require q >= 0.0",
        f"param batch : Vector[{kind}, 3]",
    )
    rendered = render_module(first.module)
    assert f": {kind}" in rendered
    assert f"Vector[{kind}, 3]" in rendered
    second = compile_source(rendered, "<rendered>")
    assert second.ok(), rendered + "\n" + second.diagnostics.render()
    assert first.hash() == second.hash(), rendered


@pytest.mark.parametrize("kind", KINDS)
def test_rendering_is_idempotent(kind):
    once = render_module(compiled(f"param q : {kind}").module)
    twice = render_module(compile_source(once, "<rendered>").module)
    assert once == twice


@pytest.mark.parametrize("kind", KINDS)
def test_a_kind_carries_its_unit_interval_proof_obligation(kind):
    result = compiled(f"param q : {kind}")
    assert any(o.description == "0 <= q <= 1" for o in result.obligations), [
        o.description for o in result.obligations
    ]


# ---------------------------------------------------------------------------
# Backend behaviour: every target erases the distinction, and each must say so
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target", ["sympy", "stan", "lean"])
def test_a_target_that_erases_the_epistemic_kind_declares_the_loss(target):
    """`backends/base.py`: a silent drop produces authoritative-looking wrong output.

    None of these targets can carry the kind. That is acceptable; not saying so is not.
    """
    from hamiltonian_lang.backends import render

    result = compiled("param pv : PValue")
    report = render(target, result.module, result.symbols)
    losses = " ".join(u.reason for u in report.unsupported)
    assert "epistemic kind" in losses, report.report()
    assert not report.faithful


def test_the_english_backend_glosses_the_referent_not_the_range():
    from hamiltonian_lang.backends import render

    result = compiled("param pv : PValue", "param post : PosteriorProbability")
    text = render("english", result.module, result.symbols).text
    assert "under the null hypothesis" in text
    assert "given the data" in text


def test_the_latex_backend_does_not_collapse_the_kind_to_an_interval():
    """`[0, 1]` for all three would erase the distinction in the display layer too."""
    from hamiltonian_lang.backends import render

    result = compiled("param pv : PValue")
    text = render("latex", result.module, result.symbols).text
    assert "PValue" in text
