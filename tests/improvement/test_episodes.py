"""The episode schema, and the two properties it exists to guarantee.

**H1, H2 and H3 stay separable forever.** A win on H3 alone is a win for verifier-guided
reasoning and must never be reported as a win for the representation. The schema makes
the confounded combinations unconstructible, and aggregation across hypotheses raises.

**Nothing is fabricated.** A token count that nobody measured cannot enter an episode
wearing the ``measured`` label.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.improvement.episodes import (
    EPISODE_SCHEMA_VERSION,
    HYPOTHESIS_CLAIMS,
    Condition,
    ConfidenceTier,
    ConfoundedCondition,
    Episode,
    FabricatedMeasurement,
    HypothesisId,
    HypothesisMixing,
    InputRepresentation,
    Measurement,
    Provenance,
    Verdict,
    assert_single_hypothesis,
    group_by_contrast,
    instrument_available,
    offline_absence,
    output_hash,
)
from hamiltonian_lang.improvement.verification import (
    Counterexample,
    VerificationResult,
    VerifierStatus,
)

H1_CONDITION = Condition(InputRepresentation.HAMILTONIAN, False, False)
H1_ENGLISH = Condition(InputRepresentation.ENGLISH, False, False)
H2_CONDITION = Condition(InputRepresentation.HAMILTONIAN, True, False)
H3_CONDITION = Condition(InputRepresentation.HAMILTONIAN, False, True)

VERIFIED_RESULT = VerificationResult(
    "canonical_comparator", "1", VerifierStatus.SUPPORTED_AND_VERIFIED
)


def episode(**kw) -> Episode:
    condition = kw.pop("condition", H1_CONDITION)
    base = dict(
        episode_id="ep-1",
        experiment_id="exp-1",
        task_id="task-1",
        canonical_object_id="obj-1",
        hypothesis_id=HypothesisId.H1,
        condition=condition,
        language_version="hml-0.1.0",
        compiler_version="hamiltonian-lang 0.1.0",
        input_representation=condition.input_representation,
        training_eligible=False,
        exclusion_reason="offline smoke episode; no model output to learn from",
    )
    base.update(kw)
    return Episode(**base)  # type: ignore[arg-type]


# --- identity and versioning ----------------------------------------------------------


def test_a_valid_episode_carries_its_schema_version():
    assert episode().schema_version == EPISODE_SCHEMA_VERSION


@pytest.mark.parametrize(
    "field", ["episode_id", "experiment_id", "task_id", "canonical_object_id"]
)
def test_identity_fields_are_required(field):
    with pytest.raises(ValueError, match=field):
        episode(**{field: ""})


def test_compiler_provenance_is_required():
    with pytest.raises(ValueError, match="compiler"):
        episode(compiler_version="")


def test_to_dict_carries_every_contracted_field():
    """A regression guard on the schema. Losing a field silently loses the evidence."""
    doc = episode().to_dict()
    required = {
        "episode_id", "schema_version", "experiment_id", "task_id",
        "canonical_object_id", "skill_ids", "dataset_split", "language_version",
        "compiler_version", "model_version", "diagnostic_version", "verifier_versions",
        "input_representation", "initial_output", "initial_output_hash",
        "parsed_object_id", "diagnostics", "verifier_results", "counterexamples",
        "repair_output", "repair_output_hash", "repaired_object_id", "semantic_edit",
        "repair_count", "final_answer", "final_verdict", "confidence_tier",
        "training_eligible", "exclusion_reason", "prompt_tokens", "completion_tokens",
        "latency_ms",
        # the durability fields
        "hypothesis_id", "hypothesis_claim", "condition",
    }
    assert required <= set(doc)


def test_digest_is_content_addressed():
    assert episode().digest() == episode().digest()
    assert episode().digest() != episode(task_id="task-2").digest()


def test_the_six_terminal_verdicts_exist():
    assert {v.value for v in Verdict} == {
        "VERIFIED", "DISPROVED", "INVALID", "UNSUPPORTED", "INCONCLUSIVE", "SEMANTIC_LOSS"
    }


# --- H1 / H2 / H3 separability: the durability property ---------------------------------


def test_every_hypothesis_has_a_recorded_claim():
    assert set(HYPOTHESIS_CLAIMS) == set(HypothesisId)
    for text in HYPOTHESIS_CLAIMS.values():
        assert len(text) > 60


def test_the_h3_claim_states_that_it_does_not_transfer_to_the_representation():
    """The single sentence a reader in a year most needs to find."""
    claim = HYPOTHESIS_CLAIMS[HypothesisId.H3].lower()
    assert "never be reported as a win for the representation" in claim


def test_an_h1_episode_cannot_carry_verifier_feedback():
    with pytest.raises(ConfoundedCondition, match="confounded with H3"):
        episode(hypothesis_id=HypothesisId.H1, condition=H3_CONDITION)


def test_an_h2_episode_cannot_carry_verifier_feedback():
    with pytest.raises(ConfoundedCondition, match="confounded with H3"):
        episode(
            hypothesis_id=HypothesisId.H2,
            condition=Condition(InputRepresentation.HAMILTONIAN, True, True),
        )


def test_an_h1_episode_cannot_require_a_derivation():
    with pytest.raises(ConfoundedCondition, match="H2's manipulation"):
        episode(hypothesis_id=HypothesisId.H1, condition=H2_CONDITION)


def test_an_h2_episode_must_require_a_derivation():
    with pytest.raises(ConfoundedCondition, match="not evidence about H2"):
        episode(hypothesis_id=HypothesisId.H2, condition=H1_CONDITION)


def test_an_h3_episode_must_have_verifier_feedback():
    with pytest.raises(ConfoundedCondition, match="not evidence about H3"):
        episode(hypothesis_id=HypothesisId.H3, condition=H1_CONDITION)


def test_the_condition_and_the_input_representation_must_agree():
    with pytest.raises(ValueError, match="ambiguous"):
        episode(input_representation=InputRepresentation.ENGLISH, condition=H1_CONDITION)


def test_repair_episodes_are_distinguishable_by_construction_not_convention():
    """A repair cannot be attached to an H1 or H2 episode at all.

    This is the structural guarantee. It is not a naming convention, and it cannot be
    defeated by a caller who forgets which arm they are in.
    """
    for hypothesis, condition in (
        (HypothesisId.H1, H1_CONDITION),
        (HypothesisId.H2, H2_CONDITION),
    ):
        base = episode(hypothesis_id=hypothesis, condition=condition)
        assert base.repaired is False
        with pytest.raises(ConfoundedCondition, match="H3's manipulation"):
            base.with_repair(repair_output="module m\n")
        with pytest.raises(ConfoundedCondition, match="H3's manipulation"):
            episode(
                hypothesis_id=hypothesis,
                condition=condition,
                repair_output="module m\n",
                repair_output_hash=output_hash("module m\n"),
                repair_count=1,
            )


def test_an_h3_episode_may_be_repaired():
    base = episode(hypothesis_id=HypothesisId.H3, condition=H3_CONDITION)
    assert base.with_repair(repair_output="module m\n").repaired


def test_aggregation_across_hypotheses_is_refused():
    """The requirement stated verbatim in the directive."""
    a = episode(episode_id="a", hypothesis_id=HypothesisId.H1, condition=H1_CONDITION)
    b = episode(episode_id="b", hypothesis_id=HypothesisId.H3, condition=H3_CONDITION)
    with pytest.raises(HypothesisMixing, match="refusing to aggregate"):
        assert_single_hypothesis([a, b])


def test_the_mixing_error_explains_both_claims():
    a = episode(hypothesis_id=HypothesisId.H1, condition=H1_CONDITION)
    b = episode(hypothesis_id=HypothesisId.H3, condition=H3_CONDITION)
    with pytest.raises(HypothesisMixing) as exc:
        assert_single_hypothesis([a, b])
    assert "representation" in str(exc.value)
    assert "verifier-guided" in str(exc.value)


def test_engineering_episodes_do_not_mix_with_hypothesis_episodes():
    a = episode(hypothesis_id=HypothesisId.H1, condition=H1_CONDITION)
    b = episode(
        hypothesis_id=HypothesisId.NONE,
        condition=Condition(InputRepresentation.ENGLISH, False, False),
        input_representation=InputRepresentation.ENGLISH,
    )
    with pytest.raises(HypothesisMixing):
        assert_single_hypothesis([a, b])


def test_aggregating_a_single_hypothesis_succeeds():
    pool = [
        episode(episode_id="a", condition=H1_CONDITION),
        episode(episode_id="b", condition=H1_ENGLISH,
                input_representation=InputRepresentation.ENGLISH),
    ]
    assert assert_single_hypothesis(pool) is HypothesisId.H1


def test_grouping_by_contrast_separates_the_two_arms():
    pool = [
        episode(episode_id="a", condition=H1_CONDITION),
        episode(episode_id="b", condition=H1_ENGLISH,
                input_representation=InputRepresentation.ENGLISH),
    ]
    buckets = group_by_contrast(pool)
    assert set(buckets) == {("hamiltonian", False, False), ("english", False, False)}


def test_the_contrast_key_records_all_three_manipulations():
    assert H3_CONDITION.contrast_key() == ("hamiltonian", False, True)


def test_an_empty_pool_is_not_silently_aggregated():
    with pytest.raises(HypothesisMixing, match="no episodes"):
        assert_single_hypothesis([])


# --- a repair never overwrites the initial attempt ----------------------------------------


def test_with_repair_preserves_the_initial_output():
    initial = "module m\n\nparam x : Rael\n"
    base = episode(
        hypothesis_id=HypothesisId.H3,
        condition=H3_CONDITION,
        initial_output=initial,
        initial_output_hash=output_hash(initial),
    )
    repaired = base.with_repair(repair_output="module m\n\nparam x : Real\n",
                                semantic_edit="corrected the type name")

    assert repaired.initial_output == initial
    assert repaired.initial_output_hash == output_hash(initial)
    assert repaired.repair_output == "module m\n\nparam x : Real\n"
    assert repaired.repair_output != repaired.initial_output
    assert repaired.repair_count == 1
    assert repaired.semantic_edit == "corrected the type name"
    # the original object is untouched
    assert base.repair_output is None and base.repair_count == 0


def test_repeated_repairs_increment_the_count_and_keep_the_first_output():
    initial = "a"
    base = episode(
        hypothesis_id=HypothesisId.H3, condition=H3_CONDITION,
        initial_output=initial, initial_output_hash=output_hash(initial),
    )
    twice = base.with_repair(repair_output="b").with_repair(repair_output="c")
    assert twice.repair_count == 2
    assert twice.initial_output == initial
    assert twice.repair_output == "c"


def test_the_episode_is_immutable():
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        episode().task_id = "other"  # type: ignore[misc]


def test_hashes_must_commit_to_their_text():
    with pytest.raises(ValueError, match="initial_output_hash"):
        episode(initial_output="a", initial_output_hash="deadbeef")
    with pytest.raises(ValueError, match="repair_output_hash"):
        episode(
            hypothesis_id=HypothesisId.H3, condition=H3_CONDITION,
            repair_output="b", repair_output_hash="deadbeef", repair_count=1,
        )


def test_repair_count_and_repair_output_must_agree():
    with pytest.raises(ValueError, match="repair_count"):
        episode(hypothesis_id=HypothesisId.H3, condition=H3_CONDITION, repair_count=3)


# --- measurements that cannot be fabricated --------------------------------------------------


def test_a_fabricated_token_count_cannot_pass_as_measured():
    """The directive's explicit requirement.

    Three routes are closed: an unknown instrument, a missing instrument, and a bare
    integer written straight into the field.
    """
    with pytest.raises(FabricatedMeasurement, match="not in KNOWN_INSTRUMENTS"):
        Measurement.measured(1234, instrument="i_estimated_it")
    with pytest.raises(FabricatedMeasurement, match="not in KNOWN_INSTRUMENTS"):
        Measurement(value=1234, provenance=Provenance.MEASURED)
    with pytest.raises(TypeError, match="must be a Measurement"):
        episode(prompt_tokens=1234)


def test_an_absent_measurement_cannot_smuggle_a_value():
    with pytest.raises(FabricatedMeasurement, match="cannot carry the value"):
        Measurement(value=7, provenance=Provenance.ABSENT, reason="none")


def test_an_absent_measurement_must_say_why():
    with pytest.raises(FabricatedMeasurement, match="must say why"):
        Measurement.absent("")


def test_a_measured_quantity_must_have_a_value():
    with pytest.raises(FabricatedMeasurement, match="must have a value"):
        Measurement(value=None, provenance=Provenance.MEASURED, instrument="tiktoken")


def test_a_negative_count_is_refused():
    with pytest.raises(FabricatedMeasurement):
        Measurement.measured(-1, instrument="time.perf_counter")


def test_naming_an_uninstalled_instrument_is_refused():
    """`tiktoken` is an optional extra and is not installed here (measured).

    An uninstalled tokeniser cannot have counted anything, so naming it is fabrication
    with extra steps. If tiktoken is ever installed, this test skips rather than lying.
    """
    if instrument_available("tiktoken"):
        pytest.skip("tiktoken is installed in this environment")
    with pytest.raises(FabricatedMeasurement, match="not available in this environment"):
        Measurement.measured(1200, instrument="tiktoken")


def test_an_unprobeable_instrument_must_cite_its_artefact():
    with pytest.raises(FabricatedMeasurement, match="must cite the artefact"):
        Measurement.measured(1200, instrument="provider_usage")


def test_the_offline_default_is_explicitly_absent():
    e = episode()
    for measurement in (e.prompt_tokens, e.completion_tokens, e.latency_ms):
        assert measurement.is_measured is False
        assert measurement.value is None
        assert "offline" in measurement.reason


def test_a_genuinely_measured_quantity_is_accepted():
    m = Measurement.measured(
        1200, instrument="provider_usage", citation="usage block of response resp-abc123"
    )
    assert m.is_measured and m.value == 1200
    assert episode(prompt_tokens=m).prompt_tokens.value == 1200

    latency = Measurement.measured(12.5, instrument="time.perf_counter")
    assert episode(latency_ms=latency).latency_ms.value == 12.5


def test_offline_absence_names_what_was_not_measured():
    assert "latency" in offline_absence("latency").reason


# --- outcome invariants -------------------------------------------------------------------------


def test_exclusion_must_be_explained():
    with pytest.raises(ValueError, match="must say why"):
        episode(training_eligible=False, exclusion_reason=None)


def test_eligible_and_excluded_cannot_both_hold():
    with pytest.raises(ValueError, match="cannot be training-eligible"):
        episode(training_eligible=True, exclusion_reason="excluded")


def test_a_verified_verdict_requires_a_verifier_that_verified():
    with pytest.raises(ValueError, match="actually verified"):
        episode(final_verdict=Verdict.VERIFIED)
    assert (
        episode(final_verdict=Verdict.VERIFIED, verifier_results=(VERIFIED_RESULT,))
        .final_verdict
        is Verdict.VERIFIED
    )


def test_machine_verified_confidence_requires_a_verified_verdict():
    with pytest.raises(ValueError, match="contradictory"):
        episode(
            final_verdict=Verdict.INCONCLUSIVE,
            confidence_tier=ConfidenceTier.MACHINE_VERIFIED,
        )


def test_counterexamples_are_carried_on_the_episode():
    e = episode(counterexamples=(Counterexample("false at x = 0", produced_by="sympy"),))
    assert e.to_dict()["counterexamples"][0]["produced_by"] == "sympy"
