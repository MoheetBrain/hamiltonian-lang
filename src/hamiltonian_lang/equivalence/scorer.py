"""The layered scorer: Tier 0 to Tier 5, in order, stopping at the first decision.

What this replaces
------------------
``CanonicalComparatorVerifier`` is exact in one direction and silent in the other:
equal hashes mean the same object, but *unequal hashes are not wrongness*. Reading
a mismatch as a failure is correct for ACQ0, where reproducing the same canonical
object **is** the task, and wrong for H1/H2, where a mathematically equivalent
encoding that hashes differently is not a wrong answer. Scoring it ``DISPROVED``
would bias H1 and H2 downward -- against the project's own thesis. That is the
Lead's ruling in CONF-003, and this module is the prerequisite it names.

The order of work
-----------------
======  ====================================================================
TIER 0  exact canonical identity -- the existing content hash
GUARDS  invariant refutations: type, epistemic status, dimension, objective
        direction, conditioning set, quantifier alternation
TIER 1  alpha-equivalence and binder-safe normalisation
TIER 2  trusted algebraic and symbolic equivalence (SymPy, decision procedures)
TIER 3  executable counterexample search -- may refute, may never certify
TIER 4  endpoint-specific answer verification
TIER 5  unresolved: queued for human adjudication
======  ====================================================================

``UNSUPPORTED`` and ``INCONCLUSIVE`` are never converted into a failure. That is
the same error as the one being fixed, pointed the other way.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .. import CompileResult, compile_source
from ..ast.nodes import AssumeStmt, Expr, Module
from .adjudication import AdjudicationItem, AdjudicationQueue
from .endpoints import AnswerSpec, verify_answer
from .guards import run_guards
from .matching import Alignment, Residual, align, strict_match
from .search import search_disagreement
from .status import (
    EQUIVALENCE_PROTOCOL_VERSION,
    Assumption,
    Certificate,
    Endpoint,
    EquivalenceResult,
    EquivalenceStatus,
    Tier,
    TierOutcome,
)
from .symbolic import compare_expressions
from .sympy_bridge import SYMPY_AVAILABLE, TranslationContext, collect_declared_types

__all__ = ["ComparisonReport", "EquivalenceScorer"]

#: Normalisations Tier 1 applies. Recorded on every Tier 1 certificate rather than
#: left implicit, because each is a modelling decision a reader may want to audit.
_TIER1_ASSUMPTIONS: tuple[Assumption, ...] = (
    Assumption(
        "the spelling of a bound name is not part of the object's identity",
        "derived",
    ),
    Assumption(
        "a module is an unordered collection of statements, not a script",
        "derived",
    ),
    Assumption("the module's own name is a label, not mathematics", "derived"),
    Assumption(
        "+, *, and, or and iff are associative and commutative over the exact "
        "quantities this language denotes",
        "derived",
    ),
)


@dataclass(frozen=True)
class ComparisonReport:
    """Everything the scorer concluded, and the evidence for it."""

    status: EquivalenceStatus
    endpoint: Endpoint
    detail: str = ""
    outcomes: tuple[TierOutcome, ...] = ()
    assumptions: tuple[Assumption, ...] = ()
    alignment: dict[str, Any] = field(default_factory=dict)
    #: Whether the canonical content hashes are equal. This is ACQ0's endpoint and
    #: is reported separately from the equivalence verdict, never merged with it.
    exact_preservation: bool | None = None
    reference_compiles: bool = True
    candidate_compiles: bool = True
    diagnostics: tuple[str, ...] = ()
    answer: EquivalenceResult | None = None
    protocol_version: str = EQUIVALENCE_PROTOCOL_VERSION

    @property
    def decided_by(self) -> Tier | None:
        for outcome in self.outcomes:
            if outcome.result.decisive:
                return outcome.tier
        return None

    @property
    def is_negative(self) -> bool:
        return self.status in (
            EquivalenceStatus.VERIFIED_NONEQUIVALENT,
            EquivalenceStatus.COUNTEREXAMPLE_FOUND,
        )

    @property
    def is_positive(self) -> bool:
        return self.status in (
            EquivalenceStatus.VERIFIED_EQUIVALENT,
            EquivalenceStatus.VERIFIED_CORRECT_ANSWER,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": str(self.status),
            "endpoint": str(self.endpoint),
            "detail": self.detail,
            "decided_by": str(self.decided_by) if self.decided_by else None,
            "outcomes": [o.to_dict() for o in self.outcomes],
            "assumptions": [a.to_dict() for a in self.assumptions],
            "alignment": self.alignment,
            "exact_preservation": self.exact_preservation,
            "reference_compiles": self.reference_compiles,
            "candidate_compiles": self.candidate_compiles,
            "diagnostics": list(self.diagnostics),
            "answer": self.answer.to_dict() if self.answer else None,
            "protocol_version": self.protocol_version,
        }


class EquivalenceScorer:
    """Compare two HML encodings, or a candidate's answer, endpoint by endpoint."""

    version = EQUIVALENCE_PROTOCOL_VERSION

    def __init__(
        self,
        *,
        search_budget: int = 400,
        queue: AdjudicationQueue | None = None,
    ) -> None:
        self.search_budget = search_budget
        self.queue = queue if queue is not None else AdjudicationQueue()

    # -- public API --------------------------------------------------------

    def compare(
        self,
        reference: str,
        candidate: str,
        *,
        endpoint: Endpoint = Endpoint.ENCODING_EQUIVALENCE,
        answer_spec: AnswerSpec | None = None,
        candidate_answer: str | None = None,
        item_id: str = "",
    ) -> ComparisonReport:
        ref = compile_source(reference, "<reference>")
        cand = compile_source(candidate, "<candidate>")
        outcomes: list[TierOutcome] = []

        if not ref.ok():
            return self._no_reference(ref, endpoint, answer_spec, candidate_answer)

        if not cand.ok():
            codes = tuple(d.code for d in cand.diagnostics.errors)
            outcomes.append(
                TierOutcome(
                    Tier.TIER0_CANONICAL_IDENTITY,
                    EquivalenceResult(
                        Tier.TIER0_CANONICAL_IDENTITY,
                        EquivalenceStatus.UNSUPPORTED,
                        "the candidate does not compile, so it denotes no object to "
                        "compare; this is recorded, not scored as a wrong answer",
                        evidence={"codes": list(codes)},
                    ),
                )
            )
            answer = self._answer_tier(answer_spec, candidate_answer, outcomes)
            status = answer.status if answer is not None else EquivalenceStatus.UNSUPPORTED
            return self._finish(
                status,
                endpoint,
                outcomes,
                (),
                {},
                exact=False,
                candidate_compiles=False,
                diagnostics=codes,
                answer=answer,
                item_id=item_id,
                reference=reference,
                candidate=candidate,
                detail="the candidate does not compile",
            )

        # -- TIER 0 --------------------------------------------------------
        exact = ref.hash() == cand.hash()
        tier0 = (
            EquivalenceResult(
                Tier.TIER0_CANONICAL_IDENTITY,
                EquivalenceStatus.VERIFIED_EQUIVALENT,
                "identical alpha-invariant canonical content hash",
                certificate=Certificate(
                    "tier0.canonical_content_hash",
                    f"both sides canonicalise to {ref.hash()[:16]}",
                    witness={"content_hash": ref.hash()},
                ),
            )
            if exact
            else EquivalenceResult(
                Tier.TIER0_CANONICAL_IDENTITY,
                EquivalenceStatus.INCONCLUSIVE,
                "the canonical hashes differ. That means the two encodings are not the "
                "same object; it does not mean the candidate is mathematically wrong",
                evidence={"reference": ref.hash()[:16], "candidate": cand.hash()[:16]},
            )
        )
        outcomes.append(TierOutcome(Tier.TIER0_CANONICAL_IDENTITY, tier0))

        if exact:
            answer = self._answer_tier(answer_spec, candidate_answer, outcomes)
            return self._finish(
                EquivalenceStatus.VERIFIED_EQUIVALENT,
                endpoint,
                outcomes,
                (),
                {},
                exact=True,
                answer=answer,
                item_id=item_id,
                reference=reference,
                candidate=candidate,
                detail="exact canonical identity",
            )

        if endpoint is Endpoint.ACQ0_EXACT_PRESERVATION:
            # ACQ0 asks whether the *same object* came back. Nothing below Tier 0
            # answers that question, so the tiers below are not consulted, and the
            # honest verdict for a mismatch is "not the same object" -- reported
            # through `exact_preservation`, not as a claim of mathematical error.
            answer = self._answer_tier(answer_spec, candidate_answer, outcomes)
            return self._finish(
                EquivalenceStatus.INCONCLUSIVE,
                endpoint,
                outcomes,
                (),
                {},
                exact=False,
                answer=answer,
                item_id=item_id,
                reference=reference,
                candidate=candidate,
                detail=(
                    "under the ACQ0 endpoint only exact canonical identity counts as "
                    "preservation, and the hashes differ"
                ),
            )

        # -- TIER 1 --------------------------------------------------------
        env = strict_match(ref.module, cand.module)
        if env is not None:
            tier1 = EquivalenceResult(
                Tier.TIER1_ALPHA_NORMALISATION,
                EquivalenceStatus.VERIFIED_EQUIVALENT,
                "a binder bijection makes the two modules identical",
                certificate=Certificate(
                    "tier1.alpha_structural_match",
                    "the two modules are identical up to alpha-renaming, statement "
                    "order, and associative/commutative regrouping",
                    assumptions=_TIER1_ASSUMPTIONS,
                    witness={"symbol_map": env.names()},
                ),
                assumptions=_TIER1_ASSUMPTIONS,
            )
            outcomes.append(TierOutcome(Tier.TIER1_ALPHA_NORMALISATION, tier1))
            answer = self._answer_tier(answer_spec, candidate_answer, outcomes)
            return self._finish(
                EquivalenceStatus.VERIFIED_EQUIVALENT,
                endpoint,
                outcomes,
                _TIER1_ASSUMPTIONS,
                {"symbol_map": env.names()},
                exact=False,
                answer=answer,
                item_id=item_id,
                reference=reference,
                candidate=candidate,
                detail="alpha-equivalent after binder-safe normalisation",
            )
        outcomes.append(
            TierOutcome(
                Tier.TIER1_ALPHA_NORMALISATION,
                EquivalenceResult(
                    Tier.TIER1_ALPHA_NORMALISATION,
                    EquivalenceStatus.INCONCLUSIVE,
                    "no binder bijection makes the modules identical; the difference is "
                    "structural, which is not yet a mathematical difference",
                ),
            )
        )

        alignment = align(ref.module, cand.module)
        ctx = self._context(ref, cand, alignment)

        # -- GUARDS --------------------------------------------------------
        for verdict in run_guards(alignment, ctx):
            outcomes.append(TierOutcome(Tier.GUARD, verdict))
            answer = self._answer_tier(answer_spec, candidate_answer, outcomes)
            return self._finish(
                verdict.status,
                endpoint,
                outcomes,
                verdict.assumptions,
                alignment.to_dict(),
                exact=False,
                answer=answer,
                item_id=item_id,
                reference=reference,
                candidate=candidate,
                detail=verdict.detail,
            )

        # -- TIER 2 and TIER 3 ---------------------------------------------
        status, detail, assumptions = self._discharge_residuals(
            alignment, ctx, ref.module, outcomes
        )

        answer = self._answer_tier(answer_spec, candidate_answer, outcomes)
        if endpoint is Endpoint.FINAL_ANSWER and answer is not None and answer.decisive:
            status, detail = answer.status, answer.detail

        return self._finish(
            status,
            endpoint,
            outcomes,
            assumptions,
            alignment.to_dict(),
            exact=False,
            answer=answer,
            item_id=item_id,
            reference=reference,
            candidate=candidate,
            detail=detail,
        )

    # -- internals ---------------------------------------------------------

    def _context(
        self, ref: CompileResult, cand: CompileResult, alignment: Alignment
    ) -> TranslationContext:
        return TranslationContext(
            left_types=collect_declared_types(ref.module),
            right_types=collect_declared_types(cand.module),
            pairing=dict(alignment.env.bwd),
        )

    def _constraints(self, module: Module, ctx: TranslationContext) -> list[Any]:
        """``assume`` propositions, used to discard inadmissible samples.

        ``require`` is deliberately excluded: it is an obligation the model must
        discharge, not a restriction on the domain, and using it to filter samples
        would let a candidate's own constraint hide its counterexample.
        """
        out: list[Any] = []
        for st in module.statements:
            if isinstance(st, AssumeStmt) and st.proposition is not None:
                translated = ctx.translate(st.proposition, "left")
                if translated.expr is not None:
                    out.append(translated.expr)
        return out

    def _discharge_residuals(
        self,
        alignment: Alignment,
        ctx: TranslationContext,
        reference_module: Module,
        outcomes: list[TierOutcome],
    ) -> tuple[EquivalenceStatus, str, tuple[Assumption, ...]]:
        if not alignment.complete:
            result = EquivalenceResult(
                Tier.TIER2_SYMBOLIC,
                EquivalenceStatus.INCONCLUSIVE,
                f"{len(alignment.unpaired_left)} reference and "
                f"{len(alignment.unpaired_right)} candidate statement(s) could not be "
                f"paired at all, so no correspondence exists to reason over",
            )
            outcomes.append(TierOutcome(Tier.TIER2_SYMBOLIC, result))
            return result.status, result.detail, ()

        structural = [r for r in alignment.residuals if r.kind != "expression"]
        if structural:
            kinds = sorted({r.kind for r in structural})
            result = EquivalenceResult(
                Tier.TIER2_SYMBOLIC,
                EquivalenceStatus.INCONCLUSIVE,
                f"the modules differ in {', '.join(kinds)}, which no guard classified "
                f"as a semantic difference and no symbolic method can discharge",
                evidence={"residuals": [r.describe() for r in structural]},
            )
            outcomes.append(TierOutcome(Tier.TIER2_SYMBOLIC, result))
            return result.status, result.detail, ()

        residuals = list(alignment.residuals)
        if not residuals:
            result = EquivalenceResult(
                Tier.TIER2_SYMBOLIC,
                EquivalenceStatus.INCONCLUSIVE,
                "the statements paired with no residual difference, yet Tier 1 found no "
                "bijection. The alignment is weaker than a proof and does not certify",
            )
            outcomes.append(TierOutcome(Tier.TIER2_SYMBOLIC, result))
            return result.status, result.detail, ()

        assumptions: list[Assumption] = []
        undecided: list[Residual] = []
        losses: list[Any] = []
        for residual in residuals:
            verdict = compare_expressions(
                residual.left if isinstance(residual.left, Expr) else None,
                residual.right if isinstance(residual.right, Expr) else None,
                ctx,
                binder_types_left={s: t for s, _, t in residual.binders},
                binder_types_right={s: t for _, s, t in residual.binders},
            )
            outcomes.append(TierOutcome(Tier.TIER2_SYMBOLIC, verdict))
            if verdict.status is EquivalenceStatus.VERIFIED_NONEQUIVALENT:
                # A negative on a *fragment* does not carry to the whole: two
                # expressions can differ everywhere and agree overall.
                if residual.may_refute:
                    return verdict.status, verdict.detail, verdict.assumptions
                undecided.append(residual)
                continue
            if verdict.status is EquivalenceStatus.VERIFIED_EQUIVALENT:
                assumptions.extend(verdict.assumptions)
                continue
            if verdict.status is EquivalenceStatus.SEMANTIC_LOSS:
                losses.extend(verdict.semantic_loss)
            undecided.append(residual)

        if not undecided:
            combined = tuple(dict.fromkeys(assumptions))
            certificate = Certificate(
                "tier2.sympy_difference_is_zero",
                f"every one of the {len(residuals)} residual difference(s) was "
                f"discharged symbolically, and everything else matched structurally",
                assumptions=combined,
            )
            result = EquivalenceResult(
                Tier.TIER2_SYMBOLIC,
                EquivalenceStatus.VERIFIED_EQUIVALENT,
                "all residual differences discharged symbolically",
                certificate=certificate,
                assumptions=combined,
            )
            outcomes.append(TierOutcome(Tier.TIER2_SYMBOLIC, result))
            return result.status, result.detail, combined + _TIER1_ASSUMPTIONS

        # -- TIER 3 --------------------------------------------------------
        # Only whole statement-level expressions are searched. A counterexample
        # inside a fragment says nothing about the expression that contains it.
        constraints = self._constraints(reference_module, ctx)
        for residual in (r for r in undecided if r.may_refute):
            found = self._search(residual, ctx, constraints)
            outcomes.append(TierOutcome(Tier.TIER3_COUNTEREXAMPLE_SEARCH, found))
            if found.status is EquivalenceStatus.COUNTEREXAMPLE_FOUND:
                return found.status, found.detail, ()

        if losses:
            return (
                EquivalenceStatus.SEMANTIC_LOSS,
                "the residual differences could not be translated into any checking "
                "medium without loss, so no verdict is issued",
                (),
            )
        return (
            EquivalenceStatus.INCONCLUSIVE,
            f"{len(undecided)} residual difference(s) were neither discharged "
            f"symbolically nor refuted by a counterexample. No verdict is issued: an "
            f"undecided comparison is not a wrong answer",
            (),
        )

    def _search(
        self, residual: Residual, ctx: TranslationContext, constraints: Sequence[Any]
    ) -> EquivalenceResult:
        if not SYMPY_AVAILABLE:  # pragma: no cover
            return EquivalenceResult(
                Tier.TIER3_COUNTEREXAMPLE_SEARCH,
                EquivalenceStatus.UNSUPPORTED,
                "sympy is not importable in this environment",
            )
        left = ctx.translate(
            residual.left if isinstance(residual.left, Expr) else None,
            "left",
            binder_types={s: t for s, _, t in residual.binders},
        )
        right = ctx.translate(
            residual.right if isinstance(residual.right, Expr) else None,
            "right",
            binder_types={s: t for _, s, t in residual.binders},
        )
        if left.expr is None or right.expr is None:
            return EquivalenceResult(
                Tier.TIER3_COUNTEREXAMPLE_SEARCH,
                EquivalenceStatus.SEMANTIC_LOSS,
                "the residual could not be made executable, so no value could be tried",
                semantic_loss=left.losses + right.losses,
            )
        free = left.expr.free_symbols | right.expr.free_symbols
        table = {n: s for n, s in ctx.symbol_table().items() if s in free}
        outcome = search_disagreement(
            left.expr,
            right.expr,
            table,
            ctx.symbol_types(),
            constraints=[c for c in constraints if c.free_symbols <= free],
            budget=self.search_budget,
            label=residual.path,
        )
        if isinstance(outcome, Exception):  # pragma: no cover - defensive
            raise outcome
        if hasattr(outcome, "assignment"):
            return EquivalenceResult(
                Tier.TIER3_COUNTEREXAMPLE_SEARCH,
                EquivalenceStatus.COUNTEREXAMPLE_FOUND,
                "a value admitted by the declared types and the stated assumptions "
                "makes the two sides disagree",
                counterexample=outcome,  # type: ignore[arg-type]
            )
        return EquivalenceResult(
            Tier.TIER3_COUNTEREXAMPLE_SEARCH,
            EquivalenceStatus.INCONCLUSIVE,
            "no disagreement was found. That is not evidence of equivalence: this tier "
            "can refute and can never certify",
            no_refutation=outcome,  # type: ignore[arg-type]
        )

    def _answer_tier(
        self,
        spec: AnswerSpec | None,
        candidate_answer: str | None,
        outcomes: list[TierOutcome],
    ) -> EquivalenceResult | None:
        if spec is None:
            return None
        result = verify_answer(spec, candidate_answer)
        outcomes.append(TierOutcome(Tier.TIER4_ENDPOINT_ANSWER, result))
        return result

    def _no_reference(
        self,
        ref: CompileResult,
        endpoint: Endpoint,
        spec: AnswerSpec | None,
        candidate_answer: str | None,
    ) -> ComparisonReport:
        outcomes: list[TierOutcome] = [
            TierOutcome(
                Tier.TIER0_CANONICAL_IDENTITY,
                EquivalenceResult(
                    Tier.TIER0_CANONICAL_IDENTITY,
                    EquivalenceStatus.UNSUPPORTED,
                    "the reference does not compile, so there is nothing to compare "
                    "against; this says nothing about the candidate",
                    evidence={"codes": [d.code for d in ref.diagnostics.errors]},
                ),
            )
        ]
        answer = self._answer_tier(spec, candidate_answer, outcomes)
        return ComparisonReport(
            status=answer.status if answer is not None else EquivalenceStatus.UNSUPPORTED,
            endpoint=endpoint,
            detail="the reference does not compile",
            outcomes=tuple(outcomes),
            reference_compiles=False,
            diagnostics=tuple(d.code for d in ref.diagnostics.errors),
            answer=answer,
        )

    def _finish(
        self,
        status: EquivalenceStatus,
        endpoint: Endpoint,
        outcomes: list[TierOutcome],
        assumptions: Sequence[Assumption],
        alignment: dict[str, Any],
        *,
        exact: bool | None,
        answer: EquivalenceResult | None = None,
        candidate_compiles: bool = True,
        diagnostics: tuple[str, ...] = (),
        item_id: str = "",
        reference: str = "",
        candidate: str = "",
        detail: str = "",
    ) -> ComparisonReport:
        report = ComparisonReport(
            status=status,
            endpoint=endpoint,
            detail=detail,
            outcomes=tuple(outcomes),
            assumptions=tuple(dict.fromkeys(assumptions)),
            alignment=alignment,
            exact_preservation=exact,
            candidate_compiles=candidate_compiles,
            diagnostics=diagnostics,
            answer=answer,
        )
        if status in (EquivalenceStatus.INCONCLUSIVE, EquivalenceStatus.SEMANTIC_LOSS):
            self.queue.add(
                AdjudicationItem(
                    item_id=item_id or f"pair-{len(self.queue) + 1}",
                    status=status,
                    reason=detail or "no tier decided this pair",
                    reference=reference,
                    candidate=candidate,
                    residuals=tuple(alignment.get("residuals", ())),
                    tiers_tried=tuple(str(o.tier) for o in outcomes),
                )
            )
        return report
