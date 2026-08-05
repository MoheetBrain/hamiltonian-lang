"""Deterministic scoring for the V1 concept-kernel ablation — Phase 10, deliverable 2.

Extends the patterns of ``evaluation/analyse.py`` rather than replacing them: the
bootstrap, the paired difference, McNemar's exact test and Cohen's h are **imported**
from there, so the V0 and V1 experiments are analysed by the same arithmetic and remain
comparable.

Two rules govern every function below.

**No model judges any output.** Every metric is a string operation, a compiler verdict,
or arithmetic over those. There is no LLM-as-judge anywhere in this file, and there is no
place where one could be added without changing a signature.

**A quantity that was not measured is reported as NOT MEASURED, with a reason and with
its denominator stated.** It is never reported as zero, never omitted, and never
estimated. This is the rule that let the V0 pilot report verifier acceptance honestly
(`docs/evaluation/HML_EVAL_001_PILOT_REPORT.md` §5) and it is inherited unchanged.

Two commands, and the difference between them matters:

    python -m evaluation.v1.score_v1 --design
        Facts about the DESIGN. Chance floors, minimum detectable effect, denominators,
        expressibility coverage. Runnable with no data, because none of it is a result.

    python -m evaluation.v1.score_v1 --run <run_id>
        Facts about a RUN. Requires evaluation/results/runs/<run_id>.jsonl.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evaluation.analyse import (
    Interval,
    bootstrap_mean,
    cohens_h,
    effect_label,
    mcnemar_exact,
    paired_diff,
)
from evaluation.corpus.cso import CanonicalSemanticObject, check_answer

from . import V1_EVAL_VERSION
from .corpus import (
    ABLATION_LADDER,
    ADMITTED_CONCEPTS,
    ADVERSARIAL_PAIRS,
    ARMS_V1,
    CATEGORY_TARGETS_V1,
    build_all_v1,
    v1_facts,
)

REPO = Path(__file__).resolve().parents[2]
RUNS = REPO / "evaluation" / "results" / "runs"

__all__ = [
    "NotMeasured",
    "TRIAL_ROW_CONTRACT",
    "chance_floors",
    "minimum_detectable_discordance",
    "design_facts",
    "extract_minted_concepts",
    "classify_minted_concept",
    "concept_admission_metrics",
    "structural_preservation",
    "answer_accuracy",
    "block_accuracy",
    "transfer_metrics",
    "transformation_metrics",
    "epistemic_metrics",
    "verifier_acceptance",
    "cost_metrics",
    "ladder_contrasts",
    "score_run",
]


# ---------------------------------------------------------------------------
# The one honest answer for anything not measured
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NotMeasured:
    """A quantity that has no value yet, with its denominator and the reason.

    Serialises to a dict whose first key is ``NOT MEASURED`` so that a reader skimming
    JSON cannot mistake it for a number, and so that a downstream consumer that expects a
    float raises rather than silently averaging in a zero.
    """

    reason: str
    denominator: str = ""
    required_field: str = ""

    def to_dict(self) -> dict:
        return {
            "NOT MEASURED": True,
            "reason": self.reason,
            "denominator": self.denominator,
            "required_field": self.required_field,
        }


def _j(x: Any) -> Any:
    if isinstance(x, NotMeasured):
        return x.to_dict()
    if isinstance(x, Interval):
        return {"point": round(x.point, 4), "ci95": [round(x.lo, 4), round(x.hi, 4)],
                "n": x.n}
    if isinstance(x, dict):
        return {k: _j(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_j(v) for v in x]
    return x


#: The per-trial row this module consumes. Fields marked OPTIONAL are what a V1 harness
#: must add beyond `evaluation/harness.py::Trial`; every metric that needs one reports
#: NOT MEASURED with the field named when it is absent from every row.
TRIAL_ROW_CONTRACT = {
    "run_id": "str",
    "problem_id": "str — must be an id from evaluation.v1.corpus.build_all_v1()",
    "arm": f"str — one of {ARMS_V1}",
    "generation": "int",
    "raw_output": "str — the model's full reply, never modified",
    "answer_correct": "bool — RE-DERIVED here from raw_output, never trusted from the log",
    "encoding_text": "str — the fenced ```hml block, empty when none was produced",
    "parse_success": "bool | None",
    "prompt_tokens": "int",
    "completion_tokens": "int",
    "latency_s": "float",
    "repair_calls": "int",
    "minted_concepts": "OPTIONAL list[str] — names the arm minted; derived here when absent",
    "recorded_obligations": "OPTIONAL list[str] — L2 side conditions the encoding recorded",
    "open_goals": "OPTIONAL list[str] — L5 goals open at end of module",
    "proof_obligations": "OPTIONAL int — obligations the checker generated",
    "obligations_discharged": "OPTIONAL int — obligations a PROVER accepted",
    "verifier_invoked": "OPTIONAL bool — false everywhere until a prover exists",
}


# ---------------------------------------------------------------------------
# Design-time facts. None of this is a result; all of it is computable with no data.
# ---------------------------------------------------------------------------


def chance_floors() -> dict:
    """Per block: the accuracy a model reaches by guessing, two ways.

    The V0 pilot reported accuracies against no floor at all, which is defensible when
    every answer is a free-form number and indefensible here, where most items are
    multiple choice. Both floors are reported because they differ: uniform guessing over
    the options, and always answering that block's modal ground truth.
    """
    corpus = build_all_v1()
    out: dict[str, dict] = {}
    for block in CATEGORY_TARGETS_V1:
        items = [c for c in corpus if c.domain == block]
        # Numeric answers in this corpus are drawn from a stated finite range, which is
        # what makes a uniform floor meaningful for them too.
        sizes = []
        for c in items:
            if c.answer.kind == "choice":
                sizes.append(len(c.answer.options))
            elif c.answer.kind == "numeric":
                sizes.append(4)  # the question states the admissible range explicitly
            else:  # pragma: no cover - no other kind is used in this corpus
                sizes.append(0)
        counts = Counter(str(c.answer.value) for c in items)
        out[block] = {
            "n": len(items),
            "uniform_guess_floor": round(sum(1 / s for s in sizes) / len(sizes), 4),
            "modal_answer_floor": round(max(counts.values()) / len(items), 4),
            "answer_distribution": dict(sorted(counts.items())),
        }
    all_sizes = [
        len(c.answer.options) if c.answer.kind == "choice" else 4 for c in corpus
    ]
    out["ALL"] = {
        "n": len(corpus),
        "uniform_guess_floor": round(sum(1 / s for s in all_sizes) / len(all_sizes), 4),
        "modal_answer_floor": None,
        "NOTE": "a whole-corpus modal floor is meaningless because blocks use different "
                "answer spaces; use the per-block floors",
    }
    return out


def minimum_detectable_discordance(n_pairs: int, alpha: float = 0.05) -> dict:
    """The smallest one-directional discordant count McNemar can call significant.

    The V0 pilot's dominating limitation was that at n = 15 with a 93% ceiling this
    number corresponded to roughly a 33-percentage-point effect. It is computed here
    rather than asserted, so the improvement is checkable.
    """
    for k in range(1, n_pairs + 1):
        if mcnemar_exact(k, 0) <= alpha:
            return {
                "n_pairs": n_pairs,
                "alpha": alpha,
                "min_one_directional_discordant_pairs": k,
                "min_detectable_accuracy_difference_pp": round(100 * k / n_pairs, 2),
                "NOTE": "assumes every discordant pair falls the same way, which is the "
                        "most favourable case; a realistic design needs more",
            }
    return {"n_pairs": n_pairs, "alpha": alpha,
            "min_one_directional_discordant_pairs": None,
            "NOTE": "no discordant count reaches significance at this n"}


def design_facts() -> dict:
    """Everything about the corpus that is true before any model is run."""
    corpus = build_all_v1()
    facts = [v1_facts(c.id) for c in corpus]
    expressible = Counter(f.v0_expressible for f in facts)
    return {
        "corpus_version": V1_EVAL_VERSION,
        "problems": len(corpus),
        "blocks": dict(CATEGORY_TARGETS_V1),
        "arms": ARMS_V1,
        "ablation_ladder": [
            {"treatment": t, "control": c, "isolates": q} for t, c, q in ABLATION_LADDER
        ],
        "chance_floors": chance_floors(),
        "power": minimum_detectable_discordance(len(corpus)),
        "power_per_block": {
            b: minimum_detectable_discordance(n) for b, n in CATEGORY_TARGETS_V1.items()
        },
        "transfer_items": sorted(f.problem_id for f in facts if f.transfer_item),
        "admitted_concepts": [c.canonical_id for c in ADMITTED_CONCEPTS],
        "v0_expressibility": dict(expressible),
        "v0_expressibility_NOTE": (
            "'no' means V0 cannot state the problem's structure at all, so the V0 arm is "
            "answering from the prose alone. That is a property of V0, not a result: it "
            "is why encoding-fidelity comparison against V0 is undefined on most of this "
            "corpus, and it must be reported beside any V1-vs-V0 fidelity number."
        ),
        "diagnostic_layers": dict(Counter(f.diagnostic_for_layer for f in facts)),
        "adversarial_pairs": len(ADVERSARIAL_PAIRS),
        "calibration_status": "NOT YET RUN — no model has been run against this corpus; "
                              "the 50-60% accuracy target is a design intent, not a "
                              "measurement",
    }


# ---------------------------------------------------------------------------
# Deterministic extraction from a model's encoding
# ---------------------------------------------------------------------------

_CONCEPT_RE = re.compile(
    r"^\s*concept\s+([A-Za-z][A-Za-z0-9_]*)(.*?)^\s*end\s*$",
    re.M | re.S,
)
_MEMBER_RE = re.compile(
    r"^\s*(parameter|transform|invariant|property|example|counterexample)\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)",
    re.M,
)
_COMPRESSES_RE = re.compile(r"compresses?\s*[:=]\s*(.+)", re.I)


@dataclass
class MintedConcept:
    """One `concept ... end` block recovered from a model's encoding."""

    name: str
    members: dict[str, list[str]] = field(default_factory=dict)
    declares_compression: bool = False
    source: str = ""

    def has(self, kind: str) -> bool:
        return bool(self.members.get(kind))


