"""V1 layer 5 — discourse state.

The layer's whole claim is that these constructs are *executable*: a goal opens something,
only a proof closes it, a case split is checked, and what is left over is reported. The
tests that matter most are the ones showing a phrase either changes state or is refused
entry.
"""

from __future__ import annotations

from hamiltonian_lang.v1.discourse import (
    KERNEL_PHRASES,
    RHETORICAL_PHRASES,
    DiscourseConstruct,
    DiscourseState,
    PhraseClass,
    check_exhaustive,
    classify_phrase,
)
from hamiltonian_lang.v1.epistemic import EpistemicClaim, EpistemicStatus, Justification
from hamiltonian_lang.v1.transformation import (
    Operation,
    chain_of,
    expression,
    step,
)

PROOF = EpistemicClaim(status=EpistemicStatus.PROVED, body="the bound holds")
DEFINITIONAL = EpistemicClaim(
    status=EpistemicStatus.DEFINITIONALLY_TRUE, body="a square has four sides"
)
REFUTATION = EpistemicClaim(
    status=EpistemicStatus.DISPROVED, body="the converse fails at x = 0"
)
EVIDENCE = EpistemicClaim(
    status=EpistemicStatus.FAIL_TO_REJECT,
    body="the coin is fair",
    context={"null": "H0", "alpha": "0.05", "p_value": "0.18"},
)
ASSUMPTION = EpistemicClaim(
    status=EpistemicStatus.MODEL_CONDITIONAL,
    body="the errors are independent",
    context={"model": "M1"},
)
CREDENCE = EpistemicClaim(status=EpistemicStatus.POSSIBLE, body="the effect is real")


# ---------------------------------------------------------------------------
# goals open obligations
# ---------------------------------------------------------------------------


def test_a_goal_opens_an_obligation():
    state = DiscourseState("thm1")
    assert state.goal("g1", "the sequence converges") is None
    assert state.is_open("g1")
    assert state.current_goal == "g1"

    pending = state.remains_to_show()
    assert [p.name for p in pending] == ["g1"]
    assert pending[0].construct is DiscourseConstruct.GOAL


def test_open_goals_are_reported_at_end_of_module():
    state = DiscourseState("thm1")
    state.goal("g1", "the sequence converges")
    report = state.end_module()

    assert not report.clean
    assert [o.name for o in report.open_obligations] == ["g1"]
    assert "HML-G808" in report.codes()
    assert "remain to show" in report.render()


def test_a_discharged_goal_leaves_nothing_open():
    state = DiscourseState("thm1")
    state.goal("g1", "the sequence converges")
    assert state.established("g1", PROOF) is None

    report = state.end_module()
    assert report.clean
    assert report.established == ("g1",)
    assert report.open_obligations == ()
    assert "nothing remains to show" in report.render()


def test_a_subgoal_hangs_off_the_current_goal():
    state = DiscourseState()
    state.goal("g1", "the estimator is consistent")
    state.subgoal("g1a", "the bias vanishes")

    item = state.item("g1a")
    assert item is not None and item.parent == "g1"
    assert state.current_goal == "g1a"
    assert {p.name for p in state.remains_to_show()} == {"g1", "g1a"}


def test_a_subgoal_of_an_unknown_goal_is_reported():
    state = DiscourseState()
    error = state.subgoal("g1a", "the bias vanishes", of="nope")
    assert error is not None and error.code == "HML-G802"


def test_a_pending_obligation_is_part_of_the_derived_open_set():
    state = DiscourseState()
    state.pending_obligation("o1", "uniform integrability")
    assert [p.name for p in state.remains_to_show()] == ["o1"]
    assert state.remains_to_show()[0].construct is DiscourseConstruct.PENDING_OBLIGATION


# ---------------------------------------------------------------------------
# only a proof discharges
# ---------------------------------------------------------------------------


def test_a_goal_cannot_be_discharged_by_evidence():
    state = DiscourseState()
    state.goal("g1", "the coin is fair")

    error = state.established("g1", EVIDENCE)
    assert error is not None
    assert error.code == "HML-G803"
    assert "only by a Proof" in error.message
    assert state.is_open("g1"), "the goal must survive a failed discharge"


