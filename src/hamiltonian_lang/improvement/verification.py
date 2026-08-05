"""Verifier federation — Phase 9.

Every verifier answers two questions, in this order:

    supports(canonical_object, candidate) -> SupportDecision
    verify(canonical_object, candidate)   -> VerificationResult

Nothing new is verified here. Each verifier is a thin wrapper over a mechanism that
already exists in this repository -- the parser, the resolver, the type checker, the
dimensional rules inside it, the V1 epistemic checker, the canonical content hash, the
SymPy backend's executable output, and :mod:`hamiltonian_lang.v1.lean_verify`. The value
added is the *classification*, and the classification is deliberately pessimistic.

The five rules that this module exists to enforce
--------------------------------------------------
1. **Unsupported is not failure.** A verifier that cannot express the claim reports
   ``UNSUPPORTED``. It never contributes to a negative verdict, and it never contributes
   to a positive one.
2. **Inconclusive is not verified.** An open obligation keeps the episode inconclusive
   no matter how many other verifiers passed.
3. **Source generation is not backend verification.** Emitting Lean or Stan text proves
   the emitter ran. :class:`StanVerifier` therefore returns ``UNSUPPORTED`` always.
4. **Successful execution is not semantic equivalence.** A SymPy module that runs proves
   it imports and evaluates. :class:`SympyExecutionVerifier` returns ``INCONCLUSIVE`` on
   success and ``SUPPORTED_AND_FAILED`` on a crash -- the negative is informative, the
   positive is not.
5. **`sorry` never counts.** :mod:`hamiltonian_lang.v1.lean_verify` already rejects it
   textually; this module maps every rejecting verdict away from
   ``SUPPORTED_AND_VERIFIED`` so a future change to that module cannot leak one through.

A sixth rule falls out of the first two and is worth naming, because over-claiming here
is the easiest mistake to make: **a failure without a counterexample is inconclusive, not
disproved.** "The verifier did not accept this" and "this is false" are different facts.

Measured environment facts, encoded rather than rediscovered
-------------------------------------------------------------
From ``docs/evaluation/PHASE1_LEAD_AUDIT.md``, reproduced on 2026-08-05 at ``967e95d``:

* ``stanc`` is absent. Stan output has never been compiled.
* Mathlib is absent, so ``Real`` does not resolve and essentially every HML statement
  about real numbers, probability or measure is outside core Lean 4.
* The Lean backend closes every obligation with ``sorry`` **by design**, and ``sorry`` is
  in ``FORBIDDEN_TACTICS``, so ``lean_verify.verify()`` rejects the backend's own output
  before Lean is invoked. The gate is sound and nothing can pass through it.
* SymPy 1.14.0 executes 15/15 non-illustrative examples.

None of these is broadened here. :data:`ENVIRONMENT_FACTS` states them, and the tests
assert the verifiers behave accordingly.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from .. import compile_source
from .events import canonical_blob, sha256_hex

__all__ = [
    "VERIFICATION_PROTOCOL_VERSION",
    "VerifierStatus",
    "CandidateLanguage",
    "CanonicalObject",
    "Candidate",
    "SupportDecision",
    "Counterexample",
    "SemanticLoss",
    "VerificationResult",
    "Verifier",
    "ENVIRONMENT_FACTS",
    "ParseVerifier",
    "ResolutionVerifier",
    "TypeCheckVerifier",
    "DimensionVerifier",
    "EpistemicVerifier",
    "CanonicalComparatorVerifier",
    "SympyExecutionVerifier",
    "LeanVerifier",
    "StanVerifier",
    "VerifierFederation",
    "default_federation",
    "classify",
]

VERIFICATION_PROTOCOL_VERSION = "hml-verification-1.0.0"


class VerifierStatus(StrEnum):
    """What one verifier concluded. Six outcomes, none of them a synonym for another."""

    SUPPORTED_AND_VERIFIED = "SUPPORTED_AND_VERIFIED"
    SUPPORTED_AND_FAILED = "SUPPORTED_AND_FAILED"
    INVALID = "INVALID"
    UNSUPPORTED = "UNSUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    SEMANTIC_LOSS = "SEMANTIC_LOSS"


class CandidateLanguage(StrEnum):
    HML = "hml"
    LEAN = "lean"
    STAN = "stan"
    SYMPY_PYTHON = "sympy_python"
    ENGLISH = "english"


#: Facts about this machine, measured and recorded so no verifier has to guess. Values
#: are ``(present, why_it_matters)``.
ENVIRONMENT_FACTS: Mapping[str, tuple[bool, str]] = {
    "stanc": (
        False,
        "not on PATH; no Stan artefact produced by this repository has ever been "
        "compiled, so no Stan claim is toolchain-verified",
    ),
    "mathlib": (
        False,
        "absent from ~/.elan/toolchains; `Real` does not resolve, so Mathlib-dependent "
        "lowering is UNSUPPORTED rather than failing",
    ),
    "lean_backend_emits_sorry": (
        True,
        "the Lean backend closes every obligation with `sorry` by design; `sorry` is in "
        "FORBIDDEN_TACTICS, so lean_verify rejects the backend's own output before Lean "
        "runs",
    ),
    "sympy": (
        True,
        "SymPy 1.14.0 executes 15/15 non-illustrative examples; execution establishes "
        "that the emitted module runs, not that it means what the HML meant",
    ),
}


@dataclass(frozen=True)
class CanonicalObject:
    """The reference the candidate is checked against.

    ``source`` is the ground-truth HML when the task has one. ``content_hash`` is the
    alpha-invariant identity from :mod:`hamiltonian_lang.backends.canonical`; it is the
    only deterministic equivalence oracle this project actually has.
    """

    object_id: str
    source: str = ""
    content_hash: str | None = None
    final_answer: str | None = None
    expected_statement: str | None = None
    attachments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Candidate:
    """The artefact under verification."""

    text: str
    language: CandidateLanguage = CandidateLanguage.HML
    attachments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SupportDecision:
    """Whether a verifier can say anything at all about this pair.

    ``reason`` is mandatory when unsupported. "It did not apply" without a reason is the
    shape a silently-skipped check takes.
    """

    supported: bool
    reason: str = ""
    missing_capability: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.supported and not self.reason.strip():
            raise ValueError(
                "an unsupported decision must say why; an unexplained skip is "
                "indistinguishable from a check that silently did nothing"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported": self.supported,
            "reason": self.reason,
            "missing_capability": list(self.missing_capability),
        }


@dataclass(frozen=True)
class Counterexample:
    """A concrete witness that the candidate is wrong.

    Its presence is what separates ``DISPROVED`` from ``INCONCLUSIVE``. A verifier that
    merely failed to accept something must not manufacture one.
    """

    description: str
    witness: str = ""
    produced_by: str = ""

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("a counterexample must describe what it witnesses")

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "witness": self.witness,
            "produced_by": self.produced_by,
        }


@dataclass(frozen=True)
class SemanticLoss:
    """Something the pipeline could not preserve, as reported by a backend."""

    construct: str
    reason: str
    severity: str = "dropped"  # dropped | approximated | weakened

    def to_dict(self) -> dict[str, Any]:
        return {"construct": self.construct, "reason": self.reason, "severity": self.severity}


@dataclass(frozen=True)
class VerificationResult:
    """One verifier's answer, with everything needed to audit it later."""

    verifier_name: str
    verifier_version: str
    status: VerifierStatus
    obligations_checked: tuple[str, ...] = ()
    obligations_remaining: tuple[str, ...] = ()
    counterexample: Counterexample | None = None
    semantic_loss: tuple[SemanticLoss, ...] = ()
    evidence: Mapping[str, Any] = field(default_factory=dict)
    evidence_hash: str = ""
    detail: str = ""
    protocol_version: str = VERIFICATION_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.status is VerifierStatus.SUPPORTED_AND_VERIFIED and self.obligations_remaining:
            raise ValueError(
                f"{self.verifier_name}: cannot report SUPPORTED_AND_VERIFIED with "
                f"{len(self.obligations_remaining)} obligation(s) still open"
            )
        if self.status is VerifierStatus.SUPPORTED_AND_VERIFIED and self.counterexample:
            raise ValueError(
                f"{self.verifier_name}: a counterexample and a verified status cannot "
                f"both be true"
            )
        if self.status is VerifierStatus.SEMANTIC_LOSS and not self.semantic_loss:
            raise ValueError(
                f"{self.verifier_name}: SEMANTIC_LOSS must name what was lost"
            )
        if not self.evidence_hash:
            object.__setattr__(self, "evidence_hash", self._hash_evidence())

    def _hash_evidence(self) -> str:
        return sha256_hex(
            canonical_blob(
                {
                    "verifier_name": self.verifier_name,
                    "verifier_version": self.verifier_version,
                    "status": str(self.status),
                    "obligations_checked": list(self.obligations_checked),
                    "obligations_remaining": list(self.obligations_remaining),
                    "counterexample": (
                        self.counterexample.to_dict() if self.counterexample else None
                    ),
                    "semantic_loss": [s.to_dict() for s in self.semantic_loss],
                    "evidence": dict(self.evidence),
                    "detail": self.detail,
                    "protocol_version": self.protocol_version,
                }
            )
        )

    @property
    def verified(self) -> bool:
        """The only property a caller may read to label something verified."""
        return self.status is VerifierStatus.SUPPORTED_AND_VERIFIED

    def to_dict(self) -> dict[str, Any]:
        return {
            "verifier_name": self.verifier_name,
            "verifier_version": self.verifier_version,
            "status": str(self.status),
            "obligations_checked": list(self.obligations_checked),
            "obligations_remaining": list(self.obligations_remaining),
            "counterexample": self.counterexample.to_dict() if self.counterexample else None,
            "semantic_loss": [s.to_dict() for s in self.semantic_loss],
            "evidence_hash": self.evidence_hash,
            "detail": self.detail,
            "protocol_version": self.protocol_version,
        }


