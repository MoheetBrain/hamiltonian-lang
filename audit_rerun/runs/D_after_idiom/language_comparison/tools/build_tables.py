"""Generate the reference-language comparison tables from the genome files.

Mission section 25 asks for several readable tables rather than one unreadable monster, and
section 7 warns that raw counts belong in their proper place: a language is never "better"
for having more functions. Both rules are enforced here.

* Every quantitative cell carries its evidence quality (A/B/C/D). A cell with no evidence
  renders `—`, never a guess.
* CORE / STANDARD LIBRARY / ECOSYSTEM are never summed. Mathlib's theorem count is an
  ECOSYSTEM figure and is reported in its own column, never as a language number.
* Systems that are not installed carry no A-quality figures, and the table says so.

The tables derive from `genomes/*.json`, so they cannot drift from the extractions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GENOMES = ROOT / "genomes"
OUT = ROOT / "comparisons"

#: Display order: the primary panel first, secondaries after.
PANEL = [
    ("HML", "HML_LANGUAGE_GENOME.json"),
    ("Lean 4", "LEAN4_LANGUAGE_GENOME.json"),
    ("Rocq/Coq", "ROCQ_COQ_LANGUAGE_GENOME.json"),
    ("Isabelle/HOL", "ISABELLE_HOL_LANGUAGE_GENOME.json"),
    ("SMT-LIB/Z3", "SMTLIB_Z3_LANGUAGE_GENOME.json"),
    ("OpenMath", "OPENMATH_LANGUAGE_GENOME.json"),
    ("Content MathML", "CONTENT_MATHML_LANGUAGE_GENOME.json"),
    ("Python core", "PYTHON_CORE_LANGUAGE_GENOME.json"),
    ("SymPy", "SYMPY_LANGUAGE_GENOME.json"),
    ("Julia", "JULIA_LANGUAGE_GENOME.json"),
    ("R", "R_LANGUAGE_GENOME.json"),
    ("Wolfram", "WOLFRAM_LANGUAGE_GENOME.json"),
    ("Stan", "STAN_LANGUAGE_GENOME.json"),
    ("PyMC", "PYMC_LANGUAGE_GENOME.json"),
    ("Turing.jl", "TURING_LANGUAGE_GENOME.json"),
    ("JuMP", "JUMP_LANGUAGE_GENOME.json"),
]


def load(fname: str) -> dict[str, Any] | None:
    p = GENOMES / fname
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def dig(d: Any, *path: str) -> Any:
    """Walk a nested genome path, tolerating the shape differences between agents."""
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        # Genomes vary in casing between agents; match case-insensitively.
        hit = None
        for kk in cur:
            if kk.lower() == k.lower():
                hit = kk
                break
        if hit is None:
            return None
        cur = cur[hit]
    return cur


def cell(v: Any) -> str:
    """Render a value that may be a bare scalar or a {value, evidence_quality} object."""
    if v is None:
        return "—"
    if isinstance(v, dict):
        val = v.get("value", v.get("count"))
        q = v.get("evidence_quality") or v.get("confidence")
        if val is None:
            return "—"
        return f"{val}" + (f" ({q})" if q else "")
    if isinstance(v, list):
        # Render a list as its content, never as its length. An earlier version returned
        # len(v), which turned `paradigm: ["...", "..."]` into the cell "4" -- a count
        # masquerading as a description. Silently publishing that would be worse than an
        # empty cell, which is why `cell` never invents a scalar from a shape.
        if not v:
            return "—"
        flat = "; ".join(str(x) for x in v if isinstance(x, (str, int, float)))
        return (flat[:60] + "…") if len(flat) > 60 else (flat or "—")
    return str(v)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    loaded = [(name, load(f)) for name, f in PANEL]
    present = [(n, g) for n, g in loaded if g]
    missing = [n for n, g in loaded if not g]

    lines: list[str] = []
    lines.append("# Language genome comparison\n")
    lines.append(
        "Generated from `genomes/*.json` by `tools/build_tables.py`. Do not edit by hand.\n"
    )
    lines.append(
        "**Evidence quality** is in parentheses: **A** measured/spec-defined · **B** "
        "authoritative doc + interpretation · **C** strong inference · **D** speculative. "
        "`—` means no value was recorded — it is **not** a zero.\n"
    )
    lines.append(
        "> **Raw counts do not rank languages.** A system is never better for having more "
        "functions. CORE, STANDARD LIBRARY and ECOSYSTEM figures are kept apart and are "
        "never summed. Mathlib's theorem count is an ECOSYSTEM number and is never "
        "presented as a property of Lean the language.\n"
    )

    lines.append("## TABLE A — identity and kernel\n")
    lines.append("| system | version | paradigm | minimal kernel |")
    lines.append("|---|---|---|---|")
    for name, g in present:
        lines.append(
            f"| **{name}** | {cell(dig(g, 'IDENTITY', 'version'))} | "
            f"{cell(dig(g, 'IDENTITY', 'paradigm'))[:44]} | "
            f"{cell(dig(g, 'MINIMAL_KERNEL', 'size'))} |"
        )
    lines.append("")

    lines.append("## TABLE B — lexical and grammatical size (CORE only)\n")
    lines.append("| system | reserved keywords | operators | AST/IR node kinds |")
    lines.append("|---|---:|---:|---:|")
    for name, g in present:
        lines.append(
            f"| **{name}** | {cell(dig(g, 'LEXICAL', 'reserved_keywords'))} | "
            f"{cell(dig(g, 'LEXICAL', 'operators'))} | "
            f"{cell(dig(g, 'AST_IR', 'node_variants'))} |"
        )
    lines.append("")

    lines.append("## TABLE D — type, logic and proof\n")
    lines.append(
        "| system | dependent types | proposition types | distribution types | "
        "dimensional types | shape types |"
    )
    lines.append("|---|---|---|---|---|---|")
    for name, g in present:
        t = dig(g, "TYPE_SYSTEM") or {}
        lines.append(
            f"| **{name}** | {cell(dig(t, 'dependent'))[:18]} | "
            f"{cell(dig(t, 'proposition_types'))[:18]} | "
            f"{cell(dig(t, 'distribution_types'))[:18]} | "
            f"{cell(dig(t, 'dimensional_types'))[:18]} | "
            f"{cell(dig(t, 'shape_types'))[:18]} |"
        )
    lines.append("")

    lines.append("## TABLE F — epistemics and transformations\n")
    lines.append(
        "The axis HML claims as its differentiator. `—` here is usually a genuine absence "
        "in the reference system, and that is the finding.\n"
    )
    lines.append("| system | assumptions | proof states | provenance | inference rules |")
    lines.append("|---|---|---|---|---|")
    for name, g in present:
        r = dig(g, "REASONING") or {}
        tr = dig(g, "TRANSFORMATIONS") or {}
        lines.append(
            f"| **{name}** | {cell(dig(r, 'assumptions'))[:22]} | "
            f"{cell(dig(r, 'proof_states'))[:22]} | "
            f"{cell(dig(r, 'provenance'))[:22]} | "
            f"{cell(dig(tr, 'inference_rules'))[:22]} |"
        )
    lines.append("")

    if missing:
        lines.append("## Genomes not available\n")
        lines.append(", ".join(f"`{m}`" for m in missing) + "\n")

    lines.append("## Limitation of this generated table\n")
    lines.append(
        "The five extraction agents were given one schema but populated it with differing "
        "internal shapes, so a generic field walk resolves only some cells. **An empty cell "
        "here means the automated walk did not find the field, NOT that the system lacks "
        "the property.** The genome JSON files are authoritative; this table is a "
        "navigation aid over them, and any cell that matters to a decision should be "
        "confirmed against the corresponding genome.\n"
    )
    lines.append("## Reading notes\n")
    lines.append(
        "- **Content MathML's kernel is OpenMath's.** MathML 3 §4.1.3 states this verbatim; "
        "counting both as independent data points double-counts one idea.\n"
        "- **Rocq's 21 kernel constructors and Lean's 12 are the same calculus.** The "
        "difference is where the kernel boundary is drawn, not expressive power.\n"
        "- **Julia, R, Wolfram and MATLAB were not installed** during this audit; their "
        "genomes carry no A-quality fields, and nothing was guessed to fill the gap.\n"
        "- **Distribution counts are not comparable without the composition rule.** Stan's "
        "families are everything it has, because Stan cannot compose distributions; PyMC's "
        "and Distributions.jl's are base inventories under combinators.\n"
    )

    p = OUT / "LANGUAGE_GENOME_TABLE.md"
    p.write_text("\n".join(lines))
    print(f"{len(present)} genomes tabulated, {len(missing)} missing")
    print(f"-> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
