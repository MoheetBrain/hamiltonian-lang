"""Verifier federation: the classification rules, enforced rather than documented.

Five rules from the directive, plus the one that falls out of them:

* unsupported is NOT failure
* inconclusive is NOT verified
* source generation is NOT backend verification
* successful execution is NOT semantic equivalence
* ``sorry`` and unexpected Lean axioms can NEVER count as verified
* a failure without a counterexample is inconclusive, not disproved

Each has at least one test below, and the measured environment facts (``stanc`` absent,
Mathlib absent, the Lean backend emitting ``sorry`` by design) are asserted against the
live machine so that a change in the environment fails loudly instead of quietly
widening what this project claims.
"""

from __future__ import annotations

import shutil

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.improvement.verification import (
    ENVIRONMENT_FACTS,
    Candidate,
    CandidateLanguage,
    CanonicalComparatorVerifier,
    CanonicalObject,
    Counterexample,
    DimensionVerifier,
    EpistemicVerifier,
    LeanVerifier,
    ParseVerifier,
    ResolutionVerifier,
    SemanticLoss,
    StanVerifier,
    SupportDecision,
    SympyExecutionVerifier,
    TypeCheckVerifier,
    VerificationResult,
    VerifierStatus,
    classify,
    default_federation,
)

GOOD = "module m\n\nparam x : Real\nparam y : Real\nrequire x + y > 0.0\n"
RENAMED = "module m\n\nparam a : Real\nparam b : Real\nrequire a + b > 0.0\n"
DIFFERENT = "module m\n\nparam x : Real\nparam y : Real\nrequire x - y > 0.0\n"
UNRESOLVED = "module m\n\nparam x : Real\nrequire z > 0.0\n"
UNPARSEABLE = "module m\n\nparam x : = = \n"

REF = CanonicalObject(object_id="obj-1", source=GOOD)


def hml(text: str) -> Candidate:
    return Candidate(text=text, language=CandidateLanguage.HML)


def result(status: VerifierStatus, **kw) -> VerificationResult:
    return VerificationResult("v", "1", status, **kw)


# --- protocol invariants ------------------------------------------------------------


def test_an_unsupported_decision_must_say_why():
    with pytest.raises(ValueError, match="must say why"):
        SupportDecision(False, "")


def test_verified_cannot_carry_an_open_obligation():
    with pytest.raises(ValueError, match="obligation"):
        result(VerifierStatus.SUPPORTED_AND_VERIFIED, obligations_remaining=("o",))


def test_verified_cannot_carry_a_counterexample():
    with pytest.raises(ValueError, match="counterexample"):
        result(
            VerifierStatus.SUPPORTED_AND_VERIFIED,
            counterexample=Counterexample("it fails at x = 1"),
        )


def test_semantic_loss_must_name_what_was_lost():
    with pytest.raises(ValueError, match="must name what was lost"):
        result(VerifierStatus.SEMANTIC_LOSS)


def test_a_counterexample_must_describe_itself():
    with pytest.raises(ValueError, match="must describe"):
        Counterexample("   ")


def test_evidence_hash_is_computed_and_content_addressed():
    a = result(VerifierStatus.INCONCLUSIVE, detail="x")
    b = result(VerifierStatus.INCONCLUSIVE, detail="x")
    c = result(VerifierStatus.INCONCLUSIVE, detail="y")
    assert a.evidence_hash == b.evidence_hash != c.evidence_hash
    assert len(a.evidence_hash) == 64


def test_only_one_status_reads_as_verified():
    for status in VerifierStatus:
        if status is VerifierStatus.SUPPORTED_AND_VERIFIED:
            assert result(status).verified
        elif status is VerifierStatus.SEMANTIC_LOSS:
            assert not result(status, semantic_loss=(SemanticLoss("law", "dropped"),)).verified
        else:
            assert not result(status).verified


# --- compiler-stage verifiers --------------------------------------------------------


def test_parser_verifies_only_syntax():
    r = ParseVerifier().verify(REF, hml(GOOD))
    assert r.status is VerifierStatus.SUPPORTED_AND_VERIFIED
    assert r.obligations_checked == ("parses",)
    assert "nothing further" in r.detail


def test_parser_rejects_unparseable_source():
    assert ParseVerifier().verify(REF, hml(UNPARSEABLE)).status is VerifierStatus.INVALID


def test_a_non_hml_candidate_is_unsupported_not_failed():
    r = ParseVerifier().verify(REF, Candidate("theorem t : True := trivial", CandidateLanguage.LEAN))
    assert r.status is VerifierStatus.UNSUPPORTED
    assert r.detail


