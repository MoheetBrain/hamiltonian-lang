"""Adversarial cases for the V1 concept kernel — Phase 10, deliverable 3.

Every case here is a **matched pair**: one thing V1 must reject, and one near-miss it
must accept. `docs/design/V1_EXPERIMENT_PLAN.md` §5 makes precision a preregistered
hypothesis (V1-H2) precisely because a checker that rejects everything has perfect recall
and is worthless. A rejection test with no acceptance twin measures nothing, so this file
refuses to contain one — ``test_every_pair_has_both_halves`` fails if it ever does.

Three layers of test, and the difference between them is the point:

1. **V0 baseline, LIVE.** For every case that can be written in V0 at all, the V0
   compiler is actually run and its verdict is compared against the ``v0_status``
   recorded in ``evaluation/v1/corpus.py``. `docs/design/V1_EXPERIMENT_PLAN.md` §4 asserts
   "V0 behaviour: accepts" for each of these classes; these tests turn that assertion into
   a checked fact, and they fail if a future V0 change makes it false.

2. **V1 epistemic layer, LIVE.** ``src/hamiltonian_lang/v1/epistemic.py`` exists, so the
   three cases it covers are executed for real and must pass now.

3. **Everything else, XFAIL with the missing interface named.** The remaining V1 modules
   are owned by other agents and do not exist yet. Those tests are written against the
   documented interface and marked ``xfail(strict=False)``, so that they turn green of
   their own accord the moment the module lands, and are never silently skipped in the
   meantime. A skipped adversarial test is how a semantic hole survives a release.

Nothing in this file imports a model, and nothing in it judges an output.
"""

from __future__ import annotations

import importlib

import pytest
from evaluation.v1.corpus import ADVERSARIAL_PAIRS, AdversarialPair

from hamiltonian_lang import compile_source

pytestmark = pytest.mark.adversarial

PAIRS = {p.id: p for p in ADVERSARIAL_PAIRS}
IDS = sorted(PAIRS)

#: The eleven cases `docs/design/V1_EXPERIMENT_PLAN.md` and the Phase 10 brief require.
#: `test_every_mandated_case_is_present` fails if one is dropped, so a case cannot leave
#: the suite by being quietly deleted from the table.
MANDATED = {
    "adv01_duplicate_concept_new_name": "a duplicate concept minted under a new name",
    "adv02_property_not_held": "a concept claiming a property it does not have",
    "adv03_pure_synonym": "a concept that compresses nothing",
    "adv04_fabricated_member": "Normal.density accepted, ArbitraryConcept.density fabricated",
    "adv05_yields_used_as_implies": "`yields` used where `implies` is required",
    "adv06_goal_discharged_by_evidence": "a goal discharged by Evidence rather than Proof",
    "adv07_prove_fail_to_reject": "prove(fail_to_reject(H0))",
    "adv08_p_value_as_posterior": "a p-value used as a posterior probability",
    "adv09_whp_without_regime": "with_high_probability with no regime",
    "adv10_estimate_is_unbiased": "'the estimate is unbiased'",
    "adv11_non_exhaustive_case_split": "a non-exhaustive case split",
}


# ---------------------------------------------------------------------------
# Which V1 modules exist yet
# ---------------------------------------------------------------------------


def _module_for(interface: str) -> str:
    """`"pkg.mod:attr"` -> `"pkg.mod"`."""
    return interface.split(":", 1)[0] if interface else ""


def _available(interface: str) -> bool:
    """Is the module AND the named attribute present?

    The attribute matters as much as the module: a V1 module that exists but does not
    expose the entry point this case needs leaves the hole open just as surely as a
    missing file, and reporting it as closed would be the more dangerous of the two
    mistakes.
    """
    mod_name = _module_for(interface)
    if not mod_name:
        return True
    try:
        obj = importlib.import_module(mod_name)
    except ImportError:
        return False
    _, _, attr_path = interface.partition(":")
    for part in (p for p in attr_path.split(".") if p):
        obj = getattr(obj, part, None)
        if obj is None:
            return False
    return True


