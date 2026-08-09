"""The checked-certificate boundary, written to break it.

Every test here is an attempt to get something through the gate that should not go
through: an unregistered checker, a checker that raises, a checker that validates a
different proposition than the one claimed, a forged `CheckedEvidence`, a stale context, a
payload that lies. The boundary is the one place where non-kernel capability becomes
evidence, so its failure mode is the failure mode of everything built on top of it.

The two tests that inject a deliberately broken checker into the registry are doing
something the language itself cannot: source has no way to register one. That is the point
being demonstrated — the registry is reachable from Python, and only from Python.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import EvidenceStatus, Literal
from hamiltonian_lang.reasoning import certificates as C


def _compile(src: str):
    return compile_source(src, "<cert>")


def _status(src: str, label: str = "e1") -> str:
    return _compile(src).reasoning.evidence_status.get(label, "<absent>")


ARITHMETIC = "module A\nevidence e1 : entails 5.0 - 2.0 = 3.0 by {checker}()\n"


# --- registry discipline ----------------------------------------------------


def test_every_registered_checker_declares_a_trust_basis():
    """An unstated trust basis is an unaudited one, so the registry refuses empty ones."""
    assert C.CHECKERS, "the registry is empty; the boundary would accept nothing"
    for name, spec in C.CHECKERS.items():
        assert spec.trust.strip(), f"{name} declares no trust basis"
        assert spec.fragment.strip(), f"{name} declares no supported fragment"
        assert spec.judgements, f"{name} declares no judgements"


def test_symbolic_equivalence_is_deliberately_not_registered():
    """SPEC 2.7. It rests on raw SymPy flags with no independent HML replay.

    Registering it would let `simplify(a - b) == 0` manufacture VERIFIED, which is exactly
    the oracle-to-proof promotion the evidence-kind split exists to prevent. If somebody
    later adds it, this test should fail loudly and force the trust argument to be made.
    """
    for name in C.checker_names():
        assert "symbolic" not in name and "sympy" not in name.lower()


def test_source_cannot_register_a_checker():
    """There is no registration path reachable from a module being checked."""
    assert not hasattr(C, "register")
    assert "register" not in C.__all__


# --- fail-closed at the gate ------------------------------------------------


def test_unknown_checker_is_rejected():
    r = _compile(ARITHMETIC.format(checker="always_valid_v1"))
    assert not r.ok()
    assert _status(ARITHMETIC.format(checker="always_valid_v1")) == EvidenceStatus.REJECTED
    assert any("not a registered trusted checker" in str(d) for d in r.diagnostics)


def test_a_checker_may_not_reach_a_judgement_it_does_not_offer():
    """`closed_eval_v1` decides arithmetic; it may not pronounce on non-entailment."""
    src = (
        "module A\nvar P : Bool\nassume a1 : P\n"
        "evidence e1 : determines_neither P from a1 by closed_eval_v1()\n"
    )
    r = _compile(src)
    assert not r.ok()
    assert any("cannot reach judgement" in str(d) for d in r.diagnostics)


def test_a_false_arithmetic_claim_is_rejected():
    assert _status(ARITHMETIC.format(checker="closed_eval_v1").replace("3.0", "4.0")) == (
        EvidenceStatus.REJECTED
    )


def test_an_open_claim_is_rejected_by_the_closed_evaluator():
    """`closed_eval_v1` is for *closed* propositions. A free name is outside its fragment."""
    src = "module A\nvar x : Real\nevidence e1 : entails x - x = 0.0 by closed_eval_v1()\n"
    assert _status(src) == EvidenceStatus.REJECTED


def test_a_claim_needing_definitions_is_refused_by_the_plain_evaluator():
    """The two adapters have disjoint jobs, and each says so rather than overlapping."""
    src = (
        "module A\ndef f(x : Real) : Real := x + 1.0\n"
        "evidence e1 : entails f(3.0) = 4.0 by closed_eval_v1()\n"
    )
    r = _compile(src)
    assert not r.ok()
    assert any("definition_unfold_v1" in str(d) for d in r.diagnostics)


def test_definition_unfolding_validates_a_dependency_chain():
    src = (
        "module A\n"
        "def f(x : Real) : Real := x + 1.0\n"
        "def g(x : Real) : Real := 2.0 * f(x)\n"
        "evidence e1 : entails g(3.0) = 8.0 by definition_unfold_v1()\n"
    )
    assert _status(src) == EvidenceStatus.VALID
    assert _status(src.replace("8.0", "9.0")) == EvidenceStatus.REJECTED


def test_evidence_citing_an_unestablished_claim_is_rejected():
    src = (
        "module A\nvar P : Bool\ngoal g1 : P\n"
        "evidence e1 : entails 5.0 - 2.0 = 3.0 from g1 by closed_eval_v1()\n"
    )
    r = _compile(src)
    assert not r.ok()
    assert _status(src) == EvidenceStatus.REJECTED


# --- CheckedEvidence is unforgeable ----------------------------------------


def test_checked_evidence_cannot_be_constructed_directly():
    """"This was checked" must be a fact about the code path, not an attachable label."""
    with pytest.raises(TypeError):
        C.CheckedEvidence(
            envelope=None,
            kind=C.EvidenceKind.CHECKED_CERTIFICATE,
            established=None,
            checker="closed_eval_v1",
        )


def test_only_verifying_kinds_can_support_verified():
    assert C.EvidenceKind.UNTRUSTED_ORACLE not in C.VERIFYING_KINDS
    assert C.EvidenceKind.NUMERIC_BOUND not in C.VERIFYING_KINDS
    assert C.EvidenceKind.NONE not in C.VERIFYING_KINDS
    assert C.EvidenceKind.NATIVE_KERNEL in C.VERIFYING_KINDS
    assert C.EvidenceKind.CHECKED_CERTIFICATE in C.VERIFYING_KINDS


# --- misbehaving checkers ---------------------------------------------------


def _install(monkeypatch, name: str, fn, judgements=None):
    spec = C.TrustedChecker(
        name=name,
        judgements=judgements or frozenset({C.JudgementKind.ENTAILS}),
        validate=fn,
        trust="test double",
        fragment="test double",
    )
    monkeypatch.setitem(C.CHECKERS, name, spec)


def test_a_checker_that_raises_is_rejected_not_propagated(monkeypatch):
    """A guard that crashes must fail closed, and must not abort the compile."""

    def boom(envelope, ctx):
        raise RuntimeError("solver exploded")

    _install(monkeypatch, "boom_v1", boom)
    r = _compile(ARITHMETIC.format(checker="boom_v1"))
    assert not r.ok()
    assert any("solver exploded" in str(d) for d in r.diagnostics)


def test_a_checker_that_establishes_something_else_is_rejected(monkeypatch):
    """The realistic checker bug: validating a proposition adjacent to the claim."""

    def wrong(envelope, ctx):
        return C.CheckerVerdict(
            True, "ok", established=Literal(value=1.0, raw="1.0")
        )

    _install(monkeypatch, "wrong_v1", wrong)
    r = _compile(ARITHMETIC.format(checker="wrong_v1"))
    assert not r.ok()
    assert any("is not the stated claim" in str(d) for d in r.diagnostics)


def test_a_checker_that_says_valid_without_naming_anything_is_rejected(monkeypatch):
    def vague(envelope, ctx):
        return C.CheckerVerdict(True, "trust me")

    _install(monkeypatch, "vague_v1", vague)
    r = _compile(ARITHMETIC.format(checker="vague_v1"))
    assert not r.ok()
    assert any("without naming what it established" in str(d) for d in r.diagnostics)


def test_a_checker_returning_a_non_verdict_is_rejected(monkeypatch):
    _install(monkeypatch, "junk_v1", lambda envelope, ctx: True)
    r = _compile(ARITHMETIC.format(checker="junk_v1"))
    assert not r.ok()
    assert any("not a verdict" in str(d) for d in r.diagnostics)


# --- envelope binding -------------------------------------------------------


def test_claim_hash_mismatch_is_rejected():
    """A certificate issued for one claim may not be spent on another."""
    env = C.CertificateEnvelope(
        certificate_type="closed_eval_v1",
        certificate_version=1,
        checker="closed_eval_v1",
        judgement=C.JudgementKind.ENTAILS,
        claim_hash="not-the-claim",
        context_hash="ctx",
        premise_hashes=(),
    )
    claim = Literal(value=1.0, raw="1.0")
    ev, reason = C.check(
        env, claim, C.CheckerContext(), current_context_hash="ctx"
    )
    assert ev is None and "different claim" in reason


def test_context_hash_mismatch_is_rejected():
    from hamiltonian_lang.backends.canonical import expr_identity

    claim = Literal(value=1.0, raw="1.0")
    env = C.CertificateEnvelope(
        certificate_type="closed_eval_v1",
        certificate_version=1,
        checker="closed_eval_v1",
        judgement=C.JudgementKind.ENTAILS,
        claim_hash=expr_identity(claim),
        context_hash="issued-under-this",
        premise_hashes=(),
    )
    ev, reason = C.check(
        env, claim, C.CheckerContext(), current_context_hash="but-spent-under-that"
    )
    assert ev is None and "stale context" in reason


def test_context_hash_is_order_independent_but_membership_sensitive():
    """Γ is a set: reordering it is the same theory, adding to it is not."""
    assert C.context_hash(["a", "b"]) == C.context_hash(["b", "a"])
    assert C.context_hash(["a", "b"]) != C.context_hash(["a", "b", "c"])


def test_validation_is_deterministic():
    src = ARITHMETIC.format(checker="closed_eval_v1")
    assert _status(src) == _status(src) == EvidenceStatus.VALID
