"""Render the HML mathematical periodic table from the coverage matrix.

The brief's requirement is blunt: "It should be possible for a human to see HML's holes
immediately." So this renders capability status per domain, with CRITICAL atoms marked and
the zeros pulled to the front of each domain rather than sorted alphabetically into
invisibility.

Generated, never hand-maintained — the markdown derives from
`matrices/MATHEMATICAL_COVERAGE_MATRIX.json`, so it cannot drift from the measurements.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "matrices" / "MATHEMATICAL_COVERAGE_MATRIX.json"
OUT = ROOT / "hml" / "HML_MATHEMATICAL_PERIODIC_TABLE.md"

GLYPH = {
    "P": ("FULL", "🟩"),
    "S": ("LIBRARY", "🟦"),
    "C": ("COMPOSED", "🟦"),
    "B": ("BACKEND", "🟪"),
    "L": ("LOSSY", "🟧"),
    "0": ("ABSENT", "🟥"),
    "?": ("not probed", "⬜"),
}

DOMAIN_TITLE = {
    "A_FOUNDATIONS_LOGIC": "A · FOUNDATIONS / LOGIC",
    "B_NUMBER_SYSTEMS": "B · NUMBER SYSTEMS",
    "C_ALGEBRA": "C · ALGEBRA",
    "D_ANALYSIS": "D · ANALYSIS",
    "E_PROBABILITY": "E · PROBABILITY",
    "F_STATISTICS": "F · STATISTICS",
    "G_DISCRETE": "G · DISCRETE",
    "H_GEOMETRY_TOPOLOGY": "H · GEOMETRY / TOPOLOGY",
    "I_OPTIMIZATION": "I · OPTIMIZATION",
    "J_SCIENTIFIC_UNITS": "J · SCIENTIFIC / UNITS",
    "K_NUMERICAL": "K · NUMERICAL",
    "L_REASONING_EPISTEMICS": "L · REASONING / EPISTEMICS",
    "M_TRANSFORMATIONS_INFERENCE": "M · TRANSFORMATIONS / INFERENCE",
}


def main() -> int:
    data = json.loads(SRC.read_text())
    rows = data["rows"]
    summary = data["summary"]

    by_domain: dict[str, list[dict]] = {}
    for r in rows:
        by_domain.setdefault(r["domain"], []).append(r)

    out: list[str] = []
    out.append("# HML mathematical periodic table\n")
    out.append(
        f"Generated from `matrices/MATHEMATICAL_COVERAGE_MATRIX.json` "
        f"({summary['n_atoms']} atoms, {summary['n_probed_by_this_audit']} probed). "
        "Do not edit by hand — run `tools/build_periodic_table.py`.\n"
    )
    out.append(
        "**⬜ means NOT PROBED, not absent.** Distinguishing "
        "\"we did not check\" from \"it is missing\" is the whole point of the matrix; "
        f"{summary['distribution']['?']} atoms carry ⬜ and are excluded from every "
        "percentage.\n"
    )
    out.append("| glyph | meaning |\n|---|---|")
    for code, (label, g) in GLYPH.items():
        out.append(f"| {g} | `{code}` — {label} |")
    out.append("")

    out.append("## Critical zeros, first\n")
    out.append(
        "The severity rubric requires these before any aggregate, so that no summary "
        "figure can bury them.\n"
    )
    crit_zero = [r for r in rows if r["HML"] == "0" and str(r["criticality"]).upper() == "CRITICAL"]
    out.append("| ontology id | capability | domain |\n|---|---|---|")
    for r in sorted(crit_zero, key=lambda r: r["ontology_id"]):
        out.append(f"| 🟥 `{r['ontology_id']}` | {r['name']} | {r['domain'].split('_')[0]} |")
    out.append("")

    out.append("## By domain\n")
    for dom in DOMAIN_TITLE:
        items = by_domain.get(dom, [])
        if not items:
            continue
        probed = [i for i in items if i["HML"] != "?"]
        zeros = [i for i in items if i["HML"] == "0"]
        crit = [i for i in items if str(i["criticality"]).upper() == "CRITICAL"]
        out.append(f"### {DOMAIN_TITLE[dom]}\n")
        out.append(
            f"{len(items)} atoms · {len(crit)} critical · {len(probed)} probed · "
            f"**{len(zeros)} absent**\n"
        )
        # Zeros first, then lossy, then the rest — holes must be visible, not sorted away.
        order = {"0": 0, "L": 1, "B": 2, "C": 3, "S": 4, "P": 5, "?": 6}
        shown = sorted(items, key=lambda i: (order[i["HML"]], i["ontology_id"]))
        interesting = [i for i in shown if i["HML"] != "?"]
        if not interesting:
            out.append("_No atom in this domain was probed by this audit._\n")
            continue
        out.append("| | ontology id | capability | crit |\n|---|---|---|---|")
        for i in interesting:
            g = GLYPH[i["HML"]][1]
            c = "**C**" if str(i["criticality"]).upper() == "CRITICAL" else ""
            out.append(f"| {g} | `{i['ontology_id']}` | {i['name'][:52]} | {c} |")
        unprobed = len(items) - len(interesting)
        if unprobed:
            out.append(f"\n_{unprobed} further atoms in this domain were not probed (⬜)._\n")
        out.append("")

    out.append("## How to read this\n")
    out.append(
        "The holes are not evenly spread, and that is the finding. **Analysis** and the "
        "conditional/expectation half of **probability** are where HML stops being able to "
        "represent the mathematics at all — and those are the domains most of applied "
        "mathematics and statistics is written in. Algebra, dimensions, and the "
        "declaration/epistemic vocabulary are comparatively solid.\n"
    )
    OUT.write_text("\n".join(out))
    print(f"{len(rows)} atoms rendered, {len(crit_zero)} critical zeros surfaced")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
