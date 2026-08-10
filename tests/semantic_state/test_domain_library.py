"""The domain lattice (SF-R14) and the two divergences from the reference checker it closed.

These are not fixture tests. All thirty acceptance fixtures passed before this library
existed and pass unchanged after it, because every fixture declares the domain the claim
already has — so no fixture distinguishes ``==`` from a containment walk, and none
distinguishes a premise subset from an exact premise list. Both divergences were latent:
real, and invisible to the acceptance set.

The strongest check here is differential rather than exemplary.
:func:`test_the_lattice_agrees_with_the_frozen_reference_checker_on_every_pair` imports the
corpus's frozen ``reference_checker`` and compares :func:`inhabits` against its
``_is_subtype`` across the entire cross product of domain names. Hand-picked examples would
only show the cases I thought of, which is how the original divergence survived.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from hamiltonian_lang.semantic_state import verify_payload
from hamiltonian_lang.semantic_state.domains import DOMAINS, DomainEntry, inhabits

CORPUS = Path("/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus")
REFERENCE = CORPUS / "experiments" / "semantic_firewall" / "reference_checker.py"

SCHEMA = "semantic-firewall-case-0.1.0"


def _reference():
    if not REFERENCE.exists():
        pytest.skip(f"research corpus not present at {CORPUS}")
    if "_frozen_reference" in sys.modules:
        return sys.modules["_frozen_reference"]
    spec = importlib.util.spec_from_file_location("_frozen_reference", REFERENCE)
    module = importlib.util.module_from_spec(spec)
    # Registered before execution: the reference defines dataclasses, and
    # ``dataclasses`` resolves a field annotation through ``sys.modules[cls.__module__]``.
    # Loading it unregistered fails inside the stdlib rather than in anything it declares.
    sys.modules["_frozen_reference"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# The library itself
# ---------------------------------------------------------------------------


def test_every_entry_is_versioned_justified_and_rooted():
    assert DOMAINS, "the lattice is empty"
    for name, entry in DOMAINS.items():
        assert entry.name == name
        assert entry.key == f"{name}_v{entry.version}"
        assert entry.justification.strip(), f"{name} carries no justification"
        assert entry.provenance.strip(), f"{name} carries no provenance"
        assert entry.parent is None or entry.parent in DOMAINS


def test_the_lattice_terminates():
    """Every chain reaches a root. ``inhabits`` walks parents, so a cycle would hang it."""
    for name in DOMAINS:
        seen: set[str] = set()
        current: str | None = name
        while current is not None:
            assert current not in seen, f"cycle through {current!r}"
            seen.add(current)
            current = DOMAINS[current].parent


def test_a_document_cannot_widen_the_lattice_it_is_checked_against():
    """The registrar is package-private, like the mathematical library's.

    A checked document that can register ``Boolean <= Integer`` has defeated the check.
    """
    import hamiltonian_lang.semantic_state.domains as mod

    assert "_register" not in getattr(mod, "__all__", [])
    assert not hasattr(__import__("hamiltonian_lang.semantic_state", fromlist=["x"]),
                       "_register")


def test_containment_is_reflexive_and_directional():
    assert inhabits("Integer", "Integer")
    assert inhabits("Natural", "Integer")
    assert inhabits("Natural", "Number")
    assert not inhabits("Integer", "Natural")
    assert inhabits("PositiveReal", "NonNegativeReal")
    assert not inhabits("NonNegativeReal", "PositiveReal"), "zero is the counterexample"


def test_an_unregistered_name_is_comparable_only_to_itself():
    """``Proposition`` and ``Boolean`` occur in the corpus in no containment relation.

    Inventing one would let a Boolean satisfy an Integer contract, which is precisely the
    corruption ``FX-TYP-ILLEGAL`` encodes.
    """
    assert inhabits("Proposition", "Proposition")
    assert not inhabits("Boolean", "Integer")
    assert not inhabits("Integer", "Boolean")
    assert not inhabits("Proposition", "Number")


def test_the_lattice_agrees_with_the_frozen_reference_checker_on_every_pair():
    ref = _reference()
    names = sorted(set(DOMAINS) | set(ref._DOMAIN_PARENTS) | {"Proposition", "Boolean"})
    disagreements = [
        (a, b)
        for a in names
        for b in names
        if inhabits(a, b) != ref.ReferenceChecker._is_subtype(a, b)
    ]
    assert not disagreements, f"lattice disagrees with the reference on: {disagreements}"


def test_the_lattice_is_not_the_hml_scalar_lattice():
    """Two lattices, two purposes. ``CLAUDE.md`` forbids a subtyping path between them.

    ``types.py`` orders HML's own scalar types and contains ``Probability`` under a
    different parent; conflating them would silently import HML's type decisions into the
    corpus's vocabulary.
    """
    from hamiltonian_lang import types

    scalar = getattr(types, "_SCALAR_PARENTS", None)
    if scalar is None:  # pragma: no cover - the attribute was renamed
        pytest.skip("types._SCALAR_PARENTS not present")
    assert DOMAINS is not scalar
    assert "Number" in DOMAINS and "Number" not in scalar


# ---------------------------------------------------------------------------
# Divergence 1 — input domains were compared with equality
# ---------------------------------------------------------------------------


def _typed(claim_domain: str, required: str, output_domain: str | None = None) -> dict:
    typing: dict = {"input_domains": {"p0": required}}
    if output_domain is not None:
        typing["output_domain"] = output_domain
    return {
        "schema_version": SCHEMA,
        "case_id": "SYNTHETIC",
        "action": {
            "id": "a1",
            "operation": "ASSERT",
            "summary": "",
            "dependencies": ["p0"],
            "preconditions": [],
            "obligations_created": [],
            "obligations_discharged": [],
            "typing": typing,
            "warrant": {},
            "goal_effect": {},
            "scope_effect": {},
            "branch_effect": {},
            "candidate_effect": {},
            "epistemic_effect": {},
        },
        "state_before": {
            "active_scopes": ["global"],
            "branches": {}, "candidates": {}, "goals": {}, "obligations": {},
            "claims": {
                "p0": {"id": "p0", "proposition": "n > 0", "status": "GIVEN",
                       "scope": "global", "domain": claim_domain, "dependencies": []}
            },
        },
        # The premise is carried forward unchanged. The frame condition (D-049) requires
        # ``state_after`` to be what the action produced and no more, so a payload that
        # silently drops a claim it never touched is a malformed transition, not a
        # neutral one.
        "state_after": {
            "active_scopes": ["global"],
            "branches": {}, "candidates": {}, "goals": {}, "obligations": {},
            "claims": {
                "p0": {"id": "p0", "proposition": "n > 0", "status": "GIVEN",
                       "scope": "global", "domain": claim_domain, "dependencies": []}
            },
        },
        "evidence": {},
        "source": {},
    }


def test_a_natural_number_may_be_offered_where_an_integer_is_required():
    """The bug this library closed: a false INVALID on sound reasoning.

    The reference checker accepts this. Comparing declared domains with ``!=`` rejected it,
    and no fixture would ever have shown that.
    """
    assert str(verify_payload(_typed("Natural", "Integer")).verdict) == "VALID"
    assert str(verify_payload(_typed("Natural", "Number")).verdict) == "VALID"


def test_containment_still_runs_in_one_direction_only():
    result = verify_payload(_typed("Real", "Integer"))
    assert str(result.verdict) == "INVALID"
    assert result.error_class == "TYPE_OR_DOMAIN_MISMATCH"


def test_an_unrelated_domain_is_still_rejected():
    """``FX-TYP-ILLEGAL`` in miniature: a Boolean where an Integer is required."""
    assert verify_payload(_typed("Boolean", "Integer")).error_class == (
        "TYPE_OR_DOMAIN_MISMATCH"
    )


def test_an_unknown_domain_is_unresolved_rather_than_invalid():
    assert str(verify_payload(_typed("UNKNOWN", "Integer")).verdict) == "UNRESOLVED"


def test_the_output_domain_check_is_a_deliberate_divergence():
    """Recorded, not hidden.

    The reference checker never reads ``output_domain``. This verifier does, because
    deleting a sound check to agree with a gap in the reference would be the wrong repair.
    It is a *stricter* divergence, so it cannot cause a corrupted transition to be
    accepted — only a well-formed one to be questioned — and it is asserted here so the
    behaviour is a decision on record rather than an accident.
    """
    ref = _reference()
    import inspect

    assert "output_domain" not in inspect.getsource(ref.ReferenceChecker._type_domain)

    case = _typed("Integer", "Integer", output_domain="Integer")
    case["action"]["output_id"] = "c1"
    case["state_after"]["claims"]["c1"] = {
        "id": "c1", "proposition": "n > 0", "status": "DERIVED",
        "scope": "global", "domain": "Boolean", "dependencies": ["p0"],
    }
    assert verify_payload(case).error_class == "TYPE_OR_DOMAIN_MISMATCH"


# ---------------------------------------------------------------------------
# Divergence 2 — the warrant premise envelope was a subset test
# ---------------------------------------------------------------------------


def _warranted(premise_ids: list[str], dependencies: list[str]) -> dict:
    case = _typed("Integer", "Integer")
    case["action"]["dependencies"] = dependencies
    case["action"]["typing"] = {}
    case["action"]["warrant"] = {"kind": "EVIDENCE_ADAPTER", "rule": "R", "evidence_id": "e1"}
    case["evidence"] = {
        "e1": {"id": "e1", "kind": "SOURCE_REVIEW", "status": "VALID",
               "supports_rule": "R", "trusted": True, "premise_ids": premise_ids}
    }
    for dep in dependencies:
        case["state_before"]["claims"].setdefault(
            dep, {"id": dep, "proposition": "q", "status": "GIVEN",
                  "scope": "global", "dependencies": []}
        )
    # Every premise survives the transition unchanged, per the frame condition (D-049).
    case["state_after"]["claims"] = dict(case["state_before"]["claims"])
    return case


def test_a_warrant_envelope_must_name_exactly_the_declared_premises():
    assert str(verify_payload(_warranted(["p0"], ["p0"])).verdict) == "VALID"


def test_evidence_resting_on_fewer_premises_than_the_action_declares_is_rejected():
    """The dangerous half of the old subset reading.

    Evidence checked against ``p0`` alone was accepted as warrant for an action declaring
    ``p0`` and ``p1``, so the conclusion acquired an ancestor the warrant never covered.
    SF-R09 binds the *exact* premise list, and the reference checker compares the lists
    outright.
    """
    result = verify_payload(_warranted(["p0"], ["p0", "p1"]))
    assert result.error_class == "WARRANT_MISMATCH", result.to_dict()


def test_evidence_resting_on_premises_the_action_never_declared_is_rejected():
    assert verify_payload(_warranted(["p0", "p9"], ["p0"])).error_class == "WARRANT_MISMATCH"


def test_the_premise_envelope_is_a_record_not_a_set():
    """Order matters because the reference treats it as mattering.

    Asserted rather than assumed: if the corpus ever normalises premise order, this is the
    test that says so instead of thirty fixtures quietly changing verdict.
    """
    result = verify_payload(_warranted(["p1", "p0"], ["p0", "p1"]))
    assert result.error_class == "WARRANT_MISMATCH"


def test_the_reference_checker_compares_the_premise_lists_outright():
    """Pins the claim above to the frozen source rather than to my reading of it."""
    ref = _reference()
    import inspect

    source = inspect.getsource(ref.ReferenceChecker._warrant)
    assert 'record.get("premise_ids", []) != dependencies' in source


def test_the_domain_entry_is_immutable():
    entry = next(iter(DOMAINS.values()))
    assert isinstance(entry, DomainEntry)
    with pytest.raises(AttributeError):
        entry.parent = "Anything"  # type: ignore[misc]
