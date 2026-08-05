"""Can this repository be rebuilt from the remote, by someone who lost this machine?

The M1 audit answered that empirically once: a clone of the private remote at tag
``hml-m1-constitutional-core``, and a clone of the recovery bundle, both reproduced the
host's conformance result exactly. See ``docs/evaluation/M1_FINAL_AUDIT.md``.

An empirical answer decays. These tests are the parts of it that can be re-checked on
every run, and each one guards a specific way the answer could quietly become false:

* the recovery procedure stops naming the artefact it depends on;
* a new hard third-party dependency enters the test suite undeclared, so a clean clone
  installs successfully and then fails, or -- worse -- silently skips;
* an optional dependency stops being optional;
* the documented serial escape hatch stops being documented.

What these tests deliberately do *not* assert is the current commit SHA. Pinning HEAD
would make every subsequent commit fail this file, which teaches people to delete it.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LINEAGE = REPO / "docs" / "evaluation" / "EXPERIMENT_LINEAGE.md"

#: The milestone tag the recovery procedure restores to.
M1_TAG = "hml-m1-constitutional-core"

#: Imported by the tests but supplied by the harness, not by ``import`` -- so the
#: static scan below cannot see them and they must be listed by hand.
_HARNESS_DEPENDENCIES = frozenset({"pytest-xdist"})

#: Third-party packages the suite uses only behind ``pytest.importorskip``. Their absence
#: reduces coverage instead of failing, which is a reporting hazard, not a build failure.
_OPTIONAL_DEPENDENCIES = frozenset({"sympy", "tiktoken"})


def _pyproject() -> dict:
    return tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))


def _declared_dev_packages() -> set[str]:
    extras = _pyproject()["project"]["optional-dependencies"]
    names = set()
    for spec in extras.get("dev", []):
        names.add(re.split(r"[<>=!~\[ ]", spec, maxsplit=1)[0].strip().lower())
    return names


def _third_party_imports_in_tests() -> dict[str, set[str]]:
    """Top-level non-stdlib, non-local packages imported statically by ``tests/``."""
    stdlib = set(sys.stdlib_module_names)
    local = {"hamiltonian_lang", "evaluation", "tests", "benchmarks", "scripts"}
    found: dict[str, set[str]] = {}
    for path in sorted((REPO / "tests").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a broken test file fails elsewhere
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if name and name not in stdlib and name not in local:
                    found.setdefault(name, set()).add(path.relative_to(REPO).as_posix())
    return found


# ---------------------------------------------------------------------------
# The dependency surface a clean clone actually gets
# ---------------------------------------------------------------------------


def test_every_package_the_tests_import_is_in_the_declared_dev_extra():
    """A clean clone must not need a package that ``pip install -e '.[dev]'`` omits.

    This is the failure the M1 rebuild was run to find: an import that works here only
    because this machine's virtualenv accumulated it.
    """
    declared = _declared_dev_packages()
    imported = _third_party_imports_in_tests()
    missing = {
        name: sorted(files)
        for name, files in imported.items()
        if name.lower() not in declared
    }
    assert not missing, (
        "these packages are imported by the test suite but are not in the `dev` extra "
        "of pyproject.toml, so a clean clone cannot run the suite:\n"
        + "\n".join(f"  {name}: {files[0]} (+{len(files) - 1} more)"
                    for name, files in sorted(missing.items()))
    )


@pytest.mark.parametrize("package", sorted(_OPTIONAL_DEPENDENCIES))
def test_an_optional_dependency_is_never_imported_unguarded(package: str):
    """Optional means ``pytest.importorskip``, everywhere, without exception.

    A bare ``import sympy`` at module scope turns a missing optional package into a
    collection error on a clean clone. Guarding it turns the same absence into a *skip*,
    which is the tradeoff this project accepts -- and
    ``test_the_cost_of_a_missing_optional_dependency_is_recorded`` states the price.
    """
    unguarded = []
    for path in sorted((REPO / "tests").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                a.name.split(".")[0] == package for a in node.names
            ):
                unguarded.append(f"{path.relative_to(REPO).as_posix()}:{node.lineno}")
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and (node.module or "").split(".")[0] == package
            ):
                unguarded.append(f"{path.relative_to(REPO).as_posix()}:{node.lineno}")
    assert not unguarded, (
        f"{package} is optional (not in the `dev` extra) but is imported directly. Use "
        f'pytest.importorskip("{package}") so a clean clone skips rather than errors:\n  '
        + "\n  ".join(unguarded)
    )


def test_the_cost_of_a_missing_optional_dependency_is_recorded():
    """Silent coverage loss is the real hazard, so it must be written down.

    Measured during the M1 audit: a clone installed from the declared ``dev`` extra alone
    reported ``3946 passed, 21 skipped, 1 xfailed`` and **CONFORMANCE: PASS**, while the
    same tree with ``sympy`` and ``pytest-xdist`` added reported ``3974 passed, 4
    skipped``. Eleven tests were never collected and the gate went green anyway. Anyone
    reading a green conformance line from a fresh clone has to be able to find that.
    """
    assert LINEAGE.exists(), f"{LINEAGE.relative_to(REPO)} is missing"
    text = LINEAGE.read_text(encoding="utf-8")
    for package in sorted(_OPTIONAL_DEPENDENCIES | _HARNESS_DEPENDENCIES):
        if package == "tiktoken":
            continue  # declared in its own `tokenizers` extra
        assert package in text, (
            f"{package} is required for the full conformance result but is not declared "
            f"in pyproject.toml; {LINEAGE.name} must say so and state the cost"
        )


def test_the_conformance_gate_still_documents_its_serial_escape_hatch():
    """``HML_JOBS=1`` is the only way to diagnose an ordering-dependent failure.

    It is also the knob that leaked into ``SCORING_WORKERS`` once and broke conformance
    for an unrelated reason. Both facts have to stay visible in the script itself.
    """
    script = (REPO / "scripts" / "conformance.sh").read_text(encoding="utf-8")
    assert "HML_JOBS" in script
    assert 'JOBS="${HML_JOBS:-18}"' in script, (
        "the serial escape hatch changed shape; docs/evaluation/EXECUTION_ENVIRONMENT.md "
        "and tests/evaluation/test_syntax_gate_harness.py both depend on it"
    )
    harness = (REPO / "evaluation" / "syntax_gate" / "harness.py").read_text(encoding="utf-8")
    assert "HML_SCORING_WORKERS" in harness and 'environ.get("HML_JOBS"' not in harness, (
        "HML_JOBS is being read by library code again; it is conformance's serial knob "
        "and nothing else may claim the name"
    )


# ---------------------------------------------------------------------------
# The recovery procedure
# ---------------------------------------------------------------------------


def test_the_recovery_procedure_names_its_artefacts():
    """A recovery document that does not name the bundle is not a recovery document."""
    assert LINEAGE.exists(), f"{LINEAGE.relative_to(REPO)} is missing"
    text = LINEAGE.read_text(encoding="utf-8")
    assert M1_TAG in text, f"the recovery document does not name the {M1_TAG} tag"
    assert "hamiltonian_lang_m1.bundle" in text, "the recovery bundle is not named"
    assert re.search(r"\b[0-9a-f]{64}\b", text), (
        "no SHA-256 recorded for the recovery bundle; an unverified bundle is not a "
        "backup, it is a file"
    )
    assert re.search(r"\bgit bundle verify\b", text), (
        "the document must state the command that verifies the bundle, not merely that "
        "it was verified once"
    )


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, timeout=60
    )


def test_the_m1_tag_is_an_ancestor_of_the_current_branch():
    """Work must build *on* the audited milestone, never beside it.

    If M1 is no longer an ancestor of HEAD, the branch was rewritten or reset, and every
    measurement taken against ``hml-m1-constitutional-core`` has to be re-taken.
    """
    if not (REPO / ".git").exists():
        pytest.skip("not a git checkout")
    if _git("rev-parse", "--verify", f"{M1_TAG}^{{commit}}").returncode != 0:
        pytest.skip(f"tag {M1_TAG} is not present in this checkout")
    result = _git("merge-base", "--is-ancestor", f"{M1_TAG}^{{commit}}", "HEAD")
    assert result.returncode == 0, (
        f"{M1_TAG} is not an ancestor of HEAD. The audited milestone is no longer in "
        "this branch's history; the M1 conformance evidence does not describe this tree."
    )
