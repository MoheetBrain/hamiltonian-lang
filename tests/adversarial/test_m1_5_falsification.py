"""Independent falsification of the four M1.5 subsystems that reported themselves ready.

What this file is
-----------------
Every subsystem below published a specific claim. This suite tries to make each claim
false and records the result either way. A test that *passes* here is an attack that was
resisted; a test marked ``xfail`` names a defect that was reproduced and is not fixed
here — Agent 4 falsifies, it does not repair.

Why ``xfail(strict=False)`` and not ``strict=True``
---------------------------------------------------
``tests/adversarial/test_rejections.py`` uses ``strict=True`` deliberately, so that a fix
shows up as a failure and forces the reason to be updated. That is the right default for a
suite written against a settled tree. It is the wrong default here: three other agents are
landing changes to ``evaluation/acq0/``, ``src/hamiltonian_lang/{repair,context_broker}/``
and ``evaluation/corpus_governance/`` concurrently with this one, and a strict xfail would
convert one of their fixes into a gate failure in a run neither of us controls. The
defects are therefore recorded in
``docs/evaluation/M1_5_FALSIFICATION_REPORT.md`` as the durable record, and each xfail
below cites the finding id there. When a defect is fixed, delete its test's marker.

Provenance
----------
Every ``xfail`` reason below records behaviour **measured** on this tree at
``57459a1`` (branch ``integration/m1.5-paper-derived-closeout``) on 2026-08-06, offline,
with no model call of any kind.

Running::

    .venv/bin/python -m pytest tests/adversarial/test_m1_5_falsification.py -q
"""

from __future__ import annotations

import concurrent.futures as cf
import json

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends.canonical import canonical_json, content_hash
from hamiltonian_lang.equivalence import (
    Endpoint,
    EquivalenceScorer,
    EquivalenceStatus,
)
from hamiltonian_lang.improvement.state import (
    Hypothesis,
    HypothesisMixingError,
    require_single_hypothesis,
)
from hamiltonian_lang.improvement.verification import (
    Candidate,
    CandidateLanguage,
    CanonicalObject,
    classify,
    default_federation,
)
from hamiltonian_lang.verification.obligations import verify_source
from hamiltonian_lang.verification.obligations.engine import GlobalVerdict

try:  # ``evaluation/acq0/budget/`` is in flight under another agent.
    import evaluation.acq0.budget.slots as _budget_slots  # noqa: F401
except Exception as _exc:  # noqa: BLE001 - absence is a skip, not a failure
    _BUDGET_IMPORT_ERROR: str | None = f"{type(_exc).__name__}: {_exc}"
else:
    _BUDGET_IMPORT_ERROR = None

pytestmark = pytest.mark.adversarial


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compare(reference: str, candidate: str) -> EquivalenceStatus:
    return EquivalenceScorer().compare(
        reference, candidate, endpoint=Endpoint.ENCODING_EQUIVALENCE
    ).status


def federated(source: str) -> str:
    """The federation's terminal verdict for ``source`` compared against itself."""
    return classify(
        default_federation().run(
            CanonicalObject(object_id="falsification", source=source),
            Candidate(text=source, language=CandidateLanguage.HML),
        )
    )


def _module(*statements: str) -> str:
    return "module M\n\n" + "\n".join(statements) + "\n"


# ===========================================================================
# TARGET 1 -- the equivalence scorer: precision 1.000, zero false-positive
#             equivalences over 49 pairs.
# ===========================================================================
#
# The required probes, at the vocabulary the benchmark corpus uses. These are the
# cases the corpus already covers and they hold.


def test_required_probe_implication_direction_is_refused():
    """``p => q`` is not ``q => p``. Corpus case ``nearmiss.converse``."""
    status = compare(
        _module("param p : Bool", "param q : Bool", "prove p implies q"),
        _module("param p : Bool", "param q : Bool", "prove q implies p"),
    )
    assert status is EquivalenceStatus.VERIFIED_NONEQUIVALENT


