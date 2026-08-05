"""The semantic index — every project-specific fact a repair may be shown.

The COCOGEN finding this implements
-----------------------------------
A diagnostic says *what* is wrong. It does not say *which* project-specific signature,
role, refinement or rule should replace the wrong thing. COCOGEN's ablations found that
compiler feedback alone did not deliver the full gain: error-conditioned **retrieval over
a structural project graph** was needed. This module is that graph's node set; retrieval
over it lives in :mod:`.broker`.

The one rule that makes this index safe
---------------------------------------
**Every item is derived from a real artefact and carries the provenance to prove it.**
:class:`ContextItem` cannot be constructed without a :class:`Provenance`, and
:meth:`SemanticIndex.unresolved_provenance` re-derives every source path from disk. An
invented rule in a repair packet is worse than no rule at all, because it arrives with the
same authority as a true one and nothing downstream distinguishes them. The facets below
are therefore *transcriptions* of ``types.py``, ``type_system/distributions.py``,
``v1/epistemic.py``, ``v1/backend_support.py`` and ``CLAUDE.md`` — not summaries of them.

When a facet has no entry for a query, the answer is emptiness, which
:mod:`.broker` reports as ``NO_RELEVANT_CONTEXT``. Emptiness is a result.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

__all__ = [
    "INDEX_VERSION",
    "FacetKind",
    "Provenance",
    "ContextItem",
    "SemanticIndex",
    "build_index",
    "local_items",
    "repo_root",
]

#: Bumped when a facet changes shape or a new facet is added.
INDEX_VERSION = "hml-semantic-index-1.0.0"


class FacetKind(StrEnum):
    """The eleven kinds of project fact this index holds.

    Fixed by the H3 programme specification. A twelfth kind would need a decision record;
    silently widening the index would let unattributed material reach a repair packet.
    """

    TYPE = "type"
    FUNCTION_SIGNATURE = "function_signature"
    CONSTRUCTOR = "constructor"
    DISTRIBUTION_ROLE = "distribution_role"
    COERCION_RULE = "coercion_rule"
    EPISTEMIC_RULE = "epistemic_rule"
    DIAGNOSTIC_CODE = "diagnostic_code"
    EXAMPLE = "example"
    RULE_CARD = "rule_card"
    BACKEND_SUPPORT = "backend_support"
    CONSTITUTIONAL_INVARIANT = "constitutional_invariant"


def repo_root() -> Path | None:
    """The repository root, or ``None`` when the package is installed outside a checkout.

    Returning ``None`` rather than guessing matters: provenance verification then reports
    ``UNRESOLVED`` instead of silently passing on a path that was never checked.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src").is_dir():
            return parent
    return None


@dataclass(frozen=True)
class Provenance:
    """Where a context item's content came from. Mandatory on every item.

    ``source`` is either ``module:<dotted.path>`` or ``file:<repo-relative path>``.
    ``symbol`` names the table, constant or heading inside that source. Together they are
    enough for a reader to go and check the item by hand, which is the only test of an
    index that actually matters.
    """

    source: str
    symbol: str

    def __post_init__(self) -> None:
        if not self.source.startswith(("module:", "file:")):
            raise ValueError(
                f"Provenance.source must start with 'module:' or 'file:'; got "
                f"{self.source!r}. An item whose origin cannot be resolved is "
                "indistinguishable from an invented one."
            )
        if not self.symbol.strip():
            raise ValueError("Provenance.symbol must name the table or heading")

    def resolve(self) -> Path | None:
        """The file this provenance points at, or ``None`` if it cannot be located."""
        kind, _, rest = self.source.partition(":")
        if kind == "module":
            try:
                spec = importlib.util.find_spec(rest)
            except (ImportError, ValueError):
                return None
            if spec is None or spec.origin is None:
                return None
            path = Path(spec.origin)
            return path if path.is_file() else None
        root = repo_root()
        if root is None:
            return None
        path = root / rest
        return path if path.is_file() else None

    def render(self) -> str:
        return f"{self.source}#{self.symbol}"