def extract_minted_concepts(encoding_text: str) -> list[MintedConcept]:
    """Recover every concept declaration from an encoding.

    Uses the V0 compiler when the encoding parses, because that is the authoritative
    reading, and falls back to a regex when it does not. The fallback matters: 27–50% of
    V0 encodings did not parse in the pilot, and dropping the unparsed ones would measure
    minting behaviour only on the subset of trials where the model already wrote valid
    syntax. Deterministic either way; no model is consulted.
    """
    if not (encoding_text or "").strip():
        return []
    try:
        from hamiltonian_lang import compile_source
        from hamiltonian_lang.ast.nodes import ConceptDecl

        result = compile_source(encoding_text, "<v1-trial>")
        decls = [s for s in result.module.statements if isinstance(s, ConceptDecl)]
        if decls:
            out = []
            for d in decls:
                members: dict[str, list[str]] = defaultdict(list)
                for m in d.members:
                    members[m.kind].append(m.name)
                out.append(MintedConcept(
                    name=d.name,
                    members=dict(members),
                    declares_compression=bool(_COMPRESSES_RE.search(encoding_text)),
                    source="parser",
                ))
            return out
    except Exception:  # pragma: no cover - a broken encoding must not break scoring
        pass

    out = []
    for m in _CONCEPT_RE.finditer(encoding_text):
        name, body = m.group(1), m.group(2)
        members: dict[str, list[str]] = defaultdict(list)
        for mm in _MEMBER_RE.finditer(body):
            members[mm.group(1)].append(mm.group(2))
        out.append(MintedConcept(
            name=name,
            members=dict(members),
            declares_compression=bool(_COMPRESSES_RE.search(body)),
            source="regex",
        ))
    return out


