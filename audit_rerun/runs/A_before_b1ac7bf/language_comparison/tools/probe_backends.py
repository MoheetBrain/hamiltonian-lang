"""Backend semantic-loss audit (mission section 16).

`backends.base.Backend` requires every backend to report what it could not preserve, via
`drop()` / `approximate()` / `weaken()`. That contract is the right one — CLAUDE.md names a
backend that silently omits a construct as the worst failure mode in the codebase — so the
audit's job is to check whether the reports are *complete*, not merely present.

Method: lower semantically rich modules through every registered backend and record the
declared loss. A backend that reports nothing on a module carrying constructs it cannot
express is a **silent** loss, which is worse than a declared one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

AUDIT_ROOT = Path(__file__).resolve().parents[3]
# RERUN HARNESS CHANGE (audit_rerun only): the original line was
#     sys.path.insert(0, str(AUDIT_ROOT / "src"))
# which pins the probes to the source tree three levels above tools/.  The rerun must
# execute the SAME probe text against three different source trees (b1ac7bf, 3dd4216,
# f0e3340), so the tree is selected by HML_PROBE_SRC.  Default behaviour is unchanged.
# This affects WHICH compiler is measured, never WHAT is measured.
import os  # noqa: E402
_SRC = os.environ.get("HML_PROBE_SRC") or str(AUDIT_ROOT / "src")
sys.path.insert(0, _SRC)

import hamiltonian_lang as H  # noqa: E402
from hamiltonian_lang import backends as B  # noqa: E402

#: Each specimen carries constructs a given backend provably cannot express, so that a
#: "no loss reported" result is a finding rather than a compliment.
SPECIMENS: dict[str, str] = {
    "epistemic_rich": (
        "module EpistemicRich\n"
        "param theta : Probability\n"
        "obs n : Natural = 10\n"
        "assume theta > 0.0\n"
        "prior theta ~ Beta(alpha := 1, beta := 1)\n"
        "require theta < 1.0\n"
        "prove forall x : Real . x = x\n"
        "infer posterior theta\n"
    ),
    "dimensional": (
        "module Dimensional\n"
        "param m : Quantity[Mass]\n"
        "param v : Quantity[Length / Time]\n"
        "def ke := 0.5 * m * v^2\n"
        "check dimension ke = Mass * Length^2 / Time^2\n"
    ),
    "quantified": (
        "module Quantified\n"
        "require forall x : Real . exists y : Real . y > x\n"
        "prove exists y : Real . forall x : Real . y > x\n"
    ),
    "concept": (
        "module Conceptual\n"
        "concept LocationScale\n"
        "    parameter location : Real\n"
        "    parameter scale : PositiveReal\n"
        "    invariant positive := scale > 0\n"
        "    example standard := location = 0 and scale = 1\n"
        "end\n"
    ),
    "linear_algebra": (
        "module LinAlg\n"
        "var A : Matrix[Real, 3, 3]\n"
        "var v : Vector[Real, 3]\n"
        "def w := A @ v\n"
    ),
    "optimisation": (
        "module Opt\nparam x : Real\ndef loss := x * x\nminimise loss\n"
    ),
}

#: What each backend fundamentally cannot represent, stated so that a missing report is
#: identifiable as a silent loss rather than as fidelity.
EXPECTED_INEXPRESSIBLE: dict[str, dict[str, str]] = {
    "stan": {
        "quantified": "Stan has no quantifiers; forall/exists cannot be a program element",
        "concept": "Stan has no abstraction-definition construct",
        "dimensional": "Stan has no units or dimensions",
        "epistemic_rich": "Stan has no `prove`; a proof goal has no Stan counterpart",
    },
    "lean": {
        "epistemic_rich": "Lean has no primitive notion of observed data or of a prior",
        "dimensional": "dimensions are library-level in Mathlib, not a kernel notion",
        "optimisation": "Lean has no `minimise` statement",
    },
    "sympy": {
        "epistemic_rich": "SymPy has no epistemic states; assume/require/prove collapse",
        "quantified": "SymPy quantifiers are not first-class propositions",
        "concept": "SymPy has no concept-definition mechanism",
    },
    "latex": {
        "epistemic_rich": "LaTeX is presentational; NO semantics survive at all",
        "quantified": "presentational only",
        "dimensional": "presentational only",
        "concept": "presentational only",
        "linear_algebra": "presentational only",
        "optimisation": "presentational only",
    },
    "english": {
        "epistemic_rich": "prose is not machine-checkable; all structure is advisory",
        "quantified": "prose",
        "dimensional": "prose",
        "concept": "prose",
        "linear_algebra": "prose",
        "optimisation": "prose",
    },
}


def main() -> int:
    B._load_optional()
    targets = sorted(B.REGISTRY)
    print(f"registered backends: {targets}\n")

    rows: list[dict] = []
    for spec_name, src in SPECIMENS.items():
        res = H.compile_source(src)
        if not res.ok():
            print(f"!! specimen {spec_name} does not compile: {res.diagnostics.codes()}")
            continue
        for tgt in targets:
            try:
                out = B.render(tgt, res.module, res.symbols)
            except Exception as e:  # noqa: BLE001 — a crashing backend is a finding
                rows.append(
                    {
                        "specimen": spec_name,
                        "backend": tgt,
                        "error": f"{type(e).__name__}: {e}",
                        "faithful": None,
                        "n_reported": None,
                    }
                )
                continue
            d = out.to_dict() if hasattr(out, "to_dict") else {"faithful": None}
            expected = EXPECTED_INEXPRESSIBLE.get(tgt, {}).get(spec_name)
            n = len(d.get("unsupported", []))
            # A loss is SILENT only when it is disclosed through NEITHER channel: neither a
            # per-construct drop/approximate/weaken, nor a backend-level limitation note.
            # An earlier version of this probe checked only the first channel and therefore
            # mis-flagged `english` and `latex`, which do disclose their one-way nature in
            # `limitations`. The distinction that survives is weaker but real: a blanket
            # note is coarser than per-construct reporting, and `faithful` stays True.
            notes = d.get("notes") or []
            disclosed_by_note = bool(notes)
            silent = bool(expected) and n == 0 and not disclosed_by_note
            rows.append(
                {
                    "specimen": spec_name,
                    "backend": tgt,
                    "faithful": d.get("faithful"),
                    "n_reported": n,
                    "severities": sorted({u["severity"] for u in d.get("unsupported", [])}),
                    "constructs": sorted({u["construct"] for u in d.get("unsupported", [])}),
                    "expected_inexpressible": expected,
                    "n_limitation_notes": len(d.get("notes") or []),
                    "disclosed_per_construct": n > 0,
                    "disclosed_by_blanket_note": bool(d.get("notes")),
                    "faithful_flag_misleading": bool(expected) and n == 0 and bool(d.get("notes")),
                    "SILENT_LOSS": silent,
                }
            )

    # RERUN HARNESS CHANGE (audit_rerun only): original was
    #     AUDIT_ROOT / "audit/language_comparison/matrices/BACKEND_SEMANTIC_LOSS_PROBES.json"
    # Redirected to this rerun copy so each source tree writes its own results.
    out_path = (
        Path(__file__).resolve().parents[1] / "matrices" / "BACKEND_SEMANTIC_LOSS_PROBES.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"rows": rows}, indent=2))

    print(f"{'specimen':16s} {'backend':10s} {'faithful':9s} {'#loss':6s} SILENT?")
    print("-" * 74)
    for r in rows:
        print(
            f"{r['specimen']:16s} {r['backend']:10s} "
            f"{str(r.get('faithful')):9s} {str(r.get('n_reported')):6s} "
            f"{'*** SILENT LOSS ***' if r.get('SILENT_LOSS') else ''}"
        )
    silent = [r for r in rows if r.get("SILENT_LOSS")]
    misleading = [r for r in rows if r.get("faithful_flag_misleading")]
    print(f"\ntruly silent losses (no channel): {len(silent)} of {len(rows)}")
    print(
        f"faithful=True despite known inexpressibility, disclosed only by a blanket "
        f"note: {len(misleading)} of {len(rows)}"
    )
    print(f"-> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
