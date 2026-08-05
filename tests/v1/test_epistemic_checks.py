"""V1 layer 4 — the epistemic checker.

``epistemic.py`` is the contract and is imported, never modified. These tests exercise the
checker built on it: what may stand where, what a hedge is worth, and what a result still
depends on.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.v1.epistemic import (
    DISCHARGES_GOALS,
    ContextError,
    EpistemicClaim,
    EpistemicStatus,
    Justification,
)
from hamiltonian_lang.v1.epistemic_checks import (
    REQUIRED_JUSTIFICATION_BY_SITE,
    Calibration,
    EpistemicChecker,
    Likely,
    Site,
    UncalibratedLikelyError,
    check_context,
    check_test_coherence,
)


def _fail_to_reject(p: str = "0.18", alpha: str = "0.05") -> EpistemicClaim:
    return EpistemicClaim(
        status=EpistemicStatus.FAIL_TO_REJECT,
        body="the coin is fair",
        context={"null": "H0", "alpha": alpha, "p_value": p},
    )


def _proved(body: str = "n is even") -> EpistemicClaim:
    return EpistemicClaim(status=EpistemicStatus.PROVED, body=body)


def _assumed(body: str = "the errors are independent") -> EpistemicClaim:
    return EpistemicClaim(status=EpistemicStatus.MODEL_CONDITIONAL, body=body,
                          context={"model": "M1"})


# ---------------------------------------------------------------------------
# the statistical negative
# ---------------------------------------------------------------------------


def test_prove_rejects_a_fail_to_reject_result():
    checker = EpistemicChecker()
    checker.declare("r1", _fail_to_reject())

    violation = checker.use("r1", Site.PROVE)
    assert violation is not None
    assert violation.code == "HML-E702"
    assert violation.required is Justification.PROOF
    assert violation.actual is Justification.EVIDENCE
    assert "failing to reject H0 does not prove H0" in violation.message


def test_a_fail_to_reject_result_may_still_be_cited_as_evidence_or_reported():
    checker = EpistemicChecker()
    checker.declare("r1", _fail_to_reject())
    assert checker.use("r1", Site.CITE_AS_EVIDENCE) is None
    assert checker.use("r1", Site.REPORT) is None
    assert checker.report().clean


def test_rejecting_at_a_significance_level_is_not_a_refutation():
    checker = EpistemicChecker()
    checker.declare(
        "r1",
        EpistemicClaim(
            status=EpistemicStatus.REJECT,
            body="the coin is fair",
            context={"null": "H0", "alpha": "0.05", "p_value": "0.01"},
        ),
    )
    violation = checker.use("r1", Site.REFUTE)
    assert violation is not None
    assert violation.code == "HML-E702"
    assert "not a disproof" in violation.message


def test_a_test_outcome_that_contradicts_its_own_alpha_is_reported():
    checker = EpistemicChecker()
    violation = checker.declare("r1", _fail_to_reject(p="0.01", alpha="0.05"))
    assert violation is not None
    assert violation.code == "HML-E704"
    assert "p = 0.01 <= alpha = 0.05" in violation.message


def test_a_rejection_above_alpha_is_reported():
    violation = check_test_coherence(
        "r1",
        EpistemicClaim(
            status=EpistemicStatus.REJECT,
            body="H0",
            context={"null": "H0", "alpha": "0.05", "p_value": "0.4"},
        ),
    )
    assert violation is not None and violation.code == "HML-E704"


def test_coherence_is_not_decided_when_the_numbers_do_not_parse():
    claim = EpistemicClaim(
        status=EpistemicStatus.FAIL_TO_REJECT,
        body="H0",
        context={"null": "H0", "alpha": "the conventional level", "p_value": "small"},
    )
    assert check_test_coherence("r1", claim) is None


def test_a_coherent_test_outcome_passes():
    assert check_test_coherence("r1", _fail_to_reject(p="0.18", alpha="0.05")) is None


# ---------------------------------------------------------------------------
# discharging goals
# ---------------------------------------------------------------------------


def test_only_a_proof_or_a_refutation_discharges():
    assert DISCHARGES_GOALS[Justification.PROOF] is True
    assert DISCHARGES_GOALS[Justification.REFUTATION] is True
    assert not any(
        DISCHARGES_GOALS[j]
        for j in (
            Justification.EVIDENCE,
            Justification.ASSUMPTION,
            Justification.CREDENCE,
            Justification.NONE,
        )
    )


def test_evidence_does_not_discharge_a_goal():
    checker = EpistemicChecker()
    checker.declare("r1", _fail_to_reject())
    violation = checker.use("r1", Site.DISCHARGE)
    assert violation is not None
    assert violation.code == "HML-E702"
    assert violation.required is Justification.PROOF


def test_an_assumption_does_not_discharge_a_goal():
    checker = EpistemicChecker()
    checker.declare("a1", _assumed())
    violation = checker.use("a1", Site.DISCHARGE)
    assert violation is not None
    assert violation.actual is Justification.ASSUMPTION
    assert "granted, not established" in violation.message


def test_a_conjecture_does_not_discharge_a_goal():
    checker = EpistemicChecker()
    checker.declare(
        "c1", EpistemicClaim(status=EpistemicStatus.CONJECTURED, body="P = NP")
    )
    violation = checker.use("c1", Site.DISCHARGE)
    assert violation is not None
    assert "a conjecture is not a theorem" in violation.message


def test_a_proof_discharges_a_goal():
    checker = EpistemicChecker()
    checker.declare("t1", _proved())
    assert checker.use("t1", Site.DISCHARGE) is None
    assert checker.use("t1", Site.PROVE) is None


def test_a_refutation_discharges_by_refuting():
    checker = EpistemicChecker()
    checker.declare(
        "d1", EpistemicClaim(status=EpistemicStatus.DISPROVED, body="every prime is odd")
    )
    assert checker.use("d1", Site.DISCHARGE) is None
    assert checker.use("d1", Site.REFUTE) is None
    # but a refutation is still not a proof of the original statement
    assert checker.use("d1", Site.PROVE) is not None


# ---------------------------------------------------------------------------
# context
# ---------------------------------------------------------------------------


def test_a_status_without_its_context_is_rejected_as_ill_formed():
    checker = EpistemicChecker()
    violation = checker.declare_status(
        "w1", EpistemicStatus.WITH_HIGH_PROBABILITY, "the estimate is consistent"
    )
    assert violation is not None
    assert violation.code == "HML-E706"
    assert "bound_or_regime" in violation.message
    assert checker.claim("w1") is None


def test_the_same_omission_raises_from_the_contract_itself():
    with pytest.raises(ContextError):
        EpistemicClaim(
            status=EpistemicStatus.WITH_HIGH_PROBABILITY, body="the estimate converges"
        )


def test_check_context_is_the_non_raising_form():
    assert check_context(EpistemicStatus.PROVED, {}) is None
    message = check_context(EpistemicStatus.MODEL_CONDITIONAL, {})
    assert message is not None and "model" in message


def test_a_status_with_its_context_is_accepted():
    checker = EpistemicChecker()
    assert (
        checker.declare_status(
            "w1",
            EpistemicStatus.WITH_HIGH_PROBABILITY,
            "the estimate is consistent",
            bound_or_regime="n -> infinity",
        )
        is None
    )
    claim = checker.claim("w1")
    assert claim is not None
    assert "With high probability (n -> infinity)" in claim.render_english()


# ---------------------------------------------------------------------------
# likely — presentation level only
# ---------------------------------------------------------------------------


def test_likely_is_not_an_epistemic_status_at_all():
    assert "likely" not in {s.value for s in EpistemicStatus}
    assert not hasattr(EpistemicStatus, "LIKELY")


def test_an_uncalibrated_likely_is_not_a_trusted_status():
    hedge = Likely("the effect is real")
    assert hedge.calibrated is False
    assert hedge.trusted_status() is None
    assert hedge.justification() is None
    assert hedge.discharges_goals() is False
    assert hedge.is_kernel_state() is False
    assert "carries no formal status" in hedge.render_english()


def test_an_uncalibrated_likely_cannot_be_promoted_to_a_claim():
    with pytest.raises(UncalibratedLikelyError) as excinfo:
        Likely("the effect is real").as_claim()
    assert "uncalibrated" in str(excinfo.value)


def test_an_uncalibrated_likely_is_rejected_wherever_a_justification_is_required():
    checker = EpistemicChecker()
    checker.declare_hedge("h1", Likely("the effect is real"))
    for site in (Site.PROVE, Site.DISCHARGE, Site.ASSERT, Site.CITE_AS_EVIDENCE):
        violation = checker.use("h1", site)
        assert violation is not None
        assert violation.code == "HML-E705"
        assert "uncalibrated" in violation.message


def test_an_uncalibrated_likely_may_still_be_reported():
    checker = EpistemicChecker()
    checker.declare_hedge("h1", Likely("the effect is real"))
    assert checker.use("h1", Site.REPORT) is None
    assert checker.report().clean


def test_a_calibrated_likely_reaches_credence_and_no_further():
    hedge = Likely(
        "the effect is real",
        Calibration(0.8, reference_class="similar RCTs", source="meta-analysis 2019"),
    )
    assert hedge.calibrated is True
    assert hedge.trusted_status() is EpistemicStatus.POSSIBLE
    assert hedge.justification() is Justification.CREDENCE
    assert hedge.discharges_goals() is False

    claim = hedge.as_claim()
    assert claim.justification is Justification.CREDENCE
    assert claim.discharges_goals() is False
    ok, reason = claim.may_be_used_as(Justification.PROOF)
    assert ok is False
    assert "degree of belief" in reason


def test_a_calibrated_likely_still_fails_a_proof_site():
    checker = EpistemicChecker()
    checker.declare_hedge(
        "h1",
        Likely(
            "the effect is real",
            Calibration(0.8, reference_class="similar RCTs", source="meta-analysis"),
        ),
    )
    violation = checker.use("h1", Site.PROVE)
    assert violation is not None
    assert violation.code == "HML-E702"
    assert violation.actual is Justification.CREDENCE


def test_calibration_demands_a_probability_a_reference_class_and_a_source():
    with pytest.raises(ValueError):
        Calibration(1.4, reference_class="x", source="y")
    with pytest.raises(ValueError):
        Calibration(0.8, reference_class="", source="y")
    with pytest.raises(ValueError):
        Calibration(0.8, reference_class="x", source="")


# ---------------------------------------------------------------------------
# dependencies and bookkeeping
# ---------------------------------------------------------------------------


def test_a_model_conditional_claim_carries_its_model_forward():
    checker = EpistemicChecker()
    checker.declare("a1", _assumed())
    checker.use("a1", Site.REPORT)
    dependencies = checker.report().dependencies
    assert any(d.on == "M1" for d in dependencies)
    assert any("not outside it" in d.reason for d in dependencies)


def test_an_unknown_claim_is_reported():
    checker = EpistemicChecker()
    violation = checker.use("ghost", Site.PROVE)
    assert violation is not None and violation.code == "HML-E701"


def test_a_duplicate_declaration_is_reported():
    checker = EpistemicChecker()
    checker.declare("t1", _proved())
    violation = checker.declare("t1", _proved())
    assert violation is not None and violation.code == "HML-E703"


def test_check_all_walks_every_use_and_reports_everything():
    checker = EpistemicChecker()
    checker.declare("r1", _fail_to_reject())
    checker.declare("t1", _proved())
    checker.declare("a1", _assumed())

    report = checker.check_all(
        [("r1", Site.PROVE), ("t1", Site.DISCHARGE), ("a1", Site.DISCHARGE)]
    )
    assert not report.clean
    assert [v.claim for v in report.violations] == ["r1", "a1"]
    assert report.dependencies
    assert "epistemic violation" in report.render()


def test_every_site_except_report_names_a_justification():
    assert set(REQUIRED_JUSTIFICATION_BY_SITE) == set(Site) - {Site.REPORT}
    assert all(
        isinstance(j, Justification) for j in REQUIRED_JUSTIFICATION_BY_SITE.values()
    )


def test_a_clean_report_says_so():
    report = EpistemicChecker().report()
    assert report.clean
    assert "no epistemic violations" in report.render()
