"""The frozen syntax-gate subset — the single source of truth shared by the manifest
and by :mod:`tests.freeze.test_quarantine`.

`docs/evaluation/V1_FREEZE_MANIFEST.md` classifies every V0/V1 feature. This module is
the *machine-readable* half of that document. The two are tied together mechanically:
``test_quarantine.py`` parses the manifest's classification table and asserts that it
agrees with the constants below, so neither can drift from the other silently.

Why an allowlist rather than a denylist
---------------------------------------
A denylist of quarantined constructs fails open: a construct nobody thought to list is
admitted. The gate is therefore specified as a **closed set** of surface keywords and
statement kinds. Adding a keyword to the lexer, or a ``Statement`` subclass to the AST,
fails ``test_quarantine.py`` until the manifest is amended and re-evidenced. That is the
whole mechanism: *promotion into the gate cannot happen as a side effect.*

The three things the gate is defined by
---------------------------------------
1. ``FROZEN_KEYWORDS`` — every token the lexer may treat as a keyword.
2. ``FROZEN_STATEMENT_KINDS`` — every ``ast.nodes.Statement`` subclass.
3. ``FROZEN_TYPE_NAMES`` — every name admissible in type position.

Plus one structural rule: **no module under ``src/hamiltonian_lang/`` outside ``v1/``
may import ``hamiltonian_lang.v1``.** That import edge is what would make the
quarantined layers reachable from ``hml check``; today there is none, and
``test_quarantine.py`` keeps it that way.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "docs" / "evaluation" / "V1_FREEZE_MANIFEST.md"

#: The closed classification vocabulary. A row carrying anything else is a manifest bug.
CLASSIFICATIONS: frozenset[str] = frozenset(
    {
        "SUPPORTED_ENFORCED",
        "SUPPORTED_PARTIAL",
        "EXPERIMENTAL",
        "KNOWN_FAILED",
        "DEFERRED",
        "UNSUPPORTED",
    }
)

#: Everything at or above this bar may be reached from the syntax gate. Everything below
#: it is quarantined and must be unreachable.
GATE_ADMITS: frozenset[str] = frozenset({"SUPPORTED_ENFORCED"})


# ---------------------------------------------------------------------------
# 1. Surface keywords
# ---------------------------------------------------------------------------

#: Exactly ``hamiltonian_lang.lexer.KEYWORDS``. Frozen at the V0 statement inventory
#: (V0_DESIGN_FREEZE.md §3) plus the concept-member keywords. Note what is ABSENT and
#: must stay absent: goal, discharge, pending_obligation, case, otherwise, end_case,
#: step, derive, yields, entails, equivalent, converse, family, member, relation, mint.
#: Those are the L2-L5 surfaces of docs/design/V1_KERNEL.md §§2-5.
FROZEN_KEYWORDS: frozenset[str] = frozenset(
    {
        # structure
        "module", "concept", "extends", "end",
        # declarations
        "var", "param", "const", "obs", "index", "rv", "def", "fn",
        # probabilistic
        "law", "prior", "likelihood", "infer", "posterior", "expectation",
        "variance", "mle", "map",
        # logical / constraint
        "assume", "require", "prove", "check", "dimension", "solve",
        "minimise", "maximise", "minimize", "maximize",
        # quantifiers and connectives
        "forall", "exists", "unique", "and", "or", "not", "implies", "iff",
        # concept members
        "parameter", "transform", "invariant", "property", "example",
        "counterexample",
        # literals
        "true", "false",
    }
)

#: Keywords that appear in ``FROZEN_KEYWORDS`` but begin no statement. Recorded so that
#: the statement-dispatch check below is exact rather than approximate.
NON_STATEMENT_KEYWORDS: frozenset[str] = frozenset(
    {
        "extends", "end", "fn", "posterior", "expectation", "variance", "mle", "map",
        "dimension", "forall", "exists", "unique", "and", "or", "not", "implies",
        "iff", "parameter", "transform", "invariant", "property", "example",
        "counterexample", "true", "false",
    }
)

#: Surface forms that `docs/design/V1_KERNEL.md` proposes for the quarantined layers.
#: Every one of these must fail to compile. The value is the layer it belongs to.
QUARANTINED_SURFACE_FORMS: dict[str, str] = {
    "goal g1 := 1 > 0": "L5 discourse",
    "discharge g1 by p1": "L5 discourse",
    "case c1 := 1 > 0": "L5 discourse",
    "otherwise": "L5 discourse",
    "end_case": "L5 discourse",
    "pending_obligation": "L5 discourse",
    "step s1 := divide(expr := e1, by := a)": "L2 transformation",
    "derive e3 from [e1, e2] via s1": "L2 transformation",
    "yields e3": "L2 transformation",
    "entails p3 from [p1, p2] via modus_ponens": "L3 inference",
    "equivalent p1 p2": "L3 inference",
    "counterexample_to p1 witness w": "L3 inference",
    "family Estimation of theta : ParameterSpace": "semantic morphology",
    "member estimator : Real": "semantic morphology",
    "relation estimate = 1": "semantic morphology",
    "mint LocationScaleFamily": "concept minting",
    "admit LocationScaleFamily": "concept minting",
}

#: Type names the quarantined layers would need in type position. None exists in
#: ``hamiltonian_lang.types``; each must be rejected as an unknown type.
#:
#: ``PValue`` and ``PosteriorProbability`` were on this list and have been **promoted**:
#: they are now scalars in ``types.py`` with no coercion path to or from ``Probability``
#: (D-022), so they are admissible in type position and appear in
#: :data:`FROZEN_SCALARS` instead. Every other name here remains unreachable.
QUARANTINED_TYPE_NAMES: tuple[str, ...] = (
    "Credence",
    "Evidence",
    "Proof",
    "Assumption",
    "Justification",
    "Derivation",
    "Entailment",
    "Goal",
    "HypothesisTest",
    "EstimationProcedure",
)


# ---------------------------------------------------------------------------
# 2. Statement kinds
# ---------------------------------------------------------------------------

#: Exactly the ``Statement`` subclasses in ``hamiltonian_lang.ast.nodes``. A new
#: statement form cannot enter the gate without editing this set, which forces the
#: manifest to be amended in the same change.
FROZEN_STATEMENT_KINDS: frozenset[str] = frozenset(
    {
        "ModuleDecl",
        "Declaration",
        "DefineStmt",
        "LawStmt",
        "AssumeStmt",
        "RequireStmt",
        "ProveStmt",
        "ObjectiveStmt",
        "SolveStmt",
        "InferStmt",
        "CheckStmt",
        "ConceptDecl",
    }
)


# ---------------------------------------------------------------------------
# 3. Types
# ---------------------------------------------------------------------------

#: Scalar names, exactly ``hamiltonian_lang.types.SCALARS``.
#:
#: ``PValue`` and ``PosteriorProbability`` joined the lattice in D-022. They are not a
#: promotion of the L4 *layer*: no `hamiltonian_lang.v1` module became reachable, no
#: keyword was added, and no epistemic status, justification or claim object entered the
#: gate. What entered is two scalars, pairwise incomparable with ``Probability``, which
#: is the narrowest change that lets an HML program state the distinction the kill
#: criterion is about.
FROZEN_SCALARS: frozenset[str] = frozenset(
    {
        "Bool", "PositiveNatural", "Natural", "Integer", "Rational", "Real",
        "NonNegativeReal", "PositiveReal", "Probability",
        "PValue", "PosteriorProbability",
    }
)

#: Type constructors admissible in type position, in addition to the scalars and to any
#: ``concept`` declared in the same module.
FROZEN_TYPE_CONSTRUCTORS: frozenset[str] = frozenset(
    {
        "Vector", "Matrix", "Tensor", "Set", "Function", "Predicate",
        "RandomVariable", "Distribution", "Quantity", "Proposition", "Dimensionless",
    }
)

FROZEN_TYPE_NAMES: frozenset[str] = FROZEN_SCALARS | FROZEN_TYPE_CONSTRUCTORS


# ---------------------------------------------------------------------------
# 4. The V0 -> V1 import barrier
# ---------------------------------------------------------------------------

#: Package that must remain unreachable from the compiler pipeline.
QUARANTINED_PACKAGE = "hamiltonian_lang.v1"

#: Directory whose modules are allowed to import :data:`QUARANTINED_PACKAGE`.
QUARANTINED_PACKAGE_DIR = REPO_ROOT / "src" / "hamiltonian_lang" / "v1"

COMPILER_SOURCE_DIR = REPO_ROOT / "src" / "hamiltonian_lang"


# ---------------------------------------------------------------------------
# 5. Manifest rows
# ---------------------------------------------------------------------------

#: Every feature the manifest is required to classify, in the order Phase F1 specified.
#: ``test_quarantine`` asserts the manifest carries exactly these rows.
REQUIRED_MANIFEST_ROWS: tuple[str, ...] = (
    "declarations and types",
    "probability roles",
    "PValue",
    "binders and quantifiers",
    "dimensions",
    "transformations",
    "epistemic statuses",
    "discourse obligations",
    "concept references",
    "concept minting and admission",
    "semantic morphology",
    "Lean",
    "Stan",
    "SymPy",
)

#: The classification each row carries. Duplicated from the manifest deliberately: the
#: test asserts the two agree, so an edit to one without the other is a test failure
#: rather than a silent divergence.
MANIFEST_CLASSIFICATION: dict[str, str] = {
    "declarations and types": "SUPPORTED_ENFORCED",
    "probability roles": "SUPPORTED_ENFORCED",
    "PValue": "SUPPORTED_ENFORCED",
    "binders and quantifiers": "SUPPORTED_ENFORCED",
    "dimensions": "SUPPORTED_ENFORCED",
    "transformations": "EXPERIMENTAL",
    "epistemic statuses": "EXPERIMENTAL",
    "discourse obligations": "EXPERIMENTAL",
    "concept references": "SUPPORTED_ENFORCED",
    "concept minting and admission": "KNOWN_FAILED",
    "semantic morphology": "EXPERIMENTAL",
    "Lean": "UNSUPPORTED",
    "Stan": "SUPPORTED_PARTIAL",
    "SymPy": "SUPPORTED_PARTIAL",
}


def quarantined_rows() -> tuple[str, ...]:
    """Every manifest row classified below ``SUPPORTED_ENFORCED``."""
    return tuple(
        row
        for row, verdict in MANIFEST_CLASSIFICATION.items()
        if verdict not in GATE_ADMITS
    )
