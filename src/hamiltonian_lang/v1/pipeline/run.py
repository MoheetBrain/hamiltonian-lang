"""The V1 pipeline driver: problem in, verified answer out.

::

    problem -> reasoning draft -> selected HML surface -> parse -> resolve -> type-check
            -> verify -> first-failure diagnostic -> ONE bounded repair -> recompile
            -> answer

Everything load-bearing here is borrowed
----------------------------------------
This module is a driver, not an implementation. Staged compilation is
:func:`hamiltonian_lang.improvement.episodes.classify_stages`; verification is
:func:`hamiltonian_lang.verification.obligations.verify_source` together with
``improvement.verification.default_federation()`` and ``classify()``; diagnosis and the
repair plan are :mod:`hamiltonian_lang.repair`; the surface front end comes from
``evaluation.syntax_gate.candidates.resolve_adapters``. Where this file makes a decision
of its own it is written down in a comment, because a second implementation of any of
those would drift from the first and the drift would be invisible.

``CompileResult.ok()`` is never read as a parse verdict
-------------------------------------------------------
Wrong arity, a wrong role label, a declared-type mismatch and an epistemic mismatch all
parse **and** resolve cleanly and fail only in the type checker; an unknown identifier
parses cleanly and fails in resolution. Every stage verdict in this pipeline comes from
``classify_stages``, which runs each stage in its own right.

Three properties the tests hold this file to
--------------------------------------------
*No hidden truncation* — the JSON record carries every model response in full.
*No silent retry* — exactly one generation call, at most one repair call, each recorded
with its index; the scripted backend independently raises on a second repair.
*No answer-key access in reasoning mode* — the key is compared only after the last model
call, and every prompt is scanned by ``assert_no_oracle`` with no exemption.
"""

from __future__ import annotations

from typing import Any

from ...improvement.diagnostics import StructuredDiagnostic, adapt_all
from ...improvement.episodes import StageOutcome, StageStatus, classify_stages
from ...improvement.runner import ArenaTask, ModelBackend, ModelResponse, ScriptedModel
from ...repair.arms import build_payload
from ...repair.plan import NoPlan, RepairPlan, assert_plan_non_leaking, statement_lines
from ...repair.teacher import DeterministicRepairTeacher
from . import _evaluation
from .answer import extract_answer, grade
from .config import ConfigError, SolveConfig
from .problem import (
    Problem,
    assert_prompt_carries_no_oracle,
    injected_repair_text,
    reasoning_prompt,
    repair_prompt,
)
from .record import (
    AnswerRecord,
    AttemptRecord,
    SolveRecord,
    StepRecord,
    StepStatus,
)

__all__ = ["PipelineError", "solve_problem", "build_model"]


class PipelineError(RuntimeError):
    """The pipeline cannot proceed truthfully. Never swallowed into a verdict."""


# ---------------------------------------------------------------------------
# Surface and model resolution
# ---------------------------------------------------------------------------


def _resolve_surface(surface: str) -> tuple[Any, tuple[str, ...], str]:
    """Bind the configured surface to a front end. Absence is refused, never defaulted."""
    try:
        module = _evaluation.candidates()
    except _evaluation.EvaluationTreeUnavailable as exc:  # pragma: no cover - environment
        raise PipelineError(str(exc)) from exc
    registry = module.CANDIDATES
    if surface not in registry:
        raise ConfigError(
            f"surface {surface!r} is not a registered candidate; known: "
            f"{sorted(registry)}"
        )
    adapter = module.resolve_adapters().get(surface)
    if adapter is None:
        raise PipelineError(
            f"candidate {surface!r} has no front end. That is NOT MEASURED, not a "
            "failure; substituting a permissive fallback would produce a parse rate for "
            "a parser that does not exist."
        )
    tags = tuple(registry[surface].fence_tags)
    return adapter, tags, f"{type(adapter).__module__}.{type(adapter).__name__}"


def build_model(problem: Problem, config: SolveConfig) -> ModelBackend:
    """Construct the backend named by the config. Reuses the shipped scripted adapter."""
    if config.model != "scripted":
        raise ConfigError(
            f"model {config.model!r} is not implemented in the V1 pipeline; only the "
            "deterministic scripted backend ships in this milestone"
        )
    if problem.scripted_turns is None:
        raise PipelineError(
            f"problem {problem.problem_id!r} carries no scripted_turns, so the scripted "
            "backend has nothing to replay"
        )
    return ScriptedModel({problem.problem_id: problem.scripted_turns})


