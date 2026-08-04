"""Model-evaluation harness — HML-EVAL-001 §6, §7.

Runs matched arms against one model and records everything needed to audit a result.

Design commitments:

* **Resumable.** Every trial is appended to a JSONL as it completes. A run that is
  interrupted after 9 hours must not lose 9 hours.
* **Arm order randomised** per (problem, generation), so drift in machine state cannot
  align with an arm.
* **Compute matched.** Identical model, temperature, top-p, max tokens and attempt count
  across arms. The one deliberate exception is arm E's repair loop, which is the
  experimental condition under test; its extra calls are counted and reported separately.
* **Nothing is scored by a model.** Answer checking is deterministic; encoding comparison
  is done by the compiler.

Usage::

    .venv/bin/python -m evaluation.harness --problems 12 --generations 3
    .venv/bin/python -m evaluation.harness --resume   # continue an interrupted run
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from hamiltonian_lang import __version__ as hml_version
from hamiltonian_lang import compile_source

from .corpus.cso import CanonicalSemanticObject, check_answer
from .corpus.generators import build_all, build_demos
from .corpus.renderers import ARMS, INFORMATION_ASYMMETRY, render_arm
from .model_client import ModelClient, ModelConfig
from .semantic_equiv import classify, compare_semantics, extract_block

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "evaluation" / "results"
RUNS = RESULTS / "runs"

#: Arms whose output contains a formal encoding we can parse and compare.
FORMAL_ARMS = {"C", "D", "E", "F"}
#: Arms whose encoding is Hamiltonian and can therefore be compared to the CSO.
HML_ARMS = {"D", "E", "F"}

MAX_REPAIRS = 2


@dataclass
class Trial:
    run_id: str
    problem_id: str
    domain: str
    difficulty: str
    arm: str
    generation: int

    model: str = ""
    model_digest: str | None = None
    sampling: dict = field(default_factory=dict)

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_chars: int = 0
    latency_s: float = 0.0
    repair_calls: int = 0
    total_calls: int = 1

    raw_output: str = ""
    raw_reasoning: str = ""
    extracted_answer: str = ""
    answer_correct: bool = False
    answer_marker_present: bool = False

    encoding_present: bool = False
    encoding_text: str = ""
    parse_success: bool | None = None
    diagnostics: list[str] = field(default_factory=list)
    semantic_score: float | None = None
    semantic_exact: bool | None = None
    semantic_detail: dict = field(default_factory=dict)

    failure_class: str = ""
    error: str | None = None
    wall_clock_utc: str = ""

    def key(self) -> str:
        return f"{self.problem_id}|{self.arm}|{self.generation}"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _demo_pairs(arm: str) -> list[tuple[str, str]]:
    """Worked demonstrations rendered in the arm's own notation.

    Every arm receives the same two problems. Giving demonstrations only to the
    Hamiltonian arms would measure demonstrations, not representation.
    """
    d1, d2 = build_demos()
    if arm in ("D", "E"):
        return [
            (d1.prose, f"```hml\n{d1.reference_hml}```\nThe role d fills is the scale."),
            (d2.prose, f"```hml\n{d2.reference_hml}```\n"
                       f"The dimension is Mass * Length / Time."),
        ]
    if arm == "F":
        return [
            (d1.prose,
             "```triples\nR -> has_type RandomVariable[Real]\nR -> declared_as rv\n"
             "c -> has_type Real\nd -> has_type PositiveReal\nlaw0 -> family Normal\n"
             "law0 -> role:location c\nlaw0 -> role:scale d\nR -> has_law:law law0\n```\n"
             "The role d fills is the scale."),
            (d2.prose,
             "```triples\nm -> has_type Quantity[Mass]\n"
             "v -> has_type Quantity[Length / Time]\np -> depends_on m\n"
             "p -> depends_on v\n```\nThe dimension is Mass * Length / Time."),
        ]
    if arm == "C":
        return [
            (d1.prose,
             "```stan\nparameters { real c; real<lower=0> d; }\n"
             "model { R ~ normal(c, d); }\n```\nThe role d fills is the scale."),
            (d2.prose,
             "```stan\n// dimensional reasoning is not expressible in Stan's type system\n"
             "```\nThe dimension is Mass * Length / Time."),
        ]
    if arm == "B":
        return [
            (d1.prose, r"$R \sim \mathcal{N}(c, d)$ with $d > 0$. "
                       "The role $d$ fills is the scale."),
            (d2.prose, r"$[p] = [m][v] = \mathrm{Mass} \cdot \mathrm{Length}/\mathrm{Time}$."),
        ]
    if arm == "A_prime":
        return [
            (d1.prose,
             "1. Objects: R a random variable on the reals; c a real; d a positive real.\n"
             "2. c and d are parameters; R is the modelled quantity; d > 0 is a constraint.\n"
             "3. No quantifiers are present.\n4. Identify the normal family.\n"
             "5. A standard deviation is by definition the scale parameter.\n"
             "6. d > 0 is required by the family.\n7. No extra assumptions used.\n"
             "8. Checked against the statement.\nThe role d fills is the scale."),
            (d2.prose,
             "1. Objects: m a mass; v a speed.\n2. Both are given; none is unknown.\n"
             "3. No quantifiers.\n4. Multiply the dimensions.\n"
             "5. Dimensions multiply under multiplication.\n"
             "6. Mass * (Length/Time) = Mass * Length / Time.\n7. None.\n8. Checked.\n"
             "The dimension is Mass * Length / Time."),
        ]
    return [
        (d1.prose, "A standard deviation is the scale parameter, so d fills the scale."),
        (d2.prose, "Multiplying the dimensions gives Mass * Length / Time."),
    ]


def _feedback_prompt(diagnostics: str, previous: str) -> str:
    return (
        "The Hamiltonian Lang compiler rejected your encoding. Its diagnostics are below. "
        "Correct the encoding and give the final answer again.\n\n"
        f"YOUR ENCODING\n```hml\n{previous}\n```\n\nCOMPILER DIAGNOSTICS\n{diagnostics}"
    )


def run_trial(
    client: ModelClient, cso: CanonicalSemanticObject, arm: str, generation: int,
    run_id: str, model_info: dict,
) -> Trial:
    t = Trial(
        run_id=run_id, problem_id=cso.id, domain=cso.domain, difficulty=cso.difficulty,
        arm=arm, generation=generation, model=client.cfg.model,
        model_digest=model_info.get("digest"),
        sampling=client.cfg.sampling_fingerprint(), wall_clock_utc=_now(),
    )
    prompt = render_arm(arm, cso, _demo_pairs(arm))

    comp = client.complete(prompt.system, prompt.user, attempt=generation)
    t.prompt_tokens += comp.prompt_tokens
    t.completion_tokens += comp.completion_tokens
    t.reasoning_chars += len(comp.reasoning)
    t.latency_s += comp.latency_s
    if not comp.ok:
        t.error = comp.error
        t.failure_class = "verifier_failure"
        return t
    t.raw_output = comp.content
    t.raw_reasoning = comp.reasoning

    if arm in HML_ARMS:
        kinds = ("triples",) if arm == "F" else ("hml", "hamiltonian")
    elif arm == "C":
        kinds = ("stan", "lean")
    else:
        kinds = ()
    encoding = extract_block(comp.content, kinds) if kinds else None

    # Arm E only: compiler-feedback repair loop. Extra calls are counted, not hidden.
    if arm == "E" and encoding:
        for _ in range(MAX_REPAIRS):
            r = compile_source(encoding, f"{cso.id}#repair")
            if r.ok():
                break
            t.repair_calls += 1
            t.total_calls += 1
            follow = client.complete(
                prompt.system,
                prompt.user + "\n\n" + _feedback_prompt(r.diagnostics.render(), encoding),
                attempt=generation,
            )
            t.prompt_tokens += follow.prompt_tokens
            t.completion_tokens += follow.completion_tokens
            t.reasoning_chars += len(follow.reasoning)
            t.latency_s += follow.latency_s
            if not follow.ok:
                break
            t.raw_output = follow.content
            new_enc = extract_block(follow.content, ("hml", "hamiltonian"))
            if not new_enc:
                break
            encoding = new_enc

    t.answer_marker_present = "<ANSWER>" in (t.raw_output or "")
    correct, extracted = check_answer(cso.answer, t.raw_output)
    t.answer_correct, t.extracted_answer = correct, extracted

    t.encoding_present = bool(encoding)
    t.encoding_text = (encoding or "")[:4000]

    comparison = None
    if arm in HML_ARMS and encoding and arm != "F":
        comparison = compare_semantics(cso, encoding)
        t.parse_success = comparison.parsed
        t.diagnostics = comparison.diagnostics
        t.semantic_score = comparison.score()
        t.semantic_exact = comparison.exact()
        t.semantic_detail = comparison.to_dict()
    elif arm == "C" and encoding:
        # Stan/Lean are not parsed by our compiler; parse success is not defined for
        # this arm and is recorded as None rather than as a free pass.
        t.parse_success = None

    t.failure_class = classify(
        answer_correct=correct,
        formal_arm=arm in FORMAL_ARMS,
        encoding_present=bool(encoding),
        comparison=comparison,
        completion_ok=True,
    )
    return t


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HML-EVAL-001 model harness")
    ap.add_argument("--problems", type=int, default=0,
                    help="number of problems to run (0 = all 120)")
    ap.add_argument("--generations", type=int, default=3)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--model", default=os.environ.get("HML_EVAL_MODEL", "gemma4:31b"))
    ap.add_argument("--base-url", default=os.environ.get(
        "HML_EVAL_BASE_URL", "http://localhost:11434/v1"))
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=2400)
    ap.add_argument("--run-id", default=time.strftime("run-%Y%m%d-%H%M%S"))
    ap.add_argument("--stratify", action="store_true", default=True,
                    help="sample evenly across the five categories")
    ap.add_argument("--seed", type=int, default=20260804)
    ap.add_argument("--time-budget-min", type=float, default=0.0,
                    help="stop cleanly after this many minutes (0 = no limit)")
    args = ap.parse_args(argv)

    arms = [a for a in args.arms.split(",") if a]
    cfg = ModelConfig(base_url=args.base_url, model=args.model,
                      temperature=args.temperature, max_tokens=args.max_tokens)
    client = ModelClient(cfg)
    model_info = client.describe()

    corpus = build_all()
    rng = random.Random(args.seed)
    if args.problems and args.problems < len(corpus):
        if args.stratify:
            by_cat: dict[str, list] = {}
            for c in corpus:
                by_cat.setdefault(c.domain, []).append(c)
            per = max(1, args.problems // len(by_cat))
            chosen: list = []
            for cat in sorted(by_cat):
                pool = list(by_cat[cat])
                rng.shuffle(pool)
                chosen.extend(pool[:per])
            rng.shuffle(chosen)
            corpus = chosen[: args.problems]
        else:
            rng.shuffle(corpus)
            corpus = corpus[: args.problems]

    RUNS.mkdir(parents=True, exist_ok=True)
    out_path = RUNS / f"{args.run_id}.jsonl"
    meta_path = RUNS / f"{args.run_id}.meta.json"

    done: set[str] = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            if line.strip():
                try:
                    done.add(json.loads(line)["_key"])
                except Exception:  # noqa: BLE001
                    pass

    meta = {
        "run_id": args.run_id,
        "started_utc": _now(),
        "hamiltonian_lang_version": hml_version,
        "git_commit": os.popen("git rev-parse HEAD").read().strip(),
        "git_tag": os.popen("git describe --tags --always").read().strip(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "model_info": model_info,
        "sampling": cfg.sampling_fingerprint(),
        "arms": arms,
        "generations": args.generations,
        "problems": [c.id for c in corpus],
        "n_problems": len(corpus),
        "planned_calls": len(corpus) * len(arms) * args.generations,
        "max_repairs_arm_E": MAX_REPAIRS,
        "information_asymmetry": INFORMATION_ASYMMETRY,
        "scoring": "deterministic; no model judges any output",
        "seed": args.seed,
        "time_budget_min": args.time_budget_min,
    }
    meta_path.write_text(json.dumps(meta, indent=2))

    # Randomise arm order per (problem, generation) so machine drift cannot align with
    # an arm. The seed makes the shuffle reproducible.
    jobs: list[tuple[CanonicalSemanticObject, str, int]] = []
    for gen in range(args.generations):
        for cso in corpus:
            order = list(arms)
            random.Random(f"{args.seed}|{cso.id}|{gen}").shuffle(order)
            for arm in order:
                jobs.append((cso, arm, gen))

    t_start = time.time()
    completed = skipped = 0
    with out_path.open("a") as fh:
        for cso, arm, gen in jobs:
            key = f"{cso.id}|{arm}|{gen}"
            if key in done:
                skipped += 1
                continue
            if args.time_budget_min and (time.time() - t_start) / 60 > args.time_budget_min:
                print(f"[budget] stopping cleanly after {completed} trials", flush=True)
                break
            trial = run_trial(client, cso, arm, gen, args.run_id, model_info)
            rec = asdict(trial)
            rec["_key"] = key
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            completed += 1
            print(
                f"[{completed:4d}/{len(jobs)-skipped}] {cso.id:34s} arm={arm:7s} g={gen} "
                f"ans={'OK ' if trial.answer_correct else 'no '} "
                f"cls={trial.failure_class:28s} {trial.latency_s:5.1f}s",
                flush=True,
            )

    print(f"\nrun {args.run_id}: {completed} new trials, {skipped} resumed-skipped")
    print(f"records: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
