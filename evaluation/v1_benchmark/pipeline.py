"""Execution. Model access is injected, explicit, and refused by default.

Why the default is refusal
--------------------------
This module was written while another study held the Ollama server. A stray call would
have corrupted that study's latency measurements, which is an unrecoverable contamination
of somebody else's data — you cannot un-measure a latency. So the pipeline has no implicit
path to a model:

* :func:`run_benchmark` takes a ``client`` and raises if it is ``None``. There is no
  fallback that constructs an Ollama adapter for you.
* It also takes a :class:`RunAuthorisation` naming who authorised the run, and refuses to
  proceed without one.
* :func:`live_client` is the only function in the package that can open a connection, it is
  never called from anywhere else, and it takes the same authorisation object.

The unit tests drive the whole pipeline through :class:`ScriptedClient`, which serves
canned strings. **No test in this package can reach a model.**

The surface must be named
-------------------------
``surface`` has no default. The syntax gate has not yet declared a winning candidate, and
a default would quietly install HML-L1 as the winner by omission — which is precisely the
kind of decision-by-default this project exists to avoid. Passing
:data:`FROZEN_L1_SURFACE` is a deliberate choice and is recorded in the run manifest as
one.

The per-task loop
-----------------
Both arms run the same shape, so the comparison is structural rather than a matter of care:

    call 1 -> extract answer -> [HML only: extract module, compile] -> call 2 -> extract answer

The HML arm's second call carries compiler diagnostics; the SE arm's carries only the
model's own prior working. Both are capped at
:data:`~evaluation.v1_benchmark.arms.PER_CALL_BUDGET`, and each arm's two calls sum to the
same total.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from evaluation.corpus.cso import CanonicalSemanticObject
from evaluation.corpus.renderers import HML_SPEC
from evaluation.v1_benchmark.arms import (
    MODEL,
    MODEL_DIGEST,
    PER_CALL_BUDGET,
    RUNTIME,
    TEMPERATURE,
    TOTAL_COMPLETION_BUDGET,
    Arm,
    extract_hml,
    hml_initial_prompt,
    hml_repair_prompt,
    se_initial_prompt,
    se_review_prompt,
)
from evaluation.v1_benchmark.scoring import (
    SE_VERIFIED_COMPLETION_NOT_APPLICABLE,
    TrialResult,
    classify_diagnostics,
    score_answer,
)
from evaluation.v1_benchmark.tasks import BenchTask

from hamiltonian_lang.improvement.state import Hypothesis

__all__ = [
    "Reply",
    "Client",
    "ScriptedClient",
    "RunAuthorisation",
    "ModelAccessRefused",
    "SurfaceNotDeclared",
    "FROZEN_L1_SURFACE",
    "run_task",
    "run_benchmark",
    "live_client",
]

#: The frozen HML-L1 reference, usable as a surface until the syntax gate names a winner.
FROZEN_L1_SURFACE = HML_SPEC


class ModelAccessRefused(RuntimeError):
    """A run was attempted without an injected client or without authorisation."""


class SurfaceNotDeclared(ValueError):
    """A run was attempted without naming the HML surface under test."""


@dataclass(frozen=True)
class Reply:
    """One model call's result. Deliberately the subset this study measures."""

    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    error: str | None = None


class Client(Protocol):
    """Anything that can answer a prompt. The live adapter and the fixtures both satisfy it."""

    def generate(self, system: str, user: str, *, max_tokens: int) -> Reply: ...


@dataclass
class ScriptedClient:
    """A client that serves canned replies. The only client the tests use.

    ``replies`` is consumed in order. Running out raises rather than returning an empty
    string, because a silently-empty reply would be scored as a model failure and would
    make a broken fixture look like a finding.
    """

    replies: list[str]
    calls: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 100
    completion_tokens: int = 200
    latency_s: float = 0.5

    def generate(self, system: str, user: str, *, max_tokens: int) -> Reply:
        if not self.replies:
            raise AssertionError(
                f"ScriptedClient exhausted after {len(self.calls)} calls. A fixture that "
                "runs out mid-task would otherwise be scored as a model failure."
            )
        self.calls.append({"system": system, "user": user, "max_tokens": max_tokens})
        return Reply(
            content=self.replies.pop(0),
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            latency_s=self.latency_s,
        )


