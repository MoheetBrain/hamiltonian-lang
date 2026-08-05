"""The constitutional semantics of Hamiltonian Lang, in one place.

Every other test file asks whether a feature works. This one asks whether the
distinctions the language exists to preserve are still preserved — the prohibited
conflations of `CLAUDE.md`, the poset commitments of `docs/design/V0_DESIGN_FREEZE.md`,
and the enforcement claims of `docs/evaluation/V1_FREEZE_MANIFEST.md`. A feature can
regress and be caught by its own test; a *conflation* can be reintroduced by a change
that every feature test still passes, because each half of it looks reasonable alone.

Runs standalone::

    .venv/bin/python -m pytest tests/constitutional -q

and as part of `./scripts/conformance.sh`, which runs the whole suite.

Attribution discipline
----------------------
Three hypotheses are under test in this project and they can come apart:

* **H1** — the representation as *input* to a model;
* **H2** — the representation as a *reasoning workspace*;
* **H3** — *verifier-guided repair*.

Nothing in this file measures any of them. Every assertion here is about the compiler
alone, with no model in the loop, and a pass is evidence that a distinction is enforced —
never evidence that enforcing it helps a model. Where a section touches machinery that a
later H3 result would depend on (diagnostics), it says so and asserts the property that
keeps H3 measurable, which is that a diagnostic must not contain the answer.

Where a distinction is enforced in Python and NOT in the language, the test says so in
its name and asserts both halves. A layer that works only for callers who write Python
is not a property of Hamiltonian Lang.
"""

from __future__ import annotations

import json

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends import render
from hamiltonian_lang.backends.canonical import canonical_json, content_hash

pytestmark = pytest.mark.adversarial


def compile_hml(*lines: str):
    return compile_source("module M\n" + "\n".join(lines) + "\n", "<constitution>")


def codes(*lines: str) -> list[str]:
    return [d.code for d in compile_hml(*lines).diagnostics.items]


def rejected(*lines: str) -> list[str]:
    result = compile_hml(*lines)
    assert not result.ok(), (
        "this program must be rejected:\n  " + "\n  ".join(lines)
    )
    return [d.code for d in result.diagnostics.items]


def accepted(*lines: str):
    result = compile_hml(*lines)
    assert result.ok(), result.diagnostics.render()
    return result


def hash_of(*lines: str) -> str:
    return content_hash(accepted(*lines).module)


# ===========================================================================
# 1. Distribution[T] is not RandomVariable[T] and neither is T
# ===========================================================================


def test_a_distribution_may_not_inhabit_its_own_support():
    """A law is not a value drawn from it. Design freeze §4."""
    assert "HML-T403" in rejected(
        "param theta : Probability",
        "def bad : Probability := Beta(alpha := 1, beta := 1)",
    )


def test_a_distribution_may_not_be_given_a_law():
    assert "HML-T410" in rejected(
        "param d : Distribution[Real]",
        "law d ~ Normal(location := 0.0, scale := 1.0)",
    )


def test_arithmetic_on_a_law_is_not_defined():
    assert "HML-T430" in rejected(
        "param d : Distribution[Real]", "def bad : Real := d + 1.0"
    )


def test_a_law_may_not_be_compared_with_a_value():
    assert "HML-T428" in rejected(
        "param d : Distribution[Real]", "require d > 0.0"
    )


def test_a_law_may_not_be_summarised_as_if_it_were_a_value():
    """`mean(d)` on a law is rejected: a law is not an aggregate of values.

    Note for the record: the checker also carries `HML-T428` for `expectation(<law>)`,
    and that branch is **unreachable from HML source** — `expectation` is a reserved
    keyword (the `infer expectation` query), so `expectation(d)` is a parse error before
    the checker sees it. The reachable route is asserted here; the unreachable one is
    named so nobody cites `HML-T428` as a live surface guarantee.
    """
    assert "HML-P231" in rejected(
        "param d : Distribution[Real]", "def m : Real := expectation(d)"
    )
    assert "HML-T427" in rejected(
        "param d : Distribution[Real]", "def m : Real := mean(d)"
    )


def test_a_random_variable_is_not_a_value_of_its_codomain():
    assert "HML-T403" in rejected(
        "rv y : RandomVariable[Real]", "def bad : Real := y"
    )


