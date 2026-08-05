"""End to end, offline: one broken encoding, one repair, one complete audit trail.

No model is called. The "model output" is a fixture, which is the point -- the record has
to be reconstructible from the ledger alone, a year later, without the run that produced
it.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import __version__, compile_source
from hamiltonian_lang.improvement.diagnostics import adapt_all, assert_non_leaking
from hamiltonian_lang.improvement.episodes import (
    Condition,
    Episode,
    HypothesisId,
    HypothesisMixing,
    InputRepresentation,
    Verdict,
    assert_single_hypothesis,
    output_hash,
)
from hamiltonian_lang.improvement.events import EventType
from hamiltonian_lang.improvement.ledger import EventLedger
from hamiltonian_lang.improvement.verification import (
    Candidate,
    CandidateLanguage,
    CanonicalObject,
    classify,
    default_federation,
)

REFERENCE = "module m\n\nparam x : Real\nparam y : Real\nrequire x + y > 0.0\n"
BROKEN = "module m\n\nparam x : Real\nrequire z + y > 0.0\n"
REPAIRED = REFERENCE

H3 = Condition(InputRepresentation.HAMILTONIAN, False, True)


def clock():
    counter = iter(f"2026-08-05T00:00:{i:02d}+00:00" for i in range(60))
    return lambda: next(counter)


def test_a_repair_episode_leaves_a_complete_and_verifiable_trail(tmp_path):
    ledger = EventLedger(tmp_path / "events.jsonl", clock=clock())
    federation = default_federation()
    reference = CanonicalObject(object_id="obj-1", source=REFERENCE)

    ledger.append(
        episode_id="ep-1", event_type=EventType.EPISODE_CREATED,
        payload={"hypothesis_id": "H3", "condition": H3.to_dict()},
    )
    ledger.append(
        episode_id="ep-1", event_type=EventType.MODEL_GENERATED,
        payload={"output_hash": output_hash(BROKEN), "source": "fixture, not a model call"},
    )

    # 1. The initial attempt fails, and the diagnostics are structured but not leaky.
    first = federation.run(reference, Candidate(BROKEN, CandidateLanguage.HML))
    assert classify(first) == "INVALID"

    structured = adapt_all(compile_source(BROKEN).diagnostics.errors)
    for s in structured:
        assert_non_leaking(s, target_program=REFERENCE, final_answer="x + y > 0")
    ledger.append(
        episode_id="ep-1", event_type=EventType.DIAGNOSTIC_ISSUED,
        payload={"fingerprints": [s.fingerprint() for s in structured],
                 "codes": [s.code for s in structured]},
    )

    initial_episode = Episode(
        episode_id="ep-1",
        experiment_id="exp-offline-1",
        task_id="task-1",
        canonical_object_id="obj-1",
        hypothesis_id=HypothesisId.H3,
        condition=H3,
        language_version="hml-0.1.0",
        compiler_version=f"hamiltonian-lang {__version__}",
        verifier_versions=federation.versions(),
        input_representation=InputRepresentation.HAMILTONIAN,
        initial_output=BROKEN,
        initial_output_hash=output_hash(BROKEN),
        diagnostics=tuple(structured),
        verifier_results=first,
        final_verdict=Verdict.INVALID,
        training_eligible=False,
        exclusion_reason="initial attempt did not compile; kept as the repair antecedent",
    )

    # 2. The repair is a new episode object; the initial output survives untouched.
    second = federation.run(reference, Candidate(REPAIRED, CandidateLanguage.HML))
    repaired = initial_episode.with_repair(
        repair_output=REPAIRED,
        repaired_object_id=compile_source(REPAIRED).hash(),
        semantic_edit="bound the free name z to the declared parameter x",
        verifier_results=second,
        final_verdict=Verdict[classify(second)],
    )
    ledger.append(
        episode_id="ep-1", event_type=EventType.REPAIR_GENERATED,
        payload={"repair_output_hash": repaired.repair_output_hash,
                 "semantic_edit": repaired.semantic_edit},
    )
    ledger.append(
        episode_id="ep-1", event_type=EventType.EPISODE_CLASSIFIED,
        payload={"final_verdict": str(repaired.final_verdict),
                 "episode_digest": repaired.digest()},
    )

    # 3. The record survives.
    assert repaired.initial_output == BROKEN
    assert repaired.initial_output_hash == output_hash(BROKEN)
    assert repaired.repair_count == 1
    assert repaired.final_verdict is Verdict.INCONCLUSIVE, (
        "the repaired module matches the reference, but the type checker's constraint "
        "obligation is still open, so VERIFIED would over-claim"
    )

    verification = ledger.verify()
    assert verification.ok and verification.events_read == 5
    assert [e.event_type for e in ledger.events_for("ep-1")] == [
        EventType.EPISODE_CREATED,
        EventType.MODEL_GENERATED,
        EventType.DIAGNOSTIC_ISSUED,
        EventType.REPAIR_GENERATED,
        EventType.EPISODE_CLASSIFIED,
    ]

    # 4. An H3 result cannot be pooled with an H1 result later on.
    h1 = Episode(
        episode_id="ep-2", experiment_id="exp-offline-1", task_id="task-1",
        canonical_object_id="obj-1", hypothesis_id=HypothesisId.H1,
        condition=Condition(InputRepresentation.HAMILTONIAN, False, False),
        language_version="hml-0.1.0", compiler_version=f"hamiltonian-lang {__version__}",
        input_representation=InputRepresentation.HAMILTONIAN,
        training_eligible=False, exclusion_reason="control arm fixture",
    )
    with pytest.raises(HypothesisMixing):
        assert_single_hypothesis([repaired, h1])
