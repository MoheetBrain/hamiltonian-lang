"""Materialise the HML-EVAL-001 corpus to disk — §4, §5.

    .venv/bin/python -m evaluation.build_corpus

Writes, under ``benchmarks/eval001/``:

    problems/<id>.json      the canonical semantic object
    arms/<arm>/<id>.txt     the exact prompt each arm receives
    MANIFEST.json           counts, hashes, and the declared information asymmetry

Rendering the arms to disk is not decoration: it makes the fairness property auditable by
inspection rather than by trust. Anyone can diff two arm files and see that the problem
statement and question are byte-identical.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hamiltonian_lang import compile_source

from .corpus.cso import CanonicalSemanticObject
from .corpus.generators import CATEGORY_TARGETS, build_all, build_demos
from .corpus.renderers import ARMS, INFORMATION_ASYMMETRY, render_arm, verify_shared_content_identical

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "benchmarks" / "eval001"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def main() -> int:
    corpus = build_all()
    demos = build_demos()
    demo_ids = {d.id for d in demos}

    (OUT / "problems").mkdir(parents=True, exist_ok=True)
    for arm in ARMS:
        (OUT / "arms" / arm).mkdir(parents=True, exist_ok=True)

    from .harness import _demo_pairs

    ref_ok = ref_fail = 0
    for cso in corpus:
        verify_shared_content_identical(cso)
        (OUT / "problems" / f"{cso.id}.json").write_text(cso.to_json() + "\n")
        for arm in ARMS:
            p = render_arm(arm, cso, _demo_pairs(arm))
            (OUT / "arms" / arm / f"{cso.id}.txt").write_text(
                f"### SYSTEM\n{p.system}\n\n### USER\n{p.user}\n"
            )
        if cso.reference_hml:
            r = compile_source(cso.reference_hml, cso.id)
            ref_ok += bool(r.ok())
            ref_fail += (not r.ok())

    # Leakage control: no benchmark item may appear in a demonstration.
    overlap = {c.id for c in corpus} & demo_ids
    assert not overlap, f"demonstration leaked into the benchmark: {overlap}"
    demo_prose = {d.prose for d in demos}
    leaked = [c.id for c in corpus if c.prose in demo_prose]
    assert not leaked, f"benchmark prose appears in a demonstration: {leaked}"

    by_domain: dict[str, int] = {}
    by_difficulty: dict[str, int] = {}
    by_answer_kind: dict[str, int] = {}
    for c in corpus:
        by_domain[c.domain] = by_domain.get(c.domain, 0) + 1
        by_difficulty[c.difficulty] = by_difficulty.get(c.difficulty, 0) + 1
        by_answer_kind[c.answer.kind] = by_answer_kind.get(c.answer.kind, 0) + 1

    manifest = {
        "corpus_version": corpus[0].corpus_version,
        "n_problems": len(corpus),
        "targets": CATEGORY_TARGETS,
        "by_domain": by_domain,
        "by_difficulty": by_difficulty,
        "by_answer_kind": by_answer_kind,
        "arms": ARMS,
        "n_demonstrations": len(demos),
        "demonstration_ids": sorted(demo_ids),
        "reference_hml_compiles": ref_ok,
        "reference_hml_fails": ref_fail,
        "leakage_control": (
            "Every problem is generated from a seeded template with randomised numeric "
            "parameters, so no exact item plausibly appears in any pretraining corpus. "
            "Demonstrations are separate objects and are asserted disjoint from the "
            "benchmark by both id and prose."
        ),
        "fairness_property": (
            "verify_shared_content_identical asserts that the problem statement and the "
            "question appear verbatim in all seven arm prompts. Arm files are written to "
            "disk so this is auditable by diff, not by trust."
        ),
        "information_asymmetry": INFORMATION_ASYMMETRY,
        "problem_hashes": {c.id: _sha(c.prose + c.question) for c in corpus},
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(f"problems written .......... {len(corpus)}")
    print(f"by domain ................. {by_domain}")
    print(f"by difficulty ............. {by_difficulty}")
    print(f"by answer kind ............ {by_answer_kind}")
    print(f"arm prompt files .......... {len(corpus) * len(ARMS)}")
    print(f"reference HML compiles .... {ref_ok} ok, {ref_fail} failing")
    print(f"leakage checks ............ passed")
    print(f"manifest .................. {OUT / 'MANIFEST.json'}")
    return 0 if ref_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