def test_the_three_are_distinct_in_the_canonical_form():
    """Not merely rejected at different sites — distinct identities."""
    identities = {
        "value": hash_of("param a : Real"),
        "random variable": hash_of("param a : RandomVariable[Real]"),
        "law": hash_of("param a : Distribution[Real]"),
    }
    assert len(set(identities.values())) == 3, identities


def test_no_subtyping_path_exists_between_them():
    from hamiltonian_lang.types import (
        DistributionType,
        RandomVariableType,
        ScalarType,
        is_subtype,
    )

    real = ScalarType("Real")
    rv = RandomVariableType(real)
    law = DistributionType(real)
    for a, b in ((rv, real), (real, rv), (law, real), (real, law), (rv, law), (law, rv)):
        assert not is_subtype(a, b), f"{a.render()} became a subtype of {b.render()}"


# ===========================================================================
# 2. PValue is not Probability
# ===========================================================================


def test_a_p_value_is_not_a_probability_in_either_direction():
    assert "HML-T403" in rejected(
        "const pv : PValue := 0.05", "def posterior_h0 : Probability := pv"
    )
    assert "HML-T403" in rejected(
        "const p : Probability = 0.5", "def observed_pvalue : PValue := p"
    )


def test_a_p_value_is_not_a_posterior_probability():
    """The prosecutor's fallacy, made unrepresentable in a program that states kinds."""
    result = compile_hml(
        "const pv : PValue := 0.05", "def post : PosteriorProbability := pv"
    )
    assert not result.ok()
    hit = next(d for d in result.diagnostics.items if d.code == "HML-T403")
    assert "prosecutor's fallacy" in " ".join(hit.notes)


def test_the_three_unit_interval_kinds_have_distinct_identities():
    identities = {
        kind: hash_of(f"const q : {kind} := 0.05")
        for kind in ("Probability", "PValue", "PosteriorProbability")
    }
    assert len(set(identities.values())) == 3, identities


def test_a_mis_declared_p_value_is_admitted_and_that_limit_is_stated():
    """The residual, asserted so it cannot be reported as closed.

    Both sides genuinely are `Probability`; the author chose the wrong type. This is a
    modelling error and no type system detects it. Enforcement begins when the program
    states its kinds.
    """
    assert compile_hml(
        "param p_value : Probability", "def posterior_h0 : Probability := p_value"
    ).ok()


# ===========================================================================
# 3. Definition binding is not mathematical equality
# ===========================================================================


def test_a_definition_requires_the_binding_operator():
    """`=` where `:=` is meant is the classic silent-meaning slip."""
    hits = rejected("param x : Real", "def f = x")
    assert "HML-P207" in hits


def test_binding_and_equality_have_different_identities():
    """`def a := b` introduces a name. `require a = b` asserts a proposition."""
    binding = hash_of("param b : Real", "def a : Real := b")
    equality = hash_of("param b : Real", "param a : Real", "require a = b")
    assert binding != equality


def test_a_binding_is_serialised_as_a_definition_not_as_a_comparison():
    doc = json.loads(canonical_json(accepted("param b : Real", "def a : Real := b").module))
    kinds = [s["kind"] for s in doc["statements"]]
    assert "Definition" in kinds and "Constraint" not in kinds

    doc = json.loads(
        canonical_json(accepted("param a : Real", "param b : Real", "require a = b").module)
    )
    kinds = [s["kind"] for s in doc["statements"]]
    assert "Constraint" in kinds and "Definition" not in kinds


def test_a_circular_definition_is_rejected_but_a_circular_equation_is_not():
    """The distinction has consequences, which is what makes it a real distinction.

    `def a := a + 1` has no reduction and is rejected. `require a = a + 1` is a
    perfectly well-formed (unsatisfiable) constraint and is a proof obligation, not a
    definition error.
    """
    assert "HML-S606" in rejected("def a : Real := a + 1")
    assert compile_hml("param a : Real", "require a = a + 1").ok()


# ===========================================================================
# 4. Implication is not equivalence (and is not correlation, and is not causation)
# ===========================================================================


def test_implication_and_equivalence_have_different_identities():
    implication = hash_of("param p : Bool", "param q : Bool", "require p => q")
    equivalence = hash_of("param p : Bool", "param q : Bool", "require p <=> q")
    assert implication != equivalence


