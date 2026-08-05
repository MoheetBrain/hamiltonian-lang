"""ACQ0 format-restriction protocol: the properties that make the comparison honest.

The tests are grouped by the failure each one prevents, because that is the useful
organisation when one of them goes red a year from now.

**No test in this file makes a model call.** Every backend used here is offline by
construction, and one of the tests asserts that a live backend without a Lead
authorisation raises rather than dialling out.
"""

from __future__ import annotations

import dataclasses

import pytest
from evaluation.acq0.prompts.field_order import (
    ANSWER_FIRST_ORDER,
    CANDIDATE_D_FIELD_ORDER_PROBE,
    CANONICAL_FIELD_ORDER,
    AnswerFirstNotLicensed,
    FieldOrderArm,
    FieldOrderViolation,
    FieldRole,
    assert_gate_field_order,
    official_gate_field_order,
    validate_field_order,
)
from evaluation.acq0.prompts.sensitivity import (
    INSTRUCTION_OBLIGATIONS,
    PHRASING_IDS,
    HeldOutTaskTouched,
    assert_development_subset_only,
    assert_phrasings_match_in_content,
    render_phrasing,
)
from evaluation.acq0.prompts.stages import (
    DEFAULT_PHRASING,
    UPSTREAM_HEADER,
    PromptStructureChanged,
    draft_prompt,
    formalise_prompt,
    plan_prompt,
    with_phrasing,
)
from evaluation.acq0.protocols.calibration import (
    CALIBRATION_CALL_COUNT,
    CALIBRATION_CELL_COUNT,
    CALIBRATION_CURRICULUM_SIZE,
    CALIBRATION_PROTOCOLS,
    ESCALATION_PROTOCOL,
    assert_calibration_tasks_are_not_evaluation,
    budget_report,
    calibration_cells,
    calibration_tasks,
    escalation_cells,
)
from evaluation.acq0.protocols.core import (
    PROTOCOL_STAGES,
    UNRESTRICTED_STAGES,
    GenerationProtocol,
    ProtocolTranscript,
    StageAccountingError,
    StageCall,
    StageKind,
    TokenLedger,
)
from evaluation.acq0.protocols.metrics import (
    EIGHT_METRICS,
    ArmSummary,
    ConflatedVerdict,
    ProtocolMetrics,
    aggregate,
    assert_no_conflated_verdict,
    format_adherence,
    metrics_for_reply,
)
from evaluation.acq0.protocols.oracle import (
    ORACLE_FIELDS,
    PERMITTED_TASK_INFORMATION,
    OracleLeak,
    TaskInformation,
    assert_demonstrations_disjoint,
    assert_information_parity,
    assert_no_oracle,
    protocol_information,
    scan_for_oracle,
)
from evaluation.acq0.protocols.runner import (
    AuthorisedSession,
    CallBudgetExhausted,
    ConformanceNotGreen,
    LiveCallAuthorisation,
    OfflineBackend,
    ScriptedBackend,
    UnauthorisedModelCall,
    run_protocol,
)
from evaluation.acq0.protocols.selection import (
    LEXICOGRAPHIC_KEYS,
    MATERIALITY,
    SelectionStatus,
    assert_no_weighted_scorer,
    select_protocol,
)
from evaluation.syntax_gate.candidates import A_V0_LINEAR, CANDIDATE_IDS, D_JSON_GRAPH
from evaluation.syntax_gate.prompts import build_prompt

from hamiltonian_lang.improvement.episodes import Measurement, offline_absence

TASK_A, TASK_B = calibration_tasks()

# --- fixtures measured against this compiler, not assumed ------------------------------
#: Not in the language. The only kind of input that is a parse failure.
BROKEN_SYNTAX = "module M\nconst a : Real = ((\n"
#: Parses and resolves; rejected by the type checker (HML-T402 family, declared-type
#: mismatch). Verified by ``test_the_conflation_defect_is_refuted_on_real_sources``.
TYPE_ERROR = "module M\nconst a : Probability = 2\n"
#: Parses; fails in *resolution* on an unknown name. A scope defect, not a syntax defect.
UNRESOLVED = "module M\ndef y : Real := zzz + 1\n"
#: Parses and resolves; rejected by the type checker on a wrong distribution role
#: (HML-T415). The exact class the directive names.
WRONG_ROLE = "module M\nvar x : Real\nlaw x ~ Normal(mean := 0.0, variance := 1.0)\n"
CLEAN = "module M\nconst a : Real = 2\nsolve a\n"


def _ledger(unrestricted: int | None, formal: int) -> TokenLedger:
    def m(v: int) -> Measurement:
        return Measurement.measured(v, instrument="provider_usage", citation="test fixture")

    if unrestricted is None:
        absent = Measurement.absent("no unrestricted stage ran")
        return TokenLedger(
            unrestricted=(absent, absent),
            formalisation=(m(formal), m(formal)),
            unrestricted_stage_ran=False,
        )
    return TokenLedger(
        unrestricted=(m(unrestricted), m(unrestricted)),
        formalisation=(m(formal), m(formal)),
        unrestricted_stage_ran=True,
    )