def test_resolver_rejects_an_unresolved_name():
    r = ResolutionVerifier().verify(REF, hml(UNRESOLVED))
    assert r.status is VerifierStatus.INVALID
    assert r.evidence["codes"] == ["HML-N301"]


def test_resolution_is_inconclusive_when_parsing_failed():
    """A stage that never ran produces no evidence about its own obligation."""
    r = ResolutionVerifier().verify(REF, hml(UNPARSEABLE))
    assert r.status is VerifierStatus.INCONCLUSIVE
    assert r.obligations_remaining


def test_type_checker_reports_collected_obligations_as_remaining():
    r = TypeCheckVerifier().verify(REF, hml(GOOD))
    assert r.status is VerifierStatus.INCONCLUSIVE
    assert r.obligations_remaining
    assert "does not discharge" in r.detail


def test_type_checker_verifies_a_module_with_no_obligation():
    r = TypeCheckVerifier().verify(REF, hml("module m\n\nparam x : Real\n"))
    assert r.status is VerifierStatus.SUPPORTED_AND_VERIFIED
    assert r.obligations_remaining == ()


def test_dimension_verifier_declines_a_dimensionless_program():
    r = DimensionVerifier().verify(REF, hml(GOOD))
    assert r.status is VerifierStatus.UNSUPPORTED
    assert "no dimensional obligation" in r.detail


def test_dimension_verifier_checks_a_program_with_quantities():
    src = "module m\n\nparam d : Quantity[length]\nparam t : Quantity[time]\n"
    r = DimensionVerifier().verify(REF, hml(src))
    assert r.status in (VerifierStatus.SUPPORTED_AND_VERIFIED, VerifierStatus.INVALID)
    assert r.status is not VerifierStatus.UNSUPPORTED


def test_epistemic_verifier_is_unsupported_for_hml_source():
    """The V1 epistemic layer is a Python API, unreachable from HML (Lead audit §5a)."""
    r = EpistemicVerifier().verify(REF, hml(GOOD))
    assert r.status is VerifierStatus.UNSUPPORTED
    assert "unreachable from HML" in r.detail


def test_epistemic_verifier_checks_supplied_claims():
    from hamiltonian_lang.v1.epistemic import EpistemicClaim, EpistemicStatus
    from hamiltonian_lang.v1.epistemic_checks import Site

    claim = EpistemicClaim(
        status=EpistemicStatus.FAIL_TO_REJECT,
        body="mu = 0",
        context={"test": "t1", "p_value": "0.18", "alpha": "0.05", "null": "mu = 0"},
    )
    candidate = Candidate(
        text="", attachments={"epistemic": {"claims": {"r1": claim},
                                            "uses": [("r1", Site.PROVE)]}}
    )
    r = EpistemicVerifier().verify(REF, candidate)
    assert r.status is VerifierStatus.INVALID
    assert "HML-E702" in r.evidence["codes"]


# --- the canonical comparator, the one real equivalence oracle ------------------------


def test_alpha_renaming_is_the_same_object():
    r = CanonicalComparatorVerifier().verify(REF, hml(RENAMED))
    assert r.status is VerifierStatus.SUPPORTED_AND_VERIFIED


def test_a_different_object_fails_with_a_counterexample():
    r = CanonicalComparatorVerifier().verify(REF, hml(DIFFERENT))
    assert r.status is VerifierStatus.SUPPORTED_AND_FAILED
    assert r.counterexample is not None
    assert "not of falsity" in r.detail


def test_a_non_compiling_candidate_denotes_no_object():
    assert (
        CanonicalComparatorVerifier().verify(REF, hml(UNRESOLVED)).status
        is VerifierStatus.INVALID
    )


def test_the_comparator_declines_without_a_reference():
    r = CanonicalComparatorVerifier().verify(CanonicalObject(object_id="none"), hml(GOOD))
    assert r.status is VerifierStatus.UNSUPPORTED
    assert "reference-semantic-object" in r.evidence["missing_capability"]


def test_an_uncompilable_reference_is_inconclusive_not_a_candidate_failure():
    bad_ref = CanonicalObject(object_id="obj-bad", source=UNRESOLVED)
    r = CanonicalComparatorVerifier().verify(bad_ref, hml(GOOD))
    assert r.status is VerifierStatus.INCONCLUSIVE
    assert "says nothing about the candidate" in r.detail


# --- measured environment facts, asserted against the live machine ---------------------


def test_stanc_is_still_absent():
    """If this fails, `stanc` appeared and the Stan classification needs re-auditing."""
    assert shutil.which("stanc") is None
    assert ENVIRONMENT_FACTS["stanc"][0] is False


def test_mathlib_is_recorded_absent():
    assert ENVIRONMENT_FACTS["mathlib"][0] is False