def _normalise_name(name: str) -> str:
    """Case- and separator-insensitive key. `Location_Scale` == `locationscale`."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


_ADMITTED_KEYS = {_normalise_name(c.canonical_id): c.canonical_id
                  for c in ADMITTED_CONCEPTS}

#: Names that are one-to-one renamings of an existing primitive rather than an
#: abbreviation of a recurring structure. A concept minted under any of these compresses
#: nothing by construction. The list is explicit rather than inferred: inferring
#: synonymy would require judgement, and judgement is what this file excludes.
_PRIMITIVE_SYNONYMS = {
    "averagevalue", "average", "mean", "expectation", "expectedvalue",
    "spread", "dispersion", "variance", "standarddeviation", "sd",
    "probability", "chance", "likelihoodvalue",
    "number", "quantity", "value", "amount",
    "distribution", "law", "density", "function", "map",
}

ADMISSION_VERDICTS = (
    "valid_admission",
    "duplicate_of_admitted",
    "synonym_no_compression",
    "no_testable_consequence",
    "unlicensed_novelty",
)


def classify_minted_concept(mc: MintedConcept, licensed: tuple[str, ...]) -> str:
    """One deterministic verdict per minted concept.

    The rules are exactly the mechanically checkable subset of
    `spec/concept_schema.yaml` and `spec/concept_registry.schema.json`:

    * no invariant and no example -> ``no_testable_consequence`` (V0's HML-S603 rule)
    * name matches an admitted concept -> ``duplicate_of_admitted``
    * name is a listed one-to-one renaming of a primitive -> ``synonym_no_compression``
    * name is neither admitted nor licensed for this problem -> ``unlicensed_novelty``
    * otherwise -> ``valid_admission``

    **What this does NOT detect**, stated here so the metric is not over-read:
    duplication at the level of the *formal definition* rather than the *name*. Two
    concepts with different names and identical definitions are the case the minting
    protocol most needs to catch, and catching it requires the registry's structural
    matcher (`hamiltonian_lang.v1.registry`). Until that module exists, definition-level
    duplication is NOT MEASURED and this function only bounds it from below.
    """
    key = _normalise_name(mc.name)
    if not mc.has("invariant") and not mc.has("example"):
        return "no_testable_consequence"
    if key in _ADMITTED_KEYS:
        return "duplicate_of_admitted"
    if key in _PRIMITIVE_SYNONYMS:
        return "synonym_no_compression"
    if key not in {_normalise_name(x) for x in licensed}:
        return "unlicensed_novelty"
    return "valid_admission"


# ---------------------------------------------------------------------------
# V1 structural preservation
# ---------------------------------------------------------------------------

_STEP_RE = re.compile(r"\b(step|derive)\b", re.I)
_OBLIGATION_HINTS = {
    "divide": ("!= 0", "nonzero", "non-zero"),
    "cancel": ("!= 0", "nonzero", "non-zero"),
    "square_both_sides": ("weaken", "not reversible", "irreversible"),
    "sqrt_both_sides": (">= 0", "branch", "case"),
    "differentiate": ("differentiable",),
    "integrate": ("integrable",),
    "limit": ("exists", "uniform"),
    "apply": ("domain",),
    "rearrange": ("isolable", "isolate"),
}
_EPISTEMIC_CONSTRUCTORS = (
    "proved", "by_definition", "assumed", "almost_sure", "with_high_probability",
    "likely", "possible", "consistent_with", "insufficient_evidence_against",
    "model_conditional", "hypothesis_test", "fail_to_reject", "reject",
)
_PROHIBITED_PHRASES = {
    "proved": (r"\bprove\b", r"\bproved\b", r"\bproof\b"),
    "disproved": (r"\bdisprove", r"\brefut"),
    "definitionally_true": (r"\bby_definition\b",),
    "estimated": (r"\bestimated\b",),
    "reject": (r"\breject\b",),
    "almost_sure": (r"\balmost_sure\b",),
}


def structural_preservation(cso: CanonicalSemanticObject, encoding_text: str) -> dict:
    """Per-facet: does the encoding record the structure the problem is about?

    This is **not** comparable to the V0 pilot's ``semantic_encoding_score`` and must
    never be reported beside it as though it were. That score compares an encoding
    against ``SemanticFacts`` — entities, types, roles, laws — and 59 of the 60 problems
    here carry no such facts, because the structures this corpus is about (a concept, a
    derivation chain, an epistemic status) have no ``SemanticFacts`` slot. The V0 fidelity
    comparison is therefore **NOT DEFINED** on this corpus except on the single problem
    that carries laws, and this function is a different, V1-specific measure with its own
    denominator.
    """
    facts = v1_facts(cso.id)
    text = encoding_text or ""
    facets: dict[str, tuple[int, int]] = {}

    if facts.block == "transformation_chain":
        n_steps = len(re.findall(r"^\s*step \d+:", cso.prose, re.M))
        found = len(_STEP_RE.findall(text))
        facets["steps_recorded"] = (min(found, n_steps), n_steps)
        if facts.first_invalid_step:
            op = _obligation_op_for(cso.id)
            hints = _OBLIGATION_HINTS.get(op, ())
            hit = any(h.lower() in text.lower() for h in hints) if hints else False
            facets["faulty_step_obligation_recorded"] = (int(hit), 1)

    if facts.block == "epistemic_calibration":
        want = facts.epistemic_status or ""
        facets["required_status_present"] = (int(want in text), 1)
        bad = 0
        for status in facts.prohibited_statuses:
            for pat in _PROHIBITED_PHRASES.get(status, ()):
                if re.search(pat, text, re.I):
                    bad = 1
                    break
        facets["no_prohibited_status_used"] = (1 - bad, 1)
        facets["any_epistemic_constructor"] = (
            int(any(c in text for c in _EPISTEMIC_CONSTRUCTORS)), 1
        )

    if facts.block == "family_derivation" and facts.family_member:
        member = facts.family_member.lower()
        facets["correct_member_named"] = (int(member in text.lower()), 1)

    if facts.block in ("concept_recognition", "recurring_structure"):
        cited = [c.canonical_id for c in ADMITTED_CONCEPTS if c.canonical_id in text]
        minted = [m.name for m in extract_minted_concepts(text)]
        licensed = {_normalise_name(x) for x in facts.licensed_concepts}
        named = {_normalise_name(x) for x in cited + minted}
        facets["licensed_concept_named"] = (
            int(bool(licensed & named)) if licensed else 0, 1 if licensed else 0
        )

    scored = {k: v for k, v in facets.items() if v[1] > 0}
    if not scored:
        return {"score": None,
                "NOT MEASURED": "no facet of this problem is checkable in this encoding",
                "facets": {}}
    total_hit = sum(a for a, _ in scored.values())
    total_max = sum(b for _, b in scored.values())
    return {"score": round(total_hit / total_max, 4),
            "facets": {k: list(v) for k, v in scored.items()}}


def _obligation_op_for(problem_id: str) -> str:
    """Which L2 operation the item's faulty step uses. Table-driven, not inferred."""
    return {
        "tc01_divide_by_possibly_zero": "divide",
        "tc02_cancel_vanishing_factor": "cancel",
        "tc03_square_treated_as_equivalence": "square_both_sides",
        "tc04_differentiate_at_a_corner": "differentiate",
        "tc06_log_of_possibly_nonpositive": "apply",
        "tc07_limit_sum_exchange": "limit",
        "tc09_sqrt_drops_a_branch": "sqrt_both_sides",
        "tc10_rearrange_not_isolable": "rearrange",
        "tc11_integrate_over_a_singularity": "integrate",
    }.get(problem_id, "")


# ---------------------------------------------------------------------------
# Metrics over a run
# ---------------------------------------------------------------------------


def _corpus_index() -> dict[str, CanonicalSemanticObject]:
    return {c.id: c for c in build_all_v1()}


def rescore(rows: list[dict]) -> list[dict]:
    """Re-derive answer correctness from ``raw_output`` using the checker in this
    repository, exactly as ``evaluation/analyse.py::rescore`` does.

    ``EVAL-DEFECT-001`` in the V0 pilot was a stored verdict that a later checker fix
    never reached. Re-deriving every verdict at analysis time is the fix for that class
    of defect, and it is applied here from the start. Raw model output is never modified.
    """
    corpus = _corpus_index()
    for r in rows:
        cso = corpus.get(r.get("problem_id", ""))
        if cso is None:
            r["_UNKNOWN_PROBLEM"] = True
            continue
        correct, extracted = check_answer(cso.answer, r.get("raw_output") or "")
        if correct != r.get("answer_correct"):
            r["_answer_rescored_from"] = r.get("answer_correct")
        r["answer_correct"] = correct
        r["extracted_answer"] = extracted
    return rows


def _rows_for(rows: list[dict], arm: str) -> list[dict]:
    return [r for r in rows if r.get("arm") == arm]


def _paired(rows: list[dict], a: str, b: str, field_name: str, subset: set[str] | None = None):
    idx = {(r["problem_id"], r["arm"], r.get("generation", 0)): r for r in rows}
    keys = sorted(
        {(p, g) for (p, arm, g) in idx if arm == a}
        & {(p, g) for (p, arm, g) in idx if arm == b}
    )
    va, vb, ids = [], [], []
    for p, g in keys:
        if subset is not None and p not in subset:
            continue
        ra, rb = idx[(p, a, g)], idx[(p, b, g)]
        if ra.get(field_name) is None or rb.get(field_name) is None:
            continue
        va.append(float(ra[field_name]))
        vb.append(float(rb[field_name]))
        ids.append((p, g))
    return va, vb, ids


def answer_accuracy(rows: list[dict]) -> dict:
    """Metric 1 — mathematical-answer accuracy, per arm, with bootstrap intervals."""
    out: dict[str, Any] = {}
    for arm in ARMS_V1:
        rs = _rows_for(rows, arm)
        if not rs:
            out[arm] = NotMeasured("no trials completed for this arm", "trials in arm")
            continue
        out[arm] = {
            "trials": len(rs),
            "accuracy": bootstrap_mean([1.0 if r["answer_correct"] else 0.0 for r in rs]),
            "empty_output_rate": round(
                sum(1 for r in rs if not (r.get("raw_output") or "").strip()) / len(rs), 4
            ),
        }
    return out


def block_accuracy(rows: list[dict]) -> dict:
    """Per block, per arm. The blocks measure different layers and must not be pooled."""
    corpus = _corpus_index()
    out: dict[str, dict] = {}
    for block in CATEGORY_TARGETS_V1:
        row = {}
        for arm in ARMS_V1:
            rs = [r for r in _rows_for(rows, arm)
                  if corpus.get(r["problem_id"]) and corpus[r["problem_id"]].domain == block]
            row[arm] = (round(sum(1 for r in rs if r["answer_correct"]) / len(rs), 4)
                        if rs else NotMeasured("no trials", f"{block} x {arm}"))
        row["n_per_arm"] = {
            arm: sum(1 for r in _rows_for(rows, arm)
                     if corpus.get(r["problem_id"])
                     and corpus[r["problem_id"]].domain == block)
            for arm in ARMS_V1
        }
        row["chance_floors"] = chance_floors()[block]
        out[block] = row
    return out


def concept_admission_metrics(rows: list[dict]) -> dict:
    """Metrics 3, 4 and 5 — valid admission, duplicate rejection, false novelty.

    Denominators, stated so a rate cannot be read against the wrong one:

    * valid concept admission = valid_admission / all concepts minted
    * false novelty           = (unlicensed_novelty + synonym_no_compression +
                                 no_testable_consequence) / all concepts minted
    * duplicate rejection     = adversarial duplicate cases the checker rejected /
                                adversarial duplicate cases presented

    The third of these needs a V1 registry to reject anything, so it is NOT MEASURED
    until `hamiltonian_lang.v1.registry` exists. The first two are computed from the
    model's own output and need no V1 module at all.
    """
    minted_total = 0
    verdicts: Counter[str] = Counter()
    per_arm: dict[str, Counter[str]] = {a: Counter() for a in ARMS_V1}
    per_arm_total: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)

    for r in rows:
        arm = r.get("arm", "")
        facts = v1_facts(r["problem_id"]) if r.get("problem_id") in _corpus_index() else None
        licensed = facts.licensed_concepts if facts else ()
        names = r.get("minted_concepts")
        mcs = (
            [MintedConcept(name=n, members={"invariant": ["?"]}, source="log") for n in names]
            if isinstance(names, list) and names
            else extract_minted_concepts(r.get("encoding_text") or "")
        )
        for mc in mcs:
            v = classify_minted_concept(mc, licensed)
            minted_total += 1
            verdicts[v] += 1
            per_arm[arm][v] += 1
            per_arm_total[arm] += 1
            if len(examples[v]) < 10:
                examples[v].append(f"{r['problem_id']}/{arm}: {mc.name}")

    if minted_total == 0:
        no_mint = NotMeasured(
            "no arm minted any concept in this run, so admission rates have an empty "
            "denominator. This is itself a finding: an arm given a minting protocol that "
            "never mints has not exercised the layer",
            "concepts minted across all trials",
            "encoding_text / minted_concepts",
        )
        valid_rate: Any = no_mint
        false_novelty: Any = no_mint
    else:
        bad = (verdicts["unlicensed_novelty"] + verdicts["synonym_no_compression"]
               + verdicts["no_testable_consequence"])
        valid_rate = round(verdicts["valid_admission"] / minted_total, 4)
        false_novelty = round(bad / minted_total, 4)

    return {
        "concepts_minted": minted_total,
        "valid_concept_admission_rate": valid_rate,
        "false_novelty_rate": false_novelty,
        "verdict_counts": dict(verdicts),
        "per_arm": {a: dict(c) for a, c in per_arm.items()},
        "per_arm_minted": dict(per_arm_total),
        "examples": dict(examples),
        "duplicate_concept_rejection_rate": NotMeasured(
            "requires a checker that can reject a duplicate; "
            "hamiltonian_lang.v1.registry does not exist yet. "
            "tests/v1/test_adversarial_v1.py carries the cases and xfails on them",
            f"{sum(1 for p in ADVERSARIAL_PAIRS if p.layer == 'concept_minting')} "
            f"adversarial duplicate/synonym cases",
            "hamiltonian_lang.v1.registry:ConceptRegistry.admit",
        ),
        "DEFINITION_LEVEL_DUPLICATION": NotMeasured(
            "classify_minted_concept matches NAMES, not formal definitions. Two concepts "
            "with different names and the same definition are counted as valid here and "
            "are exactly what the minting protocol must catch. The reported "
            "false_novelty_rate is therefore a LOWER BOUND",
            "concepts minted across all trials",
            "hamiltonian_lang.v1.registry structural matcher",
        ),
    }


