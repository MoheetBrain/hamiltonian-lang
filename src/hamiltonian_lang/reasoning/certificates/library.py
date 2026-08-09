"""Checkers that let the domain libraries reach the reasoning graph.

Two, and they have deliberately different shapes because they rest on different things.

``library_theorem_v1``
    Applies a named theorem from the static registry. What it checks is the
    **instantiation**: that the theorem exists at that version, that every variable is
    substituted exactly once with something whose resolved type inhabits its declared
    domain, that the conclusion the theorem licenses is canonically the proposition the
    author claimed, and that every premise it requires was declared. What it does *not*
    check is the theorem itself -- ``add_zero`` is an axiom of the algebra library, and the
    certificate says so rather than pretending otherwise.

``derivative_trace_v1``
    Differentiates the expression itself and compares. Nothing in the proposal is trusted,
    so a derivative suggested by a CAS, a model or a guess is worth exactly as much as one
    the author typed: it is a claim, and the replay decides it.

Both route their side conditions into the **existing** obligation machinery through the
verdict, so ``P(A) > 0`` and ``x != 0`` are discharged against Γ by the same code that
discharges a ``divide_both_sides`` obligation. There is no library-specific condition
system, and an undischarged mandatory condition means the certificate does not validate.

Neither checker can be supplied by a library. The registry is static, as it was before this
package existed; libraries provide *theorems*, which are data, not trusted code.
"""

from __future__ import annotations

from ...ast.nodes import Ref
from ...libraries import theorem as lib
from ...libraries.calculus import DifferentiationError, check_derivative_claim
from . import (
    CertificateEnvelope,
    CheckerContext,
    CheckerVerdict,
    JudgementKind,
    TrustedChecker,
    _register,
)

__all__: list[str] = []

#: The role that names the theorem. Resolved against the theorem registry rather than the
#: value namespace, exactly as the `fn` role of `congruence` is resolved against functions.
THEOREM_ROLE = "theorem"


def _library_theorem(
    envelope: CertificateEnvelope, ctx: CheckerContext
) -> CheckerVerdict:
    from ...backends.canonical import expr_identity
    from ...backends.hml import render_expr

    claim = ctx.payload.get("__claim__")
    if claim is None:
        return CheckerVerdict(False, "no claim was supplied")

    named = ctx.payload.get(THEOREM_ROLE)
    if not isinstance(named, Ref):
        return CheckerVerdict(
            False,
            f"library_theorem_v1 needs `{THEOREM_ROLE} := <id>` naming a registered "
            f"theorem (available: {', '.join(lib.theorem_ids()) or 'none'})",
        )
    thm = lib.THEOREMS.get(named.name)
    if thm is None:
        return CheckerVerdict(
            False,
            f"{named.name!r} is not a registered theorem "
            f"(available: {', '.join(lib.theorem_ids()) or 'none'})",
        )

    substitution = {
        role: value
        for role, value in ctx.payload.items()
        if role not in (THEOREM_ROLE, "__claim__")
    }
    try:
        applied = lib.instantiate(thm, substitution)
    except lib.InstantiationError as exc:
        return CheckerVerdict(False, str(exc))

    if expr_identity(applied.conclusion) != expr_identity(claim):
        return CheckerVerdict(
            False,
            f"theorem {thm.id!r} under this substitution licenses "
            f"{render_expr(applied.conclusion)}, not the stated "
            f"{render_expr(claim)}",
        )

    # Every premise the theorem requires must be among the DECLARED dependencies. Finding
    # it elsewhere in the module would not do: the point of `from ...` is that a claim
    # states what it rests on.
    declared = {expr_identity(p) for _, p in ctx.premises}
    missing = [p for p in applied.premises if expr_identity(p) not in declared]
    if missing:
        return CheckerVerdict(
            False,
            f"theorem {thm.id!r} requires "
            f"{', '.join(render_expr(m) for m in missing)}, which "
            f"{'is' if len(missing) == 1 else 'are'} not among the declared premises",
        )

    return CheckerVerdict(
        True,
        f"instantiation of {thm.id} v{thm.version}",
        established=claim,
        obligations=applied.side_conditions,
        detail={
            "theorem": f"{thm.id} v{thm.version}",
            "library": thm.library,
            "verification_kind": str(thm.verification_kind),
            "statement": thm.statement,
            "substitution": ", ".join(
                f"{k} := {render_expr(v)}" for k, v in sorted(substitution.items())
            ),
        },
    )


_register(
    TrustedChecker(
        name="library_theorem_v1",
        judgements=frozenset({JudgementKind.ENTAILS}),
        validate=_library_theorem,
        trust=(
            "The INSTANTIATION is checked here: registry membership, variable coverage, "
            "type conformance via the language's own is_subtype, conclusion identity, and "
            "premise declaration. The THEOREM ITSELF is not derived by HML -- algebra and "
            "probability theorems are labelled LIBRARY_AXIOM or DEFINITIONAL, each carries "
            "a written justification, and libraries.axioms() prints the complete assumed "
            "set. Side conditions become ordinary obligations discharged against Gamma."
        ),
        fragment=(
            "applications of theorems in the static registry "
            "(hamiltonian_lang.libraries), with typed substitutions"
        ),
        doc="Applies a named library theorem and checks the instantiation.",
    )
)


def _derivative_trace(
    envelope: CertificateEnvelope, ctx: CheckerContext
) -> CheckerVerdict:
    claim = ctx.payload.get("__claim__")
    if claim is None:
        return CheckerVerdict(False, "no claim was supplied")
    extra = [k for k in ctx.payload if k != "__claim__"]
    if extra:
        return CheckerVerdict(
            False,
            f"derivative_trace_v1 takes no arguments; it re-derives the derivative "
            f"itself. Got {', '.join(sorted(extra))}",
        )
    try:
        established, conditions, detail = check_derivative_claim(claim)
    except DifferentiationError as exc:
        return CheckerVerdict(False, str(exc))

    return CheckerVerdict(
        True,
        "differentiation replayed from primitive rules",
        established=established,
        obligations=tuple(
            (c, "differentiation_domain_condition", True) for c in conditions
        ),
        detail=detail,
    )


_register(
    TrustedChecker(
        name="derivative_trace_v1",
        judgements=frozenset({JudgementKind.ENTAILS}),
        validate=_derivative_trace,
        trust=(
            "hamiltonian_lang.libraries.calculus, which differentiates the expression "
            "itself from primitive rules and compares. NO proposal is trusted -- a "
            "derivative from a CAS, a model or a guess is a claim the replay decides. "
            "Normalisation uses the oriented algebra identities, each a named registered "
            "theorem, applied deterministically to a fixed point; sympy.simplify is not "
            "used anywhere on this path. Quotient domain conditions become ordinary "
            "obligations discharged against Gamma."
        ),
        fragment=(
            "derivative(<body>, x : T) = <result> where body is built from literals, "
            "references, + - * / and a literal power; no chain rule, no transcendentals"
        ),
        doc="Replays a differentiation and checks the claimed result.",
    )
)
