"""Per-trial scorer for the syntax tournament.

Eight facets per trial: first-attempt parse, repaired parse, semantic preservation,
empty/truncated output, visible output length, reasoning-inclusive completion tokens,
latency, and a failure category.

The rule this module exists to enforce
--------------------------------------
The HML-EVAL-001 pilot shipped a scorer that returned ``0.0`` when nothing was
checkable, and it silently zeroed 25 problems: the dimensional items declared no
entities, so every encoding of them scored zero regardless of quality. The fix is not
"be careful". It is a type distinction, applied everywhere:

* **0.0 means measured and failed.** The ground truth carried facets and the output
  preserved none of them.
* **``NotMeasured`` means there was nothing to measure.** No facets in the ground truth,
  no front end for this candidate, a transport failure, or a control arm that emits no
  encoding at all. ``NotMeasured`` serialises to a dict whose first key is
  ``NOT MEASURED``, so a downstream consumer that expects a float raises rather than
  averaging in a zero.

``mutations.py`` carries a synthetic passing case and a synthetic failing case for every
facet below, and the tests assert both. A facet that has never been observed failing is
not known to work.

The other rule
--------------
**An empty visible answer is a model failure.** It is scored as a failed parse and a
failed answer, and it is never retried. Only a *transport* failure may be retried, and
the harness preserves the original request and every response. Retrying on content would
bias the sample toward outputs the caller likes, which is the same defect as scoring on
model judgement.

A parse rate must count parses
------------------------------
``first_attempt_parse`` used to be ``ParseOutcome.ok``, which is the verdict of the
*whole* compiler. Measured on this compiler, ``HML-T426`` (wrong arity), ``HML-T415``
(wrong role label) and ``HML-T403`` (declared-type mismatch) parse cleanly and resolve
cleanly, failing only in the type checker; an unknown identifier parses cleanly and
fails in resolution. Every one of them was being counted as a parse failure. The effect
is not neutral: it *understates* first-attempt parse rate — ACQ0's single most important
number — and attributes the compiler's type checking to the candidate surface, so a
syntax that the model writes perfectly could be rejected for mathematics the model got
wrong.

``first_attempt_parse`` is now ``stages.parse_status is PASS``. The old quantity is kept
under its true name, ``first_attempt_compiled``, because "did this compile" is also a
real question; the fix is to ask each question by its own name.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import lru_cache
from typing import Any

from evaluation.corpus.cso import check_answer
from evaluation.semantic_equiv import compare_semantics
from evaluation.v1.score_v1 import NotMeasured

from .candidates import (
    CANDIDATES,
    SE_CONTROL,
    ParseOutcome,
    SyntaxAdapter,
    TerminalOutcome,
    classify_stages,
    extract_fenced,
)
from .tasks import GateTask

__all__ = [
    "FACETS",
    "STAGE_FACETS",
    "FAILURE_CATEGORIES",
    "TrialInput",
    "ScoredTrial",
    "score_trial",
    "score_many",
]

#: Every facet this scorer measures. ``mutations.MUTATIONS`` must cover all of them, and
#: a test asserts the two sets are equal -- so adding a facet without a failing mutation
#: breaks the build rather than shipping unverified.
FACETS: tuple[str, ...] = (
    "first_attempt_parse",
    "repaired_parse",
    "semantic_preservation",
    "empty_or_truncated",
    "visible_output_length",
    "completion_tokens_reasoning_inclusive",
    "latency_s",
    "failure_category",
)

#: Facets derived from the per-stage record. Listed separately from ``FACETS`` because
#: they are not independently mutated -- each is a projection of ``terminal_outcome``,
#: and ``test_syntax_gate_scorer`` asserts the projection directly rather than through a
#: mutation that could only restate it.
STAGE_FACETS: tuple[str, ...] = (
    "first_attempt_compiled",
    "terminal_outcome",
    "repair_terminal_outcome",
)

FAILURE_CATEGORIES: tuple[str, ...] = (
    "ok",
    "empty_visible_answer",       # model failure. never retried.
    "truncated_output",           # finish_reason == length
    "no_encoding_block",          # produced prose but no fenced encoding
    "syntax_failure",             # HML-L*, HML-P*
    "type_failure",               # HML-T*, HML-D*
    "semantic_failure",           # HML-N*, HML-S*
    "parse_failure_other",
    "semantic_mistranslation",    # parsed cleanly, preserved less than the threshold
    "front_end_unavailable",      # NOT a model failure. excluded from every rate.
    "transport_failure",          # NOT a model failure. excluded from every rate.
    "control_arm_no_encoding",    # SE control. excluded from every parse rate.
)

#: Diagnostic-code prefixes, following the taxonomy in ``evaluation/semantic_equiv.py``.
_SYNTAX_PREFIXES = ("HML-L", "HML-P", "EMPTY", "CRASH")
_TYPE_PREFIXES = ("HML-T", "HML-D")
_SEMANTIC_PREFIXES = ("HML-N", "HML-S")

#: The preservation level at or above which a parsed encoding counts as preserved. Fixed
#: here, before any result is seen, because the Gate 2 threshold is >= 90% of trials
#: preserved and a movable per-trial bar would make the gate negotiable.
PRESERVATION_THRESHOLD = 1.0


@dataclass
class TrialInput:
    """One raw generation, plus at most one repair. The harness writes these."""

    trial_id: str
    run_id: str
    task_id: str
    condition: str
    curriculum_size: int
    seed: int | None = None
    content: str = ""
    reasoning: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    finish_reason: str = ""
    #: Transport-level failure. Distinct from an empty completion, which is a model
    #: failure. Never None-and-empty at the same time by accident: the harness sets one.
    error: str | None = None
    #: The single permitted repair attempt, if the harness ran one.
    repair_attempted: bool = False
    repair_content: str = ""
    repair_completion_tokens: int = 0
    repair_latency_s: float = 0.0
    repair_finish_reason: str = ""
    #: Every attempt made, including transport failures, preserved verbatim.
    attempts: list[dict] = field(default_factory=list)


@dataclass
class ScoredTrial:
    trial_id: str
    run_id: str
    task_id: str
    domain: str
    condition: str
    curriculum_size: int
    #: **Did the text parse.** Not "did it compile" -- see the module docstring.
    first_attempt_parse: bool | NotMeasured
    repaired_parse: bool | NotMeasured
    semantic_preservation: float | NotMeasured
    preserved: bool | NotMeasured
    empty_or_truncated: bool
    visible_output_length: int
    completion_tokens_reasoning_inclusive: int
    first_attempt_completion_tokens: int
    latency_s: float
    failure_category: str
    answer_correct: bool | NotMeasured
    #: Did the whole pipeline accept the first attempt. The quantity
    #: ``first_attempt_parse`` used to hold, under the name it actually means.
    first_attempt_compiled: bool | NotMeasured = False
    #: Where the first attempt stopped, as a ``TerminalOutcome`` value, or ``""`` when
    #: nothing classified it.
    terminal_outcome: str = ""
    #: The same for the repaired attempt; ``""`` when no repair was scored.
    repair_terminal_outcome: str = ""
    #: Whether the **exact expected canonical object** was recovered: hash equality over
    #: the nameless canonical form. Stricter than ``preserved``, which scores the facets
    #: the answer key happens to declare. ACQ0's semantic-preservation rate is defined on
    #: this field.
    exact_canonical_match: bool | NotMeasured = False
    diagnostics: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def j(x: Any) -> Any:
            return x.to_dict() if isinstance(x, NotMeasured) else x

        return {k: j(v) for k, v in asdict(self).items()}


def _category_from_diagnostics(codes: list[str]) -> str:
    for c in codes:
        if c.startswith(_SYNTAX_PREFIXES):
            return "syntax_failure"
    for c in codes:
        if c.startswith(_TYPE_PREFIXES):
            return "type_failure"
    for c in codes:
        if c.startswith(_SEMANTIC_PREFIXES):
            return "semantic_failure"
    return "parse_failure_other"


@lru_cache(maxsize=512)
def _reference_canonical_hash(reference_hml: str) -> str | None:
    """The alpha-invariant content hash of a task's reference object, or ``None``.

    ``None`` when the reference itself does not compile — a fact about the corpus, not
    about any model output, so it makes the exact-object comparison unavailable rather
    than failed.
    """
    if not (reference_hml or "").strip():
        return None
    stages = classify_stages(reference_hml, file="syntax_gate#reference")
    return stages.canonical_hash


def _exact_canonical_match(
    task: GateTask, outcome: ParseOutcome | None
) -> bool | NotMeasured:
    """Did this attempt recover the **exact expected canonical object**?

    Hash equality over the nameless canonical form, which is the strictest available
    notion of "the same object" and the one ACQ0's preservation rate is defined on. It
    is deliberately stricter than the facet comparator: the comparator scores how many
    declared facets survived, and a candidate can score 1.0 on the declared facets while
    differing in something the answer key never listed.
    """
    reference = _reference_canonical_hash(task.cso.reference_hml)
    if reference is None:
        return NotMeasured(
            reason=(
                f"task {task.id!r} has no compilable reference encoding, so there is no "
                "canonical object to recover; the corpus, not the model, is what is "
                "missing here"
            ),
            denominator="0 reference objects",
            required_field="GateTask.cso.reference_hml",
        )
    if outcome is None or outcome.stages is None:
        return NotMeasured(
            reason="no per-stage record, so no canonical hash was computed",
            denominator="0 classified attempts",
            required_field="ParseOutcome.stages.canonical_hash",
        )
    if outcome.stages.canonical_hash is None:
        # It did not compile, so it has no canonical identity. That is a measured
        # failure to recover the object, not an absent measurement.
        return False
    return outcome.stages.canonical_hash == reference


def _parse_facet(outcome: ParseOutcome, condition: str) -> bool | NotMeasured:
    """The parse verdict, or an explicit absence. **Never** ``ParseOutcome.ok``.

    A front end that reports no ``stages`` has not observed whether the text parsed.
    Returning ``ok`` in that case would substitute a compile verdict for a parse verdict,
    which is precisely the defect; returning ``False`` would invent a parse failure
    nobody measured. Both are refused, and the row is excluded with the reason recorded.
    """
    if outcome.stages is None:
        return NotMeasured(
            reason=(
                f"the front end for {condition} reported no per-stage record, so no "
                "parse verdict exists; CompileResult.ok() is a whole-pipeline verdict "
                "and must not be substituted for one"
            ),
            denominator="0 classified attempts",
            required_field="ParseOutcome.stages",
        )
    if outcome.stages.terminal is TerminalOutcome.INCONCLUSIVE:
        return NotMeasured(
            reason=f"the parse stage produced no verdict: {outcome.stages.detail}",
            denominator="0 classified attempts",
            required_field="ParseOutcome.stages.parse_status",
        )
    return outcome.stages.parsed


def _preservation(
    task: GateTask, hml_l1: str | None
) -> tuple[float | NotMeasured, list[str]]:
    """The distinction the pilot got wrong, made explicit.

    Returns ``NotMeasured`` only when the *ground truth* offers nothing to compare
    against. When the ground truth carries facets and the model produced no usable
    encoding, that is a measured 0.0 -- a real failure, not an absent measurement.
    """
    notes: list[str] = []
    if not task.scored_facets:
        return (
            NotMeasured(
                reason="the answer key populates no comparable semantic facet",
                denominator="0 facets",
                required_field="GateTask.scored_facets",
            ),
            notes,
        )
    if not hml_l1:
        notes.append(
            "ground truth carries "
            f"{len(task.scored_facets)} facets and no encoding was recovered: measured 0.0"
        )
        return 0.0, notes
    cmp = compare_semantics(task.cso, hml_l1)
    score = cmp.score()
    if score is None:
        # The ground truth said there were facets and the comparator found no
        # denominator. That is a disagreement between the corpus and the comparator, not
        # a model result, and it must never be averaged in as a zero.
        return (
            NotMeasured(
                reason=(
                    "comparator found no checkable facet although the answer key "
                    f"declares {sorted(task.scored_facets)}; corpus and comparator "
                    "disagree and the trial is excluded rather than scored"
                ),
                denominator="0 facets",
                required_field="SemanticComparison.score()",
            ),
            notes + cmp.notes[:4],
        )
    return score, notes + cmp.notes[:4]


def score_trial(
    trial: TrialInput,
    task: GateTask,
    adapter: SyntaxAdapter | None,
) -> ScoredTrial:
    """Score one trial. Never calls a model; never raises on malformed input."""
    notes: list[str] = []
    visible = (trial.content or "").strip()
    visible_len = len(trial.content or "")
    total_tokens = trial.completion_tokens + (
        trial.repair_completion_tokens if trial.repair_attempted else 0
    )
    total_latency = round(
        trial.latency_s + (trial.repair_latency_s if trial.repair_attempted else 0.0), 4
    )
    truncated = trial.finish_reason == "length"

    def base(**kw: Any) -> ScoredTrial:
        defaults: dict[str, Any] = dict(
            trial_id=trial.trial_id,
            run_id=trial.run_id,
            task_id=trial.task_id,
            domain=task.domain,
            condition=trial.condition,
            curriculum_size=trial.curriculum_size,
            first_attempt_parse=False,
            repaired_parse=False,
            semantic_preservation=0.0,
            preserved=False,
            empty_or_truncated=(not visible) or truncated,
            visible_output_length=visible_len,
            completion_tokens_reasoning_inclusive=total_tokens,
            first_attempt_completion_tokens=trial.completion_tokens,
            latency_s=total_latency,
            failure_category="ok",
            answer_correct=False,
            first_attempt_compiled=False,
            terminal_outcome="",
            repair_terminal_outcome="",
            exact_canonical_match=False,
            diagnostics=[],
            notes=notes,
        )
        defaults.update(kw)
        return ScoredTrial(**defaults)

    # 1. Transport failure. Not a model failure; excluded from every rate.
    if trial.error:
        nm = NotMeasured(
            reason=f"transport failure: {trial.error}",
            denominator="0 completed calls",
            required_field="TrialInput.content",
        )
        notes.append("transport failure preserved in TrialInput.attempts; not retried here")
        return base(
            first_attempt_parse=nm, repaired_parse=nm, semantic_preservation=nm,
            preserved=nm, answer_correct=nm, failure_category="transport_failure",
            empty_or_truncated=False, visible_output_length=0,
            first_attempt_compiled=nm,
            terminal_outcome=TerminalOutcome.INCONCLUSIVE.value,
            exact_canonical_match=nm,
        )

    # 2. Empty visible answer. A MODEL FAILURE, scored as such and never retried.
    if not visible:
        pres, pnotes = _preservation(task, None)
        notes.extend(pnotes)
        notes.append(
            "empty visible answer scored as a model failure per the harness contract; "
            "the reasoning channel may have consumed the whole budget, which is a "
            "property of the model under this representation, not a transport fault"
        )
        return base(
            first_attempt_parse=False, repaired_parse=False,
            semantic_preservation=pres,
            preserved=(pres if isinstance(pres, NotMeasured) else False),
            answer_correct=False, failure_category="empty_visible_answer",
            empty_or_truncated=True,
            first_attempt_compiled=False,
            terminal_outcome=TerminalOutcome.PARSE_FAILED.value,
        )

    correct, _ = check_answer(task.cso.answer, trial.content)

    # 3. The structured-English control emits no formal encoding. Giving it a parse rate
    #    of 0 would make the control look catastrophic at the one thing it is not doing.
    if trial.condition == SE_CONTROL:
        nm = NotMeasured(
            reason="the structured-English control emits no formal encoding by design",
            denominator="0 encodings",
            required_field="condition != SE_structured_english",
        )
        return base(
            first_attempt_parse=nm, repaired_parse=nm, semantic_preservation=nm,
            preserved=nm, answer_correct=correct,
            failure_category="truncated_output" if truncated else "control_arm_no_encoding",
            first_attempt_compiled=nm,
            terminal_outcome=TerminalOutcome.UNSUPPORTED.value,
            exact_canonical_match=nm,
        )

    # 4. No front end for this candidate yet. Absence of a measurement is not a failed
    #    measurement, and must never be reported as a parse rate of zero.
    if adapter is None:
        nm = NotMeasured(
            reason=(
                f"no front end for {trial.condition}; required from "
                "evaluation.syntax_acquisition (Phase F3)"
            ),
            denominator="0 parseable candidates",
            required_field="candidates.resolve_adapters()",
        )
        return base(
            first_attempt_parse=nm, repaired_parse=nm, semantic_preservation=nm,
            preserved=nm, answer_correct=correct,
            failure_category="front_end_unavailable",
            first_attempt_compiled=nm,
            terminal_outcome=TerminalOutcome.UNSUPPORTED.value,
            exact_canonical_match=nm,
        )

    tags = CANDIDATES[trial.condition].fence_tags
    encoding = extract_fenced(trial.content, tags)
    if encoding is None:
        pres, pnotes = _preservation(task, None)
        notes.extend(pnotes)
        return base(
            first_attempt_parse=False, repaired_parse=False,
            semantic_preservation=pres,
            preserved=(pres if isinstance(pres, NotMeasured) else False),
            answer_correct=correct,
            failure_category="truncated_output" if truncated else "no_encoding_block",
            diagnostics=["NO_FENCED_BLOCK"],
            first_attempt_compiled=False,
            terminal_outcome=TerminalOutcome.PARSE_FAILED.value,
        )

    first = adapter.parse(encoding)
    diagnostics = list(first.diagnostics)
    repaired_compiled = first.ok
    final_hml = first.hml_l1
    #: The attempt the semantic comparison is made against: the repair when one was
    #: scored, otherwise the first attempt.
    final_outcome: ParseOutcome | None = first

    # The parse verdict comes from the stage record, never from ``ok``. A front end that
    # reports no stages has not measured a parse, and NOT MEASURED is not zero.
    first_parsed = _parse_facet(first, trial.condition)
    repair_parsed = first_parsed
    first_terminal = first.terminal
    repair_terminal: TerminalOutcome | None = None

    if not first.ok and trial.repair_attempted:
        repair_encoding = extract_fenced(trial.repair_content or "", tags)
        if repair_encoding is None:
            notes.append("repair produced no fenced block")
            repair_parsed = False
            repair_terminal = TerminalOutcome.PARSE_FAILED
        else:
            second = adapter.parse(repair_encoding)
            diagnostics += [f"repair:{c}" for c in second.diagnostics]
            repaired_compiled = second.ok
            repair_parsed = _parse_facet(second, trial.condition)
            repair_terminal = second.terminal
            if second.hml_l1 is not None:
                final_hml = second.hml_l1
                final_outcome = second
            elif second.ok:
                final_outcome = second
    elif not first.ok:
        notes.append("no repair attempted; repaired_parse equals first_attempt_parse")

    pres, pnotes = _preservation(task, final_hml if repaired_compiled else None)
    notes.extend(pnotes)
    preserved: bool | NotMeasured = (
        pres if isinstance(pres, NotMeasured) else pres >= PRESERVATION_THRESHOLD
    )

    if not repaired_compiled:
        category = _category_from_diagnostics(diagnostics)
    elif truncated:
        category = "truncated_output"
    elif preserved is True:
        category = "ok"
    elif isinstance(preserved, NotMeasured):
        category = "ok"
    else:
        category = "semantic_mistranslation"

    return base(
        first_attempt_parse=first_parsed,
        repaired_parse=repair_parsed,
        semantic_preservation=pres,
        preserved=preserved,
        answer_correct=correct,
        failure_category=category,
        diagnostics=diagnostics[:12],
        first_attempt_compiled=first.ok,
        terminal_outcome=first_terminal.value if first_terminal else "",
        repair_terminal_outcome=repair_terminal.value if repair_terminal else "",
        exact_canonical_match=_exact_canonical_match(task, final_outcome),
    )


def score_many(
    trials: list[TrialInput],
    tasks: dict[str, GateTask],
    adapters: dict[str, SyntaxAdapter | None],
    *,
    workers: int | None = None,
) -> list[ScoredTrial]:
    """Score a batch. CPU-bound, so this is where the 18 cores pay.

    ``workers`` defaults to ``harness.SCORING_WORKERS``. Parsing and comparing are pure
    functions of their inputs, so the order of the output is the order of the input
    regardless of how the work was distributed.
    """
    from concurrent.futures import ThreadPoolExecutor

    from .harness import SCORING_WORKERS

    n = workers or SCORING_WORKERS
    if n <= 1 or len(trials) < 4:
        return [
            score_trial(t, tasks[t.task_id], adapters.get(t.condition)) for t in trials
        ]
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(
            pool.map(
                lambda t: score_trial(t, tasks[t.task_id], adapters.get(t.condition)),
                trials,
            )
        )
