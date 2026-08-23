# COMMON-ENVELOPE 10K CAUSAL CONTROL — FINAL

Date: 2026-08-23. Protocol commit: `ce5614947da1bf184d2e04c0107211cdddf4ee20`.

## Final verdict

**COMMON_ENVELOPE_EFFECT_FAILED.** Under a byte-identical instruction/candidate/answer envelope, Neutral canonical JSON scores **88.10%** and HML scores **85.33%** on the frozen 3,000-row FINAL set: HML−Neutral = **−2.77pp**, problem-clustered 95% CI **[−3.72, −1.81]pp**. The frozen seed-1 gate therefore stopped the experiment; seed 2 was not run.

The previous +35.55pp result was not a state-serialization advantage. HML remained essentially stable while Neutral rose by 37.90pp, mechanically identifying the previous arm-specific envelope as a severe Neutral handicap.

## Frozen design and authority

- Corpus: `MoheetBrain/hml-reasoning-corpus` at `627194144abd9396dadbebf0b7834e76b937d908`; 10K rung hash `1eeb0b2f79d3472b96f72b6b9ee47b12ee9c20b17a9de6e647877169b198bbff`.
- Model: Qwen3-8B BF16 at `b968826d9c46dd6066d109eabc6255188de91218`; no quantization.
- LoRA: last 8 layers, q+o, rank 4, scale 2.0, dropout 0, Adam, learning rate 1e-4, batch 2, 5,000 optimizer steps, prompt masking, gradient checkpointing, max sequence 6,144.
- The only permitted prompt difference was the content inside `<STATE>...</STATE>`: readable HML versus canonical Neutral JSON. Instructions, candidate bytes/order, target, IDs, parents and source transition hashes were matched.

## Preflight audits

- Common-envelope byte audit: **PASS**, 16,000 paired train/dev/final rows; zero prefix, suffix, candidate, target, ID, parent, source or unexpected mismatches. All 16,000 state payloads differed syntactically.
- Semantic parity: **PASS**, 16,000/16,000. Full typed states reconstructed exactly in both arms. Claims/facts, goals, embedded goal markers, scopes/local context, statuses, identifiers, branches, candidates and obligations matched; zero HML-only semantic information.
- Leakage/split audit: zero train↔FINAL record or parent overlap; no future/gold fields.
- Token audit: **PASS**, zero truncation. Mean complete chat prompt: HML 494.62 tokens, Neutral 408.16; HML cost **1.212×** (+21.18%). Max: 3,504 versus 3,281, both below 6,144.

## Untouched-base zero-shot diagnostic

| arm | Top-1 | MRR | NLL |
|---|---:|---:|---:|
| HML | 0.8400 | 0.8993 | 0.6232 |
| Neutral | 0.8797 | 0.9242 | 0.6037 |
| HML−Neutral | **−0.0397** | −0.0249 | +0.0196 |

Zero-shot Top-1 CI: **[−4.87, −3.07]pp**. The untouched model already preferred Neutral under the common envelope.

## Seed 1 trained result

| arm | Top-1 | MRR | NLL | entropy | correct-action margin |
|---|---:|---:|---:|---:|---:|
| HML | 0.8533 | 0.9104 | 0.4427 | 0.6569 | 2.7821 |
| Neutral | 0.8810 | 0.9283 | 0.3971 | 0.6468 | 2.8855 |
| HML−Neutral | **−0.0277** | −0.0179 | +0.0456 | +0.0100 | −0.1034 |

Top-1 paired discordances: HML-only 47, Neutral-only 130; exact McNemar p = `3.38e-10`. Clustered bootstrap used 4,000 draws, frozen seed 20260823, and 888 problem groups.

Learning gain over untouched base:

- HML: **+1.33pp**.
- Neutral: **+0.13pp**.

## Neutral training sanity

**PASS.** Both arms used the same recipe and prompt mask, identical ordered targets, 80,000 prepared supervised suffix tokens, 10,000 examples, 5,000 optimizer steps and 90,000 trainer-reported tokens. Neither arm truncated. Neutral training loss fell from **0.493 to 0.031** (HML: 0.613 to 0.040). No implementation bug was found.

## Previous → common-envelope decomposition

| | previous | common envelope | change |
|---|---:|---:|---:|
| HML | 0.8575 | 0.8533 | **−0.42pp** |
| Neutral | 0.5020 | 0.8810 | **+37.90pp** |
| HML−Neutral | +35.55pp | **−2.77pp** | −38.32pp |

Delta retained: **−7.78%**. Mechanical interpretation: **HML stable + Neutral rises strongly ⇒ the previous envelope disproportionately hurt Neutral.** Predictions changed on 281 HML rows versus 1,408 Neutral rows.

## Frozen strata: HML−Neutral Top-1 delta

| depth | delta | n |
|---|---:|---:|
| 1 | −2.36pp | 804 |
| 2–3 | −2.39pp | 838 |
| 4–5 | −2.72pp | 404 |
| 6–10 | −2.06pp | 485 |
| 11–20 | −4.53pp | 331 |
| 21+ | −5.80pp | 138 |

| complexity | delta | n |
|---|---:|---:|
| LOW | −3.60pp | 806 |
| MEDIUM | −2.12pp | 756 |
| HIGH | −1.82pp | 714 |
| VERY_HIGH | −3.45pp | 724 |

- Lexical-baseline-failure subset: HML 0.7704, Neutral 0.8051, delta **−3.48pp**, n=1,437.
- Statistics/probability subset: HML 0.8505, Neutral 0.8816, delta **−3.12pp**, n=321.
- There is no positive HML depth or complexity interaction.

## Resources and diagnostic trail

- Training wall time: HML 72.96 min; Neutral 51.56 min. Scoring: HML 12.45 min; Neutral 10.91 min. Zero-shot scoring: 24.70 min. End-to-end wall clock: **2h 56m**.
- Peak MLX memory: **30.71 GB**. Observed swap range during training: **4.95–9.46 GB**; current final swap 8.53 GB. Minimum free memory: 1.86 GiB.
- Paired diagnostic JSONL: 4.45 MB, hashes/IDs/tokens/scores/labels/metadata only, no full prompts; below the 50 MB cap.
- Failure forensics: `diagnostics/failure_analysis.md`.

## Scientific conclusion and next experiment

This proves that the earlier +35.55pp was not caused by HML state serialization: with all non-state prompt bytes controlled, canonical Neutral JSON is modestly but significantly better both zero-shot and after 10K LoRA.

It does not prove universal JSON superiority beyond this frozen Qwen3-8B next-action task, dataset and adapter recipe.

No seed 2, 30K, 50K, prompt tuning or architecture work is authorized. The next clean scientific experiment is an independently frozen task/benchmark replication only if separately approved.
