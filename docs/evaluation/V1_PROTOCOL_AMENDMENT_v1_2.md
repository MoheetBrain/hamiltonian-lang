# Developmental protocol v1.2 — runtime amendment to the V1 benchmark

**Status:** committed before any scientific call of the SE-versus-HML-V1 measurement.
**Supersedes:** the v1 frozen budget inherited from ACQ0, for this run only.
**Machine-readable form:** `evaluation/v1_benchmark/protocol_v1_2.py`.

This document exists so that the run it governs can never be described as the untouched
original configuration. It was written and committed **before any scientific result was
observed**, which is the only point at which a budget change is not a post-hoc one.

---

## 1. What is amended

| | v1 (frozen) | v1.2 (this run) |
|---|---|---|
| `PER_CALL_COMPLETION_ALLOWANCE` | 1024 | **4096** |
| `TOTAL_COMPLETION_ALLOWANCE_PER_ARM` | 2048 | **8192** |

Applied **identically to SE and to HML-V1**. Every other scientific input is held exactly
as frozen:

- temperature `0.0`
- model `gemma4:31b`, digest `6316f0629137b426…`, verified live against the pin
- two calls per task per arm
- the same 24 tasks in the same frozen order
- the same deterministic scorer
- matched mathematical information between the arms
- matched revision opportunity between the arms

## 2. Why 1024 was operationally unsafe

The v1 figure was inherited from `docs/evaluation/ACQ0_CONTEXT_BUDGET.md`, where 2048
completion tokens per task were fixed so that ACQ0 and this benchmark could share one
server configuration. That is a **scheduling** constraint, not a scientific one, and it was
never validated against this benchmark's output lengths.

The eval001 headroom screen then measured the consequence directly. From
`evaluation/results/h2_headroom_screen/SCREEN_REPORT.json` and the commit that closed it
(`fa39abc`): **11 truncations at a 2400-token cap**, with the explicit note that *"the cap
must be raised before any corpus is measured for real."*

1024 is **less than half** the cap that already truncated 11 times.

The reason this is not a symmetric inconvenience:

> A truncated completion is not a wrong answer. It is an **absent** one, and the scorer
> records it as a failure of the representation under test.

The HML arm must emit a fenced module **in addition to** its reasoning, so it is the more
verbose arm by construction. A truncation artefact would therefore be
**anti-correlated with the treatment** — it would fall hardest on the arm being tested and
would be reported as evidence about the representation. Running at 1024 would have measured
verbosity and published it as semantics.

Raising a ceiling symmetrically cannot advantage either arm: no prompt, task, or piece of
information changes. It removes an artefact; it does not add a signal.

## 3. The runtime is recorded as measured, not as inherited

`evaluation/v1_benchmark/arms.py` records `RUNTIME = "4 x 8192"`. **The live server does not
match that string.** Read from the running `ollama serve` process at amendment time:

```
OLLAMA_NUM_PARALLEL=2   OLLAMA_CONTEXT_LENGTH=16384   OLLAMA_KEEP_ALIVE=4h
```

That is a two-slot **`2 x 16384`** arrangement. The measured value is recorded in
`protocol_v1_2.py` as `RUNTIME_MEASURED`, and the driver refuses to start when the live
server disagrees with it, so the discrepancy cannot be inherited silently into the results.

## 4. The context-fit requirement

The amendment requires, for every arm and every call:

```
prompt_envelope + 4096 + 256  <=  per_slot_context
```

Envelopes were rendered offline and then **measured** against the live tokeniser with
`max_tokens=1` calls (Ollama 0.32.5 exposes no tokenizer endpoint). Calibration calls
occupy a different cache key from run calls — the key includes `max_tokens` — so they
cannot be replayed in place of scientific data.

Call-two envelopes are **upper bounds**: the carried body is synthetic and sized as a
completion that consumed the entire 4096-token allowance.

