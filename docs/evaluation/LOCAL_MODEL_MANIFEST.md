# Local Model Manifest

Every field below was read from a local command, not inferred. The command that produced
each block is shown. Nothing here is derived from file size where Ollama can report it
directly.

Captured: 2026-08-04.

## 1. Identity

`ollama --version` → **`ollama version is 0.32.5`**

`curl -s http://localhost:11434/api/tags`:

| field | value |
|-------|-------|
| name / model | `gemma4:31b` |
| digest | `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7` |
| format | `gguf` |
| family | `gemma4` |
| parameter_size | `31.3B` |
| quantization_level | `Q4_K_M` |
| size on disk | `19868981791` bytes = **19.87 GB (18.50 GiB)** |
| modified_at | `2026-07-29T08:50:20+01:00` |

`ollama show gemma4:31b`:

| field | value |
|-------|-------|
| architecture | `gemma4` |
| parameters | `31.3B` — **reported by Ollama, not inferred from the 19.87 GB file** |
| **context length** | **`262144`** |
| embedding length | `5376` |
| quantization | `Q4_K_M` |
| requires | ollama ≥ `0.20.0` |
| licence | Apache License 2.0 |

### A discrepancy, recorded rather than resolved

`ollama show` lists capabilities `completion, vision, tools, thinking`.
`/api/tags` lists `completion, tools, thinking` — **no `vision`**.

The two endpoints disagree. Nothing in this study uses images, so it does not affect any
result, but it is recorded because an unexplained inconsistency in a source of truth is
worth knowing about before it matters.

## 2. Generation APIs

Both are available and both were exercised.

| API | endpoint | reasoning field | token fields |
|-----|----------|-----------------|--------------|
| OpenAI-compatible | `POST /v1/chat/completions` | `choices[0].message.reasoning` | `usage.prompt_tokens`, `usage.completion_tokens` |
| Ollama native | `POST /api/generate` (`"think": true`) | top-level `thinking` | `prompt_eval_count`, `eval_count` |

The native API additionally returns `total_duration`, `load_duration`,
`prompt_eval_duration` and `eval_duration` in nanoseconds, which is a more precise latency
source than wall-clock timing around `curl`.

## 3. Reasoning is returned separately — and is billed to completion tokens

**Yes, separately.** Verified on both APIs.

OpenAI-compatible, prompt `"Reply with only: OK"`, `temperature=0`:

```
content         = 'OK'          (2 characters)
reasoning       = 121 characters
prompt_tokens   = 21
completion_tokens = 43
```

**43 completion tokens produced 2 characters of content.** The reasoning trace is billed to
`completion_tokens` but does not appear in `content`.

Native API, `"think": true`, prompt `"What is 6*7? Answer only the number."`:

```
response = '42'
thinking = present, 133 characters
eval_count = 46
```

### Consequences for this study, stated now

1. **Any token-efficiency comparison must say which channel it counts.** Comparing
   `completion_tokens` across arms compares reasoning-plus-answer, not answer.
2. **`max_tokens` can be consumed entirely by reasoning**, yielding empty content. This is
   the confirmed cause of the 6 empty outputs in 105 cells during HML-EVAL-001, which
   concentrated on a single hard problem.
3. **The model decomposes internally in every arm.** Any structured-prompting manipulation
   is competing with something the model already does, which compresses scaffolding
   contrasts toward the null.

## 4. Sampling

Model defaults reported by `ollama show`:

| parameter | default |
|-----------|---------|
| temperature | `1` |
| top_k | `64` |
| top_p | `0.95` |

These defaults are **not** used. Every study fixes sampling explicitly and records it per
call, because a default that changes between Ollama versions would silently change results.

## 5. Latency

`temperature=0`, trivial prompt (21 prompt tokens, 43 completion tokens), wall-clock around
`curl`:

| call | wall time |
|------|-----------|
| 1 (cold — model load) | **8.03 s** |
| 2 (warm) | **1.96 s** |
| 3 (warm) | **1.96 s** |

Native API on the same class of prompt: `total_duration` 2.27 s, of which
`load_duration` 0.22 s.

**Cold-start cost is ≈ 6 s**, paid once per model load.

### Realistic latency is an order of magnitude higher

The trivial-prompt figures are not representative. On HML-EVAL-001's real prompts
(1200–1700 prompt tokens, ~1000 completion tokens) the measured range was **57–100 s per
call**, and it degraded within a long run — the first cells averaged ~57 s and later cells
reached 98–187 s.

**Plan compute from 60–120 s per call, not from 2 s.** A 320-call exploratory study is
5–10 hours, not minutes.

## 6. Determinism

`temperature=0` produced byte-identical `content`, identical `reasoning` length and
identical token counts across three consecutive calls. Temperature 0 is therefore usable as
a deterministic condition, and repeated generations at temperature 0 carry **no** independent
information — any multi-generation design must use temperature > 0 for the stochastic arm.

## 7. Configuration used by the adapter

```
base_url    http://localhost:11434/v1     (OpenAI-compatible)
model       gemma4:31b
digest      6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7
timeout     900 s per request
retries     2, exponential backoff, on transport error or empty content only
cache key   sha256(model | digest | temperature | top_p | max_tokens | seed | system | user)
```

Raw responses are written once and **never overwritten**. A cache hit replays the stored
response; it never re-queries. Re-running a study therefore costs nothing for calls already
made, and cannot silently produce different data for the same inputs.