def transfer_metrics(rows: list[dict]) -> dict:
    """Metric 10 — transfer to related concepts absent from the supplied registry.

    Reported as an interaction, never as a single accuracy: the question is whether the
    minting arms' advantage (if any) survives on items whose answer the registry does not
    name. An arm that is better only on registry items has learnt a lookup, not a concept.
    """
    corpus = _corpus_index()
    transfer = {c.id for c in corpus.values() if v1_facts(c.id).transfer_item}
    recognition = {c.id for c in corpus.values() if c.domain == "concept_recognition"}
    non_transfer = recognition - transfer

    def _acc(arm: str, subset: set[str]) -> Any:
        rs = [r for r in _rows_for(rows, arm) if r["problem_id"] in subset]
        if not rs:
            return NotMeasured("no trials", f"{len(subset)} items x {arm}")
        return round(sum(1 for r in rs if r["answer_correct"]) / len(rs), 4)

    per_arm = {
        arm: {"transfer": _acc(arm, transfer),
              "non_transfer": _acc(arm, non_transfer)}
        for arm in ARMS_V1
    }
    inter = {}
    for treat, ctrl, _q in ABLATION_LADDER:
        ta, tb, _ = _paired(rows, treat, ctrl, "answer_correct", subset=transfer)
        na, nb, _ = _paired(rows, treat, ctrl, "answer_correct", subset=non_transfer)
        if not ta or not na:
            inter[f"{treat}-{ctrl}"] = NotMeasured(
                "no paired cell in both arms on one of the two subsets",
                f"{len(transfer)} transfer / {len(non_transfer)} non-transfer items")
            continue
        d_t = paired_diff(ta, tb)
        d_n = paired_diff(na, nb)
        inter[f"{treat}-{ctrl}"] = {
            "transfer_difference": d_t,
            "non_transfer_difference": d_n,
            "interaction_point": round(d_t.point - d_n.point, 4),
            "READ_AS": "a positive non-transfer difference with a zero transfer "
                       "difference is a registry lookup, not a concept advantage",
        }
    return {
        "transfer_items": sorted(transfer),
        "non_transfer_recognition_items": sorted(non_transfer),
        "per_arm": per_arm,
        "interaction": inter,
    }