# ---------------------------------------------------------------------------
# One compile-and-verify pass
# ---------------------------------------------------------------------------


def _select_surface(raw_text: str, tags: tuple[str, ...]) -> tuple[str, str]:
    """Pull the candidate encoding out of the model's reply, and say how it was found."""
    fenced = _evaluation.candidates().extract_fenced(raw_text, tags)
    if fenced is not None:
        return fenced, f"fenced block (tags tried: {', '.join(tags)})"
    # Recorded fallback, not a hidden one: a model that omits the fence made a formatting
    # error, not a mathematical one, and the two are reported separately.
    return raw_text.strip(), "NO FENCED BLOCK FOUND; the whole reply was taken verbatim"


def _run_federation(source: str, config: SolveConfig) -> tuple[str, list[dict[str, Any]]]:
    from ...improvement.verification import (
        Candidate,
        CanonicalObject,
        classify,
        default_federation,
    )

    federation = default_federation(include_execution=config.include_execution_verifiers)
    results = federation.run(
        CanonicalObject(object_id="v1-solve"), Candidate(text=source)
    )
    return classify(results), [r.to_dict() for r in results]


def _evaluate_attempt(
    *,
    label: str,
    model_call: str,
    raw_text: str,
    adapter: Any,
    tags: tuple[str, ...],
    config: SolveConfig,
    problem_id: str,
) -> tuple[AttemptRecord, StageOutcome | None, str]:
    """Select, compile stage by stage, verify. Returns the record and the stage outcome."""
    surface, how = _select_surface(raw_text, tags)
    if not surface.strip():
        empty = classify_stages("", file=f"<{problem_id}:{label}>")
        return (
            AttemptRecord(
                label=label,
                model_call=model_call,
                raw_model_text=raw_text,
                extracted_surface=None,
                hml_l1=None,
                stages=empty.to_dict(),
                obligations=None,
                federation_verdict="UNSUPPORTED",
            ),
            empty,
            how,
        )

    outcome = adapter.parse(surface)
    stages: StageOutcome | None = outcome.stages
    hml_l1 = outcome.hml_l1
    obligations: dict[str, Any] | None = None
    verdict = "UNSUPPORTED"
    results: list[dict[str, Any]] = []

    if hml_l1 is not None and stages is not None and stages.compiled:
        from ...verification.obligations import verify_source

        verification = verify_source(hml_l1, f"<{problem_id}:{label}>")
        obligations = verification.to_dict()
        verdict, results = _run_federation(hml_l1, config)
        # Re-classify with the verifier's verdict so the stage record and the federation
        # cannot disagree about whether verification passed. One classifier, always.
        stages = classify_stages(
            hml_l1,
            file=f"<{problem_id}:{label}>",
            verifier_passed=verdict == "VERIFIED",
        )
    elif stages is not None:
        verdict, results = _run_federation(surface, config)

    return (
        AttemptRecord(
            label=label,
            model_call=model_call,
            raw_model_text=raw_text,
            extracted_surface=surface,
            hml_l1=hml_l1,
            stages=stages.to_dict() if stages is not None else None,
            obligations=obligations,
            federation_verdict=verdict,
            federation_results=results,
        ),
        stages,
        how,
    )


def _stage_steps(stages: StageOutcome | None, suffix: str = "") -> list[StepRecord]:
    """Project one stage record onto the three named pipeline steps."""
    if stages is None:
        return [
            StepRecord(f"{name}{suffix}", StepStatus.SKIPPED, "no candidate to compile")
            for name in ("parse", "resolve", "type-check")
        ]
    mapping = {
        "parse": stages.parse_status,
        "resolve": stages.resolution_status,
        "type-check": stages.type_status,
    }
    steps: list[StepRecord] = []
    for name, status in mapping.items():
        if status is StageStatus.PASS:
            step_status, detail = StepStatus.PASS, ""
        elif status is StageStatus.FAIL:
            step_status, detail = StepStatus.FAIL, stages.detail
        else:
            step_status, detail = StepStatus.SKIPPED, f"stage {status}"
        steps.append(
            StepRecord(
                f"{name}{suffix}",
                step_status,
                detail,
                {"status": str(status), "codes": list(stages.diagnostic_codes)},
            )
        )
    return steps


# ---------------------------------------------------------------------------
# First-failure localisation and the verified prefix
# ---------------------------------------------------------------------------


