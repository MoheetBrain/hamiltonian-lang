"""Constructions the language MUST reject, asserted on the diagnostic CODE.

Why codes and not messages
--------------------------
A message is prose and may be reworded; a code is a contract. Asserting on the message
would make this suite a spelling test and would let a real regression pass as long as the
wording survived. Every assertion here names a code from ``hamiltonian_lang.diagnostics``.

Why some tests are xfail
------------------------
Some of these rejections **do not happen**. From the required list: a symbol may take a
distribution family's name, and a concept cycle of length >= 2 is not detected (only
``A extends A`` is). Probing turned up four more the list did not ask for: cross-role
constraints such as ``Uniform(lower := 5.0, upper := 1.0)``, a ``prior`` on an ``obs``,
``infer mle`` with no likelihood, and ``UnknownType`` surviving a clean check.

Those tests are marked ``xfail(strict=True)`` with the reason recorded inline and in
``audits/RED_TEAM_REPORT.md``. They are *not* weakened to pass. ``strict=True`` means the
suite fails loudly the day someone fixes the compiler without updating this file, which is
the behaviour you want from a red-team suite: it must notice good news too.

Provenance of the xfail claims
------------------------------
Every ``xfail`` reason below records a behaviour **measured** against the source tree
fingerprinted as::

    SRC_TREE_SHA256 = 6640d1a22a31fcb5aad75ca25d01a7a8d8ce116003e3922309a005ea44ec15dc
    (sha256 over sorted src/**/*.py contents, measured 2026-08-04T20:12:47)

The tree was being edited by another author while this suite was written, and several
defects found earlier in the session were fixed before it was finished. Because
``xfail(strict=True)`` turns a fix into a *failure*, this suite self-reports when it has
gone stale. That is the intended behaviour: re-run it, and update the reasons from the new
measurement rather than from memory.

Running::

    .venv/bin/python -m pytest tests/adversarial -q
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source, content_hash


def codes(src: str) -> list[str]:
    return [d.code for d in compile_source(src).diagnostics.errors]


def assert_rejected_with(src: str, code: str) -> None:
    result = compile_source(src)
    got = [d.code for d in result.diagnostics.errors]
    assert not result.ok(), (
        f"expected rejection with {code}, but the program compiled clean:\n{src}"
    )
    assert code in got, f"expected {code}, got {got}\n{src}"


# ---------------------------------------------------------------------------
# 1. negative standard deviation
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_negative_standard_deviation_is_rejected():
    assert_rejected_with(
        "module M\n"
        "param sigma : PositiveReal = -1.0\n"
        "var X : RandomVariable[Real]\n"
        "law X ~ Normal(location := 0.0, scale := sigma)\n",
        "HML-T402",
    )


@pytest.mark.adversarial
def test_negative_scale_literal_in_distribution_is_rejected():
    assert_rejected_with(
        "module M\n"
        "var X : RandomVariable[Real]\n"
        "law X ~ Normal(location := 0.0, scale := -1.0)\n",
        "HML-T413",
    )


@pytest.mark.adversarial
def test_positive_scale_is_accepted_control():
    """False-alarm control for the two rejections above: the VALID form must still
    compile. A checker that rejects the negative case by rejecting everything would
    pass those two tests and fail this one."""
    result = compile_source(
        "module M\n"
        "param sigma : PositiveReal\n"
        "var X : RandomVariable[Real]\n"
        "law X ~ Normal(location := 0.0, scale := sigma)\n"
    )
    assert result.ok(), result.diagnostics.render()


# ---------------------------------------------------------------------------
# 2. unbound symbol
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_unbound_symbol_is_rejected():
    assert_rejected_with(
        "module M\nvar x : Real\nrequire x + y > 0.0\n",
        "HML-N301",
    )


@pytest.mark.adversarial
def test_unbound_law_target_is_rejected():
    assert_rejected_with(
        "module M\nlaw NotDeclared ~ Normal(location := 0.0, scale := 1.0)\n",
        "HML-N301",
    )


# ---------------------------------------------------------------------------
# 3. shadowed index
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_shadowed_index_is_rejected():
    assert_rejected_with(
        "module M\nindex i : Natural\nrequire forall i : Natural . i > 0\n",
        "HML-N302",
    )


@pytest.mark.adversarial
def test_nested_quantifier_shadowing_is_rejected():
    assert_rejected_with(
        "module M\nrequire forall x : Real . exists x : Real . x > 0.0\n",
        "HML-N302",
    )


# ---------------------------------------------------------------------------
# 4. conflicting type declaration
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_conflicting_type_declaration_is_rejected():
    assert_rejected_with(
        "module M\nparam rate : PositiveReal\nparam rate : Real\n",
        "HML-N303",
    )


@pytest.mark.adversarial
def test_declaration_value_outside_declared_type_is_rejected():
    assert_rejected_with(
        "module M\nparam p : Probability = 4.0\n",
        "HML-T402",
    )


# ---------------------------------------------------------------------------
# 5. ambiguous conditioning
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_two_laws_for_one_symbol_is_rejected():
    """A symbol with two probability laws has an ambiguous conditional structure."""
    assert_rejected_with(
        "module M\n"
        "param theta : Probability\n"
        "obs y : Natural\n"
        "likelihood y | theta ~ Poisson(rate := 1.0)\n"
        "likelihood y | theta ~ Poisson(rate := 2.0)\n",
        "HML-S601",
    )


@pytest.mark.adversarial
def test_conditioning_on_an_unbound_symbol_is_rejected():
    assert_rejected_with(
        "module M\nobs y : Natural\nlikelihood y | nowhere ~ Poisson(rate := 1.0)\n",
        "HML-N301",
    )


@pytest.mark.adversarial
def test_posterior_without_a_prior_is_rejected():
    assert_rejected_with(
        "module M\nparam theta : Probability\ninfer posterior theta\n",
        "HML-S604",
    )


# ---------------------------------------------------------------------------
# 6. reversed quantifier scope must NOT hash-equal the forward form
# ---------------------------------------------------------------------------

FORWARD = "module ScopePair\nrequire forall x : Real . exists y : Real . y > x\n"
REVERSED = "module ScopePair\nrequire exists y : Real . forall x : Real . y > x\n"


@pytest.mark.adversarial
def test_reversed_quantifier_scope_has_a_different_hash():
    assert content_hash(FORWARD) != content_hash(REVERSED), (
        "forall-exists and exists-forall collapsed to the same canonical hash; "
        "quantifier order is not part of object identity, which falsifies H2's premise"
    )


@pytest.mark.adversarial
def test_negation_position_changes_the_hash_at_equal_prefix():
    """Same quantifier prefix, different negation position, different meaning."""
    outer = "module NegationScope\nrequire not forall x : Real . x > 0.0\n"
    inner = "module NegationScope\nrequire forall x : Real . not x > 0.0\n"
    assert content_hash(outer) != content_hash(inner)


@pytest.mark.adversarial
def test_forward_form_is_stable_under_reserialisation():
    """A control: the forward form must keep its own hash across a print/reparse cycle."""
    result = compile_source(FORWARD)
    assert result.ok(), result.diagnostics.render()
    reprinted = compile_source(result.render("hml").text)
    assert reprinted.ok(), reprinted.diagnostics.render()
    assert result.hash() == reprinted.hash()


# ---------------------------------------------------------------------------
# 7. dimensionally invalid addition
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_dimensionally_invalid_addition_is_rejected():
    assert_rejected_with(
        "module M\n"
        "param work : Quantity[Mass * Length^2 / Time^2]\n"
        "param force : Quantity[Mass * Length / Time^2]\n"
        "def bad := work + force\n",
        "HML-D502",
    )


@pytest.mark.adversarial
def test_dimensionally_invalid_comparison_is_rejected():
    assert_rejected_with(
        "module M\n"
        "param m : Quantity[Mass]\n"
        "param l : Quantity[Length]\n"
        "require m > l\n",
        "HML-D502",
    )


@pytest.mark.adversarial
def test_wrong_asserted_dimension_is_rejected():
    assert_rejected_with(
        "module M\n"
        "param m : Quantity[Mass]\n"
        "param v : Quantity[Length / Time]\n"
        "def ke := 0.5 * m * v^2\n"
        "check dimension ke = Mass * Length^3 / Time^2\n",
        "HML-D504",
    )


@pytest.mark.adversarial
def test_symbolic_exponent_on_a_dimensional_quantity_is_rejected():
    assert_rejected_with(
        "module M\n"
        "param l : Quantity[Length]\n"
        "param n : Real\n"
        "def bad := l^n\n",
        "HML-D505",
    )


# ---------------------------------------------------------------------------
# 8. same name used for a value and for a distribution
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_giving_a_law_to_a_distribution_typed_symbol_is_rejected():
    assert_rejected_with(
        "module M\nvar D : Distribution[Real]\nlaw D ~ Normal(location := 0.0, scale := 1.0)\n",
        "HML-T410",
    )


@pytest.mark.adversarial
def test_arithmetic_on_a_distribution_is_rejected():
    assert_rejected_with(
        "module M\nparam mu : Real\ndef bad := Normal(location := mu, scale := 1.0) + 1.0\n",
        "HML-T430",
    )


@pytest.mark.adversarial
# Was xfail(strict=True) for red-team finding 1.2.. The defect was
# fixed by the Lead Architect in the same session; the strict marker did its
# job by turning the fix into a visible failure. See DECISIONS.md D-016.
def test_symbol_shadowing_a_distribution_family_is_rejected():
    result = compile_source(
        "module M\n"
        "param Normal : Real\n"
        "var X : RandomVariable[Real]\n"
        "law X ~ Normal(location := 0.0, scale := 1.0)\n"
    )
    assert not result.ok(), (
        "'Normal' names both a real parameter and the distribution family used on the "
        "next line, with no diagnostic"
    )


# ---------------------------------------------------------------------------
# 9. unsupported backend construct
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_unknown_distribution_family_is_rejected():
    assert_rejected_with(
        "module M\n"
        "var X : RandomVariable[Real]\n"
        "law X ~ Wiener(drift := 0.0, diffusion := 1.0)\n",
        "HML-T412",
    )


@pytest.mark.adversarial
def test_unknown_function_is_rejected():
    assert_rejected_with(
        "module M\nparam x : Real\ndef bad := besselj(x)\n",
        "HML-N306",
    )


@pytest.mark.adversarial
def test_an_unknown_backend_raises_rather_than_emitting_nonsense():
    result = compile_source("module M\nvar x : Real\n")
    with pytest.raises(KeyError):
        result.render("coq")


@pytest.mark.adversarial
def test_lean_backend_emits_sorry_and_never_claims_a_proof():
    """The Lean lowering must not present an unproved statement as proved.

    Design freeze section 8 rules out proof search of any kind. A backend that emitted a
    closed proof term would be claiming something the system cannot do, so the presence of
    `sorry` is a correctness requirement, not a limitation to be tidied away later.
    """
    result = compile_source(
        "module M\nrequire forall x : Real . exists y : Real . y > x\n"
    )
    assert result.ok(), result.diagnostics.render()
    text = result.render("lean").text
    assert "sorry" in text, "Lean output closes an obligation without a proof"


@pytest.mark.adversarial
def test_stan_backend_refuses_constructs_it_cannot_express():
    """A lowering that silently drops what it cannot represent is worse than one that
    fails. Dimensional quantities have no Stan counterpart; the backend must say so
    rather than emit a bare real and lose the dimension."""
    from hamiltonian_lang.backends import Unsupported

    result = compile_source(
        "module M\n"
        "param m : Quantity[Mass]\n"
        "param v : Quantity[Length / Time]\n"
        "def ke := 0.5 * m * v^2\n"
        "check dimension ke = Mass * Length^2 / Time^2\n"
    )
    assert result.ok(), result.diagnostics.render()
    try:
        text = result.render("stan").text
    except Unsupported:
        return  # refusing is the correct behaviour
    # If it did emit, it must at least not pretend the dimension survived.
    assert "Quantity" in text or "dimension" in text.lower(), (
        "Stan output silently dropped the dimensional information with no marker"
    )


# ---------------------------------------------------------------------------
# 10. cyclic concept definition
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_self_extending_concept_is_rejected():
    assert_rejected_with(
        "module M\n"
        "concept A extends A\n"
        "    parameter p : Real\n"
        "    invariant i := p > 0.0\n"
        "end\n",
        "HML-S602",
    )


@pytest.mark.adversarial
# Was xfail(strict=True) for red-team finding 1.3.. The defect was
# fixed by the Lead Architect in the same session; the strict marker did its
# job by turning the fix into a visible failure. See DECISIONS.md D-016.
def test_mutually_cyclic_concepts_are_rejected():
    result = compile_source(
        "module M\n"
        "concept A extends B\n"
        "    parameter p : Real\n"
        "    invariant i := p > 0.0\n"
        "end\n"
        "concept B extends A\n"
        "    parameter q : Real\n"
        "    invariant j := q > 0.0\n"
        "end\n"
    )
    assert not result.ok(), "A extends B extends A compiled clean"


@pytest.mark.adversarial
# Was xfail(strict=True) for red-team finding 1.4.. The defect was
# fixed by the Lead Architect in the same session; the strict marker did its
# job by turning the fix into a visible failure. See DECISIONS.md D-016.
def test_cyclic_definitions_are_rejected():
    result = compile_source(
        "module M\nparam a : Real\ndef f := g + a\ndef g := f + a\n"
    )
    assert not result.ok(), "mutually recursive definitions compiled clean"


# ---------------------------------------------------------------------------
# 11. false semantic equivalence
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_swapped_distribution_roles_are_not_equivalent():
    """Both forms type-check (both parameters are PositiveReal). Only the role labels
    distinguish them, so the canonical form must distinguish them too."""
    a = ("module RoleAssignment\nparam first : PositiveReal\nparam second : PositiveReal\n"
         "var Z : RandomVariable[Real]\nlaw Z ~ Normal(location := first, scale := second)\n")
    b = ("module RoleAssignment\nparam first : PositiveReal\nparam second : PositiveReal\n"
         "var Z : RandomVariable[Real]\nlaw Z ~ Normal(location := second, scale := first)\n")
    assert content_hash(a) != content_hash(b)


@pytest.mark.adversarial
def test_role_order_is_not_part_of_identity():
    """The converse: writing the same roles in the other textual order is the SAME object."""
    a = ("module RoleAssignment\nparam first : PositiveReal\nparam second : PositiveReal\n"
         "var Z : RandomVariable[Real]\nlaw Z ~ Normal(location := first, scale := second)\n")
    c = ("module RoleAssignment\nparam first : PositiveReal\nparam second : PositiveReal\n"
         "var Z : RandomVariable[Real]\nlaw Z ~ Normal(scale := second, location := first)\n")
    assert content_hash(a) == content_hash(c)


@pytest.mark.adversarial
def test_assume_and_require_are_not_the_same_object():
    a = "module M\nvar x : Real\nassume x > 0.0\n"
    b = "module M\nvar x : Real\nrequire x > 0.0\n"
    assert content_hash(a) != content_hash(b)


@pytest.mark.adversarial
def test_different_distribution_families_are_not_equivalent():
    a = ("module M\nvar X : RandomVariable[Real]\n"
         "law X ~ Normal(location := 0.0, scale := 1.0)\n")
    b = ("module M\nvar X : RandomVariable[Real]\n"
         "law X ~ Cauchy(location := 0.0, scale := 1.0)\n")
    assert content_hash(a) != content_hash(b)


# ---------------------------------------------------------------------------
# 12. positional distribution arguments
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_positional_distribution_arguments_are_rejected():
    assert_rejected_with(
        "module M\nvar X : RandomVariable[Real]\nlaw X ~ Normal(0.0, 1.0)\n",
        "HML-P234",
    )


@pytest.mark.adversarial
def test_partially_positional_distribution_arguments_are_rejected():
    assert_rejected_with(
        "module M\nvar X : RandomVariable[Real]\nlaw X ~ Normal(0.0, scale := 1.0)\n",
        "HML-P234",
    )


@pytest.mark.adversarial
def test_a_repeated_role_is_rejected():
    assert_rejected_with(
        "module M\n"
        "var X : RandomVariable[Real]\n"
        "law X ~ Normal(location := 0.0, location := 1.0, scale := 1.0)\n",
        "HML-P235",
    )


# ---------------------------------------------------------------------------
# 13. Normal(variance := ...)
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_normal_parameterised_by_variance_is_rejected():
    assert_rejected_with(
        "module M\n"
        "param mu : Real\n"
        "param v : PositiveReal\n"
        "var X : RandomVariable[Real]\n"
        "law X ~ Normal(location := mu, variance := v)\n",
        "HML-T415",
    )


@pytest.mark.adversarial
@pytest.mark.parametrize("bad_role", ["sd", "stddev", "sigma", "mean", "mu", "loc"])
def test_common_misparameterisations_are_rejected(bad_role: str):
    src = (
        "module M\n"
        "param a : Real\n"
        "param b : PositiveReal\n"
        "var X : RandomVariable[Real]\n"
        f"law X ~ Normal({bad_role} := b, scale := b)\n"
    )
    got = codes(src)
    assert not compile_source(src).ok(), f"{bad_role!r} was accepted as a Normal role"
    assert any(c in got for c in ("HML-T415", "HML-T416")), got


@pytest.mark.adversarial
def test_exponential_parameterised_by_lambda_is_rejected():
    assert_rejected_with(
        "module M\n"
        "var W : RandomVariable[PositiveReal]\n"
        "law W ~ Exponential(lambda := 0.25)\n",
        "HML-T415",
    )


@pytest.mark.adversarial
def test_missing_required_role_is_rejected():
    assert_rejected_with(
        "module M\nparam mu : Real\nvar X : RandomVariable[Real]\n"
        "law X ~ Normal(location := mu)\n",
        "HML-T414",
    )


# ---------------------------------------------------------------------------
# 14. a distribution compared to a value
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_distribution_compared_to_a_value_is_rejected():
    assert_rejected_with(
        "module M\nparam mu : Real\nrequire Normal(location := mu, scale := 1.0) > 0.0\n",
        "HML-T428",
    )


@pytest.mark.adversarial
def test_distribution_equated_to_a_value_is_rejected():
    assert_rejected_with(
        "module M\nparam mu : Real\nrequire Normal(location := mu, scale := 1.0) = mu\n",
        "HML-T428",
    )


# ---------------------------------------------------------------------------
# 15. chained comparison
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_chained_comparison_is_rejected():
    assert_rejected_with(
        "module M\nvar a : Real\nvar b : Real\nvar c : Real\nrequire a < b < c\n",
        "HML-P230",
    )


@pytest.mark.adversarial
def test_chained_equality_is_rejected():
    assert_rejected_with(
        "module M\nvar a : Real\nvar b : Real\nvar c : Real\nrequire a = b = c\n",
        "HML-P230",
    )


@pytest.mark.adversarial
def test_explicit_conjunction_is_accepted_control():
    result = compile_source(
        "module M\nvar a : Real\nvar b : Real\nvar c : Real\n"
        "require a < b and b < c\n"
    )
    assert result.ok(), result.diagnostics.render()


# ---------------------------------------------------------------------------
# 16. a concept with no invariant and no example
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_concept_without_invariant_or_example_is_rejected():
    assert_rejected_with(
        "module M\nconcept Vague\n    parameter p : Real\nend\n",
        "HML-S603",
    )


@pytest.mark.adversarial
def test_concept_with_only_an_example_is_accepted_control():
    result = compile_source(
        "module M\nconcept Grounded\n"
        "    parameter p : Real\n"
        "    example unit := p = 1.0\n"
        "end\n"
    )
    assert result.ok(), result.diagnostics.render()


@pytest.mark.adversarial
def test_concept_extending_an_unknown_concept_is_rejected():
    assert_rejected_with(
        "module M\nconcept A extends DoesNotExist\n"
        "    parameter p : Real\n"
        "    invariant i := p > 0.0\n"
        "end\n",
        "HML-N305",
    )


@pytest.mark.adversarial
def test_duplicate_concept_is_rejected():
    assert_rejected_with(
        "module M\n"
        "concept A\n    parameter p : Real\n    invariant i := p > 0.0\nend\n"
        "concept A\n    parameter q : Real\n    invariant j := q > 0.0\nend\n",
        "HML-N304",
    )


# ---------------------------------------------------------------------------
# Additional holes found while probing. Not on the required list; recorded because
# a red-team suite that only tests the list it was handed is not a red team.
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_sqrt_of_a_negative_literal_is_rejected():
    assert not compile_source("module M\ndef d := sqrt(-4.0)\n").ok()


@pytest.mark.adversarial
def test_log_of_a_negative_literal_is_rejected():
    assert not compile_source("module M\ndef d := log(-1.0)\n").ok()


@pytest.mark.adversarial
def test_probability_literals_respect_the_refinement_poset():
    """The scalar order is a poset: PositiveReal and Probability are incomparable.

    A literal in the unit interval must inhabit Probability; a literal above 1 must not.
    Getting either direction wrong collapses the poset into a chain, which the design
    freeze section 4 explicitly forbids.
    """
    assert compile_source("module M\nparam p : Probability = 0.5\n").ok()
    assert "HML-T402" in codes("module M\nparam p : Probability = 2.0\n")
    assert "HML-T402" in codes("module M\nparam p : Probability = -0.5\n")


@pytest.mark.adversarial
# Was xfail(strict=True) for red-team finding 1.5.. The defect was
# fixed by the Lead Architect in the same session; the strict marker did its
# job by turning the fix into a visible failure. See DECISIONS.md D-016.
def test_uniform_with_reversed_bounds_is_rejected_or_obligated():
    result = compile_source(
        "module M\n"
        "var X : RandomVariable[Real]\n"
        "law X ~ Uniform(lower := 5.0, upper := 1.0)\n"
    )
    obligation_text = " ".join(o.description for o in result.obligations)
    assert (not result.ok()) or ("lower" in obligation_text and "upper" in obligation_text), (
        "Uniform(5.0, 1.0) compiled clean and generated no lower <= upper obligation"
    )


@pytest.mark.adversarial
# Was xfail(strict=True) for red-team finding 1.6.. The defect was
# fixed by the Lead Architect in the same session; the strict marker did its
# job by turning the fix into a visible failure. See DECISIONS.md D-016.
def test_a_prior_on_observed_data_is_rejected():
    result = compile_source(
        "module M\nobs y : Real = 3.0\nprior y ~ Normal(location := 0.0, scale := 1.0)\n"
    )
    assert not result.ok(), "a 'prior' was accepted on an 'obs' declaration"


@pytest.mark.adversarial
# Was xfail(strict=True) for red-team finding 1.7.. The defect was
# fixed by the Lead Architect in the same session; the strict marker did its
# job by turning the fix into a visible failure. See DECISIONS.md D-016.
def test_mle_without_a_likelihood_is_rejected():
    result = compile_source("module M\nparam t : Real\ninfer mle t\n")
    assert not result.ok(), "'infer mle' on a symbol with no probability law compiled clean"


@pytest.mark.adversarial
# Was xfail(strict=True) for red-team finding 1.8.. The defect was
# fixed by the Lead Architect in the same session; the strict marker did its
# job by turning the fix into a visible failure. See DECISIONS.md D-016.
def test_unknown_type_does_not_survive_a_successful_check():
    from hamiltonian_lang.ast.nodes import walk
    from hamiltonian_lang.types import UnknownType

    result = compile_source(
        "module M\n"
        "index K : Natural\n"
        "var w : Vector[Probability, K]\n"
        "require sum(w) = 1.0\n"
    )
    assert result.ok(), result.diagnostics.render()
    unknown = [n for n in walk(result.module)
               if isinstance(getattr(n, "type_", None), UnknownType)]
    assert not unknown, f"{len(unknown)} node(s) kept an UnknownType after a clean check"