def test_required_probe_quantifier_alternation_is_refused():
    """``forall x . exists y`` entails ``exists y . forall x`` and not conversely."""
    status = compare(
        _module("prove forall x : Real . exists y : Real . y > x"),
        _module("prove exists y : Real . forall x : Real . y > x"),
    )
    assert status is EquivalenceStatus.VERIFIED_NONEQUIVALENT


def test_required_probe_pvalue_is_not_probability():
    """``PValue`` and ``Probability`` are the same subset of [0,1], different objects."""
    status = compare(_module("param p : Probability"), _module("param p : PValue"))
    assert status is EquivalenceStatus.VERIFIED_NONEQUIVALENT


def test_required_probe_power_is_not_associative():
    """``(a^b)^c`` is not ``a^(b^c)``; ``^`` is deliberately not flattened."""
    decls = ("param a : Real", "param b : Real", "param c : Real")
    status = compare(
        _module(*decls, "def r := (a ^ b) ^ c"),
        _module(*decls, "def r := a ^ (b ^ c)"),
    )
    assert status in (
        EquivalenceStatus.VERIFIED_NONEQUIVALENT,
        EquivalenceStatus.COUNTEREXAMPLE_FOUND,
    )


# -- FINDING F-1 ------------------------------------------------------------
#
# ``matching.strict_match`` enables the module-level name lock only when the two
# modules declare *exactly* the same vocabulary::
#
#     locked = bool(vocabulary) and vocabulary == declared_names(candidate)
#
# Renaming one declaration that plays no part in the claim makes the vocabularies
# unequal, the lock switches off, and Tier 1 is then free to permute the two names
# that do carry the claim. The engine certifies the very pairs it refutes when the
# spare name happens to match.

_F1 = (
    "F-1: the Tier-1 module-level name lock is all-or-nothing on exact vocabulary "
    "equality (matching.py strict_match), so renaming one unrelated declaration "
    "disables it and Tier 1 certifies a role swap that the same engine refutes when "
    "the vocabularies happen to coincide"
)


@pytest.mark.xfail(reason=_F1, strict=False)
@pytest.mark.parametrize(
    ("claim", "left", "right"),
    [
        ("implication direction", "prove p implies q", "prove q implies p"),
        ("subtraction order", "def r := p - q", "def r := q - p"),
        ("comparison direction", "require p > q", "require q > p"),
    ],
    ids=["converse", "subtraction", "comparison"],
)
def test_f1_spare_rename_must_not_flip_the_verdict(claim, left, right):
    """The same claim, with one irrelevant declaration spelled differently.

    ``spare`` and ``filler`` are declared, never referenced, and cannot change what
    either module asserts. The verdict must not depend on their spelling.
    """
    scalar = "Bool" if "implies" in left else "Real"
    locked = compare(
        _module(f"param p : {scalar}", f"param q : {scalar}", f"param spare : {scalar}", left),
        _module(f"param p : {scalar}", f"param q : {scalar}", f"param spare : {scalar}", right),
    )
    unlocked = compare(
        _module(f"param p : {scalar}", f"param q : {scalar}", f"param spare : {scalar}", left),
        _module(f"param p : {scalar}", f"param q : {scalar}", f"param filler : {scalar}", right),
    )
    assert unlocked is not EquivalenceStatus.VERIFIED_EQUIVALENT, (
        f"{claim}: renaming the unused declaration turned {locked} into {unlocked}. "
        f"A false-positive equivalence is the one failure the approval criterion "
        f"forbids outright."
    )


def test_f1_control_the_same_pair_is_refuted_when_vocabularies_coincide():
    """The control half of F-1, asserted as a hard test: with the lock on, it holds.

    This is what makes the xfail above a defect rather than a policy disagreement.
    The engine issues both verdicts for the same mathematical content.
    """
    status = compare(
        _module("param p : Bool", "param q : Bool", "param spare : Bool", "prove p implies q"),
        _module("param p : Bool", "param q : Bool", "param spare : Bool", "prove q implies p"),
    )
    assert status is EquivalenceStatus.VERIFIED_NONEQUIVALENT


