"""Arm AST -- a generic semantic JSON tree. **This is the required control.**

Without it, any advantage measured for HML could be an advantage of *structure in
general* -- of receiving an explicit tree instead of prose -- and the project would
attribute it to HML specifically. That is the single most likely way this experiment
could produce a confident wrong conclusion, so the control is not optional.

The node vocabulary is the generic Apply/Bind/Name/Lit core that D-041 rejected as an
internal representation for HML. Using it here is not a reopening of D-041: that
decision was about what HML's *own* AST should be, judged on compositional coverage.
Here the same core is exactly what a neutral control wants, because it is what a
competent engineer would reach for knowing nothing about this project.

**What this arm deliberately does not have.** Comparisons are ordinary applications, not
a distinguished node kind. There are no sorts on expressions, no evidence status, no
rule roles, no distinction between equality and definition. It carries the same *facts*
as the other two arms and none of HML's ontology. If HML wins here, that gap is the
candidate explanation; if it does not, structure alone was enough.

**Serialisation is compact on purpose, and that took two attempts.** Pretty-printed at
`indent=2` with fully tagged nodes, this arm ran 4.7x the length of structured English
on the algebraic family. A control inflated that far is not a control: every HML win
would then be equally consistent with "HML beats verbose JSON", which is not a claim
anybody wants to defend. The encoding below drops the wrapper objects that carried no
information -- a name is a JSON string, an integer literal is a JSON number, an
application is `{"op": ..., "args": [...]}`. That is unambiguous here because the IR's
terms are only names and numbers, and it is a standard idiom (JsonLogic, MathJSON, and
most lightweight ASTs encode arithmetic this way).

What is *not* done: abbreviating keys to `n`/`o`/`a`. That would buy tokens by making the
control cryptic, which is the same error in the other direction. A tree serialisation is
inherently longer than infix notation, and `budget.py` reports the residual difference
instead of engineering it away.
"""

from __future__ import annotations

import json

from ..ir import Atom, BinOp, Cmp, Conn, Elem, Not, Num, Prop, Quant, Rel, Term, Var
from ..worlds import World
from .base import arm, fmt_num

__all__ = ["AstRenderer"]

_SEP = (",", ":")


def _dumps(node) -> str:
    return json.dumps(node, separators=_SEP)


def _lit(v) -> object:
    """An exact integer becomes a JSON number; anything else keeps its exact text."""
    if isinstance(v, int):
        return v
    return {"lit": fmt_num(v)} if v.denominator != 1 else v.numerator


def _term(t: Term) -> object:
    match t:
        case Num(value):
            return _lit(value)
        case Var(name):
            return name
        case BinOp(op, left, right):
            return {"op": op, "args": [_term(left), _term(right)]}
        case _:  # pragma: no cover
            raise TypeError(f"not a term: {t!r}")


def _arg(a) -> object:
    return a.value if isinstance(a, Elem) else a.name


def _prop(p: Prop) -> object:
    match p:
        case Atom(name):
            return name
        case Rel(name, args):
            return {"op": name, "args": [_arg(a) for a in args]}
        case Not(inner):
            return {"op": "not", "args": [_prop(inner)]}
        case Conn(op, left, right):
            return {"op": op, "args": [_prop(left), _prop(right)]}
        case Cmp(op, left, right):
            # A comparison is just an application. The control does not get HML's
            # distinction between an equation and any other binary operator.
            return {"op": op, "args": [_term(left), _term(right)]}
        case Quant(kind, var, dom, body):
            return {"bind": kind, "var": var, "domain": dom, "body": _prop(body)}
        case _:  # pragma: no cover
            raise TypeError(f"not a proposition: {p!r}")


@arm("AST")
class AstRenderer:
    ARM = "AST"
    LABEL = "generic semantic AST"

    def prop(self, p: Prop) -> str:
        return _dumps(_prop(p))

    def state(self, w: World) -> str:
        decls: list[dict] = []
        facts: list[dict] = []

        if w.relation is not None:
            decls.append({"decl": "D", "sort": "set", "elements": list(w.domain)})
            decls.append(
                {"decl": w.relation.name, "sort": "relation", "arity": w.relation.arity}
            )
            facts.append(
                {
                    "fact": "f0",
                    "extension_of": w.relation.name,
                    "holds_exactly_for": [list(t) for t in w.relation.true_tuples],
                }
            )
        else:
            for d in w.decls:
                decls.append({"decl": d.name, "sort": d.sort})
            for f in w.facts:
                facts.append({"fact": f.label, "body": _prop(f.prop)})

        d = ",\n    ".join(_dumps(x) for x in decls)
        f = ",\n    ".join(_dumps(x) for x in facts)
        return '{\n  "decls": [\n    ' + d + '\n  ],\n  "facts": [\n    ' + f + "\n  ]\n}"

    def question(self, w: World) -> str:
        q = w.query
        if q.kind == "VALUE":
            return (
                "Determine the value requested by this query node:\n\n  "
                + _dumps({"query": "value_of", "target": q.target})
            )
        if q.kind == "ENTAILMENT":
            return (
                "Decide whether the facts entail the target of this query node, refute "
                "it, or leave it undetermined:\n\n  "
                + _dumps({"query": "entailment", "target": q.target})
            )
        return (
            "Is the claim in this query node true or false?\n\n  "
            + _dumps({"query": "truth_of", "claim": _prop(q.claim)})
        )
