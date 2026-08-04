"""Backends: one semantic object, many views.

Every backend subclasses :class:`~.base.Backend` and must declare what it could not
translate. See ``docs/design/V0_DESIGN_FREEZE.md`` section 8 for what v0 does not
support at all.

Registry entries map a target name to a callable ``(module, symbols) -> BackendResult``.
"""

from __future__ import annotations

from collections.abc import Callable

from .base import Backend, BackendResult, Unsupported

__all__ = [
    "Backend", "BackendResult", "Unsupported",
    "REGISTRY", "available", "render", "register",
]

REGISTRY: dict[str, Callable] = {}


def register(name: str, fn: Callable) -> None:
    REGISTRY[name] = fn


def _load_optional() -> None:
    """Register backends that may be contributed independently."""
    for module_name, target in (
        ("stan", "stan"),
        ("sympy", "sympy"),
        ("lean", "lean"),
    ):
        try:
            mod = __import__(f"hamiltonian_lang.backends.{module_name}", fromlist=["*"])
        except ImportError:
            continue
        fn = getattr(mod, f"to_{module_name}", None)
        if callable(fn):
            REGISTRY[target] = fn


def _bootstrap() -> None:
    from .english import to_english
    from .hml import render_module
    from .latex import to_latex

    register("latex", to_latex)
    register("english", to_english)

    def _hml(module, symbols=None) -> BackendResult:
        return BackendResult(target="hml", text=render_module(module))

    register("hml", _hml)

    def _json(module, symbols=None) -> BackendResult:
        import json

        from .canonical import to_canonical

        return BackendResult(
            target="json",
            text=json.dumps(to_canonical(module), indent=2, sort_keys=True),
        )

    register("json", _json)

    def _graph(module, symbols=None) -> BackendResult:
        import json

        from ..graph import build_graph

        if symbols is None:
            return BackendResult(
                target="graph",
                text="",
                unsupported=[
                    Unsupported("graph", "requires a resolved symbol table", 0, "dropped")
                ],
            )
        g = build_graph(module, symbols)
        return BackendResult(target="graph", text=json.dumps(g.to_dict(), indent=2))

    register("graph", _graph)

    def _triples(module, symbols=None) -> BackendResult:
        from ..graph import build_graph

        if symbols is None:
            return BackendResult(
                target="triples",
                text="",
                unsupported=[
                    Unsupported("triples", "requires a resolved symbol table", 0, "dropped")
                ],
            )
        return BackendResult(target="triples", text=build_graph(module, symbols).render_triples())

    register("triples", _triples)

    _load_optional()


_bootstrap()


def available() -> list[str]:
    return sorted(REGISTRY)


def render(target: str, module, symbols=None) -> BackendResult:
    if target not in REGISTRY:
        raise KeyError(f"unknown backend {target!r}; available: {', '.join(available())}")
    return REGISTRY[target](module, symbols)
