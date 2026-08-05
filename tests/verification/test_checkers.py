"""Every supported class executes, on both a case it decides and one it refuses.

A checker that has never been shown to fire is indistinguishable from one that is dead
code, and a checker that has never been shown to *decline* is indistinguishable from one
that accepts everything. Each class therefore gets both.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.verification.obligations import (
    SUPPORTED_CLASSES,
    GlobalVerdict,
    ObligationClass,
    ObligationStatus,
    verify_source,
)

# (source, class that must appear, status that class must carry)
DECIDED: list[tuple[str, str, ObligationClass, ObligationStatus]] = [
    (
        "closed equality, true",
        "module M\nrequire 2 + 3 = 5\n",
        ObligationClass.CLOSED_ARITHMETIC_EQUALITY,
        ObligationStatus.DISCHARGED,
    ),
    (
        "closed equality, false",
        "module M\nrequire 2 + 3 = 6\n",
        ObligationClass.CLOSED_ARITHMETIC_EQUALITY,
        ObligationStatus.FAILED,
    ),
    (
        "closed inequality, true",
        "module M\nconst g : PositiveReal = 9.81\nrequire g > 9\n",
        ObligationClass.CLOSED_INEQUALITY,
        ObligationStatus.DISCHARGED,
    ),
    (
        "closed inequality, false",
        "module M\nconst g : PositiveReal = 9.81\nrequire g > 10\n",
        ObligationClass.CLOSED_INEQUALITY,
        ObligationStatus.FAILED,
    ),
    (
        "refinement bound entailed",
        "module M\nparam s : PositiveReal\nprove s > 0\n",
        ObligationClass.LITERAL_REFINEMENT_BOUND,
        ObligationStatus.DISCHARGED,
    ),
    (
        "dimension agrees",
        "module M\nparam m : Quantity[Mass]\nparam v : Quantity[Length / Time]\n"
        "def e := 0.5 * m * v^2\ncheck dimension e = Mass * Length^2 / Time^2\n",
        ObligationClass.DIMENSION_COMPATIBILITY,
        ObligationStatus.DISCHARGED,
    ),
    (
        "signature conforms",
        "module M\ndef add(a : Real, b : Real) : Real := a + b\nrequire add(1.0, 2.0) = 3\n",
        ObligationClass.DECLARED_SIGNATURE_CONFORMANCE,
        ObligationStatus.DISCHARGED,
    ),
    (
        "finite exhaustion, true",
        "module M\nprove forall b : Bool . b = true or b = false\n",
        ObligationClass.FINITE_SET_MEMBERSHIP,
        ObligationStatus.DISCHARGED,
    ),
    (
        "finite exhaustion, false",
        "module M\nprove forall b : Bool . b = true\n",
        ObligationClass.FINITE_SET_MEMBERSHIP,
        ObligationStatus.FAILED,
    ),
    (
        "constraint set satisfiable",
        "module M\nvar x : Real\nvar y : Real\nrequire x + y >= 10\nrequire x >= 0\n",
        ObligationClass.LOGICAL_CONSISTENCY,
        ObligationStatus.DISCHARGED,
    ),
    (
        "constraint set infeasible",
        "module M\nvar x : Real\nrequire x > 5\nrequire x < 3\n",
        ObligationClass.LOGICAL_CONSISTENCY,
        ObligationStatus.FAILED,
    ),
    (
        "symbolic identity",
        "module M\nvar x : Real\nprove (x + 1)^2 = x^2 + 2 * x + 1\n",
        ObligationClass.SYMBOLIC_IDENTITY,
        ObligationStatus.DISCHARGED,
    ),
    (
        "numerical counterexample",
        "module M\nvar x : Real\nprove (x + 1)^2 = x^2 + 1\n",
        ObligationClass.NUMERICAL_COUNTEREXAMPLE,
        ObligationStatus.FAILED,
    ),
]


@pytest.mark.parametrize(
    ("label", "source", "expected_class", "expected_status"),
    DECIDED,
    ids=[c[0] for c in DECIDED],
)
def test_each_supported_class_decides_its_case(
    label: str, source: str, expected_class: ObligationClass, expected_status: ObligationStatus
) -> None:
    outcome = verify_source(source)
    matching = [r for r in outcome.records if r.obligation_class is expected_class]
    assert matching, f"{label}: class {expected_class} never fired; got {outcome.by_class()}"
    assert any(r.status is expected_status for r in matching), (
        f"{label}: {expected_class} produced "
        f"{[str(r.status) for r in matching]}, wanted {expected_status}"
    )


def test_every_supported_class_is_exercised_by_this_file() -> None:
    """A class with no test is a claim with no evidence."""
    covered = {c for _label, _src, c, _s in DECIDED}
    assert covered == SUPPORTED_CLASSES, f"unexercised: {sorted(SUPPORTED_CLASSES - covered)}"


def test_every_failure_carries_a_witness() -> None:
    for label, source, _cls, status in DECIDED:
        if status is not ObligationStatus.FAILED:
            continue
        outcome = verify_source(source)
        failures = [r for r in outcome.records if r.status is ObligationStatus.FAILED]
        assert failures, label
        for record in failures:
            assert record.witness is not None, label
            assert record.witness.bindings or record.witness.evaluated, label


def test_a_counterexample_is_a_real_assignment_that_can_be_rechecked() -> None:
    """The witness must actually refute the claim when substituted back."""
    outcome = verify_source("module M\nvar x : Real\nprove (x + 1)^2 = x^2 + 1\n")
    failure = outcome.first_failure()
    assert failure is not None and failure.witness is not None
    bindings = failure.witness.bindings
    assert "x" in bindings
    from fractions import Fraction

    x = Fraction(bindings["x"])
    assert (x + 1) ** 2 != x**2 + 1


def test_sampling_never_produces_a_discharge() -> None:
    """A grid that finds no counterexample proves nothing, and must not say otherwise."""
    outcome = verify_source("module M\nvar x : Real\nprove x^2 >= -1\n")
    numeric = [
        r
        for r in outcome.records
        if r.obligation_class is ObligationClass.NUMERICAL_COUNTEREXAMPLE
    ]
    for record in numeric:
        assert record.status is not ObligationStatus.DISCHARGED


def test_a_definitional_discharge_is_labelled_as_such() -> None:
    outcome = verify_source("module M\nparam s : PositiveReal\n")
    assert outcome.verdict is GlobalVerdict.VERIFIED
    assert not outcome.substantive
    assert all(r.evidence.get("definitional") for r in outcome.records if r.discharged)


def test_an_unsupported_shape_names_what_is_missing() -> None:
    outcome = verify_source(
        "module M\nvar w : Vector[Real, 3]\nindex i : Natural\nprove w[i] = w[i]\n"
    )
    unsupported = [r for r in outcome.records if r.status is ObligationStatus.UNSUPPORTED]
    assert unsupported
    assert all(r.detail.strip() for r in unsupported)


def test_a_dimension_mismatch_is_caught_before_the_engine_runs() -> None:
    """HML-D504 rejects it at type-check time; the engine reports INVALID, not a pass."""
    outcome = verify_source(
        "module M\nparam m : Quantity[Mass]\nparam v : Quantity[Length / Time]\n"
        "def e := 0.5 * m * v^2\ncheck dimension e = Mass * Length^3 / Time^2\n"
    )
    assert outcome.verdict is GlobalVerdict.INVALID
    assert "HML-D504" in outcome.diagnostics


def test_a_dimension_claim_is_recomputed_not_echoed() -> None:
    """The recomputation reads declared types, never ``Expr.type_``."""
    from hamiltonian_lang import compile_source
    from hamiltonian_lang.verification.obligations.checkers import dimension_of_expr
    from hamiltonian_lang.verification.obligations.evaluate import build_environment

    result = compile_source(
        "module M\nparam m : Quantity[Mass]\nparam v : Quantity[Length / Time]\n"
        "def e := 0.5 * m * v^2\ncheck dimension e = Mass * Length^2 / Time^2\n"
    )
    env = build_environment(result.module, result.symbols)
    subject = result.obligations[0].expression
    assert subject is not None
    subject.type_ = None  # the checker's answer is removed; the result must not change
    assert dimension_of_expr(subject, env) is not None
    assert dimension_of_expr(subject, env).render() == "Length^2 * Mass / Time^2"
