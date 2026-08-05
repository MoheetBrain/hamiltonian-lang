"""Gate 2 — deterministic semantic checks. The gate that does the actual filtering.

FormalMATH's funnel is the design brief for this module: roughly 92% of candidates were
compiler-valid and roughly 32% survived semantic checking. Gate 1 is close to free; almost
everything that is going to be caught is caught here and at gate 3.

Every check in this module is a **pure function of the parsed module and the recorded
ground truth**. No model, no proof assistant, no sampling, no judgement. That is what
makes the drop rate reproducible: run it twice and the same items fall out.

The checks
----------
``entities_declared``       every entity the ground truth names is declared in the encoding
``kinds_match``             each entity is declared with the epistemic kind the truth says
``no_undeclared_entities``  the encoding does not smuggle in structure the truth lacks
``quantifier_order``        the prefix appears in the ground-truth order, not merely with
                            the same quantifiers
``dimensions_match``        each declared dimension equals the ground-truth dimension
``law_families``            each distribution family matches, and roles are not swapped
``conditioning``            the given-set of each law matches exactly
``answer_wellformed``       the recorded answer is checkable by the deterministic checker
``answer_not_in_prose``     the answer is not lexically recoverable from the prose
``distractor_distinct``     every distractor differs from the answer after normalisation
``conflations``             the four prohibited conflations are not committed

Why ``no_undeclared_entities`` matters as much as ``entities_declared``
----------------------------------------------------------------------
An encoding that declares everything asked for *plus* three extra parameters is not a
faithful formalisation; it is a different model that happens to contain the right one.
Checking only for omissions makes the gate one-sided and lets padding through.

Three statuses, and why there are three rather than two
-------------------------------------------------------
``PASS``/``FAIL`` are the ordinary ones. The other two are distinguished deliberately:

``NOT_APPLICABLE``  the check's precondition is structurally absent — a purely logical item
                    declares no distribution law, so ``law_families`` has nothing to
                    compare. Neutral, and does not block admission.
``INCONCLUSIVE``    the check applies and could not be decided. **Blocks admission** and
                    routes the item to the human gate.

Collapsing the two would be a real loss in either direction. Treating "no laws here" as
inconclusive blocks every logic item forever; treating "could not decide" as inapplicable
waves through exactly the items the gate was built for. The HML-EVAL-001 pilot shipped a
scorer that returned 0.0 when nothing was checkable and silently zeroed 25 problems; that
is the same confusion with a third spelling.

Because ``NOT_APPLICABLE`` is neutral, an item could in principle be admitted with almost
nothing checked. :data:`MIN_APPLICABLE_CHECKS` closes that: admission additionally requires
a minimum number of checks that actually ran. "Passed because nothing was checked" is not a
pass.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from evaluation.corpus.cso import (
    ANSWER_CLOSE,
    ANSWER_OPEN,
    AnswerSpec,
    SemanticFacts,
    check_answer,
    normalise_answer,
    parse_dimension,
)
from hamiltonian_lang import compile_source
from hamiltonian_lang.ast.nodes import (
    Declaration,
    DefineStmt,
    LawStmt,
    Module,
    Quantifier,
    walk,
)

__all__ = [
    "CheckStatus",
    "CheckResult",
    "SemanticReport",
    "run_semantic_checks",
    "PROHIBITED_CONFLATIONS",
    "MIN_APPLICABLE_CHECKS",
]

#: Admission requires at least this many checks that actually ran. Without it an item with
#: no laws, no dimensions, no quantifiers and no roles would be admitted on the strength of
#: having been looked at.
MIN_APPLICABLE_CHECKS = 4


class CheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    #: The check's precondition is structurally absent. Neutral; does not block admission.
    NOT_APPLICABLE = "not_applicable"
    #: The check applies and could not be decided. Blocks admission; goes to the human gate.
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: CheckStatus
    #: Mandatory in all three directions. A passing check with no detail is unauditable.
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": str(self.status), "detail": self.detail}


@dataclass(frozen=True)
class SemanticReport:
    item_id: str
    results: tuple[CheckResult, ...]

    @property
    def failures(self) -> tuple[CheckResult, ...]:
        return tuple(r for r in self.results if r.status is CheckStatus.FAIL)

    @property
    def inconclusive(self) -> tuple[CheckResult, ...]:
        return tuple(r for r in self.results if r.status is CheckStatus.INCONCLUSIVE)

    @property
    def not_applicable(self) -> tuple[CheckResult, ...]:
        return tuple(r for r in self.results if r.status is CheckStatus.NOT_APPLICABLE)

    @property
    def applicable(self) -> int:
        """How many checks actually ran on this item."""
        return len(self.results) - len(self.not_applicable)

    def admitted(self) -> bool:
        """Zero failures, zero inconclusive, and enough checks to have looked.

        An inconclusive check blocks admission rather than being ignored. Ignoring it is
        how a corpus ends up containing the items its own checks could not evaluate. The
        applicable-count floor blocks the opposite failure: an item on which nothing was
        checkable is not thereby verified.
        """
        return (
            not self.failures
            and not self.inconclusive
            and self.applicable >= MIN_APPLICABLE_CHECKS
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "admitted": self.admitted(),
            "applicable_checks": self.applicable,
            "failed": [r.to_dict() for r in self.failures],
            "inconclusive": [r.to_dict() for r in self.inconclusive],
            "not_applicable": [r.to_dict() for r in self.not_applicable],
            "results": [r.to_dict() for r in self.results],
        }


#: The four conflations the type system exists to prevent, restated as corpus rules. A
#: benchmark item that commits one of them teaches the wrong thing whatever its answer is.
PROHIBITED_CONFLATIONS: tuple[tuple[str, str], ...] = (
    ("distribution_is_not_value", "a Distribution[T] is not a value of T"),
    ("rv_is_not_distribution", "a RandomVariable[T] is neither a Distribution[T] nor a T"),
    ("equality_is_not_law", "= is not ~ and neither is approximation"),
    ("implication_is_not_correlation", "=> is not correlation and is not causation"),
)


def _declarations(module: Module) -> dict[str, Declaration]:
    return {s.name: s for s in module.statements if isinstance(s, Declaration)}


def _definitions(module: Module) -> dict[str, DefineStmt]:
    return {s.name: s for s in module.statements if isinstance(s, DefineStmt)}


def _laws(module: Module) -> list[LawStmt]:
    return [s for s in module.statements if isinstance(s, LawStmt)]


def _quantifier_prefix(module: Module) -> list[str]:
    """The quantifier prefix in **source order**, as ``["forall x", "exists y"]``.

    ``walk`` is a pre-order traversal, so nesting order is preserved. Sorting this list —
    or comparing it as a set — would make ``forall x . exists y`` indistinguishable from
    ``exists y . forall x``, which are different propositions with different truth values.
    """
    out: list[str] = []
    for node in walk(module):
        if isinstance(node, Quantifier):
            out.append(f"{node.kind} {node.var}")
    return out


def _check(name: str, ok: bool, on_pass: str, on_fail: str) -> CheckResult:
    return CheckResult(
        name=name,
        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
        detail=on_pass if ok else on_fail,
    )


def _na(name: str, why: str) -> CheckResult:
    """The check's precondition is structurally absent. Neutral, and says so."""
    return CheckResult(name=name, status=CheckStatus.NOT_APPLICABLE, detail=why)


