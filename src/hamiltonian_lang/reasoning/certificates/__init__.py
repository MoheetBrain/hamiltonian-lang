"""The checked-certificate boundary: how anything outside the kernel may become evidence.

The problem this solves
-----------------------
HML already contains machinery that can decide real mathematical questions — an exact
rational evaluator with definitional unfolding, interval and partiality analysis, a
symbolic-equivalence engine. None of it could feed the v2 ``derive``/``proved`` path,
because that path admits exactly one source of truth: a rule in
:mod:`~hamiltonian_lang.reasoning.kernel`. The obvious repair — a rule per capability — is
the wrong one. It grows the trusted computing base once per mathematical fact anybody
wants, and each addition is a fresh place for an unsound step to enter. Arithmetic,
probability and calculus are not universal reasoning semantics; they are domain knowledge,
and domain knowledge belongs in libraries.

So there is **one** gate instead of dozens of rules::

    claim + context + dependencies + payload + checker id
        -> registered trusted checker
        -> REJECT   |   CheckedEvidence

Normative specification: ``docs/hml_v2/GOLD10_CORE_SEMANTICS_SPEC.md`` §2.

What the core does and does not trust
-------------------------------------
The core does **not** trust "a library says this is true". It trusts that a named,
versioned, in-repository, deterministic checker re-decided the stated claim from the
stated inputs, and that the envelope still describes the mathematics actually in front of
it. Concretely:

* the checker is selected from :data:`CHECKERS`, a static table populated by the checker
  modules in this package. There is **no registration API reachable from HML source, from
  a module being checked, or from library data** — because if a library could register
  ``def always_valid(...): return VALID`` the entire TCB would be gone. Libraries may
  *refer* to a checker by name; they may not supply one;
* the version is part of the registry key (``closed_eval_v1``, not ``closed_eval`` at
  version 1), so when semantics change the key changes and modules naming the old key stop
  validating instead of silently acquiring new behaviour;
* every checker declares which judgements it may reach, so it cannot exceed its declared
  competence even by accident;
* validation is fail-closed in every direction, including on any exception (§2.4).

This is still a TCB extension, and pretending otherwise would be the dishonest move.
:class:`TrustedChecker` carries :attr:`trust` — a plain statement of what that checker's
soundness actually rests on — and a test requires it to be non-empty. An unstated trust
basis is an unaudited one.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from ...ast.nodes import Expr, Span

if TYPE_CHECKING:  # pragma: no cover - typing only
    # Import-time only. At runtime the annotation stays a string (PEP 563), so the
    # boundary keeps no hard dependency on the evaluator package.
    from ...verification.obligations.evaluate import Environment

__all__ = [
    "JudgementKind",
    "EvidenceKind",
    "CertificateEnvelope",
    "CheckerContext",
    "CheckerVerdict",
    "CheckedEvidence",
    "TrustedChecker",
    "CHECKERS",
    "checker_names",
    "context_hash",
    "check",
]


class JudgementKind(StrEnum):
    """What a certificate claims. The two are **not** on a scale; they are different kinds.

    ``ENTAILS``
        The dependencies establish the claim. Once validated this is ordinary evidence
        and may be a premise.

    ``DETERMINES_NEITHER``
        The dependencies establish neither the claim nor its negation. This is a statement
        about the *theory*, not an assertion of the proposition, and it must never be
        usable as a premise: "P is undetermined" does not give you P. Treating it as
        though it did would be the worst failure available here, so the evidence graph
        classifies it ``NOT_EVIDENCE`` and a test pins that.
    """

    ENTAILS = "ENTAILS"
    DETERMINES_NEITHER = "DETERMINES_NEITHER"


class EvidenceKind(StrEnum):
    """What *kind* of support a claim has. Orthogonal to ``DerivationStatus``/``GoalStatus``.

    Keeping these axes separate is what stops "an oracle answered" from drifting into "it
    is proved". The status says how far adjudication got; the kind says what the support
    actually is, and only two kinds can ever reach VERIFIED.
    """

    #: The trusted inference kernel applied a rule. May establish VERIFIED.
    NATIVE_KERNEL = "NATIVE_KERNEL"
    #: A registered checker validated the exact envelope. May establish VERIFIED.
    CHECKED_CERTIFICATE = "CHECKED_CERTIFICATE"
    #: SymPy, an SMT solver, a CAS, a model. Recorded, never VERIFIED. See SPEC §2.7.
    UNTRUSTED_ORACLE = "UNTRUSTED_ORACLE"
    #: Interval/float evidence. Never establishes an exact equality — only the
    #: corresponding bounded or approximate proposition.
    NUMERIC_BOUND = "NUMERIC_BOUND"
    NONE = "NONE"


#: Kinds that may support a VERIFIED result. Anything absent here cannot, by construction.
VERIFYING_KINDS = frozenset({EvidenceKind.NATIVE_KERNEL, EvidenceKind.CHECKED_CERTIFICATE})


def _digest(parts: Sequence[str]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def context_hash(propositions: Sequence[str]) -> str:
    """Identity of Γ: a digest over the *sorted* canonical identities of its members.

    Sorted, because Γ is a set — reordering two assumptions must not change the theory.
    Digested rather than concatenated so the value is a fixed size regardless of how large
    the context grows.
    """
    return _digest(sorted(propositions))


@dataclass(frozen=True)
class CertificateEnvelope:
    """A certificate bound to the exact mathematics it was issued about.

    The hashes are the anti-replay mechanism. A certificate is about one claim, in one
    context, resting on one ordered premise list. Change any of them and the envelope no
    longer describes the situation, so it does not apply — it does not "mostly apply", and
    it does not degrade to a warning.

    **Execution metadata must never appear here.** Timestamps, durations, log paths, host
    and solver build are provenance; they are recorded beside the mathematics and never
    inside its identity. This is the existing rule (D-034 E1/E10) applied to certificates.
    """

    certificate_type: str
    certificate_version: int
    #: Registry key. The version is part of the key.
    checker: str
    judgement: JudgementKind
    #: ``expr_identity`` of the claim.
    claim_hash: str
    #: Identity of Γ at issuance. Re-derived and compared at consumption (SPEC §3.3).
    context_hash: str
    #: ``expr_identity`` of each declared dependency, in declared order.
    premise_hashes: tuple[str, ...]
    span: Span = field(default_factory=Span)

    def summary(self) -> str:
        return (
            f"{self.certificate_type}/v{self.certificate_version} via {self.checker} "
            f"[claim {self.claim_hash[:12]}, context {self.context_hash[:12]}]"
        )


@dataclass(frozen=True)
class CheckerContext:
    """Everything a checker may read. Deliberately small, and deliberately inert.

    A checker sees the resolved propositions of the certificate's *declared* dependencies
    and nothing else — not the module, not the whole claim pool. A checker that wants a
    fact must have it declared, which is what makes ``dependencies`` an auditable statement
    of what the conclusion rests on rather than decoration.

    No clock, no filesystem, no network, no randomness: validation must be a pure function
    of the envelope and this context, so a re-run reaches the same verdict.
    """

    #: label -> proposition, declared dependencies only, in declared order.
    premises: tuple[tuple[str, Expr], ...] = ()
    #: Role-labelled payload from the source statement. Opaque to this module by design:
    #: the boundary must not grow a branch per checker.
    payload: Mapping[str, Expr] = field(default_factory=dict)
    #: Exact-evaluation environment built from the module's declarations. ``None`` when
    #: one could not be built, in which case every checker that needs it fails closed.
    environment: Environment | None = None
    #: Present so a checker can consult declared types without reaching for the module.
    declared_types: Mapping[str, object] = field(default_factory=dict)

    def premise_props(self) -> tuple[Expr, ...]:
        return tuple(p for _, p in self.premises)


@dataclass(frozen=True)
class CheckerVerdict:
    """A checker's answer.

    ``established`` is what the checker believes it decided. :func:`check` compares it
    against the envelope's claim under canonical identity and rejects a mismatch. That
    guard does not defend against a *malicious* checker — a checker is trusted code by
    definition — but it does catch the realistic failure, which is a checker that reads the
    wrong part of the payload and validates something adjacent to what the author wrote.
    """

    valid: bool
    reason: str = ""
    established: Expr | None = None
    #: Diagnostics and provenance only. Never enters a content hash.
    detail: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TrustedChecker:
    name: str
    #: Judgements this checker may reach. Checked before it runs.
    judgements: frozenset[JudgementKind]
    validate: Callable[[CertificateEnvelope, CheckerContext], CheckerVerdict]
    #: What this checker's soundness actually rests on. Required non-empty.
    trust: str
    #: The fragment outside which it must fail closed.
    fragment: str = ""
    doc: str = ""


#: The static trusted registry. Populated at import by the modules in this package.
#: Adding an entry is a deliberate, reviewable TCB change.
CHECKERS: dict[str, TrustedChecker] = {}


def _register(spec: TrustedChecker) -> TrustedChecker:
    """Package-private. Not exported, and not reachable from source or library data."""
    if spec.name in CHECKERS:
        raise RuntimeError(f"checker {spec.name!r} is already registered")
    if not spec.trust.strip():
        raise RuntimeError(f"checker {spec.name!r} declares no trust basis")
    CHECKERS[spec.name] = spec
    return spec


def checker_names() -> tuple[str, ...]:
    return tuple(sorted(CHECKERS))


#: Construction token for :class:`CheckedEvidence`. Module-private by convention *and* by
#: value: nothing outside this module has it, so nothing outside this module can build a
#: CheckedEvidence. See :func:`check`.
_MINT = object()


@dataclass(frozen=True)
class CheckedEvidence:
    """The only object the reasoning layer accepts as certificate-derived support.

    Constructible **only** by :func:`check`. Surface HML cannot produce one, library data
    cannot produce one, and a payload cannot contain one — direct construction raises.
    That is what makes "this was checked" a fact about the code path rather than a label
    anybody can attach.
    """

    envelope: CertificateEnvelope
    kind: EvidenceKind
    established: Expr
    checker: str
    detail: Mapping[str, str] = field(default_factory=dict)
    _token: object = None

    def __post_init__(self) -> None:
        if self._token is not _MINT:
            raise TypeError(
                "CheckedEvidence is minted only by reasoning.certificates.check(); "
                "constructing one directly would forge the fact that it was checked"
            )


def check(
    envelope: CertificateEnvelope,
    claim: Expr,
    ctx: CheckerContext,
    *,
    current_context_hash: str,
) -> tuple[CheckedEvidence | None, str]:
    """The gate. Returns ``(evidence, "")`` or ``(None, reason)``.

    Order matters: the cheap structural refusals come first, so a checker never runs on an
    envelope that has already failed and the reported reason is the first thing genuinely
    wrong rather than whatever the checker happened to notice.

    ``current_context_hash`` is Γ *at the point of consumption*. Comparing it with the
    envelope's is what stops a certificate issued under one theory from being spent under
    another (SPEC §3.3).
    """
    from ...backends.canonical import expr_identity

    spec = CHECKERS.get(envelope.checker)
    if spec is None:
        return None, (
            f"{envelope.checker!r} is not a registered trusted checker "
            f"(registered: {', '.join(checker_names()) or 'none'})"
        )
    if envelope.judgement not in spec.judgements:
        offered = ", ".join(sorted(str(j) for j in spec.judgements))
        return None, (
            f"checker {spec.name!r} cannot reach judgement {envelope.judgement}; "
            f"it offers {offered}"
        )
    if claim is None:
        return None, "the certificate states no claim"

    if expr_identity(claim) != envelope.claim_hash:
        return None, (
            "the certificate was issued for a different claim than the one stated "
            "(claim hash mismatch)"
        )
    if envelope.context_hash != current_context_hash:
        return None, (
            "the certificate was issued under a different context than the one in scope "
            "here; a certificate does not survive a change to the premises it was issued "
            "against (stale context)"
        )
    actual_premises = tuple(expr_identity(p) for _, p in ctx.premises)
    if actual_premises != envelope.premise_hashes:
        return None, (
            "the certificate's declared premises are not the premises it is being applied "
            "to (premise hash mismatch)"
        )

    try:
        verdict = spec.validate(envelope, ctx)
    except Exception as exc:  # noqa: BLE001 -- fail closed on ANY checker failure
        # A checker that raises has established nothing. Letting the exception escape
        # would abort the compile; treating it as a pass would be catastrophic.
        return None, f"checker {spec.name!r} failed: {type(exc).__name__}: {exc}"

    if not isinstance(verdict, CheckerVerdict):
        return None, (
            f"checker {spec.name!r} returned {type(verdict).__name__}, not a verdict"
        )
    if not verdict.valid:
        return None, verdict.reason or f"checker {spec.name!r} rejected the certificate"
    if verdict.established is None:
        return None, (
            f"checker {spec.name!r} reported VALID without naming what it established"
        )
    if expr_identity(verdict.established) != expr_identity(claim):
        from ...backends.hml import render_expr

        return None, (
            f"checker {spec.name!r} established {render_expr(verdict.established)}, "
            f"which is not the stated claim {render_expr(claim)}"
        )

    return (
        CheckedEvidence(
            envelope=envelope,
            kind=EvidenceKind.CHECKED_CERTIFICATE,
            established=verdict.established,
            checker=spec.name,
            detail=dict(verdict.detail),
            _token=_MINT,
        ),
        "",
    )


from . import builtin as _builtin  # noqa: E402,F401  -- populates CHECKERS
