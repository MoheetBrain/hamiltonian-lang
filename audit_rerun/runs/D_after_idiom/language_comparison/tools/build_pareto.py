"""The Pareto frontier of candidate HML additions (mission section 21).

The design objective is explicitly two-sided: maximise coverage, compositional closure,
semantic precision, verifiability, model writability, extensibility and interoperability,
while minimising grammar size, primitive count, token count, ambiguity, compiler complexity,
special cases and backend coupling.

So a candidate is not scored by "would this be nice". It is scored by **capability unlocked
per unit of complexity added**, and candidates that unlock nothing the language cannot
already express are excluded no matter how conventional they look.

Two rules are enforced here, both from the mission:

* **Do not propose cloning Lean + Wolfram + Julia + Stan.** Several obvious candidates are
  deliberately scored as LIBRARY-NOT-CORE or rejected outright, with the reason recorded.
* **This is analysis, not redesign.** Nothing here is implemented. The output ranks options
  for a decision that has not been taken.

Complexity is scored 1–10 on a published rubric (see `notes` per row): grammar productions
added, new type-system rules, new checker passes, and backend surface touched.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "hml"

# id, name, layer, critical_atoms_unlocked, high_atoms, compositions_unlocked,
# safety_delta, grammar_cost, compiler_cost, backend_cost, note
CANDIDATES = [
    (
        "P1", "Side-condition / obligation generation for partial operations", "CORE",
        0, 6, 3, 5, 2, 6, 1,
        "Emit an inspectable obligation whenever a partial operation appears (division, "
        "inverse, log, sqrt, index). Unlocks maturity criterion 3.4, which the ladder names "
        "as HALF the distinguishing capability of a reasoning IR. Closes H-1 (division "
        "unguarded), H-2 (tan/^ unguarded), and makes the existing sqrt/log discipline a "
        "policy rather than two special cases. Grammar cost is near zero -- this is a "
        "checker change, not a syntax change.",
    ),
    (
        "P2", "Let assumptions discharge side conditions", "CORE",
        0, 4, 4, 5, 1, 7, 0,
        "Connect the epistemic layer to the type/obligation layer so `assume x > 0` "
        "discharges log's domain restriction. Closes C-1, the sharpest finding in the audit. "
        "Requires an assumption context and a decision procedure for simple arithmetic "
        "predicates -- the compiler cost is real. Pairs with P1: neither is worth much alone, "
        "and together they are the difference between annotating and reasoning.",
    ),
    (
        "P3", "An expectation / probability term in the expression grammar", "CORE",
        4, 5, 4, 2, 3, 3, 3,
        "`E[X]`, `E[X|Y]`, `Pr(A|B)`, `Var[X]`. Unlocks 4 CRITICAL atoms (EXPECTATION, "
        "JOINT, CONDITIONAL_PROBABILITY, INDEPENDENCE) and most of STAT.*. Note that the "
        "type rules ALREADY EXIST -- `variance`/`expectation` are in the builtin table with "
        "full signatures and are unreachable because they are reserved keywords. Part of "
        "this candidate is deleting a lexer entry.",
    ),
    (
        "P4", "A derivation/inference statement form", "CORE",
        0, 8, 6, 4, 4, 8, 4,
        "A statement meaning `from A, by rule R, infer B`, carrying preconditions, side "
        "conditions and provenance. Takes N_transformation_forms from 0 to non-zero and is "
        "the other half of maturity criterion 3.5. The single largest change on this list, "
        "and the only one that addresses the project's actual thesis. The Python "
        "improvement/repair machinery already models this; the gap is surface syntax and "
        "a reachable path from `compile_source`.",
    ),
    (
        "P5", "Set membership and comprehension", "CORE",
        2, 3, 2, 1, 2, 2, 2,
        "`x in S`, `{ x : T | P(x) }`. `Set[T]` already exists as a type constructor with "
        "no elimination form, so sets are currently inert. Cheap, closes 2 CRITICAL atoms, "
        "and unlocks feasible sets and event algebra.",
    ),
    (
        "P6", "Make RandomVariable compose with Quantity", "CORE",
        0, 3, 2, 3, 0, 4, 1,
        "`RandomVariable[Quantity[Length]]` currently fails HML-T411 because the support "
        "check compares against the raw carrier type. A measured height in metres is the "
        "most ordinary object in scientific statistics. Zero grammar cost -- this is a "
        "support-check fix.",
    ),
    (
        "P7", "An approximation relation distinct from equality", "CORE",
        0, 3, 2, 4, 1, 3, 2,
        "`a ~= b` with an error term or bound. The project's charter forbids conflating `=` "
        "with approximation, and currently enforces that by having no approximation at all "
        "-- prevention by omission, which is not the same as distinction. Unlocks maturity "
        "criterion 3.7 and the whole NUMERICAL domain's epistemics.",
    ),
    (
        "P8", "An `import` / module-library layer", "CORE",
        0, 2, 1, 0, 1, 4, 1,
        "There is currently NO library layer: every file is closed-world and the standard "
        "library is whatever is compiled into the binary. Unlocks growth for every other "
        "capability without further compiler edits, so its real value is as a multiplier on "
        "P9 rather than as coverage in itself.",
    ),
    (
        "P9", "User-declarable distributions and types", "CORE",
        0, 2, 2, 1, 2, 5, 2,
        "Today a new distribution family or type requires a compiler edit. With P8 this "
        "moves statistics from a closed set of 16 families to an open one. Scored below P8 "
        "because without a library layer a user-declared family cannot be shared.",
    ),
    (
        "P10", "Analysis operators: limit, derivative, integral, indexed sum", "STDLIB",
        4, 6, 3, 1, 3, 4, 5,
        "Closes 4 CRITICAL atoms and most of domain D. Scored as STDLIB rather than CORE: "
        "these are binders over an expression, and once the language has a binder form they "
        "are library signatures rather than new semantics. Sequencing matters -- doing this "
        "before P4 buys notation without reasoning, which is the Wolfram failure mode.",
    ),
    (
        "P11", "Complex numbers", "STDLIB",
        0, 3, 1, 0, 1, 2, 3,
        "Currently `HML-T440: unknown type 'Complex'`. Excludes Fourier analysis, spectral "
        "theory and the general eigenvalue problem. A type-lattice addition, not a semantic "
        "one.",
    ),
    (
        "P12", "Fix `Predicate[T]` to be applicable", "CORE",
        0, 1, 1, 1, 0, 1, 0,
        "`Predicate[Real]` is declarable and not callable, while the structurally identical "
        "`Function[Real -> Bool]` works. A defect with a clean workaround: cheapest item on "
        "the list, smallest payoff. Included because the cost is close to zero.",
    ),
    # --- deliberately NOT recommended for core ---
    (
        "X1", "A tactic language / proof automation", "REJECT-NOT-CORE",
        0, 0, 0, 0, 9, 10, 8,
        "This is cloning Lean. HML has no proof calculus, no trusted kernel and no soundness "
        "argument; a tactic layer on top of a system where `prove 1 = 2` compiles clean "
        "would produce authoritative-looking output with nothing behind it -- the exact "
        "failure mode CLAUDE.md names as the worst in the codebase. Level 4 is a different "
        "paradigm, not a further step.",
    ),
    (
        "X2", "A large mathematical function library", "REJECT-NOT-CORE",
        0, 0, 0, 0, 1, 2, 6,
        "Going from 7 builtins to hundreds. Adds vocabulary, not expressive power, and would "
        "inflate every raw count while changing no capability class. Belongs in a library "
        "behind P8, and is worthless before P8 exists.",
    ),
    (
        "X3", "General term rewriting / simplification engine", "REJECT-NOT-CORE",
        0, 0, 0, -2, 3, 9, 4,
        "Cloning SymPy/Wolfram. Negative safety delta: an unchecked rewriter that silently "
        "returns an unevaluated or subtly different expression is precisely what makes those "
        "systems untrustworthy for reasoning. Only defensible AFTER P4, as rules whose "
        "preservation is checked.",
    ),
]

HEADER = [
    "id", "name", "layer", "critical_atoms_unlocked", "high_atoms_unlocked",
    "compositions_unlocked", "safety_delta", "grammar_cost", "compiler_cost",
    "backend_cost", "total_cost", "benefit", "ratio", "note",
]


def main() -> int:
    rows = []
    for (
        cid, name, layer, crit, high, comps, safety, gcost, ccost, bcost, note
    ) in CANDIDATES:
        # Benefit weights criticals heavily: the severity rubric makes a critical zero
        # qualitatively different from a missing convenience, and an aggregate that
        # averaged them would hide exactly what matters.
        benefit = 3 * crit + 1 * high + 2 * comps + 2 * safety
        cost = gcost + ccost + bcost
        ratio = round(benefit / cost, 2) if cost else None
        rows.append(
            {
                "id": cid, "name": name, "layer": layer,
                "critical_atoms_unlocked": crit, "high_atoms_unlocked": high,
                "compositions_unlocked": comps, "safety_delta": safety,
                "grammar_cost": gcost, "compiler_cost": ccost, "backend_cost": bcost,
                "total_cost": cost, "benefit": benefit, "ratio": ratio, "note": note,
            }
        )

    recommended = [r for r in rows if not r["layer"].startswith("REJECT")]
    recommended.sort(key=lambda r: (-(r["ratio"] or 0), r["total_cost"]))

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "HML_PARETO_UPGRADE_FRONTIER.csv"
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        w.writeheader()
        w.writerows(recommended + [r for r in rows if r["layer"].startswith("REJECT")])

    (OUT / "HML_PARETO_UPGRADE_FRONTIER.json").write_text(json.dumps(rows, indent=2))

    print(f"{'rank':5s} {'id':4s} {'ratio':6s} {'ben':4s} {'cost':5s} {'layer':16s} name")
    print("-" * 96)
    for i, r in enumerate(recommended, 1):
        print(
            f"{i:<5d} {r['id']:4s} {str(r['ratio']):6s} {r['benefit']:<4d} "
            f"{r['total_cost']:<5d} {r['layer']:16s} {r['name'][:44]}"
        )
    print("\nDeliberately NOT recommended for core:")
    for r in rows:
        if r["layer"].startswith("REJECT"):
            print(f"      {r['id']:4s} {'':6s} {'':4s} {'':5s} {r['layer']:16s} {r['name'][:44]}")
    print(f"\n-> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