def _xfail_reason(pair: AdversarialPair) -> str:
    return (
        f"{pair.layer}: `{pair.required_interface}` does not exist yet. Another agent owns "
        f"the V1 modules; this test is written against the documented interface and will "
        f"pass unchanged when that module lands. Until then the case is an OPEN semantic "
        f"hole, not a passing test."
    )


def _needs(pair: AdversarialPair):
    return pytest.mark.xfail(
        not _available(pair.required_interface),
        reason=_xfail_reason(pair),
        strict=False,
    )


def _param(pid: str):
    p = PAIRS[pid]
    return pytest.param(p, id=pid, marks=_needs(p))


ALL_PARAMS = [_param(pid) for pid in IDS]


# ---------------------------------------------------------------------------
# Layer 1 — the V0 baseline, executed live
# ---------------------------------------------------------------------------

_WITH_V0_SOURCE = [pytest.param(PAIRS[pid], id=pid) for pid in IDS if PAIRS[pid].v0_source]


@pytest.mark.parametrize("pair", _WITH_V0_SOURCE)
def test_recorded_v0_status_matches_the_real_compiler(pair: AdversarialPair):
    """The corpus records what V0 does; this runs V0 and checks it.

    `V1_EXPERIMENT_PLAN.md` §4 lists "V0 behaviour: accepts" for every one of these error
    classes. That claim is the baseline every V1 recall number is measured against, so it
    must be a fact rather than a remembered impression.
    """
    result = compile_source(pair.v0_source, pair.id)
    actual = "accepts" if result.ok() else "rejects"
    codes = [d.code for d in result.diagnostics.errors]
    assert actual == pair.v0_status, (
        f"{pair.id}: corpus records v0_status={pair.v0_status!r} but V0 {actual}. "
        f"diagnostics={codes}"
    )


@pytest.mark.parametrize("pair", _WITH_V0_SOURCE)
def test_v0_cannot_discriminate_the_pair(pair: AdversarialPair):
    """Where V0 accepts the error, it must accept the near-miss too — or it is not blind.

    This pins the exact shape of V0's failure. V0 does not reject these cases for the
    wrong reason and it does not accidentally catch them: it treats the error and the
    correct form identically, which is what makes its recall on this class **0.0** and
    its precision undefined. Any V1 improvement is measured against that.
    """
    if pair.v0_status != "accepts" or not pair.v0_accept_source:
        pytest.skip("no V0 near-miss source recorded for this pair")
    bad = compile_source(pair.v0_source, pair.id + ":reject")
    good = compile_source(pair.v0_accept_source, pair.id + ":accept")
    assert bad.ok() and good.ok(), (
        f"{pair.id}: V0 was expected to accept both halves indistinguishably; "
        f"bad.ok()={bad.ok()} good.ok()={good.ok()}"
    )


def test_v0_baseline_recall_over_the_expressible_cases_is_zero():
    """The single number the V1 recall claim is measured against.

    Reported here as an executed assertion rather than as prose in a report, because a
    baseline that lives only in prose drifts.
    """
    expressible = [p for p in ADVERSARIAL_PAIRS if p.v0_source]
    caught = [p for p in expressible
              if not compile_source(p.v0_source, p.id).ok()]
    assert caught == [], (
        f"V0 unexpectedly rejects {[p.id for p in caught]}. The baseline recorded in "
        f"docs/evaluation/HML_V1_CONCEPT_ABLATION_REPORT.md must be updated to match."
    )
    assert len(expressible) >= 4, "too few cases are expressible in V0 to state a baseline"