@dataclass(frozen=True)
class ContextItem:
    """One retrievable fact.

    ``key`` is what exact-symbol lookup matches on (a type name, a function name, a
    distribution family, a diagnostic code). ``content`` is what a repair packet shows.
    ``aliases`` carry the *wrong* spellings that should still find this item — a
    misparameterisation such as ``variance`` is precisely the query that must reach the
    ``Normal`` role card.
    """

    facet: FacetKind
    key: str
    content: str
    provenance: Provenance
    aliases: tuple[str, ...] = ()
    #: Diagnostic codes for which this item is the *deterministic* answer.
    codes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("ContextItem.key must be non-empty")
        if not self.content.strip():
            raise ValueError(
                f"ContextItem({self.facet}, {self.key!r}).content is empty; an item with "
                "no content is a retrieval hit that teaches nothing"
            )

    def match_keys(self) -> tuple[str, ...]:
        return (self.key, *self.aliases)

    def to_dict(self) -> dict[str, Any]:
        return {
            "facet": str(self.facet),
            "key": self.key,
            "content": self.content,
            "provenance": self.provenance.render(),
            "aliases": list(self.aliases),
            "codes": list(self.codes),
            "tags": list(self.tags),
        }


# ---------------------------------------------------------------------------
# The index
# ---------------------------------------------------------------------------


@dataclass
class SemanticIndex:
    """A keyed, facetted collection of :class:`ContextItem`. Construction is additive."""

    items: list[ContextItem] = field(default_factory=list)
    index_version: str = INDEX_VERSION
    _by_key: dict[str, list[ContextItem]] = field(default_factory=dict, repr=False)
    _by_facet: dict[FacetKind, list[ContextItem]] = field(default_factory=dict, repr=False)
    _by_code: dict[str, list[ContextItem]] = field(default_factory=dict, repr=False)

    def add(self, item: ContextItem) -> None:
        self.items.append(item)
        for k in item.match_keys():
            self._by_key.setdefault(k.casefold(), []).append(item)
        self._by_facet.setdefault(item.facet, []).append(item)
        for code in item.codes:
            self._by_code.setdefault(code, []).append(item)

    def extend(self, items: Iterable[ContextItem]) -> None:
        for item in items:
            self.add(item)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[ContextItem]:
        return iter(self.items)

    # -- lookup ------------------------------------------------------------------

    def by_key(
        self, key: str, *, facets: Sequence[FacetKind] | None = None
    ) -> list[ContextItem]:
        hits = self._by_key.get(key.casefold(), [])
        if facets is None:
            return list(hits)
        allowed = set(facets)
        return [i for i in hits if i.facet in allowed]

    def by_facet(self, facet: FacetKind) -> list[ContextItem]:
        return list(self._by_facet.get(facet, []))

    def by_code(self, code: str) -> list[ContextItem]:
        return list(self._by_code.get(code, []))

    def facets(self) -> dict[str, int]:
        return {str(f): len(v) for f, v in sorted(self._by_facet.items())}

    def keys(self) -> list[str]:
        return sorted({i.key for i in self.items})

    # -- integrity ---------------------------------------------------------------

    def unresolved_provenance(self) -> list[ContextItem]:
        """Items whose source file could not be located. Empty is the healthy answer."""
        return [i for i in self.items if i.provenance.resolve() is None]

    def to_dict(self) -> dict[str, Any]:
        return {
            "index_version": self.index_version,
            "size": len(self.items),
            "facets": self.facets(),
        }


# ---------------------------------------------------------------------------
# Facet builders — each transcribes one real table
# ---------------------------------------------------------------------------

