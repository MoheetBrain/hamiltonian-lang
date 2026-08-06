"""Tests for benchmark corpus governance and the M3-Lite corpus.

The load-bearing tests, and what each of them would catch:

* ``test_compiler_acceptance_is_not_admission`` — an item that compiles cleanly and means
  something else is rejected. If this ever passes trivially, gate 1 has quietly become the
  whole funnel, which is the FormalMATH failure.
* ``test_failing_to_prove_the_negation_yields_no_information`` and its type-level sibling —
  a failed refutation is not evidence. Encoded in the constructor set, not a comment.
* ``test_judge_disagreement_is_never_voted_on`` — three judges, two one way, one the other,
  and the panel returns ``INCONCLUSIVE``. A majority vote would return ``ALIGNED``.
* ``test_m3_lite_is_disjoint_from_every_acq0_split_by_content_hash`` — disjointness on
  content, so an item renamed and reused is still caught.
* ``test_constant_response_baselines_are_below_threshold`` — a corpus whose booleans are
  mostly ``FALSE`` can be beaten to a plausible-looking score by answer bias. This test
  caught exactly that during authoring (``always_FALSE`` = 0.55) and forced a rebalance.
"""

from __future__ import annotations

import ast
import pathlib
from dataclasses import replace

import pytest
from evaluation.corpus.cso import AnswerSpec, SemanticFacts
from evaluation.corpus_governance import CORPUS_GOVERNANCE_VERSION, GATE_ORDER
from evaluation.corpus_governance.back_translation import (
    Alignment,
    JudgeDecision,
    JudgePanel,
    deterministic_overlap,
    panel_from,
    render_controlled_nl,
)
from evaluation.corpus_governance.contamination import (
    ContentFields,
    acq0_splits,
    check_contamination,
    content_digest,
    fingerprint,
    normalised_digest,
    shingle_overlap,
)
from evaluation.corpus_governance.gates import (
    Gate,
    GateOutcome,
    compiler_gate,
    run_funnel,
)
from evaluation.corpus_governance.human_gate import (
    HumanReviewRequired,
    ReviewDecision,
    ReviewQueue,
    ReviewRequest,
    ReviewTrigger,
)
from evaluation.corpus_governance.negation import (
    NegationVerdict,
    NoInformation,
    Refutation,
    attack,
    no_prover_available,
    obligation_disprover,
    sympy_disprover,
)
from evaluation.corpus_governance.semantic_checks import (
    CheckStatus,
    run_semantic_checks,
)
from evaluation.m3.lite import DOMAINS, ERROR_CATEGORIES
from evaluation.m3.lite.calibration import (
    MAX_CONSTANT_RESPONSE_BASELINE,
    MAX_SHALLOW_READER_BASELINE,
    TARGET_BAND,
    BandStatus,
    calibration_report,
    constant_response_baselines,
    difficulty_index,
    estimate_band,
    shallow_reader_baselines,
    uniform_guess_floor,
)
from evaluation.m3.lite.guidance import (
    DEFAULT_SCOUT_GUIDANCE,
    Guidance,
    GuidanceConfig,
    GuidanceViolation,
    assert_scout_guidance,
    render_prompt,
)
from evaluation.m3.lite.items import H3_INELIGIBLE_DOMAINS, LiteItem, build_items
from evaluation.m3.lite.partitions import (
    HELD_OUT,
    PARTITION_ROLES,
    VISIBLE,
    Partition,
    ProvenanceError,
    acq0_demonstration_splits,
    assign_partitions,
    build_manifest,
    held_out_contamination,
    partitioned,
    promotion_critical_ids,
    validate_provenance,
)
from evaluation.m3.lite.roster import (
    DOMAIN_FLOORS,
    ERROR_CATEGORY_FLOOR,
    build_roster,
)

from hamiltonian_lang import compile_source
from hamiltonian_lang.improvement.state import (
    Hypothesis,
    HypothesisMixingError,
    require_single_hypothesis,
)

# ---------------------------------------------------------------------------
# QUARANTINE LIFTED 2026-08-06. Recorded here rather than deleted, because what the
# quarantine was protecting against is the thing a future reader most needs to know.
#
# Quarantined 2026-08-05: the benchmark-governance subagent terminated on a session limit
# while writing this file. Three things were actually wrong, and the third was not in the
# original diagnosis:
#
# 1. `evaluation/corpus_governance/semantic_checks.py::_distractors_distinct` called a
#    `_skip` helper that was never written (`NameError`). It is now `_na`, the helper that
#    already existed for exactly that meaning -- a structurally-absent precondition,
#    neutral, and not counted towards MIN_APPLICABLE_CHECKS. A second name for one status
#    would have been the thing that confuses somebody later.
# 2. `test_compiler_acceptance_is_not_admission` did not compile, and *why* it did not
#    compile inverted the test: the swapped fixture declared `centre : Real`, which made
#    the role swap visible to the type checker, so gate 1 rejected it and gate 2 never ran.
#    Both parameters are now `PositiveReal`, the swap is type-correct, and the test asserts
#    the type-visible variant is caught at gate 1 as a control.
# 3. `test_no_lean_or_stan_path_is_relied_on` flagged the corpus_governance package
#    docstring -- the paragraph explaining why no Lean path can certify anything on this
#    host -- as evidence of a dependency on Lean. Its line-prefix heuristic is replaced by
#    a parse-based scan over identifiers and imports, with negative controls.
#
# The lift condition was not "the tests pass". It was that each property FAILS when
# violated. Mutation controls were run and are recorded in the session report: neutering
# `_roles_match` fails (1); a majority vote in `JudgePanel.verdict`, or merely adding a
# `majority` attribute, fails (3); giving `NoInformation.evidential_weight` a non-zero
# value, adding a `Confirmation` constructor, or returning `Refutation` when the negation
# was not proved, all fail (2); comparing ids instead of content digests fails the
# contamination controls; adding `auto_resolve` to `ReviewQueue` fails.
REPO = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def items() -> list[LiteItem]:
    return build_items()


# ===========================================================================
# 1. Corpus shape: 40 items, seven domains with floors, eight balanced categories
# ===========================================================================


def test_corpus_is_forty_items(items: list[LiteItem]) -> None:
    assert len(items) == 40
    assert len({i.id for i in items}) == 40


def test_every_domain_meets_its_own_floor(items: list[LiteItem]) -> None:
    """Per domain, never as an average.

    FormalMATH found sharp domain bias. An overall 55% is compatible with six domains at
    65% and one at 5%, and those are different corpora with different conclusions.
    """
    counts = {d: sum(1 for i in items if i.domain == d) for d in DOMAINS}
    assert set(counts) == set(DOMAIN_FLOORS)
    below = {d: (n, DOMAIN_FLOORS[d]) for d, n in counts.items() if n < DOMAIN_FLOORS[d]}
    assert not below, f"domains below their floor: {below}"
    assert sum(counts.values()) == 40


