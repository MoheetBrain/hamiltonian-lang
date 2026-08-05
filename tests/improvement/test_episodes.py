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
    StageOutcome,
    StageStatus,
    TerminalOutcome,
    TrainingEligibility,
    TrainingEligibilityOverride,
    Verdict,
    assert_single_hypothesis,
    classify_stages,
    group_by_contrast,
    instrument_available,
    offline_absence,
    output_hash,
)
from hamiltonian_lang.improvement.memory import (
    MemoryStoreKind,
    QuarantineEligibilityError,
    QuarantineReason,
    RoutingDecision,
    RoutingFacts,
    route,
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
        exclusion_reason="offline smoke episode; no model output to learn from",
    )
    base.update(kw)
    return Episode(**base)  # type: ignore[arg-type]


def eligible_decision(store: MemoryStoreKind = MemoryStoreKind.POSITIVE) -> RoutingDecision:
    """A router decision that says yes. Built here rather than hand-written on an
    episode, because that is now the only way to obtain one."""
    return RoutingDecision(
        store=store,
        training_eligible=True,
        reasons=("first attempt was faithful and every required verifier passed",),
    )


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
    """The single sentence a reader in a year most needs to find.

    Phrased as a prohibition rather than a quotation of the forbidden claim:
    ``test_hypothesis_separation`` bans the literal string "win for the representation"
    from every rendered H3 report, and a negated occurrence would still trip a reader
    skimming for it.
    """
    claim = HYPOTHESIS_CLAIMS[HypothesisId.H3].lower()
    assert "does not support any claim about the representation" in claim
    assert "misattributes the cause" in claim


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
        hypothesis_id=HypothesisId.EXCLUDED,
        condition=Condition(InputRepresentation.ENGLISH, False, False),
        input_representation=InputRepresentation.ENGLISH,
    )
    with pytest.raises(HypothesisMixing):
        assert_single_hypothesis([a, b])


def test_excluded_alone_is_still_refused_as_a_scientific_aggregate():
    """The old ``NONE`` was mixable-with-nothing but aggregatable-alone. ``EXCLUDED`` is
    not evidence, so a statistic over it is not a result and the guard says so."""
    pool = [
        episode(
            episode_id=i,
            hypothesis_id=HypothesisId.EXCLUDED,
            condition=Condition(InputRepresentation.ENGLISH, False, False),
            input_representation=InputRepresentation.ENGLISH,
        )
        for i in ("a", "b")
    ]
    with pytest.raises(HypothesisMixing, match="EXCLUDED"):
        assert_single_hypothesis(pool)
    # Counting non-evidence deliberately is still possible, and has to be asked for.
    assert assert_single_hypothesis(pool, allow_excluded=True) is HypothesisId.EXCLUDED


def test_the_old_none_member_is_gone_and_did_not_become_a_silent_alias():
    """``NONE`` read as "not recorded yet". Migrating it to ``EXCLUDED`` is the point of
    the change, so the old spelling must not still resolve."""
    assert not hasattr(HypothesisId, "NONE")
    with pytest.raises(ValueError):
        HypothesisId("NONE")


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
        episode(exclusion_reason=None)


def test_eligible_and_excluded_cannot_both_hold():
    with pytest.raises(ValueError, match="cannot be training-eligible"):
        episode(eligibility=TrainingEligibility.from_decision(eligible_decision()),
                exclusion_reason="excluded")


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


# --- Defect A: a compile verdict is not a parse verdict -------------------------------


#: Sources whose *only* defect is after the parser. Every one of these compiles to
#: ``False`` and parses to ``True``, which is the whole point: a harness reading
#: ``CompileResult.ok()`` as "parsed" would record all five as syntax failures and
#: understate ACQ0's first-attempt parse rate.
PARSES_BUT_DOES_NOT_COMPILE = {
    "HML-T426 wrong arity": (
        "module M\n"
        "param v : Vector[Real, 3]\n"
        "def s : Real := sum(v, v)\n",
        "HML-T426",
        TerminalOutcome.RESOLVED_TYPE_FAILED,
    ),
    "HML-T415 wrong role label": (
        "module M\n"
        "param mu : Real\n"
        "param v : PositiveReal\n"
        "var X : RandomVariable[Real]\n"
        "law X ~ Normal(location := mu, variance := v)\n",
        "HML-T415",
        TerminalOutcome.RESOLVED_TYPE_FAILED,
    ),
    "HML-T403 declared-type mismatch": (
        "module M\n"
        "param p : Probability = 0.5\n"
        "def d : PositiveReal := p\n",
        "HML-T403",
        TerminalOutcome.RESOLVED_TYPE_FAILED,
    ),
    "epistemic-kind mismatch": (
        "module M\n"
        "const pv : PValue := 0.05\n"
        "def post : PosteriorProbability := pv\n",
        "HML-T403",
        TerminalOutcome.RESOLVED_TYPE_FAILED,
    ),
    "unknown identifier": (
        "module M\ndef d : Real := nosuchthing\n",
        "HML-N301",
        TerminalOutcome.PARSE_PASSED_RESOLUTION_FAILED,
    ),
}


