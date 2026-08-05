"""No ``sorry`` and no ``admit`` may contribute to a discharge — by any route.

CONF-005 records the measured position: the Lean backend closes every obligation with
``sorry`` **by design**, ``sorry`` is in ``FORBIDDEN_TACTICS``, and Mathlib is absent.
The gate is sound and nothing can pass through it. Those facts are reproduced here
rather than trusted, because the failure they prevent — an emitted proof skeleton being
counted as a proof — is exactly the "authoritative-looking output that is wrong" that
``CLAUDE.md`` names as the worst failure mode in this codebase.

The obligation engine takes a different route entirely: it never invokes Lean, never
reads emitted Lean, and never consults a proof-assistant artefact. That independence is
asserted too, so a future change that quietly wires Lean in has to break a test first.
"""

from __future__ import annotations

import pathlib

from hamiltonian_lang import compile_source
from hamiltonian_lang.v1.lean_verify import FORBIDDEN_TACTICS, LeanVerdict
from hamiltonian_lang.v1.lean_verify import verify as lean_verify
from hamiltonian_lang.verification.obligations import GlobalVerdict, verify_source

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "hamiltonian_lang"
ENGINE = SRC / "verification" / "obligations"

VERIFIABLE = "module M\nvar x : Real\nrequire x >= 0\nprove (x + 1)^2 = x^2 + 2 * x + 1\n"


def test_sorry_and_admit_are_still_forbidden_tactics() -> None:
    assert "sorry" in FORBIDDEN_TACTICS
    assert "admit" in FORBIDDEN_TACTICS


def test_the_lean_backend_still_emits_sorry_and_is_still_rejected() -> None:
    result = compile_source(VERIFIABLE)
    assert result.ok()
    emitted = result.render("lean").text
    assert "sorry" in emitted, "the recorded environment fact has changed; re-audit CONF-005"
    outcome = lean_verify(emitted)
    assert outcome.verdict is not LeanVerdict.VERIFIED
    assert outcome.verdict in (
        LeanVerdict.REJECTED_FORBIDDEN_TACTIC,
        LeanVerdict.NOT_ATTEMPTED,
    )


def test_a_verified_module_owes_nothing_to_lean() -> None:
    outcome = verify_source(VERIFIABLE)
    assert outcome.verdict is GlobalVerdict.VERIFIED
    checkers = {r.checker for r in outcome.records}
    assert not any("lean" in c for c in checkers)
    for record in outcome.records:
        blob = record.render().lower()
        assert "sorry" not in blob
        assert "admit" not in blob


def test_the_engine_never_imports_the_lean_path() -> None:
    """Independence enforced by inspection, so wiring Lean in has to break a test."""
    for path in sorted(ENGINE.glob("*.py")):
        text = path.read_text()
        assert "lean_verify" not in text, path
        assert "import lean" not in text, path


def test_the_engine_makes_no_model_call() -> None:
    """The whole M3 verification apparatus is offline. Nothing here reaches a server."""
    banned = ("model_client", "ollama", "requests", "httpx", "urllib.request", "socket")
    roots = [ENGINE, pathlib.Path(__file__).resolve().parents[2] / "evaluation" / "m3" / "verification"]
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            text = path.read_text()
            for token in banned:
                assert f"import {token}" not in text, f"{path} imports {token}"
                assert f"from {token}" not in text, f"{path} imports from {token}"
