# Emergency forensic protocol

Frozen before reading forensic measurements on 2026-08-23. Existing training,
prediction, protocol, manifest and report artifacts are read-only. No training is allowed.

## Required gates

The audit follows the requested phase order. A fatal failure in scorer reproduction,
adapter identity, FINAL pairing, or asymmetric gold/future leakage stops later optional
work after one independent confirmation.

Headline reproduction uses a fresh implementation over saved candidate scores. Ties use
the first candidate index, matching deterministic Python `argmax` behavior. Both mean and
sum candidate scores are recomputed from the stored arrays.

Adapter integrity is decided from on-disk SHA-256 values, cell manifests, commands,
adapter output directories, base revision and the frozen LoRA config. Any cross-arm path
or hash mismatch is fatal.

FINAL parity requires identical record/parent/target/index/candidate order, matching
canonical-transition hashes, exact state-before view hashes and no state-after view hash
substitution.

## Contamination metric

Exact checks use raw, Unicode-NFKC/whitespace/case-normalized and identifier-normalized
forms. The theorem-statement proxy is the active Lean goal after the final `⊢`; the exact
decision instance is normalized state plus ordered candidate actions plus gold index.

The one near-duplicate metric is exact Jaccard similarity over sets of 5-token shingles
from the normalized representation-neutral decision input: raw Lean state-before plus the
six ordered candidate actions. Sparse binary matrix multiplication computes every nonzero
TRAIN–FINAL intersection exactly. Thresholds are frozen at `>=0.90`, `>=0.95`, `>=0.98`
before measurement. Exclusion deltas remove FINAL rows whose maximum 10K-TRAIN similarity
meets the stated threshold.

## Surface controls

Surface-only candidate features are fixed before fitting: candidate index; character,
token, punctuation, Unicode and line counts; prefix/suffix class; tactic-head category;
length rank; same-head multiplicity; and candidate/state lexical Jaccard. Separate
logistic-regression and depth-6 decision-tree models are trained on the 10K rows and tested
on FINAL. The reported arm baseline is the better of those two predeclared models, with
both retained in JSON. No model-visible gold/future/verification field is a feature.

The lexical baseline independently selects the first candidate with maximal token-Jaccard
overlap with the state. Manual sampling uses seed `20260823`, pooled two-seed candidate
scores, 50 HML-correct/Neutral-wrong cases, all available reverse cases up to 50, then
both-wrong fillers to 100.

Optional base-model, cross-view and structure-shuffle inference may be skipped for token
conservation; their omission cannot upgrade a failed core gate.