@pytest.mark.parametrize(
    "case", sorted(PARSES_BUT_DOES_NOT_COMPILE), ids=sorted(PARSES_BUT_DOES_NOT_COMPILE)
)
def test_a_post_parse_defect_is_never_classified_as_a_parse_failure(case):
    source, expected_code, expected_terminal = PARSES_BUT_DOES_NOT_COMPILE[case]
    from hamiltonian_lang import compile_source

    # The premise: the compile verdict says "no" for all of these.
    assert not compile_source(source).ok(), f"{case} unexpectedly compiles clean"

    outcome = classify_stages(source)
    assert outcome.parse_status is StageStatus.PASS, (case, outcome.to_dict())
    assert outcome.parsed is True
    assert outcome.compiled is False
    assert outcome.terminal is expected_terminal, (case, outcome.to_dict())
    assert outcome.terminal is not TerminalOutcome.PARSE_FAILED
    assert expected_code in outcome.diagnostic_codes, (case, outcome.diagnostic_codes)


def test_syntax_level_malformed_input_is_a_parse_failure_and_stops_there():
    outcome = classify_stages("module M\nparam p : = = =\n")
    assert outcome.parse_status is StageStatus.FAIL
    assert outcome.terminal is TerminalOutcome.PARSE_FAILED
    # Later stages were never given the input, so they have no verdict at all.
    assert outcome.resolution_status is StageStatus.NOT_RUN
    assert outcome.type_status is StageStatus.NOT_RUN


def test_an_empty_attempt_is_a_parse_failure_not_an_absent_measurement():
    outcome = classify_stages("   \n")
    assert outcome.terminal is TerminalOutcome.PARSE_FAILED
    assert outcome.diagnostic_codes == ("EMPTY",)


def test_a_clean_encoding_reaches_the_semantic_stage():
    source = "module M\nparam p : Probability = 0.5\n"
    outcome = classify_stages(source)
    assert outcome.compiled is True
    assert outcome.canonical_hash is not None
    # No reference supplied: nothing was compared, and that is NOT_APPLICABLE rather
    # than a pass.
    assert outcome.semantic_status is StageStatus.NOT_APPLICABLE

    matched = classify_stages(source, expected_canonical_hash=outcome.canonical_hash)
    assert matched.semantic_status is StageStatus.PASS
    assert matched.terminal is TerminalOutcome.SEMANTICALLY_PRESERVED

    other = classify_stages(source, expected_canonical_hash="0" * 64)
    assert other.terminal is TerminalOutcome.TYPED_SEMANTIC_LOSS
    assert other.parsed is True  # it parsed; the meaning is what differed


def test_a_verified_attempt_is_distinguished_from_a_merely_preserved_one():
    source = "module M\nparam p : Probability = 0.5\n"
    h = classify_stages(source).canonical_hash
    assert (
        classify_stages(source, expected_canonical_hash=h, verifier_passed=True).terminal
        is TerminalOutcome.VERIFIED
    )
    assert (
        classify_stages(source, expected_canonical_hash=h).terminal
        is TerminalOutcome.SEMANTICALLY_PRESERVED
    )


def test_the_terminal_outcome_and_the_parse_status_cannot_disagree():
    """The invariant that keeps the two halves of the type honest."""
    with pytest.raises(ValueError, match="disagree about whether the text parsed"):
        StageOutcome(
            parse_status=StageStatus.FAIL,
            resolution_status=StageStatus.NOT_RUN,
            type_status=StageStatus.NOT_RUN,
            semantic_status=StageStatus.NOT_RUN,
            verification_status=StageStatus.NOT_RUN,
            terminal=TerminalOutcome.RESOLVED_TYPE_FAILED,
        )


def test_all_eight_terminal_distinctions_exist():
    assert {t.value for t in TerminalOutcome} == {
        "PARSE_FAILED",
        "PARSE_PASSED_RESOLUTION_FAILED",
        "RESOLVED_TYPE_FAILED",
        "TYPED_SEMANTIC_LOSS",
        "SEMANTICALLY_PRESERVED",
        "VERIFIED",
        "INCONCLUSIVE",
        "UNSUPPORTED",
    }


# --- Defect B: the router is the only authority on training eligibility ---------------


def _quarantined_facts(**kw) -> RoutingFacts:
    base = dict(
        episode_id="ep-1",
        hypothesis=HypothesisId.H1,
        exact_hash="deadbeef",
        provenance_complete=False,  # fail-closed condition
    )
    base.update(kw)
    return RoutingFacts(**base)  # type: ignore[arg-type]


def test_a_caller_cannot_supply_training_eligible_at_all():
    """The defect in one line: a caller-supplied flag beside a router-derived one."""
    with pytest.raises(TrainingEligibilityOverride, match="router"):
        episode(training_eligible=True)


