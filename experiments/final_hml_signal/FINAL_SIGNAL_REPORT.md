# Final HML Signal Report

Date: 2026-08-23  
Branch: `codex/final-hml-signal`  
Corpus payload/reporting commits: `fb6e28edec0f77753d97486cbae759a59f1d1f38` / `627194144abd9396dadbebf0b7834e76b937d908`  
Qwen3-8B revision: `b968826d9c46dd6066d109eabc6255188de91218`

## Verdict

**30K_JUSTIFIED.** Both independent 10K seeds favor HML by more than 35 percentage
points, and the two-seed parent-clustered 95% bootstrap interval excludes zero by a wide
margin. The frozen replication gate passes. Per the emergency finish instruction, no 30K
or 50K cell was started.

This is a result for **depth-conditioned one-step action selection**, not a free-running
rollout. The overall HML advantage is decisive, but neither the depth interaction nor the
complexity interaction is independently clear after pooling both seeds.

## Primary result

| result | HML Top-1 | Neutral Top-1 | HML − Neutral | parent-bootstrap 95% CI |
|---|---:|---:|---:|---:|
| seed 1 | 0.8543 | 0.5023 | **+0.3520** | [+0.3308, +0.3726] |
| seed 2 | 0.8607 | 0.5017 | **+0.3590** | [+0.3371, +0.3800] |
| two-seed mean | **0.8575** | 0.5020 | **+0.3555** | **[+0.3353, +0.3750]** |

The two-seed relative error reduction is 71.39%. The historical corrected approximately
3.2K result was +2.30pp; the measured 10K advantage is much larger. This comparison is a
training-scale reference, while the confirmatory inference is the matched 10K comparison.

## Frozen strata

| depth | n | HML | Neutral | delta | 95% CI |
|---|---:|---:|---:|---:|---:|
| 1 | 804 | 0.8800 | 0.5529 | +0.3271 | [+0.2942, +0.3607] |
| 2–3 | 838 | 0.8496 | 0.4994 | +0.3502 | [+0.3174, +0.3839] |
| 4–5 | 404 | 0.8725 | 0.4938 | +0.3787 | [+0.3296, +0.4267] |
| 6–10 | 485 | 0.8577 | 0.5041 | +0.3536 | [+0.3039, +0.4022] |
| 11–20 | 331 | 0.8021 | 0.4215 | +0.3807 | [+0.3194, +0.4446] |
| 21+ | 138 | 0.8623 | 0.4312 | +0.4312 | [+0.3613, +0.4877] |

The pooled depth-11+ minus depth-1–10 interaction is +4.74pp, 95% CI
[-0.86, +9.95]pp: directionally positive, but not independently clear.

| complexity | n | HML | Neutral | delta | 95% CI |
|---|---:|---:|---:|---:|---:|
| LOW | 806 | 0.8579 | 0.5062 | +0.3517 | [+0.3175, +0.3859] |
| MEDIUM | 756 | 0.8704 | 0.5218 | +0.3485 | [+0.3088, +0.3855] |
| HIGH | 714 | 0.8536 | 0.5175 | +0.3361 | [+0.2986, +0.3735] |
| VERY_HIGH | 724 | 0.8474 | 0.4613 | +0.3860 | [+0.3444, +0.4257] |

The pooled HIGH/VERY_HIGH minus LOW/MEDIUM interaction is +1.11pp, 95% CI
[-2.92, +4.94]pp: not clear.

## Secondary checks

| subset/metric | n | HML | Neutral | delta | 95% CI |
|---|---:|---:|---:|---:|---:|
| statistics/probability Top-1 | 321 | 0.8536 | 0.5452 | +0.3084 | [+0.2542, +0.3625] |
| lexical-baseline failure Top-1 | 1,437 | 0.7787 | 0.4144 | +0.3643 | [+0.3376, +0.3912] |
| complete multi-step states Top-1 | 1,489 | 0.8418 | 0.4758 | +0.3660 | [+0.3370, +0.3940] |
| MRR | 3,000 | 0.9109 | 0.6721 | +0.2388 | [+0.2251, +0.2522] |
| NLL | 3,000 | 0.5518 | 1.3633 | -0.8115 | [-0.8413, -0.7808] |
| candidate entropy | 3,000 | 0.9441 | 1.5745 | -0.6304 | [-0.6484, -0.6127] |
| gold-action margin | 3,000 | 1.9250 | 0.2542 | +1.6708 | [+1.6041, +1.7392] |

The frozen lexical-overlap baseline is 0.5210. HML's advantage persists and is slightly
larger on the 1,437 examples where that heuristic fails, so the result is not confined to
lexically easy rows.

## Gate and audit

The frozen second-seed gate requires both seeds to favor HML and at least one of: mean
delta at least +3pp, pooled paired uncertainty excluding zero, or a replicated interaction.
Both seeds favor HML; mean delta is +35.55pp; pooled CI is [+33.53, +37.50]pp. **PASS.**

Preflight verified byte-identical paired record IDs, parents, splits, targets, candidates
and candidate order; zero train/FINAL record or parent overlap; exact corpus/rung hashes;
native BF16 weights; and no target marker or gold-candidate annotation in either input.
The scorer's shared-prefix optimization was bitwise identical to the inherited validated
prompt-cache candidate scorer on its parity probe.

Training used four one-epoch 10K cells, 5,000 iterations each, batch 2, 90,000 reported
supervised tokens per cell. Total training wall time was 12,906.17 seconds
(3h 35m 06s). Peak MLX allocation was 29.905 GB (HML) and 29.491 GB (Neutral).

## Machine artifacts

- `raw_predictions/10k_hml_s1.json` — SHA-256 `36ec4d780933df6d5a587263922e07dd7c6c70b7819a702d7c8d5220a813ec8f`
- `raw_predictions/10k_neutral_s1.json` — SHA-256 `b41beac99b8fee395ab11e4d1f0ac4823f1fa204d78a40efdcf049d88ef5d54a`
- `raw_predictions/10k_hml_s2.json` — SHA-256 `a45d605a8b5e4622fa0035ec5c94b652309789a89b41ee99422dddbab542f4c2`
- `raw_predictions/10k_neutral_s2.json` — SHA-256 `0003db852de86ec409b8932d4cf883c7727dfc10fcebb06743fe2f6dbd64ee04`
- `statistics_10k_s1-2.json` — SHA-256 `bf16cfbbad47507ccb10ff89a76476ab2182d68a4de765f48ee98a13ebc47326`

