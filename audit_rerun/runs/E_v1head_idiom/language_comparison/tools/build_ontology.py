#!/usr/bin/env python3
"""Assemble MATHEMATICAL_REASONING_ONTOLOGY_V1.json from the per-domain fragments.

Deterministic: fragments are read in sorted filename order and atoms are emitted
in sorted-by-id order within each domain, so the output byte stream depends only
on the inputs.

Also validates the ontology:
  * atom ids are unique, uppercase, dotted
  * every ``depends_on`` / ``composes_with`` target exists
  * criticality and weight are consistent with the declared banding
  * declared domain matches the fragment file it appears in

Usage:
    python3 tools/build_ontology.py            # write + validate
    python3 tools/build_ontology.py --check    # validate only, non-zero exit on error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FRAGMENT_DIR = ROOT / "ontology" / "_domains"
OUTPUT = ROOT / "ontology" / "MATHEMATICAL_REASONING_ONTOLOGY_V1.json"

ONTOLOGY_VERSION = "1.0.0"

DOMAINS = [
    "A_FOUNDATIONS_LOGIC",
    "B_NUMBER_SYSTEMS",
    "C_ALGEBRA",
    "D_ANALYSIS",
    "E_PROBABILITY",
    "F_STATISTICS",
    "G_DISCRETE",
    "H_GEOMETRY_TOPOLOGY",
    "I_OPTIMIZATION",
    "J_SCIENTIFIC_UNITS",
    "K_NUMERICAL",
    "L_REASONING_EPISTEMICS",
    "M_TRANSFORMATIONS_INFERENCE",
]

# Weight bands per criticality. Criticality is the qualitative judgement;
# weight is the quantitative scoring coefficient. They must agree.
WEIGHT_BANDS = {
    "CRITICAL": (9, 10),
    "HIGH": (7, 8),
    "MEDIUM": (5, 6),
    "LOW": (1, 4),
}

REQUIRED_FIELDS = [
    "id",
    "domain",
    "name",
    "essential_semantics",
    "canonical_example",
    "criticality",
    "weight",
    "depends_on",
    "composes_with",
    "rationale",
]

ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(\.[A-Z][A-Z0-9_]*)+$")


def load_fragments() -> list[dict]:
    atoms: list[dict] = []
    for path in sorted(FRAGMENT_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            raise SystemExit(f"{path}: expected a JSON array of atoms")
        for atom in data:
            atom["_fragment"] = path.stem
        atoms.extend(data)
    return atoms


def validate(atoms: list[dict]) -> list[str]:
    errors: list[str] = []
    ids = [a.get("id") for a in atoms]
    seen: set[str] = set()

    for atom in atoms:
        aid = atom.get("id", "<missing id>")
        for field in REQUIRED_FIELDS:
            if field not in atom:
                errors.append(f"{aid}: missing required field '{field}'")
        if not isinstance(aid, str) or not ID_RE.match(aid):
            errors.append(f"{aid}: id is not a dotted uppercase identifier")
        if aid in seen:
            errors.append(f"{aid}: duplicate id")
        seen.add(aid)

        dom = atom.get("domain")
        if dom not in DOMAINS:
            errors.append(f"{aid}: unknown domain {dom!r}")
        if dom != atom.get("_fragment"):
            errors.append(
                f"{aid}: declared domain {dom!r} does not match fragment "
                f"{atom.get('_fragment')!r}"
            )

        crit = atom.get("criticality")
        weight = atom.get("weight")
        if crit not in WEIGHT_BANDS:
            errors.append(f"{aid}: unknown criticality {crit!r}")
        elif not isinstance(weight, int):
            errors.append(f"{aid}: weight must be an integer, got {weight!r}")
        else:
            lo, hi = WEIGHT_BANDS[crit]
            if not lo <= weight <= hi:
                errors.append(
                    f"{aid}: weight {weight} outside band {lo}-{hi} for {crit}"
                )

        for field in ("depends_on", "composes_with"):
            refs = atom.get(field, [])
            if not isinstance(refs, list):
                errors.append(f"{aid}: '{field}' must be a list")
                continue
            if len(set(refs)) != len(refs):
                errors.append(f"{aid}: '{field}' contains duplicates")
            if aid in refs:
                errors.append(f"{aid}: '{field}' refers to itself")

    known = set(seen)
    for atom in atoms:
        aid = atom.get("id")
        for field in ("depends_on", "composes_with"):
            for ref in atom.get(field, []):
                if ref not in known:
                    errors.append(f"{aid}: '{field}' references unknown atom {ref!r}")

    if len(ids) < 300:
        errors.append(f"ontology has {len(ids)} atoms; the design target is >= 300")
    return errors


def build(atoms: list[dict]) -> dict:
    clean = []
    for atom in sorted(atoms, key=lambda a: (a["domain"], a["id"])):
        atom = {k: v for k, v in atom.items() if not k.startswith("_")}
        atom["depends_on"] = sorted(atom["depends_on"])
        atom["composes_with"] = sorted(atom["composes_with"])
        clean.append(atom)

    by_domain: dict[str, int] = {d: 0 for d in DOMAINS}
    by_criticality: dict[str, int] = {c: 0 for c in WEIGHT_BANDS}
    for atom in clean:
        by_domain[atom["domain"]] += 1
        by_criticality[atom["criticality"]] += 1

    return {
        "ontology_id": "MATHEMATICAL_REASONING_ONTOLOGY",
        "version": ONTOLOGY_VERSION,
        "purpose": (
            "A language-independent inventory of capability atoms that a system "
            "claiming to represent mathematical reasoning may be scored against. "
            "It is specified without reference to any particular implementation: "
            "the question behind every atom is 'what would a faithful "
            "representation of mathematics have to be able to express?', not "
            "'what does some existing system happen to provide?'."
        ),
        "scope": {
            "in_scope": (
                "Mathematical and scientific reasoning: logic and foundations, "
                "number systems, algebra, analysis, probability, statistics, "
                "discrete mathematics, geometry and topology, optimisation, "
                "units and dimensions, numerical method semantics, epistemic "
                "status of statements, and meaning-preserving transformation."
            ),
            "out_of_scope": (
                "General-purpose software concerns are excluded by construction: "
                "networking, HTTP, user interfaces, filesystems, persistence, "
                "concurrency primitives, business-domain objects, serialisation "
                "formats. A system is neither credited nor penalised for them."
            ),
        },
        "criticality_definition": {
            "CRITICAL": (
                "A representation lacking this atom cannot faithfully express a "
                "broad and important class of mathematics at all; the gap is not "
                "closable by user-level composition."
            ),
            "HIGH": (
                "Absence blocks or distorts a substantial, frequently occurring "
                "class of statements, or forces an encoding that loses semantics."
            ),
            "MEDIUM": (
                "Absence is a real limitation within one domain but is usually "
                "workaroundable with an explicit, faithful encoding."
            ),
            "LOW": (
                "Specialised or boundary-marking. Included to delimit the space "
                "and to probe hidden assumptions, not as an expectation."
            ),
        },
        "weight_bands": {k: list(v) for k, v in WEIGHT_BANDS.items()},
        "size_note": (
            "The design target for V1 was 300-450 atoms. The delivered ontology "
            "exceeds the upper end of that range. No atom was removed to hit the "
            "number: every atom present names a capability that some class of "
            "mathematical statement genuinely requires, and cutting to a quota "
            "would have made coverage a function of an arbitrary budget rather "
            "than of the subject matter. Scoring is weight-based, so the extra "
            "LOW-weight atoms shift aggregate scores only slightly; they exist "
            "mainly to delimit the space and to probe hidden assumptions."
        ),
        "counts": {
            "total_atoms": len(clean),
            "by_domain": by_domain,
            "by_criticality": by_criticality,
        },
        "atoms": clean,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate only")
    args = parser.parse_args()

    atoms = load_fragments()
    errors = validate(atoms)
    for err in errors:
        print(f"ERROR {err}", file=sys.stderr)
    if errors:
        return 1
    if args.check:
        print(f"OK: {len(atoms)} atoms, no validation errors")
        return 0

    doc = build(atoms)
    OUTPUT.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {doc['counts']['total_atoms']} atoms")
    for dom, n in doc["counts"]["by_domain"].items():
        print(f"  {dom:32s} {n:4d}")
    print(f"  criticality: {doc['counts']['by_criticality']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
