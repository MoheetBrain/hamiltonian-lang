"""The registered trusted checkers.

Three, deliberately. Each one wraps capability that **already exists in this tree** and
adds only the discipline needed to turn a computation into evidence: recompute rather than
trust, name what was established, and fail closed outside the supported fragment.

None of them contains mathematics. ``closed_eval_v1`` and ``definition_unfold_v1`` delegate
to :mod:`hamiltonian_lang.verification.obligations.evaluate`, which was already exact,
already unfolded definitions, and already refused what it could not decide;
``propositional_underdetermination_v1`` uses the same evaluator as a model checker. There
is no arithmetic rewrite catalogue here, no ``x - 0 -> x``, no special case for ``f(3)``,
and nothing that knows what Gold-10 contains.

What is deliberately absent
---------------------------
``equivalence/symbolic.py`` is **not** registered. Its own docstring is explicit that
``simplify(a - b) == 0`` certifies equality and that propositional validity is decided by
``satisfiable(...)``, and HML performs no independent replay of either — the verdict rests
on a raw SymPy success flag. That makes it ``UNTRUSTED_ORACLE``, not a trusted checker,
regardless of the module using the word "certificate". See SPEC §2.7 for the full decision
and its consequence for Gold-10 G07.
"""

from __future__ import annotations

from fractions import Fraction

from ...ast.nodes import Call, Comparison, Expr, Literal, LogicalOp, Ref, UnaryOp, walk
from ...verification.obligations.evaluate import Undecidable, evaluate, free_names
from . import (
    CertificateEnvelope,
    CheckerContext,
    CheckerVerdict,
    JudgementKind,
    TrustedChecker,
    _register,
)

__all__ = ["extract_model"]


def _reject(reason: str) -> CheckerVerdict:
    return CheckerVerdict(False, reason)


def _definitions_used(expr: Expr, env) -> set[str]:
    """Names of user definitions and functions this expression depends on, transitively.

    Computed structurally rather than by instrumenting the evaluator, so the dependency
    record is a property of the claim rather than of one execution. Bounded by the set of
    declared names, so it terminates even on a cyclic definition (which the evaluator
    refuses separately).
    """
    found: set[str] = set()
    pending = [expr]
    while pending:
        node = pending.pop()
        for sub in walk(node):
            name = None
            if isinstance(sub, Ref):
                name = sub.name if sub.name in env.definitions else None
            elif isinstance(sub, Call):
                name = sub.callee if sub.callee in env.functions else None
            if name is not None and name not in found:
                found.add(name)
                body = (env.definitions.get(name) or env.functions.get(name)).body
                if body is not None:
                    pending.append(body)
    return found


# ---------------------------------------------------------------------------
# 1. closed_eval_v1 -- exact evaluation of a closed proposition
# ---------------------------------------------------------------------------


def _closed_eval(envelope: CertificateEnvelope, ctx: CheckerContext) -> CheckerVerdict:
    """Recompute the claim exactly. The payload is never trusted for the answer.

    A payload asserting ``result = 3`` would be worthless — the whole point is that the
    checker derives the truth of the claim itself, from the claim itself. So this takes no
    payload at all beyond what the envelope carries.
    """
    claim = ctx.payload.get("__claim__")
    env = ctx.environment
    if claim is None or env is None:
        return _reject("closed_eval_v1 requires a claim and an environment")

    used = _definitions_used(claim, env)
    if used:
        return _reject(
            f"the claim depends on definition(s) {', '.join(sorted(used))}; "
            f"use definition_unfold_v1, which records them as dependencies"
        )
    free = free_names(claim, env)
    if free:
        return _reject(
            f"the claim is not closed: {', '.join(sorted(free))} "
            f"{'is' if len(free) == 1 else 'are'} free"
        )
    try:
        value = evaluate(claim, env)
    except Undecidable as exc:
        # Outside the fragment. UNKNOWN, and emphatically not a licence to conclude
        # anything about the claim.
        return _reject(f"outside the exactly-evaluable fragment: {exc}")
    if not value.exact:
        return _reject(
            "the evaluation was inexact; a float result can refute a claim by a wide "
            "margin but can never establish an equality"
        )
    try:
        truth = value.as_bool()
    except Undecidable as exc:
        return _reject(f"the claim is not a proposition: {exc}")
    if not truth:
        return _reject("the claim evaluates to false")
    return CheckerVerdict(True, "exact evaluation", established=claim)


