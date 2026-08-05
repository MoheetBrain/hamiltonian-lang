"""The Repair Teacher — the role that diagnoses, and is forbidden from answering.

Role separation is the mechanism
--------------------------------
The Teacher receives the broken output, the structured diagnostic, the retrieved project
context and the verified prefix. It returns the cause and a plan. It does **not** return
the corrected program and it does **not** return the final mathematical answer.

That separation is INTERVENOR's fix for Degeneration-of-Thought: the model that produced
the broken output is trapped in the interpretation that produced it, and asking it to
"try again" re-derives the same error. A second role, reasoning from the diagnostic rather
than from the original intent, breaks the loop.

The shipped Teacher makes no model call
---------------------------------------
:class:`DeterministicRepairTeacher` is a pure function of (diagnostic, context). It exists
for three reasons: it is the control against which a model-based Teacher must be compared;
it makes the entire chain testable offline with no sampling variance; and — the COCOGEN
point — for the five hard-coded diagnostic mappings there is exactly one right plan, so
spending a model call on them would buy nothing but variance.

Where the invariant comes from, and what happens when there is none
-------------------------------------------------------------------
``failing_invariant`` is taken, in order, from the compiler's own invariant table, then a
retrieved context item, then the class-level rule in :data:`CLASS_INVARIANT`. The source
is recorded on the plan. When none of the three applies the Teacher returns
:class:`~.plan.NoPlan` — it never composes a plausible-sounding invariant, because a
fabricated rule in a repair packet is indistinguishable from a true one and would enter
the training record as fact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..context_broker import (
    ContextQuery,
    ContextStatus,
    DiagnosticContextBroker,
    ErrorClass,
    FacetKind,
    RetrievedContext,
)
from ..improvement.diagnostics import StructuredDiagnostic
from .plan import NoPlan, RepairPlan, assert_plan_non_leaking

__all__ = [
    "TEACHER_VERSION",
    "CLASS_INVARIANT",
    "CLASS_SEMANTIC_CATEGORY",
    "CLASS_REPAIR_STEPS",
    "UNIVERSAL_PRESERVATION",
    "TeachResult",
    "RepairTeacher",
    "DeterministicRepairTeacher",
    "numerals_in",
]

TEACHER_VERSION = "hml-repair-teacher-1.0.0"

#: The rule each error class violates, stated at class level. Each entry restates a rule
#: the compiler actually enforces; the comment names where. These are fallbacks — a
#: code-specific invariant from ``VIOLATED_INVARIANT_BY_CODE`` always wins.
CLASS_INVARIANT: dict[ErrorClass, str] = {
    # parser/lexer: hamiltonian_lang/parser/__init__.py
    ErrorClass.SYNTAX: (
        "the input must be a well-formed Hamiltonian Lang module before any meaning is "
        "assigned to it"
    ),
    # semantics/__init__.py::Resolver.reference / visit_expr
    ErrorClass.RESOLUTION: (
        "every name and every callee must resolve to something declared in this module "
        "or built in to the language"
    ),
    # type_system/__init__.py::CallableSignature
    ErrorClass.ARITY: (
        "a call must supply exactly as many arguments as the callee declares parameters; "
        "arity is part of the signature"
    ),
    # type_system/__init__.py::TypeChecker._validate_type
    ErrorClass.TYPE: (
        "every annotation must name a type the checker knows, and every expression must "
        "be used in a position that accepts its kind"
    ),
    # types.py::is_subtype — refinement obligations run upward only
    ErrorClass.REFINEMENT: (
        "a value must inhabit the refinement type demanded at the position where it is "
        "supplied; subtyping runs upward only and there is no implicit narrowing"
    ),
    # type_system/distributions.py::DistributionSpec.roles
    ErrorClass.ROLE: (
        "every distribution argument must carry a role label drawn from that family's own "
        "declared role set, and every required role must be supplied"
    ),
    # semantics/__init__.py::Scope
    ErrorClass.SCOPE: (
        "a name is bound at most once per scope and must be visible at its use site"
    ),
    # types.py::dimension_of and the D5xx family
    ErrorClass.DIMENSION: (
        "operands of an additive operator or a comparison must have equal physical "
        "dimension"
    ),
    # v1/epistemic.py::PROHIBITED_COERCIONS
    ErrorClass.EPISTEMIC: (
        "a claim's grounds must be the grounds the position requires; the justification "
        "kinds are not an ordered chain and admit no coercion between them"
    ),
    # type_system/__init__.py::ProofObligation
    ErrorClass.OBLIGATION: (
        "an obligation is discharged only by grounds that can discharge it; asserting it "
        "more strongly does not discharge it"
    ),
    # backends/canonical.py — the canonical form is the semantic contract
    ErrorClass.SEMANTIC_EQUIVALENCE: (
        "the program must denote the target semantic object, not merely compile"
    ),
    # backends/base.py::Backend.drop/approximate/weaken
    ErrorClass.BACKEND: (
        "a backend must report every construct it cannot express; silent omission "
        "produces authoritative-looking output that is wrong"
    ),
}

#: The *kind* of thing that belongs at the failing span. A category, never a value — that
#: distinction is what keeps the plan from being the answer.
CLASS_SEMANTIC_CATEGORY: dict[ErrorClass, str] = {
    ErrorClass.SYNTAX: "a syntactically complete statement of the intended form",
    ErrorClass.RESOLUTION: "a name that is declared in this module or built in",
    ErrorClass.ARITY: "an argument list of the callee's declared length",
    ErrorClass.TYPE: "a type drawn from the checker's vocabulary or declared as a concept",
    ErrorClass.REFINEMENT: "a value inhabiting the refinement type demanded here",
    ErrorClass.ROLE: "a role label from this distribution family's declared role set",
    ErrorClass.SCOPE: "a binding that is unique in its scope and visible at the use site",
    ErrorClass.DIMENSION: "an operand carrying the same physical dimension as its partner",
    ErrorClass.EPISTEMIC: "a claim whose grounds match what this position requires",
    ErrorClass.OBLIGATION: "grounds capable of discharging the stated obligation",
    ErrorClass.SEMANTIC_EQUIVALENCE: (
        "a construct denoting the same object as the target, not merely one that compiles"
    ),
    ErrorClass.BACKEND: "a construct the target backend can express, or a recorded loss",
}

#: Steps per class. Imperatives about *what kind of edit*, with no value ever supplied.
CLASS_REPAIR_STEPS: dict[ErrorClass, tuple[str, ...]] = {
    ErrorClass.SYNTAX: (
        "Re-read the statement at the span and identify which token the grammar expected.",
        "Rewrite that one statement in well-formed syntax, changing nothing else.",
    ),
    ErrorClass.RESOLUTION: (
        "Decide whether the name was misspelled or genuinely never declared.",
        "If misspelled, correct the spelling at the use site only.",
        "If undeclared, add a declaration before first use, or call a built-in instead.",
    ),
    ErrorClass.ARITY: (
        "Read the callee's declared parameter list from the signature above.",
        "Add the missing arguments, or remove the surplus ones, at the call site only.",
        "Do not change the definition to match the call.",
    ),
    ErrorClass.TYPE: (
        "Compare the annotation against the type vocabulary above.",
        "Replace it with the intended type, or declare a concept of that name.",
    ),
    ErrorClass.REFINEMENT: (
        "Identify which argument position failed and what refinement it demands.",
        "Supply an expression that provably inhabits that refinement at that position.",
        "Do not widen the declared parameter type to admit the current argument.",
    ),
    ErrorClass.ROLE: (
        "Look up this family's declared roles above.",
        "Rename the offending label to the canonical role for the quantity you meant.",
        "Check that the value you pass still means what that role demands.",
    ),
    ErrorClass.SCOPE: (
        "Determine which binding the use site should see.",
        "Rename one of the two bindings, or move the declaration into the right scope.",
    ),
    ErrorClass.DIMENSION: (
        "Compute the dimension of each operand.",
        "Convert or re-annotate one operand so both carry the same dimension.",
        "Do not drop a dimension annotation to make the check pass.",
    ),
    ErrorClass.EPISTEMIC: (
        "Identify the grounds this position requires and the grounds actually offered.",
        "Either supply grounds of the required kind, or weaken the claim to match.",
        "Do not coerce between justification kinds; no coercion exists.",
    ),
    ErrorClass.OBLIGATION: (
        "Name the obligation that is open.",
        "Discharge it with grounds that can discharge it, or record it as open.",
    ),
    ErrorClass.SEMANTIC_EQUIVALENCE: (
        "State, in one sentence, what the construct currently denotes.",
        "State what the target denotes, and edit the construct until the two agree.",
    ),
    ErrorClass.BACKEND: (
        "Identify the construct the backend cannot express.",
        "Express it another way, or record the loss explicitly.",
    ),
}

#: Attached to every plan. These are the ways a repair can pass the checker while
#: destroying the thing being measured, and each has been observed in generated code.
UNIVERSAL_PRESERVATION: tuple[str, ...] = (
    "Do not delete the failing construct. Removing it satisfies the checker and changes "
    "what the program means.",
    "Do not weaken a declared type, a refinement or a check to make the error go away. "
    "Rejection is the product; a repair that disables the rejection has repaired nothing.",
    "Change only what the diagnostic names. Every other statement must survive byte for "
    "byte.",
)

_NUMERAL = re.compile(r"(?<![A-Za-z0-9_.])-?\d+(?:\.\d+)?(?![A-Za-z0-9_])")


def numerals_in(*texts: str) -> tuple[str, ...]:
    """Every numeral appearing in ``texts``. The whitelist for the novel-numeral check."""
    out: set[str] = set()
    for t in texts:
        if t:
            out.update(m.group(0) for m in _NUMERAL.finditer(t))
    return tuple(sorted(out))


#: What a Teacher hands back: a plan, or a recorded refusal to produce one.
TeachResult = RepairPlan | NoPlan


@runtime_checkable
class RepairTeacher(Protocol):
    """The Teacher role. Any implementation must honour the non-leaking contract."""

    name: str
    #: True if this Teacher contacts a model or a network. The chain driver refuses live
    #: components unless explicitly allowed, so an offline suite cannot drift online.
    live: bool

    def teach(
        self,
        *,
        broken_output: str,
        diagnostic: StructuredDiagnostic,
        context: RetrievedContext,
        verified_prefix: str = "",
        forbid_novel_numerals: bool = False,
    ) -> TeachResult: ...


@dataclass
class DeterministicRepairTeacher:
    """A Teacher that is a pure function of the diagnostic and the retrieved context."""

    name: str = "deterministic"
    live: bool = False
    broker: DiagnosticContextBroker = field(default_factory=DiagnosticContextBroker)
    version: str = TEACHER_VERSION

    # -- convenience -------------------------------------------------------------

    def diagnose(
        self,
        *,
        broken_output: str,
        diagnostic: StructuredDiagnostic,
        verified_prefix: str = "",
        forbid_novel_numerals: bool = False,
        max_items: int = 6,
    ) -> tuple[RetrievedContext, TeachResult]:
        """Retrieve context for ``diagnostic`` and teach from it, in one call."""
        context = self.broker.retrieve(
            ContextQuery(
                diagnostic=diagnostic, source=broken_output, max_items=max_items
            )
        )
        result = self.teach(
            broken_output=broken_output,
            diagnostic=diagnostic,
            context=context,
            verified_prefix=verified_prefix,
            forbid_novel_numerals=forbid_novel_numerals,
        )
        return context, result

    # -- the role ----------------------------------------------------------------

    def teach(
        self,
        *,
        broken_output: str,
        diagnostic: StructuredDiagnostic,
        context: RetrievedContext,
        verified_prefix: str = "",
        forbid_novel_numerals: bool = False,
    ) -> TeachResult:
        error_class = context.error_class
        if error_class is None:
            return NoPlan(
                reason=(
                    f"{diagnostic.code} has no error class in the repair taxonomy "
                    f"({context.status}); no plan can be stated without inventing the "
                    "rule that was broken"
                ),
                context_status=context.status,
            )

        invariant, invariant_source = self._invariant(diagnostic, context, error_class)
        if invariant is None:
            return NoPlan(
                reason=(
                    f"no invariant is recorded for {diagnostic.code} and retrieval "
                    f"returned {context.status}; the Teacher does not compose one"
                ),
                error_class=error_class,
                context_status=context.status,
            )

        plan = RepairPlan(
            failing_invariant=invariant,
            cause=self._cause(diagnostic, error_class),
            source_span=diagnostic.source_span,
            expected_semantic_category=self._category(diagnostic, error_class),
            repair_steps=self._steps(diagnostic, context, error_class),
            preservation_constraints=self._preservation(context),
            error_class=error_class,
            context_status=context.status,
            context_provenance=context.provenance(),
            diagnostic_code=diagnostic.code,
            invariant_source=invariant_source,
        )

        known = numerals_in(
            broken_output,
            verified_prefix,
            diagnostic.render(),
            *(i.content for i in context.items),
        )
        return assert_plan_non_leaking(
            plan,
            known_numerals=known,
            forbid_novel_numerals=forbid_novel_numerals,
        )

    # -- field construction ------------------------------------------------------

    def _invariant(
        self,
        diagnostic: StructuredDiagnostic,
        context: RetrievedContext,
        error_class: ErrorClass,
    ) -> tuple[str | None, str]:
        if diagnostic.violated_invariant:
            return diagnostic.violated_invariant, "compiler_invariant_table"
        for item in context.items:
            if item.facet is FacetKind.DIAGNOSTIC_CODE and item.key == diagnostic.code:
                return item.content, item.provenance.render()
        rule = CLASS_INVARIANT.get(error_class)
        if rule is not None:
            return rule, f"class_invariant:{error_class}"
        return None, ""

    def _cause(
        self, diagnostic: StructuredDiagnostic, error_class: ErrorClass
    ) -> str:
        """Why *this* construct breaks the invariant. Built from the compiler's own words.

        ``found``/``expected`` are the compiler's structured statement of the mismatch, so
        quoting them is a restatement of the diagnostic, never an inference beyond it.
        """
        parts = [diagnostic.message.strip() or f"{diagnostic.code} was reported"]
        if diagnostic.actual is not None and diagnostic.expected is not None:
            parts.append(
                f"the position supplied {diagnostic.actual} where {diagnostic.expected} "
                "is required"
            )
        elif diagnostic.actual is not None:
            parts.append(f"the offending item is {diagnostic.actual}")
        elif diagnostic.expected is not None:
            parts.append(f"the position requires {diagnostic.expected}")
        for note in diagnostic.notes[:2]:
            if note.strip():
                parts.append(note.strip())
        return f"[{error_class}] " + "; ".join(parts)

    def _category(
        self, diagnostic: StructuredDiagnostic, error_class: ErrorClass
    ) -> str:
        base = CLASS_SEMANTIC_CATEGORY[error_class]
        if error_class in (ErrorClass.REFINEMENT, ErrorClass.TYPE) and diagnostic.expected:
            return f"{base} — here, {diagnostic.expected}"
        return base

    def _steps(
        self,
        diagnostic: StructuredDiagnostic,
        context: RetrievedContext,
        error_class: ErrorClass,
    ) -> tuple[str, ...]:
        steps = list(CLASS_REPAIR_STEPS[error_class])
        if context.status is ContextStatus.NO_RELEVANT_CONTEXT:
            # Stated, not hidden. A Learner told that nothing was retrieved will not
            # invent a rule to satisfy a plan that implied one existed.
            steps.append(
                "No project-specific rule was retrievable for this code. Work from the "
                "diagnostic alone and do not assume a rule that was not shown to you."
            )
        return tuple(steps)

    def _preservation(self, context: RetrievedContext) -> tuple[str, ...]:
        out = list(UNIVERSAL_PRESERVATION)
        for item in context.items:
            if item.facet is FacetKind.CONSTITUTIONAL_INVARIANT:
                out.append(f"Constitutional: {item.content}")
        return tuple(out)
