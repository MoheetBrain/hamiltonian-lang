"""Deterministic scoring, and the H2/H3 attribution that keeps two claims apart.

No model judges anything here. Every field is a string comparison, a compiler verdict, or
arithmetic over those.

Two claims, and why conflating them is the failure mode
-------------------------------------------------------
This benchmark can produce two quite different wins, and reporting one as the other is the
single most likely way its result gets misread:

* **H2 — representation as workspace.** The model reasons *in* HML and reaches a better
  answer. Evidence for the representation.
* **H3 — verifier-guided repair.** The model reasons, gets compiler diagnostics, and fixes
  its answer. Evidence for the *loop*, not for the notation. A pipeline that showed the
  model any well-formedness checker might do as well.

Attribution is therefore made per trial, on a rule fixed before any run:

    an HML-V1 trial is H3 if and only if the repair call CHANGED the final answer;
    otherwise it is H2.

The rule keys on *whether the repair moved the answer*, not on whether the answer ended up
correct, so it is not outcome-dependent post-hoc labelling. An SE trial is always H2: the
SE arm has no verifier, so no SE trial can be H3.

Verified completion is not accuracy
-----------------------------------
:attr:`TrialResult.verified_completion` records whether the emitted module compiled — that
every name resolved and every type checked. It is defined **only in the HML arm**, because
the SE arm emits no artefact a verifier could check. It is therefore reported as a rate
with its own denominator and **never** as an uplift over SE: dividing by an arm that
cannot have the property would manufacture a 100-point improvement out of a definition.
SE's field carries :class:`NotMeasured` with that reason attached, so a consumer expecting
a float raises rather than averaging in a zero.

Error taxonomy
--------------
Following ``evaluation/semantic_equiv.py``:

* **structural** — ``HML-L*`` (lex) and ``HML-P*`` (parse), plus the case where no fenced
  module was emitted at all. The output is not well-formed Hamiltonian Lang.
* **semantic** — ``HML-N*``/``HML-S*`` (resolution, scope) and ``HML-T*``/``HML-D*`` (type,
  dimension). The output is well-formed and still wrong: an unresolved name, a wrong
  arity, a probability where a positive real belongs.

The split matters because the two say different things about the surface syntax. A corpus
of structural errors indicts the grammar; a corpus of semantic errors indicts the model's
grasp of the mathematics, which is what the benchmark is trying to measure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evaluation.corpus.cso import CanonicalSemanticObject, check_answer
from evaluation.v1.score_v1 import NotMeasured
from evaluation.v1_benchmark.arms import Arm
from evaluation.v1_benchmark.sequential import PairCounts

from hamiltonian_lang.improvement.state import Hypothesis

__all__ = [
    "TrialResult",
    "CompileVerdict",
    "classify_diagnostics",
    "score_answer",
    "pair_counts",
    "Aggregate",
    "aggregate",
    "SE_VERIFIED_COMPLETION_NOT_APPLICABLE",
]

_STRUCTURAL_PREFIXES = ("HML-L", "HML-P")
_SEMANTIC_PREFIXES = ("HML-N", "HML-S", "HML-T", "HML-D")

#: Why the SE arm has no verified-completion figure. Carried in every SE row.
SE_VERIFIED_COMPLETION_NOT_APPLICABLE = NotMeasured(
    reason=(
        "not applicable: the SE arm emits prose, not an artefact a compiler can check. "
        "Reporting this as False would create a spurious 100-point HML advantage out of a "
        "definitional asymmetry rather than a measurement."
    ),
    denominator="SE trials (0 checkable artefacts)",
    required_field="verified_completion",
)


@dataclass(frozen=True)
class CompileVerdict:
    """One compile of one emitted module."""

    emitted: bool
    ok: bool
    codes: tuple[str, ...]
    rendered: str

    @property
    def structural_errors(self) -> int:
        if not self.emitted:
            # No fenced module at all is the most structural failure available.
            return 1
        return sum(1 for c in self.codes if c.startswith(_STRUCTURAL_PREFIXES))

    @property
    def semantic_errors(self) -> int:
        if not self.emitted:
            return 0
        return sum(1 for c in self.codes if c.startswith(_SEMANTIC_PREFIXES))

    def to_dict(self) -> dict[str, Any]:
        return {
            "emitted": self.emitted,
            "compiled": self.ok,
            "codes": list(self.codes),
            "structural_errors": self.structural_errors,
            "semantic_errors": self.semantic_errors,
        }


def classify_diagnostics(source: str) -> CompileVerdict:
    """Compile an extracted module and classify what came back.

    An empty source is *not* compiled: it is recorded as ``emitted=False``. Compiling the
    empty string would return a clean parse of an empty module, which would score a model
    that emitted no formalisation at all as having produced a verified one.
    """
    if not source.strip():
        return CompileVerdict(
            emitted=False,
            ok=False,
            codes=(),
            rendered="no fenced hml module was emitted",
        )
    from hamiltonian_lang import compile_source

    result = compile_source(source)
    bag = result.diagnostics
    codes = tuple(bag.codes())
    return CompileVerdict(
        emitted=True,
        ok=bool(result.ok()),
        codes=codes,
        rendered=bag.render(),
    )


def score_answer(cso: CanonicalSemanticObject, raw: str) -> tuple[bool, str]:
    """Deterministic answer check. Delegates to the frozen ``check_answer``."""
    return check_answer(cso.answer, raw)


@dataclass
class TrialResult:
    """One task, one arm, both calls. Every field is measured or explicitly not."""

    task_id: str
    domain: str
    arm: Arm
    hypothesis: Hypothesis

    #: Correctness of the FINAL answer, after the second call.
    answer_correct: bool
    #: Correctness after the first call only. The H3 contrast is built from this.
    first_attempt_correct: bool
    #: Did the second call change the extracted answer?
    second_call_changed_answer: bool

    #: HML arm only; NotMeasured in the SE arm. See the module docstring.
    verified_completion: bool | NotMeasured
    structural_errors: int | NotMeasured
    semantic_errors: int | NotMeasured

    prompt_tokens: int
    completion_tokens: int
    latency_s: float

    normalised_answer: str = ""
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.hypothesis is Hypothesis.EXCLUDED:
            raise ValueError(
                f"{self.task_id}/{self.arm} was tagged EXCLUDED. EXCLUDED is for "
                "engineering work and is never routed into a scientific aggregate; a "
                "benchmark trial that reaches scoring is not engineering work."
            )
        if self.arm is Arm.SE and self.hypothesis is Hypothesis.H3:
            raise ValueError(
                "an SE trial was tagged H3. The SE arm has no verifier, so no SE trial can "
                "be evidence about verifier-guided repair."
            )

    @property
    def repair_attributable(self) -> bool:
        return self.hypothesis is Hypothesis.H3

    def to_dict(self) -> dict[str, Any]:
        def _v(x: Any) -> Any:
            return x.to_dict() if isinstance(x, NotMeasured) else x

        return {
            "task_id": self.task_id,
            "domain": self.domain,
            "arm": str(self.arm),
            "hypothesis": str(self.hypothesis),
            "hypothesis_claim": self.hypothesis.claim,
            "hypothesis_excluded_claim": self.hypothesis.excluded_claim,
            "answer_correct": self.answer_correct,
            "first_attempt_correct": self.first_attempt_correct,
            "second_call_changed_answer": self.second_call_changed_answer,
            "verified_completion": _v(self.verified_completion),
            "structural_errors": _v(self.structural_errors),
            "semantic_errors": _v(self.semantic_errors),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "latency_s": round(self.latency_s, 4),
            "normalised_answer": self.normalised_answer,
            "errors": list(self.errors),
        }


def _index(rows: list[TrialResult], arm: Arm) -> dict[str, TrialResult]:
    out: dict[str, TrialResult] = {}
    for r in rows:
        if r.arm is arm:
            if r.task_id in out:
                raise ValueError(f"two {arm} rows for {r.task_id}; pairing would be ambiguous")
            out[r.task_id] = r
    return out


def pair_counts(rows: list[TrialResult], *, h2_only: bool = False) -> PairCounts:
    """Build the paired table. Every task must appear in both arms or the pair is dropped.

    With ``h2_only`` the table is restricted to tasks whose HML trial the repair did not
    move, which is the contrast that speaks to the representation rather than to the loop.
    Restricting changes the denominator, so the restricted table's ``n`` is smaller and is
    reported as such rather than being compared against the full table's rates.
    """
    se = _index(rows, Arm.SE)
    hml = _index(rows, Arm.HML_V1)
    shared = sorted(set(se) & set(hml))

    w = losses = both = neither = 0
    for tid in shared:
        h, s = hml[tid], se[tid]
        if h2_only and h.hypothesis is Hypothesis.H3:
            continue
        if h.answer_correct and not s.answer_correct:
            w += 1
        elif s.answer_correct and not h.answer_correct:
            losses += 1
        elif h.answer_correct and s.answer_correct:
            both += 1
        else:
            neither += 1
    return PairCounts(w=w, losses=losses, both=both, neither=neither)


@dataclass(frozen=True)
class Aggregate:
    """Everything the report needs, with the two claims kept apart."""

    overall: PairCounts
    h2_restricted: PairCounts
    #: HML trials the repair moved, and how many of those ended correct.
    repair_moved: int
    repair_moved_to_correct: int
    repair_moved_to_incorrect: int
    #: HML arm only. Numerator and denominator both stated.
    verified_completions: int
    verified_denominator: int
    structural_errors: int
    semantic_errors: int
    tokens: dict[str, dict[str, int]]
    latency_s: dict[str, float]

    @property
    def verified_completion_rate(self) -> float | None:
        if not self.verified_denominator:
            return None
        return round(self.verified_completions / self.verified_denominator, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer_accuracy": {
                "note": (
                    "The paired answer-accuracy contrast. This is the H2/H3 headline and is "
                    "reported separately from verified completion below, which is a "
                    "different claim measured on a different denominator."
                ),
                "overall": self.overall.to_dict(),
                "h2_restricted": {
                    "note": (
                        "Tasks whose HML trial the repair did not move. The contrast that "
                        "speaks to the representation rather than to the verifier loop. Its "
                        "n is smaller than the overall n and its rates are not comparable "
                        "with the overall rates."
                    ),
                    **self.h2_restricted.to_dict(),
                },
            },
            "h3_repair": {
                "note": (
                    "Trials the repair call moved. A win here is verifier-guided repair and "
                    "is NOT evidence about the representation."
                ),
                "moved": self.repair_moved,
                "moved_to_correct": self.repair_moved_to_correct,
                "moved_to_incorrect": self.repair_moved_to_incorrect,
            },
            "verified_completion": {
                "note": (
                    "HML arm only. The SE arm emits no checkable artefact, so no uplift "
                    "ratio against SE is computed or computable. This is not answer "
                    "accuracy and must never be reported as it."
                ),
                "verified": self.verified_completions,
                "denominator": self.verified_denominator,
                "rate": self.verified_completion_rate,
                "se_comparison": SE_VERIFIED_COMPLETION_NOT_APPLICABLE.to_dict(),
            },
            "errors": {
                "structural": self.structural_errors,
                "semantic": self.semantic_errors,
                "taxonomy": {
                    "structural": "HML-L* (lex), HML-P* (parse), or no module emitted",
                    "semantic": "HML-N*/HML-S* (resolution, scope), HML-T*/HML-D* (type, dimension)",
                },
            },
            "tokens": self.tokens,
            "latency_s": self.latency_s,
        }


def aggregate(rows: list[TrialResult]) -> Aggregate:
    hml = [r for r in rows if r.arm is Arm.HML_V1]
    moved = [r for r in hml if r.second_call_changed_answer]

    tokens: dict[str, dict[str, int]] = {}
    latency: dict[str, float] = {}
    for arm in (Arm.SE, Arm.HML_V1):
        rs = [r for r in rows if r.arm is arm]
        tokens[str(arm)] = {
            "prompt_tokens": sum(r.prompt_tokens for r in rs),
            "completion_tokens": sum(r.completion_tokens for r in rs),
        }
        latency[str(arm)] = round(sum(r.latency_s for r in rs), 3)

    return Aggregate(
        overall=pair_counts(rows),
        h2_restricted=pair_counts(rows, h2_only=True),
        repair_moved=len(moved),
        repair_moved_to_correct=sum(1 for r in moved if r.answer_correct),
        repair_moved_to_incorrect=sum(1 for r in moved if not r.answer_correct),
        verified_completions=sum(1 for r in hml if r.verified_completion is True),
        verified_denominator=len(hml),
        structural_errors=sum(
            r.structural_errors for r in hml if isinstance(r.structural_errors, int)
        ),
        semantic_errors=sum(
            r.semantic_errors for r in hml if isinstance(r.semantic_errors, int)
        ),
        tokens=tokens,
        latency_s=latency,
    )