def transformation_metrics(rows: list[dict]) -> dict:
    """Metric 7 — transformation correctness.

    Two things, kept apart: identifying the faulty step (an answer, measured now) and
    recording the obligation that step generates (an encoding property, measured only
    when the encoding is present).
    """
    corpus = _corpus_index()
    block = {c.id for c in corpus.values() if c.domain == "transformation_chain"}
    valid_chains = {p for p in block if v1_facts(p).first_invalid_step == 0}
    out: dict[str, Any] = {"n_items": len(block), "n_valid_chains": len(valid_chains)}
    for arm in ARMS_V1:
        rs = [r for r in _rows_for(rows, arm) if r["problem_id"] in block]
        if not rs:
            out[arm] = NotMeasured("no trials", f"{len(block)} chain items x {arm}")
            continue
        faulted = [r for r in rs if r["problem_id"] not in valid_chains]
        clean = [r for r in rs if r["problem_id"] in valid_chains]
        obl = [structural_preservation(corpus[r["problem_id"]], r.get("encoding_text") or "")
               for r in faulted]
        obl_hits = [
            f["facets"]["faulty_step_obligation_recorded"][0]
            for f in obl if "faulty_step_obligation_recorded" in f.get("facets", {})
        ]
        out[arm] = {
            "first_invalid_step_exact": round(
                sum(1 for r in rs if r["answer_correct"]) / len(rs), 4),
            "recall_on_faulted_chains": (
                round(sum(1 for r in faulted if r["answer_correct"]) / len(faulted), 4)
                if faulted else None),
            "specificity_on_valid_chains": (
                round(sum(1 for r in clean if r["answer_correct"]) / len(clean), 4)
                if clean else None),
            "obligation_recorded_rate": (
                round(sum(obl_hits) / len(obl_hits), 4) if obl_hits
                else NotMeasured("no encoding carried a recognisable obligation",
                                 f"{len(faulted)} faulted chains", "encoding_text")),
        }
    out["READ_AS"] = (
        "specificity_on_valid_chains is the guard against a 'always report a fault' "
        "strategy: three of twelve chains are wholly valid and answering 0 is the only "
        "way to score them"
    )
    return out


