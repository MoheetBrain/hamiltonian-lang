"""Lean verification that cannot certify a false theorem.

HML-COMPILER-CORE-003 item 6. Complements `backend_support.py`, which *records* what Lean
can express; this module *enforces* it at the point a claim would be labelled verified.

Three traps, each confirmed by direct experiment on Lean 4.32.2 and each closed here:

1. **`sorry` compiles and exits 0.**

       theorem definitely_false : (1 : Nat) = 2 := by sorry
       $ lean False.lean ; echo $?
       warning: declaration uses `sorry`
       0

   Exit status alone certifies a demonstrably false theorem. `#print axioms` is the only
   discriminator: the skeleton depends on `sorryAx`, a real proof does not.

2. **Lean invents missing types.** With `autoImplicit` at its default,
   `theorem t : ∀ x : Real, x = x` elaborates *even though `Real` does not exist* — it is
   auto-bound as `{Real : Sort u_1}`, so the theorem is vacuously about an arbitrary type.
   Every file compiled here sets `autoImplicit false` and `relaxedAutoImplicit false`.

3. **A compiled statement is not the intended statement.** Compilation says nothing about
   whether the Lean says what the HML said, so an explicit `expected_statement`
   comparison is required before any acceptance.

The default is refusal. `verify()` returns `VERIFIED` only when every check passes; a
missing toolchain yields `NOT_ATTEMPTED`, never a pass.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

__all__ = [
    "LeanVerdict",
    "LeanResult",
    "lean_available",
    "lean_version",
    "verify",
    "FORBIDDEN_TACTICS",
    "PREAMBLE",
]

#: Tactics that close a goal without proving it. Textual rejection happens before Lean
#: runs, so a file containing one can never reach the acceptance path at all.
FORBIDDEN_TACTICS = ("sorry", "admit", "native_decide")

#: Prepended to every file. `autoImplicit false` is not optional -- see trap 2.
PREAMBLE = (
    "set_option autoImplicit false\n"
    "set_option relaxedAutoImplicit false\n"
)

#: Lean reports axioms in two shapes, and missing the clean one would reject every real
#: proof as unverifiable:
#:     't' depends on axioms: [sorryAx]
#:     't' does not depend on any axioms
_AXIOM_LINE = re.compile(r"'(?P<name>[^']+)' depends on axioms: \[(?P<axioms>[^\]]*)\]")
_NO_AXIOM_LINE = re.compile(r"'(?P<name>[^']+)' does not depend on any axioms")
_THEOREM = re.compile(r"^\s*theorem\s+([A-Za-z_][A-Za-z0-9_']*)", re.M)

#: Axioms Lean's own standard library relies on. Anything else is a smell; `sorryAx` is a
#: hard failure.
_ACCEPTABLE_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


class LeanVerdict(StrEnum):
    VERIFIED = "verified"
    REJECTED_FORBIDDEN_TACTIC = "rejected_forbidden_tactic"
    REJECTED_COMPILE_ERROR = "rejected_compile_error"
    REJECTED_SORRY_AXIOM = "rejected_sorry_axiom"
    REJECTED_UNEXPECTED_AXIOM = "rejected_unexpected_axiom"
    REJECTED_STATEMENT_MISMATCH = "rejected_statement_mismatch"
    REJECTED_NO_THEOREM = "rejected_no_theorem"
    NOT_ATTEMPTED = "not_attempted"


@dataclass
class LeanResult:
    verdict: LeanVerdict
    detail: str = ""
    theorems: list[str] = field(default_factory=list)
    axioms: dict[str, list[str]] = field(default_factory=dict)
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    lean_version: str | None = None

    @property
    def verified(self) -> bool:
        """The ONLY property callers may use to label something proved."""
        return self.verdict is LeanVerdict.VERIFIED

    def to_dict(self) -> dict:
        return {
            "verdict": str(self.verdict),
            "verified": self.verified,
            "detail": self.detail,
            "theorems": list(self.theorems),
            "axioms": dict(self.axioms),
            "exit_code": self.exit_code,
            "lean_version": self.lean_version,
        }


def lean_available() -> bool:
    return shutil.which("lean") is not None


def lean_version() -> str | None:
    if not lean_available():
        return None
    try:
        r = subprocess.run(
            ["lean", "--version"], capture_output=True, text=True, timeout=60
        )
        return r.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def verify(
    source: str,
    *,
    expected_statement: str | None = None,
    timeout_s: int = 180,
) -> LeanResult:
    """Compile ``source`` and accept it only if every check passes.

    ``expected_statement`` is the statement the caller believes it emitted, normalised for
    whitespace before comparison. Passing ``None`` skips only that check; it does not
    weaken the others.
    """
    version = lean_version()

    # 1. Forbidden tactics, before Lean is invoked at all.
    for tactic in FORBIDDEN_TACTICS:
        if re.search(rf"\b{re.escape(tactic)}\b", source):
            return LeanResult(
                LeanVerdict.REJECTED_FORBIDDEN_TACTIC,
                f"source contains {tactic!r}; a goal closed by {tactic!r} is not proved, "
                f"and Lean exits 0 on it",
                lean_version=version,
            )

    names = _THEOREM.findall(source)
    if not names:
        return LeanResult(
            LeanVerdict.REJECTED_NO_THEOREM,
            "no theorem declaration found; there is nothing to verify",
            lean_version=version,
        )

    # 2. Statement comparison. Compilation alone never shows the Lean says what HML said.
    if expected_statement is not None:
        if _norm(expected_statement) not in _norm(source):
            return LeanResult(
                LeanVerdict.REJECTED_STATEMENT_MISMATCH,
                "the compiled statement is not the expected statement; compiling proves "
                "something, but not necessarily what was intended",
                theorems=names,
                lean_version=version,
            )

    if not lean_available():
        return LeanResult(
            LeanVerdict.NOT_ATTEMPTED,
            "no `lean` on PATH; nothing was compiled and nothing may be called verified",
            theorems=names,
            lean_version=None,
        )

    # 3. Compile with autoImplicit disabled, and ask for the axioms of every theorem.
    body = PREAMBLE + source
    if "#print axioms" not in source:
        body += "\n" + "\n".join(f"#print axioms {n}" for n in names) + "\n"

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "Probe.lean"
        path.write_text(body)
        try:
            proc = subprocess.run(
                ["lean", str(path)], capture_output=True, text=True, timeout=timeout_s
            )
        except subprocess.TimeoutExpired:
            return LeanResult(
                LeanVerdict.REJECTED_COMPILE_ERROR,
                f"lean did not terminate within {timeout_s}s",
                theorems=names,
                lean_version=version,
            )

    combined = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return LeanResult(
            LeanVerdict.REJECTED_COMPILE_ERROR,
            f"lean exited {proc.returncode}",
            theorems=names, exit_code=proc.returncode,
            stdout=proc.stdout, stderr=proc.stderr, lean_version=version,
        )

    axioms: dict[str, list[str]] = {
        m.group("name"): [a.strip() for a in m.group("axioms").split(",") if a.strip()]
        for m in _AXIOM_LINE.finditer(combined)
    }
    for m in _NO_AXIOM_LINE.finditer(combined):
        axioms.setdefault(m.group("name"), [])

    # 4. sorryAx is a hard failure even though the exit code was 0.
    tainted = [n for n, ax in axioms.items() if "sorryAx" in ax]
    if tainted or "sorryAx" in combined:
        return LeanResult(
            LeanVerdict.REJECTED_SORRY_AXIOM,
            f"depends on sorryAx: {tainted or 'reported in output'}. Lean exited 0, which "
            f"is exactly why exit status alone must never be treated as verification",
            theorems=names, axioms=axioms, exit_code=0,
            stdout=proc.stdout, stderr=proc.stderr, lean_version=version,
        )

    missing = [n for n in names if n not in axioms]
    if missing:
        return LeanResult(
            LeanVerdict.REJECTED_NO_THEOREM,
            f"no axiom report for {missing}; cannot confirm the proof is real",
            theorems=names, axioms=axioms, exit_code=0, lean_version=version,
        )

    unexpected = {
        n: [a for a in ax if a not in _ACCEPTABLE_AXIOMS] for n, ax in axioms.items()
    }
    unexpected = {n: ax for n, ax in unexpected.items() if ax}
    if unexpected:
        return LeanResult(
            LeanVerdict.REJECTED_UNEXPECTED_AXIOM,
            f"depends on axioms outside the accepted set: {unexpected}",
            theorems=names, axioms=axioms, exit_code=0, lean_version=version,
        )

    return LeanResult(
        LeanVerdict.VERIFIED,
        f"compiled with autoImplicit false, no forbidden tactic, and {names} depend only "
        f"on accepted axioms",
        theorems=names, axioms=axioms, exit_code=0,
        stdout=proc.stdout, stderr=proc.stderr, lean_version=version,
    )


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