def test_stan_is_always_unsupported():
    r = StanVerifier().verify(REF, Candidate("model { }", CandidateLanguage.STAN))
    assert r.status is VerifierStatus.UNSUPPORTED
    assert "source generation, not verification" in r.detail
    assert "`stanc` is absent" in r.detail


def test_emitting_lean_from_hml_is_not_verification():
    r = LeanVerifier().verify(REF, hml(GOOD))
    assert r.status is VerifierStatus.UNSUPPORTED
    assert "source generation is not verification" in r.detail


def test_a_mathlib_dependent_lean_candidate_is_unsupported_not_failed():
    r = LeanVerifier().verify(REF, Candidate("theorem t : ∀ x : ℝ, x = x := by intro x; rfl",
                                             CandidateLanguage.LEAN))
    assert r.status is VerifierStatus.UNSUPPORTED
    assert "mathlib" in r.evidence["missing_capability"]


def test_the_lean_backend_closes_obligations_with_sorry_and_is_therefore_rejected():
    """The measured fact, encoded: a sound gate with nothing able to pass through it.

    The Lean backend emits ``sorry`` by design and ``sorry`` is in ``FORBIDDEN_TACTICS``,
    so ``lean_verify.verify()`` rejects the backend's own output before Lean runs.
    """
    from hamiltonian_lang.v1.lean_verify import LeanVerdict
    from hamiltonian_lang.v1.lean_verify import verify as lean_verify

    emitted = compile_source(GOOD).render("lean").text
    assert "sorry" in emitted
    outcome = lean_verify(emitted)
    assert outcome.verdict is LeanVerdict.REJECTED_FORBIDDEN_TACTIC
    assert not outcome.verified

    r = LeanVerifier().verify(REF, Candidate(emitted, CandidateLanguage.LEAN))
    assert r.status is not VerifierStatus.SUPPORTED_AND_VERIFIED


@pytest.mark.parametrize("tactic", ["sorry", "admit", "native_decide"])
def test_no_forbidden_tactic_can_reach_verified(tactic):
    text = f"theorem t : (1 : Nat) = 2 := by {tactic}"
    r = LeanVerifier().verify(REF, Candidate(text, CandidateLanguage.LEAN))
    assert r.status is not VerifierStatus.SUPPORTED_AND_VERIFIED


# --- execution is not equivalence -------------------------------------------------------


def test_a_clean_sympy_run_is_inconclusive_not_verified():
    r = SympyExecutionVerifier().verify(REF, hml(GOOD))
    if r.status is VerifierStatus.UNSUPPORTED:  # sympy absent
        pytest.skip("sympy is not importable in this environment")
    assert r.status is VerifierStatus.INCONCLUSIVE
    assert "not semantic equivalence" in r.detail
    assert r.obligations_remaining


def test_backend_loss_outranks_a_clean_run():
    r = SympyExecutionVerifier().verify(REF, hml("module m\n\nconst a : Real = 2.0\n"))
    if r.status is VerifierStatus.UNSUPPORTED:
        pytest.skip("sympy is not importable in this environment")
    assert r.status is VerifierStatus.SEMANTIC_LOSS
    assert r.semantic_loss


# --- classification ----------------------------------------------------------------------


def test_no_results_is_unsupported():
    assert classify([]) == "UNSUPPORTED"


def test_all_unsupported_is_unsupported():
    assert classify([result(VerifierStatus.UNSUPPORTED)] * 3) == "UNSUPPORTED"


def test_unsupported_is_not_failure():
    """An unsupported verifier neither blocks a verdict nor creates a negative one."""
    assert classify(
        [result(VerifierStatus.UNSUPPORTED), result(VerifierStatus.SUPPORTED_AND_VERIFIED)]
    ) == "VERIFIED"


def test_inconclusive_is_not_verified():
    assert classify(
        [result(VerifierStatus.SUPPORTED_AND_VERIFIED), result(VerifierStatus.INCONCLUSIVE)]
    ) == "INCONCLUSIVE"


def test_an_open_obligation_blocks_verified():
    assert classify(
        [
            result(VerifierStatus.SUPPORTED_AND_VERIFIED),
            result(VerifierStatus.UNSUPPORTED, obligations_remaining=("the theorem holds",)),
        ]
    ) == "INCONCLUSIVE"


def test_failure_without_a_counterexample_is_inconclusive():
    assert classify([result(VerifierStatus.SUPPORTED_AND_FAILED)]) == "INCONCLUSIVE"


def test_failure_with_a_counterexample_is_disproved():
    assert classify(
        [result(VerifierStatus.SUPPORTED_AND_FAILED,
                counterexample=Counterexample("false at x = 0"))]
    ) == "DISPROVED"