def test_implication_is_not_symmetric_in_the_canonical_form():
    forward = hash_of("param p : Bool", "param q : Bool", "require p => q")
    backward = hash_of("param p : Bool", "param q : Bool", "require q => p")
    assert forward != backward, "p => q and q => p canonicalised the same"


def test_both_sides_of_an_implication_must_be_truth_valued():
    """Arithmetic on either side would make it a correlation-shaped statement."""
    hits = rejected("param x : Real", "param q : Bool", "require x => q")
    assert "HML-T421" in hits
    diagnostic = next(
        d for d in compile_hml("param x : Real", "param q : Bool", "require x => q")
        .diagnostics.items
        if d.code == "HML-T421"
    )
    assert "not correlation" in " ".join(diagnostic.notes)


def test_the_operators_are_distinct_at_the_ast_level():
    from hamiltonian_lang.ast.nodes import LogicalOp, walk

    def op_of(source_line: str) -> str:
        module = accepted("param p : Bool", "param q : Bool", source_line).module
        return next(n.op for n in walk(module) if isinstance(n, LogicalOp))

    assert op_of("require p => q") == "implies"
    assert op_of("require p <=> q") == "iff"
    assert op_of("require p implies q") == "implies"
    assert op_of("require p iff q") == "iff"


# ===========================================================================
# 5 & 6. Estimated is not proved; fail_to_reject is not a proof of the null
#
# ENFORCED IN PYTHON ONLY. `hamiltonian_lang.v1.epistemic` is a standalone API that no
# module on the `hml check` path imports, so no HML program can invoke it or be judged
# by it. Both halves are asserted: the contract holds, and the surface does not exist.
# ===========================================================================


def test_evidence_does_not_discharge_a_proof_goal_in_the_python_layer():
    from hamiltonian_lang.v1.epistemic import (
        DISCHARGES_GOALS,
        EpistemicClaim,
        EpistemicStatus,
        Justification,
        coercion_allowed,
    )

    for status in (EpistemicStatus.ESTIMATED, EpistemicStatus.FAIL_TO_REJECT):
        claim = EpistemicClaim(
            status,
            "H0",
            {"null": "H0", "alpha": "0.05", "p_value": "0.18",
             "estimator": "xbar", "sample": "y"},
        )
        assert claim.justification is Justification.EVIDENCE
        assert not claim.discharges_goals()

    assert DISCHARGES_GOALS[Justification.PROOF] is True
    ok, reason = coercion_allowed(Justification.EVIDENCE, Justification.PROOF)
    assert not ok
    assert "does not prove H0" in reason


def test_failing_to_reject_renders_with_its_caveat_attached():
    """The caveat is carried by the type, not by the author remembering to add it."""
    from hamiltonian_lang.v1.epistemic import EpistemicClaim, EpistemicStatus

    claim = EpistemicClaim(
        EpistemicStatus.FAIL_TO_REJECT,
        "H0",
        {"null": "H0", "alpha": "0.05", "p_value": "0.18"},
    )
    assert "is not evidence that H0 is true" in claim.render_english()


def test_a_test_result_without_its_context_is_not_a_statement():
    from hamiltonian_lang.v1.epistemic import (
        ContextError,
        EpistemicClaim,
        EpistemicStatus,
    )

    with pytest.raises(ContextError):
        EpistemicClaim(EpistemicStatus.FAIL_TO_REJECT, "H0", {})


@pytest.mark.parametrize(
    "name", ["Evidence", "Proof", "Credence", "Justification", "Assumption"]
)
def test_the_epistemic_vocabulary_is_not_reachable_from_hml_source(name):
    """The honest half. `prove fail_to_reject(...)` is not expressible, because
    `fail_to_reject` is not expressible — not because it is rejected."""
    assert "HML-T440" in rejected(f"param x : {name}")