def test_structural_error_categories_are_balanced(items: list[LiteItem]) -> None:
    counts = {c: sum(1 for i in items if i.error_category == c) for c in ERROR_CATEGORIES}
    assert set(counts) == set(ERROR_CATEGORIES)
    assert all(n >= ERROR_CATEGORY_FLOOR for n in counts.values()), counts
    # Exactly balanced, so a per-category error rate has the same denominator everywhere.
    assert len(set(counts.values())) == 1, counts


def test_no_item_is_a_single_step(items: list[LiteItem]) -> None:
    """A one-step item is a ceiling item; the constructor refuses one."""
    assert all(i.reasoning_steps >= 2 for i in items)
    with pytest.raises(ValueError, match="ceiling item"):
        LiteItem(
            cso=items[0].cso,
            error_category=items[0].error_category,
            common_error="x",
            negated_claim="x",
            reasoning_steps=1,
            h3_eligible=True,
        )


def test_every_item_records_a_distractor_distinct_from_its_answer(
    items: list[LiteItem],
) -> None:
    for item in items:
        assert item.cso.distractors, item.id
        assert item.common_error.strip(), item.id
        assert str(item.cso.answer.value) not in item.cso.distractors, item.id


# ===========================================================================
# 2. Hypothesis discipline
# ===========================================================================


def test_every_item_carries_exactly_one_hypothesis(items: list[LiteItem]) -> None:
    assert require_single_hypothesis(items, context="M3-Lite default") is Hypothesis.H2


def test_acq0_is_never_a_value_on_a_reasoning_item(items: list[LiteItem]) -> None:
    """ACQ0 is a prerequisite, not evidence for H1/H2/H3. Register rule 1."""
    with pytest.raises(ValueError, match="prerequisite"):
        items[0].for_hypothesis(Hypothesis.ACQ0)
    with pytest.raises(ValueError, match="engineering work"):
        items[0].for_hypothesis(Hypothesis.EXCLUDED)


def test_no_roster_can_be_built_for_acq0_or_excluded() -> None:
    for h in (Hypothesis.ACQ0, Hypothesis.EXCLUDED):
        with pytest.raises(ValueError, match="no .* roster|has no"):
            build_roster(h)


def test_a_roster_cannot_mix_hypotheses(items: list[LiteItem]) -> None:
    mixed = [items[0].for_hypothesis(Hypothesis.H1), items[1].for_hypothesis(Hypothesis.H2)]
    with pytest.raises(HypothesisMixingError):
        require_single_hypothesis(mixed, context="deliberately mixed")


@pytest.mark.parametrize("hypothesis", [Hypothesis.H1, Hypothesis.H2, Hypothesis.H3])
def test_each_roster_is_single_hypothesis_and_meets_its_floors(
    hypothesis: Hypothesis,
) -> None:
    roster = build_roster(hypothesis)
    assert require_single_hypothesis(roster.items, context=str(hypothesis)) is hypothesis
    assert roster.domain_floor_report().met(), roster.domain_floor_report().shortfalls()
    assert roster.category_floor_report().met(), roster.category_floor_report().shortfalls()


def test_h3_roster_drops_the_verifier_ineligible_domains_and_says_so() -> None:
    """The drop is reported, not silent.

    A filter that quietly keeps only the tasks the verifier happens to handle makes H3
    unfalsifiable: whatever the model does, the retained subset is the one where the
    machinery works.
    """
    h3 = build_roster(Hypothesis.H3)
    h2 = build_roster(Hypothesis.H2)
    assert len(h3) < len(h2)
    assert {d for d, _ in h3.excluded_domains} == set(H3_INELIGIBLE_DOMAINS)
    assert all(why.strip() for _, why in h3.excluded_domains)
    assert not {i.domain for i in h3.items} & H3_INELIGIBLE_DOMAINS
    payload = h3.to_dict()
    assert payload["excluded_domains"], "an H3 roster must publish what it dropped"


# ===========================================================================
# 3. Gate 1: every reference encoding compiles -- and that is not enough
# ===========================================================================


def test_every_reference_encoding_passes_the_compiler_gate(items: list[LiteItem]) -> None:
    for item in items:
        record, module = compiler_gate(item.id, item.cso.reference_hml)
        assert record.outcome is GateOutcome.PASSED, f"{item.id}: {record.detail}"
        assert module is not None


def test_gate_order_is_the_declared_order() -> None:
    assert tuple(g.value for g in Gate) == GATE_ORDER
    assert GATE_ORDER[0] == "compiler"
    assert GATE_ORDER[-1] == "human_review"


def test_compiler_acceptance_is_not_admission() -> None:
    """The FormalMATH finding, as an executable test.

    Both parameters are ``PositiveReal``, so the role swap is *type-correct* and the
    compiler has no way to see it: gate 1 passes on an encoding that means something else.
    The ground truth says ``location`` is filled by ``centre``; the encoding fills it with
    ``spread``. Only gate 2, comparing against the recorded ground truth, rejects it — and
    it rejects it on ``roles_match`` and nothing else, so the rejection is for the reason
    claimed rather than an incidental one.

    The type symmetry is load-bearing, and the second half of this test says why. An
    earlier draft of the fixture declared ``centre : Real``; that made the swap visible to
    the type checker, gate 1 rejected it, and gate 2 never ran — so the test asserted the
    opposite of its own thesis.
    """
    source = """module SwappedRoles
param centre : PositiveReal
param spread : PositiveReal
obs y : Real
law y | centre spread ~ Normal(location := spread, scale := centre)
"""
    result = compile_source(source, file="swapped")
    assert result.ok(), "the fixture must compile, or it tests nothing"

    truth = SemanticFacts(
        entities={"centre": "PositiveReal", "spread": "PositiveReal", "y": "Real"},
        declaration_kinds={"centre": "param", "spread": "param", "y": "obs"},
        law_families={"y": "Normal"},
        laws={"y": {"location": "centre", "scale": "spread"}},
    )
    report = run_semantic_checks(
        "swapped",
        result.module,
        truth,
        prose="a normal law centred at centre with spread spread",
        question="which symbol fills which role?",
        answer=AnswerSpec(
            kind="role_map",
            value={"location": "centre", "scale": "spread"},
            justification="stated in the specification",
        ),
        distractors=['{"location": "spread", "scale": "centre"}'],
    )
    assert not report.admitted()
    assert {r.name for r in report.failures} == {"roles_match"}

    # The same swap, made type-visible, is caught at gate 1 instead — HML-T413, because
    # ``scale`` requires PositiveReal. Compiler acceptance is a real filter; it is just not
    # the whole one, and this line is what keeps the fixture above honest about which gate
    # is doing the work.
    type_visible = source.replace("param centre : PositiveReal", "param centre : Real")
    visible = compile_source(type_visible, file="swapped-visible")
    assert not visible.ok()
    assert any(d.code == "HML-T413" for d in visible.diagnostics.errors)

    # And the corrected encoding — same source shape, roles the right way round — is
    # admitted. Without this the test would be satisfied by a gate 2 that rejects
    # everything.
    fixed = source.replace(
        "Normal(location := spread, scale := centre)",
        "Normal(location := centre, scale := spread)",
    )
    fixed_result = compile_source(fixed, file="fixed")
    assert fixed_result.ok()
    fixed_report = run_semantic_checks(
        "fixed",
        fixed_result.module,
        truth,
        prose="a normal law centred at centre with spread spread",
        question="which symbol fills which role?",
        answer=AnswerSpec(
            kind="role_map",
            value={"location": "centre", "scale": "spread"},
            justification="stated in the specification",
        ),
        distractors=['{"location": "spread", "scale": "centre"}'],
    )
    assert fixed_report.admitted(), [r.to_dict() for r in fixed_report.failures]