# ===========================================================================
# TARGET 2 -- obligation discharge: VERIFIED is reachable and still sound.
# ===========================================================================


@pytest.mark.parametrize(
    ("label", "source", "forbidden"),
    [
        (
            "x/x = 1 over Real is false at zero",
            _module("param x : Real", "prove x / x = 1"),
            GlobalVerdict.VERIFIED,
        ),
        (
            "an undecidable forall is never VERIFIED",
            _module("prove forall x : Real . x * x >= 0"),
            GlobalVerdict.VERIFIED,
        ),
    ],
    ids=["division-at-zero", "unsupported-quantifier"],
)
def test_required_probe_unsound_claims_never_reach_verified(label, source, forbidden):
    outcome = verify_source(source)
    assert outcome.verdict is not forbidden, label
    assert federated(source) != "VERIFIED", label


def test_required_probe_division_is_verified_over_a_positive_domain():
    """``x / x = 1`` is a theorem once the divisor cannot be zero."""
    source = _module("param x : PositiveReal", "prove x / x = 1")
    assert verify_source(source).verdict is GlobalVerdict.VERIFIED
    assert federated(source) == "VERIFIED"


def test_required_probe_false_arithmetic_is_disproved_with_a_witness():
    source = _module("prove 2 + 2 = 5")
    outcome = verify_source(source)
    assert outcome.verdict is GlobalVerdict.DISPROVED
    failure = outcome.first_failure()
    assert failure is not None and failure.witness is not None
    assert federated(source) == "DISPROVED"


def test_verified_requires_a_discharged_obligation_not_merely_no_failure():
    """Condition 4 of the engine's conjunction: no obligation may remain UNSUPPORTED."""
    outcome = verify_source(_module("param x : Real", "prove x / x = 1"))
    assert outcome.verdict is GlobalVerdict.UNSUPPORTED
    assert outcome.discharged_fraction == 0.0


# -- FINDING F-2 ------------------------------------------------------------
#
# ``checkers.partiality_risk`` walks BinOp, Call, UnaryOp, Comparison and LogicalOp.
# It has **no ``Ref`` case**, so it returns ``None`` for a bare name. ``_to_sympy``
# does the opposite: on a ``Ref`` it looks the name up in ``env.definitions`` and
# **inlines the definition body**. The guard therefore inspects a different expression
# from the one the decision procedure decides, and any partial operation moved behind
# a ``def`` becomes invisible to it.

_F2 = (
    "F-2: checkers.partiality_risk has no Ref case while checkers._to_sympy inlines "
    "env.definitions, so a partial operation hidden behind a `def` is invisible to the "
    "totality guard and SymPy's generic cancellation is believed. `prove q = 1` with "
    "`def q := x / x` and `x : Real` reaches VERIFIED, and it is false at zero"
)


@pytest.mark.xfail(reason=_F2, strict=False)
@pytest.mark.parametrize(
    ("label", "definition", "claim"),
    [
        ("division by a possibly-zero name", "def q := x / x", "prove q = 1"),
        ("negative power of a possibly-zero base", "def q := x ^ (-1)", "prove q * x = 1"),
        ("zero power of a possibly-zero base", "def q := x ^ 0", "prove q = 1"),
    ],
    ids=["x-over-x", "x-to-the-minus-one", "x-to-the-zero"],
)
def test_f2_a_partial_operation_behind_a_def_must_not_reach_verified(
    label, definition, claim
):
    source = _module("param x : Real", definition, claim)
    outcome = verify_source(source)
    assert outcome.verdict is not GlobalVerdict.VERIFIED, (
        f"{label}: {definition!r} + {claim!r} over Real reached {outcome.verdict}. "
        f"The claim fails at x = 0."
    )


@pytest.mark.xfail(reason=_F2, strict=False)
def test_f2_the_federation_inherits_the_unsound_verified():
    """The defect is not contained inside the engine; ``classify`` reports it too."""
    source = _module("param x : Real", "def q := x / x", "prove q = 1")
    assert federated(source) != "VERIFIED"


