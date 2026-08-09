"""Arm AST_V2 — a compact generic S-expression control. **AST-v1 is preserved, not replaced.**

Why a second control exists. The B1 pilot put the JSON AST last (0/12 pairs), but its
prompts ran 1.8x structured English, so its result was confounded with length. The binder
diagnostic then showed it could not read binder *nesting* at all: its answers were predicted
on 5/5 configurations by "say `forall` if `forall` appears anywhere", a token-presence rule.
Both defects point the same way — the tagged-object JSON encoding buries nesting inside
`{"bind": …, "body": {"bind": …}}` and pays a heavy token tax to do it.

An S-expression fixes both without borrowing anything from HML:

    forall(x, D, exists(y, D, R(x, y)))

Nesting is carried by parenthesis depth, which is the most conventional way structure is
written in every Lisp, every algebraic CAS and most textbook logic. It is compact, fully
generic, and — critically — contains **no HML machinery**: no `assume`/`goal`, no epistemic
status, no obligations, no typed declarations beyond a bare sort, no distinction between
equality and definition. If it beats the JSON AST, that is an encoding effect; if HML beats
*both*, HML's advantage is not merely "structure".

AST-v1 stays exactly where it is and keeps its results. This is an additional arm.
"""

from __future__ import annotations

import re

from ..ir import Atom, BinOp, BVar, Cmp, Conn, Elem, Not, Num, Prop, Quant, Rel, Term, Var
from ..worlds import World
from .base import arm, fmt_num

__all__ = ["SexprRenderer", "parse_sexpr_prop"]


def _term(t: Term) -> str:
    match t:
        case Num(v):
            return fmt_num(v)
        case Var(n):
            return n
        case BinOp(op, a, b):
            return f"{ {'+': 'add', '-': 'sub', '*': 'mul'}[op] }({_term(a)}, {_term(b)})"
        case _:  # pragma: no cover
            raise TypeError(t)


def _arg(a) -> str:
    return str(a.value) if isinstance(a, Elem) else a.name


_CMP_NAME = {"=": "eq", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}
_CMP_BACK = {v: k for k, v in _CMP_NAME.items()}


def _prop(p: Prop) -> str:
    match p:
        case Atom(n):
            return n
        case Rel(n, args):
            return f"{n}({', '.join(_arg(a) for a in args)})"
        case Not(x):
            return f"not({_prop(x)})"
        case Conn(op, a, b):
            return f"{op}({_prop(a)}, {_prop(b)})"
        case Cmp(op, a, b):
            return f"{_CMP_NAME[op]}({_term(a)}, {_term(b)})"
        case Quant(k, v, d, body):
            return f"{k}({v}, {d}, {_prop(body)})"
        case _:  # pragma: no cover
            raise TypeError(p)


# --- decoding ---------------------------------------------------------------

_TOK = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|-?\d+/\d+|-?\d+|[(),]")


def _split_args(s: str) -> list[str]:
    """Top-level comma split, respecting nesting."""
    out, depth, cur = [], 0, []
    for ch in s:
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        cur.append(ch)
    if cur:
        out.append("".join(cur).strip())
    return out


def parse_sexpr_prop(s: str) -> Prop:
    """Parse one S-expression proposition back to the neutral IR."""
    s = s.strip()
    m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\((.*)\)", s, re.S)
    if not m:
        return Atom(s)
    head, inner = m.group(1), m.group(2)
    args = _split_args(inner)
    if head in ("forall", "exists"):
        return Quant(head, args[0], args[1], parse_sexpr_prop(args[2]))
    if head == "not":
        return Not(parse_sexpr_prop(args[0]))
    if head in ("and", "or", "implies", "iff"):
        return Conn(head, parse_sexpr_prop(args[0]), parse_sexpr_prop(args[1]))
    if head in _CMP_BACK:
        return Cmp(_CMP_BACK[head], _parse_term(args[0]), _parse_term(args[1]))
    # Anything else applied to arguments is a relation.
    return Rel(head, tuple(Elem(int(a)) if a.lstrip("-").isdigit() else BVar(a) for a in args))


def _parse_term(s: str) -> Term:
    from fractions import Fraction

    s = s.strip()
    m = re.fullmatch(r"(add|sub|mul)\((.*)\)", s, re.S)
    if m:
        a, b = _split_args(m.group(2))
        return BinOp({"add": "+", "sub": "-", "mul": "*"}[m.group(1)], _parse_term(a), _parse_term(b))
    if re.fullmatch(r"-?\d+(/\d+)?", s):
        return Num(Fraction(s))
    return Var(s)


@arm("AST_V2")
class SexprRenderer:
    ARM = "AST_V2"
    LABEL = "generic S-expression"

    def prop(self, p: Prop) -> str:
        return _prop(p)

    def state(self, w: World) -> str:
        lines: list[str] = []
        if w.relation is not None:
            lines.append(f"D = {{{', '.join(str(e) for e in w.domain)}}}")
            lines.append(f"{w.relation.name} : relation/{w.relation.arity} over D")
            lines.append("")
            pairs = " ".join("(" + ", ".join(str(x) for x in t) + ")"
                             for t in w.relation.true_tuples)
            lines.append(f"{w.relation.name} holds exactly for: {pairs if pairs else '(none)'}")
            return "\n".join(lines)

        sort = "Real" if w.family == "ALGEBRAIC_DEPENDENCY_GRAPH" else "Proposition"
        for d in w.decls:
            lines.append(f"{d.name} : {sort}")
        lines.append("")
        for f in w.facts:
            lines.append(f"{f.label}: {_prop(f.prop)}")
        return "\n".join(lines)

    def question(self, w: World) -> str:
        q = w.query
        if q.kind == "VALUE":
            return f"Determine the exact value of {q.target}."
        if q.kind == "ENTAILMENT":
            return (
                f"Is {q.target} necessarily true, necessarily false, or is it not "
                f"determined by these facts?"
            )
        return f"Is the following statement true or false?\n\n  {_prop(q.claim)}"
