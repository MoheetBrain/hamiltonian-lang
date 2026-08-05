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


# ---------------------------------------------------------------------------
# A parse rate must count parses, not compiles
# ---------------------------------------------------------------------------

#: Encodings whose only defect is *after* the parser. Every one fails
#: ``CompileResult.ok()`` and every one parses. A scorer that reads ``ok()`` as the
#: parse verdict reports all four as syntax failures, understating ACQ0's first-attempt
#: parse rate and blaming the candidate surface for the compiler's type checking.
_POST_PARSE_DEFECTS = {
    "HML-T426 wrong arity": (
        "module M\n"
        "param v : Vector[Real, 3]\n"
        "def s : Real := sum(v, v)\n",
        "HML-T426",
        "RESOLVED_TYPE_FAILED",
    ),
    "HML-T415 wrong role label": (
        "module M\n"
        "param mu : Real\n"
        "param v : PositiveReal\n"
        "var X : RandomVariable[Real]\n"
        "law X ~ Normal(location := mu, variance := v)\n",
        "HML-T415",
        "RESOLVED_TYPE_FAILED",
    ),
    "HML-T403 declared-type mismatch": (
        "module M\n"
        "param p : Probability = 0.5\n"
        "def d : PositiveReal := p\n",
        "HML-T403",
        "RESOLVED_TYPE_FAILED",
    ),
    "unknown identifier": (
        "module M\ndef d : Real := nosuchthing\n",
        "HML-N301",
        "PARSE_PASSED_RESOLUTION_FAILED",
    ),
}

_SYNTAX_DEFECT = "module M\nconst a : Real = ((\n"


def _trial_with(encoding: str, **kw):
    from dataclasses import replace

    base = TrialInput(
        trial_id="stage", run_id="r", task_id=T0.id, condition=A_V0_LINEAR,
        curriculum_size=0,
        content=f"```hml\n{encoding}```\n\n<ANSWER>{T0.cso.answer.value}</ANSWER>",
        completion_tokens=40, finish_reason="stop",
    )
    return replace(base, **kw)


@pytest.mark.parametrize("case", sorted(_POST_PARSE_DEFECTS), ids=sorted(_POST_PARSE_DEFECTS))
def test_a_post_parse_defect_is_not_scored_as_a_parse_failure(case):
    encoding, expected_code, expected_terminal = _POST_PARSE_DEFECTS[case]
    from hamiltonian_lang import compile_source

    # The premise, restated at the scorer boundary so this test stands alone.
    assert not compile_source(encoding).ok(), f"{case} unexpectedly compiles clean"

    s = score_trial(_trial_with(encoding), T0, ADAPTER)
    assert s.first_attempt_parse is True, (case, s.terminal_outcome, s.diagnostics)
    assert s.first_attempt_compiled is False, case
    assert s.terminal_outcome == expected_terminal, (case, s.terminal_outcome)
    assert any(expected_code in d for d in s.diagnostics), (case, s.diagnostics)
    # It did not recover the reference object either -- but for a reason that is not
    # "the model could not write the syntax".
    assert s.exact_canonical_match is False, case


def test_a_genuine_syntax_defect_is_still_a_parse_failure():
    """The other half. If this ever passes, the fix has gone too far and the parse rate
    has become a constant."""
    s = score_trial(_trial_with(_SYNTAX_DEFECT), T0, ADAPTER)
    assert s.first_attempt_parse is False
    assert s.first_attempt_compiled is False
    assert s.terminal_outcome == "PARSE_FAILED"
    assert s.failure_category == "syntax_failure"


def test_the_parse_rate_and_the_compile_rate_genuinely_differ():
    """A differential test, so the two fields cannot both be aliases of one boolean."""
    rows = [
        score_trial(_trial_with(enc), T0, ADAPTER)
        for enc, _, _ in _POST_PARSE_DEFECTS.values()
    ]
    rows.append(score_trial(_trial_with(_SYNTAX_DEFECT), T0, ADAPTER))

    parsed = sum(1 for r in rows if r.first_attempt_parse is True)
    compiled = sum(1 for r in rows if r.first_attempt_compiled is True)
    assert parsed == len(_POST_PARSE_DEFECTS)
    assert compiled == 0
    assert parsed != compiled, (
        "first_attempt_parse and first_attempt_compiled reported the same number on a "
        "set constructed so that they must differ; the conflation has returned"
    )


def test_a_repair_that_fixes_syntax_and_leaves_a_type_error_counts_as_a_parse():
    encoding, _, _ = _POST_PARSE_DEFECTS["HML-T426 wrong arity"]
    s = score_trial(
        _trial_with(
            _SYNTAX_DEFECT,
            repair_attempted=True,
            repair_content=f"```hml\n{encoding}```\n<ANSWER>0</ANSWER>",
            repair_completion_tokens=40,
        ),
        T0,
        ADAPTER,
    )
    assert s.first_attempt_parse is False
    assert s.repaired_parse is True, s.diagnostics
    assert s.repair_terminal_outcome == "RESOLVED_TYPE_FAILED"
    # Parsing is not succeeding. The trial still failed to recover the object.
    assert s.exact_canonical_match is False