_TYPES_MODULE = "module:hamiltonian_lang.types"
_DIST_MODULE = "module:hamiltonian_lang.type_system.distributions"
_CHECKER_MODULE = "module:hamiltonian_lang.type_system"
_RESOLVER_MODULE = "module:hamiltonian_lang.semantics"
_EPISTEMIC_MODULE = "module:hamiltonian_lang.v1.epistemic"
_BACKEND_MODULE = "module:hamiltonian_lang.v1.backend_support"
_ADAPTER_MODULE = "module:hamiltonian_lang.improvement.diagnostics"
_CLAUDE_MD = "file:CLAUDE.md"


def _type_items() -> list[ContextItem]:
    from ..types import _SCALAR_PARENTS, SCALARS, UNIT_INTERVAL_KINDS

    prov = Provenance(_TYPES_MODULE, "_SCALAR_PARENTS")
    out: list[ContextItem] = []
    for name in SCALARS:
        parents = _SCALAR_PARENTS[name]
        parent_text = ", ".join(parents) if parents else "none (a root of the lattice)"
        note = ""
        if name in UNIT_INTERVAL_KINDS:
            others = sorted(UNIT_INTERVAL_KINDS - {name})
            note = (
                f" Values lie in [0, 1]; {name} is INCOMPARABLE with "
                f"{' and '.join(others)} — no subtyping path exists in either direction."
            )
        out.append(
            ContextItem(
                facet=FacetKind.TYPE,
                key=name,
                content=f"{name} is a scalar type. Immediate supertypes: {parent_text}.{note}",
                provenance=prov,
                codes=("HML-T440",),
                tags=("scalar",),
            )
        )
    vocab = ", ".join(SCALARS)
    out.append(
        ContextItem(
            facet=FacetKind.TYPE,
            key="__scalar_vocabulary__",
            content=(
                "The complete scalar type vocabulary is: "
                f"{vocab}. A type annotation naming anything else is HML-T440 unless it "
                "names a concept declared in the same module."
            ),
            provenance=prov,
            aliases=("scalar vocabulary", "type vocabulary"),
            codes=("HML-T440",),
            tags=("vocabulary",),
        )
    )
    return out


def _constructor_items() -> list[ContextItem]:
    prov = Provenance(_CHECKER_MODULE, "TypeChecker._known_type_names")
    specs = {
        "Vector": "Vector[T] or Vector[T, n] — a length-indexed sequence of T.",
        "Matrix": "Matrix[T, rows, cols] — a two-index array of T.",
        "Tensor": "Tensor[T, ...] — an n-index array of T.",
        "Set": "Set[T] — an unordered collection of T.",
        "Function": "Function[A -> B] — the arrow requires '->' between domain and codomain.",
        "Predicate": "Predicate[T] — a T-indexed proposition, not a Bool-valued function.",
        "RandomVariable": (
            "RandomVariable[T] — a T-valued random variable. It is NOT a Distribution[T] "
            "and it is NOT a T."
        ),
        "Distribution": (
            "Distribution[T] — a probability law over T. It is NOT a value of T."
        ),
        "Quantity": "Quantity[D] — a real number carrying the physical dimension D.",
        "Proposition": "Proposition — a truth-apt statement, not a Bool.",
        "Dimensionless": "Dimensionless — the unit of the dimension monoid.",
    }
    return [
        ContextItem(
            facet=FacetKind.CONSTRUCTOR,
            key=name,
            content=text,
            provenance=prov,
            codes=("HML-T440", "HML-P221", "HML-P223"),
            tags=("constructor",),
        )
        for name, text in specs.items()
    ]


