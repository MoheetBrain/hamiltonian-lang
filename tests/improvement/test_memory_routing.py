"""Phase 10 — routing into four append-only stores, and the rules that fill them.

The load-bearing assertions here are the negative ones: quarantined data cannot be made
training-eligible by any route, an unlabelled failure is not quietly filed as a negative
example, and deduplication is structural rather than a similarity threshold.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from hamiltonian_lang.improvement.memory import (
    AppendStatus,
    MemoryBank,
    MemoryRecord,
    MemoryStore,
    MemoryStoreKind,
    NearMissKind,
    QuarantineEligibilityError,
    QuarantineReason,
    RoutingDecision,
    RoutingDisagreement,
    RoutingFacts,
    TrainingPolicy,
    VerifierOutcome,
    build_record,
    canonical_hash_of,
    exact_hash_of,
    route,
    route_episode,
)
from hamiltonian_lang.improvement.state import Hypothesis

H3 = Hypothesis.H3_VERIFIER_GUIDED_REPAIR
H1 = Hypothesis.H1_REPRESENTATION_AS_INPUT

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "hamiltonian_lang" / "improvement"


def facts(**kw) -> RoutingFacts:
    base = {
        "episode_id": "ep-1",
        "hypothesis": H3,
        "exact_hash": "e" * 64,
        "canonical_hash": "c" * 64,
        "required_verifiers": ("canonical_form",),
        "verifier_results": {"canonical_form": VerifierOutcome.PASS},
        "provenance_complete": True,
    }
    base.update(kw)
    return RoutingFacts(**base)


def positive_facts(**kw) -> RoutingFacts:
    defaults = {"first_attempt_parsed": True, "first_attempt_semantic_fidelity": True}
    defaults.update(kw)
    return facts(**defaults)


def repair_facts(**kw) -> RoutingFacts:
    defaults = {
        "first_attempt_parsed": False,
        "structured_diagnostic_codes": ("HML-T415",),
        "repair_attempts": 1,
        "repair_verified": True,
    }
    defaults.update(kw)
    return facts(**defaults)


# ---------------------------------------------------------------------------
# The four stores
# ---------------------------------------------------------------------------


def test_first_attempt_success_routes_to_positive():
    d = route(positive_facts())
    assert d.store is MemoryStoreKind.POSITIVE
    assert d.training_eligible


def test_an_unresolved_obligation_keeps_an_episode_out_of_positive_memory():
    d = route(positive_facts(unresolved_obligations=1))
    assert d.store is not MemoryStoreKind.POSITIVE


def test_a_declared_but_absent_verifier_is_not_a_pass():
    d = route(positive_facts(verifier_results={}))
    assert d.store is MemoryStoreKind.QUARANTINE
    assert QuarantineReason.INCONCLUSIVE_VERIFICATION in d.quarantine_reasons


def test_no_required_verifier_means_nothing_was_required_to_pass():
    d = route(positive_facts(required_verifiers=(), verifier_results={}))
    assert d.store is MemoryStoreKind.QUARANTINE


def test_one_diagnosed_repair_that_verifies_routes_to_repair():
    d = route(repair_facts())
    assert d.store is MemoryStoreKind.REPAIR
    assert d.training_eligible


def test_two_repairs_do_not_route_to_repair_memory():
    d = route(repair_facts(repair_attempts=2))
    assert d.store is MemoryStoreKind.QUARANTINE
    assert "exactly one repair is required" in " ".join(d.reasons)


def test_a_repair_with_no_structured_diagnostic_is_not_repair_memory():
    d = route(repair_facts(structured_diagnostic_codes=()))
    assert d.store is MemoryStoreKind.QUARANTINE


def test_a_minimal_attributable_near_miss_routes_to_hard_negative():
    d = route(
        facts(
            first_attempt_parsed=True,
            verifier_results={"canonical_form": VerifierOutcome.FAIL},
            near_miss_kinds=(NearMissKind.WRONG_ARITY,),
            attributed_skill_ids=("typing.function_arity",),
        )
    )
    assert d.store is MemoryStoreKind.HARD_NEGATIVE
    assert d.near_miss is NearMissKind.WRONG_ARITY


def test_two_near_misses_are_not_minimal_and_are_quarantined():
    d = route(
        facts(
            first_attempt_parsed=True,
            verifier_results={"canonical_form": VerifierOutcome.FAIL},
            near_miss_kinds=(NearMissKind.WRONG_ARITY, NearMissKind.WRONG_ROLE),
            attributed_skill_ids=("typing.function_arity",),
        )
    )
    assert d.store is MemoryStoreKind.QUARANTINE
    assert QuarantineReason.AMBIGUOUS_LABEL in d.quarantine_reasons


def test_an_unattributed_failure_is_quarantined_rather_than_labelled():
    d = route(facts(first_attempt_parsed=True, verifier_results={"canonical_form": VerifierOutcome.FAIL}))
    assert d.store is MemoryStoreKind.QUARANTINE
    assert QuarantineReason.AMBIGUOUS_LABEL in d.quarantine_reasons
    # The refusal explains itself against all three positive stores.
    assert len(d.reasons) == 3


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"unsupported_backend_dependency": True}, QuarantineReason.UNSUPPORTED_BACKEND),
        (
            {"verifier_results": {"canonical_form": VerifierOutcome.INCONCLUSIVE}},
            QuarantineReason.INCONCLUSIVE_VERIFICATION,
        ),
        (
            {"verifier_results": {"canonical_form": VerifierOutcome.UNSUPPORTED}},
            QuarantineReason.UNSUPPORTED_BACKEND,
        ),
        ({"semantic_loss": True}, QuarantineReason.SEMANTIC_LOSS),
        ({"ambiguous_label": True}, QuarantineReason.AMBIGUOUS_LABEL),
        (
            {"evaluation_contamination": True},
            QuarantineReason.POTENTIAL_EVALUATION_CONTAMINATION,
        ),
        ({"provenance_complete": False}, QuarantineReason.MISSING_PROVENANCE),
        ({"untrusted_synthetic_truth": True}, QuarantineReason.UNTRUSTED_SYNTHETIC_TRUTH),
    ],
)
def test_every_quarantine_trigger_wins_over_an_otherwise_perfect_episode(kwargs, reason):
    d = route(positive_facts(**kwargs))
    assert d.store is MemoryStoreKind.QUARANTINE
    assert reason in d.quarantine_reasons
    assert not d.training_eligible


# ---------------------------------------------------------------------------
# Quarantine is never training-eligible
# ---------------------------------------------------------------------------


def test_a_quarantined_record_cannot_be_constructed_as_training_eligible():
    f = positive_facts(semantic_loss=True)
    d = route(f)
    with pytest.raises(QuarantineEligibilityError):
        MemoryRecord(
            record_id="r-1",
            episode_id=f.episode_id,
            hypothesis=f.hypothesis,
            store=MemoryStoreKind.QUARANTINE,
            exact_hash=f.exact_hash,
            canonical_hash=f.canonical_hash,
            training_eligible=True,
            decision=d,
        )


def test_the_store_re_checks_eligibility_even_if_the_record_was_tampered_with():
    """The record guard and the store guard are independent, and both must hold."""
    record = build_record("r-1", positive_facts(semantic_loss=True))
    assert record.store is MemoryStoreKind.QUARANTINE
    object.__setattr__(record, "training_eligible", True)  # bypass the first guard
    store = MemoryStore(MemoryStoreKind.QUARANTINE, H3)
    with pytest.raises(QuarantineEligibilityError):
        store.append(record)


def test_a_training_batch_never_contains_quarantined_rows():
    bank = MemoryBank()
    bank.admit(build_record("good", positive_facts()))
    bank.admit(build_record("bad", positive_facts(semantic_loss=True, episode_id="ep-2")))
    batch = bank.training_batch(H3)
    assert [r.record_id for r in batch] == ["good"]
    assert bank.quarantined_ids(H3) == ("bad",)


def test_quarantine_cannot_even_be_requested_as_a_training_source():
    bank = MemoryBank()
    with pytest.raises(QuarantineEligibilityError):
        bank.training_batch(H3, kinds=[MemoryStoreKind.QUARANTINE])


def test_a_record_may_not_disagree_with_its_own_routing_decision():
    f = positive_facts()
    with pytest.raises(ValueError, match="routing decision"):
        MemoryRecord(
            record_id="r-1",
            episode_id=f.episode_id,
            hypothesis=f.hypothesis,
            store=MemoryStoreKind.HARD_NEGATIVE,
            exact_hash=f.exact_hash,
            canonical_hash=f.canonical_hash,
            training_eligible=True,
            decision=route(f),
        )


# ---------------------------------------------------------------------------
# Append-only and deduplication
# ---------------------------------------------------------------------------


def test_stores_expose_no_removal_or_mutation_api():
    forbidden = {"remove", "delete", "pop", "clear", "update", "__setitem__", "__delitem__"}
    assert forbidden.isdisjoint(dir(MemoryStore))
    assert forbidden.isdisjoint(dir(MemoryBank))


def test_records_are_frozen():
    record = build_record("r-1", positive_facts())
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.training_eligible = False  # type: ignore[misc]


def test_an_exact_duplicate_is_recorded_but_not_stored_twice():
    store = MemoryStore(MemoryStoreKind.POSITIVE, H3)
    assert store.append(build_record("a", positive_facts())).status is AppendStatus.APPENDED
    second = store.append(build_record("b", positive_facts(episode_id="ep-2")))
    assert second.status is AppendStatus.EXACT_DUPLICATE
    assert second.existing_record_id == "a"
    assert len(store) == 1
    assert len(store.duplicates) == 1


def test_alpha_equivalent_encodings_deduplicate_on_the_canonical_hash():
    """Renaming a bound variable changes the text and not the meaning."""
    first = "module Ordering\n\nassume forall x : Real . x = x\n"
    second = "module Ordering\n\nassume forall y : Real . y = y\n"
    assert exact_hash_of(first) != exact_hash_of(second)
    assert canonical_hash_of(first) == canonical_hash_of(second) is not None

    store = MemoryStore(MemoryStoreKind.POSITIVE, H3)
    store.append(
        build_record(
            "a", positive_facts(exact_hash=exact_hash_of(first), canonical_hash=canonical_hash_of(first))
        )
    )
    outcome = store.append(
        build_record(
            "b",
            positive_facts(
                episode_id="ep-2",
                exact_hash=exact_hash_of(second),
                canonical_hash=canonical_hash_of(second),
            ),
        )
    )
    assert outcome.status is AppendStatus.ALPHA_EQUIVALENT_DUPLICATE
    assert len(store) == 1


def test_output_that_does_not_compile_has_no_canonical_identity():
    assert canonical_hash_of("module Broken\n\nconst x : Real = \n") is None


def test_deduplication_does_not_cross_hypotheses():
    """The same content under two hypotheses is two answers, not one duplicate."""
    bank = MemoryBank()
    bank.admit(build_record("h3", positive_facts(hypothesis=H3)))
    bank.admit(build_record("h1", positive_facts(hypothesis=H1)))
    assert len(bank.records(MemoryStoreKind.POSITIVE, H3)) == 1
    assert len(bank.records(MemoryStoreKind.POSITIVE, H1)) == 1
    assert bank.counts() == {("positive", "H1"): 1, ("positive", "H3"): 1}


def test_a_store_refuses_a_record_from_another_hypothesis():
    store = MemoryStore(MemoryStoreKind.POSITIVE, H3)
    with pytest.raises(ValueError, match="never merged"):
        store.append(build_record("h1", positive_facts(hypothesis=H1)))


def test_routing_facts_reject_an_untyped_hypothesis():
    with pytest.raises(TypeError, match="Hypothesis"):
        facts(hypothesis="H3")


def test_a_verification_of_a_repair_that_never_happened_is_rejected():
    with pytest.raises(ValueError, match="did not happen"):
        facts(repair_attempts=0, repair_verified=True)


# ---------------------------------------------------------------------------
# The deduplicator is structural, not a similarity threshold
# ---------------------------------------------------------------------------

_EMBEDDING_TOKENS = (
    "embedding",
    "embeddings",
    "faiss",
    "chromadb",
    "pinecone",
    "weaviate",
    "qdrant",
    "sentence_transformers",
    "sentencetransformer",
    "cosine_similarity",
    "nearest_neighbors",
    "nearest_neighbours",
    "hnswlib",
    "annoy",
    "sklearn",
)


def _identifiers(tree: ast.AST) -> set[str]:
    """Every name the code *uses* — docstrings and comments are not code."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            found.add(node.name)
        elif isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.update((node.module or "").split("."))
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.keyword) and node.arg:
            found.add(node.arg)
    return {f.lower() for f in found}


