"""The crash-safe experiment driver for the SE-versus-HML-V1 measurement.

Why this module replaces :func:`evaluation.v1_benchmark.pipeline.run_benchmark`
-------------------------------------------------------------------------------
``run_benchmark`` holds every result in memory and returns it at the end. For a run of ~100
calls at ~40 s each that is a two-hour window in which any interruption — a crash, a
context exhaustion, a closed laptop — loses everything. The previous session of this study
ended exactly that way.

It also interleaves the arms (``run_task`` runs SE then HML for each task), which makes the
SE-first headroom gate impossible: the gate must see the complete SE matrix before a single
HML call is made, so that an insufficient-headroom finding costs no HML compute and cannot
be reached after the treatment results are already visible.

Guarantees
----------
* **Write-once records.** One JSON file per (task, arm), named deterministically. The
  driver refuses to overwrite; a resume fills only what is missing.
* **Saved immediately.** A record is written the moment its task completes, not at the end.
* **Immutable manifest.** Written once at run start, hashed, and re-verified on every
  resume. Any drift in prompts, model, tasks, scorer or compiler halts the run.
* **Raw calls preserved.** Both calls' full content, reasoning, token counts, latency,
  finish reason and truncation status are stored verbatim.
* **Truncation halts.** A completion that hits the allowance is a measurement defect under
  this protocol, not a datum, and the run stops rather than silently recording it.
* **No silent patching.** The manifest hash covers the prompt builders, the scorer and the
  compiler; changing any of them mid-run is detected and refused.

Usage::

    .venv/bin/python -m evaluation.v1_benchmark.driver --arm SE     --run-id <id>
    .venv/bin/python -m evaluation.v1_benchmark.driver --arm HML-V1 --run-id <id>
    .venv/bin/python -m evaluation.v1_benchmark.driver --probe      --run-id <id>
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from evaluation.corpus.renderers import HML_SPEC, SCHEMA_A_PRIME
from evaluation.model_adapters.ollama import Generation, OllamaAdapter, OllamaConfig
from evaluation.v1_benchmark import answer_extraction
from evaluation.v1_benchmark import arms as arms_mod
from evaluation.v1_benchmark import scoring as scoring_mod
from evaluation.v1_benchmark.answer_extraction import score_answer_v13
from evaluation.v1_benchmark.arms import (
    MODEL,
    MODEL_DIGEST,
    TEMPERATURE,
    Arm,
    extract_hml,
    hml_initial_prompt,
    hml_repair_prompt,
    se_initial_prompt,
    se_review_prompt,
)
from evaluation.v1_benchmark.arms_v1_3 import hml_repair_prompt_v13
from evaluation.v1_benchmark.diagnostics_budget import bound_diagnostics
from evaluation.v1_benchmark.protocol_v1_2 import (
    EXCLUDED_TASKS,
    NUM_PARALLEL,
    PER_CALL_COMPLETION_ALLOWANCE,
    PER_SLOT_CONTEXT,
    PROTOCOL,
    RUNTIME_MEASURED,
    TOTAL_COMPLETION_ALLOWANCE_PER_ARM,
    amendment,
)
from evaluation.v1_benchmark.scoring import classify_diagnostics, score_answer
from evaluation.v1_benchmark.tasks import BenchTask, build_tasks

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "evaluation" / "results" / "v1_benchmark"

__all__ = [
    "RunPaths",
    "DriftDetected",
    "TruncationDetected",
    "build_manifest",
    "run_arm",
    "main",
]


class DriftDetected(RuntimeError):
    """A scientific input changed between manifest creation and execution."""


class TruncationDetected(RuntimeError):
    """A completion hit the allowance. Under v1.2 this halts the run."""


class DigestMismatch(RuntimeError):
    """The live model is not the pinned model."""


# ---------------------------------------------------------------------------
# Paths. One directory per run; records are addressed, never appended.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunPaths:
    run_id: str

    @property
    def root(self) -> Path:
        return RESULTS / self.run_id

    @property
    def manifest(self) -> Path:
        return self.root / "MANIFEST.json"

    @property
    def records(self) -> Path:
        return self.root / "records"

    @property
    def heartbeat(self) -> Path:
        return self.root / "HEARTBEAT.json"

    @property
    def progress(self) -> Path:
        return self.root / "PROGRESS.json"

    @property
    def cache(self) -> Path:
        return self.root / "generation_cache"

    def record(self, task_id: str, arm: str) -> Path:
        safe = arm.replace("/", "_")
        return self.records / f"{task_id}__{safe}.json"

    def ensure(self) -> None:
        self.records.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# The manifest, and the drift hash that makes it load-bearing
# ---------------------------------------------------------------------------


def _source_hash(*objs: Any) -> str:
    """Hash the *source text* of the functions and constants that define the experiment.

    Hashing the source rather than a version string means an edit to a prompt builder is
    detected even if nobody remembers to bump anything. That is the whole point: the
    failure this guards against is an honest mid-run edit, not a dishonest one.
    """
    h = hashlib.sha256()
    for o in objs:
        if isinstance(o, str):
            h.update(o.encode())
        else:
            h.update(inspect.getsource(o).encode())
        h.update(b"\x00")
    return h.hexdigest()


def scientific_input_hash() -> dict[str, str]:
    """Per-surface hashes, so a drift report names *what* moved."""
    tasks = build_tasks()
    task_blob = json.dumps(
        [
            {
                "id": t.id,
                "domain": t.domain,
                "prose": t.cso.prose,
                "question": t.cso.question,
                "answer": repr(t.cso.answer.value),
                "instruction": t.cso.answer.render_instruction(),
            }
            for t in tasks
        ],
        sort_keys=True,
    )
    from hamiltonian_lang import compile_source

    return {
        "tasks": hashlib.sha256(task_blob.encode()).hexdigest(),
        "prompts": _source_hash(
            se_initial_prompt,
            se_review_prompt,
            hml_initial_prompt,
            hml_repair_prompt,
            arms_mod._BASE_SYSTEM,
            arms_mod._HML_INSTRUCTION,
            SCHEMA_A_PRIME,
            HML_SPEC,
        ),
        "scorer": _source_hash(
            score_answer, scoring_mod.classify_diagnostics, scoring_mod.CompileVerdict
        ),
        "compiler": _source_hash(compile_source),
        "extraction": _source_hash(
            extract_hml,
            arms_mod.strip_answer_block,
            answer_extraction.extract_final_answer,
            answer_extraction.parse_numeric,
            answer_extraction.score_answer_v13,
        ),
        "repair_prompt_v13": _source_hash(hml_repair_prompt_v13),
        "diagnostics_budget": _source_hash(bound_diagnostics),
    }


def build_manifest(paths: RunPaths, *, task_ids: list[str], note: str) -> dict[str, Any]:
    """Create the manifest once, or return the existing one. Never rewrites."""
    if paths.manifest.exists():
        return json.loads(paths.manifest.read_text())

    manifest = {
        "run_id": paths.run_id,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": note,
        "protocol": PROTOCOL,
        "amendment": amendment(),
        "model": MODEL,
        "model_digest_pinned": MODEL_DIGEST,
        "temperature": TEMPERATURE,
        "per_call_completion_allowance": PER_CALL_COMPLETION_ALLOWANCE,
        "total_completion_allowance_per_arm": TOTAL_COMPLETION_ALLOWANCE_PER_ARM,
        "calls_per_task_per_arm": 2,
        "runtime_measured": RUNTIME_MEASURED,
        "per_slot_context": PER_SLOT_CONTEXT,
        "num_parallel": NUM_PARALLEL,
        "surface": "FROZEN_L1_SURFACE (HML_SPEC)",
        "surface_sha256": hashlib.sha256(HML_SPEC.encode()).hexdigest(),
        "frozen_task_order": task_ids,
        "excluded_tasks": EXCLUDED_TASKS,
        "n_tasks": len(task_ids),
        "scientific_input_hash": scientific_input_hash(),
        "arms": [str(Arm.SE), str(Arm.HML_V1)],
    }
    paths.ensure()
    paths.manifest.write_text(json.dumps(manifest, indent=2))
    return manifest


def verify_no_drift(manifest: dict[str, Any]) -> None:
    """Refuse to continue a run whose scientific inputs have moved."""
    now = scientific_input_hash()
    was = manifest["scientific_input_hash"]
    moved = [k for k in was if was[k] != now.get(k)]
    if moved:
        raise DriftDetected(
            "scientific inputs changed since the manifest was written: "
            + ", ".join(moved)
            + ". The run cannot continue; results already collected remain valid for the "
            "inputs recorded in the manifest, and a new run id is required for the new ones."
        )


# ---------------------------------------------------------------------------
# One call, fully preserved
# ---------------------------------------------------------------------------


def _call_record(stage: str, prompt: Any, gen: Generation) -> dict[str, Any]:
    truncated = gen.finish_reason == "length"
    return {
        "stage": stage,
        "system": prompt.system,
        "user": prompt.user,
        "prompt_sha256": hashlib.sha256(
            (prompt.system + "\x00" + prompt.user).encode()
        ).hexdigest(),
        "prompt_chars": len(prompt.system) + len(prompt.user),
        "requested_max_tokens": PER_CALL_COMPLETION_ALLOWANCE,
        "content": gen.content,
        "reasoning": gen.reasoning,
        "prompt_tokens": gen.prompt_tokens,
        "completion_tokens": gen.completion_tokens,
        "total_tokens": gen.total_tokens,
        "latency_s": gen.latency_s,
        "finish_reason": gen.finish_reason,
        "truncated": truncated,
        "attempts": gen.attempts,
        "from_cache": gen.from_cache,
        "empty": gen.empty,
        "error": gen.error,
        "cache_key": gen.cache_key,
        "model_digest": gen.model_digest,
        "sampling": gen.sampling,
        "captured_utc": gen.captured_utc,
    }


def _guard_call(rec: dict[str, Any], task_id: str, arm: str) -> None:
    if rec["error"]:
        # Transport failure is an operational fault, not model data. Halt: a run with
        # silent holes in it cannot be audited afterwards.
        raise RuntimeError(f"{task_id}/{arm}/{rec['stage']}: transport error {rec['error']}")
    if rec["truncated"]:
        raise TruncationDetected(
            f"{task_id}/{arm}/{rec['stage']} hit the {PER_CALL_COMPLETION_ALLOWANCE}-token "
            "allowance. Under v1.2 a truncated completion is a measurement defect, not a "
            "datum: it is an absent answer that the scorer would record as a failure of the "
            "representation under test."
        )


# ---------------------------------------------------------------------------
# The two arms
# ---------------------------------------------------------------------------


def _run_se_task(task: BenchTask, adapter: OllamaAdapter) -> dict[str, Any]:
    cso = task.cso
    p1 = se_initial_prompt(cso)
    g1 = adapter.generate(p1.system, p1.user)
    c1 = _call_record("initial", p1, g1)
    _guard_call(c1, task.id, str(Arm.SE))
    first_ok, first_norm, first_diag = score_answer_v13(cso.answer, g1.content)

    p2 = se_review_prompt(cso, g1.content)
    g2 = adapter.generate(p2.system, p2.user)
    c2 = _call_record("review", p2, g2)
    _guard_call(c2, task.id, str(Arm.SE))
    final_ok, final_norm, final_diag = score_answer_v13(cso.answer, g2.content)
    c1["scoring"] = first_diag
    c2["scoring"] = final_diag

    return {
        "task_id": task.id,
        "domain": task.domain,
        "arm": str(Arm.SE),
        "calls": [c1, c2],
        "first_attempt_correct": first_ok,
        "first_normalised_answer": first_norm,
        "answer_correct": final_ok,
        "normalised_answer": final_norm,
        "second_call_changed_answer": final_norm != first_norm,
        "verified_completion": None,
        "verified_completion_note": "not applicable: the SE arm emits no checkable artefact",
        "hml": None,
        "prompt_tokens": c1["prompt_tokens"] + c2["prompt_tokens"],
        "completion_tokens": c1["completion_tokens"] + c2["completion_tokens"],
        "latency_s": round(c1["latency_s"] + c2["latency_s"], 3),
    }


def _run_hml_task(task: BenchTask, adapter: OllamaAdapter, surface: str) -> dict[str, Any]:
    cso = task.cso
    p1 = hml_initial_prompt(cso, surface_spec=surface)
    g1 = adapter.generate(p1.system, p1.user)
    c1 = _call_record("initial", p1, g1)
    _guard_call(c1, task.id, str(Arm.HML_V1))
    first_ok, first_norm, first_diag = score_answer_v13(cso.answer, g1.content)

    module = extract_hml(g1.content)
    verdict = classify_diagnostics(module)
    bounded = bound_diagnostics(verdict.rendered)

    # v1.3: carry the full prior reply, exactly as the SE arm does, so that compiler
    # diagnostics are the ONLY thing distinguishing the two arms' second calls.
    p2 = hml_repair_prompt_v13(
        cso,
        g1.content,
        module or "(no module emitted)",
        bounded.text,
        surface_spec=surface,
    )
    g2 = adapter.generate(p2.system, p2.user)
    c2 = _call_record("repair", p2, g2)
    _guard_call(c2, task.id, str(Arm.HML_V1))
    final_ok, final_norm, final_diag = score_answer_v13(cso.answer, g2.content)
    c1["scoring"] = first_diag
    c2["scoring"] = final_diag

    repaired = extract_hml(g2.content)
    final_verdict = classify_diagnostics(repaired) if repaired else verdict

    return {
        "task_id": task.id,
        "domain": task.domain,
        "arm": str(Arm.HML_V1),
        "calls": [c1, c2],
        "first_attempt_correct": first_ok,
        "first_normalised_answer": first_norm,
        "answer_correct": final_ok,
        "normalised_answer": final_norm,
        "second_call_changed_answer": final_norm != first_norm,
        "verified_completion": final_verdict.ok,
        "verified_completion_note": "compiled: parsed, names resolved, types checked",
        "hml": {
            "initial_module": module,
            "initial_module_emitted": bool(module.strip()),
            "initial_verdict": verdict.to_dict(),
            "diagnostics_shown": bounded.to_dict(),
            "diagnostics_text": bounded.text,
            "repaired_module": repaired,
            "repaired_module_emitted": bool(repaired.strip()),
            "final_verdict": final_verdict.to_dict(),
            "structural_errors": final_verdict.structural_errors,
            "semantic_errors": final_verdict.semantic_errors,
        },
        "prompt_tokens": c1["prompt_tokens"] + c2["prompt_tokens"],
        "completion_tokens": c1["completion_tokens"] + c2["completion_tokens"],
        "latency_s": round(c1["latency_s"] + c2["latency_s"], 3),
    }


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


@dataclass
class Progress:
    run_id: str
    arm: str
    total: int
    done: int = 0
    failed: int = 0
    started_utc: str = ""
    errors: list[str] = field(default_factory=list)

    def write(self, paths: RunPaths) -> None:
        paths.progress.write_text(json.dumps(asdict(self), indent=2))


def _heartbeat(paths: RunPaths, arm: str, note: str, done: int, total: int) -> None:
    paths.heartbeat.write_text(
        json.dumps(
            {
                "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "epoch": time.time(),
                "pid": os.getpid(),
                "arm": arm,
                "note": note,
                "done": done,
                "total": total,
            },
            indent=2,
        )
    )


def run_arm(
    paths: RunPaths,
    arm: Arm,
    *,
    task_ids: list[str] | None = None,
    workers: int = NUM_PARALLEL,
    adapter: OllamaAdapter | None = None,
) -> Progress:
    """Run one arm over the frozen task order, resuming only what is missing.

    ``adapter`` exists so the driver's own guarantees — write-once, resume, drift refusal,
    truncation halt — are testable without a model. It is never passed in production; the
    live path constructs its own adapter and checks the digest against the pin.
    """
    manifest = json.loads(paths.manifest.read_text())
    verify_no_drift(manifest)

    order: list[str] = manifest["frozen_task_order"]
    if task_ids is not None:
        order = [t for t in order if t in set(task_ids)]

    by_id = {t.id: t for t in build_tasks()}
    pending = [tid for tid in order if not paths.record(tid, str(arm)).exists()]

    prog = Progress(
        run_id=paths.run_id,
        arm=str(arm),
        total=len(order),
        done=len(order) - len(pending),
        started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    prog.write(paths)
    print(
        f"[{arm}] {len(order)} tasks in frozen order; {prog.done} already recorded, "
        f"{len(pending)} to run; workers={workers}",
        flush=True,
    )
    if not pending:
        return prog

    if adapter is None:
        cfg = OllamaConfig(
            model=MODEL,
            temperature=TEMPERATURE,
            max_tokens=PER_CALL_COMPLETION_ALLOWANCE,
            seed=0,
            timeout_s=1800,
        )
        adapter = OllamaAdapter(cfg, cache_dir=paths.cache)
        if adapter.digest != MODEL_DIGEST:
            raise DigestMismatch(
                f"live digest {adapter.digest} != pinned {MODEL_DIGEST}; refusing to run"
            )

    surface = HML_SPEC

    def one(tid: str) -> tuple[str, dict[str, Any] | None, str | None]:
        try:
            task = by_id[tid]
            if arm is Arm.SE:
                rec = _run_se_task(task, adapter)
            else:
                rec = _run_hml_task(task, adapter, surface)
            return tid, rec, None
        except Exception as e:  # noqa: BLE001 — recorded, then re-raised by the caller
            return tid, None, f"{type(e).__name__}: {e}"

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for tid, rec, err in pool.map(one, pending):
            if err is not None:
                prog.failed += 1
                prog.errors.append(f"{tid}: {err}")
                prog.write(paths)
                print(f"[{arm}] FAILED {tid}: {err}", file=sys.stderr, flush=True)
                continue
            assert rec is not None
            path = paths.record(tid, str(arm))
            if path.exists():
                # Write-once. A concurrent or resumed writer must never clobber a record.
                print(f"[{arm}] refusing to overwrite {path.name}", file=sys.stderr)
                continue
            rec["manifest_run_id"] = paths.run_id
            rec["protocol"] = PROTOCOL
            rec["written_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            path.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
            prog.done += 1
            prog.write(paths)
            _heartbeat(paths, str(arm), f"recorded {tid}", prog.done, prog.total)
            print(
                f"[{arm}] {prog.done}/{prog.total} {tid} "
                f"correct={rec['answer_correct']} "
                f"tok={rec['completion_tokens']} {rec['latency_s']:.1f}s",
                flush=True,
            )

    print(
        f"[{arm}] finished: {prog.done}/{prog.total} recorded, {prog.failed} failed, "
        f"wall={time.time() - t0:.1f}s",
        flush=True,
    )
    if prog.failed:
        raise RuntimeError(
            f"{prog.failed} task(s) failed in arm {arm}: {prog.errors}. "
            "Resume after resolving; recorded tasks will not be repeated."
        )
    return prog


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="V1 benchmark driver (developmental v1.2)")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arm", choices=["SE", "HML-V1"])
    ap.add_argument("--tasks", nargs="*", default=None, help="restrict to these task ids")
    ap.add_argument("--note", default="")
    ap.add_argument("--workers", type=int, default=NUM_PARALLEL)
    ap.add_argument("--init-only", action="store_true")
    ap.add_argument(
        "--include-excluded",
        action="store_true",
        help="run tasks excluded for a documented pre-run defect (probe use only)",
    )
    args = ap.parse_args(argv)

    paths = RunPaths(args.run_id)
    paths.ensure()
    all_tasks = build_tasks()
    order = [t.id for t in all_tasks]
    if not args.include_excluded:
        dropped = [t for t in order if t in EXCLUDED_TASKS]
        order = [t for t in order if t not in EXCLUDED_TASKS]
        for d in dropped:
            print(f"EXCLUDED (pre-run defect) {d}: {EXCLUDED_TASKS[d]}", file=sys.stderr)
    if args.tasks:
        order = [t for t in order if t in set(args.tasks)]
    build_manifest(paths, task_ids=order, note=args.note)

    if args.init_only:
        print(json.dumps(json.loads(paths.manifest.read_text()), indent=2))
        return 0
    if not args.arm:
        print("--arm is required unless --init-only", file=sys.stderr)
        return 2

    try:
        run_arm(paths, Arm(args.arm), task_ids=args.tasks, workers=args.workers)
    except Exception:
        traceback.print_exc()
        _heartbeat(paths, args.arm, "HALTED", -1, -1)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