def _signature_items() -> list[ContextItem]:
    from ..semantics import _BUILTIN_FUNCTIONS
    from ..type_system import _BUILTIN_SIGNATURES

    out: list[ContextItem] = []
    sig_prov = Provenance(_CHECKER_MODULE, "_BUILTIN_SIGNATURES")
    for name, (domain, codomain) in _BUILTIN_SIGNATURES.items():
        rendered = ", ".join(t.render() for t in domain)
        out.append(
            ContextItem(
                facet=FacetKind.FUNCTION_SIGNATURE,
                key=name,
                content=(
                    f"{name}({rendered}) : {codomain.render()} — arity {len(domain)}. "
                    "Arity is part of the signature; a call with the wrong number of "
                    "arguments denotes nothing."
                ),
                provenance=sig_prov,
                codes=("HML-T471", "HML-T426", "HML-N306"),
                tags=("builtin",),
            )
        )
    known_prov = Provenance(_RESOLVER_MODULE, "_BUILTIN_FUNCTIONS")
    known = ", ".join(sorted(_BUILTIN_FUNCTIONS))
    out.append(
        ContextItem(
            facet=FacetKind.FUNCTION_SIGNATURE,
            key="__known_functions__",
            content=(
                f"The built-in function names are: {known}. Any other callee must be a "
                "'def' with a parameter list declared in the same module, otherwise the "
                "call is HML-N306."
            ),
            provenance=known_prov,
            aliases=("known functions", "function list"),
            codes=("HML-N306",),
            tags=("vocabulary",),
        )
    )
    out.append(
        ContextItem(
            facet=FacetKind.RULE_CARD,
            key="__arity_rule__",
            content=(
                "Arity rule: a callable's signature is its ordered parameter types "
                "together with its result type. A codomain is not a signature. The number "
                "of arguments at a call site must equal the declared parameter count "
                "exactly; there are no optional or variadic parameters."
            ),
            provenance=Provenance(_CHECKER_MODULE, "CallableSignature"),
            aliases=("arity rule",),
            codes=("HML-T471", "HML-T426", "HML-T424", "HML-S605"),
            tags=("rule", "arity"),
        )
    )
    out.append(
        ContextItem(
            facet=FacetKind.RULE_CARD,
            key="__argument_position_rule__",
            content=(
                "Argument-position rule: each parameter position imposes its declared "
                "refinement type on the argument supplied there. Supplying a Real where "
                "PositiveReal is declared is rejected even though every PositiveReal is a "
                "Real — the obligation runs the other way. Repair the argument at the "
                "named position, not the signature."
            ),
            provenance=Provenance(_CHECKER_MODULE, "TypeChecker._check_call_arguments"),
            aliases=("argument position rule", "refinement rule"),
            codes=("HML-T472", "HML-T413", "HML-T402", "HML-T403", "HML-T473"),
            tags=("rule", "refinement"),
        )
    )
    return out


