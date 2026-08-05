"""The Diagnostic Context Broker — error-conditioned retrieval over the semantic index.

The retrieval order, and why it is this order
---------------------------------------------
::

    1  DETERMINISTIC_CODE_MAP   the code alone fixes the answer
    2  EXACT_SYMBOL             the offending name is in the index verbatim
    3  AST_NEIGHBOURHOOD        names and constructs adjacent to the failing span
    4  SEMANTIC_EXAMPLE         a compiling example exercising the same construct
    5  (none)                   an explicit no-context result

Stages are ordered by decreasing precision and increasing cost, and the first stages are
*free*. A wrong-arity diagnostic does not need a search: it needs the callee's signature
and the arity rule, and those are a dictionary lookup. Spending a model call on a
deterministic failure buys nothing and adds sampling variance to a measurement.

COCOGEN's ablation is the reason stages 2–4 exist at all: compiler feedback alone did not
deliver the full gain, and most of the remaining gain arrived in the first retrieval.
Stages 1 and 2 therefore both run and their results are pooled; 3 and 4 run only while the
item budget is unspent.

Four outcomes, and no fifth
---------------------------
:class:`ContextStatus` is total over what can happen:

``CONTEXT_FOUND``          at least one item was retrieved
``NO_RELEVANT_CONTEXT``    the query was valid and the index has nothing — say so
``QUERY_INVALID``          the query is malformed (no code, or a code of the wrong shape)
``UNSUPPORTED_ERROR_CLASS`` the code is well-formed but its family is unknown here

There is deliberately no "best effort" outcome. **Never hallucinate a rule.** An invented
rule inside a repair packet is worse than no context, because it arrives with exactly the
authority of a true one and the record cannot tell them apart afterwards.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..improvement.diagnostics import StructuredDiagnostic
from .index import ContextItem, FacetKind, SemanticIndex, build_index, local_items
from .taxonomy import TAXONOMY_VERSION, Classification, ErrorClass, classify

__all__ = [
    "BROKER_VERSION",
    "ContextStatus",
    "RetrievalStage",
    "DETERMINISTIC_FACETS",
    "DETERMINISTIC_CODE_NOTE",
    "ContextQuery",
    "RetrievedContext",
    "DiagnosticContextBroker",
]

BROKER_VERSION = "hml-context-broker-1.0.0"


class ContextStatus(StrEnum):
    """The four things retrieval can conclude. Total, by construction."""

    CONTEXT_FOUND = "CONTEXT_FOUND"
    NO_RELEVANT_CONTEXT = "NO_RELEVANT_CONTEXT"
    QUERY_INVALID = "QUERY_INVALID"
    UNSUPPORTED_ERROR_CLASS = "UNSUPPORTED_ERROR_CLASS"


class RetrievalStage(StrEnum):
    """Which rung of the ladder produced an item."""

    DETERMINISTIC_CODE_MAP = "deterministic_code_map"
    EXACT_SYMBOL = "exact_symbol"
    AST_NEIGHBOURHOOD = "ast_neighbourhood"
    SEMANTIC_EXAMPLE = "semantic_example"
    NONE = "none"


#: **The hard-coded frequent mappings.** These five codes account for the bulk of observed
#: encoding failures, and each has exactly one right answer, so none of them may cost a
#: model call. Keys are diagnostic codes; values are the facets to draw from, in order.
DETERMINISTIC_FACETS: dict[str, tuple[FacetKind, ...]] = {
    # wrong number of arguments -> the callee's signature, and the arity rule
    "HML-T471": (FacetKind.FUNCTION_SIGNATURE, FacetKind.RULE_CARD),
    # argument fails the parameter's refinement -> argument position and refinement rule
    "HML-T472": (FacetKind.RULE_CARD, FacetKind.COERCION_RULE, FacetKind.TYPE),
    # wrong distribution role label -> the family's named roles
    "HML-T415": (FacetKind.DISTRIBUTION_ROLE, FacetKind.RULE_CARD),
    # unknown type name -> the valid type vocabulary, with a nearest-name suggestion
    "HML-T440": (FacetKind.TYPE, FacetKind.CONSTRUCTOR),
    # unknown callee -> the known-function list
    "HML-N306": (FacetKind.FUNCTION_SIGNATURE,),
}

#: What each deterministic mapping is *for*, stated so a reader of a repair record can see
#: that the retrieval was mechanical and not a search that happened to succeed.
DETERMINISTIC_CODE_NOTE: dict[str, str] = {
    "HML-T471": "function signature and arity rule",
    "HML-T472": "argument position and required refinement type",
    "HML-T415": "named distribution roles",
    "HML-T440": "valid type vocabulary (with nearest-name suggestion)",
    "HML-N306": "unknown callee / known function list",
}

#: Identifiers, quoted names and dotted paths that may appear in a diagnostic's fields.
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_QUOTED = re.compile(r"'([^']+)'|\"([^\"]+)\"")

#: Words that appear in every diagnostic and identify nothing. Matching on them would turn
#: exact-symbol lookup into a full-index scan wearing a precise-looking label.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "not", "no", "and", "or", "of", "to", "in", "at",
        "it", "its", "be", "was", "were", "has", "have", "had", "this", "that", "these",
        "given", "found", "expected", "argument", "arguments", "takes", "type", "types",
        "unknown", "declared", "value", "values", "did", "you", "mean", "use", "used",
        "one", "two", "three", "line", "role", "roles", "must", "may", "can", "cannot",
        "here", "there", "with", "without", "from", "for", "but", "does", "do", "known",
        "function", "functions", "name", "names", "bound", "call", "calls", "requires",
    }
)


@dataclass(frozen=True)
class ContextQuery:
    """What retrieval is conditioned on.

    ``diagnostic`` is the only mandatory part: the whole point of error-conditioned
    retrieval is that the error selects the context. ``source`` and ``neighbourhood_names``
    are optional and only feed stage 3.
    """

    diagnostic: StructuredDiagnostic
    #: The broken program, used to read the AST neighbourhood of the failing span.
    source: str | None = None
    #: Names already known to be in scope, if the caller has resolved them.
    neighbourhood_names: tuple[str, ...] = ()
    #: Upper bound on retrieved items. A packet that is mostly context is a packet the
    #: model reads past.
    max_items: int = 6
    #: Whether to index the broken program's own declarations. On by default: a
    #: wrong-arity call on a user ``def`` needs *that* signature, not the built-in list.
    include_local: bool = True

    def is_valid(self) -> tuple[bool, str]:
        d = self.diagnostic
        if not isinstance(d, StructuredDiagnostic):
            return False, "query.diagnostic is not a StructuredDiagnostic"
        if not d.code.strip():
            return False, "query.diagnostic.code is empty; retrieval is error-conditioned"
        if self.max_items < 1:
            return False, f"query.max_items must be >= 1, got {self.max_items}"
        return True, ""


@dataclass(frozen=True)
class RetrievedContext:
    """The result of one retrieval. Carries its own status, never a bare list.

    A caller that reads ``items`` without reading ``status`` cannot distinguish "the index
    has nothing" from "the code was malformed", and those demand different repairs — one
    of the index, one of the caller.
    """

    status: ContextStatus
    classification: Classification
    items: tuple[ContextItem, ...] = ()
    stages_used: tuple[RetrievalStage, ...] = ()
    #: Why the status is what it is. Always populated for the three non-found statuses.
    reason: str = ""
    #: Populated when the code is one of the five hard-coded mappings.
    deterministic_note: str = ""
    broker_version: str = BROKER_VERSION
    taxonomy_version: str = TAXONOMY_VERSION

    @property
    def found(self) -> bool:
        return self.status is ContextStatus.CONTEXT_FOUND

    @property
    def error_class(self) -> ErrorClass | None:
        return self.classification.error_class

    def provenance(self) -> tuple[str, ...]:
        return tuple(i.provenance.render() for i in self.items)

    def render(self) -> str:
        """The context block a repair packet shows. Empty statuses render their reason.

        Every line carries its provenance, so a reader of a transcript can check any claim
        against the file it came from. A context block without provenance is a block of
        assertions of unknown origin.
        """
        if not self.items:
            return f"[{self.status}] {self.reason}"
        lines = [f"[{self.status}] {len(self.items)} item(s) retrieved:"]
        for item in self.items:
            lines.append(f"- ({item.facet}) {item.content}")
            lines.append(f"  source: {item.provenance.render()}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": str(self.status),
            "classification": self.classification.to_dict(),
            "items": [i.to_dict() for i in self.items],
            "stages_used": [str(s) for s in self.stages_used],
            "reason": self.reason,
            "deterministic_note": self.deterministic_note,
            "broker_version": self.broker_version,
            "taxonomy_version": self.taxonomy_version,
        }


# ---------------------------------------------------------------------------
# The broker
# ---------------------------------------------------------------------------


@dataclass
class DiagnosticContextBroker:
    """Error-conditioned retrieval. Deterministic, offline, and honest about emptiness."""

    index: SemanticIndex = field(default_factory=build_index)

    # -- public ------------------------------------------------------------------

    def retrieve(self, query: ContextQuery) -> RetrievedContext:
        ok, why = query.is_valid()
        if not ok:
            code = getattr(getattr(query, "diagnostic", None), "code", "")
            return RetrievedContext(
                status=ContextStatus.QUERY_INVALID,
                classification=classify(str(code)),
                reason=why,
                stages_used=(RetrievalStage.NONE,),
            )

        diagnostic = query.diagnostic
        classification = classify(diagnostic.code)
        if not classification.well_formed:
            return RetrievedContext(
                status=ContextStatus.QUERY_INVALID,
                classification=classification,
                reason=(
                    f"{diagnostic.code!r} is not a Hamiltonian Lang diagnostic code "
                    "(expected HML-<letter><three digits>)"
                ),
                stages_used=(RetrievalStage.NONE,),
            )
        if not classification.supported:
            return RetrievedContext(
                status=ContextStatus.UNSUPPORTED_ERROR_CLASS,
                classification=classification,
                reason=(
                    f"{diagnostic.code} is well-formed but its family is not in the repair "
                    "taxonomy; no error class can be assigned without guessing"
                ),
                stages_used=(RetrievalStage.NONE,),
            )

        local = SemanticIndex()
        if query.include_local and query.source:
            local.extend(local_items(query.source))

        collected: list[ContextItem] = []
        stages: list[RetrievalStage] = []
        seen: set[tuple[str, str]] = set()

        def take(items: Sequence[ContextItem], stage: RetrievalStage) -> None:
            added = False
            for item in items:
                if len(collected) >= query.max_items:
                    break
                ident = (str(item.facet), item.key)
                if ident in seen:
                    continue
                seen.add(ident)
                collected.append(item)
                added = True
            if added:
                stages.append(stage)

        take(
            self._stage_deterministic(diagnostic, local),
            RetrievalStage.DETERMINISTIC_CODE_MAP,
        )
        take(self._stage_exact_symbol(diagnostic, local), RetrievalStage.EXACT_SYMBOL)
        if len(collected) < query.max_items:
            take(self._stage_neighbourhood(query, local), RetrievalStage.AST_NEIGHBOURHOOD)
        if len(collected) < query.max_items:
            take(
                self._stage_examples(diagnostic, classification.error_class),
                RetrievalStage.SEMANTIC_EXAMPLE,
            )

        note = DETERMINISTIC_CODE_NOTE.get(diagnostic.code, "")
        if not collected:
            return RetrievedContext(
                status=ContextStatus.NO_RELEVANT_CONTEXT,
                classification=classification,
                stages_used=(RetrievalStage.NONE,),
                reason=(
                    f"the index holds nothing keyed to {diagnostic.code} "
                    f"({classification.error_class}) or to any symbol named in it; "
                    "no rule is supplied rather than an invented one"
                ),
                deterministic_note=note,
            )
        return RetrievedContext(
            status=ContextStatus.CONTEXT_FOUND,
            classification=classification,
            items=tuple(collected),
            stages_used=tuple(stages),
            deterministic_note=note,
        )

    # -- stages ------------------------------------------------------------------

    def _by_key(
        self, local: SemanticIndex, key: str, *, facets: Sequence[FacetKind] | None = None
    ) -> list[ContextItem]:
        """Local declarations first, then the global index. Order encodes specificity."""
        return local.by_key(key, facets=facets) + self.index.by_key(key, facets=facets)

    def _stage_deterministic(
        self, d: StructuredDiagnostic, local: SemanticIndex
    ) -> list[ContextItem]:
        """Stage 1. The code alone selects the answer — no search, no model call."""
        out: list[ContextItem] = []

        facets = DETERMINISTIC_FACETS.get(d.code)
        if facets is not None:
            # Symbol hits under the mapped facets: the offending name, resolved against
            # the program's own declarations first and the global tables second.
            hits: list[ContextItem] = []
            for name in _candidate_symbols(d):
                for item in self._by_key(local, name, facets=facets):
                    if item not in hits:
                        hits.append(item)
            # Then the generic answer for this code. One merged ranking, so a vocabulary
            # list cannot be pushed out of the budget by individual table entries: for an
            # unknown type name the useful context is "here is the whole vocabulary", not
            # the first six scalars in declaration order.
            generic = [
                i
                for i in self.index.by_code(d.code)
                if i.facet in facets and i not in hits
            ]
            out.extend(_rank_deterministic(hits, generic))
        else:
            out.extend(_rank_deterministic([], self.index.by_code(d.code)))

        # The invariant card for the code, wherever it exists, always belongs.
        for item in self.index.by_key(d.code, facets=(FacetKind.DIAGNOSTIC_CODE,)):
            if item not in out:
                out.append(item)
        return out

    def _stage_exact_symbol(
        self, d: StructuredDiagnostic, local: SemanticIndex
    ) -> list[ContextItem]:
        """Stage 2. The names the diagnostic itself quoted, looked up verbatim."""
        out: list[ContextItem] = []
        for name in _candidate_symbols(d):
            for item in self._by_key(local, name):
                if item.facet is not FacetKind.EXAMPLE and item not in out:
                    out.append(item)
        return out

    def _stage_neighbourhood(
        self, query: ContextQuery, local: SemanticIndex
    ) -> list[ContextItem]:
        """Stage 3. Identifiers on and around the failing line of the broken program."""
        names = list(query.neighbourhood_names)
        source = query.source
        line = query.diagnostic.source_span.line
        if source and line > 0:
            lines = source.splitlines()
            lo, hi = max(0, line - 2), min(len(lines), line + 1)
            for text in lines[lo:hi]:
                names.extend(_IDENT.findall(text))
        out: list[ContextItem] = []
        for name in _dedupe(names):
            if name.casefold() in _STOPWORDS:
                continue
            for item in self._by_key(local, name):
                if item.facet is not FacetKind.EXAMPLE and item not in out:
                    out.append(item)
        return out

    def _stage_examples(
        self, d: StructuredDiagnostic, error_class: ErrorClass | None
    ) -> list[ContextItem]:
        """Stage 4. A compiling example that exercises the same construct.

        Matched on the symbols the diagnostic named, not on the error class alone: an
        example retrieved because both concern "types" teaches nothing specific.
        """
        wanted = [n for n in _candidate_symbols(d) if n.casefold() not in _STOPWORDS]
        if not wanted:
            return []
        out: list[ContextItem] = []
        for item in self.index.by_facet(FacetKind.EXAMPLE):
            if any(re.search(rf"(?<![A-Za-z0-9_]){re.escape(w)}\b", item.content)
                   for w in wanted):
                out.append(item)
        return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rank_deterministic(
    symbol_hits: Sequence[ContextItem], generic: Sequence[ContextItem]
) -> list[ContextItem]:
    """Order stage-1 results by specificity, as one merged list.

    Ranking, most specific first:

    0. a declaration in the program under repair — the most project-specific fact there is
    1. a global table entry matching the offending name (the ``Normal`` role card for a
       ``variance`` label)
    2. the rule that governs this code class
    3. a vocabulary list (the whole type vocabulary, the whole builtin list)
    4. everything else

    Ranking the two sources together rather than concatenating them is what stops a
    vocabulary list being pushed past ``max_items`` by individual table rows.
    """

    def rank(item: ContextItem, hit: bool) -> int:
        if hit and "local" in item.tags:
            return 0
        if hit:
            return 1
        if item.facet is FacetKind.RULE_CARD:
            return 2
        if "vocabulary" in item.tags:
            return 3
        return 4

    tagged = [(rank(i, True), n, i) for n, i in enumerate(symbol_hits)]
    offset = len(symbol_hits)
    tagged += [(rank(i, False), offset + n, i) for n, i in enumerate(generic)]
    return [i for _, _, i in sorted(tagged, key=lambda t: (t[0], t[1]))]


def _dedupe(names: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _candidate_symbols(d: StructuredDiagnostic) -> list[str]:
    """The names a diagnostic points at, most specific first.

    ``found`` and ``expected`` come first because the compiler put the offending spelling
    there deliberately; quoted names in the message come next; bare identifiers in the
    message come last and are stop-worded, because a message is prose and most of its
    words name nothing.
    """
    out: list[str] = []
    for value in (d.actual, d.expected):
        if not value:
            continue
        head = value.split(":", 1)[0].split("(", 1)[0].strip().strip("'\"")
        if head and _IDENT.fullmatch(head):
            out.append(head)
        out.extend(m for m in _IDENT.findall(value))
    for text in (d.message, *(d.notes or ()), d.local_hint or ""):
        for m in _QUOTED.finditer(text):
            out.append(m.group(1) or m.group(2))
    for text in (d.message,):
        out.extend(_IDENT.findall(text))
    return [n for n in _dedupe(out) if n.casefold() not in _STOPWORDS]