def _reply(encoding: str, tag: str = "hml", answer: str = "40.0") -> str:
    return f"Working.\n\n```{tag}\n{encoding}```\n\n<ANSWER>{answer}</ANSWER>"


# =======================================================================================
# 1. The protocols exist and their stage structure is enforced
# =======================================================================================


def test_three_protocols_with_the_stage_counts_the_design_claims():
    assert set(GenerationProtocol) == {
        GenerationProtocol.DIRECT_FORMAL,
        GenerationProtocol.DRAFT_THEN_FORMAL,
        GenerationProtocol.PLAN_THEN_FORMAL,
    }
    assert len(PROTOCOL_STAGES[GenerationProtocol.DIRECT_FORMAL]) == 1
    assert len(PROTOCOL_STAGES[GenerationProtocol.DRAFT_THEN_FORMAL]) == 2
    assert len(PROTOCOL_STAGES[GenerationProtocol.PLAN_THEN_FORMAL]) == 2


def test_the_first_stage_of_each_two_stage_protocol_is_format_unrestricted():
    for protocol in (
        GenerationProtocol.DRAFT_THEN_FORMAL,
        GenerationProtocol.PLAN_THEN_FORMAL,
    ):
        assert PROTOCOL_STAGES[protocol][0] in UNRESTRICTED_STAGES
        assert PROTOCOL_STAGES[protocol][-1] is StageKind.FORMALISE


def test_a_two_stage_transcript_missing_its_draft_call_is_refused():
    """The flattering error: two-stage quality reported at one-stage cost."""
    only_formal = StageCall(
        stage=StageKind.FORMALISE,
        protocol=GenerationProtocol.DRAFT_THEN_FORMAL,
        condition=A_V0_LINEAR,
    )
    with pytest.raises(StageAccountingError):
        ProtocolTranscript(
            protocol=GenerationProtocol.DRAFT_THEN_FORMAL,
            task_id=TASK_A.id,
            condition=A_V0_LINEAR,
            calls=(only_formal,),
        )


def test_a_call_cannot_be_recorded_under_a_protocol_that_does_not_run_its_stage():
    with pytest.raises(StageAccountingError):
        StageCall(
            stage=StageKind.DRAFT,
            protocol=GenerationProtocol.DIRECT_FORMAL,
            condition=A_V0_LINEAR,
        )


# =======================================================================================
# 2. Draft tokens are recorded separately from formalisation tokens
# =======================================================================================


def test_draft_and_formalisation_costs_are_separate_fields():
    ledger = _ledger(unrestricted=120, formal=300)
    assert ledger.unrestricted_completion_tokens.value == 120
    assert ledger.formalisation_completion_tokens.value == 300
    assert ledger.total_completion_tokens.value == 420


def test_the_two_stage_protocol_cannot_report_one_stage_cost():
    """Identical formalisation cost; the two-stage arm's total must be strictly larger."""
    one = _ledger(unrestricted=None, formal=300)
    two = _ledger(unrestricted=120, formal=300)
    assert one.total_completion_tokens.value == 300
    assert two.total_completion_tokens.value == 420
    assert two.total_completion_tokens.value > one.total_completion_tokens.value


def test_a_stage_that_ran_but_was_not_measured_has_no_total():
    """Absent is not zero. A total over a partially measured run invites a false compare."""
    ledger = TokenLedger(
        unrestricted=(offline_absence("prompt"), offline_absence("completion")),
        formalisation=(
            Measurement.measured(10, instrument="provider_usage", citation="fixture"),
            Measurement.measured(10, instrument="provider_usage", citation="fixture"),
        ),
        unrestricted_stage_ran=True,
    )
    assert not ledger.total_completion_tokens.is_measured
    assert "absent" in ledger.total_completion_tokens.reason


def test_a_stage_that_never_ran_contributes_a_structural_zero():
    """DIRECT_FORMAL must have a complete total, or it cannot be compared on cost at all."""
    ledger = _ledger(unrestricted=None, formal=300)
    assert ledger.total_completion_tokens.is_measured
    assert ledger.total_completion_tokens.value == 300


def test_the_ledger_exposes_no_settable_total():
    names = {f.name for f in dataclasses.fields(TokenLedger)}
    assert not any("total" in n for n in names), (
        f"{names} contains a settable total; totals must be derived so a two-stage run "
        "cannot be recorded at a one-stage price"
    )


def test_an_end_to_end_offline_run_records_both_stages():
    backend = ScriptedBackend(
        lambda stage, condition, task_id: (
            "unrestricted working" if stage != "formalise" else _reply(CLEAN)
        )
    )
    transcript = run_protocol(
        TASK_A, A_V0_LINEAR, GenerationProtocol.DRAFT_THEN_FORMAL, backend
    )
    assert [str(c.stage) for c in transcript.calls] == ["draft", "formalise"]
    assert transcript.ledger.unrestricted_completion_tokens.is_measured
    assert transcript.ledger.formalisation_completion_tokens.is_measured
    assert transcript.unrestricted_output == "unrestricted working"