def _undecided(name: str, why: str) -> CheckResult:
    """The check applies and could not be decided. Blocks admission."""
    return CheckResult(name=name, status=CheckStatus.INCONCLUSIVE, detail=why)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _entities_declared(module: Module, truth: SemanticFacts) -> CheckResult:
    if not truth.entities:
        return _na("entities_declared", "the ground truth names no entities")
    declared = set(_declarations(module)) | set(_definitions(module))
    missing = sorted(set(truth.entities) - declared)
    return _check(
        "entities_declared",
        not missing,
        f"all {len(truth.entities)} ground-truth entities are declared",
        f"the encoding never declares {missing}",
    )


def _no_undeclared_entities(module: Module, truth: SemanticFacts) -> CheckResult:
    if not truth.entities:
        return _na("no_undeclared_entities", "the ground truth names no entities")
    declared = set(_declarations(module)) | set(_definitions(module))
    extra = sorted(declared - set(truth.entities))
    return _check(
        "no_undeclared_entities",
        not extra,
        "the encoding introduces no structure the ground truth lacks",
        f"the encoding introduces {extra}, which the specification never mentions; an "
        f"encoding that contains the right model plus more is a different model",
    )


def _kinds_match(module: Module, truth: SemanticFacts) -> CheckResult:
    if not truth.declaration_kinds:
        return _na("kinds_match", "the ground truth records no declaration kinds")
    decls = _declarations(module)
    wrong: list[str] = []
    for name, expected in truth.declaration_kinds.items():
        got = decls[name].kind if name in decls else "<undeclared>"
        if got != expected:
            wrong.append(f"{name}: expected {expected}, encoded {got}")
    return _check(
        "kinds_match",
        not wrong,
        f"all {len(truth.declaration_kinds)} epistemic kinds match",
        "; ".join(wrong),
    )


