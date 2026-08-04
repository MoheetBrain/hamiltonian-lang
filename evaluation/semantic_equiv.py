"""Semantic-equivalence evaluation and failure taxonomy — HML-EVAL-001 §8.

A Hamiltonian program can be internally valid and still mistranslate the problem. Parser
acceptance is therefore **not** evidence of anything on its own, and the directive
forbids claiming a language advantage from it.

This module compares

    original problem  ->  canonical semantic object     (ground truth, hand-authored)
    model output      ->  parsed semantic object        (recovered by the compiler)

on entities, types, roles, constraints, quantifier order, dependencies, probability laws
and the requested objective, and classifies every output into exactly one bucket.

No model is called here. Where a comparison is genuinely undecidable the case is marked
``NEEDS_REVIEW`` rather than guessed — blinded human review is the fallback, per §8.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import (
    Declaration,
    DefineStmt,
    LawStmt,
    ObjectiveStmt,
    ProveStmt,
    Quantifier,
    RequireStmt,
)

from .corpus.cso import CanonicalSemanticObject

__all__ = [
    "FailureClass", "SemanticComparison", "extract_block", "compare_semantics",
    "classify",
]

FailureClass = Literal[
    "correct_solution",
    "syntax_failure",
    "type_failure",
    "semantic_mistranslation",
    "invalid_transformation",
    "correct_reasoning_wrong_answer",
    "unsupported_construct",
    "verifier_failure",
    "no_encoding_produced",
    "needs_review",
]


@dataclass
class SemanticComparison:
    """Per-facet agreement between ground truth and the recovered object."""

    parsed: bool = False
    diagnostics: list[str] = field(default_factory=list)
    entities: tuple[int, int] = (0, 0)          # (matched, expected)
    types: tuple[int, int] = (0, 0)
    declaration_kinds: tuple[int, int] = (0, 0)
    law_families: tuple[int, int] = (0, 0)
    roles: tuple[int, int] = (0, 0)
    conditioning: tuple[int, int] = (0, 0)
    quantifier_order: tuple[int, int] = (0, 0)
    objective: tuple[int, int] = (0, 0)
    notes: list[str] = field(default_factory=list)

    def _facets(self) -> list[tuple[str, tuple[int, int]]]:
        return [
            ("entities", self.entities), ("types", self.types),
            ("declaration_kinds", self.declaration_kinds),
            ("law_families", self.law_families), ("roles", self.roles),
            ("conditioning", self.conditioning),
            ("quantifier_order", self.quantifier_order), ("objective", self.objective),
        ]

    def score(self) -> float:
        """Fraction of checkable facets recovered. Facets with nothing to check are
        excluded rather than counted as free marks."""
        num = sum(m for _, (m, e) in self._facets() if e)
        den = sum(e for _, (m, e) in self._facets() if e)
        return (num / den) if den else 0.0

    def exact(self) -> bool:
        return all(m == e for _, (m, e) in self._facets() if e)

    def to_dict(self) -> dict:
        return {
            "parsed": self.parsed,
            "diagnostics": self.diagnostics[:8],
            "score": round(self.score(), 4),
            "exact": self.exact(),
            **{k: list(v) for k, v in self._facets()},
            "notes": self.notes[:8],
        }


_FENCE = re.compile(
    r"```[ \t]*(hml|hamiltonian|stan|lean|triples|text)?[ \t]*\r?\n(.*?)```", re.S | re.I
)


def extract_block(text: str, kinds: tuple[str, ...]) -> str | None:
    """Pull the first fenced block whose tag is in ``kinds``.

    Falls back to any untagged fence, because a model that omits the tag has made a
    formatting error, not a mathematical one, and the two must be measured separately.
    """
    if not text:
        return None
    tagged: list[tuple[str, str]] = [
        ((m.group(1) or "").lower(), m.group(2)) for m in _FENCE.finditer(text)
    ]
    for want in kinds:
        for tag, body in tagged:
            if tag == want:
                return body.strip()
    for tag, body in tagged:
        if tag in ("", "text"):
            return body.strip()
    return None


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s)).lower()


def _quantifier_chain(module) -> list[str]:
    """Outermost-first quantifier kinds across every proposition in the module."""
    chain: list[str] = []
    for st in module.statements:
        if isinstance(st, (RequireStmt, ProveStmt)):
            node = st.proposition
            while isinstance(node, Quantifier):
                chain.append(node.kind)
                node = node.body
    return chain


def compare_semantics(
    cso: CanonicalSemanticObject, hml_text: str | None
) -> SemanticComparison:
    """Compare a model-produced HML encoding against the ground-truth facts.

    **Every comparison here is name-independent.** Module-level declaration names are
    binders, not roles (D-017): an encoding that writes `n` and `p` where the ground truth
    writes `trials` and `prob` is not a mistranslation, it is a renaming. Scoring names
    would systematically understate encoding accuracy and would be measuring spelling.

    What *is* scored is structure that survives renaming:

    * the multiset of declared types and declaration kinds;
    * the distribution family of each law;
    * for each role, the **type and declaration kind of the symbol filling it** — so
      swapping `location` and `scale` fillers is caught, while renaming them is not;
    * the arity of each conditioning set;
    * quantifier nesting order as a sequence;
    * objective direction.

    Name agreement is recorded separately in ``notes`` as information, never scored.
    """
    cmp = SemanticComparison()
    if not hml_text or not hml_text.strip():
        cmp.notes.append("no encoding produced")
        return cmp

    result = compile_source(hml_text, f"{cso.id}#model")
    cmp.diagnostics = [d.code for d in result.diagnostics.errors]
    cmp.parsed = result.ok()
    module = result.module
    facts = cso.semantics

    decls: dict[str, object] = {
        s.name: s for s in module.statements if isinstance(s, (Declaration, DefineStmt))
    }

    def kind_of(d) -> str:
        return getattr(d, "kind", "def")

    def type_of(d) -> str:
        t = getattr(d, "declared_type", None)
        return _norm(t.render()) if t is not None else "?"

    # -- entities: count only. Which names were chosen is not part of meaning.
    if facts.entities:
        cmp.entities = (min(len(decls), len(facts.entities)), len(facts.entities))
        overlap = {_norm(k) for k in facts.entities} & {_norm(k) for k in decls}
        cmp.notes.append(
            f"name agreement (unscored): {len(overlap)}/{len(facts.entities)}"
        )

    # -- types: compare as multisets, so renaming is invisible and structure is not.
    if facts.entities:
        from collections import Counter

        want = Counter(_norm(v) for v in facts.entities.values())
        got = Counter(type_of(d) for d in decls.values())
        matched = sum((want & got).values())
        cmp.types = (matched, sum(want.values()))

    if facts.declaration_kinds:
        from collections import Counter

        want = Counter(facts.declaration_kinds.values())
        got = Counter(kind_of(d) for d in decls.values())
        cmp.declaration_kinds = (sum((want & got).values()), sum(want.values()))

    laws = [s for s in module.statements if isinstance(s, LawStmt)]

    # -- law families: a multiset comparison, name-independent by construction.
    if facts.law_families:
        from collections import Counter

        want = Counter(_norm(v) for v in facts.law_families.values())
        got = Counter(_norm(s.distribution.family) for s in laws if s.distribution)
        cmp.law_families = (sum((want & got).values()), sum(want.values()))

    # -- roles: match each ground-truth law to a model law of the same family, then
    #    compare the TYPE and DECLARATION KIND of each role filler. This catches a
    #    location/scale swap (different types or different kinds) while ignoring names.
    if facts.laws:
        matched = expected = 0
        used: set[int] = set()
        for target, roles in facts.laws.items():
            want_family = _norm(facts.law_families.get(target, ""))
            candidate = None
            for idx, law in enumerate(laws):
                if idx in used or law.distribution is None:
                    continue
                if not want_family or _norm(law.distribution.family) == want_family:
                    candidate = (idx, law)
                    break
            if candidate is not None:
                used.add(candidate[0])
            for role, filler in roles.items():
                expected += 1
                if candidate is None:
                    continue
                arg = candidate[1].distribution.arg(role)
                if arg is None:
                    continue
                from hamiltonian_lang.backends.hml import render_expr

                got_text = _norm(render_expr(arg))
                # A literal filler is compared by value; a symbolic filler by the type
                # and kind of the symbol it names, which is renaming-invariant.
                if re.fullmatch(r"-?\d+(?:\.\d+)?", _norm(filler)):
                    if got_text == _norm(filler):
                        matched += 1
                    continue
                got_decl = next(
                    (d for n, d in decls.items() if _norm(n) == got_text), None
                )
                truth_type = _norm(cso.semantics.entities.get(filler, ""))
                truth_kind = cso.semantics.declaration_kinds.get(filler, "")
                if got_decl is None:
                    continue
                type_ok = (not truth_type) or type_of(got_decl) == truth_type
                kind_ok = (not truth_kind) or kind_of(got_decl) == truth_kind
                if type_ok and kind_ok:
                    matched += 1
        cmp.roles = (matched, expected)

    # -- conditioning: compare arity, which is renaming-invariant.
    if facts.conditioning:
        matched = expected = 0
        want_sizes = sorted(len(v) for v in facts.conditioning.values())
        got_sizes = sorted(len(law.given) for law in laws if law.given)
        expected = len(want_sizes)
        for w in want_sizes:
            if w in got_sizes:
                got_sizes.remove(w)
                matched += 1
        cmp.conditioning = (matched, expected)

    if facts.quantifier_order:
        want = [q.split()[0] for q in facts.quantifier_order if q.split()[0] != "not"]
        got = _quantifier_chain(module)
        if len(got) != len(want):
            cmp.notes.append(f"quantifier depth {len(got)} vs expected {len(want)}")
            cmp.quantifier_order = (0, len(want))
        else:
            # Order is the entire point: compare as a sequence, not as a set.
            matched = sum(1 for a, b in zip(want, got, strict=True) if a == b)
            cmp.quantifier_order = (matched, len(want))

    if facts.objective:
        objs = [s for s in module.statements if isinstance(s, ObjectiveStmt)]
        want_dir = "minimise" if "minimis" in facts.objective else "maximise"
        cmp.objective = (1 if objs and objs[0].direction == want_dir else 0, 1)

    return cmp


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

_SYNTAX_PREFIXES = ("HML-L", "HML-P")
_TYPE_PREFIXES = ("HML-T", "HML-D")
_SEMANTIC_PREFIXES = ("HML-N", "HML-S")


def classify(
    *,
    answer_correct: bool,
    formal_arm: bool,
    encoding_present: bool,
    comparison: SemanticComparison | None,
    completion_ok: bool,
) -> FailureClass:
    """Assign exactly one bucket. Deterministic; never calls a model.

    Ordering matters. An output whose *answer* is right but whose *encoding* mistranslates
    the problem is still recorded as a mistranslation for the encoding metric, but its
    answer is scored correct — the two are reported separately and never merged.
    """
    if not completion_ok:
        return "verifier_failure"

    if answer_correct:
        return "correct_solution"

    if not formal_arm:
        # Prose arms produce no encoding, so the only distinction available without a
        # model judging is right-answer versus wrong-answer.
        return "correct_reasoning_wrong_answer"

    if not encoding_present:
        return "no_encoding_produced"

    if comparison is None:
        return "needs_review"

    codes = comparison.diagnostics
    if any(c.startswith(_SYNTAX_PREFIXES) for c in codes):
        return "syntax_failure"
    if any(c.startswith(_TYPE_PREFIXES) for c in codes):
        return "type_failure"
    if any(c.startswith(_SEMANTIC_PREFIXES) for c in codes):
        return "unsupported_construct" if "HML-T412" in codes else "semantic_mistranslation"

    if comparison.parsed and not comparison.exact():
        return "semantic_mistranslation"
    if comparison.parsed and comparison.exact():
        # Encoded the problem correctly and still got the answer wrong: the failure is in
        # the reasoning over the encoding, not in the encoding.
        return "correct_reasoning_wrong_answer"
    return "needs_review"