# =======================================================================================
# 3. No hidden oracle information reaches any stage
# =======================================================================================


def test_the_draft_prompt_carries_no_oracle_content():
    prompt = draft_prompt(TASK_A, A_V0_LINEAR)
    assert scan_for_oracle(prompt.user, TASK_A.cso) == ()


def test_the_plan_prompt_carries_no_oracle_content():
    prompt = plan_prompt(TASK_A, A_V0_LINEAR)
    assert scan_for_oracle(prompt.user, TASK_A.cso) == ()


@pytest.mark.parametrize("condition", list(CANDIDATE_IDS))
def test_the_formalisation_prompt_carries_no_oracle_content(condition):
    prompt = formalise_prompt(TASK_A, condition, GenerationProtocol.DIRECT_FORMAL)
    assert scan_for_oracle(prompt.user, TASK_A.cso) == ()


def test_the_guard_actually_catches_an_injected_reference_line():
    """A guard that never fires is not evidence; this is the positive control."""
    line = next(
        ln.strip()
        for ln in TASK_A.cso.reference_hml.splitlines()
        if len(ln.strip()) >= 6
    )
    poisoned = draft_prompt(TASK_A, A_V0_LINEAR).user + "\n\nHint: " + line
    findings = scan_for_oracle(poisoned, TASK_A.cso)
    assert any(f.field is TaskInformation.REFERENCE_ENCODING for f in findings)
    with pytest.raises(OracleLeak):
        assert_no_oracle(poisoned, TASK_A.cso)


def test_the_unrestricted_stage_names_no_target_syntax():
    """If the draft differed per candidate it would be four first stages, not one."""
    users = {c: draft_prompt(TASK_A, c).user for c in CANDIDATE_IDS}
    assert len(set(users.values())) == 1, "the draft prompt differs between candidates"
    body = next(iter(users.values()))
    for forbidden in ("```", "CONCISE REFERENCE", "triples", "S-expression"):
        assert forbidden not in body


def test_the_unrestricted_stage_is_marked_unrestricted():
    assert draft_prompt(TASK_A, A_V0_LINEAR).format_restricted is False
    assert plan_prompt(TASK_A, A_V0_LINEAR).format_restricted is False
    assert (
        formalise_prompt(
            TASK_A, A_V0_LINEAR, GenerationProtocol.DIRECT_FORMAL
        ).format_restricted
        is True
    )


def test_every_protocol_arm_receives_matched_task_information():
    assert_information_parity(list(GenerationProtocol))


def test_no_protocol_declares_it_may_carry_an_oracle_field():
    for protocol in GenerationProtocol:
        assert not (protocol_information(protocol) & ORACLE_FIELDS)


def test_the_permitted_set_and_the_oracle_set_are_disjoint():
    assert not (PERMITTED_TASK_INFORMATION & ORACLE_FIELDS)


def test_the_only_permitted_difference_between_arms_is_the_models_own_output():
    direct = protocol_information(GenerationProtocol.DIRECT_FORMAL)
    draft = protocol_information(GenerationProtocol.DRAFT_THEN_FORMAL)
    assert draft - direct == {TaskInformation.UPSTREAM_MODEL_OUTPUT}


def test_a_task_may_not_appear_in_its_own_demonstration_curriculum():
    """The genuine leak: the model shown the answer encoding for the task it must encode."""
    from evaluation.syntax_gate.candidates import resolve_adapters
    from evaluation.syntax_gate.partition import demonstration_curriculum
    from evaluation.syntax_gate.tasks import build_track_a

    by_id = {t.id: t for t in build_track_a()}
    demos = [by_id[i] for i in demonstration_curriculum(50)]
    assert TASK_A.id in {d.id for d in demos}, (
        "this test needs a task that is in the demonstration pool; TASK_A is one by "
        "construction, which is exactly why calibration runs at curriculum 0"
    )
    with pytest.raises(OracleLeak):
        formalise_prompt(
            TASK_A,
            A_V0_LINEAR,
            GenerationProtocol.DIRECT_FORMAL,
            demonstrations=demos,
            adapters=resolve_adapters(),
        )


def test_a_duplicated_task_under_a_different_id_is_still_caught():
    """Ids can differ while content does not; the content hash is the instrument."""
    twin = dataclasses.replace(TASK_A, cso=dataclasses.replace(TASK_A.cso))
    twin.cso.id = "some_other_id"
    assert twin.id != TASK_A.id
    assert twin.content_hash == TASK_A.content_hash
    with pytest.raises(OracleLeak) as exc:
        assert_demonstrations_disjoint(TASK_A, [twin])
    assert "content hash" in str(exc.value)