_register(
    TrustedChecker(
        name="closed_eval_v1",
        judgements=frozenset({JudgementKind.ENTAILS}),
        validate=_closed_eval,
        trust=(
            "hamiltonian_lang.verification.obligations.evaluate, an HML-owned exact "
            "rational evaluator. No external CAS or solver participates. Floats are "
            "rejected rather than rounded."
        ),
        fragment="closed propositions over exact rationals; no free names, no definitions",
        doc="Recomputes a closed proposition exactly and requires it to be true.",
    )
)


# ---------------------------------------------------------------------------
# 2. definition_unfold_v1 -- replayed unfolding, with its dependencies recorded
# ---------------------------------------------------------------------------


def _definition_unfold(
    envelope: CertificateEnvelope, ctx: CheckerContext
) -> CheckerVerdict:
    """Replay definitional unfolding and exact evaluation, recording what was used.

    The evaluator already unfolds definitions and parameterised functions, caps recursion
    and detects cycles. What was missing was not the computation but the *evidence*: which
    definitions the result depends on. That set is recorded here, so the claim carries its
    dependency chain instead of arriving as a bare number.

    Nothing here knows about any particular function or argument.
    """
    claim = ctx.payload.get("__claim__")
    env = ctx.environment
    if claim is None or env is None:
        return _reject("definition_unfold_v1 requires a claim and an environment")

    used = _definitions_used(claim, env)
    if not used:
        return _reject(
            "the claim unfolds no definition; use closed_eval_v1 for plain arithmetic"
        )
    free = free_names(claim, env)
    if free:
        return _reject(
            f"the claim is not closed after unfolding: {', '.join(sorted(free))} "
            f"{'is' if len(free) == 1 else 'are'} free"
        )
    try:
        value = evaluate(claim, env)
    except Undecidable as exc:
        return _reject(f"outside the exactly-evaluable fragment: {exc}")
    if not value.exact:
        return _reject("the evaluation was inexact; it cannot establish an equality")
    try:
        truth = value.as_bool()
    except Undecidable as exc:
        return _reject(f"the claim is not a proposition: {exc}")
    if not truth:
        return _reject("the claim evaluates to false")
    return CheckerVerdict(
        True,
        "definitional unfolding and exact evaluation",
        established=claim,
        detail={"unfolded": ", ".join(sorted(used))},
    )


_register(
    TrustedChecker(
        name="definition_unfold_v1",
        judgements=frozenset({JudgementKind.ENTAILS}),
        validate=_definition_unfold,
        trust=(
            "hamiltonian_lang.verification.obligations.evaluate, an HML-owned exact "
            "evaluator with bounded recursive unfolding and cycle detection. No external "
            "CAS or solver participates."
        ),
        fragment=(
            "claims closed after unfolding user definitions and parameterised functions, "
            "over exact rationals"
        ),
        doc="Replays definition/function unfolding and records the definitions used.",
    )
)


# ---------------------------------------------------------------------------
# 3. propositional_underdetermination_v1 -- the two-model certificate
# ---------------------------------------------------------------------------


def extract_model(expr: Expr) -> dict[str, bool]:
    """Read a witness expression as a total Boolean assignment.

    The accepted shape is deliberately tiny, and anything else raises:

    * ``P``               -> P is true
    * ``not P``           -> P is false
    * ``P = true`` /``P = false``
    * conjunctions of the above

    Only Boolean *literals* are accepted as values. The evaluator carries truth values as
    rationals and restores them with ``raw != 0``, so admitting a numeric witness would let
    ``P := 2`` mean true. Narrowing the witness grammar closes that off at the door rather
    than relying on the evaluator's convention.

    Raises ``ValueError`` on anything outside the shape, and on a name assigned twice —
    a contradictory witness is malformed, not a preference for the last value.
    """
    out: dict[str, bool] = {}

    def put(name: str, value: bool) -> None:
        if name in out and out[name] != value:
            raise ValueError(f"{name!r} is assigned both true and false")
        if name in out:
            raise ValueError(f"{name!r} is assigned twice")
        out[name] = value

    def walk_conjunction(e: Expr) -> None:
        if isinstance(e, LogicalOp) and e.op in ("and", "&&"):
            walk_conjunction(e.left)
            walk_conjunction(e.right)
            return
        if isinstance(e, Ref):
            put(e.name, True)
            return
        if isinstance(e, UnaryOp) and e.op == "not" and isinstance(e.operand, Ref):
            put(e.operand.name, False)
            return
        if (
            isinstance(e, Comparison)
            and e.op == "="
            and isinstance(e.left, Ref)
            and isinstance(e.right, Literal)
            and isinstance(e.right.value, bool)
        ):
            put(e.left.name, bool(e.right.value))
            return
        raise ValueError(
            "a witness must be a conjunction of `P`, `not P` or `P = true|false`"
        )

    walk_conjunction(expr)
    if not out:
        raise ValueError("the witness assigns nothing")
    return out


