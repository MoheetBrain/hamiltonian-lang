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
    LogicalOp,
    ObjectiveStmt,
    ProveStmt,
    Quantifier,
    Ref,
    RequireStmt,
    UnaryOp,
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
    dimensions: tuple[int, int] = (0, 0)
    notes: list[str] = field(default_factory=list)

    def _facets(self) -> list[tuple[str, tuple[int, int]]]:
        return [
            ("entities", self.entities), ("types", self.types),
            ("declaration_kinds", self.declaration_kinds),
            ("law_families", self.law_families), ("roles", self.roles),
            ("conditioning", self.conditioning),
            ("quantifier_order", self.quantifier_order), ("objective", self.objective),
            ("dimensions", self.dimensions),
        ]

    def score(self) -> float | None:
        """Fraction of checkable facets recovered, or None when nothing is checkable.

        Returning 0.0 for "nothing to check" would be a serious bias: the dimensional
        problems declare no entities, so every Hamiltonian encoding of them would have
        scored zero regardless of quality. None is excluded from aggregates instead.
        """
        num = sum(m for _, (m, e) in self._facets() if e)
        den = sum(e for _, (m, e) in self._facets() if e)
        return (num / den) if den else None

    def exact(self) -> bool:
        return all(m == e for _, (m, e) in self._facets() if e)

    def to_dict(self) -> dict:
        return {
            "parsed": self.parsed,
            "diagnostics": self.diagnostics[:8],
            "score": (round(self.score(), 4) if self.score() is not None else None),
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
    """Outermost-first quantifier kinds across every proposition in the module.

    Follows one level of indirection: `def p := forall …` followed by `prove p` is a
    legitimate encoding and its quantifier structure must be found, not missed.
    """
    defs = {
        s.name: s.body for s in module.statements
        if isinstance(s, DefineStmt) and not s.params
    }

    def walk_chain(node) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        while True:
            if isinstance(node, Ref) and node.name in defs and node.name not in seen:
                seen.add(node.name)
                node = defs[node.name]
                continue
            # Negation placement is part of the structure: `not forall x . P` and
            # `forall x . not P` are different statements, so the marker is recorded in
            # sequence rather than stripped.
            if isinstance(node, UnaryOp) and node.op == "not":
                out.append("not")
                node = node.operand
                continue
            if isinstance(node, Quantifier):
                out.append(node.kind)
                node = node.body
                continue
            if isinstance(node, LogicalOp):
                # `(exists …) and (forall …)` -- take the first branch that quantifies
                left = walk_chain(node.left)
                return out + (left or walk_chain(node.right))
            return out

    chain: list[str] = []
    for st in module.statements:
        if isinstance(st, (RequireStmt, ProveStmt)):
            chain.extend(walk_chain(st.proposition))
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
        """The declared type, reconstructing a function type for a parameterised def.

        `def F(w : Real) : Real := ...` carries Real as its *return* type. Comparing that
        against a ground truth of Function[Real -> Real] would mark a correct encoding
        wrong.
        """
        t = getattr(d, "declared_type", None)
        params = getattr(d, "params", None)
        if params:
            dom = " * ".join(
                (pt.render() if pt is not None else "?") for _, pt in params
            )
            cod = t.render() if t is not None else "?"
            return _norm(f"Function[{dom} -> {cod}]")
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
        want = [q.split()[0] for q in facts.quantifier_order]
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

    # Dimensional problems declare no entities, so without this facet they would have
    # nothing checkable at all and would be excluded from encoding accuracy entirely.
    if facts.dimensions:
        from hamiltonian_lang.ast.nodes import CheckStmt
        from hamiltonian_lang.types import dimension_of

        want = {
            _dimension_key(v) for v in facts.dimensions.values() if _dimension_key(v)
        }
        got: set[frozenset] = set()
        for st in module.statements:
            if isinstance(st, CheckStmt) and st.subject is not None:
                d = dimension_of(st.subject.type_) if st.subject.type_ else None
                if d is not None:
                    got.add(frozenset(d.as_dict().items()))
            if isinstance(st, (Declaration, DefineStmt)):
                t = getattr(st, "declared_type", None)
                if t is not None:
                    d = dimension_of(t)
                    if d is not None and not d.is_dimensionless():
                        got.add(frozenset(d.as_dict().items()))
        cmp.dimensions = (len(want & got), len(want))

    return cmp


def _dimension_key(text: str) -> frozenset | None:
    """Parse a ground-truth dimension string into a comparable exponent set."""
    from fractions import Fraction

    from .corpus.cso import parse_dimension

    parsed = parse_dimension(text)
    if parsed is None:
        return None
    return frozenset((k, Fraction(v).limit_denominator(12)) for k, v in parsed.items())


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