def test_invalid_outranks_everything():
    assert classify(
        [result(VerifierStatus.SUPPORTED_AND_VERIFIED), result(VerifierStatus.INVALID)]
    ) == "INVALID"


def test_semantic_loss_outranks_a_pass():
    assert classify(
        [
            result(VerifierStatus.SUPPORTED_AND_VERIFIED),
            result(VerifierStatus.SEMANTIC_LOSS,
                   semantic_loss=(SemanticLoss("law", "sympy has no conditioning set"),)),
        ]
    ) == "SEMANTIC_LOSS"


def test_a_bare_inconclusive_pool_is_inconclusive():
    assert classify([result(VerifierStatus.INCONCLUSIVE)]) == "INCONCLUSIVE"


def test_verified_requires_something_to_have_verified():
    assert classify([result(VerifierStatus.SUPPORTED_AND_VERIFIED)]) == "VERIFIED"


def test_every_classification_names_a_terminal_verdict():
    """``classify`` returns a string to avoid an import cycle; it must still be a Verdict."""
    from hamiltonian_lang.improvement.episodes import Verdict

    pools = [
        [],
        [result(VerifierStatus.UNSUPPORTED)],
        [result(VerifierStatus.INCONCLUSIVE)],
        [result(VerifierStatus.INVALID)],
        [result(VerifierStatus.SUPPORTED_AND_VERIFIED)],
        [result(VerifierStatus.SUPPORTED_AND_FAILED)],
        [result(VerifierStatus.SUPPORTED_AND_FAILED, counterexample=Counterexample("w"))],
        [result(VerifierStatus.SEMANTIC_LOSS, semantic_loss=(SemanticLoss("law", "r"),))],
    ]
    for pool in pools:
        assert Verdict[classify(pool)].value == classify(pool)


# --- the federation ------------------------------------------------------------------------


def test_default_federation_names_are_unique_and_versioned():
    fed = default_federation()
    assert len(set(fed.names())) == len(fed.names())
    assert all(v for v in fed.versions().values())


def test_the_federation_wraps_only_existing_mechanisms():
    """`obligation_discharge` joined the set under D-025.

    The rule this pins is unchanged: the federation wraps mechanisms that already exist
    and does not invent a verifier. The obligation engine is one such mechanism -- it
    discharges nine explicitly supported classes deterministically and returns
    UNSUPPORTED outside them. A name appearing here without an implementation behind it
    is what this test is for.
    """
    assert set(default_federation().names()) == {
        "parser", "resolver", "type_checker", "dimensional_checker",
        "epistemic_checker", "canonical_comparator", "lean", "stan",
        "obligation_discharge",
    }


def test_a_faithful_candidate_reaches_verified_once_its_obligations_are_discharged():
    """MIGRATED by D-025. This test previously pinned the opposite.

    It asserted that GOOD -- which matches the reference exactly -- could *not* reach
    VERIFIED, because the type checker collected an undischarged constraint and nothing
    discharged it. That was honest at the time and it did its job: the change could not
    land silently.

    It also meant VERIFIED was unreachable for any module containing `require`, and with
    Lean unusable (Mathlib absent; the backend closes every obligation with `sorry` by
    design) that made H3's primary endpoint -- kernel-verified completion rate --
    unmeasurable. `ObligationDischargeVerifier` now discharges the supported classes and
    `classify` composes across verifiers.

    The over-claim this module exists to prevent is still prevented: see
    `test_an_undischargeable_obligation_still_blocks_verified` below.
    """
    results = default_federation().run(REF, hml(GOOD))
    assert classify(results) == "VERIFIED"
    assert any(r.verified for r in results)


def test_an_undischargeable_obligation_still_blocks_verified():
    """The guard that keeps D-025 from being a weakening.

    A quantified claim is outside every implemented obligation class, so nothing can
    discharge it soundly. It must stay INCONCLUSIVE. An earlier draft of the classify
    change reported VERIFIED here, because the adapter listed UNSUPPORTED records as
    `obligations_checked` -- checked is not discharged.
    """
    src = "module M\nprove forall z : Real . z = z\n"
    ref = CanonicalObject(object_id="quantified", source=src)
    assert classify(default_federation().run(ref, hml(src))) == "INCONCLUSIVE"


def test_a_wrong_candidate_is_disproved_against_the_reference():
    assert classify(default_federation().run(REF, hml(DIFFERENT))) == "DISPROVED"


def test_an_unresolved_candidate_is_invalid():
    assert classify(default_federation().run(REF, hml(UNRESOLVED))) == "INVALID"
