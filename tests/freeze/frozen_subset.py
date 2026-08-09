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
        # -- V2 reasoning spine (D-025) ------------------------------------
        # Admitted deliberately, not by drift. These five open the derivation
        # statement forms described in docs/hml_v2/REASONING_MODEL.md.
        #
        # Note that the V1_KERNEL surface forms in QUARANTINED_SURFACE_FORMS below
        # remain REJECTED: `goal g1 := ...` and `derive e3 from [...] via s1` are
        # different syntax from V2's `goal g1 : ...` and
        # `derive d1 : ... from ... by ...`. The quarantine of the L2/L3/L5 *layers*
        # is unaffected -- V2 reaches its own kernel in `reasoning/`, not `v1/`, and
        # the import barrier in test_quarantine.py still forbids that edge.
        "derive", "goal", "proved", "from", "by",
        # -- V2 mathematical expression coverage (D-026) -------------------
        # Eleven keywords, each opening ONE expression production that closes one of
        # the eleven critical coverage zeros the language audit measured. Admitted
        # deliberately, with the same three questions answered for each as for D-025:
        #
        # 1. *Does it reach a quarantined layer?* No. Every one of these is handled in
        #    `parser/`, `type_system/` and `backends/`. None reaches
        #    `hamiltonian_lang.v1`; the import barrier below is untouched and
        #    `test_no_compiler_module_statically_imports_the_quarantined_package`
        #    still passes.
        # 2. *Does it promote a QUARANTINED_SURFACE_FORM?* No. The forms in that table
        #    (`step`, `entails`, `family`, `member`, `relation`, `mint`, ...) remain
        #    rejected; none of these eleven appears there, and none of them is a
        #    spelling of one.
        # 3. *Is it enforced or merely parsed?* Enforced. Each has a type rule that
        #    REJECTS the corresponding misuse -- HML-T480/T481/T482/T483/T484/T485/
        #    T486/T487/T488/T489/T490/T491/T492/T493/T494/T495 -- which is the bar
        #    `SUPPORTED_ENFORCED` sets. The executed rejection for each lives in
        #    `tests/adversarial/test_v2_expression_rejections.py`, NOT in
        #    `docs/evaluation/V1_FREEZE_MANIFEST.md`: that manifest is the frozen
        #    evidence document for the V1 language, its rows are pinned by
        #    REQUIRED_MANIFEST_ROWS below, and D-025 set the precedent that V2
        #    additions are evidenced in DECISIONS.md and docs/hml_v2/ rather than
        #    backdated into it. The full record is D-026 and
        #    docs/hml_v2/EXPRESSION_COVERAGE.md.
        #
        # `expectation` and `variance` are ABSENT from this block because they were
        # already frozen keywords. D-026 did not add them; it gave them an expression
        # production they had never had, which is what unshadowed the type rules the
        # audit found unreachable.
        "probability", "joint", "independent", "in",
        "limit", "derivative", "integral", "continuous",
        "associated", "correlated", "causes",
        # -- scoped assumption frames (D-043) ------------------------------
        # `scope ... end` is what makes "assume P *for the purposes of this argument*"
        # expressible. Admitted deliberately: it reaches the refinement environment in
        # `reasoning/refinement.py`, not the quarantined `v1/` layer, and the import
        # barrier is untouched. It reuses `end`, so the block convention stays one
        # convention rather than two.
        "scope",
        # -- the checked-certificate boundary (D-047) ----------------------
        # Four keywords opening two statement forms:
        #     evidence     e1 : entails <prop> [from ...] by <checker>(...)
        #     evidence     e2 : determines_neither <prop> from ... by <checker>(...)
        #     undetermined g1 by e2
        #
        # Admitted deliberately, with the same three questions D-025 and D-026 answered:
        #
        # 1. *Does it reach the quarantined `v1/` layer?* No. `evidence` reaches
        #    `reasoning/certificates/`, a new package depending only on `ast/`,
        #    `backends/canonical.py` and `verification/obligations/evaluate.py`. The
        #    import barrier is untouched.
        # 2. *Does it promote a QUARANTINED_SURFACE_FORM?* No -- and this needs stating
        #    carefully, because `entails` also appears in that table. The quarantined L3
        #    form is `entails p3 from [p1, p2] via modus_ponens`, where `entails` is a
        #    STATEMENT HEAD. Here it is never a statement head: it is a mandatory
        #    judgement qualifier that can appear only after `evidence <label> :`. The
        #    parser dispatches no statement on `entails`, so the L3 form still fails to
        #    parse, and `test_quarantined_surface_forms_are_rejected` still asserts it.
        #    The two occupy different grammatical positions and could coexist if L3 were
        #    ever unquarantined.
        # 3. *Is it enforced or merely parsed?* Enforced, which is the entire point. An
        #    `evidence` statement is REJECTED unless a checker in the static registry
        #    validates the exact envelope; `undetermined` is REJECTED unless that
        #    certificate is VALID, carries a `determines_neither` judgement, is about the
        #    goal's own proposition, and was issued against the context still in scope.
        #    Executed rejections: `tests/reasoning/test_certificates.py` and
        #    `tests/reasoning/test_underdetermination.py`.
        #
        # Record: DECISIONS.md D-047, docs/hml_v2/GOLD10_CORE_SEMANTICS_SPEC.md.
        "evidence", "undetermined", "entails", "determines_neither",
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
        # V2: `from` and `by` are separators inside `derive`/`proved`, not statement
        # heads. `derive`, `goal` and `proved` ARE statement heads and so are absent.
        "from", "by",
        # D-026: all eleven are EXPRESSION heads. None begins a statement, which is
        # exactly why the statement-kind set below is unchanged: this change adds
        # mathematics that composes inside the statements that already exist, rather
        # than adding statements.
        "probability", "joint", "independent", "in",
        "limit", "derivative", "integral", "continuous",
        "associated", "correlated", "causes",
        # D-047: `entails` and `determines_neither` are judgement qualifiers *inside* an
        # `evidence` statement, never statement heads -- which is precisely why the
        # quarantined L3 form `entails p3 from [...] via ...` remains rejected.
        # `evidence` and `undetermined` ARE statement heads and so are absent.
        "entails", "determines_neither",
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
        # -- V2 reasoning spine (D-025) ------------------------------------
        "GoalStmt",
        "DeriveStmt",
        "ProvedStmt",
        # -- scoped assumption frames (D-043) ------------------------------
        "ScopeStmt",
        # -- the checked-certificate boundary (D-047) ----------------------
        # `EvidenceStmt` is the bridge through which HML-owned capability -- the exact
        # evaluator, definitional unfolding -- becomes reasoning evidence, and through
        # which future libraries will do the same without adding trusted kernel rules.
        # `UndeterminedStmt` is the adjudicating counterpart of `ProvedStmt`.
        #
        # Neither carries a settable status: `EvidenceStatus` and `GoalStatus` are
        # computed, exactly as `DerivationStatus` is, and there is no surface syntax for
        # VALID or UNDERDETERMINED.
        "EvidenceStmt",
        "UndeterminedStmt",
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
        # -- D-026 -------------------------------------------------------
        # `Event` is nullary like `Proposition`, and INCOMPARABLE with it: an event has
        # a probability, a proposition has a truth value, and admitting one where the
        # other is expected is the conflation the constructor exists to prevent.
        #
        # `Product[T1, T2]` is what gives `joint(X, Y)` an honest type. Neither name
        # appears in QUARANTINED_TYPE_NAMES, and neither is a spelling of anything
        # there: no epistemic status, justification, proof or derivation object entered
        # the gate.
        "Event", "Product",
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