def test_deterministic_semantics_rejects_a_reversed_quantifier_prefix() -> None:
    source = """module Reversed
require exists w : Real . forall u : Real . w > u
"""
    result = compile_source(source, file="reversed")
    assert result.ok()
    truth = SemanticFacts(quantifier_order=["forall u", "exists w"])
    report = run_semantic_checks("reversed", result.module, truth)
    failures = {r.name: r.detail for r in report.failures}
    assert "quantifier_order" in failures
    assert "different nesting" in failures["quantifier_order"]


def test_an_encoding_with_extra_structure_is_rejected() -> None:
    """Faithful is both directions: no omissions and no padding."""
    source = """module Padded
var x : Real
var y : Real
require x > 0.0
"""
    result = compile_source(source, file="padded")
    assert result.ok()
    truth = SemanticFacts(entities={"x": "Real"}, declaration_kinds={"x": "var"})
    report = run_semantic_checks("padded", result.module, truth)
    assert "no_undeclared_entities" in {r.name for r in report.failures}


def test_every_item_passes_every_deterministic_semantic_check(
    items: list[LiteItem],
) -> None:
    for item in items:
        result = compile_source(item.cso.reference_hml, file=item.id)
        assert result.ok(), item.id
        report = run_semantic_checks(
            item.id,
            result.module,
            item.cso.semantics,
            prose=item.cso.prose,
            question=item.cso.question,
            answer=item.cso.answer,
            distractors=item.cso.distractors,
        )
        assert not report.failures, (item.id, [r.to_dict() for r in report.failures])
        assert not report.inconclusive, (item.id, [r.to_dict() for r in report.inconclusive])
        assert report.admitted(), (item.id, report.applicable)


def test_not_applicable_is_not_a_pass_and_does_not_carry_admission() -> None:
    """An item on which almost nothing is checkable is not thereby verified."""
    source = "module Bare\nvar x : Real\nrequire x > 0.0\n"
    result = compile_source(source, file="bare")
    report = run_semantic_checks("bare", result.module, SemanticFacts())
    assert report.not_applicable
    assert not any(r.status is CheckStatus.PASS for r in report.not_applicable)


# ===========================================================================
# 4. Gate 3: back-translation, and the refusal to vote
# ===========================================================================


def test_controlled_rendering_preserves_quantifier_order() -> None:
    forward = compile_source(
        "module A\nrequire forall u : Real . exists w : Real . w > u\n"
    )
    backward = compile_source(
        "module A\nrequire exists w : Real . forall u : Real . w > u\n"
    )
    assert forward.ok() and backward.ok()
    a = render_controlled_nl(forward.module)
    b = render_controlled_nl(backward.module)
    assert a != b, "a renderer that normalises quantifier order reports two propositions as one"


def test_judge_disagreement_is_never_voted_on() -> None:
    panel = JudgePanel(
        item_id="disputed",
        specification="spec",
        rendering="rendering",
        decisions=(
            JudgeDecision("j1", Alignment.ALIGNED, "reads the same to me"),
            JudgeDecision("j2", Alignment.ALIGNED, "same"),
            JudgeDecision("j3", Alignment.MISALIGNED, "the conditioning set differs"),
        ),
    )
    assert panel.is_disputed()
    assert panel.verdict() is Alignment.INCONCLUSIVE, "2-1 is not 'aligned'"
    # Every individual decision survives.
    assert len(panel.decisions) == 3
    assert [d.alignment for d in panel.decisions].count(Alignment.MISALIGNED) == 1
    assert not hasattr(panel, "majority")
    assert not hasattr(panel, "modal_alignment")


def test_a_disputed_panel_raises_a_human_review_request_carrying_all_decisions() -> None:
    panel = panel_from(
        "disputed",
        "the specification",
        "the rendering",
        [
            JudgeDecision("j1", Alignment.ALIGNED, "ok"),
            JudgeDecision("j2", Alignment.INCONCLUSIVE, "cannot tell"),
        ],
    )
    request = panel.review_request()
    assert request is not None
    assert request.trigger is ReviewTrigger.INCONCLUSIVE_SEMANTIC_PAIR
    assert len(request.evidence["decisions"]) == 2


def test_a_unanimous_panel_raises_nothing() -> None:
    panel = panel_from(
        "clean",
        "spec",
        "spec",
        [JudgeDecision("j1", Alignment.ALIGNED, "ok"), JudgeDecision("j2", Alignment.ALIGNED, "ok")],
    )
    assert panel.verdict() is Alignment.ALIGNED
    assert panel.review_request() is None


def test_a_panel_with_no_decisions_is_an_unrun_gate_not_an_inconclusive_one() -> None:
    with pytest.raises(ValueError, match="unrun gate"):
        JudgePanel(item_id="x", specification="s", rendering="r", decisions=())


def test_lexical_overlap_is_a_screen_not_a_verdict() -> None:
    """A reversed quantifier prefix reuses every word, so overlap cannot detect it."""
    a = "for every u there exists a w with w greater than u"
    b = "there exists a w such that for every u, w is greater than u"
    assert deterministic_overlap(a, b) > 0.9


# ===========================================================================
# 5. Gate 4: the asymmetry, encoded in the types
# ===========================================================================


def test_proving_the_negation_refutes_the_candidate() -> None:
    outcome = attack("bad_key", "Ne(2*7, 15)", disprove=sympy_disprover)
    assert isinstance(outcome, Refutation)
    assert outcome.candidate_rejected is True
    assert outcome.attempt.verdict is NegationVerdict.NEGATION_PROVED


def test_failing_to_prove_the_negation_yields_no_information() -> None:
    outcome = attack("good_key", "Ne(2*7, 14)", disprove=sympy_disprover)
    assert isinstance(outcome, NoInformation)
    assert outcome.candidate_rejected is False
    assert outcome.evidential_weight == 0
    assert outcome.attempt.verdict is NegationVerdict.NEGATION_NOT_PROVED


