# M1 final audit — reproducibility and stability

**Subject:** commit `9afafa8ada6edf54f92d26b56f6620c9558e5cb6`, tag
`hml-m1-constitutional-core`, branch `hml-v1-concept-kernel`.
**Date:** 2026-08-05. **Purpose:** decide whether M1 is a stable enough base to spend
model tokens on. No model call was made during this audit.

**Verdict: M1 passes.** Every gate criterion was met, twice, in checkouts that share no
untracked file with this machine's working copy.

Two things qualify that verdict and neither changes it. First, the *working tree* was red
at the time of writing — see [§7](#7-the-live-working-tree-is-not-m1). Second, a real
thread-safety defect exists in the canonical form; it cannot fire under `pytest -n 18`
and does not fire on any path in use today, but it is live and it is silent — see
[§5.1](#51-hazard-1--the-canonical-form-hangs-on-a-process-global).

## 1. Gate criteria

| criterion | result |
|---|---|
| five consecutive full parallel passes | **10/10** on the host, **5/5** in the clean room |
| ten consecutive hypothesis-isolation passes | **10/10** on the host, **10/10** in the clean room |
| remote clone reproduces conformance | **yes** — `CONFORMANCE: PASS`, 8/8 stages |
| bundle verifies and restores | **yes** — `git bundle verify` clean, restores to the same tree |
| local SHA = remote SHA | **yes** — `9afafa8`, and the peeled tag agrees |

## 2. Lineage — verified independently

Full detail, with the commands and their real output, is in
[`EXPERIMENT_LINEAGE.md`](EXPERIMENT_LINEAGE.md). Every claim handed to this audit was
re-derived rather than accepted:

- `HEAD` = `origin/hml-v1-concept-kernel` = `hml-m1-constitutional-core^{}` = `9afafa8…`
- repository visibility `PRIVATE`
- working tree clean **at the start of the audit** (it did not stay that way)
- bundle 1 497 725 bytes, SHA-256 `053bd934c1ebb3c5e009d146d66eb5fd59b47a07e3c72476e34c56b532bf224e`

All four match what was handed over. The tree object `9ee9b4d523d5f92f87107a35646f99aaaec1b199`
is identical in this working copy, in a fresh clone of the remote, and in a clone of the
bundle.

## 3. Stability under parallel execution

Every run below is a separate process invocation with `-p no:cacheprovider`, so no run
inherits another's cache.

| what | where | runs | result |
|---|---|---|---|
| `pytest -q -n 18` | host, tree clean at `9afafa8` | 5 | 5/5 reached 100%, zero `F`/`E` markers † |
| `pytest -n 18` | host, tree clean at `9afafa8` | 5 | 5/5 exit 0, `3974 passed, 4 skipped, 1 xfailed` each |
| `pytest -n 18` | clean room restored **from the bundle** | 5 | 5/5 exit 0, identical counts |
| `test_hypothesis_separation.py -n 18` | host | 10 | 10/10 exit 0, `17 passed` each |
| `test_hypothesis_separation.py -n 18` | clean room | 10 | 10/10 exit 0, `17 passed` each |
| `HML_JOBS=1 pytest tests/evaluation/test_syntax_gate_harness.py` | host | 1 | `28 passed` |
| `HML_JOBS=1 …` (serial escape hatch) | clean room | 1 | `28 passed` |
| `pytest` fully serial, no xdist | clean room | 1 | identical counts |
| `pytest -n 18 --dist loadfile` | clean room | 1 | identical counts |

† The first batch was run before `stability_runs.sh` existed, with `-q` on the command
line on top of the `-q` already in `addopts`. At `-qq` pytest prints no summary line, and
the loop's `PIPESTATUS` did not survive the shell, so those five runs are evidenced by the
absence of any failure marker in their captured output rather than by a recorded exit
code. Every other run in this table has its exit code recorded. Treat the host figure as
**5 runs with verified exit status plus 5 with verified output**.

The serial escape hatch — which regressed once before, when `HML_JOBS` was read by
`evaluation/syntax_gate/harness.py` and throttled `SCORING_WORKERS` to 1 — is intact.

Three distribution strategies (serial, `--dist load`, `--dist loadfile`) produce
byte-identical outcome counts. Combined with CPython's per-process hash randomisation,
which reshuffles set and dict iteration order on every run, that is reasonable evidence
of no ordering dependence in the current suite.

**A caveat on what "5/5 green" proves.** The suite is not deterministic between runs:
Hypothesis is not derandomised, so property tests draw fresh examples each time. Fifteen
green runs are evidence of stability under nondeterminism, not proof of determinism. A
hazard with a narrow window can still be sitting in the suite unobserved — which is why
§5 hunts mechanisms rather than counting green runs.

## 4. Rebuilding from the remote, and from the bundle

Two clean rooms, neither of which can see an untracked file from this machine.

**From the remote.** `git clone` of the private repository, `git checkout
hml-m1-constitutional-core` → `9afafa8`, tree `9ee9b4d`.

- constitutional tests, declared `dev` extra only: **72 passed**
- full suite, declared `dev` extra only: **3946 passed, 21 skipped, 1 xfailed**
- full conformance: **CONFORMANCE: PASS**, all 8 stages
- with `sympy` and `pytest-xdist` added: **3974 passed, 4 skipped, 1 xfailed** — exactly
  the host result — and conformance PASS on all 8 stages including `pytest (-n 18)`

**From the bundle.** `git bundle verify` reports *okay* and *records a complete history*;
9 refs, including `refs/heads/hml-v1-concept-kernel` at `9afafa8` and the annotated
`refs/tags/hml-m1-constitutional-core` peeling to `9afafa8`. `git clone` from the bundle
restores to the same tree, `git fsck` is clean, and the working tree differs from the
remote clone only by build artefacts (`__pycache__`, `.hypothesis`). Five consecutive
`-n 18` runs there: 5/5 green.

### 4.1 Finding — a green conformance line does not pin an environment

The declared `dev` extra omits `sympy` and `pytest-xdist`. Both routes above therefore
produce **two different green results** from one commit:

| install | outcomes | conformance |
|---|---|---|
| `pip install -e ".[dev]"` | `3946 passed, 21 skipped, 1 xfailed` | PASS |
| `+ sympy pytest-xdist` | `3974 passed, 4 skipped, 1 xfailed` | PASS |

Eleven tests are never collected without `sympy` (`tests/backends/test_sympy_execution.py`
is guarded by a module-level `pytest.importorskip`) and seventeen more skip. The gate
reports PASS either way. Without `pytest-xdist`, `scripts/conformance.sh` silently falls
back to a serial `pytest`.

This is not a gate failure — the milestone *does* reproduce — but it means "conformance
passed on a clean clone" is an ambiguous statement, and any result quoted from a fresh
clone has to name its environment. There is also **no lockfile**: the `dev` extra pins
only lower bounds, and drift is already measurable (`hypothesis` 6.165.0 here, 6.165.1 in
a clone made the same day).

`tests/reproducibility/test_recovery_lineage.py` keeps this honest mechanically: it fails
if a *new* undeclared hard dependency enters the suite, if an optional dependency is ever
imported unguarded, or if the recovery document stops naming its artefacts.

## 5. Concurrency hazard register

Two kinds of parallelism run in this repository and they fail differently. `pytest -n 18`
forks **processes**, so module globals are per-worker and the exposure is a shared
*filesystem path*. `evaluation/syntax_gate/scorer.py::score_many` uses a
**ThreadPoolExecutor** over `compile_source`, so the exposure there is a shared *module
global*. Both were hunted.

### 5.1 Hazard 1 — the canonical form hangs on a process global

> **RESOLVED 2026-08-05 by the Lead under D-024.** `_INCLUDE_NAMES` is now a
> `ContextVar`, so each thread holds its own value. Content hashes are byte-identical
> across the change (`bayesian_coin` `f79c553cca1adaa1…`, `quantifier_scope`
> `8250373bb23c814a…`, `kinetic_energy` `25efff792d32ccf0…`) and `tests/roundtrip` and
> `tests/golden` pass unchanged, so the fix is behaviour-preserving single-threaded.
> `test_the_canonical_form_still_hangs_on_a_process_global` has been **inverted** rather
> than deleted: it now fails if the global returns.
>
> One correction to the finding below. The stress reproduction is a **weak** guard: a
> deliberately reverted implementation survived 16 threads over a 2000-statement module
> in this session, and the original audit hit the window only once. The load-bearing
> guard is therefore structural — `test_the_include_names_flag_is_per_thread_by_construction`
> asserts the flag *is* a `ContextVar` and that a second thread does not observe this
> thread's setting. Verified against a simulated revert: it fires every run.
>
> The finding as originally written is preserved verbatim below.

**Status at time of audit: live, silent, currently unreachable. Not fixed by this audit**
— `src/` is outside this agent's ownership, and the fix touches the frozen semantic
contract, so it needs a `DECISIONS.md` record.

`src/hamiltonian_lang/backends/canonical.py` keeps `_INCLUDE_NAMES` as a module global.
`to_canonical` sets it, serialises, and restores it in a `finally`. That is safe against
*reentrancy* — a nested call restores the outer value — but not against *threads*:
`content_hash` forces the flag to `False` for the duration of its own serialisation, and
any other thread serialising *with* names at that moment silently emits the **nameless**
canonical form instead.

Reproduced on this host (CPython 3.14.6, GIL enabled):

```python
import sys, threading
sys.setswitchinterval(1e-6)                      # widen the window
from hamiltonian_lang import compile_source
from hamiltonian_lang.backends.canonical import canonical_json, content_hash

lines = (["module m"] + [f"var v{i} : Real" for i in range(400)]
         + [f"require v{i} > 0.0" for i in range(200)])
mod = compile_source("\n".join(lines) + "\n").module
named = canonical_json(mod, include_names=True)
# 8 threads looping content_hash(mod); 1 thread looping canonical_json(..., True)
# -> a mismatch appears within 400 calls.
```

Observed: `corrupted named canonical forms: 1`. At the default switch interval and with a
small module the window is narrow enough that 20 000 attempts produced none — which is
exactly why this has never been seen in the suite, and exactly why counting green runs
would not have found it.

There is no exception and no diagnostic. It produces an authoritative-looking canonical
form with the names removed. Section 8 of `CLAUDE.md` calls that the worst failure mode
in this codebase.

**Why it cannot fire today:** `score_many` is the only thread pool over the compiler, and
`score_trial` reaches `compile_source` and `render_module` but never `to_canonical`,
`canonical_json`, `content_hash`, `.hash()` or `.canonical()`.

**Guards added:** `tests/concurrency/test_shared_state_hazards.py`

- `test_the_scoring_thread_pool_never_reaches_canonical_serialisation` — fails the moment
  a scorer facet starts comparing canonical hashes, i.e. before the race can corrupt a
  measured result. It has a negative control, so it cannot pass vacuously.
- `test_the_compiler_paths_the_scoring_pool_does_use_are_thread_safe` — positive control:
  16 threads over every example must agree byte-for-byte with the serial answer.
- `test_the_canonical_form_still_hangs_on_a_process_global` — asserts the hazard is still
  present, so this register cannot go stale. **If someone fixes the global, that test is
  supposed to fail**; delete it and this entry together.

**Recommended fix (not applied):** thread the flag through `_sym`/`_params`, or hold it in
a `contextvars.ContextVar`. Either changes `backends/canonical.py`, which is contract, so
it needs a decision record.

### 5.2 Hazard 2 — a tracked file rewritten from inside a test

**Status: latent. Guarded.**

`tests/golden/test_golden.py::test_canonical_hashes_are_stable` reads
`tests/golden/hashes.json`, and when a key is missing it writes the whole dict back and
`skip`s. Under `-n 18` that is a lost update: every worker holding a missing key reads the
same file, adds its own key, writes — last writer wins. All but one new hash is discarded,
each of those tests reports `skip` rather than a failure, and the next run passes with
examples that have no tripwire at all. A golden file is a tripwire; a tripwire that can
silently lose entries is worse than none.

The branch is dead only while every example already has an entry. It does today: 8
examples, 8 keys, no gaps either way. `test_the_golden_tripwire_never_takes_its_write_branch_under_parallel_execution`
enforces exactly that precondition, so adding an example without blessing it now fails
loudly and deterministically in one place instead of racing.

### 5.3 Hazard 3 — environment variables that change what the suite checks

**Status: guarded.**

`HML_BLESS` disarms the golden tripwire *and* rewrites a tracked file. `HML_SCORING_WORKERS`
changes measured concurrency. `HML_JOBS` is `scripts/conformance.sh`'s serial escape hatch
and has already leaked into library code once. A suite whose verdict depends on the
inherited shell is not a suite.
`test_no_environment_knob_silently_changes_what_the_suite_checks` asserts none of them is
set; `test_the_conformance_gate_still_documents_its_serial_escape_hatch` asserts
`HML_JOBS` has not been re-claimed by `evaluation/syntax_gate/harness.py`.

### 5.4 Hazard 4 — `importlib.reload`

**Status: absent from tests. Guarded.**

Reloading rebinds every class a module defines, so a reloaded `PhaseGateError` is a
different class from the one sibling tests catch — which is how a previous repair broke a
neighbouring test. No test calls `importlib.reload` today; the supported technique is a
subprocess, and `tests/evaluation/test_syntax_gate_harness.py` uses one.
`test_import_time_constants_are_not_re_read_by_reloading` keeps it that way.

### 5.5 Generic scan — repository-rooted writes from tests

`test_no_test_module_writes_to_a_path_rooted_in_the_repository` walks every
`tests/**/test_*.py`, finds module constants derived from `__file__`, and flags writes
through them. One offender exists — `GOLDEN` in `tests/golden/test_golden.py` — and it is
allowlisted next to the invariant from §5.2 that makes it safe. The detector has a
negative control.

### 5.6 Examined and cleared

- `evaluation/syntax_gate/harness.py` writes raw logs under `RAW_DIR` inside the repo, but
  `append_raw` opens `"a"` only and every test call passes `raw_dir=tmp_path`.
- `tests/freeze/test_syntax_gate_freeze.py` monkeypatches `F.OUT` to `tmp_path` before
  writing any manifest, so no test can arm the real Phase F4 freeze gate.
- `tests/improvement/test_ledger.py` writes only under `tmp_path`.
- `backends/REGISTRY` is populated once at import; `available()` returns `sorted(...)`.
- `.hypothesis/examples` was empty throughout, so no stored failing example was being
  replayed between runs.
- `evaluation/syntax_acquisition/gate.py` uses a `ProcessPoolExecutor`, which does not
  share globals.

## 6. What this audit did not do

- **No model or Ollama call.** By instruction, and because the phase gate forbids one
  before the Phase F4 freeze.
- **No commit, no push.** The Lead owns those.
- **No fix to hazard 1.** `src/` is owned by other agents this session and the change is
  contract-level.
- **No repeated-run measurement of the mutation or fuzz suites in isolation.** They ran
  inside all 15 full-suite runs, never separately.
- **No second host.** Every result is from one 18-core Apple Silicon machine. Nothing here
  supports a claim about any other platform.

## 7. The live working tree is not M1

M1 is `9afafa8`. The **working tree** drifted during this audit as other agents committed
nothing but edited freely. Sequence, as observed:

1. audit start — `git status` clean, tree at `9afafa8`; the 10 host runs in §3 were taken
   here and were green;
2. mid-audit — `src/hamiltonian_lang/improvement/{episodes,memory,state}.py` modified;
   full suite went to **12 failures**, including
   `tests/improvement/test_hypothesis_separation.py::test_the_three_hypotheses_are_distinct_values_and_stay_that_way`
   (`assert [h.value for h in Hypothesis] == ["H1","H2","H3"]` failing with
   `['ACQ0','H1',…,'EXCLUDED']`) and 11 `TypeError: Episode.__init__() got an unexpected
   keyword argument 'training_eligible'`;
3. later — `evaluation/syntax_gate/{candidates,mutations,scorer}.py` modified; three test
   modules stopped collecting entirely with `NameError: name 'lru_cache' is not defined`.

This is in-flight work by concurrent agents, not M1 instability: the same commit is green
five times over in two pristine clean rooms. But two points need the Lead's attention:

- **The H1/H2/H3 separation invariant is currently failing.** Widening the `Hypothesis`
  enum with `ACQ0` and `EXCLUDED` may well be correct, but `test_hypothesis_separation.py`
  exists precisely so that widening cannot happen silently. It has to be resolved
  deliberately, with a decision record, before M2/M3 results are attributed to a
  hypothesis.
- **A missing `lru_cache` import** in the syntax-gate package is breaking collection of
  `test_syntax_gate_{scorer,harness,partition}.py`. It is almost certainly a half-finished
  edit, but conformance cannot pass while it stands.

Neither is a reason to withhold the M1 gate. Both are reasons not to run the tournament
against the working tree until they are closed.

## 8. Reproducing this audit

```bash
scripts/reproducibility/stability_runs.sh 5  full-parallel -n 18 -p no:cacheprovider
scripts/reproducibility/stability_runs.sh 10 hyp tests/improvement/test_hypothesis_separation.py -n 18 -p no:cacheprovider
HML_JOBS=1 .venv/bin/python -m pytest tests/evaluation/test_syntax_gate_harness.py
.venv/bin/python -m pytest tests/concurrency tests/reproducibility
```

`stability_runs.sh` exists because `pyproject.toml` already puts `-q` in `addopts`: adding
another `-q` on the command line suppresses the summary line, and a naive repeat-run loop
then records no evidence of what happened. It captures each run's real exit code and real
summary, one log per run. `HML_PYTHON` points it at a different interpreter, which is how
the clean-room runs were driven.
