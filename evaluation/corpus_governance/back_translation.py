"""Gate 3 — back-translation, and the refusal to average judges.

What the gate does
------------------
Render the formal object into **controlled natural language**, then compare that rendering
against the specification the item was authored from. If the two say different things, the
formalisation is wrong however cleanly it compiles — which is the FormalMATH finding
restated: gate 1 accepted roughly 92% of candidates and only about 32% survived semantic
checking, so most of what a type checker waves through does not mean what the prose said.

The controlled language
-----------------------
:func:`render_controlled_nl` is a deterministic surface-to-English renderer over the frozen
AST. It is deliberately stilted — one clause per statement, fixed vocabulary, no synonyms,
no reordering. A fluent renderer would paper over exactly the differences the gate exists
to expose: "for every x there is a y" and "there is a y for every x" read almost the same
in fluent English and are different propositions, so the renderer emits the quantifier
prefix in source order with explicit numbering and never smooths it.

Nothing here calls a model. Rendering is a pure function of the parsed module.

Judges
------
Comparison of the rendering against the specification is the one step where independent
judgement is legitimate — and where a benchmark most easily destroys its own evidence.
:class:`JudgePanel` therefore:

* retains **every** individual :class:`JudgeDecision`, permanently;
* exposes **no** majority vote, no mean, no modal alignment;
* returns ``INCONCLUSIVE`` whenever judges disagree, and raises a human-review request.

Two judges saying ``ALIGNED`` and one saying ``MISALIGNED`` is not "aligned, 2-1". It is an
item about which competent readers disagree, which is a property of the *item* and the
single most useful thing the gate can tell you. Majority voting deletes it and replaces it
with a number that looks like agreement.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from hamiltonian_lang.ast.nodes import (
    AssumeStmt,
    CheckStmt,
    Declaration,
    DefineStmt,
    InferStmt,
    LawStmt,
    Module,
    ObjectiveStmt,
    ProveStmt,
    RequireStmt,
    SolveStmt,
    Statement,
)
from hamiltonian_lang.backends.hml import render_expr

from .human_gate import ReviewRequest, ReviewTrigger

__all__ = [
    "Alignment",
    "JudgeDecision",
    "JudgePanel",
    "panel_from",
    "render_controlled_nl",
    "normalise_for_comparison",
    "deterministic_overlap",
]


class Alignment(StrEnum):
    """The three verdicts. ``INCONCLUSIVE`` is a result, not a missing result."""

    ALIGNED = "aligned"
    MISALIGNED = "misaligned"
    INCONCLUSIVE = "inconclusive"


# ---------------------------------------------------------------------------
# Controlled natural language
# ---------------------------------------------------------------------------

#: Declaration keyword -> the fixed English phrase. One phrase per kind, no synonyms, so
#: that a difference in the rendering is always a difference in the object.
_KIND_PHRASE = {
    "var": "an unknown",
    "param": "a parameter to be inferred",
    "const": "a fixed constant",
    "obs": "an observed quantity",
    "index": "an index",
    "rv": "a random variable",
}

_LAW_PHRASE = {
    "law": "is distributed as",
    "prior": "has prior distribution",
    "likelihood": "has likelihood",
}


def _type_phrase(node: Any) -> str:
    text = getattr(node, "declared_type", None)
    return str(text) if text is not None else "an unstated type"


def _names(refs: Sequence[Any]) -> str:
    """Reference names in source order. Never sorted — order is meaning here."""
    return ", ".join(getattr(r, "name", str(r)) for r in refs)


def _stmt_sentence(index: int, stmt: Statement) -> str:
    """One statement, one numbered clause, in source order."""
    n = f"({index})"
    if isinstance(stmt, Declaration):
        kind = _KIND_PHRASE.get(stmt.kind, f"a {stmt.kind}")
        base = f"{n} {stmt.name} is {kind} of type {_type_phrase(stmt)}"
        if getattr(stmt, "value", None) is not None:
            base += f", fixed to {render_expr(stmt.value)}"
        return base + "."
    if isinstance(stmt, DefineStmt):
        return f"{n} {stmt.name} is defined to equal {render_expr(stmt.body)}."
    if isinstance(stmt, LawStmt):
        phrase = _LAW_PHRASE.get(stmt.role, "is related by law to")
        cond = f" given {_names(stmt.given)}" if stmt.given else ""
        dist = render_expr(stmt.distribution) if stmt.distribution is not None else "?"
        return f"{n} {stmt.target}{cond} {phrase} {dist}."
    if isinstance(stmt, AssumeStmt):
        return f"{n} it is assumed, not proved, that {render_expr(stmt.proposition)}."
    if isinstance(stmt, RequireStmt):
        return f"{n} it is required that {render_expr(stmt.proposition)}."
    if isinstance(stmt, ProveStmt):
        return f"{n} it is claimed, and must be proved, that {render_expr(stmt.proposition)}."
    if isinstance(stmt, CheckStmt):
        subject = render_expr(stmt.subject) if stmt.subject is not None else "?"
        return (
            f"{n} the {stmt.check_kind} of {subject} is checked to equal {stmt.expected}."
        )
    if isinstance(stmt, ObjectiveStmt):
        return f"{n} the objective is to {stmt.direction} {render_expr(stmt.expression)}."
    if isinstance(stmt, SolveStmt):
        return f"{n} the unknowns to solve for are {_names(stmt.targets)}."
    if isinstance(stmt, InferStmt):
        return f"{n} the quantity to infer is the {stmt.query} of {_names(stmt.targets)}."
    return f"{n} {type(stmt).__name__} (no controlled rendering)."


def render_controlled_nl(module: Module) -> str:
    """Render a parsed module as numbered controlled English, in source order.

    Source order is preserved and never normalised. Two modules that differ only in the
    order of a quantifier prefix must produce different renderings, because they are
    different propositions; a renderer that sorted its output would report them identical.
    """
    lines = [f"Module {module.name}."]
    lines += [_stmt_sentence(i + 1, s) for i, s in enumerate(module.statements)]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deterministic pre-comparison
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[a-z0-9_]+")

#: Words carrying no propositional content. Stripped before overlap so that agreement on
#: "the of a is" cannot inflate the score.
_STOP = frozenset(
    """a an the of to for is are be that this it its as at by on in and or with which
    where when we let there such then thus so all each any some given""".split()
)


def normalise_for_comparison(text: str) -> tuple[str, ...]:
    """Lowercase, keep word characters, drop stop words. Order is preserved."""
    return tuple(w for w in _WORD.findall(text.lower()) if w not in _STOP)


def deterministic_overlap(specification: str, rendering: str) -> float:
    """Jaccard overlap of content words. A screen, never a verdict.

    This number exists to *route* items to judges, not to decide them. A high overlap is
    entirely compatible with a reversed quantifier prefix or a swapped distribution role,
    because those errors reuse every word of the original. It is reported alongside the
    judges' decisions and never in place of them.
    """
    a = set(normalise_for_comparison(specification))
    b = set(normalise_for_comparison(rendering))
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------------------
# Judges
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JudgeDecision:
    """One judge's verdict, kept whole and kept forever."""

    judge_id: str
    alignment: Alignment
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "judge_id": self.judge_id,
            "alignment": str(self.alignment),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class JudgePanel:
    """Every judge's decision, and a verdict that refuses to vote.

    The verdict rule, in full:

    * every judge says ``ALIGNED``            -> ``ALIGNED``
    * every judge says ``MISALIGNED``         -> ``MISALIGNED``
    * anything else, including any single
      ``INCONCLUSIVE`` and any disagreement   -> ``INCONCLUSIVE`` + human review

    Note what is missing: there is no branch in which a minority decision is discarded.
    ``2 ALIGNED, 1 MISALIGNED`` and ``1 ALIGNED, 2 MISALIGNED`` produce the same verdict,
    because in both cases the honest statement is "competent readers disagree about this
    item" and the count does not change it.
    """

    item_id: str
    specification: str
    rendering: str
    decisions: tuple[JudgeDecision, ...]
    #: The deterministic screen, recorded beside the judgements, never instead of them.
    lexical_overlap: float = 0.0

    def __post_init__(self) -> None:
        if not self.decisions:
            raise ValueError(
                f"{self.item_id}: a panel with no decisions is not an inconclusive panel, "
                f"it is an unrun gate"
            )
        seen = [d.judge_id for d in self.decisions]
        if len(set(seen)) != len(seen):
            raise ValueError(f"{self.item_id}: the same judge appears twice: {sorted(seen)}")

    @property
    def alignments(self) -> tuple[Alignment, ...]:
        return tuple(d.alignment for d in self.decisions)

    def is_disputed(self) -> bool:
        """True when the judges did not all say the same thing."""
        return len(set(self.alignments)) > 1

    def verdict(self) -> Alignment:
        distinct = set(self.alignments)
        if distinct == {Alignment.ALIGNED}:
            return Alignment.ALIGNED
        if distinct == {Alignment.MISALIGNED}:
            return Alignment.MISALIGNED
        return Alignment.INCONCLUSIVE

    def review_request(self) -> ReviewRequest | None:
        """The human-review request this panel raises, or ``None`` if it is unanimous."""
        if self.verdict() is not Alignment.INCONCLUSIVE:
            return None
        return ReviewRequest(
            request_id=f"bt::{self.item_id}",
            trigger=ReviewTrigger.INCONCLUSIVE_SEMANTIC_PAIR,
            item_id=self.item_id,
            question=(
                "Does the controlled-language rendering of the formal object state the "
                "same proposition as the specification? Independent judges did not agree; "
                "their individual decisions are preserved below and were not voted on."
            ),
            evidence={
                "specification": self.specification,
                "rendering": self.rendering,
                "lexical_overlap": round(self.lexical_overlap, 4),
                "decisions": [d.to_dict() for d in self.decisions],
                "disputed": self.is_disputed(),
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "verdict": str(self.verdict()),
            "disputed": self.is_disputed(),
            "lexical_overlap": round(self.lexical_overlap, 4),
            "decisions": [d.to_dict() for d in self.decisions],
        }


def panel_from(
    item_id: str,
    specification: str,
    rendering: str,
    decisions: Sequence[JudgeDecision],
) -> JudgePanel:
    """Assemble a panel and attach the deterministic screen."""
    return JudgePanel(
        item_id=item_id,
        specification=specification,
        rendering=rendering,
        decisions=tuple(decisions),
        lexical_overlap=deterministic_overlap(specification, rendering),
    )
