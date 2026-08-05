"""The four candidate syntaxes, the shared-core feature vocabulary, and the front-end
interface this package needs from ``evaluation/syntax_acquisition/``.

Why a feature vocabulary rather than prose
------------------------------------------
"Representable in all four candidates" has to be a decidable predicate, or Track A
membership becomes a judgement call and the gate becomes negotiable after the fact. Every
task declares the set of core features it uses; every candidate declares the set it
supports; a task is Track A iff its features are a subset of the intersection. The
exclusion reason is then a *fact* — which feature, which candidate, which grammar line —
rather than an opinion, which is what ``EXPRESSIBILITY_MATRIX.csv`` records.

Capability sets are read off the frozen grammars in ``spec/grammars/`` and, for
candidate A, off the implemented compiler. Where the grammar and the implementation
disagree the **implementation wins**, because the implementation is what will parse the
model's output. One such disagreement is recorded below: ``exists_unique``.

The front-end interface
-----------------------
Rendering and parsing the four surfaces belongs to the Phase F3 offline equivalence gate
(``evaluation/syntax_acquisition/``), which this package must not edit. ``SyntaxAdapter``
is the interface required from it. Only candidate A is implementable here and now, from
the existing compiler, so ``V0LinearAdapter`` is provided as the reference implementation
of the protocol and as the live end of the tests. The other three resolve to ``None``
until F3 lands, and every consumer must treat ``None`` as *not measured*, never as zero.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from hamiltonian_lang.improvement.episodes import (
    StageOutcome,
    StageStatus,
    TerminalOutcome,
    classify_stages,
)

__all__ = [
    "CANDIDATES",
    "CANDIDATE_IDS",
    "CORE_FEATURES",
    "SHARED_CORE_FEATURES",
    "SCORED_FACETS",
    "SE_CONTROL",
    "Candidate",
    "Feature",
    "ParseOutcome",
    "StageOutcome",
    "StageStatus",
    "TerminalOutcome",
    "unsupported_stages",
    "SyntaxAdapter",
    "V0LinearAdapter",
    "SyntaxAcquisitionAdapter",
    "F3_CANDIDATE_ID",
    "SYNTAX_ACQUISITION_INTERFACE",
    "resolve_adapters",
    "adapter_availability",
]

# ---------------------------------------------------------------------------
# Feature vocabulary
# ---------------------------------------------------------------------------

Feature = str

#: Every semantic feature a task in this milestone may use. A task declaring a feature
#: outside this set is a bug, not a new capability -- `tests` asserts closure.
CORE_FEATURES: frozenset[Feature] = frozenset(
    {
        # declarations
        "decl_var", "decl_param", "decl_const", "decl_obs", "decl_index", "decl_rv",
        # types
        "type_scalar", "type_refined", "type_quantity", "type_proposition",
        "type_random_variable", "type_function", "type_set",
        # definitions
        "def_simple", "def_parametric",
        # probability
        "law_labelled_roles", "law_conditioning", "law_prior", "law_likelihood",
        # propositions and queries
        "assume", "require", "prove", "objective", "solve", "infer",
        "check_dimension",
        # logic
        "quantifier_nested", "quantifier_negation", "op_implication", "op_equivalence",
        "op_comparison", "op_arithmetic", "op_logical",
        # blocks
        "concept_block", "concept_named_invariant",
        # features on which the four candidates genuinely disagree
        "surface_precedence_disambiguation", "quantifier_exists_unique",
        # V1 layers -- Track B territory
        "v1_transformation_step", "v1_derivation", "v1_entailment",
        "v1_epistemic_status", "v1_discourse_goal", "v1_case_analysis",
        "v1_concept_minting", "v1_family_declaration", "v1_semantic_morphology",
    }
)

#: The facets ``evaluation.semantic_equiv.SemanticComparison`` can score. A task declares
#: which of these its ground truth actually populates; a candidate declares which it can
#: expose deterministically. Scoreability is the second half of Track A membership.
SCORED_FACETS: frozenset[str] = frozenset(
    {
        "entities", "types", "declaration_kinds", "law_families", "roles",
        "conditioning", "quantifier_order", "objective", "dimensions",
    }
)

_V1_FEATURES: frozenset[Feature] = frozenset(f for f in CORE_FEATURES if f.startswith("v1_"))

#: Features every candidate supports, computed once the candidates are declared.
_V0_SEMANTIC_CORE: frozenset[Feature] = frozenset(
    f
    for f in CORE_FEATURES
    if not f.startswith("v1_")
    and f
    not in {
        "surface_precedence_disambiguation",
        "quantifier_exists_unique",
        "concept_named_invariant",
    }
)



@dataclass(frozen=True)
class Candidate:
    """One competing surface rendering of the identical semantic core."""

    id: str
    label: str
    #: Where the surface is specified. A capability claim with no reference is an opinion.
    grammar_ref: str
    features: frozenset[Feature]
    scoreable_facets: frozenset[str]
    #: Fenced-block tags the model is told to use, in preference order.
    fence_tags: tuple[str, ...]
    #: Properties that bias this candidate, stated rather than hidden.
    known_hazards: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


A_V0_LINEAR = "A_v0_labelled_linear"
B_V1_LINEAR = "B_v1_labelled_linear_simplified"
C_SEXPR = "C_prefix_sexpr"
D_JSON_GRAPH = "D_constrained_json_graph"

#: The matched control condition. **Not a candidate** -- it cannot win the gate. It exists
#: because the Gate 2 token threshold is defined relative to structured English, so a
#: matched structured-English arm is a required measurement, not an optional extra.
SE_CONTROL = "SE_structured_english"

CANDIDATES: dict[str, Candidate] = {
    A_V0_LINEAR: Candidate(
        id=A_V0_LINEAR,
        label="V0 labelled-linear (HML-L1, the implemented syntax)",
        grammar_ref="spec/grammars/a_labelled_linear.ebnf; implemented in src/hamiltonian_lang",
        features=(
            _V0_SEMANTIC_CORE
            | {"surface_precedence_disambiguation", "concept_named_invariant"}
        ),
        scoreable_facets=SCORED_FACETS,
        fence_tags=("hml", "hamiltonian"),
        known_hazards=(
            "the only candidate with a real implementation, so its diagnostics are "
            "richer than the others'; direction: in favour of A",
        ),
        notes=(
            "shadowing is rejected by design decision D-006 (HML-N302), so a module-level "
            "declaration may not share a name with a quantifier binder.",
        ),
    ),
    B_V1_LINEAR: Candidate(
        id=B_V1_LINEAR,
        label="simplified V1 labelled-linear",
        grammar_ref="spec/v1/semantic_objects.yaml; evaluation/v1/corpus.py::V1_VOCAB_SPEC",
        features=(
            _V0_SEMANTIC_CORE
            | _V1_FEATURES
            | {"surface_precedence_disambiguation", "concept_named_invariant"}
        ),
        scoreable_facets=SCORED_FACETS,
        fence_tags=("hml", "hmlv1", "hamiltonian"),
        known_hazards=(
            "the only candidate that can express the V1 layers, so Track B is scoreable "
            "in B alone; that is exactly why Track B may not touch the gate",
        ),
        notes=(
            "a superset surface over A for the shared core: every shared-core feature A "
            "accepts, B accepts with the same spelling.",
            "exists_unique is recorded as UNSUPPORTED rather than unknown. B's front end "
            "does not exist yet and will be built on the same parser core as A, which "
            "rejects it. Assuming support for an unbuilt parser would put a task in "
            "Track A that may prove unrepresentable; the conservative call is the safe "
            "one and is revisited when F3 lands.",
        ),
    ),
    C_SEXPR: Candidate(
        id=C_SEXPR,
        label="prefix / S-expression",
        grammar_ref="spec/grammars/c_sexpr.ebnf",
        features=_V0_SEMANTIC_CORE | {"quantifier_exists_unique"},
        scoreable_facets=SCORED_FACETS,
        fence_tags=("sexpr", "lisp", "scheme"),
        known_hazards=(
            "grammar header: no operator precedence and no infix position, so the parse "
            "tree IS the AST. A task about recovering intended grouping from an "
            "unparenthesised infix expression cannot be posed in C at all.",
        ),
        notes=(
            "grammar lines 22-45 cover declaration/define/law/assume/require/objective/"
            "solve/infer/check/prove/concept; lines 69-76 cover forall, exists and "
            "exists_unique.",
            "grammar line 54: `member ::= \"(\" \"invariant\" expr \")\"` has no IDENT "
            "slot, so C cannot name an invariant. HML-L1 requires the name (HML-P202, "
            "verified), so a concept task with named invariants is not representable in C.",
        ),
    ),
    D_JSON_GRAPH: Candidate(
        id=D_JSON_GRAPH,
        label="constrained JSON / graph triples",
        grammar_ref="spec/grammars/e_graph_triple.ebnf",
        features=(
            _V0_SEMANTIC_CORE
            | {"quantifier_exists_unique", "concept_named_invariant"}
        ),
        scoreable_facets=SCORED_FACETS,
        fence_tags=("json", "triples", "graph"),
        known_hazards=(
            "grammar note E2: D has NO SYNTACTIC SCOPE. Quantifier nesting is one edge, "
            "so 'forall x . exists y' and 'exists y . forall x' differ by exactly one "
            "triple. Representable, and maximally fragile. Direction: against D on the "
            "quantifier_scope domain specifically.",
        ),
        notes=(
            "node classes and the closed predicate vocabulary are the real specification "
            "(grammar lines 33-110); a triple with an unlisted predicate is rejected.",
            "grammar line 47: the `order` predicate carries statement order explicitly, "
            "so order-dependent content is representable despite the unordered file.",
            "grammar lines 76-89 reify every expression as nodes and lhs/rhs edges, so "
            "there is no unparenthesised infix form to disambiguate.",
        ),
    ),
}

#: Features the four candidates genuinely disagree on, with the evidence for each
#: verdict. ``EXPRESSIBILITY_MATRIX.csv`` reads its "why" straight out of this table, so
#: no reason recorded in that file is an opinion.
FEATURE_EVIDENCE: dict[tuple[str, str], str] = {
    ("quantifier_exists_unique", A_V0_LINEAR): (
        "NO: a_labelled_linear.ebnf line 93 lists exists_unique but the implemented "
        "parser rejects it with HML-P204 (verified 2026-08-05). The implementation wins."
    ),
    ("quantifier_exists_unique", B_V1_LINEAR): (
        "NO (conservative): B's front end does not exist and will share A's parser core."
    ),
    ("quantifier_exists_unique", C_SEXPR): "YES: c_sexpr.ebnf line 76.",
    ("quantifier_exists_unique", D_JSON_GRAPH): (
        "YES: e_graph_triple.ebnf line 90, quantKind -> forall|exists|exists_unique."
    ),
    ("concept_named_invariant", A_V0_LINEAR): (
        "YES: HML-L1 requires the name; an unnamed invariant is HML-P202 (verified)."
    ),
    ("concept_named_invariant", B_V1_LINEAR): "YES: B inherits A's concept block.",
    ("concept_named_invariant", C_SEXPR): (
        "NO: c_sexpr.ebnf line 54, `(\"invariant\" expr)` has no IDENT slot."
    ),
    ("concept_named_invariant", D_JSON_GRAPH): (
        "YES: e_graph_triple.ebnf line 51 `name ... ConceptMember -> NAME` with "
        "memberKind invariant on line 107."
    ),
    ("surface_precedence_disambiguation", A_V0_LINEAR): (
        "YES: a_labelled_linear.ebnf declares an infix precedence ladder."
    ),
    ("surface_precedence_disambiguation", B_V1_LINEAR): "YES: B keeps A's infix ladder.",
    ("surface_precedence_disambiguation", C_SEXPR): (
        "NO: c_sexpr.ebnf header, 'no operator precedence and no infix position'. The "
        "question cannot be posed, not merely answered differently."
    ),
    ("surface_precedence_disambiguation", D_JSON_GRAPH): (
        "NO: e_graph_triple.ebnf lines 76-89 reify every expression as a tree; there is "
        "no unparenthesised form whose grouping is in doubt."
    ),
}

#: Every V1 layer feature is unsupported by A, C and D for the same reason.
for _f in _V1_FEATURES:
    FEATURE_EVIDENCE[(_f, B_V1_LINEAR)] = (
        "YES: evaluation/v1/corpus.py::V1_VOCAB_SPEC layers L2-L5."
    )
    for _c in (A_V0_LINEAR, C_SEXPR, D_JSON_GRAPH):
        FEATURE_EVIDENCE[(_f, _c)] = (
            "NO: the V1 layers postdate this surface and it has no vocabulary for them."
        )

CANDIDATE_IDS: tuple[str, ...] = (A_V0_LINEAR, B_V1_LINEAR, C_SEXPR, D_JSON_GRAPH)

#: The intersection. Track A membership is decided against this and nothing else.
SHARED_CORE_FEATURES: frozenset[Feature] = frozenset.intersection(
    *(CANDIDATES[c].features for c in CANDIDATE_IDS)
)

#: Facets scoreable in every candidate. The second half of Track A membership.
SHARED_SCOREABLE_FACETS: frozenset[str] = frozenset.intersection(
    *(CANDIDATES[c].scoreable_facets for c in CANDIDATE_IDS)
)


# ---------------------------------------------------------------------------
# The interface required from evaluation/syntax_acquisition/
# ---------------------------------------------------------------------------


@dataclass
class ParseOutcome:
    """The result of pushing one candidate-syntax encoding through its front end.

    ``hml_l1`` is the load-bearing field. Normalising every candidate to HML-L1 means
    semantic preservation is computed by **one** comparator
    (``evaluation.semantic_equiv.compare_semantics``) for all four surfaces. Four
    comparators would make a preservation difference between candidates indistinguishable
    from a difference between comparators.

    ``ok`` is **not** a parse verdict
    ---------------------------------
    ``ok`` means *the whole pipeline accepted this text* — parsed, resolved and
    type-checked. It was being read as "it parsed", and it is not. Measured on this
    compiler, ``HML-T426`` (wrong arity), ``HML-T415`` (wrong role label) and
    ``HML-T403`` (declared-type mismatch) all parse cleanly and resolve cleanly, failing
    only in the type checker; an unknown identifier parses cleanly and fails in
    resolution. Counting any of them as a parse failure understates ACQ0's first-attempt
    parse rate and blames the candidate surface for the compiler's type checking.

    Read :attr:`parsed` for the parse verdict and :attr:`stages` for the full per-stage
    record. ``ok`` is retained because "did this compile" is also a real question, and
    the fix is to ask each question by its own name rather than to rename one of them.
    """

    ok: bool
    #: The encoding normalised to HML-L1, or None when the front end could not.
    hml_l1: str | None = None
    #: Diagnostic codes, not prose, so failure categories aggregate.
    diagnostics: list[str] = field(default_factory=list)
    #: The surface text that was parsed, preserved verbatim.
    surface: str = ""
    #: Set when the front end for this candidate does not exist yet. Distinct from a
    #: parse failure: absence of a measurement is not a failed measurement.
    unavailable_reason: str | None = None
    #: Per-stage verdicts. ``None`` only from a front end that has not been updated to
    #: report them; consumers must treat that as *not measured*, never as a pass.
    stages: StageOutcome | None = None

    @property
    def parsed(self) -> bool | None:
        """Whether the text was in the language. ``None`` when nothing measured it.

        ``None`` rather than ``False`` on absence: a front end that reports no stage
        record has not observed a parse failure, and returning ``False`` here would
        manufacture one.
        """
        return None if self.stages is None else self.stages.parsed

    @property
    def terminal(self) -> TerminalOutcome | None:
        return None if self.stages is None else self.stages.terminal


@runtime_checkable
class SyntaxAdapter(Protocol):
    """What ``evaluation/syntax_acquisition/`` must expose, per candidate.

    Four members. ``render`` builds demonstrations and the F3 round-trip corpus;
    ``parse`` is what the scorer needs at trial time.
    """

    candidate_id: str
    #: False for stubs and for adapters that never touch a model or a network.
    LIVE: bool

    def render(self, hml_l1: str) -> str:
        """Render an HML-L1 source text into this candidate's surface."""

    def parse(self, encoding: str) -> ParseOutcome:
        """Parse this candidate's surface and normalise it back to HML-L1."""


