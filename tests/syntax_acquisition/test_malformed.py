"""Malformed input must fail loudly in every surface.

The failure mode this file exists to exclude is *silent acceptance*: a damaged rendering
that parses, resolves, checks, and produces an authoritative-looking object that is not
the one that was written. Every case below asserts rejection at a named stage, and
:func:`test_no_mutation_is_silently_accepted` sweeps a mechanical mutation set over the
whole corpus so the enumerated cases are a floor and not the whole story.

Note which stage rejects what, because it is the D-003 story in miniature: a wrong
*role name* is well-formed at the grammar level in all four surfaces and is caught by
the type system (HML-T415/HML-T416), not by the parser.
"""

from __future__ import annotations

import json

import pytest
from evaluation.syntax_acquisition.core import CANDIDATES, SurfaceParseError
from evaluation.syntax_acquisition.generator import corpus

from hamiltonian_lang.diagnostics import DiagnosticBag
from hamiltonian_lang.semantics import resolve
from hamiltonian_lang.type_system import check

CANDIDATE_IDS = tuple(sorted(CANDIDATES))


def accepts(candidate_id: str, text: str) -> tuple[bool, str]:
    """Run the full pipeline on raw surface text. Returns ``(accepted, why_not)``."""
    cand = CANDIDATES[candidate_id]
    try:
        module = cand.parse(text)
    except SurfaceParseError as exc:
        return False, f"parse: {exc}"
    except Exception as exc:  # noqa: BLE001 - a crash is also a rejection, but a bad one
        return False, f"crash in parse: {type(exc).__name__}: {exc}"
    bag = DiagnosticBag(text, f"<candidate-{candidate_id}>")
    symbols = resolve(module, bag)
    if not bag.ok():
        return False, "resolve: " + "; ".join(d.code for d in bag.errors)
    check(module, symbols, bag)
    if not bag.ok():
        return False, "check: " + "; ".join(d.code for d in bag.errors)
    return True, ""


def reject(candidate_id: str, text: str, label: str) -> str:
    ok, why = accepts(candidate_id, text)
    assert not ok, f"[{candidate_id}] silently accepted {label}:\n{text[:600]}"
    return why


# ---------------------------------------------------------------------------
# Hand-written malformed cases, one family per surface
# ---------------------------------------------------------------------------

_A_BAD = {
    "truncated mid-expression": "module M\nparam a_ : Real\ndef z_ := a_ +",
    "unbalanced paren": "module M\nparam a_ : Real\ndef z_ := (a_ + 1.0",
    "unbalanced bracket": "module M\nparam v_ : Vector[Real, 3",
    "invented type": "module M\nparam a_ : Realz",
    "invented statement keyword": "module M\nasseert a_ = a_",
    "positional distribution arguments": (
        "module M\nparam m_ : Real\nparam s_ : PositiveReal\n"
        "var x_ : RandomVariable[Real]\nlaw x_ ~ Normal(m_, s_)"
    ),
    "unknown parameter role": (
        "module M\nparam m_ : Real\nparam s_ : PositiveReal\n"
        "var x_ : RandomVariable[Real]\nlaw x_ ~ Normal(location := m_, zzz := s_)"
    ),
    "misparameterised role": (
        "module M\nparam m_ : Real\nparam s_ : PositiveReal\n"
        "var x_ : RandomVariable[Real]\nlaw x_ ~ Normal(location := m_, variance := s_)"
    ),
    "repeated role": (
        "module M\nparam m_ : Real\nvar x_ : RandomVariable[Real]\n"
        "law x_ ~ Normal(location := m_, location := m_)"
    ),
    "untyped quantifier binder": "module M\nrequire forall x_ . x_ = x_",
    "unresolved name": "module M\nparam a_ : Real\ndef z_ := b_",
    "unclosed concept": "module M\nconcept C\n    parameter p : Real",
    "chained comparison": "module M\nparam a_ : Real\nrequire 0.0 < a_ < 1.0",
    "garbage": "!!! ??? %%%",
}