def test_the_scan_does_not_fire_on_legitimate_demonstrations_of_other_tasks():
    """Measured: a substring scan over the demonstration block flags 281 of 320 gate
    prompts, every one a false alarm, because the corpus reuses module names per domain
    and draws symbols from a shared pool. A guard with an 88% false-alarm rate gets
    switched off, taking the real check with it."""
    from evaluation.syntax_gate.candidates import resolve_adapters
    from evaluation.syntax_gate.partition import (
        TRACK_A_GATE_IDS,
        demonstration_curriculum,
    )
    from evaluation.syntax_gate.tasks import build_track_a

    by_id = {t.id: t for t in build_track_a()}
    demos = [by_id[i] for i in demonstration_curriculum(50)]
    adapters = resolve_adapters()
    sample = sorted(TRACK_A_GATE_IDS)[:4]
    for tid in sample:
        for condition in CANDIDATE_IDS:
            formalise_prompt(
                by_id[tid],
                condition,
                GenerationProtocol.DIRECT_FORMAL,
                demonstrations=demos,
                adapters=adapters,
            )


def test_the_models_own_answer_in_its_draft_is_not_treated_as_a_leak():
    """A model that solved the problem writes the gold answer into its own draft.

    Flagging that would accuse the harness of revealing an answer the model derived, and
    would make the two-stage protocol unrunnable on every task it gets right.
    """
    gold = str(TASK_A.cso.answer.value)
    backend = ScriptedBackend(
        lambda stage, condition, task_id: (
            f"I make it {gold}." if stage != "formalise" else _reply(CLEAN)
        )
    )
    transcript = run_protocol(
        TASK_A, A_V0_LINEAR, GenerationProtocol.DRAFT_THEN_FORMAL, backend
    )
    assert UPSTREAM_HEADER in backend.calls[1]["user"]
    assert gold in backend.calls[1]["user"]
    assert len(transcript.calls) == 2


# =======================================================================================
# 4. The eight metrics, and the CompileResult.ok() conflation
# =======================================================================================


def test_there_are_exactly_eight_metrics_and_they_are_eight_fields():
    assert len(EIGHT_METRICS) == 8
    fields = {f.name for f in dataclasses.fields(ProtocolMetrics)}
    assert set(EIGHT_METRICS) <= fields


def test_the_metrics_record_exposes_no_aggregate():
    banned = ("score", "overall", "combined", "weighted", "summary_value")
    found = [
        name
        for name in dir(ProtocolMetrics)
        if any(b in name.lower() for b in banned) and not name.startswith("_")
    ]
    assert not found, (
        f"ProtocolMetrics exposes {found}. Format adherence near 1.0 alongside degraded "
        "semantic preservation is the documented failure mode; a single number hides it."
    )


@pytest.mark.parametrize(
    "source,parse,resolution,type_",
    [
        (BROKEN_SYNTAX, False, None, None),
        (UNRESOLVED, True, False, None),
        (TYPE_ERROR, True, True, False),
        (WRONG_ROLE, True, True, False),
        (CLEAN, True, True, True),
    ],
)
def test_the_conflation_defect_is_refuted_on_real_sources(source, parse, resolution, type_):
    """Four of these five would be one boolean under ``CompileResult.ok()``.

    Only ``BROKEN_SYNTAX`` is a parse failure. ``UNRESOLVED`` is a scope defect;
    ``TYPE_ERROR`` and ``WRONG_ROLE`` (HML-T415, a wrong distribution role) parse **and**
    resolve cleanly. Counting any of them as a parse failure understates ACQ0's
    first-attempt parse rate and blames the surface syntax for the type checker.
    """
    m = metrics_for_reply(
        _reply(source),
        source,
        fence_tags=("hml",),
        expected_canonical_hash=None,
        token_cost=_ledger(None, 10),
    )
    assert m.parse_success is parse
    assert m.resolution_success is resolution
    assert m.type_success is type_


def test_a_wrong_role_is_a_type_defect_and_not_a_syntax_defect():
    m = metrics_for_reply(
        _reply(WRONG_ROLE),
        WRONG_ROLE,
        fence_tags=("hml",),
        expected_canonical_hash=None,
        token_cost=_ledger(None, 10),
    )
    assert m.parse_success is True
    assert m.type_success is False
    assert any(c.startswith("HML-T4") for c in m.diagnostic_codes)


def test_format_adherence_and_parse_success_are_independent_measurements():
    """The paper's 0.148%-parse-error / 38-point-gap pattern, as a type-level property."""
    adherent_but_broken = metrics_for_reply(
        _reply(BROKEN_SYNTAX),
        BROKEN_SYNTAX,
        fence_tags=("hml",),
        expected_canonical_hash=None,
        token_cost=_ledger(None, 10),
    )
    assert adherent_but_broken.format_adherence is True
    assert adherent_but_broken.parse_success is False

    unfenced_but_valid = metrics_for_reply(
        f"{CLEAN}\n<ANSWER>2</ANSWER>",
        CLEAN,
        fence_tags=("hml",),
        expected_canonical_hash=None,
        token_cost=_ledger(None, 10),
    )
    assert unfenced_but_valid.format_adherence is False
    assert unfenced_but_valid.parse_success is True