def _quantifier_order(module: Module, truth: SemanticFacts) -> CheckResult:
    if not truth.quantifier_order:
        return _na("quantifier_order", "the item states no quantifier prefix")
    got = _quantifier_prefix(module)
    expected = list(truth.quantifier_order)
    if got == expected:
        return _check("quantifier_order", True, f"prefix {got} matches in order", "")
    same_multiset = sorted(got) == sorted(expected)
    reason = (
        f"the prefix is {got}, the specification says {expected}"
        + (
            " — same quantifiers, different nesting, which is a different proposition"
            if same_multiset
            else ""
        )
    )
    return CheckResult("quantifier_order", CheckStatus.FAIL, reason)


_QUANTITY = re.compile(r"^\s*Quantity\[(.*)\]\s*$", re.S)


def _dimension_vector(text: str) -> dict[str, float] | None:
    """Base-dimension exponent vector, or ``None`` if the text is not a dimension.

    Compared as **vectors**, never as strings: the type renderer canonicalises factor
    order, so ``Quantity[Mass * Length^2 / Time^2]`` prints as
    ``Quantity[Length^2 * Mass / Time^2]``. A string comparison would report a mismatch
    between an expression and its own canonical form, which is a check that fails for a
    reason having nothing to do with the item.
    """
    inner = _QUANTITY.match(text)
    return parse_dimension(inner.group(1) if inner else text)


def _dimensions_match(module: Module, truth: SemanticFacts) -> CheckResult:
    if not truth.dimensions:
        return _na("dimensions_match", "the item carries no dimensional ground truth")
    decls = _declarations(module)
    wrong: list[str] = []
    undecided: list[str] = []
    for name, dim in truth.dimensions.items():
        decl = decls.get(name)
        if decl is None or decl.declared_type is None:
            wrong.append(f"{name}: not declared with a type")
            continue
        want = _dimension_vector(dim)
        got = _dimension_vector(str(decl.declared_type))
        if want is None or got is None:
            undecided.append(f"{name}: {dim!r} or {decl.declared_type} is not a dimension")
            continue
        if want != got:
            wrong.append(f"{name}: expected {want}, encoded {got}")
    if undecided:
        return _undecided("dimensions_match", "; ".join(undecided))
    return _check(
        "dimensions_match",
        not wrong,
        f"all {len(truth.dimensions)} dimension vectors match the specification",
        "; ".join(wrong),
    )


def _law_families(module: Module, truth: SemanticFacts) -> CheckResult:
    if not truth.law_families:
        return _na("law_families", "the item declares no distribution laws")
    got = {
        law.target: (law.distribution.family if law.distribution is not None else "<none>")
        for law in _laws(module)
    }
    wrong = [
        f"{target}: expected {family}, encoded {got.get(target, '<no law>')}"
        for target, family in truth.law_families.items()
        if got.get(target) != family
    ]
    return _check(
        "law_families",
        not wrong,
        f"all {len(truth.law_families)} distribution families match",
        "; ".join(wrong),
    )


def _roles_match(module: Module, truth: SemanticFacts) -> CheckResult:
    if not truth.laws:
        return _na("roles_match", "the item records no parameter roles")
    laws = {law.target: law for law in _laws(module)}
    wrong: list[str] = []
    for target, roles in truth.laws.items():
        law = laws.get(target)
        if law is None or law.distribution is None:
            wrong.append(f"{target}: no law encoded")
            continue
        for role, symbol in roles.items():
            arg = law.distribution.arg(role)
            got = getattr(arg, "name", None) or (arg.raw if arg is not None else None)
            if got != symbol:
                wrong.append(f"{target}.{role}: expected {symbol}, encoded {got}")
    return _check(
        "roles_match",
        not wrong,
        "every parameter role is filled by the symbol the specification names",
        "; ".join(wrong),
    )