def test_a_goal_cannot_be_discharged_by_an_assumption():
    state = DiscourseState()
    state.goal("g1", "the errors are independent")

    error = state.established("g1", ASSUMPTION)
    assert error is not None
    assert error.code == "HML-G803"
    assert state.is_open("g1")


def test_a_goal_cannot_be_discharged_by_a_credence():
    state = DiscourseState()
    state.goal("g1", "the effect is real")
    error = state.established("g1", CREDENCE)
    assert error is not None and error.code == "HML-G803"
    assert state.is_open("g1")


def test_a_goal_is_discharged_by_a_proof_or_a_definition():
    for claim in (PROOF, DEFINITIONAL):
        state = DiscourseState()
        state.goal("g1", "the bound holds")
        assert state.established("g1", claim) is None
        assert not state.is_open("g1")
        assert claim.justification is Justification.PROOF


def test_a_converse_goal_is_discharged_by_a_refutation():
    state = DiscourseState()
    state.converse_goal("c1", of="g1")
    assert state.is_open("c1")
    assert state.established("c1", REFUTATION) is None
    assert state.end_module().clean


def test_an_unresolved_converse_is_reported_at_end_of_module():
    state = DiscourseState()
    state.converse_goal("c1", of="g1")
    report = state.end_module()
    assert [o.name for o in report.open_obligations] == ["c1"]
    assert report.open_obligations[0].origin == "converse of g1"


def test_establishing_an_unknown_or_already_closed_goal_is_reported():
    state = DiscourseState()
    assert state.established("ghost", PROOF).code == "HML-G802"

    state.goal("g1", "P")
    state.established("g1", PROOF)
    again = state.established("g1", PROOF)
    assert again is not None and again.code == "HML-G811"


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------


def test_a_non_exhaustive_case_split_is_reported():
    state = DiscourseState()
    state.goal("g1", "f(x) has a fixed point")
    state.consider_case("pos", "x > 0")
    state.consider_case("neg", "x < 0")

    error = state.end_case()
    assert error is not None
    assert error.code == "HML-G804"
    assert "x = 0 uncovered" in error.message


def test_an_otherwise_branch_makes_the_split_exhaustive():
    state = DiscourseState()
    state.consider_case("pos", "x > 0")
    state.otherwise()
    assert state.end_case() is None

    report = state.end_module()
    assert report.splits[0][1].shown is True
    assert "exhaustive" in report.render()


def test_a_split_that_names_every_cell_is_exhaustive():
    state = DiscourseState()
    state.consider_case("pos", "x > 0")
    state.consider_case("neg", "x < 0")
    state.consider_case("zero", "x = 0")
    assert state.end_case() is None


def test_exhaustiveness_offered_on_evidence_is_refused():
    state = DiscourseState()
    state.consider_case("pos", "x > 0")
    error = state.end_case(exhaustive_by=EVIDENCE)
    assert error is not None and error.code == "HML-G804"
    assert "only a Proof establishes it" in error.message


def test_exhaustiveness_proved_is_accepted():
    state = DiscourseState()
    state.consider_case("a", "x is rational")
    state.consider_case("b", "x is irrational")
    assert state.end_case(exhaustive_by=PROOF) is None


def test_an_undecidable_split_is_reported_not_assumed():
    state = DiscourseState()
    state.consider_case("a", "x is rational")
    state.consider_case("b", "x is irrational")
    error = state.end_case()
    assert error is not None and error.code == "HML-G804"
    assert "outside the decidable fragment" in error.message


def test_check_exhaustive_decides_only_what_it_can():
    covered = check_exhaustive(["x > 0", "x <= 0"])
    assert covered.decided and covered.exhaustive and covered.shown

    gap = check_exhaustive(["x > 0", "x < 0"])
    assert gap.decided and not gap.exhaustive
    assert gap.uncovered == "x = 0"

    interval_gap = check_exhaustive(["x < 0", "x > 1"])
    assert interval_gap.decided and not interval_gap.exhaustive

    two_variables = check_exhaustive(["x > 0", "y < 0"])
    assert not two_variables.decided and not two_variables.shown

    prose = check_exhaustive(["the matrix is symmetric"])
    assert not prose.decided

    empty = check_exhaustive([])
    assert not empty.exhaustive


