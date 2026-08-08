"""Arm HML -- the language under test, in its real surface syntax.

**Everything this arm emits must pass `hml check`.** `tests/arena/test_hml_arm.py`
compiles every rendered world with the actual compiler. An HML arm made of
plausible-looking syntax that the compiler would reject is the exact failure mode
CLAUDE.md calls the worst one in this codebase: authoritative-looking output that is
wrong. If HML cannot express a world, that is a finding to record, not a licence to
invent syntax.

Two places where HML pays a real, measured cost:

1. **Relativised quantification.** HML has no `forall x in D` binder, so a quantifier
   over a finite domain becomes `forall x : Real . x in D implies ...` (and `exists x :
   Real . x in D and ...`). That is the standard encoding and it is sound, but it is
   longer than the English and AST forms, and it makes the domain guard part of the
   formula rather than part of the binder.
2. **No uninterpreted predicate.** A declared `Predicate` is not callable (`HML-T470`),
   so a finite relation must be `def R(x, y) : Proposition := <disjunction of pairs>`,
   which grows with the extension where the other arms list tuples.

Both costs are reported in the token budget rather than engineered away. Hiding them by
giving HML a private shorthand would make the arena measure a notation that does not
exist.
"""

from __future__ import annotations

from ..ir import Atom, Cmp, Conn, Elem, Not, Prop, Quant, Rel
from ..worlds import World
from .base import PROP_PREC, arm, infix_term, needs_paren

__all__ = ["HmlRenderer"]


def _arg(a) -> str:
    return str(a.value) if isinstance(a, Elem) else a.name


@arm("HML")
class HmlRenderer:
    ARM = "HML"
    LABEL = "Hamiltonian Lang"

    # -- propositions ------------------------------------------------------

    def prop(self, p: Prop) -> str:
        """Render with minimal parentheses, except around a nested quantifier.

        A quantifier body runs to the end of the expression, so an unbracketed
        quantifier as the operand of a connective would swallow everything after it.
        Bracketing it is two characters and removes the ambiguity entirely.
        """
        match p:
            case Atom(name):
                return name
            case Rel(name, args):
                return f"{name}({', '.join(_arg(a) for a in args)})"
            case Not(inner):
                s = self._operand(inner, PROP_PREC["not"])
                return f"not {s}"
            case Cmp(op, left, right):
                return f"{infix_term(left)} {op} {infix_term(right)}"
            case Conn(op, left, right):
                prec = PROP_PREC[op]
                ls = self._operand(left, prec)
                rs = self._operand(right, prec, right_of_same=True)
                return f"{ls} {op} {rs}"
            case Quant(kind, var, dom, body):
                # The relativised body is the right operand of the guard connective, so
                # it is bracketed by the same precedence rule as any other operand. A
                # nested quantifier is always bracketed: a quantifier body runs to the
                # end of the expression, so an unbracketed one silently absorbs whatever
                # follows it. That produced a claim which parsed, and happened to mean
                # the right thing only because `implies` is right-associative -- correct
                # by luck is not correct.
                if kind == "forall":
                    inner = self._operand(body, PROP_PREC["implies"], right_of_same=True)
                    return f"forall {var} : Real . {var} in {dom} implies {inner}"
                inner = self._operand(body, PROP_PREC["and"], right_of_same=True)
                return f"exists {var} : Real . {var} in {dom} and {inner}"
            case _:  # pragma: no cover
                raise TypeError(f"not a proposition: {p!r}")

    def _operand(self, child: Prop, parent_prec: int, *, right_of_same: bool = False) -> str:
        s = self.prop(child)
        if isinstance(child, Quant) or needs_paren(child, parent_prec, right_of_same=right_of_same):
            return f"({s})"
        return s

    # -- world state -------------------------------------------------------

    def module_name(self, w: World) -> str:
        return f"Arena_{w.world_id}"

    def state(self, w: World) -> str:
        lines = [f"module {self.module_name(w)}", ""]

        if w.relation is not None:
            dom = " or ".join(f"x = {e}" for e in w.domain)
            lines.append(f"def D : Set[Real] := {{x : Real | {dom}}}")
            lines.append("")
            if w.relation.true_tuples:
                body = " or ".join(
                    "(" + " and ".join(f"{v} = {x}" for v, x in zip("xy", t, strict=True)) + ")"
                    for t in w.relation.true_tuples
                )
            else:
                # An empty extension has no disjuncts; `false` is the identity.
                body = "false"
            lines.append(
                f"def {w.relation.name}(x : Real, y : Real) : Proposition := {body}"
            )
            return "\n".join(lines)

        sort = "Real" if w.family == "ALGEBRAIC_DEPENDENCY_GRAPH" else "Proposition"
        for d in w.decls:
            lines.append(f"var {d.name} : {sort}")
        lines.append("")
        for f in w.facts:
            lines.append(f"assume {f.label} : {self.prop(f.prop)}")
        return "\n".join(lines)

    # -- the question ------------------------------------------------------

    def question(self, w: World) -> str:
        q = w.query
        if q.kind == "VALUE":
            return f"Determine the exact value of {q.target}."
        if q.kind == "ENTAILMENT":
            return (
                f"Is {q.target} necessarily true, necessarily false, or is it not "
                f"determined by these assumptions?"
            )
        return (
            "Is the following goal true or false under the definitions above?\n\n"
            f"  goal q1 : {self.prop(q.claim)}"
        )

    # -- compiler-facing form ---------------------------------------------

    def compilable(self, w: World) -> str:
        """The state plus the query as a `goal`, for `hml check`.

        The goal is stated, never asserted, so nothing here leaks the answer: `hml
        check` reports a goal as OPEN whether it is true or false.
        """
        src = self.state(w)
        q = w.query
        if q.kind == "TRUTH":
            return f"{src}\n\ngoal q1 : {self.prop(q.claim)}\n"
        if q.kind == "ENTAILMENT":
            return f"{src}\n\ngoal q1 : {q.target}\n"
        return f"{src}\n"
