"""The model-facing runner. One call per item, one fresh context per call, nothing shared.

Used for all three model-facing stages -- developmental selection, the acquisition sanity
check, and the representation pilot -- because they must differ only in *which* seeds and
*which* arms are used, never in how a call is made or scored.

**Isolation.** `ModelClient.complete` posts a single `[system, user]` pair per call and
keeps no state, so twins and arms cannot influence each other. This is the property that
makes a contrast pair a real pair: if the two members shared a context, the second would be
answered by a model that had already seen the first, and pair scoring would measure
consistency rather than sensitivity.

**Arms are a parameter, and the developmental screen passes exactly one.** Selecting a
model after seeing how it does on AST or HML would choose the organism *for* the treatment,
which is contamination that no later analysis can undo. `run_screen` therefore refuses to
run a `DEV_SELECTION` band with anything but `("SE",)`.

**Nothing is retried and nothing is repaired.** A truncated response is recorded as invalid
and never scored; a malformed answer is wrong. Both are reported, because a run with
truncations in it is a run whose headroom estimate cannot be trusted.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .bands import assert_band, band_of
from .budget import ENCODING
from .endpoints import contrast
from .endpoints.common import build_prompt
from .parity import ARM_RENDERERS
from .scoring import SCORER_VERSION, pair_score, score_response
from .worlds import ARENA_VERSION

__all__ = ["RunSpec", "SYSTEM_PROMPT", "build_dev_pairs", "run_screen"]

#: Every DEV_SELECTION pair offset any candidate has consumed (0 = the lost 12B run,
#: 4 = e4b, 6 = e2b / gemma3:4b / llama3.2:3b, 8 = the gemma3:4b confirmation).
#: Offset 6 was spent on three candidates, which is a deliberate common-item ladder for
#: bracketing -- not the "fresh items per candidate" the `build_dev_pairs` docstring
#: describes. Recorded here so the two are not silently in conflict.
_BURNED_DEV_OFFSETS = (0, 4, 6, 8)

#: The band each stage is allowed to draw from. Enforced in `run_screen`, not just in the
#: CLI's STAGES table, so a directly-constructed RunSpec cannot mislabel a run.
_STAGE_BANDS = {
    "DEV_SELECTION": "DEV_SELECTION",
    "ACQUISITION": "ACQUISITION",
    "PILOT": "PILOT",
    "BINDER_DIAGNOSTIC": "DIAGNOSTIC",
}

#: Identical for every arm and every stage. Recorded in the freeze.
SYSTEM_PROMPT = (
    "You are a careful reasoner. Read the state exactly as given and answer the question. "
    "Follow the requested answer format exactly."
)


@dataclass
class RunSpec:
    run_id: str
    stage: str  # DEV_SELECTION | ACQUISITION | PILOT
    band: str
    arms: tuple[str, ...]
    level: str
    n_per_contrast: int
    model: str
    base_url: str = "http://localhost:11434/v1"
    temperature: float = 0.0
    max_tokens: int = 4096
    order_seed: int = 20260808
    contrasts: tuple[str, ...] = contrast.CONTRASTS
    #: Pairs to skip -- items already spent on an earlier candidate.
    pair_offset: int = 0
    notes: str = ""

    def fingerprint(self) -> dict:
        return {
            "arena_version": ARENA_VERSION,
            "scorer_version": SCORER_VERSION,
            "tokenizer_for_budget": ENCODING,
            "system_prompt_sha256": _sha(SYSTEM_PROMPT),
            **{k: v for k, v in asdict(self).items()},
        }


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def build_dev_pairs(
    band: str, level: str, n_per_contrast: int, contrasts, *, pair_offset: int = 0
) -> list:
    """A balanced pair set drawn from one band.

    Balanced across the three contrast operators on purpose: selecting a model on
    quantifier order alone would tune the organism to one distinction, and the pilot uses
    all three. `IMPLICATION_DIRECTION` is the scarce one -- most flips do not change the
    answer -- so the seed window is widened until the quota is met rather than the quota
    being quietly reduced.

    `pair_offset` skips pairs already spent on an earlier candidate. The first
    developmental attempt consumed indices 0..3 of each contrast, so a later screen asks
    for `pair_offset=4` and gets items no model in this programme has seen. Reusing them
    would measure a second model on a set whose difficulty is already known.
    """
    from .bands import band_range

    window = list(band_range(band))
    out = []
    for kind in contrasts:
        got = contrast.build_pairs(kind, level, window[:4000])
        need = pair_offset + n_per_contrast
        if len(got) < need:
            raise RuntimeError(
                f"only {len(got)} {kind} pairs available in band {band}, "
                f"need {need} (offset {pair_offset} + {n_per_contrast})"
            )
        out.extend(got[pair_offset:need])
    assert_band([p[0].world.seed for p in out] + [p[1].world.seed for p in out], band)
    return out


def run_screen(
    spec: RunSpec, items, *, pairs=None, out_path: str | None = None, client=None
) -> dict:
    """Run one stage. `items` is a flat list; `pairs` is supplied when pair scoring applies.

    Acquisition items have no twins, so they pass `items` only and are scored per item.

    `client` exists so the preflight test can drive the whole path -- CLI, calls, JSONL,
    summary, reload -- with a fake that never touches a model. The persistence path is the
    one that already lost 24 paid-for calls once; it is not allowed to be exercised for the
    first time by a real run again.
    """
    from ..model_client import ModelClient, ModelConfig

    # Stage and band must agree. The arm guard below keys on `stage`, which is free-form
    # text; `RunSpec(stage="PILOT", band="DEV_SELECTION", arms=(...))` therefore slipped
    # past it, and `stage="ACQUISITION", band="PILOT"` would have applied bare scoring
    # while burning pilot seeds. Unreachable through the CLI, where STAGES pairs them --
    # but a guard that protects a label rather than the seed range it is named for is not
    # a guard.
    if spec.stage not in _STAGE_BANDS:
        raise ValueError(f"unknown stage {spec.stage!r}; expected one of {sorted(_STAGE_BANDS)}")
    if spec.band != _STAGE_BANDS[spec.stage]:
        raise ValueError(
            f"stage {spec.stage!r} must draw from band {_STAGE_BANDS[spec.stage]!r}, "
            f"not {spec.band!r}"
        )
    if spec.stage == "DEV_SELECTION" and tuple(spec.arms) != ("SE",):
        raise ValueError(
            "developmental selection must be structured-English only; seeing AST or HML "
            "performance before choosing the model contaminates the experiment"
        )
    pairs = pairs or []

    if client is None:
        cfg = ModelConfig(
            base_url=spec.base_url, model=spec.model,
            temperature=spec.temperature, max_tokens=spec.max_tokens,
        )
        client = ModelClient(cfg)
    identity = client.describe()

    # One work unit per (item, arm). Order is shuffled deterministically so that any drift
    # in the server over the run cannot line up with one arm, and so that a pair's two
    # members are not adjacent.
    units = [(item, arm) for item in items for arm in spec.arms]
    random.Random(spec.order_seed).shuffle(units)

    records = []
    for n, (item, arm) in enumerate(units, 1):
        prompt = build_prompt(item, ARM_RENDERERS[arm], instructions=_INSTRUCTIONS)
        # Latency is measured inside the client, around the request itself.
        c = client.complete(SYSTEM_PROMPT, prompt)
        scored = score_response(
            item.item_id, c.content, item.answer, item.answer_space,
            finish_reason=c.finish_reason or ("error" if c.error else "stop"),
            # Literal-recall stages only. Both ask for a single word, and this model
            # often answers with the bare word; scoring that wrong would measure format
            # compliance instead of reading. The reasoning pilot keeps the strict
            # `FINAL:`-only rule, because relaxing it there would change what a scored
            # reasoning answer means.
            allow_bare=(spec.stage in ("ACQUISITION", "BINDER_DIAGNOSTIC")),
        )
        records.append({
            "n": n,
            "item_id": item.item_id,
            "pair_id": item.pair_id,
            "arm": arm,
            "endpoint": item.endpoint,
            "family": item.family,
            "level": item.level,
            "seed": item.world.seed,
            "band": band_of(item.world.seed),
            "contrast": item.metrics.get("contrast", ""),
            "prompt_sha256": _sha(prompt),
            "prompt_chars": len(prompt),
            "expected": item.answer,
            "answer_space": list(item.answer_space),
            "raw_response": c.content,
            "raw_reasoning_chars": len(c.reasoning or ""),
            "parsed_answer": scored.extracted,
            "valid": scored.valid,
            "correct": scored.correct,
            "score_reason": scored.reason,
            "latency_s": round(c.latency_s, 2),
            "prompt_tokens": c.prompt_tokens,
            "completion_tokens": c.completion_tokens,
            "finish_reason": c.finish_reason,
            "error": c.error,
        })
        # Append each record to a JSONL sidecar the moment it exists. A model call costs
        # real time and cannot be un-spent, so no crash after this point may lose one.
        if out_path:
            with open(str(out_path) + "l", "a") as fh:
                fh.write(json.dumps(records[-1]) + "\n")
        print(
            f"  [{n:3d}/{len(units)}] {arm:3s} {item.item_id[:34]:34s} "
            f"exp={item.answer:<6s} got={scored.extracted or '-':<6s} "
            f"{'OK ' if scored.correct else ('inv' if not scored.valid else '.  ')} "
            f"{c.completion_tokens:5d}tok {c.latency_s:6.1f}s",
            flush=True,
        )

    # Summarising must never be able to destroy the run. It once did: `_summarise` was
    # defined below the module-entry guard, so `main()` raised NameError after all 24
    # calls had completed and every record was discarded unwritten.
    try:
        summary = _summarise(spec, pairs, records, items)
    except Exception as exc:  # noqa: BLE001 - the records are the expensive part
        summary = {"summary_error": f"{type(exc).__name__}: {exc}", "n_calls": len(records)}
    out = {
        "spec": spec.fingerprint(),
        "model_identity": identity,
        "summary": summary,
        "records": records,
    }
    if out_path:
        Path(out_path).write_text(json.dumps(out, indent=2) + "\n")
    return out


_INSTRUCTIONS = (
    "You are given a formal description of a state, and a question about it.\n"
    "Everything needed to answer is stated. Nothing is implied by convention."
)

#: Fixed stage shapes, so a run cannot be quietly resized after its numbers are seen.
#:
#: `micro` is the cheap first look at a candidate: 6 pairs (2 per contrast operator) = 12
#: calls, structured English only. `pair_offset=4` steps past the pairs the first
#: developmental attempt already spent, so a second candidate is never screened on items
#: whose difficulty is already known. `dev` continues the same candidate to 12 pairs.
STAGES = {
    "micro": dict(stage="DEV_SELECTION", band="DEV_SELECTION", arms=("SE",),
                  n_per_contrast=2, pair_offset=4),
    "dev": dict(stage="DEV_SELECTION", band="DEV_SELECTION", arms=("SE",),
                n_per_contrast=4, pair_offset=0),
    "acq": dict(stage="ACQUISITION", band="ACQUISITION", arms=("SE", "AST", "HML"),
                n_per_contrast=0, pair_offset=0),
    # Control characterisation, not a gate: does an arm let the model read binder order?
    "binder": dict(stage="BINDER_DIAGNOSTIC", band="DIAGNOSTIC", arms=("SE", "AST", "HML"),
                   n_per_contrast=0, pair_offset=0),
    # Pilot composition is calibrated from the SE-ONLY control arm, never from treatment:
    # DEV_SELECTION showed OPERAND_ORDER at 4/4 (ceiling) against QUANTIFIER_ORDER 2/4 and
    # IMPLICATION_DIRECTION 2/4. Including a saturated operator would spend a third of the
    # pilot on pairs that cannot move. Zero Endpoint-B AST or HML calls had been made when
    # this was decided -- see docs/evaluation/PILOT_COMPOSITION_DECISION.md.
    # B1: implication direction only. The binder diagnostic showed the AST control cannot
    # read binder NESTING out of JSON -- its answers are exactly predicted by "say forall
    # if forall appears anywhere", which fails every `exists`-outer claim. QUANTIFIER_ORDER
    # pairs are precisely {forall->exists, exists->forall}, so AST would fail one member of
    # every such pair for a READING reason, and an HML>AST gap there would be
    # uninterpretable. Implication is `{"op":"implies","args":[A,B]}` -- argument order, not
    # nesting depth -- and is unaffected. Quantifier scope becomes endpoint B2 after AST-v2.
    "pilot": dict(stage="PILOT", band="PILOT", arms=("SE", "AST", "HML"),
                  n_per_contrast=12, pair_offset=0,
                  contrasts=("IMPLICATION_DIRECTION",)),
}


def main(argv: list[str] | None = None) -> int:
    import argparse

    from .bands import assert_disjoint
    from .endpoints import acquisition

    ap = argparse.ArgumentParser(description="Run one model-facing arena stage.")
    ap.add_argument("stage", choices=sorted(STAGES))
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--level", default="L3")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument(
        "--pair-offset", type=int, default=None,
        help="override the stage's pair offset, so a new candidate is screened on items "
             "no earlier candidate has seen",
    )
    ap.add_argument(
        "--acq-seed-base", type=int, default=400_001,
        help="first ACQUISITION seed; bump it to draw a completely fresh item set",
    )
    a = ap.parse_args(argv)

    cfg = dict(STAGES[a.stage])
    if a.pair_offset is not None:
        cfg["pair_offset"] = a.pair_offset
    spec = RunSpec(
        run_id=f"{a.stage}-{a.model}-{time.strftime('%Y%m%dT%H%M%S')}",
        model=a.model, level=a.level, max_tokens=a.max_tokens, **cfg,
    )

    if a.stage == "binder":
        from .endpoints import binder_diag

        items = binder_diag.build_items()
        assert_band([i.world.seed for i in items], "DIAGNOSTIC")
        pairs = None
    elif a.stage == "acq":
        items = acquisition.build_items(
            range(a.acq_seed_base, a.acq_seed_base + 6), level=a.level
        )
        # `build_dev_pairs` asserts its band; the acquisition path did not, so a mistyped
        # `--acq-seed-base 500001` would have silently burned PILOT seeds -- a named stop
        # condition for this programme.
        assert_band([i.world.seed for i in items], "ACQUISITION")
        pairs = None
    else:
        pairs = build_dev_pairs(
            spec.band, spec.level, spec.n_per_contrast, spec.contrasts,
            pair_offset=spec.pair_offset,
        )
        items = [it for p in pairs for it in p]
        if a.stage == "pilot":
            # The named stop condition: no development seed may appear in the pilot.
            #
            # This compared against dev indices 0..5 of the pilot's own two contrasts --
            # which excluded the offsets actually spent (0,4,6,8) and every OPERAND_ORDER
            # item, and could not fail anyway since 300000+ and 500000+ are numerically
            # disjoint by construction. Now it covers every offset any candidate consumed
            # and compares item ids, which is the thing that could genuinely collide.
            burned_seeds, burned_ids = [], []
            for off in _BURNED_DEV_OFFSETS:
                for p in build_dev_pairs(
                    "DEV_SELECTION", spec.level, 4, contrast.CONTRASTS, pair_offset=off
                ):
                    for it in p:
                        burned_seeds.append(it.world.seed)
                        burned_ids.append(it.item_id)
            assert_disjoint(
                [it.world.seed for p in pairs for it in p], "PILOT",
                burned_seeds, "DEV_SELECTION",
            )
            assert_disjoint(
                [it.item_id for p in pairs for it in p], "PILOT items",
                burned_ids, "DEV_SELECTION items",
            )

    print(f"stage={a.stage} model={a.model} arms={spec.arms} "
          f"items={len(items)} calls={len(items) * len(spec.arms)}", flush=True)
    out = run_screen(spec, items, pairs=pairs, out_path=a.out)
    print(json.dumps(out["summary"], indent=2))
    return 0


def _summarise(spec, pairs, records, items) -> dict:
    by_arm: dict = {}
    for arm in spec.arms:
        rs = [r for r in records if r["arm"] == arm]
        valid = [r for r in rs if r["valid"]]
        scored_by_id = {
            r["item_id"]: type("S", (), {
                "valid": r["valid"], "correct": r["correct"], "item_id": r["item_id"],
            })()
            for r in rs
        }
        ps = pair_score(scored_by_id, pairs) if pairs else {}
        by_arm[arm] = {
            "items": len(rs),
            "valid": len(valid),
            "invalid": len(rs) - len(valid),
            "truncated": sum(1 for r in rs if r["finish_reason"] == "length"),
            "errors": sum(1 for r in rs if r["error"]),
            "single_item_correct": sum(1 for r in valid if r["correct"]),
            "single_item_accuracy": (
                round(sum(1 for r in valid if r["correct"]) / len(valid), 4) if valid else None
            ),
            **ps,
            "mean_completion_tokens": (
                round(sum(r["completion_tokens"] for r in rs) / len(rs), 1) if rs else 0
            ),
            "mean_prompt_tokens": (
                round(sum(r["prompt_tokens"] for r in rs) / len(rs), 1) if rs else 0
            ),
            "mean_latency_s": round(sum(r["latency_s"] for r in rs) / len(rs), 1) if rs else 0,
        }
    out = {
        "n_items": len(items),
        "n_pairs": len(pairs),
        "n_calls": len(records),
        "by_arm": by_arm,
        "any_truncation": any(r["finish_reason"] == "length" for r in records),
        "any_error": any(r["error"] for r in records),
    }
    if spec.stage == "ACQUISITION":
        # Which *kind* of literal recovery failed matters: "cannot find a declared sort"
        # and "cannot read a relation extension" are different diagnoses.
        # Keyed off the item's recorded kind, never off a substring of the id:
        # `FACT_CONTENT` and `FACT_COUNT` both start "FACT_", so splitting the id
        # silently merged two different diagnoses into one cell.
        kinds = {i.item_id: i.metrics.get("acquisition_kind", "?") for i in items}
        out["by_arm_and_kind"] = {
            arm: {
                kinds.get(r["item_id"], "?"):
                    ("correct" if r["correct"] else ("INVALID" if not r["valid"] else "WRONG"))
                for r in records if r["arm"] == arm
            }
            for arm in spec.arms
        }
    return out


# The module-entry guard lives at the very bottom, after every function it can reach.
# Placed above `_summarise`, it ran `main()` before that name was bound: the whole
# developmental screen completed its 24 model calls and then died with a NameError,
# discarding every record. Hence also `_flush` above -- results are written as they
# arrive, so a crash can never again cost calls that were already paid for.
if __name__ == "__main__":
    raise SystemExit(main())