def test_f2_control_the_same_claim_is_unsupported_when_written_inline():
    """Hard test. Written without the ``def``, the identical claim is correctly refused.

    This is what makes F-2 a defect in the guard rather than a decision about ``x/x``:
    the engine gives two different answers to one question depending on whether the
    divisor was named.
    """
    outcome = verify_source(_module("param x : Real", "prove x / x = 1"))
    assert outcome.verdict is GlobalVerdict.UNSUPPORTED
    assert "not provably non-zero" in outcome.records[0].detail


# ===========================================================================
# TARGET 3 -- metric integrity: these must parse and fail later.
# ===========================================================================


@pytest.mark.parametrize(
    ("label", "source", "expected_code"),
    [
        (
            "wrong arity",
            _module("def f(a : Real, b : Real) := a + b", "def g := f(1.0)"),
            "HML-T471",
        ),
        (
            "wrong argument type",
            _module("def f(a : Real) := a + 1.0", "param p : Bool", "def g := f(p)"),
            "HML-T472",
        ),
        (
            "wrong distribution role",
            _module("var X : RandomVariable[Real]", "law X ~ Normal(shape := 0.0, rate := 1.0)"),
            "HML-T416",
        ),
        (
            "declared-type mismatch",
            _module("param p : Probability = 2.0"),
            "HML-T402",
        ),
    ],
    ids=["arity", "argument-type", "distribution-role", "declared-type"],
)
def test_semantic_errors_are_not_parse_errors(label, source, expected_code):
    """A semantic rejection must reach the type checker, never die in the parser.

    Scoring these as parse failures would credit a candidate syntax with a lower parse
    rate for errors that are nothing to do with its grammar.
    """
    result = compile_source(source)
    codes = [d.code for d in result.diagnostics.errors]
    assert not result.ok(), label
    assert expected_code in codes, f"{label}: got {codes}"
    assert not any(c.startswith("HML-P") for c in codes), (
        f"{label}: a semantic error was reported at the parse stage ({codes})"
    )


def test_an_unknown_identifier_fails_resolution_and_not_parsing():
    codes = [d.code for d in compile_source(_module("require nosuchname > 0.0")).diagnostics.errors]
    assert "HML-N301" in codes
    assert not any(c.startswith("HML-P") for c in codes)


def test_a_genuine_syntax_error_still_fails_at_the_parse_stage():
    """The control: the parse stage must remain able to fail, or the check above is vacuous."""
    codes = [d.code for d in compile_source("module M\n\nrequire ((((\n").diagnostics.errors]
    assert any(c.startswith("HML-P") for c in codes), codes


def test_compile_result_ok_is_not_a_parse_verdict():
    """``ok()`` means the whole pipeline accepted the text. It is not "it parsed"."""
    result = compile_source(_module("param p : Probability = 2.0"))
    assert not result.ok()
    assert result.module is not None
    assert result.module.statements, (
        "the text parsed into statements, so any metric reading ok() as a parse "
        "verdict would record a parse failure that did not happen"
    )


# ===========================================================================
# TARGET 4 -- training eligibility: one authority, and quarantine wins.
# ===========================================================================


def _quarantined_facts():
    from hamiltonian_lang.improvement.memory import RoutingFacts

    return RoutingFacts(
        episode_id="E-falsify",
        hypothesis=Hypothesis.EXCLUDED,
        exact_hash="e",
        canonical_hash="c",
    )


def test_route_quarantines_an_excluded_hypothesis_and_refuses_eligibility():
    from hamiltonian_lang.improvement.memory import MemoryStoreKind, route

    decision = route(_quarantined_facts())
    assert decision.store is MemoryStoreKind.QUARANTINE
    assert decision.training_eligible is False


def test_a_caller_supplied_decision_cannot_override_the_router():
    """Route 1: hand ``build_record`` a forged POSITIVE/eligible decision."""
    from hamiltonian_lang.improvement.memory import (
        MemoryStoreKind,
        RoutingDecision,
        RoutingDisagreement,
        build_record,
    )

    with pytest.raises(RoutingDisagreement):
        build_record(
            "R-forged",
            _quarantined_facts(),
            decision=RoutingDecision(
                store=MemoryStoreKind.POSITIVE,
                training_eligible=True,
                reasons=("a caller's second opinion",),
            ),
        )