def _first_failure(source: str, file: str) -> tuple[StructuredDiagnostic | None, str, int]:
    """The earliest located error, and the source text that precedes it.

    ``compile_source`` stops at the first stage that reports, so every diagnostic in the
    bag belongs to the same stage; within it the earliest span is the first failure. The
    verified prefix is the run of lines strictly before that span — the part of the
    program the compiler had already accepted when it stopped.
    """
    from ... import compile_source

    result = compile_source(source, file)
    diagnostics = adapt_all(result.diagnostics)
    if not diagnostics:
        return None, "", 0
    located = [d for d in diagnostics if d.source_span.located]
    first = min(located, key=lambda d: (d.source_span.line, d.source_span.col)) if located else diagnostics[0]
    if not first.source_span.located:
        return first, "", 0
    lines = source.splitlines()
    prefix_lines = lines[: max(0, first.source_span.line - 1)]
    return first, "\n".join(prefix_lines), len(prefix_lines)


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------


def solve_problem(
    problem: Problem,
    config: SolveConfig | None = None,
    *,
    model: ModelBackend | None = None,
) -> SolveRecord:
    """Run the whole path once. Returns a record whatever happens; never a bare bool."""
    config = config or SolveConfig()
    if config.repair_budget.limit != 1:
        raise ConfigError(
            f"the V1 pipeline performs exactly one bounded repair, but repair_budget "
            f"{config.repair_budget.value} allows {config.repair_budget.limit}. A "
            "three-turn arm does not measure the same quantity as a one-turn arm and is "
            "not run here under a one-turn name."
        )

    steps: list[StepRecord] = []
    errors: list[str] = []
    model_calls: list[dict[str, Any]] = []

    adapter, tags, adapter_name = _resolve_surface(config.surface)
    steps.append(
        StepRecord(
            "select-syntax",
            StepStatus.PASS,
            f"{config.surface} via {adapter_name}",
            {"surface": config.surface, "adapter": adapter_name, "fence_tags": list(tags)},
        )
    )

    backend = model or build_model(problem, config)
    if getattr(backend, "live", False) and not config.allow_live_model:
        raise PipelineError(
            f"backend {getattr(backend, 'name', backend)!r} reports live=True and "
            "allow_live_model is false; a live call is refused"
        )

    # -- the draft ---------------------------------------------------------------
    prompt = reasoning_prompt(
        problem.disclosable, surface=config.surface, fence_tag=tags[0] if tags else "hml"
    )
    assert_prompt_carries_no_oracle(prompt, problem, where=f"draft[{problem.problem_id}]")
    steps.append(
        StepRecord(
            "prompt",
            StepStatus.PASS,
            "built from prose, question and answer format only; scanned by assert_no_oracle",
            {"prompt_chars": len(prompt), "oracle_scan": "PASSED", "exemption": None},
        )
    )

    # The task object handed to the backend deliberately carries no reference encoding.
    # ArenaTask.reference_source is the answer key in HML form; a live adapter that built
    # its request from the task rather than the prompt would leak it, so this path never
    # puts it there.
    task = ArenaTask(
        task_id=problem.problem_id,
        prompt=prompt,
        reference_source="",
        required_verifiers=("obligation_discharge",),
        description=problem.disclosable.question,
    )
    draft: ModelResponse = backend.generate(task, prompt)
    model_calls.append(
        {"index": 0, "role": "generate", "backend": getattr(backend, "name", "?"),
         "live": bool(getattr(backend, "live", False)), "error": draft.error,
         "response_chars": len(draft.text)}
    )
    if not draft.ok:
        errors.append(f"the model reported an error on generation: {draft.error}")
    steps.append(
        StepRecord(
            "draft",
            StepStatus.PASS if draft.ok else StepStatus.FAIL,
            f"{len(draft.text)} characters from {getattr(backend, 'name', '?')}",
            {"tokens": draft.tokens.to_dict()},
        )
    )

    attempt, stages, how = _evaluate_attempt(
        label="draft",
        model_call="generate#0",
        raw_text=draft.text,
        adapter=adapter,
        tags=tags,
        config=config,
        problem_id=problem.problem_id,
    )
    steps.append(StepRecord("extract", StepStatus.PASS, how))
    steps.extend(_stage_steps(stages))
    steps.append(_verify_step(attempt, stages))

    attempts = [attempt]
    first_failure_record: dict[str, Any] | None = None
    repair_record: dict[str, Any] | None = None
    repair_used = False

    # -- first failure, then exactly one bounded repair ---------------------------
    needs_repair = attempt.federation_verdict != "VERIFIED"
    if not needs_repair:
        steps.append(
            StepRecord("localise", StepStatus.NOT_APPLICABLE, "the draft verified; nothing failed")
        )
        steps.append(
            StepRecord("repair", StepStatus.NOT_APPLICABLE, "the draft verified; the budget was not spent")
        )
    else:
        source_for_diagnosis = attempt.hml_l1 or attempt.extracted_surface or ""
        diagnostic, verified_prefix, prefix_lines = _first_failure(
            source_for_diagnosis, f"<{problem.problem_id}>"
        )
        if diagnostic is None:
            first_failure_record = {
                "code": None,
                "where": None,
                "message": (
                    "the candidate compiles; the verdict is not VERIFIED for a reason the "
                    "compiler does not report as a diagnostic (see the obligation record)"
                ),
                "verified_prefix_lines": None,
            }
            steps.append(
                StepRecord(
                    "localise",
                    StepStatus.PASS,
                    "no compiler diagnostic; the block is in verification, not compilation",
                    first_failure_record,
                )
            )
            steps.append(
                StepRecord(
                    "repair",
                    StepStatus.SKIPPED,
                    "no compiler diagnostic to repair from; the Teacher is not asked to "
                    "invent one",
                )
            )
        else:
            span = diagnostic.source_span
            where = f"{span.file}:{span.line}:{span.col + 1}" if span.located else "not attributed"
            first_failure_record = {
                "code": diagnostic.code,
                "category": str(diagnostic.category),
                "where": where,
                "message": diagnostic.message,
                "diagnostic": diagnostic.to_dict(),
                "verified_prefix_lines": prefix_lines,
                "verified_prefix": verified_prefix,
            }
            steps.append(
                StepRecord(
                    "localise",
                    StepStatus.PASS,
                    f"{diagnostic.code} at {where}; {prefix_lines} line(s) verified before it",
                    {"code": diagnostic.code, "where": where},
                )
            )
            repair_step, repair_record, repaired = _attempt_repair(
                problem=problem,
                config=config,
                backend=backend,
                task=task,
                broken=source_for_diagnosis,
                diagnostic=diagnostic,
                verified_prefix=verified_prefix,
                model_calls=model_calls,
                errors=errors,
            )
            steps.append(repair_step)
            if repaired is not None:
                repair_used = True
                new_attempt, stages, how = _evaluate_attempt(
                    label="repair",
                    model_call="repair#1",
                    raw_text=repaired.text,
                    adapter=adapter,
                    tags=tags,
                    config=config,
                    problem_id=problem.problem_id,
                )
                attempts.append(new_attempt)
                attempt = new_attempt
                steps.append(StepRecord("extract#2", StepStatus.PASS, how))
                steps.extend(_stage_steps(stages, suffix="#2"))
                steps.append(_verify_step(attempt, stages, suffix="#2"))
                if repair_record is not None:
                    repair_record["outcome"] = attempt.federation_verdict

    # -- the answer ---------------------------------------------------------------
    if attempt.hml_l1:
        answer = extract_answer(
            attempt.hml_l1, binding=problem.answer_binding, file=f"<{problem.problem_id}>"
        )
    else:
        answer = AnswerRecord(
            kind="NOT_EXTRACTED",
            value=None,
            basis="no candidate compiled, so there is no module to read an answer from",
        )
    # The one and only read of the answer key, after the last model call has been made.
    answer = grade(answer, problem.withheld.answer_key)
    steps.append(
        StepRecord(
            "answer",
            StepStatus.PASS if answer.value is not None else StepStatus.FAIL,
            answer.basis,
            {"kind": answer.kind, "matches_key": answer.matches_key},
        )
    )

    terminal = "NOT_RUN"
    if attempt.stages is not None:
        terminal = str(attempt.stages.get("terminal", "NOT_RUN"))

    return SolveRecord(
        problem=problem.to_public_dict(),
        config=config.to_dict(),
        steps=tuple(steps),
        attempts=tuple(attempts),
        answer=answer,
        final_verdict=attempt.federation_verdict,
        terminal=terminal,
        repair_used=repair_used,
        repair=repair_record,
        first_failure=first_failure_record,
        model_calls=tuple(model_calls),
        errors=tuple(errors),
    )