def test_no_compiler_module_can_reach_the_epistemic_layer():
    """Restated here because §5-6 above would otherwise read as language properties."""
    import ast
    from pathlib import Path

    root = Path("src/hamiltonian_lang")
    offenders = []
    for path in sorted(root.rglob("*.py")):
        if (root / "v1") in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                relative = "." * node.level + (node.module or "")
                if relative.endswith(".v1") or (node.module or "").startswith(
                    "hamiltonian_lang.v1"
                ):
                    offenders.append(f"{path}:{node.lineno}")
            elif isinstance(node, ast.Import):
                offenders.extend(
                    f"{path}:{node.lineno}"
                    for a in node.names
                    if a.name.startswith("hamiltonian_lang.v1")
                )
    assert not offenders, offenders


# ===========================================================================
# 7. Dimensions stay compatible
# ===========================================================================


def test_quantities_of_different_dimensions_may_not_be_added():
    assert "HML-D502" in rejected(
        "param m : Quantity[Mass]",
        "param l : Quantity[Length]",
        "def bad : Quantity[Mass] := m + l",
    )


def test_quantities_of_different_dimensions_may_not_be_compared():
    assert "HML-D502" in rejected(
        "param m : Quantity[Mass]", "param l : Quantity[Length]", "require m > l"
    )


def test_an_asserted_dimension_is_checked_against_the_computed_one():
    assert "HML-D504" in rejected(
        "param m : Quantity[Mass]",
        "param v : Quantity[Length / Time]",
        "def ke : Quantity[Mass * Length^2 / Time^2] := 0.5 * m * v^2",
        "check dimension ke = Mass * Length^3 / Time^2",
    )


def test_dimensional_algebra_is_exact_not_floating():
    from fractions import Fraction

    from hamiltonian_lang.types import Dimension

    half = Dimension.of(Length=1).power(Fraction(1, 2))
    assert half.power(2) == Dimension.of(Length=1)
    assert half.as_dict()["Length"] == Fraction(1, 2)


def test_a_dimension_variable_is_never_silently_dimensionless():
    from hamiltonian_lang.types import Dimension

    unknown = Dimension.variable("D")
    assert not unknown.is_dimensionless()
    assert not unknown.is_concrete()


def test_a_typo_in_a_dimension_name_is_an_error_not_a_variable():
    """`Quantity[Lenght]` must not silently become an unknown dimension."""
    assert "HML-D501" in rejected("param x : Quantity[Lenght]")


def test_dimensions_survive_canonicalisation_distinctly():
    assert hash_of("param x : Quantity[Mass]") != hash_of("param x : Quantity[Length]")


# ===========================================================================
# 8. Binder scope and quantifier order are preserved
# ===========================================================================


def test_alpha_renaming_does_not_change_identity():
    a = hash_of("require forall x : Real . exists y : Real . y > x")
    b = hash_of("require forall aardvark : Real . exists zebra : Real . zebra > aardvark")
    assert a == b


def test_quantifier_order_does_change_identity():
    """H2's structural claim, asserted on the compiler alone."""
    forall_exists = hash_of("require forall x : Real . exists y : Real . y > x")
    exists_forall = hash_of("require exists y : Real . forall x : Real . y > x")
    assert forall_exists != exists_forall


def test_a_binder_does_not_escape_its_scope():
    assert "HML-N301" in rejected(
        "require forall x : Real . x > 0.0", "require x > 1.0"
    )


def test_shadowing_is_rejected_rather_than_warned_about():
    """D-006. A warning does not prevent a silent scope change."""
    assert "HML-N302" in rejected(
        "require forall x : Real . forall x : Real . x > 0.0"
    )


def test_a_quantified_variable_must_declare_its_domain():
    assert "HML-P236" in rejected("require forall x . x > 0.0")


def test_the_canonical_form_carries_no_binder_spelling():
    doc = canonical_json(
        accepted("require forall x : Real . x > 0.0").module, include_names=False
    )
    assert '"x"' not in doc
    assert "sym:#" in doc


# ===========================================================================
# 9. Distribution roles stay explicit
# ===========================================================================


def test_positional_distribution_arguments_are_a_parse_error():
    """D-003, the load-bearing grammar decision."""
    assert "HML-P234" in rejected(
        "param mu : Real",
        "param sigma : PositiveReal",
        "rv y : RandomVariable[Real]",
        "law y ~ Normal(mu, sigma)",
    )