def test_a_caller_supplied_true_cannot_override_quarantine():
    """The requirement stated verbatim: quarantined data never reaches training.

    Every route a caller could take is closed: the decision object refuses to represent
    it, the eligibility record refuses to be built from it, and an unrouted episode is
    ineligible by default rather than by omission.
    """
    decision = route(_quarantined_facts())
    assert decision.store is MemoryStoreKind.QUARANTINE
    assert decision.training_eligible is False

    e = episode(eligibility=TrainingEligibility.from_decision(decision))
    assert e.training_eligible is False

    # 1. the decision object cannot be built saying otherwise
    with pytest.raises(QuarantineEligibilityError):
        RoutingDecision(
            store=MemoryStoreKind.QUARANTINE,
            training_eligible=True,
            reasons=("a caller insisted",),
        )
    # 2. nor can the eligibility record
    with pytest.raises(QuarantineEligibilityError):
        TrainingEligibility(
            eligible=True,
            store=MemoryStoreKind.QUARANTINE.value,
            reasons=("a caller insisted",),
            decided_by="a caller",
        )
    # 3. nor can the episode be told directly
    with pytest.raises(TrainingEligibilityOverride):
        episode(training_eligible=True)


def test_an_unrouted_episode_is_not_eligible():
    """Fail closed: the absence of a decision is not a decision to include."""
    e = episode()
    assert e.eligibility is None
    assert e.training_eligible is False


def test_an_excluded_episode_is_never_training_eligible():
    facts = _quarantined_facts(
        hypothesis=HypothesisId.EXCLUDED, provenance_complete=True
    )
    decision = route(facts)
    assert decision.store is MemoryStoreKind.QUARANTINE
    assert QuarantineReason.EXCLUDED_HYPOTHESIS in decision.quarantine_reasons
    assert decision.training_eligible is False

    with pytest.raises(QuarantineEligibilityError, match="EXCLUDED|engineering"):
        episode(
            hypothesis_id=HypothesisId.EXCLUDED,
            condition=Condition(InputRepresentation.ENGLISH, False, False),
            input_representation=InputRepresentation.ENGLISH,
            eligibility=TrainingEligibility.from_decision(eligible_decision()),
            exclusion_reason=None,
        )


def test_the_eligibility_record_names_the_authority_that_decided():
    e = episode(eligibility=TrainingEligibility.from_decision(eligible_decision()),
                exclusion_reason=None)
    assert e.training_eligible is True
    assert e.eligibility is not None
    assert "memory.route" in e.eligibility.decided_by
    assert e.to_dict()["training_eligibility"]["eligible"] is True


def test_an_unattributed_eligibility_decision_is_refused():
    with pytest.raises(ValueError, match="name the authority"):
        TrainingEligibility(
            eligible=False, store="quarantine", reasons=(), decided_by="  "
        )


# --- Defect C: one hypothesis type, ACQ0 separated from H3 ----------------------------


def test_there_is_exactly_one_hypothesis_type():
    from hamiltonian_lang.improvement import state

    assert HypothesisId is state.Hypothesis


def test_the_canonical_hypothesis_values():
    assert {h.value for h in HypothesisId} == {"ACQ0", "H1", "H2", "H3", "EXCLUDED"}


def test_an_arbitrary_string_is_not_a_hypothesis():
    for bad in ("h1", "H4", "NONE", "acq0", "", "H1 "):
        with pytest.raises(ValueError):
            HypothesisId(bad)


def test_acq0_repair_is_not_h3():
    """The distinction the register exists to protect. Conflating them would let 'the
    model learned to write the syntax with compiler help' read as 'verifier feedback
    improved mathematical reasoning'."""
    acq0 = episode(
        hypothesis_id=HypothesisId.ACQ0,
        condition=Condition(InputRepresentation.HAMILTONIAN, False, True),
        input_representation=InputRepresentation.HAMILTONIAN,
    ).with_repair(repair_output="module m\n")
    h3 = episode(
        hypothesis_id=HypothesisId.H3, condition=H3_CONDITION
    ).with_repair(repair_output="module m\n")

    assert acq0.repair_mechanism == "ACQ0_REPAIR"
    assert h3.repair_mechanism == "H3_VERIFIER_GUIDED_REPAIR"
    assert acq0.repair_mechanism != h3.repair_mechanism
    with pytest.raises(HypothesisMixing):
        assert_single_hypothesis([acq0, h3])


def test_an_acq0_episode_may_not_require_a_derivation():
    """That is H2's manipulation; an episode carrying both is evidence about neither."""
    with pytest.raises(ConfoundedCondition, match="H2's manipulation"):
        episode(
            hypothesis_id=HypothesisId.ACQ0,
            condition=Condition(InputRepresentation.HAMILTONIAN, True, False),
            input_representation=InputRepresentation.HAMILTONIAN,
        )


def test_acq0_is_scientific_and_excluded_is_not():
    assert HypothesisId.ACQ0.scientific is True
    assert HypothesisId.EXCLUDED.scientific is False


def test_the_acq0_claim_states_it_is_a_prerequisite_and_not_h3():
    text = HYPOTHESIS_CLAIMS[HypothesisId.ACQ0]
    assert "PREREQUISITE" in text
    assert "ACQ0_REPAIR" in text
