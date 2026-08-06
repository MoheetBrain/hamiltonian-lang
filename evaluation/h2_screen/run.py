"""Execute the H2 headroom screen. Unattended; one immutable record per (problem, seed)."""
from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from evaluation.corpus.cso import AnswerSpec, check_answer  # noqa: E402
from evaluation.h2_screen.screen import (  # noqa: E402
    MAX_TOKENS,
    OUT,
    SEEDS,
    TEMPERATURE,
    build_manifest,
    eligible,
    load_corpus,
    prompt_parts,
    sha,
)
from evaluation.model_adapters.ollama import OllamaAdapter, OllamaConfig  # noqa: E402


def spec_of(answer: dict) -> AnswerSpec:
    return AnswerSpec(kind=answer["kind"], value=answer.get("value"),
                      options=list(answer.get("options") or []),
                      tolerance=answer.get("tolerance", 1e-6))


def run(pids: list[str], out_dir: pathlib.Path, adapter) -> list[dict]:
    problems = load_corpus()
    records = []
    for pid in pids:
        system, user = prompt_parts(pid)
        answer = problems[pid]["answer"]
        for seed in SEEDS:
            path = out_dir / f"{pid}__seed{seed}.json"
            if path.exists():
                records.append(json.loads(path.read_text()))
                continue
            adapter.cfg = OllamaConfig(model=adapter.cfg.model, temperature=TEMPERATURE,
                                       max_tokens=MAX_TOKENS, seed=seed, timeout_s=900)
            t0 = time.time()
            gen = adapter.generate(system, user, force=True)
            try:
                correct, extracted = check_answer(spec_of(answer), gen.content)
                failure = ""
            except Exception as exc:  # noqa: BLE001 - a scorer crash is a datum
                correct, extracted, failure = False, "", f"{type(exc).__name__}: {exc}"
            rec = {
                "task_id": pid, "domain": problems[pid]["domain"],
                "difficulty": problems[pid]["difficulty"],
                "answer_kind": answer["kind"], "seed": seed,
                "prompt_sha256": sha(system + user), "model_digest": adapter.digest,
                "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
                "raw_response": gen.content, "finish_reason": gen.finish_reason,
                "truncated": gen.finish_reason == "length",
                "transport_error": gen.error or "",
                "prompt_tokens": gen.prompt_tokens,
                "completion_tokens": gen.completion_tokens,
                "latency_s": round(time.time() - t0, 2),
                "extracted_answer": extracted, "correct": bool(correct),
                "scoring_failure": failure,
            }
            path.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
            records.append(rec)
            print(f"{len(records):4d}/{len(pids)*len(SEEDS)} {pid[:28]:28s} s{seed} "
                  f"{'OK ' if correct else 'no '} fin={gen.finish_reason} "
                  f"ct={gen.completion_tokens} {rec['latency_s']:.0f}s", flush=True)
    return records


def main(limit: int | None = None, tag: str = "") -> int:
    pids, excluded = eligible(load_corpus())
    if limit:
        seen, pick = set(), []
        for p in pids:  # one per domain, distinct domains for the dry run
            d = load_corpus()[p]["domain"]
            if d not in seen:
                seen.add(d); pick.append(p)
            if len(pick) == limit: break
        pids = pick
    out_dir = OUT / (tag or "full")
    if out_dir.exists() and any(out_dir.glob("*.json")) and not limit:
        sys.exit(f"REFUSING: {out_dir} already holds records")
    out_dir.mkdir(parents=True, exist_ok=True)
    adapter = OllamaAdapter(OllamaConfig(model="gemma4:31b", temperature=TEMPERATURE,
                                         max_tokens=MAX_TOKENS, timeout_s=900))
    manifest = build_manifest(pids, excluded, adapter.digest)
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"digest {adapter.digest[:24]} | {len(pids)} problems x {len(SEEDS)} seeds "
          f"= {len(pids)*len(SEEDS)} calls | T={TEMPERATURE} max_tokens={MAX_TOKENS}",
          flush=True)
    t0 = time.time()
    run(pids, out_dir, adapter)
    print(f"\nDONE in {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(n, "dry_run" if n else "")