def test_an_untagged_fence_is_not_counted_as_format_adherence():
    """The extractor tolerates one; measuring the tolerance would credit the model with
    compliance it did not produce."""
    assert format_adherence("```\nx\n```", ("hml",)) is False
    assert format_adherence("```hml\nx\n```", ("hml",)) is True


def test_a_record_that_conflates_stages_is_refused_at_construction():
    with pytest.raises(ConflatedVerdict):
        ProtocolMetrics(
            format_adherence=True,
            parse_success=False,
            resolution_success=True,
            type_success=None,
            semantic_preservation_exact=None,
            repair_success=None,
            token_cost=_ledger(None, 1),
            latency=offline_absence("latency"),
        )


def test_a_third_party_object_offering_only_ok_is_refused():
    class LooksLikeCompileResult:
        def ok(self) -> bool:
            return True

    with pytest.raises(ConflatedVerdict):
        assert_no_conflated_verdict(LooksLikeCompileResult())


def test_repair_that_fixes_syntax_and_leaves_a_type_error_counts_as_a_repaired_parse():
    m = metrics_for_reply(
        _reply(BROKEN_SYNTAX),
        BROKEN_SYNTAX,
        fence_tags=("hml",),
        expected_canonical_hash=None,
        token_cost=_ledger(None, 10),
        repair_encoding=TYPE_ERROR,
    )
    assert m.parse_success is False
    assert m.repair_success is True, (
        "a repair that makes the text grammatical repaired the parse; it failing in the "
        "type checker is a different measurement"
    )


def test_no_repair_attempted_is_not_a_failed_repair():
    m = metrics_for_reply(
        _reply(CLEAN),
        CLEAN,
        fence_tags=("hml",),
        expected_canonical_hash=None,
        token_cost=_ledger(None, 10),
    )
    assert m.repair_success is None


def test_exact_semantic_preservation_is_hash_equality_against_the_reference():
    from hamiltonian_lang.improvement.episodes import classify_stages

    expected = classify_stages(TASK_A.cso.reference_hml).canonical_hash
    assert expected is not None
    hit = metrics_for_reply(
        _reply(TASK_A.cso.reference_hml),
        TASK_A.cso.reference_hml,
        fence_tags=("hml",),
        expected_canonical_hash=expected,
        token_cost=_ledger(None, 10),
    )
    assert hit.semantic_preservation_exact is True
    miss = metrics_for_reply(
        _reply(CLEAN),
        CLEAN,
        fence_tags=("hml",),
        expected_canonical_hash=expected,
        token_cost=_ledger(None, 10),
    )
    assert miss.parse_success is True
    assert miss.semantic_preservation_exact is False


def test_rates_are_over_what_was_measured_not_over_what_was_attempted():
    trials = [
        metrics_for_reply(
            _reply(s),
            s,
            fence_tags=("hml",),
            expected_canonical_hash=None,
            token_cost=_ledger(None, 10),
        )
        for s in (CLEAN, BROKEN_SYNTAX, TYPE_ERROR)
    ]
    summary = aggregate("DIRECT_FORMAL", trials)
    # parse was measured on all three; type only on the two that parsed and resolved.
    assert summary.denominators["parse_success"] == 3
    assert summary.denominators["type_success"] == 2
    assert summary.rates["type_success"] == 0.5


# =======================================================================================
# 5. Field order as an inductive bias
# =======================================================================================


def test_the_canonical_order_puts_prerequisites_before_the_result():
    assert CANONICAL_FIELD_ORDER[-1] is FieldRole.RESULT
    validate_field_order(CANONICAL_FIELD_ORDER)
    assert official_gate_field_order() == CANONICAL_FIELD_ORDER


def test_answer_first_violates_the_order_by_construction():
    with pytest.raises(FieldOrderViolation):
        validate_field_order(ANSWER_FIRST_ORDER)


def test_the_gate_refuses_answer_first_without_evidence():
    assert_gate_field_order(FieldOrderArm.SEMANTIC_FIRST)
    with pytest.raises(AnswerFirstNotLicensed):
        assert_gate_field_order(FieldOrderArm.ANSWER_FIRST)


@pytest.mark.parametrize(
    "evidence",
    [
        {"probe_run": False, "degrades_semantic_preservation": False, "citation": "x"},
        {"probe_run": True, "degrades_semantic_preservation": True, "citation": "x"},
        {"probe_run": True, "degrades_semantic_preservation": None, "citation": "x"},
        {"probe_run": True, "degrades_semantic_preservation": False, "citation": "  "},
    ],
)
def test_partial_evidence_does_not_license_answer_first(evidence):
    with pytest.raises(AnswerFirstNotLicensed):
        assert_gate_field_order(FieldOrderArm.ANSWER_FIRST, evidence=evidence)


