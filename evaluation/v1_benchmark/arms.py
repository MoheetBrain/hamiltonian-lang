"""The two arms, and the matching that makes their comparison mean anything.

    Arm SE       problem -> structured-English reasoning -> self-review -> final answer
    Arm HML-V1   problem -> unrestricted reasoning -> HML formalisation
                         -> compile and verify -> one repair -> final answer

Why arm SE gets a second call
-----------------------------
The Lead's sketch gives HML-V1 a repair step and gives SE nothing corresponding. Run that
way, an HML win has a completely mundane alternative explanation — *it had two attempts
and the control had one* — and no amount of statistical machinery afterwards can separate
that from a representation effect. So SE gets a second call too: an unaided self-review
with the same token allowance, carrying no signal from outside the model.

The two arms then differ in exactly one respect, which is the treatment: HML-V1's second
call carries **compiler diagnostics**, and SE's does not. That residual difference is the
independent variable, and a win attributable to it is :data:`Hypothesis.H3` —
verifier-guided reasoning — not a win for the representation. See
:mod:`evaluation.v1_benchmark.scoring`, which performs that attribution per task rather
than leaving it to the write-up.

The budget, inherited rather than invented
------------------------------------------
:data:`TOTAL_COMPLETION_BUDGET` is 2048, taken from the ACQ0 context budget
(``docs/evaluation/ACQ0_CONTEXT_BUDGET.md``), which fixes the same figure for a one-stage
and a two-stage protocol alike so that neither wins by being allowed to emit more. The
same rule applies here: **2048 completion tokens per task per arm, across all calls**, so
each arm's two calls get 1024. Reusing ACQ0's figure also keeps the two studies runnable
under one server configuration at ``4 x 8192``.

The oracle guard
----------------
:func:`assert_no_oracle` runs on **every** prompt this module builds, in both arms, with
no exemption and with the hypothesis fixed to H2. ACQ0's scoped exemption supplies targets
for *translation* tasks; it is refused here, both by the upstream guard (which raises for
any non-ACQ0 hypothesis) and by :func:`_refuse_exemption` below, so the refusal survives
someone changing one of the two.

One limitation of the upstream guard is worth stating rather than discovering later: it
skips gold answers shorter than two characters, so the four tasks whose answer is a single
digit are not protected by substring scanning. They are protected structurally instead —
no prompt builder in this module takes ``answer.value`` as an input, only
``answer.render_instruction()``, and
``test_prompt_construction_is_independent_of_the_answer_key`` proves it by rebuilding every
prompt against a mutated key and comparing bytes.

``reference_hml`` is empty on every task in this corpus, so the guard's reference-encoding
check has nothing to find. That is correct: producing a formalisation is the HML arm's
work, so there is no authored encoding to leak.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from evaluation.acq0.protocols.oracle import Hypothesis as OracleHypothesis
from evaluation.acq0.protocols.oracle import (
    OracleExemption,
    assert_no_oracle,
)
from evaluation.corpus.cso import (
    ANSWER_CLOSE,
    ANSWER_OPEN,
    CanonicalSemanticObject,
)
from evaluation.corpus.renderers import HML_SPEC, SCHEMA_A_PRIME

__all__ = [
    "Arm",
    "ArmPrompt",
    "TOTAL_COMPLETION_BUDGET",
    "CALLS_PER_ARM",
    "PER_CALL_BUDGET",
    "TEMPERATURE",
    "MODEL",
    "MODEL_DIGEST",
    "RUNTIME",
    "HML_BLOCK_OPEN",
    "HML_BLOCK_CLOSE",
    "MATCHING",
    "MatchedDimension",
    "ExemptionRefused",
    "se_initial_prompt",
    "se_review_prompt",
    "hml_initial_prompt",
    "hml_repair_prompt",
    "extract_hml",
    "strip_answer_block",
]


class Arm(StrEnum):
    SE = "SE"
    HML_V1 = "HML-V1"


#: Frozen model identity. Both arms, every call, no exception.
MODEL = "gemma4:31b"
MODEL_DIGEST = "6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7"
TEMPERATURE = 0.0
RUNTIME = "4 x 8192"

#: Completion tokens per task per arm, across every call that arm makes. From ACQ0.
TOTAL_COMPLETION_BUDGET = 2048
CALLS_PER_ARM = 2
PER_CALL_BUDGET = TOTAL_COMPLETION_BUDGET // CALLS_PER_ARM

#: The fence the HML arm must wrap its formalisation in, so extraction is deterministic.
HML_BLOCK_OPEN = "```hml"
HML_BLOCK_CLOSE = "```"


class ExemptionRefused(AssertionError):
    """An ACQ0 oracle exemption was offered to a V1-benchmark prompt builder."""


def _refuse_exemption(exemption: OracleExemption | None, where: str) -> None:
    """Second lock on the ACQ0 exemption, independent of the upstream guard.

    The upstream :func:`assert_no_oracle` already raises for a non-ACQ0 hypothesis. This
    refuses one call earlier and for a different reason, so that neither lock alone is
    load-bearing: an edit that relaxed the upstream check would still hit this one.
    """
    if exemption is not None:
        raise ExemptionRefused(
            f"an ACQ0 oracle exemption was offered to {where}. That exemption is scoped to "
            "ACQ0 *translation* prompts, which are handed the canonical target and asked "
            "only to encode it. Every task in this benchmark asks the model to DERIVE an "
            "answer, so disclosing any part of the key does not weaken the test, it "
            "deletes it."
        )


@dataclass(frozen=True)
class ArmPrompt:
    arm: Arm
    stage: str
    system: str
    user: str
    completion_budget: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": str(self.arm),
            "stage": self.stage,
            "completion_budget": self.completion_budget,
            "system_chars": len(self.system),
            "user_chars": len(self.user),
        }


# ---------------------------------------------------------------------------
# Shared content. Identical bytes in both arms, by construction.
# ---------------------------------------------------------------------------

_BASE_SYSTEM = (
    "You are solving a mathematics problem. Be precise. Do not restate the problem. "
    "Your reply must end with the final answer wrapped in "
    f"{ANSWER_OPEN} and {ANSWER_CLOSE} markers, and nothing after the closing marker."
)


def _problem_block(cso: CanonicalSemanticObject) -> str:
    """Prose and question, verbatim. Byte-identical in both arms."""
    return f"PROBLEM\n{cso.prose}"


def _answer_block(cso: CanonicalSemanticObject) -> str:
    """The answer contract.

    Built from ``render_instruction()``, which describes the answer's *shape*. It never
    touches ``answer.value``, which is the key.
    """
    return (
        f"QUESTION\n{cso.question}\n\n"
        f"Give your final answer as {cso.answer.render_instruction()}\n"
        f"The answer must appear exactly once, wrapped in {ANSWER_OPEN} ... {ANSWER_CLOSE}."
    )


#: Stands in for a segment that is excluded from the leak scan. Two kinds of segment are
#: excluded, and both are excluded for the same reason, stated in :func:`_guard`.
_CARRIED_PLACEHOLDER = "<<SEGMENT EXCLUDED FROM THE LEAK SCAN>>"


def _guard(prompt: str, cso: CanonicalSemanticObject, where: str) -> None:
    """Mandatory in both arms. Fixed to H2, never exempt.

    **The scanning rule: every task-dependent segment is scanned; task-independent
    constants and model-produced text are replaced by :data:`_CARRIED_PLACEHOLDER` first.**

    This is the upstream module's own argument applied one level out. ``permitted_text``
    excuses content that every arm receives, on the ground that content carried by
    everything cannot discriminate. The same holds for content carried by every *task*:

    * **Task-independent constants** — the structured-English schema and the Hamiltonian
      Lang specification. They are byte-identical in all 24 prompts, so they cannot encode
      anything about any one task's key. They must nonetheless be excluded, because the
      language specification legitimately contains ``forall x : Real . ...`` as a worked
      example of quantifier syntax, and a task whose variable is named ``x`` and typed
      ``Real`` produces the semantic-fact rendering ``x : Real``. That collision is a false
      positive of a deliberately blunt heuristic — the upstream module notes that a
      name/type *pairing* cannot arrive from the prose by accident, which is true, but it
      can arrive from a grammar reference. ``test_excluded_segments_are_task_independent``
      is what licenses the exclusion: it asserts these segments really are identical across
      every task, so nothing task-specific can hide inside one.
    * **Model-produced text** — the working carried into a second call, and the compiler
      diagnostics, which quote the model's own source lines. The guard asks "did we
      disclose the key?"; a model that states the right answer in its own working has been
      told nothing, it derived it. Scanning that segment would fail the run precisely when
      the model succeeded, inverting the guard's meaning.

    Neither exclusion is a hole a prompt builder could exploit, because no function in this
    module accepts ``answer.value`` at all.
    ``test_prompt_construction_is_independent_of_the_answer_key`` proves that by rebuilding
    every prompt against a mutated key and comparing bytes, so independence from the key is
    a measured property rather than a claim resting on these paragraphs.
    """
    assert_no_oracle(
        prompt,
        cso,
        where=where,
        hypothesis=OracleHypothesis.H2,
        exemption=None,
    )


#: The task-independent constants excluded from the leak scan. Named here so that the test
#: which proves they are task-independent reads from the same list the guard uses.
TASK_INDEPENDENT_SEGMENTS: tuple[str, ...] = (SCHEMA_A_PRIME, HML_SPEC)


def strip_answer_block(text: str) -> str:
    """Remove the ``<ANSWER>...</ANSWER>`` span from a model reply.

    Carried-forward working is stripped of its conclusion before the second call sees it.
    Two reasons, and the second is the substantive one:

    * it keeps the authored prompt free of a string that a leak scanner would, correctly,
      be unable to distinguish from a disclosure;
    * it removes an anchoring confound. A model shown its own previous answer tends to
      restate it, which would suppress the revision rate in **both** arms and would blunt
      exactly the repair effect this design exists to measure.

    The working is preserved in full; only the conclusion is removed.
    """
    if not text:
        return ""
    out = re.sub(
        re.escape(ANSWER_OPEN) + r".*?" + re.escape(ANSWER_CLOSE),
        "",
        text,
        flags=re.S | re.I,
    )
    # An unterminated marker leaves everything after it, which would carry the answer.
    out = re.sub(re.escape(ANSWER_OPEN) + r".*\Z", "", out, flags=re.S | re.I)
    return out.strip()


# ---------------------------------------------------------------------------
# Arm SE
# ---------------------------------------------------------------------------


def se_initial_prompt(
    cso: CanonicalSemanticObject, *, exemption: OracleExemption | None = None
) -> ArmPrompt:
    _refuse_exemption(exemption, "se_initial_prompt")
    system = _BASE_SYSTEM

    def _assemble(schema: str) -> str:
        return "\n\n".join(
            [
                _problem_block(cso),
                "REASONING FORMAT\n" + schema,
                _answer_block(cso),
            ]
        )

    user = _assemble(SCHEMA_A_PRIME)
    _guard(system + "\n" + _assemble(_CARRIED_PLACEHOLDER), cso, "SE:initial")
    return ArmPrompt(Arm.SE, "initial", system, user, PER_CALL_BUDGET)


def se_review_prompt(
    cso: CanonicalSemanticObject,
    previous: str,
    *,
    exemption: OracleExemption | None = None,
) -> ArmPrompt:
    """The unaided second pass.

    Deliberately carries **no** information the model did not itself produce. Its only
    purpose is to equalise the attempt count against HML-V1's repair, so that "two tries"
    cannot explain a difference between the arms.
    """
    _refuse_exemption(exemption, "se_review_prompt")
    system = _BASE_SYSTEM
    carried = strip_answer_block(previous)
    review = (
        "REVIEW\nRe-examine the working above for errors of reasoning, scope or "
        "arithmetic. No external check has been performed on it and no new "
        "information is being supplied. Correct anything you find wrong, then give "
        "your final answer."
    )

    def _assemble(body: str) -> str:
        return "\n\n".join(
            [
                _problem_block(cso),
                "YOUR PREVIOUS WORKING\n" + body,
                review,
                _answer_block(cso),
            ]
        )

    user = _assemble(carried)
    _guard(system + "\n" + _assemble(_CARRIED_PLACEHOLDER), cso, "SE:review")
    return ArmPrompt(Arm.SE, "review", system, user, PER_CALL_BUDGET)


# ---------------------------------------------------------------------------
# Arm HML-V1
# ---------------------------------------------------------------------------

_HML_INSTRUCTION = f"""FORMALISATION FORMAT