def _conditioning(module: Module, truth: SemanticFacts) -> CheckResult:
    if not truth.conditioning:
        return _na("conditioning", "the item records no conditioning sets")
    laws = {law.target: law for law in _laws(module)}
    wrong: list[str] = []
    for target, given in truth.conditioning.items():
        law = laws.get(target)
        if law is None:
            wrong.append(f"{target}: no law encoded")
            continue
        got = sorted(r.name for r in law.given)
        if got != sorted(given):
            wrong.append(f"{target}: conditioned on {got}, specification says {sorted(given)}")
    return _check(
        "conditioning",
        not wrong,
        "every law is conditioned on exactly the specified set",
        "; ".join(wrong),
    )


_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


#: Answer kinds for which the copy test is informative. Excluded kinds draw their answer
#: from a vocabulary the prose necessarily contains — a dimension answer must name base
#: dimensions the problem also names, and a ``choice`` answer is one of options the problem
#: states — so a token hit would flag every well-formed item of those kinds. Ceiling risk
#: for them is covered instead by the shallow-reader baseline in
#: ``evaluation/m3/lite/calibration.py``, which is a measurement rather than a heuristic.
_COPY_TESTABLE_KINDS = frozenset({"numeric", "exact_string", "boolean"})


def _answer_not_in_prose(
    prose: str, question: str, answer_value: Any, answer_kind: str
) -> CheckResult:
    """The answer must not be lexically recoverable from the problem statement.

    An item whose answer appears verbatim in its own prose is not measuring reasoning; it
    is measuring copying, and it will sit at ceiling for every model and every arm.
    """
    if answer_kind not in _COPY_TESTABLE_KINDS:
        return _na(
            "answer_not_in_prose",
            f"a {answer_kind} answer is drawn from vocabulary the problem statement must "
            f"contain, so a token match would not indicate copying; see the shallow-reader "
            f"baseline instead",
        )
    target = normalise_answer(str(answer_value))
    if not target:
        return _na("answer_not_in_prose", "the item records no answer value")
    haystack = f"{prose} {question}".lower()
    if target.lower() in haystack.split():
        return CheckResult(
            "answer_not_in_prose",
            CheckStatus.FAIL,
            f"the answer {target!r} appears as a token of the problem statement, so the "
            f"item can be passed by copying",
        )
    return _check("answer_not_in_prose", True, "the answer is not a token of the prose", "")


def _distractors_distinct(answer_value: Any, distractors: Sequence[str]) -> CheckResult:
    if not distractors:
        return _skip(
            "distractors_distinct",
            "the item records no distractor, so no near-miss failure can be classified",
        )
    target = normalise_answer(str(answer_value))
    clashing = [d for d in distractors if normalise_answer(d) == target]
    return _check(
        "distractors_distinct",
        not clashing,
        f"all {len(distractors)} distractors differ from the answer",
        f"distractor(s) {clashing} normalise to the answer, so a wrong reading would be "
        f"scored correct",
    )


def _reference_round_trip(module: Module) -> CheckResult:
    """Render the encoding back to surface syntax, re-read it, compare canonical hashes.

    Applies to every item, which is why it is here rather than in a backend test. An
    encoding whose meaning is not stable under the language's own render/parse cycle is not
    a usable answer key: the arm that is scored against it would be scored against whichever
    of the two readings the pipeline happened to produce.
    """
    from hamiltonian_lang.backends.canonical import content_hash
    from hamiltonian_lang.backends.hml import render_module

    before = content_hash(module)
    rendered = render_module(module)
    again = compile_source(rendered, file="<round-trip>")
    if not again.ok():
        codes = ", ".join(d.code for d in again.diagnostics.errors[:3])
        return CheckResult(
            "reference_round_trip",
            CheckStatus.FAIL,
            f"the encoding does not survive its own surface rendering ({codes})",
        )
    after = content_hash(again.module)
    return _check(
        "reference_round_trip",
        before == after,
        "the canonical object is recovered unchanged after render and re-parse",
        f"the canonical hash changed under render/re-parse: {before[:12]} -> {after[:12]}",
    )


