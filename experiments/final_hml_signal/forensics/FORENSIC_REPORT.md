# Forensic report: replicated +35.55pp HML signal

Date: 2026-08-23  
Result under audit: two-seed 10K `HML_WORKED_UTF8` 0.8575 versus
`STRUCTURED_NEUTRAL_WORKED` 0.5020 on the frozen 3,000-row FINAL set.

## Verdict

**MAJOR_SIGNAL_SURVIVES_FORENSICS.** The independent scorer reproduces +35.55pp exactly;
all four adapters, checkpoints and score paths are correct; FINAL pairing is exact; no
asymmetric gold/future field is model-visible; train–FINAL duplication does not explain
the result; surface-only models reach at most 39.37%; the lexical-failure delta is
+36.43pp; mean/sum/content-only rankings agree; and Neutral training completed normally.

This establishes a major representation-conditioned effect on **one-step next-action
selection**. It does not establish autonomous theorem solving, free-running multi-step
reasoning, or long-horizon solve rate.

## Required integrity gates

| gate | result | decisive evidence |
|---|---|---|
| independent scorer | PASS | 0 row-prediction, index, order or normalization mismatches; delta +0.3555 |
| adapters/checkpoints | PASS | four distinct on-disk hashes; score paths/hashes match; pinned base and recipe; no resume/init adapter flags |
| exact FINAL pairing | PASS | 3,000/3,000 IDs, parents, targets, candidate actions/order, state semantics and canonical hashes match |
| gold/future leakage | PASS | both prompts reconstruct exactly from state-before + identical candidate set + static instruction; no selected marker, state-after, delta, warrant, verdict or future field |
| Neutral training | PASS | both Neutral cells reached 5,000 steps/10,000 examples/90,000 reported target tokens; finite losses; no truncation, skip, NaN or failure |

The recorded source action is necessarily one of the six decision options in both views.
It is unmarked, has the same ID/order/action surface in both views, and is therefore not an
asymmetric HML leak. Detailed field tracing is in `field_provenance.csv`.

## Contamination

Exact state+candidates+gold duplicates: **0**. Raw normalized state duplicates: 1;
goal-text duplicates: 123; identifier-normalized state matches: 13; ordered candidate-set
duplicates: 0. None is an exact decision-instance duplicate.

The predeclared exact metric was 5-token-shingle Jaccard over normalized state plus ordered
candidates. Maximum TRAIN–FINAL similarity was 0.6919; counts at >=0.90, >=0.95 and >=0.98
were all **0**. Excluding >=0.98 or >=0.95 rows therefore leaves all 3,000 rows and the
delta unchanged at **+35.55pp**.

## Shortcut and robustness controls

| control | HML | Neutral | delta/reading |
|---|---:|---:|---|
| surface logistic regression | 0.3783 | 0.3937 | cannot explain HML 0.8575 |
| surface depth-6 tree | 0.3387 | 0.3550 | cannot explain HML 0.8575 |
| lexical-failure subset (n=1,437) | 0.7787 | 0.4144 | **+0.3643** |
| mean candidate logprob | 0.8575 | 0.5020 | **+0.3555** |
| raw sum logprob | 0.8575 | 0.5020 | **+0.3555** |
| content-only ranking | 0.8575 | 0.5020 | **+0.3555** |

Content-only ranking is determined without inference: every label is two tokens with the
same first token, so removing that common term cannot change any candidate argmax.
Fractional credit on exact top-score ties leaves +35.40pp; excluding all tied rows leaves
+34.25pp. The registered first-index tie rule therefore cannot explain the headline.

Targets are byte-paired and representation-independent `C0`–`C5` labels. Both arms have
mean/median/p95 raw target length 2 tokens, 20,000 raw target tokens, 80,000 supervised
suffix tokens and 90,000 trainer-reported tokens per seed. The common raw prefix is one
token and the variable index is one token. **OUTPUT_TARGET_CONFOUND = NO.**

## Manual and distribution audit

The deterministic pooled-score sample contains 50 HML-correct/Neutral-wrong and 50 reverse
rows. Mutually exclusive tags: LEXICAL_CUE 41; HML_SURFACE_CUE 1;
FUTURE_OR_GOLD_LEAK 0; TARGET_SERIALIZATION 0; TRAIN_NEAR_DUPLICATE 0;
TEMPLATE_SHORTCUT 14; GENUINE_ORGANIZATION_ADVANTAGE 19; UNCLEAR 25. The organization tag
is an operational residual after tested artifacts, not standalone causal proof.

Gold-position deltas are positive at every position: C0 +28.51pp, C1 +29.87pp,
C2 +38.16pp, C3 +41.51pp, C4 +37.33pp, C5 +38.32pp. Majority-position accuracy is 17.30%.
The largest tactic-family contribution is `rw` at 20.96% of total extra correct decisions;
no family dominates. The next largest are `simp` 15.19% and `exact` 13.55%, with positive
deltas of +39.51pp and +36.31pp respectively.

Optional base-model, cross-view and structure-shuffle inference were skipped for the
explicit token-conservation rule. No required core gate depends on them.

## Decision

No tested artifact explains the +35.55pp. Because output targets are already exactly common,
the next causal experiment is one **common-envelope 10K control**: use identical instruction,
candidate formatting/position and `C0`–`C5` targets, varying only HML state versus canonical
Neutral state. No 30K or 50K training was run during this audit.
