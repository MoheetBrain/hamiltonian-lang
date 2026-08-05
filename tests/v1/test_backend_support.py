"""Tests for the V1 backend support matrix — HML-V1-CONCEPT-001 Phase 8.

The table's job is to stop a report claiming more than was measured, so these tests are
mostly about what the table must REFUSE to say:

* ``verified_by_toolchain`` cannot be raised without an evidence record reporting a real,
  accepting run — and for Lean, exit code 0 is explicitly not enough, because a
  ``sorry``-closed false theorem also exits 0.
* An ``unsupported`` cell must say why. "Unsupported" with no reason is indistinguishable
  from "nobody looked".
* The two established measured limitations — Stan cannot express strict positivity, and
  the Lean route drops probability laws detectably only by content hash — must both be
  represented, so that a later edit cannot quietly drop them.

One test optionally re-runs Lean when it is installed, so the recorded acceptance is
re-checkable rather than a claim frozen in a string literal.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hamiltonian_lang.v1.backend_support import (
    LEAN_EPISTEMIC,
    SUPPORT,
    TOOLCHAINS,
    V0_LAYERS,
    V1_LAYERS,
    Backend,
    Layer,
    Obstacle,
    Status,
    Support,
    ToolchainEvidence,
    entry,
    registry_backend_support,
    supported,
    toolchain,
    unverified,
)
from hamiltonian_lang.v1.epistemic import EpistemicStatus

REPO = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# The central invariant: verification cannot be asserted, only evidenced
# ---------------------------------------------------------------------------


def test_nothing_is_verified_without_an_evidence_record():
    """The headline rule. No cell may claim verification with nothing behind it."""
    for (layer, backend), s in SUPPORT.items():
        if s.verified_by_toolchain:
            assert s.evidence is not None, (
                f"{layer}/{backend} claims toolchain verification with no evidence"
            )
            assert s.evidence.command.strip(), (
                f"{layer}/{backend} claims verification without recording a command"
            )
            assert s.evidence.exit_code == 0, (
                f"{layer}/{backend} claims verification from a failing run"
            )


def test_verified_by_toolchain_has_no_setter():
    """It is a derived property, so it cannot be set directly on a frozen dataclass."""
    s = entry(Layer.V0_QUANTIFIER, Backend.LEAN)
    with pytest.raises((AttributeError, TypeError)):
        s.verified_by_toolchain = False  # type: ignore[misc]


def test_lean_exit_zero_is_not_sufficient_for_verification():
    """`theorem : (1 : Nat) = 2 := by sorry` exits 0. Exit status alone certifies nothing."""
    sorry_closed = ToolchainEvidence(
        tool="lean",
        version="4.32.2",
        command="lean Skeleton.lean",
        exit_code=0,
        output="warning: declaration uses `sorry`",
        sorry_free=False,
        scope="a skeleton closed with sorry",
        establishes="that the file elaborates",
        does_not_establish="that anything in it is true",
    )
    assert not sorry_closed.accepted, (
        "a sorry-closed Lean run must never count as acceptance"
    )

    real_proof = ToolchainEvidence(
        tool="lean",
        version="4.32.2",
        command="lean Proof.lean",
        exit_code=0,
        output="'t' does not depend on any axioms",
        sorry_free=True,
        scope="a theorem with a real proof term",
        establishes="kernel acceptance",
        does_not_establish="anything about ℝ-typed content",
    )
    assert real_proof.accepted


def test_lean_evidence_must_state_whether_it_was_sorry_free():
    """A Lean run that exited 0 without answering the `sorry` question is incomplete."""
    with pytest.raises(ValueError, match="sorry"):
        ToolchainEvidence(
            tool="lean",
            version="4.32.2",
            command="lean X.lean",
            exit_code=0,
            output="",
            scope="something",
            establishes="something",
            does_not_establish="something",
        )


def test_a_failing_run_is_never_acceptance():
    """Negative evidence is recorded, but it never raises the verified flag."""
    rejected = ToolchainEvidence(
        tool="lean",
        version="4.32.2",
        command="lean QuantScope.lean",
        exit_code=1,
        output="error: unknown module prefix 'Mathlib'",
        scope="V0 Lean backend output",
        establishes="that it does not compile here",
        does_not_establish="that the emitted statements are wrong",
    )
    assert not rejected.accepted


def test_evidence_must_record_what_it_does_not_establish():
    """An unbounded verification claim is the failure mode the field exists to stop."""
    with pytest.raises(ValueError, match="does NOT establish|not establish"):
        ToolchainEvidence(
            tool="sympy",
            version="1.14.0",
            command="python m.py",
            exit_code=0,
            output="",
            scope="a module",
            establishes="that it runs",
            does_not_establish="   ",
        )


def test_an_accepting_run_cannot_back_an_unsupported_cell():
    """The two would contradict each other, so the constructor refuses."""
    ok = ToolchainEvidence(
        tool="sympy",
        version="1.14.0",
        command="python m.py",
        exit_code=0,
        output="",
        scope="a module",
        establishes="that it runs",
        does_not_establish="that the mathematics survived",
    )
    with pytest.raises(ValueError, match="unsupported"):
        Support(
            layer=Layer.V0_PROBABILITY_LAW,
            backend=Backend.SYMPY,
            status=Status.UNSUPPORTED,
            reason="laws are dropped",
            evidence=ok,
        )


def test_evidence_from_the_wrong_tool_cannot_back_a_row():
    lean_ev = ToolchainEvidence(
        tool="lean",
        version="4.32.2",
        command="lean X.lean",
        exit_code=0,
        output="",
        sorry_free=True,
        scope="a Lean file",
        establishes="kernel acceptance",
        does_not_establish="anything about SymPy",
    )
    with pytest.raises(ValueError, match="cannot back"):
        Support(
            layer=Layer.V0_DEFINITION,
            backend=Backend.SYMPY,
            status=Status.PARTIAL,
            losses=("something",),
            evidence=lean_ev,
        )


# ---------------------------------------------------------------------------
# Every unsupported entry carries a reason; every partial one carries losses
# ---------------------------------------------------------------------------


def test_every_unsupported_entry_carries_a_reason():
    for (layer, backend), s in SUPPORT.items():
        if s.status is Status.UNSUPPORTED:
            assert s.reason.strip(), (
                f"{layer}/{backend} is unsupported with no stated reason"
            )
            assert len(s.reason) > 40, (
                f"{layer}/{backend}: the reason is too short to be a reason: {s.reason!r}"
            )


def test_unsupported_without_a_reason_is_rejected_at_construction():
    with pytest.raises(ValueError, match="reason"):
        Support(
            layer=Layer.MORPHOLOGY,
            backend=Backend.STAN,
            status=Status.UNSUPPORTED,
        )


def test_every_partial_entry_enumerates_its_losses():
    for (layer, backend), s in SUPPORT.items():
        if s.status is Status.PARTIAL:
            assert s.losses, f"{layer}/{backend} is partial but declares no losses"


def test_partial_without_losses_is_rejected_at_construction():
    with pytest.raises(ValueError, match="losses"):
        Support(
            layer=Layer.V0_DEFINITION,
            backend=Backend.LEAN,
            status=Status.PARTIAL,
        )


def test_supported_entries_declare_no_losses():
    """A `supported` cell with a hedge attached is really a `partial` cell."""
    with pytest.raises(ValueError, match="supported"):
        Support(
            layer=Layer.V0_QUANTIFIER,
            backend=Backend.LEAN,
            status=Status.SUPPORTED,
            losses=("actually something is lost",),
        )


# ---------------------------------------------------------------------------
# The two established measured limitations must be represented
# ---------------------------------------------------------------------------


def test_stan_positive_real_limitation_is_represented():
    """Stan's `real<lower=0>` admits 0; HML's PositiveReal does not.

    This is the single largest limitation in the table and the reason most probabilistic
    models cannot round-trip through Stan. It must not go missing.
    """
    s = entry(Layer.V0_REFINEMENT_SCALAR, Backend.STAN)
    blob = " ".join(s.losses) + " " + s.reason
    assert "PositiveReal" in blob, "the PositiveReal limitation is not stated"
    assert "lower=0" in blob, "the `real<lower=0>` mechanism is not named"
    assert "admits 0" in blob or "admits zero" in blob, (
        "the table must say WHY the two differ: Stan's bound is closed"
    )
    # The consequence — most families are excluded — must be stated too.
    assert "Uniform" in blob and "Binomial" in blob and "Bernoulli" in blob, (
        "the three families that DO survive must be named, since they are the exception"
    )
    for family in ("Normal", "Beta", "Gamma", "Exponential"):
        assert family in blob, f"{family} is blocked by this limitation and must be listed"

    law = entry(Layer.V0_PROBABILITY_LAW, Backend.STAN)
    assert "PositiveReal" in " ".join(law.losses), (
        "the law row must also carry the PositiveReal consequence"
    )


def test_lean_law_dropping_limitation_is_represented():
    """The Lean route drops probability laws and the reconstruction still compiles.

    Only the content-hash comparison detects it, which is the strongest argument in the
    codebase for round-tripping as a validation method. It must stay in the table.
    """
    s = entry(Layer.V0_PROBABILITY_LAW, Backend.LEAN)
    assert s.status is Status.UNSUPPORTED
    blob = s.reason
    assert "content-hash" in blob or "content hash" in blob, (
        "the table must record that ONLY the content hash detects this loss"
    )
    assert "compiles" in blob, (
        "the danger is that the reconstruction compiles happily; that must be stated"
    )
    assert "one-way" in blob, (
        "a one-way test cannot detect this class of loss, which is the point"
    )


def test_stan_loses_observed_values_and_declaration_order():
    """Both were measured in tests/roundtrip/test_importers.py and are carried here."""
    obs = entry(Layer.V0_OBSERVED_VALUE, Backend.STAN)
    assert obs.status is Status.UNSUPPORTED
    assert "data file" in obs.reason, "Stan reads data from a data file, not the program"

    order = entry(Layer.V0_DECLARATION_ORDER, Backend.STAN)
    assert order.status is Status.UNSUPPORTED
    assert "content hash" in order.reason


# ---------------------------------------------------------------------------
# Toolchain reality
# ---------------------------------------------------------------------------


def test_stan_is_never_marked_verified_because_stanc_is_absent():
    assert not toolchain("stanc").present
    for (layer, backend), s in SUPPORT.items():
        if backend is Backend.STAN:
            assert not s.verified_by_toolchain, (
                f"{layer}/stan claims verification, but stanc is not installed"
            )


def test_mathlib_absence_is_recorded_because_it_gates_every_real_typed_row():
    mathlib = toolchain("mathlib")
    assert not mathlib.present
    assert "ℝ" in mathlib.detail, (
        "the consequence — every HML real scalar maps to ℝ, which lives in Mathlib — "
        "must be recorded, not just the bare absence"
    )


def test_every_toolchain_probe_records_how_it_was_probed():
    for probe in TOOLCHAINS:
        assert probe.command.strip(), f"{probe.name}: no probe command recorded"
        assert probe.detail.strip(), f"{probe.name}: no finding recorded"
        if probe.present:
            assert probe.version.strip(), f"{probe.name}: present but no version recorded"


def test_most_of_the_table_is_unverified_and_says_so():
    """A guard against the table drifting towards optimism.

    No toolchain checked the majority of these cells and the table must keep reflecting
    that. If this ever fails because real verification was added, the assertion should be
    revised deliberately — not deleted.
    """
    assert len(unverified()) > len(SUPPORT) / 2, (
        "more than half the matrix should still be unverified; if that changed, "
        "confirm it changed because toolchains were run, not because claims were relaxed"
    )


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------


def test_every_layer_backend_pair_has_an_entry():
    for layer in Layer:
        for backend in Backend:
            assert (layer, backend) in SUPPORT, f"missing cell: {layer}/{backend}"


def test_layer_partition_is_exhaustive():
    assert set(V1_LAYERS) | set(V0_LAYERS) == set(Layer)
    assert not set(V1_LAYERS) & set(V0_LAYERS)
    for layer in V0_LAYERS:
        assert layer.value.startswith("v0_")


def test_the_five_v1_layers_the_brief_names_are_all_present():
    for layer in (
        Layer.CONCEPT_REGISTRY,
        Layer.MORPHOLOGY,
        Layer.TRANSFORMATION,
        Layer.EPISTEMIC_STATUS,
        Layer.DISCOURSE_STATE,
    ):
        assert layer in V1_LAYERS


def test_entry_raises_rather_than_defaulting_on_an_unknown_cell():
    """A missing cell is an unanswered question; a default would answer it."""
    with pytest.raises(KeyError):
        entry("not_a_layer", Backend.LEAN)  # type: ignore[arg-type]


def test_supported_returns_status_and_losses():
    status, losses = supported(Layer.V0_REFINEMENT_SCALAR, Backend.STAN)
    assert status is Status.PARTIAL
    assert any("PositiveReal" in loss for loss in losses)


# ---------------------------------------------------------------------------
# Epistemic statuses — the hardest rows
# ---------------------------------------------------------------------------


def test_every_epistemic_status_has_a_lean_row():
    """The set of statuses is closed, so the table must be exhaustive over it."""
    assert set(LEAN_EPISTEMIC) == set(EpistemicStatus), (
        f"missing: {set(EpistemicStatus) - set(LEAN_EPISTEMIC)}"
    )


def test_no_encoding_is_invented_for_an_inexpressible_status():
    """The brief's hard rule: do NOT invent encodings."""
    for status, enc in LEAN_EPISTEMIC.items():
        if not enc.expressible:
            assert enc.encoding == "", f"{status}: an encoding was invented"
            assert enc.obstacle is not Obstacle.NONE, f"{status}: no obstacle recorded"
            assert enc.note.strip(), f"{status}: no reasoning recorded"