def test_no_vector_embedding_is_used_as_the_semantic_deduplicator():
    """A tunable similarity threshold would silently change what the corpus contains."""
    offenders: list[str] = []
    for path in sorted(PACKAGE.glob("*.py")):
        names = _identifiers(ast.parse(path.read_text(encoding="utf-8")))
        for token in _EMBEDDING_TOKENS:
            if any(token in name for name in names):
                offenders.append(f"{path.name}: {token}")
    assert not offenders, f"vector-similarity machinery appears in code: {offenders}"


# ---------------------------------------------------------------------------
# The router is the only authority on training eligibility
# ---------------------------------------------------------------------------


def test_a_routing_decision_cannot_represent_an_eligible_quarantine():
    """The strongest form of the guarantee: the illegal state is unrepresentable."""
    with pytest.raises(QuarantineEligibilityError, match="never trainable"):
        RoutingDecision(
            store=MemoryStoreKind.QUARANTINE,
            training_eligible=True,
            reasons=("a caller insisted",),
        )


def test_an_eligible_decision_cannot_carry_quarantine_reasons():
    with pytest.raises(QuarantineEligibilityError, match="trusted or it is not"):
        RoutingDecision(
            store=MemoryStoreKind.POSITIVE,
            training_eligible=True,
            reasons=("looks fine",),
            quarantine_reasons=(QuarantineReason.SEMANTIC_LOSS,),
        )