@dataclass(frozen=True)
class RunAuthorisation:
    """Who authorised a live run, and against what state.

    Not a boolean and not defaultable. An unattributed run is indistinguishable after the
    fact from an accidental one, and this study is sharing a server with another.
    """

    authorised_by: str
    scope: str
    ollama_contention_cleared: bool

    def __post_init__(self) -> None:
        for f in ("authorised_by", "scope"):
            if not str(getattr(self, f)).strip():
                raise ModelAccessRefused(f"a run authorisation must record {f}")
        if not self.ollama_contention_cleared:
            raise ModelAccessRefused(
                "the run authorisation does not clear Ollama contention. Another study's "
                "latency measurements are invalidated by a concurrent call, and that "
                "damage cannot be undone after the fact."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorised_by": self.authorised_by,
            "scope": self.scope,
            "ollama_contention_cleared": self.ollama_contention_cleared,
        }


def _tally(replies: list[Reply]) -> tuple[int, int, float, list[str]]:
    return (
        sum(r.prompt_tokens for r in replies),
        sum(r.completion_tokens for r in replies),
        sum(r.latency_s for r in replies),
        [r.error for r in replies if r.error],
    )


def _run_se(task: BenchTask, client: Client) -> TrialResult:
    cso: CanonicalSemanticObject = task.cso

    p1 = se_initial_prompt(cso)
    r1 = client.generate(p1.system, p1.user, max_tokens=p1.completion_budget)
    first_ok, first_norm = score_answer(cso, r1.content)

    p2 = se_review_prompt(cso, r1.content)
    r2 = client.generate(p2.system, p2.user, max_tokens=p2.completion_budget)
    final_ok, final_norm = score_answer(cso, r2.content)

    pt, ct, lat, errs = _tally([r1, r2])
    return TrialResult(
        task_id=task.id,
        domain=task.domain,
        arm=Arm.SE,
        # Always H2: the SE arm is the control for the representation contrast and has no
        # verifier, so it can never be evidence about verifier-guided repair.
        hypothesis=Hypothesis.H2,
        answer_correct=final_ok,
        first_attempt_correct=first_ok,
        second_call_changed_answer=final_norm != first_norm,
        verified_completion=SE_VERIFIED_COMPLETION_NOT_APPLICABLE,
        structural_errors=SE_VERIFIED_COMPLETION_NOT_APPLICABLE,
        semantic_errors=SE_VERIFIED_COMPLETION_NOT_APPLICABLE,
        prompt_tokens=pt,
        completion_tokens=ct,
        latency_s=lat,
        normalised_answer=final_norm,
        errors=errs,
    )


def _run_hml(task: BenchTask, client: Client, surface: str) -> TrialResult:
    cso: CanonicalSemanticObject = task.cso

    p1 = hml_initial_prompt(cso, surface_spec=surface)
    r1 = client.generate(p1.system, p1.user, max_tokens=p1.completion_budget)
    first_ok, first_norm = score_answer(cso, r1.content)

    module = extract_hml(r1.content)
    verdict = classify_diagnostics(module)

    p2 = hml_repair_prompt(cso, module or "(no module emitted)", verdict.rendered, surface_spec=surface)
    r2 = client.generate(p2.system, p2.user, max_tokens=p2.completion_budget)
    final_ok, final_norm = score_answer(cso, r2.content)

    repaired_module = extract_hml(r2.content)
    final_verdict = classify_diagnostics(repaired_module) if repaired_module else verdict

    changed = final_norm != first_norm
    pt, ct, lat, errs = _tally([r1, r2])
    return TrialResult(
        task_id=task.id,
        domain=task.domain,
        arm=Arm.HML_V1,
        # The pre-registered attribution rule: the repair moving the answer makes the trial
        # evidence about the verifier loop, not about the representation.
        hypothesis=Hypothesis.H3 if changed else Hypothesis.H2,
        answer_correct=final_ok,
        first_attempt_correct=first_ok,
        second_call_changed_answer=changed,
        verified_completion=final_verdict.ok,
        structural_errors=final_verdict.structural_errors,
        semantic_errors=final_verdict.semantic_errors,
        prompt_tokens=pt,
        completion_tokens=ct,
        latency_s=lat,
        normalised_answer=final_norm,
        errors=errs,
    )


