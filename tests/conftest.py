from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"


def example_files() -> list[Path]:
    return sorted(p for p in EXAMPLES.rglob("*.hml") if "candidate_syntaxes" not in p.parts)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO


@pytest.fixture(params=example_files(), ids=lambda p: p.relative_to(EXAMPLES).as_posix())
def example(request) -> Path:
    return request.param


def compile_ok(source: str):
    """Compile and assert success, showing diagnostics on failure."""
    from hamiltonian_lang import compile_source

    result = compile_source(source)
    assert result.ok(), "\n" + result.diagnostics.render()
    return result


def codes_of(source: str) -> list[str]:
    from hamiltonian_lang import compile_source

    return [d.code for d in compile_source(source).diagnostics.errors]