def _distribution_items() -> list[ContextItem]:
    from ..type_system.distributions import DISTRIBUTIONS, MISPARAMETERISATIONS

    out: list[ContextItem] = []
    spec_prov = Provenance(_DIST_MODULE, "DISTRIBUTIONS")
    wrong_by_family: dict[str, list[str]] = {}
    for wrong, (family, explanation, canonical) in MISPARAMETERISATIONS.items():
        target = family or "any family"
        wrong_by_family.setdefault(target, []).append(
            f"{wrong!r} is not a role ({explanation} canonical role: {canonical!r})"
        )

    for name, spec in DISTRIBUTIONS.items():
        roles = ", ".join(
            f"{role} : {t.render()}" for role, t in sorted(spec.roles.items())
        )
        required = ", ".join(sorted(spec.required())) or "none"
        lines = [
            f"{name} declares the roles: {roles}.",
            f"Required roles: {required}. Support: {spec.support.render()}.",
            "Roles are mandatory and positional arguments are rejected, so the role name "
            "carries the whole meaning of the argument.",
        ]
        if spec.note:
            lines.append(f"Note: {spec.note}.")
        for left, op, right, why in spec.cross_constraints:
            lines.append(f"Cross-role constraint: {left} {op} {right} — {why}.")
        confusions = wrong_by_family.get(name, []) + wrong_by_family.get("any family", [])
        if confusions:
            lines.append("Common wrong role names: " + "; ".join(sorted(confusions)) + ".")
        out.append(
            ContextItem(
                facet=FacetKind.DISTRIBUTION_ROLE,
                key=name,
                content=" ".join(lines),
                provenance=spec_prov,
                codes=("HML-T412", "HML-T414", "HML-T415", "HML-T416", "HML-T417",
                       "HML-T413", "HML-P234", "HML-P235"),
                tags=("distribution",),
            )
        )

    mis_prov = Provenance(_DIST_MODULE, "MISPARAMETERISATIONS")
    for wrong, (family, explanation, canonical) in MISPARAMETERISATIONS.items():
        scope = family or "every family"
        out.append(
            ContextItem(
                facet=FacetKind.DISTRIBUTION_ROLE,
                key=f"role:{wrong}",
                content=(
                    f"{wrong!r} is not a parameter role in {scope}. {explanation} "
                    f"The canonical role is {canonical!r}."
                ),
                provenance=mis_prov,
                aliases=(wrong,),
                codes=("HML-T415", "HML-T416"),
                tags=("distribution", "misparameterisation"),
            )
        )

    out.append(
        ContextItem(
            facet=FacetKind.RULE_CARD,
            key="__named_role_rule__",
            content=(
                "Named-role rule: every distribution argument is labelled with a role "
                "drawn from that family's own role set. Two families may use the same "
                "role name for different quantities, so a role is only meaningful "
                "relative to its family. Repair the role LABEL first; only then check "
                "whether the value inhabits the type that role demands."
            ),
            provenance=Provenance(_DIST_MODULE, "DistributionSpec.roles"),
            aliases=("named distribution roles", "role rule"),
            codes=("HML-T415", "HML-T416", "HML-T414", "HML-P232", "HML-P234"),
            tags=("rule", "role"),
        )
    )
    return out


def _coercion_items() -> list[ContextItem]:
    from ..types import _SCALAR_PARENTS, UNIT_INTERVAL_KINDS

    prov = Provenance(_TYPES_MODULE, "_SCALAR_PARENTS / is_subtype")
    out = [
        ContextItem(
            facet=FacetKind.COERCION_RULE,
            key="__subtyping_direction__",
            content=(
                "Subtyping runs upward only: every PositiveReal is a Real, so a "
                "PositiveReal may be supplied where a Real is demanded. The converse is "
                "refused — a Real is not a PositiveReal — and there is no implicit "
                "narrowing, no widening of a refinement, and no numeric coercion."
            ),
            provenance=prov,
            aliases=("subtyping", "coercion"),
            codes=("HML-T402", "HML-T403", "HML-T413", "HML-T472"),
            tags=("coercion",),
        ),
        ContextItem(
            facet=FacetKind.COERCION_RULE,
            key="__probability_incomparability__",
            content=(
                "Probability, PValue and PosteriorProbability are pairwise INCOMPARABLE. "
                "Each has NonNegativeReal as its only parent, so no coercion exists "
                "between any pair in either direction. A p-value is P(data at least this "
                "extreme | H0); a posterior is P(H0 | data). The values are numerically "
                "indistinguishable, so only the type separates them."
            ),
            provenance=prov,
            aliases=tuple(sorted(UNIT_INTERVAL_KINDS)),
            codes=("HML-T402", "HML-T403", "HML-T413", "HML-T472", "HML-T460"),
            tags=("coercion", "epistemic"),
        ),
        ContextItem(
            facet=FacetKind.COERCION_RULE,
            key="__probability_vs_positive__",
            content=(
                "Probability is not PositiveReal and PositiveReal is not Probability. "
                "0 is a probability but is not positive; 2.0 is a positive real but is "
                "not a probability. They are incomparable and meet at NonNegativeReal."
            ),
            provenance=prov,
            aliases=("Probability", "PositiveReal"),
            codes=("HML-T402", "HML-T413", "HML-T472"),
            tags=("coercion",),
        ),
    ]
    meet_note = (
        "PositiveNatural is the meet of Natural and PositiveReal. It exists so the "
        "literal 1 can inhabit both a count type and a scale parameter; Natural alone "
        "is not a subtype of PositiveReal because Natural contains 0."
    )
    if "PositiveNatural" in _SCALAR_PARENTS:
        out.append(
            ContextItem(
                facet=FacetKind.COERCION_RULE,
                key="PositiveNatural",
                content=meet_note,
                provenance=prov,
                codes=("HML-T402", "HML-T413", "HML-T472"),
                tags=("coercion",),
            )
        )
    return out


