"""The theorem-library contract, and the trust boundary around it.

The question these tests exist to answer is not "does add_zero work". It is: **can a
library get something into the reasoning graph that it has not earned?** A library is
shipped Python; if living in a shipped Python file were enough to make an assertion
VERIFIED, the trusted computing base would be "everything anyone ever added to
`libraries/`", which is no boundary at all.

So: a library supplies *theorems*, which are data. It cannot supply a checker, cannot reach
a registration API from source, and cannot satisfy its own side conditions.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang import libraries as lib
from hamiltonian_lang.ast.nodes import EvidenceStatus
from hamiltonian_lang.reasoning import certificates as C
from hamiltonian_lang.reasoning import kernel


def _compile(src: str):
    return compile_source(src, "<lib>")


def _status(src: str, label: str = "e1") -> str:
    r = _compile(src)
    if r.reasoning is None:
        return "<not reached>"
    return r.reasoning.evidence_status.get(label, "<absent>")


ADD_ZERO = (
    "module A\nvar n : Natural\n"
    "evidence e1 : entails n + 0.0 = n by library_theorem_v1({args})\n"
)


# --- theorem is not an inference rule ---------------------------------------


def test_no_library_theorem_became_a_kernel_rule():
    """The whole architectural point. Domain facts must not grow the trusted kernel."""
    for theorem_id in lib.theorem_ids():
        assert theorem_id not in kernel.RULES, (
            f"{theorem_id} is in kernel.RULES; a domain theorem is not an inference rule"
        )
    for banned in ("add_zero", "conditional_product", "quotient", "derivative"):
        assert not any(banned in r for r in kernel.RULES), (
            f"a rule mentioning {banned!r} entered the kernel"
        )


def test_the_kernel_rule_set_is_unchanged_by_this_layer():
    """Pinned explicitly: the library layer added no inference rule at all."""
    assert set(kernel.rule_names()) == {
        "add_both_sides", "add_inequality", "and_elim_left", "and_elim_right",
        "and_intro", "congruence", "divide_both_sides", "forall_elim", "forall_intro",
        "modus_ponens", "modus_tollens", "multiply_both_sides", "multiply_inequality",
        "subtract_both_sides", "substitute", "symmetry", "transitivity",
        "weaken_inequality",
    }


# --- the registry is static -------------------------------------------------


def test_source_cannot_define_a_theorem():
    assert not hasattr(lib, "register")
    assert "register" not in lib.__all__


def test_a_library_cannot_register_a_trusted_checker():
    """A library that could supply `lambda *_: VALID` would end the TCB."""
    assert not hasattr(C, "register")
    assert "register" not in C.__all__


def test_an_unregistered_theorem_id_is_rejected():
    r = _compile(ADD_ZERO.format(args="theorem := no_such_theorem, x := n"))
    assert not r.ok()
    assert any("not a registered theorem" in str(d) for d in r.diagnostics)


def test_a_theorem_name_is_not_resolved_as_a_value():
    """`theorem := add_zero` names a registry entry, not a variable.

    Without the dedicated resolution path this reports "'add_zero' is not bound", which is
    right for a value position and wrong here -- a theorem has no binding occurrence.
    """
    assert _status(ADD_ZERO.format(args="theorem := add_zero, x := n")) == (
        EvidenceStatus.VALID
    )


def test_omitting_the_theorem_role_is_rejected():
    r = _compile(ADD_ZERO.format(args="x := n"))
    assert not r.ok()
    assert _status(ADD_ZERO.format(args="x := n")) == EvidenceStatus.REJECTED


# --- instantiation discipline ----------------------------------------------


def test_a_missing_variable_is_rejected():
    r = _compile(ADD_ZERO.format(args="theorem := add_zero"))
    assert not r.ok()
    assert any("needs x" in str(d) for d in r.diagnostics)


def test_a_spurious_variable_is_rejected():
    r = _compile(ADD_ZERO.format(args="theorem := add_zero, x := n, y := n"))
    assert not r.ok()
    assert any("has no variable" in str(d) for d in r.diagnostics)


def test_a_wrongly_typed_substitution_is_rejected():
    src = (
        "module A\nvar b : Bool\n"
        "evidence e1 : entails b + 0.0 = b by library_theorem_v1(theorem := add_zero, x := b)\n"
    )
    assert _status(src) != EvidenceStatus.VALID


def test_a_conclusion_the_theorem_does_not_license_is_rejected():
    """The substitution is fine; the claimed proposition is not what follows from it."""
    src = (
        "module A\nvar n : Natural\n"
        "evidence e1 : entails n + 1.0 = n by library_theorem_v1(theorem := add_zero, x := n)\n"
    )
    r = _compile(src)
    assert not r.ok()
    assert any("licenses" in str(d) for d in r.diagnostics)
    assert _status(src) == EvidenceStatus.REJECTED


def test_instantiate_refuses_an_untyped_substitution():
    from hamiltonian_lang.ast.nodes import Ref

    with pytest.raises(lib.InstantiationError):
        lib.instantiate(lib.THEOREMS["add_zero"], {"x": Ref(name="q")})


# --- honesty about what is assumed ------------------------------------------


def test_every_assumed_theorem_carries_a_justification():
    """An unjustified assumption is an unaudited one, so the registry refuses empty ones."""
    assert lib.axioms(), "nothing is labelled assumed; the audit surface would be empty"
    for t in lib.axioms():
        assert t.justification.strip(), f"{t.id} is assumed without a justification"
        assert t.statement.strip()
        assert t.provenance.strip()


def test_the_assumed_set_can_be_enumerated():
    """A trusted computing base you can only describe is one nobody checks."""
    ids = {t.id for t in lib.axioms()}
    assert "add_zero" in ids
    assert "conditional_product" in ids
    text = lib.describe()
    assert "add_zero" in text and "LIBRARY_AXIOM" in text


def test_a_replayed_theorem_is_not_labelled_assumed():
    """Calculus earns its result; it must not be lumped in with the axioms."""
    for t in lib.axioms():
        assert t.library != "calculus"


def test_every_theorem_has_a_stable_versioned_key():
    for theorem_id in lib.theorem_ids():
        t = lib.THEOREMS[theorem_id]
        assert t.key == f"{t.id}_v{t.version}"
        assert t.version >= 1


# --- side conditions cannot be self-satisfied -------------------------------


def test_a_library_cannot_discharge_its_own_side_condition():
    """The side condition goes to Γ. Nothing in `libraries/` can put a fact there."""
    from hamiltonian_lang.libraries.probability import CONDITIONAL_PRODUCT

    assert CONDITIONAL_PRODUCT.side_conditions
    for sc in CONDITIONAL_PRODUCT.side_conditions:
        assert sc.mandatory, "a definedness condition that does not block is decoration"
