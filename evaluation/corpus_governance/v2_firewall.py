"""ACQ0 is a translation instrument. It is not the H2/H3 reasoning oracle.

`CanonicalAcq0TaskV2` knows the intended encoding. That is exactly what H2 and H3 must
never see: a reasoning arm scored against a *particular* encoding would be penalised for
any other valid derivation, and a repair diagnostic derived from the target would make H3
a tautology rather than a measurement.

Enforced by a mode gate rather than by documentation, because documentation does not fail
a build.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

__all__ = ["Mode", "CrossModeAccess", "acq0_semantic_diff", "current_mode", "in_mode"]


class Mode(StrEnum):
    ACQ0 = "ACQ0"
    H2 = "H2"
    H3 = "H3"


class CrossModeAccess(RuntimeError):
    """A reasoning mode tried to reach ACQ0 target-relative material."""


_MODE: list[Mode] = [Mode.ACQ0]


def current_mode() -> Mode:
    return _MODE[-1]


class in_mode:
    """Context manager declaring which experiment is running."""

    def __init__(self, mode: Mode) -> None:
        self._mode = mode

    def __enter__(self) -> Mode:
        _MODE.append(self._mode)
        return self._mode

    def __exit__(self, *exc: object) -> None:
        _MODE.pop()


def acq0_semantic_diff(task: Any, submitted: str) -> dict[str, Any]:
    """Field-level diff of a submission against the ACQ0 target.

    **Refuses to run outside ACQ0.** The diff names which statements are missing or wrong
    relative to a specific intended encoding. Handing that to H2 would penalise a different
    but valid derivation; handing it to H3 would supply the answer and convert a
    verifier-guided-repair measurement into transcription.
    """
    if current_mode() is not Mode.ACQ0:
        raise CrossModeAccess(
            f"{current_mode()} requested an ACQ0 semantic diff. ACQ0 knows the intended "
            f"encoding; a reasoning arm scored against it would be penalised for any other "
            f"valid derivation, and a repair fed by it would be transcription, not repair. "
            f"H2/H3 must use an independent answer oracle."
        )
    from hamiltonian_lang import compile_source, content_hash

    result = compile_source(submitted, "<submitted>")
    if not result.ok():
        return {"comparable": False,
                "codes": [d.code for d in result.diagnostics.errors]}
    got = content_hash(submitted)
    expected = task.canonical_hash()
    if got == expected:
        return {"comparable": True, "equal": True, "differences": []}

    target = task.structured_target()
    from evaluation.corpus_governance.canonical_v2 import CanonicalAcq0TaskV2
    mirror = CanonicalAcq0TaskV2.structured_target
    submitted_view = mirror.__get__(  # reuse the same derivation on the submission
        _Shim(result.module), CanonicalAcq0TaskV2)()
    differences = [
        {"field": key, "expected": target[key], "submitted": submitted_view.get(key)}
        for key in ("declarations", "definitions", "probability_laws",
                    "assumptions", "domain_constraints")
        if target[key] != submitted_view.get(key)
    ]
    return {"comparable": True, "equal": False, "differences": differences}


class _Shim:
    """Minimal stand-in so the target derivation can run over a submitted module."""

    def __init__(self, module: Any) -> None:
        self.module = module
        self.derived_facts: tuple[Any, ...] = ()
        self.objective = None
        self.prohibited_assumptions: tuple[str, ...] = ()
        self.schema_version = "submitted"
        self.task_id = "<submitted>"
        self.family = "submitted"