def test_a_recognised_but_wrong_role_names_the_confusion():
    """`variance` where `scale` is meant is the error D-003 exists to make visible."""
    result = compile_hml(
        "param mu : Real",
        "param s : PositiveReal",
        "rv y : RandomVariable[Real]",
        "law y ~ Normal(location := mu, variance := s)",
    )
    assert not result.ok()
    hit = next(d for d in result.diagnostics.items if d.code == "HML-T415")
    assert "scale" in (hit.expected or "")


def test_an_unrecognised_role_is_rejected():
    assert "HML-T416" in rejected(
        "param mu : Real",
        "param sigma : PositiveReal",
        "rv y : RandomVariable[Real]",
        "law y ~ Normal(location := mu, spread := sigma)",
    )


def test_a_missing_role_is_rejected():
    assert "HML-T414" in rejected(
        "param mu : Real",
        "rv y : RandomVariable[Real]",
        "law y ~ Normal(location := mu)",
    )


def test_role_order_is_not_identity_but_role_naming_is():
    """Reordering roles is the same law; renaming one is a different law."""
    def law(roles: str) -> str:
        return f"law y ~ Normal({roles})"

    # Both parameters are PositiveReal, so every arrangement below type-checks and the
    # only thing separating them is which role each symbol fills.
    prefix = ("param a : PositiveReal", "param b : PositiveReal",
              "rv y : RandomVariable[Real]")
    forward = hash_of(*prefix, law("location := a, scale := b"))
    reversed_ = hash_of(*prefix, law("scale := b, location := a"))
    assert forward == reversed_, "writing the roles in a different order changed identity"

    swapped = hash_of(*prefix, law("location := b, scale := a"))
    assert forward != swapped, "swapping which symbol fills which role left identity alone"


def test_a_cross_role_constraint_is_decided_when_it_can_be():
    assert "HML-T417" in rejected(
        "rv u : RandomVariable[Real]", "law u ~ Uniform(lower := 5, upper := 1)"
    )


# ===========================================================================
# 10. Unknown types fail loudly
# ===========================================================================


def test_a_hallucinated_type_name_is_rejected():
    assert "HML-T440" in rejected("param x : Frobnicator")


def test_a_truncated_type_name_is_rejected_with_a_suggestion():
    result = compile_hml("param sigma : Positiv")
    hit = next(d for d in result.diagnostics.items if d.code == "HML-T440")
    assert "PositiveReal" in (hit.correction or "")


def test_an_unbound_name_is_rejected():
    assert "HML-N301" in rejected("def f : Real := undefined_name + 1.0")


def test_an_unknown_function_is_rejected():
    assert "HML-N306" in rejected("def f : Real := nowhere(1.0)")


def test_an_unknown_distribution_family_is_rejected():
    assert "HML-T412" in rejected(
        "rv y : RandomVariable[Real]", "law y ~ Frobnormal(location := 0.0)"
    )


def test_no_untyped_expression_survives_a_clean_check(example):
    """`UnknownType` is permissive on both sides of `is_subtype`, so an Unknown that
    survives makes a comparison against it succeed vacuously. HML-T450 exists for this;
    here it is asserted over the shipped corpus rather than over a probe."""
    from hamiltonian_lang.ast.nodes import Expr, walk
    from hamiltonian_lang.types import UnknownType

    result = compile_source(example.read_text(), str(example))
    if not result.ok():
        pytest.skip(f"{example} does not check")
    untyped = [
        n
        for n in walk(result.module)
        if isinstance(n, Expr) and isinstance(n.type_, UnknownType)
    ]
    assert not untyped, [type(n).__name__ for n in untyped]


# ===========================================================================
# 11. An unsupported backend must not report verification
#
# The worst available failure: output that looks authoritative and is not. No Lean
# toolchain is invoked here — the rejection is textual and happens before Lean runs.
# ===========================================================================


def test_the_lean_backend_closes_every_obligation_with_sorry_and_says_so():
    result = accepted("param x : Real", "prove x = x")
    emitted = render("lean", result.module, result.symbols)
    assert "sorry" in emitted.text
    assert "sorry" in emitted.with_report().lower()


def test_the_lean_verifier_rejects_this_project_s_own_lean_output():
    """A working gate with nothing able to pass through it — stated, not hidden."""
    from hamiltonian_lang.v1.lean_verify import LeanVerdict, verify

    result = accepted("param x : Real", "prove x = x")
    emitted = render("lean", result.module, result.symbols)
    verdict = verify(emitted.text)
    assert verdict.verdict is LeanVerdict.REJECTED_FORBIDDEN_TACTIC
    assert not verdict.verified