def test_cases_v0_cannot_express_are_recorded_as_such_not_as_v0_successes():
    """`not_expressible` is not a V0 win, and must never be counted as one.

    Seven of the eleven cases cannot be written in V0 at all — V0 has no `entails`, no
    `discharge`, no `case`, no `fail_to_reject`. Treating "V0 rejects this source" as
    "V0 caught the error" would manufacture a baseline out of a missing keyword.
    """
    for p in ADVERSARIAL_PAIRS:
        if p.v0_status == "not_expressible":
            assert not p.v0_source, (
                f"{p.id}: recorded not_expressible but carries a V0 source. Either it is "
                f"expressible, or the source tests a different thing."
            )


# ---------------------------------------------------------------------------
# Layer 2 — the V1 epistemic layer, which exists and must pass NOW
# ---------------------------------------------------------------------------


def test_prove_fail_to_reject_is_rejected():
    """adv07 — the one error L4 exists to make unrepresentable."""
    from hamiltonian_lang.v1.epistemic import (
        EpistemicClaim,
        EpistemicStatus,
        Justification,
    )

    claim = EpistemicClaim(
        EpistemicStatus.FAIL_TO_REJECT, "mu = 0",
        {"null": "H0", "alpha": "0.05", "p_value": "0.18"},
    )
    ok, reason = claim.may_be_used_as(Justification.PROOF)
    assert ok is False
    assert "prove" in reason.lower() or "evidence" in reason.lower()
    assert claim.justification is Justification.EVIDENCE


def test_the_near_miss_of_prove_fail_to_reject_is_accepted():
    """adv07's twin — the same evidence, used as evidence, must go through.

    Without this the previous test is satisfied by a checker that refuses everything.
    """
    from hamiltonian_lang.v1.epistemic import (
        EpistemicClaim,
        EpistemicStatus,
        Justification,
    )

    claim = EpistemicClaim(
        EpistemicStatus.FAIL_TO_REJECT, "mu = 0",
        {"null": "H0", "alpha": "0.05", "p_value": "0.18"},
    )
    ok, _ = claim.may_be_used_as(Justification.EVIDENCE)
    assert ok is True
    rendered = claim.render_english()
    assert "not evidence that H0 is true" in rendered, rendered


def test_goal_discharged_by_evidence_is_rejected():
    """adv06 — `discharge` requires a Proof."""
    from hamiltonian_lang.v1.epistemic import EpistemicClaim, EpistemicStatus

    evidence = EpistemicClaim(
        EpistemicStatus.CONSISTENT_WITH, "P", {"data": "D"}
    )
    assert evidence.discharges_goals() is False

    assumption = EpistemicClaim(EpistemicStatus.MODEL_CONDITIONAL, "P", {"model": "M"})
    assert assumption.discharges_goals() is False, (
        "assumed(P) must never discharge a goal (V1_KERNEL §7 item 7)"
    )


def test_goal_discharged_by_proof_is_accepted():
    """adv06's twin."""
    from hamiltonian_lang.v1.epistemic import EpistemicClaim, EpistemicStatus

    assert EpistemicClaim(EpistemicStatus.PROVED, "P").discharges_goals() is True
    assert EpistemicClaim(EpistemicStatus.DEFINITIONALLY_TRUE, "P").discharges_goals() is True


def test_with_high_probability_without_a_regime_is_rejected():
    """adv09 — a probabilistic qualifier with no regime names no proposition."""
    from hamiltonian_lang.v1.epistemic import (
        ContextError,
        EpistemicClaim,
        EpistemicStatus,
    )

    with pytest.raises(ContextError) as exc:
        EpistemicClaim(EpistemicStatus.WITH_HIGH_PROBABILITY, "the estimator is close")
    assert "bound_or_regime" in str(exc.value)


def test_with_high_probability_with_a_regime_is_accepted():
    """adv09's twin — the identical claim with the regime supplied."""
    from hamiltonian_lang.v1.epistemic import EpistemicClaim, EpistemicStatus

    claim = EpistemicClaim(
        EpistemicStatus.WITH_HIGH_PROBABILITY, "the estimator is close",
        {"bound_or_regime": "n -> infinity"},
    )
    assert "n -> infinity" in claim.render_english()


