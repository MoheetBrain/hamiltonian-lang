# Experiment lineage and recovery

What this experiment is anchored to, and how to get it back if this machine is gone.

Everything below was verified on 2026-08-05 by re-executing the commands shown. Nothing
is asserted from memory. Where a command was not run, it says so.

## The anchor

| | |
|---|---|
| repository | `https://github.com/MoheetBrain/hamiltonian-lang` (**PRIVATE**) |
| branch | `hml-v1-concept-kernel` |
| milestone commit | `9afafa8ada6edf54f92d26b56f6620c9558e5cb6` |
| milestone tag | `hml-m1-constitutional-core` (annotated: `5ac8f7af43025ad43c19b94c5c1fa5adb058788d` → `9afafa8`) |
| tree object at M1 | `9ee9b4d523d5f92f87107a35646f99aaaec1b199` |
| recovery bundle | `../hamiltonian_lang_m1.bundle`, 1 497 725 bytes |
| bundle SHA-256 | `053bd934c1ebb3c5e009d146d66eb5fd59b47a07e3c72476e34c56b532bf224e` |

Verification commands, and their actual results:

```bash
git rev-parse HEAD
# 9afafa8ada6edf54f92d26b56f6620c9558e5cb6

git ls-remote origin | grep -E 'hml-v1-concept-kernel|hml-m1-constitutional-core'
# 9afafa8... refs/heads/hml-v1-concept-kernel
# 5ac8f7a... refs/tags/hml-m1-constitutional-core
# 9afafa8... refs/tags/hml-m1-constitutional-core^{}

gh repo view --json visibility
# {"visibility":"PRIVATE"}

shasum -a 256 ../hamiltonian_lang_m1.bundle
# 053bd934c1ebb3c5e009d146d66eb5fd59b47a07e3c72476e34c56b532bf224e

git bundle verify ../hamiltonian_lang_m1.bundle
# ../hamiltonian_lang_m1.bundle is okay
# The bundle contains these 9 refs ... The bundle records a complete history.
```

Local `HEAD`, `origin/hml-v1-concept-kernel` and the peeled M1 tag are the same commit.
The identical **tree** hash was observed in three independent checkouts — this working
copy, a fresh clone of the remote, and a clone of the bundle — which is what makes the
three interchangeable rather than merely similar.

One asymmetry worth knowing: the bundle carries a local `refs/heads/main` at `8359afc`
while `origin/main` is `965a7c7` ("Initial commit"). The local `main` has diverged from
the remote's. No M1 artefact depends on `main`; the milestone lives entirely on
`hml-v1-concept-kernel`.

## Recovery

Two independent routes, both executed and both successful.

### From the remote

```bash
git clone https://github.com/MoheetBrain/hamiltonian-lang.git repo
cd repo && git checkout hml-m1-constitutional-core     # -> 9afafa8, tree 9ee9b4d
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]" sympy==1.14.0 pytest-xdist==3.8.0
.venv/bin/python -m pytest -n 18                       # 3974 passed, 4 skipped, 1 xfailed
bash scripts/conformance.sh                            # CONFORMANCE: PASS (8/8 stages)
```

### From the bundle

```bash
git clone -b hml-v1-concept-kernel ../hamiltonian_lang_m1.bundle restored
# -> 9afafa8, tree 9ee9b4d, all three tags present, `git fsck` clean
```

The restored clone was then built and run exactly as above and produced the same
`3974 passed, 4 skipped, 1 xfailed`, five times consecutively under `-n 18`.

Neither route uses any untracked file from this machine. That was the point of running
both: the milestone is reproducible from version control alone.

## The dependency set is not fully declared

`pyproject.toml` declares `dev = ["pytest>=8", "hypothesis>=6", "ruff>=0.6",
"mypy>=1.11", "jsonschema>=4"]`. Two packages that the conformance result depends on are
**not** in it:

| package | how it is used | what its absence does |
|---|---|---|
| `sympy` | the SymPy backend and its execution tests | 11 tests are never collected, 17 more skip — **and the gate still reports PASS** |
| `pytest-xdist` | `scripts/conformance.sh` runs `pytest -n 18` | the script silently falls back to a serial run |

Measured, same tree, same commit, one clone each:

| install | result | conformance |
|---|---|---|
| `pip install -e ".[dev]"` only | `3946 passed, 21 skipped, 1 xfailed` | PASS |
| `+ sympy==1.14.0 pytest-xdist==3.8.0` | `3974 passed, 4 skipped, 1 xfailed` | PASS |

Both say PASS. The first ran 11 fewer tests. Anyone quoting a conformance result from a
fresh clone must say which of these two environments produced it.

`sympy` is reached only through `pytest.importorskip`, which is deliberate — its absence
should reduce coverage rather than break collection — but the reduction has to be
visible, which is what this section is for.
`tests/reproducibility/test_recovery_lineage.py` keeps it visible mechanically.

## There is no lockfile

`git ls-files` matches no lockfile, `requirements*.txt`, or constraints file. The `dev`
extra pins nothing but lower bounds, and the drift is already observable: `hypothesis`
resolved to `6.165.0` on this host and `6.165.1` in a clone made the same day.

Consequence: **the environment is reproducible only to the resolution of a version
range.** The commit is exactly reproducible; the interpreter and package set are not.
The exact host environment at M1 is recorded below so a future run can be compared
against it rather than guessed at.

| | |
|---|---|
| Python | 3.14.6 (GIL enabled) |
| pytest | 9.1.1 |
| pytest-xdist | 3.8.0 |
| hypothesis | 6.165.0 |
| sympy | 1.14.0 |
| jsonschema | 4.26.0 |
| ruff | 0.16.1 |
| mypy | 2.3.0 |

## Run-to-run determinism

The suite is **not** deterministic between runs, by design:

- Hypothesis is not `derandomize`d, so property tests draw different examples each run.
  The example database (`.hypothesis/examples`) was empty throughout the audit, so no
  failing example is being replayed from a previous run.
- CPython randomises string hashing per process, so set and dict iteration order differs
  between runs and between xdist workers.

Both were exercised: 15 full-suite runs across two machines-worth of checkouts produced
identical outcome counts. That is evidence of stability under nondeterminism, not
evidence of determinism, and the distinction matters if a failure ever needs to be
reproduced exactly. To reproduce a specific run, pin `PYTHONHASHSEED` and add
`derandomize=True` to the Hypothesis profile.
