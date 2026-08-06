"""`CanonicalAcq0TaskV2` — one object, one truth, every artefact derived.

Why this exists
---------------
The v1 corpus kept mathematics in three places that were authored independently: a prose
paragraph, a `SemanticFacts(...)` **repr string**, and a private reference encoding. They
disagreed, and 41 of 41 tasks were inadmissible. In `assumption_boundary_000` the prose
said *"varrho of an argument equals 5 divided by that argument"* while the reference wrote
`eta / mu` with `eta = 5`; a frontier model followed the prose, produced a mathematically
identical function, and was scored FAIL. The instrument was wrong, not the model.

The fix is structural, not editorial: **one authority, everything else generated.**

Where the authority lives
-------------------------
**The canonical ACQ0 authority is the normalised compiler AST plus every validated semantic
metadata field.** Not the source text alone: metadata such as `derived_facts` and
`prohibited_assumptions` reaches model-visible prose, so it is part of what the task *means*
and must participate in identity. The earlier wording -- "the reference encoding is the
authority" -- was wrong, and the hardening audit found the consequence: two tasks with
different prohibited assumptions rendered different prose while sharing a canonical hash.

Two identities are therefore distinguished, and confusing them is the defect:

* :meth:`canonical_hash` -- the identity of the **encoding**. Derived from the compiled AST
  alone. This is what a model's output is scored against, and metadata must *not* enter it:
  a model is asked to encode mathematics, not to restate a prohibition.
* :meth:`semantic_identity` -- the identity of the **task**. AST hash plus every SEMANTIC
  metadata field. Two tasks sharing this are the same experiment; two tasks sharing only
  `canonical_hash` are not.

The structured target, prose, every surface rendering and the expected hash remain derived.
Nothing is hand-authored twice, so nothing can disagree.

This deliberately avoids inventing a second mathematical AST for evaluation. The compiler's
AST is the AST; a competing one would reintroduce exactly the divergence this replaces.

What is metadata rather than mathematics
----------------------------------------
Epistemic categorisation, derived-fact provenance, the objective and prohibited assumptions
are *about* the mathematics and cannot be read off the source alone, so they are carried
explicitly and validated against it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "SCHEMA_VERSION",
    "EpistemicCategory",
    "TaskFamily",
    "DerivedFact",
    "Objective",
    "Provenance",
    "CanonicalAcq0TaskV2",
    "SchemaViolation",
]

SCHEMA_VERSION = "acq0.v2.lossless"


class SchemaViolation(ValueError):
    """Raised at construction. An invalid task must not exist as an object."""


class EpistemicCategory(StrEnum):
    """Exactly one per proposition. The v1 corpus conflated these silently.

    `d != 0` beside `d > 4` was filed as an input premise although the bound entails it,
    so an encoder could not know whether restating it was required.
    """

    SUPPLIED_ASSUMPTION = "supplied_assumption"
    DOMAIN_CONSTRAINT = "domain_constraint"
    DERIVED_FACT = "derived_fact"
    PROOF_OBLIGATION = "proof_obligation"


class TaskFamily(StrEnum):
    BINDING_DEPENDENCY = "binding_dependency"
    ASSUMPTION_BOUNDARY = "assumption_boundary"
    IMPLICATION_VS_EQUIVALENCE = "implication_vs_equivalence"
    APPROXIMATION_VS_EQUALITY = "approximation_vs_equality"
    QUANTIFIER_SCOPE = "quantifier_scope"
    PROBABILITY_LAW_ROLE = "probability_law_role"
    DIMENSIONAL_ALGEBRA = "dimensional_algebra"
    TRANSFORMATION_SIDE_CONDITION = "transformation_side_condition"


@dataclass(frozen=True)
class DerivedFact:
    """A consequence, with what it follows from. Never a premise."""

    statement: str
    derived_from: tuple[str, ...]
    #: Whether the premise prose may mention it. Default false: a derived fact stated as a
    #: premise is the v1 defect.
    state_in_prose: bool = False

    def __post_init__(self) -> None:
        if not self.derived_from:
            raise SchemaViolation(
                f"derived fact {self.statement!r} names no premises; a fact that follows "
                f"from nothing is a premise, and must be declared as one"
            )


@dataclass(frozen=True)
class Objective:
    """A goal. `None` means no goal, and then no goal may be rendered anywhere.

    v1 posed a natural-language question while `objective=None`, so whether a `prove`
    statement belonged in the encoding was undetermined. A model added one; the reference
    had none; the hashes differed.
    """

    kind: str  # "prove" | "solve" | "infer" | "decide"
    statement: str

    def __post_init__(self) -> None:
        if self.kind not in {"prove", "solve", "infer", "decide"}:
            raise SchemaViolation(f"unsupported objective kind {self.kind!r}")
        if not self.statement.strip():
            raise SchemaViolation("an objective must state what is to be established")


@dataclass(frozen=True)
class Provenance:
    author: str
    created_utc: str
    generator: str = "hand-authored canonical v2"
    notes: str = ""


@dataclass(frozen=True)
class CanonicalAcq0TaskV2:
    """The sole mathematical authority for one ACQ0 task."""

    task_id: str
    family: TaskFamily
    #: THE authoritative mathematics. Everything else is derived from compiling this.
    source: str
    provenance: Provenance
    objective: Objective | None = None
    derived_facts: tuple[DerivedFact, ...] = ()
    prohibited_assumptions: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION
    notes: str = ""
    _compiled: Any = field(default=None, init=False, repr=False, compare=False)

    # -- construction-time invariants ------------------------------------------------

    def __post_init__(self) -> None:
        from hamiltonian_lang import compile_source
        from hamiltonian_lang.ast.nodes import (
            AssumeStmt,
            Declaration,
            DefineStmt,
            InferStmt,
            ProveStmt,
            SolveStmt,
        )

        if not self.task_id.strip():
            raise SchemaViolation("a task needs an id")

        result = compile_source(self.source, f"<{self.task_id}>")
        if not result.ok():
            codes = [d.code for d in result.diagnostics.errors]
            raise SchemaViolation(
                f"{self.task_id}: the authoritative source does not compile: {codes}"
            )
        object.__setattr__(self, "_compiled", result)

        goal_kinds = (ProveStmt, SolveStmt, InferStmt)
        goals = [s for s in result.module.statements if isinstance(s, goal_kinds)]

        for st in result.module.statements:
            # `const` without a value is unguessable -- the v1 `eta` defect.
            if isinstance(st, Declaration) and st.kind == "const" and st.value is None:
                raise SchemaViolation(
                    f"{self.task_id}: const {st.name!r} has no initialiser. Under current "
                    f"HML semantics a const requires one, and an encoder cannot invent it."
                )
            if isinstance(st, DefineStmt):
                if st.body is None:
                    raise SchemaViolation(
                        f"{self.task_id}: definition {st.name!r} has no body")
                for pname, ptype in st.params:
                    if ptype is None:
                        raise SchemaViolation(
                            f"{self.task_id}: binder {pname!r} of {st.name!r} is untyped")
                if st.params and st.declared_type is None:
                    raise SchemaViolation(
                        f"{self.task_id}: function {st.name!r} has no codomain")
                _reject_unguarded_partiality(self.task_id, st, result)

        # objective=None means no goal may exist, anywhere.
        if self.objective is None and goals:
            raise SchemaViolation(
                f"{self.task_id}: objective is None but the source contains "
                f"{len(goals)} goal statement(s). A goal that no objective declares "
                f"cannot be rendered consistently -- this is the v1 defect that let a "
                f"model add a `prove` the reference lacked."
            )
        if self.objective is not None and not goals:
            raise SchemaViolation(
                f"{self.task_id}: an objective is declared but the source states no goal")

        # A derived fact must not also be asserted as a premise.
        premises = {
            _render_expr(s.proposition) for s in result.module.statements
            if isinstance(s, AssumeStmt)
        }
        for fact in self.derived_facts:
            if fact.statement in premises:
                raise SchemaViolation(
                    f"{self.task_id}: {fact.statement!r} is declared derived and also "
                    f"asserted as an assumption; a fact belongs to exactly one category"
                )

    # -- derived artefacts ------------------------------------------------------------

    @property
    def module(self) -> Any:
        return self._compiled.module

    def canonical_hash(self) -> str:
        """The expected semantic identity. Alpha-invariant by construction."""
        from hamiltonian_lang import content_hash
        return content_hash(self.source)

    def reference_hml(self) -> str:
        """The reference encoding *is* the authority, not a copy of it."""
        return self.source

    def structured_target(self) -> dict[str, Any]:
        """The model-visible target, derived. Schema-validatable, never a repr string."""
        from hamiltonian_lang.ast.nodes import (
            AssumeStmt,
            Declaration,
            DefineStmt,
            LawStmt,
            RequireStmt,
        )
        decls, defs, laws, assumptions, constraints = [], [], [], [], []
        for st in self.module.statements:
            if isinstance(st, Declaration):
                entry = {"name": st.name, "kind": st.kind,
                         "type": st.declared_type.render() if st.declared_type else None}
                if st.value is not None:
                    entry["value"] = _render_expr(st.value)
                decls.append(entry)
            elif isinstance(st, DefineStmt):
                defs.append({
                    "name": st.name,
                    "binders": [{"name": n, "type": t.render() if t else None}
                                for n, t in st.params],
                    "codomain": st.declared_type.render() if st.declared_type else None,
                    "body": _render_expr(st.body),
                })
            elif isinstance(st, LawStmt):
                laws.append({
                    "role": st.role,
                    "target": st.target_symbol.name if st.target_symbol else None,
                    "given": [g.symbol_id.name for g in st.given if g.symbol_id],
                    "distribution": _render_expr(st.distribution),
                })
            elif isinstance(st, AssumeStmt):
                assumptions.append(_render_expr(st.proposition))
            elif isinstance(st, RequireStmt):
                constraints.append(_render_expr(st.proposition))
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "family": str(self.family),
            "module": self.module.name,
            "declarations": decls,
            "definitions": defs,
            "probability_laws": laws,
            "assumptions": assumptions,
            "domain_constraints": constraints,
            "derived_facts": [
                {"statement": f.statement, "derived_from": list(f.derived_from)}
                for f in self.derived_facts
            ],
            "objective": (None if self.objective is None
                          else {"kind": self.objective.kind,
                                "statement": self.objective.statement}),
            "prohibited_assumptions": list(self.prohibited_assumptions),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "schema_version": self.schema_version,
            "family": str(self.family),
            "source": self.source,
            "objective": (None if self.objective is None
                          else {"kind": self.objective.kind,
                                "statement": self.objective.statement}),
            "derived_facts": [
                {"statement": f.statement, "derived_from": list(f.derived_from),
                 "state_in_prose": f.state_in_prose} for f in self.derived_facts
            ],
            "prohibited_assumptions": list(self.prohibited_assumptions),
            "provenance": {
                "author": self.provenance.author,
                "created_utc": self.provenance.created_utc,
                "generator": self.provenance.generator,
                "notes": self.provenance.notes,
            },
            "canonical_hash": self.canonical_hash(),
            "semantic_identity": self.semantic_identity(),
            "content_digest": self.content_digest(),
            "notes": self.notes,
        }

    #: Every field, classified by what it can change. Audited and asserted by tests.
    #:
    #: SEMANTIC          -- changes task identity; must enter `semantic_identity`
    #: PRESENTATION_ONLY -- may change rendering, never mathematical identity
    #: OPERATIONAL_ONLY  -- provenance or execution only
    FIELD_CLASSIFICATION = {
        "source": "SEMANTIC",
        "objective": "SEMANTIC",
        "derived_facts": "SEMANTIC",          # reaches prose via state_in_prose
        "prohibited_assumptions": "SEMANTIC",  # reaches prose
        "family": "SEMANTIC",                  # selects the experiment cell
        "task_id": "OPERATIONAL_ONLY",
        "schema_version": "OPERATIONAL_ONLY",
        "provenance": "OPERATIONAL_ONLY",
        "notes": "OPERATIONAL_ONLY",
    }

    def semantic_identity(self) -> str:
        """Identity of the **task**: compiled AST plus every SEMANTIC metadata field.

        Distinct from :meth:`canonical_hash`, which identifies only the *encoding* and is
        what a model is scored against. Metadata must not enter that one -- a model encodes
        mathematics, and asking it to also encode a prohibition would change what ACQ0
        measures. But metadata must enter *this* one, or two materially different tasks
        compare equal. The hardening audit found exactly that: differing
        `prohibited_assumptions` rendered different prose under one canonical hash.
        """
        payload = json.dumps(
            {
                "ast": self.canonical_hash(),
                "family": str(self.family),
                "objective": None if self.objective is None else
                             [self.objective.kind, self.objective.statement],
                "derived_facts": sorted(
                    [f.statement, sorted(f.derived_from), f.state_in_prose]
                    for f in self.derived_facts
                ),
                "prohibited_assumptions": sorted(self.prohibited_assumptions),
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def content_digest(self) -> str:
        """Digest over the whole task record, not only its mathematics."""
        payload = json.dumps(
            {"source": self.source, "family": str(self.family),
             "objective": None if self.objective is None else
                          [self.objective.kind, self.objective.statement],
             "derived": [[f.statement, list(f.derived_from)] for f in self.derived_facts],
             "prohibited": list(self.prohibited_assumptions)},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


def _reject_unguarded_partiality(task_id: str, define: Any, compiled: Any) -> None:
    """A function declared total over a domain where its body is not total is rejected.

    Found by the hardening audit in this project's own proof corpus:
    `def varrho(mu : Real) : Real := eta / mu` declares totality over Real while being
    undefined at zero, and the obligation engine returns VERIFIED for it -- it generates no
    definedness obligation over a binder's declared domain at all.

    A task carrying that is not a valid instrument: a model could encode it faithfully, or
    could add a guard, and neither reading is wrong. The remedy is to narrow the binder
    type (`PositiveReal`) or state an explicit precondition -- **never** to have the
    corpus silently assume non-zeroness on the model's behalf.
    """
    from hamiltonian_lang.ast.nodes import BinOp

    binder_types = {n: t for n, t in define.params}

    def totality_gap(expr: Any, depth: int = 0) -> str | None:
        if expr is None or depth > 24:
            return None
        if isinstance(expr, BinOp) and expr.op == "/":
            name = getattr(expr.right, "name", None)
            if name in binder_types:
                declared = binder_types[name]
                kind = getattr(declared, "name", None) or (
                    declared.render() if declared is not None else None)
                if kind not in {"PositiveReal", "PositiveNatural"}:
                    return (f"divides by binder {name!r} declared {kind or declared}, "
                            f"which admits zero")
        for attr in ("left", "right", "operand", "body", "base"):
            gap = totality_gap(getattr(expr, attr, None), depth + 1)
            if gap:
                return gap
        for arg in getattr(expr, "args", ()) or ():
            gap = totality_gap(arg, depth + 1)
            if gap:
                return gap
        return None

    gap = totality_gap(define.body)
    if gap:
        raise SchemaViolation(
            f"{task_id}: definition {define.name!r} is declared total over its binder "
            f"domain but {gap}. Narrow the binder type or state an explicit precondition; "
            f"the corpus must not assume non-zeroness on the model's behalf."
        )


def _render_expr(expr: Any) -> str:
    """Surface text for an expression, via the HML backend -- never a Python repr."""
    if expr is None:
        return ""
    from hamiltonian_lang.backends.hml import render_expr
    return render_expr(expr)
