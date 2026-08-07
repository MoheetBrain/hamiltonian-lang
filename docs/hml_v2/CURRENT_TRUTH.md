# Current truth — measured, not inherited

**Snapshot taken:** 2026-08-07 · **Verified at:** `ae9a2a0`

Every figure here was re-measured at this SHA. Where a directive or an earlier report
quoted a different number, the correction is shown.

## Repository

| | |
|---|---|
| worktree | `/Users/moheet/hml_v2_worktree` |
| branch | `feature/hml-reasoning-kernel-v2` |
| HEAD | `ae9a2a0` |
| remote | `ae9a2a0` — **in sync** |
| tree | clean except two untracked files from a running probe agent |
| model processes | `ollama serve` only, **idle**; no experiment running |
| other worktrees | `hamiltonian_lang` @ `3dd4216` (scientific integration, untouched) · `hml_audit_worktree` @ `b1ac7bf` (read-only evidence, untouched) |

## Corrections to quoted figures

| quoted | measured | |
|---|---|---|
| SHA `0715bfc` | `ae9a2a0` | 4 commits since |
| 6240 tests | **6279 passed, 0 failed** | |
| closure 0.692 | **0.417 strict (20/48)** | 0.692 is 9/13 on the *legacy subset*; different instrument |
| extensibility 0/9 | **0/6 probed forms** | confirmed absent |

## Measured state

**Tests.** 6279 passed, 5 skipped, 7 xfailed, 7 xpassed, **0 failed**.

**Composition.** STRICT **20/48 = 0.417**; FRAMEWORK **20/38 = 0.526** (10 UNSUPPORTED
excluded). The legacy 13-probe subset reads 0.692 at this same SHA. *These are two
instruments, not two points on a trend.*

Failure attribution over the 28 failures:
`GRAMMAR 14 · TYPE 8 · COMPILER 3 · CONSTRAINT 2 · SCOPE 1 · CANONICAL 0 · BACKEND 0 ·
SPECIMEN 0`.

**Ontology.** 486 atoms, 64 critical. Full probing **in progress** — `ALL_ATOMS.json`
exists, the report does not. Not yet inspected; nothing is claimed from it.

**Evidence DAG.** Implemented (`reasoning/evidence.py`, D-040). E1/E2/E3/E4/E7/E8 have
named checks; the validator walks all four edge kinds.

**Gemma calls since V2 work began: 0.**

## What is implemented vs. frozen-but-absent

| capability | state |
|---|---|
| evidence DAG | **implemented** |
| circular-law rejection | **implemented** (HML-S607, D-042) |
| assumption → type narrowing | **implemented** (D-028) |
| scoped Γ | **frozen as D-035, NOT built** — `push`/`pop` exist, nothing calls them |
| partiality contracts | **frozen as D-036, NOT built** — CT-038 open |
| approximation | **frozen as D-037, NOT built** |
| certificates | **frozen as D-038, NOT built** |
| extension signatures | **frozen as D-039, NOT built** — measured 0/6 |
| binder protocol | **not built** |
| synthetic generator | not built |
| compiler exhaustion | frontend fuzz only (52 tests) |

## Open defects with evidence

- **CT-038** — `(x^2 - 1) / (x - 1) = x + 1` compiles with **0 obligations**. Verified at
  this SHA. Closed only by D-036.
- **Binder duplication** — `free_names` returns `[]` for `integral(y, x : Real, 0.0, 1.0)`
  where `y` is free; latent because an unrelated guard masks it.
- **Two targeted AST additions outstanding** — abstraction (no derivative-at-a-point) and
  a binder over statements (indexed families of laws unwritable).

## Decisions that must not be reopened without new falsifying evidence

- **D-041** — the generic Apply/Bind/Attribute core is **rejected on measurement**: it
  reaches 0.563 alone, *below* the Level 2 threshold, while targeted repairs reach 0.854.
  Confidence 0.75, with a written falsification condition.

## Maturity

**LEVEL 1 — DOMAIN DSL.** Unchanged. Level 2 needs compositionality ≥ 0.70 on its own
instrument and a coverage assessment that does not yet exist. No level claim is made from
the 0.417 or the 0.692 figure until the ontology probe completes.