def test_every_prohibited_coercion_is_refused_and_identity_is_allowed():
    """The §7 conflation list, exhaustively, plus the precision guard.

    `spec/v1/semantic_objects.yaml::kill_criteria` sets L4's criterion as "any prohibited
    conflation type-checks". This is that criterion, executed. The identity half is the
    precision guard: a `coercion_allowed` that returns False unconditionally would satisfy
    the first loop and fail the second.
    """
    from hamiltonian_lang.v1.epistemic import (
        PROHIBITED_COERCIONS,
        Justification,
        coercion_allowed,
    )

    for (src, dst), why in PROHIBITED_COERCIONS.items():
        ok, reason = coercion_allowed(src, dst)
        assert ok is False, f"{src} -> {dst} type-checks; L4's kill criterion is met"
        assert reason == why

    for j in Justification:
        ok, _ = coercion_allowed(j, j)
        assert ok is True, f"identity coercion on {j} was refused; the checker is inert"


def test_evidence_never_reaches_proof_by_any_two_step_route():
    """No laundering path: Evidence -> X -> Proof must be closed for every X.

    A prohibition on the direct edge is worth nothing if a two-hop route exists. The
    V0 type system keeps ``Distribution[T]``, ``RandomVariable[T]`` and ``T`` apart the
    same way, and this is the V1 analogue of that check.
    """
    from hamiltonian_lang.v1.epistemic import Justification, coercion_allowed

    for mid in Justification:
        a, _ = coercion_allowed(Justification.EVIDENCE, mid)
        b, _ = coercion_allowed(mid, Justification.PROOF)
        assert not (a and b and mid is not Justification.PROOF), (
            f"Evidence launders into Proof via {mid}"
        )
    assert coercion_allowed(Justification.EVIDENCE, Justification.PROOF)[0] is False


def test_a_test_result_without_alpha_is_ill_formed():
    """`fail_to_reject` with no alpha is not a mathematical statement.

    This is the context rule, not the coercion rule, and it is a separate way the same
    error class gets in: a non-rejection reported with no significance level cannot be
    checked against anything.
    """
    from hamiltonian_lang.v1.epistemic import (
        ContextError,
        EpistemicClaim,
        EpistemicStatus,
    )

    with pytest.raises(ContextError):
        EpistemicClaim(EpistemicStatus.FAIL_TO_REJECT, "H0", {"null": "H0"})
    # the twin: fully specified, and therefore admissible
    EpistemicClaim(
        EpistemicStatus.FAIL_TO_REJECT, "H0",
        {"null": "H0", "alpha": "0.05", "p_value": "0.18"},
    )


# ---------------------------------------------------------------------------
# Layer 3 — the remaining cases, against the V1 modules' real interfaces
# ---------------------------------------------------------------------------
#
# These bind to the entry points named in each pair's `required_interface`. Where the
# module or attribute is absent the xfail marker reports which one, so the suite states
# exactly what would close the hole rather than going quiet about it.

_MINT_STRUCTURE = "the centred two-term form (a - b) + (a - b)"


def _concept(canonical_id: str, **overrides):
    """A minimal well-formed concept. Every field the schema requires, nothing more."""
    from hamiltonian_lang.v1.registry import Claim, ClaimStatus, Concept, Parameter, Provenance

    fields = {
        "canonical_id": canonical_id,
        "namespace": "AdversarialV1",
        "version": "1.0.0",
        "type_signature": "Real * Real -> Real",
        "domain": "Real * Real",
        "codomain": "Real",
        "formal_definition": "C(a, b) = (a - b) + (a - b)",
        "provenance": Provenance(proposed_by="tests/v1", proposed_at="2026-08-05"),
        "parameters": (Parameter(name="a", type="Real", role="left"),
                       Parameter(name="b", type="Real", role="right")),
        "invariants": (Claim(statement="C(a, a) = 0", status=ClaimStatus.PROVED,
                             discharged_by="lemma_centred_pair"),),
        "compresses": (_MINT_STRUCTURE,),
    }
    fields.update(overrides)
    return Concept(**fields)


