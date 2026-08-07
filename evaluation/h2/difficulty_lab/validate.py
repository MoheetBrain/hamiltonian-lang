"""Offline validation gate — must pass before any model call (directive §6).

Checks, per family, over >=100 generated instances:

* every instance has a deterministic oracle answer;
* the same seed reproduces the same specimen, byte for byte;
* no duplicate problem text within a family;
* answers are not degenerate (a family whose answer is always TRUE measures nothing);
* an **independent second implementation** of each oracle agrees on a sample.

The second implementation is the part that matters. An oracle checked only against itself
is checked against nothing, and this project has already shipped one answer key that was
wrong in a way a re-derivation would have caught.
"""

from __future__ import annotations

import collections
import json
import sys
from fractions import Fraction
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from evaluation.h2.difficulty_lab.families import (  # noqa: E402
    FAMILIES,
    GENERATOR_VERSION,
    LEVELS,
    generate,
)
from evaluation.h2.difficulty_lab.scorer import (  # noqa: E402
    SCORER_VERSION,
    extraction_selftest,
    selftest,
)

N_PER_FAMILY = 120


def _recheck_algebraic(spec) -> str:
    """Independent re-derivation: re-parse the ENGLISH and re-evaluate.

    Deliberately reads the rendered prompt rather than the generator's own dictionary, so
    a bug in rendering — a definition shown differently from how it was computed — is
    caught rather than mirrored.
    """
    import re

    body = spec.prompt.split("\n\n")[1]
    defs: dict[str, str] = {}
    for line in body.strip().splitlines():
        lhs, rhs = line.strip().split("=", 1)
        defs[lhs.strip()] = rhs.strip()
    target = re.search(r"exact value of (\w+)", spec.prompt).group(1)

    seen: set[str] = set()

    def val(name: str) -> Fraction:
        if name in seen:
            raise RuntimeError("cycle")
        rhs = defs[name]
        m = re.fullmatch(r"-?\d+", rhs)
        if m:
            return Fraction(int(rhs))
        m = re.fullmatch(r"(\d+) \* (\w+) ([+-]) (\d+) \* (\w+)", rhs)
        ca, a, op, cb, b = m.groups()
        left, right = int(ca) * val(a), int(cb) * val(b)
        return left + right if op == "+" else left - right

    got = val(target)
    return str(got.numerator) if got.denominator == 1 else str(got)


def _recheck_quantifier(spec) -> str:
    """Independent re-derivation: re-parse the pair list from the ENGLISH and re-enumerate."""
    import re

    dm = re.search(r"D = \{([^}]*)\}", spec.prompt)
    elems = [int(x.strip()) for x in dm.group(1).split(",")]
    pairs = set()
    pm = re.findall(r"\((\d+),(\d+)\)", spec.prompt)
    for a, b in pm:
        pairs.add((int(a), int(b)))
    R = {(a, b): (a, b) in pairs for a in elems for b in elems}
    stmt = spec.prompt.split("Is the following statement true or false?")[1]
    if "for every x there exists a y" in stmt:
        truth = all(any(R[(a, b)] for b in elems) for a in elems)
    elif "there exists a y such that for every x" in stmt:
        truth = any(all(R[(a, b)] for a in elems) for b in elems)
    elif "if R(x, y) then R(y, x)" in stmt:
        truth = all((not R[(a, b)]) or R[(b, a)] for a in elems for b in elems)
    else:
        truth = any(all(not R[(a, b)] for b in elems) for a in elems)
    return "TRUE" if truth else "FALSE"


def main() -> int:
    print(f"generator {GENERATOR_VERSION} · scorer {SCORER_VERSION}\n")

    bad = selftest()
    ebad = extraction_selftest()
    print(f"scorer self-test      : {'PASS' if not bad else 'FAIL ' + str(bad)}")
    print(f"extraction self-test  : {'PASS' if not ebad else 'FAIL ' + str(ebad)}")
    if bad or ebad:
        return 1

    report: dict = {
        "generator_version": GENERATOR_VERSION,
        "scorer_version": SCORER_VERSION,
        "n_per_family": N_PER_FAMILY,
        "families": {},
    }
    ok_all = True

    for family in FAMILIES:
        specs = []
        for level in LEVELS:
            for seed in range(N_PER_FAMILY // len(LEVELS)):
                specs.append(generate(family, level, seed))

        answers = [s.answer for s in specs]
        prompts = [s.prompt for s in specs]

        determinism = all(
            generate(s.family, s.level, s.seed).to_dict() == s.to_dict() for s in specs[:25]
        )
        dupes = len(prompts) - len(set(prompts))
        dist = collections.Counter(answers)
        # A family whose answer is always the same measures nothing.
        degenerate = len(dist) == 1
        top_share = dist.most_common(1)[0][1] / len(answers)

        cross = "n/a"
        if family == "ALGEBRAIC_DEPENDENCY_GRAPH":
            mism = [s.task_id for s in specs[:40] if _recheck_algebraic(s) != s.answer]
            cross = f"{40 - len(mism)}/40" + (f" MISMATCH {mism[:3]}" if mism else "")
            ok_all &= not mism
        elif family == "FINITE_QUANTIFIER_WORLD":
            mism = [s.task_id for s in specs[:40] if _recheck_quantifier(s) != s.answer]
            cross = f"{40 - len(mism)}/40" + (f" MISMATCH {mism[:3]}" if mism else "")
            ok_all &= not mism

        ok = determinism and dupes == 0 and not degenerate and top_share <= 0.85
        ok_all &= ok
        report["families"][family] = {
            "n": len(specs),
            "deterministic": determinism,
            "duplicate_prompts": dupes,
            "answer_distribution": dict(dist.most_common(6)),
            "max_answer_share": round(top_share, 3),
            "independent_cross_check": cross,
            "ok": ok,
        }
        print(
            f"{family:28} n={len(specs):3} det={determinism} dupes={dupes} "
            f"top_share={top_share:.2f} cross={cross} {'OK' if ok else 'FAIL'}"
        )

    out = Path(__file__).resolve().parent / "VALIDATION.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\n{'ALL FAMILIES VALID' if ok_all else 'VALIDATION FAILED'} -> {out}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