def test_an_unattempted_negation_is_the_same_amount_of_evidence_as_a_failed_one() -> None:
    a = attack("x", "anything at all", disprove=no_prover_available)
    b = attack("x", "Ne(1, 1)", disprove=sympy_disprover)
    assert type(a) is type(b) is NoInformation
    assert a.evidential_weight == b.evidential_weight == 0


def test_the_negation_module_has_no_constructor_that_supports_a_candidate() -> None:
    """The asymmetry is structural, not documentary.

    A comment saying "note: failing to refute proves nothing" is deleted by the first
    person in a hurry. A missing constructor is not. This test reads the module's own
    source and asserts that the only outcome types are the two.
    """
    import evaluation.corpus_governance.negation as negation

    source = pathlib.Path(negation.__file__).read_text()
    tree = ast.parse(source)
    classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    outcome_types = classes - {"NegationVerdict", "NegationAttempt"}
    assert outcome_types == {"Refutation", "NoInformation"}, outcome_types
    for banned in ("Confirmation", "Validated", "Supported", "Survived"):
        assert banned not in classes


def test_no_information_cannot_be_given_a_non_zero_weight() -> None:
    outcome = attack("x", "not a relation", disprove=no_prover_available)
    assert isinstance(outcome, NoInformation)
    with pytest.raises(AttributeError):
        outcome.evidential_weight = 1  # type: ignore[misc]


def test_sympy_declines_rather_than_guessing_on_open_terms() -> None:
    outcome = attack("open", "Ne(x, 1)", disprove=sympy_disprover)
    assert isinstance(outcome, NoInformation)
    assert "free symbols" in outcome.attempt.detail


def test_the_obligation_engine_can_refute_an_hml_stated_negation() -> None:
    """Gate 4 reuses the project's obligation engine rather than a second set of checks."""
    outcome = attack(
        "arith", "module N\nrequire 2.0 * 7.0 != 15.0\n", disprove=obligation_disprover
    )
    assert isinstance(outcome, Refutation)
    assert outcome.attempt.verdict is NegationVerdict.NEGATION_PROVED
    assert outcome.attempt.procedure == "obligations"
    assert "closed_arithmetic_equality" in outcome.attempt.detail


def test_a_vacuously_verified_module_is_not_a_refutation() -> None:
    """The trap that makes the ``substantive`` conjunct load-bearing.

    ``verify_source`` returns ``VERIFIED`` on a module carrying no obligations at all —
    correctly, since there was nothing to fail. Read on the verdict alone, gate 4 would
    refute every candidate whose negation is not statable in the supported subset, which
    deletes items rather than admitting them.
    """
    from hamiltonian_lang.verification.obligations import GlobalVerdict, verify_source

    empty = verify_source("module N\nvar x : Real\n")
    assert empty.verdict is GlobalVerdict.VERIFIED, "the fixture must verify, or it is moot"
    assert not empty.substantive

    outcome = attack("empty", "module N\nvar x : Real\n", disprove=obligation_disprover)
    assert isinstance(outcome, NoInformation)
    assert outcome.evidential_weight == 0
    assert "vacuous" in outcome.attempt.detail


@pytest.mark.parametrize(
    ("label", "source"),
    [
        ("disproved", "module N\nrequire 2.0 * 7.0 != 14.0\n"),
        ("unsupported", "module N\nvar x : Real\nrequire forall y : Real . y > x\n"),
        ("invalid", "Ne(2*7, 15)"),
    ],
)
def test_every_other_engine_verdict_is_no_information(label: str, source: str) -> None:
    """``DISPROVED`` says the negation is false. It does not say the candidate is true."""
    outcome = attack(label, source, disprove=obligation_disprover)
    assert isinstance(outcome, NoInformation), label
    assert outcome.evidential_weight == 0
    assert outcome.attempt.verdict is NegationVerdict.NEGATION_NOT_PROVED


def test_the_arithmetic_negated_claims_audit_the_answer_keys(
    items: list[LiteItem],
) -> None:
    """Where the answer is recomputable, gate 4 checks the recorded key against a recomputation.

    A mistyped key is *proved wrong* by this pass, which is the one direction the negation
    attack can legitimately decide.
    """
    decided = 0
    for item in items:
        outcome = attack(item.id, item.negated_claim, disprove=sympy_disprover)
        assert isinstance(outcome, NoInformation), (
            f"{item.id}: the negation of the recorded ground truth was PROVED, so the "
            f"answer key is wrong: {outcome.reason if isinstance(outcome, Refutation) else ''}"
        )
        if outcome.attempt.detail.startswith("SymPy evaluates"):
            decided += 1
    # Enough items carry a genuinely checkable claim that gate 4 is doing real work rather
    # than declining forty times.
    assert decided >= 8, f"only {decided} of {len(items)} negated claims were decidable"


# ===========================================================================
# 6. Gate 5: the pipeline stops rather than resolving
# ===========================================================================


def test_an_open_request_blocks_promotion() -> None:
    queue = ReviewQueue()
    queue.raise_request(
        ReviewRequest(
            request_id="r1",
            trigger=ReviewTrigger.PROMOTION_SET_AMBIGUITY,
            item_id="item",
            question="admit?",
        )
    )
    with pytest.raises(HumanReviewRequired):
        queue.assert_clear(context="promotion")


def test_there_is_no_automatic_resolution_path() -> None:
    queue = ReviewQueue()
    for banned in ("auto_resolve", "resolve_by_majority", "resolve_all", "expire"):
        assert not hasattr(queue, banned), banned


def test_a_decision_requires_a_named_reviewer_and_a_written_rationale() -> None:
    with pytest.raises(ValueError, match="named reviewer"):
        ReviewDecision(request_id="r1", reviewer="  ", admit=True, rationale="fine")
    with pytest.raises(ValueError, match="written rationale"):
        ReviewDecision(request_id="r1", reviewer="lead", admit=True, rationale="")


def test_resolving_clears_the_block_and_keeps_the_audit_trail() -> None:
    queue = ReviewQueue()
    queue.raise_request(
        ReviewRequest(
            request_id="r1",
            trigger=ReviewTrigger.BENCHMARK_CORRECTION,
            item_id="item",
            question="is the key wrong?",
        )
    )
    queue.resolve(
        ReviewDecision(request_id="r1", reviewer="lead", admit=False, rationale="key is wrong")
    )
    queue.assert_clear(context="promotion")
    assert queue.rejected_items() == frozenset({"item"})
    assert len(queue.resolved) == 1


def test_all_five_triggers_are_representable() -> None:
    assert {t.value for t in ReviewTrigger} == {
        "promotion_set_ambiguity",
        "new_equivalence_transformation",
        "new_verifier_class",
        "inconclusive_semantic_pair",
        "benchmark_correction",
    }


# ===========================================================================
# 7. The funnel as a whole
# ===========================================================================


