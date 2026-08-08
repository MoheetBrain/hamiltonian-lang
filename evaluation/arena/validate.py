"""The pre-flight gate. **Run this to completion before any model call.**

The synthetic calibration earned its credibility by validating the generator before
spending a single call, and by recording the gate's output alongside the results. The
same rule applies here, with more at stake: the arena's whole claim rests on the arms
being information-matched, and that is a property of the code, checkable offline, for
free. Discovering a parity defect after a paid run would invalidate the run, not the
defect.

Nine checks, all offline:

1. determinism -- rebuilding the corpus yields byte-identical prompts;
2. parity -- every world round-trips through every arm to the same canonical form;
3. HML validity -- every HML rendering compiles under the real compiler;
4. no duplicate prompts within an arm;
5. answer distribution is non-degenerate, so a constant answer cannot score well;
6. contrast pairs are answer-balanced, which is what makes both-correct meaningful;
7. seeds are disjoint from the calibration band;
8. the scorer's own behaviour, including its refusal to grade a truncated response;
9. the token budget per arm, recorded so a length effect stays visible.

Exit code is non-zero if any check fails. A failed gate means no run.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from .budget import budget_table
from .corpus import build_corpus, prompts_for
from .parity import ARM_RENDERERS, check_corpus
from .scoring import SCORER_VERSION, score_response
from .worlds import ARENA_SEED_BASE, ARENA_VERSION

__all__ = ["run_gate", "main"]

ARMS = ("SE", "AST", "HML")
CALIBRATION_BAND = 900_000


def _check_determinism(kw) -> dict:
    a, b = build_corpus(**kw), build_corpus(**kw)
    if len(a.items) != len(b.items):
        return {"ok": False, "detail": f"item count differs: {len(a.items)} vs {len(b.items)}"}
    for arm in ARMS:
        if prompts_for(a.items, arm) != prompts_for(b.items, arm):
            return {"ok": False, "detail": f"prompts differ between builds in arm {arm}"}
    return {"ok": True, "n_items": len(a.items)}


def _check_parity(corpus) -> dict:
    worlds = {w.world_id: w for w in (i.world for i in corpus.items)}
    n, bad = check_corpus(worlds.values())
    return {
        "ok": not bad,
        "worlds_checked": n,
        "round_trips": n * len(ARMS),
        "failures": [r.report() for r in bad[:5]],
    }


def _check_hml_compiles(corpus, venv_hml: str) -> dict:
    """Every HML rendering must pass the real compiler, not a syntax approximation."""
    r = ARM_RENDERERS["HML"]
    seen: dict[str, str] = {}
    for i in corpus.items:
        seen.setdefault(i.world.world_id, r.compilable(i.world))
    failures = []
    with tempfile.TemporaryDirectory() as td:
        for wid, src in seen.items():
            p = Path(td) / f"{wid}.hml"
            p.write_text(src)
            out = subprocess.run([venv_hml, "check", str(p)], capture_output=True, text=True)
            if out.returncode != 0:
                failures.append({"world": wid, "stdout": out.stdout[:300]})
    return {"ok": not failures, "compiled": len(seen), "failures": failures[:5]}


def _check_no_duplicates(corpus) -> dict:
    dupes = {}
    for arm in ARMS:
        ps = prompts_for(corpus.items, arm)
        c = Counter(ps)
        n = sum(v - 1 for v in c.values() if v > 1)
        if n:
            dupes[arm] = n
    return {"ok": not dupes, "duplicate_prompts": dupes}


def _check_answer_distribution(corpus) -> dict:
    out = {}
    ok = True
    for ep in ("NEXT_ACTION", "CONTRAST", "CORRUPTION"):
        items = corpus.by_endpoint(ep)
        if not items:
            continue
        c = Counter(i.answer for i in items)
        top = max(c.values()) / len(items)
        out[ep] = {"n": len(items), "distinct_answers": len(c), "modal_share": round(top, 3)}
        # A corpus a constant answer could pass is not measuring anything.
        if top > 0.75:
            ok = False
            out[ep]["problem"] = "a single constant answer would score above 75%"
    return {"ok": ok, "by_endpoint": out}


def _check_pair_balance(corpus) -> dict:
    if not corpus.pairs:
        return {"ok": True, "pairs": 0}
    same = [p for p in corpus.pairs if p[0].answer == p[1].answer]
    return {
        "ok": not same,
        "pairs": len(corpus.pairs),
        "pairs_with_equal_answers": len(same),
    }


def _check_seed_band(corpus) -> dict:
    bad = [i.item_id for i in corpus.items if i.seed >= CALIBRATION_BAND]
    return {
        "ok": not bad,
        "base": ARENA_SEED_BASE,
        "calibration_band": CALIBRATION_BAND,
        "items_in_calibration_band": bad[:5],
    }


def _check_scorer() -> dict:
    space4 = ("A", "B", "C", "D")
    cases = [
        ("plain", "FINAL: B", "B", space4, "stop", True, True),
        ("last wins", "FINAL: A\nwait\nFINAL: C", "C", space4, "stop", True, True),
        ("decorated", "FINAL: **B**.", "B", space4, "stop", True, True),
        ("lowercase", "FINAL: b", "B", space4, "stop", True, True),
        ("wrong", "FINAL: A", "B", space4, "stop", True, False),
        ("missing line", "the answer is B", "B", space4, "stop", True, False),
        ("out of space", "FINAL: Z", "B", space4, "stop", True, False),
        ("prose not matched", "FINAL: B is correct", "B", space4, "stop", True, False),
        ("truncated is not scored", "FINAL: B", "B", space4, "length", False, False),
        ("numeric", "FINAL: -5", "-5", ("an exact integer or fraction",), "stop", True, True),
        ("numeric equal form", "FINAL: 4/2", "2", ("an exact integer or fraction",), "stop", True, True),
        ("closed word", "FINAL: UNDETERMINED", "UNDETERMINED",
         ("TRUE", "FALSE", "UNDETERMINED"), "stop", True, True),
    ]
    failures = []
    for name, resp, exp, space, finish, want_valid, want_correct in cases:
        s = score_response("t", resp, exp, space, finish_reason=finish)
        if s.valid != want_valid or s.correct != want_correct:
            failures.append(
                {"case": name, "got": {"valid": s.valid, "correct": s.correct},
                 "want": {"valid": want_valid, "correct": want_correct}}
            )
    return {"ok": not failures, "cases": len(cases), "failures": failures,
            "scorer_version": SCORER_VERSION}


def run_gate(*, venv_hml: str = ".venv/bin/hml", **corpus_kw) -> dict:
    corpus = build_corpus(**corpus_kw)
    prompts = {arm: prompts_for(corpus.items, arm) for arm in ARMS}

    checks = {
        "determinism": _check_determinism(corpus_kw),
        "parity": _check_parity(corpus),
        "hml_compiles": _check_hml_compiles(corpus, venv_hml),
        "no_duplicate_prompts": _check_no_duplicates(corpus),
        "answer_distribution": _check_answer_distribution(corpus),
        "pair_balance": _check_pair_balance(corpus),
        "seed_band": _check_seed_band(corpus),
        "scorer": _check_scorer(),
    }
    return {
        "arena_version": ARENA_VERSION,
        "scorer_version": SCORER_VERSION,
        "n_items": len(corpus.items),
        "n_pairs": len(corpus.pairs),
        "items_by_endpoint": {
            ep: len(corpus.by_endpoint(ep))
            for ep in ("NEXT_ACTION", "CONTRAST", "CORRUPTION")
        },
        "budget": budget_table(prompts),
        "checks": checks,
        "all_ok": all(c["ok"] for c in checks.values()),
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out = run_gate()
    text = json.dumps(out, indent=2)
    if argv:
        Path(argv[0]).write_text(text + "\n")
    print(text)
    return 0 if out["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