def _epistemic_items() -> list[ContextItem]:
    from ..v1.epistemic import (
        DISCHARGES_GOALS,
        PROHIBITED_COERCIONS,
        REQUIRED_CONTEXT,
        Justification,
    )

    out: list[ContextItem] = []
    j_prov = Provenance(_EPISTEMIC_MODULE, "Justification")
    grounds = ", ".join(j.value for j in Justification)
    out.append(
        ContextItem(
            facet=FacetKind.EPISTEMIC_RULE,
            key="__justification_vocabulary__",
            content=(
                f"The grounds on which a claim may be held are: {grounds}. They are "
                "deliberately NOT an ordered chain: no amount of Evidence becomes a "
                "Proof, and an Assumption is not weak evidence."
            ),
            provenance=j_prov,
            aliases=("justification", "grounds"),
            codes=("HML-E701", "HML-E702", "HML-T460"),
            tags=("epistemic", "vocabulary"),
        )
    )
    coerce_prov = Provenance(_EPISTEMIC_MODULE, "PROHIBITED_COERCIONS")
    for (src, dst), reason in sorted(
        PROHIBITED_COERCIONS.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))
    ):
        out.append(
            ContextItem(
                facet=FacetKind.EPISTEMIC_RULE,
                key=f"coercion:{src}->{dst}",
                content=f"No coercion from {src} to {dst}: {reason}",
                provenance=coerce_prov,
                aliases=(str(src), str(dst)),
                codes=("HML-E701", "HML-E702", "HML-E703", "HML-T460"),
                tags=("epistemic", "coercion"),
            )
        )
    goals_prov = Provenance(_EPISTEMIC_MODULE, "DISCHARGES_GOALS")
    discharging = sorted(str(j) for j, ok in DISCHARGES_GOALS.items() if ok)
    out.append(
        ContextItem(
            facet=FacetKind.EPISTEMIC_RULE,
            key="__discharge_rule__",
            content=(
                "Only these grounds discharge a proof goal: "
                f"{', '.join(discharging) or 'none'}. Everything else records a belief "
                "and leaves the obligation open."
            ),
            provenance=goals_prov,
            aliases=("discharge", "obligation"),
            codes=("HML-E704", "HML-E705", "HML-G801"),
            tags=("epistemic", "obligation"),
        )
    )
    ctx_prov = Provenance(_EPISTEMIC_MODULE, "REQUIRED_CONTEXT")
    for status, needed in sorted(REQUIRED_CONTEXT.items(), key=lambda kv: str(kv[0])):
        fields = ", ".join(sorted(needed)) if needed else "none"
        out.append(
            ContextItem(
                facet=FacetKind.EPISTEMIC_RULE,
                key=f"status:{status}",
                content=f"An epistemic status of {status} requires the context: {fields}.",
                provenance=ctx_prov,
                aliases=(str(status),),
                codes=("HML-E704", "HML-E706"),
                tags=("epistemic",),
            )
        )
    return out