def _candidate(concept, *, compression: bool = True, claims=()):
    from hamiltonian_lang.v1.minting import (
        CompressionEvidence,
        ConceptCandidate,
        Example,
    )

    return ConceptCandidate(
        concept=concept,
        examples=(Example("C(3, 1) = 4", lambda: True),),
        compression=(
            (CompressionEvidence(
                structure=_MINT_STRUCTURE,
                occurrences=("examples/site_one.hml", "examples/site_two.hml"),
                expansion="(a - b) + (a - b)",
                abbreviation="C(a, b)",
            ),) if compression else ()
        ),
        claims=claims,
    )


@_needs(PAIRS["adv01_duplicate_concept_new_name"])
def test_duplicate_concept_under_a_new_name_is_rejected():
    """adv01 — the same typed structure, a different identifier.

    The reject half and the accept half share a registry deliberately: the specialisation
    is offered to the *same* registry that has just refused the duplicate, so a matcher
    that rejects on any structural neighbourhood fails the second assertion.
    """
    from hamiltonian_lang.v1.minting import mint
    from hamiltonian_lang.v1.registry import ConceptRegistry, Lifecycle, Parameter

    reg = ConceptRegistry()
    assert mint(_candidate(_concept("CentredPair")), reg).verdict is Lifecycle.ADMITTED

    duplicate = mint(_candidate(_concept("CentredPairRenamed")), reg)
    assert duplicate.verdict is not Lifecycle.ADMITTED, PAIRS[
        "adv01_duplicate_concept_new_name"].reject_reason
    assert duplicate.verdict is Lifecycle.DUPLICATE
    assert duplicate.duplicate_of == "CentredPair"

    specialisation = mint(_candidate(_concept(
        "CentredPairOnAnInterval",
        type_signature="Real * Real * Real -> Real",
        domain="Real * Real * Real",
        formal_definition="C_I(a, b, r) = ((a - b) + (a - b)) restricted to |a| <= r",
        parameters=(Parameter(name="a", type="Real", role="left"),
                    Parameter(name="b", type="Real", role="right"),
                    Parameter(name="r", type="Real", role="radius")),
    )), reg)
    assert specialisation.verdict is Lifecycle.ADMITTED, PAIRS[
        "adv01_duplicate_concept_new_name"].accept_reason


@_needs(PAIRS["adv02_property_not_held"])
def test_a_property_claimed_without_evidence_is_not_recorded_as_established():
    """adv02 — claiming `proved` with no proof must not produce a `proved` record.

    The concept may still be admitted; what must not happen is the claim surviving at the
    status it was claimed at. A registry that records an unsupported claim as proved
    launders a conjecture into a theorem, which is the failure this case exists to catch.
    """
    from hamiltonian_lang.v1.minting import PropertyClaim, mint
    from hamiltonian_lang.v1.registry import ClaimStatus, ConceptRegistry

    reg = ConceptRegistry()
    unsupported = mint(_candidate(
        _concept("SymmetricKernel"),
        claims=(PropertyClaim(statement="positive definite",
                              claimed_status=ClaimStatus.PROVED),),
    ), reg)
    adjudged = {a.statement: a for a in unsupported.claim_adjudications}
    got = adjudged["positive definite"]
    assert got.claimed_status is ClaimStatus.PROVED
    assert got.status is not ClaimStatus.PROVED, PAIRS["adv02_property_not_held"].reject_reason
    assert got.status is ClaimStatus.UNSUPPORTED

    reg2 = ConceptRegistry()
    honest = mint(_candidate(
        _concept("SymmetricKernelConjecturedPD"),
        claims=(PropertyClaim(statement="positive definite",
                              claimed_status=ClaimStatus.CONJECTURED),),
    ), reg2)
    kept = {a.statement: a for a in honest.claim_adjudications}["positive definite"]
    assert kept.status is ClaimStatus.CONJECTURED, PAIRS["adv02_property_not_held"].accept_reason


