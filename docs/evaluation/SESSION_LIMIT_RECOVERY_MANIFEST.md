# Session-limit recovery manifest

Three subagents terminated mid-write on an API session limit (resets 23:20 Europe/London).
**The dirty tree is evidence.** It is preserved verbatim here before any integration edit,
so that nothing an interrupted agent wrote is lost or silently rewritten.

**This is a recovery commit, not a scientific freeze.** Nothing in it is claimed to be
complete or correct. The M1.5 freeze happens later, on a separate branch, after audit.

| | |
|---|---|
| parent commit | `9afafa8` (`hml-m1-constitutional-core`) |
| recovery branch | `recovery/session-limit-2026-08-05` |
| files preserved | **152** |
| secret scan | **clean** — no credentials, model blobs, virtualenvs, caches, or files >1 MB |
| suite at time of capture | **4721 passed**, 4 skipped, 1 xfailed |
| conformance at time of capture | **PASS**, 8/8, no override |

The state was green when captured. That is worth stating precisely: the interruptions
happened *between* coherent units of work, not in the middle of a broken edit.

## What each agent left

| subsystem | attributed to | status |
|---|---|---|
| `src/hamiltonian_lang/equivalence/`, `evaluation/m3/equivalence/`, `tests/equivalence/` | equivalence scorer | **COMPLETE** — returned `M3_EQUIVALENCE_SCORER_READY` |
| `src/hamiltonian_lang/verification/`, `evaluation/m3/verification/`, `tests/verification/` | verified endpoint | **COMPLETE** — returned `M3_VERIFIED_ENDPOINT_READY` |
| `src/hamiltonian_lang/improvement/`, `evaluation/syntax_gate/` | metric integrity | **COMPLETE** — returned `M2_METRIC_INTEGRITY_CONFIRMED` |
| `tests/reproducibility/`, `tests/concurrency/`, `scripts/reproducibility/` | reproducibility auditor | **COMPLETE** — returned `M1_REPRODUCIBILITY_CONFIRMED` |
| `src/hamiltonian_lang/repair/`, `context_broker/`, `tests/repair/` | Chain-of-Repair | **INTERRUPTED** — last words: *"Now the leakage harness tests"* |
| `evaluation/acq0/`, `tests/evaluation/test_acq0_protocols.py` | format protocol | **INTERRUPTED** — last words: *"Now full verification"* |
| `evaluation/corpus_governance/`, `evaluation/m3/lite/` | benchmark governance | **INTERRUPTED** — last words: *"Now the test file"* |
| `backends/canonical.py`, `DECISIONS.md` | Lead (D-024, D-025) | **COMPLETE** |

Counts: **94 COMPLETE · 47 INTERRUPTED · 5 MIXED · 6 REVIEW.**

The three interrupted agents each stopped while writing *tests*, not implementation. Their
implementation code is present and the suite is green, but **their own leakage, verification
and governance controls are the parts most likely to be missing** — which is precisely the
category of work whose absence is least visible. Nothing from those three subsystems may be
treated as validated until an audit says so.

## What is NOT claimed by this commit

- No agent's readiness claim is accepted here. Four returned gate verdicts; three did not.
- The interrupted subsystems are **not** integrated, **not** audited and **not** frozen.
- **ACQ0 = UNTESTED · H1 = UNTESTED · H2 = UNTESTED · H3 = UNTESTED.** No model call has
  been made beyond host-tuning probes. No syntax tournament, no calibration, no scout.

## Machine-readable form

`evaluation/manifests/session_limit_recovery.json` carries the per-file classification:
path, attributed agent, completion status.

## Next

Audit on `integration/m1.5-paper-derived-closeout`, then freeze M1.5. The recovery branch
is never rebased, amended or force-pushed — its whole value is being an untouched record of
what existed at the moment of interruption.
