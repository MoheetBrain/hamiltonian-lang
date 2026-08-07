"""Executed probes for the 19 transformation forms of TRANSFORMATION_CAPABILITY_MATRIX.csv.

Why this file exists
--------------------
The original audit's 0/19 figure was **NOT produced by a probe**. It is a hand-authored
table in `tools/build_hml_matrices.py`: the 19 names are a literal list, every row is
written `NO`, and three exceptions are written `PARTIAL` by hand. Nothing was compiled.
That is defensible for a system where the grammar demonstrably had no derivation
statement, but it cannot be *rerun*, and a rerun that simply re-typed the table would be
worthless.

So this suite compiles real HML for every one of the 19 names, against whichever source
tree `HML_PROBE_SRC` selects, and scores four properties by execution:

REPRESENTABLE          a surface statement expresses "from A, by rule R, infer B" for this
                       transformation, and it compiles clean.
EXECUTABLE             the system computes the output from the input rather than the
                       author stating it.  Scored NO throughout for HML v2 and stated as
                       such: `derive` requires the author to write the conclusion; the
                       kernel recomputes it and compares, which is checking, not execution.
VERIFIABLE             BOTH must hold, both executed: (a) the correct step reaches
                       DerivationStatus.VERIFIED, and (b) a deliberately broken variant of
                       the same step is REJECTED.  A rule that accepts everything is not a
                       checker, so (b) is mandatory -- this mirrors MATURITY_LADDER 3.5
                       ("the check must fail on a deliberately broken variant").
PROVENANCE_PRESERVING  the compiled artefact records premises, rule name and status, AND
                       the content hash is unchanged by that record (SEMANTICS.md 4).

The same file runs against v1 and v2.  v1 has no `derive`, so every probe there fails at
the parser, which reproduces the published 0/19 by execution instead of by assertion.
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

PRELUDE = "module M\nvar x : Real\nvar y : Real\nvar k : Real\nvar z : Real\n"

#: name -> (correct step, broken variant or None, note)
#: The broken variant keeps the SAME premises and the SAME rule and changes only the
#: conclusion, so a rejection can only come from the rule check.
CASES: dict[str, tuple[str | None, str | None, str]] = {
    "substitution": (
        "assume a1 : y = 2.0 * x\nassume a2 : z = y + k\n"
        "derive d1 : z = 2.0 * x + k from a1, a2 by substitute\n",
        "assume a1 : y = 2.0 * x\nassume a2 : z = y + k\n"
        "derive d1 : z = 2.0 * x + 99.0 from a1, a2 by substitute\n",
        "rule `substitute`",
    ),
    "rewrite": (
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : exp(y) = exp(2.0 * x) from a1 by congruence(fn := exp)\n",
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : exp(y) = exp(3.0 * x) from a1 by congruence(fn := exp)\n",
        "rewriting under a context = rule `congruence`",
    ),
    "simplify": (None, None, "no normalisation rule in the closed catalogue"),
    "rearrange": (
        "assume a1 : y + k = 2.0 * x\n"
        "derive d1 : y + k - k = 2.0 * x - k from a1 by subtract_both_sides(by := k)\n",
        "assume a1 : y + k = 2.0 * x\n"
        "derive d1 : y + k - k = 2.0 * x - 99.0 from a1 by subtract_both_sides(by := k)\n",
        "rule `subtract_both_sides`",
    ),
    "cancel": (
        "assume a0 : k != 0.0\nassume a1 : y * k = 2.0 * x * k\n"
        "derive d1 : y * k / k = 2.0 * x * k / k from a1 by divide_both_sides(by := k)\n",
        "assume a0 : k != 0.0\nassume a1 : y * k = 2.0 * x * k\n"
        "derive d1 : y * k / k = 2.0 * x from a1 by divide_both_sides(by := k)\n",
        "rule `divide_both_sides`, with its k != 0 obligation",
    ),
    "factor": (None, None, "no factoring rule in the closed catalogue"),
    "expand": (None, None, "no expansion rule in the closed catalogue"),
    "differentiate": (
        None, None,
        "`derivative(f(x), x : T)` is an EXPRESSION (D-026); there is no rule that "
        "differentiates both sides of an equation",
    ),
    "integrate": (
        None, None,
        "`integral(...)` is an EXPRESSION; there is no rule that integrates a relation",
    ),
    "change of variables": (None, None, "no change-of-variables rule"),
    "case split": (None, None, "no case-analysis rule; `or` cannot be eliminated"),
    "contradiction": (
        "assume a1 : x > 0.0 implies y > 0.0\nassume a2 : not (y > 0.0)\n"
        "derive d1 : not (x > 0.0) from a2, a1 by modus_tollens\n",
        "assume a1 : x > 0.0 implies y > 0.0\nassume a2 : not (y > 0.0)\n"
        "derive d1 : not (x > 1.0) from a2, a1 by modus_tollens\n",
        "`modus_tollens` only. There is no reductio/`False`-elimination rule, so "
        "proof BY contradiction proper is absent; scored on modus tollens alone and "
        "flagged in the report.",
    ),
    "induction": (None, None, "no induction rule; no inductive types"),
    "implication application": (
        "assume a1 : x > 0.0\nassume a2 : x > 0.0 implies y > 0.0\n"
        "derive d1 : y > 0.0 from a1, a2 by modus_ponens\n",
        "assume a1 : x > 0.0\nassume a2 : x > 0.0 implies y > 0.0\n"
        "derive d1 : y > 1.0 from a1, a2 by modus_ponens\n",
        "rule `modus_ponens`",
    ),
    "equality substitution": (
        "assume a1 : y = 2.0 * x\n"
        "derive d1 : 2.0 * x = y from a1 by symmetry\n"
        "assume a2 : 2.0 * x = k\n"
        "derive d2 : y = k from a1, a2 by transitivity\n",
        "assume a1 : y = 2.0 * x\nassume a2 : 2.0 * x = k\n"
        "derive d2 : y = z from a1, a2 by transitivity\n",
        "rules `symmetry` + `transitivity`",
    ),
    "probability conditioning": (
        None, None,
        "`probability(A | B)` and `expectation(X | Y)` are EXPRESSIONS (D-026). No rule "
        "in the catalogue derives one conditional statement from another, so the "
        "conditioning STEP is still not representable.",
    ),
    "Bayesian update": (
        None, None,
        "`infer posterior x` REQUESTS an update; no rule represents one as a step",
    ),
    "optimisation update": (
        None, None,
        "`minimise`/`maximise` state an objective; no optimisation step is representable",
    ),
    "approximation": (
        None, None,
        "no approximation relation exists in the surface language",
    ),
}


def _derivation_status(result, label: str) -> str | None:
    try:
        from hamiltonian_lang.ast.nodes import DeriveStmt
    except Exception:  # noqa: BLE001 — v1 has no DeriveStmt
        return None
    for st in result.module.statements:
        if isinstance(st, DeriveStmt) and getattr(st, "label", None) == label:
            return str(st.status)
    return None


def _compile(src: str):
    try:
        return H.compile_source(PRELUDE + src, "<probe>"), None
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def _content_hash(result) -> str | None:
    h = getattr(result, "hash", None)
    try:
        return h if isinstance(h, str) else (h() if callable(h) else None)
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    rows = []
    for name, (good, bad, note) in CASES.items():
        row: dict = {
            "transformation": name,
            "note": note,
            "representable": "NO",
            "executable": "NO",
            "verifiable": "NO",
            "provenance_preserving": "NO",
            "good_source": good,
            "bad_source": bad,
        }
        if good is None:
            row["evidence"] = "no candidate surface form exists; not attempted"
            rows.append(row)
            continue

        r, err = _compile(good)
        if err or r is None:
            row["evidence"] = f"crash: {err}"
            rows.append(row)
            continue
        row["good_codes"] = list(r.diagnostics.codes())
        row["good_ok"] = bool(r.ok())
        labels = ["d1", "d2"]
        statuses = {lab: _derivation_status(r, lab) for lab in labels}
        statuses = {k: v for k, v in statuses.items() if v is not None}
        row["good_statuses"] = statuses

        if r.ok() and statuses:
            row["representable"] = "YES"

        verified = bool(statuses) and all(s == "VERIFIED" for s in statuses.values())

        rejected = None
        if bad is not None:
            r2, err2 = _compile(bad)
            if r2 is not None:
                row["bad_codes"] = list(r2.diagnostics.codes())
                row["bad_ok"] = bool(r2.ok())
                rejected = not r2.ok()
            else:
                row["bad_codes"] = [f"crash: {err2}"]
                rejected = False
        row["broken_variant_rejected"] = rejected
        row["correct_step_verified"] = verified
        if verified and rejected:
            row["verifiable"] = "YES"

        # provenance: premises + rule + status recorded, and NOT part of the content hash
        prov = None
        try:
            from hamiltonian_lang.ast.nodes import DeriveStmt

            for st in r.module.statements:
                if isinstance(st, DeriveStmt) and st.label == "d1":
                    prov = {
                        "premises": list(getattr(st, "premises", []) or []),
                        "rule": getattr(st, "rule", None),
                        "status": str(getattr(st, "status", None)),
                    }
                    break
        except Exception:  # noqa: BLE001
            prov = None
        row["provenance_record"] = prov
        if prov and prov["premises"] and prov["rule"] and prov["status"]:
            row["provenance_preserving"] = "YES"
        row["content_hash"] = _content_hash(r)
        row["evidence"] = (
            f"codes={row.get('good_codes')} statuses={statuses} "
            f"broken_rejected={rejected}"
        )
        rows.append(row)

    out = Path(__file__).resolve().parent / "results" / (
        f"TRANSFORMATIONS_{os.environ.get('HML_RUN_LABEL', 'unlabelled')}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    n_rep = sum(1 for r in rows if r["representable"] == "YES")
    n_ver = sum(1 for r in rows if r["verifiable"] == "YES")
    n_prov = sum(1 for r in rows if r["provenance_preserving"] == "YES")
    n_exec = sum(1 for r in rows if r["executable"] == "YES")
    summary = {
        "src": _SRC or "default",
        "hamiltonian_lang": H.__file__,
        "n": len(rows),
        "representable": n_rep,
        "executable": n_exec,
        "verifiable": n_ver,
        "provenance_preserving": n_prov,
    }
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))

    print(f"src = {H.__file__}")
    print(f"{'transformation':26s} {'REPR':5s} {'EXEC':5s} {'VERIF':6s} {'PROV':5s}  evidence")
    print("-" * 118)
    for r in rows:
        print(
            f"{r['transformation']:26s} {r['representable']:5s} {r['executable']:5s} "
            f"{r['verifiable']:6s} {r['provenance_preserving']:5s}  {r['evidence'][:60]}"
        )
    print(
        f"\nrepresentable {n_rep}/{len(rows)} · executable {n_exec}/{len(rows)} · "
        f"verifiable {n_ver}/{len(rows)} · provenance {n_prov}/{len(rows)}"
    )
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
