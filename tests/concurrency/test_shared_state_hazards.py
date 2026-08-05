"""Concurrency hazards: the shared state that ``-n 18`` and thread pools can corrupt.

This file exists because of two incidents recorded in ``docs/PROJECT_LEDGER.md``:

* a test that failed *only* under ``-n 18`` and passed in isolation, and
* a repair that used ``importlib.reload``, which rebinds a module's exception classes so
  that a reloaded ``PhaseGateError`` is no longer the class a sibling test catches.

Both had the same shape: state that outlives one test. The tests below are the standing
guard against the remaining instances of that shape. Each one names the mechanism, not
just the symptom, because a symptom test goes green the moment the schedule changes.

Two kinds of parallelism are in play here and they fail differently:

* ``pytest -n 18`` forks **processes**. Module globals are per-worker, so the hazard is
  a *shared filesystem path* -- two workers reading and rewriting one tracked file.
* ``evaluation.syntax_gate.scorer.score_many`` uses a **ThreadPoolExecutor** over
  ``compile_source``. Threads share module globals, so the hazard is a *process-global
  flag* mutated mid-serialisation.

The guards below cover one of each.
"""

from __future__ import annotations

import ast
import inspect
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends import canonical as canonical_mod
from hamiltonian_lang.backends.hml import render_module

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"


def _example_files() -> list[Path]:
    return sorted(p for p in EXAMPLES.rglob("*.hml") if "candidate_syntaxes" not in p.parts)


# ---------------------------------------------------------------------------
# Hazard 1 -- a process-global flag inside the canonical form
# ---------------------------------------------------------------------------


def test_the_canonical_form_still_hangs_on_a_process_global():
    """``backends.canonical._INCLUDE_NAMES`` is module-global state, and that is a race.

    ``to_canonical`` sets the flag, serialises, and restores it in a ``finally``. That
    makes it safe against *reentrancy* -- a nested call restores the outer value -- but
    it is not safe against *threads*: ``content_hash`` forces the flag to ``False`` for
    the duration of its own serialisation, and any other thread serialising with names
    at that moment silently produces the nameless form instead.

    Reproduction (observed on this host, CPython 3.14.6, GIL enabled)::

        import sys, threading
        sys.setswitchinterval(1e-6)
        from hamiltonian_lang import compile_source
        from hamiltonian_lang.backends.canonical import canonical_json, content_hash
        lines = (["module m"] + [f"var v{i} : Real" for i in range(400)]
                 + [f"require v{i} > 0.0" for i in range(200)])
        mod = compile_source("\\n".join(lines) + "\\n").module
        named = canonical_json(mod, include_names=True)
        # 8 threads looping on content_hash(mod); one thread looping on
        # canonical_json(mod, include_names=True) -> a mismatch appears within 400 calls.

    The failure mode is the worst one this codebase recognises: no exception, no
    diagnostic, just an authoritative-looking canonical form with the names removed.

    MIGRATED 2026-08-05 by D-024, and the direction is now inverted.

    This test was written to assert the hazard was *still present*, so that the register
    in ``docs/evaluation/M1_FINAL_AUDIT.md`` could not silently go stale. It did its job:
    the fix could not land quietly, and it forced the decision record.

    The hazard is now CLOSED -- ``_INCLUDE_NAMES`` is a ``ContextVar``, so each thread
    holds its own value. Rather than delete the test, it now fails if the global ever
    returns. A closed hazard still deserves a guard.

    The deterministic guard lives in ``test_canonical_thread_safety.py``; this one keeps
    the hazard register honest.
    """
    from contextvars import ContextVar

    assert hasattr(canonical_mod, "_INCLUDE_NAMES"), (
        "backends.canonical._INCLUDE_NAMES is gone entirely. If the flag was threaded "
        "through _sym/_params instead, update this test and the hazard entry in "
        "docs/evaluation/M1_FINAL_AUDIT.md together."
    )
    assert isinstance(canonical_mod._INCLUDE_NAMES, ContextVar), (
        "the include-names flag is a process global again -- D-024 reverted. Concurrent "
        "content_hash can now silently strip names from another thread's canonical form."
    )
    src = inspect.getsource(canonical_mod.to_canonical)
    assert "global _INCLUDE_NAMES" not in src, (
        "to_canonical mutates a process global again; see D-024."
    )


#: Names that reach ``backends.canonical`` and therefore touch the process global.
_CANONICAL_NAMES = frozenset(
    {"to_canonical", "canonical_json", "content_hash", "hash", "canonical"}
)

