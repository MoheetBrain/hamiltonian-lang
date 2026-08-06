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


def required_public_facts(task: CanonicalAcq0TaskV2) -> tuple[Fact, ...]:
    """Every fact the ACQ0 view must expose, derived from the canonical object.

    One fact per semantically load-bearing element: a declaration's kind, type and
    initialiser are separate facts, because prose can drop the initialiser while keeping
    the name -- which is exactly what v1 did.
    """
    st = task.structured_target()
    out: list[Fact] = []

    for i, d in enumerate(st["declarations"]):
        out.append(Fact(f"decl{i}.name", "declaration_name", d["name"]))
        out.append(Fact(f"decl{i}.kind", "declaration_kind", d["kind"]))
        out.append(Fact(f"decl{i}.type", "type", str(d["type"])))
        if "value" in d:
            out.append(Fact(f"decl{i}.value", "initializer", str(d["value"])))

    for i, f in enumerate(st["definitions"]):
        out.append(Fact(f"def{i}.name", "definition_name", f["name"]))
        out.append(Fact(f"def{i}.codomain", "codomain", str(f["codomain"])))
        out.append(Fact(f"def{i}.body", "function_body", f["body"]))
        # binder ORDER is content: a swap changes the function.
        for j, b in enumerate(f["binders"]):
            out.append(Fact(f"def{i}.binder{j}", "binder", f"{j}:{b['name']}:{b['type']}"))

    for i, law in enumerate(st["probability_laws"]):
        out.append(Fact(f"law{i}.role", "law_role", law["role"]))
        out.append(Fact(f"law{i}.family", "probability_family", law["distribution"]))
        out.append(Fact(f"law{i}.target", "law_target", str(law["target"])))
        if law["given"]:
            out.append(Fact(f"law{i}.given", "conditioning", ",".join(law["given"])))

    for i, a in enumerate(st["assumptions"]):
        out.append(Fact(f"assume{i}", "assumption", a))
    for i, c in enumerate(st["domain_constraints"]):
        out.append(Fact(f"require{i}", "requirement", c))
    for i, p in enumerate(task.prohibited_assumptions):
        out.append(Fact(f"prohibit{i}", "prohibited_assumption", p))

    # The absence of a goal is itself a fact the ACQ0 view must convey.
    out.append(Fact("objective", "objective",
                    "none" if task.objective is None
                    else f"{task.objective.kind}:{task.objective.statement}"))
    return tuple(out)


def prose_clauses(task: CanonicalAcq0TaskV2, view: str = "ACQ0_TRANSLATION") -> tuple[Clause, ...]:
    """Regenerate the prose clause by clause, each tagged with the facts it carries.

    Built from the same structured target the prose renderer uses, so the mapping is
    constructed rather than inferred. Inferring it from finished text would be the
    heuristic matching this module exists to avoid.
    """
    st = task.structured_target()
    out: list[Clause] = []

    for i, d in enumerate(st["declarations"]):
        ids = [f"decl{i}.name", f"decl{i}.kind", f"decl{i}.type"]
        if "value" in d:
            ids.append(f"decl{i}.value")
            text = (f"The constant {d['name']} has type {d['type']} and the value "
                    f"{d['value']}." if d["kind"] == "const" else
                    f"The observed quantity {d['name']} has type {d['type']} and the "
                    f"value {d['value']}.")
        else:
            text = (f"The quantity {d['name']} is declared as {d['kind']} "
                    f"with type {d['type']}.")
        out.append(Clause(f"c.decl{i}", text, tuple(ids), view))

    for i, f in enumerate(st["definitions"]):
        ids = [f"def{i}.name", f"def{i}.codomain", f"def{i}.body"]
        ids += [f"def{i}.binder{j}" for j in range(len(f["binders"]))]
        binders = ", ".join(f"{b['name']} of type {b['type']}" for b in f["binders"])
        text = (f"The function {f['name']} takes {binders}, returns {f['codomain']}, "
                f"and is defined by {f['body']}." if binders else
                f"The value {f['name']} has type {f['codomain']} and is defined by "
                f"{f['body']}.")
        out.append(Clause(f"c.def{i}", text, tuple(ids), view))

    for i, law in enumerate(st["probability_laws"]):
        ids = [f"law{i}.role", f"law{i}.family", f"law{i}.target"]
        given = ""
        if law["given"]:
            ids.append(f"law{i}.given")
            given = f" given {', '.join(law['given'])}"
        out.append(Clause(f"c.law{i}",
                          f"The {law['role']} of {law['target']}{given} is "
                          f"{law['distribution']}.", tuple(ids), view))

    for i, a in enumerate(st["assumptions"]):
        out.append(Clause(f"c.assume{i}", f"It is assumed that {a}.", (f"assume{i}",), view))
    for i, c in enumerate(st["domain_constraints"]):
        out.append(Clause(f"c.require{i}", f"It is required that {c}.",
                          (f"require{i}",), view))
    for i, p in enumerate(task.prohibited_assumptions):
        out.append(Clause(f"c.prohibit{i}", f"Do not assume {p}.",
                          (f"prohibit{i}",), view))

    out.append(Clause(
        "c.objective",
        "No goal is stated; encode the object only."
        if task.objective is None
        else f"The goal is to {task.objective.kind} {task.objective.statement}.",
        ("objective",), view))

    # A derived fact is explanatory, never a premise, and carries no required fact id.
    for i, fact in enumerate(task.derived_facts):
        if fact.state_in_prose:
            out.append(Clause(
                f"c.derived{i}",
                f"It follows from {' and '.join(fact.derived_from)} that "
                f"{fact.statement}; this is a consequence, not a further restriction.",
                (), view, required=False))
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
    st = task.structured_target()
    return {
        "module": st["module"],
        "family": st["family"],
        "declarations": st["declarations"],
        "definitions": st["definitions"],
        "probability_laws": st["probability_laws"],
        "assumptions": st["assumptions"],
        "domain_constraints": st["domain_constraints"],
        "derived_facts": st["derived_facts"],
        "objective": st["objective"],
        "prohibited_assumptions": st["prohibited_assumptions"],
    }


def reconstruct_semantic_payload(structured_target: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the payload from the model-visible target **alone**.

    Reads no authored source, no reference encoding, no expected hash and no other task.
    If a field is absent the target was a summary, and reconstruction fails loudly rather
    than filling a default -- a silently defaulted field is how a model gets blamed for
    information it never had.
    """
    required = ("module", "family", "declarations", "definitions", "probability_laws",
                "assumptions", "domain_constraints", "derived_facts", "objective",
                "prohibited_assumptions")
    missing = [k for k in required if k not in structured_target]
    if missing:
        raise ReversibilityFailure(
            f"the structured target omits {missing}; it is a summary, not a complete "
            f"model-visible target")

    for i, d in enumerate(structured_target["declarations"]):
        for field in ("name", "kind", "type"):
            if field not in d:
                raise ReversibilityFailure(f"declaration {i} omits {field!r}")
        if d["kind"] in {"const", "obs"} and "value" not in d:
            raise ReversibilityFailure(
                f"declaration {d['name']!r} is {d['kind']} with no initialiser; an "
                f"encoder cannot invent one")
    for i, f in enumerate(structured_target["definitions"]):
        for field in ("name", "binders", "codomain", "body"):
            if field not in f or f[field] in (None, ""):
                raise ReversibilityFailure(f"definition {i} omits {field!r}")

    return {k: structured_target[k] for k in required}