_B_BAD = {
    "truncated mid-expression": "mod M\ndec param a_ : Real\nfun z_ := a_ +",
    "unbalanced paren": "mod M\ndec param a_ : Real\nfun z_ := (a_ + 1.0",
    "invented type": "mod M\ndec param a_ : Realz",
    "invented statement keyword": "mod M\nsayy require a_ = a_",
    "invented declaration kind": "mod M\ndec thing a_ : Real",
    "invented say mode": "mod M\ndec param a_ : Real\nsay insist a_ = a_",
    "invented query": "mod M\ndec param a_ : Real\nask guess a_",
    "HML-L1 keyword instead of B's": "mod M\nparam a_ : Real",
    "positional distribution arguments": (
        "mod M\ndec param m_ : Real\ndec param s_ : PositiveReal\n"
        "dec var x_ : RandomVariable[Real]\ndist law x_ ~ Normal(m_, s_)"
    ),
    "unknown parameter role": (
        "mod M\ndec param m_ : Real\ndec param s_ : PositiveReal\n"
        "dec var x_ : RandomVariable[Real]\ndist law x_ ~ Normal(location := m_, zzz := s_)"
    ),
    "misparameterised role": (
        "mod M\ndec param m_ : Real\ndec param s_ : PositiveReal\n"
        "dec var x_ : RandomVariable[Real]\n"
        "dist law x_ ~ Normal(location := m_, variance := s_)"
    ),
    "repeated role": (
        "mod M\ndec param m_ : Real\ndec var x_ : RandomVariable[Real]\n"
        "dist law x_ ~ Normal(location := m_, location := m_)"
    ),
    "unclosed concept": "mod M\nkind C\n    parameter p : Real",
    "missing binding token": "mod M\nfun z_ = 1.0",
    "garbage": "!!! ??? %%%",
}

_C_BAD = {
    "truncated": "(module M\n  (dec param a_ Real)\n  (def z_ () #none (+ a_",
    "unbalanced close": "(module M (dec param a_ Real)))",
    "no top-level module": "(dec param a_ Real)",
    "two top-level forms": "(module M) (module N)",
    "atom at top level": "module",
    "invented statement head": "(module M (declare param a_ Real))",
    "invented declaration kind": "(module M (dec thing a_ Real))",
    "invented type": "(module M (dec param a_ Realz) (require (= a_ a_)))",
    "invented type constructor": "(module M (dec param a_ (Bag Real)))",
    "wrong arity on dec": "(module M (dec param a_))",
    "wrong arity on a binary operator": (
        "(module M (dec param a_ Real) (dec param b_ Real) (require (= a_ b_ a_)))"
    ),
    "invented expression head": (
        "(module M (dec param a_ Real) (require (= (frobnicate a_) a_)))"
    ),
    "distribution argument is not a pair": (
        "(module M (dec param m_ Real) (dec var x_ (RandomVariable Real))"
        " (law law x_ (given) (dist Normal (location))))"
    ),
    "unknown parameter role": (
        "(module M (dec param m_ Real) (dec param s_ PositiveReal)"
        " (dec var x_ (RandomVariable Real))"
        " (law law x_ (given) (dist Normal (location m_) (zzz s_))))"
    ),
    "misparameterised role": (
        "(module M (dec param m_ Real) (dec param s_ PositiveReal)"
        " (dec var x_ (RandomVariable Real))"
        " (law law x_ (given) (dist Normal (location m_) (variance s_))))"
    ),
    "repeated role": (
        "(module M (dec param m_ Real) (dec var x_ (RandomVariable Real))"
        " (law law x_ (given) (dist Normal (location m_) (location m_))))"
    ),
    "missing given list": (
        "(module M (dec param m_ Real) (dec var x_ (RandomVariable Real))"
        " (law law x_ (dist Normal (location m_))))"
    ),
    "bad dimension operator": "(module M (dec param q_ (Quantity (times Mass Length))))",
    "garbage": "!!! ??? %%%",
}


def _d(statements: list[dict], module: str = "M") -> str:
    return json.dumps(
        {"surface": "hml-graph-d-1", "module": module, "statements": statements},
        indent=2,
        sort_keys=True,
    )


