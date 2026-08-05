"""The offline round-trip gate, as pytest items.

100% round-trip on the frozen supported subset is the phase requirement, so the failure
message carries the failing stage and the rendered text: a red cell here has to be
actionable without re-running anything.
"""

from __future__ import annotations

import pytest
from evaluation.syntax_acquisition.core import CANDIDATES, round_trip
from evaluation.syntax_acquisition.generator import (
    CORPUS_CHUNKS as CHUNKS,
)
from evaluation.syntax_acquisition.generator import (
    MIN_CORPUS_SIZE,
    build_corpus,
    corpus,
    coverage_report,
)
from evaluation.syntax_acquisition.generator import (
    corpus_chunk as chunk,
)

CANDIDATE_IDS = tuple(sorted(CANDIDATES))


# -- corpus health -------------------------------------------------------


def test_corpus_reaches_the_required_size():
    assert len(corpus()) >= MIN_CORPUS_SIZE


def test_every_generated_source_compiles():
    """A source the compiler refuses is dropped, so the count must stay at zero.

    Without this the corpus could shrink silently: a generator change that broke half
    the programs would still leave a green round-trip suite over whatever survived.
    """
    _, rejected = build_corpus()
    assert rejected == (), "generated sources the compiler refused:\n" + "\n".join(
        f"  {oid}: {msg}" for oid, msg in rejected
    )


def test_object_ids_are_unique():
    ids = [o.id for o in corpus()]
    assert len(ids) == len(set(ids))


# -- coverage ------------------------------------------------------------

_REQUIRED_COVERAGE = {
    "declaration_kind": ("var", "param", "const", "obs", "index", "rv"),
    "quantifier": ("forall", "exists", "exists_unique"),
    "infer_query": (
        "posterior", "expectation", "variance", "mle", "map", "solve",
        "minimise", "maximise",
    ),
    "concept_member": (
        "parameter", "transform", "invariant", "property", "example", "counterexample",
    ),
    "operator": (
        "+", "-", "*", "/", "^", "@",
        "=", "!=", "<", "<=", ">", ">=",
        "and", "or", "implies", "iff", "not",
    ),
    "statement": (
        "Declaration", "DefineStmt", "LawStmt", "AssumeStmt", "RequireStmt", "ProveStmt",
        "ObjectiveStmt", "SolveStmt", "InferStmt", "CheckStmt", "ConceptDecl",
        "law:law", "law:prior", "law:likelihood",
        "check:proposition", "check:dimension",
        "DefineStmt:with-params",
    ),
    "binder_depth": ("1", "2", "3", "4"),
}

_REQUIRED_SCALARS = (
    "Bool", "Natural", "PositiveNatural", "Integer", "Rational", "Real",
    "NonNegativeReal", "PositiveReal", "Probability",
)


@pytest.fixture(scope="module")
def coverage():
    return coverage_report()


@pytest.mark.parametrize("axis,values", sorted(_REQUIRED_COVERAGE.items()))
def test_corpus_reaches_every_value_on_each_axis(coverage, axis, values):
    """A green gate over a corpus that never reaches a construct proves nothing about it.

    This is the same lesson ``tests/roundtrip`` records for alpha-renaming: the property
    test was green while the property was false, because the generator never produced
    the one binder form that failed.
    """
    missing = [v for v in values if coverage[axis].get(v, 0) == 0]
    assert not missing, f"axis {axis!r} never reached: {missing}"


def test_corpus_reaches_every_scalar_refinement(coverage):
    missing = [s for s in _REQUIRED_SCALARS if coverage["scalar_type"].get(s, 0) == 0]
    assert not missing, f"scalar refinements never declared: {missing}"


def test_corpus_reaches_every_distribution_family(coverage):
    from hamiltonian_lang.type_system.distributions import DISTRIBUTIONS

    missing = [f for f in DISTRIBUTIONS if coverage["distribution_family"].get(f, 0) == 0]
    assert not missing, f"distribution families never used: {missing}"


def test_corpus_reaches_every_parameter_role(coverage):
    from hamiltonian_lang.type_system.distributions import DISTRIBUTIONS

    missing = [
        f"{family}.{role}"
        for family, spec in DISTRIBUTIONS.items()
        for role in spec.roles
        if coverage["parameter_role"].get(f"{family}.{role}", 0) == 0
    ]
    assert not missing, f"parameter roles never filled: {missing}"


def test_corpus_reaches_rational_exponents_and_dimension_variables(coverage):
    dimensions = list(coverage["dimension"])
    assert any("^1/2" in d or "^3/2" in d for d in dimensions), (
        f"no rational dimension exponent in the corpus: {dimensions}"
    )
    # A dimension variable is a single capital letter that is not a base dimension.
    assert any(
        any(part.strip().rstrip("^0123456789/").strip() in ("D", "E") for part in d.split("*"))
        for d in dimensions
    ), f"no dimension variable in the corpus: {dimensions}"


# -- the matrix ----------------------------------------------------------


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
@pytest.mark.parametrize("index", range(CHUNKS))
def test_round_trip(candidate_id, index):
    cand = CANDIDATES[candidate_id]
    failures = []
    for obj in chunk(index):
        outcome = round_trip(cand, obj.module, obj.id)
        if not outcome.ok:
            failures.append(
                f"[{candidate_id}] {obj.id} failed at {outcome.stage}: {outcome.detail}\n"
                f"--- rendered ---\n{outcome.rendered}"
            )
    assert not failures, "\n\n".join(failures[:5])


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
@pytest.mark.parametrize("index", range(CHUNKS))
def test_rendering_is_byte_identical_on_repeat(candidate_id, index):
    cand = CANDIDATES[candidate_id]
    for obj in chunk(index):
        first = cand.render(obj.module)
        assert first == cand.render(obj.module), f"[{candidate_id}] {obj.id} is not deterministic"


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
@pytest.mark.parametrize("index", range(CHUNKS))
def test_rendering_is_ascii(candidate_id, index):
    """ASCII is the canonical serialization (v0 freeze section 1), for every surface."""
    cand = CANDIDATES[candidate_id]
    for obj in chunk(index):
        cand.render(obj.module).encode("ascii")


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
@pytest.mark.parametrize("index", range(CHUNKS))
def test_reparse_is_idempotent(candidate_id, index):
    """render -> parse -> render must reach a fixed point in one step."""
    cand = CANDIDATES[candidate_id]
    for obj in chunk(index):
        once = cand.render(obj.module)
        twice = cand.render(cand.parse(once))
        assert once == twice, f"[{candidate_id}] {obj.id} is not idempotent"
