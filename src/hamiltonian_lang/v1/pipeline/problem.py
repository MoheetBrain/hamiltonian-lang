"""The problem file, split at load time into what the model may see and what it may not.

The firewall is structural, then asserted
-----------------------------------------
``solve`` runs in **reasoning mode**: the model is asked to derive an answer, so a prompt
carrying the answer does not merely inflate the score, it deletes the task. Two
independent mechanisms enforce that here, and the second is not a restatement of the
first:

1. :class:`Disclosable` holds prose, question and answer-format instruction, and *nothing
   else*. :func:`reasoning_prompt` takes a :class:`Disclosable` — not a
   :class:`Problem` — so the withheld fields are not in scope at the point the prompt is
   built. A leak would have to be a deliberate edit to the signature.
2. :func:`assert_prompt_carries_no_oracle` runs
   ``evaluation.acq0.protocols.oracle.assert_no_oracle`` over the finished prompt with
   **no exemption argument**. The ACQ0 encoding exemption is scoped to
   ``Hypothesis.ACQ0``; this path passes ``Hypothesis.H3`` and no exemption, and
   ``assert_no_oracle`` raises ``ExemptionMisuse`` if an exemption is ever presented
   under a reasoning hypothesis. The exemption is therefore unreachable from here by
   construction rather than by convention.

If the guard cannot be imported the pipeline **refuses to run**. A safety check that
degrades to a no-op when its dependency is missing is worse than no check, because the
record still says the prompt was scanned.

Problem file format (JSON)
--------------------------
::

    {
      "cso": { ... evaluation.corpus.cso.CanonicalSemanticObject fields ... },
      "pipeline": {"answer_binding": "area"},
      "scripted_turns": {"generation": "...", "repair": "..."}
    }

``scripted_turns`` is the model's *output*, not its input: it is what the deterministic
adapter replays when called. It never enters a prompt, and the oracle scan would catch it
if it did.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...improvement.runner import ScriptedTurns
from . import _evaluation

__all__ = [
    "PROBLEM_SCHEMA_VERSION",
    "ProblemError",
    "OracleGuardUnavailable",
    "AnswerKey",
    "Withheld",
    "Disclosable",
    "Problem",
    "load_problem",
    "problem_from_dict",
    "reasoning_prompt",
    "repair_prompt",
    "injected_repair_text",
    "assert_prompt_carries_no_oracle",
]

PROBLEM_SCHEMA_VERSION = "hml-v1-problem-1.0.0"


class ProblemError(ValueError):
    """The problem file is unusable."""


class OracleGuardUnavailable(RuntimeError):
    """The no-oracle guard could not be loaded, so no prompt may be built."""


# ---------------------------------------------------------------------------
# The two halves
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnswerKey:
    """The verified answer. Read only *after* the model has answered."""

    kind: str
    value: Any
    tolerance: float = 1e-6
    options: tuple[str, ...] = ()
    justification: str = ""

    def render_instruction(self) -> str:
        """The *format* of the answer. Names the kind of answer, never the answer."""
        return _evaluation.cso().AnswerSpec(
            kind=self.kind,
            value=self.value,
            tolerance=self.tolerance,
            options=list(self.options),
        ).render_instruction()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "tolerance": self.tolerance,
            "options": list(self.options),
            "justification": self.justification,
        }


@dataclass(frozen=True)
class Withheld:
    """Everything the model must never receive. Not reachable from the prompt builder."""

    answer_key: AnswerKey
    reference_hml: str = ""
    semantics: dict[str, Any] = field(default_factory=dict)
    distractors: tuple[str, ...] = ()


@dataclass(frozen=True)
class Disclosable:
    """Everything the model may receive. The only input :func:`reasoning_prompt` takes."""

    problem_id: str
    domain: str
    prose: str
    question: str
    answer_instruction: str


@dataclass(frozen=True)
class Problem:
    """One problem, with the firewall already applied."""

    disclosable: Disclosable
    withheld: Withheld
    #: Name of the declaration whose value is the answer. Pipeline metadata; the model
    #: never sees it and it carries no value, only a name that is already in the prose.
    answer_binding: str | None = None
    scripted_turns: ScriptedTurns | None = None
    difficulty: str = "medium"
    source_path: str = "<dict>"

    @property
    def problem_id(self) -> str:
        return self.disclosable.problem_id

    @property
    def domain(self) -> str:
        return self.disclosable.domain

    def cso(self) -> Any:
        """Rebuild the canonical semantic object the oracle scanner needs.

        Built here, at the point of scanning, rather than carried around: the scanner
        needs the answer key in order to look for it, and that is the one legitimate
        consumer of the withheld half.
        """
        module = _evaluation.cso()
        AnswerSpec = module.AnswerSpec
        SemanticFacts = module.SemanticFacts

        key = self.withheld.answer_key
        semantics = {k: v for k, v in self.withheld.semantics.items() if not k.startswith("_")}
        facts = SemanticFacts(**semantics) if semantics else SemanticFacts()
        return module.CanonicalSemanticObject(
            id=self.problem_id,
            domain=self.domain,
            difficulty=self.difficulty,
            prose=self.disclosable.prose,
            question=self.disclosable.question,
            answer=AnswerSpec(
                kind=key.kind,
                value=key.value,
                tolerance=key.tolerance,
                options=list(key.options),
                justification=key.justification,
            ),
            semantics=facts,
            distractors=list(self.withheld.distractors),
            reference_hml=self.withheld.reference_hml,
        )

    def to_public_dict(self) -> dict[str, Any]:
        """What may be printed. Deliberately omits the withheld half."""
        return {
            "problem_id": self.problem_id,
            "domain": self.domain,
            "difficulty": self.difficulty,
            "source_path": self.source_path,
            "answer_binding": self.answer_binding,
        }


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_problem(path: str | Path) -> Problem:
    p = Path(path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProblemError(f"problem file {p} does not exist") from exc
    except json.JSONDecodeError as exc:
        raise ProblemError(f"problem file {p} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProblemError(f"problem file {p} must contain a JSON object")
    return problem_from_dict(raw, source_path=str(p))


def problem_from_dict(raw: dict[str, Any], *, source_path: str = "<dict>") -> Problem:
    cso = raw.get("cso")
    if not isinstance(cso, dict):
        raise ProblemError(f"{source_path}: missing the 'cso' object")
    for required in ("id", "domain", "prose", "question", "answer"):
        if not cso.get(required):
            raise ProblemError(f"{source_path}: cso.{required} is missing or empty")
    answer = cso["answer"]
    if not isinstance(answer, dict) or "kind" not in answer:
        raise ProblemError(f"{source_path}: cso.answer must be an object with a 'kind'")

    key = AnswerKey(
        kind=str(answer["kind"]),
        value=answer.get("value"),
        tolerance=float(answer.get("tolerance", 1e-6)),
        options=tuple(str(o) for o in answer.get("options", ())),
        justification=str(answer.get("justification", "")),
    )
    withheld = Withheld(
        answer_key=key,
        reference_hml=str(cso.get("reference_hml", "")),
        semantics=dict(cso.get("semantics") or {}),
        distractors=tuple(str(d) for d in cso.get("distractors", ())),
    )
    disclosable = Disclosable(
        problem_id=str(cso["id"]),
        domain=str(cso["domain"]),
        prose=str(cso["prose"]),
        question=str(cso["question"]),
        answer_instruction=key.render_instruction(),
    )

    turns_raw = raw.get("scripted_turns")
    turns: ScriptedTurns | None = None
    if isinstance(turns_raw, dict):
        generation = turns_raw.get("generation")
        if not isinstance(generation, str) or not generation.strip():
            raise ProblemError(f"{source_path}: scripted_turns.generation must be text")
        repair = turns_raw.get("repair")
        if repair is not None and not isinstance(repair, str):
            raise ProblemError(f"{source_path}: scripted_turns.repair must be text or absent")
        turns = ScriptedTurns(generation=generation, repair=repair)

    pipeline = raw.get("pipeline") or {}
    if not isinstance(pipeline, dict):
        raise ProblemError(f"{source_path}: 'pipeline' must be an object")

    return Problem(
        disclosable=disclosable,
        withheld=withheld,
        answer_binding=pipeline.get("answer_binding"),
        scripted_turns=turns,
        difficulty=str(cso.get("difficulty", "medium")),
        source_path=source_path,
    )


# ---------------------------------------------------------------------------
# Prompts — the only functions that produce text for a model
# ---------------------------------------------------------------------------

_SURFACE_INSTRUCTION = (
    "Work the problem out yourself, then encode your reasoning as a Hamiltonian Lang "
    "module in the {surface} surface. Emit the module in a single fenced block tagged "
    "`{tag}`. State every constraint you relied on with `require` so it can be checked; "
    "do not assert anything you have not derived."
)


def reasoning_prompt(
    disclosable: Disclosable, *, surface: str, fence_tag: str = "hml"
) -> str:
    """Build the draft prompt.

    Takes :class:`Disclosable`, not :class:`Problem`. The answer key, the reference
    encoding, the structured ground truth and the distractors are not parameters of this
    function and are not in its scope.
    """
    return "\n\n".join(
        [
            f"# Problem {disclosable.problem_id} ({disclosable.domain})",
            disclosable.prose.strip(),
            f"Question: {disclosable.question.strip()}",
            f"Answer format: {disclosable.answer_instruction}",
            _SURFACE_INSTRUCTION.format(surface=surface, tag=fence_tag),
        ]
    )


_REPAIR_TAIL = "Apply the plan. Change only what the diagnostic names."


def repair_prompt(disclosable: Disclosable, *, payload_text: str) -> str:
    """Build the repair prompt from the question and the Teacher's packet.

    The packet comes from :mod:`hamiltonian_lang.repair`, which guarantees it carries a
    cause and a plan and never the corrected program. The answer key is, again, not a
    parameter of this function.
    """
    return "\n\n".join(
        [
            f"# Repair for problem {disclosable.problem_id}",
            f"Question: {disclosable.question.strip()}",
            payload_text,
            _REPAIR_TAIL,
        ]
    )


def injected_repair_text(disclosable: Disclosable, payload: Any) -> str:
    """Exactly the material *this pipeline* puts into the repair prompt.

    The model's own broken output is excluded, and the exclusion is not a loophole.
    ``TaskInformation.UPSTREAM_MODEL_OUTPUT`` is model-generated, never key-generated,
    which is why the ACQ0 protocol does not treat it as an oracle field. A model that
    derived the right answer on the draft turn legitimately has it in its own text;
    scanning that text would report the model's success as our leak, and the first
    person to hit the false positive would loosen the guard for everyone.

    What *is* scanned is everything we inject: the question, the rendered diagnostic, the
    retrieved project context, the Teacher's plan and our own instruction. Those are the
    channels through which the answer key could actually travel.
    """
    return "\n\n".join(
        part
        for part in (
            f"Question: {disclosable.question.strip()}",
            getattr(payload, "diagnostic_text", ""),
            getattr(payload, "context_text", ""),
            getattr(payload, "plan_text", ""),
            _REPAIR_TAIL,
        )
        if part
    )


def assert_prompt_carries_no_oracle(prompt_text: str, problem: Problem, *, where: str) -> None:
    """Mandatory. Raises if any part of the answer key reached ``prompt_text``.

    No ``exemption`` parameter is accepted or forwarded. ``Hypothesis.H3`` is passed
    explicitly, which makes ``assert_no_oracle`` raise ``ExemptionMisuse`` should an
    exemption ever be threaded through here by a later edit.
    """
    try:
        module = _evaluation.oracle()
    except _evaluation.EvaluationTreeUnavailable as exc:  # pragma: no cover - environment
        raise OracleGuardUnavailable(
            "the no-oracle guard could not be loaded. The pipeline refuses to build a "
            f"prompt rather than build an unscanned one and record it as scanned: {exc}"
        ) from exc
    module.assert_no_oracle(
        prompt_text, problem.cso(), where=where, hypothesis=module.Hypothesis.H3
    )