def test_complete_evidence_does_license_answer_first():
    assert_gate_field_order(
        FieldOrderArm.ANSWER_FIRST,
        evidence={
            "probe_run": True,
            "degrades_semantic_preservation": False,
            "citation": "evaluation/results/acq0/field_order_probe.json",
        },
    )


def test_the_field_order_probe_targets_candidate_d_and_no_scoring_pool():
    probe = CANDIDATE_D_FIELD_ORDER_PROBE
    assert probe.candidate_id == D_JSON_GRAPH
    assert set(probe.arms) == {FieldOrderArm.SEMANTIC_FIRST, FieldOrderArm.ANSWER_FIRST}
    assert "demonstration" in probe.task_pool
    assert "never" in probe.task_pool, "the pool must state which stages it excludes"
    assert "candidate D" in probe.scope_of_conclusion


def test_the_answer_first_arm_is_buildable_so_the_probe_can_actually_run():
    """A refusal is only meaningful if the refused thing exists to be compared against."""
    prompt = draft_prompt(TASK_A, A_V0_LINEAR, field_order_arm=FieldOrderArm.ANSWER_FIRST)
    assert prompt.field_order_arm is FieldOrderArm.ANSWER_FIRST


# =======================================================================================
# 6. Prompt sensitivity
# =======================================================================================


def test_there_are_three_phrasings_and_all_carry_the_same_content():
    assert len(PHRASING_IDS) == 3
    assert DEFAULT_PHRASING in PHRASING_IDS
    assert_phrasings_match_in_content()
    for tag in ("hml", "sexpr", "json"):
        assert_phrasings_match_in_content(tag)


def test_a_phrasing_that_drops_an_obligation_is_caught(monkeypatch):
    """The negative control. A checker that cannot fail is not evidence of anything."""
    from evaluation.acq0.prompts import sensitivity

    monkeypatch.setattr(
        sensitivity,
        "PHRASINGS",
        {**sensitivity.PHRASINGS, "P2_descriptive": "Please do your best."},
    )
    with pytest.raises(sensitivity.PhrasingContentMismatch) as exc:
        sensitivity.assert_phrasings_match_in_content()
    assert "P2_descriptive" in str(exc.value)
    assert len(INSTRUCTION_OBLIGATIONS) >= 5


def test_the_phrasings_are_actually_different_strings():
    rendered = {render_phrasing(p, "hml") for p in PHRASING_IDS}
    assert len(rendered) == 3


def test_the_default_phrasing_leaves_the_tournament_prompt_untouched():
    base = build_prompt(TASK_A, A_V0_LINEAR)
    direct = formalise_prompt(TASK_A, A_V0_LINEAR, GenerationProtocol.DIRECT_FORMAL)
    assert direct.user == base.user
    assert direct.system == base.system


def test_an_alternative_phrasing_changes_the_method_block_and_nothing_else():
    base = build_prompt(TASK_A, D_JSON_GRAPH)
    alt = formalise_prompt(
        TASK_A,
        D_JSON_GRAPH,
        GenerationProtocol.DIRECT_FORMAL,
        phrasing_id="P3_procedural",
    )
    assert alt.user != base.user
    assert TASK_A.cso.prose in alt.user
    assert TASK_A.cso.question in alt.user
    assert "```json" in alt.user


def test_a_silent_no_op_substitution_is_impossible():
    with pytest.raises(PromptStructureChanged):
        with_phrasing("no method block here", "P2_descriptive", A_V0_LINEAR)


def test_a_held_out_task_cannot_reach_a_developmental_probe():
    from evaluation.syntax_gate.partition import TRACK_A_GATE_IDS

    assert_development_subset_only([TASK_A.id, TASK_B.id])
    with pytest.raises(HeldOutTaskTouched):
        assert_development_subset_only([sorted(TRACK_A_GATE_IDS)[0]])


# =======================================================================================
# 7. No model call happens without the Lead's authorisation
# =======================================================================================


def test_the_default_backend_is_offline():
    transcript = run_protocol(TASK_A, A_V0_LINEAR, GenerationProtocol.DIRECT_FORMAL)
    assert transcript.formal_output == ""
    assert OfflineBackend.LIVE is False


def test_a_live_backend_without_authorisation_raises():
    class PretendLive:
        LIVE = True

        def generate(self, system: str, user: str) -> dict:  # pragma: no cover
            raise AssertionError("a model call was made without authorisation")

    with pytest.raises(UnauthorisedModelCall):
        run_protocol(
            TASK_A, A_V0_LINEAR, GenerationProtocol.DIRECT_FORMAL, PretendLive()
        )


def test_an_authorisation_against_a_red_tree_is_refused():
    with pytest.raises(ConformanceNotGreen):
        LiveCallAuthorisation(
            authorised_by="Lead",
            call_budget=24,
            scope="ACQ0 calibration",
            conformance_state="red: 24 findings in equivalence/",
        )