#: Modules reachable from ``score_trial``, which ``score_many`` runs on worker threads.
_SCORING_PATH = (
    "evaluation/syntax_gate/scorer.py",
    "evaluation/syntax_gate/candidates.py",
    "evaluation/semantic_equiv.py",
    "evaluation/corpus/cso.py",
)


def _canonical_references(source: str, label: str) -> list[str]:
    """Every reference to canonical serialisation in ``source``, as ``label:line name``."""
    hits = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.Name):
            name = node.id
        else:
            continue
        if name in _CANONICAL_NAMES:
            hits.append(f"{label}:{node.lineno} references {name!r}")
    return hits


def test_the_canonical_reference_detector_is_not_vacuous():
    """Negative control. A detector that cannot fail is decoration."""
    assert _canonical_references("x = result.hash()", "synthetic")
    assert _canonical_references("content_hash(module)", "synthetic")
    assert _canonical_references("y = to_canonical(m, include_names=False)", "synthetic")
    assert not _canonical_references("x = compile_source(text).ok()", "synthetic")


def test_the_scoring_thread_pool_never_reaches_canonical_serialisation():
    """The live guard for hazard 1.

    ``score_many`` maps ``score_trial`` over a ``ThreadPoolExecutor``. Today that path
    reaches ``compile_source`` and ``render_module`` but never ``to_canonical``,
    ``canonical_json``, ``content_hash``, ``CompileResult.hash`` or
    ``CompileResult.canonical`` -- which is the only reason the process-global above has
    never fired in anger.

    If a scorer facet ever starts comparing canonical hashes, this test fails *before*
    the race can silently corrupt a measured result.
    """
    offenders: list[str] = []
    for rel in _SCORING_PATH:
        path = REPO / rel
        if not path.exists():
            continue
        offenders += _canonical_references(path.read_text(encoding="utf-8"), rel)
    assert not offenders, (
        "canonical serialisation reached from evaluation.syntax_gate.scorer.score_many, "
        "which runs on a ThreadPoolExecutor. backends.canonical._INCLUDE_NAMES is a "
        "process global (see the sibling test) and this path can now corrupt it "
        "silently:\n  " + "\n  ".join(offenders)
    )


def test_the_compiler_paths_the_scoring_pool_does_use_are_thread_safe():
    """Positive control for the guard above.

    ``score_trial`` runs ``compile_source`` and ``render_module`` on worker threads. Both
    must be pure with respect to shared state. Sixteen threads over every example must
    agree byte-for-byte with the serial answer; a disagreement means a global crept into
    the front end.
    """
    sources = [p.read_text(encoding="utf-8") for p in _example_files()]
    assert sources, "no examples found; this control would pass vacuously"

    def work(src: str) -> tuple[bool, str]:
        result = compile_source(src)
        return result.ok(), render_module(result.module) if result.module else ""

    serial = [work(s) for s in sources * 4]
    with ThreadPoolExecutor(max_workers=16) as pool:
        parallel = list(pool.map(work, sources * 4))
    assert parallel == serial, (
        "compile_source/render_module disagreed between serial and 16-thread execution; "
        "shared mutable state has entered the front end"
    )


# ---------------------------------------------------------------------------
# Hazard 2 -- a tracked file rewritten from inside a test
# ---------------------------------------------------------------------------


def test_the_golden_tripwire_never_takes_its_write_branch_under_parallel_execution():
    """``tests/golden/test_golden.py`` read-modify-writes a *tracked* file.

    ``test_canonical_hashes_are_stable`` loads ``tests/golden/hashes.json``, and when a
    key is missing it writes the whole dict back and skips. Under ``-n 18`` that branch
    is a lost update: every worker holding a missing key reads the same file, adds its
    own key, and writes -- last writer wins, so all but one new hash is silently
    discarded and each of those tests reports ``skip`` rather than a failure. The next
    run then passes with examples that have no tripwire at all.

    The branch is only dead while every example already has an entry. This test enforces
    exactly that precondition, so adding an example without blessing it fails here --
    loudly, deterministically, and in one place -- instead of racing.
    """
    golden = json.loads((REPO / "tests" / "golden" / "hashes.json").read_text())
    keys = {p.relative_to(REPO).as_posix() for p in _example_files()}
    missing = sorted(keys - set(golden))
    assert not missing, (
        "these examples have no golden hash, so tests/golden/test_golden.py would "
        "rewrite a tracked file from N xdist workers at once and lose all but one "
        "entry:\n  " + "\n  ".join(missing) + "\n"
        "Bless them deliberately: HML_BLESS=1 .venv/bin/python -m pytest tests/golden"
    )
    stale = sorted(set(golden) - keys)
    assert not stale, (
        "tests/golden/hashes.json carries entries for examples that no longer exist: "
        + ", ".join(stale)
    )


