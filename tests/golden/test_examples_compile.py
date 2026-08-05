"""Every example under `examples/` compiles, or is explicitly marked illustrative.

CLAUDE.md rule 10 has always required this, but nothing enforced it. The conformance gate
globbed `examples/*/*.hml` -- one level deep -- so the 35 files under
`examples/candidate_syntaxes/` were never checked. Two of them had silently drifted out of
the language:

    3_linear_regression.hml   `infer posterior` with no prior, an error since D-016
    7_concept_definition.hml  unnamed invariants, rejected by the parser

In both cases the compiler was right and the example was stale. A rule that is stated but
unenforced is worth nothing, so the walk here is recursive and the marker is explicit.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MARKER = ".illustrative"


def _illustrative(path: Path) -> Path | None:
    """Return the marker governing `path`, if any directory above it carries one."""
    for parent in path.parents:
        if (parent / MARKER).is_file():
            return parent / MARKER
        if parent == REPO:
            break
    return None


def _all_examples() -> list[Path]:
    return sorted(REPO.joinpath("examples").rglob("*.hml"))


def _compilable() -> list[Path]:
    return [p for p in _all_examples() if _illustrative(p) is None]


def test_examples_exist():
    """A passing suite must not be the result of finding no files."""
    assert len(_all_examples()) >= 40, "the example corpus disappeared or moved"
    assert len(_compilable()) >= 8, "no compilable examples found; the marker over-matched"


@pytest.mark.parametrize("path", _compilable(), ids=lambda p: str(p.relative_to(REPO)))
def test_example_compiles(path: Path):
    result = subprocess.run(
        [sys.executable, "-m", "hamiltonian_lang.cli", "check", str(path)],
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"{path.relative_to(REPO)} does not compile.\n"
        f"Either fix the example, or -- if it is a design sketch in a surface the compiler "
        f"does not accept -- put a `{MARKER}` file in its directory saying so.\n"
        f"{result.stdout}{result.stderr}"
    )


@pytest.mark.parametrize(
    "marker",
    sorted(REPO.joinpath("examples").rglob(MARKER)),
    ids=lambda p: str(p.parent.relative_to(REPO)),
)
def test_illustrative_marker_states_a_reason(marker: Path):
    """A bare marker file would let anyone silence a real failure with `touch`."""
    reason = marker.read_text().strip()
    assert len(reason) >= 30, (
        f"{marker.relative_to(REPO)} must state why its files are not expected to "
        f"compile; found {reason!r}"
    )


def test_marker_does_not_cover_the_implemented_syntax():
    """`a_labelled_linear` is HML-L1. Marking it illustrative would disable the gate."""
    real = REPO / "examples/candidate_syntaxes/a_labelled_linear"
    assert real.is_dir()
    assert _illustrative(real / "1_normal_distribution.hml") is None, (
        "the implemented syntax must never be marked illustrative"
    )