def test_a_missing_toolchain_yields_not_attempted_and_never_a_pass():
    from hamiltonian_lang.v1.lean_verify import LeanVerdict, verify

    assert verify("").verdict is LeanVerdict.REJECTED_NO_THEOREM
    assert not verify("").verified
    assert LeanVerdict.NOT_ATTEMPTED is not LeanVerdict.VERIFIED


def test_no_backend_result_can_report_faithfulness_while_declaring_loss():
    from hamiltonian_lang.backends.base import BackendResult, Unsupported

    lossy = BackendResult("probe", "", [Unsupported("c", "why")])
    assert not lossy.faithful
    assert "not fully preserved" in lossy.report()
    assert BackendResult("probe", "").faithful


@pytest.mark.parametrize("target", ["lean", "stan", "sympy", "latex"])
def test_a_backend_declares_its_loss_on_a_construct_it_cannot_carry(target):
    """Every formal target loses part of a probability law. None may drop it silently.

    `english` is excluded and covered separately below: it *can* state a law in prose,
    reports `faithful`, and is honest about that because it declares itself one-way.
    """
    result = accepted(
        "param theta : Probability",
        "rv y : RandomVariable[Bool]",
        "prior theta ~ Beta(alpha := 1, beta := 1)",
        "likelihood y | theta ~ Bernoulli(prob := theta)",
        "infer posterior theta",
    )
    emitted = render(target, result.module, result.symbols)
    assert not emitted.faithful, f"{target} claims a faithful translation of a law"
    assert emitted.unsupported
    for loss in emitted.unsupported:
        assert loss.reason.strip(), f"{target} reported a loss with no reason"
        assert loss.severity in ("dropped", "approximated", "weakened")


def test_the_english_backend_claims_faithfulness_only_alongside_its_one_way_notice():
    """`english` is the one target that reports no loss on a law, because prose can
    state one. That claim is only admissible because the backend also declares that it
    is one-way and is not a source format — a faithful *reading*, not a faithful
    *translation* something downstream could rely on."""
    result = accepted(
        "param theta : Probability",
        "rv y : RandomVariable[Bool]",
        "prior theta ~ Beta(alpha := 1, beta := 1)",
    )
    emitted = render("english", result.module, result.symbols)
    assert emitted.faithful
    joined = " ".join(emitted.notes)
    assert "one-way" in joined and "not parsed back" in joined
    assert "reading aid" in joined


def test_no_backend_exposes_anything_that_could_be_read_as_verification():
    """`BackendResult` must carry no field a caller could mistake for a proof."""
    from dataclasses import fields

    from hamiltonian_lang.backends.base import BackendResult

    names = {f.name for f in fields(BackendResult)}
    forbidden = {"verified", "proved", "valid", "sound", "checked", "certified"}
    assert not (names & forbidden), names & forbidden


# ===========================================================================
# 12. Diagnostics do not leak the answer (keeps H3 measurable)
# ===========================================================================


def test_no_diagnostic_in_this_file_s_rejections_contains_a_repaired_program():
    """H3 measures whether a model can act on a diagnostic. If the diagnostic contains
    the corrected program, a later H3 number measures transcription and would still be
    reported as verifier-guided repair. H1 and H2 are unaffected either way, which is
    exactly why the three must not be collapsed."""
    probes = (
        ("param theta : Probability", "def bad : Probability := Beta(alpha := 1, beta := 1)"),
        ("const pv : PValue := 0.05", "def posterior_h0 : Probability := pv"),
        ("def f(x : Real, y : PositiveReal) : Real := x + y", "def a : Real := f(1.0)"),
        ("param m : Quantity[Mass]", "param l : Quantity[Length]",
         "def bad : Quantity[Mass] := m + l"),
    )
    for lines in probes:
        for d in compile_hml(*lines).diagnostics.items:
            correction = d.correction or ""
            assert not correction.lstrip().startswith(("def ", "const ", "param ")), (
                f"{d.code} offers a complete replacement statement: {correction!r}"
            )
            assert "\n" not in correction, f"{d.code} offers a multi-line correction"