#: This package's candidate ids mapped onto the single-letter ids the Phase F3 package
#: registers. Kept as data so a rename on either side is a one-line change and not a
#: silent mismatch that resolves every candidate to None.
F3_CANDIDATE_ID = {
    A_V0_LINEAR: "A",
    B_V1_LINEAR: "B",
    C_SEXPR: "C",
    D_JSON_GRAPH: "D",
}

#: Reported verbatim to the Lead Architect and to the F3 agent. Kept as data so a
#: mismatch between what this package needs and what F3 builds is discoverable by
#: reading one constant rather than by reading this module.
SYNTAX_ACQUISITION_INTERFACE = {
    "module": "evaluation.syntax_acquisition",
    "resolution_order": [
        "get_adapter(candidate_id: str) -> SyntaxAdapter | None",
        "ADAPTERS: Mapping[str, SyntaxAdapter]",
        "candidate('A'|'B'|'C'|'D') -> SyntaxCandidate  [bound via "
        "SyntaxAcquisitionAdapter; this is what Phase F3 actually shipped]",
    ],
    "as_shipped": (
        "F3 exposes SyntaxCandidate with render(Module) -> str and parse(str) -> Module, "
        "raising SurfaceParseError. This package needs text in and a verdict out, so "
        "SyntaxAcquisitionAdapter converts at the boundary and normalises every "
        "candidate back to HML-L1 so that ONE comparator scores all four surfaces."
    ),
    "candidate_ids": list(CANDIDATE_IDS),
    "f3_candidate_ids": dict(F3_CANDIDATE_ID),
    "protocol": {
        "attribute candidate_id": "str, one of candidate_ids",
        "attribute LIVE": "bool, False when the adapter performs no model or network call",
        "method render(hml_l1: str) -> str": (
            "render an HML-L1 source text into this candidate's surface; used for "
            "demonstration curricula and for the F3 round-trip matrix"
        ),
        "method parse(encoding: str) -> ParseOutcome": (
            "parse this candidate's surface; set ok (whole pipeline accepted), fill "
            "hml_l1 with the HML-L1 normalisation, fill diagnostics with codes, echo "
            "surface verbatim, and fill `stages` with a StageOutcome. `ok` is NOT a "
            "parse verdict: HML-T426/T415/T403 all parse and fail later, so a front end "
            "that leaves `stages` empty makes its trials unusable for the first-attempt "
            "parse rate."
        ),
    },
    "import_path_for_ParseOutcome": "evaluation.syntax_gate.candidates.ParseOutcome",
    "contract": (
        "parse() must never raise. A front end that cannot handle an input returns "
        "ok=False with diagnostics. A front end that does not exist yet is represented "
        "by get_adapter returning None, which this package reports as NOT MEASURED."
    ),
}