def _answer_wellformed(answer: AnswerSpec | None) -> CheckResult:
    """The recorded answer must be accepted by the deterministic checker that will score it.

    An answer key the scorer cannot recognise scores every response wrong, which looks
    exactly like a hard item. The HML-EVAL-001 scorer's silent-zero defect is the same
    failure one layer down, and this check is what makes it impossible here.
    """
    if answer is None:
        return _undecided("answer_wellformed", "the item records no answer specification")
    # A role_map is scored as JSON, so the self-probe must be JSON. Python's dict repr uses
    # single quotes and would fail the checker for a formatting reason rather than a
    # semantic one -- which is itself worth knowing, and is why the probe is explicit.
    rendered = (
        json.dumps(answer.value, sort_keys=True)
        if answer.kind == "role_map"
        else str(answer.value)
    )
    correct, normalised = check_answer(answer, f"{ANSWER_OPEN}{rendered}{ANSWER_CLOSE}")
    if not correct:
        return CheckResult(
            "answer_wellformed",
            CheckStatus.FAIL,
            f"the deterministic checker does not accept the item's own recorded answer "
            f"{answer.value!r} (normalised to {normalised!r}) for kind {answer.kind}",
        )
    if answer.kind == "choice" and str(answer.value) not in answer.options:
        return CheckResult(
            "answer_wellformed",
            CheckStatus.FAIL,
            f"the recorded choice {answer.value!r} is not among the options {answer.options}",
        )
    if not answer.justification.strip():
        return CheckResult(
            "answer_wellformed",
            CheckStatus.FAIL,
            "the answer carries no justification, so a wrong ground truth would be unauditable",
        )
    return _check(
        "answer_wellformed",
        True,
        f"the {answer.kind} answer is accepted by the deterministic checker and justified",
        "",
    )


def _conflations(module: Module, truth: SemanticFacts) -> CheckResult:
    """None of the four prohibited conflations is committed by the encoding.

    The checkable half: a symbol the ground truth types as a ``Distribution`` or a
    ``RandomVariable`` must not be declared as a bare scalar, and vice versa. The compiler
    enforces the lattice, but it cannot know which side of it the *specification* meant —
    that is what the ground truth is for.
    """
    if not truth.entities:
        return _na("conflations", "the ground truth records no entity types")
    decls = _declarations(module)
    wrong: list[str] = []
    for name, expected_type in truth.entities.items():
        decl = decls.get(name)
        if decl is None or decl.declared_type is None:
            continue
        got = str(decl.declared_type)
        for marker in ("Distribution", "RandomVariable"):
            if (marker in expected_type) != (marker in got):
                wrong.append(
                    f"{name}: specification says {expected_type}, encoding says {got} — "
                    f"{marker} appears on one side only"
                )
    return _check(
        "conflations",
        not wrong,
        "no Distribution/RandomVariable/value conflation in the encoding",
        "; ".join(wrong),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_semantic_checks(
    item_id: str,
    module: Module,
    truth: SemanticFacts,
    *,
    prose: str = "",
    question: str = "",
    answer: AnswerSpec | None = None,
    distractors: Sequence[str] = (),
    extra: Mapping[str, CheckResult] | None = None,
) -> SemanticReport:
    """Run every deterministic check and return all of them, passes included.

    Passes are retained because a report listing only failures cannot be distinguished
    from a report produced by a check suite that never ran.
    """
    answer_value = answer.value if answer is not None else ""
    answer_kind = answer.kind if answer is not None else "exact_string"
    results: list[CheckResult] = [
        _entities_declared(module, truth),
        _no_undeclared_entities(module, truth),
        _kinds_match(module, truth),
        _quantifier_order(module, truth),
        _dimensions_match(module, truth),
        _law_families(module, truth),
        _roles_match(module, truth),
        _conditioning(module, truth),
        _conflations(module, truth),
        _reference_round_trip(module),
        _answer_wellformed(answer),
        _answer_not_in_prose(prose, question, answer_value, answer_kind),
        _distractors_distinct(answer_value, distractors),
    ]
    if extra:
        results.extend(extra.values())
    return SemanticReport(item_id=item_id, results=tuple(results))