def test_the_statistical_statuses_have_no_lean_encoding():
    """fail_to_reject, consistent_with, estimated and reject are category mismatches.

    No library fixes these, and recording them as library-gated would falsely imply a fix
    exists. For fail_to_reject in particular the absence is a requirement, not a gap.
    """
    for status in (
        EpistemicStatus.FAIL_TO_REJECT,
        EpistemicStatus.REJECT,
        EpistemicStatus.ESTIMATED,
        EpistemicStatus.CONSISTENT_WITH,
    ):
        enc = LEAN_EPISTEMIC[status]
        assert not enc.expressible, f"{status} must not claim a Lean encoding"
        assert enc.obstacle is Obstacle.CATEGORY_MISMATCH, (
            f"{status} is not merely library-gated; recording it that way implies "
            "installing Mathlib would fix it, and it would not"
        )
        assert not enc.kernel_checked


def test_fail_to_reject_records_why_a_theorem_would_be_the_wrong_encoding():
    """The sharpest row: emitting a theorem here would perform the forbidden coercion."""
    note = LEAN_EPISTEMIC[EpistemicStatus.FAIL_TO_REJECT].note
    assert "Evidence" in note and "Proof" in note, (
        "the note must name the Evidence-to-Proof coercion it would commit"
    )
    assert "theorem" in note