@runtime_checkable
class Verifier(Protocol):
    """The common protocol. Implementations wrap existing mechanisms only."""

    name: str
    version: str

    def supports(self, canonical_object: CanonicalObject, candidate: Candidate) -> SupportDecision:
        ...

    def verify(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> VerificationResult:
        ...


class _BaseVerifier:
    """Shared plumbing. ``verify`` refuses to run when ``supports`` said no."""

    name = "base"
    version = "0.0.0"

    def supports(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> SupportDecision:  # pragma: no cover - overridden
        raise NotImplementedError

    def _unsupported(self, decision: SupportDecision) -> VerificationResult:
        return VerificationResult(
            verifier_name=self.name,
            verifier_version=self.version,
            status=VerifierStatus.UNSUPPORTED,
            detail=decision.reason,
            evidence={"missing_capability": list(decision.missing_capability)},
        )

    def _result(self, status: VerifierStatus, **kw: Any) -> VerificationResult:
        return VerificationResult(
            verifier_name=self.name, verifier_version=self.version, status=status, **kw
        )


# ---------------------------------------------------------------------------
# Compiler-stage verifiers
# ---------------------------------------------------------------------------


def _hml_only(candidate: Candidate, what: str) -> SupportDecision:
    if candidate.language is not CandidateLanguage.HML:
        return SupportDecision(
            False,
            f"{what} reads HML; this candidate is {candidate.language}",
            missing_capability=(f"{candidate.language}-frontend",),
        )
    if not candidate.text.strip():
        return SupportDecision(False, "the candidate is empty; there is nothing to check")
    return SupportDecision(True)


def _codes(diags: Sequence[Any], prefix: str) -> list[str]:
    return [d.code for d in diags if d.code.startswith(prefix)]


class ParseVerifier(_BaseVerifier):
    """Wraps the lexer and parser. Establishes syntactic well-formedness only."""

    name = "parser"
    version = "hml-0.1.0"

    def supports(self, canonical_object: CanonicalObject, candidate: Candidate) -> SupportDecision:
        return _hml_only(candidate, "the HML parser")

    def verify(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> VerificationResult:
        decision = self.supports(canonical_object, candidate)
        if not decision.supported:
            return self._unsupported(decision)
        from .. import parse

        _module, bag = parse(candidate.text)
        errors = [d for d in bag.errors if d.code.startswith(("HML-L", "HML-P"))]
        if errors:
            return self._result(
                VerifierStatus.INVALID,
                obligations_checked=("parses",),
                obligations_remaining=("parses",),
                detail=f"{len(errors)} lexical or parse error(s): {[d.code for d in errors]}",
                evidence={"codes": [d.code for d in errors]},
            )
        # Parsing is one obligation and only one. Saying so keeps a green parse from
        # being read as a green anything-else.
        return self._result(
            VerifierStatus.SUPPORTED_AND_VERIFIED,
            obligations_checked=("parses",),
            detail="the candidate parses; this establishes syntax and nothing further",
        )


class ResolutionVerifier(_BaseVerifier):
    """Wraps name resolution and scoping (``HML-N3xx``)."""

    name = "resolver"
    version = "hml-0.1.0"

    def supports(self, canonical_object: CanonicalObject, candidate: Candidate) -> SupportDecision:
        return _hml_only(candidate, "the HML resolver")

    def verify(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> VerificationResult:
        decision = self.supports(canonical_object, candidate)
        if not decision.supported:
            return self._unsupported(decision)
        result = compile_source(candidate.text)
        parse_errors = _codes(result.diagnostics.errors, "HML-P")
        if parse_errors:
            return self._result(
                VerifierStatus.INCONCLUSIVE,
                obligations_remaining=("every name resolves",),
                detail=(
                    "resolution did not run because parsing failed; that is not evidence "
                    "about names"
                ),
                evidence={"parse_codes": parse_errors},
            )
        bad = _codes(result.diagnostics.errors, "HML-N")
        if bad:
            return self._result(
                VerifierStatus.INVALID,
                obligations_checked=("every name resolves",),
                obligations_remaining=("every name resolves",),
                detail=f"unresolved or mis-scoped names: {bad}",
                evidence={"codes": bad},
            )
        return self._result(
            VerifierStatus.SUPPORTED_AND_VERIFIED,
            obligations_checked=("every name resolves",),
            detail="every name resolves to a binding in scope",
        )


class TypeCheckVerifier(_BaseVerifier):
    """Wraps the type checker (``HML-T4xx``).

    Reports the proof obligations the checker collected as *remaining*: the type checker
    discharges typing, not the mathematics the obligations state.
    """

    name = "type_checker"
    version = "hml-0.1.0"

    def supports(self, canonical_object: CanonicalObject, candidate: Candidate) -> SupportDecision:
        return _hml_only(candidate, "the HML type checker")

    def verify(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> VerificationResult:
        decision = self.supports(canonical_object, candidate)
        if not decision.supported:
            return self._unsupported(decision)
        result = compile_source(candidate.text)
        blocked = _codes(result.diagnostics.errors, "HML-P") + _codes(
            result.diagnostics.errors, "HML-N"
        )
        if blocked:
            return self._result(
                VerifierStatus.INCONCLUSIVE,
                obligations_remaining=("every expression is well typed",),
                detail="type checking did not run because an earlier stage failed",
                evidence={"codes": blocked},
            )
        bad = _codes(result.diagnostics.errors, "HML-T") + _codes(
            result.diagnostics.errors, "HML-S"
        )
        obligations = tuple(f"{o.kind}:{o.description}" for o in result.obligations)
        if bad:
            return self._result(
                VerifierStatus.INVALID,
                obligations_checked=("every expression is well typed",),
                obligations_remaining=("every expression is well typed", *obligations),
                detail=f"type errors: {bad}",
                evidence={"codes": bad},
            )
        return self._result(
            VerifierStatus.SUPPORTED_AND_VERIFIED if not obligations
            else VerifierStatus.INCONCLUSIVE,
            obligations_checked=("every expression is well typed",),
            obligations_remaining=obligations,
            detail=(
                "well typed; the collected proof obligations are open and typing does "
                "not discharge them"
                if obligations
                else "well typed, with no proof obligation collected"
            ),
        )


class DimensionVerifier(_BaseVerifier):
    """Wraps the dimensional rules inside the type checker (``HML-D5xx``).

    ``supports`` is False when the candidate carries no dimensional content at all: a
    program with no quantities has nothing dimensional to be right or wrong about, and
    reporting a pass there would inflate the verified count with vacuous results.
    """

    name = "dimensional_checker"
    version = "hml-0.1.0"

    def supports(self, canonical_object: CanonicalObject, candidate: Candidate) -> SupportDecision:
        base = _hml_only(candidate, "the dimensional checker")
        if not base.supported:
            return base
        if "Quantity[" not in candidate.text and "check dimension" not in candidate.text:
            return SupportDecision(
                False,
                "the candidate declares no Quantity and asserts no dimension; there is "
                "no dimensional obligation to check",
            )
        return SupportDecision(True)

    def verify(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> VerificationResult:
        decision = self.supports(canonical_object, candidate)
        if not decision.supported:
            return self._unsupported(decision)
        result = compile_source(candidate.text)
        blocked = _codes(result.diagnostics.errors, "HML-P") + _codes(
            result.diagnostics.errors, "HML-N"
        )
        if blocked:
            return self._result(
                VerifierStatus.INCONCLUSIVE,
                obligations_remaining=("dimensions agree",),
                detail="an earlier stage failed, so dimensions were never compared",
                evidence={"codes": blocked},
            )
        bad = _codes(result.diagnostics.errors, "HML-D")
        if bad:
            return self._result(
                VerifierStatus.INVALID,
                obligations_checked=("dimensions agree",),
                obligations_remaining=("dimensions agree",),
                detail=f"dimensional errors: {bad}",
                evidence={"codes": bad},
            )
        return self._result(
            VerifierStatus.SUPPORTED_AND_VERIFIED,
            obligations_checked=("dimensions agree",),
            detail="every dimensional obligation the checker raised is satisfied",
        )


class EpistemicVerifier(_BaseVerifier):
    """Wraps :mod:`hamiltonian_lang.v1.epistemic_checks`.

    That checker is a **Python API**. ``docs/evaluation/PHASE1_LEAD_AUDIT.md`` §5a
    establishes that nothing on the ``hml check`` path imports
    :mod:`hamiltonian_lang.v1`, so no HML program can express an epistemic claim and the
    checker cannot see one. An HML candidate is therefore ``UNSUPPORTED``, and that is
    the honest answer rather than a vacuous pass.

    A candidate that supplies claims directly, through
    ``attachments["epistemic"] = {"claims": {...}, "uses": [(name, Site), ...]}``, is
    checked for real.
    """

    name = "epistemic_checker"
    version = "hml-v1-0.1.0"

    def supports(self, canonical_object: CanonicalObject, candidate: Candidate) -> SupportDecision:
        payload = candidate.attachments.get("epistemic")
        if payload is None:
            return SupportDecision(
                False,
                "no epistemic claims were supplied; the V1 epistemic layer is a Python "
                "API and is unreachable from HML source (Lead audit §5a), so an HML "
                "program carries nothing this checker can read",
                missing_capability=("hml-surface-for-epistemic-status",),
            )
        if not isinstance(payload, Mapping) or "claims" not in payload:
            return SupportDecision(
                False, "attachments['epistemic'] must be a mapping carrying 'claims'"
            )
        return SupportDecision(True)

    def verify(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> VerificationResult:
        decision = self.supports(canonical_object, candidate)
        if not decision.supported:
            return self._unsupported(decision)
        from ..v1.epistemic_checks import EpistemicChecker

        payload = dict(candidate.attachments["epistemic"])
        checker = EpistemicChecker()
        for claim_name, claim in dict(payload["claims"]).items():
            checker.declare(claim_name, claim)
        for use_name, site in list(payload.get("uses", ())):
            checker.use(use_name, site)
        report = checker.report()
        checked = tuple(f"claim:{n}" for n in dict(payload["claims"]))
        if report.violations:
            return self._result(
                VerifierStatus.INVALID,
                obligations_checked=checked,
                obligations_remaining=checked,
                detail=report.render(),
                evidence={"codes": [v.code for v in report.violations]},
            )
        return self._result(
            VerifierStatus.SUPPORTED_AND_VERIFIED,
            obligations_checked=checked,
            detail="no epistemic violation; every use is justified by its claim's status",
            evidence={"dependencies": [d.render() for d in report.dependencies]},
        )


# ---------------------------------------------------------------------------
# Semantic comparison
# ---------------------------------------------------------------------------


class CanonicalComparatorVerifier(_BaseVerifier):
    """Compares the candidate's content hash with the reference's.

    This is the project's only deterministic equivalence oracle. It is exact in one
    direction and silent in the other: **equal hashes mean the same semantic object; a
    difference means the objects differ, not that the candidate is mathematically
    wrong.** A different-but-equivalent formulation hashes differently, so a mismatch is
    reported with a counterexample only when the reference itself compiles, and even then
    the counterexample witnesses *structural inequality*, not falsity.
    """

    name = "canonical_comparator"
    version = "hml-canonical-0.1.0"

    def supports(self, canonical_object: CanonicalObject, candidate: Candidate) -> SupportDecision:
        base = _hml_only(candidate, "the canonical comparator")
        if not base.supported:
            return base
        if not canonical_object.content_hash and not canonical_object.source.strip():
            return SupportDecision(
                False,
                "the canonical object carries neither a content hash nor a reference "
                "source; there is nothing to compare against",
                missing_capability=("reference-semantic-object",),
            )
        return SupportDecision(True)

    def verify(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> VerificationResult:
        decision = self.supports(canonical_object, candidate)
        if not decision.supported:
            return self._unsupported(decision)

        reference_hash = canonical_object.content_hash
        if reference_hash is None:
            reference = compile_source(canonical_object.source)
            if not reference.ok():
                return self._result(
                    VerifierStatus.INCONCLUSIVE,
                    obligations_remaining=("candidate and reference denote one object",),
                    detail=(
                        "the reference source does not compile, so no comparison was "
                        "possible; this says nothing about the candidate"
                    ),
                    evidence={"reference_codes": [d.code for d in reference.diagnostics.errors]},
                )
            reference_hash = reference.hash()

        actual = compile_source(candidate.text)
        if not actual.ok():
            return self._result(
                VerifierStatus.INVALID,
                obligations_checked=("candidate and reference denote one object",),
                obligations_remaining=("candidate and reference denote one object",),
                detail="the candidate does not compile, so it denotes no object at all",
                evidence={"codes": [d.code for d in actual.diagnostics.errors]},
            )
        candidate_hash = actual.hash()
        if candidate_hash == reference_hash:
            return self._result(
                VerifierStatus.SUPPORTED_AND_VERIFIED,
                obligations_checked=("candidate and reference denote one object",),
                detail="identical alpha-invariant content hash",
                evidence={"content_hash": candidate_hash},
            )
        return self._result(
            VerifierStatus.SUPPORTED_AND_FAILED,
            obligations_checked=("candidate and reference denote one object",),
            obligations_remaining=("candidate and reference denote one object",),
            counterexample=Counterexample(
                description=(
                    "the candidate's canonical form differs from the reference's, so the "
                    "two are not the same semantic object"
                ),
                witness=f"candidate {candidate_hash[:16]} != reference {reference_hash[:16]}",
                produced_by=self.name,
            ),
            detail=(
                "structural inequality. An equivalent-but-differently-shaped encoding "
                "also lands here, so this is evidence of difference, not of falsity"
            ),
            evidence={"candidate_hash": candidate_hash, "reference_hash": reference_hash},
        )


# ---------------------------------------------------------------------------
# Backend-adjacent verifiers
# ---------------------------------------------------------------------------


class SympyExecutionVerifier(_BaseVerifier):
    """Renders the candidate through the SymPy backend and executes the module.

    A clean run returns ``INCONCLUSIVE``, never ``SUPPORTED_AND_VERIFIED``. The Lead
    audit states the reason plainly: execution proves the emitted module imports, builds
    its symbols and evaluates; it does not prove the SymPy expression means what the HML
    meant. A crash returns ``SUPPORTED_AND_FAILED`` with the traceback as evidence,
    because a negative result here *is* informative.

    Backend loss is reported as ``SEMANTIC_LOSS`` and takes precedence: a module that
    runs after its laws were dropped is not evidence about the laws.
    """

    name = "sympy_execution"
    version = "sympy-1.14.0"

    def __init__(self, *, timeout_s: int = 60, python: str | None = None) -> None:
        self.timeout_s = timeout_s
        self.python = python or sys.executable

    def supports(self, canonical_object: CanonicalObject, candidate: Candidate) -> SupportDecision:
        base = _hml_only(candidate, "the SymPy backend")
        if not base.supported:
            return base
        try:
            import sympy  # noqa: F401
        except ImportError:
            return SupportDecision(
                False, "sympy is not importable in this environment",
                missing_capability=("sympy",),
            )
        return SupportDecision(True)

    def verify(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> VerificationResult:
        decision = self.supports(canonical_object, candidate)
        if not decision.supported:
            return self._unsupported(decision)
        compiled = compile_source(candidate.text)
        if not compiled.ok():
            return self._result(
                VerifierStatus.INVALID,
                obligations_remaining=("the emitted SymPy module runs",),
                detail="the candidate does not compile, so nothing was emitted",
                evidence={"codes": [d.code for d in compiled.diagnostics.errors]},
            )
        rendered = compiled.render("sympy")
        losses = tuple(
            SemanticLoss(u.construct, u.reason, u.severity) for u in rendered.unsupported
        )
        if losses:
            return self._result(
                VerifierStatus.SEMANTIC_LOSS,
                obligations_remaining=("the emitted SymPy module runs",),
                semantic_loss=losses,
                detail=(
                    f"{len(losses)} construct(s) were not preserved by the SymPy backend; "
                    f"running what remains is not evidence about what was removed"
                ),
            )
        try:
            proc = subprocess.run(
                [self.python, "-c", rendered.text],
                capture_output=True, text=True, timeout=self.timeout_s, check=False,
            )
        except subprocess.TimeoutExpired:
            return self._result(
                VerifierStatus.INCONCLUSIVE,
                obligations_remaining=("the emitted SymPy module runs",),
                detail=f"the emitted module did not terminate within {self.timeout_s}s",
            )
        if proc.returncode != 0:
            return self._result(
                VerifierStatus.SUPPORTED_AND_FAILED,
                obligations_checked=("the emitted SymPy module runs",),
                obligations_remaining=("the emitted SymPy module runs",),
                counterexample=Counterexample(
                    description="the emitted SymPy module raised while evaluating",
                    witness=proc.stderr.strip()[-800:],
                    produced_by=self.name,
                ),
                detail=f"exit code {proc.returncode}",
                evidence={"exit_code": proc.returncode},
            )
        return self._result(
            VerifierStatus.INCONCLUSIVE,
            obligations_checked=("the emitted SymPy module runs",),
            obligations_remaining=("the SymPy expressions mean what the HML meant",),
            detail=(
                "the module executed cleanly. Execution is not semantic equivalence, so "
                "this is not a verification"
            ),
            evidence={"exit_code": 0},
        )


class LeanVerifier(_BaseVerifier):
    """Wraps :func:`hamiltonian_lang.v1.lean_verify.verify`, which is unchanged.

    Two measured facts bound what this can do, and neither is worked around here:

    * **Mathlib is absent.** A candidate mentioning real numbers, measures or the Mathlib
      notations is ``UNSUPPORTED``; it would fail to elaborate for an environmental
      reason, and reporting that as a failed proof would be wrong.
    * **The HML Lean backend emits `sorry` by design.** Since ``sorry`` is in
      ``FORBIDDEN_TACTICS``, backend output is rejected before Lean runs. This verifier
      therefore never sees a machine-generated proof it can accept, and the tests assert
      exactly that rather than pretending otherwise.

    Every rejecting Lean verdict maps away from ``SUPPORTED_AND_VERIFIED``. Nothing here
    broadens Lean support.
    """

    name = "lean"
    version = "hml-lean-verify-0.1.0"

    #: Tokens that only make sense with Mathlib present.
    MATHLIB_TOKENS = ("Mathlib", "ℝ", "ℕ", "Real", "MeasureTheory", "ENNReal")

    def __init__(self, *, timeout_s: int = 180) -> None:
        self.timeout_s = timeout_s

    def supports(self, canonical_object: CanonicalObject, candidate: Candidate) -> SupportDecision:
        if candidate.language is not CandidateLanguage.LEAN:
            return SupportDecision(
                False,
                f"this verifier reads Lean source; the candidate is {candidate.language}. "
                f"Emitting Lean from HML is source generation, and source generation is "
                f"not verification",
                missing_capability=("lean-candidate",),
            )
        mathlib_present, mathlib_reason = ENVIRONMENT_FACTS["mathlib"]
        hits = [t for t in self.MATHLIB_TOKENS if t in candidate.text]
        if hits and not mathlib_present:
            return SupportDecision(
                False,
                f"the candidate uses {hits}, which need Mathlib: {mathlib_reason}",
                missing_capability=("mathlib",),
            )
        from ..v1.lean_verify import lean_available

        if not lean_available():
            return SupportDecision(
                False, "no `lean` on PATH", missing_capability=("lean",)
            )
        return SupportDecision(True)

    def verify(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> VerificationResult:
        decision = self.supports(canonical_object, candidate)
        if not decision.supported:
            return self._unsupported(decision)
        from ..v1.lean_verify import LeanVerdict
        from ..v1.lean_verify import verify as lean_verify

        outcome = lean_verify(
            candidate.text,
            expected_statement=canonical_object.expected_statement,
            timeout_s=self.timeout_s,
        )
        obligation = ("the Lean theorem is proved without `sorry` or unexpected axioms",)
        if outcome.verdict is LeanVerdict.VERIFIED:
            return self._result(
                VerifierStatus.SUPPORTED_AND_VERIFIED,
                obligations_checked=obligation,
                detail=outcome.detail,
                evidence=outcome.to_dict(),
            )
        if outcome.verdict is LeanVerdict.NOT_ATTEMPTED:
            return self._unsupported(
                SupportDecision(False, outcome.detail, missing_capability=("lean",))
            )
        invalid = {
            LeanVerdict.REJECTED_COMPILE_ERROR,
            LeanVerdict.REJECTED_STATEMENT_MISMATCH,
            LeanVerdict.REJECTED_NO_THEOREM,
        }
        status = (
            VerifierStatus.INVALID
            if outcome.verdict in invalid
            else VerifierStatus.SUPPORTED_AND_FAILED
        )
        return self._result(
            status,
            obligations_checked=obligation,
            obligations_remaining=obligation,
            detail=f"{outcome.verdict}: {outcome.detail}",
            evidence=outcome.to_dict(),
        )


class StanVerifier(_BaseVerifier):
    """Always ``UNSUPPORTED``, for two independent reasons.

    ``stanc`` is absent from this machine, so no Stan artefact has ever been compiled.
    Even with ``stanc`` present, compiling a model would establish that the model
    compiles -- source generation is not verification, and no equivalence check between
    an HML object and a Stan program exists in this repository. Both reasons are reported
    so that installing ``stanc`` does not silently turn this into a passing verifier.
    """

    name = "stan"
    version = "hml-stan-0.1.0"

    def supports(self, canonical_object: CanonicalObject, candidate: Candidate) -> SupportDecision:
        stanc_present = shutil.which("stanc") is not None
        recorded, recorded_reason = ENVIRONMENT_FACTS["stanc"]
        reasons = [
            "no equivalence check between an HML object and a Stan program exists; "
            "emitting Stan is source generation, not verification"
        ]
        missing = ["stan-equivalence-check"]
        if not stanc_present:
            reasons.append(f"`stanc` is absent ({recorded_reason})")
            missing.append("stanc")
        elif not recorded:
            reasons.append(
                "`stanc` is now on PATH although the recorded probe says absent; the "
                "disagreement is reported rather than resolved by guessing"
            )
        return SupportDecision(False, "; ".join(reasons), missing_capability=tuple(missing))

    def verify(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> VerificationResult:
        return self._unsupported(self.supports(canonical_object, candidate))


# ---------------------------------------------------------------------------
# Federation and classification
# ---------------------------------------------------------------------------


class VerifierFederation:
    """Runs every registered verifier and collects the results in a stable order."""

    def __init__(self, verifiers: Sequence[Verifier]) -> None:
        names = [v.name for v in verifiers]
        if len(set(names)) != len(names):
            raise ValueError(f"verifier names must be unique, got {names}")
        self.verifiers = tuple(verifiers)

    def names(self) -> tuple[str, ...]:
        return tuple(v.name for v in self.verifiers)

    def versions(self) -> dict[str, str]:
        return {v.name: v.version for v in self.verifiers}

    def run(
        self, canonical_object: CanonicalObject, candidate: Candidate
    ) -> tuple[VerificationResult, ...]:
        return tuple(v.verify(canonical_object, candidate) for v in self.verifiers)


def default_federation(*, include_execution: bool = False) -> VerifierFederation:
    """The standard set.

    ``include_execution`` is off by default because
    :class:`SympyExecutionVerifier` spawns a subprocess. Its verdict is never positive,
    so leaving it out cannot turn an unverified episode into a verified one.
    """
    verifiers: list[Verifier] = [
        ParseVerifier(),
        ResolutionVerifier(),
        TypeCheckVerifier(),
        DimensionVerifier(),
        EpistemicVerifier(),
        CanonicalComparatorVerifier(),
        LeanVerifier(),
        StanVerifier(),
    ]
    if include_execution:
        verifiers.append(SympyExecutionVerifier())
    return VerifierFederation(verifiers)


def classify(results: Sequence[VerificationResult]) -> str:
    """Reduce a federation's results to one terminal verdict.

    The order of the tests is the policy, and it is pessimistic by construction::

        any INVALID                          -> INVALID
        any SEMANTIC_LOSS                    -> SEMANTIC_LOSS
        any SUPPORTED_AND_FAILED
              with a counterexample          -> DISPROVED
              without one                    -> INCONCLUSIVE
        nothing verified
              and every result UNSUPPORTED   -> UNSUPPORTED
              otherwise                      -> INCONCLUSIVE
        something verified
              but an obligation remains      -> INCONCLUSIVE
              or some result INCONCLUSIVE    -> INCONCLUSIVE
              otherwise                      -> VERIFIED

    The return value is the string form of
    :class:`hamiltonian_lang.improvement.episodes.Verdict`; it is returned as ``str`` so
    that this module does not import the episode schema and create a cycle.
    """
    statuses = [r.status for r in results]
    if not statuses:
        return "UNSUPPORTED"
    if VerifierStatus.INVALID in statuses:
        return "INVALID"
    if VerifierStatus.SEMANTIC_LOSS in statuses:
        return "SEMANTIC_LOSS"

    failed = [r for r in results if r.status is VerifierStatus.SUPPORTED_AND_FAILED]
    if failed:
        return "DISPROVED" if any(r.counterexample for r in failed) else "INCONCLUSIVE"

    verified = [r for r in results if r.status is VerifierStatus.SUPPORTED_AND_VERIFIED]
    if not verified:
        if all(s is VerifierStatus.UNSUPPORTED for s in statuses):
            return "UNSUPPORTED"
        return "INCONCLUSIVE"

    if any(r.obligations_remaining for r in results):
        return "INCONCLUSIVE"
    if VerifierStatus.INCONCLUSIVE in statuses:
        return "INCONCLUSIVE"
    return "VERIFIED"
