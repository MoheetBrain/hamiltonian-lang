"""Phase 3 — the concept-minting protocol.

The protocol exists to refuse candidates, so most of this file is refusals. Two of them
carry the weight:

* a **duplicate under a new name** is returned ``duplicate``, because a handle is not a
  concept;
* a candidate that **compresses nothing** is returned ``duplicate`` even when every other
  check passes, because a well-typed name for something already sayable is a synonym.

The third is the claim ledger: a property that an executed test refutes is recorded
``unsupported``, never ``proved``, whatever the author declared.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang.v1.minting import (
    MINIMUM_RECURRENCE,
    AdmissionReport,
    CompressionEvidence,
    ConceptCandidate,
    ConstraintCheck,
    CounterexampleTest,
    Example,
    Finding,
    PropertyClaim,
    Severity,
    TypeSignatureError,
    adjudicate_claim,
    mint,
    parse_type_signature,
    resolve_verdict,
    search_registry,
    summarise,
)
from hamiltonian_lang.v1.registry import (
    Claim,
    ClaimStatus,
    Concept,
    ConceptRegistry,
    Lifecycle,
    Parameter,
    Provenance,
    Relation,
    RelationKind,
    validate_document,
)

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

_DEFINITION = (
    "The law of mu + sigma * Z, where Z follows the given standard law, mu is the "
    "location and sigma the scale."
)


def a_concept(canonical_id: str = "LocationScaleFamily", **overrides: object) -> Concept:
    fields: dict[str, object] = {
        "canonical_id": canonical_id,
        "namespace": "hml.v1.statistics",
        "version": "0.1.0",
        "type_signature": (
            "Distribution[Real] * Real * PositiveReal -> Distribution[Real]"
        ),
        "domain": "Distribution[Real] * Real * PositiveReal",
        "codomain": "Distribution[Real]",
        "formal_definition": _DEFINITION,
        "provenance": Provenance(proposed_by="tests", proposed_at="2026-08-05"),
        "parameters": (
            Parameter(name="standard", type="Distribution[Real]", role="standard_law"),
            Parameter(name="mu", type="Real", role="location"),
            Parameter(name="sigma", type="PositiveReal", role="scale"),
        ),
        "constraints": ("sigma > 0",),
        "compresses": ("mu + sigma * Z with Z standard",),
    }
    fields.update(overrides)
    return Concept(**fields)  # type: ignore[arg-type]


def good_compression() -> CompressionEvidence:
    return CompressionEvidence(
        structure="mu + sigma * Z with Z standard",
        occurrences=(
            "examples/statistics/normal_model.hml:12",
            "examples/statistics/student_t.hml:8",
            "examples/statistics/logistic_regression.hml:31",
        ),
        expansion="the law of mu + sigma * Z where Z follows the standard law",
        abbreviation="LocationScaleFamily(F, mu, sigma)",
    )


def a_candidate(concept: Concept | None = None, **overrides: object) -> ConceptCandidate:
    fields: dict[str, object] = {
        "concept": concept if concept is not None else a_concept(),
        "examples": (
            Example("the standard normal is a member", lambda: True),
            Example("scaling by 2 stays in the family", lambda: True),
        ),
        "claims": (
            PropertyClaim(
                statement="the family is closed under affine maps",
                claimed_status=ClaimStatus.CONJECTURED,
            ),
        ),
        "constraint_checks": (ConstraintCheck("sigma > 0", lambda: True),),
        "compression": (good_compression(),),
    }
    fields.update(overrides)
    return ConceptCandidate(**fields)  # type: ignore[arg-type]


def a_registry() -> ConceptRegistry:
    return ConceptRegistry()


# ---------------------------------------------------------------------------
# The happy path, so that every rejection below is attributable to one cause
# ---------------------------------------------------------------------------


def test_a_sound_candidate_is_admitted_and_recorded() -> None:
    registry = a_registry()
    report = mint(a_candidate(), registry, admitted_at="2026-08-05T10:00:00Z")

    assert report.admitted
    assert report.verdict is Lifecycle.ADMITTED
    assert report.blocking_findings == ()
    assert report.reason() == "every check passed"

    stored = registry.get("LocationScaleFamily")
    assert stored.admission_status is Lifecycle.ADMITTED
    assert stored.provenance.admitted_at == "2026-08-05T10:00:00Z"
    assert stored.admission_report is not None
    assert stored.admission_report.is_complete()
    assert stored.admission_report.verdict is Lifecycle.ADMITTED


def test_the_eight_steps_run_in_order() -> None:
    """Findings arrive in step order, and no step is skipped once an earlier one objects."""
    registry = a_registry()
    mint(a_candidate(), registry)  # so that step 1 has something to find

    report = mint(
        a_candidate(
            a_concept("AffineLawFamily", compresses=()),
            constraint_checks=(),
            claims=(PropertyClaim("closure holds", ClaimStatus.PROVED),),
            counterexample_tests=(
                CounterexampleTest("all have a mean", "the Cauchy family", lambda: True),
            ),
        ),
        registry,
    )
    steps = [f.step for f in report.findings]
    assert steps == sorted(steps)
    # every step that had something to say is present, including the ones after the first
    # objection: the report is complete rather than truncated
    assert set(steps) == {1, 2, 4, 5, 7, 8}


def test_record_false_leaves_the_registry_untouched() -> None:
    registry = a_registry()
    report = mint(a_candidate(), registry, record=False)
    assert report.admitted
    assert not report.recorded
    assert len(registry) == 0


def test_a_minted_registry_still_validates_against_the_schema() -> None:
    registry = a_registry()
    mint(a_candidate(), registry)
    mint(a_candidate(a_concept("ScaleFamily", compresses=("sigma * Z",))), registry)
    validate_document(registry.to_json())
    assert ConceptRegistry.from_json(registry.to_json()) == registry


# ---------------------------------------------------------------------------
# Step 1 and 2 — a new name for an old concept
# ---------------------------------------------------------------------------


def test_a_duplicate_under_a_new_name_is_rejected_as_duplicate() -> None:
    """The headline case. Renaming a concept does not create one."""
    registry = a_registry()
    first = mint(a_candidate(), registry)
    assert first.admitted

    # Same signature, same constraints, same definition — a different handle only.
    renamed = a_concept("AffineLawFamily", aliases=("shift_scale",))
    report = mint(a_candidate(renamed), registry)

    assert report.verdict is Lifecycle.DUPLICATE
    assert not report.admitted
    assert "DUPLICATE_OF_EXISTING" in report.blocking_codes
    assert report.search.equality_matches == ("LocationScaleFamily",)
    assert report.duplicate_of == "LocationScaleFamily"

    stored = registry.get("AffineLawFamily")
    assert stored.admission_status is Lifecycle.DUPLICATE
    assert stored.provenance.duplicate_of == "LocationScaleFamily"
    assert stored.provenance.rejected_reason


def test_a_renaming_of_the_parameters_is_also_a_duplicate() -> None:
    """`f(x) = x^2` and `f(y) = y^2` are one concept, not two."""
    registry = a_registry()
    mint(a_candidate(), registry)

    alpha_renamed = a_concept(
        "ShiftScaleFamily",
        formal_definition=(
            "The law of a + b * Z, where Z follows the given standard law, a is the "
            "location and b the scale."
        ),
        parameters=(
            Parameter(name="standard", type="Distribution[Real]", role="standard_law"),
            Parameter(name="a", type="Real", role="location"),
            Parameter(name="b", type="PositiveReal", role="scale"),
        ),
        constraints=("b > 0",),
    )
    report = mint(
        a_candidate(
            alpha_renamed, constraint_checks=(ConstraintCheck("b > 0", lambda: True),)
        ),
        registry,
    )

    assert report.verdict is Lifecycle.DUPLICATE
    assert report.search.renaming_matches == ("LocationScaleFamily",)
    assert "RENAMING_OF_EXISTING" in report.blocking_codes


def test_renaming_detection_only_abstracts_declared_parameters() -> None:
    """A stated limit, tested so that it stays a choice rather than becoming a surprise.

    A free symbol the concept does not declare as a parameter is not abstracted, so two
    definitions differing only in such a symbol are reported as two concepts. Erring this
    way costs a redundant entry; erring the other way would report unrelated concepts as
    duplicates.
    """
    registry = a_registry()
    mint(a_candidate(), registry)

    free_symbol_renamed = a_concept(
        "ShiftScaleFamilyW",
        formal_definition=(
            "The law of mu + sigma * W, where W follows the given standard law, mu is the "
            "location and sigma the scale."
        ),
    )
    search = search_registry(free_symbol_renamed, registry)
    assert search.equality_matches == ()
    assert search.renaming_matches == ()


def test_a_specialisation_is_a_genuinely_new_abstraction() -> None:
    """Adding a constraint is not renaming. Step 2 has to tell them apart."""
    registry = a_registry()
    mint(a_candidate(), registry)

    specialised = a_concept(
        "SymmetricLocationScaleFamily",
        constraints=("sigma > 0", "the standard law is symmetric about zero"),
        compresses=("symmetric mu + sigma * Z with Z standard",),
    )
    report = mint(
        a_candidate(
            specialised,
            constraint_checks=(
                ConstraintCheck("sigma > 0", lambda: True),
                ConstraintCheck(
                    "the standard law is symmetric about zero", lambda: True
                ),
            ),
            compression=(
                CompressionEvidence(
                    structure="symmetric mu + sigma * Z with Z standard",
                    occurrences=("examples/a.hml:1", "examples/b.hml:2"),
                    expansion="a location-scale family whose standard law is symmetric",
                    abbreviation="SymmetricLocationScale(F, mu, sigma)",
                ),
            ),
        ),
        registry,
    )

    assert report.admitted
    assert report.search.specialisation_of == ("LocationScaleFamily",)
    assert report.search.equality_matches == ()
    assert "NOVEL_STRUCTURE" in report.codes


def test_a_taken_canonical_id_is_a_duplicate() -> None:
    registry = a_registry()
    mint(a_candidate(), registry)
    report = mint(
        a_candidate(a_concept(formal_definition="Something else entirely, quite unlike it.")),
        registry,
    )
    assert report.verdict is Lifecycle.DUPLICATE
    assert "CANONICAL_ID_TAKEN" in report.blocking_codes
    # the incumbent is untouched
    assert registry.get("LocationScaleFamily").admission_status is Lifecycle.ADMITTED


def test_a_match_against_a_rejected_entry_does_not_count() -> None:
    """The ground a rejected concept occupied is free again."""
    registry = a_registry()
    rejected = mint(a_candidate(a_concept("Doomed", compresses=())), registry)
    assert rejected.verdict is Lifecycle.DUPLICATE

    search = search_registry(a_concept("Fresh"), registry)
    assert search.equality_matches == ()
    assert search.renaming_matches == ()


# ---------------------------------------------------------------------------
# Step 3 — a valid type signature and a formal definition
# ---------------------------------------------------------------------------


def test_parse_type_signature_splits_at_the_top_level_arrow_only() -> None:
    domain, codomain = parse_type_signature("Sample -> Function[Real -> Real]")
    assert domain == "Sample"
    assert codomain == "Function [ Real -> Real ]"

    domain, codomain = parse_type_signature(
        "Dataset[Real] * LossFunction[Real, Real] -> ArgminSet[Real]"
    )
    assert "LossFunction" in domain
    assert codomain == "ArgminSet [ Real ]"


@pytest.mark.parametrize(
    "signature",
    [
        "",
        "Real",
        "Real ->",
        "-> Real",
        "Real -> [Real]",
        "Distribution[Real -> Real",
        "Real -> Real]",
        "Real ** Real -> Real",
    ],
)
def test_a_malformed_type_signature_is_refused(signature: str) -> None:
    with pytest.raises(TypeSignatureError):
        parse_type_signature(signature)


def test_an_invalid_type_signature_rejects_the_candidate() -> None:
    report = mint(
        a_candidate(a_concept(type_signature="Distribution[Real", domain="x", codomain="y")),
        a_registry(),
    )
    assert report.verdict is Lifecycle.REJECTED
    assert not report.type_valid
    assert "INVALID_TYPE_SIGNATURE" in report.blocking_codes


def test_a_signature_that_disagrees_with_the_domain_field_is_rejected() -> None:
    report = mint(
        a_candidate(a_concept(domain="Real")), a_registry()
    )
    assert report.verdict is Lifecycle.REJECTED
    assert "DOMAIN_MISMATCH" in report.blocking_codes


@pytest.mark.parametrize(
    "definition", ["", "TODO", "see above", "Standard.", "LocationScaleFamily", "a law"]
)
def test_a_placeholder_definition_is_not_a_definition(definition: str) -> None:
    report = mint(
        a_candidate(a_concept(formal_definition=definition)), a_registry()
    )
    assert report.verdict is Lifecycle.REJECTED
    assert not report.definition_present
    assert "NO_FORMAL_DEFINITION" in report.blocking_codes


def test_two_parameters_may_not_claim_the_same_role() -> None:
    report = mint(
        a_candidate(
            a_concept(
                parameters=(
                    Parameter(name="standard", type="Distribution[Real]", role="scale"),
                    Parameter(name="mu", type="Real", role="scale"),
                    Parameter(name="sigma", type="PositiveReal", role="scale"),
                )
            )
        ),
        a_registry(),
    )
    assert report.verdict is Lifecycle.REJECTED
    assert "PARAMETER_ROLE_REPEATED" in report.blocking_codes


def test_a_candidate_may_not_cite_an_unadmitted_dependency() -> None:
    registry = a_registry()
    registry.add(a_concept("Draft"))
    report = mint(
        a_candidate(a_concept("Citing", dependencies=("Draft",))), registry
    )
    assert report.verdict is Lifecycle.REJECTED
    assert "DEPENDENCY_NOT_ADMITTED" in report.blocking_codes


def test_a_candidate_may_not_cite_a_concept_that_does_not_exist() -> None:
    report = mint(
        a_candidate(a_concept("Citing", dependencies=("Nowhere",))), a_registry()
    )
    assert report.verdict is Lifecycle.REJECTED
    assert "DEPENDENCY_MISSING" in report.blocking_codes


# ---------------------------------------------------------------------------
# Step 4 — declared constraints
# ---------------------------------------------------------------------------


def test_a_violated_constraint_rejects_the_candidate() -> None:
    report = mint(
        a_candidate(constraint_checks=(ConstraintCheck("sigma > 0", lambda: False),)),
        a_registry(),
    )
    assert report.verdict is Lifecycle.REJECTED
    assert not report.constraints_verified
    assert "CONSTRAINT_VIOLATED" in report.blocking_codes


def test_a_constraint_with_no_check_is_unverified_not_satisfied() -> None:
    report = mint(a_candidate(constraint_checks=()), a_registry())
    assert not report.constraints_verified
    assert "CONSTRAINT_UNVERIFIED" in report.codes
    # unverified is a gap in evidence, not a falsehood, so it becomes an obligation
    assert any("sigma > 0" in o.statement for o in report.obligations)
    assert report.admitted


def test_a_constraint_check_that_raises_is_a_rejection_not_a_crash() -> None:
    def boom() -> bool:
        raise ZeroDivisionError("sigma was zero")

    report = mint(
        a_candidate(constraint_checks=(ConstraintCheck("sigma > 0", boom),)), a_registry()
    )
    assert report.verdict is Lifecycle.REJECTED
    assert "CONSTRAINT_CHECK_RAISED" in report.blocking_codes


# ---------------------------------------------------------------------------
# Step 5 — proof obligations
# ---------------------------------------------------------------------------


def test_every_unproved_claim_becomes_an_obligation() -> None:
    report = mint(
        a_candidate(
            claims=(
                PropertyClaim("closed under affine maps", ClaimStatus.CONJECTURED),
                PropertyClaim(
                    "the scale is identifiable",
                    ClaimStatus.PROVED,
                    proof="proofs/identifiability",
                    proof_checked=True,
                ),
            )
        ),
        a_registry(),
    )
    statements = [o.statement for o in report.obligations]
    assert "closed under affine maps" in statements
    assert "the scale is identifiable" not in statements
    assert report.obligations_generated == len(report.obligations)


def test_an_unproved_declared_relation_generates_an_obligation() -> None:
    concept = a_concept(
        equivalences=(
            Relation(
                other="AffineImage",
                kind=RelationKind.EQUIVALENT_TO,
                status=ClaimStatus.CONJECTURED,
                conditions=("sigma > 0",),
            ),
        )
    )
    report = mint(a_candidate(concept), a_registry())
    obligation = next(o for o in report.obligations if "AffineImage" in o.statement)
    assert "sigma > 0" in obligation.statement
    assert obligation.status is ClaimStatus.CONJECTURED


# ---------------------------------------------------------------------------
# Step 6 — examples and counterexamples are executed
# ---------------------------------------------------------------------------


def test_examples_are_actually_run() -> None:
    calls: list[str] = []

    def record(name: str) -> bool:
        calls.append(name)
        return True

    report = mint(
        a_candidate(
            examples=(
                Example("first", lambda: record("first")),
                Example("second", lambda: record("second")),
            )
        ),
        a_registry(),
    )
    assert calls == ["first", "second"]
    assert (report.examples_tested, report.examples_passed) == (2, 2)


def test_a_failing_example_rejects_the_candidate() -> None:
    report = mint(
        a_candidate(
            examples=(
                Example("holds", lambda: True),
                Example("does not hold", lambda: False),
            )
        ),
        a_registry(),
    )
    assert report.verdict is Lifecycle.REJECTED
    assert (report.examples_tested, report.examples_passed) == (2, 1)
    assert "EXAMPLE_FAILED" in report.blocking_codes


def test_a_concept_with_no_example_is_rejected() -> None:
    report = mint(a_candidate(examples=()), a_registry())
    assert report.verdict is Lifecycle.REJECTED
    assert "NO_EXAMPLE" in report.blocking_codes


def test_a_counterexample_that_refutes_nothing_is_a_false_record() -> None:
    report = mint(
        a_candidate(
            counterexample_tests=(
                CounterexampleTest(
                    refutes="every location-scale family has a mean",
                    witness="the normal family",
                    run=lambda: False,
                ),
            )
        ),
        a_registry(),
    )
    assert report.verdict is Lifecycle.REJECTED
    assert "COUNTEREXAMPLE_DOES_NOT_REFUTE" in report.blocking_codes
    assert report.counterexamples_tested == 1
    assert report.counterexamples_verified == 0


def test_a_genuine_counterexample_is_recorded_as_verified() -> None:
    registry = a_registry()
    report = mint(
        a_candidate(
            counterexample_tests=(
                CounterexampleTest(
                    refutes="every location-scale family has a mean",
                    witness="the Cauchy location-scale family",
                    run=lambda: True,
                ),
            )
        ),
        registry,
    )
    assert report.admitted
    stored = registry.get("LocationScaleFamily")
    assert stored.counterexamples[0].verified is True
    assert stored.counterexamples[0].witness == "the Cauchy location-scale family"


# ---------------------------------------------------------------------------
# Step 7 — a concept that compresses nothing is a synonym
# ---------------------------------------------------------------------------


def test_a_concept_that_compresses_nothing_is_rejected() -> None:
    """The prominent rejection path: everything else is fine and it still fails."""
    registry = a_registry()
    report = mint(a_candidate(a_concept("Gaussianoid", compresses=())), registry)

    assert not report.admitted
    assert report.verdict is Lifecycle.DUPLICATE
    assert not report.compression_demonstrated
    assert "COMPRESSES_NOTHING" in report.blocking_codes

    # It failed for exactly one reason. Nothing else was wrong with it.
    assert report.type_valid
    assert report.definition_present
    assert report.constraints_verified
    assert report.examples_passed == report.examples_tested == 2
    assert all(c.status is not ClaimStatus.UNSUPPORTED for c in report.claim_adjudications)
    assert report.blocking_codes == ("COMPRESSES_NOTHING",)

    assert registry.get("Gaussianoid").admission_status is Lifecycle.DUPLICATE


def test_a_structure_cited_once_does_not_recur() -> None:
    report = mint(
        a_candidate(
            compression=(
                CompressionEvidence(
                    structure="mu + sigma * Z with Z standard",
                    occurrences=("examples/only_here.hml:3",),
                    expansion="the law of mu + sigma * Z where Z follows the standard law",
                    abbreviation="LocationScaleFamily(F, mu, sigma)",
                ),
            )
        ),
        a_registry(),
    )
    assert report.verdict is Lifecycle.DUPLICATE
    assert "COMPRESSION_NOT_DEMONSTRATED" in report.codes
    assert "COMPRESSES_NOTHING" in report.blocking_codes


def test_the_same_site_cited_twice_does_not_recur() -> None:
    report = mint(
        a_candidate(
            compression=(
                CompressionEvidence(
                    structure="mu + sigma * Z with Z standard",
                    occurrences=("examples/a.hml:3", "examples/a.hml:3"),
                    expansion="the law of mu + sigma * Z where Z follows the standard law",
                    abbreviation="LocationScaleFamily(F, mu, sigma)",
                ),
            )
        ),
        a_registry(),
    )
    assert report.verdict is Lifecycle.DUPLICATE
    assert "COMPRESSES_NOTHING" in report.blocking_codes


def test_an_abbreviation_that_is_not_shorter_abbreviates_nothing() -> None:
    report = mint(
        a_candidate(
            compression=(
                CompressionEvidence(
                    structure="mu + sigma * Z with Z standard",
                    occurrences=("examples/a.hml:1", "examples/b.hml:2"),
                    expansion="mu + sigma * Z",
                    abbreviation="LocationScaleFamily(standard_law, location, scale)",
                ),
            )
        ),
        a_registry(),
    )
    assert report.verdict is Lifecycle.DUPLICATE
    assert not report.compression_demonstrated


def test_a_compression_claim_with_no_evidence_is_recorded_not_accepted() -> None:
    report = mint(a_candidate(compression=()), a_registry())
    assert report.verdict is Lifecycle.DUPLICATE
    assert "COMPRESSION_UNEVIDENCED" in report.codes
    assert not report.compression_demonstrated


def test_recurrence_threshold_is_stated_not_implied() -> None:
    assert MINIMUM_RECURRENCE == 2
    evidence = good_compression()
    assert evidence.recurs and evidence.shortens and evidence.demonstrated


# ---------------------------------------------------------------------------
# Step 8 — the claim ledger
# ---------------------------------------------------------------------------


def test_a_false_property_is_recorded_unsupported_not_proved() -> None:
    """The headline claim case. The author says 'proved'; the test says otherwise."""
    statement = "every location-scale family has a finite mean"
    registry = a_registry()
    report = mint(
        a_candidate(
            claims=(
                PropertyClaim(
                    statement=statement,
                    claimed_status=ClaimStatus.PROVED,
                    test=lambda: False,  # the Cauchy family refutes it
                ),
            )
        ),
        registry,
    )

    adjudicated = report.claim(statement)
    assert adjudicated.status is ClaimStatus.UNSUPPORTED
    assert adjudicated.status is not ClaimStatus.PROVED
    assert adjudicated.claimed_status is ClaimStatus.PROVED
    assert adjudicated.refuted
    assert adjudicated.downgraded

    assert not report.admitted
    assert "CLAIM_REFUTED" in report.blocking_codes

    stored = registry.get("LocationScaleFamily")
    recorded = next(c for c in stored.invariants if c.statement == statement)
    assert recorded.status is ClaimStatus.UNSUPPORTED
    assert recorded.discharged_by is None


def test_claiming_proved_with_nothing_behind_it_is_unsupported() -> None:
    statement = "the family is closed under affine maps"
    report = mint(
        a_candidate(
            claims=(PropertyClaim(statement, ClaimStatus.PROVED),)
        ),
        a_registry(),
    )
    assert report.claim(statement).status is ClaimStatus.UNSUPPORTED
    assert not report.admitted
    assert "CLAIM_UNSUPPORTED" in report.blocking_codes


def test_an_honest_conjecture_keeps_its_status_and_is_admissible() -> None:
    statement = "the family is closed under affine maps"
    report = mint(
        a_candidate(claims=(PropertyClaim(statement, ClaimStatus.CONJECTURED),)),
        a_registry(),
    )
    assert report.claim(statement).status is ClaimStatus.CONJECTURED
    assert report.admitted


def test_a_passing_test_is_evidence_and_never_a_proof() -> None:
    statement = "the family is closed under affine maps"
    report = mint(
        a_candidate(
            claims=(PropertyClaim(statement, ClaimStatus.PROVED, test=lambda: True),)
        ),
        a_registry(),
    )
    adjudicated = report.claim(statement)
    assert adjudicated.status is ClaimStatus.TESTED
    assert adjudicated.status is not ClaimStatus.PROVED
    assert adjudicated.downgraded
    assert "CLAIM_DOWNGRADED" in report.codes
    assert report.admitted


def test_an_unchecked_proof_reference_is_a_conjecture() -> None:
    claim = PropertyClaim(
        "closure holds",
        ClaimStatus.PROVED,
        proof="proofs/closure.lean",
        proof_checked=False,
    )
    assert adjudicate_claim(claim).status is ClaimStatus.CONJECTURED


def test_a_checked_proof_is_a_proof() -> None:
    claim = PropertyClaim(
        "closure holds",
        ClaimStatus.CONJECTURED,
        proof="proofs/closure.lean",
        proof_checked=True,
    )
    adjudicated = adjudicate_claim(claim)
    assert adjudicated.status is ClaimStatus.PROVED
    assert adjudicated.discharged_by == "proofs/closure.lean"


def test_a_test_that_raises_refutes_the_claim() -> None:
    def boom() -> bool:
        raise ArithmeticError("undefined for the Cauchy family")

    adjudicated = adjudicate_claim(
        PropertyClaim("has a mean", ClaimStatus.PROVED, test=boom)
    )
    assert adjudicated.status is ClaimStatus.UNSUPPORTED
    assert adjudicated.refuted


def test_an_invariant_written_into_the_concept_is_adjudicated_too() -> None:
    """Writing a claim into the record directly does not get it past the ledger."""
    statement = "the shape is invariant under scaling"
    report = mint(
        a_candidate(
            a_concept(
                invariants=(
                    Claim(statement=statement, status=ClaimStatus.PROVED),
                )
            ),
            claims=(),
        ),
        a_registry(),
    )
    assert report.claim(statement).status is ClaimStatus.UNSUPPORTED
    assert not report.admitted


# ---------------------------------------------------------------------------
# Verdict resolution
# ---------------------------------------------------------------------------


def test_rejected_takes_precedence_over_duplicate() -> None:
    findings = (
        Finding(2, "DUPLICATE_OF_EXISTING", Severity.BLOCKING, "", Lifecycle.DUPLICATE),
        Finding(3, "INVALID_TYPE_SIGNATURE", Severity.BLOCKING, "", Lifecycle.REJECTED),
    )
    assert resolve_verdict(findings) is Lifecycle.REJECTED
    assert resolve_verdict(tuple(reversed(findings))) is Lifecycle.REJECTED


def test_notes_never_block() -> None:
    findings = (Finding(1, "NOVEL_STRUCTURE", Severity.NOTE, "fine"),)
    assert resolve_verdict(findings) is Lifecycle.ADMITTED


def test_a_malformed_duplicate_reports_the_deeper_fault() -> None:
    registry = a_registry()
    mint(a_candidate(), registry)
    report = mint(
        a_candidate(a_concept("AffineLawFamily", type_signature="Distribution[Real")),
        registry,
    )
    assert report.verdict is Lifecycle.REJECTED
    assert "INVALID_TYPE_SIGNATURE" in report.blocking_codes


def test_summarise_counts_verdicts() -> None:
    registry = a_registry()
    reports: list[AdmissionReport] = [
        mint(a_candidate(), registry),
        mint(a_candidate(a_concept("Synonym", compresses=())), registry),
    ]
    counts = summarise(reports)
    assert counts[Lifecycle.ADMITTED] == 1
    assert counts[Lifecycle.DUPLICATE] == 1


def test_the_report_renders_its_reasoning() -> None:
    report = mint(a_candidate(a_concept("Synonym", compresses=())), a_registry())
    rendered = report.render()
    assert "Synonym: duplicate" in rendered
    assert "COMPRESSES_NOTHING" in rendered