def test_measure_theoretic_statuses_are_library_gated_not_category_mismatches():
    """These become expressible with Mathlib. The distinction must not be collapsed."""
    for status in (
        EpistemicStatus.ALMOST_SURE,
        EpistemicStatus.CONVERGES_IN_PROBABILITY,
        EpistemicStatus.WITH_HIGH_PROBABILITY,
    ):
        enc = LEAN_EPISTEMIC[status]
        assert not enc.expressible, "not expressible HERE: Mathlib is absent"
        assert enc.obstacle is Obstacle.LIBRARY_GATED
        assert not enc.kernel_checked, (
            f"{status} was never compiled and must not be marked as though it were"
        )


def test_with_high_probability_records_that_the_regime_must_be_typed():
    note = LEAN_EPISTEMIC[EpistemicStatus.WITH_HIGH_PROBABILITY].note
    assert "regime" in note


def test_only_kernel_checked_statuses_claim_kernel_acceptance():
    """Exactly the five that were compiled during Phase 8, and no others."""
    checked = {s for s, e in LEAN_EPISTEMIC.items() if e.kernel_checked}
    assert checked == {
        EpistemicStatus.PROVED,
        EpistemicStatus.DEFINITIONALLY_TRUE,
        EpistemicStatus.DISPROVED,
        EpistemicStatus.CONJECTURED,
        EpistemicStatus.MODEL_CONDITIONAL,
    }
    for status in checked:
        assert LEAN_EPISTEMIC[status].expressible


