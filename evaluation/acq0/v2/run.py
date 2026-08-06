"""Tranche A: the first valid ACQ0 acquisition run. One record per condition, nothing lost.

Scoring is mechanical. The headline metric is **content-hash equality** between the
model's encoding, imported to HML-L1, and the reference. No LLM judge is used for semantic
preservation, and none may be: a judge that is wrong in the direction of the hypothesis is
indistinguishable from a result.

Repair is permitted **once**, and the feedback is the compiler's own diagnostics **on the
model's own output**. That is safe by construction — the compiler never sees the reference,
so it cannot leak it. `acq0_semantic_diff` is deliberately NOT used for repair: it is
computed against the intended encoding, and feeding it back would convert a repair
measurement into transcription (v2_firewall states the same rule for H3).

Attempt zero is written once and never overwritten. A run that loses its first attempt
cannot distinguish "the model got it right" from "the model got it right the second time".
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from evaluation.corpus_governance.v2_render import SUPPORTED_SURFACES
from evaluation.syntax_gate.candidates import resolve_adapters

from .prompt import build_prompt, prompt_hash

__all__ = ["ConditionRecord", "run_condition", "run_tranche", "RESULTS",
           "CONTINUATION_GATE", "FINAL_GATE", "gate_verdict"]

RESULTS = Path(__file__).resolve().parents[3] / "evaluation" / "results" / "acq0" / "v2_tranche_a"

#: After the first eight tasks, a surface stays viable only if it can still reach the final
#: gate. Stated before the run, not chosen after it.
CONTINUATION_GATE = {"repaired_parse": 6, "exact_semantic": 5, "constitutional": 0,
                     "of": 8}
FINAL_GATE = {"repaired_parse": 10, "exact_semantic": 9, "constitutional": 0, "of": 12}


@dataclass
class ConditionRecord:
    """Everything about one (task, surface) condition. Written once."""

    task_id: str
    surface: str
    model: str
    model_digest: str

    prompt: str = ""
    prompt_sha256: str = ""

    # --- attempt zero: never overwritten -------------------------------------------
    raw_attempt_zero: str = ""
    finish_reason: str = ""
    truncated: bool = False
    transport_error: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0

    imported_hml: str = ""
    import_ok: bool = False
    import_diagnostics: list[str] = field(default_factory=list)

    parse_ok: bool = False
    resolution_ok: bool = False
    type_ok: bool = False
    compiler_diagnostics: list[str] = field(default_factory=list)
    obligation_status: str = "NOT_RUN"

    content_hash: str = ""
    semantic_preservation_exact: bool = False
    constitutional_failures: list[str] = field(default_factory=list)

    # --- repair: at most one, fed only by the model's own diagnostics ----------------
    repair_eligible: bool = False
    safe_diagnostic: str = ""
    repair_raw: str = ""
    repair_finish_reason: str = ""
    repair_truncated: bool = False
    repair_prompt_tokens: int = 0
    repair_completion_tokens: int = 0
    repair_latency_s: float = 0.0
    repaired_parse_ok: bool = False
    repaired_semantic_exact: bool = False

    captured_utc: str = ""

    @property
    def final_parse_ok(self) -> bool:
        return self.parse_ok or self.repaired_parse_ok

    @property
    def final_semantic_exact(self) -> bool:
        return self.semantic_preservation_exact or self.repaired_semantic_exact


def _safe_diagnostic(record: ConditionRecord) -> str:
    """Feedback derived ONLY from the model's own output.

    The compiler is run on the submission; it has never seen the reference, so nothing it
    says can carry the answer. Diagnostics are truncated to codes and messages -- a
    diagnostic that quoted a *reference* span would be a leak, and none can, because no
    reference span exists in this compilation.
    """
    codes = record.import_diagnostics or record.compiler_diagnostics
    if not codes:
        return ""
    return ("Your encoding was rejected. The compiler reported:\n"
            + "\n".join(f"  - {c}" for c in codes[:8])
            + "\nRe-emit the SAME mathematical object, corrected. Do not add, remove or "
              "change any statement. Output only the encoding.")


def _constitutional_failures(record: ConditionRecord, task) -> list[str]:
    """Failures that invalidate the condition rather than merely scoring it badly."""
    out: list[str] = []
    if record.transport_error:
        out.append(f"transport: {record.transport_error}")
    if record.truncated:
        out.append("attempt zero hit the completion cap; the answer was cut off, so this "
                   "measures the budget, not the surface")
    if record.repair_raw and record.repair_truncated:
        out.append("the repair hit the completion cap")
    if not record.raw_attempt_zero.strip() and not record.transport_error:
        out.append("empty completion with no transport error")
    return out


def strip_fence(text: str, surface: str) -> str:
    """Remove a surrounding markdown code fence before importing.

    Found on the first run and it would have been fatal. The candidate-C specification
    advertises the fence tags `sexpr`, `lisp` and `scheme`; the model used ```lisp, wrote a
    **hash-identical** encoding inside it, and the raw text was handed to the importer
    fence and all. Surface C would have been eliminated on a harness defect, and the
    elimination would have been reported as a property of the notation.

    Any fence is accepted, not only the advertised tags: refusing an unadvertised tag
    measures instruction-following, which is a different experiment.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    body = stripped[3:]
    newline = body.find("\n")
    if newline == -1:
        return text
    body = body[newline + 1:]
    close = body.rfind("```")
    return body[:close] if close != -1 else body