def _clean_inputs(item: LiteItem):
    result = compile_source(item.cso.reference_hml, file=item.id)
    report = run_semantic_checks(
        item.id,
        result.module,
        item.cso.semantics,
        prose=item.cso.prose,
        question=item.cso.question,
        answer=item.cso.answer,
        distractors=item.cso.distractors,
    )
    panel = panel_from(
        item.id,
        item.cso.prose,
        render_controlled_nl(result.module),
        [
            JudgeDecision("j1", Alignment.ALIGNED, "checked by hand"),
            JudgeDecision("j2", Alignment.ALIGNED, "checked by hand"),
        ],
    )
    negation = attack(item.id, item.negated_claim, disprove=sympy_disprover)
    return report, panel, negation


def test_the_funnel_admits_a_clean_item_and_records_all_five_gates(
    items: list[LiteItem],
) -> None:
    item = items[0]
    report, panel, negation = _clean_inputs(item)
    queue = ReviewQueue()
    funnel = run_funnel(
        [(item.id, item.cso.reference_hml)],
        semantic={item.id: report},
        panels={item.id: panel},
        negations={item.id: negation},
        queue=queue,
    )
    decision = funnel.decisions[0]
    assert decision.admitted()
    assert [r.gate for r in decision.records] == list(Gate)


def test_a_missing_gate_result_escalates_rather_than_passing(
    items: list[LiteItem],
) -> None:
    """An unrun gate is not a passed gate."""
    item = items[0]
    queue = ReviewQueue()
    funnel = run_funnel(
        [(item.id, item.cso.reference_hml)],
        semantic={},
        panels={},
        negations={},
        queue=queue,
    )
    decision = funnel.decisions[0]
    assert not decision.admitted()
    assert decision.records[1].outcome is GateOutcome.ESCALATED
    assert "unrun gate is not a passed gate" in decision.records[1].detail
    assert len(queue) == 1


def test_the_funnel_reports_the_gap_between_compiler_only_and_true_retention(
    items: list[LiteItem],
) -> None:
    """FormalMATH's ~92% vs ~32%. The gap must be a number in the report, not a paragraph."""
    good, bad = items[0], items[1]
    good_report, good_panel, good_neg = _clean_inputs(good)
    bad_report, bad_panel, bad_neg = _clean_inputs(bad)
    # Corrupt the second item's ground truth so gate 2 rejects it while gate 1 still passes.
    corrupted = run_semantic_checks(
        bad.id,
        compile_source(bad.cso.reference_hml, file=bad.id).module,
        SemanticFacts(entities={"nonexistent": "Real"}, declaration_kinds={"nonexistent": "var"}),
        prose=bad.cso.prose,
        question=bad.cso.question,
        answer=bad.cso.answer,
        distractors=bad.cso.distractors,
    )
    del bad_report
    funnel = run_funnel(
        [(good.id, good.cso.reference_hml), (bad.id, bad.cso.reference_hml)],
        semantic={good.id: good_report, bad.id: corrupted},
        panels={good.id: good_panel, bad.id: bad_panel},
        negations={good.id: good_neg, bad.id: bad_neg},
        queue=ReviewQueue(),
    )
    assert funnel.compiler_only_illusion() == 1.0
    assert len(funnel.admitted) == 1
    curve = funnel.survival_curve()
    assert curve["compiler"]["survived"] == 2
    assert curve["deterministic_semantics"]["survived"] == 1
    payload = funnel.to_dict()
    assert payload["governance_version"] == CORPUS_GOVERNANCE_VERSION
    assert payload["compiler_only_illusion"] > payload["retention"]


def test_a_promotion_critical_item_is_stopped_even_when_every_gate_passed(
    items: list[LiteItem],
) -> None:
    item = items[0]
    report, panel, negation = _clean_inputs(item)
    queue = ReviewQueue()
    funnel = run_funnel(
        [(item.id, item.cso.reference_hml)],
        semantic={item.id: report},
        panels={item.id: panel},
        negations={item.id: negation},
        queue=queue,
        promotion_critical=frozenset({item.id}),
    )
    decision = funnel.decisions[0]
    assert not decision.admitted()
    assert decision.records[-1].outcome is GateOutcome.ESCALATED
    with pytest.raises(HumanReviewRequired):
        queue.assert_clear(context="promotion")


def test_rejected_candidates_are_recorded_never_discarded(items: list[LiteItem]) -> None:
    bad_source = "module Broken\nvar x : Nonexistent\n"
    funnel = run_funnel(
        [("broken", bad_source)],
        semantic={},
        panels={},
        negations={},
        queue=ReviewQueue(),
    )
    assert funnel.total == 1
    assert funnel.decisions[0].outcome is GateOutcome.REJECTED
    assert funnel.decisions[0].final_gate is Gate.COMPILER


# ===========================================================================
# 8. Contamination: by content hash, not by name
# ===========================================================================


def _extract(item: LiteItem) -> tuple[str, ContentFields]:
    cso = item.cso
    return cso.id, ContentFields(
        specification=cso.prose,
        question=cso.question,
        answer=str(cso.answer.value),
        reference=cso.reference_hml,
    )


def test_content_digest_ignores_the_identifier() -> None:
    a = ContentFields("same prose", "same question", "7", "module M\n")
    b = ContentFields("same prose", "same question", "7", "module M\n")
    assert content_digest(a) == content_digest(b)


def test_normalised_digest_catches_a_cosmetic_edit() -> None:
    a = ContentFields("The value of X is seven.", "What is X?", "7", "module M\n")
    b = ContentFields("the value of x is seven", "what is x", "7", "module M\n")
    assert content_digest(a) != content_digest(b)
    assert normalised_digest(a) == normalised_digest(b)


def test_shingle_overlap_catches_a_paraphrase_that_both_hashes_miss() -> None:
    a = "a real quantity x satisfies x squared equals nine and the sign of x is not stated"
    b = "a real quantity x satisfies x squared equals nine and the sign of x is unstated"
    assert shingle_overlap(a, b) > 0.5


@pytest.mark.slow
def test_m3_lite_is_disjoint_from_every_acq0_split_by_content_hash(
    items: list[LiteItem],
) -> None:
    """The requirement, stated exactly: empty intersection with **every** ACQ0 split.

    Checked on content, never on id: two items differing only in their id would pass an id
    check and still be the same item.
    """
    candidate = fingerprint("m3_lite", items, _extract)
    splits = acq0_splits()
    assert len(splits) >= 8, "the split registry has stopped discovering the stage pools"
    assert sum(len(s) for s in splits) > 300, "the foreign corpora look truncated"
    assert {"acq0::demonstration", "acq0::G4_confirmatory", "hml_eval_001::corpus"} <= {
        s.name for s in splits
    }

    report = check_contamination(candidate, splits)
    assert report.clean(), [c.to_dict() for c in report.hard_collisions]
    assert not report.flagged, [c.to_dict() for c in report.flagged]

    # And explicitly as a set intersection of digests, per split.
    for split in splits:
        overlap = set(candidate.exact.values()) & set(split.exact.values())
        assert not overlap, f"{split.name} shares content with M3-Lite"
        overlap_n = set(candidate.normalised.values()) & set(split.normalised.values())
        assert not overlap_n, f"{split.name} shares normalised content with M3-Lite"


