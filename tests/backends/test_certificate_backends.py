"""Backend behaviour for the two new statement forms.

Two obligations, and the second is the one CLAUDE.md calls the worst failure mode in the
codebase:

1. **Round trip.** `backends/hml.py` must render `evidence` and `undetermined` so that
   re-parsing gives back the same canonical identity. A construct the HML backend cannot
   emit is a construct that silently disappears from any tool that normalises through it.
2. **Declared loss.** A backend that *cannot* represent them must say so. Dropping an
   `evidence` statement is worse than dropping most things: strip the judgement from a
   `determines_neither` certificate and what is left is a bare proposition, which reads as
   an assertion of exactly the thing the certificate says is unsettled.
"""

from __future__ import annotations

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends.canonical import content_hash
from hamiltonian_lang.backends.hml import render_module

UNDERDETERMINATION = """module R
var P : Bool
var Q : Bool
assume a1 : P implies Q
assume a2 : Q
goal g1 : P
evidence e1 : determines_neither P from a1, a2 by propositional_underdetermination_v1(holds := P and Q, fails := (not P) and Q)
undetermined g1 by e1
"""

ENTAILMENT = """module R
evidence e1 : entails 5.0 - 2.0 = 3.0 by closed_eval_v1()
"""

QUANTIFIERS = """module R
var a : Natural
assume a1 : forall x : Natural . x >= 0.0
goal g1 : forall a : Natural . a >= 0.0
derive d1 : a >= 0.0 from a1 by forall_elim(at := a)
derive d2 : forall a : Natural . a >= 0.0 from d1 by forall_intro(var := a)
proved g1 by d2
"""

SOURCES = [UNDERDETERMINATION, ENTAILMENT, QUANTIFIERS]


@pytest.mark.parametrize("src", SOURCES)
def test_hml_backend_round_trips_the_new_forms(src):
    first = compile_source(src, "<rt>")
    assert first.ok(), [str(d) for d in first.diagnostics]
    again = compile_source(render_module(first.module), "<rt2>")
    assert again.ok(), [str(d) for d in again.diagnostics]
    assert content_hash(first.module) == content_hash(again.module)


@pytest.mark.parametrize("src", SOURCES)
def test_the_round_trip_re_earns_its_verdicts(src):
    """The rendered form carries no status, so the checker must decide it again.

    This is the property that keeps `VERIFIED` and `VALID` unwritable: if the backend
    emitted them, a round trip would launder an unchecked module into a checked-looking
    one.
    """
    first = compile_source(src, "<rt>")
    again = compile_source(render_module(first.module), "<rt2>")
    rendered = render_module(first.module)
    for banned in ("VERIFIED", "VALID", "UNDERDETERMINED", "PROVED", "CHECKED"):
        assert banned not in rendered, f"the backend emitted the status {banned}"
    assert first.reasoning.goal_status == again.reasoning.goal_status
    assert first.reasoning.evidence_status == again.reasoning.evidence_status
    assert first.reasoning.derivation_status == again.reasoning.derivation_status


def test_a_backend_that_cannot_represent_evidence_declares_the_loss():
    """And the message must name the inversion, not just say "dropped"."""
    from hamiltonian_lang.backends.base import Backend

    class Bare(Backend):
        target = "bare"

        def emit(self) -> str:
            self.report_reasoning_loss()
            return ""

    compiled = compile_source(UNDERDETERMINATION, "<loss>")
    result = Bare(compiled.module).run()
    losses = " ".join(u.render() for u in result.unsupported)
    assert "evidence e1" in losses
    assert "undetermined g1" in losses
    assert "OPPOSITE" in losses, (
        "the loss report must say that a stripped determines_neither certificate reads "
        "as an assertion of what it denies"
    )
    assert not result.faithful