def test_a_quarantined_record_cannot_be_constructed_eligible():
    """Route 2: skip the router and build the record directly."""
    from hamiltonian_lang.improvement.memory import (
        MemoryRecord,
        MemoryStoreKind,
        RoutingDecision,
    )

    decision = RoutingDecision(
        store=MemoryStoreKind.QUARANTINE, training_eligible=False, reasons=("x",)
    )
    with pytest.raises(Exception) as excinfo:
        MemoryRecord(
            record_id="R-direct",
            episode_id="E-falsify",
            hypothesis=Hypothesis.H1,
            store=MemoryStoreKind.QUARANTINE,
            exact_hash="a",
            canonical_hash="b",
            training_eligible=True,
            decision=decision,
        )
    assert "training-eligible" in str(excinfo.value)


def test_an_excluded_hypothesis_cannot_carry_an_eligible_record():
    """Route 3: launder eligibility through a trainable store on non-evidence."""
    from hamiltonian_lang.improvement.memory import (
        MemoryRecord,
        MemoryStoreKind,
        RoutingDecision,
    )

    decision = RoutingDecision(
        store=MemoryStoreKind.POSITIVE, training_eligible=True, reasons=("x",)
    )
    with pytest.raises(Exception) as excinfo:
        MemoryRecord(
            record_id="R-excluded",
            episode_id="E-falsify",
            hypothesis=Hypothesis.EXCLUDED,
            store=MemoryStoreKind.POSITIVE,
            exact_hash="a",
            canonical_hash="b",
            training_eligible=True,
            decision=decision,
        )
    assert "EXCLUDED" in str(excinfo.value)


def test_a_record_may_not_disagree_with_its_own_routing_decision():
    from hamiltonian_lang.improvement.memory import (
        MemoryRecord,
        MemoryStoreKind,
        RoutingDecision,
    )

    decision = RoutingDecision(
        store=MemoryStoreKind.QUARANTINE, training_eligible=False, reasons=("x",)
    )
    with pytest.raises(ValueError):
        MemoryRecord(
            record_id="R-mismatch",
            episode_id="E-falsify",
            hypothesis=Hypothesis.H1,
            store=MemoryStoreKind.POSITIVE,
            exact_hash="a",
            canonical_hash="b",
            training_eligible=False,
            decision=decision,
        )


# ===========================================================================
# TARGET 5 -- hypothesis isolation: no cross-hypothesis aggregation.
# ===========================================================================


@pytest.mark.parametrize(
    ("label", "items"),
    [
        ("ACQ0 pooled into H3", [Hypothesis.ACQ0, Hypothesis.H3]),
        ("H1 pooled into H2", [Hypothesis.H1, Hypothesis.H2]),
        ("EXCLUDED pooled into H1", [Hypothesis.EXCLUDED, Hypothesis.H1]),
    ],
    ids=["acq0-h3", "h1-h2", "excluded-h1"],
)
def test_cross_hypothesis_aggregation_is_refused(label, items):
    with pytest.raises(HypothesisMixingError):
        require_single_hypothesis(items, context=label)


def test_allow_excluded_does_not_license_mixing():
    """``allow_excluded`` widens which single hypothesis is acceptable, never the count."""
    with pytest.raises(HypothesisMixingError):
        require_single_hypothesis(
            [Hypothesis.EXCLUDED, Hypothesis.H1], context="mix", allow_excluded=True
        )


def test_a_bare_string_is_not_a_hypothesis():
    with pytest.raises(HypothesisMixingError):
        require_single_hypothesis(["H1"], context="untyped")


def test_no_observations_is_not_a_hypothesis():
    with pytest.raises(HypothesisMixingError):
        require_single_hypothesis([], context="empty")