def run_task(task: BenchTask, client: Client, *, surface: str) -> list[TrialResult]:
    """Both arms of one task. Arm order is fixed so a shared cache warms identically."""
    if not surface or not surface.strip():
        raise SurfaceNotDeclared("the HML surface under test must be named; see the module docstring")
    return [_run_se(task, client), _run_hml(task, client, surface)]


def run_benchmark(
    tasks: list[BenchTask],
    *,
    client: Client | None = None,
    surface: str | None = None,
    authorisation: RunAuthorisation | None = None,
) -> dict[str, Any]:
    """Run every task in both arms. Refuses by default; see the module docstring."""
    if client is None:
        raise ModelAccessRefused(
            "run_benchmark requires an injected client. There is no implicit path to a "
            "model in this package: pass a ScriptedClient for a dry run, or live_client() "
            "with an authorisation once the Lead has cleared Ollama contention."
        )
    if authorisation is None:
        raise ModelAccessRefused(
            "run_benchmark requires a RunAuthorisation. An unattributed run cannot be "
            "distinguished afterwards from an accidental one."
        )
    if surface is None:
        raise SurfaceNotDeclared(
            "the HML surface under test must be named. The syntax gate has not declared a "
            "winner, and defaulting would install HML-L1 as the winner by omission. Pass "
            "FROZEN_L1_SURFACE explicitly if that is the intended choice."
        )

    started = time.time()
    rows: list[TrialResult] = []
    for task in tasks:
        rows.extend(run_task(task, client, surface=surface))

    return {
        "manifest": {
            "model": MODEL,
            "model_digest": MODEL_DIGEST,
            "temperature": TEMPERATURE,
            "runtime": RUNTIME,
            "total_completion_budget_per_task_per_arm": TOTAL_COMPLETION_BUDGET,
            "per_call_budget": PER_CALL_BUDGET,
            "surface_is_frozen_l1": surface == FROZEN_L1_SURFACE,
            "surface_chars": len(surface),
            "n_tasks": len(tasks),
            "authorisation": authorisation.to_dict(),
            "wall_clock_s": round(time.time() - started, 3),
        },
        "rows": [r.to_dict() for r in rows],
        "_rows": rows,
    }


def live_client(authorisation: RunAuthorisation, *, cache_dir: str | None = None) -> Client:
    """The only function here that can open a model connection.

    Imported lazily so that importing this package never touches the network stack, and
    kept separate from :func:`run_benchmark` so that the authorisation is presented twice —
    once to obtain the client and once to run — rather than threaded through implicitly.
    """
    if not isinstance(authorisation, RunAuthorisation):
        raise ModelAccessRefused("live_client requires a RunAuthorisation")

    from pathlib import Path

    from evaluation.model_adapters.ollama import OllamaAdapter, OllamaConfig

    cfg = OllamaConfig(
        model=MODEL,
        temperature=TEMPERATURE,
        max_tokens=PER_CALL_BUDGET,
        seed=0,
    )
    adapter = OllamaAdapter(
        cfg,
        cache_dir=Path(cache_dir) if cache_dir else None,
    )

    class _Adapted:
        def generate(self, system: str, user: str, *, max_tokens: int) -> Reply:
            gen = adapter.generate(system, user)
            return Reply(
                content=gen.content,
                prompt_tokens=gen.prompt_tokens,
                completion_tokens=gen.completion_tokens,
                latency_s=gen.latency_s,
                error=gen.error,
            )

    return _Adapted()