def epistemic_metrics(rows: list[dict]) -> dict:
    """Metric 8 — epistemic-calibration accuracy, plus the conflation rate.

    The second number is the one the layer exists for. An arm can pick the right option
    and still write ``prove`` over an ``Evidence`` claim in its encoding; the conflation
    rate counts that directly, from the encoding, with no model in the loop.
    """
    corpus = _corpus_index()
    block = {c.id for c in corpus.values() if c.domain == "epistemic_calibration"}
    negatives = {
        p for p in block
        if v1_facts(p).epistemic_status in ("fail_to_reject", "unsupported")
    }
    out: dict[str, Any] = {
        "n_items": len(block),
        "n_items_whose_correct_answer_is_that_evidence_is_insufficient": len(negatives),
        "insufficient_evidence_items": sorted(negatives),
    }
    for arm in ARMS_V1:
        rs = [r for r in _rows_for(rows, arm) if r["problem_id"] in block]
        if not rs:
            out[arm] = NotMeasured("no trials", f"{len(block)} epistemic items x {arm}")
            continue
        neg = [r for r in rs if r["problem_id"] in negatives]
        conflations = 0
        checked = 0
        for r in rs:
            enc = r.get("encoding_text") or ""
            if not enc.strip():
                continue
            checked += 1
            sp = structural_preservation(corpus[r["problem_id"]], enc)
            if sp.get("facets", {}).get("no_prohibited_status_used", [1, 1])[0] == 0:
                conflations += 1
        out[arm] = {
            "accuracy": round(sum(1 for r in rs if r["answer_correct"]) / len(rs), 4),
            "accuracy_on_insufficient_evidence_items": (
                round(sum(1 for r in neg if r["answer_correct"]) / len(neg), 4)
                if neg else None),
            "prohibited_status_in_encoding_rate": (
                round(conflations / checked, 4) if checked
                else NotMeasured("no arm produced an encoding for these items",
                                 f"{len(rs)} trials", "encoding_text")),
            "encodings_checked": checked,
        }
    out["READ_AS"] = (
        "accuracy_on_insufficient_evidence_items is the headline for L4. These are the "
        "items where 'H0 is true', 'there is no effect' and 'H0 is proved' are all wrong "
        "and 'insufficient evidence against H0' is right, which is the single "
        "prohibition V1 exists to enforce"
    )
    return out


