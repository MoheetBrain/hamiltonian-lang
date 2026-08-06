# Execution environment and measured tuning

Host tuning for HML-PHASE-FG-001. Every number below was measured on this machine, not
estimated. This document is part of the Phase F4 execution manifest.

## Hardware

| | |
|---|---|
| CPU | 18 physical cores / 18 logical (Apple Silicon) |
| RAM | 52 GB unified |
| model | `gemma4:31b`, 19 GB on disk, ~20 GB resident, 100% GPU |
| Ollama | 0.32.5, OpenAI-compatible endpoint on `localhost:11434` |

## The 18 cores do not accelerate the tournament

The tournament is model-call bound, and a 31B model resident in GPU/unified memory does
not use the CPU cores for decode. CPU parallelism helps the **offline** work (Phase F3
round-trips, the test suite); it does nothing for Phases G2–G4.

## Finding 1 — stock Ollama serialises every request

Ollama's `llama-server` was running with `-np 1` (one parallel slot). Concurrent client
threads queue behind a single slot:

```
OLLAMA_NUM_PARALLEL unset  (-c 32768 -np 1)
workers= 1  n= 2  wall=  5.9s  per_call=3.0s  agg_tok/s=21.7
workers= 2  n= 4  wall= 11.0s  per_call=2.7s  agg_tok/s=23.3
workers= 4  n= 8  wall= 22.1s  per_call=2.8s  agg_tok/s=23.1
workers= 6  n=12  wall= 33.2s  per_call=2.8s  agg_tok/s=23.1
```

Wall time is exactly linear in `n` (12 x 2.8s = 33.2s) and aggregate throughput is pinned
at ~23 tok/s. **Adding client workers to a stock server buys nothing.**

## Finding 2 — four batching slots give 2.08x, and eight workers is worse than four

Decode on a 31B model is memory-bandwidth-bound: each token requires streaming the whole
weight set. Batching amortises that read across concurrent sequences.

```
OLLAMA_NUM_PARALLEL=4  (-c 32768 -np 4, 8192 ctx per slot)
workers= 1  n= 3  wall= 21.1s  per_call=7.0s  agg_tok/s=22.8  speedup=1.00x
workers= 2  n= 6  wall= 27.3s  per_call=4.6s  agg_tok/s=35.1  speedup=1.54x
workers= 4  n=12  wall= 40.5s  per_call=3.4s  agg_tok/s=47.4  speedup=2.08x   <- optimum
workers= 8  n=24  wall=117.5s  per_call=4.9s  agg_tok/s=32.7  speedup=1.43x   <- degrades
```

Client concurrency **must equal the slot count**. Oversubscribing past four slots forces
requests to queue while still competing for bandwidth, and throughput falls back to
1.43x. The harness therefore pins `max_workers = OLLAMA_NUM_PARALLEL = 4`.

## Finding 3 — the context budget is split across slots

`-np 4` divides the 32768-token context into four 8192-token slots. The 50-demonstration
curriculum is the longest prompt in the tournament and **must be measured against the
8192 per-slot budget, not the 32768 total**.

> **SUPERSEDED for ACQ0 — see `docs/evaluation/ACQ0_CONTEXT_BUDGET.md`.**
> The table below is a real measurement and is preserved as one. It is **not
> authoritative for the syntax tournament or for ACQ0**, because it was measured on the
> legacy V0 material in `benchmarks/representations/` and **not on the frozen
> syntax-gate curricula those experiments actually use**. The frozen curricula are
> several times larger: at 50 demonstrations, candidate A estimates at ~9,857 tokens and
> candidate D at ~35,321 — against the 5,893 recorded here. The caveat two paragraphs
> below ("if the frozen curricula are materially longer, re-measure before Phase G2")
> has therefore **triggered**, and no curriculum above 5 demonstrations should be assumed
> to fit any slot.

Measured with Ollama's own `prompt_eval_count` (not a chars-per-token estimate), building
curricula from the 24 paired English/HML demonstrations in `benchmarks/representations/`:

| demos | chars | prompt tokens | vs 8192 slot |
|------:|------:|--------------:|---|
| 0 | 250 | 66 | fits |
| 5 | 2,504 | 643 | fits |
| 10 | 5,308 | 1,286 | fits |
| 25 | 12,319 | 2,967 | fits |
| **50** | **24,592** | **5,893** | **fits — ~2,300 tokens left for completion** |

**`-np 4` is therefore safe for every curriculum size**, and the 2.08x speedup applies to
the whole tournament. Growth is close to linear at ~117 prompt tokens per demonstration.

Two caveats. The completion headroom at 50 demonstrations is ~2,300 tokens; an HML encoding
is well under that, but a verbose reasoning channel could approach it, so G2 must record
truncation as a distinct failure category rather than as a parse failure. And these figures
come from the existing V0 demonstration material — **if the frozen curricula are
materially longer, re-measure before Phase G2.** If a curriculum ever fails to fit, drop to
`OLLAMA_NUM_PARALLEL=2` (16384 per slot, still 1.54x). Never truncate a curriculum: a
truncated curriculum is a different experimental condition.

## Required server configuration

```bash
OLLAMA_NUM_PARALLEL=4 OLLAMA_KEEP_ALIVE=4h OLLAMA_CONTEXT_LENGTH=8192 ollama serve
```

`OLLAMA_KEEP_ALIVE=4h` prevents a 19 GB reload between phases; the first cold load took
over 120 seconds and would otherwise be charged to whichever call happened to trigger it,
corrupting the latency measurements.

Setting the variables and restarting is **required**: `launchctl setenv` and exporting in
a shell both failed here because Ollama.app respawns its own server process that does not
inherit them. The app must be quit (`osascript -e 'quit app "Ollama"'`) and the port
confirmed free before `ollama serve` is started manually. Verify with:

```bash
ps aux | grep "[l]lama-server" | grep -o -E "\-c [0-9]+ \-np [0-9]+"
```

This must print `-c 32768 -np 4`. **To restore stock behaviour, relaunch Ollama.app.**

## Offline parallelism (where the 18 cores do pay)

| stage | before | after | change |
|---|---|---|---|
| `pytest` full suite | 13.3s | 6.5s | `-n 18` via `pytest-xdist` |
| conformance `examples check` | serial loop | `xargs -P 18` | |

`scripts/conformance.sh` honours `HML_JOBS`; `HML_JOBS=1` forces a serial run, which is
required when diagnosing an ordering-dependent test failure because `-n` hides it.

Phase F3 renders and re-parses 500+ canonical objects in four syntaxes — 2000+ independent
round-trips. That is process-parallel across 18 cores and is where the core count matters.