def test_build_record_refuses_a_decision_that_disagrees_with_the_facts():
    """``decision=`` used to be an override. It is now a claim that gets checked.

    This is the defect in one call: quarantined facts plus a hand-made positive decision
    used to produce a stored, training-eligible row.
    """
    quarantined = positive_facts(semantic_loss=True)
    forged = RoutingDecision(
        store=MemoryStoreKind.POSITIVE,
        training_eligible=True,
        reasons=("hand-written",),
    )
    with pytest.raises(RoutingDisagreement, match="router decides"):
        build_record("r-1", quarantined, decision=forged)

    # A decision that agrees is still accepted, so the parameter keeps its purpose.
    good = positive_facts()
    assert build_record("r-2", good, decision=route(good)).training_eligible is True


def test_route_episode_refuses_an_episode_whose_facts_change_the_hypothesis():
    class Mismatched:
        episode_id = "ep-1"
        hypothesis = H1

        def routing_facts(self) -> RoutingFacts:
            return positive_facts(episode_id="ep-1", hypothesis=H3)

    with pytest.raises(RoutingDisagreement, match="cannot both be true"):
        route_episode(Mismatched())


# ---------------------------------------------------------------------------
# Hard negatives require an explicit policy
# ---------------------------------------------------------------------------


def hard_negative_facts(**kw) -> RoutingFacts:
    base = {
        "first_attempt_parsed": True,
        "first_attempt_semantic_fidelity": False,
        "near_miss_kinds": (NearMissKind.WRONG_ROLE,),
        "attributed_skill_ids": ("skill.probability.roles",),
        "required_verifiers": (),
        "verifier_results": {},
    }
    base.update(kw)
    return facts(**base)