def verifier_acceptance(rows: list[dict]) -> Any:
    """Metric 9 — verifier acceptance.

    The V0 pilot reported this as NOT MEASURED because no prover was ever invoked, and
    nothing in V1 changes that. It stays NOT MEASURED until a real prover accepts or
    rejects a real obligation. Reporting a parser's verdict here instead would be the
    single most misleading number this apparatus could produce.
    """
    invoked = [r for r in rows if r.get("verifier_invoked")]
    if not invoked:
        return NotMeasured(
            "no theorem prover was invoked in any trial, exactly as in the V0 pilot "
            "(HML_EVAL_001_PILOT_REPORT §5). Parser acceptance is NOT verifier acceptance "
            "and is reported separately",
            "obligations discharged / obligations generated",
            "verifier_invoked, proof_obligations, obligations_discharged",
        )
    gen = sum(r.get("proof_obligations", 0) for r in invoked)
    dis = sum(r.get("obligations_discharged", 0) for r in invoked)
    return {"trials_with_verifier": len(invoked), "obligations_generated": gen,
            "obligations_discharged": dis,
            "acceptance_rate": round(dis / gen, 4) if gen else None}


def semantic_preservation(rows: list[dict]) -> dict:
    """Metric 2 — semantic preservation, in the two senses that are not the same thing."""
    corpus = _corpus_index()
    with_facts = [c for c in corpus.values() if c.semantics.entities]
    out: dict[str, Any] = {
        "v0_style_encoding_fidelity": NotMeasured(
            f"only {len(with_facts)} of {len(corpus)} problems carry SemanticFacts, "
            f"because this corpus is deliberately about structures V0's SemanticFacts "
            f"has no slot for. The V0 pilot's 0.648 encoding score is therefore NOT "
            f"comparable to anything in this run and must not be placed beside it",
            f"{len(with_facts)} of {len(corpus)} problems",
            "SemanticFacts on the CSO",
        ),
        "problems_with_v0_semantic_facts": [c.id for c in with_facts],
    }
    for arm in ARMS_V1:
        rs = [r for r in _rows_for(rows, arm) if (r.get("encoding_text") or "").strip()]
        if not rs:
            out[arm] = NotMeasured("no encoding produced in this arm",
                                   "trials producing an encoding", "encoding_text")
            continue
        scores = []
        for r in rs:
            sp = structural_preservation(corpus[r["problem_id"]], r["encoding_text"])
            if sp.get("score") is not None:
                scores.append(sp["score"])
        out[arm] = {
            "encodings_produced": len(rs),
            "v1_structural_preservation": (
                bootstrap_mean(scores) if scores
                else NotMeasured("no facet checkable in any encoding",
                                 f"{len(rs)} encodings", "encoding_text")),
            "parse_success_rate": (
                round(sum(1 for r in rs if r.get("parse_success")) / len(rs), 4)
                if any(r.get("parse_success") is not None for r in rs)
                else NotMeasured("no trial recorded parse_success",
                                 f"{len(rs)} encodings", "parse_success")),
        }
    out["PARSE_RATE_GATE"] = (
        "docs/design/V1_EXPERIMENT_PLAN.md §1 forbids reporting any V0-vs-V1 comparison "
        "until the V1 parse rate reaches 90%. Check that gate before reading any "
        "contrast in this document."
    )
    return out


def cost_metrics(rows: list[dict]) -> dict:
    """Metrics 11 and 12 — token and latency cost, per arm and paired along the ladder."""
    out: dict[str, Any] = {}
    for arm in ARMS_V1:
        rs = _rows_for(rows, arm)
        if not rs:
            out[arm] = NotMeasured("no trials", f"trials in {arm}")
            continue
        out[arm] = {
            "trials": len(rs),
            "mean_prompt_tokens": round(
                sum(r.get("prompt_tokens", 0) for r in rs) / len(rs), 1),
            "mean_completion_tokens": round(
                sum(r.get("completion_tokens", 0) for r in rs) / len(rs), 1),
            "mean_latency_s": round(sum(r.get("latency_s", 0.0) for r in rs) / len(rs), 1),
            "total_repair_calls": sum(r.get("repair_calls", 0) for r in rs),
        }
    paired_cost = {}
    for treat, ctrl, _q in ABLATION_LADDER:
        for fname in ("completion_tokens", "latency_s"):
            va, vb, _ = _paired(rows, treat, ctrl, fname)
            paired_cost[f"{treat}-{ctrl}:{fname}"] = (
                paired_diff(va, vb) if va
                else NotMeasured("no paired cell", "problem-generation cells in both arms")
            )
    out["paired"] = paired_cost
    return out


def ladder_contrasts(rows: list[dict]) -> list[dict]:
    """Paired answer-accuracy contrasts along the ablation ladder.

    Same three commitments as ``evaluation/analyse.py``: paired over cells present in
    BOTH arms, unrun reported as unrun, and the discordant-pair counts shown beside every
    difference. The V0 pilot's decisive finding was six contrasts with **zero** discordant
    pairs — a fact invisible in the accuracy column and unmissable in this one.
    """
    out = []
    for treat, ctrl, question in ABLATION_LADDER:
        va, vb, ids = _paired(rows, treat, ctrl, "answer_correct")
        if not va:
            out.append({"treatment": treat, "control": ctrl, "question": question,
                        "n_pairs": 0,
                        "status": "NOT ESTIMABLE — no problem-generation cell completed "
                                  "in both arms"})
            continue
        b = sum(1 for t, c in zip(va, vb, strict=True) if t > c)
        c_ = sum(1 for t, c in zip(va, vb, strict=True) if t < c)
        d = paired_diff(va, vb)
        p1, p2 = sum(va) / len(va), sum(vb) / len(vb)
        h = cohens_h(p1, p2)
        out.append({
            "treatment": treat, "control": ctrl, "question": question,
            "n_pairs": len(va),
            "treatment_accuracy": round(p1, 4),
            "control_accuracy": round(p2, 4),
            "paired_difference": d,
            "discordant_pairs": {"treatment_only_correct": b, "control_only_correct": c_},
            "mcnemar_exact_p": round(mcnemar_exact(b, c_), 4),
            "cohens_h": round(h, 4),
            "effect_size": effect_label(h),
            "ci_excludes_zero": (d.lo > 0) or (d.hi < 0),
        })
    return out


