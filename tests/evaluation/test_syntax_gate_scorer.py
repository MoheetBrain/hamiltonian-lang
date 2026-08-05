"""The scorer, and the mutation suite that proves each facet can pass and fail.

The pilot's scorer returned 0.0 when nothing was checkable and silently zeroed 25
problems. Nothing caught it because nothing had ever exercised the branch. Every facet
in ``scorer.FACETS`` therefore has at least one mutation that makes it report its healthy
value and at least one that makes it report its unhealthy value, and this file asserts
both — plus the specific distinction the pilot got wrong.
"""

from __future__ import annotations

import pytest
from evaluation.syntax_gate.candidates import (
    A_V0_LINEAR,
    C_SEXPR,
    SE_CONTROL,
    V0LinearAdapter,
)
from evaluation.syntax_gate.mutations import MUTATIONS, covered_facets, run_mutation
from evaluation.syntax_gate.scorer import (
    FACETS,
    FAILURE_CATEGORIES,
    TrialInput,
    score_many,
    score_trial,
)
from evaluation.syntax_gate.tasks import GateTask, build_track_a
from evaluation.v1.score_v1 import NotMeasured

TASKS = build_track_a()
T0 = TASKS[0]
ADAPTER = V0LinearAdapter()


@pytest.mark.parametrize("m", MUTATIONS, ids=[f"{m.facet}:{m.kind}:{m.name}" for m in MUTATIONS])
def test_mutation(m):
    ok, detail = run_mutation(m)
    assert ok, detail


def test_every_facet_has_a_mutation():
    assert covered_facets() == set(FACETS)


def test_every_facet_has_both_a_passing_and_a_failing_mutation():
    kinds = {}
    for m in MUTATIONS:
        kinds.setdefault(m.facet, set()).add(m.kind)
    missing = {f: sorted(k) for f, k in kinds.items() if k != {"pass", "fail"}}
    assert not missing, f"facets without both a pass and a fail case: {missing}"


def test_the_pilot_defect_cannot_recur():
    """Nothing-to-check must be NOT MEASURED; a real failure must be a measured 0.0.

    These are the two halves of the HML-EVAL-001 bug. Confusing them in either direction
    is a scoring error, and both directions are asserted here.
    """
    from dataclasses import replace

    reply = f"```hml\n{T0.cso.reference_hml}```\n\n<ANSWER>{T0.cso.answer.value}</ANSWER>"
    trial = TrialInput(
        trial_id="x", run_id="r", task_id=T0.id, condition=A_V0_LINEAR,
        curriculum_size=0, content=reply, completion_tokens=10, finish_reason="stop",
    )

    no_facets = GateTask(
        cso=T0.cso, track=T0.track, features=T0.features, scored_facets=frozenset()
    )
    s = score_trial(trial, no_facets, ADAPTER)
    assert isinstance(s.semantic_preservation, NotMeasured)
    assert s.semantic_preservation.to_dict()["NOT MEASURED"] is True

    empty = replace(trial, content="<ANSWER>0</ANSWER>")
    s2 = score_trial(empty, T0, ADAPTER)
    assert s2.semantic_preservation == 0.0
    assert not isinstance(s2.semantic_preservation, NotMeasured)


def test_empty_visible_answer_is_a_model_failure_not_a_retry():
    trial = TrialInput(
        trial_id="x", run_id="r", task_id=T0.id, condition=A_V0_LINEAR,
        curriculum_size=0, content="", reasoning="r" * 9000,
        completion_tokens=2400, finish_reason="length",
    )
    s = score_trial(trial, T0, ADAPTER)
    assert s.failure_category == "empty_visible_answer"
    assert s.first_attempt_parse is False
    assert s.repaired_parse is False
    assert s.answer_correct is False
    assert s.empty_or_truncated is True
    # It is a *failure*, not an absent measurement.
    assert not isinstance(s.first_attempt_parse, NotMeasured)


def test_transport_failure_is_excluded_not_counted_as_a_failure():
    trial = TrialInput(
        trial_id="x", run_id="r", task_id=T0.id, condition=A_V0_LINEAR,
        curriculum_size=0, content="", error="URLError: connection refused",
    )
    s = score_trial(trial, T0, ADAPTER)
    assert s.failure_category == "transport_failure"
    for f in ("first_attempt_parse", "repaired_parse", "semantic_preservation",
              "answer_correct"):
        assert isinstance(getattr(s, f), NotMeasured), f


def test_an_absent_front_end_is_never_reported_as_zero_parse():
    trial = TrialInput(
        trial_id="x", run_id="r", task_id=T0.id, condition=C_SEXPR,
        curriculum_size=0, content="```sexpr\n(module X)\n```\n<ANSWER>1</ANSWER>",
    )
    s = score_trial(trial, T0, None)
    assert s.failure_category == "front_end_unavailable"
    assert isinstance(s.first_attempt_parse, NotMeasured)
    assert "syntax_acquisition" in s.first_attempt_parse.reason