@_needs(PAIRS["adv03_pure_synonym"])
def test_a_concept_that_compresses_nothing_is_rejected():
    """adv03 — a one-to-one renaming of an existing primitive."""
    from hamiltonian_lang.v1.minting import mint
    from hamiltonian_lang.v1.registry import ConceptRegistry, Lifecycle

    reg = ConceptRegistry()
    synonym = mint(
        _candidate(_concept("AverageValue", compresses=()), compression=False), reg)
    assert synonym.verdict is not Lifecycle.ADMITTED, PAIRS["adv03_pure_synonym"].reject_reason
    assert synonym.compression_demonstrated is False

    reg2 = ConceptRegistry()
    compressing = mint(_candidate(_concept("CenteredSecondMoment")), reg2)
    assert compressing.verdict is Lifecycle.ADMITTED, PAIRS["adv03_pure_synonym"].accept_reason
    assert compressing.compression_demonstrated is True


@_needs(PAIRS["adv04_fabricated_member"])
def test_a_fabricated_member_does_not_resolve_and_a_declared_one_does():
    """adv04 — `Normal.density` resolves, `ArbitraryConcept.density` does not.

    Both halves in one test because the pair *is* the assertion: a resolver that refuses
    every dotted reference passes the first half and fails the second, and a resolver with
    a productive suffix rule passes the second and fails the first.
    """
    from hamiltonian_lang.v1.morphology import Morphology, MorphologyError, Role

    m = Morphology()
    m.declare_role("Normal", Role.MEASURE, "Measure[Real]", "the dominating measure")
    m.declare_role("Normal", Role.DENSITY, "Real -> NonNegativeReal",
                   "the density with respect to Lebesgue measure")

    assert m.has("Normal", Role.DENSITY) is True
    assert m.resolve("Normal", Role.DENSITY).concept_id == "Normal"

    assert m.has("ArbitraryConcept", Role.DENSITY) is False
    with pytest.raises(MorphologyError):
        m.resolve("ArbitraryConcept", Role.DENSITY)


@_needs(PAIRS["adv04_fabricated_member"])
def test_no_member_is_manufactured_by_a_string_rule():
    """The mechanism behind adv04, asserted directly.

    `docs/design/V1_KERNEL.md` §5 forbids productive morphology over mathematical
    vocabulary. This checks the prohibition is a property of the implementation and not
    an intention in a docstring.
    """
    from hamiltonian_lang.v1.morphology import STRING_DERIVATION_IS_PROHIBITED, Morphology, Role

    assert STRING_DERIVATION_IS_PROHIBITED
    m = Morphology()
    m.declare_role("Estimation", Role.ESTIMATOR, "Sample -> Real", "the estimator")
    # `estimate` is NOT derivable from `estimator` by dropping a suffix.
    assert m.has("Estimation", Role.ESTIMAND) is False


@_needs(PAIRS["adv05_yields_used_as_implies"])
def test_an_algebraic_rewrite_does_not_coerce_to_a_logical_implication():
    """adv05 — Derivation (L2) is not Entailment (L3), in both directions."""
    from hamiltonian_lang.v1.transformation import EdgeKind, edge_kind_coercion_allowed

    forward, reason = edge_kind_coercion_allowed(
        EdgeKind.ALGEBRAIC, EdgeKind.LOGICAL_IMPLICATION)
    assert forward is False, PAIRS["adv05_yields_used_as_implies"].reject_reason
    assert reason.strip()

    backward, _ = edge_kind_coercion_allowed(
        EdgeKind.LOGICAL_IMPLICATION, EdgeKind.ALGEBRAIC)
    assert backward is False, "the prohibition must hold in both directions"

    same, _ = edge_kind_coercion_allowed(EdgeKind.ALGEBRAIC, EdgeKind.ALGEBRAIC)
    assert same is True, "a rewrite used as a rewrite was refused; the checker is inert"