def test_a_case_split_left_open_at_end_of_module_is_reported():
    state = DiscourseState()
    state.consider_case("pos", "x > 0")
    report = state.end_module()
    assert "HML-G805" in report.codes()


def test_otherwise_or_end_case_outside_a_split_is_reported():
    state = DiscourseState()
    assert state.otherwise().code == "HML-G809"
    assert state.end_case().code == "HML-G809"

    state2 = DiscourseState()
    state2.consider_case("pos", "x > 0")
    state2.otherwise()
    assert state2.otherwise().code == "HML-G809"


def test_returning_to_a_goal_from_inside_an_open_case_is_reported():
    state = DiscourseState()
    state.goal("g1", "P")
    state.consider_case("pos", "x > 0")

    error = state.return_to_goal("g1")
    assert error is not None and error.code == "HML-G807"

    state.otherwise()
    state.end_case()
    assert state.return_to_goal("g1") is None
    assert state.current_goal == "g1"


def test_returning_to_an_unknown_goal_is_reported():
    state = DiscourseState()
    assert state.return_to_goal("ghost").code == "HML-G802"


def test_a_goal_proved_only_inside_a_special_case_is_not_closed():
    """Proving the special case and calling the theorem done is the error here."""
    state = DiscourseState()
    state.goal("g1", "the map is a contraction")
    state.consider_case("small", "x < 1")

    error = state.established("g1", PROOF)
    assert error is not None
    assert error.code == "HML-G806"
    assert "conditional on those cases" in error.message
    assert state.is_open("g1")


def test_a_goal_opened_inside_a_case_may_be_closed_inside_it():
    state = DiscourseState()
    state.consider_case("small", "x < 1")
    state.goal("g1", "the map is a contraction on the small case")
    assert state.established("g1", PROOF) is None


# ---------------------------------------------------------------------------
# controlled English
# ---------------------------------------------------------------------------


def test_the_documented_phrase_mappings_hold():
    assert classify_phrase("We now show that P").construct is DiscourseConstruct.GOAL
    assert (
        classify_phrase("It remains to establish Q").construct
        is DiscourseConstruct.PENDING_OBLIGATION
    )
    assert (
        classify_phrase("Consider first the special case x = 0").construct
        is DiscourseConstruct.CONSIDER_CASE
    )
    assert (
        classify_phrase("The converse need not hold").construct
        is DiscourseConstruct.CONVERSE_GOAL
    )


def test_for_completeness_does_not_enter_the_kernel():
    mapping = classify_phrase("For completeness, we record the constant.")
    assert mapping.classification is PhraseClass.RENDERER_ONLY
    assert mapping.construct is None
    assert mapping.enters_kernel is False
    assert "for completeness" in mapping.rhetorical


def test_applying_a_rhetorical_phrase_changes_nothing_at_all():
    state = DiscourseState()
    state.goal("g1", "P")
    before = state.snapshot()

    for phrase in RHETORICAL_PHRASES:
        mapping = state.apply_phrase(phrase, name="x1", statement="something")
        assert mapping.enters_kernel is False
        assert state.snapshot() == before, f"{phrase!r} altered checker state"

    assert state.item("x1") is None
    assert state.errors() == ()


def test_no_rhetorical_phrase_maps_to_a_construct():
    for phrase in RHETORICAL_PHRASES:
        mapping = classify_phrase(phrase)
        assert mapping.construct is None
        assert mapping.classification is PhraseClass.RENDERER_ONLY
        assert mapping.reason


def test_the_two_phrase_tables_do_not_overlap():
    assert set(KERNEL_PHRASES) & set(RHETORICAL_PHRASES) == set()