def _diagnostic_code_items() -> list[ContextItem]:
    from ..improvement.diagnostics import VIOLATED_INVARIANT_BY_CODE

    prov = Provenance(_ADAPTER_MODULE, "VIOLATED_INVARIANT_BY_CODE")
    return [
        ContextItem(
            facet=FacetKind.DIAGNOSTIC_CODE,
            key=code,
            content=f"{code} reports a violation of the invariant: {invariant}.",
            provenance=prov,
            codes=(code,),
            tags=("invariant",),
        )
        for code, invariant in sorted(VIOLATED_INVARIANT_BY_CODE.items())
    ]


def _backend_items() -> list[ContextItem]:
    try:
        from ..v1.backend_support import SUPPORT
    except Exception:  # pragma: no cover - the module is present in this repo
        return []

    prov = Provenance(_BACKEND_MODULE, "SUPPORT")
    grouped: dict[str, list[str]] = {}
    for key, entry in SUPPORT.items():
        layer = str(getattr(entry, "layer", key[0] if isinstance(key, tuple) else key))
        backend = str(getattr(entry, "backend", key[1] if isinstance(key, tuple) else "?"))
        status = str(getattr(entry, "status", "unrecorded"))
        losses = tuple(getattr(entry, "losses", ()))
        text = f"{backend}: {status}"
        if losses:
            text += f" ({len(losses)} recorded translation loss(es))"
        grouped.setdefault(layer, []).append(text)
    return [
        ContextItem(
            facet=FacetKind.BACKEND_SUPPORT,
            key=f"layer:{layer}",
            content=(
                f"Backend support for the {layer} layer — "
                + "; ".join(sorted(entries))
                + ". A backend that cannot express a construct must report the loss via "
                "drop/approximate/weaken; it must never omit the construct silently."
            ),
            provenance=prov,
            aliases=(layer,),
            codes=("HML-B701",),
            tags=("backend",),
        )
        for layer, entries in sorted(grouped.items())
    ]


#: The prohibited conflations, transcribed from ``CLAUDE.md``. They are quoted rather than
#: paraphrased because a paraphrase of a constitutional rule is a new rule.
_CONSTITUTIONAL: tuple[tuple[str, str], ...] = (
    ("distribution_vs_value", "a Distribution[T] is not a value of T"),
    (
        "random_variable",
        "a RandomVariable[T] is not a Distribution[T] and is not a T",
    ),
    ("equality_vs_law", "'=' (equality) is not '~' (distributed as) and is not approximation"),
    (
        "implication",
        "'=>' (implication) is not correlation and is not causation",
    ),
    (
        "probability_vs_positive",
        "Probability is not PositiveReal — they are incomparable, meeting at NonNegativeReal",
    ),
)


def _constitutional_items() -> list[ContextItem]:
    prov = Provenance(_CLAUDE_MD, "Prohibited conflations")
    out = [
        ContextItem(
            facet=FacetKind.CONSTITUTIONAL_INVARIANT,
            key=f"conflation:{key}",
            content=f"Prohibited conflation: {text}. No subtyping path may be added.",
            provenance=prov,
            codes=("HML-T402", "HML-T403", "HML-T410", "HML-T428", "HML-T430"),
            tags=("constitutional",),
        )
        for key, text in _CONSTITUTIONAL
    ]
    out.append(
        ContextItem(
            facet=FacetKind.CONSTITUTIONAL_INVARIANT,
            key="rejection_is_the_product",
            content=(
                "Unresolved names, invalid scopes and incompatible types are rejected. A "
                "repair must remove the cause of the rejection, never weaken the check "
                "that produced it."
            ),
            provenance=Provenance(_CLAUDE_MD, "rule 9"),
            codes=(),
            tags=("constitutional",),
        )
    )
    return out