def test_the_contamination_check_actually_fires_when_an_item_is_reused(
    items: list[LiteItem],
) -> None:
    """A check that has never been observed failing is not known to work."""
    candidate = fingerprint("m3_lite", items[:3], _extract)
    # Same content, different ids -- the exact leak an id check would miss.
    renamed = [
        (f"renamed_{i}", ContentFields(it.cso.prose, it.cso.question,
                                       str(it.cso.answer.value), it.cso.reference_hml))
        for i, it in enumerate(items[:3])
    ]
    foreign = fingerprint("foreign", renamed, lambda pair: pair)
    report = check_contamination(candidate, [foreign])
    assert not report.clean()
    assert len(report.hard_collisions) == 3
    assert all(c.kind == "exact" for c in report.hard_collisions)


def test_m3_lite_uses_a_seed_namespace_no_earlier_study_used(
    items: list[LiteItem],
) -> None:
    assert all(i.cso.generator.startswith("hml-m3-lite-001::") for i in items)
    assert all(i.cso.corpus_version == "hml-m3-lite-001-0.1.0" for i in items)


# ===========================================================================
# 9. Calibration: what is measured, and what is only predicted
# ===========================================================================


def test_take_distractor_baseline_scores_exactly_zero(items: list[LiteItem]) -> None:
    """The corpus's own statement of the careless reading must never be the answer."""
    assert shallow_reader_baselines(items)["take_distractor"] == 0.0


def test_shallow_reader_baselines_are_below_threshold(items: list[LiteItem]) -> None:
    baselines = shallow_reader_baselines(items)
    high = {k: v for k, v in baselines.items() if v > MAX_SHALLOW_READER_BASELINE}
    assert not high, f"solvable by surface heuristics: {high}"


def test_constant_response_baselines_are_below_threshold(items: list[LiteItem]) -> None:
    """Response bias would be indistinguishable from reasoning in the results table.

    This test caught ``always_FALSE`` = 0.55 during authoring and forced the boolean
    polarity to be rebalanced.
    """
    baselines = constant_response_baselines(items)
    high = {k: v for k, v in baselines.items() if v > MAX_CONSTANT_RESPONSE_BASELINE}
    assert not high, f"beatable by a constant response: {high}"
    assert baselines["always_TRUE"] > 0.15, "the booleans have swung the other way"
    assert baselines["always_FALSE"] > 0.15, baselines


def test_the_uniform_guess_floor_is_computed_not_asserted(items: list[LiteItem]) -> None:
    floor = uniform_guess_floor(items)
    assert 0.0 < floor < TARGET_BAND[0]


def test_the_band_is_predicted_and_says_so() -> None:
    band = estimate_band()
    assert band.status is BandStatus.PREDICTED_NOT_MEASURED
    assert band.measured_band is None
    assert not band.is_measured()
    assert band.within_target()
    assert TARGET_BAND == (0.40, 0.70)
    # The ceiling anchor is named and explicitly not used.
    assert any("NOT used" in a for a in band.anchors)
    assert band.caveats


def test_the_band_cannot_be_marked_measured_without_a_measurement() -> None:
    band = estimate_band()
    assert not hasattr(band, "mark_measured")
    with pytest.raises(AttributeError):
        band.measured_band = (0.5, 0.6)  # type: ignore[misc]


def test_difficulty_is_not_concentrated_at_the_easy_end(items: list[LiteItem]) -> None:
    indices = [difficulty_index(i) for i in items]
    assert min(indices) >= 4
    assert len(set(indices)) >= 3, "a single difficulty value is not a stratified corpus"


def test_calibration_report_keeps_measured_and_predicted_apart() -> None:
    report = calibration_report()
    assert set(report) == {"measured", "predicted"}
    assert report["predicted"]["status"] == "predicted_not_measured"
    assert report["predicted"]["measured_band"] is None
    assert report["measured"]["n_items"] == 40


# ===========================================================================
# 10. Guidance variants: prepared, not run
# ===========================================================================


def test_the_three_variants_exist_and_the_default_is_no_supplied_solution() -> None:
    assert {g.value for g in Guidance} == {
        "no_supplied_solution",
        "model_generated_local_plan",
        "human_written_complete_solution",
    }
    assert DEFAULT_SCOUT_GUIDANCE is Guidance.NO_SUPPLIED_SOLUTION


@pytest.mark.parametrize("hypothesis", [Hypothesis.H2, Hypothesis.H3])
def test_the_default_scout_refuses_a_human_written_complete_solution(
    hypothesis: Hypothesis,
) -> None:
    """FormalMATH: a supplied full solution sometimes *reduced* success."""
    config = GuidanceConfig(
        guidance=Guidance.HUMAN_WRITTEN_COMPLETE_SOLUTION,
        justification="explicitly requested as an extra arm",
    )
    with pytest.raises(GuidanceViolation, match="must not supply"):
        assert_scout_guidance(hypothesis, config)


def test_the_default_scout_accepts_the_other_two_variants() -> None:
    for guidance in (Guidance.NO_SUPPLIED_SOLUTION, Guidance.MODEL_GENERATED_LOCAL_PLAN):
        assert_scout_guidance(Hypothesis.H2, GuidanceConfig(guidance=guidance))


def test_the_human_written_variant_requires_a_written_justification() -> None:
    with pytest.raises(GuidanceViolation, match="requires a written justification"):
        GuidanceConfig(guidance=Guidance.HUMAN_WRITTEN_COMPLETE_SOLUTION)


def test_render_prompt_produces_text_and_never_sends_it(items: list[LiteItem]) -> None:
    prompt = render_prompt(items[0])
    assert isinstance(prompt, str)
    assert items[0].cso.prose in prompt
    assert items[0].cso.question in prompt
    assert "<ANSWER>" in prompt
    plan = render_prompt(items[0], GuidanceConfig(Guidance.MODEL_GENERATED_LOCAL_PLAN))
    assert "plan of at most three lines" in plan


def test_the_human_written_variant_will_not_silently_render_as_the_no_solution_arm(
    items: list[LiteItem],
) -> None:
    config = GuidanceConfig(
        guidance=Guidance.HUMAN_WRITTEN_COMPLETE_SOLUTION, justification="extra arm"
    )
    with pytest.raises(GuidanceViolation, match="no solution text"):
        render_prompt(items[0], config)


# ===========================================================================
# 11. Partitions: development / adversarial / promotion / transfer
# ===========================================================================