Reason however you find most effective. Then express the problem's mathematical structure
as a Hamiltonian Lang module, and give your final answer.

Emit the module exactly once, fenced like this:

{HML_BLOCK_OPEN}
... your module ...
{HML_BLOCK_CLOSE}

The module will be compiled. Declare every object you use with the keyword that records
its epistemic status, keep quantifier order faithful to the problem, and do not conflate
equality with distribution or with implication."""


def hml_initial_prompt(
    cso: CanonicalSemanticObject,
    *,
    surface_spec: str = HML_SPEC,
    exemption: OracleExemption | None = None,
) -> ArmPrompt:
    """The formalisation call.

    ``surface_spec`` defaults to the frozen HML-L1 reference. It is a parameter because the
    syntax gate has **not** yet named a winning candidate surface; when it does, that
    surface is injected here and the change is one argument rather than a rewrite. Running
    the benchmark before a winner exists silently makes HML-L1 the winner by default, which
    is why :mod:`evaluation.v1_benchmark.pipeline` requires the surface to be declared.
    """
    _refuse_exemption(exemption, "hml_initial_prompt")
    system = _BASE_SYSTEM

    def _assemble(spec: str) -> str:
        return "\n\n".join(
            [
                _problem_block(cso),
                spec,
                _HML_INSTRUCTION,
                _answer_block(cso),
            ]
        )

    user = _assemble(surface_spec)
    _guard(system + "\n" + _assemble(_CARRIED_PLACEHOLDER), cso, "HML-V1:initial")
    return ArmPrompt(Arm.HML_V1, "initial", system, user, PER_CALL_BUDGET)


def hml_repair_prompt(
    cso: CanonicalSemanticObject,
    previous: str,
    diagnostics: str,
    *,
    surface_spec: str = HML_SPEC,
    exemption: OracleExemption | None = None,
) -> ArmPrompt:
    """The one repair.

    ``diagnostics`` is compiler output and nothing else. It is a verdict about the
    *module*, never about the answer: the compiler has no access to the answer key and
    cannot say whether a well-typed module models the right problem. That distinction is
    what keeps this a verifier and not an oracle.
    """
    _refuse_exemption(exemption, "hml_repair_prompt")
    system = _BASE_SYSTEM
    note = (
        "\n\nThe compiler checks the module's form: that it parses, that every "
        "name resolves, and that it type-checks. It does not know the answer and "
        "cannot tell you whether the module models the right problem. Repair the "
        "module, then give your final answer."
    )

    def _assemble(module: str, diags: str) -> str:
        return "\n\n".join(
            [
                _problem_block(cso),
                "YOUR PREVIOUS MODULE\n" + module,
                "COMPILER OUTPUT\n" + diags + note,
                _answer_block(cso),
            ]
        )

    user = _assemble(strip_answer_block(previous), diagnostics.strip())
    # Both the module and the diagnostics derive from model output -- the diagnostics quote
    # the module's own source lines -- so both are excluded from the scan for the reason
    # given in _guard, and the authored scaffolding is guarded on its own.
    _guard(
        system + "\n" + _assemble(_CARRIED_PLACEHOLDER, _CARRIED_PLACEHOLDER),
        cso,
        "HML-V1:repair",
    )
    return ArmPrompt(Arm.HML_V1, "repair", system, user, PER_CALL_BUDGET)


def extract_hml(text: str) -> str:
    """The fenced module, or the empty string.

    Deterministic and conservative. A reply with no fence yields ``""``, which is scored as
    a formalisation failure rather than being repaired by guesswork — inferring a module
    from unfenced prose would make the extractor part of the treatment.
    """
    if not text:
        return ""
    lower = text.lower()
    start = lower.find(HML_BLOCK_OPEN)
    if start < 0:
        return ""
    body = text[start + len(HML_BLOCK_OPEN) :]
    end = body.find(HML_BLOCK_CLOSE)
    return (body if end < 0 else body[:end]).strip()


# ---------------------------------------------------------------------------
# The matching table
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchedDimension:
    dimension: str
    matched: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"dimension": self.dimension, "matched": self.matched, "detail": self.detail}


#: What is matched between the arms and what is not. The unmatched rows are the ones that
#: matter: an unmatched budget is the likeliest single reason for this result to be
#: dismissed, so every asymmetry is stated here rather than left for a reader to find.
MATCHING: tuple[MatchedDimension, ...] = (
    MatchedDimension("task", True, "one CanonicalSemanticObject; prose and question are byte-identical in both arms"),
    MatchedDimension("model", True, f"{MODEL}, digest pinned to {MODEL_DIGEST[:12]}..."),
    MatchedDimension("temperature", True, f"{TEMPERATURE} in both arms, every call"),
    MatchedDimension("runtime", True, f"{RUNTIME}; one server configuration for the whole run"),
    MatchedDimension(
        "total generation budget",
        True,
        f"{TOTAL_COMPLETION_BUDGET} completion tokens per task per arm, across all calls "
        f"({CALLS_PER_ARM} x {PER_CALL_BUDGET}). Inherited from the ACQ0 context budget.",
    ),
    MatchedDimension("number of attempts", True, f"{CALLS_PER_ARM} generations per task in both arms"),
    MatchedDimension(
        "external information",
        False,
        "NOT MATCHED, and this is the treatment. HML-V1's second call carries compiler "
        "diagnostics; SE's second call carries only its own prior working. A win "
        "attributable to the repair is H3, not H2, and scoring attributes it per task.",
    ),
    MatchedDimension(
        "answer contract",
        True,
        "identical render_instruction() and identical ANSWER markers, so extraction is not "
        "an arm-dependent variable",
    ),
    MatchedDimension(
        "prompt length",
        False,
        "NOT MATCHED. The HML arm carries a language specification of roughly 3,000 "
        "characters; the SE arm carries an eight-point schema of roughly 600. Padding SE to "
        "match would add content nobody would otherwise send. Measured prompt_tokens are "
        "recorded per call so the gap is visible in the results rather than argued about.",
    ),
    MatchedDimension(
        "familiarity of the notation",
        False,
        "NOT MATCHED and not matchable. Structured English is in the model's pretraining "
        "distribution; Hamiltonian Lang was invented weeks ago and is not. This biases "
        "AGAINST the HML arm, so it does not manufacture a positive result, but it does "
        "mean a null result cannot distinguish 'the representation does not help' from "
        "'the model cannot yet write it'. That is ACQ0's question, not this benchmark's.",
    ),
    MatchedDimension(
        "worked demonstrations",
        True,
        "zero in both arms. The benchmark is zero-shot on both sides.",
    ),
)
