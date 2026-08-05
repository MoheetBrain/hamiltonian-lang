"""The fairness constraint: no candidate receives additional mathematical information.

Three independent statements of it, each with a negative control that proves the check
has teeth. A fairness test with no negative control is indistinguishable from a fairness
test that always passes, and this phase's whole value rests on the constraint holding.

P1  **Content parity.** All four renderings, parsed back *before* resolution, normalise
    to a byte-identical ``declared_content``. Catches a surface that writes down a fact
    the others omit, or omits one the others write.
P2  **No pre-resolution.** No candidate's parse output carries a ``SymbolId`` or an
    inferred type. Catches a surface that resolves a name or infers a type for the
    reader -- the ``refTo`` edge in the ``e_graph_triple`` sketch is exactly this.
P3  **Recovery parity.** All four recover the same canonical content hash. Catches a
    surface that drops information.
"""

from __future__ import annotations

import json

import pytest
from evaluation.syntax_acquisition.candidate_d import CandidateD
from evaluation.syntax_acquisition.core import (
    CANDIDATES,
    declared_content,
    derived_facts_present,
    round_trip,
)
from evaluation.syntax_acquisition.generator import (
    CORPUS_CHUNKS as CHUNKS,
)
from evaluation.syntax_acquisition.generator import (
    corpus,
)
from evaluation.syntax_acquisition.generator import (
    corpus_chunk as chunk,
)

from hamiltonian_lang.ast.nodes import DefineStmt, Module, Ref, SymbolId
from hamiltonian_lang.backends.canonical import content_hash
from hamiltonian_lang.types import ScalarType

CANDIDATE_IDS = tuple(sorted(CANDIDATES))

# -- P1: content parity --------------------------------------------------


@pytest.mark.parametrize("index", range(CHUNKS))
def test_all_four_renderings_carry_identical_declared_content(index):
    for obj in chunk(index):
        contents = {
            cid: declared_content(cand.parse(cand.render(obj.module)))
            for cid, cand in sorted(CANDIDATES.items())
        }
        distinct = set(contents.values())
        if len(distinct) != 1:
            reference = contents["A"]
            offenders = [cid for cid, text in contents.items() if text != reference]
            pytest.fail(
                f"{obj.id}: surfaces {offenders} disagree with A on declared content\n"
                + "\n".join(
                    f"--- {cid} ---\n{json.dumps(json.loads(text), indent=1)[:2000]}"
                    for cid, text in sorted(contents.items())
                    if cid in ("A", *offenders)
                )
            )


# -- P2: no pre-resolution -----------------------------------------------


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
@pytest.mark.parametrize("index", range(CHUNKS))
def test_no_candidate_pre_resolves_names_or_types(candidate_id, index):
    cand = CANDIDATES[candidate_id]
    for obj in chunk(index):
        leaked = derived_facts_present(cand.parse(cand.render(obj.module)))
        assert leaked == {"symbol_ids": 0, "inferred_types": 0}, (
            f"[{candidate_id}] {obj.id} handed the reader checker-derived facts: {leaked}"
        )


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
@pytest.mark.parametrize("index", range(CHUNKS))
def test_no_rendering_contains_a_canonical_symbol_id(candidate_id, index):
    """``sym:#depth.ordinal`` is the resolver's output. No surface may quote it."""
    cand = CANDIDATES[candidate_id]
    for obj in chunk(index):
        text = cand.render(obj.module)
        assert "sym:#" not in text and "sym:" not in text, (
            f"[{candidate_id}] {obj.id} leaks a canonical symbol id"
        )


# -- P3: recovery parity -------------------------------------------------


@pytest.mark.parametrize("index", range(CHUNKS))
def test_all_four_recover_the_same_canonical_hash(index):
    for obj in chunk(index):
        original = content_hash(obj.module)
        recovered = {}
        for cid, cand in sorted(CANDIDATES.items()):
            outcome = round_trip(cand, obj.module, obj.id)
            assert outcome.ok, f"[{cid}] {obj.id}: {outcome.stage} {outcome.detail}"
            recovered[cid] = outcome.recovered_hash
        assert set(recovered.values()) == {original}, f"{obj.id}: {recovered}"


