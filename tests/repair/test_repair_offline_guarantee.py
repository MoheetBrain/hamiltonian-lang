"""These two packages contact nothing, and that is checked rather than asserted in prose.

The Lead authorises live runs separately. Until then a repair test suite that quietly
started making model calls would produce numbers nobody intended to spend, would vary
between runs, and would look exactly like the offline results it replaced.
"""

from __future__ import annotations

import ast
import re
import socket
from pathlib import Path

import pytest

from hamiltonian_lang.improvement.state import Hypothesis
from hamiltonian_lang.repair import (
    DeterministicRepairTeacher,
    FeedbackArm,
    RepairBudget,
    RepairEndpoint,
    ScriptedLeakageProbe,
    ScriptedRepairLearner,
    run_repair_chain,
)

SRC = Path(__file__).resolve().parents[2] / "src" / "hamiltonian_lang"
PACKAGES = (SRC / "repair", SRC / "context_broker")

#: Modules that reach a network, a subprocess or a model provider. Importing any of them
#: from these packages would make an offline guarantee unenforceable.
FORBIDDEN_IMPORTS = {
    "http", "http.client", "httpx", "requests", "urllib", "urllib.request", "socket",
    "ssl", "subprocess", "asyncio", "ollama", "openai", "anthropic",
}

FORBIDDEN_MODULE_PREFIXES = ("evaluation.model", "evaluation.harness")


def python_files() -> list[Path]:
    return sorted(p for pkg in PACKAGES for p in pkg.rglob("*.py"))


def test_the_packages_exist_and_are_non_empty() -> None:
    assert python_files()


@pytest.mark.parametrize("path", python_files(), ids=lambda p: p.name)
def test_no_module_imports_a_network_or_provider_module(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module)
    hits = {
        name
        for name in imported
        if name in FORBIDDEN_IMPORTS
        or name.split(".")[0] in FORBIDDEN_IMPORTS
        or name.startswith(FORBIDDEN_MODULE_PREFIXES)
    }
    assert not hits, f"{path.name} imports {sorted(hits)}"


@pytest.mark.parametrize("path", python_files(), ids=lambda p: p.name)
def test_no_module_contains_a_url(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert not re.search(r"https?://", text), f"{path.name} contains a URL"


def test_the_default_components_all_declare_themselves_offline() -> None:
    assert DeterministicRepairTeacher().live is False
    assert ScriptedRepairLearner(script={}).live is False
    assert ScriptedLeakageProbe(script={}).live is False


def test_a_full_chain_runs_with_the_socket_module_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The strongest available offline check: make any connection attempt raise."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the repair chain attempted a network connection")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)

    broken = "module M\ndef f(a : Real, b : Real) : Real := a + b\ndef g : Real := f(1.0)\n"
    fixed = (
        "module M\ndef f(a : Real, b : Real) : Real := a + b\n"
        "def g : Real := f(1.0, 2.0)\n"
    )
    learner = ScriptedRepairLearner(
        script={("t", FeedbackArm.CHAIN_OF_REPAIR, 1): fixed}
    )
    record = run_repair_chain(
        task_id="t",
        hypothesis=Hypothesis.ACQ0,
        endpoint=RepairEndpoint.SYNTACTIC_ENCODING,
        budget=RepairBudget.OFFICIAL_ONE,
        arm=FeedbackArm.CHAIN_OF_REPAIR,
        initial_output=broken,
        learner=learner,
    )
    assert record.repaired is True