@_needs(PAIRS["adv06_goal_discharged_by_evidence"])
def test_a_goal_discharged_by_evidence_is_reported_and_by_proof_is_not():
    """adv06 — `discharge` is a Proof site."""
    from hamiltonian_lang.v1.epistemic import EpistemicClaim, EpistemicStatus, Justification
    from hamiltonian_lang.v1.epistemic_checks import REQUIRED_JUSTIFICATION_BY_SITE, Site

    assert REQUIRED_JUSTIFICATION_BY_SITE[Site.DISCHARGE] is Justification.PROOF

    evidence = EpistemicClaim(EpistemicStatus.CONSISTENT_WITH, "P", {"data": "D"})
    assert evidence.discharges_goals() is False, PAIRS[
        "adv06_goal_discharged_by_evidence"].reject_reason
    assert evidence.may_be_used_as(Justification.PROOF)[0] is False

    proof = EpistemicClaim(EpistemicStatus.PROVED, "P")
    assert proof.discharges_goals() is True, PAIRS[
        "adv06_goal_discharged_by_evidence"].accept_reason


@_needs(PAIRS["adv08_p_value_as_posterior"])
def test_p_value_does_not_coerce_to_a_posterior():
    """adv08 — PValue is its own type with no route to a posterior probability.

    OPEN at the time of writing. `V1_KERNEL` §7 item 3 and
    `spec/v1/semantic_objects.yaml::no_coercion_between` both name this prohibition, and
    no V1 module implements it: there is no ``PValue`` type anywhere in
    ``src/hamiltonian_lang/v1/``, and V0 types both sides as ``Probability``, so the
    conflation type-checks today. This test names the gap rather than hiding it.
    """
    from hamiltonian_lang.v1 import types as v1types

    assert v1types.coerces(v1types.PValue, v1types.PosteriorProbability) is False
    assert v1types.coerces(v1types.PValue, v1types.PValue) is True


@_needs(PAIRS["adv10_estimate_is_unbiased"])
def test_unbiasedness_attaches_to_the_estimator_not_the_estimate():
    """adv10 — the family confusion `V1_KERNEL` §5 names as the flagship type error."""
    from hamiltonian_lang.v1.morphology import (
        EstimationRole,
        RoleTypeError,
        attribute_property,
    )

    with pytest.raises(RoleTypeError):
        attribute_property("unbiased", to=EstimationRole.ESTIMATE)
    # the twin: the same property on the member that can carry it
    attribute_property("unbiased", to=EstimationRole.ESTIMATOR)


@_needs(PAIRS["adv10_estimate_is_unbiased"])
def test_the_five_estimation_members_do_not_substitute_for_one_another():
    """The mechanism behind adv10. Procedure, estimator, estimate and law are four
    objects, and no pair of them is interchangeable."""
    from hamiltonian_lang.v1.morphology import EstimationRole, RoleTypeError, check_substitution

    roles = list(EstimationRole)
    for src in roles:
        check_substitution(src, src)  # identity must be allowed, or nothing is
        for dst in roles:
            if src is dst:
                continue
            with pytest.raises(RoleTypeError):
                check_substitution(src, dst)


@_needs(PAIRS["adv11_non_exhaustive_case_split"])
def test_non_exhaustive_case_split_is_reported():
    """adv11 — `x > 0` and `x < 0` leave `x = 0` uncovered."""
    from hamiltonian_lang.v1.discourse import DiscourseState, check_exhaustive

    gap = check_exhaustive(["x > 0", "x < 0"])
    assert gap.decided is True, "the checker could not decide a split it must decide"
    assert gap.exhaustive is False, PAIRS["adv11_non_exhaustive_case_split"].reject_reason
    assert gap.uncovered

    state = DiscourseState("Adv11")
    state.consider_case("c1", "x > 0", split="s")
    state.consider_case("c2", "x < 0", split="s")
    assert state.end_case() is not None, "the gap was not reported at end_case"


