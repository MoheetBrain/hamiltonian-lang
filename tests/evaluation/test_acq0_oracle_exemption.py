"""The ACQ0 oracle exemption is scoped to ACQ0 and unreachable from H1/H2/H3.

The property under test is not "the exemption works". It is "the exemption cannot be
reached from a reasoning prompt". Three independent instruments, because any one of them
alone can be defeated by a plausible edit:

* the **type** refuses to exist for a reasoning hypothesis;
* the **guard** refuses an exemption presented under a reasoning hypothesis;
* the **call sites** in ``evaluation/acq0/prompts/stages.py`` -- which build every H1/H2/H3
  prompt -- pass no exemption, checked against the source text so that adding one is a
  test failure and not a review question.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from evaluation.acq0.prompts import stages as stages_module
from evaluation.acq0.protocols.calibration import (
    FROZEN_CURRICULUM_IDS,
    calibration_tasks,
)
from evaluation.acq0.protocols.encoding import (
    ACQ0_ENCODING_INSTRUCTION,
    ACQ0_TARGET_HEADER,
    TaskQuarantined,
    acq0_encoding_prompt,
    assert_mathematics_fixed_independently,
    quarantine_report,
    render_disclosure,
)
from evaluation.acq0.protocols.ledger import derive_call_ledger, phase_authorisation
from evaluation.acq0.protocols.oracle import (
    ACQ0_ANSWER_FACET_VOID,
    ACQ0_ENCODING_DISCLOSURE,
    ACQ0_ENCODING_EXEMPTION,
    NEVER_DISCLOSED,
    REASONING_HYPOTHESES,
    ExemptionMisuse,
    Hypothesis,
    OracleExemption,
    TaskInformation,
    assert_no_oracle,
)


def _task():
    return calibration_tasks()[0]


# ---------------------------------------------------------------------------
# 1. The type refuses to exist outside ACQ0
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("hypothesis", sorted(REASONING_HYPOTHESES))
def test_exemption_cannot_be_constructed_for_a_reasoning_hypothesis(hypothesis):
    with pytest.raises(ExemptionMisuse) as exc:
        OracleExemption(
            hypothesis=hypothesis,
            granted_by="anyone",
            authority="anything",
            rationale="any reason",
            permits=ACQ0_ENCODING_DISCLOSURE,
        )
    assert "ACQ0" in str(exc.value)


def test_exemption_may_never_disclose_the_reference_encoding_or_distractors():
    for forbidden in NEVER_DISCLOSED:
        with pytest.raises(ExemptionMisuse):
            OracleExemption(
                hypothesis=Hypothesis.ACQ0,
                granted_by="user",
                authority="ACQ0 addendum §1",
                rationale="encoding only",
                permits=frozenset({forbidden}),
            )


def test_exemption_requires_attribution():
    with pytest.raises(ExemptionMisuse):
        OracleExemption(
            hypothesis=Hypothesis.ACQ0,
            granted_by="   ",
            authority="ACQ0 addendum §1",
            rationale="encoding only",
            permits=ACQ0_ENCODING_DISCLOSURE,
        )


def test_the_study_exemption_permits_exactly_the_addendum_fields():
    assert ACQ0_ENCODING_EXEMPTION.permits == frozenset(
        {TaskInformation.GOLD_ANSWER, TaskInformation.SEMANTIC_FACTS}
    )
    assert TaskInformation.REFERENCE_ENCODING not in ACQ0_ENCODING_EXEMPTION.permits


# ---------------------------------------------------------------------------
# 2. The guard refuses an exemption presented under a reasoning hypothesis
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("hypothesis", sorted(REASONING_HYPOTHESES))
def test_guard_refuses_an_exemption_under_a_reasoning_hypothesis(hypothesis):
    task = _task()
    with pytest.raises(ExemptionMisuse):
        assert_no_oracle(
            "irrelevant text",
            task.cso,
            where="test",
            hypothesis=hypothesis,
            exemption=ACQ0_ENCODING_EXEMPTION,
        )


def test_guard_is_unchanged_when_no_exemption_is_supplied():
    """The default path must still raise on a leak, and the default is what stages.py uses."""
    from evaluation.acq0.protocols.oracle import OracleLeak

    task = _task()
    poisoned = "PROBLEM\n" + (task.cso.reference_hml or "")
    with pytest.raises(OracleLeak):
        assert_no_oracle(poisoned, task.cso, where="test")


def test_exemption_still_raises_on_a_field_it_does_not_permit():
    """An exemption for the target does not license leaking the reference encoding."""
    from evaluation.acq0.protocols.oracle import OracleLeak

    task = _task()
    poisoned = "ENCODE THIS\n" + (task.cso.reference_hml or "")
    with pytest.raises(OracleLeak):
        assert_no_oracle(
            poisoned,
            task.cso,
            where="test",
            hypothesis=Hypothesis.ACQ0,
            exemption=ACQ0_ENCODING_EXEMPTION,
        )


# ---------------------------------------------------------------------------
# 3. The H1/H2/H3 prompt builders carry no exemption, checked on the source
# ---------------------------------------------------------------------------


def test_stages_module_passes_no_exemption_at_any_call_site():
    source = Path(inspect.getsourcefile(stages_module)).read_text(encoding="utf-8")
    assert "exemption" not in source, (
        "evaluation/acq0/prompts/stages.py builds every H1/H2/H3 prompt. It must call "
        "assert_no_oracle with no exemption argument; the ACQ0 disclosure is applied by "
        "evaluation/acq0/protocols/encoding.py, which is the exemption's only call site."
    )
    assert "OracleExemption" not in source
    assert "Hypothesis" not in source


def test_encoding_module_is_the_only_call_site_of_the_exemption():
    root = Path(__file__).resolve().parents[2]
    hits = sorted(
        p.relative_to(root).as_posix()
        for p in (root / "evaluation").rglob("*.py")
        if "ACQ0_ENCODING_EXEMPTION" in p.read_text(encoding="utf-8")
    )
    assert hits == [
        "evaluation/acq0/protocols/encoding.py",
        "evaluation/acq0/protocols/oracle.py",
    ], f"the exemption acquired a new call site: {hits}"


@pytest.mark.parametrize("builder", ["draft_prompt", "plan_prompt"])
def test_reasoning_stage_builders_are_still_guarded(builder):
    """The unrestricted stages still refuse a leak; the exemption changed nothing here."""
    task = _task()
    prompt = getattr(stages_module, builder)(task, "A_v0_labelled_linear")
    assert (task.cso.reference_hml or "").strip() not in prompt.user


# ---------------------------------------------------------------------------
# The ACQ0 encoding prompt itself
# ---------------------------------------------------------------------------


def test_acq0_prompt_discloses_the_target_and_records_it():
    task = _task()
    base = stages_module.build_stage_prompt(
        task,
        "A_v0_labelled_linear",
        __import__(
            "evaluation.acq0.protocols.core", fromlist=["GenerationProtocol"]
        ).GenerationProtocol.DIRECT_FORMAL,
        __import__(
            "evaluation.acq0.protocols.core", fromlist=["StageKind"]
        ).StageKind.FORMALISE,
        demonstrations=[],
    )
    prompt = acq0_encoding_prompt(base, task)
    assert ACQ0_TARGET_HEADER in prompt.user
    assert ACQ0_ENCODING_INSTRUCTION in prompt.user
    # The reference encoding is NOT disclosed: producing it is the task.
    for line in (task.cso.reference_hml or "").splitlines():
        if len(line.strip()) >= 12 and not line.strip().startswith("#"):
            assert line.strip() not in prompt.user
    record = prompt.to_dict()
    assert record["consequence"] == ACQ0_ANSWER_FACET_VOID
    assert record["disclosed_fields"], "a disclosure that disclosed nothing is not one"


def test_render_disclosure_refuses_a_task_with_no_structured_mathematics():
    class _Facts:
        entities = {}
        declaration_kinds = {}
        laws = {}
        law_families = {}
        conditioning = None
        constraints = ()
        quantifier_order = ()
        dependencies = None
        objective = None
        dimensions = {}

    class _Answer:
        value = None

    class _Cso:
        id = "empty_000"
        assumptions = ()
        semantics = _Facts()
        answer = _Answer()

    with pytest.raises(TaskQuarantined):
        render_disclosure(_Cso())


def test_calibration_tasks_are_quarantine_clean():
    tasks = calibration_tasks()
    for t in tasks:
        assert quarantine_report(t) == ()
    assert_mathematics_fixed_independently(tasks)


def test_calibration_tasks_are_disjoint_from_the_frozen_curriculum():
    """A task in its own demonstration curriculum would measure copying."""
    chosen = {t.id for t in calibration_tasks()}
    assert not (chosen & set(FROZEN_CURRICULUM_IDS))


# ---------------------------------------------------------------------------
# The phase call ledger and its authorisation
# ---------------------------------------------------------------------------


def test_call_ledger_is_derived_not_asserted():
    ledger = derive_call_ledger()
    assert ledger.conditions == 16
    assert ledger.direct_generation == 8
    assert ledger.draft_generation == 8
    assert ledger.formalisation == 16
    assert ledger.max_repair == 16
    assert ledger.hard_maximum_total == 40


def test_phase_authorisation_equals_the_derived_maximum_and_needs_green():
    from evaluation.acq0.protocols.runner import ConformanceNotGreen

    ledger = derive_call_ledger()
    auth = phase_authorisation(
        ledger, authorised_by="Lead", conformance_state="green"
    )
    assert auth.call_budget == ledger.hard_maximum_total == 40
    assert "21687cf" in auth.citation and "hml-m2-context-budget" in auth.citation
    with pytest.raises(ConformanceNotGreen):
        phase_authorisation(ledger, authorised_by="Lead", conformance_state="red")
