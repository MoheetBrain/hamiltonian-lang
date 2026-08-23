# Final HML signal protocol

Frozen before viewing any HML50K model result on 2026-08-23.

## Question

Does one matched epoch over 10,000 underlying transitions make literal-UTF-8 HML improve
Qwen3-8B next-action selection over the information-matched canonical-JSON Neutral view?
The primary endpoint is FINAL-set Top-1 accuracy and the primary contrast is HML minus
Neutral. The materiality bar remains +5 percentage points.

Depth results are depth-conditioned one-step action-selection results. They are not
free-running rollouts.

## Frozen authorities

- Corpus: `/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus` at reporting commit
  `627194144abd9396dadbebf0b7834e76b937d908`; immutable payload commit
  `fb6e28edec0f77753d97486cbae759a59f1d1f38`.
- Rung ID hashes: 10K `1eeb0b2f79d3472b96f72b6b9ee47b12ee9c20b17a9de6e647877169b198bbff`;
  30K `255832921459b25dfe29fb86b20e38ab62e3e2e04d2067e359b8c8423cf137b4`;
  50K `4777d6e6a2751888473a6eec894da750c2394c1349c8e3be5582862b355f5391`.
- Views: `HML_WORKED_UTF8` and `STRUCTURED_NEUTRAL_WORKED`. No rendering change is
  permitted.
- Model: `Qwen/Qwen3-8B` revision
  `b968826d9c46dd6066d109eabc6255188de91218`, native BF16 only.
- Previous validated recipe: last 8 layers, LoRA rank 4/scale 2, q_proj + o_proj, dropout
  0, Adam, learning rate 1e-4, batch 2, masked prompt, gradient checkpointing, MAXSEQ 6144.

## Exposure and evaluation

Each arm receives exactly the same underlying 10,000 records for one epoch (5,000 batch-2
iterations). Examples are sorted by their own exact chat-token length before MLX loading,
as in the validated prior harness, to avoid the known `CacheDataset.itemlen` bucketing bug.
This changes batching efficiency, not membership or exposure. HML is not truncated or
token-matched; its token cost is recorded.

The fixed 3,000-row FINAL split is scored with thinking disabled and constrained candidate
log probabilities. Candidate order, labels, model, adapter recipe and scoring are identical
between arms. Primary candidate score is mean token log probability, inherited from the
previous Qwen action-selection experiment. Raw sum is retained.

Report Top-1, MRR, candidate-set NLL, entropy and gold-minus-best-distractor mean-logprob
margin. Uncertainty is a 4,000-draw parent/theorem-clustered paired bootstrap with seed
20260823. The frozen lexical-overlap heuristic is the Jaccard overlap between Unicode-aware
state tokens and candidate-action tokens, first-index tie break.

Frozen strata are corpus complexity labels and depth bins `1`, `2-3`, `4-5`, `6-10`,
`11-20`, `21+`. Also report complete multi-step trajectories, statistics/probability rows,
and lexical-success/failure subsets.

## Mechanical gate

After one 10K seed:

- If delta is at most zero: terminate the representation program.
- If delta is below +2pp and neither depth nor complexity has a clear positive interaction:
  terminate.
- If delta is at least +5pp: run exactly one second 10K seed.
- If delta is +2pp to below +5pp: run exactly one second 10K seed.
- A sub-2pp result earns a second seed only for a clear interaction: the combined harder
  population (depth 11+ or HIGH/VERY_HIGH) must exceed its easier complement by at least
  3pp, contain at least 100 rows, and have a parent-bootstrap interaction CI above zero.

If seed 2 runs, proceed only when both seeds favor HML and at least one holds: mean delta
is at least +3pp; the pooled paired CI excludes zero; or the positive pre-existing-strata
interaction replicates by the same rule. Otherwise terminate.

30K is allowed only after that replicated 10K gate. 50K is allowed only if 30K is more
positive or materially confirms the replicated mechanism. No tuning, new data, new syntax,
new model, altered strata, or post-result representation work is permitted.

## Success and stopping language

Strong success requires at least +5pp Top-1 or roughly 15-20% relative error reduction with
credible paired uncertainty. A modest overall effect with a large reproducible depth-11+ or
HIGH/VERY_HIGH effect is reported only as `HML_SPECIALIZED_LONG_DEPTH_EFFECT_FOUND`.
Otherwise, after the minimum gate-authorized runs, the exact verdict is
`HML_REASONING_REPRESENTATION_PROGRAM_TERMINATED`.