@pytest.mark.parametrize(
    "kw",
    [
        {"authorised_by": "  "},
        {"call_budget": 0},
        {"scope": ""},
    ],
)
def test_an_incomplete_authorisation_is_refused(kw):
    base = {
        "authorised_by": "Lead",
        "call_budget": 24,
        "scope": "ACQ0 calibration",
        "conformance_state": "green",
    }
    with pytest.raises(ValueError):
        LiveCallAuthorisation(**{**base, **kw})


def test_the_call_budget_is_spent_and_then_refuses():
    auth = LiveCallAuthorisation(
        authorised_by="Lead",
        call_budget=2,
        scope="ACQ0 calibration",
        conformance_state="green",
    )
    session = AuthorisedSession(auth)
    session.charge("one")
    session.charge("two")
    assert session.remaining == 0
    with pytest.raises(CallBudgetExhausted):
        session.charge("three")


def test_a_two_stage_protocol_charges_two_calls_against_the_budget():
    """The budget arithmetic the cell count would get wrong."""

    class CountingLive:
        LIVE = True

        def __init__(self) -> None:
            self.n = 0

        def generate(self, system: str, user: str) -> dict:
            self.n += 1
            return {
                "content": _reply(CLEAN),
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "latency_s": 0.0,
                "finish_reason": "stop",
                "error": None,
            }

    auth = LiveCallAuthorisation(
        authorised_by="Lead",
        call_budget=2,
        scope="test",
        conformance_state="green",
    )
    session = AuthorisedSession(auth)
    backend = CountingLive()
    run_protocol(
        TASK_A,
        A_V0_LINEAR,
        GenerationProtocol.DRAFT_THEN_FORMAL,
        backend,
        session=session,
    )
    assert backend.n == 2
    assert session.calls_made == 2


# =======================================================================================
# 8. Selection is lexicographic, and refuses when it should
# =======================================================================================


def _arm(
    protocol: str,
    *,
    preservation: float | None = 0.5,
    repair: float | None = 0.5,
    domains: dict[str, float | None] | None = None,
    tokens: int | None = 1000,
    latency: float | None = 10.0,
    valid: bool = True,
    n: int = 8,
) -> ArmSummary:
    def m(v, instrument):
        return (
            Measurement.measured(v, instrument=instrument, citation="fixture")
            if v is not None
            else Measurement.absent("not measured in this fixture")
        )

    return ArmSummary(
        protocol=protocol,
        n_trials=n,
        denominators={"parse_success": n, "semantic_preservation_exact": n},
        rates={
            "semantic_preservation_exact": preservation,
            "repair_success": repair,
            "parse_success": 1.0,
        },
        total_prompt_tokens=m(tokens, "provider_usage"),
        total_completion_tokens=m(tokens, "provider_usage"),
        total_latency_s=m(latency, "time.perf_counter"),
        per_domain_preservation=domains or {"binding_chain": 0.5, "distribution_law": 0.5},
        constitutionally_valid=valid,
        constitutional_findings=() if valid else ("oracle leak in the draft prompt",),
    )


def test_the_key_order_is_the_one_the_directive_specifies():
    assert LEXICOGRAPHIC_KEYS[0] == "constitutional_validity"
    assert LEXICOGRAPHIC_KEYS[1] == "semantic_preservation"
    assert LEXICOGRAPHIC_KEYS.index("token_cost") > LEXICOGRAPHIC_KEYS.index(
        "semantic_preservation"
    )
    assert "parse_rate" not in LEXICOGRAPHIC_KEYS


def test_zero_measured_trials_cannot_produce_a_selection():
    result = select_protocol([_arm("DIRECT_FORMAL", n=0), _arm("DRAFT_THEN_FORMAL", n=0)])
    assert result.status is SelectionStatus.UNSTABLE
    assert result.protocol is None


def test_no_arms_at_all_cannot_produce_a_selection():
    assert select_protocol([]).status is SelectionStatus.UNSTABLE


def test_a_constitutional_violation_disqualifies_before_any_number_is_read():
    result = select_protocol(
        [
            _arm("DIRECT_FORMAL", preservation=1.0, valid=False),
            _arm("DRAFT_THEN_FORMAL", preservation=0.1),
        ]
    )
    assert result.status is SelectionStatus.SELECTED
    assert result.protocol == "DRAFT_THEN_FORMAL"
    assert result.decided_by == "constitutional_validity"


def test_token_efficiency_never_compensates_for_semantic_corruption():
    """The property the whole design rests on."""
    cheap_and_wrong = _arm("DIRECT_FORMAL", preservation=0.25, tokens=100, latency=1.0)
    dear_and_right = _arm("DRAFT_THEN_FORMAL", preservation=1.0, tokens=100_000, latency=900.0)
    result = select_protocol([cheap_and_wrong, dear_and_right])
    assert result.status is SelectionStatus.SELECTED
    assert result.protocol == "DRAFT_THEN_FORMAL"
    assert result.decided_by == "semantic_preservation"