def test_acq0_repair_is_not_h3():
    """``ACQ0_REPAIR`` and ``H3_VERIFIER_GUIDED_REPAIR`` are different mechanisms."""
    from hamiltonian_lang.improvement.state import REPAIR_MECHANISM

    assert REPAIR_MECHANISM[Hypothesis.ACQ0] == "ACQ0_REPAIR"
    assert REPAIR_MECHANISM[Hypothesis.H3] == "H3_VERIFIER_GUIDED_REPAIR"
    assert REPAIR_MECHANISM[Hypothesis.ACQ0] != REPAIR_MECHANISM[Hypothesis.H3]
    assert "H3" not in REPAIR_MECHANISM[Hypothesis.ACQ0]


def test_excluded_is_the_only_non_scientific_member():
    assert not Hypothesis.EXCLUDED.scientific
    for member in (Hypothesis.ACQ0, Hypothesis.H1, Hypothesis.H2, Hypothesis.H3):
        assert member.scientific


# ===========================================================================
# TARGET 6 -- Chain-of-Repair leakage: a plan may not contain the answer.
# ===========================================================================

_LEAK_TARGET = (
    "module M\n"
    "param sigma : PositiveReal\n"
    "var X : RandomVariable[Real]\n"
    "require sigma > 0.0"
)


def _plan(steps):
    from hamiltonian_lang.context_broker import ContextStatus, ErrorClass
    from hamiltonian_lang.improvement.diagnostics import SourceSpan
    from hamiltonian_lang.repair.plan import RepairPlan

    return RepairPlan(
        failing_invariant="a scale parameter must be positive",
        cause="the declaration admits non-positive values",
        source_span=SourceSpan(line=2, col=0),
        expected_semantic_category="a positive real scale parameter",
        repair_steps=tuple(steps),
        preservation_constraints=("do not delete the requirement",),
        error_class=ErrorClass.REFINEMENT,
        context_status=ContextStatus.CONTEXT_FOUND,
        diagnostic_code="HML-T402",
    )


def test_a_plan_carrying_the_corrected_program_verbatim_is_refused():
    from hamiltonian_lang.repair.plan import PlanLeak, assert_plan_non_leaking

    with pytest.raises(PlanLeak):
        assert_plan_non_leaking(
            _plan(_LEAK_TARGET.splitlines()), target_program=_LEAK_TARGET
        )


# -- FINDING F-4 ------------------------------------------------------------
#
# ``plan_leak_reasons`` tests ``normalise(target_program) in normalise(fields)`` --
# a whitespace-normalised exact substring. A module is an unordered collection of
# statements (``matching.py`` says so explicitly, as a Tier-1 assumption), so permuting
# the statements produces the same module and a different string. The plan still hands
# the Learner every statement it needs.

_F4 = (
    "F-4: repair.plan.plan_leak_reasons detects the corrected program by "
    "whitespace-normalised exact substring, so permuting the statements of a module -- "
    "which the project's own Tier-1 assumption says leaves the module unchanged -- "
    "hides a complete, transcribable copy of the answer from the leak check"
)


@pytest.mark.xfail(reason=_F4, strict=False)
def test_f4_a_permuted_corrected_program_is_still_the_answer():
    from hamiltonian_lang.repair.plan import PlanLeak, assert_plan_non_leaking

    lines = _LEAK_TARGET.splitlines()
    permuted = [lines[0], lines[2], lines[1], lines[3]]
    assert sorted(permuted) == sorted(lines)
    with pytest.raises(PlanLeak):
        assert_plan_non_leaking(_plan(permuted), target_program=_LEAK_TARGET)


@pytest.mark.xfail(reason=_F4, strict=False)
def test_f4_a_spelled_out_numeral_evades_the_novel_numeral_check():
    """``forbid_novel_numerals`` scans for digits; an answer in words carries none."""
    from hamiltonian_lang.repair.plan import plan_leak_reasons

    plan = _plan(("the corrected scale is three point one four",))
    reasons = plan_leak_reasons(
        plan, final_answer="3.14", forbid_novel_numerals=True, known_numerals=()
    )
    assert reasons, "a plan stating the answer in words was not flagged"


