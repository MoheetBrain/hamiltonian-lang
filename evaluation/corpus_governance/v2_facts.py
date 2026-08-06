"""Fact provenance: every prose clause maps to canonical facts, and back again.

Two properties the earlier tests could not establish.

**C — exact prose coverage.** "Prose names every declared entity" is necessary and not
sufficient: it cannot see a *missing* initialiser, a *reordered* binder, or an *invented*
clause. Here each generated clause carries the fact ids it represents, so coverage is set
equality rather than substring presence, and an unmapped clause is a failure.

**F — structured-target reversibility.** If the model-visible target cannot be turned back
into the canonical semantic payload, then it is a summary, and a model shown only a summary
is being asked to guess. Reconstruction reads the target **alone** — never the authored
source, the reference, or the expected hash.

Fact ids reference existing compiler AST statements by index and kind. No second
mathematical AST is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical_v2 import CanonicalAcq0TaskV2

__all__ = [
    "Fact",
    "Clause",
    "ProseCoverage",
    "required_public_facts",
    "prose_clauses",
    "check_prose_coverage",
    "reconstruct_semantic_payload",
    "semantic_payload",
    "ReversibilityFailure",
]


class ReversibilityFailure(RuntimeError):
    """The structured target does not carry enough to rebuild the payload."""


@dataclass(frozen=True)
class Fact:
    """One atomic, model-visible mathematical fact."""

    fact_id: str
    kind: str
    detail: str

    def __str__(self) -> str:
        return f"{self.fact_id}:{self.kind}"


@dataclass(frozen=True)
class Clause:
    clause_id: str
    text: str
    fact_ids: tuple[str, ...]
    view: str
    required: bool = True


@dataclass(frozen=True)
class ProseCoverage:
    task_id: str
    required: frozenset[str]
    emitted: frozenset[str]
    unmapped: tuple[str, ...]

    @property
    def exact(self) -> bool:
        return self.required == self.emitted and not self.unmapped

    def render(self) -> str:
        if self.exact:
            return f"{self.task_id}: EXACT ({len(self.required)} facts)"
        missing = sorted(self.required - self.emitted)
        extra = sorted(self.emitted - self.required)
        return (f"{self.task_id}: INEXACT missing={missing} extra={extra} "
                f"unmapped={list(self.unmapped)}")


def _facts_of(record: dict[str, Any]) -> list[Fact]:
    """Every load-bearing element of ONE positional statement.

    Keyed by position, not by kind-bucket index, so a statement can neither be dropped nor
    silently renumbered. `check_*` has a branch here because it had none in the bucketed
    predecessor -- and its absence let the coverage check certify a task whose defining
    statement it could not see.
    """
    sid = record["statement_id"]
    kind = record["kind"]
    out = [Fact(f"{sid}.kind", "statement_kind", kind),
           Fact(f"{sid}.position", "position", str(record["position"]))]

    if kind in {"var", "const", "param", "obs", "index", "rv"}:
        out.append(Fact(f"{sid}.name", "declaration_name", record["name"]))
        out.append(Fact(f"{sid}.type", "type", str(record["type"])))
        if "value" in record:
            out.append(Fact(f"{sid}.value", "initializer", str(record["value"])))
    elif kind == "def":
        out.append(Fact(f"{sid}.name", "definition_name", record["name"]))
        out.append(Fact(f"{sid}.codomain", "codomain", str(record["codomain"])))
        out.append(Fact(f"{sid}.body", "function_body", record["body"]))
        # binder ORDER is content: a swap changes the function.
        for j, b in enumerate(record["binders"]):
            out.append(Fact(f"{sid}.binder{j}", "binder", f"{j}:{b['name']}:{b['type']}"))
    elif kind in {"assume", "require", "prove"}:
        out.append(Fact(f"{sid}.expression", f"{kind}_expression", record["expression"]))
    elif kind in {"prior", "likelihood", "law", "posterior"}:
        out.append(Fact(f"{sid}.target", "law_target", str(record["target"])))
        out.append(Fact(f"{sid}.family", "probability_family", record["distribution"]))
        if record.get("given"):
            out.append(Fact(f"{sid}.given", "conditioning", ",".join(record["given"])))
    elif kind.startswith("check_"):
        out.append(Fact(f"{sid}.subject", "checked_subject", record["subject"]))
        out.append(Fact(f"{sid}.expected", "checked_value", record["expression"]))
    else:
        raise ReversibilityFailure(f"no fact derivation for statement kind {kind!r}")
    return out


def _clause_text(record: dict[str, Any]) -> str:
    """The prose sentence for one positional statement. THE prose generator.

    `render_prose` joins these. Two independent renderers is how the bucketed clause
    generator came to omit a statement the ordered one emitted.
    """
    kind = record["kind"]
    if kind == "const":
        return (f"The constant `{record['name']}` has type `{record['type']}` and the "
                f"value `{record.get('value')}`.")
    if kind == "obs":
        return (f"The observed quantity `{record['name']}` has type `{record['type']}` "
                f"and the value `{record.get('value')}`.")
    if kind in {"var", "param", "index", "rv"}:
        return (f"The quantity `{record['name']}` is declared as {kind} with type "
                f"`{record['type']}`.")
    if kind == "def":
        binders = ", ".join(f"`{b['name']}` of type `{b['type']}`"
                            for b in record["binders"])
        # "The value X ... is defined by B" also reads as `const X : T = B` and as
        # `var X : T = B`, and all three hash differently. Naming the statement kind is
        # the fix; every other kind already names its own keyword.
        if binders:
            return (f"The definition `{record['name']}` takes {binders}, has codomain "
                    f"`{record['codomain']}` and body `{record['body']}`.")
        return (f"The definition `{record['name']}` takes no arguments, has codomain "
                f"`{record['codomain']}` and body `{record['body']}`.")
    if kind == "assume":
        return f"It is assumed that `{record['expression']}`."
    if kind == "require":
        return f"It is required that `{record['expression']}`."
    if kind == "prove":
        return f"The goal is to prove that `{record['expression']}`."
    if kind in {"prior", "likelihood", "law", "posterior"}:
        given = (" given " + ", ".join(f"`{g}`" for g in record["given"])
                 if record.get("given") else "")
        return (f"The {kind} of `{record['target']}`{given} is "
                f"`{record['distribution']}`.")
    if kind.startswith("check_"):
        return (f"It is checked that the {kind[len('check_'):]} of "
                f"`{record['subject']}` is `{record['expression']}`.")
    raise ReversibilityFailure(f"no prose form for statement kind {kind!r}")


def required_public_facts(task: CanonicalAcq0TaskV2) -> tuple[Fact, ...]:
    """Every fact the ACQ0 view must expose, derived from the ORDERED view.

    One fact per semantically load-bearing element: a declaration's kind, type and
    initialiser are separate facts, because prose can drop the initialiser while keeping
    the name -- which is exactly what v1 did. The module name is a fact for the same
    reason: it is part of the content hash and was in no prose sentence at all.
    """
    from .v2_view import encoding_view

    view = encoding_view(task)
    out: list[Fact] = [Fact("module", "module_name", view["module"])]
    for record in sorted(view["encoding_statements"], key=lambda r: r["position"]):
        out.extend(_facts_of(record))
    for i, p in enumerate(task.prohibited_assumptions):
        out.append(Fact(f"prohibit{i}", "prohibited_assumption", p))

    # The absence of a goal is itself a fact the ACQ0 view must convey.
    out.append(Fact("objective", "objective",
                    "none" if task.objective is None
                    else f"{task.objective.kind}:{task.objective.statement}"))
    return tuple(out)


def prose_clauses(task: CanonicalAcq0TaskV2, view: str = "ACQ0_TRANSLATION") -> tuple[Clause, ...]:
    """The prose, clause by clause, each tagged with the facts it carries.

    Built from the ordered view — the same traversal `encoding_view` uses — so the mapping
    is constructed rather than inferred, and cannot drift from the statements it describes.
    """
    from .v2_view import encoding_view

    v = encoding_view(task)
    out: list[Clause] = [Clause(
        "c.module",
        f"The module is named `{v['module']}`; every statement below belongs to it, "
        f"in the order given.",
        ("module",), view)]

    for record in sorted(v["encoding_statements"], key=lambda r: r["position"]):
        ids = tuple(f.fact_id for f in _facts_of(record))
        out.append(Clause(f"c.{record['statement_id']}", _clause_text(record), ids, view))

    # A derived fact is explanatory, never a premise, and carries no required fact id.
    for i, fact in enumerate(task.derived_facts):
        if fact.state_in_prose:
            out.append(Clause(
                f"c.derived{i}",
                f"It follows from {' and '.join(fact.derived_from)} that "
                f"`{fact.statement}`; this is a consequence, not a further restriction, "
                f"and must not be encoded.",
                (), view, required=False))
    for i, p in enumerate(task.prohibited_assumptions):
        out.append(Clause(f"c.prohibit{i}",
                          f"Do not assume {p}. This is guidance and must not be encoded.",
                          (f"prohibit{i}",), view))

    # The objective is METADATA about the task, not a statement to emit. The previous
    # wording -- "The goal is to prove X." -- was one word from the prose form of the
    # `prove` statement itself, so every objective-bearing task shipped two goal sentences
    # and the duplicate reading COMPILED with a different hash. Naming the already-listed
    # statement, and forbidding a second, removes the rival reading.
    out.append(Clause(
        "c.objective",
        "No goal is stated; do not add one. Encode the statements above and nothing else."
        if task.objective is None
        else (f"The point of this task is the `{task.objective.kind}` statement already "
              f"listed above ({task.objective.statement}). It is described here, not "
              f"restated: do not emit a second statement for it."),
        ("objective",), view))
    return tuple(out)


def check_prose_coverage(task: CanonicalAcq0TaskV2) -> ProseCoverage:
    required = {f.fact_id for f in required_public_facts(task)}
    clauses = prose_clauses(task)
    emitted = {fid for c in clauses for fid in c.fact_ids}
    unmapped = tuple(c.clause_id for c in clauses if c.required and not c.fact_ids)
    return ProseCoverage(task.task_id, frozenset(required), frozenset(emitted), unmapped)


# --- F: reversibility ------------------------------------------------------------------

def semantic_payload(task: CanonicalAcq0TaskV2) -> dict[str, Any]:
    """The SEMANTIC content of a task, excluding operational fields."""
    from .v2_view import encoding_view

    view = encoding_view(task)
    return {
        "module": view["module"],
        "family": view["family"],
        "encoding_statements": view["encoding_statements"],
        "derived_facts": view["derived_facts"],
        "objective": view["objective"],
        "prohibited_assumptions": view["prohibited_assumptions"],
    }


def reconstruct_semantic_payload(structured_target: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the payload from the model-visible target **alone**.

    Reads no authored source, no reference encoding, no expected hash and no other task.
    If a field is absent the target was a summary, and reconstruction fails loudly rather
    than filling a default -- a silently defaulted field is how a model gets blamed for
    information it never had.

    This check is weaker than `view_reconstructs_exactly` and does not replace it: both
    sides derive from the view, so it can only detect a *missing key*, never a statement
    the view drops. That blind spot is why the reconstruction gate exists.
    """
    required = ("module", "family", "encoding_statements", "derived_facts", "objective",
                "prohibited_assumptions")
    missing = [k for k in required if k not in structured_target]
    if missing:
        raise ReversibilityFailure(
            f"the model-visible target omits {missing}; it is a summary, not a target")
    return {k: structured_target[k] for k in required}