def test_a_front_end_reporting_no_stage_record_is_not_measured_rather_than_false():
    """A front end that has not been updated has not observed a parse failure. Falling
    back to ``ok`` would silently reinstate the defect for that candidate."""
    from evaluation.syntax_gate.candidates import ParseOutcome

    class StagelessAdapter:
        candidate_id = A_V0_LINEAR
        LIVE = False

        def render(self, hml_l1: str) -> str:
            return hml_l1

        def parse(self, encoding: str) -> ParseOutcome:
            # ok=False with no stages: the old shape.
            return ParseOutcome(ok=False, hml_l1=None, diagnostics=["HML-T426"],
                                surface=encoding)

    s = score_trial(_trial_with(_SYNTAX_DEFECT), T0, StagelessAdapter())
    assert isinstance(s.first_attempt_parse, NotMeasured)
    assert "per-stage record" in s.first_attempt_parse.reason
    assert isinstance(s.exact_canonical_match, NotMeasured)


def test_a_reference_encoding_recovers_the_exact_canonical_object():
    reply = f"```hml\n{T0.cso.reference_hml}```\n\n<ANSWER>{T0.cso.answer.value}</ANSWER>"
    trial = TrialInput(
        trial_id="x", run_id="r", task_id=T0.id, condition=A_V0_LINEAR,
        curriculum_size=0, content=reply, completion_tokens=10, finish_reason="stop",
    )
    s = score_trial(trial, T0, ADAPTER)
    assert s.first_attempt_parse is True
    assert s.first_attempt_compiled is True
    assert s.exact_canonical_match is True
    assert s.terminal_outcome == "SEMANTICALLY_PRESERVED"


# ---------------------------------------------------------------------------
# The ACQ0 metric definitions
# ---------------------------------------------------------------------------


def test_acq0_metrics_count_parses_and_state_their_own_definitions():
    from evaluation.syntax_gate.stats import acq0_metrics

    rows = [
        score_trial(_trial_with(enc), T0, ADAPTER)
        for enc, _, _ in _POST_PARSE_DEFECTS.values()
    ]
    rows.append(score_trial(_trial_with(_SYNTAX_DEFECT), T0, ADAPTER))

    m = acq0_metrics(rows, A_V0_LINEAR)
    first = m["first_attempt_parse_rate"]
    assert first["numerator"] == len(_POST_PARSE_DEFECTS)
    assert first["denominator"] == len(rows)
    assert "parse_status = PASS" in first["definition"]

    # Only the genuine syntax failure was ever eligible for a repair.
    assert m["repaired_parse_rate"]["repair_eligible_total"] == 1

    # None of these recovered the reference object.
    assert m["semantic_preservation_rate"]["numerator"] == 0
    assert m["semantic_preservation_rate"]["denominator"] == len(rows)

    # The gate quantity is reported under a different name from the repair-loop rate,
    # so a report cannot quote one as the other.
    assert (
        m["parse_rate_after_at_most_one_repair"]["definition"]
        != m["repaired_parse_rate"]["definition"]
    )
    assert m["terminal_outcomes"]["PARSE_FAILED"] == 1
    assert m["terminal_outcomes"]["RESOLVED_TYPE_FAILED"] == 3


def test_the_repaired_parse_rate_excludes_trials_that_never_needed_a_repair():
    from evaluation.syntax_gate.stats import acq0_metrics

    good = f"```hml\n{T0.cso.reference_hml}```\n<ANSWER>{T0.cso.answer.value}</ANSWER>"
    rows = [
        score_trial(
            TrialInput(
                trial_id="ok", run_id="r", task_id=T0.id, condition=A_V0_LINEAR,
                curriculum_size=0, content=good, completion_tokens=10,
                finish_reason="stop",
            ),
            T0, ADAPTER,
        ),
        score_trial(_trial_with(_SYNTAX_DEFECT), T0, ADAPTER),
    ]
    m = acq0_metrics(rows, A_V0_LINEAR)
    assert m["first_attempt_parse_rate"]["numerator"] == 1
    assert m["first_attempt_parse_rate"]["denominator"] == 2
    # One row parsed first time, so exactly one row was repair-eligible.
    assert m["repaired_parse_rate"]["repair_eligible_total"] == 1
    assert m["repaired_parse_rate"]["denominator"] == 1
    # The gate quantity counts both rows.
    assert m["parse_rate_after_at_most_one_repair"]["denominator"] == 2