def test_the_control_arm_is_not_given_a_parse_rate():
    trial = TrialInput(
        trial_id="x", run_id="r", task_id=T0.id, condition=SE_CONTROL,
        curriculum_size=0, content=f"Working.\n\n<ANSWER>{T0.cso.answer.value}</ANSWER>",
        completion_tokens=200,
    )
    s = score_trial(trial, T0, None)
    assert s.failure_category == "control_arm_no_encoding"
    assert isinstance(s.first_attempt_parse, NotMeasured)
    assert s.answer_correct is True
    assert s.completion_tokens_reasoning_inclusive == 200


def test_every_emitted_failure_category_is_declared():
    seen = set()
    for m in MUTATIONS:
        task = m.task
        if m.trial.task_id == "synthetic_no_facets":
            continue
        seen.add(score_trial(m.trial, task, m.adapter).failure_category)
    assert seen <= set(FAILURE_CATEGORIES)
    # The suite must exercise most of the taxonomy, not just the happy path.
    assert len(seen) >= 8, sorted(seen)


# ---------------------------------------------------------------------------
# The four surfaces, through the Phase F3 front ends
# ---------------------------------------------------------------------------

_ADAPTERS = __import__(
    "evaluation.syntax_gate.candidates", fromlist=["resolve_adapters"]
).resolve_adapters()
_AVAILABLE = [c for c in _ADAPTERS if _ADAPTERS[c] is not None]


def test_candidate_a_always_has_a_front_end():
    """A's surface is HML-L1 and the compiler implements it, so A is measurable with or
    without the Phase F3 package. B, C and D are not, and must report NOT MEASURED
    rather than a fabricated parse rate when their front ends are absent."""
    assert _ADAPTERS[A_V0_LINEAR] is not None


def _two_per_domain():
    """Two tasks from each of the eight supported domains, in a fixed order.

    ``TASKS[:8]`` would be eight items from one domain and would tell us nothing about
    the other seven, which is where a surface most plausibly loses meaning.
    """
    from evaluation.syntax_gate.tasks import TRACK_A_DOMAINS

    out = []
    for d in TRACK_A_DOMAINS:
        out += [t for t in TASKS if t.domain == d][:2]
    return out


_SPREAD = _two_per_domain()


@pytest.mark.parametrize("condition", _AVAILABLE)
@pytest.mark.parametrize("task", _SPREAD, ids=[t.id for t in _SPREAD])
def test_a_reference_encoding_survives_a_render_parse_score_round_trip(condition, task):
    """The end-to-end path the tournament will use: render the reference object into a
    candidate surface, feed it back as if a model had written it, and score it. A
    reference object must score 1.0 in every surface, or the surface is losing meaning
    and any later parse rate measures the front end rather than the model."""
    adapter = _ADAPTERS[condition]
    surface = adapter.render(task.cso.reference_hml)
    from evaluation.syntax_gate.candidates import CANDIDATES

    tag = CANDIDATES[condition].fence_tags[0]
    trial = TrialInput(
        trial_id="rt", run_id="r", task_id=task.id, condition=condition,
        curriculum_size=0,
        content=f"```{tag}\n{surface}\n```\n\n<ANSWER>{task.cso.answer.value}</ANSWER>",
        completion_tokens=50, finish_reason="stop",
    )
    s = score_trial(trial, task, adapter)
    assert s.first_attempt_parse is True, (condition, s.diagnostics)
    assert s.failure_category == "ok", (condition, s.diagnostics, s.notes)
    if task.scored_facets:
        assert s.semantic_preservation == 1.0, (condition, s.notes)


def test_score_many_is_order_preserving_and_parallel_safe():
    reply = f"```hml\n{T0.cso.reference_hml}```\n\n<ANSWER>{T0.cso.answer.value}</ANSWER>"
    trials = [
        TrialInput(
            trial_id=f"t{i}", run_id="r", task_id=t.id, condition=A_V0_LINEAR,
            curriculum_size=0,
            content=(reply if t.id == T0.id else
                     f"```hml\n{t.cso.reference_hml}```\n\n"
                     f"<ANSWER>{t.cso.answer.value}</ANSWER>"),
            completion_tokens=10, finish_reason="stop",
        )
        for i, t in enumerate(TASKS[:24])
    ]
    tasks = {t.id: t for t in TASKS}
    adapters = {A_V0_LINEAR: ADAPTER}
    serial = score_many(trials, tasks, adapters, workers=1)
    parallel = score_many(trials, tasks, adapters, workers=18)
    assert [s.trial_id for s in parallel] == [s.trial_id for s in serial]
    assert [s.to_dict() for s in parallel] == [s.to_dict() for s in serial]
    assert all(s.first_attempt_parse for s in serial)
