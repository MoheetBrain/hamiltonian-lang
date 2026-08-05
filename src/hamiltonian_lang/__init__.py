"""Hamiltonian Lang — an AI-native mathematical language.

Private research prototype. See ``GOAL.md`` for the thesis and
``docs/design/V0_DESIGN_FREEZE.md`` for the frozen v0 contract.

No claim of superiority over any existing language is made or implied by this package.
The comparative evaluation is preregistered in ``docs/research/BENCHMARK_PROTOCOL.md``
and has not yet returned a verdict.

Typical use::

    from hamiltonian_lang import compile_source
    result = compile_source(open("model.hml").read())
    if result.ok():
        print(result.render("english").text)
    else:
        print(result.diagnostics.render())
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ast.nodes import Module
from .diagnostics import DiagnosticBag, HamiltonianError
from .parser import parse as _parse
from .semantics import SymbolTable
from .semantics import resolve as _resolve
from .type_system import CheckResult, ProofObligation
from .type_system import check as _check

__version__ = "0.1.0"
__all__ = [
    "__version__",
    "CompileResult",
    "parse",
    "compile_source",
    "canonical_json",
    "content_hash",
    "HamiltonianError",
]


@dataclass
class CompileResult:
    module: Module
    diagnostics: DiagnosticBag
    symbols: SymbolTable | None = None
    obligations: list[ProofObligation] = field(default_factory=list)
    source: str = ""

    def ok(self) -> bool:
        """Did **every** stage accept this source: lex, parse, resolve and type-check.

        **This is not a parse verdict.** Wrong arity (``HML-T426``), a wrong role label
        (``HML-T415``), a declared-type mismatch (``HML-T403``) and an epistemic-kind
        mismatch all *parse* cleanly and fail later; an unknown identifier parses cleanly
        and fails in resolution. A harness that reads ``ok()`` as "the output parsed"
        understates its parse rate and attributes type and scope defects to the surface
        syntax — which, for a study measuring whether a candidate syntax is writable, is
        the most damaging direction to be wrong in.

        Use :func:`hamiltonian_lang.improvement.episodes.classify_stages` when the stage
        matters; it runs each stage in its own right and reports all of them.
        """
        return self.diagnostics.ok()

    def render(self, target: str):
        from .backends import render as _render

        return _render(target, self.module, self.symbols)

    def canonical(self) -> str:
        from .backends.canonical import canonical_json

        return canonical_json(self.module)

    def hash(self) -> str:
        from .backends.canonical import content_hash

        return content_hash(self.module)

    def graph(self):
        from .graph import build_graph

        if self.symbols is None:
            raise ValueError("no symbol table: resolution did not run")
        return build_graph(self.module, self.symbols)

    def raise_for_errors(self) -> CompileResult:
        if not self.ok():
            raise HamiltonianError(self.diagnostics)
        return self


def parse(source: str, file: str = "<input>"):
    """Parse only. Returns ``(module, diagnostics)``."""
    return _parse(source, file)


def compile_source(source: str, file: str = "<input>") -> CompileResult:
    """Full pipeline: lex, parse, resolve, type-check.

    Always returns a result; inspect ``.ok()`` and ``.diagnostics``. Later stages are
    skipped when an earlier stage failed, so diagnostics do not cascade.
    """
    bag = DiagnosticBag(source, file)
    module, bag = _parse(source, file, bag)
    if not bag.ok():
        return CompileResult(module, bag, None, [], source)

    symbols = _resolve(module, bag)
    if not bag.ok():
        return CompileResult(module, bag, symbols, [], source)

    result: CheckResult = _check(module, symbols, bag)
    return CompileResult(module, bag, symbols, result.obligations, source)


def canonical_json(source: str) -> str:
    return compile_source(source).raise_for_errors().canonical()


def content_hash(source: str) -> str:
    return compile_source(source).raise_for_errors().hash()