# ---------------------------------------------------------------------------
# Candidate A: the one front end that exists today
# ---------------------------------------------------------------------------

_FENCE = re.compile(
    r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\r?\n(.*?)```", re.S
)


def extract_fenced(text: str, tags: tuple[str, ...]) -> str | None:
    """Pull the first fenced block whose tag is in ``tags``, else any untagged fence.

    A model that omits the tag has made a formatting error, not a mathematical one. The
    two are measured separately, so the fallback is deliberate.
    """
    if not text:
        return None
    blocks = [((m.group(1) or "").lower(), m.group(2)) for m in _FENCE.finditer(text)]
    lowered = tuple(t.lower() for t in tags)
    for want in lowered:
        for tag, body in blocks:
            if tag == want:
                return body.strip()
    for tag, body in blocks:
        if tag in ("", "text"):
            return body.strip()
    return None


def unsupported_stages(reason: str) -> StageOutcome:
    """The stage record for machinery that does not exist. Never a failure."""
    return StageOutcome(
        parse_status=StageStatus.NOT_RUN,
        resolution_status=StageStatus.NOT_RUN,
        type_status=StageStatus.NOT_RUN,
        semantic_status=StageStatus.NOT_RUN,
        verification_status=StageStatus.NOT_RUN,
        terminal=TerminalOutcome.UNSUPPORTED,
        detail=reason,
    )


class V0LinearAdapter:
    """Candidate A, implemented against the frozen compiler.

    The reference implementation of ``SyntaxAdapter``. Candidate A's surface *is* HML-L1,
    so ``render`` and the HML-L1 normalisation are both the identity; all the work is in
    reporting the compiler's verdict without embellishing it — and in reporting it
    **stage by stage**, so that a type error is never counted as a syntax error.
    """

    candidate_id = A_V0_LINEAR
    LIVE = False

    def render(self, hml_l1: str) -> str:
        return hml_l1

    def parse(self, encoding: str) -> ParseOutcome:
        stages = classify_stages(encoding or "", file="syntax_gate#A")
        compiled = stages.compiled
        return ParseOutcome(
            ok=compiled,
            hml_l1=encoding if compiled else None,
            diagnostics=list(stages.diagnostic_codes),
            surface=encoding or "",
            stages=stages,
        )


class SyntaxAcquisitionAdapter:
    """Shim from the Phase F3 ``SyntaxCandidate`` onto this package's protocol.

    The two interfaces differ, and the difference is real rather than cosmetic: F3 works
    in ``Module`` objects because its job is a round-trip over canonical objects, while
    the scorer works in **text**, because what a model emits is text and what the gate
    measures is whether that text parses. The shim converts at the boundary:

        HML-L1 text -> Module -> candidate surface           (render)
        candidate surface -> Module -> HML-L1 text -> verdict (parse)

    Normalising every candidate back to HML-L1 is what lets **one** comparator
    (``evaluation.semantic_equiv.compare_semantics``) score all four surfaces. Four
    comparators would make a preservation difference between candidates
    indistinguishable from a difference between comparators.
    """

    LIVE = False

    def __init__(self, candidate_id: str, sc: Any) -> None:
        self.candidate_id = candidate_id
        self._sc = sc

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<SyntaxAcquisitionAdapter {self.candidate_id} -> {self._sc!r}>"

    def render(self, hml_l1: str) -> str:
        from hamiltonian_lang import compile_source

        result = compile_source(hml_l1, f"syntax_gate#{self.candidate_id}")
        if result.module is None:
            raise ValueError(
                f"cannot render {self.candidate_id}: the HML-L1 source did not parse"
            )
        return self._sc.render(result.module)

    def parse(self, encoding: str) -> ParseOutcome:
        """Parse the surface, then classify the normalised HML-L1 stage by stage.

        Two distinct failures are kept apart. A **surface** parse error — the text is not
        in candidate B/C/D's grammar — is ``PARSE_FAILED``. A surface that parses and
        normalises into HML-L1 that the semantic core then rejects is *not* a parse
        failure: the model wrote the candidate syntax correctly and got the mathematics
        wrong, and ``classify_stages`` says which stage caught it.
        """
        from hamiltonian_lang.backends.hml import render_module

        if not (encoding or "").strip():
            stages = StageOutcome(
                parse_status=StageStatus.FAIL,
                resolution_status=StageStatus.NOT_RUN,
                type_status=StageStatus.NOT_RUN,
                semantic_status=StageStatus.NOT_RUN,
                verification_status=StageStatus.NOT_RUN,
                terminal=TerminalOutcome.PARSE_FAILED,
                diagnostic_codes=("EMPTY",),
                detail="the attempt produced no text to parse",
            )
            return ParseOutcome(False, None, ["EMPTY"], encoding or "", stages=stages)
        try:
            module = self._sc.parse(encoding)
        except Exception as exc:  # noqa: BLE001 -- parse() must never raise
            codes: list[str] = []
            bag = getattr(exc, "diagnostics", None)
            if bag is not None:
                codes = [d.code for d in getattr(bag, "errors", [])]
            codes = codes or [f"SURFACE:{type(exc).__name__}"]
            stages = StageOutcome(
                parse_status=StageStatus.FAIL,
                resolution_status=StageStatus.NOT_RUN,
                type_status=StageStatus.NOT_RUN,
                semantic_status=StageStatus.NOT_RUN,
                verification_status=StageStatus.NOT_RUN,
                terminal=TerminalOutcome.PARSE_FAILED,
                diagnostic_codes=tuple(codes),
                detail=f"the text is not in candidate {self.candidate_id}'s grammar",
            )
            return ParseOutcome(False, None, codes, encoding, stages=stages)
        try:
            hml = render_module(module)
        except Exception as exc:  # noqa: BLE001
            # The surface parsed and the normaliser broke. That is a fact about this
            # front end, not about the model's text, so it decides nothing.
            stages = StageOutcome(
                parse_status=StageStatus.NOT_RUN,
                resolution_status=StageStatus.NOT_RUN,
                type_status=StageStatus.NOT_RUN,
                semantic_status=StageStatus.NOT_RUN,
                verification_status=StageStatus.NOT_RUN,
                terminal=TerminalOutcome.INCONCLUSIVE,
                diagnostic_codes=(f"RENDER:{type(exc).__name__}",),
                detail=(
                    "the surface parsed but the HML-L1 normaliser raised; the front end "
                    "failed, so this trial has no verdict about the model"
                ),
            )
            return ParseOutcome(
                False, None, [f"RENDER:{type(exc).__name__}"], encoding, stages=stages
            )
        # The surface parsed; the semantic core still has to accept it. A candidate that
        # reads back into an ill-typed module has not preserved the object.
        stages = classify_stages(hml, file=f"syntax_gate#{self.candidate_id}")
        compiled = stages.compiled
        return ParseOutcome(
            ok=compiled,
            hml_l1=hml if compiled else None,
            diagnostics=list(stages.diagnostic_codes),
            surface=encoding,
            stages=stages,
        )


def resolve_adapters(
    *, prefer_syntax_acquisition: bool = True
) -> dict[str, SyntaxAdapter | None]:
    """Bind each candidate to a front end, preferring the Phase F3 agent's.

    Returns ``None`` for any candidate with no front end. Callers must propagate that as
    NOT MEASURED. Substituting a permissive fallback here would produce a parse rate for
    a parser that does not exist, which is the single most damaging thing this package
    could do.
    """
    out: dict[str, SyntaxAdapter | None] = dict.fromkeys(CANDIDATE_IDS, None)
    mod = None
    if prefer_syntax_acquisition:
        try:
            mod = importlib.import_module("evaluation.syntax_acquisition")
        except Exception:  # noqa: BLE001 -- absence is data, not an error
            mod = None
    for cid in CANDIDATE_IDS:
        adapter: SyntaxAdapter | None = None
        if mod is not None:
            getter = getattr(mod, "get_adapter", None)
            if callable(getter):
                try:
                    adapter = getter(cid)
                except Exception:  # noqa: BLE001
                    adapter = None
            if adapter is None:
                table = getattr(mod, "ADAPTERS", None)
                if isinstance(table, dict):
                    adapter = table.get(cid)
            if adapter is None:
                # The Phase F3 package registers single-letter candidates exposing
                # render(Module)/parse(text). Bind through the shim rather than
                # reporting NOT AVAILABLE for a front end that exists.
                getter = getattr(mod, "candidate", None)
                if callable(getter):
                    try:
                        sc = getter(F3_CANDIDATE_ID[cid])
                    except Exception:  # noqa: BLE001 -- absence is data
                        sc = None
                    if sc is not None:
                        adapter = SyntaxAcquisitionAdapter(cid, sc)
        out[cid] = adapter
    if out[A_V0_LINEAR] is None:
        out[A_V0_LINEAR] = V0LinearAdapter()
    return out


def adapter_availability() -> dict[str, str]:
    """Which candidates can be measured today, and by what. Reported, not assumed."""
    resolved = resolve_adapters()
    report: dict[str, str] = {}
    for cid in CANDIDATE_IDS:
        a = resolved[cid]
        if a is None:
            report[cid] = (
                "NOT AVAILABLE: no front end. Required from "
                "evaluation.syntax_acquisition (Phase F3)."
            )
        else:
            report[cid] = f"available: {type(a).__module__}.{type(a).__name__}"
    return report
