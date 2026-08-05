"""Candidate A -- V0 labelled-linear (HML-L1 as frozen).

The implemented surface. The renderer's obligation is not to be pretty but to emit text
that ``hamiltonian_lang.parser`` accepts and that reads back to the same canonical
object, so it is written against the parser's productions rather than against
``backends/hml.py``'s pretty-printer.

Two places where that distinction has teeth, both verified against the parser:

* ``^`` and ``=>``/``<=>`` are right-associative, so a *left*-nested occurrence needs
  parentheses. ``backends/hml.py`` parenthesises neither, which silently turns
  ``(a ^ b) ^ c`` into ``a ^ b ^ c``.
* ``check dimension`` reads its subject at the additive level, because the ``=`` that
  may follow introduces a dimension and not an equation. A subject that binds looser
  than ``+`` must be parenthesised.
"""

from __future__ import annotations

from hamiltonian_lang.ast.nodes import (
    AssumeStmt,
    CheckStmt,
    ConceptDecl,
    ConceptMember,
    Declaration,
    DefineStmt,
    InferStmt,
    LawStmt,
    Module,
    ModuleDecl,
    ObjectiveStmt,
    ProveStmt,
    RequireStmt,
    SolveStmt,
    Statement,
)
from hamiltonian_lang.parser import parse as parse_hml

from ._infix import HML_L1, render_expr, render_expr_at, render_type
from .core import SurfaceParseError, SyntaxCandidate, validate_supported

__all__ = ["CandidateA", "render_module_a"]

SURFACE = "A"

#: The additive level, matching ``parser.parse_check``'s entry point for a dimension
#: subject. Named rather than inlined because the coupling is easy to miss.
_ADDITIVE_PREC = 5


def _member(m: ConceptMember) -> str:
    params = ""
    if m.params:
        inner = ", ".join(f"{n} : {render_type(t)}" for n, t in m.params)
        params = f"({inner})"
    annotation = f" : {render_type(m.declared_type)}" if m.declared_type is not None else ""
    body = f" := {render_expr(m.body, HML_L1)}" if m.body is not None else ""
    return f"    {m.kind} {m.name}{params}{annotation}{body}"


def render_statement_a(st: Statement) -> str:
    if isinstance(st, ModuleDecl):
        return f"module {st.name}"

    if isinstance(st, Declaration):
        line = f"{st.kind} {st.name} : {render_type(st.declared_type)}"
        if st.value is not None:
            line += f" = {render_expr(st.value, HML_L1)}"
        return line

    if isinstance(st, DefineStmt):
        params = ""
        if st.params:
            inner = ", ".join(
                n if t is None else f"{n} : {render_type(t)}" for n, t in st.params
            )
            params = f"({inner})"
        annotation = (
            f" : {render_type(st.declared_type)}" if st.declared_type is not None else ""
        )
        return f"def {st.name}{params}{annotation} := {render_expr(st.body, HML_L1)}"

    if isinstance(st, LawStmt):
        given = f" | {' '.join(g.name for g in st.given)}" if st.given else ""
        return f"{st.role} {st.target}{given} ~ {render_expr(st.distribution, HML_L1)}"

    if isinstance(st, AssumeStmt):
        return f"assume {render_expr(st.proposition, HML_L1)}"
    if isinstance(st, RequireStmt):
        return f"require {render_expr(st.proposition, HML_L1)}"
    if isinstance(st, ProveStmt):
        return f"prove {render_expr(st.proposition, HML_L1)}"

    if isinstance(st, ObjectiveStmt):
        return f"{st.direction} {render_expr(st.expression, HML_L1)}"

    if isinstance(st, SolveStmt):
        return f"solve {' '.join(t.name for t in st.targets)}"

    if isinstance(st, InferStmt):
        return f"infer {st.query} {' '.join(t.name for t in st.targets)}"

    if isinstance(st, CheckStmt):
        if st.check_kind == "dimension":
            subject = render_expr_at(st.subject, _ADDITIVE_PREC, HML_L1)
            line = f"check dimension {subject}"
            if st.expected is not None:
                line += f" = {st.expected}"
            return line
        return f"check {render_expr(st.subject, HML_L1)}"

    if isinstance(st, ConceptDecl):
        head = f"concept {st.name}"
        if st.extends:
            head += " extends " + ", ".join(st.extends)
        return "\n".join([head, *(_member(m) for m in st.members), "end"])

    raise AssertionError(f"validate_supported let through {type(st).__name__}")


def render_module_a(module: Module) -> str:
    validate_supported(module, SURFACE)
    lines: list[str] = []
    if not any(isinstance(s, ModuleDecl) for s in module.statements):
        lines.append(f"module {module.name}")
    lines.extend(render_statement_a(st) for st in module.statements)
    return "\n".join(lines) + "\n"


class CandidateA(SyntaxCandidate):
    id = "A"
    name = "V0 labelled-linear (HML-L1)"
    family = "line-oriented infix, role-labelled distribution arguments, `end`-delimited"

    def render(self, module: Module) -> str:
        return render_module_a(module)

    def parse(self, text: str) -> Module:
        parsed, bag = parse_hml(text, f"<candidate-{SURFACE}>")
        if not bag.ok():
            raise SurfaceParseError(
                SURFACE,
                "; ".join(f"{d.code} {d.message}" for d in bag.errors),
                bag,
            )
        return parsed