def _example_items(limit_per_domain: int = 4) -> list[ContextItem]:
    """Index the ``.hml`` corpus. Empty when the checkout is not on disk — never faked."""
    root = repo_root()
    if root is None:
        return []
    examples = root / "examples"
    if not examples.is_dir():
        return []
    out: list[ContextItem] = []
    for domain_dir in sorted(p for p in examples.iterdir() if p.is_dir()):
        taken = 0
        for path in sorted(domain_dir.glob("*.hml")):
            if taken >= limit_per_domain:
                break
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:  # pragma: no cover - unreadable file
                continue
            rel = path.relative_to(root).as_posix()
            out.append(
                ContextItem(
                    facet=FacetKind.EXAMPLE,
                    key=rel,
                    content=text.strip(),
                    provenance=Provenance(f"file:{rel}", "whole file"),
                    aliases=(path.stem, domain_dir.name),
                    tags=("example", domain_dir.name),
                )
            )
            taken += 1
    return out


def local_items(source: str, *, file: str = "<broken>") -> list[ContextItem]:
    """Signatures and concepts declared **by the broken program itself**.

    This is the project-specific half COCOGEN's ablation showed to matter. Retrieving the
    global built-in list for a wrong-arity call on a user ``def`` is retrieval that looks
    successful and helps nothing; the model needs *that* definition's parameter list.

    The declaration was written by the model, so showing it back is not a leak — it is
    the program's own contract, restated at the point where the call broke it.

    Parsing is best-effort. A source that does not parse yields no items rather than a
    guess, and the caller sees an empty stage, which is the truthful outcome.
    """
    try:
        from ..ast.nodes import ConceptDecl, DefineStmt
        from ..parser import parse as _parse
    except Exception:  # pragma: no cover - import failure is not a data condition
        return []
    try:
        parsed = _parse(source, file=file)
    except Exception:
        return []
    # ``parse`` returns ``(Module, DiagnosticBag)``. The bag is deliberately ignored: the
    # program is *known* broken, and a partial AST still names the declarations the call
    # site got wrong.
    module = parsed[0] if isinstance(parsed, tuple) else parsed

    prov = Provenance(f"file:{file}", "the program under repair")
    out: list[ContextItem] = []
    for st in getattr(module, "statements", []):
        if isinstance(st, DefineStmt) and st.params:
            params = ", ".join(
                f"{n} : {t.render() if t is not None else '<no declared type>'}"
                for n, t in st.params
            )
            ret = (
                st.declared_type.render() if st.declared_type is not None
                else "<inferred from the body>"
            )
            out.append(
                ContextItem(
                    facet=FacetKind.FUNCTION_SIGNATURE,
                    key=st.name,
                    content=(
                        f"This module declares {st.name}({params}) : {ret} at line "
                        f"{st.span.line} — arity {len(st.params)}. Every call to "
                        f"{st.name} must supply exactly {len(st.params)} argument(s), "
                        "each inhabiting the type declared at its position."
                    ),
                    provenance=prov,
                    codes=("HML-T471", "HML-T472", "HML-T470", "HML-N306"),
                    tags=("local", "signature"),
                )
            )
        elif isinstance(st, ConceptDecl):
            members = ", ".join(f"{m.kind} {m.name}" for m in st.members) or "no members"
            out.append(
                ContextItem(
                    facet=FacetKind.TYPE,
                    key=st.name,
                    content=(
                        f"This module declares the concept {st.name} at line "
                        f"{st.span.line} with: {members}. It may be used as a type here."
                    ),
                    provenance=prov,
                    codes=("HML-T440", "HML-N305"),
                    tags=("local", "concept"),
                )
            )
    return out


def build_index(*, include_examples: bool = True) -> SemanticIndex:
    """Assemble the whole index from the live compiler tables.

    Deterministic: two calls in one process produce equal content. Nothing here reads the
    network, and nothing calls a model.
    """
    index = SemanticIndex()
    index.extend(_type_items())
    index.extend(_constructor_items())
    index.extend(_signature_items())
    index.extend(_distribution_items())
    index.extend(_coercion_items())
    index.extend(_epistemic_items())
    index.extend(_diagnostic_code_items())
    index.extend(_backend_items())
    index.extend(_constitutional_items())
    if include_examples:
        index.extend(_example_items())
    return index
