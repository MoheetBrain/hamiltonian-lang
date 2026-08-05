"""Verification services layered *over* the compiler, never inside it.

Nothing in this package modifies ``ast/nodes.py``, ``types.py``, the parser, the
resolver or the type checker. Every checker here reads the output of
:func:`hamiltonian_lang.compile_source` and adds one thing the compiler deliberately
does not do: it **discharges** proof obligations, within an explicitly bounded subset,
and refuses to pretend about the rest.

See :mod:`hamiltonian_lang.verification.obligations` and
``docs/architecture/HML_PROCESS_VERIFICATION.md``.
"""

from __future__ import annotations

__all__ = ["obligations"]