def test_no_environment_knob_silently_changes_what_the_suite_checks():
    """Environment leakage is a reproducibility failure, not a convenience.

    ``HML_BLESS`` disarms the golden tripwire *and* rewrites a tracked file.
    ``HML_SCORING_WORKERS`` changes measured concurrency. ``HML_JOBS`` is the documented
    serial escape hatch for ``scripts/conformance.sh`` and must never be read by library
    code -- it already leaked into ``SCORING_WORKERS`` once (ledger entry for
    ``9afafa8``). A suite whose verdict depends on the inherited shell is not a suite.
    """
    armed = [name for name in ("HML_BLESS", "HML_SCORING_WORKERS") if os.environ.get(name)]
    assert not armed, (
        f"{', '.join(armed)} set in the environment: this run does not check what an "
        "unconfigured run checks. Unset it and re-run."
    )


#: ``(test file, constant)`` pairs that write through a repository-rooted path and the
#: invariant that currently makes each one safe under ``pytest -n 18``.
_ALLOWED_REPO_WRITES = {
    # Guarded by test_the_golden_tripwire_never_takes_its_write_branch...: the write
    # branch is unreachable while every example already has a blessed hash.
    ("tests/golden/test_golden.py", "GOLDEN"),
}

_WRITE_METHODS = ("write_text", "write_bytes", "mkdir", "touch", "unlink", "open")


def _repo_rooted_writes(source: str, label: str) -> list[tuple[str, str]]:
    """Writes through a module constant derived from ``__file__``.

    Returns ``(constant name, "label:line CONST.method()")`` pairs.
    """
    tree = ast.parse(source)
    repo_rooted = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and "__file__" in ast.dump(node.value)
    }
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in _WRITE_METHODS:
            continue
        root = node.func.value
        while isinstance(root, ast.BinOp):  # PATH / "a" / "b"
            root = root.left
        if isinstance(root, ast.Name) and root.id in repo_rooted:
            hits.append(
                (root.id, f"{label}:{node.lineno} {root.id}.{node.func.attr}()")
            )
    return hits


def test_the_repo_rooted_write_detector_is_not_vacuous():
    """Negative control for the scan below."""
    offender = 'from pathlib import Path\nOUT = Path(__file__).parent / "x.json"\nOUT.write_text("1")\n'
    safe = 'def test_a(tmp_path):\n    (tmp_path / "x.json").write_text("1")\n'
    assert _repo_rooted_writes(offender, "synthetic")
    assert not _repo_rooted_writes(safe, "synthetic")


def test_no_test_module_writes_to_a_path_rooted_in_the_repository():
    """Mechanised hunt for the shared-output-file hazard.

    Any test that writes through a module-level constant derived from the repository
    root is a candidate for two xdist workers writing the same file. ``tmp_path`` and
    ``tmp_path_factory`` are per-test and per-worker, so they are safe; a constant such
    as ``GOLDEN = Path(__file__).parent / "hashes.json"`` is not.

    The one known offender is allowlisted with the reason it is currently safe, and the
    sibling test above enforces that reason.
    """
    offenders: list[str] = []
    for path in sorted((REPO / "tests").rglob("test_*.py")):
        rel = path.relative_to(REPO).as_posix()
        offenders += [
            hit
            for const, hit in _repo_rooted_writes(path.read_text(encoding="utf-8"), rel)
            if (rel, const) not in _ALLOWED_REPO_WRITES
        ]

    assert not offenders, (
        "test modules write through a repository-rooted constant. Under `pytest -n 18` "
        "several workers can hit the same file at once; use the `tmp_path` fixture, or "
        "allowlist it here with the invariant that makes it safe:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("module_name", ["evaluation.syntax_gate.harness"])
def test_import_time_constants_are_not_re_read_by_reloading(module_name: str):
    """``importlib.reload`` is banned as a way to re-read an import-time constant.

    Reloading rebinds every class the module defines, so a reloaded ``PhaseGateError`` is
    a *different* class from the one sibling tests catch with ``pytest.raises`` -- which
    is exactly how a previous fix broke a neighbouring test. The supported way to verify
    an import-time constant under a different environment is a subprocess, and
    ``tests/evaluation/test_syntax_gate_harness.py`` does that.
    """
    offenders = [
        f"{p.relative_to(REPO).as_posix()}:{node.lineno}"
        for p in sorted((REPO / "tests").rglob("test_*.py"))
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "reload"
    ]
    assert not offenders, (
        f"importlib.reload used in a test; it rebinds the exception classes that "
        f"{module_name} exports and breaks sibling tests that catch them. Use a "
        "subprocess instead:\n  " + "\n  ".join(offenders)
    )