def coverage(rows: list[dict], meta: dict) -> dict:
    corpus = _corpus_index()
    gens = meta.get("generations", 1)
    planned = len(corpus) * len(ARMS_V1) * gens
    have = {(r["problem_id"], r["arm"], r.get("generation", 0)) for r in rows}
    complete = [
        (p, g) for p in corpus for g in range(gens)
        if all((p, a, g) in have for a in ARMS_V1)
    ]
    return {
        "planned_calls": planned,
        "completed_calls": len(rows),
        "UNRUN_CELLS": planned - len(rows),
        "completion_fraction": round(len(rows) / planned, 4) if planned else None,
        "trials_per_arm": {a: sum(1 for r in rows if r.get("arm") == a) for a in ARMS_V1},
        "fully_covered_problem_generations": len(complete),
        "unknown_problem_ids": sorted(
            {r["problem_id"] for r in rows if r["problem_id"] not in corpus}
        ),
    }


def score_run(rows: list[dict], meta: dict | None = None) -> dict:
    """The complete deterministic scorecard for one run."""
    meta = meta or {}
    rows = rescore(rows)
    return {
        "HEADER": {
            "WHAT_THIS_IS": "Deterministic scoring for the V1 concept-kernel ablation.",
            "SCORING": "No model judged any output at any point. Every number here is a "
                       "string operation, a compiler verdict, or arithmetic over those.",
            "NOT_MEASURED": "Any object with a 'NOT MEASURED' key has no value yet. It "
                            "is not zero and must not be averaged, plotted or compared.",
            "PARSER_ACCEPTANCE_WARNING": "Parse success is NOT evidence of a language "
                                         "advantage. A V1 program can parse cleanly and "
                                         "misrepresent the problem entirely.",
            "CEILING_WARNING": "Read every accuracy against the per-block chance floor "
                               "in `design.chance_floors`, not against zero.",
            "corpus_version": V1_EVAL_VERSION,
        },
        "design": design_facts(),
        "coverage": coverage(rows, meta),
        "answer_accuracy": answer_accuracy(rows),
        "block_accuracy": block_accuracy(rows),
        "semantic_preservation": semantic_preservation(rows),
        "concept_admission": concept_admission_metrics(rows),
        "transfer": transfer_metrics(rows),
        "transformation": transformation_metrics(rows),
        "epistemic": epistemic_metrics(rows),
        "verifier_acceptance": verifier_acceptance(rows),
        "cost": cost_metrics(rows),
        "ladder_contrasts": ladder_contrasts(rows),
    }


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", default=None, help="run id under evaluation/results/runs/")
    ap.add_argument("--design", action="store_true",
                    help="print design-time facts only; needs no data")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if args.design or not args.run:
        doc = {"design": design_facts(), "trial_row_contract": TRIAL_ROW_CONTRACT}
        text = json.dumps(_j(doc), indent=2, default=str)
        if args.out:
            Path(args.out).write_text(text + "\n")
        print(text)
        return 0

    path = RUNS / f"{args.run}.jsonl"
    if not path.exists():
        raise SystemExit(
            f"no such run: {path}\n"
            f"Nothing has been run against this corpus. Use --design for the facts that "
            f"exist without data."
        )
    rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    meta_path = RUNS / f"{args.run}.meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    doc = score_run(rows, meta)
    out_path = Path(args.out) if args.out else RUNS / f"{args.run}.v1_analysis.json"
    out_path.write_text(json.dumps(_j(doc), indent=2, default=str) + "\n")

    cov = doc["coverage"]
    print("=" * 78)
    print(f"HML-V1 concept ablation — run {args.run}")
    print("=" * 78)
    print(f"completed {cov['completed_calls']} / {cov['planned_calls']}   "
          f"UNRUN: {cov['UNRUN_CELLS']}")
    for arm in ARMS_V1:
        a = doc["answer_accuracy"][arm]
        if isinstance(a, NotMeasured):
            print(f"{arm:11s} NOT MEASURED — {a.reason}")
            continue
        print(f"{arm:11s} n={a['trials']:4d}  accuracy {a['accuracy'].render()}")
    print("\nLADDER CONTRASTS (paired, cells present in both arms)")
    for c in doc["ladder_contrasts"]:
        if c.get("status"):
            print(f"  {c['treatment']:10s} vs {c['control']:10s}  {c['status']}")
            continue
        d = c["paired_difference"]
        star = " *" if c["ci_excludes_zero"] else "  "
        print(f"  {c['treatment']:10s} vs {c['control']:10s} n={c['n_pairs']:3d} "
              f"diff={d.point:+.3f} CI[{d.lo:+.3f},{d.hi:+.3f}]{star} "
              f"McNemar p={c['mcnemar_exact_p']:.3f}  discordant "
              f"{c['discordant_pairs']['treatment_only_correct']}/"
              f"{c['discordant_pairs']['control_only_correct']}")
    print(f"\nwritten: {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