def test_a_plan_stating_a_category_rather_than_a_value_is_clean():
    """The control: the boundary must still admit a legitimate plan."""
    from hamiltonian_lang.repair.plan import plan_leak_reasons

    plan = _plan(("widen the declared type until it excludes non-positive values",))
    assert plan_leak_reasons(plan, target_program=_LEAK_TARGET) == []


# ===========================================================================
# TARGET 7 -- context-budget arithmetic: zero hidden truncation.
# ===========================================================================

#: ``evaluation/acq0/budget/`` is owned by another agent and landed during this run. The
#: budget tests skip rather than error if it is absent, so this suite never reports a
#: defect in a module that is simply not there yet.
budget_required = pytest.mark.skipif(
    _BUDGET_IMPORT_ERROR is not None,
    reason=f"evaluation.acq0.budget.slots is unavailable ({_BUDGET_IMPORT_ERROR})",
)


def _count(n: int):
    from hamiltonian_lang.improvement.episodes import Measurement

    return Measurement.measured(
        n, instrument="provider_usage", citation="falsification fixture, offline"
    )


@budget_required
def test_the_stated_inequality_holds_at_the_documented_defaults():
    from evaluation.acq0.budget.slots import Fit, eligibility, policy_for_slots

    policy = policy_for_slots(4)
    assert policy.per_slot_context == 8192
    assert eligibility(_count(5888), policy).fit is Fit.FITS
    assert eligibility(_count(5889), policy).fit is Fit.OVERFLOWS


@budget_required
def test_an_unmeasured_prompt_is_undetermined_and_not_a_pass():
    from evaluation.acq0.budget.slots import Fit, eligibility, policy_for_slots

    from hamiltonian_lang.improvement.episodes import Measurement

    result = eligibility(
        Measurement.absent("the run has not happened yet"), policy_for_slots(4)
    )
    assert result.fit is Fit.UNDETERMINED
    assert result.fits is False


@budget_required
def test_the_safety_reserve_floor_is_enforced():
    from evaluation.acq0.budget.slots import InsufficientReserve, eligibility, policy_for_slots

    with pytest.raises(InsufficientReserve):
        eligibility(_count(100), policy_for_slots(4), safety_reserve=255)


# -- FINDING F-3 ------------------------------------------------------------
#
# ``safety_reserve`` is floored at ``MIN_SAFETY_RESERVE``. Its sibling
# ``completion_allowance`` is a keyword argument with no floor and no sign check, so a
# caller can shrink or negate it and obtain ``FITS`` for a prompt that provably cannot
# fit the slot. The rendered ``detail`` then records the false arithmetic verbatim.

_F3 = (
    "F-3: evaluation/acq0/budget/slots.py::eligibility validates safety_reserve against "
    "MIN_SAFETY_RESERVE but leaves completion_allowance unvalidated, so a caller can "
    "pass 0 or a negative value and receive Fit.FITS for a prompt larger than the slot"
)


@budget_required
@pytest.mark.xfail(reason=_F3, strict=False)
@pytest.mark.parametrize(
    ("label", "prompt", "completion_allowance"),
    [
        ("a shrunken allowance leaves no room for the reply", 7900, 0),
        ("a negative allowance is arithmetic nonsense", 9000, -2000),
    ],
    ids=["zero-allowance", "negative-allowance"],
)
def test_f3_no_prompt_may_be_eligible_when_the_real_inequality_fails(
    label, prompt, completion_allowance
):
    from evaluation.acq0.budget.slots import (
        COMPLETION_ALLOWANCE,
        DEFAULT_SAFETY_RESERVE,
        Fit,
        eligibility,
        policy_for_slots,
    )

    policy = policy_for_slots(4)
    result = eligibility(
        _count(prompt), policy, completion_allowance=completion_allowance
    )
    required = prompt + COMPLETION_ALLOWANCE + DEFAULT_SAFETY_RESERVE
    assert required > policy.per_slot_context, "the fixture must actually overflow"
    assert result.fit is not Fit.FITS, (
        f"{label}: {prompt} + {COMPLETION_ALLOWANCE} + {DEFAULT_SAFETY_RESERVE} = "
        f"{required} > {policy.per_slot_context}, yet eligibility reported "
        f"{result.fit} with detail {result.detail!r}"
    )


