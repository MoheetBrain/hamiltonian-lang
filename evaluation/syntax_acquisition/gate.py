"""The offline round-trip gate.

Renders every generated object in all four surfaces, reads each rendering back, runs the
shared resolver and type checker over it, and compares the canonical content hash. A
candidate that cannot reach 100% on the frozen subset does not enter the model
tournament; that is a legitimate outcome and is reported as a number, not a narrative.

The matrix is |corpus| x 4 independent checks with no shared state, so it runs on a
process pool. On this machine (18 physical cores) that is the difference between a gate
you run and a gate you skip.

Run it directly::

    .venv/bin/python -m evaluation.syntax_acquisition.gate --workers 18 --report
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field

from .core import CANDIDATES, declared_content, round_trip
from .generator import MIN_CORPUS_SIZE, build_corpus, coverage_report

__all__ = ["GateResult", "run_gate", "main", "DEFAULT_WORKERS"]

DEFAULT_WORKERS = 18


@dataclass
class GateResult:
    corpus_size: int
    rejected_sources: int
    per_candidate: dict[str, dict[str, int]] = field(default_factory=dict)
    failures: list[dict] = field(default_factory=list)
    parity_failures: list[dict] = field(default_factory=list)
    render_bytes: dict[str, int] = field(default_factory=dict)
    #: Time for the |corpus| x 4 matrix only, excluding the parent's corpus build.
    wall_seconds: float = 0.0
    #: Time to generate and compile the corpus in the parent process. Each spawned
    #: worker repeats this, which is why the pool's speedup is bounded well below the
    #: core count at this corpus size.
    corpus_seconds: float = 0.0
    workers: int = 0
    coverage: dict[str, dict[str, int]] = field(default_factory=dict)

    def all_passed(self) -> bool:
        return (
            not self.failures
            and not self.parity_failures
            and self.corpus_size >= MIN_CORPUS_SIZE
            and all(
                stats["passed"] == stats["total"] for stats in self.per_candidate.values()
            )
        )

    def to_dict(self) -> dict:
        return {
            "corpus_size": self.corpus_size,
            "rejected_sources": self.rejected_sources,
            "per_candidate": self.per_candidate,
            "failures": self.failures[:50],
            "parity_failures": self.parity_failures[:50],
            "render_bytes": self.render_bytes,
            "wall_seconds": round(self.wall_seconds, 3),
            "corpus_seconds": round(self.corpus_seconds, 3),
            "workers": self.workers,
            "coverage": self.coverage,
        }


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


def _check_one(index: int) -> dict:
    """Round-trip one object through all four surfaces, plus the parity comparison.

    Takes an index rather than an object because a compiled ``Module`` is not worth
    pickling across a process boundary: each worker builds the corpus once, from the
    same deterministic generator, and indexes into it.
    """
    objects, _ = build_corpus()
    obj = objects[index]
    row: dict = {"id": obj.id, "family": obj.family, "results": {}, "bytes": {}}
    parity: dict[str, str] = {}
    for cid, cand in sorted(CANDIDATES.items()):
        outcome = round_trip(cand, obj.module, obj.id)
        row["results"][cid] = {
            "ok": outcome.ok,
            "stage": outcome.stage,
            "detail": outcome.detail[:400],
        }
        row["bytes"][cid] = outcome.render_bytes
        if outcome.ok:
            parity[cid] = declared_content(cand.parse(outcome.rendered))
    if len(parity) == 4 and len(set(parity.values())) != 1:
        row["parity"] = {
            "id": obj.id,
            "distinct": len(set(parity.values())),
            "digests": {cid: hash(text) for cid, text in parity.items()},
        }
    return row


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def run_gate(workers: int = DEFAULT_WORKERS, *, with_coverage: bool = True) -> GateResult:
    corpus_started = time.perf_counter()
    objects, rejected = build_corpus()
    corpus_seconds = time.perf_counter() - corpus_started
    total = len(objects)
    result = GateResult(corpus_size=total, rejected_sources=len(rejected), workers=workers)
    result.corpus_seconds = corpus_seconds
    per: dict[str, Counter] = {cid: Counter() for cid in sorted(CANDIDATES)}
    byte_totals: Counter = Counter()

    started = time.perf_counter()
    if workers <= 1:
        rows = [_check_one(i) for i in range(total)]
    else:
        chunk = max(1, total // (workers * 4))
        with ProcessPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(_check_one, range(total), chunksize=chunk))
    result.wall_seconds = time.perf_counter() - started

    for row in rows:
        for cid, outcome in row["results"].items():
            per[cid]["total"] += 1
            if outcome["ok"]:
                per[cid]["passed"] += 1
            else:
                per[cid][f"stage:{outcome['stage']}"] += 1
                result.failures.append(
                    {
                        "id": row["id"],
                        "family": row["family"],
                        "candidate": cid,
                        "stage": outcome["stage"],
                        "detail": outcome["detail"],
                    }
                )
        for cid, n in row["bytes"].items():
            byte_totals[cid] += n
        if "parity" in row:
            result.parity_failures.append(row["parity"])

    result.per_candidate = {cid: dict(counter) for cid, counter in per.items()}
    result.render_bytes = dict(byte_totals)
    if with_coverage:
        result.coverage = coverage_report()
    return result


def format_table(result: GateResult) -> str:
    lines = [
        f"{'candidate':<12}{'name':<36}{'passed':>10}{'total':>8}{'rate':>9}",
        "-" * 75,
    ]
    for cid in sorted(result.per_candidate):
        stats = result.per_candidate[cid]
        passed, total = stats.get("passed", 0), stats.get("total", 0)
        rate = f"{100.0 * passed / total:.1f}%" if total else "n/a"
        lines.append(f"{cid:<12}{CANDIDATES[cid].name:<36}{passed:>10}{total:>8}{rate:>9}")
    lines.append("-" * 75)
    lines.append(
        f"corpus {result.corpus_size} objects (built in {result.corpus_seconds:.2f}s)  |  "
        f"{result.workers} worker(s)  |  matrix {result.wall_seconds:.2f}s wall"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HML-PHASE-FG-001 F3 offline round-trip gate")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--json", type=str, default="", help="write the full result here")
    parser.add_argument("--report", action="store_true", help="print the per-candidate table")
    args = parser.parse_args(argv)

    result = run_gate(args.workers)
    if args.report or not args.json:
        print(format_table(result))
        if result.failures:
            print(f"\n{len(result.failures)} failing cell(s); first 10:")
            for f in result.failures[:10]:
                print(f"  {f['candidate']} {f['id']} [{f['stage']}] {f['detail'][:160]}")
        if result.parity_failures:
            print(f"\n{len(result.parity_failures)} information-parity failure(s)")
    if args.json:
        path = os.path.abspath(args.json)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="ascii") as fh:
            json.dump(result.to_dict(), fh, indent=2, sort_keys=True)
        print(f"wrote {path}")
    return 0 if result.all_passed() else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
