"""Golden tests.

Every example must check cleanly and produce a stable canonical hash. The snapshot
file ``tests/golden/hashes.json`` is the tripwire: if a hash changes, either the
semantics changed (which requires a DECISIONS.md record) or something regressed.

To re-bless intentionally: ``HML_BLESS=1 pytest tests/golden``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends import available, render

GOLDEN = Path(__file__).parent / "hashes.json"


def _load() -> dict:
    return json.loads(GOLDEN.read_text()) if GOLDEN.exists() else {}


def _compiled(path: Path):
    r = compile_source(path.read_text(), str(path))
    assert r.ok(), f"{path} failed to check:\n" + r.diagnostics.render()
    return r


def test_every_example_checks(example):
    _compiled(example)


def test_canonical_hashes_are_stable(example, repo_root):
    key = example.relative_to(repo_root).as_posix()
    actual = _compiled(example).hash()
    golden = _load()
    if os.environ.get("HML_BLESS") or key not in golden:
        golden[key] = actual
        GOLDEN.write_text(json.dumps(golden, indent=2, sort_keys=True) + "\n")
        if not os.environ.get("HML_BLESS"):
            pytest.skip(f"recorded new golden hash for {key}")
        return
    assert actual == golden[key], (
        f"canonical hash changed for {key}.\n"
        "If this was intentional, record the reason in DECISIONS.md and re-bless "
        "with HML_BLESS=1."
    )


@pytest.mark.parametrize("target", ["hml", "english", "latex", "json", "graph", "triples"])
def test_core_backends_render_every_example(example, target):
    r = _compiled(example)
    out = render(target, r.module, r.symbols)
    assert out.text.strip(), f"{target} produced nothing for {example}"


def test_lossy_backends_declare_their_loss(example):
    """A backend that drops meaning must say so. Silence would be the real failure."""
    r = _compiled(example)
    latex = render("latex", r.module, r.symbols)
    src = example.read_text()
    if "param " in src or "obs " in src or "concept " in src:
        assert not latex.faithful
        assert latex.unsupported
        assert all(u.reason for u in latex.unsupported)


def test_faithful_backends_report_no_loss(example):
    r = _compiled(example)
    for target in ("hml", "json"):
        assert render(target, r.module, r.symbols).faithful


def test_quantifier_scope_examples_have_different_hashes(repo_root):
    a = _compiled(repo_root / "examples/logic/quantifier_scope.hml").hash()
    b = _compiled(repo_root / "examples/logic/quantifier_scope_reversed.hml").hash()
    assert a != b, "the two quantifier scopings must not be confusable"


def test_no_superiority_claim_in_public_docs(repo_root):
    """CLAUDE.md rule 5. No measurement has been run, so no claim may be made."""
    banned = [
        "outperforms", "better than english", "superior to", "beats latex",
        "proven to improve", "demonstrably better", "state of the art",
    ]
    for name in ("README.md", "GOAL.md", "ARCHITECTURE.md", "SPEC.md"):
        p = repo_root / name
        if not p.exists():
            continue
        text = p.read_text().lower()
        for phrase in banned:
            assert phrase not in text, f"{name} contains an unsupported claim: {phrase!r}"


def test_private_docs_are_not_referenced_from_public_docs(repo_root):
    for name in ("README.md", "GOAL.md"):
        p = repo_root / name
        if p.exists():
            assert "docs/private/" not in p.read_text()


def test_backend_registry_is_populated():
    for required in ("hml", "json", "latex", "english", "graph", "triples"):
        assert required in available()