def test_rhetorical_material_is_dropped_but_a_real_construct_still_lands():
    state = DiscourseState()
    mapping = state.apply_phrase(
        "For completeness, we now show that the bound is tight",
        name="g1",
        statement="the bound is tight",
    )
    assert mapping.enters_kernel is True
    assert mapping.construct is DiscourseConstruct.GOAL
    assert mapping.rhetorical == ("for completeness",)
    assert state.is_open("g1")


def test_longest_phrase_match_wins():
    mapping = classify_phrase("It remains to show that the limit exists")
    assert mapping.matched == "it remains to show"
    assert mapping.construct is DiscourseConstruct.PENDING_OBLIGATION


def test_an_unrecognised_sentence_enters_nothing():
    state = DiscourseState()
    before = state.snapshot()
    mapping = state.apply_phrase("The determinant equals seventeen.")
    assert mapping.classification is PhraseClass.UNRECOGNISED
    assert state.snapshot() == before


def test_a_closing_phrase_without_a_claim_does_not_close_anything():
    state = DiscourseState()
    state.goal("g1", "P")
    mapping = state.apply_phrase("This completes the proof", name="g1")
    assert mapping.enters_kernel is True
    assert state.is_open("g1")
    assert "HML-G803" in [e.code for e in state.errors()]


def test_a_closing_phrase_with_a_proof_does_close_the_goal():
    state = DiscourseState()
    state.goal("g1", "P")
    state.apply_phrase("This completes the proof", name="g1", claim=PROOF)
    assert not state.is_open("g1")


def test_a_dependency_phrase_records_a_dependency():
    state = DiscourseState()
    state.goal("g1", "the estimator is consistent")
    state.apply_phrase(
        "Under the assumption that the errors are independent",
        statement="the errors are independent",
    )
    report = state.end_module()
    assert any(d.on == "the errors are independent" for d in report.dependencies)


def test_a_case_phrase_opens_a_branch():
    state = DiscourseState()
    state.apply_phrase(
        "Consider first the special case", name="zero", statement="x = 0"
    )
    state.apply_phrase("Otherwise", name="rest")
    assert state.end_case() is None


# ---------------------------------------------------------------------------
# integration with layer 2
# ---------------------------------------------------------------------------


def test_transformation_obligations_become_open_discourse_obligations():
    chain = chain_of(
        [expression("e1", "a*x = a*y")],
        [
            step(
                "s1",
                source="e1",
                operation=Operation.DIVIDE_THROUGH,
                target="e2",
                arguments={"by": "a"},
                assumptions=["a is real"],
            ),
            step("s2", source="e2", operation=Operation.SQUARE_BOTH_SIDES, target="e3"),
        ],
    )
    chain_report = chain.validate()
    assert chain_report.valid

    state = DiscourseState("lemma")
    state.goal("g1", "x = y")
    opened = state.absorb(chain_report)
    assert opened == ("s1#0",)

    report = state.end_module()
    statements = [o.statement for o in report.open_obligations]
    assert "a != 0" in statements
    assert any(o.origin == "step s1" for o in report.open_obligations)
    # the squaring weakening travels with the derivation without becoming an obligation
    assert len(report.weakenings) == 1
    assert "not reversible" in report.weakenings[0].lost
    assert any(d.on == "a is real" for d in report.dependencies)
    assert "HML-G808" in report.codes()


def test_absorbing_obligations_directly_works_too():
    chain = chain_of(
        [expression("e1")],
        [
            step(
                "s1",
                source="e1",
                operation=Operation.TAKE_LOG,
                target="e2",
                arguments={"of": "1 - p"},
            )
        ],
    )
    state = DiscourseState()
    names = state.absorb_obligations(chain.validate().obligations)
    assert names == ("s1#0",)
    assert state.remains_to_show()[0].statement == "1 - p > 0"


def test_the_module_report_renders_every_section():
    state = DiscourseState("worked")
    state.goal("g1", "the bound is tight")
    state.dependency_notice("g1", "the model M1")
    state.consider_case("pos", "x > 0")
    state.end_case()
    text = state.end_module().render()
    for fragment in ("# module worked", "remain to show", "discourse error", "case splits",
                     "dependencies"):
        assert fragment in text