@budget_required
@pytest.mark.xfail(reason=_F3, strict=False)
def test_f3_the_ceiling_may_never_exceed_the_slot():
    """A ceiling above the slot size describes a server that cannot exist."""
    from evaluation.acq0.budget.slots import eligibility, policy_for_slots

    policy = policy_for_slots(4)
    result = eligibility(_count(1000), policy, completion_allowance=-2000)
    assert result.ceiling <= policy.per_slot_context


# ===========================================================================
# TARGET 8 -- concurrency: hunt the next shared-state hazard after D-024.
# ===========================================================================


def test_d024_holds_under_contention_between_named_and_nameless_serialisation():
    """The regression D-024 fixed: a ``ContextVar``, not a module global.

    ``content_hash`` forces names off while it serialises. Under the old module global a
    concurrent ``canonical_json(..., include_names=True)`` returned the *nameless*
    document with no diagnostic. 600 named forms are produced here while 600 hashings
    contend with them.
    """
    statements = "\n".join(f"param p{i} : Real" for i in range(300))
    result = compile_source(f"module Big\n\n{statements}\n\nrequire p0 > p1\n")
    assert result.ok()
    expected = json.dumps(canonical_json(result.module, include_names=True), sort_keys=True)
    assert expected != json.dumps(
        canonical_json(result.module, include_names=False), sort_keys=True
    )

    def named(_):
        return json.dumps(canonical_json(result.module, include_names=True), sort_keys=True)

    def hashed(_):
        content_hash(result.module)
        return expected

    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        produced = list(
            pool.map(lambda i: named(i) if i % 2 else hashed(i), range(1200))
        )
    assert all(p == expected for p in produced), "a concurrent hashing stripped names"


def test_the_content_hash_is_stable_under_concurrent_hashing():
    result = compile_source(_module("param alpha : Real", "param beta : Real", "require alpha > beta"))
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        hashes = set(pool.map(lambda _: result.hash(), range(400)))
    assert len(hashes) == 1


# -- FINDING F-5 ------------------------------------------------------------
#
# ``equivalence.status.register_certifying_method`` mutates a module-level ``set`` and
# rebinds a module-level ``frozenset``. ``equivalence/__init__.py`` re-exports the
# frozenset by value (``from .status import CERTIFYING_METHODS``), so the rebinding is
# invisible there and the two names disagree from the first registration onward. The set
# names the methods permitted to *certify an equivalence*, so a consumer reading the
# stale name has a different oracle from the one the scorer uses.

_F5 = (
    "F-5: equivalence.status.register_certifying_method rebinds the module-level "
    "CERTIFYING_METHODS, but equivalence/__init__.py re-exported it by value, so the "
    "package-level name (and every `from ... import CERTIFYING_METHODS` binding) is "
    "stale after the first registration -- one authoritative set with two names that "
    "disagree"
)


@pytest.mark.xfail(reason=_F5, strict=False)
def test_f5_the_certifying_method_set_has_one_value_not_two():
    import hamiltonian_lang.equivalence as package
    from hamiltonian_lang.equivalence import status

    method = "tier9.falsification_probe_method"
    try:
        status.register_certifying_method(method)
        assert method in status.CERTIFYING_METHODS
        assert method in package.CERTIFYING_METHODS, (
            "the package-level re-export did not see the registration; a consumer "
            "importing it holds a different certifying oracle from the scorer's"
        )
    finally:
        status._CERTIFYING.discard(method)
        status.CERTIFYING_METHODS = frozenset(status._CERTIFYING)


def test_a_search_method_can_never_be_promoted_to_certifying():
    """The control on F-5's module: the block that matters is executable and holds."""
    from hamiltonian_lang.equivalence import status

    for method in status.SEARCH_ONLY_METHODS:
        with pytest.raises(ValueError):
            status.register_certifying_method(method)
        assert method not in status.CERTIFYING_METHODS