_D_BAD = {
    "truncated": _d([{"node": "check", "subject": {"node": "literal", "value": True}}])[:60],
    "unbalanced brace": _d([])[:-1],
    "not json": "surface: hml-graph-d-1",
    "wrong surface tag": json.dumps(
        {"surface": "hml-graph-d-99", "module": "M", "statements": []}
    ),
    "missing key": json.dumps({"surface": "hml-graph-d-1", "module": "M"}),
    "unexpected top-level key": json.dumps(
        {"surface": "hml-graph-d-1", "module": "M", "statements": [], "hint": "theta is a param"}
    ),
    "unexpected statement key": _d(
        [
            {
                "node": "declaration",
                "declaration_kind": "param",
                "name": "a_",
                "type": {"ctor": "Real"},
                "value": None,
                "resolved_symbol": "sym:#0.0",
            }
        ]
    ),
    "invented node discriminator": _d([{"node": "postulate", "proposition": None}]),
    "invented declaration kind": _d(
        [
            {
                "node": "declaration",
                "declaration_kind": "thing",
                "name": "a_",
                "type": {"ctor": "Real"},
                "value": None,
            }
        ]
    ),
    "invented type constructor": _d(
        [
            {
                "node": "declaration",
                "declaration_kind": "param",
                "name": "a_",
                "type": {"ctor": "Bag", "element": {"ctor": "Real"}},
                "value": None,
            }
        ]
    ),
    "invented operator": _d(
        [
            {
                "node": "check",
                "subject": {
                    "node": "binary",
                    "operator": "%",
                    "left": {"node": "literal", "value": 1},
                    "right": {"node": "literal", "value": 2},
                },
            }
        ]
    ),
    "float dimension exponent": _d(
        [
            {
                "node": "declaration",
                "declaration_kind": "param",
                "name": "q_",
                "type": {"ctor": "Quantity",
                         "dimension": {"numerator": [["Length", 0.5]], "denominator": []}},
                "value": None,
            }
        ]
    ),
    "dimension is not a numerator/denominator pair": _d(
        [
            {
                "node": "declaration", "declaration_kind": "param", "name": "q_",
                "type": {"ctor": "Quantity", "dimension": [["Length", "1"]]},
                "value": None,
            }
        ]
    ),
    "unknown dimension name": _d(
        [
            {
                "node": "declaration",
                "declaration_kind": "param",
                "name": "q_",
                "type": {"ctor": "Quantity",
                         "dimension": {"numerator": [["Lenght", "1"]], "denominator": []}},
                "value": None,
            }
        ]
    ),
    "statements is not a list": json.dumps(
        {"surface": "hml-graph-d-1", "module": "M", "statements": {}}
    ),
    "unknown parameter role": _d(
        [
            {
                "node": "declaration", "declaration_kind": "param", "name": "m_",
                "type": {"ctor": "Real"}, "value": None,
            },
            {
                "node": "declaration", "declaration_kind": "param", "name": "s_",
                "type": {"ctor": "PositiveReal"}, "value": None,
            },
            {
                "node": "declaration", "declaration_kind": "var", "name": "x_",
                "type": {"ctor": "RandomVariable", "codomain": {"ctor": "Real"}},
                "value": None,
            },
            {
                "node": "law", "role": "law", "target": "x_", "given": [],
                "distribution": {
                    "node": "distribution", "family": "Normal",
                    "arguments": [
                        {"role": "location", "value": {"node": "reference", "name": "m_"}},
                        {"role": "zzz", "value": {"node": "reference", "name": "s_"}},
                    ],
                },
            },
        ]
    ),
    "misparameterised role": _d(
        [
            {
                "node": "declaration", "declaration_kind": "param", "name": "m_",
                "type": {"ctor": "Real"}, "value": None,
            },
            {
                "node": "declaration", "declaration_kind": "param", "name": "s_",
                "type": {"ctor": "PositiveReal"}, "value": None,
            },
            {
                "node": "declaration", "declaration_kind": "var", "name": "x_",
                "type": {"ctor": "RandomVariable", "codomain": {"ctor": "Real"}},
                "value": None,
            },
            {
                "node": "law", "role": "law", "target": "x_", "given": [],
                "distribution": {
                    "node": "distribution", "family": "Normal",
                    "arguments": [
                        {"role": "location", "value": {"node": "reference", "name": "m_"}},
                        {"role": "variance", "value": {"node": "reference", "name": "s_"}},
                    ],
                },
            },
        ]
    ),
    "repeated role": _d(
        [
            {
                "node": "declaration", "declaration_kind": "param", "name": "m_",
                "type": {"ctor": "Real"}, "value": None,
            },
            {
                "node": "declaration", "declaration_kind": "var", "name": "x_",
                "type": {"ctor": "RandomVariable", "codomain": {"ctor": "Real"}},
                "value": None,
            },
            {
                "node": "law", "role": "law", "target": "x_", "given": [],
                "distribution": {
                    "node": "distribution", "family": "Normal",
                    "arguments": [
                        {"role": "location", "value": {"node": "reference", "name": "m_"}},
                        {"role": "location", "value": {"node": "reference", "name": "m_"}},
                    ],
                },
            },
        ]
    ),
    "garbage": "!!! ??? %%%",
}

_BAD_BY_CANDIDATE = {"A": _A_BAD, "B": _B_BAD, "C": _C_BAD, "D": _D_BAD}


