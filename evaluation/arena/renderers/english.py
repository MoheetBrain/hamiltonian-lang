"""Arm SE -- information-matched structured English.

This is meant to be a *strong* baseline, not a straw man. Structured English is what the
project's every previous model call used, and it saturated two benchmarks; if HML is to
claim a representation-level advantage it has to beat English written as well as English
can reasonably be written for this content.

**Unambiguity is enforced by construction.** Rule 1 of the project instructions is that a
shorter surface admitting an ambiguous reading is a regression, and that applies to the
baseline as much as to HML. Natural-language connectives scope badly -- "A and B or C"
has two readings -- so nesting is rendered with the explicitly bracketing English forms
`both ... and ...`, `either ... or ...`, `if ..., then ...`. These are wordier than the
bare connectives and that cost is real and is reported, but an English arm that could be
misread would make every result uninterpretable: a wrong answer could always be blamed
on the phrasing rather than the representation.

`Not(Atom)` is special-cased to "P does not hold" because "it is not the case that P
holds" is unambiguous but needlessly clumsy, and a baseline should not be penalised for
clumsiness that a competent writer would not produce.
"""

from __future__ import annotations

from ..ir import Atom, Cmp, Conn, Elem, Not, Prop, Quant, Rel
from ..worlds import World
from .base import arm, infix_term

__all__ = ["EnglishRenderer"]


def _arg(a) -> str:
    return str(a.value) if isinstance(a, Elem) else a.name


@arm("SE")
class EnglishRenderer:
    ARM = "SE"
    LABEL = "structured English"

    # -- propositions ------------------------------------------------------

    def prop(self, p: Prop) -> str:
        match p:
            case Atom(name):
                return f"{name} holds"
            case Rel(name, args):
                return f"{name}({', '.join(_arg(a) for a in args)}) holds"
            case Not(Atom(name)):
                return f"{name} does not hold"
            case Not(Rel(name, args)):
                return f"{name}({', '.join(_arg(a) for a in args)}) does not hold"
            case Not(inner):
                return f"it is not the case that {self.prop(inner)}"
            case Cmp(op, left, right):
                return f"{infix_term(left)} {op} {infix_term(right)}"
            case Conn(op, left, right):
                # No precedence handling is needed: every English connective form below
                # is prefix-marked, so nesting is unambiguous without brackets.
                ls, rs = self.prop(left), self.prop(right)
                if op == "and":
                    return f"both {ls} and {rs}"
                if op == "or":
                    return f"either {ls} or {rs}"
                if op == "implies":
                    return f"if {ls}, then {rs}"
                return f"{ls} if and only if {rs}"
            case Quant(kind, var, dom, body):
                if kind == "forall":
                    return f"for every {var} in {dom}, {self.prop(body)}"
                return f"there exists {var} in {dom} such that {self.prop(body)}"
            case _:  # pragma: no cover
                raise TypeError(f"not a proposition: {p!r}")

    # -- world state -------------------------------------------------------

    def state(self, w: World) -> str:
        lines: list[str] = []
        lines.append("DECLARATIONS")
        if w.family == "ALGEBRAIC_DEPENDENCY_GRAPH":
            names = ", ".join(d.name for d in w.decls)
            lines.append(f"  {names} are exact rational numbers.")
        elif w.family == "FINITE_LOGIC_WORLD":
            names = ", ".join(d.name for d in w.decls)
            lines.append(f"  {names} are propositions. Each is either true or false.")
        else:
            dom = ", ".join(str(e) for e in w.domain)
            lines.append(f"  D is the set {{{dom}}}.")
            lines.append(f"  {w.relation.name} is a binary relation on D.")

        lines.append("")
        lines.append("FACTS")
        if w.relation is not None:
            pairs = ", ".join(
                "(" + ", ".join(str(x) for x in t) + ")" for t in w.relation.true_tuples
            )
            lines.append(
                f"  f0. {w.relation.name}(x, y) holds for exactly the following "
                f"ordered pairs (x, y), and for no others:"
            )
            lines.append(f"      {pairs if pairs else '(none)'}")
        else:
            lines.append("  All of the following are true.")
            for f in w.facts:
                lines.append(f"  {f.label}. {self.prop(f.prop)}.")
        return "\n".join(lines)

    # -- the question ------------------------------------------------------

    def question(self, w: World) -> str:
        q = w.query
        if q.kind == "VALUE":
            return f"Determine the exact value of {q.target}."
        if q.kind == "ENTAILMENT":
            return (
                f"Is {q.target} necessarily true, necessarily false, or is it not "
                f"determined by these facts?"
            )
        return f"Is the following statement true or false?\n\n  {self.prop(q.claim)}"
