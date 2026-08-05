"""Per-surface properties, and a drift guard on the written specifications.

The worked example in each specification document is asserted byte-identical to real
renderer output. A grammar document whose example was typed by hand is a document that
will be wrong within a month, and nobody will notice until someone trusts it.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from evaluation.syntax_acquisition.candidate_b import B_RESERVED_WORDS
from evaluation.syntax_acquisition.candidate_c import C_HEADS
from evaluation.syntax_acquisition.candidate_d import D_DOCUMENT_VERSION
from evaluation.syntax_acquisition.core import (
    CANDIDATES,
    RESERVED_IN_ANY_SURFACE,
    SurfaceParseError,
    round_trip,
)

from hamiltonian_lang import compile_source
from hamiltonian_lang.backends.canonical import content_hash
from hamiltonian_lang.lexer import KEYWORDS

REPO = pathlib.Path(__file__).resolve().parents[2]
SPEC_DIR = REPO / "docs" / "design" / "syntax"
CANDIDATE_IDS = tuple(sorted(CANDIDATES))

WORKED_EXAMPLE = """module BayesianCoin

param theta : Probability
const trials : Natural = 10
obs successes : Natural = 7

prior theta ~ Beta(alpha := 1, beta := 1)
likelihood successes | theta ~ Binomial(trials := trials, prob := theta)
infer posterior theta
"""


def _worked_module():
    result = compile_source(WORKED_EXAMPLE, "<worked-example>")
    assert result.ok(), "\n" + result.diagnostics.render()
    return result.module


# -- specification documents ---------------------------------------------


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
def test_specification_document_exists(candidate_id):
    assert (SPEC_DIR / f"CANDIDATE_{candidate_id}.md").is_file()


def test_specification_index_exists():
    assert (SPEC_DIR / "README.md").is_file()


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
def test_the_worked_example_in_the_specification_is_real_renderer_output(candidate_id):
    rendered = CANDIDATES[candidate_id].render(_worked_module())
    document = (SPEC_DIR / f"CANDIDATE_{candidate_id}.md").read_text()
    assert rendered.strip() in document, (
        f"CANDIDATE_{candidate_id}.md's worked example has drifted from the renderer.\n"
        f"--- actual output ---\n{rendered}"
    )


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
def test_the_worked_example_round_trips(candidate_id):
    outcome = round_trip(CANDIDATES[candidate_id], _worked_module(), "worked-example")
    assert outcome.ok, f"{outcome.stage}: {outcome.detail}"


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
def test_every_specification_states_what_the_surface_cannot_express(candidate_id):
    document = (SPEC_DIR / f"CANDIDATE_{candidate_id}.md").read_text()
    assert "cannot express" in document


# -- candidate B ---------------------------------------------------------


def test_candidate_b_reserves_fewer_words_than_hml_l1():
    """The claim B is built on, stated as a number rather than an impression."""
    assert len(B_RESERVED_WORDS) == 17
    assert len(KEYWORDS) == 47
    assert len(B_RESERVED_WORDS) < len(KEYWORDS)


def test_candidate_b_reserved_words_are_excluded_from_the_shared_subset():
    """Otherwise a name legal in A would be unrenderable in B and the subset would split."""
    assert B_RESERVED_WORDS <= RESERVED_IN_ANY_SURFACE


def test_words_b_frees_are_genuinely_free_in_b():
    """`param`, `prior`, `min`, `invariant` carry meaning only by position in B."""
    freed = {"param", "prior", "likelihood", "posterior", "invariant", "variance", "solve"}
    assert freed <= KEYWORDS, "these are keywords in HML-L1"
    assert not (freed & B_RESERVED_WORDS), "B still reserves some of them"


def test_candidate_b_rejects_hml_l1_statement_keywords():
    with pytest.raises(SurfaceParseError):
        CANDIDATES["B"].parse("mod M\nparam a_ : Real\n")


# -- candidate C ---------------------------------------------------------


def test_candidate_c_head_vocabulary_is_closed_and_does_not_capture_user_names():
    """A symbol spelled like a C head must still round-trip.

    `call`, `neg`, `mul`, `pow` and `given` are ordinary identifiers in HML-L1 and in
    the frozen subset. Because C never puts a user symbol in head position, they parse
    as references and nothing collides.
    """
    collisions = ("call", "neg", "mul", "div", "pow", "given", "extends_")
    assert {"call", "neg", "mul", "div", "pow", "given"} <= C_HEADS
    assert not ({"call", "neg", "mul", "div", "pow", "given"} & RESERVED_IN_ANY_SURFACE)
    source = "module HeadCollision\n" + "".join(
        f"param {name} : Real\n" for name in collisions
    ) + "def total := " + " + ".join(collisions) + "\n"
    result = compile_source(source, "<head-collision>")
    assert result.ok(), "\n" + result.diagnostics.render()
    for cid in CANDIDATE_IDS:
        outcome = round_trip(CANDIDATES[cid], result.module, "head-collision")
        assert outcome.ok, f"[{cid}] {outcome.stage}: {outcome.detail}"


def test_candidate_c_uses_an_algebraic_dimension_not_an_exponent_vector():
    """The parity decision, asserted rather than described.

    `Mass * Length^2 / Time^2` must appear as a div/mul/pow tree with positive
    exponents. A signed exponent vector would hand C a normalisation the linear
    surfaces leave to the reader.
    """
    result = compile_source(
        "module Dim\nparam q_ : Quantity[Mass * Length^2 / Time^2]\n", "<dim>"
    )
    assert result.ok()
    text = CANDIDATES["C"].render(result.module)
    assert "(div (mul (pow Length 2) Mass) (pow Time 2))" in text, text
    assert "-2" not in text, f"C published a signed exponent: {text}"


# -- candidate D ---------------------------------------------------------


def test_candidate_d_document_is_sorted_and_tagged():
    text = CANDIDATES["D"].render(_worked_module())
    doc = json.loads(text)
    assert doc["surface"] == D_DOCUMENT_VERSION
    assert text == json.dumps(doc, indent=2, sort_keys=True) + "\n"


def test_candidate_d_rejects_an_unknown_key_anywhere():
    text = CANDIDATES["D"].render(_worked_module())
    doc = json.loads(text)
    doc["statements"][0]["symbol"] = "sym:#0.0"
    with pytest.raises(SurfaceParseError):
        CANDIDATES["D"].parse(json.dumps(doc))


def test_candidate_d_carries_no_node_identities():
    """The departure from the `e_graph_triple` sketch, asserted on real output."""
    text = CANDIDATES["D"].render(_worked_module())
    for forbidden in ('"id"', '"node_id"', '"refTo"', '"symbol"', '"ordinal"', '"depth"', "_:"):
        assert forbidden not in text, f"D emitted {forbidden}"


def test_candidate_d_uses_an_algebraic_dimension_not_an_exponent_vector():
    result = compile_source(
        "module Dim\nparam q_ : Quantity[Mass * Length^2 / Time^2]\n", "<dim>"
    )
    assert result.ok()
    dimension = json.loads(CANDIDATES["D"].render(result.module))["statements"][0]["type"][
        "dimension"
    ]
    assert dimension == {
        "numerator": [["Length", "2"], ["Mass", "1"]],
        "denominator": [["Time", "2"]],
    }, dimension


def test_candidate_d_keeps_integer_and_real_literals_distinct():
    """`1` and `1.0` are different values in the canonical form and must stay different."""
    integral = compile_source("module M\nconst k_ : Real = 1\n").module
    real = compile_source("module M\nconst k_ : Real = 1.0\n").module
    assert content_hash(integral) != content_hash(real)
    for cid in CANDIDATE_IDS:
        a = round_trip(CANDIDATES[cid], integral, "int")
        b = round_trip(CANDIDATES[cid], real, "real")
        assert a.ok and b.ok
        assert a.recovered_hash != b.recovered_hash, f"[{cid}] collapsed 1 and 1.0"


# -- the shipped example corpus ------------------------------------------


def _example_files():
    root = REPO / "examples"
    out = []
    for path in sorted(root.rglob("*.hml")):
        if any((parent / ".illustrative").exists() for parent in path.parents):
            continue
        out.append(path)
    return out


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
@pytest.mark.parametrize(
    "path", _example_files(), ids=lambda p: p.relative_to(REPO / "examples").as_posix()
)
def test_every_shipped_example_round_trips_in_every_surface(candidate_id, path):
    """The generated corpus is systematic; the shipped examples are what people read."""
    result = compile_source(path.read_text(), str(path))
    assert result.ok(), "\n" + result.diagnostics.render()
    outcome = round_trip(CANDIDATES[candidate_id], result.module, str(path))
    assert outcome.ok, (
        f"[{candidate_id}] {path} failed at {outcome.stage}: {outcome.detail}\n"
        f"--- rendered ---\n{outcome.rendered}"
    )