def _evaluate(text: str, surface: str, task) -> dict[str, Any]:
    """Import one surface answer and score it mechanically."""
    from hamiltonian_lang import compile_source, content_hash

    text = strip_fence(text, surface)
    adapters = resolve_adapters()
    adapter = adapters[surface]
    out: dict[str, Any] = {"imported_hml": "", "import_ok": False,
                           "import_diagnostics": [], "parse_ok": False,
                           "resolution_ok": False, "type_ok": False,
                           "compiler_diagnostics": [], "content_hash": "",
                           "exact": False, "obligation_status": "NOT_RUN"}
    try:
        outcome = adapter.parse(text)
    except Exception as exc:  # noqa: BLE001 - a crashing import is a datum, not a stop
        out["import_diagnostics"] = [f"{type(exc).__name__}: {exc}"]
        return out
    out["import_ok"] = bool(outcome.ok)
    out["import_diagnostics"] = [str(d) for d in (outcome.diagnostics or [])]
    if not outcome.ok:
        return out
    out["imported_hml"] = outcome.hml_l1

    result = compile_source(outcome.hml_l1, f"<{task.task_id}:{surface}>")
    codes = [d.code for d in result.diagnostics.errors]
    out["compiler_diagnostics"] = codes
    out["parse_ok"] = not any(c.startswith(("HML-L", "HML-P")) for c in codes)
    out["resolution_ok"] = out["parse_ok"] and not any(c.startswith("HML-N") for c in codes)
    out["type_ok"] = result.ok()
    if result.ok():
        out["content_hash"] = content_hash(outcome.hml_l1)
        out["exact"] = out["content_hash"] == task.canonical_hash()
        obligations = getattr(result, "obligations", None)
        out["obligation_status"] = (
            f"{len(obligations)} collected" if obligations else "none collected")
    return out