# ---------------------------------------------------------------------------
# Negative controls -- each must FAIL the corresponding check
# ---------------------------------------------------------------------------


class _PreResolvingD(CandidateD):
    """A candidate that hands the reader the result of name resolution.

    Models the ``e_graph_triple`` sketch's ``_:q1cl refTo _:q1y`` edge: a use pointing
    straight at its binder. Its output would round-trip perfectly and hash correctly --
    which is exactly why P3 alone is not enough.
    """

    id = "D-leaky-resolution"

    def parse(self, text: str) -> Module:
        module = super().parse(text)
        for st in module.statements:
            if isinstance(st, DefineStmt):
                st.symbol_id = SymbolId(st.name, 0, 0)
        return module


class _OverAnnotatingD(CandidateD):
    """A candidate that writes an inferred type as if the author had declared it."""

    id = "D-leaky-annotation"

    def parse(self, text: str) -> Module:
        module = super().parse(text)
        for st in module.statements:
            if isinstance(st, DefineStmt) and st.declared_type is None:
                st.declared_type = ScalarType("Real")
        return module


class _DroppingD(CandidateD):
    """A candidate that silently omits the conditioning set of a law."""

    id = "D-lossy"

    def render(self, module: Module) -> str:
        text = super().render(module)
        doc = json.loads(text)
        for st in doc["statements"]:
            if st.get("node") == "law":
                st["given"] = []
        return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def _first(predicate):
    for obj in corpus():
        if predicate(obj):
            return obj
    raise AssertionError("the corpus does not contain a suitable object")


def test_pre_resolution_leak_is_detected():
    obj = _first(lambda o: any(isinstance(s, DefineStmt) for s in o.module.statements))
    leaky = _PreResolvingD()
    leaked = derived_facts_present(leaky.parse(leaky.render(obj.module)))
    assert leaked["symbol_ids"] > 0, "P2 did not notice a pre-resolved binder"
    outcome = round_trip(leaky, obj.module, obj.id)
    assert not outcome.ok and outcome.stage == "parity", (
        "the round-trip gate accepted a candidate that pre-resolves names"
    )


def test_extra_annotation_leak_is_detected():
    obj = _first(
        lambda o: any(
            isinstance(s, DefineStmt) and s.declared_type is None for s in o.module.statements
        )
    )
    leaky = _OverAnnotatingD()
    honest = declared_content(CANDIDATES["A"].parse(CANDIDATES["A"].render(obj.module)))
    leaked = declared_content(leaky.parse(leaky.render(obj.module)))
    assert honest != leaked, (
        "P1 did not notice a surface that supplies a type the others leave to inference"
    )


def test_information_loss_is_detected():
    obj = _first(
        lambda o: any(getattr(s, "given", None) for s in o.module.statements)
    )
    lossy = _DroppingD()
    outcome = round_trip(lossy, obj.module, obj.id)
    assert not outcome.ok, "the round-trip gate accepted a candidate that dropped a conditioning set"
    assert outcome.stage in ("hash", "check", "resolve"), outcome.stage


def test_a_reference_is_never_rendered_as_a_binder_pointer():
    """The specific leak the phase brief names, stated as a property of every surface.

    Every ``Ref`` must be written by *name*, so that resolving it costs the reader the
    same scope walk in all four surfaces.
    """
    obj = _first(lambda o: any(isinstance(n, Ref) for n in _walk(o.module)))
    for cid, cand in sorted(CANDIDATES.items()):
        parsed = cand.parse(cand.render(obj.module))
        refs = [n for n in _walk(parsed) if isinstance(n, Ref)]
        assert refs, f"[{cid}] lost every reference"
        for ref in refs:
            assert ref.symbol_id is None, f"[{cid}] pre-bound the reference {ref.name!r}"
            assert ref.name, f"[{cid}] emitted a reference with no name"


def _walk(node):
    from hamiltonian_lang.ast.nodes import walk

    return walk(node)
