"""Tournament harness for Phases G2-G4.

Concurrency, measured rather than guessed
-----------------------------------------
This machine has 18 physical cores and the model is GPU-resident, so **CPU parallelism
does not speed up model calls at all**. ``docs/evaluation/EXECUTION_ENVIRONMENT.md``
records the probe: with ``OLLAMA_NUM_PARALLEL=4``, four client workers give **2.08x**
aggregate throughput and eight workers *degrade* to **1.43x**, because oversubscribing
past the slot count makes requests queue while still competing for memory bandwidth.
``MAX_WORKERS`` is therefore pinned to the slot count and is not a tuning knob.

The 18 cores pay off in scoring and analysis, which are pure CPU. ``SCORING_WORKERS``
uses them.

Two contract rules, encoded rather than documented
--------------------------------------------------
1. **An empty visible answer is a model failure and is never retried.** The shared
   ``OllamaAdapter`` retries an empty completion once by default; this harness therefore
   constructs it with ``retries=0`` and performs its own retry loop, which fires on
   **transport failures only**. Retrying on content would bias the sample toward outputs
   the caller likes.
2. **Every attempt is preserved.** A retried transport failure appends the original
   request and the original response to the raw log before the retry is made. The raw
   log is opened append-only and is never rewritten, so a re-run can add rows and can
   never remove or alter one.

Phase ordering
--------------
No model call is legitimate until the Phase F3 offline equivalence gate passes and the
Lead Architect freezes at F4. ``run_tournament`` refuses any adapter that reports
``LIVE = True`` until ``FREEZE_MANIFEST.json`` exists. ``StubAdapter`` reports
``LIVE = False`` and is what the tests drive.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from . import SYNTAX_GATE_VERSION
from .candidates import SyntaxAdapter, resolve_adapters
from .prompts import Prompt, build_prompt
from .scorer import TrialInput
from .tasks import GateTask

__all__ = [
    "MAX_WORKERS",
    "SCORING_WORKERS",
    "CONCURRENCY_CITATION",
    "PhaseGateError",
    "ContextBudgetError",
    "PER_SLOT_TOKEN_BUDGET",
    "ModelBackend",
    "StubAdapter",
    "OllamaBackend",
    "RunConfig",
    "run_tournament",
    "freeze_manifest_path",
    "freeze_present",
    "require_freeze",
    "append_raw",
    "RAW_DIR",
]

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "evaluation" / "results" / "syntax_gate"
RAW_DIR = RESULTS / "raw"

#: Client concurrency for model calls. **Equal to OLLAMA_NUM_PARALLEL by requirement.**
#: Measured on this host: 1 worker 22.8 tok/s, 2 workers 35.1, 4 workers 47.4 (2.08x),
#: 8 workers 32.7 (1.43x -- worse than four). See
#: docs/evaluation/EXECUTION_ENVIRONMENT.md, Finding 2.
MAX_WORKERS = 4

CONCURRENCY_CITATION = (
    "docs/evaluation/EXECUTION_ENVIRONMENT.md Finding 2: four batching slots give 2.08x "
    "at four client workers and degrade to 1.43x at eight. Client concurrency must equal "
    "the slot count; MAX_WORKERS is not a tuning knob."
)

#: Scoring and analysis are CPU-bound and this is where 18 cores help.
SCORING_WORKERS = int(os.environ.get("HML_JOBS") or (os.cpu_count() or 4))


#: ``OLLAMA_NUM_PARALLEL=4`` divides the 32768-token context into four 8192-token slots
#: (docs/evaluation/EXECUTION_ENVIRONMENT.md, Finding 3). The longest prompt must be
#: measured against the per-slot budget, not the total.
PER_SLOT_TOKEN_BUDGET = 8192


class PhaseGateError(RuntimeError):
    """Raised when a live model call is attempted before the Phase F4 freeze."""


class ContextBudgetError(RuntimeError):
    """Raised when a prompt is estimated to exceed the per-slot context budget.

    EXECUTION_ENVIRONMENT.md Finding 3 is explicit: if a curriculum does not fit, the
    correct response is to lower ``OLLAMA_NUM_PARALLEL`` or shorten the curriculum **as
    a recorded decision**, never to let the server truncate it. A truncated curriculum
    is a different experimental condition wearing the same label, and it would be
    reported as the labelled one.
    """


def freeze_manifest_path() -> Path:
    return RESULTS / "FREEZE_MANIFEST.json"


def freeze_present() -> bool:
    return freeze_manifest_path().exists()


def require_freeze() -> None:
    if not freeze_present():
        raise PhaseGateError(
            "no Phase F4 freeze manifest at "
            f"{freeze_manifest_path()}. Phase ordering is strict: the offline "
            "equivalence gate (F3) must pass and the Lead Architect must freeze (F4) "
            "before any model call is legitimate. A call made now would contaminate "
            "the experiment. Run with a non-live adapter (StubAdapter) instead."
        )


# ---------------------------------------------------------------------------
# Model backends
# ---------------------------------------------------------------------------


@runtime_checkable
class ModelBackend(Protocol):
    """What the harness needs from a generator. Deliberately smaller than OllamaAdapter."""

    LIVE: bool

    def generate(self, system: str, user: str) -> dict[str, Any]:
        """Return a dict with content, reasoning, prompt_tokens, completion_tokens,
        latency_s, finish_reason, error, from_cache, cache_key."""


def _blank_generation(**kw: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "content": "", "reasoning": "", "prompt_tokens": 0, "completion_tokens": 0,
        "latency_s": 0.0, "finish_reason": "", "error": None, "from_cache": False,
        "cache_key": "", "model_digest": "", "captured_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        ),
    }
    out.update(kw)
    return out


class StubAdapter:
    """A deterministic, offline generator. **Never touches a model or a network.**

    Exists so the harness can be built and unit-tested before the freeze without
    contaminating the experiment. ``responder`` maps (condition, task_id) to a reply, so
    a test can produce a clean parse, a syntax error, an empty answer or a transport
    failure on demand.
    """

    LIVE = False

    def __init__(self, responder=None, *, fail_transport_times: int = 0) -> None:
        self.responder = responder or (lambda system, user: "")
        self.calls: list[tuple[str, str]] = []
        self._transport_budget = fail_transport_times

    def generate(self, system: str, user: str) -> dict[str, Any]:
        self.calls.append((system, user))
        if self._transport_budget > 0:
            self._transport_budget -= 1
            return _blank_generation(error="StubTransportError: injected", latency_s=0.01)
        reply = self.responder(system, user)
        if isinstance(reply, dict):
            return _blank_generation(**reply)
        text = reply or ""
        return _blank_generation(
            content=text,
            completion_tokens=max(1, len(text) // 4),
            prompt_tokens=max(1, len(user) // 4),
            latency_s=0.01,
            finish_reason="stop",
        )


class OllamaBackend:
    """Adapter over the Lead-owned ``evaluation/model_adapters/ollama.py``.

    Reuses that module's content-addressed cache verbatim, so a repeated study costs
    nothing for calls already made. Constructed with ``retries=0`` on purpose: that
    module retries an empty completion once, and this milestone's contract is that an
    empty visible answer is a **model failure**, never retried. Transport retries are
    performed here instead, where every attempt can be preserved.
    """

    LIVE = True

    def __init__(self, cfg=None) -> None:
        from dataclasses import replace

        from evaluation.model_adapters.ollama import OllamaAdapter, OllamaConfig

        base = cfg or OllamaConfig()
        # retries=0 disables the shared module's empty-content retry; see the docstring.
        self._adapter = OllamaAdapter(replace(base, retries=0))

    @property
    def model_info(self) -> dict:
        return self._adapter.model_info

    def generate(self, system: str, user: str) -> dict[str, Any]:
        gen = self._adapter.generate(system, user)
        return _blank_generation(
            content=gen.content, reasoning=gen.reasoning,
            prompt_tokens=gen.prompt_tokens, completion_tokens=gen.completion_tokens,
            latency_s=gen.latency_s, finish_reason=gen.finish_reason,
            error=gen.error, from_cache=gen.from_cache, cache_key=gen.cache_key,
            model_digest=gen.model_digest, captured_utc=gen.captured_utc,
        )


# ---------------------------------------------------------------------------
# Append-only raw log
# ---------------------------------------------------------------------------


def append_raw(run_id: str, record: dict, *, raw_dir: Path | None = None) -> Path:
    """Append one JSON record. Opened ``a`` only; nothing here can truncate a file.

    A re-run adds rows and can never remove or alter one, which is what makes a stored
    generation evidence rather than a cache of the current opinion.
    """
    d = Path(raw_dir or RAW_DIR)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{run_id}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return path


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


@dataclass
class RunConfig:
    run_id: str
    stage: str
    curriculum_size: int = 0
    seed: int | None = None
    #: Transport-only. An empty completion is never retried; see the module docstring.
    transport_retries: int = 2
    transport_backoff_s: float = 2.0
    max_workers: int = MAX_WORKERS
    raw_dir: Path | None = None
    #: Set only as a recorded decision. A prompt over the per-slot budget is truncated by
    #: the server, and a truncated curriculum is a different experimental condition.
    acknowledge_context_overflow: bool = False
    per_slot_token_budget: int = PER_SLOT_TOKEN_BUDGET
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.max_workers != MAX_WORKERS:
            self.notes.append(
                f"max_workers overridden to {self.max_workers}; {CONCURRENCY_CITATION}"
            )


def _one_trial(
    backend: ModelBackend,
    prompt: Prompt,
    cfg: RunConfig,
) -> TrialInput:
    """One prompt, at most ``transport_retries`` transport retries, all preserved."""
    attempts: list[dict] = []
    gen: dict[str, Any] = {}
    for attempt in range(1, cfg.transport_retries + 2):
        gen = backend.generate(prompt.system, prompt.user)
        attempts.append(
            {
                "attempt": attempt,
                "request": {"system": prompt.system, "user": prompt.user},
                "response": dict(gen),
            }
        )
        if not gen.get("error"):
            break
        if attempt <= cfg.transport_retries and cfg.transport_backoff_s > 0:
            time.sleep(cfg.transport_backoff_s * attempt)
    return TrialInput(
        trial_id=f"{cfg.run_id}:{prompt.condition}:{prompt.task_id}",
        run_id=cfg.run_id,
        task_id=prompt.task_id,
        condition=prompt.condition,
        curriculum_size=prompt.curriculum_size,
        seed=cfg.seed,
        content=gen.get("content", ""),
        reasoning=gen.get("reasoning", ""),
        prompt_tokens=gen.get("prompt_tokens", 0),
        completion_tokens=gen.get("completion_tokens", 0),
        latency_s=gen.get("latency_s", 0.0),
        finish_reason=gen.get("finish_reason", ""),
        error=gen.get("error"),
        attempts=attempts,
    )


def run_tournament(
    tasks: list[GateTask],
    conditions: list[str],
    backend: ModelBackend,
    cfg: RunConfig,
    *,
    demonstrations: list[GateTask] | None = None,
    adapters: dict[str, SyntaxAdapter | None] | None = None,
) -> list[TrialInput]:
    """Run one stage. Model calls at ``MAX_WORKERS``; nothing else is parallelised here.

    Refuses a live backend before the Phase F4 freeze. That check is the only thing
    standing between a half-built harness and a contaminated experiment, so it is a
    raised exception rather than a warning.
    """
    if getattr(backend, "LIVE", False):
        require_freeze()

    adapters = adapters if adapters is not None else resolve_adapters()
    demos = demonstrations or []
    prompts: list[Prompt] = []
    for task in tasks:
        for condition in conditions:
            prompts.append(build_prompt(task, condition, demos, adapters))

    # Context budget. Estimated, labelled as an estimate, and refused rather than left to
    # the server to truncate. EXECUTION_ENVIRONMENT.md Finding 3.
    from .prompts import estimate_tokens

    budget: dict[str, Any] = {"per_slot_token_budget": cfg.per_slot_token_budget}
    if prompts:
        worst = max(prompts, key=lambda p: len(p.system) + len(p.user))
        est = estimate_tokens(worst.system + "\n" + worst.user)
        budget.update(
            worst_prompt_condition=worst.condition,
            worst_prompt_task=worst.task_id,
            **est,
            fits=est["estimated_tokens_conservative"] <= cfg.per_slot_token_budget,
            estimate_only=True,
            authoritative="prompt_tokens reported per call",
        )
        if not budget["fits"] and getattr(backend, "LIVE", False):
            if not cfg.acknowledge_context_overflow:
                raise ContextBudgetError(
                    f"the longest prompt in this run ({worst.condition} / "
                    f"{worst.task_id}) is estimated at "
                    f"{est['estimated_tokens_conservative']} tokens against a per-slot "
                    f"budget of {cfg.per_slot_token_budget}. The server would truncate "
                    "it, and a truncated curriculum is a different experimental "
                    "condition. Lower OLLAMA_NUM_PARALLEL, shorten the curriculum, or "
                    "set acknowledge_context_overflow=True as a recorded decision."
                )
            cfg.notes.append(
                "context overflow acknowledged: "
                f"{est['estimated_tokens_conservative']} estimated tokens against a "
                f"{cfg.per_slot_token_budget}-token slot"
            )

    manifest = {
        "kind": "run_manifest",
        "context_budget": budget,
        "notes": list(cfg.notes),
        "run_id": cfg.run_id,
        "stage": cfg.stage,
        "version": SYNTAX_GATE_VERSION,
        "conditions": list(conditions),
        "task_ids": [t.id for t in tasks],
        "demonstration_ids": [d.id for d in demos],
        "curriculum_size": len(demos),
        "seed": cfg.seed,
        "max_workers": cfg.max_workers,
        "concurrency_citation": CONCURRENCY_CITATION,
        "backend": type(backend).__name__,
        "backend_live": bool(getattr(backend, "LIVE", False)),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "uuid": str(uuid.uuid4()),
    }
    append_raw(cfg.run_id, manifest, raw_dir=cfg.raw_dir)

    if cfg.max_workers <= 1 or len(prompts) == 1:
        trials = [_one_trial(backend, p, cfg) for p in prompts]
    else:
        with ThreadPoolExecutor(max_workers=cfg.max_workers) as pool:
            trials = list(pool.map(lambda p: _one_trial(backend, p, cfg), prompts))

    for t in trials:
        append_raw(
            cfg.run_id,
            {"kind": "trial", "version": SYNTAX_GATE_VERSION, **asdict(t)},
            raw_dir=cfg.raw_dir,
        )
    return trials