def run_condition(task, surface: str, adapter, *, allow_repair: bool = True
                  ) -> ConditionRecord:
    """One (task, surface) condition, attempt zero plus at most one safe repair."""
    prompt = build_prompt(task, surface)
    record = ConditionRecord(
        task_id=task.task_id, surface=surface,
        model=getattr(adapter.cfg, "model", "unknown"),
        model_digest=getattr(adapter, "digest", ""),
        prompt=prompt, prompt_sha256=prompt_hash(prompt),
        captured_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    gen = adapter.generate("", prompt)
    record.raw_attempt_zero = gen.content
    record.finish_reason = gen.finish_reason
    record.truncated = gen.finish_reason == "length"
    record.transport_error = gen.error or ""
    record.prompt_tokens = gen.prompt_tokens
    record.completion_tokens = gen.completion_tokens
    record.latency_s = gen.latency_s

    scored = _evaluate(gen.content, surface, task)
    record.imported_hml = scored["imported_hml"]
    record.import_ok = scored["import_ok"]
    record.import_diagnostics = scored["import_diagnostics"]
    record.parse_ok = scored["parse_ok"]
    record.resolution_ok = scored["resolution_ok"]
    record.type_ok = scored["type_ok"]
    record.compiler_diagnostics = scored["compiler_diagnostics"]
    record.content_hash = scored["content_hash"]
    record.obligation_status = scored["obligation_status"]
    record.semantic_preservation_exact = scored["exact"]

    record.repair_eligible = (
        allow_repair and not record.semantic_preservation_exact
        and not record.truncated and not record.transport_error
        and bool(record.raw_attempt_zero.strip()))

    if record.repair_eligible:
        record.safe_diagnostic = _safe_diagnostic(record)
        if record.safe_diagnostic:
            repair_prompt = (f"{prompt}\n\n=== YOUR PREVIOUS ANSWER ===\n"
                             f"{record.raw_attempt_zero}\n\n"
                             f"=== COMPILER FEEDBACK ===\n{record.safe_diagnostic}\n")
            rgen = adapter.generate("", repair_prompt)
            record.repair_raw = rgen.content
            record.repair_finish_reason = rgen.finish_reason
            record.repair_truncated = rgen.finish_reason == "length"
            record.repair_prompt_tokens = rgen.prompt_tokens
            record.repair_completion_tokens = rgen.completion_tokens
            record.repair_latency_s = rgen.latency_s
            rescored = _evaluate(rgen.content, surface, task)
            record.repaired_parse_ok = rescored["parse_ok"]
            record.repaired_semantic_exact = rescored["exact"]

    record.constitutional_failures = _constitutional_failures(record, task)
    return record


def run_tranche(tasks, surfaces=SUPPORTED_SURFACES, *, adapter, out_dir: Path | None = None
                ) -> list[ConditionRecord]:
    """Every (task, surface) condition. Records are written as they complete."""
    out_dir = out_dir or RESULTS
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[ConditionRecord] = []
    for task in tasks:
        for surface in surfaces:
            record = run_condition(task, surface, adapter)
            records.append(record)
            path = out_dir / f"{task.task_id}__{surface}.json"
            if not path.exists():  # attempt zero is never overwritten
                path.write_text(json.dumps(asdict(record), indent=2, ensure_ascii=False))
    return records


def gate_verdict(records: list[ConditionRecord], surface: str, gate: dict) -> dict[str, Any]:
    """Apply a preregistered gate to one surface. No post-hoc thresholds."""
    mine = [r for r in records if r.surface == surface]
    parse = sum(r.final_parse_ok for r in mine)
    exact = sum(r.final_semantic_exact for r in mine)
    constitutional = sum(bool(r.constitutional_failures) for r in mine)
    first_parse = sum(r.parse_ok for r in mine)
    first_exact = sum(r.semantic_preservation_exact for r in mine)
    return {
        "surface": surface, "n": len(mine),
        "repaired_parse": parse, "exact_semantic": exact,
        "first_pass_parse": first_parse, "first_pass_exact": first_exact,
        "constitutional_failures": constitutional,
        "tokens": sum(r.prompt_tokens + r.completion_tokens for r in mine),
        "latency_s": round(sum(r.latency_s + r.repair_latency_s for r in mine), 1),
        "viable": (parse >= gate["repaired_parse"] and exact >= gate["exact_semantic"]
                   and constitutional == gate["constitutional"]),
    }
