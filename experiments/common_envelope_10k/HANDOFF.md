# New-chat handoff — frozen common-envelope 10K result

Date: 2026-08-24 (Europe/London). This handoff closes the HML/Neutral common-envelope experiment and is the sole starting point for a new chat.

## Start here

Repository: `/Users/moheet/Documents/ChatGPT/hamiltonian-lang-final-signal`

Remote: `https://github.com/MoheetBrain/hamiltonian-lang.git`

Branch: `codex/final-hml-signal`

Frozen tag: `common-envelope-10k-final-20260824`

Read, in order:

1. `experiments/common_envelope_10k/COMMON_ENVELOPE_REPORT.md`
2. `experiments/common_envelope_10k/COMMON_ENVELOPE_PROTOCOL.md`
3. `experiments/common_envelope_10k/diagnostics/final_analysis.json`
4. This handoff.

## Immutable anchors

- Frozen protocol commit: `ce5614947da1bf184d2e04c0107211cdddf4ee20`
- Complete result-data commit: `4bbd71c86c6650265679c565e12a48630ef4b58f`
- Result commit repository tree: `d30266991ef695366d7b7047ce95f305bc8576c0`
- Result commit `experiments/common_envelope_10k` subtree: `9e098c8ae8f1474d3b88e76ad3006b9066afae2b`
- Corpus commit: `627194144abd9396dadbebf0b7834e76b937d908`
- 10K rung SHA-256: `1eeb0b2f79d3472b96f72b6b9ee47b12ee9c20b17a9de6e647877169b198bbff`
- Qwen3-8B BF16 revision: `b968826d9c46dd6066d109eabc6255188de91218`
- Model snapshot SHA-256: `2ee8d5231104dd7a49cbb914896386977d628e8aee9e168dbab7f6ab53a834e4`

The annotated tag above points to the handoff/freeze commit. The result-data commit and subtree IDs anchor the exact pre-handoff scientific artifacts without any circular self-reference.

## Final scientific state

**Final verdict: `COMMON_ENVELOPE_EFFECT_FAILED`.**

- Byte audit: PASS, 16,000 paired rows; only state-payload bytes differ.
- Strict semantic parity: PASS, 16,000/16,000; no missing or HML-only information.
- Neutral training sanity: PASS; same masking, ordered targets, supervised-token count, examples and optimizer steps; Neutral loss fell 0.493 → 0.031.
- Zero-shot: HML 84.00%, Neutral 87.97%, delta −3.97pp, 95% CI [−4.87, −3.07]pp.
- Trained seed 1: HML 85.33%, Neutral 88.10%, delta −2.77pp, 95% CI [−3.72, −1.81]pp.
- Learning gain: HML +1.33pp; Neutral +0.13pp.
- Previous → common envelope: HML −0.42pp; Neutral +37.90pp; delta +35.55pp → −2.77pp.
- Mechanical conclusion: the previous arm-specific envelope disproportionately harmed Neutral; the +35.55pp result was not an HML state-serialization advantage.
- Frozen gate: delta ≤ 0, so seed 2 was not authorized and was not run.

Do not resume seed 2. Do not start 30K/50K, prompt tuning, another model, architecture work or another benchmark from this handoff. A new scientific task requires a new explicit user decision and a separately frozen protocol.

## Saved data

Everything required to inspect the conclusion is tracked and pushed under `experiments/common_envelope_10k/`:

- protocol, run manifests, report and this handoff;
- byte, semantic, strict-semantic and token audits;
- complete trained and zero-shot row-level predictions;
- seed-1 analysis, clustered bootstrap results, paired diagnostics and failure forensics;
- compact training/scoring summaries and telemetry;
- full training logs;
- final HML and Neutral LoRA adapters.

Vendored final adapters:

- `adapters/hml_seed1/adapters.safetensors`: `6c65c179f4ae3f38ec079e9c5c121a6afae1719841a0a1293f27c8b2fca4ec69`
- `adapters/neutral_seed1/adapters.safetensors`: `2c72c200fd6738d0d91f3b0297ad1d78497c5eeb639e871b64852344eb39cb50`

The local external artifact root remains `/Users/moheet/hml_research_artifacts/common_envelope_10k/`. It additionally contains reproducible prepared JSONL and 100-step adapter checkpoints. Those intermediate checkpoints are not required for the verdict; the final adapters are vendored above.

## Fast verification

```bash
git checkout codex/final-hml-signal
git status --short
jq '{final_verdict,gate,seed2,learning_gain,comparison_previous}' experiments/common_envelope_10k/diagnostics/final_analysis.json
jq '{result,total_pairs}' experiments/common_envelope_10k/audits/envelope_byte_diff.json experiments/common_envelope_10k/audits/strict_semantic_parity.json
shasum -a 256 experiments/common_envelope_10k/adapters/*/adapters.safetensors
```

Expected repository state after checkout: clean worktree, no training/scoring/Metal process, branch and annotated freeze tag present on `origin`.

## Paste into the new chat

> Read `experiments/common_envelope_10k/HANDOFF.md` and `COMMON_ENVELOPE_REPORT.md` from the frozen tag `common-envelope-10k-final-20260824`. Treat `COMMON_ENVELOPE_EFFECT_FAILED` and the seed-2 stop as final. Do not rerun or extend this experiment. First report the immutable commits, artifact integrity, and the exact scientific boundary; wait for a new explicitly authorized task before changing anything.
