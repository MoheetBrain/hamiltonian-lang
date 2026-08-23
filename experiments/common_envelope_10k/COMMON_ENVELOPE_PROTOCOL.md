# Common-envelope 10K causal-control protocol

Frozen before training or evaluation on 2026-08-23. This experiment changes exactly one
model-visible variable: the serialization inside a delimited state payload. It does not
change HML, candidates, targets, data, splits, optimization or scoring.

## Authorities

- Corpus reporting commit: `627194144abd9396dadbebf0b7834e76b937d908`
- Immutable corpus payload: `fb6e28edec0f77753d97486cbae759a59f1d1f38`
- 10K record-ID SHA-256: `1eeb0b2f79d3472b96f72b6b9ee47b12ee9c20b17a9de6e647877169b198bbff`
- Qwen3-8B BF16 revision: `b968826d9c46dd6066d109eabc6255188de91218`
- HML state authority used by the corpus: `68178f07784d2a17a9aed9c4dedbea9c740c97a0`

## Frozen prompt

There is no system message. The single user message is constructed once as:

```text
Choose the single most useful next mathematical tactic from the six candidates.

<STATE>
{STATE_SERIALIZATION}
</STATE>

<CANDIDATES>
C0: {RAW_ACTION_0}
C1: {RAW_ACTION_1}
C2: {RAW_ACTION_2}
C3: {RAW_ACTION_3}
C4: {RAW_ACTION_4}
C5: {RAW_ACTION_5}
</CANDIDATES>

Answer with exactly one label:
C0 / C1 / C2 / C3 / C4 / C5
```

Candidate text, IDs, order, punctuation, spacing and placement are byte-identical. The
target is the same `C0`–`C5` string. The HML payload is the existing exact
`HML_WORKED_UTF8` state rendering. The Neutral payload is canonical JSON of the same
typed `state_before`. Neither arm names its representation.

Preflight must show zero prefix, suffix, candidate, target, ID, parent or semantic-source
mismatches across 10K TRAIN + 3K DEV + 3K FINAL; exactly one delimited payload is permitted
to differ. Independent HML parsing and Neutral JSON parsing must reconstruct the same typed
state for all 16K pairs. Any material mismatch stops training.

## Training and evaluation

Native BF16 base, no quantization; LoRA last 8 layers, `q_proj + o_proj`, rank 4, scale 2,
dropout 0; Adam; learning rate `1e-4`; batch 2; mask prompt; gradient checkpointing;
MAXSEQ 6144; one complete 10K epoch (5,000 iterations); no representation-specific tuning.
The actual prior recipe file is reused byte-for-byte. Arms run sequentially on MLX Metal.

FINAL is the untouched 3,000-row split. Thinking is disabled. Each equal-length `C0`–`C5`
label is scored by mean candidate-token log probability, using the validated shared-prefix
prompt-cache scorer. Report Top-1 (primary), MRR, candidate-set NLL, entropy and
gold-minus-best-distractor margin. Parent-clustered paired bootstrap: 4,000 draws, seed
`20260823`. Ties select the first maximal candidate index.

Seed 1 runs first. If delta <= 0, stop with `COMMON_ENVELOPE_EFFECT_FAILED`. If
0 < delta < +5pp, seed 2 runs only when the parent-bootstrap lower bound exceeds zero or
the exact paired discordance test has p < .05; otherwise stop `COMMON_ENVELOPE_EFFECT_WEAK`.
If delta >= +5pp, seed 2 runs. Two-seed verdict thresholds are: <=0 failed; (0,5) weak;
[5,15) confirmed modest; [15,25) strong; >=25 extraordinary.

Frozen diagnostic strata are depth `1`, `2-3`, `4-5`, `6-10`, `11-20`, `21+` and
complexity LOW/MEDIUM/HIGH/VERY_HIGH, plus the existing lexical heuristic and
statistics/probability flag. These remain secondary. If the final delta is <15pp, the
predeclared old-versus-new failure analysis runs from saved predictions only.

No 30K, 50K, HML redesign, candidate regeneration, hyperparameter search or theorem
rollout is authorized. The result is one-step next-action selection, not theorem solving.