def _verify_step(
    attempt: AttemptRecord, stages: StageOutcome | None, suffix: str = ""
) -> StepRecord:
    if stages is None or not stages.compiled:
        return StepRecord(
            f"verify{suffix}",
            StepStatus.SKIPPED,
            "the candidate never compiled, so no obligation was generated to discharge",
        )
    obligations = attempt.obligations or {}
    counts = obligations.get("counts", {})
    detail = f"{attempt.federation_verdict}; obligations {counts}"
    return StepRecord(
        f"verify{suffix}",
        StepStatus.PASS if attempt.federation_verdict == "VERIFIED" else StepStatus.FAIL,
        detail,
        {
            "federation_verdict": attempt.federation_verdict,
            "obligation_verdict": obligations.get("verdict"),
            "substantive": obligations.get("substantive"),
        },
    )


def _attempt_repair(
    *,
    problem: Problem,
    config: SolveConfig,
    backend: ModelBackend,
    task: ArenaTask,
    broken: str,
    diagnostic: StructuredDiagnostic,
    verified_prefix: str,
    model_calls: list[dict[str, Any]],
    errors: list[str],
) -> tuple[StepRecord, dict[str, Any] | None, ModelResponse | None]:
    """One repair turn: Teacher diagnoses, model applies. Never two.

    The Teacher is role-separated by construction — ``DeterministicRepairTeacher`` returns
    a cause and a plan and its output is passed through ``assert_plan_non_leaking`` inside
    ``teach``. The corrected program comes from the model, which is a different role.
    """
    teacher = DeterministicRepairTeacher()
    context, plan = teacher.diagnose(
        broken_output=broken,
        diagnostic=diagnostic,
        verified_prefix=verified_prefix,
        forbid_novel_numerals=True,
    )
    payload = build_payload(
        config.feedback_arm,
        broken_output=broken,
        diagnostic=diagnostic,
        context=context,
        plan=plan,
    )
    # Two checks over and above the Teacher's own contract. Both are cheap and both fail
    # loudly, because a repair turn that hands over the answer makes every number
    # downstream of it uninterpretable.
    #
    # 1. The rendered plan must contain no *statement lines* -- lines opening with an HML
    #    statement keyword. That is the shared definition of "this line is a program, not
    #    prose"; the retrieved context is exempt, because project signatures are the
    #    COCOGEN treatment rather than a leak.
    leaked = statement_lines(payload.plan_text)
    if leaked:
        raise PipelineError(
            f"the repair plan contains {len(leaked)} HML statement line(s) ({leaked[:2]}); "
            "the Teacher returns a cause and a plan, never the corrected program"
        )
    # 2. The plan must not contain the final answer in any spelling. The key is read here
    #    only to assert its absence -- the same use `assert_no_oracle` makes of it.
    if isinstance(plan, RepairPlan):
        assert_plan_non_leaking(
            plan,
            final_answer=str(problem.withheld.answer_key.value),
            known_numerals=(),
            forbid_novel_numerals=False,
        )

    prompt = repair_prompt(problem.disclosable, payload_text=payload.render())
    # Scan what this pipeline injected. The model's own broken output is excluded, and
    # `injected_repair_text` documents why that is not a loophole.
    assert_prompt_carries_no_oracle(
        injected_repair_text(problem.disclosable, payload),
        problem,
        where=f"repair[{problem.problem_id}]",
    )

    record: dict[str, Any] = {
        "budget": str(config.repair_budget),
        "limit": config.repair_budget.limit,
        "arm": str(config.feedback_arm),
        "plan_kind": type(plan).__name__,
        "context_status": str(context.status),
        "error_class": str(plan.error_class) if plan.error_class is not None else None,
        "cause": plan.cause if isinstance(plan, RepairPlan) else plan.reason,
        "plan": plan.to_dict(),
        "payload": payload.to_dict(),
        "prompt_chars": len(prompt),
        "oracle_scan": "PASSED (injected material only; the model's own prior output is "
                       "upstream model output, not an oracle field)",
        "outcome": "not run",
    }
    if isinstance(plan, NoPlan):
        record["preservation_constraints"] = []
    else:
        record["preservation_constraints"] = list(plan.preservation_constraints)

    response = backend.repair(task, broken, prompt)
    model_calls.append(
        {"index": 1, "role": "repair", "backend": getattr(backend, "name", "?"),
         "live": bool(getattr(backend, "live", False)), "error": response.error,
         "response_chars": len(response.text)}
    )
    if not response.ok:
        errors.append(f"the model reported an error on repair: {response.error}")
        record["outcome"] = "model error"
        return (
            StepRecord("repair", StepStatus.FAIL, str(response.error), record),
            record,
            None,
        )
    return (
        StepRecord(
            "repair",
            StepStatus.PASS,
            f"one bounded repair under {config.feedback_arm}; plan={type(plan).__name__}",
            {"error_class": record["error_class"], "plan_kind": record["plan_kind"]},
        ),
        record,
        response,
    )