def test_a_kernel_checked_inexpressible_status_is_rejected():
    from hamiltonian_lang.v1.backend_support import LeanEncoding

    with pytest.raises(ValueError):
        LeanEncoding(
            status=EpistemicStatus.FAIL_TO_REJECT,
            expressible=False,
            encoding="",
            obstacle=Obstacle.CATEGORY_MISMATCH,
            note="x",
            kernel_checked=True,
        )


def test_an_encoding_on_an_inexpressible_status_is_rejected():
    from hamiltonian_lang.v1.backend_support import LeanEncoding

    with pytest.raises(ValueError, match="invent"):
        LeanEncoding(
            status=EpistemicStatus.FAIL_TO_REJECT,
            expressible=False,
            encoding="theorem h0_true : H0 := by sorry",
            obstacle=Obstacle.CATEGORY_MISMATCH,
            note="x",
        )


def test_epistemic_status_is_unsupported_for_stan_and_sympy():
    """Neither target has any justification object, so every status collapses together."""
    for backend in (Backend.STAN, Backend.SYMPY):
        s = entry(Layer.EPISTEMIC_STATUS, backend)
        assert s.status is Status.UNSUPPORTED
        assert s.reason.strip()


# ---------------------------------------------------------------------------
# The registry block
# ---------------------------------------------------------------------------