def test_the_deal_is_total_disjoint_and_level(items: list[LiteItem]) -> None:
    manifest = build_manifest(items)
    assert set(manifest.members) == set(Partition)
    assert manifest.sizes() == {str(p): 10 for p in Partition}

    seen: list[str] = [i for ids in manifest.members.values() for i in ids]
    assert sorted(seen) == sorted(i.id for i in items), "the deal is not total"
    assert len(set(seen)) == len(seen), "an item is in two partitions at once"
    assert manifest.held_out_ids() | manifest.visible_ids() == set(seen)
    assert not (manifest.held_out_ids() & manifest.visible_ids())


def test_only_development_is_visible() -> None:
    assert VISIBLE == frozenset({Partition.DEVELOPMENT})
    assert HELD_OUT == {Partition.ADVERSARIAL, Partition.PROMOTION, Partition.TRANSFER}
    assert not VISIBLE & HELD_OUT
    assert set(PARTITION_ROLES) == set(Partition), "every partition states its own cost"
    assert all(why.strip() for why in PARTITION_ROLES.values())


def test_every_domain_is_present_in_every_partition(items: list[LiteItem]) -> None:
    manifest = build_manifest(items)
    assert not manifest.shortfalls(), manifest.shortfalls()
    for partition in Partition:
        assert set(manifest.domain_counts[partition]) == set(DOMAINS), partition


def test_the_deal_is_reproducible_and_not_hand_picked(items: list[LiteItem]) -> None:
    """A partition somebody chose by hand is a partition somebody chose by difficulty."""
    first = assign_partitions(items)
    second = assign_partitions(list(reversed(items)))
    assert first == second, "the deal depends on input order, so it is not reproducible"


def test_the_manifest_records_content_digests_not_only_ids(items: list[LiteItem]) -> None:
    """Ids are re-usable; digests are not. This is the whole basis of the check below."""
    manifest = build_manifest(items)
    assert set(manifest.digests) == {i.id for i in items}
    assert len(set(manifest.digests.values())) == len(items), "two items share content"

    # A renamed item keeps its digest. That is the property every id-based check lacks.
    original = items[0]
    renamed = replace(original, cso=replace(original.cso, id="totally_different_id"))
    assert renamed.id != original.id
    assert content_digest(_extract(renamed)[1]) == manifest.digests[original.id]


def test_no_acq0_demonstration_comes_from_a_held_out_partition(
    items: list[LiteItem],
) -> None:
    """The requirement, on content rather than on names.

    An item shown to a model as a worked example and later scored is measuring recall. The
    comparison is over ``(specification, question, answer, reference)`` digests, so an item
    reused under a new id is still caught — which is the case a name-based check passes.
    """
    splits = acq0_demonstration_splits()
    assert {s.name for s in splits} >= {"acq0::demonstration"}
    assert sum(len(s) for s in splits) >= 50, "the demonstration pools look truncated"

    reports = held_out_contamination(items, splits)
    assert set(reports) == HELD_OUT, "a held-out partition went unchecked"
    for partition, report in reports.items():
        assert report.clean(), (partition, [c.to_dict() for c in report.hard_collisions])
        assert not report.flagged, (partition, [c.to_dict() for c in report.flagged])
        assert report.checked_against, partition

    # Explicitly as a set intersection of digests, per held-out partition per split.
    pools = partitioned(items)
    for partition in sorted(HELD_OUT):
        mine = {content_digest(_extract(i)[1]) for i in pools[partition]}
        for split in splits:
            assert not mine & set(split.exact.values()), (partition, split.name)


def test_the_held_out_check_fires_on_an_item_reused_under_a_new_name(
    items: list[LiteItem],
) -> None:
    """The negative control for the test above.

    A demonstration pool is synthesised containing one *renamed* copy of a promotion item.
    Nothing about its id matches; every content field does. The check must fire, and it
    must fire as a hard collision rather than a near-duplicate flag.
    """
    pools = partitioned(items)
    reused = pools[Partition.PROMOTION][0]
    disguised = replace(reused, cso=replace(reused.cso, id="demo_task_00"))
    assert disguised.id != reused.id

    planted = fingerprint("acq0::demonstration", [disguised], _extract)
    reports = held_out_contamination(items, [planted])

    promotion = reports[Partition.PROMOTION]
    assert not promotion.clean()
    assert [c.kind for c in promotion.hard_collisions] == ["exact"]
    collision = promotion.hard_collisions[0]
    assert collision.candidate_id == reused.id
    assert collision.foreign_id == "demo_task_00"

    # And the other held-out partitions are untouched: the check localises the leak.
    assert reports[Partition.TRANSFER].clean()
    assert reports[Partition.ADVERSARIAL].clean()


def test_an_empty_foreign_set_is_refused_rather_than_passing(
    items: list[LiteItem],
) -> None:
    """A contamination check against nothing passes trivially, so it must not be possible."""
    with pytest.raises(ProvenanceError, match="passes trivially"):
        held_out_contamination(items, [])


def test_provenance_rejects_an_item_from_a_foreign_namespace(
    items: list[LiteItem],
) -> None:
    assert validate_provenance(items)["n"] == 40
    smuggled = list(items)
    smuggled[3] = replace(
        items[3], cso=replace(items[3].cso, generator="eval001::algebra_gen")
    )
    with pytest.raises(ProvenanceError, match="outside the .* namespace"):
        validate_provenance(smuggled)


def test_provenance_rejects_a_mixed_corpus_version(items: list[LiteItem]) -> None:
    mixed = list(items)
    mixed[7] = replace(items[7], cso=replace(items[7].cso, corpus_version="eval001-v1"))
    with pytest.raises(ProvenanceError, match="mixed corpus versions"):
        validate_provenance(mixed)


def test_provenance_rejects_duplicate_ids(items: list[LiteItem]) -> None:
    duped = [*items, replace(items[0])]
    with pytest.raises(ProvenanceError, match="duplicate item ids"):
        validate_provenance(duped)


def test_provenance_rejects_a_domain_outside_the_declared_strata(
    items: list[LiteItem],
) -> None:
    """An undeclared domain has no floor and no stratum, so it must not deal silently."""
    stray = list(items)
    stray[2] = replace(items[2], cso=replace(items[2].cso, domain="number_theory"))
    with pytest.raises(ProvenanceError, match="outside the declared strata"):
        assign_partitions(stray)


