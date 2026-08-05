"""Canonical serialisation must be thread-safe, not merely reentrant.

``to_canonical`` selects whether declaration names appear. ``content_hash`` always forces
them *off*, because identity is structural. That flag used to be a module global with
save/restore, which is reentrancy-safe and **not** thread-safe: while one thread hashed,
another thread asking for the human-readable named form silently received the *nameless*
document. No exception, no diagnostic -- just the wrong answer, which `CLAUDE.md` names
as the worst failure mode in this codebase.

Found by the M1 reproducibility audit, reproduced here, and closed by a ``ContextVar``
(D-024). The hazard was not reachable from any shipped code path at the time -- the only
thread pool never canonicalised -- but ACQ0 scores semantic preservation by comparing
canonical forms, so the first threaded scorer would have hit it.

These tests must keep failing if the ContextVar is ever reverted to a global.
"""

from __future__ import annotations

import sys
import threading
from contextvars import ContextVar

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends.canonical import content_hash, to_canonical

MODULE = "module M\n" + "\n".join(f"param v{i} : Real" for i in range(400)) + "\n"


def _named(doc: dict) -> int:
    """How many statements carry a spelled name."""
    return sum(1 for s in doc["statements"] if isinstance(s.get("symbol"), dict))


def test_the_probe_itself_distinguishes_the_two_forms():
    """Without this, the concurrency test below could pass vacuously."""
    result = compile_source(MODULE)
    assert _named(to_canonical(result.module, include_names=True)) > 0
    assert _named(to_canonical(result.module, include_names=False)) == 0


def test_the_include_names_flag_is_per_thread_by_construction():
    """The load-bearing guard. Deterministic, unlike winning a race.

    The stress tests below are honest but weak: the window is narrow enough that the
    original audit hit it once, and a reverted implementation was NOT caught by 16
    threads over a 2000-statement module. A test that only *sometimes* detects the
    regression it exists for is decoration.

    This one cannot miss. A ``ContextVar`` gives each thread an independent value; a
    module global does not. Setting it here and reading it from a fresh thread
    distinguishes the two implementations every single run.
    """
    from hamiltonian_lang.backends import canonical

    assert isinstance(canonical._INCLUDE_NAMES, ContextVar), (
        "the include-names flag is process-global again; concurrent hashing can now "
        "silently strip names from another thread's canonical form (D-024)"
    )

    seen: list[bool] = []
    token = canonical._INCLUDE_NAMES.set(False)
    try:
        thread = threading.Thread(target=lambda: seen.append(canonical._INCLUDE_NAMES.get()))
        thread.start()
        thread.join()
    finally:
        canonical._INCLUDE_NAMES.reset(token)

    assert seen == [True], (
        f"a second thread observed this thread's setting ({seen}); the flag is shared "
        f"across threads and D-024 has been reverted"
    )


def test_concurrent_hashing_does_not_corrupt_the_named_form():
    result = compile_source(MODULE)
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # widen the window the old global raced in
    corrupted = 0
    lock = threading.Lock()

    def hasher() -> None:
        for _ in range(50):
            to_canonical(result.module, include_names=False)

    def namer() -> None:
        nonlocal corrupted
        for _ in range(50):
            if _named(to_canonical(result.module, include_names=True)) == 0:
                with lock:
                    corrupted += 1

    try:
        threads = [threading.Thread(target=hasher) for _ in range(8)]
        threads += [threading.Thread(target=namer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(previous)

    # Best-effort: this window is narrow and a reverted implementation may survive it.
    # The deterministic guard is test_the_include_names_flag_is_per_thread_by_construction.
    assert corrupted == 0, (
        f"{corrupted} named canonical forms were silently emitted without names while "
        f"another thread hashed. The include-names flag is process-global again."
    )


def test_concurrent_naming_does_not_corrupt_the_hash():
    """The converse direction: identity must not depend on what another thread asked for."""
    result = compile_source(MODULE)
    expected = content_hash(result.module)
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    mismatches = 0
    lock = threading.Lock()

    def namer() -> None:
        for _ in range(50):
            to_canonical(result.module, include_names=True)

    def hasher() -> None:
        nonlocal mismatches
        for _ in range(50):
            if content_hash(result.module) != expected:
                with lock:
                    mismatches += 1

    try:
        threads = [threading.Thread(target=namer) for _ in range(4)]
        threads += [threading.Thread(target=hasher) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(previous)

    assert mismatches == 0, f"{mismatches} content hashes changed under concurrency"


def test_nesting_still_restores_the_outer_setting():
    """The ContextVar must keep the reentrancy the global already had."""
    result = compile_source("module M\nparam x : Real\n")
    outer = to_canonical(result.module, include_names=True)
    to_canonical(result.module, include_names=False)
    assert to_canonical(result.module, include_names=True) == outer
