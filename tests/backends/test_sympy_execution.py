"""Generated SymPy must EXECUTE, not merely render.

Measured defect: `def p := forall y : Real . y > x` followed by `prove p` emitted
`claims.append(p)` for a `p` that was never assigned. SymPy has no quantifiers, so the
definition was silently skipped while the reference survived — and the module raised
`NameError` on import.

The defect survived every existing test because those tests check the emitted *text*.
Rendering succeeded. Only running the file revealed it. These tests run the file.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends import render

pytest.importorskip("sympy", reason="the generated module imports sympy")

DANGLING_CASES = {
    "quantified def then prove":
        "module M\n\nvar x : Real\ndef p := forall y : Real . y > x\n\nprove p\n",
    "quantified def then require":
        "module M\n\nvar x : Real\ndef q := forall y : Real . y > x\n\nrequire q\n",
    "exists def then prove":
        "module M\n\nvar x : Real\ndef e := exists y : Real . y > x\n\nprove e\n",
}


def _execute(src: str) -> subprocess.CompletedProcess:
    r = compile_source(src)
    assert r.ok(), r.diagnostics.render()
    text = render("sympy", r.module, r.symbols).text
    path = pathlib.Path(tempfile.mkdtemp()) / "generated.py"
    path.write_text(text)
    return subprocess.run(
        [sys.executable, str(path)], capture_output=True, text=True, timeout=300
    )


@pytest.mark.parametrize("src", DANGLING_CASES.values(), ids=list(DANGLING_CASES))
def test_a_dropped_definition_does_not_leave_a_dangling_reference(src):
    proc = _execute(src)
    assert proc.returncode == 0, (
        "generated SymPy failed to execute:\n" + proc.stderr[-800:]
    )
    assert "NameError" not in proc.stderr


@pytest.mark.parametrize(
    "path",
    [p for p in sorted(pathlib.Path("examples").rglob("*.hml"))
     if "candidate_syntaxes" not in p.parts],
    ids=lambda p: p.name,
)
def test_every_example_generates_executable_sympy(path):
    proc = _execute(path.read_text())
    assert proc.returncode == 0, (
        f"{path} generated SymPy that does not run:\n" + proc.stderr[-800:]
    )


def test_the_drop_is_reported_not_silent():
    """A dropped reference must appear in the loss report, or the output looks complete."""
    r = compile_source(DANGLING_CASES["quantified def then prove"])
    out = render("sympy", r.module, r.symbols)
    assert not out.faithful
    reasons = " ".join(u.reason for u in out.unsupported)
    assert "NameError" in reasons or "dropped" in reasons.lower()