def test_an_absent_key_is_unavailable_and_not_a_tie():
    result = select_protocol(
        [
            _arm("DIRECT_FORMAL", preservation=None),
            _arm("DRAFT_THEN_FORMAL", preservation=0.9),
        ]
    )
    assert result.status is SelectionStatus.UNSTABLE
    assert result.decided_by == "semantic_preservation"


def test_a_full_tie_escalates_rather_than_falling_through_to_cost():
    result = select_protocol([_arm("DIRECT_FORMAL"), _arm("DRAFT_THEN_FORMAL")])
    assert result.status is SelectionStatus.AMBIGUOUS
    assert result.protocol is None
    assert "PLAN_THEN_FORMAL" in " ".join(result.reasons)


def test_a_difference_below_the_materiality_threshold_does_not_decide():
    below = MATERIALITY["semantic_preservation"] / 2
    result = select_protocol(
        [
            _arm("DIRECT_FORMAL", preservation=0.5),
            _arm("DRAFT_THEN_FORMAL", preservation=0.5 + below),
        ]
    )
    assert result.status is SelectionStatus.AMBIGUOUS


def test_domain_stability_reads_the_worst_domain_not_the_mean():
    lopsided = _arm(
        "DIRECT_FORMAL",
        domains={"binding_chain": 1.0, "distribution_law": 0.0},
    )
    even = _arm(
        "DRAFT_THEN_FORMAL",
        domains={"binding_chain": 0.5, "distribution_law": 0.5},
    )
    result = select_protocol([lopsided, even])
    assert result.status is SelectionStatus.SELECTED
    assert result.protocol == "DRAFT_THEN_FORMAL"
    assert result.decided_by == "domain_stability"


def test_the_selector_module_exposes_no_weighted_combiner():
    assert_no_weighted_scorer()


# =======================================================================================
# 9. The calibration design
# =======================================================================================


def test_the_design_is_four_syntaxes_by_two_tasks_by_two_protocols():
    assert CALIBRATION_CELL_COUNT == 16
    cells = calibration_cells()
    assert len(cells) == 16
    assert {c.condition for c in cells} == set(CANDIDATE_IDS)
    assert len({c.task_id for c in cells}) == 2
    assert {c.protocol for c in cells} == set(CALIBRATION_PROTOCOLS)


def test_sixteen_cells_are_twenty_four_calls_because_one_arm_has_two_stages():
    """An authorisation written against the cell count is short by the draft stage."""
    report = budget_report()
    assert report["cells"] == 16
    assert report["calls"] == 24 == CALIBRATION_CALL_COUNT
    assert report["per_protocol"]["DIRECT_FORMAL"]["calls"] == 8
    assert report["per_protocol"]["DRAFT_THEN_FORMAL"]["calls"] == 16


def test_no_calibration_task_can_ever_score_the_gate():
    assert_calibration_tasks_are_not_evaluation()
    from evaluation.syntax_gate.partition import TRACK_A_HELD_OUT_IDS, partition

    stage_of = partition()["stage_of"]
    for task in calibration_tasks():
        assert task.id not in TRACK_A_HELD_OUT_IDS
        assert stage_of[task.id] == "demonstration"


def test_the_guard_catches_a_held_out_calibration_task():
    from evaluation.syntax_gate.partition import TRACK_A_GATE_IDS
    from evaluation.syntax_gate.tasks import build_track_a

    gate_id = sorted(TRACK_A_GATE_IDS)[0]
    gate_task = next(t for t in build_track_a() if t.id == gate_id)
    with pytest.raises(AssertionError):
        assert_calibration_tasks_are_not_evaluation([gate_task])


def test_the_two_calibration_tasks_come_from_different_domains():
    a, b = calibration_tasks()
    assert a.domain != b.domain


def test_the_calibration_runs_at_curriculum_zero_so_no_task_demonstrates_itself():
    assert CALIBRATION_CURRICULUM_SIZE == 0
    assert all(c.curriculum_size == 0 for c in calibration_cells())


def test_plan_then_formal_is_the_escalation_and_not_part_of_the_first_pass():
    assert ESCALATION_PROTOCOL is GenerationProtocol.PLAN_THEN_FORMAL
    assert ESCALATION_PROTOCOL not in CALIBRATION_PROTOCOLS
    assert {c.protocol for c in escalation_cells()} == {ESCALATION_PROTOCOL}
    assert sum(c.calls for c in escalation_cells()) == 16


def test_the_design_record_states_that_nothing_has_been_executed():
    from evaluation.acq0.protocols.calibration import calibration_design

    design = calibration_design()
    assert design["executed"] is False
    assert design["budget"]["calls"] == 24
    assert design["selection"]["keys_in_order"][1] == "semantic_preservation"
