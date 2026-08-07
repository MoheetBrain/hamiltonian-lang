"""Build the mathematical coverage matrix from the ontology and the measured evidence.

Honesty rules this file enforces mechanically
---------------------------------------------
1. **The HML column is derived from executed evidence**, not from reading the source.
   Every HML cell traces to a probe result or to a genome capability whose status was
   itself verified by execution.
2. **`?` is a legitimate value and is never upgraded to a guess.** The mission is explicit:
   do not fabricate a value because the table needs one. An atom with no evidence gets `?`
   and is counted separately from an atom measured as absent (`0`). Conflating "we did not
   check" with "it is missing" would be the easiest way to make this audit worthless.
3. **Aggregates never hide a critical zero.** Every summary reports CRITICAL-atom coverage
   separately, and lists the critical atoms scoring `0` by id.

Classification (from METRIC_DEFINITIONS.md):
    P core primitive · S standard-library/canonical derivation · C compositionally
    representable · B external backend required · L representable but semantically lossy ·
    0 not representable · ? unknown
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_DIR = ROOT / "ontology" / "_domains"
ONTOLOGY_FILE = ROOT / "ontology" / "MATHEMATICAL_REASONING_ONTOLOGY_V1.json"
MATRICES = ROOT / "matrices"


#: Capability strings used in the early probe suites that predate ONTOLOGY_V1, mapped onto
#: their V1 ids. Found by the ontology agent, which reported that 17 ids in the composition
#: and definedness suites would not join. Without this the affected probes silently fall out
#: of the matrix and their atoms read as `?` -- which is exactly the "we did not check" vs
#: "it is missing" conflation the matrix exists to avoid.
PROBE_ID_REMAP: dict[str, str] = {
    "ALG.EIGENVALUE": "ALG.EIGEN",
    "ALG.INDEXING": "LOGIC.INDEXED_FAMILY",
    "LOGIC.FUNCTION": "LOGIC.FUNCTION_AS_OBJECT",
    "LOGIC.PIECEWISE_DEFINITION": "ANA.PIECEWISE",
    "LOGIC.UNIQUENESS": "LOGIC.EXISTS_UNIQUE",
    "NUM.APPROXIMATE": "NUMER.APPROXIMATION_MARKER",
    "NUM.DIVISION": "LOGIC.PARTIAL_DEFINEDNESS",
    "NUM.REFINEMENT": "LOGIC.SUBTYPING_REFINEMENT",
    "NUM.REFINEMENT.PROBABILITY": "NUM.PROBABILITY_SCALAR",
    "NUM.REFINEMENT.NATURAL": "NUM.NATURAL",
    "PROB.CONDITIONAL": "PROB.CONDITIONAL_PROBABILITY",
    "PROB.CONDITIONAL_ON_SIGMA_ALGEBRA": "PROB.CONDITIONING_ON_SIGMA_ALGEBRA",
    "PROB.DISTRIBUTION": "PROB.DISTRIBUTION_OBJECT",
    "SCI.DIMENSIONAL_ALGEBRA": "SCI.DIMENSION",
    "SCI.DIMENSIONAL_EQUALITY": "SCI.DIMENSIONAL_HOMOGENEITY",
    "SCI.PHYSICAL_QUANTITY": "SCI.QUANTITY",
    "DEFINEDNESS.SQRT": "LOGIC.PARTIAL_DEFINEDNESS",
    "DEFINEDNESS.LOG": "LOGIC.PARTIAL_DEFINEDNESS",
    "DEFINEDNESS.DIVISION_BY_ZERO": "LOGIC.PARTIAL_DEFINEDNESS",
    "ALG.MATRIX.PRODUCT": "ALG.MATRIX_ARITHMETIC",
    "ALG.MATRIX.INVERSE": "ALG.MATRIX_INVERSE",
    "LOGIC.VACUOUS_TRUTH": "LOGIC.FORALL",
}

FAITHFUL = {"P", "S", "C"}  # counts toward "faithfully representable"
PRESENT = FAITHFUL | {"B", "L"}  # representable at all, however imperfectly


def load_ontology() -> list[dict[str, Any]]:
    """Prefer the merged file; fall back to the per-domain shards."""
    if ONTOLOGY_FILE.exists():
        data = json.loads(ONTOLOGY_FILE.read_text())
        atoms = data if isinstance(data, list) else data.get("atoms", [])
        if atoms:
            return atoms
    atoms: list[dict[str, Any]] = []
    for f in sorted(ONTOLOGY_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        items = d if isinstance(d, list) else (d.get("atoms") or d.get("capabilities") or [])
        atoms.extend(items)
    return atoms


def load_probe_evidence() -> dict[str, dict[str, Any]]:
    """Every executed probe, keyed by the capability string it declared.

    **Precedence matters and is explicit.** A probe written against an exact ontology id
    (the critical-atom suite) always beats a legacy probe that reaches the same atom only
    through `PROBE_ID_REMAP`. Without this rule, `setdefault` resolved by glob order, and a
    definedness probe that happened to fail on an unrelated type mismatch claimed
    `PROB.CONDITIONAL_PROBABILITY` and scored it `L` -- while the purpose-built probe
    (`Pr(A | B)` -> `HML-P201`, i.e. no grammar for it at all) was discarded. That silently
    moved a CRITICAL atom out of the zero list, which is exactly the kind of error the
    criticals-first rule exists to make impossible.
    """
    exact: dict[str, dict[str, Any]] = {}
    remapped: dict[str, dict[str, Any]] = {}
    for f in sorted(MATRICES.glob("HML_*_PROBES.json")):
        d = json.loads(f.read_text())
        for r in d.get("results", []):
            for cap in str(r.get("capability", "")).split("/"):
                cap = cap.strip()
                if not cap:
                    continue
                exact.setdefault(cap, r)
                mapped = PROBE_ID_REMAP.get(cap)
                if mapped:
                    remapped.setdefault(mapped, r)
    # Remapped evidence fills only atoms no exact probe reached.
    return {**remapped, **exact}


def hml_classification(atom: dict[str, Any], probes: dict[str, dict[str, Any]]) -> tuple[str, str, str]:
    """Return (code, evidence, evidence_quality) for one atom in HML.

    Matching is deliberately conservative: an atom is only classified from a probe whose
    declared capability names it. Everything else stays `?`, which is the honest value for
    "this audit did not test it".
    """
    aid = atom["id"]

    # Direct hit: a probe declared this exact ontology id.
    p = probes.get(aid)
    if p is None:
        # Allow a probe to cover an atom by prefix (e.g. DEFINEDNESS.SQRT covers
        # NUM.SQRT.DOMAIN) only when the probe's capability string contains the id.
        for cap, rec in probes.items():
            if aid in cap:
                p = rec
                break

    if p is None:
        return "?", "not probed by this audit", "—"

    src = p["source"].replace("\n", " ; ")
    codes = ",".join(p["codes"]) if p["codes"] else "clean"
    ev = f'`{src}` -> {codes}'

    if p["ok"]:
        return "P", ev, "A"
    # Compiles-with-error: distinguish "correctly rejected" from "cannot express".
    if p["mode"] == "reject":
        return "P", ev + " (correctly rejected — the check exists)", "A"
    first = (p["codes"] or [""])[0]
    if first.startswith(("HML-P", "HML-L")):
        return "0", ev + " (grammar has no production)", "A"
    if first.startswith("HML-N"):
        return "0", ev + " (no such function/name)", "A"
    if first.startswith(("HML-T", "HML-D")):
        return "L", ev + " (expressible only by weakening the declared type)", "A"
    return "?", ev, "C"


def main() -> int:
    atoms = load_ontology()
    if not atoms:
        print("ontology not available yet; nothing to build")
        return 1
    probes = load_probe_evidence()

    rows: list[dict[str, Any]] = []
    for a in atoms:
        code, ev, q = hml_classification(a, probes)
        rows.append(
            {
                "ontology_id": a["id"],
                "domain": a.get("domain", ""),
                "name": a.get("name", ""),
                "criticality": a.get("criticality", ""),
                "weight": a.get("weight", ""),
                "HML": code,
                "HML_evidence": ev,
                "HML_evidence_quality": q,
            }
        )

    MATRICES.mkdir(parents=True, exist_ok=True)
    csv_path = MATRICES / "MATHEMATICAL_COVERAGE_MATRIX.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    probed = [r for r in rows if r["HML"] != "?"]
    crit = [r for r in rows if str(r["criticality"]).upper() == "CRITICAL"]
    crit_probed = [r for r in crit if r["HML"] != "?"]
    crit_zero = [r for r in crit if r["HML"] == "0"]

    def pct(n: int, d: int) -> float | None:
        return round(100 * n / d, 1) if d else None

    summary = {
        "n_atoms": len(rows),
        "n_probed_by_this_audit": len(probed),
        "coverage_is_computed_over": (
            "PROBED atoms only. Unprobed atoms are '?' and are excluded from every "
            "percentage rather than being counted as absent. A percentage over the whole "
            "ontology would be an artefact of how many probes were written."
        ),
        "faithful_of_probed": pct(sum(1 for r in probed if r["HML"] in FAITHFUL), len(probed)),
        "present_of_probed": pct(sum(1 for r in probed if r["HML"] in PRESENT), len(probed)),
        "absent_of_probed": pct(sum(1 for r in probed if r["HML"] == "0"), len(probed)),
        "lossy_of_probed": pct(sum(1 for r in probed if r["HML"] == "L"), len(probed)),
        "critical_atoms": len(crit),
        "critical_probed": len(crit_probed),
        "critical_faithful_of_probed": pct(
            sum(1 for r in crit_probed if r["HML"] in FAITHFUL), len(crit_probed)
        ),
        "CRITICAL_ATOMS_SCORING_ZERO": [r["ontology_id"] for r in crit_zero],
        "distribution": {
            c: sum(1 for r in rows if r["HML"] == c) for c in ["P", "S", "C", "B", "L", "0", "?"]
        },
    }
    (MATRICES / "MATHEMATICAL_COVERAGE_MATRIX.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2)
    )

    print(json.dumps(summary, indent=2))
    print(f"\n-> {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
