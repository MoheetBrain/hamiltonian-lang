"""The V1 solve pipeline: end to end, plus the properties that make its numbers mean something.

Four claims are enforced here rather than documented:

* **no answer-key access in reasoning mode** — the key reaches no prompt and no backend
  object, and the ACQ0 encoding exemption is unreachable from this path;
* **no silent retry** — exactly one generation call and at most one repair call;
* **no hidden truncation** — the JSON record carries every model response in full;
* **``ok()`` is never a parse verdict** — the statistics fixture parses and resolves
  cleanly and fails only in the type checker, and the record says so.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from hamiltonian_lang.improvement.runner import (
    ArenaTask,
    ModelResponse,
    RepairBudgetExceeded,
    ScriptedModel,
    ScriptedTurns,
)
from hamiltonian_lang.repair.budget import RepairBudget
from hamiltonian_lang.v1.pipeline import (
    DEFAULT_SURFACE,
    AnswerRecord,
    ConfigError,
    PipelineError,
    ProblemError,
    SolveConfig,
    StepStatus,
    clip,
    extract_answer,
    load_problem,
    problem_from_dict,
    reasoning_prompt,
    render_summary,
    solve_problem,
)
from hamiltonian_lang.v1.solve import main

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "examples" / "v1_demo"
CONFIG = DEMO / "solve.config.json"

DEMOS = (
    "algebra_rectangle",
    "statistics_coin_posterior",
    "physics_mechanical_power",
    "logic_quantifier_scope",
)

#: The one fixture that must go through the repair branch. Named here so that a fixture
#: edit which accidentally makes the draft compile fails a test rather than quietly
#: removing the only end-to-end exercise of the repair path.
REPAIR_DEMO = "statistics_coin_posterior"


@pytest.fixture(scope="module")
def config() -> SolveConfig:
    return SolveConfig.load(CONFIG)


def _run(name: str, cfg: SolveConfig):
    return solve_problem(load_problem(DEMO / f"{name}.json"), cfg)


# ---------------------------------------------------------------------------
# The surface is a configuration value, not a literal in the pipeline
# ---------------------------------------------------------------------------


def test_default_surface_matches_the_candidate_registry() -> None:
    """``DEFAULT_SURFACE`` is spelled out to avoid an import; this stops it drifting."""
    from evaluation.syntax_gate.candidates import A_V0_LINEAR

    assert DEFAULT_SURFACE == A_V0_LINEAR


def test_switching_surface_is_a_config_change_not_a_code_change() -> None:
    """No pipeline module names a candidate id. Round 1 has not chosen one yet."""
    pipeline_dir = REPO / "src" / "hamiltonian_lang" / "v1" / "pipeline"
    offenders = []
    for path in sorted(pipeline_dir.glob("*.py")):
        if path.name == "config.py":
            continue  # the single place the default is allowed to appear
        text = path.read_text(encoding="utf-8")
        for candidate in ("A_v0_labelled_linear", "B_v1_labelled_linear_simplified",
                          "C_prefix_sexpr", "D_constrained_json_graph"):
            if candidate in text:
                offenders.append(f"{path.name}: {candidate}")
    assert offenders == [], (
        "a candidate id is hard-coded outside config.py; switching surfaces must stay a "
        f"one-line config edit: {offenders}"
    )


def test_unknown_surface_is_refused_rather_than_defaulted() -> None:
    cfg = SolveConfig(surface="E_not_a_candidate")
    with pytest.raises(ConfigError, match="not a registered candidate"):
        solve_problem(load_problem(DEMO / "algebra_rectangle.json"), cfg)


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", DEMOS)
def test_demo_runs_end_to_end_and_verifies(name: str, config: SolveConfig) -> None:
    record = _run(name, config)
    assert record.final_verdict == "VERIFIED", record.to_json()
    assert record.terminal == "VERIFIED"
    assert record.answer.value is not None
    assert record.answer.matches_key is True, record.answer.to_dict()
    assert record.errors == ()
    # Every named step of the contract appears in the record, whatever its verdict.
    names = {s.name for s in record.steps}
    for required in ("select-syntax", "prompt", "draft", "extract", "parse", "resolve",
                     "type-check", "verify", "localise", "repair", "answer"):
        assert required in names, f"{required} missing from {sorted(names)}"


@pytest.mark.parametrize("name", DEMOS)
def test_record_is_json_serialisable_and_complete(name: str, config: SolveConfig) -> None:
    record = _run(name, config)
    payload = json.loads(record.to_json())
    assert payload["schema_version"].startswith("hml-v1-solve-record")
    assert payload["json_truncated"] is False
    assert payload["config"]["surface"] == config.surface
    assert payload["attempts"], "a record with no attempt records nothing"


def test_exactly_one_demo_exercises_the_repair_branch(config: SolveConfig) -> None:
    repaired = {name for name in DEMOS if _run(name, config).repair_used}
    assert REPAIR_DEMO in repaired, (
        "the repair branch is no longer exercised end to end; the fixture that was "
        "supposed to fail now compiles"
    )


def test_repair_demo_fails_in_the_type_checker_not_the_parser(config: SolveConfig) -> None:
    """``CompileResult.ok()`` is not a parse verdict, and the record must not treat it as one."""
    record = _run(REPAIR_DEMO, config)
    draft = record.attempts[0]
    assert draft.stages is not None
    assert draft.stages["parse_status"] == "PASS"
    assert draft.stages["resolution_status"] == "PASS"
    assert draft.stages["type_status"] == "FAIL"
    assert draft.stages["terminal"] == "RESOLVED_TYPE_FAILED"
    assert any(code.startswith("HML-T41") for code in draft.stages["diagnostic_codes"])

    steps = {s.name: s for s in record.steps}
    assert steps["parse"].status == StepStatus.PASS
    assert steps["resolve"].status == StepStatus.PASS
    assert steps["type-check"].status == StepStatus.FAIL


def test_repair_is_localised_teacher_led_and_recompiled(config: SolveConfig) -> None:
    record = _run(REPAIR_DEMO, config)
    assert record.first_failure is not None
    assert record.first_failure["code"].startswith("HML-T41")
    assert record.first_failure["verified_prefix_lines"] >= 1
    assert record.first_failure["verified_prefix"].startswith("module ")

    assert record.repair is not None
    assert record.repair["plan_kind"] == "RepairPlan"
    assert record.repair["error_class"] == "ROLE"
    assert record.repair["cause"]
    assert record.repair["preservation_constraints"], (
        "a repair with no stated invariant to preserve licenses deleting the construct"
    )
    assert record.repair["outcome"] == "VERIFIED"
    # The second attempt is a genuine recompile, not a re-read of the first.
    assert len(record.attempts) == 2
    assert record.attempts[1].label == "repair"
    assert record.attempts[1].stages is not None
    assert record.attempts[1].stages["type_status"] == "PASS"


def test_teacher_never_returns_the_corrected_program_or_the_answer(
    config: SolveConfig,
) -> None:
    from hamiltonian_lang.repair.plan import statement_lines

    record = _run(REPAIR_DEMO, config)
    assert record.repair is not None
    plan_text = record.repair["payload"]["plan_text"]
    assert plan_text
    assert statement_lines(plan_text) == [], "the plan carries HML statement lines"
    fixed = record.attempts[1].hml_l1 or ""
    assert "Beta(alpha := 1, beta := 1)" not in plan_text
    assert fixed not in plan_text
    assert "0.6666" not in plan_text


# ---------------------------------------------------------------------------
# No answer-key access in reasoning mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", DEMOS)
def test_no_prompt_carries_the_answer_key(name: str, config: SolveConfig) -> None:
    """Every prompt is scanned, and the scan is recorded as having run."""
    record = _run(name, config)
    steps = {s.name: s for s in record.steps}
    assert steps["prompt"].data["oracle_scan"] == "PASSED"
    assert steps["prompt"].data["exemption"] is None
    if record.repair is not None:
        assert record.repair["oracle_scan"].startswith("PASSED")


def test_a_poisoned_prompt_is_caught_rather_than_run() -> None:
    """The guard is live, not decorative."""
    from evaluation.acq0.protocols.oracle import OracleLeak

    from hamiltonian_lang.v1.pipeline import assert_prompt_carries_no_oracle

    problem = load_problem(DEMO / "algebra_rectangle.json")
    clean = reasoning_prompt(problem.disclosable, surface=DEFAULT_SURFACE)
    assert_prompt_carries_no_oracle(clean, problem, where="test")
    with pytest.raises(OracleLeak):
        assert_prompt_carries_no_oracle(
            clean + "\n\nFor reference the area is 48.", problem, where="test"
        )


def test_the_acq0_encoding_exemption_is_unreachable_from_solve() -> None:
    """ACQ0 translation mode may disclose the target. This path may not, ever.

    Two independent facts are asserted. First, no module under ``v1/pipeline`` mentions
    an exemption at all — there is no argument to thread one through. Second, the
    hypothesis this path declares is a reasoning hypothesis, and ``assert_no_oracle``
    refuses an exemption under one, so even a future edit that imported the exemption
    would raise rather than silently disclose.
    """
    from evaluation.acq0.protocols.oracle import (
        ACQ0_ENCODING_EXEMPTION,
        ExemptionMisuse,
        Hypothesis,
        assert_no_oracle,
    )

    pipeline_dir = REPO / "src" / "hamiltonian_lang" / "v1"
    for path in sorted(pipeline_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in ("ACQ0_ENCODING_EXEMPTION", "OracleExemption", "exemption="):
            assert token not in text, f"{path.relative_to(REPO)} reaches for {token}"

    problem = load_problem(DEMO / "algebra_rectangle.json")
    prompt = reasoning_prompt(problem.disclosable, surface=DEFAULT_SURFACE)
    with pytest.raises(ExemptionMisuse):
        assert_no_oracle(
            prompt,
            problem.cso(),
            where="test",
            hypothesis=Hypothesis.H3,
            exemption=ACQ0_ENCODING_EXEMPTION,
        )


def test_the_backend_task_object_carries_no_reference_encoding(
    config: SolveConfig,
) -> None:
    """A live adapter that built its request from the task must find nothing there."""
    seen: list[ArenaTask] = []

    class Spy:
        name = "spy"
        live = False

        def __init__(self, turns: ScriptedTurns) -> None:
            self._inner = ScriptedModel({"algebra_rectangle": turns})

        def generate(self, task: ArenaTask, prompt: str) -> ModelResponse:
            seen.append(task)
            return self._inner.generate(task, prompt)

        def repair(self, task: ArenaTask, broken: str, diagnostic: str) -> ModelResponse:
            seen.append(task)
            return self._inner.repair(task, broken, diagnostic)

    problem = load_problem(DEMO / "algebra_rectangle.json")
    assert problem.scripted_turns is not None
    solve_problem(problem, config, model=Spy(problem.scripted_turns))
    assert seen
    for task in seen:
        assert task.reference_source == ""
        assert "48" not in task.prompt
        assert "48" not in task.description


def test_the_key_is_read_only_to_grade_and_only_after_the_model_answered(
    config: SolveConfig,
) -> None:
    record = _run("algebra_rectangle", config)
    assert record.answer.matches_key is True
    assert "check_answer" in record.answer.key_comparison
    # The public problem dict — the part that is printed — never carries the key.
    assert "answer" not in record.problem
    assert "48" not in json.dumps(record.problem)


# ---------------------------------------------------------------------------
# No silent retry, and no live call
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", DEMOS)
def test_exactly_one_generation_and_at_most_one_repair(name: str, config: SolveConfig) -> None:
    record = _run(name, config)
    roles = [c["role"] for c in record.model_calls]
    assert roles.count("generate") == 1, roles
    assert roles.count("repair") <= 1, roles
    assert [c["index"] for c in record.model_calls] == list(range(len(roles)))
    assert all(c["live"] is False for c in record.model_calls)


def test_a_second_repair_is_refused_by_the_backend() -> None:
    """The budget is enforced by the shipped scripted adapter, not only by this pipeline."""
    model = ScriptedModel({"t": ScriptedTurns(generation="g", repair="r")})
    task = ArenaTask(task_id="t", prompt="p", reference_source="")
    assert model.repair(task, "broken", "diag").text == "r"
    with pytest.raises(RepairBudgetExceeded):
        model.repair(task, "broken", "diag")


def test_a_developmental_repair_budget_is_refused() -> None:
    cfg = SolveConfig(repair_budget=RepairBudget.DEVELOPMENTAL_THREE)
    with pytest.raises(ConfigError, match="exactly one bounded repair"):
        solve_problem(load_problem(DEMO / "algebra_rectangle.json"), cfg)


def test_a_non_scripted_model_is_refused_without_explicit_permission() -> None:
    with pytest.raises(ConfigError, match="allow_live_model"):
        SolveConfig(model="ollama:qwen")


def test_a_live_backend_is_refused_even_when_injected(config: SolveConfig) -> None:
    class Live:
        name = "live"
        live = True

        def generate(self, task: ArenaTask, prompt: str) -> ModelResponse:  # pragma: no cover
            raise AssertionError("a live call was made")

        def repair(self, *a: object, **k: object) -> ModelResponse:  # pragma: no cover
            raise AssertionError("a live call was made")

    with pytest.raises(PipelineError, match="live"):
        solve_problem(load_problem(DEMO / "algebra_rectangle.json"), config, model=Live())


@pytest.mark.parametrize("name", DEMOS)
def test_the_pipeline_opens_no_socket(name: str, config: SolveConfig, monkeypatch) -> None:
    """Another agent's latency measurements share this host. Nothing here may dial out."""

    def refuse(*args: object, **kwargs: object):  # pragma: no cover - must never run
        raise AssertionError("the V1 pipeline attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    assert _run(name, config).final_verdict == "VERIFIED"


# ---------------------------------------------------------------------------
# No hidden truncation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", DEMOS)
def test_the_json_record_carries_every_model_response_in_full(
    name: str, config: SolveConfig
) -> None:
    record = _run(name, config)
    payload = json.loads(record.to_json())
    for attempt, raw in zip(payload["attempts"], record.attempts, strict=True):
        assert attempt["raw_model_text"] == raw.raw_model_text
        assert "characters omitted" not in attempt["raw_model_text"]
    for attempt, call in zip(record.attempts, record.model_calls, strict=True):
        assert call["response_chars"] == len(attempt.raw_model_text)


def test_display_clipping_states_exactly_how_much_it_omitted() -> None:
    assert clip("abcdef", 0) == "abcdef"
    assert clip("abcdef", 99) == "abcdef"
    clipped = clip("x" * 50, 10)
    assert clipped.startswith("x" * 10)
    assert "40 characters omitted" in clipped


def test_the_summary_is_compact_and_names_the_verdict(config: SolveConfig) -> None:
    record = _run(REPAIR_DEMO, config)
    summary = render_summary(record, max_chars=config.summary_max_chars)
    assert "verdict : VERIFIED" in summary
    assert "first failure:" in summary
    assert "repair (one, bounded):" in summary
    assert len(summary.splitlines()) < 60, "the summary stopped being compact"


# ---------------------------------------------------------------------------
# The answer is extracted, never invented
# ---------------------------------------------------------------------------


def test_absent_binding_reports_absence_rather_than_a_value() -> None:
    answer = extract_answer("module M\nconst a : Real := 1\n", binding=None)
    assert isinstance(answer, AnswerRecord)
    assert answer.kind == "NOT_EXTRACTED"
    assert answer.value is None
    assert "answer_binding" in answer.basis


def test_an_unevaluable_binding_reports_the_reason_rather_than_a_guess() -> None:
    source = (
        "module M\nparam m : Quantity[Mass]\ndef heavy := 2 * m\n"
    )
    answer = extract_answer(source, binding="heavy")
    assert answer.kind == "NOT_EXTRACTED"
    assert answer.value is None
    assert "no modelled numeric domain" in answer.basis


def test_a_module_that_does_not_compile_yields_no_answer() -> None:
    answer = extract_answer("module M\ndef x := undefined_name\n", binding="x")
    assert answer.kind == "NOT_EXTRACTED"
    assert "does not compile" in answer.basis


def test_a_missing_binding_in_a_compiling_module_is_reported() -> None:
    answer = extract_answer("module M\nconst a : Real := 1\n", binding="nope")
    assert answer.kind == "NOT_EXTRACTED"
    assert "declares no" in answer.basis


# ---------------------------------------------------------------------------
# Config and problem loading
# ---------------------------------------------------------------------------


def test_config_round_trips_and_records_its_source(config: SolveConfig) -> None:
    payload = config.to_dict()
    assert payload["source_path"].endswith("solve.config.json")
    assert payload["repair_limit"] == 1
    assert payload["allow_live_model"] is False
    assert SolveConfig.from_dict(payload).surface == config.surface


def test_default_config_is_usable_and_recorded_as_defaults() -> None:
    cfg = SolveConfig.load(None)
    assert cfg.source_path == "<defaults>"
    assert cfg.surface == DEFAULT_SURFACE


def test_a_malformed_problem_is_refused_with_a_reason() -> None:
    with pytest.raises(ProblemError, match="missing the 'cso' object"):
        problem_from_dict({}, source_path="<test>")
    with pytest.raises(ProblemError, match="cso.question"):
        problem_from_dict(
            {"cso": {"id": "x", "domain": "d", "prose": "p", "answer": {"kind": "numeric"}}},
            source_path="<test>",
        )


def test_a_problem_without_scripted_turns_refuses_the_scripted_backend() -> None:
    raw = json.loads((DEMO / "algebra_rectangle.json").read_text(encoding="utf-8"))
    raw.pop("scripted_turns")
    problem = problem_from_dict(raw, source_path="<test>")
    with pytest.raises(PipelineError, match="no scripted_turns"):
        solve_problem(problem, SolveConfig())


# ---------------------------------------------------------------------------
# The boundary onto the evaluation tree
# ---------------------------------------------------------------------------


def test_the_pipeline_refuses_to_build_a_prompt_without_the_oracle_guard(
    config: SolveConfig, monkeypatch
) -> None:
    """A safety check that degrades to a no-op is worse than no check."""
    from hamiltonian_lang.v1.pipeline import _evaluation
    from hamiltonian_lang.v1.pipeline.problem import OracleGuardUnavailable

    def absent() -> object:
        raise _evaluation.EvaluationTreeUnavailable("simulated absence")

    monkeypatch.setattr(_evaluation, "oracle", absent)
    with pytest.raises(OracleGuardUnavailable):
        solve_problem(load_problem(DEMO / "algebra_rectangle.json"), config)


def test_a_missing_front_end_is_reported_as_not_measured(
    config: SolveConfig, monkeypatch
) -> None:
    """Substituting a permissive fallback would report a parse rate for no parser."""
    from hamiltonian_lang.v1.pipeline import _evaluation

    real = _evaluation.candidates()

    class NoAdapters:
        CANDIDATES = real.CANDIDATES
        extract_fenced = staticmethod(real.extract_fenced)

        @staticmethod
        def resolve_adapters(**_: object) -> dict[str, None]:
            return dict.fromkeys(real.CANDIDATES, None)

    monkeypatch.setattr(_evaluation, "candidates", lambda: NoAdapters)
    with pytest.raises(PipelineError, match="no front end"):
        solve_problem(load_problem(DEMO / "algebra_rectangle.json"), config)


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


def test_cli_runs_writes_a_record_and_exits_zero_on_verified(tmp_path, capsys) -> None:
    out = tmp_path / "record.json"
    code = main(
        [
            "--problem", str(DEMO / "algebra_rectangle.json"),
            "--config", str(CONFIG),
            "--json", str(out),
        ]
    )
    assert code == 0
    printed = capsys.readouterr().out
    assert "verdict : VERIFIED" in printed
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["final_verdict"] == "VERIFIED"
    assert payload["answer"]["matches_key"] is True


def test_cli_exits_two_when_the_run_cannot_be_made(capsys) -> None:
    code = main(["--problem", str(DEMO / "does_not_exist.json")])
    assert code == 2
    assert "ProblemError" in capsys.readouterr().err