| arm | stage | task | chars | measured prompt tokens | required | headroom vs 16384 | fits |
|---|---|---|---:|---:|---:|---:|---|
| SE | initial | `v1b_23` | 1,667 | 405 | 4,757 | 11,627 | yes |
| SE | review | `v1b_23` | 19,273 | 3,323 | 7,675 | 8,709 | yes |
| HML-V1 | initial | `v1b_23` | 4,400 | 1,199 | 5,551 | 10,833 | yes |
| HML-V1 | repair | `v1b_23` | 13,688 | 6,505 | 10,857 | **5,527** | yes |

Full record: `evaluation/results/v1_benchmark/ENVELOPE_CALIBRATION.json`.

**The two-slot arrangement fits the largest matched envelope with 5,527 tokens to spare, so
the single 32,768-token slot is not required and the server is not restarted.**

### A correction made during calibration

The first calibration attempt sized the synthetic carried bodies in *characters*, at an
assumed 5.0 chars/token. Measured, HML-like source tokenises at ~2.1–3.0 chars/token, so a
filler intended to represent 4,096 tokens actually measured ~6,800. That bound was not
conservative, it was **incoherent** — it modelled a completion the allowance forbids, and
it produced a false `EXCEEDS` verdict against the 16,384 slot. Fillers are now sized in
tokens at the ratio each text shape actually measures. The over-conservatism that remains
is in the safe direction and is retained.

## 5. A defect found and fixed before any scientific call

### Unbounded compiler diagnostics

`classify_diagnostics()` renders the entire diagnostic bag, and that rendering is
**unbounded relative to the module that produced it**. Measured on this compiler:

| module | source | rendered | ratio |
|---|---:|---:|---:|
| 200 unresolved names | 9,469 ch | 59,760 ch | 6.3× |
| 200 type errors | 6,289 ch | 34,070 ch | 5.4× |
| 200 parse errors | 2,289 ch | 52,580 ch | 23.0× |
| **200 lines of garbage** | 3,199 ch | **389,426 ch** | **121.7×** |

389,426 characters is roughly 130,000 tokens. It overflows a 16,384 slot eightfold and a
32,768 slot fourfold, so **no context size solves this**.

An over-long prompt does not raise — it truncates. The repair call would have been made
against a mutilated prompt, and the mutilation would have been worst **exactly where the
model wrote the worst HML**. Once again the artefact is anti-correlated with the treatment.

**Fix:** `evaluation/v1_benchmark/diagnostics_budget.py` caps rendered diagnostics at 6,000
characters and 40 diagnostics, on whole-line boundaries, always appending an explicit count
of what was omitted — the behaviour every production compiler has.

**Why the cap is not a thumb on the scale.** It can only *remove* information from the
treatment arm, never add any. Whenever it binds, HML-V1 receives **less** help than it
otherwise would, so a positive HML result measured under this cap is a **lower bound** on
what an uncapped run would have produced. Every record carries `truncated` and `omitted`
so a reviewer can count exactly when it bound and on which tasks.

Regression tests: `tests/evaluation/test_diagnostics_budget.py` (9 tests, all passing),
including a test that pins the unbounded behaviour of the underlying renderer so the
premise for the cap cannot silently lapse.

## 6. A matched asymmetry, recorded rather than corrected

Neither arm's second call re-supplies its format guidance: `se_review_prompt` omits
`SCHEMA_A_PRIME` and `hml_repair_prompt` omits `HML_SPEC`. Calls carry no conversation
history, so on call two **both** arms are working without their format specification in
context.

This is **matched**, and it is left exactly as frozen. It is recorded here because
`hml_repair_prompt` still accepts a `surface_spec` parameter that it never uses, which
reads like a defect and is not one — removing the parameter would be a change to the frozen
contract for no measurement benefit. It does mean the HML arm repairs a module in a
language whose specification it cannot see, which is a genuine handicap on the treatment
arm and is noted as a limitation, not fixed.

## 7. What this protocol cannot claim

- It is **not** the untouched original configuration, and no report derived from it may say
  it is.
- The amendment is a developmental one, taken to obtain a usable signal on a private
  research question. It is not a publication-grade pre-registration.
- Raising the ceiling removes a truncation artefact. It does not make the measurement
  fair in any other respect; the unmatched dimensions recorded in `arms.MATCHING`
  (prompt length, notation familiarity) are unchanged and still bias **against** HML-V1.