def _underdetermination(
    envelope: CertificateEnvelope, ctx: CheckerContext
) -> CheckerVerdict:
    """Validate a two-model non-entailment certificate.

    Sound because the two models jointly witness both halves of the claim: M⁻ satisfies Γ
    with the target false, so Γ ⊭ P; M⁺ satisfies Γ with the target true, so Γ ⊭ ¬P.

    Requiring **both** models to satisfy Γ also certifies that Γ is satisfiable, so an
    inconsistent Γ — which entails everything — cannot reach UNDERDETERMINED by this route.
    That is not incidental; it is why the certificate demands models of Γ rather than of
    the target alone.
    """
    claim = ctx.payload.get("__claim__")
    env = ctx.environment
    if claim is None or env is None:
        return _reject("propositional_underdetermination_v1 requires a claim and an environment")

    holds_expr = ctx.payload.get("holds")
    fails_expr = ctx.payload.get("fails")
    if holds_expr is None or fails_expr is None:
        return _reject(
            "a two-model certificate needs both witnesses: "
            "holds := <model>, fails := <model>"
        )

    try:
        m_plus = extract_model(holds_expr)
        m_minus = extract_model(fails_expr)
    except ValueError as exc:
        return _reject(f"malformed witness: {exc}")

    premises = ctx.premise_props()

    # The semantic signature: every name still free in the theory or the target.
    signature: set[str] = set(free_names(claim, env))
    for p in premises:
        signature |= set(free_names(p, env))

    non_bool = sorted(n for n in signature if n not in env.bool_names)
    if non_bool:
        # Outside the supported fragment. UNKNOWN -- never UNDERDETERMINED.
        return _reject(
            f"outside the propositional fragment: {', '.join(non_bool)} "
            f"{'is' if len(non_bool) == 1 else 'are'} not a declared Bool"
        )

    for label, model in (("holds", m_plus), ("fails", m_minus)):
        missing = sorted(signature - set(model))
        if missing:
            return _reject(
                f"the {label} witness is partial: {', '.join(missing)} unassigned. "
                f"An incomplete model is rejected, never completed"
            )
        extra = sorted(set(model) - signature)
        if extra:
            return _reject(
                f"the {label} witness assigns {', '.join(extra)}, which "
                f"{'is' if len(extra) == 1 else 'are'} not in the semantic signature"
            )

    if m_plus == m_minus:
        return _reject(
            "both witnesses are the same model; one model cannot give the target both "
            "truth values"
        )

    def truth_of(e: Expr, model: dict[str, bool], what: str) -> bool:
        assignment = {k: Fraction(1 if v else 0) for k, v in model.items()}
        try:
            value = evaluate(e, env, assignment)
        except Undecidable as exc:
            raise ValueError(f"{what} is outside the evaluable fragment: {exc}") from exc
        if not value.exact:
            raise ValueError(f"{what} did not evaluate exactly")
        try:
            return value.as_bool()
        except Undecidable as exc:
            raise ValueError(f"{what} is not a proposition: {exc}") from exc

    try:
        for label, model in (("holds", m_plus), ("fails", m_minus)):
            for i, premise in enumerate(premises):
                if not truth_of(premise, model, f"premise {i} under the {label} witness"):
                    return _reject(
                        f"the {label} witness does not satisfy premise {i}; a witness "
                        f"that violates the context says nothing about entailment from it"
                    )
        if not truth_of(claim, m_plus, "the target under the holds witness"):
            return _reject("the holds witness does not make the target true")
        if truth_of(claim, m_minus, "the fails witness"):
            return _reject("the fails witness does not make the target false")
    except ValueError as exc:
        return _reject(str(exc))

    return CheckerVerdict(
        True,
        "two models of the context disagree on the target",
        established=claim,
        detail={
            "holds": ", ".join(f"{k}={str(v).lower()}" for k, v in sorted(m_plus.items())),
            "fails": ", ".join(f"{k}={str(v).lower()}" for k, v in sorted(m_minus.items())),
            "premises_satisfied": str(len(premises)),
        },
    )


_register(
    TrustedChecker(
        name="propositional_underdetermination_v1",
        judgements=frozenset({JudgementKind.DETERMINES_NEITHER}),
        validate=_underdetermination,
        trust=(
            "hamiltonian_lang.verification.obligations.evaluate used as a model checker "
            "over declared Bool names. No SAT/SMT solver participates: both models are "
            "supplied by the author and independently evaluated here."
        ),
        fragment=(
            "finite ground classical propositional logic over declared Bool names; no "
            "first-order completeness is claimed"
        ),
        doc="Validates two models of Γ that disagree on the target.",
    )
)