def test_a_promotion_item_is_stopped_by_the_human_gate_end_to_end(
    items: list[LiteItem],
) -> None:
    """The partition wired to gate 5, not merely declared.

    Every gate passes and the item is still not admitted, because a promotion decision is
    precisely where "the machinery was satisfied" is not a sufficient reason.
    """
    critical = promotion_critical_ids(items)
    assert len(critical) == 10
    assert critical == {i.id for i in partitioned(items)[Partition.PROMOTION]}

    item = next(i for i in items if i.id in critical)
    report, panel, negation = _clean_inputs(item)
    queue = ReviewQueue()
    funnel = run_funnel(
        [(item.id, item.cso.reference_hml)],
        semantic={item.id: report},
        panels={item.id: panel},
        negations={item.id: negation},
        queue=queue,
        promotion_critical=critical,
    )
    decision = funnel.decisions[0]
    assert [r.outcome for r in decision.records[:4]] == [GateOutcome.PASSED] * 4
    assert decision.records[-1].outcome is GateOutcome.ESCALATED
    assert not decision.admitted()
    with pytest.raises(HumanReviewRequired):
        queue.assert_clear(context="promotion")

    # The negative control: the same item, not promotion-critical, is admitted. Without
    # this the test would also pass if the funnel rejected everything.
    clean_queue = ReviewQueue()
    ordinary = run_funnel(
        [(item.id, item.cso.reference_hml)],
        semantic={item.id: report},
        panels={item.id: panel},
        negations={item.id: negation},
        queue=clean_queue,
    )
    assert ordinary.decisions[0].admitted()
    clean_queue.assert_clear(context="promotion")


# ===========================================================================
# 12. Nothing in this apparatus can call a model or a proof assistant
# ===========================================================================


_OWNED_PACKAGES = ("evaluation/corpus_governance", "evaluation/m3/lite")

_FORBIDDEN_IMPORTS = (
    "requests", "httpx", "urllib", "socket", "openai", "ollama", "aiohttp",
)
_FORBIDDEN_MODULES = ("evaluation.model_client", "evaluation.harness", "hamiltonian_lang.v1")


def _sources() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for package in _OWNED_PACKAGES:
        out.extend(sorted((REPO / package).glob("*.py")))
    assert len(out) >= 9, out
    return out


def test_no_module_here_can_reach_a_network_or_a_model_client() -> None:
    offenders: list[str] = []
    for path in _sources():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                root = name.split(".")[0]
                if root in _FORBIDDEN_IMPORTS or name in _FORBIDDEN_MODULES:
                    offenders.append(f"{path.name}: {name}")
    assert not offenders, offenders


#: Import roots that would let a module reach an external tool.
_FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"subprocess", "os", "importlib", "runpy", "pty", "shutil", "multiprocessing"}
)
#: Builtins that turn a string into running code. Their absence is what makes it safe to
#: scan identifiers only: a module with no execution primitive cannot execute a literal.
_FORBIDDEN_BUILTINS = frozenset({"exec", "eval", "compile", "open", "__import__"})
#: External-tool call sites, matched as whole identifiers or attribute names.
_FORBIDDEN_TOOL_NAMES = frozenset(
    {"lean_verify", "stanc", "Popen", "system", "popen", "spawn", "check_output", "call"}
)


def _external_tool_references(path: pathlib.Path) -> list[str]:
    """Every way this module could reach Lean, stanc, or any other external process.

    Identifiers and imports are matched **as whole names**, never as substrings. Substring
    matching is not an option here: ``stanc`` is a substring of ``isinstance``, which this
    package uses on nearly every line, so a substring scan reports the entire subsystem.

    Prose is excluded by *parsing*, not by a line-prefix heuristic. That distinction is the
    whole reason this helper exists. The line-based version this replaces flagged the
    ``corpus_governance`` package docstring — the paragraph explaining *why* no Lean path
    can certify anything on this host — as evidence of a dependency on Lean, i.e. it read
    the disclaimer as the offence.

    Scanning names rather than string literals is sound only because
    :data:`_FORBIDDEN_BUILTINS` is separately asserted absent: with no ``exec``, ``eval``,
    ``compile``, ``open`` or ``__import__`` anywhere in the package, a string containing
    ``"stanc"`` cannot become a call. ``negation.py`` contains exactly such a string — the
    per-item message recording that stanc is *absent* — and it is not a dependency.
    """
    offenders: list[str] = []
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        roots: list[str] = []
        if isinstance(node, ast.Import):
            roots = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots = [node.module]
        for name in roots:
            if name.split(".")[0] in _FORBIDDEN_IMPORT_ROOTS:
                offenders.append(f"{path.name}: imports {name}")
        if isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_BUILTINS:
                offenders.append(f"{path.name}: uses the builtin {node.id}")
            if node.id in _FORBIDDEN_TOOL_NAMES:
                offenders.append(f"{path.name}: names {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_TOOL_NAMES:
            offenders.append(f"{path.name}: calls .{node.attr}")
    return offenders


def test_no_lean_or_stan_path_is_relied_on(tmp_path: pathlib.Path) -> None:
    """Mathlib and stanc are absent and the Lean backend closes obligations with ``sorry``,
    so ``lean_verify`` rejects its own backend's output. Nothing here may depend on either.

    The negative controls at the end are not decoration. This assertion is a scan that
    finds nothing, and a scan that finds nothing is indistinguishable from a scan that
    looks for nothing — so the same scanner is pointed at a module that *does* offend and
    at one whose only mention is prose, and it must separate them.
    """
    offenders = [o for path in _sources() for o in _external_tool_references(path)]
    assert not offenders, offenders

    planted = tmp_path / "planted.py"
    planted.write_text(
        "import subprocess\n"
        "\n"
        "\n"
        "def verify(path: str) -> object:\n"
        "    proc = subprocess.Popen([path])\n"
        "    return lean_verify(proc)\n"
    )
    found = _external_tool_references(planted)
    assert any("imports subprocess" in o for o in found), found
    assert any("calls .Popen" in o for o in found), found
    assert any("names lean_verify" in o for o in found), found

    stanc_call = tmp_path / "stanc_call.py"
    stanc_call.write_text("def f(model: str) -> object:\n    return stanc(model)\n")
    assert _external_tool_references(stanc_call) == ["stanc_call.py: names stanc"]

    # Whole names, not substrings: ``stanc`` sits inside ``isinstance``.
    lookalike = tmp_path / "lookalike.py"
    lookalike.write_text("def f(x: object) -> bool:\n    return isinstance(x, str)\n")
    assert not _external_tool_references(lookalike)

    # Prose is not a dependency. This is the case the line-based scanner got wrong.
    prose_only = tmp_path / "prose.py"
    prose_only.write_text(
        '"""stanc is absent here and lean_verify rejects its own backend output."""\n\n'
        'REASON = "no deterministic disproof procedure applies: stanc is absent"\n'
    )
    assert not _external_tool_references(prose_only)


def test_the_governance_document_exists_and_states_the_funnel() -> None:
    doc = REPO / "docs" / "evaluation" / "BENCHMARK_GOVERNANCE.md"
    assert doc.exists()
    text = doc.read_text()
    for gate in GATE_ORDER:
        assert gate.replace("_", " ") in text.lower() or gate in text, gate
    assert "PREDICTED_NOT_MEASURED" in text
    assert CORPUS_GOVERNANCE_VERSION in text