def test_registry_block_matches_the_schema():
    """The generated block must validate against concept_registry.schema.json."""
    import jsonschema

    schema = json.loads((REPO / "spec" / "concept_registry.schema.json").read_text())
    sub = schema["$defs"]["concept"]["properties"]["backend_support"]
    sub = {**sub, "$defs": schema["$defs"]}

    for layer in Layer:
        block = registry_backend_support(layer)
        jsonschema.validate(block, sub)


def test_registry_block_covers_every_backend_explicitly():
    """Absence means unsupported, but an explicit entry with a reason says more."""
    block = registry_backend_support(Layer.EPISTEMIC_STATUS)
    assert set(block) == {b.value for b in Backend}


def test_registry_block_carries_the_reason_into_losses_for_unsupported_cells():
    """Nothing may be dropped on the way into the registry."""
    block = registry_backend_support(Layer.EPISTEMIC_STATUS)
    assert block["stan"]["supported"] is False
    assert block["stan"]["losses"], "an unsupported cell must still explain itself"
    assert any("unsupported:" in loss for loss in block["stan"]["losses"])


def test_registry_block_never_reports_verification_stan_did_not_get():
    for layer in Layer:
        block = registry_backend_support(layer)
        assert block["stan"]["verified_by_toolchain"] is False


def test_registry_block_verified_flag_tracks_the_evidence():
    for layer in Layer:
        block = registry_backend_support(layer)
        for backend in Backend:
            assert (
                block[backend.value]["verified_by_toolchain"]
                is entry(layer, backend).verified_by_toolchain
            )


# ---------------------------------------------------------------------------
# The prose document must not drift away from the table
# ---------------------------------------------------------------------------


MATRIX_DOC = REPO / "docs" / "design" / "V1_BACKEND_SUPPORT_MATRIX.md"


def test_the_matrix_document_exists():
    assert MATRIX_DOC.is_file(), "Deliverable 1 is missing"


def test_document_headline_counts_match_the_table():
    """Numbers written in prose drift. This pins them to the data."""
    text = MATRIX_DOC.read_text(encoding="utf-8")
    counts = {status: 0 for status in Status}
    for s in SUPPORT.values():
        counts[s.status] += 1
    n_verified = sum(1 for s in SUPPORT.values() if s.verified_by_toolchain)

    expected = (
        f"{counts[Status.SUPPORTED]} supported, {counts[Status.PARTIAL]} partial, "
        f"{counts[Status.UNSUPPORTED]} unsupported"
    )
    assert expected in text, f"the document must state: {expected}"
    assert f"{n_verified} toolchain-verified" in text
    assert f"{len(SUPPORT)} cells" in text
    assert f"{len(unverified())} of {len(SUPPORT)} cells are unverified" in text


def test_document_records_that_mathlib_and_stanc_are_absent():
    text = MATRIX_DOC.read_text(encoding="utf-8")
    assert "unknown module prefix 'Mathlib'" in text, (
        "the exact Lean error must be quoted, not paraphrased"
    )
    assert "stanc" in text
    for probe in TOOLCHAINS:
        if probe.present and probe.version:
            assert probe.version.split()[0] in text, (
                f"{probe.name} version {probe.version} is not recorded in the document"
            )


def test_document_refuses_the_round_trip_equivalence_claim():
    """The brief forbids it and the measured findings show why."""
    text = MATRIX_DOC.read_text(encoding="utf-8")
    assert "No general HML↔Stan or HML↔Lean round-trip equivalence" in text