def test_a_hard_negative_is_stored_but_not_trained_on_by_default():
    d = route(hard_negative_facts())
    assert d.store is MemoryStoreKind.HARD_NEGATIVE
    assert d.training_eligible is False
    assert any("NOT training-eligible" in r for r in d.reasons)


def test_a_hard_negative_becomes_eligible_only_under_a_declared_policy():
    policy = TrainingPolicy(
        hard_negatives_eligible=True,
        rationale="contrastive fine-tuning run R-7; approved 2026-08-05",
    )
    d = route(hard_negative_facts(), policy)
    assert d.store is MemoryStoreKind.HARD_NEGATIVE
    assert d.training_eligible is True
    assert any("R-7" in r for r in d.reasons)


def test_a_hard_negative_decision_cannot_claim_eligibility_without_the_policy():
    with pytest.raises(QuarantineEligibilityError, match="policy that says so"):
        RoutingDecision(
            store=MemoryStoreKind.HARD_NEGATIVE,
            training_eligible=True,
            reasons=("a near miss",),
            near_miss=NearMissKind.WRONG_ROLE,
        )


def test_the_policy_travels_with_the_decision():
    policy = TrainingPolicy(hard_negatives_eligible=True, rationale="run R-7")
    doc = route(hard_negative_facts(), policy).to_dict()
    assert doc["policy"]["hard_negatives_eligible"] is True
    assert doc["policy"]["rationale"] == "run R-7"
    assert doc["decided_by"].endswith("memory.route")


# ---------------------------------------------------------------------------
# EXCLUDED is never trainable and never aggregated
# ---------------------------------------------------------------------------


def test_an_excluded_hypothesis_quarantines_an_otherwise_perfect_episode():
    d = route(positive_facts(hypothesis=Hypothesis.EXCLUDED))
    assert d.store is MemoryStoreKind.QUARANTINE
    assert QuarantineReason.EXCLUDED_HYPOTHESIS in d.quarantine_reasons
    assert d.training_eligible is False


def test_an_excluded_record_cannot_be_marked_training_eligible():
    f = positive_facts()
    with pytest.raises(QuarantineEligibilityError, match="never trainable"):
        MemoryRecord(
            record_id="r-1",
            episode_id=f.episode_id,
            hypothesis=Hypothesis.EXCLUDED,
            store=MemoryStoreKind.POSITIVE,
            exact_hash=f.exact_hash,
            canonical_hash=f.canonical_hash,
            training_eligible=True,
            decision=route(f),
        )


def test_acq0_routes_normally_and_stays_separate_from_h3():
    """ACQ0 is a real experiment with real training-eligible rows. It is simply keyed
    into its own stores, so ACQ0_REPAIR data can never be drawn as H3 data."""
    bank = MemoryBank()
    bank.admit(build_record("acq0", positive_facts(hypothesis=Hypothesis.ACQ0)))
    bank.admit(build_record("h3", positive_facts(episode_id="ep-2")))
    assert [r.record_id for r in bank.training_batch(Hypothesis.ACQ0)] == ["acq0"]
    assert [r.record_id for r in bank.training_batch(H3)] == ["h3"]