@_needs(PAIRS["adv11_non_exhaustive_case_split"])
def test_a_split_closed_by_otherwise_is_accepted():
    """adv11's twin — `otherwise` is the complement branch and needs no proof.

    Note where the two halves live. ``check_exhaustive`` is a decider over *conditions*
    and treats the token ``otherwise`` as an undecidable condition, returning
    ``decided=False``; the complement branch is modelled one level up, as
    ``Case(complement=True)``. Asserting the accept half against ``check_exhaustive``
    would be asserting against the wrong layer, and the failure would look like a bug in
    the checker rather than a mistake in the test.
    """
    from hamiltonian_lang.v1.discourse import DiscourseState

    state = DiscourseState("Adv11Accept")
    state.consider_case("c1", "x > 0", split="s")
    assert state.otherwise() is None
    assert state.end_case() is None, PAIRS["adv11_non_exhaustive_case_split"].accept_reason


@_needs(PAIRS["adv11_non_exhaustive_case_split"])
def test_otherwise_is_not_decidable_as_a_bare_condition():
    """A gap worth recording rather than working around.

    ``check_exhaustive(["x > 0", "otherwise"])`` returns ``decided=False``. That is the
    right answer for a condition decider — ``otherwise`` is not a condition — but it means
    any caller that reaches for ``check_exhaustive`` alone will fail to recognise the one
    construct `V1_KERNEL` §4 says makes a split exhaustive by construction. The two must
    be used together, and this test pins that coupling so it cannot be broken silently.
    """
    from hamiltonian_lang.v1.discourse import check_exhaustive

    verdict = check_exhaustive(["x > 0", "otherwise"])
    assert verdict.decided is False
    assert verdict.exhaustive is False
    assert "decidable fragment" in verdict.reason


# ---------------------------------------------------------------------------
# Meta-tests — the suite's own integrity
# ---------------------------------------------------------------------------


def test_every_mandated_case_is_present():
    missing = sorted(set(MANDATED) - set(PAIRS))
    assert not missing, f"mandated adversarial cases are missing: {missing}"


@pytest.mark.parametrize("pair", [pytest.param(PAIRS[p], id=p) for p in IDS])
def test_every_pair_has_both_halves(pair: AdversarialPair):
    """A rejection case with no acceptance twin makes precision unmeasurable."""
    assert pair.reject_case.strip(), f"{pair.id}: empty reject case"
    assert pair.accept_case.strip(), f"{pair.id}: empty accept case"
    assert pair.reject_case.strip() != pair.accept_case.strip(), (
        f"{pair.id}: the two halves are identical, so the pair discriminates nothing"
    )
    assert pair.reject_reason.strip() and pair.accept_reason.strip()


@pytest.mark.parametrize("pair", [pytest.param(PAIRS[p], id=p) for p in IDS])
def test_every_pair_names_the_interface_that_would_close_it(pair: AdversarialPair):
    """An open hole must say what would close it, or it cannot be scheduled."""
    assert pair.required_interface, f"{pair.id}: no required_interface recorded"
    assert ":" in pair.required_interface, (
        f"{pair.id}: required_interface must be 'module:attr', got "
        f"{pair.required_interface!r}"
    )


def test_open_holes_are_counted_and_named():
    """A single place that says how much of V1's claim is currently unimplemented.

    This test never fails on the count. It exists so the number appears in the test log
    rather than only in a document that can go stale.
    """
    open_ = [p.id for p in ADVERSARIAL_PAIRS if not _available(p.required_interface)]
    closed = [p.id for p in ADVERSARIAL_PAIRS if _available(p.required_interface)]
    assert len(open_) + len(closed) == len(ADVERSARIAL_PAIRS)
    print(f"\nV1 adversarial coverage: {len(closed)} implemented, {len(open_)} open")
    for pid in open_:
        print(f"  OPEN  {pid}  needs {PAIRS[pid].required_interface}")
