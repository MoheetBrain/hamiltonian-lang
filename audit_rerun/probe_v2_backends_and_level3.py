"""Two supplementary suites the original instrument cannot reach.

1. BACKEND SILENT LOSS ON V2 CONSTRUCTS.  `tools/probe_backends.py` lowers six fixed
   specimens, none of which contains a v2 construct, so its "0 of 54 silent losses"
   result says nothing about the sixteen forms V2 added.  This suite lowers v2-carrying
   modules through every registered backend using the SAME silent-loss definition
   (a loss is silent iff it is disclosed by NEITHER a per-construct unsupported record
   NOR a backend-level limitation note).  It is reported as its own denominator; it is
   never folded into the 0/54.

2. MATURITY LADDER LEVEL 3 CRITERIA 3.3, 3.4, 3.6, 3.7, 3.8, executed.
   These were assessed by inspection in the original audit.  Each is turned into a
   program whose acceptance or rejection settles the criterion.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SRC = os.environ.get("HML_PROBE_SRC")
if _SRC:
    sys.path.insert(0, _SRC)

import hamiltonian_lang as H  # noqa: E402
from hamiltonian_lang import backends as B  # noqa: E402

RV = "rv X : RandomVariable[Real]\nrv Y : RandomVariable[Real]\n"

#: Each specimen carries v2 constructs that most targets provably cannot express.
V2_SPECIMENS: dict[str, str] = {
    "v2_probability": (
        "module V2Prob\n" + RV
        + "law X ~ Normal(location := 0.0, scale := 1.0)\n"
        "law Y ~ Normal(location := 0.0, scale := 1.0)\n"
        "require expectation(X) = 0.0\n"
        "require probability(X > 0.0) = 0.5\n"
        "require independent(X, Y)\n"
        "def j := joint(X, Y)\n"
    ),
    "v2_analysis": (
        "module V2Ana\n"
        "var f : Function[Real -> Real]\n"
        "var D : Set[Real]\n"
        "def l := limit(f(x), x : Real -> 0.0)\n"
        "def d := derivative(f(x), x : Real)\n"
        "def a := integral(f(x), x : Real, 0.0, 1.0)\n"
        "require continuous(f, on := D)\n"
    ),
    "v2_sets": (
        "module V2Sets\n"
        "var S : Set[Real]\nvar x : Real\n"
        "require x in S\n"
        "def T := { u : Real | u > 0.0 }\n"
    ),
    "v2_causal": (
        "module V2Causal\n" + RV
        + "require correlated(X, Y)\n"
        "require associated(X, Y)\n"
        "require causes(X, Y)\n"
    ),
    "v2_reasoning": (
        "module V2Reason\n"
        "var x : Real\nvar y : Real\n"
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : 2.0 * x = y from a1 by symmetry\n"
        "goal g : 2.0 * x = y\n"
        "proved g by d1\n"
    ),
}


def backend_rows() -> list[dict]:
    B._load_optional()
    targets = sorted(B.REGISTRY)
    rows: list[dict] = []
    for name, src in V2_SPECIMENS.items():
        res = H.compile_source(src, "<probe>")
        if not res.ok():
            rows.append(
                {
                    "specimen": name,
                    "backend": "-",
                    "SPECIMEN_DOES_NOT_COMPILE": list(res.diagnostics.codes()),
                    "diagnostics": res.diagnostics.render()[:400],
                }
            )
            continue
        for tgt in targets:
            try:
                out = B.render(tgt, res.module, res.symbols)
            except Exception as e:  # noqa: BLE001 — a crashing backend is a finding
                rows.append(
                    {"specimen": name, "backend": tgt, "error": f"{type(e).__name__}: {e}",
                     "SILENT_LOSS": True}
                )
                continue
            d = out.to_dict() if hasattr(out, "to_dict") else {}
            n = len(d.get("unsupported", []))
            notes = d.get("notes") or []
            rows.append(
                {
                    "specimen": name,
                    "backend": tgt,
                    "faithful": d.get("faithful"),
                    "n_unsupported": n,
                    "n_notes": len(notes),
                    "constructs": sorted({u["construct"] for u in d.get("unsupported", [])}),
                    # A backend that renders a v2 construct and reports nothing is only
                    # honest if it really did render it.  We cannot decide that
                    # mechanically for every target, so the recorded property is the
                    # disclosure channel, exactly as the original probe does.
                    "disclosed_per_construct": n > 0,
                    "disclosed_by_blanket_note": bool(notes),
                    "SILENT_LOSS": n == 0 and not notes and d.get("faithful") is not True,
                }
            )
    return rows


def _ok(src: str) -> tuple[bool, list[str]]:
    try:
        r = H.compile_source(src, "<probe>")
    except Exception as e:  # noqa: BLE001
        return False, [f"CRASH {type(e).__name__}: {e}"]
    return bool(r.ok()), list(r.diagnostics.codes())


def _obligations(src: str) -> int | None:
    try:
        r = H.compile_source(src, "<probe>")
    except Exception:  # noqa: BLE001
        return None
    return len(list(r.obligations or []))


#: criterion -> list of (label, source, "accept" | "reject")
LEVEL3: dict[str, list[tuple[str, str, str]]] = {
    "3.3 assumptions first-class and SCOPED": [
        (
            "is there ANY local assumption context? (block form)",
            "module M\nvar x : Real\nscope\n  assume a0 : x > 0.0\nend\n",
            "accept",
        ),
        (
            "does a module-level assumption refine the TYPE of its symbol?",
            "module M\nvar x : Real\nassume a0 : x > 0.0\ndef y := log(x)\n",
            "accept",
        ),
    ],
    "3.4 side conditions generated from partial operations": [
        ("division by an unconstrained variable", "module M\nvar x : Real\ndef y := 1.0 / x\n", "reject"),
        ("division by a literal zero", "module M\nconst y : Real = 1.0 / 0.0\n", "reject"),
        ("matrix inverse", "module M\nvar A : Matrix[Real, 3, 3]\ndef B := inverse(A)\n", "reject"),
        ("tan at a pole", "module M\nvar x : Real\ndef y := tan(x)\n", "reject"),
        ("0 ^ -1", "module M\nconst y : Real = 0.0 ^ -1.0\n", "reject"),
    ],
    "3.6 epistemic status preserved through a transformation": [
        (
            "an assumed premise yields a derivation whose status is recorded",
            "module M\nvar x : Real\nvar y : Real\nassume a1 : y = 2.0 * x\n"
            "derive d1 : 2.0 * x = y from a1 by symmetry\n",
            "accept",
        ),
        (
            "a REQUIRED proposition must not be usable as a derivation premise",
            "module M\nvar x : Real\nvar y : Real\nrequire y = 2.0 * x\n"
            "derive d1 : 2.0 * x = y from y by symmetry\n",
            "reject",
        ),
    ],
    "3.7 approximation is a distinct relation carrying an error term": [
        ("approximate equality operator", "module M\nconst p : Real ~= 3.14159\n", "accept"),
        # NOTE: this one COMPILES, but as 9.81 + (-0.02).  It is recorded here with
        # mode "accept" so the raw behaviour is visible, and adjudicated in the report as
        # a FALSE POSITIVE: parsing as subtraction is not expressing an uncertainty.
        ("value with an uncertainty (parses as subtraction)",
         "module M\nconst m : Real = 9.81 +- 0.02\n", "accept"),
    ],
}


def main() -> int:
    rows = backend_rows()
    silent = [r for r in rows if r.get("SILENT_LOSS")]
    bad_specimens = [r for r in rows if r.get("SPECIMEN_DOES_NOT_COMPILE")]

    l3: dict[str, list[dict]] = {}
    for crit, cases in LEVEL3.items():
        out = []
        for label, src, mode in cases:
            ok, codes = _ok(src)
            out.append(
                {
                    "case": label,
                    "mode": mode,
                    "accepted": ok,
                    "codes": codes,
                    "obligations": _obligations(src),
                    "behaves_as_required": (ok if mode == "accept" else not ok),
                }
            )
        l3[crit] = out

    # 3.8 queryability: can we mechanically answer structural questions?
    q_src = (
        "module Q\nvar x : Real\nvar y : Real\nrv A : RandomVariable[Real]\n"
        "rv Bv : RandomVariable[Real]\nassume a1 : y = 2.0 * x\n"
        "require independent(A, Bv)\n"
        "derive d1 : 2.0 * x = y from a1 by symmetry\n"
        "goal g : 2.0 * x = y\nproved g by d1\n"
    )
    r = H.compile_source(q_src, "<probe>")
    queries: dict[str, object] = {"compiles": bool(r.ok()), "codes": list(r.diagnostics.codes())}
    if r.ok():
        try:
            from hamiltonian_lang.ast.nodes import AssumeStmt, DeriveStmt, GoalStmt

            queries["which statements assume?"] = [
                getattr(s, "label", None) or type(s).__name__
                for s in r.module.statements
                if isinstance(s, AssumeStmt)
            ]
            queries["which derivations, and with what status?"] = [
                {"label": s.label, "rule": s.rule, "status": str(s.status)}
                for s in r.module.statements
                if isinstance(s, DeriveStmt)
            ]
            queries["which goals, and with what status?"] = [
                {"label": s.label, "status": str(s.status)}
                for s in r.module.statements
                if isinstance(s, GoalStmt)
            ]
        except Exception as e:  # noqa: BLE001
            queries["error"] = f"{type(e).__name__}: {e}"
        for attr in ("canonical", "graph", "hash", "symbols"):
            try:
                v = getattr(r, attr, None)
                queries[f"result.{attr} available"] = v is not None
            except Exception:  # noqa: BLE001
                queries[f"result.{attr} available"] = False
        try:
            queries["reasoning.obligations"] = [
                {"reason": getattr(o, "reason", None), "status": str(getattr(o, "status", None))}
                for o in (r.reasoning.obligations or [])
            ]
            queries["reasoning.open_obligations"] = len(r.reasoning.open_obligations())
        except Exception as e:  # noqa: BLE001
            queries["reasoning_query_error"] = f"{type(e).__name__}: {e}"

    out_path = Path(__file__).resolve().parent / "results" / (
        f"V2SUPP_{os.environ.get('HML_RUN_LABEL', 'unlabelled')}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "src": H.__file__,
                "backend_summary": {
                    "lowerings": len([r for r in rows if r.get("backend") != "-"]),
                    "silent_losses": len(silent),
                    "specimens_that_do_not_compile": [r["specimen"] for r in bad_specimens],
                },
                "backend_rows": rows,
                "level3": l3,
                "level3_8_queryability": queries,
            },
            indent=2,
        )
    )

    print(f"src = {H.__file__}\n")
    print("--- V2 CONSTRUCTS THROUGH EVERY BACKEND ---")
    if bad_specimens:
        for r in bad_specimens:
            print(f"  !! {r['specimen']} does not compile: {r['SPECIMEN_DOES_NOT_COMPILE']}")
    print(f"{'specimen':16s} {'backend':9s} {'faithful':9s} {'#unsup':7s} {'#notes':7s} SILENT?")
    for r in rows:
        if r.get("backend") == "-":
            continue
        print(
            f"{r['specimen']:16s} {r['backend']:9s} {str(r.get('faithful')):9s} "
            f"{str(r.get('n_unsupported')):7s} {str(r.get('n_notes')):7s} "
            f"{'*** SILENT ***' if r.get('SILENT_LOSS') else ''}"
        )
    print(
        f"\nsilent losses on v2 constructs: {len(silent)} of "
        f"{len([r for r in rows if r.get('backend') != '-'])}"
    )

    print("\n--- MATURITY LADDER LEVEL 3, EXECUTED ---")
    for crit, cases in l3.items():
        print(f"\n{crit}")
        for c in cases:
            print(
                f"   [{'ok ' if c['behaves_as_required'] else 'NO '}] {c['case'][:60]:60s} "
                f"want={c['mode']:6s} accepted={str(c['accepted']):5s} "
                f"obligations={c['obligations']} {','.join(c['codes']) or 'clean'}"
            )
    print("\n3.8 queryability:")
    print(json.dumps(queries, indent=2)[:1400])
    print(f"\n-> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
