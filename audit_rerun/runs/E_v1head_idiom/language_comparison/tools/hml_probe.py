"""Behavioural probing of HML: compile real source and record what actually happens.

Static extraction tells you what symbols exist. This tells you what the compiler *does*,
which is the only thing that settles questions like "is `1/x` guarded?" or "does the type
system really keep `Distribution[T]` apart from `T`?".

Isolation: the audit worktree's `src/` is forced to the front of `sys.path`, so every
result here is attributable to the audited SHA rather than to whatever the venv's editable
install happens to point at.

Nothing in this module modifies HML. A probe that fails is a finding, not a bug to fix.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

AUDIT_ROOT = Path(__file__).resolve().parents[3]
# RERUN HARNESS CHANGE (audit_rerun only): the original line was
#     sys.path.insert(0, str(AUDIT_ROOT / "src"))
# which pins the probes to the source tree three levels above tools/.  The rerun must
# execute the SAME probe text against three different source trees (b1ac7bf, 3dd4216,
# f0e3340), so the tree is selected by HML_PROBE_SRC.  Default behaviour is unchanged.
# This affects WHICH compiler is measured, never WHAT is measured.
import os  # noqa: E402
_SRC = os.environ.get("HML_PROBE_SRC") or str(AUDIT_ROOT / "src")
sys.path.insert(0, _SRC)

import hamiltonian_lang as H  # noqa: E402

__all__ = ["Probe", "ProbeResult", "run", "run_all"]


@dataclass
class Probe:
    """One HML snippet and what we expect of it."""

    id: str
    source: str
    #: What the probe is testing, in ontology terms where applicable.
    capability: str
    #: What a language adequate for this capability ought to do.
    expectation: str
    #: "accept" (must compile clean), "reject" (must produce an error diagnostic),
    #: "observe" (no pass/fail; we are recording behaviour).
    mode: str = "observe"
    notes: str = ""
    group: str = ""


@dataclass
class ProbeResult:
    probe: Probe
    compiled: bool
    ok: bool
    codes: list[str]
    rendered: str
    content_hash: str | None
    error: str | None = None
    obligations: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if self.error:
            return "CRASH"
        if self.probe.mode == "accept":
            return "PASS" if self.ok else "FAIL"
        if self.probe.mode == "reject":
            return "PASS" if not self.ok else "FAIL"
        return "OBSERVED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.probe.id,
            "group": self.probe.group,
            "capability": self.probe.capability,
            "mode": self.probe.mode,
            "expectation": self.probe.expectation,
            "source": self.probe.source,
            "compiled": self.compiled,
            "ok": self.ok,
            "codes": self.codes,
            "content_hash": self.content_hash,
            "obligations": self.obligations,
            "verdict": self.verdict,
            "diagnostics": self.rendered[:2000],
            "error": self.error,
            "notes": self.probe.notes,
        }


def run(p: Probe) -> ProbeResult:
    try:
        r = H.compile_source(p.source)
    except Exception as e:  # noqa: BLE001 — a crash is itself a finding
        return ProbeResult(p, False, False, [], "", None, error=f"{type(e).__name__}: {e}")

    codes = list(r.diagnostics.codes())
    try:
        chash = r.hash if isinstance(r.hash, str) else (r.hash() if callable(r.hash) else None)
    except Exception:  # noqa: BLE001
        chash = None
    try:
        obs = [str(o) for o in (r.obligations or [])]
    except Exception:  # noqa: BLE001
        obs = []
    return ProbeResult(
        probe=p,
        compiled=True,
        ok=bool(r.ok()),
        codes=codes,
        rendered=r.diagnostics.render(),
        content_hash=chash,
        obligations=obs,
    )


def run_all(probes: list[Probe]) -> list[ProbeResult]:
    return [run(p) for p in probes]


def summarise(results: list[ProbeResult]) -> dict[str, Any]:
    by_group: dict[str, dict[str, int]] = {}
    for r in results:
        g = by_group.setdefault(r.probe.group or "ungrouped", {})
        g[r.verdict] = g.get(r.verdict, 0) + 1
    return {
        "n": len(results),
        "by_verdict": {
            v: sum(1 for r in results if r.verdict == v)
            for v in ("PASS", "FAIL", "OBSERVED", "CRASH")
        },
        "by_group": by_group,
    }


def emit(results: list[ProbeResult], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "hml_source_sha": _source_sha(),
                "summary": summarise(results),
                "results": [r.to_dict() for r in results],
            },
            indent=2,
        )
    )


def _source_sha() -> str:
    import subprocess

    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=AUDIT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"
