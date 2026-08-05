"""``require`` is a constraint; ``prove`` is a claim. Conflating them is the main hazard.

This file is a regression test for a real defect found while building the engine. The
first implementation read every obligation universally, so ``require x >= 0`` for a free
real ``x`` was "refuted" by the witness ``x = -1`` — a confident, authoritative-looking
failure on a perfectly good program. The Lean backend already documents the correct
reading in its own words: an HML ``require`` is *"a constraint the model must satisfy,
i.e. an obligation over free variables"*, and read literally as a theorem it "may be
false".

So:

* ``require`` / ``assume``  -> the obligation is **satisfiability**. Discharged by a
  model; refuted only by proving that none exists.
* ``prove`` / ``invariant`` -> the obligation is **universal truth**. Discharged by a
  proof; refuted by one counterexample.

Both directions are asserted, because each mistake has its own failure mode: reading a
``require`` universally invents failures, and reading a ``prove`` existentially invents
successes. The second is the worse of the two.
"""

from __future__ import annotations

from hamiltonian_lang.verification.obligations import (
    GlobalVerdict,
    ObligationStatus,
    verify_source,
)
from hamiltonian_lang.verification.obligations.records import ObligationMode


def _modes(source: str) -> dict[str, ObligationMode]:
    return {r.statement: r.mode for r in verify_source(source).records}


def test_a_require_is_read_as_a_constraint_not_a_theorem() -> None:
    outcome = verify_source("module M\nvar x : Real\nrequire x >= 0\n")
    assert outcome.verdict is GlobalVerdict.VERIFIED
    constraint = next(r for r in outcome.records if r.statement == "x >= 0")
    assert constraint.mode is ObligationMode.SATISFIABLE
    assert constraint.status is ObligationStatus.DISCHARGED
    assert "model" in constraint.evidence


def test_the_same_proposition_under_prove_is_read_universally_and_is_not_verified() -> None:
    """``x >= 0`` for a free real is satisfiable but not universally true."""
    outcome = verify_source("module M\nvar x : Real\nprove x >= 0\n")
    assert outcome.verdict is GlobalVerdict.DISPROVED
    claim = next(r for r in outcome.records if r.statement == "x >= 0")
    assert claim.mode is ObligationMode.UNIVERSAL
    assert claim.status is ObligationStatus.FAILED
    assert claim.witness is not None


def test_an_assume_is_a_hypothesis_and_carries_a_consistency_obligation() -> None:
    modes = _modes("module M\nvar x : Real\nassume x > 3\n")
    assert modes["x > 3"] is ObligationMode.SATISFIABLE


def test_a_concept_invariant_is_universal() -> None:
    source = (
        "module M\n"
        "concept Scaled\n"
        "  parameter scale : PositiveReal\n"
        "  invariant positive_scale := scale > 0\n"
        "  example unit := 1.0\n"
        "end\n"
    )
    outcome = verify_source(source)
    invariants = [r for r in outcome.records if "positive_scale" in r.statement]
    assert invariants
    assert all(r.mode is ObligationMode.UNIVERSAL for r in invariants)


def test_a_refinement_obligation_is_universal() -> None:
    modes = _modes("module M\nparam s : PositiveReal\n")
    assert modes["s > 0"] is ObligationMode.UNIVERSAL


def test_a_dimension_obligation_is_structural() -> None:
    modes = _modes(
        "module M\nparam m : Quantity[Mass]\ndef e := m\ncheck dimension e = Mass\n"
    )
    assert any(m is ObligationMode.STRUCTURAL for m in modes.values())


def test_an_unattributable_obligation_defaults_to_the_strict_reading() -> None:
    """Guessing 'satisfiable' would be the permissive guess, and permissive guesses pass."""
    from hamiltonian_lang.ast.nodes import Span
    from hamiltonian_lang.type_system import ProofObligation
    from hamiltonian_lang.verification.obligations.engine import _mode_of

    orphan = ProofObligation("constraint", "x > 0", Span(line=999, col=99))
    mode, where = _mode_of(orphan, {})
    assert mode is ObligationMode.UNIVERSAL
    assert where == "unattributed"


def test_a_satisfiable_obligation_is_still_refuted_when_no_model_exists() -> None:
    """Satisfiability is not a free pass: the declarations can rule a constraint out."""
    outcome = verify_source("module M\nparam p : Probability\nrequire p > 1\n")
    assert outcome.verdict is GlobalVerdict.DISPROVED
    failure = outcome.first_failure()
    assert failure is not None and failure.mode is ObligationMode.SATISFIABLE
    assert failure.witness is not None
    assert "intersection empty" in failure.witness.evaluated