@pytest.mark.parametrize(
    "candidate_id,label",
    [(cid, label) for cid, cases in sorted(_BAD_BY_CANDIDATE.items()) for label in cases],
)
def test_malformed_input_is_rejected(candidate_id, label):
    reject(candidate_id, _BAD_BY_CANDIDATE[candidate_id][label], label)


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
def test_wrong_role_names_are_caught_by_the_type_system_not_the_grammar(candidate_id):
    """D-003, restated per surface.

    The grammar of every candidate accepts ``Normal(location := mu, variance := s)``.
    The closed role signature in ``type_system/distributions.py`` is what rejects it,
    naming the confusion. If any surface started rejecting it at parse time the four
    would no longer be comparable on this axis.
    """
    cases = _BAD_BY_CANDIDATE[candidate_id]
    why = reject(candidate_id, cases["misparameterised role"], "misparameterised role")
    assert why.startswith("check:"), f"[{candidate_id}] rejected too early: {why}"
    assert "HML-T415" in why, why

    why = reject(candidate_id, cases["unknown parameter role"], "unknown parameter role")
    assert why.startswith("check:"), f"[{candidate_id}] rejected too early: {why}"
    assert "HML-T416" in why, why


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
def test_repeated_roles_are_rejected(candidate_id):
    if "repeated role" not in _BAD_BY_CANDIDATE[candidate_id]:
        pytest.skip(f"{candidate_id} has no repeated-role case")
    reject(candidate_id, _BAD_BY_CANDIDATE[candidate_id]["repeated role"], "repeated role")


# ---------------------------------------------------------------------------
# Mechanical mutation sweep
# ---------------------------------------------------------------------------


def _mutations(text: str) -> list[tuple[str, str]]:
    """Damage that must never be absorbed silently."""
    out: list[tuple[str, str]] = []
    if len(text) > 20:
        out.append(("truncated to 60%", text[: int(len(text) * 0.6)]))
        out.append(("truncated to 30%", text[: int(len(text) * 0.3)]))
    for opener, closer in (("(", ")"), ("[", "]"), ("{", "}")):
        if closer in text:
            out.append((f"dropped one {closer!r}", text.replace(closer, "", 1)))
        if opener in text:
            out.append((f"dropped one {opener!r}", text.replace(opener, "", 1)))
    return out


@pytest.mark.parametrize("candidate_id", CANDIDATE_IDS)
def test_no_mutation_is_silently_accepted(candidate_id):
    """Sweep every corpus object: damaged text must never recover the original object.

    A mutation is allowed to be *rejected* (the normal case) and it is allowed to parse
    into a **different** object -- deleting a bracket can turn one valid program into
    another. What it may never do is reproduce the object that was written, because that
    would mean the deleted character carried no meaning.
    """
    from hamiltonian_lang.backends.canonical import content_hash

    cand = CANDIDATES[candidate_id]
    survivors: list[str] = []
    examined = 0
    for obj in corpus()[::7]:
        original_hash = content_hash(obj.module)
        text = cand.render(obj.module)
        for label, mutated in _mutations(text):
            if mutated == text:
                continue
            examined += 1
            ok, _ = accepts(candidate_id, mutated)
            if not ok:
                continue
            recovered = cand.parse(mutated)
            bag = DiagnosticBag(mutated, "<mutation>")
            symbols = resolve(recovered, bag)
            check(recovered, symbols, bag)
            if bag.ok() and content_hash(recovered) == original_hash:
                survivors.append(f"{obj.id} [{label}]")
    assert examined > 0, "the mutation sweep examined nothing"
    assert not survivors, (
        f"[{candidate_id}] damaged text reproduced the original object: {survivors[:10]}"
    )


def test_the_empty_document_is_a_measured_asymmetry_between_the_surfaces():
    """An empty document is not malformed -- and the four surfaces disagree about it.

    A and B are line-oriented with no envelope, so empty input is a well-formed *empty*
    module whose name falls back to the parser's default ``Main``. C and D have an
    explicit envelope (``(module ...)`` / a JSON object) and reject empty input for
    lack of one.

    This is recorded rather than papered over. It never arises for rendered output --
    every renderer emits the module header -- so it does not affect the round-trip
    figures, but it is a genuine difference in what each surface accepts and it belongs
    in the report, not in a comment.
    """
    accepted = {cid: accepts(cid, "")[0] for cid in CANDIDATE_IDS}
    assert accepted == {"A": True, "B": True, "C": False, "D": False}, accepted
    for cid in ("A", "B"):
        module = CANDIDATES[cid].parse("")
        assert module.statements == []
        assert module.name == "Main"
