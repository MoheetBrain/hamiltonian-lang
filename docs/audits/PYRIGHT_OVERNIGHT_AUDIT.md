# Pyright overnight audit — 2026-08-06

**Starting SHA** `4f9e6fa` · **Pyright** 1.1.411 · **Python** 3.11 target, 329 files.

Run under a live experiment: the eval001 headroom screen owned Ollama throughout
(PID 38523, ~250/285 calls at the time of writing). No model call was made, no experiment
file was touched, and nothing consumed by the running process was modified.

## What was actually wrong with the baseline

**There was no Pyright configuration at all.** No `pyrightconfig.json`, no
`[tool.pyright]`. Pyright could not see `.venv`, so it reported 126 missing imports for
packages that are installed and import fine at runtime:

| module | count | | module | count |
|---|---|---|---|---|
| pytest | 99 | | numpy | 5 |
| sympy | 7 | | scipy(+.optimize) | 7 |
| hypothesis | 6 | | tiktoken | 1 |

That is not a code defect, and it is worse than one: every file carrying an unresolved
import has its real analysis degraded, so the other 358 diagnostics were being computed
against a partly-blind view of the codebase.

## Baseline table

| rule | baseline | after config | disposition |
|---|---|---|---|
| reportArgumentType | 218 | 217 | mostly tests; **not yet triaged** |
| reportMissingImports | 126 | 13 | **C — configuration**, resolved |
| reportOptionalMemberAccess | 43 | 44 | **A/E** — see below |
| reportPossiblyUnboundVariable | 29 | 29 | **B — likely defect**, not yet triaged |
| reportAttributeAccessIssue | 25 | 31 | not yet triaged |
| reportOperatorIssue | 15 | 15 | not yet triaged |
| reportAssignmentType | 10 | 10 | not yet triaged |
| reportUnsupportedDunderAll | 5 | 5 | **1 REAL_DEFECT (fixed)**, rest dynamic |
| reportCallIssue / ReturnType / GeneralTypeIssues / OptionalOperand | 18 | 14 | not yet triaged |
| **total errors** | **484** | **374** | |

Counts rose slightly in two rules after configuration — that is expected and healthy:
resolving the imports let Pyright see types it previously could not, so it found more.

### Where the diagnostics live

`tests/` 336 · `src/hamiltonian_lang` 61 · `evaluation` 82. Within `src`, the critical path
is nearly clean; the concentration is in `equivalence/` (52 of 58), which is **not** on the
current critical path (compiler → ACQ0 → surface → benchmark → H2).

## Confirmed defects

### 1. Stale re-export in `hamiltonian_lang.verification` — REAL_DEFECT, fixed

`__init__.py` declared `__all__ = ["obligations"]` and never imported the submodule.
Confirmed at runtime, not merely by the checker:

```
__all__: ['obligations']
  MISSING at runtime: obligations
star-import: OK        <- binds nothing, appears to succeed
```

`verification.obligations` raised `AttributeError` unless some other module had already
imported it, and `from hamiltonian_lang.verification import *` silently bound nothing. This
is defect class 10 (a stale re-export exposing an outdated interface), and it is on the
critical path — the obligations engine is the verifier.

**Fix:** import the submodule so the declared export is real. Behaviour-preserving; it only
makes a promise the package already made come true.

**Test:** `tests/verification/test_package_exports.py` walks every package under
`hamiltonian_lang` and asserts each `__all__` entry exists — 19 packages, all passing. The
class is now closed, not just this instance.

### 2. `equivalence/sympy_bridge.py` — E, INTENTIONAL_DYNAMIC_BOUNDARY

21 diagnostics of the form `"Symbol" is not a known attribute of "None"`. The module does
`try: import sympy / except ImportError: sympy = None`, so Pyright is correct that every
use is `None`-typed. Whether each use sits behind a runtime guard was **not verified** —
that is the first thing to check tomorrow, because if any use is unguarded it converts from
class E to class A. Not on the critical path.

### 3. `repair/record.py:329-334` — LIKELY_DEFECT, not fixed

`.status` and `.error_class` accessed on a `RetrievedContext | None`, and the same optional
passed to a parameter typed `RetrievedContext`. This is defect class 1 (a value can be
`None` but downstream assumes it exists) on an experiment-record type. **Not investigated
far enough to fix safely** — it needs the reference search and a reproducing test first.

### 4. `improvement/verification.py:601` — UNCERTAIN

`"Never" is not iterable`. Consistent with an exhaustiveness construct Pyright has narrowed
to `Never`; could be correct code or a real dead branch. Not triaged.

## Not done

The directive's sections 2–5 (semantic interface mapping, the ordered-view/reconstruction
type audit, the public/private firewall typing, experiment-record invariants, verdict
exhaustiveness, H2 benchmark typing) were **not** executed. 374 diagnostics remain, of which
only the `reportMissingImports` class and one `reportUnsupportedDunderAll` have been
dispositioned. No suppression was added anywhere, no type was weakened, no mode was lowered.

The reason is plain: this session reached its context limit. Stopping with one verified fix
and an honest baseline is better than a batch of unverified edits made while running out of
room to check them.

## Verification actually executed

| command | result |
|---|---|
| `pyright` baseline | 484 errors, 9 warnings, 329 files |
| `pyright` after config | **374 errors, 7 warnings** |
| `ruff check` (changed files) | All checks passed |
| `mypy src` | Success, 84 source files |
| `pytest tests/verification` | 135 passed |
| `pytest tests/verification/test_package_exports.py` | 19 passed |

Full pytest and conformance were **not** re-run: the source change is a single import, and
the targeted suite covers it. They should run before this is treated as complete.

## Three highest-ROI next actions

1. **Triage the 29 `reportPossiblyUnboundVariable`.** This class is the likeliest source of
   a real runtime `UnboundLocalError` and it is cheap to adjudicate — each one is a branch
   where a name is bound on some paths only.
2. **Finish `repair/record.py`** (defect 3). It is a concrete optional-access defect on an
   experiment-record type, which is exactly the class the directive ranks first.
3. **Decide whether `equivalence/` is in scope at all.** 52 of the 58 `src` diagnostics are
   there, it is off the critical path, and if it stays off, the honest move is to say so in
   the config rather than carry 52 diagnostics that nobody will act on.