def test_document_states_the_epistemic_split():
    """5 expressible / 5 library-gated / 6 category mismatch."""
    text = MATRIX_DOC.read_text(encoding="utf-8")
    n_expressible = sum(1 for e in LEAN_EPISTEMIC.values() if e.expressible)
    n_gated = sum(
        1 for e in LEAN_EPISTEMIC.values() if e.obstacle is Obstacle.LIBRARY_GATED
    )
    n_mismatch = sum(
        1 for e in LEAN_EPISTEMIC.values() if e.obstacle is Obstacle.CATEGORY_MISMATCH
    )
    assert n_expressible + n_gated + n_mismatch == len(EpistemicStatus)
    assert f"Expressible, and compiled here ({n_expressible})" in text
    assert f"this machine does not ({n_gated})" in text
    assert f"no library fixes these ({n_mismatch})" in text


# ---------------------------------------------------------------------------
# Optional live re-verification
# ---------------------------------------------------------------------------


def _lean_binary() -> str | None:
    for candidate in ("lean", str(Path.home() / ".elan" / "bin" / "lean")):
        if shutil.which(candidate) or Path(candidate).is_file():
            return candidate
    return None


@pytest.mark.skipif(_lean_binary() is None, reason="Lean is not installed")
def test_recorded_lean_acceptance_still_holds(tmp_path: Path):
    """Re-run the epistemic probe, so the recorded acceptance is re-checkable.

    `autoImplicit` is disabled deliberately: with it on, Lean silently binds an unknown
    type name as an implicit variable of arbitrary sort, and a file referring to types
    that do not exist still compiles — a false positive this suite must not accept.
    """
    lean = _lean_binary()
    assert lean is not None
    probe = tmp_path / "Probe.lean"
    probe.write_text(
        "set_option autoImplicit false\n"
        "set_option relaxedAutoImplicit false\n"
        "namespace P\n"
        "theorem status_proved : ∀ a b : Nat, a + b = b + a := Nat.add_comm\n"
        "def two : Nat := 2\n"
        "theorem status_definitionally_true : two = 2 := rfl\n"
        "theorem status_disproved : ¬ ((1 : Nat) = 2) := by omega\n"
        "def status_conjectured : Prop := ∀ n : Nat, n > 1 → ∃ p q : Nat, p + q = n\n"
        "theorem status_model_conditional (h : ∀ n : Nat, n = 0) : (3 : Nat) = 0 := h 3\n"
        "end P\n"
        "#print axioms P.status_proved\n",
        encoding="utf-8",
    )
    cp = subprocess.run(
        [lean, str(probe)], capture_output=True, text=True, timeout=300
    )
    assert cp.returncode == 0, f"Lean rejected the recorded encodings:\n{cp.stderr}"
    combined = cp.stdout + cp.stderr
    assert "sorry" not in combined, (
        f"the probe must contain no `sorry`; exit 0 alone proves nothing:\n{combined}"
    )
    assert "does not depend on any axioms" in combined, (
        f"expected a real proof term for `proved`:\n{combined}"
    )


@pytest.mark.skipif(_lean_binary() is None, reason="Lean is not installed")
def test_lean_exit_code_zero_really_does_certify_a_false_theorem(tmp_path: Path):
    """The control behind `sorry_free`. If this ever stops holding, relax the rule.

    A demonstrably false theorem closed with `sorry` exits 0. That is why
    `ToolchainEvidence.accepted` requires more than the exit code for Lean.
    """
    lean = _lean_binary()
    assert lean is not None
    bad = tmp_path / "Bad.lean"
    bad.write_text(
        "set_option autoImplicit false\n"
        "theorem definitely_false : (1 : Nat) = 2 := by sorry\n",
        encoding="utf-8",
    )
    cp = subprocess.run([lean, str(bad)], capture_output=True, text=True, timeout=300)
    assert cp.returncode == 0, (
        "if Lean now fails a sorry-closed file, the sorry_free rule can be simplified"
    )
    assert "sorry" in (cp.stdout + cp.stderr)


@pytest.mark.skipif(_lean_binary() is None, reason="Lean is not installed")
def test_mathlib_really_is_absent(tmp_path: Path):
    """The table's most consequential claim, re-checked rather than trusted."""
    lean = _lean_binary()
    assert lean is not None
    probe = tmp_path / "M.lean"
    probe.write_text("import Mathlib\n", encoding="utf-8")
    cp = subprocess.run([lean, str(probe)], capture_output=True, text=True, timeout=300)
    if cp.returncode == 0:
        pytest.skip(
            "Mathlib is now installed; the Lean rows in the matrix should be re-measured"
        )
    assert not toolchain("mathlib").present
